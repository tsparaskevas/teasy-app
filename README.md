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

```bibtext
@software{Paraskevas_Teasy_App_2025,
  author  = {Paraskevas, Thodoris},
  title   = {Teasy App},
  year    = {2025},
  version = {1.0.0},
  url     = {https://github.com/tsparaskevas/teasy-app},
  note    = {Software}
}
```

## License
MIT - see the [LICENSE](LICENSE) file for details.

© 2025 Thodoris Paraskevas
