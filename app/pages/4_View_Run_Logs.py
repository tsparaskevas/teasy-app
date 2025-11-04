import sys
from pathlib import Path
def _add_project_root(marker="teasy_core"):
    here = Path(__file__).resolve()
    for p in [here] + list(here.parents):
        if (p / marker).is_dir():
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))
            return str(p)
    return None
PROJECT_ROOT = _add_project_root()

import streamlit as st
import pandas as pd
from pathlib import Path

LOGS_CSV = Path(__file__).resolve().parents[2] / "data" / "logs" / "runs.csv"

st.title("4 · View Run Logs")

st.markdown(
    "Browse and filter **scrape runs** recorded in `data/logs/runs.csv`. "
    "Use the dropdowns to filter by category, spec, or status. "
    "The table shows one row per run with date/time, pages, term, rows saved, and any message."
)

if not LOGS_CSV.exists():
    st.info("No runs logged yet.")
    st.stop()

df = pd.read_csv(LOGS_CSV)
if 'run_date' in df.columns:
    try:
        df['run_date'] = pd.to_datetime(df['run_date'], errors='coerce').dt.date
    except Exception:
        pass

cols = ['run_date','run_time','spec_name','category','pages','term_in','term_used','rows','status','output_csv','message']
df = df[[c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols]]

col1, col2, col3 = st.columns(3)
with col1:
    cats = ["(all)"] + sorted(df['category'].dropna().unique().tolist()) if 'category' in df else ["(all)"]
    cat = st.selectbox("Category", cats, help="Filter runs by scraper category (e.g., search, opinion). Choose (all) to show everything.")
with col2:
    specs = ["(all)"] + sorted(df['spec_name'].dropna().unique().tolist()) if 'spec_name' in df else ["(all)"]
    spec = st.selectbox("Spec", specs, help="Limit to a specific YAML spec name. Choose (all) to include every spec.")
with col3:
    stat = st.selectbox("Status", ["(all)","ok","fail"], help="Show only successful runs (ok) or failures/timeouts (fail).")

mask = pd.Series([True]*len(df))
if 'category' in df and cat != "(all)":
    mask &= (df['category'] == cat)
if 'spec_name' in df and spec != "(all)":
    mask &= (df['spec_name'] == spec)
if 'status' in df and stat != "(all)":
    mask &= (df['status'] == stat)

st.dataframe(df[mask].sort_values(by=['run_date','run_time'], ascending=[False, False]), width='stretch')
