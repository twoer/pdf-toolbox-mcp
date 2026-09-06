"""Real-world regression manifest sanity checks."""

from __future__ import annotations

import json
from pathlib import Path


def test_manifest_shape():
    path = Path(__file__).resolve().parent / "realworld" / "manifest.json"
    data = json.loads(path.read_text())

    assert data["name"] == "realworld-regressions"
    assert data["version"] == 1
    assert len(data["samples"]) == 7

    for item in data["samples"]:
        assert {"id", "fixture", "use", "assertions"} <= set(item)
        assert item["id"]
        assert item["fixture"]
        assert item["use"]
        assert item["assertions"]
