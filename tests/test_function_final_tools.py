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
