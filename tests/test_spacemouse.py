"""Die 3D-Maus — ohne Gerät prüfbar (Konzept 3D-Maus, Abschnitt 8 und Abnahme 11).

Die Abbildung ist eine reine Funktion, also gewöhnliche Tests: je Achse
einer, der sagt, was sie bewegt (Abnahme 4), dazu Determinismus (Abnahme 3)
und die Zusage, dass fünfhundert Berichte keinen Verlaufsschritt erzeugen
(Abnahme 8). Die Vorzeichen des Geräts prüft eine **aufgezeichnete Lesung**
aus ``tests/data/spacemouse/`` — geführt am echten Compact, je Geste eine
Phase —, damit Achsen und Vorzeichen für immer ohne Gerät prüfbar sind. Der
Leser bekommt seine Berichte hier direkt — die Naht ist
:meth:`SpaceMouseController.handle_report`, keine HID-Attrappe.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.spacemouse import (
    AXIS_RANGE,
    DEADZONE,
    CameraPose,
    Motion,
    SpaceMouseController,
    camera_step,
    decode_report,
    speed_factor,
)

START = CameraPose(
    position=(0.0, -100.0, 50.0), focal_point=(0.0, 0.0, 0.0), view_up=(0.0, 0.0, 1.0)
)
DT = 1.0 / 60.0
CORPUS = Path(__file__).parent / "data" / "spacemouse" / "compact-2026-09-02.jsonl"


def report(report_id: int, *values: int) -> bytes:
    """Ein HID-Bericht, wie das Gerät ihn liefert: Kennung, dann int16 klein-endian."""
    return bytes([report_id]) + struct.pack("<" + "h" * len(values), *values)


def distance(pose: CameraPose) -> float:
    return math.dist(pose.position, pose.focal_point)


def forward(pose: CameraPose) -> tuple[float, float, float]:
    dx, dy, dz = (f - p for f, p in zip(pose.focal_point, pose.position, strict=True))
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    return (dx / length, dy / length, dz / length)


def right(pose: CameraPose) -> tuple[float, float, float]:
    fx, fy, fz = forward(pose)
    ux, uy, uz = pose.view_up
    rx, ry, rz = (fy * uz - fz * uy, fz * ux - fx * uz, fx * uy - fy * ux)
    length = math.sqrt(rx * rx + ry * ry + rz * rz)
    return (rx / length, ry / length, rz / length)


def square_up(pose: CameraPose) -> tuple[float, float, float]:
    """Das senkrechte „Oben" der Stellung — VTK richtet den Wert selbst so aus."""
    rx, ry, rz = right(pose)
    fx, fy, fz = forward(pose)
    return (ry * fz - rz * fy, rz * fx - rx * fz, rx * fy - ry * fx)


# --- Lesen -------------------------------------------------------------------


def test_translation_and_rotation_reports_complement_each_other() -> None:
    """Schub und Drehung kommen getrennt; der eine Bericht löscht den anderen nicht."""
    motion = decode_report(report(1, 350, 0, 175), Motion())
    assert (motion.x, motion.y, motion.z) == (1.0, 0.0, -0.5)
    motion = decode_report(report(2, 0, -70, 0), motion)
    assert motion.x == 1.0, "der Schub bleibt, wenn die Drehung gemeldet wird"
    assert motion.ry == pytest.approx(0.2)


def test_a_combined_twelve_byte_report_sets_all_six_axes() -> None:
    motion = decode_report(report(1, 35, 35, -70, 70, 105, -105), Motion())
    assert motion == Motion(x=0.1, y=-0.1, z=0.2, rx=-0.2, ry=-0.3, rz=0.3)


def test_buttons_are_a_bitmask_and_unknown_reports_change_nothing() -> None:
    motion = decode_report(bytes([3, 0b101, 0]), Motion(x=0.5))
    assert motion.buttons == 0b101
    assert motion.x == 0.5
    assert decode_report(bytes([9, 1, 2, 3]), motion) == motion
    assert decode_report(b"", motion) == motion
    assert decode_report(bytes([1, 1, 2]), motion) == motion, (
        "ein verstümmelter Bericht ändert nichts"
    )


