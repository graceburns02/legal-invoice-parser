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


import re


def parse_column_ocr_text(raw_text: str) -> pd.DataFrame:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    descriptions: list[str] = []
    prices: list[str] = []
    qtys: list[str] = []
    totals: list[str] = []

    try:
        desc_start = lines.index("Description") + 1
        for line in lines[desc_start:]:
            lower = line.lower()
            if lower.startswith("payment terms") or lower.startswith("notes"):
                break
            if lower.startswith("service"):
                descriptions.append(line)
    except ValueError:
        pass

    price_qty_pattern = re.compile(r"^(\d+\.\d{2})\s+(\d+)$")
    for line in lines:
        match = price_qty_pattern.match(line)
        if match:
            prices.append(match.group(1))
            qtys.append(match.group(2))

    money_pattern = re.compile(r"^\d+\.\d{2}$")
    total_indices = [i for i, line in enumerate(lines) if line.lower() == "total"]

    if total_indices:
        total_start = total_indices[-1] + 1
        for line in lines[total_start:]:
            if money_pattern.match(line):
                totals.append(line)

    row_count = min(len(descriptions), len(prices), len(qtys), len(totals))

    rows = []
    for i in range(row_count):
        rows.append(
            {
                "Description": descriptions[i],
                "Price": prices[i],
                "QTY": qtys[i],
                "Total": totals[i],
            }
        )

    return pd.DataFrame(rows, columns=["Description", "Price", "QTY", "Total"])


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

    raw_text = "\n".join(extracted_lines)
    if extraction_method == "ocr":
        df = parse_column_ocr_text(raw_text)
    else:
        df = parse_column_ocr_text(raw_text)

    debug_rows = [
        f"{row.Description} | {row.Price} | {row.QTY} | {row.Total}"
        for row in df.itertuples(index=False)
    ]

    debug_info = {
        "method": extraction_method,
        "raw_text": raw_text,
        "parsed_rows": "\n".join(debug_rows),
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
        st.caption("Parsed rows")
        st.code(str(debug_info["parsed_rows"]), language="text")

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
