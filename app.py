from __future__ import annotations

import io
import re
from collections import defaultdict

import pandas as pd
import pdfplumber
import streamlit as st


st.set_page_config(page_title="Invoice Parser", layout="centered")

st.title("Legal Invoice Parser")
st.write("Upload an invoice PDF, preview line items, and download them as CSV.")


def local_parse_invoice(pdf_bytes: bytes) -> pd.DataFrame:
    extracted_rows: list[str] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=2, y_tolerance=3) or []

            rows_by_top: dict[float, list[dict]] = defaultdict(list)
            for word in words:
                top_key = round(float(word["top"]), 1)
                rows_by_top[top_key].append(word)

            for _, row_words in sorted(rows_by_top.items(), key=lambda item: item[0]):
                sorted_words = sorted(row_words, key=lambda w: float(w["x0"]))
                row_text = " ".join(w["text"].strip() for w in sorted_words if w.get("text", "").strip())
                if row_text:
                    extracted_rows.append(row_text)

    line_item_pattern = re.compile(
        r"^(?P<description>.+?)\s+(?P<price>\$?\d[\d,]*(?:\.\d{1,2})?)\s+(?P<qty>\d+(?:\.\d+)?)\s+(?P<total>\$?\d[\d,]*(?:\.\d{1,2})?)$"
    )

    ignore_pattern = re.compile(
        r"(?i)\b(subtotal|tax|total due|balance due|payment terms|invoice number|invoice #|bill to|ship to|amount due|invoice date|due date|terms|remit|attn|account)\b"
    )

    line_items: list[dict[str, str]] = []
    for row_text in extracted_rows:
        if ignore_pattern.search(row_text):
            continue

        match = line_item_pattern.match(row_text.strip())
        if not match:
            continue

        line_items.append(
            {
                "Description": match.group("description").strip(),
                "Price": match.group("price").strip(),
                "QTY": match.group("qty").strip(),
                "Total": match.group("total").strip(),
            }
        )

    return pd.DataFrame(line_items, columns=["Description", "Price", "QTY", "Total"])


uploaded_file = st.file_uploader("Upload invoice PDF", type=["pdf"])

if uploaded_file is not None:
    df_line_items = local_parse_invoice(uploaded_file.read())
    line_items_csv = df_line_items.to_csv(index=False).encode("utf-8")

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
