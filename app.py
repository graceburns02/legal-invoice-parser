from __future__ import annotations

import streamlit as st

from parser import parse_invoice


st.set_page_config(page_title="Invoice Parser", layout="centered")
st.title("Legal Invoice Parser")
st.write("Upload an invoice PDF, then download parsed tables as CSV.")

uploaded_file = st.file_uploader("Upload invoice PDF", type=["pdf"])

if uploaded_file is not None:
    parsed = parse_invoice(uploaded_file.read())

    fees_csv = parsed.fees_expenses.to_csv(index=False).encode("utf-8")
    adjustments_csv = parsed.adjustments.to_csv(index=False).encode("utf-8")

    st.subheader("Preview")
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Fees & Expenses")
        st.dataframe(parsed.fees_expenses, use_container_width=True)
    with col2:
        st.caption("Adjustments")
        st.dataframe(parsed.adjustments, use_container_width=True)

    st.download_button(
        "Download Fees & Expenses CSV",
        data=fees_csv,
        file_name="fees_expenses.csv",
        mime="text/csv",
    )
    st.download_button(
        "Download Adjustments CSV",
        data=adjustments_csv,
        file_name="adjustments.csv",
        mime="text/csv",
    )
else:
    st.info("Please upload a PDF file to begin parsing.")
