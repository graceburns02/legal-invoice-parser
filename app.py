from __future__ import annotations

import io

import pandas as pd
import pdfplumber
import pytesseract
import streamlit as st
from pdf2image import convert_from_bytes


st.set_page_config(page_title="Invoice Parser", layout="centered")

st.title("Legal Invoice Parser")
st.write("Upload an invoice PDF, preview line items, and download them as CSV.")


STOP_MARKERS = ("subtotal", "tax", "total due", "payment terms", "notes")


def _parse_row_from_right(row_text: str) -> dict[str, str] | None:
    parts = row_text.split()
    if len(parts) < 4:
        return None

    description = " ".join(parts[:-3]).strip()
    price = parts[-3].strip()
    qty = parts[-2].strip()
    total = parts[-1].strip()

    if not description:
        return None

    return {
        "Description": description,
        "Price": price,
        "QTY": qty,
        "Total": total,
    }


def _find_and_parse_line_items(lines: list[str]) -> list[dict[str, str]]:
    header_index: int | None = None
    for i, row in enumerate(lines):
        row_lower = row.lower()
        if (
            "description" in row_lower
            and "price" in row_lower
            and "qty" in row_lower
            and "total" in row_lower
        ):
            header_index = i
            break

    if header_index is None:
        return []

    line_items: list[dict[str, str]] = []
    for row in lines[header_index + 1 :]:
        row_lower = row.lower()
        if any(marker in row_lower for marker in STOP_MARKERS):
            break

        parsed = _parse_row_from_right(row)
        if parsed:
            line_items.append(parsed)

    return line_items


def local_parse_invoice(pdf_bytes: bytes) -> tuple[pd.DataFrame, dict[str, object]]:
    extracted_lines: list[str] = []
    extraction_method = "embedded"

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                extracted_lines.extend([line.strip() for line in page_text.split("\n") if line.strip()])

            page_words = page.extract_words(x_tolerance=2, y_tolerance=3) or []
            if page_words:
                extracted_lines.extend([word["text"].strip() for word in page_words if word.get("text", "").strip()])

    has_embedded_text = any(line.strip() for line in extracted_lines)

    if not has_embedded_text:
        extraction_method = "ocr"
        extracted_lines = []
        images = convert_from_bytes(pdf_bytes)
        for image in images:
            ocr_text = pytesseract.image_to_string(image) or ""
            extracted_lines.extend([line.strip() for line in ocr_text.split("\n") if line.strip()])

    line_items = _find_and_parse_line_items(extracted_lines)
    df = pd.DataFrame(line_items, columns=["Description", "Price", "QTY", "Total"])

    debug_info = {
        "method": extraction_method,
        "raw_text": "\n".join(extracted_lines),
    }
    return df, debug_info


show_debug = st.checkbox("Show extracted text debug")
uploaded_file = st.file_uploader("Upload invoice PDF", type=["pdf"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    df_line_items, debug_info = local_parse_invoice(file_bytes)
    line_items_csv = df_line_items.to_csv(index=False).encode("utf-8")

    if show_debug:
        st.subheader("Extraction Debug")
        st.write(f"Method used: **{debug_info['method'].upper()}**")
        st.caption("Raw extracted text")
        st.code(str(debug_info["raw_text"]), language="text")

    st.subheader("Preview")
    st.caption("Invoice Line Items")

    if df_line_items.empty:
        st.warning("No line items were detected in this invoice.")

    st.dataframe(df_line_items, use_container_width=True)

    st.download_button(
        "Download Invoice Line Items CSV",
        data=line_items_csv,
        file_name="invoice_line_items.csv",
        mime="text/csv",
    )
else:
    st.info("Please upload a PDF file to begin parsing.")
