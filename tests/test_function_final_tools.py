"""Werkzeug für den Schlusslauf am echten Fenster (Plan Schluss §1.5, Entscheidungen §6).

Was der Prüfstand für die Punkte braucht, die der finale Lauf nicht belegen
konnte: 125 % (FD-109), die Inhaltsschrift 14 und 18 pt samt Wechsel
(FD-54, 57, 58, 185), das Bild im gehaltenen Zug (FD-73), der Weg aus dem
Verlauf in den Zeichenmodus, die Kurzhilfe am grauen *Übernehmen* (FD-99), der
Tastaturweg ab der Reiterleiste (FD-177), der zweite Schritt eines Wegs
(FD-36) und eine Gesamtfrist für ``file_acceptance run``. Ohne natives
Fenster; die Fälle mit ``qt_app`` laufen offscreen.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tools import function_setup
from tools.function_checks import SCALES, SMALLEST_AVAILABLE

#: Der Messschirm des Schlusslaufs (MSI MAG271CQR): 2560 x 1440 bei 100 %, die
#: Taskleiste 48 Punkte hoch.
MSI: tuple[int, int] = (2560, 1440)
TASKBAR = 48


def _logical(scale: float) -> list[int]:
    """Die verfügbare logische Fläche des Messschirms bei ``scale`` (wie ``availableGeometry``)."""
    return [0, 0, int(MSI[0] / scale), int((MSI[1] - TASKBAR) / scale)]


def test_125_percent_is_a_case_on_the_measuring_screen_and_150_200_are_not() -> None:
    """FD-109 „bei 125 %“: 2048 x 1152 logisch am MSI, ein gültiger Fall (Entscheidung §6.3).

    150 und 200 % drücken den Schirm unter die kleinste Arbeitsfläche; das
    Protokoll nennt dann den Grund, statt zu messen.
    """
    assert 1.25 in SCALES
    scaled = {
        entry["scale"] for entry in function_setup.variant_sets()["skalierung"] if "scale" in entry
    }
    assert scaled == {scale for scale in SCALES if scale != 1.0}
    assert (int(MSI[0] / 1.25), int(MSI[1] / 1.25)) == (2048, 1152)
    quarter = function_setup.Variant.of({"set": "skalierung", "scale": 1.25})
    area = _logical(1.25)
    assert area[2] >= SMALLEST_AVAILABLE[0] and area[3] >= SMALLEST_AVAILABLE[1]
    assert function_setup.below_smallest({"screen": "MSI", "geometry": area}, quarter) == ""
    for scale in (1.5, 2.0):
        variant = function_setup.Variant.of({"set": "skalierung", "scale": scale})
        reason = function_setup.below_smallest(
            {"screen": "MSI", "geometry": _logical(scale)}, variant
        )
        assert "kein Fall" in reason and "kleinsten Arbeitsfläche" in reason, reason


# --- Werkzeug 1: Inhaltsschrift 14 und 18 pt, Wechsel 9 → 14 → 9 pt (FD-54, 57, 58, 185) --


def test_the_font_sets_exist_and_only_carry_fonts_there() -> None:
    sets = function_setup.variant_sets()
    assert [entry["font"] for entry in sets["schrift"]] == [14.0, 18.0]
    assert [tuple(entry["font_change"]) for entry in sets["schriftwechsel"]] == [(9.0, 14.0, 9.0)]
    assert function_setup.PHASES["schrift"] == ("surface",)
    assert function_setup.PHASES["schriftwechsel"] == ("fontchange",)
    changing = function_setup.Variant.of(sets["schriftwechsel"][0])
    assert function_setup.Variant.of(changing.as_dict()) == changing
    for broken in (
        {"set": "basis", "font": 14.0},
        {"set": "schrift", "font": -1.0},
        {"set": "schriftwechsel", "font_change": [9.0, 0.0]},
    ):
        with pytest.raises(ValueError):
            function_setup.Variant.of(broken)


def test_the_content_font_goes_through_the_style_of_the_application(qt_app: Any) -> None:
    """Wie ein Wechsel der Systemschrift: Schrift der Anwendung und ihr Stylesheet folgen."""
    from tools.function_fonts import set_content_font

    before = qt_app.styleSheet()
    assert set_content_font(qt_app, 18.0, "light") == 18.0
    assert qt_app.font().pointSizeF() == 18.0
    assert qt_app.styleSheet() != before, "das Stylesheet rechnet mit der neuen Größe"


def test_the_font_change_records_every_stage_narrow_and_wide(qt_app: Any) -> None:
    """FD-57/58: je Stufe Schrift, Größe, Ruhe, Bild, abgeschnittene Texte — schmal, groß."""
    from types import SimpleNamespace

    from PySide6.QtWidgets import QLabel, QWidget

    from tools import function_bench
    from tools.function_checks import SMALLEST_WINDOW
    from tools.function_machine import Step

    window = QWidget()
    surface = QLabel("Auswahl", window)
    flow = object.__new__(function_bench.FunctionFlow)
    flow.application = qt_app
    flow.window = window
    flow.variant = function_setup.Variant.of(function_setup.variant_sets()["schriftwechsel"][0])
    flow.data = {"images": [], "unmeasured": {}}
    flow.surface = lambda: surface
    flow.path_steps = list
    flow.picture = lambda label: flow.data["images"].append(f"cases/001/{label}.png")
    flow.window_size = lambda: [window.width(), window.height()]

    def still(name: str, root: Any) -> Step:
        if name == "schrift-2-14pt-gross":
            # Eine Fläche, die nach dem Wechsel nicht zur Ruhe kommt (FD-57).
            flow.data["unmeasured"][f"still:{name}"] = "ohne Stillstand"
        return Step(name, lambda machine: None)

    flow.still_step = still

    def run_steps(label: str, steps: list[Any], timeout_s: float | None = None) -> bool:
        for step in steps:
            step.act(SimpleNamespace(insert=lambda more: None))
        return True

    flow.run_steps = run_steps
    try:
        flow.phase_fontchange()
    finally:
        window.close()
    stages = flow.data["font_change"]
    assert [stage["wanted"] for stage in stages] == [9.0, 14.0, 9.0]
    assert [stage["points"] for stage in stages] == [9.0, 14.0, 9.0]
    assert stages[0]["window"] == list(SMALLEST_WINDOW) == stages[2]["window"]
    assert [stage["still"] for stage in stages] == [True, False, True]
    assert [stage["image"] for stage in stages] == [
        "cases/001/schrift-1-9pt-schmal.png",
        "cases/001/schrift-2-14pt-gross.png",
        "cases/001/schrift-3-9pt-schmal.png",
    ]
    assert all(isinstance(stage["cut"], list) for stage in stages)


# --- Werkzeug 2: das Bild im gehaltenen Zug (FD-73) ------------------------------------


def _drag_flow(qt_app: Any, row_set: str, spec: dict[str, Any]) -> tuple[Any, list[str]]:
    """Ein Fall mit einem echten Griff-Widget; ``events`` hält Druck, Bild und Loslassen."""
    from types import SimpleNamespace

    from PySide6.QtCore import QEvent, QObject, QRect
    from PySide6.QtWidgets import QWidget

    from tools import function_bench

    events: list[str] = []

    class Spy(QObject):
        def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qts Name
            kinds = {QEvent.Type.MouseButtonPress: "druck", QEvent.Type.MouseButtonRelease: "los"}
            if event.type() in kinds:
                events.append(kinds[event.type()])
            return False

    grip = QWidget()
    grip.resize(80, 40)
    grip.show()
    spy = Spy(grip)
    grip.installEventFilter(spy)
    click = SimpleNamespace(rect=QRect(grip.mapToGlobal(grip.rect().topLeft()), grip.size()))
    flow = object.__new__(function_bench.FunctionFlow)
    flow.application = qt_app
    flow.window = SimpleNamespace(viewport=SimpleNamespace())
    flow.row = {"id": "slot_hole", "target": "feature:slot_hole"}
    flow.spec = spec
    flow.variant = function_setup.Variant.of({"set": row_set, "theme": "dark"})
    flow.data = {"images": [], "unmeasured": {}}
    flow.frames_wrapped = True
    flow.ports = SimpleNamespace(
        next_click=lambda name: click,
        centre=lambda rect: rect.center(),
        widget_under=lambda point: grip,
        covers=lambda found, hit: hit is grip,
    )
    flow.path_steps = list
    flow.picture = lambda label: (events.append(label), flow.data["images"].append(label))

    def run_steps(label: str, steps: list[Any], timeout_s: float | None = None) -> bool:
        for step in steps:
            step.act(SimpleNamespace(insert=lambda more: None))
        return True

    flow.run_steps = run_steps
    flow._keep = (grip, spy)
    return flow, events


def test_the_held_drag_is_pictured_before_the_release(qt_app: Any) -> None:
    """FD-73: Das Griffmaß steht nur, solange die Taste gehalten wird — dort entsteht das Bild."""
    from tools.function_gestures import HELD_PICTURE

    flow, events = _drag_flow(qt_app, "basis", {"drag": "handle:slot.end"})
    flow.phase_drag()
    assert events == ["druck", HELD_PICTURE, "los"], events
    # Im dunklen Thema zieht nur eine Zeile, die ihren Griff nennt.
    dark, dark_events = _drag_flow(qt_app, "dunkel", {"drag": "handle:slot.end"})
    dark.phase_drag()
    assert dark_events == ["druck", HELD_PICTURE, "los"], dark_events
    plain, plain_events = _drag_flow(qt_app, "dunkel", {})
    plain.phase_drag()
    assert plain_events == [] and plain.data["unmeasured"] == {}


def test_the_slot_row_names_its_grip() -> None:
    from tools.function_list import SPEC_KEYS, load_specs

    assert "drag" in SPEC_KEYS
    assert load_specs()["slot_hole"].values["drag"] == "handle:slot.end"


# --- Werkzeug 4: der Zeichenmodus aus dem Verlauf ---------------------------------------


def test_the_drawing_mode_is_reached_from_the_history() -> None:
    """*Fertig* im Zeichenmodus über *Zeichnung weiterverwenden* am Verlaufsschritt (§6.4).

    Vorher führte jeder D7-Weg über den Dichtweg-Editor; der Zeichenmodus im
    Raum stand in keiner Spezifikation.
    """
    from tools.function_list import load_specs, rows, validate_specs
    from tools.function_scenes import load_scenes

    spec = load_specs()["sketch.done"].values
    assert [step["target"] for step in spec["route"]] == [
        "history.row:2",
        "history:reuse_drawing",
    ]
    scenes = load_scenes()
    scene = scenes[spec["start_scene"]]
    assert [step.op for step in scene.ops][-1] == "sketch_pocket"
    assert '"plane"' in str(scene.ops[-1].params["sketch"])
    only = {"sketch.done": load_specs()["sketch.done"]}
    assert validate_specs(rows(with_specs=False), only, scenes) == []


# --- Werkzeug 5: Kurzhilfe am grauen Übernehmen, Tab ab der Reiterleiste, Weg in Schritten -


def test_the_reason_of_a_grey_apply_is_pictured_on_the_main_path(
    qt_app: Any, tmp_path: Any
) -> None:
    """FD-99: Der Grund stand nur im Protokoll; das Bild entstand nur im Fehlfall."""
    import inspect

    from PySide6.QtWidgets import QPushButton

    from tools import function_bench, function_tooltips

    apply = QPushButton("Übernehmen")
    apply.setToolTip("Erst „Durchmesser“ ändern, dann übernehmen.")
    apply.setEnabled(False)
    apply.show()
    qt_app.processEvents()
    folder = tmp_path / "cases" / "001"
    folder.mkdir(parents=True)
    flow = SimpleNamespace(
        widget={"feature.apply": apply}.get,
        folder=folder,
        out=tmp_path,
        data={"images": []},
    )
    try:
        function_tooltips.grey_apply_step(flow, "feature.apply").act(None)
        assert flow.data["images"] == ["cases/001/02-uebernehmen-grund-1.png"]
        apply.setEnabled(True)
        function_tooltips.grey_apply_step(flow, "feature.apply").act(None)
        assert len(flow.data["images"]) == 1, "ein offener Knopf hat kein Grundbild"
    finally:
        apply.close()
    # Angeschlossen: Der Hauptweg nimmt den Schritt vor den Eingaben.
    source = inspect.getsource(function_bench.FunctionFlow.phase_main)
    assert source.index("grey_apply_step") < source.index("self.input_steps(inputs)")


def test_the_keyboard_way_starts_at_the_tab_bar(qt_app: Any) -> None:
    """FD-177: Von der Reiterleiste führt Tab auf die vordere Seite — gemessen wird es jetzt.

    Die Kette des Hauptwegs beginnt am ersten Feld der Fläche; den Weg von der
    Leiste ging sie nie.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLineEdit, QTabWidget, QVBoxLayout, QWidget

    from tools import function_bench, function_capture

    tabs = QTabWidget()
    page = QWidget()
    first, second = QLineEdit(page), QLineEdit(page)
    first.setAccessibleName("Erstes Feld")
    layout = QVBoxLayout(page)
    layout.addWidget(first)
    layout.addWidget(second)
    tabs.addTab(page, "Prüfbericht")
    tabs.addTab(QWidget(), "Chat")
    tabs.show()
    qt_app.processEvents()

    def press(sequence: str) -> None:
        backwards = sequence == "Shift+Tab"
        key = Qt.Key.Key_Backtab if backwards else Qt.Key.Key_Tab
        modifier = (
            Qt.KeyboardModifier.ShiftModifier if backwards else Qt.KeyboardModifier.NoModifier
        )
        QTest.keyClick(QApplication.focusWidget(), key, modifier)

    try:
        chain = function_capture.bar_chain(first, press)
        assert chain[0]["class"] == "QTabBar" and not chain[0]["inside"]
        assert chain[1]["name"] == "Erstes Feld" and chain[1]["inside"], chain
        assert function_capture.bar_chain(QLineEdit(), press) == []
    finally:
        tabs.close()
    import inspect

    assert "bar_chain" in inspect.getsource(function_bench.FunctionFlow.phase_main)


