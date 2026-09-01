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
from app.core.knowledge import profiles
from app.core.scene import OperationDraft, evaluate
from app.core.scene.history import History, change_for
from app.core.scene.project import Project, ProjectSources, load
from app.core.tour import TOURS, Tour, tour_for
from app.core.types import Document
from app.i18n import SOURCE_LANGUAGE, set_language
from app.i18n.catalog import install_language


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
    """Weg 3 verspricht nur den belegten Dateiimport, keinen Generator."""
    tour = tour_for("weg3-generiert-aufbereiten")
    assert tour is not None
    closing = str(tour.closing)

    assert "GLB" in closing
    assert "STL" in closing
    assert "extern" in closing
    assert "deaktiviert" in closing
    assert "ComfyUI" not in closing


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

    panel.advance()  # Leseschritt
    assert panel.next_button.text() == "Schritt überspringen"
    assert panel._row_hosts[1].property("tourState") == "current"

    panel.advance()  # Handlung bewusst auslassen

    marker, _text = panel._rows[1]
    assert 1 in panel._skipped and 1 not in panel._completed
    assert marker.accessibleName() == "Übersprungen"
    assert marker.pixmap().isNull(), "ein übersprungener Schritt trägt keinen Erledigt-Haken"
    assert panel._row_hosts[1].property("tourState") == "skipped"
    assert panel.next_button.isDefault(), "die eindeutige nächste Handlung ist der Hauptknopf"

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
    assert panel._rows[1][1].toolTip() == panel._rows[1][1].full_text()

    panel.advance()

    assert not panel._rows[0][1].wordWrap()
    assert panel._rows[1][1].wordWrap()
    assert panel._rows[1][1].toolTip() == ""

    panel.deleteLater()
    session.release()


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


def test_the_first_tour_describes_the_report_it_really_gets() -> None:
    """Die letzte Zeile der ersten Tour versprach Reparaturbefunde.

    „Rechts im Prüfbericht steht, was die Reparatur am Anfang gefunden hat" —
    und der Bericht dieses Beispiels sagt „An diesem Netz war nichts zu
    reparieren." Wer als Erstes einen Widerspruch zwischen Anleitung und
    Anwendung liest, glaubt danach keiner von beiden.

    Festgehalten wird die Zahl, auf die der Text sich beruft: drei Hinweise,
    keine Warnung. Ändert jemand die Kette des Beispiels, fällt das hier um und
    nicht vor einem neuen Nutzer.
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
    assert len(findings) == 3, [str(entry.message) for entry in findings]
    assert {entry.severity for entry in findings} == {"info"}
    codes = {entry.code for entry in findings}
    assert "repair.nothing_to_do" in codes, "der Text nennt es, also gehoert der Befund dazu"

    tour = tour_for("weg1-halterung-anpassen")
    assert tour is not None
    last = str(tour.steps[-1].text)
    assert "drei Hinweise" in last, "der Text nennt die Zahl nicht mehr, die hier geprüft wird"
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
    """Das elfte Beispiel: ein Strg+Z, und die Warnung ist weg.

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
    beim Öffnen, keine nach einem Undo.

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

    assert warnungen() == ["fit.violated"], "beim Öffnen steht genau diese eine Warnung"

    history.undo()

    assert warnungen() == [], "nach einem Undo ist der Bericht grün"


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
