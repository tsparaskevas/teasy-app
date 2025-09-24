
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple

import streamlit as st
import pandas as pd

# ---------- Project root & defaults ----------
def _find_project_root(marker: str = "data") -> Path:
    here = Path(__file__).resolve()
    for p in [here] + list(here.parents):
        if (p / marker).exists():
            return p
    return here.parent.parent

PROJECT_ROOT = _find_project_root()
DEFAULT_OUTPUTS = PROJECT_ROOT / "data" / "outputs"

# ---------- Filename parsing ----------
# def _parse_row(fp: Path) -> Optional[dict]:
#     if fp.suffix.lower() != ".csv":
#         return None
#     parts = fp.stem.split("_")
#     if len(parts) < 2:
#         return None
#     site = parts[0]
#     category = parts[1]
#     slug = parts[2] if len(parts) >= 3 else None
#     return {"path": str(fp), "site": site, "category": category, "slug": slug}

def _parse_row(fp: Path) -> Optional[dict]:
    if fp.suffix.lower() != ".csv":
        return None
    parts = fp.stem.split("_")
    if len(parts) < 2:
        return None
    site = parts[0]
    category = parts[1].lower()             # normalize: 'search' / 'all' / 'opinion'
    slug = "_".join(parts[2:]) if len(parts) > 2 else None  # keep full slug even if it has underscores
    return {"path": str(fp), "site": site, "category": category, "slug": slug}

@st.cache_data(show_spinner=False)
def list_outputs_df(dir_path: str) -> pd.DataFrame:
    p = Path(dir_path)
    if not p.exists():
        return pd.DataFrame(columns=["path","site","category","slug"])
    rows = []
    for f in sorted(p.glob("*.csv")):
        row = _parse_row(f)
        if row:
            rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["path","site","category","slug"])
    return pd.DataFrame(rows)

@st.cache_data(show_spinner=False)
def load_csv_trimmed(fp: str) -> pd.DataFrame:
    df = pd.read_csv(fp)
    if "date" not in df.columns:
        if "published_at" in df.columns:
            df["date"] = df["published_at"].astype(str)
        else:
            df["date"] = ""
    df["date_str"] = df["date"].astype(str).str.strip().str[:10]
    return df[["date_str"]]

@st.cache_data(show_spinner=False)
def load_many_minimal(pairs: Tuple[Tuple[str, str], ...]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for path, site in pairs:
        try:
            d = load_csv_trimmed(path)
            if d is None or d.empty:
                continue
            d = d.copy()
            d["site"] = site
            frames.append(d[["site","date_str"]])
        except Exception:
            continue
    if not frames:
        return pd.DataFrame(columns=["site","date_str"])
    out = pd.concat(frames, ignore_index=True)
    out = out[out["date_str"].notna() & (out["date_str"] != "")]
    return out

# ---------- UI ----------
st.set_page_config(page_title="6 · Visualize", page_icon="📈", layout="wide")
st.title("6 · Visualize Data — Category overview & timeline")

# Folder picker
out_dir = st.text_input("Outputs folder", str(DEFAULT_OUTPUTS))

meta = list_outputs_df(out_dir)
if meta.empty:
    st.info("No output CSVs found. Point to your `data/outputs` directory.")
    st.stop()

# Step 1: Category
categories = sorted(meta["category"].dropna().unique().tolist())
cat = st.selectbox("Select category", options=["(select)"] + categories, index=0)

# Step 2: Slug (search term) if category == search
slug = None
if cat == "search":
    slugs = sorted(meta.loc[meta["category"]=="search", "slug"].dropna().unique().tolist())
    slug = st.selectbox("Select search term (from filename)", options=["(select)"] + slugs, index=0)
    if slug == "(select)":
        slug = None

# Guard
if not cat or cat == "(select)":
    st.info("Pick a category to continue.")
    st.stop()
if cat == "search" and not slug:
    st.info("Pick a search term to continue.")
    st.stop()

# Filter files by selection
filtered = meta[meta["category"] == cat].copy()
if cat == "search":
    filtered = filtered[filtered["slug"] == slug]

if filtered.empty:
    st.error("No files match your selection.")
    st.stop()

# Load minimal date data for only the matched files
pairs = tuple((row["path"], row["site"]) for _, row in filtered.iterrows())
data = load_many_minimal(pairs)
if data.empty:
    st.warning("No rows with dates in the matching files.")
    st.stop()

# Step 3: Date range (based on available dates)
dates = pd.to_datetime(data["date_str"], errors="coerce")
dates = dates.dropna()
if dates.empty:
    st.warning("No valid dates parsed.")
    st.stop()
min_d, max_d = dates.min().date(), dates.max().date()
date_range = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)

# Step 4: Sites (with Select-all)
all_sites = sorted(data["site"].unique().tolist())
col_sites1, col_sites2 = st.columns([1,3])
with col_sites1:
    select_all = st.checkbox("Select all sites", value=True)
with col_sites2:
    if select_all:
        sel_sites = all_sites
        st.multiselect("Sites", options=all_sites, default=all_sites, disabled=True, key="sites_ms")
    else:
        sel_sites = st.multiselect("Sites", options=all_sites, default=all_sites, key="sites_ms")

# Apply filters
start, end = date_range if isinstance(date_range, (list, tuple)) else (date_range, date_range)
mask = pd.Series(True, index=data.index)
mask &= data["site"].isin(sel_sites)
dser = pd.to_datetime(data["date_str"], errors="coerce")
mask &= (dser >= pd.Timestamp(start)) & (dser <= pd.Timestamp(end))
df_f = data[mask].copy()

st.divider()

# Chart 1: Bar chart articles per site
st.subheader("Articles per site")
bar = df_f.groupby("site").size().reset_index(name="articles").sort_values("articles", ascending=False)
if bar.empty:
    st.info("No rows for the selected filters.")
else:
    try:
        import altair as alt
        chart = alt.Chart(bar).mark_bar().encode(
            x=alt.X("site:N", sort="-y", title="Site"),
            y=alt.Y("articles:Q", title="Articles"),
            tooltip=["site:N","articles:Q"]
        ).properties(height=320)
        st.altair_chart(chart, width='stretch')
    except Exception:
        st.bar_chart(bar.set_index("site")["articles"])

# Chart 2: Timeline aggregated across selected sites
st.subheader("Articles per day (aggregated across selected sites)")
ts = (
    df_f.groupby("date_str").size()
        .reset_index(name="articles")
        .sort_values("date_str")
)
if ts.empty:
    st.info("No rows to plot for the current selection.")
else:
    try:
        import altair as alt
        chart = alt.Chart(ts).mark_line(point=True).encode(
            x=alt.X("date_str:O", title="Date (YYYY-MM-DD)"),
            y=alt.Y("articles:Q", title="Articles"),
            tooltip=["date_str:N","articles:Q"]
        ).properties(height=320)
        st.altair_chart(chart, width='stretch')
    except Exception:
        st.line_chart(ts.set_index("date_str")["articles"])

# Table & downloads
with st.expander("Show aggregated daily counts", expanded=False):
    st.dataframe(ts, width='stretch', height=260)
    st.download_button(
        "Download daily counts CSV",
        data=ts.to_csv(index=False).encode("utf-8"),
        file_name=f"daily_counts_{cat}" + (f"_{slug}" if slug else "") + ".csv",
        mime="text/csv"
    )

with st.sidebar:
    if st.button("↻ Clear cache & reload files"):
        st.cache_data.clear()
        st.success("Cache cleared. Rerun the page.")
