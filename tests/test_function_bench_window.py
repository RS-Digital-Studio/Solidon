"""Der Prüfstand am echten Fenster (D0-P, RM-737) — Fenstertests, gezielt oder in der CI.

Die Probezeile im Prozess und im eigenen Prozess vom Inventar bis zum Bericht,
die Probe an echten Widgets (Liste, Ansicht, Rollfläche, Menüzeile,
Suchtreffer, Bausteinkachel, Leiste), Texte und Fokus an echten Widgets,
Haltgrund, Projektwechsel, Startfall und die Aufnahmen an einem kleinen
Dialog. Offscreen, wie ``tests/conftest.py`` es setzt.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest

from tests.bench_fakes import (
    PROBE_ROW,
    ROWS,
)
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window
from tools import (
    function_bench,
    function_checks,
    function_gestures,
    function_machine,
    function_protocol,
    function_setup,
    function_walk,
)
from tools import function_capture as capture
from tools.file_acceptance import (
    ROOT,
    read_cases,
)
from tools.function_checks import (
    MAIN_PHASES,
    NOT_FOUND,
    PROTOCOL_SCHEMA,
    SMALLEST_WINDOW,
    validate_protocol,
)
from tools.function_list import STARTUP_LICENCE

ACCEPTANCE = ROOT / "tools" / "file_acceptance.py"


@pytest.mark.parametrize("explicit_size", [False, True])
def test_repeated_window_placement_keeps_the_real_qt_client(qt_app, monkeypatch, explicit_size):
    """FD75: Ein zweiter Aufbau wahrt Maximierung oder stellt die verlangte Clientgröße her."""
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QMainWindow

    # Dieser kleine Qt-Zustandsfall braucht keinen echten großen Schirm. Der
    # Mindestgrößenvertrag bleibt separat geprüft; native Pixel folgen auf MSI.
    monkeypatch.setattr(function_setup, "SMALLEST_AVAILABLE", (0, 0))
    window = QMainWindow()
    variant = function_setup.Variant(screen=qt_app.primaryScreen().name())
    try:
        function_setup.place_window(qt_app, window, variant)
        qt_app.processEvents()
        assert window.isMaximized()
        original = window.geometry()
        handle = window.windowHandle()
        assert handle is not None
        if explicit_size:
            variant = replace(variant, window_size="1920x1009")
        function_setup.place_window(qt_app, window, variant)
        qt_app.processEvents()
        if explicit_size:
            assert not window.isMaximized()
            assert window.size() == QSize(1920, 1009)
        else:
            assert window.isMaximized()
            assert window.geometry() == original
        assert window.contentsRect().size() == window.size() == handle.size()
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_a_drag_counts_only_if_the_view_noticed_the_grip(qt_app: Any) -> None:
    """Review L11: Ein Zug, bei dem die Ansicht keinen Zugwert meldet, fasste keinen Griff.

    Griff und Ansicht sind ein echtes Widget. Meldet es bei den Bewegungen
    nichts, ist Z1 ungemessen — vorher standen auch dann Bildzeiten im
    Protokoll. Meldet es ``transformDragged`` wie die Ansicht, stehen die
    rohen Zeiten da, und die Bewegungen kamen im Takt einer Hand
    (``DRAG_TICK_S``), nicht so schnell die Schleife kann.
    """
    from types import SimpleNamespace

    from PySide6.QtCore import QPoint, QRect, QSize, Signal
    from PySide6.QtWidgets import QApplication, QWidget

    class View(QWidget):
        transformDragged = Signal(object)  # noqa: N815 - Name des Signals der Ansicht

        def __init__(self, answers: bool) -> None:
            super().__init__()
            self.answers = answers
            self.setMouseTracking(True)

        def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802 - Qt
            if self.answers:
                self.transformDragged.emit(event.position())

    def drag(answers: bool) -> tuple[dict[str, Any], list[float]]:
        view = View(answers)
        view.resize(300, 200)
        view.show()
        QApplication.processEvents()
        rect = QRect(view.mapToGlobal(QPoint(40, 90)), QSize(20, 20))
        moves: list[float] = []

        def latencies(events: list[float]) -> list[float | None]:
            moves.extend(events)
            return [5.0 for _ in events]

        flow = object.__new__(function_bench.FunctionFlow)
        flow.row = {"id": "zug", "target": "handle:move.x"}
        flow.spec = {"criteria": ["Z1"]}
        flow.data = {"unmeasured": {}}
        flow.frames_wrapped = True
        # Das Bild der letzten Bewegung ist da: Das Bild im gehaltenen Zug wartet nicht.
        flow.frames = SimpleNamespace(latencies=latencies, first_after=lambda moment: moment)
        flow.reference_factor = 1.5
        # Im Satz ``basis`` zieht jede Zeile mit Griff; vor dem Loslassen ein Bild (FD-73).
        flow.variant = function_setup.Variant.of({"set": "basis"})
        flow.picture = lambda label: None  # type: ignore[method-assign]
        flow.application = QApplication.instance()
        flow.window = SimpleNamespace(viewport=view)
        flow.ports = SimpleNamespace(
            next_click=lambda target: SimpleNamespace(rect=rect, why="ziel", target=target),
            centre=lambda area: area.center(),
            widget_under=lambda point: view,
            covers=lambda click, hit: True,
        )
        flow.path_steps = lambda: [function_machine.Step("hin", lambda machine: None)]  # type: ignore[method-assign]
        flow.run_steps = lambda label, steps: all(  # type: ignore[method-assign]
            step.act(None) or True for step in steps
        )
        try:
            flow.phase_drag()
        finally:
            view.close()
            view.deleteLater()
            QApplication.processEvents()
        return flow.data, moves

    data, _moves = drag(answers=False)
    assert "frames" not in data
    assert data["unmeasured"]["frames.raw_drag_ms"] == "der Zug fasste keinen Griff"

    data, moves = drag(answers=True)
    assert data["frames"] == {
        "raw_drag_ms": [5.0] * function_gestures.DRAG_MOVES,
        "reference_factor": 1.5,
    }
    assert "frames.raw_drag_ms" not in data["unmeasured"]
    gaps = [later - earlier for earlier, later in itertools.pairwise(moves)]
    assert (
        len(moves) == function_gestures.DRAG_MOVES
        and min(gaps) >= function_gestures.DRAG_TICK_S * 0.9
    )


def _probe_row(scenes: Path) -> dict[str, Any]:
    """Die Zeile ``resize_hole`` aus der erzeugten Liste, Startszenen wie im Inventar."""
    from tools import function_list, function_scenes

    rows = {row.id: asdict(row) for row in function_list.rows()}
    function_scenes.save_scenes(scenes)
    return rows[PROBE_ROW]


def _assert_the_main_way(data: dict[str, Any]) -> None:
    """Escape verwirft, Rückgängig kehrt zurück, Wiederholen bringt das Übernommene zurück."""
    assert not data["errors"], data["errors"]
    assert not data["findings"], data["findings"]
    states = data["states"]
    assert function_protocol.compare_prints(states["before"], states["escape"])["same"] is True
    assert function_protocol.compare_prints(states["before"], states["applied"])["same"] is False
    assert function_protocol.compare_prints(states["before"], states["undo"])["same"] is True
    assert function_protocol.compare_prints(states["applied"], states["redo"])["same"] is True
    main = [step for step in data["steps"] if step.get("phase") in MAIN_PHASES]
    assert any(step.get("why") == function_walk.TARGET_REASON and step.get("hit") for step in main)
    assert any(step.get("typed") for step in main), "keine Zahl getippt"
    assert data["place"]["error"] is None and data["place"]["where"] == "karte"
    assert data["preview"] is not None and data["preview"]["bodies"]
    assert data["timing"]["main_gap_ms"] is not None and data["timing"]["total_s"] is not None
    assert data["result"]["metrics"]["hole.diameter"] == pytest.approx(8.0, abs=0.01)
    assert validate_protocol(data) == []


def test_the_probe_row_runs_through_input_events_in_the_window(window: Any, tmp_path: Path) -> None:
    """Die Zeile ``resize_hole`` im Prozess der Suite: Auswahl, Tippen, Vorschau, Tasten.

    Offscreen, Phasen ``escape`` und ``main`` — dieselben, mit denen eine Zeile
    nach einem Fix nachgeprüft wird. Jeder Klick ging über ``next_click`` mit
    Probe; kein Fund, kein Fehler, und das Protokoll ist gegen U's Schema gültig.
    """
    from PySide6.QtWidgets import QApplication

    scenes = tmp_path / "scenes"
    row = _probe_row(scenes)
    variant = function_setup.Variant.of({"phases": ["escape", "main"]})
    data = function_protocol.empty_protocol(
        row, variant.protocol(None, (0, 0)), {"commit": "", "app": ""}
    )
    folder = tmp_path / "cases" / "001"
    folder.mkdir(parents=True)
    flow = function_bench.FunctionFlow(
        QApplication.instance(),
        window,
        folder,
        data,
        lambda: None,
        row,
        variant,
        scenes,
        out=tmp_path,
    )
    flow.prepare()
    flow.run()
    _assert_the_main_way(data)


def test_a_finding_action_applies_with_its_own_click_and_is_timed(
    window: Any, tmp_path: Path
) -> None:
    """Probelauf, Befund B: *Auf das Bett setzen* wirkt mit seinem Klick — das ist das Übernehmen.

    Vorher fiel der Klick auf die Befundhandlung in den Weg; das Übernehmen
    merkte sich danach das schon neue Ergebnis, klickte nichts und wartete die
    vollen 180 s auf ein weiteres. Jetzt fällt der Klick in der Phase
    Übernehmen, die Zeit steht da, der Ort stimmt, und Rückgängig wartet nicht
    auf eine Wirkung, die ausbleibt.
    """
    from PySide6.QtWidgets import QApplication

    from tools import function_list, function_scenes

    scenes = tmp_path / "scenes"
    function_scenes.save_scenes(scenes)
    row = {item.id: asdict(item) for item in function_list.rows()}["finding.action:place_on_bed"]
    variant = function_setup.Variant.of({"phases": ["main", "revise"]})
    data = function_protocol.empty_protocol(
        row, variant.protocol(None, (0, 0)), {"commit": "", "app": ""}
    )
    folder = tmp_path / "cases" / "001"
    folder.mkdir(parents=True)
    flow = function_bench.FunctionFlow(
        QApplication.instance(),
        window,
        folder,
        data,
        lambda: None,
        row,
        variant,
        scenes,
        out=tmp_path,
    )
    flow.prepare()
    flow.run()
    assert not any("Zeitgrenze" in error for error in data["errors"]), data["errors"]
    assert "timing" not in data["unmeasured"], data["unmeasured"]
    assert data["timing"]["total_s"] is not None and data["timing"]["total_s"] < 60
    acting = [
        step
        for step in data["steps"]
        if step.get("target") == "finding.action:place_on_bed"
        and step.get("why") == "ziel"
        and step.get("phase") in MAIN_PHASES
    ]
    assert [step["phase"] for step in acting] == [MAIN_PHASES[1]], data["steps"]
    assert data["place"]["error"] is None
    states = data["states"]
    assert function_protocol.compare_prints(states["before"], states["applied"])["same"] is False
    # Rückgängig und Wiederholen sind gemessen, ohne auf eine Wirkung zu warten,
    # die nicht kommt; ob sie zurückkehren, urteilt D0-U (Prüfpunkt 5).
    assert {"undo", "redo"} <= set(states)
    # *Auf das Bett setzen* hat keinen Wert: Es gibt keinen Dialog, den Ändern
    # öffnen könnte — der Prüfstand sagt das, statt „öffnet nicht“ zu messen
    # (Probelauf F-23). Den Rechtsklick ins Kontextmenü des Verlaufs prüft
    # ``test_a_right_click_brings_the_context_menu_event``.
    assert data["revise"] == []
    assert data["unmeasured"]["revise"] == function_checks.STEP_WITHOUT_VALUES
    assert validate_protocol(data) == []


def _command_row(window: Any, row_id: str) -> dict[str, Any]:
    """Eine Zeile der Fensterbefehle, gelesen an der Menüleiste des Fensters."""
    from tools import function_list

    rows = {row.id: asdict(row) for row in function_list.rows(function_list.menubar_of(window))}
    return rows[row_id]


def _run_flow(
    window: Any, tmp_path: Path, row: dict[str, Any], entry: dict[str, Any], number: str
) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    variant = function_setup.Variant.of(entry)
    data = function_protocol.empty_protocol(
        row, variant.protocol(None, (0, 0)), {"commit": "", "app": ""}
    )
    folder = tmp_path / "cases" / number
    folder.mkdir(parents=True)
    flow = function_bench.FunctionFlow(
        QApplication.instance(),
        window,
        folder,
        data,
        lambda: None,
        row,
        variant,
        tmp_path / "scenes",
        out=tmp_path,
    )
    flow.prepare()
    flow.run()
    return data


def test_a_window_command_with_inputs_creates_and_tries_to_write_when_locked(
    window: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-25, F-26, F-35, F-36: *Parameter anlegen* legt an — gesperrt nicht still „lesend“.

    Vorher tippte der Prüfstand Name und Wert und klickte nie *Anlegen*: Nichts
    entstand, Prüfpunkt 5 stand auf „ja“ (F-36), und der Lizenzlauf öffnete nur
    den Dialog — sein Dialog galt als fremde Nachfrage (F-26), und „schreibt“
    blieb falsch (F-35). Jetzt legt der Hauptweg das Maß an, und der gesperrte
    Lauf geht denselben Weg: grau mit Grund oder eine Absage an der
    Lizenzgrenze, die das Schreiben belegt.
    """
    from app.core import activation
    from app.core.activation import store
    from tools import function_scenes

    function_scenes.save_scenes(tmp_path / "scenes")
    row = _command_row(window, "Bearbeiten/Parameter anlegen …")
    assert function_setup.default_apply_target(row) == "dialog.accept"
    data = _run_flow(window, tmp_path, row, {"phases": ["main"]}, "001")
    assert not data["errors"], data["errors"]
    states = data["states"]
    assert function_protocol.compare_prints(states["before"], states["applied"])["differs"] == [
        "project_params"
    ]
    assert data["result"]["metrics"]["parameter.breite"] == pytest.approx(40.0)
    assert all(entry["allowed"] for entry in data["modals"] or ()), data["modals"]
    for name in ("_cached", "DEMO_UNTIL", "TRIAL_FROM"):
        holder = activation if name == "_cached" else store
        monkeypatch.setattr(holder, name, getattr(holder, name))
    function_setup.apply_licence("needs_activation")
    locked = _run_flow(
        window,
        tmp_path,
        row,
        {"set": "lizenz", "licence": "needs_activation"},
        "002",
    )
    run = locked["licence_runs"]["needs_activation"]
    assert (run["state"] == "grau" and run["reason"]) or run["writes"], run
    assert all(
        entry["allowed"] for entry in locked["modals"] or () if entry["class"] == "ParameterDialog"
    ), locked["modals"]


