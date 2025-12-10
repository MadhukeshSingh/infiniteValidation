# app.py
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from dateutil.parser import parse as date_parse
from difflib import SequenceMatcher

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(
    page_title="Data Validator",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------
# FUTURISTIC UI CSS (NEW BACKGROUND)
# ---------------------------------------------------
st.markdown("""
<style>
.stApp {
    background: linear-gradient(rgba(0,0,0,0.70), rgba(0,0,0,0.70)),
                url('https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=2000&q=80');
    background-size: cover;
    background-position: center;
    color: #e4f2ff;
    font-family: 'Segoe UI', Tahoma, sans-serif;
}

.card {
    background: rgba(12, 18, 28, 0.72);
    border-radius: 14px;
    padding: 22px;
    box-shadow: 0 8px 25px rgba(0,0,0,0.55);
    border: 1px solid rgba(255,255,255,0.08);
    backdrop-filter: blur(10px);
}

h1, h2, h3 {
    color: #00eaff;
    text-shadow: 0 0 12px rgba(0,255,255,0.5);
}

.small { font-size: 13px; color: #b6cde3; }
.attention { color: #ff7b7b; font-weight: 600; }
.ok { color: #7bffb5; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# HEADER SECTION
# ---------------------------------------------------
st.markdown("""
<div class='card'>
    <h1>DATA VALIDATOR</h1>
    <p class='small'>Upload Excel → Select LEFT/RIGHT blocks → Map columns → Validate values.</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------
file = st.file_uploader("Upload Excel (.xlsx / .xls)", type=["xlsx", "xls"])

if file is None:
    st.stop()

try:
    df = pd.read_excel(file, header=None)
except Exception:
    st.error("❌ Error reading Excel file.")
    st.stop()

# ---------------------------------------------------
# Helper: Make Columns Unique (Fix Duplicate Names)
# ---------------------------------------------------
def make_unique(columns):
    seen = {}
    new_cols = []
    for col in columns:
        if col not in seen:
            seen[col] = 0
            new_cols.append(col)
        else:
            seen[col] += 1
            new_cols.append(f"{col}__{seen[col]}")  # e.g. person_name__1
    return new_cols

# ---------------------------------------------------
# HEADER SELECTION
# ---------------------------------------------------
st.markdown("<div class='card'><h2>Select Header Row</h2></div>", unsafe_allow_html=True)

header_row = st.number_input("Header row (0-based)", min_value=0, max_value=len(df)-1, value=0)

raw_cols = df.iloc[header_row].astype(str).tolist()
unique_cols = make_unique(raw_cols)

df_preview = df.iloc[header_row+1:].reset_index(drop=True)
df_preview.columns = unique_cols

st.dataframe(df_preview.head(8), height=260)

# ---------------------------------------------------
# SELECT LEFT & RIGHT COLUMNS
# ---------------------------------------------------
st.markdown("<div class='card'><h2>Choose Columns for LEFT and RIGHT</h2></div>", unsafe_allow_html=True)

columns = list(df_preview.columns)

col1, col2 = st.columns(2)

with col1:
    left_cols = st.multiselect("LEFT Columns", columns)

with col2:
    right_cols = st.multiselect("RIGHT Columns", columns)

if not left_cols or not right_cols:
    st.warning("⚠ Please select at least 1 LEFT and 1 RIGHT column.")
    st.stop()

# ---------------------------------------------------
# COLUMN MAPPING
# ---------------------------------------------------
st.markdown("<div class='card'><h2>Map Columns</h2></div>", unsafe_allow_html=True)

num_pairs = st.number_input("Number of column pairs", min_value=1, max_value=200, value=10)

mapping = []
for i in range(num_pairs):
    c1, c2 = st.columns(2)
    with c1:
        l = st.selectbox(f"Left column {i+1}", left_cols, key=f"L_{i}")
    with c2:
        r = st.selectbox(f"Right column {i+1}", right_cols, key=f"R_{i}")
    mapping.append((l, r))

# ---------------------------------------------------
# Type-Aware Value Comparison
# ---------------------------------------------------
def detect_type(v):
    if pd.isna(v): return None
    try:
        float(v)
        return "number"
    except: pass

    try:
        date_parse(str(v))
        return "date"
    except: pass

    return "string"

def compare(a, b, tol=0.01, fuzzy=0.85):
    if pd.isna(a) and pd.isna(b): return True, "empty"
    if pd.isna(a): return False, "left empty"
    if pd.isna(b): return False, "right empty"

    ta, tb = detect_type(a), detect_type(b)

    # numeric
    if ta=="number" or tb=="number":
        try:
            if abs(float(a) - float(b)) <= tol:
                return True, "num ok"
            return False, "num mismatch"
        except:
            return False, "num parse fail"

    # date
    if ta=="date" or tb=="date":
        try:
            if date_parse(str(a)).date() == date_parse(str(b)).date():
                return True, "date ok"
            return False, "date mismatch"
        except:
            pass

    # string
    a, b = str(a).strip(), str(b).strip()
    if a == b:
        return True, "string match"

    ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return ratio >= fuzzy, f"string mismatch ({ratio:.2f})"

# ---------------------------------------------------
# RUN VALIDATION
# ---------------------------------------------------
st.markdown("<div class='card'><h2>Run Validation</h2></div>", unsafe_allow_html=True)

start_row = st.number_input("Start Row", min_value=0, value=0)
end_row = st.number_input("End Row", min_value=0, value=len(df_preview)-1)

num_tol = st.number_input("Numeric tolerance", value=0.01, step=0.01)
fuzzy_tol = st.slider("Fuzzy threshold", 0.3, 1.0, 0.85)

run = st.button("Validate Now")

if run:
    mismatches = []

    for row in range(start_row, end_row + 1):
        for (lc, rc) in mapping:
            left_val = df_preview.iloc[row][lc]
            right_val = df_preview.iloc[row][rc]

            ok, reason = compare(left_val, right_val, num_tol, fuzzy_tol)

            if not ok:
                mismatches.append({
                    "row": row,
                    "left_column": lc,
                    "right_column": rc,
                    "left_value": left_val,
                    "right_value": right_val,
                    "reason": reason
                })

    total_checks = (end_row - start_row + 1) * len(mapping)

    st.markdown(f"""
    <div class='card'>
        <h3>Validation Summary</h3>
        <p>Total checks: {total_checks}<br>
        Mismatches: <span class='attention'>{len(mismatches)}</span></p>
    </div>
    """, unsafe_allow_html=True)

    if len(mismatches) > 0:
        mismatch_df = pd.DataFrame(mismatches)
        st.dataframe(mismatch_df, height=350)

        st.download_button(
            "Download mismatch CSV",
            mismatch_df.to_csv(index=False).encode(),
            "mismatches.csv",
            "text/csv"
        )
    else:
        st.success("🎉 All values match perfectly!")

