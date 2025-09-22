from __future__ import annotations
import random
import re
from unicodedata import normalize

def user_agent() -> str:
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
    ]
    return random.choice(agents)

_G2L = str.maketrans({
    "ά":"a","α":"a","Ά":"a","Α":"a",
    "β":"v","Β":"v",
    "γ":"g","Γ":"g",
    "δ":"d","Δ":"d",
    "ε":"e","έ":"e","Ε":"e","Έ":"e",
    "ζ":"z","Ζ":"z",
    "η":"i","ή":"i","Η":"i","Ή":"i",
    "θ":"th","Θ":"th",
    "ι":"i","ί":"i","ϊ":"i","ΐ":"i","Ι":"i","Ί":"i",
    "κ":"k","Κ":"k",
    "λ":"l","Λ":"l",
    "μ":"m","Μ":"m",
    "ν":"n","Ν":"n",
    "ξ":"x","Ξ":"x",
    "ο":"o","ό":"o","Ο":"o","Ό":"o",
    "π":"p","Π":"p",
    "ρ":"r","Ρ":"r",
    "σ":"s","Σ":"s","ς":"s",
    "τ":"t","Τ":"t",
    "υ":"y","ύ":"y","ϋ":"y","ΰ":"y","Υ":"y","Ύ":"y",
    "φ":"f","Φ":"f",
    "χ":"x","Χ":"x",
    "ψ":"ps","Ψ":"ps",
    "ω":"o","ώ":"o","Ω":"o","Ώ":"o",
})

def greek_to_latin(text: str) -> str:
    return (text or "").translate(_G2L)

def slugify(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return "search"
    raw = greek_to_latin(raw)
    raw = normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not ord(ch) in range(0x300, 0x370))
    slug = re.sub(r"[^a-z0-9]+", "-", raw, flags=re.IGNORECASE)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "search"
