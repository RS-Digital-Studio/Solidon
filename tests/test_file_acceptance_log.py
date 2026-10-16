"""Ein Fallprozess schreibt das Dateiprotokoll der Anwendung in sein Profil (FD-163, RM-737).

Nur ``app.main`` richtete das Dateiprotokoll ein; die Prozesse des Prüfstands
(``file_acceptance.child``) schrieben keins. Die Wartezeile des Abbaus aus FD-154
und jede Warnung der Auswertung standen deshalb in keinem Protokoll eines Falls.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from tools import file_acceptance, function_list, function_scenes
from tools.function_setup import Variant

#: Eine Zeile, deren Startszene hält: Die Auswertung schreibt ``evaluation stopped``.
ROW = "dialog:step_values_dialog"


@pytest.mark.windowed
def test_a_case_process_writes_the_application_log_into_its_profile(tmp_path: Path) -> None:
    rows = {row.id: asdict(row) for row in function_list.rows()}
    row = rows[ROW]
    scene = (row.get("spec") or {}).get("start_scene") or row["start_scene"]
    catalogue = function_scenes.load_scenes()
    assert catalogue[scene].promises.get("stops"), "Voraussetzung: die Startszene hält an"
    assert function_scenes._opened_as_is(catalogue[scene])
    out = tmp_path / "abnahme"
    (out / "scenes").mkdir(parents=True)
    source = function_scenes.DATA / catalogue[scene].opens
    (out / "scenes" / f"{scene}.p3d").write_bytes(source.read_bytes())
    file_acceptance.write_json(out / "rows.json", [row])
    case = file_acceptance.Case(
        1,
        f"{row['package']} [de]",
        "",
        "",
        kind="language",
        row=str(row["package"]),
        variant=Variant.of({"set": "sprachen", "language": "de"}).as_dict(),
    )
    file_acceptance.write_json(out / "cases.json", [asdict(case)])
    script = str(file_acceptance.ROOT / "tools" / "file_acceptance.py")
    finished = subprocess.run(
        [sys.executable, script, "child", "--out", str(out), "--case", "1"],
        cwd=file_acceptance.ROOT,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        check=False,
    )
    assert finished.returncode == 0, (finished.stdout, finished.stderr)
    profile = out / "cases" / "001" / "profile"
    state = json.loads((out / "cases" / "001" / "bench.json").read_text(encoding="utf-8"))
    assert state["stage"] == "done", state.get("harness_exception")
    logs = sorted(profile.rglob("app.log"))
    assert logs, sorted(path.relative_to(profile).as_posix() for path in profile.rglob("*"))
    text = logs[0].read_text(encoding="utf-8")
    assert "evaluation stopped" in text, text[-2000:]
