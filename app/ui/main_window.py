"""Das Hauptfenster (Bauplan §2.5).

Höchstens drei sichtbare Zonen: die Panels links, der Viewport in der Mitte,
Prüfbericht oder Chat rechts — und die rechte Seite klappt mit einer Taste ganz
weg. Betriebsarten gibt es nicht; es gibt einen Zustand, und der ist die Szene.

Das Menü steht auch hier nicht ausgeschrieben: es wird aus dem Register gebaut
— eine Operation erscheint also im Menü, in der Palette und auf der
Kommandozeile, sobald sie deklariert ist (§10).
"""

from __future__ import annotations

import time
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any, Final, cast

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from app.branding import APP_NAME, APP_VERSION, PROJECT_SUFFIX
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
    AppError,
    ExternalToolError,
    InternalError,
    OperationCancelled,
    UserError,
)
from app.core.export.handover import SliceOutcome
from app.core.export.writer import (
    ExportFormat,
    adhesion_margin,
    plan_export,
    safe_name,
    write_assembly,
    write_plan,
)
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
from app.core.geom.section import plane_through
from app.core.ingest.fetch import FetchedModel, check_url, fetch_model
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
    caveat_line,
    group_for_variant,
    group_is_flat,
    menu_tree,
    palette_entries,
    variant_members,
)
from app.core.scene import (
    EvaluationResult,
    OperationDraft,
    values_for,
    values_for_object,
)
from app.core.scene.cancel import CancelSignal
from app.core.scene.project import clear_autosave, find_recovery
from app.core.sketch.planes import frame_for_plane
from app.core.sketch.profile import curves_of
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
    ObjectId,
    Origin,
    Parameter,
    PlaneFrame,
    SliceResult,
    SourceOrigin,
    Stroke,
    Vec3,
)
from app.i18n import _, tr
from app.ui import first_run
from app.ui.analysis_bar import AnalysisBar, LayerBar
from app.ui.catalog import PartCatalog
from app.ui.chat import ChatPanel
from app.ui.command_palette import CommandPalette
from app.ui.dialogs import (
    AboutDialog,
    ActivationDialog,
    AskDialog,
    CalibrationDialog,
    KeyDialog,
    ParameterDialog,
    confirm_discard,
    confirm_unsaved,
    open_website,
    show_details,
    show_error,
)
from app.ui.explode_bar import ExplodeBar
from app.ui.facts import PrintFacts
from app.ui.generate_dialog import IMAGE_SUFFIXES, GenerateDialog, image_filter
from app.ui.header import HeaderBar, header_stylesheet
from app.ui.icons import icon, icon_name_for
from app.ui.install_dialog import InstallDialog
from app.ui.labels import (
    MENU_GROUPS,
    demo_line,
    display_unit,
    feature_label,
    kind_requirement,
    length,
    localised,
    spoiled_the_exact_body,
)
from app.ui.labels import area as area_label
from app.ui.labels import set_display_unit as set_length_unit
from app.ui.leash import Worker, WorkerLeash, weak_slot
from app.ui.loading import LoadingVeil, remaining_time
from app.ui.manual_window import ManualWindow
from app.ui.motion import switch
from app.ui.op_dialog import OperationDialog, SketchUseDialog
from app.ui.overlay import CARD_PADDING, OverlayHost, card_stylesheet
from app.ui.paint_bar import PaintBar
from app.ui.palette import ROLES
from app.ui.panels import (
    SEVERITY_MARKER,
    HistoryPanel,
    MeasurementLabel,
    ObjectTree,
    ParameterPanel,
    ReportPanel,
    collapsible,
    describe_selection,
)
from app.ui.pose_bar import PoseBar
from app.ui.print_settings_dialog import PrintSettingsDialog, remembered_setup
from app.ui.recipe_dialog import RecipeDialog
from app.ui.remote_server import RemoteServer, WindowBridge
from app.ui.sculpt_bar import SculptBar
from app.ui.section_bar import MeasureBar, SectionBar
from app.ui.session import AskRequest, Session
from app.ui.settings import UiSettings, save_settings
from app.ui.settings_dialog import SettingsDialog
from app.ui.shortcut_schemes import install_navigation_keys, shortcut_for
from app.ui.sketch_editor import SketchPanel, Surroundings, grid_step_for
from app.ui.split_bar import POINTS_NEEDED, SplitBar
from app.ui.start_screen import StartScreen, accepted_path, accepted_url
from app.ui.style import NORMAL, TIGHT, make_primary
from app.ui.support_dialog import SupportDialog, window_shot
from app.ui.survey import SurveyNotice, UsageClock
from app.ui.theme import apply_theme
from app.ui.tool_strip import ToolStrip, strip_title
from app.ui.tour import TourPanel
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
MODEL_SUFFIXES: Final = (
    ".stl",
    ".3mf",
    ".obj",
    ".glb",
    ".gltf",
    ".ply",
    ".off",
    ".step",
    ".stp",
    ".svg",
    ".dxf",
)
GCODE_SUFFIXES: Final = (".gcode", ".gco", ".g", ".nc")

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
LID_OPS: Final = frozenset({"create_lid", "create_screw_lid"})


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
    for name, ending in FORMAT_SUFFIX.items():
        if f"*{ending}" in chosen_filter:
            return name
    return "stl"


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


