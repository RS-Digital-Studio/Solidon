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


def test_the_font_sets_run_in_every_language() -> None:
    """RC2-4: FD-57 war spanisch, FD-58 spanisch, französisch, italienisch, portugiesisch rot.

    Ein deutscher Fall stellt die Lage nicht her; je Sprache ein Fall, je Schrift.
    """
    from app.i18n.catalog import available_languages
    from tests.bench_fakes import ROWS
    from tools.file_acceptance import function_cases

    spoken = available_languages()
    assert len(spoken) == 6
    change = function_cases(ROWS, row_ids=["resize_hole"], variant_sets=["schriftwechsel"])
    assert [case.variant["language"] for case in change] == list(spoken)
    assert {tuple(case.variant["font_change"]) for case in change} == {(9.0, 14.0, 9.0)}
    fonts = function_cases(ROWS, row_ids=["resize_hole"], variant_sets=["schrift"])
    assert sorted((case.variant["font"], case.variant["language"]) for case in fonts) == sorted(
        (points, code) for points in (14.0, 18.0) for code in spoken
    )
    assert all("language=" in case.relative for case in (*change, *fonts))
    # Eine Einschränkung der Sprachen gilt auch hier; eine fremde Sprache gibt es nicht.
    only = function_cases(
        ROWS, row_ids=["resize_hole"], variant_sets=["schriftwechsel"], languages=("es",)
    )
    assert [case.variant["language"] for case in only] == ["es"]
    with pytest.raises(ValueError, match="Sprache"):
        function_setup.Variant.of({"set": "schrift", "font": 14.0, "language": "xx"})


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
    from tools.function_capture import FrameCounter

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
    flow.frames = FrameCounter()
    flow.reference_factor = 1.0
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


def test_a_drag_approaches_its_grip_before_it_presses(qt_app: Any) -> None:
    """Schlusslauf 2: Die Ansicht schärft den Griff erst beim Überfahren.

    Der Zug drückte ohne Hinfahren; am echten Fenster fasste er den Körper statt
    des Langlochknopfs, und das Bild im Zug zeigte den verschobenen Körper.
    Attrappe: Der Griff wird 50 ms nach einer Bewegung ohne Taste scharf; ein
    Druck vorher fasst den Körper.
    """
    from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal

    class View(QObject):
        slotDragged = Signal(float)  # noqa: N815 - Name der Ansicht

    flow, _events = _drag_flow(qt_app, "basis", {"drag": "handle:slot.end"})
    view = View()
    flow.window = SimpleNamespace(viewport=view)
    state = {"sharp": False, "grabbed": ""}

    class Grip(QObject):
        def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qts Name
            kind = event.type()
            held = kind == QEvent.Type.MouseMove and bool(
                event.buttons() & Qt.MouseButton.LeftButton
            )
            if kind == QEvent.Type.MouseMove and not held:
                QTimer.singleShot(50, lambda: state.update(sharp=True))
            elif kind == QEvent.Type.MouseButtonPress:
                state["grabbed"] = "griff" if state["sharp"] else "körper"
            elif kind == QEvent.Type.MouseMove and state["grabbed"] == "griff":
                view.slotDragged.emit(1.0)
            return False

    grip = flow._keep[0]
    grip.setMouseTracking(True)  # wie die Ansicht: sie hört auch Bewegungen ohne Taste
    hover = Grip(grip)
    grip.installEventFilter(hover)
    try:
        flow.phase_drag()
    finally:
        grip.close()
    assert state["grabbed"] == "griff", state


