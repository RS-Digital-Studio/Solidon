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
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from app.core.geom.sculpt import strokes_from_text
from app.ui.main_window import MainWindow
from app.ui.session import Session
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window
from tests.ui_helpers import with_a_body

MESHES = Path(__file__).parent / "data" / "meshes"


# --- hinein und heraus ----------------------------------------------------------


@pytest.fixture
def exact_body(window: MainWindow) -> str:
    """Ein unvernetzter Quader für die tatsächlichen Konvertierungswege."""
    from app.core.scene.history import OperationDraft
    from tests.helpers import exact_kernel

    exact_kernel()
    assert window.session.apply(
        "Quader",
        [OperationDraft("create_brep_box", params={"width": 20.0, "depth": 20.0, "height": 20.0})],
    )
    assert window.session.wait_for_idle(30_000)
    identifier = next(iter(window.session.last_result.scene.objects))
    window.object_tree.select_object(identifier)
    return identifier


def test_exact_sculpt_requires_the_latest_strokes_and_symmetry_before_finishing(
    window: MainWindow, exact_body: str
) -> None:
    """Frühes Fertig schreibt nichts; neue Gesten entwerten die alte Vorschau
    sofort — samt dem Klick, der an ihr hing."""
    window.start_sculpt(exact_body)
    before = len(window.session.project.document.ops)
    # Der vernetzte Quader hat acht Ecken und sonst keinen Punkt: Ein Zug
    # bewegt nur, was in seinem Radius liegt — also an eine Ecke, nicht in die
    # Luft daneben und nicht auf die Mitte einer Fläche ohne Punkt.
    window._on_sculpt((10.0, 10.0, 20.0))
    first = window._preview_approval
    assert first is not None and first.owner is window.sculpt_bar.done
    # **Warten ist keine Sperre** (Entscheidung Robert, 21.09.2026): Der Knopf
    # bleibt frei, ein Klick vor dem Bild bindet sich an die Freigabe.
    assert window.sculpt_bar.done.isEnabled()
    window.finish_sculpt()
    assert first.pending_click is not None
    assert window.sculpting() and len(window.session.project.document.ops) == before
    window._on_sculpt((-10.0, 10.0, 20.0))
    window.sculpt_bar.symmetry.setCurrentIndex(1)
    latest = window._preview_approval
    assert latest is not first and latest.pending_click is None
    assert window.sculpt_bar.done.isEnabled()
    assert window.session.wait_for_idle(30_000)
    assert latest.displayed and window.sculpt_bar.done.isEnabled()
    assert window.sculpting() and len(window.session.project.document.ops) == before
    assert "geraden Teilstücken" in window.viewport._preview_note
    prepared = latest.order.drafts[0]
    assert len(strokes_from_text(prepared.params["strokes"])) == 2
    assert prepared.params["symmetry"] == "x"
    window.sculpt_bar.done.click()
    assert window.session.wait_for_idle(30_000)
    assert not window.sculpting()
    assert window.session.project.document.ops[-1].params == prepared.params
    assert window.session.last_result.scene.objects[exact_body].kind == "mesh"
    window.session.undo()
    assert window.session.wait_for_idle(30_000)
    assert window.session.last_result.scene.objects[exact_body].kind == "brep"


def test_exact_refinement_waits_for_the_current_brush_without_auto_applying(
    window: MainWindow, exact_body: str
) -> None:
    """Die bestehende Vernetzungshandlung übernimmt nur ihren zuletzt geprüften Radius."""
    window.start_sculpt(exact_body)
    before = len(window.session.project.document.ops)
    window.refine_for_sculpt()
    first = window._preview_approval
    assert first is not None and first.owner is window.sculpt_bar.refine
    first_edge = first.order.drafts[0].params["edge"]
    window.refine_for_sculpt()
    assert len(window.session.project.document.ops) == before
    assert first.pending_click is not None, "der frühe Klick wartet auf das Bild"
    window.sculpt_bar.radius.set_value_mm(8.0)
    latest = window._preview_approval
    assert latest is not first and latest.order.drafts[0].params["edge"] > first_edge
    # Der neue Radius entwertet die alte Vorschau samt dem Klick, der an ihr
    # hing; der Knopf bleibt frei (Warten ist keine Sperre).
    assert latest.pending_click is None and window.sculpt_bar.refine.isEnabled()
    assert window.session.wait_for_idle(30_000)
    assert latest.displayed and window.sculpt_bar.refine.isEnabled()
    assert len(window.session.project.document.ops) == before
    window.sculpt_bar.refine.click()
    assert window.session.wait_for_idle(30_000)
    assert window.sculpting()
    assert window.session.project.document.ops[-1].params == latest.order.drafts[0].params
    assert window.session.last_result.scene.objects[exact_body].kind == "mesh"


def test_an_early_finish_waits_for_the_conversion_preview_and_closes_once(
    window: MainWindow, exact_body: str
) -> None:
    """*Fertig* vor dem Bild verfällt nicht: Es läuft, sobald die Vorschau
    steht — und genau einmal (Entscheidung Robert, 21.09.2026)."""
    window.start_sculpt(exact_body)
    before = len(window.session.project.document.ops)
    window._on_sculpt((10.0, 10.0, 20.0))
    window.finish_sculpt()
    approval = window._preview_approval
    assert approval is not None and approval.pending_click is not None
    assert window.sculpting() and len(window.session.project.document.ops) == before
    assert window.session.wait_for_idle(30_000)
    assert not window.sculpting()
    assert len(window.session.project.document.ops) == before + 1
    assert window.session.project.document.ops[-1].op == "sculpt_strokes"
    assert window.session.last_result.scene.objects[exact_body].kind == "mesh"


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


def test_a_second_carve_into_the_shown_pit_starts_its_own_stage(
    window: MainWindow, tmp_path: Path
) -> None:
    """RM-456 (Testlücke zu RM-438): Das Fenster reicht die Züge der Sitzung an
    den neuen Zug weiter (``before=self._sculpt_shown()``).

    Ohne sie misst der zweite Zug in die eben gegrabene Mulde gegen die Fläche
    vor der Etappe, greift nichts und heißt verfehlt. Der Kerntest prüft
    ``stroke_at``; dieser prüft den Anschluss im Fenster — bisher blieben alle
    Fenstertests grün, wenn ``before`` fehlte.
    """
    import numpy as np
    import trimesh

    from app.core.geom.sculpt import apply_strokes

    # Eine fein vernetzte Kugel wie im Kerntest: An der Figur liegt unter einer
    # 4 mm tiefen Mulde schnell die Gegenseite eines Arms im Pinselradius.
    ball = tmp_path / "kugel.stl"
    trimesh.creation.icosphere(subdivisions=4, radius=20.0).export(ball)
    window.open_path(ball)
    assert window.session.wait_for_idle(60_000)
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    object_id = window.object_tree.selected()
    assert object_id
    window.start_sculpt(str(object_id))
    bar = window.sculpt_bar
    bar.tool.setCurrentIndex(bar.tool.findData("carve"))
    bar.radius.set_value_mm(3.0)
    bar.strength.set_value_mm(4.0)
    mesh = window._sculpt_mesh(window._sculpt_target)
    assert mesh is not None
    points = np.asarray(mesh.raw.vertices, dtype=float)
    index = int(np.argmax(points[:, 0]))

    window._on_sculpt(tuple(points[index]))
    shown = apply_strokes(mesh, window._sculpt_shown())
    bottom = tuple(float(value) for value in np.asarray(shown.raw.vertices)[index])
    window._on_sculpt(bottom)

    first, second = window._sculpt_strokes
    assert not first.cut
    assert second.cut, "der Zug in die gezeigte Mulde beginnt eine eigene Etappe"


