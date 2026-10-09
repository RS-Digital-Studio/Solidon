"""Export, G-Code-Prüfung und Slicerübergabe am echten Fenster (§29, §22)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from app.core import errors
from app.core.scene import OperationDraft
from app.core.types import (
    Finding,
    SceneObject,
)
from app.i18n import tr
from app.ui import main_window as main_window_module
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import MESHES, export_anyway, wait_for_export
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


@pytest.fixture(autouse=True)
def _window_computes_fine(request: pytest.FixtureRequest) -> None:
    """Die Exportmechanik am feinen Ergebnis, wie nach dem Warten (RM-426).

    Seit RM-426 rechnet das Fenster im Entwurf, und ein Export bestellt erst
    die feine Rechnung. Diese Datei prüft, was danach geschieht — Arbeiter,
    Vorprüfung, Abbruch, späte Signale —, und rechnet deshalb von Anfang an
    fein. Das Warten selbst prüft ``test_ui.py``.
    """
    if "window" in request.fixturenames:
        request.getfixturevalue("window").session.quality = "fine"


def test_an_unreadable_gcode_file_says_so(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 17: keine Handlung endet stumm.

    ``action_check_gcode`` las die Datei ohne Netz darunter. Zwischen Auswählen
    und Lesen kann sie verschwinden, auf einem getrennten Laufwerk liegen oder
    ohne Leserecht dastehen — die Ausnahme lief dann ungefangen in Qts
    Ereignisverteiler: kein Dialog, keine Zeile, die Handlung tat nichts.
    """
    from PySide6.QtWidgets import QFileDialog

    from app.ui import dialogs

    gezeigt: list[object] = []
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(tmp_path / "weg.gcode"), "")),
    )
    monkeypatch.setattr(dialogs, "show_error", lambda error, *args, **kwargs: gezeigt.append(error))
    monkeypatch.setattr(
        "app.ui.main_window.show_error", lambda error, *args, **kwargs: gezeigt.append(error)
    )

    window.action_check_gcode()

    worker = window._gcode_worker
    assert worker is not None
    worker.wait(20_000)
    QApplication.processEvents()

    assert gezeigt, "die fehlende Datei wurde stillschweigend übergangen"
    assert gezeigt[0].suggestions, "und der Fehler trägt keinen Handlungsvorschlag"


def test_reading_a_gcode_file_runs_outside_the_qt_thread(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.8: Ein Strom von 10 MB kostet gemessen 520 ms.

    ``action_check_gcode`` las die Datei und zerlegte sie im Qt-Hauptthread,
    ohne dass das Fenster Ereignisse bearbeiten konnte. Gemessen wird am
    Thread während des Zerlegens; die gestufte Anzeige beginnt zugleich.
    """
    from PySide6.QtWidgets import QFileDialog

    from app.core.slice import gcode as gcode_module

    datei = tmp_path / "platte.gcode"
    datei.write_text(";LAYER:0\nG1 X10 Y10 E0.5 F1800\nG1 Z0.2\n", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(datei), "")),
    )
    gesehen: list[tuple[int, object, object]] = []
    echt = gcode_module.analyze_lines

    def beobachtet(lines: Any, *, cancelled: Any = None) -> Any:
        gesehen.append((threading.get_ident(), getattr(lines, "name", None), cancelled))
        return echt(lines, cancelled=cancelled)

    monkeypatch.setattr("app.ui.main_window.gcode.analyze_lines", beobachtet)

    window.action_check_gcode()

    worker = window._gcode_worker
    assert worker is not None
    assert window._progress_states["gcode"].active
    worker.wait(20_000)
    QApplication.processEvents()

    assert gesehen, "zerlegt wurde nichts — der Test misst am falschen Ort"
    thread_id, stream_name, token = gesehen[0]
    assert thread_id != threading.get_ident(), "zerlegt wurde im Qt-Hauptthread"
    assert stream_name == str(datei), (
        "die ganze Datei wurde vor dem Zerlegen in den Speicher gelesen"
    )
    assert token is worker.cancel, "der Abbrechen-Schalter erreicht den Zeilenparser nicht"
    assert not window._progress_states["gcode"].active


def test_cancelling_reaches_the_running_gcode_parser(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Abbrechen-Knopf beendet auch das Zerlegen, nicht nur Lesen und Zustellen."""
    from PySide6.QtWidgets import QFileDialog

    from app.core.slice import gcode as gcode_module

    path = tmp_path / "lang.gcode"
    path.write_text("G1 X1 Y1 E1\n", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(path), "")),
    )
    started = threading.Event()
    pulse = threading.Event()
    tokens: list[object] = []
    echt = gcode_module.analyze_lines

    def waits_for_cancel(_lines: Any, *, cancelled: Any = None) -> Any:
        tokens.append(cancelled)
        started.set()
        if cancelled is None:
            return echt(_lines, cancelled=cancelled)
        while not cancelled.is_cancelled:
            pulse.wait(0.01)
        cancelled.raise_if_cancelled()

    monkeypatch.setattr("app.ui.main_window.gcode.analyze_lines", waits_for_cancel)

    window.action_check_gcode()
    worker = window._gcode_worker
    assert worker is not None and started.wait(1.0)

    window._cancel_gcode()
    assert worker.wait(2_000)
    QApplication.processEvents()

    assert tokens == [worker.cancel]
    assert "abgebrochen" in window.status_message.text().lower()


def test_cancelling_rejects_a_gcode_result_already_waiting_in_qt(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch ein vor dem Knopfdruck eingereihtes Ergebnis bleibt verworfen."""
    from PySide6.QtWidgets import QFileDialog

    path = tmp_path / "fertig.gcode"
    path.write_text(";LAYER:0\nG1 X10 Y10 E0.5 F1800\n", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(path), "")),
    )
    added: list[object] = []
    compared: list[object] = []
    monkeypatch.setattr(
        window.report,
        "add_findings",
        lambda findings, **_kwargs: added.append(findings),
    )
    monkeypatch.setattr(window, "_compare_totals", compared.append)

    window.action_check_gcode()
    worker = window._gcode_worker
    assert worker is not None and worker.wait(2_000)

    window._cancel_gcode()
    QApplication.processEvents()

    assert added == []
    assert compared == []
    assert not window._progress_states["gcode"].active


def test_a_gcode_check_keeps_the_body_selected_when_it_started(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bedienbare Auswahl und späteres Worker-Ergebnis gehören nicht vermischt."""
    from PySide6.QtWidgets import QFileDialog

    path = tmp_path / "stuetzen.gcode"
    path.write_text(
        "; filament_diameter = 1.75\n"
        "G21\nG90\nM82\nG92 E0\nG1 X0 Y0 Z0.2 F1800\n"
        ";LAYER:0\n;TYPE:Support material\nG1 X10 Y10 E1 F1800\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(path), "")),
    )
    selected = ["body-at-start"]
    compared: list[str] = []
    monkeypatch.setattr(window.object_tree, "selected", lambda: selected[0])
    monkeypatch.setattr(
        window,
        "_slice_of",
        lambda object_id, _complete: compared.append(object_id),
    )

    window.action_check_gcode()
    worker = window._gcode_worker
    assert worker is not None and worker.wait(2_000)
    selected[0] = "body-selected-later"
    QApplication.processEvents()

    assert compared == ["body-at-start"]


def test_export_suggests_the_complete_print_format_first(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne CAD-Wissen soll der erste Weg nichts Wichtiges wegwerfen.

    3MF bewahrt Baugruppe, Farben und Druckeinstellungen; STL ist der
    ausdrücklich wählbare Altweg. Der Vorschlag im Dateidialog muss deshalb
    zu seinem ersten Filter passen.
    """
    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    asked: list[tuple[str, str]] = []

    def remember(_parent: object, _title: str, name: str, filters: str) -> tuple[str, str]:
        asked.append((name, filters))
        return "", ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(remember))

    window.action_export()

    assert asked
    name, filters = asked[0]
    assert name.endswith(".3mf")
    assert filters.split(";;", 1)[0] == "3MF (*.3mf)"


def test_export_writes_the_selected_format(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Weg 1 endet mit „exportieren" — und dieser Schritt war aus dem Fenster
    nicht erreichbar: der Schreiber stand seit P2 im Kern, der einzige Weg zu
    einer Datei führte über einen installierten Slicer."""
    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)

    target = tmp_path / "wuerfel.stl"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "STL (*.stl)")),
    )
    window.action_export()
    wait_for_export(window)

    assert target.is_file(), "der gewählte Name ist die Datei, nicht ein Schema daraus"
    assert target.stat().st_size > 0


