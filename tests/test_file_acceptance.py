"""Die Logik der nativen Einzeldateiabnahme — ohne Fenster (RM-184).

``tools/file_acceptance.py`` fährt jeden Fall im echten Fenster; das ist
Releasearbeit. Was davor und danach geschieht — Bestand, Wahl des Merkmals,
neue Zahl, Abgleich der Netzabdrücke, Bericht —, ist reine Rechnung und wird
hier an Fällen mit bekanntem Ausgang geprüft.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

from app.ui.main_window import MainWindow
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window
from tools.file_acceptance import (
    MOST_FEATURE_TRIES,
    NO_LENGTH_FIELD,
    REFUSED,
    ROOT,
    STEPS,
    UNCHANGEABLE,
    Case,
    bore_ids,
    case_stage,
    cases_from_manifest,
    cases_from_source,
    changed_value,
    choose_feature,
    compared,
    first_with_a_length_field,
    group_anchors,
    mesh_digest,
    outside_the_repository,
    passed,
    ranked_features,
    size_field_first,
    summary,
    values_to_try,
    write_json,
)


def test_the_inventory_counts_like_the_audit(tmp_path: Path) -> None:
    """Modelle und Projekte, Sicherungen als Kopie, Archivmitglieder hinten — Text nicht."""
    source = tmp_path / "quelle"
    (source / "ordner").mkdir(parents=True)
    (source / "a.stl").write_bytes(b"solid a\nendsolid a\n")
    (source / "ordner" / "drill-holder.3mf").write_bytes(b"3mf")
    (source / "notiz.txt").write_text("kein Fall", encoding="utf-8")
    (source / "haus.p3d.vor-reparatur").write_bytes(b"projekt")
    with zipfile.ZipFile(source / "paket.zip", "w") as archive:
        archive.writestr("innen/teil.stl", b"solid t\nendsolid t\n")
        archive.writestr("innen/liesmich.md", "nein")
    out = tmp_path / "ausgabe"
    cases = cases_from_source(source, out)
    assert [case.relative for case in cases] == [
        "a.stl",
        "haus.p3d.vor-reparatur",
        str(Path("ordner") / "drill-holder.3mf"),
        "paket.zip :: innen/teil.stl",
    ]
    assert [case.number for case in cases] == [1, 2, 3, 4]
    assert [case.bores for case in cases] == [False, False, True, False]
    # Die Sicherung wird als Projekt geöffnet, das Archivmitglied aus seiner Kopie.
    assert cases[1].suffix == ".p3d" and Path(cases[1].path).read_bytes() == b"projekt"
    assert Path(cases[3].path).read_bytes() == b"solid t\nendsolid t\n"
    assert Path(cases[3].path).parent == out / "archive-models"
    # Die Originale bleiben, wo sie sind.
    assert (source / "haus.p3d.vor-reparatur").read_bytes() == b"projekt"


def test_an_inventory_without_cases_fails_instead_of_counting_nothing(tmp_path: Path) -> None:
    """Ein Bestand mit null Fällen endet nicht mit 0 — ein Lauf darüber prüfte nichts.

    ``--source`` auf ``audit.py`` statt auf einen Ordner zählte null Fälle und
    meldete Erfolg. Daneben die Gegenprobe: ein Ordner mit einem Modell.
    """
    from tools.file_acceptance import main

    script = tmp_path / "audit.py"
    script.write_text("# kein Bestand\n", encoding="utf-8")
    empty = tmp_path / "leer"
    empty.mkdir()
    stock = tmp_path / "bestand"
    stock.mkdir()
    (stock / "a.stl").write_bytes(b"solid a\nendsolid a\n")
    for source, code in ((script, 2), (empty, 1), (stock, 0)):
        out = tmp_path / f"ausgabe-{source.name}"
        assert main(["inventory", "--source", str(source), "--out", str(out)]) == code
        assert (out / "cases.json").exists() is (code == 0)
    written = json.loads((tmp_path / "ausgabe-bestand" / "cases.json").read_text(encoding="utf-8"))
    assert [case["relative"] for case in written] == ["a.stl"]


def test_a_manifest_keeps_the_audit_numbers(tmp_path: Path) -> None:
    """Dieselben Fälle wie im Audit: Modelle, Projekte und Sicherungen mit Prüfkopie."""
    manifest = tmp_path / "manifest.json"
    write_json(
        manifest,
        [
            {"id": 1, "relative": "a.stl", "path": "F:/x/a.stl", "suffix": ".stl"},
            {"id": 2, "relative": "b.md", "path": "F:/x/b.md", "suffix": ".md"},
            {
                "id": 3,
                "relative": "c.p3d.vor-reparatur",
                "path": "F:/x/c.p3d.vor-reparatur",
                "suffix": ".vor-reparatur",
                "audit_path": "F:/audit/backup-3.p3d",
            },
            {
                "id": 7,
                "relative": "drill-holder.3mf",
                "path": "F:/x/drill-holder.3mf",
                "suffix": ".3mf",
            },
        ],
    )
    cases = cases_from_manifest(manifest)
    assert [(case.number, case.suffix, case.bores) for case in cases] == [
        (1, ".stl", False),
        (3, ".p3d", False),
        (7, ".3mf", True),
    ]
    assert cases[1].path == "F:/audit/backup-3.p3d"


def test_the_chosen_feature_is_a_bore_first_and_the_same_every_run() -> None:
    """Bohrung vor Fläche, bei gleicher Art der kleinere Körper, dann die kleinere Nummer."""
    objects = {
        "obj_2": {"face_1": "face", "hole_10": "hole", "hole_9": "hole"},
        "obj_1": {"face_3": "face", "fillet_1": "fillet"},
    }
    assert choose_feature(objects) == ("obj_2", "hole_9")
    assert choose_feature({"obj_1": {"face_12": "face", "face_2": "face"}}) == ("obj_1", "face_2")
    assert choose_feature({"obj_1": {"curved_face_1": "curved_face"}}) is None
    assert bore_ids({"hole_10": "hole", "hole_2": "hole", "face_1": "face"}) == [
        "hole_2",
        "hole_10",
    ]


def test_the_floor_of_a_chamber_comes_before_cones_pins_and_faces() -> None:
    """Am 1x1-bin trägt keine Fläche ein Längenfeld, die Kammer (RM-184) schon."""
    groups = ["chamber/closed:face_9", "channel/passage:hole_2", "thread/outer:pin_1"]
    assert group_anchors(groups) == {"face_9"}
    objects = {
        "obj_1": {"cone_1": "cone", "face_3": "face", "face_9": "face", "fillet_4": "fillet"}
    }
    assert ranked_features(objects, {"obj_1": group_anchors(groups)}) == [
        ("obj_1", "face_9"),
        ("obj_1", "cone_1"),
        ("obj_1", "fillet_4"),
        ("obj_1", "face_3"),
    ]


def test_every_kind_comes_up_within_the_tries() -> None:
    """Am 1x1-tray verbrauchten Kegel und Rundungen ohne Längenfeld alle zwölf Versuche.

    Ein Maß trugen dort nur die vier Wülste. Je Art höchstens drei: Kammerboden
    und Kanal, je drei Kegel, Rundungen und Wülste, dann die erste Fläche —
    alles innerhalb der Versuche. Die Merkmale wie am 1x1-tray.
    """
    features = {f"cone_{n}": "cone" for n in range(1, 5)}
    features |= {f"fillet_{n}": "fillet" for n in range(1, 8)}
    features |= {f"torus_{n}": "torus" for n in range(1, 5)}
    features |= {f"face_{n}": "face" for n in range(1, 18)}
    ranked = ranked_features({"obj_1": features}, {"obj_1": {"face_2", "face_11"}})
    assert ranked[:MOST_FEATURE_TRIES] == [
        ("obj_1", "face_2"),
        ("obj_1", "face_11"),
        ("obj_1", "cone_1"),
        ("obj_1", "cone_2"),
        ("obj_1", "cone_3"),
        ("obj_1", "fillet_1"),
        ("obj_1", "fillet_2"),
        ("obj_1", "fillet_3"),
        ("obj_1", "torus_1"),
        ("obj_1", "torus_2"),
        ("obj_1", "torus_3"),
        ("obj_1", "face_1"),
    ]


def test_a_size_comes_before_a_position() -> None:
    """Am Drillholder stand „Merkmal verschieben — X“ vorn, und jede Bohrung wurde verschoben.

    Die Maßänderung nimmt das erste Feld, das keine Lage nennt; trägt das
    Fenster nur Lagen, das erste.
    """
    bore = [
        "Merkmal verschieben — X",
        "Merkmal verschieben — Y",
        "Merkmal verschieben — Z",
        "Bohrung ändern — Durchmesser",
        "Bohrung ändern — X",
    ]
    assert size_field_first(bore) == 3
    assert size_field_first(["Kammer ändern — Breite innen", "Kammer ändern — Tiefe"]) == 0
    assert size_field_first(["Merkmal verschieben — X", "Merkmal verschieben — Y"]) == 0
    assert size_field_first([]) == 0


def test_a_feature_without_a_length_field_hands_over_to_the_next() -> None:
    """Am 1x1-bin stand vorn ein Kegel ohne Längenfeld — dann gilt das nächste Merkmal."""
    objects = {"obj_1": {"cone_1": "cone", "pin_2": "pin", "face_7": "face"}}
    ranked = ranked_features(objects)
    assert ranked == [("obj_1", "cone_1"), ("obj_1", "pin_2"), ("obj_1", "face_7")]

    def cycle(chosen: tuple[str, str]) -> dict[str, object]:
        return {"note": NO_LENGTH_FIELD} if chosen[1] == "cone_1" else {"feature": chosen[1]}

    tried, record = first_with_a_length_field(ranked, cycle)
    assert tried == ["cone_1", "pin_2"]
    assert record == {"feature": "pin_2"}
    # Ohne jedes Längenfeld bleibt der letzte Versuch mit seinem Vermerk.
    tried, record = first_with_a_length_field(ranked, lambda chosen: {"note": NO_LENGTH_FIELD})
    assert tried == ["cone_1", "pin_2", "face_7"]
    assert record == {"note": NO_LENGTH_FIELD}
    assert first_with_a_length_field([], cycle) == ([], None)


def test_a_briefly_locked_file_is_written_on_a_later_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows sperrt eine gelesene Datei kurz (``Errno 22`` am Drillholder): Es geht weiter."""
    target = tmp_path / "result.json"
    original = Path.replace
    failures = [OSError(22, "Invalid argument"), OSError(13, "Permission denied")]

    def replace(self: Path, other: Path) -> Path:
        if failures:
            raise failures.pop(0)
        return original(self, other)

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr("tools.file_acceptance.time.sleep", lambda seconds: None)
    write_json(target, {"stage": "done"})
    assert json.loads(target.read_text(encoding="utf-8")) == {"stage": "done"}
    assert not failures
    # Bleibt die Sperre, kommt der Fehler nach dem letzten Versuch heraus.
    failures.extend(OSError(22, "Invalid argument") for _ in range(3))
    with pytest.raises(OSError):
        write_json(target, {"stage": "later"}, attempts=3)
    assert json.loads(target.read_text(encoding="utf-8")) == {"stage": "done"}