def test_values_beyond_full_deflection_are_clipped() -> None:
    motion = decode_report(report(1, 32767, 32767, -int(AXIS_RANGE)), Motion())
    assert (motion.x, motion.y, motion.z) == (1.0, -1.0, 1.0)


def test_rest_is_rest() -> None:
    """Das Rauschen einer losgelassenen Kappe ist keine Bewegung."""
    assert not Motion(x=DEADZONE / 2, rz=-DEADZONE / 2).active()
    assert Motion(ry=DEADZONE).active()
    assert camera_step(START, Motion(x=DEADZONE / 2), DT) == START


def _corpus_phases() -> dict[str, list[Motion]]:
    lines = CORPUS.read_text(encoding="utf-8").splitlines()
    head = json.loads(lines[0])
    assert head["reports_total"] > 1000, head
    phases: dict[str, list[Motion]] = {}
    motion = Motion()
    for line in lines[1:]:
        entry = json.loads(line)
        motion = decode_report(bytes.fromhex(entry["hex"]), motion)
        phases.setdefault(entry["phase"], []).append(motion)
    assert len(phases) >= 11, sorted(phases)
    return phases


def _mean(motions: list[Motion], axis: str) -> float:
    return sum(getattr(m, axis) for m in motions) / len(motions)


@pytest.mark.parametrize(
    ("phase", "axis", "sign"),
    [
        ("1", "x", +1),  # nach rechts schieben
        ("2", "x", -1),  # nach links schieben
        ("3", "z", +1),  # hochziehen
        ("4", "z", -1),  # nach unten drücken
        ("5", "y", -1),  # zu sich ziehen
        ("6", "y", +1),  # von sich wegschieben
        ("7", "rz", -1),  # im Uhrzeigersinn drehen, von oben gesehen
        ("9", "ry", +1),  # nach rechts kippen, rechte Kante runter
    ],
)
def test_the_recording_moves_the_axis_its_gesture_names(phase: str, axis: str, sign: int) -> None:
    """Abnahme 4 am echten Gerät: Jede Geste der Aufzeichnung landet auf ihrer Achse.

    Gemessen wird der Mittelwert der Phase — die Kappe spricht beim Schieben
    immer ein wenig über (wer nach rechts schiebt, drückt auch etwas nach
    unten), und der Mittelwert nennt die Achse, die gemeint war. Ein
    umgedrehtes Vorzeichen in ``decode_report`` macht genau die Fälle dieser
    Achse rot.
    """
    motions = _corpus_phases()[phase]
    means = {name: _mean(motions, name) for name in ("x", "y", "z", "rx", "ry", "rz")}
    strongest = max(means, key=lambda name: abs(means[name]))
    assert strongest == axis, means
    assert math.copysign(1.0, means[axis]) == sign, means
    assert abs(means[axis]) > 0.25, means


def test_tilting_the_front_edge_down_is_a_positive_rx() -> None:
    """Die Kippgeste am Compact spricht stark auf den Schub über; das Vorzeichen bleibt.

    Beide Aufzeichnungen des Tages zeigen es gleich: Vorderkante runter ist
    ein negativer Rohwert, also ein positives ``rx`` nach der Rechte-Hand-Regel
    um die Bildwaagerechte.
    """
    motions = _corpus_phases()["8"]
    assert _mean(motions, "rx") > DEADZONE


def test_the_recording_names_both_buttons() -> None:
    phases = _corpus_phases()
    assert any(m.buttons == 1 for m in phases["10"]), "linke Taste ist Bit 0"
    assert any(m.buttons == 2 for m in phases["11"]), "rechte Taste ist Bit 1"
    assert all(m.buttons in (0, 1) for m in phases["10"])


# --- Abbilden: je Achse ein Test ----------------------------------------------


def test_push_right_moves_the_part_right() -> None:
    """Objektmodus: Die Kappe ist das Teil — es wandert nach rechts, die Kamera fährt nach links."""
    after = camera_step(START, Motion(x=1.0), DT)
    assert after.position[0] < 0.0
    assert after.focal_point[0] == pytest.approx(after.position[0]), (
        "Standort und Blickpunkt wandern gemeinsam"
    )
    assert after.position[1:] == pytest.approx(START.position[1:])
    assert distance(after) == pytest.approx(distance(START))
    assert forward(after) == pytest.approx(forward(START))


