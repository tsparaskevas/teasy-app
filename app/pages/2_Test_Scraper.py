from __future__ import annotations
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
import yaml, pandas as pd

from teasy_core.config import DEMO  # <-- demo flag (Cloud via Secrets/env)
from teasy_core.models import ScraperSpec
from teasy_core.runner import run_scraper, planned_urls, slug_from_term
from teasy_core.postprocess import REQUIRED_COLS

SCRAPER_DIR = Path(__file__).resolve().parents[2] / "data" / "scrapers"

st.title("2 · Test Scraper")

st.markdown(
    "Use this page to **try a scraper spec without saving data**. "
    "Pick a YAML, choose pages (and a search term if applicable), preview the planned URLs, then **Run test** to see the extracted rows."
)

# Demo guard (Cloud)
DEMO_DISABLED = bool(DEMO)
if DEMO_DISABLED:
    st.info(
        "Demo mode: **live scraping is disabled** on Streamlit Cloud. "
        "You can still preview planned URLs. "
        "To run tests, clone the repo and run locally."
    )

files = sorted(SCRAPER_DIR.glob("*.yaml"))
if not files:
    st.info("No specs found. Create one in '0 · Build'.")
    st.stop()

fname = st.selectbox("Choose a spec", [f.name for f in files], help="Pick a YAML scraper spec from /data/scrapers to test.")
spec = ScraperSpec.model_validate(yaml.safe_load((SCRAPER_DIR / fname).read_text(encoding="utf-8")))

# Optional search term for 'search' category
vars = {}
term_in = ""
term_used = ""
slug = ""
if spec.category == "search":
    term_in = st.text_input("Search term (s)", "Τέμπη", help="Only for 'search' category. Type your query; mapping/greeklish rules from the spec will be applied.")
    term_used, slug = slug_from_term(spec, term_in)
    vars["s"] = term_used

# Start page (allow 0)
start_from = st.number_input("Start from page", min_value=0, value=spec.pagination.first_page, help="The first page index to use during this test. Many sites start at 1, some at 0.")

# Page mode
page_mode = st.radio(
    "Pages to fetch",
    ["Limit to N", "From–To", "All pages (until empty)"],
    horizontal=True,
    help="How many pages to fetch:\n• Limit to N → fetch N pages starting at Start from.\n• From–To → exact range (inclusive).\n• All pages → continue until an empty page is found."
)

pages_to_fetch = None
page_from = None
page_to = None
fetch_all = False

if page_mode == "Limit to N":
    pages_to_fetch = st.number_input("Pages", min_value=1, max_value=1000, value=3, help="How many pages to fetch starting from the selected first page.")
elif page_mode == "From–To":
    c1, c2 = st.columns(2)
    with c1:
        page_from = st.number_input("From page", min_value=0, value=int(start_from), help="Range start (inclusive). Must be ≤ To page.")
    with c2:
        page_to = st.number_input("To page", min_value=0, value=int(max(start_from, start_from+2)), help="Range end (inclusive). Must be ≥ From page.")
    if page_to < page_from:
        st.error("‘To page’ must be ≥ ‘From page’.")
        st.stop()
else:
    fetch_all = True

# Build planned URLs preview using the same logic we’ll use to run
eff_page_from = None
eff_page_to = None
eff_pages = None
if page_mode == "Limit to N":
    eff_page_from = int(start_from)
    eff_pages = int(pages_to_fetch or 1)
elif page_mode == "From–To":
    eff_page_from = int(page_from)
    eff_page_to = int(page_to)
else:
    eff_page_from = int(start_from)
    eff_pages = None  # ignored when fetch_all=True

urls = planned_urls(
    spec,
    vars=vars,
    pages=eff_pages,
    fetch_all=fetch_all,
    page_from=eff_page_from,
    page_to=eff_page_to,
)

label = (
    "ALL"
    if fetch_all else
    (f"{eff_page_from}-{eff_page_to}" if eff_page_from is not None and eff_page_to is not None
     else f"{eff_pages or 1} starting at {eff_page_from}")
)

st.info(
    f"Will scrape **{spec.name}** (category: **{spec.category}**) — pages: **{label}**"
    + (f" — term: '{term_in}' → used: '{term_used}', slug: '{slug}'" if spec.category=='search' else "")
)
with st.expander("Planned URLs"):
    st.caption("Preview of the exact URLs that will be requested with these settings.")
    for u in urls:
        st.write(u)

if st.button("Run test", type="primary", disabled=DEMO_DISABLED,
    help="Disabled in demo mode" if DEMO_DISABLED else "Runs the scraper with the chosen settings and shows a dataframe (no files are written).",):
    # Apply the effective start page in-memory so the runner’s relative math aligns
    spec.pagination.first_page = int(start_from)

    df = run_scraper(
        spec,
        vars=vars,
        pages=eff_pages,
        fetch_all=fetch_all,
        page_from=eff_page_from if (page_mode != "Limit to N") else None,  # in limit mode we pass pages not range
        page_to=eff_page_to if (page_mode != "Limit to N") else None,
    )

    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = None
    df = df[[c for c in REQUIRED_COLS if c in df.columns] + [c for c in df.columns if c not in REQUIRED_COLS]]

    st.write(f"Collected **{len(df)}** rows.")
    st.dataframe(df, width='stretch')