@pytest.mark.parametrize(
    ("before", "after"),
    [(14.86 / 1.1, 14.86), (3.0, 3.5), (0.0, 1.0), (-20.0, -18.0)],
)
def test_the_changed_number_is_a_tenth_more_and_at_least_half_a_millimetre(
    before: float, after: float
) -> None:
    assert changed_value(before) == pytest.approx(after, abs=0.005)


def test_a_refused_change_tries_less_and_then_the_next_feature() -> None:
    """Am 1x1-bin brach die breitere Kammer durch die Wand — dann gilt weniger, dann das Nächste.

    Zuerst ein Zehntel mehr, dann ebenso viel weniger, solange die Zahl
    positiv bleibt; sagt die Vorschau beides ab, ist das Merkmal kein Fall der
    Maßänderung, wie eines ohne Längenfeld.
    """
    assert values_to_try(36.0) == pytest.approx((39.6, 32.4))
    assert values_to_try(3.0) == pytest.approx((3.5, 2.5))
    assert values_to_try(0.4) == pytest.approx((0.9,)), "weniger bliebe nicht positiv"
    assert values_to_try(0.0) == pytest.approx((1.0,))
    ranked = [("obj_1", "face_9"), ("obj_1", "hole_1")]

    def cycle(chosen: tuple[str, str]) -> dict[str, object]:
        return {"note": REFUSED} if chosen[1] == "face_9" else {"feature": chosen[1]}

    tried, record = first_with_a_length_field(ranked, cycle)
    assert tried == ["face_9", "hole_1"]
    assert record == {"feature": "hole_1"}


