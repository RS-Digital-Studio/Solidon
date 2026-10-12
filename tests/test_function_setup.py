"""Vorbereitung eines Funktionsfalls und die Fälle eines Laufs, ohne Fenster (D0-P, RM-737).

Profil, Lizenzläufe der Fassung, Vorbedingungen über die Nahtstellen der Suite,
Varianten und Spezifikation (``function_setup``); die Fälle, die
``file_acceptance`` aus Zeilen und Varianten auffaltet, Wiederaufnahme und
Bericht; der Weg einer Zeile, die eigene Szenenkopie je Fall und was ein
neuer Lauf nach einem Absturz wegräumt.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.bench_fakes import (
    ROWS,
)
from tools import (
    function_protocol,
    function_setup,
)
from tools.file_acceptance import (
    Case,
    function_cases,
    read_cases,
    resumes,
    summary,
    write_json,
)
from tools.function_checks import (
    COVERED,
    LICENCE_UNLOCKED,
    SMALLEST_WINDOW,
)
from tools.function_list import LICENCE_STATES, STARTUP_LICENCE, licence_states


def test_the_prepared_profile_is_what_the_application_reads_at_its_start() -> None:
    """Sprache, Thema, Einheit und Drucker kommen aus der Variante, Zuletzt-Liste dazu.

    Die Suite hat die Nutzerordner schon umgebogen (§38); geschrieben wird also
    in das Profil des Tests, gelesen mit ``load_settings`` wie beim Start.
    """
    from app.ui.settings import load_settings

    variant = function_setup.Variant.of(
        {"language": "en", "theme": "dark", "unit": "in", "preconditions": {"printer": "resin"}}
    )
    second = Path("scenes") / "zweites_projekt.p3d"
    function_setup.write_profile(variant, recent=[second])
    settings = load_settings()
    assert (settings.language, settings.theme, settings.display_unit) == ("en", "dark", "in")
    assert (settings.printer, settings.material) == function_setup.PRINTERS["resin"]
    assert settings.first_run_done is True and settings.check_for_updates is False
    assert settings.recent == [str(second)]
    assert settings.ai_disclosure_version == "", "der KI-Hinweis bleibt Teil des Kundenwegs"
    plain = function_setup.write_profile(function_setup.Variant())
    assert plain.is_file()
    settings = load_settings()
    assert (settings.language, settings.printer) == ("de", "centauri-carbon-2")


@pytest.mark.parametrize("trial_from", [None, date(2026, 12, 1)])
def test_each_licence_run_of_the_shipped_version_is_set_through_the_suites_seam(
    monkeypatch: pytest.MonkeyPatch, trial_from: date | None
) -> None:
    """Die Läufe sind die Zustände, die die Fassung erreicht (Entscheidung 12.10., Review S1).

    Ohne ``store.TRIAL_FROM`` (Verkaufsversion) ``sale_without_trial``, mit ihm
    ``expired``; dazu ``needs_activation`` und ``licensed``. Jeder ohne private
    Schlüssel über ``activation._cached``, und an dem gebauten Zustand gilt genau
    seine Eigenschaft — auch keine von ``over``. Gesperrt heißt: Die Grenze im
    Datenpfad wirft (``activation.require``), so wie U es erwartet
    (``LICENCE_UNLOCKED``). Der Satz ``lizenz`` liest die Läufe erst jetzt.
    """
    from app.core import activation
    from app.core.activation import store
    from app.core.errors import DeviceActivationRequired, LicenceRequired

    monkeypatch.setattr(activation, "_cached", activation._cached)
    monkeypatch.setattr(store, "DEMO_UNTIL", store.DEMO_UNTIL)
    monkeypatch.setattr(store, "TRIAL_FROM", trial_from)
    runs = licence_states()
    assert ("expired" in runs) is (trial_from is not None)
    assert {entry["licence"] for entry in function_setup.variant_sets()["lizenz"]} == set(runs)
    for state in runs:
        monkeypatch.setattr(store, "TRIAL_FROM", trial_from)
        cached = function_setup.apply_licence(state, date(2026, 10, 12))
        assert activation.state() is cached
        holding = {name for name in (*LICENCE_STATES, STARTUP_LICENCE) if getattr(cached, name)}
        assert holding == {state}, (state, holding)
        assert store.DEMO_UNTIL is None
        assert cached.unlocked is LICENCE_UNLOCKED[state]
        if LICENCE_UNLOCKED[state]:
            activation.require(activation.CHANGE)
        else:
            # Ein Kaufcode ohne Gerätefreigabe sperrt mit eigenem Weg hinaus.
            with pytest.raises((LicenceRequired, DeviceActivationRequired)):
                activation.require(activation.CHANGE)
    if trial_from is None:
        with pytest.raises(ValueError, match="TRIAL_FROM"):
            function_setup.apply_licence("expired", date(2026, 10, 12))


def test_the_expired_demo_is_the_start_case_and_no_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """``over`` ist kein Lauf je Funktion, sondern der Startfall der D12-Zeile (Review S1).

    Der Zustand trägt seinen Stichtag (gestern), und eine Variante mit ihm gibt
    es nur im Satz ``start``.
    """
    from app.core import activation
    from app.core.activation import store

    monkeypatch.setattr(activation, "_cached", activation._cached)
    monkeypatch.setattr(store, "DEMO_UNTIL", store.DEMO_UNTIL)
    cached = function_setup.apply_licence(STARTUP_LICENCE, date(2026, 10, 12))
    assert cached.over is True and cached.unlocked is False
    assert store.DEMO_UNTIL == cached.deadline == date(2026, 10, 11)
    assert STARTUP_LICENCE not in licence_states()
    with pytest.raises(ValueError, match="Startfall"):
        function_setup.Variant.of({"licence": STARTUP_LICENCE})
    with pytest.raises(ValueError, match="Startfall"):
        function_setup.Variant.of({"set": "start", "licence": "licensed"})
    start = function_setup.Variant.of({"set": "start", "licence": STARTUP_LICENCE})
    assert start.protocol(None, (0, 0))["licence"] == STARTUP_LICENCE
    assert function_setup.PHASES["start"] == ()


def test_missing_preconditions_go_through_the_seams_and_present_ones_are_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """„fehlt“ setzt die Nahtstellen der Suite; „vorhanden“ wird an der Maschine nachgesehen.

    In der Suite gibt es keinen gefundenen Slicer und kein Modell
    (``tests/conftest.py``) — „vorhanden“ verlangt, steht also ehrlich als
    „fehlt (Maschine)“ im Lauf, statt einen Fall zu behaupten, den es nicht gab.
    """
    from app.core import discover, tools
    from app.core.backends import llm, mesh

    monkeypatch.setattr(discover, "find_program", discover.find_program)
    monkeypatch.setattr(discover, "find_programs", discover.find_programs)
    monkeypatch.setattr(discover, "reachable", discover.reachable)
    monkeypatch.setattr(llm, "backends", llm.backends)
    monkeypatch.setattr(mesh, "reachable", mesh.reachable)
    applied = function_setup.apply_preconditions(
        {"slicer": "fehlt", "ki": "fehlt", "comfyui": "fehlt", "printer": "resin"}
    )
    assert applied == {"slicer": "fehlt", "ki": "fehlt", "comfyui": "fehlt", "printer": "resin"}
    assert tools.slicer_programs() == ()
    assert tuple(llm.backends()) == ()
    assert mesh.reachable(mesh.DEFAULT_COMFY_URL) is False
    assert function_setup.apply_preconditions({"slicer": "vorhanden"}) == {
        "slicer": "fehlt (Maschine)"
    }


def test_present_ai_and_a_missing_comfyui_are_read_the_way_the_application_reads_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """„KI vorhanden“ liest ``available`` als Eigenschaft (M2), ComfyUI fehlt an beiden Wegen (L1).

    Gegenprobe M2: Ein Backend-Doppel mit ``available`` als Eigenschaft —
    vorher stürzte ``available()`` an einem ``bool`` ab. Gegenprobe L1: Der
    Werkzeugdialog fragt ``discover.reachable``; nach „ComfyUI fehlt“ antwortet
    dort keine ComfyUI-Adresse mehr, jede andere wie vorher.
    """
    from app.core import discover
    from app.core.backends import llm, mesh

    class Backend:
        def __init__(self, ready: bool) -> None:
            self.ready = ready

        @property
        def available(self) -> bool:
            return self.ready

    monkeypatch.setattr(llm, "backends", lambda: (Backend(False), Backend(True)))
    assert function_setup.apply_preconditions({"ki": "vorhanden"}) == {"ki": "vorhanden"}
    monkeypatch.setattr(llm, "backends", lambda: (Backend(False),))
    assert function_setup.apply_preconditions({"ki": "vorhanden"}) == {"ki": "fehlt (Maschine)"}

    asked: list[str] = []

    def answers(url: str, seconds: float = 0.0) -> bool:
        asked.append(url)
        return True

    monkeypatch.setattr(discover, "reachable", answers)
    monkeypatch.setattr(mesh, "reachable", mesh.reachable)
    assert function_setup.apply_preconditions({"comfyui": "fehlt"}) == {"comfyui": "fehlt"}
    assert discover.reachable(mesh.DEFAULT_COMFY_URL) is False
    assert discover.reachable("127.0.0.1:8188") is False
    assert mesh.reachable(mesh.DEFAULT_COMFY_URL) is False
    assert discover.reachable("http://127.0.0.1:11434") is True
    assert asked == ["http://127.0.0.1:11434"]


def test_a_missing_exact_kernel_goes_through_the_suites_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """„OpenCASCADE fehlt“ wie in der Suite (``brep.kernel.available``): Ein exakter Schritt
    sagt danach mit *Zusätzliche Programme* ab; „vorhanden“ liest dieselbe Probe."""
    from app.core.brep import kernel

    monkeypatch.setattr(kernel, "available", kernel.available)
    present = kernel.available()
    assert function_setup.apply_preconditions({"opencascade": "vorhanden"}) == {
        "opencascade": "vorhanden" if present else "fehlt (Maschine)"
    }
    assert function_setup.apply_preconditions({"opencascade": "fehlt"}) == {"opencascade": "fehlt"}
    assert kernel.available() is False
    with pytest.raises(kernel.BRepUnavailable) as caught:
        kernel.require()
    assert caught.value.suggestions[0].id == "install"


def test_a_scene_says_what_the_bench_prepares_before_the_row() -> None:
    """Vorbedingungen, eigene Bausteine und die Klicks vor der Zeile kommen aus der Szene.

    Die Einfügemarke setzt das Kontextmenü des Verlaufs, *Automatisch teilen* der
    Befehl am Körper, der Export der Befehl samt Dateiname mit der Endung des
    Formats — jedes Ziel steht im Wortschatz.
    """
    from app.core.guides import is_target
    from tools.function_scenes import DATA

    assert function_setup.scene_setup("gibt_es_nicht") == function_setup.SceneSetup("gibt_es_nicht")
    assert function_setup.scene_setup("ohne_opencascade.exakt").preconditions == {
        "opencascade": "fehlt"
    }
    assert function_setup.scene_setup("erzeugte_haut.netz").preconditions == {
        "comfyui": "vorhanden"
    }
    assert function_setup.scene_setup("baustein_geaendert.netz").own_parts == (
        DATA / "recipes" / "werkstatt_halter_lokal.json",
    )
    folder = Path("fall") / "ausloeser"
    routes = {
        key: function_setup.preparation_route(function_setup.scene_setup(key), folder)
        for key in ("einfuegen.netz", "geschuetzte_leiste.netz", "export_gemischt", "quader.netz")
    }
    assert routes["einfuegen.netz"] == [
        {"target": "history.row:2", "button": "right"},
        {"target": "history:insert"},
    ]
    assert routes["geschuetzte_leiste.netz"] == [
        {"target": "tree.row:obj_1"},
        {"target": "command:edit.auto_split"},
    ]
    assert routes["export_gemischt"] == [
        {"target": "command:file.export"},
        {"key": "Ctrl+A"},
        {"type": str(folder / "szene.step")},
        {"key": "Return"},
    ]
    assert routes["quader.netz"] == []
    for route in routes.values():
        assert all(is_target(entry["target"]) for entry in route if "target" in entry)


def test_own_parts_lie_in_the_user_folder_before_the_application_starts() -> None:
    """Das Rezept der Szene liegt unter seinem Namen im Nutzerordner des Falls
    (``tests/conftest.py`` legt ihn in einen Temp-Ordner)."""
    from app.core.knowledge.parts import recipe

    setup = function_setup.scene_setup("baustein_geaendert.netz")
    (placed,) = function_setup.install_own_parts(setup)
    assert placed == recipe.recipes_dir() / "werkstatt_halter.json"
    assert placed.read_bytes() == setup.own_parts[0].read_bytes()
    assert function_setup.install_own_parts(function_setup.SceneSetup("quader.netz")) == []


def test_the_own_part_leaves_the_user_folder_with_its_test() -> None:
    """Das Rezept des Tests darüber reist nicht in den nächsten Test desselben Prozesses.

    Der Nutzerordner der Suite ist einer je Prozess, und ein Rezept darin hängt
    jedem folgenden ``results_cache_dir`` ein Kürzel an
    (``paths._own_parts_stamp``) — auch im gebauten Paket. Im parallelen Lauf
    war ``test_cache.py::test_a_built_package_needs_no_source_stamp`` deshalb
    rot, sobald derselbe Arbeiter vorher den Test darüber gefahren hatte.
    Gefahren wird genau diese Reihenfolge, in einem eigenen Prozess ohne xdist:
    Ein ``-n`` aus ``PYTEST_ADDOPTS`` verteilte die zwei Tests auf zwei
    Arbeiter, und die Reihenfolge wäre nicht mehr die geprüfte.
    """
    root = Path(__file__).resolve().parent.parent
    environment = {name: value for name, value in os.environ.items() if name != "PYTEST_ADDOPTS"}
    done = subprocess.run(
        [
            sys.executable,
            *("-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:xdist"),
            "tests/test_function_setup.py::"
            "test_own_parts_lie_in_the_user_folder_before_the_application_starts",
            "tests/test_cache.py::test_a_built_package_needs_no_source_stamp",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "2 passed" in done.stdout, done.stdout


def test_a_row_starting_in_a_scene_with_preconditions_runs_only_in_them() -> None:
    """Was die Startszene verlangt, gilt für jeden Fall der Zeile — ohne Gegenlauf:
    Ohne fehlendes OpenCASCADE gäbe es den Befund nicht, um den es geht."""
    row = {
        "id": "finding.action:install",
        "kind": "bedienflaeche",
        "source": "befundhandlung",
        "package": "D12",
        "start_scene": "ohne_opencascade.exakt",
    }
    cases = function_cases([row])
    assert cases and all(
        case.variant["preconditions"] == {"opencascade": "fehlt"} for case in cases
    )
    assert (
        function_cases([{**row, "start_scene": "quader.exakt"}])[0].variant["preconditions"] == {}
    )


def test_the_spec_sets_licence_and_preconditions_and_both_states_run() -> None:
    """Die Spezifikation legt Lizenz und Vorbedingungen fest; „fehlt“ und „vorhanden“ laufen beide.

    Die Spezifikation nennt Lizenzzustände mit den Namen von D0-L; der Prüfstand
    übersetzt nichts. Was die Fassung nicht erreicht, ist ein Fehler: das alte
    Wort „demo“, ein deutsches Wort, ``over`` (der Startfall) und der gesperrte
    Zustand, den diese Fassung nicht hat.
    """
    locked = licence_states()[0]
    base, others = function_setup.spec_variants(
        {"preconditions": {"licence": locked, "slicer": "vorhanden", "printer": "resin"}}
    )
    assert base == {
        "licence": locked,
        "preconditions": {"slicer": "vorhanden", "printer": "resin"},
    }
    assert others == [
        {"preconditions": {"slicer": "fehlt", "printer": "resin"}, "phases": ["main"]}
    ]
    assert function_setup.spec_variants(None) == ({}, [])
    assert function_setup.spec_licence("licensed") == "licensed"
    unreachable = next(state for state in LICENCE_STATES if state not in licence_states())
    for word in ("demo", "gekauft", STARTUP_LICENCE, unreachable):
        with pytest.raises(ValueError, match="keinen Lauf"):
            function_setup.spec_licence(word)


def test_a_variant_takes_only_states_the_bench_can_make() -> None:
    assert function_setup.Variant.of(None) == function_setup.Variant()
    for broken in (
        {"licence": "gekauft"},
        {"preconditions": {"slicer": "kaputt"}},
        {"preconditions": {"drucker": "filament"}},
        {"unit": "cm"},
        {"theme": "bunt"},
        {"window_size": "groß"},
        {"scale": 0},
        {"farbe": "rot"},
        {"set": "bunt"},
        {"phases": ["fliegen"]},
        {"set": "lizenz", "phases": ["main"]},
        {"licence": STARTUP_LICENCE},
    ):
        with pytest.raises(ValueError):
            function_setup.Variant.of(broken)
    variant = function_setup.Variant.of(
        {"window_size": "1920x1032", "scale": 1.5, "phases": ["main"]}
    )
    assert function_setup.parse_size(variant.window_size) == (1920, 1032)
    assert variant.phases == ("main",)
    assert function_setup.Variant.of(variant.as_dict()) == variant
    sets = function_setup.variant_sets()
    assert set(function_setup.PHASES) == {*sets, "start"}
    assert {entry.get("licence") for entry in sets["lizenz"]} == set(licence_states())
    assert {entry.get("window_size") for entry in sets["skalierung"]} >= set(
        function_setup.WINDOW_SIZES
    )
    assert sets["bewegung"] == ({"set": "bewegung", "motion": False},)


def test_function_cases_unfold_rows_variants_and_languages() -> None:
    """Je Zeile und Variante ein Fall, je Sprache und Paket einer; fremde Kennung ist ein Fehler."""
    cases = function_cases(
        ROWS,
        packages=["D4"],
        variant_sets=["basis", "lizenz", "sprachen"],
        languages=("de", "en"),
        first_number=5,
    )
    function = [case for case in cases if case.kind == "function"]
    language = [case for case in cases if case.kind == "language"]
    assert [case.number for case in cases] == list(range(5, 5 + len(cases)))
    # basis: resize_hole einmal, drill_hole zweimal (Slicer vorhanden und fehlt); lizenz: je
    # einer je Lauf der Fassung.
    assert len(function) == 1 + 2 + 2 * len(licence_states())
    slicer = [case.variant["preconditions"] for case in function if case.row == "drill_hole"]
    assert {"slicer": "vorhanden"} in slicer and {"slicer": "fehlt"} in slicer
    assert [(case.row, case.variant["language"]) for case in language] == [
        ("D4", "de"),
        ("D4", "en"),
    ]
    first = function[0]
    assert first.path == "scenes/merkmal.hole.exakt.p3d" and first.variant["set"] == "basis"
    assert {case.variant["licence"] for case in function if case.variant["set"] == "lizenz"} == set(
        licence_states()
    )
    assert function_cases(ROWS, row_ids=["finding.action:place_on_bed"])[0].row == (
        "finding.action:place_on_bed"
    )
    again = function_cases(ROWS, row_ids=["resize_hole"], phases=["escape", "main"])
    assert [case.variant["phases"] for case in again] == [["escape", "main"]]
    with pytest.raises(ValueError, match="Phasen"):
        function_cases(ROWS, row_ids=["resize_hole"], variant_sets=["lizenz"], phases=["main"])
    # Review L5: Phasen gelten nur für Sätze, die sie haben; der Lizenzsatz fällt weg.
    mixed = function_cases(
        ROWS, row_ids=["resize_hole"], variant_sets=["basis", "lizenz"], phases=["main"]
    )
    assert [(case.variant["set"], case.variant["phases"]) for case in mixed] == [
        ("basis", ["main"])
    ]
    # Die Zeile des Startablaufs ist ein Startfall, einmal, im Zustand „Demo abgelaufen“.
    started = function_cases(ROWS, packages=["D12"], variant_sets=["basis", "lizenz", "dunkel"])
    assert [
        (case.kind, case.row, case.variant["set"], case.variant["licence"]) for case in started
    ] == [("start", "startup.expired_demo", "start", STARTUP_LICENCE)]
    with pytest.raises(ValueError, match="keine Zeile"):
        function_cases(ROWS, row_ids=["gibt_es_nicht"])
    with pytest.raises(ValueError, match="Variantensätze"):
        function_cases(ROWS, variant_sets=["basis", "bunt"])


def test_old_cases_stay_file_cases_and_new_ones_keep_their_fields(tmp_path: Path) -> None:
    """Ein ``cases.json`` von RM-184 ohne die neuen Felder liest sich als Dateifälle."""
    write_json(
        tmp_path / "cases.json",
        [
            {
                "number": 1,
                "relative": "a.stl",
                "path": "F:/x/a.stl",
                "suffix": ".stl",
                "bores": False,
            }
        ],
    )
    (old,) = read_cases(tmp_path)
    assert (old.kind, old.row, old.variant) == ("file", "", {})
    new = function_cases(ROWS, row_ids=["resize_hole"])[0]
    write_json(tmp_path / "cases.json", [asdict(new)])
    assert read_cases(tmp_path) == [new]


def test_only_a_broken_language_case_resumes_without_again() -> None:
    """Ein Sprachfall nimmt seine Flächen einzeln wieder auf, andere Fälle nur mit ``--again``."""
    language = Case(1, "D4 [de]", "", "", kind="language", row="D4")
    function = Case(2, "resize_hole [basis]", "", "", kind="function", row="resize_hole")
    assert resumes(language, {"exit_code": 1, "timeout": False})
    assert resumes(language, {"exit_code": 0, "timeout": True})
    assert not resumes(language, {"exit_code": 0, "timeout": False})
    assert not resumes(function, {"exit_code": 1, "timeout": False})


def test_a_run_starts_only_what_is_not_done_and_hands_on_the_screen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wiederaufnahme wie bei RM-184: Fertige Fälle bleiben liegen, ``--again`` fährt alle neu.

    Der Kindprozess ist nachgestellt; geprüft wird, welche Fälle ``run`` startet,
    mit welcher Frist und ob ``--screen`` beim Kind ankommt.
    """
    from tools import file_acceptance

    cases = [
        Case(1, "a.stl", "F:/x/a.stl", ".stl"),
        Case(2, "resize_hole [basis]", "", "", kind="function", row="resize_hole"),
        Case(3, "D4 [de]", "", "", kind="language", row="D4"),
        Case(4, "D4 [en]", "", "", kind="language", row="D4"),
    ]
    write_json(tmp_path / "cases.json", [asdict(case) for case in cases])
    for number, code in ((1, 0), (2, 0), (3, 1), (4, 0)):
        write_json(
            tmp_path / "cases" / f"{number:03d}" / "process.json",
            {"exit_code": code, "timeout": False, "wall_s": 1.0},
        )
    started: list[tuple[str, float, list[str]]] = []

    class Child:
        def __init__(self, command: list[str], **_options: object) -> None:
            self.command = command
            self.pid = 4711

        def wait(self, timeout: float | None = None) -> int:
            number = self.command[self.command.index("--case") + 1]
            started.append((number, float(timeout or 0.0), self.command))
            return 0

    monkeypatch.setattr(file_acceptance.subprocess, "Popen", Child)
    assert file_acceptance.run(tmp_path, 1, 99, False, 600.0, screen="MSI") == 0
    assert [(number, timeout) for number, timeout, _command in started] == [
        ("3", file_acceptance.LANGUAGE_CASE_TIMEOUT)
    ]
    assert started[0][2][-2:] == ["--screen", "MSI"]
    started.clear()
    assert file_acceptance.run(tmp_path, 1, 99, True, 600.0) == 0
    assert [(number, timeout) for number, timeout, _command in started] == [
        ("1", 600.0),
        ("2", file_acceptance.FUNCTION_CASE_TIMEOUT),
        ("3", file_acceptance.LANGUAGE_CASE_TIMEOUT),
        ("4", file_acceptance.LANGUAGE_CASE_TIMEOUT),
    ]
    assert all("--screen" not in command for _number, _timeout, command in started)