def test_pull_up_lifts_the_part() -> None:
    """Kappe hochziehen: das Teil steigt im Bild, die Kamera senkt sich entlang ihres Oben."""
    after = camera_step(START, Motion(z=1.0), DT)
    assert after.position[2] < START.position[2]
    assert after.focal_point[2] < 0.0
    assert after.focal_point[0] == pytest.approx(0.0)
    assert distance(after) == pytest.approx(distance(START))


def test_pull_toward_you_brings_the_part_closer() -> None:
    """y ist die Achse vom Nutzer weg: zu sich ziehen ist negativ und holt das Teil näher."""
    closer = camera_step(START, Motion(y=-1.0), DT)
    farther = camera_step(START, Motion(y=1.0), DT)
    assert distance(closer) < distance(START) < distance(farther)
    assert closer.focal_point == START.focal_point
    assert forward(closer) == pytest.approx(forward(START))


def test_zoom_never_passes_through_the_focal_point() -> None:
    pose = START
    for _ in range(3000):
        pose = camera_step(pose, Motion(y=-1.0), DT)
    assert distance(pose) >= 0.5
    assert forward(pose) == pytest.approx(forward(START))


def test_twist_turns_the_part_around_the_screen_vertical() -> None:
    """Drehen: der Standort wandert um die Bildsenkrechte, Abstand und Oben bleiben."""
    after = camera_step(START, Motion(rz=1.0), DT)
    assert distance(after) == pytest.approx(distance(START))
    assert after.focal_point == START.focal_point
    assert after.position[0] != pytest.approx(0.0), "es hat sich gedreht"
    assert after.view_up == pytest.approx(square_up(START)), "die Drehachse selbst steht"
    # Gegen den Uhrzeigersinn an der Kappe (rz positiv) heißt: das Teil dreht
    # gegen den Uhrzeigersinn, also fährt die Kamera im Uhrzeigersinn um das
    # Oben — von oben gesehen nach links, wenn sie vorn steht.
    assert after.position[0] < 0.0


def test_tilt_changes_the_elevation_and_keeps_the_distance() -> None:
    """Vorderkante runter (rx positiv): das Teil kippt zum Betrachter, die Kamera steigt."""
    after = camera_step(START, Motion(rx=1.0), DT)
    assert after.position[2] > START.position[2]
    assert after.position[0] == pytest.approx(0.0)
    assert distance(after) == pytest.approx(distance(START))
    assert after.focal_point == START.focal_point
    assert right(after) == pytest.approx(right(START)), "die Kippachse selbst steht"


def test_roll_turns_the_picture_around_the_line_of_sight() -> None:
    """Rechte Kante runter (ry positiv): das Teil rollt nach rechts, die Kamera rollt gegen.

    Robert, 02.09.2026: „wir wollen alle 6 Achsen nutzen" — die Rollachse ist
    seitdem die sechste und keine stille mehr.
    """
    after = camera_step(START, Motion(ry=1.0), DT)
    assert after.position == START.position
    assert after.focal_point == START.focal_point
    assert forward(after) == pytest.approx(forward(START)), "die Rollachse selbst steht"
    assert after.view_up != pytest.approx(square_up(START))
    # Gegenrollen der Kamera: ihr Oben kippt nach links, damit das Bild nach
    # rechts rollt.
    assert after.view_up[0] < 0.0


def test_continuous_tilting_keeps_the_frame_orthonormal() -> None:
    """Sechs freie Achsen kennen keinen Pol: über den Scheitel kippen bleibt sauber."""
    pose = START
    for _ in range(600):
        pose = camera_step(pose, Motion(rx=1.0, ry=0.3, rz=-0.4), DT)
        assert math.dist(pose.view_up, (0.0, 0.0, 0.0)) == pytest.approx(1.0)
        assert abs(sum(a * b for a, b in zip(forward(pose), pose.view_up, strict=True))) < 1e-6
        assert distance(pose) == pytest.approx(distance(START))


def test_orbit_off_keeps_the_direction_but_still_pans_and_zooms() -> None:
    """Im Zeichenmodus bleibt der Blick auf der Zeichenebene; schieben und zoomen geht."""
    turned = camera_step(START, Motion(rx=1.0, ry=1.0, rz=1.0), DT, orbit=False)
    assert turned == START
    moved = camera_step(START, Motion(x=1.0, y=-1.0), DT, orbit=False)
    assert forward(moved) == pytest.approx(forward(START))
    assert moved.position[0] < 0.0
    assert distance(moved) < distance(START)


