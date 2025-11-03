from __future__ import annotations
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
from urllib.parse import urljoin
import unicodedata

# ------------------------------------------------------------
# Date parsing helpers (comments in English, Greek tokens kept)
# ------------------------------------------------------------
# 20/09/2025 • 00:00 •   also accepts middle dot, dash, comma, or vertical bar
RE_DDMMYYYY_BULLET_HHMM = re.compile(
    r"""^\s*
        (\d{1,2})[./-](\d{1,2})[./-](\d{2,4})     # DD/MM/YYYY
        \s*[-–—•\u00B7,|]\s*                      # dash/en/em dash/bullet/middle dot/comma/pipe
        (\d{1,2}):(\d{2})(?::(\d{2}))?            # HH:MM[:SS]
        \s*(?:[•\u00B7|]\s*)?$                    # optional trailing bullet/middle dot/pipe
    """, re.X
)

# 19/09/2025 - 20:00   (also accepts en/em dash and optional seconds)
RE_DDMMYYYY_DASH_HHMM = re.compile(
    r"""^\s*
        (\d{1,2})[./-](\d{1,2})[./-](\d{2,4})      # DD/MM/YYYY
        \s*[-–—]\s*                                 # dash with optional spaces
        (\d{1,2}):(\d{2})(?::(\d{2}))?              # HH:MM[:SS]
        \s*$
    """, re.X
)

# 07:27 17/09/2025 or 07:2717/09/2025  (space optional)
RE_HHMM_DDMMYYYY_COMPACT = re.compile(
    r"^\s*(\d{1,2}):(\d{2})\s*(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\s*$"
)

# 19.09.25 13:41 or 19.09.2513:41  (space optional; year 2 or 4 digits)
# use a lookahead to ensure year is followed by a time, so '25' doesn't eat the '13'
RE_DDMMYYYY_HHMM_COMPACT = re.compile(
    r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})(?=\s*\d{1,2}:)\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$"
)

# Examples: "19/09/2025 10:10", "19-09-25 10:10", "19.09.2025 10:10:05"
RE_DDMMYYYY_HHMM = re.compile(
    r"^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$"
)

# Example: "11:37 09/07"  -> assume current year
RE_HHMM_DDMM = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*(\d{2})/(\d{2})\s*$")

# Examples: "28/09/2023", "28-09-23", "28.09.2023"
RE_DDMMYYYY = re.compile(r"^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\s*$")

# Example: "28/09" (assume current year)
RE_DDMM = re.compile(r"^\s*(\d{1,2})[./-](\d{1,2})\s*$")

# Examples accepted (month token can be Greek or English):
#   "19 Σεπ 2025 10:24"
#   "19 Σεπ. 2025 10:24"
#   "19 Sep 2025 10:24"
#   "19 Σεπ 10:24"  (no year -> assume current)
#   "19 Σεπ 2025"   (no time)
RE_DAY_MON_YEAR_TIME = re.compile(
    r"""(?ix)
    ^\s*
    (?P<day>\d{1,2})
    (?:\s*,\s*|\s+)                                  # allow comma or space after day
    (?P<mon>[A-Za-zΑ-ΩΆΈΊΌΎΉΏα-ωάέίόύήώϊϋΐΰ.]+)      # month token (Greek or English)
    (?: (?:\s*,\s*|\s+) (?P<year>\d{2,4}) )?         # optional year (comma/space)
    (?: (?:\s*,\s*|\s+|\s*[-–—•\u00B7,|]\s*) (?P<hh>\d{1,2}):(?P<mm>\d{2})(?::(?P<ss>\d{2}))? )?  # optional time, accepts | • · dashes
    \s*$
    """
)

