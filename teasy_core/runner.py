from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple, Callable
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus, urlparse, parse_qsl, urlencode, urlunparse
import pandas as pd
import re

from .models import ScraperSpec
from .fetcher import HybridFetcher
from .extractor import extract_items
from .postprocess import normalize_rows
from .utils import greek_to_latin, slugify

PLACEHOLDER_RE = re.compile(r"{([a-zA-Z_]\w*)}")

def placeholders(tmpl: str) -> Set[str]:
    return set(PLACEHOLDER_RE.findall(tmpl or ""))

def format_with_ctx(tmpl: str, ctx: Dict[str, str]) -> str:
    try:
        return tmpl.format(**ctx)
    except Exception:
        return tmpl
    
def _replace_query_param(url: str, param: str, value: int) -> str:
    u = urlparse(url)
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    q[param] = str(value)
    new_q = urlencode(q, doseq=True)
    return urlunparse(u._replace(query=new_q))

def _get_query_param_int(url: str, param: str) -> int | None:
    u = urlparse(url)
    for k, v in parse_qsl(u.query, keep_blank_values=True):
        if k == param:
            try:
                return int(v)
            except Exception:
                return None
    return None

def page_url(spec: ScraperSpec, page: int, vars: Dict[str, str] | None) -> str:
    pg = spec.pagination
    base = str(spec.start_url)

    # Build the context first, for any placeholders in start_url or template
    ctx = dict(pg.template_vars or {})
    ctx["page"] = page
    if vars:
        ctx.update(vars)
    enc_ctx = {k: (quote_plus(str(v)) if isinstance(v, str) else v) for k, v in ctx.items()}

    # Render start_url placeholders if present (e.g., ?q={s})
    base_f = format_with_ctx(base, enc_ctx) if placeholders(base) else base

    # PATH mode: always use the template for each page
    if pg.mode == "path" and pg.template:
        return format_with_ctx(pg.template, enc_ctx)

    # NONE mode: just return the (possibly rendered) start_url
    if pg.mode == "none":
        return base_f

    # PARAM mode:
    # If per_page is set, treat the param as an OFFSET (e.g., start=0,31,62,...).
    if pg.mode == "param":
        # If the start_url already has the parameter, use that as the base offset for first_page.
        existing = _get_query_param_int(base_f, pg.param)
        if pg.per_page:
            # Compute the offset for this "page"
            # Base offset: existing value, or per_page * first_page (common default)
            base_offset = existing if existing is not None else (pg.per_page * pg.first_page)
            offset_val = base_offset + (page - pg.first_page) * pg.per_page

            # If start_url already has the param, replace it; otherwise, append it.
            if re.search(rf"(?:[?&]){re.escape(pg.param)}=", base_f):
                return _replace_query_param(base_f, pg.param, offset_val)
            else:
                # If we're on first_page and site doesn't require start=0 explicitly, keep base_f as-is.
                if page == pg.first_page:
                    return base_f
                sep = "&" if "?" in base_f else "?"
                return f"{base_f}{sep}{pg.param}={offset_val}"
        else:
            # Simple page-number param (no offset math)
            if re.search(rf"(?:[?&]){re.escape(pg.param)}=", base_f):
                return _replace_query_param(base_f, pg.param, page)
            if page == pg.first_page:
                return base_f
            sep = "&" if "?" in base_f else "?"
            return f"{base_f}{sep}{pg.param}={page}"

    # Fallback
    return base_f

def map_search_term(spec: ScraperSpec, term: str) -> str:
    t = (term or "").strip()
    if not t:
        return ""
    if t in (spec.search_term_map or {}):
        return spec.search_term_map[t]
    mode = (spec.search_term_mode or "raw").lower()
    if mode == "greeklish":
        return greek_to_latin(t)
    return t

# def slug_from_term(spec: ScraperSpec, term_in: str) -> Tuple[str, str]:
#     used = map_search_term(spec, term_in)
#     basis = used if used else term_in
#     slug = slugify(basis)
#     return used, slug

def slug_from_term(spec: ScraperSpec, term_in: str) -> tuple[str, str]:
    used = map_search_term(spec, term_in)
    # Make the filename slug come from the user's input (transliterated),
    # not from the mapped URL value.
    basis = term_in if (term_in or "").strip() else used
    slug = slugify(basis)
    return used, slug

def planned_urls(
    spec: ScraperSpec,
    vars: Dict[str, str] | None,
    pages: Optional[int],
    fetch_all: bool,
    page_from: Optional[int] = None,
    page_to: Optional[int] = None,
) -> List[str]:
    urls: List[str] = []
    start_page = page_from if page_from is not None else spec.pagination.first_page

    if fetch_all:
        # show a preview only
        max_show = 5 if pages is None else min(5, pages)
        for i in range(max_show):
            p = start_page + i
            if page_to is not None and p > page_to:
                break
            urls.append(page_url(spec, p, vars))
        if page_to is None:
            urls.append("… (continues until empty page)")
        return urls

    if page_from is not None and page_to is not None:
        for p in range(page_from, page_to + 1):
            urls.append(page_url(spec, p, vars))
        return urls

    # Fallback to "pages count" starting at start_page
    if not pages:
        pages = 1
    for i in range(pages):
        p = start_page + i
        urls.append(page_url(spec, p, vars))
    return urls