def test_invert_turns_the_object_mode_into_the_camera_mode() -> None:
    """„Richtung umkehren" ist auf jeder Achse dasselbe wie die Kappe andersherum zu bewegen."""
    for axis in ("x", "y", "z", "rx", "ry", "rz"):
        inverted = camera_step(START, Motion(**{axis: 0.7}), DT, invert=True)
        mirrored = camera_step(START, Motion(**{axis: -0.7}), DT)
        assert inverted.position == pytest.approx(mirrored.position), axis
        assert inverted.focal_point == pytest.approx(mirrored.focal_point), axis
        assert inverted.view_up == pytest.approx(mirrored.view_up), axis
        assert inverted != camera_step(START, Motion(**{axis: 0.7}), DT), axis


def test_speed_scales_the_step_and_five_is_neutral() -> None:
    assert speed_factor(5) == 1.0
    assert speed_factor(10) == 2.0
    assert speed_factor(0) == speed_factor(1) and speed_factor(99) == speed_factor(10)
    slow = camera_step(START, Motion(x=1.0), DT, speed=speed_factor(1))
    fast = camera_step(START, Motion(x=1.0), DT, speed=speed_factor(10))
    assert abs(fast.position[0]) > abs(slow.position[0]) > 0.0


def test_the_response_is_finer_near_the_middle() -> None:
    """Halber Ausschlag bewegt weniger als die Hälfte des Vollen — die Hand bekommt Platz."""
    half = camera_step(START, Motion(x=0.5), DT)
    full = camera_step(START, Motion(x=1.0), DT)
    assert 0.0 < abs(half.position[0]) < 0.5 * abs(full.position[0])


def test_no_time_or_no_motion_returns_the_same_pose() -> None:
    assert camera_step(START, Motion(x=1.0), 0.0) == START
    assert camera_step(START, Motion(), DT) == START


def test_the_same_recording_gives_the_same_camera_twice() -> None:
    """Abnahme 3: zwei Läufe derselben Lesung ergeben dieselbe Kamerafolge, Wert für Wert."""
    phases = _corpus_phases()
    recording = [motion for phase in sorted(phases) for motion in phases[phase]]

    def replay() -> list[CameraPose]:
        poses = []
        pose = START
        for motion in recording:
            pose = camera_step(pose, motion, DT, speed=1.4)
            poses.append(pose)
        return poses

    assert replay() == replay()


def test_looking_straight_down_still_turns_instead_of_shrinking() -> None:
    """Blick entlang des eigenen Oben: der Rechtsvektor darf nie null werden.

    Eine Drehung um eine Nullachse staucht (Rodrigues wird zu ``vector * cos``)
    — der Abstand schrumpfte mit jedem Takt, und das Oben fiel in sich zusammen.
    """
    down = CameraPose(
        position=(0.0, 0.0, 120.0), focal_point=(0.0, 0.0, 0.0), view_up=(0.0, 0.0, 1.0)
    )
    for motion in (Motion(rx=1.0), Motion(rz=1.0), Motion(ry=1.0), Motion(x=1.0, z=-1.0)):
        after = camera_step(down, motion, DT)
        assert distance(after) == pytest.approx(distance(down)), motion
        assert math.dist(after.view_up, (0.0, 0.0, 0.0)) == pytest.approx(1.0), motion
        assert abs(sum(a * b for a, b in zip(forward(after), after.view_up, strict=True))) < 1e-6


# --- Steuerung ------------------------------------------------------------------


@dataclass
class _Camera:
    position: tuple[float, float, float] = START.position
    focal_point: tuple[float, float, float] = START.focal_point
    up: tuple[float, float, float] = START.view_up


@dataclass
class _Plotter:
    camera: _Camera = field(default_factory=_Camera)