def test_the_report_lists_function_cases_beside_the_file_cases(tmp_path: Path) -> None:
    """Der Lauf steht in ``bench.json``, die Messung im Protokoll — die Übersicht liest beide."""
    cases = [
        Case(1, "plate.stl", "F:/x/plate.stl", ".stl"),
        Case(
            2,
            "resize_hole [basis]",
            "scenes/merkmal.hole.exakt.p3d",
            "",
            kind="function",
            row="resize_hole",
            variant={"set": "basis"},
        ),
        Case(3, "D4 [en]", "", "", kind="language", row="D4", variant={"set": "sprachen"}),
    ]
    folder = tmp_path / "cases"
    write_json(folder / "002" / "bench.json", {"stage": "done"})
    write_json(
        folder / "002" / "function.json",
        {"findings": [{"kind": COVERED}], "unmeasured": {"abort": "x"}, "errors": []},
    )
    write_json(folder / "002" / "process.json", {"exit_code": 0, "timeout": False, "wall_s": 41.0})
    write_json(folder / "003" / "bench.json", {"stage": "start", "harness_exception": "Abriss"})
    write_json(folder / "003" / "surfaces" / "resize_hole.json", {"errors": [], "findings": []})
    write_json(folder / "003" / "process.json", {"exit_code": 139, "timeout": False, "wall_s": 9.0})
    data = summary(tmp_path, cases)
    assert (
        data["cases"],
        data["function_cases"],
        data["function_ran"],
        data["function_complete"],
    ) == (1, 2, 2, 1)
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "| 2 | resize_hole [basis] | function | basis | done | 0 | 41.0 | 1 | 1 |" in text
    assert "- 3 D4 [en]: Abriss" in text
    written = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert written["functions"][1]["exit_code"] == 139