@pytest.mark.usefixtures("require_graphics_adapter")
@pytest.mark.parametrize("start", ["", "merkmal.hole.exakt"], ids=["erkannt", "gebohrt"])
def test_the_real_window_measures_the_action_of_the_row_not_the_one_in_the_view(
    tmp_path: Path, native_window_platform: str, start: str
) -> None:
    """F-20 und N5 am echten Fenster: Die Maßgruppe im Bild zählt nur mit der Handlung der Zeile.

    Offscreen gibt es kein Bild, und *Bohrung ändern* steht im Merkmalfenster.
    Am echten Fenster rückt nach der Auswahl eine Maßgruppe ins Bild, und der
    Kopf ihrer Handlung rechts tritt zurück (RM-199).

    **Erkannt** — die Startszene der Zeile (FD-29, ``erkannte_bohrung.netz``):
    Im Bild steht *Bohrung ändern* selbst. Der Prüfstand tippt dort ohne Klick,
    übernimmt und misst 8 mm, ohne Fund und ohne Vermerk.

    **Gebohrt** — die Startszene, die der Test im Inventar einsetzt: An der
    Bohrung von ``merkmal.hole.exakt`` steht *Bohrung im ursprünglichen Schritt
    ändern* (``drill_hole``) im Bild. Der Prüfstand tippte dort früher für
    ``resize_hole``, änderte den Ursprungsschritt und maß 8,2 mm; er misst die
    Handlung der Zeile: nicht auffindbar, mit dem Vermerk, welche Handlung im
    Bild stand.
    """
    import os
    import subprocess
    import sys

    from tools import function_list

    out = tmp_path / "abnahme"
    environment = {**os.environ, "QT_QPA_PLATFORM": native_window_platform, "PYTHONUTF8": "1"}

    def started_elsewhere() -> None:
        if not start:
            return
        listed = out / "rows.json"
        rows = json.loads(listed.read_text(encoding="utf-8"))
        for row in rows:
            if row["id"] == "resize_hole":
                row["start_scene"] = row["spec"]["start_scene"] = start
        listed.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    for arguments, limit in (
        (["inventory", "--functions", "--rows", "resize_hole", "--phases", "main"], 600),
        (["run"], 900),
    ):
        done = subprocess.run(
            [sys.executable, str(ACCEPTANCE), *arguments, "--out", str(out)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=limit,
        )
        assert done.returncode == 0, done.stdout + done.stderr
        if arguments[0] == "inventory":
            started_elsewhere()
    data = json.loads((out / "cases" / "001" / "function.json").read_text(encoding="utf-8"))
    assert validate_protocol(data) == []
    if start:
        assert data["scene"]["key"] == start, data["scene"]
        assert [(found["kind"], found["target"]) for found in data["findings"]] == [
            (NOT_FOUND, "feature:resize_hole")
        ], data["findings"]
        assert "drill_hole" in data["unmeasured"]["im_bild:feature:resize_hole"]
        assert data["result"] is None, "gemessen wurde eine andere Handlung"
        return
    assert data["scene"]["key"] == "erkannte_bohrung.netz", data["scene"]
    assert data["findings"] == [] and data["errors"] == [], (data["findings"], data["errors"])
    assert "im_bild:feature:resize_hole" not in data["unmeasured"], data["unmeasured"]
    assert any(
        step.get("target") == "feature:resize_hole" and step.get("zone") == "ansicht"
        for step in data["steps"]
    ), "Bohrung ändern stand nach der Auswahl in der Maßgruppe im Bild"
    assert data["result"] is not None, data["unmeasured"]
    expected = function_list.load_specs()["resize_hole"].values["expectation"]
    metrics = data["result"]["metrics"]
    for name in ("hole.diameter", "volume"):
        wanted = expected[name]
        assert metrics[name] == pytest.approx(wanted["value"], abs=wanted["tolerance"]), name


def test_a_double_click_reaches_a_list_as_a_double_click(qt_app: Any) -> None:
    """F-34, F-23: Der Doppelklick über ``QtPorts.press`` öffnet eine Zeile wie der des Kunden.

    ``QTest.mouseDClick`` allein schickt nur das Doppelklickereignis; eine
    Liste meldet ``itemDoubleClicked`` aber nur an der Zeile, die vorher
    gedrückt war. Kein Doppelklick des Prüfstands öffnete so je einen Schritt
    im Verlauf — der Fehlfall von *Auf das Bett setzen* fand sein Feld nie.

    Danach ist die Taste wieder los (FD-83): ``mouseDClick`` lässt sie nicht
    los, und Qt hielt sie bis zum nächsten Klick für gedrückt — jede Bewegung
    bis dahin war ein Zug ohne Leave, ein Tooltip blieb über dem nächsten Ziel.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QListWidget

    listing = QListWidget()
    listing.addItems(["1  Quader anlegen", "2  Bohrung setzen"])
    opened: list[str] = []
    listing.itemDoubleClicked.connect(lambda item: opened.append(item.text()))
    listing.show()
    qt_app.processEvents()
    try:
        place = listing.visualItemRect(listing.item(1)).center()
        point = listing.viewport().mapToGlobal(place)
        ports = function_walk.QtPorts(None, 0.0)
        ports.press(ports.widget_under(point), point, "double")
        qt_app.processEvents()
        assert opened == ["2  Bohrung setzen"]
        assert QApplication.mouseButtons() == Qt.MouseButton.NoButton
    finally:
        listing.close()
        listing.deleteLater()
        qt_app.processEvents()


def test_a_double_click_that_removes_its_widget_releases_at_the_pointer(
    qt_app: Any, monkeypatch: Any
) -> None:
    """FD-83, Rückfallzweig: Baut der Doppelklick das gedrückte Widget ab, lässt das los,
    was jetzt unter dem Zeiger liegt — wie Qt beim Kunden.

    Offscreen lässt sich das gedrückte Widget im Doppelklick nicht abbauen, ohne
    den Prozess zu verlieren. Der Fall öffnet deshalb an derselben Stelle eine
    neue Fläche und meldet die Liste über ``shiboken6.isValid`` als abgebaut;
    ``press`` holt ``isValid`` erst im Aufruf.
    """
    import shiboken6
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QListWidget, QStackedWidget, QWidget

    stack = QStackedWidget()
    listing = QListWidget()
    listing.addItems(["1  Quader anlegen", "2  Bohrung setzen"])
    opened = QWidget()
    stack.addWidget(listing)
    stack.addWidget(opened)
    listing.itemDoubleClicked.connect(lambda _item: stack.setCurrentWidget(opened))
    stack.resize(300, 200)
    stack.show()
    qt_app.processEvents()
    pressed = listing.viewport()
    valid = shiboken6.isValid
    monkeypatch.setattr(shiboken6, "isValid", lambda thing: thing is not pressed and valid(thing))
    released: list[Any] = []
    release = QTest.mouseRelease

    def record(widget: Any, *args: Any) -> None:
        released.append(widget)
        release(widget, *args)

    monkeypatch.setattr(QTest, "mouseRelease", record)
    try:
        point = pressed.mapToGlobal(listing.visualItemRect(listing.item(1)).center())
        ports = function_walk.QtPorts(None, 0.0)
        assert ports.widget_under(point) is pressed
        ports.press(pressed, point, "double")
        qt_app.processEvents()
        assert stack.currentWidget() is opened
        assert ports.widget_under(point) is opened
        assert released == [opened]
        assert QApplication.mouseButtons() == Qt.MouseButton.NoButton
    finally:
        stack.close()
        stack.deleteLater()
        qt_app.processEvents()


def test_a_click_into_a_field_lands_in_its_box_not_beside_it(qt_app: Any, monkeypatch: Any) -> None:
    """F-34: Ein Feld, breiter als sein Kästchen, wird im Kästchen geklickt.

    Ein Zahlenfeld des Operationsdialogs (``ValueField``) ist ein Behälter mit
    dem Kästchen links; seine Mitte lag am echten Schirm im leeren Teil
    daneben, der Fokus blieb im Rollbereich, und der Fehlfall tippte ins Leere.
    """
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QWidget

    from app.ui import guide_targets

    holder = QWidget()
    holder.resize(420, 40)
    row = QHBoxLayout(holder)
    box = QDoubleSpinBox(holder)
    box.setFixedWidth(80)
    row.addWidget(box)
    row.addStretch(1)
    holder.show()
    qt_app.processEvents()
    monkeypatch.setattr(
        guide_targets,
        "widget_for",
        lambda window, name: holder if name == "field:edge" else None,
    )
    try:
        ports = function_walk.QtPorts(holder, 0.0)
        centre = QRect(holder.mapToGlobal(QPoint(0, 0)), holder.size()).center()
        assert ports.widget_under(centre) is not box
        click = type("Click", (), {"target": "field:edge"})()
        aimed = ports.aim(click, centre)
        hit = ports.widget_under(aimed)
        assert hit is box or box.isAncestorOf(hit), hit
    finally:
        holder.close()
        holder.deleteLater()
        qt_app.processEvents()


def test_a_right_click_brings_the_context_menu_event(qt_app: Any) -> None:
    """Ein Rechtsklick über ``QtPorts.press`` erreicht das Kontextmenü des Widgets.

    ``QTest.mouseClick`` mit der rechten Taste schickt nur die Maus; das
    Kontextmenüereignis, das der Kunde mit dem Loslassen bekommt, blieb aus
    (Befund B). Eine Liste mit eigenem Kontextmenü meldet es an der Stelle.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    listing = QListWidget()
    listing.addItem("Schritt 1")
    listing.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    asked: list[Any] = []
    listing.customContextMenuRequested.connect(asked.append)
    listing.show()
    qt_app.processEvents()
    try:
        place = listing.visualItemRect(listing.item(0)).center()
        point = listing.viewport().mapToGlobal(place)
        ports = function_walk.QtPorts(None, 0.0)
        hit = ports.widget_under(point)
        assert hit is listing.viewport(), hit
        ports.press(hit, point, "right")
        assert asked == [place]
    finally:
        listing.close()
        listing.deleteLater()
        qt_app.processEvents()


@pytest.fixture
def button_probe(qt_app: Any, monkeypatch: Any) -> Any:
    """Echte Mauszustellung; nur die Wortschatzauflösung stammt aus der kleinen Szene."""
    import time
    from types import SimpleNamespace

    from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt
    from PySide6.QtWidgets import QLabel, QPushButton, QWidget

    from app.ui import guide_targets

    holder = QWidget()
    holder.resize(720, 480)
    owner = QLabel("Weitere Werte", holder)
    owner.setGeometry(30, 40, 160, 30)
    owner.setToolTip("Änderungsumfang, X, Y …")
    target = QPushButton("Abbrechen", holder)
    target.setGeometry(420, 260, 180, 36)
    state = SimpleNamespace(holder=holder, owner=owner, target=target, events=[], records=[])

    class Observer(QObject):
        def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qt
            if watched is state.target and event.type() == QEvent.Type.MouseButtonPress:
                state.events.append(("press", event.globalPosition().toPoint()))
            return False

    observer = Observer(holder)
    qt_app.installEventFilter(observer)

    def resolve(window: Any, name: str) -> Any:
        button = state.target
        if not button.isVisible() or not button.isEnabled():
            raise LookupError("Der Knopf ist gerade nicht bedienbar")
        return guide_targets.Click(
            QRect(button.mapToGlobal(QPoint()), button.size()),
            Qt.MouseButton.LeftButton,
            "ziel",
            name,
        )

    monkeypatch.setattr(guide_targets, "next_click", resolve)
    monkeypatch.setattr(guide_targets, "widget_for", lambda window, name: state.target)
    monkeypatch.setattr(guide_targets, "zone_of", lambda window, widget: "karte")
    state.ports = function_walk.QtPorts(holder, time.perf_counter())
    monkeypatch.setattr(state.ports, "pending", lambda: False)
    state.walker = function_walk.Walk(state.ports, state.records, time.perf_counter())
    holder.show()
    holder.activateWindow()
    qt_app.processEvents()
    state.ports.move(owner.mapToGlobal(owner.rect().center()))
    qt_app.processEvents()
    try:
        yield state
    finally:
        qt_app.removeEventFilter(observer)
        holder.close()
        holder.deleteLater()
        qt_app.processEvents()


def _drive_button_probe(qt_app: Any, scene: Any, named: bool) -> Any:
    """Derselbe Schrittautomat wie im Prüfstand, mit unveränderter 15-s-Klickfrist."""
    import time

    def press(machine: Any) -> None:
        assert function_walk.click_button(scene.ports, scene.walker, scene.target, "Abbrechen")

    step = (
        scene.walker.step("feature:resize_hole")
        if named
        else function_machine.Step(
            "Abbrechen",
            press,
            ready=scene.walker.stable("Abbrechen", button=lambda: scene.target),
        )
    )
    step.timeout_s = 15
    machine = function_machine.StepMachine(function_machine.qt_schedule, time.perf_counter)

    def pump() -> None:
        qt_app.processEvents()
        time.sleep(0.001)

    function_machine.drive(
        machine,
        [
            step,
            function_machine.Step(
                "nach dem Klick", lambda machine: scene.events.append(("after", None))
            ),
        ],
        pump,
        time.perf_counter,
        timeout_s=16,
    )
    return machine


@pytest.mark.parametrize("named", [True, False], ids=["wortschatz", "knopf"])
def test_button_probe_moves_away_from_a_real_tooltip_before_testing_coverage(
    qt_app: Any, button_probe: Any, named: bool
) -> None:
    """FD74: Ein echter Tooltip verschwindet durch Mausbewegung, nicht durch den Prüfer."""
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QCursor
    from PySide6.QtWidgets import QToolTip

    scene = button_probe
    # Nur der Ausgangszustand wird gestellt; der Prüfpfad darf den Tooltip
    # weder ausblenden noch bei der Trefferprüfung überspringen.
    QToolTip.showText(scene.target.mapToGlobal(QPoint()), scene.owner.toolTip(), scene.owner)
    qt_app.processEvents()
    tip = next(
        widget
        for widget in qt_app.topLevelWidgets()
        if widget.objectName() == "qtooltip_label" and widget.isVisible()
    )
    centre = QRect(tip.mapToGlobal(QPoint()), tip.size()).center()
    scene.target.move(scene.holder.mapFromGlobal(centre) - scene.target.rect().center())
    assert scene.ports.widget_under(centre) is tip
    assert QCursor.pos() != centre

    machine = _drive_button_probe(qt_app, scene, named)

    assert machine.error is None and machine.finding is None, (machine.error, machine.finding)
    assert [event[0] for event in scene.events] == ["press", "after"]
    assert scene.events[0][1] == scene.target.mapToGlobal(scene.target.rect().center())
    assert not QToolTip.isVisible()
    assert scene.records[-1]["hit"] is True


@pytest.mark.parametrize("named", [True, False], ids=["wortschatz", "knopf"])
def test_button_probe_keeps_a_real_persistent_cover_as_a_finding(
    qt_app: Any, button_probe: Any, named: bool
) -> None:
    """FD74: Die neue Bewegung macht einen tatsächlich verdeckten Knopf nicht klickbar."""
    from PySide6.QtWidgets import QLabel

    scene = button_probe
    cover = QLabel("Bleibende Überdeckung", scene.holder)
    cover.setGeometry(scene.target.geometry())
    cover.show()
    cover.raise_()
    qt_app.processEvents()

    machine = _drive_button_probe(qt_app, scene, named)

    assert not scene.events
    assert machine.error is not None or machine.finding is not None
    assert scene.records[-1]["finding"] == function_checks.COVERED
    assert scene.records[-1]["widget_at"]["text"] == "Bleibende Überdeckung"


@pytest.mark.parametrize("change", ["move", "replace", "hide", "disable"])
def test_button_probe_resolves_the_target_again_after_the_move(
    qt_app: Any, button_probe: Any, change: str
) -> None:
    """FD74: Zwischen Anfahren und Klick gilt das neue Widget an seiner neuen Stelle."""
    import time

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QPushButton

    scene = button_probe
    original = scene.target
    ready = scene.walker.stable("Abbrechen", button=lambda: scene.target)
    old_centre = original.mapToGlobal(original.rect().center())
    assert not ready(), "Die erste Bewegung muss eine spätere Ereignisrunde zulassen"
    assert not scene.events
    if change == "move":
        original.move(original.pos() + QPoint(-180, 40))
    elif change == "replace":
        replacement = QPushButton("Neuer Knopf", scene.holder)
        replacement.setGeometry(210, 320, 180, 36)
        replacement.show()
        original.hide()
        scene.target = replacement
    else:
        if change == "hide":
            original.hide()
        else:
            original.setEnabled(False)
        qt_app.processEvents()
        time.sleep(function_walk.STABLE_S)
        assert not ready()
        assert not scene.events
        original.show()
        original.setEnabled(True)
        original.move(original.pos() + QPoint(-180, 40))
    qt_app.processEvents()
    assert not ready(), "Geänderte Lage muss neu angefahren werden"
    deadline = time.perf_counter() + 15
    while not ready() and time.perf_counter() < deadline:
        qt_app.processEvents()
        time.sleep(0.001)
    assert ready()
    assert function_walk.click_button(scene.ports, scene.walker, scene.target, "Abbrechen")
    assert [event[0] for event in scene.events] == ["press"]
    assert scene.events[0][1] != old_centre
    assert scene.events[0][1] == scene.target.mapToGlobal(scene.target.rect().center())


@pytest.mark.parametrize("change", ["hide", "disable", "delete"])
def test_button_probe_final_guard_rejects_a_target_that_is_no_longer_usable(
    qt_app: Any, button_probe: Any, change: str
) -> None:
    """Auch ein direkter Aufrufer darf keinen unsichtbaren, grauen oder gelöschten Knopf drücken."""
    from PySide6.QtCore import QCoreApplication, QEvent

    scene = button_probe
    if change == "hide":
        scene.target.hide()
    elif change == "disable":
        scene.target.setEnabled(False)
    else:
        scene.target.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    with pytest.raises(RuntimeError, match="nicht bedienbar"):
        function_walk.click_button(scene.ports, scene.walker, scene.target, "Abbrechen")
    assert not scene.events


@pytest.mark.windowed
def test_the_probe_row_runs_in_its_own_process_from_inventory_to_report(tmp_path: Path) -> None:
    """Der ganze Weg eines Funktionsfalls: Inventar, eigener Prozess mit Profil, Protokoll, Bericht.

    Wie ``test_file_acceptance`` für den Dateiweg: Der Prozess baut die
    Anwendung wie ``main``, mit vorbereitetem Profil, Lizenz über die
    Nahtstelle und ohne Systemdialoge; die Menüleiste zählt ein Kindprozess.
    """
    import os
    import subprocess
    import sys

    out = tmp_path / "abnahme"
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONUTF8": "1"}
    for arguments in (
        [
            "inventory",
            "--functions",
            "--rows",
            PROBE_ROW,
            "--phases",
            "escape,main",
            "--out",
            str(out),
        ],
        ["run", "--out", str(out), "--timeout", "900"],
    ):
        finished = subprocess.run(
            [sys.executable, str(ACCEPTANCE), *arguments],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=1200,
            check=False,
        )
        assert finished.returncode == 0, (finished.stdout, finished.stderr)
    state = json.loads((out / "cases" / "001" / "bench.json").read_text(encoding="utf-8"))
    assert state["stage"] == "done" and state["shutdown_complete"] is True
    protocol = json.loads((out / "cases" / "001" / "function.json").read_text(encoding="utf-8"))
    assert validate_protocol(protocol) == []
    variant = protocol["variant"]
    assert (variant["licence"], variant["language"], variant["phases"]) == (
        "licensed",
        "de",
        ["escape", "main"],
    )
    assert protocol["row"]["id"] == PROBE_ROW and protocol["scene"]["key"]
    # Ein Referenzfaktor je Lauf (Bauplan §31): ``run`` misst ihn, der Fall
    # schreibt genau diesen an die Stelle, an der D0-U ihn liest.
    factor = json.loads((out / capture.REFERENCE_FILE).read_text(encoding="utf-8"))
    from tools.function_checks import REFERENCE_FACTOR_AT

    section, key = REFERENCE_FACTOR_AT
    assert protocol[section][key] == factor["reference_factor"] > 0
    # Der Hauptweg ist geprobt: Jeder Klick steht mit Treffer oder Fund da. Ob
    # die Anwendung ihn freigibt, ist ein Befund über sie, nicht über den
    # Prüfstand — ein Fund steht dann vollständig in ``findings``.
    main = [step for step in protocol["steps"] if step["phase"] in MAIN_PHASES]
    assert main and all("hit" in step or "finding" in step for step in main if step.get("why"))
    assert protocol["errors"] == [], protocol["errors"]
    # Review L9: streng wie im Prozess — ein falsches „verdeckt“ hielte den Fall
    # sonst grün. Die Probe kennt seit der Fixrunde den Empfänger jedes Klicks.
    assert protocol["findings"] == [], protocol["findings"]
    _assert_the_main_way(protocol)
    from tools import function_list

    menu = function_list.read_menubar(out / "menubar.json")
    assert len(menu) > 30 and all(entry.object_name.startswith("menubar.") for entry in menu)
    report = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert (report["function_cases"], report["function_complete"]) == (1, 1)


def test_the_probe_finds_a_list_or_the_view_over_a_real_target(window: Any) -> None:
    """Review S2 an echten Widgets: Liste oder 3D-Ansicht über dem Ziel ergeben „verdeckt“.

    Ein Behälter zählt nur, wenn er der Behälter **dieses** Ziels ist. Ziel ist
    das Suchfeld des Fensters (``search``). Kontrollfall: frei, getroffen. Eine
    ``QListWidget`` darüber — vorher hielt die Probe ihre Fläche für „eine
    Liste, also ein Behälter“. Die Ansicht an der Stelle des Ziels — vorher
    galt ``window.viewport`` für jedes Ziel als Behälter. Die Ansicht als
    eigenes Ziel (``viewport``) bleibt getroffen.
    """
    from types import SimpleNamespace

    from PySide6.QtCore import QPoint, QRect, QSize, Qt
    from PySide6.QtWidgets import QApplication, QListWidget

    from app.ui import guide_targets

    def settle() -> None:
        for _ in range(20):
            QApplication.processEvents()

    def global_rect(widget: Any) -> QRect:
        return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())

    def click(rect: QRect, target: str) -> Any:
        return SimpleNamespace(
            rect=rect, why="ziel", target=target, button=Qt.MouseButton.LeftButton, direction=0
        )

    window.resize(*SMALLEST_WINDOW)
    window.show()
    settle()
    ports = function_walk.QtPorts(window, 0.0)
    # Was gerade dasteht: der Startbildschirm mit *Neues Projekt* oder das Suchfeld.
    name, field = next(
        (name, widget)
        for name in ("start.new", "search")
        if (widget := guide_targets.widget_for(window, name)).isVisible()
    )
    rect = global_rect(field)
    free = ports.widget_under(rect.center())
    assert ports.covers(click(rect, name), free), "Kontrollfall: das freie Ziel"

    cover = QListWidget(window)
    cover.addItem("darüber")
    cover.setGeometry(
        QRect(window.mapFromGlobal(rect.topLeft()) - QPoint(10, 10), rect.size() + QSize(20, 20))
    )
    cover.raise_()
    cover.show()
    settle()
    try:
        hit = ports.widget_under(rect.center())
        assert hit is cover or cover.isAncestorOf(hit), hit
        assert not ports.covers(click(rect, name), hit), "Liste über dem Ziel"
    finally:
        cover.hide()
        cover.deleteLater()
        settle()

    if window.stack.currentWidget() is window.start_screen:
        # Die Ansicht steht erst mit einem Projekt da — *Neues Projekt*, geklickt.
        from PySide6.QtTest import QTest

        start = guide_targets.widget_for(window, "start.new")
        QTest.mouseClick(start, Qt.MouseButton.LeftButton)
        for _ in range(200):
            settle()
            if window.stack.currentWidget() is not window.start_screen:
                break
    view = window.viewport
    centre = view.mapToGlobal(view.rect().center())
    spot = QRect(centre - QPoint(50, 10), QSize(100, 20))
    hit = ports.widget_under(spot.center())
    assert hit is view or view.isAncestorOf(hit), hit
    assert not ports.covers(click(spot, name), hit), "die Ansicht an der Stelle des Ziels"
    assert ports.covers(click(spot, "viewport"), hit), "die Ansicht als eigenes Ziel"


