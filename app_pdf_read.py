import streamlit as st
import pdfplumber
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="AI Report Extractor", layout="wide")

# -----------------------------
# PDF TEXT EXTRACTION
# -----------------------------

def extract_text_from_bytes(file_bytes: bytes) -> str:
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        pages_text = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages_text)
# -----------------------------
# PDF TABLE EXTRACTION
# -----------------------------
def extract_tables_from_bytes(file_bytes: bytes):
    tables = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            extracted = page.extract_tables()
            for table in extracted:
                # Basic cleanup to guard against ragged rows
                header = table[0]
                rows = table[1:]
                # Normalize row lengths to header length
                normalized = []
                for r in rows:
                    if len(r) < len(header):
                        r = r + [None] * (len(header) - len(r))
                    elif len(r) > len(header):
                        r = r[:len(header)]
                    normalized.append(r)
                try:
                    df = pd.DataFrame(normalized, columns=header)
                    tables.append(df)
                except Exception:
                    # Fallback if header is messy
                    df = pd.DataFrame(rows)
                    tables.append(df)
    return tables

# -----------------------------
# FINANCIAL METRICS EXTRACTOR
# -----------------------------
# NOTE: You can expand synonyms below as you see different reports.
PATTERNS = {
    "Revenue": r"(net sales|revenue|total income)\b[^\\d]{0,40}([\\d,.]+(?:\\s?(?:bn|billion|mn|million|cr|crore|lakhs?)?)?)",
    "Operating Income": r"(operating income|operating profit|EBIT)\b[^\\d]{0,40}([\\d,.]+(?:\\s?(?:bn|billion|mn|million|cr|crore|lakhs?)?)?)",
    "EBITDA": r"\\bEBITDA\\b[^\\d]{0,40}([\\d,.]+(?:\\s?(?:bn|billion|mn|million|cr|crore|lakhs?)?)?)",
    "Net Income": r"(net income|net profit|profit for the year|PAT)\\b[^\\d]{0,40}([\\d,.]+(?:\\s?(?:bn|billion|mn|million|cr|crore|lakhs?)?)?)",
    "EPS": r"(EPS|earnings per share)\\b[^\\d]{0,20}([\\d,.]+)",
    "Cash Flow from Ops": r"(cash flow from operations|CFO)\\b[^\\d]{0,40}([\\d,.]+(?:\\s?(?:bn|billion|mn|million|cr|crore|lakhs?)?)?)",
    "Total Assets": r"(total assets)\\b[^\\d]{0,40}([\\d,.]+(?:\\s?(?:bn|billion|mn|million|cr|crore|lakhs?)?)?)",
    "Total Liabilities": r"(total liabilities)\\b[^\\d]{0,40}([\\d,.]+(?:\\s?(?:bn|billion|mn|million|cr|crore|lakhs?)?)?)",
    "Dividend": r"(dividend(?: per share)?)\\b[^\\d]{0,40}([\\d,.]+)",
    "Operating Margin %": r"(operating margin)\\b[^\\d%]{0,20}([\\d,.]+)\\s?%",
    "ROCE %": r"(ROCE|return on capital employed)\\b[^\\d%]{0,20}([\\d,.]+)\\s?%"
}

def normalize_number(s: str) -> str:
    """Normalize common suffixes to consistent plain numbers where possible."""
    if s is None:
        return s
    t = s.strip().lower().replace(",", "")
    mult = 1
    if "billion" in t or t.endswith("bn"):
        mult = 1_000_000_000
        t = t.replace("billion", "").replace("bn", "").strip()
    elif "million" in t or t.endswith("mn"):
        mult = 1_000_000
        t = t.replace("million", "").replace("mn", "").strip()
    elif "crore" in t or t.endswith("cr"):
        mult = 10_000_000
        t = t.replace("crore", "").replace("cr", "").strip()
    elif "lakh" in t or "lakhs" in t:
        mult = 100_000
        t = t.replace("lakhs", "").replace("lakh", "").strip()
    try:
        val = float(t) * mult
        # Return both raw & pretty
        return f"{val:.0f}"
    except Exception:
        return s  # fallback to original

def extract_financial_metrics(text: str):
    results = {}
    for label, pattern in PATTERNS.items():
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            value = m.group(2)
            results[label] = {
                "value_raw": value,
                "value_normalized": normalize_number(value)
            }
        else:
            results[label] = {"value_raw": None, "value_normalized": None}
    return results

def create_excel(tables, metrics):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        # Summary
        df_metrics = (
            pd.DataFrame.from_dict(metrics, orient="index")
            .reset_index()
            .rename(columns={"index": "Metric"})
        )
        df_metrics.to_excel(writer, sheet_name="Summary", index=False)

        # Tables
        for i, df in enumerate(tables, start=1):
            # Limit sheet name length
            sheet = f"Table_{i}"
            df.to_excel(writer, sheet_name=sheet, index=False)
    buf.seek(0)
    return buf

# -----------------------------
# UI
# -----------------------------
st.title("📘 AI Report Extractor")
st.caption("Upload an annual report PDF → extract figures, statements & tables → download Excel")

uploaded = st.file_uploader("Upload PDF", type=["pdf"])

col1, col2 = st.columns([1, 1])

if uploaded:
    file_bytes = uploaded.getvalue()
    with st.spinner("Reading PDF and extracting…"):
        text = extract_text_from_bytes(file_bytes)
        tables = extract_tables_from_bytes(file_bytes)
        metrics = extract_financial_metrics(text)

    with col1:
        st.subheader("📊 Financial Summary")
        st.json(metrics)

    with col2:
        st.subheader("📄 Extracted Tables")
        st.write(f"Found **{len(tables)}** tables")
        for i, df in enumerate(tables, start=1):
            st.write(f"**Table {i}**")
            st.dataframe(df, use_container_width=True)

    excel_file = create_excel(tables, metrics)
    st.download_button(
        "⬇️ Download Excel (Summary + Tables)",
        data=excel_file,
        file_name="extracted_financials.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.markdown("---")
st.caption("Note: Works best on digitally generated PDFs. Scanned PDFs may require OCR (can be added later).")
