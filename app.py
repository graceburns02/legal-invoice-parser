from __future__ import annotations

import io
from collections import defaultdict

import pandas as pd
import pdfplumber
import streamlit as st


st.set_page_config(page_title="Invoice Parser", layout="centered")

st.title("Legal Invoice Parser")
st.write("Upload an invoice PDF, preview line items, and download them as CSV.")


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


def local_parse_invoice(pdf_bytes: bytes) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    stop_markers = ("subtotal", "tax", "total due", "payment terms")
    page_debug: list[dict[str, object]] = []
    line_items: list[dict[str, str]] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            page_words = page.extract_words(x_tolerance=2, y_tolerance=3) or []

            page_debug.append(
                {
                    "page_number": page_number,
                    "text": page_text,
                    "words_preview": page_words[:50],
                    "no_embedded_text": not page_text.strip() and not page_words,
                }
            )

            page_rows: list[str] = []
            if page_words:
                rows_by_top: dict[float, list[dict]] = defaultdict(list)
                for word in page_words:
                    top_key = round(float(word["top"]), 1)
                    rows_by_top[top_key].append(word)

                for _, row_words in sorted(rows_by_top.items(), key=lambda item: item[0]):
                    sorted_words = sorted(row_words, key=lambda w: float(w["x0"]))
                    row_text = " ".join(
                        w["text"].strip() for w in sorted_words if w.get("text", "").strip()
                    )
                    if row_text:
                        page_rows.append(row_text)

            if not page_rows and page_text.strip():
                page_rows = [line.strip() for line in page_text.split("\n") if line.strip()]

            header_index: int | None = None
            for i, row in enumerate(page_rows):
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
                continue

            for row in page_rows[header_index + 1 :]:
                row_lower = row.lower()
                if any(marker in row_lower for marker in stop_markers):
                    break

                parsed = _parse_row_from_right(row)
                if parsed:
                    line_items.append(parsed)

    return pd.DataFrame(line_items, columns=["Description", "Price", "QTY", "Total"]), page_debug


show_debug = st.checkbox("Show extracted text debug")
uploaded_file = st.file_uploader("Upload invoice PDF", type=["pdf"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    df_line_items, debug_pages = local_parse_invoice(file_bytes)
    line_items_csv = df_line_items.to_csv(index=False).encode("utf-8")

    if show_debug:
        st.subheader("Extraction Debug")
        for page_info in debug_pages:
            st.markdown(f"**Page {page_info['page_number']}**")

            if page_info["no_embedded_text"]:
                st.warning(
                    "No embedded PDF text found. This PDF may be scanned/image-based and needs OCR."
                )

            st.caption("page.extract_text()")
            st.code(page_info["text"] or "", language="text")

            st.caption("First 50 results from page.extract_words()")
            st.json(page_info["words_preview"])

            raw_lines: list[str] = []
            text_value = str(page_info["text"] or "")
            if text_value.strip():
                raw_lines = [line for line in text_value.split("\n") if line.strip()]

            if raw_lines:
                st.caption("Raw extracted lines before filtering")
                st.code("\n".join(raw_lines), language="text")

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
