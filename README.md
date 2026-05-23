# legal-invoice-parser
# OCR Invoice Parser

A local-first invoice parsing tool built with Streamlit, pdfplumber, and Tesseract OCR.

The app:
- extracts invoice line items from PDFs
- supports scanned/image-based invoices
- parses borderless invoice layouts
- exports structured CSV files
- runs fully locally with no API dependencies

## Features

- OCR fallback for scanned PDFs
- CSV export
- Streamlit UI
- Local processing only
- Modular parsing pipeline

## Tech Stack

- Python
- Streamlit
- pdfplumber
- pytesseract
- pdf2image
- pandas

## Run Locally

Install dependencies:

```bash
brew install tesseract poppler
pip install -r requirements.txt