@pytest.fixture
def box_window(qt_app: Any) -> Any:
    """Ein gezeigtes Fenster mit einem Quader samt Bohrung, ohne Startbildschirm.

    Gebaut wie ``prepared_window`` von D0-W: Die Attrappe des Renderers gibt der
    Ansicht eine Projektion. Das ist Vorbereitung, nicht der geprüfte Weg.
    """
    from PySide6.QtWidgets import QMenu

    from app.core.scene.history import OperationDraft
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from tests.render_fakes import RecordingRenderer

    window = MainWindow(Session(), UiSettings())
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.resize(*SMALLEST_WINDOW)
    window.show()
    window._show_start_screen(False)
    assert window.session.apply(
        "Quader mit Bohrung",
        [
            OperationDraft(op="create_box"),
            OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 12.0}),
        ],
    )
    assert window.session.wait_for_idle(60_000)
    _settle(qt_app)
    try:
        yield window
    finally:
        for menu in [*window.findChildren(QMenu), *qt_app.topLevelWidgets()]:
            if isinstance(menu, QMenu) and menu.isVisible():
                menu.hide()
        window.hide()
        window.release()
        window.viewport.renderer = None


def _settle(qt_app: Any, rounds: int = 20) -> None:
    for _ in range(rounds):
        qt_app.processEvents()