def test_the_preview_does_not_redo_the_whole_session_after_each_stroke(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-366: Nach jedem Klick rechnete die Vorschau alle Etappen der Sitzung
    neu, im Oberflächen-Thread — an einer Figur mit 145 742 Ecken 5,8 s nach
    dem vierzigsten Zug im Wechsel von Auftragen und Glätten, ohne Abbrechen.
    Jetzt baut ein Klick höchstens eine Etappe, und das Bild ist bitgleich mit
    dem, was die Operation aus denselben Zügen rechnet."""
    import numpy as np

    from app.core.geom import sculpt

    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    mesh = window._sculpt_mesh(object_id)
    assert mesh is not None
    crown = mesh.bounds.maximum
    built = 0
    real = sculpt._Stage.__init__

    def counted(self: object, *args: object, **kwargs: object) -> None:
        nonlocal built
        built += 1
        real(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(sculpt._Stage, "__init__", counted)
    bar = window.sculpt_bar
    clicks = 40
    for click in range(clicks):
        bar.tool.setCurrentIndex(bar.tool.findData("smooth" if click % 2 else "draw"))
        window._on_sculpt((0.0, 0.0, float(crown[2])))

    assert len(sculpt.stages(window._sculpt_shown())) == clicks, "jeder Zug eine Etappe"
    assert built <= clicks + 2, f"{built} Etappen gebaut für {clicks} Klicks"
    preview = window._sculpt_preview
    assert preview is not None
    expected = sculpt.apply_strokes(mesh, window._sculpt_shown())
    assert np.array_equal(np.asarray(preview.shown.raw.vertices), np.asarray(expected.raw.vertices))


def test_the_session_mirror_reaches_the_stage_decision_in_the_window(
    window: MainWindow, tmp_path: Path
) -> None:
    """RM-454 im Fenster: Die Leiste *Symmetrie* liegt über allen Zügen; ob ein
    Zug eine eigene Etappe braucht, fragt jetzt auch sein Spiegelbild. Am
    schiefen Prisma greift ein Klick auf die rechte Wand selbst nichts, sein
    Spiegelbild aber genau die Mulde, die der Zug davor links gegraben hat."""
    import numpy as np
    import trimesh

    from tests.test_sculpt import lopsided_prism

    path = tmp_path / "prisma.stl"
    path.write_bytes(trimesh.exchange.stl.export_stl(lopsided_prism().raw))
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    object_id = str(next(iter(window.session.last_result.scene.objects)))
    mesh = window._sculpt_mesh(object_id)
    assert mesh is not None
    shift = np.asarray(mesh.raw.bounds[0], dtype=float) - np.array([-10.0, -10.0, -10.0])
    window.start_sculpt(object_id)
    bar = window.sculpt_bar
    bar.symmetry.setCurrentIndex(bar.symmetry.findData("x"))
    bar.tool.setCurrentIndex(bar.tool.findData("carve"))
    bar.radius.set_value_mm(0.4)
    bar.strength.set_value_mm(1.0)

    window._on_sculpt(tuple(float(value) for value in np.array([-10.0, 0.0, 0.0]) + shift))
    window._on_sculpt(tuple(float(value) for value in np.array([9.0, 0.0, 0.0]) + shift))

    first, second = window._sculpt_strokes
    assert not first.cut
    assert second.cut, "nur das Spiegelbild greift — auf der Fläche nach der ersten Etappe"


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


@pytest.mark.parametrize("language", ["en", "es", "fr", "it", "pt"])
def test_the_brush_strength_is_not_named_like_a_wall_thickness(
    qt_app: QApplication, language: str
) -> None:
    """„Stärke" heißt in der Leiste Pinselstärke, nicht Wandstärke.

    Der allgemeine Schlüssel steht für Maße wie die Stärke eines Halters und
    ist mit „Thickness" übersetzt; die Formleiste las sich so, als stelle sie
    eine Wanddicke ein. Beschriftung und Name für den Bildschirmleser tragen
    deshalb den Kontext „Pinsel".
    """
    from PySide6.QtWidgets import QLabel

    from app.i18n import set_language
    from app.i18n.catalog import install_language, read_catalog
    from app.ui.sculpt_bar import SculptBar

    catalog = read_catalog(language)
    brush = catalog["Pinsel\x04Stärke"]
    assert brush != catalog["Stärke"]
    install_language(language)
    set_language(language)
    try:
        bar = SculptBar()
        try:
            labels = {label.text() for label in bar.findChildren(QLabel)}
            assert brush in labels and catalog["Stärke"] not in labels
            assert bar.strength.accessibleName() == brush
        finally:
            bar.deleteLater()
    finally:
        install_language("de")
        set_language("de")


def test_a_narrow_sculpt_bar_moves_its_tail_into_a_second_row(qt_app: QApplication) -> None:
    """Ist die Leiste zu schmal, rücken Zustand und *Fertig* in eine zweite Zeile.

    Am echten Fenster (1 100 Punkte breit, Fensterabnahme 04.10.2026, RM-366)
    stand die Leiste in einer Zeile und kürzte jedes Wort: „Auftrage“,
    „Neu ansetze“, „2 Züge, eine Eta“. Ein halbes Wort ist schlechter als eine
    zweite Zeile. Breit wird sie wieder eine Zeile, und ihre Wunschbreite bleibt
    die der einen Zeile — sonst wüchse sie nie zurück (``ansicht.md``).
    """
    from PySide6.QtWidgets import QWidget

    from app.ui.sculpt_bar import SculptBar

    # Im Fenster ist die Leiste ein Kind und bekommt die Breite, die die
    # untere Zone hat — auch weniger als ihr Mindestmaß. Ein Fenster der
    # obersten Ebene klemmte sie dagegen an ihr Mindestmaß.
    host = QWidget()
    bar = SculptBar(host)
    try:
        bar.show_count(2, 1)
        host.resize(3000, 400)
        host.show()
        QApplication.processEvents()
        roomy = bar.sizeHint().width()
        bar.setGeometry(0, 0, roomy + 40, 200)
        QApplication.processEvents()
        assert abs(bar.done.y() - bar.tool.y()) < bar.tool.height(), "breit eine Zeile"
        bar.setGeometry(0, 0, int(roomy * 0.6), 200)
        QApplication.processEvents()
        assert bar.done.y() > bar.tool.y() + bar.tool.height() // 2, (
            "Fertig steht in der zweiten Zeile"
        )
        assert bar.state.y() > bar.tool.y() + bar.tool.height() // 2
        assert bar.sizeHint().width() >= roomy, "die Wunschbreite bleibt die einer Zeile"
        bar.setGeometry(0, 0, roomy + 40, 200)
        QApplication.processEvents()
        assert abs(bar.done.y() - bar.tool.y()) < bar.tool.height(), "breit wieder eine Zeile"
    finally:
        host.deleteLater()


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
    assert window.session.wait_for_idle(60_000)
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
    # Seit dem 22.09.2026 rechnet ein Arbeiter (Review Fenster 0.5.0): Die
    # Prüfung kostete an echten Modellen Sekunden im Hauptthread.
    assert window.wait_for_sculpt_check()

    text = window.sculpt_bar.warning.text()
    assert any(char.isdigit() for char in text), f"eine Zahl muss dastehen: {text!r}"


def test_a_solid_body_leaves_the_warning_empty(window: MainWindow) -> None:
    """Die Gegenprobe — sonst warnt jede Sitzung und keine Warnung zählt."""
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window._on_sculpt((0.0, 0.0, 82.0))

    window._check_sculpted_walls()
    assert window.wait_for_sculpt_check()

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


def test_the_wall_check_does_not_hold_the_window(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Wandprüfung stand Sekunden im Hauptthread, nach jedem Zug.

    Gemessen am 22.09.2026 an echten Modellen: 2,7 bis 5,5 s je Prüfung,
    400 ms nach jedem abgesetzten Zug — mit Wartezeiger, ohne Abbrechen, und
    weiterformen ließ sich in der Zeit nicht (Review Fenster 0.5.0). Jetzt
    rechnet ein Arbeiter; die Leiste sagt, dass geprüft wird, und nur die
    Antwort der jüngsten Prüfung zählt.
    """
    import threading
    import time

    import app.ui.main_window as module

    object_id = with_a_thin_shell(window, tmp_path)
    window.start_sculpt(object_id)
    window._on_sculpt((0.0, 0.0, 20.0))
    release = threading.Event()
    real = module.wall_thickness_map

    def slow(*args: Any, **kwargs: Any) -> Any:
        release.wait(10)
        return real(*args, **kwargs)

    monkeypatch.setattr(module, "wall_thickness_map", slow)

    # Der Hinweis auf ein zu grobes Netz hat Vorrang vor „wird geprüft"; hier
    # geht es um die Zeile, die sonst leer stünde.
    window.sculpt_bar.show_warning("")
    started = time.perf_counter()
    window._check_sculpted_walls()
    assert time.perf_counter() - started < 1.0, "the check ran in the main thread"
    assert window.sculpt_bar.warning.text() == "Wandstärke wird geprüft …"

    # Ein weiterer Zug macht die laufende Prüfung wertlos.
    stale = window._sculpt_wall_number
    window._on_sculpt((0.0, 0.0, 20.0))
    window._check_sculpted_walls()
    assert window._sculpt_wall_number > stale

    release.set()
    assert window.wait_for_sculpt_check()
    text = window.sculpt_bar.warning.text()
    assert any(char.isdigit() for char in text), f"the latest answer must stand: {text!r}"

    window._sculpt_walls_checked(stale, 0)
    assert window.sculpt_bar.warning.text() == text, "an old answer must not overwrite it"


def with_a_plate(window: MainWindow, tmp_path: Path) -> str:
    """Eine 4-mm-Platte, fein genug vernetzt für einen 6-mm-Pinsel, geöffnet
    wie eine Datei des Kunden."""
    import trimesh

    box = trimesh.creation.box(extents=(40.0, 40.0, 4.0))
    vertices, faces = trimesh.remesh.subdivide_to_size(box.vertices, box.faces, max_edge=0.8)
    path = tmp_path / "platte.stl"
    path.write_bytes(trimesh.exchange.stl.export_stl(trimesh.Trimesh(vertices, faces)))
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    object_id = next(iter(window.session.last_result.scene.objects))
    return str(object_id)


def test_taking_back_the_piercing_stroke_is_one_undoable_step(
    window: MainWindow, tmp_path: Path
) -> None:
    """*Zug zurücknehmen* am Durchstich im Prüfbericht nimmt genau den Zug aus
    der Sitzung, der die Wand durchstochen hat — eine Transaktion, die
    Strg+Z zurückholt (RM-419). Vorher stand „zurücknehmen“ nur im Satz."""
    from app.core.geom.sculpt import strokes_to_text
    from app.core.scene.history import OperationDraft
    from app.core.types import Stroke

    object_id = with_a_plate(window, tmp_path)
    low, high = window.session.last_result.scene.objects[object_id].mesh.raw.bounds
    middle = (low + high) / 2.0
    top = float(high[2])
    harmless = Stroke(
        point=(float(low[0]) + 3.0, float(low[1]) + 3.0, top),
        normal=(0.0, 0.0, 1.0),
        radius=2.0,
        strength=0.3,
    )
    piercing = Stroke(
        point=(float(middle[0]), float(middle[1]), top),
        normal=(0.0, 0.0, 1.0),
        radius=6.0,
        strength=6.0,
        tool="carve",
    )
    assert window.session.apply(
        "Formen",
        [
            OperationDraft(
                op="sculpt_strokes",
                inputs=(object_id,),
                params={"strokes": strokes_to_text([harmless, piercing])},
            )
        ],
    )
    assert window.session.wait_for_idle(30_000)
    report = window.report
    item = next(
        report.list.item(row)
        for row in range(report.list.count())
        if getattr(report.list.item(row).data(256), "code", "") == "sculpt.pierced"
    )

    report._run_action_for(item, "take_back_stroke")
    assert window.session.wait_for_idle(30_000)

    sculpt = window.session.project.document.ops[-1]
    assert strokes_from_text(sculpt.params["strokes"]) == [harmless]
    assert "sculpt.pierced" not in {
        f.code for f in window.session.last_result.scene.report.findings
    }
    assert "Strg+Z" in window.status_message.text()

    window.session.undo()
    assert window.session.wait_for_idle(30_000)
    restored = window.session.project.document.ops[-1]
    assert len(strokes_from_text(restored.params["strokes"])) == 2


def test_the_export_says_a_stroke_pierced_the_wall(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Durchstich stand im Prüfbericht, der Export schrieb ohne Hinweis
    (RM-419). Jetzt fragt der Export davor und nennt ihn."""
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from app.core.geom.sculpt import strokes_to_text
    from app.core.scene.history import OperationDraft
    from app.core.types import Stroke
    from app.i18n import tr
    from tests.ui_helpers import wait_for_export

    object_id = with_a_plate(window, tmp_path)
    low, high = window.session.last_result.scene.objects[object_id].mesh.raw.bounds
    middle = (low + high) / 2.0
    piercing = Stroke(
        point=(float(middle[0]), float(middle[1]), float(high[2])),
        normal=(0.0, 0.0, 1.0),
        radius=6.0,
        strength=6.0,
        tool="carve",
    )
    assert window.session.apply(
        "Formen",
        [
            OperationDraft(
                op="sculpt_strokes",
                inputs=(object_id,),
                params={"strokes": strokes_to_text([piercing])},
            )
        ],
    )
    assert window.session.wait_for_idle(30_000)
    target = tmp_path / "platte_geformt.stl"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "STL (*.stl)")),
    )
    seen: list[str] = []

    def cancel(box: QMessageBox) -> int:
        seen.append(box.informativeText())
        next(entry for entry in box.buttons() if entry.text() == tr("Abbrechen")).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", cancel)
    window.action_export()
    # Der Export wartet erst auf die feine Rechnung (RM-426) und prüft dann.
    assert window.session.wait_for_idle(60_000)
    wait_for_export(window)

    assert seen, "der Export schrieb, ohne die durchstochene Wand zu zeigen"
    assert "Wand dahinter" in seen[0], f"der Dialog nennt den Durchstich nicht: {seen[0]!r}"
    assert not target.exists()


# --- Einbacken (Entscheidung D) -------------------------------------------------


def test_baking_and_reopening_keeps_the_face_materials(
    window: MainWindow,
    tmp_path: Path,
) -> None:
    """Festschreiben und Projektdatei behalten die bemalten Dreiecke samt Palette."""
    from app.core.scene import OperationDraft

    session = window.session
    session.history.apply(
        "Zwei Farben",
        [
            OperationDraft(op="create_box", params={"width": 10.0, "depth": 10.0, "height": 10.0}),
            OperationDraft(
                op="assign_slot",
                inputs=("obj_1",),
                params={"slot": 1, "name": "Rot", "colour": "#ff0000"},
            ),
        ],
    )
    initial = session.evaluate_now()
    face = next(
        key
        for key, entry in initial.scene.objects["obj_1"].features.items()
        if entry.kind == "face" and entry.face_indices
    )
    session.history.apply(
        "Fläche und Formsitzung",
        [
            OperationDraft(
                op="paint_slot",
                inputs=("obj_1",),
                params={"slot": 2, "name": "Blau", "colour": "#0000ff", "at_feature": face},
            ),
            OperationDraft(op="sculpt_strokes", inputs=("obj_1",), params={"strokes": ""}),
        ],
    )
    before = session.evaluate_now().scene.objects["obj_1"]
    assert set(before.mesh.slot_indices) == {1, 2}
    operation = session.project.document.ops[-1]
    assert session.bake_strokes(operation.id)
    assert session.wait_for_idle()
    baked = session.evaluate_now().scene.objects["obj_1"]
    assert baked.mesh.slot_indices == before.mesh.slot_indices
    assert baked.material_slots == before.material_slots
    path = tmp_path / "bemalt.p3d"
    session.save_project(path)
    session.open_project(path)
    assert session.wait_for_idle(60_000)
    restored = session.evaluate_now().scene.objects["obj_1"]
    assert restored.mesh.slot_indices == before.mesh.slot_indices
    assert restored.material_slots == before.material_slots


def with_a_cone_session(window: MainWindow) -> tuple[str, int]:
    """Ein Kegelstumpf und eine Formsitzung auf seiner Deckfläche."""
    from app.core.geom.sculpt import strokes_to_text
    from app.core.scene.history import OperationDraft
    from app.core.types import Stroke

    assert window.session.apply(
        "Kegel",
        [
            OperationDraft(
                op="create_cone",
                params={"bottom_diameter": 30.0, "top_diameter": 10.0, "height": 30.0},
            )
        ],
    )
    assert window.session.wait_for_idle(30_000)
    object_id = str(next(iter(window.session.last_result.scene.objects)))
    top = float(window.session.last_result.scene.objects[object_id].mesh.raw.bounds[1][2])
    stroke = Stroke(point=(0.0, 0.0, top), normal=(0.0, 0.0, 1.0), radius=6.0, strength=1.0)
    assert window.session.apply(
        "Formen",
        [
            OperationDraft(
                op="sculpt_strokes",
                inputs=(object_id,),
                params={"strokes": strokes_to_text([stroke])},
            )
        ],
    )
    assert window.session.wait_for_idle(30_000)
    return object_id, window.session.project.document.ops[-1].id


def test_baking_keeps_the_fine_result(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    """RM-365: *Festschreiben* fror das Entwurfsnetz des Fensters ein. An der
    Figur aus Weg 4 standen danach 6 964 statt 9 974 Dreiecke im Export, das
    Volumen 2,6 % weniger, die Form bis 0,94 mm verschoben. Festgeschrieben wird die
    feine Rechnung — sie ist es, die gerechnet wird, und danach stehen dieselben
    Dreiecke und dasselbe Volumen wie in der feinen Auswertung."""
    import threading

    import app.ui.session as session_module

    object_id, op_id = with_a_cone_session(window)
    fine = window.session.evaluate_now().scene.objects[object_id].mesh
    asked: list[str] = []
    real = session_module.evaluate
    caller = threading.get_ident()

    def spied(document: Any, *args: Any, **kwargs: Any) -> Any:
        # Nur die Rechnung des Festschreibens selbst: Die Entwurfsrechnung, die
        # das Fenster danach im Arbeiter startet, lief am Mac schon, bevor hier
        # gezählt wurde, und ist kein Teil der Zusage (RM-531).
        if threading.get_ident() == caller:
            asked.append(str(kwargs.get("quality")))
        return real(document, *args, **kwargs)

    monkeypatch.setattr(session_module, "evaluate", spied)
    assert window.session.bake_strokes(op_id)
    assert asked == ["fine"], "das Festschreiben rechnet fein"
    monkeypatch.setattr(session_module, "evaluate", real)
    assert window.session.wait_for_idle(30_000)

    baked = window.session.evaluate_now().scene.objects[object_id].mesh
    assert baked.triangle_count == fine.triangle_count
    assert baked.volume == pytest.approx(fine.volume, rel=1e-12)


def test_baking_in_the_window_runs_beside_it_and_keeps_the_fine_result(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Weg des Fensters: *Festschreiben* im Verlauf rechnet fein im
    Arbeiter, das Fenster wartet nicht darauf (§2.8), und festgehalten wird
    der feine Stand."""
    import threading
    import time

    import app.ui.session as session_module

    object_id, op_id = with_a_cone_session(window)
    fine = window.session.evaluate_now().scene.objects[object_id].mesh
    release = threading.Event()
    asked: list[str] = []
    real = session_module.evaluate

    def held(document: Any, *args: Any, **kwargs: Any) -> Any:
        asked.append(str(kwargs.get("quality")))
        release.wait(10)
        return real(document, *args, **kwargs)

    monkeypatch.setattr(session_module, "evaluate", held)
    started = time.perf_counter()
    window.bake_sculpt(op_id)
    assert time.perf_counter() - started < 1.0, "das Fenster wartete auf das Festschreiben"
    assert window.session.busy
    release.set()
    assert window.session.wait_for_idle(30_000)
    monkeypatch.setattr(session_module, "evaluate", real)

    assert asked and asked[0] == "fine", "das Festschreiben rechnet fein"
    sculpt = next(entry for entry in window.session.project.document.ops if entry.id == op_id)
    assert sculpt.params["baked"]
    assert "Strg+Z" in window.status_message.text()
    baked = window.session.evaluate_now().scene.objects[object_id].mesh
    assert baked.triangle_count == fine.triangle_count


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


def test_baking_asks_nothing_because_undo_takes_it_back(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 19: Festschreiben ist rücknehmbar — also keine Nachfrage davor.

    Entscheidung D (13.08.2026) stellte eine Nachfrage vor das Einbacken, weil
    es „nicht folgenlos rücknehmbar" sei. Nachgemessen am 22.09.2026 (Review
    Fenster 0.5.0): Das Festschreiben ist ein ``change_params`` und damit
    eine gewöhnliche Transaktion; ein Strg+Z gibt der Sitzung ihre Züge
    zurück, und sie rechnet wieder. Die Voraussetzung der Ausnahme trägt
    nicht, und AGENTS.md Regel 19 kennt seither genau eine: das Löschen im
    Verlauf. Die Folgen stehen jetzt in der Ansage samt Rückweg.
    """
    from PySide6.QtWidgets import QMessageBox

    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window._on_sculpt((0.0, 0.0, 82.0))
    window.finish_sculpt()
    window.session.wait_for_idle()
    sculpt = next(
        entry for entry in window.session.project.document.ops if entry.op == "sculpt_strokes"
    )

    def no_box(*_args: Any, **_kwargs: Any) -> int:
        raise AssertionError("baking must not ask first")

    monkeypatch.setattr(QMessageBox, "exec", no_box)

    window.bake_sculpt(sculpt.id)
    window.session.wait_for_idle()

    baked = next(entry for entry in window.session.project.document.ops if entry.id == sculpt.id)
    assert baked.params["baked"]
    assert "Strg+Z" in window.status_message.text()

    window.session.undo()
    window.session.wait_for_idle()

    live = next(entry for entry in window.session.project.document.ops if entry.id == sculpt.id)
    assert not live.params.get("baked"), "undo gives the session its strokes back"


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
    # Das Vernetzen der Figur dauert unter Last länger als die Vorgabe von 10 s.
    assert window.session.wait_for_idle(120_000)

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
    # Das Vernetzen der Figur dauert unter Last länger als die Vorgabe von 10 s.
    assert window.session.wait_for_idle(120_000)

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


# --- die Anzeigeeinheit endet nicht an der Leiste (§19.3) ------------------------


def test_a_stroke_in_inches_still_reaches_the_core_in_millimetres(
    window: MainWindow,
) -> None:
    """Was der Zug mitnimmt, sind Millimeter — auch wenn das Feld Zoll zeigt.

    Sechs Stellen lasen die Leiste mit ``value()``, also dem Anzeigewert. In
    Zoll lief damit ein Pinsel von 0,2 mm, wo 5 mm eingestellt waren, und das
    ist kein Anzeigefehler: ``stroke_at`` schreibt Geometrie ins Dokument.

    Gefallen ist es niemandem auf, weil kein Test die Leisten je in Zoll fuhr.
    Dieser tut es.
    """
    from app.ui.labels import set_display_unit

    object_id = with_a_body(window)
    window.sculpt_bar.radius.set_value_mm(5.0)
    window.sculpt_bar.strength.set_value_mm(1.0)

    set_display_unit("in")
    window.sculpt_bar.radius.refresh_unit()
    window.sculpt_bar.strength.refresh_unit()
    assert window.sculpt_bar.radius.value() == pytest.approx(5.0 / 25.4, abs=1e-4), (
        "das Feld muss Zoll zeigen, sonst prüft der Test nichts"
    )

    window.start_sculpt(object_id)
    window._on_sculpt((20.0, 0.0, 0.0))

    stroke = window._sculpt_strokes[0]
    assert stroke.radius == pytest.approx(5.0), "der Zug rechnet in Millimetern"
    assert stroke.strength == pytest.approx(1.0)


def test_the_brush_ring_follows_the_slider_in_millimetres(window: MainWindow) -> None:
    """Der Ring ist ein Weltmaß und hängt am Signal, nicht am nächsten Zug.

    ``valueChanged`` trägt die Zahl aus dem Feld; angeschlossen war es dort, und
    in Zoll bekam der Ring ein Fünfundzwanzigstel des Pinsels. ``valueChangedMm``
    trägt dieselbe Nachricht in der Einheit des Kerns.
    """
    from app.ui.labels import set_display_unit

    object_id = with_a_body(window)
    window.start_sculpt(object_id)

    set_display_unit("in")
    window.sculpt_bar.radius.refresh_unit()
    window.sculpt_bar.radius.setValue(0.5)  # ein halber Zoll

    assert window.viewport._brush_radius == pytest.approx(12.7), (
        "der Ring bekam den Anzeigewert statt der Größe"
    )


def test_the_bar_answers_exactly_what_a_stroke_asks_for() -> None:
    """Bauart-Prüfung: ``values()`` und ``stroke_at`` driften nicht auseinander.

    Die Methode stand mit den richtigen Einheiten hier und hatte **keinen
    Aufrufer**, während das Fenster dieselben vier Werte aus den Widgets neu
    zusammenstellte — und dabei ``value()`` nahm. Zwei Wege zu derselben
    Auskunft, und der benutzte war der falsche. Jetzt gibt es einen; dieser Test
    hält ihn fest, damit der zweite nicht wiederkommt.
    """
    import inspect

    from app.core.geom.sculpt import stroke_at
    from app.ui.sculpt_bar import StrokeValues

    accepted = {
        name
        for name, parameter in inspect.signature(stroke_at).parameters.items()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    }
    offered = set(StrokeValues.__annotations__)

    assert offered <= accepted, f"die Leiste bietet, was der Zug nicht nimmt: {offered - accepted}"
    # Und die Namen, die ein Zug zwingend braucht, sind dabei — sonst wäre das
    # Auspacken ein TypeError beim ersten Klick und kein Typfehler beim Prüfen.
    assert {"radius", "strength"} <= offered


def test_baking_freezes_the_state_right_after_the_sculpt_step(window: MainWindow) -> None:
    """Gesamtreview 05.09.2026, UI-17: Festgeschrieben wurde ``last_result``,
    also der Stand am **Ende** des Stapels. Lag nach der Formsitzung noch ein
    Verschieben um 10 mm auf dem Körper, steckte es in der eingebetteten STL
    und lief bei der nächsten Auswertung ein zweites Mal — aus 5…15 wurden
    15…25. Festgeschrieben wird der Stand unmittelbar nach der Formsitzung."""
    from app.core.scene import OperationDraft

    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window._on_sculpt((0.0, 0.0, 82.0))
    window.finish_sculpt()
    window.session.wait_for_idle()
    sculpt = next(
        entry for entry in window.session.project.document.ops if entry.op == "sculpt_strokes"
    )
    window.session.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=(object_id,), params={"dx": 10.0})],
    )
    window.session.wait_for_idle()
    result = window.session.last_result
    assert result is not None
    before = result.scene.objects[object_id].mesh.bounds

    assert window.session.bake_strokes(sculpt.id)
    window.session.wait_for_idle()

    result = window.session.last_result
    assert result is not None
    after = result.scene.objects[object_id].mesh.bounds
    assert after.minimum[0] == pytest.approx(before.minimum[0], abs=0.05), (
        "das Verschieben lief ein zweites Mal"
    )
    assert after.maximum[0] == pytest.approx(before.maximum[0], abs=0.05)


def test_reopened_sculpt_changes_the_same_step_and_undo_restores_three_strokes(
    window: MainWindow,
) -> None:
    """RM-375: Originaleingang, gleicher Schritt, Undo und erneutes Öffnen."""
    import numpy as np

    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    original = window._sculpt_mesh(object_id)
    assert original is not None
    points = np.asarray(original.raw.vertices).copy()
    for point in points[:3]:
        window._on_sculpt(tuple(point))
    window.finish_sculpt()
    assert window.session.wait_for_idle(30_000)
    operation = window.session.project.document.ops[-1]
    step = operation.id
    count = len(window.session.project.document.ops)
    window.edit_operation(step)
    assert window.session.wait_for_idle(30_000)
    assert window.sculpting()
    assert np.array_equal(window._sculpt_source.raw.vertices, points)
    assert len(window._sculpt_strokes) == 3
    assert window.undo_sculpt_stroke()
    window.finish_sculpt()
    assert window.session.wait_for_idle(30_000)
    assert len(window.session.project.document.ops) == count
    assert len(strokes_from_text(window.session.history.operation(step).params["strokes"])) == 2
    window.session.undo()
    assert window.session.wait_for_idle(30_000)
    assert len(strokes_from_text(window.session.history.operation(step).params["strokes"])) == 3
    window.session.redo()
    assert window.session.wait_for_idle(30_000)
    window.edit_operation(step)
    assert window.session.wait_for_idle(30_000)
    assert len(window._sculpt_strokes) == 2
    assert window.undo_sculpt_stroke()
    assert window.undo_sculpt_stroke()
    window.finish_sculpt()
    assert window.session.wait_for_idle(30_000)
    assert len(strokes_from_text(window.session.history.operation(step).params["strokes"])) == 0
    assert len(window.session.project.document.ops) == count


def test_gesture_map_switch_and_late_answer_preserve_the_selected_map(window: MainWindow) -> None:
    """RM-377: Karten gehören zur letzten Wahl und zum jüngsten Zug."""
    from app.core.perceive import maps

    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    chooser = window.sculpt_bar.analysis.choice
    chooser.setCurrentIndex(chooser.findData("overhang"))
    window._check_sculpted_walls()
    assert window.wait_for_sculpt_check()
    assert window.viewport.analysis_map.kind == "overhang"
    assert window.sculpt_bar.analysis.note.text()
    assert window.sculpt_bar.analysis.legend.isVisibleTo(window.sculpt_bar)
    assert window.sculpt_bar.analysis.legend.entries
    assert "Geometrie" in window.sculpt_bar.analysis.legend.note.text()
    assert "Wandstärke wird geprüft" not in window.sculpt_bar.warning.text()
    old = window._sculpt_wall_number
    chooser.setCurrentIndex(chooser.findData("wall"))
    window._check_sculpted_walls()
    assert window.wait_for_sculpt_check()
    assert window.viewport.analysis_map.kind == "wall"
    window._gesture_analysis_ready(old, maps.overhang_map(window._sculpt_preview.shown), [])
    assert window.viewport.analysis_map.kind == "wall"
    chooser.setCurrentIndex(0)
    assert window.viewport.analysis_map is None
    window.finish_sculpt()
    window._gesture_analysis_ready(window._sculpt_wall_number - 1, None, [])
    assert window.viewport.analysis_map is None


def test_stroke_summary_keeps_the_saved_text_without_an_editable_json_field(
    qt_app: QApplication,
) -> None:
    """Der Rohdialog zeigt eine Zusammenfassung und erhält seine Daten."""
    from app.core.geom.sculpt import strokes_to_text
    from app.core.types import Stroke
    from app.ui.op_dialog import StrokeSummary

    text = strokes_to_text([Stroke(point=(0, 0, 0), normal=(0, 0, 1), radius=2, strength=1)])
    field = StrokeSummary(text)
    assert field.value() == text
    assert field.text() == "Ein Zug"
    assert "{" not in field.text()


def test_a_sculpt_preview_outside_the_printer_is_reported(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-377: Die Vorschau und nicht nur der gespeicherte Körper wird geprüft."""
    from dataclasses import replace

    import numpy as np

    object_id = with_a_body(window)
    profile = replace(
        window.session.profile,
        printer=replace(window.session.profile.printer, build_volume=(2.0, 2.0, 2.0)),
    )
    monkeypatch.setattr(Session, "evaluation_profile", property(lambda self: profile))
    window.start_sculpt(object_id)
    point = tuple(np.asarray(window._sculpt_mesh(object_id).raw.vertices)[0])
    window._on_sculpt(point)
    window._check_sculpted_walls()
    assert window.wait_for_sculpt_check()
    assert any(
        word in window.sculpt_bar.analysis.note.text()
        for word in ("Bauraum", "Druckfläche", "Bett")
    )


def test_a_new_sculpt_session_does_not_inherit_the_last_note(window: MainWindow) -> None:
    """Der Befund der vorigen Sitzung gehört ihrem Körper und ihren Zügen.

    Am Mausoleum-Drachen stand nach dem Wiederöffnen des Schritts noch
    „3863 Stellen dünner als 0,84 mm“ aus der Sitzung davor, bevor eine
    Prüfung gelaufen war (Fensterabnahme RM-366).
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window.sculpt_bar.analysis.show_note("12 Stellen dünner als 0,84 mm")
    window.finish_sculpt()
    window.session.wait_for_idle()
    window.start_sculpt(object_id)
    assert window.sculpt_bar.analysis.note.text() == ""


def test_thin_walls_are_named_once_in_the_sculpt_bar(window: MainWindow) -> None:
    """Die Warnzeile nennt zu dünne Stellen; die Kartenzeile wiederholt sie nicht."""
    from dataclasses import replace

    from app.core.perceive import maps

    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    mesh = window._sculpt_preview_for(window._sculpt_mesh(object_id)).shown
    card = maps.wall_thickness_map(mesh, 1.0)
    thin = replace(card, highlighted=(0, 1, 2))
    window._sculpt_wall_number += 1
    number = window._sculpt_wall_number
    window._sculpt_walls_checked(number, 3)
    window._gesture_analysis_ready(number, thin, [])
    warning = window.sculpt_bar.warning.text()
    assert "3" in warning
    assert warning not in window.sculpt_bar.analysis.note.text()


def test_cancelling_a_gesture_check_rejects_its_late_answer(window: MainWindow) -> None:
    """Abbruch lässt die Geste stehen und verhindert eine verspätete Karte."""
    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window.sculpt_bar.analysis.choice.setCurrentIndex(2)
    window._check_sculpted_walls()
    old = window._sculpt_wall_number
    window._cancel_analysis()
    assert window.wait_for_sculpt_check()
    assert window.sculpting()
    assert "abgebrochen" in window.sculpt_bar.analysis.note.text()
    assert window._sculpt_wall_number > old
    assert not window._progress_states["map"].active


def test_reopening_cancel_and_document_change_never_open_a_stale_session(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein alter Eingangsstand darf kein neues Dokument bearbeiten."""
    from copy import deepcopy

    object_id = with_a_body(window)
    window.start_sculpt(object_id)
    window._on_sculpt((20.0, 0.0, 0.0))
    window.finish_sculpt()
    assert window.session.wait_for_idle(30_000)
    step = window.session.project.document.ops[-1].id
    callbacks = []
    monkeypatch.setattr(
        window.session,
        "scene_before_step_async",
        lambda _id, then, **kwargs: callbacks.append(then),
    )
    window.edit_operation(step)
    window.session.project.document = deepcopy(window.session.project.document)
    callbacks.pop()(window.session.last_result.scene)
    assert not window.sculpting()
    assert not window._progress_states["preview"].active


def test_reopened_sculpt_keeps_later_steps_and_survives_saving(
    window: MainWindow, tmp_path: Path
) -> None:
    """Ein späteres Verschieben gehört nicht zum Eingang der gespeicherten Sitzung."""
    import numpy as np

    from app.core.scene.history import OperationDraft

    target = with_a_body(window)
    window.start_sculpt(target)
    original = np.asarray(window._sculpt_mesh(target).raw.vertices).copy()
    window._on_sculpt(tuple(original[0]))
    window._on_sculpt(tuple(original[1]))
    window.finish_sculpt()
    assert window.session.wait_for_idle(30_000)
    step = window.session.project.document.ops[-1].id
    window.session.apply(
        "Verschieben", [OperationDraft("translate_object", inputs=(target,), params={"x": 17.0})]
    )
    assert window.session.wait_for_idle(30_000)
    path = tmp_path / "formen.p3d"
    window.session.save_project(path)
    window.session.open_project(path)
    assert window.session.wait_for_idle(60_000)
    count = len(window.session.project.document.ops)
    window.edit_operation(step)
    assert window.session.wait_for_idle(30_000)
    assert np.array_equal(window._sculpt_source.raw.vertices, original)
    assert window._gesture_scene is not None
    assert len(window._sculpt_strokes) == 2
    window.undo_sculpt_stroke()
    window.finish_sculpt()
    assert window.session.wait_for_idle(30_000)
    assert len(window.session.project.document.ops) == count
    assert window.session.project.document.ops[-1].op == "translate_object"
    assert window.session.project.document.ops[-1].params["x"] == 17.0
    assert window._gesture_scene is None
    window.session.save_project(path)
    window.session.open_project(path)
    assert window.session.wait_for_idle(60_000)
    window.edit_operation(step)
    assert window.session.wait_for_idle(30_000)
    assert len(window._sculpt_strokes) == 1


def test_finishing_an_unchanged_reopened_sculpt_does_not_add_an_undo_step(
    window: MainWindow,
) -> None:
    """Öffnen und Schließen ist keine Dokumentänderung."""
    target = with_a_body(window)
    window.start_sculpt(target)
    window._on_sculpt((20.0, 0.0, 0.0))
    window.finish_sculpt()
    assert window.session.wait_for_idle(30_000)
    step = window.session.project.document.ops[-1].id
    before = len(window.session.project.document.transactions)
    window.edit_operation(step)
    assert window.session.wait_for_idle(30_000)
    window.finish_sculpt()
    assert window.session.wait_for_idle(30_000)
    assert len(window.session.project.document.transactions) == before


def _begin_unsaved_gesture(window: MainWindow, kind: str, target: str) -> None:
    """Drei reale Editoreinstiege mit je einer noch nicht übernommenen Geste."""
    if kind == "sculpt":
        window.start_sculpt(target)
        window._on_sculpt((20.0, 0.0, 0.0))
    elif kind == "pose":
        window.start_armature(target)
        window._on_bone_point((0.0, 0.0, 0.0))
        window._on_bone_point((0.0, 0.0, 10.0))
    else:
        from app.core.sketch import shapes
        from app.core.sketch.serialize import sketch_to_text

        window.start_sketch("sketch_extrude", text=sketch_to_text(shapes.rectangle(20.0, 10.0)))


@pytest.mark.parametrize("kind", ["sculpt", "pose", "sketch"])
def test_project_switch_cancel_and_discard_include_local_gestures(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Auch bei sauber gespeicherter Datei schützt die Wechselabfrage lokale Gesten."""
    target = with_a_body(window)
    window.session.save_project(tmp_path / "vorher.p3d")
    _begin_unsaved_gesture(window, kind, target)
    assert not window.session.modified
    assert window._has_unsaved_gestures()
    monkeypatch.setattr("app.ui.main_window.confirm_unsaved", lambda *args: "cancel")
    assert not window._may_discard()
    assert window._has_unsaved_gestures()
    monkeypatch.setattr("app.ui.main_window.confirm_unsaved", lambda *args: "discard")
    assert window._may_discard()
    window.session.start_new()
    assert not window._has_unsaved_gestures()
    assert not window.sculpting() and not window.setting_armature()
    assert window._sketch_panel is None and window._discarded_sketch is None
    assert window._gesture_scene is None
    assert window.viewport.analysis_map is None


@pytest.mark.parametrize("kind", ["sculpt", "pose", "sketch"])
def test_save_before_project_switch_waits_for_the_gesture_result_dialog(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Speichern darf die offenen Knochen/Zeichnungen nicht als gesichert ausgeben."""
    from PySide6.QtTest import QTest

    target = with_a_body(window)
    path = tmp_path / "gespeichert.p3d"
    window.session.save_project(path)
    before = len(window.session.project.document.ops)
    _begin_unsaved_gesture(window, kind, target)
    monkeypatch.setattr("app.ui.main_window.confirm_unsaved", lambda *args: "save")
    permitted = window._may_discard()
    if kind == "sculpt":
        assert permitted
    else:
        assert not permitted
        dialog = window._op_dialog
        assert dialog is not None
        assert window._has_unsaved_gestures()
        assert len(window.session.project.document.ops) == before
        QTest.qWait(350)
        # Mit der Frist der übrigen Tests dieser Datei: Auf dem Intel-Mac-Runner
        # reichten die zehn Sekunden der Vorgabe nicht (RM-531).
        assert window.session.wait_for_idle(30_000)
        dialog.accept()
        assert window.session.wait_for_idle(30_000)
        assert not window._has_unsaved_gestures()
        assert window._may_discard()
    assert window.session.wait_for_idle()
    assert not window.session.modified
    assert len(window.session.project.document.ops) == before + 1
    window.session.open_project(path)
    assert window.session.wait_for_idle(60_000)
    assert len(window.session.project.document.ops) == before + 1


@pytest.mark.parametrize("kind", ["sculpt", "pose", "sketch"])
def test_incoming_project_change_clears_all_local_gesture_state(
    window: MainWindow, kind: str
) -> None:
    """Ein von der Sitzung gemeldeter Wechsel hinterlässt keine Ziele des Vorgängers."""
    target = with_a_body(window)
    _begin_unsaved_gesture(window, kind, target)
    window.session.start_new()
    assert not window._has_unsaved_gestures()
    assert window._sketch_panel is None and window._sculpt_target is None
    assert window._armature_target is None and window._pose_report_target is None
    assert not window.restore_discarded_sketch()


def test_background_sculpt_orders_pending_strokes_and_finishes_once(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Schnelle Folgeklicks und frühes Fertig bilden genau eine geordnete Sitzung."""
    from threading import Event

    import app.ui.main_window as module

    target = with_a_body(window)
    monkeypatch.setattr(MainWindow, "_sculpt_needs_worker", staticmethod(lambda mesh: True))
    window.start_sculpt(target)
    assert window.wait_for_sculpt_preview()
    entered, proceed = Event(), Event()
    original = module.stroke_at

    def held(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        assert proceed.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "stroke_at", held)
    before = len(window.session.project.document.ops)
    window._on_sculpt((20.0, 0.0, 0.0))
    assert entered.wait(2)
    window._on_sculpt((0.0, 20.0, 0.0))
    window._on_sculpt((-20.0, 0.0, 0.0))
    assert window.undo_sculpt_stroke()
    window.finish_sculpt()
    assert window.sculpting()
    assert len(window.session.project.document.ops) == before
    proceed.set()
    assert window.wait_for_sculpt_preview()
    assert window.session.wait_for_idle()
    assert not window.sculpting()
    assert len(window.session.project.document.ops) == before + 1
    strokes = strokes_from_text(window.session.project.document.ops[-1].params["strokes"])
    assert [stroke.point for stroke in strokes] == [(20.0, 0.0, 0.0), (0.0, 20.0, 0.0)]
    window.session.undo()
    assert window.session.wait_for_idle()
    assert len(window.session.project.document.ops) == before


def test_background_sculpt_cancellation_and_project_change_reject_late_answers(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein abgebrochener Arbeiter darf weder zählen noch in das neue Projekt zeichnen."""
    from threading import Event

    import app.ui.main_window as module

    target = with_a_body(window)
    monkeypatch.setattr(MainWindow, "_sculpt_needs_worker", staticmethod(lambda mesh: True))
    window.start_sculpt(target)
    assert window.wait_for_sculpt_preview()
    entered, proceed = Event(), Event()
    original = module.stroke_at

    def held(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        assert proceed.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "stroke_at", held)
    window._on_sculpt((20.0, 0.0, 0.0))
    assert entered.wait(2)
    worker = window._sculpt_preview_worker
    number = window._sculpt_preview_number
    window._cancel_preview_run()
    assert window.sculpting()
    assert not window._sculpt_pending and not window._sculpt_strokes
    window.session.start_new()
    proceed.set()
    assert worker.wait(5000)
    QApplication.processEvents()
    window._sculpt_preview_received(worker, number, None, [], 1.0)
    assert window._sculpt_preview_worker is None
    assert not window.sculpting()
    assert not window.session.project.document.ops
    assert not window._progress_states["preview"].active


def test_saving_after_removing_every_reopened_stroke_preserves_the_empty_edit(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch das Löschen der letzten Geste ist eine ungesicherte Änderung."""
    target = with_a_body(window)
    window.start_sculpt(target)
    window._on_sculpt((20.0, 0.0, 0.0))
    window.finish_sculpt()
    assert window.session.wait_for_idle()
    step = window.session.project.document.ops[-1].id
    window.session.save_project(tmp_path / "leer.p3d")
    window.edit_operation(step)
    assert window.session.wait_for_idle()
    assert not window._has_unsaved_gestures()
    window.undo_sculpt_stroke()
    assert window._has_unsaved_gestures()
    monkeypatch.setattr("app.ui.main_window.confirm_unsaved", lambda *args: "save")
    assert window._may_discard()
    assert window.session.wait_for_idle()
    assert not strokes_from_text(window.session.history.operation(step).params["strokes"])


def test_saving_does_not_discard_a_half_drawn_bone(window: MainWindow, tmp_path: Path) -> None:
    """Ein gesetztes Gelenk wartet auf sein Ende oder ein ausdrückliches Verwerfen."""
    target = with_a_body(window)
    window.session.save_project(tmp_path / "knochen.p3d")
    window.start_armature(target)
    window._on_bone_point((0.0, 0.0, 0.0))
    window.action_save()
    assert window._armature_head is not None
    assert window._has_unsaved_gestures()
    assert "Ende des Knochens" in window._announcement


@pytest.mark.parametrize("new_tool", ["sculpt", "pose", "sketch", "cancel"])
def test_loading_a_saved_gesture_cannot_replace_a_newer_tool(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, new_tool: str
) -> None:
    """Ein neuer Werkzeugstart oder Abbruch entwertet die alte Eingangsabfrage."""
    target = with_a_body(window)
    window.start_sculpt(target)
    window._on_sculpt((20.0, 0.0, 0.0))
    window.finish_sculpt()
    assert window.session.wait_for_idle()
    callbacks = []
    monkeypatch.setattr(
        window.session,
        "scene_before_step_async",
        lambda step, then, **kwargs: callbacks.append(then),
    )
    window.edit_operation(window.session.project.document.ops[-1].id)
    if new_tool == "cancel":
        window._cancel_preview_run()
    else:
        _begin_unsaved_gesture(window, new_tool, target)
    callbacks.pop()(window.session.last_result.scene)
    assert window._gesture_scene is None
    assert (window._sculpt_target is not None) == (new_tool == "sculpt")
    assert (window._armature_target is not None) == (new_tool == "pose")
    assert (window._sketch_panel is not None) == (new_tool == "sketch")


def test_refining_a_reopened_sculpt_inserts_before_it_and_keeps_local_strokes(
    window: MainWindow,
) -> None:
    """*Dreiecke jetzt angleichen* verfeinert den Eingang, nicht den später verschobenen Stand."""
    from app.core.scene.history import OperationDraft

    target = with_a_body(window)
    window.start_sculpt(target)
    window._on_sculpt((20.0, 0.0, 0.0))
    window.finish_sculpt()
    assert window.session.wait_for_idle()
    step = window.session.project.document.ops[-1].id
    window.session.apply(
        "Verschieben", [OperationDraft("translate_object", inputs=(target,), params={"x": 17.0})]
    )
    assert window.session.wait_for_idle()
    window.edit_operation(step)
    assert window.session.wait_for_idle()
    count = window._sculpt_source.triangle_count
    window._on_sculpt((0.0, 20.0, 0.0))
    window.sculpt_bar.radius.setValue(6.0)
    window.refine_for_sculpt()
    assert window.session.wait_for_idle()
    assert window.wait_for_sculpt_preview()
    assert window.sculpting()
    assert len(window._sculpt_strokes) == 2
    assert window._sculpt_source.triangle_count > count
    entries = window.session.project.document.ops
    assert [entry.op for entry in entries[-3:]] == [
        "remesh_uniform",
        "sculpt_strokes",
        "translate_object",
    ]
    assert window._sculpt_step == entries[-2].id
    assert window.session.inserting is None
    window.finish_sculpt()
    assert window.session.wait_for_idle()
    assert len(strokes_from_text(window.session.project.document.ops[-2].params["strokes"])) == 2
    assert window.session.project.document.ops[-1].params["x"] == 17.0


@pytest.mark.parametrize("kind", ["sculpt", "pose"])
def test_the_undo_menu_reaches_the_local_gesture_and_never_removes_the_import(
    window: MainWindow, kind: str
) -> None:
    """Menü und Strg+Z sind derselbe erreichbare Rückweg, auch nach dem letzten Zug."""
    target = with_a_body(window)
    before = len(window.session.project.document.ops)
    _begin_unsaved_gesture(window, kind, target)
    assert window.undo_action.isEnabled()
    window.undo_action.trigger()
    assert not window._sculpt_strokes and not window._armature_bones
    assert not window.undo_action.isEnabled()
    window.action_undo()
    assert len(window.session.project.document.ops) == before


@pytest.mark.parametrize("kind", ["sculpt", "pose", "sketch"])
@pytest.mark.parametrize("batch", [False, True])
def test_import_during_a_gesture_keeps_the_editor_and_its_input(
    window: MainWindow, kind: str, batch: bool
) -> None:
    """Ablegen und Mehrfachimport ersetzen nicht die Fläche einer laufenden Geste."""
    target = with_a_body(window)
    _begin_unsaved_gesture(window, kind, target)
    count = len(window.session.project.document.ops)
    if batch:
        window.import_paths([MESHES / "clean_figure.stl"])
    else:
        window.open_path(MESHES / "clean_figure.stl")
    assert len(window.session.project.document.ops) == count
    assert window._has_unsaved_gestures()
    assert "aktuelle Änderung" in window._announcement


def test_reopened_sculpt_keeps_maps_and_edits_when_a_later_step_consumes_the_body(
    window: MainWindow,
) -> None:
    """Auch ein im Endstand gelöschter Körper bleibt an seinem Formschnitt bearbeitbar."""
    from app.core.scene.history import OperationDraft

    target = with_a_body(window)
    window.start_sculpt(target)
    window._on_sculpt((20.0, 0.0, 0.0))
    window.finish_sculpt()
    assert window.session.wait_for_idle()
    step = window.session.project.document.ops[-1].id
    window.session.apply("Entfernen", [OperationDraft("delete_object", inputs=(target,))])
    assert window.session.wait_for_idle()
    assert target not in window.session.last_result.scene.objects
    window.edit_operation(step)
    assert window.session.wait_for_idle()
    assert window.sculpting()
    window.sculpt_bar.analysis.choice.setCurrentIndex(2)
    window._check_sculpted_walls()
    assert window.wait_for_sculpt_check()
    assert window.viewport.analysis_map is not None
    window._on_sculpt((0.0, 20.0, 0.0))
    window.finish_sculpt()
    assert window.session.wait_for_idle()
    assert len(strokes_from_text(window.session.history.operation(step).params["strokes"])) == 2
    assert target not in window.session.last_result.scene.objects


@pytest.mark.parametrize("background", [False, True])
def test_whole_mouse_gestures_undo_redo_and_reopen(window, monkeypatch, tmp_path, background):
    """Mehrere Proben eines Mauszuges bleiben beim Speichern und Bearbeiten eine Einheit."""
    from app.core.geom.sculpt import stroke_count
    from app.core.scene.project import save

    target = with_a_body(window)
    monkeypatch.setattr(MainWindow, "_sculpt_needs_worker", staticmethod(lambda mesh: background))
    window.start_sculpt(target)
    assert window.wait_for_sculpt_preview()
    for points in (((20, 0, 0), (18, 4, 0)), ((0, 20, 0), (4, 18, 0))):
        window.viewport.sculptGestureStarted.emit()
        for point in points:
            window.viewport.sculptRequested.emit(point)
        window.viewport.sculptGestureFinished.emit()
    assert window.wait_for_sculpt_preview()
    assert len(window._sculpt_strokes) == 4
    assert stroke_count(window._sculpt_strokes) == 2
    assert "2 Züge" in window.sculpt_bar.state.text()
    window.undo_action.trigger()
    assert window.wait_for_sculpt_preview()
    assert len(window._sculpt_strokes) == 2
    assert window.redo_action.isEnabled()
    window.redo_action.trigger()
    assert window.wait_for_sculpt_preview()
    assert len(window._sculpt_strokes) == 4
    window.finish_sculpt()
    assert window.session.wait_for_idle()
    path = save(window.session.project, tmp_path / "gestures.p3d")
    window.session.open_project(path)
    assert window.session.wait_for_idle(60_000)
    step = window.session.project.document.ops[-1].id
    window.edit_operation(step)
    assert window.session.wait_for_idle()
    assert window.wait_for_sculpt_preview()
    assert stroke_count(window._sculpt_strokes) == 2
    window.undo_action.trigger()
    assert window.wait_for_sculpt_preview()
    assert len(window._sculpt_strokes) == 2
    window.redo_action.trigger()
    assert window.wait_for_sculpt_preview()
    assert len(window._sculpt_strokes) == 4
    window.undo_action.trigger()
    window._on_sculpt((-20, 0, 0))
    assert window.wait_for_sculpt_preview()
    assert not window.redo_action.isEnabled()
    window.finish_sculpt()
    assert window.session.wait_for_idle()


def test_undo_of_a_partly_computed_drag_cancels_all_of_its_pending_samples(window, monkeypatch):
    """Eine späte Antwort darf einen zurückgenommenen Mauszug nicht halb zurückbringen."""
    from threading import Event

    import app.ui.main_window as module

    target = with_a_body(window)
    monkeypatch.setattr(MainWindow, "_sculpt_needs_worker", staticmethod(lambda mesh: True))
    window.start_sculpt(target)
    assert window.wait_for_sculpt_preview()
    window._begin_sculpt_gesture()
    window._on_sculpt((20, 0, 0))
    assert window.wait_for_sculpt_preview()
    entered, proceed = Event(), Event()
    original = module.stroke_at

    def held(*args, **kwargs):
        entered.set()
        assert proceed.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "stroke_at", held)
    window._on_sculpt((18, 4, 0))
    assert entered.wait(2)
    worker = window._sculpt_preview_worker
    window._on_sculpt((16, 8, 0))
    window._end_sculpt_gesture()
    try:
        window.undo_action.trigger()
        assert not window._sculpt_strokes and not window._sculpt_pending
    finally:
        proceed.set()
    assert worker.wait(5000)
    assert window.wait_for_sculpt_preview()
    QApplication.processEvents()
    assert not window._sculpt_strokes
    window.redo_action.trigger()
    assert window.wait_for_sculpt_preview()
    assert len(window._sculpt_strokes) == 3
    assert len({s.gesture for s in window._sculpt_strokes}) == 1
    window.finish_sculpt()
    assert window.session.wait_for_idle()
