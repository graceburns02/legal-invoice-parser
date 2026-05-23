from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

try:
    from pdf2image import convert_from_bytes
except Exception:  # pragma: no cover - dependency can be unavailable in some envs
    convert_from_bytes = None

try:
    import pytesseract
except Exception:  # pragma: no cover - dependency can be unavailable in some envs
    pytesseract = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - dependency can be unavailable in some envs
    PdfReader = None


LINE_ITEM_COLUMNS = ["Description", "Price", "QTY", "Total"]
STOP_KEYWORDS = ("Invoice Terms:", "Subtotal", "Total")
HEADER_TOKENS = ("description", "price", "qty", "total")
MONEY_PATTERN = re.compile(r"^\$?\d[\d,]*(?:\.\d{2})?$")
QUANTITY_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")
PRICE_QTY_PATTERN = re.compile(r"^(\d+\.\d{2})\s+(\d+)$")
MONEY_VALUE_PATTERN = re.compile(r"^\d+\.\d{2}$")
METADATA_PREFIXES = (
    "invoice",
    "bill to",
    "ship to",
    "date",
    "due",
    "email",
    "phone",
    "address",
)


@dataclass
class ParsedInvoice:
    line_items: pd.DataFrame


def _normalize_space(value: str) -> str:
    return " ".join(value.split()).strip()


def _is_header_line(line: str) -> bool:
    normalized = _normalize_space(line.lower())
    return all(token in normalized for token in HEADER_TOKENS)


def _is_stop_line(line: str) -> bool:
    lowered = line.lower()
    return any(keyword.lower() in lowered for keyword in STOP_KEYWORDS)


def _is_probable_metadata(line: str) -> bool:
    lowered = line.lower().strip()
    return any(lowered.startswith(prefix) for prefix in METADATA_PREFIXES)


def _is_line_total(value: str) -> bool:
    return bool(MONEY_PATTERN.match(value))


def _is_quantity(value: str) -> bool:
    return bool(QUANTITY_PATTERN.match(value))


def _parse_line_like_row(line: str) -> Optional[List[str]]:
    tokens = line.split()
    if len(tokens) < 5:
        return None

    line_total = tokens[-1]
    quantity = tokens[-2]
    unit_cost = tokens[-3]
    item = tokens[0]
    description = " ".join(tokens[1:-3]).strip()

    if not description:
        return None

    if not (_is_line_total(line_total) and _is_quantity(quantity) and _is_line_total(unit_cost)):
        return None

    return [description, unit_cost, quantity, line_total]


def _extract_lines_from_ocr_layout(pdf_bytes: bytes) -> List[str]:
    if convert_from_bytes is None or pytesseract is None:
        return []

    pages = convert_from_bytes(pdf_bytes, dpi=300)
    lines: List[str] = []

    for page in pages:
        ocr_data: Dict[str, Sequence] = pytesseract.image_to_data(
            page, output_type=pytesseract.Output.DICT
        )

        grouped: Dict[Tuple[int, int, int], List[Tuple[int, str]]] = {}
        total = len(ocr_data.get("text", []))
        for idx in range(total):
            text = _normalize_space(str(ocr_data["text"][idx]))
            conf_raw = str(ocr_data.get("conf", ["-1"] * total)[idx])
            if not text:
                continue
            try:
                conf = float(conf_raw)
            except ValueError:
                conf = -1
            if conf < 30:
                continue

            key = (
                int(ocr_data["block_num"][idx]),
                int(ocr_data["par_num"][idx]),
                int(ocr_data["line_num"][idx]),
            )
            x_left = int(ocr_data["left"][idx])
            grouped.setdefault(key, []).append((x_left, text))

        for _, line_words in sorted(grouped.items(), key=lambda kv: kv[0]):
            sorted_words = [word for _, word in sorted(line_words, key=lambda t: t[0])]
            full_line = _normalize_space(" ".join(sorted_words))
            if full_line:
                lines.append(full_line)

    return lines


