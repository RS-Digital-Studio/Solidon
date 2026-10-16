"""Prüfpunkt 15 misst die Einfügemarke an einem Stand, an dem es den Weg der Zeile gibt.

Die Marke stand immer vor dem letzten Schritt der Startszene. Entsteht erst dort,
worüber der Weg führt — die Bohrung, an der *Bohrung ändern* steht, der Befund
des Körpers unter dem Bett —, gibt es den Weg am Stand davor nicht: Jeder Lauf
seit welle4 meldete an *Bohrung ändern* und *Auf das Bett setzen* „nicht
auffindbar“ im Schritt „einfügen“ (Läufe 001, 002), ein Fund gegen die
Anwendung, wo der Kunde nur nichts zu wählen hätte. Jetzt wendet der Fall die
Zeile dann einmal an und setzt die Marke vor diesen Schritt. Ebenso blieb eine
Absage, die als Meldung aus dem Arbeiter kam, offen, und die Ereignisschleife
kehrte nie zurück (*Als Muster zusammenfassen*: fünf Minuten in ``show_error``).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from tools import file_acceptance, function_list, function_scenes


def _halt_case(tmp_path: Path, row_id: str) -> dict[str, Any]:
    """Der Funktionsfall der Zeile nur mit Prüfpunkt 15, im eigenen Prozess wie im Lauf."""
    from app.core.scene.project import save
    from tools.file_acceptance import ROOT, write_json

    rows = [asdict(row) for row in function_list.rows()]
    cases = file_acceptance.function_cases(rows, row_ids=[row_id], phases=["halt"])
    assert len(cases) == 1, cases
    case = cases[0]
    out = tmp_path / "abnahme"
    (out / "scenes").mkdir(parents=True)
    key = Path(case.path).stem
    save(function_scenes.build_scene(key), out / "scenes" / f"{key}.p3d")
    write_json(out / "rows.json", [row for row in rows if row["id"] == row_id])
    write_json(out / "cases.json", [asdict(case)])
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONUTF8": "1"}
    finished = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "file_acceptance.py"),
            "child",
            "--out",
            str(out),
            "--case",
            str(case.number),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        check=False,
    )
    assert finished.returncode == 0, (key, finished.stdout, finished.stderr)
    folder = out / "cases" / f"{case.number:03d}"
    protocol: dict[str, Any] = json.loads((folder / "function.json").read_text(encoding="utf-8"))
    return protocol


@pytest.mark.windowed
@pytest.mark.parametrize(
    ("row_id", "outcome"),
    [("resize_hole", "ergebnis"), ("group_pattern", "absage")],
    ids=["bohrung-aendern", "als-muster"],
)
def test_the_insertion_marker_stands_where_the_way_of_the_row_exists(
    tmp_path: Path, row_id: str, outcome: str
) -> None:
    protocol = _halt_case(tmp_path, row_id)
    inserting = [step for step in protocol["steps"] if step.get("phase") == "einfügen"]
    assert [f for f in protocol["findings"] if f.get("phase") == "einfügen"] == []
    assert protocol["insertion"] is not None, protocol.get("unmeasured")
    assert protocol["insertion"]["outcome"] == outcome, protocol["insertion"]
    # Die erste Marke stand vor dem letzten Schritt der Startszene, die zweite vor
    # dem Schritt, den die Zeile eben angelegt hat — dort steht ihr Weg.
    markers = [step["target"] for step in inserting if step.get("button") == "right"]
    assert len(markers) == 2 and markers[0] != markers[1], markers