# 07:00, 1 Σεπτεμβρίου 2025  (optionally with seconds and optional commas/spaces)
RE_HHMM_DAY_MON_YEAR = re.compile(
    r"""(?ix)
    ^\s*
    (?P<hh>\d{1,2}):(?P<mm>\d{2})(?::(?P<ss>\d{2}))?   # time first
    (?:\s*,\s*|\s+)                                    # comma or space
    (?P<day>\d{1,2})
    (?:\s*,\s*|\s+)
    (?P<mon>[A-Za-zΑ-ΩΆΈΊΌΎΉΏα-ωάέίόύήώϊϋΐΰ.]+)
    (?:\s*,\s*|\s+)(?P<year>\d{2,4})?                  # year optional
    \s*$
    """
)

# 07:00, Παρασκευή 1 Σεπτεμβρίου 2025  (time first, optional weekday)
RE_HHMM_WD_DAY_MON_YEAR = re.compile(
    r"""(?ix)
    ^\s*
    (?P<hh>\d{1,2}):(?P<mm>\d{2})(?::(?P<ss>\d{2}))?   # time first
    (?:\s*,\s*|\s+)                                    # comma or space
    (?:(?P<wd>[\w.\u0370-\u03FF\u1F00-\u1FFF]+)(?:\s*,\s*|\s+))?  # optional weekday (Greek/English), optional comma
    (?P<day>\d{1,2})
    (?:\s*,\s*|\s+)
    (?P<mon>[\w.\u0370-\u03FF\u1F00-\u1FFF]+)
    (?:\s*,\s*|\s+)(?P<year>\d{2,4})?                  # optional year
    \s*$
    """
)

# "x ago" families (English)
RE_EAGO = [
    re.compile(r"(?i)\b(\d+)\s*seconds?\s*ago\b"),
    re.compile(r"(?i)\b(\d+)\s*mins?\s*ago\b"),
    re.compile(r"(?i)\b(\d+)\s*hours?\s*ago\b"),
    re.compile(r"(?i)\b(\d+)\s*days?\s*ago\b"),
    re.compile(r"(?i)\b(\d+)\s*weeks?\s*ago\b"),
    re.compile(r"(?i)\b(\d+)\s*months?\s*ago\b"),
    re.compile(r"(?i)\b(\d+)\s*years?\s*ago\b"),
]

# "x ago" families (Greek)
RE_GAGO = [
    # "πριν 12 δευτερόλεπτα" / "πριν 12 δευτ." / "sec" / "seconds"
    re.compile(r"(?i)\bπριν(?:\s+από)?\s+(\d+)\s*(δευτερόλεπτα|δευτ\.?|sec|seconds?)\b"),
    # "πριν 5 λεπτά" / "πριν 5 λεπτο" / "min" / "minutes"
    re.compile(r"(?i)\bπριν(?:\s+από)?\s+(\d+)\s*(λεπτά|λεπτο|λεπτ\.?|min|minutes?)\b"),
    # "πριν 3 ωρες" / "πριν 3 ώρα" / "πριν 3 ώρες" / "hour" / "hours"
    re.compile(r"(?i)\bπριν(?:\s+από)?\s+(\d+)\s*(ωρες|ώρα|ώρες|hour|hours?)\b"),
    # "πριν 2 ημέρες" / "πριν 2 μέρες" / "day" / "days"
    re.compile(r"(?i)\bπριν(?:\s+από)?\s+(\d+)\s*(ημέρες|ημέρα|μέρες|μέρα|day|days?)\b"),
    # "πριν 2 εβδομάδες" / "week" / "weeks"
    re.compile(r"(?i)\bπριν(?:\s+από)?\s+(\d+)\s*(εβδομάδες|εβδομάδα|week|weeks?)\b"),
    # "πριν 2 μήνες" / "πριν 2 μηνες" / "month" / "months"
    re.compile(r"(?i)\bπριν(?:\s+από)?\s+(\d+)\s*(μήνες|μηνες|month|months?)\b"),
    # "πριν 2 χρόνια" / "πριν 2 έτη" / "year" / "years"
    re.compile(r"(?i)\bπριν(?:\s+από)?\s+(\d+)\s*(χρόνια|έτη|year|years?)\b"),
]

