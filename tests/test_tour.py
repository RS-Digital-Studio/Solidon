"""Die Touren durch die Beispielprojekte (Bauplan §37.2).

Eine Tour verspricht zweierlei: dass jedes Beispiel eine hat, und dass die
Erkennung stimmt — ein Schritt gilt erst nach seiner Handlung als getan,
danach aber sicher. Beides wird hier am echten Beispielprojekt durchgespielt,
Schritt für Schritt, wie es die Oberfläche täte. Driften Tour und
``tools/make_examples.py`` auseinander (anderer Ausgangswert, andere
Operation), fällt genau das hier um — nicht erst vor einem neuen Nutzer.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest

from app.core import examples
from app.core.knowledge import profiles
from app.core.scene import OperationDraft, evaluate
from app.core.scene.history import History, change_for
from app.core.scene.project import Project, ProjectSources, load
from app.core.tour import TOURS, Tour, tour_for
from app.core.types import Document
from app.i18n import SOURCE_LANGUAGE, set_language
from app.i18n.catalog import install_language

if TYPE_CHECKING:
    from app.ui.tour import TourPanel


def test_every_example_has_a_tour() -> None:
    """§37.2 nennt die Beispiele Doku — ohne Tour wären sie nur Ergebnis."""
    for entry in examples.EXAMPLES:
        tour = tour_for(entry.id)
        assert tour is not None, f"{entry.id} hat keine Tour"
        assert str(tour.intro).strip()
        assert str(tour.closing).strip()
        assert len(tour.steps) >= 3
        for step in tour.steps:
            assert str(step.text).strip()
        # Mindestens eine Handlung mit Erkennung — sonst wäre es keine Tour,
        # sondern eine Seite Text.
        assert any(step.done is not None for step in tour.steps)


def test_every_tour_belongs_to_an_example() -> None:
    ids = {entry.id for entry in examples.EXAMPLES}
    for tour in TOURS:
        assert tour.example_id in ids

    assert tour_for("gibt-es-nicht") is None


def _opened(example_id: str) -> tuple[Project, History]:
    """Das Beispiel, wie die Oberfläche es öffnet: Datei plus frischer
    Verlauf."""
    project = load(examples.directory() / f"{example_id}.p3d")
    return project, History(project.document)


Action = Callable[[Document, History], None]


def _walk(tour: Tour, document: Document, history: History, actions: dict[int, Action]) -> None:
    """Spielt die Tour durch, wie es ein Nutzer täte.

    Leseschritte werden übersprungen (die Oberfläche quittiert sie über
    „Weiter"); jede Handlung muss ihren Schritt von „nicht getan" auf
    „getan" kippen. Ein Schritt, der vorher schon als getan gilt, würde in
    der Oberfläche sofort übersprungen — auch das ist ein Fehler.
    """
    for index, step in enumerate(tour.steps):
        if step.done is None:
            continue
        assert index in actions, f"Schritt {index} hat eine Erkennung, aber keine Handlung im Test"
        assert not step.done(document, history), f"Schritt {index} gilt schon vor der Handlung"
        actions[index](document, history)
        assert step.done(document, history), f"Schritt {index} erkennt seine Handlung nicht"


def _op_id(document: Document, name: str, position: int = 0) -> int:
    entries = [entry for entry in document.ops if entry.op == name]
    assert entries, f"{name} steht nicht im Beispiel — Tour und Beispiel sind auseinander"
    return entries[position].id


def test_way_one_tour_recognises_its_actions() -> None:
    """Weg 1: Durchmesser ändern, zurücknehmen, wiederholen."""
    project, history = _opened("weg1-halterung-anpassen")
    document = project.document

    _walk(
        tour_for("weg1-halterung-anpassen"),  # type: ignore[arg-type]
        document,
        history,
        {
            1: lambda d, h: h.change_params(_op_id(d, "drill_hole"), {"diameter": 6.0}),
            2: lambda d, h: h.undo(),
            3: lambda d, h: h.redo(),
        },
    )


def test_way_two_tour_recognises_its_actions() -> None:
    """Weg 2: einen Parameter drehen, einen Baustein setzen."""
    project, history = _opened("weg2-halter-konstruieren")
    document = project.document

    def turn_breite(d: Document, h: History) -> None:
        parameter = dataclasses.replace(d.parameters["breite"], value=90.0)
        h.apply("Parameter breite", changes=change_for(d, parameters={"breite": parameter}))

    def insert_part(d: Document, h: History) -> None:
        h.apply(
            "Drittes Schraubenloch",
            [
                OperationDraft(
                    op="insert_screw_hole",
                    inputs=("obj_1",),
                    params={"size": "M4", "depth": 6.0, "x": 0.0, "z": "=@staerke"},
                )
            ],
        )

    _walk(
        tour_for("weg2-halter-konstruieren"),  # type: ignore[arg-type]
        document,
        history,
        {1: turn_breite, 3: insert_part},
    )


def test_way_three_tour_recognises_its_actions() -> None:
    """Weg 3: eine Bohrung setzen, dann zurücknehmen."""
    project, history = _opened("weg3-generiert-aufbereiten")
    document = project.document
    body = document.ops[-1].outputs[0]

    def drill(d: Document, h: History) -> None:
        h.apply(
            "Bohrung setzen",
            [
                OperationDraft(
                    op="drill_hole",
                    inputs=(body,),
                    params={"diameter": 4.0, "x": 0.0, "y": 0.0, "z": 2.0, "axis": "z"},
                )
            ],
        )

    _walk(
        tour_for("weg3-generiert-aufbereiten"),  # type: ignore[arg-type]
        document,
        history,
        {2: drill, 3: lambda d, h: h.undo()},
    )


def test_way_three_names_the_current_external_model_contract() -> None:
    """Weg 3 nennt beides: den Dateiimport und den Erzeugen-Dialog.

    Am 02.09.2026 stand hier „Bild/Text zu 3D ist in dieser Version
    deaktiviert" — neben einem aktiven Menüeintrag und einem Changelog, der
    den Weg bewirbt. Entscheidung Robert (02.09.2026): TripoSG bleibt in
    Betrieb, solange die Rechtsprüfung nichts anderes ergibt; die Tour sagt
    deshalb, was die Anwendung tut, und nennt nichts als abgeschaltet.
    """
    tour = tour_for("weg3-generiert-aufbereiten")
    assert tour is not None
    closing = str(tour.closing)

    assert "GLB" in closing
    assert "STL" in closing
    assert "extern" in closing
    assert "deaktiviert" not in closing
    assert "ComfyUI" in closing


def test_way_four_tour_recognises_its_actions() -> None:
    """Weg 4: Übergang ändern, eine Formsitzung anlegen, zurücknehmen."""
    project, history = _opened("weg4-figur-formen")
    document = project.document

    def sculpt(d: Document, h: History) -> None:
        h.apply(
            "Formen",
            [
                OperationDraft(
                    op="sculpt_strokes",
                    inputs=("obj_1",),
                    params={"strokes": "[]"},
                )
            ],
        )

    _walk(
        tour_for("weg4-figur-formen"),  # type: ignore[arg-type]
        document,
        history,
        {
            1: lambda d, h: h.change_params(_op_id(d, "blend_union"), {"radius": 8.0}),
            2: sculpt,
            3: lambda d, h: h.undo(),
        },
    )


def test_housing_tour_recognises_its_actions() -> None:
    """Gehäuse: Wandstärke drehen, Mutternfalle umstellen."""
    project, history = _opened("gehaeuse-mit-bausteinen")
    document = project.document

    def turn_wand(d: Document, h: History) -> None:
        parameter = dataclasses.replace(d.parameters["wand"], value=10.0)
        h.apply("Parameter wand", changes=change_for(d, parameters={"wand": parameter}))

    _walk(
        tour_for("gehaeuse-mit-bausteinen"),  # type: ignore[arg-type]
        document,
        history,
        {
            2: turn_wand,
            3: lambda d, h: h.change_params(_op_id(d, "insert_nut_trap"), {"size": "M4"}),
        },
    )


def test_sign_tour_recognises_its_actions() -> None:
    """Schild: eigenen Text schreiben, Aufhängung verschieben."""
    project, history = _opened("schild-zweifarbig")
    document = project.document

    _walk(
        tour_for("schild-zweifarbig"),  # type: ignore[arg-type]
        document,
        history,
        {
            0: lambda d, h: h.change_params(_op_id(d, "label_text"), {"text": "GARAGE"}),
            2: lambda d, h: h.change_params(_op_id(d, "insert_keyhole"), {"x": 0.0}),
        },
    )


def test_calibration_tour_recognises_its_actions() -> None:
    """Kalibrieren: den Abstand der Anordnung umstellen."""
    project, history = _opened("drucker-kalibrieren")
    document = project.document

    _walk(
        tour_for("drucker-kalibrieren"),  # type: ignore[arg-type]
        document,
        history,
        {1: lambda d, h: h.change_params(_op_id(d, "arrange_bed"), {"spacing": 15.0})},
    )


def test_hollow_tour_recognises_its_actions() -> None:
    """Aushöhlen und teilen: die Wandstärke einer Hälfte umstellen."""
    project, history = _opened("aushoehlen-und-teilen")
    document = project.document

    _walk(
        tour_for("aushoehlen-und-teilen"),  # type: ignore[arg-type]
        document,
        history,
        {2: lambda d, h: h.change_params(_op_id(d, "hollow_object"), {"wall": 5.0})},
    )


def test_oversized_tour_recognises_its_action() -> None:
    """Das Schaustück zu Automatisch teilen: die erste Naht verschieben wird erkannt."""
    project, history = _opened("zu-gross-automatisch-teilen")
    document = project.document

    _walk(
        tour_for("zu-gross-automatisch-teilen"),  # type: ignore[arg-type]
        document,
        history,
        {2: lambda d, h: h.change_params(_op_id(d, "split_pinned"), {"position": -90.0})},
    )


def test_box_tour_recognises_its_action() -> None:
    """Die Dose führt nicht nur Text: Die Höhenänderung wird erkannt."""
    project, history = _opened("dose-mit-deckel")
    document = project.document

    def turn_height(d: Document, h: History) -> None:
        parameter = dataclasses.replace(d.parameters["hoehe"], value=60.0)
        h.apply("Parameter Höhe", changes=change_for(d, parameters={"hoehe": parameter}))

    _walk(
        tour_for("dose-mit-deckel"),  # type: ignore[arg-type]
        document,
        history,
        {0: turn_height},
    )


def test_the_tours_are_translated() -> None:
    """Regel 20 gilt auch hier: jede Tour spricht beide Sprachen."""
    from app.i18n.catalog import read_catalog

    catalog = read_catalog("en")
    for tour in TOURS:
        for text in (tour.intro, tour.closing, *(step.text for step in tour.steps)):
            key = getattr(text, "msgid", str(text))
            assert catalog.get(key), f"ohne englische Übersetzung: {key[:60]} …"


def test_a_reading_step_does_not_hold_up_the_recognition() -> None:
    """Fünf der sieben Touren beginnen mit einer Beobachtung.

    „Sehen Sie links in den Verlauf", „Links unter Parameter stehen breite,
    tiefe und stärke" — Hinsehen ändert nichts am Dokument, ein solcher Schritt
    trägt also kein ``done``. Die Erkennung des Panels brach genau dort ab: wer
    den Durchmesser änderte, das Teil folgen sah und auf die Tour blickte,
    stand weiterhin auf Schritt 1 von 5. Die Handlung war getan, die Tour sagte
    es nur nicht.

    Geprüft wird das Panel, nicht die Erkennungsfunktionen — die stimmten die
    ganze Zeit, und die Tests darüber waren grün, während die Oberfläche hing.
    """

    from app.ui.tour import TourPanel

    project, history = _opened("weg1-halterung-anpassen")
    document = project.document
    tour = tour_for("weg1-halterung-anpassen")
    assert tour is not None
    assert tour.steps[0].done is None, "Schritt 1 ist eine Beobachtung"

    panel = TourPanel.__new__(TourPanel)
    panel._tour = tour
    panel._document = document
    panel._current = 0
    panel._already = set()
    panel._completed = set()
    panel._skipped = set()
    panel._session = _FakeSession(project, history)
    panel._update_marks = lambda: None  # type: ignore[method-assign]

    # Schritt 2 der Tour: den Durchmesser der Bohrung ändern.
    history.change_params(_op_id(document, "drill_hole"), {"diameter": 6.0})
    panel._check()

    assert panel._current > 1, (
        "die getane Handlung schaltet weiter, obwohl der Schritt davor nur gelesen wird"
    )


class _FakeSession:
    """Nur die zwei Dinge, die ``_check`` liest."""

    def __init__(self, project: Project, history: History) -> None:
        self.project = project
        self.history = history


def test_a_tour_names_parameters_the_way_the_window_shows_them() -> None:
    """§4.1: der Text sagte „staerke", die Parameterleiste zeigt „Stärke".

    Der Bezeichner ist ASCII, weil er ein Bezeichner ist; angezeigt wird der
    Titel. Wer nach „staerke" sucht, findet nichts — und wer nach „breite"
    sucht, findet „Breite" nur, wenn er die Groß- und Kleinschreibung übersieht.

    Nach einem ``@`` bleibt der Bezeichner stehen: dort ist er kein Text,
    sondern das, was in einen Ausdruck gehört.
    """
    import re

    from app.core.scene.project import load

    for entry in examples.EXAMPLES:
        tour = tour_for(entry.id)
        if tour is None:
            continue
        project = load(examples.directory() / f"{entry.id}.p3d")
        texts = [str(tour.intro), str(tour.closing)]
        texts.extend(str(step.text) for step in tour.steps)

        for name, parameter in project.document.parameters.items():
            title = parameter.title or name
            if title == name:
                continue  # ohne eigenen Titel gibt es nichts zu verwechseln
            for text in texts:
                # Der Name ohne @ davor — das ist die Stelle, an der ein
                # Bezeichner als Text steht.
                bare = re.search(rf"(?<!@)(?<!\w){re.escape(name)}(?!\w)", text)
                assert bare is None, (
                    f"{entry.id}: die Tour schreibt {name}, die Oberfläche zeigt {title}"
                )


def test_every_step_that_names_a_place_points_at_it() -> None:
    """§2.6: „Sehen Sie links in den Verlauf" lässt vier Bereiche offen.

    Wer den Satz zum ersten Mal liest, sucht. Ein Schritt, der einen Bereich
    beim Namen nennt, sagt jetzt auch, welcher es ist — die Oberfläche lässt
    ihn kurz aufleuchten.
    """
    places = {
        "Verlauf": "history",
        "Prüfbericht": "report",
        "unter Parameter": "parameters",
        "im Objektbaum": "tree",
        "Werkzeugleiste": "toolbar",
        "Werkzeugzeile": "tools",
    }
    for tour in TOURS:
        for index, step in enumerate(tour.steps):
            text = str(step.text)
            named = [target for needle, target in places.items() if needle in text]
            if not named:
                continue
            assert step.shows is not None, (
                f"{tour.example_id}, Schritt {index + 1}: nennt {named[0]} und zeigt nirgendwohin"
            )
            assert step.shows in named, (
                f"{tour.example_id}, Schritt {index + 1}: zeigt auf {step.shows}, "
                f"spricht aber von {named}"
            )


def test_the_second_way_points_at_the_parameters_it_asks_to_change() -> None:
    """Der Satz begann bei den Parametern, ließ aber den Verlauf aufleuchten."""
    tour = tour_for("weg2-halter-konstruieren")
    assert tour is not None
    assert tour.steps[0].shows == "parameters"


def test_skipping_an_action_is_not_drawn_as_completed(qt_app: object) -> None:
    """„Weiter“ setzte auch ohne Handlung einen Haken an die Übung.

    Die Tour darf nie sperren. Sie muss aber ehrlich unterscheiden, ob eine
    erkannte Handlung erledigt oder auf Wunsch übersprungen wurde — durch Wort
    und Zeichen, nicht nur durch Farbe (Regel 18).
    """
    from PySide6.QtGui import QFont

    from app.ui.session import Session
    from app.ui.tour import TourPanel

    project, history = _opened("weg1-halterung-anpassen")
    session = Session()
    session.project = project
    session.history = history
    tour = tour_for("weg1-halterung-anpassen")
    assert tour is not None
    panel = TourPanel(session)
    panel.start(examples.EXAMPLES[0], tour)

    assert panel.next_button.text() == "Weiter"
    assert panel.next_button.isDefault(), "beim Leseschritt ist Weiter der eine Weg"

    panel.advance()  # Leseschritt
    assert panel.next_button.text() == "Schritt überspringen"
    # Die Übung findet im Fenster statt; Überspringen ist ein Nebenweg und
    # trägt weder Akzent noch Halbfett (RM-512).
    assert not panel.next_button.isDefault(), "Überspringen ist kein Hauptknopf"
    assert panel.next_button.font().weight() < QFont.Weight.DemiBold
    assert panel._row_hosts[1].property("tourState") == "current"

    panel.advance()  # Handlung bewusst auslassen

    marker, _text = panel._rows[1]
    assert 1 in panel._skipped and 1 not in panel._completed
    assert marker.accessibleName() == "Übersprungen"
    assert marker.pixmap().isNull(), "ein übersprungener Schritt trägt keinen Erledigt-Haken"
    assert panel._row_hosts[1].property("tourState") == "skipped"
    # Schritt 3 ist wieder eine Übung: Überspringen bleibt Nebenweg.
    assert panel.next_button.text() == "Schritt überspringen"
    assert not panel.next_button.isDefault(), "auch bei der nächsten Übung kein Hauptknopf"

    # Wer erst weiterliest und die Übung dann versteht, darf sie nachholen.
    # Der alte Stand prüfte nur ab dem aktuellen Schritt und ließ den Strich
    # deshalb selbst dann stehen, wenn die Handlung inzwischen erkannt wurde.
    history.change_params(_op_id(project.document, "drill_hole"), {"diameter": 6.0})
    panel._check()

    assert 1 in panel._completed and 1 not in panel._skipped
    assert marker.accessibleName() == "Erledigt"
    assert not marker.pixmap().isNull(), "die nachgeholte Handlung bekommt ihren Haken"
    assert panel._row_hosts[1].property("tourState") == "completed"

    panel.deleteLater()
    session.release()


def test_only_the_current_tour_step_is_expanded(qt_app: object) -> None:
    """Eine Führung zeigt einen Auftrag, nicht alle Absätze auf einmal."""
    from app.ui.session import Session
    from app.ui.tour import TourPanel

    project, history = _opened("weg1-halterung-anpassen")
    session = Session()
    session.project = project
    session.history = history
    tour = tour_for("weg1-halterung-anpassen")
    assert tour is not None
    panel = TourPanel(session)
    panel.start(examples.EXAMPLES[0], tour)

    assert panel._rows[0][1].wordWrap()
    assert all(not text.wordWrap() for _marker, text in panel._rows[1:])
    # Keine Sprechblase (RM-553): Sie lief quer über Ansicht und Kartentext.
    # Die Hilfstechnik liest den ganzen Satz aus der Beschreibung.
    assert all(not text.toolTip() for _marker, text in panel._rows)
    assert panel._rows[1][1].accessibleDescription() == panel._rows[1][1].full_text()

    panel.advance()

    assert not panel._rows[0][1].wordWrap()
    assert panel._rows[1][1].wordWrap()
    assert panel._rows[1][1].accessibleDescription() == ""

    # Ein Klick klappt einen anderen Schritt auf und wieder zu, der aktuelle bleibt offen
    # — über den Mausweg, nicht am Signal vorbei (Review U1, Fund 5).
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    fourth = panel._rows[3][1]
    QTest.mouseClick(fourth, Qt.MouseButton.LeftButton)
    assert fourth.wordWrap()
    assert panel._rows[1][1].wordWrap()
    QTest.mouseClick(fourth, Qt.MouseButton.LeftButton)
    assert not fourth.wordWrap()
    QTest.mouseClick(fourth, Qt.MouseButton.RightButton)
    assert not fourth.wordWrap(), "die rechte Taste klappt nicht auf"
    QTest.mouseClick(panel._rows[1][1], Qt.MouseButton.LeftButton)
    assert panel._rows[1][1].wordWrap(), "der aktuelle Schritt klappt nicht zu"

    # Und mit der Tastatur: Die eingeklappte Zeile nimmt den Tabulatorfokus, die
    # Leertaste klappt auf, die Eingabetaste wieder zu.
    assert fourth.focusPolicy() == Qt.FocusPolicy.TabFocus
    assert panel._rows[1][1].focusPolicy() == Qt.FocusPolicy.NoFocus
    QTest.keyClick(fourth, Qt.Key.Key_Space)
    assert fourth.wordWrap()
    QTest.keyClick(fourth, Qt.Key.Key_Return)
    assert not fourth.wordWrap()

    panel.deleteLater()
    session.release()


def _in_the_customers_style() -> None:
    """Thema und Stilblatt wie beim Kunden — samt Fokusrahmen der Schrittzeilen.

    Der Rahmen gibt dem Label eine Rahmenbreite, und damit rückt Qt den Text
    von sich aus ein. Ohne Stilblatt gibt es beides nicht (``tests.md``).
    """
    from PySide6.QtWidgets import QApplication

    from app.ui.theme import apply_theme

    application = QApplication.instance()
    assert application is not None
    apply_theme(application, "dark")  # type: ignore[arg-type]


def _assert_tour_lines_fit(panel: TourPanel, where: str) -> None:
    """Jede sichtbare Tourzeile liegt im sichtbaren Bereich und zeigt sich ganz."""
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QLabel, QWidget

    from app.ui.tour import StepLabel

    viewport = panel._scroll.viewport()
    assert panel._scroll.horizontalScrollBar().maximum() == 0, (
        f"{where}: die Liste ist breiter als ihr Rollbereich "
        f"({panel._scroll.widget().width()} > {viewport.width()})"
    )
    lines: list[tuple[str, QLabel, QWidget]] = [
        ("Titel", panel.title, panel),
        ("Einleitung", panel.intro, panel),
        ("Fortschritt", panel.progress, panel),
        ("Schluss", panel.closing, panel),
    ]
    for at, (_marker, text) in enumerate(panel._rows):
        lines.append((f"Schritt {at + 1}", text, viewport))
        # Halbfett ist nur der aktuelle: Das Stilblatt setzte beim Polieren die
        # Schrift von vorher zurück, und gekürzt war mit einer anderen.
        assert text.font().bold() == (at == panel.current_index), (
            f"{where}: Schritt {at + 1} ist {'' if text.font().bold() else 'nicht '}halbfett, "
            f"aktuell ist Schritt {panel.current_index + 1}"
        )
    for name, label, clip in lines:
        if not label.isVisible():
            continue
        box = QRect(label.mapTo(clip, QPoint(0, 0)), label.size())
        assert clip.rect().left() <= box.left() and box.right() <= clip.rect().right(), (
            f"{where}: {name} liegt bei {box.left()}..{box.right()}, "
            f"sichtbar ist 0..{clip.rect().right()}"
        )
        metrics = label.fontMetrics()
        if label.wordWrap():
            assert label.heightForWidth(label.width()) <= label.height(), (
                f"{where}: {name} ist niedriger als sein Umbruch"
            )
            continue
        indent = label.indent()
        if indent < 0 and label.frameWidth() > 0:
            indent = metrics.horizontalAdvance("x") // 2
        room = label.contentsRect().width() - max(indent, 0)
        shown = label.text()
        assert metrics.horizontalAdvance(shown) <= room, (
            f"{where}: {name} ist breiter als sein Platz: {shown!r}"
        )
        if isinstance(label, StepLabel) and shown != label.full_text():
            assert shown.endswith("…"), f"{where}: {name} endet ohne Auslassung"
            assert label.full_text().startswith(shown[:-1]), (
                f"{where}: {name} ist vorn beschnitten: {shown!r}"
            )

    if panel.current_index >= len(panel._rows):
        return
    current = panel._rows[panel.current_index][1]
    assert current.wordWrap(), f"{where}: der aktuelle Schritt bricht um"
    metrics = current.fontMetrics()
    if metrics.horizontalAdvance(current.full_text()) > current.contentsRect().width():
        assert current.height() >= 2 * metrics.lineSpacing(), (
            f"{where}: der aktuelle Schritt passt auf keine Zeile und steht doch auf einer"
        )


@pytest.mark.parametrize("example_id", [tour.example_id for tour in TOURS])
def test_every_tour_line_stays_inside_the_card(qt_app: object, example_id: str) -> None:
    """Kein Tourtext wird seitlich beschnitten, auch nicht nach dem Verkleinern.

    Eine gekürzte Schrittzeile verlangte als Mindestbreite ihren schon
    gekürzten Text und schrumpfte nie wieder: Die Liste wurde breiter als ihr
    Rollbereich, rechts fehlte der Rest, und das Nachrollen zum aktuellen
    Schritt schob den Anfang links hinaus. Der aktuelle Schritt stand dann
    einzeilig, weil er so breit war (Robert, 0.6.0). Dazu rückte der
    Fokusrahmen den Text um ein halbes „x“ ein, das die Kürzung nicht kannte.

    Jede Tour, und zuletzt bei der schmalsten Karte, die es gibt: Schmaler
    lassen weder die Seitenzone noch das abgedockte Fenster die Tour werden.
    Dort steht jeder Schritt einmal als aktueller — ein umgebrochener verlangt
    sein längstes Wort. Offscreen gibt es keine echte Schrift; geprüft werden
    Lage, Umbruch und Metrik, nicht Bildpunkte.
    """
    from PySide6.QtWidgets import QApplication

    from app.ui.session import Session
    from app.ui.tour import TourPanel

    _in_the_customers_style()
    example = next(entry for entry in examples.EXAMPLES if entry.id == example_id)
    project, history = _opened(example.id)
    session = Session()
    session.project = project
    session.history = history
    tour = tour_for(example.id)
    assert tour is not None
    panel = TourPanel(session)

    def settle() -> None:
        for _ in range(8):
            QApplication.processEvents()

    try:
        panel.resize(560, 700)
        panel.show()
        panel.start(example, tour)
        settle()
        # Erst breit, dann schmaler: Eine Zeile, die beim Kürzen ihre Breite
        # festhielte, wüchse nur noch.
        for width in (560, 420, 320, 260):
            panel.resize(width, 700)
            settle()
            _assert_tour_lines_fit(panel, f"{example_id} bei {width}")
        # Ein aufgeklappter erledigter Schritt bricht um wie der aktuelle.
        panel.advance()
        settle()
        panel._toggle(0)
        settle()
        assert panel._rows[0][1].wordWrap()
        _assert_tour_lines_fit(panel, f"{example_id} aufgeklappt")
        panel._toggle(0)
        settle()

        narrowest = panel.minimumSizeHint().width()
        panel.resize(narrowest, 700)
        settle()
        while True:
            where = f"{example_id} bei {narrowest}, Schritt {panel.current_index + 1}"
            _assert_tour_lines_fit(panel, where)
            if panel.current_index >= len(tour.steps):
                break
            panel.advance()
            settle()
        assert panel.closing.isVisible() and panel.closing.wordWrap()
    finally:
        panel.close()
        panel.deleteLater()
        session.release()


def test_a_folded_step_fits_where_the_font_kerns_before_the_ellipsis(qt_app: object) -> None:
    """``elidedText`` misst den Anfang im ganzen Satz, gezeichnet wird er vor „…“.

    Rückt die Schrift vor der Auslassung anders zusammen („V…“ statt „Vo“),
    ist die gekürzte Zeile einen Punkt breiter als ihr Platz (Ubuntu-CI:
    369 in 368). Unter DejaVu geschieht das in wenigen Lagen; eine Kette von
    Unterschneidungspaaren über viele Breiten trifft sie ohne einen
    bestimmten Tourtext. Mit der Ersatzschrift unter Windows offscreen gibt
    es keine Unterschneidung — dort ist der Test nur grün, unter Linux misst er.
    """
    from PySide6.QtWidgets import QApplication

    from app.ui.tour import StepLabel

    _in_the_customers_style()
    full = "1. " + " ".join(["To Ta Te Vo Va Ve Wo We Yo Av AT"] * 8)
    label = StepLabel(full)
    label.setObjectName("tourStepText")
    label.set_wrapped(False)
    label.show()
    over: list[str] = []
    try:
        for width in range(40, 400):
            label.resize(width, 40)
            QApplication.processEvents()
            room = label.contentsRect().width()
            advance = label.fontMetrics().horizontalAdvance(label.text())
            if advance > room:
                over.append(f"{width}: {advance}/{room} {label.text()[-6:]!r}")
    finally:
        label.close()
        label.deleteLater()
    assert not over, f"{len(over)} Breiten über dem Platz, erste: {over[:3]}"


def test_a_folded_step_is_cut_inside_its_frame_and_not_earlier(qt_app: object) -> None:
    """Gekürzt wird auf die Fläche im Rahmen — bei jeder Breite, nicht bei vier.

    Offscreen hat jedes Zeichen dieselbe Breite. Bei wenigen festen Breiten
    fiele die Kürzung auf die ganze Breite deshalb zufällig nie in den Rahmen;
    dreißig aufeinanderfolgende Breiten treffen jede Lage im Raster. Gemessen
    wird in beide Richtungen: nicht breiter als der Platz, aber auch nicht
    viel früher gekürzt als nötig.
    """
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from app.ui.tour import StepLabel

    _in_the_customers_style()
    full = (
        "2. Öffnen Sie „Bohrung setzen“ im Verlauf mit einem Doppelklick und "
        "ändern Sie den Durchmesser auf 5 mm."
    )
    label = StepLabel(full)
    label.setObjectName("tourStepText")
    label.set_wrapped(False)
    label.show()
    try:
        QApplication.processEvents()
        assert label.frameWidth() > 0, "premise: der Fokusrahmen aus dem Stilblatt liegt an"
        metrics = label.fontMetrics()
        slack = 3 * metrics.averageCharWidth()
        for width in range(200, 230):
            label.resize(width, 40)
            QApplication.processEvents()
            shown = label.text()
            room = label.contentsRect().width()
            advance = metrics.horizontalAdvance(shown)
            assert shown.endswith("…") and full.startswith(shown[:-1]), (width, shown)
            assert advance <= room, f"bei {width}: {advance} Punkte Text in {room} Punkten"
            assert advance > room - slack, (
                f"bei {width}: zu früh gekürzt, {shown!r} lässt {room - advance} Punkte frei"
            )
        # Eine neue Schrift — vom Stilblatt oder von hier — kürzt neu.
        bigger = QFont(label.font())
        bigger.setPixelSize(2 * label.fontMetrics().height())
        label.setFont(bigger)
        QApplication.processEvents()
        shown = label.text()
        advance = label.fontMetrics().horizontalAdvance(shown)
        room = label.contentsRect().width()
        assert advance <= room, f"nach dem Schriftwechsel: {advance} Punkte Text in {room} Punkten"
    finally:
        label.close()
        label.deleteLater()


def test_a_step_taller_than_the_card_shows_its_beginning(
    qt_app: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review U1, Fund 4: Ist der aktuelle Schritt höher als der Ausschnitt, steht sein Anfang.

    ``ensureWidgetVisible`` mittet ein zu hohes Widget, und Nummer und erste
    Zeilen standen über dem Rand.

    **Jedes Rollen trifft, nicht erst das letzte.** Gerollt wurde auch mitten in
    Qts Größenrechnung, vor dem neuen Rollbereich, und dort stieß es an die
    alte Grenze. Unter Windows rückte ein späterer Umbruch es zurecht; auf macOS
    blieb der Schritt 46 Punkte unter dem Rand. Deshalb wird jeder Aufruf
    geprüft, auch nach dem Verkleinern der Karte.
    """
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from app.ui.session import Session
    from app.ui.tour import TourPanel

    missed: list[tuple[int, int]] = []
    real_show_row = TourPanel._show_row

    def show_row(self: TourPanel) -> None:
        real_show_row(self)
        if not 0 <= self._in_view < len(self._row_hosts):
            return
        row = self._row_hosts[self._in_view]
        seen = self._scroll.viewport()
        if row.height() > seen.height():
            top = row.mapTo(seen, QPoint(0, 0)).y()
            if top != 0:
                missed.append((row.y(), top))

    monkeypatch.setattr(TourPanel, "_show_row", show_row)

    example = next(entry for entry in examples.EXAMPLES if entry.id == "weg2-halter-konstruieren")
    project, history = _opened(example.id)
    session = Session()
    session.project = project
    session.history = history
    tour = tour_for(example.id)
    assert tour is not None
    longest = max(range(len(tour.steps)), key=lambda at: len(str(tour.steps[at].text)))
    panel = TourPanel(session)
    try:
        # Wie hoch der längste Schritt ist, hängt an der Schrift: Unter Windows
        # ist er bei 240 höher als der Ausschnitt, mit DejaVu (Linux) nicht.
        # Die Karte wird so lange flacher, bis er es ist.
        small = 240
        panel.resize(220, small)
        panel.show()
        panel.start(example, tour)
        panel._current = longest
        panel._update_marks()
        for _ in range(6):
            QApplication.processEvents()
        host = panel._row_hosts[longest]
        viewport = panel._scroll.viewport()
        if host.height() <= viewport.height():
            while host.height() <= viewport.height() and small > 120:
                small -= 10
                panel.resize(220, small)
                for _ in range(6):
                    QApplication.processEvents()
            # Gezeigt wird der Schritt erst jetzt, in der flacheren Karte — wie
            # unter Windows bei 240 gleich beim Start.
            panel._update_marks()
            for _ in range(6):
                QApplication.processEvents()
        assert host.height() > viewport.height(), (
            f"premise: der Schritt ({host.height()}) ist höher als der Ausschnitt "
            f"({viewport.height()})"
        )
        assert host.mapTo(viewport, QPoint(0, 0)).y() == 0, "der Anfang des Schritts steht oben"

        # Erst groß, dann klein: Die Karte schrumpft, der Inhalt mit ihr, und
        # der Rollbereich bekommt seine Grenze erst nach dem Inhalt.
        panel.resize(220, 2000)
        for _ in range(6):
            QApplication.processEvents()
        panel.resize(220, small)
        for _ in range(6):
            QApplication.processEvents()
        assert host.mapTo(viewport, QPoint(0, 0)).y() == 0, "nach dem Verkleinern steht er oben"
        assert not missed, f"gerollt vor dem neuen Rollbereich (Lage, Oberkante): {missed}"
    finally:
        panel.close()
        panel.deleteLater()
        session.release()


def test_the_last_step_of_a_tour_leads_to_the_next_example() -> None:
    """Am Ende steht eine Frage, die vorher niemand beantwortet hat: und jetzt?

    Der Abschlusstext sagte, was man gelernt hat, und führte nirgendwohin. Die
    übrigen sechs Beispiele fand nur, wer den Startbildschirm wiederzufinden
    wusste — und der ist nach „Datei → Neu" nicht mehr zu haben.
    """

    from app.ui.tour import TourPanel

    ids = [entry.id for entry in examples.EXAMPLES]
    panel = TourPanel.__new__(TourPanel)

    for position, entry in enumerate(examples.EXAMPLES):
        panel._example = entry
        following = panel._next_example()
        if position + 1 < len(ids):
            assert following is not None
            assert following.id == ids[position + 1]
        else:
            assert following is None, "nach dem letzten kommt keines — kein Kreis"


def test_the_first_tour_describes_the_report_it_really_gets() -> None:
    """Die letzte Zeile der ersten Tour versprach Reparaturbefunde.

    „Rechts im Prüfbericht steht, was die Reparatur am Anfang gefunden hat" —
    und der Bericht dieses Beispiels sagt „An diesem Netz war nichts zu
    reparieren." Wer als Erstes einen Widerspruch zwischen Anleitung und
    Anwendung liest, glaubt danach keiner von beiden.

    Festgehalten wird die Zahl, auf die der Text sich beruft: zwei Hinweise,
    keine Warnung. Ändert jemand die Kette des Beispiels, fällt das hier um und
    nicht vor einem neuen Nutzer — so wie am 14.09.2026, als das Verschweißen
    einer STL aufhörte, ein Befund zu sein, und vom 20. bis zum 21.09.2026,
    als der Hinweis auf die Analysekarte „Formabweichung" an jedem Körper mit
    belegten Flächen stand: Seither ist er ein Befund mit Maß, der nur steht,
    wo belegte Punkte neben der Form liegen — an dieser Halterung nicht.
    """
    from app.core.knowledge import profiles
    from app.core.scene import evaluate
    from app.core.scene.project import ProjectSources

    project = load(examples.directory() / "weg1-halterung-anpassen.p3d")
    result = evaluate(
        project.document,
        profiles.make_profile(
            project.document.printer or "centauri-carbon-2",
            project.document.material or "petg",
        ),
        sources=ProjectSources(project),
    )

    findings = result.scene.report.findings
    assert len(findings) == 2, [str(entry.message) for entry in findings]
    assert {entry.severity for entry in findings} == {"info"}
    codes = {entry.code for entry in findings}
    assert "repair.nothing_to_do" in codes, "der Text nennt es, also gehört der Befund dazu"
    assert "perceive.deviation" not in codes, "an dieser Halterung liegt kein Punkt neben der Form"

    tour = tour_for("weg1-halterung-anpassen")
    assert tour is not None
    last = str(tour.steps[-1].text)
    assert "zwei Hinweise" in last, "der Text nennt die Zahl nicht mehr, die hier geprüft wird"
    assert "verschweißt" not in last, "das Lesen einer STL ist kein Befund mehr"
    assert "gefunden hat" not in last, "die alte Behauptung steht wieder da"


def test_every_tour_counts_the_steps_its_example_really_has() -> None:
    """Die Weg-4-Tour sagte „vier Schritte", im Verlauf stehen fünf.

    Quader, Kugel, Versetzen, Verschmelzen, Vernetzen — nachgezählt. Und „der
    dritte ist der, den man auslässt" meinte das Vernetzen, also den fünften;
    der dritte ist das Versetzen. Eine Anleitung, die neben einer Liste steht und
    anders zählt als sie, ist schlechter als keine.

    Geprüft wird jede Tour, die eine Zahl nennt: Steht sie im Text, muss sie die
    Länge des Verlaufs sein. Damit fällt auch der nächste Schritt auf, der einem
    Beispiel hinzugefügt wird, ohne den Text nachzuziehen.
    """
    zahlwoerter = {
        "einen": 1,
        "zwei": 2,
        "drei": 3,
        "vier": 4,
        "fünf": 5,
        "sechs": 6,
        "sieben": 7,
        "acht": 8,
        "neun": 9,
        "zehn": 10,
    }

    geprueft = 0
    for tour in TOURS:
        project = load(examples.directory() / f"{tour.example_id}.p3d")
        schritte = len(project.document.ops)
        for step in tour.steps:
            text = str(step.text)
            for wort, zahl in zahlwoerter.items():
                if f"{wort} Schritte" not in text and f"{wort} Schritt" not in text:
                    continue
                geprueft += 1
                assert zahl == schritte, (
                    f"{tour.example_id}: die Tour sagt {wort} ({zahl}), der Verlauf hat {schritte}"
                )
    assert geprueft, "keine Tour nennt eine Zahl — dann prüft dieser Test nichts"


def test_the_fit_tour_needs_exactly_one_undo() -> None:
    """Das elfte Beispiel: ein Strg+Z, und die Materialwarnung ist weg.

    **Der Test gibt es, weil genau das einmal nicht stimmte.** Die Tour sagte
    „nimm den letzten Schritt zurück", und hinter dem gemeinten stand noch das
    Anordnen: Es brauchte zwei Undo, und die Erkennung quittierte schon nach
    dem ersten — der Nutzer tat, was dastand, sah die Warnung weiterhin und
    wurde darin bestätigt. Gefunden von Hand in der Abnahme (31.08.2026),
    behoben in ``25bb2581``; hier steht die Zusicherung dazu.
    """
    project, history = _opened("passung-nach-materialwechsel")

    _walk(
        tour_for("passung-nach-materialwechsel"),  # type: ignore[arg-type]
        project.document,
        history,
        {3: lambda d, h: h.undo()},
    )


def test_the_fit_tour_leads_out_of_the_warning() -> None:
    """Und der Prüfbericht bestätigt es — nicht nur die Erkennung der Tour.

    **Die beiden sind nicht dasselbe, und der alte Fehler saß genau dazwischen.**
    ``_walk`` fragt die ``done``-Funktion; die kann quittieren, während die
    Warnung noch steht. Hier wird gemessen, was der Kunde sieht: eine Warnung
    zum Material beim Öffnen, keine Warnung nach einem Undo — die getrennt
    angeordneten Druckteile sind kein Befund.

    Geprüft wird der Befundcode und nicht die Zahl allein — „genau eine
    Warnung" wäre auch erfüllt, wenn es eine andere wäre.
    """
    project, history = _opened("passung-nach-materialwechsel")
    profile = profiles.make_profile(
        project.document.printer or "centauri-carbon-2",
        project.document.material or "pla",
    )

    def warnungen() -> list[str]:
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        return [
            finding.code
            for finding in result.scene.report.findings
            if finding.severity in ("warning", "error")
        ]

    assert warnungen() == ["fit.violated"]

    history.undo()

    assert warnungen() == [], "nach dem Undo steht keine Warnung mehr im Bericht"


def test_the_fit_tour_names_the_numbers_the_report_shows() -> None:
    """Die Zahlen im Tourtext sind die des Prüfberichts, in jeder Sprache.

    **Ein Text, der andere Zahlen nennt als die Anzeige daneben, ist eine
    Fährte** — der Kunde sucht dann nach etwas, das so nicht dasteht. Die Tour
    nennt 0,20 und 0,35 Millimeter; beides muss aus dem Befund kommen und
    nicht aus dem Gedächtnis dessen, der den Text geschrieben hat.

    Verglichen werden nur die Ziffern, nicht die Schreibweise: Der Bericht
    setzt einen Punkt (``format_length`` tut das in allen Sprachen), die
    deutsche Tour ein Komma. Dass das auseinandergeht, ist ein eigener Befund
    an ``format_length`` und keiner an diesem Text — die Zahl erkennt jeder
    wieder, die Schreibweise gehört an eine Stelle, die über alle Anzeigen
    entscheidet.
    """
    project, _ = _opened("passung-nach-materialwechsel")
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    befund = next(
        finding for finding in result.scene.report.findings if finding.code == "fit.violated"
    )
    werte = dict(befund.values)
    ziffern = {
        str(werte["actual"]).split()[0].replace(",", "."),
        str(werte["expected"]).split()[0].replace(",", "."),
    }

    tour = tour_for("passung-nach-materialwechsel")
    assert tour is not None

    for sprache in ("de", "en"):
        if sprache != SOURCE_LANGUAGE:
            install_language(sprache)
        set_language(sprache)
        texte = " ".join(str(step.text) for step in tour.steps)
        gerade = texte.replace(",", ".")
        fehlend = sorted(zahl for zahl in ziffern if zahl not in gerade)
        assert not fehlend, f"{sprache}: die Tour nennt {fehlend} nicht, der Bericht schon"

    set_language(SOURCE_LANGUAGE)


def test_the_undo_step_of_way_one_means_the_number_not_the_hole() -> None:
    """Gesamtreview 05.09.2026, CORE-32: Der Schritt sagte, nach Strg+Z sei
    das Loch zu — zurückgenommen wird aber der letzte Schritt, und das ist
    die Zahl. Die Erkennung fragte nur ``can_redo`` und quittierte damit
    auch ein Undo, nach dem der Durchmesser noch nicht wieder auf 4,2 mm
    steht."""
    project, history = _opened("weg1-halterung-anpassen")
    document = project.document
    step = tour_for("weg1-halterung-anpassen").steps[2]  # type: ignore[union-attr]
    assert step.done is not None

    assert "4,2 mm" in str(step.text)
    assert "Loch ist zu" not in str(step.text)

    op_id = _op_id(document, "drill_hole")
    history.change_params(op_id, {"diameter": 6.0})
    history.change_params(op_id, {"diameter": 7.0})
    history.undo()

    assert history.can_redo
    assert not step.done(document, history), "6,0 mm ist nicht 4,2 mm — der Satz stimmt noch nicht"

    history.undo()
    assert step.done(document, history), "jetzt steht die Zahl wieder, und die Bohrung bleibt"
    assert abs(_first_drill_diameter(document) - 4.2) < 1e-9


def _first_drill_diameter(document: Document) -> float:
    entry = next(entry for entry in document.ops if entry.op == "drill_hole")
    return float(entry.params["diameter"])


def test_a_restarted_tour_points_at_its_first_place_again(qt_app: object) -> None:
    """Nach „Tour beenden" zeigte die nächste Tour ihren ersten Bereich nicht.

    Das Panel merkte sich, worauf es zuletzt gezeigt hatte, damit ein Rahmen
    nicht bei jeder Neuberechnung aufblinkt — und vergaß es beim Beenden nicht.
    Fast jede Tour beginnt beim Verlauf; wer eine abbrach und eine neue
    begann, bekam deren ersten Hinweis nie zu sehen (Review Fenster 0.5.0,
    22.09.2026).
    """
    from app.ui.session import Session
    from app.ui.tour import TourPanel

    project, history = _opened("weg1-halterung-anpassen")
    session = Session()
    session.project = project
    session.history = history
    tour = tour_for("weg1-halterung-anpassen")
    assert tour is not None
    first = tour.steps[0].shows
    assert first is not None, "premise: the first step names a place"
    panel = TourPanel(session)
    pointed: list[str] = []
    panel.pointsAt.connect(pointed.append)

    panel.start(examples.EXAMPLES[0], tour)
    assert pointed == [first]

    panel.stop()
    panel.start(examples.EXAMPLES[0], tour)
    assert pointed == [first, first], "the new tour must show its first place again"

    panel.deleteLater()
    session.release()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_an_upcoming_step_is_readable_and_says_so(qt_app: object, theme: str) -> None:
    """Nachprüfung U1, Fund 6: Kommende Schritte sind lesbar grau und nennen ihren Zustand.

    Seit sie nicht mehr gesperrt sind, nehmen sie Fokus und Klick an und sind
    lesbarer Inhalt: Das Grau braucht 4,5 : 1 gegen die Karte, und der Marker
    sagt dem Bildschirmleser, dass der Schritt noch kommt — vorher meldete er
    „nicht verfügbar“, ohne Namen gar nichts.
    """
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication

    from app.i18n import tr
    from app.ui.session import Session
    from app.ui.theme import THEMES, apply_theme, contrast_ratio
    from app.ui.tour import TourPanel

    application = QApplication.instance()
    assert isinstance(application, QApplication)
    apply_theme(application, theme)  # type: ignore[arg-type]
    project, history = _opened("weg1-halterung-anpassen")
    session = Session()
    session.project = project
    session.history = history
    tour = tour_for("weg1-halterung-anpassen")
    assert tour is not None
    panel = TourPanel(session)
    try:
        panel.show()
        panel.start(examples.EXAMPLES[0], tour)
        QApplication.processEvents()
        marker, text = panel._rows[3]
        assert panel._row_hosts[3].property("tourState") == "upcoming"
        assert marker.accessibleName() == tr("Kommt noch")
        shown = text.palette().color(QPalette.ColorRole.WindowText).name()
        card = THEMES[theme]["window"]
        assert contrast_ratio(shown, card) >= 4.5, (shown, card, contrast_ratio(shown, card))
    finally:
        panel.close()
        panel.deleteLater()
        session.release()
        apply_theme(application, "dark")  # type: ignore[arg-type]
