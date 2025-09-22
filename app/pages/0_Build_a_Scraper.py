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
import yaml
from pathlib import Path
from bs4 import BeautifulSoup

from teasy_core.extractor import extract_items, selector_diagnostics
from teasy_core.models import Selector, FieldMap
from teasy_core.consent import KNOWN_CONSENT_XPATHS
from teasy_core.fetcher import HybridFetcher, RequestsFetcher
from teasy_core.postprocess import normalize_rows, REQUIRED_COLS
from urllib.parse import urlparse
import re

SCRAPER_DIR = Path(__file__).resolve().parents[2] / "data" / "scrapers"
SCRAPER_DIR.mkdir(parents=True, exist_ok=True)

st.title("0 · Build a Scraper")

for k, v in {"final_url":"", "html_cache":"", "engine": ""}.items():
    st.session_state.setdefault(k, v)

site_key_raw = st.text_input("Site key (filename prefix)", "capital")
category = st.selectbox("Category", ["all","search","opinion"], index=1)

url = st.text_input("Teaser page URL (first page)", "")
main_container = st.text_input("Main container CSS (list wrapper)", "article")
item_css = st.text_input("Item CSS (each teaser)", "article")

if category != "search" and "{s}" in url:
    st.warning("Το {s} χρησιμοποιείται μόνο σε 'search' κατηγορία. Αφαίρεσέ το ή άλλαξε την κατηγορία σε 'search'.")

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

def fetch_with_fallback(u: str, container_css: str, item_css: str):
    try:
        req = RequestsFetcher()
        final_url, html = req.get(u, headers={})
        soup = BeautifulSoup(html, "lxml")
        if container_css.strip() and soup.select(container_css):
            return final_url, html, "Requests"
    except Exception:
        pass
    f = HybridFetcher(js_required=True, page_load_strategy="eager")
    final_url, html = f.get(
        u,
        headers={},
        wait_for_css=(item_css.strip() or container_css.strip() or None),
        wait_timeout=20,
        consent_click_xpaths=KNOWN_CONSENT_XPATHS,
    )
    return final_url, html, "Selenium"

col1, col2 = st.columns([2,1])
with col1:
    if st.button("Fetch page", type="primary", width='stretch'):
        if not url.strip():
            st.warning("Provide a URL")
        else:
            final_url, html, engine = fetch_with_fallback(url.strip(), main_container.strip(), item_css.strip())
            st.session_state["final_url"] = final_url
            st.session_state["html_cache"] = html
            st.session_state["engine"] = engine
with col2:
    if st.button("Clear"):
        for k in ["final_url","html_cache","engine"]:
            st.session_state[k] = ""

if st.session_state.get("final_url"):
    st.success(f"Fetched via **{st.session_state['engine']}** → {st.session_state['final_url']}")
    soup = BeautifulSoup(st.session_state["html_cache"], "lxml")
    mc = len(soup.select(main_container)) if main_container.strip() else 0
    it = len(soup.select(item_css)) if item_css.strip() else 0
    st.caption(f"Main container matches: {mc} — Item matches: {it}")

st.divider()
st.subheader("Selectors (relative to Item CSS)")
left, right = st.columns(2)
with left:
    title_css = st.text_input("Title CSS", "h2 a")
    url_css = st.text_input("URL CSS", "h2 a")
    url_attr = st.text_input("URL attr", "href")
    date_css = st.text_input("Date CSS", "time")
    date_attr = st.text_input("Date attr", "datetime")
with right:
    section_css = st.text_input("Section CSS", "")
    summary_css = st.text_input("Summary CSS", "")

