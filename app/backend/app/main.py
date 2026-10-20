"""Pyrestus local API: converts DICOM ultrasound and video files to image frames."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Literal, Optional

import cv2
import numpy as np
import pydicom
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --------------------------------------------------------------------------- config

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / ".pyrestus-jobs"
WEB = ROOT / "app" / "build" / "web"
DEFAULT = Path.home() / "Documents" / "Pyrestus Results"

DICOM_EXT = {".dcm", ".dicom"}
VIDEO_EXT = {".avi", ".mp4", ".mov", ".mkv"}
ALLOWED_EXT = DICOM_EXT | VIDEO_EXT
CHUNK = 1024 * 1024  # 1 MB upload chunks

WORK.mkdir(parents=True, exist_ok=True)

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
DIALOG_LOCK = threading.Lock()

app = FastAPI(title="Pyrestus Local API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Options(BaseModel):
    output_directory: Optional[str] = None
    output_format: Literal["png", "jpg"] = "png"


# --------------------------------------------------------------------------- helpers

def get_job(job_id: str) -> dict:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


def update_job(job: dict, **fields) -> None:
    with JOBS_LOCK:
        job.update(fields)


def snapshot(job: dict) -> dict:
    """Copy for JSON responses so the worker thread can't change it mid-serialization."""
    with JOBS_LOCK:
        return {**job, "files": list(job["files"])}


def unique_path(folder: Path, name: str) -> Path:
    target = folder / name
    stem, suffix = Path(name).stem, Path(name).suffix
    k = 1
    while target.exists():
        target = folder / f"{stem}_{k}{suffix}"
        k += 1
    return target


def ensure_writable(folder: Path) -> None:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / f".pyrestus-write-test-{uuid.uuid4().hex}"
        probe.write_bytes(b"")
        probe.unlink()
    except OSError as e:
        raise HTTPException(400, f"Pyrestus cannot write to {folder}: {e.strerror or e}")


# --------------------------------------------------------------------------- folder dialog

def _applescript_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _powershell_str(s: str) -> str:
    return s.replace("'", "''")


def open_folder_dialog() -> Optional[str]:
    """Show the OS-native folder dialog. Returns a path, or None if cancelled.

    Runs as a separate process, so it is safe from any thread (unlike tkinter),
    appears above the browser, and lists system folders and external drives.
    """
    start = str(DEFAULT if DEFAULT.exists() else Path.home())
    title = "Choose Pyrestus output folder"

    if sys.platform == "darwin":
        script = (
            f'POSIX path of (choose folder with prompt "{title}" '
            f'default location (POSIX file "{_applescript_str(start)}") with invisibles)'
        )
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if r.returncode != 0:
            if "-128" in r.stderr:  # user cancelled
                return None
            raise RuntimeError(r.stderr.strip() or "osascript failed")
        path = r.stdout.strip()
        return path.rstrip("/") or "/" if path else None

    if os.name == "nt":
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "[System.Windows.Forms.Application]::EnableVisualStyles();"
            "$f = New-Object System.Windows.Forms.Form -Property @{TopMost=$true; ShowInTaskbar=$false};"
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
            f"$d.Description = '{title}';"
            "$d.ShowNewFolderButton = $true;"
            f"$d.SelectedPath = '{_powershell_str(start)}';"
            "if ($d.ShowDialog($f) -eq 'OK') { [Console]::Out.Write($d.SelectedPath) };"
            "$f.Dispose()"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", ps],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or "PowerShell failed")
        return r.stdout.strip() or None

    # Linux / BSD
    candidates = [
        ["zenity", "--file-selection", "--directory", f"--title={title}", f"--filename={start}/"],
        ["kdialog", "--getexistingdirectory", start, "--title", title],
    ]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            return r.stdout.strip() or None  # non-zero exit = cancelled
    raise RuntimeError("No folder dialog found. Install zenity (e.g. sudo apt install zenity).")


# --------------------------------------------------------------------------- frame writing

def to_uint8(frame: np.ndarray) -> np.ndarray:
    """Scale any bit depth (e.g. 16-bit DICOM) to 8-bit for PNG/JPG."""
    if frame.dtype == np.uint8:
        return frame
    frame = frame.astype(np.float32)
    lo, hi = float(frame.min()), float(frame.max())
    if hi <= lo:
        return np.zeros(frame.shape, dtype=np.uint8)
    return ((frame - lo) * (255.0 / (hi - lo))).astype(np.uint8)


def write_frame(frame: np.ndarray, out: Path, index: int, fmt: str) -> None:
    frame = to_uint8(np.asarray(frame))
    if frame.ndim == 3:
        if frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        elif frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            frame = frame[..., 0]
    params = [cv2.IMWRITE_JPEG_QUALITY, 95] if fmt == "jpg" else []
    if not cv2.imwrite(str(out / f"{index:04d}.{fmt}"), frame, params):
        raise RuntimeError(f"Could not write frame {index} to {out}")


def convert_video(src: Path, out: Path, fmt: str, on_frame) -> int:
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise ValueError(f"{src.name}: this video could not be opened")
    count = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            write_frame(frame, out, count, fmt)
            count += 1
            on_frame()
    finally:
        cap.release()
    if count == 0:
        raise ValueError(f"{src.name}: no frames found in video")
    return count