@dataclass
class _Viewport:
    plotter: _Plotter | None = field(default_factory=_Plotter)
    sketch_active: bool = False
    draws: int = 0
    settled: int = 0
    parallel_scale: float | None = None

    def camera_pose(self) -> tuple[object, object, object, float | None]:
        assert self.plotter is not None
        camera = self.plotter.camera
        return (camera.position, camera.focal_point, camera.up, self.parallel_scale)

    def set_camera_pose(
        self,
        position: object,
        focal_point: object,
        view_up: object,
        parallel_scale: float | None = None,
    ) -> None:
        assert self.plotter is not None
        self.plotter.camera.position = position  # type: ignore[assignment]
        self.plotter.camera.focal_point = focal_point  # type: ignore[assignment]
        self.plotter.camera.up = view_up  # type: ignore[assignment]
        if parallel_scale is not None:
            self.parallel_scale = parallel_scale
        self.draws += 1

    def settle_camera(self) -> None:
        self.settled += 1


@dataclass
class _Settings:
    spacemouse_enabled: bool = True
    spacemouse_speed: int = 5
    spacemouse_invert: bool = False
    spacemouse_seen: bool = False


def _controller(
    qt_app: object, *, settings: _Settings | None = None, viewport: _Viewport | None = None
) -> tuple[SpaceMouseController, _Viewport, _Settings, list[str]]:
    view = viewport or _Viewport()
    conf = settings or _Settings()
    fits: list[str] = []
    controller = SpaceMouseController(view, conf, lambda: fits.append("fit"))
    return controller, view, conf, fits


def test_a_report_marks_the_device_as_seen_once(qt_app: QApplication) -> None:
    """Die Einstellungszeile erscheint ab dem ersten Gerät — und das Signal kommt genau einmal."""
    controller, _view, settings, _fits = _controller(qt_app)
    seen: list[int] = []
    controller.deviceSeen.connect(lambda: seen.append(1))
    assert not settings.spacemouse_seen
    controller.handle_report(report(1, 0, 0, 0))
    controller.handle_report(report(1, 100, 0, 0))
    assert settings.spacemouse_seen
    assert seen == [1]


def test_a_button_press_fits_once_per_press(qt_app: QApplication) -> None:
    """Flanke, nicht Pegel: gehalten ist nicht noch einmal gedrückt."""
    controller, _view, _settings, fits = _controller(qt_app)
    controller.handle_report(bytes([3, 1, 0]))
    controller.handle_report(bytes([3, 1, 0]))
    assert fits == ["fit"]
    controller.handle_report(bytes([3, 0, 0]))
    controller.handle_report(bytes([3, 2, 0]))
    assert fits == ["fit", "fit"], "jede Taste passt ein, jede nur beim Drücken"


def test_advance_moves_the_camera_and_draws_once(qt_app: QApplication) -> None:
    controller, view, _settings, _fits = _controller(qt_app)
    assert not controller.advance(DT), "ohne Bewegung wird nichts gezeichnet"
    controller.handle_report(report(1, 350, 0, 0))
    assert controller.advance(DT)
    assert view.draws == 1
    assert view.plotter is not None
    assert view.plotter.camera.position[0] < 0.0
    assert controller.motion.x == 1.0


def test_switched_off_the_device_is_still_seen_but_moves_nothing(qt_app: QApplication) -> None:
    """Aus ist aus — und trotzdem weiß die Anwendung, dass ein Gerät da ist."""
    controller, view, settings, fits = _controller(
        qt_app, settings=_Settings(spacemouse_enabled=False)
    )
    controller.handle_report(report(1, 350, 0, 0))
    controller.handle_report(bytes([3, 1, 0]))
    assert settings.spacemouse_seen
    assert fits == []
    controller.advance(DT)
    assert view.draws == 0


def test_without_a_plotter_nothing_happens(qt_app: QApplication) -> None:
    """Offscreen gibt es keinen Plotter — und keinen Fehler."""
    controller, _view, _settings, _fits = _controller(qt_app, viewport=_Viewport(plotter=None))
    controller.handle_report(report(1, 350, 0, 0))
    assert not controller.advance(DT)


def test_in_sketch_mode_the_view_keeps_its_direction(qt_app: QApplication) -> None:
    controller, view, _settings, _fits = _controller(qt_app, viewport=_Viewport(sketch_active=True))
    controller.handle_report(report(2, 350, 0, 350))
    assert not controller.advance(DT), "Drehen tut im Zeichenmodus nichts"
    controller.handle_report(report(1, 0, 350, 0))
    assert controller.advance(DT)
    assert view.plotter is not None
    assert forward(
        CameraPose(
            view.plotter.camera.position, view.plotter.camera.focal_point, view.plotter.camera.up
        )
    ) == pytest.approx(forward(START))


