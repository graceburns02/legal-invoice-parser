from __future__ import annotations

import io
from dataclasses import dataclass
from typing import List

import pandas as pd
import pdfplumber


LINE_ITEM_COLUMNS = ["Item", "Description", "Unit Cost", "Quantity", "Line Total"]
STOP_KEYWORDS = ("Invoice Terms:", "Subtotal", "Total")


@dataclass
class ParsedInvoice:
    line_items: pd.DataFrame


def _clean_table_rows(raw_table: List[List[str | None]]) -> List[List[str]]:
    cleaned_rows: List[List[str]] = []
    for row in raw_table:
        cleaned = [(cell or "").strip() for cell in row]
        if any(cleaned):
            cleaned_rows.append(cleaned)
    return cleaned_rows


def _is_stop_row(row: List[str]) -> bool:
    row_text = " ".join(row)
    return any(keyword in row_text for keyword in STOP_KEYWORDS)


def _is_header_row(row: List[str]) -> bool:
    return [cell.strip() for cell in row[: len(LINE_ITEM_COLUMNS)]] == LINE_ITEM_COLUMNS


def parse_line_items(pdf_bytes: bytes) -> pd.DataFrame:
    rows: List[List[str]] = []
    table_settings = {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
    }

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            extracted = page.extract_table(table_settings=table_settings) or []
            cleaned_rows = _clean_table_rows(extracted)

            for row in cleaned_rows:
                if _is_stop_row(row):
                    return pd.DataFrame(rows, columns=LINE_ITEM_COLUMNS)

                if len(row) >= len(LINE_ITEM_COLUMNS):
                    if _is_header_row(row):
                        continue
                    rows.append(row[: len(LINE_ITEM_COLUMNS)])

    return pd.DataFrame(rows, columns=LINE_ITEM_COLUMNS)


def parse_invoice(pdf_bytes: bytes) -> ParsedInvoice:
    line_items_df = parse_line_items(pdf_bytes)
    return ParsedInvoice(line_items=line_items_df)