def _walk_to(qt_app: Any, ports: Any, name: str) -> Any:
    """Die Wegklicks zu ``name`` über ``QtPorts.press``, jeder mit Probe; der Zielklick nicht.

    Gibt den Zielklick und den Treffer der Probe an seiner Mitte zurück.
    """
    for _step in range(6):
        click = ports.next_click(name)
        point = ports.centre(click.rect)
        hit = ports.widget_under(point)
        if click.why == function_walk.TARGET_REASON:
            return click, hit
        assert hit is not None and ports.covers(click, hit), (name, click.why, hit)
        ports.press(hit, point, "left")
        _settle(qt_app)
    raise AssertionError(f"{name}: kein Ziel nach sechs Wegklicks")


def test_an_operation_that_stands_only_in_the_menu_is_its_menu_line(
    box_window: Any, qt_app: Any
) -> None:
    """Review N1: Eine Operation ohne Kartenknopf steht als Zeile im offenen Menü.

    Der Weg geht über Menütitel und Untermenü der Leiste; am Ziel liegt unter der
    Mitte das Menü mit genau dieser Zeile — gedeckt. Vorher galt dort „verdeckt“,
    denn die Operation hat kein eigenes Widget. Die Ansicht an derselben Stelle
    bleibt verdeckt.
    """
    from PySide6.QtWidgets import QMenu

    ports = function_walk.QtPorts(box_window, 0.0)
    name = next(
        f"operation:{op}"
        for op in ("field_cut", "inlay_text", "label_text")
        if (button := box_window.selection_operations.button_for(op)) is None
        or not button.isVisible()
    )
    click, hit = _walk_to(qt_app, ports, name)
    assert isinstance(hit, QMenu), hit
    assert ports.covers(click, hit), name
    assert not ports.covers(click, box_window.viewport), "die Ansicht ist nicht die Menüzeile"


