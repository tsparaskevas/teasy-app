---
title: 'Teasy App: a configurable tool for reproducible scraping of news-site teaser pages'
tags:
  - Python
  - web scraping
  - journalism studies
  - computational social science
  - online news
authors:
  - name: Thodoris Paraskevas
    orcid: 0000-0001-8857-7581 
    affiliation: 1
affiliations:
  - name: Faculty of Communication and Media Studies, National and Kapodistrian University of Athens, Greece
    index: 1
date: 2025-12-01
bibliography: paper.bib
---

# Summary

Online news websites present teaser lists—on front pages, category pages, or
search results—that link to full articles. These lists often include titles,
URLs, summaries, sections, and timestamps. Teaser scrapers are a central tool
for building URL lists for subsequent article collection, but they are
typically implemented as ad-hoc scripts with limited reproducibility.

**Teasy App** is an interactive Streamlit application for configuring,
validating, and running scrapers for news-site teaser pages. It provides a
template-based system for defining CSS selectors, supports Requests→Selenium
fallback with consent-click handling, and enables multi-site scraping with
deduped CSV outputs and per-run logs. The application includes tools for data
browsing and simple visualization, helping researchers understand coverage
patterns and assess scraper health.

# Statement of need

Researchers often require large sets of URLs from news sites to assemble
article corpora for downstream text analysis. While many scraping libraries
exist, they do not provide a reproducible workflow for building and testing
site-specific teaser scrapers. Challenges include site heterogeneity,
frequent HTML changes, dynamic content, and cookie/consent pop-ups.

Existing solutions for teaser scraping are either:

- one-off scripts tied to specific outlets;
- generic scraping libraries requiring substantial coding; or
- pipelines without UI support, making it difficult for collaborators to
  understand and revise extraction logic.

**Teasy App** fills this niche by offering:

- per-site configurable teaser templates,
- interactive testing of selectors on live pages or snapshots,
- Requests→Selenium fallback with optional consent-click handling,
- multi-site scraper orchestration, and
- structured logging and visualization.

Combined with its companion tool, **Conty App**, which handles article-level
extraction, Teasy App covers the initial stage of URL collection within a
fully reproducible workflow.

# Software description

Teasy App provides:

- Template configuration for teaser scraping (title, URL, date, summary,
  section).
- Support for categories (`all`, `search`, `opinion`), including `{s}`
  placeholder expansion and slug mapping for search queries.
- Live fetching or demo-mode snapshot loading.
- Multi-site scraping with deduped outputs and run logs.
- Browsing and filtering of collected teaser data.
- Basic visualizations (per-site bar chart, daily timeline, date-range
  filters).

The app is written in Python and built on Streamlit. Scraping is performed via
the Requests library with Selenium fallback, allowing it to handle dynamic
content and consent pop-ups.

# Relation to Conty App

Teaser scraping represents the “front end” of news-data collection, where
URL lists are assembled from site pages. **Teasy App** performs this step,
while **Conty App** processes the corresponding full articles using
template-based extraction rules. Together, the two tools form a coordinated
pipeline for reproducible news-data collection, but each is published as an
independent application suited to a distinct stage of the workflow.

# Acknowledgements

I thank colleagues and collaborators who provided feedback on early versions
of the scrapers and the maintainers of open-source libraries such as
Streamlit [@streamlit2021], Requests [@requests], Selenium [@selenium],
BeautifulSoup [@bs4], and Pandas [@pandas].

# References

