"""Druckeinstellungen und Übergabe an den Slicer (Bauplan §29, §2.4).

Der Dialog, der den Wechsel ins andere Programm ersetzt. Vorn steht, was man
wirklich ändert — Qualität, Füllung, Stützen, Farbe —, hinter „Weitere
Einstellungen" liegt der Rest, nach Gebieten sortiert (§2.4, gestufte Tiefe).

Die Felder kommen aus :data:`FIELDS`, einer Tabelle: eine neue Einstellung im
Kernmodell kostet hier eine Zeile und keinen Eingriff. Titel und Einheiten
stehen bewusst hier und nicht im Kern — es sind Oberflächentexte, sie gehen
durch ``_()``, und der Kern kennt keine Beschriftungen. ``_()`` und nicht
``tr()``, weil die Tabelle im Modulrumpf steht: Der Kommentar über ihr sagt,
was das ausmacht.

Was die Geometrie selbst verlangt, steht darunter als Liste mit Begründung
(:mod:`app.core.slice.advise`). Übernommen wird auf Klick, nie von allein:
ein Vorschlag, der sich still anwendet, ist eine Einstellung, die der Nutzer
nicht getroffen hat.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final, Literal, cast

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core import activation, discover, tools
from app.core.errors import AppError, InternalError, OperationCancelled
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
    HandoverKind,
    MaterialSlot,
    PrintSettings,
    Profile,
    SceneObject,
    SettingAdvice,
    SliceResult,
    SlotOverride,
)
from app.core.units import DEGREE_UNIT, is_close
from app.i18n import TranslatableText, _, tr
from app.ui.dialogs import handlers_of, licence_lock_line, show_error
from app.ui.facts import duration, mass
from app.ui.filament_picker import SWATCH_PIXELS, shown_colour, swatch
from app.ui.labels import (
    NumberSpin,
    by_title,
    choice_label,
    colour_name,
    explain_choices,
    localised,
)
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.palette import ROLES
from app.ui.panels import align_forms, collapsible
from app.ui.session import Session
from app.ui.settings import UiSettings, save_settings
from app.ui.style import ROOMY, TIGHT, make_primary, set_level
from app.ui.theme import THEMES, current_theme

_log = get_logger(__name__)

FieldKind = Literal["float", "int", "bool", "enum", "colour"]


@dataclass(frozen=True, slots=True)
class Field:
    """Eine Zeile im Dialog. ``group`` ist der Reiter, ``front`` hebt sie nach
    vorn."""

    path: str
    title: str | TranslatableText
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
    note: str | TranslatableText = ""
    """Was der Wert tut, und woran man ihn ändert — als Tooltip am Feld.

    **Der größte Dialog der Anwendung war der einzige ohne ein erklärendes
    Wort.** Jeder der 136 Menüeinträge trägt einen Satz, jeder Parameter einer
    Operation seinen ``doc``-Satz; hier standen sechsundfünfzig Felder, und wer
    „Außenwand auf Sollmaß" oder „Wände nicht überfahren" las, blieb allein
    damit. Bei „Schichthöhe" hätte man es übersehen können — bei den
    dreiundzwanzig Feldern, deren Name eine Technik nennt statt einer Sache,
    nicht.

    Alle sechsundfünfzig tragen einen: Ein Dialog, in dem die Hälfte der Felder
    einen Tooltip hat, lehrt niemanden, dass es Tooltips gibt (Konsistenz vor
    Vollständigkeit). ``tests/test_print_settings_ui.py`` hält das fest."""


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
#: Die Reiter der Tiefe, in der Reihenfolge, in der sie stehen.
#:
#: **Ein Reiter, ein Thema** (Befund B10): Bis zum 30.08.2026 sammelte
#: ``other`` unter dem Titel „Haftung, Rückzug, Filament" sechzehn Felder —
#: fast dreimal so viele wie der Schnitt, und drei Themen in einem Namen sind
#: kein Titel, sondern eine Aufzählung. Die Teilung stand längst im Pfad
#: jedes Feldes; jetzt ist der Reiter eines Feldes sein Bereich.
#: Aus dem Kern geholt, nicht abgeschrieben: ``read_path`` lehnt jeden Pfad ab,
#: dessen Bereich dort nicht steht — eine eigene Liste hier hätte den elften
#: Bereich still verschluckt.
GROUPS = print_settings.GROUPS

#: Wie breit ein Feld höchstens wird, je Art des Werts. Ein Haken steht nicht
#: dabei: bei ihm ist die breite Fläche ein größeres Ziel und kein gedehnter
#: Kasten. Die Zahlen sind Höchstmaße — wer mehr braucht, bekommt mehr
#: (:meth:`PrintSettingsDialog._editor`).
#: Qt-Eigenschaft, unter der ein Feld seinen **eigenen** Hinweis aufhebt.
#:
#: Ein gesperrtes Feld trägt den Grund der Sperre; wird es wieder frei, muss
#: der ursprüngliche Satz zurück — und der lässt sich nicht neu bauen. Der
#: Farbknopf etwa nennt in seinem Tooltip den Hexwert, den sonst nichts zeigt.
_OWN_TIP: Final = "solidonOwnTip"

FIELD_WIDTH: Final[dict[str, int]] = {
    "float": 130,
    "int": 130,
    "enum": 280,
    "colour": 160,
}


#: Wann zwei Einstellungswerte als gleich gelten — feiner als jedes Feld
#: anzeigt.
#:
#: Nicht ``EPS_GEOM`` (0,001 mm): Ein Flussverhältnis steht auf 0,98, eine
#: Schichthöhe auf 0,08, und ein Anteil der Füllung auf 0,15 — dort wären
#: tausendstel Schritte eine echte Änderung. Sechs Stellen liegen unter jeder
#: Anzeige (höchstens drei Nachkommastellen) und über dem Rauschen, das beim
#: Hin- und Herrechnen durch ``factor`` entsteht.
EPS_SETTING: Final = 1e-6


def _same_value(a: object, b: object) -> bool:
    """Ob zwei Einstellungswerte dasselbe sagen.

    Regel 6: Fließkomma nie mit ``==``. Die Felder tragen dreierlei — Zahlen,
    Wahrheitswerte und Zeichenketten —, und ein Wahrheitswert ist in Python
    eine Zahl: Ohne die Abfrage davor wäre ``True`` gleich ``1,0``, und ein
    Haken, den jemand gesetzt hat, sähe aus wie eine unveränderte Eins.
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, int | float) and isinstance(b, int | float):
        return is_close(float(a), float(b), EPS_SETTING)
    return bool(a == b)


def group_title(group: str) -> str:
    return {
        "layers": tr("Schichten"),
        "shell": tr("Wände"),
        "infill": tr("Füllung"),
        "temperature": tr("Temperaturen"),
        "cooling": tr("Kühlung"),
        "speed": tr("Geschwindigkeit"),
        "support": tr("Stützen"),
        "adhesion": tr("Haftung"),
        "retraction": tr("Rückzug"),
        "filament": tr("Filament"),
    }.get(group, group)


# **Eine Tabelle für Auswahlwerte, nicht zwei.** Hier stand eine eigene neben
# ``labels._CHOICE_NAMES``, mit demselben Funktionsnamen davor — die eine
# verdeckte die andere, und beide beschrifteten dieselben Schlüssel. Sie waren
# schon auseinandergelaufen: „cubic" hieß dort „Würfelgitter" und hier „Würfel",
# „none" dort „Ohne" und hier „Keine". Und zwei Werte hatte keine von beiden:
# Im deutschen Fenster stand „Wandbahnen: classic" und „arachne".
#
# Die Gebietsregel nennt den Ort eindeutig — „Der Name steht in
# ``_CHOICE_NAMES`` (``app/ui/labels.py``)" —, und ``tests/test_translations.py``
# prüft jetzt beide Feldquellen gegen diese eine Tabelle.
#
# **Und jeder Text hier steht mit ``_()``, nicht mit ``tr()``.** Die Tabelle
# ist ein Modulrumpf: ``tr()`` übersetzt sofort, also beim Import, in der
# Sprache, die dann gerade gilt — und das ist beim Start noch keine.
# ``main_window.py`` zieht dieses Modul auf Modulebene nach, ``app.py``
# installiert die Sprache danach; ein Sprachwechsel zur Laufzeit
# (``rebuild_for_language``) baut die Fenster neu und die Module nicht. Alle
# sechsundfünfzig Titel und alle sechsundfünfzig Sätze blieben damit in der
# Startsprache stehen — der größte Dialog der Anwendung, deutsch in einem
# englischen Fenster. ``_()`` gibt einen ``TranslatableText``, der seine
# Sprache erst beim ``str()`` sucht; aufgelöst wird in ``_label`` und
# ``_editor``. Dieselbe Umstellung wie in ``settings_dialog``.