def run_scraper(
    spec: ScraperSpec,
    vars: Dict[str, str] | None = None,
    pages: Optional[int] = None,
    fetch_all: bool = False,
    page_from: Optional[int] = None,
    page_to: Optional[int] = None,
    hard_max_pages: int = 1000,
    progress: Optional[Callable[[dict], None]] = None,
) -> pd.DataFrame:
    """
    Supports three modes:
      - fetch_all=True: start at (page_from or first_page) and continue until an empty page (or page_to / hard_max_pages).
      - page_from & page_to: fetch inclusive range.
      - pages=N: fetch N pages starting at (page_from or first_page).
    """
    fetcher = HybridFetcher(js_required=spec.js_required, page_load_strategy="eager")
    all_rows: List[Dict] = []

    start_page = page_from if page_from is not None else spec.pagination.first_page

    # === incremental saving setup ===
    # Data directory: repo_root/data/outputs/_partial/<spec-name>_<run-id>.csv
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    repo_root = Path(__file__).resolve().parents[2]
    partial_dir = repo_root / "data" / "outputs" / "_partial"
    partial_dir.mkdir(parents=True, exist_ok=True)
    partial_path = partial_dir / f"{slugify(spec.name)}_{run_id}.csv"

    def _append_partial(rows: List[Dict]) -> None:
        if not rows:
            return
        dfp = pd.DataFrame(rows)
        # write header only on first write
        header = not partial_path.exists()
        dfp.to_csv(partial_path, mode="a", header=header, index=False, encoding="utf-8")
        if progress:
            progress({"event": "partial_append", "rows": len(dfp), "file": str(partial_path)})

    if fetch_all:
        fetched = 0
        while True:
            current = start_page + fetched
            if page_to is not None and current > page_to:
                break
            target_url = page_url(spec, current, vars)
            if progress:
                progress({"event":"fetch_start","page": current, "url": target_url, "site": spec.name})
            try:
                final_url, html = fetcher.get(
                    target_url,
                    headers=spec.headers,
                    wait_for_css=(spec.item_css or spec.main_container_css or None),
                    wait_timeout=20,
                )
            except Exception as e:
                # If we already fetched some pages and we're in "ALL" mode,
                # treat a timeout/404 as "we reached the end" instead of failing the whole site.
                is_timeout = e.__class__.__name__.lower().endswith("timeout")
                is_http404 = getattr(getattr(e, "response", None), "status_code", None) == 404
                if fetched > 0 and (is_timeout or is_http404):
                    if progress:
                        progress({"event":"assume_end","page": current, "url": target_url, "reason": str(e)})
                    break
                raise
            rows = extract_items(html, spec.selectors, container_css=spec.main_container_css, item_css=spec.item_css)
            rows = normalize_rows(rows, base_url=final_url)
            if not rows:
                break
            all_rows.extend(rows)
            # incremental checkpoint
            _append_partial(rows)
            fetched += 1
            if fetched >= hard_max_pages:
                break

    elif page_from is not None and page_to is not None:
        for p in range(page_from, page_to + 1):
            target_url = page_url(spec, p, vars)
            if progress:
                progress({"event":"fetch_start","page": p, "url": target_url, "site": spec.name})
            final_url, html = fetcher.get(
                target_url,
                headers=spec.headers,
                wait_for_css=(spec.item_css or spec.main_container_css or None),
                wait_timeout=20,
            )
            rows = extract_items(html, spec.selectors, container_css=spec.main_container_css, item_css=spec.item_css)
            rows = normalize_rows(rows, base_url=final_url)
            all_rows.extend(rows)
            _append_partial(rows)

    else:
        if not pages:
            pages = 1
        for i in range(pages):
            p = start_page + i
            target_url = page_url(spec, p, vars)
            if progress:
                progress({"event":"fetch_start","page": p, "url": target_url, "site": spec.name})
            final_url, html = fetcher.get(
                target_url,
                headers=spec.headers,
                wait_for_css=(spec.item_css or spec.main_container_css or None),
                wait_timeout=20,
            )
            rows = extract_items(html, spec.selectors, container_css=spec.main_container_css, item_css=spec.item_css)
            rows = normalize_rows(rows, base_url=final_url)
            all_rows.extend(rows)
            _append_partial(rows)

    df = pd.DataFrame(all_rows)
    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"], keep="last")
    return df

