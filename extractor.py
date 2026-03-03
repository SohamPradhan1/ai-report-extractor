
# extractor.py
# Offline OCR extractor using: pdf2image + Tesseract OCR
# Heuristics:
#  - scan first N pages (default 5)
#  - find lines with "employees" synonyms
#  - parse numbers (Indian & Western formats + K/M/B suffixes)
#  - ignore small numbers (<1000)
#  - return largest plausible count

import os
import re
import gc
from typing import List, Optional, Tuple

import pytesseract
from pdf2image import convert_from_path
from PIL import Image

EMPLOYEE_KEYWORDS = [
    "employees",
    "employee strength",
    "workforce",
    "headcount",
    "staff",
    "team size",
]

# 260K / 2.3M / 1.1B etc.
NUMBER_WITH_SUFFIX = r"([0-9]+(?:\.[0-9]+)?)\s*([KMBkmb])"
# Indian (3,23,578), Western (323,578), or plain (323578)
NUMBER_STANDARD = r"([0-9]{1,3}(?:[,][0-9]{2,3})*(?:[,][0-9]{3})*|[0-9]{3,7})"

BLACKLIST_PATTERNS = [
    r"\bover\s+\d+\s+employees\b",
    r"\bmore than\s+\d+\s+employees\b",
    r"\bfewer than\s+\d+\s+employees\b",
    r"\bat least\s+\d+\s+employees\b",
]

MIN_SOLID = int(os.getenv("MIN_EMP_COUNT", "1000"))  # ignore tiny numbers


def clean_number(num_str: str, suffix: Optional[str] = None) -> Optional[int]:
    if not num_str:
        return None
    if suffix:
        try:
            base = float(num_str)
            s = suffix.upper()
            if s == "K":
                return int(base * 1_000)
            if s == "M":
                return int(base * 1_000_000)
            if s == "B":
                return int(base * 1_000_000_000)
        except:
            return None
    try:
        return int(num_str.replace(",", ""))
    except:
        try:
            return int(num_str.replace(",", "").replace(".", ""))
        except:
            return None


def is_blacklisted(line: str) -> bool:
    low = line.lower()
    return any(re.search(p, low) for p in BLACKLIST_PATTERNS)


def ocr_first_pages(pdf_path: str, max_pages: int = 5, dpi: int = 200) -> str:
    """
    Convert first N PDF pages to images and OCR them with Tesseract.
    Returns combined text.
    """
    text_chunks: List[str] = []
    # Render only the first N pages (fast & memory-safe)
    pages = convert_from_path(
        pdf_path,
        dpi=dpi,
        first_page=1,
        last_page=max_pages,
        # Poppler is installed inside the container; no extra args needed
    )
    for img in pages:
        # Small pre-processing: grayscale to help OCR
        try:
            g = img.convert("L")
        except Exception:
            g = img
        txt = pytesseract.image_to_string(g) or ""
        if txt:
            text_chunks.append(txt)
    gc.collect()
    return "\n".join(text_chunks)


def find_employee_count_in_text(text: str) -> Tuple[Optional[int], List[str]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    matches: List[str] = []
    best_num: Optional[int] = None

    def consider(n: Optional[int], ctx: str):
        nonlocal best_num
        if n is not None and n >= MIN_SOLID:
            matches.append(ctx)
            best_num = max(best_num or 0, n)

    # Case A: keyword & number in same line
    for ln in lines:
        low = ln.lower()
        if any(kw in low for kw in EMPLOYEE_KEYWORDS):
            if is_blacklisted(ln):
                continue

            m2 = re.search(NUMBER_WITH_SUFFIX, ln)
            if m2:
                consider(clean_number(m2.group(1), m2.group(2)), ln)

            m1 = re.findall(NUMBER_STANDARD, ln)
            for token in m1:
                consider(clean_number(token), ln)

    # Case B: number above keyword (two-line pattern)
    for i in range(len(lines) - 1):
        cur = lines[i]
        nxt = lines[i + 1].lower()
        if any(kw in nxt for kw in EMPLOYEE_KEYWORDS):
            if is_blacklisted(cur):
                continue
            m2 = re.search(NUMBER_WITH_SUFFIX, cur)
            if m2:
                consider(clean_number(m2.group(1), m2.group(2)), f"{cur} / {lines[i+1]}")
            m1 = re.findall(NUMBER_STANDARD, cur)
            for token in m1:
                consider(clean_number(token), f"{cur} / {lines[i+1]}")

    return best_num, matches


def extract_employee_count_from_pdf(pdf_path: str, max_pages: int = 5) -> dict:
    """
    Public entry point used by app.py
    """
    text = ocr_first_pages(pdf_path, max_pages=max_pages, dpi=200)
    count, matches = find_employee_count_in_text(text)
    return {
        "employee_count": count,
        "matches": matches[:30],  # keep response compact
        "source": "offline_ocr"
    }