def test_route_apply_target_and_command_line_come_from_the_row() -> None:
    row = {
        "target": "menu:tree.rename",
        "route": [{"target": "tree.row:obj_1", "button": "left", "modifier": ""}],
        "spec": {"route": [{"target": "tree.row:obj_2", "button": "left", "modifier": "ctrl"}]},
    }
    assert function_setup.route_of(row) == [
        ("tree.row:obj_1", "left"),
        ("tree.row:obj_2", "ctrl+left"),
        ("menu:tree.rename", "left"),
    ]
    assert function_setup.route_of({"target": "feature:resize_hole"}) == [
        ("feature:resize_hole", "left")
    ]
    feature_row = {
        "target": "operation:resize_hole",
        "route": [{"target": "tree.row:obj_1.hole_1", "button": "left", "modifier": ""}],
        "spec": {"inputs": {"feature.field:resize_hole.diameter": 8.0}},
    }
    # Eine Merkmalsoperation findet der Kunde an der Auswahl als Handlung, nicht im
    # Kontextmenü: Der Hauptweg führt zu ihrem Kopf, übernommen wird dort.
    assert function_setup.walk_target(feature_row) == "feature:resize_hole"
    assert function_setup.route_of(feature_row)[-1] == ("feature:resize_hole", "left")
    assert function_setup.default_apply_target(feature_row) == "feature.apply"
    dialog_row = {"target": "operation:drill_hole", "spec": {"inputs": {"field:diameter": 5}}}
    assert function_setup.walk_target(dialog_row) == "operation:drill_hole"
    assert function_protocol.protocol_spec({"inputs": {}, "file": "d04.toml", "package": "D4"}) == {
        "inputs": {}
    }
    assert function_protocol.protocol_spec(None) is None
    assert function_setup.selected_feature(ROWS[0]) == ("obj_1", "hole_1")
    assert function_setup.selected_feature(ROWS[1]) is None
    assert function_setup.default_apply_target({"target": "feature:resize_hole"}) == "feature.apply"
    assert function_setup.default_apply_target({"target": "edge:fillet_edges"}) == "feature.apply"
    assert (
        function_setup.default_apply_target({"target": "operation:drill_hole"}) == "dialog.accept"
    )
    assert function_setup.default_apply_target({"target": "menu:menubar.datei.speichern"}) is None
    assert function_protocol.cli_arguments(
        {
            "op": "drill_hole",
            "in": ["obj_1"],
            "params": {"diameter": 5.2, "axis": "z", "slotted": False},
        }
    ) == ["drill_hole", "--on", "obj_1", "--diameter", "5.2", "--axis", "z", "--no-slotted"]
    assert (
        function_protocol.cli_arguments({"op": "pattern", "params": {"points": [[0, 0]]}}) is None
    )
    named = function_protocol.safe_name("Datei/Speichern unter …")
    assert named.startswith("Datei_Speichern_unter-")
    # Review L4: zwei Kennungen, die sich nur im Zeichen danach unterscheiden.
    assert named != function_protocol.safe_name("Datei/Speichern unter")
    assert function_protocol.bodies_digest({"b": "2", "a": "1"}) == function_protocol.bodies_digest(
        {"a": "1", "b": "2"}
    )