def test_the_held_picture_does_not_fall_into_the_frame_time_of_the_drag(qt_app: Any) -> None:
    """RC2-2: Z1 misst je Bewegung die Zeit bis zum nächsten Bild — nicht die Aufnahme.

    Die Ansicht malt 40 ms nach der jeweils letzten Bewegung, länger als der Takt
    des Zugs (16,7 ms); die Aufnahme hält den Hauptfaden 120 ms an. Vorher nahm
    der Zug das Bild vor dem Bild der letzten Bewegung auf, und deren Zeit trug
    die Aufnahme (über 120 ms, Z1 „fund“). Jetzt wartet er auf dieses Bild.
    """
    import time

    from PySide6.QtCore import QEvent, QObject, QTimer, Signal

    class View(QObject):
        slotDragged = Signal(float)  # noqa: N815 - Name der Ansicht

    flow, events = _drag_flow(qt_app, "basis", {"drag": "handle:slot.end"})
    view = View()
    flow.window = SimpleNamespace(viewport=view)
    renderer = SimpleNamespace(render=lambda: None)
    assert flow.frames.wrap(renderer)
    picture_s = 0.12
    moved: list[float] = []

    painting = QTimer()
    painting.setSingleShot(True)
    painting.setInterval(40)
    painting.timeout.connect(renderer.render)

    class Renderer(QObject):
        def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qts Name
            if event.type() == QEvent.Type.MouseMove:
                moved.append(time.perf_counter())
                view.slotDragged.emit(1.0)
                painting.start()
            return False

    grip = flow._keep[0]
    painter = Renderer(grip)
    grip.installEventFilter(painter)
    taken: list[float] = []

    def picture(label: str) -> None:
        taken.append(time.perf_counter())
        time.sleep(picture_s)  # grabWindow und PNG eines großen Fensters, Hauptfaden
        events.append(label)

    flow.picture = picture
    flow.phase_drag()
    raw = flow.data["frames"]["raw_drag_ms"]
    assert len(raw) == len(moved) and taken, (raw, taken)
    frame = flow.frames.first_after(moved[-1])
    assert frame is not None and frame <= taken[0], "aufgenommen vor dem Bild der letzten Bewegung"
    assert raw[-1] is not None and raw[-1] < picture_s * 1000.0, raw


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


class _StopError(Exception):
    """Hält den nachgestellten Hauptweg nach seinem Lauf an — das Danach misst hier nichts."""


def _grey(qt_app: Any, text: str = "Übernehmen") -> Any:
    from PySide6.QtWidgets import QPushButton

    button = QPushButton(text)
    button.setToolTip("Erst „Durchmesser“ ändern, dann übernehmen.")
    button.setEnabled(False)
    button.show()
    qt_app.processEvents()
    return button


def _main_flow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    row: dict[str, Any],
    widgets: dict[str, Any],
    *,
    opened: dict[str, Any] | None = None,
) -> Any:
    """``phase_main`` mit nachgestelltem Fluss: echte Schrittfolge, Schritte ohne Fenster.

    Jeder Schritt läuft der Reihe nach; ``fläche aufnehmen`` ist der echte, mit
    nachgestellter Erfassung. ``opened`` erscheint unter ``widgets``, sobald der
    Klick auf das Ziel lief (Änderungsweg). Nach dem Lauf hält :class:`_StopError` an.
    """
    from tools import function_bench, function_capture, function_surface
    from tools.function_machine import Step
    from tools.function_protocol import empty_protocol
    from tools.function_setup import default_apply_target

    folder = tmp_path / "cases" / "001"
    folder.mkdir(parents=True, exist_ok=True)
    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = row
    flow.spec = row.get("spec") or {}
    flow.data = empty_protocol(row, {}, {})
    flow.folder, flow.out = folder, tmp_path
    flow.window = object()
    flow.walker = SimpleNamespace(before_target=None)
    flow.variant = SimpleNamespace(predict=False, set="basis")
    flow.apply_target = default_apply_target(row)
    flow.widget = widgets.get
    flow.snapshot = lambda name: None
    flow.picture = lambda label: flow.data["images"].append(f"cases/001/{label}.png")
    flow.surface = lambda: "fläche"
    flow.claim_surface = flow.capture_surface = lambda root: None
    flow.spot = dict
    flow.expects_preview = lambda: False
    flow.idle = lambda: True
    flow.wait_step = flow.still_step = lambda name, check: Step(name, lambda machine: None)
    flow.preview_steps = list
    flow.ports = SimpleNamespace(keys=lambda sequence: None)

    def click(machine: Any) -> None:
        widgets.update(opened or {})

    flow.path_steps = lambda: [Step(f"weg zu {row['target']}", click)]
    flow.input_steps = lambda inputs: [Step(f"eingabe {name}", lambda m: None) for name in inputs]
    flow.apply_step = lambda: Step("übernehmen", lambda machine: None)
    flow.apply_steps = lambda acting: ([acting] if acting else [], lambda: None)
    names: list[str] = []

    def run_steps(label: str, steps: list[Any], timeout_s: float | None = None) -> bool:
        for step in steps:
            names.append(step.name)
            step.act(SimpleNamespace(insert=lambda more: None))
        raise _StopError

    flow.run_steps = run_steps
    flow.names = names
    monkeypatch.setattr(function_surface, "open_dialog", lambda window: None)
    monkeypatch.setattr(function_capture, "message_entries", lambda window: [])
    monkeypatch.setattr(function_capture, "tab_chain", lambda root, press, on_focus: [])
    monkeypatch.setattr(function_capture, "state_images", lambda widget, focus=None: {})
    bar = [{"name": "Prüfbericht", "rect": [0, 0, 1, 1], "inside": False, "class": "QTabBar"}]
    monkeypatch.setattr(function_capture, "bar_chain", lambda root, press: list(bar))
    return flow


