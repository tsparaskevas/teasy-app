from __future__ import annotations
from bs4 import BeautifulSoup
from lxml import etree
from typing import Optional, List, Dict
from .models import Selector, FieldMap

def _get_text_or_attr(el, attr: Optional[str]):
    if el is None:
        return None
    if attr:
        try:
            return el.get(attr) if hasattr(el, "get") else el.attrib.get(attr)
        except Exception:
            return None
    try:
        return el.get_text(strip=True)
    except Exception:
        return None

def _sel_all(soup_or_el, sel: Optional[Selector]):
    if sel is None:
        return []
    if sel.type == "css":
        return soup_or_el.select(sel.query)
    elif sel.type == "xpath":
        root = etree.HTML(str(soup_or_el))
        return root.xpath(sel.query)
    return []

def extract_items(html: str, selectors: FieldMap, container_css: Optional[str] = None, item_css: Optional[str] = None) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    scope = soup
    if container_css:
        found = soup.select(container_css)
        if not found:
            # If main container returns 0, there are no articles
            return []
        scope = BeautifulSoup(str(found[0]), "lxml")

    rows: List[Dict] = []
    if item_css:
        items = scope.select(item_css)
        for it in items:
            row = {}
            row["title"] = _get_text_or_attr((_sel_all(it, selectors.title) or [None])[0], selectors.title.attr)
            if selectors.url:
                row["url"] = _get_text_or_attr(
                    (_sel_all(it, selectors.url) or [None])[0],
                    selectors.url.attr,
                )
            else:
                row["url"] = None
            if selectors.date:
                row["date"] = _get_text_or_attr((_sel_all(it, selectors.date) or [None])[0], selectors.date.attr)
            if selectors.summary:
                row["summary"] = _get_text_or_attr((_sel_all(it, selectors.summary) or [None])[0], selectors.summary.attr)
            if selectors.section:
                row["section"] = _get_text_or_attr((_sel_all(it, selectors.section) or [None])[0], selectors.section.attr)
            for k in ["title","url","date","summary","section"]:
                row.setdefault(k, None)
            if not row.get("title") and not row.get("url"):
                continue
            rows.append(row)
        return rows

    titles = _sel_all(scope, selectors.title)
    urls = _sel_all(scope, selectors.url) if selectors.url else []
    n = max(len(titles), len(urls)) if urls else len(titles)
    dates = _sel_all(scope, selectors.date) if selectors.date else []
    summaries = _sel_all(scope, selectors.summary) if selectors.summary else []
    sections = _sel_all(scope, selectors.section) if selectors.section else []

    for i in range(n):
        t_el = titles[i] if i < len(titles) else None
        u_el = urls[i] if i < len(urls) else None
        title = _get_text_or_attr(t_el, selectors.title.attr)
        if selectors.url:
            url = _get_text_or_attr(u_el, selectors.url.attr)
        else:
            url = None
        row = {"title": title or None, "url": url or None}
        if selectors.date:
            row["date"] = _get_text_or_attr(dates[i] if i < len(dates) else None, selectors.date.attr)
        if selectors.summary:
            row["summary"] = _get_text_or_attr(summaries[i] if i < len(summaries) else None, selectors.summary.attr)
        if selectors.section:
            row["section"] = _get_text_or_attr(sections[i] if i < len(sections) else None, selectors.section.attr)
        for k in ["title","url","date","summary","section"]:
            row.setdefault(k, None)
        if not row.get("title") and not row.get("url"):
            continue
        rows.append(row)
    return rows

#def selector_diagnostics(html: str, selectors: FieldMap, container_css: Optional[str], item_css: Optional[str]) -> Dict[str, int]:
#    soup = BeautifulSoup(html, "lxml")
#    scope = soup
#    if container_css:
#        found = soup.select(container_css)
#        if found:
#            scope = BeautifulSoup(str(found[0]), "lxml")
#    counts = {}
#    counts["container_found"] = 1 if (container_css and soup.select(container_css)) else 0
#    if item_css:
#        counts["items"] = len(scope.select(item_css))
#    counts["title_matches"] = len(_sel_all(scope, selectors.title))
#    if selectors.url:
#        counts["url_matches"] = len(_sel_all(scope, selectors.url))
#    if selectors.date:
#        counts["date_matches"] = len(_sel_all(scope, selectors.date))
#    if selectors.summary:
#        counts["summary_matches"] = len(_sel_all(scope, selectors.summary))
#    if selectors.section:
#        counts["section_matches"] = len(_sel_all(scope, selectors.section))
#
#    return counts

def selector_diagnostics(html: str, selectors: FieldMap, container_css: Optional[str], item_css: Optional[str]) -> Dict[str, int]:
    soup = BeautifulSoup(html, "lxml")
    scope = soup
    counts: Dict[str, int] = {}

    if container_css:
        found = soup.select(container_css)
        counts["container_found"] = 1 if found else 0
        if not found:
            # No container => no items
            counts["items"] = 0
            counts["title_matches"] = 0
            counts["url_matches"] = 0
            if selectors.date: counts["date_matches"] = 0
            if selectors.summary: counts["summary_matches"] = 0
            if selectors.section: counts["section_matches"] = 0
            return counts
        scope = BeautifulSoup(str(found[0]), "lxml")
    else:
        counts["container_found"] = 0

    if item_css:
        counts["items"] = len(scope.select(item_css))
    counts["title_matches"] = len(_sel_all(scope, selectors.title))
    if selectors.url:
        counts["url_matches"] = len(_sel_all(scope, selectors.url))
    if selectors.date:
        counts["date_matches"] = len(_sel_all(scope, selectors.date))
    if selectors.summary:
        counts["summary_matches"] = len(_sel_all(scope, selectors.summary))
    if selectors.section:
        counts["section_matches"] = len(_sel_all(scope, selectors.section))

    return counts
