# Pyrestus

**Py**thon **Re**search **T**ools for **U**ltrasonography in **S**wallowing

Pyrestus is a research toolkit for studying ultrasound imaging of swallowing. It combines a set of Python processing tools with a local web application (Flutter front end, FastAPI back end) for working with ultrasound data.

> **Status:** under active development. Interfaces and folder layout may change.

---

## Table of contents

- [Repository layout](#repository-layout)
- [Requirements](#requirements)
- [Option A: Web app (recommended)](#option-a-web-app-recommended)
- [Option B: Core Python tools](#option-b-core-python-tools)
- [Legacy modules](#legacy-modules)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Repository layout

| Path | Description |
| --- | --- |
| `app/` | Web application: Flutter front end (`app/`) and FastAPI back end (`app/backend/`) |
| `usv/` | <!-- TODO: one-line description --> |
| `sequences/` | <!-- TODO: one-line description --> |
| `skip/` | <!-- TODO: one-line description --> |
| `dev/` | Development files |
| `legacy/` | Earlier standalone modules (see [Legacy modules](#legacy-modules)) |
| `setup-web.sh` | Builds the web app (Python venv, back-end deps, Flutter web build) |
| `pyrestus-web.sh` | Starts, stops and monitors the web app |
| `setup.sh` | macOS setup for the core Python tools (Homebrew, Anaconda, conda env) |
| `setup.py` | Builds the Cython extensions |
| `environment.yml` | Conda environment definition |
| `requirements-core.txt` | Dependencies for the core tools |
| `requirements.txt` | Full dependency list |

---

## Requirements

**Core tools**

- Python 3.8 or above
- `numpy` >= 1.12
- `pandas` >= 1.3
- `opencv-python` >= 4.5
- `tqdm` >= 4.0
- `Pillow` >= 8.4
- `scipy` >= 1.7
- `Cython` >= 0.29

**Web app (additionally)**

- Python 3 with `venv`
- [Flutter SDK](https://docs.flutter.dev/get-started/install) available on your `PATH`
- Back-end dependencies listed in `app/backend/requirements.txt` (installed automatically by the setup script)

---

## Option A: Web app (recommended)

The web app is built once and then served locally at <http://127.0.0.1:8080>.

### 1. Clone the repository

```bash
git clone https://github.com/wilys-json/pyrestus-app.git
cd pyrestus-app
```

### 2. Build

```bash
./setup-web.sh
```

This script will:

1. Check that `python3` and `flutter` are installed.
2. Create a virtual environment at `.venv/` (reused if it already exists).
3. Install the back-end dependencies from `app/backend/requirements.txt`.
4. Run `flutter clean`, `flutter pub get` and `flutter build web` inside `app/`, with the API URL set to `/api`.

### 3. Run

```bash
./pyrestus-web.sh start
```

The server starts with `uvicorn` on `127.0.0.1:8080` and opens your browser automatically when it is ready.

| Command | Action |
| --- | --- |
| `./pyrestus-web.sh start` | Start the app |
| `./pyrestus-web.sh stop` | Stop the app |
| `./pyrestus-web.sh restart` | Restart the app |
| `./pyrestus-web.sh status` | Show whether the app is running |
| `./pyrestus-web.sh logs` | Follow the last 100 lines of the log |

Runtime files are written to the project root: `.pyrestus-web.pid` and `.pyrestus-web.log`. A health check is available at `/api/health`.

---

## Option B: Core Python tools

### macOS

```bash
git clone https://github.com/wilys-json/pyrestus-app.git
cd pyrestus-app
/bin/bash setup.sh
```

`setup.sh` installs Homebrew and Anaconda if needed, creates the `pyrestus` conda environment from `environment.yml`, and builds the Cython extensions with `python3 -m setup build_ext --inplace`.

Afterwards, activate the environment in new terminals with:

```bash
conda activate pyrestus
```

### Windows

1. Clone the repository:
   ```bash
   git clone https://github.com/wilys-json/pyrestus-app.git
   ```
2. Install [Python 3.8+](https://www.python.org/downloads/).
3. Open Command Prompt in the project folder and run:
   ```bash
   python -m pip install -r requirements-core.txt
   ```

### Linux

There is no dedicated script. Create a virtual environment or conda environment, then install the core requirements:

```bash
python -m pip install -r requirements-core.txt
python -m setup build_ext --inplace
```

---

## Legacy modules

Earlier standalone tools are kept in `legacy/`, each with its own documentation:

- [Randomization of Ultrasound Images](legacy/randomize/README.md)
- [Extraction of Raw Segmentation](legacy/compareimages/README.md#Extraction-of-Raw-Segmentation)
- [Evaluation Metrics for Segmentation](legacy/compareimages/README.md#Evaluation-Metrics)

---

## Troubleshooting

- **"Run ./setup-web.sh first."** The `.venv/` folder or the Flutter build output (`app/build/web`) is missing. Run the setup script.
- **"Flutter SDK is required."** Install Flutter and make sure `flutter` is on your `PATH`.
- **Start fails or the page doesn't load.** Check the log with `./pyrestus-web.sh logs`, and confirm that nothing else is using port 8080.

---

## License

Released under the [MIT License](LICENSE).
