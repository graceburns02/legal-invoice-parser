from __future__ import annotations

import io

import pandas as pd
import pdfplumber
import streamlit as st


st.set_page_config(page_title="Invoice Parser", layout="centered")

st.title("Legal Invoice Parser")
st.write("Upload an invoice PDF, preview line items, and download them as CSV.")


def local_parse_invoice(pdf_bytes: bytes) -> pd.DataFrame:
    all_rows = []

    table_settings = {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "snap_y_tolerance": 3,
        "intersection_y_tolerance": 3,
    }

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables(table_settings=table_settings)

            for table in tables:
                for row in table:
                    cleaned = [cell.strip() if cell else "" for cell in row]
                    if any(cleaned):
                        all_rows.append(cleaned)

    if not all_rows:
        return pd.DataFrame(columns=["Description", "Price", "QTY", "Total"])

    max_cols = max(len(row) for row in all_rows)
    normalized_rows = [row + [""] * (max_cols - len(row)) for row in all_rows]
    df = pd.DataFrame(normalized_rows)

    header_idx = None
    for idx, row in df.iterrows():
        row_text = " ".join(str(value).lower() for value in row)
        if "description" in row_text and "price" in row_text:
            header_idx = idx
            break

    if header_idx is not None:
        df.columns = df.iloc[header_idx]
        df = df.iloc[header_idx + 1 :].reset_index(drop=True)
    else:
        fallback_columns = ["Description", "Price", "QTY", "Total"]
        df.columns = fallback_columns + [
            f"Column {i}" for i in range(5, max_cols + 1)
        ]

    df = df.dropna(how="all")
    df = df.loc[:, df.columns.astype(str).str.strip() != ""]

    description_col = next(
        (col for col in df.columns if str(col).strip().lower() == "description"),
        df.columns[0],
    )

    df[description_col] = df[description_col].astype(str).str.strip()

    exclude_pattern = r"(?i)subtotal|tax|total due|payment terms|balance due"
    df = df[~df[description_col].str.contains(exclude_pattern, na=False)]
    df = df[df[description_col] != ""]

    return df.reset_index(drop=True)


uploaded_file = st.file_uploader("Upload invoice PDF", type=["pdf"])

if uploaded_file is not None:
    df_line_items = local_parse_invoice(uploaded_file.read())
    line_items_csv = df_line_items.to_csv(index=False).encode("utf-8")

    st.subheader("Preview")
    st.caption("Invoice Line Items")
    st.dataframe(df_line_items, use_container_width=True)

    st.download_button(
        "Download Invoice Line Items CSV",
        data=line_items_csv,
        file_name="invoice_line_items.csv",
        mime="text/csv",
    )
else:
    st.info("Please upload a PDF file to begin parsing.")
