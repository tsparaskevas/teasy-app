# teasy_core/config.py
import os

def _get_secret(key: str, default: str = "0") -> str:
    """Read from Streamlit secrets if available; otherwise return default."""
    try:
        import streamlit as st  # present on Streamlit Cloud
        v = st.secrets.get(key, default)
        return str(v) if v is not None else default
    except Exception:
        return default

# Demo mode: ON only if TEASY_DEMO == "1" (env var or Streamlit Secret)
DEMO: bool = (os.getenv("TEASY_DEMO", "0") == "1") or (_get_secret("TEASY_DEMO", "0") == "1")
