"""Ein Sprachfall je Einrichtung der Startszenen (FD-101, RM-737).

Ein Sprachfall geht alle Flächen eines Pakets in einem Prozess ab. Vorbedingungen
einer Startszene (``opencascade = fehlt``) und eigene Bausteine im Nutzerordner
wendete nur der Funktionsfall an; im Sprachfall fanden *Installieren* und
*Gespeicherte Bausteine behalten* ihren Befund nie („der Prüfbericht zeigt
keinen Befund mit dieser Kennung“, Lauf 043). Jetzt laufen solche Zeilen in einem
eigenen Sprachfall, der die Einrichtung ab seinem Start trägt.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from tools import file_acceptance, function_list
from tools.function_setup import Variant

INSTALL = "finding.action:install"
KEEP = "finding.action:keep_saved_parts"


@pytest.fixture(scope="module")
def rows() -> list[dict[str, Any]]:
    return [asdict(row) for row in function_list.rows()]


def test_rows_whose_scenes_need_a_setup_run_in_their_own_language_case(
    rows: list[dict[str, Any]],
) -> None:
    from tools import function_cases

    groups = function_cases.language_groups(row for row in rows if row["package"] == "D8")
    keys = [setup.key for setup in groups["D8"]]
    assert keys[0] == "", keys
    by_id = {row["id"]: row for row in rows}
    install = function_cases.setup_of(by_id[INSTALL])
    keep = function_cases.setup_of(by_id[KEEP])
    assert dict(install.preconditions) == {"opencascade": "fehlt"}
    assert keep.user_data and not keep.preconditions
    assert {install.key, keep.key} <= set(keys)
    # Die Zeilen des Pakets ohne Einrichtung bleiben unter seiner Kennung.
    plain = function_cases.rows_of(rows, "D8")
    assert by_id["finding.action:place_on_bed"] in plain
    assert by_id[INSTALL] not in plain and by_id[KEEP] not in plain
    assert function_cases.rows_of(rows, function_cases.case_row("D8", install)) == [
        row for row in rows if row["package"] == "D8" and function_cases.setup_of(row) == install
    ]


def test_the_language_case_of_a_setup_carries_its_preconditions(
    rows: list[dict[str, Any]],
) -> None:
    """Die Vorbedingung steht in der Variante des Falls; ``child`` wendet sie vor dem Start an."""
    cases = file_acceptance.function_cases(
        rows, packages=["D8"], variant_sets=["sprachen"], languages=["de"]
    )
    by_row = {case.row: case for case in cases}
    assert "D8" in by_row and Variant.of(by_row["D8"].variant).preconditions == {}
    own = [row for row in by_row if row.startswith("D8@")]
    assert own, sorted(by_row)
    missing = next(case for row, case in by_row.items() if "opencascade=fehlt" in row)
    assert Variant.of(missing.variant).preconditions == {"opencascade": "fehlt"}
    assert all(case.kind == "language" for case in cases)


def test_spools_of_a_scene_lie_in_the_store_of_the_case_before_it_starts(
    rows: list[dict[str, Any]],
) -> None:
    """Eine Spule im Lager ändert jede Fläche, die das Lager zeigt: Die Zeilen ihrer Szene
    laufen in einem eigenen Sprachfall, und die Spule liegt vor dem Start im Lager
    des Falls — im Profil der Suite, nie im Nutzerordner des Kunden (FD-101)."""
    from app.core.knowledge import filaments
    from tools import function_cases

    by_id = {row["id"]: row for row in rows}
    setup = function_cases.setup_of(by_id["meldung:_replacement_slot"])
    assert setup.key == "nutzerdaten:sieben_filamente.netz"
    assert setup.user_data == ("sieben_filamente.netz",)
    assert all(spool.name != "PETG Rot" for spool in filaments.catalogue())
    placed = function_cases.install_user_data("sieben_filamente.netz")
    assert placed == [str(filaments.catalogue_path())]
    assert [spool.name for spool in filaments.catalogue()].count("PETG Rot") == 1


def test_the_preconditions_of_the_spec_join_the_setup_of_the_language_case(
    rows: list[dict[str, Any]],
) -> None:
    """Eine Vorbedingung der Spezifikation gilt im Sprachfall wie im Funktionsfall:
    Der Druckhinweis lief im Sprachfall nie offen, eine Zeile ohne KI mit ihr.
    Lizenz und Druckart bilden keine Einrichtung — die prüfen eigene Läufe —,
    ebenso was jeder Fall ohnehin hat, und die Szene geht der Spezifikation vor
    (FD-101, FD-121)."""
    from tools import function_cases

    by_id = {row["id"]: row for row in rows}
    hint = function_cases.setup_of(by_id["dialog:print_disclosure_dialog"])
    assert (hint.key, dict(hint.preconditions)) == (
        "druckhinweis=offen",
        {"druckhinweis": "offen"},
    )
    row = {**by_id["parameters.bind"]}
    assert function_cases.setup_of(row).key == ""
    row["spec"] = {
        **(row.get("spec") or {}),
        "preconditions": {"ki": "fehlt", "licence": "licensed", "printer": "resin"},
    }
    setup = function_cases.setup_of(row)
    assert (setup.key, dict(setup.preconditions)) == ("ki=fehlt", {"ki": "fehlt"})
    # Gegenprobe: Den Slicer der Maschine hat jeder Fall — kein eigener Prozess.
    row["spec"] = {**row["spec"], "preconditions": {"slicer": "vorhanden"}}
    assert function_cases.setup_of(row).key == ""
    assert function_cases.setup_of(by_id["dialog:slicer_filament_dialog"]).key == ""
    # Ohne OpenCASCADE sagt die Startszene; die Spezifikation ändert daran nichts.
    install = {**by_id[INSTALL]}
    install["spec"] = {**(install.get("spec") or {}), "preconditions": {"opencascade": "vorhanden"}}
    assert dict(function_cases.setup_of(install).preconditions) == {"opencascade": "fehlt"}


@pytest.mark.windowed
def test_the_language_case_of_own_parts_finds_their_finding(
    rows: list[dict[str, Any]], tmp_path: Path
) -> None:
    """Ende zu Ende im eigenen Prozess: Der Baustein liegt vor dem Start im Nutzerordner,
    die Anwendung liest ihn wie ``app.main`` (``load_user_parts``), und die Fläche von
    *Gespeicherte Bausteine behalten* wird erreicht — vorher „der Prüfbericht zeigt
    keinen Befund mit dieser Kennung“."""
    import os
    import subprocess
    import sys

    from tools import function_cases, function_scenes
    from tools.file_acceptance import ROOT, write_json

    by_id = {row["id"]: row for row in rows}
    setup = function_cases.setup_of(by_id[KEEP])
    case_row = function_cases.case_row("D8", setup)
    chosen = function_cases.rows_of(rows, case_row)
    assert [row["id"] for row in chosen] == [KEEP]
    out = tmp_path / "abnahme"
    (out / "scenes").mkdir(parents=True)
    scene = by_id[KEEP]["start_scene"]
    catalogue = function_scenes.load_scenes()
    # Unverändert geöffnet wie in ``save_scenes``: Neu gespeichert trüge die Datei den
    # Abdruck ihres Bausteins von heute, und der Befund wäre weg.
    assert function_scenes._opened_as_is(catalogue[scene])
    source = function_scenes.DATA / catalogue[scene].opens
    (out / "scenes" / f"{scene}.p3d").write_bytes(source.read_bytes())
    write_json(out / "rows.json", chosen)
    variant = Variant.of({"set": "sprachen", "language": "de"})
    case = file_acceptance.Case(
        1, f"{case_row} [de]", "", "", kind="language", row=case_row, variant=variant.as_dict()
    )
    write_json(out / "cases.json", [asdict(case)])
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONUTF8": "1"}
    script = str(ROOT / "tools" / "file_acceptance.py")
    finished = subprocess.run(
        [sys.executable, script, "child", "--out", str(out), "--case", "1"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        check=False,
    )
    assert finished.returncode == 0, (finished.stdout, finished.stderr)
    import json

    folder = out / "cases" / "001"
    state = json.loads((folder / "bench.json").read_text(encoding="utf-8"))
    assert state["stage"] == "done", state.get("harness_exception")
    assert state["user_data"], "der Baustein lag nicht im Nutzerordner"
    protocol = next(
        json.loads(path.read_text(encoding="utf-8"))
        for path in (folder / "surfaces").glob("*.json")
        if not path.stem.endswith("-vorher")
    )
    assert protocol["findings"] == [], protocol["findings"]
    assert any(
        step.get("target") == KEEP and step.get("why") == "ziel" for step in protocol["steps"]
    ), protocol["steps"]


def test_the_start_row_runs_as_a_start_case_in_every_language(
    rows: list[dict[str, Any]],
) -> None:
    """Die Startzeile läuft im Satz ``sprachen`` je Sprache als Startfall (FD-175).

    Ihre Fläche zeigt ``main`` vor dem Hauptfenster. Ein Sprachfall erreicht sie
    nicht, und gefahren wurde sie nur im Satz ``basis`` — auf Deutsch.
    """
    from tools import function_cases
    from tools.function_list import STARTUP_LICENCE, STARTUP_ROW

    spoken = ("de", "en", "fr")
    cases = function_cases.language_cases(rows, {"D12"}, spoken, 1)
    starts = [case for case in cases if case.kind == "start"]
    assert [(case.row, case.variant["language"], case.variant["licence"]) for case in starts] == [
        (STARTUP_ROW, language, STARTUP_LICENCE) for language in spoken
    ]
    assert {Variant.of(case.variant).set for case in starts} == {"start"}
    walked = [case for case in cases if case.kind == "language"]
    assert walked
    for case in walked:
        assert STARTUP_ROW not in [row["id"] for row in function_cases.rows_of(rows, case.row)]
    assert [case.number for case in cases] == list(range(1, len(cases) + 1))


def test_the_licence_of_the_spec_is_the_licence_of_its_language_case() -> None:
    """Ein Fenster, das nur ein Lizenzzustand zeigt, misst der Sprachfall in diesem (FD-175).

    *Offline aktivieren …* steht nur, solange ein Kaufcode auf die Freischaltung
    dieses Rechners wartet. Jeder Sprachfall lief freigeschaltet, und der Dateiweg
    der Aktivierung hatte in keiner Sprache eine Fläche.
    """
    from tools import function_cases

    row = {
        "id": "dialog:offline_activation_dialog",
        "package": "D12",
        "start_scene": "leer",
        "spec": {"preconditions": {"licence": "needs_activation"}},
    }
    setup = function_cases.setup_of(row)
    assert (setup.key, setup.licence) == ("licence=needs_activation", "needs_activation")
    (case,) = function_cases.language_cases([row], {"D12"}, ("de",), 1)
    assert case.variant["licence"] == "needs_activation"
    assert case.row == "D12@licence=needs_activation"
    licensed = function_cases.setup_of({**row, "spec": {"preconditions": {"licence": "licensed"}}})
    assert (licensed.key, licensed.licence) == ("", "")
