"""Das Hauptfenster (Bauplan §2.5).

Höchstens drei sichtbare Zonen: die Panels links, der Viewport in der Mitte,
Prüfbericht oder Chat rechts — und die rechte Seite klappt mit einer Taste ganz
weg. Betriebsarten gibt es nicht; es gibt einen Zustand, und der ist die Szene.

Das Menü steht auch hier nicht ausgeschrieben: es wird aus dem Register gebaut
— eine Operation erscheint also im Menü, in der Palette und auf der
Kommandozeile, sobald sie deklariert ist (§10).
"""

from __future__ import annotations

import inspect
import time
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
from copy import copy
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any, Final, cast

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QShortcut,
    QShowEvent,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from app.branding import APP_NAME, APP_VERSION, PART_FILE_SUFFIX, PROJECT_SUFFIX
from app.core import activation, bootstrap, examples, manual, updates
from app.core.agent import apply as agent_apply
from app.core.agent.analysis import ANALYSIS_KINDS, analysis_text
from app.core.agent.session import (
    MAX_STEPS,
    build_fit,
    find_part_text,
    parse_number,
    report_text,
    standard_text,
)
from app.core.agent.tools import (
    ADD_FIT,
    ADD_PARAMETER,
    FIND_PART,
    OBJECTS_FIELD,
    READ_ANALYSIS,
    READ_DIGEST,
    READ_REPORT,
    READ_STANDARD,
    SET_PARAMETER,
    SET_PRINT_TARGET,
    STANDARD_KINDS,
    UNDO_TRANSACTION,
)
from app.core.backends import llm
from app.core.errors import (
    CANCEL,
    CHOOSE,
    REPAIR_AND_RETRY,
    AppError,
    ExternalToolError,
    InternalError,
    OperationCancelled,
    UserError,
    ValidationError,
)
from app.core.export.handover import GCODE_SUFFIXES as _CORE_GCODE_SUFFIXES
from app.core.export.handover import SliceOutcome, override_for, with_slot_override
from app.core.export.writer import (
    ExportFormat,
    adhesion_margin,
    plan_export,
    safe_name,
    write_assembly,
    write_plan,
)
from app.core.geom.measure import bounding_box_of, volume_of
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.pose import armature_to_text
from app.core.geom.sculpt import (
    BRUSH_TO_EDGE,
    SYMMETRY_BITS,
    apply_strokes,
    median_edge,
    stages,
    stroke_at,
    strokes_to_text,
)
from app.core.geom.section import SectionPlane, plane_through
from app.core.ingest.fetch import FetchedModel, check_url, fetch_model
from app.core.ingest.plan import MODEL_SUFFIXES as _CORE_MODEL_SUFFIXES
from app.core.knowledge import calibration, print_settings, profiles
from app.core.knowledge.parts.ops import op_name as part_op_name
from app.core.log import get_logger
from app.core.perceive import maps
from app.core.perceive.digest import digest
from app.core.perceive.maps import wall_thickness_map
from app.core.registry import (
    MENU_TWINS,
    REGISTRY,
    TWIN_TOGGLES,
    VARIANT_GROUPS,
    OperationSpec,
    PaletteEntry,
    catalogue_operations,
    caveat_line,
    folded_categories,
    group_for_variant,
    menu_tree,
    palette_entries,
    variant_members,
)
from app.core.scene import (
    EvaluationResult,
    OperationDraft,
    advises_on_bores,
    bore_advice,
    values_for,
    values_for_object,
)
from app.core.scene.cancel import CancelSignal
from app.core.scene.history import repair_is_available
from app.core.scene.project import clear_autosave, find_recovery
from app.core.sketch.planes import feature_plane, frame_for_plane, to_world
from app.core.sketch.profile import SketchCurve, curves_of
from app.core.slice import gcode
from app.core.slice.analysis import slice_body
from app.core.slice.estimate import support_material
from app.core.slice.estimate import total as estimate_total
from app.core.support import KIND_CRASH, KIND_IDEA, KIND_SURVEY
from app.core.tour import tour_for
from app.core.types import (
    Bone,
    Feature,
    Finding,
    MaterialSlot,
    ObjectId,
    Origin,
    Parameter,
    PlaneFrame,
    QualityPreset,
    SliceResult,
    SolvedSketch,
    SourceOrigin,
    Stroke,
    Vec3,
)
from app.i18n import _, tr
from app.ui import first_run
from app.ui.ai_disclosure import (
    DisclosureResult,
    ensure_ai_disclosure,
    target_for_backend,
)
from app.ui.analysis_bar import AnalysisBar, LayerBar
from app.ui.catalog import PartCatalog
from app.ui.chat import ChatPanel
from app.ui.command_palette import CommandPalette
from app.ui.dialogs import (
    AboutDialog,
    ActivationDialog,
    AskDialog,
    CalibrationDialog,
    DonationDialog,
    KeyDialog,
    ParameterDialog,
    StepValuesDialog,
    confirm_discard,
    confirm_unsaved,
    damaged_line,
    licence_lock_line,
    open_website,
    show_details,
    show_error,
)
from app.ui.explode_bar import ExplodeBar
from app.ui.facts import PrintFacts
from app.ui.filament_picker import FilamentPanel
from app.ui.generate_dialog import IMAGE_SUFFIXES, GenerateDialog, image_filter
from app.ui.header import HeaderBar, header_stylesheet
from app.ui.icons import icon, icon_name_for
from app.ui.install_dialog import InstallDialog
from app.ui.labels import (
    MENU_GROUPS,
    LengthSpin,
    circle_measure,
    demo_line,
    display_unit,
    feature_label,
    feature_requirement,
    kind_requirement,
    length,
    localised,
    set_circle_measure,
    spoiled_the_exact_body,
)
from app.ui.labels import area as area_label
from app.ui.labels import set_display_unit as set_length_unit
from app.ui.leash import Worker, WorkerLeash, weak_slot
from app.ui.loading import BAR_AFTER_MS, DELAY_MS, LoadingVeil, remaining_time
from app.ui.manual_window import ManualWindow
from app.ui.motion import switch
from app.ui.op_dialog import OperationDialog, SketchUseDialog
from app.ui.overlay import CARD_PADDING, OverlayHost, card_stylesheet
from app.ui.palette import text_colour
from app.ui.panels import (
    SEVERITY_MARKER,
    FeaturePanel,
    HistoryPanel,
    MeasurementLabel,
    ObjectTree,
    ParameterPanel,
    ReportPanel,
    collapsible,
    describe_selection,
    open_section,
)
from app.ui.pose_bar import PoseBar
from app.ui.print_disclosure import ensure_print_disclosure
from app.ui.print_settings_dialog import (
    FilamentOverrideDialog,
    PrintSettingsDialog,
    remembered_setup,
    settings_for_export,
)
from app.ui.recipe_dialog import RecipeDialog
from app.ui.remote_server import RemoteServer, WindowBridge
from app.ui.sculpt_bar import SculptBar
from app.ui.section_bar import MeasureBar, SectionBar
from app.ui.session import AskRequest, Session
from app.ui.settings import UiSettings, save_settings
from app.ui.settings_dialog import NAVIGATION, THEMES, SettingsDialog
from app.ui.shortcut_schemes import install_navigation_keys, shortcut_for
from app.ui.sketch_editor import (
    SketchField,
    SketchPanel,
    Surroundings,
    grid_step_for,
    plane_where,
)
from app.ui.spacemouse import SpaceMouseController
from app.ui.split_bar import POINTS_NEEDED, SplitBar
from app.ui.start_screen import StartScreen, accepted_path, accepted_url
from app.ui.style import NORMAL, TIGHT, divider, make_primary, menu_heading, set_level
from app.ui.support_dialog import SupportDialog, window_shot
from app.ui.survey import SurveyNotice, UsageClock
from app.ui.theme import apply_theme
from app.ui.tool_strip import ToolStrip, strip_title
from app.ui.tour import TourPanel
from app.ui.transform_bar import ROLES as TRANSFORM_ROLES
from app.ui.transform_bar import TransformBar
from app.ui.update_dialog import UpdateDialog
from app.ui.variants_dialog import VariantsDialog
from app.ui.viewport import DisplayMode, Projection, Viewport

_log = get_logger(__name__)

AUTOSAVE_INTERVAL_MS = 120_000

#: Zwei Sätze, die diese Datei je viermal sagte.
#:
#: **Mit ``_()`` und nicht mit ``tr()``, und das ist hier keine Feinheit.**
#: ``tr()`` übersetzt sofort und gibt eine nackte Zeichenkette zurück — auf
#: Modulebene aufgerufen friert es die Sprache ein, die beim *Import* galt, und
#: ein späteres ``set_language`` erreicht die Konstante nie mehr. Gemessen am
#: 24.08.2026: nach dem Wechsel auf Englisch liefert ``str(_(…))``
#: „Please select an object first.", ein zur Importzeit ausgewertetes ``tr(…)``
#: dagegen weiter den deutschen Satz. Deshalb steht hier der Marker, und die
#: Verwendungsstelle löst ihn mit ``str()`` auf.
#:
#: Der Einsammler findet sie trotzdem: ``i18n.extract`` liest das erste
#: Argument von ``_()`` und ``tr()``, wenn es eine feste Zeichenkette ist — und
#: das ist es genau hier. Wer den Satz stattdessen als nackte Zeichenkette
#: ablegte und an der Verwendungsstelle ``tr(_NEEDS_SELECTION)`` schriebe,
#: hätte ihn aus dem Katalog geworfen: Dort steht dann eine Variable, und die
#: sieht der Einsammler nicht.
_NEEDS_SELECTION = _("Bitte zuerst ein Objekt auswählen.")
_NEEDS_BODY = _("Dafür braucht es einen Körper in der Szene.")

#: Wie lange der Rahmen steht, mit dem ein Tourschritt auf seinen Bereich
#: zeigt. Lang genug, um den Blick dorthin zu ziehen, kurz genug, um nicht als
#: Zustand gelesen zu werden.
FLASH_MS = 1200


def _flash_colour(widget: QWidget) -> str:
    """Die Rahmenfarbe, mit der ein Bereich kurz aufleuchtet.

    Über :func:`text_colour` und nicht über ``ROLES['select']`` direkt: Das
    Bernstein der Auswahl ist für die dunkle Fläche gewählt, auf der die
    Anwendung startet, und dort trägt es 5,54. Auf der hellen bringt es 1,70 —
    WCAG 1.4.11 verlangt für eine Umrandung 3,0, also weniger als die Hälfte
    des Nötigen. Ein Rahmen, den man nicht sieht, zeigt auf nichts.

    Gefragt wird die Fläche des Widgets selbst und nicht das eingestellte
    Thema: Der Aufrufer kennt die Fläche, auf die er zeichnet, immer.
    """
    return text_colour("select", widget.palette().window().color().name())


def _tick(group: QActionGroup, value: str) -> None:
    """Setzt das Häkchen auf den Eintrag, der jetzt gilt.

    Qt tut das von selbst, wenn jemand im Menü klickt — nicht aber, wenn die
    Einstellung von woanders kommt, etwa aus dem Einstellungsdialog. Dann stand
    der Haken auf dem alten Eintrag und behauptete etwas Falsches.
    """
    for action in group.actions():
        action.setChecked(action.data() == value)


#: Der eigene Container. Sein Name ist der der Anwendung und wird nicht
#: übersetzt.
PROJECT_FILTER = f"{APP_NAME} ({'*' + PROJECT_SUFFIX})"

#: Was die Eingangsstufe liest, und was ein Slicer schreibt. Die Endungen
#: stehen für sich; die Beschriftung davor ist ein Text wie jeder andere und
#: geht durch ``tr()`` (Regel 20).
MODEL_SUFFIXES: Final = _CORE_MODEL_SUFFIXES
#: Die Endungen kommen aus dem Kern: Was der Dialog zum Öffnen anbietet,
#: muss dieselbe Menge sein, die ``handover`` im Ausgabeordner sucht.
#: Standen sie doppelt, liefen sie auseinander (27.08.2026).
GCODE_SUFFIXES: Final = _CORE_GCODE_SUFFIXES

#: Wie viel mehr Platz die Werkzeugleiste braucht, bevor sie ihre Wörter
#: zurückbekommt (D6). Zwei Schwellen statt einer: Wäre es dieselbe, flackerte
#: die Leiste, sobald jemand das Fenster genau an der Grenze zieht — der
#: Bereich, in dem beide Antworten stimmen, ist der, in dem beide falsch
#: aussehen.
TOOLBAR_HYSTERESIS: Final = 80

#: Wie lange nach dem letzten Pinselzug gewartet wird, bevor die Wandstärke
#: nachgerechnet wird (Entscheidung L). Bei jedem Zug zu rechnen hieße, den
#: Pinsel zu verzögern, damit eine Zahl aktuell ist, die sich beim nächsten Zug
#: wieder ändert.
#: Wie weit das Raster der Zeichenebene reicht, in Millimetern von der Mitte.
#:
#: Der halbe Bauraum eines großen Druckers, aufgerundet: Wer auf einer Ebene
#: zeichnet, tut es innerhalb dessen, was gedruckt werden kann. Ein Raster,
#: das darüber hinausreicht, kostet Linien und sagt nichts — und eines, das
#: früher endet, sähe aus wie eine Grenze, die es nicht gibt.
SKETCH_GRID_REACH: Final = 150.0

SCULPT_CHECK_MS: Final = 400

#: Wie fein die mitlaufende Wandprüfung rastert, als Anteil der
#: Mindestwandstärke. Ein Raster, das gröber ist als die gesuchte Wand, findet
#: sie nicht: bei 2 mm Raster und 1,2 mm Mindestwand meldete die Karte null zu
#: dünne Stellen an einer Schale mit 0,8 mm Wand.
WALL_GRID_SHARE: Final = 0.8

#: Operationen, die einen Deckel bauen und deshalb über ihren Ablauf laufen —
#: er trägt die Passung ein, die die Operation allein nicht eintragen darf
#: (§14, §15.1).
LID_OPS: Final = frozenset({"create_lid", "screw_lid"})


def _filter_for(label: str, suffixes: tuple[str, ...]) -> str:
    """Ein Dateifilter in der Sprache des Nutzers.

    Als Funktion und nicht als Konstante: ``tr()`` löst sofort auf, und eine
    Konstante auf Modulebene bliebe in der Sprache stehen, die beim Import
    galt — hier hieß es „Modelle" auch in der englischen Oberfläche.
    """
    return f"{label} ({' '.join('*' + suffix for suffix in suffixes)})"


@contextmanager
def waiting() -> Iterator[None]:
    """Der Wartezeiger für die Rechnung, die bis zu zwei Sekunden dauert
    (§2.8).

    Die Stufe darunter zeigt nichts, die darüber gehört in einen Arbeiter.
    Dazwischen liegt genau das hier: eine Datei von der Platte lesen, einen
    Dialog aufbauen, den Slicer suchen. Als Kontextmanager, weil das
    Zurücksetzen sonst am ersten Fehlerausgang hängen bleibt — und ein
    Wartezeiger, der stehen bleibt, sieht aus wie ein hängendes Programm.
    """
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


def model_filter() -> str:
    return _filter_for(tr("Modelle"), MODEL_SUFFIXES)


def gcode_filter() -> str:
    return _filter_for(tr("G-Code"), GCODE_SUFFIXES)


#: Welche Merkmalsoperation zu welcher Körperoperation gehört.
#:
#: Roberts Regel vom 03.09.2026: „wenn man die Wulst wählt verschiebt man die
#: Wulst, immer das Ausgewählte." Die Bewegen-Leiste nennt weiterhin ihre
#: Körperoperation; ist ein Merkmal gewählt, für das es die Merkmalsoperation
#: gibt, läuft diese stattdessen (:meth:`MainWindow.feature_draft`).
#:
#: **Geprüft wird gegen das Register, nicht gegen diese Liste.** Was hier
#: steht und dort fehlt, fällt still auf den Körper zurück — die übrigen
#: Handlungen entstehen gerade, und ein Name, der zu früh greift, wäre eine
#: Sackgasse statt eines Rückfalls.
FEATURE_TWINS: Final[dict[str, str]] = {
    "translate_object": "move_feature",
    "rotate_object": "rotate_feature",
    "scale_object": "resize_feature",
    "delete_object": "remove_feature",
}


class _FeatureDock(QDockWidget):
    """Das Merkmalsfenster — merkt sich, wenn der Kunde es **selbst** zumacht.

    Es startet zu und geht beim ersten gewählten Merkmal von selbst auf. Wer
    es danach schließt, hat entschieden; von da an öffnet nur noch der
    Schalter unter *Ansicht*. Ein Fenster, das nach jedem Klick wieder
    aufspringt, ist keine Hilfe, sondern dieselbe Frage noch einmal.

    Warum das nicht über ``visibilityChanged`` läuft: Qt beantwortet
    ``isVisible()`` mit „nein", solange das Hauptfenster nicht angezeigt ist,
    und feuert das Signal dann gar nicht. Im Testlauf ist nie etwas angezeigt.
    ``closeEvent`` und ``hideEvent`` kommen in beiden Lagen an — das eine beim
    Kreuz, das andere beim Schalter.
    """

    #: Es ist zugegangen. Wer eine Vorschau hat, die zu diesem Fenster gehört,
    #: räumt sie hier ab — das Fenster, in dem man sie zurücknehmen könnte, ist
    #: gerade verschwunden.
    closed = Signal()

    # Als Klassenwerte, nicht erst im Rumpf: ``setVisible`` ist überschrieben
    # und kann von Qt schon aus ``super().__init__`` heraus gerufen werden —
    # dann stünden die Felder noch nicht.
    dismissed = False
    _watching = False

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)

    def start_watching(self) -> None:
        """Ab hier zählt ein Zumachen als Entscheidung — nicht das erste Verbergen."""
        self._watching = True

    def reveal(self) -> None:
        """Zeigt das Fenster, es sei denn, der Kunde hat es zugemacht.

        Gefragt wird ``isHidden()`` und nicht ``isVisible()``: Das eine ist der
        gesetzte Zustand, das andere hängt am Hauptfenster.
        """
        if self.dismissed or not self.isHidden():
            return
        self.show()

    def setVisible(self, visible: bool) -> None:  # noqa: N802 - Qt name
        """Der Trichter, durch den jedes Auf und Zu läuft.

        Das Kreuz, der Schalter unter *Ansicht* und ``reveal()`` enden alle
        hier — Ereignisse dagegen nicht: ``showEvent`` und ``hideEvent``
        bleiben aus, solange das Hauptfenster nicht angezeigt ist, und
        ``visibilityChanged`` ebenso (gemessen am 03.09.2026, beides).

        Zumachen heißt „nicht jetzt", Aufmachen heißt das Gegenteil. Deshalb
        setzt dieselbe Zeile den Merker in beide Richtungen.
        """
        if self._watching:
            self.dismissed = not visible
        super().setVisible(visible)
        if self._watching and not visible:
            self.closed.emit()


class _MapWorker(Worker):
    """Eine Analysekarte, abseits des Oberflächen-Threads (§18.9).

    Sekunden an einem großen Körper — lang genug, dass ein Fenster, das sie in
    der Ereignisschleife rechnet, aufhört zu zeichnen, und das liest sich wie
    ein Absturz statt wie Arbeit.
    """

    done = Signal(object)
    tooLarge = Signal()

    def __init__(self, kind: Any, entry: Any, profile: Any, scene: Any) -> None:
        super().__init__()
        self._kind = kind
        self._entry = entry
        self._profile = profile
        self._scene = scene
        self.cancelled = CancelSignal()
        """Der Schalter zum Kartenwechsel (§18.4): Wer die zweite Karte wählt,
        wartete bis hierher erst die erste ab — 3,4 s bei 51 000 Dreiecken, und
        das Fenster meldete die ganze Zeit „wird berechnet …" für die falsche."""

    def cancel(self) -> None:
        self.cancelled.cancel()

    def work(self) -> None:
        try:
            self.done.emit(
                maps.build(
                    self._kind,
                    self._entry,
                    profile=self._profile,
                    scene=self._scene,
                    cancelled=self.cancelled,
                )
            )
        except maps.MapTooLarge:
            # §31: eine Karte, die Minuten bräuchte, sagt Nein, statt einzufrieren.
            self.tooLarge.emit()
        except OperationCancelled:
            # Kein Fehler und nie als einer gezeigt (§15.6): Eine andere Karte
            # ist schon unterwegs, und ihr Ergebnis ist das, auf das jemand
            # wartet.
            return


class _UpdateWorker(Worker):
    """Die Update-Anfrage, abseits des Oberflächen-Threads (§37.2).

    Sie lief beim Start im Hauptthread — ihr Docstring versprach „niemand
    wartet auf sie", das Fenster wartete aber bis zu vier Sekunden auf einen
    Server, der nicht antwortet. Jetzt wartet wirklich niemand.
    """

    done = Signal(object)

    def work(self) -> None:
        self.done.emit(updates.check())


class _OllamaSizeWorker(Worker):
    """Die Modellgrößen-Frage an Ollama (§27), abseits des Oberflächen-Threads.

    Sie läuft nur, wenn der Chat über das lokale Modell aufwacht. Das Ergebnis
    ist ein Satz oder nichts — und ein Server, der nicht antwortet, ist kein
    Fehler, sondern Schweigen.
    """

    done = Signal(object)

    def __init__(self, model: str) -> None:
        super().__init__()
        self._model = model

    def work(self) -> None:
        self.done.emit(llm.ollama_size_warning(self._model))


class _DownloadWorker(Worker):
    """Eine Modelldatei aus dem Netz holen, abseits des Oberflächen-Threads
    (§2.8).

    Eine Leitung kann langsam sein, und ein Fenster, das währenddessen nicht
    reagiert, sieht aus wie ein abgestürztes. Der Fortschritt kommt aus dem
    Lesen selbst, also aus dem Kern — die Statusleiste zeigt ihn wie bei jeder
    anderen langen Rechnung.
    """

    done = Signal(object)
    failed = Signal(object)
    stopped = Signal()
    step = Signal(float, str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url
        self.cancel = CancelSignal()
        """§2.8: über zwei Sekunden gehört zum Fortschritt ein Abbrechen —
        ein 300-MB-Modell an langsamer Leitung war sonst nur über das
        Beenden der Anwendung zu stoppen. Der Kern liest blockweise und
        meldet je Block Fortschritt; der Rückruf ist damit der Punkt, an dem
        sich sauber aufhören lässt, ohne dass der Kern einen eigenen
        Abbruchparameter braucht."""

    def work(self) -> None:
        try:
            self.done.emit(fetch_model(self._url, progress=self._report))
        except OperationCancelled:
            self.stopped.emit()
        except AppError as error:
            self.failed.emit(error)

    def _report(self, share: float, text: str) -> None:
        if self.cancel.is_cancelled:
            raise OperationCancelled(tr("Der Download wurde abgebrochen."))
        self.step.emit(share, text)


@dataclass(frozen=True, slots=True)
class _WriteFailure:
    """Was nach einem gescheiterten Schreiben möglich ist (§2.7).

    Zwei Wege, und beide braucht der Fall, der wirklich vorkommt: Die Datei
    liegt in einem anderen Programm offen — dann hilft ein zweiter Anlauf auf
    dieselbe Datei, sobald sie frei ist. Oder das Laufwerk ist voll, das Recht
    fehlt, der Pfad ist weg — dann hilft ein anderer Ort.

    Als Bündel und nicht als zwei Felder je Schreibweg: Export und Speichern
    scheitern am selben Betriebssystem, und der Kunde bekommt in beiden Fällen
    dieselben zwei Antworten. Was sie *tun*, weiß nur die Stelle, an der es
    schiefging — deshalb stehen hier Aufrufe und keine Pfade.
    """

    again: Callable[[], None]
    elsewhere: Callable[[], None]


@dataclass(frozen=True, slots=True)
class _ProgressState:
    """Eine Aufgabe, die sich den gemeinsamen Fortschrittsbereich teilt."""

    active: bool
    text: str
    minimum: int
    maximum: int
    value: int
    accessible_name: str
    accessible_description: str
    cancel_description: str
    cancellable: bool
    cancel_enabled: bool
    immediate: bool


_PROGRESS_PRIORITY: Final = (
    "split",
    "download",
    "export",
    "part_file",
    "agent",
    "evaluation",
)


class _ExportWorker(Worker):
    """Der Export, abseits des Oberflächen-Threads (§2.8, §29).

    Er rechnete und schrieb komplett in der Ereignisschleife: die Prüfung vor
    dem Export, der Aufbau der Baugruppe samt Slicer-Suche, die
    Anordnungsprüfung und das Schreiben selbst. Bei ein paar großen Körpern
    sind das mehr als zwei Sekunden mit stehendem Fenster — und §2.8 verlangt
    darüber ein Fenster, das bedienbar bleibt.

    **Ohne Abbrechen, und das ist Absicht.** Ein halb geschriebener Export ist
    eine halbe Datei; der Schreiber im Kern kennt keinen Abbruchpunkt, an dem
    er sauber aufhören könnte, und einen einzubauen hieße, ihn mitten in einer
    Datei anhalten zu dürfen. Was §2.8 hier trägt, ist die Bedienbarkeit: der
    Balken läuft, das Fenster reagiert, und der Menüeintrag ist gesperrt,
    damit kein zweiter Lauf auf denselben Ordner schreibt.

    Die Befunde der Prüfung kommen mit dem Ergebnis zurück, nicht davor. §29
    sagt „vor dem Schreiben", und genau das ist hier nicht mehr zu haben:
    **die Prüfung ist der lange Teil**, sie im Hauptthread zu lassen wäre die
    Blockade, gegen die dieser Arbeiter geschrieben ist. Die Baugruppe macht
    es seit je so — sie prüft und schreibt in einem Zug —, und der Abstand
    zwischen beidem ist jetzt derselbe Wimpernschlag.
    """

    done = Signal(object, object)
    failed = Signal(object)

    def __init__(
        self,
        objects: list[Any],
        target: Path,
        export_format: ExportFormat,
        *,
        profile: Any,
        sources: Any,
        settings: Any,
        ui_settings: Any,
        material: str,
    ) -> None:
        super().__init__()
        self._objects = objects
        self._target = target
        self._format = export_format
        self._profile = profile
        self._sources = sources
        self._settings = settings
        self._ui_settings = ui_settings
        self._material = material

    def work(self) -> None:
        try:
            if self._format == "3mf":
                written, findings = self._assembly()
            else:
                written, findings = self._files()
        except AppError as error:
            self.failed.emit(error)
            return
        self.done.emit(written, findings)

    def _assembly(self) -> tuple[list[Path], list[Finding]]:
        """Eine Baugruppe bleibt eine Datei: der Slicer bekommt einen
        Druckauftrag, keine Handvoll Teile (§20). Auch bei **einem** Körper —
        der lief über den Plan-Weg, und der kennt keine Einstellungen.

        Die Slicer-Suche in ``remembered_setup`` läuft hier mit: sie kostet
        eine knappe halbe Sekunde und hatte im Hauptthread einen Wartezeiger
        über sich. Hier braucht sie keinen.
        """
        written_path, findings = write_assembly(
            self._objects,
            self._target.parent,
            project_name=self._target.stem,
            profile=self._profile,
            sources=self._sources,
            settings=self._settings,
            setup=remembered_setup(self._ui_settings, self._material, self._profile.printer.id),
        )
        return [written_path], list(findings)

    def _files(self) -> tuple[list[Path], list[Finding]]:
        """Ein fester Name für einen Körper; bei mehreren zählt das
        Namensschema aus §29, damit auf der Platte lesbar bleibt, welches Teil
        welches ist. Geschweifte Klammern im Namen sind Zeichen, keine
        Platzhalter — ``format`` sähe das anders.
        """
        fixed = self._target.stem.replace("{", "{{").replace("}", "}}")
        plan = plan_export(
            self._objects,
            project_name=self._target.stem,
            profile=self._profile,
            export_format=self._format,
            scheme=fixed if len(self._objects) == 1 else None,
            sources=self._sources,
        )
        return write_plan(plan, self._target.parent, self._format), list(plan.findings)


class _PartImportWorker(Worker):
    """Eine Bausteindatei prüfen und atomar installieren (§2.8, §24.5).

    Die Prüfung umfasst nicht nur JSON, sondern auch Quellen, Ressourcen,
    Operationen und einen Geometrie-Probelauf. Das kann länger als ein
    Lidschlag dauern und gehört deshalb nicht in den Qt-Hauptthread. Ein
    Abbruch wird nicht angeboten: Datei und Register werden im Kern als eine
    Transaktion veröffentlicht und dürfen nicht auf halbem Weg stehen bleiben.
    """

    done = Signal(object)
    failed = Signal(object, object)

    def __init__(self, source: bytes | Path, name: str | None = None) -> None:
        super().__init__()
        self._source = source
        self._name = name

    def work(self) -> None:
        from app.core.knowledge.parts.part_file import PartFileIO

        if isinstance(self._source, Path):
            try:
                payload = self._source.read_bytes()
            except OSError:
                self.failed.emit(
                    ValidationError(
                        field="title",
                        detail=tr(
                            "Die gewählte Bausteindatei ließ sich nicht öffnen. "
                            "Wählen Sie eine andere Datei oder prüfen Sie deren Zugriffsrechte."
                        ),
                        constraint="part_file_unreadable",
                        suggestions=(CHOOSE, CANCEL),
                    ),
                    None,
                )
                return
        else:
            payload = self._source
        try:
            installed = PartFileIO().install_file(payload, name=self._name)
        except AppError as error:
            self.failed.emit(error, payload)
            return
        self.done.emit(installed)


class _PartExportWorker(Worker):
    """Eine Bausteindatei prüfen und atomar an den gewählten Ort schreiben.

    Wie beim Import ist die vollständige Dateiprüfung der teure Teil. Das
    Fenster bleibt währenddessen bedienbar; ein Abbruch fehlt absichtlich,
    weil der atomare Schreiber ohne sichtbare Zwischenfassung fertig wird.
    """

    done = Signal(object)
    failed = Signal(object)

    def __init__(self, data: Mapping[str, Any], target: Path) -> None:
        super().__init__()
        self._data = dict(data)
        self._target = target

    def work(self) -> None:
        from app.core.knowledge.parts.part_file import PartFileIO
        from app.core.knowledge.parts.recipe import from_data

        try:
            recipe = from_data(dict(self._data))
            PartFileIO().export_to_file(recipe, self._target)
        except AppError as error:
            self.failed.emit(error)
            return
        except (TypeError, ValueError):
            self.failed.emit(
                ValidationError(
                    field="title",
                    detail=tr(
                        "Die Datei dieses Bausteins ließ sich nicht lesen. "
                        "Speichern Sie ihn neu, dann steht sie wieder."
                    ),
                    constraint="part_file_unavailable",
                    suggestions=(CANCEL,),
                )
            )
            return
        self.done.emit(self._target)


class _PartRemoveWorker(Worker):
    """Einen lokalen Bibliothekseintrag samt exaktem Rückweg entfernen (§2.8).

    Ein Abbruch wird nicht angeboten, aus demselben Grund wie beim Einlesen
    (:class:`_PartImportWorker`): Datei und Register werden im Kern als eine
    Transaktion geändert und dürfen nicht auf halbem Weg stehen bleiben. Der
    Rückweg ist der Bytestand, den das Entfernen zurückgibt — nicht ein
    Anhalten mittendrin.
    """

    done = Signal(object)
    failed = Signal(object)

    def __init__(self, name: str, expected_sha256: str | None = None) -> None:
        super().__init__()
        self._name = name
        self._expected_sha256 = expected_sha256

    def work(self) -> None:
        from app.core.knowledge.parts.part_file import PartFileIO

        try:
            removed = PartFileIO().remove_from_library(
                self._name, expected_sha256=self._expected_sha256
            )
        except AppError as error:
            self.failed.emit(error)
            return
        self.done.emit(removed)


class _PartRestoreWorker(Worker):
    """Den bytegenauen Rückweg einer Bibliotheksentfernung ausführen (§2.8).

    Auch hier kein Abbruch: Das Zurücklegen ist die zweite Hälfte einer
    Handlung, die der Kunde schon zurückgenommen hat. Wer sie mittendrin
    anhielte, ließe die Bibliothek in einem Zustand zurück, den niemand
    gewollt hat — und dafür gibt es keinen zweiten Rückweg.
    """

    done = Signal(object)
    failed = Signal(object)

    def __init__(self, token: Any) -> None:
        super().__init__()
        self._token = token

    def work(self) -> None:
        from app.core.knowledge.parts.part_file import PartFileIO

        try:
            restored = PartFileIO().restore_to_library(self._token)
        except AppError as error:
            self.failed.emit(error)
            return
        self.done.emit(restored)


class _SliceWorker(Worker):
    """Eine Schichtanalyse, abseits des Oberflächen-Threads (§2.8, §22).

    Dieselbe Begründung wie bei der Analysekarte, nur später bemerkt: an einem
    großen Körper dauert sie Sekunden, und ein Wartezeiger macht daraus keine
    kürzere Blockade, nur eine angekündigte.
    """

    done = Signal(object)

    def __init__(self, entry: Any, layer_height: float) -> None:
        super().__init__()
        self._entry = entry
        self._layer_height = layer_height

    def work(self) -> None:
        self.done.emit(slice_body(as_mesh_data(self._entry.mesh), self._layer_height))


def inputs_for(
    spec: OperationSpec, objects: list[ObjectId], selected: Sequence[ObjectId]
) -> tuple[ObjectId, ...]:
    """Auf welche Objekte eine Operation angewandt wird (§10, §25).

    Eine eigene Funktion, keine zwei Zeilen im Menü-Handler: die Regel ist
    dieselbe für Kommandozeile und Agent, und eine Operation, die auf der
    ganzen Szene arbeitet und nichts bekommt, läuft auf nichts und sieht kaputt
    aus.

    ``selected`` ist die Auswahl in Klickreihenfolge. Eine Operation nimmt so
    viele davon, wie sie deklariert — vorher nahm sie immer genau eines, und
    damit war keine der drei Booleschen über das Menü ausführbar: sie
    erwarten zwei und bekamen eines.
    """
    if spec.takes_whole_scene:
        return tuple(objects)
    return tuple(selected[: spec.consumes]) if spec.consumes else ()


def _format_of(target: Path, chosen_filter: str) -> ExportFormat:
    """Das Exportformat aus dem Dateinamen, sonst aus dem gewählten Filter.

    Wer ``teil.3mf`` tippt, meint 3MF, auch wenn der Filter noch auf STL
    steht — die Endung ist die ausdrücklichere der beiden Angaben.
    """
    from app.core.export.writer import FORMAT_SUFFIX

    suffix = target.suffix.lower()
    for name, ending in FORMAT_SUFFIX.items():
        if suffix == ending:
            return name
    filtered = _format_from_filter(chosen_filter)
    return filtered if filtered is not None else "stl"


def _format_from_filter(chosen_filter: str) -> ExportFormat | None:
    """Das Format eines Dateidialogfilters, falls er eines benennt."""
    from app.core.export.writer import FORMAT_SUFFIX

    for name, ending in FORMAT_SUFFIX.items():
        if f"*{ending}" in chosen_filter:
            return name
    return None


def _export_target(
    target: Path, chosen_filter: str, suggested_name: str
) -> tuple[Path, ExportFormat]:
    """Dateiname und Format aus den zwei Angaben des Dateidialogs abstimmen.

    Der vorausgefüllte Name endet auf 3MF. Wechselt jemand nur den Filter auf
    STL, ist diese Auswahl ausdrücklich und die noch unangetastete Vorgabe
    darf sie nicht wieder überschreiben. Eine selbst getippte, bekannte
    Endung bleibt dagegen die genauere Angabe. Fehlt eine bekannte Endung,
    wird die des Filters angehängt, damit Dateiinhalt und Name zusammenpassen.
    """
    from app.core.export.writer import FORMAT_SUFFIX

    known = next(
        (name for name, ending in FORMAT_SUFFIX.items() if target.suffix.lower() == ending),
        None,
    )
    filtered = _format_from_filter(chosen_filter) or known or "stl"
    untouched_suggestion = target.name.casefold() == suggested_name.casefold()
    if untouched_suggestion:
        return target.with_suffix(FORMAT_SUFFIX[filtered]), filtered
    if known is not None:
        return target, known
    return target.with_name(target.name + FORMAT_SUFFIX[filtered]), filtered


def _as_project_path(name: str) -> Path:
    """Der getippte Name bekommt die Projektendung, wenn er keine trägt.

    ``save_project`` schrieb jede Endung klaglos, und ``open_path`` verzweigt
    strikt über sie: Eine als ``halter.stl`` gespeicherte Projektdatei wurde
    beim Öffnen als Fremdmodell gelesen — „Dieses Dateiformat kann nicht
    gelesen werden", über der eigenen Datei (Gesamtreview A2). Angehängt und
    nicht ersetzt: Wer „Halter 2.5" tippt, meint keine Endung ``.5``.
    """
    path = Path(name)
    if path.suffix.lower() == PROJECT_SUFFIX:
        return path
    return path.with_name(path.name + PROJECT_SUFFIX)


def _has_sketch_param(spec: OperationSpec) -> bool:
    """Ob diese Operation eine gezeichnete Skizze verbraucht (§30.1)."""
    return any(entry.kind == "sketch" for entry in spec.params.spec())


def _has_armature_param(spec: OperationSpec) -> bool:
    """Ob diese Operation ein gesetztes Skelett verbraucht (§25).

    Vor dem Strichfeld geprüft: ``pose_armature`` hat beides nicht, aber die
    Reihenfolge der Fälle ist die Reihenfolge, in der jemand sie liest.
    """
    return any(entry.kind == "armature" for entry in spec.params.spec())


def _has_stroke_param(spec: OperationSpec) -> bool:
    """Ob diese Operation gemalte Züge verbraucht (§25, Konzept P16).

    Derselbe Gedanke wie beim Skizzenfeld: Der Menüeintrag führt dorthin, wo
    der Wert entsteht, und nicht in einen Dialog mit einem Textfeld voller
    Zahlen, die niemand tippt.
    """
    return any(entry.kind == "strokes" for entry in spec.params.spec())


def _sketch_param(op_name: str) -> str:
    """Wie der Skizzenparameter dieser Operation heißt (§30.1).

    Gefragt statt geraten: der Name steht im Schema, und eine zweite Liste
    daneben wäre eine zweite Wahrheit. Operationen ohne Skizzenfeld kommen
    hier nie an — der Modus wird nur für die angeboten, die eines haben.
    """
    for entry in REGISTRY.get(op_name).params.spec():
        if entry.kind == "sketch":
            return entry.name
    raise InternalError(
        detail=f"{op_name!r} has no sketch parameter",
        values={"op": op_name},
    )


#: Die Operation, in die der Ziehgriff der Querschau mündet (§30.1).
#:
#: Er zieht eine **Höhe** aus einem Umriss, und das ist genau das, was
#: ``sketch_extrude`` tut. Dieselbe Vorwahl, die auch der Dialog bei „Fertig"
#: trifft (``op_dialog.DEFAULT_SKETCH_USE``) — der Griff ist die kurze Hand
#: für den häufigsten der fünf Wege, nicht ein sechster.
PULL_OP = "sketch_extrude"

#: Wie der Höhenparameter dieser Operation heißt.
PULL_FIELD = "height"

#: Nach innen ziehen schneidet eine Tasche in den gewählten exakten Körper.
POCKET_OP = "sketch_pocket"
POCKET_FIELD = "depth"


def operation_limits(op_name: str, field: str) -> tuple[float, float]:
    """Unter- und Obergrenze eines gezogenen Maßes — **aus dem Schema**.

    Gefragt statt abgeschrieben, aus demselben Grund wie bei
    :func:`_sketch_param`: Eine zweite Zahl in der Ansicht fiele erst auf, wenn
    der Dialog einen Wert ablehnt, den der Griff gerade gezeigt hat. Fehlt eine
    Grenze im Schema, kommt null zurück — die Ansicht klemmt dann nicht, und
    das ist richtiger als eine erfundene Grenze.
    """
    for entry in REGISTRY.get(op_name).params.spec():
        if entry.name == field:
            return (float(entry.minimum or 0.0), float(entry.maximum or 0.0))
    raise InternalError(
        detail=f"{op_name!r} has no {field!r} parameter",
        values={"op": op_name},
    )


def pull_limits() -> tuple[float, float]:
    """Grenzen der Höhe für den Zug nach außen."""
    return operation_limits(PULL_OP, PULL_FIELD)


def pocket_limits() -> tuple[float, float]:
    """Grenzen der Tiefe für den Zug nach innen."""
    return operation_limits(POCKET_OP, POCKET_FIELD)


#: Was im Herkunftsvermerk einer ferngesteuerten Transaktion als Modell
#: steht. „user" und „agent" sind die einzigen Urheber, die das Format
#: kennt (§26.4); ein dritter kostete eine Migration, und für die Frage
#: „habe ich das getan?" reicht dieser Vermerk.
REMOTE_ORIGIN = "mcp"

#: Wie lange ein Fernaufruf auf die Auswertung wartet. Länger als im
#: Fenster: dort sieht jemand den Fortschritt, am anderen Ende der Leitung
#: sieht niemand etwas und braucht das fertige Ergebnis.
REMOTE_WAIT_MS = 120_000


def _needs_objects(count: int) -> str:
    """Der Satz, der sagt, wie viele Körper fehlen — nicht nur, dass welche
    fehlen.

    „Wählen Sie zuerst ein Objekt" half bei einer Vereinigung nicht weiter:
    eines war ja gewählt. Sie braucht zwei, und das steht jetzt da.
    """
    if count <= 1:
        return tr("Wählen Sie zuerst ein Objekt im Objektbaum.")
    return tr("Diese Operation braucht zwei Objekte. Das zweite dazu mit Strg und Klick.")


def _works_on(names: Sequence[str], chosen: int, takes: int) -> str:
    """Woran die Operation arbeitet, wenn mehr gewählt ist als sie nimmt.

    Eine Operation nimmt so viele Körper, wie sie deklariert, und zwar in
    Klickreihenfolge (:func:`inputs_for`). Bei zwei gewählten Würfeln und
    *Bohrung setzen* bekam einer ein Loch und der andere nicht — im Dialog
    stand kein Wort dazu. Das ist kein Raten (Regel 21): die Regel steht nur
    nirgends, wo sie jemand liest.

    **Und sie nennt die Körper beim Namen, auch wenn es mehrere sind.** Bei
    einem Eingang stand der Name hier seit je; bei zweien hieß es nur „die 2
    zuerst gewählten von 3", und damit musste der Kunde seine eigene
    Klickreihenfolge erinnern. Ausgerechnet dort zählt sie am meisten: Die
    Booleschen sagen zu, dass „das zuerst angeklickte mit seinem Namen und
    Material bleibt" — welches das ist, war die Frage, die der Satz offenließ.

    Leer, wo es nichts zu sagen gibt — und das ist der Normalfall.
    """
    if takes <= 0 or chosen <= takes or not any(names):
        return ""
    if takes == 1:
        return tr("Angewendet wird auf {name} — der zuerst gewählte von {count}.").format(
            name=names[0], count=chosen
        )
    return tr("Angewendet wird auf {names} — die {takes} zuerst gewählten von {count}.").format(
        names=tr(" und ").join(names[:takes]), takes=takes, count=chosen
    )


def _face_side(normal: Any) -> str:
    """Wo eine Fläche sitzt, in einem Wort.

    Nur nach der Richtung ihrer Normalen, ohne den Körper zu befragen. Das ist
    grob und reicht: gebraucht wird es, um zwei Flächen in einer Liste
    auseinanderzuhalten, nicht um sie zu vermessen.

    Die Normale kann nach innen zeigen — ``app.core.sketch.planes`` dreht sie
    erst bei der Auswertung um. „Oben" und „unten" können deshalb vertauscht
    sein; für das Wiedererkennen in einer Liste ändert das nichts, und die
    Richtung, in die extrudiert wird, entscheidet ohnehin der Kern.
    """
    x, y, z = (float(normal[0]), float(normal[1]), float(normal[2]))
    if abs(z) >= max(abs(x), abs(y)):
        return tr("oben") if z >= 0.0 else tr("unten")
    if abs(x) >= abs(y):
        return tr("rechts") if x >= 0.0 else tr("links")
    return tr("hinten") if y >= 0.0 else tr("vorn")


@dataclass(frozen=True, slots=True)
class _DiscardedSketch:
    """Eine verworfene Zeichnung — Editorzustand, kein Dokumentzustand.

    Regel 2 zieht die Grenze: Was der Editor sammelt, wird erst bei der
    Auswertung zu Geometrie. Eine Zeichnung, die nie „Fertig" gesehen hat,
    war nie im Dokument — sie gehört deshalb nicht in den Verlauf, sondern
    hierher, und ``action_undo`` behandelt sie wie einen Pinselzug: eigenes
    Rückgängig vor dem des Verlaufs.

    ``steps`` ist die Zahl der Verlaufsschritte im Augenblick des Verwerfens.
    Sie beantwortet die Frage, wie lange das Angebot gilt: Sobald der Kunde
    etwas anderes tut, meint sein Strg+Z das andere. Ohne diese Zahl holte er
    nach drei Operationen noch immer die alte Zeichnung zurück statt der
    Operation davor.
    """

    op_name: str
    text: str
    plane: str
    steps: int


class MainWindow(QMainWindow):
    """Fenster, Menüs und die Verdrahtung zwischen Sitzung und Panels."""

    projectOpened = Signal(Path)
    languageChanged = Signal()
    """Die Sprache wurde im Einstellungsdialog gewechselt. Übersetzen lässt
    sich ein stehendes Fenster nicht (gemessen: 170 von 170 Texten blieben) —
    ``app.rebuild_for_language`` baut es neu, und das gehört in den nächsten
    Ereignisdurchlauf, nicht in den Signalpfad eines eigenen Dialogs."""

    def __init__(self, session: Session, settings: UiSettings) -> None:
        super().__init__()
        self.session = session
        self.settings = settings
        self.setAcceptDrops(True)
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 820)
        self._map_cache: dict[tuple[str, str, int], Any] = {}
        self._finding_awaiting_map: Finding | None = None
        """Der angeklickte Befund, dessen Analysekarte noch gerechnet wird.

        **Der erste Klick auf eine Warnung fuhr sonst ins Leere.** Der Ort
        eines Kartenbefunds kommt aus ``_map_cache``, und der ist beim ersten
        Klick leer — die Karte rechnet gerade erst, und die Ansicht wartet
        ausdrücklich nicht darauf. Gemessen am 30.08.2026 über alle 58 Befunde
        der Beispielprojekte: **keiner** löste beim ersten Klick einen Flug
        aus. Hier steht, wofür ``_map_ready`` ihn nachholen soll.
        """
        self._map_worker: Any = None
        """Die Karte, die gerade gerechnet wird (§18.9). Eine neuere Anfrage ersetzt sie."""
        """Nur die letzte Karte wird gehalten: neu zu rechnen ist billig, sie zu
    halten teuer."""
        self._slice_cache: SliceResult | None = None
        self._slice_key: tuple[str, int] | None = None
        self._slice_worker: Any = None
        self._slice_pending: tuple[str, int] | None = None
        """Der Schlüssel, an dem der laufende Schnitt-Arbeiter rechnet — damit
        derselbe Körper nicht je Schieberschritt einen weiteren bekommt."""
        self._slice_waiters: list[Any] = []
        """Wer auf das laufende Ergebnis wartet. Ein Rückruf, der schon in der
        Reihe steht, wird nicht doppelt eingereiht."""
        self._update_worker: Any = None
        self._finished_update_worker: Any = None
        """Die ausgelaufene Abfrage, festgehalten bis zur nächsten — dieselbe
        Halteleine wie bei den Arbeitern der Sitzung."""
        """Die laufende Update-Anfrage (§37.2) — festgehalten wie jeder
        andere Arbeiter, damit sie das Fenster nicht überlebt."""
        self._ollama_size_worker: Any = None
        """Die Modellgrößen-Frage an Ollama (§27), aus demselben Grund."""
        self._download_worker: Any = None
        self._downloading = False
        """Ob gerade eine Datei geholt wird — als eigene Flagge, nicht über
        das Worker-Feld: ``done``/``failed`` kommen vor ``finished``, und das
        Feld hält den Arbeiter absichtlich länger (GC-Falle). Der Balken
        richtet sich nach dem Zustand, nicht nach der Lebensdauer."""
        """Ein Modell, das gerade aus dem Netz kommt (§16.3) — dieselbe
        Halteleine, derselbe Grund."""
        self._export_worker: Any = None
        self._exporting = False
        """Wie ``_downloading`` — der Export meldet sein Ende vor dem
        Auslaufen seines Threads."""
        self._export_attempt: tuple[Path, ExportFormat] | None = None
        """Wohin der laufende Export schreibt — für einen zweiten Anlauf."""
        self._part_file_worker: Any = None
        self._part_file_button: Any = None
        """Der lokale Bausteindateiweg und sein vorübergehend gesperrter Knopf.

        Ein eigenes Feld neben ``_export_worker``: Ein Bausteinexport ist kein
        Szenenexport, teilt aber dessen Fortschrittsbereich und dieselbe
        Halteleine. Der Knopf wird nach jedem Ausgang wieder freigegeben.
        """
        self._part_file_undo: tuple[str, Any] | None = None
        self._part_file_affected_step: int | None = None
        """Die genau eine sichtbare Rücknahme und ihr erster verwendeter Schritt."""
        self._write_failure: _WriteFailure | None = None
        """Was nach einem gescheiterten Schreiben möglich ist — oder ``None``.

        Solange hier etwas steht, bietet :meth:`error_handlers` *Erneut
        versuchen* und *Anderen Ort wählen* an. Ein Bündel und nicht zwei
        Felder je Schreibweg: Export und Speichern scheitern am selben
        Betriebssystem, und der Kunde bekommt in beiden Fällen dieselben zwei
        Antworten."""
        """Der laufende Export (§2.8, §29). Solange er steht, ist der
        Menüeintrag gesperrt — zwei Läufe auf denselben Ordner wären ein
        Wettlauf um dieselben Dateinamen."""
        self._leash = WorkerLeash(self)
        """Hält fertige und ersetzte Arbeiter, bis Qt mit ihnen durch ist —
        das Warum steht in :mod:`app.ui.leash`."""
        self._proposal: Any = None
        self._applied_transaction: str | None = None
        """Die Transaktion hinter der Übernommen-Leiste (§26.5) — nur solange
        sie die oberste ist, hält der Rückgängig-Knopf sein Versprechen."""
        """Der Agentenzug, der auf eine Entscheidung wartet (§26.5)."""
        self._manual: ManualWindow | None = None
        """Das Handbuchfenster, einmal gebaut und danach wiederverwendet."""
        self._crash_dialog: SupportDialog | None = None
        """Der offene Fehlerbericht, solange einer offen ist (§2.7).

        Ein zweiter Programmfehler wird an ihn angehängt, statt ein zweites
        modales Fenster darüber zu stellen — siehe :meth:`report_error`.
        """
        self._settings_dialog: PrintSettingsDialog | None = None
        """Der offene Druckeinstellungen-Dialog, solange er offen ist (§29).
        Die nachgereichte Schichtanalyse findet über ihn ihren Weg — nach
        ``exec`` steht hier wieder ``None``, und der Rückruf läuft ins
        Leere statt in ein zerstörtes Widget."""
        self._op_dialog: OperationDialog | None = None
        """Der offene Operationsdialog. Er sperrt das Fenster nicht mehr, also
        braucht er eine Referenz: ein Dialog, den nur eine lokale Variable hält,
        verschwindet mit dem Verlassen der Funktion."""
        self._hidden: frozenset[str] = frozenset()
        """§18.8: was der Nutzer ausgeblendet hat. Ansichtszustand des
        Fensters, nicht des Dokuments — er reist nicht mit der Datei."""
        self._announcement = ""
        self._halted = False
        """Ob die stehende Meldung von einer angehaltenen Kette stammt.

        Eine Meldung überlebt hier absichtlich jeden Lauf (:meth:`announce`) —
        richtig für das **Ergebnis einer Handlung**, falsch für einen
        **Zustand**: „Die Kette hält an" galt weiter, nachdem der Kunde den
        Schritt längst berichtigt hatte, und behauptete einen Stopp über einem
        Prüfbericht ohne einen einzigen Fehler (Robert, 29.08.2026). Gemerkt
        wird deshalb die Herkunft, nicht der Text — ein Vergleich auf den Satz
        bräche beim ersten Sprachwechsel."""
        self._run_started: float | None = None
        """Wann der laufende Lauf begann — für die Restzeitschätzung (§2.8).

        Am Fenster und nicht am Balken: Der Balken kennt nur seinen Wert,
        und aus einem Wert allein lässt sich nicht hochrechnen."""
        self._split_fraction = 0.0
        self._split_progress_text = ""
        self._split_determinate = False
        self._split_started: float | None = None
        """Der letzte gültige Stand der laufenden Trennebenensuche.

        Er wird sofort gesammelt, aber erst nach der 0,2-s-Schwelle gezeigt.
        Die bestimmte Stützbewertung darf dabei nie rückwärts laufen."""
        """Was zuletzt zu melden war — siehe :meth:`announce`. Ein laufender
        Fortschritt legt sich darüber und gibt es danach wieder frei."""
        self._patience = QTimer(self)
        """Wann der Wartezeiger kommt — die zweite Stufe von §2.8.

        **Unter zwei Zehntelsekunden zeigt die Anwendung nichts**, und das ist
        keine Feinheit: Von 28 gemessenen Rechnungen liegen elf darunter,
        darunter die häufigsten Gesten überhaupt — einen Wert im Dialog ändern
        (7 ms), am Schichtregler ziehen (0,01 ms), einen Pinselstrich setzen
        (0,2 ms). Bei jeder davon zuckte bisher der Fortschrittsbalken auf und
        sofort wieder weg. Was aufblitzt, sagt nichts; es macht nur unruhig."""
        self._patience.setSingleShot(True)
        self._patience.setInterval(DELAY_MS)
        self._patience.timeout.connect(self._show_wait_cursor)
        self._bar_delay = QTimer(self)
        """Wann Balken und Abbrechen kommen — die dritte Stufe von §2.8.

        Zwölf der 28 Marken liegen zwischen zwei Zehnteln und zwei Sekunden:
        Netz vergröbern, Fläche unterteilen, ein Beispielprojekt öffnen. Dort
        verlangt der Bauplan Zeiger und Zeile, nicht den Balken — und beides
        steht schon da. Der Balken kommt erst, wo das Warten lang genug ist,
        dass man wissen will, wie weit es ist."""
        self._bar_delay.setSingleShot(True)
        self._bar_delay.setInterval(BAR_AFTER_MS)
        self._bar_delay.timeout.connect(self._show_progress_bar)
        self._split_patience = QTimer(self)
        self._split_patience.setSingleShot(True)
        self._split_patience.setInterval(DELAY_MS)
        self._split_patience.timeout.connect(self._release_split_status)
        self._split_bar_delay = QTimer(self)
        self._split_bar_delay.setSingleShot(True)
        self._split_bar_delay.setInterval(BAR_AFTER_MS)
        self._split_bar_delay.timeout.connect(self._release_split_bar)
        self._split_status_released = False
        self._split_bar_released = False
        self._waits = False
        """Ob gerade etwas läuft, das die Stufen von §2.8 trägt.

        Der Zeitgeber fragt danach und nicht die Sitzung: Er gehört dem Lauf,
        der ihn gestartet hat."""
        self._waiting = False
        """Ob der Wartezeiger gerade gesetzt ist.

        Qt stapelt Zeiger: Zweimal setzen und einmal zurücknehmen lässt einen
        stehen, und ein Zeiger, der nach dem Rechnen bleibt, sieht aus wie ein
        hängendes Programm. Die Flagge macht das Paar abzählbar."""
        """Was zuletzt zu melden war — siehe :meth:`announce`. Ein laufender
        Fortschritt legt sich darüber und gibt es danach wieder frei."""
        self._menus: list[QMenu] = []
        """Jedes Menü der Leiste, festgehalten.

        PySide gibt für ein Menü bei jedem Zugriff einen neuen Wrapper, und
        wird einer davon eingesammelt, nimmt er das C++-Objekt mit — danach
        zeigt die Leiste auf ein Menü, das es nicht mehr gibt. Solange nur die
        Bar sie kannte, ging das gut; mit der zweiten Ebene wird aus dem
        Zufall ein Fehler."""
        self._seen_objects = False
        """Ob die Szene schon einmal einen Körper hatte — der erste bekommt
        die Kamera."""
        self._op_actions: dict[str, QAction] = {}
        self._variant_actions: dict[str, QAction] = {}
        """Die Sammeleinträge der Variantengruppen, unter dem Namen ihrer
        ersten Operation. Getrennt von ``_op_actions``, weil sie keiner
        Operation gehören: Wer dort nachschlägt, sucht einen Eintrag, der
        genau eine Operation auslöst, und das tun sie nicht."""
        """Die Menüeinträge der Operationen, damit sie sich ausgrauen lassen.
        Ein Menü, in dem alles anklickbar ist und die Hälfte mit „Bitte zuerst
        etwas auswählen" antwortet, lässt den Nutzer die Regeln erraten."""
        self._palette_actions: dict[str, QAction] = {}
        """Zu welcher Action ein Fensterbefehl der Palette gehört.

        Gefüllt von ``_menu_commands``, gelesen von ``_extra_availability`` —
        die Palette graut damit aus, was das Menü ausgraut."""
        self._display_actions: list[QAction] = []
        """Die Einträge unter *Ansicht → Darstellung*.

        Sie brauchen dieselbe Behandlung wie die Operationen, und zwar aus zwei
        Gründen. Sie wirken auf den Viewport, und den tauscht ``start_sketch``
        aus dem Stapel heraus — im Skizzenmodus ändern sie also etwas, das
        niemand sieht. Und ihre Kürzel sind die Ziffern 1 bis 6, auf denen dort
        der Ebenenwechsel liegt: Qt lässt bei zwei aktiven Kürzeln derselben
        Taste **keines** von beiden feuern. Die Zeichenfläche versprach die
        Taste sichtbar — „(1)", „(2)", „(3)" stehen am Ebenenfeld und noch
        einmal im Tooltip —, und gedrückt geschah nichts."""
        self._trial_message = ""
        """Die Testlauf-Zeile der Statusleiste — gemerkt, damit das
        Freischalten genau sie wegräumt und keine fremde Meldung."""
        self._asked_for_update = False
        """Ob jemand von Hand nach einer neuen Version gefragt hat. Die
        Abfrage beim Start schweigt, wenn es nichts Neues gibt; auf einen Klick
        hin wäre dasselbe Schweigen ein toter Knopf."""
        self._showing_scene = False
        """Ob gerade eine Auswertung ins Fenster geschrieben wird (siehe
        ``_on_scene``). Ein zweiter Durchlauf mitten im ersten räumt Listen,
        die gerade befüllt werden."""
        self._pending_scene: EvaluationResult | None = None
        self._ask_candidates: tuple[tuple[str, str], ...] = ()
        """Die Kandidaten der offenen Rückfrage (§21.3) — leer, wenn keine offen ist."""
        """Das Ergebnis, das während des Aufbaus hereinkam — nachgeholt, sobald
        er fertig ist."""

        self._build_central()
        self._build_status_bar()
        self._build_menus()
        # **Nach den Menüs, weil das Dock seinen Ein-/Ausschalter dort
        # einhängt.** Vorher stand der Aufruf im Zentrum und lief in ein Menü,
        # das es noch nicht gab — die Anwendung kam gar nicht erst hoch.
        self._build_feature_dock()
        # Nach den Menüs, denn die Kopfzeile entsteht in der Werkzeugleiste:
        # ein Aufruf aus ``_build_central`` heraus fände sie noch nicht.
        self._apply_card_style(self.settings.theme)
        self._connect_session()
        self._update_actions()
        self._trial_status_line()

        # §2.6: das offene Werkzeug schließen. ``close_tool`` gab es dafür seit
        # jeher und niemanden, der es rief — Escape tat nichts.
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._escape)

        # §19.2: der Viewport ist mit der Tastatur navigierbar. Die
        # Achsansichten waren es, Zoom und Durchblättern nicht — wer ohne
        # Zeigegerät arbeitet, sah jedes Modell aus derselben Entfernung.
        for sequence, step in (
            (QKeySequence.StandardKey.ZoomIn, 1.25),
            (QKeySequence.StandardKey.ZoomOut, 0.8),
        ):
            QShortcut(sequence, self, weak_slot(self, lambda view, f: view.viewport.zoom(f), step))
        QShortcut(
            QKeySequence("Ctrl+Tab"),
            self,
            weak_slot(self, lambda view: view.object_tree.step_selection(True)),
        )
        QShortcut(
            QKeySequence("Ctrl+Shift+Tab"),
            self,
            weak_slot(self, lambda view: view.object_tree.step_selection(False)),
        )

        # §19.2: die acht Werkzeuge der unteren Leiste bekommen ihr Kürzel, und
        # zwar in der Reihenfolge, in der sie dastehen. Sie hatten als Einzige
        # keines — ausgerechnet die Handgriffe, die einem Anfänger am nächsten
        # liegen.
        #
        # ``Alt`` und eine Ziffer, und zwar aus einem gemessenen Grund: Die
        # Ziffern 1 bis 6 allein gehören der Darstellung und der Projektion,
        # ``Ctrl+1`` bis ``Ctrl+6`` den Kameras. Für eine durchgehende Reihe
        # von acht bleibt ``Alt`` — nachgezählt über alle Fensterbefehle und
        # Menüeinträge, dort ist keine Alt-Folge vergeben.
        #
        # Hier stand als zweite Begründung, ein Kürzel ohne Modifikator
        # schlucke den Buchstaben, während jemand in den Chat tippt. Das ist
        # **falsch**, nachgemessen mit ``QTest``: Ein fokussiertes Eingabefeld
        # bekommt den Buchstaben, der Shortcut feuert nicht. Der Satz ist
        # weg, die Wahl bleibt — sie trägt auch ohne ihn.
        #
        # Welche Zahl zu welchem Werkzeug gehört, steht im Tooltip des Knopfes
        # und in der Kürzelübersicht; geraten werden muss es nicht.
        for index, key in enumerate(self.tools.tools(), start=1):
            self.tools.set_shortcut(key, f"Alt+{index}")
            QShortcut(
                QKeySequence(f"Alt+{index}"),
                self,
                weak_slot(self, lambda view, name: view.tools.toggle(name), key),
            )

        self._autosave = QTimer(self)
        self._autosave.setInterval(AUTOSAVE_INTERVAL_MS)
        self._autosave.timeout.connect(self.session.autosave)
        self._autosave.start()

        self.start_screen.show_recent(settings.existing_recent())
        self._show_start_screen(True)

    # --- construction -----------------------------------------------------------

    def _build_central(self) -> None:
        self.object_tree = ObjectTree(self)
        # Die Vorschaubilder im Baum werden für ein Thema gezeichnet — beim
        # Aufbau ist das die Einstellung, nicht die Vorgabe der Klasse.
        self.object_tree.set_theme(self.settings.theme)
        self.parameters = ParameterPanel(self)
        self.history_panel = HistoryPanel(self)
        self.history_panel.operationActivated.connect(self.edit_operation)
        self.history_panel.noteRequested.connect(self.announce)
        self.history_panel.removalRequested.connect(self.remove_history_operations)
        self.history_panel.bakeRequested.connect(self.bake_sculpt)
        self.filaments = FilamentPanel(self)
        self.filaments.overrideRequested.connect(self._edit_filament_settings)

        # Ohne Streckfaktoren: die Karte ist so hoch wie ihr Inhalt, nicht so
        # hoch wie die Spalte. Ein Objektbaum mit einer Zeile soll eine Zeile
        # hoch sein — gestreckt hinterließ er dreihundert Pixel leere Fläche
        # über einem Modell, das daneben keinen Platz hatte.
        self.feature_panel = FeaturePanel(self)
        self.feature_panel.operationRequested.connect(self._apply_from_feature_panel)
        # **Die Vorschau wartet, das Tippen nicht.** Jeder Tastendruck in einem
        # Zahlenfeld wäre sonst eine Boolesche über das ganze Teil; dieselbe
        # Verzögerung wie im Operationsdialog (§18.7).
        self._feature_preview = QTimer(self)
        self._feature_preview.setSingleShot(True)
        self._feature_preview.setInterval(300)
        self._feature_preview.timeout.connect(self._preview_feature_change)
        self._feature_pending: tuple[str, dict[str, Any]] | None = None
        self.feature_panel.valuesChanged.connect(self._on_feature_values_changed)
        self.feature_panel.operationRequestedForEach.connect(self._apply_to_each_feature)
        # Derselbe Katalog wie aus dem Objektbaum — ein zweiter Weg dorthin,
        # kein zweiter Katalog.
        self.feature_panel.catalogRequested.connect(self.action_catalog)

        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        # Ein Pixel Polster, damit die Randlinie der Karte stehen bleibt: die
        # Listen darin tragen eigene Flächen und malten sie sonst zu (siehe
        # ``CARD_PADDING``).
        left_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        left_layout.setSpacing(TIGHT)
        left_layout.addWidget(collapsible(tr("Objekte"), self.object_tree))
        left_layout.addWidget(collapsible(tr("Parameter"), self.parameters))
        left_layout.addWidget(collapsible(tr("Verlauf"), self.history_panel))
        # Zugeklappt: Die drei darüber beantworten Fragen, die beim Bauen
        # jeden Schritt begleiten; welche Spulen im Regal liegen, fragt man
        # einmal am Anfang und einmal vor dem Drucken (§2.4).
        left_layout.addWidget(collapsible(tr("Filamente"), self.filaments, open_now=False))
        left_layout.addStretch(1)

        self.viewport = Viewport(self)
        # Die 3D-Maus fährt dieselbe Kamera — eine zweite Hand, kein Modus
        # (Konzept 3D-Maus). Gesucht wird das Gerät ab dem ersten Anzeigen —
        # vorher gibt es keine Kamera, die es fahren könnte.
        self.spacemouse = SpaceMouseController(
            self.viewport, self.settings, self.viewport.reset_camera, self
        )
        self.viewport.set_bed_visible(self.settings.bed_visible)
        self.spacemouse.deviceSeen.connect(
            weak_slot(
                self,
                lambda view: view.announce(
                    tr("3D-Maus erkannt. Geschwindigkeit und Richtung stehen in den Einstellungen.")
                ),
            )
        )
        self.viewport.measurementTaken.connect(self._on_measurement)
        self.section_bar = SectionBar(self)
        self.section_bar.sectionChanged.connect(self._on_section)
        self.measure_bar = MeasureBar(self)
        self.viewport.measurementStatus.connect(self.measure_bar.show_status)
        self.measure_bar.modeChanged.connect(self.viewport.set_measure_mode)
        self.measure_bar.clearRequested.connect(self.viewport.clear_measurements)
        self.measure_bar.undoRequested.connect(self.viewport.undo_measurement)
        self.transform_bar = TransformBar(self)
        self.transform_bar.applyRequested.connect(self._apply_from_transform_bar)
        self.transform_bar.snappingChanged.connect(self.viewport.set_snapping)
        self.viewport.transformDragged.connect(self._on_transform_dragged)
        self.viewport.sketchPointPicked.connect(self._on_sketch_point)
        self.viewport.sketchMenuAt.connect(self._on_sketch_menu)
        self.viewport.sketchPointHovered.connect(self._on_sketch_hover)
        self.viewport.sketchPulled.connect(self._on_sketch_pulled)
        self.viewport.sketchPlaneChosen.connect(self._on_sketch_plane_chosen)
        self.viewport.sketchPullBlocked.connect(self.announce)
        self.viewport.sketchViewChanged.connect(self._on_sketch_view_changed)
        self.viewport.faceDragged.connect(self._on_face_dragged)
        self.viewport.scaleDragged.connect(self._on_scale_dragged)
        # **Der Zug am Merkmal kommt fertig gerechnet an.** Die Ansicht hält
        # das Merkmal in der Hand und kennt den Fang; sie schickt die
        # Zielmitte absolut und den Winkel gerastet. Das Fenster macht daraus
        # einen Schritt und rechnet nichts nach (§18.11).
        self.viewport.featureMoved.connect(self._on_feature_moved)
        self.viewport.featureTurned.connect(self._on_feature_turned)
        # Was der Griff bewegen wird, sagt die Ansicht — wo der Satz steht,
        # entscheidet das Fenster, wie bei ``measurementStatus``.
        self.viewport.gizmoStatus.connect(self.announce)
        self.viewport.featurePicked.connect(self._on_feature_picked)
        self.viewport.objectPicked.connect(self._on_object_picked)
        self.viewport.contextMenuAt.connect(self._on_viewport_context_menu)
        self.viewport.pointPicked.connect(self._on_point_picked)

        self.analysis_bar = AnalysisBar(self)
        self.analysis_bar.mapChanged.connect(self._on_map_changed)
        self.analysis_bar.overlayToggled.connect(self.viewport.set_feature_overlay)
        self.layer_bar = LayerBar(self)
        self.layer_bar.layerChanged.connect(self._on_layer_changed)
        self.explode_bar = ExplodeBar(self)
        self.explode_bar.factorChanged.connect(self.viewport.set_explosion)
        self.split_bar = SplitBar(self)
        self.split_bar.applyRequested.connect(self._apply_split_line)
        self.split_bar.clearRequested.connect(self._clear_split_line)
        self.viewport.splitPointRequested.connect(self._on_split_point)
        self._split_points: list[Vec3] = []
        """Die Enden der gezeichneten Trennlinie, in Weltkoordinaten. Eine
        Vorschau, kein Dokumentzustand (Regel 2) — die Operation bekommt die
        Ebene, die daraus folgt."""
        self._split_target: ObjectId | None = None
        """Der Körper, auf den der erste Klick fiel. Aus dem Klick und nicht
        aus der Auswahl: Wer auf ein Teil zeigt, meint dieses Teil, und ein
        Werkzeug, das stattdessen das zuletzt Ausgewählte nimmt, trennt das
        falsche."""
        self._split_plane: SectionPlane | None = None
        """Die beim zweiten Punkt festgelegte und sichtbare Schnittebene.

        Sie bleibt auch dann gleich, wenn danach die Kamera bewegt wird. Die
        Vorschau und die Operation meinen dadurch garantiert dieselbe Ebene.
        """
        self._pending_split_reveal: frozenset[ObjectId] = frozenset()
        """Neue Hälften, die nach ihrer Auswertung auseinandergezogen werden.

        Die Auswertung kommt asynchron; bis dahin zeigt ``last_result`` noch
        die alte Szene. Gemerkt werden deshalb die Ausgaben der Operation und
        nicht ein Zeitpunkt.
        """

        # §2.4: eine Zeile Umschalter statt sieben Dauerleisten. Wie ein
        # Werkzeug beim Schließen zurückgenommen wird, steht hier und nicht in
        # den Leisten — verdrahtet wird sowieso an dieser Stelle.
        self.tools = ToolStrip(self)
        self.tools.add(
            "section",
            tr("Schnitt"),
            self.section_bar,
            weak_slot(self, lambda view: view.section_bar.axis.setCurrentIndex(0)),
            symbol="section",
            # Beim Öffnen waagerecht schneiden: „Kein Schnitt" mit gesperrtem
            # Regler war der Zustand, in dem der Hinweis daneben zum Ziehen
            # aufforderte. Z, weil eine Schicht so liegt, wie der Drucker sie
            # legt — und weil es die Wandstärke zeigt, von der der Hinweis
            # spricht.
            start=weak_slot(self, lambda view: view.section_bar.axis.setCurrentIndex(3)),
            hint=tr(
                "Ziehen Sie den Regler durch das Teil, oder tippen Sie eine Höhe. "
                "Die Schnittfläche wird geschlossen gezeigt — so ist die Wandstärke "
                "ablesbar."
            ),
        )
        self.tools.add(
            "measure",
            tr("Messen"),
            self.measure_bar,
            # **Das Schließen räumt die Maße weg** (Robert, 03.09.2026). Ein
            # Maß ist eine Auskunft über das Teil und kein Dokumentzustand
            # (Regel 2) — dieselbe Entscheidung wie bei der Trennlinie, die
            # ihr Werkzeug auch nicht überlebt. Vorher blieben die Linien im
            # Bild stehen, ohne Werkzeug daneben, mit dem man sie loswird.
            weak_slot(self, lambda view: view.close_measuring()),
            symbol="measure",
            # „Zwei Punkte im Bild anklicken" — dafür muss gemessen werden.
            # Abstand ist die häufigere der beiden Arten und die, die der
            # Hinweis zuerst nennt.
            start=weak_slot(self, lambda view: view.measure_bar.mode.setCurrentIndex(1)),
            hint=tr(
                "Zwei Punkte im Bild anklicken. Der Fang rastet auf Ecken und Kanten; "
                "für die Wandstärke genügt ein Klick auf die Fläche."
            ),
        )
        self.tools.add(
            "transform",
            tr("Bewegen"),
            self.transform_bar,
            weak_slot(self, lambda view: view.viewport.set_gizmo(False)),
            symbol="move",
            # **Das Werkzeug ist der Griff.** Hier stand ein Haken „Gizmo", den
            # das Öffnen setzte und das Schließen wegnahm — ein Schalter also,
            # der nie in einem anderen Zustand war als das Werkzeug selbst. Er
            # ist ersatzlos entfallen; wer *Bewegen* öffnet, will bewegen.
            start=weak_slot(self, lambda view: view.viewport.set_gizmo(True)),
            hint=tr(
                "Am Griff im Bild ziehen, oder Werte eintippen. Jeder Zug wird ein "
                "Schritt im Verlauf und ist einzeln zurücknehmbar."
            ),
        )
        self.tools.add(
            "analysis",
            tr("Analyse"),
            self.analysis_bar,
            weak_slot(self, lambda view: view.analysis_bar.selector.setCurrentIndex(0)),
            symbol="analysis",
            hint=tr(
                "Karte wählen — der Körper färbt sich nach Zahlen, die Legende nennt "
                "den Bereich. Ein Klick auf eine Warnung im Prüfbericht fährt hin."
            ),
        )
        self.tools.add(
            "layers",
            tr("Schichten"),
            self.layer_bar,
            weak_slot(self, lambda view: view.layer_bar.set_active(False)),
            symbol="layers",
            hint=tr(
                "Durch die Höhe fahren und den Querschnitt ansehen. Inseln sind "
                "hervorgehoben: dort beginnt Material in der Luft."
            ),
        )
        self.tools.add(
            "explode",
            tr("Explosion"),
            self.explode_bar,
            weak_slot(self, lambda view: view.explode_bar.slider.setValue(0)),
            symbol="explode",
            hint=tr(
                "Regler schiebt die Teile auseinander. Nur die Ansicht — was "
                "exportiert wird, bleibt, wo es ist."
            ),
        )
        # Trennen ist das eine Werkzeug der Zeile, das das Modell ändert und
        # nicht nur die Ansicht: Es ist der Handgriff, den ein Anfänger als
        # Erstes braucht, sobald ein Teil nicht auf die Platte passt, und ein
        # Menüweg dahin wäre einer zu viel. Was das Schließen zurücknimmt, ist
        # die gezeichnete Linie; ein getrenntes Teil bleibt getrennt und geht
        # über Strg+Z zurück. (Das Bemalen stand mit demselben Argument
        # daneben, bis der Punkt-Radius-Pinsel fiel — Färben läuft seither
        # über das Kontextmenü am Merkmal, als Operation wie jede andere.)
        self.tools.add(
            "split",
            tr("Trennen"),
            self.split_bar,
            # Auch eine gebundene Methode hält hier stark: Der Umschalter legt
            # sie in ein ``Tool`` und das in ein Wörterbuch — ein gewöhnlicher
            # Python-Container, kein Qt-Signal. Was Qt schwach hält, hält eine
            # Liste fest.
            weak_slot(self, lambda view: view._end_split()),
            symbol="split",
            hint=tr(
                "Zwei Punkte auf dem Teil anklicken — dazwischen wird getrennt, "
                "gerade in den Bildschirm hinein. Die Hälften bekommen Stifte zum "
                "Zusammenstecken, wenn der Haken steht."
            ),
        )
        # §30.1 Stufe zwei: die Skizze ist ein Modus des mittleren Bereichs,
        # kein Fenster darüber. Der Stapel hat zwei Seiten — die Ansicht und
        # die Zeichenfläche —, und ein Modus, der die Ansicht ersetzt, ist
        # ehrlicher als ein Qt-Widget über einem OpenGL-Fenster: was man dort
        # sieht, gehört zwei Zeichenwegen, und einer von beiden hat immer
        # gerade nicht neu gezeichnet.
        self.middle_stack = QStackedWidget(self)
        self.middle_stack.addWidget(self.viewport)
        self._remote: RemoteServer | None = None
        """Die MCP-Schnittstelle, solange sie läuft (Konzept P15 §7 Etappe 9)."""
        self._sketch_panel: SketchPanel | None = None
        self._sketch_target: str | None = None
        self._mode_before_sketch: DisplayMode = "solid"
        self._projection_before_sketch: Projection = "perspective"
        """Die Darstellung vor dem Skizzenmodus (§30.1, P4).

        Er blendet das Modell durchscheinend, damit die Zeichnung darauf
        liegt und nicht dahinter. Wer vorher im Drahtgitter gearbeitet hat,
        soll danach wieder darin sein — gemerkt statt geraten."""
        """Der Operationsname, für den gerade gezeichnet wird."""

        # Die Leiste des Skizzenmodus. Sie steht neben der Werkzeugzeile statt
        # in ihr: die sieben dort sind Ansichtswerkzeuge, die sich gegenseitig
        # ablösen — Zeichnen ist keines davon, und ein achter Umschalter hätte
        # die Grenze aus Etappe 0 gerissen, ohne dass er hingehört.
        self.sketch_bar = QWidget(self)
        sketch_layout = QVBoxLayout(self.sketch_bar)
        sketch_layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        sketch_layout.setSpacing(TIGHT)
        sketch_heading = QHBoxLayout()
        sketch_heading.setContentsMargins(0, 0, 0, 0)
        sketch_title = QLabel(tr("Skizze"), self.sketch_bar)
        set_level(sketch_title, "section")
        sketch_heading.addWidget(sketch_title)
        self._sketch_hint = QLabel(
            tr("Zeichnen — die Operation öffnet auf der Skizze."), self.sketch_bar
        )
        self._sketch_hint.setWordWrap(True)
        sketch_heading.addWidget(self._sketch_hint, stretch=1)
        sketch_layout.addLayout(sketch_heading)
        sketch_actions = QHBoxLayout()
        sketch_actions.setContentsMargins(0, 0, 0, 0)
        sketch_actions.addStretch(1)
        # Der Abschluss sieht aus wie einer. Fusion setzt dafür einen großen
        # Haken oben rechts; hier stand ein Textknopf unter den anderen und
        # war von „Verwerfen" nicht zu unterscheiden. Als Hauptknopf trägt er
        # die Auswahlfarbe des Themas und liegt auf der Eingabetaste.
        # Die Formsitzung bekommt ihre eigene Leiste, aus demselben Grund wie
        # die Skizze: Formen ist kein Ansichtswerkzeug, das sich mit Schnitt
        # und Messen ablöst, sondern ein Modus, in den man hineingeht und aus
        # dem man herauskommt (Konzept P16, Entscheidung J).
        self.sculpt_bar = SculptBar(self)
        self.sculpt_bar.finished.connect(self.finish_sculpt)
        self.sculpt_bar.refineRequested.connect(self.refine_for_sculpt)
        # Der Ring folgt dem Regler und nicht erst dem nächsten Zug: Wer den
        # Pinsel größer stellt, will vor dem Klicken sehen, was er greift.
        # ``valueChangedMm`` und nicht ``valueChanged``: Letzteres trägt die
        # Zahl aus dem Feld, und in Zoll wäre der Ring ein Fünfundzwanzigstel
        # des Pinsels.
        self.sculpt_bar.radius.valueChangedMm.connect(self.viewport.set_brush_radius)

        # Der Skeletteditor, dieselbe Bauart: eine Leiste neben der
        # Werkzeugzeile, ein Zustand im Fenster, eine Operation am Ende.
        self.pose_bar = PoseBar(self)
        self.pose_bar.finished.connect(self.finish_armature)
        self.pose_bar.chainBroken.connect(self.break_armature_chain)
        self.pose_bar.lastRemoved.connect(self.undo_bone)
        self.pose_bar.setVisible(False)
        self.viewport.boneRequested.connect(self._on_bone_point)
        self._armature_target: str | None = None
        self._armature_step: int | None = None
        #: Der Verlaufsschritt, den der Zeichenmodus gerade ändert (Z9).
        #:
        #: Gesetzt, wenn jemand aus dem Dialog eines vorhandenen Schritts „Im
        #: Raum zeichnen“ gewählt hat. Dann legt „Fertig“ **keinen** neuen
        #: Schritt an, sondern öffnet denselben mit der neuen Zeichnung —
        #: derselbe Weg, den der Skeletteditor geht.
        self._sketch_step: int | None = None
        """Der Schritt, den dieser Editor ändert — ``None`` heißt: ein neuer."""
        self._armature_bones: list[Bone] = []
        self._armature_head: tuple[float, float, float] | None = None
        """Das Gelenk eines angefangenen Knochens — zwei Klicks machen einen."""
        self._armature_parent = ""
        """Woran der nächste Knochen hängt. Leer nach *Neue Kette*."""
        self.sculpt_bar.setVisible(False)
        self.viewport.sculptRequested.connect(self._on_sculpt)
        self._sculpt_target: str | None = None
        """Das Objekt, an dem gerade geformt wird — leer, wenn keine Sitzung
        läuft."""
        self._sculpt_check = QTimer(self)
        self._usage = UsageClock(self)
        """Die Uhr des Feedbackbogens (§37.2).

        Sie zählt **Arbeit und nicht Laufzeit**: Ein Fenster, das über Nacht
        offen steht, hat die Nacht nicht gearbeitet, und der Bogen erschiene
        sonst jemandem, der gerade vom Kaffee zurückkommt. Was sie zählt und
        wann sie fällig wird, entscheidet ``app.core.feedback`` — hier hängt
        nur, was daraus im Fenster passiert.
        """
        self._usage.due.connect(self._offer_survey)
        self._survey_notice = SurveyNotice(self.viewport)
        """Die Karte über der Ansicht, mit der gefragt wird. Sie hält nichts
        an und verschwindet nicht von selbst — sie bleibt, bis jemand einen
        ihrer beiden Knöpfe drückt."""
        self._survey_notice.accepted.connect(self._open_survey)
        self._survey_dialog: SupportDialog | None = None
        """Der offene Bogen — festgehalten, weil ein nicht modales Fenster ohne
        Referenz eingesammelt wird, sobald die Methode zurückkehrt."""
        self._sculpt_check.setSingleShot(True)
        self._sculpt_check.setInterval(SCULPT_CHECK_MS)
        self._sculpt_check.timeout.connect(self._check_sculpted_walls)
        """Die Wandstärkenprüfung läuft **nach** der Geste, nicht in ihr
        (Entscheidung L). Bei jedem Zug zu rechnen hieße, den Pinsel um eine
        Viertelsekunde zu verzögern, damit eine Zahl aktuell ist, die sich beim
        nächsten Zug wieder ändert."""
        self._sculpt_strokes: list[Stroke] = []
        self._discarded_sketch: _DiscardedSketch | None = None
        """Die zuletzt verworfene Zeichnung, solange Strg+Z sie noch meint."""
        """Die Züge dieser Sitzung. Das Rückgängig des Editors läuft auf
        dieser Liste und nicht über den Verlauf: Der Verlauf bekommt die
        Sitzung als *eine* Transaktion, wenn sie fertig ist (Regel 16)."""

        # Die zwei häufigsten Folgen stehen **an der fertigen Kontur**. Wer
        # Solidon ohne CAD-Vokabular benutzt, soll weder „Extrusion“ kennen
        # noch erst über *Fertig* eine Liste durchsuchen. Der Dialog danach
        # bleibt: Dort wird die genaue Höhe oder Tiefe eingetragen.
        self.sketch_pull_button = QPushButton(tr("Hochziehen"), self.sketch_bar)
        self.sketch_pull_button.setIcon(icon("sketch_pull", self.sketch_pull_button))
        self.sketch_pull_button.clicked.connect(
            weak_slot(self, lambda view: view._finish_sketch_as(PULL_OP))
        )
        self.sketch_cut_button = QPushButton(tr("Abtragen"), self.sketch_bar)
        self.sketch_cut_button.setIcon(icon("sketch_cut", self.sketch_cut_button))
        self.sketch_cut_button.clicked.connect(
            weak_slot(self, lambda view: view._finish_sketch_as(POCKET_OP))
        )
        sketch_actions.addWidget(self.sketch_pull_button)
        sketch_actions.addWidget(self.sketch_cut_button)

        done = QPushButton(tr("Fertig"), self.sketch_bar)
        make_primary(done)
        done.clicked.connect(weak_slot(self, lambda view: view.finish_sketch(keep=True)))
        discard = QPushButton(tr("Verwerfen"), self.sketch_bar)
        discard.clicked.connect(weak_slot(self, lambda view: view.finish_sketch(keep=False)))
        sketch_actions.addWidget(done)
        sketch_actions.addWidget(discard)
        sketch_layout.addLayout(sketch_actions)
        self.sketch_bar.setVisible(False)

        # Werkzeugzeile und Skizzenleiste schweben zusammen unten in der Mitte.
        # Zusammen, weil beide dasselbe meinen — was gerade in der Hand liegt —
        # und weil zwei getrennt schwebende Bänder übereinander aussähen wie
        # ein Versehen.
        bottom = QWidget(self)
        bottom.setObjectName("overlayCard")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(TIGHT, TIGHT, TIGHT, TIGHT)
        bottom_layout.setSpacing(0)
        self._bottom_layout = bottom_layout
        """Die schwebende Karte unten — dort hängt sich der Skizzenmodus ein.

        Als Feld, weil ``start_sketch`` das Panel hineinstellt, statt es wie
        früher gegen die Ansicht zu tauschen (§30.1, P4)."""
        bottom_layout.addWidget(self.sketch_bar)
        bottom_layout.addWidget(self.sculpt_bar)
        bottom_layout.addWidget(self.pose_bar)
        bottom_layout.addWidget(self.tools)

        self.report = ReportPanel(self)
        self.report.findingActivated.connect(self._on_finding_activated)
        self.report.actionOnBodies.connect(self._run_on_chosen_bodies)
        self.report.slicerRequested.connect(self.action_print_settings)
        self.chat = ChatPanel(self)
        self.chat.requestSent.connect(self._on_request_sent)
        self.chat.accepted.connect(self._on_proposal_accepted)
        self.chat.discarded.connect(self._on_proposal_discarded)
        self.chat.undoRequested.connect(self._on_applied_undone)
        # Der Knopf am gesperrten Chat führt dorthin, wo beide Wege aus §27
        # stehen — Schlüssel und lokales Modell. Er hing am Installationsdialog
        # und bot damit nur einen davon an.
        self.chat.setupRequested.connect(self.action_llm_key)
        self.chat.unlockRequested.connect(self.action_activate)
        self.chat.imageDropped.connect(self.action_generate_from_image)

        # §37.2: die Beispiele sind auch Doku. Die Tour macht sie dazu — der
        # Reiter ist nur sichtbar, solange ein Beispiel offen ist.
        self.tour = TourPanel(self.session, self)
        self.tour.closed.connect(self._remove_tour)
        self.tour.pointsAt.connect(self._flash_area)
        self.tour.followRequested.connect(self._open_example)

        self.right = QTabWidget(self)
        self.right.addTab(self.report, tr("Prüfbericht"))
        self.right.addTab(self.chat, tr("Chat"))
        # Der Reiter trägt, wie viele Fehler und Warnungen hinter ihm stehen.
        # Ohne die Zahl bleibt eine Warnung unsichtbar, solange Chat oder Tour
        # vorn sind: ein eingelesenes Netz mit offenen Stellen meldete sich im
        # Bericht, und der Reiter sah aus wie vorher.
        self.report.alertsChanged.connect(self._mark_report_tab)
        self.report.alertsChanged.connect(self._mark_status_alerts)
        # Der Reiter wird einmal angelegt und danach nur noch ein- und
        # ausgeblendet, nie entfernt: ``removeTab`` machte das Panel elternlos,
        # und ein elternloses Widget gehört dem Speicherbereiniger — der es
        # irgendwann aus einem Arbeiter-Thread zerstörte. Ein Absturz ohne
        # Zeile, lange nach der Tour.
        self.right.addTab(self.tour, tr("Tour"))
        self.right.setTabVisible(self.right.indexOf(self.tour), False)
        self._constraints_room = QWidget(self)
        """Der Reiter, in dem die Bedingungen der offenen Skizze stehen (§30.1).

        Dauerhaft angelegt und nur ein- und ausgeblendet, wie die Tour daneben:
        Ein Reiter, der jedes Mal neu entsteht, hätte einen Index, auf den sich
        nichts verlassen kann."""
        self._constraints_box = QVBoxLayout(self._constraints_room)
        self._constraints_box.setContentsMargins(0, 0, 0, 0)
        self.right.addTab(self._constraints_room, tr("Bedingungen"))
        self.right.setTabVisible(self.right.indexOf(self._constraints_room), False)

        # §2.5 nennt drei Zonen und sagt nicht, dass die äußeren der mittleren
        # ihre Fläche nehmen. Sie liegen jetzt darüber: die Ansicht füllt das
        # Fenster, und wo keine Karte steht, sieht man das Modell.
        left.setObjectName("overlayCard")
        self.right.setObjectName("overlayCard")
        self.overlay = OverlayHost(self.middle_stack, self)
        self.overlay.set_zones(left, self.right, bottom)
        # Parameterzeilen entstehen nach dem Öffnen eines Projekts neu. Ihre
        # endgültige Höhe kennt Qt einen Ereignisschritt später; dann muss die
        # frei gesetzte linke Karte ausdrücklich neu verteilt werden. Ohne
        # diesen Weg blieb auf Windows die Höhe des leeren Zustands stehen und
        # drückte Zahlen- und Einheitenfelder zu schmalen Schlitzen zusammen.
        self.parameters.heightChanged.connect(weak_slot(self, lambda view: view.overlay.reflow()))
        # Ein geöffnetes Werkzeug macht die untere Zone dreimal so hoch. Die
        # Überlagerung setzt Geometrien, statt sie von einem Layout rechnen zu
        # lassen — sie muss also erfahren, dass sich der Bedarf geändert hat.
        # Ohne diese Verbindung blieb die Zone auf der Höhe der Knopfreihe,
        # und die Leiste des Werkzeugs lag über den Umschaltern — bei jedem
        # einzelnen, von Schnitt bis Trennen.
        self.tools.toolChanged.connect(weak_slot(self, lambda view: view.overlay.reflow()))
        # **Ein Werkzeugwechsel beendet das Zug-Bündel** (§15.5, P9). Er legt
        # keine Transaktion an und ist trotzdem eine Handlung — ohne diese
        # Zeile hinge der erste Zug nach dem Wechsel am letzten davor, und ein
        # Strg+Z nähme beide zusammen zurück.
        self.tools.toolChanged.connect(
            weak_slot(self, lambda view: view.session.history.end_bundle())
        )
        # Wer *Schichten* öffnet, will Schichten sehen. Der Schalter dafür war
        # ein zweites Auswahlfeld in der Leiste selbst — ein Umschalter hinter
        # dem Umschalter, der die Leiste öffnet. Geschlossen wird über den
        # ``reset`` des Werkzeugs.
        self.tools.toolChanged.connect(
            weak_slot(
                self, lambda view, key: view.layer_bar.set_active(key == "layers"), forward=True
            )
        )
        # Dasselbe für das Trennen: Der Umschalter macht aus Klicks Punkte der
        # Trennlinie. An der Leiste vorbei gäbe es zwei Stellen, die denselben
        # Zustand steuern — und die gewinnen abwechselnd.
        self.tools.toolChanged.connect(
            weak_slot(
                self, lambda view, key: view.viewport.set_splitting(key == "split"), forward=True
            )
        )
        # Dasselbe für Befunde, die nach der Auswertung nachkommen: die Liste
        # meldet ihr Wachstum, weil ein QListWidget es nicht von selbst tut.
        self.report.contentGrew.connect(self.overlay.reflow)
        self.sketch_bar.installEventFilter(self.overlay)

        # **Einmal für die ganze Anwendung, nicht je Fenster.** Das
        # ``ShortcutOverride`` geht an das Bedienelement mit dem Fokus, nicht an
        # das Fenster darüber — von dort aus ist es nicht zu sehen. Der Filter
        # hängt deshalb an der Anwendung, und er hängt dort **einmal**: Je
        # Fenster installiert, wuchs die Filterkette mit jedem gebauten Fenster,
        # und jedes Ereignis lief durch alle. In der Suite, die über zweihundert
        # Fenster in einem Prozess baut, blieb der Lauf bei 97 % stehen —
        # gemessen, zweimal, nach zehn Minuten abgebrochen.
        install_navigation_keys()

        # §2.8: eine Wartezeit gehört dorthin, wo hingesehen wird. Der Balken
        # unten rechts ist richtig, solange ein Modell im Bild steht — beim
        # Öffnen eines Projekts steht dort nichts, und dann war er die einzige
        # Auskunft an der Stelle, an der niemand hinsieht.
        self.veil = LoadingVeil(self)
        self.veil.set_theme(self.settings.theme)
        # Der Schleier gehört ausschließlich zur Auswertung einer leeren Szene.
        # Ein Agentenzug oder Split kann parallel laufen und bleibt davon
        # unberührt; der gemeinsame Statusknopf entscheidet dagegen per Owner.
        self.veil.cancelRequested.connect(self.session.cancel_evaluation)
        # Solange der Schleier steht, wird die Ansicht verborgen, nicht nur
        # verdeckt — warum, steht am Signal ``appeared`` in loading.py.
        self.veil.appeared.connect(self._on_veil_appeared)
        self.veil.ended.connect(self._on_veil_ended)
        self.overlay.set_veil(self.veil)

        self.start_screen = StartScreen(self)
        self.start_screen.newRequested.connect(self.start_empty)
        self.start_screen.browseRequested.connect(self.action_open)
        self.start_screen.importRequested.connect(self.action_import)
        self.start_screen.openRequested.connect(self.open_path)
        self.start_screen.fileDropped.connect(self.open_path)
        self.start_screen.urlDropped.connect(self.download_model)
        self.start_screen.forgetRequested.connect(self._forget_recent)
        # Mit Kapitel: Der Knopf nennt es, also schlägt er es auf.
        self.start_screen.manualRequested.connect(
            weak_slot(self, lambda view: view.action_manual(manual.FIRST_MINUTES))
        )
        self.start_screen.feedbackRequested.connect(self._open_survey)
        self.start_screen.supportRequested.connect(self.action_donate)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.start_screen)
        self.stack.addWidget(self.overlay)
        self.setCentralWidget(self.stack)

        self.object_tree.selectionChanged.connect(self._on_selection)
        self.object_tree.featureSelected.connect(self._on_feature_selected)
        # Zwei markierte Merkmale beantworten eine andere Frage als eines —
        # deshalb ein eigenes Signal und ein eigener Empfänger.
        self.object_tree.featuresSelected.connect(self._on_features_selected)
        # **Über ``launch_operation``, nicht ``run_operation``.** Genau dieser
        # Fehler ist für Menü und Palette schon behoben worden, das Kontextmenü
        # blieb hängen: Drei Operationen mit Gestenfeld stehen dort am Körper —
        # „Formen", „Stellung geben" und „Tasche schneiden" —, und ein
        # Rechtsklick darauf öffnete einen Dialog mit einem Textfeld für Züge
        # statt des Pinsels. Die Operation lief, änderte nichts und hinterließ
        # einen leeren Schritt im Verlauf. Der Rechtsklick auf den Körper ist
        # der Weg, den §2.6 „den kürzesten Weg vom Sehen zum Tun" nennt.
        self.object_tree.operationRequested.connect(self.launch_operation)
        self.object_tree.stepRequested.connect(self.edit_operation)
        self.object_tree.sketchOnFaceRequested.connect(self._on_sketch_on_face)
        self.object_tree.catalogRequested.connect(self.action_catalog)
        self.object_tree.visibilityRequested.connect(self._on_visibility)
        self.object_tree.isolateRequested.connect(self._on_isolate)
        self.parameters.parameterEdited.connect(self._on_parameter_edited)
        self.parameters.parameterUnitEdited.connect(self._on_parameter_unit_edited)
        self.parameters.addRequested.connect(self.action_add_parameter)
        self.parameters.limitsRequested.connect(self.action_edit_parameter)
        self.right.setVisible(self.settings.right_panel_visible)

    def _build_status_bar(self) -> None:
        self.measurements = MeasurementLabel(self)
        self.status_message = QLabel("", self)
        # **Keine Zahl im Balken.** Sie steht mittig, und der Rand der
        # Füllung wandert darunter hindurch: bei 45 % lag sie halb auf
        # Bernstein und halb auf der Spur, ab 60 % ganz auf Bernstein — mit
        # 1,69 Kontrast, also unlesbar. Eine Farbe, die auf beiden Gründen
        # trägt, gibt es nicht; eine dunklere Füllung nähme dem Balken den
        # Akzent (gerechnet: 4,5 Schriftkontrast kostet die Hälfte des
        # Flächenkontrasts). Der Prozentwert steht deshalb in der Zeile
        # daneben, wo ein ruhiger Grund ist.
        self.progress = QProgressBar(self)
        self.progress.setTextVisible(False)
        self.progress.setMaximumWidth(180)
        self.progress.setAccessibleName(tr("Fortschritt"))
        self.progress.setAccessibleDescription(tr("Zeigt den Fortschritt der laufenden Aufgabe."))
        self.progress.setVisible(False)
        self.cancel_button = QPushButton(tr("Abbrechen"), self)
        self.cancel_button.setAccessibleName(tr("Abbrechen"))
        self.cancel_button.setAccessibleDescription(tr("Bricht die laufende Aufgabe ab."))
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._cancel_visible_progress)
        generic_name = tr("Fortschritt")
        generic_description = tr("Zeigt den Fortschritt der laufenden Aufgabe.")
        generic_cancel = tr("Bricht die laufende Aufgabe ab.")
        self._progress_states = {
            "evaluation": _ProgressState(
                False,
                "",
                0,
                100,
                0,
                generic_name,
                generic_description,
                generic_cancel,
                True,
                True,
                False,
            ),
            "agent": _ProgressState(
                False,
                tr("Der Agent denkt nach."),
                0,
                0,
                0,
                generic_name,
                tr("Der Agent denkt nach."),
                generic_cancel,
                True,
                True,
                True,
            ),
            "export": _ProgressState(
                False,
                "",
                0,
                0,
                0,
                generic_name,
                generic_description,
                generic_cancel,
                False,
                False,
                True,
            ),
            "part_file": _ProgressState(
                False,
                "",
                0,
                0,
                0,
                generic_name,
                generic_description,
                generic_cancel,
                False,
                False,
                False,
            ),
            "download": _ProgressState(
                False,
                tr("Modell herunterladen …"),
                0,
                100,
                0,
                tr("Modell herunterladen"),
                tr("Modell herunterladen …"),
                generic_cancel,
                True,
                True,
                True,
            ),
            "split": _ProgressState(
                False,
                tr("Die Trennebenen werden gesucht …"),
                0,
                0,
                0,
                tr("Fortschritt: Automatisch teilen"),
                tr("Die Trennebenen werden gesucht …"),
                tr("Bricht die automatische Teilung ab. Modell und Verlauf bleiben unverändert."),
                True,
                True,
                False,
            ),
        }
        self._progress_owner: str | None = None

        # §2.5 nennt für die Statusleiste „Maße · Auswahl · Fortschritt ·
        # Warnungen". Material und Dauer gehören dazu: sie sind das Maß, das
        # beim Drucken zählt, und standen bisher allein hinter Strg+P.
        self.facts = PrintFacts(self)
        self.facts.clicked.connect(self.action_print_settings)

        # Die Demo- und Testzeitraumzeile steht **dauerhaft** (Demo-Konzept
        # §2 F) und ist damit keine Meldung im Sinne von ``showMessage`` —
        # das blendet aus, was links per ``addWidget`` liegt. Genau das war
        # sie vorher, und weil das Maß-Label trotzdem sichtbar blieb, lagen
        # „Keine Auswahl" und „Demo — noch 79 Tage" übereinander: auf jedem
        # Handbuchbild, in jeder Sprache. Als eigenes dauerhaftes Feld steht
        # sie neben den Maßen statt auf ihnen, und ``showMessage`` bleibt
        # frei für das, wofür es gedacht ist — den Zeichenmodus etwa.
        # §2.5 nennt für die Statusleiste auch „Warnungen", und die standen
        # dort nie. Solange die rechte Spalte offen ist, trägt ihr Reiter die
        # Zahl; ist sie zu, erreichte eine neue Warnung niemanden mehr —
        # ``_focus_report`` steigt bei unsichtbarer Spalte zu Recht aus, und
        # danach kam nichts. Der Knopf erscheint genau dann und holt beides
        # zurück: die Spalte und den Bericht.
        self.alert_button = QToolButton(self)
        self.alert_button.setAutoRaise(True)
        self.alert_button.setAccessibleName(tr("Offene Befunde"))
        self.alert_button.setVisible(False)
        self.alert_button.clicked.connect(self._show_alerts)

        # **Ein Knopf und kein Label, weil die Zeile einen Weg nennt.** Sie
        # sagt „Hilfe → Solidon freischalten …", und eine Wegbeschreibung an
        # der Stelle, an der man steht, ist ein Weg, den jemand zu Fuß gehen
        # soll. Als Knopf ist sie derselbe Satz und ein Klick — flach
        # gezeichnet, damit die Statusleiste eine Auskunftszeile bleibt und
        # keine Knopfleiste wird.
        self.trial_line = QToolButton(self)
        self.trial_line.setAutoRaise(True)
        self.trial_line.setVisible(False)
        self.trial_line.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trial_line.clicked.connect(self.action_activate)

        bar = self.statusBar()
        bar.addWidget(self.measurements, 1)
        bar.addPermanentWidget(self.alert_button)
        bar.addPermanentWidget(self.trial_line)
        # **Zwei Auskünfte, nicht ein Satz.** Links steht, wie lange die
        # Fassung noch läuft, rechts, was das Teil kostet — dazwischen lag
        # nur ein Wortabstand, und „… bis zum 30.10.2026  51 g · 3 h 30 min"
        # las sich als eine Aussage. Der Mittelpunkt trennt weiter *innerhalb*
        # einer Auskunft; zwischen zweien steht die Linie.
        self.trial_divider = divider(self)
        self.trial_divider.setVisible(False)
        bar.addPermanentWidget(self.trial_divider)
        bar.addPermanentWidget(self.facts)
        bar.addPermanentWidget(self.status_message)
        bar.addPermanentWidget(self.progress)
        bar.addPermanentWidget(self.cancel_button)

    def _set_progress_state(self, owner: str, **changes: Any) -> None:
        """Speichert genau einen Aufgabenstand und wählt danach die Anzeige."""

        self._progress_states[owner] = replace(self._progress_states[owner], **changes)
        self._render_progress_state()

    def _active_progress_owner(self) -> str | None:
        """Wählt bei überlappenden Aufgaben immer denselben sichtbaren Besitzer."""

        return next(
            (owner for owner in _PROGRESS_PRIORITY if self._progress_states[owner].active),
            None,
        )

    def _visible_progress_owner(self, *, split_released: bool) -> str | None:
        """Wählt einen Besitzer, dessen eigene Sichtbarkeitsschwelle erreicht ist."""

        return next(
            (
                owner
                for owner in _PROGRESS_PRIORITY
                if self._progress_states[owner].active and (owner != "split" or split_released)
            ),
            None,
        )

    def _render_progress_state(self, *, force_visible: bool = False) -> None:
        """Überträgt ausschließlich den gewählten Aufgabenstand in die Widgets."""

        previous_owner = self._progress_owner
        was_visible = self.progress.isVisibleTo(self)
        owner = self._visible_progress_owner(split_released=self._split_bar_released)
        status_owner = self._visible_progress_owner(split_released=self._split_status_released)
        self._progress_owner = owner
        if owner is None:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.setAccessibleName(tr("Fortschritt"))
            self.progress.setAccessibleDescription(
                tr("Zeigt den Fortschritt der laufenden Aufgabe.")
            )
            self.progress.setVisible(False)
            self.cancel_button.setEnabled(True)
            self.cancel_button.setAccessibleDescription(tr("Bricht die laufende Aufgabe ab."))
            self.cancel_button.setVisible(False)
        else:
            state = self._progress_states[owner]
            self.progress.setRange(state.minimum, state.maximum)
            self.progress.setValue(state.value)
            self.progress.setAccessibleName(state.accessible_name)
            self.progress.setAccessibleDescription(state.accessible_description)
            self.cancel_button.setEnabled(state.cancel_enabled)
            self.cancel_button.setAccessibleDescription(state.cancel_description)

            visible = (
                state.immediate or force_visible or (previous_owner is not None and was_visible)
            )
            self.progress.setVisible(visible)
            self.cancel_button.setVisible(visible and state.cancellable)

        if status_owner is None:
            self.status_message.setText(self._announcement)
            return
        status = self._progress_states[status_owner]
        if status.immediate or status_owner == "split" or self._waiting:
            self.status_message.setText(status.text or self._announcement)
        else:
            self.status_message.setText(self._announcement)

    def _cancel_visible_progress(self) -> None:
        """Bricht nur die Aufgabe ab, die der gemeinsame Bereich gerade nennt."""

        owner = self._visible_progress_owner(split_released=self._split_bar_released)
        if owner is None:
            return
        state = self._progress_states[owner]
        if not state.cancellable or not state.cancel_enabled:
            return
        handlers = {
            "evaluation": self.session.cancel_evaluation,
            "agent": self.session.cancel_agent,
            "download": self._cancel_download,
            "split": self.session.cancel_split,
        }
        handler = handlers.get(owner)
        if handler is not None:
            handler()

    def _build_menus(self) -> None:
        self._workspace_menus: list[QMenu] = []
        """Menüs, die eine offene Szene voraussetzen. Auf dem Startbildschirm
        werden sie ausgeblendet statt ausgegraut: siebzig Einträge, von denen
        dort keiner etwas tut, sind keine Auskunft, sondern Kulisse (§2.6).
        Datei und Hilfe bleiben — Öffnen, Beenden, Handbuch und Freischalten
        sind genau dort sinnvoll."""
        file_menu = self._menu(tr("Datei"))
        # Festgehalten, nicht weil das Menü sie bräuchte, sondern weil die
        # Werkzeugleiste ihren Satz und ihr Kürzel übernimmt: derselbe Knopf
        # soll nicht zwei Erklärungen haben, die auseinanderdriften.
        self.new_action = self._add_action(
            file_menu,
            tr("Neu"),
            QKeySequence.StandardKey.New,
            self.action_new,
            tr("Zum Startbildschirm: leeres Projekt, ein Beispiel, oder zuletzt Geöffnetes."),
            symbol="new",
        )
        self.open_action = self._add_action(
            file_menu,
            tr("Öffnen …"),
            QKeySequence.StandardKey.Open,
            self.action_open,
            tr("Ein gespeichertes Projekt öffnen (.p3d)."),
            symbol="open",
        )
        self.save_action = self._add_action(
            file_menu,
            tr("Speichern"),
            QKeySequence.StandardKey.Save,
            self.action_save,
            tr("Projekt mit Geometrie, Verlauf und Parametern in eine Datei schreiben."),
            symbol="save",
        )
        self._add_action(
            file_menu,
            tr("Speichern unter …"),
            QKeySequence.StandardKey.SaveAs,
            self.action_save_as,
            tr("Das Projekt unter einem anderen Namen ablegen."),
            symbol="save",
        )
        file_menu.addSeparator()
        self.import_action = self._add_action(
            file_menu,
            tr("Modell einfügen …"),
            "Ctrl+I",
            self.action_import,
            tr(
                "Eine Modelldatei oder flache Zeichnung laden. Eine 3MF-Baugruppe "
                "kommt als einzelne Körper an."
            ),
            symbol="import",
        )
        self.import_url_action = self._add_action(
            file_menu,
            tr("Modell aus dem Netz …"),
            None,
            self.action_import_url,
            tr(
                "Eine Modelldatei über ihre Adresse laden — für den Fall, dass sie "
                "noch nicht auf dem Bett liegt."
            ),
            symbol="network",
        )
        self.generate_action = self._add_action(
            file_menu,
            tr("Modell erzeugen …"),
            "Ctrl+G",
            self.action_generate,
            tr("Aus Text oder Bild ein 3D-Modell erzeugen lassen — braucht ein laufendes ComfyUI."),
            symbol="generate",
        )
        # **Dieselbe Aktion hängt unten noch einmal im Menü *Bausteine*.**
        # Nicht als zweite mit demselben Kürzel: Qt registriert Strg+K dann
        # zweimal, meldet „ambiguous shortcut overload" und führt keine von
        # beiden aus. Eine ``QAction`` darf in mehreren Menüs stehen; ihr
        # Kürzel gehört ihr, nicht dem Menü.
        self._catalog_action = self._add_action(
            file_menu,
            tr("Bausteinkatalog …"),
            "Ctrl+K",
            self.action_catalog,
            tr("Alle Bausteine durchsehen: Mutternfalle, Rastnase, Scharnier und die anderen."),
            symbol="category.parts",
        )
        self.export_action = self._add_action(
            file_menu,
            tr("Exportieren …"),
            "Ctrl+E",
            self.action_export,
            tr(
                "Die Körper als STL, 3MF, OBJ, PLY oder STEP schreiben — "
                "mit der Prüfung aus dem Bericht davor."
            ),
            symbol="export",
        )
        self._add_action(
            file_menu,
            tr("Druckeinstellungen …"),
            "Ctrl+P",
            self.action_print_settings,
            tr("Schichten, Temperaturen, Farbe und Stützen einstellen — und slicen lassen."),
            symbol="print_settings",
        )
        self._add_action(
            file_menu,
            tr("G-Code gegenprüfen …"),
            None,
            self.action_check_gcode,
            tr("Eine Datei aus dem Slicer lesen und ihre Zahlen neben die eigenen stellen."),
            symbol="layers",
        )
        file_menu.addSeparator()
        # Ohne Kürzel: QKeySequence.StandardKey.Quit liefert auf Windows die
        # Multimedia-Taste „Exit", und im Menü stand deshalb „Beenden ·
        # Verlassen" — eine Taste, die kaum eine Tastatur hat, als Kürzel
        # angeboten. Alt+F4 macht Windows selbst, Cmd+Q macht macOS über sein
        # Anwendungsmenü. Ein falsches Kürzel ist schlechter als keines.
        self._quit_action = self._add_action(
            file_menu,
            tr("Beenden"),
            None,
            self.close,
            tr("Solidon schließen. Ungesichertes wird vorher erfragt."),
            symbol="quit",
        )

        edit_menu = self._menu(tr("Bearbeiten"))
        self._workspace_menus.append(edit_menu)
        # Rückgängig und Wiederholen zuerst: sie sind die häufigsten Einträge
        # des Menüs und stehen in jeder Anwendung oben. Vorher lagen sie unter
        # den Spezialfunktionen, hinter „Chat einrichten".
        self.undo_action = self._add_action(
            edit_menu,
            tr("Rückgängig"),
            QKeySequence.StandardKey.Undo,
            self.action_undo,
            tr("Den letzten Schritt zurücknehmen — auch einen Vorschlag des Chats, ganz."),
            symbol="undo",
        )
        self.redo_action = self._add_action(
            edit_menu,
            tr("Wiederholen"),
            QKeySequence.StandardKey.Redo,
            self.action_redo,
            tr("Einen zurückgenommenen Schritt wieder anwenden."),
            symbol="redo",
        )
        edit_menu.addSeparator()
        # Gemerkt, weil die Kürzelübersicht darauf verweist. Dort stand die
        # Taste als Text, und der war falsch.
        self._palette_action = self._add_action(
            edit_menu,
            tr("Befehlspalette …"),
            "Ctrl+Shift+P",
            self.action_command_palette,
            tr("Jede Operation über ihren Namen finden, ohne durch die Menüs zu gehen."),
        )
        self._add_action(
            edit_menu,
            tr("Parameter anlegen …"),
            None,
            self.action_add_parameter,
            tr("Ein Maß benennen, auf das Operationen und Skizzen mit @name verweisen können."),
        )
        self._add_action(
            edit_menu,
            tr("Material kalibrieren …"),
            None,
            self.action_calibrate,
            tr(
                "Das gemessene Spiel eintragen. Es gilt danach für jede Passung, "
                "auch in älteren Projekten."
            ),
        )
        self.variants_action = self._add_action(
            edit_menu,
            tr("Varianten erzeugen …"),
            None,
            self.action_variants,
            tr(
                "Dasselbe Teil mehrfach mit gestaffelten Werten exportieren, "
                "statt von Hand zu ändern."
            ),
        )
        self._add_action(
            edit_menu,
            tr("Einstellungen …"),
            "Ctrl+,",
            self.action_settings,
            tr("Sprache, Anzeigeeinheit, Thema, Navigation und die Vorgaben für neue Projekte."),
        )
        self._add_action(
            edit_menu,
            tr("Chat einrichten …"),
            None,
            self.action_llm_key,
            tr(
                "Schlüssel oder lokales Modell für den Chat hinterlegen. Ein "
                "Schlüssel landet im Schlüsselbund, nie in der Projektdatei."
            ),
        )

        # Alles darunter kommt aus dem Register (§10). Der Hinweis ist die
        # Beschreibung der Operation und steht deshalb an beiden Stellen: in der
        # Statusleiste beim Durchgehen und als Tooltip beim Zögern.
        # **Eigene Bausteine des Nutzers bleiben aus der Menüleiste heraus**
        # (§24.5, Konzept Befestigungssysteme E1). Jeder von ihnen wird eine
        # Operation und damit ein Menüeintrag; zwanzig eigene Teile machen aus
        # einem Menü eine Liste zum Absuchen, und die Zeilengrenze aus
        # ``tests/test_interface_limits.py`` kann es nie sehen — die Suite
        # liest den Nutzerordner bewusst nicht (§38). Erreichbar bleiben sie
        # über Bausteinkatalog, Befehlspalette und Kontextmenü.
        # **Und die Bausteine der Bibliothek ebenso** (§2.6): Ein räumliches
        # Teil als Textzeile zu führen ist die schlechtere Darstellung, und im
        # Menü standen neunundzwanzig davon in sechs Untermenüs — jede Zeile
        # eine Vokabel statt einer Form. Der Katalog mit Bildern steht in
        # *Datei*, auf Strg+K und im Kontextmenü am gewählten Teil.
        #
        # **Gefragt wird nach der Kachel, nicht nach der Kategorie.** Hier
        # stand die ganze Kategorie ``parts``, und das nahm zwei Operationen
        # mit, die gar keine Kachel haben: *Deckel erzeugen* und *Drehdeckel
        # erzeugen* bauen einen Deckel, statt einen fertigen einzusetzen.
        # Gemessen am gebauten Fenster waren es 114 Menüeinträge ohne einen
        # davon — und im Katalog stehen sie auch nicht. Sie bleiben deshalb
        # hier stehen, und das Menü *Bausteine* trägt sie.
        own = frozenset(bootstrap.user_operations()) | catalogue_operations()
        sections = {section.category: section for section in menu_tree(skip=own)}
        groups: dict[str, QMenu] = {}
        for title, categories in MENU_GROUPS:
            present = [sections[name] for name in categories if name in sections]
            if not present:
                continue
            group = self._menu(str(title))
            groups[str(title)] = group
            self._workspace_menus.append(group)
            if any(section.category == "parts" for section in present):
                # **Ein Menü *Bausteine*, in dem keine Bausteine stehen,
                # führt in die Irre.** Übrig sind hier zwei Operationen, die
                # einen Deckel bauen; wer das Menü öffnet, um ein Scharnier zu
                # suchen, findet zwei Deckel und keinen Hinweis. Der Katalog
                # steht deshalb als erste Zeile darin — derselbe Befehl wie in
                # *Datei*, nur an dem Ort, an dem danach gesucht wird.
                group.addAction(self._catalog_action)
                group.addSeparator()
            # **Je Kategorie, nicht je Gruppe** (§2.6). Vorher entschied
            # ``group_is_flat`` für die ganze Gruppe: alles flach oder
            # jede Kategorie eine Ebene tiefer. Damit lagen im Menü
            # *Ändern* alle sieben Kategorien im Untermenü — auch
            # *Bohrungen* mit drei Einträgen, und damit die Bohrung, deren
            # zweiter Klick am 24.08.2026 den Umbau des Kontextmenüs
            # ausgelöst hat. Das Kontextmenü faltet seit damals nur so
            # weit, bis der Rest passt; die Leiste konnte es nicht, weil
            # die Rechnung in dieser Schicht lag und der Kern sie nicht
            # fragen darf. Sie liegt jetzt im Kern, und beide fragen sie.
            gefaltet = folded_categories(present[0].category)
            # **Erst die direkten Kategorien, dann die gefalteten.** Eine
            # Überschrift benennt alles bis zum nächsten Trennstrich — eine
            # Untermenü-Zeile dazwischen liest sich als Teil der Kategorie
            # davor. Gemessen am 27.08.2026 im Menü *Ändern*: „Transformation"
            # und „Formgebung" standen unter der Überschrift „Verbinden und
            # Abziehen", also in einem Abschnitt, zu dem sie nicht gehören.
            #
            # Den Fall gab es vorher nicht: Bis zu diesem Tag war eine Gruppe
            # ganz flach oder ganz gefaltet, und die Mischung entsteht erst mit
            # ``folded_categories``. Wer eine Zwischenebene je Kategorie
            # einführt, führt damit auch die Frage ein, wo sie im Menü steht.
            #
            # Innerhalb beider Blöcke bleibt die Reihenfolge von
            # ``MENU_GROUPS``; sie zählt von häufig nach selten auf, und genau
            # deshalb stehen die direkten vorn — was oft gebraucht wird, faltet
            # nicht.
            direct = [section for section in present if section.category not in gefaltet]
            deep = [section for section in present if section.category in gefaltet]
            for position, section in enumerate([*direct, *deep]):
                if direct and deep and position == len(direct):
                    # Ein **nackter** Trennstrich, kein benannter: Die Zeilen
                    # dahinter tragen ihre Namen selbst, und eine Überschrift
                    # bräuchte ein Wort, das es nicht gibt („Weitere"?) — samt
                    # Katalogeintrag in sechs Sprachen (Regel 20). Er schließt
                    # den letzten Abschnitt ab, und das ist seine ganze
                    # Aufgabe.
                    group.addSeparator()
                # Eine Gruppe aus einer Kategorie braucht kein Untermenü — es
                # hieße genauso wie das Menü darüber. Und eine Gruppe, die
                # ganz hineinpasst, braucht auch keines: dann ist die
                # Zwischenebene ein Klick für nichts (siehe
                # ``_fits_without_submenus``).
                target = group
                folded = section.category in gefaltet
                if not folded and len(present) > 1:
                    # **Die Kategorie behält ihren Namen, auch flach.** Hier
                    # stand ein nackter Trennstrich ab der zweiten Kategorie;
                    # er hielt sie auseinander und **benannte** sie nicht. Der
                    # Vergleich mit Fusion hat das sichtbar gemacht
                    # (27.08.2026): Dort steht der Gruppenname dauernd im Band
                    # („ERSTELLEN", „ÄNDERN"), bei uns erfuhr man ihn nur, wenn
                    # eine Zwischenebene ihn trug — also genau dann, wenn der
                    # Weg einen Klick länger war.
                    #
                    # ``addSection`` **zeigt den Namen nicht** — auf Windows
                    # ist ein Abschnitt derselbe Trennstrich wie
                    # ``addSeparator``, und der Text wird verworfen; gemessen
                    # sind Überschrift und nackter Strich punkt- und
                    # höhengleich, auch ohne jedes Stylesheet. ``menu_heading``
                    # setzt sie als Label in einer Aktion und hält sie über
                    # ``setSeparator(True)`` zugleich aus der Zeilenrechnung
                    # heraus (``tests/test_interface_limits.py``). Auch vor der ersten
                    # Kategorie: Ein Menü, dessen zweite Gruppe eine
                    # Überschrift hat und dessen erste nicht, liest sich, als
                    # gehörte der Anfang zu keiner.
                    #
                    # **Bei einer einzigen Kategorie bleibt sie weg** — dieselbe
                    # Begründung, mit der ``group_is_flat`` dort nie ein
                    # Untermenü zieht: Die Überschrift wäre ein zweiter Name
                    # für dasselbe Menü („Bausteine → Bausteine").
                    menu_heading(group, str(section.title))
                if folded:
                    # Mit dem Fenster als Elternteil erzeugt, nicht über
                    # ``addMenu(titel)``: sonst hält nichts auf der Python-Seite
                    # das Untermenü, und sein C++-Objekt wird eingesammelt,
                    # während die Leiste es noch zeigt.
                    target = QMenu(str(section.title), self)
                    target.setToolTipsVisible(True)
                    group.addMenu(target)
                    self._menus.append(target)
                subgroups: dict[str, QMenu] = {}
                for spec in section.entries:
                    if spec.name in MENU_TWINS:
                        # Zusammengelegte Zwillinge (MENU_TWINS): der B-Rep-
                        # Zwilling hat keinen eigenen Eintrag — sein Weg ist
                        # der Umschalter im Dialog des Mesh-Zwillings, und
                        # erreichbar bleibt er über Palette und Verlauf.
                        continue
                    if spec.name in variant_members():
                        # Variantengruppe (VARIANT_GROUPS): Die vier Wege aus
                        # einer Skizze stehen unter **einem** Eintrag, und die
                        # Art wählt der Dialog. Er wird unten angelegt, nach
                        # der Schleife — sein Titel gehört keiner Operation,
                        # deshalb kann er nicht hier entstehen.
                        continue
                    place = self._subgroup_for(spec, target, subgroups)
                    self._op_actions[spec.name] = self._operation_action(place, spec)
                self._add_variant_entries(section.category, target, subgroups)

        # *Automatisch teilen* ist kein Registereintrag, sondern ein Ablauf über
        # mehreren Operationen — und stand deshalb unter *Bearbeiten*, zwei
        # Menüs entfernt von den anderen Wegen, ein Teil zu trennen. Wer ein zu
        # großes Teil vor sich hat, sucht nicht nach der Bauart einer Funktion,
        # sondern nach dem Wort „teilen"; sie stehen jetzt beieinander.
        #
        # Gesucht wird über die **Kategorie** und nicht über den Menütitel:
        # Der Titel ist übersetzt und umbenennbar, und ein Vergleich darauf
        # ließe den Eintrag nach der nächsten Umbenennung still unter
        # *Bearbeiten* zurück. Gibt es die Gruppe nicht, weil keine
        # Vorbereiten-Operation registriert ist, bleibt *Bearbeiten* der Platz
        # — ein Eintrag darf umziehen, nicht verschwinden.
        prepare_group = next(
            (str(title) for title, categories in MENU_GROUPS if "prepare" in categories), ""
        )
        prepare_menu = groups.get(prepare_group, edit_menu)
        if prepare_menu is not edit_menu:
            prepare_menu.addSeparator()
        self.auto_split_action = self._add_action(
            prepare_menu,
            tr("Automatisch teilen …"),
            None,
            self.action_auto_split,
            tr(
                "Ein zu großes Teil zerschneiden, bis jedes Stück auf das Bett passt — "
                "mit Passstiften in jeder Schnittfläche."
            ),
            symbol="split",
        )

        # Was das Register kennt und diese Tabelle nicht, bekommt sein eigenes
        # Menü: eine neue Kategorie soll auftauchen, nicht verschwinden.
        grouped = {name for _title, names in MENU_GROUPS for name in names}
        for section in menu_tree(skip=own):
            if section.category in grouped:
                continue
            menu = self._menu(str(section.title))
            self._workspace_menus.append(menu)
            for spec in section.entries:
                self._op_actions[spec.name] = self._operation_action(menu, spec)

        view_menu = self._menu(tr("Ansicht"))
        # Festgehalten, weil das Merkmalsfenster seinen Ein-/Ausschalter
        # später dort einhängt — es entsteht erst mit dem Zentrum.
        self._view_menu = view_menu
        self._workspace_menus.append(view_menu)
        # **Gehört zu den Darstellungseinträgen**, obwohl er nicht in ihrem
        # Untermenü steht: Er teilt ihr Problem. „Pos1" ist fensterweit
        # gebunden, die Zeichenfläche hat dieselbe Taste für ihr Einpassen
        # (``VIEW_KEYS['fit']``) — und zwei aktive Kürzel auf einer Taste
        # lassen Qt **keines** von beiden feuern. Gemessen: sechs Drücke mit
        # Fokus auf der Zeichenfläche, null Aufrufe von ``fit_view``, zwei
        # ``activatedAmbiguously``. Versprochen wird die Taste zweimal, im
        # Tooltip des Knopfes und im Handbuch — derselbe Fall wie bei Escape,
        # und dieselbe Lösung: im Skizzenmodus gehört sie dem Blatt.
        self._display_actions.append(
            self._add_action(
                view_menu,
                tr("Einpassen"),
                "Home",
                self.viewport.reset_camera,
                tr("Rückt die Kamera auf den gewählten Körper — ohne Auswahl auf die ganze Szene."),
                symbol="fit",
            )
        )
        self._add_action(
            view_menu,
            tr("Rechten Bereich zeigen"),
            "F9",
            self.action_toggle_right,
            tr("Verlauf, Parameter und Chat ein- oder ausblenden."),
        )
        # Robert, 02.09.2026: „eine Option, wo man schnell hinkommt, um die
        # Druckplatte auszublenden". Ein Haken mit Kürzel, in der Palette
        # gelistet, und der Zustand bleibt über den Neustart.
        self._bed_action = self._add_action(
            view_menu,
            tr("Druckplatte zeigen"),
            "Ctrl+Shift+D",
            self.action_toggle_bed,
            tr("Bett, Bauraum und Maßstab ein- oder ausblenden — das Teil bleibt."),
        )
        self._bed_action.setCheckable(True)
        self._bed_action.setChecked(self.settings.bed_visible)
        view_menu.addSeparator()

        # Sechs Blöcke ohne Überschrift waren dreiundzwanzig Zeilen, durch
        # Trennstriche gegliedert — eine Liste, die man absucht (Konzept P15
        # §5). Was zusammengehört, bekommt jetzt seinen Namen und seine Ebene.
        display_menu = self._submenu(view_menu, tr("Darstellung"))
        # **Die drei Gruppen tragen Häkchen, und ihre Wahl wird gemerkt.**
        # Vorher waren es zwölf Einträge ohne Zustand: Man sah nicht, welcher
        # gilt, und beim nächsten Start galt wieder die Vorgabe. Wer
        # *Transparent* eingestellt hatte, hielt das für seine eigene
        # Erinnerung (Robert, 03.09.2026).
        self._mode_group = QActionGroup(self)
        self._mode_group.setExclusive(True)
        for mode, label, shortcut, hint in (
            ("solid", tr("Massiv"), "1", tr("Die Oberfläche, wie sie gedruckt wird.")),
            (
                "solid_edges",
                tr("Massiv mit Kanten"),
                "2",
                tr("Dazu die Dreieckskanten — zeigt, wie fein das Netz ist."),
            ),
            (
                "wireframe",
                tr("Drahtgitter"),
                "3",
                tr("Nur die Kanten. Lässt durch das Teil hindurchsehen."),
            ),
            (
                "transparent",
                tr("Transparent"),
                "4",
                tr("Durchscheinend — für Hohlräume und Teile, die ineinandergreifen."),
            ),
        ):
            action = self._add_action(
                display_menu,
                label,
                shortcut,
                weak_slot(self, lambda view, key: view.action_display_mode(key), mode),
                hint,
            )
            action.setCheckable(True)
            action.setChecked(mode == self.settings.display_mode)
            action.setData(mode)
            self._mode_group.addAction(action)
            self._display_actions.append(action)
        display_menu.addSeparator()
        self._shading_group = QActionGroup(self)
        self._shading_group.setExclusive(True)
        for shading, label, hint in (
            (
                "flat",
                tr("Flache Schattierung"),
                tr("Jedes Dreieck für sich — die wahre Form, Facetten inklusive."),
            ),
            (
                "smooth",
                tr("Weiche Schattierung"),
                tr("Über die Kanten hinweg gemittelt. Schöner, aber beschönigend."),
            ),
        ):
            action = self._add_action(
                display_menu,
                label,
                None,
                weak_slot(self, lambda view, key: view.action_shading(key), shading),
                hint,
            )
            action.setCheckable(True)
            action.setChecked(shading == self.settings.shading)
            action.setData(shading)
            self._shading_group.addAction(action)
            self._display_actions.append(action)
        display_menu.addSeparator()
        self._projection_group = QActionGroup(self)
        self._projection_group.setExclusive(True)
        for projection, label, shortcut, hint in (
            (
                "perspective",
                tr("Perspektivisch"),
                "5",
                tr("Wie das Auge sieht: Fernes wird kleiner."),
            ),
            (
                "orthographic",
                tr("Orthografisch"),
                "6",
                tr("Ohne Fluchtpunkt — gleich lange Kanten sehen gleich lang aus. Zum Messen."),
            ),
        ):
            action = self._add_action(
                display_menu,
                label,
                shortcut,
                weak_slot(self, lambda view, key: view.action_projection(key), projection),
                hint,
            )
            action.setCheckable(True)
            action.setChecked(projection == self.settings.projection)
            action.setData(projection)
            self._projection_group.addAction(action)
            self._display_actions.append(action)

        camera_menu = self._submenu(view_menu, tr("Kamera"))
        standpoint = tr("Kamera auf diesen Standpunkt setzen.")
        for name, label, shortcut in (
            ("iso", tr("Isometrisch"), "Ctrl+0"),
            ("front", tr("Vorne"), "Ctrl+1"),
            ("back", tr("Hinten"), "Ctrl+2"),
            ("left", tr("Links"), "Ctrl+3"),
            ("right", tr("Rechts"), "Ctrl+4"),
            ("top", tr("Oben"), "Ctrl+5"),
            ("bottom", tr("Unten"), "Ctrl+6"),
        ):
            self._add_action(
                camera_menu,
                label,
                shortcut,
                weak_slot(self, lambda view, key: view.viewport.view_from(key), name),
                standpoint,
            )
        view_menu.addSeparator()
        # Vier Navigationsschemata und zwei Themen, und keines sagte, welches
        # gerade gilt. Wer die Vorgabe einmal umgestellt hat, konnte danach nur
        # ausprobieren, worauf sie steht.
        theme_menu = self._submenu(view_menu, tr("Thema"))
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        for theme, hint in (
            ("dark", tr("Helle Geometrie auf dunklem Grund.")),
            ("light", tr("Dunkle Geometrie auf hellem Grund.")),
        ):
            action = self._add_action(
                theme_menu,
                str(THEMES[theme]),
                None,
                weak_slot(self, lambda view, key: view.action_theme(key), theme),
                hint,
            )
            action.setCheckable(True)
            action.setChecked(theme == self.settings.theme)
            action.setData(theme)
            self._theme_group.addAction(action)

        navigation_menu = self._submenu(view_menu, tr("Navigation"))
        self._navigation_group = QActionGroup(self)
        self._navigation_group.setExclusive(True)
        # **Die Mitgliedschaft kommt aus dem Katalog, nicht aus einer Liste
        # hier.** Sie stand hier als vierte Aufzählung derselben Schemata, und
        # sie ist genau so auseinandergelaufen: Das Schema ``solidon`` kam
        # dazu und wurde zugleich Vorgabe, stand aber nicht in dieser Liste —
        # womit **kein** Eintrag angehakt war und das Menü dem Kunden sagte,
        # es sei keine Steuerung aktiv, während er mit der neuen fuhr
        # (gefunden von 3d-druck-06, gemeldet von 3d-druck-85, 03.09.2026).
        #
        # Über ``NAVIGATION`` gelesen kann das nicht wieder passieren: Ein
        # sechstes Schema steht ohne Zutun im Menü. Fehlt ihm der Hinweissatz
        # unten, bleibt der Statustext leer — sichtbar zu wenig, aber nicht
        # falsch. Die Reihenfolge ist die des Katalogs, und dort steht die
        # Vorgabe vorn.
        hints = {
            "solidon": tr("Links verschiebt, rechts dreht, das gedrückte Rad kippt; WASD fliegt."),
            # Der Hinweis stand hier andersherum, als das Schema arbeitet:
            # „links drehen, rechts schieben" beschreibt Bambu und Prusa,
            # nicht die Vorgabe aus §2.9.
            "slicer": tr("Links wählt, rechts dreht, Umschalt und Ziehen schiebt."),
            "orbit": tr("Links dreht, rechts schiebt — die verbreitetste Aufteilung."),
            "cad": tr("Mittlere Taste dreht, mit Umschalt schiebt sie; rechts zoomt."),
            "blender": tr("Links wählt, mittlere Taste dreht, Umschalt und Mitte schiebt."),
        }
        for scheme in NAVIGATION:
            hint = hints.get(scheme, "")
            action = self._add_action(
                navigation_menu,
                str(NAVIGATION[scheme]),
                None,
                weak_slot(self, lambda view, key: view.action_navigation(key), scheme),
                hint,
            )
            action.setCheckable(True)
            action.setChecked(scheme == self.settings.navigation)
            action.setData(scheme)
            self._navigation_group.addAction(action)

        help_menu = self._menu(tr("Hilfe"))
        self._add_action(
            help_menu,
            tr("Handbuch …"),
            QKeySequence.StandardKey.HelpContents,
            self.action_manual,
            tr("Jede Operation mit ihren Werten, nach Bereichen sortiert."),
            symbol="manual",
        )
        self._add_action(
            help_menu,
            tr("Beispiele"),
            None,
            self.action_examples,
            tr("Die Beispielprojekte mit ihren Touren — sie stehen auf dem Startbildschirm."),
        )
        help_menu.addSeparator()
        self._add_action(
            help_menu,
            tr("Zusätzliche Programme …"),
            None,
            self.action_install_extras,
            tr("Was Solidon außerdem benutzen kann, wo es liegt und wie es dazukommt."),
        )
        self._add_action(
            help_menu,
            tr("Tastenkürzel …"),
            "?",
            self.action_shortcuts,
            tr("Alle belegten Tasten, erzeugt aus dem Register — nie veraltet."),
        )
        self._add_action(
            help_menu,
            tr("Erste Schritte …"),
            None,
            self.action_first_run,
            tr("Sprache, Drucker, Filamente und die externen Programme noch einmal einstellen."),
        )
        self._add_action(
            help_menu,
            tr("Rückmeldung senden …"),
            None,
            self.action_feedback,
            tr("Vorschlag, Fehler oder Frage an den Support — auf Wunsch mit Bild und Sitzung."),
        )
        help_menu.addSeparator()
        self._add_action(
            help_menu,
            tr("Nach einer neuen Version sehen"),
            None,
            self.action_check_updates,
            tr(
                "Fragt einmal bei solidon3d.de nach. Geladen und installiert wird "
                "erst auf Ihre Bestätigung."
            ),
        )
        # Daneben und nicht woanders: Wer wissen will, ob es etwas Neues gibt,
        # will oft auch wissen, was das Letzte gebracht hat. Der Verlauf liegt
        # im Paket — dieser Eintrag fragt nichts nach draußen.
        self._add_action(
            help_menu,
            tr("Neuerungen …"),
            None,
            self.action_changes,
            tr("Was sich in dieser und den vorigen Versionen geändert hat."),
        )
        help_menu.addSeparator()
        self._add_action(
            help_menu,
            tr("Solidon freischalten …"),
            None,
            self.action_activate,
            tr("Testzeitraum, Lizenzschlüssel eintragen, und was nach Ablauf offen bleibt."),
        )
        self._add_action(
            help_menu,
            tr("{app} unterstützen …").format(app=APP_NAME),
            None,
            self.action_donate,
            tr("Die Weiterentwicklung, Tests und die nächste Version freiwillig mitfinanzieren."),
        )
        self._add_action(
            help_menu,
            tr("Über Solidon"),
            None,
            self.action_about,
            tr("Version, Rechteinhaber und die verwendeten Fremdbibliotheken."),
            symbol="about",
        )

        toolbar = QToolBar(tr("Werkzeuge"), self)
        self.toolbar = toolbar
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        # Zeichen **und** Wörter: Blatt, Ordner und Diskette sind vertraut,
        # Zeichnen, Formen und Skelett nicht. Gerade diese drei tragen die
        # Hauptwege für neue Nutzer. Eine Leiste, deren Namen erst am Zeiger
        # erscheinen, ist für sie eine Bilderprüfung. Text neben dem Zeichen
        # bleibt eine Zeile hoch; auf schmalen Fenstern sammelt Qt den
        # Überstand wie bei jeder Werkzeugleiste im Pfeilmenü ein.
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        # **Und wenn der Platz nicht reicht, kürzen sie, statt zu
        # verschwinden** (Befund D6). Qt sammelt den Überstand einer
        # Werkzeugleiste hinter einem unbeschrifteten Pfeil ein — was dort
        # landet, ist für den Kunden weg. Gemessen an einem geöffneten
        # Projekt wünschte diese Leiste 2283 Pixel; auf einem 1920er
        # Bildschirm fiel die ganze Kopfzeile hinein, also Projektname, Maße,
        # Druckplatte, Drucker und Material zusammen. Bei leerem Projekt
        # passierte das nicht, und deshalb fällt es beim Ausprobieren nicht
        # auf. Ein Zeichen ohne Wort ist eine schwächere Auskunft als beides;
        # gar keins ist keine. :meth:`_fit_toolbar` entscheidet das bei jeder
        # Größenänderung neu.
        self._toolbar_wide = True
        #: Wie breit die Leiste mit Wörtern zuletzt sein wollte — die Marke,
        #: gegen die zurückgeschaltet wird. Ohne sie misst die Hysterese ihre
        #: eigene Wirkung und schwingt.
        self._toolbar_full_width = 0
        # Vier der sieben haben ein Menüpendant; von ihm kommen Satz und
        # Kürzel (``source``). Die drei anderen gibt es nur hier und tragen
        # ihren Satz selbst.
        for symbol, label, slot, source, own_hint in (
            ("new", tr("Neues Projekt"), self.action_new, self.new_action, ""),
            ("open", tr("Öffnen"), self.action_open, self.open_action, ""),
            ("save", tr("Speichern"), self.action_save, self.save_action, ""),
            ("import", tr("Modell einfügen"), self.action_import, self.import_action, ""),
            # Weg 2 aus §2.2 bekommt seinen vorgesehenen Platz: die
            # Hauptwege-Tabelle nennt für „neu konstruieren" ausdrücklich die
            # Werkzeugzeile — belegt war er nie, und das Zeichnen lag drei
            # Ebenen tief im Menü. Erst zeichnen, die Erzeugungsart kommt bei
            # „Fertig".
            (
                "category.sketch",
                tr("Zeichnen"),
                self.action_sketch_free,
                None,
                tr("Ein Profil zeichnen; was daraus wird, fragt der Dialog bei „Fertig“."),
            ),
            # Und Weg 4 daneben. Beide lagen unter *Ändern → Netz* zwischen
            # Reparaturwerkzeugen, ohne Kürzel — die Hauptwege-Tabelle nennt
            # für „organisch formen" die Werkzeugzeile, und die untere ist mit
            # acht Umschaltern voll. Der Menüeintrag bleibt, wo er war: Palette
            # und Verlauf führen über ihn.
            (
                "sculpt",
                tr("Formen"),
                self.action_sculpt_free,
                None,
                tr("Einen gewählten Körper mit dem Pinsel auf- und abtragen."),
            ),
            (
                "armature",
                tr("Skelett"),
                self.action_armature_free,
                None,
                tr("Knochen in einen gewählten Körper setzen und ihn danach beugen."),
            ),
        ):
            if symbol in ("import", "sculpt"):
                toolbar.addSeparator()
            action = QAction(icon(symbol, toolbar), label, self)
            action.triggered.connect(slot)
            # Ohne Beschriftung am Knopf ist der Tooltip die Stelle, an der
            # Name, Kürzel und Zweck gelesen werden; dieselbe Angabe gehört in
            # die Statusleiste (§2 C). Der ``statusTip`` ist zugleich das,
            # woraus ``_lock_hint`` den eigenen Hinweis wiederherstellt — ohne
            # ihn bliebe der Knopf nach dem Freischalten stumm.
            tip = self._button_tip(label, source, own_hint)
            action.setToolTip(tip)
            action.setStatusTip(tip)
            action.setProperty("wordless", False)
            toolbar.addAction(action)
            if symbol == "import":
                # Vier Knöpfe der Zeile lösen Transaktionen aus — nach Ablauf
                # des Testlaufs grauen sie mit den Menüs aus (§2 C).
                self._toolbar_import = action
            if symbol == "category.sketch":
                self._toolbar_sketch = action
            if symbol == "sculpt":
                self._toolbar_sculpt = action
            if symbol == "armature":
                self._toolbar_armature = action

        # Rechts neben den sieben Knöpfen stand die halbe Leiste leer. Dort
        # steht jetzt, was das Projekt gerade ist und worauf es gedruckt wird —
        # Angaben, die jede Toleranz im Stapel bestimmen (§12) und für die man
        # bisher einen Dialog öffnen musste.
        toolbar.addSeparator()
        self.header = HeaderBar(toolbar)
        self.header.plateChanged.connect(self.viewport.set_plate)
        toolbar.addWidget(self.header)

    def _menu(self, title: str) -> QMenu:
        """Ein Menü der Leiste — festgehalten, damit es nicht eingesammelt wird."""
        menu = self.menuBar().addMenu(title)
        menu.setToolTipsVisible(True)
        self._menus.append(menu)
        return menu

    def _submenu(self, parent: QMenu, title: str) -> QMenu:
        """Eine Zwischenebene. Elternteil ist das Fenster, nicht das Menü —
        sonst hält nichts auf der Python-Seite das Untermenü fest, und sein
        C++-Objekt wird eingesammelt, während die Leiste es noch zeigt.
        """
        submenu = QMenu(title, self)
        submenu.setToolTipsVisible(True)
        parent.addMenu(submenu)
        self._menus.append(submenu)
        return submenu

    def _subgroup_for(self, spec: OperationSpec, menu: QMenu, made: dict[str, QMenu]) -> QMenu:
        """Das Menü, in das dieser Eintrag gehört — mit einer Zwischenebene,
        wo die Kategorie sonst zu lang würde (Konzept P15 §5).

        Betrifft heute die Bausteine: sechzehn Einfügungen flach untereinander
        sind eine Liste, die man absucht, kein Menü, das man liest. Die
        Gliederung ist nicht erfunden — es ist dieselbe Gruppe, nach der der
        Katalog seine Kacheln ordnet (``parts.GROUPS``). Was keine Gruppe hat,
        bleibt oben stehen: ``create_lid`` ist kein Baustein aus der
        Bibliothek.
        """
        from app.core.knowledge.parts import GROUPS, PARTS
        from app.core.knowledge.parts.ops import op_name

        group = next(
            (part.group for part in PARTS.all() if op_name(part.name) == spec.name),
            None,
        )
        if group is None or group not in GROUPS:
            return menu
        if group not in made:
            # Elternteil ist das Fenster, nicht das Menü — siehe die
            # Begründung eine Ebene höher.
            submenu = QMenu(str(GROUPS[group]), self)
            submenu.setToolTipsVisible(True)
            menu.addMenu(submenu)
            self._menus.append(submenu)
            made[group] = submenu
        return made[group]

    def _operation_action(self, menu: Any, spec: OperationSpec) -> QAction:
        """Ein Menüeintrag für eine Operation, überall gleich gebaut."""
        action = QAction(icon(icon_name_for(spec), self), str(spec.title), self)
        key = shortcut_for(spec.name, spec.shortcut, self.settings.shortcut_scheme)
        if key:
            action.setShortcut(QKeySequence(key))
            self._scope_shortcut(action, key)
        # Die Statuszeile bekommt den Satz, der Tooltip den Satz **und** die
        # Grenze. Zwölf Operationen tragen einen ``caveat``, und gelesen hat
        # ihn allein das Handbuch — also niemand in dem Augenblick, in dem er
        # zählt. In die Statuszeile passt er nicht: die ist eine Zeile, und
        # abgeschnitten wäre eine Warnung schlimmer als keine.
        action.setStatusTip(str(spec.doc))
        warning = caveat_line(spec)
        action.setToolTip(f"{spec.doc}\n\n{warning}" if warning else str(spec.doc))
        action.triggered.connect(
            weak_slot(self, lambda view, entry: view.launch_operation(entry), spec)
        )
        menu.addAction(action)
        return action

    def launch_operation(self, spec: OperationSpec) -> None:
        """Der eine Einstieg für Menü, Palette und jeden künftigen Weg.

        Eine Operation mit Gestenfeld führt in ihren Editor statt in einen
        Dialog mit einem Feld, das man erst aufklappen muss (§30.1 Stufe
        zwei): Wer „Formen" wählt, will den Pinsel und keine Strichliste,
        wer „Stellung geben" wählt, die Knochen und keine Koordinaten. Die
        Verzweigung stand nur im Menüaufbau — die Palette rief
        ``run_operation`` direkt, und „Formen" über Strg+Umschalt+P endete
        in einem Rohdialog: die Operation lief, veränderte nichts und
        hinterließ einen leeren Schritt im Verlauf.
        """
        if _has_sketch_param(spec):
            self.start_sketch(spec.name)
        elif _has_armature_param(spec):
            self.start_armature()
        elif _has_stroke_param(spec):
            self.start_sculpt()
        else:
            self.run_operation(spec)

    #: Kürzel, die eine Taste ohne Zusatztaste sind und deshalb nur dort
    #: gelten dürfen, wo eine Objektauswahl sichtbar ist.
    _BARE_KEYS = frozenset({"Del", "Delete"})

    def _scope_shortcut(self, action: QAction, key: str) -> None:
        """Begrenzt nackte Tasten auf Objektbaum und Ansicht.

        „Entf" war fensterweit gebunden und löschte deshalb den ausgewählten
        Körper, auch wenn der Fokus im Verlauf lag und ein Schritt markiert war
        — man drückt die Taste in der Erwartung, den Schritt loszuwerden, und
        verliert das Teil. Rücknehmbar, aber genau die Art Überraschung, die
        Vertrauen kostet.

        Kürzel mit Zusatztaste bleiben, wo sie waren: Strg+B ist eindeutig
        gemeint, egal worauf der Fokus steht.
        """
        if key not in self._BARE_KEYS:
            return
        action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        for widget in (self.object_tree, self.viewport):
            widget.addAction(action)

    def _add_variant_entries(self, category: str, target: Any, subgroups: dict[str, QMenu]) -> None:
        """Für jede Variantengruppe dieser Kategorie **einen** Eintrag.

        Der Titel gehört keiner Operation, deshalb entsteht er nicht in der
        Schleife darüber — dort steht je ein `OperationSpec`. Angelegt wird er
        wie *Automatisch teilen*: ein Menüeintrag über einem Ablauf, nicht über
        einem Registereintrag.

        **Das Kürzel wandert mit.** ``sketch_extrude`` trug „E"; nach dem
        Zusammenlegen hat es keinen eigenen Eintrag mehr, an dem eine
        ``QAction`` hinge. Anders als bei ``shell_exact`` (dort ist es
        entfallen) bleibt es hier erhalten und sitzt am Sammeleintrag: Der
        öffnet ohnehin mit der ersten Variante, also mit Extrudieren. Wer „E"
        gewohnt ist, bekommt denselben Dialog wie vorher — nur mit einer Wahl
        darin.
        """
        for group in VARIANT_GROUPS:
            first = REGISTRY.get(group.members[0])
            if first.category != category:
                continue
            place = self._subgroup_for(first, target, subgroups)
            key = shortcut_for(first.name, first.shortcut, self.settings.shortcut_scheme)
            action = self._add_action(
                place,
                str(group.title),
                key or None,
                weak_slot(self, MainWindow.run_operation, first),
                str(group.doc),
                # Die Gruppe hat kein eigenes Zeichen, ihre Mitglieder schon —
                # und der Dialog öffnet mit dem ersten. Ohne das stand sie als
                # einzige Lücke in der Symbolspalte von *Erzeugen*.
                symbol=icon_name_for(first),
            )
            if key:
                self._scope_shortcut(action, key)
            self._variant_actions[group.members[0]] = action

    def _add_action(
        self,
        menu: Any,
        label: str,
        shortcut: Any,
        slot: Any,
        hint: str = "",
        symbol: str = "",
    ) -> QAction:
        """Ein Menüeintrag mit dem Satz, der sagt, was er tut.

        Der Hinweis steht an zwei Stellen, weil ihn zwei Arten von Leuten
        suchen: in der Statusleiste, wo er beim Durchgehen mitläuft, und als
        Tooltip, wo er beim Zögern erscheint. Ohne beides ist ein Menü mit
        vierzehn Einträgen eine Liste von Vermutungen.

        ``symbol`` ist für die Einträge, die **keine** Registeroperation sind
        und deshalb nicht über :func:`icon_name_for` an ihr Zeichen kommen.
        Drei gab es davon, alle drei in Menüs, deren übrige Zeilen eines
        tragen: *Aus Skizze erzeugen*, *Automatisch teilen* und
        *Bausteinkatalog* standen als Lücke in einer Symbolspalte.
        """
        action = QAction(label, self)
        if symbol:
            action.setIcon(icon(symbol, self))
        if shortcut is not None:
            action.setShortcut(
                shortcut
                if isinstance(shortcut, QKeySequence.StandardKey)
                else QKeySequence(shortcut)
            )
        if hint:
            action.setStatusTip(hint)
            action.setToolTip(hint)
        # ``triggered`` trägt ein ``bool``; drei Slots mit optionalem
        # Parameter bekamen es als Wert (``action_manual(False)``) und
        # überlebten nur, weil ihre Rümpfe gegen Falschheit prüfen. Das
        # Argument endet hier — ein Menüeintrag ruft, er übergibt nichts.
        #
        # Über ``weak_slot``, nicht über ein Lambda: Qt hält eine gebundene
        # Methode schwach, ein Lambda mit ``call=slot`` dagegen stark — 41
        # Menüeinträge hielten so jedes Fenster fest, zehn von zehn
        # überlebten ihr Loslassen. Was nicht gebunden ist (die
        # ``weak_slot``-Aufrufstellen der Schleifen), hält niemanden und
        # verwirft das ``checked`` selbst.
        if inspect.ismethod(slot):
            slot = weak_slot(cast(QObject, slot.__self__), slot.__func__)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _update_actions(self) -> None:
        """Was jetzt geht, sieht man, statt es zu erfahren (§2.6).

        Vorher war jeder der siebzig Einträge immer anklickbar, auch bei leerer
        Szene; wer einen wählte, bekam ein modales Fenster mit dem Hinweis, dass
        er vorher etwas hätte auswählen sollen. Eine Sackgasse als Antwort auf
        eine Frage, die das Menü selbst beantworten kann.
        """
        result = self.session.last_result
        objects = len(result.scene.objects) if result else 0
        chosen = len(self.object_tree.selected_objects())
        # **Im Skizzenmodus ist keine Operation dran.** Das ist nicht nur
        # inhaltlich richtig — es ist die Bedingung dafür, dass die
        # Zeichenkürzel überhaupt ankommen: `R` und `C` liegen im
        # Fusion-Schema auf Drehen und Fasen, und Qt lässt bei zwei aktiven
        # Kürzeln derselben Taste **keines** von beiden feuern. Fusion macht
        # es genauso: im Skizzenmodus gilt der Zeichensatz.
        drawing = self._sketch_panel is not None
        # **Und in einer Form- oder Skelettsitzung genauso.** Beide sammeln
        # Gesten für die eine Operation, die gerade entsteht — wer währenddessen
        # „Objekt entfernen" traf, malte danach stumm ins Leere, und *Fertig*
        # verlor die Züge mit einer Meldung über einen Wert, den es nicht gab.
        gesturing = drawing or self.sculpting() or self.setting_armature()
        # §2 C: nach Ablauf des Testlaufs graut die schreibende Seite aus —
        # vor dem Klick, mit Grund im Hinweistext. Die Hürde selbst liegt im
        # Kern; das hier ist die Freundlichkeit davor.
        locked = not activation.state().unlocked
        # Ein offener Editor sammelt gerade Gesten für genau eine Operation.
        # Einen älteren Schritt darunter zu löschen würde seinen Vorschauzustand
        # entwerten; außerdem trägt der Skizzeneditor selbst Entf. Deshalb gilt
        # hier dieselbe Sperre wie für alle anderen schreibenden Aktionen.
        self.history_panel.remove_action.setEnabled(not locked and not gesturing)

        # Welcher Bauart die Auswahl ist — das Menü fragte bisher nur, wie
        # viele Objekte darin liegen. „Verrunden" war damit bei einem Netz
        # anklickbar, und der Satz „Der gewählte Körper ist ein Netz" kam erst
        # nach dem ausgefüllten Dialog (Regel 19: keine Sackgassen).
        kinds = self._kinds_of_selection(result)

        for name, action in self._op_actions.items():
            spec = REGISTRY.get(name)
            # **Ein Grund, und beide Seiten folgen ihm.** Hier stand die
            # Bedingung ein zweites Mal, von Hand nachgebaut — Bauart und
            # Anzahl, aber nicht das Merkmal. ``_reason_locked`` prüft alle
            # drei und belieferte bisher nur den Hinweistext: *Bohrung ändern*
            # war an einem Körper ohne Bohrung anklickbar, während sein
            # eigener Tooltip „Dafür braucht es eine erkannte Bohrung am
            # gewählten Teil." sagte. Gemessen an einer eingelesenen STEP-Datei
            # mit 302 Merkmalen und null Bohrungen: Dialog geht auf,
            # ``at_feature`` steht auf einer **Unterseite**, Übernehmen ist
            # frei, und die Absage steht danach im Prüfbericht — die Sackgasse
            # aus Regel 19, die dieselbe Schleife bei den Operationen des
            # exakten Kerns seit je vermeidet.
            reason = (
                None if locked or gesturing else self._reason_locked(spec, kinds, objects, chosen)
            )
            action.setEnabled(not locked and not gesturing and reason is None)
            self._lock_hint(action, locked)
            self._kind_hint(action, reason, locked)

        # Dieselbe Regel für die Werkzeugzeile unten. Sie stand dem Anfänger
        # näher als jedes Menü und bot auf einer leeren Szene weiter Messen,
        # Bewegen, Analyse und Schichten an — jedes davon braucht einen
        # Körper, und keines sagte das.
        self.tools.set_usable(
            objects > 0 and not gesturing,
            str(_NEEDS_BODY),
        )

        # Rückgängig und Wiederholen bleiben nach Ablauf offen (§2 C): wer
        # nichts mehr ändern kann, darf trotzdem zurück und wieder vor.
        #
        # Im Skizzenmodus aber nicht: dort meint Strg+Z den letzten Zug auf
        # dem Blatt und nicht den letzten Schritt im Verlauf. Beide Kürzel
        # gleichzeitig aktiv zu lassen wäre die schlechtere Hälfte der Wahl —
        # Qt lässt bei zwei aktiven Belegungen derselben Taste **keine**
        # feuern, dieselbe Falle wie bei R und C oben.
        # `gesturing`, nicht nur `drawing`: auch die Formsitzung belegt
        # Strg+Z mit ihrem eigenen Zug-Rückgängig (P16.6).
        self.undo_action.setEnabled(self.session.history.can_undo and not gesturing)
        self.redo_action.setEnabled(self.session.history.can_redo and not gesturing)
        # Und die Darstellung. **Von den zwei Gründen dafür gilt seit dem
        # Schnitt (§30.1, P4) nur noch einer.** Der erste — „im Skizzenmodus
        # liegt der Viewport nicht im Stapel, sie ändern also etwas, das
        # niemand sieht" — ist weggefallen: Die Ansicht steht jetzt, und eine
        # Darstellung zu wechseln wäre dort sichtbar.
        #
        # Der zweite trägt weiter: Ihre Kürzel sind die Ziffern 1 bis 6, und
        # dort liegt im Skizzenmodus der Ebenenwechsel. Qt lässt bei zwei
        # aktiven Kürzeln derselben Taste **keines** von beiden feuern — die
        # Zeichenfläche verspricht die Taste sichtbar am Ebenenfeld, und
        # gedrückt geschähe nichts.
        #
        # Die Kamera ist davon nicht betroffen und war es nie: *Draufsicht*
        # und *Seitenansicht* liegen auf Strg+1 bis Strg+6 und blieben immer
        # bedienbar. Dass sie nichts bewirkten, lag allein am getauschten
        # Stapel — seit er steht, wirken sie ohne eine Zeile Änderung.
        for action in self._display_actions:
            action.setEnabled(not drawing)
        # Dieselbe Regel für die zwei Einträge, die keine Operationen sind und
        # trotzdem einen Körper brauchen: ausgegraut statt einer modalen
        # Sackgasse nach dem Klick.
        self.auto_split_action.setEnabled(chosen >= 1 and not locked and not gesturing)
        self.variants_action.setEnabled(objects > 0 and not locked and not gesturing)
        self.export_action.setEnabled(objects > 0 and not locked and self._export_worker is None)

        # Und jeder der fünf sagt, was ihm fehlt. Die Reihenfolge der Gründe
        # ist die der Bedingungen darüber: Was zuerst zutrifft, wird genannt.
        gesture_note = tr("Solange gezeichnet oder geformt wird, gilt die Taste dem Werkzeug.")
        needs_body = str(_NEEDS_BODY)
        self._say_why(
            self.undo_action,
            gesture_note if gesturing else tr("Es ist kein Schritt da, der zurückgehen könnte."),
        )
        self._say_why(
            self.redo_action,
            gesture_note
            if gesturing
            else tr("Es wurde nichts zurückgenommen, das wieder gelten könnte."),
        )
        self._say_why(
            self.auto_split_action,
            gesture_note if gesturing else tr("Dafür muss ein Körper ausgewählt sein."),
        )
        self._say_why(self.variants_action, gesture_note if gesturing else needs_body)
        self._say_why(
            self.export_action,
            tr("Es wird gerade exportiert.") if self._export_worker is not None else needs_body,
        )
        self.import_action.setEnabled(not locked)
        self.generate_action.setEnabled(not locked)
        self._toolbar_import.setEnabled(not locked)
        self._toolbar_sketch.setEnabled(not locked)
        # Formen und Skelett gehen beide von einem gewählten Körper aus. Das
        # fing bisher erst die Sitzung selbst ab — eine Meldung nach dem Klick,
        # wo der Knopf sie vorher sagen kann (§2.6).
        ready = chosen >= 1 and not locked and not gesturing
        self._toolbar_sculpt.setEnabled(ready)
        self._toolbar_armature.setEnabled(ready)
        for action in (
            self.auto_split_action,
            self.variants_action,
            self.export_action,
            self.import_action,
            self.generate_action,
            self._toolbar_import,
            self._toolbar_sketch,
            self._toolbar_sculpt,
            self._toolbar_armature,
        ):
            self._lock_hint(action, locked)
        for action in (self._toolbar_sculpt, self._toolbar_armature):
            self._pick_hint(action, ready, locked)
        self._hide_dead_menus()

    def _hide_dead_menus(self) -> None:
        """Ein Menü, in dem **kein** Eintrag geht, tritt beiseite.

        **Robert am 23.08.2026:** „wenn man kein 3d modell ausgewählt hat
        bringen menüs wie bohrung anlegen nichts, hier ausblenden" — und auf
        die Rückfrage: „ausblenden wenn es nicht sinnvoll ist".

        Gemessen auf der leeren Szene, bevor gebaut wurde:

            Objekt         0 von  5 bedienbar
            Ändern         0 von 34
            Bausteine      0 von 20
            Vorbereiten    0 von 10

        **Neunundsechzig gesperrte Zeilen in vier Menüs**, und die Erklärung
        dazu sieht nur, wer mit der Maus darüberfährt. Mit einem gewählten
        Körper sind alle vier vollständig nutzbar — das Menü ist also nicht
        kaputt, es kommt nur zu früh.

        **Die Grenze läuft am Menü, nicht am Eintrag, und das ist der ganze
        Schnitt.** Ein Menü, in dem jeder Eintrag gesperrt ist, erklärt nichts —
        es ist Lärm. Ein Menü mit gemischtem Inhalt behält seine grauen Zeilen
        samt Grund (:meth:`_kind_hint`), denn dort steht die Erklärung **neben
        einem Eintrag, der geht**, und dieser Vergleich sagt mehr als das
        Verschwinden.

        Was ausdrücklich bleibt: die Werkzeugzeile unten. Sie nennt den Grund
        im Klartext („Dafür braucht es einen Körper in der Szene.") und ist die
        Stelle, an der ein Anfänger zuerst hinsieht — dort wäre Ausblenden der
        Verlust der einzigen Auskunft.

        **Und nur bei leerer Szene**, das ist die zweite Hälfte der Grenze und
        die teurer erkaufte. Der erste Bau blendete auch dann aus, wenn ein
        Körper dalag und bloß niemand ihn angeklickt hatte —
        ``test_the_start_screen_shows_only_menus_that_do_something_there`` fiel
        darauf, und zu Recht: Wer eine Datei geöffnet hat, **sieht** sein Teil.
        Ihm fehlt ein Klick, nicht ein Modell. Ein Menü, das dabei verschwindet
        und beim Anklicken wiederkäme, ließe die Leiste bei jeder Auswahl
        flackern — eine Oberfläche, die sich unter dem Kunden bewegt, ist
        schlimmer als eine graue Zeile, die ihren Grund nennt.

        Damit deckt sich der Schnitt mit dem Satz oben: Bei leerer Szene *kann*
        nichts gehen, gleich was der Kunde täte. Steht ein Körper da, ist das
        Menü einen Klick entfernt — und dann ist die graue Zeile die Auskunft,
        die ihn hinführt.
        """
        result = self.session.last_result
        if result is not None and result.scene.objects:
            # Ein Körper liegt da: alles bleibt stehen, auch das Gesperrte.
            for menu in self._menus:
                handle = menu.menuAction()
                if isValid(menu) and handle in self.menuBar().actions():
                    handle.setVisible(True)
            return

        # **Über die gehaltene Liste, nicht über die Leiste.** Die Leiste gibt
        # Actions zurück, deren Menü sie selbst besitzt; self._menus ist die
        # Quelle, die sie am Leben hält (siehe _menu). Der erste Anlauf ging
        # über menuBar().actions() und fasste dabei ein Menü an, dessen
        # C++-Seite fort war — derselbe Fehler wie in overlay.py, nur an
        # einer Stelle, die ich selbst gebaut hatte.
        for menu in self._menus:
            handle = menu.menuAction()
            # **Nicht ``is None``, und das ist kein Stilwunsch.** PySide6 gibt
            # in seinen Stubs ``QMenu`` statt ``QMenu | None`` zurück, und mypy
            # hält den Zweig damit für unerreichbar — zur Laufzeit liefert eine
            # Action ohne Untermenü sehr wohl ``None``. Dieselbe Stub-Falle wie
            # bei ``NumberSpin.validate``: Die Wahrheit steht im Verhalten, nicht
            # in der Deklaration.
            if not isValid(menu) or handle not in self.menuBar().actions():
                # Nur die obersten: Untermenüs stehen auch in _menus, und
                # ein Untermenü auszublenden verschöbe die Zeile darüber.
                continue
            entries = list(_menu_entries(menu))
            # Ein Menü ohne Einträge bleibt stehen: Es ist keines, in dem
            # nichts geht, sondern eines, das noch gefüllt wird.
            handle.setVisible(not entries or any(entry.isEnabled() for entry in entries))

    def _kinds_of_selection(self, result: Any) -> list[str]:
        """Die Bauart jedes gewählten Körpers — Netz oder exakt.

        Gefragt wird der Baum: er hält Auswahl und Auswertung, und sein
        Kontextmenü braucht dieselbe Antwort. ``result`` bleibt im Aufruf, weil
        das Fenster hier schon eines in der Hand hat — der Baum hat dasselbe.
        """
        return self.object_tree.kinds_of_selection()

    def _kind_hint(self, action: QAction, reason: str | None, locked: bool) -> None:
        """Sagt am ausgegrauten Eintrag, *warum* er ausgegraut ist.

        Ausgrauen allein wäre die halbe Antwort: der Nutzer sieht, dass es
        nicht geht, und sucht den Grund bei sich. Der Satz ist derselbe, den
        der Kern wirft, nur kommt er hier vor dem Klick statt nach dem Dialog.

        **Er galt lange nur für die Bauart.** Die Funktion stieg sofort aus,
        wenn ``requires_kind`` leer war — und das haben sieben von 84
        Operationen. Auf der leeren Szene sind 69 von 82 Einträgen gesperrt,
        und bei allen 69 stand als Hinweis ihr Beschreibungssatz: was sie täte,
        wenn sie könnte. Die Werkzeugzeile daneben sagte es im selben Augenblick
        richtig („Dafür braucht es einen Körper in der Szene."), weil
        ``set_usable`` den Grund mitbekommt.

        **Der Grund kommt herein, statt hier gerechnet zu werden.** Er wird
        oben schon gebraucht — die Freigabe des Eintrags folgt ihm —, und
        ``_reason_locked`` ein zweites Mal je Eintrag zu rufen ist nicht nur
        doppelte Arbeit: mit 59 Einträgen je Aktualisierung endete
        ``tests/test_operation_ui.py`` reproduzierbar in einer
        Zugriffsverletzung, während derselbe Lauf mit einem Aufruf zweimal
        sauber durchging.
        """
        if locked:
            return
        stored = action.property("tip_before_kind")
        if reason is not None:
            if stored is None:
                action.setProperty("tip_before_kind", action.statusTip())
            action.setStatusTip(reason)
            action.setToolTip(reason)
        elif stored is not None:
            action.setStatusTip(str(stored))
            action.setToolTip(str(stored))
            action.setProperty("tip_before_kind", None)

    def _reason_locked(
        self, spec: OperationSpec, kinds: list[str], objects: int, chosen: int
    ) -> str | None:
        """Warum diese Operation gerade nicht geht — oder ``None``, wenn sie geht.

        Die Reihenfolge ist die, in der ein Nutzer sie beheben würde: erst
        etwas in die Szene, dann etwas auswählen, dann die richtige Bauart.
        """
        if spec.takes_whole_scene:
            if objects <= 0:
                return str(_NEEDS_BODY)
            return None
        if not spec.consumes:
            return None
        if chosen < spec.consumes:
            if objects <= 0:
                return str(_NEEDS_BODY)
            if spec.consumes == 1:
                return str(tr("Wählen Sie dafür ein Objekt aus — im Bild oder im Objektbaum."))
            return str(
                tr("Wählen Sie dafür {count} Objekte aus — im Bild oder im Objektbaum.").format(
                    count=spec.consumes
                )
            )
        # Der Satz steht in ``labels``: das Kontextmenü am Körper braucht ihn
        # auch, und zwei Stellen mit derselben Auskunft driften.
        reason = kind_requirement(spec, kinds, spoiled_the_exact_body(self.session.last_result))
        if reason is not None:
            return reason
        # Und zuletzt das Merkmal: Eine Operation, deren Pflichtfeld eine
        # Bohrung benennt, ist auf einem Körper ohne Bohrung eine Sackgasse —
        # der Dialog öffnete mit leerer Pflicht-Auswahl (Regel 19).
        return feature_requirement(spec, self._feature_kinds_of_selection())

    def _feature_kinds_of_selection(self) -> frozenset[str]:
        """Die Arten der erkannten Merkmale am gewählten Körper.

        Dieselbe Erhebung wie :meth:`_feature_names`, nur auf die Frage des
        Sperr-Grunds verengt: nicht *welche* Bohrung, sondern *ob* eine da ist.
        """
        result = self.session.last_result
        chosen = self.object_tree.selected()
        if result is None or chosen is None:
            return frozenset()
        entry = result.scene.objects.get(chosen)
        if entry is None:
            return frozenset()
        return frozenset(feature.kind for feature in entry.features.values())

    def _lock_twin_toggle(self, toggle: QCheckBox, hidden: str, objects: int, chosen: int) -> None:
        """Den Umschalter sperren, wo sein Zwilling auf dieser Auswahl nicht
        kann — mit dem Grund statt des Werbetexts.

        **Dieselbe Sackgasse, die die Menüleiste zwei Ebenen weiter vermeidet,
        stand am Haken wieder offen.** Eine Operation des exakten Kerns trägt
        ``requires_kind="brep"``; das Menü graut sie an einem Netz aus und
        schreibt den Grund in den Tooltip, statt sie anzubieten und nach dem
        ausgefüllten Dialog abzulehnen (Regel 19). Seit die Zwillinge
        zusammengelegt sind, ist der Haken der Weg zu ihr — sie hat gar keinen
        eigenen Menüeintrag mehr —, und dort wurde nicht gefragt. Gemessen an
        einer eingelesenen STL: Haken wählbar, Dialog geht durch, Auswertung
        hält an, und die Absage steht im Prüfbericht.

        Der gute Satz im Kern bleibt, er ist die **zweite** Hürde: „Der
        gewählte Körper ist ein Netz. Exakte Körper kommen aus einer
        STEP-Datei oder aus den Grundformen, deren Name mit Exakt beginnt."
        Was fehlte, war die erste.

        **Beim Quader konnte es nicht auffallen.** ``create_brep_box`` und
        ``create_brep_cylinder`` verbrauchen nichts (``consumes=0``) — es gibt
        keinen Eingangskörper, der der falsche sein könnte. Die exakte Bohrung
        ist der erste Zwilling mit einem Eingang, und damit der erste Fall, in
        dem der Haken eine Bedingung hat.

        Gefragt wird über ``_reason_locked``, also über dieselbe Kette wie
        Menüleiste und Kontextmenü — eine dritte Formulierung derselben
        Auskunft wäre eine dritte Gelegenheit, auseinanderzulaufen.
        """
        kinds = self._kinds_of_selection(self.session.last_result)
        reason = self._reason_locked(REGISTRY.get(hidden), kinds, objects, chosen)
        if reason is None:
            return
        toggle.setEnabled(False)
        toggle.setToolTip(reason)
        toggle.setStatusTip(reason)

    def _twin_toggle_hint(self, hint: str, op_id: int, *, exact_now: bool) -> str:
        """Der Satz am Umschalter — und was das Abwählen den Schritten darüber
        kostet.

        **Die Sperre daneben fragt die Auswahl, nicht die Zukunft.**
        :meth:`_lock_twin_toggle` prüft, ob der Zwilling auf dem *gewählten*
        Körper überhaupt kann, und schützt damit den Weg **zum** exakten Kern.
        Der Weg zurück hat dieselbe Sackgasse spiegelbildlich: Ein exakter
        Quader, darüber eine Verrundung, dann den Haken abgewählt — die
        Auswertung hält bei der Verrundung an, weil sie einen exakten Körper
        braucht. Der Satz des Kerns ist gut und kommt zu spät; er steht im
        Prüfbericht, nachdem geklickt wurde (Regel 19).

        **Gesperrt wird trotzdem nicht.** Zurückschalten ist eine legitime
        Absicht — vielleicht will der Kunde die Verrundung ohnehin loswerden,
        und ein Haken, den er nicht abwählen darf, wäre die schlechtere
        Sackgasse. Was fehlte, ist die Auskunft davor: wie viele Schritte
        darüber daran hängen. Die Zahl steht im Verlauf, die Bedingung im
        Register.
        """
        if not exact_now:
            # Der Haken ist aus: Setzen kostet nichts, was hier zu warnen wäre.
            return hint
        document = self.session.project.document
        later = [
            entry
            for entry in document.ops
            if entry.id > op_id and REGISTRY.get(entry.op).requires_kind == "brep"
        ]
        if not later:
            return hint
        warning = tr(
            "Darüber liegen {count} Schritte, die einzeln bearbeitbare Flächen und "
            "Kanten brauchen. Ohne diese Option halten sie an."
        ).format(count=len(later))
        return f"{hint}\n\n{warning}"

    @staticmethod
    def _button_tip(label: str, source: QAction | None, own_hint: str) -> str:
        """Was am Werkzeugknopf steht: Name, Kürzel, Zweck.

        Der Zweck kommt aus dem Menüeintrag derselben Handlung, wenn es einen
        gibt — er ist dort schon geschrieben und übersetzt, und zwei Sätze für
        einen Knopf driften auseinander. Das Kürzel steht dabei: Es ist die
        Stelle, an der man es nebenbei lernt, wie in der Werkzeugzeile unten
        und im Skizzeneditor.
        """
        text = label
        if source is not None:
            key = source.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
            if key:
                text = f"{label}  ({key})"
        sentence = own_hint or (source.statusTip() if source is not None else "")
        # Gedankenstrich hier, Doppelpunkt in ``_with_name``: jeder Trenner
        # dort, wo der Satz dahinter ihn nicht schon selbst führt. „Zum
        # Startbildschirm: leeres Projekt …" mit einem zweiten Doppelpunkt
        # davor liest sich wie zwei Aufzählungen ineinander.
        return f"{text} — {sentence}" if sentence else text

    @staticmethod
    def _with_name(action: QAction, reason: str) -> str:
        """Der Grund, dem Namen vorangestellt — nur wenn der Knopf ihn nicht zeigt.

        Beschriftete Werkzeugknöpfe und Menüeinträge lassen den Grund allein.
        Für einen reinen Symbolknopf bleibt der Name im Hinweis erhalten; ein
        Bild und ein Satz ohne Verbindung wären sonst zu raten.

        Getrennt wird mit Doppelpunkt und nicht mit Gedankenstrich: Der
        Sperrgrund führt selbst einen, und zwei in einem Satz sagen nicht mehr,
        welcher die Gliederung trägt.
        """
        return f"{action.text()}: {reason}" if action.property("wordless") else reason

    def _pick_hint(self, action: QAction, ready: bool, locked: bool) -> None:
        """Sagt am ausgegrauten Knopf, dass ihm die Auswahl fehlt.

        Dasselbe Muster wie :meth:`_kind_hint`, nur mit der einfacheren Frage:
        Formen und Skelett brauchen einen gewählten Körper. Ausgegraut allein
        wäre die halbe Antwort — der Satz steht dort, wo er **vor** dem Klick
        gelesen wird.

        Bei gesperrter Anwendung schweigt er: dort gilt der Grund aus
        :meth:`_lock_hint`, und zwei Gründe an einem Knopf sind einer zu viel.
        """
        if locked:
            return
        stored = action.property("tip_before_pick")
        if not ready:
            if stored is None:
                action.setProperty("tip_before_pick", action.statusTip())
            reason = self._with_name(action, tr("Dafür braucht es einen ausgewählten Körper."))
            action.setStatusTip(reason)
            action.setToolTip(reason)
        elif stored is not None:
            action.setStatusTip(str(stored))
            action.setToolTip(str(stored))

    def _open_error_url(self, error: AppError) -> None:
        """Öffnet die Adresse, die im Fehler mitreist — nicht die Produktseite.

        ``open_website`` wäre hier falsch: Der Kunde wollte zu **seiner**
        Datei, und ihre Adresse steht in ``values["url"]``. Der Rat „Seite im
        Browser öffnen" stand bis zum 30.08.2026 nur als Satz da, obwohl die
        Anwendung ihn einlösen kann.

        Fehlt die Adresse, geschieht nichts — ein Knopf, der ins Leere führt,
        wäre schlimmer als der Satz, den er ersetzt. Angeboten wird er
        ohnehin nur zu den zwei Adressfehlern, die sie mitgeben.

        **Woher die Adresse kommt**, damit der nächste Leser die Frage nicht
        neu stellt: aus der Eingabe des Import-Dialogs — der Kunde hat sie
        selbst getippt oder eingefügt, und ``fetch`` reicht sie unverändert in
        ``values`` durch. Geöffnet wird also nichts, was er nicht schon vor
        sich hatte.
        """
        adresse = str(error.values.get("url", "")) if error.values else ""
        if adresse:
            QDesktopServices.openUrl(QUrl(adresse))

    def _say_why(self, action: QAction, reason: str) -> None:
        """Schreibt den Grund einer Sperre an den Eintrag — und nimmt ihn zurück.

        Gebaut wie ``_lock_hint`` und ``_kind_hint``, nur für die Befehle, die
        nicht aus dem Register kommen: Exportieren, Rückgängig, Wiederholen,
        Automatisch teilen und Varianten. Bei leerem Projekt sind genau diese
        fünf gesperrt, und in Menü und Palette stand als Hinweis ihr
        Beschreibungssatz — was sie täte, wenn sie könnte.

        Der Grund gehört dorthin, wo die Bedingung steht, und nicht in eine
        zweite Tabelle: Wer die Bedingung ändert und den Satz vergisst, hat ihn
        eine Zeile weiter vor Augen.
        """
        stored = action.property("tip_before_why")
        if reason and not action.isEnabled():
            if stored is None:
                action.setProperty("tip_before_why", action.statusTip())
            action.setStatusTip(reason)
            action.setToolTip(reason)
            return
        if stored is not None:
            action.setStatusTip(str(stored))
            action.setToolTip(str(stored))
            action.setProperty("tip_before_why", None)

    def _lock_hint(self, action: QAction, locked: bool) -> None:
        """Schreibt den Grund der Sperre in den Hinweistext — und stellt den
        eigenen wieder her, sobald ein Schlüssel eingetragen ist.

        Der Grund steht dort, wo der Eintrag ihn **vor** dem Klick zeigt:
        Statusleiste und Tooltip (§2 C). Der ursprüngliche Satz reist als
        Qt-Property mit, weil er je Eintrag ein anderer ist.

        **Welcher Grund es ist, wird gefragt und nicht angenommen.** Hier stand
        ein fester Satz über den abgelaufenen Testzeitraum, abgeleitet aus
        ``not unlocked`` — und ``unlocked`` verlangt auch ``not damaged``.
        Damit las ein **zahlender** Kunde mit beschädigter Installation „dafür
        braucht Solidon einen Lizenzschlüssel", während die Statuszeile im
        selben Fenster „Die Installation ist beschädigt" sagte: zwei
        Auskünfte, und die am Menüeintrag war falsch.

        Die beiden Lagen auseinanderzuhalten ist der ganze Sinn von
        ``damaged`` (:attr:`app.core.activation.Activation.expired` sagt es im
        Docstring). Der Wortlaut kommt aus derselben Quelle wie dort —
        :func:`~app.ui.dialogs.damaged_line`, gespeist aus
        ``InstallationDamaged`` im Kern. Gefunden von 3d-druck-46 im
        Lizenz-Audit; dieselbe Form baut ``print_settings_dialog`` am
        Slicen-Knopf.
        """
        stored = action.property("tip_before_lock")
        if locked:
            if stored is None:
                action.setProperty("tip_before_lock", action.statusTip())
            explanation = licence_lock_line()
            reason = self._with_name(action, explanation)
            action.setStatusTip(reason)
            action.setToolTip(reason)
        elif stored is not None:
            action.setStatusTip(str(stored))
            action.setToolTip(str(stored))
            action.setProperty("tip_before_lock", None)

    def _trial_status_line(self) -> None:
        """§2 C: **einmal** eine Zeile in der Statusleiste, wenn weniger als
        drei Tage übrig sind.

        Kein Startdialog, keine Zählung im Fenstertitel, keine Erinnerung am
        dritten Tag — die Zeile steht in ihrem eigenen Feld am rechten Rand
        der Statusleiste, und das ist genug. Nach dem Eintragen eines
        Schlüssels räumt derselbe Aufruf sie weg.

        Sie war einmal eine ``showMessage``-Meldung, und das war der Fehler:
        Eine solche Meldung legt sich über alles, was links per ``addWidget``
        liegt — hier über die Maße der Auswahl. Auf jedem Handbuchbild lagen
        deshalb „Keine Auswahl" und „Demo — noch 79 Tage" ineinander. Was
        dauerhaft steht, ist keine Meldung.

        **In der Demo steht sie dauerhaft** (Demo-Konzept §2 F). Dort endet
        die Frist nicht in einem Betrachtermodus, sondern im Schluss; eine
        Zeile, die erst am vorletzten Tag erscheint, käme für den zu spät, der
        drei Tage vorher angefangen hat.
        """
        state = activation.state()
        message = ""
        if state.damaged:
            # Demo und Testlauf nennen sich hier selbst — ausgerechnet der
            # Zustand, der alles sperrt, schwieg: Der Kunde sah eine
            # Oberfläche wie immer und erfuhr den Grund erst am ersten
            # Änderungsversuch. Derselbe Satz wie im Freischaltdialog, aus
            # derselben Quelle — zwei Formulierungen liefen auseinander.
            message = damaged_line()
        elif state.deactivation_pending:
            message = licence_lock_line(state)
        elif state.needs_activation:
            message = tr(
                "Lizenzschlüssel gültig — diesen Rechner noch aktivieren: "
                "Hilfe → Solidon freischalten …"
            )
        elif state.in_demo and state.days_left > 0:
            message = demo_line(state)
        elif state.in_trial and state.days_left < 3:
            message = tr("Testzeitraum: noch {days} Tage — Hilfe → Solidon freischalten …").format(
                days=state.days_left
            )
        elif state.expired:
            # **Ausgerechnet am Tag, an dem alles grau wird, schwieg die
            # Zeile.** ``in_trial`` verlangt ``days_left > 0``, also fiel bei
            # genau null keine Verzweigung mehr zu: 10 Tage unsichtbar
            # (richtig), 2 Tage sichtbar, 0 Tage unsichtbar. Die Erklärung
            # stand dann nur noch in Tooltips — und der Docstring darüber
            # begründet die Dauerzeile damit, dass niemand überrascht werden
            # darf. ``expired`` gab es die ganze Zeit; gefragt hat es niemand.
            message = tr("Der Testzeitraum ist abgelaufen — Hilfe → Solidon freischalten …")
        elif state.sale_without_trial:
            message = licence_lock_line(state)
        self.trial_line.setText(message)
        self.trial_line.setVisible(bool(message))
        # Der Satz nennt den Menüweg weiterhin — er steht auch im Handbuch und
        # in fünf Katalogen so. Was dazukommt, ist die Zusage, dass der Klick
        # dorthin führt: an drei Stellen, weil drei verschiedene Leute sie
        # brauchen (Regel 18).
        if message:
            self.trial_line.setToolTip(tr("Öffnet die Freischaltung."))
            self.trial_line.setStatusTip(tr("Öffnet die Freischaltung."))
            self.trial_line.setAccessibleName(tr("Solidon freischalten"))
            self.trial_line.setAccessibleDescription(message)
        # Die Linie trennt zwei Auskünfte — steht links keine, trennt sie
        # nichts und wäre ein Strich ohne Anlass.
        self.trial_divider.setVisible(bool(message))
        self._trial_message = message

    def _connect_session(self) -> None:
        self.session.sceneChanged.connect(self._on_scene)
        self.session.projectChanged.connect(self._on_project)
        self.session.progressChanged.connect(self._on_progress)
        self.session.busyChanged.connect(self._on_busy)
        self.session.askRequested.connect(self._on_ask)
        # Der asynchrone Einleseweg meldet, wo der synchrone geworfen hat.
        #: Der Name der heruntergeladenen Datei, bis ihr Import durch ist.
        #: Die Meldung „Geladen: …" gehört ans Ende des Vorgangs, und der
        #: endet seit dem Arbeiter nicht mehr in derselben Methode.
        self._pending_download = ""
        self.session.importFailed.connect(self._on_import_failed)
        self.session.importFinished.connect(self._on_import_finished)
        self.session.failed.connect(self._on_error)
        # Gebundene Methode, kein Lambda: Der Sender ist ein Kind dieses
        # Fensters, und ein Lambda schlösse den Ring aus `.claude/rules`.
        self.session.backendChanged.connect(self._refresh_chat_availability)
        self.session.proposalReady.connect(self._on_proposal)
        self.session.agentBusyChanged.connect(self._on_agent_busy)
        self.session.agentProgress.connect(self._on_agent_progress)
        self.session.splitBusyChanged.connect(self._on_split_busy)
        self.session.splitProgressChanged.connect(self._on_split_progress)
        self.session.splitCancelRequested.connect(self._on_split_cancel_requested)
        self.session.splitCancelled.connect(self._on_split_cancelled)
        self.session.evaluationCancelled.connect(self._on_evaluation_cancelled)
        self._refresh_chat_availability()

    # --- actions ----------------------------------------------------------------

    def action_new(self) -> None:
        """Führt auf den Startbildschirm — dort steht, womit man anfangen kann.

        Vorher legte *Neu* sofort eine leere Szene an, und damit waren die
        sieben Beispielprojekte samt ihren Touren nach dem ersten Start nur
        noch über *Öffnen* mit Pfadkenntnis zu erreichen. Der Startbildschirm
        ist der einzige Ort, an dem sie stehen.

        Ein Klick mehr ist es nicht: „Neues Projekt" ist dort der Hauptknopf
        und liegt auf der Eingabetaste. Verworfen wird hier noch nichts —
        gefragt wird erst, wenn wirklich etwas verloren ginge (Regel 19).
        """
        self._show_start_screen(True)

    def action_examples(self) -> None:
        """Zurück zu den Beispielprojekten (§37.2).

        Sie sind Dokumentation, Abnahmetest und Startbildschirm-Inhalt in
        einem — und standen genau an einer Stelle: auf dem Startbildschirm,
        den nach *Datei → Neu* niemand mehr suchte. Im Hilfemenü ist es der
        Ort, an dem man nach Lehrmaterial sieht.

        Denselben Weg wie *Neu*: Verworfen wird hier nichts. Gefragt wird
        erst, wenn wirklich etwas verloren ginge — beim Öffnen eines
        Beispiels oder beim leeren Projekt (Regel 19).
        """
        self._show_start_screen(True)

    def start_empty(self) -> None:
        """Ein leeres Projekt — was der Hauptknopf des Startbildschirms tut."""
        if not self._may_discard():
            return
        self.announce("")
        self.session.start_new(self.settings.printer, self.settings.material)
        self._remove_tour()
        self._show_start_screen(False)

    def action_open(self) -> None:
        name, _filter = QFileDialog.getOpenFileName(self, tr("Projekt öffnen"), "", PROJECT_FILTER)
        if name:
            self.open_path(Path(name))

    def _forget_recent(self, path: Path) -> None:
        """Einen Eintrag aus „Zuletzt geöffnet" nehmen — die Datei bleibt."""
        self.settings.recent = [entry for entry in self.settings.recent if entry != str(path)]
        save_settings(self.settings)
        self.start_screen.show_recent(self.settings.existing_recent())

    def _may_discard(self) -> bool:
        """Fragt, bevor ein geändertes Projekt weggeworfen wird.

        Kein Widerspruch zu Regel 19: die verbietet Rückfragen vor
        rücknehmbaren Handlungen, und ein verworfenes Dokument holt kein Undo
        zurück. Die Frage bietet deshalb das Speichern gleich mit an, statt
        den Nutzer zurückzuschicken.
        """
        if not self.session.modified:
            return True
        answer = confirm_unsaved(self.session.title, self)
        if answer == "cancel":
            return False
        if answer == "save":
            self.action_save()
            # Wer den Dateidialog abbricht, hat nicht gespeichert — und will
            # dann ganz sicher nicht, dass die Arbeit trotzdem verschwindet.
            return not self.session.modified
        # Verworfen heißt verworfen. Die automatische Sicherung ist für den
        # Absturz da (§38) — nicht dafür, eine Entscheidung des Nutzers zu
        # überstimmen. Bleibt sie liegen, bietet das nächste Öffnen genau den
        # Stand wieder an, den er hier gerade weggeworfen hat.
        clear_autosave(self.session.path)
        return True

    def open_path(self, path: Path) -> None:
        """Ein Einstiegspunkt für Menü, Zuletzt-Liste und Drag and Drop.

        Mit Wartezeiger und Statuszeile: Gelesen wird hier synchron — die
        Projektdatei über ``load``, das Modell über ``path.read_bytes()``. Die
        Ladeanzeige deckt das **nicht** ab: sie hängt am Fortschritt der
        Auswertung, und der beginnt erst, wenn die Datei gelesen ist; ihre
        200 ms Verzögerung kommen obendrauf. Die Statuszeile wird ausdrücklich
        neu gezeichnet, bevor das Lesen den Hauptthread belegt (§2.8).
        """
        if path.suffix.lower() == PART_FILE_SUFFIX:
            self._open_part_file(path)
            return
        project_file = path.suffix.lower() == PROJECT_SUFFIX
        if project_file and not self._may_discard():
            return
        # Vom Startbildschirm aus ersetzt ein Modell das offene Projekt — und
        # die Frage danach gehört VOR den Wartezeiger, wie bei der .p3d oben:
        # ein Fenster, das fragt und zugleich „bitte warten" zeigt, sagt
        # zweierlei (§2.8).
        starting_fresh = not project_file and self.stack.currentWidget() is self.start_screen
        if starting_fresh and not self._may_discard():
            return
        if project_file:
            # Was zum vorigen Projekt zu sagen war, gilt für dieses nicht:
            # „Exportiert: dose.3mf" über einer gerade geöffneten Datei wäre
            # eine Auskunft über etwas anderes. Vor dem Ladehinweis leeren,
            # sonst nähme ``announce`` ihn gleich wieder weg.
            self.announce("")
        self.status_message.setText(
            tr("Projekt wird geladen …") if project_file else tr("Modell einfügen …")
        )
        self.status_message.repaint()
        try:
            if project_file:
                with waiting():
                    self.session.open_project(path)
                    self.settings.remember(path)
                    save_settings(self.settings)
                # Beide fragen etwas, und beide erst außerhalb des
                # Wartezeigers: ein Fenster, das um Antwort bittet und dabei
                # „bitte warten" zeigt, sagt zweierlei.
                self._offer_recovery(path)
                self._offer_tour(path)
            else:
                if starting_fresh:
                    self.session.start_new(self.settings.printer, self.settings.material)
                    # Der Projektwechsel zeichnet den gemeinsamen
                    # Fortschrittsbereich neu; der Lesehinweis gehört
                    # unmittelbar davor.
                    self.status_message.setText(tr("Modell einfügen …"))
                    self.status_message.repaint()
                # **Kein Wartezeiger mehr, und das ist die Änderung.** Gemessen
                # an einer 3MF von 63 MB mit 32 Körpern: 0,09 s Lesen, 14,1 s
                # Zählen — und das Zählen lief hier im Hauptthread. Ein
                # Wartezeiger ist die Anzeige für zwei Sekunden; darüber
                # gehört die Arbeit in einen Arbeiter, sagt der Docstring von
                # ``waiting`` selbst. Was der Kunde jetzt sieht, ist die
                # Ladeanzeige mit Fortschritt über die Modelldateien der
                # Baugruppe — und ein Fenster, das sich bewegen lässt.
                #
                # Der Fehlerfall kommt nicht mehr als Ausnahme zurück, sondern
                # über ``importFailed``: Wer im Arbeiter plant, kann nicht in
                # einen Aufrufer werfen, der längst weitergelaufen ist.
                # **Der Wartezeiger bleibt, und er regelt sich selbst.** Unter
                # ``PLAN_IN_WORKER_ABOVE`` läuft der Weg gerade durch — dann
                # steht er, solange gelesen wird, wie eh und je. Darüber kehrt
                # der Aufruf sofort zurück, der Zeiger verschwindet mit dem
                # ``with``, und die Ladeanzeige mit ihrem Fortschritt übernimmt.
                # Eine Fallunterscheidung braucht es dafür nicht.
                with waiting():
                    self.session.import_model_async(path)
                return
        except AppError as error:
            self.status_message.setText(self._announcement)
            show_error(error, self)
            return
        self._show_start_screen(False)

    def action_save(self) -> None:
        if self.session.path is None:
            self.action_save_as()
            return
        self._save_to(self.session.path)

    def action_save_as(self) -> None:
        name, _filter = QFileDialog.getSaveFileName(
            self, tr("Projekt speichern"), "", PROJECT_FILTER
        )
        if name:
            self._save_to(_as_project_path(name))

    def _save_to(self, path: Path) -> None:
        """Speichern mit Wartezeiger — es ist keine Handlung ohne Dauer.

        Gemessen: 903 ms für ein Projekt mit einem 62-MiB-Netz, und das ohne
        jedes Zeichen. Nach §2.8 ist das die mittlere Stufe — Mauszeiger und
        Statusleiste —, und beide fehlten. Wer *Speichern* drückte, sah für
        eine Sekunde ein Fenster, das nicht reagiert; ob der Klick angekommen
        war, wusste er erst danach.

        Kein Arbeiter: Das Schreiben mutiert nichts an der Szene, es blockiert
        einmal und ist fertig. Ein Thread brächte eine Halteleine, einen
        Fehlerpfad und die Frage, was passiert, wenn dazwischen jemand
        weiterarbeitet — für unter zwei Sekunden ist das der teurere Weg.

        Die Zeile wird **selbst neu gezeichnet**, bevor blockiert wird. Ohne
        das käme sie erst, wenn die Ereignisschleife wieder dran ist — also
        nachdem das Warten vorbei ist. ``repaint`` und nicht
        ``processEvents``: Es zeichnet das eine Widget, statt fremde Eingaben
        mitten in den laufenden Aufruf zu lassen.
        """
        self.status_message.setText(tr("Wird gespeichert …"))
        self.status_message.repaint()
        try:
            with waiting():
                saved = self.session.save_project(path)
        except AppError as error:
            self.status_message.setText(self._announcement)
            # **Der datenkritischste Schreibfehler von allen.** Wessen Projekt
            # sich nicht speichern lässt, hat seine Arbeit noch nicht in
            # Sicherheit — und bekam einen Dialog, der nur „Details anzeigen"
            # anbot. Die Datei liegt in einem Programm offen oder das Laufwerk
            # ist voll: dann hilft ein zweiter Anlauf auf dieselbe Datei, oder
            # ein anderer Ort. Beides steht jetzt als Knopf da.
            self._write_failure = _WriteFailure(
                again=partial(self._save_to, path),
                elsewhere=self.action_save_as,
            )
            show_error(error, self)
            return
        self._write_failure = None
        self.settings.remember(saved)
        save_settings(self.settings)
        self.announce(tr("Gespeichert"))

    def action_import(self) -> None:
        """Eine Modelldatei in die laufende Szene (§17.1).

        Mit Wartezeiger und ohne Arbeiter: Gelesen wird die Datei am Stück
        (``read_bytes``), gerechnet wird an ihr erst in der Auswertung — und
        die läuft längst im Arbeiter, mit Balken und Abbrechen. Ein zweiter
        Arbeiter allein für das Lesen brächte eine Halteleine, einen
        Fehlerpfad und einen zweiten Weg in ``import_payload`` — für die paar
        Zehntel, die eine Platte für dreißig Megabyte braucht (§2.8).
        """
        name, _filter = QFileDialog.getOpenFileName(self, tr("Modell einfügen"), "", model_filter())
        if not name:
            return
        starting_fresh = self.stack.currentWidget() is self.start_screen
        # Der Anfang ersetzt das offene Projekt — dieselbe Frage wie in
        # ``open_path``, und aus demselben Grund vor dem Wartezeiger: Ohne
        # sie verschwanden Dokument und Verlauf wortlos, und Undo holte
        # nichts zurück (Gesamtreview-b, Bericht 08, Fund 1).
        if starting_fresh and not self._may_discard():
            return
        self.status_message.setText(tr("Modell einfügen …"))
        self.status_message.repaint()
        if starting_fresh:
            # Vom Startbildschirm aus ist Einfügen ein Anfang, kein
            # Nachtrag: ein frisches Projekt mit Drucker und Material
            # aus den Einstellungen, wie es open_path beim Ablegen
            # einer Datei auch anlegt.
            self.session.start_new(self.settings.printer, self.settings.material)
            # ``start_new`` zeichnet den gemeinsamen Fortschrittsbereich neu.
            # Der vorübergehende Lesehinweis wird danach erneut gesetzt, ohne
            # ihn anzukündigen.
            self.status_message.setText(tr("Modell einfügen …"))
            self.status_message.repaint()
        # Derselbe Weg wie in ``open_path``, aus demselben Grund: Das Zählen
        # der Körper einer Baugruppe dauert bei 63 MB vierzehn Sekunden, und
        # die gehören nicht in den Hauptthread. Der Fehler kommt über
        # ``importFailed``, der Wartezeiger deckt den kurzen Weg.
        with waiting():
            self.session.import_model_async(Path(name))

    def action_import_url(self) -> None:
        """Weg 1 (§2.2), wenn die Datei noch nicht auf dem Bett liegt.

        Die Zwischenablage ist vorbelegt, und das ist der ganze Griff: wer von
        einer Modellseite kommt, hat die Adresse gerade kopiert. Steht dort
        etwas anderes, bleibt das Feld leer statt Unsinn anzubieten.
        """
        clipboard = QApplication.clipboard()
        pasted = clipboard.text().strip() if clipboard is not None else ""
        try:
            suggestion = check_url(pasted)
        except AppError:
            suggestion = ""

        url, accepted = QInputDialog.getText(
            self,
            tr("Modell aus dem Netz"),
            tr("Direkte Adresse der Modelldatei:"),
            text=suggestion,
        )
        if accepted and url.strip():
            self.download_model(url.strip())

    def download_model(self, url: str) -> None:
        """Holt eine Adresse und legt das Ergebnis auf den Stapel.

        Die Adresse wird geprüft, **bevor** ein Arbeiter startet: eine
        ``file:``-Adresse aus der Zwischenablage soll gar nicht erst in einen
        Thread wandern (§32), und ein Tippfehler soll sofort etwas sagen.
        """
        try:
            address = check_url(url)
        except AppError as error:
            show_error(error, self)
            return

        worker = _DownloadWorker(address)
        self._retire(self._download_worker)
        self._download_worker = worker
        worker.step.connect(self._on_download_progress)
        worker.done.connect(self._downloaded)
        worker.failed.connect(self._download_failed)
        worker.stopped.connect(self._download_stopped)
        worker.crashed.connect(lambda detail: self._download_failed(InternalError(detail=detail)))
        worker.finished.connect(lambda done=worker: self._download_worker_done(done))
        self._downloading = True
        text = tr("Modell herunterladen …")
        self._set_progress_state(
            "download",
            active=True,
            text=text,
            minimum=0,
            maximum=100,
            value=0,
            accessible_description=text,
            cancel_enabled=True,
        )
        self._leash.start(worker)

    def _on_download_progress(self, share: float, label: str) -> None:
        """Wie weit die Datei ist. Ein Server ohne Längenangabe liefert
        ``0.0`` — dann läuft der Balken endlos, statt auf null zu stehen."""
        if share > 0.0:
            minimum, maximum, value = 0, 100, int(share * 100)
        else:
            minimum, maximum, value = 0, 0, 0
        self._set_progress_state(
            "download",
            text=label,
            minimum=minimum,
            maximum=maximum,
            value=value,
            accessible_description=label,
        )

    def _download_worker_done(self, worker: Any) -> None:
        if self._download_worker is worker:
            self._download_worker = None
        self._hold_until_done(worker)

    def _download_failed(self, error: AppError) -> None:
        self._end_download()
        show_error(error, self)

    def _downloaded(self, fetched: FetchedModel) -> None:
        """Was ankam, geht denselben Weg wie eine Datei von der Platte — mit
        einer Herkunft mehr (§16.3).

        „Denselben Weg" heißt auch: dieselben zwei Schritte drumherum wie in
        :meth:`open_path`. Ohne sie landete das Modell in einem Projekt, das
        noch gar nicht angefangen hat, und das Fenster blieb auf dem
        Startbildschirm stehen — geladen laut Statusleiste, unsichtbar im
        Bild.
        """
        self._end_download()
        if self.stack.currentWidget() is self.start_screen:
            # Dieselbe Frage wie in ``open_path`` und ``action_import``: Der
            # Anfang ersetzt das offene Projekt. Hier NACH dem Download —
            # die Datei ist schon da, verworfen wird nur die Sendung, nie
            # stumm die Arbeit.
            if not self._may_discard():
                self.announce(tr("Der Download wurde verworfen — das Projekt bleibt."))
                return
            self.session.start_new(self.settings.printer, self.settings.material)
        # Wie die zwei Wege von der Platte: Geplant wird im Arbeiter, gemeldet
        # über ``importFailed``. Eine heruntergeladene Baugruppe ist genau der
        # Fall, für den das gebaut ist — sie kommt ohne Vorwarnung in jeder
        # Größe.
        self._pending_download = fetched.name
        with waiting():
            self.session.import_payload_async(
                fetched.name,
                fetched.payload,
                origin=SourceOrigin(url=fetched.url, retrieved=fetched.retrieved),
            )

    def _cancel_download(self) -> None:
        """Der eine Abbrechen-Knopf gilt auch dem Download (§2.8) — ein
        300-MB-Modell an langsamer Leitung war sonst nur über das Beenden
        der Anwendung zu stoppen."""
        if self._download_worker is not None:
            self._download_worker.cancel.cancel()

    def _download_stopped(self) -> None:
        self._end_download()
        self.announce(tr("Der Download wurde abgebrochen."))

    def _end_download(self) -> None:
        self._downloading = False
        self._set_progress_state("download", active=False)
        self._progress_idle()

    def _anything_running(self) -> bool:
        """Ob irgendetwas läuft, das den Balken trägt (§2.8).

        Vier Besitzer mit drei verschiedenen Bedingungen, und keiner fragte
        Export oder Download: Endete eine Auswertung während eines Exports,
        verschwand der Balken, während die Datei noch geschrieben wurde — der
        Kunde hielt das Schreiben für beendet und schloss das Fenster. Eine
        Auskunft, alle Stellen fragen sie.
        """
        return (
            self.session.busy
            or self.chat.busy
            or self.session.split_running
            or self._exporting
            or self._downloading
        )

    def _progress_idle(self) -> None:
        """Die Anzeige zurück in den Ruhezustand — aber nur, wenn nicht schon
        etwas anderes rechnet.

        Gemeinsam für alle Arbeiter, die den Balken der Statusleiste selbst
        anschalten (Download, Export): jeder von ihnen muss ihn wieder
        loswerden, und keiner darf dabei den laufenden Auswertungsbalken
        ausknipsen.
        """
        if self._active_progress_owner() is None and not self._anything_running():
            # Mit dem Balken gehen die Zeitgeber und der Zeiger: Ein Arbeiter,
            # der den Balken selbst anschaltet, hat die Stufung übersprungen,
            # und ein Wartezeiger ohne laufende Rechnung sieht aus wie ein
            # hängendes Programm.
            self._stop_waiting()
        self._render_progress_state()

    def action_generate(self) -> None:
        """Weg 3 (§2.2): ein Satz oder ein Bild wird ein Körper in der Szene."""
        self._generate(None)

    def action_generate_from_image(self, path: str) -> None:
        """Ein Bild, das im Chatfenster gelandet ist (Konzept P15, E8).

        Meshys eine Bedienidee, die ohne Cloud nachbaubar ist: ein Foto oder
        eine Kinderzeichnung ist eine Eingabe wie ein Satz. Der Dialog öffnet
        mit dem Bild schon darin — noch einmal danach zu fragen wäre ein
        Schritt zu viel für jemanden, der es gerade fallen gelassen hat.
        """
        self._generate(Path(path))

    def _generate(self, image: Path | None) -> None:
        # Der Aufbau fragt einmal, ob ein Generator läuft, und das ist ein
        # Socket mit Zeitlimit — gemessen eine halbe Sekunde. Damit gehört er
        # in die mittlere Zeile der Wartezeit-Tabelle (§2.8).
        with waiting():
            dialog = GenerateDialog(parent=self)
        # Regel 17: „Es läuft kein Generator" bot nichts an. Von hier führt der
        # Weg in die Liste der zusätzlichen Programme, und danach sieht der
        # Dialog noch einmal nach — wer ComfyUI gerade gestartet hat, soll
        # nicht schließen und neu öffnen müssen.
        dialog.setupRequested.connect(lambda: self._offer_generator_setup(dialog))
        # Und wo ComfyUI läuft, aber die Knoten fehlen, führt der Weg direkt in
        # die Einrichtung: über die Liste der Programme wären es drei Klicks für
        # etwas, das der Dialog schon weiß.
        dialog.nodesRequested.connect(lambda: self._offer_generator_nodes(dialog))
        if image is not None:
            dialog.set_image(image)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result_mesh is None:
                return
            self.session.add_generated(dialog.result_mesh)
        finally:
            # Die zwei Lambdas darüber fangen das Fenster, und der Dialog ist
            # sein Kind — ohne Freigeben überlebt beides den Aufruf
            # (dieselbe Stelle wie in :meth:`_exec_catalog`).
            dialog.deleteLater()

    def action_auto_split(self, object_id: ObjectId | None = None) -> None:
        """§25: das gewählte Teil teilen, bis es passt, und die Nähte
        verstiften (§14).

        Der Körper lässt sich benennen, damit auch der Fehlerdialog „Modell
        teilen" anbieten kann — er weiß, welches Teil nicht passte.
        """
        if self.session.split_running:
            # Erste Hälfte der Sperre (Gesamtreview I-10) — die zweite steht
            # in ``session.split_async``: Zwei Suchen zugleich gab es nie
            # absichtlich, und der Abbrechen-Knopf gilt der laufenden.
            self.announce(tr("Die Teilung läuft schon — der Abbrechen-Knopf hält sie an."))
            return
        object_id = object_id or self.object_tree.selected()
        if not object_id:
            QMessageBox.information(self, tr("Automatisch teilen"), str(_NEEDS_SELECTION))
            return

        # Kein Wartezeiger mehr: die Suche prüft Kandidatenebene für
        # Kandidatenebene und dauert an einem großen Körper Sekunden bis
        # Minuten — §2.8 verlangt dafür Fortschritt und Abbrechen, kein
        # eingefrorenes Fenster mit Ankündigung.
        self.session.split_async(object_id, self._split_done)

    def _split_done(self, applied: Any) -> None:
        self.report.add_findings(applied.findings)
        if applied.transaction is None:
            self.announce(tr("Dieses Objekt passt bereits auf das Bett."))
            return
        self._queue_split_reveal(applied.object_ids)
        self.announce(
            f"{tr('Geteilt')}: {len(applied.object_ids)} · {len(applied.fits)} {tr('Passungen')}"
        )

    def bake_sculpt(self, op_id: int) -> None:
        """Den Stand einer Formsitzung festschreiben — mit Nachfrage.

        **Eine von zwei Bestätigungen vor einer Handlung.** (Daneben gibt es
        die ausdrücklich gewünschte Ausnahme beim Löschen im Verlauf sowie
        zwei Fragen anderer Art: Wiederherstellung nach einem Absturz und
        Speichern/Verwerfen beim Schließen.) Regel 19 verbietet sonst
        Bestätigungsdialoge vor rücknehmbaren Handlungen; diese Handlung ist
        es nicht folgenlos, denn danach lässt sich an den Zügen nichts mehr
        ändern. Deshalb steht im Dialog auch nicht „Sind Sie sicher", sondern
        was danach nicht mehr geht (Entscheidung D, §2.7).
        """
        box = QMessageBox(
            QMessageBox.Icon.Question,
            tr("Stand festschreiben"),
            tr(
                "Der jetzige Stand wird als Körper im Projekt abgelegt. Die Züge bleiben "
                "als Beleg stehen, wirken aber nicht mehr — an dieser Sitzung lässt sich "
                "danach nichts mehr ändern. Dafür wird sie nicht mehr gerechnet."
            ),
            QMessageBox.StandardButton.NoButton,
            self,
        )
        # Die Knöpfe heißen nach ihrer Handlung, nicht „OK": „Ja" verlangt,
        # die Frage im Kopf zu behalten — „Festschreiben" nicht. Derselbe
        # Grund wie bei `confirm_discard` nebenan.
        bake = box.addButton(tr("Festschreiben"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Abbrechen"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not bake:
            return
        if not self.session.bake_strokes(op_id):
            self.announce(tr("Dieser Schritt lässt sich nicht festschreiben."))

    def remove_history_operations(self, op_ids: Sequence[int]) -> None:
        """Gewählte Verlaufsschritte nach ausdrücklicher Bestätigung löschen.

        Das ist die vom Nutzer gewünschte Ausnahme zu Regel 19. Die Handlung
        bleibt als eine Transaktion rücknehmbar; die Nachfrage macht vor allem
        sichtbar, wenn spätere abhängige Schritte mit entfernt werden.
        """
        chosen = tuple(dict.fromkeys(int(op_id) for op_id in op_ids))
        removing = self.session.removal_closure(chosen)
        if not removing:
            return
        if len(chosen) > 1 and len(removing) > len(chosen):
            message = tr(
                "Mit den gewählten Schritten werden auch weitere spätere abhängige Schritte "
                "gelöscht. Strg+Z stellt alle gemeinsam wieder her."
            )
        elif len(chosen) > 1:
            message = tr(
                "Die gewählten Schritte werden aus dem Verlauf gelöscht. "
                "Strg+Z stellt alle gemeinsam wieder her."
            )
        elif len(removing) > len(chosen):
            message = tr(
                "Mit dem gewählten Schritt werden auch spätere abhängige Schritte "
                "gelöscht. Strg+Z stellt alle gemeinsam wieder her."
            )
        else:
            message = tr(
                "Der gewählte Schritt wird aus dem Verlauf gelöscht. Strg+Z stellt ihn wieder her."
            )
        discarded = self._discarded_names()
        if len(discarded) == 1:
            message += "\n\n" + tr(
                "Außerdem kann ein bereits zurückgenommener Schritt danach nicht mehr "
                "wiederholt werden:"
            )
        elif discarded:
            message += "\n\n" + tr(
                "Außerdem können {count} bereits zurückgenommene Schritte danach nicht mehr "
                "wiederholt werden:"
            ).replace("{count}", str(len(discarded)))
        if discarded:
            message += "\n" + "\n".join(f"· {name}" for name in discarded)
        box = QMessageBox(
            QMessageBox.Icon.Warning if discarded else QMessageBox.Icon.Question,
            tr("Schritt löschen"),
            message,
            QMessageBox.StandardButton.NoButton,
            self,
        )
        remove = box.addButton(tr("Löschen"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(tr("Abbrechen"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        if box.clickedButton() is not remove:
            return
        self.session.remove_operations(chosen)

    def action_undo(self) -> None:
        # Läuft eine Formsitzung, nimmt Strg+Z den letzten Zug zurück und
        # nicht die Operation davor. Dieselbe Trennung wie beim
        # Skizzeneditor: Der Editor hat sein eigenes Rückgängig, der Verlauf
        # bekommt die Sitzung als eine Transaktion (Regel 16).
        if self.restore_discarded_sketch() or self.undo_sculpt_stroke() or self.undo_bone():
            return
        transaction = self.session.undo()
        if transaction is not None:
            self.announce(tr("{name} zurückgenommen.").format(name=str(transaction.title)))

    def action_redo(self) -> None:
        self.session.redo()

    def action_toggle_bed(self) -> None:
        """Druckplatte, Bauraum und Maßstab aus- oder wieder einblenden.

        Der Haken im Menü und die Einstellung folgen dem Aufruf, gleich ob er
        aus dem Menü, der Palette oder dem Kürzel kommt.
        """
        visible = not self.settings.bed_visible
        self.settings.bed_visible = visible
        self._bed_action.setChecked(visible)
        self.viewport.set_bed_visible(visible)
        save_settings(self.settings)
        self.announce(tr("Druckplatte wieder da.") if visible else tr("Druckplatte ausgeblendet."))

    def action_toggle_right(self) -> None:
        visible = not self.settings.right_panel_visible
        self.right.setVisible(visible)
        self.settings.right_panel_visible = visible
        save_settings(self.settings)
        self._mark_status_alerts()

    def action_variants(self) -> None:
        """§28.3: derselbe Stapel mit einer gestuften Zahl, nebeneinander auf
        einer Platte.
        """
        VariantsDialog(self.session, self).exec()

    def action_install_extras(self) -> None:
        """§36: was fehlt, wofür es da ist, und ein Knopf, der es holt."""
        InstallDialog(self, settings=self.settings).exec()

    def _offer_slicer_setup(self, dialog: PrintSettingsDialog) -> None:
        """Aus den Druckeinstellungen in die Liste der zusätzlichen Programme.

        Und zurück: Der Dialog sieht danach noch einmal nach, ob ein Slicer da
        ist — sonst wäre der Weg eine Sackgasse mit Umweg.
        """
        self.action_install_extras()
        dialog.recheck_slicer()

    def _show_filaments(self, dialog: PrintSettingsDialog) -> None:
        """Aus den Druckeinstellungen zum Filamentwähler in der linken Spalte.

        Der Abschnitt ist einklappbar und im Regelfall zu; ein Aufleuchten
        allein zeigte auf eine Kopfzeile, unter der nichts steht — dieselbe
        Zusage wie beim Tourschritt (:meth:`_flash_area`).

        Der Dialog bleibt dabei offen und tritt nur zurück: Er ist modal, also
        wäre der Weg dorthin sonst einer, den man nicht gehen kann. Beim
        Zurückkommen liest die Kopfzeile neu, was die Spulen jetzt sagen.
        """
        dialog.hide()
        open_section(self.filaments)
        self.filaments.setStyleSheet(f"border: 2px solid {_flash_colour(self.filaments)};")
        QTimer.singleShot(FLASH_MS, self, lambda: self.filaments.setStyleSheet(""))
        dialog.show()
        dialog.refresh_materials()

    def _offer_generator_nodes(self, dialog: GenerateDialog) -> None:
        """Die Knoten und das Modell einrichten, und danach neu nachsehen."""
        from app.ui.comfy_dialog import ComfySetupDialog

        ComfySetupDialog(self).exec()
        dialog.recheck()

    def _offer_generator_setup(self, dialog: GenerateDialog) -> None:
        """Aus dem Erzeugungsdialog in die Liste der zusätzlichen Programme.

        Und zurück: Der Dialog fragt danach noch einmal, ob ein Generator
        läuft. Ohne das wäre der Weg eine Sackgasse mit Umweg — man kommt
        dorthin, wo es zu beheben ist, und muss dann trotzdem schließen und
        neu öffnen.
        """
        self.action_install_extras()
        with waiting():
            dialog.recheck()

    def action_shortcuts(self) -> None:
        """Die Kürzelübersicht (§19.2, D6).

        Als Dialog und nicht als Fenster: anders als das Handbuch schlägt man
        hier eine Taste nach und arbeitet weiter, statt daneben zu lesen.
        """
        from app.ui.shortcuts_window import ShortcutsWindow

        ShortcutsWindow(
            self.menuBar(),
            self,
            self._palette_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText),
        ).exec()

    def action_manual(self, page: str = "") -> None:
        """Das Handbuch — ein Fenster, kein Dialog.

        Es bleibt offen, während gearbeitet wird; ein Handbuch, das man zum
        Weiterarbeiten schließen muss, wird kein zweites Mal geöffnet. Und es
        wird wiederverwendet, damit nicht bei jedem Aufruf eines mehr auf dem
        Bildschirm steht.

        ``page`` schlägt das Kapitel auf, das der Aufrufer meint. Ohne Angabe
        bleibt es beim ersten Eintrag — richtig für *Hilfe → Handbuch*, falsch
        für einen Knopf, der ein bestimmtes Kapitel verspricht: Der
        Startbildschirm bot „Handbuch — die ersten fünfzehn Minuten" an und
        öffnete „Was Solidon ist", den ersten von über vierzig Einträgen. Wer den
        einzigen Hilfe-Knopf des Startbildschirms drückt, hat das zugesagte
        Kapitel danach selbst gesucht. ``ManualWindow.show_page`` konnte das seit
        je und wurde von keiner Stelle der Anwendung gerufen — nur vom Test.
        """
        window = self._manual
        if window is None:
            window = ManualWindow(self)
            self._manual = window
        window.show()
        if page:
            # Nach ``show``, denn erst dort steht die Liste der sichtbaren
            # Seiten; davor wäre die Zeile eine, die es noch nicht gibt.
            window.show_page(page)
        window.raise_()
        window.activateWindow()

    def action_about(self) -> None:
        AboutDialog(self).exec()

    def action_donate(self) -> None:
        DonationDialog(self).exec()

    def action_print_settings(self) -> None:
        """§29: die Einstellungen, mit denen gedruckt wird — hier, nicht im
        anderen Programm.

        Der Dialog bekommt die Schichtanalyse, und wo keine vorliegt, wird sie
        **nachgereicht**: die Vorschläge über Stützen, Haftung und
        Mindestschichtzeit hängen an der Geometrie und nicht am Material
        allein. Ohne sie ging der Dialog mit null Vorschlägen auf — bei einem
        Teil, dem Solidon 845 mm² Überhang auf einer Schicht ansieht.

        Gewartet wird darauf nicht mehr. Der Weg hierher stand bis zu zwei
        Sekunden still (``worker.wait``), und das war die schlechtere Hälfte
        beider Möglichkeiten: lange genug, um sich wie ein Hänger zu lesen,
        und trotzdem ohne Zusage — wer den Zeitraum riss, bekam den Dialog
        eben doch ohne Analyse. Er geht jetzt sofort auf, und
        :meth:`PrintSettingsDialog.take_slice_result` trägt sie nach, sobald
        sie da ist (§2.8).
        """
        # §29: Was Solidon hier rechnet, reist mit einer gespeicherten 3MF und
        # mit der Übergabe an den Slicer. Der Hinweis sagt das einmal je
        # Textfassung und lässt dabei wählen, ob es so sein soll; danach steht
        # die Wahl in den Einstellungen. Er hält nichts an (Regel 19) — hier
        # verlässt nichts das Gerät, anders als beim KI-Hinweis.
        ensure_print_disclosure(self.settings, self)
        # Der Wartezeiger bleibt für den Aufbau: die Suche nach dem Slicer im
        # Konstruktor kostet eine knappe halbe Sekunde — unter der Grenze aus
        # §2.8, aber nicht unter der, ab der ein Zeiger dazugehört.
        with waiting():
            dialog = PrintSettingsDialog(
                self.session, self.settings, self, slice_result=self._current_slice()
            )
        object_id = self.object_tree.selected()
        if dialog.slice_result is None and object_id is not None:
            # Läuft schon eine für diesen Körper, stellt sich der Dialog an;
            # sonst startet hier ein Arbeiter. Beide Wege enden in
            # ``_slice_for_settings`` — und der ruft nur, solange der Dialog
            # offen ist.
            self._settings_dialog = dialog
            self._slice_of(object_id, self._slice_for_settings)
        dialog.sliced.connect(self._gcode_returned)
        dialog.reported.connect(self._slicer_findings)
        # Regel 17: „Kein Slicer eingerichtet" sagte, was fehlt, und bot nichts
        # an — an der Stelle, an der jemand gerade slicen wollte. Von hier
        # führt der Weg in die Liste, und danach sieht der Dialog neu nach.
        dialog.setupRequested.connect(lambda: self._offer_slicer_setup(dialog))
        # Dasselbe Muster für das Material: Die Kopfzeile berichtet, woher es
        # kommt, und der Knopf daneben führt dorthin, wo es gewählt wird.
        dialog.filamentsRequested.connect(lambda: self._show_filaments(dialog))
        dialog.exec()
        self._settings_dialog = None

        # Die Einstellungen gehören zum Projekt, die Stufe und die Slicer-Wahl
        # zur Anwendung (§29). Getrennt gespeichert, weil ein Projekt auf einem
        # anderen Rechner geöffnet wird, wo ein anderer Slicer liegt.
        #
        # **Nur, wenn der Dialog etwas bewirkt hat.** Vorher schrieb schon das
        # bloße Öffnen die aufgelösten Werte ins Dokument; wer nachsah, welche
        # Temperatur vorgeschlagen würde, trug sie danach in jeder exportierten
        # 3MF mit sich. ``has_changes`` misst am Anfangszustand und nicht an
        # einer Liste von Knöpfen.
        if dialog.has_changes():
            self.session.set_print_settings(dialog.settings)
        self.settings.print_quality = dialog.settings.quality
        save_settings(self.settings)
        # Ohne das blieb jede Öffnung samt Profilliste am Fenster hängen —
        # bei der Orca-Familie einige tausend Einträge je Aufruf.
        dialog.deleteLater()

    def _edit_filament_settings(self, slot: object) -> None:
        """Die Druckwerte einer Spule direkt am Filamentwähler (§20, §29).

        Farbe und Flächenzuweisung bleiben Operationen. Hier ändert sich nur,
        womit der Slicer diesen bereits vorhandenen Materialslot fährt; deshalb
        reist der Wert über :meth:`Session.set_print_settings` und nicht am
        Operationsstapel vorbei in die Geometrie.
        """
        if not isinstance(slot, MaterialSlot):
            return
        document = self.session.project.document
        quality = cast(
            QualityPreset,
            self.settings.print_quality
            if self.settings.print_quality in print_settings.quality_presets()
            else print_settings.DEFAULT_QUALITY,
        )
        settings = document.print_settings or print_settings.resolve(self.session.profile, quality)
        dialog = FilamentOverrideDialog(
            slot,
            settings,
            override_for(settings, slot),
            self,
        )
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            updated = with_slot_override(settings, slot, dialog.override())
            self.session.set_print_settings(updated)
            result = self.session.last_result
            if result is not None:
                self.filaments.show_scene(list(result.scene.objects.values()), updated)
        finally:
            # Das Hauptfenster ist Qt-Eigentümer. Ohne die Freigabe bliebe
            # jeder geschlossene Dialog samt seinen neunzehn Feldern bis zum
            # Ende der Sitzung als unsichtbares Kind erhalten.
            dialog.deleteLater()

    def _current_slice(self) -> SliceResult | None:
        """Die Schichtanalyse des gewählten Körpers, wenn sie schon vorliegt.

        Liegt sie nicht vor, startet :meth:`_slice_of` sie und gibt ``None``
        zurück — **ohne** darauf zu warten. Der Weg zu den Druckeinstellungen
        stand hier zwei Sekunden still, weil ohne Analyse kein einziger
        Vorschlag zur Geometrie zustande kommt: keine Stützen, keine Haftung,
        keine Mindestschichtzeit, und die Warnung „Die Überhänge sind zu groß,
        um sich selbst zu tragen" erst danach, wenn überhaupt.

        Beides ist zu haben. Der Dialog geht sofort auf und bekommt die
        Analyse nachgereicht (``take_slice_result``) — an genau der Stelle,
        an der sie etwas ändert, nämlich in der Vorschlagsliste.
        """
        object_id = self.object_tree.selected()
        if object_id is None:
            return None
        return self._slice_of(object_id)

    def _slice_for_settings(self, result: SliceResult | None) -> None:
        """Die fertige Analyse in den offenen Druckeinstellungen-Dialog.

        Über das Feld und nicht als gebundene Methode des Dialogs in der
        Warteliste: Der Dialog wird nach ``exec`` weggeräumt
        (``deleteLater``), und ein Rückruf in ein zerstörtes C++-Objekt ist
        der Absturz ohne Zeile. Ist keiner mehr offen, ist das Ergebnis
        einfach nichts wert — im Cache liegt es trotzdem.
        """
        dialog = self._settings_dialog
        if dialog is not None:
            dialog.take_slice_result(result)

    def _gcode_returned(self, outcomes: list[SliceOutcome]) -> None:
        """Was der Slicer gemessen hat, geht in den Prüfbericht — als gemessen
        markiert, neben der Schätzung, nie an ihrer Stelle (Regel 14).

        Eine Liste, weil ein Auftrag mehrere Platten haben kann (§25). Die
        Gegenprobe läuft gegen die **Summe**: die Schätzung gilt dem Projekt,
        und sie je Platte dagegenzuhalten hieße, dreimal denselben Vergleich mit
        einem Drittel der Messung zu führen.
        """
        # Der erste Nachtrag räumt die G-Code-Befunde des vorigen Laufs ab —
        # sie beschreiben eine Druckdatei, die es nicht mehr gibt (Regel 14
        # liefert mit der Herkunft das Kriterium). Die weiteren Platten und
        # ``_compare_totals`` hängen an denselben Lauf an.
        for index, outcome in enumerate(outcomes):
            self.report.add_findings(
                outcome.findings, replacing_source="gcode" if index == 0 else None
            )
        self._compare_totals(gcode.combine([entry.metrics for entry in outcomes]))
        self._focus_report()
        self.announce(
            f"{tr('Geslicet')}: {outcomes[0].gcode_path.name}"
            if len(outcomes) == 1
            else f"{tr('Geslicet')}: {len(outcomes)} {tr('Platten')}"
        )

    def _slicer_findings(self, findings: list[Finding]) -> None:
        """Die Vorprüfung bleibt sichtbar, wenn der externe Lauf abbricht.

        Erfolgreiche Läufe bringen dieselben Befunde über
        :meth:`_gcode_returned` mit. Dieser Weg gehört nur dem Fehlerfall und
        verhindert deshalb keine Dubletten und erzeugt keine zweite Herkunft.
        """
        if not findings:
            return
        self.report.add_findings(findings)
        self._focus_report()

    def action_check_gcode(self) -> None:
        """§28.1: eine geslicete Datei zurücklesen und gegen die Schätzung
        halten.

        Die gemessenen Zahlen landen als gemessen markiert im Prüfbericht; die
        interne Schätzung bleibt, wo sie war. Nichts wird still ersetzt (§22.5).

        Lesen und Zerlegen laufen unter dem Wartezeiger: gemessen kostet ein
        Strom von 10 MB — dreihunderttausend Zeilen, ein mittleres Teil —
        520 ms im Qt-Hauptthread, und eine große Platte ist ein Mehrfaches
        davon. Das ist die mittlere Zeile der Wartezeit-Tabelle, und dort stand
        bisher nichts (§2.8). Der Zeiger endet vor jeder Meldung: eine Frage
        unter einem Wartezeiger sagt zweierlei.
        """
        name, _filter = QFileDialog.getOpenFileName(
            self, tr("G-Code gegenprüfen"), "", gcode_filter()
        )
        if not name:
            return

        try:
            with waiting():
                text = Path(name).read_text(encoding="utf-8", errors="replace")
                metrics = gcode.parse(text)
                findings = gcode.findings_for(metrics)
        except OSError as problem:
            # Zwischen Auswählen und Lesen kann eine Datei verschwinden, und
            # auf einem getrennten Netzlaufwerk oder ohne Leserecht gelingt
            # der Zugriff gar nicht. Ungefangen lief die Ausnahme in Qts
            # Ereignisverteiler: kein Dialog, keine Zeile, die Handlung tat
            # nichts — genau der stille Ausfall, den Regel 17 ausschließt.
            show_error(
                UserError(
                    title=tr("Diese G-Code-Datei ließ sich nicht lesen."),
                    detail=tr(
                        "Sie ist vielleicht verschoben worden, oder das Laufwerk "
                        "ist gerade nicht erreichbar. Wählen Sie die Datei noch "
                        "einmal aus."
                    ),
                    values={"path": Path(name).name, "reason": str(problem)},
                ),
                self,
            )
            return

        # Auch hier: Die gelesene Datei ist jetzt die aktuelle — was ein
        # früherer Lauf über eine andere gesagt hat, wird ersetzt.
        self.report.add_findings(findings, replacing_source="gcode")
        self._compare_totals(metrics)
        self._focus_report()
        self.announce(f"{tr('G-Code gelesen')}: {metrics.slicer or tr('unbekannter Slicer')}")

        # Die Gegenprobe zum Stützvolumen braucht die eigene Schätzung. Sie
        # wird geholt, nicht erzwungen: liegt sie noch nicht vor, rechnet der
        # Arbeiter sie und der Vergleich kommt nach — die gemessenen Zahlen
        # stehen längst im Bericht (§22.5).
        object_id = self.object_tree.selected()
        if object_id is not None and metrics.support_mm3 is not None:
            measured = metrics.support_mm3
            self._slice_of(
                object_id,
                lambda estimate, measured=measured: self._compare_support(estimate, measured),
            )

    def _compare_support(self, estimate: SliceResult | None, measured: float) -> None:
        """Geschätztes gegen gemessenes Stützvolumen (§22.5, Regel 14).

        Verglichen wird Material gegen Material, nicht Raum gegen Material:
        Die Säule aus der Schichtanalyse ist ein Rauminhalt, der Drucker füllt
        ihn nur zu ``support.density`` — :func:`support_material` rechnet um.
        """
        if estimate is None:
            return
        settings = self.session.project.document.print_settings or print_settings.resolve(
            self.session.profile
        )
        expected = support_material(estimate.support_volume, settings)
        self.report.add_findings(gcode.compare(expected, measured, "support").findings)

    def _compare_totals(self, metrics: gcode.GcodeMetrics) -> None:
        """Geschätzte gegen gemessene Druckzeit und Materialmenge (§28.2).

        Das Stützvolumen wurde schon immer gegengeprüft, Zeit und Material
        nicht — dabei liegen beide Zahlen nebeneinander vor. Beim Gewürzhalter
        standen 12 g gegen 10 g und 46 min gegen 37 min, also 17 und 20 Prozent
        auseinander, und der Bericht meldete vier Hinweise und keine Warnung.
        Die Schwelle von fünfzehn Prozent steht in :func:`gcode.compare` seit
        je; gerufen wurde sie nur an einer Stelle.

        Ersetzt wird nichts: beide Zahlen behalten ihre Herkunft (Regel 14).
        Der Bericht sagt bloß, dass sie sich widersprechen — und genau das ist
        das Signal, dass die Schichtanalyse Arbeit braucht.
        """
        result = self.session.last_result
        if result is None or not result.scene.objects:
            return
        settings = self.session.project.document.print_settings or print_settings.resolve(
            self.session.profile
        )
        bodies = [(entry.mesh.volume, entry.mesh.area) for entry in result.scene.objects.values()]
        estimate = estimate_total(bodies, settings)

        findings: list[Finding] = []
        grams = metrics.grams(settings.filament.density)
        if grams is not None and estimate.grams > 0.0:
            findings += gcode.compare(estimate.grams, grams, "material").findings
        if metrics.print_minutes is not None and estimate.seconds > 0.0:
            findings += gcode.compare(
                estimate.seconds / 60.0, metrics.print_minutes, "time"
            ).findings
        self.report.add_findings(findings)

    def action_export(self) -> None:
        """§29: die Körper als Datei — der Schritt, mit dem jeder der drei
        Wege aus §2.2 endet.

        Der Schreiber stand seit P2 im Kern und war, wie vorher schon auf der
        Kommandozeile, aus dem Fenster nicht erreichbar: der einzige Weg zu
        einer Datei führte über den Slicer (Strg+P), und der setzt einen
        installierten Slicer voraus. Exportiert wird die Auswahl, ohne
        Auswahl alles; ein 3MF wird **eine** Datei mit allen Körpern (§20),
        jedes andere Format eine Datei je Körper nach dem Namensschema.
        Die Prüfung davor ist ein Bericht, keine Sperre (§29) — ihre Befunde
        landen im Prüfbericht. „Wer trotzdem exportieren will, kann das — er
        weiß dann nur, was er tut", sagt §29.

        Gerechnet und geschrieben wird im Arbeiter (§2.8): Prüfung, Aufbau der
        Baugruppe und das Schreiben zusammen sind bei mehreren großen Körpern
        mehr als zwei Sekunden. Hier bleiben der Dateidialog und das
        Einsammeln der Körper — beides braucht die Auswahl, und beides ist
        sofort vorbei.
        """
        result = self.session.last_result
        if result is None or not result.scene.objects:
            return
        chosen = self.object_tree.selected_objects()
        objects = [
            entry
            for object_id, entry in result.scene.objects.items()
            if not chosen or object_id in chosen
        ]

        # ``document_name`` und nicht ``title``: Der Titel trägt seit dem
        # 23.08.2026 den Zusatz für ein ungespeichertes Projekt, und der gehört
        # ins Fenster und nicht in einen Dateinamen.
        stem = safe_name(self.session.document_name, "projekt")
        # 3MF steht zuerst und ist der vorgeschlagene Kundenweg: Es hält eine
        # Baugruppe in einer Datei und nimmt Namen, Farben und Druckeinstellungen
        # mit. STL bleibt für ältere Slicer ausdrücklich erreichbar, verliert
        # diese Informationen aber zwangsläufig.
        # GLB steht am Ende und nicht bei den Druckformaten: es ist das
        # Format zum Zeigen, nicht zum Drucken — Farben und Name reisen mit,
        # jeder Betrachter öffnet es, kein Slicer will es.
        offered = ["3MF (*.3mf)", "STL (*.stl)", "OBJ (*.obj)", "PLY (*.ply)", "GLB (*.glb)"]
        # STEP hält Flächen und Kanten fest, und ein Netz hat keine. Der
        # Schreiber sagt das mit einem guten Satz — nur sagte er ihn erst,
        # nachdem der Nutzer Format, Ordner und Namen gewählt hatte. Bei
        # Mesh-Projekten, und das sind die meisten, konnte der Eintrag nie zu
        # etwas führen. Angeboten wird er jetzt, wenn wenigstens ein Körper
        # ihn tragen kann.
        if any(entry.kind == "brep" for entry in objects):
            offered.append("STEP (*.step)")
        filters = ";;".join(offered)
        suggested_name = f"{stem}.3mf"
        name, chosen_filter = QFileDialog.getSaveFileName(
            self, tr("Exportieren"), suggested_name, filters
        )
        if not name:
            return
        target, export_format = _export_target(Path(name), chosen_filter, suggested_name)
        self._start_export(target, export_format)

    def _start_export(self, target: Path, export_format: ExportFormat) -> None:
        """Schreiben, wohin schon entschieden ist — ohne Dateidialog.

        Getrennt von :meth:`action_export`, weil ein zweiter Anlauf denselben
        Ort meint: Die häufigste Ursache für einen gescheiterten Export ist
        eine Datei, die im Slicer offen liegt, und wer sie dort schließt, will
        nicht Format, Ordner und Namen ein zweites Mal wählen (§2.7).

        Eingesammelt werden die Körper hier neu und nicht mitgeschleppt: Zwischen
        zwei Anläufen kann eine Auswertung gelaufen sein, und ein Körper aus der
        alten Szene wäre ein Netz, das im Dokument nicht mehr steht.
        """
        result = self.session.last_result
        if result is None or not result.scene.objects:
            return
        chosen = self.object_tree.selected_objects()
        objects = [
            entry
            for object_id, entry in result.scene.objects.items()
            if not chosen or object_id in chosen
        ]
        # Ein neuer Anlauf beginnt ohne die Vorgeschichte des alten: Was hier
        # stehen bleibt, wäre beim nächsten Fehler ein Wiederholknopf auf ein
        # Ziel, das niemand mehr gemeint hat.
        self._export_attempt = (target, export_format)
        self._write_failure = None

        worker = _ExportWorker(
            objects,
            target,
            export_format,
            profile=self.session.profile,
            sources=self.session.project.document.sources,
            # Die Druckeinstellungen reisen mit, und mit ihnen das Profil des
            # eingestellten Slicers (§29). Ohne beides ist die Datei reine
            # Geometrie: Der Slicer füllt sie aus dem, was gerade bei ihm
            # steht, und meldet dann Widersprüche zu einem Drucker, den
            # niemand gemeint hat. ``None`` im Dokument heißt „Dialog nie
            # geöffnet", nicht „keine Einstellungen" — dann gilt die Auflösung
            # aus Stufe, Material und Drucker, wie überall sonst.
            #
            # **Es sei denn, der Kunde will das nicht.** Die drei Fälle stehen
            # in :func:`settings_for_export`, damit ein Test sie fragen kann;
            # als Ausdruck an dieser Stelle waren sie es nicht.
            settings=settings_for_export(
                self.session.project.document, self.session.profile, self.settings
            ),
            ui_settings=self.settings,
            material=self.session.profile.material.id,
        )
        self._export_worker = worker
        # Die Flagge, nicht nur das Worker-Feld: ``_anything_running`` fragt
        # sie, und ohne sie nahm das Ende einer Auswertung dem noch
        # schreibenden Export den Balken weg — genau der Satz im Docstring
        # von ``_anything_running``, nur war die Flagge nie gesetzt worden.
        self._exporting = True
        worker.done.connect(self._export_done)
        worker.failed.connect(self._export_failed)
        # **Und das Unerwartete.** Der Menüeintrag ist gesperrt, solange
        # geschrieben wird; eine Ausnahme, die den Thread abriss, ließ ihn für
        # den Rest der Sitzung gesperrt — der Kunde konnte nicht mehr
        # exportieren und erfuhr nicht, warum.
        worker.crashed.connect(lambda detail: self._export_failed(InternalError(detail=detail)))
        worker.finished.connect(lambda done=worker: self._export_worker_done(done))
        text = tr("Exportiert wird … {name}").format(name=target.name)
        self._set_progress_state(
            "export",
            active=True,
            text=text,
            minimum=0,
            maximum=0,
            value=0,
            accessible_description=text,
        )
        # Solange geschrieben wird, führt der Menüeintrag nirgendwo hin: ein
        # zweiter Lauf schriebe in dieselben Dateien, und welcher von beiden
        # gewinnt, entschiede die Reihenfolge zweier Threads.
        self._update_actions()
        self._leash.start(worker)

    def _export_done(self, written: list[Path], findings: list[Finding]) -> None:
        """Was geschrieben wurde, und was dabei aufgefallen ist (§29)."""
        # Das Ende kommt vor dem Auslaufen des Threads (siehe Feld-Docstring).
        self._exporting = False
        self._set_progress_state("export", active=False)
        # Geschrieben heißt: es gibt nichts zu wiederholen.
        self._export_attempt = None
        self._write_failure = None
        if findings:
            self.report.add_findings(list(findings))
            self._focus_report()
        if not written:
            return
        self.announce(
            f"{tr('Exportiert')}: {written[0].name}"
            if len(written) == 1
            else f"{tr('Exportiert')}: {len(written)} {tr('Dateien')} → {written[0].parent}"
        )

    def _export_failed(self, error: AppError) -> None:
        """Der Fehlerdialog gehört in den Hauptthread, nicht in den Arbeiter.

        **Und er bekommt seinen Wiederholknopf.** ``FileWriteError`` schlägt
        *Erneut versuchen* vor, und für keine der beiden Ausnahmen, die das tun,
        gab es einen Handler — angezeigt wurde der Rat als Satz. Dabei ist das
        hier der Fall, in dem er fast immer stimmt: Die Datei liegt im Slicer
        offen, der Kunde schließt sie dort, und dann fehlt nur ein Klick. Was
        wiederholt werden soll, weiß allein diese Stelle; deshalb steht das Ziel
        hier und nicht in der Handlung.
        """
        self._exporting = False
        self._set_progress_state("export", active=False)
        attempt = self._export_attempt
        if attempt is not None:
            self._write_failure = _WriteFailure(
                again=partial(self._start_export, attempt[0], attempt[1]),
                elsewhere=self.action_export,
            )
        show_error(error, self)

    def _export_as_mesh_after_error(self, _error: Any) -> None:
        """Dasselbe Teil als 3MF, wenn STEP an einem Netz gescheitert ist (§29).

        STEP hält Flächen und Kanten fest; ein Netz hat keine. Der Befund sagt
        das seit je und nennt beide Auswege — er sagte es nur in Prosa, und
        §2.7 verspricht anklickbare Handlungen.

        Das Ziel kommt aus dem letzten Versuch, wie beim Schreibfehler daneben:
        Wer eine Datei benannt hat, will sie nicht ein zweites Mal benennen.
        Ist keiner bekannt — der Bericht lässt sich auch lange nach dem Export
        ansehen —, führt der Weg in den Dateidialog statt ins Leere.
        """
        attempt = self._export_attempt
        if attempt is None:
            self.action_export()
            return
        self._start_export(attempt[0].with_suffix(".3mf"), "3mf")

    def _after_write_failure(self, way: str) -> None:
        """Den zweiten Anlauf gehen — dieselbe Datei oder ein anderer Ort (§2.7)."""
        failure = self._write_failure
        if failure is None:
            return
        (failure.again if way == "again" else failure.elsewhere)()

    def _export_worker_done(self, worker: Any) -> None:
        if self._export_worker is worker:
            self._export_worker = None
            self._exporting = False
            self._set_progress_state("export", active=False)
            self._progress_idle()
            self._update_actions()
        self._hold_until_done(worker)

    def action_catalog(self) -> None:
        """§24.3: die Bibliothek, die man sehen kann. Einen Baustein zu wählen
        führt seine Operation aus.
        """
        self._open_catalog()

    def action_adopt_part_file(self) -> None:
        """Eine lokale Bausteindatei wählen und im sichtbaren Katalog prüfen."""
        catalog = self._make_catalog()
        catalog.show()
        self._adopt_part(catalog)
        self._exec_catalog(catalog)

    def action_share_part_file(self) -> None:
        """Den Katalog zur Auswahl des weiterzugebenden Bausteins öffnen."""
        self._open_catalog()

    def _open_part_file(self, path: Path) -> None:
        """Eine direkt geöffnete Bausteindatei im Katalog einlesen."""
        catalog = self._make_catalog()
        catalog.show()
        self._import_part_path(catalog, path)
        self._exec_catalog(catalog)

    def _open_catalog(self) -> None:
        """Den gemeinsamen Katalogaufbau öffnen."""
        self._exec_catalog(self._make_catalog())

    def _make_catalog(self) -> PartCatalog:
        """Den Katalog für alle drei lokalen Zugänge gleich verdrahten."""
        catalog = PartCatalog(self)
        catalog.set_can_save(*self._recipe_readiness())
        catalog.set_can_insert(*self._insert_readiness())
        # Und die zweite Bedingung, die je Baustein gilt: Vierundzwanzig der
        # siebenundzwanzig werden an eine Fläche oder Bohrung gesetzt. Sie
        # sperrt nicht — der Weg über eine eingetragene Position bleibt —,
        # aber sie sagt es vorher statt als Fehler danach (Robert, 29.08.2026).
        catalog.set_feature_chosen(self.object_tree.selected_feature() is not None)
        catalog.saveRequested.connect(lambda: self._save_as_part(catalog))
        catalog.shareRequested.connect(lambda: self._share_part(catalog))
        catalog.adoptRequested.connect(lambda: self._adopt_part(catalog))
        catalog.removeRequested.connect(lambda name: self._remove_part(catalog, name))
        catalog.undoFileRequested.connect(lambda: self._undo_part_file(catalog))
        catalog.showAffectedStepRequested.connect(lambda: self._show_part_affected_step(catalog))
        return catalog

    def _exec_catalog(self, catalog: PartCatalog) -> None:
        """Den Katalog ausführen und eine bestätigte Einfügeauswahl anwenden."""
        try:
            if catalog.exec() != PartCatalog.DialogCode.Accepted:
                return
            name = catalog.chosen()
            if name:
                self.run_operation(REGISTRY.get(part_op_name(name)))
        finally:
            # Die sechs Lambdas aus :meth:`_make_catalog` fangen das Fenster,
            # und der Katalog ist sein Kind: Ohne Freigeben hält jede Öffnung
            # das ganze Fenster samt Kachelliste bis zum Programmende fest.
            # Im ``finally``, weil der abgebrochene Katalog der häufigere Fall
            # ist — genau der, der vorher hängenblieb.
            catalog.deleteLater()

    def _insert_readiness(self) -> tuple[bool, str]:
        """Ob sich gerade ein Baustein einsetzen lässt — und sonst warum nicht.

        Die Absage stand vorher **hinter** dem Katalog: Auf der Startseite
        ließ sich ein Baustein wählen und bestätigen, und erst dann kam
        „Wählen Sie zuerst ein Objekt" — zwei Dialoge für eine Antwort, die
        beim Öffnen feststand (Robert, 25.08.2026). Der Grund für den leeren
        Fall ist ein eigener Satz: Auf der Startseite gibt es keinen
        Objektbaum, auf den der Standardsatz zeigen könnte.
        """
        result = self.session.last_result
        if result is None or not result.scene.objects:
            return False, tr(
                "Die Szene ist leer — ein Baustein wird auf einen Körper gesetzt. "
                "Lesen Sie zuerst ein Modell ein oder legen Sie einen Grundkörper an."
            )
        if not self.object_tree.selected_objects():
            return False, _needs_objects(1)
        return True, ""

    def _recipe_readiness(self) -> tuple[bool, str]:
        """Ob sich aus dem Stand ein eigener Baustein machen lässt — und sonst warum nicht.

        Drei Bedingungen, jede mit einem Satz statt eines grauen Knopfes
        (§2.7): etwas gerechnet, mindestens ein Schritt, mindestens ein
        Projektparameter. Die dritte ist die, die am ehesten fehlt — ohne sie
        wäre der Baustein starr, und das merkt der Kunde erst, wenn er ihn
        benutzt.
        """
        document = self.session.project.document
        if self.session.last_result is None:
            return False, tr("Dafür muss zuerst etwas gerechnet sein.")
        if not document.ops:
            return False, tr("Dieses Projekt hat noch keine Schritte.")
        if not document.parameters:
            return False, tr(
                "Legen Sie zuerst Projektparameter an und binden Sie die Maße daran, "
                "die am Baustein einstellbar sein sollen."
            )
        return True, ""

    def _adopt_part(self, catalog: PartCatalog) -> None:
        """Prüft und installiert eine lokale Bausteindatei.

        **Der Kern entscheidet, was mit ihr geschieht, nicht dieser Handler.**
        ``PartFileIO.install_file`` prüft Struktur, Ressourcen, Quellen und
        Geometrie, setzt die Herkunftsquittung und legt Datei, Katalogeintrag
        und Operation als eine Einheit an. Eine Namenskollision ersetzt
        nichts; der Befund nennt den freien Vorschlag.

        Die Herkunft besteht ausschließlich aus SHA-256 der exakten
        Eingangsbytes und UTC-Importzeit. Lokaler Pfad und Dateiname reisen
        nicht mit; eine gehostete oder veröffentlichte Quelle wird nicht
        behauptet.
        """
        source, _filter = QFileDialog.getOpenFileName(
            catalog,
            tr("Baustein hinzufügen"),
            "",
            f"{tr('Baustein hinzufügen')} (*{PART_FILE_SUFFIX} *.json)",
        )
        if not source:
            return
        self._import_part_path(catalog, Path(source))

    def _import_part_path(self, catalog: PartCatalog, source: Path) -> None:
        """Einen gewählten Pfad lesen und dem gemeinsamen Importarbeiter geben."""
        self._start_part_import(catalog, source)

    def _start_part_import(
        self,
        catalog: PartCatalog,
        source: bytes | Path,
        *,
        name: str | None = None,
    ) -> None:
        """Pfad und Prüfung im Arbeiter lesen, oder gelesene Bytes erneut prüfen."""
        self._clear_part_file_result(catalog)
        worker = _PartImportWorker(source, name)
        worker.done.connect(lambda installed: self._part_import_done(catalog, installed))
        worker.failed.connect(
            lambda error, payload: self._part_import_failed(
                catalog,
                cast(bytes | None, payload),
                cast(AppError, error),
            )
        )
        worker.crashed.connect(lambda detail: self._part_file_crashed(catalog, str(detail)))
        worker.finished.connect(lambda done=worker: self._part_file_worker_done(done))
        self._start_part_file_worker(
            worker,
            catalog.adopt_part,
            tr("Baustein hinzufügen"),
        )

    def _part_import_done(self, catalog: PartCatalog, installed: Any) -> None:
        """Den neuen Eintrag zeigen und die Herkunft dauerhaft ausweisen."""
        self._end_part_file_attempt()
        name = installed.recipe.name
        affected = self._part_usage(name)
        self._part_file_undo = ("remove", (name, installed.stored_sha256, affected))
        self._part_file_affected_step = affected[0] if affected else None
        catalog.invalidate_preview(name)
        catalog.refresh()
        text = self._part_usage_text(tr("Baustein hinzugefügt"), len(affected))
        catalog.show_file_result(
            text,
            part_name=name,
            can_undo=True,
            can_show_affected_step=bool(affected),
        )
        self.statusBar().showMessage(text, 8000)
        _log.info("part file imported: %s", installed.sha256)

    def _part_import_failed(
        self,
        catalog: PartCatalog,
        payload: bytes | None,
        problem: AppError,
    ) -> None:
        """Eine Ablehnung mit den zwei echten lokalen Auswegen zeigen."""
        self._end_part_file_attempt()
        self._show_part_import_error(problem, catalog, payload)

    def _show_part_import_error(
        self,
        problem: AppError,
        catalog: PartCatalog,
        payload: bytes | None = None,
    ) -> None:
        """Den Dateifehler mit lokalen, ausführbaren Handlungen verbinden."""
        handlers = self.error_handlers()
        handlers["choose"] = lambda _error: self._adopt_part(catalog)
        if payload is not None:
            handlers["use_suggested_name"] = lambda error: self._use_suggested_part_name(
                catalog, payload, error
            )
        show_error(problem, catalog, handlers)

    def _use_suggested_part_name(
        self,
        catalog: PartCatalog,
        payload: bytes,
        problem: AppError,
    ) -> None:
        """Den vom Kern gelieferten freien Namen ausdrücklich übernehmen."""
        suggested = problem.values.get("suggested_name")
        if isinstance(suggested, str) and suggested:
            self._start_part_import(catalog, payload, name=suggested)

    def _share_part(self, catalog: PartCatalog) -> None:
        """Exportiert den gewählten Baustein als lokale Bausteindatei.

        **Geschrieben wird über den einen lokalen Dateivertrag und nie über
        ``json.dumps(file_data(...))``.** Die eigene Serialisierung wäre ein
        zweiter Weg an Struktur-, Quellen- und Ressourcenprüfung vorbei.

        Der Baustein ist an dieser Stelle ein eigenes oder zuvor importiertes
        Rezept: Der Katalog sperrt den Knopf bei allem anderen und sagt, warum
        (``_share_state``). Seine geprüften Rezeptdaten stehen am Katalogeintrag
        selbst. Damit bleibt der Export auch nach einem Neustart und nach dem
        Verschieben der ursprünglich importierten Datei derselbe Kernweg.
        """
        from app.core.knowledge.parts.registry import PARTS

        name = catalog.chosen()
        if not name:
            return
        data = PARTS.get(name).recipe_data
        if data is None:
            show_error(
                ValidationError(
                    field="title",
                    detail=tr(
                        "Die Datei dieses Bausteins ließ sich nicht lesen. "
                        "Speichern Sie ihn neu, dann steht sie wieder."
                    ),
                    constraint="part_file_unavailable",
                    suggestions=(CANCEL,),
                ),
                catalog,
            )
            return

        target, _filter = QFileDialog.getSaveFileName(
            catalog,
            tr("Baustein weitergeben"),
            f"{name}{PART_FILE_SUFFIX}",
            f"{tr('Baustein weitergeben')} (*{PART_FILE_SUFFIX})",
        )
        if not target:
            return
        self._start_part_export(catalog, name, data, Path(target))

    def _start_part_export(
        self,
        catalog: PartCatalog,
        name: str,
        data: Mapping[str, Any],
        target: Path,
    ) -> None:
        """Prüfung und atomare Ausgabe ohne weiteren Dateidialog beginnen."""
        self._clear_part_file_result(catalog)
        self._write_failure = None
        worker = _PartExportWorker(data, target)
        worker.done.connect(
            lambda written: self._part_export_done(catalog, name, cast(Path, written))
        )
        worker.failed.connect(
            lambda error: self._part_export_failed(
                catalog,
                name,
                data,
                target,
                cast(AppError, error),
            )
        )
        worker.crashed.connect(lambda detail: self._part_file_crashed(catalog, str(detail)))
        worker.finished.connect(lambda done=worker: self._part_file_worker_done(done))
        self._start_part_file_worker(
            worker,
            catalog.share_part,
            tr("Baustein weitergeben"),
        )

    def _part_export_done(self, catalog: PartCatalog, name: str, _target: Path) -> None:
        """Die dauerhafte Rückmeldung am Baustein und in der Statuszeile zeigen."""
        self._end_part_file_attempt()
        self._write_failure = None
        text = tr("Baustein weitergegeben. Die Datei kann lokal hinzugefügt werden.")
        catalog.show_file_result(text, part_name=name)
        self.statusBar().showMessage(text, 8000)

    def _remove_part(self, catalog: PartCatalog, name: str) -> None:
        """Einen lokalen Baustein sofort entfernen; der Rückweg folgt im Ergebnis."""

        self._start_part_remove(catalog, name, None, self._part_usage(name))

    def _start_part_remove(
        self,
        catalog: PartCatalog,
        name: str,
        expected_sha256: str | None,
        affected: tuple[int, ...],
    ) -> None:
        """Eine bytegebundene Entfernung im Arbeiter beginnen."""

        self._clear_part_file_result(catalog)
        worker = _PartRemoveWorker(name, expected_sha256)
        worker.done.connect(lambda removed: self._part_remove_done(catalog, removed, affected))
        worker.failed.connect(
            lambda error: self._part_remove_failed(
                catalog,
                name,
                expected_sha256,
                affected,
                cast(AppError, error),
            )
        )
        worker.crashed.connect(lambda detail: self._part_file_crashed(catalog, str(detail)))
        worker.finished.connect(lambda done=worker: self._part_file_worker_done(done))
        self._start_part_file_worker(worker, catalog.remove_part, tr("Baustein entfernen"))

    def _part_remove_done(
        self,
        catalog: PartCatalog,
        removed: Any,
        affected: tuple[int, ...],
    ) -> None:
        """Entfernung, Verwendungsort und bytegenauen Rückweg sichtbar halten."""

        self._end_part_file_attempt()
        name = removed.recipe.name
        self._part_file_undo = ("restore", (removed.undo, affected))
        self._part_file_affected_step = affected[0] if affected else None
        catalog.invalidate_preview(name)
        catalog.refresh()
        text = self._part_usage_text(tr("Baustein entfernt"), len(affected))
        catalog.show_file_result(
            text,
            can_undo=True,
            can_show_affected_step=bool(affected),
        )
        self.statusBar().showMessage(text, 8000)

    def _part_remove_failed(
        self,
        catalog: PartCatalog,
        name: str,
        expected_sha256: str | None,
        affected: tuple[int, ...],
        problem: AppError,
    ) -> None:
        """Eine gescheiterte Entfernung mit demselben sicheren Versuch verbinden."""

        self._end_part_file_attempt()
        handlers = self.error_handlers()
        handlers["retry"] = lambda _error: self._start_part_remove(
            catalog, name, expected_sha256, affected
        )
        show_error(problem, catalog, handlers)

    def _start_part_restore(
        self,
        catalog: PartCatalog,
        token: Any,
        affected: tuple[int, ...],
    ) -> None:
        """Den unveränderten Kern-Rücknahmetoken im Arbeiter wiederherstellen."""

        self._clear_part_file_result(catalog)
        worker = _PartRestoreWorker(token)
        worker.done.connect(
            lambda installed: self._part_restore_done(catalog, installed, token, affected)
        )
        worker.failed.connect(
            lambda error: self._part_restore_failed(catalog, token, affected, cast(AppError, error))
        )
        worker.crashed.connect(lambda detail: self._part_file_crashed(catalog, str(detail)))
        worker.finished.connect(lambda done=worker: self._part_file_worker_done(done))
        self._start_part_file_worker(worker, catalog.file_undo, tr("Baustein wiederherstellen"))

    def _part_restore_done(
        self,
        catalog: PartCatalog,
        installed: Any,
        _token: Any,
        affected: tuple[int, ...],
    ) -> None:
        """Wiederhergestellten Eintrag neu rendern und erneut rücknehmbar machen."""

        self._end_part_file_attempt()
        name = installed.recipe.name
        self._part_file_undo = ("remove", (name, installed.stored_sha256, affected))
        self._part_file_affected_step = affected[0] if affected else None
        catalog.invalidate_preview(name)
        catalog.refresh()
        text = self._part_usage_text(tr("Baustein wiederhergestellt"), len(affected))
        catalog.show_file_result(
            text,
            part_name=name,
            can_undo=True,
            can_show_affected_step=bool(affected),
        )
        self.statusBar().showMessage(text, 8000)

    def _part_restore_failed(
        self,
        catalog: PartCatalog,
        token: Any,
        affected: tuple[int, ...],
        problem: AppError,
    ) -> None:
        """Eine gescheiterte Wiederherstellung am unveränderten Token wiederholen."""

        self._end_part_file_attempt()
        handlers = self.error_handlers()
        handlers["retry"] = lambda _error: self._start_part_restore(catalog, token, affected)
        show_error(problem, catalog, handlers)

    def _undo_part_file(self, catalog: PartCatalog) -> None:
        """Nur die sichtbare Bibliothekshandlung zurücknehmen, nie die Szene."""

        pending = self._part_file_undo
        if pending is None:
            return
        kind, data = pending
        if kind == "remove":
            name, expected_sha256, affected = cast(tuple[str, str, tuple[int, ...]], data)
            self._start_part_remove(catalog, name, expected_sha256, affected)
            return
        token, affected = cast(tuple[Any, tuple[int, ...]], data)
        self._start_part_restore(catalog, token, affected)

    def _clear_part_file_result(self, catalog: PartCatalog) -> None:
        """Eine alte Ergebnisaktion vor der nächsten Bibliothekshandlung einziehen."""

        self._part_file_undo = None
        self._part_file_affected_step = None
        catalog.show_file_result("")

    def _part_usage(self, name: str) -> tuple[int, ...]:
        """Schritte des offenen Dokuments, die den Bibliotheksbaustein verwenden."""

        operation = part_op_name(name)
        return tuple(
            entry.id for entry in self.session.project.document.ops if entry.op == operation
        )

    @staticmethod
    def _part_usage_text(text: str, count: int) -> str:
        """Eine Bibliotheksmeldung um die sichtbare Auswirkung im Verlauf ergänzen."""

        if count == 1:
            usage = tr("Der Baustein wird in einem Schritt des geöffneten Projekts verwendet.")
        elif count > 1:
            usage = tr(
                "Der Baustein wird in {count} Schritten des geöffneten Projekts verwendet."
            ).format(count=count)
        else:
            return text
        return f"{text}. {usage}"

    def _show_part_affected_step(self, catalog: PartCatalog) -> None:
        """Den Katalog schließen und den ersten betroffenen Verlaufsschritt zeigen."""

        op_id = self._part_file_affected_step
        if op_id is None:
            return
        catalog.reject()
        if self.history_panel.point_at(op_id):
            open_section(self.history_panel)

    def _part_export_failed(
        self,
        catalog: PartCatalog,
        name: str,
        data: Mapping[str, Any],
        target: Path,
        problem: AppError,
    ) -> None:
        """Denselben Zielpfad oder einen neuen Ort als echte Handlung anbieten."""
        self._end_part_file_attempt()
        self._write_failure = _WriteFailure(
            again=partial(self._start_part_export, catalog, name, data, target),
            elsewhere=partial(self._share_part, catalog),
        )
        show_error(problem, catalog)

    def _start_part_file_worker(
        self,
        worker: Worker,
        button: Any,
        text: str,
    ) -> None:
        """Einen lokalen Dateilauf sichtbar und gegen Doppelklick geschützt starten."""
        previous = self._part_file_worker
        if previous is not None and previous.isRunning():
            # Das Fehlersignal kommt unmittelbar vor dem Thread-Ende. Klickt
            # der Kunde seine Handlung sofort, darf dieser kurze Auslauf den
            # neuen Versuch nicht verschlucken; die Halteleine übernimmt ihn.
            self._retire(previous)
        self._part_file_worker = worker
        self._part_file_button = button
        button.setEnabled(False)
        self._set_progress_state(
            "part_file",
            active=True,
            text=text,
            minimum=0,
            maximum=0,
            value=0,
            accessible_description=text,
        )
        self._update_waiting_state()
        self._leash.start(worker)

    def _end_part_file_attempt(self) -> None:
        """Fortschritt und Knopfsperre nach jedem Ausgang zuverlässig lösen."""
        self._set_progress_state("part_file", active=False)
        button = self._part_file_button
        self._part_file_button = None
        if button is not None and isValid(button):
            button.setEnabled(True)
        self._progress_idle()

    def _part_file_crashed(self, catalog: PartCatalog, detail: str) -> None:
        """Auch ein unerwarteter Workerfehler lässt keinen Wartezustand zurück."""
        self._end_part_file_attempt()
        show_error(InternalError(detail=detail), catalog)

    def _part_file_worker_done(self, worker: Any) -> None:
        if self._part_file_worker is worker:
            self._part_file_worker = None
        self._hold_until_done(worker)

    def _save_as_part(self, catalog: PartCatalog) -> None:
        """Öffnet den Rezeptdialog über dem Katalog (Konzept §16, Schritt 4 und 5).

        **Genommen wird, was im Verlauf gewählt ist — sonst der ganze Stapel.**
        Das Konzept spricht von einem Ausschnitt, und ``capture`` nimmt dafür
        ``op_ids``; bis der Verlauf eine Mehrfachauswahl bekam, wanderte
        mangels Auswahl immer alles mit. Das fehlt selten und dann deutlich:
        Wer sein Teil gerade gebaut hat, meint ohnehin den ganzen Stapel — wer
        aus einem gewachsenen Projekt *einen* Halter herauslöst, bekam einen
        Baustein, der Dinge baut, die niemand bestellt hat.

        Die leere Auswahl heißt weiter „alles", und zwar ausdrücklich: Sie ist
        der häufige Fall, und ein Dialog, der bei nichts Gewähltem nichts
        anbietet, wäre eine Hürde ohne Gewinn. Was er nimmt, schreibt der
        Dialog in seine Kopfzeile, damit die Vorgabe nicht stillschweigend
        gilt.

        **Lücken werden nicht abgefangen**, und das ist eine Entscheidung: Ein
        Ausschnitt aus Schritt 3 und 7 ohne 4 bis 6 kann sinnvoll sein — wenn
        die Zwischenschritte einen anderen Körper betreffen — oder unsinnig.
        Welches von beidem, weiß der Bereichstest in ``capture``, der ohnehin
        vor dem Speichern läuft und sagt, was dabei herauskommt. Eine Regel im
        Dialog müsste dieselbe Frage schlechter beantworten.
        """
        result = self.session.last_result
        document = self.session.project.document
        if result is None:
            return
        # **Die IDs der Schritte, nicht ihre Plätze.** ``capture`` filtert nach
        # ``Operation.id``, und die zählt ab eins; ``enumerate`` ab null. Mit
        # Indizes fiel der **letzte** Schritt jedes Stapels still aus dem
        # Rezept — beim Weg-2-Halter die Versteifung. Gefunden am 25.08.2026 im
        # echten Fenster: Das gespeicherte Rezept trug drei von vier Schritten,
        # und der Bereichstest war trotzdem grün, denn drei Schritte ergeben
        # auch einen Körper.
        whole = tuple(op.id for op in document.ops)
        chosen = self.history_panel.selected_operations()
        dialog = RecipeDialog(
            document,
            dict(self.session.project.sources),
            chosen or whole,
            self._result_features(),
            self.session.profile,
            parent=catalog,
        )
        # ``refresh``, nicht ``show_parts``: ``saved`` trägt den **Namen** des
        # Rezepts, und ``show_parts`` versteht sein Argument als Suchtext. So
        # verbunden zeigte der Katalog nach dem Speichern nur noch den neuen
        # Baustein — bei leerem Suchfeld, also ohne dass der Kunde sähe,
        # warum. Gefunden am 25.08.2026 im echten Fenster.
        dialog.saved.connect(catalog.refresh)
        dialog.saved.connect(self._part_saved)
        try:
            dialog.exec()
        finally:
            dialog.release()
            dialog.deleteLater()

    def _result_features(self) -> tuple[Feature, ...]:
        """Jedes erkannte und erzeugte Merkmal des gerechneten Standes.

        Eigene Methode und keine Zeile im Aufruf darüber: **Szene und Körper
        führen ihre Inhalte als Wörterbücher.** Über sie zu iterieren gibt
        Kennungen statt Objekte, und der Dialog fragte danach nach ``.id`` einer
        Zeichenkette — ein Fehler, der erst beim ersten echten Klick auffällt,
        weil ein Test mit Attrappen ihn nicht berührt. Als Methode hat er eine
        Stelle, an der er geprüft werden kann.
        """
        result = self.session.last_result
        if result is None:
            return ()
        return tuple(
            feature
            for scene_object in result.scene.objects.values()
            for feature in scene_object.features.values()
        )

    def _part_saved(self, name: str, range_passed: bool = True) -> None:
        """Ein eigener Baustein ist entstanden — sagen, wo er steht.

        **Und ob sein Bereichstest bestand.** Der Dialog konnte das nicht
        sagen: Er setzte den Warnsatz und rief einen Atemzug später
        ``accept()``, womit ihn niemand las (3d-druck-43, Gesamtreview K-15).
        §24.5 verlangt den Hinweis, nicht die Verweigerung — der Baustein ist
        angelegt und steht im Katalog, er trägt nur die Warnung mit.
        """
        if range_passed:
            self.announce(
                tr("Der Baustein steht im Katalog. Er gehört Ihnen und bleibt auf diesem Rechner.")
            )
        else:
            self.announce(
                tr(
                    "Der Baustein steht im Katalog — aber an den Grenzen kam kein "
                    "brauchbarer Körper heraus. Der Katalog zeigt das an; engere "
                    "Grenzen beheben es."
                )
            )
        _log.info("own part saved: %s (range passed: %s)", name, range_passed)

    def action_calibrate(self) -> None:
        """§28.3: gemessene Werte ins Materialprofil, und alles folgt."""
        material = self.session.project.document.material or self.session.profile.material.id
        dialog = CalibrationDialog(material, self)
        if dialog.exec() != CalibrationDialog.DialogCode.Accepted:
            return
        try:
            calibrated = calibration.apply(dialog.measured())
        except AppError as error:
            show_error(error, self)
            return
        self.announce(
            f"{tr('Kalibriert')}: {calibrated.id} · {tr('Spiel')} "
            + localised(f"{calibrated.clearance:.2f} mm")
        )
        # Toleranzen sind Verweise (§12), die Szene muss also neu gebaut werden.
        self.session.evaluate_async()

    def action_llm_key(self) -> None:
        """§27: der eigene Schlüssel des Nutzers, in den Schlüsselbund, und der
        Chat wacht auf.

        **Auch nach „Abbrechen".** Der Dialog nimmt nicht nur einen Schlüssel
        an: Er startet Ollama und holt ein Modell, und beides ist getan, sobald
        es getan ist. Wer diese zwei Schritte machte und dann abbrach — weil er
        gar keinen Schlüssel eintragen wollte —, hatte alles richtig gemacht
        und einen Chat, der grau blieb. Aufgefrischt wird deshalb in jedem
        Fall; was der Dialog verändert hat, weiß er selbst nicht besser als
        eine neue Prüfung.
        """
        KeyDialog(parent=self, settings=self.settings).exec()
        self.session.set_agent_backend(None)
        self._refresh_chat_availability(probe_local=True)

    def _refresh_chat_availability(self, probe_local: bool = False) -> None:
        """Der eine Ort, an dem der Chat-Zustand gelesen wird.

        Vorher stand derselbe Dreizeiler an drei Stellen. Dazu die Prüfung aus
        §27: wacht der Chat über das lokale Modell auf, fragt ein Arbeiter die
        Modellgröße ab — im Hintergrund, denn ein Start, der auf einen
        HTTP-Aufruf wartet, wäre der Fehler der Update-Prüfung noch einmal.

        ``probe_local`` gilt nur für Einrichtungs-Anlässe (erster Start,
        Schlüsseldialog): der stille Fensterbau startet keinen Arbeiter, dessen
        Leben an einer HTTP-Antwort hängt — Tests und Screenshot-Werkzeuge
        bauen Fenster und warten auf keinen. Und einmal bei der Einrichtung
        gesagt ist genug — bei jedem Start wäre es Nörgeln (§27).
        """
        backend = self.session.agent_backend
        self.chat.set_available(
            backend is not None, f"{backend.id}:{backend.model}" if backend else ""
        )
        self.chat.set_notice("")
        # Nach set_available, denn die Sperre überschreibt dessen Hinweis:
        # §2 C zählt den Chat zur schreibenden Seite, mit oder ohne Modell.
        self.chat.set_locked(not activation.state().unlocked)
        if not probe_local or backend is None or backend.id != "ollama":
            return
        worker = _OllamaSizeWorker(backend.model)
        worker.done.connect(self._ollama_size_answered)
        # Ein Absturz der Messung ist kein Fall für einen Dialog — sie läuft
        # unsichtbar im Hintergrund, und ihr Ausfall kostet nur den Hinweis.
        # Aber taub sein darf sie nicht: ohne Empfänger verschwände der Grund
        # spurlos (Gesamtreview I-2).
        worker.crashed.connect(self._ollama_size_crashed)
        self._retire(self._ollama_size_worker)
        self._ollama_size_worker = worker
        worker.finished.connect(lambda done=worker: self._ollama_size_worker_done(done))
        self._leash.start(worker)

    def _ollama_size_worker_done(self, worker: Any) -> None:
        if self._ollama_size_worker is worker:
            self._ollama_size_worker = None
        self._hold_until_done(worker)

    def _ollama_size_crashed(self, detail: str) -> None:
        """Die Messung ist ein Angebot — ihr Ausfall lässt den Chat ohne
        Warnhinweis, nicht das Fenster ohne Auskunft."""
        _log.warning("ollama size probe crashed: %s", detail)

    def _ollama_size_answered(self, warning: Any) -> None:
        """Was zum lokalen Modell zu sagen ist, steht an der Chatleiste.

        Zwei Sorten Satz: die Warnung, wenn etwas nicht laufen wird — und
        sonst die gemessene Erwartung. Ohne die zweite erlebt jemand das
        Ergebnis als Fehler der Anwendung: ein Zug, der zwei Minuten braucht
        und dann das falsche Werkzeug ruft, sieht danach aus und ist eine
        Eigenschaft des Modells.
        """
        self.chat.set_notice(str(warning if warning is not None else llm.local_model_expectation()))

    def action_settings(self) -> None:
        """§19.3, §38: alles, was die Anwendung sich merkt, an einer Stelle.

        Alles wirkt sofort — Thema, Einheit, Navigation, Farben, und seit dem
        Erststart-Weg auch die Sprache: ``languageChanged`` meldet den
        Wechsel, und ``app.py`` baut das Fenster mit derselben Sitzung neu.
        Ohne Rückfrage, aus demselben Grund wie dort: Der Dialog ist modal,
        offen ist sonst nichts, und Dokument samt Verlauf wandern mit.
        """
        # Was an den Feldern umgeschaltet wurde, gehört in die Einstellungen,
        # bevor der Dialog sie liest und zurückschreibt.
        self.settings.circle_measure = circle_measure()
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        spoken = self.settings.language
        dialog.apply_to(self.settings)
        save_settings(self.settings)
        self._apply_settings()
        self._apply_remote()
        if self.settings.language != spoken:
            self.languageChanged.emit()

    def _apply_settings(self) -> None:
        """Trägt die Einstellungen dorthin, wo sie wirken."""
        application = QApplication.instance()
        if application is not None:
            apply_theme(application, self.settings.theme)  # type: ignore[arg-type]
        self.viewport.set_theme(self.settings.theme)
        # Der Einstellungsdialog kann das Thema wechseln, und die schwebenden
        # Karten hingen bisher an ``action_theme`` allein: über den Dialog
        # gewechselt, behielten sie die Farben des alten Themas.
        self._apply_card_style(self.settings.theme)
        self.viewport.set_navigation(self.settings.navigation)  # type: ignore[arg-type]
        self.viewport.set_difference_palette(self.settings.diff_palette)  # type: ignore[arg-type]
        # Was der Nutzer zuletzt eingestellt hat, gilt wieder — und die
        # Häkchen im Menü zeigen es. Über den Viewport und nicht über die
        # ``action_``-Methoden: Beim Start ist nichts zu speichern, und ein
        # Schreiben in die Einstellungen bei jedem Programmstart wäre eine
        # Änderung, die niemand gemacht hat.
        self.viewport.set_display_mode(self.settings.display_mode)  # type: ignore[arg-type]
        self.viewport.set_shading(self.settings.shading)  # type: ignore[arg-type]
        self.viewport.set_projection(self.settings.projection)  # type: ignore[arg-type]
        _tick(self._mode_group, self.settings.display_mode)
        _tick(self._shading_group, self.settings.shading)
        _tick(self._projection_group, self.settings.projection)
        self.set_display_unit(self.settings.display_unit)
        set_circle_measure("radius" if self.settings.circle_measure == "radius" else "diameter")

    def set_display_unit(self, unit: str) -> None:
        """§19.3: Millimeter oder Zoll — in der Anzeige, nie im Kern.

        Die Einstellung gab es seit P0 und niemanden, der sie las. Dann lasen
        sie drei Stellen, und der Test dazu hieß trotzdem „reaches everything
        that shows a length" — geprüft hat er zwei. Die übrigen elf
        Längenausgaben standen auf der Vorgabe „mm": der ganze Skizzeneditor,
        die Analyseleiste, die Schnittleiste und die Merkmalsbeschriftungen.
        Wer auf Zoll stellte, las im selben Fenster beides.

        Gesetzt wird deshalb der **Zustand** (``labels.set_display_unit``), dem
        jede Ausgabe ohne ausdrückliche Einheit folgt. Hier bleibt, die
        Ansichten neu zeichnen zu lassen: Ein Zustand wirkt erst, wenn etwas
        ihn wieder liest.

        **Die Kopfzeile hing dabei einen Schritt nach.** Sie liest die
        Einstellung selbst, wurde aber nur bei Profil- oder Auswertungswechsel
        neu geschrieben — und ``action_settings`` sagt zu, die Einheit wirke
        sofort.

        Analyse- und Schnittleiste folgen erst beim nächsten Zeichnen: Sie
        halten die Werte nicht, aus denen ihre Zeilen entstehen, und ihnen
        eine Datenhaltung dafür zu geben ist ein eigener Schritt. Das steht so
        in der Arbeitsliste, statt hier als stille Lücke.

        **Die Druckeinstellungen bleiben in Millimetern**, mit Absicht: Ihre
        Werte gehen so an den Slicer, wie er sie führt, und wer dort eine
        Schichthöhe von 0,2 mm liest, findet sie im Slicer wieder; in Zoll
        fände er sie nicht.
        """
        set_length_unit(unit)  # type: ignore[arg-type]
        self.measurements.set_unit(unit)  # type: ignore[arg-type]
        self.object_tree.set_unit(unit)  # type: ignore[arg-type]
        self._on_selection(self.object_tree.selected())
        self._update_header()
        # Die Merkmalsbeschriftungen in der Überlagerung schreiben Längen ohne
        # eigene Einheit; sie brauchen nur den Anstoß, es neu zu tun.
        self.viewport.refresh_labels()
        # **Und jedes Längenfeld im Fenster.** ``LengthSpin`` zieht von sich aus
        # nur beim Einblenden nach (``showEvent``); eine Leiste, die gerade
        # offen steht, behielt ihr altes Suffix, während der Rest der Anwendung
        # umgestellt hatte. Solange die Leisten nur Anzeigen trugen, war das
        # eine Unschönheit — seit die Bewegen-Leiste Eingabefelder hat, steht
        # dort „mm" über einem Fenster, das in Zoll rechnet.
        #
        # Gesucht wird über den Widgetbaum und nicht über eine Liste von
        # Leisten: Eine Liste vergisst die nächste. ``refresh_unit`` steigt von
        # selbst aus, wo nichts zu tun ist.
        for field in self.findChildren(LengthSpin):
            field.refresh_unit()

    def window_commands(self) -> dict[str, tuple[str, str, Any]]:
        """Was die Palette außer den Operationen kennen muss (§2.6, §19.2).

        „Alles aus dem Register" war zu wenig: Speichern, das Handbuch, die
        Darstellungsarten und die sieben Ansichtswerkzeuge stehen nicht im
        Register, und die Palette soll der Universalzugang sein. Kennung,
        Titel, Kürzel und was zu tun ist.
        """
        commands: dict[str, tuple[str, str, Any]] = {
            "file.new": (tr("Neu"), "Ctrl+N", self.action_new),
            "file.open": (tr("Öffnen …"), "Ctrl+O", self.action_open),
            "file.save": (tr("Speichern"), "Ctrl+S", self.action_save),
            "file.import": (tr("Modell einfügen …"), "Ctrl+I", self.action_import),
            "file.export": (tr("Exportieren …"), "Ctrl+E", self.action_export),
            "file.print_settings": (
                tr("Druckeinstellungen …"),
                "Ctrl+P",
                self.action_print_settings,
            ),
            "file.catalog": (tr("Bausteinkatalog …"), "Ctrl+K", self.action_catalog),
            "file.part_adopt": (
                tr("Baustein aus Datei hinzufügen …"),
                "",
                self.action_adopt_part_file,
            ),
            "file.part_share": (
                tr("Baustein als Datei weitergeben …"),
                "",
                self.action_share_part_file,
            ),
            "edit.settings": (tr("Einstellungen …"), "Ctrl+,", self.action_settings),
            "edit.undo": (tr("Rückgängig"), "Ctrl+Z", self.action_undo),
            "edit.redo": (tr("Wiederholen"), "Ctrl+Y", self.action_redo),
            "edit.add_parameter": (
                tr("Parameter anlegen …"),
                "",
                self.action_add_parameter,
            ),
            "edit.auto_split": (tr("Automatisch teilen …"), "", self.action_auto_split),
            "view.fit": (tr("Einpassen"), "Home", self.viewport.reset_camera),
            "view.toggle_right": (tr("Rechten Bereich zeigen"), "F9", self.action_toggle_right),
            "view.bed": (tr("Druckplatte zeigen"), "Ctrl+Shift+D", self.action_toggle_bed),
            "help.manual": (tr("Handbuch …"), "F1", self.action_manual),
        }
        for key, tool in self.tools.tools().items():
            commands[f"tool.{key}"] = (
                f"{strip_title()}: {tool.title}",
                tool.shortcut,
                lambda name=key: self.tools.toggle(name),
            )
        commands.update(self._menu_commands(commands))
        return commands

    def _menu_commands(self, known: dict[str, tuple[str, str, Any]]) -> dict[str, Any]:
        """Alles Übrige aus der Menüleiste — sie ist die Quelle, nicht eine
        zweite Liste daneben.

        §19.2 verlangt die Palette als Universalzugang, und das Wörterbuch
        darüber führte sie von Hand. Von Hand heißt: Es driftet, und es war
        gedriftet — **39 von 136 Menüzeilen fehlten**, darunter jede
        Darstellungsart, jede Kameravorgabe, beide Themen, alle vier
        Navigationsschemata und acht Zeilen aus dem Hilfe-Menü. Nachzutragen
        hätte den nächsten Eintrag wieder vergessen lassen; aus der Leiste
        gelesen kann das nicht mehr passieren.

        Die Operationen bleiben draußen: Sie kommen aus dem Register und
        tragen dort ihre Beschreibung, ihre Kategorie und ihre Verfügbarkeit —
        über das Menü gelesen wären sie ein zweites, ärmeres Exemplar.

        **Zwei Zeilen bleiben ebenfalls draußen**, und beide mit Grund:
        *Beenden* wäre in einer Liste, durch die man tippt, ein Klick zu nah am
        Verlust der Arbeit, und *Befehlspalette* öffnete sich selbst.
        """
        known_titles = {title for title, _shortcut, _slot in known.values()}
        # Und wo dieselbe Handlung schon von Hand in der Tabelle steht, wird
        # ihre Action **trotzdem** gemerkt: Exportieren, Rückgängig,
        # Wiederholen und Automatisch teilen stehen dort mit einer gebundenen
        # Methode, und eine Methode weiß nicht, ob sie darf. Vier der fünf
        # gesperrten Befehle eines leeren Projekts sind genau diese vier — sie
        # nur über die Menüschleife zu finden hätte einen von fünf erwischt.
        by_title = {title: key for key, (title, _shortcut, _slot) in known.items()}
        ops = set(self._op_actions.values())
        found: dict[str, Any] = {}
        self._palette_actions.clear()
        for path, action in _menu_lines(self.menuBar()):
            if action in ops:
                continue
            if action.text() in known_titles:
                self._palette_actions[by_title[action.text()]] = action
                continue
            if action in (self._quit_action, self._palette_action):
                continue
            # Der Weg steht im Titel: „Vorne" allein sagt in einer Liste aus
            # hundert Zeilen nichts, „Kamera: Vorne" schon.
            title = f"{path}: {action.text()}" if path else action.text()
            key = f"menu.{len(found)}"
            found[key] = (
                title,
                action.shortcut().toString(),
                action.trigger,
            )
            # **Und die Action wird gemerkt.** Sie ist die einzige Quelle
            # dafür, ob dieser Befehl jetzt geht — die Operationen der Palette
            # lesen sie längst (``_palette_availability``), die
            # Fensterbefehle taten es nicht: Sie standen alle gleich da, und
            # „Rückgängig" ohne Verlauf nahm den Klick an und tat nichts. Bei
            # leerem Projekt sind das fünf von 54 (Exportieren, Rückgängig,
            # Wiederholen, Varianten, Automatisch teilen).
            #
            # Als Tabelle daneben und nicht als vierter Wert im Tupel:
            # ``window_commands`` hat sechs Aufrufstellen, die drei auspacken,
            # und eine Signatur zu ändern, um eine Frage zu beantworten, ist
            # der teurere Weg zum selben Ergebnis.
            self._palette_actions[key] = action
        return found

    def _extra_availability(self, key: str) -> tuple[bool, str]:
        """Ob ein Fensterbefehl jetzt ausführbar ist, und warum nicht.

        Dieselbe Auskunft wie ``_palette_availability`` für die Operationen,
        aus derselben Quelle: der Action, die auch das Menü ausgraut. Was von
        Hand in ``window_commands`` steht und keine Action hat — Speichern,
        das Handbuch, „Einpassen" — kann immer.
        """
        action = self._palette_actions.get(key)
        if action is None or action.isEnabled():
            return True, ""
        hint = action.toolTip().strip()
        if hint and hint != action.text().replace("&", "").strip():
            return False, hint
        return False, tr("Das geht gerade nicht.")

    def selected_feature_kind(self) -> str | None:
        """Die Art des gerade ausgewählten Merkmals — ``hole``, ``face`` und
        so fort, oder ``None``.

        Sie entscheidet, was die Befehlspalette zuerst zeigt (Konzept P15 §5,
        E13). Dieselbe Auskunft, aus der auch das Kontextmenü gebaut wird, nur
        an der anderen Stelle gefragt.
        """
        feature_id = self.object_tree.selected_feature()
        selected = self.object_tree.selected()
        result = self.session.last_result
        if not feature_id or selected is None or result is None:
            return None
        entry = result.scene.objects.get(selected)
        feature = entry.features.get(feature_id) if entry else None
        return feature.kind if feature is not None else None

    def _selected_face_plane(self) -> str:
        """Die gewählte Fläche als Zeichenebene — leer, wenn keine gewählt ist.

        Dieselbe Auskunft, aus der Palette und Kontextmenü ihre Vorschläge
        bauen, nur als eindeutigen Ebenennamen des Kerns. Ob die Fläche als
        Zeichenebene taugt, entscheidet danach ``choose_plane`` — hier wird
        nur weitergegeben, was der Nutzer schon gesagt hat.
        """
        if self.selected_feature_kind() != "face":
            return ""
        object_id = self.object_tree.selected()
        feature_id = self.object_tree.selected_feature()
        if object_id is None or feature_id is None:
            return ""
        return feature_plane(object_id, feature_id)

    def _drawable_faces(self) -> list[tuple[str, str, tuple[float, float, float]]]:
        """Die planaren Flächen der Szene, auf denen gezeichnet werden kann.

        Nach Fläche absteigend: auf einer Deckplatte zeichnet man, auf einer
        Fase von zwei Quadratmillimetern nicht, und eine Liste in
        Erkennungsreihenfolge stellte beide gleichberechtigt nebeneinander.
        Der Deckel steht damit oben, wo er hingehört.

        Die Beschriftung nennt Objekt, Größe und Lage — eine Feature-ID allein
        („face_7") sagt niemandem, welche Fläche gemeint ist. Ausgewählt wird
        sie ohnehin im Baum oder im Viewport; hier muss man sie nur
        wiedererkennen.
        """
        result = self.session.last_result
        if result is None:
            return []
        found: list[tuple[float, str, str, tuple[float, float, float]]] = []
        for object_id, entry in result.scene.objects.items():
            for feature_id, feature in entry.features.items():
                if feature.kind != "face":
                    continue
                size = float(feature.params.get("area", 0.0))
                normal = feature.params.get("normal", (0.0, 0.0, 1.0))
                label = tr("Fläche an {object} — {area}, {side}").format(
                    object=entry.name,
                    # Die Einheit gehört in den Wert und nicht in den Satz: In
                    # Zoll steht dort „in²", und ein Satz mit eingebautem „mm²"
                    # könnte das nicht sagen.
                    area=area_label(size),
                    side=_face_side(normal),
                )
                found.append(
                    (
                        size,
                        feature_plane(object_id, feature_id).removeprefix("feature:"),
                        label,
                        (float(normal[0]), float(normal[1]), float(normal[2])),
                    )
                )
        found.sort(key=lambda row: -row[0])
        return [(feature_id, label, normal) for _area, feature_id, label, normal in found]

    # --- Skizzenmodus (§30.1 Stufe zwei) ----------------------------------------

    def _escape(self) -> None:
        """Escape verlässt, was gerade offen ist — ein Werkzeug oder die Skizze.

        Eine laufende Trennsuche zuerst, dann die Skizze: Beide liegen vor der
        Auswahl, und wer dort arbeitet, meint mit Escape die aktuelle Handlung
        statt einer Ebene darunter. Verworfen wird dabei nichts Gerechnetes.
        """
        if self.session.split_running:
            # Die lange Suche ist die oberste laufende Handlung. Erst sie
            # anhalten; die Auswahl darunter bleibt stehen und zeigt weiter,
            # welches Modell unverändert blieb.
            self.session.cancel_split()
            return
        if self._sketch_panel is not None:
            # Zwei Stufen: erst das Zeichenwerkzeug ablegen, dann die Skizze
            # verlassen. Vorher lag auf dieser Taste auch ein Kürzel des
            # Editors, und Qt führte deshalb **keines** von beiden aus — es
            # meldete ``activatedAmbiguously`` und tat nichts.
            if self._sketch_panel.drop_tool():
                return
            self.finish_sketch(keep=False)
            return
        if self._armature_target is not None:
            # Wie beim Formen: Escape beendet und verwirft nicht.
            self.finish_armature()
            return
        if self._sculpt_target is not None:
            # Nicht verwerfen: Escape beendet die Sitzung wie „Fertig", und
            # was dabei entsteht, nimmt ein Undo zurück (Regel 19). Ein
            # Escape, das stundenlange Arbeit wegwirft, wäre die teuerste
            # Taste des Programms.
            self.finish_sculpt()
            return
        if self.tools.active() is not None:
            self.tools.close_tool()
            return
        # Zuletzt der Weg aus der Auswahl heraus. Nur wenn kein Werkzeug offen
        # war: Wer eines geöffnet hat, meint mit Escape das Werkzeug.
        self._step_selection_out()

    def _step_selection_out(self) -> bool:
        """Escape geht eine Stufe zurück: Merkmal → Körper → nichts (§18.5).

        Der Gegenweg zur gestuften Auswahl im Viewport
        (:meth:`Viewport._click_target`). Ohne ihn ist die Tiefe eine
        Einbahnstraße: Wer eine Bohrung gewählt hat, kam nur wieder zum ganzen
        Teil, indem er neben das Modell klickte und von vorn anfing — und wer
        gar nichts mehr gewählt haben wollte, musste es zweimal tun.

        Dieselbe Aufteilung haben Figma und Illustrator (Escape verlässt die
        Gruppe, in die man hineingeklickt hat) und Onshape (Escape und
        Leertaste räumen die Auswahl). Der Unterschied zu Onshape ist die
        Stufe: Dort räumt Escape alles in einem Zug, hier eine Ebene, weil hier
        eine Ebene dazwischenliegt.

        Gestellt wird die Frage dem Viewport, gestellt wird die Auswahl im
        Objektbaum — er ist ihr Eigentümer, und beide Ansichten zeigen eine
        Auswahl (§18.5). Gibt zurück, ob etwas zurückgenommen wurde.
        """
        depth = self.viewport.selection_depth()
        if depth == 0:
            return False
        # Auf Stufe 2 bleibt der Körper und das Merkmal fällt weg; auf Stufe 1
        # fällt der Körper weg. ``select_object`` räumt den Baum und setzt neu,
        # und dabei geht ``featureSelected(None)`` mit hinaus.
        self.object_tree.select_object(self.object_tree.selected() if depth > 1 else None)
        return True

    def sketching(self) -> bool:
        """Ob gerade gezeichnet wird statt betrachtet."""
        return self._sketch_panel is not None

    def _sketch_surroundings(self) -> Surroundings:
        """Was eine Zeichenfläche von der Szene wissen soll (§30.1, E1, E18).

        Eine Stelle für beide Wege: den Skizzenmodus und das Skizzenfeld im
        Operationsdialog. Getrennt gepflegt war das Feld ärmer als der Modus —
        ohne Bauraumrand, ohne die Flächen der Körper in der Ebenenwahl, und
        *Projizieren* meldete „kein Körper" an einem Modell, das im Fenster
        stand.

        Der Bauraum steht im Profil, es braucht also keine Rechnung — nur die
        Zahl an der richtigen Stelle. Von den Objekten reisen die Netze mit und
        nicht die Szene: der Zeichenbereich braucht die Kante, nicht das Objekt
        darum.
        """
        volume = self.session.profile.printer.build_volume
        result = self.session.last_result
        return Surroundings(
            bed=(float(volume[0]), float(volume[1])),
            faces=tuple(self._drawable_faces()),
            bodies=tuple(entry.mesh for entry in result.scene.objects.values()) if result else (),
            frame_of=self._plane_frame,
        )

    def _plane_frame(self, plane: str) -> PlaneFrame | None:
        """Der Rahmen zu einer Ebenenangabe, gegen die aktuelle Szene.

        Fürs Projizieren auf einer Flächenebene (Gesamtreview D-9): Die
        Zeichenfläche kennt die Szene nicht, hier steht sie."""
        result = self.session.last_result
        objects = result.scene.objects.values() if result else ()
        return frame_for_plane(plane, objects)

    def start_sketch(
        self, op_name: str, text: str = "", plane: str = "", *, step: int | None = None
    ) -> None:
        """In den Skizzenmodus wechseln, für die Operation, die sie verbraucht.

        Der mittlere Bereich zeigt die Zeichenfläche statt der Ansicht; die
        Werkzeugzeile darunter bleibt, wo sie ist, und trägt Fertig und
        Verwerfen. Kein Fenster darüber, kein modaler Zustand — Escape kommt
        hier heraus wie aus jedem anderen Werkzeug (§2.1).

        Die Skizze bleibt dabei, was §30.1 aus ihr macht: der Parameterwert
        einer Operation. Am Ende steht derselbe Text, den auch der Dialog
        erzeugt, und alles Weitere — Cache, Undo, die Sperre für den Agenten —
        gilt unverändert.

        ``plane`` ist die vorgewählte Zeichenebene, üblicherweise
        eine eindeutige ``feature:``-Angabe aus einem Klick auf eine Fläche.
        Sie wird über
        :meth:`SketchPanel.choose_plane` gesetzt, also **über das Auswahlfeld**
        und nicht an ihm vorbei — sonst behaupten zwei Stellen zweierlei. Und
        ihr Rückgabewert wird gelesen: Eine Fläche, die der Körper nicht
        (mehr) hat, steht nicht zur Wahl, und stillschweigend auf der
        Grundebene zu landen wäre die schlechteste Antwort (Regel 17).

        **Ohne ``plane`` zählt die gewählte Fläche.** Robert hat am 24.08.2026
        die Deckfläche ausgewählt, „Zeichnen" gedrückt — und unter dem Körper
        auf z=0 gezeichnet: Der Knopf warf die Auswahl weg und startete auf
        der Grundebene. Wer eine Fläche wählt und dann zeichnet, meint diese
        Fläche; erst wenn nichts gewählt ist, ist die Grundebene die richtige
        Vorgabe. Das gilt für jeden Weg ohne eigene Ebene — den Knopf der
        Werkzeugzeile genauso wie eine Skizzen-Operation aus Menü oder
        Palette.
        """
        if self._sketch_panel is not None:
            return
        plane = plane or self._selected_face_plane()
        show_plane_picker = not text.strip() and not plane
        panel = SketchPanel(text, self._parameter_values(), self, self._sketch_surroundings())
        if plane and not panel.choose_plane(plane):
            self.announce(tr("Diese Fläche steht nicht mehr zur Verfügung."))
        self._sketch_panel = panel
        self._sketch_target = op_name
        # Beim Korrigieren aus dem Verlauf trägt der Modus die Kennung des
        # Schritts, den er ändert (Z9). Beim Anlegen bleibt sie leer.
        self._sketch_step = step
        """Leer beim freien Zeichnen über den Werkzeugzeilen-Knopf — die
        Erzeugungsart kommt dann bei „Fertig" (§2.2, Weg 2)."""
        # **Der Schnitt (§30.1, P4): Die Ansicht bleibt stehen.** Früher stand
        # hier ein Tausch im Stapel, und daraus folgte alles, was Robert am
        # 24.08.2026 gemeldet hat — „am Viewport ändert sich nichts", und
        # Draufsicht wie Seitenansicht taten nichts, weil sie etwas geändert
        # hätten, das niemand sieht. Das Panel wird jetzt zur Leiste unter dem
        # Bild; gezeichnet wird dort, wo die Skizze liegt.
        panel.use_viewport()
        # E19 zieht mit in den Viewport: Das Maßfeld wohnt jetzt über der
        # Ansicht (der Canvas ist unsichtbar), und die erste Ziffer erreicht
        # es über deren Ereignisfilter.
        panel.canvas.lend_measure_field(self.viewport, self.viewport.sketch_screen_at)
        self.viewport.set_sketch_entry(
            panel.canvas.pending_measure, panel.canvas.begin_measure_entry
        )
        # Und der Abschluss eines begonnenen Zugs (Z4): Der Hinweis in der
        # Leiste verspricht „Doppelklick oder Eingabetaste schließt sie", und
        # beides kam nie an — die Empfänger sitzen im unsichtbaren
        # Zeichenbereich.
        self.viewport.set_sketch_stroke(self._finish_sketch_stroke)
        self.viewport.set_sketch_edit(
            panel.canvas.can_drag_on_plane,
            panel.canvas.begin_drag_on_plane,
            panel.canvas.drag_on_plane,
            panel.canvas.end_drag_on_plane,
        )
        # **Der Ziehgriff der Querschau** (§30.1): Sobald Blick und
        # Zeichenebene auseinandergehen, wird aus einem Zug am Umriss eine
        # Höhe. Die Grenzen kommen aus dem Schema, damit die Zahl am Zeiger
        # dieselbe ist, die der Dialog danach annimmt.
        self.viewport.set_sketch_pull(
            self._sketch_pull_offer,
            pull_limits(),
            pocket_limits(),
            self._sketch_cut_available,
            self._pocket_top_shift,
        )
        # **Die Bedingungen ziehen in die rechte Spalte, als eigener Reiter.**
        # Gemessen nahm die Leiste sonst 334 von 900 Bildpunkten — 37 Prozent
        # des Fensters —, und gezeichnet wurde zur Hälfte dahinter.
        #
        # Ein Reiter und kein einklappbarer Abschnitt, und zwar nach dem
        # Muster, das die **Tour** schon benutzt: Sie hängt genauso als dritter
        # Reiter neben Prüfbericht und Chat, solange ein Beispiel offen ist.
        # Die Bedingungen sind dieselbe Sorte Auskunft — eine, die zu einem
        # Zustand gehört und mit ihm kommt und geht.
        self._constraints_box.addWidget(panel.take_constraint_list())
        self.right.setTabVisible(self.right.indexOf(self._constraints_room), True)
        self.right.setCurrentWidget(self._constraints_room)
        self._bottom_layout.insertWidget(0, panel)
        panel.sketchChanged.connect(self._redraw_sketch)
        panel.viewFitted.connect(self._fit_sketch_view)
        # **Die dritte Kante: Kamera → Raster.** Feld → Bild läuft über
        # ``sketchChanged``, Bild → Feld über ``follow_grid`` — aber Rad,
        # Drehzug und Einpassen änderten den Maßstab, ohne dass irgendwer
        # neu zeichnete: Das Raster zeigte die Weite vom Betreten, und der
        # nächste Strich ließ es springen. ``cameraMoved`` kommt am Ende
        # einer Bewegung, nicht während ihr — ein Neuzeichnen je Zug.
        self.viewport.cameraMoved.connect(self._redraw_sketch)
        # Die Fangmarke: Der Canvas kennt den Ort, an dem ein Klick wirklich
        # landet (Raster **und** „vorhandener Punkt schlägt Raster"), die
        # Ansicht kann ihn zeigen. Ihn im Viewport nachzurechnen wäre die
        # zweite Zahl für dieselbe Sache — der Fehler, den d6335c1 schon
        # einmal behoben hat. Ohne die Marke sitzt der Punkt bis zu einem
        # halben Rasterschritt neben dem Zeiger, und genau das hat Robert am
        # 24.08.2026 als „die Klicks sind woanders" gemeldet.
        panel.pointerMoved.connect(self._on_sketch_pointer)
        panel.canvas.selectionChanged.connect(self._update_sketch_selection)
        # **Auch die Zeichnung entscheidet über die Kapsel**, nicht nur die
        # Auswahl: Ob „Keine Auswahl" etwas aussagt, hängt daran, ob es
        # überhaupt etwas zu wählen gibt. Ohne diese Verbindung bliebe die
        # Einblendung nach dem ersten Strich stumm, bis der Kunde zum ersten
        # Mal etwas anklickt und wieder abwählt — eine Lage, die dann von der
        # Reihenfolge abhinge statt von der Sache.
        panel.sketchChanged.connect(self._update_sketch_selection)
        panel.canvas.selectionChanged.connect(self._redraw_sketch)
        panel.canvas.measureViewChanged.connect(self._redraw_sketch)
        # **Das Modell bleibt stehen und tritt zurück.** Es ist der Grund,
        # aus dem man auf einer Fläche zeichnet — verstecken hieße, die Frage
        # wegzuräumen, die man gerade beantwortet. Durchscheinend, damit die
        # Zeichnung darauf und nicht dahinter liegt.
        self._mode_before_sketch = self.viewport.display_mode
        self.viewport.set_display_mode("transparent")
        # **Und die Ansicht wird orthografisch.** Der Grund steht schon am
        # Umschalter (§18.1): Parallelprojektion ist das, was gemessene Längen
        # vertrauenswürdig macht. Auf einer Zeichenebene wiegt das schwerer als
        # sonst irgendwo — perspektivisch ist eine Draufsicht keine. Gesehen an
        # der Korpusplatte: Sie stand trapezförmig im Bild, mit sichtbaren
        # Seitenwänden, während die Zeile darunter „Draufsicht (XY)" meldete.
        # Zwei gleich lange Strecken auf derselben Ebene erscheinen dabei
        # verschieden lang, je nachdem, wie weit sie von der Bildmitte weg
        # liegen — und genau darauf setzt man beim Zeichnen Punkte.
        #
        # Vor dem Schwenk, nicht danach: ``view_on_plane`` rechnet den
        # Ausschnitt der Parallelprojektion aus der Kameradistanz, und dafür
        # muss sie schon gelten.
        self._projection_before_sketch = self.viewport.projection
        self.viewport.set_projection("orthographic")
        frame = self._sketch_frame()
        if frame is not None:
            # Einmal schwenken, beim Betreten. Danach nie wieder von selbst:
            # Wer beim Zeichnen dreht, soll gedreht bleiben.
            self.viewport.view_on_plane(frame)
            # **Und die Rasterweite einmal nachziehen, wenn das Layout steht.**
            # Hier ist der Viewport noch 100 mal 30 groß — Qts Startwert für ein
            # Widget ohne fertiges Layout —, und daran gemessen käme ein Raster
            # von 100 mm heraus. ``pixels_per_mm`` fängt das ab und gibt seinen
            # Rückfallwert; der stimmt aber auch nicht, sobald das Fenster steht.
            # Ein Durchlauf der Ereignisschlange später ist die Größe echt.
            QTimer.singleShot(0, self._redraw_sketch)
        # Ab jetzt trifft ein Klick die Ebene und nicht die Szene.
        self.viewport.set_sketching(frame)
        panel.planeChanged.connect(self._sketch_plane_changed)
        self._redraw_sketch()
        self.viewport.show_sketch_planes(show_plane_picker)
        self._update_sketch_selection()
        # Der Startbildschirm liegt vor dem Arbeitsbereich, solange nichts
        # offen ist — und zu zeichnen beginnen ist genau der Fall, in dem noch
        # nichts offen ist (Weg 2, §2.2). Ohne diese Zeile meldete die
        # Statusleiste den Modus, und zu sehen war der Startbildschirm.
        self._show_start_screen(False)
        self.tools.close_tool()
        # Die Ansichtswerkzeuge tun im Skizzenmodus nichts — Schnitt, Messen
        # und Trennen brauchen einen Körper und ein Bild. Sie standen dort als
        # zweite Leiste unter der des Editors und boten ihre Umschalter an,
        # von denen keiner etwas bewirkte.
        self.tools.setVisible(False)
        self.toolbar.setVisible(False)
        self.sketch_bar.setVisible(True)
        self._update_actions()
        # Beide Texte sagten „die Operation", auch wenn es noch keine gab: der
        # Zeichnen-Knopf startet ohne festgelegte Op, und was aus der Skizze
        # wird, entscheidet der Dialog bei „Fertig". Ein Hinweis, der auf eine
        # Operation zeigt, die niemand gewählt hat, lässt den Nutzer suchen,
        # wo nichts ist.
        self._update_sketch_hint()
        if op_name:
            self.statusBar().showMessage(
                tr("Skizze für {op} — Escape verlässt den Modus.").format(
                    op=str(REGISTRY.get(op_name).title)
                )
            )
            return
        self.statusBar().showMessage(tr("Freies Zeichnen — Escape verlässt den Modus."))

    def _sketch_plane_changed(self) -> None:
        """Die Zeichenebene wurde gewechselt — Kamera, Ziel und Bild nachziehen.

        **Hier wird geschwenkt, und das ist kein Widerspruch zu „nur beim
        Betreten".** Wer die Ebene wechselt, sagt damit, dass er woanders
        hinsieht; ihn auf der alten Blickrichtung stehen zu lassen wäre
        dasselbe, als hätte der Wechsel nicht stattgefunden. Was nicht
        schwenkt, ist das Zeichnen selbst — dort bleibt die Ansicht, wie der
        Nutzer sie gedreht hat.
        """
        self.viewport.show_sketch_planes(False)
        frame = self._sketch_frame()
        self.viewport.set_sketching(frame)
        # Gezeichnet wird auf ``frame``, gesehen auf ``_view_frame`` — solange
        # die Skizze leer ist, sind beide dasselbe.
        looking = self._view_frame()
        if looking is not None:
            self.viewport.view_on_plane(looking)
        self._update_sketch_hint()
        self._redraw_sketch()

    def _on_sketch_plane_chosen(self, plane: str) -> None:
        """Eine Ebenenkarte im Bild nimmt denselben Weg wie das Auswahlfeld."""
        panel = self._sketch_panel
        if panel is None:
            return
        if not panel.choose_plane(plane):
            self.announce(tr("Diese Fläche steht nicht mehr zur Verfügung."))

    def _finish_sketch_stroke(self) -> bool:
        """Einen begonnenen Zug abschließen — Doppelklick oder Eingabetaste (Z4).

        **Gibt zurück, ob es etwas abzuschließen gab.** Nur dann schluckt der
        Ereignisfilter der Ansicht das Ereignis; eine Eingabetaste, die keinen
        Zug beendet, gehört weiter dem, der sie sonst bekäme — dem Maßfeld
        etwa, oder dem Fenster.

        Gefragt wird an derselben Stelle, an der auch der Hinweis entsteht:
        Werkzeug „Kurve" und ein begonnener Zug. ``pending_elements`` ist die
        öffentliche Auskunft darüber — dieselbe, aus der die Vorschau im Bild
        entsteht; leer heißt, es ist noch kein Punkt gesetzt. Ein Spline unter
        zwei Punkten wird von ``finish_spline`` selbst verworfen, das ist dort
        begründet und bleibt dort.
        """
        panel = self._sketch_panel
        if panel is None or panel.canvas.tool != "spline":
            return False
        if not panel.canvas.pending_elements():
            return False
        panel.canvas.finish_spline()
        return True

    def _update_sketch_selection(self) -> None:
        """Die Auswahl steht ruhig am Bildrand, mit Wort statt nur Farbe."""
        panel = self._sketch_panel
        if panel is None:
            self.viewport.show_sketch_selection("")
            return
        count = len(panel.canvas.selection)
        if count == 0 and not panel.canvas.sketch.elements:
            # **Eine Kapsel, die nur sagt, dass nichts ist, ist Rauschen** (B20).
            # Sie schwebte über dem leeren Blatt, bevor der Kunde den ersten
            # Strich gezogen hatte — eine Verneinung ohne Gegenstück. Sobald
            # etwas da ist, das man anklicken könnte, sagt sie etwas: Dann
            # heißt „Keine Auswahl", dass der Klick nichts getroffen hat.
            note = ""
        elif count == 0:
            note = tr("Keine Auswahl")
        elif count == 1:
            kind = panel.canvas.selection[0][0]
            note = (
                tr("Punkt ausgewählt — ziehen oder Koordinaten eingeben.")
                if kind == "point"
                else tr("Element ausgewählt — ziehen oder mit Strg weitere dazunehmen.")
            )
        else:
            note = tr("{count} ausgewählt — gemeinsam ziehen.").format(count=count)
        self.viewport.show_sketch_selection(str(note))

    def _on_sketch_point(self, point: object) -> None:
        """Ein Klick auf die Zeichenebene setzt einen Punkt (§30.1, P4).

        Der Ort kommt in Millimetern; die Zeichenfläche nimmt ihn über
        ``place_on_plane`` entgegen und macht damit dasselbe wie mit einem
        Klick auf sich selbst — Fang, Deckung, Undo-Punkt inbegriffen.
        """
        panel = self._sketch_panel
        if panel is None:
            return
        place = cast(tuple[float, float], point)
        extend = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
        panel.canvas.place_on_plane(place, extend=extend)

    def _on_sketch_view_changed(self, plane: str) -> None:
        """Eine gekippte oder eingerastete Kamera im Ebenenfeld spiegeln."""
        panel = self._sketch_panel
        if panel is None:
            return
        drawing_before = panel.canvas.sketch.plane
        panel.reflect_camera_view(plane or None)
        # Bei einer leeren Skizze darf die eingerastete Ansicht zugleich die
        # Zeichenebene festlegen. Danach ändert sich hier nur noch der Blick.
        if panel.canvas.sketch.plane != drawing_before:
            self.viewport.set_sketching(self._sketch_frame())
        self._update_sketch_hint()
        self._redraw_sketch()

    def _on_sketch_pointer(self, x: float, y: float) -> None:
        """Der Canvas hat den Zeiger gefangen — die Ansicht zeigt, wohin.

        Die zwei Zahlen sind schon die gefangenen; hier wird nichts mehr
        gerechnet, nur gezeigt (:meth:`Viewport.show_sketch_cursor`).
        """
        frame = self._sketch_frame()
        preview = self._sketch_preview_curves(frame) if frame is not None else ()
        self.viewport.show_sketch_pointer((x, y), preview)

    def _sketch_preview_curves(self, frame: PlaneFrame) -> tuple[SketchCurve, ...]:
        """Die unfertige Geste mit demselben Kurvenweg wie die feste Skizze."""
        panel = self._sketch_panel
        if panel is None:
            return ()
        elements = panel.canvas.pending_elements()
        if not elements:
            return ()
        return curves_of(SolvedSketch(elements, 0, 0.0), frame)

    def _sketch_pull_offer(self) -> str:
        """Ob am Umriss gerade eine Höhe gezogen werden darf (§30.1).

        Robert am 27.08.2026: „schön wäre auch dass wenn ich in der skizze was
        in der draufsicht zeichne und dann in die Seitenansicht oder
        vorderansicht gehe sie nach oben ziehen kann." Genau dieser Zustand ist
        die Bedingung — **die Querschau**, also Blick und Zeichenebene
        auseinander (``view_plane`` gegen ``sketch.plane``). In der Draufsicht
        bliebe die Geste dem Zeichnen im Weg: Ein Druck auf eine Umrisskante
        wäre dort mal ein Punkt, mal ein Zug.

        **Hier stand „dort sieht man die Ebene von der Kante", und das galt
        nur für die eingerasteten Ansichten.** Ein Ungleichheitsvergleich
        trennt „von der Kante gesehen" nicht von „ein wenig gekippt": Sobald
        die Kamera frei steht, meldet ``reflect_camera_view`` ``FREE_VIEW``,
        und die Bedingung war erfüllt, während weiter von schräg oben
        gezeichnet wurde. Der Ziehgriff ist dort zugleich am unbrauchbarsten —
        seine Empfindlichkeit wächst mit ``1/sin`` des Kippwinkels, bei einem
        Grad bedeuten zehn Pixel Mausbewegung rund siebzig Millimeter Höhe
        (gemessen am 30.08.2026 über :func:`app.core.sketch.planes.axis_hit`).

        **Geschlossen ist das nicht hier, sondern am Einrasten**
        (:meth:`Viewport._settle_sketch_view`): Eine Kamera innerhalb von zehn
        Grad um eine Hauptansicht rastet auf sie ein, und damit gibt es die
        unbrauchbare Lage nach einem Mausdrehen nicht mehr. Zehn Grad decken
        die rund sieben ab, unter denen ein Pixel mehr als einen Rasterschritt
        bedeutet — deshalb steht hier **keine** zweite Schwelle daneben.

        Drei Antworten, wie :meth:`Viewport.set_sketch_pull` sie erwartet.
        Ein **Grund** statt einer leeren Zeichenkette kommt nur, wo die Geste
        gemeint war und nicht ging — sonst stünde bei jedem Druck irgendwo im
        Bild ein Satz über eine Handlung, die niemand versucht hat.
        """
        panel = self._sketch_panel
        if panel is None:
            return ""
        if panel.canvas.view_plane == panel.canvas.sketch.plane:
            return ""
        if self._sketch_target and self._sketch_target not in (PULL_OP, POCKET_OP):
            # Wer den Modus für *Grundform drehen* betreten hat, meint keine
            # Höhe. Der Griff gehört zu ``sketch_extrude``; ihn dort anzubieten
            # hieße, die gewählte Operation stillschweigend zu tauschen.
            return str(
                tr(
                    "Der Ziehgriff zieht eine Höhe auf — bei {op} entscheidet das der Dialog."
                ).format(op=str(REGISTRY.get(self._sketch_target).title))
            )
        if not panel.canvas.outline:
            return str(tr("Zum Aufziehen fehlt der geschlossene Umriss."))
        if self._sketch_target == POCKET_OP:
            # Wer ausdrücklich „Abtragen" gewählt hat, bekommt ohne Zielkörper
            # nicht ersatzweise den entgegengesetzten Aufbau angeboten. Eine
            # verlorene Auswahl ändert die Absicht nicht stillschweigend.
            problem = self._pocket_target_problem()
            if problem:
                return problem
        return "ready"

    def _body_under_the_outline(self) -> str:
        """Der bearbeitbare Körper, über dem die Zeichnung liegt — oder nichts.

        **In Fusion wählt man vor dem Abtragen keinen Körper aus**: Man zieht
        den Umriss nach unten, und geschnitten wird, was darunter liegt. Wer
        von dort kommt, zieht — und Solidon antwortete „Zum Abtragen muss genau
        ein Körper ausgewählt sein", obwohl das Teil unter der Zeichnung lag
        und nur nicht angeklickt war (Robert, 30.08.2026).

        Gesucht wird deshalb über die Lage: Der Umriss wird auf die Ebene
        gelegt und sein Hüllrechteck gegen die Hüllquader der Körper gehalten.
        Trifft es genau einen bearbeitbaren, ist das der gemeinte.

        **Der Hüllquader ist die grobe Antwort, und sie genügt hier.** Eine
        genaue wäre der Schnitt des ausgetragenen Umrisses mit dem Körper —
        die rechnet aber die Operation ohnehin, und wenn sie nichts findet,
        sagt sie es. Was hier gebraucht wird, ist die Frage „welcher ist
        gemeint", nicht „trifft es wirklich".
        """
        panel = self._sketch_panel
        frame = self._sketch_frame()
        result = self.session.last_result
        if panel is None or frame is None or result is None:
            return ""
        points = [point for element in panel.canvas.sketch.elements for point in element.points]
        if not points:
            return ""

        from app.core.sketch.planes import to_world

        corners = [to_world(frame, point) for point in points]
        low = tuple(min(corner[axis] for corner in corners) for axis in range(3))
        high = tuple(max(corner[axis] for corner in corners) for axis in range(3))

        hits = []
        for object_id, entry in result.scene.objects.items():
            # **Jede Art zählt.** Bis zum 30.08.2026 sprang die Schleife über
            # jedes Netz hinweg, weil nur ein exakter Körper abtragbar war —
            # jetzt ist er es nicht mehr allein, und wer ein heruntergeladenes
            # STL geöffnet hat, ist der Normalfall, nicht die Ausnahme.
            bounds = entry.mesh.bounds
            # In der Zugrichtung wird nicht verglichen: Dort *soll* der Umriss
            # außerhalb des Körpers liegen, sonst gäbe es nichts zu ziehen.
            across = [axis for axis in range(3) if abs(frame.normal[axis]) < 0.5]
            if all(
                low[axis] <= bounds.maximum[axis] and high[axis] >= bounds.minimum[axis]
                for axis in across
            ):
                hits.append(object_id)
        return hits[0] if len(hits) == 1 else ""

    def _pocket_top_shift(self) -> float:
        """Wie weit die Oberkante des Zielkörpers über der Zeichenebene liegt.

        Dort beginnt ``sketch_pocket`` zu schneiden, wenn die Zeichnung tiefer
        liegt, also zeigt die Drahtform der Ansicht dort ihre Tiefe. Der
        Zielkörper ist der gewählte, sonst der unter dem Umriss — dieselbe
        Reihenfolge wie in :meth:`_pocket_target_problem`. Gerechnet wird
        über die acht Ecken des Hüllquaders entlang der Ebenennormale: grob,
        aber in dieselbe Richtung wie die Operation, und ohne zweiten Schnitt.
        """
        frame = self._sketch_frame()
        result = self.session.last_result
        if frame is None or result is None:
            return 0.0
        chosen = self.object_tree.selected() or self._body_under_the_outline()
        entry = result.scene.objects.get(chosen) if chosen else None
        if entry is None:
            return 0.0
        bounds = entry.mesh.bounds
        normal = frame.normal
        corners = (
            (x, y, z)
            for x in (bounds.minimum[0], bounds.maximum[0])
            for y in (bounds.minimum[1], bounds.maximum[1])
            for z in (bounds.minimum[2], bounds.maximum[2])
        )
        top = max(sum(c * n for c, n in zip(corner, normal, strict=True)) for corner in corners)
        plane = sum(o * n for o, n in zip(frame.origin, normal, strict=True))
        return max(0.0, top - plane)

    def _pocket_target_problem(self) -> str:
        """Warum die gezeichnete Kontur gerade nichts abtragen kann.

        Gefragt wird in zwei Stufen: erst der gewählte Körper — wer einen
        anklickt, meint ihn —, dann der, über dem die Zeichnung liegt. Die
        zweite Stufe ist die, die ein Fusion-Kunde erwartet
        (:meth:`_body_under_the_outline`).
        """
        selected = self.object_tree.selected_objects()
        result = self.session.last_result
        if result is None:
            return str(tr("Zum Abtragen muss ein Körper in der Szene liegen."))
        chosen = selected[0] if len(selected) == 1 and selected[0] in result.scene.objects else ""
        if not chosen:
            chosen = self._body_under_the_outline()
        if not chosen:
            return str(tr("Unter der Zeichnung liegt kein bearbeitbarer Körper — einen auswählen."))
        # **Kein dritter Grund mehr.** Hier stand bis zum 30.08.2026 „Der
        # gewählte Körper besteht bereits aus festen Dreiecken" — und damit war
        # Abtragen für jedes eingelesene Modell ausgeschlossen. Seit
        # ``geom.sketch_solid`` schneidet die Operation auch in ein Netz; was
        # dabei herauskommt, ist wieder ein Netz, und das ist die richtige
        # Antwort und nicht eine Absage.
        return ""

    def _sketch_cut_available(self) -> bool:
        """Ob Griff, Beschriftung und Operation dieselbe Tasche anbieten."""
        return not self._pocket_target_problem()

    def _update_sketch_actions(self) -> None:
        """Hochziehen und Abtragen folgen dem Zustand der freien Kontur."""
        panel = self._sketch_panel
        free = panel is not None and not self._sketch_target
        self.sketch_pull_button.setVisible(free)
        self.sketch_cut_button.setVisible(free)
        if not free or panel is None:
            return

        closed = bool(panel.canvas.outline)
        outline_problem = str(tr("Erst einen geschlossenen Umriss zeichnen."))
        self.sketch_pull_button.setEnabled(closed)
        self.sketch_pull_button.setToolTip(
            str(tr("Macht aus dem Umriss einen Körper. Danach die Höhe einstellen."))
            if closed
            else outline_problem
        )
        pocket_problem = self._pocket_target_problem() if closed else outline_problem
        self.sketch_cut_button.setEnabled(closed and not pocket_problem)
        self.sketch_cut_button.setToolTip(
            pocket_problem
            or str(
                tr("Schneidet den Umriss aus dem ausgewählten Körper. Danach die Tiefe einstellen.")
            )
        )

    def _finish_sketch_as(self, op_name: str) -> None:
        """Die sichtbare kurze Hand von der Kontur zu Aufbau oder Tasche."""
        panel = self._sketch_panel
        if panel is None:
            return
        if not panel.canvas.outline:
            self.announce(tr("Erst einen geschlossenen Umriss zeichnen."))
            return
        if op_name == POCKET_OP:
            problem = self._pocket_target_problem()
            if problem:
                self.announce(problem)
                return
        self._sketch_target = op_name
        self.finish_sketch(keep=True)

    def _on_sketch_pulled(self, height: float) -> None:
        """Der Zug am Griff wird zur Operation — mit dem Dialog als Bestätigung.

        Während des Zugs steht das Maß an der Drahtform (Viewport,
        ``sketch_pull_measure``), so wie beim Zeichnen einer Linie. Loslassen
        öffnet den Dialog mit der gezogenen Höhe, und dort bleiben alle Werte
        änderbar — Robert, 02.09.2026: „bei Bestätigung sollen alle drei Werte
        noch änderbar sein". Ein Höhenfeld in der Skizzenleiste stand hier
        einen Vormittag lang und ging wieder: „unten im Feld wollen wir es
        nicht".
        """
        self._apply_sketch_pull(height)

    def _apply_sketch_pull(self, height: float) -> None:
        """Außen wird Material aufgebaut, innen aus einem Körper entfernt.

        Der Zug endet als **Operation** und nicht als Zustand (Regel 2): Der
        Modus wird verlassen wie bei „Fertig", und ``sketch_extrude`` bekommt
        die Zeichnung und die Höhe. Der Dialog geht dabei auf wie immer — wer
        nachrechnen oder eine andere Zahl setzen will, tut es dort, und der
        Verlauf trägt einen Schritt und nicht zwei.
        """
        if self._sketch_panel is None:
            return
        if height < 0.0:
            problem = self._pocket_target_problem()
            if problem:
                self.viewport.cancel_sketch_pull()
                self.announce(problem)
                return
            # **Gefunden heißt noch nicht gewählt.** ``run_operation`` nimmt
            # seine Eingänge aus dem Objektbaum; ein Körper, den nur
            # :meth:`_body_under_the_outline` kennt, käme dort nie an, und die
            # Operation liefe ohne Eingang. Das ist dasselbe letzte Glied, an
            # dem heute schon zwei Befunde hingen — die Entscheidung fällt,
            # und niemand setzt sie um.
            if not self.object_tree.selected_objects():
                found = self._body_under_the_outline()
                if found:
                    self.object_tree.select_object(found)
            self._sketch_target = POCKET_OP
            self.finish_sketch(keep=True, given={POCKET_FIELD: abs(float(height))})
            return
        self._sketch_target = PULL_OP
        self.finish_sketch(keep=True, given={PULL_FIELD: float(height)})

    def _on_sketch_hover(self, point: object) -> None:
        """Der Zeiger steht auf der Ebene — die Vorschau zieht nach."""
        panel = self._sketch_panel
        if panel is None:
            return
        panel.canvas.hover_on_plane(cast(tuple[float, float], point))

    def _update_sketch_hint(self) -> None:
        """Der Hinweis über der Zeichenleiste nennt die Ebene, auf der
        gezeichnet wird.

        Die andere Hälfte der Auskunft, die die Fangmarke gibt: Das Kreuz
        sagt, wohin der Klick fällt — dieser Satz sagt, worauf. Robert hat am
        24.08.2026 auf z=0 gezeichnet und es erst am Ergebnis gemerkt; mit dem
        Satz hätte die Leiste „Draufsicht (XY)" gesagt, während er auf die
        Deckfläche sah.

        Die Beschriftung kommt aus dem Ebenen-Auswahlfeld, das sie schon
        führt — keine zweite Quelle. Nur das Tastenkürzel am Ende fällt weg:
        „(2)" hilft beim Wechseln, nicht beim Wissen, wo man ist.
        """
        panel = self._sketch_panel
        if panel is None:
            return
        # Die Zeichenebene kommt aus dem Dokumentzustand, nicht aus dem Feld:
        # Nach dem ersten Element zeigt dieses Feld die **Ansicht**. Genau die
        # Verwechslung erzeugte den Screenshot „Vorderansicht" neben dem Satz
        # „Zeichenebene: Draufsicht".
        drawing_plane = panel.canvas.sketch.plane
        place = plane_where(drawing_plane)
        if drawing_plane.startswith("feature:"):
            # „Die gewählte Fläche" bestätigt nur, **dass** eine Auswahl
            # angekommen ist. Der Kunde muss hier wiedererkennen, **welche**:
            # dieselbe Beschriftung mit Objektname, Fläche und Lage, die auch
            # das Ebenenfeld und das Kontextmenü verwenden.
            feature_id = drawing_plane.removeprefix("feature:")
            place = next(
                (
                    label
                    for candidate, label, _normal in self._drawable_faces()
                    if candidate == feature_id
                ),
                place,
            )
        if self._sketch_target:
            source = tr("Zeichenebene: {place} · Zeichnen — die Operation öffnet auf der Skizze.")
        elif panel.canvas.outline:
            source = tr(
                "Zeichenebene: {place} · Umriss geschlossen — daraus wird jetzt ein Körper."
            )
        else:
            # **Der Halbsatz nennt die fertigen Formen** (Befund Z6). Hinter
            # dem Pfeil des Rechteck-Knopfs liegen sechs vollbemaßte Formen —
            # Rechteck, Langloch, Kreis, Sechseck, Lochkreis, Lochraster —,
            # und für jemanden ohne CAD-Kenntnisse ist das die hilfreichste
            # Stelle der ganzen Leiste. Sie war zugleich die einzige, die man
            # nur findet, wenn man einen kleinen Pfeil trifft.
            #
            # Hier und nicht in der Leiste: Der Satz steht ohnehin da, wo ein
            # Anfänger nachliest, was als Nächstes geht, und kostet keinen
            # Bildpunkt Breite. Der häufigste Fall — jemand will ein Rechteck
            # — bleibt damit ein Klick.
            source = tr(
                "Zeichenebene: {place} · Geschlossenen Umriss zeichnen oder eine "
                "fertige Form einsetzen — daraus wird dann ein Körper."
            )
        # **In der Querschau steht hier die Geste**, und zwar aus derselben
        # Quelle, die sie auch erlaubt (:meth:`_sketch_pull_offer`) — sonst
        # verspricht der Satz etwas, was der Griff nicht hält. Ohne ihn findet
        # ihn niemand: Der Umriss sieht von der Kante aus wie ein Strich, und
        # dass man daran ziehen kann, sagt allein der Mauszeiger, wenn man
        # schon darüber ist.
        #
        # Eingesetzt wird **vor** dem Anhängen: Ein Grund, der selbst eine
        # geschweifte Klammer trägt, ließe ``format`` sonst über einen Text
        # laufen, der keine Vorlage mehr ist.
        line = source.format(place=place)
        if panel.canvas.view_plane != panel.canvas.sketch.plane:
            # **„Ansicht: freien Ansicht“ war kein Satz** (Z8). plane_where
            # liefert die Dativform, gebaut für „Sie sehen die Zeichnung aus
            # der …“ — hinter einem Doppelpunkt steht sie im falschen Fall.
            # Der Artikel gehört deshalb in den Satz, nicht in die Wortliste:
            # So passen alle drei Antworten, die die Funktion geben kann.
            line = tr("Blick aus der {view} · {instruction}").format(
                view=plane_where(panel.canvas.view_plane), instruction=line
            )
        offer = self._sketch_pull_offer()
        action = ""
        if offer == "ready":
            action = (
                str(tr("Pfeil: Körper hochziehen · Kreuz: Tasche schneiden."))
                if self._sketch_cut_available()
                else str(
                    tr(
                        "Pfeil: Körper hochziehen · Abtragen braucht einen ausgewählten, "
                        "bearbeitbaren Körper."
                    )
                )
            )
            line = f"{line} {action}"
        elif offer:
            line = f"{line} {offer}"
        elif (
            panel.canvas.outline
            and panel.canvas.view_plane == panel.canvas.sketch.plane
            and self._sketch_target in ("", PULL_OP, POCKET_OP)
        ):
            action = (
                str(tr("Zum Ziehen mit der Maus: Vorder- oder Seitenansicht wählen."))
                if self._sketch_cut_available()
                else str(
                    tr(
                        "Zum Ziehen mit der Maus: Vorder- oder Seitenansicht wählen. "
                        "Abtragen braucht zusätzlich einen bearbeitbaren Körper."
                    )
                )
            )
        self._sketch_hint.setText(line)
        self.viewport.show_sketch_action(action)
        self._update_sketch_actions()

    def _sketch_frame(self) -> PlaneFrame | None:
        """Der Rahmen der Ebene, auf der gerade gezeichnet wird."""
        panel = self._sketch_panel
        if panel is None:
            return None
        return self._plane_frame(panel.canvas.sketch.plane)

    def _view_frame(self) -> PlaneFrame | None:
        """Der Rahmen, auf den die Kamera sieht.

        **Nicht dasselbe wie der oben, sobald etwas gezeichnet ist.** Wer
        danach die Ebene wechselt, will sehen, wo seine Zeichnung im Raum
        liegt — sie bleibt liegen, die Kamera geht woandershin. Ein Klick
        landet weiter auf der Zeichenebene, denn dort wird gezeichnet.
        """
        panel = self._sketch_panel
        if panel is None:
            return None
        return self._plane_frame(panel.canvas.view_plane)

    def _fit_sketch_view(self, x: float, y: float, span_x: float, span_y: float) -> None:
        """*Einpassen* im Skizzenmodus — die Ansicht folgt der Zeichenfläche.

        Dieselbe Vermittlung wie beim Zeichnen: Das Panel kennt den Viewport
        nicht, es meldet nur, was es eingepasst hat. Ohne diesen Weg setzte der
        Knopf den Maßstab eines Widgets, das seit P4 niemand mehr sieht.
        """
        frame = self._sketch_frame()
        if frame is None:
            return
        self.viewport.show_span_on_plane(frame, (x, y), (span_x, span_y))

    def _redraw_sketch(self) -> None:
        """Die Zeichnung in der Szene nachziehen (§30.1, P4).

        Gezeigt wird die **gelöste** Skizze — dieselbe, die der Kern später
        rechnet. Eine ungelöste wäre die Lage vor den Bedingungen und damit
        eine Aussage über etwas, das es nicht gibt; bei einem Konflikt hält
        der Canvas ohnehin die letzte gültige Lage.

        Die Kamera wird hier **nicht** bewegt. Sie schwenkt einmal beim
        Betreten und danach nie wieder von selbst: Wer beim Zeichnen dreht,
        soll gedreht bleiben — ein Bild, das nach jedem Strich zurückspringt,
        wäre schlimmer als eines, das nie schwenkt.
        """
        panel = self._sketch_panel
        frame = self._sketch_frame()
        if panel is None or frame is None:
            self.viewport.clear_sketch()
            return
        # **Das Raster hängt nicht an der Zeichnung.** Es hing daran, und
        # damit fehlte es genau dann, wenn man es am nötigsten hat: Eine leere
        # Skizze hat kein gelöstes Ergebnis, also wurde vor dem ersten Strich
        # gar nichts gelegt — keine Kurven, aber eben auch kein Raster. Was
        # man sah, war das Bett; wo die Zeichenebene liegt, sagte nichts.
        #
        # Gemessen war das ``sketch_actors == 0`` im laufenden Modus, und im
        # Bild nicht von „das Raster ist zu blass" zu unterscheiden.
        solved = panel.canvas.solved
        kurven = curves_of(solved, frame) if solved is not None else ()
        if panel.canvas.sketch.elements:
            self.viewport.show_sketch_planes(False)
        # **Die Rasterweite folgt der Kamera, nicht der Zeichenfläche.**
        # Deren Maßstab steht im Viewport-Modus auf dem Startwert — dort
        # zoomt niemand mehr. Gemessen kam damit ein Raster von 20 mm
        # heraus, während auf 1 mm gefangen wurde: zwei Zahlen für
        # dieselbe Sache, und die sichtbare war die falsche.
        shown_scale = self.viewport.pixels_per_mm(frame)
        step = grid_step_for(shown_scale)
        # **Auch der Fangradius rechnet gegen das sichtbare Bild.** Der Canvas
        # ist im Viewport-Modus unsichtbar und sein Maßstab steht auf dem
        # Startwert — acht Bildpunkte wären darüber 6,7 mm, und ein Klick
        # fünf Millimeter neben einem Punkt schnappte auf ihn.
        panel.canvas.set_view_scale(shown_scale)
        # **Und der Fang bekommt dieselbe Zahl.** Robert am 24.08.2026: „das
        # fang sollte immer das raster sein." Vorher waren es zwei — gezeichnet
        # 5 mm, gefangen auf 1 mm, und gemessen landeten vier von vier Klicks
        # zwischen zwei sichtbaren Linien. Das Kästchen heißt „Am Raster
        # fangen"; es hat damit etwas versprochen, das nicht eintrat.
        #
        # ``follow_grid`` übernimmt die Weite nur, solange niemand sie
        # eingetippt hat. Danach steht sie, und das Raster folgt umgekehrt ihr
        # — eine Zahl bleibt es in beiden Richtungen.
        panel.follow_grid(step)
        if panel.snap_is_pinned():
            step = panel.snap_step.value_mm()
        control_points = tuple(to_world(frame, point) for point in panel.canvas.points())
        measure_labels = tuple(
            (to_world(frame, point), label) for point, label in panel.canvas.measure_annotations()
        )
        self.viewport.show_sketch(
            kurven,
            frame,
            step,
            SKETCH_GRID_REACH,
            selected_curves=panel.canvas.selected_element_indices(),
            control_points=control_points,
            selected_points=panel.canvas.selected_point_indices(),
            axis_names=panel.canvas.axis_names(),
            measure_labels=measure_labels,
            preview=self._sketch_preview_curves(frame),
        )
        # **Und die Zeile über der Leiste altert nicht mit der Zeichnung.** Sie
        # nennt neben der Ebene auch, ob der Ziehgriff gerade gilt, und das
        # hängt am geschlossenen Umriss. Gerufen wurde sie nur beim Betreten
        # und beim Ebenenwechsel: Wer in der Querschau ein Rechteck hatte und
        # eine lose Linie dazuzeichnete, las weiter „Am Umriss ziehen", während
        # das Angebot schon „fehlt der geschlossene Umriss" sagte — zwei
        # Aussagen über denselben Zustand (gefunden von der Review-Sitzung,
        # 27.08.2026). Hier, weil ``_redraw_sketch`` an ``sketchChanged`` und
        # an ``cameraMoved`` hängt und damit jede Änderung sieht; die Zeile
        # kostet nur Text und kein Bild.
        self._update_sketch_hint()

    def finish_sketch(self, keep: bool = True, *, given: dict[str, Any] | None = None) -> None:
        """Den Modus verlassen. Mit ``keep`` öffnet die Operation auf der
        gezeichneten Skizze, sonst wird sie verworfen.

        ``given`` sind Werte, die schon beantwortet sind, wenn der Dialog
        aufgeht. Der Ziehgriff ist der eine Fall: Er hat die Höhe gezogen, und
        sie im Dialog wieder auf die Vorgabe zu stellen hieße, die Geste
        wegzuwerfen (:meth:`_on_sketch_pulled`).
        """
        panel = self._sketch_panel
        target = self._sketch_target
        step = self._sketch_step
        if panel is None:
            return
        text = panel.sketch_text()
        if not keep:
            # **Verworfen heißt nicht vernichtet.** Escape war die teuerste
            # Taste des Programms: eine halbe Stunde Zeichnung, ein Tastendruck,
            # kein Rückweg — und kein Dialog davor, weil Regel 19 keinen
            # zulässt, solange die Handlung rücknehmbar ist. Sie ist es jetzt.
            self._remember_discarded(target, text, panel)
            text = ""
        # Die Ansicht stand die ganze Zeit — zurückzuschalten gibt es nichts
        # mehr (§30.1, P4). Was geht, sind die Zeichnung aus der Szene und
        # das Panel aus der Leiste.
        #
        # **Erst abmelden, dann aufräumen, dann die Ansicht anfassen.**
        # ``set_display_mode`` baut die Szene neu auf; liefe dabei noch eine
        # Verbindung vom Panel hierher, zeichnete ``_redraw_sketch`` in eine
        # Szene, die gerade entsteht, und läse dabei ein Panel, das schon zum
        # Löschen vorgemerkt ist. Kein ``setParent(None)``: Das macht ein
        # Kind-Widget für einen Augenblick zum eigenen Fenster, und ein
        # Fenster, das im selben Atemzug gelöscht wird, ist der Absturz ohne
        # Zeile (gemessen, Segmentierungsfehler in ``test_ui.py``).
        self._sketch_panel = None
        self._sketch_target = None
        self._sketch_step = None
        self.viewport.set_sketching(None)
        # Die Maßeingabe abklemmen und das Feld heimholen, **bevor** das Panel
        # stirbt: Die Ansicht hielte sonst Rückrufe auf einen toten Canvas,
        # und das Feld bliebe als Waise über dem Bild stehen.
        self.viewport.set_sketch_entry(None, None)
        self.viewport.set_sketch_stroke(None)
        self.viewport.set_sketch_edit(None, None, None, None)
        # Aus demselben Grund wie die Zeile darüber: ``_sketch_pull_offer`` ist
        # eine gebundene Methode dieses Fensters und liest das Panel, das
        # gleich stirbt.
        self.viewport.set_sketch_pull(None)
        self.viewport.show_sketch_planes(False)
        self.viewport.show_sketch_selection("")
        self.viewport.show_sketch_action("")
        panel.canvas.reclaim_measure_field()
        panel.sketchChanged.disconnect(self._redraw_sketch)
        self.viewport.cameraMoved.disconnect(self._redraw_sketch)
        panel.pointerMoved.disconnect(self._on_sketch_pointer)
        panel.planeChanged.disconnect(self._sketch_plane_changed)
        panel.canvas.selectionChanged.disconnect(self._update_sketch_selection)
        panel.sketchChanged.disconnect(self._update_sketch_selection)
        panel.canvas.selectionChanged.disconnect(self._redraw_sketch)
        # Die dritte Verbindung aus derselben Zeilengruppe wie die zwei
        # darüber — heute folgenlos (der unsichtbare Canvas ruft fit_view
        # nie), aber die Begründung „erst abmelden, dann aufräumen" gilt für
        # sie genauso.
        panel.viewFitted.disconnect(self._fit_sketch_view)
        # **Die Box geht ans Panel zurück, bevor es stirbt.** Sie hing im
        # Reiter, also am Fenster — das Panel zu löschen ließe sie dort stehen,
        # mit Signalen, die ins Leere zeigen, und beim nächsten Skizzenmodus
        # käme eine zweite dazu. Gemessen war das ein Segmentierungsfehler in
        # der Fensterdatei, kein sichtbarer Rest.
        self.right.setTabVisible(self.right.indexOf(self._constraints_room), False)
        box = panel.take_constraint_list()
        self._constraints_box.removeWidget(box)
        box.setParent(panel)
        box.hide()
        self._bottom_layout.removeWidget(panel)
        panel.hide()
        panel.deleteLater()
        self.viewport.clear_sketch()
        self.viewport.set_display_mode(self._mode_before_sketch)
        self.viewport.set_projection(self._projection_before_sketch)
        self.tools.setVisible(True)
        self.toolbar.setVisible(True)
        self.sketch_bar.setVisible(False)
        self.statusBar().clearMessage()
        self._update_actions()
        if keep and text:
            if target:
                values: dict[str, Any] = {_sketch_param(target): text}
                values.update(given or {})
                if step is not None:
                    # **Derselbe Schritt, andere Zeichnung** (Z9). Wer aus dem
                    # Dialog eines vorhandenen Schritts in den Raum gewechselt
                    # ist, will ihn ändern und keinen zweiten anlegen, der
                    # dasselbe noch einmal tut — dieselbe Entscheidung wie beim
                    # Skeletteditor. Die übrigen Feldwerte stehen am Schritt und
                    # reisen von dort mit; ``given`` überschreibt nur die
                    # Zeichnung.
                    self.edit_operation(step, given=values)
                else:
                    self.run_operation(REGISTRY.get(target), given=values)
            else:
                # Freies Zeichnen (Weg 2): erst jetzt fällt die Entscheidung,
                # was aus der Skizze wird — mit der fertigen Zeichnung vor
                # Augen statt vorab aus fünf Menüeinträgen.
                self._offer_sketch_use(text)

    # --- Formsitzung (§25, Konzept P16.6) ---------------------------------------

    def start_sculpt(self, object_id: str = "") -> None:
        """Die Formsitzung öffnen: Klicks werden von jetzt an Pinselzüge.

        Ein **Werkzeugmodus**, kein Betriebsmodus (Entscheidung J): Er gilt für
        die eine Operation, die gerade entsteht, die Szene bleibt die Szene,
        und Escape kommt heraus. Der Unterschied zum Skizzenmodus ist, dass die
        Ansicht bleibt, was sie ist — geformt wird am Körper, nicht auf einer
        Zeichenfläche.
        """
        if self._sculpt_target is not None:
            return
        target = object_id or self.object_tree.selected()
        if not target:
            self.announce(str(_NEEDS_SELECTION))
            return
        mesh = self._sculpt_mesh(target)
        if mesh is None:
            self.announce(tr("Dieses Objekt hat kein Netz zum Formen."))
            return

        self._sculpt_target = target
        # **Auch der erste Zug ist einer.** Der Schalter wird nach jedem Zug
        # zurückgenommen (der Grund steht dort), beim Betreten aber nicht: Wer
        # ihn in der vorigen Sitzung zuletzt setzte, fand ihn hier wieder und
        # bekam eine eigene Etappe, ohne sie verlangt zu haben.
        self.sculpt_bar.cut.setChecked(False)
        self._sculpt_strokes = []
        self.viewport.set_sculpting(True, self.sculpt_bar.radius.value_mm())
        self.tools.close_tool()
        self.tools.setVisible(False)
        self.sculpt_bar.setVisible(True)
        self.sculpt_bar.show_count(0, 0)
        self.sculpt_bar.show_warning(self._sculpt_resolution_hint(mesh), refinable=True)
        self._update_actions()
        self.statusBar().showMessage(
            tr("Mit dem Pinsel über den Körper ziehen — Escape beendet die Sitzung.")
        )

    def sculpting(self) -> bool:
        """Ob gerade geformt wird statt betrachtet."""
        return self._sculpt_target is not None

    def _sculpt_mesh(self, object_id: str) -> MeshData | None:
        """Das Netz, auf dem geformt wird — aus der letzten Auswertung."""
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result else None
        if entry is None:
            return None
        try:
            return as_mesh_data(entry.mesh)
        except AppError:
            return None

    def _sculpt_resolution_hint(self, mesh: MeshData) -> str:
        """Entscheidung E: sagen, dass das Netz zu grob ist, **bevor** jemand
        vergeblich malt.

        ``warp`` ändert die Topologie nicht. Wer eine feine Falte in ein grobes
        Netz zieht, bekommt keine Falte, sondern eine verzogene Facette — und
        das erkennt man am Ergebnis nicht, sondern nur an dieser Zeile.
        """
        edge = median_edge(mesh)
        radius = self.sculpt_bar.radius.value_mm()
        if radius >= edge * BRUSH_TO_EDGE:
            return ""
        return tr("Das Netz ist für diesen Pinsel zu grob — erst gleichmäßig vernetzen.")

    def refine_for_sculpt(self) -> None:
        """Das Netz so fein machen, dass der eingestellte Pinsel greift.

        Die Kantenlänge ist keine Frage an den Nutzer: Sie folgt aus dem
        Radius, den er schon eingestellt hat, über dieselbe Schwelle, die die
        Warnung auslöst (:data:`BRUSH_TO_EDGE`). Ein Viertel darunter statt
        genau darauf — die Vernetzung trifft ihren Zielwert nur ungefähr, und
        eine Warnung, die nach ihrer eigenen Behebung stehen bleibt, ist
        schlimmer als gar keine.

        Die Sitzung läuft weiter. Vorhandene Züge überleben das: sie stehen in
        Weltkoordinaten und nicht als Eckenverweise (§30.1), und die Operation
        entsteht ohnehin erst beim Verlassen.
        """
        if self._sculpt_target is None:
            return
        edge = self.sculpt_bar.radius.value_mm() / (BRUSH_TO_EDGE * 1.25)
        # Der feinste Wert, den die Operation annimmt, steht in ihrem Schema
        # und nicht hier: der kleinste Pinsel (0,1 mm) rechnet sich sonst auf
        # eine Kante, die sie ablehnt — eine Sackgasse hinter einem Knopf, der
        # aus einer Sackgasse herausführen soll.
        finest = next(
            entry.minimum or 0.0
            for entry in REGISTRY.get("remesh_uniform").params.spec()
            if entry.name == "edge"
        )
        self.session.apply(
            tr("Dreiecke angleichen"),
            [
                OperationDraft(
                    op="remesh_uniform",
                    inputs=(self._sculpt_target,),
                    outputs=(self._sculpt_target,),
                    params={"edge": max(finest, edge)},
                )
            ],
        )

    def _on_sculpt(self, point: Any) -> None:
        """Ein Klick im Viewport wird ein Zug.

        Geometrie entsteht dabei **nicht** (Regel 2): Der Zug geht in die
        Liste, und was das Fenster zeigt, ist eine Vorschau. Die Operation
        entsteht beim Verlassen der Sitzung, aus derselben Liste.
        """
        if self._sculpt_target is None:
            return
        mesh = self._sculpt_mesh(self._sculpt_target)
        if mesh is None:
            return
        bar = self.sculpt_bar
        self._sculpt_strokes.append(
            stroke_at(
                mesh,
                (float(point[0]), float(point[1]), float(point[2])),
                # Über ``values()`` und nicht an den Widgets vorbei: Die
                # Leiste kennt ihre Einheiten, ein Aufrufer nicht. Von Hand
                # nachgebaut stand hier ``radius.value()``, und damit lief in
                # Zoll ein Pinsel von 0,2 mm, wo 5 mm eingestellt waren —
                # Geometrie ins Dokument, aus einem Anzeigewert.
                **bar.values(),
            )
        )
        # Der Schalter gilt für **einen** Zug. Stehen zu bleiben hieße, dass
        # jeder weitere Zug eine eigene Etappe bekommt — und damit einen
        # eigenen Durchgang, ohne dass jemand das verlangt hätte.
        self.sculpt_bar.cut.setChecked(False)
        self._show_sculpt_preview(mesh)
        self._sculpt_check.start()

    def _show_sculpt_preview(self, mesh: MeshData) -> None:
        """Was der Zug bewirkt, sofort — und was er kostet, daneben.

        Die Vorschau rechnet dieselbe Auswertung wie die Operation, nur auf dem
        Anzeigenetz und ohne den Stapel darum: Tausend Züge auf dem
        §31-Prüfnetz kosten 96 ms, ein einzelner also nichts, was jemand
        bemerkt. Der Dokumentzustand ändert sich dabei nicht — er ändert sich
        bei „Fertig", in einer Transaktion.
        """
        strokes = self._sculpt_strokes
        self.sculpt_bar.show_count(len(strokes), len(stages(strokes)))
        self.sculpt_bar.show_warning(self._sculpt_resolution_hint(mesh), refinable=True)
        if self._sculpt_target is None:
            return
        plane = SYMMETRY_BITS.get(self.sculpt_bar.plane(), 0)
        shown = [replace(s, symmetry=s.symmetry | plane) for s in strokes] if plane else strokes
        self.viewport.show_preview_mesh(self._sculpt_target, apply_strokes(mesh, shown))

    def _check_sculpted_walls(self) -> None:
        """Entscheidung L: Was der Pinsel zu dünn gemacht hat, sagt es selbst.

        **Das ist der Grund, warum dieses Vorhaben zu Solidon gehört und nicht
        zu Blender.** Ein Sculpting-Programm weiß nichts über Drucker; ein
        Slicer merkt es, aber erst, wenn die Form fertig ist. Hier steht es in
        der Leiste, während man formt.

        In Entwurfsqualität und verzögert: Das Raster muss feiner sein als die
        Mindestwandstärke, sonst findet die Karte gar nichts — bei 2 mm Raster
        und 1,2 mm Mindestwand meldete sie null zu dünne Stellen an einer
        Schale mit 0,8 mm Wand. Und als Zahl, nicht nur als Farbe (Regel 18).
        """
        if self._sculpt_target is None or not self._sculpt_strokes:
            return
        mesh = self._sculpt_mesh(self._sculpt_target)
        if mesh is None:
            return
        plane = SYMMETRY_BITS.get(self.sculpt_bar.plane(), 0)
        strokes = self._sculpt_strokes
        shown = [replace(s, symmetry=s.symmetry | plane) for s in strokes] if plane else strokes
        sculpted = apply_strokes(mesh, shown)
        minimum = self.session.profile.minimum_wall_thickness
        # Mit Wartezeiger: gemessen 273 ms bei 82 000 Dreiecken — über der
        # 200-ms-Grenze aus §2.8, und die Prüfung läuft nach jedem Zug. Auf
        # feinen Netzen (und `refine_for_sculpt` erzeugt gezielt feine) wäre
        # das ein Stocken ohne Erklärung.
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            card = wall_thickness_map(sculpted, minimum=minimum, pitch=minimum * WALL_GRID_SHARE)
        except AppError:
            # Ein zu großes Netz ist kein Grund, die Sitzung zu stören. Der
            # Prüfbericht sagt dasselbe später und gründlicher.
            return
        finally:
            QApplication.restoreOverrideCursor()
        thin = len(card.highlighted)
        if not thin:
            self.sculpt_bar.show_warning(self._sculpt_resolution_hint(mesh), refinable=True)
            return
        self.sculpt_bar.show_warning(
            tr("{count} Stellen dünner als {minimum}")
            .replace("{count}", str(thin))
            .replace("{minimum}", length(minimum))
        )

    def _remember_discarded(self, target: str | None, text: str, panel: Any) -> None:
        """Die verworfene Zeichnung aufheben und den Rückweg ansagen.

        Angesagt wird in der Statuszeile und nicht in einem Dialog: Die Geste
        bleibt, wie sie war (Regel 19), und wer bewusst verwirft, soll nicht
        aufgehalten werden. Wer es nicht wollte, findet den Weg zurück da, wo
        er ohnehin hinsieht, nachdem etwas verschwunden ist.

        Eine leere Zeichnung wird nicht gemerkt — ein Angebot, nichts
        zurückzuholen, wäre eine Meldung ohne Inhalt.
        """
        if not text:
            self._discarded_sketch = None
            return
        plane = ""
        chooser = getattr(panel, "plane_choice", None)
        if chooser is not None:
            plane = str(chooser.currentData() or "")
        self._discarded_sketch = _DiscardedSketch(
            op_name=target or "",
            text=text,
            plane=plane,
            steps=len(self.session.history.operations),
        )
        self.announce(tr("Zeichnung verworfen — Strg+Z holt sie zurück."))

    def restore_discarded_sketch(self) -> bool:
        """Die verworfene Zeichnung zurückholen — der erste Griff von Strg+Z.

        Dieselbe Trennung wie bei :meth:`undo_sculpt_stroke`: eigenes
        Rückgängig des Editors vor dem des Verlaufs. Das Angebot gilt, solange
        der Kunde nichts anderes getan hat; hat er inzwischen eine Operation
        angewandt oder zurückgenommen, meint sein Strg+Z diese.
        """
        discarded = self._discarded_sketch
        if discarded is None:
            return False
        self._discarded_sketch = None
        if len(self.session.history.operations) != discarded.steps:
            # Der Verlauf ist weitergegangen — das Angebot ist verfallen, und
            # dieser Griff gehört dem Verlauf.
            return False
        self.start_sketch(discarded.op_name, text=discarded.text, plane=discarded.plane)
        self.announce(tr("Zeichnung zurückgeholt."))
        return True

    def undo_sculpt_stroke(self) -> bool:
        """Das Rückgängig des Editors: ein Zug, nicht die Sitzung.

        Dieselbe Trennung wie beim Skizzeneditor. Der Verlauf bekommt die
        Sitzung als **eine** Transaktion (Regel 16); solange sie offen ist,
        wäre ein Schritt darin im Verlauf ein Eintrag, den niemand haben will.
        """
        if self._sculpt_target is None or not self._sculpt_strokes:
            return False
        self._sculpt_strokes.pop()
        mesh = self._sculpt_mesh(self._sculpt_target)
        if mesh is not None:
            self._show_sculpt_preview(mesh)
        return True

    def finish_sculpt(self) -> None:
        """Die Sitzung schließen — und aus ihr genau eine Operation machen."""
        target = self._sculpt_target
        strokes = self._sculpt_strokes
        if target is None:
            return
        result = self.session.last_result
        if strokes and (result is None or target not in result.scene.objects):
            # Das Ziel ist fort — nur noch über einen Fern- oder Agentenzug
            # möglich, denn die Menüs sind während der Sitzung gesperrt.
            # Die Züge nicht verwerfen: die Sitzung bleibt offen, und der
            # Satz sagt es (§2.7). Vorher lief *Fertig* durch, verlor die
            # Züge und meldete einen Wert außerhalb seines Bereichs.
            self.announce(tr("Der geformte Körper ist nicht mehr da — die Sitzung bleibt offen."))
            return
        self._sculpt_target = None
        self._sculpt_strokes = []
        self._sculpt_check.stop()
        self.viewport.set_sculpting(False)
        self.viewport.clear_preview_mesh()
        self.sculpt_bar.setVisible(False)
        self.tools.setVisible(True)
        self.statusBar().clearMessage()
        self._update_actions()
        if not strokes:
            # Eine Sitzung ohne Zug hinterlässt nichts. Ein leerer Schritt im
            # Verlauf wäre Rauschen an genau der Stelle, an der man sucht.
            return
        self.session.apply(
            _("Formen"),
            [
                OperationDraft(
                    op="sculpt_strokes",
                    inputs=(target,),
                    params={
                        "strokes": strokes_to_text(strokes),
                        "symmetry": self.sculpt_bar.plane(),
                    },
                )
            ],
        )

    # --- Skelettsitzung (§25, Konzept P16 §7.5) ---------------------------------

    def start_armature(self, object_id: str = "") -> None:
        """Den Skeletteditor öffnen: Klicks setzen von jetzt an Knochenpunkte.

        Zwei Klicks je Knochen — erst das Gelenk, dann das Ende. Der nächste
        Knochen hängt am vorigen, bis jemand *Neue Kette* drückt: Ein Skelett
        ist meistens eine Kette, und wer für jeden Knochen sein Elternteil
        wählen muss, klickt dreimal so oft wie nötig.
        """
        if self._armature_target is not None or self._sculpt_target is not None:
            return
        target = object_id or self.object_tree.selected()
        if not target:
            self.announce(str(_NEEDS_SELECTION))
            return

        self._armature_target = target
        # **Ein vorhandenes Skelett kommt mit.** Wer den Editor auf einem
        # Körper öffnet, der schon eines trägt, erwartet seine Knochen zu
        # sehen — nicht ein leeres Blatt. Ohne das war der einzige Weg zu
        # einem verschobenen Gelenk, das Skelett neu zu setzen, und beim
        # „Fertig" entstand eine **zweite** Operation, die ein zweites Mal
        # beugt.
        self._armature_step, self._armature_bones = self._armature_of(target)
        self._armature_head = None
        self._armature_parent = ""
        self.viewport.set_boning(True)
        self.tools.close_tool()
        self.tools.setVisible(False)
        self.pose_bar.setVisible(True)
        # **Der Zustand wird abgeleitet, nicht behauptet.** Sieben Zeilen
        # darüber lädt ``_armature_of`` die Knochen des vorhandenen Schritts;
        # eine feste Null daneben ist eine zweite Quelle für etwas, das schon
        # eine hat — und sie war die falsche. Wer „Noch kein Knochen" liest,
        # hält das für eine Zusage: Er fängt bei null an. Setzt er dann einen
        # und sieht vier, weiß er nicht, ob er drei fremde geerbt oder drei
        # eigene verloren hat, und *Fertig* ändert einen Schritt, von dem die
        # Leiste behauptet hat, er sei leer (gemessen 3d-druck-85, 03.09.2026:
        # drei geladene Knochen, angezeigt „Noch kein Knochen").
        #
        # Das Namensfeld gehört dazu: Es überlebte sonst die Sitzung, und der
        # erste Knochen am **nächsten** Körper hieß, was jemand hier getippt
        # und nie gesetzt hatte. ``clear_name`` verbietet das in seinem
        # eigenen Docstring — gerufen hat es diese Stelle nur nicht.
        self.pose_bar.clear_name()
        self.pose_bar.show_state(
            len(self._armature_bones),
            pending=False,
            chain=bool(self._armature_parent),
        )
        self._update_actions()
        self.statusBar().showMessage(tr("Zwei Klicks setzen einen Knochen — Escape beendet."))

    def _armature_of(self, target: str) -> tuple[int | None, list[Any]]:
        """Der letzte Skelettschritt dieses Körpers und seine Knochen.

        ``(None, [])``, wenn es keinen gibt — dann ist der Editor ein leeres
        Blatt wie beim ersten Mal.

        **Der letzte und nicht der erste:** Wer sein Skelett schon zweimal
        geändert hat, meint die Fassung, die gerade gilt. Gelesen wird aus dem
        Dokument und nicht aus der Szene, weil dort die *Eingabe* steht — die
        Szene trägt das Ergebnis, und aus einem gebeugten Körper lassen sich
        die Knochen nicht zurückrechnen.
        """
        from app.core.geom.pose import armature_from_text

        for entry in reversed(self.session.project.document.ops):
            if entry.op != "pose_armature" or target not in entry.inputs:
                continue
            text = str(entry.params.get("armature", ""))
            if not text.strip():
                return (None, [])
            try:
                return (entry.id, armature_from_text(text))
            except AppError:
                # Ein unlesbares Skelett ist kein Grund, den Editor zu
                # verweigern — dann fängt er leer an, und der alte Schritt
                # bleibt unberührt im Verlauf stehen.
                return (None, [])
        return (None, [])

    def setting_armature(self) -> bool:
        """Ob gerade ein Skelett gesetzt wird."""
        return self._armature_target is not None

    def _on_bone_point(self, point: Any) -> None:
        """Ein Klick im Viewport: erst der Kopf, dann der Fuß eines Knochens."""
        if self._armature_target is None:
            return
        place = (float(point[0]), float(point[1]), float(point[2]))
        if self._armature_head is None:
            self._armature_head = place
            self.pose_bar.show_state(
                len(self._armature_bones), pending=True, chain=bool(self._armature_parent)
            )
            return

        name = self.pose_bar.next_name() or f"bone_{len(self._armature_bones) + 1}"
        # Ein Name, den es schon gibt, wäre ein Skelett, dessen Stellung
        # niemand mehr zuordnet — die Winkel stehen je Knochenname.
        taken = {bone.name for bone in self._armature_bones}
        while name in taken:
            name = f"{name}_1"
        self._armature_bones.append(
            Bone(name=name, head=self._armature_head, tail=place, parent=self._armature_parent)
        )
        self._armature_head = None
        self._armature_parent = name
        self.pose_bar.clear_name()
        self.pose_bar.show_state(
            len(self._armature_bones), pending=False, chain=bool(self._armature_parent)
        )

    def break_armature_chain(self) -> None:
        """Der nächste Knochen hängt an nichts — für den zweiten Arm."""
        self._armature_parent = ""
        self._armature_head = None
        self.pose_bar.show_state(len(self._armature_bones), pending=False, chain=False)

    def undo_bone(self) -> bool:
        """Das Rückgängig des Editors: ein Knochen, nicht die Sitzung."""
        if self._armature_target is None:
            return False
        if self._armature_head is not None:
            # Ein halb gesetzter Knochen ist der erste, der zurückgeht: Sonst
            # nähme das erste Strg+Z einen fertigen Knochen und ließe den
            # angefangenen stehen.
            self._armature_head = None
        elif self._armature_bones:
            gone = self._armature_bones.pop()
            self._armature_parent = gone.parent
        else:
            return False
        # ``gone.parent`` ist leer, sobald der zurückgenommene Knochen der
        # erste einer neuen Kette war: Der nächste hängt dann wieder an nichts
        # — ein zweiter Arm —, und ein festes ``chain=True`` verschwieg genau
        # das. Der Kunde drückte *Neue Kette* ein zweites Mal oder bekam ein
        # Skelett mit falscher Elternkette.
        self.pose_bar.show_state(
            len(self._armature_bones),
            pending=False,
            chain=bool(self._armature_parent),
        )
        return True

    def finish_armature(self) -> None:
        """Die Sitzung schließen — und aus ihr genau eine Operation machen."""
        target = self._armature_target
        bones = self._armature_bones
        if target is None:
            return
        result = self.session.last_result
        if bones and (result is None or target not in result.scene.objects):
            # Wie beim Formen: das Ziel ist fort, die Knochen bleiben — die
            # Sitzung schließt nicht über einem Körper, den es nicht mehr
            # gibt (§2.7).
            self.announce(
                tr("Der Körper des Skeletts ist nicht mehr da — die Sitzung bleibt offen.")
            )
            return
        step = self._armature_step
        self._armature_target = None
        self._armature_bones = []
        self._armature_step = None
        self._armature_head = None
        self.viewport.set_boning(False)
        self.pose_bar.setVisible(False)
        self.tools.setVisible(True)
        self.statusBar().clearMessage()
        self._update_actions()
        if not bones:
            return
        # Der Editor setzt das Skelett, die Winkel sind Zahlen und gehören in
        # den Dialog — dort darf auch ein Projektparameter stehen. Also öffnet
        # „Fertig" den Dialog mit gesetztem Skelett, wie es „Fertig" der
        # Skizze vormacht: eine Operation mit leerer Stellung anzulegen hieße,
        # dass nichts geschieht und niemand erfährt, wo es weitergeht.
        self.object_tree.select_object(target)
        gesetzt = {"armature": armature_to_text(bones)}
        if step is not None:
            # **Denselben Schritt ändern, keinen zweiten anlegen.** Zwei
            # Skelettschritte auf einem Körper beugen ihn zweimal; der Kunde
            # hat aber sein Skelett bearbeitet und kein weiteres gesetzt.
            self.edit_operation(step, given=gesetzt)
            return
        self.run_operation(REGISTRY.get("pose_armature"), given=gesetzt)

    def action_sketch_free(self) -> None:
        """Der Zeichnen-Knopf der Werkzeugzeile: Skizzenmodus ohne
        festgelegte Operation (§2.2, Weg 2)."""
        self.start_sketch("")

    def action_sculpt_free(self) -> None:
        """Der Formen-Knopf der Werkzeugleiste (§2.2, Weg 4).

        Eine eigene Methode und nicht ``start_sculpt`` selbst: ``triggered``
        reicht seinen Haken-Zustand als erstes Argument durch, und das wäre
        hier die Objektkennung — ``False`` als Körper, den es nicht gibt.
        """
        self.start_sculpt()

    def action_armature_free(self) -> None:
        """Der Skelett-Knopf der Werkzeugleiste — aus demselben Grund eine
        eigene Methode wie der Nachbar darüber."""
        self.start_armature()

    def _offer_sketch_use(self, text: str) -> None:
        """Was soll aus der Skizze werden? — die fünf Arten, mit der
        Zeichnung vor Augen.

        Abbrechen wirft nichts weg: es geht zurück in den Skizzenmodus, die
        Zeichnung bleibt. Ein „Abbrechen", das gezeichnete Arbeit vernichtet,
        wäre die Sackgasse, die §2.1 verbietet.
        """
        # **Was unter der Zeichnung liegt, entscheidet die Vorwahl.** Ohne
        # Körper wird ein Körper daraus, mit Körper meistens eine Tasche darin
        # — dieselbe Regel, die der Ziehgriff seit jeher an der Richtung
        # trifft. Gefragt wird in der Reihenfolge, die auch ``_apply_sketch_pull``
        # benutzt: erst der ausgewählte, dann der unter dem Umriss. Der zweite
        # Teil ist der wichtige, denn in Fusion wählt man vor dem Abtragen
        # keinen Körper aus (Robert, 30.08.2026).
        chosen_body = self.object_tree.selected() or self._body_under_the_outline()
        result = self.session.last_result
        entry = result.scene.objects.get(chosen_body) if result and chosen_body else None
        dialog = SketchUseDialog(self, on_body=str(entry.name) if entry else "")
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.chosen():
            name = dialog.chosen()
            # **Gefunden heißt noch nicht gewählt** — dieselbe Falle wie beim
            # Ziehgriff: ``run_operation`` nimmt seine Eingänge aus dem
            # Objektbaum, und ein nur gefundener Körper käme dort nie an. Die
            # Operation liefe ohne Eingang und meldete einen fehlenden Körper,
            # obwohl er unter der Zeichnung liegt.
            if name == POCKET_OP and chosen_body and not self.object_tree.selected_objects():
                self.object_tree.select_object(chosen_body)
            self.run_operation(REGISTRY.get(name), given={_sketch_param(name): text})
            return
        self.start_sketch("", text)

    def palette_rows(
        self, commands: dict[str, tuple[str, str, Any]] | None = None
    ) -> list[PaletteEntry]:
        """Was in der Palette steht — Operationen und Fensterbefehle.

        Getrennt von :meth:`action_command_palette`, weil dort ein modaler
        Dialog aufgeht: Was danach kommt, sieht keine Prüfung mehr, und was
        eine Prüfung nicht sieht, driftet. Die Kürzelfrage ist genau so
        entstanden.

        Die Fensterbefehle kommen als Argument, wenn der Aufrufer sie ohnehin
        braucht — er führt sie danach aus, und zweimal gebaut wären es zwei
        Listen, von denen niemand garantiert, dass sie dieselbe ist.
        """
        commands = self.window_commands() if commands is None else commands
        extra = [
            PaletteEntry(
                name=key,
                title=title,
                doc=title,
                shortcut=shortcut,
                category=key.split(".", 1)[0],
                available=usable,
                reason=reason,
            )
            for key, (title, shortcut, _slot) in commands.items()
            for usable, reason in (self._extra_availability(key),)
        ]
        # Die Verfügbarkeit kommt aus derselben Quelle wie im Menü — den
        # QActions, die `_update_actions` pflegt. Vorher zeigte die Palette
        # jeden Eintrag gleich, und wer einen ohne passende Auswahl wählte,
        # bekam die modale Sackgasse, die das Menü längst beseitigt hat.
        # **Das Kürzel geht durch die Belegung, wie im Menü.** Der Kern liefert
        # das Kürzel aus dem Register — er kennt die Belegung nicht und darf es
        # nicht, sie ist eine Einstellung der Oberfläche. Ungefiltert
        # weitergereicht lehrte die Palette im Schema „Wie Fusion und Onshape"
        # drei falsche Tasten (`translate_object` „Strg+T" statt „M") und
        # verschwieg sieben, die es dort gibt — während der Menüeintrag daneben
        # die richtige zeigte. Dieselbe Umrechnung wie in `_update_actions`.
        entries = [
            replace(
                entry,
                available=usable,
                reason=reason,
                shortcut=shortcut_for(entry.name, entry.shortcut, self.settings.shortcut_scheme),
            )
            for entry in palette_entries(for_feature=self.selected_feature_kind())
            for usable, reason in (self._palette_availability(entry.name),)
        ]
        return [*entries, *extra]

    def action_command_palette(self) -> None:
        """Eine Taste, alles — und die Kürzel lernen sich nebenbei (§2.6)."""
        commands = self.window_commands()
        palette = CommandPalette(self.palette_rows(commands), parent=self)
        if palette.exec() != CommandPalette.DialogCode.Accepted:
            return
        name = palette.chosen()
        if not name:
            return
        if name in commands:
            self._run_window_command(name, commands)
            return
        self._run_palette_choice(name)

    def _run_window_command(self, name: str, commands: Mapping[str, tuple[str, str, Any]]) -> None:
        """Führt den gewählten Fensterbefehl aus — oder sagt, warum nicht.

        Dieselbe Wache wie in :meth:`_run_palette_choice`, im Nachbarzweig:
        Die Liste sperrt ihre Zeilen, aber die Tastatur springt auch auf eine
        gesperrte, und Enter führte den Fensterbefehl trotzdem aus (Regel 19 —
        dieselbe Bauart, die für Operationen seit cc40aaa4 behoben ist). Der
        Grund geht in die Statuszeile, wie dort. Als eigene Methode, weil
        ``action_command_palette`` an einem ``exec`` hängt und ein Test die
        Wache sonst nur mit offenem Dialog erreichte.
        """
        available, reason = self._extra_availability(name)
        if not available:
            self.announce(reason)
            return
        commands[name][2]()

    def _run_palette_choice(self, name: str) -> None:
        """Führt die gewählte Operation aus — oder sagt, warum nicht.

        **Gesperrt bleibt gesperrt, auch über die Pfeiltasten.** Die Liste
        sperrt ihre Zeilen, aber die Tastatur konnte auf eine gesperrte
        springen, und Enter führte sie aus: „Gitter füllen" auf leerer Szene
        öffnete die modale Sackgasse, die der Kommentar an ``palette_rows``
        als beseitigt beschreibt (Regel 19, Gesamtreview I-3). Der Grund geht
        in die Statuszeile — dieselbe Auskunft, die die Zeile trägt.
        """
        available, reason = self._palette_availability(name)
        if not available:
            self.announce(reason)
            return
        self.launch_operation(REGISTRY.get(name))

    def _palette_availability(self, name: str) -> tuple[bool, str]:
        """Ob eine Operation jetzt ausführbar ist, und warum nicht.

        Aus den Menü-Actions gelesen statt neu gerechnet: zwei Quellen für
        dieselbe Frage drifteten beim nächsten Zuwachs auseinander.

        **Und wo es keine Action gibt, wird gerechnet — mit derselben
        Funktion, die auch die Action ausgraut.** ``action is None`` hieß
        „erlaubt", und das war eine stille Annahme: dass jede Operation einen
        Menüeintrag hat. Sie stimmt heute schon nicht für die zusammengelegten
        Zwillinge, und sie hört ganz auf zu stimmen, sobald eigene Bausteine
        in den Katalog wandern statt in die Menüleiste — dann hätte *jeder*
        von ihnen die Antwort „erlaubt" bekommen, auch auf leerer Szene, und
        der Kunde wäre in genau der modalen Sackgasse gelandet, gegen die
        ``_run_palette_choice`` gebaut wurde.

        ``_reason_locked`` ist dabei keine zweite Quelle, sondern **die**
        Quelle: Der Menüeintrag wird über sie ausgegraut (``_kind_hint``), der
        Zwillingshaken fragt sie, und hier antwortet sie eben direkt statt über
        den Umweg einer Action, die es nicht gibt.
        """
        spec = REGISTRY.get(name)
        action = self._op_actions.get(name)
        if action is None:
            result = self.session.last_result
            reason = self._reason_locked(
                spec,
                self._kinds_of_selection(result),
                len(result.scene.objects) if result else 0,
                len(self.object_tree.selected_objects()),
            )
            return reason is None, reason or ""
        if action.isEnabled():
            return True, ""
        hint = action.toolTip()
        if hint and hint != str(spec.doc):
            # `_lock_hint`/`_kind_hint` haben einen Grund gesetzt.
            return False, hint
        return False, tr("Dafür braucht es eine passende Auswahl.")

    def _build_feature_dock(self) -> None:
        """Das Merkmalspanel als **eigenes, frei platzierbares Fenster**.

        Robert am 03.09.2026, nachdem es zuerst ein Abschnitt der linken Spalte
        war: „bei dem Panel mit den merkmalen hab ich gedacht ein extra panel
        nicht die bestehenden erweitern." Ein Dock ist genau das — es steht
        angedockt da, lässt sich abziehen und irgendwohin stellen, bleibt
        offen und hat seine eigene Breite. Die linke Spalte bleibt, wie sie
        war.

        **Mit Rollbereich**, und das ist keine Vorsorge: An einer Bohrung sind
        es vier Handlungen mit zusammen sechs Feldern und vier Knöpfen. Ohne
        Rollbereich schneidet ein niedriges Fenster die letzte Handlung ab —
        dieselbe Sorte Fehler, die Robert am abgeschnittenen Text gemeldet hat,
        nur senkrecht (Robert: „auch auf die größen achten war viel
        abgeschnitten").
        """
        scroller = QScrollArea(self)
        scroller.setWidget(self.feature_panel)
        # Ohne dies bleibt das Panel auf seiner Wunschbreite stehen und wird
        # waagerecht gerollt statt umgebrochen.
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QScrollArea.Shape.NoFrame)

        self.feature_dock = _FeatureDock(tr("Merkmal"), self)
        self.feature_dock.setObjectName("featureDock")
        self.feature_dock.setWidget(scroller)
        self.feature_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.feature_dock)
        # **Beim Start zu.** Es stand offen und leer am rechten Rand und nahm
        # der Ansicht 165 von 1280 Punkten für einen einzigen Satz ab —
        # gemessen an vier Videoaufnahmen (3d-druck-06, 03.09.2026). Wer eine
        # Datei öffnet, hat noch nichts gewählt; ein Bereich, der beim Start
        # nichts zeigt, ist Fläche ohne Auskunft.
        #
        # Es geht beim **ersten** gewählten Merkmal von selbst auf — dort
        # beantwortet es eine Frage, die gerade gestellt wurde. Wer es danach
        # zumacht, hat entschieden: ``_feature_dock_dismissed`` merkt es sich,
        # und von da an öffnet nur noch der Schalter unter *Ansicht*. Ein
        # Fenster, das nach jedem Klick wieder aufspringt, ist keine Hilfe.
        self.feature_dock.hide()
        self.feature_dock.start_watching()
        # Wer das Fenster zumacht, während eine Vorschau darauf wartet, hätte
        # sonst eine Änderung im Bild und keinen Ort mehr, sie zu übernehmen
        # oder zurückzunehmen — samt dem Band und seinem anwendungsweiten
        # Ereignisfilter (gemessen am 03.09.2026: alle sechs Zustände blieben).
        self.feature_dock.closed.connect(self._drop_feature_preview)
        # Der Eintrag kommt von Qt selbst und trägt damit denselben Namen wie
        # das Fenster; wer es zugemacht hat, findet es hier wieder.
        entry = self.feature_dock.toggleViewAction()
        entry.setStatusTip(
            tr("Zeigt die Maße des gewählten Merkmals — als eigenes Fenster, frei platzierbar.")
        )
        self._view_menu.addSeparator()
        self._view_menu.addAction(entry)

    def _on_feature_moved(self, feature_id: str, centre: Any) -> None:
        """Ein Zug am Griff hat ein Merkmal versetzt (§18.11, Regel 2).

        Die Zielmitte kommt **absolut** aus der Ansicht — sie hält das Merkmal
        und kennt das Raster, in das der Zug gefangen wurde. Hier wird sie
        weder umgerechnet noch nachgeprüft; ein zweiter Fang an dieser Stelle
        wäre eine zweite Meinung über denselben Zug.
        """
        self._feature_step(
            "move_feature",
            feature_id,
            {"x": float(centre[0]), "y": float(centre[1]), "z": float(centre[2])},
        )

    def _on_feature_turned(self, feature_id: str, axis: str, angle: float) -> None:
        """Ein Zug am Ring hat ein Merkmal gekippt — mit dem **gerasteten**
        Winkel, also dem, der während des Zugs am Zeiger stand."""
        self._feature_step("rotate_feature", feature_id, {"axis": axis, "angle": float(angle)})

    def _feature_step(self, op: str, feature_id: str, params: dict[str, Any]) -> None:
        """Ein Zug, eine Transaktion — dieselbe Zusage wie am Körpergriff.

        **Die Operation wird gegen das Register geprüft.** Die Ansicht sendet
        nur, wo eine Griff-Operation gilt; steht sie hier trotzdem nicht im
        Register, geschieht nichts, statt dass das Fenster mit einer
        unbekannten Operation abbricht.
        """
        selected = self.object_tree.selected()
        if selected is None or not REGISTRY.has(op):
            return
        draft = OperationDraft(
            op=op, inputs=(selected,), params={"at_feature": feature_id, **params}
        )
        self.session.apply(REGISTRY.get(op).title, [draft])

    def _on_face_dragged(self, normal: Any, distance: float) -> None:
        """Ein Zug am Flächengriff wird eine Operation (§18.11, Regel 2).

        Der Viewport hat das Signal seit dem Gizmo an der Fläche gesendet, und
        niemand hörte zu: der Griff ließ sich ziehen, das Modell blieb, wie es
        war. Ein Signal ohne Empfänger fällt in keinem Review auf und in keinem
        Test, der nur den Sender prüft.

        Ein Zug, eine Transaktion — dieselbe Zusage wie beim Verschieben des
        ganzen Körpers, nur dass hier die Fläche wandert und die Nachbarwände
        mitwachsen.
        """
        selected = self.object_tree.selected()
        if selected is None:
            return
        self.session.apply(
            REGISTRY.get("push_face").title,
            [
                OperationDraft(
                    op="push_face",
                    inputs=(selected,),
                    params={
                        "nx": float(normal[0]),
                        "ny": float(normal[1]),
                        "nz": float(normal[2]),
                        "distance": float(distance),
                    },
                )
            ],
        )

    def feature_instead_of(self, op: str) -> OperationSpec | None:
        """Die Merkmalsoperation, die an die Stelle dieser Körperoperation tritt.

        **Die eine Stelle, an der die Frage steht** „ist ein Merkmal gewählt,
        und gilt für seine Art eine eigene Operation?". Taste, Menüeintrag und
        Bewegen-Leiste lesen dieselbe Antwort; zwei Antworten liefen nach der
        nächsten Registeränderung auseinander, und dann graut das Menü etwas
        aus, das die Taste noch zulässt.

        Geprüft wird gegen das Register: eine Zuordnung ohne Operation fällt
        still auf den Körper zurück.
        """
        twin = FEATURE_TWINS.get(op)
        if twin is None or not REGISTRY.has(twin):
            return None
        feature = self._selected_feature_object()
        if feature is None:
            return None
        spec = REGISTRY.get(twin)
        return spec if feature.kind in (spec.applies_to or ()) else None

    def _selected_feature_object(self) -> Feature | None:
        """Das gewählte Merkmal selbst — oder nichts, wenn keines gewählt ist."""
        feature_id = self.object_tree.selected_feature()
        object_id = self.object_tree.selected()
        if feature_id is None or object_id is None:
            return None
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result is not None else None
        return entry.features.get(feature_id) if entry is not None else None

    def feature_draft(self, op: str, params: Mapping[str, Any]) -> OperationDraft | None:
        """Der Zug gilt dem **gewählten Merkmal**, wenn es dafür eine Operation
        gibt — sonst wie bisher seinem Körper.

        Roberts Regel vom 03.09.2026: „wenn man die Wulst wählt verschiebt man
        die Wulst, immer das Ausgewählte." Bis dahin nahm die Bewegen-Leiste
        immer den Körper, auch wenn im Objektbaum eine Bohrung markiert war —
        das Teil sprang, und das Merkmal blieb, wo es war.

        **Die Zuordnung wird gegen das Register geprüft.** Eine Handlung, deren
        Merkmalsoperation es noch nicht gibt, fällt still auf den Körper zurück
        statt zu scheitern; sobald sie im Register steht, greift sie von selbst.
        Und die Art entscheidet mit: Eine Verrundung folgt ihrer Kante und hat
        kein Verschieben, also bewegt sich dort weiterhin der Körper.

        **Zielwert statt Zuwachs.** Die Merkmalsoperationen nehmen die neue Lage
        absolut (``x``, ``y``, ``z`` ist die neue Mitte), die Leiste gibt einen
        Versatz. Umgerechnet wird hier, weil nur die Oberfläche die heutige
        Mitte kennt — und absolut ist es, weil eine Operation aus ihren
        Parametern reproduzierbar sein muss (Regel 2).
        """
        twin = FEATURE_TWINS.get(op)
        if twin is None or not REGISTRY.has(twin):
            return None
        feature_id = self.object_tree.selected_feature()
        object_id = self.object_tree.selected()
        if feature_id is None or object_id is None:
            return None
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result is not None else None
        feature = entry.features.get(feature_id) if entry is not None else None
        if feature is None:
            return None
        spec = REGISTRY.get(twin)
        if feature.kind not in (spec.applies_to or ()):
            return None
        centre = feature.params.get("centre")
        if centre is None or len(centre) != 3:
            return None
        return OperationDraft(
            op=twin,
            inputs=(object_id,),
            params={
                "at_feature": feature_id,
                "x": float(centre[0]) + float(params.get("dx", 0.0)),
                "y": float(centre[1]) + float(params.get("dy", 0.0)),
                "z": float(centre[2]) + float(params.get("dz", 0.0)),
            },
        )

    def inputs_for_transform(self, op: str) -> tuple[ObjectId, ...]:
        """Welche Körper eine Transformation trifft — leer heißt: keine Auswahl.

        **Weil ein Kunde, der zwei Teile markiert hat, zwei Teile meint.**
        ``object_tree.selected()`` gibt ``items[0]``, den ersten von mehreren,
        und ein Zug am Griff bewegte damit still eines von zwei markierten
        Teilen. Das ist nicht ungenau, sondern kaputt: Die Auswahl sagt zwei,
        das Bild zeigt eines, und niemand erfährt, warum.

        **Alle drei Züge gelten inzwischen der ganzen Auswahl.** Verschieben
        konnte das immer — sein Vektor ist für jeden Körper derselbe. Drehen
        und Skalieren gingen zunächst nicht: Sie nahmen ihren Bezugspunkt aus
        dem *eigenen* Netz, jeder Körper drehte also um sich selbst statt die
        Gruppe um ihre Mitte. Seit die Operationen einen genannten Punkt
        annehmen (``about="point"``), gibt es diesen Unterschied nicht mehr;
        den Punkt liefert :meth:`pivot_for_transform`.

        Die Reihenfolge ist die Anklickreihenfolge (``selected_objects``).
        """
        return self.object_tree.selected_objects()

    def pivot_for_transform(self) -> dict[str, float | str]:
        """Der gemeinsame Bezugspunkt für einen Zug an mehreren Körpern.

        Leer bei einem einzelnen Körper: Dann gilt sein eigener Schwerpunkt,
        genau wie bisher und wie in jeder bestehenden Projektdatei. Erst ab
        zwei markierten Körpern steht ein Punkt in den Parametern.

        **Die Mitte der gemeinsamen Hülle und nicht der Schwerpunkt der
        Massen.** Was der Kunde sieht, ist der Kasten um seine Auswahl; dessen
        Mitte ist die Stelle, an der er den Griff erwartet. Ein Schwerpunkt
        wanderte mit dem Volumen und läge bei einem großen und einem kleinen
        Teil fast im großen — die Drehung sähe dann aus, als griffe sie nur
        eines an.

        **Eine Abfrage und keine Geometrieänderung** (Regel 2): Hier entsteht
        kein Ergebnis, das in ein Dokument wandert, sondern ein *Parameter*,
        den die Operation dann selbst verrechnet. Der Unterschied ist der, an
        dem der Weg über eine Zerlegung in der Oberfläche gescheitert wäre —
        dort stünde am Ende eine Zahl in der Projektdatei, deren Herkunft
        niemand mehr nachvollzieht, und ein nachträglich geänderter Winkel im
        Verlauf rechnete sie nicht mit.
        """
        chosen = self.object_tree.selected_objects()
        if len(chosen) < 2:
            return {}
        result = self.session.last_result
        if result is None:
            return {}
        meshes = [
            as_mesh_data(entry.mesh)
            for entry in (result.scene.objects.get(one) for one in chosen)
            if entry is not None
        ]
        if not meshes:
            return {}
        centre = bounding_box_of(meshes).centre
        return {
            "about": "point",
            "pivot_x": float(centre[0]),
            "pivot_y": float(centre[1]),
            "pivot_z": float(centre[2]),
        }

    def _on_transform_dragged(self, steps: Any) -> None:
        """Ein Ziehen, eine Transaktion — in einem Schritt zurückgenommen
        (§18.11, §15.5).
        """
        drafts: list[OperationDraft] = []
        if steps.moves:
            # Derselbe Vorrang wie bei den getippten Werten: Was gewählt ist,
            # wird bewegt. Ein Zug am Griff, der ein Merkmal meint, darf nicht
            # das ganze Teil versetzen.
            single = self.feature_draft(
                "translate_object",
                {"dx": steps.offset[0], "dy": steps.offset[1], "dz": steps.offset[2]},
            )
            if single is not None:
                self.session.apply(REGISTRY.get(str(single.op)).title, [single])
                return
            # Ein Draft je Körper, alle in einem ``apply`` — weiter genau eine
            # Transaktion, und ein Strg+Z nimmt den ganzen Zug zurück.
            drafts.extend(
                OperationDraft(
                    op="translate_object",
                    inputs=(object_id,),
                    params={"dx": steps.offset[0], "dy": steps.offset[1], "dz": steps.offset[2]},
                )
                for object_id in self.inputs_for_transform("translate_object")
            )
        if steps.turns:
            pivot = self.pivot_for_transform()
            drafts.extend(
                OperationDraft(
                    op="rotate_object",
                    inputs=(object_id,),
                    params={"axis": steps.axis, "angle": steps.angle, **pivot},
                )
                for object_id in self.inputs_for_transform("rotate_object")
            )
        if steps.resizes:
            pivot = self.pivot_for_transform()
            drafts.extend(
                OperationDraft(
                    op="scale_object",
                    inputs=(object_id,),
                    params={"factor": steps.scale, **pivot},
                )
                for object_id in self.inputs_for_transform("scale_object")
            )
        if drafts:
            # **Aufeinanderfolgende Züge sind eine Handlung** (§15.5, P9). Wer
            # ein Teil an seinen Platz schiebt, zieht selten einmal: ziehen,
            # nachsehen, nachziehen — und hatte dafür einen Eintrag je Zug,
            # für eine einzige Absicht. Ob wirklich gebündelt wird, entscheidet
            # die ``History``; hier steht nur das Angebot.
            self.session.apply(_("Direkt bewegt"), drafts, bundle=True)

    def _on_scale_dragged(self, factor: float) -> None:
        """Ein Zug am Skalierwürfel wird eine Operation (§18.11, Regel 2).

        Gleichmäßig und um den Schwerpunkt — genau das, was die Vorschau
        während des Zugs gezeigt hat. Wer achsweise oder um einen anderen
        Punkt skalieren will, nimmt den Dialog; der Zug ist für das
        Gleichmäßige da.
        """
        chosen = self.inputs_for_transform("scale_object")
        if not chosen:
            return
        # Der Würfel greift alle markierten Körper — um ihre gemeinsame Mitte,
        # damit die Anordnung erhalten bleibt statt jeden für sich zu blähen.
        pivot = self.pivot_for_transform()
        self.session.apply(
            REGISTRY.get("scale_object").title,
            [
                OperationDraft(
                    op="scale_object",
                    inputs=(object_id,),
                    params={"factor": float(factor), **pivot},
                )
                for object_id in chosen
            ],
        )

    def _on_measurement(self, measurement: Any) -> None:
        self.measure_bar.show_measurement(
            measurement.kind, measurement.value, len(self.viewport.measurements)
        )

    # --- Analysekarten und Schichten (§18.4, §18.10) ----------------------------

    def _on_map_changed(self, kind: Any) -> None:
        """Baut die gewählte Karte für das gewählte Objekt und gibt sie der
        Ansicht.
        """
        object_id = self.object_tree.selected()
        if kind is None or object_id is None:
            self.viewport.set_analysis_map(None, None)
            self.analysis_bar.show_legend(None)
            if kind is not None:
                self.analysis_bar.show_problem(tr("Wählen Sie zuerst ein Objekt im Objektbaum."))
            return

        self._analysis_map(kind, object_id)

    def _analysis_map(self, kind: maps.MapKind, object_id: ObjectId) -> None:
        """§18.9: im Hintergrund gerechnet, je Objekt und Art gecacht.

        Sekunden an einem großen Körper, und ein Fenster, das so lange nicht
        antwortet, sieht kaputt aus. Eine neuere Anfrage ersetzt eine wartende —
        niemand will die Karte, von der er weggeklickt hat.
        """
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result else None
        if entry is None:
            return

        key = (object_id, kind, entry.mesh.triangle_count)
        if key in self._map_cache:
            self._show_map(self._map_cache[key], object_id)
            return

        self.analysis_bar.show_problem(tr("Die Analysekarte wird berechnet …"))
        worker = _MapWorker(kind, entry, self.session.profile, result.scene if result else None)
        # Stirbt der Arbeiter unerwartet, darf die Legende nicht für immer
        # „wird berechnet" sagen (Gesamtreview I-2): Wartezustand lösen, der
        # Grund geht den InternalError-Weg (§33.1).
        worker.crashed.connect(self._map_crashed)
        worker.done.connect(
            lambda analysis, key=key, object_id=object_id: self._map_ready(analysis, key, object_id)
        )
        worker.tooLarge.connect(
            lambda: self.analysis_bar.show_problem(
                tr("Für eine Analysekarte ist dieses Modell zu groß.")
            )
        )
        # **Nicht** auf ``None`` setzen, wenn der Arbeiter fertig ist.
        #
        # ``finished`` kommt, während Qt den Thread noch abräumt. Wer die
        # Referenz in diesem Moment löscht, überlässt das QThread-Objekt dem
        # Speicherbereiniger — und der zerstört das C++-Objekt unter einem
        # Thread, der gerade zu Ende geht. Das ist genau die Falle, vor der
        # ``_retired`` weiter oben warnt, hier nur von der anderen Seite.
        #
        # Der Absturz war eine Zugriffsverletzung ohne Zeile, in etwa jedem
        # achten Lauf von ``test_analysis_ui.py`` und in etwa jedem vierten
        # Lauf der ganzen Suite. Der Arbeiter wandert jetzt in dieselbe
        # Halteleine wie ein ersetzter und wird dort gelöst, wenn er
        # tatsächlich ausgelaufen ist.
        #
        # Vorher bekommt er das Abbruchzeichen: Sein Ergebnis will niemand
        # mehr, und bis er von allein fertig ist, rechnet er gegen den, der
        # gerade startet (§18.4).
        self._cancel_map_worker()
        self._retire(self._map_worker)
        self._map_worker = worker
        worker.finished.connect(lambda done=worker: self._map_worker_done(done))
        self._leash.start(worker)

    def _cancel_map_worker(self) -> None:
        """Der laufenden Karte sagen, dass niemand mehr auf sie wartet."""
        worker = self._map_worker
        if worker is not None and worker.isRunning():
            worker.cancel()

    def _map_worker_done(self, worker: Any) -> None:
        if self._map_worker is worker:
            self._map_worker = None
        self._hold_until_done(worker)

    def _hold_until_done(self, worker: Any) -> None:
        """Den fertigen Arbeiter halten, bis Qt mit ihm durch ist — die
        Halteleine steht in :mod:`app.ui.leash`, damit die Dialoge dasselbe
        Muster benutzen, statt es nachzubauen."""
        self._leash.hold_until_done(worker)

    def _retire(self, worker: Any) -> None:
        """Hält einen ersetzten Arbeiter fest, bis er ausgelaufen ist."""
        self._leash.retire(worker)

    def _map_crashed(self, detail: str) -> None:
        self.analysis_bar.show_problem(tr("Die Analysekarte ließ sich nicht berechnen."))
        self._on_error(InternalError(detail=detail))

    def _map_ready(self, analysis: Any, key: tuple[Any, ...], object_id: ObjectId) -> None:
        self._map_cache = {key: analysis}
        if self.analysis_bar.chosen() == key[1] and self.object_tree.selected() == object_id:
            self._show_map(analysis, object_id)
        # **Den Flug nachholen, auf den der Klick gewartet hat.** Der Ort eines
        # Kartenbefunds steht erst hier fest; wer ihn beim Klick sucht, findet
        # einen leeren Cache. Nur für den Befund, der noch gilt — wer inzwischen
        # etwas anderes angeklickt hat, will nicht dorthin.
        waiting = self._finding_awaiting_map
        self._finding_awaiting_map = None
        if waiting is None or analysis is None:
            return
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result else None
        if entry is None:
            return
        target = maps.location_of(entry, waiting) or maps.focus_point(entry, analysis)
        if target is not None:
            self._show_finding_at(waiting, entry, target)

    def _show_map(self, analysis: Any, object_id: ObjectId) -> None:
        self.viewport.set_analysis_map(analysis, object_id if analysis else None)
        self.analysis_bar.show_legend(analysis, self._feature_names())

    def _only_body(self) -> ObjectId | None:
        """Der einzige Körper der Szene — oder nichts, wenn es mehrere sind.

        Nach dem Öffnen einer Datei ist das der Normalfall: ein Teil, und der
        Kunde hat es nie „ausgewählt", weil es nichts auszuwählen gab. Ein
        Werkzeug, das ihn dann nach einer Auswahl fragt, fragt nach etwas,
        das nur eine Antwort hat (§2.4).
        """
        result = self.session.last_result
        if result is None or len(result.scene.objects) != 1:
            return None
        return next(iter(result.scene.objects))

    def _on_layer_changed(self, index: int) -> None:
        """Durch die Schichtanalyse fahren (§18.10) — Geometrie, keine
        Werkzeugwege.

        **Ohne Auswahl tat das Werkzeug stumm nichts.** Wer *Schichten*
        anklickte, bekam einen Regler, der sich ziehen ließ und nichts bewegte;
        der Grund stand als „Keine Auswahl" in der Statuszeile am unteren
        Fensterrand, also nicht dort, wo er gerade hinsah. Zwei Antworten
        darauf, und die erste ist die wichtigere: Bei genau einem Körper
        braucht es keine Auswahl, und sonst sagt die Leiste selbst, was fehlt.
        """
        object_id = self.object_tree.selected()
        if object_id is None and index >= 0:
            object_id = self._only_body()
        if index < 0 or object_id is None:
            self.viewport.set_layer(None)
            if index >= 0:
                # Auf das Teil zeigen, nicht auf den Baum: Wer aus einem Slicer
                # kommt, klickt das Modell an, nicht eine Zeile in einer Liste.
                self.layer_bar.show_note(
                    tr("Klicken Sie das Teil an, dessen Schichten Sie sehen möchten.")
                )
            return
        self.layer_bar.show_note("")
        # Eine gebundene Methode statt eines Lambdas je Schritt: sie ist bei
        # jedem Aufruf dieselbe, also reiht die Warteliste sie nur einmal ein —
        # und sie liest den Schieber erst, wenn das Ergebnis da ist. Gezeigt
        # wird die Schicht, auf der der Schieber jetzt steht, nicht die, auf
        # der er beim Start des Arbeiters stand.
        self._slice_of(object_id, self._show_current_layer)

    def _show_current_layer(self, result: SliceResult | None) -> None:
        self._show_layer(result, self.layer_bar.index())

    def _show_layer(self, result: SliceResult | None, index: int) -> None:
        if result is None or not result.layers:
            self.viewport.set_layer(None)
            return
        self.viewport.set_layer(result.layers[min(index, len(result.layers) - 1)])

    def _slice_of(self, object_id: ObjectId, then: Any = None) -> SliceResult | None:
        """Die Schichtanalyse eines Körpers — aus dem Cache oder gerechnet.

        Gerechnet wird im Arbeiter (§2.8): an einem großen Netz sind das
        Sekunden, und ein Fenster, das sie in der Ereignisschleife verbringt,
        hört auf zu zeichnen. Vorher stand hier ein Wartezeiger, und der macht
        aus einer Blockade nur eine angekündigte.

        Gibt das Ergebnis zurück, **wenn** es schon vorliegt; sonst ``None``
        und ``then`` wird gerufen, sobald es da ist.
        """
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result else None
        if entry is None:
            return None

        key = (object_id, entry.mesh.triangle_count)
        if key == self._slice_key:
            if then is not None:
                then(self._slice_cache)
            return self._slice_cache

        if self._slice_worker is not None and self._slice_pending == key:
            # Für diesen Körper rechnet schon ein Arbeiter. Ein zweiter täte
            # exakt dieselbe Arbeit noch einmal — und beim Ziehen durch die
            # Schichten hieße das: je Schritt ein weiterer, an einem
            # texturierten Netz jeder davon mit Sekunden an Rechenzeit, alle
            # gleichzeitig. Wer etwas vom Ergebnis will, stellt sich an; ein
            # Rückruf, der schon in der Reihe steht (die Schichtansicht bei
            # jedem Schritt), wird nicht doppelt eingereiht.
            if then is not None and all(waiter != then for waiter in self._slice_waiters):
                self._slice_waiters.append(then)
            return None

        self.status_message.setText(tr("Die Schichtanalyse läuft …"))
        worker = _SliceWorker(entry, self.session.profile.printer.layer_height)
        # Ohne Empfänger blieb „Die Schichtanalyse läuft …" für immer stehen,
        # und die Warteschlange der Druckeinstellungen leerte sich nie
        # (Gesamtreview I-2).
        worker.crashed.connect(self._slice_crashed)
        self._slice_pending = key
        self._slice_waiters = [] if then is None else [then]
        worker.done.connect(
            lambda outcome, key=key, worker=worker: self._slice_ready(outcome, key, worker)
        )
        # Dieselbe Halteleine wie bei der Analysekarte, und aus demselben
        # Grund: hier stand ein Lambda, das ``None`` in das Feld schrieb,
        # sobald *irgendein* Schnitt-Arbeiter fertig war. Wer durch die
        # Schichten schiebt, startet einen zweiten, während der erste noch
        # läuft — und dessen ``finished`` löschte dann die Referenz auf den
        # laufenden zweiten. Ein QThread ohne Referenz wird eingesammelt.
        self._retire(self._slice_worker)
        self._slice_worker = worker
        worker.finished.connect(lambda done=worker: self._slice_worker_done(done))
        self._leash.start(worker)
        return None

    def _slice_crashed(self, detail: str) -> None:
        """Wartezustand lösen: Zeile leeren, Anstehende verabschieden, Grund
        melden — sonst wartete der Druckeinstellungen-Dialog auf eine
        Analyse, die nie mehr kommt."""
        self._slice_pending = None
        self._slice_waiters = []
        self.status_message.setText("")
        self._on_error(InternalError(detail=detail))

    def _slice_worker_done(self, worker: Any) -> None:
        if self._slice_worker is worker:
            self._slice_worker = None
        self._hold_until_done(worker)

    def _slice_ready(self, outcome: SliceResult, key: tuple[Any, ...], worker: Any) -> None:
        if worker is not self._slice_worker:
            # Ein abgelöster Arbeiter — inzwischen rechnet ein neuer an einem
            # anderen Körper. Sein Ergebnis jetzt zu übernehmen zeigte die
            # Schichten des falschen Körpers und riefe Rückrufe, die auf den
            # neuen warten.
            return
        self._slice_cache = outcome
        self._slice_key = key
        self._slice_pending = None
        waiters, self._slice_waiters = self._slice_waiters, []
        self.layer_bar.show_result(outcome)
        self.status_message.setText(self._announcement)
        for waiter in waiters:
            waiter(outcome)

    def _run_on_chosen_bodies(self, action_id: str, bodies: object) -> None:
        """Eine Handlung aus einer Sammelzeile des Prüfberichts.

        Der gewöhnliche Weg geht über ``error_handlers`` und einen ``AppError``
        mit genau einem Körper. Eine Zeile, die zwölf vertritt, hat gefragt,
        welche gemeint sind (``BodyChoiceDialog``), und schickt sie hierher.

        Die Kennung der Handlung ist zugleich der Name der Operation —
        ``decimate_mesh`` heißt an beiden Enden gleich. Wo das nicht zutrifft,
        passiert nichts: Eine Sammelzeile mit einer Handlung ohne gleichnamige
        Operation gibt es heute nicht, und still das Falsche zu tun wäre
        schlechter, als nichts zu tun.
        """
        # bodies kommt über ein Qt-Signal und ist dort object — die
        # Prüfung hier ist die Stelle, an der aus "irgendetwas" eine Folge wird.
        if not isinstance(bodies, (tuple, list)):
            return
        wanted = tuple(str(entry) for entry in bodies)
        spec = next((entry for entry in REGISTRY.all() if entry.name == action_id), None)
        if spec is None or not wanted:
            return
        self.run_operation(spec, on_bodies=wanted)

    def _on_finding_activated(self, finding: Finding) -> None:
        """Eine Warnung anklicken, die Stelle sehen: der kürzeste Weg vom Problem
        zum Ort (§18.4).

        **Ein Klick auf einen Befund bleibt nie folgenlos.** Gestuft nach dem,
        was der Befund hergibt: Wo es einen Ort gibt, fliegt die Kamera hin und
        eine Marke steht dort; wo nur ein Körper genannt ist, wird der
        ausgewählt; und wo ein Schritt genannt ist, zeigt der Verlauf ihn.
        Gemessen am 30.08.2026 über alle 58 Befunde der Beispielprojekte: **58
        lösten gar nichts aus** — auch die fünfzig mit Analysekarte, deren Ort
        erst aus dem Kartencache kommt und der beim ersten Klick leer ist.
        """
        # **Der Schritt zuerst, denn er gilt unabhängig vom Körper.** Ein
        # Operationsfehler trägt eine ``op_id`` und sonst wenig; sie beantwortet
        # die Frage, die er stellt — welcher Schritt war es? Bei einem Befund
        # ohne Körper ist sie sogar die einzige Antwort, die es gibt.
        if finding.op_id is not None and self.history_panel.point_at(int(finding.op_id)):
            open_section(self.history_panel)

        object_id = finding.object_id or self.object_tree.selected()
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result and object_id else None
        if entry is None:
            return

        kind = maps.map_for(finding)
        if kind is not None:
            # Wie ``_show_error_location``: Das Werkzeug kommt mit, sonst
            # färbt die Karte das Modell ohne Legende und Kartenwähler —
            # reine Farbe ohne zweite Kodierung (Regel 18, §18.4).
            self.tools.activate("analysis")
            self.analysis_bar.show_map(kind)
            self._analysis_map(kind, entry.id)
            # Die Kamera geht zu dem Ort, den der Befund nennt. Wo der Befund
            # keinen eigenen Ort hat, hat die Karte einen — aber die Karte
            # rechnet vielleicht noch (§18.9), und die Ansicht wird nicht
            # dafür aufgehalten.
            target = maps.location_of(entry, finding)
            if target is None:
                cached = self._map_cache.get((entry.id, kind, entry.mesh.triangle_count))
                target = maps.focus_point(entry, cached) if cached is not None else None
        else:
            target = maps.location_of(entry, finding)

        # **Ein Klick auf einen Befund bleibt nie folgenlos** — und die drei
        # Stufen schließen einander nicht aus (§18.4). Hier stand nach dem Flug
        # ein ``return``, und die Auswahl darunter wurde nie erreicht: Wer auf
        # eine Warnung mit Ort klickte, bekam den Flug **statt** der Auswahl.
        # Regel und Docstring beschrieben sie gleichzeitig, der Code führte sie
        # exklusiv aus.
        #
        # Der Wächter daneben sah es nicht, weil er den Quelltext nach
        # ``select_object`` absucht: Der Aufruf stand da, er lief nur nicht.
        if target is not None:
            self._show_finding_at(finding, entry, target)
        elif kind is not None:
            # Die Karte rechnet noch. ``_map_ready`` holt den Flug nach, sobald
            # sie steht; bis dahin bleibt die Auswahl die Antwort.
            self._finding_awaiting_map = finding

        # Und der Körper wird ausgewählt, ob geflogen wurde oder nicht: Wer die
        # Stelle sieht, will auch wissen, zu welchem Teil sie gehört — bei zwei
        # Körpern auf dem Bett ist das nicht selbstverständlich.
        self.object_tree.select_object(entry.id)

    def _show_finding_at(self, finding: Finding, entry: Any, target: Vec3) -> None:
        """Zur Stelle eines Befunds fliegen und sie markieren.

        **Aus der Szene in die Ansicht, einmal.** Der Ort eines Befunds liegt in
        Szenenkoordinaten; im Bild steht der Körper auf seiner Platte und
        womöglich auseinandergezogen (§18.8, §25). Ohne die Umrechnung fliegt
        die Kamera bei einem Körper auf Platte 2 eine Bettbreite daneben — die
        Verwechslung, die beim Klick schon einmal eine Bohrung danebengesetzt
        hat, hier in der Gegenrichtung.

        Die Marke ist nötig, weil der Flug allein die Frage nicht beantwortet:
        Wo eine Analysekarte läuft, färbt sie die Stelle ein; wo keine läuft,
        stand der Kunde vor einem Teil, das überall gleich aussieht (§18.4).
        """
        self._finding_awaiting_map = None
        shown = self.viewport.view_point_of(target, entry.id)
        # **Der Abstand richtet sich nach dem Körper, nicht nach der Szene.**
        # Vermessen an der Dose (Kamera zurückgezogen, Blickrichtung gleich):
        # bei 0,26 Diagonalen war **eine** von acht Ecken im Bild, bei 1,2
        # sechs — dort springt aus „irgendeiner Fläche" ein erkennbares Teil,
        # und genau dort wird auch die Beschriftung der Marke sichtbar. Vorher
        # steht der Satz, für den die Marke da ist, außerhalb des Bildes.
        #
        # 1,4 statt 1,2 ist Sicherheitsabstand: Ein Wert direkt am Knick kippt
        # bei anderen Teilen und Blickwinkeln. Weiter hinaus (2,5) macht die
        # Marke klein, und der Zweck des Flugs ist, dass man die Stelle sieht.
        #
        # In Vielfachen der Diagonale und nicht in Millimetern — das gilt für
        # ein Teil jeder Größe. Gemessen werden konnte es nur an einem: Über
        # alle elf Beispiele trägt genau ein Befund einen Ort.
        self.viewport.fly_to(shown, reach=1.4 * float(entry.mesh.bounds.diagonal))
        self.viewport.mark_finding(target, str(finding.message), entry.id)

    # --- der Agent (§26) --------------------------------------------------------

    def _on_request_sent(self, request: str) -> None:
        """Ein Zug. Die Auswahl reist mit, sonst heißt „dieses Loch"
        nichts (§26.1).
        """
        backend = self.session.agent_backend
        try:
            target = target_for_backend(backend)
        except (TypeError, ValueError):
            result = DisclosureResult.FAILED
        else:
            result = (
                DisclosureResult.CURRENT
                if target is None
                else ensure_ai_disclosure(self.settings, target, self)
            )
        if not result.allowed:
            self._disclosure_stopped(
                request,
                rendering_problem=result is DisclosureResult.FAILED,
            )
            return
        self.chat.forget_restorable_request(request)
        selected = self.object_tree.selected()
        feature = self.object_tree.selected_feature()
        selection = (selected, feature or "") if selected else None
        self.session.propose_async(request, selection, backend=backend)

    def _disclosure_stopped(self, request: str, *, rendering_problem: bool) -> None:
        """Stellt den Auftrag wieder her und führt zurück zur Backend-Auswahl."""

        self.chat.restore_request(request)
        self.action_llm_key()
        if rendering_problem:
            self.chat.set_notice(
                tr(
                    "Der KI-Hinweis konnte nicht vollständig angezeigt oder gespeichert werden. "
                    "Wählen Sie den Chat-Zugang erneut und versuchen Sie es noch einmal."
                )
            )

    def _on_agent_busy(self, busy: bool) -> None:
        """Ein Zug dauert zehn bis sechzig Sekunden — §2.8 verlangt dafür
        Fortschritt **und** Abbrechen.

        Bisher gab es nur den Satz „Der Agent denkt nach.": der Knopf hing
        allein an der Auswertung, und ein Zug, der zu lange lief, war nur über
        das Schließen des Fensters zu beenden.
        """
        self.chat.set_busy(busy)
        if busy:
            # Wie viele Schritte ein Zug braucht, steht vorher nicht fest —
            # ein Balken ohne Ende sagt „es läuft", ohne etwas zu versprechen.
            text = tr("Der Agent denkt nach.")
            self._set_progress_state(
                "agent",
                active=True,
                text=text,
                minimum=0,
                maximum=0,
                value=0,
                accessible_description=text,
                cancel_enabled=True,
            )
            return
        self._set_progress_state("agent", active=False)
        self._update_waiting_state()

    def _on_agent_progress(self, step: int, label: str) -> None:
        """Was der Zug gerade tut, statt nur dass er läuft (§2.8).

        „Der Agent denkt nach." war die ganze Auskunft über zehn bis sechzig
        Sekunden — jetzt steht da, welcher Schritt läuft und welches Werkzeug
        (Konzept Agent-Vertiefung 4.1). Der Deckel dahinter, damit erkennbar
        ist, dass die Zahl nicht ins Leere wächst.
        """
        if not self.chat.busy:
            return
        text = f"{tr('Schritt')} {step}/{MAX_STEPS} — {label}"
        self._set_progress_state("agent", text=text, accessible_description=text)
        # **Und im Chat**, wo der Nutzer während eines Zuges hinsieht. Die
        # Statuszeile bleibt: Sie trägt den Deckel (``/MAX_STEPS``) und steht
        # auch dann, wenn der Chat zugeklappt ist.
        self.chat.show_progress(step, label)

    def _on_split_busy(self, busy: bool) -> None:
        """Die Trennebenensuche läuft — Fortschritt und Abbrechen wie bei
        jedem anderen Lauf über zwei Sekunden (§2.8)."""
        if busy:
            self._split_status_released = False
            self._split_bar_released = False
            self._split_patience.start()
            self._split_bar_delay.start()
            self._split_fraction = 0.0
            self._split_progress_text = tr("Die Trennebenen werden gesucht …")
            self._split_determinate = False
            self._split_started = time.monotonic()
            self._set_progress_state(
                "split",
                active=True,
                text=self._split_progress_text,
                minimum=0,
                maximum=0,
                value=0,
                accessible_description=self._split_accessibility(),
                cancel_enabled=True,
            )
        if not busy:
            self._split_patience.stop()
            self._split_bar_delay.stop()
            self._split_status_released = False
            self._split_bar_released = False
            self._split_started = None
            self._set_progress_state("split", active=False, cancel_enabled=True)
        self._update_waiting_state()

    def _release_split_status(self) -> None:
        """Gibt nach 0,2 Sekunden ausschließlich den Split-Statustext frei."""

        if not self._progress_states["split"].active:
            return
        self._split_status_released = True
        self._render_progress_state()

    def _release_split_bar(self) -> None:
        """Gibt nach zwei Sekunden Split-Balken und -Abbruch gemeinsam frei."""

        if not self._progress_states["split"].active:
            return
        self._split_bar_released = True
        self._render_progress_state(force_visible=True)

    def _on_split_progress(self, fraction: float, text: str) -> None:
        """Zeigt Grobsuche unbestimmt, Stützbewertung bestimmt und monoton."""
        fraction = min(1.0, max(0.0, fraction))
        if not text:
            # Der Kern beendet mit ``progress(1.0, "")``. Der leere Text
            # beendet die Phase nicht: Er bestätigt ihren vollständigen
            # Anteil, und Hilfstechnik soll weiter wissen, was fertig wurde.
            self._split_fraction = max(self._split_fraction, fraction)
            if self._split_determinate:
                value = round(self._split_fraction * 100)
                text = f"{self._split_progress_text}  ·  {value} %"
                self._set_progress_state(
                    "split",
                    text=text,
                    minimum=0,
                    maximum=100,
                    value=value,
                    accessible_description=self._split_accessibility(),
                )
            else:
                self._set_progress_state(
                    "split", accessible_description=self._split_accessibility()
                )
            return
        support = text == tr("Ausrichtung suchen")
        if support:
            self._split_determinate = True
            self._split_fraction = max(self._split_fraction, fraction)
            minimum, maximum = 0, 100
        else:
            self._split_determinate = False
            self._split_fraction = max(self._split_fraction, fraction)
            minimum, maximum = 0, 0
        self._split_progress_text = text
        parts = [text]
        if self._split_determinate:
            parts.append(f"{round(self._split_fraction * 100)} %")
            if left_over := remaining_time(self._split_started, self._split_fraction):
                parts.append(left_over)
        self._set_progress_state(
            "split",
            text="  ·  ".join(parts),
            minimum=minimum,
            maximum=maximum,
            value=round(self._split_fraction * 100),
            accessible_description=self._split_accessibility(),
        )

    def _split_accessibility(self) -> str:
        """Nennt Phase, Anteil und verfügbaren Ausweg ohne Farbaussage."""
        parts = [self._split_progress_text]
        if self._split_determinate:
            parts.append(f"{round(self._split_fraction * 100)} %")
        if self._progress_states["split"].cancel_enabled:
            parts.append(tr("Abbrechen ist verfügbar."))
        return "  ·  ".join(part for part in parts if part)

    def _on_split_cancel_requested(self) -> None:
        """Der Knopf wirkt sofort; der Arbeiter bestätigt das Ende später."""
        self._set_progress_state(
            "split",
            text=tr("Teilung wird abgebrochen …"),
            accessible_description=tr("Teilung wird abgebrochen …"),
            cancel_enabled=False,
        )
        self.announce(tr("Teilung wird abgebrochen …"))

    def _on_split_cancelled(self) -> None:
        """Erst der Arbeiter bestätigt, dass die Suche wirklich beendet ist."""
        self.announce(tr("Teilung abgebrochen. Modell und Verlauf sind unverändert."))

    def _on_proposal(self, preview: Any) -> None:
        """Ein Vorschlag ist da: zeigen, was er änderte — und entscheiden
        lassen, wo eine Entscheidung nötig ist.

        §26.5 lässt die Übernahme bei eindeutig umkehrbaren Operationen
        automatisch laufen, und Regel 19 kennt keine Bestätigung vor
        rücknehmbaren Handlungen. Die vier Bedingungen prüft der Kern
        (``agent_apply.auto_acceptable``); die Leiste wird dann zur
        Übernommen-Leiste mit dem Weg zurück — ein Klick, derselbe Effekt
        wie vorher zwei.
        """
        if preview.proposal.findings:
            # Die Befunde des Zugs — Verweigerung, Abschneiden, Prüfungen nach
            # jeder Op — hatten keinen Anzeigeweg: Sie standen am Vorschlag
            # und nirgends im Fenster. In den Prüfbericht wie jeder andere
            # Befund; die Chatblase fasst zusammen, der Bericht trägt alles.
            self.report.add_findings(list(preview.proposal.findings))
        if preview.proposal.empty and not preview.proposal.stopped:
            # Regel 19 im Geist: ein reiner Auskunftszug ist keine
            # Entscheidung. Übernehmen/Verwerfen über „Keine Änderung"
            # anzubieten war eine Wahl ohne Gegenstand — der Beitrag wird
            # sofort aufgezeichnet, und nur das Gespräch bleibt.
            #
            # **Nicht bei ``stopped``:** Eine Verweigerung oder ein
            # abgeschnittener Zug ist auch leer, aber kein Auskunftszug —
            # die Abkürzung warf ihn weg, und die Blase dazu blieb leer.
            self.session.discard_proposal(preview)
            self._proposal = None
            self.chat.show_proposal(None)
            self.chat.show_document(self.session.project.document)
            self._focus_chat()
            return
        if self.settings.auto_accept_reversible and agent_apply.auto_acceptable(preview.proposal):
            try:
                transaction = self.session.accept_proposal(preview)
            except AppError as error:
                # Derselbe Riss wie beim Klick auf Übernehmen: Der Stapel kann
                # sich zwischen Entwurf und Zustellung bewegt haben
                # (``history_moved``). Dann wird aus der automatischen
                # Übernahme ein normaler Vorschlag — mit dem Fehler dazu,
                # statt eines stummen Verlusts.
                show_error(error, self)
            else:
                self._proposal = None
                self._applied_transaction = transaction.id if transaction else None
                self.chat.show_applied(preview, transaction.id if transaction else "")
                self.chat.show_document(self.session.project.document)
                # Eine wartende Differenz eines abgelösten Vorschlags bliebe
                # sonst unbeschriftet über der neuen Szene stehen.
                self.viewport.show_difference(None)
                self.viewport.mark_preview("")
                self._focus_chat()
                return
        self._proposal = preview
        self.chat.show_proposal(preview)
        if preview.difference is not None:
            self.viewport.show_difference(preview.difference)
            self.viewport.mark_preview(
                tr("Vorschlag — noch nicht übernommen"),
                tr("Leertaste halten: vorher"),
            )
        self._focus_chat()

    def _on_proposal_accepted(self) -> None:
        if self._proposal is None:
            return
        try:
            self.session.accept_proposal(self._proposal)
        except AppError as error:
            # ``ValidationError(history_moved)`` landete auf stderr, und der
            # Klick blieb ohne jede Wirkung. Der Fehler trägt seine Handlung
            # (der Verweis in den Verlauf, §2.7); der Vorschlag bleibt
            # stehen — ihn wegzuräumen wäre die zweite stumme Folge desselben
            # Klicks, und Verwerfen geht weiterhin.
            show_error(error, self)
            return
        self._clear_proposal()

    def _on_proposal_discarded(self) -> None:
        if self._proposal is None:
            return
        self.session.discard_proposal(self._proposal)
        self._clear_proposal()

    def _on_applied_undone(self) -> None:
        """Der Rückgängig-Knopf der Übernommen-Leiste (§26.5).

        Er nimmt genau die Transaktion zurück, die die Leiste verspricht —
        und nur, wenn sie noch die oberste ist. Die Regel dazu wohnt im Kern
        (``agent_apply.undo_applied``, über ``Session.undo_applied``); hier
        von Hand geprüft war sie die dritte Ausschreibung derselben
        Bedingung, und ``proposal.py`` beschreibt, wie so etwas
        auseinanderläuft. Der Fall ist durch :meth:`_refresh_applied_bar`
        selten, aber nicht unmöglich — ein Fernaufruf läuft ohne
        ``projectChanged``-Lücke dazwischen.
        """
        applied = self._applied_transaction
        self._applied_transaction = None
        if applied and not self.session.undo_applied(applied):
            transactions = self.session.project.document.transactions
            if any(entry.id == applied for entry in transactions):
                self.announce(
                    tr(
                        "Inzwischen liegt Neueres obenauf — das Rückgängig im Menü "
                        "nimmt Schritt für Schritt zurück."
                    )
                )
        self._clear_proposal()

    def _clear_proposal(self) -> None:
        self._proposal = None
        self.chat.show_proposal(None)
        self.viewport.show_difference(None)
        self.viewport.mark_preview("")
        self.chat.show_document(self.session.project.document)

    def _focus_chat(self) -> None:
        if self.right.isVisible():
            switch(self.right, self.chat)

    # --- Trennen entlang einer gezeichneten Linie (§25) --------------------------

    def _on_split_point(self, point: Any) -> None:
        """Ein Klick setzt ein Ende der Trennlinie; zwei machen sie fertig.

        Der dritte Klick fängt von vorn an, statt nichts zu tun oder eine
        dritte Ecke anzulegen: Wer nach zwei Punkten noch einmal klickt, hat
        sich vertan — und einen Knopf dafür zu suchen wäre der Umweg, den
        dieses Werkzeug gerade abschaffen soll.
        """
        picked = (float(point[0]), float(point[1]), float(point[2]))
        if len(self._split_points) >= POINTS_NEEDED:
            self._clear_split_line()
        if not self._split_points:
            target = self.viewport.object_at(picked)
            if target is None:
                # Daneben geklickt. Die alte Linie muss dabei weg — sie stand
                # sonst weiter im Bild, der Knopf blieb bedienbar, und was er
                # dann täte, wäre nichts: der Körper unter ihr ist keiner mehr,
                # den dieser Klick meint.
                self._clear_split_line()
                self.announce(tr("Bitte auf das Teil klicken, das getrennt werden soll."))
                return
            self._split_target = target
        elif self.viewport.object_at(picked) != self._split_target:
            self.announce(tr("Den zweiten Punkt bitte auf demselben Teil anklicken."))
            return
        self._split_points.append(picked)
        if len(self._split_points) == POINTS_NEEDED:
            first, second = self._split_points
            self._split_plane = plane_through(first, second, self.viewport.view_direction())
            if self._split_plane is None:
                # Zwei Punkte genau hintereinander sehen im Bild aus wie
                # einer. Der erste bleibt stehen, damit nur der missglückte
                # zweite Klick wiederholt werden muss.
                self._split_points.pop()
                self.announce(
                    tr("Die zwei Punkte liegen hintereinander — bitte quer über das Teil zeichnen.")
                )
        self.viewport.show_split_line(
            self._split_points,
            plane=self._split_plane,
            target=self._split_target,
        )
        self.split_bar.show_points(len(self._split_points))

    def _clear_split_line(self) -> None:
        """Die gezeichnete Linie verwerfen — kein Undo nötig, es war nie eine
        Änderung."""
        self._split_points = []
        self._split_target = None
        self._split_plane = None
        self.viewport.clear_split_line()
        self.split_bar.show_points(0)

    def _end_split(self) -> None:
        """Was das Schließen des Werkzeugs zurücknimmt."""
        self.viewport.set_splitting(False)
        self._clear_split_line()
        self.split_bar.reset()

    def _apply_split_line(self) -> None:
        """§25: Aus der sichtbaren Ebene wird eine Transaktion.

        Die Blickrichtung wurde schon beim zweiten Punkt gelesen. Dadurch
        bleibt genau die Ebene, die im Bild stand, auch nach einer Kamerafahrt
        die Eingabe der Operation (§11.2).
        """
        if (
            len(self._split_points) < POINTS_NEEDED
            or self._split_target is None
            or self._split_plane is None
        ):
            return

        chosen = self.split_bar.values()
        pins = int(chosen["pins"])
        applied = self.session.split_along(
            self._split_target, self._split_plane, pins=pins, shape=str(chosen["shape"])
        )
        self.report.add_findings(applied.findings)
        self._queue_split_reveal(applied.object_ids)
        self._clear_split_line()
        connector_count = len(applied.fits)
        if not pins:
            message = tr("Getrennt — die Hälften sind zur Kontrolle geöffnet.")
        elif not connector_count:
            message = tr("Getrennt und geöffnet — die Schnittfläche ist zu klein für Passstifte.")
        elif connector_count == 1:
            message = tr("Getrennt und geöffnet: 1 Passstift an Teil A, passendes Loch an Teil B.")
        else:
            message = tr(
                "Getrennt und geöffnet: {count} Passstifte an Teil A, passende Löcher an Teil B."
            ).format(count=connector_count)
        self.announce(message)

    def _queue_split_reveal(self, object_ids: Sequence[ObjectId]) -> None:
        """Öffnet neue Hälften, sobald genau diese Ausgaben im Bild stehen."""
        self._pending_split_reveal = frozenset(object_ids)
        result = self.session.last_result
        if result is not None:
            self._reveal_split_result(result)

    def _reveal_split_result(self, result: EvaluationResult) -> None:
        """Macht Naht, Stifte und Löcher ohne gesuchten zweiten Griff sichtbar."""
        wanted = self._pending_split_reveal
        if len(wanted) < 2 or not wanted.issubset(result.scene.objects):
            return
        self._pending_split_reveal = frozenset()
        self.tools.activate("explode")
        self.explode_bar.reveal()

    # --- Sichtbarkeit (§18.8) ---------------------------------------------------

    def _on_visibility(self, objects: Any, visible: bool) -> None:
        """Ein- oder ausblenden. Ansicht, nicht Szene — der Körper bleibt in
        der Auswertung, im Prüfbericht und im Export.
        """
        chosen = set(objects)
        self._apply_hidden(self._hidden - chosen if visible else self._hidden | chosen)

    def _on_isolate(self, objects: Any) -> None:
        """Alles andere ausblenden — und derselbe Eintrag holt es zurück (§18.8).

        Beschriftung und Wirkung lasen dasselbe Feld mit verschiedener Frage:
        Rechtsklick auf einen **ausgeblendeten** Körper zeigte „Alles andere
        ausblenden" und blendete alles ein (Gesamtreview I-6). Jetzt gilt die
        Antwort des Baums für beide Seiten.
        """
        chosen = set(objects)
        result = self.session.last_result
        everything = set(result.scene.objects) if result else set()
        if self.object_tree.isolation_holds(tuple(chosen)):
            self._apply_hidden(frozenset())
        else:
            self._apply_hidden(frozenset(everything - chosen))

    def _apply_hidden(self, hidden: frozenset[str]) -> None:
        self._hidden = hidden
        self.viewport.set_hidden(hidden)
        self.object_tree.set_hidden(hidden)
        self.announce(f"{len(hidden)} × {tr('ausgeblendet')}" if hidden else "")

    def _on_feature_picked(self, feature_id: str) -> None:
        """Ein Klick in der Ansicht wählt das Merkmal auch im Baum aus (§18.5).

        Steht ein Dialog offen, der nach einem Merkmal fragt, bekommt er es —
        dann war der Klick eine Eingabe und keine Auswahl.
        """
        object_id = self.object_tree.selected()
        if object_id is not None:
            self.object_tree.select_feature(object_id, feature_id)
        dialog = self._op_dialog
        if dialog is not None:
            dialog.take_feature(feature_id, self._feature_names().get(feature_id, feature_id))
        # **Auch hier**, und nicht nur bei der Objektauswahl: Ein Klick auf ein
        # Merkmal ändert, was die Leiste anbieten darf, und `_on_selection`
        # läuft dabei nicht — der gewählte Körper bleibt ja derselbe.
        self._update_transform_roles()

    def _update_transform_roles(self) -> None:
        """Sagt der Bewegen-Leiste, welche Rollen die Auswahl zulässt.

        Die Frage steht hier und nicht in der Leiste, weil sie hier schon
        einmal steht: `feature_instead_of` beantwortet für Taste, Menü und
        Befehlspalette dasselbe. Zwei Antworten darauf liefen nach der nächsten
        Registeränderung auseinander, und dann graute das Menü etwas aus, das
        die Leiste noch anbietet.

        Drei Fälle, und der mittlere ist der, den Robert gemeldet hat:

        * **Kein Merkmal gewählt** — alles gilt dem Körper, nichts ist gesperrt.
        * **Ein Merkmal mit eigener Operation** (Bohrung: verschieben, drehen)
          — die Rolle bleibt frei und läuft über die Merkmalsoperation.
        * **Ein Merkmal ohne** (Fläche: drehen, skalieren) — gesperrt, mit dem
          Satz aus ``reason_against``. Er kommt aus dem Kern, damit Panel und
          Leiste denselben sagen.
        """
        from app.core.perceive.actions import reason_against

        feature = self._selected_feature_object()
        reasons: dict[str, str | None] = {}
        for key, op, _symbol in TRANSFORM_ROLES:
            if feature is None or self.feature_instead_of(op) is not None:
                reasons[key] = None
                continue
            # Kein Zwilling für diese Art: Der Satz sagt, warum.
            #
            # **Der Kern zuerst, der eigene Satz nur als Rückfall.**
            # ``reason_against`` kennt die Operation und die Merkmalsart und
            # sagt es genauer, als es hier möglich wäre; der Satz darunter
            # greift, wenn es gar keine Merkmalsoperation gibt (dann ist auch
            # nichts zu begründen als „nicht am Merkmal").
            #
            # ``str()`` und nicht ``TranslatableText``: Die Leiste schreibt den
            # Satz in einen Tooltip und in die Statuszeile, und beide wollen
            # eine Zeichenkette. Beim Sprachwechsel wird die Leiste ohnehin neu
            # gefüttert, weil sich mit der Sprache auch die Auswahl neu
            # anzeigt — ein mitreisender ``TranslatableText`` brächte hier
            # nichts, was nicht schon da wäre.
            twin = FEATURE_TWINS.get(op)
            spoken = reason_against(twin, feature.kind) if twin else None
            reasons[key] = str(spoken or _("Das geht an einem gewählten Merkmal nicht."))
        self.transform_bar.limit_roles(reasons)

    def _on_point_picked(self, point: Any) -> None:
        """Ein Klick auf eine Stelle füllt die Positionsfelder eines offenen
        Dialogs (§18.5).

        *Bohrung setzen* öffnete mit X, Y und Z auf 0,00 — und der Ursprung
        liegt bei einer geladenen Platte an einer Ecke. Wer dort bohrte,
        kratzte einen Span von der Kante ab, und der Prüfbericht sagte nur, die
        Bohrung sei um die Materialtoleranz vergrößert worden.
        """
        dialog = self._op_dialog
        if dialog is not None:
            dialog.take_point((float(point[0]), float(point[1]), float(point[2])))

    def _on_viewport_context_menu(self, x: int, y: int) -> None:
        """Zeigt am Zeiger dasselbe Menü, das der Objektbaum anbietet (§18.5).

        Gebaut wird es dort, weil es dort schon steht: dieselbe Sichtbarkeit,
        dieselben Operationen aus ``applies_to``. Zwei Menüs mit derselben
        Aufgabe wären zwei Gelegenheiten, auseinanderzulaufen.

        VTK zählt seine Fensterkoordinaten von unten, Qt von oben — die
        Umrechnung passiert hier, weil hier beide Seiten bekannt sind.
        """
        menu = self.object_tree.context_menu()
        if menu is None:
            return
        menu.exec(self.viewport.mapToGlobal(self._from_vtk_point(x, y)))

    def _on_sketch_menu(self, point: object, x: int, y: int) -> None:
        """Das Kontextmenü der Zeichnung, am Zeiger (§30.1, P4).

        Gebaut wird es vom Canvas (``context_menu_on_plane``), gezeigt hier —
        dieselbe Trennung wie überall: Ein Menü, das sich selbst öffnet, hält
        eine Suite an. Ohne diesen Weg war das Menü im Viewport-Modus
        unerreichbar, und der Rechtsklick verstellte beim Zeichnen die
        Objektauswahl.
        """
        panel = self._sketch_panel
        if panel is None or not isinstance(point, tuple) or len(point) != 2:
            return
        menu = panel.canvas.context_menu_on_plane((float(point[0]), float(point[1])))
        if menu.isEmpty():
            return
        menu.exec(self.viewport.mapToGlobal(self._from_vtk_point(x, y)))

    def _from_vtk_point(self, x: int, y: int) -> QPoint:
        """Eine VTK-Fensterstelle als Qt-Logikpunkt des Viewports.

        VTK zählt von unten und in Gerätepunkten (pyvistas ``rwi`` rechnet
        jede Mausposition mit ``devicePixelRatio`` hoch); Qt zählt von oben
        und in Logikpunkten. Wer nur die Höhe umrechnet, öffnet auf einem
        skalierten Bildschirm das Menü neben dem Zeiger. Bei dpr 1,0 ändert
        der Faktor nichts.
        """
        ratio = float(self.viewport.devicePixelRatioF()) or 1.0
        return QPoint(int(x / ratio), int(self.viewport.height() - y / ratio))

    def _on_sketch_on_face(self, feature_id: str) -> None:
        """Ein Klick auf eine Fläche beginnt dort eine Skizze (§30.1).

        Der Baum meldet nur die Merkmalskennung; die Ebene daraus zu bauen ist
        Sache des Fensters — eine ``feature:``-Ebene ist ein Begriff des Kerns
        (``app.core.sketch.planes``), und der Objektbaum kennt den
        Skizzenmodus nicht.

        **Ohne festgelegte Operation.** Was aus der Zeichnung wird, fragt der
        Dialog bei „Fertig" (§2.2, Weg 2) — auf einer Deckfläche ist eine
        Tasche so plausibel wie ein Aufbau, und die Entscheidung vorwegzunehmen
        hieße, dem Nutzer eine von zwei gleich guten zu nehmen.
        """
        object_id = self.object_tree.selected()
        plane = (
            feature_plane(object_id, feature_id)
            if object_id is not None
            else f"feature:{feature_id}"
        )
        self.start_sketch("", plane=plane)

    def _on_object_picked(self, object_id: str) -> None:
        """Ein Klick auf einen Körper wählt ihn im Baum aus; einer daneben hebt
        die Auswahl auf.

        Damit gilt endlich, was das Navigationsschema verspricht und das
        Handbuch beschreibt: links wählt aus. Bis hierher ging Auswählen nur
        über den Baum — und wer die Bohrung meinte, musste ihren Namen kennen.
        """
        self.object_tree.select_object(object_id or None)

    def _on_feature_selected(self, feature_id: str | None) -> None:
        """Das gewählte Merkmal — in der Ansicht, in der Statusleiste und im
        Panel, das seine Maße änderbar zeigt."""
        self.viewport.select_feature(feature_id)
        # Eine Vorschau, die zum vorigen Merkmal gehört, hat hier nichts mehr
        # zu suchen — sie zeigte eine Änderung an etwas, das nicht mehr gewählt
        # ist.
        self._drop_feature_preview()
        if feature_id is None:
            self.feature_panel.clear()
            return
        result = self.session.last_result
        object_id = self.object_tree.selected()
        entry = result.scene.objects.get(object_id) if result and object_id else None
        feature = entry.features.get(feature_id) if entry is not None else None
        if entry is not None and feature is not None:
            self.measurements.setText(f"{entry.name} · {feature_label(feature_id, feature)}")
            # **Die gleichartigen Geschwister kommen mit.** Der Objektbaum
            # führt sie längst unter einem Dach; das Panel bietet damit an, eine
            # Handlung für alle zu tun, statt sie sechsmal zu wiederholen.
            alike = [
                other
                for other, candidate in entry.features.items()
                if other != feature_id and candidate.kind == feature.kind
            ]
            self.feature_panel.show_feature(feature_id, feature, alike)
            self.feature_dock.reveal()
        else:
            self.feature_panel.clear()

    def _on_features_selected(self, chosen: list[Any]) -> None:
        """Zwei markierte Merkmale: das Panel zeigt, wie weit sie auseinander
        stehen.

        **Nur bei genau zweien und nur am selben Körper.** Bei einem gilt der
        gewöhnliche Weg (:meth:`_on_feature_selected` hat ihn schon gefüllt);
        bei dreien gibt es keine Strecke, sondern drei, und welche gemeint
        wäre, kann niemand wissen. Über zwei Körper hinweg wäre der Abstand
        zwar rechenbar, aber die beiden stehen in verschiedenen Verläufen — was
        man damit täte, ist eine andere Frage als „wie weit sitzen die zwei
        Bohrungen in diesem Teil".
        """
        if len(chosen) != 2:
            return
        (first_object, first_id), (second_object, second_id) = chosen
        if first_object != second_object:
            return
        result = self.session.last_result
        entry = result.scene.objects.get(first_object) if result is not None else None
        if entry is None:
            return
        first = entry.features.get(first_id)
        second = entry.features.get(second_id)
        if first is None or second is None:
            return
        self.feature_panel.show_pair(first_id, first, second_id, second)
        self.feature_dock.reveal()

    def _apply_to_each_feature(
        self, op: str, params: dict[str, Any], feature_ids: list[str]
    ) -> None:
        """Dieselbe Handlung für mehrere gleichartige Merkmale — **eine**
        Transaktion (Regel 16).

        Ein Draft je Merkmal, alle in einem ``apply``: Ein Strg+Z nimmt sie
        zusammen zurück, weil es eine Handlung war. Sechs einzelne Aufrufe wären
        sechs Schritte im Verlauf und sechs Undos für einen Handgriff.
        """
        selected = self.object_tree.selected()
        if selected is None or not REGISTRY.has(op) or not feature_ids:
            return
        drafts = [
            OperationDraft(op=op, inputs=(selected,), params={**params, "at_feature": feature_id})
            for feature_id in feature_ids
        ]
        self._drop_feature_preview()
        self.session.apply(REGISTRY.get(op).title, drafts, bundle=True)

    def _drop_feature_preview(self) -> None:
        """Die wartende Vorschau des Merkmalsfensters fällt.

        **Vier Dinge, und alle vier einzeln nötig.** Der gemerkte Posten, weil
        der Zeitgeber sonst eine Änderung von vorhin rechnet; der Zeitgeber,
        weil er sonst nach dem Übernehmen noch einmal feuert; die Rechnung,
        weil ein Arbeiter, der schon läuft, sein Ergebnis sonst über das
        fertige Teil legt (``session.apply`` dreht die Vorschau-Generation
        nicht weiter); und das **Bild**, weil das Abbrechen einer Rechnung
        nichts wegnimmt, was schon gezeichnet ist.

        Das Bild ist der Teil, an dem zwei Sitzungen vorbeigelaufen sind, und
        er wiegt am schwersten. Sichtbar bleibt der Differenzkörper der alten
        Vorschau über der neuen Geometrie liegen, mit einem Band, das sagt, sie
        sei nicht übernommen. Unsichtbar bleibt mit dem Band ``_comparing``
        stehen, und mit ihm ein **anwendungsweiter** Ereignisfilter: Die
        Leertaste blendet danach überall zwischen „mit" und „ohne" um.
        ``mark_preview("")`` nimmt beides zurück, und ``_clear_preview`` tut
        genau das — mitsamt der Frage, ob ein wartender Agentenvorschlag seine
        Differenz zurückbekommt (gefunden von 3d-druck-85, 03.09.2026).

        Am 03.09.2026 stand der Abbau nur im Weg *abwählen*, und auch dort nur
        zur Hälfte. Der Weg *anwenden* führte ganz daran vorbei — die Form, in
        der dieser Fehler an diesem Tag mehrfach auftrat: Der Abbruch war
        bedacht, das Fertigwerden nicht.
        """
        if self._feature_pending is None and not self._feature_preview.isActive():
            # **Nichts zu tun, und das ist der Normalfall.** Seit dieser Abbau
            # am Dokumentwechsel hängt, läuft er bei jedem Anwenden, jedem Undo
            # und jedem geänderten Parameter — und ``_clear_preview`` ist nicht
            # billig: ``show_difference`` färbt die Auswahl neu, zeichnet die
            # Merkmale neu, die Differenz neu und stößt einen Bildaufbau an.
            # Ohne diese Zeile kostete das jeden Dokumentwechsel einen vollen
            # Neuaufbau, für den es nichts abzuräumen gab (§31).
            #
            # Gefragt wird nach dem Merkposten und dem Zeitgeber, nicht nach
            # dem Bild: Der Merkposten bleibt gesetzt, solange eine Vorschau
            # dieses Fensters wartet **oder** schon gezeichnet ist —
            # ``_preview_feature_change`` liest ihn und leert ihn nicht.
            return
        self._feature_pending = None
        self._feature_preview.stop()
        self._clear_preview()

    def _on_feature_values_changed(self, op: str, params: dict[str, Any]) -> None:
        """Eine geänderte Zahl im Merkmalspanel — erst zeigen, nicht tun.

        Robert am 03.09.2026: „eine live vorschau wäre noch gut." Gemerkt und
        verzögert: Wer 16 tippt, tippt zuerst 1, und eine Boolesche über das
        ganze Teil je Tastendruck macht das Feld unbenutzbar.
        """
        self._feature_pending = (op, dict(params))
        self._feature_preview.start()

    def _preview_feature_change(self) -> None:
        """Rechnet die gemerkte Änderung und legt sie ins Bild (§18.7).

        **Über denselben Weg wie der Operationsdialog**: `preview_async` rechnet
        im Arbeiter, eine jüngere Anfrage ersetzt die wartende, und gezeigt wird
        nur das Jüngste. Was hier entsteht, ist eine Vorschau und kein
        Dokumentzustand (Regel 2) — im Verlauf steht erst etwas, wenn der Knopf
        gedrückt wird.
        """
        merkposten = self._feature_pending
        if merkposten is None:
            return
        op, params = merkposten
        selected = self.object_tree.selected()
        if selected is None or not REGISTRY.has(op):
            return
        self.session.preview_async(
            self._show_preview, [OperationDraft(op=op, inputs=(selected,), params=params)]
        )

    def _apply_from_feature_panel(self, op: str, params: dict[str, Any]) -> None:
        """Eine geänderte Zahl im Merkmal-Panel wird ein Schritt im Verlauf.

        Dasselbe wie bei der Bewegen-Leiste: Das Panel rechnet nichts und
        ändert nichts, es nennt eine registrierte Operation und ihre Werte
        (Regel 2). Der Körper kommt aus der Auswahl — welches Merkmal gemeint
        ist, steht schon in ``at_feature``.
        """
        object_id = self.object_tree.selected()
        if object_id is None:
            self.announce(_needs_objects(0))
            return
        self._drop_feature_preview()
        draft = OperationDraft(op=op, inputs=(object_id,), params=params)
        self.session.apply(REGISTRY.get(op).title, [draft])

    def close_measuring(self) -> None:
        """Das Messwerkzeug schließen: Modus aus, Maße weg.

        Ein Maß ist eine Auskunft und kein Dokumentzustand (Regel 2). Vorher
        schaltete das Schließen nur den Modus ab, und die Linien blieben im
        Bild stehen — ohne die Leiste, an der ein Knopf zum Löschen sitzt.
        """
        self.measure_bar.mode.setCurrentIndex(0)
        self.viewport.clear_measurements()

    def _on_section(self, plane: object, thickness: object) -> None:
        self.viewport.set_section(plane, thickness)  # type: ignore[arg-type]
        self.section_bar.show_capping_state(self.viewport.section_uncapped)

    def action_theme(self, theme: str) -> None:
        application = QApplication.instance()
        if application is not None:
            apply_theme(application, theme)  # type: ignore[arg-type]
        self.viewport.set_theme(theme)
        self.object_tree.set_theme(theme)
        self._apply_card_style(theme)
        self.settings.theme = theme
        save_settings(self.settings)
        _tick(self._theme_group, theme)

    def _apply_card_style(self, theme: str) -> None:
        """Die schwebenden Zonen decken, was hinter ihnen liegt.

        Auf dem Fenster und nicht auf der Anwendung: das anwendungsweite
        Stylesheet gehört ``style.py``, und zwei Stellen, die es setzen, wären
        zwei Stellen, an denen ein Themenwechsel halb ankommt.
        """
        self.overlay.setStyleSheet(card_stylesheet(theme))  # type: ignore[arg-type]
        self.header.setStyleSheet(header_stylesheet(theme))
        # Der Schleier zeichnet den Verlauf der Ansicht nach und braucht
        # dieselben Farben wie sie.
        self.veil.set_theme(theme)

    def action_navigation(self, scheme: str) -> None:
        self.viewport.set_navigation(scheme)  # type: ignore[arg-type]
        self.settings.navigation = scheme
        save_settings(self.settings)
        _tick(self._navigation_group, scheme)

    def action_display_mode(self, mode: str) -> None:
        """Massiv, mit Kanten, Drahtgitter oder transparent — und gemerkt.

        **Der Weg über diese Methode ist der des Nutzers.** Der Skizzenmodus
        stellt daneben direkt am Viewport um (`set_display_mode`) und nimmt es
        beim Verlassen zurück; das ist eine Leihgabe und keine Entscheidung,
        also wird sie nicht gespeichert.
        """
        self.viewport.set_display_mode(mode)  # type: ignore[arg-type]
        self.settings.display_mode = mode
        save_settings(self.settings)
        _tick(self._mode_group, mode)

    def action_shading(self, shading: str) -> None:
        """Flach oder weich — dieselbe Bauart wie eine Methode darüber."""
        self.viewport.set_shading(shading)  # type: ignore[arg-type]
        self.settings.shading = shading
        save_settings(self.settings)
        _tick(self._shading_group, shading)

    def action_projection(self, projection: str) -> None:
        """Perspektivisch oder orthografisch.

        Wer misst, arbeitet orthografisch, und wer das einmal eingestellt hat,
        meint es dauerhaft (§18.1). Der Skizzenmodus stellt sie ebenfalls
        vorübergehend um und nimmt es zurück — auch das ist keine Entscheidung.
        """
        self.viewport.set_projection(projection)  # type: ignore[arg-type]
        self.settings.projection = projection
        save_settings(self.settings)
        _tick(self._projection_group, projection)

    def run_operation(
        self,
        spec: OperationSpec,
        given: Mapping[str, Any] | None = None,
        *,
        on_bodies: Sequence[ObjectId] | None = None,
    ) -> None:
        """Menüeintrag, Dialog, Transaktion — derselbe Weg, den auch der Agent
        nehmen wird.

        ``given`` belegt Felder vor, die der Aufrufer schon kennt — der
        Skizzenmodus reicht so seine gezeichnete Skizze herein. Es ersetzt den
        Dialog nicht: die übrigen Werte fragt er weiter, und was hier steht,
        lässt sich dort ändern.

        ``on_bodies`` wendet dieselbe Operation auf **mehrere** Körper an, mit
        denselben Werten und in **einer** Transaktion (Regel 16: ein Undo nimmt
        sie vollständig zurück). Der Weg kommt aus dem Prüfbericht: Eine
        Sammelzeile vertritt sechs oder zwölf Körper, und ihre Handlung fragt
        beim Klick, für welche davon sie gelten soll. Der Dialog fragt die
        Werte dabei **einmal** — sechs gleiche Dialoge hintereinander wären
        dieselbe Frage sechsmal. Die Auswahl im Objektbaum bleibt außen vor:
        Was hier gilt, hat der Kunde in der Liste angehakt und nicht im Baum
        markiert.
        """
        # **Erst das Merkmal, dann der Körper** (Robert, 03.09.2026: „wenn wir
        # ein Merkmal auswählen und auf der Tastatur Entf drücken löschen wir
        # den ganzen Körper statt das Merkmal"). Der Weg gilt für jeden
        # Aufrufer dieser Methode — Taste, Menüeintrag, Befehlspalette —, weil
        # die Frage hier steht und nicht an jeder Taste neu.
        #
        # **Ohne Dialog, wenn nichts zu fragen bleibt.** *Merkmal entfernen*
        # kennt nur ``at_feature``, und das steht in der Auswahl; ein Dialog
        # dafür wäre eine Frage, deren Antwort schon dasteht — und vor einer
        # rücknehmbaren Handlung verbietet Regel 19 sie ohnehin.
        instead = self.feature_instead_of(spec.name)
        if instead is not None:
            feature_id = self.object_tree.selected_feature()
            unanswered = [
                entry.name for entry in instead.params.spec() if entry.name != "at_feature"
            ]
            if feature_id is not None and not unanswered:
                self._feature_step(str(instead.name), feature_id, {})
                return
            spec = instead
            given = {**(given or {}), "at_feature": feature_id}

        if self.session.history.discardable and not confirm_discard(
            self.session.history.discardable, self._discarded_names(), self
        ):
            return

        result = self.session.last_result
        objects = list(result.scene.objects) if result else []
        # Die Körper der Sammelzeile treten an die Stelle der Baumauswahl —
        # sonst fragte die Prüfung darunter nach einer Markierung, die für
        # diesen Weg nie gemeint war.
        chosen = tuple(on_bodies) if on_bodies else self.object_tree.selected_objects()
        if spec.consumes and len(chosen) < spec.consumes:
            QMessageBox.information(self, str(spec.title), _needs_objects(spec.consumes))
            return

        if spec.takes_whole_scene and not objects:
            QMessageBox.information(self, str(spec.title), tr("Die Szene ist leer."))
            return

        values = dict(self._from_selection(spec, chosen[0] if chosen else None))
        values.update(self._spacing_for(spec))
        values.update(given or {})
        inputs = inputs_for(spec, objects, chosen)
        # Was der Dialog über seinen Bezug sagt — leer, solange genau so viel
        # gewählt ist, wie die Operation nimmt.
        note = (
            _works_on(
                [self._object_names().get(entry, "") for entry in inputs],
                len(chosen),
                spec.consumes,
            )
            if inputs and not spec.takes_whole_scene
            else ""
        )
        # Der gemessene Durchmesser gehört in den Dialog: Die Anwendung kennt
        # ihn und sagt ihn, statt wortlos eine Größe vorzuschlagen, die nicht
        # dazu passt. Formuliert im Kern (bore_advice), gezeigt hier — und nur
        # bei den Dialogen, die aus der Bohrung eine Größe ableiten.
        picked = self.object_tree.selected_feature()
        entry = result.scene.objects.get(chosen[0]) if result and chosen else None
        feature = entry.features.get(picked) if entry and picked else None
        if feature is not None and feature.kind == "hole" and advises_on_bores(spec):
            diameter = feature.params.get("diameter")
            if diameter is not None:
                said, choices = bore_advice(float(diameter))
                # **Eine Frage ohne Antwortweg ist keine Frage, sondern eine
                # Sackgasse.** Wo keine Normgröße passt, endet der Satz aus dem
                # Kern mit „Zu welcher Schraube gehört sie?" und bringt die
                # beiden Nachbargrößen mit; bis zum 03.09.2026 hat die
                # Oberfläche sie in einen Unterstrich geworfen. Gemessen an
                # 7,50 mm: gefragt wurde, `['M6', 'M8', 'Selbst eintragen']`
                # wurde verworfen — dieselbe Lücke, die §2.7 bei Fehlern
                # schließt („ein Fehler endet nie mit fehlgeschlagen").
                #
                # Wo eine Größe passt, ist die Liste leer und der Satz steht
                # allein; das ist die Unterscheidung, die `bore_advice`
                # ausdrücklich trifft, und sie bleibt unangetastet.
                if choices:
                    options = str(_("Infrage kommen: {list}.")).format(list=", ".join(choices))
                    said = f"{said} {options}"
                note = f"{note}\n{said}" if note else said

        def run(params: Mapping[str, Any]) -> None:
            if spec.name in LID_OPS and inputs:
                # Der Deckel geht über seinen Ablauf, nicht über die nackte
                # Operation: erst der trägt das Paar aus Öffnung und Kragen als
                # Passung ein (§14), und daran hängen im Slicer die genaue
                # Außenwand, die gebremste Beschleunigung und das Bügeln.
                applied = self.session.create_lid(inputs[0], dict(params), op=spec.name)
                self.report.add_findings(applied.findings)
                return
            count_before = len(self.session.project.document.ops)
            # Ein Schritt je Körper, alle in einer Transaktion: Die Operation
            # verbraucht einen (``consumes``), die Handlung meint zwölf.
            drafts = (
                [
                    OperationDraft(op=spec.name, inputs=(body,), params=dict(params))
                    for body in on_bodies
                ]
                if on_bodies
                else [OperationDraft(op=spec.name, inputs=inputs, params=dict(params))]
            )
            self.session.apply(spec.title, drafts, bundle=bool(on_bodies))
            operations = self.session.project.document.ops
            if spec.name == "split_pinned" and len(operations) > count_before:
                self._queue_split_reveal(operations[-1].outputs)

        if spec.params.spec():
            # Zusammengelegte Zwillinge (MENU_TWINS): derselbe Dialog trägt
            # hinten einen Umschalter, und erst er entscheidet, welche der
            # beiden Ops rechnet — Mesh oder exakter Kern. Die Parameter
            # werden auf das Schema der gewählten Op gefiltert (der exakte
            # Quader kennt kein ``anchor``, der exakte Zylinder keine
            # ``segments``).
            #
            # Den Umschalter bekommt nur, wer einen deklariert hat
            # (``TWIN_TOGGLES``). Die Beschriftung stand hier als feste
            # Zeichenkette, und damit taugte die ganze Zusammenlegung für
            # nichts als die zwei Rechenkerne: *An Ebene teilen* unter
            # *Teilen* hätte einen Haken bekommen, der von einem exakten
            # Körper spricht, den es dort nicht gibt.
            #
            # Dieses dritte Paar gibt es nicht mehr — es rechnete wirklich
            # dasselbe und ist in Formatversion 11 in *Teilen* aufgegangen.
            # Ein Zwilling, der keinen Umschalter braucht, gehört in eine
            # Migration und nicht hierher: Aus dem Menü war er fort, in der
            # Befehlspalette stand er weiter.
            hidden_twin = next(
                (
                    hidden
                    for hidden, shown in MENU_TWINS.items()
                    if shown == spec.name and hidden in TWIN_TOGGLES
                ),
                None,
            )
            exact: QCheckBox | None = None
            if hidden_twin is not None:
                label, hint = TWIN_TOGGLES[hidden_twin]
                exact = QCheckBox(str(label), self)
                exact.setToolTip(str(hint))
                self._lock_twin_toggle(exact, hidden_twin, len(objects), len(chosen))

            # **Die Variantengruppe (VARIANT_GROUPS), und warum sie eine Liste
            # bekommt und keinen Haken.** Ein Haken trägt zwei Zustände; hier
            # sind es vier Arten, aus einer Grundform einen Körper zu machen.
            # Sie schließen einander aus und sind gleichrangig — keine ist die
            # Abweichung von einer anderen, wie es der exakte Kern vom Netz
            # ist. Ein Zwilling und eine Gruppe treffen nie zusammen: Keine
            # Op steht in beiden Tabellen.
            group = group_for_variant(spec.name)
            variant: QComboBox | None = None
            if group is not None:
                variant = QComboBox(self)
                for name in group.members:
                    variant.addItem(str(REGISTRY.get(name).title), name)
                    # **Eine Variante mit Eingang fragt ihre Bedingung vorher.**
                    # Vier der fünf Arten erzeugen aus dem Nichts; *Tasche
                    # schneiden* braucht einen Körper (`consumes=1`). Ohne
                    # diese Sperre steht sie wählbar in der Liste, der Dialog
                    # geht durch, und die Auswertung hält danach an — dieselbe
                    # Lage, die bei den Zwillingen schon einmal gemessen wurde
                    # (`oberflaeche.md`, „Ein Umschalter, dessen Zwilling eine
                    # Bedingung hat, fragt sie — vorher").
                    #
                    # Gefragt wird über `_reason_locked`, also dieselbe Kette
                    # wie Menüleiste und Kontextmenü: eine dritte Formulierung
                    # derselben Auskunft wäre eine dritte Gelegenheit,
                    # auseinanderzulaufen.
                    locked = self._reason_locked(
                        REGISTRY.get(name),
                        self._kinds_of_selection(self.session.last_result),
                        len(objects),
                        len(chosen),
                    )
                    model = variant.model()
                    if locked and isinstance(model, QStandardItemModel):
                        item = model.item(variant.count() - 1)
                        item.setEnabled(False)
                        item.setToolTip(locked)
                        # Regel 18: der Grund steht nicht nur am Zeigerbild.
                        item.setData(locked, Qt.ItemDataRole.AccessibleDescriptionRole)
                variant.setToolTip(str(group.doc))

            def chosen_spec() -> OperationSpec:
                if variant is not None:
                    return REGISTRY.get(str(variant.currentData()))
                if exact is not None and exact.isChecked() and hidden_twin is not None:
                    return REGISTRY.get(hidden_twin)
                return spec

            def fitted(entered: Mapping[str, Any]) -> dict[str, Any]:
                allowed = {entry.name for entry in chosen_spec().params.spec()}
                return {key: value for key, value in entered.items() if key in allowed}

            dialog = OperationDialog(
                spec,
                self._object_names(),
                self,
                values=values,
                sources=self._source_names(),
                parameter_values=self._parameter_values(),
                # **Auch hier die Merkmale**, nicht nur beim Korrigieren einer
                # bestehenden Operation. Ohne sie baut der Dialog seine
                # Auswahl aus dem *Wert*, den er mitbekommt: Aus „hole_1"
                # wurde ein Eintrag „hole_1", und die übrigen Flächen des
                # Körpers kannte die Liste nicht. Das ist der Hauptweg — das
                # Kontextmenü am Merkmal (Weg 1) und die Menüs *Erzeugen* und
                # *Ändern* laufen hier durch —, und der Docstring des
                # Parameters verspricht die lesbare Bezeichnung. Gemessen:
                # ohne Liste „hole_1", mit Liste „Bohrung 1 · Ø5,2".
                #
                # Verengt auf die Arten, die diese Operation nimmt: eine
                # Auswahl, in der nichts passt, ist keine (§18.5).
                features=self._feature_names(spec),
                extra=exact if exact is not None else variant,
                extra_label=str(group.choice) if group is not None else "",
                surroundings=self._sketch_surroundings(),
                images=self._image_names(),
                pick_image=self._pick_image_source,
                pick_source=self._pick_model_source,
                slots=self._slots_of_selection(),
                note=note,
            )
            if variant is not None:
                # Dieselbe Pflicht wie beim Kernwechsel: Was der Dialog zeigt
                # und was die Vorschau rechnet, muss dieselbe Variante sein.
                variant.currentIndexChanged.connect(lambda: dialog.switch_variant(chosen_spec()))
                variant.currentIndexChanged.connect(dialog.valuesChanged)
            if exact is not None:
                # Die Live-Vorschau (§18.7) muss den Kernwechsel mitmachen —
                # eine Vorschau der falschen Variante wäre gelogen. Und der
                # Dialog zeigt danach nur noch, was die gewählte Variante
                # kennt: die Werte wurden schon vorher gefiltert, die Felder
                # standen weiter da und versprachen eine Wirkung, die es nicht
                # gab (Bezugspunkt beim exakten Quader, Segmentzahl beim
                # exakten Zylinder).
                exact.toggled.connect(lambda: dialog.switch_variant(chosen_spec()))
                exact.toggled.connect(dialog.valuesChanged)
            # §18.7: der Dialog zeigt, was er täte, während getippt wird —
            # dieselbe Differenzansicht wie beim Agentenvorschlag.
            self._wire_preview(
                dialog,
                lambda entered: [
                    OperationDraft(op=chosen_spec().name, inputs=inputs, params=fitted(entered))
                ],
            )
            dialog.place_beside(self.viewport)

            def run_chosen() -> None:
                picked = chosen_spec()
                if picked is spec:
                    run(dialog.values())
                    return
                self.session.apply(
                    picked.title,
                    [OperationDraft(op=picked.name, inputs=inputs, params=fitted(dialog.values()))],
                )

            self._open_operation_dialog(dialog, run_chosen)
            return
        # Ohne Parameter gibt es nichts zu fragen, und ein Fenster mit nur „OK"
        # wäre die Bestätigung vor einer rücknehmbaren Handlung, die Regel 19
        # verbietet. Entfernen, Vereinigen, Abziehen — alle laufen sofort, und
        # alle nimmt ein Undo zurück.
        run(values)

    # --- Fernsteuerung über MCP (Konzept P15 §7 Etappe 9, D19) ------------------

    def run_remote(self, name: str, arguments: Mapping[str, Any]) -> str:
        """Ein Fernaufruf, ausgeführt wie ein Menüklick.

        Derselbe Weg durch ``session.apply``, also dieselbe Transaktion,
        dieselbe Auswertung, dasselbe Undo. Was hier **nicht** steht, ist
        genauso wichtig: kein eigener Zugriff auf das Dokument, keine zweite
        Auswertung, kein Weg an der Prüfung vorbei.

        Der Herkunftsvermerk trägt ``mcp`` als Modell. Ein eigener Urheber
        neben „user" und „agent" wäre ehrlicher, kostete aber eine
        Formatänderung samt Migration — und für die Frage „habe ich das
        getan?" reicht der Vermerk, den der Verlauf ohnehin zeigt.

        Antwortet in Worten, nicht in Zahlen: am anderen Ende sitzt ein
        Modell, und ein Satz sagt ihm mehr als eine Objektkennung.
        """
        values = dict(arguments)
        if name == UNDO_TRANSACTION:
            self.session.undo()
            return tr("Zurückgenommen.")
        if name == READ_REPORT:
            return self._remote_report(str(values.get("severity", "")))
        if name in (ADD_PARAMETER, SET_PARAMETER):
            return self._remote_parameter(name, values)
        if name == ADD_FIT:
            return self._remote_fit(values)
        if name == FIND_PART:
            return find_part_text(str(values.get("description", "")))
        if name == READ_DIGEST:
            result = self.session.last_result
            if result is None:
                return tr("Es ist nichts geöffnet.")
            wanted = tuple(str(entry) for entry in values.get(OBJECTS_FIELD, ()) or ())
            return digest(result.scene, self.session.project.document, only=wanted or None)
        if name == READ_STANDARD:
            kind = str(values.get("kind", ""))
            if kind not in STANDARD_KINDS:
                return tr("Diese Tabelle gibt es nicht: {kinds}").format(
                    kinds=", ".join(STANDARD_KINDS)
                )
            return standard_text(kind, str(values.get("size", "")).strip())
        if name == READ_ANALYSIS:
            result = self.session.last_result
            if result is None:
                return tr("Es ist nichts geöffnet.")
            kind = str(values.get("kind", ""))
            if kind not in ANALYSIS_KINDS:
                return tr("Diese Analyse gibt es nicht: {kinds}").format(
                    kinds=", ".join(ANALYSIS_KINDS)
                )
            if kind == "orientation":
                # Der Fernaufruf läuft im Qt-Hauptthread (WindowBridge stellt
                # per postEvent zu), und die Orientierungssuche kostet dort
                # Sekunden ohne Fortschritt und ohne Abbrechen — gemessen
                # 5,3 s an der kleinen Referenzplatte. Bis sie einen Arbeiter
                # hat, wird sie hier abgelehnt; die drei anderen Analysen
                # bleiben unter 0,1 s (§2.8: darunter braucht es nichts).
                return tr(
                    "Die Orientierungssuche hielte das Fenster an — sie läuft "
                    "über den Chat oder den Dialog „Druckoptimal ausrichten“."
                )
            wanted = tuple(str(entry) for entry in values.get(OBJECTS_FIELD, ()) or ())
            return analysis_text(
                kind,
                result.scene,
                self.session.project.document,
                self.session.profile,
                objects=wanted,
            )
        if name == SET_PRINT_TARGET:
            printer = str(values.get("printer", "")).strip()
            material = str(values.get("material", "")).strip()
            document = self.session.project.document
            try:
                profiles.printer(printer or document.printer)
                profiles.material(material or document.material)
            except AppError as error:
                return f"{error.title} {error.detail or ''}".strip()
            changed = self.session.change_scene_profile(
                printer or document.printer,
                material or document.material,
                origin=Origin(by="agent", model=REMOTE_ORIGIN),
            )
            if not changed:
                return tr("Drucker und Material sind schon so eingestellt.")
            return f"{tr('Druckziel geändert')}: {document.printer} / {document.material}"

        spec = REGISTRY.get(name)
        chosen = [str(entry) for entry in values.pop(OBJECTS_FIELD, ()) or ()]
        result = self.session.last_result
        objects = list(result.scene.objects) if result else []
        if spec.consumes and len(chosen) < spec.consumes:
            return str(_needs_objects(spec.consumes))
        self.session.apply(
            spec.title,
            [OperationDraft(op=name, inputs=inputs_for(spec, objects, chosen), params=values)],
            origin=Origin(by="agent", model=REMOTE_ORIGIN),
        )
        self.session.wait_for_idle(REMOTE_WAIT_MS)
        return self._remote_state(spec)

    def _remote_state(self, spec: OperationSpec) -> str:
        """Was nach einem Fernaufruf dasteht — Objekte und Befunde.

        Ohne diese Rückmeldung müsste die Gegenstelle nach jedem Schritt
        nachfragen, was geschehen ist. Sie bekommt dieselbe Auskunft, die im
        Fenster im Objektbaum und im Prüfbericht steht.
        """
        result = self.session.last_result
        if result is None:
            return str(spec.title)
        names = ", ".join(f"{entry.id} ({entry.name})" for entry in result.scene.objects.values())
        warnings = [
            finding for finding in result.scene.report.findings if finding.severity != "info"
        ]
        lines = [f"{spec.title}: {tr('fertig')}.", f"{tr('Objekte')}: {names or tr('keine')}"]
        lines.extend(f"{finding.severity}: {finding.message}" for finding in warnings)
        return "\n".join(lines)

    def _remote_report(self, severity: str) -> str:
        """Der Prüfbericht von außen — dieselbe Funktion wie im Chat.

        Hier stand ein zweiter Filter, und er filterte anders: exakt statt
        „ab dieser Schwere", wie das Werkzeugschema es sagt. Auf ``warning``
        kamen keine Fehler — dieselbe Frage, zwei Antworten, je nachdem,
        woher sie kam (Konzept Agent-Vertiefung 2.4).
        """
        result = self.session.last_result
        if result is None:
            return tr("Es ist nichts geöffnet.")
        return report_text(result.scene, severity or None)

    def _remote_fit(self, values: Mapping[str, Any]) -> str:
        """Eine Passung von außen (§14).

        Wie im Chat, und seit der Konsolidierung (Konzept 2.4) wörtlich: den
        Fit baut ``build_fit``, dieselbe Funktion wie in der Sitzung. Ohne
        diesen Zweig lief der Aufruf in ``REGISTRY.get`` und endete als
        Programmfehler.
        """
        document = self.session.project.document
        try:
            fit = build_fit(dict(values), self.session.profile.material.id, len(document.fits))
        except ValueError as error:
            return str(error)
        if not self.session.add_fit(fit, origin=Origin(by="agent", model=REMOTE_ORIGIN)):
            return tr("Die Passung wurde nicht angelegt — den Grund zeigt das Fenster.")
        return f"{tr('Passung angelegt')}: {fit.name} ({fit.kind}, {fit.tolerance})"

    def _remote_parameter(self, tool: str, values: Mapping[str, Any]) -> str:
        """Ein Projektmaß von außen — dieselben Wege wie die Parameterleiste.

        Und damit dieselbe Zusage: die Änderung ist eine Transaktion, sie gilt
        als Änderung, und beim Schließen ist sie nicht weg. Den Wert prüft
        ``parse_number`` wie in der Sitzung — ``float()`` stand hier ungeprüft,
        und ein „abc" von außen war ein Programmfehler statt einer Meldung
        (Konzept 2.4).
        """
        name = str(values.get("name", ""))
        try:
            number = parse_number(values.get("value", 0.0))
        except ValueError as error:
            return str(error)
        remote = Origin(by="agent", model=REMOTE_ORIGIN)
        if tool == ADD_PARAMETER:
            made = self.session.add_parameter(
                Parameter(name=name, value=number, unit=str(values.get("unit", "mm"))),
                origin=remote,
            )
            if not made:
                return tr("Der Parameter wurde nicht angelegt — den Grund zeigt das Fenster.")
            return f"{tr('Parameter angelegt')}: {name} = {number}"
        if name not in self.session.project.document.parameters:
            return f"{tr('Diesen Parameter gibt es nicht')}: {name}"
        if not self.session.change_parameter(name, number, origin=remote):
            return tr("Der Wert ist schon so eingestellt.")
        return f"{tr('Parameter gesetzt')}: {name} = {number}"

    def _draw_sketch_in_space(self, op_id: int, op_name: str, dialog: QDialog, text: str) -> None:
        """Vom Dialog in den Zeichenmodus, für einen vorhandenen Schritt (Z9).

        **Der Dialog geht endgültig zu**, statt zu warten und später
        wiederzukommen: Ein modales Fenster, das sich schließt und nach einem
        Moduswechsel zurückkehrt, wäre eine Zustandsmaschine mehr, und die
        übrigen Feldwerte stehen ohnehin am Schritt und reisen von dort mit.
        „Fertig" im Modus öffnet denselben Dialog wieder — mit der neuen
        Zeichnung und ohne einen zweiten Schritt im Verlauf.

        Der Knopf sagt das vorher; sein Hinweis nennt beides, was er bringt
        und was er kostet.
        """
        dialog.reject()
        self.start_sketch(op_name, text=text, step=op_id)

    def edit_operation(
        self, op_id: int, field: str = "", given: Mapping[str, Any] | None = None
    ) -> None:
        """Eine Operation des Stapels wieder öffnen und ihr andere Zahlen
        geben (§15.4).

        Derselbe erzeugte Dialog, auf den Werten, die in der Datei stehen. Vor
        dem hier war der einzige Weg zu einer Bohrung zwei Millimeter weiter
        links, zurückzunehmen und neu zu bohren — und das ist ein Schritt zum
        Zurücknehmen, eine Position nicht.

        ``field`` setzt den Cursor gleich in das Feld, um das es geht. Wer über
        *Eingabe korrigieren* aus dem Prüfbericht kommt, hat dort einen Satz
        über **einen** Wert gelesen; der Kern nennt ihn im Befund, und ohne
        diesen Sprung müsste der Kunde ihn unter acht Zeilen wiederfinden.

        ``given`` überschreibt einzelne Werte, bevor der Dialog sie zeigt —
        für den Fall, dass eine **Geste** sie geändert hat und nicht die
        Tastatur. Der Skeletteditor ist der erste: Wer sein Skelett mit der
        Maus ändert, soll den Schritt ändern und keinen zweiten anlegen, der
        ein zweites Mal beugt.
        """
        try:
            entry = self.session.history.operation(op_id)
            spec = REGISTRY.get(entry.op)
        except AppError as error:
            self.session.failed.emit(error)
            return

        # Der Umschalter der Rechenkerne gehört auch hierher. Beim Anlegen gab
        # es ihn seit je, beim Nachbearbeiten nicht — und damit war ein
        # Quader, den jemand ohne ihn angelegt hatte, endgültig ein Netz. Sieben
        # Operationen blieben ihm für immer grau, und der einzige Weg dorthin
        # war, den Schritt zu löschen und alles darüber neu zu bauen.
        #
        # Gezeigt wird er an **beiden** Enden des Paars: Der Schritt kann schon
        # der exakte sein, und dann heißt Umschalten, den Haken wegzunehmen.
        shown = MENU_TWINS.get(spec.name, spec.name)
        hidden = next((name for name, partner in MENU_TWINS.items() if partner == shown), None)
        exact: QCheckBox | None = None
        if hidden is not None and hidden in TWIN_TOGGLES:
            label, hint = TWIN_TOGGLES[hidden]
            exact = QCheckBox(str(label), self)
            exact.setToolTip(
                self._twin_toggle_hint(str(hint), op_id, exact_now=spec.name == hidden)
            )
            exact.setStatusTip(exact.toolTip())
            exact.setAccessibleDescription(exact.toolTip())
            exact.setChecked(spec.name == hidden)

        def chosen_spec() -> OperationSpec:
            if exact is not None and hidden is not None:
                return REGISTRY.get(hidden if exact.isChecked() else shown)
            return spec

        def fitted(entered: Mapping[str, Any]) -> dict[str, Any]:
            allowed = {item.name for item in chosen_spec().params.spec()}
            return {key: value for key, value in entered.items() if key in allowed}

        dialog = OperationDialog(
            # Gebaut wird immer aus dem **sichtbaren** Zwilling, gleich welcher
            # von beiden gerade im Verlauf steht: Sein Schema trägt die Felder,
            # die der andere auch hat, und dazu die des Netzkerns. Aus dem
            # exakten heraus gäbe es kein ``anchor``, und wer den Haken
            # abwählte, bekäme einen Dialog ohne die Felder, die er gerade
            # freigeschaltet hat.
            REGISTRY.get(shown),
            self._object_names(),
            self,
            values={**entry.params, **(given or {})},
            sources=self._source_names(),
            parameter_values=self._parameter_values(),
            # Dieselbe Verengung wie beim Anlegen: Wer einen Schritt im Verlauf
            # korrigiert, soll dort dieselbe Auswahl vorfinden wie beim ersten
            # Mal — sonst hinge die Liste daran, wie man den Dialog geöffnet hat.
            features=self._feature_names(REGISTRY.get(shown)),
            extra=exact,
            surroundings=self._sketch_surroundings(),
            images=self._image_names(),
            pick_image=self._pick_image_source,
            pick_source=self._pick_model_source,
            slots=self._slots_of_selection(),
        )
        dialog.setWindowTitle(f"{spec.title} — {tr('Operation')} {op_id}")
        # **Der Weg in den Raum, und nur von hier aus** (Z9): Wer eine Skizze
        # aus dem Verlauf korrigiert, saß bisher vor einem weißen Blatt ohne
        # Ziehgriff, ohne Maßeingabe im Bild und ohne den Körper darunter —
        # dieselbe Operation, eine andere Umgebung, je nachdem ob man sie
        # anlegt oder ändert. Das Feld kennt seinen Schritt nicht; diese
        # Stelle kennt ihn, also verdrahtet sie ihn.
        # **Nicht ``field`` als Schleifenname** — so hieß er einen Commit lang,
        # und dieser Rumpf trägt bereits einen Parameter dieses Namens: den
        # Feldnamen, in den *Eingabe korrigieren* den Cursor setzt. Nach der
        # Schleife stand dort ein Widget, und ``dialog.focus_field(field)``
        # zwei Zeilen weiter bekam es statt einer Zeichenkette. Getroffen
        # hätte es genau die fünf Skizzen-Operationen, denn nur bei ihnen ist
        # die Schleife nicht leer.
        for sketch_field in dialog.findChildren(SketchField):
            sketch_field.offer_space(partial(self._draw_sketch_in_space, op_id, entry.op, dialog))
        if exact is not None:
            exact.toggled.connect(lambda: dialog.switch_variant(chosen_spec()))
            exact.toggled.connect(dialog.valuesChanged)
            dialog.switch_variant(chosen_spec())
        # Auch beim Korrigieren zeigt die Vorschau den Zweig, wie er würde —
        # gerechnet als geänderte Operation, nicht als neuer Schritt (§15.4).
        self._wire_preview(dialog, None, change_op=op_id)
        dialog.place_beside(self.viewport)

        def apply_change() -> None:
            picked = chosen_spec()
            values = fitted(dialog.values())
            if picked.name == entry.op:
                self.session.change_params(op_id, values)
                return
            self.session.change_kernel(op_id, picked.name, values)

        self._open_operation_dialog(dialog, apply_change)
        if field:
            # Nach dem Öffnen: ein Fokus in einem Fenster, das noch nicht
            # gezeigt wurde, ist keiner.
            dialog.focus_field(field)

    def _parameter_values(self) -> dict[str, float]:
        """Die aufgelösten Projektparameter — der Skizzeneditor rechnet
        Maßausdrücke damit (§13)."""
        from app.core import expressions

        try:
            return dict(expressions.resolve(self.session.project.document.parameters))
        except AppError:
            return {}

    def _open_operation_dialog(self, dialog: OperationDialog, on_accept: Any) -> None:
        """Öffnet einen Operationsdialog, ohne das Fenster zu sperren.

        Ein Operationsdialog trägt eine Live-Vorschau (§18.7), und eine
        Vorschau, die man nicht umdrehen kann, ist eine halbe: ``exec()``
        blockierte jede Kameraführung, solange der Dialog offen war. Wer sehen
        wollte, ob die Bohrung auf der Rückseite austritt, musste abbrechen,
        drehen und von vorn anfangen.

        Der Stapel wird ohnehin erst bei „Übernehmen" angefasst — die Sperre
        schützte nichts. Was sie verhinderte, war ein zweiter offener Dialog;
        das übernimmt jetzt diese Stelle, denn zwei Vorschauen um denselben
        Viewport wären eine Frage ohne Antwort.
        """
        previous = self._op_dialog
        if previous is not None:
            previous.reject()

        def finished(code: int) -> None:
            self._op_dialog = None
            # Zurück zur gestuften Auswahl: Ohne Dialog ist ein Klick wieder
            # eine Navigation und keine Antwort (§18.5).
            self.viewport.set_direct_picking(False)
            self._clear_preview()
            if code == QDialog.DialogCode.Accepted:
                on_accept()

        dialog.finished.connect(finished)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._op_dialog = dialog
        # Solange er offen ist, meint ein Klick das tiefste Ziel: Wer *Bohrung
        # vergrößern* offen hat und auf die Bohrung zeigt, antwortet auf eine
        # Frage und wählt nicht aus. Zwei Klicks für eine Antwort sähen aus wie
        # ein verschluckter erster.
        self.viewport.set_direct_picking(True)
        dialog.show()

    def _wire_preview(
        self, dialog: OperationDialog, drafts_of: Any, *, change_op: int | None = None
    ) -> None:
        """Verbindet einen Operationsdialog mit der Live-Vorschau (§18.7).

        Entprellt: dreißig Klicks auf den Drehknopf sind eine Rechnung, nicht
        dreißig. Die erste Vorschau läuft sofort — auch die Vorgaben sind eine
        Aussage darüber, was gleich passiert.
        """
        timer = QTimer(dialog)
        timer.setSingleShot(True)
        timer.setInterval(300)

        def request() -> None:
            entered = dialog.values()
            if change_op is not None:
                self.session.preview_async(
                    self._show_preview, change_op=change_op, change_values=entered
                )
            else:
                self.session.preview_async(self._show_preview, drafts_of(entered))

        timer.timeout.connect(request)
        dialog.valuesChanged.connect(lambda: timer.start())
        request()

    def _show_preview(self, difference: Any) -> None:
        """Die Live-Vorschau ins Bild — und dazu, ob sie vollständig ist.

        **Eine Vorschau, die stumm nichts zeigt, ist eine Rückmeldung, die
        fehlt.** Die schnelle Stufe der Booleschen Kette scheitert an groben
        Netzen aus dem Netz regelmäßig, während die Auswertung dieselbe
        Operation danach sauber rechnet; ``difference.compare`` vermerkt das
        seit je als ``difference.incomplete``, und der Vermerk kam bis zum
        03.09.2026 nirgends an. Gemessen an ``garden-hose-holder.3mf``
        (392 532 Dreiecke): Die Vorschau rechnete 3 579 mm³ abgetragenes
        Volumen, die Gegenrichtung nicht, und im Fenster stand dasselbe Band
        wie über einer vollständigen Vorschau. Wer den Durchmesser bewegt,
        kann dann nicht unterscheiden, ob er falsch zielt, ob es rechnet oder
        ob es nicht geht.

        Der Satz sagt, was gilt, und nennt den Ausweg, der ohnehin der nächste
        Schritt ist — das Ergebnis entsteht beim Übernehmen, und dort ist es
        richtig.
        """
        self.viewport.show_difference(difference)
        partial = any(
            finding.code == "difference.incomplete"
            for entry in getattr(difference, "entries", {}).values()
            for finding in entry.findings
        )
        self.viewport.mark_preview(
            tr("Vorschau unvollständig — beim Übernehmen wird genau gerechnet")
            if partial
            else tr("Vorschau — noch nicht übernommen"),
            tr("Leertaste halten: vorher"),
        )

    def _clear_preview(self) -> None:
        """Die Vorschau geht — Rechnung und Bild —, ein wartender
        Agentenvorschlag bekommt seine Differenz zurück.

        Geschrieben für den geschlossenen Dialog, gilt aber für jeden Weg, an
        dessen Ende keine Vorschau mehr stehen darf; :meth:`_drop_feature_preview`
        ruft sie ebenfalls.
        """
        self.session.cancel_preview()
        pending = self._proposal.difference if self._proposal is not None else None
        self.viewport.show_difference(pending)
        # Ein wartender Vorschlag ist auch noch nicht übernommen — nur sagt er
        # es anders: über ihn entscheidet der Chat, nicht ein Dialog.
        self.viewport.mark_preview(
            tr("Vorschlag — noch nicht übernommen") if pending is not None else "",
            tr("Leertaste halten: vorher") if pending is not None else "",
        )

    def _object_names(self) -> dict[str, str]:
        """Kennung auf Name, wie die Dialoge die Szene sehen.

        Der Baum zeigt Namen, das Dokument führt Kennungen — ein Aufklappmenü
        voller „obj_7" verlangt vom Nutzer, die Übersetzung selbst zu machen.
        """
        result = self.session.last_result
        if result is None:
            return {}
        return {object_id: str(entry.name) for object_id, entry in result.scene.objects.items()}

    def _source_names(self) -> dict[str, str]:
        """Kennung auf Dateiname, für die Quellenwähler (§16.3)."""
        return {
            source_id: Path(source.path).name or source_id
            for source_id, source in self.session.project.document.sources.items()
        }

    def _image_names(self) -> dict[str, str]:
        """Nur die Bildquellen — für das Feld „Bild" (§25, ``displace_image``)."""
        return {
            source_id: Path(source.path).name or source_id
            for source_id, source in self.session.project.document.sources.items()
            if source.kind == "image"
        }

    def _pick_image_source(self) -> tuple[str, str] | None:
        """Holt ein Bild von der Platte ins Projekt — der Rückruf des
        Bildwählers im Operationsdialog."""
        name, _filter = QFileDialog.getOpenFileName(self, tr("Bild wählen"), "", image_filter())
        if not name:
            return None
        path = Path(name)
        try:
            source_id = self.session.import_image(path)
        except AppError as error:
            show_error(error, self)
            return None
        return source_id, path.name

    def _pick_model_source(self) -> tuple[str, str] | None:
        """Holt eine Modelldatei von der Platte ins Projekt — der Rückruf des
        Quellenwählers im Operationsdialog.

        Zwilling von :meth:`_pick_image_source`, und er fehlte: Das Bildfeld
        hatte seinen Wähler seit je, das Quellenfeld nicht. Betroffen waren
        ausgerechnet die drei Einstiegsdialoge — *Modell laden*, *STEP laden*,
        *Zeichnung extrudieren*.
        """
        name, _filter = QFileDialog.getOpenFileName(self, tr("Datei wählen"), "", model_filter())
        if not name:
            return None
        path = Path(name)
        try:
            source_id = self.session.embed_model(path)
        except AppError as error:
            show_error(error, self)
            return None
        return source_id, path.name

    def _slots_of_selection(self) -> tuple[Any, ...]:
        """Die Materialslots des gewählten Körpers — für den Filamentwähler.

        Dieselbe Bauart wie :meth:`_feature_names` daneben und aus demselben
        Grund: Der Dialog fragt nicht die Szene, er bekommt, was zum gewählten
        Körper gehört. Damit beantwortet der Wähler die Frage, an der das
        alte Zahlenfeld gescheitert ist — *welche Farbe hat Slot 1?* —, ohne
        dass jemand erst malen muss.

        Ohne Auswahl bleibt die Liste leer: Dann zeigt der Wähler die Vorwahl
        und die freien Nummern, und das ist die ehrliche Auskunft.
        """
        result = self.session.last_result
        chosen = self.object_tree.selected()
        if result is None or chosen is None:
            return ()
        entry = result.scene.objects.get(chosen)
        return tuple(entry.material_slots) if entry is not None else ()

    def _feature_names(self, spec: OperationSpec | None = None) -> dict[str, str]:
        """Die Merkmale des gewählten Körpers, Kennung auf Beschriftung (§18.5).

        Dieselbe Beschriftung wie im Objektbaum und über dem Modell: „hole_1 ·
        Ø5,19 mm". Ohne Auswahl bleibt die Liste leer — welche Fläche gemeint
        ist, entscheidet der Körper, an dem gearbeitet wird.

        ``spec`` verengt die Liste auf die Merkmalsarten, mit denen diese
        Operation etwas anfangen kann (``applies_to``) — dieselbe Zuordnung,
        über die das Kontextmenü am Merkmal die Operation findet (§18.5, §10).

        **Ohne sie war die Auswahl eines Dialogs die aller Merkmale.** An einer
        eingelesenen STEP-Datei mit 302 erkannten Merkmalen bot *Bohrung
        ändern* 238 Flächen und 64 Verrundungen an und keine einzige Bohrung —
        es gab dort keine. Vorausgewählt war „Unterseite · 60 mm²", denn eine
        Pflicht-Auswahl trägt keinen Leereintrag und steht damit auf ihrem
        ersten Eintrag; das liest sich als Vorschlag der Anwendung und ist
        keiner. Auch wo passende Merkmale da sind, kostet die ungefilterte
        Liste das Suchen: der Motorhalter aus dem Kundenbestand hat 27
        Merkmale und darunter 6 Bohrungen.

        Ohne ``applies_to`` wird nicht gefiltert — dieselbe Haltung wie in
        :func:`labels.feature_requirement`: Raten wäre schlechter als Anbieten.
        Die übrigen Aufrufer (Legende der Analyseleiste, das Nachtragen eines
        angeklickten Merkmals) fragen ohne ``spec`` und bekommen alles.
        """
        result = self.session.last_result
        chosen = self.object_tree.selected()
        if result is None or chosen is None:
            return {}
        entry = result.scene.objects.get(chosen)
        if entry is None:
            return {}
        wanted = frozenset(spec.applies_to or ()) if spec is not None else frozenset()
        return {
            feature_id: feature_label(feature_id, feature)
            for feature_id, feature in entry.features.items()
            if not wanted or feature.kind in wanted
        }

    def _spacing_for(self, spec: OperationSpec) -> dict[str, Any]:
        """Der Abstand beim Anordnen kennt die Druckbetthaftung (§25, §29).

        Die Operation kann das nicht wissen: sie gehört dem Dokument, die
        Haftung ist eine Druckeinstellung, und beides bleibt getrennt. Das
        Fenster kennt beide Seiten — also belegt es hier vor.

        Zwei Körper mit fünf Millimetern Luft und je fünf Millimetern Brim
        stehen einander im Weg, und zwar erst auf der Platte: der Rand zählt
        zwischen Nachbarn zweimal. Beim Gewürzset war genau das die erste
        Deckelplatte. Vorbelegt, nicht erzwungen — im Dialog steht die Zahl und
        lässt sich ändern.
        """
        if "spacing" not in {entry.name for entry in spec.params.spec()}:
            return {}
        settings = self.session.project.document.print_settings
        if settings is None:
            settings = print_settings.resolve(self.session.profile)
        needed = 2.0 * adhesion_margin(settings)
        if needed <= 0.0:
            return {}
        default = next(
            (entry.default for entry in spec.params.spec() if entry.name == "spacing"), 0.0
        )
        return {"spacing": max(float(default or 0.0), needed)}

    def _from_selection(self, spec: OperationSpec, selected: ObjectId | None) -> dict[str, Any]:
        """Was das angeklickte Merkmal darüber sagt, wohin diese Operation
        gehört (§18.5).

        Ohne das war die Auswahl in Baum und Ansicht zum Ansehen da: der Dialog
        öffnete auf seinen Vorgaben, und wer eine Bohrung in der eben
        angeklickten Fläche wollte, las ihre Koordinaten von der Analysekarte ab
        und tippte sie ein.

        Ist nur der Körper gewählt und kein Merkmal darin, zählt seine oberste
        Fläche. Die Vorgabe war sonst der Ursprung, und ob der im Material
        liegt, ist Zufall: bei einem Teil, das auf dem Bett angeordnet ist,
        liegt er daneben, und die Bohrung trägt nichts ab.
        """
        result = self.session.last_result
        if selected is None or result is None:
            return {}
        entry = result.scene.objects.get(selected)
        if entry is None:
            return {}
        feature_id = self.object_tree.selected_feature()
        feature = entry.features.get(feature_id) if feature_id else None
        if feature is not None:
            return dict(values_for(spec, feature))
        return dict(values_for_object(spec, entry.features))

    # --- session replies --------------------------------------------------------

    def _on_scene(self, result: EvaluationResult) -> None:
        """Eine fertige Auswertung ins Fenster bringen — **nicht verschachtelt**.

        Der Aufbau unten schreibt in Objektbaum, Verlauf und Bericht. Läuft er
        ein zweites Mal, während der erste noch mittendrin ist, räumt
        ``show_document`` eine Liste, die gerade befüllt wird; unter Linux
        endete das im Segmentierungsfehler, unter Windows in einer Ansicht,
        die zwei Stände mischt.

        Verschachteln lässt es sich leicht: Jede Warteschleife mit
        ``processEvents`` — ``Session.wait_for_idle``, die Vorschau des
        Agenten, jeder Test, der auf eine Transaktion wartet — stellt
        Ereignisse zu, während dieser Slot arbeitet. Der zweite Anlauf wird
        deshalb gemerkt und **nach** dem ersten nachgeholt: das neueste
        Ergebnis gewinnt, keines geht verloren, und keine Liste wird zweimal
        gleichzeitig angefasst.
        """
        if self._showing_scene:
            self._pending_scene = result
            return
        self._showing_scene = True
        try:
            self._show_scene(result)
            while self._pending_scene is not None:
                pending, self._pending_scene = self._pending_scene, None
                self._show_scene(pending)
        finally:
            self._showing_scene = False
            self._pending_scene = None

    def _show_scene(self, result: EvaluationResult) -> None:
        # Neue Geometrie heißt: jede Karte und jeder Schnitt sind veraltet.
        self._map_cache.clear()
        self._slice_key = None
        # Auch der Arbeiter, der noch an der alten rechnet, wird abgelöst:
        # sein Schlüssel — Objekt und Dreieckszahl — überlebt eine
        # Verschiebung, sein Ergebnis nicht. Ließe man ihn stehen, reihte
        # sich der nächste Schieberzug bei ihm ein und bekäme die Schichten
        # der Geometrie von vorhin.
        self._slice_pending = None
        self._slice_waiters = []
        if self._slice_worker is not None:
            self._retire(self._slice_worker)
            self._slice_worker = None
        self.layer_bar.show_result(None)
        self.viewport.set_analysis_map(None, None)
        self.viewport.set_layer(None)
        self.analysis_bar.show_legend(None)
        # Ausgeblendetes, das die Szene nicht mehr enthält, wird vergessen —
        # sonst blendet eine wiederhergestellte Nummer später etwas aus, das
        # niemand versteckt hat.
        self._hidden &= set(result.scene.objects)
        self.viewport.set_hidden(self._hidden)
        self.object_tree.set_hidden(self._hidden)
        # **Und dasselbe für das Merkmalsfenster** — es war der Zwilling, den
        # die Zeile darüber nicht mitgenommen hat. Es zeigt die Handlungen
        # eines Merkmals, und nach dem Öffnen einer anderen Datei bezeichnet
        # dieselbe Kennung dort etwas anderes oder gar nichts; seine Knöpfe
        # zeigten auf ein Merkmal, das die Szene nicht mehr enthält.
        #
        # Geprüft und nicht pauschal geleert: Nach einem Übernehmen oder einem
        # Undo lebt dasselbe Merkmal weiter, und das Fenster soll dann
        # stehenbleiben.
        shown = self.feature_panel.feature_id
        if shown is not None and not any(
            shown in entry.features for entry in result.scene.objects.values()
        ):
            self.feature_panel.clear()
        # Eingepasst wird im Viewport (``_fit_once_for``), nicht hier: dort ist
        # die neue Szene schon gesetzt. Von hier aus lief es mit den Maßen der
        # *vorigen* — beim ersten Projekt also mit gar keinen, und dann passte
        # es auf den Bauraum ein statt auf das Teil.
        self._seen_objects = bool(result.scene.objects)
        self.object_tree.show_scene(result, self.session.project.document)
        effective_settings = self.effective_print_settings()
        self.filaments.show_scene(list(result.scene.objects.values()), effective_settings)
        plates = {entry.plate for entry in result.scene.objects.values()}
        # Der Plattenwähler sitzt in der Kopfzeile und nicht mehr in der
        # Explodier-Leiste: Wer eine einzelne Platte ansehen wollte, suchte ihn
        # unter einem Werkzeug, das Teile auseinanderzieht.
        self.header.show_plates(max(plates, default=0) + 1)
        self.tools.set_available("explode", self.explode_bar.show_for(len(result.scene.objects)))
        self.report.show_result(result, self.session.project.document)
        self._update_header()
        self.viewport.show_build_volume(self.session.profile)
        self.viewport.show_scene(result)
        self._reveal_split_result(result)
        self.section_bar.set_ranges(self.viewport.section_ranges())
        self.section_bar.show_capping_state(self.viewport.section_uncapped)
        self.history_panel.show_document(
            self.session.project.document, result.stopped_at, self.session.history.undone
        )
        self._update_actions()
        if result.stopped_at is not None:
            # §15.3: der letzte vollständige Zustand bleibt sichtbar, die
            # Statusleiste sagt warum. Und der Bericht kommt nach vorn, auch
            # wenn eine Tour läuft: die Meldung verweist auf ihn, und ein
            # Verweis auf etwas Zugehaltenes ist keiner.
            self.announce(tr("Die Kette hält an — siehe Prüfbericht."))
            self._halted = True
            self._focus_report(force=True)
        else:
            # **Ein Zustand gilt, solange er gilt.** Rechnet die Kette wieder
            # durch, ist die Absage von vorhin keine Auskunft mehr, sondern
            # eine falsche: Sie stand über einem Prüfbericht mit null Fehlern
            # und null Warnungen. Geräumt wird nur die eigene Meldung — was
            # der Kunde seither getan hat („Exportiert: dose.3mf"), bleibt.
            if self._halted:
                self._halted = False
                self.announce("")
            if self.report.worst_severity(result) in ("warning", "error"):
                self._focus_report()

    def _on_import_failed(self, error: AppError) -> None:
        """Was der ``except``-Zweig von ``open_path`` getan hat, nur später.

        Der Weg über das Signal ist nötig, weil der Plan im Arbeiter entsteht:
        Wer dort scheitert, kann nicht in einen Aufrufer werfen, der längst
        zurückgekehrt ist. Gezeigt wird dasselbe wie vorher — der Fehlerdialog
        mit seinen Handlungen, und die Statuszeile zurück auf das, was vor dem
        Ladehinweis dastand.
        """
        # **Erst den Wartezeiger, dann den Dialog.** Unterhalb von
        # ``PLAN_IN_WORKER_ABOVE`` läuft der Einleseweg gerade durch, und
        # dieser Slot steht damit noch **im** ``with waiting()`` des
        # Aufrufers. Ein Fehlerdialog unter dem Wartezeiger ist genau das
        # Fenster, das zugleich fragt und bittet zu warten — dagegen gibt es
        # seit dem 29.08.2026 einen Test. Über der Schwelle steht hier
        # ohnehin keiner, und ``restoreOverrideCursor`` auf einem leeren
        # Stapel tut nichts.
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self.status_message.setText(self._announcement)
        show_error(error, self)

    def _on_import_finished(self, accepted: bool) -> None:
        """Der Stapel steht; die Auswertung läuft danach von selbst.

        Der Startbildschirm weicht erst hier — vorher wäre er einer leeren
        Szene gewichen, und der Kunde sähe vierzehn Sekunden lang nichts.
        """
        geladen, self._pending_download = self._pending_download, ""
        if accepted:
            self._show_start_screen(False)
            if geladen:
                self.announce(f"{tr('Geladen')}: {geladen}")
        else:
            self.status_message.setText(self._announcement)

    def _on_project(self) -> None:
        # Eine gezeichnete Trennlinie liegt auf einem Körper, den es nach einer
        # Änderung am Dokument so nicht mehr geben muss — ein neues Projekt,
        # ein Undo, eine Operation von woanders. Sie stehen zu lassen hieße,
        # auf zwei Punkte im Leeren zu zeigen; und das Ziel der Linie wäre nach
        # dem Öffnen einer anderen Datei eine Kennung, die dort etwas anderes
        # bezeichnet.
        if self._split_points:
            self._clear_split_line()
        # **Und aus demselben Grund die Vorschau des Merkmalsfensters.** Sie
        # zeigt eine Änderung an einer Geometrie, die es nach einem Undo, einem
        # gelöschten Verlaufsschritt oder einer Operation von woanders so nicht
        # mehr gibt.
        #
        # Gemessen war dieser Weg sauber — aber nur mittelbar: Der neu gebaute
        # Objektbaum meldete eine geänderte Auswahl, und *die* räumte ab. Eine
        # Verteidigung, die über die Auswahl eines anderen Bedienelements läuft,
        # hält nur so lange, wie dieses Element sich so verhält. Hier kommt
        # jeder Dokumentwechsel durch (Vorschlag 3d-druck-85, 03.09.2026).
        #
        # Eine laufende Vorschau kann das nicht treffen: Sie ändert das
        # Dokument nicht und löst ``projectChanged`` deshalb nicht aus.
        self._drop_feature_preview()
        document = self.session.project.document
        produced = frozenset(output for operation in document.ops for output in operation.outputs)
        if self._pending_split_reveal and not self._pending_split_reveal.issubset(produced):
            self._pending_split_reveal = frozenset()
        # Wer auf dem Startbildschirm etwas ins Dokument bringt — Einfügen,
        # Generieren, ein Baustein aus dem Katalog —, will es auch sehen. Von
        # acht Wegen wechselten sieben einzeln von Hand, und der achte war der
        # Schlussknopf der Erstinbetriebnahme: Modell geladen, Startbildschirm
        # stand. Der Wechsel am Dokument selbst macht die vergessene Stelle
        # unmöglich.
        if document.ops and self.stack.currentWidget() is self.start_screen:
            self._show_start_screen(False)
        self.parameters.show_document(document)
        # **Mit der Halt-Marke**, und die fehlte hier. ``_show_scene`` reicht
        # ``result.stopped_at`` weiter, dieser Weg nicht — und ``save_project``
        # meldet einen Dokumentwechsel **ohne** nachfolgende Auswertung. Ein
        # Strg+S löschte damit das Ausrufezeichen vor dem Schritt, an dem die
        # Kette hängt, während Statuszeile und Prüfbericht weiter „Die Kette
        # hält an" sagten (§15.3; gefunden von 3d-druck-85, 03.09.2026).
        result = self.session.last_result
        self.history_panel.show_document(
            document,
            result.stopped_at if result is not None else None,
            self.session.history.undone,
        )
        self.chat.show_document(document)
        self._refresh_applied_bar()
        self.setWindowTitle(f"{self.session.title} — {APP_NAME}")
        self._update_header()
        self._update_actions()

    def _refresh_applied_bar(self) -> None:
        """Die Übernommen-Leiste hängt am Dokument, nicht an der Zeit (§26.5).

        Sobald ihre Transaktion nicht mehr die oberste ist — ein Strg+Z, ein
        Menüklick danach, ein Projektwechsel —, hat der Rückgängig-Knopf sein
        Versprechen verloren und die Leiste verschwindet. Ohne das überlebte
        sie sogar ein neues Projekt und nahm auf Klick fremde Arbeit zurück.
        """
        if self._applied_transaction is None:
            return
        transactions = self.session.project.document.transactions
        if not transactions or transactions[-1].id != self._applied_transaction:
            self._applied_transaction = None
            self.chat.show_proposal(None)

    def _update_header(self) -> None:
        """Was oben rechts steht, kommt aus Dokument und Profil.

        An beiden Stellen aufgerufen, an denen sich etwas davon ändert: das
        Profil hängt am Dokument (Drucker und Material stehen darin), das
        Außenmaß am Ergebnis der Auswertung.

        Die Anzeigeeinheit kommt aus dem **Zustand** und nicht aus den
        Einstellungen. Beides wäre dasselbe, solange nur ``_apply_settings``
        sie setzt — und genau darauf hatte sich das verlassen: Ein Aufruf von
        ``set_display_unit`` mit einer anderen Einheit als der gespeicherten
        schrieb hier weiter die gespeicherte. Zwei Quellen für eine Angabe, und
        die eine war die Persistenz und nicht die Wahrheit.
        """
        self.header.show_project(
            self.session.title,
            self.session.last_result,
            display_unit(),
        )
        self.header.show_profile(self.session.profile)
        self._update_facts()

    def effective_print_settings(self) -> Any:
        """Die Druckeinstellungen, die für dieses Projekt wirklich gelten.

        **Zuerst die des Dokuments**, denn wer sie im Dialog gesetzt hat, meint
        sie; sonst die aufgelöste Vorgabe aus Profil und gewählter Stufe. Die
        Stufe darf nicht fehlen: ``resolve(profile)`` allein nimmt die
        Standardstufe, und an einem Quader von 40 auf 30 auf 20 mm auf „fein" stand damit
        13 g · 49 min in der Zahlenzeile, während es 14,1 g · 116 min sind —
        Faktor 2,4 auf der Dauer, und die Zeile bewegte sich beim Umstellen
        nicht (gemessen von 3d-druck-85, 03.09.2026).

        Als eigene Stelle, weil derselbe Ausdruck an vier weiteren stand und
        ``_update_facts`` als fünfte davon abwich. Ein sechster Ort kann jetzt
        nicht mehr anders rechnen.
        """
        quality = cast(
            QualityPreset,
            self.settings.print_quality
            if self.settings.print_quality in print_settings.quality_presets()
            else print_settings.DEFAULT_QUALITY,
        )
        document = self.session.project.document
        return document.print_settings or print_settings.resolve(self.session.profile, quality)

    def _update_facts(self) -> None:
        """Material und Dauer aus dem, was ohnehin vorliegt.

        Volumen und Oberfläche bringt jedes ausgewertete Netz mit; die
        Schätzung darauf kostet nichts und darf deshalb nach jeder Auswertung
        laufen (§31). Eine Schichtanalyse dürfte das nicht — sie braucht
        Sekunden, und die Zeile stünde nach jedem gezogenen Parameter still.

        Gerechnet wird mit :meth:`effective_print_settings` — die Zeile führt
        eine Zahl, die der Kunde liest, und sie muss dieselbe Grundlage haben
        wie der Dialog, in den sie per Klick führt.
        """
        result = self.session.last_result
        if result is None or not result.scene.objects:
            self.facts.show_estimate(None)
            return
        bodies = [(entry.mesh.volume, entry.mesh.area) for entry in result.scene.objects.values()]
        self.facts.show_estimate(estimate_total(bodies, self.effective_print_settings()))

    def _facts_key(self) -> str:
        """Woran die Zahlenzeile ein Projekt wiedererkennt.

        Der Pfad und nicht ``session.title``: der trägt einen Stern, sobald
        etwas ungesichert ist, und wechselt damit bei der ersten Änderung. Die
        Zeile hätte ihren Vergleich genau dann verloren, wenn er zum ersten Mal
        etwas zu sagen hätte.
        """
        path = self.session.path
        return str(path) if path else ""

    def announce(self, text: str) -> None:
        """Eine Meldung, die einen Lauf überlebt (§2.8).

        Die Statuszeile trug zweierlei und behandelte es gleich: den
        Fortschrittstext eines Laufs, der mit ihm verschwinden soll, und das
        Ergebnis einer Handlung, das stehenbleiben muss. Weil das Ende jedes
        Laufs die Zeile leerte, gewann immer der Lauf.

        Am deutlichsten beim automatischen Teilen: „Geteilt: 2 · 2 Passungen"
        stand nie da. ``_split_done`` schrieb es, und das ``busy``-Signal
        desselben Arbeiters löschte es unmittelbar danach — die einzige
        Auskunft darüber, wie viele Teile und wie viele Passungen entstanden
        sind, hat nie jemand gesehen. Ein Export direkt nach einer Änderung
        verlor seine Bestätigung an die nachlaufende Auswertung.

        Gemerkt wird deshalb, was zuletzt zu *sagen* war; die Laufanzeige legt
        sich nur darüber und gibt sie danach wieder frei.
        """
        self._announcement = text
        if self._active_progress_owner() is None:
            self.status_message.setText(text)
        else:
            self._render_progress_state()

    def _on_progress(self, fraction: float, text: str) -> None:
        self.veil.step(fraction, text)
        if not text:
            # Ein leerer Text heißt, der Lauf ist vorbei; dann kommt zurück,
            # was zuletzt zu sagen war (§2.8).
            self._run_started = None
            self._set_progress_state(
                "evaluation",
                text=self._announcement,
                value=int(fraction * 100),
            )
            return
        if self._run_started is None:
            self._run_started = time.monotonic()
        # **Über zehn Sekunden zusätzlich eine Schätzung** — die Zeile aus der
        # Wartezeit-Tabelle galt bisher für genau den Fall nicht, für den sie
        # geschrieben ist. Sie hing am Ladeschleier, und den gibt es nur bei
        # leerem Bild; bei jeder langen Rechnung an einem geladenen Modell
        # stand hier Prozent ohne jede Zeitangabe.
        left_over = remaining_time(self._run_started, fraction)
        # Der Prozentwert steht hier und nicht im Balken: dort wanderte der Rand
        # der Füllung unter der Zahl hindurch, und ab 60 % war sie mit 1,69
        # Kontrast auf Bernstein nicht mehr zu lesen. Hier hat sie einen ruhigen
        # Grund — und steht neben dem Schritt, den sie meint.
        parts = [text, f"{round(fraction * 100)} %"]
        if left_over:
            parts.append(left_over)
        display = "  ·  ".join(parts)
        self._set_progress_state(
            "evaluation",
            text=display,
            minimum=0,
            maximum=100,
            value=int(fraction * 100),
            accessible_description=display,
        )

    def _show_wait_cursor(self) -> None:
        """Stufe zwei: der Zeiger sagt, dass gerechnet wird (§2.8).

        ``BusyCursor`` und nicht ``WaitCursor``: Das ist der Zeiger *mit*
        Sanduhr daneben, und er ist der einzige, der die Wahrheit sagt. Die
        Rechnung läuft in einem Arbeiter, die Oberfläche bleibt bedienbar —
        genau das verlangt §2.8 —, und ein reiner Wartezeiger behauptete das
        Gegenteil.
        """
        # **Am Fenster und nicht an der Anwendung**, und das ist keine Feinheit.
        # ``setOverrideCursor`` führt einen **Stapel**, und
        # ``restoreOverrideCursor`` nimmt blind das oberste Element — nicht das
        # eigene. Beim Einlesen einer Datei laufen zwei Zeiger nebeneinander:
        # ``waiting()`` setzt den reinen Wartezeiger für die synchrone Rechnung
        # (dort ist er richtig, der Hauptthread rechnet), und dieser hier gilt
        # dem asynchronen Lauf. Wer beide über den Override legt, räumt beim
        # Aufräumen den fremden weg und lässt den eigenen darunter stehen — der
        # Kunde sah dann die falsche von zwei Aussagen, und acht Tests, die mit
        # Wartezeit nichts zu tun haben, wurden rot.
        #
        # Als Widget-Eigenschaft gibt es keinen Stapel: Ein Override liegt
        # darüber, solange er gilt, und darunter kommt dieser wieder hervor.
        # Das ist auch die ehrlichere Aussage — der Zeiger gilt diesem Fenster,
        # und die Oberfläche bleibt bedienbar.
        if self._waits and not self._waiting:
            self.setCursor(Qt.CursorShape.BusyCursor)
            self._waiting = True
            self._render_progress_state()

    def _show_progress_bar(self) -> None:
        """Stufe drei: ab zwei Sekunden will man wissen, wie weit es ist.

        Gefragt wird ``_waits``, nicht ``_anything_running()``: Der Zeitgeber
        gehört dem Lauf, der ihn gestartet hat, und der Zustand der Sitzung
        kann sich zwischen Start und Feuern geändert haben. Endet der Lauf
        vorher, stoppt ``_stop_waiting`` den Zeitgeber, und er feuert gar
        nicht — das ist die Zusage, nicht eine zweite Abfrage.
        """
        if self._waits:
            self._render_progress_state(force_visible=True)

    def _stop_waiting(self) -> None:
        """Alle Stufen zurück — Zeitgeber, Zeiger, Balken, Knopf.

        Der Zeiger ist eine Eigenschaft dieses Fensters und kein Override der
        Anwendung — der Grund steht bei :meth:`_show_wait_cursor`. Die Flagge
        bleibt trotzdem: ``unsetCursor`` auf einem Fenster, das nie einen
        gesetzt hat, ist zwar folgenlos, aber die Flagge sagt auch, ob die
        Stufe überhaupt erreicht wurde.
        """
        self._patience.stop()
        self._bar_delay.stop()
        if self._waiting:
            self.unsetCursor()
            self._waiting = False

    def _on_busy(self, busy: bool) -> None:
        self._set_progress_state(
            "evaluation",
            active=busy,
            minimum=0,
            maximum=100,
            value=0 if busy else self._progress_states["evaluation"].value,
            accessible_description=tr("Zeigt den Fortschritt der laufenden Aufgabe."),
            cancel_enabled=True,
        )
        self._update_waiting_state()
        self._update_veil(busy)

    def _update_waiting_state(self) -> None:
        """Führt die gestufte Warteanzeige für den gewählten Besitzer nach."""

        running = self._active_progress_owner() is not None or self._anything_running()
        # **Gestuft und nicht sofort** (§2.8). Die Zeitgeber und ihre Zahlen
        # sind bei ihrer Anlage begründet; hier steht nur, wann sie laufen.
        # Ein Lauf, der noch aussteht, startet sie nicht neu — sonst schöbe
        # jede Zwischenmeldung eines nebenher laufenden Exports den Balken
        # wieder zwei Sekunden nach hinten.
        self._waits = running
        if running:
            if not self._patience.isActive() and not self._waiting:
                self._patience.start()
            if not self._bar_delay.isActive() and not self.progress.isVisibleTo(self):
                self._bar_delay.start()
        else:
            self._stop_waiting()
        self._render_progress_state()
        if not running:
            self.status_message.setText(self._announcement)

    def _on_evaluation_cancelled(self) -> None:
        """Sagen, dass angehalten wurde — und was jetzt gilt.

        Ohne diesen Satz sah ein abgebrochener Lauf genauso aus wie ein
        fertiger: Balken weg, Knopf weg, dieselbe Ansicht wie vorher. Der Satz
        nennt deshalb beides, das Aufhören **und** den Stand, den man vor sich
        hat — sonst bleibt die Frage offen, ob das Bild das Ergebnis ist.

        Er geht in ``_announcement``, nicht nur in die Zeile: Das nächste
        ``_on_busy`` schreibt die Ansage zurück, und ein Satz, der beim
        nächsten Ereignis verschwindet, war für den, der gerade woanders
        hinsah, nie da.
        """
        self._announcement = tr(
            "Abgebrochen. Zu sehen ist der letzte vollständig gerechnete Stand — "
            "eine Änderung am Stapel rechnet weiter."
        )
        self.status_message.setText(self._announcement)

    def _update_veil(self, busy: bool) -> None:
        """Die Ladeanzeige gilt dem leeren Bild, nicht jeder Rechnung.

        Steht ein Körper da, bleibt er stehen (§15.3, §2.8): dann sagen Balken
        und Statuszeile, dass gerechnet wird, und die Ansicht bleibt die
        Ansicht. Etwas darüberzulegen, das man ohnehin gerade ansieht, wäre
        eine Verschlechterung.

        Verdeckt wird nur, wo nichts zu verdecken ist — beim Öffnen eines
        Projekts, beim Wiederherstellen einer Sicherung und beim ersten Lauf
        eines neuen Dokuments. Die Verzögerung in ``LoadingVeil`` sorgt dafür,
        dass der letzte Fall nichts aufblitzen lässt.
        """
        result = self.session.last_result
        if not busy or (result is not None and result.scene.objects):
            self.veil.end()
            return
        # Ein Projekt ohne Ergebnis wird geladen; eines mit leerem Ergebnis
        # rechnet an etwas, das noch keinen Körper hat. Beim Laden eines
        # Projekts **mit** Schritten kommt die Anzeige sofort: die Wartezeit
        # ist dort sicher, und jede unbedeckte Millisekunde zeigt das nie
        # gerenderte native Ansichtsfenster (loading.py, ``appeared``). Die
        # Verzögerung bleibt dem leeren Dokument, dessen Lauf in
        # Millisekunden fertig ist.
        self.veil.begin(
            tr("Projekt wird geladen …") if result is None else tr("Wird berechnet …"),
            at_once=result is None and bool(self.session.project.document.ops),
        )

    def _on_veil_appeared(self) -> None:
        """Die Ansicht ist weg, solange der Schleier steht — nicht nur verdeckt.

        Das Ansichtsfenster ist ein natives Fenster (VTK) und läge auf dem
        Bildschirm über dem gemalten Schleier; solange es nie gerendert hat,
        zeigt es alte Pixel. Verborgen ist es kein Fenster, und der Schleier
        gewinnt. Der Wechsel zurück läuft über ``ended`` — denselben Weg, den
        auch der Seitenwechsel des ``middle_stack`` täglich geht.
        """
        self.middle_stack.setVisible(False)

    def _on_veil_ended(self) -> None:
        """Der Schleier ist weg — die Ansicht kommt zurück.

        Erst jetzt wird das native Fenster erzeugt und gerendert; die Szene
        steht zu diesem Zeitpunkt bereits, das erste Bild ist also das
        fertige Modell und nicht Schwarz.
        """
        self.middle_stack.setVisible(True)

    def _on_ask(self, request: AskRequest) -> None:
        """Der Arbeiter wartet, solange dieser Dialog offen ist (§21.3).

        **Und die Kandidaten stehen dabei hervorgehoben in der Ansicht.** Der
        Bauplan verlangt es wörtlich, gebaut war es bis zum 03.09.2026 nicht:
        Wer eine Projektdatei öffnete, deren Verweis mehrdeutig geworden war,
        bekam ``hole_1``, ``hole_2``, ``hole_3`` zur Wahl und sollte zwischen
        Bohrungen entscheiden, die er nicht sieht. Die Auskunft lag im Kern
        bereit (``orphans.candidates_of``) und wurde nie abgerufen.

        Die markierte Zeile wandert mit: Was gleich die Antwort wäre, leuchtet
        deckender als die übrigen. Steht dieselbe Kennung an mehreren Körpern
        — der Fall der Skizzenebene, die auf jeder Fläche zu Hause sein darf —,
        wird keine betont, denn die Frage entscheidet dort über die Kennung
        und nicht über den Fundort.
        """
        dialog = AskDialog(request.question, request.choices, self)
        self._ask_candidates = tuple(request.candidates)
        if self._ask_candidates:
            self.viewport.show_candidates(self._ask_candidates)
            dialog.list.currentItemChanged.connect(weak_slot(self, MainWindow._emphasise_candidate))
            self._emphasise_candidate(dialog.list.currentItem(), None)
        try:
            if dialog.exec() == AskDialog.DialogCode.Accepted:
                request.reply(dialog.chosen())
            else:
                request.reply(None)
        finally:
            # Auch bei Abbruch und auch, wenn der Dialog wirft: Was ohne offene
            # Frage leuchtet, leuchtet ohne Anlass. Der Kern nimmt seine Ansage
            # ebenfalls zurück, aber die erreicht nur die nächste Frage — das
            # Bild gehört dem Fenster.
            if self._ask_candidates:
                self.viewport.show_candidates()
                self._ask_candidates = ()

    def _emphasise_candidate(self, current: object, _previous: object) -> None:
        """Die markierte Zeile bekommt die deckendere Hervorhebung.

        Zwei Argumente, weil ``currentItemChanged`` zwei sendet: Qt verbindet,
        was von der Stelligkeit passt, und ein Slot mit einem Argument bekäme
        hier stillschweigend das falsche.
        """
        chosen = ""
        if isinstance(current, QListWidgetItem):
            chosen = str(current.data(Qt.ItemDataRole.UserRole) or "")
        matching = [pair for pair in self._ask_candidates if pair[1] == chosen]
        self.viewport.show_candidates(
            self._ask_candidates, matching[0] if len(matching) == 1 else None
        )

    def _on_error(self, error: AppError) -> None:
        """§33.1: ein Fehler des Nutzers sieht anders aus als ein Fehler im
        Programm.
        """
        if isinstance(error, InternalError):
            self.report_error(error)
            return
        result = self.session.last_result
        offers_repair = any(action.id == REPAIR_AND_RETRY.id for action in error.suggestions)
        if offers_repair and not repair_is_available(
            self.session.project.document,
            stopped_at=result.stopped_at if result is not None else None,
            op_id=error.op_id,
            object_id=error.object_id,
            live_objects=frozenset(result.scene.objects) if result is not None else None,
        ):
            # Der Dialog darf keinen Knopf zeigen, dessen Handler anschließend
            # ohne Ziel zurückkehrt. Die ursprüngliche Ausnahme bleibt für
            # Protokoll und Bericht unverändert; nur ihre Dialogfassung verliert
            # den nicht ausführbaren Vorschlag.
            error = copy(error)
            error.suggestions = tuple(
                action for action in error.suggestions if action.id != REPAIR_AND_RETRY.id
            )
        show_error(error, self)

    def error_handlers(self) -> dict[str, Any]:
        """Was hinter den Knöpfen eines Fehlerdialogs steckt (§2.7, Regel 17).

        Der Kern schlägt Handlungen vor, die Oberfläche führt sie aus — das
        war der fehlende Draht. Was hier nicht steht, wird auch nicht
        angeboten; ein Knopf, der nichts tut, ist schlimmer als keiner.

        Nicht dabei und bewusst: ``use_voxel_stage`` (die Stufe ist kein
        Parameter, den ein Dialog setzen könnte), ``choose`` (der Kern fragt
        dafür über ``ctx.ask``, bevor er wirft) und ``choose_printer`` — das
        kommt mit dem Einstellungsdialog.
        """
        return {
            "report_error": lambda error: self.report_error(error),
            "show_details": lambda error: show_details(error, self),
            "show_locations": self._show_error_location,
            # Die Rücknahme-Warnung des Agenten zeigt in den Verlauf — dort
            # stehen die Transaktionen, die eine Annahme mitnähme (H-1).
            "show_history": lambda _error: self._flash_area("history"),
            # **Ein Rat, den nur der Kunde ausführen kann, ist ein halber.**
            # „Die Teilung läuft schon" schlägt vor, sie abzubrechen, und die
            # Handlung gibt es (``Session.cancel_split`` hält an *und*
            # verwirft). Ohne Draht wurde daraus über ``unhandled_advice`` ein
            # Satz zum Lesen — richtig gegenüber einem Knopf ohne Wirkung, aber
            # eben nur die Notlösung für Kennungen, die niemand einlösen kann.
            "cancel_split": lambda _error: self.session.cancel_split(),
            "repair_and_retry": self._repair_after_error,
            "remove_small_parts": self._remove_small_parts,
            "split_model": self._split_after_error,
            "split_along_line": lambda _error: self.tools.activate("split"),
            "scale_to_fit": self._scale_after_error,
            "export_as_mesh": self._export_as_mesh_after_error,
            "place_on_bed": self._place_on_bed_after_error,
            "arrange_on_bed": self._arrange_after_error,
            "correct_input": self._correct_after_error,
            "show_step_values": self._show_step_values,
            # **Die Absage beim Einlesen hatte nur „Abbrechen".** Eine
            # kaputte Datei lässt sich nicht korrigieren, und der Schritt,
            # den ``correct_input`` öffnen würde, entsteht gar nicht erst.
            # Was bleibt, ist eine andere Datei — ``action_import``, nicht
            # ``action_open``: Einfügen ersetzt kein offenes Projekt.
            "choose_another_file": lambda _error: self.action_import(),
            # Die andere Hälfte davon: Wo nicht ein Wert, sondern die
            # Auswahl nicht geht, hilft kein Dialog (§15.4).
            "change_selection": self._change_selection_after_error,
            # **Die dritte Bauraum-Handlung.** Teilen und Verkleinern wurden
            # nachgezogen, als der Prüfbericht seine Handlungen bekam; „anderes
            # Druckerprofil" blieb liegen, weil ihr Weg fehlte — der Drucker
            # eines offenen Projekts wird in den Druckeinstellungen gewechselt
            # (``_scene_profile_changed``) und nicht in den Anwendungs-
            # einstellungen, wo nur die Vorgabe für neue Projekte steht. Wer
            # einen größeren Drucker hat, ist damit einen Klick entfernt statt
            # gezwungen, sein Teil zu verkleinern.
            "choose_printer": lambda _error: self.action_print_settings(),
            # **Derselbe Weg, dieselbe Lücke, eine Zeile weiter.** Scheitert
            # der Slicer-Lauf, schlägt die Absage vor, einen anderen zu
            # wählen — und auch dieser Rat hatte keinen Draht. Auf einem
            # Rechner mit drei installierten Slicern ist das eine Sackgasse
            # nach §2.1, während zwei arbeitende danebenliegen.
            #
            # **Am Fenster und nicht am Dialog**, weil der Fehler auch ohne
            # offenen Druckdialog auftritt (``handover.py``, der
            # ``detect``-Fall). Am Dialog hinge der Knopf genau dort nicht, wo
            # man ihn am nötigsten braucht. Gemessen von 3d-druck-55 an den
            # echten Handlern.
            "choose_slicer": lambda _error: self.action_print_settings(),
            # **Und die zwei, die der Druckdialog besser kann — hier trotzdem.**
            # Beide hängen auch am Dialog (``print_settings_dialog.py``), wo
            # ``show_output`` die Slicer-Ausgabe in ein aufklappbares Textfeld
            # legt statt in eine Zeile: Achthundert Zeichen Protokoll als
            # ``value_line`` liest niemand. Der Wächter sieht den Dialog aber
            # nicht — er liest ``error_handlers`` des Fensters —, und wichtiger
            # als das ist: Der Fehler tritt auch **ohne** offenen Dialog auf.
            #
            # ``show_details`` ist dafür kein Notbehelf, sondern der zweitbeste
            # Ort: Es zeigt ``error.values`` vollständig, und die Ausgabe des
            # Slicers liegt genau dort (``values["output"]``, an allen vier
            # Stellen gesetzt). Derselbe Inhalt, nur weniger gut gesetzt.
            # ``check_profile`` ist wörtlich dieselbe Handlung wie
            # ``choose_printer``: Das Profil wechselt man in den
            # Druckeinstellungen. Befunde und Fassungen von 3d-druck-fb.
            "show_output": lambda error: show_details(error, self),
            "check_profile": lambda _error: self.action_print_settings(),
            # **Zwei verschenkte Klickwege, gefunden beim Release-Durchgang.**
            # Beide standen als Satz da — ehrlich, aber an diesen Stellen zu
            # wenig: Der naheliegendste Rat soll ein Knopf sein, wo die
            # Anwendung ihn einlösen kann.
            #
            # *Dreiecke verringern* ist der Hauptvorschlag zu „Für eine
            # Analysekarte ist dieses Modell zu groß", und die Operation
            # gleichen Namens liegt im Register — der Weg dorthin ist der
            # Dialog, den jede Operation bekommt.
            "decimate_mesh": lambda _error: self.run_operation(REGISTRY.get("decimate_mesh")),
            # Und die Adresse reist im Fehler mit (``values["url"]``): Der
            # Knopf öffnet **sie**, nicht die Produktseite. ``open_website``
            # wäre hier falsch — der Kunde wollte zu *seiner* Datei.
            "open_in_browser": lambda error: self._open_error_url(error),
            # **Sechsmal angeboten, nie ausgeführt.** Wenn der Slicer fehlt,
            # abbricht oder seine Kommandozeile unbekannt ist, schlägt die
            # Übergabe vor, nur zu exportieren und selbst zu slicen — an sechs
            # Stellen. Einen Draht hatte der Rat nie: Er wurde inline als
            # ``Action(id="export_only", …)`` gebaut, und ``test_every_offered_
            # error_action_does_something`` sieht nur die Konstanten aus
            # ``errors``. Aufgefallen ist es erst, als die sechs zu
            # ``EXPORT_ONLY`` zusammengelegt wurden — der Wächter stand die
            # ganze Zeit daneben und konnte nicht hinsehen.
            # ``action_export`` ist genau die Antwort: Es schreibt die Körper
            # als Datei, ohne einen Slicer zu brauchen (§29).
            "export_only": lambda _error: self.action_export(),
            # Eine Projektdatei aus einer neueren Version sagt „Ein Update
            # öffnet sie" — und der Weg dorthin steht im Hilfe-Menü.
            "check_updates": lambda _error: self.action_check_updates(),
            # Und wenn das Paket nicht kommt oder sich nicht starten lässt,
            # bleibt der Weg, den es vor dem Update in der Anwendung als
            # einzigen gab (§37.2).
            "open_download_page": lambda _error: open_website(),
            # **Der Rat, der die ganze Zeit ins Leere zeigte.** Im Fenster läuft
            # die kurze Rückfallkette (§31); *Voxelstufe erzwingen* ist deshalb
            # der richtige nächste Schritt und war doch nur ein Satz. Angeboten
            # wird er nur, wenn die Voxelstufe noch nicht dran war — das
            # entscheidet ``BooleanFailedError`` an seinen versuchten Stufen.
            "use_voxel_stage": lambda _error: self.session.recompute_fully(),
            # **Nur wo es etwas zu wiederholen gibt.** Nach einem gescheiterten
            # Schreiben sind das die zwei Antworten, die wirklich helfen: die
            # Datei freigeben und *erneut* schreiben, oder einen *anderen Ort*
            # nehmen. Außerhalb dieses Falls wüsste niemand, *was* wiederholt
            # werden soll — derselbe Grundsatz wie oben: Was hier nicht steht,
            # wird nicht angeboten.
            **(
                {
                    "retry": lambda _error: self._after_write_failure("again"),
                    "save_elsewhere": lambda _error: self._after_write_failure("elsewhere"),
                }
                if self._write_failure is not None
                else {}
            ),
            # **Der Draht, der fehlte.** ``install`` vergeben
            # ``BRepUnavailable`` und jeder ``ExternalToolError`` — ohne
            # Handler wurde daraus ein grauer Satz („… installieren"), während
            # der Dialog, der genau das kann, im Hilfe-Menü stand. Zwei
            # Zeilen darunter hing er unter ``open_settings``, also unter
            # einem Namen, den kein Knopf trug.
            "install": lambda _error: self.action_install_extras(),
            # Und der heißt jetzt, was er tut: die Einstellungen. Bis hierhin
            # öffnete er die Liste der externen Programme, weil der Kern ihn
            # dafür benutzte — der Knopf log also seinen Namen.
            "open_settings": lambda _error: self.action_settings(),
            "enter_licence_key": lambda _error: self.action_activate(),
            "activate_online": lambda _error: self.action_activate(),
            "activate_offline": lambda _error: self.action_activate(),
            "deactivate_device": lambda _error: self.action_activate(),
            "buy_licence": lambda _error: open_website(),
        }

    def action_activate(self) -> None:
        """Öffnet den Freischaltdialog (Konzept §2 B).

        Steht im Hilfe-Menü und nicht nur hinter der Fehlerhandlung
        ``enter_licence_key``: Wer kauft, braucht einen Weg, den Schlüssel
        einzutragen und diesen Rechner online oder per Datei zu aktivieren,
        **bevor** ihn etwas aufhält.

        Den gehaltenen Zustand räumt der Dialog selbst weg. Hier bleibt, die
        Aktionen nachzuziehen — mit einem eingetragenen Schlüssel steht wieder
        offen, was der abgelaufene Testlauf zugemacht hat.
        """
        ActivationDialog(self).exec()
        self._update_actions()
        self._refresh_chat_availability()
        self._trial_status_line()

    def _object_of(self, error: AppError) -> ObjectId | None:
        """Der Körper, um den es geht — aus dem Fehler oder aus der Auswahl."""
        if error.object_id:
            return error.object_id
        chosen = self.object_tree.selected_objects()
        return chosen[0] if chosen else None

    def _show_error_location(self, error: AppError) -> None:
        """„Stellen zeigen" heißt: die Karte, auf der sie zu sehen sind (§18.4).

        Ein Fehler nennt selten eine einzelne Koordinate — bei einem Netz mit
        drei offenen Kanten wären es drei. Die Defektkarte färbt sie alle, und
        das ist die Antwort auf die Frage, die der Knopf stellt.
        """
        object_id = self._object_of(error)
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result and object_id else None
        if entry is None:
            return
        self.object_tree.select_object(entry.id)
        self.tools.activate("analysis")
        self.analysis_bar.show_map("defects")
        self._analysis_map("defects", entry.id)

    def _apply_from_transform_bar(self, op: str, params: dict[str, Any]) -> None:
        """Ein Wert aus der Bewegen-Leiste wird ein Schritt im Verlauf.

        Die Leiste rechnet nichts und ändert nichts; sie nennt eine
        registrierte Operation und ihre Werte (Regel 2). Damit ist jeder
        getippte Wert genauso rücknehmbar wie ein Zug am Griff — und steht im
        Verlauf mit demselben Namen.

        Ohne gewähltes Objekt sagt die Statuszeile, was fehlt. Kein Dialog:
        Die Handlung ist rücknehmbar, und Regel 19 verbietet die Rückfrage
        davor; der Satz kommt aus derselben Quelle wie überall
        (:func:`_needs_objects`), damit nicht zwei Stellen verschieden
        erklären, was dasselbe ist.
        """
        # **Erst das Merkmal, dann der Körper** (Robert, 03.09.2026). Steht die
        # Auswahl auf einer Bohrung und gibt es die Merkmalsoperation, gilt der
        # Zug ihr — sonst wie bisher dem ganzen Teil.
        single = self.feature_draft(op, params)
        if single is not None:
            self.session.apply(REGISTRY.get(str(single.op)).title, [single])
            return
        chosen = self.inputs_for_transform(op)
        if not chosen:
            self.announce(_needs_objects(0))
            return
        # **Ein Draft je Körper, alle in einer Transaktion.** Wer zwei Teile
        # markiert hat, meint zwei — und ein Undo nimmt beide zusammen zurück,
        # weil es eine Handlung war.
        #
        # **Und alle um denselben Punkt.** Ohne ihn drehte jedes Teil um sich
        # selbst, und die Anordnung der Auswahl ginge verloren; bei einem
        # einzelnen Körper bleibt :meth:`pivot_for_transform` leer, dann gilt
        # sein eigener Schwerpunkt wie bisher. Der getippte Winkel nimmt den
        # Punkt aus derselben Quelle wie der Zug am Griff — zwei Wege zum
        # selben Ergebnis sind sonst zwei Ergebnisse.
        params = {**params, **self.pivot_for_transform()}
        drafts = [OperationDraft(op=op, inputs=(one,), params=params) for one in chosen]

        # **Nach dem Drehen aufs Bett — in derselben Transaktion.** Eine
        # Drehung um X oder Y kippt den Körper, und seine Unterseite liegt
        # danach irgendwo: mal über der Platte, mal darunter. Wer dreht, will
        # fast immer drucken, und ein Teil, das nicht aufliegt, druckt nicht.
        #
        # Entscheidend ist das **Wo**, nicht das Ob: Zwei getrennte
        # ``session.apply`` wären zwei Schritte im Verlauf und zwei Undos für
        # eine Handlung — der Kunde drückt einmal Strg+Z, sieht das Teil in der
        # Luft und weiß nicht, was er da halb zurückgenommen hat. Als ein
        # Aufruf ist es eine Handlung mit zwei Teilen, und genau so heißt sie
        # auch im Verlauf.
        title = REGISTRY.get(op).title
        if self.transform_bar.drops_to_bed():
            drafts += [OperationDraft(op="place_on_bed", inputs=(one,)) for one in chosen]
            title = tr("Drehen und aufs Bett setzen")

        self.session.apply(title, drafts)

    def _repair_after_error(self, error: AppError) -> None:
        """§17.1: vor dem Fehler wiederholen, sonst am Befund anhängen.

        Ein angehaltener Operationslauf braucht die Reparatur **vor** seinem
        fehlerhaften Schritt. Ein gewöhnlicher Berichtsbefund — etwa direkt
        nach dem Einlesen — hat dagegen keinen angehaltenen Suffix und bekommt
        die Reparatur als nächsten Schritt. In beiden Fällen stammt das Ziel
        aus dem Dokument oder dem Befund, nie aus der aktuellen Auswahl.
        """
        result = self.session.last_result
        if error.op_id is not None and result is not None and result.stopped_at == error.op_id:
            self.session.repair_and_retry(error.op_id)
            return
        object_id = error.object_id
        if object_id is None:
            return
        self.session.apply(
            REGISTRY.get("repair").title,
            [OperationDraft(op="repair", inputs=(object_id,))],
        )

    def _remove_small_parts(self, error: AppError) -> None:
        """Dieselbe Operation wie die Reparatur — aber mit dem Schalter, der wirkt.

        ``repair`` kann die kleinen Einzelteile entfernen und lässt sie in der
        Vorgabe stehen (``small_components: bool = False``). Wer hier
        :meth:`_repair_after_error` wiederverwendet, bekommt einen Knopf, der
        durchläuft, Erfolg meldet und nichts tut.

        Kein Bestätigungsdialog (Regel 19): Die Handlung ist eine Operation im
        Verlauf, und Strg+Z nimmt sie zurück.
        """
        object_id = self._object_of(error)
        if object_id is None:
            return
        self.session.apply(
            REGISTRY.get("repair").title,
            [
                OperationDraft(
                    op="repair",
                    inputs=(object_id,),
                    params={"small_components": True},
                )
            ],
        )

    def _split_after_error(self, error: AppError) -> None:
        """Zu groß für das Bett: teilen, bis jedes Stück passt (§25)."""
        object_id = self._object_of(error)
        if object_id is not None:
            self.action_auto_split(object_id)

    def _change_selection_after_error(self, error: AppError) -> None:
        """Einem Schritt andere Objekte geben — im Objektbaum, nicht im Dialog.

        **Der zweite Fall von „Eingabe korrigieren", und er ist kein Wert.**
        Wo ein *Parameter* nicht geht, öffnet ``edit_operation`` den Schritt mit
        dem Cursor im genannten Feld. Wo die *Auswahl* nicht geht, gibt es
        nichts aufzuklappen: ``field="in"`` ist keine Zeile im Formular, und ein
        Dialog darauf zeigte auf ein Feld, das es nicht gibt.

        Also der Weg, den der Nutzer ohnehin kennt — im Objektbaum markieren.
        Steht dort schon eine Auswahl, wird sie genommen; steht keine, sagt die
        Statuszeile, was fehlt, statt einen Dialog aufzumachen (Regel 19: die
        Handlung ist rücknehmbar, sie braucht keine Rückfrage).

        Der Schritt wird **ersetzt** und nicht verdoppelt (§15.4) — dieselbe
        Zusicherung wie beim Ändern eines Parameters.
        """
        if error.op_id is None:
            return
        chosen = self.object_tree.selected_objects()
        if not chosen:
            self.announce(
                tr("Markieren Sie die Objekte im Objektbaum und wählen Sie die Handlung erneut.")
            )
            return
        self.session.change_inputs(error.op_id, list(chosen))

    def _show_step_values(self, error: AppError) -> None:
        """Die rohen Werte eines Schritts zeigen, den diese Fassung nicht kennt.

        **Der Gegenpart zu einem Befund, der sonst in eine Sackgasse führte.**
        ``evaluate.unknown_operation`` sagt dem Kunden, seine Werte blieben
        erhalten — und bis hierhin gab es keinen Weg, an sie heranzukommen: Der
        Operationsdialog wird aus einem Registereintrag gebaut, den es für
        diesen Schritt nicht gibt. Löschen hilft beim Aufräumen; zum Bergen
        der Arbeit braucht es weiterhin diese Ansicht.

        Derselbe Handler bedient die Ausnahme aus ``History._spec_of``. Damit
        endet die Reise — Datei öffnen, Befund lesen, Verlauf zeigen, Schritt
        anklicken — bei der Arbeit des Kunden statt an einem Programmfehler.
        """
        if error.op_id is None:
            # Wie bei ``_correct_after_error``: ``NEEDS_OP`` filtert das schon,
            # das hier ist die Zusicherung für jeden anderen Aufrufer.
            return
        wanted = next(
            (entry for entry in self.session.project.document.ops if entry.id == error.op_id),
            None,
        )
        if wanted is None:
            return
        StepValuesDialog(wanted, self).exec()

    def _correct_after_error(self, error: AppError) -> None:
        """Den Schritt wieder öffnen, dessen Werte nicht gingen (§2.7, §2.1).

        **Der häufigste Fehler des Programms hatte keinen Weg zurück.** Eine
        Operation, deren Werte nicht gehen, wirft keinen Fehlerdialog: Der Kern
        macht daraus einen Befund und hält die Kette an. Im Prüfbericht stand
        dann „Der Wert liegt über dem zulässigen Höchstwert" — und der Weg zu
        diesem Wert war, den Schritt im Verlauf zu suchen und doppelzuklicken.
        *Eingabe korrigieren* stand daneben, aber nur als Satz: die häufigste
        Handlung des Kerns, und die einzige ohne Handler.

        ``edit_operation`` ist genau das Richtige dafür: derselbe erzeugte
        Dialog auf den Werten aus der Datei, und beim Übernehmen wird der
        Schritt **ersetzt** statt ein zweiter angelegt (§15.4). Damit ist auch
        das Versprechen aus §2.1 eingelöst, dass jeder Wert nachträglich
        änderbar ist — an der Stelle, an der es zählt.
        """
        if error.op_id is None:
            # ``offered_actions`` filtert das (``NEEDS_OP``), und das Menü am
            # Befund bietet die Handlung nur mit Kennung an. Bleibt als
            # Zusicherung für jeden anderen Aufrufer.
            return
        # Der Kern nennt das Feld, das nicht ging (``ValidationError.field``),
        # und der Befund trägt es weiter. Damit steht der Cursor gleich dort.
        self.edit_operation(error.op_id, str(error.values.get("field", "")))

    def _place_on_bed_after_error(self, error: AppError) -> None:
        """Ein Klick gegen den häufigsten Befund von Weg 1 (§17.1, §2.7).

        Ein heruntergeladenes Modell ist um den Ursprung zentriert und steckt
        damit zur Hälfte unter der Platte. Die Eingangsstufe setzt es bewusst
        nicht von selbst auf — sie soll es *anbieten*, und angeboten war es
        nirgends: Der Bericht nannte den Fall, und die einzigen Handlungen dazu
        waren *Modell teilen* und *Auf den Bauraum verkleinern*.

        Kein Dialog davor: die Operation hat keinen Parameter, und ein Undo
        nimmt sie zurück (Regel 19).
        """
        object_id = self._object_of(error)
        if object_id is None:
            return
        spec = REGISTRY.get("place_on_bed")
        self.session.apply(
            spec.title, [OperationDraft(op=spec.name, inputs=(object_id,), params={})]
        )

    def _arrange_after_error(self, error: AppError) -> None:
        """Neben der Platte heißt verschieben, nicht verkleinern (§29).

        Dieselbe Verwechslung wie beim Aufsetzen, nur in x und y. *Auf dem Bett
        anordnen* arbeitet über die ganze Szene — es legt alle nebeneinander,
        auch den, der herausragte.

        **Und es braucht die Szene trotzdem als Eingabe.** „Über die ganze
        Szene" heißt nicht „ohne Eingaben": Der Stapel plant die Ausgänge eines
        Schritts, und für eine Operation mit variabler Objektzahl ohne Eingaben
        sind das keine (``History._outputs_for``). Der Schritt landete im
        Verlauf, gab nichts zurück, und kein Körper bewegte sich — ein
        Vorschlag nach Regel 17, der optisch erfüllt und funktional hohl war,
        wie ``scale_to_fit`` vor ihm. Gemessen an zwei Würfeln unter der
        Platte: über das Menü wandern sie auf (-105, 85, 0) und (-80, 85, 0),
        über diesen Knopf blieben beide auf (-10, -10, -10) stehen, ohne
        Meldung. Getroffen hat es den häufigsten Importfall überhaupt — eine
        3MF in Bettkoordinaten meldet ``arrange.off_the_plate``, und dieser
        Knopf ist die Handlung, die dort hilft.

        Die Eingaben kommen über :func:`inputs_for`, aus demselben Grund, aus
        dem Menü, Palette und Fernaufruf sie dort holen: Die Regel, was eine
        Operation bekommt, gehört an eine Stelle.

        Der Abstand kommt aus der Druckbetthaftung wie im Dialog des
        Menüeintrags (:meth:`_spacing_for`). Hier ist er nicht Vorbelegung,
        sondern die einzige Gelegenheit — ein Knopf ohne Dialog fragt nichts,
        und zwei Teile mit je fünf Millimetern Brim stehen einander sonst auf
        der Platte im Weg.
        """
        spec = REGISTRY.get("arrange_bed")
        result = self.session.last_result
        objects = list(result.scene.objects) if result is not None else []
        inputs = inputs_for(spec, objects, ())
        if not inputs:
            return
        self.session.apply(
            spec.title,
            [OperationDraft(op=spec.name, inputs=inputs, params=self._spacing_for(spec))],
        )

    def _scale_after_error(self, error: AppError) -> None:
        """Auf den Bauraum verkleinern — mit dem Faktor, der wirklich passt.

        **Der Knopf tat nichts, und das war nicht zu sehen.** Gelesen wurden
        ``build_volume`` und ``size`` aus den Werten des Fehlers — zwei
        Schlüssel, die **keine** Ausnahme und **kein** Befund je trägt. Die
        Bedingung darunter griff also immer, und die Methode kehrte still
        zurück: ein Vorschlag nach Regel 17, der optisch erfüllt und
        funktional hohl war, wie „Reparieren und erneut versuchen" vor ihm.

        Gerechnet wird jetzt aus Profil und Szene. Das ist keine zweite
        Wahrheit, sondern dieselbe, aus der auch ``check_build_volume``
        rechnet — und sie ist immer da, gleich ob die Handlung aus einem
        Fehlerdialog kommt oder aus dem Kontextmenü des Prüfberichts.

        Ein Prozent Luft, damit das Teil nicht exakt an der Wand klebt.
        """
        object_id = self._object_of(error)
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result and object_id else None
        if object_id is None or entry is None:
            return
        volume = self.session.profile.printer.build_volume
        size = as_mesh_data(entry.mesh).bounds.size
        needed_any = [needed for needed in size if needed > 0.0]
        if not needed_any:
            return
        factor = min(
            available / needed
            for available, needed in zip(volume, size, strict=False)
            if needed > 0.0
        )
        self.session.apply(
            REGISTRY.get("scale_object").title,
            [
                OperationDraft(
                    op="scale_object", inputs=(object_id,), params={"factor": factor * 0.99}
                )
            ],
        )

    def _on_selection(self, object_id: str | None) -> None:
        # **Alle gewählten Körper, nicht nur der erste.** Hier stand
        # ``select(object_id)`` — die Kennung des ersten Eintrags —, während
        # die Statuszeile drei Zeilen weiter unten mit ``selected_objects()``
        # rechnet und ``inputs_for_transform`` dieselbe Menge zurückgibt. Bei
        # zwei gewählten Teilen leuchtete eines, die Zeile sagte „2 Teile",
        # und ein Zug an der Bewegen-Leiste bewegte beide (gemessen von
        # 3d-druck-85, 03.09.2026).
        #
        # Dass alle bewegt werden, ist die Entscheidung — sie steht unten im
        # Kommentar zur Zahl. Falsch war das Bild, und das Bild wird hier
        # gesetzt. Der erste führt: An ihm hängt der Griff, weil ein Griff
        # einen Bezugspunkt braucht; die weiteren tragen nur die Farbe.
        chosen = self.object_tree.selected_objects()
        self.viewport.select(chosen[0] if chosen else object_id, more=chosen[1:])
        # Karte und Schichtanalyse gehören zu einem Körper; ein anderer Körper
        # braucht seine eigenen, also folgen sie der Auswahl, statt zu
        # verweilen.
        self._on_map_changed(self.analysis_bar.chosen())
        self._on_layer_changed(self.layer_bar.index())
        self._update_actions()
        self._update_transform_roles()
        # „Abtragen“ hängt nicht nur am Umriss, sondern am gewählten exakten
        # Körper. Wer dem Hinweis folgt und ihn im Objektbaum auswählt, muss
        # den Knopf sofort benutzen können — ohne erst noch die Kamera oder
        # die Skizze zu bewegen.
        if self._sketch_panel is not None:
            # Neben dem Knopf ändern sich auch Kreuz, Griffbeschriftung und
            # Erklärung im Viewport. Ein gemeinsamer Neuaufbau hält alle vier
            # Auskünfte im selben Zustand.
            self._redraw_sketch()
        else:
            self._update_sketch_actions()
        result = self.session.last_result
        chosen = self.object_tree.selected_objects()
        entries = [result.scene.objects.get(entry) for entry in chosen] if result else []
        meshes = [as_mesh_data(entry.mesh) for entry in entries if entry is not None]
        described = describe_selection(result, object_id)
        if described is None or not meshes:
            self.measurements.clear_selection()
            return
        # **Die Zahl statt „Auswahl".** Sie allein nannte nicht einmal, wie
        # viele Teile gewählt sind.
        #
        # Hier stand kurz auch, was ein Zug tut — „Ziehen verschiebt alle ·
        # Drehen und Größe gelten dem ersten". Der Satz ist mit dem genannten
        # Drehpunkt gegenstandslos geworden: Alle drei Züge gelten jetzt der
        # ganzen Auswahl, und ein Hinweis auf eine Einschränkung, die es nicht
        # mehr gibt, ist schlechter als keiner. Er ist auch aus den fünf
        # Katalogen entfernt — ein Schlüssel, den niemand mehr benutzt, meldet
        # sich sonst in ``test_translations`` als „nicht mehr gebraucht".
        name = described[0] if len(meshes) == 1 else tr("{count} Teile").format(count=len(meshes))
        bounds = bounding_box_of(meshes)
        self.measurements.show_object(name, bounds.size, volume_of(meshes))

    def action_add_parameter(self) -> None:
        """§13: ein Hauptmaß benennen — auch ohne den Agenten (§2.3)."""
        dialog = ParameterDialog(self.session.project.document.parameters, self)
        if dialog.exec() != ParameterDialog.DialogCode.Accepted:
            return
        self.session.add_parameter(dialog.parameter())

    def action_edit_parameter(self, name: str) -> None:
        """§13: die Grenzen eines vorhandenen Maßes ändern — derselbe Dialog.

        Der Weg dorthin ist das Kontextmenü an der Zeile der Parameterleiste.
        Ohne ihn waren Grenzen anlegbar und nie änderbar: Die Leiste liest
        ``minimum``/``maximum`` nur als Spinbox-Grenzen, und *Parameter
        anlegen …* wies den vorhandenen Namen ab — das Feld klemmte, und der
        einzige Dialog dazu sagte „Diesen Namen gibt es schon" (§2.1).

        Keine Rückfrage: Die Änderung ist eine Transaktion und rücknehmbar
        (Regel 19).
        """
        parameters = self.session.project.document.parameters
        existing = parameters.get(name)
        if existing is None:
            return
        dialog = ParameterDialog(parameters, self, existing=existing)
        if dialog.exec() != ParameterDialog.DialogCode.Accepted:
            return
        self.session.edit_parameter(name, dialog.parameter())

    def _on_parameter_edited(self, name: str, value: float) -> None:
        """An einer Zahl zu drehen ist eine Transaktion, dann eine frische
        Auswertung (§13, §15.5).

        Dieselbe Rückfrage wie bei einer Operation: eine Änderung nach einem
        Undo wirft die abgeschnittenen Schritte weg (§15.4), und das darf eine
        gedrehte Zahl nicht stiller tun als ein Menüeintrag. Sagt der Nutzer
        nein, springt die Leiste auf den Stand des Dokuments zurück.
        """
        if self.session.history.discardable and not confirm_discard(
            self.session.history.discardable, self._discarded_names(), self
        ):
            self.parameters.show_document(self.session.project.document)
            return
        self.session.change_parameter(name, value)

    def _on_parameter_unit_edited(self, name: str, unit: str) -> None:
        """Die feste Einheitenauswahl als rücknehmbare Dokumentänderung.

        Auch sie kommt erst nach dem Qt-Signal der Auswahl hier an. Der
        anschließende Neuaufbau der Leiste darf den gerade angeklickten Kasten
        nicht während seines eigenen Signals freigeben — derselbe Absturzpfad
        wie bei der Zahl links daneben.
        """
        if self.session.history.discardable and not confirm_discard(
            self.session.history.discardable, self._discarded_names(), self
        ):
            self.parameters.show_document(self.session.project.document)
            return
        existing = self.session.project.document.parameters.get(name)
        if existing is None:
            return
        self.session.edit_parameter(name, replace(existing, unit=unit))

    # --- start ------------------------------------------------------------------

    def start(self) -> None:
        """Was passiert, sobald das Fenster wirklich auf dem Bildschirm ist (§38).

        Mit Absicht nicht im Konstruktor: der erste Start öffnet einen modalen
        Dialog, und ein Fenster, das das während seines Aufbaus tut, lässt sich
        von nichts aufbauen, das kein Mensch ist — kein Test, kein
        Screenshot-Werkzeug, kein zweites Fenster.
        """
        if first_run.should_run(self.settings):
            self.action_first_run()
        self._offer_unsaved_recovery()
        if self.settings.check_for_updates:
            self._check_for_updates()
        self._apply_remote()
        # Sie prüft selbst, ob überhaupt noch jemand gefragt wird — erledigt,
        # abgelehnt, dreimal gezeigt oder verkaufte Fassung, und sie tut
        # nichts.
        self._usage.start()

    def _apply_remote(self) -> None:
        """Die MCP-Schnittstelle an- oder abschalten (Konzept P15 §7 Etappe 9).

        Nach jeder Änderung der Einstellungen und einmal beim Start. Der Port
        kann sich geändert haben, also wird bei jeder Änderung gestoppt und
        neu gestartet — ein laufender Server auf dem alten Port wäre genau die
        offene Tür, die niemand bestellt hat.

        Ein belegter Port ist kein Grund, die Anwendung anzuhalten: die
        Schnittstelle bleibt aus, und es steht im Protokoll. Ein modaler Fehler
        beim Start wäre die schlechteste aller Antworten auf eine Einstellung,
        die mit dem Konstruieren nichts zu tun hat.

        **Im Protokoll allein stand es aber zu leise** (Regel 17): Der Haken in
        den Einstellungen blieb gesetzt, und nichts sagte, dass die
        Fernsteuerung nicht läuft — wer ein fremdes Programm darauf zeigen
        ließ, suchte den Fehler dort. Die Statuszeile nennt jetzt den Port und
        den Weg zurück zu ihm.
        """
        if self._remote is not None:
            self._remote.stop()
            self._remote = None
        if not self.settings.remote_enabled:
            return
        try:
            server = RemoteServer(WindowBridge(self.run_remote, self), self.settings.remote_port)
            server.start()
        except OSError as problem:
            _log.warning("mcp server did not start: %s", problem)
            self.announce(
                tr(
                    "Die Fernsteuerung bleibt aus: Port {port} ist belegt. "
                    "Unter Bearbeiten → Einstellungen … lässt sich ein anderer wählen."
                ).format(port=self.settings.remote_port)
            )
            return
        self._remote = server

    def _offer_unsaved_recovery(self) -> None:
        """§38: eine Sicherung, die nie einen Namen bekam, wird angeboten.

        Sie wurde geschrieben, seit es die automatische Sicherung gibt, und
        nie angeboten: das Fenster suchte nur neben einer geöffneten Datei.
        Wer vor dem ersten Speichern abstürzte, hatte die Arbeit verloren,
        obwohl sie auf der Platte lag.
        """
        candidate = find_recovery(None)
        if candidate is None:
            return
        if not self._ask_recovery(
            candidate,
            None,
            tr("Ein Projekt aus einer früheren Sitzung wurde nie gespeichert."),
            tr("Leer beginnen"),
        ):
            # Dieselbe Begründung wie beim benannten Fall: sonst begrüßt
            # dieselbe Frage jeden Start, bis irgendwann jemand die Datei von
            # Hand löscht.
            clear_autosave(None)
            return
        try:
            self.session.recover(candidate)
        except AppError as error:
            show_error(error, self)
            return
        self._show_start_screen(False)

    def action_first_run(self) -> None:
        """§38: Sprache, Drucker, Filamente, externe Programme, Chat-Zugang.
        Überspringbar.

        **Die Schleife ist der Sprachwechsel.** Der Dialog übersetzt sich nicht,
        er wird neu gebaut — dieselbe Entscheidung wie beim Hauptfenster
        (:func:`app.ui.app.rebuild_for_language`), und aus demselben Grund: Ein
        ``retranslate()`` müsste neunzehn Texte einzeln nachziehen, und die
        vergessene Zeile fällt nur in einer Sprache auf. Er schließt sich
        deshalb mit ``LANGUAGE_CHANGED``, seine Antworten stehen dann schon in
        den Einstellungen, und der nächste Durchgang baut ihn daraus wieder
        auf.

        Ein Deckel ist keiner: Jeder Durchgang setzt ``settings.language`` auf
        die gewählte Sprache, und der Dialog schließt nur, wenn die Wahl davon
        abweicht. Zweimal dieselbe Sprache zu wählen beendet die Schleife also
        von selbst.
        """
        spoken = self.settings.language
        while True:
            dialog = first_run.FirstRunDialog(self.settings, self)
            dialog.importRequested.connect(self.action_import)
            answer = dialog.exec()
            if answer != first_run.LANGUAGE_CHANGED:
                break
            dialog.release()
        if answer == first_run.FirstRunDialog.DialogCode.Accepted:
            dialog.apply_to(self.settings)
            self._adopt_defaults()
        else:
            # Überspringen zählt als erledigt: beim nächsten Mal wieder zu fragen
            # wäre Nörgeln.
            self.settings.first_run_done = True
        # Die Erhebung übernimmt geladene Spulen auch dann, wenn dieser Dialog
        # über Hilfe → Erste Schritte in einem bestehenden Projekt geöffnet
        # wurde. Das Panel ist bereits gebaut und liest den Katalog deshalb
        # ausdrücklich neu ein; eine Dokumentauswertung wäre dafür weder nötig
        # noch bei einem nichtleeren Projekt zulässig.
        self.filaments.refresh_catalogue()
        save_settings(self.settings)
        # Wer im Dialog den Chat eingerichtet hat, soll ihn nicht erst nach
        # einem Neustart bekommen — derselbe Weckruf wie in action_llm_key.
        self.session.set_agent_backend(None)
        self._refresh_chat_availability(probe_local=True)
        # **Der Dialog hat sich schon umgestellt, das Fenster dahinter nicht.**
        # Den Fenstertausch löst der Erststart in ``main()`` aus — oder dieses
        # Signal, wie in ``action_settings``; über das Hilfemenü geöffnet gäbe
        # es ihn sonst gar nicht.
        if self.settings.language != spoken:
            self.languageChanged.emit()

    def _discarded_names(self) -> list[str]:
        """Wie die zurückgenommenen Schritte heißen, jüngster zuerst.

        Die Frage nannte nur ihre Zahl. „Diese Änderung verwirft 2
        zurückgenommene Schritte" sagt, wie viel weg ist, nicht was — und
        genau das entscheidet, ob man Ja sagt.
        """
        return [str(entry.title) for entry in reversed(self.session.history.undone)]

    def _adopt_defaults(self) -> None:
        """Ein leeres Projekt übernimmt die eben gewählten Vorgaben.

        Die Erstinbetriebnahme fragt nach dem Drucker; das Material kommt aus
        dem Filament und wird dort nicht ein zweites Mal abgefragt. Beim
        ersten Start ist das offene Projekt genau das, mit dem weitergearbeitet
        wird: Der gewählte Drucker muss deshalb sofort darin gelten.

        Nur bei leerem Dokument. In ein Projekt mit Inhalt greift eine
        Einstellung nicht hinein — dafür gibt es die Druckeinstellungen, und
        ein stiller Profilwechsel unter einer fertigen Konstruktion wäre eine
        Geometrieänderung ohne Operation.
        """
        if self.session.project.document.ops:
            return
        self.session.start_new(self.settings.printer, self.settings.material)

    def _check_for_updates(self) -> None:
        """§37.2: ein sichtbarer Hinweis, wenn es etwas Neueres gibt.

        Hier stand „Nichts wird heruntergeladen, nichts ersetzt" — richtig zu
        der Zeit, als der Weg wirklich nur ein Link war, und mit ``download()``
        und ``start_installer()`` still falsch geworden. Die Zusage des
        Bauplans ist eine andere und eine genauere: **Die Grenze liegt beim
        Auslöser, nicht beim Vorgang.** Es lädt nichts von allein, ersetzt sich
        nichts im Hintergrund und startet nichts ohne Klick.
        """
        worker = _UpdateWorker()
        worker.done.connect(self._update_answered)
        # Ohne Empfänger blieb ``_asked_for_update`` stehen, und „Nach einer
        # neuen Version sehen" war für den Rest der Sitzung ein toter Knopf
        # (Gesamtreview I-2). Kein Dialog: Die Prüfung läuft unaufgefordert
        # beim Start, und ihr Scheitern ist eine Zeile, keine Störung.
        worker.crashed.connect(self._update_crashed)
        # Nicht als Lambda, das ``None`` in genau das Feld schreibt, dessen
        # Objekt es gerade zustellt: derselbe Fehler, der beim Auswertungs-
        # Arbeiter die Suite ohne Traceback abriss (siehe Session).
        worker.finished.connect(self._update_worker_done)
        self._update_worker = worker
        self._leash.start(worker)

    def _update_crashed(self, detail: str) -> None:
        _log.warning("update check crashed: %s", detail)
        if self._asked_for_update:
            # Auf einen Klick hin wäre Schweigen ein toter Knopf — derselbe
            # Satz wie bei einer unerreichbaren Seite, denn mehr weiß der
            # Kunde daraus nicht.
            self._asked_for_update = False
            self.announce(tr("Die Seite war nicht erreichbar — später noch einmal versuchen."))

    def _update_worker_done(self) -> None:
        """Die Abfrage ist ausgelaufen — ihr Arbeiter bleibt bis zur nächsten."""
        self._finished_update_worker = self._update_worker
        self._update_worker = None

    def _update_answered(self, release: Any) -> None:
        if release is not None and release.newer_than():
            self._asked_for_update = False
            self.announce(tr("Neue Version verfügbar: {version}").format(version=release.version))
            self._show_update(release)
            return
        # Beim Start schweigt die Abfrage, wenn es nichts Neues gibt — niemand
        # will beim Öffnen lesen, dass alles beim Alten ist. Auf einen Klick
        # hin ist dasselbe Schweigen ein toter Knopf, und der Nutzer klickt
        # ein zweites Mal.
        if self._asked_for_update:
            self._asked_for_update = False
            if release is None:
                self.announce(tr("Die Seite war nicht erreichbar — später noch einmal versuchen."))
            else:
                self.announce(
                    tr("Sie haben die aktuelle Version ({version}).").format(version=APP_VERSION)
                )

    def _offer_survey(self) -> None:
        """Die halbe Stunde ist zusammen: Die Karte tritt über die Ansicht.

        **Kein Dialog an dieser Stelle.** Der Update-Hinweis kommt beim Start,
        dieser mitten in die Arbeit — ein Fenster, das dort alles anhält, wird
        weggeklickt, ohne gelesen zu werden, und die Rückmeldung, die es holen
        sollte, ist damit verloren. Die Karte fragt erst, ob überhaupt gefragt
        werden darf; der Bogen geht nur auf, wenn jemand Ja sagt.

        **Und nicht mitten in eine Rechnung.** Wer gerade auf ein Ergebnis
        wartet, hat für eine Frage keinen Kopf. Die Uhr läuft dann weiter und
        meldet sich in einer Minute wieder — sie hält erst an, wenn die Karte
        wirklich dasteht. Das ist der Unterschied zwischen „später" und
        „gar nicht": Ein Bogen, der ausgerechnet in eine lange Rechnung fällt,
        wäre sonst für die ganze Sitzung verloren.
        """
        if self.session.busy or self._survey_notice.isVisibleTo(self.viewport):
            return
        self._usage.stop()
        self._survey_notice.ask()

    def _open_survey(self) -> None:
        """*Rückmeldung geben*: der Rückmeldungsdialog als Bogen.

        **Ein Fenster, ein Sendeknopf, ein Aufrufer.** Der Bogen ist eine
        Betriebsart des vorhandenen Dialogs und kein zweiter Weg hinaus;
        ``tests/test_support.py`` zählt die Aufrufer von ``support.send`` und
        lässt genau einen zu. Das ist die Grenze zur Telemetrie, und ein
        zweiter Weg wäre ihr Ende, wie bequem er auch wäre.
        """
        dialog = self._support_dialog(KIND_SURVEY)
        self._survey_dialog = dialog
        dialog.show()
        dialog.raise_()

    def _show_update(self, release: Any) -> None:
        """Den Fund zeigen — sichtbar, und nicht in einer Zeile, die die
        nächste Meldung überschreibt (§37.2).

        Nicht modal: Der Hinweis kommt beim Start, und ein Fenster, das dort
        alles anhält, ist eines, das man wegklickt, ohne es gelesen zu haben.
        Es steht davor, es lässt sich beiseiteschieben, und *Später* heißt
        wirklich später.
        """
        dialog = UpdateDialog(release, self)
        dialog.installRequested.connect(self._install_update)
        # Festhalten: Ein nicht modaler Dialog ohne Referenz ist einer, den der
        # Aufräumer einsammelt, sobald diese Methode zurückkehrt.
        self._update_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _install_update(self, file: object) -> None:
        """Beenden, dann starten — in dieser Reihenfolge.

        Unter Windows hält die laufende Anwendung ihre eigenen Dateien fest;
        ein Installer, der sie ersetzen will, findet sie gesperrt. Und
        wichtiger: ``close`` ist der Weg, auf dem die Frage nach dem
        ungespeicherten Dokument gestellt wird. Wer dort abbricht, hat auch das
        Update abgebrochen — das Paket liegt noch, der Dialog steht noch.
        """
        package = Path(str(file))
        if not package.is_file():
            show_error(
                ExternalToolError(
                    tool="update",
                    detail=tr("Das Paket liegt nicht mehr da, wo es geladen wurde."),
                    values={"path": str(package)},
                ),
                self,
            )
            return
        if not self.close():
            return
        try:
            updates.start_installer(package)
        except AppError:
            # Das Fenster ist zu diesem Zeitpunkt zu; bleibt das Protokoll und
            # der Weg über die Download-Seite beim nächsten Start (§33.2).
            _log.exception("could not start the installer")

    def action_changes(self) -> None:
        """Der Verlauf aus dem Paket — ohne eine Frage nach draußen.

        Der Import steht hier und nicht oben: Der Dialog wird selten geöffnet,
        und ein Fenster, das beim Start alles mitlädt, was jemand *einmal*
        braucht, startet langsamer. Dieselbe Überlegung wie beim
        Abschiedsdialog der abgelaufenen Demo.
        """
        from app.ui.changes_dialog import ChangesDialog

        ChangesDialog(self).exec()

    def action_check_updates(self) -> None:
        """Von Hand nach einer neuen Version sehen (Demo-Konzept §2 G).

        Die Abfrage beim Start bleibt eine Einstellung und ist aus; ohne diesen
        Weg gäbe es für alle anderen gar keinen. Für eine Demo mit Enddatum ist
        das der Unterschied zwischen „endet am 30.10." und „ist einfach weg".
        """
        self._asked_for_update = True
        self.announce(tr("Es wird nach einer neuen Version gesehen …"))
        self._check_for_updates()

    def action_feedback(self, kind: str = KIND_IDEA) -> None:
        """Vorschlag, Fehler oder Frage — geschrieben, gesehen, gesendet (§37.2).

        Vorher war das eine vorbereitete Mail: Solidon öffnete das
        Mailprogramm, und ab da lag alles beim Nutzer — Anhänge suchen,
        Bildschirmfoto selbst machen, Projektdatei finden. Der Weg endete
        meistens genau dort. Jetzt hängen Bild, Sitzung und Protokoll schon
        dran, und der Knopf schickt sie los.

        Was das **nicht** ist: Telemetrie. Es geht nichts von allein, es geht
        nichts unbesehen, und der abgelegte Ordner steht als Weg daneben.
        """
        dialog = self._support_dialog(kind)
        dialog.exec()
        self._remember_contact(dialog)

    def report_error(self, error: BaseException, summary: str = "") -> None:
        """§33.1: ein Programmfehler bekommt ein Berichtsangebot, keinen
        Vorschlag.

        Das Bildschirmfoto entsteht **vor** dem Dialog: eine Sekunde später
        zeigte es den Fehlerdialog statt dessen, was darunter schiefging.
        """
        text = "\n".join(
            filter(None, (summary, str(error), "".join(traceback.format_exception(error))))
        )
        # **Zwei Fehler, ein Bericht.** Zwei modale Fenster übereinander heißen
        # zweimal wegklicken, und der zweite Fehler ist oft der eigentliche —
        # der erste ist die Folge, die zuerst auffällt. Der offene Bericht nimmt
        # ihn auf und tritt nach vorn.
        #
        # Das Bildschirmfoto bleibt dabei das des ersten Fehlers, und das ist
        # keine Sparsamkeit: Es entsteht **vor** dem Dialog, damit es zeigt, was
        # darunter schiefging. Beim zweiten steht der Bericht schon offen — ein
        # neues Foto zeigte ihn selbst.
        if self._crash_dialog is not None:
            self._crash_dialog.add_crash(text)
            self._crash_dialog.raise_()
            self._crash_dialog.activateWindow()
            return
        dialog = self._support_dialog(KIND_CRASH, detail=text)
        self._crash_dialog = dialog
        try:
            dialog.exec()
        finally:
            self._crash_dialog = None
        self._remember_contact(dialog)

    def _support_dialog(self, kind: str, detail: str = "") -> SupportDialog:
        """Der Rückmeldungsdialog mit allem, was dieses Fenster beisteuern kann."""
        return SupportDialog(
            kind,
            detail=detail,
            screenshot=window_shot(self),
            session=self.session,
            contact=self.settings.support_contact,
            parent=self,
        )

    def _remember_contact(self, dialog: SupportDialog) -> None:
        """Die Rückadresse überlebt den Dialog — sie zweimal zu tippen ist
        einmal zu viel."""
        address = dialog.contact.text().strip()
        if address and address != self.settings.support_contact:
            self.settings.support_contact = address
            save_settings(self.settings)

    # --- window -----------------------------------------------------------------

    def _show_start_screen(self, show: bool) -> None:
        # Der härteste Schnitt, den die Anwendung hat: der ganze Inhalt wird
        # ein anderer. Mit Blende liest das Auge „dasselbe Fenster, andere
        # Ansicht" statt von vorn (``app/ui/motion.py``).
        if show:
            # **Eine Vorschau überlebt diesen Schnitt nicht.** Wer mit einer
            # wartenden Änderung auf *Datei → Neu* geht, ließ bis zum
            # 03.09.2026 den Differenzkörper und sein Band hinter sich: Beim
            # nächsten geöffneten Projekt lag die Vorschau von vorhin über der
            # neuen Szene, und die Leertaste blendete anwendungsweit um, weil
            # mit dem Band der Ereignisfilter stehenblieb (gemessen an
            # ``action_new``: Bild da, Filter hängt).
            #
            # ``start_empty`` braucht das nicht noch einmal — es hängt am
            # Hauptknopf des Startbildschirms, ist also nur von hier aus
            # erreichbar.
            self._drop_feature_preview()
        switch(self.stack, self.start_screen if show else self.overlay)
        # Die Menüleiste folgt dem Schnitt: was eine offene Szene voraussetzt,
        # steht auf dem Startbildschirm nicht herum. Die Kürzel der Einträge
        # bleiben gültig — Qt registriert sie am Fenster, nicht an der
        # Sichtbarkeit des Menüs.
        for menu in self._workspace_menus:
            menu.menuAction().setVisible(not show)

    def _mark_report_tab(self, alerts: int) -> None:
        """Schreibt die Zahl der Fehler und Warnungen an den Reiter.

        Eine Zahl und kein Punkt: Regel 18 verlangt eine zweite Kodierung
        neben der Farbe, und „3" sagt mehr als ein Fleck. Bei null bleibt es
        beim bloßen Namen — ein Zähler, der immer dasteht, wird Tapete.
        """
        index = self.right.indexOf(self.report)
        if index < 0:
            return
        name = tr("Prüfbericht")
        self.right.setTabText(index, f"{name} · {alerts}" if alerts else name)

    def _mark_status_alerts(self, alerts: int = -1) -> None:
        """Der Warnungszähler in der Statusleiste — nur wenn er gebraucht wird.

        Nicht immer: Steht die rechte Spalte offen, trägt ihr Reiter dieselbe
        Zahl, und zwei Zähler nebeneinander sind einer zu viel. Bei
        ausgeblendeter Spalte ist er die einzige Auskunft, dass etwas
        aufgelaufen ist — und der Weg zurück.
        """
        if alerts >= 0:
            self._alerts = alerts
        count = getattr(self, "_alerts", 0)
        # ``isVisibleTo`` und nicht ``isVisible``: Gefragt ist, ob die Spalte
        # ausgeblendet **wurde**. ``isVisible`` ist auch dann falsch, wenn nur
        # das Fenster selbst noch nicht gezeigt wird — beim Aufbau und in jedem
        # Test, und der Zähler stünde dort fälschlich neben einem offenen
        # Bericht.
        show = count > 0 and not self.right.isVisibleTo(self)
        self.alert_button.setVisible(show)
        if not show:
            return
        # Das Zeichen steht neben der Zahl, nicht statt ihrer: dieselbe zweite
        # Kodierung wie am Reiter (Regel 18).
        self.alert_button.setText(f"{SEVERITY_MARKER['warning']} {count}")
        hint = tr("{count} offene Befunde — anklicken öffnet den Prüfbericht.").format(count=count)
        self.alert_button.setToolTip(hint)
        self.alert_button.setStatusTip(hint)

    def _show_alerts(self) -> None:
        """Die rechte Spalte zurückholen und den Bericht nach vorn."""
        self.right.setVisible(True)
        self.settings.right_panel_visible = True
        save_settings(self.settings)
        self._focus_report(force=True)
        self._mark_status_alerts()

    def _focus_report(self, force: bool = False) -> None:
        """Den Prüfbericht nach vorn holen.

        ``force`` überstimmt die laufende Tour. Gebraucht wird das genau
        einmal: wenn die Kette anhält. Die Statusleiste sagt dann wörtlich
        „siehe Prüfbericht", und ein Verweis auf ein Fenster, das die
        Anwendung selbst zuhält, ist keiner. Für eine Warnung im normalen
        Ablauf bleibt es beim Vorrang der Anleitung.
        """
        if not self.right.isVisible():
            return
        if not force and self.right.currentWidget() is self.tour and self.tour.active:
            # Die Tour zeigt selbst auf den Prüfbericht, wenn er dran ist —
            # ein Reiterwechsel unter der Anleitung weg wäre ihr Ende.
            return
        switch(self.right, self.report)

    def _offer_tour(self, path: Path) -> None:
        """§37.2: ein Beispiel öffnet sich mit seiner Tour — jedes andere
        Projekt räumt sie weg.

        Kein Dialog und keine Frage: der Reiter ist da, die Tour beginnt, und
        „Tour beenden“ ist jederzeit einen Klick entfernt (Regel 19).
        """
        example = examples.by_path(path)
        tour = tour_for(example.id) if example is not None else None
        if example is None or tour is None:
            self._remove_tour()
            return
        self.right.setTabVisible(self.right.indexOf(self.tour), True)
        self.tour.start(example, tour)
        if not self.right.isVisible():
            # Wer die rechte Spalte ausgeblendet hatte, bekäme eine
            # unsichtbare Tour — und das Beispiel wurde gerade absichtlich
            # geöffnet. Einblenden wie über F9, samt Einstellung.
            self.settings.right_panel_visible = True
            save_settings(self.settings)
            self.right.setVisible(True)
        self.right.setCurrentWidget(self.tour)

    def _open_example(self, example_id: str) -> None:
        """Öffnet ein Beispiel über seine Kennung — der Weg vom Ende einer Tour
        zur nächsten."""
        from app.core import examples

        path = examples.directory() / f"{example_id}.p3d"
        if path.exists():
            self.open_path(path)

    def _flash_area(self, target: str) -> None:
        """Lässt den Bereich aufleuchten, von dem ein Tourschritt spricht.

        „Sehen Sie links in den Verlauf" nennt einen Bereich, und
        wer den Satz zum ersten Mal liest, sucht ihn. Ein Rahmen für eine
        Sekunde beantwortet die Frage, ohne sie gestellt zu haben.

        Zeigt der Schritt auf den Prüfbericht, wird der Reiter gleich
        mitgeholt: er teilt sich die Spalte mit der Tour, und ihn suchen zu
        lassen hieße, die Tour aus dem Blick zu nehmen.
        """
        areas: dict[str, QWidget] = {
            "tree": self.object_tree,
            "parameters": self.parameters,
            "history": self.history_panel,
            "report": self.report,
            "viewport": self.viewport,
            "toolbar": self.toolbar,
            "tools": self.tools,
        }
        area = areas.get(target)
        if area is None:
            return
        if area is self.report:
            self.right.setCurrentWidget(self.report)
        # **Und die andere Bauart derselben Zusage.** Der Bericht teilt sich
        # eine Spalte mit der Tour und wird über den Reiter geholt; Objektbaum,
        # Parameter und Verlauf sitzen in einklappbaren Abschnitten (§2.5).
        # War einer zugeklappt, leuchtete der Rahmen um eine Kopfzeile auf,
        # unter der nichts steht — „Sehen Sie links in den Verlauf" zeigte auf
        # eine leere Stelle. Genau dieselbe Frage stellt der Agent, wenn seine
        # Rücknahme-Warnung in den Verlauf zeigt (H-1).
        open_section(area)

        area.setStyleSheet(f"border: 2px solid {_flash_colour(area)};")
        QTimer.singleShot(FLASH_MS, self, lambda: area.setStyleSheet(""))

    def _remove_tour(self) -> None:
        """Blendet den Tour-Reiter aus — beim Beenden und beim Projektwechsel."""
        self.tour.reset()
        self.right.setTabVisible(self.right.indexOf(self.tour), False)

    @staticmethod
    def _when(path: Path) -> str:
        """Wann diese Datei zuletzt geschrieben wurde, in Worten des Nutzers.

        Nicht als Zeitstempel: „vor 4 Minuten" beantwortet die Frage, die im
        Wiederherstellungsdialog wirklich gestellt wird, und „2026-08-07
        15:41:02" verlangt, sie selbst auszurechnen.
        """
        from datetime import datetime

        try:
            written = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            return tr("unbekannt")
        minutes = int((datetime.now() - written).total_seconds() // 60)
        if minutes < 1:
            return tr("gerade eben")
        # Die Einzahl steht daneben, sie wird nicht gebildet: „vor 1 Stunden"
        # liest sich wie ein Fehler in der Anwendung, und im Englischen fiele
        # das gebildete „1 hours" genauso auf. Zwei Formen je Einheit sind
        # billiger als eine Regel, die für jede Sprache anders lautet.
        if minutes < 60:
            return (
                tr("vor einer Minute") if minutes == 1 else tr("vor {n} Minuten").format(n=minutes)
            )
        hours = minutes // 60
        if hours < 24:
            return tr("vor einer Stunde") if hours == 1 else tr("vor {n} Stunden").format(n=hours)
        return written.strftime("%d.%m.%Y %H:%M")

    def _ask_recovery(
        self, candidate: Path, saved: Path | None, question: str, decline: str
    ) -> bool:
        """Die Frage nach einer automatischen Sicherung — eine für beide Fälle.

        Zwei Dialoge stellten dieselbe Entscheidung, und nur einer hatte die
        Lehre daraus gezogen. Sie steht hier, damit sie für beide gilt:

        **Die Knöpfe heißen nach ihrer Handlung**, nicht „Ja" und „Nein" —
        dieselbe Begründung wie bei ``confirm_discard``: wer „Ja" liest, muss
        die Frage im Kopf behalten, um zu wissen, was er auslöst.

        **Das Alter der Sicherung steht dabei.** Zwischen „von vor fünf
        Minuten" und „von vor drei Wochen" liegt die ganze Entscheidung. Der
        namenlose Fall hatte davon gar nichts: dort ist die Sicherung das
        Einzige, was es gibt, und sie wurde ohne jede Angabe angeboten.

        Getrennt gepflegt driftet das wieder auseinander — der Unterschied
        zwischen den beiden Fällen ist der Text, nicht der Aufbau.
        """
        box = QMessageBox(self)
        box.setWindowTitle(tr("Wiederherstellung"))
        box.setText(question)
        lines = [tr("Sicherung: {backup}").format(backup=self._when(candidate))]
        if saved is not None:
            lines.append(tr("Gespeicherter Stand: {saved}").format(saved=self._when(saved)))
        # Was das Ablehnen kostet, steht dabei. Die Sicherung wird danach
        # gelöscht — sonst käme dieselbe Frage bei jedem Öffnen wieder —, und
        # eine Löschung, die niemand angekündigt hat, ist ein Datenverlust
        # mit Ansage an die falsche Adresse.
        lines.append(tr("Wird die Sicherung nicht geöffnet, wird sie verworfen."))
        box.setInformativeText("\n".join(lines))
        restore = box.addButton(tr("Sicherung öffnen"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(decline, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(restore)
        box.exec()
        return box.clickedButton() is restore

    def _offer_recovery(self, path: Path) -> None:
        """Eine Sicherung anbieten, die neuer ist als die Datei (§38).

        **Einmal gefragt, nicht bei jedem Öffnen.** Die abgelehnte Sicherung
        blieb liegen, und weil sie weiter neuer war als die Datei, stellte das
        nächste Öffnen dieselbe Frage — und das übernächste auch. Gemessen:
        sechs Öffnungen, sechs Fragen. Eine Entscheidung, die nicht hält, ist
        keine.
        """
        candidate = find_recovery(path)
        if candidate is None:
            return
        if not self._ask_recovery(
            candidate,
            path,
            tr("Es gibt eine automatische Sicherung, die neuer ist als die Datei."),
            tr("Gespeicherten Stand behalten"),
        ):
            clear_autosave(path)
            return
        # Dieselbe synchrone Lesung wie in ``open_path``, also derselbe
        # Zeiger (§2.8).
        #
        # Über ``recover`` und nicht über ``open_project``: Letzteres machte
        # die Sicherung zum Projekt, und ein „Speichern" danach schrieb in
        # `…p3d.autosave` statt in die Datei des Nutzers. Seine eigentliche
        # Datei blieb dabei unangetastet — die wiederhergestellte Arbeit war
        # beim nächsten Öffnen wieder fort.
        with waiting():
            self.session.recover(candidate, path)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt name
        if (
            accepted_path(event) is not None
            or accepted_url(event) is not None
            or _image_path(event) is not None
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt name
        image = _image_path(event)
        if image is not None:
            self._drop_image(image)
            event.acceptProposedAction()
            return
        path = accepted_path(event)
        if path is not None:
            self.open_path(path)
            event.acceptProposedAction()
            return
        # Ein Verweis aus dem Browser ist dieselbe Handlung wie eine Datei,
        # nur liegt die Datei noch nicht auf der Platte (§16.3).
        url = accepted_url(event)
        if url is not None:
            self.download_model(url)
            event.acceptProposedAction()

    def _drop_image(self, path: Path) -> None:
        """Ein Bild auf dem Fenster ist ein Relief-Wunsch (§25).

        Auf den gewählten Körper, als geöffneter Dialog — nicht als stiller
        Import: Ein Bild wird kein Körper, es gehört einer Operation als Wert.
        """
        target = self.object_tree.selected()
        if not target:
            self.announce(tr("Bitte zuerst ein Objekt auswählen — das Bild wird ein Relief."))
            return
        try:
            # Auch das Bild kommt von der Platte, und auch hier liest die
            # Sitzung es am Stück (§2.8).
            with waiting():
                source_id = self.session.import_image(path)
        except AppError as error:
            show_error(error, self)
            return
        self.run_operation(REGISTRY.get("displace_image"), given={"source": source_id})

    def wait_for_workers(self, timeout_ms: int = 2000) -> None:
        """Jeden Arbeiter dieses Fensters auslaufen lassen.

        Ergebnisse, die niemand mehr sehen wird — aber **ein Thread, der sein
        Fenster überlebt, nimmt den Prozess mit**. Die Schichtanalyse fehlte
        hier einmal: Schließen während sie lief war ein Absturz beim Beenden.

        Als eigene Methode und nicht nur im ``closeEvent``, weil es zwei Wege
        gibt, ein Fenster loszuwerden: schließen und wegräumen. Der zweite ist
        der Weg der Tests, und dort führte er zu genau dem Absturz, gegen den
        die Liste hier geschrieben wurde — nur ohne Zeile, weil niemand mehr
        da war, die zu schreiben.
        """
        self.session.cancel()
        self.session.wait_for_idle(timeout_ms)
        # Die Analysekarte hat einen eigenen Schalter — ohne ihn läuft sie
        # ihre Sekunden zu Ende, während das Fenster schon zugeht.
        self._cancel_map_worker()
        for worker in (
            self._map_worker,
            self._slice_worker,
            self._update_worker,
            self._finished_update_worker,
            self._ollama_size_worker,
            # Der Download fehlte hier. Er folgt dem Muster mit ``retire`` und
            # ``hold_until_done`` sauber — aber die Halteleine bekommt ihn erst,
            # wenn er fertig ist. Solange er läuft, hält ihn allein dieses Feld,
            # und wer währenddessen schließt, ließ einen Thread sein Fenster
            # überleben. Genau der Absturz, gegen den diese Liste geschrieben
            # wurde.
            self._download_worker,
            self._export_worker,
            self._part_file_worker,
            *self._leash.pending(),
        ):
            if worker is not None and worker.isRunning():
                worker.wait(timeout_ms)

    def release(self, timeout_ms: int = 2000) -> None:
        """Alles loslassen, was dieses Fenster außerhalb von Qt hält: seine
        Arbeiter und seine Verbindungen zur Sitzung.

        **Was hier ausdrücklich nicht steht, ist der Viewport.** Ihn zu
        schließen war der zweite Anlauf gegen den Absturz auf dem Ubuntu-Runner,
        und er hat ihn nur verschoben: mit geschlossenem Plotter stirbt der
        **nächste** Fensteraufbau in ``render_window_interactor.initialize``,
        weil VTKs Zustand dem Prozess gehört und nicht dem Widget. Beides
        gemessen, in Fenstern nacheinander.

        Die Ursache war nie die Lebenszeit des Fensters, sondern die
        Verbindung: die Sitzung überlebt es und rief ihr Ergebnis in Widgets,
        die der Speicherbereiniger schon abgeräumt hatte. Wer die Verbindung
        kappt, braucht das Fenster nicht zu zerstören.
        """
        self.wait_for_workers(timeout_ms)
        self.spacemouse.stop()
        # **Der Wartezeiger geht mit.** Er ist ein Override der *Anwendung*,
        # nicht des Fensters: Ein Zeitgeber, der nach dem Loslassen feuert,
        # setzt ihn für alles, was danach kommt, und niemand nimmt ihn
        # zurück. In der Suite hat das acht Bestandstests umgebracht, die mit
        # der Wartezeit nichts zu tun haben — sie liefen hinter einem Test,
        # der einen Lauf begann und ihn nicht endete. Im Betrieb ist es
        # dasselbe eine Stufe größer: Wer das Fenster schließt, während
        # gerechnet wird, behält die Sanduhr über dem Schreibtisch.
        self._stop_waiting()
        # Die Sitzung überlebt dieses Fenster — in der Suite gehört sie einem
        # eigenen Fixture, im Betrieb kann ein zweites Fenster folgen. Solange
        # ihre Signale hierher zeigen, ruft das nächste Ergebnis in ein
        # Fenster, dessen Widgets auf der C++-Seite schon weg sind, und
        # `show_document` schreibt in freigegebenen Speicher. Das war der
        # Absturz, der den Ubuntu-Runner eine Woche lang jedes Mal an
        # derselben Zeile umbrachte.
        #
        # Ausdrücklich getrennt und nicht dem Zerstören überlassen: `deleteLater`
        # trennt zwar auch, aber erst wenn es wirklich ausgeführt wird — und
        # ein `processEvents` allein tut das nicht.
        # Nichts verbunden oder Sitzung schon weg: beides ist das Ziel dieser
        # Zeile, also ist beides kein Fehler.
        with suppress(RuntimeError, TypeError):
            self.session.disconnect(self)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt name
        super().resizeEvent(event)
        self._fit_toolbar()

    def _fit_toolbar(self) -> None:
        """Kürzt die Werkzeugleiste, statt sie überlaufen zu lassen (D6).

        Passt die Leiste in ihrer breiten Form nicht mehr ins Fenster,
        verlieren die Knöpfe ihr Wort und behalten ihr Zeichen. Der Name geht
        dabei nicht verloren — er steht am ``QAction``, im Tooltip und im
        ``statusTip``, also dort, wo ihn Bildschirmleser und Statuszeile
        ohnehin lesen (`oberflaeche.md`, „Ein Zeichen darf allein stehen").

        **Zwei Schwellen, nicht eine.** Umgeschaltet wird bei knapp, zurück
        erst bei deutlich mehr Platz; sonst flackert die Leiste, wenn jemand
        das Fenster genau an der Grenze zieht. Dieselbe Vorsicht wie bei jeder
        Hysterese: Ein Rand, an dem zwei Antworten stimmen, ist ein Rand, an
        dem beide falsch aussehen.
        """
        room = self.toolbar.width()
        if room <= 0:
            return
        if self._toolbar_wide:
            wanted = self.toolbar.sizeHint().width()
            if wanted > room:
                # **Die Breite der Wortform merken, bevor sie verschwindet.**
                # Der erste Anlauf verglich den Platz mit der Wunschbreite des
                # *aktuellen* Stils — und die ist ohne Wörter kleiner. Die
                # Leiste schaltete deshalb sofort zurück, wurde wieder zu
                # breit, schaltete wieder um: gemessen sprang sie über sieben
                # Fensterbreiten viermal hin und her. Eine Hysterese, die ihre
                # eigene Wirkung misst, ist keine.
                self._toolbar_full_width = wanted
                self._toolbar_wide = False
                self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        elif room > self._toolbar_full_width + TOOLBAR_HYSTERESIS:
            self._toolbar_wide = True
            self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt name
        super().showEvent(event)
        self.spacemouse.start()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt name
        # Der Menühinweis versprach das seit jeher („Ungesichertes wird vorher
        # erfragt"), gefragt wurde nie: das Fenster schrieb eine automatische
        # Sicherung und ging zu. Wer die nicht kennt, hat seine Arbeit verloren.
        if not self._may_discard():
            event.ignore()
            return
        self.wait_for_workers()
        if self._remote is not None:
            self._remote.stop()
            self._remote = None
        self.spacemouse.stop()
        # Hier stand eine Sicherung. Sie lief **nach** der Frage darüber, und
        # dort kann nur noch stehen, wer gerade *Verwerfen* geklickt hat —
        # gespeichert hätte ``modified`` geräumt. Sie schrieb also genau den
        # Stand weg, den der Nutzer eben weggeworfen hatte, und das nächste
        # Öffnen bot ihn wieder an. Wer im Betrieb abstürzt, ist weiter
        # abgedeckt: der Zeitgeber sichert im Lauf (``AUTOSAVE_INTERVAL_MS``).
        # Wie das Fenster verlassen wird, so kommt es wieder — maximiert ist
        # nur die Vorgabe für den ersten Start.
        self.settings.window_geometry = bytes(self.saveGeometry().toHex().data()).decode("ascii")
        self.settings.circle_measure = circle_measure()
        save_settings(self.settings)
        self._usage.stop()
        # Erst hier steht fest, dass das echte Anwendungsfenster wirklich
        # endet. Der VTK-Plotter braucht seinen noch lebenden Qt-OpenGL-Kontext
        # zum Abbau; Qts später Prozessabriss kommt dafür zu spät und meldet
        # je nach Treiber unvollständige Framebuffer oder ``wglMakeCurrent``.
        # ``release()`` darf das ausdrücklich nicht tun: Es bedient auch den
        # Sprachwechsel, bei dem im selben Prozess schon das nächste Fenster
        # lebt.
        self.viewport.release_plotter()
        event.accept()


def _menu_entries(menu: Any) -> Iterator[Any]:
    """Jede anklickbare Zeile eines Menüs, Untermenüs eingeschlossen.

    Getrennt von :func:`_menu_lines`, weil das den **Weg** liefert und dies die
    **Handlung**: Wer wissen will, ob in einem Menü irgendetwas geht, braucht
    die Actions selbst und nicht ihre Beschriftungen.
    """
    for action in menu.actions():
        if action.isSeparator():
            continue
        sub = action.menu()
        if sub is not None:
            yield from _menu_entries(sub)
            continue
        yield action


def _menu_lines(menu: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    """Jede Zeile der Menüleiste mit ihrem Weg — Untermenüs eingeschlossen.

    Trennstriche fallen weg, ein Untermenü liefert seine Kinder statt sich
    selbst. Der Weg ist das, was in einer Liste aus hundert Zeilen den
    Unterschied macht: „Vorne" sagt nichts, „Kamera: Vorne" schon.
    """
    for action in menu.actions():
        if action.isSeparator():
            continue
        sub = action.menu()
        if sub is not None:
            yield from _menu_lines(sub, f"{path} > {action.text()}" if path else action.text())
            continue
        yield path, action


def registered_operations() -> list[OperationSpec]:
    """Kleine Hilfe, die die Befehlspalette benutzt."""
    return list(REGISTRY.all())


def _image_path(event: QDragEnterEvent | QDropEvent) -> Path | None:
    """Das abgelegte Bild, oder ``None``.

    Erkannt an der Endung, nicht am angebotenen Typ — Dateimanager
    beschriften verschieden, die Endung ist überall dieselbe. Die Liste ist
    dieselbe wie im Generierungsdialog und im Chat.
    """
    data = event.mimeData()
    if data is None or not data.hasUrls():
        return None
    for url in data.urls():
        name = url.toLocalFile()
        if name and name.lower().endswith(IMAGE_SUFFIXES):
            return Path(name)
    return None
