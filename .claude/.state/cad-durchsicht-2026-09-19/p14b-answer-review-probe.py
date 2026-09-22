"""Unabhängige Gegenproben der reinen Antwortschicht, ohne Produktänderung."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.errors import AmbiguityError
from app.core.perceive.match_decisions import (
    group_fingerprint,
    mapping_with_decisions,
    resolve_group,
)
from app.core.perceive.matching import MatchResult
from app.core.types import Feature


def feature(name, x):
    return Feature(
        name,
        "hole",
        "detected",
        {"centre": (x, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "diameter": 4.0},
    )


failures = []

whole = MatchResult(ambiguous={"a": ("x",), "b": ("x",)})
try:
    partial = mapping_with_decisions(whole, {"a": ("x",)}, {"a": "x"})
except AmbiguityError:
    print("PASS: Teilgruppe abgewiesen")
else:
    failures.append("partial_group")
    print("FAIL: Teilgruppe freigegeben:", json.dumps(partial))

found = {"x": feature("x", -0.25), "y": feature("y", 0.25)}
claims = {"a": ("x", "y"), "b": ("x", "y")}
saved = group_fingerprint("body", claims, {"a": "y", "b": None}, found, (0, 0, 0), 10.0)
occupied = resolve_group(saved, "body", claims, found, (0, 0, 0), 10.0, frozenset({"x"}))
if occupied is None:
    print("PASS: Besetzter nichtgewählter Gruppenkandidat öffnet den Entscheid")
else:
    failures.append("occupied_unselected_candidate")
    print("FAIL: Gruppe trotz besetztem nichtgewähltem Kandidaten freigegeben:", json.dumps(occupied))

found = {"x": feature("x", 0.0)}
claims = {"a": ("x",), "b": ("x",)}
saved = group_fingerprint("body", claims, {"a": "x", "b": None}, found, (0, 0, 0), 10.0)
found["x"] = replace(found["x"], params={**found["x"].params, "centre": (float("nan"), 0, 0)})
invalid = resolve_group(saved, "body", claims, found, (0, 0, 0), 10.0)
if invalid is None:
    print("PASS: Nichtendliche aktuelle Geometrie wird nicht wiedererkannt")
else:
    failures.append("nonfinite_current_geometry")
    print("FAIL: Nichtendliche aktuelle Geometrie wiedererkannt:", json.dumps(invalid))

print("FINDINGS:", ", ".join(failures))
assert not failures, "Die Gegenfälle verletzen den vollständigen Antwortvertrag."