FIELDS: tuple[Field, ...] = (
    # --- Schichten ---
    Field(
        "layers.layer_height",
        _("Schichthöhe"),
        "layers",
        unit="mm",
        minimum=0.02,
        maximum=1.2,
        step=0.02,
        decimals=3,
        front=True,
        note=_(
            "Wie dick jede Schicht ist. Weniger heißt feiner und länger: 0,2 mm ist der Alltag, "
            "0,12 mm für Sichtteile, 0,28 mm für Klötze."
        ),
    ),
    Field(
        "layers.first_layer_height",
        _("Erste Schicht"),
        "layers",
        unit="mm",
        minimum=0.02,
        maximum=1.2,
        step=0.02,
        decimals=3,
        note=_(
            "Die erste Schicht darf dicker sein — sie füllt Unebenheiten der Platte aus und hält "
            "damit besser."
        ),
    ),
    Field(
        "layers.line_width",
        _("Linienbreite"),
        "layers",
        unit="mm",
        minimum=0.1,
        maximum=2.0,
        step=0.02,
        decimals=3,
        note=_(
            "Wie breit eine Bahn gelegt wird. Etwas mehr als der Düsendurchmesser ist normal: "
            "mehr trägt besser, weniger zeichnet feiner."
        ),
    ),
    Field(
        "layers.first_layer_line_width",
        _("Linienbreite erste Schicht"),
        "layers",
        unit="mm",
        minimum=0.1,
        maximum=2.0,
        step=0.02,
        decimals=3,
        note=_("Breiter als die übrigen Bahnen — mehr Material auf dem Bett heißt mehr Haftung."),
    ),
    # --- Wände ---
    Field(
        "shell.wall_count",
        _("Wände"),
        "shell",
        kind="int",
        minimum=1,
        maximum=20,
        front=True,
        note=_(
            "Wie viele Bahnen die Außenhaut dick ist. Zwei halten die Form, drei oder vier tragen "
            "Last."
        ),
    ),
    Field(
        "shell.top_layers",
        _("Deckschichten"),
        "shell",
        kind="int",
        minimum=0,
        maximum=50,
        note=_(
            "Volle Schichten oben, damit die Füllung nicht durchscheint. Unter drei bleiben "
            "Löcher über den Zellen."
        ),
    ),
    Field(
        "shell.bottom_layers",
        _("Bodenschichten"),
        "shell",
        kind="int",
        minimum=0,
        maximum=50,
        note=_("Volle Schichten auf dem Bett. Sie bestimmen, wie glatt die Unterseite wird."),
    ),
    Field(
        "shell.outer_wall_first",
        _("Außenwand zuerst"),
        "shell",
        kind="bool",
        note=_(
            "Legt die Außenbahn vor der Innenbahn. Das trifft Maße genauer und stützt Überhänge "
            "schlechter."
        ),
    ),
    Field(
        "shell.seam_position",
        _("Naht"),
        "shell",
        kind="enum",
        choices=("aligned", "nearest", "random", "rear"),
        note=_(
            "Wo die Naht jeder Schicht sitzt — die Stelle, an der eine Bahn beginnt und endet. "
            "Ausgerichtet ergibt eine sichtbare Linie, zufällig verteilt sie sich."
        ),
    ),
    Field(
        "shell.wall_generator",
        _("Wandbahnen"),
        "shell",
        kind="enum",
        choices=("classic", "arachne"),
        note=_(
            "Wie die Bahnen einer Wand verteilt werden. Arachne trifft schmale Stege, die auf "
            "keine ganze Bahnbreite passen; klassisch rechnet mit gleicher Breite und füllt den "
            "Rest."
        ),
    ),
    Field(
        "shell.precise_outer_wall",
        _("Außenwand auf Sollmaß"),
        "shell",
        kind="bool",
        note=_(
            "Rechnet die Außenwand auf ihr Sollmaß statt auf die Bahnmitte. Für Passungen "
            "richtig, sonst unnötig."
        ),
    ),
    Field(
        "shell.ironing",
        _("Oberfläche bügeln"),
        "shell",
        kind="bool",
        note=_(
            "Fährt die Oberseite ein zweites Mal ab und glättet sie mit wenig Material. Kostet "
            "Zeit und lohnt bei Sichtflächen."
        ),
    ),
    # --- Füllung ---
    Field(
        "infill.density",
        _("Fülldichte"),
        "infill",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
        front=True,
        note=_(
            "Wie viel Material im Inneren steht. 15 % ist Alltag, 40 % für Belastung, 0 % ergibt "
            "einen hohlen Körper."
        ),
    ),
    Field(
        "infill.pattern",
        _("Füllmuster"),
        "infill",
        kind="enum",
        choices=("grid", "gyroid", "honeycomb", "cubic", "lines", "triangles"),
        front=True,
        note=_(
            "Wie die Füllung gelegt wird. Gyroid trägt in alle Richtungen gleich, Gitter ist "
            "schneller, Wabe liegt dazwischen."
        ),
    ),
    Field(
        "infill.angle",
        _("Füllwinkel"),
        "infill",
        unit=DEGREE_UNIT,
        minimum=0.0,
        maximum=180.0,
        step=5.0,
        decimals=1,
        note=_(
            "Um wie viel die Füllung gedreht liegt. Bahnen längs der Belastung tragen mehr "
            "als querlaufende — bei einem Teil, das in eine bekannte Richtung belastet wird, "
            "lohnt das Drehen."
        ),
    ),
    # --- Temperaturen ---
    Field(
        "temperature.nozzle",
        _("Düse"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=400,
        front=True,
        note=_(
            "Wie heiß die Düse ist. Zu kalt heißt schwache Schichtbindung, zu heiß bringt Fäden "
            "und weiche Überhänge."
        ),
    ),
    Field(
        "temperature.nozzle_first_layer",
        _("Düse, erste Schicht"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=400,
        note=_("Meist etwas heißer als der Rest: Die erste Schicht soll auf dem Bett kleben."),
    ),
    Field(
        "temperature.bed",
        _("Bett"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=150,
        front=True,
        note=_(
            "Wie warm das Bett ist. Es hält das Teil unten fest und verhindert, dass es sich "
            "an den Ecken hochzieht."
        ),
    ),
    Field(
        "temperature.bed_first_layer",
        _("Bett, erste Schicht"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=150,
        note=_("Für die erste Schicht darf das Bett wärmer sein als danach."),
    ),
    Field(
        "temperature.chamber",
        _("Kammer"),
        "temperature",
        kind="int",
        unit="°C",
        minimum=0,
        maximum=90,
        note=_(
            "Temperatur im geschlossenen Bauraum — nur bei Druckern, die einen haben. ABS und ASA "
            "brauchen sie, PLA nicht."
        ),
    ),
    # --- Kühlung ---
    Field(
        "cooling.fan_speed",
        _("Lüfter"),
        "cooling",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
        note=_(
            "Wie stark der Lüfter läuft. Viel Kühlung gibt scharfe Kanten und schwächere "
            "Schichten; bei ABS deshalb wenig."
        ),
    ),
    Field(
        "cooling.bridge_fan_speed",
        _("Lüfter bei Brücken"),
        "cooling",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
        note=_(
            "Über einer Brücke darf mehr gekühlt werden: Die Bahn hängt frei und soll schnell "
            "fest sein."
        ),
    ),
    Field(
        "cooling.disable_first_layers",
        _("Lüfter aus für Schichten"),
        "cooling",
        kind="int",
        minimum=0,
        maximum=20,
        note=_(
            "So viele Schichten bleiben ungekühlt. Der Lüfter würde die erste Schicht vom "
            "Bett lösen."
        ),
    ),
    Field(
        "cooling.minimum_layer_time",
        _("Mindestzeit je Schicht"),
        "cooling",
        unit="s",
        minimum=0.0,
        maximum=120.0,
        step=1.0,
        decimals=0,
        note=_(
            "Wie lange eine Schicht mindestens dauert. Bei kleinen Querschnitten bremst der "
            "Drucker, damit die vorige Schicht fest wird."
        ),
    ),
    # --- Geschwindigkeit ---
    Field(
        "speed.outer_wall",
        _("Außenwand"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
        note=_("Tempo der sichtbaren Außenbahn. Langsamer heißt glatter und maßgenauer."),
    ),
    Field(
        "speed.inner_wall",
        _("Innenwand"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
        note=_("Tempo der inneren Bahnen. Sie sieht niemand — hier darf es schneller sein."),
    ),
    Field(
        "speed.infill",
        _("Füllung"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
        note=_("Tempo der Füllung. Nach oben begrenzt sie ohnehin der höchste Volumenstrom."),
    ),
    Field(
        "speed.top_surface",
        _("Oberfläche"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
        note=_("Tempo der Deckschichten. Langsam macht die Oberseite gleichmäßig."),
    ),
    Field(
        "speed.first_layer",
        _("Erste Schicht"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=5.0,
        decimals=1,
        note=_("Tempo der ersten Schicht. Langsam heißt haften."),
    ),
    Field(
        "speed.travel",
        _("Leerfahrt"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=1000.0,
        step=10.0,
        decimals=0,
        note=_("Tempo ohne Material. Schnell spart Zeit und schüttelt den Drucker mehr."),
    ),
    Field(
        "speed.bridge",
        _("Brücken"),
        "speed",
        unit="mm/s",
        minimum=1.0,
        maximum=200.0,
        step=5.0,
        decimals=1,
        note=_("Tempo über einer Brücke. Zu langsam hängt durch, zu schnell reißt."),
    ),
    Field(
        "speed.acceleration",
        _("Beschleunigung"),
        "speed",
        unit="mm/s²",
        minimum=100.0,
        maximum=30000.0,
        step=500.0,
        decimals=0,
        note=_("Wie hart der Drucker beschleunigt. Weniger heißt sauberere Ecken und mehr Zeit."),
    ),
    Field(
        "speed.outer_wall_acceleration",
        _("Beschleunigung Außenwand"),
        "speed",
        unit="mm/s²",
        minimum=100.0,
        maximum=30000.0,
        step=500.0,
        decimals=0,
        note=_(
            "Beschleunigung nur für die Außenbahn. Hier lohnt es, weniger zu nehmen als überall "
            "sonst."
        ),
    ),
    # --- Stützen ---
    Field(
        "support.style",
        _("Stützen"),
        "support",
        kind="enum",
        choices=("none", "grid", "tree"),
        front=True,
        note=_(
            "Ob und wie gestützt wird. Baum braucht weniger Material und lässt sich leichter "
            "abnehmen, Gitter trägt schwere Überhänge sicherer."
        ),
    ),
    Field(
        "support.placement",
        _("Stützen ansetzen"),
        "support",
        kind="enum",
        choices=("everywhere", "build_plate"),
        note=_(
            "Wo Stützen ansetzen dürfen. Nur vom Bett lässt das Modell selbst unberührt; "
            "überall stützt auch mitten darauf und hinterlässt Spuren."
        ),
    ),
    Field(
        "support.threshold_angle",
        _("Ab Winkel"),
        "support",
        unit=DEGREE_UNIT,
        minimum=0.0,
        maximum=90.0,
        step=5.0,
        decimals=1,
        note=_(
            "Ab welcher Neigung gestützt wird, gemessen zur Senkrechten. Was steiler steht, trägt "
            "sich selbst — wie steil, sagt der Überhangfächer."
        ),
    ),
    Field(
        "support.z_gap",
        _("Abstand nach oben"),
        "support",
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        step=0.05,
        decimals=2,
        note=_(
            "Luft zwischen Stütze und Teil nach oben. Mehr heißt leichter abnehmen und rauere "
            "Fläche darüber."
        ),
    ),
    Field(
        "support.xy_gap",
        _("Abstand zur Seite"),
        "support",
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        step=0.1,
        decimals=2,
        note=_("Luft zwischen Stütze und Teil zur Seite. Zu wenig verschweißt beides miteinander."),
    ),
    Field(
        "support.density",
        _("Stützdichte"),
        "support",
        unit="%",
        minimum=0.0,
        maximum=100.0,
        step=5.0,
        decimals=0,
        factor=100.0,
        note=_("Wie dicht die Stütze steht. Dichter trägt mehr und ist schwerer abzunehmen."),
    ),
    Field(
        "support.interface_layers",
        _("Trennschichten"),
        "support",
        kind="int",
        minimum=0,
        maximum=10,
        note=_(
            "Dichte Schichten zwischen Stütze und Teil. Sie machen die gestützte Fläche glatter."
        ),
    ),
    # --- Haftung ---
    Field(
        "adhesion.kind",
        _("Druckbetthaftung"),
        "adhesion",
        kind="enum",
        choices=("none", "skirt", "brim", "raft"),
        note=_(
            "Was zusätzlich auf das Bett kommt, damit das Teil hält. Brim legt einen Rand an, "
            "Raft eine ganze Unterlage; Skirt berührt das Teil nicht und hält nur die Düse im "
            "Fluss."
        ),
    ),
    Field(
        "adhesion.skirt_loops",
        _("Skirt-Runden"),
        "adhesion",
        kind="int",
        minimum=0,
        maximum=20,
        note=_("Wie viele Runden neben dem Teil gelegt werden, ohne es zu berühren."),
    ),
    Field(
        "adhesion.skirt_distance",
        _("Skirt-Abstand"),
        "adhesion",
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        step=0.5,
        decimals=1,
        note=_("Wie weit diese Runden vom Teil entfernt liegen."),
    ),
    Field(
        "adhesion.brim_width",
        _("Brim-Breite"),
        "adhesion",
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        step=0.5,
        decimals=1,
        note=_(
            "Wie breit der angelegte Rand ist. Mehr hält besser und muss hinterher abgeschnitten "
            "werden."
        ),
    ),
    Field(
        "adhesion.raft_layers",
        _("Raft-Schichten"),
        "adhesion",
        kind="int",
        minimum=0,
        maximum=20,
        note=_("Wie viele Schichten die Unterlage hat, auf der das Teil steht."),
    ),
    # --- Rückzug ---
    Field(
        "retraction.length",
        _("Rückzug"),
        "retraction",
        unit="mm",
        minimum=0.0,
        maximum=10.0,
        step=0.1,
        decimals=2,
        note=_(
            "Wie weit das Filament zurückgezogen wird, bevor die Düse leer fährt. Das Mittel "
            "gegen Fäden."
        ),
    ),
    Field(
        "retraction.speed",
        _("Rückzugstempo"),
        "retraction",
        unit="mm/s",
        minimum=1.0,
        maximum=200.0,
        step=5.0,
        decimals=0,
        note=_(
            "Wie schnell zurückgezogen wird. Zu schnell mahlt das Antriebsrad ins Filament, zu "
            "langsam zieht Fäden."
        ),
    ),
    Field(
        "retraction.z_hop",
        _("Z-Sprung"),
        "retraction",
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        step=0.05,
        decimals=2,
        note=_(
            "Wie weit die Düse anhebt, bevor sie leer fährt. Sie stößt dann nicht an schon "
            "Gedrucktes."
        ),
    ),
    Field(
        "retraction.wipe",
        _("Abstreifen"),
        "retraction",
        kind="bool",
        note=_("Wischt die Düse am Teil ab, bevor sie wegfährt. Weniger Nasen, etwas mehr Zeit."),
    ),
    Field(
        "retraction.avoid_crossing_walls",
        _("Wände nicht überfahren"),
        "retraction",
        kind="bool",
        note=_(
            "Führt Leerfahrten um Wände herum statt darüber. Weniger Narben auf der Oberfläche, "
            "längere Wege."
        ),
    ),
    # --- Filament ---
    # **Nicht vorn**, und der Grund ist die Spule: Sobald ein Teil einen
    # Materialslot mit eigener Farbe trägt, überschreibt ``handover`` diesen
    # Wert damit — die Farbe gehört dorthin, wo sie gewählt wird. Zwei Orte für
    # dieselbe Auskunft heißen raten, welcher gilt (Robert, 30.08.2026). Im
    # Modell bleibt sie: Ein Teil ganz ohne Spule hat sonst keine Farbe für den
    # Slicer, und ein Rückfall gehört nach hinten, nicht auf die Vorderseite.
    Field(
        "filament.colour",
        _("Farbe ohne eigene Spule"),
        "filament",
        kind="colour",
        note=_(
            "Gilt nur, solange das Teil keine eingefärbte Spule hat — dann steht hier, womit "
            "der Slicer rechnet. Sobald Sie im Filamentwähler eine Farbe setzen oder über "
            "*Fläche färben* arbeiten, gilt die Spule."
        ),
    ),
    Field(
        "filament.diameter",
        _("Filamentdurchmesser"),
        "filament",
        unit="mm",
        minimum=1.0,
        maximum=4.0,
        step=0.05,
        decimals=2,
        note=_("Der Durchmesser des Filaments, wie die Rolle ihn angibt — 1,75 mm oder 2,85 mm."),
    ),
    Field(
        "filament.density",
        _("Dichte"),
        "filament",
        unit="g/cm³",
        minimum=0.5,
        maximum=3.0,
        step=0.01,
        decimals=2,
        note=_("Dichte des Materials. Daraus rechnet die Schätzung das Gewicht."),
    ),
    Field(
        "filament.flow_ratio",
        _("Flussfaktor"),
        "filament",
        minimum=0.5,
        maximum=1.5,
        step=0.01,
        decimals=3,
        note=_(
            "Feinkorrektur der Materialmenge. Über 1 legt mehr, darunter weniger — geändert wird "
            "das nach einem gemessenen Prüfwürfel."
        ),
    ),
    Field(
        "filament.max_flow",
        _("Höchster Volumenstrom"),
        "filament",
        unit="mm³/s",
        minimum=0.5,
        maximum=60.0,
        step=0.5,
        decimals=1,
        note=_(
            "Wie viel Material die Düse je Sekunde schafft. Diese Grenze bremst jedes Tempo, das "
            "mehr verlangt."
        ),
    ),
    Field(
        "filament.cost_per_kg",
        _("Preis je Kilogramm"),
        "filament",
        minimum=0.0,
        maximum=1000.0,
        step=1.0,
        decimals=2,
        note=_("Was ein Kilogramm kostet. Nur für die Kostenschätzung."),
    ),
)


#: Nur Werte, die physisch an der Spule hängen (§20). Die Farbe fehlt
#: absichtlich: Sie gehört dem Materialslot und wird im Filamentwähler gesetzt.
#: Schichthöhe, Wände und Geschwindigkeit gelten dem Teil und dürfen hier nie
#: auftauchen — sonst erhielte ein zweifarbiges Teil zwei Geometrien.
FILAMENT_GROUPS: Final = ("temperature", "cooling", "retraction", "filament")
FILAMENT_FIELDS: tuple[Field, ...] = tuple(
    field
    for field in FIELDS
    if field.path.partition(".")[0] in FILAMENT_GROUPS and field.path != "filament.colour"
)


def _toggle_of(section: QWidget) -> QToolButton | None:
    """Der Umschalter eines Abschnitts aus :func:`panels.collapsible`.

    Der Helfer gibt die Hülle zurück und nicht den Knopf; hier wird der Knopf
    zweimal gebraucht — einmal, um den Dehnungsfaktor des Dialogs nachzuziehen,
    einmal, um einen Abschnitt von selbst aufzuklappen, wenn eine Entscheidung
    darin ansteht.
    """
    return section.findChild(QToolButton)


def _select_data(box: QComboBox, identifier: str) -> None:
    """Wählt den Eintrag mit dieser Kennung, wenn es ihn gibt."""
    index = box.findData(identifier)
    if index >= 0:
        box.setCurrentIndex(index)


def settings_for_export(
    document: Any, profile: Profile, ui_settings: UiSettings
) -> PrintSettings | None:
    """Welche Druckeinstellungen mit einer Datei hinausgehen — oder keine (§29).

    Die Entscheidung stand als verschachtelter Ausdruck im Aufruf des
    Export-Arbeiters und war damit von außen nicht prüfbar. Sie hat drei
    Fälle, und der dritte fehlte bis zum 03.09.2026 ganz:

    * Das Projekt trägt eigene Werte — die gelten.
    * Es trägt keine — dann wird aus Stufe, Material und Drucker aufgelöst.
      ``None`` im Dokument heißt „Dialog nie geöffnet", nicht „keine Werte".
    * **Der Kunde will keine mitgeben** — dann geht nur Geometrie hinaus, und
      sein Slicer arbeitet mit dem eigenen Profil.

    Ohne den dritten Fall gab es keine 3MF ohne Solidons Werte: Der Ausgang im
    Kern (``writer._plate_settings`` gibt bei ``None`` ein leeres Verzeichnis
    zurück) war von der Anwendung aus nicht erreichbar, weil hier immer
    aufgelöst wurde.
    """
    if not ui_settings.print_settings_in_files:
        return None
    stored = document.print_settings
    return stored if stored is not None else print_settings.resolve(profile)


def remembered_setup(
    settings: UiSettings, material: str = "", printer_id: str = ""
) -> handover.SlicerSetup | None:
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

    ``printer_id`` ist der Drucker, für den gerade exportiert wird. Weicht er
    von dem ab, für den die Profile gewählt wurden, gilt nichts davon: Ein
    Maschinenprofil gehört zu genau einem Drucker, und das des letzten Projekts
    an das nächste weiterzureichen wäre schlimmer als gar keines — die Datei
    sähe vollständig aus und zeigte auf die falsche Maschine. Ohne Vermerk
    (Einstellungen aus einer älteren Version) wird nicht verglichen.

    Und dieselbe Frage an den **Slicer**: Weicht der gefundene vom
    vermerkten ab, gelten die Profile nicht — sie stammen aus dem Bestand
    eines anderen Programms. Auch hier gilt: ohne Vermerk kein Vergleich.

    ``None``, solange kein Druckerprofil gemerkt ist: Die Suche nach dem
    Programm geht über PATH, Registry und die üblichen Orte und kostet eine
    halbe Sekunde. Wer den Slicer nie eingerichtet hat, bekäme dafür ein Setup
    ohne Maschine — also nichts, was die Kette auflösen könnte.
    """
    if not settings.slicer_machine_profile:
        return None
    chosen_for = settings.slicer_profile_printer
    if printer_id and chosen_for and chosen_for != printer_id:
        return None
    found = discover.find_program("slicer", tools.SLICERS)
    if found is None:
        return None
    # Dieselbe Regel für den Slicer wie für den Drucker: Die Profile gehören
    # zu dem Programm, mit dem sie gewählt wurden — ein Orca-Maschinenprofil
    # ist für PrusaSlicer eine fremde Datei. Leer heißt „von früher", dann
    # wird nicht verglichen: Bestandskunden verlören sonst ihre Profilwahl
    # mit der ersten Aktualisierung (Begründung am Feld in settings.py).
    chosen_with = settings.slicer_profile_slicer
    if chosen_with and str(found) != chosen_with:
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

    def __init__(self, value: str, parent: QWidget | None = None, note: str = "") -> None:
        super().__init__(parent)
        self._value = value
        self._note = note
        """Was das Feld tut — der Knopf schreibt es hinter den Farbwert.

        Er baut seinen Tooltip in :meth:`_refresh` selbst neu, sobald sich die
        Farbe ändert; ein von außen gesetzter Satz wäre beim ersten Klick weg."""
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
        exact = self._value.upper()
        self.setToolTip(f"{exact} — {self._note}" if self._note else exact)
        self.setStyleSheet(f"background-color: {self._value}; color: {readable};")

    def _choose(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._value), self, tr("Filamentfarbe"))
        if chosen.isValid():
            self.set_value(chosen.name())
            self.changed.emit(self._value)


def swatch_size(reference: QWidget) -> int:
    """Wie groß ein Farbfeld neben diesem Text sein muss.

    Die Farbe einer Spule steht in zwei Lagen: in einer Liste, wo sie neben
    ihren Geschwistern nur unterscheiden muss, und als Überschrift, wo sie
    allein sagt, welche Spule gemeint ist. Für die erste genügen die vierzehn
    Punkte aus dem Filamentwähler; für die zweite ist das zu wenig (Befund
    B28: „die wichtigste Eigenschaft als unauffälligstes Element").

    Gerechnet aus der Zeile statt als Zahl daneben — die Schrift skaliert
    (§19.3), und eine Konstante wäre bei der nächsten Größe wieder zu klein.
    """
    return max(SWATCH_PIXELS, reference.sizeHint().height())


def _make_setting_editor(
    field: Field,
    parent: QWidget,
    changed: Callable[..., None],
) -> QWidget:
    """Baut dasselbe Einstellungsfeld für beide Druckdialoge.

    Der große Druckdialog und die Werte einer einzelnen Spule dürfen nicht
    zwei verschiedene Zahlenfelder für dieselbe Sache führen. Grenzen,
    Einheiten, Auswahlwerte und Hilfesätze kommen deshalb aus derselben
    :data:`FIELDS`-Zeile und gehen durch diesen einen Bauweg.
    """
    editor: QWidget
    if field.kind == "bool":
        editor = QCheckBox(parent)
        editor.toggled.connect(changed)
    elif field.kind == "int":
        spin = QSpinBox(parent)
        spin.setRange(int(field.minimum), int(field.maximum))
        spin.valueChanged.connect(changed)
        editor = spin
    elif field.kind == "enum":
        combo = QComboBox(parent)
        for choice in field.choices:
            combo.addItem(choice_label(choice), choice)
        explain_choices(combo)
        combo.currentIndexChanged.connect(changed)
        editor = combo
    elif field.kind == "colour":
        button = _ColourButton("#000000", parent, note=str(field.note))
        button.changed.connect(changed)
        editor = button
    else:
        number = NumberSpin(parent)
        number.setRange(field.minimum, field.maximum)
        number.setSingleStep(field.step)
        number.setDecimals(field.decimals)
        number.valueChanged.connect(changed)
        editor = number

    # **Die Einheit steht am Wert, nicht in der Beschriftung** (§19.3, B12).
    # „Schichthöhe [mm]" über einem Feld mit „0,200" war die eine Schreibweise,
    # die das Haus überall sonst abgelegt hat — die Leisten schreiben
    # „20,00 mm" in den Wert. Am Suffix steht sie dort, wo der Wert steht.
    if field.unit and isinstance(editor, QAbstractSpinBox):
        editor.setSuffix(f" {field.unit}")

    limit = FIELD_WIDTH.get(field.kind)
    if limit is not None:
        editor.setMaximumWidth(max(limit, editor.sizeHint().width()))
    note = str(field.note)
    if note:
        if not editor.toolTip():
            editor.setToolTip(note)
        editor.setStatusTip(note)
        editor.setAccessibleDescription(note)
    return editor


def _set_setting_editor(editor: QWidget, field: Field, value: object) -> None:
    """Schreibt einen Modellwert in sein Feld."""
    if isinstance(editor, QCheckBox):
        editor.setChecked(bool(value))
    elif isinstance(editor, QSpinBox):
        editor.setValue(int(cast(Any, value)))
    elif isinstance(editor, QComboBox):
        editor.setCurrentIndex(max(editor.findData(str(value)), 0))
    elif isinstance(editor, _ColourButton):
        editor.set_value(str(value))
    elif isinstance(editor, QDoubleSpinBox):
        editor.setValue(float(cast(Any, value)) * field.factor)


def _setting_editor_value(editor: QWidget, field: Field) -> object:
    """Liest den Modellwert aus seinem Feld."""
    if isinstance(editor, QCheckBox):
        return editor.isChecked()
    if isinstance(editor, QSpinBox):
        return editor.value()
    if isinstance(editor, QComboBox):
        return editor.currentData()
    if isinstance(editor, _ColourButton):
        return editor.value()
    if isinstance(editor, QDoubleSpinBox):
        return float(editor.value()) / field.factor
    raise TypeError(type(editor).__name__)


class FilamentOverrideDialog(QDialog):
    """Eigene Druckwerte einer Spule, gruppenweise und ohne CAD-Begriffe.

    Ausgeschaltet bedeutet Projektwert. Wer nur die Düsentemperatur ändern
    will, schaltet „Temperaturen" ein; der vollständige Bereich ist mit den
    Projektwerten vorbelegt und genau ein Wert muss geändert werden. Das ist
    der Vertrag von :class:`SlotOverride`, sichtbar in der Oberfläche.
    """

    def __init__(
        self,
        slot: MaterialSlot,
        settings: PrintSettings,
        existing: SlotOverride | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.slot = slot
        self.settings = settings
        self.existing = existing
        self.editors: dict[str, QWidget] = {}
        self.groups: dict[str, QGroupBox] = {}
        self.group_bodies: dict[str, QWidget] = {}

        name = str(slot.name) or tr("Filament")
        self.setWindowTitle(f"{tr('Druckeinstellungen')} — {name}")
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)

        heading = QWidget(self)
        heading_layout = QHBoxLayout(heading)
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(TIGHT)
        title = QLabel(name, heading)
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        colour = QLabel(heading)
        # **So hoch wie die Zeile, in der sie steht** (Befund B28). Vierzehn
        # Punkte sind das Maß einer Listenzeile, wo die Farbe neben zwanzig
        # Geschwistern nur unterscheiden muss. Hier steht sie allein und sagt,
        # welche Spule gemeint ist — ein dunkles Blau von einem dunklen Grau zu
        # trennen verlangt Fläche. Gerechnet statt gesetzt, weil die Schrift
        # skaliert (§19.3): eine feste Zahl wäre bei der nächsten Schriftgröße
        # wieder zu klein.
        edge = swatch_size(title)
        colour.setPixmap(swatch(shown_colour(int(slot.index), slot.colour)).pixmap(edge, edge))
        colour.setAccessibleName(tr("Filamentfarbe"))
        heading_layout.addWidget(colour)
        heading_layout.addWidget(title, 1)
        layout.addWidget(heading)

        intro = QLabel(
            tr(
                "Nur was diese Spule anders braucht. Ausgeschaltete Bereiche "
                "benutzen die Projektwerte."
            ),
            self,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        contents = QWidget(scroll)
        sections = QVBoxLayout(contents)
        self._scroll = scroll
        self._section_contents = contents
        self._sections = sections
        sections.setContentsMargins(0, TIGHT, 0, TIGHT)
        sections.setSpacing(TIGHT)
        titles = {
            "temperature": tr("Temperaturen"),
            "cooling": tr("Kühlung"),
            "retraction": tr("Rückzug"),
            "filament": tr("Filament"),
        }
        for group in FILAMENT_GROUPS:
            box = QGroupBox(titles[group], contents)
            box.setCheckable(True)
            own_section = getattr(existing, group) if existing is not None else None
            box.setChecked(own_section is not None)
            explanation = tr("Eingeschaltet gelten diese Werte nur für die gewählte Spule.")
            box.setToolTip(explanation)
            box.setAccessibleDescription(explanation)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(TIGHT, TIGHT, TIGHT, TIGHT)
            body = QWidget(box)
            form = QFormLayout(body)
            form.setContentsMargins(0, 0, 0, 0)
            source = own_section or getattr(settings, group)
            for field in (
                entry for entry in FILAMENT_FIELDS if entry.path.partition(".")[0] == group
            ):
                editor = _make_setting_editor(field, body, lambda *_args: None)
                _set_setting_editor(editor, field, getattr(source, field.path.partition(".")[2]))
                self.editors[field.path] = editor
                label = QLabel(
                    f"{field.title!s} [{field.unit}]" if field.unit else str(field.title),
                    body,
                )
                note = str(field.note)
                if note:
                    label.setToolTip(note)
                    label.setStatusTip(note)
                form.addRow(label, editor)
            box_layout.addWidget(body)
            box.toggled.connect(body.setVisible)
            box.toggled.connect(self._fit_depth)
            body.setVisible(box.isChecked())
            self.groups[group] = box
            self.group_bodies[group] = body
            sections.addWidget(box)
        sections.addStretch(1)
        scroll.setWidget(contents)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText(tr("Übernehmen"))
        make_primary(ok)
        self.project_values_button = buttons.addButton(
            tr("Projektwerte verwenden"), QDialogButtonBox.ButtonRole.ResetRole
        )
        self.project_values_button.clicked.connect(self._use_project_values)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._fit_depth()

    def _fit_depth(self, _checked: bool | None = None) -> None:
        """Die Dialoghöhe an geöffnete Gruppen und den Bildschirm anpassen."""
        self._sections.activate()
        self._section_contents.adjustSize()
        available = self.screen().availableGeometry().height()
        maximum = max(240, int(available * 0.55))
        wanted = min(self._section_contents.sizeHint().height(), maximum)
        self._scroll.setMinimumHeight(wanted)
        self.adjustSize()

    def _use_project_values(self) -> None:
        """Alle eigenen Gruppen sichtbar und eindeutig zurücknehmen."""
        for field in FILAMENT_FIELDS:
            group, _separator, name = field.path.partition(".")
            value = getattr(getattr(self.settings, group), name)
            _set_setting_editor(self.editors[field.path], field, value)
        for box in self.groups.values():
            box.setChecked(False)

    def override(self) -> SlotOverride | None:
        """Die vier Gruppen aus den Feldern, oder Projektwerte für alle."""
        values: dict[str, Any] = {}
        for group in FILAMENT_GROUPS:
            if not self.groups[group].isChecked():
                continue
            previous = getattr(self.existing, group) if self.existing is not None else None
            section = previous or getattr(self.settings, group)
            changed = {
                field.path.partition(".")[2]: _setting_editor_value(self.editors[field.path], field)
                for field in FILAMENT_FIELDS
                if field.path.partition(".")[0] == group
            }
            values[group] = replace(section, **changed)
        if not values:
            return None
        return SlotOverride(name=self.slot.name, colour=self.slot.colour, **values)


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
    model_height: float | None = None
    """Wie hoch die Teile dieser Platte sind, in mm.

    Für den Vergleich mit der Höhe, die im G-Code tatsächlich gefahren wird:
    Cura druckte bei zentriert importiertem Modell still die halbe Höhe — was
    unter dem Druckbett lag, fiel weg, und niemand sah es (Handlauf,
    30.08.2026). Ohne die Angabe entfällt der Vergleich; geraten wird nichts.
    """
    findings: tuple[Finding, ...] = ()
    """Was beim Schreiben der Baugruppe auffiel — Haftungsränder,
    Filamentwechsel. Sie reisen mit ihrer Platte, damit im Prüfbericht steht,
    welche gemeint ist."""


class _SliceWorker(Worker):
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
    failed = Signal(object, object)
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

    def work(self) -> None:
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
                    model_height=entry.model_height,
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
                self.failed.emit(problem, list(entry.findings))
                return
            outcome.findings = [*entry.findings, *outcome.findings]
            results.append(outcome)
        self.done.emit(results)


class _ProfileWorker(Worker):
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

    def work(self) -> None:
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


def _slicer_title(path: Path) -> str:
    """Ein Name, den ein Mensch wiedererkennt — der Installationsordner.

    „elegoo-slicer.exe" und „prusa-slicer-console.exe" sind Dateinamen; was
    auf der Packung steht, ist „ElegooSlicer" und „PrusaSlicer". Der Ordner
    trägt genau das, und bei Cura sogar die Version („UltiMaker Cura 5.13.0"),
    was bei zwei installierten Fassungen der Unterschied ist.
    """
    folder = path.parent.name
    return folder or path.stem


class PrintSettingsDialog(QDialog):
    """Alle Druckeinstellungen, die Vorschläge dazu, und der Weg zum G-Code."""

    sliced = Signal(object)
    """Die Befunde des Laufs, für den Prüfbericht des Fensters."""

    reported = Signal(object)
    """Die Vorprüfung einer Platte, wenn der Slicer danach abbricht.

    Bei einem erfolgreichen Lauf reisen dieselben Befunde im
    :class:`SliceOutcome`. Im Fehlerfall gab es bisher keinen Rückweg: Gerade
    „zu groß“ und „nicht geschlossen“ verschwanden hinter dem allgemeineren
    Satz des Fremdprogramms.
    """

    setupRequested = Signal()
    """Es ist kein Slicer eingerichtet, und jemand möchte einen.

    Regel 17: „Kein Slicer eingerichtet" sagte, was fehlt, und bot nichts an —
    an der Stelle, an der jemand gerade slicen wollte. Von hier führt der Weg
    in die Liste der zusätzlichen Programme, und danach sieht der Dialog noch
    einmal nach (:meth:`recheck_slicer`)."""

    filamentsRequested = Signal()
    """Die Kopfzeile berichtet das Material, gewählt wird es an der Spule.

    Ein Label, das auf den Filamentwähler verweist und den Kunden dann suchen
    lässt, ist die halbe Antwort — das Fenster klappt den Abschnitt auf und
    lässt ihn aufleuchten."""

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
        self._labels: dict[str, QLabel] = {}
        #: Wo die Suche gerade steht — Begriff, Trefferliste, Platz darin.
        self._search_term = ""
        self._search_hits: list[str] = []
        self._search_at = -1
        self._lifted = ""
        self._fields: dict[str, Field] = {}
        self._loading = False
        self._worker: _SliceWorker | None = None
        self._profile_worker: _ProfileWorker | None = None
        self._leash = WorkerLeash(self)
        """Hält ausgelaufene Arbeiter, bis Qt mit ihnen durch ist — das
        Warum steht in :mod:`app.ui.leash`."""
        self._profiles: list[slicer_profiles.SlicerProfile] = []
        self._needs_profiles = False
        """Ob der gefundene Slicer Profile verlangt (nur die Orca-Familie)."""
        self._profiles_pending = False
        """Ob die Profilsuche noch läuft — solange sagt der Knopf „wird
        durchgesehen" statt „bitte wählen": kein Zustand ohne Erhebung."""
        self._temporary: TemporaryDirectory[str] | None = None
        self._gcode: list[Path] = []
        """Die Druckdateien des letzten Laufs — eine je Platte."""
        self._state_shows_reason = False
        """Ob in der Zustandszeile gerade ein **Sperr-Grund** steht.

        Die Zeile trägt zweierlei: das Ergebnis des letzten Laufs und den
        Grund, warum gerade nicht geslicet werden kann. Beide sind verschieden
        alt — ein Ergebnis bleibt gültig, bis ein neuer Lauf es ersetzt, ein
        Grund gilt nur, solange er zutrifft. Ohne diese Unterscheidung blieb
        „Dieser Slicer braucht ein Druckerprofil" nach dem Wechsel auf
        PrusaSlicer stehen, während der Knopf schon frei war — ein Widerspruch
        auf demselben Bildschirm (Handlauf 3d-druck-55, 30.08.2026)."""
        self._settled = False
        """Ob schon aufgeräumt wurde — es gibt drei Wege hinaus (siehe
        :meth:`_settle`)."""
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
        # Woran :meth:`has_changes` misst, ob dieser Dialog etwas bewirkt hat.
        # Bis zum 03.09.2026 schrieb schon das bloße Öffnen die aufgelösten
        # Werte ins Projekt: Wer nur nachsah, welche Temperatur vorgeschlagen
        # würde, hatte sie danach im Dokument — und jede exportierte 3MF trug
        # sie mit, ohne Weg zurück.
        self._opened_with = self.settings
        # Einmal suchen, dreimal gebraucht: die Suche geht über PATH,
        # Registry und die üblichen Installationsorte und kostet eine halbe
        # Sekunde — dreimal wäre die Hälfte der Zeit, die der Dialog zum
        # Aufgehen braucht.
        self._slicer_path = self._pick_slicer()

        layout = QVBoxLayout(self)
        # **Vor** dem Slicer-Abschnitt: Dessen Filamentzeilen fragen die
        # Plattenwahl bereits beim Aufbau (``_plate_slots``). Erzeugt
        # wird sie deshalb hier, eingehängt wird sie weiter unten in
        # ``_build_state`` — dort, wo der Kunde sie braucht.
        self._make_plate_row()
        layout.addLayout(self._build_head())
        layout.addWidget(self._build_front())
        # **Über der Klappe, nicht darin.** Wer sucht, weiß gerade nicht, wo
        # das Gesuchte steht — ein Suchfeld in „Weitere Einstellungen" fände
        # nur, wer den Bereich schon offen hat. Es steht deshalb frei darüber
        # und klappt selbst auf, wenn der Treffer dahinter liegt.
        layout.addLayout(self._build_search())
        layout.addWidget(self._build_tabs(), 1)
        layout.addWidget(self._build_slicer())
        layout.addWidget(self._build_advice())
        layout.addWidget(self._build_state())
        layout.addWidget(self._build_buttons())

        self._load_into_editors()
        self._refresh_advice()
        self._start_profile_search()
        # Zuletzt, wenn jede Zeile steht: eine Beschriftungsspalte für den
        # ganzen Dialog. Zehn Formulare rechneten sie bis hierhin einzeln, und
        # die Felder begannen an zehn Stellen (B8/B11).
        align_forms(self)

    def has_changes(self) -> bool:
        """Hat der Kunde in diesem Dialog etwas bewirkt?

        Gefragt wird nicht, ob er einen Knopf gedrückt hat, sondern ob am Ende
        etwas anderes dasteht als am Anfang — das erfasst jeden der sieben
        Wege, auf denen sich ``settings`` ändert (Feld, Stufe, Vorschläge,
        Slot-Profil, übernommene Werte, Übergabeart), und kann nicht veralten,
        wenn ein achter dazukommt.

        Wer nur nachsieht, bewirkt nichts: Sein Projekt bleibt ohne
        Druckeinstellungen, und eine exportierte 3MF trägt weiter nur
        Geometrie. Das ist kein Verlust — beim nächsten Öffnen löst der Dialog
        aus Stufe, Material und Drucker dieselben Werte wieder auf.
        """
        return self.settings != self._opened_with

    def take_slice_result(self, result: SliceResult | None) -> None:
        """Die nachgereichte Schichtanalyse übernehmen (§2.8, §29).

        Der Dialog geht auf, sobald er kann, und nicht erst, wenn die Analyse
        fertig ist: Auf sie zu warten hielt den Weg zu den Druckeinstellungen
        bis zu zwei Sekunden auf, mit stehendem Fenster und ohne dass irgendwo
        stand, worauf.

        Was aus der Geometrie folgt — Stützen, Haftung, Mindestschichtzeit —,
        kommt damit ein paar Zehntel später in die Vorschlagsliste, statt den
        ganzen Dialog aufzuhalten. Ein ``None`` ändert nichts: dann bleibt es
        bei dem, was aus Material und Maschine folgt.
        """
        if result is None:
            return
        self.slice_result = result
        self._refresh_advice()

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

        # **Das Material wird hier nicht mehr gewählt, sondern berichtet.**
        # Es kommt aus der Spule (``profiles.for_object``), und eine zweite
        # Wahl daneben hieße, etwas einzustellen, was das Filament schon sagt —
        # „das material kommt ja auch aus dem filament" (Robert, 30.08.2026).
        # Der Wert steht mit seiner Herkunft da: Ohne Spule ist es die
        # Projektvorgabe, und das gehört dazugesagt.
        self.material_state = QLabel(self)
        self.material_state.setTextFormat(Qt.TextFormat.PlainText)
        # Kein totes Label: Gewählt wird im Filamentwähler, und von hier führt
        # ein Weg dorthin (Regel 17 in ihrer freundlichen Gestalt — sagen, was
        # jetzt möglich ist, statt nur zu berichten).
        self.material_link = QPushButton(tr("Filamente …"), self)
        self.material_link.setToolTip(
            tr("Öffnet links den Abschnitt „Filamente“ — dort wird die Spule gewählt.")
        )
        self.material_link.setStatusTip(self.material_link.toolTip())
        self.material_link.setAccessibleDescription(self.material_link.toolTip())
        self.material_link.clicked.connect(self.filamentsRequested)
        self.refresh_materials()

        # Ob diese Werte die Anwendung verlassen (§29). Der Druckhinweis fragt
        # es einmal; hier steht die Antwort zum Nachsehen und Ändern — sonst
        # wäre die Wahl eine Einbahnstraße, und genau das war der Fehler, den
        # dieser Umschalter behebt.
        self.share_settings = QCheckBox(tr("Werte mitgeben"), self)
        self.share_settings.setChecked(self.ui_settings.print_settings_in_files)
        self.share_settings.setToolTip(
            tr(
                "Mit Haken tragen eine gespeicherte 3MF und die Übergabe an den Slicer "
                "diese Werte. Ohne Haken geht nur die Geometrie hinaus, und Ihr Slicer "
                "arbeitet mit seinem eigenen Profil."
            )
        )
        self.share_settings.setStatusTip(self.share_settings.toolTip())
        self.share_settings.setAccessibleDescription(self.share_settings.toolTip())
        self.share_settings.toggled.connect(self._share_toggled)

        row.addWidget(QLabel(tr("Qualität"), self))
        row.addWidget(self.quality, 1)
        row.addWidget(QLabel(tr("Drucker"), self))
        row.addWidget(self.printer_choice, 1)
        row.addWidget(QLabel(tr("Material"), self))
        row.addWidget(self.material_state, 1)
        row.addWidget(self.material_link)
        row.addWidget(self.share_settings)
        return row

    def _share_toggled(self, on: bool) -> None:
        """Die Wahl gilt für die Anwendung, nicht für dieses Projekt (§29).

        Dieselbe Trennung wie bei der Slicer-Wahl: Ein Projekt wandert auf
        einen anderen Rechner, die Arbeitsweise seines Besitzers nicht. Sofort
        gespeichert, damit sie auch dann steht, wenn die Anwendung nach dem
        Dialog nicht mehr regulär endet.
        """
        self.ui_settings.print_settings_in_files = on
        save_settings(self.ui_settings)

    def show_materials(self, materials: Sequence[str]) -> None:
        """Woraus sich das Material ergibt — die Liste, sonst die Vorgabe
        samt Herkunft.

        Mehrere Materialien werden aufgezählt und nicht auf eines verkürzt:
        Der Kunde soll sehen, was wirklich gedruckt wird. Für die *Toleranz*
        entscheidet je Körper Slot 0 (§20) — das ist eine Rechnung und keine
        Anzeige.
        """
        names = [name for name in dict.fromkeys(materials) if name]
        if names:
            self.material_state.setText(" + ".join(names))
            self.material_state.setToolTip(
                tr("Kommt aus den Körpern der Szene. Zum Ändern die Spule wechseln.")
            )
        else:
            fallback = self.session.project.document.material or profiles.DEFAULT_MATERIAL
            title = str(profiles.material(fallback).title)
            self.material_state.setText(f"{title} — {tr('Projektvorgabe')}")
            self.material_state.setToolTip(
                tr("Noch keine Spule gewählt — solange gilt die Vorgabe des Projekts.")
            )
        self.material_state.setStatusTip(self.material_state.toolTip())
        self.material_state.setAccessibleDescription(self.material_state.toolTip())

    def refresh_materials(self) -> None:
        """Die Anzeige aus den Körpern der gewählten Platten neu setzen."""
        self.show_materials(self._materials_of(self._plate_bodies()))

    def _materials_of(self, bodies: Sequence[SceneObject]) -> list[str]:
        """In welchen Materialien diese Körper wirklich gedruckt werden.

        **Gefragt wird dasselbe wie bei der Toleranz** (:func:`profiles.for_object`)
        — eigenes Material des Körpers, sonst seine Spule, sonst die Vorgabe des
        Projekts. Zwei Wege zu derselben Auskunft wären einer zu viel, und der
        erste Anlauf hier war genau das: Er las nur die Spulen und schrieb
        daneben „PLA — Projektvorgabe", während ein Körper aus TPU auf dem Bett
        lag (Robert, 30.08.2026: „warum aber noch material pla falls einer
        unterschiedliche materialien hat").

        Die **weiteren** Spulen eines Körpers kommen dazu: Für die Toleranz
        entscheidet Slot 0, gedruckt wird trotzdem auch der Schriftzug daneben,
        und wer wissen will, was er einlegen muss, will beide sehen. Leer heißt:
        Es gibt nichts anzuzeigen — dann nennt :meth:`show_materials` die
        Vorgabe und sagt dazu, dass sie eine ist.
        """
        project = self.session.profile
        names: list[str] = []
        for body in bodies:
            # ``for_object`` gibt das **übergebene** Profil unverändert zurück,
            # wo der Körper nichts Eigenes hat — daran hängt hier die
            # Unterscheidung: hergeleitet wird genannt, Vorgabe nennt sich
            # unten selbst als solche. Ein Körper, der ausdrücklich das
            # Projektmaterial trägt, zählt zur Vorgabe, und das ist wahr.
            chosen = profiles.for_object(project, body)
            if chosen is not project:
                names.append(str(chosen.material.title))
            for slot in body.material_slots:
                if slot.index == 0 or not slot.material_type:
                    continue
                known = profiles.material_id_for_type(slot.material_type)
                names.append(str(profiles.material(known).title) if known else slot.material_type)
        return names

    def _plate_bodies(self) -> list[SceneObject]:
        """Die Körper der gewählten Platten — dieselbe Auswahl wie
        :meth:`_plate_slots`, nur eine Ebene davor."""
        result = self.session.last_result
        if result is None:
            return []
        wanted = set(self._chosen_plates())
        return [entry for entry in result.scene.objects.values() if entry.plate in wanted]

    def _scene_profile_changed(self) -> None:
        """Ein anderer Drucker heißt andere Vorgaben — und eine Neuauswertung.

        Sofort statt beim Schließen: die Vorschläge in diesem Dialog hängen an
        Maschine und Material, und sie stehen lassen, während oben etwas
        anderes gewählt ist, wäre eine Anzeige, die nicht mehr stimmt.

        **Das Material bleibt dabei, wie es ist.** Es wird hier nicht mehr
        gewählt (es kommt aus der Spule), und der Drucker geht es nichts an —
        wer die Maschine wechselt, wechselt nicht das Filament.

        **Was der Kunde selbst gesetzt hat, überlebt den Wechsel.** Hier stand
        ein blankes ``resolve``, und das warf jeden übersteuerten und jeden
        mitgebrachten Wert weg — gemessen: 62 % Füllung aus einer eingelesenen
        3MF wurden beim Umstellen des Druckers wortlos zu 15 %. Ein Drucker
        wechselt *Vorgaben*; eine Entscheidung ist keine Vorgabe.

        Was eine Entscheidung ist, sagt der Vergleich mit den **alten**
        Vorgaben: Wo der heutige Wert von dem abweicht, was das alte Profil
        vorgeschlagen hätte, hat jemand Hand angelegt. Alles andere wird neu
        aufgelöst — und das ist genau der Sinn des Wechsels.

        Der Unterschied zu :meth:`_quality_changed` ist Absicht: Eine Stufe zu
        wechseln *heißt*, alles neu vorgeben zu lassen; einen Drucker zu
        wechseln heißt es nicht.
        """
        # Vor dem Umschalten lesen: danach ist ``session.profile`` das neue.
        old_defaults = print_settings.resolve(self.session.profile, self.settings.quality)
        chosen = {
            field.path: print_settings.read_path(self.settings, field.path)
            for field in FIELDS
            if not _same_value(
                print_settings.read_path(self.settings, field.path),
                print_settings.read_path(old_defaults, field.path),
            )
        }

        document = self.session.project.document
        self.session.change_scene_profile(
            str(self.printer_choice.currentData()),
            document.material or profiles.DEFAULT_MATERIAL,
        )
        settings = self._resolved(self.settings.quality)
        for path, value in chosen.items():
            settings = print_settings.with_path(settings, path, value)
        self.settings = settings
        self._load_into_editors()
        self._refresh_advice()
        self._refill_slicer_profiles()

    def _refill_slicer_profiles(self) -> None:
        """Die Profilfelder folgen dem Drucker des Projekts (§29).

        **Sie taten es nicht, und das traf Roberts eigenen Drucker.** Gemessen
        am 03.09.2026 (Fund von 3d-druck-c7, hier nachgestellt): Der Dialog
        öffnet mit dem Drucker aus den Einstellungen, bei frischem Stand also
        dem allgemeinen 220er. Für den ordnet sich kein Profil zu, die
        Notbremse in :meth:`_machines_worth_showing` zeigt deshalb den ganzen
        Bestand. Danach stellt der Kunde seinen Drucker ein — und die Liste
        blieb, wie sie war:

            generic-220         1001 zur Wahl, nichts gewählt
            Centauri Carbon 2   1001 zur Wahl, nichts gewählt
            neu gefüllt            4 zur Wahl, das richtige gewählt

        Für den einzigen Drucker, den er besitzt, hieß das: aus 1001 Einträgen
        suchen, obwohl vier davon seine sind und ``printer_for`` sie kennt.

        **Die gemerkte Wahl überlebt den Wechsel nicht**, und deshalb wird das
        Feld vorher geleert: Sie galt für den vorigen Drucker, und ein
        Maschinenprofil gehört zu genau einem. Innerhalb desselben Druckers
        bleibt eine Abweichung stehen — das hält
        ``test_a_remembered_choice_wins_over_the_match`` fest, und
        :meth:`_profiles_found` liest dafür ``already``.

        Ohne gefundene Profile gibt es nichts zu füllen. Die Suche läuft in
        einem Arbeiter; kommt sie später, füllt sie selbst.
        """
        if not self._profiles:
            return
        with QSignalBlocker(self.machine_choice):
            self.machine_choice.setCurrentIndex(-1)
        self._profiles_found(self._profiles)

    def _resolved(self, quality: Any) -> PrintSettings:
        """Neu aufgelöste Vorgaben — mit der Slotbelegung von vorher.

        **``resolve`` ist eine reine Funktion aus Profil und Stufe, und genau
        zwei Felder haben dort keine Quelle: ``slot_profiles`` und
        ``slot_overrides``.** Nachgemessen: Ein
        Satz durch „fein" und zurück nach „standard" ergibt Feld für Feld
        wieder denselben — die Slotbelegung steht danach auf ``()`` und
        bleibt es, gleich wie oft man zurückschaltet.

        Das ist der Unterschied, auf den es ankommt. Für alles andere trägt
        :meth:`_quality_changed` sein Argument zu Recht: Eine Stufe zu wechseln
        *heißt*, sich neue Vorgaben geben zu lassen, und wer die alten
        zurückwill, wählt die alte Stufe. Für die Slotbelegung stimmt dieser
        Satz nicht — sie kommt von keiner Stufe zurück, weil sie von keiner
        kam.

        Und sie ist auch der Sache nach keine Druckeinstellung: Sie sagt,
        **welche Spule auf welchem Materialslot des Modells liegt** (§20). Ob
        die Schrift eines Gehäuses aus Weiß gedruckt wird, ändert sich nicht,
        weil jemand von 0,2 auf 0,12 mm Schichthöhe geht.

        Der Fehler war an beiden Stellen derselbe, und die zweite ist die
        Stelle, an der die Übersteuerungen gerettet werden — dort fiel die
        Slotbelegung und die eigenen Werte der Spulen durch dasselbe Loch.
        """
        return replace(
            print_settings.resolve(self.session.profile, quality),
            slot_profiles=self.settings.slot_profiles,
            slot_overrides=self.settings.slot_overrides,
        )

    def _build_front(self) -> QWidget:
        """Die sieben Werte, die man wirklich ändert (§2.4).

        **Als Aufklapper und nicht als gerahmter Kasten** (Befund B9): Der
        Dialog mischte zwei Abschnittsformen — eingelassener Titel in einem
        Rahmen über rahmenlosen Aufklappern —, und zwei Formen heißen zwei
        Rhythmen. Gewonnen hat die Familie, die mehr kann: Zuklappen verlangt
        §2.5, und links im Fenster tragen Objektbaum, Parameter und Verlauf
        dieselbe Form. Ein Griff statt zweier.
        """
        inner = QWidget(self)
        form = QFormLayout(inner)
        form.setContentsMargins(0, 0, 0, 0)
        for field in FIELDS:
            if field.front:
                form.addRow(self._label(field), self._editor(field))
        box = collapsible(tr("Das Wichtigste"), inner)
        self.front_toggle = _toggle_of(box)
        return box

    def _build_search(self) -> QHBoxLayout:
        """Die Zeile, mit der man eine von sechsundfünfzig Einstellungen findet.

        Der Dialog trägt zehn Gruppen, und bis hierhin half nur Aufklappen und
        Lesen — die Geste, die jeder Slicer mitbringt, fehlte als einzige.
        """
        row = QHBoxLayout()
        self.search = QLineEdit(self)
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText(tr("Einstellung suchen …"))
        self.search.setToolTip(
            tr("Sucht in Namen und Erklärungen. Eingabetaste führt zum nächsten Treffer.")
        )
        self.search.setStatusTip(self.search.toolTip())
        self.search.setAccessibleDescription(self.search.toolTip())
        self.search.returnPressed.connect(self._search_forward)
        self.search.textChanged.connect(self._search_typed)
        self.search_state = QLabel(self)
        # Nebentext und keine Bedeutung: Hier steht „1 von 5", die Trefferzahl
        # der Suche. „note" gab es als Stufe nie — die vier heißen title,
        # section, body und caption —, und gerendert war die Zeile deshalb
        # gewöhnlicher Text. Gemeint war leise, und das ist „caption".
        set_level(self.search_state, "caption")
        row.addWidget(QLabel(tr("Suchen"), self))
        row.addWidget(self.search, 1)
        row.addWidget(self.search_state)
        return row

    def search_hits(self, term: str) -> list[str]:
        """Welche Einstellungen zu diesem Begriff passen, in Dialogreihenfolge.

        Gesucht wird über das, was der Kunde liest: Titel, Satz darunter und
        Name der Gruppe. Der **Satz** gehört ausdrücklich dazu, und das ist
        gemessen: „Überhänge" steht in drei Sätzen und in keinem Titel. Der
        **Gruppenname** ebenso — „Stützen" ist die Frage, mit der ein
        Slicer-Kunde ankommt, und sie findet alle sieben Zeilen.

        Die **Einheit** steht bewusst nicht darin: „mm" träfe zweiundzwanzig
        von sechsundfünfzig Zeilen, ohne dass eine davon gemeint wäre — ein
        Treffer, der ein Drittel des Dialogs trifft, ist keiner.

        Gefaltet wie in der Befehlspalette (``command_palette.fold``): „ä" wird
        zu „ae", damit „aushoehlen" und „Aushöhlen" dasselbe finden. Zwei
        Aufgaben, eine Tabelle — nicht zu verwechseln mit der Sortierfaltung,
        wo „ä" wie „a" zählt.

        **Und der Name aus dem Slicer zählt mit.** Wer von PrusaSlicer kommt,
        sucht seine Wandzahl unter ``perimeters``, wer von Orca kommt unter
        ``wall_loops``, wer von Cura kommt unter ``wall_line_count`` — drei
        Wörter für dieselbe Zeile, und keines davon steht im Dialog. Sie kommen
        aus derselben Tabelle, mit der die Übergabe schreibt
        (``slicer_keys.keys_for``): ein zweites Verzeichnis wäre eines, das
        altert, sobald ein Schlüssel sich ändert.

        **Und der Unterstrich zählt wie ein Leerzeichen.** Die Schlüssel heißen
        ``wall_loops``, gelesen und gesprochen wird „wall loops" — wer es so
        eintippt, bekam nichts, obwohl die Zeile danebensteht. Beide Seiten
        werden deshalb gleich geschrieben, der Begriff wie der Heuhaufen.
        """
        from app.core.export.slicer_keys import keys_for
        from app.ui.command_palette import fold

        def flatten(text: str) -> str:
            """Gefaltet, und der Unterstrich als Leerzeichen."""
            return fold(text).replace("_", " ")

        wanted = flatten(term).strip()
        if not wanted:
            return []
        hits = []
        for field in FIELDS:
            haystack = flatten(
                " ".join(
                    (
                        str(field.title),
                        str(field.note),
                        group_title(field.group),
                        *keys_for(field.path),
                    )
                )
            )
            if wanted in haystack:
                hits.append(field.path)
        return hits

    def highlighted(self) -> str:
        """Welche Zeile gerade hervorgehoben ist — leer, wenn keine."""
        return self._lifted

    def jump_to(self, term: str) -> None:
        """Zum nächsten Treffer springen und ihn hervorheben.

        **Heben und nicht filtern.** Eine Liste, die sich beim Tippen umbaut,
        nimmt dem Kunden die Übersicht, die er gerade gewinnt: Wer „Temperatur"
        sucht, will sehen, *wo* sie steht, um beim nächsten Mal direkt
        hinzugehen. Also bleibt jede Gruppe stehen; der Weg dorthin wird
        freigeräumt (Klappe auf, Reiter gewählt, Zeile in den Blick gerollt)
        und die Zeile leuchtet auf — dieselbe Bauart wie
        ``MainWindow._flash_area``, nur bleibend, solange die Suche steht.
        """
        if term != self._search_term:
            self._search_term = term
            self._search_hits = self.search_hits(term)
            self._search_at = -1
        if not self._search_hits:
            self._lift("")
            self._show_search_state()
            return
        self._search_at = (self._search_at + 1) % len(self._search_hits)
        self._lift(self._search_hits[self._search_at])
        self._show_search_state()

    def _search_typed(self, term: str) -> None:
        """Beim Tippen zählen, aber nicht springen.

        Der Sprung gehört an die Eingabetaste: Wer „Tem" tippt, ist noch nicht
        fertig, und ein Dialog, der bei jedem Buchstaben den Reiter wechselt,
        ist Unruhe statt Hilfe. Die Zahl daneben aktualisiert sich trotzdem —
        so sieht man beim Tippen, ob der Begriff trägt.
        """
        self._search_term = term
        self._search_hits = self.search_hits(term)
        self._search_at = -1
        if not term:
            self._lift("")
        self._show_search_state()

    def _search_forward(self) -> None:
        self.jump_to(self.search.text())

    def _show_search_state(self) -> None:
        """„2 von 4" — ohne Zähler weiß niemand, ob er alles gesehen hat."""
        if not self._search_term:
            self.search_state.setText("")
            return
        if not self._search_hits:
            self.search_state.setText(tr("kein Treffer"))
            return
        place = max(self._search_at, 0) + 1
        self.search_state.setText(
            tr("{position} von {count}")
            .replace("{position}", localised(str(place)))
            .replace("{count}", localised(str(len(self._search_hits))))
        )

    def _lift(self, path: str) -> None:
        """Eine Zeile in den Blick holen und hervorheben — höchstens eine."""
        for old in (self._lifted, path):
            if old and old in self._labels:
                self._labels[old].setStyleSheet("")
        self._lifted = path
        if not path:
            return
        field = next((entry for entry in FIELDS if entry.path == path), None)
        editor = self._editors.get(path)
        label = self._labels.get(path)
        if field is None or editor is None or label is None:
            return
        if not field.front:
            if self.tabs_toggle is not None and not self.tabs_toggle.isChecked():
                self.tabs_toggle.setChecked(True)
            index = GROUPS.index(field.group) if field.group in GROUPS else -1
            if index >= 0:
                self.tabs.setCurrentIndex(index)
                area = self.tabs.widget(index)
                if isinstance(area, QScrollArea):
                    area.ensureWidgetVisible(editor)
        # **Die Füllfarbe füllt, sie schreibt nicht.** Als Schriftfarbe auf der
        # Dialogfläche brachte ``select`` im hellen Thema 1,70 — die am
        # schlechtesten lesbare Zeile des Dialogs war ausgerechnet die gesuchte.
        # ``accent_line`` wie beim Fokusring wäre 3,01 und damit die Schwelle
        # für eine Umrandung, nicht für Text. Als Fläche mit der zugehörigen
        # Schriftfarbe sind es 7,93, in beiden Themen. Das Fett bleibt als
        # zweite Kodierung (Regel 18).
        # ``current_theme()`` und nicht ``ui_settings.theme``: Es gibt den Typ
        # ``Theme`` zurück statt eines ``str`` — und es nennt das gerade
        # aktive Thema, nicht den zuletzt gespeicherten Wert.
        colours = THEMES[current_theme()]
        label.setStyleSheet(
            f"background: {ROLES['select']}; color: {colours['highlight_text']};"
            " font-weight: 600; border-radius: 3px; padding: 0 4px;"
        )
        editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def _build_tabs(self) -> QWidget:
        """Die hinteren sechsundvierzig Felder, hinter einem Dreieck.

        Vorher war es eine ankreuzbare Gruppe, und darüber hat dieselbe
        Anwendung an zwei anderen Stellen schon entschieden (siehe
        ``op_dialog`` und ``generate_dialog``): Ein Häkchen liest sich wie ein
        Schalter, der etwas bewirkt — „Weitere Einstellungen ☐" sagt nicht
        „zugeklappt", es sagt „aus". Der Umschalter aus ``panels.collapsible``
        ist derselbe wie dort, mit Dreieck und ganzer Zeile als Klickfläche.
        """
        self.tabs = QTabWidget(self)
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
            self.tabs.setTabToolTip(self.tabs.count() - 1, group_title(group))
        # **Acht Gruppen, und zwei davon waren unerreichbar.** Bei der
        # Vorgabebreite endete die Reiterleiste nach „Geschwindigkeit"; die
        # Rollknöpfe, die Qt dafür einblendet, sind unter unserem Stylesheet
        # blanke Flächen — gemessen, je 16 auf 22 Punkte in einer Farbe,
        # dieselbe Falle wie bei den Pfeilen des Zahlenfelds, nur ohne deren
        # Ausweg: Ein ``image:`` an ihnen greift nicht (auch das gemessen).
        # Wer nichts zum Rollen sieht, hat die achte Gruppe nicht.
        #
        # Also gar nicht erst rollen: Die Reiter werden gekürzt statt
        # abgeschnitten (der volle Name steht im Tooltip darüber), und der
        # Dialog wächst beim Aufklappen in der Breite mit — dieselbe Bewegung,
        # die er für die Höhe schon macht.
        bar = self.tabs.tabBar()
        bar.setUsesScrollButtons(False)
        bar.setElideMode(Qt.TextElideMode.ElideRight)
        bar.setExpanding(False)
        box = collapsible(tr("Weitere Einstellungen"), self.tabs, open_now=False)
        self.tabs_toggle = _toggle_of(box)
        if self.tabs_toggle is not None:
            self.tabs_toggle.toggled.connect(self._unfold_tabs)
        return box

    def _unfold_tabs(self, open_now: bool) -> None:
        """Zugeklappt bekommt die Gruppe auch keinen Platz mehr — und offen
        bekommt sie echten.

        Das Register verschwand schon vorher; sein Rahmen behielt aber den
        Dehnungsfaktor und damit den ganzen freien Raum des Dialogs — ein
        leerer Kasten, in dem nichts stand.

        Beim Öffnen wächst der Dialog selbst (Robert, 26.08.2026: „klappt zu
        klein auf"). `adjustSize` taugt dafür nicht: Es deckelt bei zwei
        Dritteln der Bildschirmhöhe, und weil die Vorderseite davon schon
        740 Punkte hält, blieben dem Register 220 von gewünschten 416 —
        vier Zeilen mit Rollbalken. Gemessen wird stattdessen die **größte**
        Gruppe: Sie soll ohne Rollen passen, wenn der Bildschirm es hergibt;
        die Grenze ist die nutzbare Bildschirmhöhe, nicht ein Anteil davon.
        """
        layout = self.layout()
        box = self.tabs.parentWidget()
        if isinstance(layout, QVBoxLayout) and box is not None:
            layout.setStretch(layout.indexOf(box), 1 if open_now else 0)
        if not open_now:
            self.adjustSize()
            return
        tallest = 0
        for index in range(self.tabs.count()):
            area = self.tabs.widget(index)
            page = area.widget() if isinstance(area, QScrollArea) else None
            if page is not None:
                tallest = max(tallest, page.sizeHint().height())
        bar = self.tabs.tabBar()
        frame = bar.sizeHint().height() + 8
        wanted = self.height() + tallest + frame + 12
        screen = self.screen()
        if screen is not None:
            wanted = min(wanted, screen.availableGeometry().height() - 48)
        self.resize(max(self._room_for_tabs(), self.width()), max(wanted, self.height()))

    def _room_for_tabs(self) -> int:
        """Die Breite, die die Reiterleiste braucht — gedeckelt vom Bildschirm.

        Eigene Methode, weil sie sonst nicht prüfbar wäre: Am gebauten Dialog
        entscheidet die Schriftmetrik, ob das Wachstum überhaupt greift, und
        offscreen gibt es keine (der Bildschirm ist dort 800 Punkte breit, die
        Leiste wünscht mehr). Die **Rechnung** lässt sich dagegen an jedem
        Bildschirm prüfen, und sie ist das, was hier zugesichert wird.

        Gemessen wird die Leiste selbst und keine Zahl daneben: Was sie
        braucht, hängt an der Schrift und an der Länge der acht Gruppennamen.
        """
        room = self.tabs.tabBar().sizeHint().width() + 2 * ROOMY
        screen = self.screen()
        if screen is not None:
            room = min(room, screen.availableGeometry().width() - 48)
        return room

    def _build_slicer(self) -> QWidget:
        """Auf welche Profile des Slicers Solidon seine Werte legt (§29).

        Zwei Auswahlen, aber im Regelfall keine Entscheidung: das
        Maschinenprofil sagt selbst, welchen Drucker und welche Düse es meint,
        und benennt sein Standard-Prozessprofil. Getroffen wird beides
        automatisch — hier steht es, damit man abweichen kann, nicht damit man
        muss.

        Zugeklappt hinter einem Dreieck und nicht hinter einem Häkchen: Als
        ankreuzbare Gruppe stand hier „Profile des Slicers ☐" über drei grauen
        Auswahlfeldern — zu lesen als „Profile: aus", also als eine Sperre, und
        das ist es nicht. Es ist der Abschnitt, den im Regelfall niemand
        braucht.
        """
        self.slicer_inner = QWidget(self)
        form = QFormLayout(self.slicer_inner)

        # **Welcher Slicer**, wenn mehr als einer installiert ist. Ohne diese
        # Zeile entschied die Suchreihenfolge: `find_program` hört beim ersten
        # Treffer auf, und auf einem Rechner mit ElegooSlicer, PrusaSlicer und
        # Cura war das eine Zufallsentscheidung. Wollte dieser eine nicht,
        # stand der Kunde vor einer Sackgasse statt vor einer Wahl (Robert,
        # 30.08.2026).
        #
        # Die Zeile erscheint nur bei mehreren — bei einem wäre sie ein
        # Auswahlfeld mit einem Eintrag, also eine Frage ohne Antwortmöglichkeit
        # (§2.4).
        self.slicer_choice = QComboBox(self.slicer_inner)
        self.slicer_choice.activated.connect(self._slicer_chosen)
        slicer_note = tr(
            "Welcher Slicer die Druckdatei rechnet. Die Wahl bleibt gemerkt und gilt "
            "auch beim nächsten Mal; die Profile darunter richten sich nach ihr."
        )
        self.slicer_choice.setToolTip(slicer_note)
        self.slicer_choice.setStatusTip(slicer_note)
        self.slicer_choice.setAccessibleDescription(slicer_note)
        self.slicer_choice.setAccessibleName(tr("Slicer"))
        # Der Satz gehört an beide Hälften der Zeile: Wer eine Zeile nicht
        # versteht, zeigt auf das Wort davor und nicht auf den Kasten daneben.
        slicer_label = QLabel(tr("Slicer"), self.slicer_inner)
        slicer_label.setToolTip(slicer_note)
        slicer_label.setStatusTip(slicer_note)
        slicer_label.setAccessibleDescription(slicer_note)
        form.addRow(slicer_label, self.slicer_choice)
        self.slicer_choice.setVisible(False)
        slicer_label.setVisible(False)

        self.machine_choice = QComboBox(self.slicer_inner)
        self.machine_choice.setEnabled(False)
        self.machine_choice.currentIndexChanged.connect(self._machine_chosen)
        # **Tippen statt scrollen** („1001 Profile sind bisschen viel", Robert,
        # 03.09.2026). Wo kein Profil zum Drucker gehört, bleiben nach der
        # Düsenstufe immer noch 387 — und eine Liste dieser Länge findet
        # niemand durch Rollen. Der Vervollständiger sucht **im ganzen Namen**
        # und nicht nur am Anfang: Wer „Ender" tippt, meint „Creality Ender-3
        # V3", und wer den Hersteller kennt, tippt ihn eben.
        #
        # ``NoInsert`` und die Sperre für neue Einträge sind das Gegenstück:
        # Ein getippter Name, den es nicht gibt, darf keine Wahl werden — dann
        # stünde im Feld ein Drucker, den der Slicer nicht kennt.
        # ``currentData()`` bleibt dabei die einzige Quelle der Wahl; sie ist
        # ``None``, solange nichts Passendes getroffen ist, und der
        # Slicen-Knopf sperrt sich mit seinem Grund (Regel 19).
        self.machine_choice.setEditable(True)
        self.machine_choice.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        machine_completer = self.machine_choice.completer()
        if machine_completer is not None:
            machine_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            machine_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        machine_note = tr(
            "Das Druckerprofil des Slicers. Tippen sucht in der ganzen Liste — "
            "auch mitten im Namen."
        )
        self.machine_choice.setToolTip(machine_note)
        self.machine_choice.setStatusTip(machine_note)
        self.machine_choice.setAccessibleDescription(machine_note)
        self.machine_choice.setAccessibleName(tr("Drucker"))
        self.process_choice = QComboBox(self.slicer_inner)
        self.process_choice.setEnabled(False)
        # Der Slicen-Knopf fragt die Profilwahl vor dem Klick (Regel 19) —
        # also muss er jede Änderung daran erfahren, nicht nur die Maschine.
        self.process_choice.currentIndexChanged.connect(self._show_slicer_state)
        self.filament_choice = QComboBox(self.slicer_inner)
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
        self.slot_rows: list[tuple[QWidget, QComboBox]] = []
        self._slot_names: list[str] = []
        """Die Namen der Slot-Zeilen — die Quelle für Meldungen über sie."""
        self.slot_form = form
        self._build_slot_rows(form)
        self.profile_note = QLabel(tr("Der Profilbestand wird durchgesehen …"), self.slicer_inner)
        self.profile_note.setWordWrap(True)
        form.addRow(self.profile_note)
        self.slicer_box = collapsible(tr("Profile des Slicers"), self.slicer_inner, open_now=False)
        self.slicer_toggle = _toggle_of(self.slicer_box)
        if self.slicer_toggle is not None:
            self.slicer_toggle.toggled.connect(self._unfold_slicer)
        # Erst jetzt: die Auswahl steht, und ``_slicer_path`` ist längst gesetzt.
        self._fill_slicer_choice()
        return self.slicer_box

    def error_handlers(self) -> dict[str, Callable[[AppError], None]]:
        """Die Handlungen des Fensters, ergänzt um die des Slicer-Wegs.

        **Ergänzt und nicht ersetzt**, und das ist hier keine Feinheit:
        :func:`handlers_of` geht die Elternkette hoch, nimmt das **erste**
        Widget, das diese Methode trägt, und kehrt damit zurück. Ohne die
        erste Zeile verlöre jeder Fehler, der mit diesem Dialog als Fenster
        erscheint, das ganze Wörterbuch des Hauptfensters — reparieren,
        verkleinern, teilen, nur exportieren. Die neuen Knöpfe wären da, die
        alten still fort.

        Drei Kennungen wurden bis hierhin angeboten und von niemandem
        eingelöst (gezählt am 30.08.2026): Wenn der Slicer-Lauf scheitert,
        schlug die Übergabe vor, seine Ausgabe anzusehen, das Maschinenprofil
        zu prüfen und einen anderen Slicer zu wählen — alle drei ohne Draht,
        also nur als Sätze zum Lesen. Auf einem Rechner mit drei Slicern war
        das eine Sackgasse, während zwei arbeitende danebenlagen (§2.1).
        ``choose_slicer`` hängt zusätzlich am Hauptfenster: Der Fehler tritt
        auch ohne offenen Dialog auf.
        """
        known = dict(handlers_of(self.parentWidget()))
        known["show_output"] = self._show_slicer_output
        known["check_profile"] = lambda _error: self._open_slicer_section()
        known["choose_slicer"] = lambda _error: self._open_slicer_section()
        return known

    def _show_slicer_output(self, error: AppError) -> None:
        """Was der Slicer geschrieben hat — als Text, nicht als Wertzeile.

        ``show_details`` setzt jeden Wert über ``value_line`` in **eine**
        Zeile. Für achthundert Zeichen Slicer-Protokoll wäre das eine Zeile,
        die niemand liest; hier steht es im aufklappbaren Teil, wo
        mehrzeiliger Text hingehört.
        """
        written = str(error.values.get("output", "") or "")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(tr("Ausgabe des Slicers"))
        box.setText(str(error.title))
        box.setDetailedText(written or tr("Der Slicer hat nichts geschrieben."))
        box.exec()

    def _open_slicer_section(self) -> None:
        """Den Abschnitt aufklappen, weil darin etwas zu entscheiden ist.

        Drei Stellen tun das: kein Profil passt von selbst, der Slicer verlangt
        ein Druckerprofil, er verlangt ein Prozessprofil. Ein Hinweis, der auf
        eine Auswahl zeigt, die zugeklappt ist, wäre einer, dem man nicht
        folgen kann.
        """
        if self.slicer_toggle is not None:
            self.slicer_toggle.setChecked(True)

    def _unfold_slicer(self, open_now: bool) -> None:
        """Beim Aufklappen wächst der Dialog mit — von selbst tut er es nicht.

        Dieser Abschnitt geht **nachgereicht** auf: Die Profilsuche läuft in
        einem Arbeiter, und Sekunden nach dem Öffnen des Dialogs stehen vier
        Zeilen mehr darin. Das Fenster bleibt dabei auf seiner Aufmachgröße,
        und den Fehlbetrag presst die Layoutrechnung aus den Feldern darüber —
        gemessen an der Kundenfahrt vom 30.08.2026: Nach dem Aufklappen
        standen die acht Zahlenfelder der Vorderseite sichtbar gestaucht da.
        Dieselbe Familie wie ``first_run._grow_to_content`` (Robert,
        26.08.2026: Auswahlfelder mit 16 von 28 Punkten Höhe).

        Nur wachsen, nie schrumpfen: Wer selbst zuklappt, will Platz sparen —
        und ein Dialog, der beim Zuklappen springt, ist Bewegung ohne Auftrag.
        Das Wachsen deckelt die nutzbare Bildschirmhöhe, wie in
        :meth:`_unfold_tabs`.
        """
        if not open_now:
            return
        # Über den Zeitgeber wie in ``first_run``: Unmittelbar im Signal meldet
        # ``sizeHint`` noch den zugeklappten Stand, und ein ``max`` mit einer
        # veralteten Zahl wächst nicht. ``self`` als Empfänger, damit der Ruf
        # verfällt, wenn der Dialog vorher weggeräumt wird.
        QTimer.singleShot(0, self, self._grow_to_content)

    def _grow_to_content(self) -> None:
        """Auf die Höhe wachsen, die der Inhalt wünscht — bis zum Bildschirm.

        **Erst die Rechnung erzwingen, dann messen.** Ein Ereignisdurchlauf
        allein genügt hier nicht: Gemessen am aufgeklappten Abschnitt meldete
        ``sizeHint`` weiterhin 633 Punkte, während die ehrliche Zahl nach
        ``layout().activate()`` bei 775 lag — ein ``max`` mit der veralteten
        Zahl wächst nicht, und der Fehlbetrag bleibt in den Feldern darüber.
        Dieselbe Sorte Lüge wie die umbrochenen Labels in
        ``first_run._grow_to_content``, nur eine Ebene höher.
        """
        layout = self.layout()
        if layout is not None:
            layout.activate()
        wanted = self.sizeHint().height()
        screen = self.screen()
        if screen is not None:
            wanted = min(wanted, screen.availableGeometry().height() - 48)
        self.resize(self.width(), max(self.height(), wanted))

    def _forget_result(self) -> None:
        """Das Ergebnis des vorigen Slicers verwerfen.

        **Der Wechsel räumte die Profile weg und das Ergebnis nicht.** Wer
        frisch auf PrusaSlicer umstellte, las in der Statuszeile weiter
        „Druckzeit: 18 min …" vom ElegooSlicer-Lauf davor — und *Druckdatei
        speichern* bot dessen Datei an. Wer dort speichert, hält einen fremden
        Lauf für seinen eigenen, und nichts auf dem Bildschirm widerspricht
        (Handlauf, 30.08.2026).

        Dieselbe Familie wie :meth:`_clear_profile_choices`: Was zum alten
        Slicer gehört, gehört nicht zum neuen.
        """
        self._gcode = []
        self._hold_the_save()
        self.state.setText("")

    def _clear_profile_choices(self) -> None:
        """Die Profilauswahl leeren, bevor eine neue Suche etwas hineinschreibt.

        **Ein Slicer kann wechseln, und die Auswahl bleibt sonst stehen.** Wer
        zwei installiert hat und im Dialog von der Orca-Familie auf Cura
        umstellt, hatte danach drei gefüllte Auswahlfelder mit Orca-Profilen
        vor sich — :func:`_start_profile_search` kehrt für ``prusa`` und
        ``cura`` früh zurück, ohne sie anzufassen. ``_slice`` liest sie
        unbesehen, und CuraEngine bekam ein ``-j`` auf eine Orca-Datei und war
        nach einer Zehntelsekunde tot; ``remembered_setup`` schrieb dieselbe
        Wahl auch noch in die Konfiguration.

        Geleert wird deshalb am Anfang jeder Suche, nicht am Ende — dann gilt
        es auch für die Wege, die vorzeitig zurückkehren.
        """
        self._profiles = []
        for combo in (self.machine_choice, self.process_choice, self.filament_choice):
            with QSignalBlocker(combo):
                combo.clear()
            combo.setEnabled(False)
        for _label, box in self.slot_rows:
            box.clear()
            box.setEnabled(False)
        self.profile_note.setText(tr("Der Profilbestand wird durchgesehen …"))

    def _start_profile_search(self) -> None:
        self._clear_profile_choices()
        self._needs_profiles = False
        self._profiles_pending = False
        found = self._slicer_path
        if found is None:
            self.slicer_box.setVisible(False)
            self._show_slicer_state()
            return
        try:
            flavour = handover.detect(found).flavour
        except AppError:
            self.slicer_box.setVisible(False)
            self._show_slicer_state()
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
            self._show_slicer_state()
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
            self._show_slicer_state()
            return

        self._needs_profiles = True
        self._profiles_pending = True
        self._show_slicer_state()
        worker = _ProfileWorker(found, flavour)
        worker.done.connect(self._profiles_found)
        # Der Profilbestand ist eine Zugabe: Was hier schiefgeht, darf den
        # Dialog nicht aufhalten — aber der Satz „Der Profilbestand wird
        # durchgesehen …" muss verschwinden, sonst steht er dort für immer.
        worker.crashed.connect(self._profiles_failed)
        worker.finished.connect(self._profile_search_finished)
        self._profile_worker = worker
        self._leash.start(worker)

    def _profiles_failed(self, detail: str) -> None:
        """Der Profilbestand ließ sich nicht durchsehen.

        Eine Zugabe, die den Dialog nicht aufhält — aber der Satz „Der
        Profilbestand wird durchgesehen …" muss verschwinden, sonst steht er
        dort für immer und behauptet einen Vorgang, den es nicht mehr gibt.
        """
        _log.warning("profile search crashed: %s", detail)
        self._profiles_pending = False
        self.profile_note.setText(
            tr(
                "Der Profilbestand ließ sich nicht durchsehen. Die Profile lassen sich "
                "unten von Hand wählen."
            )
        )
        if self.slicer_toggle is not None:
            self.slicer_toggle.setChecked(True)
        self._show_slicer_state()

    def _profiles_found(self, found: list[slicer_profiles.SlicerProfile]) -> None:
        # **Zuerst lesen, was schon gewählt ist.** Nach dem ersten ``addItem``
        # steht der Index auf 0, und „was gewählt ist" wäre dann Qts
        # Vorbelegung statt einer Entscheidung — die Prüfung unten hielte den
        # ersten Eintrag des Bestands für die Wahl des Nutzers.
        already = str(self.machine_choice.currentData() or "")
        already_shown = self.machine_choice.currentText()
        self._profiles = found
        self._profiles_pending = False
        machines = slicer_profiles.machines(found)
        if not machines:
            # Regel 17: Der Satz sagte, was fehlt, und hörte dort auf. Was hilft,
            # ist eine Handlung — die Profile entstehen, wenn der Slicer einmal
            # gelaufen ist und einen Drucker kennt.
            self.profile_note.setText(
                tr(
                    "Keine Profile gefunden — ohne sie lehnt dieser Slicer den Auftrag ab. "
                    "Öffnen Sie den Slicer einmal und legen Sie einen Drucker an; danach steht "
                    "sein Profil hier."
                )
            )
            self._show_slicer_state()
            return

        # ``QSignalBlocker`` und nicht das Paar von Hand: Zwischen Sperren und
        # Freigeben laufen ``_machines_worth_showing`` und ``entry.title`` über
        # bis zu tausend gefundene Profile. Wirft eines davon, bliebe die
        # Druckerauswahl für immer stumm — sie zeigte weiter ihre Liste, ließe
        # wählen und sagte es niemandem.
        with QSignalBlocker(self.machine_choice):
            # **Leeren, bevor gefüllt wird**, und zwar hier statt beim Aufrufer:
            # Zweimal gefunden hieß bis hierhin zweimal angehängt, und aus tausend
            # Druckerprofilen wurden zweitausend, jedes doppelt (Handlauf,
            # 30.08.2026). Der Weg über ``_slicer_chosen`` leerte vorher, der über
            # ``recheck_slicer`` nicht — eine Absicherung, die am Aufrufer hängt,
            # lässt den nächsten Aufrufer wieder ungeschützt. ``_fill_processes``
            # macht es an derselben Stelle richtig.
            self.machine_choice.clear()
            for entry in self._machines_worth_showing(machines):
                self.machine_choice.addItem(entry.title(tr("eigenes")), str(entry.path))
            # **Eine Wahl, die der neue Fund nicht kennt, bleibt trotzdem stehen.**
            # Das Leeren darf nur den Bestand ersetzen, nicht die Entscheidung des
            # Nutzers wegwerfen: Wer wählt, während die Suche noch läuft, hätte
            # sonst nach ihrer Antwort ein leeres Feld — derselbe Wettlauf, den der
            # Abschnitt darunter schon einmal gekostet hat.
            if already and self.machine_choice.findData(already) < 0:
                self.machine_choice.addItem(already_shown, already)
        self.machine_choice.setEnabled(True)
        self.process_choice.setEnabled(True)
        self.filament_choice.setEnabled(True)

        chosen, process = slicer_profiles.match(found, self.session.profile.printer)
        # **Eine getroffene Wahl bleibt stehen.** Die Profilsuche läuft in einem
        # Arbeiter und antwortet nachgereicht; wer in der Zwischenzeit selbst
        # eine Maschine gewählt hat, sah sie danach auf etwas anderes springen —
        # und beim Schließen wurde die *neue* gemerkt, nicht seine. Dieselbe
        # Regel wie beim Druckervorschlag der Erstinbetriebnahme: Eine Vorgabe,
        # die eine Wahl überschreibt, ist keine Vorgabe mehr (§2.4).
        #
        # Sichtbar wurde es an einem Test, der unter Last einmal rot war: Er
        # setzt die drei Auswahlen von Hand und schließt den Dialog, und dazwischen
        # kam die Antwort der Suche.
        remembered = already or self.ui_settings.slicer_machine_profile
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
            # **Eine Aufforderung ist noch keine Auskunft.** Hier stand „Zu
            # diesem Drucker passt kein Profil von selbst — bitte auswählen.":
            # wahr, und es ließ offen, *welcher* Drucker gemeint ist und warum
            # die Liste darunter dann tausend Einträge hat. Gemessen an einem
            # frischen Projekt auf *Allgemeiner FDM-Drucker 220 mm* mit
            # ElegooSlicer: 1001 Profile zur Wahl, das Feld leer, der
            # Slicen-Knopf gesperrt — und kein Wort darüber, dass der Slicer
            # für genau diesen Drucker keines mitbringt. Wer beide Namen liest,
            # weiß sofort, ob er den Drucker wechseln oder ein Profil suchen
            # muss.
            #
            # ``.replace`` und nicht ``.format``: dieselbe Schreibweise wie am
            # Satz über die ignorierte Einstellung, und ein Katalogeintrag, der
            # eine geschweifte Klammer verliert, wirft damit nicht.
            printer = self.printer_choice.currentText()
            slicer = _slicer_title(self._slicer_path) if self._slicer_path else ""
            if printer and slicer:
                # **Ohne „aus der Liste".** Wo gewählt wird, sagt das Feld
                # selbst („Tippen sucht in der ganzen Liste …"); dieser Satz
                # sagt die Lage. Zwei Sätze, die dasselbe Wort tragen, laufen
                # irgendwann auseinander — bei den Auswahlnamen hat das zwei
                # Tabellen gekostet (Hinweis 3d-druck-7f).
                self.profile_note.setText(
                    str(
                        tr(
                            "Für {printer} bringt {slicer} kein eigenes Profil mit — "
                            "wählen Sie das Profil Ihres Druckers."
                        )
                    )
                    .replace("{printer}", printer)
                    .replace("{slicer}", slicer)
                )
            else:
                self.profile_note.setText(
                    tr("Zu diesem Drucker passt kein Profil von selbst — bitte auswählen.")
                )
            self._open_slicer_section()
        else:
            self.profile_note.setText(
                tr(
                    "Automatisch zugeordnet. Was hier steht, bringt der Slicer mit; Solidon legt "
                    "seine Werte darauf."
                )
            )
        self._show_slicer_state()

    def _machine_chosen(self) -> None:
        if self._profiles:
            self._fill_processes(None)
        self._show_slicer_state()

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

    def _machines_worth_showing(
        self, machines: list[slicer_profiles.SlicerProfile]
    ) -> list[slicer_profiles.SlicerProfile]:
        """Die Maschinenprofile zum eigenen Drucker — sonst alle.

        „Ich hab da mehr Drucker zur Auswahl, offiziell hab ich nur den Elegoo
        Centauri Carbon 2" (Robert, 03.09.2026). Gemessen an seinem
        ElegooSlicer: **1001** Maschinenprofile in der Liste, davon 103 einem
        Solidon-Drucker zuordenbar und **4** seinem — die vier Düsenvarianten.
        Die Vorwahl traf dabei die richtige; unbrauchbar war die Liste
        dahinter.

        Zugeordnet wird über :func:`slicer_profiles.printer_for`, also über
        dieselbe Auskunft, mit der auch die Vorwahl arbeitet — keine zweite
        Namensheuristik daneben (Vorschlag 3d-druck-a0).

        **Bleibt nichts übrig, bleibt alles stehen.** Für den Vorgabedrucker
        „Allgemeiner FDM-Drucker" ordnet sich kein einziges Profil zu, und eine
        leere Druckerliste wäre schlimmer als eine lange: Der Slicer lehnt ohne
        Maschinenprofil jeden Auftrag ab. Dieselbe Grenze wie bei den
        Filamenten eine Methode weiter — ein Filter, der alles wegnimmt, ist
        keiner.

        **Und dazwischen liegt eine Stufe, weil „alles" zu viel ist** („1001
        Profile sind bisschen viel", Robert, 03.09.2026). Wo kein Profil zum
        Drucker gehört, gibt es immer noch eine echte Auskunft über ihn: seine
        Düse. Ein Profil für 0,8 mm ist an einem 0,4-mm-Drucker die falsche
        Wahl, gleich wie der Drucker heißt. Gemessen am Bestand des
        ElegooSlicer:

            ohne Filter                     1001
            nach Düse (0,4 mm)               387
            dem Drucker zugeordnet          4 bis 41

        Der Herstellername hilft dabei nicht weiter: Er ist genau bei dem
        Drucker leer, bei dem diese Stufe überhaupt greift.
        """
        mine = self.session.profile.printer.id
        known = profiles.printer_profiles()
        # Eine gemerkte Wahl bleibt immer stehen, auch wenn sie nicht zum
        # eingestellten Drucker gehört: Wer einmal abgewichen ist, meinte es so
        # (`test_a_remembered_choice_wins_over_the_match`). Ohne diese Zeile
        # nahm der Filter genau die Entscheidung weg, die jemand getroffen hat.
        remembered = self.ui_settings.slicer_machine_profile
        fitting = [
            entry
            for entry in machines
            if slicer_profiles.printer_for(entry.name, known) == mine
            or str(entry.path) == remembered
        ]
        if fitting:
            return fitting
        nozzle = self.session.profile.printer.nozzle_diameter
        same_nozzle = [
            entry
            for entry in machines
            if is_close(entry.nozzle, nozzle) or str(entry.path) == remembered
        ]
        return same_nozzle or machines

    def _filaments_worth_showing(
        self, machine: slicer_profiles.SlicerProfile | None
    ) -> list[slicer_profiles.SlicerProfile]:
        """Die Filamente zur Auswahl — ohne Maschine die des eigenen Herstellers.

        Mit gewähltem Maschinenprofil entscheidet der Slicer, was passt. Ohne
        eines stand hier eine leere Liste, und das war eine
        Leistungsentscheidung: Der Bestand hält **5962** Filamentprofile über
        48 Hersteller, und sie alle in eine Combobox zu legen ließ die
        Anwendung minutenlang stehen.

        Solidon weiß aber mehr, als es benutzt hat: Der Drucker des Projekts
        kennt seinen Hersteller, und die Profilnamen tragen ihn vorn („Elegoo
        PLA @EC"). Für einen Elegoo bleiben damit gut zweihundert statt
        sechstausend — eine Liste, die man lesen kann (Vorschlag 3d-druck-a0,
        03.09.2026).

        **Der Vorgabedrucker hat keinen Hersteller, und das ist genau der
        Fall, um den es geht.** ``generic-220`` heißt „Allgemeiner
        FDM-Drucker"; ein Filter auf sein leeres Herstellerfeld träfe mit
        ``startswith("")`` jeden Eintrag und stellte den Hänger wieder her, den
        die leere Liste verhindert. Ohne Hersteller bleibt es deshalb leer —
        und der Platzhalter darunter sagt, was zu tun ist, statt ein leeres
        Feld hinzustellen (§2.1: keine Sackgassen).
        """
        if machine is not None:
            return slicer_profiles.filaments(self._profiles, machine)
        # Das **erste Wort** des Herstellers, nicht sein ganzer Name: Die
        # Profile heißen „Bambu PLA Basic", der Hersteller aber „Bambu Lab" —
        # ein Vergleich auf den vollen Namen traf dort null von vier, gemessen
        # am 03.09.2026. Bei „Elegoo", „Creality" und „Anycubic" ist es
        # dasselbe Wort, der Fall fällt also nur bei zweiteiligen Namen auf.
        vendor = self.session.profile.printer.vendor.strip().casefold().split(" ")[0]
        if not vendor:
            return []
        return [
            entry
            for entry in slicer_profiles.filaments(self._profiles, None)
            if entry.name.casefold().startswith(vendor)
        ]

    def _fill_filaments(self, machine: slicer_profiles.SlicerProfile | None) -> None:
        """Die Filamentprofile zum gewählten Drucker, vorbelegt nach Material.

        Die Vorgabe ist die Grundausführung des eingestellten Materials —
        „Elegoo PETG", nicht „Elegoo PETG Translucent". Von einem Material
        liegen mehrere Ausführungen im Bestand, und sie fahren verschieden:
        das transluzente will 255 Grad, das PRO 240 bei halbem Volumenstrom.
        Wer eine besondere Spule hat, stellt sie hier ein.
        """
        fitting = self._filaments_worth_showing(machine)
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
            # Ein leeres Feld ist eine Sackgasse; der Platzhalter nennt den
            # nächsten Schritt (§2.1, Regel 17 in ihrer freundlichen Gestalt).
            self.filament_choice.setPlaceholderText(
                tr("Erst einen Drucker wählen — dann stehen die Filamente hier.")
            )
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
            found = self._filament_index(box, name)
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
        self._slot_names = []
        for index, slot in enumerate(slots):
            box = QComboBox(self.slicer_inner)
            box.setEnabled(bool(self._profiles))
            box.activated.connect(lambda _i, position=index: self._slot_filament_chosen(position))
            caption = str(slot.name or tr("Slot {number}").replace("{number}", str(index + 1)))
            self._slot_names.append(caption)
            label = QLabel(f"   {caption}", self.slicer_inner)
            # **Die Farbe steht daneben** — hier wird zugeordnet, welche Spule
            # in welchen Extruder kommt, und ohne sie ist „Schrift" ein Wort
            # ohne Bild. Dieselbe Kette wie im Filamentwähler und im Panel
            # (``shown_colour``): eigene Farbe, sonst Grauleiter, für Slot 0
            # die Farbe des Teils.
            label.setToolTip(tr("Die Farbe, in der dieses Filament in der Ansicht steht."))
            colour = QLabel(self.slicer_inner)
            colour.setPixmap(
                swatch(shown_colour(int(slot.index), slot.colour)).pixmap(
                    SWATCH_PIXELS, SWATCH_PIXELS
                )
            )
            row = QWidget(self.slicer_inner)
            # Die Zeile ist jetzt zweiteilig (Farbfeld, Text). Ihr Name steht
            # deshalb am Container: Ein Bildschirmleser findet die Zeile sonst
            # nur als „Widget", und ein Farbfeld ohne Namen ist genau die
            # Bedeutung allein über Farbe, die Regel 18 verbietet.
            row.setAccessibleName(caption)
            side = QHBoxLayout(row)
            side.setContentsMargins(0, 0, 0, 0)
            side.setSpacing(TIGHT)
            side.addWidget(colour)
            side.addWidget(label, 1)
            form.addRow(row, box)
            self.slot_rows.append((row, box))
            if index < len(stored) and stored[index]:
                box.setProperty("wanted", stored[index])

    def _profile_name(self, path: object) -> str:
        """Der Profilname zu einem Pfad aus einer Auswahlliste, oder leer.

        Die Listen tragen den Pfad als Kennung (``addItem(titel, pfad)``); was
        gespeichert und an den Slicer gereicht wird, ist der Name. Dazwischen
        liegt genau dieses Nachschlagen — die Beschriftung taugt dafür nicht,
        sie trägt einen übersetzten Zusatz.
        """
        if not path:
            return ""
        wanted = str(path)
        for entry in self._profiles:
            if str(entry.path) == wanted:
                return entry.name
        return ""

    def _filament_index(self, box: QComboBox, name: str) -> int:
        """Wo das gemerkte Filament in dieser Liste steht — oder ``-1``.

        Drei Lesarten, in dieser Reihenfolge, und jede hat ihren Grund:

        * **Der Name** ist das, was seit heute abgelegt wird. Er steht nicht in
          der Liste (dort steht die Beschriftung), also führt der Weg über das
          Profil zu seinem Pfad.
        * **Der Pfad**, falls ein Projekt ihn trägt: ``slicer_base_filament``
          merkt sich Pfade, und dieselbe Zeile liest beide Merker.
        * **Die Beschriftung**, für alles, was vor der Behebung gespeichert
          wurde. Ein Projekt mit „Generic PETG (eigenes)" darin soll seine Wahl
          nicht verlieren, nur weil sie falsch abgelegt war — im deutschen
          Fenster findet sie sich damit wieder, im englischen nicht mehr, und
          das ist genau der Fehler, der behoben wurde.
        """
        if not name:
            return -1
        for entry in self._profiles:
            if entry.name == name:
                found = box.findData(str(entry.path))
                if found >= 0:
                    return found
        found = box.findData(name)
        return found if found >= 0 else box.findText(name)

    def _make_plate_row(self) -> None:
        """Die Plattenwahl anlegen — eingehängt wird sie in ``_build_state``.

        Bei einer einzigen Platte bleibt die Zeile verborgen: Eine Wahl ohne
        Alternative ist keine, und der Kunde liest sie trotzdem.
        """
        self.plate_row = QWidget(self)
        line = QHBoxLayout(self.plate_row)
        line.setContentsMargins(0, 0, 0, 0)
        self.plate_label = QLabel(tr("Platte"), self.plate_row)
        self.plate_choice = QComboBox(self.plate_row)
        self.plate_label.setBuddy(self.plate_choice)
        self.plate_choice.activated.connect(self._plate_chosen)
        line.addWidget(self.plate_label)
        # Kein Dehnfaktor, dafür ein Anschlag dahinter: Das Feld trägt
        # „Platte 2" und die Sammelzeile, mehr nicht. Über die ganze
        # Dialogbreite gezogen sah es aus wie das Hauptfeld der Seite,
        # während die Auswahl daneben zwei Wörter lang ist.
        self.plate_choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        line.addWidget(self.plate_choice)
        line.addStretch(1)
        self.plate_row.setVisible(False)
        self._refresh_plates()

    def _refresh_plates(self) -> None:
        """Die Plattenzeile füllen — sichtbar erst ab der zweiten Platte.

        „Alle" steht oben und ist die Vorgabe, weil das der bisherige Weg
        ist: Wer nichts wählt, bekommt weiterhin jede Platte als eigene
        Druckdatei. Die Wahl einer einzelnen ist der Zusatz, nicht die neue
        Regel.
        """
        plates = self._all_plates()
        self.plate_choice.clear()
        if len(plates) < 2:
            self.plate_row.setVisible(False)
            return
        self.plate_choice.addItem(
            tr("Alle Platten ({count})").replace("{count}", str(len(plates))), None
        )
        for plate in plates:
            self.plate_choice.addItem(
                tr("Platte {number}").replace("{number}", str(plate + 1)), plate
            )
        self.plate_choice.setCurrentIndex(0)
        self.plate_row.setVisible(True)

    def _all_plates(self) -> list[int]:
        """Die Platten der Szene, aufsteigend."""
        result = self.session.last_result
        if result is None:
            return []
        return sorted({entry.plate for entry in result.scene.objects.values()})

    def _chosen_plates(self) -> list[int]:
        """Welche Platten der Lauf umfasst — alle, oder die eine gewählte.

        Gefragt wird die **Datenlage**, nicht die Sichtbarkeit der Zeile:
        ``isVisible`` antwortet ``False``, solange der Dialog nicht
        angezeigt wurde, und zwar auch für ein Widget, das ausdrücklich
        auf sichtbar steht. Wer daran hängt, bekommt beim Aufbau und in
        jedem Test außerhalb eines echten Fensters stillschweigend alle
        Platten zurück — die Wahl des Kunden wäre folgenlos gewesen.
        """
        plates = self._all_plates()
        if len(plates) < 2:
            return plates
        chosen = self.plate_choice.currentData()
        return plates if chosen is None else [int(chosen)]

    def _plate_chosen(self, _index: int) -> None:
        """Nach dem Wechsel zeigen die Filamentzeilen die Slots dieser Platte.

        Ohne diesen Ruf blieben sie auf der Wahl von vorhin stehen, und der
        Kunde ordnete Spulen einer Platte zu, die er gar nicht slict — der
        Fehler wäre erst am fertigen Druck zu sehen.
        """
        self._build_slot_rows(self.slot_form)
        # Und die Kopfzeile mit: Eine andere Platte kann andere Spulen tragen,
        # also auch ein anderes Material — genau der Fehler, den der Docstring
        # oben für die Filamentzeilen beschreibt, eine Zeile höher.
        self.refresh_materials()
        self._show_slicer_state()

    def _plate_slots(self) -> list[MaterialSlot]:
        """Die Materialslots der gewählten Platten, zusammengelegt wie beim Export.

        **Der gewählten, nicht der ersten.** Solange hier ``min(entry.plate)``
        stand, zeigte der Dialog die Spulen von Platte 1 — auch wenn Platte 2
        geslicet wurde und andere trug. Der Kunde ordnete Filamente einer
        Platte zu, die er nicht druckte, und sah den Fehler erst am Ergebnis.
        """
        result = self.session.last_result
        if result is None:
            return []
        wanted = set(self._chosen_plates())
        objects = [entry for entry in result.scene.objects.values() if entry.plate in wanted]
        if not objects:
            return []
        return threemf.merge_slots(
            [
                threemf.AssemblyPart(
                    mesh=as_mesh_data(entry.mesh), slots=tuple(entry.material_slots)
                )
                for entry in objects
            ]
        )

    def _profiles_for(self, slots: Sequence[MaterialSlot]) -> tuple[str, ...]:
        """Die gewählten Filamentprofile in der Reihenfolge **dieser** Slots.

        ``settings.slot_profiles`` ist positionsbezogen, und die Position
        meint die Liste, die im Dialog **stand**, als der Kunde wählte. Die
        Liste eines Laufs ist eine andere: Angezeigt wird die
        Zusammenlegung der gewählten Platten, gedruckt wird Platte für
        Platte, und jede legt für sich zusammen (`_plate_run`). Bei „Alle
        Platten" mit Rot auf Platte 1 und Weiß+Rot auf Platte 2 standen
        deshalb [Rot, Weiß] im Dialog und [Weiß, Rot] im Lauf der zweiten
        Platte — gemessen bekam **Weiß das Rot-Profil**, und mit dem Profil
        wandert die Temperatur (26.08.2026).

        Übersetzt wird über die Identität des Slots — Name und Farbe, genau
        der Schlüssel, über den auch ``threemf.merge_slots`` zusammenlegt.
        Das Speicherformat bleibt, wie es ist: Was der Kunde einmal wählte,
        gilt weiter je Position seiner Liste; nur die Zuordnung zum Lauf
        fragt jetzt, **welcher Slot** gemeint war.
        """
        stored = self.settings.slot_profiles
        shown = self._plate_slots()
        if not shown:
            # Ohne Anzeigeliste gibt es nichts zu übersetzen — dann gilt die
            # Position, wie bisher. Ein leeres Ergebnis wäre schlechter als
            # eine Zuordnung, die in genau diesem Fall schon immer stimmte:
            # Wer keine Szene hat, hat auch keine zweite Reihenfolge.
            return tuple(stored)
        by_slot = {
            (str(slot.name), slot.colour): stored[index]
            for index, slot in enumerate(shown)
            if index < len(stored) and stored[index]
        }
        return tuple(by_slot.get((str(slot.name), slot.colour), "") for slot in slots)

    def _slot_filament_chosen(self, position: int) -> None:
        """Die Wahl für einen Slot festhalten (§20).

        Gespeichert wird der **Name**, nicht der Pfad: er reist mit dem Projekt
        und zeigt auf einem zweiten Rechner nicht ins Leere (Regel 12).

        **Das versprach der Satz darüber, und abgelegt wurde etwas anderes:**
        ``currentText()`` gibt die *Beschriftung*, und die trägt bei einem
        selbst angelegten Profil den Zusatz „(eigenes)" — übersetzt. Im
        englischen Fenster hieß dasselbe Profil damit „Generic PETG (own)", im
        deutschen „Generic PETG (eigenes)", und der Slicer kennt keins von
        beidem: Die Wahl kam nie an, und beim nächsten Öffnen fand die
        Vorbelegung ihren eigenen Eintrag nicht wieder.

        Der Name steht im Profil, und der Weg dorthin ist der Pfad in
        ``currentData()`` — dieselbe Kennung, mit der die Liste gefüllt wurde.
        """
        if position >= len(self.slot_rows):
            return
        box = self.slot_rows[position][1]
        chosen = self._profile_name(box.currentData()) or box.currentText()
        names = list(self.settings.slot_profiles)
        names += [""] * (len(self.slot_rows) - len(names))
        names[position] = chosen
        self.settings = replace(self.settings, slot_profiles=tuple(names))
        self.state.setText(
            tr("{slot} druckt mit {profile}.")
            # Aus den Daten und nicht aus der Beschriftung: Die Zeile trägt
            # jetzt ein Farbfeld neben dem Text, ist also ein Container ohne
            # ``text()`` — und die Anzeige war ohnehin die falsche Quelle für
            # eine Meldung (dieselbe Lehre wie bei ``currentText()`` darüber).
            .replace("{slot}", self._slot_names[position])
            .replace("{profile}", chosen)
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
            tr("Werte aus {profile} übernommen.").replace(
                "{profile}", self.filament_choice.currentText()
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
        """Was Material und Geometrie an Einstellungen nahelegen (§29).

        Dieselbe Form wie die übrigen Abschnitte — siehe :meth:`_build_front`.
        """
        holder = QWidget(self)
        inner = QVBoxLayout(holder)
        inner.setContentsMargins(0, 0, 0, 0)

        self.advice_view = QTreeWidget(holder)
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

        self.apply_button = QPushButton(tr("Vorschläge übernehmen"), holder)
        self.apply_button.clicked.connect(self._apply_advice)
        inner.addWidget(self.apply_button, 0, Qt.AlignmentFlag.AlignRight)
        box = collapsible(tr("Was dieses Teil verlangt"), holder)
        self.advice_toggle = _toggle_of(box)
        return box

    def _build_state(self) -> QWidget:
        holder = QWidget(self)
        row = QVBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        # Die Plattenwahl steht **hier** und nicht bei den Profilen: Sie
        # gehört dorthin, wo geslicet wird, damit vor dem Klick zu sehen
        # ist, was gleich hinausgeht. Erzeugt wurde sie früher
        # (``_make_plate_row``), eingehängt wird sie hier.
        row.addWidget(self.plate_row)
        self.state = QLabel("", holder)
        self.state.setWordWrap(True)
        # **Keine Zahl im Balken.** Sie steht mittig, und der Rand der
        # Füllung wandert darunter hindurch: bei 45 % lag sie halb auf
        # Bernstein und halb auf der Spur, ab 60 % ganz auf Bernstein — mit
        # 1,69 Kontrast, also unlesbar. Eine Farbe, die auf beiden Gründen
        # trägt, gibt es nicht; eine dunklere Füllung nähme dem Balken den
        # Akzent (gerechnet: 4,5 Schriftkontrast kostet die Hälfte des
        # Flächenkontrasts). Der Prozentwert steht deshalb in der Zeile
        # daneben, wo ein ruhiger Grund ist.
        self.progress = QProgressBar(holder)
        self.progress.setTextVisible(False)
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
        self.slice_button.clicked.connect(self._slice)
        buttons.addButton(self.slice_button, QDialogButtonBox.ButtonRole.ActionRole)
        # Die zweite Übergabeart aus §29: nicht rechnen lassen, sondern die
        # Datei im Fenster des Slicers öffnen. Zwei Handlungen, keine
        # Betriebsart — und keine Profilpflicht, denn das Fenster bringt
        # seine eigenen Profile mit.
        self.open_button = QPushButton(tr("Im Slicer öffnen …"), self)
        self.open_button.clicked.connect(self._open_in_slicer)
        buttons.addButton(self.open_button, QDialogButtonBox.ButtonRole.ActionRole)
        # Der gemerkte Weg ist der Hauptknopf (§29: die Übergabeart wird je
        # Projekt gemerkt) — entschieden beim Aufbau, nicht live: ein
        # Hauptknopf, der unter dem Zeiger wechselt, wäre Bewegung ohne
        # Auftrag.
        make_primary(self.open_button if self.settings.handover == "open" else self.slice_button)
        self.save_button = QPushButton(tr("Druckdatei speichern …"), self)
        self.save_button.clicked.connect(self._save_gcode)
        self._hold_the_save()
        buttons.addButton(self.save_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)

        # Der Weg zu einem Slicer, sichtbar nur, solange keiner da ist.
        self.setup_button = QPushButton(tr("Zusätzliche Programme …"), self)
        self.setup_button.clicked.connect(self.setupRequested)
        buttons.addButton(self.setup_button, QDialogButtonBox.ButtonRole.ResetRole)

        self._show_slicer_state()
        return buttons

    @staticmethod
    def _machine_missing_line() -> str:
        """Die eine Quelle für den fehlenden Drucker — Knopf und Wächter
        in `_slice` sagen denselben Satz, sonst driften sie."""
        return str(tr("Dieser Slicer braucht ein Druckerprofil — bitte eines auswählen."))

    @staticmethod
    def _process_missing_line() -> str:
        return str(tr("Dieser Slicer braucht auch ein Prozessprofil — bitte eines auswählen."))

    def _profile_gap(self) -> str:
        """Was der Profilwahl noch fehlt — leer, wenn das Slicen starten darf.

        Nur die Orca-Familie verlangt Profile (`_start_profile_search`);
        PrusaSlicer und CuraEngine kommen ohne aus. Solange die Suche läuft,
        heißt die Antwort „wird durchgesehen" — kein Zustand ohne Erhebung,
        und ein Knopf, der „bitte wählen" sagt, während die Liste noch gar
        nicht da sein kann, schickt in eine leere Auswahl.
        """
        if not self._needs_profiles:
            return ""
        if self._profiles_pending:
            return str(tr("Der Profilbestand wird durchgesehen …"))
        if not str(self.machine_choice.currentData() or ""):
            return self._machine_missing_line()
        if not str(self.process_choice.currentData() or ""):
            return self._process_missing_line()
        return ""

    def _mark_fields_this_slicer_ignores(self) -> None:
        """Ein Feld, das beim eingestellten Slicer nichts tut, sagt es.

        Dieselbe Bauart wie bei den Operationen im Menü und bei den bedingten
        Feldern im Operationsdialog: **grau und begründet**, nicht unsichtbar —
        wer eine Zeile vermisst, sucht sie.

        Gemessen am 03.09.2026 trifft es eines von sechsundfünfzig Feldern bei
        PrusaSlicer und fünf bei ``CuraEngine``; die Orca-Familie nimmt alles.
        Vorher ließ sich an ihnen ziehen, ohne dass irgendetwas geschah — der
        Wert stand im Projekt, in der Druckdatei stand er nie.

        **Der eigene Hinweis wird gemerkt und zurückgegeben, nicht neu
        gebaut.** Ein Widget, das seinen Tooltip selbst führt, behält ihn: Der
        Farbknopf nennt darin den Hexwert, den sonst nichts zeigt. Ihn aus
        ``field.note`` neu zusammenzusetzen kostete genau diese Auskunft — der
        erste Anlauf hat damit ``test_the_explanation_arrives_at_the_field_
        and_at_its_label`` gerissen.

        Der Grund hängt an **beiden** Hälften der Zeile (Regel 18: Tooltip,
        Statuszeile, Bildschirmleser). In ein ausgegrautes Feld zeigt niemand;
        man zeigt auf das Wort davor.
        """
        flavour = self._current_flavour()
        for path, editor in self._editors.items():
            ignored = flavour is not None and not slicer_keys.takes(flavour, path)
            name = _slicer_title(self._slicer_path) if self._slicer_path else ""
            reason = (
                str(
                    tr("{slicer} kennt diese Einstellung nicht — der Wert bleibt ohne Wirkung.")
                ).replace("{slicer}", name)
                if ignored
                else ""
            )
            editor.setEnabled(not ignored)
            for widget in (editor, self._labels.get(path)):
                if widget is None:
                    continue
                own = widget.property(_OWN_TIP)
                if own is None:
                    # Beim ersten Mal sind die drei Kanäle die eigenen — und
                    # sie sind **nicht** derselbe Text: Der Farbknopf nennt im
                    # Tooltip zuerst den Hexwert und hängt den Satz an, während
                    # Statuszeile und Bildschirmleser nur den Satz führen. Wer
                    # sie gleichsetzt, verliert entweder den Wert oder schiebt
                    # ihn in eine Zeile, in die er nicht gehört.
                    own = (widget.toolTip(), widget.statusTip(), widget.accessibleDescription())
                    widget.setProperty(_OWN_TIP, own)
                tip, status, described = own
                widget.setToolTip(reason or str(tip))
                widget.setStatusTip(reason or str(status))
                widget.setAccessibleDescription(reason or str(described))

    def _show_slicer_state(self) -> None:
        """Ob ein Slicer da ist — und wenn nicht, der Weg zu einem.

        §27: das Backend meldet sich ab, es nörgelt nicht. Regel 17: aber es
        sagt, was jetzt möglich ist.

        Und die Lizenzgrenze steht vor dem Klick, nicht dahinter: `handover`
        fragt `activation.require` erst im Arbeiter, und mit abgelaufener
        Demo hätte der Kunde den ganzen Dialog ausgefüllt, bevor die Absage
        kam (Regel 19). Von den vier Grenzen war SLICER die einzige ohne
        dieses Ausgrauen. Der Kern bleibt die zweite Hürde; das hier ist die
        Freundlichkeit davor — dieselbe Bauart wie bei den Operationen im
        Menü, mit dem Grund an beiden Kodierungen (Regel 18: Tooltip,
        Statuszeile, Bildschirmleser).
        """
        found = self._slicer_path
        state = activation.state()
        # **Der häufigste Grund stand in keinem der Zweige.** Beide Knöpfe
        # brauchen einen Slicer, und wenn keiner da ist, sperrte sie
        # ``found is None`` unten wortlos: Der ``reason``-Zweig verlangt
        # ``found is not None``, also blieb der Satz leer. Gefunden hat es der
        # Wächter über alle Knöpfe des Dialogs (03.09.2026) — die zwei Tests je
        # Knopf daneben prüfen den Fall, dass ein Slicer da ist, und der ist
        # der seltenere: Ein Kunde ohne eingerichteten Slicer sieht diesen hier
        # bei jedem Öffnen. Die Auskunft gab es, aber in der Zustandszeile
        # darunter; wer auf den grauen Knopf zeigt, fragt ihn und nicht sie.
        no_slicer = str(
            tr("Dafür fehlt ein Slicer — der Knopf Zusätzliche Programme richtet einen ein.")
        )
        reason = ""
        if not state.unlocked:
            reason = licence_lock_line(state)
        elif found is None:
            reason = no_slicer
        elif found is not None:
            # Die dritte Hürde derselben Bauart: Ein Slicer der Orca-Familie
            # ohne gewähltes Profil lehnt jeden Auftrag ab — das stand bisher
            # erst nach dem Klick in der Statuszeile (Fund ce, 26.08.2026).
            reason = self._profile_gap()
        # Ein laufender Auftrag hält den Knopf zu, gleich was die drei
        # Bedingungen sagen — sonst schaltete eine nachgereichte
        # Profilantwort ihn mitten im Lauf wieder frei.
        running = self._worker is not None
        self.slice_button.setEnabled(found is not None and not reason and not running)
        self.slice_button.setToolTip(reason)
        self.slice_button.setStatusTip(reason)
        self.slice_button.setAccessibleDescription(reason)
        # Der Öffnen-Weg hat andere Bedingungen als der Rechen-Weg: Profile
        # braucht er nie (das Fenster bringt seine mit), dafür ein Programm
        # mit Fenster — CuraEngine allein rechnet nur. Lizenz und laufender
        # Auftrag gelten für beide.
        open_reason = ""
        if not state.unlocked:
            open_reason = licence_lock_line(state)
        elif found is None:
            # Dieselbe Lücke wie oben, und sie war hier genauso still: Ohne
            # Slicer sperrt die Zeile unten auch diesen Knopf, und keiner der
            # beiden Zweige darüber hatte einen Satz dafür.
            open_reason = no_slicer
        elif handover.window_program(found) is None:
            open_reason = str(tr("Zu diesem Slicer ist kein Fenster installiert — er rechnet nur."))
        self.open_button.setEnabled(found is not None and not open_reason and not running)
        self.open_button.setToolTip(open_reason)
        self.open_button.setStatusTip(open_reason)
        self.open_button.setAccessibleDescription(open_reason)
        self.setup_button.setVisible(found is None)
        self._mark_fields_this_slicer_ignores()
        if found is None:
            self.state.setText(
                tr("Kein Slicer eingerichtet — die Einstellungen lassen sich trotzdem pflegen.")
            )
        elif reason:
            # **Der Grund gehört auf den Bildschirm, nicht in einen Tooltip.**
            # Er stand bis hierhin nur an ``slice_button`` — und ein Tooltip
            # erscheint erst, wenn jemand mit der Maus darauf wartet. Wer den
            # grauen Knopf sieht und nicht auf die Idee kommt, ihn anzuzielen,
            # las nirgends, was ihm fehlt; die Auswahl dazu liegt zudem in
            # einer zugeklappten Box (Handlauf, 30.08.2026). Ein grauer Knopf
            # allein ist außerdem Bedeutung über Farbe (Regel 18).
            #
            # Nur wenn es einen Grund gibt: Ohne einen trägt die Zeile das
            # Ergebnis des letzten Laufs, und das wäre hier nicht zu
            # überschreiben, sondern stehen zu lassen.
            self.state.setText(str(reason))
            self._state_shows_reason = True
        elif open_reason and self.settings.handover == "open":
            # Dieselbe Regel für den Öffnen-Weg — aber nur, wenn er der
            # gemerkte Hauptweg dieses Projekts ist: Der Grund eines
            # Nebenknopfs verdrängt keine Ergebniszeile.
            self.state.setText(open_reason)
            self._state_shows_reason = True
        elif self._state_shows_reason:
            # **Ein Grund, der nicht mehr gilt, muss weichen.** Der Zweig
            # darüber schützt ein *Ergebnis* davor, überschrieben zu werden —
            # ein veralteter *Grund* ist davon nicht gedeckt. Nach dem Wechsel
            # von der Orca-Familie auf PrusaSlicer stand sonst weiter „braucht
            # ein Druckerprofil" da, während der Knopf längst frei war.
            self.state.setText("")
            self._state_shows_reason = False

    def _pick_slicer(self) -> Path | None:
        """Welcher Slicer gilt — der gemerkte, sonst der erste gefundene.

        Ein Rechner kann drei haben. Bis hierhin gewann der erste Treffer der
        Suchreihenfolge, und wollte der nicht, war das eine Sackgasse: Der
        Dialog bot keinen zweiten an, obwohl zwei danebenstanden.

        **Ohne Widget**, weil das hier aus dem Konstruktor läuft und die
        Auswahlfelder erst danach entstehen — dieselbe Reihenfolgefalle, die
        die Bedingungsliste des Skizzeneditors schon einmal leer ließ. Das
        Füllen macht :meth:`_fill_slicer_choice` am Ende des Aufbaus.
        """
        found = discover.find_programs("slicer", tools.SLICERS)
        self._slicers = found
        remembered = discover.remembered_path("slicer")
        return next((entry for entry in found if str(entry) == remembered), None) or (
            found[0] if found else None
        )

    def _fill_slicer_choice(self) -> None:
        """Die Auswahl füllen — sichtbar nur, wenn es etwas zu wählen gibt.

        Eine Zeile mit einem einzigen Eintrag ist eine Frage ohne
        Antwortmöglichkeit (§2.4); bei einem Slicer bleibt sie weg. Der volle
        Pfad steht im Tooltip: Zwei Installationen desselben Programms
        unterscheiden sich am Ordner, nicht am Namen.
        """
        with QSignalBlocker(self.slicer_choice):
            self.slicer_choice.clear()
            for entry in self._slicers:
                self.slicer_choice.addItem(_slicer_title(entry), str(entry))
                self.slicer_choice.setItemData(
                    self.slicer_choice.count() - 1, str(entry), Qt.ItemDataRole.ToolTipRole
                )
            if self._slicer_path is not None and self._slicer_path in self._slicers:
                self.slicer_choice.setCurrentIndex(self._slicers.index(self._slicer_path))

        several = len(self._slicers) > 1
        self.slicer_choice.setVisible(several)
        layout = self.slicer_inner.layout()
        if isinstance(layout, QFormLayout):
            label = layout.labelForField(self.slicer_choice)
            if label is not None:
                label.setVisible(several)

    def _slicer_chosen(self, index: int) -> None:
        """Ein anderer Slicer: merken und die Profile neu durchsehen.

        Gemerkt wird über `discover.remember_path`, also dort, wo auch ein von
        Hand eingetragener Pfad steht — die Wahl überlebt damit den Neustart
        und gilt für jeden, der nach dem Slicer fragt.
        """
        if not 0 <= index < len(self._slicers):
            return
        chosen = self._slicers[index]
        if chosen != self._slicer_path:
            self._forget_result()
        discover.remember_path("slicer", str(chosen))
        self._slicer_path = chosen
        self._clear_profile_choices()
        self._show_slicer_state()
        self._start_profile_search()

    def recheck_slicer(self) -> None:
        """Noch einmal nachsehen, ob jetzt ein Slicer da ist.

        Nach dem Besuch bei den zusätzlichen Programmen: Wer einen gerade
        installiert hat, soll nicht schließen und neu öffnen müssen.
        """
        discover.forget_cache()
        before = self._slicer_path
        self._slicer_path = self._pick_slicer()
        if self._slicer_path != before:
            self._forget_result()
        self._show_slicer_state()
        if self._slicer_path is not None:
            self.state.setText("")
            self._start_profile_search()

    def _label(self, field: Field) -> QLabel:
        """Die Beschriftung der Zeile — mit demselben Satz wie das Feld daneben.

        Wer eine Zeile liest, zeigt auf ihre Beschriftung und nicht auf das
        Eingabefeld — ein Tooltip, der nur am Feld hängt, findet nur, wer schon
        dort steht.

        Als Widget und nicht als Zeichenkette, damit der Satz dort steht, wo
        die Beschriftung entsteht. Erreichbar wäre sie auch danach: ``addRow``
        baut aus einem String selbst ein `QLabel`, und
        ``QFormLayout.labelForField`` gibt es heraus — so macht es der
        Operationsdialog, der seine Zeilen als Zeichenketten anlegt. Beides
        geht; hier stand die Wahl für die Stelle, an der man es nicht vergisst.

        **Und aufgelöst wird hier, nicht in der Tabelle.** ``field.title`` und
        ``field.note`` sind träge Texte (:class:`TranslatableText`); ihr
        ``str()`` steht an jeder Stelle, an der ein Text an Qt geht, damit er
        die Sprache trägt, die beim **Bauen** des Dialogs gilt — und nicht die
        vom Import.
        """
        # **Ohne Einheit in der Klammer** (B12): Sie steht am Wert selbst, den
        # ``_make_setting_editor`` mit ihr beschriftet.
        label = QLabel(str(field.title), self)
        note = str(field.note)
        if note:
            label.setToolTip(note)
            label.setStatusTip(note)
        # Abgelegt wie der Editor daneben: Die Suche hebt beide Hälften der
        # Zeile hervor, und wer eine Zeile sucht, sucht ihr Wort — das steht
        # links (:meth:`_lift`).
        self._labels[field.path] = label
        return label

    def _editor(self, field: Field) -> QWidget:
        """Ein Feld je Einstellung — und keines breiter, als sein Wert ist.

        Ein ``QFormLayout`` gibt der Spalte der Editoren allen Platz, den es
        hat. Im Kasten „Das Wichtigste" waren das gemessene 726 von 970
        Bildpunkten je Zeile, für Werte wie ``0,200`` und ``215``: Die Zahl
        stand links in einem handbreiten Kasten, ihre Beschriftung am anderen
        Ende der Zeile, und zusammengehört haben sie trotzdem. Acht Zeilen
        davon sind das erste, was jemand von diesem Dialog sieht.

        Haken bleiben ungedeckelt: Bei ihnen ist die breite Fläche kein
        gedehnter Kasten, sondern ein größeres Ziel — zu sehen ist ohnehin nur
        das Kästchen.
        """
        editor = _make_setting_editor(field, self, self._editor_changed)
        self._editors[field.path] = editor
        # **Der Satz gehört an beide Hälften der Zeile.** Ein Tooltip nur am
        # Eingabefeld findet, wer schon dort steht; wer die Zeile liest, zeigt
        # auf ihre Beschriftung. Der ``statusTip`` kommt dazu, weil ein
        # Bildschirmleser ihn vorliest und die Statuszeile ihn zeigt, ohne dass
        # jemand warten muss (Regel 18: nicht nur eine Kodierung).
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
                _set_setting_editor(editor, field, value)
        finally:
            self._loading = False

    def _collect(self) -> PrintSettings:
        """Aus den Feldern zurück ins Modell."""
        settings = self.settings
        for field in FIELDS:
            editor = self._editors[field.path]
            value = _setting_editor_value(editor, field)
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
        über die Stufe, aus der man kam (Regel 19: keine Rückfrage).

        **Bis auf die Slotbelegung**, und die ist keine Ausnahme von diesem
        Satz, sondern fällt gar nicht unter ihn: Sie kommt von keiner Stufe
        zurück, weil sie von keiner kam (:meth:`_resolved` misst es nach). Wer
        „fein" wählte, hatte danach zwei Slots ohne Spule — und sah es nicht,
        denn die zwei Auswahlfelder standen unverändert da, während das Modell
        nichts mehr davon wusste. Beim Export lief die weiße Schrift dann mit
        dem Filament der Platte.
        """
        chosen = self.quality.currentData()
        if chosen is None:
            return
        self.settings = self._resolved(chosen)
        self._load_into_editors()
        self._refresh_advice()

    # --- Vorschläge -----------------------------------------------------------

    def _current_advice(self) -> list[SettingAdvice]:
        """Die Vorschläge — ohne die, bei denen der gewählte Slicer nicht mitkann.

        Der Kern rechnet ohne Kenntnis des Slicers, und das ist richtig: Was
        die Geometrie verlangt, hängt nicht am Programm daneben. Anzeigen darf
        man einen Vorschlag trotzdem nur, wenn er ankommt — „Außenwand auf
        Sollmaß" kennt nur die Orca-Familie, und mit PrusaSlicer übernähme der
        Kunde eine Empfehlung, die in keiner Datei landet.

        Gemessen am 03.09.2026 sind es zwei von sechsundfünfzig Feldern.
        Solange kein Slicer gewählt ist, wird nichts weggelassen: Dann steht
        noch nicht fest, was ankommt, und eine leere Liste wäre die schlechtere
        Auskunft.
        """
        entries = advise.advise(
            self.settings,
            self.session.profile,
            self.slice_result,
            bounds=self._bounds(),
            fit_kinds=self._fits_in_play(),
            connectors=self._connector_diameters(),
        )
        flavour = self._current_flavour()
        if flavour is None:
            return entries
        return [entry for entry in entries if slicer_keys.takes(flavour, entry.path)]

    def _current_flavour(self) -> slicer_keys.SlicerFlavour | None:
        """Die Familie des eingestellten Slicers, solange einer dasteht."""
        if self._slicer_path is None:
            return None
        return slicer_keys.flavour_of(self._slicer_path.name)

    def _connector_diameters(self) -> tuple[float, ...]:
        """Die Durchmesser der Zapfen, die beim Teilen entstanden sind.

        Aus den Merkmalen und nicht aus dem Stapel: Die Stiftplanung rechnet
        den Durchmesser aus der Schnittfläche, er ist also kein Parameter, den
        jemand eingetragen hätte. Wo er steht, ist das erzeugte Merkmal.

        Nur die Zapfen, nicht die Bohrungen — es ist dasselbe Maß plus Spiel,
        und zweimal gezählt sähe es nach doppelt so vielen Verbindern aus.

        **Und nur die erzeugten.** Ein „Zapfen" aus der Merkmalserkennung ist
        eine Vermutung über eine Form, und sein Durchmesser ist, was der
        Erkenner hineingepasst hat — an einem gerippten Bogen kann das alles
        sein. Gemessen an einem heruntergeladenen Sockel von 160 auf 231 auf
        14 mm: erkannt wurden zehn Zapfen, der dickste mit **Ø 631,6 mm**, und
        die Wandregel daneben rechnete daraus einen Vorschlag von **376 Wänden**.
        *Vorschläge übernehmen* schrieb ihn ins Projekt. Eine Vermutung darf
        keine Einstellung setzen; der Docstring oben sagt es seit je — „wo er
        steht, ist das **erzeugte** Merkmal".
        """
        result = self.session.last_result
        if result is None:
            return ()
        return tuple(
            float(feature.params["diameter"])
            for entry in result.scene.objects.values()
            for feature in entry.features.values()
            if feature.kind == "pin"
            and feature.provenance == "generated"
            and "diameter" in feature.params
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
                    f"{marker}{str(field.title) if field else entry.path}",
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
        # **Ein gesperrter Knopf nennt seinen Grund** — dieselbe Zusage, die
        # „Slicen" und „Druckdatei speichern …" darunter einlösen, und die
        # einzige Stelle im Dialog, an der sie fehlte (gemessen am 03.09.2026
        # über alle sichtbaren Knöpfe). Die Tabelle darüber sagt zwar „Nichts
        # einzuwenden.", aber das ist ein Satz an einer anderen Stelle; wer auf
        # den grauen Knopf zeigt, fragt ihn und nicht sie. An allen drei
        # Kanälen, weil ein Grund, den nur die Maus findet, für den
        # Bildschirmleser keiner ist (Regel 18).
        why = (
            "" if entries else tr("Es gibt nichts zu übernehmen — die Werte passen zu diesem Teil.")
        )
        self.apply_button.setToolTip(why)
        self.apply_button.setStatusTip(why)
        self.apply_button.setAccessibleDescription(why)
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

    def _remember_slicer_choice(self, *, require_machine: bool) -> None:
        """Was im Dialog steht, gilt auch für den Export (§29).

        Gemerkt wurde das nur beim **Slicen**. Wer die Profile hier einstellte
        und danach über *Datei → Exportieren* eine 3MF schrieb, bekam die
        Auswahl vom vorletzten Mal — der Docstring von :func:`remembered_setup`
        verspricht mehr, und für den Nutzer ist es dieselbe Entscheidung.

        ``require_machine`` beim Schließen: Die Profilsuche läuft im
        Hintergrund, und wer den Dialog vorher wieder zumacht, hat eine leere
        Auswahl vor sich. Sie zu übernehmen hieße, eine gemerkte Einstellung
        zu löschen, weil niemand hingesehen hat.

        Und wo es **gar nichts zu wählen gibt**, gibt es auch nichts zu
        merken: Für ``prusa`` und ``cura`` steht die Auswahl leer, weil Solidon
        die Maschine selbst beschreibt (`_clear_profile_choices`). Das Leere zu
        merken löschte die Wahl, die zum nächsten Orca-Lauf gehört — dieselbe
        Falle wie beim Schließen, nur ohne Wartezeit.

        Gefragt sind dabei die Auswahlfelder und nicht ``_profiles``: Leer ist,
        was der Nutzer leer sieht.
        """
        if not any(
            combo.count()
            for combo in (self.machine_choice, self.process_choice, self.filament_choice)
        ):
            return
        machine = str(self.machine_choice.currentData() or "")
        if require_machine and not machine:
            return
        self.ui_settings.slicer_machine_profile = machine
        self.ui_settings.slicer_base_process = str(self.process_choice.currentData() or "")
        filament = str(self.filament_choice.currentData() or "")
        self.ui_settings.slicer_base_filament = filament
        # Zu welchem Drucker die drei gehören. Ohne den Vermerk trägt das
        # nächste Projekt auf einer anderen Maschine dieselben Profile.
        self.ui_settings.slicer_profile_printer = self.session.profile.printer.id
        # Und zu welchem Slicer: Ein Orca-Maschinenprofil ist für PrusaSlicer
        # keine Auskunft, sondern eine fremde Datei — und der frühe Rückweg
        # oben ließ den Orca-Bestand jeden Wechsel überleben, denn nach einem
        # Wechsel auf Prusa oder Cura sind die Felder immer leer (gemessen
        # 30.08.2026, Begründung am Feld in settings.py).
        if self._slicer_path is not None:
            self.ui_settings.slicer_profile_slicer = str(self._slicer_path)
        # Und je Material: „petg" allein sagt nicht, welche der sieben Spulen
        # gemeint war, und nach einem TPU-Teil stünde die falsche da.
        if filament:
            self.ui_settings.slicer_filament_per_material[self.session.profile.material.id] = (
                filament
            )

    def _current_setup(self) -> handover.SlicerSetup | None:
        """Der eingestellte Slicer mit der Profilwahl aus den Feldern (§29).

        Was in der Auswahl steht, gilt — sie ist automatisch vorbelegt, aber
        der Nutzer darf abweichen, und dann zählt seine Wahl. Eine Stelle für
        beide Übergabearten: Der Rechen-Weg und der Öffnen-Weg lesen dieselben
        Felder, und zwei Abschriften davon drifteten auseinander.
        """
        found = self._slicer_path
        if found is None:
            return None
        try:
            setup = handover.detect(found)
        except AppError as problem:
            show_error(problem, self)
            return None
        return replace(
            setup,
            machine_profile=str(self.machine_choice.currentData() or ""),
            base_process=str(self.process_choice.currentData() or ""),
            base_filament=str(self.filament_choice.currentData() or ""),
        )

    def _remember_handover(self, kind: HandoverKind) -> None:
        """Die benutzte Übergabeart merken (§29) — bei Nutzung, nie bei Ansicht.

        Über :attr:`settings` reist sie mit ``set_print_settings`` ins
        Projekt; der gemerkte Weg wird beim nächsten Aufbau der Hauptknopf.
        """
        if self.settings.handover != kind:
            self.settings = replace(self.settings, handover=kind)

    def _open_in_slicer(self) -> None:
        """Die zweite Übergabeart aus §29: die Platten im Fenster des Slicers.

        Kein Profil, kein Zeitlimit, kein Rücklesen — ab dem Öffnen gehört
        der Auftrag dem Nutzer. Geschrieben wird derselbe Plattenaufbau wie
        beim Rechen-Weg (:meth:`_plate_run`), nur in den Austauschordner
        statt in einen Arbeitsordner, der mit dem Dialog verschwindet: Das
        Fenster des Slicers braucht Sekunden zum Laden, und eine Datei, die
        vorher verschwindet, wäre eine Übergabe ins Leere.

        Synchron und ohne Zeiger, wie der Bestand den Plattenaufbau in
        :meth:`_slice` hält — gerechnet wird hier nichts, geschrieben in
        Zehntelsekunden.
        """
        result = self.session.last_result
        objects = list(result.scene.objects.values()) if result is not None else []
        if not objects:
            self.state.setText(tr("Es ist nichts da, was sich öffnen ließe."))
            return
        setup = self._current_setup()
        if setup is None:
            return
        self._remember_slicer_choice(require_machine=False)
        self._remember_handover("open")

        folder = discover.exchange_dir() / "open-in-slicer"
        name = self.session.path.stem if self.session.path else "solidon"
        plates = self._chosen_plates()
        findings: list[Finding] = []
        try:
            folder.mkdir(parents=True, exist_ok=True)
            # ``plates`` ist nie leer, solange es Objekte gibt: ``_all_plates``
            # ist nur ohne ``last_result`` leer, und genau dann hat der frühe
            # Rückweg über ``objects`` oben schon geantwortet — dieselbe
            # Quelle, zwei Ecken. Ohne diese Kette stünde unten „0 Platten".
            runs = [
                self._plate_run(
                    objects,
                    plate,
                    folder,
                    name,
                    setup,
                    with_settings=self.ui_settings.print_settings_in_files,
                )
                for plate in plates
            ]
            for run in runs:
                handover.open_in_slicer(run.model, setup)
                findings.extend(run.findings)
        except AppError as problem:
            show_error(problem, self)
            return
        if findings:
            # Die Vorprüfung gehört in den Bericht wie beim Rechen-Weg —
            # nur dass es hier nie einen G-Code-Rückweg geben wird.
            self.reported.emit(findings)
        # Die Handlung quittiert sich (§2.8): Das fremde Fenster braucht
        # Sekunden, und ein Knopf ohne Antwort wäre für genau diese
        # Sekunden ein Knopf, der nichts tut.
        self.state.setText(
            tr("An {slicer} übergeben — das Fenster gehört jetzt Ihnen.").replace(
                "{slicer}", _slicer_title(setup.executable)
            )
            if len(runs) == 1
            else tr("An {slicer} übergeben — {count} Platten, je eine Datei.")
            .replace("{slicer}", _slicer_title(setup.executable))
            .replace("{count}", str(len(runs)))
        )

    def _slice(self) -> None:
        result = self.session.last_result
        objects = list(result.scene.objects.values()) if result is not None else []
        if not objects:
            self.state.setText(tr("Es ist nichts da, was sich slicen ließe."))
            return

        setup = self._current_setup()
        if setup is None:
            return
        # Nur die Orca-Familie: PrusaSlicer läuft mit Solidons vollständiger
        # ini, und CuraEngine bekommt die Maschine aus dem Kern selbst
        # (`_machine_keys`) — für Cura gibt es strukturell keine Profile zu
        # wählen, und die Forderung war eine Wahl aus einer leeren Liste.
        if setup.flavour == "orca" and not setup.machine_profile:
            self._open_slicer_section()
            self.state.setText(self._machine_missing_line())
            return
        # Das Prozessprofil ist genauso wenig verzichtbar, nur fiel es später
        # auf: die Orca-Familie nimmt kein Prozessprofil an, das nicht zum
        # Drucker passt, und ohne ein Systemprofil darunter hat Solidons
        # Datei nichts, wozu sie passen könnte (siehe `_orca_process`). Der
        # Lauf lief bis dahin los und endete in „Der Slicer hat keine
        # Druckdatei geschrieben" — ein Satz über das Ende, nicht über die
        # Ursache.
        if setup.flavour == "orca" and not setup.base_process:
            self._open_slicer_section()
            self.state.setText(self._process_missing_line())
            return
        self._remember_slicer_choice(require_machine=False)
        # Gemerkt bei Nutzung, nie bei Ansicht (§29): Wer rechnet, dessen
        # Hauptweg ist das Rechnen — der Öffnen-Weg merkt sich genauso.
        self._remember_handover("slice")

        self._temporary = TemporaryDirectory(prefix="solidon-handover-")
        folder = Path(self._temporary.name)
        name = self.session.path.stem if self.session.path else "solidon"
        # Die gewählten, nicht alle: Wer Platte 2 slicen will, bekommt
        # eine Druckdatei und nicht drei, von denen er zwei wegwirft.
        plates = self._chosen_plates()
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
        worker.crashed.connect(lambda detail: self._slice_failed(InternalError(detail=detail)))
        worker.finished.connect(self._slice_finished)
        worker.step.connect(self._slicing_plate)
        self._worker = worker
        self._leash.start(worker)

    def _plate_run(
        self,
        objects: list[SceneObject],
        plate: int,
        folder: Path,
        name: str,
        setup: handover.SlicerSetup,
        *,
        with_settings: bool = True,
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
            #
            # ``with_settings=False`` kommt vom Übergabeweg „Im Slicer öffnen":
            # Dort gehört das Fenster danach dem Nutzer, und wer im Kopf des
            # Dialogs den Haken weggenommen hat, will genau dort sein eigenes
            # Profil sehen. Beim Rechen-Weg bleibt es dabei — dort misst
            # Solidon mit seinen Werten und liest das Ergebnis zurück; ohne sie
            # wäre die gemessene Zahl die eines fremden Profils.
            settings=self.settings if with_settings else None,
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
        chosen = self._profiles_for(slots)
        return PlateRun(
            plate=plate,
            model=written,
            # Die Wahl aus den Slot-Zeilen reist am Slot selbst: eingesammelt
            # wurde sie schon immer, angekommen ist sie hier nie — alle Slots
            # slicten mit dem Basisfilament, und „druckt mit" war eine Zusage
            # ohne Deckung (§20).
            slots=handover.with_slot_profiles(slots, chosen),
            keep_arrangement=keep,
            # Die höchste der Platte: Der Vergleich fragt, ob der G-Code so
            # hoch wird wie das Modell, und ein niedrigeres Teil daneben
            # ändert daran nichts.
            model_height=max(
                (as_mesh_data(entry.mesh).bounds.size[2] for entry in on_plate), default=None
            ),
            findings=tuple(findings),
        )

    def _slicing_plate(self, index: int, count: int) -> None:
        """Bei welcher Platte der Lauf steht (§2.8).

        Nur bei mehreren: „Platte 1 von 1" wäre eine Zahl ohne Aussage.
        """
        if count > 1:
            self.progress.setValue(index - 1)
            self.state.setText(
                tr("Der Slicer rechnet — Platte {number} von {count} …")
                .replace("{number}", str(index))
                .replace("{count}", str(count))
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
        # **Über ``facts``, nicht von Hand.** Hier stand `f"{minutes:.0f} min"`
        # und `f"{grams:.1f} g"`: Die Statuszeile schrieb für dieselbe Größe
        # „10 h 5 min" und „18 g", dieser Dialog „605 min" und „18,4 g" — eine
        # Sitzung, zwei Schreibweisen. Dazu waren `min` und `g` feste
        # Zeichenketten in der Oberfläche (Regel 20), während `facts.py` sie
        # ausdrücklich durch `tr()` schickt.
        if metrics.print_minutes is not None:
            parts.append(f"{tr('Druckzeit')}: {duration(metrics.print_minutes * 60.0)}")
        grams = metrics.grams(self.settings.filament.density)
        if grams is not None:
            parts.append(f"{tr('Material')}: {mass(grams)}")
        if metrics.layer_count is not None:
            parts.append(f"{tr('Schichten')}: {metrics.layer_count}")
        if len(outcomes) > 1:
            parts.append(f"{tr('Platten')}: {len(outcomes)}")
        self.state.setText(" · ".join(parts) if parts else tr("Fertig geslicet."))
        # Die Dateien liegen im Arbeitsordner, der beim Schließen verschwindet.
        # Ohne diesen Knopf wäre der ganze Lauf eine Zahl auf dem Bildschirm
        # und nichts, was auf einen Drucker geht.
        self._gcode = [entry.gcode_path for entry in outcomes]
        # Ab hier trägt die Zeile ein Ergebnis und keinen Grund.
        self._state_shows_reason = False
        self._release_the_save()
        outcomes[0].findings = [*self._pending_findings, *outcomes[0].findings]
        self._pending_findings = []
        self.sliced.emit(outcomes)
        _log.info(
            "sliced %d plate(s) with %s in %.1f s",
            len(outcomes),
            metrics.slicer,
            sum(entry.seconds for entry in outcomes),
        )

    def _hold_the_save(self) -> None:
        """Den Speichern-Knopf sperren — und sagen, was ihm fehlt.

        Er ist das Ziel eines Slicer-Kunden: „Druckdatei speichern …" ist der
        Satz, für den er gekommen ist. Gesperrt stand er wortlos da, während
        die zwei Knöpfe daneben ihren Grund vorbildlich nennen — *Slicen*
        sagt „Dieser Slicer braucht ein Druckerprofil", *Im Slicer öffnen*
        sagt „Zu diesem Slicer ist kein Fenster installiert". Nur hier stand
        nichts, und der Grund ist der einfachste von allen: Es gibt noch keine
        Datei.

        Dieselben drei Kanäle wie dort — Tooltip, Statuszeile und die
        Beschreibung für den Bildschirmleser (Regel 18: eine Bedeutung nie
        allein über das Aussehen).
        """
        reason = str(tr("Noch keine Druckdatei — sie entsteht beim Slicen."))
        self.save_button.setEnabled(False)
        self.save_button.setToolTip(reason)
        self.save_button.setStatusTip(reason)
        self.save_button.setAccessibleDescription(reason)

    def _release_the_save(self) -> None:
        """Freigeben — und den Grund wegnehmen, der nicht mehr gilt.

        Ein Hinweis, der an einem freigegebenen Knopf hängen bleibt, ist die
        Umkehrung des Fehlers: Er sagt, etwas fehle, während es da ist.
        """
        self.save_button.setEnabled(True)
        self.save_button.setToolTip("")
        self.save_button.setStatusTip("")
        self.save_button.setAccessibleDescription("")

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

    def _slice_failed(self, problem: AppError, findings: Sequence[Finding] = ()) -> None:
        """Der Lauf ist gescheitert: Fehlerfenster **und** Zeile im Dialog.

        Die Zeile stand auf ``""``, und damit hatte das Fenster den Lauf
        vergessen, sobald jemand das Fehlerfenster zumachte — dort, wo eben
        noch „Der Slicer rechnet …" stand, war nichts. Gemessen im
        Kundendurchgang: PrusaSlicer lehnte eine Platte in Bettkoordinaten ab
        („Der Slicer sagt, die Teile liegen außerhalb seines Bauraums"), der
        Satz erschien einmal und war danach fort.

        Genommen wird der Satz des Fehlers selbst und keine eigene
        Formulierung: Zwei Sätze über dieselbe Sache driften auseinander, und
        der hier trägt schon die Ursache.
        """
        if findings:
            self.reported.emit(list(findings))
        self.state.setText(str(problem.detail) if problem.detail else tr("Abgebrochen."))
        show_error(problem, self)

    def _slice_finished(self) -> None:
        self.progress.setVisible(False)
        self.cancel_slice.setVisible(False)
        worker = self._worker
        self._worker = None
        # Nicht blank freischalten: Der Knopf hat inzwischen drei Bedingungen
        # (Slicer, Lizenz, Profilwahl), und die eine Stelle kennt sie alle —
        # nach dem Austragen des Arbeiters, sonst hielte dessen Wache ihn zu.
        self._show_slicer_state()
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

    def done(self, result: int) -> None:
        """Auch die Knöpfe räumen auf, nicht nur das Schließkreuz.

        ``closeEvent`` kommt, wenn das Fenster geschlossen wird. *Slicen*,
        *Übernehmen* und *Abbrechen* gehen aber über ``done``, und Qt schickt
        dabei kein Schließereignis — gemessen: Nach ``accept()`` lief die
        Profilsuche weiter, und der Dialog war weg, sobald der Aufrufer seine
        Referenz fallen ließ. Ein Thread, der sein Fenster überlebt, nimmt den
        Prozess mit; genau dagegen ist die Halteleine geschrieben.
        """
        self._settle()
        super().done(result)

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Alles loslassen, was dieses Fenster außerhalb von Qt hält.

        Warum der Name, warum die eigene Frist: :mod:`app.ui.leash`.
        """
        self.wait_for_workers(timeout_ms)

    def wait_for_workers(self, timeout_ms: int = 2000) -> None:
        """Derselbe Weg für die Suite, die Dialoge wegräumt statt sie zu
        schließen.

        Der Name ist der des Hauptfensters, und das ist der Punkt: Die
        Aufräumhilfe der Suite (``tests/conftest.py``) sucht ihn an jedem
        obersten Fenster. Ein Dialog, der ihn nicht führt, bleibt dort
        unbeachtet — mit laufendem Arbeiter.
        """
        self._settle(timeout_ms)

    def _settle(self, timeout_ms: int | None = None) -> None:
        """Den Ordner erst freigeben, wenn niemand mehr darin liest.

        Der Slicer-Lauf wird abgebrochen statt abgewartet: ``worker.wait()``
        ohne Grenze stand hier im Qt-Hauptthread, und wer während eines
        großen Auftrags schloss, hatte eine eingefrorene Anwendung, bis der
        externe Slicer von sich aus fertig war — Minuten. Das Warten bleibt,
        aber nach dem Abbruch ist es kurz: der Kindprozess stirbt binnen
        Sekunden, und ohne das Warten stürbe der Thread über einem
        zerstörten Dialog.
        """
        # Genau einmal: Es gibt drei Wege hinaus (Knopf, Schließkreuz,
        # Wegräumen), und zwei davon können hintereinander kommen. Zweimal
        # aufzuräumen schriebe die Slicer-Wahl zweimal und wartete zweimal.
        if self._settled:
            return
        self._settled = True
        # Erst merken, dann abräumen: Die Auswahl steht in Widgets, die es
        # gleich nicht mehr gibt.
        self._remember_slicer_choice(require_machine=True)
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.cancel()
        for pending in (self._worker, self._profile_worker):
            if pending is not None and pending.isRunning():
                # Ohne Grenze, wenn der Weg über das Schließen geht (siehe
                # oben); mit Grenze, wenn die Suite wegräumt — dort soll ein
                # hängender Arbeiter den Lauf nicht anhalten, sondern auffallen.
                pending.wait() if timeout_ms is None else pending.wait(timeout_ms)
        self._leash.wait_all()
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
