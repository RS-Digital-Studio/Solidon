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


# --- der Pinselring -------------------------------------------------------------


def test_the_brush_ring_lies_flat_on_the_surface() -> None:
    """Ein Weltmaß gehört als Ring in die Szene, nicht an den Zeiger.

    Ein Zeiger hat feste Punktgröße und weiß nichts von der Kamera — beim
    ersten Zoom behauptet er eine Größe, die er nicht mehr hat. Der Ring liegt
    stattdessen flach auf der Fläche: Einer, der immer zum Betrachter zeigt,
    sagt nichts darüber, wie schräg die Stelle unter ihm steht, und schräg ist
    beim Formen der Normalfall.
    """
    import numpy as np

    from app.ui.viewport import _ring_points

    centre = np.array([10.0, 0.0, 0.0])
    normal = np.array([1.0, 0.0, 0.0])

    ring = _ring_points(centre, normal, 4.0)

    away = np.linalg.norm(ring - centre - normal * 4.0 * 0.02, axis=1)
    assert np.allclose(away, 4.0), "jeder Punkt hat den Pinselradius"
    assert np.allclose(ring[:, 0], ring[0, 0]), "und alle liegen in einer Ebene quer zur Normale"


def test_the_brush_ring_survives_a_normal_along_any_axis() -> None:
    """Der Hilfsvektor darf nirgends parallel zur Normale liegen.

    Ein fester Startvektor wäre genau dort entartet, wo er parallel zu ihr
    steht — und das ist keine seltene Lage, sondern jede achsparallele Fläche.
    """
    import numpy as np

    from app.ui.viewport import _ring_points

    for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)):
        ring = _ring_points(np.zeros(3), np.asarray(axis), 3.0)
        assert np.isfinite(ring).all(), f"Normale {axis} ergibt keine Zahlen"
        assert len(np.unique(np.round(ring, 6), axis=0)) == len(ring), "keine doppelten Punkte"


# --- die mitlaufende Wandprüfung ------------------------------------------------


def with_a_thin_shell(window: MainWindow, tmp_path: Path) -> str:
    """Eine Schale mit 0,6 mm Wand — dünner, als jedes Material verträgt.

    Aus zwei Quadern und nicht über ``hollow``: Das Aushöhlen läuft über ein
    Raster und liefert 160 000 Dreiecke, deren Laden den Test von der
    Reihenfolge abhängig machte. Vierundzwanzig Dreiecke sagen dasselbe über
    eine dünne Wand.
    """
    import numpy as np
    import trimesh

    outer = trimesh.creation.box(extents=(30.0, 30.0, 20.0))
    inner = trimesh.creation.box(extents=(28.8, 28.8, 18.8))
    shell = trimesh.Trimesh(
        vertices=np.vstack([outer.vertices, inner.vertices]),
        faces=np.vstack([outer.faces, inner.faces[:, ::-1] + len(outer.vertices)]),
        process=False,
    )
    shell.apply_translation((0.0, 0.0, 10.0))
    path = tmp_path / "shell.stl"
    path.write_bytes(trimesh.exchange.stl.export_stl(shell))
    window.open_path(path)
    window.session.wait_for_idle()
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    object_id = window.object_tree.selected()
    assert object_id
    return str(object_id)


def test_sculpting_reports_walls_that_are_too_thin(window: MainWindow, tmp_path: Path) -> None:
    """Entscheidung L, und der Grund, warum das Vorhaben hierher gehört.

    Ein Sculpting-Programm weiß nichts über Drucker; ein Slicer merkt es, aber
    erst wenn die Form fertig ist. Hier steht es in der Leiste, während man
    formt — als Zahl und nicht nur als Farbe (Regel 18).
    """
    object_id = with_a_thin_shell(window, tmp_path)
    window.start_sculpt(object_id)
    window._on_sculpt((0.0, 0.0, 20.0))

    window._check_sculpted_walls()

    text = window.sculpt_bar.warning.text()
    assert any(char.isdigit() for char in text), f"eine Zahl muss dastehen: {text!r}"


def test_a_solid_body_leaves_the_warning_empty(window: MainWindow) -> None:
    """Die Gegenprobe — sonst warnt jede Sitzung und keine Warnung zählt."""
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window._on_sculpt((0.0, 0.0, 82.0))

    window._check_sculpted_walls()

    assert not window.sculpt_bar.warning.text()