def test_a_way_in_two_steps_is_walked_to_its_end(qt_app: Any) -> None:
    """FD-36: „zuerst „Abbrechen“, danach „Merkmal entfernen““ — beide Schritte, der zweite wirkt.

    Gelesen wurde der Satz, geklickt höchstens die erste Handlung; ob
    *Merkmal entfernen* danach frei ist, prüfte niemand.
    """
    import time

    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from tools import function_bench
    from tools.function_machine import Step
    from tools.function_walk import QtPorts, Walk

    window = QWidget()
    cancel = QPushButton("Abbrechen", window)
    remove = QPushButton("Merkmal entfernen", window)
    remove.setEnabled(False)
    cancel.clicked.connect(lambda: (cancel.hide(), remove.setEnabled(True)))
    removed: list[bool] = []
    remove.clicked.connect(lambda: (removed.append(True), remove.hide()))
    layout = QVBoxLayout(window)
    layout.addWidget(cancel)
    layout.addWidget(remove)
    window._op_dialog = None  # wie am Hauptfenster: kein Operationsdialog offen
    window.show()
    qt_app.processEvents()
    flow = object.__new__(function_bench.FunctionFlow)
    flow.window = window
    flow.ports = QtPorts(window, time.perf_counter())
    flow.walker = Walk(flow.ports, [], time.perf_counter())
    flow.scene_now = dict
    flow.pump = qt_app.processEvents

    def run_steps(label: str, steps: list[Step], timeout_s: float | None = None) -> bool:
        for step in steps:
            assert step.ready is not None and step.ready(), step.name
            step.act(SimpleNamespace(insert=lambda more: None))
            qt_app.processEvents()
        return True

    flow.run_steps = run_steps
    text = (
        "0,10 mm liegt unter der Grenze. "
        "Zum Entfernen zuerst „Abbrechen“ wählen, danach „Merkmal entfernen“."
    )
    messages = [{"text": text, "actions": [], "kind": "grenzablehnung", "way_out": True}]
    try:
        flow.walk_ways(messages)
    finally:
        window.close()
    assert messages[0]["way"] == [
        {"title": "Abbrechen", "clicked": True, "effect": True},
        {"title": "Merkmal entfernen", "clicked": True, "effect": True},
    ]
    assert removed == [True]
    # Eine Meldung mit einem Knopf oder ohne Ausweg geht keinen Weg.
    single = [{"text": "Mit „Abbrechen“ zurück.", "actions": [], "way_out": True}]
    flow.walk_ways(single)
    assert "way" not in single[0]