def test_an_operation_found_by_the_search_is_its_row_in_the_hits(
    box_window: Any, qt_app: Any
) -> None:
    """Review N1: Ein Suchtreffer einer Operation ist ihre Zeile in der Trefferliste.

    Vorher nahm die Probe den Kartenknopf oder ein Rechteck und meldete
    „verdeckt“. Gedeckt ist nur die Zeile **dieser** Operation: Derselbe Ort für
    einen anderen Treffer ist es nicht.
    """
    from app.ui import guide_targets

    box_window.right.setCurrentIndex(0)
    box_window.selection_operations.search.setText("e")
    _settle(qt_app)
    ports = function_walk.QtPorts(box_window, 0.0)
    found = [hit for hit in guide_targets.search_hits(box_window) if hit.startswith("operation:")]
    assert len(found) >= 2, found
    name, other = found[0], found[1]
    click, hit = _walk_to(qt_app, ports, name)
    hits = box_window.selection_operations.hits
    assert hit is hits or hits.isAncestorOf(hit), hit
    assert ports.covers(click, hit), name
    elsewhere = replace(click, target=other)
    assert not ports.covers(elsewhere, hit), "die Zeile einer anderen Operation"
    box_window.selection_operations.search.setText("")


def test_a_part_is_its_tile_in_the_open_catalog(box_window: Any, qt_app: Any) -> None:
    """Review N1: Ein Baustein (``part:``) ist seine Kachel in der Liste des Katalogs.

    Vorher warf ``widget_for`` für ``part:``, die Probe nahm ein Rechteck und
    meldete an jeder Kachel „verdeckt“. Die Ansicht des Fensters unter dem
    Katalog ist es nicht.
    """
    from PySide6.QtCore import Qt

    from app.ui.catalog import PartCatalog

    catalog = PartCatalog(box_window)
    catalog.setModal(True)
    catalog.show()
    _settle(qt_app)
    try:
        # Überschriften der Gruppen tragen keinen Namen, nur die Kacheln.
        names = [
            str(named)
            for row in range(catalog.list.count())
            if (named := catalog.list.item(row).data(Qt.ItemDataRole.UserRole))
        ]
        assert names, "der Katalog zeigt keine Kachel"
        ports = function_walk.QtPorts(box_window, 0.0)
        click, hit = _walk_to(qt_app, ports, f"part:{names[0]}")
        assert hit is catalog.list or catalog.list.isAncestorOf(hit), hit
        assert ports.covers(click, hit)
        assert not ports.covers(click, box_window.viewport), "die Ansicht unter dem Katalog"
    finally:
        catalog.hide()
        catalog.deleteLater()
        _settle(qt_app)


