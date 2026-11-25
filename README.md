# P&ID Analyzer

Streamlit prototype for viewing P&ID documents, reviewing I/O data, and exporting validated results to Excel.

## Project layout

- `app.py` — Streamlit application entry point.
- `pdf_viewer.py` — PDF preview component.
- `detection_bulles.py` and `ocr_validation.py` — experimental detection/OCR scripts.
- `export_excel.py` — Excel export utility.
- `data/` — demo data and JSON integration notes.
- `.streamlit/` — Streamlit configuration.
- `archive/` — historical application backups when they are moved out of the root.

## Start the app on Windows

From this folder, create the virtual environment once:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then launch the application:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local address shown by Streamlit, usually `http://localhost:8501`.
Stop the server with `Ctrl+C`.

## Working safely

1. Keep `app.py` as the stable entry point.
2. Put reusable sample data in `data/`.
3. Keep experiments in separate scripts until they are integrated into the app.
4. Do not commit `.venv/`, caches, generated exports, or industrial PDFs.
5. Check the app after changes with `git status` and run it locally before committing.

## Current limitations

- The default table uses fictitious demo data.
- OCR and automatic extraction are experimental and are not yet part of the main app flow.
- Edited data is kept in the Streamlit session and is not persisted automatically.
