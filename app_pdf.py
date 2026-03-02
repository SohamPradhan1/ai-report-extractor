
import streamlit as st
import pdfplumber
import pandas as pd
from io import BytesIO
import re
import json

st.set_page_config(page_title="AI Report Extractor", layout="wide")

# -----------------------------
# TEXT EXTRACTION
# -----------------------------
def extract_text_from_bytes(file_bytes: bytes) -> str:
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        pages_text = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages_text)

# -----------------------------
# TABLE EXTRACTION
# -----------------------------
def extract_tables_from_bytes(file_bytes: bytes):
    tables = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            extracted = page.extract_tables()
            for table in extracted:
                header = table[0]
                rows = table[1:]
                # fix uneven rows
                clean_rows = []
                for row in rows:
                    if len(row) < len(header):
                        row = row + [None] * (len(header) - len(row))
                    elif len(row) > len(header):
                        row = row[:len(header)]
                    clean_rows.append(row)
                try:
                    df = pd.DataFrame(clean_rows, columns=header)
                except:
                    df = pd.DataFrame(clean_rows)
                tables.append(df)
    return tables

# -----------------------------
# FINANCIAL METRIC EXTRACTION
# -----------------------------
PATTERNS = {
    "Revenue": r"(net sales|revenue|total income)\b[^0-9]{0,40}([0-9,\.]+)",
    "Operating Income": r"(operating income|operating profit|EBIT)\b[^0-9]{0,40}([0-9,\.]+)",
    "Net Income": r"(net income|net profit|profit for the year|PAT)\b[^0-9]{0,40}([0-9,\.]+)",
    "EPS": r"(EPS|earnings per share)\b[^0-9]{0,20}([0-9,\.]+)",
    "Cash Flow from Ops": r"(cash flow from operations|CFO)\b[^0-9]{0,40}([0-9,\.]+)",
    "Total Assets": r"(total assets)\b[^0-9]{0,40}([0-9,\.]+)",
    "Total Liabilities": r"(total liabilities)\b[^0-9]{0,40}([0-9,\.]+)"
}

def extract_financial_metrics(text):
    results = {}
    for label, pattern in PATTERNS.items():
        m = re.search(pattern, text, flags=re.IGNORECASE)
        results[label] = m.group(2) if m else None
    return results

# -----------------------------
# EXCEL EXPORT
# -----------------------------
def create_excel(tables, metrics):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        pd.DataFrame(metrics.items(), columns=["Metric", "Value"]).to_excel(
            writer, sheet_name="Summary", index=False
        )
        for i, df in enumerate(tables, start=1):
            df.to_excel(writer, sheet_name=f"Table_{i}", index=False)
    buf.seek(0)
    return buf

# -----------------------------
# STREAMLIT UI
# -----------------------------
st.title("📘 AI Report Extractor")
st.caption("Upload an annual report PDF → extract text, tables, and financial metrics")

uploaded = st.file_uploader("Upload a PDF file", type=["pdf"])

if uploaded:
    with st.spinner("Extracting data..."):
        file_bytes = uploaded.getvalue()
        text = extract_text_from_bytes(file_bytes)
        tables = extract_tables_from_bytes(file_bytes)
        metrics = extract_financial_metrics(text)

    st.subheader("📊 Financial Summary")
    st.json(metrics)

    st.subheader(f"📄 Extracted Tables ({len(tables)} found)")
    for i, df in enumerate(tables):
        st.write(f"### Table {i+1}")
        st.dataframe(df)

    excel_file = create_excel(tables, metrics)
    st.download_button(
        "⬇️ Download Excel",
        data=excel_file,
        file_name="extracted_financials.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
