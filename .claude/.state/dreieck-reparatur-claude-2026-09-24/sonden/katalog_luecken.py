"""Welche Schlüssel fehlen oder sind verwaist — je Sprache, als JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from app.i18n import SOURCE_LANGUAGE  # noqa: E402
from app.i18n.catalog import available_languages, read_catalog  # noqa: E402
from tests.test_translations import message_ids  # noqa: E402

ids = message_ids()
out = {}
for language in available_languages():
    if language == SOURCE_LANGUAGE:
        continue
    catalog = read_catalog(language)
    out[language] = {
        "missing": sorted(key for key in ids if not catalog.get(key)),
        "orphaned": sorted(key for key in catalog if key not in ids),
    }
target = Path(".claude/.state/dreieck-reparatur-claude-2026-09-24/katalog_luecken.json")
target.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for language, entry in out.items():
    print(language, len(entry["missing"]), "fehlen,", len(entry["orphaned"]), "verwaist")