def test_a_bar_over_the_view_is_its_own_widget_not_the_view(box_window: Any, qt_app: Any) -> None:
    """Review N1: ``handle:bar.*`` ist die Leiste in der Werkzeugzeile, nicht die Ansicht.

    Das Werkzeug *Schnitt* wird per Klick geöffnet; dann steht die Schnittleiste.
    Vorher nahm die Probe für jeden ``handle:`` die Ansicht und meldete an jeder
    der sieben Leisten „verdeckt“. Ein Griff im Bild bleibt bei der Ansicht.
    """
    ports = function_walk.QtPorts(box_window, 0.0)
    click, hit = _walk_to(qt_app, ports, "tool:section")
    ports.press(hit, ports.centre(click.rect), "left")
    _settle(qt_app, 60)
    bar = box_window.section_bar
    assert bar.isVisible()
    click, hit = _walk_to(qt_app, ports, "handle:bar.section")
    assert hit is bar or bar.isAncestorOf(hit), hit
    assert not box_window.viewport.isAncestorOf(hit)
    assert ports.covers(click, hit)
    assert not ports.covers(click, box_window.viewport), "die Ansicht ist nicht die Leiste"


def test_a_scroll_click_covers_its_scroll_area_and_not_a_list_over_it(qt_app: Any) -> None:
    """Rollen nennt bei D0-W die Sichtfläche, ganz oder ihren sichtbaren Teil.

    Ziel ist die Rollfläche selbst: Die Probe an der Mitte trifft ihre
    Sichtfläche — gedeckt, ob der Klick die ganze Sichtfläche oder nur ihren
    sichtbaren Teil nennt. Eine Liste darüber ist auch eine Rollfläche, aber
    nicht die mit diesem Rechteck: verdeckt.
    """
    from types import SimpleNamespace

    from PySide6.QtCore import QPoint, QRect, QSize, Qt
    from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QScrollArea, QWidget

    def settle() -> None:
        for _ in range(20):
            QApplication.processEvents()

    root = QWidget()
    root.resize(400, 300)
    area = QScrollArea(root)
    # Unten ragt die Rollfläche aus dem Fenster: Ihr sichtbarer Teil ist kleiner.
    area.setGeometry(20, 20, 300, 400)
    inner = QLabel("lang")
    inner.setMinimumSize(280, 900)
    area.setWidget(inner)
    root.show()
    settle()
    try:
        ports = function_walk.QtPorts(None, 0.0)
        viewport = area.viewport()
        whole = QRect(viewport.mapToGlobal(QPoint(0, 0)), viewport.size())
        shown = function_walk._shown(viewport)
        assert shown != whole and whole.contains(shown), (shown, whole)

        def roll(rect: QRect) -> Any:
            return SimpleNamespace(
                rect=rect,
                why="rollen",
                target="param.x",
                button=Qt.MouseButton.NoButton,
                direction=1,
            )

        hit = ports.widget_under(whole.center())
        assert hit is viewport or viewport.isAncestorOf(hit), hit
        assert ports.covers(roll(whole), hit), "die ganze Sichtfläche"
        assert ports.covers(roll(shown), hit), "ihr sichtbarer Teil"

        cover = QListWidget(root)
        cover.addItem("darüber")
        cover.setGeometry(QRect(root.mapFromGlobal(whole.center()) - QPoint(40, 20), QSize(80, 40)))
        cover.raise_()
        cover.show()
        settle()
        hit = ports.widget_under(whole.center())
        assert hit is cover or cover.isAncestorOf(hit), hit
        assert not ports.covers(roll(whole), hit), "eine Liste über der Rollfläche"
    finally:
        root.close()
        root.deleteLater()
        settle()


@pytest.mark.parametrize(
    "kind, text, expected",
    [
        ("plain", "A & B <b>wörtlich</b> &nbsp;", "A & B <b>wörtlich</b> &nbsp;"),
        ("auto", "A & B", "A & B"),
        ("auto", "<b>A&nbsp;&amp;&nbsp;B</b>", "A & B"),
        ("rich", "&nbsp;A&amp;B&nbsp;", " A&B "),
        ("rich", "&lt;b&gt;X&lt;/b&gt; &#43; &#x2212;", "<b>X</b> + −"),
        ("button", "&Datei && Ablage", "Datei & Ablage"),
        ("button", "<b>&Datei</b>", "<b>Datei</b>"),
        ("button", "A&", "A"),
        ("button", "A&&&", "A&"),
        ("buddy", "A&\nB", "A\nB"),
        ("group", "&Datei && Ablage", "Datei & Ablage"),
        ("buddy", "&Datei && Ablage", "Datei & Ablage"),
        ("rich_buddy", "<b>&amp;Datei &amp;&amp; Ablage</b>", "Datei & Ablage"),
        ("tab", "&Datei && Ablage", "Datei & Ablage"),
    ],
)
def test_text_capture_respects_entities_formats_and_mnemonic_carriers(
    qt_app: Any, kind: str, text: str, expected: str
) -> None:
    """FD76: Sichtbarer Text statt HTML-Reste oder pauschal entfernter Ampersands."""
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtWidgets import QGroupBox, QLabel, QLineEdit, QPushButton, QTabBar, QWidget

    root = QWidget()
    root.resize(900, 200)
    if kind == "button":
        carrier = QPushButton(text, root)
    elif kind == "group":
        carrier = QGroupBox(text, root)
    elif kind == "tab":
        carrier = QTabBar(root)
        carrier.addTab(text)
    else:
        carrier = QLabel(text, root)
        if kind == "plain":
            carrier.setTextFormat(Qt.TextFormat.PlainText)
        elif kind in ("rich", "rich_buddy"):
            carrier.setTextFormat(Qt.TextFormat.RichText)
        if kind in ("buddy", "rich_buddy"):
            carrier.setBuddy(QLineEdit(root))
    carrier.setGeometry(20, 60, 850, 60)
    try:
        root.show()
        qt_app.processEvents()
        entries = capture.text_entries(root)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["text"] == expected
        assert not entry["cut"], entry
        # Ein HTML-ähnlicher Plaintext darf auch am gemeinsamen Namensweg nicht verschwinden.
        if kind != "tab":
            assert capture.name_of(carrier) == expected
    finally:
        root.close()
        root.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("narrow", [False, True], ids=["passt", "wirklich_zu_schmal"])
