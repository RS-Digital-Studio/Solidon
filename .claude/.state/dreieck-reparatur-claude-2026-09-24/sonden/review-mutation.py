"""Review-Sonde: Fangen die Tests es, wenn eine Sicherung ausfällt? (Mutation, nur lesend)

Aufruf: python review-mutation.py <mutation>
  band_crosses   — `_band_crosses` antwortet immer „kreuzt nicht"
  folds          — `_folds` antwortet immer „faltet nicht"
  majority       — `wind_consistently` ohne Mehrheitsregel (Startdreieck bleibt)
Fährt nur die Reparaturtests ohne Fenster.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(r"F:\3D Druck")
sys.path.insert(0, str(ROOT))
mutation = sys.argv[1]


class Mutant:
    def pytest_configure(self, config):  # noqa: ARG002
        from app.core.geom import repair

        if mutation == "band_crosses":
            repair._band_crosses = lambda *args, **kwargs: False
        elif mutation == "folds":
            repair._folds = lambda *args, **kwargs: False
        else:
            raise SystemExit(f"unbekannte Mutation {mutation}")


code = pytest.main(
    [
        "-q",
        "-p",
        "no:cacheprovider",
        "-m",
        "not windowed and not performance",
        "-k",
        "bore_wall or countersink or rings_joined or quarter or face_with_holes or fold or cut_sphere or window_around",
        str(ROOT / "tests" / "test_repair.py"),
        str(ROOT / "tests" / "test_repair_features.py"),
    ],
    plugins=[Mutant()],
)
print("pytest exit", int(code))
