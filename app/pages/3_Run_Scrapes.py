
from __future__ import annotations
import sys
import re
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

from teasy_core.config import DEMO                   # ← demo flag (Cloud via Secrets/env)
from teasy_core.models import ScraperSpec
from teasy_core.runner import run_scraper, slug_from_term, planned_urls
from teasy_core.storage import save_or_merge_csv
from teasy_core.postprocess import REQUIRED_COLS
from teasy_core.logger import append_run_log
from urllib.parse import urlparse

SCRAPER_DIR = Path(__file__).resolve().parents[2] / "data" / "scrapers"
OUTPUT_DIR  = Path(__file__).resolve().parents[2] / "data" / "outputs"
LOGS_CSV    = Path(__file__).resolve().parents[2] / "data" / "logs" / "runs.csv"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

st.title("3 · Run Scrapes")

# Demo guard (Cloud)
DEMO_DISABLED = bool(DEMO)
if DEMO_DISABLED:
    st.info(
        "Demo mode: **live scraping is disabled** on Streamlit Cloud. "
        "You can still select specs and preview planned URLs. "
        "To run scrapes, clone the repo and run locally."
    )

target_cat = st.selectbox("Category to run", ["all","search","opinion"], index=1)

all_files = sorted(SCRAPER_DIR.glob("*.yaml"))
if not all_files:
    st.info("No specs found. Create one in '0 · Build'.")
    st.stop()

def _load(path):
    import yaml as _y
    from teasy_core.models import ScraperSpec as _S
    return _S.model_validate(_y.safe_load(path.read_text(encoding="utf-8")))

def normalize_site_key(raw: str, base_url: str | None = None) -> str:
    s = (raw or "").strip().lower()
    if not s and base_url:
        host = (urlparse(base_url).hostname or "").lower()
        s = host
    # strip scheme/paths just in case
    s = s.replace("http://", "").replace("https://", "")
    s = s.split("/")[0]
    # drop www.
    if s.startswith("www."):
        s = s[4:]
    # if it looks like a domain, take the first label (e.g., dnews.gr -> dnews, www.kathimerini.gr -> kathimerini)
    if "." in s:
        parts = [p for p in s.split(".") if p]
        if parts and parts[0] == "www":
            parts = parts[1:]
        if parts:
            s = parts[0]
    # keep only safe chars
    s = re.sub(r"[^a-z0-9_-]+", "", s)
    return s or "site"

def normalized_base_name(spec) -> str:
    """
    Turn spec.name like 'dnews.gr_search' into 'dnews_search'
    without requiring you to recreate the YAML.
    """
    base = spec.name
    m = re.match(r'^([^_]+)_(.+)$', base)
    if m:
        raw_site, cat = m.groups()
    else:
        raw_site, cat = base, spec.category
    site = normalize_site_key(raw_site, base_url=str(spec.base_url))
    return f"{site}_{cat}"

specs = []
for fp in all_files:
    try:
        sp = _load(fp)
        if sp.category == target_cat:
            specs.append((fp.name, sp))
    except Exception:
        continue

if not specs:
    st.info(f"No specs for category '{target_cat}'.")
    st.stop()

names = [n for n,_ in specs]
select_all = st.checkbox(f"Select all ({len(names)})", value=True)
chosen = st.multiselect("Choose specs", names, default=(names if select_all else []))

# Page mode selector
page_mode = st.radio(
    "Pages to scrape",
    ["Limit to N", "From–To", "All pages (until empty)"],
    horizontal=True
)

pages_to_fetch = None
page_from = None
page_to = None
fetch_all = False

if page_mode == "Limit to N":
    pages_to_fetch = st.number_input("Pages per site", min_value=1, max_value=1000, value=3)
elif page_mode == "From–To":
    cols = st.columns(2)
    with cols[0]:
        page_from = st.number_input("From page", min_value=0, value=0)
    with cols[1]:
        page_to = st.number_input("To page", min_value=0, value=2)
    if page_to < page_from:
        st.error("‘To page’ must be ≥ ‘From page’.")
        st.stop()
