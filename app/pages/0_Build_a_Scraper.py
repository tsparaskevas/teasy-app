from __future__ import annotations
import sys, os, re
from pathlib import Path
import streamlit as st 

# st.set_page_config(page_title="Build a Scraper", page_icon="🧱", layout="wide")

def _add_project_root(marker="teasy_core"):
    here = Path(__file__).resolve()
    for p in [here] + list(here.parents):
        if (p / marker).is_dir():
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))
            return str(p)
    return None

PROJECT_ROOT = _add_project_root()

# Demo flag: Streamlit Cloud can set TEASY_DEMO="1" in Secrets or env
from teasy_core.config import DEMO
DEMO_DISABLED = bool(DEMO)  # True on Cloud demo, False locally

if DEMO_DISABLED:
    st.info(
        "Demo mode: **live fetching is disabled** on Streamlit Cloud. "
        "You can still define selectors and **save the YAML spec**. "
        "To fetch pages and test scrapers, clone the repo and run locally."
    )

import pandas as pd
import yaml
import json 
from bs4 import BeautifulSoup

from teasy_core.extractor import extract_items, selector_diagnostics
from teasy_core.models import Selector, FieldMap
from teasy_core.consent import KNOWN_CONSENT_XPATHS
from teasy_core.fetcher import HybridFetcher, RequestsFetcher
from teasy_core.postprocess import normalize_rows, REQUIRED_COLS
from urllib.parse import urlparse

SCRAPER_DIR = Path(__file__).resolve().parents[2] / "data" / "scrapers"
SCRAPER_DIR.mkdir(parents=True, exist_ok=True)

def load_spec_to_ui(path: Path):
    """It reads a YAML spec and fills the st.session_state fields for editing."""
    try:
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        st.error(f"Could not load spec {path.name}: {e}")
        return

    # e.g. "imerisia_search"
    name = spec.get("name", path.stem)
    if "_" in name:
        site_key, cat = name.rsplit("_", 1)
    else:
        site_key, cat = name, spec.get("category", "all")

    # Basic fields
    st.session_state["site_key_raw"] = site_key
    st.session_state["category"] = spec.get("category", cat)

    st.session_state["base_url"] = spec.get("base_url", "")
    st.session_state["start_url"] = spec.get("start_url", "")
    # URL to Fetch: the start_url 
    raw_start = spec.get("start_url", "") or ""
    cat = spec.get("category", "search")
    stm = spec.get("search_term_map") or {}

    if cat == "search" and "{s}" in raw_start:
        # If there is key mapping in yaml, take the first key as an example
        if stm:
            example_term = next(iter(stm.keys()))
        else:
            example_term = "Τέμπη"
        url_for_fetch = raw_start.replace("{s}", example_term)
    else:
        url_for_fetch = raw_start

    st.session_state["url"] = url_for_fetch

    st.session_state["main_container"] = spec.get("main_container_css") or ""
    st.session_state["item_css"] = spec.get("item_css") or ""

    # Response type / JSON flags
    resp_type = spec.get("response_type", "html")
    st.session_state["response_type"] = resp_type
    st.session_state["is_json"] = (resp_type == "json")

    st.session_state["is_chronological"] = bool(spec.get("is_chronological", True))
    st.session_state["force_js"] = bool(spec.get("js_required", False))

    # Selectors
    selectors = spec.get("selectors", {}) or {}

    if resp_type == "html":
        title_sel = selectors.get("title", {}) or {}
        url_sel = selectors.get("url", {}) or {}
        date_sel = selectors.get("date", {}) or {}
        section_sel = selectors.get("section", {}) or {}
        summary_sel = selectors.get("summary", {}) or {}

        st.session_state["title_css"] = title_sel.get("query", "h2 a")
        st.session_state["url_css"] = url_sel.get("query", "h2 a")
        st.session_state["url_attr"] = url_sel.get("attr", "href") or ""

        st.session_state["date_css"] = date_sel.get("query", "") or ""
        st.session_state["date_attr"] = date_sel.get("attr", "") or ""

        st.session_state["section_css"] = section_sel.get("query", "") or ""
        st.session_state["summary_css"] = summary_sel.get("query", "") or ""

    else:  # JSON
        title_sel = selectors.get("title", {}) or {}
        url_sel = selectors.get("url", {}) or {}
        date_sel = selectors.get("date", {}) or {}
        section_sel = selectors.get("section", {}) or {}
        summary_sel = selectors.get("summary", {}) or {}

        st.session_state["json_list_path"] = spec.get("json_list_path") or ""
        st.session_state["json_url_template"] = spec.get("json_url_template") or ""

        st.session_state["json_title_key"] = title_sel.get("query", "") or ""
        st.session_state["json_url_key"] = url_sel.get("query", "") or ""
        st.session_state["json_date_key"] = date_sel.get("query", "") or ""
        st.session_state["json_section_key"] = section_sel.get("query", "") or ""
        st.session_state["json_summary_key"] = summary_sel.get("query", "") or ""

    # Pagination
    pag = spec.get("pagination", {}) or {}
    st.session_state["pagination_mode"] = pag.get("mode", "param")
    st.session_state["pagination_template"] = pag.get("template") or ""
    st.session_state["pagination_param"] = pag.get("param", "page") or "page"
    st.session_state["first_page"] = int(pag.get("first_page", 1) or 1)
    st.session_state["per_page"] = int(pag.get("per_page", 0) or 0)

    # Search-related
    st.session_state["search_term_mode"] = spec.get("search_term_mode", "raw") or "raw"
    stm = spec.get("search_term_map") or {}
    if stm:
        k, v = next(iter(stm.items()))
        st.session_state["map_key"] = k
        st.session_state["map_val"] = v
    else:
        st.session_state["map_key"] = ""
        st.session_state["map_val"] = ""


