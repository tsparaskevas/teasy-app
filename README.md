# Teasy App

Minimal UI to build/edit/test scrapers for news-sites teaser pages, run single/multi-site scrapes and track results.

- Build scrapers with manual CSS selectors (title, url, date, section, summary)
- Requests-Selenium fallback with consent-clicks
- Categories: `all`, `search`, `opinion` (search supports `{s}` and slug mapping)
- Multi-site runs, deduped CSV outputs, per-run logs
- Scraped data browser
- Visualize: per-site bar chart & daily timeline with date-range filters

## Quick start (local)

```bash
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/Home.py
```

## Citation

If you use this app, please cite:

Paraskevas, T. (2025). *Teasy App* (Version 1.0.0) [Software]. GitHub. https://github.com/tsparaskevas/teasy-app

```bibtex
@software{Paraskevas_Teasy_App_2025,
  author  = {Paraskevas, Thodoris},
  title   = {Teasy App},
  year    = {2025},
  version = {1.0.0},
  url     = {https://github.com/tsparaskevas/teasy-app},
  note    = {Software}
}
```


## Live demo (Streamlit Community Cloud)

👉 Try the read-only demo: **[Teasy App — Streamlit Cloud](https://teasy-app-bdpyknngneda7uqrgxbggp.streamlit.app/)**

**What works in the demo**
- Browse example outputs (`data/outputs` samples)
- View & filter data
- Visualize timelines and per-site counts
- Inspect recent run logs

**What’s disabled (and why)**
- Live scraping (Requests→Selenium) is **off** in demo mode.
- Reason: public cloud sessions are resource-limited, storage is ephemeral, and many news sites actively block or rate-limit headless scrapers.  
- The demo sets `TEASY_DEMO=1`, which disables network fetches. Clone the repo to run full scrapes locally.

**Run the full app locally**
```bash
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/Home.py
# Scraping is enabled locally (no TEASY_DEMO)
```

## License
MIT - see the [LICENSE](LICENSE) file for details.

© 2025 Thodoris Paraskevas
