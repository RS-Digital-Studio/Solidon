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

from app.core import examples
from app.core.scene import OperationDraft
from app.core.scene.history import History, change_for
from app.core.scene.project import Project, load
from app.core.tour import TOURS, Tour, tour_for
from app.core.types import Document


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
    import pytest

    pytest.importorskip("PySide6")

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


def test_the_last_step_of_a_tour_leads_to_the_next_example() -> None:
    """Am Ende steht eine Frage, die vorher niemand beantwortet hat: und jetzt?

    Der Abschlusstext sagte, was man gelernt hat, und führte nirgendwohin. Die
    übrigen sechs Beispiele fand nur, wer den Startbildschirm wiederzufinden
    wusste — und der ist nach „Datei → Neu" nicht mehr zu haben.
    """
    import pytest

    pytest.importorskip("PySide6")

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