def test_a_case_where_no_feature_took_a_change_is_no_deviation() -> None:
    """Abweichung heißt: übernommen, und eine Prüfung widerspricht.

    Am 1x1-tray trug keines der zwölf versuchten Merkmale eine Änderung, und
    der Fall hieß „abweichung“, obwohl kein Schritt etwas geprüft hatte.
    """
    unchecked = dict.fromkeys(
        ("changed", "undo_restores_import", "redo_restores_applied", "preview_shows_result")
    )
    assert case_stage({"note": REFUSED, "checks": unchecked}) == UNCHANGEABLE
    assert case_stage({"note": NO_LENGTH_FIELD, "checks": unchecked}) == UNCHANGEABLE
    good = dict.fromkeys(unchecked, True)
    assert case_stage({"checks": good}) == "done"
    assert case_stage({"checks": {**good, "undo_restores_import": False}}) == "abweichung"


def test_the_checks_read_the_digests_of_every_step() -> None:
    """Rückgängig zum Import, Wiederholen zum Übernommenen, die Vorschau zeigt das Ergebnis."""
    cube = np.asarray([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    faces = np.asarray([[0, 1, 2]])
    original = mesh_digest(cube, faces)
    changed = mesh_digest(cube * 2.0, faces)
    assert original != changed and original == mesh_digest(cube.copy(), faces.copy())
    states = {
        "01-import": {"obj_1": original},
        "04-applied": {"obj_1": changed},
        "05-undo": {"obj_1": original},
        "06-redo": {"obj_1": changed},
    }
    checks = compared(states, {"obj_1": changed})
    assert checks == {
        "changed": True,
        "undo_restores_import": True,
        "redo_restores_applied": True,
        "preview_shows_result": True,
    }
    assert passed(checks)
    broken = compared({**states, "05-undo": {"obj_1": changed}}, None)
    assert broken["undo_restores_import"] is False and broken["preview_shows_result"] is None
    assert not passed(broken)
    # Ohne Rückgängig ist nichts bestanden — auch wenn sonst nichts widerspricht.
    assert not passed(compared({"01-import": states["01-import"]}, None))
    assert set(STEPS) >= set(states)


def test_the_report_counts_cases_and_bores_and_names_errors(tmp_path: Path) -> None:
    """JSON und Markdown aus den Ergebnissen der Fälle — auch aus einem nie gelaufenen."""
    good = {
        "stage": "done",
        "objects": [{"features": {"hole_1": "hole"}, "groups": ["chamber/closed:face_1"]}],
    }
    good["selection"] = {"feature": "hole_1"}
    good["checks"] = {
        "changed": True,
        "undo_restores_import": True,
        "redo_restores_applied": True,
        "preview_shows_result": True,
    }
    good["bores"] = [{"feature": "hole_1", "checks": good["checks"]}]
    bad = {"stage": "import", "errors": ["Die Datei ist leer"], "objects": []}
    write_json(tmp_path / "cases" / "001" / "result.json", good)
    write_json(
        tmp_path / "cases" / "001" / "process.json",
        {"exit_code": 0, "timeout": False, "wall_s": 12.5},
    )
    write_json(tmp_path / "cases" / "002" / "result.json", bad)
    write_json(
        tmp_path / "cases" / "002" / "process.json",
        {"exit_code": 1, "timeout": False, "wall_s": 3.0},
    )
    cases = [
        Case(1, "drill-holder.3mf", "F:/x/drill-holder.3mf", ".3mf", bores=True),
        Case(2, "leer.stl", "F:/x/leer.stl", ".stl"),
        Case(3, "fehlt.stl", "F:/x/fehlt.stl", ".stl"),
    ]
    data = summary(tmp_path, cases)
    assert (data["cases"], data["ran"], data["passed"], data["bores"], data["bores_passed"]) == (
        3,
        2,
        1,
        1,
        1,
    )
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["passed"] == 1
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert (
        "| 1 | drill-holder.3mf | done | 0 | 12.5 | 1 | 1 | 1 | hole_1 | ja | ja | ja | ja | ja |"
        in text
    )
    assert "| 3 | fehlt.stl | nicht gelaufen |" in text
    assert "Die Datei ist leer" in text


def test_the_window_flow_changes_every_bore_and_takes_it_back(
    window: MainWindow, tmp_path: Path
) -> None:
    """Ein Fall im Fenster, offscreen: jede Bohrung der Lochplatte, dann der gewählte Fall.

    Vier Bohrungen Ø 5,2 (``data/meshes/plate_holes.stl``). Je Bohrung ändert
    das erste Längenfeld des Merkmalfensters den Körper, Rückgängig stellt den
    Import her, Wiederholen das Übernommene, und die Vorschau zeigt, was
    übernommen wird — derselbe Weg, den der echte Lauf je Fall geht.
    """
    from PySide6.QtWidgets import QApplication

    from tools.file_acceptance import WindowFlow

    data: dict[str, object] = {
        "stage": "start",
        "errors": [],
        "questions": [],
        "dialogs": [],
        "states": {},
    }
    flow = WindowFlow(QApplication.instance(), window, window.session, tmp_path, data, lambda: None)
    flow.prepare()
    plate = Path(__file__).parent / "data" / "meshes" / "plate_holes.stl"
    flow.run(Case(1, "plate_holes.stl", str(plate), ".stl", bores=True))

    assert data["stage"] == "done", data.get("errors")
    bores = data["bores"]
    assert isinstance(bores, list) and len(bores) == 4
    assert all(passed(bore["checks"]) for bore in bores), [bore["checks"] for bore in bores]
    checks = data["checks"]
    assert isinstance(checks, dict)
    assert checks["changed"] is True and checks["preview_shows_result"] is True
    assert (tmp_path / "04-applied.png").exists()


def test_the_window_flow_narrows_a_chamber_whose_wider_wall_would_break(
    window: MainWindow, tmp_path: Path
) -> None:
    """Ein Kasten 38 × 28 × 20 mit 1 mm Wand: Ein Zehntel breiter bräche die Wand.

    Innen 36 breit; 39,6 läge über der Außenwand, die Vorschau sagt ab, und der
    Lauf nimmt 32,4 — Übernehmen, Rückgängig und Wiederholen gehen durch. Am
    1x1-bin wartete der Lauf auf ein Bild, das es nicht geben konnte, und brach
    nach sechs Minuten ab.
    """
    import trimesh
    from PySide6.QtWidgets import QApplication

    from app.core.geom.boolean import boolean
    from app.core.geom.mesh import MeshData
    from tools.file_acceptance import WindowFlow

    outer = trimesh.creation.box(extents=(38.0, 28.0, 20.0))
    outer.apply_translation((0.0, 0.0, 10.0))
    inner = trimesh.creation.box(extents=(36.0, 26.0, 20.0))
    inner.apply_translation((0.0, 0.0, 12.0))
    box = tmp_path / "kasten.stl"
    boolean("difference", [MeshData.of(outer), MeshData.of(inner)]).mesh.raw.export(box)
    data: dict[str, object] = {
        "stage": "start",
        "errors": [],
        "questions": [],
        "dialogs": [],
        "states": {},
    }
    flow = WindowFlow(QApplication.instance(), window, window.session, tmp_path, data, lambda: None)
    flow.prepare()
    flow.run(Case(1, "kasten.stl", str(box), ".stl", bores=False))

    assert data["stage"] == "done", (data.get("errors"), data.get("selection"))
    checks = data["checks"]
    assert isinstance(checks, dict) and passed(checks), checks
    selection = data["selection"]
    assert isinstance(selection, dict)
    changed = selection["changed"]
    assert (changed["before"], changed["after"]) == pytest.approx((36.0, 32.4))
    refusals = data["refusals"]
    assert isinstance(refusals, list) and [entry["value"] for entry in refusals] == [39.6]
    assert "durchbrechen" in refusals[0]["reason"]
    assert refusals[0]["feature"] == selection["feature"]


@pytest.mark.windowed
def test_a_case_runs_in_its_own_process_from_inventory_to_report(tmp_path: Path) -> None:
    """Der ganze Weg eines Falls: Bestand, eigener Prozess mit eigenem Profil, Bericht.

    Der Prozess baut die Anwendung wie ``main`` — ohne das Register davor
    brach jeder Fall beim Bau der Menüs ab (``unknown operation``), und der
    Fensterweg im Test darüber hätte es nie gesehen, weil die Suite das
    Register schon geladen hat. Offscreen, die Lochplatte mit vier Bohrungen
    unter einem Namen, der jede Bohrung verlangt.
    """
    import os
    import shutil
    import subprocess
    import sys

    source = tmp_path / "bestand"
    source.mkdir()
    shutil.copyfile(
        Path(__file__).parent / "data" / "meshes" / "plate_holes.stl",
        source / "drill-holder-platte.stl",
    )
    out = tmp_path / "abnahme"
    tool = ROOT / "tools" / "file_acceptance.py"
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONUTF8": "1"}
    for arguments in (
        ["inventory", "--source", str(source), "--out", str(out)],
        ["run", "--out", str(out), "--timeout", "600"],
    ):
        finished = subprocess.run(
            [sys.executable, str(tool), *arguments],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=900,
            check=False,
        )
        assert finished.returncode == 0, (finished.stdout, finished.stderr)
    report = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert (report["cases"], report["ran"], report["passed"]) == (1, 1, 1), report["rows"]
    assert (report["bores"], report["bores_passed"]) == (4, 4)
    assert (
        (out / "summary.md").read_text(encoding="utf-8").startswith("# Native Einzeldateiabnahme")
    )


def test_the_output_folder_stays_outside_the_repository(tmp_path: Path) -> None:
    """Bilder und Profile gehören nicht in den Arbeitsbaum."""
    with pytest.raises(SystemExit):
        outside_the_repository(ROOT / "tmp" / "abnahme")
    assert outside_the_repository(tmp_path) == tmp_path.resolve()