# --- Werkzeug 6: Gesamtfrist und Siegel im Lauf ---------------------------------------


def test_the_run_guard_keeps_a_total_deadline_and_the_seal(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import acceptance_guard, native_binding

    now = {"t": 0.0}
    guard = acceptance_guard.RunGuard(total_s=1000.0, clock=lambda: now["t"])
    assert guard.stop_reason() == "" and guard.case_limit(1800.0) == 1000.0
    now["t"] = 950.0
    assert guard.case_limit(1800.0) == 50.0
    reason = guard.stop_reason()
    assert "Gesamtfrist 1000 s abgelaufen" in reason and "Handlungsvorschlag" in reason
    with pytest.raises(ValueError):
        acceptance_guard.RunGuard(total_s=0.0)
    # Das Siegel: vor jedem Fall gegen die Bindung, ein Bruch ist der Grund.
    checks: list[str] = []
    monkeypatch.setattr(native_binding, "read_binding", lambda path: {"runner": {}})

    def verify(binding: Any, root: Any) -> dict[str, str]:
        checks.append("geprüft")
        if len(checks) > 1:
            raise native_binding.SealError("Siegel gebrochen: tools/x.py", "neu binden")
        return {}

    monkeypatch.setattr(native_binding, "verify", verify)
    sealed = acceptance_guard.RunGuard(binding=Path("bindung.json"))
    assert sealed.stop_reason() == ""
    assert "Siegel gebrochen" in sealed.stop_reason()


def test_the_run_stops_before_the_next_case_and_caps_its_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``run`` fragt die Wache vor jedem Fall und gibt dem Fall höchstens ihre Restzeit."""
    import subprocess

    from tools import file_acceptance as acceptance

    waited: list[float] = []

    class Process:
        pid = 4711

        def __init__(self, *args: Any, **named: Any) -> None:
            pass

        def wait(self, timeout: float | None = None) -> int:
            waited.append(float(timeout or 0.0))
            return 0

    cases = [acceptance.Case(1, "eins", "", ""), acceptance.Case(2, "zwei", "", "")]
    monkeypatch.setattr(acceptance, "read_cases", lambda out: cases)
    monkeypatch.setattr(acceptance, "summary", lambda *args: {})
    monkeypatch.setattr(
        acceptance,
        "subprocess",
        SimpleNamespace(Popen=Process, TimeoutExpired=subprocess.TimeoutExpired),
    )
    reasons = iter(["", "Siegel gebrochen: tools/x.py weicht ab"])
    guard = SimpleNamespace(stop_reason=lambda: next(reasons), case_limit=lambda wanted: 123.0)
    assert acceptance.run(tmp_path, 1, 9, False, 10.0, "", guard) == 1
    assert waited == [123.0]
    out = capsys.readouterr().out
    assert "HALT vor [002]: Siegel gebrochen" in out and "START [002]" not in out