@pytest.mark.parametrize("change", ["selection", "geometry", "project"])
def test_export_keeps_the_checked_objects_while_the_window_changes(
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    """Vorprüfung und Datei meinen dieselben Körper und denselben Dokumentstand."""
    import trimesh

    assert window.session.apply(
        "Zwei Körper",
        [
            OperationDraft(op="create_box", params={"width": 10.0, "depth": 10.0, "height": 10.0}),
            OperationDraft(op="create_box", params={"width": 30.0, "depth": 10.0, "height": 10.0}),
        ],
    )
    assert window.session.wait_for_idle(30000)
    entered, proceed = threading.Event(), threading.Event()
    checked: list[tuple[list[str], float]] = []

    def held_check(objects: list[SceneObject], *args: Any, **kwargs: Any) -> list[Finding]:
        entered.set()
        assert proceed.wait(15)
        checked.append(([body.id for body in objects], kwargs["document"].ops[0].params["width"]))
        return [
            Finding(
                code="export.not_watertight",
                severity="warning",
                message="Das Objekt ist nicht geschlossen.",
                object_id=objects[0].id,
            )
        ]

    monkeypatch.setattr(main_window_module, "check_before_export", held_check)
    export_anyway(monkeypatch)
    window.object_tree.select_object("obj_1")
    target = tmp_path / "auswahl.stl"
    window._start_export(target, "stl")
    try:
        assert entered.wait(5)
        if change == "selection":
            window.object_tree.select_object("obj_2")
        elif change == "geometry":
            window.session.change_params(1, {"width": 40.0, "depth": 10.0, "height": 10.0})
            assert window.session.wait_for_idle(30000)
        else:
            window.session.start_new()
            assert window.session.wait_for_idle(30000)
            assert window.session.apply(
                "Neues Projekt",
                [
                    OperationDraft(
                        op="create_box", params={"width": 50.0, "depth": 10.0, "height": 10.0}
                    )
                ],
            )
            assert window.session.wait_for_idle(30000)
        proceed.set()
        wait_for_export(window)
        assert checked == [(["obj_1"], 10.0)], "only the original document is checked, once"
        assert target.is_file()
        written = trimesh.load_mesh(target)
        assert written.extents[0] == pytest.approx(10.0), "the checked body reaches the file"
    finally:
        proceed.set()
        wait_for_export(window)


def _thin_walled_tube(window: MainWindow) -> None:
    """Ein Rohr mit einem halben Millimeter Wand — der kleinste Körper, an dem
    die Exportprüfung etwas zu sagen hat, das sie vor RM-140 nicht sagte."""
    window.session.apply(
        "Zylinder",
        [OperationDraft(op="create_cylinder", params={"diameter": 20.0, "height": 20.0})],
    )
    assert window.session.wait_for_idle(60_000)
    window.session.apply(
        "Bohren",
        [
            OperationDraft(
                op="drill_hole", inputs=("obj_1",), params={"diameter": 19.0, "x": 0.0, "y": 0.0}
            )
        ],
    )
    assert window.session.wait_for_idle(60_000)


def test_the_export_asks_before_it_writes(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§29: „Bericht, nicht Blockade" — und beides vor der Datei (RM-140).

    Die Prüfung lief bis dahin mit dem Schreiben in einem Zug; die Befunde
    kamen an, als die Datei schon auf der Platte lag. Jetzt hört der erste
    Lauf an der Prüfung auf: Der Prüfbericht bekommt die Befunde, der Dialog
    fragt, und erst ein Ja schreibt.

    Gemessen an der Wandstärke, weil sie der Teil ist, der vorher gar nicht
    geprüft wurde — sie ist damit zugleich der Beleg, dass die Szene beim
    Export ankommt.
    """
    from PySide6.QtWidgets import QFileDialog

    _thin_walled_tube(window)
    target = tmp_path / "rohr.3mf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "3MF (*.3mf)")),
    )
    gesehen: list[str] = []

    def abbrechen(box: QMessageBox) -> int:
        gesehen.append(box.informativeText())
        next(entry for entry in box.buttons() if entry.text() == tr("Abbrechen")).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", abbrechen)
    window.action_export()
    wait_for_export(window)

    assert gesehen, "der Export schrieb, ohne die Befunde zu zeigen"
    assert "Wand" in gesehen[0], f"der Dialog nennt nicht, was gefunden wurde: {gesehen[0]!r}"
    assert not target.exists(), "abgebrochen heißt: keine Datei"

    def trotzdem(box: QMessageBox) -> int:
        next(entry for entry in box.buttons() if entry.text() == tr("Trotzdem exportieren")).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", trotzdem)
    window.action_export()
    wait_for_export(window)

    assert target.is_file(), "ein bewusst fortgesetzter Export schreibt"


def test_a_clean_export_asks_nothing(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenprobe, und sie ist eine eigene Zusage.

    Der häufige Fall ist der saubere. Ein Dialog, der „alles in Ordnung" sagt,
    ist ein Klick ohne Auskunft — und nach dem dritten liest ihn niemand mehr.
    """
    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    target = tmp_path / "wuerfel.3mf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "3MF (*.3mf)")),
    )

    def niemals(box: QMessageBox) -> int:
        raise AssertionError(f"ein sauberer Export fragt nicht: {box.text()!r}")

    monkeypatch.setattr(QMessageBox, "exec", niemals)
    window.action_export()
    wait_for_export(window)

    assert target.is_file()


def test_changing_only_the_export_filter_changes_format_and_suffix(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der 3MF-Vorschlag darf eine spätere Filterwahl nicht überstimmen.

    Ein Kunde ändert im Dateidialog häufig nur „Dateityp" auf STL und lässt
    den vorausgefüllten Namen stehen. Inhalt und Endung müssen dann beide STL
    werden; eine STL-Datei namens ``.3mf`` wäre weder verständlich noch in
    jedem Slicer zu öffnen.
    """
    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    proposed: list[str] = []

    def choose(_parent: object, _title: str, name: str, _filters: str) -> tuple[str, str]:
        proposed.append(name)
        return str(tmp_path / Path(name).name), "STL (*.stl)"

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(choose))
    window.action_export()
    wait_for_export(window)

    assert proposed and proposed[0].endswith(".3mf"), "3MF bleibt der einfache Kundenweg"
    expected = tmp_path / f"{Path(proposed[0]).stem}.stl"
    assert expected.is_file(), "der gewählte Filter bestimmt Inhalt und sichtbare Endung"
    assert not (tmp_path / Path(proposed[0]).name).exists(), "keine falsch benannte STL-Datei"


def test_an_explicit_export_suffix_still_wins_over_the_filter() -> None:
    """Wer den Namen selbst samt Endung tippt, hat die genauere Wahl getroffen."""
    from app.ui.main_window import _export_target

    target, export_format = _export_target(Path("mein_teil.obj"), "STL (*.stl)", "projekt.3mf")

    assert target == Path("mein_teil.obj")
    assert export_format == "obj"


def test_export_as_3mf_writes_one_assembly(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mehrere Körper als 3MF sind eine Baugruppe in einer Datei (§20) —
    nicht eine Datei je Körper, über deren Zusammengehörigkeit der Slicer
    selbst entscheiden müsste.

    **Und die Datei trägt die Druckeinstellungen mit** (§29). Sie tat es nicht:
    Der Aufruf im Menü ließ ``settings`` weg, und heraus kam eine 3MF ganz ohne
    ``project_settings.config``. Der Slicer füllt dann alles aus dem Profil,
    das gerade bei ihm steht — und meldet Widersprüche zu einem Drucker, den
    niemand gemeint hat.
    """
    import json
    import zipfile

    from PySide6.QtWidgets import QFileDialog

    from app.core.knowledge import print_settings

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    window.session.import_model(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    window.session.set_print_settings(print_settings.resolve(window.session.profile))

    target = tmp_path / "baugruppe.3mf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "3MF (*.3mf)")),
    )
    # Das zweite Modell liegt seit dem 28.09.2026 an einer freien Stelle; wo
    # doch zwei Körper am selben Ort stehen, fragt der Export seit RM-140 vor
    # dem Schreiben, und die Antwort steht bereit.
    export_anyway(monkeypatch)
    window.object_tree.tree.clearSelection()
    window.action_export()
    wait_for_export(window)

    written = list(tmp_path.glob("*.3mf"))
    assert len(written) == 1, "eine Baugruppe, eine Datei"
    with zipfile.ZipFile(written[0]) as archive:
        assert "Metadata/project_settings.config" in archive.namelist(), (
            "die Datei ist reine Geometrie — der Slicer erfindet den Rest"
        )
        values = json.loads(archive.read("Metadata/project_settings.config"))
    assert values.get("layer_height"), "ohne Schichthöhe sagt die Datei nichts über den Druck"
    assert float(values["layer_height"]) <= window.session.profile.printer.nozzle_diameter, (
        "eine Schichthöhe über dem Düsendurchmesser lehnt jeder Slicer ab"
    )


@pytest.mark.parametrize("remembered", ["", "other printer"])
def test_without_a_fitting_choice_the_export_takes_the_dialogs_choice(
    monkeypatch: pytest.MonkeyPatch, remembered: str
) -> None:
    """RM-623: Leere oder fremde Wahl hieß bisher gar kein Setup.

    Roberts Einstellungen trugen weder Maschine noch Prozess; die Datei ging
    ohne Herstellerprozess hinaus, und das Hauptfenster rechnete mit Solidons
    Tabelle. Jetzt fragt der Export den Bestand nach der Wahl, die der Dialog
    für **diesen** Drucker und dieses Material vorbelegt.
    """
    from pathlib import Path as PathType

    from app.core import discover
    from app.core.export import handover
    from app.ui.print_settings_dialog import remembered_setup
    from app.ui.settings import UiSettings

    monkeypatch.setattr(
        discover, "find_program", lambda *args, **kwargs: PathType("elegoo-slicer.exe")
    )
    asked: list[tuple[str, str, str, str]] = []
    chosen = handover.SlicerSetup(PathType("elegoo-slicer.exe"), "orca", machine_profile="CC2")

    def standard(setup: handover.SlicerSetup, profile, **_kwargs) -> handover.SlicerSetup:  # type: ignore[no-untyped-def]
        asked.append(
            (profile.printer.id, profile.material.id, setup.machine_profile, setup.base_filament)
        )
        return chosen

    monkeypatch.setattr(handover, "standard_choice", standard)
    settings = UiSettings()
    settings.slicer_filament_per_material["petg"] = "Elegoo PETG PRO @ECC2"
    if remembered:
        settings.slicer_machine_profile = "Prusa MK4S"
        settings.slicer_profile_printer = "prusa-mk4s"

    assert remembered_setup(settings, "petg", "centauri-carbon-2") is chosen
    assert asked == [("centauri-carbon-2", "petg", "", "Elegoo PETG PRO @ECC2")], (
        "die gemerkte Spule ist der Vorzug wie im Dialog, die fremde Maschine reist nicht mit"
    )


def test_the_remembered_slicer_becomes_a_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Was im Druckeinstellungen-Dialog stand, gilt auch für den Export (§29).

    Ohne Systemprofil trägt eine 3MF zwar Solidons Werte, aber keinen Drucker,
    zu dem sie passen — und der Slicer bleibt bei dem, der gerade bei ihm
    eingestellt ist. Steht dort eine 0,2er Düse, kollidiert sie mit einer
    ersten Schicht von 0,25 mm, und die Meldung spricht vom Modell.
    """
    from pathlib import Path as PathType

    from app.core import discover
    from app.ui.print_settings_dialog import remembered_setup
    from app.ui.settings import UiSettings

    settings = UiSettings()
    monkeypatch.setattr(
        discover, "find_program", lambda *args, **kwargs: PathType("orca-slicer.exe")
    )
    # Ohne gemerkte Wahl entscheidet der Bestand (RM-623); dieser hier hat
    # keinen, und ohne ihn gibt es nichts aufzulösen.
    assert remembered_setup(settings) is None, "kein Bestand, der den Drucker kennt"

    settings.slicer_machine_profile = "Elegoo Centauri Carbon 2 0.4 nozzle"
    settings.slicer_base_process = "0.20mm Standard @Elegoo CC2 0.4 nozzle"
    settings.slicer_base_filament = "Elegoo PETG PRO @ECC2"

    setup = remembered_setup(settings)
    assert setup is not None, "der gemerkte Drucker ist da, das Programm auch"
    assert setup.machine_profile == settings.slicer_machine_profile
    assert setup.base_process == settings.slicer_base_process
    assert setup.base_filament == settings.slicer_base_filament

    # Je Material zuerst, das globale nur als Rückfall — sonst trägt ein
    # TPU-Projekt nach einem PETG-Lauf das PETG-Profil.
    settings.slicer_filament_per_material["tpu"] = "Elegoo TPU @ECC2"
    per_material = remembered_setup(settings, "tpu")
    assert per_material is not None
    assert per_material.base_filament == "Elegoo TPU @ECC2"
    fallback = remembered_setup(settings, "pla")
    assert fallback is not None
    assert fallback.base_filament == settings.slicer_base_filament


def test_a_single_body_3mf_carries_the_settings_too(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der häufigste Fall ist ein Körper — und genau der lief über den
    Plan-Weg, der keine Einstellungen kennt. Dazu war der Dialog nie offen:
    ``document.print_settings`` ist dann ``None``, und das hieß reine
    Geometrie statt der Auflösung aus Stufe, Material und Drucker (§29)."""
    import json
    import zipfile

    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)

    target = tmp_path / "einzel.3mf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "3MF (*.3mf)")),
    )
    window.object_tree.tree.clearSelection()
    window.action_export()
    wait_for_export(window)

    written = list(tmp_path.glob("*.3mf"))
    assert len(written) == 1
    with zipfile.ZipFile(written[0]) as archive:
        assert "Metadata/project_settings.config" in archive.namelist(), (
            "ein Körper ohne geöffneten Dialog ist der Normalfall — nicht die Ausnahme"
        )
        values = json.loads(archive.read("Metadata/project_settings.config"))
    assert values.get("layer_height"), "die Auflösung aus Stufe, Material und Drucker gilt"


