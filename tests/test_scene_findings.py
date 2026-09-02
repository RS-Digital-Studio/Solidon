"""Befunde der Durchsicht von ``app/core/scene/`` und ``app/core/paths.py``.

Jeder Test hier hat einen Fall hinter sich, der reproduziert wurde, bevor er
behoben war — die Datei ist das Regressionsnetz dieser Durchsicht und keine
Sammlung von Vermutungen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app.core.paths as paths_module
import app.core.scene.project as project_module
from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.knowledge import profiles
from app.core.scene import History, OperationDraft, bundling
from app.core.scene.evaluate import evaluate
from app.core.scene.project import Project, load, new_project, save
from app.core.types import Document, Operation, Parameter, Source

# --- Ein Name, der wie ein Verweis aussieht (gathered.py) ------------------------


def test_a_name_that_looks_like_a_reference_still_opens(tmp_path: Path) -> None:
    """Ein Objektname mit ``source:`` davor macht das Projekt nicht unöffenbar.

    Vor dem 02.09.2026 galt **jeder** Parameterwert mit diesem Präfix beim
    Laden als Verweis auf einen ausgelagerten Sammelwert, gleich welcher Art
    der Parameter war. Wer sein Objekt ``source:meiner`` nannte, speicherte
    ein Projekt und bekam beim Öffnen „Zu diesem Schritt fehlt der
    ausgelagerte Inhalt im Container — die Datei ist unvollständig", während
    der Container heil war.

    Geprüft mit beiden Gestalten: der beliebigen und der, die zufällig genau
    wie ein echter Verweis aussieht. Der Parameter ist ein Name (``kind``
    ``string``), also ist er nie ein Sammelwert — das entscheidet das
    Register, nicht der Text.
    """
    for name in ("source:meiner", "source:gathered_1"):
        project = new_project()
        history = History(project.document)
        history.apply("Quader", [OperationDraft(op="create_box")])
        history.apply(
            "Umbenennen",
            [OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": name})],
        )

        again = load(save(project, tmp_path / "namen.p3d"))

        assert again.document.ops[-1].params["name"] == name


# --- Parameter, die sich nicht auflösen lassen (evaluate.py) ---------------------


def _document_with_a_division_by_zero() -> Document:
    """Ein Dokument, dessen Parameter sich nicht auflösen lassen."""
    document = Document(format_version=1, app_version="0.0.1")
    document.parameters["a"] = Parameter(name="a", value=0.0, unit="mm")
    document.parameters["b"] = Parameter(name="b", value=1.0, unit="mm", expression="=10/@a")
    return document


def _a_box() -> Operation:
    """Ein Schritt im Stapel, damit die Kette etwas zum Anhalten hat."""
    load_operations()
    return Operation(id=1, op="create_box", inputs=(), outputs=("obj_1",), params={})


def test_unresolvable_parameters_stop_the_chain_instead_of_raising() -> None:
    """§15.3: Die Auswertung hält an und sagt es — sie fliegt nicht auf.

    ``expressions.resolve`` stand als einzige Zeile der Funktion außerhalb
    jedes ``try``. Eine Division durch null, ein Kreis oder ein Verweis ins
    Leere kam damit als Ausnahme aus ``evaluate()`` heraus, statt als Befund
    im Prüfbericht zu stehen — für den Aufrufer ein Absturz an einer Stelle,
    an der jeder andere Fehler eine Zeile ist.
    """
    document = _document_with_a_division_by_zero()
    document.ops.append(_a_box())

    result = evaluate(document, profiles.make_profile("centauri-carbon-2", "petg"))

    assert result.stopped_at == 1, "die Kette hält am ersten Schritt an"
    codes = [entry.code for entry in result.scene.report.findings]
    assert "parameter.unresolvable" in codes
    unresolvable = next(
        entry for entry in result.scene.report.findings if entry.code == "parameter.unresolvable"
    )
    assert unresolvable.severity == "error"
    assert unresolvable.suggestions, "Regel 17: ein Fehler endet nie mit „fehlgeschlagen“"


def test_unresolvable_parameters_without_a_stack_are_still_reported() -> None:
    """Ohne Operationen gibt es keinen Schritt, an dem es anhalten könnte.

    Der Befund muss trotzdem dastehen: Die Parameterleiste zeigt den Zustand
    an, und ein leerer Bericht hieße „alles in Ordnung".
    """
    result = evaluate(
        _document_with_a_division_by_zero(),
        profiles.make_profile("centauri-carbon-2", "petg"),
    )

    assert result.stopped_at is None
    assert [entry.code for entry in result.scene.report.findings] == ["parameter.unresolvable"]


# --- Was Solidon schreibt, muss Solidon lesen können (project.py) ----------------


def test_a_container_solidon_cannot_read_is_not_written(tmp_path: Path) -> None:
    """Was der Leser ablehnt, schreibt der Schreiber gar nicht erst.

    Der Leser lehnt ein Kompressionsverhältnis über 250 ab (§32); der
    Schreiber prüfte es nicht. Vier Mebibyte gleicher Bytes wurden zu rund
    zwölf Kilobyte — Verhältnis 342 —, das Speichern lief durch, und beim
    Öffnen stand „Die Datei entpackt sich größer, als diese Anwendung
    verarbeitet". Ein Projekt, das nur Solidon selbst anlegen konnte, mit einer
    Meldung über eine Grenze, die der Kunde nicht gerissen hat.

    Jetzt sagt es die Anwendung dort, wo der Kunde noch handeln kann.
    """
    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/src_1.stl", sha256=""
    )
    project.sources["src_1"] = b"A" * (4 * 1024 * 1024)
    target = tmp_path / "presse.p3d"

    with pytest.raises(ValidationError) as caught:
        save(project, target)

    assert caught.value.constraint == "file_too_large"
    assert caught.value.suggestions, "Regel 17: ein Fehler endet nie mit „fehlgeschlagen“"
    assert not target.exists(), "eine halbe Datei wäre schlimmer als keine"
    assert not list(tmp_path.glob("*.part")), "der Zwischenschritt ist weg"


def test_a_refused_save_leaves_the_existing_project_alone(tmp_path: Path) -> None:
    """Und die vorhandene Datei bleibt, was sie war.

    Geschrieben wird atomar (§16.1): Die Prüfung läuft am fertigen Container
    im Zwischenschritt, also **vor** dem Wechsel auf den Zielnamen. Stünde sie
    danach, kostete eine gerissene Grenze das Projekt von gestern.
    """
    project = new_project()
    path = save(project, tmp_path / "bestand.p3d")
    before = path.read_bytes()
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/src_1.stl", sha256=""
    )
    project.sources["src_1"] = b"A" * (4 * 1024 * 1024)

    with pytest.raises(ValidationError):
        save(project, path)

    assert path.read_bytes() == before, "das vorhandene Projekt bleibt heil"
    assert not list(tmp_path.glob("*.part"))


def test_two_linked_models_of_full_size_fit_together() -> None:
    """Das Summenbudget verknüpfter Quellen trägt zwei einzeln erlaubte Modelle.

    ``MAX_LINKED_SOURCE_BYTES`` zählt über alle verknüpften Quellen und stand
    auf der Grenze einer **einzelnen** Datei: Zwei je zulässige Modelle
    öffneten damit nicht. Für eingebettete Quellen gilt seit dem 02.09.2026
    ausdrücklich das Doppelte (``MAX_ARCHIVE_UNPACKED_BYTES``) — dieselbe
    Regel, derselbe Grund.
    """
    assert project_module.MAX_LINKED_SOURCE_BYTES == project_module.MAX_ARCHIVE_UNPACKED_BYTES
    assert project_module.MAX_LINKED_SOURCE_BYTES >= 2 * project_module.MAX_ARCHIVE_ENTRY_BYTES


# --- Der Stempel der eigenen Bausteine (paths.py) --------------------------------


def test_a_changed_recipe_changes_the_cache_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein geändertes Rezept fängt kalt an — wie ein geänderter eigener Baustein.

    Der Stempel sah nur ``*.py`` und damit die Rezepte nicht: Sie liegen als
    ``.json`` unter ``<Bausteine>/recipes``. Ein Rezept ist trotzdem eine
    Operation, und ändert sich ein Maß darin, bleiben Op-Name und Parameter
    gleich — der Operations-Hash sieht nichts, und der Plattencache lieferte
    weiter die alte Geometrie.
    """
    from app.core.knowledge.parts.recipe import RECIPES_DIRNAME

    monkeypatch.setattr(paths_module, "user_parts_dir", lambda: tmp_path)
    recipes = tmp_path / RECIPES_DIRNAME
    recipes.mkdir(parents=True)
    recipe = recipes / "halter.json"
    recipe.write_text('{"name": "halter", "steps": []}', encoding="utf-8")

    first = paths_module.results_cache_dir()
    recipe.write_text('{"name": "halter", "steps": [1]}', encoding="utf-8")
    second = paths_module.results_cache_dir()

    assert first != second, "die Änderung am Rezept steht im Ordnernamen"