else:
    fetch_all = True
    st.caption("Will continue until an empty page is reached (or a site-specific stop condition).")

# Optional: auto-fetch ALL for non-chronological specs when user chose "Limit to N"
auto_all_if_not_chrono = st.checkbox(
    "Auto-fetch ALL for non-chronological specs (when using ‘Limit to N’)",
    value=True,
    help="If a spec's results are not newest-first, ignore the numeric page limit and scrape until an empty page."
)

search_term_global = ""
if target_cat == "search":
    search_term_global = st.text_input("Search term", "Τέμπη")

help_msg = "Disabled in demo mode" if DEMO_DISABLED else (None if chosen else "Choose at least one spec")
disabled_flag = DEMO_DISABLED or (len(chosen) == 0)

run_clicked = st.button(
    "Run",
    type="primary",
    disabled=disabled_flag,
    help=help_msg,
)

if run_clicked:
    for name, spec in specs:
        if name not in chosen:
            continue        
    for name, spec in specs:
        if name not in chosen:
            continue

        vars = {}
        slug_part = ""
        term_in = ""
        term_used = ""
        if spec.category == "search":
            term_in = search_term_global
            term_used, slug = slug_from_term(spec, term_in)
            vars["s"] = term_used
            slug_part = "_" + slug

        # Effective per-spec mode
        effective_fetch_all = fetch_all
        effective_page_from = page_from
        effective_page_to = page_to
        effective_pages = pages_to_fetch

        if page_mode == "Limit to N" and auto_all_if_not_chrono and not spec.is_chronological:
            effective_fetch_all = True
            effective_pages = None  # ignore numeric limit

        urls = planned_urls(
            spec,
            vars=vars,
            pages=effective_pages,
            fetch_all=effective_fetch_all,
            page_from=effective_page_from,
            page_to=effective_page_to,
        )

        # Label for logs/UI
        if effective_fetch_all:
            if effective_page_from is not None and effective_page_to is not None:
                pages_label = f"ALL(from {effective_page_from} to {effective_page_to})"
            elif effective_page_from is not None:
                pages_label = f"ALL(from {effective_page_from})"
            else:
                pages_label = "ALL"
        elif effective_page_from is not None and effective_page_to is not None:
            pages_label = f"{effective_page_from}-{effective_page_to}"
        else:
            pages_label = str(effective_pages or 1)

        st.info(
            f"Scraping **{spec.name}** — pages: {pages_label}"
            + (f" — term: '{term_in}' → '{term_used}', slug: '{slug_part[1:]}'" if spec.category=='search' else "")
        )
        with st.expander(f"Planned URLs for {spec.name}"):
            for u in urls:
                st.write(u)

        status = "ok"
        msg = ""
        rows = 0
        try:
            df = run_scraper(
                spec,
                vars=vars,
                pages=effective_pages,
                fetch_all=effective_fetch_all,
                page_from=effective_page_from,
                page_to=effective_page_to,
            )
            rows = len(df)
            for col in REQUIRED_COLS:
                if col not in df.columns: df[col] = None
            df = df[[c for c in REQUIRED_COLS if c in df.columns] + [c for c in df.columns if c not in REQUIRED_COLS]]

            base_norm = normalized_base_name(spec)
            out_name = f"{base_norm}{slug_part}.csv"
            before, added, total = save_or_merge_csv(df, OUTPUT_DIR / out_name)
            st.success(f"{base_norm} ? +{added} / total {total} rows ? saved to data/outputs/{out_name}")
            msg = f"added={added}, total={total}"
        except Exception as e:
            status = "fail"
            msg = str(e)
            st.error(f"{spec.name} failed: {e}")

        append_run_log(
            LOGS_CSV,
            spec_name=base_norm,
            category=spec.category,
            pages=pages_label,
            term_in=(term_in if spec.category=="search" else ""),
            term_used=(term_used if spec.category=="search" else ""),
            output_csv=(f"{spec.name}{slug_part}.csv"),
            rows=rows,
            status=status,
            message=msg,
        )

    st.info("Done.")