def test_real_preview_legend_keeps_its_visible_text_and_the_public_p9_guard(
    qt_app: Any, narrow: bool
) -> None:
    """FD76: Echte Vorschaulegende ohne falschen P9-Fund; echter Platzmangel bleibt rot."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QWidget

    from app.i18n import tr
    from app.ui.viewport import PreviewBanner
    from tools.function_points import judge_case
    from tools.function_samples import sample_context, sample_protocol

    root = QWidget()
    root.resize(1920, 1080)
    banner = PreviewBanner(root)
    try:
        root.show()
        banner.show_preview("Vorschau", "blue_orange", "Vorher")
        qt_app.processEvents()
        expected = f" + {tr('Hinzugefügt')}    - {tr('Entfernt')} "
        assert "&nbsp;" in banner.legend.text(), "Der echte Träger muss Entities enthalten"
        if narrow:
            banner.legend.setFixedWidth(1)
            qt_app.processEvents()
        entries = capture.text_entries(banner)
        legend = next(entry for entry in entries if tr("Hinzugefügt") in entry["text"])
        assert legend["text"] == expected
        assert legend["cut"] is narrow, legend
        protocol = sample_protocol()
        protocol["texts"] = [legend]
        outcome = judge_case(protocol, sample_context()).points[9]
        assert (outcome.verdict == "fund") is narrow, outcome
        assert bool(outcome.issues) is narrow
    finally:
        root.close()
        root.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_text_needs_count_box_symbol_padding_rich_text_and_list_cells(qt_app: Any) -> None:
    """Review M12 und L3 an echten Widgets.

    Je Widget genau so breit wie sein Text: Ein Haken braucht sein Kästchen, ein
    Knopf mit Symbol Symbol und Polsterung — beide abgeschnitten; der Kontrollfall
    ``QLabel`` passt genau. Rich Text zählt mit seinem sichtbaren Text, eine
    schmale Listenzelle ist abgeschnitten. Ein Symbolknopf trägt die Farbe seines
    Symbols, und „groß“ beginnt bei 18 pt (fett 14 pt).
    """
    from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QLabel,
        QListWidget,
        QPushButton,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )

    root = QWidget()
    root.resize(600, 500)
    layout = QVBoxLayout(root)
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("#ff0000"))
    label = QLabel("Durchmesser ändern", root)
    box = QCheckBox("Durchgehend bohren", root)
    button = QPushButton(QIcon(pixmap), "Mit Symbol übernehmen", root)
    rich = QLabel("<b>Fett</b> und <i>schräg</i>", root)
    listing = QListWidget(root)
    listing.addItem("Ein sehr langer Eintrag, der in keine schmale Liste passt")
    symbol = QToolButton(root)
    symbol.setIcon(QIcon(pixmap))
    for widget in (label, box, button, rich, listing, symbol):
        layout.addWidget(widget)
    root.show()
    QApplication.processEvents()
    for widget in (label, box, button):
        text_px = widget.fontMetrics().horizontalAdvance(widget.text().replace("&", ""))
        widget.setFixedWidth(text_px + (widget.width() - widget.contentsRect().width()))
    listing.setFixedWidth(120)
    QApplication.processEvents()
    texts = {entry["text"]: entry for entry in capture.text_entries(root)}
    assert texts["Durchmesser ändern"]["cut"] is False, "Kontrollfall: das Etikett passt"
    assert texts["Durchgehend bohren"]["cut"] is True, "das Kästchen braucht Platz"
    assert texts["Mit Symbol übernehmen"]["cut"] is True, "Symbol und Polsterung brauchen Platz"
    assert "Fett und schräg" in texts, "Rich Text zählt mit seinem sichtbaren Text"
    cell = texts["Ein sehr langer Eintrag, der in keine schmale Liste passt"]
    assert cell["carrier"] == "QListWidget.Zeile" and cell["cut"] is True
    contrast = {entry["widget"]: entry for entry in capture.contrast_entries(root, "light")}
    (painted,) = [entry for entry in contrast.values() if entry["symbol"]]
    assert painted["foreground"] == "#ff0000"
    big = QLabel("Groß", root)
    big.setFont(QFont(big.font().family(), 16))
    bold = QLabel("Fett", root)
    font = QFont(bold.font().family(), 14)
    font.setBold(True)
    bold.setFont(font)
    layout.addWidget(big)
    layout.addWidget(bold)
    QApplication.processEvents()
    contrast = {entry["widget"]: entry for entry in capture.contrast_entries(root, "light")}
    assert contrast["Groß"]["large"] is False, "16 pt ist nach WCAG nicht groß"
    assert contrast["Fett"]["large"] is True
    root.close()
    root.deleteLater()


#: Tippt im eigenen Prozess Umlaute, ß und Zeichen außerhalb von Latin-1 über
#: ``QtPorts.type_text`` in eine Zeile und gibt deren Text aus.
_TYPING = """
import sys
sys.path.insert(0, sys.argv[1])
from PySide6.QtWidgets import QApplication, QLineEdit
from tools.function_walk import QtPorts
application = QApplication([])
line = QLineEdit()
line.show()
line.activateWindow()
line.setFocus()
for _ in range(10):
    application.processEvents()
QtPorts(None, 0.0).type_text(sys.argv[2])
application.processEvents()
print(line.text(), flush=True)
"""


@pytest.mark.windowed
def test_typing_umlauts_and_signs_reaches_the_field_without_aborting_qt(tmp_path: Path) -> None:
    """Probelauf, Befund A: Die Suchprobe „Bohrung vergrößern“ brach den Fall nativ ab.

    ``QTest.keyClicks`` kennt nur ASCII; an ö und ß endet Qt mit einem ASSERT in
    ``qasciikey.cpp`` (Ausgang 0xC0000409), ohne eine Zeile in ``stderr.log``.
    Im eigenen Prozess, denn vorher riss der Abbruch den Testlauf mit.
    """
    import os
    import subprocess
    import sys

    text = "Bohrung vergrößern 5,0 € É"
    script = tmp_path / "tippen.py"
    script.write_text(_TYPING, encoding="utf-8")
    finished = subprocess.run(
        [sys.executable, str(script), str(ROOT), text],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert finished.returncode == 0, (hex(finished.returncode & 0xFFFFFFFF), finished.stderr)
    assert finished.stdout.strip() == text


def test_typing_needs_the_focus_in_the_field_and_actions_need_a_vocabulary_name(
    qt_app: Any,
) -> None:
    """Review M13 und M11 an echten Widgets.

    Getippt wird nur, wenn der Fokus im Feld des Ziels liegt — auch in der
    Textzeile eines Zahlenfelds; sonst ein Fehler, der das Fokuswidget nennt.
    Eine Handlung einer Meldung hat nur mit Wortschatzkennzeichen ein Ziel; ein
    ``objectName`` ist keines.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit, QPushButton, QWidget

    from app.core.guides import TARGET_PROPERTY

    root = QWidget()
    spin = QDoubleSpinBox(root)
    other = QLineEdit(root)
    other.move(0, 40)
    root.show()
    root.activateWindow()
    spin.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    function_walk.focus_check(spin, "feature.field:resize_hole.diameter")
    other.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    with pytest.raises(RuntimeError, match="QLineEdit"):
        function_walk.focus_check(spin, "feature.field:resize_hole.diameter")
    with pytest.raises(RuntimeError, match="kein Feld"):
        function_walk.focus_check(None, "search")
    named = QPushButton("Auf das Bett legen", root)
    named.setProperty(TARGET_PROPERTY, "finding.action:place_on_bed")
    plain = QPushButton("Ohne Namen", root)
    plain.setObjectName("handlung_ohne_namen")
    assert capture.vocabulary_name(named) == "finding.action:place_on_bed"
    assert capture.vocabulary_name(plain) == ""
    root.close()
    root.deleteLater()