if st.button("Preview extraction"):
    html_cache = st.session_state.get("html_cache") or ""
    base = st.session_state.get("final_url") or ""
    if not html_cache:
        st.warning("Fetch the page first.")
    else:
        fields = {
            "title": Selector(type="css", query=title_css),
            "url":   Selector(type="css", query=url_css, attr=url_attr),
        }
        if date_css:    fields["date"]    = Selector(type="css", query=date_css, attr=date_attr or None)
        if section_css: fields["section"] = Selector(type="css", query=section_css)
        if summary_css: fields["summary"] = Selector(type="css", query=summary_css)
        fm = FieldMap(**fields)  # type: ignore
        rows = extract_items(html_cache, fm, container_css=main_container or None, item_css=item_css or None)
        rows = normalize_rows(rows, base_url=base)
        df = pd.DataFrame(rows)
        for col in REQUIRED_COLS:
            if col not in df.columns: df[col] = None
        df = df[[c for c in REQUIRED_COLS if c in df.columns] + [c for c in df.columns if c not in REQUIRED_COLS]]
        with st.expander("Selector diagnostics"):
            from teasy_core.extractor import selector_diagnostics
            st.json(selector_diagnostics(html_cache, fm, container_css=main_container or None, item_css=item_css or None))
        st.dataframe(df, width='stretch')

st.divider()
st.subheader("Save as YAML spec")
base_url = st.text_input("Base URL (for resolving relative links)", "https://example.com")
start_url = st.text_input("Start URL (use {s} only for 'search')", "https://example.com/search?page=1&q={s}")

mode = st.radio("Pagination", ["path","param","none"], index=1, horizontal=True)
template = st.text_input("Template (path)", "", disabled=(mode!="path"))
param = st.text_input("Param (param)", "page", disabled=(mode!="param"))
# allow 0 for sites whose first page is 0
first_page = st.number_input("First page", min_value=0, max_value=999, value=1)
# per_page for offset pagination
per_page = st.number_input(
    "Per-page (offset step)",
    min_value=0, max_value=5000, value=0,
    help="Leave 0 for page-number mode. For offset-style pagination (e.g., ?start=0,31,62?), set the step (31 here).",
    disabled=(mode!="param"),
)
is_chronological = st.checkbox("Results are newest-first?", value=True)
force_js = st.checkbox("Force Selenium (JS required)", value=True)

search_term_mode = st.selectbox("Search term mode (only for 'search')", ["raw","greeklish"], index=0, disabled=(category!="search"))
st.caption("Optional map (only for 'search'): e.g. key='Τέμπη' → value='tempi'")
map_key = st.text_input("Map key", "", disabled=(category!="search"))
map_val = st.text_input("Map value", "", disabled=(category!="search"))

if st.button("Save spec"):
    key = normalize_site_key(site_key_raw, base_url=base_url)
    fields_yaml = {
        "title": {"type":"css", "query": title_css},
        "url":   {"type":"css", "query": url_css, "attr": url_attr},
    }
    if date_css:
        fields_yaml["date"] = {"type":"css", "query": date_css, "attr": (date_attr or None)}
    if section_css:
        fields_yaml["section"] = {"type":"css", "query": section_css}
    if summary_css:
        fields_yaml["summary"] = {"type":"css", "query": summary_css}

    spec_yaml = {
        "name": f"{key}_{category}",
        "base_url": base_url,
        "start_url": start_url,
        "selectors": fields_yaml,
        "pagination": {
            "mode": mode,
            "template": (template if mode=="path" else None),
            "param": (param if mode=="param" else "page"),
            "first_page": int(first_page),
            "per_page": (int(per_page) if (mode=="param" and per_page > 0) else None),  # <-- NEW
            "template_vars": {},
        },
        "max_pages": 3,
        "js_required": bool(force_js),
        "headers": {},
        "category": category,
        "is_chronological": bool(is_chronological),
        "main_container_css": (main_container or None),
        "item_css": (item_css or None),
    }

    if category == "search":
        spec_yaml["search_term_mode"] = search_term_mode
        if map_key and map_val:
            spec_yaml["search_term_map"] = {map_key: map_val}

    fname = f"{key}_{category}.yaml"
    (SCRAPER_DIR / fname).write_text(yaml.safe_dump(spec_yaml, sort_keys=False, allow_unicode=True))
    st.success(f"Saved spec → {fname}")
