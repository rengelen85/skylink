from datetime import date, datetime

import polars as pl

TODAY = date(2026, 10, 26)
NOW = datetime(2026, 10, 26, 8, 26)
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
BLOCKING = ["APPROVED", "ACTIVE", "RECORDED", "ENROLLED"]   # availability statuses that make someone unavailable


def D(c):   # ISO date column -> Date
    return pl.col(c).str.to_date()


def TS(c):  # ISO timestamp column -> Datetime
    return pl.col(c).str.to_datetime(TS_FMT)


def none(df: pl.DataFrame, msg: str = ""):
    """Assert a frame of offending rows is empty; show a sample otherwise."""
    assert df.height == 0, f"{msg}: {df.height:,} offending rows, e.g.\n{df.head(5)}"


def overlaps(df: pl.DataFrame, key: str, start: str, end: str) -> pl.DataFrame:
    """Rows whose interval starts before the previous interval of the same key ended."""
    return (df.sort(key, start)
              .with_columns(_prev_end=pl.col(end).shift(1).over(key))
              .filter(pl.col(start) < pl.col("_prev_end")))