st.title("0 · Build a Scraper")

for k, v in {"final_url":"", "html_cache":"", "engine": "", "is_json": False, "json_cache": None, "site_key_raw": "", "category": "search", "response_type": "auto", "pagination_mode": "param", "search_term_mode": "raw", "main_container": "main_container", "item_css": "div.articles", "url": "", "title_css": "h2 a", "url_css": "h2 a", "url_attr": "href",}.items():
    st.session_state.setdefault(k, v)

# Load existing spec (optional)
spec_files = sorted(SCRAPER_DIR.glob("*.yaml"))
options = ["— Load existing spec —"] + [f.name for f in spec_files]

choice = st.selectbox(
    "Load existing spec (optional)",
    options,
    index=0,
    key="load_existing_choice",
)

if choice != "— Load existing spec —":
    spec_path = SCRAPER_DIR / choice
    if st.button("Load this spec", key="btn_load_spec"):
        load_spec_to_ui(spec_path)
        st.rerun()

site_key_raw = st.text_input(
    "Site key (filename prefix)",
    help="Used as the filename prefix for the YAML spec. Tip: leave blank to auto-derive from Base URL (e.g., 'dnews.gr' → 'dnews'). Examples: 'parapolitika', 'kathimerini'.",
    key="site_key_raw",
)
category = st.selectbox(
    "Category",
    ["all","search","opinion"],
    help="Affects naming and search behavior. 'search' enables term mapping & {s} placeholder.",
    key="category",
)

response_type = st.radio(
    "Response type",
    ["auto", "html", "json"],
    horizontal=True,
    help="auto: try to detect JSON vs HTML\nhtml: force HTML parsing with CSS selectors\njson: treat response as JSON",
    key="response_type",
)

# Keep is_json in sync with the chosen response_type
if response_type == "json":
    st.session_state["is_json"] = True
elif response_type == "html":
    st.session_state["is_json"] = False

url = st.text_input(
    "Teaser page URL (first page)",
    help="The first teaser/listing page you want to extract. Examples:\nhttps://www.parapolitika.gr/, https://www.protothema.gr/politics/?page=1, For search: https://site.gr/search?page=1&q={s}",
    key="url",
)

main_container = st.text_input(
    "Main container CSS (list wrapper)",
    help="CSS that wraps all teaser items (optional). Example: 'div.articles' or 'section#content'.",
    key="main_container",
)

item_css = st.text_input(
    "Item CSS (each teaser)",
    help="CSS for each teaser card. Examples: 'article', 'li.result', 'div.teaser'.",
    key="item_css",
)

