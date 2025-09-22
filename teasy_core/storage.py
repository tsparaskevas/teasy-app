from __future__ import annotations
import pandas as pd
from pathlib import Path

def save_or_merge_csv(df: pd.DataFrame, path: Path, dedup_on: str = "url") -> tuple[int,int,int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    before = 0
    if path.exists():
        prev = pd.read_csv(path)
        before = len(prev)
        merged = pd.concat([prev, df], ignore_index=True)
    else:
        merged = df.copy()
    if dedup_on in merged.columns:
        merged = merged.drop_duplicates(subset=[dedup_on], keep="first").reset_index(drop=True)
    merged.to_csv(path, index=False)
    after = len(merged)
    added = max(0, after - before)
    return before, added, after