def _drive(flow: Any) -> Any:
    with pytest.raises(_StopError):
        flow.phase_main()
    return flow


def test_the_reason_of_a_grey_apply_is_pictured_on_the_main_path(
    qt_app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FD-99: Der Grund stand nur im Protokoll; das Bild entstand nur im Fehlfall.

    Am nachgestellten Hauptweg (RC2-5): Der Schritt steht vor den Eingaben und
    nimmt die Kurzhilfe auf, auch an einer Zeile ohne Eingaben (RC2-3,
    ``resize_feature``); ein offener Knopf hat kein Grundbild.
    """
    from tools import function_tooltips

    apply = _grey(qt_app)
    try:
        for inputs, row_id in (
            ({"feature.field:resize_hole.diameter": 8.0}, "resize_hole"),
            ({}, "resize_feature"),
        ):
            row = {
                "id": row_id,
                "target": f"feature:{row_id}",
                "kind": "operation",
                "spec": {"inputs": inputs},
            }
            flow = _drive(_main_flow(monkeypatch, tmp_path / row_id, row, {"feature.apply": apply}))
            step = flow.names.index("grund am grauen übernehmen")
            assert all(step < flow.names.index(f"eingabe {name}") for name in inputs), flow.names
            assert "cases/001/02-uebernehmen-grund-1.png" in flow.data["images"], flow.data
            assert flow.data["grey_apply"] == [
                {
                    "where": function_tooltips.GREY_APPLY_PICTURE,
                    "target": "feature.apply",
                    "grey": True,
                    "image": "cases/001/02-uebernehmen-grund-1.png",
                }
            ]
        apply.setEnabled(True)
        row = {"id": "resize_hole", "target": "feature:resize_hole", "kind": "operation"}
        flow = _drive(_main_flow(monkeypatch, tmp_path / "frei", row, {"feature.apply": apply}))
        assert flow.data["grey_apply"][0]["grey"] is False
        assert not [image for image in flow.data["images"] if "grund" in image]
    finally:
        apply.close()


def test_the_reason_of_a_grey_apply_is_pictured_where_the_click_opens_the_surface(
    qt_app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RC2-3: Im Änderungsweg öffnet erst der Klick die Fläche — dort, danach, das Bild.

    ``finding.action:change_creating_step`` hat kein Ziel des Übernehmens und
    keine Eingaben; das Formular des erzeugenden Schritts steht mit grauem
    Hauptknopf da. Vorher entstand an dieser Zeile kein Bild, und das Protokoll
    schwieg darüber.
    """
    from tools import function_tooltips

    accept = _grey(qt_app)
    row = {
        "id": "finding.action:change_creating_step",
        "target": "finding.action:change_creating_step",
        "kind": "bedienflaeche",
    }
    try:
        flow = _drive(_main_flow(monkeypatch, tmp_path, row, {}, opened={"dialog.accept": accept}))
    finally:
        accept.close()
    assert flow.names.index("grund am grauen übernehmen") > flow.names.index(
        "weg zu finding.action:change_creating_step"
    ), flow.names
    picture = f"cases/001/{function_tooltips.OPENED_APPLY_PICTURE}-1.png"
    assert picture in flow.data["images"], flow.data["images"]
    assert flow.data["grey_apply"][0]["target"] == "dialog.accept"
    # Steht kein Hauptknopf da, sagt es das Protokoll.
    empty = _drive(_main_flow(monkeypatch, tmp_path / "leer", row, {}))
    assert empty.data["grey_apply"] == [
        {
            "where": function_tooltips.OPENED_APPLY_PICTURE,
            "target": None,
            "reason": function_tooltips.NO_APPLY_TARGET,
        }
    ]


def test_a_tooltip_that_fades_in_is_pictured_after_its_animation(
    qt_app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Schlusslauf: Unter Windows blendet Qt die Kurzhilfe ein (``UI_AnimateTooltip``).

    Sichtbar wird sie erst nach der Animation. Gefragt wurde nach einem einzigen
    Ereignisdurchlauf, und jeder graue Hauptknopf hieß „Kurzhilfe gesetzt, aber
    nicht gezeigt“. Nachgestellt: Die Kurzhilfe erscheint 200 ms nach dem Aufruf.
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QToolTip

    from tools import function_tooltips

    real = QToolTip.showText
    shown: list[bool] = []

    def animated(point: Any, text: str, widget: Any = None, *rest: Any) -> None:
        QTimer.singleShot(200, lambda: (real(point, text, widget), shown.append(True)))

    monkeypatch.setattr(QToolTip, "showText", animated)
    button = _grey(qt_app)
    try:
        assert function_tooltips.reason_picture(button, tmp_path / "grund.png"), shown
    finally:
        button.close()
    assert shown and (tmp_path / "grund.png").is_file()


def _tips() -> list[Any]:
    from PySide6.QtWidgets import QApplication

    return [w for w in QApplication.topLevelWidgets() if w.inherits("QTipLabel")]


def test_the_pointer_goes_over_the_grey_button_before_its_tooltip(
    qt_app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Schlusslauf 2: Qt blendet eine Kurzhilfe mit Widget aus, steht der Zeiger außerhalb.

    Am echten Fenster stand er noch am letzten Klickort, und der graue
    *Übernehmen* oben in der Karte hieß „Kurzhilfe gesetzt, aber nicht gezeigt“.
    Attrappe: Die Kurzhilfe geht sofort wieder aus, solange der Zeiger den Knopf
    nicht betreten hat.
    """
    from PySide6.QtCore import QEvent, QObject, QTimer
    from PySide6.QtWidgets import QToolTip

    from tools import function_tooltips

    button = _grey(qt_app)
    inside = {"value": False}

    class Pointer(QObject):
        def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qts Name
            if event.type() == QEvent.Type.Enter:
                inside["value"] = True
            elif event.type() == QEvent.Type.Leave:
                inside["value"] = False
            return False

    pointer = Pointer(button)
    button.installEventFilter(pointer)
    real = QToolTip.showText

    def strict(point: Any, text: str, widget: Any = None, *rest: Any) -> None:
        real(point, text, widget)
        if not inside["value"]:
            # Sofort aus, wie Qt, sobald es den Zeiger außerhalb sieht.
            QTimer.singleShot(0, lambda: [tip.hide() for tip in _tips()])

    monkeypatch.setattr(QToolTip, "showText", strict)
    try:
        assert function_tooltips.reason_picture(button, tmp_path / "grund.png")
    finally:
        button.close()
    assert inside["value"] and (tmp_path / "grund.png").is_file()


def test_grey_without_a_tooltip_is_named_in_the_protocol(qt_app: Any, tmp_path: Path) -> None:
    """Grau ohne Kurzhilfe: kein Bild, aber ``unmeasured`` sagt warum (RC2-3)."""
    from tools import function_tooltips

    silent = _grey(qt_app)
    silent.setToolTip("")
    folder = tmp_path / "cases" / "001"
    folder.mkdir(parents=True)
    flow = SimpleNamespace(
        widget={"dialog.accept": silent}.get,
        folder=folder,
        out=tmp_path,
        data={"images": [], "unmeasured": {}, "grey_apply": None},
        apply_target=None,
    )
    try:
        function_tooltips.grey_apply_step(flow, function_tooltips.main_buttons(None)).act(None)
    finally:
        silent.close()
    assert flow.data["images"] == []
    assert flow.data["unmeasured"] == {
        "sperrgrund:dialog.accept": function_tooltips.NO_VISIBLE_REASON
    }
    assert flow.data["grey_apply"][0]["grey"] is True


def test_the_language_case_pictures_the_reason_of_its_surface(
    qt_app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RC2-3: Im Sprachfall entsteht das Bild an jeder aufgenommenen Fläche, je Sprache."""
    from tools import function_surface

    apply = _grey(qt_app)
    row = {"id": "resize_hole", "target": "feature:resize_hole", "kind": "operation"}
    flow = _main_flow(monkeypatch, tmp_path, row, {"feature.apply": apply})
    flow.variant = SimpleNamespace(predict=False, set="sprachen", language="es")
    flow.path_steps = list
    monkeypatch.setattr(function_surface, "acts_at_once", lambda window, target: False)
    try:
        with pytest.raises(_StopError):
            flow.phase_surface()
    finally:
        apply.close()
    from tools.function_tooltips import GREY_APPLY_PICTURE

    label = function_surface.picture_label(flow.variant, "resize_hole", GREY_APPLY_PICTURE)
    assert label.startswith(f"{GREY_APPLY_PICTURE}-es-")
    assert f"cases/001/{label}-1.png" in flow.data["images"], flow.data["images"]


def test_the_keyboard_way_starts_at_the_tab_bar(qt_app: Any) -> None:
    """FD-177: Von der Reiterleiste führt Tab auf die vordere Seite — gemessen wird es jetzt.

    Die Kette des Hauptwegs beginnt am ersten Feld der Fläche; den Weg von der
    Leiste ging sie nie.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLineEdit, QTabWidget, QVBoxLayout, QWidget

    from tools import function_capture

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


def test_the_main_path_writes_the_keyboard_way_from_the_tab_bar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RC2-5: Die Fläche des Hauptwegs schreibt ``tab_from_bar`` — die Anwendung tut es.

    Vorher prüfte der Test nur, dass ``bar_chain`` im Quelltext steht; ein Weg,
    der die Kette nie ging, blieb grün.
    """
    row = {"id": "resize_hole", "target": "feature:resize_hole", "kind": "operation"}
    flow = _drive(_main_flow(monkeypatch, tmp_path, row, {}))
    assert flow.data["tab_from_bar"] == [
        {"name": "Prüfbericht", "rect": [0, 0, 1, 1], "inside": False, "class": "QTabBar"}
    ]


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


_WAY_TEXT = (
    "0,10 mm liegt unter der Grenze. "
    "Zum Entfernen zuerst „Abbrechen“ wählen, danach „Merkmal entfernen“."
)


def _way_surface(qt_app: Any, enable_second: bool, clicked: list[str], label: str) -> Any:
    """Die Fläche der Meldung: *Abbrechen* und das graue *Merkmal entfernen* daneben."""
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    window = QWidget()
    cancel = QPushButton("Abbrechen", window)
    remove = QPushButton("Merkmal entfernen", window)
    remove.setEnabled(False)

    def cancelled() -> None:
        clicked.append(f"{label}: Abbrechen")
        cancel.hide()
        remove.setEnabled(enable_second)

    cancel.clicked.connect(cancelled)
    remove.clicked.connect(lambda: (clicked.append(f"{label}: Merkmal entfernen"), remove.hide()))
    layout = QVBoxLayout(window)
    layout.addWidget(cancel)
    layout.addWidget(remove)
    window._op_dialog = None  # wie am Hauptfenster: kein Operationsdialog offen
    window.resize(300, 120)
    window.show()
    qt_app.processEvents()
    return window


def _way_flow(qt_app: Any, window: Any) -> Any:
    """Ein Fehlfall mit dem echten Automaten (``run_steps``) und seiner Frist."""
    import time

    from tools import function_bench
    from tools.function_walk import QtPorts, Walk

    flow = object.__new__(function_bench.FunctionFlow)
    flow.window = window
    flow.ports = QtPorts(window, time.perf_counter())
    flow.walker = Walk(flow.ports, [], time.perf_counter())
    flow.scene_now = dict
    flow.pump = qt_app.processEvents
    flow.variant = function_setup.Variant.of({"set": "basis"})
    flow.data = {"findings": [], "errors": [], "closed_by_escape": [], "steps": []}
    flow.persist = lambda: None
    return flow


def test_a_way_step_that_stays_grey_is_a_measurement(
    qt_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RC2-6: Bleibt *Merkmal entfernen* grau — die Lage von FD-36 —, sagt es der Weg.

    Vorher lief der Schritt in die Frist des Automaten, und der Fall stand unter
    „Fehler“ des Prüfstands statt mit einer Messung.
    """
    from tools import function_way

    monkeypatch.setattr(function_way, "WAY_STEP_S", 0.3)
    clicked: list[str] = []
    window = _way_surface(qt_app, False, clicked, "Fläche")
    flow = _way_flow(qt_app, window)
    messages = [{"text": _WAY_TEXT, "actions": [], "kind": "grenzablehnung", "way_out": True}]
    try:
        flow.walk_ways(messages)
    finally:
        window.close()
    assert messages[0]["way"] == [
        {"title": "Abbrechen", "clicked": True, "effect": True},
        {
            "title": "Merkmal entfernen",
            "clicked": False,
            "effect": None,
            "reason": f"nach 0.3 s {function_way.STILL_GREY}",
        },
    ]
    assert flow.data["errors"] == [] and clicked == ["Fläche: Abbrechen"]


def test_the_way_takes_the_button_of_the_message_window_and_does_not_guess(
    qt_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RC2-6: Ein fremdes *Abbrechen* in einem anderen Fenster wird nicht geklickt.

    Vorher nahm der Weg den ersten Treffer über alle Fenster, je nach deren
    Reihenfolge das fremde. Zwei gleiche Knöpfe im selben Fenster: nicht raten.
    """
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from tools import function_way

    monkeypatch.setattr(function_way, "WAY_STEP_S", 0.3)
    for foreign_first in (True, False):
        clicked: list[str] = []
        shown: list[Any] = []

        def foreign(clicked: list[str] = clicked, shown: list[Any] = shown) -> None:
            other = QWidget()
            button = QPushButton("Abbrechen", other)
            button.clicked.connect(lambda: clicked.append("fremd: Abbrechen"))
            QVBoxLayout(other).addWidget(button)
            other.show()
            shown.append(other)

        if foreign_first:
            foreign()
        window = _way_surface(qt_app, True, clicked, "Fläche")
        if not foreign_first:
            foreign()
        qt_app.processEvents()
        flow = _way_flow(qt_app, window)
        messages = [{"text": _WAY_TEXT, "actions": [], "kind": "grenzablehnung", "way_out": True}]
        try:
            flow.walk_ways(messages)
        finally:
            for each in (window, *shown):
                each.close()
            qt_app.processEvents()
        assert clicked == ["Fläche: Abbrechen", "Fläche: Merkmal entfernen"], clicked
        assert [entry["effect"] for entry in messages[0]["way"]] == [True, True]
    # Zwei *Abbrechen* in der Fläche der Meldung: welcher gemeint ist, sagt sie nicht.
    clicked = []
    window = _way_surface(qt_app, True, clicked, "Fläche")
    twin = QPushButton("Abbrechen", window)
    window.layout().addWidget(twin)
    twin.show()
    qt_app.processEvents()
    flow = _way_flow(qt_app, window)
    messages = [{"text": _WAY_TEXT, "actions": [], "kind": "grenzablehnung", "way_out": True}]
    try:
        flow.walk_ways(messages)
    finally:
        window.close()
    first, second = messages[0]["way"]
    assert first["clicked"] is False and first["reason"].startswith(function_way.AMBIGUOUS)
    assert second["reason"] == function_way.AFTER_MISSED and clicked == []
    assert flow.data["errors"] == []


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


def test_the_run_asks_the_seal_after_its_last_case_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """RC2-7: Bricht das Siegel im letzten oder einzigen Fall, endet ``run`` nicht mit 0."""
    import subprocess

    from tools import acceptance_guard
    from tools import file_acceptance as acceptance

    class Process:
        pid = 4711

        def __init__(self, *args: Any, **named: Any) -> None:
            pass

        def wait(self, timeout: float | None = None) -> int:
            return 0

    monkeypatch.setattr(acceptance, "read_cases", lambda out: [acceptance.Case(1, "eins", "", "")])
    monkeypatch.setattr(acceptance, "summary", lambda *args: {})
    monkeypatch.setattr(
        acceptance,
        "subprocess",
        SimpleNamespace(Popen=Process, TimeoutExpired=subprocess.TimeoutExpired),
    )
    answers = iter(["", "Siegel gebrochen: tools/x.py weicht ab"])

    def seal() -> str:
        return next(answers)

    guard = SimpleNamespace(stop_reason=seal, seal_reason=seal, case_limit=lambda wanted: wanted)
    assert acceptance.run(tmp_path, 1, 9, False, 10.0, "", guard) == 1
    out = capsys.readouterr().out
    assert "HALT nach [001]: Fall 001 lief unter geändertem Stand" in out
    with pytest.raises(ValueError, match="Handlungsvorschlag"):
        acceptance_guard.RunGuard(total_s=0.0)
