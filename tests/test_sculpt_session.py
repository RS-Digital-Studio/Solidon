"""Die Formsitzung im Fenster (Konzept P16.6, Bauplan §25).

Ein **Werkzeugmodus**, kein Betriebsmodus (Entscheidung J): Er gilt für die
eine Operation, die gerade entsteht, die Szene bleibt die Szene, und Escape
kommt heraus. Was ihn vom Skizzenmodus unterscheidet, ist, dass die Ansicht
bleibt — geformt wird am Körper, nicht auf einer Zeichenfläche.

Geprüft wird offscreen, wie bei ``test_sketch_editor.py``: Die Züge entstehen
über Methodenaufrufe und nicht über Mauswege. Ein Zug ist hier drei Zahlen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.geom.sculpt import strokes_from_text
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    """Ein Fenster ohne Körper — jeder Test entscheidet selbst, ob er einen
    braucht."""
    return MainWindow(Session(), UiSettings())


def with_a_body(window: MainWindow) -> str:
    """Die saubere Figur aus dem Korpus, ausgewählt wie nach einem Klick.

    Nicht irgendein Quader: Sie ist die Vorlage, für die es diese Sitzung
    gibt, und ihre mittlere Kantenlänge von 2,8 mm macht nebenbei den
    Auflösungshinweis prüfbar.
    """
    window.open_path(MESHES / "clean_figure.stl")
    window.session.wait_for_idle()
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    object_id = window.object_tree.selected()
    assert object_id
    return str(object_id)


# --- hinein und heraus ----------------------------------------------------------


def test_the_session_needs_something_to_sculpt(window: MainWindow) -> None:
    """Ohne Objekt kein Pinsel — und ein Satz dazu statt einer stillen
    Nichtreaktion."""
    window.start_sculpt()

    assert not window.sculpting()
    assert not window.sculpt_bar.isVisible()


def test_starting_shows_the_bar_and_hides_the_view_tools(window: MainWindow) -> None:
    """Die Ansichtswerkzeuge tun beim Formen nichts.

    Sie standen im Skizzenmodus als zweite Leiste unter der des Editors und
    boten sieben Umschalter an, von denen keiner etwas bewirkte. Hier gilt
    dasselbe: Schnitt, Messen und Bemalen brauchen einen fertigen Körper.
    """
    object_id = with_a_body(window)

    window.start_sculpt(object_id)

    assert window.sculpting()
    assert window.sculpt_bar.isVisibleTo(window)
    assert not window.tools.isVisibleTo(window)


def test_escape_leaves_the_session_without_throwing_work_away(window: MainWindow) -> None:
    """Escape beendet wie „Fertig" — es verwirft nicht.

    Ein Escape, das eine Stunde Arbeit wegwirft, wäre die teuerste Taste des
    Programms. Was dabei entsteht, nimmt ein Undo zurück (Regel 19).
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window._on_sculpt((20.0, 0.0, 0.0))
    before = len(window.session.project.document.ops)

    window._escape()

    assert not window.sculpting()
    assert len(window.session.project.document.ops) == before + 1


def test_an_empty_session_leaves_no_step_behind(window: MainWindow) -> None:
    """Eine Sitzung ohne Zug hinterlässt nichts.

    Ein leerer Schritt im Verlauf wäre Rauschen an genau der Stelle, an der
    man sucht.
    """
    object_id = with_a_body(window)
    before = len(window.session.project.document.ops)

    window.start_sculpt(object_id)
    window.finish_sculpt()

    assert len(window.session.project.document.ops) == before


# --- Züge sammeln ---------------------------------------------------------------


def test_strokes_gather_without_touching_the_document(window: MainWindow) -> None:
    """Regel 2: Geometrie entsteht in der Operation, nicht im Fenster.

    Während der Sitzung wächst eine Liste. Der Dokumentzustand ändert sich
    dabei nicht — er ändert sich bei „Fertig", in einer Transaktion.
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    before = len(window.session.project.document.ops)

    window._on_sculpt((20.0, 0.0, 0.0))
    window._on_sculpt((0.0, 20.0, 0.0))

    assert len(window._sculpt_strokes) == 2
    assert len(window.session.project.document.ops) == before


def test_the_bar_counts_strokes_and_stages(window: MainWindow) -> None:
    """Die Etappenzahl ist der Preis aus Entscheidung C und gehört sichtbar."""
    object_id = with_a_body(window)
    window.start_sculpt(object_id)

    window._on_sculpt((20.0, 0.0, 0.0))
    window.sculpt_bar.tool.setCurrentIndex(2)  # Glätten — beginnt eine Etappe
    window._on_sculpt((0.0, 20.0, 0.0))

    text = window.sculpt_bar.state.text()
    assert "2" in text, f"zwei Züge müssen dastehen: {text!r}"


def test_a_forced_cut_applies_to_one_stroke_only(window: MainWindow) -> None:
    """Der Schalter gilt für **einen** Zug.

    Stehen zu bleiben hieße, dass jeder weitere Zug eine eigene Etappe bekommt
    — und damit einen eigenen Durchgang, ohne dass jemand das verlangt hätte.
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)

    window.sculpt_bar.cut.setChecked(True)
    window._on_sculpt((20.0, 0.0, 0.0))
    window._on_sculpt((0.0, 20.0, 0.0))

    assert not window.sculpt_bar.cut.isChecked(), "der Schalter fällt nach einem Zug zurück"
    assert window._sculpt_strokes[0].cut is True
    assert window._sculpt_strokes[1].cut is False


