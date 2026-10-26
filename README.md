# SkyLink dataset validation

Repeatable checks for the synthetic dataset produced by `dataset/skylink_generator.py`.

```bash
./setup.sh               # installs uv if missing, then creates .venv (polars + pytest)
uv run pytest            # ~5 s: structure, keys, FKs, business rules, README stories
uv run pytest --regen    # + re-runs the generator in a temp dir and diffs every file (~20 s)
uv run pytest --dataset-dir PATH   # validate another copy of the dataset
```

Tests live in `tests/` (one module per area). If you find a generator defect you can't fix right away, encode it as an `xfail(strict=True)`
test with the cause in the reason: it stays green now and fails loudly once the generator is fixed, so the marker gets removed.
