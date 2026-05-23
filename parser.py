from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd
import pdfplumber


FEES_COLUMNS = ["DATE", "DESCRIPTION", "RATE", "ADJMTS", "TAX", "TOTAL"]
ADJUSTMENTS_COLUMNS = ["DESCRIPTION", "AMOUNT"]


@dataclass
class ParsedInvoice:
    fees_expenses: pd.DataFrame
    adjustments: pd.DataFrame


_AMOUNT_RE = re.compile(r"[-+]?\$?\d[\d,]*\.\d{2}$")
_DATE_RE = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})$")


def _normalize_line(line: str) -> str:
    """Normalize spacing and remove noisy quantity markers like `x 2.00`."""
    cleaned = re.sub(r"\s*x\s+\d+(?:\.\d+)?\s*$", "", line.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _extract_text_lines(pdf_bytes: bytes) -> List[str]:
    lines: List[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if not page_text:
                continue
            for raw in page_text.splitlines():
                norm = _normalize_line(raw)
                if norm:
                    lines.append(norm)
    return lines


def _find_section(lines: List[str], header_pattern: str, start_index: int = 0) -> Optional[int]:
    header_re = re.compile(header_pattern, re.IGNORECASE)
    for idx in range(start_index, len(lines)):
        if header_re.search(lines[idx]):
            return idx
    return None


def _looks_like_fees_header(line: str) -> bool:
    upper = line.upper()
    return all(token in upper for token in FEES_COLUMNS)


def _tokenize_amount_tail(text: str) -> tuple[str, str, str, str, str]:
    """
    Split a fees row into description + last four amount-like columns.
    Returns (description, rate, adjmts, tax, total).
    """
    parts = text.rsplit(" ", 4)
    if len(parts) < 5:
        # best effort fallback
        padded = ["", "", "", "", ""]
        padded[0] = text
        return tuple(padded)  # type: ignore[return-value]
    return parts[0], parts[1], parts[2], parts[3], parts[4]


def parse_fees_expenses(lines: List[str]) -> pd.DataFrame:
    start = _find_section(lines, r"FEES\s*&\s*EXPENSES")
    if start is None:
        return pd.DataFrame(columns=FEES_COLUMNS)

    header_idx = None
    for i in range(start, min(start + 20, len(lines))):
        if _looks_like_fees_header(lines[i]):
            header_idx = i
            break

    if header_idx is None:
        return pd.DataFrame(columns=FEES_COLUMNS)

    rows: list[dict[str, str]] = []
    current: Optional[dict[str, str]] = None

    for line in lines[header_idx + 1 :]:
        upper = line.upper()
        if upper.startswith("ADJUSTMENTS") or upper.startswith("TOTAL"):
            break
        if not line:
            continue

        tokens = line.split(" ")
        first = tokens[0] if tokens else ""

        is_new_row = bool(_DATE_RE.match(first))

        if is_new_row:
            if current:
                rows.append(current)

            date = first
            remainder = line[len(first) :].strip()
            desc, rate, adjmts, tax, total = _tokenize_amount_tail(remainder)
            current = {
                "DATE": date,
                "DESCRIPTION": desc.strip(),
                "RATE": rate.strip(),
                "ADJMTS": adjmts.strip(),
                "TAX": tax.strip(),
                "TOTAL": total.strip(),
            }
        else:
            # Continuation line: merge wrapped description into current row.
            if current:
                current["DESCRIPTION"] = f"{current['DESCRIPTION']} {line}".strip()

    if current:
        rows.append(current)

    # Cleanup spaces and ensure multiplier noise was removed consistently.
    for row in rows:
        for col in FEES_COLUMNS:
            row[col] = _normalize_line(str(row.get(col, "")))

    return pd.DataFrame(rows, columns=FEES_COLUMNS)


def parse_adjustments(lines: List[str]) -> pd.DataFrame:
    start = _find_section(lines, r"^ADJUSTMENTS$")
    if start is None:
        start = _find_section(lines, r"ADJUSTMENTS")
    if start is None:
        return pd.DataFrame(columns=ADJUSTMENTS_COLUMNS)

    # Move below optional table header.
    i = start + 1
    if i < len(lines) and "DESCRIPTION" in lines[i].upper() and "AMOUNT" in lines[i].upper():
        i += 1

    rows: list[dict[str, str]] = []

    while i < len(lines):
        line = lines[i]
        upper = line.upper()
        if upper.startswith("TOTAL"):
            break
        if not line:
            i += 1
            continue

        # strict description + amount parse from line tail
        m = re.match(r"^(?P<desc>.+?)\s+(?P<amount>[-+]?\$?\d[\d,]*\.\d{2})$", line)
        if m:
            rows.append(
                {
                    "DESCRIPTION": _normalize_line(m.group("desc")),
                    "AMOUNT": _normalize_line(m.group("amount")),
                }
            )
        elif rows:
            # handle wrapped descriptions until amount appears on same line later
            if not _AMOUNT_RE.search(line):
                rows[-1]["DESCRIPTION"] = _normalize_line(f"{rows[-1]['DESCRIPTION']} {line}")
        i += 1

    return pd.DataFrame(rows, columns=ADJUSTMENTS_COLUMNS)


def parse_invoice(pdf_bytes: bytes) -> ParsedInvoice:
    lines = _extract_text_lines(pdf_bytes)
    fees_df = parse_fees_expenses(lines)
    adjustments_df = parse_adjustments(lines)
    return ParsedInvoice(fees_expenses=fees_df, adjustments=adjustments_df)
