from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import List

import pandas as pd
import pdfplumber


LINE_ITEM_COLUMNS = ["Item", "Description", "Unit Cost", "Quantity", "Line Total"]
STOP_KEYWORDS = ("Invoice Terms:", "Subtotal", "Total")
HEADER_TOKENS = tuple(col.lower() for col in LINE_ITEM_COLUMNS)
LINE_ITEM_PATTERN = re.compile(
    r"^\s*(?P<item>\S+)\s+(?P<description>.+?)\s+"
    r"(?P<unit_cost>\$?\d[\d,]*(?:\.\d{2})?)\s+"
    r"(?P<quantity>\d+(?:\.\d+)?)\s+"
    r"(?P<line_total>\$?\d[\d,]*(?:\.\d{2})?)\s*$"
)


@dataclass
class ParsedInvoice:
    line_items: pd.DataFrame


def _is_header_line(line: str) -> bool:
    normalized = " ".join(line.lower().split())
    return all(token in normalized for token in HEADER_TOKENS)


def _is_stop_line(line: str) -> bool:
    return any(keyword.lower() in line.lower() for keyword in STOP_KEYWORDS)


def parse_line_items(pdf_bytes: bytes) -> pd.DataFrame:
    rows: List[List[str]] = []
    header_seen = False

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(layout=True) or ""
            for raw_line in page_text.splitlines():
                line = " ".join(raw_line.split()).strip()
                if not line:
                    continue

                if not header_seen:
                    if _is_header_line(line):
                        header_seen = True
                    continue

                if _is_stop_line(line):
                    return pd.DataFrame(rows, columns=LINE_ITEM_COLUMNS)

                match = LINE_ITEM_PATTERN.match(line)
                if match:
                    rows.append(
                        [
                            match.group("item"),
                            match.group("description"),
                            match.group("unit_cost"),
                            match.group("quantity"),
                            match.group("line_total"),
                        ]
                    )
                    continue

                if rows:
                    rows[-1][1] = f"{rows[-1][1]} {line}".strip()

    return pd.DataFrame(rows, columns=LINE_ITEM_COLUMNS)


def parse_invoice(pdf_bytes: bytes) -> ParsedInvoice:
    line_items_df = parse_line_items(pdf_bytes)
    return ParsedInvoice(line_items=line_items_df)
