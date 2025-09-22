from __future__ import annotations
from pathlib import Path
import pandas as pd
from datetime import datetime

def append_run_log(log_csv: Path, **fields):
    log_csv.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    fields.setdefault("run_date", now.strftime("%Y-%m-%d"))
    fields.setdefault("run_time", now.strftime("%H:%M:%S"))
    df = pd.DataFrame([fields])
    if log_csv.exists():
        prev = pd.read_csv(log_csv)
        all_df = pd.concat([prev, df], ignore_index=True)
    else:
        all_df = df
    all_df.to_csv(log_csv, index=False)