# Enforce: if you use Item CSS in HTML mode, you must set Main container CSS
is_json = st.session_state.get("is_json", False)

if not is_json and item_css.strip() and not main_container.strip():
    st.error(
        "You have set an Item CSS but no Main container CSS. "
        "For HTML scrapers, selectors must be scoped inside a Main container."
    )

if category != "search" and "{s}" in url:
    st.warning("{s} is used for 'search' category only. Remove it or change category to 'search'.")

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
    if DEMO_DISABLED:
        raise RuntimeError("Demo mode: fetching disabled")
    try:
        req = RequestsFetcher()
        final_url, body = req.get(u, headers={})
        return final_url, body, "Requests"
    except Exception:
        pass
    f = HybridFetcher(js_required=True, page_load_strategy="eager")
    final_url, body = f.get(
        u,
        headers={},
        wait_for_css=(item_css.strip() or container_css.strip() or None),
        wait_timeout=20,
        consent_click_xpaths=KNOWN_CONSENT_XPATHS,
    )
    return final_url, body, "Selenium"

col1, col2 = st.columns([2,1])
with col1:
    if st.button(
        "Fetch page", type="primary", 
        disabled=DEMO_DISABLED,
        help="Disabled in demo mode" if DEMO_DISABLED else "Fetches the page using Requests first, then falls back to Selenium if needed.",
        width='stretch',
    ):
        if not url.strip():
            st.warning("Provide a URL")
        else:
            final_url, body, engine = fetch_with_fallback(url.strip(), main_container.strip(), item_css.strip())
            st.session_state["final_url"] = final_url
            st.session_state["html_cache"] = body
            st.session_state["engine"] = engine

            # Detect JSON vs HTML based on response_type toggle
            raw = body
            is_json = False
            st.session_state["json_cache"] = None

            if response_type in ("auto", "json"):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, (list, dict)):
                        is_json = True
                        st.session_state["json_cache"] = parsed
                except json.JSONDecodeError:
                    pass

            if response_type == "html":
                is_json = False
                st.session_state["json_cache"] = None

            st.session_state["is_json"] = is_json

with col2:
    if st.button("Clear"):
        for k in ["final_url","html_cache","engine", "is_json", "json_cache"]:
            st.session_state[k] = "" if k != "is_json" else False

if st.session_state.get("final_url"):
    is_json = st.session_state.get("is_json", False)
    raw = st.session_state["html_cache"]

    if is_json:
        st.success(f"Fetched JSON via **{st.session_state['engine']}** → {st.session_state['final_url']}")
        data = st.session_state.get("json_cache")
        if isinstance(data, list):
            st.caption(f"Top-level JSON array with {len(data)} items.")
        elif isinstance(data, dict):
            st.caption(
                "Top-level JSON object with keys: "
                + ", ".join(list(data.keys())[:10])
            )
        else:
            st.caption("JSON payload detected, but structure is not a list or dict.")

    else:
        st.success(f"Fetched HTML via **{st.session_state['engine']}** → {st.session_state['final_url']}")
        soup = BeautifulSoup(raw, "lxml")
        mc = len(soup.select(main_container)) if main_container.strip() else 0
        if main_container.strip() and item_css.strip():
            containers = soup.select(main_container)
            # count all items in each container
            it = sum(len(container.select(item_css)) for container in containers)
        else:
            it = 0
        st.caption(f"Main container matches: {mc} — Item matches: {it}")

# defaults so they exist in both modes (json, html)
json_list_path = ""
json_title_key = ""
json_url_key = ""
json_url_template = ""
json_date_key = ""
json_section_key = ""
json_summary_key = ""

st.divider()
is_json = st.session_state.get("is_json", False)