def test_undo_takes_back_a_stroke_not_the_operation(window: MainWindow) -> None:
    """Das Rückgängig des Editors läuft auf der Strichliste.

    Solange die Sitzung offen ist, wäre ein Zug im Verlauf ein Eintrag, den
    niemand haben will — der Verlauf bekommt die Sitzung als eine Transaktion
    (Regel 16).
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    before = len(window.session.project.document.ops)
    window._on_sculpt((20.0, 0.0, 0.0))
    window._on_sculpt((0.0, 20.0, 0.0))

    window.action_undo()

    assert len(window._sculpt_strokes) == 1
    assert len(window.session.project.document.ops) == before, "der Verlauf bleibt unberührt"


def test_undo_outside_a_session_still_undoes_the_history(window: MainWindow) -> None:
    """Die Gegenprobe — sonst wäre Strg+Z nach der Sitzung tot."""
    with_a_body(window)
    before = len(window.session.project.document.ops)

    window.action_undo()

    assert len(window.session.project.document.ops) < before


# --- was dabei herauskommt ------------------------------------------------------


def test_finishing_writes_exactly_one_operation(window: MainWindow) -> None:
    """Regel 16: Der ganze Vorgang ist eine Transaktion.

    Vier Züge, ein Schritt im Verlauf — und ein Undo nimmt ihn vollständig
    zurück.
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    for point in ((20.0, 0.0, 0.0), (0.0, 20.0, 0.0), (0.0, 0.0, 20.0), (-20.0, 0.0, 0.0)):
        window._on_sculpt(point)
    before = len(window.session.project.document.ops)

    window.finish_sculpt()

    ops = window.session.project.document.ops
    assert len(ops) == before + 1
    assert ops[-1].op == "sculpt_strokes"
    assert len(strokes_from_text(str(ops[-1].params["strokes"]))) == 4

    window.action_undo()
    assert len(window.session.project.document.ops) == before


def test_the_chosen_symmetry_reaches_the_operation(window: MainWindow) -> None:
    """Entscheidung F: Symmetrie ist eine Eigenschaft der Operation und
    deshalb nachträglich änderbar."""
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window.sculpt_bar.symmetry.setCurrentIndex(1)  # x
    window._on_sculpt((20.0, 0.0, 0.0))

    window.finish_sculpt()

    assert window.session.project.document.ops[-1].params["symmetry"] == "x"


def test_a_stroke_carries_the_surface_direction(window: MainWindow) -> None:
    """Der Klick liefert einen Ort, der Zug braucht eine Richtung.

    Sie kommt aus dem Kern, nicht aus dem Fenster — die Oberfläche steuert
    zwei Zahlen und einen Klick bei.
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    mesh = window._sculpt_mesh(object_id)
    assert mesh is not None
    crown = mesh.bounds.maximum

    window._on_sculpt((0.0, 0.0, crown[2]))

    normal = window._sculpt_strokes[0].normal
    assert normal[2] > 0.8, f"auf dem Scheitel zeigt die Fläche nach oben: {normal}"


def test_a_brush_finer_than_the_mesh_says_so_before_anyone_paints(
    window: MainWindow,
) -> None:
    """Entscheidung E: Fehler als Vorschlag, bevor der Fehler passiert.

    Die Warnung steht beim Öffnen da, nicht erst nach dem ersten vergeblichen
    Zug — und sie verschwindet, sobald der Pinsel zum Netz passt.
    """
    object_id = with_a_body(window)

    window.sculpt_bar.radius.setValue(0.2)
    window.start_sculpt(object_id)
    assert window.sculpt_bar.warning.text()

    window.sculpt_bar.radius.setValue(6.0)
    window._on_sculpt((20.0, 0.0, 0.0))
    assert not window.sculpt_bar.warning.text()
