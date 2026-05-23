# OCR Invoice Parser

Live Demo: https://YOUR-APP.streamlit.app

A local-first invoice parsing tool that extracts structured line-item data from scanned and borderless PDF invoices using OCR and exports clean CSV files.

---

## Features

- OCR support for scanned/image-based PDFs
- Borderless invoice parsing
- CSV export
- Streamlit UI
- Local processing (no external APIs)

---

## Demo

![App Preview](screenshots/app_preview.png)

---

## Tech Stack

- Python
- Streamlit
- Tesseract OCR
- pdfplumber
- pdf2image
- pandas

---

## Run Locally

Install system dependencies:

```bash
brew install tesseract poppler
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
streamlit run app.py
```

---

## Sample Output

| Description | Price | QTY | Total |
|---|---|---|---|
| Service 1 | 10.00 | 1 | 10.00 |
| Service 2 | 5.43 | 2 | 10.86 |
| Service 3 | 7.88 | 5 | 39.40 |

---

## Future Improvements

- Multi-invoice template support
- Confidence scoring
- Batch PDF uploads
- Structured parser modules
- Table detection improvements