if not is_json:
    st.subheader("Selectors (relative to Item CSS)")
    left, right = st.columns(2)
    with left:
        title_css = st.text_input(
            "Title CSS",
            help="CSS (relative to each item) for the title element. Example: 'h2 a' or '.title a'.",
            key="title_css",
        )
        url_css = st.text_input(
            "URL CSS",
            help="CSS (relative to each item) that contains the article link. Usually the same as Title CSS (e.g., 'h2 a').",
            key="url_css",
        )
        url_attr = st.text_input(
            "URL attr",
            help="Attribute that holds the URL. Usually 'href'.",
            key="url_attr",
        )
        date_css = st.text_input(
            "Date CSS",
            "time",
            help="CSS (relative to each item) for the date/time element. Examples: 'time', '.meta time', 'span.date'.",
            key="date_css",
        )
        date_attr = st.text_input(
            "Date attr",
            "datetime",
            help="Attribute that holds the datetime when available. Common: 'datetime'. Leave empty to extract text.",
            key="date_attr",
        )
    with right:
        section_css = st.text_input(
            "Section CSS",
            "",
            help="CSS (relative to each item) for the section/category label (optional). Example: '.section'.",
            key="section_css",
        )
        summary_css = st.text_input(
            "Summary CSS",
            "",
            help="CSS (relative to each item) for a short summary/excerpt (optional). Example: 'p.summary'.",
            key="summary_css",
        )

else:
    st.subheader("JSON selectors")
    st.caption("Configure how to extract fields from the JSON payload.")

    left, right = st.columns(2)
    with left:
        json_list_path = st.text_input(
            "JSON list path",
            "",
            help="Dot-separated path to the list of items. Leave empty if the top-level JSON is already a list.",
            key="json_list_path",
        )
        json_title_key = st.text_input(
            "Title key",
            "title",
            help="Key in each JSON item for the title (e.g. 'title').",
            key="json_title_key",
        )
        json_url_key = st.text_input(
            "URL key",
            "url",
            help="Key in each JSON item for the article URL or ID (e.g. 'url').",
            key="json_url_key",
        )
        json_url_template = st.text_input(
            "URL template",
            "",
            help=(
                "Optional Python-style template to build the URL from JSON fields. "
                "Example for AMNA: 'https://www.amna.gr/{note2}/{kind}/{note3}'. "
                "If this is non-empty, it is used instead of URL key."
            ),
            key="json_url_template",
        )
        json_date_key = st.text_input(
            "Date key",
            "",
            help="Optional key for date/datetime (e.g. 'c_daytime').",
            key="json_date_key",
        )
    with right:
        json_section_key = st.text_input(
            "Section key",
            "",
            help="Optional key for section/category.",
            key="json_section_key",
        )
        json_summary_key = st.text_input(
            "Summary key",
            "",
            help="Optional key for summary/excerpt.",
            key="json_summary_key",
        )