def test_each_case_opens_its_own_copy_of_a_shared_scene(tmp_path: Path) -> None:
    """Review M6: Die gemeinsame Szene unter ``<out>/scenes`` wird nie selbst geöffnet."""
    scenes = tmp_path / "scenes"
    scenes.mkdir()
    (scenes / "quader.exakt.p3d").write_bytes(b"szene")
    folder = tmp_path / "cases" / "007"
    copy = function_setup.case_scene(folder, scenes, "quader.exakt")
    assert copy == folder / "scenes" / "quader.exakt.p3d" and copy.read_bytes() == b"szene"
    copy.write_bytes(b"geaendert")
    assert function_setup.case_scene(folder, scenes, "quader.exakt") == copy
    assert copy.read_bytes() == b"geaendert", "einmal angelegt, dann die eigene"
    assert (scenes / "quader.exakt.p3d").read_bytes() == b"szene"
    assert function_setup.case_scene(folder, scenes, "gibt_es_nicht") is None


def test_a_failed_preparation_lands_in_the_case_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review L8: Scheitert Lizenz oder Vorbedingung, steht der Grund in ``bench.json``.

    Vorher standen Profil, Lizenz, Vorbedingungen und Fensterbau vor dem
    ``try`` — ``bench.json`` blieb auf ``start``, die Übersicht nannte keinen Grund.
    """
    from tools import file_acceptance

    monkeypatch.setattr(file_acceptance, "version_info", lambda: {"commit": "", "app": ""})

    def refuses(state: str, today: Any = None) -> Any:
        raise RuntimeError("Lizenz ließ sich nicht setzen")

    monkeypatch.setattr(function_setup, "apply_licence", refuses)
    out = tmp_path / "lauf"
    write_json(out / "rows.json", [ROWS[0]])
    case = function_cases(ROWS, row_ids=["resize_hole"])[0]
    folder = out / "cases" / "001"
    folder.mkdir(parents=True)
    code = file_acceptance.function_child(out, case, folder, "")
    state = json.loads((folder / "bench.json").read_text(encoding="utf-8"))
    assert code == 1 and state["stage"] == "start" and state["shutdown_complete"] is True
    assert "Lizenz ließ sich nicht setzen" in state["harness_exception"]


def test_a_case_run_again_starts_without_the_copies_and_backups_of_its_last_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review N2: ``--again`` nach einem Absturz öffnet eine frische Kopie, ohne alte Sicherung.

    Nachgestellt ist der Fall nach dem Absturz: Die Kopie der zweiten Szene ist
    verändert, daneben liegt ihre ``.autosave``, im Profil die Sicherung eines
    namenlosen Projekts. Vorher öffnete der neue Lauf dieselbe Kopie samt
    Sicherung und stand an der Wiederherstellungsfrage. Die Lizenz scheitert
    absichtlich, damit der Lauf nach der Vorbereitung endet.
    """
    from tools import file_acceptance

    monkeypatch.setattr(file_acceptance, "version_info", lambda: {"commit": "", "app": ""})

    def refuses(state: str, today: Any = None) -> Any:
        raise RuntimeError("Lauf endet hier")

    monkeypatch.setattr(function_setup, "apply_licence", refuses)
    out = tmp_path / "lauf"
    write_json(out / "rows.json", [ROWS[0]])
    shared = out / "scenes" / f"{function_setup.SECOND_SCENE}.p3d"
    shared.parent.mkdir(parents=True)
    shared.write_bytes(b"frisch")
    case = function_cases(ROWS, row_ids=["resize_hole"])[0]
    folder = out / "cases" / "001"
    copy = folder / "scenes" / shared.name
    copy.parent.mkdir(parents=True)
    copy.write_bytes(b"vom abgestuerzten Lauf")
    copy.with_name(copy.name + ".autosave").write_bytes(b"sicherung")
    unsaved = folder / "profile" / "Solidon3D" / "recovery" / "unsaved-1a2b3c4d.p3d.autosave"
    unsaved.parent.mkdir(parents=True)
    unsaved.write_bytes(b"sicherung")
    settings = folder / "profile" / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    file_acceptance.function_child(out, case, folder, "")
    assert copy.read_bytes() == b"frisch", "die Kopie ist neu"
    assert not list(folder.rglob("*.autosave")), "keine Sicherung des vorigen Laufs"
    assert settings.is_file(), "Einstellungen bleiben"
    state = json.loads((folder / "bench.json").read_text(encoding="utf-8"))
    assert f"scenes/{shared.name}.autosave" in state["cleared"]
    assert "profile/Solidon3D/recovery/unsaved-1a2b3c4d.p3d.autosave" in state["cleared"]


