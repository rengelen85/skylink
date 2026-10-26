"""Regenerates the dataset in a temp dir and checks it is byte-identical to the committed files. Run with --regen."""
import hashlib
import shutil
import subprocess
import sys

import pytest


@pytest.mark.regen
def test_generator_is_deterministic(root, tmp_path):
    shutil.copy(root / "skylink_generator.py", tmp_path)
    p = subprocess.run([sys.executable, "-I", str(tmp_path / "skylink_generator.py")], cwd=tmp_path, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-800:]
    sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
    bad = []
    for sub in ("csv", "json"):
        a = {f.name: f for f in (root / sub).iterdir()}; b = {f.name: f for f in (tmp_path / sub).iterdir()}
        bad += [f"{sub}/{n}: only on one side" for n in a.keys() ^ b.keys()]
        bad += [f"{sub}/{n}: content differs" for n in sorted(a.keys() & b.keys()) if sha(a[n]) != sha(b[n])]
    if sha(root / "_row_counts.json") != sha(tmp_path / "_row_counts.json"): bad.append("_row_counts.json differs")
    assert not bad, "\n".join(bad)