def _works_on(name: str, chosen: int, takes: int) -> str:
    """Woran die Operation arbeitet, wenn mehr gewählt ist als sie nimmt.

    Eine Operation nimmt so viele Körper, wie sie deklariert, und zwar in
    Klickreihenfolge (:func:`inputs_for`). Bei zwei gewählten Würfeln und
    *Bohrung setzen* bekam einer ein Loch und der andere nicht — im Dialog
    stand kein Wort dazu. Das ist kein Raten (Regel 21): die Regel steht nur
    nirgends, wo sie jemand liest.

    Leer, wo es nichts zu sagen gibt — und das ist der Normalfall.
    """
    if takes <= 0 or chosen <= takes or not name:
        return ""
    if takes == 1:
        return tr("Angewendet wird auf {name} — der zuerst gewählte von {count}.").format(
            name=name, count=chosen
        )
    return tr("Angewendet wird auf die {takes} zuerst gewählten von {count}.").format(
        takes=takes, count=chosen
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
        self._run_started: float | None = None
        """Wann der laufende Lauf begann — für die Restzeitschätzung (§2.8).

        Am Fenster und nicht am Balken: Der Balken kennt nur seinen Wert,
        und aus einem Wert allein lässt sich nicht hochrechnen."""
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
        """Das Ergebnis, das während des Aufbaus hereinkam — nachgeholt, sobald
        er fertig ist."""

        self._build_central()
        self._build_status_bar()
        self._build_menus()
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
        self.history_panel.bakeRequested.connect(self.bake_sculpt)

        # Ohne Streckfaktoren: die Karte ist so hoch wie ihr Inhalt, nicht so
        # hoch wie die Spalte. Ein Objektbaum mit einer Zeile soll eine Zeile
        # hoch sein — gestreckt hinterließ er dreihundert Pixel leere Fläche
        # über einem Modell, das daneben keinen Platz hatte.
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
        left_layout.addStretch(1)

        self.viewport = Viewport(self)
        self.viewport.measurementTaken.connect(self._on_measurement)
        self.section_bar = SectionBar(self)
        self.section_bar.sectionChanged.connect(self._on_section)
        self.measure_bar = MeasureBar(self)
        self.measure_bar.modeChanged.connect(self.viewport.set_measure_mode)
        self.measure_bar.clearRequested.connect(self.viewport.clear_measurements)
        self.transform_bar = TransformBar(self)
        self.transform_bar.gizmoToggled.connect(self.viewport.set_gizmo)
        self.transform_bar.snappingChanged.connect(self.viewport.set_snapping)
        self.viewport.transformDragged.connect(self._on_transform_dragged)
        self.viewport.sketchPointPicked.connect(self._on_sketch_point)
        self.viewport.sketchMenuAt.connect(self._on_sketch_menu)
        self.viewport.sketchPointHovered.connect(self._on_sketch_hover)
        self.viewport.faceDragged.connect(self._on_face_dragged)
        self.viewport.scaleDragged.connect(self._on_scale_dragged)
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
        self.paint_bar = PaintBar(self)
        self.paint_bar.paintingToggled.connect(self.viewport.set_painting)
        self.viewport.paintRequested.connect(self._on_paint)
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
            weak_slot(self, lambda view: view.measure_bar.mode.setCurrentIndex(0)),
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
            weak_slot(self, lambda view: view.transform_bar.gizmo.setChecked(False)),
            symbol="move",
            # „Am Griff im Bild ziehen" — und der Griff war aus. Wer ihn nicht
            # will, klickt den Haken weg; wer das Werkzeug öffnet, will bewegen.
            start=weak_slot(self, lambda view: view.transform_bar.gizmo.setChecked(True)),
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
        # Trennen ist das zweite Werkzeug, das das Modell ändert und nicht nur
        # die Ansicht — aus demselben Grund wie das Bemalen daneben: Es ist der
        # Handgriff, den ein Anfänger als Erstes braucht, sobald ein Teil nicht
        # auf die Platte passt, und ein Menüweg dahin wäre einer zu viel. Was
        # das Schließen zurücknimmt, ist die gezeichnete Linie; ein getrenntes
        # Teil bleibt getrennt und geht über Strg+Z zurück.
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
        # Bemalen ändert Materialslots und nicht bloß die Ansicht: das Schließen
        # beendet das Bemalen, nimmt aber nichts Gemaltes zurück.
        self.tools.add(
            "paint",
            tr("Bemalen"),
            self.paint_bar,
            weak_slot(self, lambda view: view.paint_bar.active.setChecked(False)),
            symbol="paint",
            hint=tr(
                "Slot wählen, dann auf die Fläche klicken. Das ändert das Modell, "
                "nicht nur das Bild — Strg+Z nimmt es zurück."
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
        sketch_row = QHBoxLayout(self.sketch_bar)
        sketch_row.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        self._sketch_hint = QLabel(
            tr("Zeichnen, dann Fertig — die Operation öffnet auf der Skizze."), self.sketch_bar
        )
        sketch_row.addWidget(self._sketch_hint, stretch=1)
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
        """Die Züge dieser Sitzung. Das Rückgängig des Editors läuft auf
        dieser Liste und nicht über den Verlauf: Der Verlauf bekommt die
        Sitzung als *eine* Transaktion, wenn sie fertig ist (Regel 16)."""

        done = QPushButton(tr("Fertig"), self.sketch_bar)
        make_primary(done)
        done.clicked.connect(weak_slot(self, lambda view: view.finish_sketch(keep=True)))
        discard = QPushButton(tr("Verwerfen"), self.sketch_bar)
        discard.clicked.connect(weak_slot(self, lambda view: view.finish_sketch(keep=False)))
        sketch_row.addWidget(done)
        sketch_row.addWidget(discard)
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
        # Ein geöffnetes Werkzeug macht die untere Zone dreimal so hoch. Die
        # Überlagerung setzt Geometrien, statt sie von einem Layout rechnen zu
        # lassen — sie muss also erfahren, dass sich der Bedarf geändert hat.
        # Ohne diese Verbindung blieb die Zone auf der Höhe der Knopfreihe,
        # und die Leiste des Werkzeugs lag über den Umschaltern: bei allen
        # sieben, von Schnitt bis Bemalen.
        self.tools.toolChanged.connect(weak_slot(self, lambda view: view.overlay.reflow()))
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
        # Derselbe Doppelgriff wie am Knopf der Statusleiste: abgebrochen wird,
        # was gerade läuft, und die Trennebenensuche hat ihr eigenes Verwerfen.
        self.veil.cancelRequested.connect(self.session.cancel)
        self.veil.cancelRequested.connect(self.session.cancel_split)
        self.overlay.set_veil(self.veil)

        self.start_screen = StartScreen(self)
        self.start_screen.newRequested.connect(self.start_empty)
        self.start_screen.browseRequested.connect(self.action_open)
        self.start_screen.openRequested.connect(self.open_path)
        self.start_screen.fileDropped.connect(self.open_path)
        self.start_screen.urlDropped.connect(self.download_model)
        self.start_screen.forgetRequested.connect(self._forget_recent)
        # Mit Kapitel: Der Knopf nennt es, also schlägt er es auf.
        self.start_screen.manualRequested.connect(
            weak_slot(self, lambda view: view.action_manual(manual.FIRST_MINUTES))
        )

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.start_screen)
        self.stack.addWidget(self.overlay)
        self.setCentralWidget(self.stack)

        self.object_tree.selectionChanged.connect(self._on_selection)
        self.object_tree.featureSelected.connect(self._on_feature_selected)
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
        self.object_tree.visibilityRequested.connect(self._on_visibility)
        self.object_tree.isolateRequested.connect(self._on_isolate)
        self.parameters.parameterEdited.connect(self._on_parameter_edited)
        self.parameters.addRequested.connect(self.action_add_parameter)
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
        self.progress.setVisible(False)
        self.cancel_button = QPushButton(tr("Abbrechen"), self)
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.session.cancel)
        self.cancel_button.clicked.connect(self._cancel_download)
        # Der Knopf gilt für alles, was gerade läuft — auch für die
        # Trennebenensuche, die ihr eigenes Verwerfen hat (§15.6).
        self.cancel_button.clicked.connect(self.session.cancel_split)

        # §2.5 nennt für die Statusleiste „Maße · Auswahl · Fortschritt ·
        # Warnungen". Material und Dauer gehören dazu: sie sind das Maß, das
        # beim Drucken zählt, und standen bisher allein hinter Strg+P.
        self.facts = PrintFacts(self)

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

        self.trial_line = QLabel("", self)
        self.trial_line.setVisible(False)

        bar = self.statusBar()
        bar.addWidget(self.measurements, 1)
        bar.addPermanentWidget(self.alert_button)
        bar.addPermanentWidget(self.trial_line)
        bar.addPermanentWidget(self.facts)
        bar.addPermanentWidget(self.status_message)
        bar.addPermanentWidget(self.progress)
        bar.addPermanentWidget(self.cancel_button)

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
        )
        self.open_action = self._add_action(
            file_menu,
            tr("Öffnen …"),
            QKeySequence.StandardKey.Open,
            self.action_open,
            tr("Ein gespeichertes Projekt öffnen (.p3d)."),
        )
        self.save_action = self._add_action(
            file_menu,
            tr("Speichern"),
            QKeySequence.StandardKey.Save,
            self.action_save,
            tr("Projekt mit Geometrie, Verlauf und Parametern in eine Datei schreiben."),
        )
        self._add_action(
            file_menu,
            tr("Speichern unter …"),
            QKeySequence.StandardKey.SaveAs,
            self.action_save_as,
            tr("Das Projekt unter einem anderen Namen ablegen."),
        )
        file_menu.addSeparator()
        self.import_action = self._add_action(
            file_menu,
            tr("Modell einfügen …"),
            "Ctrl+I",
            self.action_import,
            tr("Eine Modelldatei laden (STL, 3MF, OBJ, STEP). Eine Baugruppe kommt einzeln an."),
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
        )
        self.generate_action = self._add_action(
            file_menu,
            tr("Modell erzeugen …"),
            "Ctrl+G",
            self.action_generate,
            tr("Aus Text oder Bild ein Mesh erzeugen lassen — braucht ein laufendes ComfyUI."),
        )
        self._add_action(
            file_menu,
            tr("Bausteinkatalog …"),
            "Ctrl+K",
            self.action_catalog,
            tr("Alle Bausteine durchsehen: Mutternfalle, Rastnase, Scharnier und die anderen."),
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
        )
        self._add_action(
            file_menu,
            tr("Druckeinstellungen …"),
            "Ctrl+P",
            self.action_print_settings,
            tr("Schichten, Temperaturen, Farbe und Stützen einstellen — und slicen lassen."),
        )
        self._add_action(
            file_menu,
            tr("G-Code gegenprüfen …"),
            None,
            self.action_check_gcode,
            tr("Eine Datei aus dem Slicer lesen und ihre Zahlen neben die eigenen stellen."),
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
        )
        self.redo_action = self._add_action(
            edit_menu,
            tr("Wiederholen"),
            QKeySequence.StandardKey.Redo,
            self.action_redo,
            tr("Einen zurückgenommenen Schritt wieder anwenden."),
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
        own = bootstrap.user_operations()
        sections = {section.category: section for section in menu_tree(skip=own)}
        groups: dict[str, QMenu] = {}
        for title, categories in MENU_GROUPS:
            present = [sections[name] for name in categories if name in sections]
            if not present:
                continue
            group = self._menu(str(title))
            groups[str(title)] = group
            self._workspace_menus.append(group)
            flat = group_is_flat(present[0].category)
            for index, section in enumerate(present):
                # Eine Gruppe aus einer Kategorie braucht kein Untermenü — es
                # hieße genauso wie das Menü darüber. Und eine Gruppe, die
                # ganz hineinpasst, braucht auch keines: dann ist die
                # Zwischenebene ein Klick für nichts (siehe
                # ``_fits_without_submenus``).
                target = group
                if flat and index:
                    # Der Trennstrich hält die Kategorien auseinander, wo der
                    # Name des Untermenüs sie nicht mehr benennt. Er zählt in
                    # der Zeilengrenze nicht mit — genau dafür ist er da.
                    group.addSeparator()
                if not flat and len(present) > 1:
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
                tr("Alles einpassen"),
                "Home",
                self.viewport.reset_camera,
                tr("Rückt die Kamera so, dass die ganze Szene ins Bild passt."),
            )
        )
        self._add_action(
            view_menu,
            tr("Rechten Bereich zeigen"),
            "F9",
            self.action_toggle_right,
            tr("Verlauf, Parameter und Chat ein- oder ausblenden."),
        )
        view_menu.addSeparator()

        # Sechs Blöcke ohne Überschrift waren dreiundzwanzig Zeilen, durch
        # Trennstriche gegliedert — eine Liste, die man absucht (Konzept P15
        # §5). Was zusammengehört, bekommt jetzt seinen Namen und seine Ebene.
        display_menu = self._submenu(view_menu, tr("Darstellung"))
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
            self._display_actions.append(
                self._add_action(
                    display_menu,
                    label,
                    shortcut,
                    weak_slot(self, lambda view, key: view.viewport.set_display_mode(key), mode),
                    hint,
                )
            )
        display_menu.addSeparator()
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
            self._display_actions.append(
                self._add_action(
                    display_menu,
                    label,
                    None,
                    weak_slot(self, lambda view, key: view.viewport.set_shading(key), shading),
                    hint,
                )
            )
        display_menu.addSeparator()
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
            self._display_actions.append(
                self._add_action(
                    display_menu,
                    label,
                    shortcut,
                    weak_slot(
                        self, lambda view, key: view.viewport.set_projection(key), projection
                    ),
                    hint,
                )
            )

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
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        for theme, label, hint in (
            ("dark", tr("Dunkles Thema"), tr("Helle Geometrie auf dunklem Grund.")),
            ("light", tr("Helles Thema"), tr("Dunkle Geometrie auf hellem Grund.")),
        ):
            action = self._add_action(
                view_menu,
                label,
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
        for scheme, label, hint in (
            (
                "slicer",
                tr("Navigation: Cura"),
                # Der Hinweis stand hier andersherum, als das Schema arbeitet:
                # „links drehen, rechts schieben" beschreibt Bambu und Prusa,
                # nicht die Vorgabe aus §2.9.
                tr("Links wählt, rechts dreht, Umschalt und Ziehen schiebt."),
            ),
            (
                "orbit",
                tr("Navigation: Bambu, Orca, Prusa"),
                tr("Links dreht, rechts schiebt — die verbreitetste Aufteilung."),
            ),
            ("cad", tr("Navigation: CAD"), tr("Wie in einem CAD-Programm: Mittlere Taste dreht.")),
            ("blender", tr("Navigation: Blender"), tr("Wie in Blender.")),
        ):
            action = self._add_action(
                navigation_menu,
                label,
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
            tr("Sprache, Drucker, Material und die externen Programme noch einmal einstellen."),
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
            tr("Was sich in dieser und den vorigen Fassungen geändert hat."),
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
            tr("Über Solidon"),
            None,
            self.action_about,
            tr("Version, Rechteinhaber und die verwendeten Fremdbibliotheken."),
        )

        toolbar = QToolBar(tr("Werkzeuge"), self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        # Nur die Zeichen, die Wörter am Zeiger. Acht beschriftete Knöpfe
        # brauchten 703 Pixel und drängten die Kopfzeile mit Projekt, Maßen,
        # Drucker und Material an den rechten Rand; ohne Text sind es 310.
        # Regel 18 verlangt eine zweite Kodierung neben der Farbe, nicht eine
        # Beschriftung neben jedem Zeichen — und Blatt, Ordner und Diskette
        # sind derselbe Fall wie Linie und Kreis im Skizzeneditor: Bilder, auf
        # die sich die Welt geeinigt hat (``app/ui/icons.py``, Abschnitt
        # Zeichenwerkzeuge). Der Name bleibt am ``QAction`` und damit im
        # Barrierefreiheitsbaum.
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        # Vier der sieben haben ein Menüpendant; von ihm kommen Satz und
        # Kürzel (``source``). Die drei anderen gibt es nur hier und tragen
        # ihren Satz selbst.
        for symbol, label, slot, source, own_hint in (
            ("new", tr("Neu"), self.action_new, self.new_action, ""),
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
            # Merkzettel für ``_with_name``: dieser Knopf zeigt seinen Namen
            # nicht selbst.
            action.setProperty("wordless", True)
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
            )
            if key:
                self._scope_shortcut(action, key)
            self._variant_actions[group.members[0]] = action

    def _add_action(
        self, menu: Any, label: str, shortcut: Any, slot: Any, hint: str = ""
    ) -> QAction:
        """Ein Menüeintrag mit dem Satz, der sagt, was er tut.

        Der Hinweis steht an zwei Stellen, weil ihn zwei Arten von Leuten
        suchen: in der Statusleiste, wo er beim Durchgehen mitläuft, und als
        Tooltip, wo er beim Zögern erscheint. Ohne beides ist ein Menü mit
        vierzehn Einträgen eine Liste von Vermutungen.
        """
        action = QAction(label, self)
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
        action.triggered.connect(lambda _checked=False, call=slot: call())
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

        # Welcher Bauart die Auswahl ist — das Menü fragte bisher nur, wie
        # viele Objekte darin liegen. „Verrunden" war damit bei einem Netz
        # anklickbar, und der Satz „Der gewählte Körper ist ein Netz" kam erst
        # nach dem ausgefüllten Dialog (Regel 19: keine Sackgassen).
        kinds = self._kinds_of_selection(result)

        for name, action in self._op_actions.items():
            spec = REGISTRY.get(name)
            if locked or gesturing:
                action.setEnabled(False)
            elif spec.takes_whole_scene:
                action.setEnabled(objects > 0)
            elif spec.consumes:
                fits = not spec.requires_kind or all(kind == spec.requires_kind for kind in kinds)
                action.setEnabled(chosen >= spec.consumes and fits)
            else:
                action.setEnabled(True)
            self._lock_hint(action, locked)
            self._kind_hint(action, spec, kinds, locked, objects, chosen)

        # Dieselbe Regel für die Werkzeugzeile unten. Sie stand dem Anfänger
        # näher als jedes Menü und bot auf einer leeren Szene weiter Messen,
        # Bewegen, Analyse, Schichten und Bemalen an — jedes davon braucht
        # einen Körper, und keines sagte das.
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

    def _kind_hint(
        self,
        action: QAction,
        spec: OperationSpec,
        kinds: list[str],
        locked: bool,
        objects: int = 0,
        chosen: int = 0,
    ) -> None:
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
        """
        if locked:
            return
        stored = action.property("tip_before_kind")
        reason = self._reason_locked(spec, kinds, objects, chosen)
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
        return kind_requirement(spec, kinds, spoiled_the_exact_body(self.session.last_result))

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

    @staticmethod
    def _button_tip(label: str, source: QAction | None, own_hint: str) -> str:
        """Was am unbeschrifteten Knopf steht: Name, Kürzel, Zweck.

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
        """Der Grund, dem Namen des Knopfes vorangestellt — aber nur dort, wo
        der Knopf ihn nicht selbst zeigt.

        Die Werkzeugleiste über dem Fenster steht ohne Beschriftung; ihr
        Tooltip ist die Stelle, an der ihr Name steht. Ein Grund, der ihn
        überschreibt, lässt ein Bild und einen Satz zurück, die nichts
        miteinander zu tun scheinen. Im Menü steht der Name daneben — dort
        bleibt der Grund allein.

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
        """
        stored = action.property("tip_before_lock")
        if locked:
            if stored is None:
                action.setProperty("tip_before_lock", action.statusTip())
            reason = self._with_name(
                action,
                tr(
                    "Der Testzeitraum ist abgelaufen — dafür braucht Solidon einen "
                    "Lizenzschlüssel (Hilfe → Solidon freischalten …)."
                ),
            )
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
        if state.in_demo and state.days_left > 0:
            message = demo_line(state)
        elif state.in_trial and state.days_left < 3:
            message = tr("Testzeitraum: noch {days} Tage — Hilfe → Solidon freischalten …").format(
                days=state.days_left
            )
        self.trial_line.setText(message)
        self.trial_line.setVisible(bool(message))
        self._trial_message = message

    def _connect_session(self) -> None:
        self.session.sceneChanged.connect(self._on_scene)
        self.session.projectChanged.connect(self._on_project)
        self.session.progressChanged.connect(self._on_progress)
        self.session.busyChanged.connect(self._on_busy)
        self.session.askRequested.connect(self._on_ask)
        self.session.failed.connect(self._on_error)
        # Gebundene Methode, kein Lambda: Der Sender ist ein Kind dieses
        # Fensters, und ein Lambda schlösse den Ring aus `.claude/rules`.
        self.session.backendChanged.connect(self._refresh_chat_availability)
        self.session.proposalReady.connect(self._on_proposal)
        self.session.agentBusyChanged.connect(self._on_agent_busy)
        self.session.agentProgress.connect(self._on_agent_progress)
        self.session.splitBusyChanged.connect(self._on_split_busy)
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

        Mit Wartezeiger: Gelesen wird hier synchron — die Projektdatei über
        ``load``, das Modell über ``path.read_bytes()``. Die Ladeanzeige deckt
        das **nicht** ab: sie hängt am Fortschritt der Auswertung, und der
        beginnt erst, wenn die Datei gelesen ist; ihre 200 ms Verzögerung
        kommen obendrauf. Bis dahin stünde ein Fenster ohne jede Auskunft da
        (§2.8).
        """
        if path.suffix.lower() == PROJECT_SUFFIX and not self._may_discard():
            return
        try:
            with waiting():
                if path.suffix.lower() == PROJECT_SUFFIX:
                    # Was zum vorigen Projekt zu sagen war, gilt für dieses
                    # nicht: „Exportiert: dose.3mf" über einer gerade
                    # geöffneten Datei wäre eine Auskunft über etwas anderes.
                    self.announce("")
                    self.session.open_project(path)
                    self.settings.remember(path)
                    save_settings(self.settings)
                else:
                    if self.stack.currentWidget() is self.start_screen:
                        self.session.start_new(self.settings.printer, self.settings.material)
                    self.session.import_model(path)
            if path.suffix.lower() == PROJECT_SUFFIX:
                # Beide fragen etwas, und beide erst außerhalb des
                # Wartezeigers: ein Fenster, das um Antwort bittet und dabei
                # „bitte warten" zeigt, sagt zweierlei.
                self._offer_recovery(path)
                self._offer_tour(path)
        except AppError as error:
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
        try:
            with waiting():
                if self.stack.currentWidget() is self.start_screen:
                    # Vom Startbildschirm aus ist Einfügen ein Anfang, kein
                    # Nachtrag: ein frisches Projekt mit Drucker und Material
                    # aus den Einstellungen, wie es open_path beim Ablegen
                    # einer Datei auch anlegt.
                    self.session.start_new(self.settings.printer, self.settings.material)
                self.session.import_model(Path(name))
        except AppError as error:
            show_error(error, self)

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
            tr("Adresse der Modelldatei (STL, 3MF, OBJ, STEP …):"),
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
        self.status_message.setText(tr("Modell herunterladen …"))
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self._leash.start(worker)

    def _on_download_progress(self, share: float, label: str) -> None:
        """Wie weit die Datei ist. Ein Server ohne Längenangabe liefert
        ``0.0`` — dann läuft der Balken endlos, statt auf null zu stehen."""
        if share > 0.0:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(share * 100))
        else:
            self.progress.setRange(0, 0)
        self.status_message.setText(label)

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
            self.session.start_new(self.settings.printer, self.settings.material)
        self.session.import_payload(
            fetched.name,
            fetched.payload,
            origin=SourceOrigin(url=fetched.url, retrieved=fetched.retrieved),
        )
        self._show_start_screen(False)
        self.announce(f"{tr('Geladen')}: {fetched.name}")

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

    def _anything_cancellable(self) -> bool:
        """Ob der Abbrechen-Knopf gerade etwas hätte, das er abbricht.

        Getrennt vom Balken: Der Export läuft mit Balken und ohne Abbrechen
        (sein Docstring begründet das), und ein Knopf, der nichts täte, wäre
        schlimmer als keiner.
        """
        return (
            self.session.busy or self.chat.busy or self.session.split_running or self._downloading
        )

    def _progress_idle(self) -> None:
        """Die Anzeige zurück in den Ruhezustand — aber nur, wenn nicht schon
        etwas anderes rechnet.

        Gemeinsam für alle Arbeiter, die den Balken der Statusleiste selbst
        anschalten (Download, Export): jeder von ihnen muss ihn wieder
        loswerden, und keiner darf dabei den laufenden Auswertungsbalken
        ausknipsen.
        """
        self.progress.setRange(0, 100)
        if not self._anything_running():
            self.progress.setVisible(False)
        self.status_message.setText(self._announcement)

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
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result_mesh is None:
            return
        self.session.add_generated(dialog.result_mesh)

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
        self.announce(
            f"{tr('Geteilt')}: {len(applied.object_ids)} · {len(applied.fits)} {tr('Passungen')}"
        )

    def bake_sculpt(self, op_id: int) -> None:
        """Den Stand einer Formsitzung festschreiben — mit Nachfrage.

        **Die einzige Bestätigung vor einer Handlung.** (Daneben gibt es zwei
        Fragen anderer Art: das Wiederherstellungs-Angebot nach einem Absturz
        und Speichern/Verwerfen beim Schließen — die eine ist ein Angebot,
        die andere schützt Unwiederbringliches.) Regel 19 verbietet
        Bestätigungsdialoge vor rücknehmbaren Handlungen, und fast alles hier
        ist rücknehmbar; diese Handlung ist es nicht folgenlos, denn danach
        lässt sich an den Zügen nichts mehr ändern. Deshalb steht im Dialog
        auch nicht „Sind Sie sicher", sondern was danach nicht mehr geht
        (Entscheidung D, §2.7).
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

    def action_undo(self) -> None:
        # Läuft eine Formsitzung, nimmt Strg+Z den letzten Zug zurück und
        # nicht die Operation davor. Dieselbe Trennung wie beim
        # Skizzeneditor: Der Editor hat sein eigenes Rückgängig, der Verlauf
        # bekommt die Sitzung als eine Transaktion (Regel 16).
        if self.undo_sculpt_stroke() or self.undo_bone():
            return
        self.session.undo()

    def action_redo(self) -> None:
        self.session.redo()

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
        InstallDialog(self).exec()

    def _offer_slicer_setup(self, dialog: PrintSettingsDialog) -> None:
        """Aus den Druckeinstellungen in die Liste der zusätzlichen Programme.

        Und zurück: Der Dialog sieht danach noch einmal nach, ob ein Slicer da
        ist — sonst wäre der Weg eine Sackgasse mit Umweg.
        """
        self.action_install_extras()
        dialog.recheck_slicer()

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
        # Regel 17: „Kein Slicer eingerichtet" sagte, was fehlt, und bot nichts
        # an — an der Stelle, an der jemand gerade slicen wollte. Von hier
        # führt der Weg in die Liste, und danach sieht der Dialog neu nach.
        dialog.setupRequested.connect(lambda: self._offer_slicer_setup(dialog))
        dialog.exec()
        self._settings_dialog = None

        # Die Einstellungen gehören zum Projekt, die Stufe und die Slicer-Wahl
        # zur Anwendung (§29). Getrennt gespeichert, weil ein Projekt auf einem
        # anderen Rechner geöffnet wird, wo ein anderer Slicer liegt.
        self.session.set_print_settings(dialog.settings)
        self.settings.print_quality = dialog.settings.quality
        save_settings(self.settings)
        # Ohne das blieb jede Öffnung samt Profilliste am Fenster hängen —
        # bei der Orca-Familie einige tausend Einträge je Aufruf.
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
        for outcome in outcomes:
            self.report.add_findings(outcome.findings)
        self._compare_totals(gcode.combine([entry.metrics for entry in outcomes]))
        self._focus_report()
        self.announce(
            f"{tr('Geslicet')}: {outcomes[0].gcode_path.name}"
            if len(outcomes) == 1
            else f"{tr('Geslicet')}: {len(outcomes)} {tr('Platten')}"
        )

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

        self.report.add_findings(findings)
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
        # GLB steht am Ende und nicht bei den Druckformaten: es ist das
        # Format zum Zeigen, nicht zum Drucken — Farben und Name reisen mit,
        # jeder Betrachter öffnet es, kein Slicer will es.
        offered = ["STL (*.stl)", "3MF (*.3mf)", "OBJ (*.obj)", "PLY (*.ply)", "GLB (*.glb)"]
        # STEP hält Flächen und Kanten fest, und ein Netz hat keine. Der
        # Schreiber sagt das mit einem guten Satz — nur sagte er ihn erst,
        # nachdem der Nutzer Format, Ordner und Namen gewählt hatte. Bei
        # Mesh-Projekten, und das sind die meisten, konnte der Eintrag nie zu
        # etwas führen. Angeboten wird er jetzt, wenn wenigstens ein Körper
        # ihn tragen kann.
        if any(entry.kind == "brep" for entry in objects):
            offered.append("STEP (*.step)")
        filters = ";;".join(offered)
        name, chosen_filter = QFileDialog.getSaveFileName(
            self, tr("Exportieren"), f"{stem}.stl", filters
        )
        if not name:
            return
        target = Path(name)
        export_format: ExportFormat = _format_of(target, chosen_filter)
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
            # niemand gemeint hat. ``None`` heißt „Dialog nie geöffnet", nicht
            # „keine Einstellungen" — dann gilt die Auflösung aus Stufe,
            # Material und Drucker, wie überall sonst.
            settings=self.session.project.document.print_settings
            or print_settings.resolve(self.session.profile),
            ui_settings=self.settings,
            material=self.session.profile.material.id,
        )
        self._export_worker = worker
        worker.done.connect(self._export_done)
        worker.failed.connect(self._export_failed)
        # **Und das Unerwartete.** Der Menüeintrag ist gesperrt, solange
        # geschrieben wird; eine Ausnahme, die den Thread abriss, ließ ihn für
        # den Rest der Sitzung gesperrt — der Kunde konnte nicht mehr
        # exportieren und erfuhr nicht, warum.
        worker.crashed.connect(lambda detail: self._export_failed(InternalError(detail=detail)))
        worker.finished.connect(lambda done=worker: self._export_worker_done(done))
        self.status_message.setText(tr("Exportiert wird … {name}").format(name=target.name))
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        # Solange geschrieben wird, führt der Menüeintrag nirgendwo hin: ein
        # zweiter Lauf schriebe in dieselben Dateien, und welcher von beiden
        # gewinnt, entschiede die Reihenfolge zweier Threads.
        self._update_actions()
        self._leash.start(worker)

    def _export_done(self, written: list[Path], findings: list[Finding]) -> None:
        """Was geschrieben wurde, und was dabei aufgefallen ist (§29)."""
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
        attempt = self._export_attempt
        if attempt is not None:
            self._write_failure = _WriteFailure(
                again=partial(self._start_export, attempt[0], attempt[1]),
                elsewhere=self.action_export,
            )
        show_error(error, self)

    def _after_write_failure(self, way: str) -> None:
        """Den zweiten Anlauf gehen — dieselbe Datei oder ein anderer Ort (§2.7)."""
        failure = self._write_failure
        if failure is None:
            return
        (failure.again if way == "again" else failure.elsewhere)()

    def _export_worker_done(self, worker: Any) -> None:
        if self._export_worker is worker:
            self._export_worker = None
            self._progress_idle()
            self._update_actions()
        self._hold_until_done(worker)

    def action_catalog(self) -> None:
        """§24.3: die Bibliothek, die man sehen kann. Einen Baustein zu wählen
        führt seine Operation aus.
        """
        catalog = PartCatalog(self)
        catalog.set_can_save(*self._recipe_readiness())
        catalog.set_can_insert(*self._insert_readiness())
        catalog.saveRequested.connect(lambda: self._save_as_part(catalog))
        if catalog.exec() != PartCatalog.DialogCode.Accepted:
            return
        name = catalog.chosen()
        if name:
            self.run_operation(REGISTRY.get(part_op_name(name)))

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

    def _save_as_part(self, catalog: PartCatalog) -> None:
        """Öffnet den Rezeptdialog über dem Katalog (Konzept §16, Schritt 4 und 5).

        **Genommen wird der ganze Stapel, nicht ein Ausschnitt daraus.** Das
        Konzept spricht von einem Ausschnitt, und ``capture`` nimmt dafür
        ``op_ids`` — aber der Verlauf kennt heute keine Mehrfachauswahl, und
        einen Bereich zu erfinden, den niemand wählen kann, wäre eine
        Bedienung, die es nicht gibt. Wer sein Teil als Baustein ablegt, hat es
        ohnehin gerade gebaut. Die Teilauswahl ist ein eigener Schritt und
        steht als solcher im Register.
        """
        result = self.session.last_result
        document = self.session.project.document
        if result is None:
            return
        dialog = RecipeDialog(
            document,
            dict(self.session.project.sources),
            # **Die IDs der Schritte, nicht ihre Plätze.** ``capture`` filtert
            # nach ``Operation.id``, und die zählt ab eins; ``enumerate`` ab
            # null. Mit Indizes fiel der **letzte** Schritt jedes Stapels
            # still aus dem Rezept — beim Weg-2-Halter die Versteifung.
            # Gefunden am 25.08.2026 im echten Fenster: Das gespeicherte
            # Rezept trug drei von vier Schritten, und der Bereichstest war
            # trotzdem grün, denn drei Schritte ergeben auch einen Körper.
            tuple(op.id for op in document.ops),
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
        KeyDialog(parent=self).exec()
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
        self.set_display_unit(self.settings.display_unit)

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
        """
        set_length_unit(unit)  # type: ignore[arg-type]
        self.measurements.set_unit(unit)  # type: ignore[arg-type]
        self.object_tree.set_unit(unit)  # type: ignore[arg-type]
        self._on_selection(self.object_tree.selected())
        self._update_header()
        # Die Merkmalsbeschriftungen in der Überlagerung schreiben Längen ohne
        # eigene Einheit; sie brauchen nur den Anstoß, es neu zu tun.
        self.viewport.refresh_labels()

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
            "edit.settings": (tr("Einstellungen …"), "Ctrl+,", self.action_settings),
            "edit.undo": (tr("Rückgängig"), "Ctrl+Z", self.action_undo),
            "edit.redo": (tr("Wiederholen"), "Ctrl+Y", self.action_redo),
            "edit.add_parameter": (
                tr("Parameter anlegen …"),
                "",
                self.action_add_parameter,
            ),
            "edit.auto_split": (tr("Automatisch teilen …"), "", self.action_auto_split),
            "view.fit": (tr("Alles einpassen"), "Home", self.viewport.reset_camera),
            "view.toggle_right": (tr("Rechten Bereich zeigen"), "F9", self.action_toggle_right),
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
        das Handbuch, „Alles einpassen" — kann immer.
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
        bauen, nur als Ebenenname des Kerns (``feature:<id>``). Ob die Fläche
        als Zeichenebene taugt, entscheidet danach ``choose_plane`` — hier
        wird nur weitergegeben, was der Nutzer schon gesagt hat.
        """
        if self.selected_feature_kind() != "face":
            return ""
        return f"feature:{self.object_tree.selected_feature()}"

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
        for entry in result.scene.objects.values():
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
                        feature_id,
                        label,
                        (float(normal[0]), float(normal[1]), float(normal[2])),
                    )
                )
        found.sort(key=lambda row: -row[0])
        return [(feature_id, label, normal) for _area, feature_id, label, normal in found]

    # --- Skizzenmodus (§30.1 Stufe zwei) ----------------------------------------

    def _escape(self) -> None:
        """Escape verlässt, was gerade offen ist — ein Werkzeug oder die Skizze.

        Die Skizze zuerst: sie liegt vor der Ansicht, und wer zeichnet, meint
        mit Escape sie und nicht eine Leiste darunter. Verworfen wird dabei
        nichts Gerechnetes — die Skizze war noch keine Operation.
        """
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

    def start_sketch(self, op_name: str, text: str = "", plane: str = "") -> None:
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
        ``feature:<id>`` aus einem Klick auf eine Fläche. Sie wird über
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
        panel = SketchPanel(text, self._parameter_values(), self, self._sketch_surroundings())
        if plane and not panel.choose_plane(plane):
            self.announce(tr("Diese Fläche steht nicht mehr zur Verfügung."))
        self._sketch_panel = panel
        self._sketch_target = op_name
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
        # Die Fangmarke: Der Canvas kennt den Ort, an dem ein Klick wirklich
        # landet (Raster **und** „vorhandener Punkt schlägt Raster"), die
        # Ansicht kann ihn zeigen. Ihn im Viewport nachzurechnen wäre die
        # zweite Zahl für dieselbe Sache — der Fehler, den d6335c1 schon
        # einmal behoben hat. Ohne die Marke sitzt der Punkt bis zu einem
        # halben Rasterschritt neben dem Zeiger, und genau das hat Robert am
        # 24.08.2026 als „die Klicks sind woanders" gemeldet.
        panel.pointerMoved.connect(self._on_sketch_pointer)
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
        panel.plane_choice.currentIndexChanged.connect(self._sketch_plane_changed)
        self._redraw_sketch()
        # Der Startbildschirm liegt vor dem Arbeitsbereich, solange nichts
        # offen ist — und zu zeichnen beginnen ist genau der Fall, in dem noch
        # nichts offen ist (Weg 2, §2.2). Ohne diese Zeile meldete die
        # Statusleiste den Modus, und zu sehen war der Startbildschirm.
        self._show_start_screen(False)
        self.tools.close_tool()
        # Die Ansichtswerkzeuge tun im Skizzenmodus nichts — Schnitt, Messen
        # und Bemalen brauchen einen Körper und ein Bild. Sie standen dort als
        # zweite Leiste unter der des Editors und boten sieben Umschalter an,
        # von denen keiner etwas bewirkte.
        self.tools.setVisible(False)
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
        frame = self._sketch_frame()
        self.viewport.set_sketching(frame)
        if frame is not None:
            self.viewport.view_on_plane(frame)
        self._update_sketch_hint()
        self._redraw_sketch()

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
        panel.canvas.place_on_plane(place)

    def _on_sketch_pointer(self, x: float, y: float) -> None:
        """Der Canvas hat den Zeiger gefangen — die Ansicht zeigt, wohin.

        Die zwei Zahlen sind schon die gefangenen; hier wird nichts mehr
        gerechnet, nur gezeigt (:meth:`Viewport.show_sketch_cursor`).
        """
        self.viewport.show_sketch_cursor((x, y))

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
        place = panel.plane_choice.currentText()
        # Der Zusatz wird über den **bekannten** Schlüssel entfernt, nicht
        # über eine Klammersuche im übersetzten Text: „(XY)" gehört zum Titel,
        # „  (1)" ist das Kürzel — eine Übersetzung, die selbst auf eine
        # Klammer endet, hätte den Hinweis sonst still zerschnitten.
        from app.ui.sketch_editor import PLANE_KEYS

        key = PLANE_KEYS.get(str(panel.plane_choice.currentData() or ""), "")
        suffix = f"  ({key})"
        if key and place.endswith(suffix):
            place = place[: -len(suffix)]
        source = (
            tr(
                "Zeichenebene: {place} · Zeichnen, dann Fertig — "
                "die Operation öffnet auf der Skizze."
            )
            if self._sketch_target
            else tr(
                "Zeichenebene: {place} · Zeichnen, dann Fertig — "
                "dann fragt Solidon, was daraus wird."
            )
        )
        self._sketch_hint.setText(source.format(place=place))

    def _sketch_frame(self) -> PlaneFrame | None:
        """Der Rahmen der Ebene, auf der gerade gezeichnet wird."""
        panel = self._sketch_panel
        if panel is None:
            return None
        return self._plane_frame(panel.canvas.sketch.plane)

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
        self.viewport.show_sketch(kurven, frame, step, SKETCH_GRID_REACH)

    def finish_sketch(self, keep: bool = True) -> None:
        """Den Modus verlassen. Mit ``keep`` öffnet die Operation auf der
        gezeichneten Skizze, sonst wird sie verworfen.
        """
        panel = self._sketch_panel
        target = self._sketch_target
        if panel is None:
            return
        text = panel.sketch_text() if keep else ""
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
        self.viewport.set_sketching(None)
        # Die Maßeingabe abklemmen und das Feld heimholen, **bevor** das Panel
        # stirbt: Die Ansicht hielte sonst Rückrufe auf einen toten Canvas,
        # und das Feld bliebe als Waise über dem Bild stehen.
        self.viewport.set_sketch_entry(None, None)
        panel.canvas.reclaim_measure_field()
        panel.sketchChanged.disconnect(self._redraw_sketch)
        panel.pointerMoved.disconnect(self._on_sketch_pointer)
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
        self.sketch_bar.setVisible(False)
        self.statusBar().clearMessage()
        self._update_actions()
        if keep and text:
            if target:
                self.run_operation(REGISTRY.get(target), given={_sketch_param(target): text})
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
        self._sculpt_strokes = []
        self.viewport.set_sculpting(True, self.sculpt_bar.radius.value_mm())
        self.tools.close_tool()
        self.tools.setVisible(False)
        self.sculpt_bar.setVisible(True)
        self.sculpt_bar.show_count(0, 0)
        self.sculpt_bar.show_warning(self._sculpt_resolution_hint(mesh), refinable=True)
        self._update_actions()
        self.statusBar().showMessage(tr("Formen — Escape oder Fertig beendet die Sitzung."))

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
            tr("{zahl} Stellen dünner als {maß}")
            .replace("{zahl}", str(thin))
            .replace("{maß}", length(minimum))
        )

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
        self._armature_bones = []
        self._armature_head = None
        self._armature_parent = ""
        self.viewport.set_boning(True)
        self.tools.close_tool()
        self.tools.setVisible(False)
        self.pose_bar.setVisible(True)
        self.pose_bar.show_state(0, pending=False, chain=True)
        self._update_actions()
        self.statusBar().showMessage(tr("Skelett setzen — Escape oder Fertig beendet."))

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
            self.pose_bar.show_state(len(self._armature_bones), pending=True, chain=True)
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
        self.pose_bar.show_state(len(self._armature_bones), pending=False, chain=True)

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
        self.pose_bar.show_state(len(self._armature_bones), pending=False, chain=True)
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
        self._armature_target = None
        self._armature_bones = []
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
        self.run_operation(
            REGISTRY.get("pose_armature"), given={"armature": armature_to_text(bones)}
        )

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
        dialog = SketchUseDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.chosen():
            name = dialog.chosen()
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
            commands[name][2]()
            return
        self._run_palette_choice(name)

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
        """
        action = self._op_actions.get(name)
        if action is None or action.isEnabled():
            return True, ""
        hint = action.toolTip()
        spec = REGISTRY.get(name)
        if hint and hint != str(spec.doc):
            # `_lock_hint`/`_kind_hint` haben einen Grund gesetzt.
            return False, hint
        return False, tr("Dafür braucht es eine passende Auswahl.")

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

    def _on_transform_dragged(self, steps: Any) -> None:
        """Ein Ziehen, eine Transaktion — in einem Schritt zurückgenommen
        (§18.11, §15.5).
        """
        selected = self.object_tree.selected()
        if selected is None:
            return
        drafts: list[OperationDraft] = []
        if steps.moves:
            drafts.append(
                OperationDraft(
                    op="translate_object",
                    inputs=(selected,),
                    params={"dx": steps.offset[0], "dy": steps.offset[1], "dz": steps.offset[2]},
                )
            )
        if steps.turns:
            drafts.append(
                OperationDraft(
                    op="rotate_object",
                    inputs=(selected,),
                    params={"axis": steps.axis, "angle": steps.angle},
                )
            )
        if steps.resizes:
            drafts.append(
                OperationDraft(
                    op="scale_object", inputs=(selected,), params={"factor": steps.scale}
                )
            )
        if drafts:
            self.session.apply(_("Direkt bewegt"), drafts)

    def _on_scale_dragged(self, factor: float) -> None:
        """Ein Zug am Skalierwürfel wird eine Operation (§18.11, Regel 2).

        Gleichmäßig und um den Schwerpunkt — genau das, was die Vorschau
        während des Zugs gezeigt hat. Wer achsweise oder um einen anderen
        Punkt skalieren will, nimmt den Dialog; der Zug ist für das
        Gleichmäßige da.
        """
        selected = self.object_tree.selected()
        if selected is None:
            return
        self.session.apply(
            REGISTRY.get("scale_object").title,
            [
                OperationDraft(
                    op="scale_object", inputs=(selected,), params={"factor": float(factor)}
                )
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

    def _show_map(self, analysis: Any, object_id: ObjectId) -> None:
        self.viewport.set_analysis_map(analysis, object_id if analysis else None)
        self.analysis_bar.show_legend(analysis, self._feature_names())

    def _on_layer_changed(self, index: int) -> None:
        """Durch die Schichtanalyse fahren (§18.10) — Geometrie, keine
        Werkzeugwege.
        """
        object_id = self.object_tree.selected()
        if index < 0 or object_id is None:
            self.viewport.set_layer(None)
            return
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

    def _on_finding_activated(self, finding: Finding) -> None:
        """Eine Warnung anklicken, die Stelle sehen: der kürzeste Weg vom Problem
        zum Ort (§18.4).
        """
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

        if target is not None:
            self.viewport.fly_to(target)

    # --- der Agent (§26) --------------------------------------------------------

    def _on_request_sent(self, request: str) -> None:
        """Ein Zug. Die Auswahl reist mit, sonst heißt „dieses Loch"
        nichts (§26.1).
        """
        selected = self.object_tree.selected()
        feature = self.object_tree.selected_feature()
        selection = (selected, feature or "") if selected else None
        self.session.propose_async(request, selection)

    def _on_agent_busy(self, busy: bool) -> None:
        """Ein Zug dauert zehn bis sechzig Sekunden — §2.8 verlangt dafür
        Fortschritt **und** Abbrechen.

        Bisher gab es nur den Satz „Der Agent denkt nach.": der Knopf hing
        allein an der Auswertung, und ein Zug, der zu lange lief, war nur über
        das Schließen des Fensters zu beenden.
        """
        self.chat.set_busy(busy)
        self.status_message.setText(tr("Der Agent denkt nach.") if busy else self._announcement)
        if busy:
            # Wie viele Schritte ein Zug braucht, steht vorher nicht fest —
            # ein Balken ohne Ende sagt „es läuft", ohne etwas zu versprechen.
            self.progress.setRange(0, 0)
            self.progress.setVisible(True)
            self.cancel_button.setVisible(True)
            return
        # Erst aufräumen, dann fragen: ``isVisible()`` vor dem Ausblenden
        # gelesen hielt den Abbrechen-Knopf nach jedem Agentenzug am Leben —
        # ohne laufende Rechnung, bis das nächste busyChanged ihn zufällig
        # mitnahm. Der Nachbar ``_on_split_busy`` machte es richtig vor.
        if not self._anything_running():
            self.progress.setRange(0, 100)
            self.progress.setVisible(False)
        self.cancel_button.setVisible(self._anything_cancellable())

    def _on_agent_progress(self, step: int, label: str) -> None:
        """Was der Zug gerade tut, statt nur dass er läuft (§2.8).

        „Der Agent denkt nach." war die ganze Auskunft über zehn bis sechzig
        Sekunden — jetzt steht da, welcher Schritt läuft und welches Werkzeug
        (Konzept Agent-Vertiefung 4.1). Der Deckel dahinter, damit erkennbar
        ist, dass die Zahl nicht ins Leere wächst.
        """
        if not self.chat.busy:
            return
        self.status_message.setText(f"{tr('Schritt')} {step}/{MAX_STEPS} — {label}")

    def _on_split_busy(self, busy: bool) -> None:
        """Die Trennebenensuche läuft — Fortschritt und Abbrechen wie bei
        jedem anderen Lauf über zwei Sekunden (§2.8)."""
        self.status_message.setText(
            tr("Die Trennebenen werden gesucht …") if busy else self._announcement
        )
        if busy:
            # Wie viele Ebenen die Suche prüft, steht vorher nicht fest —
            # derselbe endlose Balken wie beim Agentenzug.
            self.progress.setRange(0, 0)
            self.progress.setVisible(True)
            self.cancel_button.setVisible(True)
            return
        if not self._anything_running():
            self.progress.setRange(0, 100)
            self.progress.setVisible(False)
        self.cancel_button.setVisible(self._anything_cancellable())

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
        if preview.proposal.empty:
            # Regel 19 im Geist: ein reiner Auskunftszug ist keine
            # Entscheidung. Übernehmen/Verwerfen über „Keine Änderung"
            # anzubieten war eine Wahl ohne Gegenstand — der Beitrag wird
            # sofort aufgezeichnet, und nur das Gespräch bleibt.
            self.session.discard_proposal(preview)
            self._proposal = None
            self.chat.show_proposal(None)
            self.chat.show_document(self.session.project.document)
            self._focus_chat()
            return
        if self.settings.auto_accept_reversible and agent_apply.auto_acceptable(preview.proposal):
            transaction = self.session.accept_proposal(preview)
            self._proposal = None
            self._applied_transaction = transaction.id if transaction else None
            self.chat.show_applied(preview, transaction.id if transaction else "")
            self.chat.show_document(self.session.project.document)
            # Eine wartende Differenz eines abgelösten Vorschlags bliebe sonst
            # unbeschriftet über der neuen Szene stehen.
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
        self.session.accept_proposal(self._proposal)
        self._clear_proposal()

    def _on_proposal_discarded(self) -> None:
        if self._proposal is None:
            return
        self.session.discard_proposal(self._proposal)
        self._clear_proposal()

    def _on_applied_undone(self) -> None:
        """Der Rückgängig-Knopf der Übernommen-Leiste (§26.5).

        Er nimmt genau die Transaktion zurück, die die Leiste verspricht —
        und nur, wenn sie noch die oberste ist. ``History.undo`` kennt nur
        „die letzte": läge inzwischen etwas anderes obenauf, zerstörte der
        Knopf fremde Arbeit und ließe die versprochene stehen. Der Fall ist
        durch :meth:`_refresh_applied_bar` selten, aber nicht unmöglich —
        ein Fernaufruf läuft ohne ``projectChanged``-Lücke dazwischen.
        """
        applied = self._applied_transaction
        self._applied_transaction = None
        transactions = self.session.project.document.transactions
        if applied and transactions and transactions[-1].id == applied:
            self.session.undo()
        elif applied and any(entry.id == applied for entry in transactions):
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

    def _on_paint(self, point: Any) -> None:
        """§20: ein Klick, eine Operation — ein Undo nimmt also einen Strich
        zurück.
        """
        object_id = self.object_tree.selected()
        if not object_id:
            self.announce(str(_NEEDS_SELECTION))
            return

        params = {**self.paint_bar.values(), "x": point[0], "y": point[1], "z": point[2]}
        self.session.apply(
            _("Bemalen"),
            [OperationDraft(op="paint_slot", inputs=(object_id,), params=params)],
        )

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
            self._split_points = []
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
        self._split_points.append(picked)
        self.viewport.show_split_line(self._split_points)
        self.split_bar.show_points(len(self._split_points))

    def _clear_split_line(self) -> None:
        """Die gezeichnete Linie verwerfen — kein Undo nötig, es war nie eine
        Änderung."""
        self._split_points = []
        self._split_target = None
        self.viewport.clear_split_line()
        self.split_bar.show_points(0)

    def _end_split(self) -> None:
        """Was das Schließen des Werkzeugs zurücknimmt."""
        self.viewport.set_splitting(False)
        self._clear_split_line()
        self.split_bar.reset()

    def _apply_split_line(self) -> None:
        """§25: aus zwei Punkten und der Blickrichtung wird eine Ebene, aus der
        Ebene eine Transaktion.

        Die Blickrichtung wird **hier** abgefragt und nicht in der Operation:
        Eine Op, die die Kamera läse, gäbe beim zweiten Auswerten ein anderes
        Ergebnis (§11.2). Was in den Stapel geht, sind Zahlen.
        """
        if len(self._split_points) < POINTS_NEEDED or self._split_target is None:
            return

        first, second = self._split_points[0], self._split_points[1]
        plane = plane_through(first, second, self.viewport.view_direction())
        if plane is None:
            # Zwei Punkte genau hintereinander sehen im Bild aus wie einer.
            # Raten wäre hier eine Ebene, die niemand gezeigt hat (Regel 21).
            self.announce(
                tr("Die zwei Punkte liegen hintereinander — bitte quer über das Teil zeichnen.")
            )
            return

        chosen = self.split_bar.values()
        pins = int(chosen["pins"])
        applied = self.session.split_along(
            self._split_target, plane, pins=pins, shape=str(chosen["shape"])
        )
        self.report.add_findings(applied.findings)
        self._clear_split_line()
        self.announce(
            tr("Getrennt — die Hälften stehen im Objektbaum.")
            if not pins
            else tr("Getrennt und zum Zusammenstecken vorbereitet.")
        )

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
        Sache des Fensters — ``feature:<id>`` ist ein Begriff des Kerns
        (``app.core.sketch.planes``), und der Objektbaum kennt den
        Skizzenmodus nicht.

        **Ohne festgelegte Operation.** Was aus der Zeichnung wird, fragt der
        Dialog bei „Fertig" (§2.2, Weg 2) — auf einer Deckfläche ist eine
        Tasche so plausibel wie ein Aufbau, und die Entscheidung vorwegzunehmen
        hieße, dem Nutzer eine von zwei gleich guten zu nehmen.
        """
        self.start_sketch("", plane=f"feature:{feature_id}")

    def _on_object_picked(self, object_id: str) -> None:
        """Ein Klick auf einen Körper wählt ihn im Baum aus; einer daneben hebt
        die Auswahl auf.

        Damit gilt endlich, was das Navigationsschema verspricht und das
        Handbuch beschreibt: links wählt aus. Bis hierher ging Auswählen nur
        über den Baum — und wer die Bohrung meinte, musste ihren Namen kennen.
        """
        self.object_tree.select_object(object_id or None)

    def _on_feature_selected(self, feature_id: str | None) -> None:
        """Das gewählte Merkmal, in der Ansicht und in der Statusleiste."""
        self.viewport.select_feature(feature_id)
        if feature_id is None:
            return
        result = self.session.last_result
        object_id = self.object_tree.selected()
        entry = result.scene.objects.get(object_id) if result and object_id else None
        feature = entry.features.get(feature_id) if entry is not None else None
        if entry is not None and feature is not None:
            self.measurements.setText(f"{entry.name} · {feature_label(feature_id, feature)}")

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

    def run_operation(self, spec: OperationSpec, given: Mapping[str, Any] | None = None) -> None:
        """Menüeintrag, Dialog, Transaktion — derselbe Weg, den auch der Agent
        nehmen wird.

        ``given`` belegt Felder vor, die der Aufrufer schon kennt — der
        Skizzenmodus reicht so seine gezeichnete Skizze herein. Es ersetzt den
        Dialog nicht: die übrigen Werte fragt er weiter, und was hier steht,
        lässt sich dort ändern.
        """
        if self.session.history.discardable and not confirm_discard(
            self.session.history.discardable, self._discarded_names(), self
        ):
            return

        result = self.session.last_result
        objects = list(result.scene.objects) if result else []
        chosen = self.object_tree.selected_objects()
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
            _works_on(self._object_names().get(inputs[0], ""), len(chosen), spec.consumes)
            if inputs and not spec.takes_whole_scene
            else ""
        )

        def run(params: Mapping[str, Any]) -> None:
            if spec.name in LID_OPS and inputs:
                # Der Deckel geht über seinen Ablauf, nicht über die nackte
                # Operation: erst der trägt das Paar aus Öffnung und Kragen als
                # Passung ein (§14), und daran hängen im Slicer die genaue
                # Außenwand, die gebremste Beschleunigung und das Bügeln.
                applied = self.session.create_lid(inputs[0], dict(params))
                self.report.add_findings(applied.findings)
                return
            self.session.apply(
                spec.title,
                [OperationDraft(op=spec.name, inputs=inputs, params=dict(params))],
            )

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
                features=self._feature_names(),
                extra=exact if exact is not None else variant,
                extra_label=str(group.choice) if group is not None else "",
                surroundings=self._sketch_surroundings(),
                images=self._image_names(),
                pick_image=self._pick_image_source,
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

    def edit_operation(self, op_id: int, field: str = "") -> None:
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
            exact.setToolTip(str(hint))
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
            values=entry.params,
            sources=self._source_names(),
            parameter_values=self._parameter_values(),
            features=self._feature_names(),
            extra=exact,
            surroundings=self._sketch_surroundings(),
            images=self._image_names(),
            pick_image=self._pick_image_source,
        )
        dialog.setWindowTitle(f"{spec.title} — {tr('Operation')} {op_id}")
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
        self.viewport.show_difference(difference)
        self.viewport.mark_preview(
            tr("Vorschau — noch nicht übernommen"),
            tr("Leertaste halten: vorher"),
        )

    def _clear_preview(self) -> None:
        """Der Dialog ist zu: die Vorschau geht, ein wartender Agentenvorschlag
        bekommt seine Differenz zurück."""
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

    def _feature_names(self) -> dict[str, str]:
        """Die Merkmale des gewählten Körpers, Kennung auf Beschriftung (§18.5).

        Dieselbe Beschriftung wie im Objektbaum und über dem Modell: „hole_1 ·
        Ø5,19 mm". Ohne Auswahl bleibt die Liste leer — welche Fläche gemeint
        ist, entscheidet der Körper, an dem gearbeitet wird.
        """
        result = self.session.last_result
        chosen = self.object_tree.selected()
        if result is None or chosen is None:
            return {}
        entry = result.scene.objects.get(chosen)
        if entry is None:
            return {}
        return {
            feature_id: feature_label(feature_id, feature)
            for feature_id, feature in entry.features.items()
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
        # Eingepasst wird im Viewport (``_fit_once_for``), nicht hier: dort ist
        # die neue Szene schon gesetzt. Von hier aus lief es mit den Maßen der
        # *vorigen* — beim ersten Projekt also mit gar keinen, und dann passte
        # es auf den Bauraum ein statt auf das Teil.
        self._seen_objects = bool(result.scene.objects)
        self.object_tree.show_scene(result, self.session.project.document)
        plates = {entry.plate for entry in result.scene.objects.values()}
        # Der Plattenwähler sitzt in der Kopfzeile und nicht mehr in der
        # Explodier-Leiste: Wer eine einzelne Platte ansehen wollte, suchte ihn
        # unter einem Werkzeug, das Teile auseinanderzieht.
        self.header.show_plates(max(plates, default=0) + 1)
        self.tools.set_available("explode", self.explode_bar.show_for(len(result.scene.objects)))
        self.report.show_result(result, self.session.project.document)
        # Ein Strich legt einen Slot an: Nach der Auswertung soll die
        # Pinselleiste ihn kennen, sonst steht dort weiter „neu".
        chosen = self.object_tree.selected_objects()
        self._tell_the_brush_about_the_slots(chosen[0] if len(chosen) == 1 else None)
        self._update_header()
        self.viewport.show_build_volume(self.session.profile)
        self.viewport.show_scene(result)
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
            self._focus_report(force=True)
        elif self.report.worst_severity(result) in ("warning", "error"):
            self._focus_report()

    def _on_project(self) -> None:
        # Eine gezeichnete Trennlinie liegt auf einem Körper, den es nach einer
        # Änderung am Dokument so nicht mehr geben muss — ein neues Projekt,
        # ein Undo, eine Operation von woanders. Sie stehen zu lassen hieße,
        # auf zwei Punkte im Leeren zu zeigen; und das Ziel der Linie wäre nach
        # dem Öffnen einer anderen Datei eine Kennung, die dort etwas anderes
        # bezeichnet.
        if self._split_points:
            self._clear_split_line()
        document = self.session.project.document
        # Wer auf dem Startbildschirm etwas ins Dokument bringt — Einfügen,
        # Generieren, ein Baustein aus dem Katalog —, will es auch sehen. Von
        # acht Wegen wechselten sieben einzeln von Hand, und der achte war der
        # Schlussknopf der Erstinbetriebnahme: Modell geladen, Startbildschirm
        # stand. Der Wechsel am Dokument selbst macht die vergessene Stelle
        # unmöglich.
        if document.ops and self.stack.currentWidget() is self.start_screen:
            self._show_start_screen(False)
        self.parameters.show_document(document)
        self.history_panel.show_document(document, undone=self.session.history.undone)
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

    def _update_facts(self) -> None:
        """Material und Dauer aus dem, was ohnehin vorliegt.

        Volumen und Oberfläche bringt jedes ausgewertete Netz mit; die
        Schätzung darauf kostet nichts und darf deshalb nach jeder Auswertung
        laufen (§31). Eine Schichtanalyse dürfte das nicht — sie braucht
        Sekunden, und die Zeile stünde nach jedem gezogenen Parameter still.
        """
        result = self.session.last_result
        if result is None or not result.scene.objects:
            self.facts.show_estimate(None)
            return
        bodies = [(entry.mesh.volume, entry.mesh.area) for entry in result.scene.objects.values()]
        settings = print_settings.resolve(self.session.profile)
        self.facts.show_estimate(estimate_total(bodies, settings))

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
        self.status_message.setText(text)

    def _on_progress(self, fraction: float, text: str) -> None:
        self.progress.setValue(int(fraction * 100))
        self.veil.step(fraction, text)
        if not text:
            # Ein leerer Text heißt, der Lauf ist vorbei; dann kommt zurück,
            # was zuletzt zu sagen war (§2.8).
            self._run_started = None
            self.status_message.setText(self._announcement)
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
        self.status_message.setText("  ·  ".join(parts))

    def _on_busy(self, busy: bool) -> None:
        # Agent, Trennebenensuche, Export und Download können neben der
        # Auswertung laufen; dann bleibt der Balken stehen, statt mit ihr zu
        # verschwinden — und der Knopf zeigt sich nur, wo er etwas abbricht.
        running = busy or self._anything_running()
        self.progress.setVisible(running)
        self.cancel_button.setVisible(busy or self._anything_cancellable())
        if busy:
            self.progress.setRange(0, 100)
        self._update_veil(busy)
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
        # rechnet an etwas, das noch keinen Körper hat.
        self.veil.begin(tr("Projekt wird geladen …") if result is None else tr("Wird berechnet …"))

    def _on_ask(self, request: AskRequest) -> None:
        """Der Arbeiter wartet, solange dieser Dialog offen ist (§21.3)."""
        dialog = AskDialog(request.question, request.choices, self)
        if dialog.exec() == AskDialog.DialogCode.Accepted:
            request.reply(dialog.chosen())
        else:
            request.reply(None)

    def _on_error(self, error: AppError) -> None:
        """§33.1: ein Fehler des Nutzers sieht anders aus als ein Fehler im
        Programm.
        """
        if isinstance(error, InternalError):
            self.report_error(error)
            return
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
            "repair_and_retry": self._repair_after_error,
            "split_model": self._split_after_error,
            "scale_to_fit": self._scale_after_error,
            "place_on_bed": self._place_on_bed_after_error,
            "arrange_on_bed": self._arrange_after_error,
            "correct_input": self._correct_after_error,
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
            # **Der Draht, der fehlte.** ``install`` vergaben ``ScadUnavailable``
            # und seit dieser Sitzung ``BRepUnavailable`` und jeder
            # ``ExternalToolError`` — ohne Handler wurde daraus ein grauer Satz
            # („OpenSCAD installieren …"), während der Dialog, der genau das
            # kann, im Hilfe-Menü stand. Zwei Zeilen darunter hing er unter
            # ``open_settings``, also unter einem Namen, den kein Knopf trug.
            "install": lambda _error: self.action_install_extras(),
            # Und der heißt jetzt, was er tut: die Einstellungen. Bis hierhin
            # öffnete er die Liste der externen Programme, weil der Kern ihn
            # dafür benutzte — der Knopf log also seinen Namen.
            "open_settings": lambda _error: self.action_settings(),
            "enter_licence_key": lambda _error: self.action_activate(),
            "buy_licence": lambda _error: open_website(),
        }

    def action_activate(self) -> None:
        """Öffnet den Freischaltdialog (Konzept §2 B).

        Steht im Hilfe-Menü und nicht nur hinter der Fehlerhandlung
        ``enter_licence_key``: wer während des Testlaufs kauft, braucht einen
        Weg, seinen Schlüssel einzutragen, **bevor** ihn etwas aufhält.

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

    def _repair_after_error(self, error: AppError) -> None:
        """§17.1: die Reparaturkette auf den Körper, an dem es hing."""
        object_id = self._object_of(error)
        if object_id is None:
            return
        self.session.apply(
            REGISTRY.get("repair").title,
            [OperationDraft(op="repair", inputs=(object_id,))],
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
        self.viewport.select(object_id)
        # Karte und Schichtanalyse gehören zu einem Körper; ein anderer Körper
        # braucht seine eigenen, also folgen sie der Auswahl, statt zu
        # verweilen.
        self._on_map_changed(self.analysis_bar.chosen())
        self._on_layer_changed(self.layer_bar.index())
        self._update_actions()
        self._tell_the_brush_about_the_slots(object_id)
        described = describe_selection(self.session.last_result, object_id)
        if described is None:
            self.measurements.clear_selection()
            return
        name, size, volume = described
        self.measurements.show_object(name, size, volume)

    def _tell_the_brush_about_the_slots(self, object_id: str | None) -> None:
        """Die Pinselleiste nennt Farbe und Namen des Slots — beides gehört dem
        Körper, nicht dem Werkzeug.

        Ohne diesen Weg wüsste die Leiste nur ihre Nummer, und die sagt nicht,
        was auf dem Teil landet. Ein Strich legt einen Slot an; nach der
        Auswertung ruft ``_refresh_all`` denselben Pfad, damit „neu" danach
        seinen Namen hat.
        """
        result = self.session.last_result
        entry = None
        if result is not None and object_id is not None:
            entry = result.scene.objects.get(object_id)
        self.paint_bar.set_slots(entry.material_slots if entry is not None else [])

    def action_add_parameter(self) -> None:
        """§13: ein Hauptmaß benennen — auch ohne den Agenten (§2.3)."""
        dialog = ParameterDialog(self.session.project.document.parameters, self)
        if dialog.exec() != ParameterDialog.DialogCode.Accepted:
            return
        self.session.add_parameter(dialog.parameter())

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
        """§38: Sprache, Drucker, Material, externe Programme, Chat-Zugang.
        Überspringbar."""
        dialog = first_run.FirstRunDialog(self.settings, self)
        dialog.importRequested.connect(self.action_import)
        if dialog.exec() == first_run.FirstRunDialog.DialogCode.Accepted:
            dialog.apply_to(self.settings)
            self._adopt_defaults()
        else:
            # Überspringen zählt als erledigt: beim nächsten Mal wieder zu fragen
            # wäre Nörgeln.
            self.settings.first_run_done = True
        save_settings(self.settings)
        # Wer im Dialog den Chat eingerichtet hat, soll ihn nicht erst nach
        # einem Neustart bekommen — derselbe Weckruf wie in action_llm_key.
        self.session.set_agent_backend(None)
        self._refresh_chat_availability(probe_local=True)

    def _discarded_names(self) -> list[str]:
        """Wie die zurückgenommenen Schritte heißen, jüngster zuerst.

        Die Frage nannte nur ihre Zahl. „Diese Änderung verwirft 2
        zurückgenommene Schritte" sagt, wie viel weg ist, nicht was — und
        genau das entscheidet, ob man Ja sagt.
        """
        return [str(entry.title) for entry in reversed(self.session.history.undone)]

    def _adopt_defaults(self) -> None:
        """Ein leeres Projekt übernimmt die eben gewählten Vorgaben.

        Die Erstinbetriebnahme fragt nach Drucker und Material, und die
        Einstellungen sagen zu Recht, dass diese Werte „für das nächste neue
        Projekt" gelten. Beim ersten Start ist das offene Projekt aber genau
        das, mit dem weitergearbeitet wird: gewählt war Centauri Carbon 2 und
        PETG, in den Druckeinstellungen stand danach „Allgemeiner FDM-Drucker"
        und PLA.

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

        „Sehen Sie links in den Verlauf" nennt einen von vier Bereichen, und
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
        }
        area = areas.get(target)
        if area is None:
            return
        if area is self.report:
            self.right.setCurrentWidget(self.report)

        area.setStyleSheet(f"border: 2px solid {ROLES['select']};")
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
        # Hier stand eine Sicherung. Sie lief **nach** der Frage darüber, und
        # dort kann nur noch stehen, wer gerade *Verwerfen* geklickt hat —
        # gespeichert hätte ``modified`` geräumt. Sie schrieb also genau den
        # Stand weg, den der Nutzer eben weggeworfen hatte, und das nächste
        # Öffnen bot ihn wieder an. Wer im Betrieb abstürzt, ist weiter
        # abgedeckt: der Zeitgeber sichert im Lauf (``AUTOSAVE_INTERVAL_MS``).
        # Wie das Fenster verlassen wird, so kommt es wieder — maximiert ist
        # nur die Vorgabe für den ersten Start.
        self.settings.window_geometry = bytes(self.saveGeometry().toHex().data()).decode("ascii")
        save_settings(self.settings)
        self._usage.stop()
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