def test_the_wall_check_waits_for_the_hand_to_rest(window: MainWindow) -> None:
    """Nicht bei jedem Zug, sondern nach dem letzten.

    Bei jedem Zug zu rechnen hieße, den Pinsel um eine Viertelsekunde zu
    verzögern, damit eine Zahl aktuell ist, die sich beim nächsten Zug wieder
    ändert.
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)

    window._on_sculpt((0.0, 0.0, 82.0))

    assert window._sculpt_check.isActive(), "der Zug stößt die Prüfung an"
    assert window._sculpt_check.interval() > 0, "und zwar verzögert"


def test_leaving_the_session_stops_the_check(window: MainWindow) -> None:
    """Eine Prüfung, die nach dem Verlassen zuschlägt, schriebe in eine Leiste,
    die niemand mehr ansieht."""
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window._on_sculpt((0.0, 0.0, 82.0))

    window.finish_sculpt()

    assert not window._sculpt_check.isActive()


# --- Einbacken (Entscheidung D) -------------------------------------------------


def test_the_history_offers_baking_only_for_a_live_session(window: MainWindow) -> None:
    """Der Eintrag steht an einer Formsitzung und an keinem anderen Schritt.

    Ein Menüeintrag, der überall steht und fast nirgends etwas tut, ist einer,
    den man nicht mehr liest.
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window._on_sculpt((0.0, 0.0, 82.0))
    window.finish_sculpt()
    window.session.wait_for_idle()

    document = window.session.project.document
    sculpt = next(entry for entry in document.ops if entry.op == "sculpt_strokes")
    other = next(entry for entry in document.ops if entry.op != "sculpt_strokes")
    window.history_panel.show_document(document)

    assert sculpt.id in window.history_panel._bakeable
    assert other.id not in window.history_panel._bakeable