def test_without_the_hid_package_the_reader_stays_silent(qt_app: QApplication) -> None:
    """Abnahme 2: ohne Paket startet alles, und niemand erfährt davon."""
    from app.ui.spacemouse import HidReader

    reader = HidReader()
    reader._unavailable = True
    assert not reader.open()
    assert reader.read() == []
    assert not reader.is_open
    controller = SpaceMouseController(_Viewport(), _Settings(), lambda: None, reader=reader)
    controller.start()
    assert not controller._poll.isActive()
    assert controller._scan.isActive(), "gesucht wird trotzdem weiter — für das Einstecken später"
    controller.stop()
    assert not controller._scan.isActive()


def test_the_settings_carry_the_four_fields_with_their_defaults() -> None:
    from app.ui.settings import UiSettings

    settings = UiSettings()
    assert settings.spacemouse_enabled is True
    assert settings.spacemouse_speed == 5
    assert settings.spacemouse_invert is False
    assert settings.spacemouse_seen is False


def test_the_settings_row_appears_only_after_a_device_was_seen(qt_app: QApplication) -> None:
    """Kein Gerät, keine Spur — ab dem ersten Gerät bleibt die Zeile, auch abgezogen."""
    from app.ui.settings import UiSettings
    from app.ui.settings_dialog import SettingsDialog

    unseen = SettingsDialog(UiSettings(), None)
    try:
        assert not unseen.spacemouse.isVisibleTo(unseen)
        assert not unseen.spacemouse_speed.isVisibleTo(unseen)
    finally:
        unseen.deleteLater()

    settings = UiSettings(spacemouse_seen=True, spacemouse_speed=7)
    dialog = SettingsDialog(settings, None)
    try:
        assert dialog.spacemouse.isVisibleTo(dialog)
        assert dialog.spacemouse.isChecked()
        assert dialog.spacemouse_speed.value() == 7
        dialog.spacemouse_speed.setValue(9)
        dialog.spacemouse_invert.setChecked(True)
        dialog.spacemouse.setChecked(False)
        assert not dialog.spacemouse_speed.isEnabled(), "aus heißt: der Regler ruht"
        dialog.apply_to(settings)
    finally:
        dialog.deleteLater()
    assert (settings.spacemouse_enabled, settings.spacemouse_speed, settings.spacemouse_invert) == (
        False,
        9,
        True,
    )


def test_five_hundred_reports_leave_the_document_alone(qt_app: QApplication) -> None:
    """Abnahme 8: kein Verlaufsschritt — die 3D-Maus fährt die Kamera und sonst nichts."""
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        before = window.session.history.operations
        for index in range(500):
            window.spacemouse.handle_report(report(1, 300 - index, index, -index, index, 50, 200))
            window.spacemouse.handle_report(bytes([3, index % 2, 0]))
            window.spacemouse.advance(DT)
        QApplication.processEvents()
        assert window.session.history.operations == before
        assert window.session.history.undone == ()
        assert window.settings.spacemouse_seen
    finally:
        window.close()
        window.deleteLater()


def test_a_plugged_device_counts_as_seen_before_it_moves(qt_app: QApplication) -> None:
    """Eingesteckt heißt gesehen — die Einstellungszeile wartet nicht auf den ersten Zug."""
    from app.ui.spacemouse import HidReader

    class _Closable:
        def close(self) -> None:
            pass

    class _Present(HidReader):
        def open(self) -> bool:
            self._device = _Closable()
            return True

        def read(self) -> list[bytes]:
            return []

    settings = _Settings()
    seen: list[int] = []
    controller = SpaceMouseController(_Viewport(), settings, lambda: None, reader=_Present())
    controller.deviceSeen.connect(lambda: seen.append(1))
    controller.start()
    controller._look_for_device()
    try:
        assert settings.spacemouse_seen
        assert seen == [1]
        assert controller._poll.isActive() and not controller._scan.isActive()
    finally:
        controller.stop()


