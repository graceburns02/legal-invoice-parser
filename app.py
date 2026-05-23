from __future__ import annotations

import streamlit as st

from parser import parse_invoice


st.set_page_config(page_title="Invoice Parser", layout="centered")
st.title("Legal Invoice Parser")
st.write("Upload an invoice PDF, preview line items, and download them as CSV.")

uploaded_file = st.file_uploader("Upload invoice PDF", type=["pdf"])

if uploaded_file is not None:
    parsed = parse_invoice(uploaded_file.read())
    line_items_csv = parsed.line_items.to_csv(index=False).encode("utf-8")

    st.subheader("Preview")
    st.caption("Invoice Line Items")
    st.dataframe(parsed.line_items, use_container_width=True)

    st.download_button(
        "Download Invoice Line Items CSV",
        data=line_items_csv,
        file_name="invoice_line_items.csv",
        mime="text/csv",
    )
else:
    st.info("Please upload a PDF file to begin parsing.")