def convert_dicom(src: Path, out: Path, fmt: str, on_frame) -> int:
    ds = pydicom.dcmread(str(src))
    pixels = ds.pixel_array
    photometric = str(getattr(ds, "PhotometricInterpretation", "")).upper()
    samples = int(getattr(ds, "SamplesPerPixel", 1))

    # Multi-frame if: grayscale with 3 dims, or color with 4 dims
    is_multi = pixels.ndim == 4 or (pixels.ndim == 3 and samples == 1)
    frames = pixels if is_multi else pixels[np.newaxis, ...]

    for i, f in enumerate(frames):
        if samples == 3 and photometric.startswith("YBR"):
            f = cv2.cvtColor(np.asarray(f, dtype=np.uint8), cv2.COLOR_YCrCb2BGR)
        elif samples == 3:  # DICOM color is RGB; OpenCV expects BGR
            f = cv2.cvtColor(to_uint8(np.asarray(f)), cv2.COLOR_RGB2BGR)
        write_frame(f, out, i, fmt)
        on_frame()
    return len(frames)


# --------------------------------------------------------------------------- worker

def run_job(job_id: str) -> None:
    job = get_job(job_id)
    inputs = WORK / job_id / "inputs"
    out_root = Path(job["output_directory"])
    fmt = job["output_format"]
    total = job["total_files"]

    def tick() -> None:
        with JOBS_LOCK:
            job["frames_created"] += 1

    try:
        for n, name in enumerate(list(job["files"]), start=1):
            update_job(job, message=f"Processing {name} ({n} of {total})")
            src = inputs / name
            out = out_root / src.stem
            out.mkdir(parents=True, exist_ok=True)

            if src.suffix.lower() in DICOM_EXT:
                convert_dicom(src, out, fmt, tick)
            else:
                convert_video(src, out, fmt, tick)

            update_job(job, files_completed=n)

        update_job(job, status="completed", message="Processing complete")
    except Exception as e:
        update_job(job, status="failed", message="Processing could not be completed", error=str(e))
    finally:
        shutil.rmtree(WORK / job_id, ignore_errors=True)  # remove temporary upload copies


# --------------------------------------------------------------------------- routes

@app.get("/api/health")
def health():
    return {"status": "healthy", "mode": "local"}


@app.post("/api/output-directory/select")
def select_output_directory():
    # Plain `def`: FastAPI runs it in a thread pool, so the server stays responsive.
    if not DIALOG_LOCK.acquire(blocking=False):
        raise HTTPException(409, "A folder dialog is already open")
    try:
        folder = open_folder_dialog()
    except Exception as e:
        raise HTTPException(500, f"Could not open folder dialog: {e}")
    finally:
        DIALOG_LOCK.release()

    if not folder:
        return {"selected": False, "path": None}

    ensure_writable(Path(folder))
    return {"selected": True, "path": folder, "path_display": folder}


@app.post("/api/jobs")
def create_job(o: Options):
    job_id = uuid.uuid4().hex
    (WORK / job_id / "inputs").mkdir(parents=True)
    job = {
        "id": job_id,
        "status": "created",
        "files": [],
        "total_files": 0,
        "files_completed": 0,
        "frames_created": 0,
        "output_format": o.output_format,
        "output_directory": None,
        "message": "Ready for files",
        "error": None,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    return snapshot(job)


@app.post("/api/jobs/{job_id}/files")
async def upload_files(job_id: str, files: list[UploadFile] = File(...)):
    job = get_job(job_id)
    if job["status"] not in ("created", "ready"):
        raise HTTPException(409, "Files can only be added before processing starts")

    dest = WORK / job_id / "inputs"
    rejected = []

    for f in files:
        name = Path(f.filename or "input").name
        if Path(name).suffix.lower() not in ALLOWED_EXT:
            rejected.append(name)
            continue
        target = unique_path(dest, name)
        with target.open("wb") as out:
            while chunk := await f.read(CHUNK):
                out.write(chunk)
        await f.close()
        with JOBS_LOCK:
            job["files"].append(target.name)

    if not job["files"]:
        raise HTTPException(400, "No supported files were uploaded")

    update_job(
        job,
        total_files=len(job["files"]),
        status="ready",
        message="Files ready" + (f" (skipped: {', '.join(rejected)})" if rejected else ""),
    )
    return snapshot(job)


@app.post("/api/jobs/{job_id}/process")
def process_job(job_id: str, o: Options):
    job = get_job(job_id)
    if not job["files"]:
        raise HTTPException(400, "Add at least one file first")
    if job["status"] == "processing":
        raise HTTPException(409, "This job is already processing")

    out = Path(o.output_directory).expanduser() if o.output_directory else DEFAULT
    ensure_writable(out)

    update_job(
        job,
        status="processing",
        output_directory=str(out),
        output_format=o.output_format,
        files_completed=0,
        frames_created=0,
        message="Starting processing",
        error=None,
    )
    threading.Thread(target=run_job, args=(job_id,), daemon=True).start()
    return snapshot(job)


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    return snapshot(get_job(job_id))


@app.post("/api/jobs/{job_id}/open-output-directory")
def open_output_directory(job_id: str):
    folder = get_job(job_id)["output_directory"]
    if not folder or not Path(folder).exists():
        raise HTTPException(404, "Output folder not found")

    if sys.platform == "darwin":
        subprocess.Popen(["open", folder])
    elif os.name == "nt":
        os.startfile(folder)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", folder])
    return {"opened": True}


# Static web build last, so /api routes take priority.
if WEB.exists():
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
