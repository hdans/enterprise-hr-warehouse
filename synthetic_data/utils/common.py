import os
import random
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker


def init_seed(seed: int = 42) -> Faker:
    random.seed(seed)
    np.random.seed(seed)
    fake = Faker("id_ID")
    Faker.seed(seed)
    return fake


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def ensure_dirs(paths: list[str]) -> None:
    for p in paths:
        os.makedirs(p, exist_ok=True)


def save_csv(df: pd.DataFrame, folder: str, filename: str) -> None:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    df.to_csv(path, index=False)
    print(f"[ok] {filename:<35s} -> {len(df):>9,} rows")


def add_minutes(value: datetime, minutes: int) -> datetime:
    return value + timedelta(minutes=int(minutes))


def to_date(value) -> date | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if value == "":
        return None
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()
