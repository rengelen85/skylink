import json
import os
import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, os.path.dirname(__file__))
pl.Config.set_tbl_cols(20).set_tbl_width_chars(200).set_fmt_str_lengths(60)

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "dataset"


def pytest_addoption(parser):
    parser.addoption("--dataset-dir", default=str(DEFAULT_DIR), help="dataset directory (csv/, json/, _row_counts.json)")
    parser.addoption("--regen", action="store_true", help="also run the (slow) regenerate-and-diff determinism test")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--regen"): return
    skip = pytest.mark.skip(reason="needs --regen")
    for it in items:
        if "regen" in it.keywords: it.add_marker(skip)


class Tables:
    """Lazy, cached CSV loader. Every column is read as a string (empty -> null); tests cast what they need."""
    def __init__(self, root: Path):
        self.root = root; self._c = {}
        self.names = sorted(p.stem for p in (root / "csv").glob("*.csv"))
    def __getitem__(self, name: str) -> pl.DataFrame:
        if name not in self._c: self._c[name] = pl.read_csv(self.root / "csv" / f"{name}.csv", infer_schema=False)
        return self._c[name]


@pytest.fixture(scope="session")
def root(request) -> Path:
    return Path(request.config.getoption("--dataset-dir"))


@pytest.fixture(scope="session")
def T(root) -> Tables:
    return Tables(root)


@pytest.fixture(scope="session")
def counts(root) -> dict:
    return json.loads((root / "_row_counts.json").read_text())
