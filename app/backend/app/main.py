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

try:  # pydicom >= 3
    from pydicom.pixels import apply_color_lut, convert_color_space
    PYDICOM3 = True
except ImportError:  # pydicom 2.x
    from pydicom.pixel_data_handlers.util import apply_color_lut, convert_color_space
    PYDICOM3 = False

# JPEG, JPEG-LS and JPEG 2000 transfer syntaxes all start with this prefix
JPEG_FAMILY = "1.2.840.10008.1.2.4."
CROP_TO_IMAGE = True   # set False to keep the full screen capture


# --------------------------------------------------------------------------- config

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / ".pyrestus-jobs"
WEB = ROOT / "app" / "build" / "web"
DEFAULT = Path.home() / "Documents" / "Pyrestus Results"

DICOM_EXT = {".dcm", ".dicom", ""}
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
    # if frame.ndim == 3:
    #     if frame.shape[2] == 4:
    #         frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
    #     elif frame.shape[2] == 3:
    #         frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    #     else:
    #         frame = frame[..., 0]
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


# def convert_dicom(src: Path, out: Path, fmt: str, on_frame) -> int:
#     ds = pydicom.dcmread(str(src))
#     pixels = ds.pixel_array
#     photometric = str(getattr(ds, "PhotometricInterpretation", "")).upper()
#     samples = int(getattr(ds, "SamplesPerPixel", 1))

#     # Multi-frame if: grayscale with 3 dims, or color with 4 dims
#     is_multi = pixels.ndim == 4 or (pixels.ndim == 3 and samples == 1)
#     frames = pixels if is_multi else pixels[np.newaxis, ...]

#     for i, f in enumerate(frames):
#         if samples == 3 and photometric.startswith("YBR"):
#             f = cv2.cvtColor(np.asarray(f, dtype=np.uint8), cv2.COLOR_YCrCb2BGR)
#         elif samples == 3:  # DICOM color is RGB; OpenCV expects BGR
#             f = cv2.cvtColor(to_uint8(np.asarray(f)), cv2.COLOR_RGB2BGR)
#         write_frame(f, out, i, fmt)
#         on_frame()
#     return len(frames)



def ultrasound_region(ds, rows: int, cols: int):
    """Crop box (y0, y1, x0, x1) from the DICOM's ultrasound region tags, or None."""
    regions = ds.get("SequenceOfUltrasoundRegions")
    if not regions:
        return None

    boxes = []
    for r in regions:
        try:
            x0, y0 = int(r.RegionLocationMinX0), int(r.RegionLocationMinY0)
            x1, y1 = int(r.RegionLocationMaxX1), int(r.RegionLocationMaxY1)
        except AttributeError:
            continue
        # RegionSpatialFormat 1 = 2D image (skip M-mode / spectral Doppler strips)
        if int(r.get("RegionSpatialFormat", 0)) == 1 and x1 > x0 and y1 > y0:
            boxes.append((x0, y0, x1, y1))

    if not boxes:
        return None

    # Union of all 2D regions -> also handles side-by-side dual views
    x0 = max(0, min(b[0] for b in boxes))
    y0 = max(0, min(b[1] for b in boxes))
    x1 = min(cols, max(b[2] for b in boxes) + 1)
    y1 = min(rows, max(b[3] for b in boxes) + 1)
    return (y0, y1, x0, x1)


def auto_region(arr: np.ndarray):
    """Fallback: find the scan area from the pixels. arr is uint8, (n, h, w[, 3])."""
    gray = arr.max(axis=-1) if arr.ndim == 4 else arr
    h, w = gray.shape[1:3]

    if len(gray) > 1:
        # Multi-frame: the scan moves, text/labels stay still
        mask = (gray.max(axis=0).astype(np.int16) - gray.min(axis=0)) > 12
    else:
        # Single frame: largest non-black area
        mask = gray[0] > 12

    mask = cv2.morphologyEx(mask.astype(np.uint8) * 255, cv2.MORPH_CLOSE,
                            np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    x, y, bw, bh = cv2.boundingRect(max(contours, key=cv2.contourArea))
    if bw * bh < 0.10 * h * w:      # too small to be the scan -> don't crop
        return None
    return (y, y + bh, x, x + bw)
def looks_like_ybr(arr: np.ndarray) -> bool:
    """True if 3-channel uint8 data is YCbCr rather than RGB (checks the pixels, not the tag)."""
    step = max(1, len(arr) // 8)                      # sample up to ~8 frames
    s = arr[::step, ::4, ::4].astype(np.int16)        # and every 4th pixel
    c0, c1, c2 = s[..., 0], s[..., 1], s[..., 2]
    rgb_score = (np.abs(c0 - c1) + np.abs(c1 - c2)).mean()   # ~0 if gray RGB
    ybr_score = (np.abs(c1 - 128) + np.abs(c2 - 128)).mean() # ~0 if gray YBR
    return ybr_score < rgb_score


def dicom_frames_bgr(ds) -> np.ndarray:
    """Return all frames as uint8, shape (n, rows, cols) or (n, rows, cols, 3) in BGR."""
    arr = ds.pixel_array
    pi = str(ds.get("PhotometricInterpretation", "")).upper().strip()
    samples = int(ds.get("SamplesPerPixel", 1))
    n_frames = int(ds.get("NumberOfFrames", 1) or 1)

    if n_frames == 1:
        arr = arr[np.newaxis, ...]

    is_color = False

    if pi == "PALETTE COLOR":
        arr = apply_color_lut(arr, ds)
        if arr.dtype != np.uint8:
            arr = (arr >> 8).astype(np.uint8) if arr.max() > 255 else arr.astype(np.uint8)
        is_color = True

    elif samples == 3 and arr.shape[-1] == 3:
        arr = to_uint8(arr)
        # Decide from the pixels: decoders/pydicom versions differ in whether
        # they already converted YBR -> RGB, and some files are mislabeled.
        if looks_like_ybr(arr):
            # Pixels are full-resolution YCbCr here (422 already upsampled),
            # so convert as YBR_FULL. pydicom uses the correct Y, Cb, Cr order.
            arr = convert_color_space(arr, "YBR_FULL", "RGB")
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        is_color = True

    if not is_color:
        arr = to_uint8(arr)
        if pi == "MONOCHROME1":
            arr = 255 - arr

    if is_color:                      # RGB -> BGR for OpenCV
        arr = arr[..., ::-1]

    if CROP_TO_IMAGE:
        rows, cols = arr.shape[1:3]
        box = ultrasound_region(ds, rows, cols) or auto_region(arr)
        if box:
            y0, y1, x0, x1 = box
            arr = arr[:, y0:y1, x0:x1]

    return np.ascontiguousarray(arr)




def convert_dicom(src: Path, out: Path, fmt: str, on_frame) -> int:
    ds = pydicom.dcmread(str(src))
    if "PixelData" not in ds:
        raise ValueError(f"{src.name}: this DICOM has no image data")

    frames = dicom_frames_bgr(ds)
    for i, f in enumerate(frames):
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
