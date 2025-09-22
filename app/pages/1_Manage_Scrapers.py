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
from pathlib import Path
import yaml
from teasy_core.models import ScraperSpec

SCRAPER_DIR = Path(__file__).resolve().parents[2] / "data" / "scrapers"
SCRAPER_DIR.mkdir(parents=True, exist_ok=True)

st.title("1 · Manage Scrapers")

files = sorted(SCRAPER_DIR.glob("*.yaml"))
if not files:
    st.info("No specs yet. Create one from '0 · Build a Scraper'.")
else:
    fname = st.selectbox("Choose a spec", [f.name for f in files])
    path = SCRAPER_DIR / fname
    yaml_text = st.text_area("YAML", value=path.read_text(encoding="utf-8"), height=520)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Validate"):
            try:
                data = yaml.safe_load(yaml_text) or {}
                ScraperSpec.model_validate(data)
                st.success("Valid spec ✔")
            except Exception as e:
                st.error(f"Invalid spec: {e}")
    with col2:
        if st.button("Save"):
            path.write_text(yaml_text, encoding="utf-8")
            st.success("Saved")