def test_in_parallel_projection_the_zoom_changes_the_picture_not_the_distance() -> None:
    """Parallelprojektion: Zoom ist die halbe Bildhöhe, der Standort bleibt.

    Ein Standort näher am Blickpunkt ändert dort am Bild nichts — und wanderte
    unsichtbar bis auf einen halben Millimeter heran, sodass das Bild beim
    Verlassen des Zeichenmodus in den Körper sprang.
    """
    flat = CameraPose(START.position, START.focal_point, START.view_up, parallel_scale=50.0)
    closer = camera_step(flat, Motion(y=-1.0), DT)
    farther = camera_step(flat, Motion(y=1.0), DT)
    assert closer.position == START.position and farther.position == START.position
    assert closer.parallel_scale is not None and farther.parallel_scale is not None
    assert closer.parallel_scale < 50.0 < farther.parallel_scale
    moved = camera_step(flat, Motion(x=1.0), DT)
    assert moved.position[0] < 0.0, "geschoben wird auch parallel"
    assert moved.parallel_scale == 50.0
    assert camera_step(START, Motion(y=-1.0), DT).parallel_scale is None


def test_the_camera_settles_once_after_the_cap_comes_to_rest(qt_app: QApplication) -> None:
    """Schatten und Raster ziehen nach der Fahrt nach — einmal, nicht sechzigmal je Sekunde."""
    from app.ui.spacemouse import HidReader

    reports: list[bytes] = [report(1, 350, 0, 0), report(1, 350, 0, 0), report(1, 0, 0, 0)]

    class _Feeding(HidReader):
        def open(self) -> bool:
            self._device = object()
            return True

        def read(self) -> list[bytes]:
            return [reports.pop(0)] if reports else []

        def close(self) -> None:
            self._device = None

    view = _Viewport()
    controller = SpaceMouseController(view, _Settings(), lambda: None, reader=_Feeding())
    controller._look_for_device()
    try:
        controller._tick()
        controller._tick()
        assert view.draws >= 1 and view.settled == 0, "während der Fahrt kein Nachziehen"
        controller._tick()
        controller._tick()
        assert view.settled == 1, "einmal, sobald die Kappe ruht"
        controller._tick()
        assert view.settled == 1
    finally:
        controller.stop()


def test_the_search_waits_for_the_window_and_then_backs_off(qt_app: QApplication) -> None:
    """Ohne Gerät sucht die Anwendung erst nach dem Fensteraufbau und dann immer seltener."""
    from app.ui.spacemouse import SCAN_FIRST_MS, SCAN_MAX_MS, SCAN_MS, HidReader

    reader = HidReader()
    reader._unavailable = True
    controller = SpaceMouseController(_Viewport(), _Settings(), lambda: None, reader=reader)
    controller.start()
    try:
        assert controller._scan.isActive()
        assert controller._scan.interval() == SCAN_FIRST_MS
        waits = []
        for _ in range(6):
            controller._look_for_device()
            waits.append(controller._scan.interval())
        assert waits[0] == SCAN_MS
        assert waits == sorted(waits), "jede leere Suche wartet länger"
        assert waits[-1] <= SCAN_MAX_MS
    finally:
        controller.stop()


def test_flying_takes_the_focal_point_along_and_zooming_does_not() -> None:
    """``fly=True`` fliegt, ``fly=False`` zoomt — der Unterschied ist der Blickpunkt.

    **Warum es beides braucht.** Der Zoom ändert den Abstand zum Blickpunkt und
    lässt ihn stehen; die Kamera fährt also bis vor das Teil und nie hinein.
    Für W/S ist das die falsche Bewegung, und zwar aus zwei Gründen: Der Zoom
    liegt schon auf dem Mausrad (Entscheidung Robert, 03.09.2026), und eine
    Kamera, die ihren Blickpunkt zurücklässt, dreht sich danach um einen Ort,
    den der Kunde längst hinter sich hat.

    Beim Fliegen wandern Standort und Blickpunkt gemeinsam — der Abstand
    zwischen ihnen bleibt, und mit ihm die Empfindlichkeit jeder folgenden
    Drehung.
    """
    pose = CameraPose(
        position=(0.0, -100.0, 0.0), focal_point=(0.0, 0.0, 0.0), view_up=(0.0, 0.0, 1.0)
    )

    flown = camera_step(pose, Motion(y=-1.0), 0.1, fly=True)
    zoomed = camera_step(pose, Motion(y=-1.0), 0.1)

    assert flown.focal_point != pose.focal_point, "beim Fliegen wandert der Blickpunkt mit"
    assert zoomed.focal_point == pose.focal_point, "beim Zoomen bleibt er stehen"

    vorher = pose.position[1] - pose.focal_point[1]
    nachher = flown.position[1] - flown.focal_point[1]
    assert vorher == pytest.approx(nachher), "und der Abstand bleibt, also auch die Drehrate"


