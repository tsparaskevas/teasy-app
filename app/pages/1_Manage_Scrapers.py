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

st.markdown(
    "Use this page to **open, edit, validate, and save** your scraper YAML specs. "
    "Pick a spec from the list, tweak the YAML, then **Validate** to check the schema or **Save** to persist changes."
)

files = sorted(SCRAPER_DIR.glob("*.yaml"))
if not files:
    st.info("No specs yet. Create one from '0 · Build a Scraper'.")
else:
    fname = st.selectbox("Choose a spec", [f.name for f in files], help="Pick a YAML scraper spec from /data/scrapers to view/edit.")
    path = SCRAPER_DIR / fname
    yaml_text = st.text_area("YAML", value=path.read_text(encoding="utf-8"), height=520, help="Edit the YAML spec directly. Tip: Use 'Validate' before saving to catch schema issues.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Validate", help="Parse the YAML and check it against the ScraperSpec model. Shows any errors."):
            try:
                data = yaml.safe_load(yaml_text) or {}
                ScraperSpec.model_validate(data)
                st.success("Valid spec ✔")
            except Exception as e:
                st.error(f"Invalid spec: {e}")
    with col2:
        if st.button("Save", help="Write the edited YAML back to /data/scrapers/<file>.yaml."):
            path.write_text(yaml_text, encoding="utf-8")
            st.success("Saved")