# --- Ein Ausdruck im Bündel (bundling.py) ----------------------------------------


def test_an_expression_does_not_bundle() -> None:
    """Ein Ausdruck als Wert gibt ``None`` — den vorgesehenen sicheren Ausgang.

    ``merge_params`` rechnete mit ``float(...)`` und warf bei ``=@dx`` einen
    rohen ``ValueError`` aus ``History.apply`` heraus: ein Programmfehler ohne
    Handlungsvorschlag für einen Wert, den §13 ausdrücklich erlaubt. ``None``
    heißt „gehört nicht zusammen", und der Aufrufer legt einen eigenen Schritt
    an — ein Bündel zu wenig kostet einen Eintrag im Verlauf.
    """
    assert bundling.merge_params("translate_object", {"dx": "=@dx"}, {"dx": 1.0}) is None
    assert bundling.merge_params("translate_object", {"dx": 1.0}, {"dx": "=@dx"}) is None
    assert (
        bundling.merge_params(
            "rotate_object", {"axis": "z", "angle": "=@a"}, {"axis": "z", "angle": 5.0}
        )
        is None
    )
    summed = bundling.merge_params("translate_object", {"dx": 1.0}, {"dx": 2.0})
    assert summed is not None and summed["dx"] == 3.0, "zwei Zahlen bündeln weiterhin"


