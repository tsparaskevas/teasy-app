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
from urllib.parse import urlparse
import concurrent.futures
import traceback
from queue import SimpleQueue, Empty

from teasy_core.config import DEMO                   # demo flag (Cloud via Secrets/env)
from teasy_core.models import ScraperSpec
from teasy_core.runner import run_scraper, slug_from_term, planned_urls
from teasy_core.storage import save_or_merge_csv
from teasy_core.postprocess import REQUIRED_COLS
from teasy_core.logger import append_run_log

SCRAPER_DIR = Path(__file__).resolve().parents[2] / "data" / "scrapers"
OUTPUT_DIR  = Path(__file__).resolve().parents[2] / "data" / "outputs"
LOGS_CSV    = Path(__file__).resolve().parents[2] / "data" / "logs" / "runs.csv"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

st.title("3 · Run Scrapes")

st.markdown(
    "Run one or more scraper specs and **save results to CSV**. "
    "Pick a category, choose specs, select how many pages to fetch, and hit **Run**. "
    "If a site takes too long, we mark it as timeout, show the **last URL attempted**, "
    "and (if available) merge any **partial rows** collected so far."
)

# Demo guard (Cloud)
DEMO_DISABLED = bool(DEMO)
if DEMO_DISABLED:
    st.info(
        "Demo mode: **live scraping is disabled** on Streamlit Cloud. "
        "You can still select specs and preview planned URLs. "
        "To run scrapes, clone the repo and run locally."
    )

target_cat = st.selectbox("Category to run", ["all","search","opinion"], index=1, help="Filter the list to specs of this category only.")

all_files = sorted(SCRAPER_DIR.glob("*.yaml"))
if not all_files:
    st.info("No specs found. Create one in '0 · Build'.")
    st.stop()

def _load(path: Path) -> ScraperSpec:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ScraperSpec.model_validate(data)

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
    # if it looks like a domain, take the first label (e.g., dnews.gr -> dnews)
    if "." in s:
        parts = [p for p in s.split(".") if p]
        if parts and parts[0] == "www":
            parts = parts[1:]
        if parts:
            s = parts[0]
    # keep only safe chars
    s = re.sub(r"[^a-z0-9_-]+", "", s)
    return s or "site"

def normalized_base_name(spec: ScraperSpec) -> str:
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

# collect specs by selected category
specs: list[tuple[str, ScraperSpec]] = []
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
select_all = st.checkbox(f"Select all ({len(names)})", value=True, help="Quickly select or clear all specs in the list.")
chosen = st.multiselect("Choose specs", names, default=(names if select_all else []), help="Pick the exact specs to run. Hold Ctrl/Cmd to multi-select.")

# Page mode selector
page_mode = st.radio(
    "Pages to scrape",
    ["Limit to N", "From–To", "All pages (until empty)"],
    horizontal=True,
    help="How many pages per site:\n• Limit to N → fetch N pages starting from the spec’s first page.\n• From–To → fetch an exact inclusive range.\n• All pages → keep going until an empty page (or stop condition)."
)

pages_to_fetch: int | None = None
page_from: int | None = None
page_to: int | None = None
fetch_all = False

if page_mode == "Limit to N":
    pages_to_fetch = st.number_input("Pages per site", min_value=1, max_value=1000, value=3, help="Number of pages per site (when using ‘Limit to N’).")
elif page_mode == "From–To":
    cols = st.columns(2)
    with cols[0]:
        page_from = st.number_input("From page", min_value=0, value=0, help="First page index to fetch (inclusive). Many sites start at 1, some at 0.")
    with cols[1]:
        page_to = st.number_input("To page", min_value=0, value=2, help="Last page index to fetch (inclusive). Must be ≥ From page.")
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
    help="If a spec isn’t newest-first, a fixed page limit can miss results. Enable to fetch until the first empty page instead."
)

per_site_timeout = st.number_input(
    "Per-site timeout (seconds)",
    min_value=30, max_value=3600, value=180,
    help="If a site takes longer than this, it is marked as 'timeout', scraping is stoped for this site, the URL that timed out is showed, and scraping continues with the next site (if applicable)."
)

search_term_global = ""
if target_cat == "search":
    search_term_global = st.text_input("Search term", "Τέμπη", help="Only for ‘search’ specs. The app applies mapping/greeklish rules from the YAML.")

# Run button (disabled in demo / when no selection)
help_msg = "Disabled in demo mode" if DEMO_DISABLED else (None if chosen else "Choose at least one spec")
disabled_flag = DEMO_DISABLED or (len(chosen) == 0)

