"""Druckeinstellungen und Übergabe an den Slicer (Bauplan §29, §2.4).

Der Dialog, der den Wechsel ins andere Programm ersetzt. Vorn steht, was man
wirklich ändert — Qualität, Füllung, Stützen, Farbe —, hinter „Weitere
Einstellungen" liegt der Rest, nach Gebieten sortiert (§2.4, gestufte Tiefe).

Die Felder kommen aus :data:`FIELDS`, einer Tabelle: eine neue Einstellung im
Kernmodell kostet hier eine Zeile und keinen Eingriff. Titel und Einheiten
stehen bewusst hier und nicht im Kern — es sind Oberflächentexte, sie gehen
durch ``tr()``, und der Kern kennt keine Beschriftungen.

Was die Geometrie selbst verlangt, steht darunter als Liste mit Begründung
(:mod:`app.core.slice.advise`). Übernommen wird auf Klick, nie von allein:
ein Vorschlag, der sich still anwendet, ist eine Einstellung, die der Nutzer
nicht getroffen hat.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core import discover, tools
from app.core.errors import AppError, OperationCancelled
from app.core.export import handover, slicer_keys, slicer_profiles, threemf
from app.core.export.slicer_keys import SlicerFlavour
from app.core.export.writer import arrangement_holds, write_assembly
from app.core.geom.mesh import as_mesh_data
from app.core.knowledge import print_settings, profiles
from app.core.log import get_logger
from app.core.scene.cancel import CancelSignal
from app.core.slice import advise, gcode
from app.core.types import (
    BoundingBox,
    Finding,
    MaterialSlot,
    PrintSettings,
    Profile,
    SceneObject,
    SettingAdvice,
    SliceResult,
)
from app.i18n import tr
from app.ui.dialogs import show_error
from app.ui.labels import by_title, colour_name
from app.ui.leash import WorkerLeash
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.style import make_primary

_log = get_logger(__name__)

FieldKind = Literal["float", "int", "bool", "enum", "colour"]


@dataclass(frozen=True, slots=True)
class Field:
    """Eine Zeile im Dialog. ``group`` ist der Reiter, ``front`` hebt sie nach
    vorn."""

    path: str
    title: str
    group: str
    kind: FieldKind = "float"
    unit: str = ""
    minimum: float = 0.0
    maximum: float = 1000.0
    step: float = 0.1
    decimals: int = 2
    choices: tuple[str, ...] = ()
    front: bool = False
    factor: float = 1.0
    """Anzeige geteilt durch Modellwert. Der Kern rechnet Anteile in 0…1, die
    Werkstatt spricht in Prozent — ein Feld mit ``[%]`` und einer 0,15 darin
    ist schlicht falsch beschriftet (§19.3)."""


#: Operationen, die eine Passung **herstellen**, ohne sie einzutragen.
#:
#: Jede von ihnen legt zwei Flächen mit einem gerechneten Spiel aufeinander —
#: aus dem Materialprofil oder der Normteiltabelle. Für den Druck heißt das
#: dasselbe wie eine eingetragene Passung: die Außenwand muss auf Maß, und
#: schnell darf sie dabei nicht sein.
FITTING_OPS: frozenset[str] = frozenset(
    {
        "create_lid",
        "screw_lid",
        "split_pinned",
        "insert_snap_fit",
        "insert_dowel",
        "insert_magnet_pocket",
        "insert_heatset_m4",
        "insert_nut_trap",
        "insert_printed_thread",
        "thread_exact",
    }
)

#: Gruppen in der Reihenfolge, in der sie erscheinen.
GROUPS = ("layers", "shell", "infill", "temperature", "cooling", "speed", "support", "other")


def group_title(group: str) -> str:
    return {
        "layers": tr("Schichten"),
        "shell": tr("Wände"),
        "infill": tr("Füllung"),
        "temperature": tr("Temperaturen"),
        "cooling": tr("Kühlung"),
        "speed": tr("Geschwindigkeit"),
        "support": tr("Stützen"),
        "other": tr("Haftung, Rückzug, Filament"),
    }.get(group, group)


#: Aufzählungswerte in Worten. Der gespeicherte Wert bleibt englisch — er geht
#: in die Projektdatei und zum Slicer —, gezeigt wird die Übersetzung (§4.1).
CHOICE_LABELS: dict[str, str] = {
    "grid": tr("Gitter"),
    "gyroid": tr("Gyroid"),
    "honeycomb": tr("Wabe"),
    "cubic": tr("Würfel"),
    "lines": tr("Linien"),
    "triangles": tr("Dreiecke"),
    "none": tr("Keine"),
    "tree": tr("Baum"),
    "everywhere": tr("Überall"),
    "build_plate": tr("Nur von der Platte"),
    "aligned": tr("Ausgerichtet"),
    "nearest": tr("Nächstgelegen"),
    "random": tr("Zufällig"),
    "rear": tr("Hinten"),
    "skirt": tr("Skirt"),
    "brim": tr("Brim"),
    "raft": tr("Raft"),
}


def choice_label(value: str) -> str:
    return CHOICE_LABELS.get(value, value)


FIELDS: tuple[Field, ...] = (
    # --- Schichten ---
    Field(
        "layers.layer_height",
        tr("Schichthöhe"),
        "layers",
        unit="mm",
        minimum=0.02,
        maximum=1.2,
        step=0.02,
        decimals=3,
        front=True,
    ),
    Field(
        "layers.first_layer_height",
        tr("Erste Schicht"),
        "layers",
        unit="mm",
        minimum=0.02,
        maximum=1.2,
        step=0.02,
        decimals=3,
    ),
    Field(
        "layers.line_width",
        tr("Linienbreite"),
        "layers",
        unit="mm",
        minimum=0.1,
        maximum=2.0,
        step=0.02,
        decimals=3,
    ),
    Field(
        "layers.first_layer_line_width",
        tr("Linienbreite erste Schicht"),
        "layers",
        unit="mm",
        minimum=0.1,
        maximum=2.0,
        step=0.02,
        decimals=3,
    ),
    # --- Wände ---
    Field("shell.wall_count", tr("Wände"), "shell", kind="int", minimum=1, maximum=20, front=True),
    Field("shell.top_layers", tr("Deckschichten"), "shell", kind="int", minimum=0, maximum=50),
    Field("shell.bottom_layers", tr("Bodenschichten"), "shell", kind="int", minimum=0, maximum=50),
    Field("shell.outer_wall_first", tr("Außenwand zuerst"), "shell", kind="bool"),
    Field(
        "shell.seam_position",
        tr("Naht"),
        "shell",
        kind="enum",
        choices=("aligned", "nearest", "random", "rear"),
    ),
    Field(
        "shell.wall_generator",
        tr("Wandbahnen"),
        "shell",
        kind="enum",
        choices=("classic", "arachne"),
    ),
    Field("shell.precise_outer_wall", tr("Außenwand auf Sollmaß"), "shell", kind="bool"),
    Field("shell.ironing", tr("Oberfläche bügeln"), "shell", kind="bool"),
    # --- Füllung ---
    Field(
        "infill.density",
        tr("Fülldichte"),
        "infill",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
        front=True,
    ),
    Field(
        "infill.pattern",
        tr("Füllmuster"),
        "infill",
        kind="enum",
        choices=("grid", "gyroid", "honeycomb", "cubic", "lines", "triangles"),
        front=True,
    ),
    Field(
        "infill.angle",
        tr("Füllwinkel"),
        "infill",
        unit="°",
        minimum=0.0,
        maximum=180.0,
        step=5.0,
        decimals=1,
    ),
    # --- Temperaturen ---
    Field(
        "temperature.nozzle",
        tr("Düse"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=400,
        front=True,
    ),
    Field(
        "temperature.nozzle_first_layer",
        tr("Düse, erste Schicht"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=400,
    ),
    Field(
        "temperature.bed",
        tr("Bett"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=150,
        front=True,
    ),
    Field(
        "temperature.bed_first_layer",
        tr("Bett, erste Schicht"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=150,
    ),
    Field(
        "temperature.chamber",
        tr("Kammer"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=90,
    ),
    # --- Kühlung ---
    Field(
        "cooling.fan_speed",
        tr("Lüfter"),
        "cooling",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
    ),
    Field(
        "cooling.bridge_fan_speed",
        tr("Lüfter bei Brücken"),
        "cooling",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
    ),
    Field(
        "cooling.disable_first_layers",
        tr("Lüfter aus für Schichten"),
        "cooling",
        kind="int",
        minimum=0,
        maximum=20,
    ),
    Field(
        "cooling.minimum_layer_time",
        tr("Mindestzeit je Schicht"),
        "cooling",
        unit="s",
        minimum=0.0,
        maximum=120.0,
        step=1.0,
        decimals=0,
    ),
    # --- Geschwindigkeit ---
    Field(
        "speed.outer_wall",
        tr("Außenwand"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
    ),
    Field(
        "speed.inner_wall",
        tr("Innenwand"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
    ),
    Field(
        "speed.infill",
        tr("Füllung"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
    ),
    Field(
        "speed.top_surface",
        tr("Oberfläche"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
    ),
    Field(
        "speed.first_layer",
        tr("Erste Schicht"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
    ),
    Field(
        "speed.travel",
        tr("Leerfahrt"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=10.0,
        decimals=0,
    ),
    Field(
        "speed.bridge",
        tr("Brücken"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=200.0,
        step=5.0,
        decimals=1,
    ),
    Field(
        "speed.acceleration",
        tr("Beschleunigung"),
        "speed",
        unit="mm/s²",
        minimum=100.0,
        maximum=30000.0,
        step=500.0,
        decimals=0,
    ),
    Field(
        "speed.outer_wall_acceleration",
        tr("Beschleunigung Außenwand"),
        "speed",
        unit="mm/s²",
        minimum=100.0,
        maximum=30000.0,
        step=500.0,
        decimals=0,
    ),
    # --- Stützen ---
    Field(
        "support.style",
        tr("Stützen"),
        "support",
        kind="enum",
        choices=("none", "grid", "tree"),
        front=True,
    ),
    Field(
        "support.placement",
        tr("Stützen ansetzen"),
        "support",
        kind="enum",
        choices=("everywhere", "build_plate"),
    ),
    Field(
        "support.threshold_angle",
        tr("Ab Winkel"),
        "support",
        unit="°",
        minimum=0.0,
        maximum=90.0,
        step=5.0,
        decimals=1,
    ),
    Field(
        "support.z_gap",
        tr("Abstand nach oben"),
        "support",
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        step=0.05,
        decimals=2,
    ),
    Field(
        "support.xy_gap",
        tr("Abstand zur Seite"),
        "support",
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        step=0.1,
        decimals=2,
    ),
    Field(
        "support.density",
        tr("Stützdichte"),
        "support",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
    ),
    Field(
        "support.interface_layers",
        tr("Trennschichten"),
        "support",
        kind="int",
        minimum=0,
        maximum=10,
    ),
    # --- Haftung, Rückzug, Filament ---
    Field(
        "adhesion.kind",
        tr("Plattenhaftung"),
        "other",
        kind="enum",
        choices=("none", "skirt", "brim", "raft"),
    ),
    Field("adhesion.skirt_loops", tr("Skirt-Runden"), "other", kind="int", minimum=0, maximum=20),
    Field(
        "adhesion.skirt_distance",
        tr("Skirt-Abstand"),
        "other",
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        step=0.5,
        decimals=1,
    ),
    Field(
        "adhesion.brim_width",
        tr("Brim-Breite"),
        "other",
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        step=0.5,
        decimals=1,
    ),
    Field("adhesion.raft_layers", tr("Raft-Schichten"), "other", kind="int", minimum=0, maximum=20),
    Field(
        "retraction.length",
        tr("Rückzug"),
        "other",
        unit="mm",
        minimum=0.0,
        maximum=10.0,
        step=0.1,
        decimals=2,
    ),
    Field(
        "retraction.speed",
        tr("Rückzugstempo"),
        "other",
        unit="mm/s",
        minimum=1.0,
        maximum=200.0,
        step=5.0,
        decimals=0,
    ),
    Field(
        "retraction.z_hop",
        tr("Z-Sprung"),
        "other",
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        step=0.05,
        decimals=2,
    ),
    Field("retraction.wipe", tr("Abstreifen"), "other", kind="bool"),
    Field("retraction.avoid_crossing_walls", tr("Wände nicht überfahren"), "other", kind="bool"),
    Field("filament.colour", tr("Farbe"), "other", kind="colour", front=True),
    Field(
        "filament.diameter",
        tr("Filamentdurchmesser"),
        "other",
        unit="mm",
        minimum=1.0,
        maximum=4.0,
        step=0.05,
        decimals=2,
    ),
    Field(
        "filament.density",
        tr("Dichte"),
        "other",
        unit="g/cm³",
        minimum=0.5,
        maximum=3.0,
        step=0.01,
        decimals=2,
    ),
    Field(
        "filament.flow_ratio",
        tr("Flussfaktor"),
        "other",
        minimum=0.5,
        maximum=1.5,
        step=0.01,
        decimals=3,
    ),
    Field(
        "filament.max_flow",
        tr("Höchster Volumenstrom"),
        "other",
        unit="mm³/s",
        minimum=0.5,
        maximum=60.0,
        step=0.5,
        decimals=1,
    ),
    Field(
        "filament.cost_per_kg",
        tr("Preis je Kilogramm"),
        "other",
        minimum=0.0,
        maximum=1000.0,
        step=1.0,
        decimals=2,
    ),
)


def _select_data(box: QComboBox, identifier: str) -> None:
    """Wählt den Eintrag mit dieser Kennung, wenn es ihn gibt."""
    index = box.findData(identifier)
    if index >= 0:
        box.setCurrentIndex(index)


def remembered_setup(settings: UiSettings, material: str = "") -> handover.SlicerSetup | None:
    """Der Slicer, wie er hier zuletzt eingestellt war (§29).

    Für alle, die eine Datei schreiben, ohne diesen Dialog geöffnet zu haben —
    allen voran der Export im Menü. Ohne ein Setup trägt eine 3MF zwar Solidons
    eigene Werte, aber kein Druckerprofil; der Slicer behält dann das gerade
    eingestellte, und dessen Düse muss zu unserer Schichthöhe nicht passen. Bei
    einer 0,2er Düse und 0,25 mm erster Schicht endet das in „Schichthöhe darf
    den Düsendurchmesser nicht überschreiten" — eine Meldung über das Modell,
    die keine über das Modell ist.

    ``material`` löst das Filament auf, wie der Dialog selbst es tut: je
    Material zuerst, das globale nur als Rückfall. Ohne das trüge ein
    TPU-Projekt nach einem PETG-Lauf das PETG-Profil — richtig gerechnet,
    falsch beschriftet.

    ``None``, solange kein Druckerprofil gemerkt ist: Die Suche nach dem
    Programm geht über PATH, Registry und die üblichen Orte und kostet eine
    halbe Sekunde. Wer den Slicer nie eingerichtet hat, bekäme dafür ein Setup
    ohne Maschine — also nichts, was die Kette auflösen könnte.
    """
    if not settings.slicer_machine_profile:
        return None
    found = discover.find_program("slicer", tools.SLICERS)
    if found is None:
        return None
    try:
        setup = handover.detect(found)
    except AppError:
        # Ein unbekanntes Programm ist hier kein Fehler, sondern eine
        # Auskunft weniger: geschrieben wird trotzdem, nur ohne Systemprofil.
        return None
    filament = (
        settings.slicer_filament_per_material.get(material, settings.slicer_base_filament)
        if material
        else settings.slicer_base_filament
    )
    return replace(
        setup,
        machine_profile=settings.slicer_machine_profile,
        base_process=settings.slicer_base_process,
        base_filament=filament,
    )


class _ColourButton(QPushButton):
    """Farbwahl, die ihren Wert auch schreibt.

    Regel 18: die Farbe allein trägt die Bedeutung nicht — der Hexwert steht
    auf dem Knopf, damit die Angabe auch ohne Farbwahrnehmung ablesbar und
    vorlesbar bleibt.
    """

    changed = Signal(str)

    def __init__(self, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = value
        self._refresh()
        self.clicked.connect(self._choose)

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        self._value = value
        self._refresh()

    def _refresh(self) -> None:
        colour = QColor(self._value)
        readable = "#000000" if colour.lightnessF() > 0.55 else "#ffffff"
        # Der Name, nicht der Hexwert: „#4A90D9" beschreibt für niemanden eine
        # Spule im Regal. Was Qt nicht benennen kann, behält seine Zahl — dann
        # ist sie das Genaueste, was zu haben ist.
        self.setText(colour_name(self._value))
        self.setToolTip(self._value.upper())
        self.setStyleSheet(f"background-color: {self._value}; color: {readable};")

    def _choose(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._value), self, tr("Filamentfarbe"))
        if chosen.isValid():
            self.set_value(chosen.name())
            self.changed.emit(self._value)


@dataclass(frozen=True, slots=True)
class PlateRun:
    """Eine Druckplatte, wie sie in den Slicer geht.

    Der Auftrag ist die **Liste** dieser Läufe, nicht einer davon: eine Szene
    mit mehr Teilen, als auf ein Bett passen, ist der Normalfall (§25), und ein
    Auftrag, von dem nur die erste Platte geslicet wird, ist kein Auftrag,
    sondern eine Teilmenge, über die niemand entschieden hat.
    """

    plate: int
    model: Path
    slots: tuple[MaterialSlot, ...] = ()
    keep_arrangement: bool = False
    findings: tuple[Finding, ...] = ()
    """Was beim Schreiben der Baugruppe auffiel — Haftungsränder,
    Filamentwechsel. Sie reisen mit ihrer Platte, damit im Prüfbericht steht,
    welche gemeint ist."""


class _SliceWorker(QThread):
    """Die Slicer-Läufe abseits der Ereignisschleife (§2.8).

    Ein Teil mit vielen Schichten beschäftigt den Slicer Minuten. Im
    Qt-Hauptthread hieße das ein eingefrorenes Fenster samt der Fortschritts-
    zeile, die davon berichten soll.

    **Eine Platte ist ein Lauf.** Der Slicer schreibt je Aufruf eine Druckdatei,
    und mehr wäre auch nicht richtig: Wer zwei Platten druckt, legt zweimal
    Filament ein und drückt zweimal Start. Dass alle drei Slicer-Familien
    denselben Weg gehen, ist der zweite Grund — die Orca-Familie könnte mehrere
    Platten in einer Projektdatei führen, Cura und PrusaSlicer nicht.
    """

    done = Signal(object)
    failed = Signal(object)
    step = Signal(int, int)
    """Welche Platte gerade läuft und wie viele es sind — beide ab eins gezählt,
    denn diese Zahl steht in der Statuszeile."""

    def __init__(
        self,
        runs: Sequence[PlateRun],
        settings: PrintSettings,
        profile: Profile,
        setup: handover.SlicerSetup,
    ) -> None:
        super().__init__()
        self._runs = list(runs)
        self._settings = settings
        self._profile = profile
        self._setup = setup
        self.cancelled = CancelSignal()
        """Der Schalter zum Abbrechen-Knopf (§2.8): Der Kern-Lauf fragt ihn ab
        und beendet den Kindprozess — vorher lief der Slicer, bis er fertig
        war, gleich was der Nutzer wollte."""

    def cancel(self) -> None:
        """Bricht den laufenden und alle weiteren Läufe ab."""
        self.cancelled.cancel()

    def run(self) -> None:
        results: list[handover.SliceOutcome] = []
        for index, entry in enumerate(self._runs, start=1):
            if self.cancelled.is_cancelled:
                return
            self.step.emit(index, len(self._runs))
            try:
                outcome = handover.slice_model(
                    [entry.model],
                    self._settings,
                    self._profile,
                    self._setup,
                    keep_arrangement=entry.keep_arrangement,
                    slots=entry.slots,
                    cancelled=self.cancelled,
                )
            except OperationCancelled:
                # Kein Fehler und nie als einer gezeigt (§15.6): der Nutzer
                # hat abgebrochen, und das Aufräumen macht `finished`.
                return
            except AppError as problem:
                # Eine Platte, die scheitert, nimmt den Auftrag mit: Was danach
                # käme, wäre eine Sammlung von Druckdateien, in der eine fehlt —
                # und wer sie hinterher an den Drucker gibt, merkt das nicht.
                self.failed.emit(problem)
                return
            outcome.findings = [*entry.findings, *outcome.findings]
            results.append(outcome)
        self.done.emit(results)


class _ProfileWorker(QThread):
    """Den Profilbestand des Slicers durchsehen, ohne den Dialog aufzuhalten.

    Ein ausgelieferter Bestand hat einige tausend Dateien; sie zu lesen dauert
    unter einer Sekunde, aber im Qt-Hauptthread wäre das eine Sekunde, in der
    das Fenster nicht erscheint. Es erscheint sofort, und die Auswahl füllt
    sich nach (§2.8).
    """

    done = Signal(object)

    def __init__(self, executable: Path, flavour: SlicerFlavour) -> None:
        super().__init__()
        self._executable = executable
        self._flavour = flavour

    def run(self) -> None:
        try:
            self.done.emit(
                slicer_profiles.find_profiles(
                    self._executable,
                    self._flavour,
                    # Filamente gehören dazu: ohne sie weiß der Slicer nur
                    # „PETG" und nicht, welches — und fährt für alles, was
                    # Solidon nicht setzt, seine eigene Voreinstellung.
                    kinds=("machine", "process", "filament"),
                )
            )
        except OSError as problem:
            # Ein unlesbarer Profilordner ist kein Grund, den Dialog zu
            # verlieren — die Auswahl bleibt dann eben leer.
            _log.warning("could not read slicer profiles: %s", problem)
            self.done.emit([])


class PrintSettingsDialog(QDialog):
    """Alle Druckeinstellungen, die Vorschläge dazu, und der Weg zum G-Code."""

    sliced = Signal(object)
    """Die Befunde des Laufs, für den Prüfbericht des Fensters."""

    def __init__(
        self,
        session: Session,
        ui_settings: UiSettings,
        parent: QWidget | None = None,
        slice_result: SliceResult | None = None,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.ui_settings = ui_settings
        self.slice_result = slice_result
        """Die Schichtanalyse, wenn das Fenster schon eine hat. Ohne sie bleiben
        die Vorschläge, die aus Material und Maschine folgen (§29)."""
        self.setWindowTitle(tr("Druckeinstellungen"))
        self.setMinimumSize(560, 640)

        self._editors: dict[str, QWidget] = {}
        self._fields: dict[str, Field] = {}
        self._loading = False
        self._worker: _SliceWorker | None = None
        self._profile_worker: _ProfileWorker | None = None
        self._leash = WorkerLeash(self)
        """Hält ausgelaufene Arbeiter, bis Qt mit ihnen durch ist — das
        Warum steht in :mod:`app.ui.leash`."""
        self._profiles: list[slicer_profiles.SlicerProfile] = []
        self._temporary: TemporaryDirectory[str] | None = None
        self._gcode: list[Path] = []
        """Die Druckdateien des letzten Laufs — eine je Platte."""
        self._pending_findings: list[Finding] = []
        """Was die Prüfung vor dem Schreiben fand (§29). Sie berichtet, sie
        blockiert nicht — also reist sie mit dem Ergebnis in den Prüfbericht."""
        # Was das Projekt mitbringt, gilt: eine Dichtung aus TPU bleibt eine
        # Dichtung aus TPU, auch wenn dazwischen anderes gedruckt wurde (§29).
        # Erst ohne eigene Einstellungen wird aus Stufe, Material und Drucker
        # aufgelöst.
        stored = session.project.document.print_settings
        self.settings = stored or print_settings.resolve(
            session.profile, self._remembered_quality()
        )
        # Einmal suchen, dreimal gebraucht: die Suche geht über PATH,
        # Registry und die üblichen Installationsorte und kostet eine halbe
        # Sekunde — dreimal wäre die Hälfte der Zeit, die der Dialog zum
        # Aufgehen braucht.
        self._slicer_path = discover.find_program("slicer", tools.SLICERS)

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_head())
        layout.addWidget(self._build_front())
        layout.addWidget(self._build_tabs(), 1)
        layout.addWidget(self._build_slicer())
        layout.addWidget(self._build_advice())
        layout.addWidget(self._build_state())
        layout.addWidget(self._build_buttons())

        self._load_into_editors()
        self._refresh_advice()
        self._start_profile_search()

    # --- Aufbau ---------------------------------------------------------------

    def _remembered_quality(self) -> Any:
        stored = self.ui_settings.print_quality
        known = print_settings.quality_presets()
        return stored if stored in known else print_settings.DEFAULT_QUALITY

    def _build_head(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.quality = QComboBox(self)
        for key, title in print_settings.quality_presets().items():
            self.quality.addItem(title, key)
        index = self.quality.findData(self.settings.quality)
        if index >= 0:
            self.quality.setCurrentIndex(index)
        self.quality.currentIndexChanged.connect(self._quality_changed)

        # Drucker und Material standen hier als Beschriftung — und es gab
        # nirgends einen Weg, sie zu ändern. Wer eine fremde Datei öffnete,
        # arbeitete für immer gegen deren Bauraum (§12).
        document = self.session.project.document
        self.printer_choice = QComboBox(self)
        for key, entry in by_title(profiles.printer_profiles()):
            self.printer_choice.addItem(str(entry.title), key)
        _select_data(self.printer_choice, document.printer or profiles.DEFAULT_PRINTER)
        self.printer_choice.currentIndexChanged.connect(self._scene_profile_changed)

        self.material_choice = QComboBox(self)
        for key, material in by_title(profiles.material_profiles()):
            self.material_choice.addItem(str(material.title), key)
        _select_data(self.material_choice, document.material or profiles.DEFAULT_MATERIAL)
        self.material_choice.currentIndexChanged.connect(self._scene_profile_changed)

        row.addWidget(QLabel(tr("Qualität"), self))
        row.addWidget(self.quality, 1)
        row.addWidget(QLabel(tr("Drucker"), self))
        row.addWidget(self.printer_choice, 1)
        row.addWidget(QLabel(tr("Material"), self))
        row.addWidget(self.material_choice, 1)
        return row

    def _scene_profile_changed(self) -> None:
        """Ein anderer Drucker heißt andere Vorgaben — und eine Neuauswertung.

        Sofort statt beim Schließen: die Vorschläge in diesem Dialog hängen an
        Maschine und Material, und sie stehen lassen, während oben etwas
        anderes gewählt ist, wäre eine Anzeige, die nicht mehr stimmt.
        """
        self.session.change_scene_profile(
            str(self.printer_choice.currentData()), str(self.material_choice.currentData())
        )
        self.settings = print_settings.resolve(self.session.profile, self.settings.quality)
        self._load_into_editors()
        self._refresh_advice()

    def _build_front(self) -> QWidget:
        box = QGroupBox(tr("Das Wichtigste"), self)
        form = QFormLayout(box)
        for field in FIELDS:
            if field.front:
                form.addRow(self._label(field), self._editor(field))
        return box

    def _build_tabs(self) -> QWidget:
        box = QGroupBox(tr("Weitere Einstellungen"), self)
        box.setCheckable(True)
        box.setChecked(False)
        outer = QVBoxLayout(box)

        self.tabs = QTabWidget(box)
        for group in GROUPS:
            page = QWidget(self.tabs)
            form = QFormLayout(page)
            for field in FIELDS:
                if field.group == group and not field.front:
                    form.addRow(self._label(field), self._editor(field))
            area = QScrollArea(self.tabs)
            area.setWidget(page)
            area.setWidgetResizable(True)
            self.tabs.addTab(area, group_title(group))
        outer.addWidget(self.tabs)
        self.tabs.setVisible(False)
        box.toggled.connect(self._unfold_tabs)
        return box

    def _unfold_tabs(self, open_now: bool) -> None:
        """Zugeklappt bekommt die Gruppe auch keinen Platz mehr.

        Das Register verschwand schon vorher; sein Rahmen behielt aber den
        Dehnungsfaktor und damit den ganzen freien Raum des Dialogs — ein
        leerer Kasten, in dem nichts stand.
        """
        self.tabs.setVisible(open_now)
        layout = self.layout()
        box = self.tabs.parentWidget()
        if isinstance(layout, QVBoxLayout) and box is not None:
            layout.setStretch(layout.indexOf(box), 1 if open_now else 0)
        self.adjustSize()

    def _build_slicer(self) -> QWidget:
        """Auf welche Profile des Slicers Solidon seine Werte legt (§29).

        Zwei Auswahlen, aber im Regelfall keine Entscheidung: das
        Maschinenprofil sagt selbst, welchen Drucker und welche Düse es meint,
        und benennt sein Standard-Prozessprofil. Getroffen wird beides
        automatisch — hier steht es, damit man abweichen kann, nicht damit man
        muss.
        """
        self.slicer_box = QGroupBox(tr("Profile des Slicers"), self)
        self.slicer_box.setCheckable(True)
        self.slicer_box.setChecked(False)
        form = QFormLayout(self.slicer_box)

        self.machine_choice = QComboBox(self.slicer_box)
        self.machine_choice.setEnabled(False)
        self.machine_choice.currentIndexChanged.connect(self._machine_chosen)
        self.process_choice = QComboBox(self.slicer_box)
        self.process_choice.setEnabled(False)
        self.filament_choice = QComboBox(self.slicer_box)
        self.filament_choice.setEnabled(False)
        self.filament_choice.activated.connect(self._filament_chosen)
        """``activated`` und nicht ``currentIndexChanged``: das eine meint die
        Wahl eines Menschen, das andere jedes Befüllen der Liste. Der
        Unterschied entscheidet, ob die Werte eines geladenen Projekts
        überschrieben werden — sie dürfen es nicht."""

        form.addRow(tr("Drucker"), self.machine_choice)
        form.addRow(tr("Grundprofil"), self.process_choice)
        form.addRow(tr("Filament"), self.filament_choice)

        # Je Materialslot eine Zeile — aber nur, wenn es mehr als einen gibt.
        # Ein einfarbiges Teil hat eine Farbe und braucht keine Liste darüber;
        # die Zeile „Filament" oben ist dann die ganze Aussage (§2.4).
        self.slot_rows: list[tuple[QLabel, QComboBox]] = []
        self.slot_form = form
        self._build_slot_rows(form)
        self.profile_note = QLabel(tr("Der Profilbestand wird durchgesehen …"), self.slicer_box)
        self.profile_note.setWordWrap(True)
        form.addRow(self.profile_note)
        return self.slicer_box

    def _start_profile_search(self) -> None:
        found = self._slicer_path
        if found is None:
            self.slicer_box.setVisible(False)
            return
        try:
            flavour = handover.detect(found).flavour
        except AppError:
            self.slicer_box.setVisible(False)
            return
        if flavour == "prusa":
            # §29: eine PrusaSlicer-ini läuft eigenständig, sobald Düse und
            # Bettform darin stehen — und die schreibt Solidon selbst.
            self.profile_note.setText(
                tr(
                    "Dieser Slicer braucht kein Grundprofil — Solidon schreibt eine vollständige "
                    "Konfiguration."
                )
            )
            return
        if flavour == "cura":
            # CuraEngine hat keinen wählbaren Profilbestand: seine Ordner
            # heißen definitions, variants und quality — `find_profiles`
            # fände strukturell nichts. Der Kern beschreibt die Maschine
            # selbst (`_machine_keys`) und nimmt die mitgelieferte Definition
            # (`_cura_base`). Vorher lief die Suche, fand null, und der
            # Türsteher in `_slice` verlangte eine Wahl aus einer leeren
            # Liste — ein Fehler ohne Ausweg (Regel 17, §2.7).
            self.profile_note.setText(
                tr("Dieser Slicer braucht kein Profil — Solidon beschreibt die Maschine selbst.")
            )
            return

        worker = _ProfileWorker(found, flavour)
        worker.done.connect(self._profiles_found)
        worker.finished.connect(self._profile_search_finished)
        self._profile_worker = worker
        worker.start()

    def _profiles_found(self, found: list[slicer_profiles.SlicerProfile]) -> None:
        self._profiles = found
        machines = slicer_profiles.machines(found)
        if not machines:
            self.profile_note.setText(
                tr("Keine Profile gefunden — ohne sie lehnt dieser Slicer den Auftrag ab.")
            )
            return

        self.machine_choice.blockSignals(True)
        for entry in machines:
            self.machine_choice.addItem(entry.title(tr("eigenes")), str(entry.path))
        self.machine_choice.blockSignals(False)
        self.machine_choice.setEnabled(True)
        self.process_choice.setEnabled(True)
        self.filament_choice.setEnabled(True)

        chosen, process = slicer_profiles.match(found, self.session.profile.printer)
        remembered = self.ui_settings.slicer_machine_profile
        index = self.machine_choice.findData(remembered) if remembered else -1
        if index < 0 and chosen is not None:
            index = self.machine_choice.findData(str(chosen.path))
        # **Kein Rückfall auf den ersten Eintrag.** Der war „Afinia H+1(HS) 0.4
        # nozzle" — der erste des installierten Bestands, und mit ihm hätte
        # gesliced, wer den Hinweis darunter überliest. Passt nichts, steht
        # hier nichts; leer ist eine ehrliche Antwort, ein fremder Drucker
        # nicht.
        #
        # Ausnahme: steht genau einer zur Wahl, ist er die Wahl. Eine Liste mit
        # einem Eintrag leer zu lassen wäre keine Vorsicht, sondern ein
        # zusätzlicher Klick ohne Entscheidung.
        if index < 0 and len(machines) == 1:
            index = 0
        self.machine_choice.setCurrentIndex(index)
        self._fill_processes(process)

        if chosen is None:
            self.profile_note.setText(
                tr("Zu diesem Drucker passt kein Profil von selbst — bitte auswählen.")
            )
            self.slicer_box.setChecked(True)
        else:
            self.profile_note.setText(
                tr(
                    "Automatisch zugeordnet. Was hier steht, bringt der Slicer mit; Solidon legt "
                    "seine Werte darauf."
                )
            )

    def _machine_chosen(self) -> None:
        if self._profiles:
            self._fill_processes(None)

    def _current_machine(self) -> slicer_profiles.SlicerProfile | None:
        wanted = self.machine_choice.currentData()
        return next((entry for entry in self._profiles if str(entry.path) == wanted), None)

    def _fill_processes(self, preferred: slicer_profiles.SlicerProfile | None) -> None:
        """Nur die Prozessprofile, die zum gewählten Drucker passen.

        Ohne die Einschränkung stünden hier zweitausend Einträge, von denen
        einer stimmt — und der Slicer lehnte jeden anderen ab, ohne zu sagen,
        warum.
        """
        machine = self._current_machine()
        # Ohne gewählten Drucker bleibt die Liste leer statt vollständig. Ein
        # Grundprofil ohne Drucker gibt es nicht — zweitausend Einträge, von
        # denen der Slicer jeden ablehnt, sind keine Auswahl, sondern eine
        # Einladung zum falschen Klick.
        fitting = slicer_profiles.processes(self._profiles, machine) if machine else []
        self.process_choice.clear()
        for entry in fitting:
            self.process_choice.addItem(entry.title(tr("eigenes")), str(entry.path))

        wanted = self.ui_settings.slicer_base_process
        index = self.process_choice.findData(wanted) if wanted else -1
        if index < 0 and preferred is not None:
            index = self.process_choice.findData(str(preferred.path))
        if index < 0 and machine is not None:
            named = [entry for entry in fitting if entry.name == machine.default_process]
            if named:
                index = self.process_choice.findData(str(named[0].path))
        self.process_choice.setCurrentIndex(max(index, 0))
        self._fill_filaments(machine)

    def _fill_filaments(self, machine: slicer_profiles.SlicerProfile | None) -> None:
        """Die Filamentprofile zum gewählten Drucker, vorbelegt nach Material.

        Die Vorgabe ist die Grundausführung des eingestellten Materials —
        „Elegoo PETG", nicht „Elegoo PETG Translucent". Von einem Material
        liegen mehrere Ausführungen im Bestand, und sie fahren verschieden:
        das transluzente will 255 Grad, das PRO 240 bei halbem Volumenstrom.
        Wer eine besondere Spule hat, stellt sie hier ein.
        """
        fitting = slicer_profiles.filaments(self._profiles, machine) if machine else []
        self.filament_choice.clear()
        for entry in fitting:
            self.filament_choice.addItem(entry.title(tr("eigenes")), str(entry.path))

        if not fitting:
            # Nichts zu wählen heißt nichts vorzuwählen. Die Suche darunter lief
            # trotzdem und war zweimal falsch: wirkungslos, weil ``findData``
            # danach eine leere Liste absucht, und teuer, weil sie ohne Drucker
            # den ganzen Bestand aufschlägt statt der Handvoll passender. Beim
            # vorgegebenen „Allgemeinen FDM-Drucker" — also beim ersten Öffnen,
            # bevor jemand einen Drucker eingestellt hat — stand die Anwendung
            # damit minutenlang.
            self.filament_choice.setCurrentIndex(-1)
            for _label, box in self.slot_rows:
                box.clear()
            return

        # Erst was für *dieses* Material zuletzt galt, dann der allgemeine
        # Merker, dann die Zuordnung nach Materialart.
        material = self.session.profile.material.id
        wanted = self.ui_settings.slicer_filament_per_material.get(
            material, self.ui_settings.slicer_base_filament
        )
        index = self.filament_choice.findData(wanted) if wanted else -1
        if index < 0 and wanted:
            index = self.filament_choice.findText(wanted)
        if index < 0:
            material = slicer_keys.filament_type(self.session.profile.material.id)
            preferred = slicer_profiles.match_filament(self._profiles, machine, material)
            if preferred is not None:
                index = self.filament_choice.findData(str(preferred.path))
        self.filament_choice.setCurrentIndex(max(index, 0))

        # Dieselbe Liste in jede Slot-Zeile. Vorbelegt mit dem, was das Projekt
        # dazu sagt; ohne Angabe mit dem Filament der Platte.
        for position, (_label, box) in enumerate(self.slot_rows):
            box.clear()
            for entry in fitting:
                box.addItem(entry.title(tr("eigenes")), str(entry.path))
            box.setEnabled(True)
            remembered = self.settings.slot_profiles
            name = remembered[position] if position < len(remembered) else ""
            found = box.findText(name) if name else -1
            box.setCurrentIndex(found if found >= 0 else self.filament_choice.currentIndex())

    def _build_slot_rows(self, form: QFormLayout) -> None:
        """Eine Auswahl je Slot, sobald ein Teil mehrere Farben trägt (§20).

        Der Slot *ist* das Filament: ein Schriftzug in Weiß auf schwarzem
        Gehäuse sind zwei Spulen mit zwei Temperaturen. Ohne diese Zeilen ließe
        sich das zwar drucken, aber nicht sagen — und die zweite Farbe liefe
        mit den Werten der ersten.
        """
        for label, _box in self.slot_rows:
            form.removeRow(label)
        self.slot_rows.clear()

        slots = self._plate_slots()
        if len(slots) < 2:
            return
        stored = self.settings.slot_profiles
        for index, slot in enumerate(slots):
            box = QComboBox(self.slicer_box)
            box.setEnabled(bool(self._profiles))
            box.activated.connect(lambda _i, position=index: self._slot_filament_chosen(position))
            caption = slot.name or tr("Slot {nummer}").replace("{nummer}", str(index + 1))
            label = QLabel(f"   {caption}", self.slicer_box)
            form.addRow(label, box)
            self.slot_rows.append((label, box))
            if index < len(stored) and stored[index]:
                box.setProperty("wanted", stored[index])

    def _plate_slots(self) -> list[MaterialSlot]:
        """Die Materialslots der ersten Platte, zusammengelegt wie beim Export."""
        result = self.session.last_result
        if result is None:
            return []
        objects = [result.scene.objects[oid] for oid in result.scene.objects]
        if not objects:
            return []
        erste = min(entry.plate for entry in objects)
        return threemf.merge_slots(
            [
                threemf.AssemblyPart(
                    mesh=as_mesh_data(entry.mesh), slots=tuple(entry.material_slots)
                )
                for entry in objects
                if entry.plate == erste
            ]
        )

    def _slot_filament_chosen(self, position: int) -> None:
        """Die Wahl für einen Slot festhalten (§20).

        Gespeichert wird der **Name**, nicht der Pfad: er reist mit dem Projekt
        und zeigt auf einem zweiten Rechner nicht ins Leere (Regel 12).
        """
        if position >= len(self.slot_rows):
            return
        box = self.slot_rows[position][1]
        chosen = box.currentText()
        names = list(self.settings.slot_profiles)
        names += [""] * (len(self.slot_rows) - len(names))
        names[position] = chosen
        self.settings = replace(self.settings, slot_profiles=tuple(names))
        self.state.setText(
            tr("{slot} druckt mit {profil}.")
            .replace("{slot}", self.slot_rows[position][0].text().strip())
            .replace("{profil}", chosen)
        )

    def _filament_chosen(self, _index: int) -> None:
        """Die Werte der gewählten Spule übernehmen (§29).

        Solidon kennt „PETG" und bringt dafür einen Startbestand mit — 10 mm³/s
        bei 80 Grad Bett. Der Bestand des Slicers kennt sieben PETG, und das
        PRO fährt 5 mm³/s bei 70 Grad. Ohne diese Übernahme rechnet die
        Beratung gegen eine Grenze, die das eingelegte Material gar nicht hat:
        sie sah 10 mm³/s, wo 5 galten, fand nichts einzuwenden und ließ ein
        Tempo stehen, das die Düse nicht flüssig bekommt.

        Nur auf ausdrückliche Wahl, nie beim Befüllen der Liste: was ein
        Projekt mitbringt, gilt (eine Dichtung aus TPU bleibt eine Dichtung aus
        TPU). Wer eine besondere Spule einlegt, sagt es hier einmal.
        """
        chosen = self.filament_choice.currentData()
        if not chosen:
            return
        values = slicer_profiles.filament_values(Path(str(chosen)))
        if not values:
            return
        settings = self.settings
        for path, value in values.items():
            settings = print_settings.with_path(settings, path, value)
        self.settings = settings
        self._load_into_editors()
        self._refresh_advice()
        self.state.setText(
            tr("Werte aus {profil} übernommen.").replace(
                "{profil}", self.filament_choice.currentText()
            )
        )
        _log.info("adopted %d values from %s", len(values), chosen)

    def _profile_search_finished(self) -> None:
        # `finished` heißt „`run` ist zurück", nicht „das Objekt darf weg" —
        # das Loslassen übernimmt die Halteleine.
        worker = self._profile_worker
        self._profile_worker = None
        if worker is not None:
            self._leash.hold_until_done(worker)

    def _build_advice(self) -> QWidget:
        box = QGroupBox(tr("Was dieses Teil verlangt"), self)
        inner = QVBoxLayout(box)

        self.advice_view = QTreeWidget(box)
        self.advice_view.setColumnCount(3)
        self.advice_view.setHeaderLabels([tr("Einstellung"), tr("Vorschlag"), tr("Grund")])
        self.advice_view.setRootIsDecorated(False)
        self.advice_view.setMaximumHeight(150)
        # Die Gründe bekommen, was die beiden ersten Spalten übrig lassen, und
        # brechen darin um, statt auf „…" zu enden. Bei drei Spalten mit
        # gleichem Anteil stand in jeder Zeile ein angefangener Satz.
        header = self.advice_view.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.advice_view.setWordWrap(True)
        inner.addWidget(self.advice_view)

        self.apply_button = QPushButton(tr("Vorschläge übernehmen"), box)
        self.apply_button.clicked.connect(self._apply_advice)
        inner.addWidget(self.apply_button, 0, Qt.AlignmentFlag.AlignRight)
        return box

    def _build_state(self) -> QWidget:
        holder = QWidget(self)
        row = QVBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        self.state = QLabel("", holder)
        self.state.setWordWrap(True)
        self.progress = QProgressBar(holder)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        # §2.8: über zwei Sekunden gehört neben den Fortschritt ein Abbrechen.
        # Es gab keines — der Lauf war erst zu Ende, wenn der Slicer es war.
        self.cancel_slice = QPushButton(tr("Abbrechen"), holder)
        self.cancel_slice.setVisible(False)
        self.cancel_slice.clicked.connect(self._cancel_slice)
        row.addWidget(self.state)
        row.addWidget(self.progress)
        row.addWidget(self.cancel_slice)
        return holder

    def _build_buttons(self) -> QWidget:
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        # Qt beschriftet seine Standardknöpfe selbst, und zwar in der Sprache
        # des Systems — Regel 20 verlangt, dass auch dieser Text durch tr() geht.
        close = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close is not None:
            close.setText(tr("Schließen"))
        self.slice_button = QPushButton(tr("Slicen"), self)
        make_primary(self.slice_button)
        self.slice_button.clicked.connect(self._slice)
        buttons.addButton(self.slice_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.save_button = QPushButton(tr("Druckdatei speichern …"), self)
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_gcode)
        buttons.addButton(self.save_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)

        found = self._slicer_path
        if found is None:
            # §27: das Backend meldet sich ab, es nörgelt nicht.
            self.slice_button.setEnabled(False)
            self.state.setText(
                tr("Kein Slicer eingerichtet — die Einstellungen lassen sich trotzdem pflegen.")
            )
        return buttons

    def _label(self, field: Field) -> str:
        return f"{field.title} [{field.unit}]" if field.unit else field.title

    def _editor(self, field: Field) -> QWidget:
        editor: QWidget
        if field.kind == "bool":
            editor = QCheckBox(self)
            editor.toggled.connect(self._editor_changed)
        elif field.kind == "int":
            spin = QSpinBox(self)
            spin.setRange(int(field.minimum), int(field.maximum))
            spin.valueChanged.connect(self._editor_changed)
            editor = spin
        elif field.kind == "enum":
            combo = QComboBox(self)
            # Gezeigt wird die Übersetzung, gespeichert der englische Wert: er
            # geht in die Projektdatei und zum Slicer (§4.1).
            for choice in field.choices:
                combo.addItem(choice_label(choice), choice)
            combo.currentIndexChanged.connect(self._editor_changed)
            editor = combo
        elif field.kind == "colour":
            button = _ColourButton("#000000", self)
            button.changed.connect(self._editor_changed)
            editor = button
        else:
            number = QDoubleSpinBox(self)
            number.setRange(field.minimum, field.maximum)
            number.setSingleStep(field.step)
            number.setDecimals(field.decimals)
            number.valueChanged.connect(self._editor_changed)
            editor = number
        self._editors[field.path] = editor
        self._fields[field.path] = field
        return editor

    # --- Werte hin und her ----------------------------------------------------

    def _load_into_editors(self) -> None:
        """Aus dem Modell in die Felder. ``_loading`` hält die Rückmeldung an,
        sonst schriebe jedes gesetzte Feld sofort wieder zurück."""
        self._loading = True
        try:
            for field in FIELDS:
                value = print_settings.read_path(self.settings, field.path)
                editor = self._editors[field.path]
                if isinstance(editor, QCheckBox):
                    editor.setChecked(bool(value))
                elif isinstance(editor, QSpinBox):
                    editor.setValue(int(value))
                elif isinstance(editor, QComboBox):
                    index = editor.findData(str(value))
                    editor.setCurrentIndex(max(index, 0))
                elif isinstance(editor, _ColourButton):
                    editor.set_value(str(value))
                elif isinstance(editor, QDoubleSpinBox):
                    editor.setValue(float(value) * field.factor)
        finally:
            self._loading = False

    def _collect(self) -> PrintSettings:
        """Aus den Feldern zurück ins Modell."""
        settings = self.settings
        for field in FIELDS:
            editor = self._editors[field.path]
            value: Any
            if isinstance(editor, QCheckBox):
                value = editor.isChecked()
            elif isinstance(editor, QSpinBox):
                value = editor.value()
            elif isinstance(editor, QComboBox):
                value = editor.currentData()
            elif isinstance(editor, _ColourButton):
                value = editor.value()
            elif isinstance(editor, QDoubleSpinBox):
                value = float(editor.value()) / field.factor
            else:
                continue
            settings = print_settings.with_path(settings, field.path, value)
        return settings

    def _editor_changed(self, *_args: object) -> None:
        if self._loading:
            return
        self.settings = self._collect()
        self._refresh_advice()

    def _quality_changed(self) -> None:
        """Die Stufe wechseln heißt: neu auflösen. Von Hand Geändertes geht
        dabei verloren — das ist der Sinn einer Stufe, und rücknehmbar ist es
        über die Stufe, aus der man kam (Regel 19: keine Rückfrage)."""
        chosen = self.quality.currentData()
        if chosen is None:
            return
        self.settings = print_settings.resolve(self.session.profile, chosen)
        self._load_into_editors()
        self._refresh_advice()

    # --- Vorschläge -----------------------------------------------------------

    def _current_advice(self) -> list[SettingAdvice]:
        return advise.advise(
            self.settings,
            self.session.profile,
            self.slice_result,
            bounds=self._bounds(),
            fit_kinds=self._fits_in_play(),
            connectors=self._connector_diameters(),
        )

    def _connector_diameters(self) -> tuple[float, ...]:
        """Die Durchmesser der Zapfen, die beim Teilen entstanden sind.

        Aus den Merkmalen und nicht aus dem Stapel: Die Stiftplanung rechnet
        den Durchmesser aus der Schnittfläche, er ist also kein Parameter, den
        jemand eingetragen hätte. Wo er steht, ist das erzeugte Merkmal.

        Nur die Zapfen, nicht die Bohrungen — es ist dasselbe Maß plus Spiel,
        und zweimal gezählt sähe es nach doppelt so vielen Verbindern aus.
        """
        result = self.session.last_result
        if result is None:
            return ()
        return tuple(
            float(feature.params["diameter"])
            for entry in result.scene.objects.values()
            for feature in entry.features.values()
            if feature.kind == "pin" and "diameter" in feature.params
        )

    def _fits_in_play(self) -> tuple[str, ...]:
        """Welche Passungen trägt dieses Projekt — eingetragene und gebaute?

        Eingetragene Passungen stehen im Dokument. Gebaute stehen nirgends: der
        Deckel aus ``create_lid`` bekommt sein Spiel aus dem Materialprofil, die
        Mutternfalle ihres aus der Normteiltabelle, und keiner von beiden trägt
        es ins Dokument ein. Damit liefen genau die Regeln nicht, die es für
        Passungen gibt — genaue Außenwand, gebremste Beschleunigung, Bügeln der
        Gleitfläche —, und der gedruckte Gewürzdeckel bekam keine davon.

        Hier zählt deshalb auch, was im Stapel steht. Das ist die kleine Hälfte
        der Sache: die Passung selbst gehört ins Dokument, damit auch die
        Prüfung sie sieht und ein Nutzer sie ändern kann. Das ändert den
        Vertrag aus §9 (eine Op müsste Passungen zurückgeben können) und ist
        eine eigene Runde wert.

        Zurück kommen die **Arten**, nicht bloß ein Ja: eine bündige Passung
        verlangt eine Einstellung mehr als ein Schiebesitz, und die Regel
        nebenan kann das nur unterscheiden, wenn sie es erfährt. Was aus dem
        Stapel kommt, zählt als Schiebesitz — welche Flächen ein Baustein
        aufeinanderlegt, steht nirgends, und eine geratene Art wäre schlechter
        als keine.
        """
        document = self.session.project.document
        kinds = [entry.kind for entry in document.fits]
        if any(entry.op in FITTING_OPS for entry in document.ops):
            kinds.append("clearance")
        return tuple(dict.fromkeys(kinds))

    def _bounds(self) -> BoundingBox | None:
        """Der Hüllquader über alles, was auf die Platte geht — daran hängt der
        Hinweis auf hohe, schmale Teile."""
        result = self.session.last_result
        if result is None or not result.scene.objects:
            return None
        boxes = [entry.mesh.bounds for entry in result.scene.objects.values() if entry.mesh]
        if not boxes:
            return None
        return BoundingBox(
            minimum=tuple(min(box.minimum[axis] for box in boxes) for axis in range(3)),  # type: ignore[arg-type]
            maximum=tuple(max(box.maximum[axis] for box in boxes) for axis in range(3)),  # type: ignore[arg-type]
        )

    def _shown(self, path: str, value: object) -> str:
        """Ein Wert so, wie er im Feld daneben steht — sonst schlägt der
        Vorschlag etwas vor, das der Nutzer nicht wiedererkennt."""
        field = self._fields.get(path)
        if isinstance(value, str):
            return choice_label(value)
        if field is not None and isinstance(value, int | float):
            return f"{float(value) * field.factor:g} {field.unit}".strip()
        return str(value)

    def _refresh_advice(self) -> None:
        entries = self._current_advice()
        self.advice_view.clear()
        for entry in entries:
            field = self._fields.get(entry.path)
            # Regel 18: das Ausrufezeichen ist die zweite Kodierung neben der
            # Einstufung — eine Warnung darf sich nicht allein an Farbe zeigen.
            marker = "! " if entry.severity == "warning" else ""
            was = self._shown(entry.path, entry.was)
            becomes = self._shown(entry.path, entry.value)
            item = QTreeWidgetItem(
                [
                    f"{marker}{field.title if field else entry.path}",
                    f"{was} → {becomes}",
                    str(entry.reason),
                ]
            )
            # Angehakt heißt „wird übernommen". Vorbelegt ja, denn die
            # Vorschläge sind begründet — aber einzeln abwählbar, weil sonst
            # die Wahl zwischen allen und keinem bestünde und der Nutzer für
            # einen unpassenden Vorschlag die übrigen mit aufgäbe.
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setData(0, Qt.ItemDataRole.UserRole, entry.path)
            # Der Grund ist der Satz, der den Vorschlag rechtfertigt, und er
            # ist länger als jede Spalte, die neben zwei anderen Platz hat.
            # In der Zeile stand deshalb „Das Projekt hat Passungen. …" — der
            # Teil, den man liest, wenn man wissen will, ob der Vorschlag zum
            # eigenen Teil passt, war genau der abgeschnittene. Er steht jetzt
            # zusätzlich am ganzen Eintrag.
            for column in range(3):
                item.setToolTip(column, str(entry.reason))
            self.advice_view.addTopLevelItem(item)
        if not entries:
            self.advice_view.addTopLevelItem(QTreeWidgetItem([tr("Nichts einzuwenden."), "", ""]))
        self.apply_button.setEnabled(bool(entries))
        for column in range(2):
            self.advice_view.resizeColumnToContents(column)

    def _chosen_advice(self) -> list[SettingAdvice]:
        """Die angehakten Vorschläge, in der Reihenfolge der Liste."""
        wanted = {
            item.data(0, Qt.ItemDataRole.UserRole)
            for index in range(self.advice_view.topLevelItemCount())
            if (item := self.advice_view.topLevelItem(index)) is not None
            and item.checkState(0) == Qt.CheckState.Checked
        }
        return [entry for entry in self._current_advice() if entry.path in wanted]

    def _apply_advice(self) -> None:
        self.settings = advise.apply(self.settings, self._chosen_advice())
        self._load_into_editors()
        self._refresh_advice()

    # --- Slicen ---------------------------------------------------------------

    def _slice(self) -> None:
        result = self.session.last_result
        objects = list(result.scene.objects.values()) if result is not None else []
        if not objects:
            self.state.setText(tr("Es ist nichts da, was sich slicen ließe."))
            return

        found = self._slicer_path
        if found is None:
            return
        try:
            setup = handover.detect(found)
        except AppError as problem:
            show_error(problem, self)
            return
        # Was in der Auswahl steht, gilt — sie ist automatisch vorbelegt, aber
        # der Nutzer darf abweichen, und dann zählt seine Wahl (§29).
        setup = replace(
            setup,
            machine_profile=str(self.machine_choice.currentData() or ""),
            base_process=str(self.process_choice.currentData() or ""),
            base_filament=str(self.filament_choice.currentData() or ""),
        )
        # Nur die Orca-Familie: PrusaSlicer läuft mit Solidons vollständiger
        # ini, und CuraEngine bekommt die Maschine aus dem Kern selbst
        # (`_machine_keys`) — für Cura gibt es strukturell keine Profile zu
        # wählen, und die Forderung war eine Wahl aus einer leeren Liste.
        if setup.flavour == "orca" and not setup.machine_profile:
            self.slicer_box.setChecked(True)
            self.state.setText(
                tr("Dieser Slicer braucht ein Druckerprofil — bitte eines auswählen.")
            )
            return
        # Das Prozessprofil ist genauso wenig verzichtbar, nur fiel es später
        # auf: die Orca-Familie nimmt kein Prozessprofil an, das nicht zum
        # Drucker passt, und ohne ein Systemprofil darunter hat Solidons
        # Datei nichts, wozu sie passen könnte (siehe `_orca_process`). Der
        # Lauf lief bis dahin los und endete in „Der Slicer hat keine
        # Druckdatei geschrieben" — ein Satz über das Ende, nicht über die
        # Ursache.
        if setup.flavour == "orca" and not setup.base_process:
            self.slicer_box.setChecked(True)
            self.state.setText(
                tr("Dieser Slicer braucht auch ein Prozessprofil — bitte eines auswählen.")
            )
            return
        self.ui_settings.slicer_machine_profile = setup.machine_profile
        self.ui_settings.slicer_base_process = setup.base_process
        self.ui_settings.slicer_base_filament = setup.base_filament
        # Und je Material: „petg" allein sagt nicht, welche der sieben Spulen
        # gemeint war, und nach einem TPU-Teil stünde die falsche da.
        if setup.base_filament:
            self.ui_settings.slicer_filament_per_material[self.session.profile.material.id] = (
                setup.base_filament
            )

        self._temporary = TemporaryDirectory(prefix="solidon-handover-")
        folder = Path(self._temporary.name)
        name = self.session.path.stem if self.session.path else "solidon"
        plates = sorted({entry.plate for entry in objects})
        try:
            runs = [self._plate_run(objects, plate, folder, name, setup) for plate in plates]
        except AppError as problem:
            show_error(problem, self)
            return

        self.slice_button.setEnabled(False)
        # Bei mehreren Platten ist die Plattenzahl die ehrlichste Schätzung
        # (§2.8) — bei einer bliebe ein Balken „0 von 1" eine Zahl ohne
        # Aussage, dann läuft er unbestimmt.
        if len(runs) > 1:
            self.progress.setRange(0, len(runs))
            self.progress.setValue(0)
        else:
            self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        self.cancel_slice.setEnabled(True)
        self.cancel_slice.setVisible(True)
        self.state.setText(tr("Der Slicer rechnet …"))

        worker = _SliceWorker(runs, self.settings, self.session.profile, setup)
        worker.done.connect(self._sliced)
        worker.failed.connect(self._slice_failed)
        worker.finished.connect(self._slice_finished)
        worker.step.connect(self._slicing_plate)
        self._worker = worker
        worker.start()

    def _plate_run(
        self,
        objects: list[SceneObject],
        plate: int,
        folder: Path,
        name: str,
        setup: handover.SlicerSetup,
    ) -> PlateRun:
        """Eine Platte für den Slicer fertig machen (§20, §25, §29).

        Eine Baugruppe je Platte und nicht eine Datei je Objekt: der Slicer
        bekommt damit einen Druckauftrag statt einer Handvoll Teile, über deren
        Zusammengehörigkeit er selbst entscheiden müsste.

        Der Dateiname trägt die Plattennummer, sobald es mehr als eine gibt —
        ohne sie schriebe die zweite Platte die erste über, und beide Läufe
        legten ihren G-Code an dieselbe Stelle daneben.
        """
        on_plate = [entry for entry in objects if entry.plate == plate]
        # Hält die Anordnung, geht sie mit — und wird beim Aufruf auch
        # durchgesetzt. Sonst ordnet der Slicer an, wie er es ohne uns täte:
        # zwei Teile übereinander wären schlimmer als eine verworfene
        # Anordnung (§29). Je Platte gefragt, denn jede ist eine eigene.
        keep = arrangement_holds(
            [as_mesh_data(entry.mesh) for entry in on_plate], self.session.profile
        )
        written, findings = write_assembly(
            objects,
            folder,
            project_name=name if len(objects) == len(on_plate) else f"{name}-{plate + 1}",
            profile=self.session.profile,
            plate=plate,
            # Damit ein Teil bekommen kann, was nur es braucht — der Brim
            # unter der Streuscheibe, nicht unter den zwölf Behältern.
            settings=self.settings,
            flavour=setup.flavour,
            place_on_bed=keep,
            # Und das Systemprofil darunter: ohne es trägt die Datei zwar
            # Solidons Werte, aber keinen Drucker, zu dem sie passen.
            setup=setup,
        )
        # Die Materialslots der Platte: je Slot ein Filament (§20). Ohne sie
        # bekäme jede Farbe die Werte der ersten. Je Platte eigene, denn die
        # Plattenaufteilung folgt gerade dem Material (`plates_by_material`).
        slots = threemf.merge_slots(
            [
                threemf.AssemblyPart(
                    mesh=as_mesh_data(entry.mesh), slots=tuple(entry.material_slots)
                )
                for entry in on_plate
            ]
        )
        return PlateRun(
            plate=plate,
            model=written,
            # Die Wahl aus den Slot-Zeilen reist am Slot selbst: eingesammelt
            # wurde sie schon immer, angekommen ist sie hier nie — alle Slots
            # slicten mit dem Basisfilament, und „druckt mit" war eine Zusage
            # ohne Deckung (§20).
            slots=handover.with_slot_profiles(slots, self.settings.slot_profiles),
            keep_arrangement=keep,
            findings=tuple(findings),
        )

    def _slicing_plate(self, index: int, count: int) -> None:
        """Bei welcher Platte der Lauf steht (§2.8).

        Nur bei mehreren: „Platte 1 von 1" wäre eine Zahl ohne Aussage.
        """
        if count > 1:
            self.progress.setValue(index - 1)
            self.state.setText(
                tr("Der Slicer rechnet — Platte {nummer} von {anzahl} …")
                .replace("{nummer}", str(index))
                .replace("{anzahl}", str(count))
            )

    def _cancel_slice(self) -> None:
        """Der Abbrechen-Knopf: den Kindprozess beenden, den Rest lassen.

        Der Knopf graut sofort aus — zweimal abbrechen gibt es nicht, und der
        Text daneben sagt, dass es angekommen ist.
        """
        worker = self._worker
        if worker is None:
            return
        self.cancel_slice.setEnabled(False)
        self.state.setText(tr("Wird abgebrochen …"))
        worker.cancel()

    def _sliced(self, outcomes: list[handover.SliceOutcome]) -> None:
        """Was der Lauf gebracht hat — über alle Platten zusammen.

        Zeit und Material sind Summen, weil zwei Platten zweimal gedruckt
        werden; die Schichtzahl steht nur bei einer, denn über zwei addiert
        wäre sie eine Zahl, die es nirgends gibt (:func:`gcode.combine`).
        """
        if not outcomes:
            return
        metrics = gcode.combine([entry.metrics for entry in outcomes])
        parts = []
        if metrics.print_minutes is not None:
            parts.append(f"{tr('Druckzeit')}: {metrics.print_minutes:.0f} min")
        grams = metrics.grams(self.settings.filament.density)
        if grams is not None:
            parts.append(f"{tr('Material')}: {grams:.1f} g")
        if metrics.layer_count is not None:
            parts.append(f"{tr('Schichten')}: {metrics.layer_count}")
        if len(outcomes) > 1:
            parts.append(f"{tr('Platten')}: {len(outcomes)}")
        self.state.setText(" · ".join(parts) if parts else tr("Fertig geslicet."))
        # Die Dateien liegen im Arbeitsordner, der beim Schließen verschwindet.
        # Ohne diesen Knopf wäre der ganze Lauf eine Zahl auf dem Bildschirm
        # und nichts, was auf einen Drucker geht.
        self._gcode = [entry.gcode_path for entry in outcomes]
        self.save_button.setEnabled(True)
        outcomes[0].findings = [*self._pending_findings, *outcomes[0].findings]
        self._pending_findings = []
        self.sliced.emit(outcomes)
        _log.info(
            "sliced %d plate(s) with %s in %.1f s",
            len(outcomes),
            metrics.slicer,
            sum(entry.seconds for entry in outcomes),
        )

    def _save_gcode(self) -> None:
        """Die Druckdateien dorthin, wo der Nutzer sie haben will (§29).

        Vorgeschlagen wird der Ordner des Projekts und der Name des Projekts —
        eine Datei namens ``plate_1.gcode`` in den Downloads findet später
        niemand wieder.

        **Bei mehreren Platten wird der Ordner gewählt, nicht die Datei.** Ein
        Speichern-Dialog je Platte wäre dieselbe Frage dreimal; die Namen
        stehen ohnehin fest, sobald der Auftrag einen hat — sie unterscheiden
        sich nur in der Plattennummer.
        """
        written = [path for path in self._gcode if path.is_file()]
        if not written:
            return
        start = self.session.path.parent if self.session.path else Path.home()
        stem = self.session.path.stem if self.session.path else "solidon"

        if len(written) == 1:
            chosen, _filter = QFileDialog.getSaveFileName(
                self,
                tr("Druckdatei speichern"),
                str(start / f"{stem}.gcode"),
                f"{tr('G-Code')} (*.gcode)",
            )
            if not chosen:
                return
            targets = [Path(chosen)]
        else:
            folder = QFileDialog.getExistingDirectory(
                self, tr("Ordner für die Druckdateien"), str(start)
            )
            if not folder:
                return
            targets = [
                Path(folder) / f"{stem}-{index}.gcode" for index in range(1, len(written) + 1)
            ]

        for target, source in zip(targets, written, strict=True):
            target.write_bytes(source.read_bytes())
            _log.info("wrote g-code to %s", target)
        self.state.setText(
            f"{tr('Gespeichert')}: {targets[0].name}"
            if len(targets) == 1
            else f"{tr('Gespeichert')}: {len(targets)} {tr('Druckdateien')} → {targets[0].parent}"
        )

    def _slice_failed(self, problem: AppError) -> None:
        self.state.setText("")
        show_error(problem, self)

    def _slice_finished(self) -> None:
        self.progress.setVisible(False)
        self.cancel_slice.setVisible(False)
        self.slice_button.setEnabled(True)
        worker = self._worker
        self._worker = None
        if worker is not None:
            if worker.cancelled.is_cancelled:
                self.state.setText(tr("Abgebrochen."))
            # `finished` heißt „`run` ist zurück", nicht „das Objekt darf
            # weg" — das Loslassen übernimmt die Halteleine.
            self._leash.hold_until_done(worker)

    def reject(self) -> None:
        """Escape und der Schließen-Knopf gehen denselben Weg wie das X.

        Qt ruft bei ``reject()`` kein ``closeEvent`` — der Arbeiter lief
        unsichtbar weiter, und ``_temporary`` blieb als Ordner liegen.
        """
        self._settle()
        super().reject()

    def closeEvent(self, event: Any) -> None:  # noqa: N802 — Qt gibt den Namen vor
        self._settle()
        super().closeEvent(event)

    def _settle(self) -> None:
        """Den Ordner erst freigeben, wenn niemand mehr darin liest.

        Der Slicer-Lauf wird abgebrochen statt abgewartet: ``worker.wait()``
        ohne Grenze stand hier im Qt-Hauptthread, und wer während eines
        großen Auftrags schloss, hatte eine eingefrorene Anwendung, bis der
        externe Slicer von sich aus fertig war — Minuten. Das Warten bleibt,
        aber nach dem Abbruch ist es kurz: der Kindprozess stirbt binnen
        Sekunden, und ohne das Warten stürbe der Thread über einem
        zerstörten Dialog.
        """
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.cancel()
        for pending in (self._worker, self._profile_worker):
            if pending is not None and pending.isRunning():
                pending.wait()
        self._leash.wait_all()
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