def test_the_export_leaves_the_window_usable(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.8: Prüfen und Schreiben laufen im Arbeiter, nicht in der
    Ereignisschleife.

    Vorher rechnete und schrieb ``action_export`` komplett im Hauptthread —
    Prüfung vor dem Export, Aufbau der Baugruppe, Anordnungsprüfung und die
    Dateien selbst. Bei mehreren großen Körpern ist das mehr als zwei
    Sekunden mit stehendem Fenster.

    Geprüft wird beides: dass der Aufruf zurückkommt, bevor geschrieben ist,
    und dass der Menüeintrag währenddessen gesperrt bleibt — zwei Läufe auf
    denselben Ordner wären ein Wettlauf um dieselben Dateinamen.
    """
    import time

    from PySide6.QtWidgets import QFileDialog

    from app.ui import main_window as module

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)

    real_write = module.write_plan

    def slow_write(*args: Any, **kwargs: Any) -> Any:
        time.sleep(0.4)
        return real_write(*args, **kwargs)

    monkeypatch.setattr(module, "write_plan", slow_write)
    target = tmp_path / "langsam.stl"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "STL (*.stl)")),
    )

    started = time.perf_counter()
    window.action_export()
    elapsed = time.perf_counter() - started

    assert elapsed < 0.3, "der Aufruf hat auf das Schreiben gewartet — genau das war der Befund"
    assert window._export_worker is not None, "ohne Arbeiter ist nichts nebenher gelaufen"
    assert not window.export_action.isEnabled(), (
        "ein zweiter Lauf schriebe in dieselben Dateien wie der erste"
    )

    wait_for_export(window)

    assert target.is_file()
    assert target.name in window._announcement, "der fertige Export meldet sich nicht"
    assert window._export_worker is None
    assert window.export_action.isEnabled(), "nach dem Lauf ist der Eintrag wieder da"
    assert not window.progress.isVisible(), "der Balken bleibt stehen, wenn niemand ihn abräumt"


@pytest.mark.parametrize("export_format", ["stl", "3mf"])
def test_cancel_export_preflight_never_starts_a_file(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, export_format: str
) -> None:
    """Der gemeinsame Knopf erreicht das Token der Prüfung und beginnt keine Ausgabe."""
    entered, resume = threading.Event(), threading.Event()
    received, writes, failures = [], [], []

    def checking(*args: Any, cancelled: Any, **kwargs: Any) -> list[Finding]:
        received.append(cancelled)
        entered.set()
        assert resume.wait(10)
        cancelled.raise_if_cancelled()
        return []

    def writing(self: Any) -> Any:
        writes.append(self._format)
        return [], []

    monkeypatch.setattr(main_window_module, "check_before_export", checking)
    monkeypatch.setattr(main_window_module._ExportWorker, "_files", writing)
    monkeypatch.setattr(main_window_module._ExportWorker, "_assembly", writing)
    monkeypatch.setattr(main_window_module, "show_error", lambda *args: failures.append(args))
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    window._start_export(tmp_path / f"abgebrochen.{export_format}", export_format)
    worker = window._export_worker
    assert worker is not None
    try:
        assert entered.wait(10)
        assert received == [worker.cancelled]
        assert window.cancel_button.isVisibleTo(window)
        window.cancel_button.click()
        assert worker.cancelled.is_cancelled
        assert not window.cancel_button.isEnabled()
    finally:
        resume.set()
        wait_for_export(window)
    assert not writes and not failures and not list(tmp_path.glob("abgebrochen*"))
    assert window._export_worker is None and not window._exporting
    assert window._export_attempt is None
    assert "Keine Datei wurde geschrieben" in window._announcement
    assert window.export_action.isEnabled() and not window.progress.isVisibleTo(window)


@pytest.mark.parametrize("answer", ["report", "failure"])
def test_a_queued_export_report_is_discarded_after_cancel(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    """Abbrechen gilt auch vor einem bereits eingereihten Bericht oder Prüfungsfehler."""
    offered = []

    def checking(*args: Any, **kwargs: Any) -> list[Finding]:
        if answer == "failure":
            raise errors.UserError(title="Die Prüfung konnte nicht abgeschlossen werden.")
        return [Finding("fit.collision", "warning", "Überschneidung")]

    monkeypatch.setattr(main_window_module, "check_before_export", checking)
    monkeypatch.setattr(main_window_module, "confirm_export", lambda *args: offered.append(args))
    monkeypatch.setattr(main_window_module, "show_error", lambda *args: offered.append(args))
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    target = tmp_path / "abgebrochen.stl"
    window._start_export(target, "stl")
    worker = window._export_worker
    assert worker is not None and worker.wait(10_000)
    window.cancel_button.click()
    QApplication.processEvents()
    assert not offered and not target.exists()
    assert window._export_worker is None and window._export_attempt is None
    assert "Keine Datei wurde geschrieben" in window._announcement


def test_the_export_check_brings_the_report_forward_before_it_asks(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Frage vor dem Export verweist auf den Bericht, also steht er vorn.

    ``confirm_export`` zeigt die ersten Befunde und sagt „Der Rest steht im
    Prüfbericht.“ Seit RM-511 teilt sich der Bericht seine Karte mit *Auswahl*,
    und Warnungen einer Auswertung holen ihn nicht nach vorn — die
    Exportprüfung ist aber ein Ergebnis, das der Kunde angefordert hat
    (``fenster.md``, Export; Durchsicht 0.5.3, Fund 3).
    """
    shown: list[object] = []

    def asked(*_args: object) -> bool:
        shown.append(window.right.currentWidget())
        return False

    monkeypatch.setattr(
        main_window_module,
        "check_before_export",
        lambda *args, **kwargs: [Finding("fit.collision", "warning", "Überschneidung")],
    )
    monkeypatch.setattr(main_window_module, "confirm_export", asked)
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    # Gezeigt: ``_focus_report`` holt nichts in eine Spalte, die niemand sieht.
    window.show()
    window._show_start_screen(False)
    window.right.setCurrentWidget(window.feature_dock)
    target = tmp_path / "gefragt.stl"
    window._start_export(target, "stl")
    wait_for_export(window)
    assert shown == [window.report], "beim Fragen steht der Bericht vorn"
    assert not target.exists()


@pytest.mark.parametrize("ending", ["close", "release"])
def test_ending_the_window_cancels_the_export_preflight(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ending: str
) -> None:
    """Fensterkreuz und Sprachneuaufbau erreichen dasselbe echte Prüfungstoken."""
    entered, resume = threading.Event(), threading.Event()
    dialogs, updates = [], []

    def checking(*args: Any, cancelled: Any, **kwargs: Any) -> list[Finding]:
        entered.set()
        assert resume.wait(10)
        cancelled.raise_if_cancelled()
        return [Finding("fit.collision", "warning", "Überschneidung")]

    monkeypatch.setattr(main_window_module, "check_before_export", checking)
    monkeypatch.setattr(main_window_module, "confirm_export", lambda *args: dialogs.append(args))
    monkeypatch.setattr(main_window_module, "show_error", lambda *args: dialogs.append(args))
    monkeypatch.setattr(window, "_may_discard", lambda: True)
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    target = tmp_path / "beendet.stl"
    window._start_export(target, "stl")
    worker = window._export_worker
    assert worker is not None
    try:
        assert entered.wait(10)
        if ending == "close":
            event = QCloseEvent()
            window.closeEvent(event)
            assert not event.isAccepted() and not window.isEnabled()
            window._close_retry.stop()
        else:
            window.release(0)
        assert worker.cancelled.is_cancelled
        assert window._export_attempt is None
        monkeypatch.setattr(window, "_progress_idle", lambda: updates.append("progress"))
        monkeypatch.setattr(window, "_update_actions", lambda: updates.append("actions"))
    finally:
        resume.set()
        wait_for_export(window)
    assert not target.exists() and not dialogs and not updates
    assert window._export_worker is None and not window._exporting
    assert not window._progress_states["export"].active


@pytest.mark.parametrize("phase", ["checking", "writing"])
def test_late_export_signals_do_not_touch_a_deleted_window(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    """Der Qt-Abbau beendet Rückrufe, während die Leine den echten Arbeiter weiter hält."""
    import sys

    from shiboken6 import isValid

    entered, resume = threading.Event(), threading.Event()
    failures = []
    real_write = main_window_module.write_plan

    def checking(*args: Any, cancelled: Any, **kwargs: Any) -> list[Finding]:
        if phase == "checking":
            entered.set()
            assert resume.wait(10)
            cancelled.raise_if_cancelled()
        return []

    def writing(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        assert resume.wait(10)
        return real_write(*args, **kwargs)

    monkeypatch.setattr(main_window_module, "check_before_export", checking)
    monkeypatch.setattr(main_window_module, "write_plan", writing)
    monkeypatch.setattr(main_window_module, "show_error", lambda *args: failures.append(args))
    monkeypatch.setattr(sys, "excepthook", lambda *args: failures.append(args))
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    assert window.viewport.wait_for_workers(10_000)
    target = tmp_path / "auslaufend.stl"
    window._start_export(target, "stl")
    worker = window._export_worker
    assert worker is not None
    try:
        assert entered.wait(10)
        window.release(0)
        assert worker.cancelled.is_cancelled is (phase == "checking")
        window.viewport.release_renderer()
        window.deleteLater()
        QApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
        assert not isValid(window) and worker.isRunning()
    finally:
        resume.set()
        assert worker.wait(10_000)
        QApplication.processEvents()
        QApplication.processEvents()
    assert not failures
    assert target.exists() is (phase == "writing")
    assert window._export_worker is None and not window._exporting


@pytest.mark.parametrize("release", [False, True])
def test_export_confirmation_may_deliver_finished_but_cannot_revive_a_released_window(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, release: bool
) -> None:
    """Threadende im Bestätigungsdialog erhält den Auftrag; Fensterende verwirft ihn."""
    monkeypatch.setattr(
        main_window_module,
        "check_before_export",
        lambda *args, **kwargs: [Finding("fit.collision", "warning", "Überschneidung")],
    )

    def confirming(*args: Any) -> bool:
        QApplication.processEvents()
        assert window._export_worker is None
        if release:
            window.release(0)
        return True

    monkeypatch.setattr(main_window_module, "confirm_export", confirming)
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    target = tmp_path / "bestaetigt.stl"
    window._start_export(target, "stl")
    wait_for_export(window)
    assert target.exists() is not release
    assert window._export_worker is None and not window._exporting
    assert window._export_attempt is None


def test_a_retried_export_keeps_its_worker_when_the_previous_thread_finishes(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der echte Wiederholknopf kann vor dem verspäteten finished den nächsten Lauf starten."""
    entered, resume = threading.Event(), threading.Event()
    calls, retried = [], []

    def checking(*args: Any, cancelled: Any, **kwargs: Any) -> list[Finding]:
        calls.append(True)
        if len(calls) == 1:
            raise errors.FileWriteError(target="export.stl", detail="Der Ordner ist belegt.")
        entered.set()
        assert resume.wait(10)
        cancelled.raise_if_cancelled()
        return []

    def retrying(problem: errors.AppError, owner: MainWindow) -> None:
        owner.error_handlers()["retry"](problem)
        retried.append(owner._export_worker)

    monkeypatch.setattr(main_window_module, "check_before_export", checking)
    monkeypatch.setattr(main_window_module, "show_error", retrying)
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    target = tmp_path / "wiederholt.stl"
    window._start_export(target, "stl")
    first = window._export_worker
    assert first is not None
    try:
        assert first.wait(10_000)
        QApplication.processEvents()
        assert entered.wait(10)
        assert len(retried) == 1 and window._export_worker is retried[0]
        assert window._export_worker is not first and window._exporting
        assert window._progress_states["export"].active
    finally:
        resume.set()
        wait_for_export(window)
    assert target.is_file()
    assert window._export_worker is None and not window._exporting


def test_export_closes_cancellation_before_the_first_file_of_a_batch(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein noch nicht zugestelltes Phasensignal erlaubt keinen halben Mehrdateiexport."""
    entered, resume = threading.Event(), threading.Event()
    real_write = main_window_module.write_plan

    def writing(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        assert resume.wait(10)
        return real_write(*args, **kwargs)

    monkeypatch.setattr(main_window_module, "check_before_export", lambda *args, **kwargs: [])
    monkeypatch.setattr(main_window_module, "write_plan", writing)
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    assert window.session.apply(
        "Zweiter Körper", [OperationDraft(op="create_box", params={"x": 60.0})]
    )
    assert window.session.wait_for_idle(30_000)
    window.object_tree.tree.clearSelection()
    window._start_export(tmp_path / "ausgabe.stl", "stl")
    worker = window._export_worker
    assert worker is not None
    try:
        assert entered.wait(10)
        # Das Schreibsignal liegt noch in der Warteschlange; der sichtbare
        # Prüfknopf muss seinen Auftrag trotzdem am aktuellen Zustand prüfen.
        window.cancel_button.click()
        assert not worker.cancelled.is_cancelled
        assert not window.cancel_button.isVisibleTo(window)
    finally:
        resume.set()
        wait_for_export(window)
    assert len(list(tmp_path.glob("*.stl"))) == 2
    assert window._export_worker is None and not window._exporting
    assert window.export_action.isEnabled() and not window.progress.isVisibleTo(window)


def test_a_failed_export_reports_in_the_main_thread(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 17: Was im Arbeiter schiefgeht, wird im Fenster gezeigt — mit
    Handlungsvorschlag, nicht als stiller Ausfall.

    Der ``try/except AppError`` stand um den Code, der jetzt im Arbeiter
    läuft. Fiele er dort ungefangen aus ``run`` heraus, endete der Export
    ohne eine Zeile — und der Menüeintrag bliebe für immer gesperrt.
    """
    from PySide6.QtWidgets import QFileDialog

    from app.ui import main_window as module

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise errors.UserError(
            title="Der Ordner ließ sich nicht beschreiben.",
            detail="Kein Schreibrecht.",
        )

    shown: list[Any] = []
    monkeypatch.setattr(module, "write_plan", refuse)
    monkeypatch.setattr(module, "show_error", lambda error, *args, **kwargs: shown.append(error))
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(tmp_path / "geht_nicht.stl"), "STL (*.stl)")),
    )

    window.action_export()
    wait_for_export(window)

    assert shown, "der Fehler des Arbeiters kam nirgends an"
    assert shown[0].suggestions, "und er trägt keinen Handlungsvorschlag"
    assert window.export_action.isEnabled(), "nach dem Fehlschlag darf man es wieder versuchen"


def test_a_failed_save_offers_both_ways_out(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der datenkritischste Schreibfehler von allen (§2.7, Regel 17).

    Wessen Projekt sich nicht speichern lässt, hat seine Arbeit noch nicht in
    Sicherheit — und bekam einen Dialog mit *Details anzeigen*. Die zwei Fälle,
    die wirklich vorkommen, haben beide eine Antwort: Die Datei liegt in einem
    anderen Programm offen (dann hilft derselbe Weg noch einmal), oder das
    Laufwerk ist voll (dann hilft ein anderer Ort).
    """
    from app.ui import main_window as module
    from app.ui.dialogs import offered_actions

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)

    target = tmp_path / "belegt.p3d"
    attempts: list[Path] = []
    real_save = type(window.session).save_project

    def busy(session: Any, path: Path) -> Path:
        attempts.append(path)
        if len(attempts) == 1:
            raise errors.FileWriteError(target=str(path), detail="Die Datei ist in Benutzung.")
        return real_save(session, path)

    monkeypatch.setattr(type(window.session), "save_project", busy)
    monkeypatch.setattr(module, "show_error", lambda error, *args, **kwargs: None)

    window._save_to(target)

    handlers = window.error_handlers()
    failure = errors.FileWriteError(target=str(target), detail="Die Datei ist in Benutzung.")
    offered = [action.id for action in offered_actions(failure, handlers)]
    assert offered[:2] == ["retry", "save_elsewhere"], offered
    assert "correct_input" not in offered, "an einem Schreibfehler gibt es keine Eingabe"

    # Das andere Programm gibt die Datei frei, der Kunde drückt den Knopf.
    handlers["retry"](failure)

    assert attempts == [target, target], "der zweite Anlauf ging woandershin"
    assert target.is_file(), "gespeichert wurde nicht"
    assert "retry" not in window.error_handlers(), "nach dem Erfolg bleibt nichts offen"


def test_a_failed_save_can_choose_another_place(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der zweite Weg: ein anderer Ort, über den Dialog, den es dafür gibt."""
    from app.ui import main_window as module

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)

    def refuse(session: Any, path: Path) -> Path:
        raise errors.FileWriteError(target=str(path), detail="Kein Platz.")

    monkeypatch.setattr(type(window.session), "save_project", refuse)
    monkeypatch.setattr(module, "show_error", lambda error, *args, **kwargs: None)
    window._save_to(tmp_path / "voll.p3d")

    # Gefragt wird der **Dateidialog** und nicht die Methode: ``_WriteFailure``
    # bindet ``action_save_as`` beim Anlegen, und ein später ersetztes Attribut
    # sähe der Knopf nie — er hätte den echten Dialog geöffnet und den Test
    # offscreen zum Hängen gebracht.
    from PySide6.QtWidgets import QFileDialog

    asked: list[str] = []

    def dialog(*args: Any, **kwargs: Any) -> tuple[str, str]:
        asked.append("gefragt")
        return "", ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(dialog))
    window.error_handlers()["save_elsewhere"](errors.FileWriteError(target="x", detail="y"))

    assert asked == ["gefragt"], "the other-place button does not reach the save dialog"


def test_a_failed_export_can_be_repeated_without_choosing_the_file_again(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die häufigste Ursache ist eine Datei, die im Slicer offen liegt (§2.7).

    ``FileWriteError`` schlägt *Erneut versuchen* vor, und für keine der beiden
    Ausnahmen, die das tun, gab es einen Handler — der Rat stand als Satz im
    Dialog. Wer die Datei im Slicer schloss, musste Format, Ordner und Namen
    ein zweites Mal wählen.

    Geprüft wird beides: dass der Knopf erscheint, sobald es etwas zu
    wiederholen gibt, dass er an denselben Ort schreibt — und dass er
    **verschwindet**, wenn nichts offen ist. Ein Knopf, der nichts tut, ist
    schlimmer als keiner.
    """
    from PySide6.QtWidgets import QFileDialog

    from app.ui import main_window as module
    from app.ui.dialogs import offered_actions

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)

    target = tmp_path / "belegt.stl"
    assert "retry" not in window.error_handlers(), "ohne Fehlschlag gibt es nichts zu wiederholen"

    real_write = module.write_plan
    attempts: list[int] = []

    def busy_file(*args: Any, **kwargs: Any) -> Any:
        attempts.append(1)
        if len(attempts) == 1:
            raise errors.FileWriteError(target=str(target), detail="Die Datei ist in Benutzung.")
        return real_write(*args, **kwargs)

    monkeypatch.setattr(module, "write_plan", busy_file)
    monkeypatch.setattr(module, "show_error", lambda error, *args, **kwargs: None)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "STL (*.stl)")),
    )

    window.action_export()
    wait_for_export(window)

    handlers = window.error_handlers()
    assert "retry" in handlers, "nach dem Fehlschlag fehlt der Wiederholknopf"
    failed = errors.FileWriteError(target=str(target), detail="Die Datei ist in Benutzung.")
    assert "retry" in {action.id for action in offered_actions(failed, handlers)}

    # Der Slicer gibt die Datei frei, der Kunde drückt den Knopf.
    handlers["retry"](failed)
    wait_for_export(window)

    assert target.is_file(), "der zweite Anlauf hat nicht geschrieben"
    assert len(attempts) == 2, "und er hat keinen dritten gebraucht"
    assert "retry" not in window.error_handlers(), (
        "nach dem geschriebenen Export gibt es nichts mehr zu wiederholen"
    )


def test_the_print_settings_open_before_the_layer_analysis(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.8: Der echte Dialog öffnet sofort und analysiert seinen Auftrag im Arbeiter."""
    import time

    from app.ui import main_window as module

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)

    at_open: list[Any] = []
    at_close: list[Any] = []
    analysed: list[set[str]] = []

    class ImmediateDialog(module.PrintSettingsDialog):
        """Statt zu warten: einmal nachsehen, dann die Ereignisse laufen
        lassen, wie es ein offener Dialog auch täte."""

        def exec(self) -> int:
            at_open.append(self.slice_result)
            deadline = time.perf_counter() + 20.0
            while self.slice_result is None and time.perf_counter() < deadline:
                QApplication.processEvents()
            at_close.append(self.slice_result)
            analysed.append(set(self._body_analyses))
            return 0

    monkeypatch.setattr(module, "PrintSettingsDialog", ImmediateDialog)

    window.action_print_settings()

    assert at_open == [None], "der Dialog hat doch auf die Schichtanalyse gewartet"
    assert at_close and at_close[0] is not None, (
        "die Analyse hat den offenen Dialog nie erreicht — genau dafür war das Warten da"
    )
    assert analysed == [set(window.session.last_result.scene.objects)], (
        "der Dialog muss den tatsächlichen Ausgabeumfang selbst analysieren"
    )


def test_closing_the_print_settings_keeps_what_was_changed(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Weg hinaus heißt *Schließen*, und Schließen verwirft nichts.

    Der Dialog schreibt jeden getippten Wert sofort in sein Modell, das Fenster
    übernimmt es nach ``exec`` — auch wenn niemand *Übernehmen* gedrückt hat,
    denn es gibt keines. Das ist die Bauart einer Einstellungsseite und kein
    Versehen: Beim Schließen wird auch die Slicer-Profilwahl festgeschrieben
    (``_remember_slicer_choice``), und die soll gerade nicht verlorengehen.

    **Getragen wird sie allein von der Beschriftung.** Ein Knopf *Abbrechen*
    verspräche hier das Gegenteil dessen, was geschieht; dass dort *Schließen*
    steht, hält ``test_the_close_button_speaks_german`` fest. Dieser Test hält
    die andere Hälfte: dass die Werte den geschlossenen Dialog überleben.
    """
    from app.ui import main_window as module
    from app.ui.labels import BoundedSpin

    class ClosingDialog(module.PrintSettingsDialog):
        """Wie ein Kunde, der einen Wert ändert und das Fenster wieder zumacht."""

        def exec(self) -> int:
            editor = self._editors["shell.wall_count"]
            assert isinstance(editor, BoundedSpin)
            editor.setValue(7)
            self.reject()
            return int(self.result())

    monkeypatch.setattr(module, "PrintSettingsDialog", ClosingDialog)

    window.action_print_settings()

    settings = window.session.project.document.print_settings
    assert settings is not None, "das Fenster hat die Einstellungen gar nicht übernommen"
    assert settings.shell.wall_count == 7, (
        f"nach dem Schließen stehen {settings.shell.wall_count} Wandbahnen statt 7 — "
        "der Knopf heißt „Schließen“ und darf nichts verwerfen"
    )


def test_a_failed_slicer_precheck_reaches_the_main_report(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der neue Rückweg ist in der Anwendung angeschlossen, nicht nur am Dialog."""
    from types import SimpleNamespace

    from PySide6.QtCore import QObject, Signal

    from app.core.knowledge import print_settings
    from app.core.types import Finding
    from app.ui import main_window as module

    before = window.report.list.count()
    finding = Finding(
        code="arrange.out_of_build_volume",
        severity="error",
        message="Das Teil ist größer als der Bauraum.",
    )

    class FailingDialog(QObject):
        """Ersetzt nur die Signale; echte Profil-Worker gehören nicht in den Anschlusstest."""

        sliced = Signal(object)
        reported = Signal(object)
        handedOver = Signal()  # noqa: N815 — bildet das echte Qt-Signal nach
        usage_changed = Signal()
        setupRequested = Signal()  # noqa: N815 - bildet das echte Qt-Signal nach
        filamentsRequested = Signal()  # noqa: N815 - dasselbe für den Weg zu den Spulen

        def __init__(
            self,
            session: Session,
            _ui_settings: UiSettings,
            parent: MainWindow,
            *,
            slice_result: object | None = None,
        ) -> None:
            super().__init__(parent)
            self.slice_result = slice_result
            self.settings = print_settings.resolve(session.profile)
            self.usage_notice = SimpleNamespace(changed=self.usage_changed, requests={})

        def exec(self) -> int:
            self.reported.emit([finding])
            return 0

        def take_scene_action(self) -> None:
            """Die Attrappe meldet nur einen Befund und fordert keine Szenenhandlung an."""
            return None

        def refresh_materials(self) -> None:
            """Was ``_show_filaments`` beim Zurückkommen ruft.

            Heute unerreicht — ``exec`` sendet nur ``reported``. Die Methode
            steht trotzdem hier: Sobald jemand den Weg zum Filamentwähler über
            diese Attrappe fährt, wäre ihr Fehlen ein ``AttributeError``, und
            genau so ist ``filamentsRequested`` eine Zeile weiter oben schon
            einmal aufgeschlagen.
            """

        def has_changes(self) -> bool:
            """Ob dieser Dialog etwas bewirkt hat (§29).

            Und hier ist der Fall, den der Docstring darüber vorhersagt,
            tatsächlich eingetreten: Seit dem 03.09.2026 fragt
            ``action_print_settings`` danach, bevor es die Einstellungen ins
            Projekt schreibt — wer nur nachsieht, soll sein Projekt unberührt
            lassen. Die Attrappe kannte die Methode nicht, und der Test starb
            mit genau dem ``AttributeError``, vor dem oben gewarnt wird.

            ``False``, weil diese Attrappe nichts einstellt: Sie sendet einen
            Befund und geht wieder.
            """
            return False

    monkeypatch.setattr(module, "PrintSettingsDialog", FailingDialog)

    window.action_print_settings()

    assert window.report.list.count() == before + 1
    shown = [
        window.report.list.item(row).data(Qt.ItemDataRole.UserRole).code
        for row in range(window.report.list.count())
    ]
    assert "arrange.out_of_build_volume" in shown


def test_export_as_3mf_carries_every_plate(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei Platten sind eine Datei mit zwei Platten darin.

    Jede Platte fängt am selben Bettursprung an. Ohne Plattenangabe legt die
    Datei die Teile der zweiten über die der ersten; am modularen Besteckkorb
    waren es neunundzwanzig Millimeter Überlappung, gemessen zwischen einem
    Fuß auf Platte eins und einem Modul auf Platte zwei. Der Datei sah man das
    nicht an, und der Slicer hätte sie genommen.
    """
    from PySide6.QtWidgets import QFileDialog

    from app.core.scene import OperationDraft

    for _ in range(2):
        window.session.apply(
            "Anlegen",
            [
                OperationDraft(
                    op="create_box", params={"width": 200.0, "depth": 200.0, "height": 10.0}
                )
            ],
        )
        assert window.session.wait_for_idle(60_000)
    result = window.session.last_result
    assert result is not None
    window.session.apply(
        "Anordnen",
        [
            OperationDraft(
                op="arrange_bed", inputs=tuple(result.scene.objects), params={"plates": 2}
            )
        ],
    )
    assert window.session.wait_for_idle(60_000)

    scene = window.session.last_result
    assert scene is not None
    assert {entry.plate for entry in scene.scene.objects.values()} == {0, 1}, "zwei Platten"

    target = tmp_path / "baugruppe.3mf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "3MF (*.3mf)")),
    )
    window.object_tree.tree.clearSelection()
    window.action_export()
    wait_for_export(window)

    written = sorted(path.name for path in tmp_path.glob("*.3mf"))
    assert written == ["baugruppe.3mf"], "eine Baugruppe, eine Datei"

    import zipfile

    with zipfile.ZipFile(target) as container:
        beilage = container.read("Metadata/model_settings.config").decode("utf-8")
    assert beilage.count("<plate>") == 2, "und darin beide Platten"
    assert 'key="plater_id" value="1"' in beilage
    assert 'key="plater_id" value="2"' in beilage


def test_export_as_3mf_carries_the_print_settings(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine 3MF ohne Einstellungen ist Geometrie, kein Druckauftrag.

    Der Slicer öffnet sie dann mit dem Profil, das gerade eingestellt ist. Was
    das kostet, steht im Projekt Besteckkorb aufgeschrieben: Die Datei sagte
    drei Wände, gedruckt wurden zwei — 127 Gramm Unterschied, und der Datei
    sah man nichts an.
    """
    import zipfile

    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    window.session.import_model(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)

    target = tmp_path / "auftrag.3mf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "3MF (*.3mf)")),
    )
    # Stünden zwei Körper am selben Ort, fragte der Export danach (§29,
    # RM-140); die Antwort steht bereit.
    export_anyway(monkeypatch)
    window.object_tree.tree.clearSelection()
    window.action_export()
    wait_for_export(window)

    with zipfile.ZipFile(target) as container:
        assert "Metadata/project_settings.config" in container.namelist()


def test_export_is_disabled_on_an_empty_scene(window: MainWindow) -> None:
    """Ein Exporteintrag, der auf leerer Szene ein Fenster öffnet, wäre die
    modale Sackgasse aus der Bedienrunde — er ist stattdessen aus."""
    assert not window.export_action.isEnabled()
    assert not window.auto_split_action.isEnabled()
    assert not window.variants_action.isEnabled()


def _asked_dialog(
    monkeypatch: pytest.MonkeyPatch, answer: tuple[str, str]
) -> list[tuple[str, str]]:
    """Merkt sich Vorgabename und Filter des Dateidialogs und antwortet fest."""
    from PySide6.QtWidgets import QFileDialog

    asked: list[tuple[str, str]] = []

    def remember(_parent: object, _title: str, name: str, filters: str) -> tuple[str, str]:
        asked.append((name, filters))
        return answer

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(remember))
    return asked


def test_the_format_of_the_last_export_comes_back(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§29: „Ordner, Format und Übergabeart werden je Projekt gemerkt" (RM-141).

    Der Dialog begann bisher jedes Mal bei 3MF. Wer ein Modell für einen
    Dienstleister pflegt (STL) und daneben ein Gehäuse für den eigenen Slicer
    (3MF), stellte bei jedem Export beides neu ein.
    """
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)

    _asked_dialog(monkeypatch, (str(tmp_path / "wuerfel.stl"), "STL (*.stl)"))
    window.action_export()
    wait_for_export(window)

    assert window.session.project.document.export_format == "stl", "die Wahl steht im Projekt"

    asked = _asked_dialog(monkeypatch, ("", ""))
    window.action_export()

    assert asked, "der Dialog wurde gefragt"
    name, filters = asked[0]
    assert name.endswith(".stl"), f"der Vorschlag folgt der letzten Wahl: {name}"
    assert filters.split(";;", 1)[0] == "STL (*.stl)", "und der erste Filter auch"


@pytest.mark.parametrize("selection", ["mesh", "brep", "all"])
def test_remembered_step_follows_the_current_selection(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, selection: str
) -> None:
    """Eine Netzauswahl bleibt exportierbar, auch wenn das Projekt STEP bevorzugt."""
    assert window.session.apply(
        "Zwei Körper",
        [OperationDraft(op="create_box"), OperationDraft(op="create_brep_box")],
    )
    assert window.session.wait_for_idle(30_000)
    result = window.session.last_result
    assert result is not None
    if selection != "all":
        body = next(entry for entry in result.scene.objects.values() if entry.kind == selection)
        window.object_tree.select_object(body.id)
    window.session.set_export_choice("step", "{index}_{object}")
    asked = _asked_dialog(monkeypatch, ("", ""))

    window.action_export()

    assert len(asked) == 1
    name, filters = asked[0]
    expected = "3MF (*.3mf)" if selection == "mesh" else "STEP (*.step)"
    assert filters.split(";;", 1)[0] == expected
    assert name.endswith(".3mf" if selection == "mesh" else ".step")
    assert ("STEP (*.step)" in filters) == (selection != "mesh")
    assert ("{object}" in name) == (selection == "all")
    assert window.session.project.document.export_format == "step"


def test_two_projects_keep_their_own_choice(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei Projekte, zwei Vorgaben — getrennt gemerkt (RM-141).

    Die Abnahme des Punktes in einem Satz: zwei Projekte mit unterschiedlichen
    Vorgaben wieder öffnen und getrennt korrekt exportieren.
    """
    stl_projekt = tmp_path / "dienstleister.p3d"
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    _asked_dialog(monkeypatch, (str(tmp_path / "teil.stl"), "STL (*.stl)"))
    window.action_export()
    wait_for_export(window)
    window.session.save_project(stl_projekt)

    drei_mf = tmp_path / "gehaeuse.p3d"
    window.session.start_new()
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    _asked_dialog(monkeypatch, (str(tmp_path / "teil.3mf"), "3MF (*.3mf)"))
    window.action_export()
    wait_for_export(window)
    window.session.save_project(drei_mf)

    window.open_path(stl_projekt)
    assert window.session.wait_for_idle(60_000)
    asked = _asked_dialog(monkeypatch, ("", ""))
    window.action_export()
    assert asked[0][0].endswith(".stl"), f"das eine Projekt bleibt bei STL: {asked[0][0]}"

    window.open_path(drei_mf)
    assert window.session.wait_for_idle(60_000)
    asked = _asked_dialog(monkeypatch, ("", ""))
    window.action_export()
    assert asked[0][0].endswith(".3mf"), f"das andere bei 3MF: {asked[0][0]}"


def test_the_naming_scheme_is_offered_and_kept(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Namensschema steht im Namensfeld — dort kann man es ändern (§29, RM-141).

    Der Bauplan sagt „Namensschema bei mehreren Teilen, konfigurierbar". Ein
    eigener Dialog dafür wäre ein zweiter Schritt vor einer Handlung, die
    ohnehin einen hat; der Dateidialog fragt schon nach dem Namen, und bei
    mehreren Dateien **ist** der Name das Muster.
    """
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    window.session.import_model(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(60_000)
    window.session.set_export_choice("stl")
    export_anyway(monkeypatch)

    asked = _asked_dialog(monkeypatch, (str(tmp_path / "{index}_{object}.stl"), "STL (*.stl)"))
    window.action_export()
    wait_for_export(window)

    assert "{object}" in asked[0][0], f"das Muster steht im Vorschlag: {asked[0][0]}"
    geschrieben = sorted(path.name for path in tmp_path.glob("*.stl"))
    assert geschrieben == ["1_Wuerfel.stl", "2_Platte.stl"] or len(geschrieben) == 2, geschrieben
    assert all(name[0].isdigit() for name in geschrieben), (
        f"das getippte Muster hat die Namen gemacht: {geschrieben}"
    )
    assert window.session.project.document.export_scheme == "{index}_{object}", "und es bleibt"


def test_a_plain_name_does_not_become_a_scheme(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Klammern ist ein Name ein Name (RM-141).

    Er darf das gemerkte Muster nicht überschreiben — sonst verlöre es, wer
    einmal einen festen Namen tippt, und bekäme beim nächsten Export wieder
    die Vorgabe.
    """
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    window.session.import_model(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(60_000)
    window.session.set_export_choice("stl", "{index}_{object}")
    export_anyway(monkeypatch)

    _asked_dialog(monkeypatch, (str(tmp_path / "alles.stl"), "STL (*.stl)"))
    window.action_export()
    wait_for_export(window)

    assert window.session.project.document.export_scheme == "{index}_{object}"
    geschrieben = sorted(path.name for path in tmp_path.glob("*.stl"))
    assert all(name.startswith("alles") for name in geschrieben), (
        f"der getippte Name trägt die Dateien: {geschrieben}"
    )


def test_the_export_folder_stays_with_the_machine(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Ordner wird gemerkt — beim Gerät, nicht im Projekt (Regel 12, RM-141).

    Ein absoluter Pfad gehört nicht in eine Projektdatei: Er zeigt auf dem
    zweiten Rechner ins Leere oder, schlimmer, auf einen fremden Ordner.
    Derselbe Schnitt wie beim Slicer-Pfad neben der Übergabeart.
    """
    folder = tmp_path / "ausgabe"
    folder.mkdir()
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)

    _asked_dialog(monkeypatch, (str(folder / "wuerfel.stl"), "STL (*.stl)"))
    window.action_export()
    wait_for_export(window)

    assert window.settings.export_dir(window.session.path) == folder

    asked = _asked_dialog(monkeypatch, ("", ""))
    window.action_export()

    assert asked[0][0].startswith(str(folder)), f"der Dialog beginnt dort: {asked[0][0]}"
