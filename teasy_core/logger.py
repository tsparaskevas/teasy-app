from __future__ import annotations
from pathlib import Path
import pandas as pd
from datetime import datetime

def append_run_log(log_csv: Path, **fields):
    log_csv.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    fields.setdefault("run_date", now.strftime("%Y-%m-%d"))
    fields.setdefault("run_time", now.strftime("%H:%M:%S"))

    # new row for this run
    df = pd.DataFrame([fields])

    if log_csv.exists():
        try:
            # try to read the log
            prev = pd.read_csv(log_csv)
        except pd.errors.EmptyDataError:
            # file exists but it's empty or has no header
            prev = pd.DataFrame(columns=df.columns)
    else:
        # log file doesn't exist yet
        prev = pd.DataFrame(columns=df.columns)

    # concat old and new rows
    all_df = pd.concat([prev, df], ignore_index=True)

    # save log
    all_df.to_csv(log_csv, index=False)