# “Bare” ποσότητες χωρίς το «πριν» (π.χ. "2 ημέρες", "2 εβδομάδες")
RE_GBARE = [
    re.compile(r"(?i)^\s*(\d+)\s*(δευτερόλεπτα|δευτ\.?|sec|seconds?)\s*$"),
    re.compile(r"(?i)^\s*(\d+)\s*(λεπτά|λεπτο|λεπτ\.?|min|minutes?)\s*$"),
    re.compile(r"(?i)^\s*(\d+)\s*(ωρες|ώρα|ώρες|hour|hours?)\s*$"),
    re.compile(r"(?i)^\s*(\d+)\s*(ημέρες|ημέρα|μέρες|μέρα|day|days?)\s*$"),
    re.compile(r"(?i)^\s*(\d+)\s*(εβδομάδες|εβδομάδα|week|weeks?)\s*$"),
    re.compile(r"(?i)^\s*(\d+)\s*(μήνες|μηνες|month|months?)\s*$"),
    re.compile(r"(?i)^\s*(\d+)\s*(χρόνια|έτη|year|years?)\s*$"),
]

# Examples: "11:20", "11:20:05", "ώρα 11:20", "11:20 πμ", "11:20 μμ", "11:20 pm", "11:20,"
RE_HHMM_ONLY = re.compile(
    r"^\s*(?:ώρα\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(πμ|μμ|am|pm|AM|PM)?\s*[.,;·]?\s*$",
    re.IGNORECASE
)

# Translation map to strip Greek accents to their base letters
_G_ACCENTS = str.maketrans({
    "ά": "α", "έ": "ε", "ί": "ι", "ό": "ο", "ύ": "υ", "ή": "η", "ώ": "ω",
    "ϊ": "ι", "ϋ": "υ", "ΐ": "ι", "ΰ": "υ",
    "Ά": "Α", "Έ": "Ε", "Ί": "Ι", "Ό": "Ο", "Ύ": "Υ", "Ή": "Η", "Ώ": "Ω",
})