def test_the_halt_reason_is_read_where_the_report_shows_it(window: Any, tmp_path: Path) -> None:
    """Review M10: Der Haltgrund ist die Zeile des Prüfberichts am angehaltenen Schritt.

    Die Szene ``halt`` hält ihre Kette an. Gelesen wird der Text der
    Berichtszeile, deren Befund am angehaltenen Schritt steht, und als Nummer
    die, die der Verlauf dem Schritt gibt — nicht „der erste Text mit einer Zahl“.
    Ob der Text die Nummer nennt, urteilt U (Prüfpunkt 15).
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.ui.labels import step_number

    scenes = tmp_path / "scenes"
    row = {**_probe_row(scenes), "start_scene": "halt", "spec": {"start_scene": "halt"}}
    variant = function_setup.Variant.of({"phases": ["halt"]})
    data = function_protocol.empty_protocol(
        row, variant.protocol(None, (0, 0)), {"commit": "", "app": ""}
    )
    folder = tmp_path / "cases" / "001"
    folder.mkdir(parents=True)
    flow = function_bench.FunctionFlow(
        QApplication.instance(), window, folder, data, lambda: None, row, variant, scenes,
        out=tmp_path,
    )  # fmt: skip
    flow.prepare()
    assert flow.reset(), data["errors"]
    result = window.session.last_result
    assert result is not None and result.stopped_at is not None, "die Szene hält an"
    flow.read_halt()
    halt = data["halt"]
    assert halt is not None, data["unmeasured"]
    assert halt["step"] == step_number(window.session.project.document, result.stopped_at)
    shown = [
        window.report.list.item(row).text()
        for row in range(window.report.list.count())
        if getattr(window.report.list.item(row).data(Qt.ItemDataRole.UserRole), "op_id", None)
        == result.stopped_at
    ]
    assert halt["text"] in shown
    flow.finish()


@pytest.mark.windowed
def test_the_project_switch_runs_in_preview_draft_and_computation(tmp_path: Path) -> None:
    """Prüfpunkt 16 (Koordinator, Konzept §4): Wechsel während Vorschau, Entwurf und Rechnung.

    Die Probezeile im eigenen Prozess, nur die Phase ``switch``. Vorschau und
    Entwurf werden gemessen; die Rechnung, wenn sie beim ersten Wechselklick
    noch läuft — sonst steht der Grund in ``unmeasured``. Keine Phase endet in
    einem Fehler, und das Protokoll ist gültig.
    """
    out = tmp_path / "wechsel"
    _run_acceptance(
        out,
        ["inventory", "--functions", "--rows", PROBE_ROW, "--phases", "switch"],
        ["run", "--timeout", "900"],
    )
    protocol = json.loads((out / "cases" / "001" / "function.json").read_text(encoding="utf-8"))
    assert validate_protocol(protocol) == []
    assert protocol["errors"] == [], protocol["errors"]
    switch = protocol["switch"]
    # Review N3: Kam der Wechsel nicht an, steht der Grund in den Funden, nicht
    # nur in ``unmeasured`` — die Meldung nennt beides.
    assert switch is not None, (protocol["unmeasured"], protocol["findings"])
    assert {"vorschau", "entwurf"} <= set(switch["phases"]), (switch, protocol["findings"])
    if "rechnung" not in switch["phases"]:
        assert "rechnung" in protocol["unmeasured"].get("switch", ""), protocol["unmeasured"]
    assert all(event["phase"] in switch["phases"] for event in switch["late_events"])


def _run_acceptance(out: Path, *arguments: list[str]) -> None:
    """``tools/file_acceptance.py`` in eigenen Prozessen, offscreen, je Aufruf ein Prozess."""
    import os
    import subprocess
    import sys

    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONUTF8": "1"}
    for argument in arguments:
        finished = subprocess.run(
            [sys.executable, str(ACCEPTANCE), *argument, "--out", str(out)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=1200,
            check=False,
        )
        assert finished.returncode == 0, (finished.stdout, finished.stderr)


@pytest.mark.windowed
def test_the_expired_demo_row_starts_through_main_and_stops(tmp_path: Path) -> None:
    """D12 „Demo abgelaufen“: der Startfall über ``app.ui.app.main`` im eigenen Prozess (S1).

    Das Starttor wird nicht umgangen: Der Fall setzt nur den Zustand über die
    Nahtstelle der Suite und ruft ``main``. Die Anwendung startet nicht, zeigt den
    Grund, der Prüfstand schließt die Meldung mit *Schließen* samt Probe, und
    ``main`` endet mit seinem eigenen Ausgang.
    """
    out = tmp_path / "start"
    _run_acceptance(
        out,
        ["inventory", "--functions", "--rows", "startup.expired_demo"],
        ["run", "--timeout", "600"],
    )
    (case,) = read_cases(out)
    assert (case.kind, case.variant["licence"]) == ("start", STARTUP_LICENCE)
    folder = out / "cases" / "001"
    state = json.loads((folder / "bench.json").read_text(encoding="utf-8"))
    assert state["stage"] == "done" and state["main_exit_code"] == 1, state
    protocol = json.loads((folder / "function.json").read_text(encoding="utf-8"))
    assert validate_protocol(protocol) == []
    assert protocol["variant"]["licence"] == STARTUP_LICENCE
    assert protocol["errors"] == [] and protocol["findings"] == []
    assert protocol["result"]["metrics"] == {
        "exit_code": 1,
        "main_window": False,
        "message_shown": True,
    }
    (message,) = protocol["messages"]
    assert message["text"].strip()
    assert [action["clicked"] for action in message["actions"]].count(True) == 1
    (click,) = protocol["steps"]
    assert click["hit"] is True and click["phase"] == "start"
    # Seit FD-21 eine Meldung im Hausstil: modal, aber kein rohes Qt-Fenster (Z5).
    assert [entry["class"] for entry in protocol["modals"]] == ["MessageDialog"]
    assert protocol["raw_windows"] == []
    report = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert (report["function_cases"], report["function_complete"]) == (1, 1)


def test_the_captures_read_a_small_dialog_without_acting_on_it(qt_app: Any) -> None:
    """Die Aufnahmen an einem kleinen, gezeigten Dialog: Texte, Felder, Layout, Tab-Kette, Zustände.

    Offscreen gibt es keine Schrift (``tests.md``) — geprüft werden Gestalt
    und Herkunft der Daten, nicht Pixelbreiten; jede Liste ist gegen U's Schema
    gültig. Die Zustandsbilder drücken den Knopf, lassen ihn aber außerhalb los:
    Er löst nicht aus.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QDialog,
        QDoubleSpinBox,
        QFormLayout,
        QLabel,
        QListWidget,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    from app.core.guides import TARGET_PROPERTY

    dialog = QDialog()
    outer = QVBoxLayout(dialog)
    outer.addWidget(QLabel("Bohrt ein rundes Loch.", dialog))
    form = QFormLayout()
    outer.addLayout(form)
    spin = QDoubleSpinBox(dialog)
    spin.setAccessibleName("Bohrung ändern — Durchmesser")
    spin.setToolTip("Wie weit die Bohrung wird.")
    spin.setProperty(TARGET_PROPERTY, "feature.field:resize_hole.diameter")
    form.addRow(QLabel("Durchmesser", dialog), spin)
    through = QCheckBox("Durchgehend", dialog)
    form.addRow(through)
    empty = QListWidget(dialog)
    outer.addWidget(empty)
    outer.addWidget(QLabel("Noch kein Eintrag", dialog))
    area = QScrollArea(dialog)
    tall = QWidget()
    tall.setMinimumHeight(2000)
    area.setWidget(tall)
    area.setFixedHeight(80)
    outer.addWidget(area)
    accept = QPushButton("Übernehmen", dialog)
    accept.setDefault(True)
    clicked: list[bool] = []
    accept.clicked.connect(lambda: clicked.append(True))
    outer.addWidget(accept)
    notice = QMessageBox(QMessageBox.Icon.Information, "Hinweis", "Roh", parent=dialog)
    watch = capture.ModalWatch(0.0)
    try:
        dialog.show()
        dialog.activateWindow()
        QApplication.processEvents()
        protocol: dict[str, Any] = {
            "texts": capture.text_entries(dialog),
            "fields": capture.field_entries(dialog),
            "empty_states": capture.empty_states(dialog),
            **capture.sheet_snapshot(dialog, "light", SMALLEST_WINDOW),
        }
        texts = {entry["text"]: entry for entry in protocol["texts"]}
        assert {"Durchmesser", "Durchgehend", "Übernehmen", "Noch kein Eintrag"} <= set(texts)
        assert texts["Bohrt ein rundes Loch."]["lead"] is True
        assert texts["Übernehmen"]["lead"] is False
        fields = {entry["accessible_name"]: entry for entry in protocol["fields"]}
        diameter = fields["Bohrung ändern — Durchmesser"]
        assert diameter["label"] == "Durchmesser" and diameter["front"] is True
        assert diameter["tooltip"] == "Wie weit die Bohrung wird."
        assert capture.field_values(dialog)["resize_hole.diameter"] == pytest.approx(0.0)
        kinds = [entry["kind"] for entry in protocol["layout"]]
        assert kinds[0] == "primary" and "form" in kinds and "spacing" in kinds
        assert protocol["layout"][0]["primary"] == 1
        assert any(entry["vertical"] for entry in protocol["scrollbars"])
        assert any("Noch kein Eintrag" in entry["sentence"] for entry in protocol["empty_states"])
        # Review S4: Der Fokus steht am Hauptknopf, wie früher nach den
        # Zustandsbildern. Die Kette beginnt trotzdem am ersten Feld, läuft in
        # Lesefolge und endet mit dem Glied, das wiederkommt — U zählt es nicht.
        QTest.mouseClick(accept, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.processEvents()
        clicked.clear()
        assert QApplication.focusWidget() is accept

        def press_tab() -> None:
            focus = QApplication.focusWidget()
            assert focus is not None
            QTest.keyClick(focus, Qt.Key.Key_Tab)

        focused: dict[str, str] = {}

        def on_focus(widget: Any) -> None:
            if widget is accept:
                focused["digest"] = capture.picture_digest(accept)

        chain = capture.tab_chain(dialog, press_tab, limit=12, on_focus=on_focus)
        assert chain[0]["name"] == "Bohrung ändern — Durchmesser" and len(chain) >= 3
        assert all(entry["inside"] for entry in chain)
        assert chain[-1]["name"] == chain[0]["name"], "das Schlussglied kommt wieder"
        from tools.function_points import _reading_order_jumps, _within_chain

        within = _within_chain(chain)
        assert len(within) == len(chain) - 1
        assert (
            _reading_order_jumps([(entry["name"], tuple(entry["rect"])) for entry in within]) == []
        )
        protocol["tab_chain"] = chain
        # Review L2: „Fokus“ ist das Bild, das die Kette am Knopf aufnahm.
        assert focused["digest"]
        protocol["state_images"] = [
            {
                "surface": "QDialog",
                "widget": "Übernehmen",
                "states": capture.state_images(accept, focused["digest"]),
            }
        ]
        assert set(protocol["state_images"][0]["states"]) == set(capture.STATES)
        assert protocol["state_images"][0]["states"]["focus"] == focused["digest"]
        assert clicked == [], "der Druck für das Bild löste den Knopf aus"
        reacting = QPushButton("Halten", dialog)
        reacting.pressed.connect(lambda: clicked.append(False))
        reacting.show()
        QApplication.processEvents()
        assert "pressed" not in capture.state_images(reacting), "Drücken hätte ausgelöst"
        assert clicked == []
        notice.show()
        QApplication.processEvents()
        watch.poll()
        protocol["raw_windows"] = watch.raw_entries()
        protocol["windows"] = watch.windows
        assert [entry["class"] for entry in protocol["raw_windows"]] == ["QMessageBox"]
        assert protocol["raw_windows"][0]["allowed"] is False
        complete = {**dict.fromkeys(PROTOCOL_SCHEMA), **protocol, **_required()}
        assert validate_protocol(complete) == []
    finally:
        notice.close()
        dialog.close()
        notice.deleteLater()
        dialog.deleteLater()
        QApplication.processEvents()


def _required() -> dict[str, Any]:
    protocol = function_protocol.empty_protocol(
        ROWS[0], function_setup.Variant().protocol(None, (0, 0)), {}
    )
    return {key: protocol[key] for key in ("row", "kind", "package", "variant", "version")}