def test_a_screen_that_matches_none_is_an_error_not_another_screen() -> None:
    """Review L14: ``--screen`` ohne Treffer fällt nicht still auf einen anderen Schirm zurück."""

    class Screen:
        def __init__(self, name: str) -> None:
            self.label = name

        def name(self) -> str:
            return self.label

        def model(self) -> str:
            return ""

        def manufacturer(self) -> str:
            return ""

    class Application:
        def screens(self) -> list[Screen]:
            return [Screen("Haupt"), Screen("MSI")]

        def primaryScreen(self) -> Screen:  # noqa: N802 - Qts Name
            return self.screens()[0]

    with pytest.raises(ValueError, match="trifft keinen Schirm"):
        function_setup.place_window(
            Application(), None, function_setup.Variant.of({"screen": "Mond"})
        )
    with pytest.raises(ValueError, match="trifft keinen Schirm"):
        function_setup.place_window(Application(), None, function_setup.Variant.of({"screen": "7"}))


def test_nothing_is_measured_below_the_smallest_screen() -> None:
    """Befund C (Festlegung Robert): 1920 × 1080 logisch ist die Untergrenze, drunter nie.

    Ist der Schirm kleiner als die kleinste Fensterfläche (offscreen 800 × 800),
    nimmt das Fenster sie an, statt kleiner zu messen; ein größerer Schirm
    bleibt maximiert. Eine Skalierung, die die logische Fläche darunter drückt,
    ist kein Fall — 150 % auf 2560 × 1440 (1707 × 928), nicht aber 200 % auf
    3840 × 2160 (1920 × 1056).
    """
    from PySide6.QtCore import QRect

    class Screen:
        def __init__(self, width: int, height: int) -> None:
            self.size = (width, height)

        def name(self) -> str:
            return "Schirm"

        def model(self) -> str:
            return ""

        def availableGeometry(self) -> QRect:  # noqa: N802 - Qts Name
            return QRect(0, 0, *self.size)

        def devicePixelRatio(self) -> float:  # noqa: N802 - Qts Name
            return 1.0

    class Application:
        def __init__(self, screen: Screen) -> None:
            self.screen = screen

        def screens(self) -> list[Screen]:
            return [self.screen]

        def primaryScreen(self) -> Screen:  # noqa: N802 - Qts Name
            return self.screen

    class Window:
        def __init__(self) -> None:
            self.calls: list[tuple[str, Any]] = []

        def resize(self, width: int, height: int) -> None:
            self.calls.append(("resize", (width, height)))

        def move(self, point: Any) -> None:
            self.calls.append(("move", (point.x(), point.y())))

        def show(self) -> None:
            self.calls.append(("show", None))

        def setGeometry(self, area: QRect) -> None:  # noqa: N802 - Qts Name
            self.calls.append(("geometry", (area.width(), area.height())))

        def showMaximized(self) -> None:  # noqa: N802 - Qts Name
            self.calls.append(("maximized", None))

    small, large = Window(), Window()
    function_setup.place_window(Application(Screen(800, 800)), small, function_setup.Variant())
    assert ("resize", SMALLEST_WINDOW) in small.calls and ("maximized", None) not in small.calls
    function_setup.place_window(Application(Screen(2560, 1392)), large, function_setup.Variant())
    assert ("maximized", None) in large.calls
    scaled = function_setup.Variant.of({"set": "skalierung", "scale": 1.5})
    reason = function_setup.below_smallest({"screen": "MSI", "geometry": [0, 0, 1707, 928]}, scaled)
    assert "kein Fall" in reason and "1707 x 928" in reason
    doubled = function_setup.Variant.of({"set": "skalierung", "scale": 2.0})
    assert function_setup.below_smallest({"geometry": [0, 0, 1920, 1056]}, doubled) == ""
    assert (
        function_setup.below_smallest({"geometry": [0, 0, 796, 796]}, function_setup.Variant())
        == ""
    )
    assert function_setup.WINDOW_SIZES == ("1920x1032",)


def test_a_menubar_child_that_never_answers_is_a_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review L6: Hängt der Kindprozess der Menüleiste, kommt eine Meldung, kein Stapel."""
    import subprocess

    from tools import file_acceptance

    def hangs(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd="menubar", timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(file_acceptance.subprocess, "run", hangs)
    with pytest.raises(RuntimeError, match="antwortete"):
        file_acceptance.menubar(tmp_path)