# Month lookup (Greek tokens, accent-insensitive via translation) + English tokens
MONTHS: Dict[str, int] = {
    # Greek short
    "ιαν": 1, "φεβ": 2, "μαρ": 3, "απρ": 4, "μαι": 5, "μαϊ": 5, "ιουν": 6, "ιουλ": 7,
    "αυγ": 8, "σεπ": 9, "σεπτ": 9, "οκτ": 10, "νοε": 11, "δεκ": 12,
    # Greek long (genitive / nominative; accents removed at lookup time)
    "ιανουαριου": 1, "ιανουαριος": 1,
    "φεβρουαριου": 2, "φεβρουαριος": 2,
    "μαρτιου": 3, "μαρτιος": 3,
    "απριλιου": 4, "απριλιος": 4,
    "μαιου": 5, "μαιος": 5,
    "ιουνιου": 6, "ιουνιος": 6,
    "ιουλιου": 7, "ιουλιος": 7,
    "αυγουστου": 8, "αυγουστος": 8,
    "σεπτεμβριου": 9, "σεπτεμβριος": 9,
    "οκτωβριου": 10, "οκτωβριος": 10,
    "νοεμβριου": 11, "νοεμβριος": 11,
    "δεκεμβριου": 12, "δεκεμβριος": 12,
    # English short/full
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

def _preclean(text: str) -> str:
    # Normalize Unicode (e.g., fullwidth digits/punct to ASCII)
    t = unicodedata.normalize("NFKC", text)
    # Normalize common “weird” spaces used on news sites
    t = t.replace("\u00A0", " ").replace("\u202F", " ").replace("\u2009", " ")
    # Normalize comma lookalikes to ASCII comma
    t = t.replace("،", ",").replace("，", ",")
    # Collapse repeated whitespace and trim
    t = re.sub(r"\s+", " ", t).strip(" \t\r\n,")
    return t

def _month_to_num(token: str) -> Optional[int]:
    if not token:
        return None
    t = token.strip().strip(".").lower().translate(_G_ACCENTS)
    # normalize diaeresis variants to base vowels
    t = t.replace("ϊ","ι").replace("ΐ","ι").replace("ϋ","υ").replace("ΰ","υ")
    return MONTHS.get(t)

def _apply_ago(now, text: str):
    t = text.strip()

    # Αγγλικά "X ... ago"
    for i, rex in enumerate(RE_EAGO):
        m = rex.search(t)
        if m:
            val = int(m.group(1))
            if i == 0: dt = now - timedelta(seconds=val)
            elif i == 1: dt = now - timedelta(minutes=val)
            elif i == 2: dt = now - timedelta(hours=val)
            elif i == 3: dt = now - timedelta(days=val)
            elif i == 4: dt = now - timedelta(weeks=val)
            elif i == 5: dt = now - timedelta(days=val*30)
            elif i == 6: dt = now - timedelta(days=val*365)
            return dt.strftime("%Y-%m-%dT%H:%M")

    # Ελληνικά "Πριν (από) X ..."
    for i, rex in enumerate(RE_GAGO):
        m = rex.search(t)
        if m:
            val = int(m.group(1))
            if i == 0: dt = now - timedelta(seconds=val)
            elif i == 1: dt = now - timedelta(minutes=val)
            elif i == 2: dt = now - timedelta(hours=val)
            elif i == 3: dt = now - timedelta(days=val)
            elif i == 4: dt = now - timedelta(weeks=val)
            elif i == 5: dt = now - timedelta(days=val*30)
            elif i == 6: dt = now - timedelta(days=val*365)
            return dt.strftime("%Y-%m-%dT%H:%M")

    # Ελληνικά/Αγγλικά "X ημέρες/εβδομάδες/..."  (χωρίς "πριν")
    for i, rex in enumerate(RE_GBARE):
        m = rex.search(t)
        if m:
            val = int(m.group(1))
            if i == 0: dt = now - timedelta(seconds=val)
            elif i == 1: dt = now - timedelta(minutes=val)
            elif i == 2: dt = now - timedelta(hours=val)
            elif i == 3: dt = now - timedelta(days=val)
            elif i == 4: dt = now - timedelta(weeks=val)
            elif i == 5: dt = now - timedelta(days=val*30)
            elif i == 6: dt = now - timedelta(days=val*365)
            return dt.strftime("%Y-%m-%dT%H:%M")

    return None

def normalize_date(text: Optional[str]) -> Optional[str]:
    """
    Normalize teaser-date shapes to ISO-like strings:
      - '19 Σεπ 2025 10:24' -> '2025-09-19T10:24'
      - '19 Σεπ 2025'      -> '2025-09-19'
      - '19 Σεπ 10:24'     -> '<current-year>-09-19T10:24'
      - '11:37 09/07'      -> '<current-year>-07-09T11:37'
      - '28/09/2023'       -> '2023-09-28'
      - '28/09'            -> '<current-year>-09-28'
      - Greek/English 'x ago' like 'πριν 3 ώρες' / '3 hours ago'
    Returns the original text if no parser matched.
    """
    if not text:
        return None
    t = _preclean(text)
    now = datetime.now()

    # "x ago" forms
    ago = _apply_ago(now, t)
    if ago:
        return ago

        # bare time only: "HH:MM[:SS]" -> assume today
    m = RE_HHMM_ONLY.match(t)
    if m:
        hh_s, mm_s, ss_s, ap = m.groups()
        hh, mi = int(hh_s), int(mm_s)
        ss = int(ss_s) if ss_s else 0
        if ap:
            ap_norm = ap.lower()
            if ap_norm in ("πμ", "am"):
                if hh == 12:
                    hh = 0
            elif ap_norm in ("μμ", "pm"):
                if hh < 12:
                    hh += 12
        try:
            dt = datetime(year=now.year, month=now.month, day=now.day,
                          hour=hh, minute=mi, second=ss)
            return dt.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            return None

    # "20/09/2025 • 00:00 •"
    m = RE_DDMMYYYY_BULLET_HHMM.match(t)
    if m:
        dd_s, MM_s, yy_s, hh_s, mm_s, ss_s = m.groups()
        dd, MM = int(dd_s), int(MM_s)
        yy = int(yy_s)
        if yy < 100:
            yy = 2000 + yy
        hh, mi = int(hh_s), int(mm_s)
        ss = int(ss_s) if ss_s else 0
        try:
            dt = datetime(year=yy, month=MM, day=dd, hour=hh, minute=mi, second=ss)
            return dt.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            return None

    # "19/09/2025 - 20:00" (supports ., -, / separators; en/em dash; optional seconds)
    m = RE_DDMMYYYY_DASH_HHMM.match(t)
    if m:
        dd_s, MM_s, yy_s, hh_s, mm_s, ss_s = m.groups()
        dd, MM = int(dd_s), int(MM_s)
        yy = int(yy_s)
        if yy < 100:
            yy = 2000 + yy
        hh, mi = int(hh_s), int(mm_s)
        ss = int(ss_s) if ss_s else 0
        try:
            dt = datetime(year=yy, month=MM, day=dd, hour=hh, minute=mi, second=ss)
            return dt.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            return None

    # "19.09.25 13:41" or "19.09.2513:41" (also supports 4-digit year and optional seconds)
    m = RE_DDMMYYYY_HHMM_COMPACT.match(t)
    if m:
        dd_s, MM_s, yy_s, hh_s, mm_s, ss_s = m.groups()
        dd, MM = int(dd_s), int(MM_s)
        yy = int(yy_s)
        if yy < 100:  # interpret 2-digit year as 2000+YY
            yy = 2000 + yy
        hh, mi = int(hh_s), int(mm_s)
        ss = int(ss_s) if ss_s else 0
        try:
            dt = datetime(year=yy, month=MM, day=dd, hour=hh, minute=mi, second=ss)
            return dt.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            return None

    # "07:27 17/09/2025" or "07:2717/09/2025"
    m = RE_HHMM_DDMMYYYY_COMPACT.match(t)
    if m:
        hh_s, mm_s, dd_s, MM_s, yy_s = m.groups()
        hh, mm = int(hh_s), int(mm_s)
        dd, MM = int(dd_s), int(MM_s)
        yy = int(yy_s)
        if yy < 100:
            yy = 2000 + yy
        try:
            dt = datetime(year=yy, month=MM, day=dd, hour=hh, minute=mm)
            return dt.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            return None

    # 07:00, Παρασκευή 1 Σεπτεμβρίου 2025  (time first, optional weekday)
    m = RE_HHMM_WD_DAY_MON_YEAR.match(t)
    if m:
        hh = int(m.group("hh"))
        mi = int(m.group("mm"))
        ss = m.group("ss")
        dd = int(m.group("day"))
        mon_tok = m.group("mon")
        year_s = m.group("year")
        mon = _month_to_num(mon_tok)
        if mon:
            year = int(year_s) if year_s else now.year
            if year < 100:
                year = 2000 + year
            try:
                dt = datetime(
                    year=year, month=mon, day=dd,
                    hour=hh, minute=mi, second=(int(ss) if ss else 0)
                )
                return dt.strftime("%Y-%m-%dT%H:%M")
            except ValueError:
                return None

    # 07:00, 1 Σεπτεμβρίου 2025  (time first)
    m = RE_HHMM_DAY_MON_YEAR.match(t)
    if m:
        hh = int(m.group("hh"))
        mi = int(m.group("mm"))
        ss = m.group("ss")
        dd = int(m.group("day"))
        mon_tok = m.group("mon")
        year_s = m.group("year")
        mon = _month_to_num(mon_tok)
        if mon:
            year = int(year_s) if year_s else now.year
            if year < 100:
                year = 2000 + year
            try:
                dt = datetime(year=year, month=mon, day=dd, hour=hh, minute=mi, second=(int(ss) if ss else 0))
                return dt.strftime("%Y-%m-%dT%H:%M")
            except ValueError:
                return None

    # 19/09/2025 10:10 (optionally with seconds)
    m = RE_DDMMYYYY_HHMM.match(t)
    if m:
        dd, MM, yy, hh, mi, ss = m.groups()
        dd, MM = int(dd), int(MM)
        yy = int(yy)
        if yy < 100:
            yy = 2000 + yy
        hh = int(hh); mi = int(mi); ss = int(ss) if ss else 0
        try:
            dt = datetime(year=yy, month=MM, day=dd, hour=hh, minute=mi, second=ss)
            return dt.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            return None

    # 11:37 09/07
    m = RE_HHMM_DDMM.match(t)
    if m:
        hh, mm, dd, MM = map(int, m.groups())
        try:
            dt = datetime(year=now.year, month=MM, day=dd, hour=hh, minute=mm)
            return dt.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            return None

    # 28/09/2023
    m = RE_DDMMYYYY.match(t)
    if m:
        dd, MM, yy = m.groups()
        dd, MM = int(dd), int(MM)
        yy = int(yy)
        if yy < 100:
            yy = 2000 + yy
        try:
            dt = datetime(year=yy, month=MM, day=dd)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    # 28/09
    m = RE_DDMM.match(t)
    if m:
        dd, MM = map(int, m.groups())
        try:
            dt = datetime(year=now.year, month=MM, day=dd)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    # Day Mon [Year] [HH:MM[:SS]]
    m = RE_DAY_MON_YEAR_TIME.match(t)
    if m:
        dd = int(m.group("day"))
        mon_tok = m.group("mon")
        year_s = m.group("year")
        hh = m.group("hh")
        mm = m.group("mm")
        ss = m.group("ss")
        mon = _month_to_num(mon_tok)
        if mon:
            year = int(year_s) if year_s else now.year
            if year < 100:
                year = 2000 + year
            try:
                if hh and mm:
                    h = int(hh); mi = int(mm); s = int(ss) if ss else 0
                    dt = datetime(year=year, month=mon, day=dd, hour=h, minute=mi, second=s)
                    return dt.strftime("%Y-%m-%dT%H:%M")
                else:
                    dt = datetime(year=year, month=mon, day=dd)
                    return dt.strftime("%Y-%m-%d")
            except ValueError:
                return None

    # Fallback: return original
    return t

REQUIRED_COLS = ["title","url","date","summary","section"]

_WS_RE = re.compile(r"\s+")
_ZW_RE = re.compile(r"[\u200B\u200C\u200D\uFEFF]")  # zero-width chars

def tidy_text(s):
    if s is None:
        return None
    t = str(s)
    # Normalize non-breaking space & zero-width stuff
    t = t.replace("\xa0", " ")
    t = _ZW_RE.sub("", t)
    # Collapse all whitespace runs to single spaces
    t = _WS_RE.sub(" ", t).strip()
    # Optional light punctuation spacing fixes
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    return t

def normalize_rows(rows: List[Dict], base_url: Optional[str] = None) -> List[Dict]:
    out: List[Dict] = []
    for r in rows:
        rr = dict(r)
        u = (rr.get("url") or "").strip()
        if base_url and u and not u.lower().startswith("http"):
            rr["url"] = urljoin(base_url, u)
        rr["date"] = normalize_date(rr.get("date"))
        # Clean textual fields
        for _k in ("title","summary","section"):
            if rr.get(_k) is not None:
                rr[_k] = tidy_text(rr[_k])
        for k in REQUIRED_COLS:
            rr.setdefault(k, None)
        out.append(rr)
    return out

