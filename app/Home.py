# app/Home.py
from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import streamlit as st
import pandas as pd

# ── Page config (must be first) ───────────────────────────────────────────────
st.set_page_config(page_title="Teasy App", page_icon="📰", layout="wide")

# ── Paths ─────────────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).parent                 # .../app
PAGES_DIR = APP_DIR / "pages"                   # .../app/pages
DATA_DIR = APP_DIR.parent / "data"              # assume .../data
SPEC_DIR = DATA_DIR / "scrapers"
OUT_DIR  = DATA_DIR / "outputs"
LOGS_CSV = DATA_DIR / "logs" / "runs.csv"

# ── Helpers ───────────────────────────────────────────────────────────────────
def page_relpath(filename: str) -> Optional[str]:
    """Return a path relative to the entrypoint (app/) that st.page_link accepts."""
    p = PAGES_DIR / filename
    if p.exists():
        return f"pages/{filename}"   # <— relative to app/
    return None

def safe_count_glob(patterns: List[str]) -> int:
    n = 0
    for pat in patterns:
        for p in DATA_DIR.glob(pat):
            if p.is_file():
                n += 1
    return n

def read_runs_csv(path: Path, limit: int = 10) -> pd.DataFrame:
    try:
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)

        # Robust date/time parsing
        if "run_date" in df.columns:
            s = df["run_date"].astype(str).str.strip()
            d = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
            miss = d.isna()
            if miss.any():
                d.loc[miss] = pd.to_datetime(s[miss], errors="coerce")
            df["run_date"] = d.dt.date

        if "run_time" in df.columns:
            s = df["run_time"].astype(str).str.strip()
            t = pd.to_datetime(s, format="%H:%M:%S", errors="coerce")
            miss = t.isna()
            if miss.any():
                t.loc[miss] = pd.to_datetime(s[miss], format="%H:%M", errors="coerce")
            miss = t.isna()
            if miss.any():
                t.loc[miss] = pd.to_datetime(s[miss], errors="coerce")
            df["run_time"] = t.dt.time

        keep = [c for c in ["run_date", "run_time", "spec_name", "rows", "status", "message"] if c in df.columns]
        return df[keep].tail(limit) if keep else df.tail(limit)
    except Exception:
        return pd.DataFrame()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Teasy App")
st.caption("Minimal UI to build/edit/test scrapers for newssites teaser pages, run single/multi-site scrapes and track results.")

# ── Status row ────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Scraper specs", f"{safe_count_glob(['scrapers/*.yaml', 'scrapers/*.yml']):,}")
with c2:
    st.metric("Output CSVs", f"{safe_count_glob(['outputs/*.csv']):,}")
with c3:
    last = read_runs_csv(LOGS_CSV, 1)
    last_date = str(last["run_date"].iloc[-1]) if not last.empty and "run_date" in last.columns else "—"
    st.metric("Last run (date)", last_date)

st.divider()

# ── Quick links (relative to app/) ────────────────────────────────────────────
PAGES = [
    ("Build a Scraper", "0_Build_a_Scraper.py", "🧱",
     "Paste URL template and CSS selectors. Uses Requests→Selenium fallback and consent clicks."),
    ("Manage Scrapers", "1_Manage_Scrapers.py", "🗂️",
     "List, edit, duplicate, or remove YAML specs (categories: all/search/opinion)."),
    ("Test Scraper", "2_Test_Scraper.py", "🧪",
     "Quick-run a spec for N pages or a page range. Preview extracted rows."),
    ("Run Scrapes", "3_Run_Scrapes.py", "🏃",
     "Run single/multi-site scrapes, merge into site CSVs, dedupe, and log outcomes."),
    ("View Run Logs", "4_View_Run_Logs.py", "📄",
     "Inspect run history (site, category, rows, status, message, date)"),
    ("View Data", "5_View_Data.py", "📒",
     "Browse output CSVs with filters. Open URLs in a new tab."),
    ("Visualize Data", "6_Visualize_Data.py", "📈",
     "Bar chart per site & daily timeline by category/search term & date range."),
]

for row in (PAGES[:3], PAGES[3:6], PAGES[6:]):
    cols = st.columns(len(row))
    for col, (label, fname, icon, desc) in zip(cols, row):
        with col:
            # card container
            with st.container(border=True):
                st.markdown(f"### {icon} {label}")
                st.caption(desc)
                target = page_relpath(fname)
                if target:
                    st.page_link(page=target, label=f"Open {label}", icon="➡️")
                else:
                    st.button(f"{label} (not found)", disabled=True)

st.divider()

# ── Recent runs ───────────────────────────────────────────────────────────────
st.subheader("Recent runs")
runs = read_runs_csv(LOGS_CSV, limit=12)
if runs.empty:
    st.info("No run logs yet. After your first run, logs will appear here (data/logs/runs.csv).")
else:
    st.dataframe(runs, width='stretch', hide_index=True)

st.sidebar.markdown("[View on GitHub](https://github.com/tsparaskevas/teasy-app)")