def test_baking_writes_the_state_into_the_project(window: MainWindow) -> None:
    """Entscheidung D: Der Stand wandert als Quelle ins Projekt.

    Danach wird nicht mehr gerechnet — bei zwanzig Etappen kostet jede
    Auswertung zwanzig Durchgänge, und genau das ist der Grund für die
    Handlung.
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window._on_sculpt((0.0, 0.0, 82.0))
    window.finish_sculpt()
    window.session.wait_for_idle()
    sculpt = next(
        entry for entry in window.session.project.document.ops if entry.op == "sculpt_strokes"
    )
    before = len(window.session.project.document.sources)

    assert window.session.bake_strokes(sculpt.id)
    window.session.wait_for_idle()

    assert len(window.session.project.document.sources) == before + 1
    frozen = next(
        entry for entry in window.session.project.document.ops if entry.op == "sculpt_strokes"
    )
    assert frozen.params["baked"], "die Operation kennt ihren festgeschriebenen Stand"
    assert frozen.params["strokes"], "und die Züge stehen weiter als Beleg da"


def test_a_baked_session_is_not_offered_again(window: MainWindow) -> None:
    """Zweimal festschreiben ergibt keinen Sinn — und der Eintrag verschwindet."""
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window._on_sculpt((0.0, 0.0, 82.0))
    window.finish_sculpt()
    window.session.wait_for_idle()
    sculpt = next(
        entry for entry in window.session.project.document.ops if entry.op == "sculpt_strokes"
    )
    window.session.bake_strokes(sculpt.id)
    window.session.wait_for_idle()

    window.history_panel.show_document(window.session.project.document)

    assert sculpt.id not in window.history_panel._bakeable


def test_baking_something_that_is_not_a_session_does_nothing(window: MainWindow) -> None:
    """Der Kern lehnt ab, statt irgendetwas festzuschreiben."""
    object_id = with_a_body(window)
    other = window.session.project.document.ops[0]
    assert other.op != "sculpt_strokes"

    assert not window.session.bake_strokes(other.id)
    assert object_id


# --- der Weg aus der Warnung heraus ---------------------------------------------


def test_the_resolution_warning_carries_a_button(window: MainWindow) -> None:
    """Ein Hinweis, der eine andere Operation verlangt, braucht den Weg dorthin.

    Die Zeile „erst gleichmäßig vernetzen" stand allein da. Wer ihr folgen
    wollte, musste die Sitzung verlassen, im Menü *Ändern → Netz* suchen, eine
    Kantenlänge raten und von vorn anfangen — vier Schritte für einen Satz,
    der die Antwort schon kennt.
    """
    with_a_body(window)
    window.sculpt_bar.radius.setValue(1.0)
    window.start_sculpt()

    assert window.sculpt_bar.warning.text(), "die Figur ist für diesen Pinsel zu grob"
    assert window.sculpt_bar.refine.isVisibleTo(window.sculpt_bar)


def test_the_button_makes_the_mesh_fine_enough_for_the_brush(window: MainWindow) -> None:
    """Und zwar fein genug, ohne zu fragen, wie fein.

    Die Kantenlänge folgt aus dem eingestellten Radius über dieselbe Schwelle,
    die die Warnung auslöst. Sie zu erfragen hieße, dem Nutzer eine Zahl
    abzuverlangen, die das Fenster ausrechnen kann.
    """
    with_a_body(window)
    window.sculpt_bar.radius.setValue(1.0)
    window.start_sculpt()

    window.sculpt_bar.refine.click()
    window.session.wait_for_idle()

    assert [entry.op for entry in window.session.project.document.ops][-1] == "remesh_uniform"
    mesh = window._sculpt_mesh(str(window.object_tree.selected()))
    assert mesh is not None
    assert window._sculpt_resolution_hint(mesh) == "", "die Warnung ist behoben, nicht verschoben"
    assert window.sculpting(), "die Sitzung läuft weiter — kein Umweg über das Beenden"


def test_the_button_goes_when_the_warning_goes(window: MainWindow) -> None:
    """Ein Knopf ohne Anlass ist ein Angebot, das ins Leere führt."""
    with_a_body(window)
    window.sculpt_bar.radius.setValue(1.0)
    window.start_sculpt()
    window.sculpt_bar.refine.click()
    window.session.wait_for_idle()

    mesh = window._sculpt_mesh(str(window.object_tree.selected()))
    assert mesh is not None
    window.sculpt_bar.show_warning(window._sculpt_resolution_hint(mesh), refinable=True)

    assert not window.sculpt_bar.refine.isVisibleTo(window.sculpt_bar)


def test_the_thin_wall_warning_gets_no_button(window: MainWindow) -> None:
    """Denn Vernetzen macht eine dünne Wand nicht dicker.

    Beide Warnungen teilen sich dasselbe Feld; nur eine hat eine Handlung, die
    von hier aus richtig ist. Deshalb sagt der Aufrufer es und nicht der Text.
    """
    with_a_body(window)
    window.start_sculpt()
    window.sculpt_bar.show_warning("Die Wand wird zu dünn.", refinable=False)

    assert window.sculpt_bar.warning.text()
    assert not window.sculpt_bar.refine.isVisibleTo(window.sculpt_bar)


def test_dragging_paints_strokes_with_spacing(window: MainWindow) -> None:
    """§18.11: Ein Grat ist ein Zug, nicht zwanzig Klicks — der gedrückte
    Zeiger malt, und der Mindestabstand (halber Pinselradius) hält die
    Zugzahl im Zaum, ohne einen frischen Ansatz zu schlucken."""
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    view = window.viewport
    window.sculpt_bar.radius.setValue(8.0)
    view.set_brush_radius(8.0)

    walked = iter(
        [
            (0.0, 0.0, 0.0),  # frischer Ansatz: erster Zug sitzt immer
            (1.0, 0.0, 0.0),  # unter 4 mm zum letzten Zug: geschluckt
            (6.0, 0.0, 0.0),  # über 4 mm: der zweite Zug
            (6.5, 0.0, 0.0),  # neuer Ansatz daneben: sitzt trotz Nähe
        ]
    )
    view._world_at = lambda x, y: next(walked)  # type: ignore[method-assign]

    view._on_paint_drag(0, 0, True)
    view._on_paint_drag(1, 0, False)
    view._on_paint_drag(2, 0, False)
    assert len(window._sculpt_strokes) == 2, "der Mindestabstand schluckt den Zwischenpunkt"

    view._on_paint_drag(3, 0, True)
    assert len(window._sculpt_strokes) == 3, "ein frischer Ansatz beginnt ohne Altlast"