run_clicked = st.button(
    "Run",
    type="primary",
    disabled=disabled_flag,
    help=help_msg or "Start scraping the selected specs with the chosen paging mode. Results are merged/deduped into data/outputs/*.csv.",
)

if run_clicked:
    for name, spec in specs:
        if name not in chosen:
            continue

        vars: dict[str, str] = {}
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

        base_norm = normalized_base_name(spec)          # define before running
        out_name = f"{base_norm}{slug_part}.csv"        # real file we will write/log

        st.info(
            f"Scraping **{spec.name}** — pages: {pages_label}"
            + (f" — term: '{term_in}' → '{term_used}', slug: '{slug_part[1:]}'" if spec.category=='search' else "")
        )
        with st.expander(f"Planned URLs for {spec.name}"):
            st.caption("Preview of the exact URLs that will be requested for this spec.")
            for u in urls:
                st.write(u)

        status = "ok"
        msg = ""
        rows = 0
        events = SimpleQueue()
        last_partial = {"file": None}
        def _on_progress(ev: dict):
            try:
                events.put_nowait(ev)
                if ev.get("event") == "partial_append" and ev.get("file"):
                    # remember where runner is appending
                    last_partial["file"] = ev["file"]
            except Exception:
                pass

        # Run with timeout so a stuck site doesn't block all others
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(
                    run_scraper,
                    spec,
                    vars=vars,
                    pages=effective_pages,
                    fetch_all=effective_fetch_all,
                    page_from=effective_page_from,
                    page_to=effective_page_to,
                    progress=_on_progress,
                )
                df = fut.result(timeout=per_site_timeout)

            rows = len(df)

            # Ensure required cols exist & order columns
            for col in REQUIRED_COLS:
                if col not in df.columns:
                    df[col] = None
            df = df[[c for c in REQUIRED_COLS if c in df.columns] + [c for c in df.columns if c not in REQUIRED_COLS]]

            # Save/merge
            before, added, total = save_or_merge_csv(df, OUTPUT_DIR / out_name)
            st.success(f"{base_norm} — +{added} / total {total} rows ✅ saved to data/outputs/{out_name}")
            msg = f"added={added}, total={total}"

        except concurrent.futures.TimeoutError:
            status = "timeout"
            msg = f"Timed out after {per_site_timeout}s"
            st.error(f"{spec.name} ⏱ {msg}")
            # If we have a partial file, merge it so rows are not lost
            try:
                if last_partial["file"]:
                    st.info("Merging rows from partial file created before timeout…")
                    dfp = pd.read_csv(last_partial["file"])
                    # Ensure required columns exist; drop dupes by URL if present
                    for col in REQUIRED_COLS:
                        if col not in dfp.columns:
                            dfp[col] = None
                    if "url" in dfp.columns:
                        dfp = dfp.drop_duplicates(subset=["url"], keep="first")
                    before, added, total = save_or_merge_csv(dfp, OUTPUT_DIR / out_name)
                    st.success(f"{base_norm} — +{added} / total {total} rows ✅ (from partial)")
            except Exception as e_part:
                st.warning(f"Could not merge partial rows: {e_part}")
            last = None
            try:
                while True:
                    last = events.get_nowait()
            except Empty:
                pass
            if last and last.get("event") == "fetch_start":
                st.warning(f"Last URL before timeout: {last.get('url')}  (page {last.get('page')})")

        except Exception as e:
            status = "fail"
            msg = f"{type(e).__name__}: {e}"
            st.error(f"{spec.name} ⏱ {msg}")
            # Drain queue to get the latest started URL
            last = None
            try:
                while True:
                    last = events.get_nowait()
            except Empty:
                pass
            if last and last.get("event") == "fetch_start":
                st.warning(f"Last URL before timeout: {last.get('url')}  (page {last.get('page')})")

            # Show the tail of the traceback for quick debugging
            tb = "".join(traceback.format_exc())
            st.code(tb[-1200:])  # last ~1200 chars

        finally:
            # Always append a log row so you can see which site stalled/failed
            try:
                append_run_log(
                    LOGS_CSV,
                    spec_name=base_norm,
                    category=spec.category,
                    pages=pages_label,
                    term_in=(term_in if spec.category=="search" else ""),
                    term_used=(term_used if spec.category=="search" else ""),
                    output_csv=out_name,     # actual filename
                    rows=rows,
                    status=status,
                    message=msg,
                )
            except Exception as e_log:
                st.warning(f"Could not write run log for {spec.name}: {e_log}")

        st.divider()

    st.info("Done.")