def _extract_lines_with_pypdf(pdf_bytes: bytes) -> List[str]:
    if PdfReader is None:
        return []

    reader = PdfReader(io.BytesIO(pdf_bytes))
    lines: List[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            normalized = _normalize_space(raw_line)
            if normalized:
                lines.append(normalized)
    return lines


def _collect_rows(lines: Sequence[str]) -> List[List[str]]:
    rows: List[List[str]] = []
    header_seen = False

    for line in lines:
        if not header_seen:
            if _is_header_line(line):
                header_seen = True
            continue

        if _is_stop_line(line):
            break

        if _is_probable_metadata(line):
            continue

        parsed = _parse_line_like_row(line)
        if parsed:
            rows.append(parsed)
            continue

        if rows and not _is_header_line(line):
            rows[-1][1] = _normalize_space(f"{rows[-1][1]} {line}")

    return rows


def _find_index(lines: Sequence[str], pattern: str, start: int = 0) -> int:
    regex = re.compile(pattern, flags=re.IGNORECASE)
    for idx in range(start, len(lines)):
        if regex.search(lines[idx]):
            return idx
    return -1


def _collect_columnar_rows(lines: Sequence[str]) -> List[List[str]]:
    cleaned = [_normalize_space(line) for line in lines if _normalize_space(line)]
    if not cleaned:
        return []

    description_idx = _find_index(cleaned, r"^description$")
    if description_idx < 0:
        return []

    description_stop_idx = _find_index(cleaned, r"^(payment terms:?|notes:?)", start=description_idx + 1)
    if description_stop_idx < 0:
        description_stop_idx = len(cleaned)

    descriptions = [
        line
        for line in cleaned[description_idx + 1 : description_stop_idx]
        if not _is_probable_metadata(line)
    ]

    price_qty_idx = _find_index(cleaned, r"^price\s+qty$", start=description_idx + 1)
    if price_qty_idx < 0:
        return []

    prices: List[str] = []
    quantities: List[str] = []
    idx = price_qty_idx + 1
    while idx < len(cleaned):
        matched = PRICE_QTY_PATTERN.match(cleaned[idx])
        if not matched:
            break
        prices.append(matched.group(1))
        quantities.append(matched.group(2))
        idx += 1

    total_due_idx = _find_index(cleaned, r"^total due$", start=price_qty_idx + 1)
    if total_due_idx < 0:
        return []

    total_header_idx = _find_index(cleaned, r"^total$", start=total_due_idx + 1)
    if total_header_idx < 0:
        return []

    totals: List[str] = []
    idx = total_header_idx + 1
    while idx < len(cleaned):
        if not MONEY_VALUE_PATTERN.match(cleaned[idx]):
            break
        totals.append(cleaned[idx])
        idx += 1

    row_count = min(len(descriptions), len(prices), len(quantities), len(totals))
    if row_count == 0:
        return []

    rows: List[List[str]] = []
    for i in range(row_count):
        rows.append([descriptions[i], prices[i], quantities[i], totals[i]])
    return rows


def parse_line_items(pdf_bytes: bytes) -> pd.DataFrame:
    ocr_lines = _extract_lines_from_ocr_layout(pdf_bytes)
    rows = _collect_rows(ocr_lines)
    if not rows:
        rows = _collect_columnar_rows(ocr_lines)

    if not rows:
        fallback_lines = _extract_lines_with_pypdf(pdf_bytes)
        rows = _collect_rows(fallback_lines)
        if not rows:
            rows = _collect_columnar_rows(fallback_lines)

    return pd.DataFrame(rows, columns=LINE_ITEM_COLUMNS)


def parse_invoice(pdf_bytes: bytes) -> ParsedInvoice:
    line_items_df = parse_line_items(pdf_bytes)
    return ParsedInvoice(line_items=line_items_df)
