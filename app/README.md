# Pyrestus Web

Local-first Flutter Web interface for USV frame extraction.

```bash
./setup-web.sh
./pyrestus-web.sh start
```

The app opens at `http://127.0.0.1:8080`. Input files are selected through the browser/system file picker and uploaded only to the local Python process. Results are written directly to the folder selected from the native folder dialog.

Accepted input: `.dcm`, `.dicom`, `.avi`, `.mp4`, `.mov`, `.mkv`.