def test_flying_and_zooming_pull_in_the_same_direction() -> None:
    """Dieselbe Achse zieht in beiden Auslegungen in dieselbe Richtung.

    ``y`` heißt bei der Kappe „wegschieben ist positiv", und der Zoom folgt
    dem. Eine Achse, die je nach Schalter das Gegenteil täte, wäre die Falle
    für den Nächsten, der ``fly`` an ein Gerät hängt — er würde sie einmal
    messen, richtig finden und beim zweiten Modus danebenliegen.
    """
    pose = CameraPose(
        position=(0.0, -100.0, 0.0), focal_point=(0.0, 0.0, 0.0), view_up=(0.0, 0.0, 1.0)
    )

    for reach in (1.0, -1.0):
        flown = camera_step(pose, Motion(y=reach), 0.1, fly=True)
        zoomed = camera_step(pose, Motion(y=reach), 0.1)
        weg_beim_fliegen = flown.position[1] - pose.position[1]
        weg_beim_zoomen = zoomed.position[1] - pose.position[1]
        assert (weg_beim_fliegen < 0) == (weg_beim_zoomen < 0), (
            f"y={reach}: fliegen {weg_beim_fliegen:+.2f}, zoomen {weg_beim_zoomen:+.2f} — "
            "dieselbe Achse muss in dieselbe Richtung ziehen"
        )


def test_a_second_of_flight_carries_about_one_distance() -> None:
    """Eine Sekunde Flug trägt ungefähr eine Kameraentfernung (§2.9).

    Die Zahl ist keine Geschmacksfrage, sondern die Antwort auf einen
    gemessenen Fehler: Bis zum 03.09.2026 war ein Tastenanschlag ein
    Flugschritt von 14,4 % der Entfernung, und die Wiederholung überließ die
    Anwendung dem Betriebssystem. Gerechnet sind das bei 31 Anschlägen je
    Sekunde das Viereinhalbfache der Entfernung — der Bauraum in einer
    Fünftelsekunde, nach einer halben Sekunde Stillstand davor.

    Seither fährt ein eigener Takt, und ``FLIGHT_RATE`` sagt in einer Einheit,
    die man lesen kann, wie schnell: Entfernungen je Sekunde. Dieser Test hält
    fest, dass die Umrechnung in ``camera_step`` das auch liefert — dessen
    ``speed`` ist ein Faktor auf ``PAN_RATE`` und keine Strecke, und genau da
    verrutscht so etwas.
    """
    from app.ui.spacemouse import PAN_RATE, CameraPose, Motion, camera_step
    from app.ui.viewport import FLIGHT_RATE

    abstand = 300.0
    pose = CameraPose(
        position=(0.0, -abstand, 0.0), focal_point=(0.0, 0.0, 0.0), view_up=(0.0, 0.0, 1.0)
    )
    nach_einer_sekunde = camera_step(
        pose, Motion(y=-1.0), 1.0, speed=FLIGHT_RATE / PAN_RATE, fly=True
    )

    weg = abs(nach_einer_sekunde.position[1] - pose.position[1])
    assert weg == pytest.approx(abstand * FLIGHT_RATE, rel=0.01), (
        f"eine Sekunde trägt {weg / abstand:.2f} Entfernungen statt {FLIGHT_RATE}"
    )

    # Und der Abstand bleibt: Fliegen ändert ihn nicht, sonst würde die
    # Bewegung mit jedem Schritt schneller oder langsamer.
    vorher = math.dist(pose.position, pose.focal_point)
    nachher = math.dist(nach_einer_sekunde.position, nach_einer_sekunde.focal_point)
    assert nachher == pytest.approx(vorher), "der Flug hält den Abstand"