def test_a_drag_with_an_expression_becomes_its_own_step() -> None:
    """Und am Verlauf gemessen: der zweite Zug wird ein eigener Schritt."""
    load_operations()
    project = Project(document=Document(format_version=1, app_version="0.0.1"))
    history = History(project.document)
    history.apply("Quader", [OperationDraft(op="create_box")])
    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 1.0})],
        bundle=True,
    )

    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": "=@dx"})],
        bundle=True,
    )

    assert [entry.op for entry in project.document.ops] == [
        "create_box",
        "translate_object",
        "translate_object",
    ]


# --- Und dasselbe eine Ebene höher (ui/session.py) -------------------------------


def test_a_turned_number_that_breaks_an_expression_is_refused(qt_app: object) -> None:
    """Die Leiste sagt es dort, wo gedreht wird — nicht erst im Prüfbericht.

    ``change_parameter`` prüfte nur, ob die Zahl endlich ist. Eine Null, an der
    ein zweites Maß mit ``=10/@a`` hängt, ging damit ins Dokument, und die
    Auswertung dahinter flog auf (§15.3). Sie hält jetzt an — und hier fällt
    die Änderung schon vorher weg, samt Satz an der Stelle, an der sie
    entstanden ist.
    """
    from app.ui.session import Session

    session = Session()
    document = session.project.document
    document.parameters["a"] = Parameter(name="a", value=10.0, unit="mm")
    document.parameters["b"] = Parameter(name="b", value=1.0, unit="mm", expression="=10/@a")
    seen: list[object] = []
    session.failed.connect(seen.append)

    assert not session.change_parameter("a", 0.0)

    assert document.parameters["a"].value == 10.0, "das Dokument bleibt, wie es war"
    assert not session.history.can_undo
    assert seen, "und der Kunde erfährt davon"


def test_a_document_that_already_fails_stays_editable(qt_app: object) -> None:
    """Die Gegenprobe, und sie ist die wichtigere Hälfte (§2.1).

    Wer eine von Hand bearbeitete Datei öffnet, deren Ausdrücke schon nicht
    aufgehen, muss die Zahl ändern können, die sie repariert. Eine Prüfung, die
    jede Änderung ablehnt, solange der Satz nicht auflöst, wäre genau die
    Sackgasse, die sie verhindern soll.
    """
    from app.ui.session import Session

    session = Session()
    document = session.project.document
    document.parameters["a"] = Parameter(name="a", value=0.0, unit="mm")
    document.parameters["b"] = Parameter(name="b", value=1.0, unit="mm", expression="=10/@a")

    assert session.change_parameter("a", 5.0)

    assert document.parameters["a"].value == 5.0