if st.button("Preview extraction"):
    html_cache = st.session_state.get("html_cache") or ""
    base = st.session_state.get("final_url") or ""
    is_json = st.session_state.get("is_json", False)

    # For HTML: require Main container if Item CSS is set
    if not is_json and item_css.strip() and not main_container.strip():
        st.error(
            "Cannot preview: Item CSS is set but Main container CSS is empty. "
            "Please provide a Main container selector first."
        )
        st.stop()

    if not html_cache:
        st.warning("Fetch the page first.")
    else:
        if not is_json:
            # HTML mode: existing behavior
            fields = {
                "title": Selector(type="css", query=title_css),
                "url":   Selector(type="css", query=url_css, attr=url_attr),
            }
            if date_css:
                fields["date"] = Selector(type="css", query=date_css, attr=date_attr or None)
            if section_css:
                fields["section"] = Selector(type="css", query=section_css)
            if summary_css:
                fields["summary"] = Selector(type="css", query=summary_css)
            fm = FieldMap(**fields)  # type: ignore
            rows = extract_items(html_cache, fm, container_css=main_container or None, item_css=item_css or None)
            rows = normalize_rows(rows, base_url=base)
            df = pd.DataFrame(rows)
            for col in REQUIRED_COLS:
                if col not in df.columns:
                    df[col] = None
            df = df[[c for c in REQUIRED_COLS if c in df.columns] + [c for c in df.columns if c not in REQUIRED_COLS]]
            with st.expander("Selector diagnostics"):
                st.json(selector_diagnostics(html_cache, fm, container_css=main_container or None, item_css=item_css or None))
            st.dataframe(df, width='stretch')

        else:
            # JSON mode
            try:
                data = st.session_state.get("json_cache") or json.loads(html_cache)
            except json.JSONDecodeError:
                st.error("Response is not valid JSON.")
                st.stop()

            # Drill down to list of items if a path is provided
            items = data
            if json_list_path.strip():
                for part in json_list_path.split("."):
                    if isinstance(items, dict):
                        items = items.get(part, [])
                    else:
                        items = []
                        break

            # If still not a list, maybe top-level is already a list
            if not isinstance(items, list):
                if isinstance(data, list):
                    items = data
                else:
                    st.error("JSON list path does not point to a list of items, and top-level JSON is not a list.")
                    st.stop()

            rows = []
            for obj in items:
                if not isinstance(obj, dict):
                    continue

                # URL: if a template is given, use it; otherwise fall back to json_url_key
                url_val = None
                if json_url_template:
                    try:
                        # This will substitute {note2}, {kind}, {note3}, etc. from the JSON object
                        url_val = json_url_template.format(**obj)
                    except Exception as e:
                        # if something is missing or wrong, keep it None
                        url_val = None
                elif json_url_key:
                    url_val = obj.get(json_url_key)

                row = {
                    "title":   obj.get(json_title_key) if json_title_key else None,
                    "url":     url_val,
                    "date":    obj.get(json_date_key)  if json_date_key else None,
                    "section": obj.get(json_section_key) if json_section_key else None,
                    "summary": obj.get(json_summary_key) if json_summary_key else None,
                }
                rows.append(row)

            # Normalize rows (e.g. resolve URL against base, enforce REQUIRED_COLS)
            rows = normalize_rows(rows, base_url=base)
            df = pd.DataFrame(rows)
            for col in REQUIRED_COLS:
                if col not in df.columns:
                    df[col] = None
            df = df[[c for c in REQUIRED_COLS if c in df.columns] + [c for c in df.columns if c not in REQUIRED_COLS]]
            st.dataframe(df, width='stretch')

st.divider()
st.subheader("Save as YAML spec")

base_url = st.text_input(
    "Base URL (for resolving relative links)",
    "https://example.com",
    help="Used to resolve relative links. Example: 'https://www.parapolitika.gr'.",
    key="base_url",
)

start_url = st.text_input(
    "Start URL (use {s} only for 'search')",
    "https://example.com/search?page=1&q={s}",
    help="The URL pattern of the first listing/search page. For search, include {s}. Examples: https://site.gr/news?page=1, https://site.gr/search?page=1&q={s}",
    key="start_url",
)

mode = st.radio(
    "Pagination",
    ["path","param","none"],
    horizontal=True,
    help="Pagination style:\n• path → /page/{n}\n• param → ?page=n (or any param)\n• none → single page only",
    key="pagination_mode",
)

template = st.text_input(
    "Template (path)",
    "",
    disabled=(mode!="path"),
    help="For path mode. Example: '/page/{n}' or '/category/politics/page/{n}'.",
    key="pagination_template",
)

param = st.text_input(
    "Param (param)",
    "page",
    disabled=(mode!="param"),
    help="For param mode. Example: 'page' (so it becomes ?page=2).",
    key="pagination_param",
)

first_page = st.number_input(
    "First page",
    min_value=0, max_value=999, value=1,
    help="First page index on the site. Many sites start at 1,  some at 0.",
    key="first_page",
)

per_page = st.number_input(
    "Per-page (offset step)",
    min_value=0, max_value=5000, value=0,
    help="Leave 0 for page-number mode. For offset-style pagination (e.g., ?start=0,31,62?), set the step (31 here).",
    disabled=(mode!="param"),
    key="per_page",
)

is_chronological = st.checkbox(
    "Results are newest-first?",
    value=True,
    help="Check if results are newest first. This helps the scraper decide when to stop.",
    key="is_chronological",
)

force_js = st.checkbox(
    "Force Selenium (JS required)",
    value=True,
    help="Force Selenium (JS). Turn off to try Requests first and use Selenium only as a fallback.",
    key="force_js",
)

# Show the engine used in last fetch
engine = st.session_state.get("engine")
if engine:
    st.caption(f"Last fetch: **{engine}**")
