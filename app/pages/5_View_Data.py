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

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "outputs"

st.title("5 · View Data")
files = sorted(OUTPUT_DIR.glob("*.csv"))
if not files:
    st.info("No output CSVs yet.")
else:
    fname = st.selectbox("CSV", [f.name for f in files])
    df = pd.read_csv(OUTPUT_DIR / fname)
    st.dataframe(df, width='stretch')