else:
    st.caption("Last fetch: (none yet — click 'Fetch page' button)")

search_term_mode = st.selectbox(
    "Search term mode (only for 'search')",
    ["raw","greeklish"],
    help="How to transform the search term for 'search' category.\n• raw → use as typed\n• greeklish → auto-convert Greek to Latin",
    disabled=(category!="search"),
    key="search_term_mode",
)

st.caption("Optional map (only for 'search'): e.g. key='Τέμπη' → value='tempi'")

map_key = st.text_input(
    "Map key",
    "",
    help="Optional mapping for specific search terms (key). Example: 'Τέμπη'.",
    disabled=(category!="search"),
    key="map_key",
)
map_val = st.text_input(
    "Map value",
    "",
    help="Mapped value (value). Example: 'tempi'. Used only in 'search' category.",
    disabled=(category!="search"),
    key="map_val",
)

# Show if spec already exists (based on site key + category)
key_preview = normalize_site_key(site_key_raw, base_url=base_url)
fname_preview = f"{key_preview}_{category}.yaml"
if (SCRAPER_DIR / fname_preview).exists():
    st.info(f"Scraper spec **already exists**: {fname_preview} (Save will overwrite it)")
else:
    st.caption(f"Spec filename will be: {fname_preview}")

if st.button("Save spec"):
    key = normalize_site_key(site_key_raw, base_url=base_url)
    is_json = st.session_state.get("is_json", False)

    # For HTML: require Main container if Item CSS is set
    if not is_json and item_css.strip() and not main_container.strip():
        st.error(
            "Cannot save spec: Item CSS is set but Main container CSS is empty. "
            "For HTML scrapers, all items must be scoped inside a Main container."
        )
        st.stop()

    if not is_json:
        # HTML: keep existing CSS-based selector spec
        fields_yaml = {
            "title": {"type": "css", "query": title_css},
            "url":   {"type": "css", "query": url_css, "attr": url_attr},
        }
        if date_css:
            fields_yaml["date"] = {"type": "css", "query": date_css, "attr": (date_attr or None)}
        if section_css:
            fields_yaml["section"] = {"type": "css", "query": section_css}
        if summary_css:
            fields_yaml["summary"] = {"type": "css", "query": summary_css}
    else:
        # JSON: store JSON keys as selectors with type 'json_key'
        fields_yaml = {}
        if json_title_key:
            fields_yaml["title"] = {"type": "json_key", "query": json_title_key}
        if json_url_key:
            fields_yaml["url"] = {"type": "json_key", "query": json_url_key}
        if json_date_key:
            fields_yaml["date"] = {"type": "json_key", "query": json_date_key}
        if json_section_key:
            fields_yaml["section"] = {"type": "json_key", "query": json_section_key}
        if json_summary_key:
            fields_yaml["summary"] = {"type": "json_key", "query": json_summary_key}

    # Decide js_required automatically:
    # - If forced JS -> always True
    # - If last fetch used Selenium (and it is HTML), also True
    engine = st.session_state.get("engine")
    auto_js = (engine == "Selenium") and (not is_json)

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
        "js_required": bool(force_js or auto_js),
        "headers": {},
        "category": category,
        "is_chronological": bool(is_chronological),
        "main_container_css": (main_container or None),
        "item_css": (item_css or None),
    }
    # Tell the core if this is JSON or HTML
    spec_yaml["response_type"] = "json" if is_json else "html"
    # If this is a JSON-based spec and a URL template is defined, store it
    if is_json and json_url_template:
        spec_yaml["json_url_template"] = json_url_template
    # If this is a JSON-based spec and a list path is defined, store it
    if is_json and json_list_path:
        spec_yaml["json_list_path"] = json_list_path

    if category == "search":
        spec_yaml["search_term_mode"] = search_term_mode
        if map_key and map_val:
            spec_yaml["search_term_map"] = {map_key: map_val}

    fname = f"{key}_{category}.yaml"
    (SCRAPER_DIR / fname).write_text(yaml.safe_dump(spec_yaml, sort_keys=False, allow_unicode=True))
    st.success(f"Saved spec → {fname}")
