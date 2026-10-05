"""Die drei Panels links und der Prüfbericht rechts (Bauplan §2.5).

Drei einklappbare Abschnitte, keine drei Fenster: Objektbaum, Parameter,
Verlauf. Sie lesen aus dem Dokument und der letzten Auswertung, und sie ändern
nie selbst Geometrie — jede Änderung geht durch eine Operation (AGENTS.md
Regel 2).
"""

from __future__ import annotations

import dataclasses
import math
import weakref
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from functools import partial
from itertools import islice, pairwise
from typing import Any, Final, NamedTuple, cast, override

from PySide6.QtCore import (
    QEvent,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    QRectF,
    QSignalBlocker,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QTextBrowser,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from app.core import expressions
from app.core.action_effects import effect_worth_showing, side_effect
from app.core.drawing import Theme as DrawingTheme
from app.core.errors import (
    ARRANGE_ON_BED,
    CANCEL,
    CHANGE_SELECTION,
    CHOOSE_PRINTER,
    CONVERT_TO_EXACT,
    CORRECT_INPUT,
    DECIMATE_AND_RETRY,
    DECIMATE_MESH,
    EXPORT_AS_MESH,
    GIVE_THICKNESS,
    MESH_AND_RETRY,
    ORIENT_FOR_PRINT,
    PLACE_ON_BED,
    RECOGNIZE_FULLY,
    RECOGNIZE_LOCAL,
    RELEASE_PROTECTION,
    REMESH_AND_RETRY,
    REMOVE_SMALL_PARTS,
    REPAIR_AND_RETRY,
    REPAIR_BEFORE_AND_RETRY,
    RESIZE_THE_WIDENING,
    RESOLVE_INTERSECTIONS,
    SCALE_TO_FIT,
    SHOW_DETAILS,
    SHOW_FEATURE,
    SHOW_HISTORY,
    SHOW_LAYERS,
    SHOW_LOCATION,
    SHOW_LOCATIONS,
    SHOW_STEP_VALUES,
    SHOW_SUPPORT_NEED,
    SPLIT_ALONG_LINE,
    SPLIT_AND_RETRY,
    SPLIT_BODIES,
    SPLIT_MODEL,
    Action,
    AppError,
)
from app.core.export.writer import PART_SETTING_CODES
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.ingest.plan import imported_group_for_bed
from app.core.log import get_logger
from app.core.perceive.actions import measure_explanation, measure_qualifier
from app.core.perceive.groups import FunctionalGroup
from app.core.perceive.local import CONFIRMED_FEATURE_LIMIT_TRIANGLES
from app.core.perceive.relations import FeatureActionGroup
from app.core.registry import REGISTRY, kernel_switch_label, kernel_twin_of, shown_of_twins
from app.core.registry.surfaces import first_sentence
from app.core.scene import EvaluationResult
from app.core.scene.cancel import CancelSignal
from app.core.scene.history import (
    StepNeed,
    recognition_reopenable,
    repair_is_available,
    step_titles,
)
from app.core.scene.parameter_binding import BindingSpot
from app.core.scene.parameter_usage import field_bounds
from app.core.types import (
    CancelToken,
    Document,
    Feature,
    Finding,
    MaterialSlot,
    ObjectId,
    OpId,
    Parameter,
    SceneObject,
    Transaction,
    measure_status,
)
from app.core.units import LengthUnit, is_close
from app.i18n import TranslatableText, sort_key, tr
from app.ui.dialogs import ADDRESS_VALUES, NEEDS_OP, handlers_of, unhandled_advice
from app.ui.icons import icon, icon_name_for, svg_pixmap
from app.ui.labels import (
    BoundedLengthSpin,
    BoundedSpin,
    LengthSpin,
    RowCheckBox,
    caption_toggles,
    cavity_name,
    choice_label,
    choice_note,
    compact_length,
    explain_choices,
    feature_label,
    feature_measure,
    feature_measure_tip,
    feature_name,
    feature_source,
    fill_parameter_units,
    group_measure_text,
    group_summary,
    kind_requirement,
    length,
    limit_sentence,
    localised,
    spoiled_the_exact_body,
    step_number,
    unit_of,
    value_line,
    value_text,
    volume,
    wheel_needs_focus,
)
from app.ui.leash import Worker, WorkerLeash, weak_slot
from app.ui.overlay import LEFT_WIDTH, ContentScroller, FittedScroller, rows_height
from app.ui.palette import SEVERITY_ENCODING, Role, text_colour
from app.ui.style import (
    NORMAL,
    ROOMY,
    SPACE,
    TARGET_SIZE,
    TIGHT,
    make_danger,
    make_primary,
    rule,
    set_level,
)
from app.ui.tab_signal import count_phrases
from app.ui.theme import UNDONE_COLOUR

_log = get_logger(__name__)

#: Zeichen je Schweregrad, aus der gemeinsamen Kodierung — Farbe steht nie
#: allein (§19.1).
SEVERITY_MARKER = {name: entry.symbol for name, entry in SEVERITY_ENCODING.items()}

#: Datenrolle einer Verlaufszeile: **alle** Operationen, die sie umfasst, als
#: Tupel. Neben ``UserRole``, das die *eine* Operation zum Öffnen trägt und
#: bei einer Transaktion aus mehreren Schritten leer bleibt — ein Doppelklick
#: hätte dort keine, die er zeigen könnte. Die Mehrfachauswahl fragt diese
#: Rolle, weil sie die andere Frage stellt: was gehört zu dieser Zeile.
OPS_ROLE = int(Qt.ItemDataRole.UserRole) + 1
#: Die Transaktion, zu der eine Kindzeile gehört — daran hängt das Einklappen.
GROUP_ROLE = int(Qt.ItemDataRole.UserRole) + 2


#: Operationen, die der Doppelklick diesen Merkmalsarten nicht erneut anbietet,
#: weil ein Griff im Bild die Handlung bereits übernimmt — Operation → Merkmalsarten.
#:
#: An einer Bohrung führt der Langlochgriff direkt zum Langloch. An einem
#: bestehenden Langloch bleibt die Operation erreichbar, weil sie dort die
#: Bearbeitung seiner Maße eröffnet. Andere Zugangswege lesen weiter das Register.
#: ``tests/test_interface_limits.py`` prüft, dass jede hier ausgenommene Art
#: tatsächlich einen passenden Griff besitzt.
HANDLE_INSTEAD: Final[dict[str, frozenset[str]]] = {
    "slot_hole": frozenset({"hole"}),
}


def shown_at_feature(kind: str, entries: Sequence[Any]) -> tuple[Any, ...]:
    """Welche Operationen der Doppelklick auf diese Merkmalsart anbietet.

    Die Rohmenge liefert ``REGISTRY.for_feature``; hier fällt weg, was
    :data:`HANDLE_INSTEAD` an dieser Art dem Griff überlässt. Eine Funktion und
    kein Ausdruck im Aufbau, weil ``tests/test_interface_limits.py`` die
    Zeilen ohne Fenster nachrechnet und dabei dieselbe Menge braucht.
    """
    return tuple(spec for spec in entries if kind not in HANDLE_INSTEAD.get(str(spec.name), ()))


#: In welcher Reihenfolge die Schweregrade stehen. Die Zeile über der Liste
#: zählt Fehler, Warnungen und Hinweise getrennt — sie verspricht damit eine
#: Rangfolge, und die Liste darunter hielt sie nicht: sie hängte an, wie es
#: kam, also stand bei zwei Warnungen und vier Hinweisen zuoberst ein Hinweis.
#: Wer einen Fehler suchte, musste ihn filtern statt lesen.
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


#: Ab wie vielen wortgleichen Befunden die Liste sie zu einer Zeile bündelt.
#:
#: Nach einem Weg-3-Erzeugungslauf standen 123 Befunde im Bericht, 118 davon
#: wortgleich („Ein Merkmal hat keinen Nachfolger mehr") — die fünf Zeilen,
#: die etwas sagten, gingen darin unter, allen voran das richtige
#: ``arrange.below_bed``. Jede Einzelzeile stimmt; die **Menge** begräbt.
#: Gebündelt wird deshalb in der Anzeige, nicht im Kern: Agent, CLI und
#: Tests lesen weiterhin jeden Befund einzeln. Die Zahl gilt dem Objektbaum
#: (gleichartige Merkmale unter einem Dach); der Prüfbericht bündelt ab
#: :data:`REPORT_BUNDLE_FROM`.
BUNDLE_FROM = 4

#: Ab wie vielen gleichen Meldungen der Prüfbericht eine gezählte Zeile
#: zeigt: ab **zwei** (Robert, 11.09.2026: „beim prüfbericht auch gleiche
#: Meldungen zusammenfassen und anzahl dann davor in Klammer anzeigen").
#:
#: Bis zum 11.09.2026 trennte der Körper die Gruppen — außer bei zwei
#: kuratierten Kennungen (``perceive.too_large``, ``ingest.very_large``), bei
#: denen die Zeile die Körper als Liste trug und die Handlung beim Klick
#: fragte, für welche sie gelten soll (Entscheidung Robert, 03.09.2026).
#: Gemessen an seinem Schriftzug: neunmal „Ausrichtung über die
#: Schichtanalyse gesucht." und sechsmal „Zwei Teile stehen so dicht …", je
#: Buchstabe eine Zeile, und der eine Befund, der etwas Eigenes sagte, stand
#: dazwischen. Der Klickvertrag bleibt: Eine Sammelzeile zeigt beim Klick
#: **alle** ihre Körper (:data:`_BODIES_ROLE`, ``bundleActivated``), nie den
#: ersten zufälligen, und ihre Handlung fragt, für welche davon sie gelten
#: soll. Damit verliert die Bündelung nichts — sie gibt die Wahl zurück, die
#: vorher neun Zeilen waren.
REPORT_BUNDLE_FROM = 2

#: Die Körper, die eine Sammelzeile vertritt — Grundlage der Auswahl beim
#: Klick. Eigene Rolle und nicht aus dem Befund gelesen: Der trägt nur seinen
#: eigenen, und die Zeile steht für alle.
_BODIES_ROLE = int(Qt.ItemDataRole.UserRole) + 5

#: Die Mitglieder einer Sammelzeile, je Körper eines — Grundlage einer
#: Handlung, die je Körper läuft (:data:`_PER_BODY_ACTIONS`): Sie bekommt
#: den Befund **dieses** Körpers und nicht den des ersten.
_MEMBERS_ROLE = int(Qt.ItemDataRole.UserRole) + 6

#: Handlungen, die einem Körper gelten und für jeden gewählten einzeln laufen,
#: wenn die Sammelzeile mehrere trägt. Alles andere — was einen Schritt meint
#: (``NEEDS_OP``, die Wiederholungen nach einem Halt), die ganze Szene
#: (*Auf dem Bett anordnen*) oder gar keinen Körper (Bericht, Einstellungen)
#: — läuft einmal. Eine Handlung, die als Operation im Register steht, geht
#: den dritten Weg: ein Schritt je Körper in **einer** Transaktion
#: (``actionOnBodies``).
_PER_BODY_ACTIONS: Final[frozenset[str]] = frozenset(
    {"place_on_bed", "scale_to_fit", "split_model", "remove_small_parts"}
)

#: Handlungen, die den **Körper** des Befunds brauchen — lebend, im Ergebnis
#: (RM-268). Ihre Handler am Fenster lesen ihn (``_object_of``, ``_entry_of``,
#: ``error.object_id``) oder wirken auf die Auswahl, die an einem verbrauchten
#: Körper eine andere wäre. Nach *Modell teilen* stand am Laptopständer
#: „Das Modell besteht aus 21 Teilen …“ am verbrauchten Körper mit
#: *Überschneidungen auflösen* und *In Einzelteile zerlegen*, und ein Klick
#: legte eine Reparatur an einem Körper an, den es nicht mehr gibt. Was einen
#: Schritt ändert (``NEEDS_OP``) oder die ganze Szene meint, gilt ohne ihn.
#: Vollständig hält die Menge ``test_finding_actions`` am Handlerverzeichnis.
NEEDS_LIVE_BODY: Final[frozenset[str]] = frozenset(
    {
        SHOW_LOCATIONS.id,
        SHOW_LOCATION.id,
        SHOW_FEATURE.id,
        SHOW_SUPPORT_NEED.id,
        SHOW_LAYERS.id,
        DECIMATE_MESH.id,
        # Hält die Kette nicht an seinem Schritt, verringert es den Körper selbst.
        DECIMATE_AND_RETRY.id,
        GIVE_THICKNESS.id,
        RESOLVE_INTERSECTIONS.id,
        SPLIT_BODIES.id,
        REMOVE_SMALL_PARTS.id,
        SPLIT_MODEL.id,
        SPLIT_AND_RETRY.id,
        RELEASE_PROTECTION.id,
        SCALE_TO_FIT.id,
        PLACE_ON_BED.id,
        CONVERT_TO_EXACT.id,
        ORIENT_FOR_PRINT.id,
        RESIZE_THE_WIDENING.id,
    }
)


def _needs_live_body(action: Action, finding: Finding, document: Document | None) -> bool:
    """Ob ``action`` am Befund den lebenden Körper braucht (:data:`NEEDS_LIVE_BODY`).

    Eine Ausnahme, so schmal wie ihr Handler: *Überschneidungen auflösen* an
    einem Reparaturschritt ändert diesen Schritt und legt keinen neuen an
    (``MainWindow._resolve_intersections_after_error``).
    """
    if action.id not in NEEDS_LIVE_BODY:
        return False
    if action.id == RESOLVE_INTERSECTIONS.id and document is not None:
        step = next((entry for entry in document.ops if entry.id == finding.op_id), None)
        return step is None or step.op != "repair"
    return True


#: Trägt an einer Sammelzeile, wie viele Befunde sie bündelt. Eine eigene
#: Rolle und nicht ``values["count"]``: Den Schlüssel führen auch Befunde des
#: Kerns („12 kleine Objekte übergangen"), und eine Zählung, die ihn läse,
#: zählte deren Zahl statt ihrer Zeile.
_BUNDLE_ROLE = int(Qt.ItemDataRole.UserRole) + 3

#: Die Farbe des Schweregradsymbols an einer Befundzeile. Trug lange keine
#: Konstante, sondern stand als ``UserRole + 4`` mitten im Aufbau — und
#: genau darauf ist :data:`_BODIES_ROLE` beim ersten Anlauf gelaufen: Die
#: Zeile lieferte ``'#3479ba'`` statt ihrer Körper. Eine Rolle ohne Namen
#: ist für den Nächsten unsichtbar; deshalb steht sie hier bei den anderen.
_TONE_ROLE = int(Qt.ItemDataRole.UserRole) + 4

#: Die Zeile eines Befunds kurz und ganz: erster Satz und vollständige Meldung
#: (:func:`headline`). Die gewählte Zeile steht ganz da (RM-508).
_LINE_ROLE = int(Qt.ItemDataRole.UserRole) + 7


def headline(message: str) -> str:
    """Der erste Satz einer Meldung — die Zeile, die man beim Überfliegen liest.

    **Erst die Befunde, dann ihre Erklärung** (RM-508): Im Hauptfenster
    standen 88 Wörter Befundtext, die Hälfte davon Rat in Prosa („Die
    Materialbahnen im Slicer prüfen; fehlen sie dort, …“), und lange Zeilen
    verdrängten die nächsten. Die Liste zeigt je Befund seinen ersten Satz;
    die gewählte Zeile steht ganz da, ihre Handlungen darunter.

    Wo ein Satz endet, sagt :func:`~app.core.registry.surfaces.first_sentence`,
    dieselbe Regel, mit der Menü, Palette und der Längenwächter schneiden
    (RM-509): Eine eigene hier schnitt hinter „ca.“ und „Nr.“ und ließ einen
    Folgesatz in Anführungszeichen stehen (Durchsicht 0.5.3, Fund 6).
    """
    return first_sentence(message)


def _bundled(
    findings: list[Finding],
    document: Document | None = None,
    live_objects: Collection[ObjectId] = (),
) -> list[tuple[Finding, list[Finding]]]:
    """Gleiche Meldungen ab :data:`REPORT_BUNDLE_FROM` zu einer Zeile je Wortlaut.

    Gruppiert wird über Kennung, Grad, Wortlaut, Herkunft, Schritt und die
    angebotenen Handlungen. **Nicht** über Körper, Ort, Merkmale und Werte:
    Genau die machen aus neun gleichen Sätzen neun Zeilen, und die Zeile soll
    den Satz einmal sagen und zählen (Robert, 11.09.2026). Was die Mitglieder
    unterscheidet, trägt die Zeile anders — die Körper als Liste für den
    Klick (:data:`_BODIES_ROLE`), Namen und Werte je Mitglied im Tooltip.
    Schritt und Auswege bleiben im Schlüssel, denn sie gehören zum
    Klickvertrag: Eine Sammelzeile darf nie zu einem zufälligen Schritt
    springen und nie ihre Handlung verlieren. Die Reihenfolge der
    Erstvorkommen bleibt erhalten; einzelne Befunde kommen als Einzelzeilen
    zurück (leere Mitgliederliste).
    """
    groups: dict[tuple[Any, ...], list[Finding]] = {}
    order: list[tuple[Any, ...]] = []
    for finding in findings:
        step_key: Any = finding.op_id
        if document is not None and finding.code in {
            "repair.holes_filled",
            "repair.branching_resolved",
            "repair.t_junctions",
            "repair.part_inside",
            "repair.empty_faces",
            "repair.duplicate_faces",
            "ingest.multiple_components",
            "ingest.small_components",
        }:
            operation = next((op for op in document.ops if op.id == finding.op_id), None)
            if operation is not None and operation.op == "load":
                transaction = next(
                    (entry for entry in document.transactions if operation.id in entry.ops), None
                )
                if transaction is not None:
                    step_key = ("import", transaction.id)
        key = (
            finding.code,
            finding.severity,
            str(finding.message),
            finding.source,
            step_key,
            tuple((action.id, str(action.label), action.primary) for action in finding.suggestions),
            _import_group_for(finding, document, live_objects),
        )
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(finding)
    result: list[tuple[Finding, list[Finding]]] = []
    for wording in order:
        members = groups[wording]
        if len(members) >= REPORT_BUNDLE_FROM:
            result.append((members[0], members))
        else:
            result.extend((one, []) for one in members)
    return result


#: Befunde über verlorene Formdetails und geschlossene Fehlstellen. Der Kern
#: meldet sie einmal je Körper und Schritt; wie viele es sind, steht dann in
#: ``values["count"]`` und fehlt bei genau einem (``evaluate``, 23.09.2026).
_LOST_CODES: Final[frozenset[str]] = frozenset({"perceive.orphaned", "perceive.mended"})


def _lost_count(finding: Finding) -> int:
    """Wie viele verlorene Formdetails oder geschlossene Stellen ein Befund nennt.

    Jeder andere Befund zählt als einer, auch wenn er ein eigenes ``count``
    trägt („12 kleine Objekte übergangen" ist ein Satz, keine zwölf).
    """
    if finding.code not in _LOST_CODES:
        return 1
    return int(cast(float, finding.values.get("count", 1)))


def _by_severity(findings: Iterable[Finding]) -> list[Finding]:
    """Schweres zuerst, sonst in der Reihenfolge, in der es entstanden ist.

    Stabil sortiert: innerhalb eines Grades bleibt die Kette der Operationen
    lesbar, und die erzählt, an welcher Stelle etwas schiefging.
    """
    return sorted(findings, key=lambda entry: SEVERITY_ORDER.get(entry.severity, 3))


#: Was gegen einen Befund hilft, je Befundkennung.
#:
#: **Ein Befund, der nur sagt, was nicht stimmt, ist die halbe Antwort.** §2.7
#: verlangt drei Teile — was nicht ging, warum, und was jetzt möglich ist —,
#: und der letzte fehlte hier ganz: Der Prüfbericht sagte „Das Objekt steht
#: über den Bauraum hinaus" und hörte auf. Dabei waren die Handlungen dazu
#: vollständig gebaut. Sie hingen an ``OutOfBuildVolume``, einer Ausnahme, die
#: **niemand wirft** — Bauraum ist ein Bericht und keine Sperre (§29), und
#: damit war der einzige Weg zu drei fertigen Vorschlägen zugemauert.
#:
#: Die Kennungen sind stabil (``Finding.code``), also ist diese Tabelle keine
#: Textsuche über Meldungen. Was hier fehlt, bekommt kein Menü — lieber keins
#: als eines, das nichts tut.
FINDING_ACTIONS: dict[str, tuple[Action, ...]] = {
    # Ein Schritt, den diese Fassung nicht kennt (§16.2). Zwei Handlungen, und
    # die erste ist die, um die es geht: *Werte ansehen* holt heraus, was in
    # dem Schritt steht — bei einer Datei aus 0.1.3 der OpenSCAD-Quelltext,
    # den jemand geschrieben hat. Ohne sie wäre der Befund eine Sackgasse: ein
    # Satz, der „Ihre Werte bleiben erhalten" verspricht, und kein Weg dorthin.
    #
    # **Löschen liegt im Verlauf selbst.** Auch ein unbekannter Schritt lässt
    # sich dort als rücknehmbare Transaktion entfernen; dieser Befund führt
    # deshalb dorthin. *Werte ansehen* bleibt vorn, weil Löschen die Arbeit
    # aufräumt, ihren Inhalt aber nicht vorab zugänglich macht (§15.4).
    "evaluate.unknown_operation": (SHOW_STEP_VALUES, SHOW_HISTORY),
    # Drei Antworten auf „passt nicht": kleiner machen, teilen — oder einen
    # anderen Drucker nehmen. Die dritte fehlte, solange ihr Handler fehlte,
    # und sie ist für den Kunden mit zwei Maschinen die naheliegendste.
    "arrange.out_of_build_volume": (SPLIT_MODEL, SCALE_TO_FIT, CHOOSE_PRINTER),
    # **Ein Befund ohne Handlung, den keine Familienprüfung fängt.**
    # `test_value_labels` hält Befunde derselben Familie zusammen — trägt
    # einer eine Handlung, müssen es alle. ``needs_solid`` steht allein in
    # seiner Familie und fiel deshalb durch: Wer `teil.step` tippte und ein
    # Netz hatte, bekam eine gute Erklärung und keinen Knopf.
    #
    # **Seit P4.0 steht der Weg zu STEP vorn**: Aus dem Netz einen Körper mit
    # echten Flächen und Kanten machen, danach trägt das Format. 3MF bleibt
    # der zweite Ausweg für den, der kein STEP braucht.
    "export.needs_solid": (CONVERT_TO_EXACT, EXPORT_AS_MESH, SHOW_DETAILS),
    # **Zu groß und nur verrutscht sind zwei Fälle.** Beide meldete der Kern
    # unter derselben Kennung, also bekam auch das Teil, das bloß zur Hälfte
    # unter der Platte steckt, *Modell teilen* und *Auf den Bauraum
    # verkleinern* angeboten — die beiden Handlungen, die hier nichts
    # ausrichten. Und es ist der häufigste Fall überhaupt: Ein
    # heruntergeladenes Modell ist um den Ursprung zentriert, und §17.1 setzt
    # es bewusst nicht von selbst auf (``place_on_bed`` steht auf „aus").
    # „Anbieten, nicht erzwingen" heißt dann aber, dass es hier auch angeboten
    # werden muss.
    "arrange.below_bed": (PLACE_ON_BED,),
    # **Beide Wege, und der zweite ist der, den Robert verlangt hat**
    # (24.08.2026): „bei an bett ausrichten sollten alle ans bett richtig
    # angeordnet werden wie fürs drucken." *Auf das Bett setzen* senkt diesen
    # einen Körper ab und lässt x und y, wie sie sind — das ist die genaue
    # Antwort auf ein Schweben. *Auf dem Bett anordnen* legt die ganze Szene
    # druckfertig, und das ist die Antwort, wenn mehr als einer in der Luft
    # hängt. Bei ``below_bed`` steht der zweite Knopf bewusst nicht: Ein Körper
    # unter der Platte ist der Normalfall eines frisch geladenen Modells, und
    # dort soll ein Klick genau das tun, was er sagt.
    "arrange.above_bed": (PLACE_ON_BED, ARRANGE_ON_BED),
    "arrange.off_the_plate": (ARRANGE_ON_BED,),
    # Auto Split fand keine belastbare Naht. Noch einmal automatisch zu
    # teilen wäre dieselbe Sackgasse; die gezeichnete Linie gibt die
    # Entscheidung sichtbar zurück. Druckerprofil und Details ergänzen nur,
    # wo Bauraum oder Suchgrenze die Antwort verändern können.
    "split.no_plane": (SPLIT_ALONG_LINE, CHOOSE_PRINTER, SHOW_DETAILS),
    "split.cut_failed": (SPLIT_ALONG_LINE, SHOW_DETAILS),
    # Die Sperre hat jede Ebene gefressen (RM-080). Der erste Weg ist, sie
    # wieder zu öffnen — der Kunde hat die Suche selbst eingeschränkt —, der
    # zweite die gezeichnete Linie, die an einer Sperre vorbeiführen kann.
    "split.blocked_by_protection": (RELEASE_PROTECTION, SPLIT_ALONG_LINE, SHOW_DETAILS),
    # **Der Satz nennt den Rückweg, und hier steht er als Knopf** (RM-039).
    # „Reparieren Sie es und teilen Sie danach erneut" stand im Befund, seine
    # Geschwister darüber trugen Handlungen, und dieser trug keine — ein Satz
    # ohne Weg nach vorn, und Regel 17 gilt im Bericht so gut wie im Dialog.
    #
    # **Dieselbe Handlung wie bei den anderen „nicht geschlossen"-Befunden**,
    # weil es dieselbe Ursache ist: `SectionResult.capped` ist genau
    # `is_watertight` der Eingabe, das Modell war also schon vor dem Schnitt
    # offen. *Stellen zeigen* steht nicht daneben — der Befund trägt keinen
    # Ort, und ein Knopf, der ins Leere führt, ist schlechter als keiner.
    "split.uncapped": (REPAIR_AND_RETRY,),
    # Dieselbe Ursache beim halben Teilen: das Modell war schon offen.
    "cut_away.uncapped": (REPAIR_AND_RETRY,),
    # **Der Satz nennt den genauen Weg, und hier steht er als Knopf**
    # (RM-246): Das Raster sprang ein, weil der Eingang nicht geschlossen war,
    # und *Erst reparieren, dann neu rechnen* setzt die Reparatur vor den
    # Schritt. Die Ausgabe zu reparieren hülfe nicht — sie ist dicht, nur
    # gerundet.
    "boolean.voxel": (REPAIR_BEFORE_AND_RETRY,),
    "split.too_many_parts": (SPLIT_ALONG_LINE, CHOOSE_PRINTER, SHOW_DETAILS),
    # Die zwei Sätze einer gelungenen Teilung (RM-080, T6/T7): warum die Naht
    # in der Mitte liegt, und dass es nicht mit weniger Stücken geht. Beide
    # sagen, was fertig ist — der nächste Handgriff ist, die Stücke zum Drucken
    # nebeneinander zu legen, und genau der steht als Knopf daneben.
    "split.symmetric": (ARRANGE_ON_BED,),
    "split.fewest_parts": (ARRANGE_ON_BED,),
    # Die Druckdatei ist niedriger als das Modell: CuraEngine schneidet unter
    # ``z = 0`` wortlos ab (gemessen 30.08.2026, 50 statt 100 Schichten). Die
    # Ursache ist dieselbe wie bei ``arrange.below_bed`` — das Teil steckt
    # unter der Platte —, nur festgestellt an der fertigen Datei; die Handlung
    # ist darum dieselbe: aufsetzen und neu slicen.
    "gcode.shorter_than_model": (PLACE_ON_BED,),
    # Körper, die genau aufeinander liegen, sind im Bild einer. Das entsteht
    # auf mehreren Wegen — zweimal *Quader anlegen*, Duplizieren, ein Muster
    # ohne Abstand —, und keiner davon ist ein Fehler: Die Stückzahl gehört in
    # den Stapel, das Verteilen ans Anordnen (§25). *Auf dem Bett anordnen*
    # ist deshalb keine Reparatur, sondern der zweite Halbschritt, den die
    # Operationen bewusst nicht selbst tun — und ohne diesen Knopf muss man
    # ihn kennen, um ihn zu finden.
    "arrange.bodies_in_one_place": (ARRANGE_ON_BED,),
    # **Eine Passung ohne ihr Merkmal nannte den Rückweg und zeigte ihn
    # nicht** (Befund Robert, 18.09.2026). Der Satz sagt „Die Schritte ab dort
    # zurücknehmen und vor der Passung ausführen" — das ist eine gute
    # Erklärung und kein Weg; Regel 17 gilt im Bericht so gut wie im Dialog.
    # *Verlauf zeigen* ist der Weg, den der Satz beschreibt: Dort steht die
    # Reihenfolge, die er meint, und dort lässt sie sich ändern. Der Befund
    # trägt keinen Ort und keine Schrittkennung — eine Passung gehört keinem
    # Schritt —, also steht *Eingabe korrigieren* nicht daneben.
    "fit.missing_feature": (SHOW_HISTORY,),
    # **Derselbe Sachverhalt eine Stufe weiter, und er stand ohne Knopf da.**
    # ``bodies_in_one_place`` meldet Körper, die genau aufeinander liegen;
    # ``collision`` meldet die, die sich teilweise durchdringen. Zwischen
    # beiden liegt kein Unterschied, den der Kunde träfe — er sieht zwei
    # Teile, die am selben Ort stehen, und will sie nebeneinander haben.
    #
    # Gefunden hat es die Nachbarsitzung beim Zählen der Befunde ohne
    # Handlung. Der Familientest daneben sah es nicht: Er gruppiert nach dem
    # Namen **hinter** dem Punkt, und ``collision`` ist damit eine Familie
    # mit einem Mitglied — immer gleich versorgt, immer grün.
    "arrange.collision": (ARRANGE_ON_BED,),
    # Dieselbe Handlung wie bei den Nachbarn: Was aneinander liegt, wird
    # nebeneinander gelegt. Der Befund kommt aus dem Teilen selbst, weil
    # nur die Operation weiß, dass die zwei Körper zusammengehören.
    "prepare.halves_in_place": (ARRANGE_ON_BED,),
    # Derselbe Sachverhalt, nur eine Stufe später gemessen: nicht die Szene
    # ragt hinaus, sondern die **Druckdatei**, die der Slicer daraus gemacht
    # hat (``gcode.analyze(...).extent``). CuraEngine prüft seinen Bauraum nicht.
    # Es hilft dasselbe wie oben — anordnen, und wenn es allein nicht passt,
    # verkleinern.
    "gcode.off_the_bed": (ARRANGE_ON_BED, SCALE_TO_FIT),
    "export.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    "ingest.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    # **Der Satz sagte, dass nichts geschah — und bot nichts an.** „Es gibt
    # sehr kleine Einzelteile. Gelöscht wurde nichts.“ stand ohne Handlung
    # da, während ``repair`` sie mit ``small_components=True`` entfernt.
    # Gemessen am Korpus: zwei von zwanzig Modellen, beide Male eine
    # Warnung ohne Weg.
    "ingest.small_components": (REMOVE_SMALL_PARTS,),
    # **Ein Befund, dessen Handlung nebenan stand.** „Das Modell besteht aus
    # mehreren Teilen." trug nichts, während im selben Bericht „sehr kleine
    # Einzelteile" den Knopf hatte — und *In Einzelteile zerlegen* stand in
    # der Karte unter 24 Handlungen (Bedienweg-Durchsicht 14.09.2026).
    "ingest.multiple_components": (SPLIT_BODIES,),
    # **Der Ausweg stand im Text des einen Befunds und das Ziel im anderen.**
    # Ein fein vernetztes Modell meldet sich zweimal: ``ingest.very_large``
    # nennt „Dreiecke verringern" beim Namen, trägt aber keine Objektkennung —
    # beim Einlesen gibt es noch keine. ``perceive.too_large`` trägt sie und
    # nennt den Ausweg nicht. Keiner der beiden war für sich vollständig, und
    # beide standen ohne Knopf da.
    #
    # Gemessen an ``Wizard+Tower+Staunton+Elegoo.3mf`` (Roberts Downloads,
    # 03.09.2026): 15 Befunde, davon zwölf aus diesen beiden Kennungen über
    # dieselben sechs Körper — und keiner mit einer Handlung. Der Kunde las
    # sechsmal, was hilft, und fand nichts zum Klicken.
    #
    # Den Knopf bekommt der Befund **mit** der Kennung: Ein Klick auf ihn
    # wählt seinen Körper (§2.7), und ``decimate_mesh`` verringert dann genau
    # dessen Dreiecke. Am anderen wäre er eine Handlung ohne Ziel — er landete
    # auf der gerade gewählten Auswahl oder, ohne sie, in einer Meldung.
    # Dieselbe Handlung hängt seit je am geworfenen Fehler der Analysekarten
    # (``app/core/perceive/maps.py``); nur der Befund kannte sie nicht.
    # **Und die ausgelassene Vollerkennung kommt zurück** (§21.1): Bis zur
    # bestätigbaren Grenze nimmt *Alle Merkmale erkennen* die gespeicherte
    # Wahl des Ladeschritts zurück, und die Frage mit Zeitschätzung kommt
    # wieder (``_recognition_reopenable``). Vorher war eine Absage eine
    # Sackgasse bis zum Neuladen der Datei.
    "perceive.too_large": (RECOGNIZE_FULLY, RECOGNIZE_LOCAL, DECIMATE_MESH),
    # **Und seit dem Nachmittag auch der andere.** Der Absatz darüber begründet,
    # warum ``ingest.very_large`` den Knopf **nicht** bekam: Er trug keine
    # Objektkennung, und eine Handlung ohne Ziel landet auf der zufälligen
    # Auswahl. Seit `c45e70e7` trägt er eine — die Auswertung reicht sie nach,
    # wo der Name des Teils genau eine Ausgabe trifft (3d-druck-85). Damit gilt
    # die Begründung von oben für ihn genauso, und ihn jetzt stumm zu lassen
    # wäre derselbe Fehler in neuer Gestalt: Sein Text ist der, der „Dreiecke
    # verringern" beim Namen nennt, und der Knopf stünde an der Zeile daneben.
    #
    # Seit dem 24.09.2026 spricht er nur noch über die Karten (die Erkennung
    # meldet ``perceive.too_large`` selbst), und damit gehört die lokale
    # Erkennung nicht mehr an ihn: Bis 1,5 Millionen Dreiecke ist längst
    # alles erkannt, und darüber steht der Knopf am Befund darunter.
    "ingest.very_large": (DECIMATE_MESH,),
    # **Dritter Melder derselben Sache, und er stand ohne Menü da.** „Nicht
    # geschlossen" meldet der Kern an drei Stellen: beim Einlesen, beim
    # Exportieren und nach jedem Zug des Agenten (``agent.not_watertight``,
    # ``app/core/agent/checks.py``). Zwei trugen die beiden Handlungen, der
    # dritte nicht — wer über den Chat ein Objekt aufriss, bekam den Satz und
    # sonst nichts, obwohl beide Handler gebaut und verdrahtet sind.
    #
    # Er ist dabei der einzige der drei, der seine Objektkennung mitbringt:
    # ``_object_of`` muss hier nicht auf die Auswahl raten.
    "agent.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    # Die Rücknahme-Warnung des Agenten (Gesamtreview H-1): „nimmt auch alle
    # jüngeren mit" braucht den Blick in den Verlauf — dort stehen die
    # Transaktionen, um die es geht. Der Befund existierte im Kern, die
    # Oberfläche kannte ihn nicht.
    "agent.undo_sweeps": (SHOW_HISTORY,),
    # Vierter Melder derselben Sache: eine Netzoperation, die den Körper
    # aufgemacht hat (``mesh_ops._deviation_findings``). Gemessen beim
    # Vereinfachen einer Ente — geschlossen hinein, offen heraus, und im
    # Bericht stand nur, dass sich die Fläche kaum verschoben hat.
    "mesh.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    # Dieselbe Sache aus dem Formen (RM-215): Das Netz ist beim Formen
    # aufgegangen, und der Satz sagt „Reparieren, bevor es weitergeht".
    "sculpt.torn": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    # Der Zwilling daneben: dieselbe Netzoperation, andere Frage — nicht „offen",
    # sondern „in wie viele Teile". Dieselben zwei Handlungen, weil dieselbe
    # Reparatur hilft und die Defektkarte zeigt, wo es auseinanderging.
    "mesh.components_split": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    # Reparieren hat getan, was ohne erfundene Fläche möglich war. Ein
    # zweiter Reparaturlauf und Kanten verfeinern führen von hier nur zurück;
    # die Defektkarte zeigt dagegen die Kanten, die wirklich übrig sind.
    "repair.still_open": (SHOW_LOCATIONS,),
    # Dieselbe Handlung, anderer Grund: Die Defektkarte kennt „verzweigte
    # Kante" als eigene Farbe (`perceive.maps`), und genau dorthin gehört der
    # Kunde bei diesem Befund — suchen würde er sonst ein Loch, das es nicht
    # gibt.
    "repair.still_branching": (SHOW_LOCATIONS,),
    # Ein offener Körper hat kein belastbares Innen, also kann die Prüfung auf
    # Selbstdurchdringungen nicht laufen. Derselbe Ort, aber eine andere
    # Aussage: Dieser Befund erklärt den ausgelassenen Schritt, der Nachbar
    # darüber den verbleibenden Defekt.
    "repair.self_intersections_skipped": (SHOW_LOCATIONS,),
    # **Drei Befunde über die Auswahl, und keiner hatte ein Menü.** Sie
    # tragen alle ihre Schrittkennung, und was hilft, ist dasselbe: andere
    # Objekte wählen. *Eingabe korrigieren* wäre hier nicht nur
    # unverdrahtet, sondern falsch — `field="in"` ist keine Zeile im
    # Formular, und der Dialog öffnete sich auf ein Feld, das es nicht gibt.
    "evaluate.missing_input": (CHANGE_SELECTION,),
    "evaluate.too_few_inputs": (CHANGE_SELECTION,),
    "evaluate.object_count": (CHANGE_SELECTION,),
}

#: Diese Handlungen dürfen nie auf die aktuelle Auswahl zurückfallen. Die
#: Auswertung trägt die Objektkennung an Operationsbefunde nach; fehlt sie
#: trotzdem, wäre „Stellen zeigen" wieder stilles Raten (Regel 21).
_LOCATED_REPAIR_FINDINGS: Final = frozenset(
    {
        "repair.still_open",
        "repair.still_branching",
        "repair.self_intersections_skipped",
        "repair.self_intersections_detected",
        "repair.self_intersections_unresolved",
        "repair.self_intersections_incomplete",
        "repair.self_crossing",
        "repair.no_thickness",
        "repair.normals_inconsistent",
    }
)

#: Kennungen der Befunde, die aus einer Ausnahme einer Operation entstanden
#: sind (``evaluate._finding_from``): ``op.<operation>.<Ausnahmeklasse>``.
_FROM_AN_OPERATION: Final = "op."


def actions_for(finding: Finding) -> tuple[Action, ...]:
    """Was gegen diesen Befund hilft — aus der Tabelle oder aus seiner Herkunft.

    **Der häufigste Befund mit einer offensichtlichen Antwort hatte keine.**
    Eine Operation, deren Werte nicht gehen, wirft keinen Fehlerdialog: Der
    Kern macht daraus einen Befund und hält die Kette an (§15.3). Im Bericht
    stand dann „Der Wert liegt über dem zulässigen Höchstwert" — und der Weg
    zurück zu diesem Wert war, ihn im Verlauf selbst zu finden und
    doppelzuklicken. Das ist entdeckbar, aber es ist nicht der kurze Weg, den
    §2.7 verlangt: was jetzt möglich ist, als anklickbare Handlung.

    Diese Befunde tragen ihre Schrittkennung immer (`_finding_from` setzt sie),
    also gibt es genau einen Schritt zu öffnen, und ``edit_operation`` tut
    danach das Richtige: derselbe Dialog, dieselben Werte, und beim Übernehmen
    wird der Schritt **ersetzt** statt ein zweiter angelegt.

    Als Muster und nicht als Tabellenzeile, weil die Kennung den Namen der
    Operation und der Ausnahme enthält — das sind 86 mal n Zeilen, die alle
    dasselbe sagen würden.
    """
    if finding.code in _LOCATED_REPAIR_FINDINGS and finding.object_id is None:
        return ()
    if finding.suggestions:
        # Im Fehlerdialog schließt „Abbrechen" das Fenster. Im Prüfbericht
        # ist kein Vorgang offen, den dieser Knopf abbrechen könnte; die Zeile
        # selbst bleibt einfach stehen. Dort ist CANCEL deshalb keine
        # Handlung, sondern ein irreführender Knopf ohne Handler.
        return tuple(action for action in finding.suggestions if action.id != CANCEL.id)
    known = FINDING_ACTIONS.get(finding.code)
    if known:
        return known
    if finding.code.startswith(_FROM_AN_OPERATION) and finding.op_id is not None:
        return (CORRECT_INPUT,)
    return ()


def _one_step(widget: QWidget) -> AbstractContextManager[None]:
    """Die Sammlung der Sitzung, in deren Fenster das Panel steckt (RM-372).

    Ohne Fenster mit Sitzung — ein Panel für sich, etwa in einem Test — gibt
    es nichts zu sammeln, und jeder Handler schreibt wie bisher selbst.
    """
    session = getattr(widget.window(), "session", None)
    gather = getattr(session, "one_step", None)
    if callable(gather):
        gathering: AbstractContextManager[None] = gather()
        return gathering
    return nullcontext()


def _object_for_finding(finding: Finding, document: Document | None) -> ObjectId | None:
    """Der belegte Körper des Befunds — niemals die aktuelle Auswahl."""
    if finding.object_id is not None:
        return finding.object_id
    if document is None or finding.op_id is None:
        return None
    operation = next((entry for entry in document.ops if entry.id == finding.op_id), None)
    if operation is None or len(operation.inputs) != 1:
        return None
    return operation.inputs[0]


def _local_targets(
    finding: Finding,
    document: Document | None,
    live_objects: Mapping[ObjectId, SceneObject] | None,
    bodies: tuple[ObjectId, ...] = (),
) -> tuple[ObjectId, ...]:
    """Nur die noch vorhandenen Netze der Befundzeile, nie die aktuelle Auswahl."""
    if live_objects is None:
        return ()
    target = _object_for_finding(finding, document)
    candidates = bodies or ((target,) if target is not None else ())
    return tuple(
        dict.fromkeys(
            identifier
            for identifier in candidates
            if identifier in live_objects and live_objects[identifier].kind == "mesh"
        )
    )


def _recognition_reopenable(finding: Finding, document: Document | None) -> bool:
    """Ob sich die ausgelassene Vollerkennung eines Körpers nachholen lässt (§21.1).

    Die Wahl gehört dem **Körper** und steht an seinem Ladeschritt — der
    Befund darf an jedem Folgeschritt stehen: Nach einem Verschieben trägt
    der des Verschiebens den Knopf, und ohne das verschwand der Rückweg mit
    dem ersten Folgeschritt (Review 24.09.2026). **Und nur, wo eine Wahl
    steht** (``history.recognition_reopenable``, dieselbe Auskunft, nach der
    der Befund seinen Satz wählt): Ein Körper, der erst nach dem Laden über
    die Grenze wuchs, bekam den Knopf, und der Klick rechnete neu, ohne dass
    eine Frage kam (Review N3, 25.09.2026). Ein verbrauchter Körper behält
    ihn, wie der Satz ihn behält — die Schritte bis zum Verbrauch lesen seine
    Merkmale. Über der bestätigbaren Grenze gibt es keine Vollerkennung, auch
    nicht nach einer neuen Frage.
    """
    if finding.code != "perceive.too_large" or document is None or finding.object_id is None:
        return False
    triangles = finding.values.get("triangles")
    if not isinstance(triangles, int | float) or triangles > CONFIRMED_FEATURE_LIMIT_TRIANGLES:
        return False
    return recognition_reopenable(document, finding.object_id)


def _repair_was_attempted(finding: Finding, document: Document | None) -> bool:
    """Ob derselbe aktive Zug alle Eingänge unmittelbar davor repariert hat.

    Der Befundtext ist dafür absichtlich ohne Bedeutung: Eine Reparatur kann
    Löcher schließen, nichts finden oder einen anderen Rest melden. In allen
    Fällen wäre derselbe Knopf unmittelbar danach ein Ring. Belegt wird der
    Versuch durch die aktiven Operationskennungen derselben Transaktion.
    """
    if document is None or finding.op_id is None:
        return False
    by_id = {entry.id: entry for entry in document.ops}
    failed = by_id.get(finding.op_id)
    if failed is None or not failed.inputs:
        return False
    transaction = next(
        (entry for entry in document.transactions if finding.op_id in entry.ops), None
    )
    if transaction is None:
        return False
    position = transaction.ops.index(finding.op_id)
    covered: set[ObjectId] = set()
    for op_id in reversed(transaction.ops[:position]):
        operation = by_id.get(op_id)
        if operation is None or operation.op != "repair":
            break
        if len(operation.inputs) == 1:
            covered.add(operation.inputs[0])
    return set(failed.inputs) <= covered


def actions_for_document(
    finding: Finding,
    document: Document | None,
    *,
    stopped_at: OpId | None = None,
    live_objects: Mapping[ObjectId, SceneObject] | None = None,
    bodies: tuple[ObjectId, ...] = (),
) -> tuple[Action, ...]:
    """Nur im aktuellen Dokument ausführbare Handlungen anbieten.

    ``live_objects`` sind die Körper des Ergebnisses samt Art: Die lokale
    Erkennung wird nur an einem vorhandenen Netz angeboten, und eine bloße
    Kennungsmenge hätte sie still aus jeder Zeile genommen.
    """
    offered = list(actions_for(finding))
    if finding.op_id is None:
        # Dieselbe Schranke wie im Fehlerdialog (``dialogs.offered_actions``):
        # *Eingabe korrigieren* öffnet den Schritt des Befunds, und ohne seine
        # Kennung wäre der Knopf einer, der nichts tut (Regel 17). Befunde aus
        # einer Operation tragen sie immer — die Auswertung trägt sie nach.
        offered = [action for action in offered if action.id not in NEEDS_OP]
    if _repair_was_attempted(finding, document) or not repair_is_available(
        document,
        stopped_at=stopped_at,
        op_id=finding.op_id,
        object_id=finding.object_id,
        live_objects=live_objects,
    ):
        offered = [action for action in offered if action.id != REPAIR_AND_RETRY.id]
    if _repair_was_attempted(finding, document) or not (
        finding.op_id is not None
        and repair_is_available(
            document,
            stopped_at=finding.op_id,
            op_id=finding.op_id,
            object_id=None,
        )
    ):
        # Vor den Schritt gehört die Reparatur nur, wo er vorhandene Netze
        # liest — dieselbe Schranke wie beim angehaltenen Schritt.
        offered = [action for action in offered if action.id != REPAIR_BEFORE_AND_RETRY.id]
    if "decimate_to" not in finding.values or not repair_is_available(
        document,
        stopped_at=stopped_at,
        op_id=finding.op_id,
        object_id=None,
    ):
        # *Dreiecke verringern und erneut versuchen* ersetzt den angehaltenen
        # Suffix wie die Reparatur — dieselbe Schranke (lebende Netze, kein
        # Schritt des exakten Kerns), und nur mit der Zahl, an der der Kern
        # nachgezählt hat.
        offered = [action for action in offered if action.id != DECIMATE_AND_RETRY.id]
    if (
        "remesh_to_mm" not in finding.values
        or finding.op_id is None
        or not repair_is_available(
            document,
            stopped_at=finding.op_id,
            op_id=finding.op_id,
            object_id=None,
        )
    ):
        # *Kanten verfeinern und erneut versuchen* dasselbe, in der Gegenrichtung:
        # nur mit der Länge, an der der Kern Verfeinern und Glätten durchgespielt
        # hat, und nur vor einem Schritt, der vorhandene Netze liest — auch vor
        # einem, der durchlief und nur zu viel Volumen kostete
        # (``mesh.smooth_shrank``), wie die Reparatur vor einem gerundeten.
        offered = [action for action in offered if action.id != REMESH_AND_RETRY.id]
    if finding.op_id is None or not repair_is_available(
        document,
        stopped_at=finding.op_id,
        op_id=finding.op_id,
        object_id=None,
    ):
        # *Flächenbearbeitung beenden und erneut versuchen* setzt die Umwandlung
        # vor den Schritt des Befunds — nur, solange er im Verlauf steht und
        # vorhandene Körper liest, dieselbe Schranke wie die Reparatur davor.
        offered = [action for action in offered if action.id != MESH_AND_RETRY.id]
    target = _object_for_finding(finding, document)
    if target is not None and live_objects is not None and target not in live_objects:
        # Der Körper des Befunds ist verbraucht (RM-268): Jede Handlung, die
        # ihn braucht, träfe nichts oder einen anderen (Review R7).
        offered = [action for action in offered if not _needs_live_body(action, finding, document)]
    if target is None:
        offered = [
            action for action in offered if action.id not in {SHOW_LOCATIONS.id, SHOW_LOCATION.id}
        ]
    if target is None or not finding.feature_ids:
        # *Merkmal zeigen* braucht Körper und Merkmal des Befunds.
        offered = [action for action in offered if action.id != SHOW_FEATURE.id]
    if target is None:
        # *Stützbedarf zeigen* fiele sonst auf die gerade gewählte Auswahl
        # zurück (``MainWindow._object_of``) — die Karte eines fremden Körpers
        # unter dem Satz über diesen wäre geraten (Regel 21).
        offered = [action for action in offered if action.id != SHOW_SUPPORT_NEED.id]
    if finding.location is None:
        # Eine Sammelzeile über verschiedene Orte trägt keinen (siehe unten),
        # und ohne Ort hätte der Knopf kein Ziel.
        offered = [action for action in offered if action.id != SHOW_LOCATION.id]
    if any(action.id == RECOGNIZE_LOCAL.id for action in offered) and not _local_targets(
        finding, document, live_objects, bodies
    ):
        offered = [action for action in offered if action.id != RECOGNIZE_LOCAL.id]
    if not _recognition_reopenable(finding, document):
        offered = [action for action in offered if action.id != RECOGNIZE_FULLY.id]
    elif finding.severity == "warning":
        # Am Speicherfehler ist die Vollerkennung der Lauf, der gerade am
        # Speicher scheiterte: Sie bleibt als Weg, aber als letzter und nicht
        # hervorgehoben; vorn stehen, was der Satz nennt.
        offered = [action for action in offered if action.id != RECOGNIZE_FULLY.id] + [
            dataclasses.replace(RECOGNIZE_FULLY, primary=False)
        ]
    if _import_group_for(finding, document, live_objects or ()):
        offered = [
            dataclasses.replace(action, label=tr("Gemeinsam auf das Bett setzen"))
            if action.id == PLACE_ON_BED.id
            else action
            for action in offered
        ]
    return tuple(offered)


def handled_actions(
    finding: Finding,
    document: Document | None,
    handlers: Mapping[str, Callable[[AppError], None]],
    *,
    stopped_at: OpId | None = None,
    live_objects: Mapping[ObjectId, SceneObject] | None = None,
    bodies: tuple[ObjectId, ...] = (),
) -> list[Action]:
    """Die Handlungen einer Befundzeile, die das Fenster wirklich ausführt (Regel 17).

    **Ein angehaltener Schritt ohne einen einzigen Knopf war eine Sackgasse.**
    Der Kern gibt vielen Absagen Räte mit, die nur der Kunde selbst ausführen
    kann — „Weniger Durchgänge nehmen.", „Eine gröbere Steigung nehmen.",
    „Ein Bild wählen." (``dialogs.unhandled_advice``). Der Fehlerdialog zeigt
    sie als Sätze; der Prüfbericht zeigt nur Knöpfe, und so stand dort die
    Zeile eines angehaltenen Schritts ohne Knopf und ohne Rat (Durchsicht
    0.5.1, gezählt: 28 solche Kennungen an 48 Stellen des Kerns). Der Weg
    zurück war, den Schritt im Verlauf selbst zu finden und doppelzuklicken.

    Bleibt an einem Befund aus einer Operation nichts übrig, steht deshalb
    *Eingabe korrigieren* da — derselbe Rückfall wie für einen solchen Befund
    ganz ohne Vorschlag (:func:`actions_for`): Der Schritt geht auf, mit dem
    Cursor im Feld, das die Absage nennt, und dort wird ausgeführt, was der
    Rat sagt. Der Rat selbst steht in der Kurzhilfe des Knopfs
    (``ReportPanel._show_offers``).
    """
    offered = [
        action
        for action in actions_for_document(
            finding,
            document,
            stopped_at=stopped_at,
            live_objects=live_objects,
            bodies=bodies,
        )
        if action.id in handlers
    ]
    if (
        not offered
        and finding.op_id is not None
        and finding.code.startswith(_FROM_AN_OPERATION)
        and CORRECT_INPUT.id in handlers
    ):
        offered = [CORRECT_INPUT]
    return offered


def _import_group_for(
    finding: Finding, document: Document | None, live_objects: Collection[ObjectId]
) -> tuple[ObjectId, ...]:
    """Nur Bettbefunde eines unveränderten Imports erhalten die gemeinsame Handlung."""
    if document is None or finding.code not in {"arrange.below_bed", "arrange.above_bed"}:
        return ()
    if not isinstance(live_objects, Mapping):
        return ()
    target = _object_for_finding(finding, document)
    return imported_group_for_bed(document, target, live_objects) if target else ()


def as_error(
    finding: Finding,
    document: Document | None = None,
    *,
    import_group: tuple[ObjectId, ...] = (),
) -> AppError:
    """Einen Befund so verpacken, dass die Fehlerhandlungen ihn annehmen.

    Die Handler des Fensters (``error_handlers``) arbeiten auf einem
    ``AppError``, weil sie aus dem Fehlerdialog kommen. Ein Befund ist keiner
    — er trägt aber genau die zwei Angaben, die sie lesen: den Körper und die
    Zahlen. Sie zweimal zu schreiben, einmal für Fehler und einmal für
    Befunde, hieße zwei Wahrheiten über dieselbe Handlung.

    **Mit dem Grund, nicht nur mit dem Titel.** ``_finding_from`` legt das
    unübersetzte Detail eines Fehlers — bei einem Programmfehler Ausnahmeart
    und -text — in ``values["detail"]``; ohne diese Zeile kam beim
    Fehlerbericht ein Fehler mit dem Titel an, und ``str(error)`` schrieb in
    den Bericht S-20260906-9ca141 nur „Im Programm ist ein unerwarteter
    Fehler aufgetreten".
    """
    detail = finding.values.get("detail")
    values: dict[str, Any] = dict(finding.values)
    if import_group:
        # Ausschließlich der beim Angebotsaufbau aus der tatsächlichen Szene
        # gebundene Umfang. Historische Ausgaben sind keine lebenden Körper.
        values["import_group"] = import_group
    if finding.feature_ids:
        # *Merkmal zeigen* wählt es; der Fehler kennt sonst kein Merkmal.
        values.setdefault("feature_ids", tuple(finding.feature_ids))
    if finding.location is not None:
        # *Stelle zeigen* fliegt dorthin; der Fehler kennt sonst keinen Ort.
        values.setdefault("location", tuple(float(value) for value in finding.location))
    if finding.outline:
        # Und den Rand, wo die Stelle eine Fläche ist (``Finding.outline``).
        values.setdefault("outline", finding.outline)
    return AppError(
        title=finding.message,
        detail=str(detail) if detail is not None else None,
        suggestions=finding.suggestions,
        object_id=_object_for_finding(finding, document),
        op_id=finding.op_id,
        values=values,
    )


def _severity_label(severity: str) -> str:
    """Der Schweregrad als Wort — die Filterzeile zeigt beides (Regel 18)."""
    return {
        "error": tr("Fehler"),
        "warning": tr("Warnung"),
        "info": tr("Hinweis"),
    }.get(severity, severity)


def origin_label(source: str) -> str:
    """Hier geschätzt oder aus G-Code gemessen — nie verwechselt (§22.5)."""
    return tr("intern geschätzt") if source == "internal" else tr("aus G-Code")


def finding_meta(finding: Finding, place: str) -> str:
    """Folge, Ort und Grundlage eines Befunds als eine Zeile (RM-508, Produktkompass 4.3).

    „Hinweis · Dose · intern geschätzt“ — das Wort für die Schwere ist die
    Folge für das Druckziel (:func:`print_contract.handoff_state` leitet den
    Status aus genau ihr ab), der Ort ist der Körper, die Grundlage die
    Herkunft der Aussage (§22.5). Drei Sätze darunter („Folge: Ein Hinweis;
    die Übergabe hängt nicht davon ab.“) sagten dasselbe in 18 Wörtern
    (Entscheidung Robert, 05.10.2026). Ohne Ort fällt er weg.
    """
    parts = (_severity_label(finding.severity), place, origin_label(finding.source))
    line = " · ".join(part for part in parts if part)
    # Die Kataloge schreiben die Schwere klein („note“), weil sie im Satz
    # steht; am Zeilenanfang steht sie groß, in jeder Sprache.
    return line[:1].upper() + line[1:]


def finding_place(
    finding: Finding,
    bodies: Sequence[str],
    live: Mapping[ObjectId, SceneObject],
    names: Mapping[str, str],
) -> tuple[str, str]:
    """Wo ein Befund liegt, und wie der Knopf heißt, der es zeigt — oder ``""``.

    ``bodies`` sind die noch vorhandenen Körper einer Sammelzeile. Ein Ort, den
    der Befund nicht trägt, wird nicht erfunden: Ohne Stelle zeigt der Knopf
    den Körper, ohne vorhandenen Körper gibt es keinen Knopf.
    """
    if len(bodies) > 1:
        return ", ".join(names.get(key, key) for key in bodies), tr("Körper zeigen")
    body = live.get(finding.object_id) if finding.object_id else None
    if body is None:
        return (tr("Körper nicht mehr vorhanden") if finding.object_id else ""), ""
    located = finding.location is not None or bool(finding.feature_ids) or bool(finding.outline)
    return str(body.name), tr("Stelle zeigen") if located else tr("Körper zeigen")


def _last_widget(row: QBoxLayout) -> QToolButton:
    """Die Überschrift, die :func:`collapsible` eben in ``row`` gelegt hat."""
    item = row.itemAt(row.count() - 1)
    widget = item.widget() if item is not None else None
    assert isinstance(widget, QToolButton)
    return widget


#: Werte, die in der Zeile eines Befunds stehen — die, nach denen man beim
#: Lesen zuerst fragt: welcher Körper, und wie viel.
#:
#: Der Wert dahinter ist die Einheit, die dazugehört, oder ``""`` für Zahlen,
#: die für sich stehen. Sie steht **hier** und nicht im Kern: dort ist eine
#: Zahl ein Wert, und wie sie geschrieben wird, entscheidet die Anzeige —
#: dieselbe Trennung wie zwischen ``format_length`` und ``length``.
#: **Eine Auswahl, keine Einheitentabelle.** Bis zum 27.08.2026 stand hier je
#: Schlüssel die Einheit, und damit entschied diese Tabelle ein zweites Mal,
#: was ``labels._VALUE_UNITS`` für den Tooltip schon entschieden hatte — mit
#: abweichendem Ergebnis und ohne die Umschaltung auf Zoll. Sie sagt jetzt nur
#: noch, **welche** Werte in die Zeile kommen und in welcher Reihenfolge;
#: **wie** sie geschrieben werden, sagt ``value_text``.
_LINE_VALUES: tuple[str, ...] = (
    "object",
    # „Ein Merkmal hat keinen Nachfolger mehr" — welches? Nach dem Einsetzen
    # eines Bausteins standen sechs wortgleiche Zeilen im Bericht, und nichts
    # daran war unterscheidbar; die Kennung stand längst im Befund, nur nie in
    # der Zeile. Derselbe Fund wie bei den zwei ausgehöhlten Klötzen darunter,
    # gefunden am 25.08.2026 bei der Verifikation im echten Fenster.
    "feature",
    "a",
    "b",
    "excess",
    "shared",
    # Aushöhlen sagte „Die Wandstärke stimmt im Rahmen des Rasters", ohne die
    # Wandstärke zu nennen — und wie viel Material dabei gespart wurde, also
    # die Frage, für die man die Operation überhaupt aufruft, stand nur im
    # Tooltip.
    "wall_mm",
    "removed_cm3",
    # Die Formabweichung nennt ihr Maß in der Zeile — der Befund steht nur,
    # wo belegte Punkte messbar neben der Form liegen (``check_form_deviation``).
    "deviation_mm",
    # Die Schichtanalyse im Bericht (§22.2): wie viel Stütze unter einer Insel
    # oder was eine andere Lage spart, wie weit eine Decke frei spannt, wie
    # schmal die dünnste Stelle ist. Ohne die Zahl ist die Zeile ein Satz
    # ohne Maß, und das Maß ist, wonach man entscheidet.
    "support_cm3",
    "saved_percent",
    "span_mm",
    "width_mm",
)


#: Werte der Zeile, die selbst Namen sind — die beiden Körper einer
#: Überschneidung. Jeder andere Wert trägt seine Beschriftung (:func:`_line_for`).
_NAMES_IN_THE_LINE: Final = frozenset({"a", "b"})


def _op_title(name: str) -> str:
    """Der Titel einer Operation, wie das Menü ihn zeigt.

    Der Verlauf schrieb den Registernamen: zwischen „Grundkörper" und
    „Versteifung" stand `insert_screw_hole`. Beides sind dieselben Schritte,
    nur kommt der eine Text aus der Transaktion und der andere aus dem Code.

    Eine Operation, die das Register nicht kennt, behält ihren Namen — eine
    Projektdatei aus einer neueren Version ist kein Grund, eine Zeile leer zu
    lassen.
    """
    try:
        return str(REGISTRY.get(name).title)
    except AppError:
        return name


def _parameter_value(parameter: Parameter) -> str:
    """Der Wert eines Projektmaßes, wie die Leiste ihn schreibt — Länge in der Anzeigeeinheit."""
    if (parameter.unit or "mm") == "mm":
        return length(parameter.value)
    return localised(f"{parameter.value:g}") + (f" {parameter.unit}" if parameter.unit else "")


def _changed_parameters(transaction: Transaction) -> str:
    """Was eine Parameteränderung im Verlauf geändert hat.

    Die Zeile heißt nach der Beschriftung der Leiste (``Session._parameter_title``);
    die Kurzhilfe nennt Wert und geänderte Grenzen davor und danach. Leer, wenn
    die Transaktion keine Projektmaße trägt.
    """
    changes = transaction.changes
    after = changes.after.parameters if changes is not None else None
    if not after:
        return ""
    before = (changes.before.parameters if changes is not None else None) or {}
    lines: list[str] = []
    for name, now in after.items():
        was = before.get(name)
        shown = now or was
        if shown is None:
            continue
        label = str(shown.title or name)
        if now is None:
            lines.append(
                tr(
                    "{name}: {before} → {after}",
                    name=label,
                    before=_parameter_value(shown),
                    after="–",
                )
            )
        elif was is None:
            lines.append(tr("{name}: {value}", name=label, value=_parameter_value(now)))
        else:
            if not is_close(was.value, now.value):
                lines.append(
                    tr(
                        "{name}: {before} → {after}",
                        name=label,
                        before=_parameter_value(was),
                        after=_parameter_value(now),
                    )
                )
        if now is None:
            continue
        for bound, title in (
            ("minimum", tr("Untergrenze")),
            ("maximum", tr("Obergrenze")),
        ):
            previous = getattr(was, bound) if was is not None else None
            current = getattr(now, bound)
            changed = (previous is None) != (current is None) or (
                previous is not None and current is not None and not is_close(previous, current)
            )
            if not changed:
                continue
            before_parameter = was if was is not None else now
            before_text = (
                _parameter_value(dataclasses.replace(before_parameter, value=previous))
                if previous is not None
                else "–"
            )
            after_text = (
                _parameter_value(dataclasses.replace(now, value=current))
                if current is not None
                else "–"
            )
            lines.append(
                tr(
                    "{name} · {bound}: {before} → {after}",
                    name=label,
                    bound=title,
                    before=before_text,
                    after=after_text,
                )
            )
    return "\n".join(lines)


def _op_icon_name(name: str) -> str:
    """Das Symbol einer Operation — ihr eigenes oder das ihrer Kategorie.

    Dieselbe Quelle, aus der Menü und Katalog ihre Zeichen holen
    (:func:`icons.icon_name_for`). Der Verlauf trug bisher keine: siebzehn
    Kategoriesymbole lagen bereit, und die Liste, an der ein Kunde seine
    Arbeit entlangliest, war eine reine Textspalte.

    Eine Operation, die das Register nicht kennt, bekommt keines statt eines
    falschen — dieselbe Zurückhaltung wie bei ihrem Titel.
    """
    try:
        return icon_name_for(REGISTRY.get(name))
    except AppError:
        return ""


def _identity(finding: Finding) -> tuple[Any, ...]:
    """Woran zwei Befunde derselbe sind.

    Der Code allein reicht nicht — zwei Körper stehen aus verschiedenen Gründen
    über den Bauraum hinaus, und das sind zwei Zeilen. Die Werte gehören dazu:
    ändert sich die Zahl, ist es eine neue Aussage über dieselbe Sache.
    """
    return (
        finding.code,
        finding.object_id,
        str(finding.message),
        tuple(sorted((key, str(value)) for key, value in finding.values.items())),
    )


def _line_for(finding: Finding, names: Mapping[str, str] | None = None) -> str:
    """Die Zeile eines Befunds: die Meldung und wovon sie handelt.

    „Zwei Objekte überschneiden sich" — welche zwei? „Ein Objekt steht über den
    Bauraum hinaus" — welches, und um wie viel? Die Antworten standen schon in
    ``values``, aber nur im Tooltip: man musste wissen, dass dort etwas ist, und
    mit der Maus hinfahren. Jetzt stehen sie in der Zeile.

    Nur die fünf Felder, nach denen man beim Lesen zuerst fragt. Alle wären
    wieder ein Tooltip, nur breiter — und der bleibt ohnehin daneben stehen.

    Dazu ``object_id``, wenn der Befund eines trägt und es nicht ohnehin unter
    den Werten steht. Das ist der Fall, den die Liste bis hierher nicht sah:
    ein Befund je Körper, zweimal derselbe Satz, und nichts daran
    unterscheidbar — zwei ausgehöhlte Klötze meldeten „Ausgehöhlt. Die
    Wandstärke stimmt im Rahmen des Rasters." als zwei Zeilen, die aussahen wie
    ein Fehler in der Anwendung.

    ``names`` löst die Kennung zum Namen auf. Eine verbrauchte Kennung ohne
    belegten Namen bleibt in den Befunddaten statt als Zusatz am Kundensatz.
    """
    extra: list[str] = []
    if finding.code in _LOCATED_REPAIR_FINDINGS and "open_edges" in finding.values:
        extra.append(value_line("open_edges", finding.values["open_edges"]))

    extra.extend(
        [
            # Über ``localised_value``: Ein Befund trägt neben Zahlen auch Pfade,
            # Adressen und Endungen, und ``localised`` tauschte dort jeden Punkt
            # gegen ein Komma — „sources/1_cube_clean,stl".
            #
            # Die Merkmalskennung bekommt ihr Wort davor: Neben dem aufgelösten
            # Objektnamen läse sich ein nacktes „face_3" wie ein zweiter Name.
            # Bei einem verlorenen Formdetail bleibt sie ganz im Tooltip: Dort
            # hilft sie der Diagnose, in der Kundenaussage wäre sie internes
            # CAD-Vokabular ohne Handlung.
            (
                f"{tr('Merkmal')} {finding.values[key]}"
                if key == "feature"
                # **Dieselbe Quelle wie der Tooltip daneben**, und zwar seit der
                # Messung vom 27.08.2026: Die Zeile trug ihre Einheit selbst und
                # schrieb „1,2 mm · 3,456 cm³", während der Tooltip an demselben
                # Eintrag „Wandstärke: 1,20 mm · Entfernt: 3,5 cm³" sagte — zwei
                # Zahlen für denselben Wert, sichtbar in einem Blick. Und in Zoll
                # blieb die Zeile bei Millimetern stehen, weil eine feste Einheit
                # nicht umschalten kann. ``value_text`` beantwortet beides und
                # lässt Pfade, Kennungen und Versionsnummern unangetastet.
                else value_text(key, finding.values[key])
                if key in _NAMES_IN_THE_LINE
                # **Je Wert ein Name** (RM-508): „— Deckel · 0 mm³ · 100 %“ ließ
                # raten, welche Zahl was ist; jetzt „Stützen: 0 mm³ · Gespart:
                # 100 %“, mit der Beschriftung der Einzelheiten.
                else value_line(key, finding.values[key])
            )
            for key in _LINE_VALUES
            if key in finding.values
            and key != "object"
            and not (finding.code in {"perceive.mended", "perceive.orphaned"} and key == "feature")
        ]
    )
    if "object" in finding.values:
        named = _object_named(finding, names or {})
        if named:
            extra.insert(0, named)
    if finding.code in PART_SETTING_CODES and "setting" in finding.values:
        extra.append(_setting_line(finding))
    if finding.object_id and "object" not in finding.values:
        identifier = str(finding.object_id)
        name = (names or {}).get(identifier, "")
        if name and name != identifier and name not in str(finding.message):
            extra.insert(0, name)
    if not extra:
        return str(finding.message)
    return f"{finding.message} — {' · '.join(extra)}"


def _object_named(finding: Finding, names: Mapping[str, str]) -> str:
    """Der Körper aus ``values["object"]`` beim Namen — nie als Kennung (RM-396).

    Der Wert ist je nach Befund ein Name (das Teil einer 3MF) oder eine
    Kennung (die Umwandlung in ein Dreiecksmodell nennt ihre Ausgabe). Eine
    Kennung ohne belegten Namen bleibt in den Einzelheiten; ein Name, der im
    Satz schon steht, wird nicht wiederholt.
    """
    value = finding.values["object"]
    text = str(value)
    identifiers = {finding.object_id, str(finding.values.get("input_object", "")), *names}
    if text in identifiers:
        named = names.get(text, "")
        text = named if named and named != str(value) else ""
    else:
        text = value_text("object", value)
    if not text or text in str(finding.message):
        return ""
    return text


def _setting_line(finding: Finding) -> str:
    """Die Einstellung eines Teils, wie der Druckdialog sie zeigt: „Stützen: Automatisch".

    Der Befund trägt Punktpfad und Rohwert (``writer.PART_SETTING_CODES``);
    beides stand bis zur Durchsicht 0.5.1 (B4) so im Tooltip —
    „Einstellung: support.style", „Wert: True". Beschriftung und Anzeige kommen
    aus derselben Quelle wie im Dialog, damit der Bericht nach dem Export den
    Wert nennt, den der Kunde dort übernommen hat.
    """
    from app.ui.print_settings_dialog import setting_title, shown_value

    path = str(finding.values["setting"])
    return tr(
        "{name}: {value}",
        name=setting_title(path),
        value=shown_value(path, finding.values.get("value")),
    )


def _value_lines(finding: Finding) -> list[str]:
    """Die Werte eines Befunds als „Beschriftung: Wert" — eine Einstellung je
    Teil mit Feldname und Wert statt Pfad und Rohwert (:func:`_setting_line`).

    Was dem Code gilt (``dialogs.ADDRESS_VALUES``: das Feld, in das ein Knopf
    den Cursor setzt), steht nicht da — „Feld: largest“ ist keine Auskunft.
    """
    if finding.code in PART_SETTING_CODES and "setting" in finding.values:
        return [_setting_line(finding)] + [
            value_line(key, value)
            for key, value in finding.values.items()
            if key not in ("setting", "value") and key not in ADDRESS_VALUES
        ]
    # Die Einheit gehört an die Grenze, nicht in eine eigene Zeile (RM-359 F7).
    unit = unit_of(finding.values)
    return [
        value_line(key, value, unit)
        for key, value in finding.values.items()
        if key not in ADDRESS_VALUES and not (unit and key == "unit")
    ]


def _origin_text(created_by: int | None, document: Document | None) -> str:
    """Aus welcher Operation und Transaktion ein Körper stammt (§18.8).

    Die Transaktion ist die Einheit, die der Verlauf zeigt und die ein Undo
    nimmt (§15.5) — sie zu nennen verbindet den Körper im Baum mit der Zeile
    im Verlauf. Fehlt das Dokument, bleibt die Operationsnummer.
    """
    if created_by is None:
        return ""
    text = f"{tr('aus Operation')} {step_number(document, created_by)}"
    if document is None:
        return text
    for transaction in document.transactions:
        if created_by in transaction.ops:
            return f"{text} · {transaction.title}"
    return text


def _feature_tip(feature_id: str, feature: Feature, document: Document | None) -> str:
    """Was dieses Merkmal ist, woher es kommt, und wie es heißt.

    Hier standen die Kennung und die Provenienz — die zwei technischsten
    Angaben, die es über ein Merkmal gibt: ``hole_1 · part:m3_screw``. Die
    Frage, die jemand stellt, der auf eine Zeile im Baum zeigt, ist eine
    andere, und Robert hat sie am 26.08.2026 wörtlich gestellt: *was ist das
    eigentlich*. Sie wird jetzt zuerst beantwortet.

    Die Reihenfolge ist die, in der man liest: **was** es ist samt seinem Maß,
    **woher** es kommt (der Schritt, den „Diesen Schritt ändern" öffnet), und
    zuletzt die **Kennung** — gebraucht wird sie nur, wenn man sie in ein
    Parameterfeld schreibt, und dafür genügt sie am Ende.

    **Es ist zugleich die zweite Kodierung, die Regel 18 verlangt.** Die
    Merkmalskarte *färbt*, was als Bohrung und was als Tasche gilt; ohne ein
    Wort daneben wäre die Farbe die einzige Aussage darüber.
    """
    lines = [feature_label(feature_id, feature)]
    if explanation := feature_measure_tip(feature):
        lines.append(explanation)
    # Erkannt oder erzeugt — das ist der Grund, aus dem es überhaupt da ist.
    # ``created_by`` trennt beides sauber: Was die Erkennung im Netz gefunden
    # hat, trägt keinen Schritt (§21.2).
    origin = _origin_text(feature.created_by, document)
    lines.append(origin or str(tr("Von der Erkennung gefunden")))
    lines.append(feature_id)
    return "\n".join(lines)


#: Wo am Gruppenknoten die Nummer seines Schrittes steht.
#:
#: Eine eigene Rolle und nicht ``UserRole``: Dort steht die Kennung des
#: Körpers, und die trägt der Knoten wie jede Zeile darunter — wer ihn
#: anklickt, hat das Teil gewählt. Die Schrittnummer ist eine zweite Auskunft
#: über dieselbe Zeile.
_STEP_ROLE = Qt.ItemDataRole.UserRole + 2


#: Welche Operationen ihre Merkmale als **ein Ding** vertreten lassen.
#:
#: Die Kategorie ``parts`` ist der Regelfall: Ein Schlüsselloch bringt zwölf
#: Merkmale mit, und wer eine Schlitzkante anklickt, hat das Schlüsselloch
#: gemeint. Der **Organizer** ist derselbe Fall mit einer anderen Kategorie —
#: er steht unter ``primitive``, weil er aus eigenen Maßen entsteht, und
#: bringt je Fach und je Trennwand Merkmale mit. Wer eine Trennwand anklickte,
#: bekam die Handlungen einer Fläche: Bohren, Tasche, Fläche versetzen. Keine
#: davon meint die Trennwand, und ihre Lage steht in keinem Parameter — sie
#: folgt aus den Fachmaßen (Befund Robert, 18.09.2026: „Baustein verschieben
#: bei Trennwand organizer keine Wirkung" und „keine Ahnung wie man
#: hinkommt").
#:
#: **Und die Ausnahme gilt der Rolle, nicht dem Schritt.** Der erste Anlauf
#: nannte nur den Operationsnamen — und traf damit **alle** vierunddreißig
#: Merkmale mit Provenienz: die vierundzwanzig Trennwände, aber auch die neun
#: Fachböden und den Innenboden, mit 26 674 mm² die größte Fläche des Teils.
#: Genau die sind Arbeitsflächen: Auf sie setzt man einen Baustein, dort bohrt
#: man, dort liegt Filament. Gemessen am gebauten Fenster verloren sie alle
#: acht Listenoperationen, die drei Hauptaktionen, den Bausteinkatalog und die
#: Filamentzuweisung — ohne Ersatzweg, denn die vier Operationsmenüs sind am
#: 11.09.2026 in diese Karte gewandert. Ein Fix, der mehr wegnimmt als er
#: behebt, ist keiner.
#:
#: Ein Name und eine Rolle, keine zweite Kategorie: Der Organizer ist heute
#: die einzige Operation außerhalb von ``parts``, die benannte Merkmale in
#: dieser Zahl erzeugt. Eine eigene Kategorie zöge Menüort und Katalogkachel
#: mit, und beides soll bleiben.
SPEAKS_FOR_ITS_FEATURES: Final[dict[str, frozenset[str]]] = {
    "create_organizer": frozenset({"divider"}),
}


def part_step_of(
    created_by: int | None,
    document: Document | None,
    feature: Feature | None = None,
) -> tuple[Any, Any] | None:
    """Der Schritt und sein Registereintrag, wenn er einen **Baustein** setzte.

    Sonst ``None``. Gefragt wird über die Kategorie ``parts`` und nicht über
    den Namen der Operation: ``drill_hole`` erzeugt ebenfalls Merkmale mit
    Provenienz und ist kein Baustein, und ein Namensmuster wie ``insert_*``
    schwiege beim nächsten Baustein, der anders heißt.

    **Dazu die Ausnahme** :data:`SPEAKS_FOR_ITS_FEATURES`, und sie braucht das
    **Merkmal**: Sie gilt einer Rolle, nicht dem ganzen Schritt. Ohne
    ``feature`` gibt es keine Rolle zu prüfen, und dann gilt sie nicht — der
    Objektbaum fragt so und gruppiert deshalb weiter nur echte Bausteine.

    **Zwei Stellen fragen das, und sie fragen es hier.** Der Objektbaum
    gruppiert danach (:func:`_part_group`), und das Fenster entscheidet danach,
    ob rechts die Handlungen des Bausteins oder die des Merkmals stehen. Zwei
    Rechnungen für dieselbe Frage laufen beim nächsten Nachbessern
    auseinander — diese hier stand zweimal, bis es jemand nachgezählt hat.
    """
    if created_by is None or document is None:
        return None
    for entry in document.ops:
        if entry.id != created_by:
            continue
        try:
            spec = REGISTRY.get(entry.op)
        except AppError:
            return None
        if spec.category == "parts":
            return (entry, spec)
        rollen = SPEAKS_FOR_ITS_FEATURES.get(spec.name)
        if rollen is None or feature is None:
            return None
        rolle = str(feature.params.get("organizer_role", ""))
        return (entry, spec) if rolle in rollen else None
    return None


def texture_steps_of(
    object_id: str,
    feature: Feature,
    document: Document,
    *,
    completed: Collection[int] | None = None,
) -> tuple[list[Any], bool]:
    """Texturschritte nach belegter Herkunft; sonst ausdrücklich am Körper wählbar."""
    from app.core.types import FeatureRef

    # Rückwärts am jeweiligen Dokumentstand: Eine spätere Textur auf dem
    # zurückgebliebenen Original gehört nicht zu seinem früher abgetrennten Teil.
    wanted = {object_id}
    names = {object_id: {feature.id}}
    candidates = []
    later_change = False
    source_overridden = False
    for operation in reversed(document.ops):
        if operation.suppressed is not None:
            continue
        if completed is not None and operation.id not in completed:
            continue
        if not wanted.intersection(operation.outputs):
            continue
        inherited = {name for output in operation.outputs for name in names.pop(output, set())}
        if operation.op == "resize_feature" and operation.inputs:
            named = str(operation.params.get("at_feature") or "")
            try:
                reference = (
                    FeatureRef.parse(named)
                    if ":" in named
                    else FeatureRef(operation.inputs[0], named)
                )
            except ValueError:
                reference = None
            if (
                reference is not None
                and reference.object_id in operation.inputs
                and reference.feature_id in inherited
            ):
                later_change = True
        if operation.op == "apply_texture":
            candidates.append(operation)
            if operation.id == feature.created_by:
                source_overridden = later_change
        wanted.difference_update(operation.outputs)
        wanted.update(operation.inputs)
        # Zusätzliche Eingänge erhalten beim Vereinigen einen Namensraum.
        # Rückwärts darf der alte Name nur auf seinen wirklichen Körper führen.
        scoped = (
            operation.inputs[1:]
            if operation.op in {"union_objects", "intersect_objects"}
            else operation.inputs
            if operation.op == "split_bodies"
            else ()
        )
        for name in inherited:
            source = next((item for item in scoped if name.startswith(f"{item}.")), None)
            if source is not None:
                names.setdefault(source, set()).add(name[len(source) + 1 :])
            else:
                unscoped = (
                    operation.inputs[:1]
                    if operation.op in {"union_objects", "intersect_objects"}
                    else operation.inputs
                )
                for source in unscoped:
                    names.setdefault(source, set()).add(name)
    candidates.reverse()
    proven = [operation for operation in candidates if operation.id == feature.created_by]
    if proven:
        # Ein alter Texturschritt kann auch einzelne Zell- oder Restflächen
        # tragen. Erst ein belegtes Muster meint unmittelbar die Textur.
        # Nach einer späteren Merkmalsänderung zeigt das normale Panel die
        # heutigen Maße; der Erzeugerschritt bleibt separat erreichbar.
        return proven, (
            feature.kind == "pattern"
            and feature.recognised
            and bool(feature.face_indices)
            and not source_overridden
        )
    # Die gewählte Fläche belegt keine Wirkung des historischen Schritts.
    # Er bleibt ausdrücklich wählbar, auch wenn sein Muster nicht mehr besteht.
    return (candidates, False) if feature.kind in {"face", "pattern"} else ([], False)


def _part_group(created_by: int | None, document: Document | None) -> tuple[str, int] | None:
    """Titel und Nummer für das Dach im Objektbaum.

    Gruppiert wird nur nach Bausteinen, und das hat einen Grund: Ein Baustein
    ist eine Sache mit einem Namen, die der Kunde als Ganzes eingesetzt hat —
    „Lochwand-Einhänger", nicht „drei Flächen und zwei Verrundungen". Eine
    Bohrung dagegen *ist* ein Merkmal; ein Knoten mit genau einem Kind darunter
    wäre eine Ebene, die nichts ordnet.
    """
    found = part_step_of(created_by, document)
    return (str(found[1].title), int(found[0].id)) if found is not None else None


def _feature_item(item: QTreeWidgetItem, feature_id: str) -> QTreeWidgetItem | None:
    """Die Zeile dieses Merkmals — über alle Ebenen unter ``item``.

    Seit die Merkmale eines Bausteins unter seinem Knoten stehen, ist der Baum
    unter einem Körper zwei Ebenen tief. Wer nur die erste absucht, findet ein
    gruppiertes Merkmal nicht mehr.
    """
    for index in range(item.childCount()):
        child = item.child(index)
        if child is None:
            # Der Index liegt durch ``childCount`` im Bereich; der Qt-Stub
            # lässt dennoch ``None`` zu. Ein defensiver Wächter hält beides.
            continue
        if child.data(1, Qt.ItemDataRole.UserRole) == feature_id:
            return child
        deeper = _feature_item(child, feature_id)
        if deeper is not None:
            return deeper
    return None


def _feature_refs_under(item: QTreeWidgetItem) -> list[tuple[str, str]]:
    """Diese Zeile und, was sie bündelt — als Paare aus Körper und Merkmal.

    Der Nachbar von :func:`_feature_item` und aus demselben Grund rekursiv:
    Der Baum ist unter einem Körper zwei Ebenen tief. Eine Dachzeile trägt
    selbst keine Merkmalskennung und liefert deshalb nur ihre Kinder; eine
    Bohrung mit ihrer Senkung darunter liefert beide (Konzept „Ein Ort für die
    Auswahl", E).

    Die Reihenfolge ist die des Baums, und das führende Glied steht vorn — bei
    einer Kette die Bohrung, deren Maße die Felder zeigen.
    """
    found: list[tuple[str, str]] = []
    object_id = item.data(0, Qt.ItemDataRole.UserRole)
    feature_id = item.data(1, Qt.ItemDataRole.UserRole)
    if object_id is not None and feature_id is not None:
        found.append((str(object_id), str(feature_id)))
    for index in range(item.childCount()):
        child = item.child(index)
        if child is None:
            # Wie in ``_feature_item``: Der Index liegt durch ``childCount``
            # im Bereich, der Qt-Stub lässt dennoch ``None`` zu.
            continue
        found.extend(_feature_refs_under(child))
    return found


def _empty_objects_text() -> str:
    """Was in der leeren Objektliste steht.

    Sie war ein stummer Kasten. Ein neues Projekt beginnt genau hier, und wer
    zum ersten Mal davorsitzt, sieht drei leere Flächen und keinen Anfang —
    die Parameterleiste daneben sagt seit jeher, wozu sie da ist.
    """
    return tr(
        "Noch keine Objekte. Über „Erzeugen“ entsteht ein Körper, "
        "„Modell einfügen“ liest eine Datei ein."
    )


def _empty_history_text() -> str:
    """Was im leeren Verlauf steht — und wozu er gut ist."""
    return tr(
        "Noch keine Schritte. Jede Änderung steht hier als eine Zeile "
        "und lässt sich mit Strg+Z zurücknehmen."
    )


#: Die Spalte, in der das Filament einer Zeile steht.
FILAMENT_COLUMN = 2

#: Ihre Breite in Bildpunkten — Farbfeld plus Rand, kein Text.
FILAMENT_WIDTH = 34

#: Kantenlänge des Farbfelds.
FILAMENT_CHIP = 14


def filament_chip(colour: str, assigned: bool, widget: QWidget) -> QIcon:
    """Ein Farbfeld für die Filamentspalte.

    **Zwei Kodierungen, nicht eine** (Regel 18): Ein zugewiesenes Filament
    steht als gefülltes Feld, ein Körper ohne eigenes als leeres mit Rand.
    Wer Farben nicht unterscheidet, sieht am Gefülltsein trotzdem, ob hier
    etwas entschieden wurde.
    """
    # Ein mehrfarbiges Filament kommt als Feldwert mit Leerzeichen an
    # (``filament_picker.slot_colours``): die erste Farbe trägt Rand und
    # Füllung, die weiteren stehen als senkrechte Streifen darin.
    colours = colour.split() or [colour]
    colour = colours[0]
    scale = widget.devicePixelRatioF() or 1.0
    side = int(FILAMENT_CHIP * scale)
    image = QPixmap(side, side)
    image.setDevicePixelRatio(scale)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(colour) if assigned else QColor(colour).darker(140))
        pen.setWidthF(1.5 * scale)
        painter.setPen(pen)
        painter.setBrush(QColor(colour) if assigned else Qt.BrushStyle.NoBrush)
        inset = 1.5 * scale
        chip = QRectF(inset, inset, side - 2 * inset, side - 2 * inset)
        painter.drawRoundedRect(chip, 2.0 * scale, 2.0 * scale)
        if assigned and len(colours) > 1:
            clip = QPainterPath()
            clip.addRoundedRect(chip, 2.0 * scale, 2.0 * scale)
            painter.setClipPath(clip)
            painter.setPen(Qt.PenStyle.NoPen)
            for number, one in enumerate(colours):
                left = chip.left() + chip.width() * number / len(colours)
                right = chip.left() + chip.width() * (number + 1) / len(colours)
                painter.fillRect(QRectF(left, chip.top(), right - left, chip.height()), QColor(one))
    finally:
        painter.end()
    return QIcon(image)


class _ThumbnailWorker(Worker):
    """Zeichnet die Vorschaubilder des Baums — neben dem Fenster, nicht darin.

    Ein Bild kostet an einem gescannten Teil achtzig Millisekunden, und ein
    eingelesenes 3MF bringt Dutzende Körper mit: Am
    ``1-24+scale+polebarn.3mf`` mit 89 Körpern lagen **5,25 s** im
    Qt-Hauptthread, in Schüben von 400 bis 775 ms (16.09.2026, Robert: „bei
    einer auswahl oder hover effekt stockt es auch noch sehr"). Das Zeichnen
    braucht kein Qt — es endet in einer Zeichenkette (:func:`drawing.thumbnail_of`);
    Qt braucht erst das Malen des fertigen SVG, und das ist ein Zehntel davon.

    **Die Punkte und Dreiecke bekommt er als Arrays**, nicht als Netz: Auf
    demselben ``Trimesh`` zu rechnen füllte dessen träge Caches neben dem
    Hauptthread (``wartezeit.md``, „for_a_worker"). Ein Array zu lesen ist
    gefahrlos, solange niemand es ändert — und eine Eingabe ändert in Solidon
    niemand (Regel 3).
    """

    #: Ein fertiges Bild: Stempel und SVG. Einzeln gemeldet, damit die Zeilen
    #: nachkommen, während der Rest noch rechnet.
    drawn = Signal(str, str)

    def __init__(self, jobs: Sequence[tuple[str, Any, Any]], pixels: int, theme: str) -> None:
        super().__init__()
        self._jobs = list(jobs)
        self._pixels = pixels
        self._theme = theme
        self.cancel = CancelSignal()
        """Dieselbe Marke, die auch eine Operation abfragt: Ein neuer
        Szenenaufbau macht jedes noch nicht gezeichnete Bild gegenstandslos."""

    def work(self) -> None:
        from app.core.drawing import thumbnail_of

        for stamp, vertices, faces in self._jobs:
            if self.cancel.is_cancelled:
                return
            try:
                drawn = thumbnail_of(vertices, faces, self._pixels, theme=self._theme)  # type: ignore[arg-type]
            except Exception as problem:  # pragma: no cover - hängt am Netz
                # Ein Vorschaubild ist Beiwerk. Scheitert eines, bleibt seine
                # Zeile, wie sie war, und die übrigen kommen trotzdem.
                _log.info("no preview for %s: %s", stamp, problem)
                continue
            self.drawn.emit(stamp, drawn)

    def release_finished_references(self) -> None:
        self._jobs = []
        super().release_finished_references()


class _ObjectTreeView(QTreeWidget):
    """Benutzerauswahl vor Qts eigener Auswahländerung prüfen.

    **Und sagen, warum sie nicht geht.** Solange eine begonnene Maßgruppe
    ihre Auswahl hält, verschluckte der Baum Klick, Doppelklick und Taste
    stumm; den Satz „Die aktuelle Änderung zuerst übernehmen oder abbrechen"
    sagte nur der Menüweg (Review Fenster #6, 21.09.2026). ``selection_refused``
    ist der Satz — einmal je Geste, nicht je Auswahländerung, deshalb an den
    Ereignissen und nicht in ``selectionCommand``.
    """

    selection_allowed: Callable[[], bool] | None = None
    selection_refused: Callable[[], None] | None = None

    def _refused(self) -> bool:
        """Ob die Auswahl gerade gehalten wird — und der Satz dazu, wenn ja."""
        if self.selection_allowed is None or self.selection_allowed():
            return False
        if self.selection_refused is not None:
            self.selection_refused()
        return True

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Schnittstelle
        if self._refused():
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Schnittstelle
        if self._refused():
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — Qt-Schnittstelle
        if event.key() != Qt.Key.Key_Escape and self._refused():
            event.accept()
            return
        super().keyPressEvent(event)

    def selectionCommand(  # noqa: N802 — Qt-Schnittstelle
        self, index: QModelIndex | QPersistentModelIndex, event: QEvent | None = None
    ) -> QItemSelectionModel.SelectionFlag:
        if (
            event is not None
            and self.selection_allowed is not None
            and not self.selection_allowed()
        ):
            return QItemSelectionModel.SelectionFlag.NoUpdate
        return super().selectionCommand(index, event)


class ObjectTree(QWidget):
    """Objekte der Szene mit ihren Merkmalen, Herkunft und Größe (§18.8,
    §18.5).
    """

    selectionChanged = Signal(object)
    featureSelected = Signal(object)
    """Ein im Baum gewähltes Merkmal — trägt seine ID, oder None."""
    featuresSelected = Signal(list)
    """Alle gewählten Merkmale als Paare aus Körper und Kennung — für die
    Frage, wie weit zwei voneinander stehen."""
    operationRequested = Signal(object)
    """Eine aus dem Kontextmenü gewählte Operation — trägt ihre ``OperationSpec``."""
    visibilityRequested = Signal(object, bool)
    """Ein- oder ausblenden (§18.8) — trägt die Kennungen und den Wunsch."""
    isolateRequested = Signal(object)
    """Nur diese zeigen — trägt die Kennungen. Ein zweiter Aufruf hebt es auf."""
    stepRequested = Signal(int)
    """Den Schritt öffnen, der das gewählte Merkmal erzeugt hat (§21.2) —
    trägt seine Kennung."""
    sketchOnFaceRequested = Signal(str)
    """Auf dieser planaren Fläche zeichnen (§30.1) — trägt die Merkmalskennung.

    Der Empfänger baut daraus die Ebene ``feature:<id>``; der Baum kennt den
    Skizzenmodus nicht und soll ihn nicht kennen."""
    filamentRequested = Signal(object, object)
    """Das Filament dieser Zeile wählen — trägt Körperkennung und Merkmal.

    Der Baum weiß, **worauf** gezeigt wurde, nicht **wie** man es zuweist: Für
    einen Körper ist das ``assign_slot``, für eine Fläche ``paint_slot``. Beide
    gehen durch ``MainWindow.launch_operation``, damit Verlauf und Undo
    erhalten bleiben (Regel 2) — der Baum ruft keine Operation selbst auf.

    Das Merkmal ist ``None``, wenn die Zeile einen ganzen Körper meint."""

    catalogRequested = Signal()
    """Den Bausteinkatalog öffnen — der kurze Weg vom gewählten Teil (§2.6).

    Ohne Kennung: Was gewählt ist, weiß das Fenster ohnehin, und der Katalog
    fragt es dort ab. Der Baum sagt nur, dass jemand ihn sehen will."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tree = _ObjectTreeView(self)
        self.tree.setAccessibleName(tr("Objekte"))
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels([tr("Objekt"), tr("Maße"), tr("Filament")])
        # Die Maßspalte nimmt, was sie braucht; der Rest gehört den Namen.
        # Vorher standen beide auf derselben festen Breite, und auf dreifache
        # Fensterbreite gezogen blieb die Maßspalte schmal, während links
        # jeder Merkmalsname abgeschnitten war.
        header = self.tree.header()
        # **Der Satz darüber galt nicht.** ``stretchLastSection`` steht auf Qts
        # Vorgabe ``True`` und überstimmt das ``ResizeToContents`` der letzten
        # Spalte: gemessen standen beide auf genau der Hälfte, 128 zu 128 bei
        # 258 Pixeln Baumbreite. Nach Abzug von Einzug und Vorschaubild blieb
        # für den Namen so wenig, dass „Gehäuseboden" und „Gehäuseboden (Kopie)
        # Prüfstück" — die zwei Körper des ersten Beispielprojekts — als
        # dieselbe abgeschnittene Zeichenkette dastanden.
        #
        # Den Deckel nur abzuschalten kippt es aber bloß um: dann nimmt die
        # Maßspalte, was ihr Inhalt braucht, und bei „60 x 40 x 12 mm" waren das
        # 186 von 258 Pixeln — 70 für den Namen, schlechter als vorher. Beide
        # Spalten wollen Platz, und die Frage ist nicht, wer ihn bekommt,
        # sondern in welchem Verhältnis. Die Maßspalte bekommt, was sie braucht,
        # und höchstens :data:`MEASURE_SHARE`; der Rest gehört dem Namen. Gesetzt
        # wird in ``_size_columns``, denn beides ändert sich: der Inhalt und die
        # Breite.
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        # Die Filamentspalte trägt ein Farbfeld und sonst nichts. Sie ist
        # deshalb fest und schmal — nähme sie sich Platz nach Inhalt, ginge er
        # dem Namen ab, und der ist die Spalte, die man liest.
        header.setSectionResizeMode(FILAMENT_COLUMN, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(FILAMENT_COLUMN, FILAMENT_WIDTH)
        # Ein Klick auf das Feld ist die Zuweisung — nicht erst ein Doppelklick
        # und kein Umweg über das Kontextmenü.
        self.tree.clicked.connect(self._on_cell_clicked)
        # §25: Vereinigen, Abziehen und Schnittmenge nehmen zwei Körper. Mit
        # Einfachauswahl war keine davon über das Menü ausführbar — die
        # Operation bekam einen Eingang, wo sie zwei erwartet, und lehnte ab.
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setRootIsDecorated(True)
        # Ohne das zeichnet Qt jedes Symbol auf Textgröße herunter, und das
        # gerenderte Vorschaubild wäre umsonst gerechnet.
        self.tree.setIconSize(QSize(_preview_pixels(self.tree), _preview_pixels(self.tree)))
        self._order: list[ObjectId] = []
        """Die Reihenfolge, in der angeklickt wurde. „A minus B" ist nicht „B
        minus A", und die Reihenfolge im Baum weiß davon nichts."""
        self._hidden: frozenset[ObjectId] = frozenset()
        self._unit: LengthUnit = "mm"
        self._room: int | None = None
        """Die Höhe, die diese Karte haben darf — von der Überlagerung
        zugeteilt (§2.5). ``None`` heißt: noch niemand hat es gesagt."""
        self._result: EvaluationResult | None = None
        """Das Zuletzt-Gezeigte, damit sich der Baum ohne neue Auswertung
        neu zeichnen kann — beim Ausblenden ändert sich nur die Anzeige."""
        self._document: Document | None = None
        self._theme: DrawingTheme = "dark"
        """Für welches Thema die Vorschaubilder gezeichnet werden."""
        self._previews: dict[str, QIcon] = {}
        """Gerenderte Vorschaubilder, nach dem Hash des Objekts.

        Nach dem Hash und nicht nach der Kennung: „obj_1" bleibt dasselbe
        Objekt, wenn sich seine Wandstärke ändert — sein Bild nicht. Der Hash
        steht ohnehin im Ergebnis, weil der Stapel ihn zum Zwischenspeichern
        braucht."""
        self._pending: list[tuple[QTreeWidgetItem, str, Any]] = []
        """Was noch gezeichnet werden muss. Erst nach dem Aufbau, sonst steht
        der Baum still, während das erste Bild entsteht — und bei einem
        gescannten Teil sind das achtzig Millisekunden je Zeile."""
        self._leash = WorkerLeash(self)
        self._drawing: _ThumbnailWorker | None = None
        """Der Arbeiter, der die vorgemerkten Bilder zeichnet — oder keiner."""
        self._rows_for: dict[str, list[QTreeWidgetItem]] = {}
        """Welche Zeilen auf welches Bild warten. Zwei Körper mit demselben
        Hash sind dasselbe Bild und dieselbe Zeichnung."""
        self._faces: set[tuple[str, str]] = set()
        """Welche Merkmale Flächen sind — die einzigen, die ein Filament tragen.

        Beim Aufbau nebenbei gefüllt, wo ``kind == "face"`` ohnehin über die
        Filamentspalte entscheidet. :meth:`selected_faces` beantwortet damit
        die Frage, die der Schnellwähler stellt, ohne die Zeile nach ihrem
        Aussehen zu befragen: Ein Icon ist Darstellung und keine Auskunft."""
        self.tree.itemSelectionChanged.connect(self._on_selection)
        # **Doppelklick öffnet, was die Zeile ändert** (Robert, 03.09.2026:
        # „bei Doppelklick würde ich auch gerne die Größen usw. ändern können
        # über einen Dialog"). Der kurze Weg zum selben Ziel, das das
        # Kontextmenü an erster Stelle führt — und in derselben Reihenfolge,
        # damit beide Wege nicht auseinanderlaufen.
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        # Wer einen Körper aufklappt, will seine Merkmale sehen und nicht in
        # einem Feld von zwei Zeilen danach scrollen.
        self.tree.itemExpanded.connect(self._fit)
        self.tree.itemCollapsed.connect(self._fit)
        self.tree.setAcceptDrops(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)

        # Der leere Zustand liegt über dem Baum, nicht darin: eine Zeile im
        # Baum wäre auswählbar, hätte eine Spalte „Maße" und sähe aus wie ein
        # Objekt namens „Noch keine Objekte".
        self._empty = QLabel(_empty_objects_text(), self)
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._empty.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        fit_wrapped(self._empty)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._empty)
        layout.addWidget(self.tree)

    def say_why_empty(self, note: str) -> None:
        """Was der leere Baum sagt: die Einladung, oder warum noch kein Körper da ist.

        Ein Projekt, dessen Kette am ersten Schritt hält, ist nicht leer; dort
        „Über „Erzeugen“ entsteht ein Körper“ zu lesen, schickte den Kunden an
        den Anfang statt an den Schritt (RM-458). Leer heißt: die Vorgabe.
        """
        text = note or _empty_objects_text()
        if self._empty.text() != text:
            self._empty.setText(text)
            fit_wrapped(self._empty)

    def set_hidden(self, hidden: frozenset[ObjectId]) -> None:
        """Welche Körper gerade nicht gezeichnet werden — nur zum Anzeigen."""
        if hidden == self._hidden:
            return
        self._hidden = hidden
        self.show_scene(self._result, self._document)

    def set_unit(self, unit: LengthUnit) -> None:
        """§19.3: Millimeter oder Zoll in der Maße-Spalte."""
        if unit == self._unit:
            return
        self._unit = unit
        self.show_scene(self._result, self._document)

    def set_theme(self, theme: str) -> None:
        """Ein anderes Thema heißt andere Vorschaubilder.

        Der Vorrat wird geleert und nicht umgefärbt: Die Bilder sind SVG mit
        eingebackenen Farben, und ein helles Teil auf hellem Grund ist kein
        Bild mehr.
        """
        if theme == self._theme:
            return
        self._theme = "light" if theme == "light" else "dark"
        self._previews.clear()
        self.show_scene(self._result, self._document)

    def _want_preview(self, item: QTreeWidgetItem, object_id: ObjectId, entry: Any) -> None:
        """Merkt vor, dass diese Zeile ein Bild bekommen soll.

        Steht es schon im Vorrat, kommt es sofort — dann hat sich am Körper
        nichts geändert, und Rendern hieße dasselbe Bild zweimal zeichnen.
        """
        stamp = self._stamp(object_id, entry)
        ready = self._previews.get(stamp)
        if ready is not None:
            item.setIcon(0, ready)
            return
        self._pending.append((item, stamp, entry))

    def _stamp(self, object_id: ObjectId, entry: Any) -> str:
        """Woran ein Bild hängt: am Hash des Körpers, nicht an seiner Kennung.

        Fehlt der Hash — bei einer Szene, die nie durch den Stapel lief —,
        tut es die Dreieckszahl mit der Kennung. Sie ist gröber und würde eine
        Formänderung bei gleicher Zahl übersehen; das ist hier verkraftbar,
        weil es um ein Bild von zwanzig Pixeln geht.
        """
        hashes = self._result.object_hashes if self._result else {}
        known = hashes.get(object_id)
        return str(known) if known else f"{object_id}:{entry.mesh.triangle_count}"

    def _render_pending(self) -> None:
        """Gibt die vorgemerkten Bilder an den Arbeiter — und zwar alle auf einmal.

        **Gezeichnet wird nebenan** (16.09.2026). Vorher entstand hier je
        Ereignisrunde eines, mit der Begründung, fünf am Stück wären eine halbe
        Sekunde Stillstand. Die Rechnung stimmte und die Abhilfe nicht: Ein
        ``singleShot(0)`` kehrt in derselben Runde zurück, und am
        ``1-24+scale+polebarn.3mf`` mit 89 Körpern lagen trotzdem **5,25 s** im
        Hauptthread, in Schüben von 400 bis 775 ms — davon 2,96 s im
        Vereinfachen der Netze für ein Bild von zwanzig Pixeln.

        Der Arbeiter gibt jedes Bild einzeln zurück (:attr:`_ThumbnailWorker.drawn`),
        und hier bleibt nur das Malen des SVG — zehn Millisekunden statt
        sechzig, und die Zeilen kommen weiter nacheinander nach.
        """
        if not self._pending:
            return
        jobs: list[tuple[str, Any, Any]] = []
        seen: set[str] = set()
        self._rows_for = {}
        for item, stamp, entry in self._pending:
            self._rows_for.setdefault(stamp, []).append(item)
            if stamp in seen:
                continue
            seen.add(stamp)
            raw = entry.mesh.raw
            # **Die Arrays werden hier gelesen, nicht dort.** Ein Arbeiter am
            # selben ``Trimesh`` füllte dessen träge Caches neben dem
            # Hauptthread; ein Array ist Speicher und wird nur gelesen.
            jobs.append((stamp, raw.vertices, raw.faces))
        self._pending.clear()
        if not jobs:
            return
        # Ein neuer Auftrag ersetzt den alten: Seine Bilder gehören zu Zeilen,
        # die es nicht mehr gibt.
        self._stop_drawing()
        worker = _ThumbnailWorker(jobs, _preview_pixels(self.tree), self._theme)
        worker.drawn.connect(self._preview_drawn)
        # Ein Vorschaubild ist Beiwerk, ein unerwarteter Fehler darin nicht:
        # Ohne Zuhörer bliebe er auf der Fehlerausgabe stehen, wo ihn kein
        # Kunde sieht (``wartezeit.md``, „crashed wird verbunden").
        worker.crashed.connect(self._drawing_crashed)
        worker.finished.connect(weak_slot(self, ObjectTree._drawing_done, worker))
        self._drawing = worker
        self._leash.start(worker)

    def _preview_drawn(self, stamp: str, image: str) -> None:
        """Ein fertiges SVG wird zum Symbol — das Einzige, wofür es Qt braucht."""
        found = QIcon(svg_pixmap(image, _preview_pixels(self.tree)))
        self._previews[stamp] = found
        for item in self._rows_for.get(stamp, ()):
            # Die Zeile kann inzwischen weg sein — eine neue Auswertung räumt
            # den Baum, während nebenan noch gezeichnet wird. ``show_scene``
            # leert ``_rows_for`` dazu; hier bleibt die Frage an shiboken, ob
            # das Objekt noch lebt, denn ``indexFromItem`` an einem gelöschten
            # Item wirft, statt einen ungültigen Index zu liefern.
            if isValid(item) and self.tree.indexFromItem(item).isValid():
                item.setIcon(0, found)

    def _drawing_done(self, worker: Any) -> None:
        if self._drawing is worker:
            self._drawing = None

    def _drawing_crashed(self, problem: str) -> None:
        """Der Zeichner ist unerwartet zurückgekommen — die Zeilen bleiben ohne Bild.

        Kein Dialog: Ein Vorschaubild ist Beiwerk, und ein Fenster, das wegen
        eines Symbols eine Frage stellt, wäre der teuerste mögliche Umgang mit
        einer Nebensache. Der Satz steht im Protokoll (§33.2), wo er beim
        nächsten Fehlerbericht mitreist.
        """
        _log.warning("previews stopped: %s", problem)
        self._drawing = None

    def _stop_drawing(self) -> None:
        """Den laufenden Zeichner abbestellen — seine Bilder gelten nicht mehr."""
        worker = self._drawing
        self._drawing = None
        if worker is not None:
            worker.cancel.cancel()

    def wait_for_previews(self, timeout_ms: int = 60000) -> bool:
        """Warten, bis die Bilder da sind — der Weg für Tests und Bildläufe.

        Dieselbe Bauart wie ``FirstRunDialog.wait_for_survey``: Der fachliche
        Name gibt einen Wahrheitswert zurück, :meth:`release` räumt auf. Ohne
        ihn prüfte ein Test den leeren Zustand — die Bilder entstehen seit dem
        16.09.2026 nebenan, und wer sofort nachsieht, sieht nichts.
        """
        from time import monotonic

        from PySide6.QtWidgets import QApplication

        until = monotonic() + timeout_ms / 1000.0
        while self._drawing is not None and monotonic() < until:
            QApplication.processEvents()
        QApplication.processEvents()
        return self._drawing is None

    def release(self) -> None:
        """Auf den Zeichner warten, bevor der Baum weggeht (``wartezeit.md``).

        **Und nichts mehr anfangen.** ``show_scene`` stellt das Zeichnen mit
        ``singleShot(0)`` zurück; wer freigibt, bevor der Zeitgeber feuert,
        ließ ihn danach einen Zeichner starten, auf den niemand mehr wartete —
        ein Thread, der den Prozess überlebt (``QThread: Destroyed while
        thread is still running``, gemessen am 21.09.2026 an fünf Fällen in
        ``test_operation_ui``, deren Test keine Ereignisrunde durchlief).
        """
        self._pending.clear()
        self._stop_drawing()
        self._leash.wait_all()

    def show_scene(self, result: EvaluationResult | None, document: Document | None = None) -> None:
        selected = self.selected_objects()
        selected_feature = self.selected_feature()
        selected_features = self.selected_features()
        self._result = result
        self._document = document
        # **Das Leeren ist keine Auswahl.** ``clear()`` meldete „nichts
        # gewählt", bevor ``_restore`` die Auswahl zurückholte — und das
        # Fenster brach dazwischen die laufende Analysekarte ab und rechnete
        # sie nach jedem Baumaufbau neu (Einheit, Thema, Ausblenden; gemessen
        # am 21.09.2026 am Einheitenwechsel). Gemeldet wird einmal, aus
        # ``_restore`` — oder hier, wenn es nichts wiederherzustellen gibt.
        with QSignalBlocker(self.tree):
            self.tree.clear()
        # Was noch nicht gezeichnet war, gehört zu Zeilen, die es nicht mehr
        # gibt. Der Vorrat bleibt: dieselben Körper kommen meist wieder.
        self._pending.clear()
        # **Und die Zeilen, auf die ein laufender Zeichner noch zeigt, sind
        # mit ``clear()`` tot** — C++-seitig gelöscht, und der erste Zugriff
        # darauf ist ein ``RuntimeError`` aus shiboken, kein ungültiger Index.
        # ``_preview_drawn`` fragte ``indexFromItem(item)`` und griff damit
        # auf das tote Objekt zu, bevor es fragen konnte (16.09.2026: Entf an
        # einer gewählten Fläche, der Zeichner der vorigen Szene lieferte in
        # den geräumten Baum). Ohne Zeilen gibt es nichts zu beschriften.
        self._rows_for = {}
        self._faces.clear()
        if result is None:
            self._on_selection()
            return
        for object_id, entry in result.scene.objects.items():
            size = entry.mesh.bounds.size
            # §19.3: die Einheit stand hier fest, obwohl sie eine Einstellung
            # ist. Umgerechnet wird nur für die Anzeige — im Netz bleibt jede
            # Zahl ein Millimeter.
            # Kompakt, weil die Spalte eng ist: mit fester Stellenzahl brauchte
            # sie dreihundert Pixel und bekam zweihundertsechzig, seit die Zonen
            # über der Ansicht liegen. Die Nullen standen dort, weil die
            # Formatierung sie vorsieht — nicht weil jemand sie gemessen hätte.
            # Krumme Maße behalten ihre Stellen.
            measures = " × ".join(compact_length(value, self._unit) for value in size)
            item = QTreeWidgetItem([str(entry.name), f"{measures} {self._unit}"])
            item.setData(0, Qt.ItemDataRole.UserRole, object_id)
            state = tr("geschlossen") if entry.mesh.is_watertight else tr("offen")
            # §30: Nicht den Namen des Rechenkerns zeigen, sondern die Folge,
            # die für die nächste Handlung zählt. „Exakt" und „B-Rep" setzen
            # CAD-Wissen voraus und lassen das Dreiecksmodell wie die
            # schlechtere Wahl aussehen.
            kind = (
                tr("Flächen und Kanten bearbeitbar; Rundungen als echte Kurven")
                if entry.kind == "brep"
                else tr("Flächen und Kanten bearbeitbar; Rundungen aus geraden Teilstücken")
            )
            triangles = tr("Dreiecke", context="Anzahl")
            tip = f"{object_id} · {kind} · {entry.mesh.triangle_count} {triangles} · {state}"
            if entry.material:
                tip += f" · {entry.material}"
            # §18.8: woher der Körper kommt. Ohne das ist ein Baum mit sieben
            # Teilen aus einer Teilung eine Liste ohne Vorgeschichte — und die
            # Frage „welcher Schritt hat das gemacht" nur durch Ausprobieren zu
            # beantworten.
            origin = _origin_text(entry.created_by, document)
            if origin:
                tip += f" · {origin}"
            item.setToolTip(0, tip)
            from app.core.export.threemf import slots_for_object
            from app.core.geom.attributes import used_slots

            mesh = as_mesh_data(entry.mesh)
            definitions = slots_for_object(entry)
            occupied = set(used_slots(mesh))
            self._show_filament(item, tuple(slot for slot in definitions if slot.index in occupied))
            if object_id in self._hidden:
                # Zeichen und Wort: eine ausgegraute Zeile allein wäre Farbe als
                # einzige Kodierung (Regel 18).
                item.setIcon(0, icon("hidden", self.tree))
                item.setText(0, f"{item.text(0)}  ·  {tr('ausgeblendet')}")
            else:
                # Ein Vorschaubild statt eines Aufzählungszeichens: „Dose" und
                # „Dose Deckel" sind zwei Zeilen Text, die man liest — zwei
                # Bilder erkennt man. Das ausgeblendete Objekt behält sein
                # eigenes Zeichen; es hat gerade nichts zu zeigen.
                self._want_preview(item, object_id, entry)
            if entry.material:
                # §12: ein Körper, der nicht im Material des Projekts ist, muss das
                # dort sagen, wo die Teile aufgezählt werden — sonst zeigt sich
                # der Unterschied nur an einer Passung, die auf einmal ein
                # anderes Spiel will.
                item.setText(1, f"{item.text(1)}  ·  {entry.material}")
            # **Was aus einem Baustein kam, steht unter ihm.** Vierzehn
            # Merkmale flach untereinander sagen nicht, welche zusammengehören:
            # Der Kunde sieht sechs Verrundungen und findet den Einhänger
            # nicht, aus dem sie stammen (Befund Robert, 25.08.2026).
            groups: dict[int, QTreeWidgetItem] = {}
            # **Und gleichartige Merkmale stehen unter einem Dach.** Der Absatz
            # darüber löst den Fall, dass vierzehn Merkmale aus einem Baustein
            # kommen; er löst nicht den häufigeren: Eine STEP-Datei aus Fusion
            # oder Onshape bringt Dutzende erkannte Verrundungen mit, die aus
            # gar keinem Schritt stammen. Gemessen an ``build_tray_v3.step``
            # (Roberts Downloads, 03.09.2026): 234 Merkmale, davon rund fünfzig
            # sichtbare Zeilen „Hohlkehle R13,98 mm" untereinander, die die
            # ganze linke Spalte füllten und Parameter und Verlauf hinausdrückten.
            # Der Prüfbericht daneben bündelte dieselbe Menge längst zu einer
            # Zeile — dieselbe Schwelle (:data:`BUNDLE_FROM`) und derselbe
            # Grund: Jede Einzelzeile stimmt, die Menge begräbt.
            #
            # **Gezählt wird nach Name *und* Maß, nicht nach dem Namen
            # allein.** Der Fall aus der STEP-Datei sind fünfzig Hohlkehlen
            # desselben Radius — die gehören unter ein Dach. Ein
            # Schlüsselloch bringt dagegen zehn mit **verschiedenen** Radien
            # mit, und die kamen unter dasselbe Dach „Hohlkehle (10)": eine
            # Zeile, die Gleichartigkeit behauptet, wo keine ist, und zehn
            # unterschiedliche Maße hinter einem Klick versteckt (Befund
            # Robert, 09.09.2026). Der Schlüssel entscheidet also, ob ein Dach
            # zusammenfasst oder verdeckt.
            by_kind: dict[tuple[str, str], QTreeWidgetItem] = {}
            # **Und eine Senkung steht unter ihrer Bohrung.** Sie sind ein
            # Merkmal in zwei Flächen: Wer die Bohrung ändert, meint die
            # Senkung mit, und wer sie als Nachbarzeile sieht, sucht sie
            # (Befund Robert, 04.09.2026, an ``broomholdervcd_d35mm.stl`` —
            # zwei Bohrungen Ø 5,44 mit je einer Senkung Ø 8,16, die im Baum
            # vier Zeilen ohne erkennbaren Zusammenhang waren).
            #
            # Die Zuordnung kommt aus dem Kern (`cavity_chains`) und
            # nicht aus einer zweiten Rechnung hier: Dieselbe Nachbarschaft
            # entscheidet, was der Prüfbericht meldet, wenn die Bohrung wächst.
            from app.core.perceive.relations import cavity_chains

            under: dict[str, str] = {}
            chains = (
                cavity_chains(entry.features, as_mesh_data(entry.mesh))
                if len(entry.features) > 1
                else ()
            )
            for chain in chains:
                for parent, nested in pairwise(chain):
                    under[nested.id] = parent.id
            cavity_names = {
                chain[0].id: cavity_name(chain[0].id, chain[0], chain) for chain in chains
            }
            # **Und was gemeinsam eine Aufgabe trägt, hängt an seinem Anker**
            # (RM-184, Dateiaudit §7): Boden und Wände einer Kammer, Gewinde
            # mit Schulter, die Nocken eines Bajonetts, die Augen eines
            # Scharniers, die Buchstaben einer Schrift. Die Zeile des Ankers
            # heißt wie die Gruppe und trägt ihr Maß; ein Klick auf sie wählt,
            # was darunter hängt — derselbe Weg wie die Senkung unter ihrer
            # Bohrung. Die Zuordnung kommt aus dem Kern, gerechnet im
            # Auswertungsarbeiter (``session._warm_metrics``).
            from app.core.perceive.groups import evidence_texts, functional_groups
            from app.core.perceive.groups import numbered_titles as group_titles

            functional = (
                functional_groups(entry.features, as_mesh_data(entry.mesh))
                if len(entry.features) > 1
                else ()
            )
            group_names = group_titles(functional)
            sentences = evidence_texts() if functional else {}
            grouped: dict[str, tuple[str, str, str]] = {}
            for unit in functional:
                anchor_id = unit.anchor
                # Was aus einem Baustein kam, steht schon unter seinem Schritt;
                # ein zweites Dach risse es dort heraus.
                if anchor_id not in entry.features or any(
                    member not in entry.features
                    or _part_group(entry.features[member].created_by, document) is not None
                    for member in unit.members
                ):
                    continue
                grouped[anchor_id] = (
                    group_names[unit.key],
                    group_summary(unit),
                    sentences[unit.evidence],
                )
                for member in unit.members:
                    if member == anchor_id or member in under:
                        continue
                    # Hängt der Anker selbst schon (über eine Senkenkette) an
                    # diesem Mitglied, bliebe es dort — ein Kreis nähme beide
                    # Zeilen aus dem Baum.
                    above = under.get(anchor_id)
                    while above is not None and above != member:
                        above = under.get(above)
                    if above is None:
                        under[member] = anchor_id
            alike: dict[tuple[str, str], int] = {}
            for other_id, other in entry.features.items():
                if (
                    other_id not in under
                    and other_id not in grouped
                    and _part_group(other.created_by, document) is None
                ):
                    group_key = (
                        cavity_names.get(other_id, feature_name(other_id, other)),
                        feature_measure(other, marked=True),
                    )
                    alike[group_key] = alike.get(group_key, 0) + 1
            made: dict[str, QTreeWidgetItem] = {}
            waiting: list[tuple[str, QTreeWidgetItem]] = []
            for feature_id, feature in entry.features.items():
                # Name links, Maß rechts. Vorher stand die ganze Beschriftung
                # links und rechts der Typ („hole", „face") — links war damit
                # abgeschnitten, was rechts gefehlt hat.
                #
                # **Die Zahl ganz, die Herkunft als Zeichen** (RM-490): Mit dem
                # Wort dahinter endete die Spalte in jeder Breite in
                # „Ø5,20 mm · ein…“. Das Wort hört der Bildschirmleser, und der
                # Tooltip nennt es samt Satz (Regel 18).
                unit_name = grouped.get(feature_id)
                child = QTreeWidgetItem(
                    [
                        unit_name[0]
                        if unit_name is not None
                        else cavity_names.get(feature_id, feature_name(feature_id, feature)),
                        unit_name[1]
                        if unit_name is not None and unit_name[1]
                        else feature_measure(feature, marked=True),
                    ]
                )
                child.setData(
                    1,
                    Qt.ItemDataRole.AccessibleTextRole,
                    unit_name[1]
                    if unit_name is not None and unit_name[1]
                    else feature_measure(feature),
                )
                child.setData(0, Qt.ItemDataRole.UserRole, object_id)
                child.setData(1, Qt.ItemDataRole.UserRole, feature_id)
                tip = _feature_tip(feature_id, feature, document)
                if feature_id in cavity_names:
                    tip = f"{cavity_names[feature_id]}\n{tip}"
                if unit_name is not None:
                    tip = f"{unit_name[0]} — {unit_name[2]}\n{tip}"
                # An beiden Spalten, wie der Regelsatz es für Zeilen verlangt:
                # Wer eine Zeile nicht versteht, zeigt auf das unverständliche
                # Wort und nicht auf die Zahl daneben.
                child.setToolTip(0, tip)
                child.setToolTip(1, tip)
                child.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, tip)
                # Nur Flächen tragen ein eigenes Filament — `paint_slot` gilt
                # für `face` und `curved_face` und für nichts sonst. Eine
                # Bohrung bekommt deshalb kein Feld, das nichts täte.
                if getattr(feature, "kind", "") in ("face", "curved_face"):
                    self._faces.add((object_id, feature_id))
                    # Ohne Slots trägt jedes Dreieck Slot 0 — ohne einen Gang
                    # über sie: An der größten Fläche des verfeinerten
                    # Spielwürfels (3 979 168 Dreiecke) kostete er den
                    # Hauptfaden 0,1 bis 0,2 s je Szenenaufbau (RM-212).
                    slots = mesh.slots
                    face_slots = (
                        {slots[face] for face in feature.face_indices}
                        if slots
                        else ({0} if feature.face_indices else set())
                    )
                    self._show_filament(
                        child,
                        tuple(slot for slot in definitions if slot.index in face_slots),
                        feature_id,
                    )

                made[feature_id] = child
                if feature_id in under:
                    # Erst wenn alle Zeilen stehen: Die Bohrung kann in der
                    # Reihenfolge hinter ihrer Senkung kommen.
                    waiting.append((under[feature_id], child))
                    continue

                part = _part_group(feature.created_by, document)
                if part is None:
                    label = (child.text(0), child.text(1))
                    if feature_id in grouped or alike.get(label, 0) < BUNDLE_FROM:
                        item.addChild(child)
                        continue
                    roof = by_kind.get(label)
                    if roof is None:
                        # Die Zahl steht im Text der Zeile selbst, wie bei der
                        # Sammelzeile des Prüfberichts. **Und das Maß steht
                        # jetzt daneben**: Seit nach Name und Maß gebündelt
                        # wird, tragen alle Kinder dasselbe, und es
                        # anzuschreiben ist keine Behauptung über die
                        # übrigen mehr, sondern ihre gemeinsame Auskunft.
                        roof = QTreeWidgetItem([f"{label[0]} ({alike[label]})", label[1]])
                        roof.setData(0, Qt.ItemDataRole.UserRole, object_id)
                        roof.setData(1, Qt.ItemDataRole.UserRole, None)
                        note = tr(
                            "{count} gleichartige Merkmale — anklicken zum Auf- und Zuklappen."
                        ).format(count=alike[label])
                        roof.setToolTip(0, note)
                        roof.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, note)
                        # Das gemeinsame Maß sagt seine Herkunft wie jedes Kind.
                        roof.setData(
                            1,
                            Qt.ItemDataRole.AccessibleTextRole,
                            child.data(1, Qt.ItemDataRole.AccessibleTextRole),
                        )
                        roof.setToolTip(1, feature_measure_tip(feature))
                        by_kind[label] = roof
                        item.addChild(roof)
                    # Zugeklappt, sonst wäre nichts gewonnen. ``_restore``
                    # klappt den Ast auf, wenn das gewählte Merkmal darin liegt.
                    roof.addChild(child)
                    continue
                title, step = part
                group = groups.get(step)
                if group is None:
                    group = QTreeWidgetItem([title, ""])
                    # Der Knoten trägt seinen Körper wie jede Zeile darunter —
                    # wer ihn anklickt, hat das Teil gewählt und nicht nichts.
                    # Das Merkmal bleibt leer: Er ist keines, sondern ihr Dach.
                    group.setData(0, Qt.ItemDataRole.UserRole, object_id)
                    group.setData(1, Qt.ItemDataRole.UserRole, None)
                    # Und er weiß, aus welchem Schritt er kommt — daran hängt
                    # „Diesen Schritt ändern" (§21.2).
                    group.setData(0, _STEP_ROLE, step)
                    group.setToolTip(0, _origin_text(step, document))
                    groups[step] = group
                    item.addChild(group)
                group.addChild(child)
            for bore, child in waiting:
                # Steht die Bohrung selbst unter einem Dach, hängt die Senkung
                # trotzdem an ihr — der Ast klappt beim Auswählen ohnehin auf.
                # Fehlt sie ganz, bleibt die Senkung dort, wo sie war: eine
                # Zeile zu verlieren wäre schlimmer als eine ohne Zusammenhang.
                (made.get(bore) or item).addChild(child)
            for group in list(groups.values()):
                # **Ein Dach über einer einzigen Zeile ist keins.** „Schraubenloch
                # mit Senkung" trägt genau ein direktes Kind — die Bohrung, an der
                # die Senkung schon hängt —, und die Dachzeile wiederholte damit
                # nur, was darunter steht. Angeklickt meinte sie den ganzen
                # Körper, und im Auswahlpanel standen alle Körperoperationen statt
                # der Bohrung (Befund Robert, 09.09.2026: „nur das Bohrung und
                # darunter Senkung machen").
                #
                # Verloren geht dabei nichts: Der Schritt steht in
                # ``feature.created_by``, und beide Wege zu ihm — Doppelklick und
                # „Diesen Schritt ändern" — lesen ihn von dort, wenn die Rolle
                # fehlt.
                #
                # **Und der Name des Dachs geht auf die Zeile über.** Sie steht
                # jetzt für den ganzen Baustein: Ein Klick darauf öffnet rechts
                # den Baustein, und der Verlauf nennt ihn beim selben Titel. Mit
                # dem Namen des Merkmals hieß eine eingesetzte Magnettasche im
                # Baum „Sackbohrung 1" und im Verlauf „Magnettasche" — für den
                # Kunden eine Sache mit zwei Namen (Kundenprüfung 0.5.1, Weg c).
                # Was die Zeile geometrisch ist, sagt weiter ihre Kurzhilfe
                # (``_feature_tip``: „Sackbohrung 1 · Ø8,25 mm"), und die Kennung
                # des Merkmals bleibt, wie sie ist.
                only = group.takeChild(0) if group.childCount() == 1 else None
                if only is not None:
                    where = item.indexOfChild(group)
                    item.removeChild(group)
                    only.setText(0, group.text(0))
                    item.insertChild(where, only)
                    only.setExpanded(True)
                    continue
                group.setExpanded(True)
            self.tree.addTopLevelItem(item)
            item.setExpanded(object_id in selected)
        self.tree.resizeColumnToContents(0)
        # **Eine gewählte Zeile bleibt eine Zeile** (Durchsicht 0.5.1). Eine
        # Bohrung mit ihrer Senkung meldet :meth:`selected_features` als zwei
        # Merkmale; nach jeder Auswertung wurden daraus zwei markierte Zeilen,
        # ``selected_feature`` hieß danach „keines“, und die Maßgruppe nach
        # *Übernehmen* hing an keinem Merkmal. Aufgelöst wird nur, was keine
        # einzelne Merkmalszeile war — ein Dach oder eine Mehrfachwahl.
        if selected_feature is None and len(selected_features) > 1:
            self.select_features(selected_features)
        else:
            self._restore(selected, selected_feature)
        self._fit()
        # Erst steht der Baum, dann kommen die Bilder nach. Andersherum wartet
        # der Nutzer auf eine Liste, die längst fertig gerechnet ist.
        if self._pending:
            QTimer.singleShot(0, self, self._render_pending)

    def wanted_height(self) -> int:
        """Die Höhe, bei der jede Zeile zu sehen wäre.

        Gemessen je Zeile (``rows_height``), nicht erste Zeile mal Zeilenzahl:
        Die Körperzeile trägt ein Vorschaubild und ist doppelt so hoch wie
        ihre Merkmale. Ein Körper mit zehn Merkmalen wollte so 583 statt rund
        300 Punkte und nahm sie der Filamentliste darunter (RM-489).
        """
        return max(view_chrome(self.tree), rows_height(self.tree))

    def least_height(self) -> int:
        """Und die, unter die diese Karte nicht geht (siehe ``fit_to_rows``)."""
        if self.tree.topLevelItemCount() == 0:
            return least_empty_height(self._empty)
        return least_height_of(self.tree)

    def set_room(self, pixels: int) -> None:
        """Wie hoch diese Karte werden darf (siehe ``fit_to_rows``)."""
        if pixels == self._room:
            return
        self._room = pixels
        self._fit()

    def _show_filament(
        self,
        item: QTreeWidgetItem,
        slots: tuple[MaterialSlot, ...],
        feature_id: str | None = None,
    ) -> None:
        """Das Farbfeld einer Zeile setzen, samt Namen für Tooltip und Leser.

        Der Aufbau reicht nur tatsächlich verwendete Slots des Körpers oder
        dieser Fläche durch. Ohne Belegung gilt die Farbe des Teils — das ist
        der Normalfall nach jedem Import und keine fehlende Angabe.
        """
        from app.ui.filament_picker import slot_colours, unpainted_colour

        if slots:
            slot = slots[0]
            colour = slot_colours(int(slot.index), slot)
            name = str(slot.name).strip() or str(slot.material_type or "")
            assigned = True
        else:
            colour = unpainted_colour()
            name = str(tr("Ohne Filament — Farbe des Teils"))
            assigned = False
        if len(slots) > 1:
            name = f"{name} · {tr('und {count} weitere').replace('{count}', str(len(slots) - 1))}"

        item.setIcon(FILAMENT_COLUMN, filament_chip(colour, assigned, self.tree))
        hint = f"{name} — {tr('zum Ändern anklicken')}"
        item.setToolTip(FILAMENT_COLUMN, hint)
        # Regel 18: Der Bildschirmleser bekommt den Namen, nicht die Farbe.
        item.setData(FILAMENT_COLUMN, Qt.ItemDataRole.AccessibleDescriptionRole, hint)
        item.setData(FILAMENT_COLUMN, Qt.ItemDataRole.UserRole, feature_id)

    def _on_cell_clicked(self, index: QModelIndex) -> None:
        """Ein Klick in die Filamentspalte fragt nach dem Filament."""
        if self.tree.selection_allowed is not None and not self.tree.selection_allowed():
            return
        if index.column() != FILAMENT_COLUMN:
            return
        item = self.tree.itemFromIndex(index)
        if item is None or item.icon(FILAMENT_COLUMN).isNull():
            return
        object_id = item.data(0, Qt.ItemDataRole.UserRole)
        if object_id is None:
            return
        feature_id = item.data(FILAMENT_COLUMN, Qt.ItemDataRole.UserRole)
        self.filamentRequested.emit(object_id, feature_id)

    def _size_columns(self) -> None:
        """Die Maßspalte so breit wie ihr Inhalt, höchstens ein Teil des Ganzen.

        Aufgerufen, wenn sich der Inhalt ändert und wenn sich die Breite ändert
        — an beidem hängt das Ergebnis. Ohne Breite (vor dem ersten Legen) gibt
        es nichts zu teilen.
        """
        width = self.tree.viewport().width()
        if width <= 0:
            return
        # **Die Filamentspalte wird abgezogen, bevor geteilt wird.** Sie ist
        # fest breit; bliebe sie in der Rechnung, nähme die Maßspalte ihren
        # Anteil vom Ganzen und der Name bekäme, was danach übrig ist — bei
        # schmaler Karte waren das 25 Punkte gegen 39 für das Maß.
        free = max(0, width - FILAMENT_WIDTH)
        needed = self.tree.sizeHintForColumn(1)
        self.tree.header().resizeSection(1, max(0, min(needed, int(free * MEASURE_SHARE))))

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Beim Breiterwerden neu teilen."""
        super().resizeEvent(event)
        self._size_columns()

    def _fit(self) -> None:
        """So hoch wie der Inhalt — aufgeklappte Merkmale zählen mit.

        Die zweite Zeile ist die entscheidende: ``fit_to_rows`` bemisst den
        Baum, nicht die Karte um ihn herum. Ohne sie meldete die Karte ihre
        nackte Mindesthöhe, und die Spalte drückte sie auf elf Pixel — ein
        leerer Rahmen über einem angeschnittenen Wort, während der Baum
        darunter seine hundert Pixel für sich behielt und nichts davon zu
        sehen war.
        """
        # Der leere Zustand tritt an die Stelle des Baums, nicht daneben: Ein
        # Satz über einem leeren Rahmen sähe aus, als fehlte darunter etwas.
        empty = self.tree.topLevelItemCount() == 0
        self._empty.setVisible(empty)
        self.tree.setVisible(not empty)
        wanted = self.wanted_height()
        ceiling = (
            self._room
            if self._room is not None
            else view_chrome(self.tree) + MAX_ROWS * row_height_of(self.tree)
        )
        self.tree.setFixedHeight(max(least_height_of(self.tree), min(wanted, ceiling)))
        self._size_columns()
        self.setMinimumHeight(self.sizeHint().height())
        self.updateGeometry()

    def _restore(self, objects: Sequence[ObjectId], feature_id: str | None) -> None:
        """Behält die Auswahl über eine Neuauswertung hinweg — sie zu verlieren
        kostet den Nutzer die Stelle, an der er gearbeitet hat.

        Das Merkmal gilt nur, wenn genau ein Körper gewählt war; bei mehreren
        gibt es keines, auf das es sich beziehen könnte.
        """
        if not objects:
            # Ohne Auswahl bekommt die erste Zeile wenigstens die Marke des
            # aktuellen Eintrags — gewählt ist damit nichts, aber die Tastatur
            # hat einen Anfang. Ohne sie stand ``currentItem()`` auf nichts,
            # und wer per Tabulator in den Baum kam, bewegte mit den
            # Pfeiltasten gar nichts.
            first = self.tree.topLevelItem(0)
            if first is not None and self.tree.currentItem() is None:
                self.tree.setCurrentItem(first)
                first.setSelected(False)
            return
        wanted = set(objects)
        self._order = list(objects)
        # Erst die gesamte Auswahl wiederherstellen: Eine Zwischenmeldung
        # nach dem ersten Körper würde die übrigen aus _order entfernen.
        with QSignalBlocker(self.tree):
            for index in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(index)
                if item is None or item.data(0, Qt.ItemDataRole.UserRole) not in wanted:
                    continue
                if feature_id is not None and len(wanted) == 1:
                    # Merkmale können unter Baustein- und Gruppenknoten liegen.
                    found = _feature_item(item, feature_id)
                    if found is not None:
                        found.setSelected(True)
                        self.tree.setCurrentItem(
                            found, 0, QItemSelectionModel.SelectionFlag.NoUpdate
                        )
                        parent = found.parent()
                        while parent is not None:
                            parent.setExpanded(True)
                            parent = parent.parent()
                    else:
                        item.setSelected(True)
                    continue
                item.setSelected(True)
        self._on_selection()
        QTimer.singleShot(0, self, self._reveal_current)

    def _reveal_current(self) -> None:
        """Nach dem Layout die heutige Auswahl zeigen; kein alter Zeiger reist im Timer."""
        current = self.tree.currentItem()
        if current is not None and current.isSelected():
            self.tree.scrollToItem(current, QAbstractItemView.ScrollHint.EnsureVisible)

    def selected(self) -> ObjectId | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        value: ObjectId | None = items[0].data(0, Qt.ItemDataRole.UserRole)
        return value

    def selected_objects(self) -> tuple[ObjectId, ...]:
        """Die gewählten Körper in der Reihenfolge, in der sie angeklickt
        wurden.

        Ein angeklicktes Merkmal zählt für seinen Körper: wer eine Bohrung
        markiert und dann etwas mit dem Teil tut, meint das Teil.
        """
        chosen = {
            object_id
            for item in self.tree.selectedItems()
            if (object_id := item.data(0, Qt.ItemDataRole.UserRole)) is not None
        }
        ordered = [object_id for object_id in self._order if object_id in chosen]
        ordered.extend(sorted(chosen.difference(ordered)))
        return tuple(ordered)

    def selected_feature(self) -> str | None:
        items = self.tree.selectedItems()
        if len(items) != 1:
            # Bei mehreren Zeilen ist „das gewählte Merkmal" keine Frage mit
            # einer Antwort — dann gilt keines als gewählt.
            return None
        value: str | None = items[0].data(1, Qt.ItemDataRole.UserRole)
        return value

    def selected_features(self) -> tuple[tuple[str, str], ...]:
        """Alle gewählten Merkmale als Paare aus Körper und Kennung.

        :meth:`selected_feature` gibt bewusst nichts zurück, sobald mehr als
        eine **Zeile** markiert ist — „das gewählte Merkmal" hätte dann keine
        Antwort. Für die Frage „wie weit stehen diese beiden auseinander"
        braucht es aber genau **zwei**, und die stehen hier.

        **Und was eine Zeile bündelt, wählt sie mit** (Konzept „Ein Ort für
        die Auswahl", E; Robert am 07.09.2026: „nicht nur bei Schraubenloch
        mit Senkung ist es so, bei allen Dach einträgen"). Der Baum bündelt an
        drei Stellen, und keine davon wählte etwas: Das Gleichart-Dach
        („Hohlkehle (17)") und das Baustein-Schritt-Dach („Schraubenloch mit
        Senkung") tragen selbst keine Merkmalskennung, und bei einer Bohrung
        mit ihrer Senkung als Kind wählte der Klick nur die Bohrung. Jetzt
        zählt zu jeder markierten Zeile, was unter ihr hängt.

        **Körperzeilen bleiben außen vor**, und das ist die eine Ausnahme, die
        es braucht: Unter einer Körperzeile hängt *jedes* Merkmal des Körpers.
        Wer einen Halter markiert, hat nicht seine achtzig Bohrungen gewählt,
        sondern den Halter — die Auflösung gilt deshalb nur unterhalb der
        obersten Ebene.
        """
        found: list[tuple[str, str]] = []
        for item in self.tree.selectedItems():
            if item.parent() is None:
                continue
            found.extend(_feature_refs_under(item))
        # Ohne Wiederholung und in der Reihenfolge des Baums: Wer eine Bohrung
        # **und** ihr Dach markiert, meint sie einmal.
        return tuple(dict.fromkeys(found))

    def selected_faces(self) -> tuple[tuple[str, str], ...]:
        """Davon die Flächen — die einzigen, denen ein Filament gehören kann.

        ``paint_slot`` gilt für ``face`` und ``curved_face`` und für nichts
        sonst; deshalb bekommt
        eine Bohrung in diesem Baum keine Filamentspalte. Der Schnellwähler
        rechts fragte bis zum 09.09.2026 :meth:`selected_features` und bot an
        einer gewählten Bohrung eine Zuweisung an, die es dort nicht gibt
        (Robert: „im Baum bei Bohrungen fehlt das Feld, also auch rechts in der
        Auswahl bei Bohrungen entfernen"). Beide lesen jetzt dieselbe Antwort.
        """
        return tuple(ref for ref in self.selected_features() if ref in self._faces)

    def step_selection(self, forward: bool = True) -> None:
        """Zum nächsten Körper weiterschalten (§19.2).

        Reihum: hinter dem letzten kommt wieder der erste. Ohne den Umlauf
        endet das Durchblättern am Rand, und wer einen Körper sucht, muss
        wissen, in welche Richtung er liegt.
        """
        if self.tree.selection_allowed is not None and not self.tree.selection_allowed():
            return
        count = self.tree.topLevelItemCount()
        if not count:
            return
        chosen = self.selected_objects()
        current = -1
        if chosen:
            for index in range(count):
                item = self.tree.topLevelItem(index)
                if item is not None and item.data(0, Qt.ItemDataRole.UserRole) == chosen[0]:
                    current = index
                    break
        target = self.tree.topLevelItem((current + (1 if forward else -1)) % count)
        if target is not None:
            self.tree.setCurrentItem(target)
            self.tree.scrollToItem(target)

    def select_object(self, object_id: ObjectId | None, *, add: bool = False) -> None:
        """Wählt einen Körper von außen aus — der Fehlerdialog tut das, wenn er
        zeigt, worum es ging, und ein Klick in der Ansicht ebenso.

        ``None`` hebt die Auswahl auf: wer neben das Modell klickt, will sie
        loswerden.

        ``add`` nimmt ihn zur bestehenden Auswahl dazu, statt sie zu
        ersetzen — Umschalt und Strg im Bild (Konzept „Ein Ort für die
        Auswahl", G). Ein zweites Mal auf denselben Körper nimmt ihn wieder
        heraus, wie im Baum: ``ExtendedSelection`` schaltet dort um, und die
        Regel darüber sagt, dass beide Wege dasselbe tun sollen.
        """
        if add and object_id is not None:
            chosen = list(self.selected_objects())
            if object_id in chosen:
                chosen.remove(object_id)
            else:
                chosen.append(object_id)
            # Geleert ohne Zwischenmeldung — gemeldet wird der neue Stand
            # (siehe :meth:`select_feature`).
            with QSignalBlocker(self.tree):
                self.tree.clearSelection()
            if chosen:
                self._restore(tuple(chosen), None)
            else:
                self._on_selection()
            return
        if object_id is None:
            self.tree.clearSelection()
            return
        with QSignalBlocker(self.tree):
            self.tree.clearSelection()
        self._restore((object_id,), None)

    def select_objects(self, object_ids: Sequence[ObjectId]) -> None:
        """Mehrere Körper auf einmal wählen — die Sammelzeile des Prüfberichts.

        Eine Zeile „(9) Ausrichtung über die Schichtanalyse gesucht." meint
        neun Körper; ihr Klick zeigt alle neun, nie den ersten zufälligen.
        Derselbe Weg wie ``add`` in :meth:`select_object`, nur in einem Zug.
        """
        with QSignalBlocker(self.tree):
            self.tree.clearSelection()
        wanted = tuple(dict.fromkeys(object_ids))
        if wanted:
            self._restore(wanted, None)
        else:
            self._on_selection()

    def select_feature(self, object_id: ObjectId, feature_id: str) -> None:
        """Folgt einem Klick im Viewport — die zwei Ansichten zeigen eine
        Auswahl (§18.5).

        **Und die Karte wächst mit.** ``_restore`` klappt den Weg zum Merkmal
        auf, hier also bis zu zwei Knoten; ohne ``_fit`` bleibt die Karte auf
        der Höhe von vorher stehen, und die aufgeklappten Zeilen liegen unter
        ihrem Rand. In ``show_scene`` kommt ``_fit`` ohnehin danach — auf
        diesem Weg kam es nie.
        """
        # **Ohne Zwischenmeldung „nichts gewählt".** ``_restore`` meldet den
        # neuen Stand ohnehin; das Leeren davor lief ungeblockt durch alle
        # Empfänger — Merkmalfenster geleert, Handlungskarte, Menüs und
        # Maßgruppe neu —, und gleich danach alles noch einmal für das neue
        # Merkmal. Am Halter mit Wabenmuster war das ein Drittel eines
        # Bohrungsklicks (22.09.2026).
        with QSignalBlocker(self.tree):
            self.tree.clearSelection()
        self._restore((object_id,), feature_id)
        self._fit()

    def select_features(self, references: Sequence[tuple[str, str]]) -> None:
        """Vollständige Merkmalsbezüge auch über zwei Körper hinweg wiederherstellen."""
        with QSignalBlocker(self.tree):
            self.tree.clearSelection()
            for object_id, feature_id in references:
                for index in range(self.tree.topLevelItemCount()):
                    body = self.tree.topLevelItem(index)
                    if body is None or body.data(0, Qt.ItemDataRole.UserRole) != object_id:
                        continue
                    item = _feature_item(body, feature_id)
                    if item is not None:
                        item.setSelected(True)
                        self.tree.setCurrentItem(
                            item, 0, QItemSelectionModel.SelectionFlag.NoUpdate
                        )
                        parent = item.parent()
                        while parent is not None:
                            parent.setExpanded(True)
                            parent = parent.parent()
                    break
        self._on_selection()
        self._fit()
        QTimer.singleShot(0, self, self._reveal_current)

    def _on_selection(self) -> None:
        self._remember_order()
        self.selectionChanged.emit(self.selected())
        self.featureSelected.emit(self.selected_feature())
        # **Und die Mehrfachauswahl getrennt**, weil sie eine andere Frage
        # beantwortet: nicht „was ist gewählt", sondern „welche stehen
        # zueinander". Über ``featureSelected`` ginge sie nicht — das trägt
        # bewusst nichts, sobald mehr als eine Zeile markiert ist.
        self.featuresSelected.emit(list(self.selected_features()))

    def _remember_order(self) -> None:
        """Führt mit, in welcher Reihenfolge angeklickt wurde.

        Qt gibt die Auswahl in Baumreihenfolge zurück, und die sagt nichts
        darüber, was zuerst gemeint war. Abgewähltes fällt heraus, Neues kommt
        hinten dazu.
        """
        current = {
            object_id
            for item in self.tree.selectedItems()
            if (object_id := item.data(0, Qt.ItemDataRole.UserRole)) is not None
        }
        self._order = [object_id for object_id in self._order if object_id in current]
        self._order.extend(sorted(current.difference(self._order)))

    def operations_for_object(self) -> tuple[Any, ...]:
        """Operationen, die auf einem gewählten Objekt arbeiten — der kürzeste
        Weg vom Sehen zum Tun (§2.6).

        **Die Rohmenge, kein Menü mehr** (11.09.2026): Das Kontextmenü trägt
        keine Operationen; wer sie sehen will, sieht rechts in die Karte der
        Handlungen. Gefragt wird sie noch von Tests, die die Zuordnung prüfen.

        Angeboten werden alle, auch die, die auf dieser Bauart nicht können:
        Ausgegraut mit Grund steht sie da und sagt, was ihr fehlt — verschwunden
        ließe sie den Nutzer suchen, wo nichts fehlt (dieselbe Entscheidung wie
        in der Menüleiste). Welche das sind, entscheidet
        :meth:`kinds_of_selection` beim Bauen des Menüs.

        """
        # Nach Titel sortiert, wie die Menüleiste: ``REGISTRY.all()`` liefert
        # nach dem internen englischen Namen, und im Kontextmenü stand damit
        # „An Merkmal ausrichten" vor „Textur aufbringen" vor „Auf dem Bett
        # anordnen". Sortiert wird mit ``sort_key`` wie dort, sonst rutscht
        # „Überhangfächer" hinter das letzte Z — „Ü" steht im Zeichensatz
        # hinter „z".
        return tuple(
            sorted(
                shown_of_twins(spec for spec in REGISTRY.all() if spec.consumes == 1),
                key=lambda spec: sort_key(spec.title),
            )
        )

    def kinds_of_selection(self) -> list[str]:
        """Die Bauart jedes gewählten Körpers — Netz oder exakt.

        Hier und nicht im Fenster: Der Baum hält die Auswahl **und** die
        Auswertung, und beide Menüs — die Leiste oben und das Kontextmenü hier —
        brauchen dieselbe Antwort. Vorher stand die Rechnung im Fenster, und das
        Kontextmenü fragte niemanden.
        """
        if self._result is None:
            return []
        objects = self._result.scene.objects
        return [objects[entry].kind for entry in self.selected_objects() if entry in objects]

    def operations_for_feature(self, kind: str) -> tuple[Any, ...]:
        """Was eine Bohrung oder eine Fläche anbietet, direkt aus ``applies_to``
        (§10, §18.5).

        **Gebraucht vom Doppelklick im Baum** (:meth:`_on_double_click`), der die
        erste passende Handlung startet — im Kontextmenü stehen seit dem
        11.09.2026 keine Operationen mehr, die stehen rechts in der Karte.

        **Ohne die zusammengelegten Zwillinge.** An jeder Fläche stand
        *Bohrung setzen* zweimal — ``drill_hole`` und ``drill_brep_hole``
        tragen denselben Titel, und der Kunde konnte nicht wissen, welche
        Zeile er nimmt; je nach Treffer bekam er einen anderen Rechenkern.
        Die Menüleiste legt das Paar seit je zusammen (``MENU_TWINS``): Der
        sichtbare Partner trägt den Eintrag, der andere ist über einen
        Umschalter in dessen Dialog erreichbar. Hier fehlte die Rechnung —
        dieselbe Frage an zwei Stellen, und eine kannte die Antwort nicht.

        **Weggelassen wird nur, wenn der Partner tatsächlich dabei ist.**
        Ein Zwilling, dessen Partner für diese Merkmalsart gar nicht gilt,
        wäre sonst spurlos weg statt zusammengelegt. Genau diese Rechnung
        steht seit dem 07.09.2026 einmal, im Kern bei der Tabelle, über die
        sie eine Aussage macht (:func:`~app.core.registry.shown_of_twins`) —
        vorher dreimal in zwei Fassungen, zwei davon in dieser Datei.

        **Und ohne die Zeilen, die ein Griff ersetzt** (:data:`HANDLE_INSTEAD`).
        """
        return shown_at_feature(kind, shown_of_twins(REGISTRY.for_feature(kind)))

    def _feature_kind(self) -> str | None:
        """Die Art des gewählten Merkmals — ``hole``, ``face``, ``edge``.

        Gelesen wurde sie aus der zweiten Spalte des Baums, und dort steht das
        Maß: „Ø3,22 mm" für eine Bohrung, „4334 mm²" für eine Fläche. Als Art
        an ``for_feature`` gereicht, fand die Anfrage nie eine Operation, und
        das Kontextmenü an einem Merkmal bestand aus Ausblenden und Alles
        andere ausblenden — an genau dem Ort, den §18.5 „die wichtigste
        Einzelfunktion" nennt.
        """
        feature = self._chosen_feature()
        return feature.kind if feature is not None else None

    def _chosen_feature(self) -> Feature | None:
        """Das gewählte Merkmal selbst, oder nichts.

        Zwei Fragen hängen daran, und beide brauchen dasselbe Objekt: was es
        anbietet (``kind``) und aus welchem Schritt es stammt
        (``created_by``).
        """
        feature_id = self.selected_feature()
        object_id = self.selected()
        if feature_id is None or object_id is None or self._result is None:
            return None
        entry = self._result.scene.objects.get(object_id)
        return entry.features.get(feature_id) if entry is not None else None

    def isolation_holds(self, chosen: tuple[str, ...]) -> bool:
        """Ob genau diese Auswahl gerade isoliert ist — alles andere versteckt.

        Eine Antwort für Beschriftung **und** Wirkung: Vorher lasen beide
        dasselbe Feld mit verschiedener Frage, und der Rechtsklick auf einen
        ausgeblendeten Körper versprach „Alles andere ausblenden" und blendete
        alles ein (Gesamtreview I-6).
        """
        if not self._hidden:
            return False
        everything = {
            item.data(0, Qt.ItemDataRole.UserRole)
            for index in range(self.tree.topLevelItemCount())
            if (item := self.tree.topLevelItem(index)) is not None
        }
        return self._hidden == frozenset(everything - set(chosen))

    def context_menu(self) -> QMenu | None:
        """Das Menü zur aktuellen Auswahl, oder nichts.

        Gebaut wird es hier und nicht dort, wo es aufgeht: der Viewport zeigt
        dasselbe Menü, wenn jemand mit rechts auf einen Körper klickt (§18.5) —
        zwei Menüs mit derselben Aufgabe wären zwei Gelegenheiten,
        auseinanderzulaufen.
        """
        chosen = self.selected_objects()
        if not chosen:
            return None

        menu = QMenu(self)
        # ``QMenu`` zeigt Tooltips von Haus aus nicht an; die Sätze der
        # Einträge sollen aber lesbar sein.
        menu.setToolTipsVisible(True)
        self._add_source_step(menu)
        # Vor der Sichtbarkeit und aus demselben Grund wie der Schritt darüber:
        # Er gilt der **Fläche**, die Sichtbarkeit dem Körper. Wer mit rechts
        # auf eine Deckfläche zeigt, meint die Deckfläche (§18.5).
        self._add_sketch_on_face(menu)
        self._add_visibility(menu, chosen)
        # **Keine Operationen mehr** (Robert, 11.09.2026: „ebenso dann beim
        # rechtsklick im objektbaum"). Sie standen hier als dieselbe Liste wie
        # rechts in der Karte der Handlungen — gruppiert, gefaltet, mit dem
        # Katalog an der Stelle der Bausteine —, und zwei Orte für dieselbe
        # Liste sind einer zu viel. Was bleibt, gibt es nur hier: der Weg vom
        # Ergebnis zurück zum Schritt, die Skizze auf der Fläche und die
        # Sichtbarkeit des Körpers.
        return menu

    def _on_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        """Ein Doppelklick öffnet den Dialog, der diese Zeile ändert (§18.5).

        **Dieselbe Reihenfolge wie im Kontextmenü**, und nicht eine zweite
        Meinung darüber, was zu einer Zeile gehört: erst der Schritt, der sie
        erzeugt hat — dort stehen ihre Maße als Parameter —, dann die erste
        Operation, die für ihre Merkmalsart gilt und in dieser Lage auch laufen
        kann.

        **Zeilen mit Kindern behalten das Auf- und Zuklappen.** Ein Körper und
        ein Dach über gleichartigen Merkmalen sind keine Sache, die man ändert;
        Qt klappt sie auf, und das ist die richtige Antwort auf den
        Doppelklick.

        **Und wo nichts gilt, geschieht nichts.** Für ein erkanntes Merkmal
        ohne eigene Operation — ein Wulst, eine Verrundung — gibt es heute
        keinen Dialog, der es ändert; irgendeinen zu öffnen wäre ein Angebot,
        das die Frage nicht beantwortet. Der Statushinweis der Zeile sagt
        weiterhin, was sie ist.
        """
        if self.tree.selection_allowed is not None and not self.tree.selection_allowed():
            return
        if item.childCount():
            return
        step: int | None = item.data(0, _STEP_ROLE)
        if step is None:
            feature = self._chosen_feature()
            if feature is not None and feature.created_by is not None:
                step = feature.created_by
        if step is not None:
            self.stepRequested.emit(step)
            return
        kind = self._feature_kind()
        if kind is None:
            return
        kinds = self.kinds_of_selection()
        spoiled = spoiled_the_exact_body(self._result)
        for spec in self.operations_for_feature(kind):
            if not kind_requirement(spec, kinds, spoiled):
                self.operationRequested.emit(spec)
                return

    def _on_context_menu(self, position: QPoint) -> None:
        # **Die Position kommt schon in Koordinaten des Ansichtsbereichs.**
        # Hier stand eine Umrechnung mit ``viewport().mapFrom(self.tree, …)``
        # und darüber die Begründung, das Signal liefere Koordinaten des
        # ganzen Baums. Das ist falsch: Qt stellt das Kontextmenü-Ereignis dem
        # Viewport zu, und von dort kommt die Position. Die Umrechnung zog
        # deshalb noch einmal die Kopfzeile ab und traf eine Zeile weiter oben
        # — bei kleiner Zeilenhöhe zwei (gemessen 03.09.2026: Kopfzeile 17 px,
        # Zeilenhöhe 12 px; ein Klick auf Zeile 5 wählte Zeile 4, ein Klick auf
        # die erste wählte gar nichts).
        #
        # Gemeldet von Robert: „wenn ich einen Eintrag links mit Rechtsklick
        # anwähle springen wir 2 Einträge hoch." Die Verlaufsliste im selben
        # Modul nimmt ihre Position seit je roh (``_on_context_menu`` dort),
        # und sie trifft.
        if self.tree.selection_allowed is not None and not self.tree.selection_allowed():
            return
        item = self.tree.itemAt(position)
        if item is not None:
            # Der Rechtsklick meint die Zeile darunter. Ohne diese Auswahl
            # öffnete sich zwar das passende Kontextmenü, der Dialog erbte
            # aber ein vorher gewähltes Merkmal oder keines — ein Gewinde
            # stand dann nicht in der gerade angeklickten Bohrung. Geleert wird
            # ohne Zwischenmeldung, gemeldet der neue Stand.
            with QSignalBlocker(self.tree):
                self.tree.clearSelection()
            item.setSelected(True)
            self.tree.setCurrentItem(item)
        menu = self.context_menu()
        if menu is not None:
            menu.exec(self.tree.viewport().mapToGlobal(position))
            # **Ein Menü je Rechtsklick, und keines bleibt liegen.** Es entsteht
            # als Kind dieses Baums und lebte sonst bis zum Fenster: Gemessen
            # am gebauten Fenster wuchsen dreißig Rechtsklicks auf dreißig
            # zusätzliche ``QMenu``-Kinder, jedes mit seinen Aktionen und den
            # Rückrufen daran. ``deleteLater`` und nicht ``setParent(None)`` —
            # das machte daraus ein eigenes Fenster (RM-101).
            menu.deleteLater()

    def _add_source_step(self, menu: QMenu) -> None:
        """„Diesen Schritt ändern" — der Weg vom Ergebnis zurück zum Schritt
        (§21.2).

        **Ein erzeugtes Merkmal bietet immer den Schritt an, der es erzeugt
        hat.** Die Frage lautete lange, welche Operation fachlich auf ein
        fertiges Gewinde gehört, und ``for_feature`` gab darauf nichts zurück
        — ``thread`` stand deshalb als benannte Ausnahme im Konsistenztest.
        Über ``applies_to`` wäre die Antwort eine neue Operation je
        Merkmalsart gewesen; über die Provenienz ist sie ein Eintrag, der für
        alle gilt und jede neue Merkmalsart von selbst mitnimmt.

        Er steht **vor** der Sichtbarkeit, weil er dem Merkmal gilt und die
        Sichtbarkeit dem Körper: Wer mit rechts auf eine Bohrung zeigt, meint
        die Bohrung (§18.5). Und er ist der einzige Weg vom *Ergebnis* zurück
        zum *Schritt* — ohne ihn sucht der Kunde unter vierzehn Zeilen des
        Verlaufs die eine, die das Ding erzeugt hat, das er gerade ansieht.

        Ein **erkanntes** Merkmal hat keinen Erzeuger und bekommt den Eintrag
        nicht: Er führte dort ins Leere, und das ist schlechter als keiner.

        **Und der Gruppenknoten eines Bausteins bietet ihn auch an.** Er ist
        kein Merkmal, sondern deren Dach — aber er ist die Zeile, die den
        Baustein beim Namen nennt, und wer den Einhänger ändern will, zeigt
        auf „Lochwand-Einhänger" und nicht auf eine seiner Flächen.
        """
        step = self._chosen_step()
        if step is None:
            feature = self._chosen_feature()
            if feature is None or feature.created_by is None:
                return
            step = feature.created_by
        change = menu.addAction(tr("Diesen Schritt ändern"))
        change.setStatusTip(tr("Öffnet den Schritt, der dieses Merkmal erzeugt hat."))
        change.triggered.connect(lambda _checked=False: self.stepRequested.emit(step))
        menu.addSeparator()

    def _chosen_step(self) -> int | None:
        """Die Schrittnummer der gewählten Zeile — nur Gruppenknoten haben eine."""
        items = self.tree.selectedItems()
        if len(items) != 1:
            return None
        value: int | None = items[0].data(0, _STEP_ROLE)
        return value

    def _add_sketch_on_face(self, menu: QMenu) -> None:
        """„Auf dieser Fläche zeichnen" — der Weg auf ein vorhandenes Teil.

        Bauplan §30.1 nennt zwei Orte für eine Skizzenebene: eine Hauptebene
        **oder eine angeklickte planare Fläche**, und
        ``app/core/sketch/planes.py`` nennt die zweite „die interessantere,
        denn sie ist der Weg, auf einem vorhandenen Teil weiterzubauen, statt
        daneben". Die Rechnung dazu steht seit je; **erreichbar war sie nur
        über ein Klappfeld** mit Zeilen wie „Fläche an Gehäuse — 2 400 mm²,
        oben", also über das Wiedererkennen einer Fläche in einer Liste statt
        über das Zeigen auf sie.

        Dass es der richtige Weg ist, sagt die Anwendung schon selbst:
        ``sketch_pocket`` verspricht in ihrem ``doc`` „Ein Klick auf eine
        Fläche trägt den Ort vorab ein". Über den Operationsdialog wird das
        eingelöst (``OpDialog.take_feature``), über den Skizzenmodus nicht —
        dasselbe Versprechen, an einer Stelle gehalten und an der anderen
        nicht.

        Nur an einer **Fläche**: Auf einer Bohrung oder einer Kante gibt es
        keine Ebene zu zeichnen, und ein Eintrag, der dort ins Leere führte,
        wäre schlechter als keiner — dieselbe Überlegung wie bei
        :meth:`_add_source_step` und dem erkannten Merkmal ohne Erzeuger.
        """
        if self._feature_kind() != "face":
            return
        feature_id = self.selected_feature()
        if feature_id is None:
            return
        draw = menu.addAction(tr("Auf dieser Fläche zeichnen"))
        draw.setStatusTip(tr("Beginnt eine Skizze auf dieser Fläche statt auf einer Grundebene."))
        draw.triggered.connect(
            lambda _checked=False: self.sketchOnFaceRequested.emit(str(feature_id))
        )

    def _add_visibility(self, menu: QMenu, chosen: tuple[ObjectId, ...]) -> None:
        """Ein- und ausblenden und isolieren (§18.8).

        Keine Operationen: eine Ansichtsentscheidung gehört nicht in den
        Verlauf, sonst steht dort bald mehr Hin und Her als Arbeit. Zurück
        kommt sie über denselben Eintrag, nicht über ein Undo.
        """
        wants_hiding = any(object_id not in self._hidden for object_id in chosen)
        if self.selected_features():
            # **An einem Merkmal sagt der Eintrag, was er trifft.** Die
            # Sichtbarkeit gilt dem Körper (§18.8) — ein Merkmal lässt sich
            # nicht für sich ausblenden. „Ausblenden" an einer Bohrung oder an
            # einem Bausteindach las sich als Zusage über das Merkmal, und der
            # ganze Körper verschwand (Robert, 16.09.2026).
            label = tr("Körper ausblenden") if wants_hiding else tr("Körper einblenden")
        else:
            label = tr("Ausblenden") if wants_hiding else tr("Einblenden")
        hide = menu.addAction(label)
        hide.triggered.connect(
            lambda _checked=False: self.visibilityRequested.emit(chosen, not wants_hiding)
        )

        isolate = menu.addAction(
            tr("Alles andere ausblenden") if not self.isolation_holds(chosen) else tr("Alle zeigen")
        )
        isolate.triggered.connect(lambda _checked=False: self.isolateRequested.emit(chosen))


def _empty_parameters_text() -> str:
    """Der leere Zustand sagt, wozu die Leiste da ist — „Noch keine
    Parameter." allein ließ die Frage offen, wie denn einer entsteht."""
    return tr(
        "Noch keine Parameter. Ein Parameter ist ein benanntes Maß — "
        "Operationen und Skizzen rechnen mit ihm."
    )


class _CompactParameterUnitBox(QComboBox):
    """Zeigt die gewählte Einheit kurz und die Auswahlliste ausführlich.

    Die linke Karte ist 260 Pixel breit. Ein geschlossener Eintrag wie
    „mm — Länge“ beanspruchte dort fast so viel Platz wie die Zahl selbst;
    aufgeklappt ist die Erklärung dagegen genau richtig. Deshalb zeichnet nur
    die geschlossene Auswahl den gespeicherten Code. Die Einträge im Menü
    bleiben unverändert und erklären weiterhin ihre Bedeutung.
    """

    def _compact_text(self) -> str:
        # Keine Einheit ist absichtlich leer. Im geöffneten Menü steht weiter
        # der übersetzte Satz „ohne Einheit“; ein erfundenes Symbol in der
        # geschlossenen Anzeige wäre dagegen ein weiterer Oberflächentext.
        return str(self.currentData() or "")

    def paintEvent(self, _event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = self._compact_text()
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt gibt den Namen
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        codes = [str(self.itemData(index) or "") for index in range(self.count())]
        width = max((self.fontMetrics().horizontalAdvance(code) for code in codes), default=0)
        content = QSize(width + 2 * TIGHT, super().sizeHint().height())
        return self.style().sizeFromContents(
            QStyle.ContentsType.CT_ComboBox,
            option,
            content,
            self,
        )

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt gibt den Namen
        return self.sizeHint()


class ParameterPanel(QWidget):
    """Benannte Projektmaße; an einer Zahl zu drehen baut das Modell
    neu (§13).
    """

    parameterEdited = Signal(str, float)
    parameterUnitEdited = Signal(str, str)
    """Eine feste Einheit wurde in der Zeile gewählt."""
    heightChanged = Signal()
    """Die frei gesetzte Seitenkarte soll ihre Geometrie neu verteilen."""
    addRequested = Signal()
    """Der Nutzer will ein Maß benennen — das Fenster öffnet den Dialog."""
    bindRequested = Signal()
    """Feste Zahlen, die zu Maßen passen, binden — das Fenster öffnet die Wahl (RM-184)."""
    limitsRequested = Signal(str)
    """Grenzen, Einheit oder Ausdruck eines vorhandenen Maßes ändern.

    Trägt den **Namen** des Parameters. Grenzen waren anlegbar und nie
    änderbar: Die Leiste liest ``minimum``/``maximum`` als Spinbox-Grenzen,
    und wer eine Obergrenze zu eng gesetzt hatte, fand ein Feld, das ohne ein
    Wort klemmt — *Parameter anlegen …* wies den Namen ab, und ein dritter Weg
    fehlte (§2.1: keine Sackgassen).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        self._room: int | None = None
        """Was die Überlagerung dieser Karte zugeteilt hat, oder nichts.

        ``None`` heißt „noch nicht zugeteilt"; dann gilt der Wunsch. Dieselbe
        Bedeutung wie bei den drei Nachbarkarten der Spalte."""
        # **Die Zeilen rollen, der Knopf nicht.** Ohne den Rollbereich hätte
        # ein Deckel die untersten Zeilen nicht versteckt, sondern
        # unerreichbar gemacht — genau der Fehler, den ``extra_height``
        # beschreibt. Und *Parameter anlegen …* bleibt darunter stehen: Er ist
        # der einzige Weg zu einem neuen Maß und darf nicht wegrollen, aus
        # demselben Grund, aus dem die Filamentkarte ihre Knöpfe außerhalb
        # ihrer Liste führt.
        # Die Mindestbreite aller Zeilen muss bis zur Karte reisen. Ein bloß
        # versteckter Querbalken lässt Qt beim Tab-Fokus die Maßnamen wegrollen.
        self._scroll = ColumnScroller(self)
        self._sheet = QWidget(self._scroll)
        self._scroll.setWidget(self._sheet)
        self._form = QFormLayout(self._sheet)
        self._form.setContentsMargins(0, 0, 0, 0)
        self._empty = QLabel(_empty_parameters_text(), self)
        self._empty.setWordWrap(True)
        fit_wrapped(self._empty)
        self._form.addRow(self._empty)
        self._editors: dict[str, QDoubleSpinBox] = {}
        self._unit_editors: dict[str, QComboBox] = {}
        self._detail_buttons: dict[str, QToolButton] = {}
        """Der sichtbare Weg zu Grenzen, Einheit und Ausdruck jeder Zeile."""
        self._derived: dict[str, QLabel] = {}
        """Die Anzeige je abgeleitetem Maß — sein Ausdruck besitzt den Wert."""
        self._titles: dict[str, QLabel] = {}
        """Die Beschriftung je Zeile."""
        self._hints: dict[str, QLabel] = {}
        """Was unter der Zeile über ihre Verwendung steht („Nicht verwendet“,
        „2 feste Zahlen passen“) — über die ganze Kartenbreite. In der schmalen
        Beschriftungsspalte brach es in vier Zeilen um, und die letzte stand
        unter der nächsten Zeile."""
        self._sliders: dict[str, QSlider] = {}
        """Der Regler je Maß mit eigener Unter- und Obergrenze (§13, RM-359 F8)."""
        self._layout: tuple[object, ...] | None = None
        """Was die Zeilen ausmacht (:meth:`_layout_of`) — gleich, so werden nur
        die Werte gesetzt und kein Feld verliert den Fokus (RM-355)."""
        self._refused_name = ""
        """Zu welchem Maß die Ablehnungszeile gehört — leer ohne."""
        self._document: Document | None = None
        """Das Dokument, dessen Maße die Zeilen zeigen — Werte setzen nur in ihm (RM-452)."""
        self._limits: dict[str, tuple[float, float]] = {}
        """Die wirksamen Grenzen je Zahlenfeld (:meth:`_bounds`). Das Qt-Feld
        reicht darüber hinaus, wenn das Dokument eine Zahl jenseits trägt
        (RM-447)."""
        self._refusal: QWidget | None = None
        """Die Zeile unter einem Feld, das eine getippte Zahl abgelehnt hat — oder nichts.

        Sie nennt die Grenze und trägt den Weg, sie zu ändern (*Parameter
        ändern …*). Eine je Leiste: Getippt wird in einem Feld."""
        self._rows: dict[QWidget, str] = {}
        """Welches Widget zu welchem Parameter gehört — für das Kontextmenü.

        Beide Hälften der Zeile stehen darin: Wer mit rechts auf die
        Beschriftung zeigt, meint dieselbe Zeile wie der, der auf das Feld
        zeigt.
        """
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        # §2.3: das Anlegen war ein Agentenwerkzeug und sonst nichts — wer
        # ohne Sprachmodell arbeitet, brauchte einen Weg mit der Maus.
        self.add_button = QPushButton(tr("Parameter anlegen …"), self)
        self.add_button.clicked.connect(self.addRequested)
        # **Und der Weg zu den Maßen, die nur halb wirken** (Dateiaudit §4):
        # Steht im Stapel eine feste Zahl, die genau zu einem Maß passt, folgt
        # sie ihm nicht. Der Knopf steht nur, wenn es solche Zahlen gibt
        # (``scene.parameter_binding``); die Wahl trifft der Dialog.
        self.bind_button = QPushButton(tr("Feste Zahlen binden …"), self)
        self.bind_button.clicked.connect(self.bindRequested)
        _set_shown(self.bind_button, False)
        outer.addWidget(self._scroll)
        outer.addWidget(self.bind_button, alignment=Qt.AlignmentFlag.AlignLeft)
        outer.addWidget(self.add_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self._outer = outer
        self._fit()

    def _around_the_rows(self) -> int:
        """Was fest um die Zeilen herum steht: Knöpfe, Ränder, Abstände.

        Aus den Wunschhöhen gerechnet und nicht aus den gelegten — dieselbe
        Bedingung, unter der die ganze Verteilung stillsteht
        (``OverlayHost._share_room``). Wortgleich mit
        ``FilamentPanel._around_the_list`` ist das nicht: Dort stehen ein
        Hinweis und drei Knöpfe, hier einer — zwei, solange *Feste Zahlen
        binden* dasteht; ein verborgener Knopf bekommt auch keinen Abstand.
        """
        margins = self._outer.contentsMargins()
        shown = [
            widget
            for index in range(self._outer.count())
            if (item := self._outer.itemAt(index)) is not None
            and (widget := item.widget()) is not None
            and not widget.isHidden()
        ]
        gaps = max(len(shown) - 1, 0) * self._outer.spacing()
        buttons = self.add_button.sizeHint().height()
        if not self.bind_button.isHidden():
            buttons += self.bind_button.sizeHint().height()
        return margins.top() + margins.bottom() + gaps + buttons

    def wanted_height(self) -> int:
        """Die Höhe, bei der jede Zeile zu sehen wäre.

        **Ohne diese drei Methoden teilt die Überlagerung dieser Karte
        nichts zu** — ``_share_room`` fragt nur Kinder mit dem Raumvertrag,
        und wer ihn nicht hat, „behält seine eigene Höhe". Genau das tat sie:
        Bei zehn Parametern stand sie auf 378 Bildpunkten und damit höher als
        Baum, Verlauf und Filamente zusammen (148, 58, 126 — gemessen am
        07.09.2026 im gebauten Fenster). Die Filamentkarte bekam 126 von 144
        gewünschten, und die Spalte war überfüllt.
        """
        return self._around_the_rows() + self._sheet.sizeHint().height()

    def least_height(self) -> int:
        """Und die, unter die diese Karte nicht geht, was auch zugeteilt wird.

        Drei Zeilen, wie bei den Nachbarn — aber **nie höher als der Wunsch**:
        Eine Karte ohne Parameter zeigt einen umbrochenen Satz, und Platz für
        drei Zeilen wäre Platz, den sie niemandem zeigen kann, während die
        Nachbarn ihn brauchen (dieselbe Feinheit wie bei der Filamentkarte).
        """
        rows = LEAST_PARAMETER_ROWS * (self.add_button.sizeHint().height() + TIGHT)
        return min(self._around_the_rows() + rows, self.wanted_height())

    def set_room(self, pixels: int) -> None:
        """Wie hoch diese Karte werden darf."""
        if pixels == self._room:
            return
        self._room = pixels
        self._fit()

    def _fit(self) -> None:
        """So hoch wie der Inhalt — wie die beiden Karten darüber und darunter.

        Der Streckfaktor am Ende ist weg: er beanspruchte Restplatz in einer
        Spalte, die keinen verteilt, und der umbrochene Satz des leeren
        Zustands wurde stattdessen gestaucht, bis er unter dem Knopf lag.

        Das Label wird hier **nicht** angefasst: ``show_document`` räumt die
        Zeilen des Formulars weg, und damit ist das C++-Objekt des alten
        Labels fort, während die Python-Referenz noch steht. Wer es hier
        vermäße, stürbe an genau dem — beim ersten Projekt mit Parametern.

        Nach ``removeRow`` und dem Neuaufbau trägt das äußere Layout noch
        seinen zwischengespeicherten Höhenwert vom alten Inhalt. Auf Windows
        kam dessen ``LayoutRequest`` zu spät für die frei gesetzte
        Überlagerung: Aus drei normalen Zeilen wurden dadurch elf Pixel hohe
        Schlitze. Deshalb wird erst im nächsten Ereignisschritt gemessen; dann
        hat Qt die neuen Kindgrößen in beide Layoutstufen aufgenommen.
        """
        self._form.invalidate()
        self._outer.invalidate()
        self.updateGeometry()
        QTimer.singleShot(0, self, self._apply_fitted_height)

    def _apply_fitted_height(self) -> None:
        """Die inzwischen berechnete Inhaltshöhe an Karte und Wirt melden.

        **Höchstens so hoch wie zugeteilt.** Ohne den Deckel setzte diese
        Karte ihre volle Inhaltshöhe als Mindesthöhe durch und nahm der
        Spalte, was die Nachbarn brauchten. Über die Zuteilung hinaus rollen
        die Zeilen jetzt (``self._scroll``); der Boden bleibt gewahrt, damit
        nicht ein Deckel von wenigen Pixeln aus der Karte einen Schlitz
        macht.
        """
        self._form.activate()
        self._outer.activate()
        height = self.wanted_height()
        if self._room is not None:
            height = max(self.least_height(), min(height, self._room))
        # **Fest wird der Rollbereich, nicht die Karte.** Die drei Nachbarn
        # tun dasselbe (``fit_to_rows`` setzt die Höhe der *Liste*), und das
        # ist keine Geschmacksfrage: ``extra_height`` fragt jede Karte nach
        # ihrem ``sizeHint``, um daraus den Kopf zu rechnen, und ein Deckel
        # auf der Karte selbst geht dort mit ein. Gemessen wanderte das
        # Beiwerk der Spalte dadurch von 120 auf 376 Bildpunkte, je nachdem,
        # was zuletzt zugeteilt worden war — genau die Rückkopplung, gegen die
        # der Docstring von ``extra_height`` „nie über die gesetzten Höhen"
        # schreibt.
        self._scroll.setFixedHeight(max(height - self._around_the_rows(), 0))
        if height == self.minimumHeight():
            return
        self.setMinimumHeight(height)
        self.updateGeometry()
        self.heightChanged.emit()

    def parameter_at(self, position: QPoint) -> str | None:
        """Welcher Parameter an dieser Stelle steht — oder ``None``.

        ``childAt`` gibt das **tiefste** Kind zurück, und eine ``NumberSpin``
        hat ein eigenes Eingabefeld darin: Ohne den Gang nach oben trifft ein
        Rechtsklick mitten in die Zahl niemanden.
        """
        widget: QWidget | None = self.childAt(position)
        while widget is not None and widget is not self:
            name = self._rows.get(widget)
            if name is not None:
                return name
            widget = widget.parentWidget()
        return None

    def context_menu(self, position: QPoint) -> QMenu | None:
        """Das Menü zur Zeile an dieser Stelle — oder ``None``, wo keine steht.

        Vom Öffnen getrennt, wie beim Objektbaum daneben: ``exec`` blockiert,
        und wer einen Eintrag prüfen will, braucht das Menü und nicht das
        Fenster darüber.

        Kein Menü auf leerer Fläche: Ein Kontextmenü mit einem einzigen
        ausgegrauten Eintrag sagt nur, dass man danebengeklickt hat, und das
        weiß man schon.
        """
        name = self.parameter_at(position)
        if name is None:
            return None
        menu = QMenu(self)
        # Ein Menü zeigt Hinweise nur, wenn man es ihm sagt — sonst kommt der
        # Satz an und Qt zeigt ihn nie.
        menu.setToolTipsVisible(True)
        entry = menu.addAction(tr("Ändern …"))
        note = tr("Untergrenze, Obergrenze, Einheit und Ausdruck dieses Maßes — rücknehmbar.")
        entry.setToolTip(note)
        entry.setStatusTip(note)
        entry.triggered.connect(lambda _checked=False, key=name: self.limitsRequested.emit(key))
        return menu

    def _on_context_menu(self, position: QPoint) -> None:
        menu = self.context_menu(position)
        if menu is not None:
            menu.exec(self.mapToGlobal(position))
            # Wie im Objektbaum: Das Menü gehört diesem Klick und nicht dem
            # Rest der Sitzung.
            menu.deleteLater()

    def _remember_row(self, name: str, field: QWidget) -> None:
        """Beide Hälften der Zeile dem Parameter zuordnen.

        Die Beschriftung baut ``addRow`` selbst aus der Zeichenkette;
        ``labelForField`` gibt sie heraus — dieselbe Stelle, an der auch der
        Operationsdialog seine Beschriftung wiederfindet.
        """
        self._rows[field] = name
        label = self._form.labelForField(field)
        if label is not None:
            self._rows[label] = name

    def _queue_parameter_edit(self, name: str, value: float) -> None:
        """Meldet eine fertige Eingabe erst nach dem Signal der Spinbox.

        ``show_document`` baut die Zeilen nach einer Änderung neu auf. Geschah
        das noch innerhalb von ``QDoubleSpinBox.valueChanged``, löschte Qt auf
        Windows das gerade sendende Eingabefeld; der Prozess verschwand ohne
        Fehlermeldung. Der nächste Ereignisschritt lässt das Signal vollständig
        zurückkehren, bevor die Leiste neu gebaut wird.
        """
        QTimer.singleShot(0, self, lambda: self.parameterEdited.emit(name, value))

    def _queue_parameter_unit_edit(self, name: str, unit: str) -> None:
        """Meldet auch die Einheit erst nach dem Signal ihrer Auswahlliste."""
        QTimer.singleShot(0, self, lambda: self.parameterUnitEdited.emit(name, unit))

    def _unit_activated(self, index: int) -> None:
        """Übernimmt die feste Auswahl, ohne den sendenden Kasten zu löschen."""
        editor = self.sender()
        if not isinstance(editor, QComboBox):
            return
        name = str(editor.property("parameterName") or "")
        if name:
            self._queue_parameter_unit_edit(name, str(editor.itemData(index) or ""))

    def _unit_editor(self, name: str, selected: str) -> QComboBox:
        """Die kompakte, nicht editierbare Einheitenauswahl einer Zeile."""
        editor = _CompactParameterUnitBox(self)
        wheel_needs_focus(editor)
        fill_parameter_units(editor, selected)
        editor.setProperty("parameterName", name)
        editor.setAccessibleName(tr("Einheit"))
        editor.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        editor.activated.connect(self._unit_activated)
        self._unit_editors[name] = editor
        return editor

    def refusal_text(self) -> str:
        """Der Satz der Ablehnung, der gerade unter einem Feld steht — leer ohne."""
        if self._refusal is None:
            return ""
        label = self._refusal.findChild(QLabel)
        return label.text() if label is not None else ""

    def _stored_beyond(self, name: str, editor: QDoubleSpinBox, unit: str) -> str:
        """Der Satz zu einer **gespeicherten** Zahl jenseits der Grenze — leer, wenn sie passt.

        Eine Datei kann *Breite* 5000 tragen, wo *Quader* höchstens 1000 mm
        breit wird; die Kette hält dann an. Das Feld zeigt die 5000 und nimmt
        die Korrektur an, und hier steht, warum die Zahl nicht geht (RM-447).
        """
        low, high = self._limits.get(name, (editor.minimum(), editor.maximum()))
        value = editor.value()
        slack = 0.5 * 10.0 ** -editor.decimals()
        if low - slack <= value <= high + slack:
            return ""
        above = value > high
        suffix = f" {unit}" if unit else ""
        return limit_sentence(
            editor.textFromValue(value) + suffix,
            editor.textFromValue(high if above else low) + suffix,
            above=above,
        )

    def _set_limits(self, editor: QDoubleSpinBox, document: Document, name: str) -> None:
        """Grenzen setzen, ohne eine gespeicherte Zahl jenseits davon zu klemmen (RM-447).

        Qt klemmte 5000 auf die Feldgrenze 1000: Die Leiste zeigte 1000, und
        1000 + Enter war keine Änderung — der Halt blieb, obwohl *Eingabe
        korrigieren* genau in dieses Feld führte. In 0.5.1 stand dort 5000.
        Das Qt-Feld reicht deshalb bis zur gespeicherten Zahl; der Satz der
        Ablehnung nennt die wirksame Grenze.
        """
        low, high = self._bounds(document, name)
        self._limits[name] = (low, high)
        stored = document.parameters[name].value
        shown_low, shown_high = min(low, stored), max(high, stored)
        if editor.minimum() != shown_low or editor.maximum() != shown_high:
            with QSignalBlocker(editor):
                editor.setRange(shown_low, shown_high)
        if isinstance(editor, (BoundedSpin, BoundedLengthSpin)):
            editor.name_limits(low, high)

    def _show_refusal(self, name: str) -> None:
        """Nennt unter dem Feld die Grenze, an der die getippte Zahl scheitert.

        Nie still (Regel des Zeichnens, ``zeichenflaeche.md``): Die abgelehnte
        Zahl bleibt markiert im Feld, darunter steht die Grenze, und der Knopf
        daneben öffnet *Parameter ändern*, wo sie steht. Eine Obergrenze, die
        zu eng gesetzt war, ist damit einen Klick entfernt.
        """
        editor = self._editors.get(name)
        unit = self._unit_editors.get(name)
        unit_text = str(unit.currentData() or "") if unit is not None else ""
        said = (
            editor.refusal(unit_text)
            if isinstance(editor, (BoundedSpin, BoundedLengthSpin))
            else ""
        )
        if not said and editor is not None:
            said = self._stored_beyond(name, editor, unit_text)
        if self._refusal is not None:
            self._form.removeRow(self._refusal)
            self._refusal = None
            self._refused_name = ""
        if editor is None:
            return
        editor.setAccessibleDescription(said)
        if not said:
            self._fit()
            return
        row = editor.parentWidget()
        if row is None:
            return
        # PySide liefert (Zeile, Rolle); der Stub kennt nur ``object``.
        position: Any = self._form.getWidgetPosition(row)
        row_index = int(position[0])
        refusal = QWidget(self._sheet)
        layout = QHBoxLayout(refusal)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
        sentence = QLabel(said, refusal)
        sentence.setWordWrap(True)
        fit_wrapped(sentence)
        set_level(sentence, "caption")
        layout.addWidget(sentence, 1)
        change = QPushButton(tr("Parameter ändern …"), refusal)
        change.setAccessibleDescription(said)
        # Über die Ereignisschleife: Der Dialog baut die Leiste neu, und dabei
        # ginge dieser Knopf mitten in seinem eigenen Signal unter.
        change.clicked.connect(
            lambda _checked=False, key=name: QTimer.singleShot(
                0, self, lambda: self.limitsRequested.emit(key)
            )
        )
        layout.addWidget(change)
        self._form.insertRow(row_index + 1, refusal)
        self._refusal = refusal
        self._refused_name = name
        self._fit()

    def _details_clicked(self) -> None:
        """Öffnet die erweiterten Angaben der angeklickten Parameterzeile."""
        button = self.sender()
        if not isinstance(button, QToolButton):
            return
        name = str(button.property("parameterName") or "")
        if name:
            self.limitsRequested.emit(name)

    def _add_parameter_row(self, name: str, title: str, value: QWidget, unit: QComboBox) -> None:
        """Zahl, Einheit und sichtbaren Änderungsweg als eine Zeile."""
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
        layout.addWidget(value, 1)
        layout.addWidget(unit)
        details = QToolButton(row)
        # Das ausführliche Wort würde neben Zahl und Einheit die 260-Pixel-
        # Karte sprengen. Die Ellipse ist der sichtbare „mehr“-Knopf; Tooltip
        # und zugänglicher Name sagen ohne Symbolwissen, was dahinterliegt.
        # Auch das sichtbare Symbol kommt aus dem Katalog (Regel 20). Jede
        # Übersetzung von „Ändern …“ endet mit derselben typografischen
        # Ellipse; nur sie wird in der schmalen Zeile gezeichnet.
        details.setText(tr("Ändern …")[-1])
        details.setAutoRaise(True)
        note = tr("Untergrenze, Obergrenze, Einheit und Ausdruck dieses Maßes — rücknehmbar.")
        details.setToolTip(note)
        # Mit dem Maß im Namen (RM-359 F9): Dreimal „Parameter ändern“ und
        # dreimal „Einheit“ hießen für einen Vorleser drei gleiche Knöpfe.
        details.setAccessibleName(tr("{name} ändern", name=title))
        unit.setAccessibleName(tr("Einheit von {name}", name=title))
        value.setAccessibleName(title)
        details.setProperty("parameterName", name)
        details.clicked.connect(self._details_clicked)
        layout.addWidget(details)
        self._detail_buttons[name] = details
        label = QLabel(title, self)
        label.setWordWrap(True)
        fit_wrapped(label)
        label.setBuddy(value)
        self._titles[name] = label
        self._form.addRow(label, row)
        self._remember_row(name, row)
        hint = QLabel(self)
        hint.setWordWrap(True)
        set_level(hint, "caption")
        fit_wrapped(hint)
        self._form.addRow(hint)
        self._hints[name] = hint
        self._rows[hint] = name
        self._show_usage(name, title, row)

    def _show_usage(self, name: str, title: str, row: QWidget) -> None:
        """Beschriftung und Kurzhilfe einer Zeile nach dem jüngsten Ergebnis."""
        label = self._titles[name]
        uses = self._usage_result.parameter_usage if self._usage_result is not None else None
        fitting = len(self._spots_for(name))
        unused = uses is not None and name in uses and not uses[name]
        if unused and fitting:
            usage = (
                tr("Nicht verwendet — eine feste Zahl passt")
                if fitting == 1
                else tr("Nicht verwendet — {count} feste Zahlen passen", count=fitting)
            )
        elif unused:
            usage = tr("Nicht verwendet")
        elif fitting:
            usage = (
                tr("Eine feste Zahl passt")
                if fitting == 1
                else tr("{count} feste Zahlen passen", count=fitting)
            )
        else:
            usage = ""
        label.setText(title)
        note = self._usage_note(name)
        hint = self._hints.get(name)
        if hint is not None:
            hint.setText(usage)
            hint.setToolTip(note)
            self._form.setRowVisible(hint, bool(usage))
        label.setToolTip(note)
        # Der Vorleser hört den Hinweis an der Beschriftung, wie er ihn vorher las.
        label.setAccessibleDescription("\n".join(part for part in (usage, note) if part))
        row.setToolTip(note)

    def _usage_note(self, name: str) -> str:
        """Belegte Operationsfelder nennen; eine ausstehende Prüfung urteilt nicht."""
        result = self._usage_result
        if result is not None and result.parameter_usage_error is not None:
            return tr("Verwendung unklar — prüfen Sie die Ausdrücke im Projekt.")
        if result is None or result.parameter_usage is None:
            return tr("Die Verwendung wird mit dem Modell geprüft.")
        uses = result.parameter_usage.get(name)
        if uses is None:
            return tr("Die Verwendung wird mit dem Modell geprüft.")
        if not uses:
            return tr(
                "Dieses Maß wird von keiner Operation verwendet. Öffnen Sie einen Schritt "
                "im Verlauf und tragen Sie =@{name} in das passende Maßfeld ein."
            ).format(name=name)
        lines = []
        for use in uses[:8]:
            operation = self._usage_operations[use.op_id]
            spec = REGISTRY.get(operation.op)
            field = next(entry for entry in spec.params.spec() if entry.name == use.field)
            lines.append(
                tr("Operation {number}: {operation} — {field}").format(
                    number=step_number(self._document, use.op_id),
                    operation=spec.title,
                    field=field.title,
                )
            )
        if len(uses) > 8:
            lines.append(tr("Weitere Verwendungen: {count}").format(count=len(uses) - 8))
        return "\n".join([*lines, *self._spot_lines(name)])

    def _spots_for(self, name: str) -> tuple[BindingSpot, ...]:
        """Die festen Zahlen, deren erster Vorschlag dieses Maß liest."""
        result = self._usage_result
        if result is None:
            return ()
        return tuple(spot for spot in result.binding_spots if name in spot.choices[0].parameters)

    def _spot_lines(self, name: str) -> list[str]:
        """Wo eine feste Zahl zu diesem Maß passt — für die Kurzhilfe der Zeile."""
        from app.ui.binding_dialog import spot_title

        spots = self._spots_for(name)
        if not spots or self._document is None:
            return []
        lines = [
            tr(
                "{place} passt zu {expression}",
                place=spot_title(self._document, spot),
                expression=spot.choices[0].expression.removeprefix("="),
            )
            for spot in spots[:8]
        ]
        if len(spots) > 8:
            lines.append(tr("Weitere feste Zahlen: {count}", count=len(spots) - 8))
        return lines

    def _show_binding(self) -> None:
        """*Feste Zahlen binden …* nur, wenn es eine gibt — mit ihrer Zahl am Knopf."""
        result = self._usage_result
        spots = result.binding_spots if result is not None else ()
        shown = bool(spots)
        if shown:
            note = tr(
                "{count} feste Zahlen passen zu Projektmaßen. Gebunden folgen sie dem Maß, "
                "wenn Sie es ändern.",
                count=len(spots),
            )
            self.bind_button.setToolTip(note)
            self.bind_button.setAccessibleDescription(note)
        if shown != (not self.bind_button.isHidden()):
            _set_shown(self.bind_button, shown)
            self._fit()

    def show_document(self, document: Document, result: EvaluationResult | None = None) -> None:
        """Zeigt die Maße des Dokuments — **bestehende Zeilen behalten ihr Feld** (RM-355).

        Nach jeder Änderung baute die Leiste alle Zeilen neu, und das gerade
        bediente Feld ging dabei unter: Ein zweites ↑ in *Breite* traf nichts
        mehr, gedreht wurde 61 statt 62, und Mausrad, gehaltener Pfeilknopf
        und Tab brachen genauso ab — an der Geste, für die Weg 2 da ist.
        Bleibt die Gestalt der Zeilen gleich (:meth:`_layout_of`), werden nur
        Werte und Hinweise gesetzt; sonst wird neu gebaut, und der Fokus geht
        an dasselbe Maß zurück.

        **Nur innerhalb eines Dokuments** (RM-452): Gleiche Zeilen in einem
        anderen Projekt sind andere Maße. Mit gleichem Wert setzte die Leiste
        dort nichts neu, und die in A abgelehnte Zahl stand samt Grenzsatz in
        B. Ein anderes Dokument wird neu gebaut, ohne Fokus mitzunehmen.
        """
        self._usage_result = result
        self._usage_operations = {operation.id: operation for operation in document.ops}
        same = document is self._document
        # Die Sitzung tauscht ``project.document`` nur bei einem Projektwechsel
        # aus; innerhalb eines Projekts ändert sie dasselbe Objekt. Die
        # Referenz hält es am Leben, damit kein neues Dokument seine Kennung erbt.
        self._document = document
        if not same:
            self._rebuild(document)
        elif not self._refresh_in_place(document):
            focus = QApplication.focusWidget()
            focused = next(
                (
                    name
                    for name, editor in self._editors.items()
                    if focus is not None and (editor is focus or editor.isAncestorOf(focus))
                ),
                "",
            )
            self._rebuild(document)
            editor = self._editors.get(focused)
            if editor is not None:
                editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self._mark_stored_beyond()
        self._show_binding()

    def _mark_stored_beyond(self) -> None:
        """Eine gespeicherte Zahl jenseits ihrer Grenze bekommt ihren Satz (RM-447).

        Eine getippte Ablehnung geht vor: Sie ist das, woran gerade gearbeitet wird.
        """
        if self._refusal is not None and self._refused_name in self._editors:
            editor = self._editors[self._refused_name]
            if isinstance(editor, (BoundedSpin, BoundedLengthSpin)) and editor.refused_value():
                return
        for name, editor in self._editors.items():
            unit = self._unit_editors.get(name)
            if self._stored_beyond(name, editor, str(unit.currentData() or "") if unit else ""):
                self._show_refusal(name)
                return
        if self._refusal is not None:
            self._form.removeRow(self._refusal)
            self._refusal = None
            self._refused_name = ""
            self._fit()

    def focus_parameter(self, name: str) -> bool:
        """Setzt den Fokus in die Zeile eines Maßes — ``False``, wenn es keine gibt.

        Der Weg von *Eingabe korrigieren*, wenn das Feld des angehaltenen
        Schritts ein Maß liest (RM-354): Im Schrittdialog stand „=@breite“,
        und wer dort eine Zahl tippte, trennte still die Bindung. Ein
        abgeleitetes Maß hat kein Zahlenfeld; dort führt der Fokus auf den
        Knopf zu seinem Ausdruck.
        """
        target: QWidget | None = self._editors.get(name) or self._detail_buttons.get(name)
        if target is None:
            return False
        open_section(self)
        self._scroll.ensureWidgetVisible(target)
        target.setFocus(Qt.FocusReason.OtherFocusReason)
        editor = self._editors.get(name)
        if editor is not None:
            editor.selectAll()
        return True

    @staticmethod
    def _bounds(document: Document, name: str) -> tuple[float, float]:
        """Die wirksamen Grenzen einer Zeile: die eigenen und die der Felder, die sie lesen.

        Ohne eigene Grenzen fiel *Breite* auf ±100 000 zurück, und 5000 lief
        durch, obwohl *Quader* höchstens 1000 mm breit wird — die Kette hielt
        an, die Ansicht stand leer (RM-354). Jetzt lehnt das Feld die Zahl ab
        und nennt die Grenze (:class:`BoundedSpin`); was über einen Ausdruck
        liest, prüft :meth:`Session.change_parameter`.
        """
        parameter = document.parameters[name]
        low, high = field_bounds(document, name)
        if parameter.minimum is not None:
            low = parameter.minimum if low is None else max(low, parameter.minimum)
        if parameter.maximum is not None:
            high = parameter.maximum if high is None else min(high, parameter.maximum)
        least = low if low is not None else -100_000.0
        most = high if high is not None else 100_000.0
        return least, max(least, most)

    @staticmethod
    def _layout_of(document: Document) -> tuple[object, ...]:
        """Was eine Zeile ausmacht: Name, Titel, Wert oder Ausdruck, Einheit, Grenzen."""
        return tuple(
            (
                name,
                str(parameter.title or name),
                bool(parameter.expression),
                str(parameter.unit or ""),
                parameter.minimum,
                parameter.maximum,
            )
            for name, parameter in document.parameters.items()
        )

    def _refresh_in_place(self, document: Document) -> bool:
        """Setzt Werte und Hinweise in die bestehenden Zeilen.

        ``False`` heißt: Die Gestalt hat sich geändert, es wird neu gebaut.
        """
        layout = self._layout_of(document)
        if not layout or layout != self._layout:
            return False
        problem: AppError | None = None
        try:
            values = expressions.resolve(document.parameters)
        except AppError as error:
            values = {}
            problem = error
        for name, parameter in document.parameters.items():
            title = f"{parameter.title or name}"
            if parameter.expression:
                label = self._derived[name]
                value = values.get(name)
                label.setText(
                    localised(f"{value:.2f}") if value is not None else tr("Ausdruck prüfen")
                )
                note = parameter.expression
                if problem is not None:
                    note += f"\n{problem}"
                label.setToolTip(note)
                label.setAccessibleDescription(note)
                row = label.parentWidget()
            else:
                editor = self._editors[name]
                self._set_limits(editor, document, name)
                if not is_close(editor.value(), parameter.value):
                    # Ohne Signal: Der Wert kommt aus dem Dokument und ist keine
                    # neue Eingabe. Eine abgelehnte Zahl darunter gilt nicht mehr.
                    with QSignalBlocker(editor):
                        editor.setValue(parameter.value)
                    editor.setMinimumWidth(least_number_width(editor))
                    self._place_slider(name, parameter.value)
                    if self._refused_name == name and self._refusal is not None:
                        self._form.removeRow(self._refusal)
                        self._refusal = None
                        self._refused_name = ""
                row = editor.parentWidget()
            if row is not None:
                self._show_usage(name, title, row)
        self._fit()
        return True

    def _rebuild(self, document: Document) -> None:
        """Alle Zeilen neu — wenn Maße dazukommen, gehen oder ihre Gestalt ändern."""
        while self._form.rowCount():
            self._form.removeRow(0)
        self._editors.clear()
        self._unit_editors.clear()
        self._detail_buttons.clear()
        self._derived.clear()
        self._titles.clear()
        self._hints.clear()
        self._sliders.clear()
        self._layout = self._layout_of(document)
        # Die Zeile der Ablehnung geht mit den Zeilen (``removeRow``); der neue
        # Stand kennt keine abgelehnte Zahl mehr.
        self._refusal = None
        self._refused_name = ""
        # **Vor dem Neuaufbau leeren, nicht danach.** ``removeRow`` löscht die
        # Widgets der alten Zeilen; ein Eintrag, der auf ein totes C++-Objekt
        # zeigt, beantwortet den nächsten Rechtsklick mit einem Absturz.
        self._rows.clear()

        if not document.parameters:
            self._empty = QLabel(_empty_parameters_text(), self)
            self._empty.setWordWrap(True)
            fit_wrapped(self._empty)
            self._form.addRow(self._empty)
            self._fit()
            return

        problem: AppError | None = None
        try:
            values = expressions.resolve(document.parameters)
        except AppError as error:
            values = {}
            problem = error
        for name, parameter in document.parameters.items():
            unit = self._unit_editor(name, str(parameter.unit or ""))
            if parameter.expression:
                # Abgeleitete Werte werden gezeigt, nicht bearbeitet — der Ausdruck
                # besitzt sie.
                value = values.get(name)
                label = QLabel(
                    localised(f"{value:.2f}") if value is not None else tr("Ausdruck prüfen"), self
                )
                note = parameter.expression
                if problem is not None:
                    note += f"\n{problem}"
                label.setToolTip(note)
                label.setAccessibleDescription(note)
                # Wie die Spinbox darf auch die reine Anzeige in der festen
                # linken Karte den Restplatz nutzen. Ohne ``Ignored`` machte
                # allein „42,00“ die Karte breiter als ihre vorgesehenen
                # 260 Pixel, obwohl die echte Schrift dort bequem hineinpasst.
                label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
                self._derived[name] = label
                self._add_parameter_row(name, f"{parameter.title or name}", label, unit)
                # Auch die abgeleitete Zeile: Ihr Ausdruck ist genau das, was
                # man an ihr ändern will, und bearbeiten lässt sie sich sonst
                # nirgends.
                continue
            # **Abgelehnt, nicht gekürzt** (:class:`BoundedSpin`): Mit
            # Obergrenze 100 wurde aus getipptem „150“ still 15 — die Null
            # verfiel, die Eingabetaste übernahm den Rest (Durchsicht 0.5.1).
            editor = BoundedSpin(self)
            wheel_needs_focus(editor)
            editor.setDecimals(2)
            self._set_limits(editor, document, name)
            editor.setValue(parameter.value)
            editor.setKeyboardTracking(False)
            # Der Wertebereich bestimmt sonst die Mindestbreite der Spinbox:
            # ±100 000 verlangt 156 Pixel, obwohl die aktuelle Zahl kurz ist.
            # In der festen linken Karte darf das Feld schrumpfen und nutzt den
            # Platz, der nach Einheit und Mehr-Knopf übrig bleibt.
            editor.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            # **Aber nicht unter den eigenen Wert** (Robert, 30.08.2026: „die
            # eingabefelder sind jetzt manchmal zu klein"). ``Ignored`` hält
            # den Wertebereich aus der Breite heraus — und ließ das Feld
            # zugleich unter das Maß schrumpfen, das seine **aktuelle** Zahl
            # zeigt: gemessen 92 Punkte, wo „1234,56" mit den zwei Knöpfen 118
            # braucht. Auf dem Bildschirm stand „2,4" statt „2,40", und Qt
            # schneidet dabei stumm.
            editor.setMinimumWidth(least_number_width(editor))
            editor.valueChanged.connect(
                lambda value, key=name: self._queue_parameter_edit(key, value)
            )
            editor.valueRefused.connect(lambda _number, key=name: self._show_refusal(key))
            editor.lineEdit().textEdited.connect(lambda _text, key=name: self._show_refusal(key))
            self._editors[name] = editor
            self._add_parameter_row(name, f"{parameter.title or name}", editor, unit)
            slider = self._slider_for(name, f"{parameter.title or name}", parameter)
            if slider is not None:
                self._form.addRow(slider)
        self._fit()

    def _slider_for(self, name: str, title: str, parameter: Parameter) -> QSlider | None:
        """Ein Regler für ein Maß mit eigener Unter- und Obergrenze (§13, RM-359 F8).

        Nur dann: Ohne beide Grenzen gibt es keine Strecke, über die er führt.
        **Und nur für einen Arbeitsbereich**: Benannte Maße erben die Grenzen
        ihres Feldes (0,1 bis 1000 mm), und ein Regler, der ein 40-mm-Maß mit
        jedem Bildpunkt um mehr als einen Millimeter verschiebt, ist keiner. Ab
        :data:`SLIDER_SPAN` mal dem Wert fehlt er; wer einen Bereich wie 30 bis
        80 setzt, bekommt ihn.
        **Ein Zug ist ein Schritt**: Während des Ziehens zeigt das Feld die Zahl,
        übernommen wird beim Loslassen — eine Transaktion, ein Strg+Z. Pfeiltasten
        und ein Klick neben den Griff ändern je einmal.
        """
        low, high = parameter.minimum, parameter.maximum
        if low is None or high is None or not high > low:
            return None
        if high - low > SLIDER_SPAN * max(abs(parameter.value), 1.0):
            return None
        slider = QSlider(Qt.Orientation.Horizontal, self._sheet)
        slider.setRange(0, SLIDER_STEPS)
        slider.setPageStep(SLIDER_STEPS // 10)
        slider.setAccessibleName(tr("{name} als Regler", name=title))
        slider.setToolTip(
            tr("Von {low} bis {high}", low=localised(f"{low:g}"), high=localised(f"{high:g}"))
        )
        wheel_needs_focus(slider)
        self._sliders[name] = slider
        self._place_slider(name, parameter.value)
        slider.sliderMoved.connect(lambda position, key=name: self._slider_moved(key, position))
        slider.sliderReleased.connect(lambda key=name: self._slider_released(key))
        slider.valueChanged.connect(lambda position, key=name: self._slider_stepped(key, position))
        return slider

    def _slider_value(self, name: str, position: int) -> float:
        """Die Zahl an einer Stelle des Reglers, gerundet wie das Feld sie zeigt."""
        low, high = self._slider_range(name)
        value = low + (high - low) * position / SLIDER_STEPS
        editor = self._editors.get(name)
        return round(value, editor.decimals() if editor is not None else 2)

    def _slider_range(self, name: str) -> tuple[float, float]:
        document = self._document
        parameter = document.parameters.get(name) if document is not None else None
        if parameter is None or parameter.minimum is None or parameter.maximum is None:
            return 0.0, 1.0
        return float(parameter.minimum), float(parameter.maximum)

    def _place_slider(self, name: str, value: float) -> None:
        """Setzt den Griff auf eine Zahl, ohne dass das eine Änderung wäre."""
        slider = self._sliders.get(name)
        if slider is None or slider.isSliderDown():
            return
        low, high = self._slider_range(name)
        share = 0.0 if high <= low else (value - low) / (high - low)
        with QSignalBlocker(slider):
            slider.setValue(round(min(max(share, 0.0), 1.0) * SLIDER_STEPS))

    def _slider_moved(self, name: str, position: int) -> None:
        """Während des Ziehens zeigt das Feld die Zahl — übernommen wird beim Loslassen."""
        editor = self._editors.get(name)
        if editor is not None:
            with QSignalBlocker(editor):
                editor.setValue(self._slider_value(name, position))

    def _slider_released(self, name: str) -> None:
        slider = self._sliders.get(name)
        if slider is not None:
            self._queue_parameter_edit(name, self._slider_value(name, slider.value()))

    def _slider_stepped(self, name: str, position: int) -> None:
        """Pfeiltaste oder Klick neben den Griff: je Schritt eine Änderung."""
        slider = self._sliders.get(name)
        if slider is None or slider.isSliderDown():
            return
        value = self._slider_value(name, position)
        editor = self._editors.get(name)
        if editor is not None:
            with QSignalBlocker(editor):
                editor.setValue(value)
        self._queue_parameter_edit(name, value)


#: Wie fein der Regler einer Parameterzeile teilt (§13, RM-359 F8).
SLIDER_STEPS: Final = 1000
#: Bis zu welchem Vielfachen seines Werts ein Bereich noch ein Arbeitsbereich ist.
SLIDER_SPAN: Final = 20.0


#: Datenrolle der Einfügemarke im Verlauf (P7.1): Die Zeile trägt keinen
#: Schritt, ein Doppelklick beendet das Einfügen.
MARKER_ROLE = int(Qt.ItemDataRole.UserRole) + 3


def history_step_titles(document: Document) -> dict[int, str]:
    """Benutzertitel folgen ausschließlich gespeicherter Herkunft durch jeden Umbau.

    Die Quelle ist ``history.step_titles``; Löschnachfrage und Löschtitel
    lesen dieselbe, damit sie den Schritt so nennen wie seine Zeile hier.
    """
    return {op_id: str(title) for op_id, title in step_titles(document).items()}


def replanned_steps(document: Document) -> frozenset[int]:
    """Schritte, die ein Einfügen oder Verschieben neu gefasst hat (P7).

    Ihre alten Zeilen sind nicht gelöscht: Derselbe Schritt steht unter neuer
    Kennung an seiner neuen Stelle. Der Verlauf blendet sie deshalb aus, statt
    sie wie ein gelöschter Schritt durchzustreichen (§15.4 gilt dem Löschen).
    """
    found: set[int] = set()
    for transaction in document.transactions:
        changes = transaction.changes
        if transaction.revision not in ("insert", "move") or changes is None:
            continue
        found.update(
            op_id for op_id, version in (changes.after.edited_ops or {}).items() if version is None
        )
    return frozenset(found)


def step_state(document: Document, op_id: int) -> str:
    """Ob ein Schritt rechnet — leer, „aus" oder „ruht" (P7.3), als Wort und nicht als Farbe."""
    entry = next((operation for operation in document.ops if operation.id == op_id), None)
    if entry is None or entry.suppressed is None:
        return ""
    return tr("aus") if entry.suppressed.chosen else tr("ruht")


def needs_tip(op_id: int, needs: Sequence[StepNeed], document: Document | None = None) -> str:
    """Was ein Schritt braucht und wer ihn braucht — die abhängige Folge in Worten (P7.2)."""
    wanted = sorted({step_number(document, need.on) for need in needs if need.step == op_id})
    users = sorted({step_number(document, need.step) for need in needs if need.on == op_id})
    lines: list[str] = []
    if wanted:
        lines.append(tr("Braucht Schritt {numbers}.").format(numbers=", ".join(map(str, wanted))))
    if users:
        lines.append(
            tr("Schritt {numbers} braucht diesen.").format(numbers=", ".join(map(str, users)))
        )
    return "\n".join(lines)


def drop_before(row_ops: Sequence[tuple[int, ...]], row: int) -> int | None:
    """Vor welchen Schritt eine Ablage vor Zeile ``row`` fällt — ``None`` heißt: ans Ende.

    Zeilen ohne Schritt (Protokollzeilen, Zurückgenommenes, die Einfügemarke)
    zählen nicht; es gilt der nächste Schritt darunter.
    """
    for ops in row_ops[max(row, 0) :]:
        if ops:
            return ops[0]
    return None


class _HistoryList(QListWidget):
    """Die Verlaufsliste, an der sich Schritte ziehen lassen (P7.2).

    Qt verschöbe beim Ablegen die Zeilen selbst. Der Verlauf ist aber das
    Dokument, und das ändert nur die Sitzung — geplant, isoliert gerechnet,
    als eine Transaktion. Die Liste sagt deshalb nur, wohin gezogen wurde, und
    zeigt schon beim Ziehen, welche Stellen gehen: Eine ungültige bekommt
    keinen Einfügestrich, und ihr Grund steht in der Statuszeile.
    """

    dropped = Signal(object, object)
    """Die gezogenen Schritte und der Schritt, vor den sie sollen (``None``: ans Ende)."""
    refused = Signal(str)
    """Warum die Stelle unter dem Zeiger nicht geht."""
    markerActivated = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.dragged: Callable[[], tuple[int, ...]] = lambda: ()
        self.places: Callable[[tuple[int, ...]], Mapping[int | None, str | None]] | None = None
        self._moving: tuple[int, ...] = ()
        self._targets: Mapping[int | None, str | None] = {}
        self._said = ""

    def row_ops(self) -> list[tuple[int, ...]]:
        """Je Zeile die Schritte, die sie trägt — sichtbar oder nicht."""
        found: list[tuple[int, ...]] = []
        for row in range(self.count()):
            item = self.item(row)
            found.append(tuple(item.data(OPS_ROLE) or ()) if not item.isHidden() else ())
        return found

    def startDrag(self, supportedActions: Qt.DropAction) -> None:  # noqa: N802, N803 - Qt
        self._moving = self.dragged()
        if not self._moving or self.places is None:
            return
        self._targets = dict(self.places(self._moving))
        self._said = ""
        super().startDrag(supportedActions)
        self._moving = ()
        self._targets = {}

    def _target_of(self, event: QDragMoveEvent | QDropEvent) -> tuple[bool, int | None]:
        """Die Stelle unter dem Zeiger: ob es eine gibt, und vor welchen Schritt."""
        position = event.position().toPoint()
        index = self.indexAt(position)
        if not index.isValid():
            return True, None
        rect = self.visualRect(index)
        row = index.row() + (1 if position.y() > rect.center().y() else 0)
        return True, drop_before(self.row_ops(), row)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt
        if event.source() is self and self._moving:
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802 - Qt
        if event.source() is not self or not self._moving:
            event.ignore()
            return
        _found, before = self._target_of(event)
        if before not in self._targets:
            # Hier bewegte sich nichts: kein Strich, und kein Satz.
            self.setDropIndicatorShown(False)
            super().dragMoveEvent(event)
            event.ignore()
            return
        problem = self._targets[before]
        self.setDropIndicatorShown(problem is None)
        super().dragMoveEvent(event)
        if problem is None:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            self._said = ""
            return
        event.ignore()
        if problem != self._said:
            self._said = problem
            self.refused.emit(problem)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt
        # **Kein ``super()``**: Qt legte sonst eine Kopie der Zeilen ab. Und
        # ``CopyAction`` statt ``MoveAction``, damit Qt die gezogenen Zeilen
        # nicht selbst entfernt — das tut der Neuaufbau nach dem Umbau.
        moving = self._moving
        _found, before = self._target_of(event)
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self.setDropIndicatorShown(True)
        if moving and before in self._targets and self._targets[before] is None:
            self.dropped.emit(moving, before)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt
        item = self.itemAt(event.position().toPoint())
        if item is not None and item.data(MARKER_ROLE):
            self.markerActivated.emit()
            return
        super().mouseDoubleClickEvent(event)


class HistoryPanel(QWidget):
    """Transaktionen, neueste zuletzt. Die Einheit des Undo (§15.5).

    Eine Transaktion ist eine Zeile, denn das ist es, was ein Undo
    zurücknimmt. Ihre Operationen bekommen eine eigene Zeile, wo es mehr als
    eine gibt — ein Agentenvorschlag, eine Teilung in vier —, damit sich jeder
    Schritt des Stapels öffnen und korrigieren lässt, nicht nur die, die allein
    kamen (§15.4).
    """

    operationActivated = Signal(int)
    """Eine Operation wurde doppelt angeklickt — trägt ihre ID, zum Ändern (§15.4)."""
    previewRequested = Signal(int)
    previewClosed = Signal()
    previewInsertRequested = Signal(object)
    noteRequested = Signal(str)
    """Was der Verlauf dem Nutzer zu sagen hat — das Fenster zeigt es an.

    Bisher nur für den Doppelklick, der nichts öffnen kann. Als Signal und
    nicht als eigene Zeile im Panel: Die Statuszeile ist der Ort für eine
    Auskunft, die eine Handlung begleitet, und der Verlauf hat keine."""
    removalRequested = Signal(object)
    """Die gewählten Operationen sollen nach einer Nachfrage gelöscht werden."""
    bakeRequested = Signal(int)
    """Der Stand einer Formsitzung soll festgeschrieben werden (Entscheidung D).

    Als Signal und nicht als Aufruf: Die Nachfrage stellt das Fenster, denn sie
    ist die einzige im ganzen Programm — die Handlung ist nicht folgenlos
    rücknehmbar, und Regel 19 gilt nur für die, die es sind."""
    kernelSwitchRequested = Signal(int)
    """Dieser Grundkörperschritt soll im anderen Rechenkern rechnen (P2.8,
    ``History.change_kernel``) — rücknehmbar, also ohne Nachfrage."""
    drawingReuseRequested = Signal(int)
    """Die Zeichnung dieses Schritts soll als Kopie für einen **neuen** Schritt
    geöffnet werden (Bedienabnahme Zeichnen E6, Entscheidung Robert
    23.09.2026). Der alte Schritt bleibt, wie er ist."""
    insertRequested = Signal(int)
    """Neue Schritte sollen vor diesen kommen (P7.1) — die Einfügemarke."""
    stopInsertRequested = Signal()
    """Die Einfügemarke soll weg; die Oberfläche zeigt wieder den Endstand."""
    moveRequested = Signal(object, object)
    """Diese Schritte vor jenen (``None``: ans Ende) — rücknehmbar, ohne Nachfrage (P7.2)."""
    suppressRequested = Signal(object)
    """Diese Schritte ausschalten (P7.3) — rücknehmbar, ohne Nachfrage."""
    reactivateRequested = Signal(object)
    """Diese Schritte wieder einschalten (P7.3)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._open_groups: set[str] = set()
        """Die Transaktionen, deren Teilschritte gerade offen stehen.

        Gemerkt über den Neuaufbau hinweg: ``show_document`` läuft nach jeder
        Änderung, und ein Verlauf, der bei jedem Schritt wieder zuklappt,
        nähme dem Kunden gerade das, was er sich eben aufgemacht hat.
        """
        self.list = _HistoryList(self)
        self.list.setAccessibleName(tr("Verlauf"))
        # **Das kleinste Symbol, das die Zeile nicht weiter treibt.** Ein
        # Symbol kostet zwei Punkte Zeilenhöhe, gleich wie klein es ist —
        # gemessen 38 ohne, 40 mit, und darunter ändert sich nichts mehr (bei
        # 18 sind es 42, bei 24 schon 48). Die zwei Punkte sind bezahlt: Die
        # linke Spalte ist ohnehin überfüllt (ihr Inhalt will 901 Punkte bei
        # 622 bis 819 verfügbaren), acht Verlaufszeilen machen daraus 917.
        # Das ist eine bewusste Abwägung und keine kostenlose Verbesserung —
        # die Überfüllung selbst ist ein eigener Befund.
        self.list.setIconSize(QSize(NORMAL * 2, NORMAL * 2))
        # **Mehrere Schritte wählbar** (§24.5): Ein Rezept nimmt beliebige
        # ``op_ids``, und solange der Verlauf nur einen Index kannte, wanderte
        # der ganze Stapel in jeden Baustein — wer einen Halter aus einem
        # gewachsenen Projekt herauslöst, bekam ein Teil, das Dinge baut, die
        # niemand bestellt hat. Dieselbe Auswahlart wie im Objektbaum daneben,
        # damit Strg- und Umschalt-Klick überall dasselbe tun.
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemDoubleClicked.connect(self._on_activated)
        # **Ein einfacher Klick klappt um, ein Doppelklick öffnet den Schritt.**
        # Beides am selben Element wäre eine Falle; hier ist es keine, denn ein
        # Oberpunkt mit mehreren Schritten hat gar keine ``UserRole`` und
        # öffnet deshalb ohnehin nichts (siehe :meth:`point_at`).
        self.list.itemClicked.connect(self._toggle_group)
        self.list.setToolTip(
            tr(
                "Doppelklick öffnet einen Schritt. Ziehen verschiebt ihn, "
                "Leertaste schaltet ihn aus und ein."
            )
        )
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
        self.remove_action = QAction(tr("Schritt löschen …"), self.list)
        self.remove_action.setShortcut(QKeySequence("Del"))
        self.remove_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.remove_action.triggered.connect(self._request_selected_removal)
        self.list.addAction(self.remove_action)
        # **Die Tastatur kann alles, was die Maus kann** (P7): davor einfügen,
        # schrittweise verschieben, aus- und einschalten. Am Verlauf und
        # nur dort — dieselbe Begrenzung wie bei Entf. Escape verteilt das
        # Hauptfenster: eine zweite Belegung hier blockierte beide Wege.
        self.insert_action = self._list_action(tr("Davor einfügen"), "Ins", self._request_insert)
        self.up_action = self._list_action(
            tr("Nach oben", context="Verlauf"), "Alt+Up", self._request_up
        )
        self.down_action = self._list_action(
            tr("Nach unten", context="Verlauf"), "Alt+Down", self._request_down
        )
        self.toggle_action = self._list_action(tr("Aus- oder einschalten"), "Space", self._toggle)
        self.stop_insert_action = self._list_action(
            tr("Einfügen beenden"), "", self.stopInsertRequested.emit
        )
        self.list.dragged = self.selected_operations
        self.list.dropped.connect(self.moveRequested.emit)
        self.list.refused.connect(self.noteRequested.emit)
        self.list.markerActivated.connect(self.stopInsertRequested.emit)
        self.revision_context: Callable[[], tuple[int | None, Sequence[StepNeed]]] | None = None
        """Einfügemarke und abhängige Folge, von der Sitzung gelesen (P7) —
        vom Fenster gesetzt; ohne es zeigt der Verlauf beides nicht."""
        self._order: tuple[int, ...] = ()
        """Die Schritte des Stapels in ihrer Folge — für Nach oben und Nach unten."""
        self._resting: dict[int, bool] = {}
        """Je ausgeschaltetem Schritt, ob er gewählt ist (``True``) oder mitruht."""
        self._inserting: int | None = None
        self._room: int | None = None
        """Wie beim Objektbaum: die zugeteilte Höhe, ``None`` bis sie kommt."""
        self._bakeable: frozenset[int] = frozenset()
        """Formsitzungen, deren Stand sich festschreiben lässt — also die, die
        noch aus ihren Zügen gerechnet werden."""
        self._switchable: dict[int, str] = {}
        """Grundkörperschritte, die in den anderen Rechenkern können, mit dem Satz dafür."""
        self._drawn: frozenset[int] = frozenset()
        """Schritte mit einer gezeichneten Skizze — dort steht „Zeichnung weiterverwenden"."""
        # Wie beim Objektbaum: ein Satz statt eines stummen Kastens.
        self._empty = QLabel(_empty_history_text(), self)
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._empty.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        fit_wrapped(self._empty)

        self.compare = QToolButton(self)
        self.compare.setText(tr("Vorher/Nachher"))
        self.compare.setCheckable(True)
        self.compare.setAccessibleName(self.compare.text())
        self.preview_allowed: Callable[[], bool] | None = None
        self.timeline = QWidget(self)
        timeline_layout = QVBoxLayout(self.timeline)
        timeline_layout.setContentsMargins(NORMAL, 0, NORMAL, TIGHT)
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal, self.timeline)
        self.timeline_slider.setAccessibleName(tr("Stand im Verlauf"))
        self.timeline_slider.setSingleStep(1)
        self.timeline_slider.setPageStep(1)
        self.timeline_slider.setTickInterval(1)
        self.timeline_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.timeline_label = QLabel(self.timeline)
        self.timeline_label.setWordWrap(True)
        self.timeline_label.setTextFormat(Qt.TextFormat.PlainText)
        self.timeline_insert = QPushButton(tr("Hier weiterarbeiten"), self.timeline)
        self.timeline_end = QPushButton(tr("Aktueller Stand"), self.timeline)
        self._timeline_titles: list[str] = []
        self._timeline_targets: list[int | None] = []
        timeline_layout.addWidget(self.timeline_slider)
        timeline_layout.addWidget(self.timeline_label)
        timeline_layout.addWidget(self.timeline_insert)
        timeline_layout.addWidget(self.timeline_end)
        self.timeline.setVisible(False)
        self.compare.toggled.connect(self._toggle_timeline)
        self.timeline_slider.valueChanged.connect(self._timeline_changed)
        self.timeline_end.clicked.connect(lambda: self.compare.setChecked(False))
        self.timeline_insert.clicked.connect(self._insert_at_preview)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.compare)
        layout.addWidget(self.timeline)
        layout.addWidget(self._empty)
        layout.addWidget(self.list)

    def _toggle_timeline(self, checked: bool) -> None:
        if checked and self.preview_allowed is not None and not self.preview_allowed():
            with QSignalBlocker(self.compare):
                self.compare.setChecked(False)
            return
        self.timeline.setVisible(checked)
        if checked:
            self._timeline_changed(self.timeline_slider.value())
            self.timeline_slider.setFocus()
        else:
            self.previewClosed.emit()
        self._fit()

    def _timeline_changed(self, count: int) -> None:
        if not self.compare.isChecked() or not 1 <= count <= len(self._timeline_titles):
            return
        self.timeline_label.setText(
            tr("Stand {number} von {count}: {title}").format(
                number=count,
                count=len(self._timeline_titles),
                title=self._timeline_titles[count - 1],
            )
        )
        self.previewRequested.emit(count)

    def _insert_at_preview(self) -> None:
        count = self.timeline_slider.value()
        if 1 <= count <= len(self._timeline_targets):
            target = self._timeline_targets[count - 1]
            self.compare.setChecked(False)
            self.previewInsertRequested.emit(target)

    def _timeline_height(self) -> int:
        if self.compare.isHidden():
            return 0
        return self.compare.sizeHint().height() + (
            self.timeline.sizeHint().height() if self.compare.isChecked() else 0
        )

    def wanted_height(self) -> int:
        """Die Höhe, bei der jeder Schritt zu sehen wäre."""
        return (
            self._timeline_height()
            + view_chrome(self.list)
            + self.list.count() * row_height_of(self.list)
        )

    def least_height(self) -> int:
        """Und die, unter die diese Karte nicht geht (siehe ``fit_to_rows``).

        Der leere Verlauf ist der Fall, an dem es auffiel: ``wanted_height``
        meldete vier Pixel, der Boden gab hundertzwölf, und die Überlagerung
        verteilte nach den vier.
        """
        if self.list.count() == 0:
            return least_empty_height(self._empty)
        return self._timeline_height() + least_height_of(self.list)

    def set_room(self, pixels: int) -> None:
        """Wie hoch diese Karte werden darf (siehe ``fit_to_rows``)."""
        if pixels == self._room:
            return
        self._room = pixels
        self._fit()

    def _fit(self) -> None:
        """So hoch wie der Inhalt, höchstens so hoch wie zugeteilt."""
        empty = self.list.count() == 0
        self._empty.setVisible(empty)
        self.list.setVisible(not empty)
        room = None if self._room is None else max(0, self._room - self._timeline_height())
        fit_to_rows(self.list, self.list.count(), room=room)
        # Dieselbe Stelle wie im Objektbaum: die Liste ist bemessen, die Karte
        # um sie herum meldete weiter ihre Mindesthöhe und wurde auf zehn Pixel
        # gedrückt.
        self.setMinimumHeight(self.sizeHint().height())
        self.updateGeometry()

    def show_document(
        self,
        document: Document,
        stopped_at: int | None = None,
        undone: Sequence[Any] = (),
    ) -> None:
        """Der Verlauf, und was ein Redo zurückholen würde.

        Zurückgenommene Transaktionen verschwanden hier spurlos: der Verlauf
        endete beim aktuellen Stand, und ob es noch etwas wiederherzustellen
        gab, verriet nur der Zustand des Menüeintrags. Sie stehen jetzt unten,
        durchgestrichen und ausgegraut — wie ein verworfener Chatbeitrag, und
        aus demselben Grund: es ist passiert, es gilt nur gerade nicht (§26.3).
        """
        self.compare.setChecked(False)
        self.list.clear()
        self._timeline_titles = [str(entry.title) for entry in document.transactions]
        existing = {entry.id for entry in document.ops}
        self._timeline_targets = [
            next(
                (
                    op
                    for later in document.transactions[index + 1 :]
                    for op in later.ops
                    if op in existing
                ),
                None,
            )
            for index in range(len(document.transactions))
        ]
        with QSignalBlocker(self.timeline_slider):
            self.timeline_slider.setRange(1, max(1, len(document.transactions)))
            self.timeline_slider.setValue(max(1, len(document.transactions)))
        self.compare.setEnabled(bool(document.transactions))
        self.compare.setVisible(bool(document.transactions))
        inserting, needs = (
            self.revision_context() if self.revision_context is not None else (None, ())
        )
        self._inserting = inserting
        self._order = tuple(entry.id for entry in sorted(document.ops, key=lambda one: one.id))
        self._resting = {
            entry.id: entry.suppressed.chosen
            for entry in document.ops
            if entry.suppressed is not None
        }
        self.stop_insert_action.setEnabled(inserting is not None)
        titles = history_step_titles(document)
        self._positions = {entry.id: index for index, entry in enumerate(document.ops, start=1)}
        replanned = replanned_steps(document)
        deleted: set[int] = set()
        for transaction in document.transactions:
            changes = transaction.changes
            if changes is None or changes.after.edited_ops is None:
                continue
            before = changes.before.edited_ops or {}
            for op_id, version in changes.after.edited_ops.items():
                if version is not None:
                    continue
                deleted.add(op_id)
                previous = before.get(op_id)
                if previous is not None:
                    titles.setdefault(op_id, _op_title(previous.op))
        deleted_ids = frozenset(deleted - replanned)
        self._bakeable = frozenset(
            entry.id
            for entry in document.ops
            if entry.op == "sculpt_strokes" and not entry.params.get("baked")
        )
        # **Der Kernwechsel steht am Schritt, nicht als Haken im Dialog** (P2.8):
        # Nur ein Schritt mit Zwilling bekommt den Eintrag, und der Satz nennt,
        # was er bringt — nie den Rechenkern.
        self._switchable = {
            entry.id: str(label)
            for entry in document.ops
            if kernel_twin_of(entry.op) is not None
            and (label := kernel_switch_label(entry.op)) is not None
        }
        self._drawn = frozenset(
            entry.id for entry in document.ops if str(entry.params.get("sketch", "") or "").strip()
        )
        for transaction in document.transactions:
            if transaction.ops and all(op_id in replanned for op_id in transaction.ops):
                # Neu gefasst, nicht gelöscht (P7): Derselbe Schritt steht unter
                # neuer Kennung beim Umbau, der ihn eingereiht hat.
                continue
            if transaction.revision in ("insert", "move"):
                self._add_revision_rows(transaction, document, titles, replanned, needs)
                continue
            # Nur was abweicht, wird ausgeschrieben (§26.4). „(Nutzer)" stand
            # vorher an jeder Zeile — in einem Projekt ohne Agenten also
            # überall, und was überall steht, liest niemand mehr. Dieselbe
            # Überlegung wie beim Material im Steckbrief: genannt wird, was
            # nicht die Regel ist.
            by = f"  ({tr('Agent')})" if transaction.origin.by == "agent" else ""
            # **Die Nummer steht an jeder Zeile, die genau einen Schritt
            # vertritt** — bisher trugen sie nur die Kinder einer
            # mehrschrittigen Transaktion, und damit war sie eine Auszeichnung
            # ohne Regel: „3" und „4" standen eingerückt unter „Kabel und
            # Befestigung", während „Aushöhlen" darüber keine hatte, obwohl
            # auch das genau ein Schritt ist. Sie ist keine Zierde: Der
            # Fehlerdialog nennt „Operation: 4", und der Titel eines geöffneten
            # Schritts lautet „Bohrung setzen — Operation 4". Wer von dort
            # zurück in den Verlauf sieht, sucht diese Zahl.
            #
            # Eine Transaktion aus mehreren Schritten bekommt keine: Sie
            # *vertritt* keinen einzelnen, und ihre Kinder tragen ihre eigenen.
            single = transaction.ops[0] if len(transaction.ops) == 1 else None
            # Ein gelöschter Schritt hat keine Stelle mehr — seine Kennung
            # stünde sonst als Nummer neben den Stellen der übrigen (RM-368).
            number = (
                f"{self._positions[single]}  "
                if single is not None and single in self._positions
                else ""
            )
            item = QListWidgetItem(f"{number}{transaction.title}{by}")
            halted = stopped_at is not None and stopped_at in transaction.ops
            if halted:
                # §15.3: die betroffenen Operationen werden im Verlauf markiert.
                item.setText(f"! {item.text()}")
            # **Schritte, nicht „Ops".** Die Kurzhilfe sagte „t3 · Ops 4, 5" —
            # ein Wort aus dem Code, und das Ausrufezeichen davor erklärte sie
            # nicht (22.09.2026). Die Kennung bleibt vorn: Mit ihr nennt die
            # Übernommen-Leiste des Chats denselben Schritt.
            steps = (
                tr("Schritt {number}").format(number=step_number(document, transaction.ops[0]))
                if len(transaction.ops) == 1
                else tr("Schritte {numbers}").format(
                    numbers=", ".join(
                        str(step_number(document, entry)) for entry in transaction.ops
                    )
                )
                if transaction.ops
                # **Eine Änderung am Projekt vertritt keinen Schritt** — dort
                # stand „t2 · Schritte “ mit leerer Liste. Sie sagt, was sich
                # änderte (:func:`_changed_parameters`), sonst nur die Kennung.
                else _changed_parameters(transaction)
            )
            tip = f"{transaction.id} · {steps}" if steps else str(transaction.id)
            if halted:
                tip += "\n" + tr("Hier hält die Kette an — der Grund steht im Prüfbericht.")
            item.setToolTip(tip)
            # **Ein Symbol je Zeile, aus derselben Quelle wie im Menü.** Der
            # Verlauf war eine reine Textspalte, während siebzehn
            # Kategoriesymbole in ``icons.py`` bereitlagen — wer seine Arbeit
            # daran entlangliest, sucht „das mit der Bohrung" und findet
            # sechzehn gleich aussehende Zeilen. Eine Transaktion aus mehreren
            # Schritten nimmt das Symbol ihres **ersten**: Sie heißt nach dem,
            # was sie tut, und das beginnt dort.
            first_op = next(
                (entry.op for entry in document.ops if entry.id in set(transaction.ops)), ""
            )
            symbol = _op_icon_name(first_op) if first_op else ""
            if symbol:
                item.setIcon(icon(symbol, self.list))
            # Neu gefasste Schritte stehen beim Umbau, nicht hier (P7) — eine
            # Auswahl dieser Zeile nennt sie nicht mit.
            active_ops = tuple(
                op_id
                for op_id in transaction.ops
                if op_id not in deleted_ids and op_id not in replanned
            )
            if transaction.ops and not active_ops:
                item.setText(f"{item.text()}  ({tr('gelöscht')})")
                font = QFont(item.font())
                font.setStrikeOut(True)
                item.setFont(font)
                item.setForeground(QColor(UNDONE_COLOUR))
            if len(transaction.ops) == 1 and active_ops:
                item.setData(Qt.ItemDataRole.UserRole, transaction.ops[0])
                self._mark_state(item, document, transaction.ops[0], needs)
            # **Die Zeile trägt auch, was sie umfasst.** ``UserRole`` bleibt
            # die *eine* Operation zum Öffnen — eine Transaktion aus vier
            # Schritten hat keine, und das ist richtig, denn welchen sollte ein
            # Doppelklick zeigen. Für die Mehrfachauswahl zählt dagegen die
            # ganze Transaktion: Wer „Teilung in vier" wählt, meint alle vier.
            item.setData(OPS_ROLE, active_ops)
            if len(transaction.ops) > 1:
                # **Ein Zeichen und nicht nur eine Einrückung** (Regel 18): Die
                # Kindzeilen stehen eingerückt, aber ein Bildschirmleser liest
                # keine Leerzeichen vor, und wer nicht scrollt, sieht sie gar
                # nicht. Das Dreieck sagt beides — dass es hier mehr gibt und
                # ob es gerade zu sehen ist.
                expanded = transaction.id in self._open_groups
                item.setText(f"{'▾' if expanded else '▸'}  {item.text()}")
                item.setData(GROUP_ROLE, transaction.id)
                item.setToolTip(
                    tr("{count} Schritte — anklicken zum Auf- und Zuklappen.").format(
                        count=len(transaction.ops)
                    )
                )
            self.list.addItem(item)

            if len(transaction.ops) > 1:
                for op_id in transaction.ops:
                    if op_id in replanned:
                        continue
                    # Ein gelöschter Schritt hat keine Stelle (RM-368) und steht
                    # eingerückt wie seine Geschwister, ohne Lücke für die Nummer.
                    position = self._positions.get(op_id)
                    number = f"{position}  " if position is not None else ""
                    child = QListWidgetItem(f"    {number}{titles.get(op_id, '')}")
                    child.setData(GROUP_ROLE, transaction.id)
                    child_symbol = _op_icon_name(
                        next((entry.op for entry in document.ops if entry.id == op_id), "")
                    )
                    if child_symbol:
                        child.setIcon(icon(child_symbol, self.list))
                    if op_id not in deleted_ids:
                        child.setData(Qt.ItemDataRole.UserRole, op_id)
                        child.setData(OPS_ROLE, (op_id,))
                        self._mark_state(child, document, op_id, needs)
                    else:
                        child.setText(f"{child.text()}  ({tr('gelöscht')})")
                        font = QFont(child.font())
                        font.setStrikeOut(True)
                        child.setFont(font)
                        child.setForeground(QColor(UNDONE_COLOUR))
                    self.list.addItem(child)
                    # **Verstecken erst, wenn die Zeile in der Liste steht.**
                    # ``setHidden`` an einem Element ohne Liste tut nichts und
                    # meldet auch nichts — dieselbe Familie wie „Qt lügt vor
                    # dem Anzeigen": Der Aufruf sieht aus wie getan, und die
                    # Zeile steht trotzdem da.
                    #
                    # **Vorgabe eingeklappt.** Ein Verlauf, der jeden
                    # Teilschritt zeigt, ist nach zehn Handlungen eine Wand aus
                    # Zeilen, und die eine, die man sucht, steht irgendwo darin.
                    child.setHidden(transaction.id not in self._open_groups)

        for transaction in reversed(list(undone)):
            item = QListWidgetItem(f"{transaction.title}  ({tr('zurückgenommen')})")
            font = QFont(item.font())
            font.setStrikeOut(True)
            item.setFont(font)
            item.setForeground(QColor(UNDONE_COLOUR))
            item.setToolTip(tr("Ein Wiederholen holt diesen Schritt zurück."))
            self.list.addItem(item)

        if inserting is not None:
            self._add_marker(inserting)
        self._fit()
        self.list.scrollToBottom()

    # --- Umbau des Verlaufs (P7) -----------------------------------------------------

    def _list_action(self, label: str, key: str, slot: Callable[[], object]) -> QAction:
        """Eine Handlung am Verlauf mit Kürzel, das nur hier gilt (wie Entf)."""
        action = QAction(label, self.list)
        action.setShortcut(QKeySequence(key))
        action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        action.triggered.connect(lambda _checked=False: slot())
        self.list.addAction(action)
        return action

    def _add_revision_rows(
        self,
        transaction: Any,
        document: Document,
        titles: Mapping[int, str],
        replanned: Collection[int],
        needs: Sequence[StepNeed],
    ) -> None:
        """Ein Einfügen oder Verschieben: eine Protokollzeile, darunter die Schritte (P7).

        Die neu gefassten Schritte stehen **nicht eingeklappt** unter dem
        Umbau, sondern wie eigene Zeilen: Sie sind die Folge des Stapels ab
        der ersten geänderten Stelle, in genau der Reihenfolge, in der sie
        rechnen. Die Protokollzeile trägt den Titel des Umbaus und nimmt mit
        Strg+Z alles zurück; sie selbst öffnet nichts.
        """
        by = f"  ({tr('Agent')})" if transaction.origin.by == "agent" else ""
        header = QListWidgetItem(f"{transaction.title}{by}")
        header.setForeground(QColor(UNDONE_COLOUR))
        header.setToolTip(
            tr("{id} · Strg+Z nimmt den ganzen Umbau zurück.").format(id=transaction.id)
        )
        header.setData(OPS_ROLE, ())
        self.list.addItem(header)
        for op_id in transaction.ops:
            if op_id in replanned:
                continue
            position = self._positions.get(op_id)
            if position is None:
                # **Später gelöscht:** keine Stelle, keine Kennung als Nummer,
                # durchgestrichen wie jede gelöschte Zeile (RM-368).
                row = QListWidgetItem(f"{titles.get(op_id, '')}  ({tr('gelöscht')})")
                font = QFont(row.font())
                font.setStrikeOut(True)
                row.setFont(font)
                row.setForeground(QColor(UNDONE_COLOUR))
                row.setData(OPS_ROLE, ())
                self.list.addItem(row)
                continue
            row = QListWidgetItem(f"{position}  {titles.get(op_id, '')}")
            symbol = _op_icon_name(
                next((entry.op for entry in document.ops if entry.id == op_id), "")
            )
            if symbol:
                row.setIcon(icon(symbol, self.list))
            row.setData(Qt.ItemDataRole.UserRole, op_id)
            row.setData(OPS_ROLE, (op_id,))
            row.setToolTip(
                tr("Position {position} · Schrittkennung {identifier}").format(
                    position=position, identifier=op_id
                )
            )
            self._mark_state(row, document, op_id, needs)
            self.list.addItem(row)

    def _mark_state(
        self, item: QListWidgetItem, document: Document, op_id: int, needs: Sequence[StepNeed]
    ) -> None:
        """Aus, ruhend, abhängig: in Worten an der Zeile, nie nur als Farbe (Regel 18)."""
        state = step_state(document, op_id)
        tips = [item.toolTip()] if item.toolTip() else []
        if state:
            item.setText(f"{item.text()}  ({state})")
            font = QFont(item.font())
            font.setItalic(True)
            item.setFont(font)
            item.setForeground(QColor(UNDONE_COLOUR))
            tips.append(
                tr("Ausgeschaltet: Der Schritt bleibt im Verlauf, rechnet aber nicht.")
                if self._resting.get(op_id)
                else tr("Ruht, weil er einen ausgeschalteten Schritt braucht.")
            )
        dependency = needs_tip(op_id, needs, document)
        if dependency:
            tips.append(dependency)
        if tips:
            item.setToolTip("\n".join(tips))

    def _add_marker(self, inserting: int) -> None:
        """Die Einfügemarke vor ihrem Schritt — und alles danach ruhig gestellt (P7.1)."""
        rows = self.list.row_ops()
        at = next(
            (index for index, ops in enumerate(rows) if ops and inserting in ops),
            self.list.count(),
        )
        marker = QListWidgetItem(f"▸  {tr('Neue Schritte kommen hierhin')}")
        font = QFont(marker.font())
        font.setBold(True)
        marker.setFont(font)
        marker.setData(MARKER_ROLE, True)
        marker.setData(OPS_ROLE, ())
        marker.setToolTip(tr("Doppelklick oder Esc beendet das Einfügen."))
        marker.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.list.insertItem(at, marker)
        for row in range(at + 1, self.list.count()):
            entry = self.list.item(row)
            if entry.data(OPS_ROLE):
                entry.setForeground(QColor(UNDONE_COLOUR))

    def _steps_for_action(self) -> tuple[int, ...]:
        chosen = self.selected_operations()
        if chosen:
            return chosen
        item = self.list.currentItem()
        return tuple(int(op_id) for op_id in (item.data(OPS_ROLE) or ())) if item else ()

    def _request_insert(self) -> None:
        chosen = self._steps_for_action()
        if len(chosen) >= 1:
            self.insertRequested.emit(chosen[0])

    def _neighbour_target(self, chosen: tuple[int, ...], upwards: bool) -> tuple[bool, int | None]:
        """Die Stelle einen Schritt höher oder tiefer — ob es eine gibt, und welche."""
        order = [op_id for op_id in self._order if op_id not in chosen]
        positions = [index for index, op_id in enumerate(self._order) if op_id in chosen]
        if not positions:
            return False, None
        first = self._order[positions[0]]
        last = self._order[positions[-1]]
        if upwards:
            earlier = [op_id for op_id in order if op_id < first]
            return (True, earlier[-1]) if earlier else (False, None)
        later = [op_id for op_id in order if op_id > last]
        if not later:
            return False, None
        return True, later[1] if len(later) > 1 else None

    def _request_up(self) -> None:
        self._request_neighbour(upwards=True)

    def _request_down(self) -> None:
        self._request_neighbour(upwards=False)

    def _request_neighbour(self, *, upwards: bool) -> None:
        chosen = self._steps_for_action()
        found, before = self._neighbour_target(chosen, upwards)
        if not chosen or not found:
            self.noteRequested.emit(
                tr("Höher geht es nicht.") if upwards else tr("Tiefer geht es nicht.")
            )
            return
        problem = self._target_problem(chosen, before)
        if problem:
            self.noteRequested.emit(problem)
            return
        self.moveRequested.emit(chosen, before)

    def _target_problem(self, chosen: tuple[int, ...], before: int | None) -> str | None:
        """Warum diese Stelle nicht geht — ``None``, wenn sie geht oder niemand es weiß."""
        if self.list.places is None:
            return None
        return self.list.places(chosen).get(before)

    def _toggle(self) -> None:
        """Leertaste: gewählte Schritte aus — oder, wenn alle schon aus sind, wieder an."""
        chosen = self._steps_for_action()
        if not chosen:
            return
        if all(op_id in self._resting for op_id in chosen):
            self.reactivateRequested.emit(chosen)
        else:
            self.suppressRequested.emit(
                tuple(op_id for op_id in chosen if op_id not in self._resting)
            )

    def _add_revision_entries(self, menu: QMenu, op_ids: tuple[int, ...]) -> None:
        """Einfügen, Verschieben, Aus- und Einschalten im Kontextmenü (P7)."""
        if len(op_ids) == 1:
            insert = menu.addAction(tr("Davor einfügen"))
            insert.setObjectName("history.insert")
            insert.setShortcut(self.insert_action.shortcut())
            insert.triggered.connect(
                lambda _checked=False, chosen=op_ids[0]: self.insertRequested.emit(chosen)
            )
        places = self.list.places(op_ids) if self.list.places is not None else {}
        for label, upwards, action in (
            (tr("Nach oben", context="Verlauf"), True, self.up_action),
            (tr("Nach unten", context="Verlauf"), False, self.down_action),
        ):
            entry = menu.addAction(label)
            entry.setShortcut(action.shortcut())
            found, before = self._neighbour_target(op_ids, upwards)
            problem = places.get(before) if found else None
            entry.setEnabled(found and problem is None and before in places)
            if problem:
                entry.setToolTip(problem)
            entry.triggered.connect(
                lambda _checked=False, chosen=op_ids, target=before: self.moveRequested.emit(
                    chosen, target
                )
            )
        valid = [before for before, problem in places.items() if problem is None]
        if valid:
            further = menu.addMenu(tr("Verschieben vor"))
            for before in valid:
                label = tr("Ans Ende") if before is None else f"{before}  {self._title_of(before)}"
                target = further.addAction(label)
                target.triggered.connect(
                    lambda _checked=False, chosen=op_ids, where=before: self.moveRequested.emit(
                        chosen, where
                    )
                )
        if all(op_id in self._resting for op_id in op_ids):
            switch = menu.addAction(tr("Einschalten"))
            switch.triggered.connect(
                lambda _checked=False, chosen=op_ids: self.reactivateRequested.emit(chosen)
            )
        else:
            switch = menu.addAction(tr("Ausschalten"))
            switch.setToolTip(
                tr("Der Schritt bleibt im Verlauf, rechnet aber nicht. Strg+Z nimmt es zurück.")
            )
            fresh = tuple(op_id for op_id in op_ids if op_id not in self._resting)
            switch.triggered.connect(
                lambda _checked=False, chosen=fresh: self.suppressRequested.emit(chosen)
            )
        switch.setShortcut(self.toggle_action.shortcut())
        switch.setObjectName("history.switch")
        if self._inserting is not None:
            stop = menu.addAction(tr("Einfügen beenden"))
            stop.setShortcut(self.stop_insert_action.shortcut())
            stop.triggered.connect(lambda _checked=False: self.stopInsertRequested.emit())

    def _title_of(self, op_id: int) -> str:
        """Der Titel eines Schritts, wie seine Zeile ihn nennt."""
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == op_id:
                return item.text().split("  ", 1)[-1].strip()
        return ""

    def _toggle_group(self, item: QListWidgetItem) -> None:
        """Einen Oberpunkt auf- oder zuklappen.

        Kein Bestätigungsdialog und keine Rückfrage (Regel 19): Einklappen
        nimmt nichts weg, es zeigt nur weniger, und der nächste Klick holt es
        zurück. Zeilen, die keine Gruppe sind, bleiben unberührt — dort ist
        der Klick eine Auswahl und sonst nichts.
        """
        group = item.data(GROUP_ROLE)
        if not group or item.text().startswith("    "):
            return
        if group in self._open_groups:
            self._open_groups.discard(group)
        else:
            self._open_groups.add(group)
        self._reflow_groups()

    def open_group(self, transaction_id: str) -> None:
        """Die Teilschritte dieser Transaktion offen zeigen — auch nach dem Neuaufbau.

        Für eine Handlung, deren Schritte der Kunde gleich sehen soll: Nach
        einer Erzeugung stand nur die zugeklappte Zeile „Modell erzeugen“ da,
        und was aus dem Netz wurde (Größe, Reparatur, aufs Bett), sah erst, wer
        aufklappte — in 0.5.1 standen die ersten Schritte offen (RM-456).
        """
        if transaction_id in self._open_groups:
            return
        self._open_groups.add(transaction_id)
        self._reflow_groups()

    def _reflow_groups(self) -> None:
        """Zeichen und Sichtbarkeit an den gemerkten Zustand angleichen.

        Ohne Neuaufbau des ganzen Verlaufs: Der kostet die Auswahl und die
        Rollposition, und beides braucht ein Kunde gerade dann, wenn er
        aufklappt, um etwas zu suchen.
        """
        for row in range(self.list.count()):
            entry = self.list.item(row)
            group = entry.data(GROUP_ROLE)
            if not group:
                continue
            expanded = group in self._open_groups
            if entry.text().startswith("    "):
                entry.setHidden(not expanded)
            else:
                entry.setText(("▾" if expanded else "▸") + entry.text()[1:])
        self._fit()

    def point_at(self, op_id: int) -> bool:
        """Die Zeile dieser Operation auswählen und ins Sichtfeld holen.

        **Wofür:** Ein Operationsfehler im Prüfbericht trägt keinen Ort und
        keine Merkmale — der Kern gibt ihm ``object_id`` und ``op_id``
        (``evaluate.py``, ``op.<operation>.<Ausnahme>``). Die ``op_id`` ist
        damit die einzige Auskunft über *welchen Schritt es war*, und ohne
        diese Methode blieb sie ungenutzt: Ein Klick auf den Fehler war
        folgenlos, gemessen an allen 58 Befunden der Beispielprojekte.

        **Zwei Rollen, nicht eine.** Eine Transaktion aus mehreren Schritten
        trägt bewusst **keine** ``UserRole`` — sonst müsste ein Doppelklick
        raten, welcher der vier sich öffnen soll. Ihre Operationen stehen in
        ``OPS_ROLE`` am Gruppenknoten. Wer nur die ``UserRole`` liest, zeigt
        bei jedem Sammelschritt ins Leere, und das sind gerade die
        interessanten.

        Gibt zurück, ob eine Zeile gefunden wurde: Der Aufrufer soll nicht
        behaupten müssen, etwas gezeigt zu haben.
        """
        first: QListWidgetItem | None = None
        for row in range(self.list.count()):
            # Ohne None-Wache, wie ``selected_operations`` daneben: Die Stubs
            # kennen dort keinen leeren Rückgabewert, und eine Prüfung darauf
            # hält mypy für unerreichbar.
            item = self.list.item(row)
            own = item.data(Qt.ItemDataRole.UserRole)
            if own == op_id:
                first = item
                break
            inside = item.data(OPS_ROLE) or ()
            if op_id in tuple(inside) and first is None:
                # Die Gruppenzeile merken, aber weitersuchen: Steht der
                # Schritt auch als eigene Kindzeile darunter, ist die die
                # genauere Antwort.
                first = item
        if first is None:
            return False
        # **Eine versteckte Zeile auszuwählen zeigt ins Leere.** Ein Klick auf
        # einen Befund, dessen Schritt in einem eingeklappten Oberpunkt liegt,
        # führte sonst zu einer Auswahl, die niemand sieht — die Stelle, an der
        # das Einklappen am ehesten still bricht (V6).
        group = first.data(GROUP_ROLE)
        if group and group not in self._open_groups:
            self._open_groups.add(group)
            self._reflow_groups()
        self.list.setCurrentItem(first)
        self.list.scrollToItem(first)
        return True

    def selected_operations(self) -> tuple[int, ...]:
        """Die gewählten Schritte, aufsteigend und ohne Doppelte.

        Der Ausschnitt für ein Rezept (§24.5). Eine gewählte Transaktion zählt
        mit **allen** ihren Operationen: Wer „Teilung in vier" anklickt, meint
        die vier und nicht eine davon.

        **Aufsteigend, weil ein Stapel eine Reihenfolge hat.** Angeklickt wird
        in beliebiger Folge, gerechnet wird von unten nach oben; ein Rezept aus
        „Schritt 7, dann Schritt 3" gibt es nicht.

        Leer heißt leer und nicht „alles". Was bei leerer Auswahl geschieht,
        entscheidet der Aufrufer — das Fenster nimmt dann den ganzen Stapel,
        und es schreibt das auch hin.
        """
        chosen: set[int] = set()
        for item in self.list.selectedItems():
            ops = item.data(OPS_ROLE)
            if ops:
                chosen.update(int(op_id) for op_id in ops)
        return tuple(sorted(chosen))

    def _on_activated(self, item: QListWidgetItem) -> None:
        """Doppelklick: die Operation öffnen — oder sagen, warum nicht.

        Eine Transaktion aus mehreren Operationen trägt keine ``UserRole``;
        welche der vier sollte der Doppelklick zeigen? Ihre Schritte stehen
        eingerückt darunter und tragen je eine.

        **Stumm bleiben darf er deswegen nicht.** Sechs der neun Beispieltouren
        lehren genau diese Geste als *den* Weg zum Ändern („Öffnen Sie die
        Mutternfalle mit einem Doppelklick im Verlauf"), und der Tooltip der
        Liste verspricht sie ohne Einschränkung. Eine Handlung, die nichts tut,
        sagt, was stattdessen geht (Regel 17, §2.1).
        """
        op_id = item.data(Qt.ItemDataRole.UserRole)
        if op_id is not None:
            self.operationActivated.emit(int(op_id))
            return
        if item.data(OPS_ROLE):
            self.noteRequested.emit(
                tr(
                    "Dieser Schritt fasst mehrere Operationen zusammen. "
                    "Öffnen lässt sich jede einzeln — die eingerückten Zeilen darunter."
                )
            )

    def _request_selected_removal(self) -> None:
        """Die sichtbare Auswahl zum bestätigten Löschen weiterreichen."""
        chosen = self.selected_operations()
        if chosen:
            self.removalRequested.emit(chosen)

    def _operations_for_context(self, item: QListWidgetItem | None) -> tuple[int, ...]:
        """Die sichtbare Mehrfachauswahl oder allein die rechts angeklickte Zeile."""
        clicked = tuple(item.data(OPS_ROLE) or ()) if item is not None else ()
        if item is not None and item.isSelected():
            return self.selected_operations()
        if item is not None and clicked:
            self.list.clearSelection()
            item.setSelected(True)
            self.list.setCurrentItem(item)
        return tuple(int(op_id) for op_id in clicked)

    def _on_context_menu(self, position: QPoint) -> None:
        """Was man mit einem Schritt tun kann, dort, wo er steht.

        Bisher gab es nur den Doppelklick, und den findet, wer ihn probiert.
        Angeboten wird, was der Stapel wirklich kann: einen Schritt öffnen,
        seine Zahlen ändern oder ihn samt abhängigen Schritten löschen
        (§15.4). Das Löschen bleibt eine Transaktion und damit rücknehmbar.
        """
        item = self.list.itemAt(position)
        op_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        op_ids = self._operations_for_context(item)
        if not op_ids:
            return

        menu = QMenu(self)
        # Die Objektnamen ``history.*`` sind die Adresse, unter der eine
        # Bildanleitung einen Eintrag markiert (``guide_targets``); der Text
        # steht damit nur hier.
        single_op = int(op_id) if op_id is not None and len(op_ids) == 1 else None
        if single_op is not None:
            action = menu.addAction(tr("Parameter ändern …"))
            action.setObjectName("history.edit")
            action.triggered.connect(
                lambda _checked=False, chosen=single_op: self.operationActivated.emit(chosen)
            )
        if single_op is not None and single_op in self._switchable:
            switch = menu.addAction(self._switchable[single_op])
            switch.triggered.connect(
                lambda _checked=False, chosen=single_op: self.kernelSwitchRequested.emit(chosen)
            )
        if single_op is not None and single_op in self._drawn:
            # **Eine Zeichnung für mehrere Schritte** (Befund E6): Außenkontur
            # hochziehen, Innenkontur als Tasche — ohne neu zu zeichnen. Der
            # Eintrag steht nur an Schritten, die eine Zeichnung tragen.
            reuse = menu.addAction(tr("Zeichnung weiterverwenden"))
            reuse.setToolTip(tr("Öffnet eine Kopie dieser Zeichnung für einen neuen Schritt."))
            menu.setToolTipsVisible(True)
            reuse.triggered.connect(
                lambda _checked=False, chosen=single_op: self.drawingReuseRequested.emit(chosen)
            )
        self._add_revision_entries(menu, op_ids)
        menu.setToolTipsVisible(True)
        remove = menu.addAction(tr("Schritt löschen …"))
        remove.setObjectName("history.delete")
        remove.triggered.connect(
            lambda _checked=False, chosen=op_ids: self.removalRequested.emit(chosen)
        )
        if single_op is not None and single_op in self._bakeable:
            # Nur an einer Formsitzung, und nur an einer, die noch gerechnet
            # wird: Ein Eintrag, der an jedem Schritt steht und an fast keinem
            # etwas tut, ist einer, den man nicht mehr liest.
            # Ohne Auslassungspunkte: Es folgt keine Frage mehr, und Strg+Z
            # nimmt es zurück (``MainWindow.bake_sculpt``).
            frozen = menu.addAction(tr("Stand festschreiben"))
            frozen.setToolTip(
                tr(
                    "Legt den jetzigen Stand als Körper ab. Die Züge bleiben als Beleg, "
                    "wirken aber nicht mehr — die Sitzung wird nicht mehr gerechnet."
                )
            )
            menu.setToolTipsVisible(True)
            frozen.triggered.connect(
                lambda _checked=False, chosen=single_op: self.bakeRequested.emit(chosen)
            )
        menu.exec(self.list.viewport().mapToGlobal(position))
        # Wie im Objektbaum: Das Menü gehört diesem Klick.
        menu.deleteLater()


#: Ab wie vielen Zeilen der Bericht seine Filterzeile zeigt.
#:
#: Acht (RM-508): Bis dahin überblickt man die Liste, und ein Suchfeld mit
#: Stufenwahl stand ab zwei Befunden über ihr — zwei Bedienelemente und drei
#: Wörter Gerüst, wo der Kunde die Befunde lesen wollte.
FILTER_FROM = 8

#: Wie viele Befundzeilen die Liste im knappen Fenster mindestens zeigt (RM-508).
LEAST_REPORT_ROWS: Final = 3

#: Handlungen eines Befunds, die seine Stelle zeigen — bietet er eine an,
#: entfällt der Zeige-Knopf der Befundzeile (RM-508, Durchsicht B10).
_SHOWING_ACTIONS: Final = frozenset({SHOW_LOCATION.id, SHOW_LOCATIONS.id})


class BodyChoiceDialog(QDialog):
    """Für welche Körper soll die Handlung einer Sammelzeile gelten?

    Sechs Zeilen „zu fein vernetzt" wurden zu einer (:data:`REPORT_BUNDLE_FROM`) —
    was dabei verlorenginge, ist die Wahl, welchen Körper man behandelt. Der
    Dialog gibt sie zurück, und zwar als Wahl und nicht als Frage: Alle sind
    angehakt, wer alle meint, drückt einmal (Entscheidung Robert, 03.09.2026).

    **Keine Bestätigung vor einer rücknehmbaren Handlung** (Regel 19): Er geht
    nur auf, wo es mehr als einen Körper gibt, und er fragt nicht „wirklich?",
    sondern „welche?". Der Unterschied ist der Grund, aus dem er erlaubt ist.
    """

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        bodies: Sequence[str],
        names: Mapping[str, str],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ROOMY, ROOMY, ROOMY, ROOMY)
        layout.setSpacing(NORMAL)
        layout.addWidget(QLabel(tr("Für welche Körper soll das gelten?"), self))
        self.list = QListWidget(self)
        for identifier in bodies:
            entry = QListWidgetItem(names.get(identifier, identifier), self.list)
            entry.setData(Qt.ItemDataRole.UserRole, identifier)
            entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(Qt.CheckState.Checked)
        layout.addWidget(self.list)

        self.all_of_them = QCheckBox(tr("Alle auswählen"), self)
        self.all_of_them.setChecked(True)
        self.all_of_them.toggled.connect(self._check_all)
        layout.addWidget(self.all_of_them)
        # Der Haken folgt der Liste, nicht nur umgekehrt: Wer den letzten
        # Körper abwählt, sieht sonst „Alle auswählen" angehakt über einer
        # leeren Wahl.
        self.list.itemChanged.connect(self._follow_list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        button_layout = buttons.layout()
        assert button_layout is not None
        button_layout.setSpacing(SPACE)
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText(title or tr("Übernehmen"))
        make_primary(self.ok_button)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _check_all(self, wanted: bool) -> None:
        state = Qt.CheckState.Checked if wanted else Qt.CheckState.Unchecked
        with QSignalBlocker(self.list):
            for row in range(self.list.count()):
                item = self.list.item(row)
                if item is not None:
                    item.setCheckState(state)
        self._update_ok()

    def _follow_list(self) -> None:
        with QSignalBlocker(self.all_of_them):
            self.all_of_them.setChecked(len(self.chosen()) == self.list.count())
        self._update_ok()

    def _update_ok(self) -> None:
        """Ohne einen einzigen Körper gibt es nichts zu tun — und der gesperrte
        Knopf sagt, warum (dieselbe Zusage wie im Druckdialog)."""
        empty = not self.chosen()
        self.ok_button.setEnabled(not empty)
        why = tr("Kein Körper ausgewählt.") if empty else ""
        self.ok_button.setToolTip(why)
        self.ok_button.setAccessibleDescription(why)

    def chosen(self) -> tuple[str, ...]:
        """Die angehakten Körper, in der Reihenfolge der Liste."""
        return tuple(
            str(item.data(Qt.ItemDataRole.UserRole))
            for row in range(self.list.count())
            if (item := self.list.item(row)) is not None
            and item.checkState() == Qt.CheckState.Checked
        )

    @classmethod
    def ask(
        cls,
        parent: QWidget | None,
        title: str,
        bodies: Sequence[str],
        names: Mapping[str, str],
    ) -> tuple[str, ...]:
        """Fragen und antworten — leer, wenn abgebrochen wurde."""
        dialog = cls(parent, title, bodies, names)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return ()
            return dialog.chosen()
        finally:
            dialog.deleteLater()


class _ReportList(QListWidget):
    """Die Befundliste: meldet das Drücken der linken Taste auf einer Zeile.

    ``itemClicked`` verlangt Drücken und Loslassen auf derselben Zeile; rollt
    die Liste dazwischen, weil die Karte ihre Höhe ändert, kommt kein Klick
    an (siehe ``ReportPanel``). Die rechte Taste gehört dem Kontextmenü.
    """

    leftPressed = Signal(QListWidgetItem)

    _least = 0
    """Die Mindesthöhe beim letzten Legen der Zeilen — siehe :meth:`updateGeometries`."""

    def _least_rows(self) -> int:
        """Die ersten drei sichtbaren Zeilen samt Rahmen, oder 0 ohne Zeile.

        Gemessen werden nur diese drei: Die Rechnung läuft in
        ``minimumSizeHint`` und ``updateGeometries``, und über alle Zeilen
        kostete sie offscreen bei 300 Befunden 11,6 ms je Aufruf (Durchsicht
        0.5.3).
        """
        visible = (row for row in range(self.count()) if not self.item(row).isHidden())
        rows = [
            max(
                self.visualRect(self.indexFromItem(self.item(row))).height(),
                self.sizeHintForRow(row),
            )
            for row in islice(visible, LEAST_REPORT_ROWS)
        ]
        return sum(rows) + 2 * self.frameWidth() if rows else 0

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Schnittstelle
        """So hoch wie die ersten drei sichtbaren Zeilen, mit Rahmen (RM-508).

        Darunter gibt die Liste im knappen Fenster nicht nach; den Rest rollt
        der Bericht über ihr (``overlay.FittedScroller``). Bei 1280 x 800 stand
        sonst von einer einzigen Warnung keine ganze Zeile da. Gemessen wird an
        den echten, umbrochenen Zeilen wie in ``overlay.rows_height``.
        """
        hint = super().minimumSizeHint()
        least = self._least_rows()
        return QSize(hint.width(), least) if least else hint

    def updateGeometries(self) -> None:  # noqa: N802 — Qt-Schnittstelle
        """Nach dem Legen der Zeilen: Hat sich die Mindesthöhe geändert, erfährt es das Layout.

        Die Zeilenhöhen hängen am Umbruch und damit an der Breite; ein Layout,
        das sich die Mindesthöhe aus dem ersten, schmalen Legen gemerkt hat,
        hielt die Liste auf 352 statt 104 Punkten, und der Bericht rollte
        seine Handlungen aus dem Bild.
        """
        super().updateGeometries()
        least = self._least_rows()
        if least != self._least:
            self._least = least
            self.updateGeometry()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 — Qt-Schnittstelle
        item = self.itemAt(event.position().toPoint())
        super().mousePressEvent(event)
        if item is not None and event.button() == Qt.MouseButton.LeftButton:
            self.leftPressed.emit(item)


class ReportPanel(QWidget):
    """Befunde aus Einlesen, Operationen und Prüfungen (§17.3)."""

    findingActivated = Signal(object)
    bundleActivated = Signal(object, object)
    """Eine Sammelzeile über mehrere Körper wurde angeklickt: Befund und Kennungen."""

    actionOnBodies = Signal(str, object)
    """Eine Handlung einer Sammelzeile, samt der Körper, für die sie gelten soll.

    Der gewöhnliche Weg geht über ``handlers_of`` und einen ``AppError`` — der
    trägt genau einen Körper. Eine Zeile, die zwölf vertritt, braucht einen
    zweiten: Das Panel fragt (:class:`BodyChoiceDialog`), das Fenster führt
    aus, und zwar als **eine** Transaktion über alle gewählten (Regel 16).
    Zwei Wege zur selben Handlung sind einer zu viel — deshalb kommt der hier
    nur zum Zug, wo es wirklich etwas zu wählen gibt."""

    contentGrew = Signal()
    """Die Liste hat Zeilen bekommen und will mehr Platz.

    Ein ``QListWidget`` meldet das von sich aus nicht — seine Wunschgröße
    hängt an der Größenrichtlinie, nicht am Inhalt. Und die Karte hängt in
    keinem Layout, das ein ``LayoutRequest`` weiterreichen könnte: sie bekommt
    ihre Geometrie von ``OverlayHost`` zugewiesen. Wer weiß, dass sich etwas
    geändert hat, sagt es — das ist der Weg, den ``OverlayHost.reflow``
    ausdrücklich vorsieht.
    """

    exportRequested = Signal()
    """Der Kunde will die Körper als Datei schreiben — derselbe Weg wie *Datei →
    Exportieren …* (RM-508)."""

    slicerRequested = Signal()
    """Der Kunde will das geprüfte Teil zum Slicer bringen.

    Der leere Bericht ist der häufigste Zustand nach einem sauberen Import —
    und genau dort stand der Kunde, der wissen wollte, ob er jetzt drucken
    kann, vor „Keine Befunde." und sonst nichts. Der Weg zum Slicer lag allein
    hinter *Datei → Druckeinstellungen …*, einem Namen, unter dem ein Laie nichts
    sucht. Der Eintrag heißt *Drucken vorbereiten*. Das Fenster verdrahtet dieses
    Signal mit demselben Dialog.
    """

    alertsChanged = Signal(int)
    """Wie viele Fehler und Warnungen jetzt im Bericht stehen.

    Der Reiter darüber trägt die Zahl; ohne sie ist eine Warnung unsichtbar,
    solange Chat oder Tour vorn stehen.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._names: Mapping[str, str] = {}
        """Kennung zu Namen aus der gezeigten Szene und der Auswertung."""
        self._review_basis = ""
        self._review_missing: tuple[str, ...] = (
            tr("Die unterstützten Prüfungen sind noch nicht vollständig nachgewiesen."),
        )
        self._document: Document | None = None
        """Für Herkunft, Zielableitung und ausführbare Berichtshandlungen."""
        self._stopped_at: OpId | None = None
        """Der wirklich angehaltene Schritt der gerade gezeigten Auswertung."""
        self._live_objects: Mapping[ObjectId, SceneObject] = {}
        """Die wirklich ausgewerteten Körper, nicht nur geplante Ausgänge."""
        self._findings: list[Finding] = []
        """Die rohen Befunde hinter den Zeilen. Die Liste im Fenster ist eine
        *Darstellung* davon (gebündelt, sortiert) — wer Zeilen aus Zeilen neu
        baut, liest ersetzte Bündel-Findings zurück und zerlegt die Bündelung.
        Genau das tat ``_resort`` nach dem ersten ``add_findings``."""
        self._alerts = 0
        """Fehler und Warnungen im aktuellen Bericht — siehe :meth:`alerts`."""
        self._alert_counts = (0, 0)
        """Dieselben getrennt, Fehler zuerst — siehe :meth:`alert_counts`."""
        self._list_follows: bool | None = None
        """Für welchen Zustand die Befundliste zuletzt von selbst auf- oder
        zugeklappt wurde: offen mit Fehlern oder Warnungen, zu mit Hinweisen
        allein (RM-508). Ein Klick des Kunden gilt, bis der Zustand wechselt —
        sonst klappte jede Auswertung nach einer Zahländerung zurück."""

        # **Der Bericht zeigt zuerst die Befunde** (RM-508). Im Ruhezustand
        # trug er rund 175 der 290 Wörter des Hauptfensters, davon 88
        # Befundtext; im Handbuchbild belegte der Kopf 62 % der Karte, und von
        # vier Befunden war einer zu sehen. Über der Liste steht jetzt eine
        # Zeile, die Kennzahlen stehen im Prüfumfang, der Nachbau in der Karte
        # der Handlungen, die Übergabe und der Export unten.
        body = QWidget(self)
        layout = QVBoxLayout(body)
        self._rows = layout
        """Die Zeilen des Berichts, im Rollbereich — die letzte ist der Stretch."""
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, TIGHT)
        layout.setSpacing(TIGHT)

        # Der Kopf: Zustand, Zähler (zugleich die Klappe der Liste) und
        # Prüfumfang in einer Zeile.
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(TIGHT)
        layout.addLayout(head)
        self.review_symbol = QLabel(body)
        self.review_symbol.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.summary = QLabel(tr("Keine Befunde."), body)
        self.summary.setWordWrap(True)
        head.addWidget(self.review_symbol)
        # Der Zustand nimmt den Platz der Zeile und bricht erst um, wenn die
        # Klappen rechts ihn brauchen.
        head.addWidget(self.summary, 1)
        self._head = head
        # Passt die Zeile nicht — französisch bei 440 Punkten Karte —, rückt der
        # Prüfumfang hierher (:meth:`_fit_head`), statt die Zähler zu kürzen.
        self._head_spill = QHBoxLayout()
        self._head_spill.setContentsMargins(0, 0, 0, 0)
        self._head_spill.addStretch(1)
        layout.addLayout(self._head_spill)

        findings_box = QWidget(body)
        self.list = _ReportList(findings_box)
        self.list.setObjectName("reportFindings")
        self.list.setAccessibleName(tr("Befunde"))
        # §2.7 schreibt die Sätze, die hier stehen — im schmalen rechten
        # Bereich endeten sie mitten im Wort hinter einer horizontalen
        # Bildlaufleiste. Umbruch statt Abschneiden: die Leiste bleibt aus,
        # und kein Befund wird auf „…" gekürzt.
        self.list.setWordWrap(True)
        self.list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Umgebrochene Zeilen messen sich an der Breite, die die Liste gerade
        # hat — ohne ``Adjust`` blieb die Höhe aus dem ersten Legen stehen, und
        # eine dreizeilige Meldung endete in der breiteren Karte auf „…“.
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        # §18.4 sagt „Klick auf eine Warnung fährt die Kamera hin" —
        # ``itemActivated`` allein hieß aber Doppelklick oder Eingabetaste,
        # und wer einmal klickte, bekam nichts. Beide Wege führen zum Ort;
        # dass ein Doppelklick dann zweimal fährt, ist dasselbe Ziel.
        # **Gewählt wird beim Drücken, nicht beim Loslassen.** Das Drücken
        # macht die Zeile zur aktuellen, die Karte darunter ändert ihre Höhe,
        # und die Liste rollt: Am Piratenschiff lag die letzte Zeile beim
        # Loslassen 90 Punkte tiefer, Qt meldete keinen Klick, und die
        # Sammelzeile über 17 Körper wählte nichts (Fensterabnahme RM-131).
        self.list.leftPressed.connect(self._on_activated)
        self.list.itemActivated.connect(self._on_activated)
        # Und was dagegen hilft, steht im Kontextmenü — siehe :meth:`_on_menu`.
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_menu)

        # Ein Bericht mit hundert Hinweisen und zwei Fehlern versteckt die zwei.
        # Gefiltert wird über den Text und über den Schweregrad; beides
        # zusammen, weil „Wandstärke" und „nur die Fehler" verschiedene Fragen
        # sind (§17.3). Erst ab :data:`FILTER_FROM` Zeilen (``_show_controls``).
        findings = QVBoxLayout(findings_box)
        findings.setContentsMargins(0, 0, 0, 0)
        findings.setSpacing(TIGHT)
        self.search = QLineEdit(findings_box)
        self.search.setMinimumHeight(TARGET_SIZE)
        self.search.setPlaceholderText(tr("Befunde durchsuchen …"))
        self.search.setAccessibleName(tr("Befunde durchsuchen"))
        self.search.textChanged.connect(self._refilter)
        self.severity = QComboBox(findings_box)
        self.severity.setMinimumHeight(TARGET_SIZE)
        self.severity.setAccessibleName(tr("Nach Schweregrad filtern"))
        self.severity.addItem(tr("Alle"), "")
        for name in ("error", "warning", "info"):
            self.severity.addItem(f"{SEVERITY_MARKER[name]} {_severity_label(name)}", name)
        self.severity.currentIndexChanged.connect(self._refilter)
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.addWidget(self.search, stretch=1)
        filter_row.addWidget(self.severity)
        findings.addLayout(filter_row)
        # Wenn der Filter alles wegnimmt, steht sonst ein leerer Rahmen da und
        # sagt nicht, ob nichts passt oder ob der Bericht leer ist. Ein Label
        # und kein Listeneintrag: gefiltert wird über ``setHidden``, die Liste
        # bleibt gefüllt, und ein Eintrag darin wäre beim nächsten Filtern im
        # Weg.
        self._nothing = QLabel("", findings_box)
        self._nothing.setWordWrap(True)
        self._nothing.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        self._nothing.setVisible(False)
        findings.addWidget(self._nothing)
        findings.addWidget(self.list, 1)

        # **Unter dem gewählten Befund eine Zeile, nicht drei** (Entscheidung
        # Robert, 05.10.2026): Folge, Ort und Grundlage als „Hinweis · Dose ·
        # intern geschätzt“ (:func:`finding_meta`), daneben die Einzelheiten
        # und ein Knopf, der die Stelle zeigt. Einen eigenen Folgesatz gibt es
        # nur, wo die Folge mehr ist als das Wort für die Schwere.
        meta = QHBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(TIGHT)
        findings.addLayout(meta)
        self.finding_context = QLabel("", findings_box)
        self.finding_context.setWordWrap(True)
        self.finding_context.setTextFormat(Qt.TextFormat.PlainText)
        set_level(self.finding_context, "caption")
        self.finding_context.hide()
        meta.addWidget(self.finding_context, 1)
        self.finding_details = QTextBrowser(findings_box)
        self.finding_details.setAccessibleName(tr("Einzelheiten zum Befund"))
        self.finding_details.setMaximumHeight(4 * TARGET_SIZE)
        self.finding_details.setOpenExternalLinks(False)
        details = collapsible(
            tr("Einzelheiten"),
            self.finding_details,
            open_now=False,
            contents=tr("Werte, Herkunft und Schritt des Befunds"),
            heading_row=meta,
        )
        details.setParent(findings_box)
        self.finding_details_toggle = _last_widget(meta)
        self.finding_details_toggle.toggled.connect(self._toggle_finding_details)
        self.finding_details_toggle.hide()
        self.finding_place = QPushButton(tr("Stelle zeigen"), findings_box)
        self.finding_place.clicked.connect(self._show_selected_place)
        self.finding_place.hide()
        meta.addWidget(self.finding_place)
        findings.addWidget(details)
        # Ein Folgesatz, wo es eine Folge gibt (:func:`finding_consequence`).
        self.finding_consequence = QLabel("", findings_box)
        self.finding_consequence.setWordWrap(True)
        self.finding_consequence.setTextFormat(Qt.TextFormat.PlainText)
        self.finding_consequence.hide()
        findings.addWidget(self.finding_consequence)

        # **Was gegen den gewählten Befund hilft, steht darunter.** Gebaut waren
        # die Handlungen längst, nur hingen sie an einem Rechtsklick auf eine
        # Listenzeile — und §2.7 verspricht „anklickbare Handlungen", nicht
        # welche zum Suchen. Leer bleibt die Zeile unsichtbar.
        self._offers = QWidget(findings_box)
        self._offers.setVisible(False)
        # Untereinander und über die ganze Breite: Zwei längere Handlungen
        # passten im schmalen Prüfbericht nicht nebeneinander. Der primäre
        # Knopf begann sichtbar außerhalb der Karte und verlor „Re“ von
        # „Reparieren“. Übersetzungen dürfen die Handlung nicht abschneiden.
        self._offer_row = QVBoxLayout(self._offers)
        self._offer_row.setContentsMargins(0, TIGHT, 0, 0)
        self._offer_row.setSpacing(TIGHT)
        # Was die vorgeschlagene Handlung außer ihrem Zweck verändert — der
        # Satz kommt aus dem Kern (``core.action_effects``) und steht unter dem
        # Hauptknopf, aber nur, wo sie etwas verändert (``effect_worth_showing``):
        # „Ändert nichts am Modell.“ stand unter 67 von 109 Handlungen.
        self.offer_effect = QLabel("", self._offers)
        self.offer_effect.setWordWrap(True)
        self.offer_effect.setTextFormat(Qt.TextFormat.PlainText)
        set_level(self.offer_effect, "caption")
        self.offer_effect.hide()
        self.list.itemSelectionChanged.connect(self._show_offers)
        findings.addWidget(self._offers)

        # Der Grund, wenn die Bewertung unvollständig ist — eine Zeile unter dem
        # Kopf; alle Gründe stehen im Prüfumfang.
        self.review_reason = QLabel("", body)
        self.review_reason.setWordWrap(True)
        self.review_reason.setTextFormat(Qt.TextFormat.PlainText)
        set_level(self.review_reason, "caption")
        self.review_reason.hide()
        layout.addWidget(self.review_reason)

        # Die Zähler sind die Klappe der Liste (:meth:`_settle_list`).
        self._findings_section = collapsible("", findings_box, heading_row=head)
        self._findings_section.setParent(body)
        self.list_toggle = _last_widget(head)
        self.list_toggle.toggled.connect(self._list_toggled)
        self.list_toggle.hide()

        # Der Prüfumfang, mit den Kennzahlen darin: was der Bericht in Sätzen
        # sagt, dort als Zahlen zum Vergleichen und Weitergeben.
        scope_box = QWidget()
        scope_rows = QVBoxLayout(scope_box)
        scope_rows.setContentsMargins(0, 0, 0, 0)
        scope_rows.setSpacing(TIGHT)
        self.facts = QLabel("", scope_box)
        self.facts.setWordWrap(True)
        self.facts.setVisible(False)
        self.review_scope = QLabel("", scope_box)
        self.review_scope.setWordWrap(True)
        self.review_scope.setTextFormat(Qt.TextFormat.PlainText)
        self.review_scope.setAccessibleName(tr("Grundlage des Übergabestatus"))
        scope_rows.addWidget(self.facts)
        scope_rows.addWidget(self.review_scope)
        self.review_scroll = QScrollArea(body)
        self.review_scroll.setWidgetResizable(True)
        self.review_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.review_scroll.setWidget(scope_box)
        self.review_scroll.setMaximumHeight(4 * TARGET_SIZE)
        self.review_scroll.setMinimumHeight(2 * TARGET_SIZE)
        self.review_scroll.setAccessibleName(tr("Prüfumfang"))
        self.review_scroll.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        scope = collapsible(
            tr("Prüfumfang"),
            self.review_scroll,
            open_now=False,
            contents=tr("Druckziel, Kennzahlen und Stand jeder Prüfung"),
            heading_row=head,
        )
        scope.setParent(body)
        self.review_toggle = _last_widget(head)
        self.review_toggle.toggled.connect(self._toggle_review_scope)
        self.review_toggle.hide()
        layout.addWidget(scope)
        layout.addWidget(self._findings_section, 1)
        layout.addStretch(0)

        # **Übergabe und Export stehen unten, außerhalb des Rollbereichs**
        # (RM-508): Mit dem Export enden alle vier Hauptwege (§2.2), und er
        # hatte keinen sichtbaren Knopf, nur *Datei → Exportieren* und Strg+E.
        # Außerhalb des Rollbereichs, damit kein langer Bericht den letzten
        # Schritt hinausschiebt — dieselbe Regel wie die Knopfzeile der Auswahl.
        self._footer = QWidget(self)
        footer = QHBoxLayout(self._footer)
        footer.setContentsMargins(NORMAL, TIGHT, NORMAL, NORMAL)
        footer.setSpacing(TIGHT)
        self.to_slicer = QPushButton(tr("An den Slicer übergeben …"), self._footer)
        self.to_slicer.setToolTip(
            tr("Druckeinstellungen prüfen und das Teil an den eingerichteten Slicer geben.")
        )
        self.to_slicer.clicked.connect(self.slicerRequested)
        self.export_button = QPushButton(tr("Exportieren …"), self._footer)
        self.export_button.setToolTip(
            tr(
                "Die Körper als STL, 3MF, OBJ, PLY, GLB oder STEP schreiben — "
                "mit der Prüfung aus dem Bericht davor."
            )
        )
        self.export_button.clicked.connect(self.exportRequested)
        for button in (self.to_slicer, self.export_button):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            footer.addWidget(button)
        self._footer.setVisible(False)

        # **Der Inhalt rollt, statt sich zu stauchen** (``overlay.FittedScroller``):
        # Erst gibt die Liste bis auf drei Zeilen nach (``_ReportList``), dann
        # rollt der Kopf mit dem Rest.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._scroller = FittedScroller(body, self)
        outer.addWidget(self._scroller, 1)
        outer.addWidget(self._footer)

        # Die Tabulatortaste geht den Weg des Auges: Kopf, Prüfumfang, Filter,
        # Liste, Befundzeile, Handlungen, unten Übergabe und Export.
        chain = (
            self.list_toggle,
            self.review_toggle,
            self.review_scroll,
            self.search,
            self.severity,
            self.list,
            self.finding_details_toggle,
            self.finding_place,
            self.to_slicer,
            self.export_button,
        )
        for before, after in pairwise(chain):
            QWidget.setTabOrder(before, after)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_head()

    def _fit_head(self) -> None:
        """Der Kopf ist eine Zeile, solange sie passt; sonst steht der Prüfumfang darunter.

        Gemessen am Zustand in einer Zeile und an der Breite des Berichts, nicht
        an gelegten Größen — sonst wechselte die Zeile bei jedem Legen hin und
        her. Die Zähler werden nie gekürzt: „1 avertisse…“ stand im französischen
        Fenster bei 1280 Punkten Breite.
        """
        head, spill, scope = self._head, self._head_spill, self.review_toggle
        shown = [
            widget.sizeHint().width()
            for widget in (self.review_symbol, self.list_toggle, scope)
            if not widget.isHidden()
        ]
        status = self.summary.fontMetrics().horizontalAdvance(self.summary.text())
        wanted = sum(shown) + status + len(shown) * head.spacing()
        bar = self._scroller.verticalScrollBar().sizeHint().width()
        room = self.width() - 2 * NORMAL - bar
        below = wanted > room
        if below == (spill.indexOf(scope) >= 0):
            return
        (head if below else spill).removeWidget(scope)
        (spill if below else head).addWidget(scope)

    def _toggle_finding_details(self, opened: bool) -> None:
        self.finding_details.setVisible(opened and bool(self.list.selectedItems()))
        self.contentGrew.emit()

    def _show_selected_place(self) -> None:
        items = self.list.selectedItems()
        if len(items) == 1:
            self._on_activated(items[0])

    def _show_finding_context(self, item: QListWidgetItem | None, *, shows: bool = False) -> None:
        """Die Befundzeile: Folge, Ort und Grundlage in einer Zeile (RM-508).

        ``shows`` sagt, dass eine angebotene Handlung die Stelle schon zeigt —
        dann gibt es keinen zweiten Knopf für denselben Weg (Durchsicht B10).
        """
        with QSignalBlocker(self.finding_details_toggle):
            self.finding_details_toggle.setChecked(False)
        self.finding_details_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.finding_details.hide()
        self.finding_context.setVisible(item is not None)
        self.finding_details_toggle.setVisible(item is not None)
        self.finding_place.hide()
        self.finding_consequence.hide()
        self.finding_details.clear()
        if item is None:
            self.finding_context.clear()
            return
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        bodies = tuple(key for key in (item.data(_BODIES_ROLE) or ()) if key in self._live_objects)
        place, way = finding_place(finding, bodies, self._live_objects, self._names)
        if way and not shows:
            self.finding_place.setText(way)
            self.finding_place.show()
        self.finding_context.setText(finding_meta(finding, place))
        from app.ui.print_contract import finding_consequence

        consequence = finding_consequence(finding)
        self.finding_consequence.setText(consequence)
        self.finding_consequence.setVisible(bool(consequence))
        self.finding_details.setPlainText(item.toolTip().replace(" · ", "\n"))

    def _show_offers(self) -> None:
        """Die Handlungen zum gewählten Befund als Knöpfe (§2.7).

        Dieselbe Quelle wie das Kontextmenü — :func:`actions_for` und die
        Handler des Fensters. Zwei Zugänge zu einer Wahrheit: der Rechtsklick
        ist der schnelle, diese Zeile der, den man findet.

        Neu gebaut statt versteckt: Welche Knöpfe hier stehen, hängt am
        gewählten Befund, und ein Vorrat aus wiederverwendeten Knöpfen müsste
        seine Beschriftung, seinen Handler und seine Sichtbarkeit einzeln
        nachziehen — drei Gelegenheiten für einen Knopf, der das Falsche tut.
        """
        self._unfold_the_chosen()
        row = self._offer_row
        while row.count():
            item = row.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is self.offer_effect:
                # Der Satz zur Nebenfolge bleibt; er wandert nur mit dem Hauptknopf.
                continue
            if widget is not None:
                # **Verstecken, nicht elternlos machen** (RM-101).
                # ``setParent(None)`` macht aus einem Kind-Widget ein
                # Top-Level-Fenster — ein Knopf „Auf das Bett setzen", der
                # allein auf dem Bildschirm steht, bis ``deleteLater`` die
                # nächste Runde der Ereignisschleife erreicht. Gemessen am
                # 12.09.2026: vier solche Knöpfe nach einem Befundwechsel,
                # zwei davon sichtbar. Dasselbe Wissen steht seit dem
                # Skizzeneditor zweimal im Code
                # (``MainWindow._close_sketch``,
                # ``SketchEditor.take_constraint_list``)
                # — hier stand es nicht.
                #
                # ``takeAt`` hat es schon aus dem Layout genommen; ``hide``
                # nimmt es aus dem Bild, und der Elternteil trägt es bis zum
                # Löschen.
                widget.hide()
                widget.deleteLater()

        items = self.list.selectedItems()
        finding: Finding | None = (
            items[0].data(Qt.ItemDataRole.UserRole) if len(items) == 1 else None
        )
        handlers = handlers_of(self)
        offered = (
            handled_actions(
                finding,
                self._document,
                handlers,
                stopped_at=self._stopped_at,
                live_objects=self._live_objects,
                bodies=items[0].data(_BODIES_ROLE) or (),
            )
            if finding is not None
            else []
        )
        primary = next(
            (action for action in offered if action.primary), offered[0] if offered else None
        )
        # **Ein Zeige-Knopf** (Durchsicht B10): Bietet der Befund selbst das
        # Zeigen an, entfällt der eigene Knopf der Befundzeile.
        self._show_finding_context(
            items[0] if finding is not None else None,
            shows=any(action.id in _SHOWING_ACTIONS for action in offered),
        )
        self.offer_effect.clear()
        self.offer_effect.hide()
        previous: QWidget = self.finding_place
        for action in offered:
            button = QPushButton(str(action.label), self._offers)
            button.setToolTip(str(finding.message) if finding is not None else "")
            if finding is not None and action.id == CORRECT_INPUT.id:
                # Der Rat des Kerns, den kein Knopf einlöst, steht beim Knopf,
                # der zu ihm führt — sonst ginge er im Bericht ganz verloren.
                advice = unhandled_advice(as_error(finding, self._document), handlers)
                if advice:
                    button.setToolTip("\n".join([str(finding.message), *advice]))
            effect = side_effect(action.id)
            if effect is not None:
                effect_line = tr("Nebenfolge: {effect}").format(effect=str(effect))
                button.setToolTip("\n".join((button.toolTip(), effect_line)).strip())
                button.setAccessibleDescription(effect_line)
                if action is primary and effect_worth_showing(action.id):
                    self.offer_effect.setText(str(effect))
                    self.offer_effect.show()
            if action is primary:
                make_primary(button)
            # ``weak_slot`` und nicht ein Lambda: ``handlers`` hält gebundene
            # Methoden des Fensters, und ein Lambda, das es fängt, schließt
            # den Ring Panel → Knopf → Handler → Fenster — gemessen hielten
            # zehn von zehn Wirten mit gewähltem Befund ihr Loslassen aus.
            # Die Handler holt der Klick deshalb selbst, frisch.
            group = (
                _import_group_for(finding, self._document, self._live_objects)
                if finding is not None and action.id == PLACE_ON_BED.id
                else ()
            )
            if group and finding is not None:
                button.clicked.connect(
                    weak_slot(
                        self,
                        ReportPanel._run_bound_bed_action,
                        as_error(finding, self._document, import_group=group),
                        self._document,
                    )
                )
            else:
                button.clicked.connect(weak_slot(self, ReportPanel._run_action, action.id))
            row.addWidget(button)
            if action is primary:
                row.addWidget(self.offer_effect)
            QWidget.setTabOrder(previous, button)
            previous = button
        if previous is not self.finding_place:
            QWidget.setTabOrder(previous, self.to_slicer)
        if not offered:
            row.addWidget(self.offer_effect)
        self._offers.setVisible(bool(offered))
        self._emphasise_slicer(bool(self._live_objects) and not offered)

    def _emphasise_slicer(self, ready: bool) -> None:
        """Bietet der Bericht nichts mehr an, steht der Weg zum Slicer halbfett da.

        **Ohne Akzentfläche:** Im Ruhezustand trägt nur *Bausteine* den Akzent
        (Entscheidung Robert, ``test_resting_state.py``). Als Hauptknopf leuchtete
        dieser Knopf neben ihm, sobald ein Modell übergabebereit war — zwei
        Signale, keines davon mehr eines. Dass nichts mehr aussteht, sagt die
        Zeile darüber mit Haken.
        """
        self.to_slicer.setDefault(False)
        font = self.to_slicer.font()
        font.setBold(ready)
        self.to_slicer.setFont(font)

    def _unfold_the_chosen(self) -> None:
        """Die gewählte Zeile ganz, jede andere mit ihrem ersten Satz (:func:`headline`)."""
        changed = False
        for row in range(self.list.count()):
            item = self.list.item(row)
            lines = item.data(_LINE_ROLE)
            if not lines:
                continue
            wanted = lines[1] if item.isSelected() else lines[0]
            if item.text() != wanted:
                item.setText(wanted)
                changed = True
        if changed:
            self._grew()

    def follow_export(self, allowed: bool, tip: str) -> None:
        """*Exportieren …* folgt dem Menüeintrag: dieselbe Sperre, derselbe Grund."""
        self.export_button.setEnabled(allowed)
        self.export_button.setToolTip(tip)
        self.export_button.setAccessibleDescription(tip)

    def _run_bound_bed_action(self, error: AppError, document: Document | None) -> None:
        """Der angezeigte Importumfang bleibt gebunden, der Handler prüft seine Gültigkeit."""
        if document is not self._document:
            return
        handler = handlers_of(self).get(PLACE_ON_BED.id)
        if handler is not None:
            handler(error)

    def _run_action(self, action_id: str) -> None:
        """Führt die Handlung des gewählten Befunds aus.

        Erst beim Klick werden Befund und Handler gelesen — nichts davon darf
        am Knopf hängen (siehe die ``weak_slot``-Begründung am Aufbau). Dass
        die Wahl zwischen Bau und Klick dieselbe ist, sichert Qt: Jede
        Wahländerung baut die Knopfzeile über ``itemSelectionChanged`` neu.
        """
        items = self.list.selectedItems()
        if len(items) != 1:
            return
        self._run_action_for(items[0], action_id)

    def _run_action_for(self, item: QListWidgetItem, action_id: str) -> None:
        """Knopf und Kontextmenü benutzen dieselbe Ziel- und Abbruchentscheidung."""
        finding: Finding | None = item.data(Qt.ItemDataRole.UserRole)
        # **Eine Sammelzeile fragt, für welche Körper sie gelten soll.** Sie
        # vertritt sechs oder zwölf, und ihr Befund trägt nur den ersten davon;
        # ihn stillschweigend zu nehmen wäre die Handlung an einem zufälligen
        # Ziel. Gefragt wird nur, wo es etwas zu wählen gibt — bei einem
        # einzigen Körper wäre der Dialog eine Bestätigung vor einer
        # rücknehmbaren Handlung, und die verbietet Regel 19.
        bodies: tuple[str, ...] = item.data(_BODIES_ROLE) or ()
        handler = handlers_of(self).get(action_id)
        if finding is not None and handler is not None and action_id == RECOGNIZE_LOCAL.id:
            # Der nächste Oberflächenklick wählt genau einen der genannten Körper.
            # Kein mehrfaches Öffnen, kein Rückfall auf die zufällige Baum-Auswahl.
            targets = _local_targets(finding, self._document, self._live_objects, bodies)
            if not targets:
                return
            error = as_error(finding, self._document)
            error.values["local_objects"] = targets
            handler(error)
            return
        if finding is not None and handler is not None and action_id == RECOGNIZE_FULLY.id:
            # Eine Sammelzeile nimmt die Wahl aller ihrer Körper zurück — eine
            # Auswertung, je Körper die Frage; sonst blieb die der übrigen
            # stehen, ohne dass die Zeile es sagte.
            error = as_error(finding, self._document)
            error.values["recognition_objects"] = bodies or (
                (finding.object_id,) if finding.object_id else ()
            )
            handler(error)
            return
        # Drei Wege für eine Sammelzeile, und der Unterschied ist, was die
        # Handlung meint. Eine **Operation** (der Name steht im Register) wird
        # ein Schritt je gewähltem Körper in einer Transaktion. Eine Handlung,
        # die **einem Körper** gilt (``_PER_BODY_ACTIONS``), läuft je gewähltem
        # Körper mit dessen eigenem Befund — nie mit dem des ersten. Alles
        # andere meint einen Schritt oder die ganze Szene und läuft einmal;
        # dafür gibt es nichts zu wählen.
        if (
            finding is not None
            and len(bodies) > 1
            and (REGISTRY.has(action_id) or action_id in _PER_BODY_ACTIONS)
        ):
            action = next(
                (
                    entry
                    for entry in actions_for_document(
                        finding,
                        self._document,
                        stopped_at=self._stopped_at,
                        live_objects=self._live_objects,
                    )
                    if entry.id == action_id
                ),
                None,
            )
            chosen = BodyChoiceDialog.ask(
                self, str(action.label) if action else "", bodies, self._names
            )
            if not chosen:
                return
            if REGISTRY.has(action_id):
                self.actionOnBodies.emit(action_id, chosen)
                return
            if handler is not None and action_id == SPLIT_MODEL.id:
                # **Eine Teilung nach der anderen** (RM-440): Die Suche läuft
                # im Arbeiter, und je Körper gestartet traf die zweite die
                # erste („Die Teilung läuft schon“). Das Fenster bekommt alle
                # gewählten Körper und teilt sie der Reihe nach.
                error = as_error(finding, self._document)
                error.values["split_objects"] = chosen
                handler(error)
                return
            members: dict[str, Finding] = item.data(_MEMBERS_ROLE) or {}
            if handler is not None:
                # **Ein Klick, ein Rückgängig-Schritt** (RM-372): Je Körper
                # legte der Handler eine eigene Transaktion an, und ein Strg+Z
                # nahm einen von dreien zurück. Die Sitzung sammelt sie.
                with _one_step(self):
                    for body in chosen:
                        handler(as_error(members.get(body, finding), self._document))
            return
        if finding is not None and handler is not None:
            if action_id == REPAIR_AND_RETRY.id:
                # Noch vor dem synchronen Umbau des Verlaufs sperren. Das
                # Ergebnis baut gleich eine frische Knopfzeile; der alte
                # Knopf bleibt auch dann gesperrt, wenn ein zweiter Klick
                # schon in der Ereignisschlange wartet.
                for button in self._offers.findChildren(QPushButton):
                    button.setEnabled(False)
            handler(as_error(finding, self._document))

    def _show_controls(self) -> None:
        """Filterzeile und Liste nur, wenn es etwas zu filtern gibt.

        Ein Bericht ohne Befunde ist der Normalfall — und er zeigte ein
        Suchfeld, eine Filterauswahl und einen leeren Listenkasten. Gefiltert
        wird erst ab :data:`FILTER_FROM` Zeilen; darunter überblickt man die
        Liste ohne Werkzeug.
        """
        count = self.list.count()
        self.list.setVisible(bool(count))
        for widget in (self.search, self.severity):
            widget.setVisible(count >= FILTER_FROM)
        if count < FILTER_FROM and (self.search.text() or self.severity.currentIndex()):
            # Ein Filter, der verschwindet, nimmt seine Wirkung mit — sonst
            # bliebe eine Auswahl gesetzt, die niemand mehr sehen und
            # zurücknehmen kann.
            self.search.clear()
            self.severity.setCurrentIndex(0)
        self._settle_list()

    def _settle_list(self) -> None:
        """Die Liste klappt mit ihrem Zähler: offen bei Fehlern und Warnungen.

        **Hinweise allein beginnen zugeklappt** (RM-508): Sie verlangen keine
        Entscheidung, und offen nahmen sie bei 1280 x 800 rund 250 Punkte
        Karte für Sätze wie „Ausgehöhlt.“. Der Zähler im Kopf nennt sie und
        öffnet sie. Wer selbst klappt, behält das, bis eine Warnung kommt oder
        geht. Ohne Befund gibt es keine Klappe.
        """
        count = self.list.count()
        self.list_toggle.setVisible(bool(count))
        section = self._findings_section
        if not count:
            self._list_follows = None
            section.hide()
        else:
            urgent = any(
                self.list.item(row).data(Qt.ItemDataRole.UserRole).severity != "info"
                for row in range(count)
            )
            if self._list_follows != urgent:
                self._list_follows = urgent
                self.list_toggle.setChecked(urgent)
            section.show()
        self._settle_stretch()
        self._fit_head()

    def _refilter(self) -> None:
        """Blendet aus, was nicht passt — gelöscht wird nichts.

        Die Zählung über der Liste bleibt die des ganzen Berichts: eine
        Filterzeile, die auch die Zusammenfassung filtert, verschweigt, dass es
        noch etwas anderes gibt.
        """
        query = self.search.text().casefold()
        wanted = str(self.severity.currentData() or "")
        for row in range(self.list.count()):
            item = self.list.item(row)
            finding: Finding = item.data(Qt.ItemDataRole.UserRole)
            matches = (not query or query in str(finding.message).casefold()) and (
                not wanted or finding.severity == wanted
            )
            item.setHidden(not matches)

        visible = sum(1 for row in range(self.list.count()) if not self.list.item(row).isHidden())
        if visible or not self.list.count():
            self._nothing.setVisible(False)
            return
        term = self.search.text().strip()
        level = self.severity.currentText().strip()
        if term and wanted:
            sentence = tr("Kein Befund passt zu „{term}“ und „{severity}“.")
        elif term:
            sentence = tr("Kein Befund passt zu „{term}“.")
        else:
            sentence = tr("Kein Befund dieser Stufe: „{severity}“.")
        self._nothing.setText(str(sentence).format(term=term, severity=level))
        self._nothing.setVisible(True)

    def show_result(
        self, result: EvaluationResult | None, document: Document | None = None
    ) -> None:
        # ``document`` nur für die Herkunft im Tooltip: welcher Schritt einen
        # Befund gemeldet hat. Die Liste sortiert nach Schwere, und damit
        # stehen Sätze aus verschiedenen Schritten untereinander — bei
        # ``weg3-generiert-aufbereiten`` liest sich das als Widerspruch:
        # „Das Modell ist nicht geschlossen." direkt neben „Eine offene Stelle
        # ist geschlossen und damit fort." Beides stimmt, das eine kommt vom
        # Einlesen, das andere von der Reparatur — und das stand nirgends.
        self._document = document
        self._stopped_at = result.stopped_at if result is not None else None
        self._live_objects = dict(result.scene.objects) if result is not None else {}
        # Die Namen der Körper, damit ein Befund sagen kann, welchen er meint.
        # Sie stehen im Ergebnis, das ohnehin hereinkommt — die Kennung „obj_2"
        # wäre die zweitbeste Antwort auf „welcher denn".
        #
        # Zwei Quellen, und die Reihenfolge ist die Aussage: Zuerst alle Namen,
        # die die Auswertung je vergeben hat, darüber die der Endszene. Ein
        # Körper, der noch da ist, heißt also so, wie er *jetzt* heißt; einer,
        # den ein späterer Schritt verbraucht hat, so wie er hieß, als der
        # Befund entstand. Vorher gab es nur die zweite Quelle, und dann stand
        # im Bericht „obj_1" — sichtbar im Handbuchbild, in allen sechs
        # Sprachen: Das Aushöhlen meldet etwas über die Dose, und nach
        # ``create_lid`` gibt es sie nicht mehr.
        self._names = (
            {
                **{str(key): name for key, name in result.object_names.items()},
                **{str(key): str(entry.name) for key, entry in result.scene.objects.items()},
            }
            if result
            else {}
        )
        self._findings = list(result.scene.report.findings) if result else []
        self._rebuild()
        self._count_up()
        self._measure_up(result)
        self._refilter()
        self._show_controls()
        self._grew()
        # Nach dem Filtern, denn eine ausgeblendete Zeile ist keine Antwort.
        self._preselect()

    def add_findings(self, findings: list[Finding], *, replacing_source: str | None = None) -> None:
        """Hängt Befunde an, die nicht aus der Auswertung kamen — die
        G-Code-Gegenprobe etwa (§28.2). Sie behalten ihre eigene
        Herkunft (§22.5).

        Was schon dasteht, kommt nicht noch einmal. Mehrere Prüfungen sehen
        dieselbe Sache: „Kollisionen prüfen" und die Exportprüfung melden beide,
        dass ein Körper über den Bauraum hinaussteht, und nach beiden stand die
        Zeile zweimal da. Zweimal gemeldet ist nicht zweimal passiert — ein
        Zähler daneben wäre eine Zahl, die etwas anderes behauptet.

        ``replacing_source`` räumt zuerst ab, was diese Herkunft schon gemeldet
        hat. Die G-Code-Befunde beschreiben die **jeweils letzte** Druckdatei —
        Regel 14 gibt mit der Herkunft das Kriterium frei Haus. Ohne das stand
        nach drei Läufen dreimal die Druckzeit da, jede mit anderer Zahl und
        darum nie „dasselbe" für die Erkennung darüber (Roberts Foto,
        30.08.2026): Eine veraltete Aussage über eine ersetzte Datei ist keine
        Historie, sondern Irreführung.
        """
        selected = self.list.selectedItems()
        selected_key = (
            _identity(selected[0].data(Qt.ItemDataRole.UserRole)) if len(selected) == 1 else None
        )
        if replacing_source is not None:
            self._findings = [entry for entry in self._findings if entry.source != replacing_source]
        # Je Identität der Befund, nicht nur die Menge: Derselbe Sachverhalt
        # kann mit zwei Gewichten eintreffen — die Auswertung meldet „unter dem
        # Druckbett" als Hinweis (ein Klick behebt es), die Exportprüfung beim
        # Schreiben als Warnung (der Klick ist nicht passiert). Die schwerere
        # Fassung ersetzt die leichtere; andersherum bliebe die Warnung stehen,
        # obwohl längst nur noch der Hinweis gilt — deshalb ersetzt auch die
        # leichtere die schwerere, sobald derselbe Sachverhalt leichter
        # wiederkommt. Was gleich schwer ist, bleibt wie bisher stehen.
        #
        # Gearbeitet wird auf den **rohen** Befunden, nie auf den Zeilen: Eine
        # Zeile kann ein Bündel vertreten, und ihr ``UserRole`` trägt dann ein
        # ersetztes Finding — wer damit weiterrechnet, zählt 1, wo 118 sind.
        standing = {_identity(entry): index for index, entry in enumerate(self._findings)}
        fresh = []
        for finding in findings:
            key = _identity(finding)
            found_at = standing.get(key)
            if found_at is not None:
                if self._findings[found_at].severity == finding.severity:
                    continue
                self._findings[found_at] = finding
            else:
                self._findings.append(finding)
                standing[key] = len(self._findings) - 1
            fresh.append(key)
        self._rebuild()
        self._count_up()
        self._refilter()
        # Nachlaufende Analyse ordnet die Liste neu, nimmt dem Kunden aber
        # nicht den gewählten Befund und seine Reparaturhandlung weg.
        if selected_key is not None:
            for row in range(self.list.count()):
                item = self.list.item(row)
                if (
                    not item.isHidden()
                    and _identity(item.data(Qt.ItemDataRole.UserRole)) == selected_key
                ):
                    self.list.setCurrentRow(row)
                    break
        self._preselect()
        # Auch hier: ein Befund, der nachkommt, bringt die Filterzeile mit —
        # sonst hängt sie an dem Stand, den die Auswertung hinterließ.
        self._show_controls()
        self._grew()
        if fresh:
            # Nach dem Ordnen steht der neue Befund nicht mehr unten, sondern
            # dort, wo sein Gewicht ihn hinstellt — also wird er gesucht und
            # nicht die Liste ans Ende gefahren.
            self._show_first_of(fresh)

    def _grew(self) -> None:
        """Melden, dass die Liste jetzt mehr Platz will — siehe ``contentGrew``.

        Die Karte blieb sonst so hoch, wie sie beim Auswerten war, und Befunde,
        die danach nachkamen (G-Code-Gegenprobe §28.2, Kollisionsprüfung,
        Exportprüfung), verschwanden hinter einem Rollbalken, während neben der
        Karte hunderte Pixel frei blieben.

        Aufgefallen ist es am Handbuchbild: acht Befunde im Kopf gezählt, zwei
        zu sehen.
        """
        self.list.updateGeometry()
        self.updateGeometry()
        self.contentGrew.emit()

    def _rebuild(self) -> None:
        """Die Zeilen aus den rohen Befunden bauen — sortiert und gebündelt.

        Der eine Weg von Befunden zu Zeilen, für Auswertung und Nachschub
        gleichermaßen: ein Fehler, der über ``add_findings`` nachkommt, gehört
        nach oben und in dieselbe Bündelung wie alles andere. Die Vorgängerin
        ``_resort`` las die Befunde aus den *Zeilen* zurück — und bekam für
        eine Sammelzeile das ersetzte Bündel-Finding statt seiner 118
        Mitglieder.
        """
        self.list.clear()
        for finding, members in _bundled(
            _by_severity(self._findings), self._document, self._live_objects or ()
        ):
            self._append(finding, members=members)

    def _preselect(self) -> None:
        """Den obersten Befund vorwählen, der eine Handlung anbietet.

        Die Knopfzeile unter der Liste zeigt die Handlungen des **gewählten**
        Befunds — und gewählt war nach dem Öffnen keiner. Der Kunde sah damit
        eine Liste und darunter nichts; dass ein Klick auf eine Listenzeile
        Knöpfe freischaltet, muss man wissen, und §2.7 verspricht anklickbare
        Handlungen und nicht auffindbare.

        Gemessen am häufigsten Fall überhaupt, dem ersten Öffnen eines
        Modells: ``block_with_rounded_edge.stl`` liegt von Z -10 bis +10, der
        Bericht meldet ``arrange.below_bed``, und *Auf das Bett setzen* löst es
        mit einem Klick. Vor der Vorauswahl standen dort null Knöpfe, nach
        einem Klick auf die Zeile einer — der Weg zur Lösung war einen Klick
        länger als nötig, und dieser Klick stand nirgends geschrieben.

        Drei Bedingungen, und jede hat ihren Grund:

        * **Nur ohne bestehende Wahl.** Eine Auswahl des Kunden zu
          überschreiben wäre schlimmer als keine Vorauswahl (§2.4).
        * **Nur sichtbare Zeilen.** ``_refilter`` blendet aus, was nicht zum
          Filter passt; eine versteckte Zeile vorzuwählen zeigt Knöpfe zu einem
          Befund, den niemand sieht.
        * **Nur mit angebotener Handlung.** Der oberste Befund ist der
          schwerste, aber nicht immer der, der etwas anzubieten hat —
          ``ingest.welded`` steht regelmäßig darüber und hat keine. Ihn
          vorzuwählen ließe die Zeile wieder leer.
        """
        if self.list.selectedItems():
            return
        handlers = handlers_of(self)
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.isHidden():
                continue
            finding = item.data(Qt.ItemDataRole.UserRole)
            if finding.severity == "info" and finding.object_id is None:
                # **Ein Hinweis zur Einrichtung ist nicht der erste Schritt am
                # Teil** (KUNDE-06). „Material kalibrieren“ stand vorgewählt,
                # in der Auswahlfarbe, mit orangem Hauptknopf, über jedem
                # sauberen Modell — und las sich wie eine Warnung. Ein Hinweis
                # am Körper (*Auf das Bett setzen*) bleibt vorwählbar.
                continue
            if handled_actions(
                finding,
                self._document,
                handlers,
                stopped_at=self._stopped_at,
                live_objects=self._live_objects,
                bodies=item.data(_BODIES_ROLE) or (),
            ):
                self.list.setCurrentRow(row)
                return

    def _show_first_of(self, keys: list[tuple[Any, ...]]) -> None:
        """Zum obersten der genannten Befunde scrollen.

        Geht ein frischer Befund in einer Sammelzeile auf, findet ihn diese
        Suche nicht — das Bündel-Finding trägt eine andere Identität — und es
        wird nicht gescrollt. Bewusst so: Nachschub ist praktisch nie
        wortgleich mit 118 Bestandszeilen, und ein falscher Sprung wäre
        schlimmer als keiner.
        """
        for row in range(self.list.count()):
            item = self.list.item(row)
            if _identity(item.data(Qt.ItemDataRole.UserRole)) in keys:
                self.list.scrollToItem(item)
                return

    def _append(self, finding: Finding, members: list[Finding] | None = None) -> None:
        """Einen Befund als Eintrag anhängen — oder ein Bündel als eine Zeile.

        ``members`` trägt bei einer Sammelzeile alle gebündelten Befunde
        (:func:`_bundled`). Die Zahl steht im Text der Zeile selbst und nicht
        nur im Tooltip (Regel 18: die Menge ist die Aussage, und sie braucht
        die sichtbare Kodierung); für die Zählung der Kopfzeile steht sie in
        :data:`_BUNDLE_ROLE`, damit ein Kernbefund mit eigenem ``count``-Wert
        weiter als eine Zeile zählt.
        """
        if members:
            names = ", ".join(self._member_label(one) for one in members[:15])
            if len(members) > 15:
                names += f" … (+{len(members) - 15})"
            # **Die Zahl steht davor, in Klammern** (Robert, 11.09.2026:
            # „anzahl dann davor in Klammer anzeigen"), der Satz einmal — die
            # Liste der Betroffenen wäre in der Zeile die nächste Flut und
            # gehört in den Tooltip. Waisen bekommen einen eigenen Satz ohne
            # CAD-Begriffe: „Merkmal" und „Nachfolger" erklären einem
            # Einsteiger weder den Zustand noch, dass seine Bearbeitung
            # erhalten blieb.
            sentence = (
                tr(
                    "Formdetails sind nach diesem Schritt nicht mehr automatisch "
                    "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
                    "Bearbeitung bleibt erhalten."
                )
                if finding.code == "perceive.orphaned"
                else str(finding.message)
            )
            # Verlorene Formdetails zählen, was verloren ist, nicht die
            # Körper: Jedes Mitglied fasst die seines Körpers schon zusammen.
            amount = sum(_lost_count(one) for one in members)
            message = f"({amount}) {sentence}"
            short = f"({amount}) {headline(sentence)}"
            # Gleicher Satz genügt nicht: Zwei Schritte wären in der Liste
            # optisch dieselbe Handlung, obwohl ihre Klicks an verschiedene
            # Ziele führen. „Schritt" ist die Sprache des sichtbaren Verlaufs
            # und keine interne Op-Kennung.
            context: list[str] = []
            # **Eine Zeile für neun Körper nennt keinen einzelnen.** Der
            # Befund trägt den des ersten Mitglieds, und ihn anzuschreiben
            # hieße, acht andere zu verschweigen. Gilt die Zeile einem
            # einzigen Körper, steht sein Name da wie an jeder Einzelzeile;
            # sonst stehen die Namen im Tooltip und die Kennungen in
            # :data:`_BODIES_ROLE` — daraus baut der Klick seine Auswahl.
            bodies = tuple(
                dict.fromkeys(str(one.object_id) for one in members if one.object_id is not None)
            )
            if len(bodies) == 1 and bodies[0] in self._names:
                name = self._names[bodies[0]]
                if name != bodies[0] and name not in message:
                    context.append(name)
            # Eine Einstellung je Teil nennt Feld und Wert in der Zeile, wenn
            # alle Mitglieder denselben tragen; die Teile stehen im Tooltip.
            if finding.code in PART_SETTING_CODES:
                shared = {_setting_line(one) for one in members if "setting" in one.values}
                if len(shared) == 1:
                    context.append(shared.pop())
            if finding.op_id is not None and all(one.op_id == finding.op_id for one in members):
                step = f"{tr('Schritt')} {step_number(self._document, finding.op_id)}"
                if self._document is not None:
                    transaction = next(
                        (
                            entry
                            for entry in self._document.transactions
                            if finding.op_id in entry.ops
                        ),
                        None,
                    )
                    if transaction is not None:
                        step = f"{step} · {transaction.title}"
                context.append(step)
            if context:
                message = f"{message} — {' · '.join(context)}"
                short = f"{short} — {' · '.join(context)}"
            item = QListWidgetItem(short)
            item.setData(_LINE_ROLE, (short, message))
            item.setData(_BUNDLE_ROLE, len(members))
            if len(bodies) > 1:
                item.setData(_BODIES_ROLE, bodies)
                # Je Körper sein erster Befund: Was eine Handlung je Körper
                # braucht, steht in dessen Werten, nicht in denen des ersten.
                by_body: dict[str, Finding] = {}
                for one in members:
                    if one.object_id is not None:
                        by_body.setdefault(str(one.object_id), one)
                item.setData(_MEMBERS_ROLE, by_body)

            # Nur Navigation mitnehmen, die für **jedes** Mitglied gilt.
            # ``_bundled`` hält Körper, Schritt und Herkunft bereits im
            # Gruppenschlüssel. Orte und Merkmale können sich gerade deshalb
            # unterscheiden, weil hier viele Einzelbefunde zusammenkommen;
            # der erste davon wäre keine Zusammenfassung, sondern eine
            # zufällige Behauptung.
            location = members[0].location
            outline = members[0].outline
            if any(one.location != location for one in members[1:]):
                # **Verschiedene Stellen eines Körpers bleiben auffindbar**, wenn
                # jedes Mitglied seinen Umriss trägt: *Stelle zeigen* fliegt zur
                # ersten und umrandet alle. Ohne Umriss wäre der erste Ort eine
                # zufällige Behauptung; die Zeile trägt dann keinen (RM-412).
                if len(bodies) <= 1 and all(
                    one.location is not None and one.outline for one in members
                ):
                    outline = tuple(segment for one in members for segment in one.outline)
                else:
                    location = None
                    outline = ()
            feature_ids = members[0].feature_ids
            if any(one.feature_ids != feature_ids for one in members[1:]):
                feature_ids = ()
            # **Die Werte der Zeile sind die Zahl und die Liste der
            # Betroffenen**, nicht die Werte des ersten Mitglieds: Bei neun
            # Buchstaben mit je eigenem Übermaß wäre das der Wert eines
            # zufälligen. Was jedes Mitglied für sich sagt, steht im Tooltip
            # (:meth:`_member_label`).
            # Ohne Körper — die Gegenprobe aus dem G-Code für Material und
            # Zeit — sind die Mitglieder keine „Objekte", sondern Einträge.
            listed = (
                "feature"
                if finding.code == "perceive.orphaned"
                else ("objects" if bodies else "entries")
            )
            values: Mapping[str, float | str | TranslatableText] = {
                "count": amount,
                listed: names,
            }
            finding = dataclasses.replace(
                finding,
                op_id=finding.op_id if all(one.op_id == finding.op_id for one in members) else None,
                message=message,
                feature_ids=feature_ids,
                values=values,
                location=location,
                outline=outline,
                # Verschiedene Vorschläge trennen schon den Gruppenschlüssel:
                # Eine verdichtete Fehlerzeile darf nie ihren Ausweg verlieren.
                suggestions=members[0].suggestions,
            )
        else:
            lost = _lost_count(finding)
            if finding.code == "perceive.orphaned":
                # Der Kernbefund bleibt für Agent, CLI und Datei kanalneutral.
                # Erst die sichtbare Zeile darf den konkreten UI-Klick nennen.
                # Mehrere Formdetails eines Schritts kommen als ein Befund und
                # stehen wie eine Sammelzeile da: die Zahl davor, in Klammern.
                several = tr(
                    "Formdetails sind nach diesem Schritt nicht mehr automatisch "
                    "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
                    "Bearbeitung bleibt erhalten."
                )
                finding = dataclasses.replace(
                    finding,
                    message=(
                        f"({lost}) {several}"
                        if lost > 1
                        else tr(
                            "Ein Formdetail ist nach diesem Schritt nicht mehr automatisch "
                            "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; "
                            "die Bearbeitung bleibt erhalten."
                        )
                    ),
                )
            elif lost > 1:
                finding = dataclasses.replace(finding, message=f"({lost}) {finding.message}")
            short = _line_for(
                dataclasses.replace(finding, message=headline(str(finding.message))), self._names
            )
            item = QListWidgetItem(short)
            item.setData(_LINE_ROLE, (short, _line_for(finding, self._names)))
        # Die Farbe folgt der Fläche, auf der sie landet. Die Rollenfarben sind
        # für den dunklen Untergrund gewählt; auf der weißen Liste des hellen
        # Themas brachte Bernstein 2,22 und das Hinweisblau 2,67 — jede Zeile
        # des Prüfberichts stand damit unter der Lesbarkeitsgrenze. Gefragt
        # wird die Liste selbst und nicht das eingestellte Thema: sie weiß, auf
        # was hier geschrieben wird.
        tone = QColor(
            text_colour(
                cast(Role, finding.severity),
                self.list.palette().base().color().name(),
            )
        )
        # Die Form trägt den Schweregrad, die Farbe verstärkt ihn nur: ein
        # Dreieck bleibt ein Dreieck, auch wo die Farbe nicht ankommt.
        item.setIcon(icon(f"severity-{finding.severity}", self.list, colour=tone))
        item.setData(Qt.ItemDataRole.UserRole, finding)
        # **Der Satz bleibt Fließtext, die Farbe steht am Symbol.** Ein ganzer
        # eingefärbter Satz war die lauteste Auszeichnung des Fensters für
        # eine Auskunft, die ohnehin schon eine hat — und ausgerechnet die
        # dringlichste Stufe traf es am härtesten: Rot bringt auf dem
        # Listengrund 4,52, Bernstein 7,46, Blau 6,19, während der gewöhnliche
        # Text 13,59 hätte. Der Fehler war der am schlechtesten lesbare
        # Befund. Regel 18 bleibt gewahrt: Die Form des Symbols trägt den
        # Schweregrad, und sie trug ihn schon vorher — Dreieck, Kreis, Punkt.
        item.setData(_TONE_ROLE, tone.name())
        # §22.5: woher eine Zahl kommt, ist Teil des Befunds und wird nie dem
        # Leser zum Annehmen überlassen — eine Schätzung ist keine Messung.
        details = [tr("Herkunft: {value}", value=origin_label(finding.source))]
        step = _origin_text(finding.op_id, self._document)
        if step:
            details.append(step)
        details.extend(_value_lines(finding))
        if members:
            details.extend(
                " · ".join(
                    filter(
                        None,
                        (
                            self._member_label(one),
                            _origin_text(one.op_id, self._document),
                            str(one.message),
                        ),
                    )
                )
                for one in members
            )
        detail_text = " · ".join(details)
        item.setToolTip(detail_text)
        # Tastatur und Bildschirmleser bekommen dieselbe Diagnose wie die
        # Maus. Bei verlorenen Formdetails liegt die interne Kennung bewusst
        # nur hier und nicht in der sichtbaren Nicht-CAD-Zeile.
        item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, detail_text)
        self.list.addItem(item)

    def _count_up(self) -> None:
        """Die Zeile über der Liste aus der Liste selbst zählen.

        Nicht aus dem übergebenen Ergebnis: Befunde kommen aus zwei Richtungen
        — aus der Auswertung und über ``add_findings`` —, und wer nur die eine
        zählt, schreibt „Keine Befunde" über eine Liste voller Befunde. Genau
        das stand hier.
        """
        counts = dict.fromkeys(SEVERITY_MARKER, 0)
        for row in range(self.list.count()):
            item = self.list.item(row)
            finding: Finding = item.data(Qt.ItemDataRole.UserRole)
            # Eine Sammelzeile (siehe ``_bundled``) zählt als das, was sie
            # bündelt — die Kopfzeile sagt sonst „6 Hinweise" über 123.
            counts[finding.severity] += item.data(_BUNDLE_ROLE) or 1
        alerts = counts["error"] + counts["warning"]
        # Auch bei gleicher Summe gemeldet: Aus einem Fehler kann eine Warnung
        # werden, und der Reiter zählt beide getrennt.
        if (counts["error"], counts["warning"]) != self._alert_counts:
            self._alerts = alerts
            self._alert_counts = (counts["error"], counts["warning"])
            self.alertsChanged.emit(alerts)
        # Übergabe und Export stehen, sobald ein Körper da ist — auch neben
        # Warnungen und Hinweisen, die den Druck nicht verhindern. Ohne Körper
        # gibt es nichts zu übergeben.
        live = bool(self._live_objects)
        self._footer.setVisible(live)
        self._emphasise_slicer(live and self._offers.isHidden())
        # **Zähler ohne Nullen** (RM-508): „0 x Fehler“ stand über jedem
        # sauberen Modell. Was es nicht gibt, wird nicht gezählt; die Zahl
        # trägt ihr Wort, das Wort seinen Plural.
        self.list_toggle.setText(
            " · ".join(count_phrases(counts["error"], counts["warning"], counts["info"]))
        )
        self.review_toggle.setVisible(live or any(counts.values()))
        if not live and not any(counts.values()):
            self.review_symbol.clear()
            self.summary.setText(tr("Keine Befunde."))
            self.review_reason.hide()
            return
        from app.ui.print_contract import handoff_state

        status = handoff_state(self._findings, self._review_missing)
        severity = (
            "error"
            if counts["error"]
            else ("warning" if self._review_missing or counts["warning"] else "info")
        )
        symbol = f"severity-{severity}" if severity != "info" else "done"
        self.review_symbol.setPixmap(icon(symbol, self).pixmap(TARGET_SIZE // 2))
        self.review_symbol.setAccessibleName(status)
        self.summary.setText(status)
        self._fit_head()
        # **Unvollständig sagt, warum** (Durchsicht B17): der erste Grund unter
        # dem Kopf, alle im Prüfumfang. Steht ein Fehler da, sagt der Status
        # schon mehr als die fehlende Prüfung.
        reason = self._review_missing[0] if self._review_missing and not counts["error"] else ""
        self.review_reason.setText(reason)
        self.review_reason.setVisible(bool(reason))

    def set_review_context(self, basis: str, missing: Sequence[str]) -> None:
        """Der Status beschreibt dieselbe Grundlage wie der Druckerknopf."""
        self._review_basis = basis
        self._review_missing = tuple(missing)
        self.review_scope.setText("\n".join(dict.fromkeys((*basis.splitlines(), *missing))))
        self._count_up()

    def _toggle_review_scope(self, _shown: bool) -> None:
        """Auf- und Zuklappen besorgt :func:`collapsible`; die Karte misst neu."""
        self.contentGrew.emit()

    def _list_toggled(self, _opened: bool) -> None:
        """Die Liste klappt — der freie Platz wandert, die Karte misst neu."""
        self._settle_stretch()
        self.contentGrew.emit()

    def _settle_stretch(self) -> None:
        """Der freie Platz gehört der offenen Liste, sonst dem Stretch darunter."""
        opened = bool(self.list.count()) and self.list_toggle.isChecked()
        rows = self._rows
        rows.setStretchFactor(self._findings_section, 1 if opened else 0)
        rows.setStretch(rows.count() - 1, 0 if opened else 1)

    def alerts(self) -> int:
        """Wie viele Befunde nach Aufmerksamkeit verlangen — Fehler und
        Warnungen, keine Hinweise.

        Der Reiter über diesem Panel trägt die Zahl. Ohne sie ist eine Warnung
        unsichtbar, solange etwas anderes vorn steht: ein eingelesenes Netz mit
        offenen Stellen meldete sich im Bericht, und im Fenster sah man einen
        Reiter, der aussah wie vorher.

        Hinweise zählen nicht mit. „Doppelte Punkte wurden verschweißt" ist
        eine Auskunft und keine Aufforderung; eine Zahl, die bei jedem Projekt
        dasteht, wird zur Tapete.
        """
        return self._alerts

    def alert_counts(self) -> tuple[int, int]:
        """Fehler und Warnungen getrennt — der Reiter zeigt je eine Marke."""
        return self._alert_counts

    def _measure_up(self, result: EvaluationResult | None) -> None:
        """Die Kennzahlen über den Befunden — wasserdicht, Volumen, Teile.

        Ein Bericht aus Sätzen sagt, *was* zu tun ist; er sagt nicht, woran man
        gerade ist. Diese drei Zahlen tun das, und sie kosten hier nichts —
        **weil der Auswertungsarbeiter sie vorher angefasst hat**
        (``session._warm_metrics``). Gemerkt werden sie am Körper; der erste
        Zugriff rechnet, und der lag bis zum 21.09.2026 in dieser Methode: 0,4
        s Hauptthread an einer Million Dreiecken, 15 s an einem exakten
        Gewinde (Review Leistung B1/B2).

        Bewusst nur, was ohne Schichtanalyse dasteht. Schmalste Wand und
        schlimmster Überhang gehören der Sache nach hierher, aber sie kosten
        einen Schnitt durch jede Schicht — eine Zeile, die beim Öffnen jeder
        Datei sekundenlang rechnet, ist keine Auskunft, sondern eine Bremse.
        """
        meshes = [entry.mesh for entry in result.scene.objects.values()] if result else []
        if not meshes:
            self.facts.setText("")
            self.facts.setVisible(False)
            return

        content = sum(float(mesh.volume) for mesh in meshes)
        parts = sum(int(mesh.component_count) for mesh in meshes)
        tight = sum(1 for mesh in meshes if mesh.is_watertight)
        # Das Wort steht neben dem Zeichen, nicht statt seiner (Regel 18).
        closed = (
            tr("geschlossen")
            if tight == len(meshes)
            else f"{tight}/{len(meshes)} {tr('geschlossen')}"
        )
        # Hier stand ein Malzeichen vor einem Plural, und das ist falsches
        # Deutsch: mit Singular hieße es zweimal dasselbe Teil, gemeint sind
        # zwei. Die Zeile darüber zählt Befunde und behält ihr Malzeichen —
        # dort steht der Singular dahinter.
        # **Über ``volume`` und nicht mit eigener Rechnung.** Hier stand
        # ``format_decimal(volume / 1000.0, 1)} cm³`` — zwei Fehler in einer
        # Zeile: Ein Teil von zwei Millimetern Kantenlänge stand als „0,0 cm³"
        # da, und in Zoll stand es auch dann in Kubikzentimetern, wenn jede
        # Länge daneben in Zoll gemessen war (§19.3). Beides beantwortet
        # ``labels.volume``: die Einheit aus der Anzeigeeinstellung, die Größe
        # aus dem Kern (:func:`units.format_volume`). Ohne Argument, weil diese
        # Karte keine eigene Einheit führt — die Anzeigeeinheit ist ein
        # Zustand, kein Feld.
        # Je Wert ein Name (RM-508): „66,6 cm³ · 2 Teile“ stand ohne Wort für
        # die erste Zahl über der Liste; im Prüfumfang heißt sie, was sie ist.
        self.facts.setText(
            " · ".join((closed, value_line("volume_mm3", content), value_line("parts", parts)))
        )
        self.facts.setVisible(True)

    def worst_severity(self, result: EvaluationResult | None) -> str | None:
        if result is None:
            return None
        return result.scene.report.worst_severity

    def _on_activated(self, item: QListWidgetItem) -> None:
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        bodies: tuple[str, ...] = item.data(_BODIES_ROLE) or ()
        if len(bodies) > 1:
            # Eine Sammelzeile über mehrere Körper zeigt beim Klick alle —
            # nie den ersten zufälligen (der Klickvertrag der Bündelung).
            self.bundleActivated.emit(finding, bodies)
            return
        self.findingActivated.emit(finding)

    def _member_label(self, finding: Finding) -> str:
        """Was ein Mitglied einer Sammelzeile im Tooltip von den anderen unterscheidet.

        Der Körper mit Namen, dahinter seine eigenen Werte — die Zeile sagt
        den Satz einmal, hier steht, für wen er gilt und mit welchen Zahlen.
        Waisen nennen ihr Merkmal, wie eh und je.
        """
        if finding.code == "perceive.orphaned":
            return str(finding.values.get("feature", finding.object_id or "?"))
        parts: list[str] = []
        if finding.object_id is not None:
            identifier = str(finding.object_id)
            parts.append(self._names.get(identifier, identifier))
        shown = {
            key: value
            for key, value in finding.values.items()
            if key not in ("count", "object", "objects", "entries", "name")
        }
        values = _value_lines(dataclasses.replace(finding, values=shown))
        # **Die Werte in Klammern hinter dem Namen**, nicht mit „ · “ daneben:
        # Die Einzelheiten brechen dort um, und in der Liste „Objekte: …“
        # stand dann „Komponenten: 2, obj_8“ in einer Zeile — Wert des einen,
        # Name des nächsten (Fensterabnahme RM-131).
        if parts and values:
            return f"{parts[0]} ({'; '.join(values)})"
        parts.extend(values)
        return " · ".join(parts) if parts else "?"

    def _on_menu(self, position: QPoint) -> None:
        """Was gegen diesen Befund hilft — als anklickbare Handlung (§2.7).

        Der Bericht sagte, was nicht stimmt, und hörte da auf. „Das Objekt
        steht über den Bauraum hinaus" ist ein Satz mit einer offensichtlichen
        Antwort — teilen oder verkleinern —, und beide Handlungen gab es
        längst: Sie hingen an ``OutOfBuildVolume``, einer Ausnahme, die
        **niemand wirft**. Drei Vorschläge, vollständig gebaut, nie angeboten.

        Angeboten wird nur, wofür das Fenster einen Handler hat, wie im
        Fehlerdialog auch (:func:`app.ui.dialogs.offered_actions`). Ein Befund
        ohne Handlung bekommt kein leeres Menü — das wäre ein Klick, der
        Auskunft verspricht und keine gibt.
        """
        item = self.list.itemAt(position)
        if item is None:
            return
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        handlers = handlers_of(self)
        offered = handled_actions(
            finding,
            self._document,
            handlers,
            stopped_at=self._stopped_at,
            live_objects=self._live_objects,
            bodies=item.data(_BODIES_ROLE) or (),
        )
        if not offered:
            return

        group = _import_group_for(finding, self._document, self._live_objects)
        bed_error = as_error(finding, self._document, import_group=group)
        document = self._document

        menu = QMenu(self)
        chosen: dict[Any, Any] = {}
        for action in offered:
            chosen[menu.addAction(str(action.label))] = action
        # Die Stubs versprechen eine Aktion; wer das Menü wegklickt, bekommt
        # None. Dieselbe Notlüge wie bei ``currentItem`` in der Palette.
        picked = cast(QAction | None, menu.exec(self.list.viewport().mapToGlobal(position)))
        # Erst nachschlagen, dann wegräumen: Die gewählte Aktion gehört dem
        # Menü, und ``deleteLater`` lässt ihr die Runde, in der sie gelesen
        # wird. Wie im Objektbaum gehört das Menü diesem Klick.
        action_id = chosen[picked].id if picked is not None else None
        menu.deleteLater()
        if action_id is None:
            return
        if action_id == PLACE_ON_BED.id and group:
            self._run_bound_bed_action(bed_error, document)
            return
        self._run_action_for(item, action_id)


class MeasurementLabel(QLabel):
    """Maße der Auswahl für die Statusleiste (§2.5)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._unit: LengthUnit = "mm"
        self.clear_selection()

    def set_unit(self, unit: LengthUnit) -> None:
        """§19.3: die Anzeigeeinheit. Der Kern bleibt bei Millimetern."""
        self._unit = unit

    def clear_selection(self) -> None:
        self.setText(tr("Keine Auswahl"))

    def show_object(
        self,
        name: str,
        size: tuple[float, float, float],
        content: float,
        note: str = "",
    ) -> None:
        """Die Maße der Auswahl, und bei mehreren Teilen, was für sie gilt.

        ``note`` steht am Ende und ist bei einem einzelnen Körper leer. Er
        trägt bei mehreren die Auskunft, welche Griffe für alle wirken und
        welche nicht — **bevor** gezogen wird und nicht als Meldung danach.
        Die Statusleiste ist dafür der richtige Ort: Sie steht ohnehin im
        Blick, sie verdeckt nichts, und sie verlangt kein Wegklicken.
        """
        text = (
            f"{name}   "
            f"{length(size[0], self._unit, with_unit=False)} × "
            f"{length(size[1], self._unit, with_unit=False)} × "
            f"{length(size[2], self._unit)}   "
            f"{volume(content, self._unit)}"
        )
        self.setText(f"{text}   {note}" if note else text)


#: Höchstanteil der Maßspalte im Objektbaum.
#:
#: Beide Spalten wollen Platz: der Name, weil zwei Körper eines Projekts sich
#: sonst nicht unterscheiden, und das Maß, weil eine halbe Zahl keine ist. Bei
#: 258 Pixeln Breite bekam der Name mit Qts Vorgabe 128 und mit reiner
#: Inhaltsbreite der Maßspalte 70 — beides zu wenig. Zwei Fünftel für das Maß
#: lassen dem Namen die Mehrheit und reichen für „60 x 40 x 12 mm" in der
#: Schrift, mit der wirklich gezeichnet wird.
MEASURE_SHARE = 0.4

#: Wie viele Zeilen eine Karte der linken Spalte mindestens hoch wird — drei,
#: damit der leere Zustand seinen Satz zeigen kann.
MIN_ROWS = 3

#: Der Deckel, solange niemand gesagt hat, wie viel Platz da ist.
#:
#: Er war einmal die ganze Antwort auf „ein Baum mit fünfzig Teilen darf nicht
#: die Spalte nehmen und den Verlauf hinausschieben". Die Sorge ist richtig,
#: eine Konstante ist die falsche Antwort darauf: im Vollbild stand der Baum
#: bei dreißig sichtbaren Zeilen auf zwölf und rollte, während unter der Karte
#: dreihundert Pixel leer blieben. Wie viel Platz da ist, weiß nur die
#: Überlagerung — sie teilt ihn über ``set_room`` zu, und dann gilt ihre Zahl
#: statt dieser.
MAX_ROWS = 12

LEAST_PARAMETER_ROWS = 3
"""Wie viele Parameterzeilen sichtbar bleiben, was auch zugeteilt wird.

Dieselbe Zahl wie der Boden der Listen (``least_height_of``), und aus
demselben Grund: Eine Karte, die auf eine Zeile gedrückt wird, zeigt nicht
weniger, sondern nichts — man sieht eine Zeile und weiß nicht, dass es
zwanzig gibt. Drei zeigen, dass es eine Liste ist.
"""


def fit_wrapped(label: QLabel) -> None:
    """Gibt einem umbrochenen Text die Höhe, die er wirklich braucht.

    Ein ``QLabel`` mit Zeilenumbruch meldet seine Höhe über
    ``heightForWidth``, und diese Kette reißt in einem Layout ohne
    Streckfaktor: der Satz „Noch keine Parameter …" bekam siebzehn Pixel und
    war nach anderthalb Zeilen abgeschnitten. Die Breite steht fest — die
    linke Spalte ist so breit, wie das Überlagerungsschema sie macht.
    """
    inner = LEFT_WIDTH - 2 * NORMAL
    label.setMinimumHeight(label.heightForWidth(inner))


def view_chrome(view: QAbstractItemView) -> int:
    """Was eine Liste über ihren Zeilen braucht: Rahmen, Spaltenkopf, Luft.

    Die zwei Pixel Luft am Ende sind nicht Zierde: ohne sie endet die letzte
    Zeile genau auf der Kante des Sichtfelds, und eine Zeile, die auf den
    Rahmen stößt, sieht abgeschnitten aus, auch wenn sie vollständig da ist.

    **Gefragt wird die Wunschhöhe des Kopfes, nicht seine aktuelle.** Ein
    Spaltenkopf, den Qt noch nicht gelegt hat, meldet 30 Pixel statt 16 —
    gemessen an einem frisch gebauten Baum. Der Deckel wurde daraus berechnet,
    also war der Objektbaum vierzehn Pixel höher als die zwölf Zeilen, die er
    zeigen sollte. Aufgefallen ist das erst, als eine andere Änderung den Kopf
    früher legte: Vorher lasen die Rechnung und der Test, der sie prüft,
    denselben falschen Wert, und beide waren zufrieden. Die Wunschhöhe steht von
    Anfang an fest.
    """
    header = 0
    if isinstance(view, QTreeWidget) and not view.isHeaderHidden():
        head = view.header()
        header = head.sizeHint().height() if head is not None else 0
    return header + 2 * view.frameWidth() + 2


def row_height_of(view: QAbstractItemView) -> int:
    """Wie hoch eine Zeile dieser Liste ist — notfalls geschätzt."""
    height = view.sizeHintForRow(0) if view.model() is not None else 0
    if height <= 0:
        height = view.fontMetrics().height() + 2 * TIGHT
    return height


def fit_to_rows(view: QAbstractItemView, rows: int, *, room: int | None = None) -> None:
    """Setzt die Höhe einer Liste oder eines Baums auf ihren Inhalt.

    Die linke Spalte baut ihre Karten ohne Streckfaktor, „so hoch wie ihr
    Inhalt" — gemeint war das seit je, umgesetzt war es nicht: Qt gab jeder
    Ansicht ihre eigene Mindesthöhe von etwa zwei Zeilen und ließ es dabei.
    Der Objektbaum scrollte damit ab dem zweiten Körper, während unter der
    Spalte sechshundert Pixel leer blieben — und der zweite Körper ist genau
    das, was nach einer Teilung entsteht.

    ``room`` ist die Höhe, die diese Liste haben darf. Sie kommt von der
    Überlagerung, die als einzige weiß, wie hoch das Fenster ist und wie viele
    Karten sich darin teilen müssen. Ohne sie gilt ``MAX_ROWS`` — für einen
    Aufruf, der von außerhalb der Spalte kommt, und für den Augenblick vor dem
    ersten Zuteilen.
    """
    chrome = view_chrome(view)
    row_height = row_height_of(view)
    wanted = chrome + max(rows, 0) * row_height
    ceiling = room if room is not None else chrome + MAX_ROWS * row_height
    view.setFixedHeight(max(least_height_of(view), min(wanted, ceiling)))


def least_height_of(view: QAbstractItemView) -> int:
    """Unter diese Höhe geht eine Liste nicht, was auch zugeteilt wird.

    Dieselbe Zahl, die ``fit_to_rows`` als Boden durchsetzt — und deshalb muss
    die Überlagerung sie kennen: Sie verteilte den Platz anteilig am Bedarf und
    rechnete damit für eine leere Verlaufsliste mit vier Pixeln, während der
    Boden ihr hundertzwölf gab. Die Summe der Zuteilungen lag danach über dem
    Platz, den es gab, und die Karte darüber wurde vom Layout zusammengedrückt,
    bis Zeilen außerhalb lagen.
    """
    return view_chrome(view) + MIN_ROWS * row_height_of(view)


def least_empty_height(label: QLabel) -> int:
    """Der Boden einer Karte, die gerade ihren leeren Zustand zeigt.

    Der leere Zustand tritt an die *Stelle* der Liste, und seine Höhe kommt aus
    dem umbrochenen Satz (``fit_wrapped``), nicht aus ``fit_to_rows``. Der
    leere Verlauf nannte deshalb 64 Pixel als Boden und stand auf 112 — die 48
    Pixel Unterschied fehlten der Karte darüber, und ihre letzten Zeilen lagen
    außerhalb des Abschnitts.

    Beide Zahlen hängen an der festen Spaltenbreite und nicht an der
    Zuteilung — die Bedingung, unter der die Spalte stillsteht.
    """
    return max(label.minimumHeight(), label.sizeHint().height())


def _folded(actions: Sequence[Any]) -> list[Any]:
    """Abgelehnte Handlungen mit **demselben** Grund zu einer Zeile.

    Die Reihenfolge bleibt die des Kerns: Die zusammengelegte Zeile steht
    dort, wo die erste ihrer Handlungen stand. Was gilt, wird nie
    zusammengelegt — eine Handlung mit Feldern und Knopf ist keine Zeile,
    die man mit einer anderen teilt.

    Die Titel werden mit Komma und „und" verbunden, weil der Satz dahinter
    einer ist: „Verschieben, Drehen, Verdoppeln und Entfernen — eine
    Verrundung gehört zu ihrer Kante." Vier Zeilen, die alle dasselbe sagen,
    lesen sich als vier Absagen; eine Zeile mit vier Namen liest sich als
    eine.
    """
    from app.core.perceive.actions import FeatureAction

    folded: list[Any] = []
    by_reason: dict[str, int] = {}
    for action in actions:
        if action.op is not None or not action.reason:
            folded.append(action)
            continue
        reason = str(action.reason)
        seen = by_reason.get(reason)
        if seen is None:
            by_reason[reason] = len(folded)
            folded.append(action)
            continue
        first = folded[seen]
        folded[seen] = FeatureAction(
            title=_and_then(str(first.title), str(action.title)),
            op=None,
            reason=first.reason,
        )
    return folded


def _and_then(gathered: str, further: str) -> str:
    """„A, B und C" — der letzte Name hängt mit „und" an, nicht mit Komma.

    **Ein gemeinsames erstes Wort fällt weg.** Die Operationen heißen
    „Merkmal verschieben", „Merkmal ändern", „Merkmal drehen" — fünfmal
    hintereinander gelesen steht das Wort im Weg und nicht im Satz. Geprüft
    wird auf Gleichheit und nichts sonst: Wo eine Sprache ihr gemeinsames
    Wort hinten trägt (im Französischen die *caractéristique*), fällt nichts
    weg, und das ist besser als eine Regel, die dort das Falsche kürzt.
    """
    leading = gathered.split(" ", 1)[0]
    if further.startswith(f"{leading} ") and len(further.split(" ", 1)) == 2:
        further = further.split(" ", 1)[1]
    if " und " in gathered:
        start, _, final = gathered.rpartition(" und ")
        return f"{start}, {final} und {further}"
    return f"{gathered} und {further}"


def _group_evidence_texts() -> dict[str, str]:
    """Ein Satz je Nachweis der Kern-Gruppe (``FeatureGroupEvidence``).

    Die Sätze stehen im Kern (``relations.group_evidence_texts``), weil der
    Steckbrief sie seit P1.5 auch liest — zur Laufzeit übersetzt, nicht beim
    Import. ``test_feature_panel`` hält die Schlüssel mit dem Literal des Kerns
    deckungsgleich.
    """
    from app.core.perceive.relations import group_evidence_texts

    return {str(key): text for key, text in group_evidence_texts().items()}


def _group_reason_texts() -> dict[str, str]:
    """Ein Satz je Grund, warum ein Merkmal nicht sicher dazugehört — aus dem Kern."""
    from app.core.perceive.relations import group_reason_texts

    return {str(key): text for key, text in group_reason_texts().items()}


#: Die Handlungen, deren Knopf unmittelbar in die Platzierung führt.
#:
#: **Eine Aufzählung und keine Regel**, weil es eine Bedienentscheidung ist und
#: keine Fähigkeit: *Merkmal verschieben* und *verdoppeln* tragen ihre Zahlen
#: als Felder daneben und tun auf Klick, was dort steht; *Zum Langloch ziehen*
#: ändert die **Form** eines Lochs, und wer sie ändert, will dabei sehen, wo es
#: sitzt (Robert, 10.09.2026). Wer eine weitere Handlung so haben will, trägt
#: sie hier ein — und nimmt ihr damit den unmittelbaren Klick.
LEADS_INTO_THE_VIEW: Final[frozenset[str]] = frozenset({"slot_hole", "resize_hole"})

#: Unter welchem Namen ein Merkmalsfeld sagt, welchen Parameter es trägt —
#: rechts im Merkmalfenster wie in der Maßgruppe im Bild, damit der Fokus von
#: einem zum anderen wandern kann (``MainWindow._hand_the_measures_over``).
FIELD_PROPERTY: Final = "featureField"


def feature_field(
    field: Any,
    parent: QWidget,
    *,
    expression_fields: Mapping[str, Any],
    part_fields: Mapping[str, Any],
    parameter_values: Mapping[str, float],
) -> QWidget:
    """Das Feld zur Art — Länge rechnet Zoll zurück, ein Winkel nicht.

    **Ein gebundener Wert bekommt das Ausdrucksfeld des Dialogs.** Die
    Textur nimmt es für jedes ihrer Zahlenfelder; ein Baustein nur dort,
    wo wirklich ein Ausdruck steht — sonst sähe die häufige Lage anders
    aus als bisher, ohne dass jemand einen Parameter im Spiel hätte.
    """
    entry = _expression_entry(field, expression_fields, part_fields)
    if entry is not None:
        from app.ui.op_dialog import ValueField

        editor: QWidget = ValueField(entry, field.value, parameter_values, parent)
        _explain_source(editor, field)
        return editor
    kind = str(field.kind)
    if kind == "bool":
        editor = RowCheckBox(parent)
    elif kind == "choice":
        combo = column_choice(QComboBox(parent))
        for value, text in field.choices or ():
            combo.addItem(choice_label(str(text)), value)
        explain_choices(combo)
        if field.name == "pattern":
            from app.ui.op_dialog import _show_patterns

            _show_patterns(combo, tuple(value for value, _text in field.choices or ()))
        editor = combo
    elif kind == "length":
        editor = BoundedLengthSpin(parent)
    elif kind == "count":
        # Eine ganze Zahl ohne Einheit — die Haken eines Einhängers, die
        # Löcher einer Halterung. Kein Längenfeld: Das trüge „mm" und
        # rechnete in Zoll um (`_kind_of` in ``perceive.actions``).
        editor = BoundedSpin(parent)
        editor.setDecimals(0)
        editor.setSingleStep(1.0)
    else:
        editor = BoundedSpin(parent)
    configure_feature_field(editor, field)
    return editor


def _expression_entry(
    field: Any, expression_fields: Mapping[str, Any], part_fields: Mapping[str, Any]
) -> Any:
    """Der Schemaeintrag, aus dem ein gebundener Wert sein Ausdrucksfeld bekommt — oder nichts."""
    from app.core.expressions import is_expression

    entry = expression_fields.get(field.name)
    if entry is None and is_expression(field.value):
        entry = part_fields.get(field.name)
    return entry


def configure_feature_field(editor: QWidget, field: Any) -> None:
    """Wert, Grenzen und Herkunft in ein gebautes Feld — beim Bau und beim Wiederverwenden.

    Die Art und die Auswahlwerte eines Felds stehen mit seinem Bau fest; was
    je Merkmal wechselt, steht hier: Spanne, Wert, Einheit und die Auskunft,
    woher der Ausgangswert kommt. Das Merkmalfenster baut eine Zeile, die zur
    selben Handlung mit denselben Feldern gehört, nicht neu (RM-204), sondern
    schreibt ihre Werte hier hinein — ohne Rückmeldung nach außen, denn
    niemand hat etwas eingegeben.
    """
    kind = str(field.kind)
    with QSignalBlocker(editor):
        for target in (editor, getattr(editor, "spin", None)):
            if isinstance(target, QWidget):
                target.setToolTip("")
                target.setStatusTip("")
                target.setAccessibleDescription("")
        if kind == "bool" and isinstance(editor, QCheckBox):
            editor.setChecked(bool(field.value))
        elif kind == "choice" and isinstance(editor, QComboBox):
            index = editor.findData(field.value)
            if index >= 0:
                editor.setCurrentIndex(index)
        elif kind == "length" and isinstance(editor, LengthSpin):
            minimum = float(field.minimum) if field.minimum is not None else -100000.0
            maximum = float(field.maximum) if field.maximum is not None else 100000.0
            editor.set_range_mm(
                minimum,
                maximum,
            )
            editor.set_value_mm(float(field.value))
            if float(field.value) < minimum or float(field.value) > maximum:
                editor.lineEdit().setText(length(float(field.value), with_unit=False))
        elif kind == "count" and isinstance(editor, BoundedSpin):
            minimum = int(field.minimum) if field.minimum is not None else 0
            maximum = int(field.maximum) if field.maximum is not None else 100000
            editor.setRange(minimum, maximum)
            editor.name_limits(field.minimum, field.maximum)
            editor.setValue(int(field.value))
            if int(field.value) < minimum or int(field.value) > maximum:
                editor.lineEdit().setText(editor.textFromValue(float(field.value)))
        elif isinstance(editor, QDoubleSpinBox):
            minimum = float(field.minimum) if field.minimum is not None else -360.0
            maximum = float(field.maximum) if field.maximum is not None else 360.0
            editor.setRange(
                minimum,
                maximum,
            )
            if isinstance(editor, (BoundedSpin, BoundedLengthSpin)):
                editor.name_limits(field.minimum, field.maximum)
            editor.setSuffix(f" {field.unit}" if field.unit else "")
            editor.setValue(float(field.value))
            if float(field.value) < minimum or float(field.value) > maximum:
                editor.lineEdit().setText(editor.textFromValue(float(field.value)))
    _explain_source(editor, field)


def _explain_source(editor: QWidget, field: Any) -> None:
    """Die Herkunft gehört zum unveränderten Ausgangswert, nicht zur neuen Eingabe."""
    status = getattr(field, "measurement", None)
    if status is None:
        return
    source = str(measure_explanation(status))
    qualifier = measure_qualifier(status)
    if isinstance(field.value, (int, float)) and not isinstance(field.value, bool):
        value = (
            length(float(field.value))
            if field.kind == "length"
            else f"{localised(f'{float(field.value):g}')} {field.unit}".strip()
        )
        if qualifier is not None:
            value = f"{value} · {qualifier}"
        source = tr("Ausgangswert: {value}. {source}").format(value=value, source=source)
    elif qualifier is not None:
        source = f"{qualifier}. {source}"
    current = editor.toolTip()
    hint = f"{current}\n{source}" if current else source
    editor.setToolTip(hint)
    editor.setAccessibleDescription(hint)
    inner = getattr(editor, "spin", None)
    if isinstance(inner, QWidget):
        inner.setToolTip(hint)
        inner.setAccessibleDescription(hint)


def feature_field_values(
    fields: Sequence[Any],
    widgets: Mapping[str, QWidget],
    fixed: Sequence[tuple[str, Any]] = (),
    *,
    feature_id: str | None = None,
) -> dict[str, Any]:
    """Was in den Feldern dieser Handlung steht, in der Einheit des Kerns.

    ``fixed`` sind die Werte, die die Handlung mitbringt und die niemand
    eingibt — an einer angeklickten Kante die Auswahl ``named`` und ihr
    Schlüssel (:attr:`~app.core.perceive.actions.FeatureAction.fixed`).
    Sie stehen **vor** den Feldern, damit ein Feld gleichen Namens gewinnt:
    Was der Kunde sieht, gilt.
    """
    params: dict[str, Any] = {}
    from app.ui.op_dialog import ValueField

    if feature_id is not None:
        # ``at_feature`` ist kein Feld: Welches Merkmal gemeint ist, steht
        # in der Auswahl, und eine Frage danach hätte ihre Antwort schon.
        params["at_feature"] = feature_id
    params.update(dict(fixed))
    for field in fields:
        widget = widgets.get(str(field.name))
        if isinstance(widget, ValueField):
            params[str(field.name)] = widget.value()
        elif isinstance(widget, LengthSpin):
            params[str(field.name)] = widget.value_mm() * field.parameter_factor
        elif isinstance(widget, QCheckBox):
            params[str(field.name)] = widget.isChecked()
        elif isinstance(widget, QComboBox):
            params[str(field.name)] = widget.currentData()
        elif isinstance(widget, QSpinBox) or (
            field.kind == "count" and isinstance(widget, QDoubleSpinBox)
        ):
            params[str(field.name)] = int(widget.value())
        elif isinstance(widget, QDoubleSpinBox):
            params[str(field.name)] = float(widget.value())
    return params


def refused_feature_field(widgets: Mapping[str, QWidget]) -> tuple[str, QWidget] | None:
    """Das erste abgelehnte Maß und das Feld, das seine Korrektur annimmt."""
    from app.ui.op_dialog import ValueField

    for editor in widgets.values():
        if editor.isHidden():
            continue
        if isinstance(editor, ValueField):
            refusal = editor.refusal()
            if refusal:
                target = editor.text if editor.toggle.isChecked() else editor.spin
                return refusal, target
            continue
        spins = (
            [editor]
            if isinstance(editor, QAbstractSpinBox)
            else editor.findChildren(QAbstractSpinBox)
        )
        for spin in spins:
            if (
                isinstance(spin, (BoundedSpin, BoundedLengthSpin))
                and spin.isVisibleTo(editor)
                and spin.refused_value() is not None
            ):
                return spin.refusal(), spin
    return None


def refresh_feature_fields(
    fields: Sequence[Any], widgets: Mapping[str, QWidget], values: Mapping[str, Any]
) -> None:
    """Kernwerte ohne Rückmeldung in dieselben Anzeige- und Ausdrucksfelder schreiben."""
    from app.ui.op_dialog import ValueField

    for field in fields:
        if field.name not in values:
            continue
        editor = widgets.get(str(field.name))
        value = values[field.name]
        if editor is None:
            continue
        # **Wer gerade tippt, bekommt nichts überschrieben.** Das Feld, in dem
        # der Kunde tippt, zeigt seine Eingabe; den Wert kennt der Entwurf
        # ohnehin. Der Fokus liegt dabei auf dem **Zeilenfeld im** Drehfeld,
        # nicht auf dem Drehfeld selbst. Die tragende Sperre steht beim
        # Aufrufer (``MainWindow._place_from_feature_panel``, ``reading``):
        # Offscreen gibt es keinen Fokus — der Aufrufer weiß, dass er liest.
        # Fokus allein ist keine Eingabe: Beim Wechsel aus der rechten Zeile
        # landet er schon in der neuen Maßkarte, bevor deren Werte folgen.
        # Nach Verlassen des Feldes darf auch ein Griff die Zahl neu setzen.
        focused = QApplication.focusWidget()
        if (
            focused is not None
            and (focused is editor or editor.isAncestorOf(focused))
            and any(line.isModified() for line in editor.findChildren(QLineEdit))
        ):
            continue
        with QSignalBlocker(editor):
            if isinstance(editor, ValueField):
                editor.set_value(value)
            elif isinstance(editor, LengthSpin):
                editor.set_value_mm(float(value) / field.parameter_factor)
            elif isinstance(editor, QCheckBox):
                editor.setChecked(bool(value))
            elif isinstance(editor, QComboBox):
                editor.setCurrentIndex(editor.findData(value))
            elif isinstance(editor, QSpinBox):
                editor.setValue(int(value))
            elif isinstance(editor, QDoubleSpinBox):
                editor.setValue(float(value))
    # Die Eingaben melden absichtlich nichts nach außen; ihre Bedingungen
    # müssen dennoch den neuen Werten folgen, auch bei gekoppelten Feldern.
    owners = {editor.parentWidget() for editor in widgets.values()}
    for owner in owners:
        if isinstance(owner, _MeasureBox):
            owner.conditionsChanged.emit()


#: Der Operationsname einer Handlung **ohne** Operation — *Maße ändern* und
#: *entfernen* an einem Baustein meinen den Schritt, nicht das Register.
#: ``str(action.op)`` macht aus ``None`` genau diese Zeichenkette; benannt,
#: damit kein Vergleich mehr gegen ein zufälliges ``"None"`` läuft.
NO_OPERATION: Final = "None"


@dataclasses.dataclass(frozen=True, slots=True)
class _Handling:
    """Was der eine Knopf unten über eine Handlung wissen muss.

    Seit dem 10.09.2026 steht kein Knopf mehr in jeder Zeile: Einer unten führt
    die aus, an der zuletzt jemand etwas angefasst hat. Er braucht dafür ihren
    Titel (für die Zusage daneben), ihren Satz, was sie tut — und wie viele
    gleichartige Merkmale es gibt, denn der Haken darüber gehört ihr ebenso.
    """

    title: str
    reason: str
    run: Callable[[], None]
    op: str
    members: int
    values: Callable[[], dict[str, Any]]
    action: Any = None
    take: Callable[[Mapping[str, Any]], None] | None = None
    """Kernwerte ohne Rückmeldung in die gegebenenfalls gesperrten Panelgegenstücke spiegeln."""
    in_view: Callable[[], None] | None = None
    """Der Weg ins Bild — oder nichts, wo die Handlung keine Stelle hat.

    Getrennt von :attr:`run`, seit der 11.09.2026 die beiden auseinanderhält:
    Bis dahin *war* das Übernehmen der Weg ins Bild, und wer eine Bohrung
    ändern wollte, landete in der Platzierung statt bei seinem Ergebnis
    (Robert: „auch 2 mal übernehmen einmal unten und einmal rechts")."""


class _FeatureAnswers(NamedTuple):
    """Was der Kern über ein Merkmal sagt, soweit das Merkmalfenster es liest."""

    cavity: tuple[Feature, ...]
    actions: tuple[Any, ...]
    groups: Mapping[str, FeatureActionGroup]
    unit: FunctionalGroup | None = None
    """Die funktionale Gruppe, in der das Merkmal steht (RM-184)."""
    unit_name: str = ""
    """Ihr Name im Baum, mit Nummer, wenn es mehrere gleiche gibt."""


def _nothing() -> None:
    """Ein toter schwacher Verweis — der Anfangsstand des Merkers."""
    return None


def feature_answers(
    feature_id: str,
    feature: Feature,
    features: Mapping[str, Feature] | None,
    mesh: MeshData | None,
    *,
    cancelled: CancelToken | None = None,
) -> _FeatureAnswers:
    """Was der Kern über dieses Merkmal sagt: Hohlraumkette, Handlungen, Gleichartige.

    Rein und ohne Qt, deshalb auch im Nebenthread aufrufbar (RM-232): An der
    dichten Platte mit 204 000 Dreiecken kosteten die drei Auskünfte beim
    ersten Klick einer Bohrung 130 ms im Hauptfaden, jede weitere Bohrung
    beim ersten Mal noch rund 60. Wer sie im Arbeiter rechnet, gibt ihr dort
    die Arbeiterkopie des Netzes (``placement_flow.for_a_worker``): Die
    trägen trimesh-Merker sind nicht threadsicher.
    """
    from app.core.perceive import relations
    from app.core.perceive.actions import actions_for

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    cavity: tuple[Feature, ...] = ()
    touches_other = False
    reason: relations.FeatureGroupReason | None = None
    if features is not None:
        if mesh is not None:
            state = relations.cavity_chain_state_at(feature, features, mesh)
            touches_other, reason = state.touches_other, state.reason
            cavity = state.chain or ()
        else:
            cavity = relations.bore_and_widening_at(feature, features) or ()
    actions = actions_for(
        feature,
        features,
        mesh=mesh,
        cavity=cavity,
        touches_other=touches_other,
        reason=reason,
        cancelled=cancelled,
    )
    groups: dict[str, FeatureActionGroup] = {}
    if features is not None and mesh is not None:
        groups = {
            group.action: group
            for group in relations.alike_for_actions(
                (str(action.op) for action in actions if action.op),
                feature_id,
                features,
                mesh,
            )
        }
    # Die Gruppe kommt aus demselben Merker wie *Kammer ändern* in den
    # Handlungen darüber — gerechnet einmal je Netz und Merkmalsliste.
    unit: FunctionalGroup | None = None
    unit_name = ""
    if features is not None and mesh is not None and len(features) > 1:
        from app.core.perceive.groups import functional_groups, group_of, numbered_titles

        functional = functional_groups(features, mesh, cancelled=cancelled)
        unit = group_of(feature_id, functional)
        if unit is not None:
            unit_name = numbered_titles(functional)[unit.key]
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    return _FeatureAnswers(cavity, tuple(actions), groups, unit, unit_name)


#: Der Merker des Merkmalfensters: der Körper (schwach), die Merkmalsliste,
#: für die er gilt, und je Merkmal die Auskunft (:meth:`FeaturePanel._answers_for`).
_RememberedAnswers = tuple[
    Callable[[], Any],
    Mapping[str, Feature] | None,
    dict[str, tuple[Feature, _FeatureAnswers]],
]


@dataclasses.dataclass(eq=False, slots=True)
class _ActionRow:
    """Eine gebaute Handlungszeile und die Handlung, die sie gerade trägt (RM-204).

    Die Widgets entstehen einmal (:meth:`FeaturePanel._new_row`); was je
    Merkmal wechselt — Schlüssel, Operation, Felder, feste Werte, Schritt —,
    steht hier und wird bei jedem Füllen neu gesetzt. Die Wege der Zeile
    (Ausführen, Werte lesen, ins Bild) lesen es beim Aufruf und nicht beim
    Bau; deshalb darf eine Zeile von einem Merkmal zum nächsten wandern.
    """

    box: QWidget
    signature: tuple[Any, ...] | None
    title: QLabel | None = None
    toggle: QToolButton | None = None
    """Der Umschalter des Akkordeons vor dem Titel (RM-510)."""
    summary: QLabel | None = None
    """Was die zugeklappte Handlung gerade einstellt — die Kopfzeile mit Wert."""
    body: QWidget | None = None
    """Die Felder; sichtbar nur, solange die Handlung offen ist."""
    dot: QToolButton | None = None
    button: QPushButton | None = None
    widgets: dict[str, QWidget] = dataclasses.field(default_factory=dict)
    labels: dict[str, QLabel] = dataclasses.field(default_factory=dict)
    refusals: dict[str, QLabel] = dataclasses.field(default_factory=dict)
    inner: dict[str, tuple[QWidget, ...]] = dataclasses.field(default_factory=dict)
    key: str = ""
    op: str = ""
    action: Any = None
    entries: tuple[Any, ...] = ()
    fixed: tuple[tuple[str, Any], ...] = ()
    step: int | None = None
    in_view: frozenset[str] = frozenset()
    """Die Felder, die gerade weichen, weil die Maßgruppe im Bild sie trägt."""
    coordinates: list[_CoordinateRow] = dataclasses.field(default_factory=list)
    """Die Zeilen, in denen X, Y und Z einer Stelle nebeneinander stehen."""


#: Die Felder einer Stelle, die nebeneinander stehen dürfen — in dieser Folge.
COORDINATE_FIELDS: Final = ("x", "y", "z")


#: Der längste Wert, für den ein Koordinatenfeld Platz hält: ein Meter, mehr
#: als ein Druckbett (Robert, 05.10.2026: „es würde auch 999,99 mm reichen“).
#: Qt bemisst ein Drehfeld am Rand seines Bereichs (±100 000 mm,
#: „-100000,00 mm“) und verlangte damit 118 Punkte je Feld; ein größerer Wert
#: rollt im Feld, statt die Zeile zu sprengen.
COORDINATE_ROOM: Final = 999.99


def _compact_width(editor: QAbstractSpinBox) -> int:
    """Die Mindestbreite eines Drehfelds für Werte bis :data:`COORDINATE_ROOM`, mit Pfeilen."""
    hint = editor.minimumSizeHint().width()
    if not isinstance(editor, QDoubleSpinBox):
        return hint
    metrics = editor.fontMetrics()

    def shown(value: float) -> int:
        text = editor.prefix() + editor.textFromValue(value) + editor.suffix()
        return metrics.horizontalAdvance(text)

    widest = max(shown(editor.minimum()), shown(editor.maximum()))
    room = shown(max(editor.minimum(), -COORDINATE_ROOM))
    return min(hint, hint - widest + room)


class _CoordinateRow(QWidget):
    """X, Y und Z einer Stelle nebeneinander — untereinander nur, wo es nicht geht.

    Seit RM-511 trägt die rechte Karte die Felder der Auswahl, und drei Zahlen
    stehen in einer Zeile (Robert, 05.10.2026). An einer Bohrung spart das bei
    *Verschieben* und *Verdoppeln* je zwei Zeilen. Als die Karte schmaler
    wurde, sollte die Zeile bleiben, die Felder kleiner werden und ihre
    Pfeiltasten behalten (Robert, 05.10.2026: „x/y/z sollten trotzdem in einer
    Zeile sein“, „mach sie bisschen kleiner“, „Maß behalten und ergänzen“).
    Jedes Feld hält deshalb Platz für Werte bis ±999,99 mm
    (:func:`_compact_width`) statt für den Rand seines Bereichs, und die Zeile
    passt mit Pfeilen in die Karte von 400 Punkten. Untereinander stehen die
    drei nur in einem sehr schmalen Fenster, statt eine Zahl abzuschneiden;
    entschieden wird an der Breite, die die Zeile bekommt.
    """

    def __init__(self, pairs: list[tuple[QLabel, QWidget]], parent: QWidget) -> None:
        super().__init__(parent)
        self._pairs = pairs
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(TIGHT)
        self._grid.setVerticalSpacing(TIGHT)
        self._across: bool | None = None
        self._arrange(across=True)

    def across(self) -> bool:
        """Ob die drei Felder gerade nebeneinander stehen."""
        return bool(self._across)

    def _fit_fields(self) -> None:
        """Jedem Drehfeld seine knappe Mindestbreite — gemessen am geltenden Stil."""
        for _label, editor in self._pairs:
            if isinstance(editor, QAbstractSpinBox):
                compact = _compact_width(editor)
                if editor.minimumWidth() != compact:
                    editor.setMinimumWidth(compact)

    def _needed(self) -> int:
        """Wie breit die Zeile sein muss, damit kein Feld unter sein Mindestmaß fällt."""
        widths = sum(
            label.sizeHint().width() + (editor.minimumWidth() or editor.minimumSizeHint().width())
            for label, editor in self._pairs
        )
        return widths + self._grid.horizontalSpacing() * (2 * len(self._pairs) - 1)

    def _arrange(self, *, across: bool) -> None:
        if across == self._across:
            return
        self._across = across
        for label, editor in self._pairs:
            self._grid.removeWidget(label)
            self._grid.removeWidget(editor)
        for column in range(2 * len(self._pairs)):
            self._grid.setColumnStretch(column, 0)
        for index, (label, editor) in enumerate(self._pairs):
            if across:
                self._grid.addWidget(label, 0, 2 * index)
                self._grid.addWidget(editor, 0, 2 * index + 1)
                self._grid.setColumnStretch(2 * index + 1, 1)
            else:
                self._grid.addWidget(label, index, 0)
                self._grid.addWidget(editor, index, 1)
        if not across:
            self._grid.setColumnStretch(1, 1)

    def follow_fields(self) -> None:
        """Die Zeile verschwindet mit ihren Feldern — sonst bliebe eine leere Lücke."""
        _set_shown(self, any(not editor.isHidden() for _label, editor in self._pairs))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt-Name
        """So schmal wie ein Paar: Untereinander geht immer."""
        hint = super().minimumSizeHint()
        narrow = max(label.sizeHint().width() for label, _editor in self._pairs) + max(
            editor.minimumSizeHint().width() for _label, editor in self._pairs
        )
        return QSize(narrow + self._grid.horizontalSpacing(), hint.height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt-Name
        super().resizeEvent(event)
        self._fit_fields()
        self._arrange(across=event.size().width() >= self._needed())


#: Wie viele Maßgruppen verschiedener Bauart auf ihre Wiederkehr warten
#: (:meth:`FeaturePanel.keep_measure_group`) — die älteste geht zuerst.
SPARE_MEASURE_GROUPS: Final = 4


class _MeasureBox(QWidget):
    """Die Maßgruppe erneuert ihre Bedingungen auch nach stiller Wertübernahme."""

    conditionsChanged = Signal()


@dataclasses.dataclass(slots=True)
class _MeasureGroup:
    """Eine gebaute Maßgruppe und ihre Teile — die Widgets bleiben, Texte und Werte wechseln.

    Dasselbe Muster wie :class:`_ActionRow` (RM-204), eine Ebene weiter: Die
    Maßgruppe im Bild entstand bis zum 27.09.2026 bei jedem Merkmalklick neu,
    am Wabenhalter von Bohrung zu Bohrung rund siebzehn Widgets je Klick,
    die gebaut, poliert und wieder gelöscht wurden, obwohl sich nur Werte
    und Texte änderten (RM-232). ``released`` trägt, was der Empfänger beim
    Binden angehängt hat — er löst es beim Zurückgeben selbst
    (:meth:`FeaturePanel.keep_measure_group`).
    """

    box: QWidget
    signature: tuple[Any, ...] | None
    title: QLabel
    current: QLabel | None
    note: QLabel | None
    widgets: dict[str, QWidget]
    labels: dict[str, QLabel]
    refusals: dict[str, QLabel]
    fields: tuple[Any, ...] = ()
    fixed: tuple[tuple[str, Any], ...] = ()
    released: list[Callable[[], None]] = dataclasses.field(default_factory=list)
    more: QWidget | None = None
    """Die Klappe „Weitere Werte“ mit X, Y und Z der Stelle — ``None`` ohne Koordinaten."""


def _coordinate_fields(action: Any) -> frozenset[str]:
    """Die Felder einer Handlung, die die Stelle als X, Y und Z tragen (RM-516).

    Im Bild steht die Stelle über die Kantenmaße; diese drei Felder sagen
    dasselbe noch einmal und stehen deshalb hinter „Weitere Werte“. Die Namen
    kommen aus dem Schema der Operation (``placement_fields``), nicht aus einer
    zweiten Liste hier.
    """
    from app.core.knowledge.parts.ops import placement_fields

    op = getattr(action, "op", None)
    if not isinstance(op, str) or not REGISTRY.has(op):
        return frozenset()
    placed = placement_fields(REGISTRY.get(op).params)
    names = frozenset(placed.get(axis, axis) for axis in ("x", "y", "z"))
    given = {str(field.name) for field in action.fields}
    return names if names <= given else frozenset()


def _set_shown(widget: QWidget, visible: bool) -> None:
    """Zeigt oder verbirgt ein Widget — aber nur, wenn sich dabei etwas ändert.

    ``setVisible`` kehrt in Qt nur bei einem **ausdrücklich** gesetzten
    gleichen Zustand sofort zurück; eine Zeile, die das Layout eingeblendet
    hat, durchläuft bei jedem ``setVisible(True)`` die ganze Anzeige mit
    Ereignissen an jeden Anwendungsfilter. Im Merkmalfenster geschah das je
    Klick gut hundertmal — Zwillingszeilen, Info-Zeichen, die Knopfzeile —,
    im gebauten Fenster eine halbe Millisekunde je Aufruf (22.09.2026).

    **Verborgen heißt ausdrücklich verborgen** (Durchsicht 0.5.1). Ein Widget,
    das gerade erst in ein sichtbares Layout kam, meldet ``isHidden()``, bis
    Qt es mit einem eingereihten ``_q_showIfNotHidden`` zeigt — und zeigt es
    dann auch, wenn es inzwischen verborgen sein sollte, weil niemand das
    ausdrücklich gesagt hat. So stand der Block von *Bohrung ändern* rechts,
    während dieselben Felder als Maßgruppe im Bild standen (RM-199).
    """
    if visible:
        if widget.isHidden():
            widget.setVisible(True)
    elif not widget.isHidden() or not widget.testAttribute(
        Qt.WidgetAttribute.WA_WState_ExplicitShowHide
    ):
        widget.setVisible(False)


def _measure_group_alive(group: _MeasureGroup) -> bool:
    """Ob jedes Widget einer Maßgruppe noch lebt — sonst wird neu gebaut."""
    parts: list[QWidget | None] = [
        group.box,
        group.title,
        group.current,
        group.note,
        group.more,
        *group.widgets.values(),
        *group.labels.values(),
        *group.refusals.values(),
    ]
    return all(part is None or isValid(part) for part in parts)


def _discard_measure_group(group: _MeasureGroup) -> None:
    """Eine wartende Maßgruppe, die keiner mehr nimmt, geht wie jede andere."""
    if isValid(group.box):
        group.box.hide()
        group.box.deleteLater()


def _discard_spare_measures(spares: dict[tuple[Any, ...], _MeasureGroup], *_args: object) -> None:
    """Alle wartenden Maßgruppen eines Merkmalfensters, das gerade geht."""
    for group in list(spares.values()):
        _discard_measure_group(group)
    spares.clear()


def _focus_stops(row: QWidget) -> list[QWidget]:
    """Die Halte der Tabulatortaste in einer Zeile, von oben nach unten.

    Die Zeile selbst zählt mit: Der Umschalter *Vor Trennnähten schützen* und
    der Katalogknopf stehen ohne Kasten in der Liste, und ``findChildren``
    sieht ein Widget nie als sein eigenes Kind. Nicht mit zählt, was zum
    Innenleben eines Felds gehört: das Textfeld **in** einem Drehfeld und die
    Liste im Aufklappfenster einer Auswahl. Die Liste ist ein Kind der
    Auswahl, wohnt aber in einem eigenen Fenster; als letzter Halt einer Zeile
    hängte ``_settle_tab_order`` den Knopf unten hinter sie statt hinter das
    Feld, und die Tabulatortaste lief an ihm vorbei (22.09.2026).
    """
    home = row.window()
    return [
        child
        for child in (row, *row.findChildren(QWidget))
        if child.focusPolicy() != Qt.FocusPolicy.NoFocus
        and not isinstance(child, QLineEdit)
        and child.window() is home
    ]


def _leads_into_the_view(op: str) -> bool:
    """Ob dieser Knopf ins Bild führt, statt sofort auszuführen."""
    return op in LEADS_INTO_THE_VIEW and _places_on_a_surface(op)


def _explained(action: Any) -> str:
    """Der Satz hinter dem Info-Zeichen einer Handlung.

    Drei Quellen, in dieser Reihenfolge: was zur **Lage** zu sagen ist, der
    Grund der Handlung, und der ``doc``-Satz ihrer Operation. Der letzte ist
    der Rückfall, der immer trägt — jede Operation hat einen (Regel 4), und er
    steht ohnehin schon im Menü und über dem Dialog.
    """
    for text in (getattr(action, "note", ""), getattr(action, "reason", "")):
        if text:
            return str(text)
    op = getattr(action, "op", None)
    if op and REGISTRY.has(str(op)):
        return str(REGISTRY.get(str(op)).doc or "")
    return ""


def _places_on_a_surface(op: str) -> bool:
    """Ob diese Operation ihre Stelle auf einer Fläche einstellen lässt.

    Der Kern beantwortet es (``placement.supports_surface_placement``), und die
    Oberfläche fragt nur — dieselbe Bauart wie bei den Handlungen selbst, die
    aus ``applies_to`` kommen. Eine unbekannte Operation trägt keinen Weg;
    ``False`` ist dort die ehrliche Antwort und kein Fehler.
    """
    from app.core.registry import REGISTRY
    from app.core.scene import placement

    if not REGISTRY.has(op):
        return False
    return bool(placement.supports_surface_placement(REGISTRY.get(op)))


def _feature_group_note(group: FeatureActionGroup) -> str:
    """Die Belege und Grenzen der Kern-Gruppe als lesbare Auskunft.

    Ein Nachweis oder Grund ohne Satz fällt aus der Auskunft, statt sie zu
    stürzen — der Test hält die Listen deckungsgleich, das Fenster bleibt
    trotzdem stehen, wenn der Kern einmal schneller war.
    """
    evidence = _group_evidence_texts()
    reasons = _group_reason_texts()
    parts = (
        [str(evidence[key]) for key in group.evidence if key in evidence]
        if len(group.members) > 1
        else []
    )
    if group.uncertain:
        parts.append(str(tr("Nicht sicher zugeordnete Merkmale bleiben ausgenommen.")))
        parts.extend(
            dict.fromkeys(
                str(reasons[item.reason]) for item in group.uncertain if item.reason in reasons
            )
        )
    return " ".join(parts)


#: Wie viele Zeichen eine Auswahl in einer Spalte mindestens zeigt (RM-488).
COLUMN_CHOICE_LETTERS: Final = 12


def column_choice(combo: QComboBox) -> QComboBox:
    """Eine Auswahl, die mit ihrer Spalte schmal wird, statt sie zu sprengen (RM-488).

    Qts Vorgabe nimmt den längsten Eintrag als Mindestbreite: „Senkung, Stufen
    und Verengung mitnehmen“ machte das Auswahlfenster breiter als seine
    Spalte, und jedes Feld daneben endete ohne Pfeile am Rand. Die offene
    Liste bleibt so breit wie ihr längster Eintrag (Fusion), gekürzt wird nur
    die geschlossene Anzeige.
    """
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(COLUMN_CHOICE_LETTERS)
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return combo


class ColumnScroller(QScrollArea):
    """Ein Rollbereich, der nur senkrecht rollt und so breit bleibt wie sein Inhalt (RM-488).

    Die Breite des Inhalts ist an die Spalte gebunden, in beide Richtungen:
    ``setWidgetResizable`` zieht ihn auf die Spalte, und die Mindestbreite des
    Inhalts wird die der Spalte. Ein waagrechter Balken unter Zahlenfeldern
    versteckt ihre Pfeile und Info-Zeichen; ein zu breites Feld macht
    stattdessen die Spalte breiter, statt rechts abgeschnitten zu werden.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    @override
    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        content = self.widget()
        if content is None:
            return hint
        # Der senkrechte Balken zählt immer mit: Kommt er erst beim Rollen,
        # darf er nichts verdecken, und die Spalte springt nicht.
        bar = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent, None, self)
        least = content.minimumSizeHint().width() + bar + 2 * self.frameWidth()
        return QSize(max(hint.width(), least), hint.height())

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # ``setWidget`` trägt den Rollbereich als Filter am Inhalt ein; ein neu
        # gelegter Inhalt kann eine neue Mindestbreite haben.
        if watched is self.widget() and event.type() == QEvent.Type.LayoutRequest:
            self.updateGeometry()
        return super().eventFilter(watched, event)


class SelectionScroller(ColumnScroller, ContentScroller):
    """Der Rollbereich im Reiter *Auswahl*: nur senkrecht, und er wünscht alles.

    Die Breite regelt :class:`ColumnScroller`, den Wunsch
    :class:`~app.ui.overlay.ContentScroller` — so wächst die rechte Karte mit
    der Auswahl bis an den Platz, den das Fenster hat, und rollt erst danach.
    Der Parameterbereich links behält Qts Wunsch; er teilt sich seine Spalte
    mit drei Nachbarn, und die Spalte verteilt selbst.
    """


class FeaturePanel(QWidget):
    """Was man mit dem gewählten Merkmal tun kann — als Felder, nicht als Menü.

    Robert am 03.09.2026: „evtl noch ein eigenes Panel, damit man nicht für
    alles Rechtsklick machen muss — übersichtlich, verständlich, innovativ und
    intuitiv." Das Panel zeigt, **was Solidon an dieser Stelle gemessen hat**,
    und macht jede Zahl änderbar: Ort, Durchmesser, Tiefe, Achse. Eine
    geänderte Zahl ist die Operation, kein Modus und kein zweiter Dialog.

    **Es kennt die Merkmalsarten nicht.** Welche Handlung für welche Art gilt,
    welche Felder sie hat und was ihr heutiger Wert ist, sagt
    :func:`app.core.perceive.actions.actions_for` — eine Stelle, nicht zwei.
    Ein Panel, das ``kind == "hole"`` fragte, führte dieselbe Tabelle ein
    zweites Mal und wüsste beim nächsten neuen Merkmal die Hälfte.

    Nicht anwendbare Handlungen werden ausgeblendet. Eine vorübergehend
    gesperrte Eingabe behält dagegen ihre Werte und die sichtbare Rückmeldung.
    """

    #: Registername und Parameter — dieselbe Form, die der Operationsdialog
    #: nach außen gibt, damit das Fenster beide gleich behandelt.
    operationRequested = Signal(str, dict)
    #: Dieselbe Handlung für **mehrere** gleichartige Merkmale, in einer
    #: Transaktion — Registername, Werte, und die Kennungen, für die sie gilt.
    #:
    #: Sechs Bohrungen auf Ø 5 zu bringen heißt sonst sechsmal derselbe Weg.
    #: Ein Undo nimmt sie zusammen zurück, weil es eine Handlung war (Regel 16).
    operationRequestedForEach = Signal(str, dict, list)
    #: Dieselbe Handlung, aber **im Bild eingestellt** — Registername und die
    #: Werte, die schon feststehen (die Merkmalskennung darunter).
    #:
    #: Getrennt von :attr:`operationRequested`, weil es etwas anderes tut: Das
    #: eine führt aus, das andere öffnet die Flächenplatzierung mit ihren
    #: Maßlinien und Zahlenfeldern. Ein Empfänger, der beides gleich behandelt,
    #: legt beim Zeigen schon einen Schritt an.
    inViewRequested = Signal(str, dict)
    #: *Abbrechen* unter dem Übernehmen: verwirft, was im Bild wartet — der
    #: gezogene Umriss, das am Griff vorgeschlagene Versetzen —, und beendet
    #: die Maße im Bild. Dasselbe wie Escape, nur als Knopf (Robert,
    #: 11.09.2026: „unter dem übernehmen rechts sollte auch noch abbrechen
    #: stehen"). Er steht nur, solange die Maße im Bild stehen
    #: (:meth:`set_measuring`).
    cancelRequested = Signal()
    #: Der Katalog, aus der Fläche heraus. An einer Fläche gilt keine der vier
    #: Merkmalshandlungen — dafür setzen dort fünfundzwanzig Bausteine an, und
    #: der Weg dorthin lag hinter Rechtsklick und Untermenü.
    catalogRequested = Signal()
    #: Dieselbe Form, während noch getippt wird (Robert, 03.09.2026: „eine
    #: live vorschau wäre noch gut").
    #:
    #: **Getrennt vom Ausführen und nicht dasselbe Signal mit einem Schalter.**
    #: Wer zuhört, muss ohne Nachdenken wissen, ob er rechnen oder ändern soll;
    #: ein Empfänger, der beim falschen Signal ausführt, schreibt einen Schritt
    #: in den Verlauf, den niemand ausgelöst hat.
    valuesChanged = Signal(str, dict)
    #: Eine **andere** Handlung ist scharf — Registername und ihre heutigen
    #: Werte. Kein ``valuesChanged``: Ein Klick in ein Feld ändert nichts,
    #: und bis zum 21.09.2026 rechnete das Fenster darauf eine Vorschau mit
    #: unveränderten Zahlen (Band, Abbrechen, an der 360k-Platte 2,6 bis 4,2 s je
    #: Tab). Wer zuhört, bindet den Auftrag der neuen Handlung und entwertet
    #: die Freigabe der alten — gerechnet wird erst bei einem echten Wert.
    handlingArmed = Signal(str, dict)

    stepChangeRequested = Signal(int, dict)
    """Neue Werte für einen Schritt des Verlaufs — die Kennung und die Werte.

    **Nicht `operationRequested`**, und der Unterschied ist der ganze Punkt:
    Ein Baustein, den man an seinen Maßen ändert, ist derselbe Schritt mit
    anderen Zahlen und kein zweiter daneben. Über `operationRequested` stünde
    nach jeder Korrektur ein weiteres Schlüsselloch im Verlauf, an derselben
    Stelle über dem alten."""

    stepRemoveRequested = Signal(int)
    """Diesen Schritt aus dem Verlauf nehmen — der Weg, einen Baustein
    loszuwerden. Seine Merkmale einzeln zu entfernen ließe die übrigen
    stehen; ein Schlüsselloch ohne seinen Schlitz ist ein Loch."""
    fitRequested = Signal(str, object)
    stepEditRequested = Signal(int)
    stepSelectionChanged = Signal()
    sketchRequested = Signal(str, bool)
    """Auf dieser Fläche zeichnen — ``True`` heißt: um auszuschneiden (Befund
    B2). Das Fenster kennt Körper und Ebene; das Panel nennt nur die Fläche."""
    protectionToggled = Signal(str, bool)
    """Dieses Merkmal als Sichtfläche sperren oder freigeben (§22.3, RM-080).

    **Keine Operation und kein ``operationRequested``**: Die Sperre schreibt
    nichts in den Verlauf, sie sagt der Trennebenensuche, wo keine Naht hin
    darf, und sie steht im Dokument. Wer sie über den Operationsweg schickte,
    legte einen Schritt an, den es nicht gibt."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows = QVBoxLayout(self)
        self._rows.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        self._rows.setSpacing(TIGHT)
        # Der leere Zustand ist ein Satz und keine leere Fläche: Wer nichts
        # gewählt hat, soll lesen, was ihn hierher bringt (§2.7).
        self._empty = QLabel(
            # Fläche, Kante, Bohrung: die drei, an denen rechts etwas steht
            # (RM-506). Die Kante fehlte, obwohl Verrunden und Fase dort ansetzen.
            tr(
                "Kein Merkmal gewählt. Klicken Sie eine Fläche, eine Kante oder eine "
                "Bohrung an — im Objektbaum oder im Bild."
            ),
            self,
        )
        self._empty.setWordWrap(True)
        # Eine Bildunterschrift, keine Überschrift (RM-510): Sie erklärt den
        # Weg und tritt hinter die Handlungen darunter zurück.
        set_level(self._empty, "caption")
        fit_wrapped(self._empty)
        self._rows.addWidget(self._empty)
        self._say_nothing_is_chosen = True
        """Ob der leere Satz stehen darf — das Fenster entscheidet es."""
        self._hint_retired = False
        """Ob die Anleitung ausgedient hat (:meth:`retire_hint`)."""
        self._print_host: QVBoxLayout | None = None
        """Der Abschnitt außerhalb, in dem der Nahtschutz steht — oder keiner."""
        # **Der Restplatz gehört nach unten, nicht zwischen die Handlungen.**
        # Das Panel steckt in einem Rollbereich mit ``setWidgetResizable``, wird
        # also auf dessen Höhe gezogen. Ohne diese Dehnung verteilt Qt den
        # Überschuss auf die Zeilen: In einem 1255 Punkte hohen Fenster wollte
        # der Inhalt 581 und stand am Ende 179 Punkte je Handlung auseinander —
        # vier Knöpfe, zwischen denen so viel Luft steht, dass die Felder
        # darüber nicht mehr erkennbar zu ihnen gehören. Gemessen am
        # 03.09.2026, sichtbar erst im Bildschirmfoto eines hohen Fensters.
        # **Der eine Knopf, und er steht unten.** Dort, wo eine Handlung endet:
        # oben die Werte, unten das Tun — dieselbe Anordnung wie in jedem
        # Dialog. Die Akzentfarbe kommt aus ``make_primary`` und mit ihr die
        # Schriftfarbe darauf (``on_highlight`` im Stylesheet); halbfett steht
        # daneben, damit die Bedeutung nicht allein an der Farbe hängt
        # (Regel 18).
        #
        # **Und sie steht nicht im Rollinhalt** (13.09.2026). Gemessen am
        # gebauten Fenster bei 1600 auf 1000 Punkten an einer gewählten Bohrung: Das
        # Sichtfeld des Rollbereichs war 877 Punkte hoch, sein Inhalt 1579 —
        # *Im Bild einstellen* lag bei y = 1015, *Übernehmen* bei y = 1062,
        # beide unter dem Rand. Wer im obersten Block eine Zahl tippte, sah
        # keinen Knopf, der sie übernimmt. Die Zeile liegt deshalb in einem
        # eigenen Widget, das der Träger **unter** den Rollbereich hängen kann
        # (:meth:`footer`); wo niemand sie nimmt, bleibt sie unten im Panel.
        self._footer = QWidget(self)
        below = QVBoxLayout(self._footer)
        below.setContentsMargins(0, 0, 0, 0)
        below.setSpacing(TIGHT)
        # Der Sperrgrund steht **über** allem, was er sperrt: Wer von unten
        # nach oben liest, findet ihn am Knopf, der nicht geht (Regel 18 —
        # die zweite Kodierung neben dem grauen Knopf ist dieser Satz).
        self._lock_note = QLabel("", self._footer)
        self._lock_note.setWordWrap(True)
        self._lock_note.setVisible(False)
        fit_wrapped(self._lock_note)
        below.addWidget(self._lock_note)
        self._locked = ""
        """Warum Felder und Knöpfe gerade nichts annehmen — oder leer.

        Gesetzt vom Fenster über :meth:`set_locked`, aus derselben Auskunft,
        mit der es Menü, Werkzeugzeile und Befehlspalette sperrt."""
        self._apply_blocked_reason: str | None = None
        self.preview_check: Callable[[], bool] | None = None
        self.preview_defer: Callable[[], None] | None = None
        """Ein Klick auf *Übernehmen* vor der Vorschau wartet auf sie — das
        Fenster hängt den Haken ein (``MainWindow._apply_when_previewed``)."""
        # **Die Reihenfolge ist eine Aussage:** Titel, der Weg ins Bild, der
        # Haken, das Übernehmen, das Verwerfen. Der Haken gehört unmittelbar
        # über den Knopf, dessen Umfang er ändert — ein Knopf dazwischen machte
        # aus „für alle" eine Frage, auf die zwei Knöpfe antworten.
        self._armed_title = QLabel("", self._footer)
        self._armed_title.setWordWrap(True)
        self._armed_title.hide()
        below.addWidget(self._armed_title)
        # **Der Knopf heißt „Übernehmen"** (Robert, 10.09.2026: „als text
        # brauchen wir auch nur übernehmen"). Welche Handlung er meint, steht
        # über ihm — die Überschrift, deren Felder gerade angefasst wurden —
        # und in seinem Tooltip; auf dem Knopf selbst wechselte der Text mit
        # jedem Klick ins nächste Feld und war damit unruhiger als hilfreich.
        # **Und daneben der Weg ins Bild** (Robert, 11.09.2026: „das über den
        # viewport wieder über einen button aktivieren"). Er steht nur an
        # Handlungen, die eine Stelle auf einer Fläche haben, und er führt
        # nichts aus: Er bringt die Maßlinien zu Kanten und Mitten in die
        # Szene, wo sich die Stelle einstellen lässt. Bis zum 11.09.2026 tat
        # das der Übernehmen-Knopf selbst — und damit gab es an einer Bohrung
        # keinen Weg mehr, einfach zu übernehmen.
        self._in_view = QPushButton(tr("Im Bild einstellen"), self._footer)
        self._in_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._in_view.clicked.connect(self._show_armed_in_view)
        self._in_view.setVisible(False)
        below.addWidget(self._in_view)
        self._every = QCheckBox("", self._footer)
        self._every.setVisible(False)
        self._every.toggled.connect(self._group_changed)
        below.addWidget(self._every)
        self._apply = make_primary(QPushButton(tr("Übernehmen"), self._footer))
        self._apply.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply.clicked.connect(self._run_armed)
        self._apply.setVisible(False)
        below.addWidget(self._apply)
        self._cancel = make_danger(QPushButton(tr("Abbrechen"), self._footer))
        self._cancel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._cancel.setToolTip(tr("Verwirft, was im Bild wartet — gerechnet wird nichts."))
        self._cancel.clicked.connect(self.cancelRequested)
        self._cancel.setVisible(False)
        below.addWidget(self._cancel)
        self._rows.addWidget(self._footer)
        self._measuring = False
        """Ob die Maße des gezeigten Merkmals gerade im Bild stehen — dann
        trägt die Maßgruppe Übernehmen und Abbrechen, und die Knöpfe hier
        unten gehen mit (``set_measuring``)."""
        self._measure_op: str | None = None
        """Welche Handlung im Bild steht — ihr Block rechts geht mit (RM-199)."""
        self._measure_begun = False
        """Ob die Maßgruppe schon einen Zug oder eine Zahl gesehen hat — dann
        sind auch die übrigen Handlungen gesperrt, bis sie endet."""
        self._cancel_offered = False
        """Ob eine Vorschau aus diesem Panel wartet — dann steht *Abbrechen*
        neben dem Übernehmen und verwirft sie (:meth:`offer_cancel`)."""
        self._rows.addStretch(1)
        self._built: list[QWidget] = []
        self._serial = 0
        self._feature_id: str | None = None
        self._part_operation: int | None = None
        self._groups: dict[str, FeatureActionGroup] = {}
        self._into_view: Callable[[], None] | None = None
        """Der Weg ins Bild für das gezeigte Merkmal — oder nichts.

        Gehört dem Merkmal und nicht der scharfen Handlung; siehe
        :meth:`_settle_in_view`."""
        self._in_view_key: str | None = None
        """Zu welcher Handlung er gehört — sie wird beim Klick scharf."""
        self._said_notes: set[str] = set()
        """Welche Gruppenbegründungen in diesem Panel schon stehen.

        Sie gehört der **Gruppe** und nicht der einzelnen Handlung: Vier
        Handlungen an derselben Bohrungskette tragen dieselben Nachweise, und
        damit stand derselbe Absatz an einer Senkung viermal untereinander
        (Befund Robert, 07.09.2026). Geleert wird sie in :meth:`clear`, und
        das genügt — ``show_feature`` beginnt damit.
        """
        self._fit_button: QPushButton | None = None
        self._fit_choice: QComboBox | None = None
        self._fit_reason = ""
        self._runs: dict[str, _Handling] = {}
        self._answers: _RememberedAnswers = (_nothing, None, {})
        """Die gemerkte Kernauskunft des gezeigten Körpers (:meth:`_answers_for`)."""
        self._shown_rows: dict[QWidget, _ActionRow] = {}
        """Je gezeigter Handlungszeile ihr Inhalt — die Quelle der Wiederverwendung."""
        self._spare_rows: dict[tuple[Any, ...], list[_ActionRow]] = {}
        """Zeilen des vorigen Merkmals, die auf eine gleichartige Handlung warten (RM-204)."""
        self._measure_groups: dict[int, _MeasureGroup] = {}
        """Die ausgegebenen Maßgruppen, je Kästchen — die Quelle der Rückgabe."""
        self._spare_measures: dict[tuple[Any, ...], _MeasureGroup] = {}
        """Zurückgegebene Maßgruppen, die auf eine gleichartige Handlung warten (RM-232).

        Sie warten ohne Elternteil, so wie sie ausgegeben werden — und gehen
        deshalb nicht von selbst mit dem Fenster. ``destroyed`` nimmt sie mit;
        der Empfänger hält nur das Wörterbuch, nicht das Fenster."""
        self.destroyed.connect(partial(_discard_spare_measures, self._spare_measures))
        self._rows_reused = False
        """Ob der laufende Aufbau eine Zeile wiederverwendet hat — dann zieht
        :meth:`_settle_tab_order` die Fokuskette neu."""
        self._keyed: list[QWidget] = []
        """Jedes Bedienelement mit ``handlingKey`` — die Liste, die
        :meth:`_settle_lock` durchgeht, statt je Aufbau alle Kinder jeder Zeile
        zu suchen (13 ms je Auswahlwechsel an sechs Handlungen, 21.09.2026)."""
        self._blocks: dict[str, tuple[QWidget | None, QWidget]] = {}
        """Je Handlungsschlüssel ihr Strich und ihre Zeile — was weggeht, solange
        ihre Maße im Bild stehen (:meth:`set_measuring`, RM-199)."""
        self._texture_fields: dict[str, Any] = {}
        self._part_fields: dict[str, Any] = {}
        """Das Parameterschema des gezeigten Bausteins — für gebundene Werte.

        Steht an einer Achse ein Ausdruck (``=@staerke``), braucht das Feld
        den Schemaeintrag, aus dem der Operationsdialog sein ``ValueField``
        baut. Ohne ihn endete ``float("=@staerke")`` den Aufbau mitten in der
        Liste: Das Beispielprojekt bindet die Höhe jedes Bausteins, und rechts
        standen danach nur *Maße ändern* — ohne Verschieben und ohne Entfernen
        (Robert, 16.09.2026: „bei manchen bausteinen keine möglichkeit zum
        verschieben")."""
        self._parameter_values: dict[str, float] = {}
        """Je Handlung ihr Titel, ihr Satz und was sie tut.

        Die Knöpfe je Handlung sind am 10.09.2026 gefallen; was bleibt, ist
        **einer** unten, und der braucht die Handlungen als Nachschlagewerk."""
        self._armed_by_tab = False
        """Ob das laufende Scharfschalten von Tab oder Umschalt+Tab kommt.

        Nur während ``_arm`` aus einem ``FocusIn`` gesetzt (:meth:`armed_by_tab`)."""
        self._armed: str | None = None
        """Welche Handlung der Knopf unten gerade meint.

        Die zuletzt angefasste: Wer einen Wert ändert oder in ein Feld klickt,
        hat damit gesagt, worum es geht. Vorbelegt ist die erste — ein Knopf
        ohne Bedeutung wäre schlechter als eine Vorgabe, die dasteht."""
        self._dots: dict[int, tuple[QToolButton, QLabel]] = {}
        """Je Handlungsbox ihr Info-Zeichen und die Überschrift daneben."""
        self._explanations: dict[int, str] = {}
        """Der Text hinter dem Info-Zeichen einer Handlung, nach ``id(box)``.

        Zwei Quellen speisen ihn — der Satz der Handlung und der Nachweis ihrer
        Gruppe —, und sie kommen an verschiedenen Stellen an."""

    @property
    def feature_id(self) -> str | None:
        """Welches Merkmal hier gerade steht — für den, der prüfen muss, ob es
        das noch gibt."""
        return self._feature_id

    @property
    def serial(self) -> int:
        """Wie oft das Fenster geleert wurde — ein Aufbaustand für Vergleiche.

        Wer wissen will, ob seit seinem letzten Aufbau jemand anderes das
        Fenster neu gefüllt hat, vergleicht diese Zahl, statt Inhalte zu lesen.
        """
        return self._serial

    def clear(self, *, rebuilding: bool = False) -> None:
        """Zurück auf den leeren Zustand.

        Versteckt und gelöscht, nicht elternlos gemacht: ``setParent(None)``
        macht aus einem Kind-Widget ein eigenes Fenster, bis der Löschauftrag
        die Ereignisschleife erreicht (RM-101, dieselbe Stelle wie in
        :meth:`ReportPanel._show_offers`).

        ``rebuilding`` sagt, dass gleich wieder Handlungen kommen und der
        Aufbau mit :meth:`_settle_apply` endet: Dann bleibt die Knopfzeile
        stehen, bis dort feststeht, was sie zeigt. Ausgeblendet und gleich
        wieder eingeblendet kostete sie je Merkmalklick sechs Wechsel im
        sichtbaren Fenster, für denselben Stand wie vorher.
        """
        self._serial += 1
        for widget in self._built:
            widget.hide()
            widget.deleteLater()
        self._built.clear()
        self._feature_id = None
        self._part_operation = None
        self._groups = {}
        self._said_notes.clear()
        self._fit_button = None
        self._fit_choice = None
        self._runs.clear()
        self._shown_rows.clear()
        self._rows_reused = False
        self._keyed.clear()
        self._blocks.clear()
        self._texture_fields.clear()
        self._part_fields.clear()
        self._parameter_values.clear()
        self._armed = None
        self._explanations.clear()
        self._dots.clear()
        self._into_view = None
        self._in_view_key = None
        self._every.setChecked(False)
        if rebuilding:
            return
        for widget in (self._apply, self._in_view, self._cancel, self._armed_title):
            _set_shown(widget, False)
        # Der Sperrgrund selbst **bleibt** (``_locked``) — die Kette hält ja
        # weiter an —, nur seine Zeile geht: Über „Kein Merkmal gewählt …"
        # stünde eine Absage auf eine Frage, die niemand gestellt hat. Der
        # nächste Aufbau bringt sie zurück (:meth:`_settle_lock`).
        _set_shown(self._lock_note, False)
        _set_shown(self._every, False)
        _set_shown(self._empty, self._say_nothing_is_chosen and not self._hint_retired)

    def retire_hint(self) -> None:
        """Die Anleitung „Kein Merkmal gewählt …“ hat ihren Dienst getan (RM-510).

        Sie steht als Bildunterschrift über den Körperhandlungen, bis der
        Kunde zum ersten Mal ein Merkmal angeklickt hat; danach weiß er, wie
        man an die Maße kommt, und 18 Wörter über jeder Körperauswahl wären
        Tapete. Ob das schon war, merkt sich das Fenster
        (``UiSettings.feature_hint_seen``).
        """
        self._hint_retired = True
        if self._feature_id is None and not self._built:
            self._empty.setVisible(False)

    def say_nothing_is_chosen(self, on: bool) -> None:
        """Ob der leere Zustand seinen Satz trägt — oder die Karte ihn trägt.

        Ohne **jede** Auswahl steht unter diesem Fenster die Handlungskarte
        mit „Nichts gewählt" und „Wählen Sie einen Körper oder eine Fläche —
        Bausteine gehen auch so." Der Satz hier sagte dasselbe ein drittes
        Mal, nur ohne den Weg zu den Bausteinen, der der Grund ist, warum die
        Karte seit dem 18.09.2026 überhaupt stehen bleibt.

        Bei gewähltem **Körper** bleibt er: Dort trägt die Karte die
        Körperhandlungen, und er ist die richtige Auskunft darüber, wie man an
        die Maße kommt.
        """
        self._say_nothing_is_chosen = on
        # **Was dasteht, entscheidet** (RM-269): Eine Kante (``show_edge``) und
        # ein Paar (``show_pair``) sind kein Merkmal, und neben ihnen stand
        # „Kein Merkmal gewählt …“, sobald die Karte danach neu aufgebaut wurde.
        if self._feature_id is None and self._part_operation is None and not self._built:
            self._empty.setVisible(on and not self._hint_retired)

    def show_feature(
        self,
        feature_id: str,
        feature: Feature,
        *,
        features: Mapping[str, Feature] | None = None,
        mesh: MeshData | None = None,
        alone: bool = False,
        protected: bool = False,
    ) -> None:
        """Die Handlungen dieses Merkmals als Zeilen — Reihenfolge aus dem Kern.

        ``alone`` sagt, dass dieser Körper der einzige im Projekt ist: Dann gibt
        es kein Gegenstück, und der Satz über die Passung entfällt.
        ``protected`` ist der heutige Stand des Umschalters *Vor Trennnähten
        schützen* — aus dem Dokument, nicht aus dem Bild.

        Gleichartige Merkmale werden je Handlung durch den Kern belegt:
        Eine Maßänderung braucht andere Übereinstimmungen als das Versetzen
        einer ganzen Bohrungskette. ``mesh``
        belegt die topologische Kette einer mehrteiligen Senkung; optional bleibt
        es für Aufrufer, die nur die einzelne Merkmalsauskunft brauchen.
        """
        answers = self._answers_for(feature_id, feature, features, mesh)
        self._keep_rows_for_reuse()
        try:
            self._show_feature_rows(
                feature_id,
                feature,
                features=features,
                mesh=mesh,
                alone=alone,
                protected=protected,
                answers=answers,
            )
        finally:
            self._drop_spare_rows()
        self._settle_apply()

    def _answers_for(
        self,
        feature_id: str,
        feature: Feature,
        features: Mapping[str, Feature] | None,
        mesh: MeshData | None,
    ) -> _FeatureAnswers:
        """Was der Kern über dieses Merkmal sagt — einmal je Merkmal und Auswertung.

        Hohlraumkette, Handlungen und gleichartige Geschwister sind reine
        Funktionen von Körper und Merkmalen (Regel 3: eine Auswertung ändert
        niemand). Bis zum 22.09.2026 fragte jeder Klick sie neu — am Halter
        mit Wabenmuster 22 ms je Bohrung allein für ``actions_for``, weil die
        Einlaufprüfung das Netz je Aufruf verschweißt und einen Suchbaum baut.
        Wer zwischen Bohrungen hin- und herklickt, bekommt jetzt die Antwort
        vom ersten Mal. Gemerkt wird für **einen** Körper und **eine**
        Merkmalsliste; ein anderer Körper oder eine neue Auswertung beginnt
        von vorn, und der Körper wird nur schwach gehalten. Gerechnet wird in
        :func:`feature_answers`; an einem großen Körper tut das der Arbeiter
        des Fensters, und seine Antwort liegt hier schon, wenn der Aufbau
        kommt (:meth:`remember_answers`, RM-232).
        """
        known = self.known_answers(feature_id, feature, features, mesh)
        if known is not None:
            return known
        answers = feature_answers(feature_id, feature, features, mesh)
        if features is not None and mesh is not None:
            self.remember_answers(feature_id, feature, features, mesh, answers)
        return answers

    def known_answers(
        self,
        feature_id: str,
        feature: Feature,
        features: Mapping[str, Feature] | None,
        mesh: MeshData | None,
    ) -> _FeatureAnswers | None:
        """Die gemerkte Antwort des Kerns zu diesem Merkmal — ``None``, wenn es keine gibt."""
        if features is None or mesh is None:
            return None
        body, listed, known = self._answers
        if body() is not mesh.raw or listed is not features:
            return None
        cached = known.get(feature_id)
        return cached[1] if cached is not None and cached[0] is feature else None

    def remember_answers(
        self,
        feature_id: str,
        feature: Feature,
        features: Mapping[str, Feature],
        mesh: MeshData,
        answers: _FeatureAnswers,
    ) -> None:
        """Eine Antwort des Kerns für diesen Körper und diese Merkmalsliste merken."""
        body, listed, known = self._answers
        if body() is not mesh.raw or listed is not features:
            known = {}
            self._answers = (weakref.ref(mesh.raw), features, known)
        known[feature_id] = (feature, answers)

    def show_pending(self, feature_id: str, feature: Feature) -> None:
        """Name und Maß des Merkmals, solange seine Handlungen noch ermittelt werden.

        Der Kern antwortet an einem großen Körper im Arbeiter (RM-232); bis
        dahin steht, was schon feststeht, und ein Satz, dass der Rest kommt.
        Eine Zeile zum Klicken gibt es in diesem Zustand nicht — was sie
        anböte, weiß noch niemand.

        **Das Merkmal steht trotzdem schon hier** (:attr:`feature_id`). Ohne
        es galt das Fenster als leer: Ein ``say_nothing_is_chosen`` aus einem
        Aufbau der Menüeinträge in dieser Zeit stellte „Kein Merkmal gewählt"
        unter den Namen des gewählten Merkmals, und die Prüfung nach einer
        neuen Auswertung (``MainWindow._show_scene``) übersah ein Merkmal,
        das es nicht mehr gibt.
        """
        self.clear()
        self._feature_id = feature_id
        _set_shown(self._empty, False)
        heading = QLabel(
            f"{cavity_name(feature_id, feature, ())}  ·  {feature_measure(feature, compact=True)}"
        )
        heading.setWordWrap(True)
        fit_wrapped(heading)
        set_level(heading, "section")
        self._rows.insertWidget(self._rows.count() - 1, heading)
        self._built.append(heading)
        self.show_note(tr("Die Handlungen werden ermittelt …"))

    def _show_unit(self, unit: FunctionalGroup, name: str) -> None:
        """Die Gruppe, zu der das Merkmal gehört: Name, Nachweis, gemessene Maße.

        Dateiaudit §7 (RM-184): Wer eine Wand der Kammer anklickt, soll lesen,
        dass sie zu „Kammer 1“ gehört und woran Solidon das erkannt hat — ein
        Verdacht sagt, dass er einer ist. Die Maße sind gemessen, nicht
        vorgegeben; ändern lässt sich die Gruppe über die Handlung darunter,
        wo es eine gibt (*Kammer ändern*).
        """
        from app.core.perceive.groups import evidence_texts, measure_titles

        box = QWidget(self)
        form = QFormLayout(box)
        form.setContentsMargins(0, 0, 0, 0)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        said = evidence_texts()[unit.evidence]
        if unit.suggested:
            said = tr("{sentence} Ein Verdacht, kein Befund.", sentence=said)
        heading = QLabel(tr("Teil von {group}", group=name), box)
        heading.setWordWrap(True)
        set_level(heading, "section")
        reason = QLabel(said, box)
        reason.setWordWrap(True)
        fit_wrapped(reason)
        form.addRow(heading)
        form.addRow(reason)
        titles = measure_titles()
        for measure in unit.measures:
            label = titles.get(measure.name, measure.name)
            field = QLabel(group_measure_text(measure), box)
            field.setAccessibleName(label)
            form.addRow(label, field)
        box.setAccessibleName(tr("Teil von {group}", group=name))
        box.setAccessibleDescription(said)
        self._rows.insertWidget(self._rows.count() - 1, box)
        self._built.append(box)

    def _show_feature_rows(
        self,
        feature_id: str,
        feature: Feature,
        *,
        features: Mapping[str, Feature] | None,
        mesh: MeshData | None,
        alone: bool,
        protected: bool,
        answers: _FeatureAnswers,
    ) -> None:
        """Der Aufbau hinter :meth:`show_feature` — mit zurückgehaltenen Zeilen."""
        from app.core.perceive import relations

        cavity = answers.cavity
        self.clear(rebuilding=True)
        self._feature_id = feature_id
        _set_shown(self._empty, False)

        # **Die Herkunft nur, wenn sie warnt** (RM-510): „gemessen“ hinter jedem
        # Maß ist keine Auskunft, „eingepasst“ schon (``measure_qualifier`` mit
        # ``compact``). Woher die Zahl kommt, sagt der Tooltip jedes Mal.
        measure = feature_measure(feature, compact=True)
        name = cavity_name(feature_id, feature, cavity)
        # **An einer Bohrung nennt der Satz darunter das Maß** (RM-516):
        # „Bohrungsmaß: 5,20 mm (eingepasst). Passt vermutlich zu M5“ — im
        # Kopf davor stand derselbe Durchmesser samt Herkunft schon einmal.
        said_below = (
            feature.kind == "hole"
            and feature.params.get("diameter") is not None
            and measure_status(feature, "diameter").available
        )
        heading = QLabel(name if said_below else f"{name}  ·  {measure}")
        hint = feature_measure_tip(feature)
        heading.setToolTip(hint)
        heading.setAccessibleDescription(hint)
        heading.setWordWrap(True)
        fit_wrapped(heading)
        set_level(heading, "section")
        self._rows.insertWidget(self._rows.count() - 1, heading)
        self._built.append(heading)

        if features is not None:
            sleeve = relations.sleeve_at(feature, features)
            if sleeve is not None:
                box = QWidget(self)
                form = QFormLayout(box)
                form.setContentsMargins(0, 0, 0, 0)
                form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
                for label, value in (
                    (tr("Innendurchmesser"), sleeve.bore_diameter),
                    (tr("Außendurchmesser"), sleeve.outer_diameter),
                    (tr("Wandstärke"), sleeve.thickness),
                ):
                    field = QLabel(length(value), box)
                    field.setAccessibleName(label)
                    form.addRow(label, field)
                self._rows.insertWidget(self._rows.count() - 1, box)
                self._built.append(box)

        if answers.unit is not None:
            self._show_unit(answers.unit, answers.unit_name)

        # **Ein Gegenstück gibt es nur neben einem zweiten Körper.** Im
        # Einzelkörperprojekt wies der Satz auf einen Klick, der nichts findet.
        if not alone:
            # Qt bildet Control für die jeweilige Plattform ab; die sichtbare
            # Taste kommt aus QKeySequence statt aus einem festen Windows-Text.
            key = (
                QKeySequence("Ctrl+A")
                .toString(QKeySequence.SequenceFormat.NativeText)[:-1]
                .rstrip("+")
            )
            self.show_note(
                tr(
                    "Für eine Passung ein Gegenstück mit {key} und Klick im Objektbaum hinzuwählen."
                ).format(key=key)
            )

        # **Was die Anwendung über diese Bohrung weiß, sagt sie hier.**
        # ``bore_advice`` steht seit je im Bohrdialog und beantwortet die
        # Frage, die der Kunde vor jedem Druck stellt: „ist das eine M5?"
        # Gemessen hat Solidon den Durchmesser ohnehin — ihn zu zeigen und die
        # Antwort zu verschweigen wäre die halbe Auskunft.
        diameter = feature.params.get("diameter")
        if feature.kind == "hole" and diameter is not None:
            from app.core.scene.placement import bore_advice

            said, _choices = bore_advice(
                float(diameter),
                ask=False,
                measured=length(float(diameter)),
                feature=feature,
                features=features,
                mesh=mesh,
                cavity=cavity,
            )
            note = QLabel(said, self)
            note.setWordWrap(True)
            fit_wrapped(note)
            self._rows.insertWidget(self._rows.count() - 1, note)
            self._built.append(note)

        actions = answers.actions
        self._groups = dict(answers.groups)
        # Unpassende Aktionen belegen keine Zeile. Der Kern behält ihre
        # Gründe für andere Aufrufer; das Panel zeigt die verfügbaren Wege.
        for action in _folded(actions):
            if action.op is None and getattr(action, "step", None) is None:
                continue
            line = self._separate()
            row = self._build_action(action)
            self._rows.insertWidget(self._rows.count() - 1, row)
            self._built.append(row)
            self._blocks[next(reversed(self._runs))] = (line, row)

        # **Eine Öffnung, an der nichts geht, sagt warum** (Durchsicht 0.5.1).
        # Am Laptop-Ständer lehnt der Kern an 13 von 28 Bohrungen jede
        # Handlung mit demselben Satz ab („In dieser Bohrung steht Material
        # …“); das Fenster zeigte Name, Maß und *Baustein einsetzen …*, und
        # der Kunde wartete auf Maße im Bild, die nie kamen. An einer Bohrung
        # ist der Grund eine Auskunft; an Kante und Fläche bleibt es bei der
        # Regel oben, dort sagt der Katalog darunter, was geht.
        if feature.kind in ("hole", "slot", "cone") and not any(
            action.op is not None or getattr(action, "step", None) is not None for action in actions
        ):
            for reason in dict.fromkeys(str(action.reason) for action in actions if action.reason):
                self.show_note(reason)

        if feature.kind == "face":
            self._build_sketch_entries(feature_id)

        # **Wo nichts gilt, steht der Weg, der gilt.** An einer Fläche ist
        # jede der vier Handlungen abgelehnt — dort setzen dafür
        # fünfundzwanzig Bausteine an, und der Katalog lag hinter Rechtsklick
        # und Untermenü. Ein Panel aus vier grauen Zeilen ist eine Sackgasse
        # mit Begründung; eine Sackgasse bleibt es trotzdem.
        # **Nicht an einer Fläche**: Dort steht unter diesem Fenster der Knopf
        # *Bausteine* zum selben Katalog, und zwei Knöpfe mit einem Ziel sind
        # eine Frage ohne Antwort (RM-510).
        if not any(action.op for action in actions) and feature.kind != "face":
            catalog = QPushButton(tr("Baustein einsetzen …"), self)
            opens = tr("Öffnet den Katalog — Bohrung, Mutternfalle, Magnettasche und die übrigen.")
            catalog.setToolTip(opens)
            catalog.setAccessibleDescription(opens)
            catalog.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            catalog.clicked.connect(lambda _checked=False: self.catalogRequested.emit())
            self._rows.insertWidget(self._rows.count() - 1, catalog)
            self._built.append(catalog)
        self._build_protection(feature_id, feature, protected)

    def _build_sketch_entries(self, feature_id: str) -> None:
        """Zwei Zeilen an jeder ebenen Fläche: *Hier zeichnen* und *Loch oder
        Aussparung zeichnen …* (Bedienabnahme Zeichnen, B2 und S2).

        §2.6 verspricht im Auswahlfenster den kürzesten Weg vom Sehen zum Tun,
        und an einer Fläche stand dort nur „Baustein einsetzen …". Wer hier ein
        Loch in einer eigenen Form wollte, musste wissen, dass *Zeichnen* oben
        in der Werkzeugzeile auf der gewählten Fläche beginnt.
        """
        for text, tip, cut in (
            (
                tr("Hier zeichnen"),
                tr("Beginnt eine Zeichnung auf dieser Fläche, für diesen Körper."),
                False,
            ),
            (
                tr("Loch oder Aussparung zeichnen …"),
                tr("Zeichnen Sie den Umriss; Fertig schneidet ihn aus diesem Körper."),
                True,
            ),
        ):
            button = QPushButton(text, self)
            button.setToolTip(tip)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(
                lambda _checked=False, chosen=cut: self.sketchRequested.emit(feature_id, chosen)
            )
            self._rows.insertWidget(self._rows.count() - 1, button)
            self._built.append(button)

    def _build_protection(self, feature_id: str, feature: Feature, protected: bool) -> None:
        """Der Umschalter *Vor Trennnähten schützen* — die eine Kundengeste der
        Trennen-Serie (T8): „Diese Fläche soll schön bleiben."

        **Unten, nach den Handlungen**, weil er keine ist: Die Zeilen darüber
        ändern das Teil, dieser Haken sagt der Suche von *Automatisch teilen*,
        wo sie nicht schneiden darf. Ob das Merkmal sich sperren lässt und was
        auf dem Haken steht, sagt der Kern (:func:`protection_of`); ein Merkmal
        ohne schützbare Fläche bekommt diesen Schalter nicht.
        """
        from app.core.perceive.actions import protection_of

        protection = protection_of(feature)
        if not protection.possible:
            return
        if self._print_host is None:
            self._separate()
        toggle = QCheckBox(str(protection.title), self)
        toggle.setObjectName("protection-toggle")
        toggle.setAccessibleName(str(protection.title))
        toggle.setChecked(protected)
        toggle.setEnabled(protection.possible)
        toggle.setToolTip(str(protection.explanation))
        toggle.setAccessibleDescription(str(protection.explanation))
        toggle.toggled.connect(lambda on: self.protectionToggled.emit(feature_id, bool(on)))
        # **Zugeklappt unter den Handlungen** (RM-510), wo das Fenster einen
        # Abschnitt „Filament und Druck“ anbietet (:meth:`set_print_host`);
        # geräumt wird er mit dem Merkmal wie jede andere Zeile.
        if self._print_host is not None:
            self._print_host.addWidget(toggle)
        else:
            self._rows.insertWidget(self._rows.count() - 1, toggle)
        self._built.append(toggle)

    def set_print_host(self, rows: QVBoxLayout) -> None:
        """Wohin der Nahtschutz kommt — der Abschnitt „Filament und Druck“ darunter."""
        self._print_host = rows

    def protection_toggle(self) -> QCheckBox | None:
        """Der Umschalter des gezeigten Merkmals, oder ``None`` ohne Merkmal."""
        for widget in self._built:
            if isinstance(widget, QCheckBox) and widget.objectName() == "protection-toggle":
                return widget
        return None

    def show_part(
        self,
        operation: Any,
        spec: Any,
        *,
        title: str = "",
        parameter_values: Mapping[str, float] | None = None,
    ) -> None:
        """Was sich an diesem **Baustein** ändern lässt — an seinem Schritt.

        Ein Schlüsselloch besteht aus zwölf Merkmalen: zwei Bohrungen, zehn
        Verrundungen und der Fläche, auf der es sitzt. Wer eines davon
        anklickt, hat das Schlüsselloch gemeint; die Verrundung trägt für sich
        gar keine Handlung, und an der Fläche standen die Handlungen einer
        Fläche (Befund Robert, 10.09.2026).

        Die Werte kommen aus dem Schritt und gehen dorthin zurück
        (:func:`~app.core.perceive.actions.part_actions`) — gemessene Maße
        ließen sich nicht verlustfrei zurückschreiben: Aus zwei Durchmessern
        käme keine Schraubengröße zurück.
        """
        from app.core.perceive.actions import part_actions

        self.clear(rebuilding=True)
        self._feature_id = None
        # **Woran die Live-Vorschau erkennt, dass sie einen Schritt meint.**
        # Ohne ihn baute sie aus denselben Werten einen *neuen* Baustein und
        # zeigte beim Drehen an der Schraubengröße ein zweites Schlüsselloch
        # an der Vorgabelage — der Fehler, den der Knopf daneben schon
        # vermeidet (``stepChangeRequested``).
        self._part_operation = int(operation.id)
        # Das Schema des Bausteins, damit ein gebundener Wert sein
        # Ausdrucksfeld bekommt (:meth:`_build_field`).
        self._part_fields = {entry.name: entry for entry in spec.params.spec()}
        self._parameter_values = dict(parameter_values or {})
        _set_shown(self._empty, False)

        heading = QLabel(title or str(spec.title), self)
        heading.setWordWrap(True)
        fit_wrapped(heading)
        set_level(heading, "section")
        self._rows.insertWidget(self._rows.count() - 1, heading)
        self._built.append(heading)

        for action in part_actions(operation, spec):
            self._separate()
            row = self._build_action(action)
            self._rows.insertWidget(self._rows.count() - 1, row)
            self._built.append(row)
        self._settle_apply()

    def offer_bore_step(
        self, operation: Any, spec: Any, parameter_values: Mapping[str, float]
    ) -> None:
        """Belegte Originalmaße zusätzlich zu den gemessenen Merkmalsmaßen anbieten."""
        from app.core.perceive.actions import bore_action

        self._part_fields = {entry.name: entry for entry in spec.params.spec()}
        self._parameter_values = dict(parameter_values)
        line = self._separate()
        row = self._build_action(bore_action(operation, spec))
        self._rows.insertWidget(self._rows.count() - 1, row)
        self._built.append(row)
        # Auch dieser Block steht nicht rechts, solange seine Maße im Bild
        # stehen (RM-199): Ohne den Eintrag blieb „Bohrung im ursprünglichen
        # Schritt ändern" mit vier gesperrten Feldern neben der Maßgruppe.
        self._blocks[next(reversed(self._runs))] = (line, row)
        self._arm(next(reversed(self._runs)))
        self._settle_apply()

    def arm_action(self, op: str) -> bool:
        """Diese Handlung scharfschalten — wenn das Merkmal sie anbietet.

        Für das Hauptfenster, das nach einem Übernehmen die Maße zurück ins
        Bild holt: Ein Langloch aus einem ``slot_hole``-Schritt bekommt sie
        an *Zum Langloch ziehen*, nicht an der ersten Handlung mit Weg ins Bild.
        """
        found = next((key for key, entry in self._runs.items() if entry.op == op), None)
        if found is None:
            return False
        self._arm(found)
        return True

    def step_for_action(self, op: str) -> int | None:
        """Die Herkunft gehört der Handlung, nicht allen Feldern derselben Karte."""
        entry = next((entry for entry in self._runs.values() if entry.op == op), None)
        return getattr(entry.action, "step", None) if entry is not None else None

    def offer_texture_steps(
        self,
        operations: Sequence[Any],
        parameter_values: Mapping[str, float],
        *,
        document: Document | None = None,
    ) -> None:
        """Ungewisse Texturzuordnungen ergänzen die normalen Flächenhandlungen."""
        button = QPushButton(tr("Textur am Körper wählen …"), self)
        button.clicked.connect(
            lambda: self.show_texture(
                operations, certain=False, parameter_values=parameter_values, document=document
            )
        )
        self._rows.insertWidget(self._rows.count() - 1, button)
        self._built.append(button)

    def show_texture(
        self,
        operations: Sequence[Any],
        *,
        selected: int | None = None,
        certain: bool = True,
        parameter_values: Mapping[str, float] | None = None,
        document: Document | None = None,
    ) -> None:
        """Texturparameter bearbeiten den vorhandenen Schritt mit derselben Vorschau."""
        from app.core.perceive.actions import texture_actions

        self.stepSelectionChanged.emit()
        self.clear()
        self._empty.hide()
        self._parameter_values = dict(parameter_values or {})
        spec = REGISTRY.get("apply_texture")
        if selected is None and certain and len(operations) == 1:
            selected = int(operations[0].id)
        if len(operations) > 1 or not certain:
            choice = column_choice(QComboBox(self))
            choice.setObjectName("texture-step-choice")
            choice.setAccessibleName(tr("Textur bearbeiten"))
            choice.addItem(tr("Textur am Körper wählen …"), userData=None)
            for operation in operations:
                choice.addItem(
                    tr("Textur aus Operation {number}").format(
                        number=step_number(document, operation.id)
                    ),
                    userData=int(operation.id),
                )
            choice.setCurrentIndex(max(0, choice.findData(selected)))
            choice.currentIndexChanged.connect(
                lambda: self.show_texture(
                    operations,
                    selected=choice.currentData(),
                    certain=certain,
                    parameter_values=parameter_values,
                    document=document,
                )
            )
            self._rows.insertWidget(self._rows.count() - 1, choice)
            self._built.append(choice)
        operation = next((item for item in operations if item.id == selected), None)
        if operation is None:
            return
        self._part_operation = int(operation.id)
        self._texture_fields = {
            entry.name: entry for entry in spec.params.spec() if entry.kind in {"float", "int"}
        }
        for action in texture_actions(operation, spec):
            row = self._build_action(action)
            self._rows.insertWidget(self._rows.count() - 1, row)
            self._built.append(row)
        details = QPushButton(tr("Weitere Einstellungen …"), self)
        self._mark(details, "texture-details")
        details.clicked.connect(lambda: self.stepEditRequested.emit(int(operation.id)))
        self._rows.insertWidget(self._rows.count() - 1, details)
        self._built.append(details)
        self._settle_apply()
        if (entered := self.preview_values()) is not None:
            self.valuesChanged.emit(*entered)

    def show_edge(
        self,
        key: str,
        title: str,
        *,
        parameter_values: Mapping[str, float] | None = None,
    ) -> None:
        """Was sich an dieser **Kante** tun lässt — verrunden und fasen.

        Eine Kante ist kein Merkmal: Sie trägt keine Kennung, die die
        Erkennung vergibt, und steht in keinem ``applies_to``. Ihre zwei
        Handlungen kommen deshalb aus einer eigenen Auskunft des Kerns
        (:func:`~app.core.perceive.actions.edge_actions`) — und aus dem Kern
        und nicht von hier, aus demselben Grund wie bei den Merkmalen: Welche
        Operation an einer Kante ansetzt, ist eine Aussage über Geometrie.

        ``title`` ist die Zeile, die der Kunde schon aus der Kantenliste des
        Dialogs kennt („Senkrecht · 20 mm · x -20,0, y -15,0"). Der Schlüssel
        dahinter steht nirgends im Fenster: Er ist eine Kennung aus sechs
        Zahlen und keine Beschriftung (§2.4).

        **Die Zahlenfelder sind die des Dialogs** (P6.2): ``ValueField`` mit
        derselben Einheit, denselben Grenzen und dem Umschalter für einen
        Ausdruck (``=@breite``), gerechnet mit ``parameter_values``. Eine Fase
        mit zwei Abständen ist ein Maß, das man an einen Projektparameter
        hängen will — im Dialog ging das, an der angeklickten Kante bis dahin
        nicht. Die Felder, die von einer Auswahl abhängen (zweiter Abstand,
        Winkel, Seitentausch), stehen nur da, solange sie gelten
        (:meth:`_follow_conditions`).
        """
        from app.core.perceive.actions import edge_actions

        self._keep_rows_for_reuse()
        try:
            self.clear(rebuilding=True)
            self._feature_id = None
            self._parameter_values = dict(parameter_values or {})
            _set_shown(self._empty, False)

            heading = QLabel(title, self)
            heading.setWordWrap(True)
            fit_wrapped(heading)
            set_level(heading, "section")
            self._rows.insertWidget(self._rows.count() - 1, heading)
            self._built.append(heading)

            for action in edge_actions(key):
                self._separate()
                # Die Ausdrucksfelder gelten je Zeile: *Verrunden* und *Wulst
                # anlegen* führen beide einen ``radius`` mit eigener Vorgabe,
                # eigenen Grenzen und eigenem Satz — ein gemeinsames
                # Verzeichnis gäbe dem einen die Beschreibung des anderen.
                self._texture_fields = {
                    entry.name: entry
                    for entry in REGISTRY.get(str(action.op)).params.spec()
                    if entry.kind == "float"
                }
                row = self._build_action(action)
                self._rows.insertWidget(self._rows.count() - 1, row)
                self._built.append(row)
        finally:
            self._texture_fields = {}
            self._drop_spare_rows()
        self._settle_apply()

    def shown_part_step(self) -> int | None:
        """Der Schritt, dessen Baustein gerade dasteht — sonst ``None``.

        Die Live-Vorschau fragt danach: Bei einem Baustein wird der vorhandene
        Schritt mit neuen Werten gerechnet (``change_op``), sonst ein Entwurf
        neben der Szene. Beides aus denselben Werten zu bauen zeigte ein
        zweites Schlüsselloch an der Vorgabelage, während man an der
        Schraubengröße drehte.
        """
        return self._part_operation

    def show_pair(self, first_id: str, first: Feature, second_id: str, second: Feature) -> None:
        """Wie weit zwei gewählte Merkmale auseinanderstehen.

        Robert am 03.09.2026, als er das Merkmalsfenster ausgebaut haben
        wollte: der Abstand zweier Bohrungen ist das, was man vor jedem Druck
        wissen will. Bis dahin ging das nur über das Messwerkzeug und zwei
        Klicks ins Bild — zwei Zeilen im Baum anzuklicken ist der kürzere Weg,
        und markiert hat man sie ohnehin schon.

        Diese Abstandsauskunft verändert weder Geometrie noch Verlauf (Regel 2).
        Der Aufrufer kann darunter eine passende Prüfbeziehung anbieten;
        deren ausdrückliche Anlage läuft getrennt über die Sitzung.

        Gezeigt werden der räumliche Abstand und die drei Achsabstände
        einzeln — die Mitte-zu-Mitte-Strecke beantwortet „passt der Schlüssel
        dazwischen", die Achsabstände „wie weit muss ich die Schablone
        schieben".
        """
        self.clear()
        _set_shown(self._empty, False)

        heading = QLabel(
            f"{feature_name(first_id, first)}  →  {feature_name(second_id, second)}", self
        )
        heading.setWordWrap(True)
        fit_wrapped(heading)
        set_level(heading, "section")
        self._rows.insertWidget(self._rows.count() - 1, heading)
        self._built.append(heading)

        here = first.params.get("centre")
        there = second.params.get("centre")
        if here is None or there is None or len(here) != 3 or len(there) != 3:
            # Ein Merkmal ohne gemessene Mitte hat keinen Abstand — und ein
            # erfundener wäre schlimmer als keiner.
            note = QLabel(tr("Für diese beiden ist kein Abstand gemessen."), self)
            note.setWordWrap(True)
            fit_wrapped(note)
            self._rows.insertWidget(self._rows.count() - 1, note)
            self._built.append(note)
            return

        gap = tuple(float(there[axis]) - float(here[axis]) for axis in range(3))
        straight = math.sqrt(sum(value * value for value in gap))
        rows = [
            (tr("Abstand"), straight),
            (tr("in X"), gap[0]),
            (tr("in Y"), gap[1]),
            (tr("in Z"), gap[2]),
        ]
        box = QWidget(self)
        form = QFormLayout(box)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(TIGHT)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        for label, value in rows:
            # Über ``length`` und nicht als rohe Zahl: außen die Anzeigeeinheit,
            # innen Millimeter — sonst stünde bei Zoll eine Millimeterzahl da.
            form.addRow(QLabel(label, box), QLabel(length(value), box))
        self._rows.insertWidget(self._rows.count() - 1, box)
        self._built.append(box)

    def show_note(self, text: str) -> None:
        """Ein sichtbarer, umgebrochener Hinweis im aktuellen Merkmalsbereich."""
        note = QLabel(text, self)
        note.setWordWrap(True)
        note.setAccessibleDescription(text)
        fit_wrapped(note)
        self._rows.insertWidget(self._rows.count() - 1, note)
        self._built.append(note)

    def show_fit_choices(self, choices: Mapping[str, str], token: object) -> None:
        """Kerngeprüfte Arten und ihre Sollauskunft; nur der ausdrückliche Klick schreibt."""
        box = QWidget(self)
        form = QFormLayout(box)
        form.setContentsMargins(0, 0, 0, 0)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        choice = column_choice(QComboBox(box))
        choice.setAccessibleName(tr("Passungsart"))
        if len(choices) > 1:
            choice.addItem(tr("Passungsart wählen …"), "")
        for kind in choices:
            choice.addItem(choice_label(kind), kind)
        explain_choices(choice)
        form.addRow(tr("Passungsart"), choice)
        target = QLabel(box)
        target.setWordWrap(True)
        target.setAccessibleName(tr("Sollmaß"))
        fit_wrapped(target)
        form.addRow(target)
        button = QPushButton(tr("Passung anlegen"), box)
        button.setAccessibleDescription(
            tr("Speichert die Prüfbeziehung. Rückgängig entfernt sie wieder.")
        )
        make_primary(button)
        form.addRow(button)
        self._fit_button = button
        self._fit_choice = choice

        def changed() -> None:
            kind = str(choice.currentData() or "")
            text = choices.get(kind, "")
            note = choice_note(kind) or ""
            if note:
                text = f"{note}\n{text}"
            for widget in (choice, form.labelForField(choice)):
                if widget is not None:
                    widget.setToolTip(note)
                    widget.setAccessibleDescription(note)
            target.setText(text)
            self.limit_fit(self._fit_reason)

        choice.currentIndexChanged.connect(changed)

        def requested() -> None:
            button.setEnabled(False)
            self.fitRequested.emit(str(choice.currentData()), token)

        button.clicked.connect(requested)
        self._rows.insertWidget(self._rows.count() - 1, box)
        self._built.append(box)
        changed()

    def limit_fit(self, reason: str) -> None:
        """Nur den schreibenden Passungsknopf sperren, seine Auskunft bleibt sichtbar."""
        self._fit_reason = reason
        if self._fit_button is not None and self._fit_choice is not None:
            chosen = bool(self._fit_choice.currentData())
            note = reason or ("" if chosen else tr("Wählen Sie die gewünschte Passungsart."))
            self._fit_button.setEnabled(not reason and chosen)
            self._fit_button.setToolTip(note)
            self._fit_button.setAccessibleDescription(
                note or tr("Speichert die Prüfbeziehung. Rückgängig entfernt sie wieder.")
            )

    def set_locked(self, reason: str) -> None:
        """Warum hier gerade nichts angenommen wird — oder leer für „es geht".

        **Dasselbe Wort wie an Menü, Werkzeugzeile und Befehlspalette**
        (`MainWindow._update_actions`). Hält die Kette an einem Schritt an,
        nimmt die Sitzung keinen neuen dahinter an (§15.3); bis zum 13.09.2026
        blieben Felder und Knöpfe hier trotzdem bedienbar, und der Versuch
        endete in einem modalen „Das hat so nicht funktioniert" — die
        Sackgasse, die Regel 19 meint. Der Grund steht jetzt **vorher** da.

        Zwei Kodierungen, wie überall (Regel 18): die Knöpfe sind grau, und
        derselbe Satz steht als Zeile darüber — dazu in Kurzhilfe und
        zugänglicher Beschreibung.
        """
        self._locked = reason
        self._settle_lock()

    def block_apply(self, reason: str | None) -> None:
        """Sperrt nur Übernehmen; Werte und Abbrechen bleiben erreichbar."""
        self._apply_blocked_reason = reason
        self._settle_apply_block()

    def can_accept(self) -> bool:
        """Ob die aktuelle Handlung mit den aktuellen Werten übernommen werden darf."""
        if self._locked or not self._apply_stands() or self._armed not in self._runs:
            return False
        current = self.preview_check is None or self.preview_check()
        return current and self._apply_allowed()

    def preview_values(self) -> tuple[str, dict[str, Any]] | None:
        """Die aktive Handlung aus derselben Wertequelle wie ihre Übernahme lesen."""
        entry = self._runs.get(self._armed or "")
        if entry is None or entry.op == NO_OPERATION:
            return None
        return entry.op, entry.values()

    def _apply_allowed(self) -> bool:
        """Die lokalen Sperren ohne erneuten Aufruf des Vorschauverwalters prüfen."""
        return (
            not self._locked
            and self._apply_blocked_reason is None
            and self._apply_stands()
            and self._armed in self._runs
            and not self._active_field_refusal()
        )

    def _settle_apply_block(self) -> None:
        """Hält Sperrgrund und Auskunft am gemeinsamen Übernehmen zusammen."""
        reason = self._locked or self._apply_blocked_reason
        field_refusal = self._active_field_refusal()
        control_reason = field_refusal or reason
        self._apply.setEnabled(self._apply_allowed())
        self._lock_note.setText(control_reason or "")
        _set_shown(self._lock_note, bool(control_reason) and bool(self._built))
        if control_reason:
            self._apply.setToolTip(control_reason)
            self._apply.setAccessibleDescription(control_reason)
        elif (entry := self._runs.get(self._armed or "")) is not None:
            self._apply.setToolTip(entry.title)
            self._apply.setAccessibleDescription(entry.reason)

    def _active_field_refusal(self) -> str:
        """Die erste sichtbare Grenzablehnung der scharfgestellten Handlung — mit dem Feld.

        Der Satz steht auch am Fußknopf, weit unter der Zeile; ohne Feldnamen
        musste man suchen, welches der Felder gemeint war (RM-342, D-N2).
        """
        row = next(
            (row for row in self._shown_rows.values() if row.key == self._armed),
            None,
        )
        if row is None:
            return ""
        from app.ui.op_dialog import ValueField

        for field in row.entries:
            editor = row.widgets.get(str(field.name))
            if editor is None or editor.isHidden() or not editor.isEnabled():
                continue
            reason = (
                editor.refusal()
                if isinstance(editor, ValueField | BoundedSpin | BoundedLengthSpin)
                else ""
            )
            if reason:
                name = editor.accessibleName() or str(field.label)
                return str(tr("{name}: {value}", name=name, value=reason))
        return ""

    def _set_refusal_label(self, editor: BoundedSpin | BoundedLengthSpin, label: QLabel) -> str:
        """Zeigt die Grenzablehnung direkt am Feld und reicht sie an Vorleser weiter."""
        reason = editor.refusal()
        if label.text() != reason:
            label.setText(reason)
            if reason:
                fit_wrapped(label)
        label.setToolTip(reason)
        label.setAccessibleDescription(reason)
        _set_shown(label, bool(reason))
        description = (
            f"{editor.toolTip()}\n{reason}"
            if reason and editor.toolTip()
            else (reason or editor.toolTip())
        )
        editor.setAccessibleDescription(description)
        return reason

    def _refresh_row_refusal(
        self,
        editor: BoundedSpin | BoundedLengthSpin,
        label: QLabel,
        row: _ActionRow,
        *_ignored: object,
    ) -> None:
        """Aktualisiert Fehlertext und Freigabe schon während der Eingabe."""
        self._set_refusal_label(editor, label)
        self._arm(row.key)
        self._settle_apply_block()

    def _refresh_measure_refusal(
        self, editor: BoundedSpin | BoundedLengthSpin, label: QLabel, *_ignored: object
    ) -> None:
        """Aktualisiert die Rückmeldung einer Maßgruppe im Bild."""
        self._set_refusal_label(editor, label)

    def _settle_lock(self) -> None:
        """Sperrt oder gibt frei, was der gemeldete Grund gerade zulässt.

        Aufgerufen aus :meth:`set_locked` und am Ende jedes Aufbaus
        (:meth:`_settle_apply`): Die Zeilen entstehen neu, der Grund bleibt —
        wer ein anderes Merkmal anklickt, während die Kette hält, bekäme sonst
        ein bedienbares Panel.

        Der Passungsknopf gehört :meth:`limit_fit` und bleibt hier
        unangetastet; zwei Stellen, die denselben Knopf schalten, gewinnen
        abwechselnd.
        """
        reason = self._locked
        for child in self._keyed:
            if not isValid(child):
                continue
            entry = self._runs.get(child.property("handlingKey"))
            in_measure = self._measuring and (
                self._measure_begun or (entry is not None and entry.op == self._measure_op)
            )
            child.setEnabled(not reason and not in_measure)
        for button in (self._in_view, self._apply, self._cancel):
            button.setEnabled(not reason)
        self._every.setEnabled(not reason and not self._measuring)
        self._lock_note.setText(reason)
        # Ohne Zeilen gibt es nichts, was der Satz erklären könnte: Über dem
        # leeren Zustand („Kein Merkmal gewählt …") stünde eine Absage auf
        # eine Frage, die niemand gestellt hat.
        _set_shown(self._lock_note, bool(reason) and bool(self._built))
        if reason:
            for button in (self._in_view, self._apply, self._cancel):
                button.setToolTip(reason)
                button.setAccessibleDescription(reason)
            return
        # **Der Weg zurück ohne Neuauswahl** (Robert, 11.09.2026, für die
        # Installationsknöpfe: überholte Sperrgründe werden verworfen). Nach
        # einem Strg+Z rechnet die Kette wieder, und dann tragen die Knöpfe
        # wieder ihre eigene Auskunft statt der Absage von vorhin.
        self._cancel.setToolTip(tr("Verwirft, was im Bild wartet — gerechnet wird nichts."))
        self._cancel.setAccessibleDescription(self._cancel.toolTip())
        self._settle_in_view()
        if self._armed is not None:
            self._arm(self._armed)
        else:
            self._settle_apply_block()
        if self._measuring:
            # Der Titel gehört zum Knopf darunter: ohne ihn stünde er allein.
            for widget in (
                self._in_view,
                self._apply,
                self._cancel,
                self._every,
                self._armed_title,
            ):
                _set_shown(widget, False)

    def _build_action(self, action: Any) -> QWidget:
        """Eine Handlung: Titel, ihre Felder untereinander, dann ihr Knopf.

        **Untereinander und nicht nebeneinander** (Robert, 03.09.2026: „auch
        auf die Größen achten, war viel abgeschnitten"). Eine Zeile aus
        Beschriftung, drei Zahlenfeldern und einem Knopf braucht rund
        fünfhundert Bildpunkte; die linke Spalte hat halb so viel, und was
        nicht passt, schneidet Qt ab — aus *Merkmal verschieben* wurde „zmal
        versch". Ein Formularlayout stellt die Beschriftung neben ihr Feld und
        bricht die Spalte um, statt sie zu beschneiden, und der Knopf steht
        darunter über die ganze Breite.

        **Eine Zeile, die schon steht, wird wiederverwendet** (RM-204). Bis zum
        22.09.2026 leerte jeder Merkmalklick das Fenster und baute jede Zeile
        neu — an einer Bohrung fünf Handlungen mit achtzehn Feldern, rund
        vierzehn Millisekunden je Klick allein für Widgets, deren Aufbau sich
        nicht geändert hatte. Dieselbe Handlung mit denselben Feldern
        (:meth:`_row_signature`) behält jetzt ihre Zeile; neu geschrieben
        werden Werte, Grenzen, Beschriftungen und Erklärung
        (:func:`configure_feature_field`), und die Signale gehen dabei nicht
        nach außen.
        """
        step = getattr(action, "step", None)
        if action.op is None and step is None:
            box = QWidget(self)
            layout = QVBoxLayout(box)
            layout.setContentsMargins(0, 0, 0, TIGHT)
            layout.setSpacing(TIGHT)
            # Titel und Grund in **einer** umbrechenden Zeile: Der Grund ist
            # ein Satz, und ein Satz gehört nicht in eine Formularspalte.
            name = QLabel(f"{action.title} — {action.reason}", box)
            name.setWordWrap(True)
            name.setAccessibleDescription(str(action.reason))
            fit_wrapped(name)
            layout.addWidget(name)
            return box

        signature = self._row_signature(action)
        spare = self._spare_rows.get(signature) if signature is not None else None
        if spare:
            row = spare.pop(0)
            self._rows_reused = True
            _set_shown(row.box, True)
            for field in action.fields:
                configure_feature_field(row.widgets[str(field.name)], field)
        else:
            row = self._new_row(action, signature)
        # **Der Schlüssel ist die Zeile, nicht die Operation.** Ein Baustein
        # bietet *Maße ändern*, *verschieben* und *entfernen* an, und zwei
        # davon tragen gar keine Operation (der Schritt ist die Handlung);
        # unter ``str(action.op)`` hießen beide „None" und die letzte
        # überschrieb die vorige — im Panel stand danach eine Handlung von
        # dreien.
        key = f"{len(self._runs)}|{action.op}"
        row.key = key
        row.op = str(action.op)
        row.action = action
        row.entries = tuple(action.fields)
        row.fixed = tuple(getattr(action, "fixed", ()))
        row.step = step
        self._fill_row(row, action)
        self._follow_conditions(row)
        self._shown_rows[row.box] = row
        box = row.box

        # **Der Haken steht nur da, wo es Geschwister gibt.** „Auf alle 1
        # anwenden" wäre eine Frage ohne Unterschied; ab dem zweiten
        # gleichartigen Merkmal spart er fünf Wege.
        #
        # **Und er steht unten, direkt über dem Knopf** (Robert, 10.09.2026:
        # „alle 4 gleichzeitig dann auch vor dem übernehmen"). Er gehört zur
        # Handlung, die gerade scharf ist — dieselbe Bewegung wie beim Knopf,
        # und aus demselben Grund: Vier gleich beschriftete Haken untereinander
        # sagen nicht, welcher welchen Zug meint.
        group = self._groups.get(str(action.op))
        if group is not None and (len(group.members) > 1 or group.uncertain):
            said = _feature_group_note(group)
            # **Derselbe Absatz steht einmal, nicht viermal.** Die Nachweise
            # gehören der Gruppe, und vier Handlungen an derselben
            # Bohrungskette haben dieselben: An einer Senkung standen
            # „Die Achsen sind parallel ausgerichtet." und die drei Sätze
            # daneben viermal untereinander, einmal je Handlung (Befund
            # Robert, 07.09.2026). Dasselbe Muster wie :func:`_folded` eine
            # Ebene höher — dort für den Grund einer Absage, hier für den
            # Nachweis einer Gruppe.
            #
            # **Weggelassen wird die Auskunft nicht, nur ihre Wiederholung.**
            # Der Haken trägt sie weiter, und zwar dort, wo sie gilt: Er ist
            # das Feld, über das sie entscheidet. Ohne das verlöre ein
            # Screenreader sie an jeder Handlung außer der ersten.
            #
            # **Und die Zusage bleibt dabei stehen.** Der Nachweis wird der
            # Statuszeile angehängt statt sie zu ersetzen, und er steht
            # hinten: Die Zeile ist eine Zeile, und was abgeschnitten wird,
            # darf nicht das Strg+Z sein — gerade diese Zusage erlaubt es, auf
            # eine Rückfrage zu verzichten (Regel 19). Ersetzt trugen zwei
            # gleich beschriftete Haken im selben Panel Verschiedenes.
            #
            # **Ohne Haken bleibt der Absatz stehen.** Eine einelementige
            # unsichere Gruppe hat kein Feld, das die Auskunft tragen könnte;
            # dort ist eine Wiederholung besser als ein Verlust.
            if said and said not in self._said_notes:
                # **Der Absatz sitzt am Info-Zeichen** — derselbe Grund wie bei
                # ``action.note`` darüber, und dasselbe Zeichen: Wer die
                # Überschrift überfliegt, sieht einen Kreis mit „i" und weiß,
                # dass es dazu etwas zu lesen gibt. Einmal, nicht viermal: Die
                # Nachweise gehören der **Gruppe**, und vier Handlungen an
                # derselben Bohrungskette haben dieselben (Befund Robert,
                # 07.09.2026).
                self._said_notes.add(said)
                self._extend_explanation(box, said)

        op_name = str(action.op)
        # **Ein Knopf unten statt einer je Handlung** (Robert, 10.09.2026: „die
        # ganzen buttons um werte zu übernehmen durch einen unten ersetzen,
        # damit wir bisschen platz sparen"). Fünf Knöpfe untereinander
        # kosteten fünf Zeilen und sagten fünfmal dasselbe: „tu das hier".
        # Was der eine unten tut, entscheidet die Handlung, an der zuletzt
        # jemand etwas angefasst hat — und sein Text nennt sie beim Namen,
        # damit niemand raten muss (:meth:`_arm`). Die Wege lesen ihre Felder
        # aus der Zeile, damit eine wiederverwendete Zeile nicht die Felder
        # des vorigen Merkmals meint.
        members = len(group.members) if group is not None else 0
        self._runs[key] = _Handling(
            title=str(action.title),
            reason=str(action.reason) or str(action.title),
            run=partial(self._run_row, row),
            take=partial(self._take_row, row),
            in_view=(
                partial(self._row_in_view, row)
                if step is None and _leads_into_the_view(op_name)
                else None
            ),
            op=op_name,
            members=members,
            values=partial(self._row_values, row),
            action=action,
        )
        if self._armed is None:
            self._arm(key)

        # **Einen Knopf ins Bild gibt es nicht mehr** (Robert, 10.09.2026: „im
        # panel rechts können wir uns den button im bild einstellen sparen, da
        # wir das sofort können … steht mehrmals da"). Er stand an jeder
        # Handlung, die auf einer Fläche sitzt — an einer Bohrung also
        # mehrfach untereinander —, und was er anbot, geschieht seit demselben
        # Tag von selbst: Ein angeklicktes Loch bringt seine Maße mitsamt
        # Maßlinien in die Szene (`MainWindow._measure_in_the_view`). Ein
        # zweiter Weg zu etwas, das schon läuft, ist kein Angebot, sondern
        # Platz, den die Zeilen darunter brauchen.
        #
        # **Was hier kein Feld hat, bekommt seinen Weg** (Befund Robert,
        # 18.09.2026). Eine Fachaufteilung ist ein Sammelparameter mit eigenem
        # Editor; sie steht in ``action.elsewhere`` und nicht als Zahlenfeld.
        # Ohne diesen Knopf trug eine Organizer-Trennwand drei Außenmaße, und
        # die Fächer — die Sache, um die es geht — waren von dort nicht zu
        # erreichen. Eine solche Zeile wird nie wiederverwendet
        # (:meth:`_row_signature`), der Knopf entsteht also mit ihr.
        elsewhere = tuple(getattr(action, "elsewhere", ()))
        if elsewhere and step is not None:
            named = ", ".join(str(entry) for entry in elsewhere)
            deeper = QPushButton(tr("{fields} ändern …").replace("{fields}", named), box)
            self._mark(deeper, f"{key}|elsewhere")
            deeper.setToolTip(tr("Öffnet den vollständigen Dialog dieses Schritts."))
            deeper.setAccessibleDescription(deeper.toolTip())
            deeper.clicked.connect(weak_slot(self, FeaturePanel._ask_for_the_step, int(step)))
            holder = box.layout()
            assert holder is not None, "jede Handlungszeile trägt ihr Layout"
            holder.addWidget(deeper)
            self._built.append(deeper)
        return box

    def _row_signature(self, action: Any) -> tuple[Any, ...] | None:
        """Woran eine Zeile erkennt, dass sie eine andere Handlung tragen kann — oder ``None``.

        Dieselbe Operation mit denselben Feldern in derselben Reihenfolge, von
        derselben Art und mit denselben Auswahlwerten: Dann unterscheiden
        sich zwei Handlungen nur in ihren Werten, und die schreibt
        :func:`configure_feature_field` neu. Nicht wiederverwendet wird, was
        mehr trägt als Werte — ein Schritt (Baustein, historische Bohrung),
        ein Weg in den vollständigen Dialog, ein Ausdrucksfeld mit gebundenem
        Wert; die entstehen je Anzeige neu wie bisher.
        """
        if getattr(action, "step", None) is not None or tuple(getattr(action, "elsewhere", ())):
            return None
        fields: list[tuple[Any, ...]] = []
        for field in action.fields:
            if _expression_entry(field, self._texture_fields, self._part_fields) is not None:
                return None
            choices = tuple((value, str(text)) for value, text in field.choices or ())
            fields.append((str(field.name), str(field.kind), choices))
        return (str(action.op), tuple(fields))

    def _new_row(self, action: Any, signature: tuple[Any, ...] | None) -> _ActionRow:
        """Baut die Widgets einer Handlungszeile — Werte schreibt :meth:`_fill_row`."""
        box = QWidget(self)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, TIGHT)
        layout.setSpacing(TIGHT)
        row = _ActionRow(box=box, signature=signature)
        if action.fields:
            # **Die Gruppe sagt selbst, wozu sie gehört.** Bis hierher benannte
            # sie nur der Knopf **darunter**, und das trägt genau einmal: Beim
            # ersten Feldpaar liest man die Bedeutung noch von unten nach, beim
            # zweiten nicht mehr. An einer Bohrung stehen vier Gruppen
            # untereinander — X/Y/Z für *Verschieben*, ein Durchmesser für
            # *Ändern*, Achse und Winkel für *Drehen*, wieder X/Y/Z für
            # *Verdoppeln* —, und der Kunde sieht zweimal dieselben drei Felder
            # ohne erkennbaren Unterschied (Bildschirmfoto eines Kunden, gemessen
            # von 3d-druck-4d am 04.09.2026).
            #
            # Die Überschrift wiederholt den Knopftext, und das ist Absicht: Sie
            # beantwortet „wozu sind diese Felder", er „und jetzt ausführen".
            # Zwei verschiedene Wörter dafür wären zwei Namen für eine Handlung.
            #
            # **Und sie ist der Umschalter eines Akkordeons** (RM-510): An einer
            # Bohrung standen sechs Handlungen mit allen Feldern zugleich offen,
            # 1579 Punkte Inhalt in 877 sichtbaren. Offen ist genau eine, und
            # zwar die, die der Knopf unten übernimmt (:meth:`_arm`) — zwei
            # Regeln wären zwei Wahrheiten über dieselbe Frage. Zugeklappt nennt
            # die Zeile darunter ihre Werte (:meth:`_summarise`).
            #
            # Der Umschalter ist ein Pfeil **vor** dem Titel, nicht der Titel
            # selbst: Ein Knopf bricht nicht um, und ein langer Titel machte die
            # Spalte sonst breiter als die Karte (RM-488). Titel und Wertezeile
            # öffnen per Klick ebenso.
            toggle = QToolButton(box)
            toggle.setObjectName("actionHeading")
            toggle.setCheckable(True)
            toggle.setAutoRaise(True)
            toggle.setArrowType(Qt.ArrowType.RightArrow)
            toggle.setAccessibleName(str(action.title))
            toggle.toggled.connect(weak_slot(self, FeaturePanel._row_toggled, row, forward=True))
            row.toggle = toggle
            group_title = _RowTitle(str(action.title), toggle, box)
            group_title.setWordWrap(True)
            set_level(group_title, "caption")
            fit_wrapped(group_title)
            # **Die Erklärung steht an der Überschrift, nicht unter ihr.** Drei
            # Zeilen Fließtext je Handlung füllten das Fenster, und an einer
            # Bohrung stehen vier davon (Robert, 10.09.2026: „die beschreibungen
            # die über den buttons zum übernehmen dastehen auch in einen
            # tooltipp passen bei der überschrift von den werten mit einem i für
            # infos"). Weg ist sie damit nicht: Der Tooltip trägt sie, und
            # ``setAccessibleDescription`` reicht sie an
            # den Bildschirmleser weiter — Qt liest einen Tooltip nicht von
            # selbst vor.
            head = QHBoxLayout()
            head.setContentsMargins(0, 0, 0, 0)
            head.setSpacing(TIGHT)
            head.addWidget(toggle)
            head.addWidget(group_title, 1)
            row.title = group_title
            row.dot = self._explain(box, head)
            layout.addLayout(head)
            summary = _RowSummary(toggle, box)
            summary.setVisible(False)
            row.summary = summary
            layout.addWidget(summary)

            body = QWidget(box)
            body.setVisible(False)
            row.body = body
            form = QFormLayout(body)
            form.setContentsMargins(0, 0, 0, 0)
            form.setSpacing(TIGHT)
            # Bricht um, statt abzuschneiden: Bei schmaler Spalte rutscht das
            # Feld unter seine Beschriftung, und beide bleiben ganz.
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            names = [str(field.name) for field in action.fields]
            pending: list[tuple[QLabel, QWidget]] = []
            waiting: list[QLabel] = []
            for field in action.fields:
                name = str(field.name)
                editor = self._build_field(field, box)
                row.widgets[name] = editor
                row.inner[name] = tuple(editor.findChildren(QLineEdit))
                label = QLabel(str(field.label), box)
                label.setWordWrap(True)
                # **Die Beschriftung gehört an das Feld, nicht nur daneben.**
                # Ein Bildschirmleser liest den Namen des Bedienelements, und
                # der war leer: elf Felder mit „Drehfeld, 0,00" und
                # „Kontrollkästchen, nicht angehakt", darunter zweimal X, Y, Z
                # — einmal für *Merkmal verschieben*, einmal für *verdoppeln*.
                # Wer sie nicht sieht, konnte sie nicht auseinanderhalten
                # (gemessen 09.09.2026 an einer gewählten Bohrung; §19.1).
                #
                # ``setBuddy`` allein genügt nicht: Es hängt den Text an die
                # Beschriftung, damit ihr Kürzel den Fokus setzt, und wird von
                # den Vorlesern unterschiedlich ausgewertet. Der Name am Feld
                # ist die Zusage, die überall trägt (:meth:`_fill_row`).
                label.setBuddy(editor)
                row.labels[name] = label
                # X, Y und Z einer Stelle teilen sich eine Zeile
                # (:class:`_CoordinateRow`); ihre Ablehnungssätze folgen
                # darunter, je an ihrem Feld benannt.
                start = names.index(name) - len(pending)
                together = (
                    names[start : start + len(COORDINATE_FIELDS)] == list(COORDINATE_FIELDS)
                    and name in COORDINATE_FIELDS
                )
                if together:
                    pending.append((label, editor))
                else:
                    form.addRow(label, editor)
                if isinstance(editor, (BoundedSpin, BoundedLengthSpin)):
                    refusal = QLabel(box)
                    refusal.setObjectName(f"feature-field-refusal-{name}")
                    refusal.setWordWrap(True)
                    refusal.setVisible(False)
                    row.refusals[name] = refusal
                    if together:
                        waiting.append(refusal)
                    else:
                        form.addRow(refusal)
                    editor.valueRefused.connect(
                        partial(self._refresh_row_refusal, editor, refusal, row)
                    )
                    editor.lineEdit().textEdited.connect(
                        partial(self._refresh_row_refusal, editor, refusal, row)
                    )
                self._watch(editor, row)
                if isinstance(editor, RowCheckBox):
                    caption_toggles(label, editor)
                if len(pending) == len(COORDINATE_FIELDS):
                    coordinates = _CoordinateRow(pending, box)
                    row.coordinates.append(coordinates)
                    form.addRow(coordinates)
                    for refusal in waiting:
                        form.addRow(refusal)
                    pending, waiting = [], []
            layout.addWidget(body)
        else:
            button = QPushButton(str(action.title), box)
            button.clicked.connect(partial(self._run_row, row))
            layout.addWidget(button)
            row.button = button
        return row

    def _fill_row(self, row: _ActionRow, action: Any) -> None:
        """Was eine Zeile über ihre Handlung sagt — beim Bau und beim Wiederverwenden.

        Beschriftungen, zugängliche Namen, die Erklärung hinter dem
        Info-Zeichen und die Merker, über die Sperre, Fokus und Eingabetaste
        die Handlung finden (:meth:`_mark`). Die Werte der Felder stehen dann
        schon (:func:`configure_feature_field`).
        """
        box = row.box
        if row.title is not None and row.dot is not None:
            row.title.setText(str(action.title))
            # Die Erklärung beginnt leer: Eine wiederverwendete Zeile trug
            # sonst die Absätze des vorigen Merkmals weiter.
            self._dots[id(box)] = (row.dot, row.title)
            self._explanations.pop(id(box), None)
            for widget in (row.dot, row.title):
                widget.setToolTip("")
            row.title.setAccessibleDescription("")
            # Sichtbar bleibt es, wenn gleich ein Text kommt: aus- und wieder
            # einblenden wäre zwei Wechsel im sichtbaren Fenster für nichts.
            _set_shown(row.dot, bool(_explained(action)))
            # **Jede Handlung hat eine Erklärung.** Drei Quellen in dieser
            # Reihenfolge: der Satz zur Lage (``note``, „Bohrung und Senkung
            # gehen gemeinsam"), der Grund der Handlung, und zuletzt der
            # ``doc``-Satz aus dem Register — die Beschreibung, die dieselbe
            # Operation auch im Menü und im Dialog trägt. Ein Zeichen, das nur
            # an einer von fünf Zeilen auftaucht, sieht aus wie ein Fehler und
            # nicht wie ein Angebot (Robert, 11.09.2026: „ist nur hinter
            # material verschieben").
            self._extend_explanation(box, _explained(action))
            for field in action.fields:
                name = str(field.name)
                editor = row.widgets[name]
                label = row.labels[name]
                label.setText(str(field.label))
                label.setToolTip(editor.toolTip())
                label.setAccessibleDescription(editor.accessibleDescription())
                # Die Überschrift der Handlung kommt vor den Feldnamen, weil
                # „Durchmesser" allein nicht sagt, welcher — an einer Bohrung
                # stehen vier Handlungen mit je eigenen Feldern.
                editor.setAccessibleName(f"{action.title} — {field.label}")
                editor.setProperty(FIELD_PROPERTY, name)
                if isinstance(editor, (BoundedSpin, BoundedLengthSpin)):
                    refusal = row.refusals.get(name)
                    if refusal is not None:
                        self._set_refusal_label(editor, refusal)
                for target in (editor, *row.inner[name]):
                    self._mark(target, row.key)
        if row.button is not None:
            row.button.setText(str(action.title))
            row.button.setToolTip(_explained(action))
            # Derselbe Merker wie an den Feldern: Er sagt, wem dieses
            # Bedienelement gehört — und damit auch, dass es mit ihnen gesperrt
            # wird, solange die Kette anhält (:meth:`_settle_lock`).
            self._mark(row.button, row.key)

    def _follow_conditions(self, row: _ActionRow) -> None:
        """Zeigt nur die Felder dieser Zeile, deren Bedingung gerade gilt (P6.2).

        Dieselbe Regel wie im Operationsdialog (``_couple_dependent_fields``)
        und aus derselben Quelle: ``depends_on`` des Parameters, durchgereicht
        über :attr:`~app.core.perceive.actions.ActionField.depends_on`, geprüft
        mit :func:`~app.core.registry.params.inactive_dependency` — auch über
        eine Kette von Bedingungen. Ein Feld, das nicht gilt, verschwindet
        samt Beschriftung; die Fokuskette übergeht es von selbst. Gesperrt
        wird es hier nicht: Sperren gehört :meth:`_settle_lock`, und zwei
        Stellen, die dieselbe Sperre setzen, gewinnen abwechselnd.

        Der Wert bleibt dabei stehen. Wer von „Zwei Abstände" auf „Gleiche
        Breite" und zurück wechselt, findet seinen zweiten Abstand wieder —
        die Operation liest ihn nur, solange er gilt.

        **Und was die Maßgruppe im Bild trägt, verschwindet ebenso**
        (:meth:`_in_the_view`) — mit demselben Weg zurück, sobald das Messen
        endet.
        """
        from app.core.registry.params import inactive_dependency

        conditional = {
            str(field.name): field for field in row.entries if getattr(field, "depends_on", None)
        }
        in_view = self._in_the_view(row)
        touched = set(conditional) | in_view | row.in_view
        row.in_view = in_view
        if not touched:
            return
        values = self._row_values(row) if conditional else {}
        for name in touched:
            editor = row.widgets.get(name)
            label = row.labels.get(name)
            if editor is None:
                continue
            field = conditional.get(name)
            active = name not in in_view and (
                field is None
                or inactive_dependency(cast(Any, field), cast(Any, row.entries), values) is None
            )
            _set_shown(editor, active)
            if label is not None:
                _set_shown(label, active)
            # **Der Ablehnungssatz geht mit seinem Feld** (RM-342 D-N1): Ohne
            # Feld stand „Höchstens 1000 mm“ unter einer Zeile, die es nicht
            # mehr gab. Kommt das Feld zurück, steht der Satz wieder, solange
            # die Zahl abgelehnt bleibt.
            refusal = row.refusals.get(name)
            if refusal is not None:
                _set_shown(refusal, active and bool(refusal.text()))
        for coordinates in row.coordinates:
            coordinates.follow_fields()

    def _in_the_view(self, row: _ActionRow) -> frozenset[str]:
        """Die Felder dieser Zeile, die die Maßgruppe im Bild gerade selbst trägt.

        RM-199 nimmt den Block der Handlung weg, deren Maße im Bild stehen. Ihr
        Zwilling daneben (:data:`LEADS_INTO_THE_VIEW`) trug dieselben Felder
        noch einmal: am Langloch unter *Bohrung ändern* den Durchmesser, den
        die Maßgruppe als Breite führt, an der runden Bohrung unter *Zum
        Langloch ziehen* die Breite, dazu je X, Y, Z und die Materialtoleranz
        (Robert, 24.09.2026: „vor allem mit dem merkmalpanel nebenan"). Was
        der Zwilling allein hat — Länge und Richtung, Tiefe und
        Änderungsumfang —, bleibt stehen; ein Klick hinein holt ihn ins Bild
        (``MainWindow._hand_the_measures_over``).
        """
        op = self._measure_op
        if (
            not self._measuring
            or op is None
            or row.op == op
            or not {row.op, op} <= LEADS_INTO_THE_VIEW
        ):
            return frozenset()
        measured = next((other for other in self._shown_rows.values() if other.op == op), None)
        if measured is None:
            return frozenset()
        return frozenset(row.widgets) & frozenset(measured.widgets)

    def toggle_field(self, op: str, name: str) -> bool:
        """Schaltet einen Haken der Handlung ``op`` um — wie ein Klick auf ihn.

        Der Weg für eine Geste außerhalb des Fensters: Ein Klick auf eine
        Marke der Fase im Bild tauscht die Seiten, und das ist hier der Haken
        *Seiten tauschen*. Über den Haken und nicht an ihm vorbei, damit Knopf,
        Vorschau und Übernehmen denselben Stand lesen wie nach einem Klick
        hier. ``False``, wenn es den Haken gerade nicht gibt oder er nicht
        gilt — dann ist im Bild auch nichts, das ihn tauschen könnte.
        """
        row = next(
            (row for row in self._shown_rows.values() if row.op == op and name in row.widgets),
            None,
        )
        if row is None:
            return False
        editor = row.widgets[name]
        if not isinstance(editor, QCheckBox) or editor.isHidden() or not editor.isEnabled():
            return False
        editor.toggle()
        return True

    def focus_field(self, op: str, name: str) -> bool:
        """Das Feld ``name`` der Handlung ``op`` bekommt den Fokus — wenn es steht.

        Für die Übergabe aus der Maßgruppe im Bild
        (``MainWindow._hand_quiet_placement_to_panel``): Dort verschwindet das
        Feld, in dem getippt wurde, und ohne diesen Weg landete die Tastatur
        auf dem nächsten Knopf der Kette statt auf derselben Zahl hier.
        """
        row = next(
            (row for row in self._shown_rows.values() if row.op == op and name in row.widgets),
            None,
        )
        if row is None:
            return False
        if row.body is not None and row.body.isHidden():
            self._arm(row.key)
        editor = row.widgets[name]
        if not editor.isVisibleTo(self) or not editor.isEnabled():
            return False
        getattr(editor, "spin", editor).setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    def _row_values(self, row: _ActionRow) -> dict[str, Any]:
        """Was in den Feldern dieser Zeile steht — mit dem gezeigten Merkmal."""
        return self._values(row.entries, row.widgets, row.fixed)

    def _run_row(self, row: _ActionRow, _checked: bool = False) -> None:
        """Führt die Handlung dieser Zeile aus — mit ihren heutigen Feldern.

        **Ein Baustein ändert seinen Schritt, er legt keinen zweiten an.**
        Ohne diese Weiche stünde nach jeder Maßkorrektur ein weiteres
        Schlüsselloch im Verlauf, an derselben Stelle über dem alten.
        """
        if row.step is not None:
            if row.action is not None and row.action.op is None:
                self.stepRemoveRequested.emit(row.step)
            else:
                self.stepChangeRequested.emit(row.step, self._row_values(row))
            return
        self._emit(row.op, row.entries, row.widgets, self._every_for(row.op), row.fixed)

    def _take_row(self, row: _ActionRow, proposed: Mapping[str, Any]) -> None:
        """Vorgeschlagene Zahlen in die Felder dieser Zeile.

        Ohne Meldung nach außen: Die Zahlen kommen aus dem Bild, und die
        Vorschau dort zeigt sie bereits. Ein ``valuesChanged`` von hier
        liefe zurück zu dem, der gerade gezogen hat.
        """
        refresh_feature_fields(row.entries, row.widgets, proposed)

    def _row_in_view(self, row: _ActionRow) -> None:
        """Dieselbe Handlung, aber im Bild eingestellt.

        **Ein eigener Knopf, seit dem 11.09.2026.** Bis dahin führte das
        *Übernehmen* selbst ins Bild, wo die Handlung eine Stelle hat — und
        damit konnte man an einer Bohrung nichts mehr übernehmen, ohne vorher
        durch die Platzierung zu gehen. Zwei Absichten brauchen zwei Knöpfe
        (Robert, 11.09.2026: „das über den viewport wieder über einen button
        aktivieren").
        """
        self.inViewRequested.emit(row.op, self._row_values(row))

    def _keep_rows_for_reuse(self) -> None:
        """Hält die Zeilen der gezeigten Handlungen für den nächsten Aufbau zurück (RM-204).

        Vor :meth:`clear` gerufen: Was wiederverwendbar ist, verlässt die
        Liste der gebauten Widgets und wird nicht gelöscht, sondern wartet
        unter seiner Signatur. Der Aufbau danach nimmt es wieder
        (:meth:`_build_action`); was keiner nimmt, räumt
        :meth:`_drop_spare_rows` ab.
        """
        self._drop_spare_rows()
        kept = {box for box, row in self._shown_rows.items() if row.signature is not None}
        for box in kept:
            row = self._shown_rows[box]
            assert row.signature is not None
            self._spare_rows.setdefault(row.signature, []).append(row)
            # Aus dem Layout, nicht aus dem Fenster: Die Zeile behält Eltern
            # und Sichtbarkeit und kommt an ihrer neuen Stelle wieder hinein.
            self._rows.removeWidget(box)
        # In der Reihenfolge des Fensters, damit eine Signatur mit zwei Zeilen
        # sie wieder in derselben Folge vergibt.
        for rows in self._spare_rows.values():
            rows.sort(key=lambda row: self._built.index(row.box))
        self._built = [widget for widget in self._built if widget not in kept]

    def _drop_spare_rows(self) -> None:
        """Zurückgehaltene Zeilen, die kein Aufbau genommen hat, gehen wie jede andere."""
        for rows in self._spare_rows.values():
            for row in rows:
                row.box.hide()
                row.box.deleteLater()
        self._spare_rows.clear()

    def _settle_row_order(self) -> None:
        """Die Tabulatortaste geht auch über wiederverwendete Zeilen den Weg des Auges.

        Qt führt die Fokuskette in der Reihenfolge, in der Widgets entstanden
        sind. Eine wiederverwendete Zeile ist älter als die neuen daneben, und
        ohne diese Kette spränge der Fokus von ihr zu Zeilen, die im Fenster
        über ihr stehen. Gezogen wird deshalb einmal von oben nach unten durch
        alle Halte der gezeigten Zeilen; die Knopfzeile hängt
        :meth:`_settle_tab_order` danach an.
        """
        stops = [
            stop for row in self._built if self.isAncestorOf(row) for stop in _focus_stops(row)
        ]
        for first, second in pairwise(stops):
            QWidget.setTabOrder(first, second)

    def _ask_for_the_step(self, step: int) -> None:
        """Den vollständigen Dialog dieses Schritts öffnen.

        Der Weg für alles, was das Merkmalfenster nicht als Feld zeigen kann
        — heute die Fachaufteilung eines Organizers. Dieselbe Bauart wie der
        Knopf *Weitere Einstellungen …* an einer Textur.
        """
        self.stepEditRequested.emit(int(step))

    def _explain(self, box: QWidget, row: QHBoxLayout) -> QToolButton:
        """Hängt das Info-Zeichen an eine Überschrift — sichtbar erst mit einem Text.

        Ohne Text kein Zeichen: Ein Kreis, hinter dem nichts steht, ist eine
        Ankündigung, die niemand einlöst. Den Text bringt :meth:`_fill_row`
        (über :meth:`_extend_explanation`), damit eine wiederverwendete Zeile
        ihre Erklärung neu bekommt.
        """
        # **Ein Knopf und kein Label.** Ein QLabel zeigt seinen Tooltip nur,
        # solange die Maus wirklich darauf steht, und bei achtzehn Bildpunkten
        # trifft das niemand zuverlässig (Robert, 11.09.2026: „der tooltip bei
        # i geht auch nicht auf"). Ein QToolButton ist ein Trefferziel: Er
        # nimmt Hover an, zeigt den Tooltip, lässt sich anklicken und mit der
        # Tabulatortaste erreichen — und flach gezeichnet sieht er aus wie das
        # Zeichen, das er ist.
        dot = QToolButton(box)
        dot.setObjectName("infoDot")
        # **Auch ein Zeichen ist ein Oberflächentext** (Regel 20). „i" steht in
        # allen sechs Sprachen für dasselbe, und genau deshalb ist der
        # Katalogeintrag billig — aber die Entscheidung gehört dorthin und
        # nicht in eine Zeile Code, die keine Sprache je sieht.
        dot.setText(tr("i"))
        dot.setAutoRaise(True)
        dot.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        dot.setCursor(Qt.CursorShape.WhatsThisCursor)
        dot.setVisible(False)
        row.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
        return dot

    def _extend_explanation(self, box: QWidget, text: str) -> None:
        """Nimmt einen weiteren Absatz hinter dasselbe Info-Zeichen.

        Zwei Quellen speisen es — der Satz der Handlung und der Nachweis ihrer
        Gruppe —, und beide sollen erreichbar sein, ohne dass zwei Zeichen
        nebeneinander stehen.
        """
        entry = self._dots.get(id(box))
        if entry is None or not text:
            return
        dot, title = entry
        gathered = self._explanations.get(id(box), "")
        gathered = f"{gathered}\n\n{text}" if gathered else text
        self._explanations[id(box)] = gathered
        for widget in (dot, title):
            widget.setToolTip(gathered)
        # **Der Bildschirmleser bekommt ihn am Titel**, nicht am Zeichen: Der
        # Kreis ist ein Bild, die Überschrift ist die Sache, zu der der Absatz
        # gehört. Am Zeichen allein fände ihn niemand, der die Zeile vorgelesen
        # bekommt (§19.1).
        title.setAccessibleDescription(gathered)
        dot.setAccessibleName(str(tr("Erklärung zu {title}")).format(title=title.text()))
        _set_shown(dot, True)

    def _apply_stands(self) -> bool:
        """Ob der Knopf unten gerade etwas anzubieten hat.

        **Nicht ``isVisibleTo(self)``**, seit die Knopfzeile beim Träger
        wohnen darf (:meth:`footer`): Die Frage läuft dann die Elternkette bis
        zum Fenster hinauf, und ein offscreen nie gezeigtes Fenster
        beantwortet sie mit „nein" — der Abbrechen-Knopf blieb weg und die
        Eingabetaste stumm. ``isHidden`` fragt genau das, was hier gemeint
        ist: ob jemand ihn ausdrücklich weggenommen hat.
        """
        return not self._apply.isHidden()

    def footer(self) -> QWidget:
        """Die Knopfzeile — der Teil, der nicht mitrollen darf.

        Titel, *Im Bild einstellen*, der Haken, *Übernehmen* und *Abbrechen*
        in einem eigenen Widget. Wer das Panel in einen Rollbereich stellt,
        nimmt sie sich hier und hängt sie **unter** ihn; dann steht sie bei
        jeder Fensterhöhe da (:meth:`MainWindow._build_feature_dock`). Wer sie
        nicht nimmt, findet sie unten im Panel, wo sie immer stand.

        Wer sie nimmt, bekommt sie mit den Seitenrändern des Panels: Unter dem
        Rollbereich steht sie außerhalb von dessen Polster, und ohne eigenen
        Rand klebte ihr Titel an der Kartenkante.
        """
        layout = self._footer.layout()
        if layout is not None:
            layout.setContentsMargins(NORMAL, 0, NORMAL, TIGHT)
        return self._footer

    def _settle_apply(self) -> None:
        """Schiebt die Knopfzeile ans Ende, nachdem alle Zeilen stehen.

        Sie wird beim Aufbau des Panels **einmal** angelegt und liegt damit vor
        den Zeilen, die ``show_feature`` und die anderen später einfügen —
        sichtbar stand sie dann ganz oben, über der Überschrift der Auswahl
        (Robert, 10.09.2026: „ich hab doch gesagt der button soll unten sein
        nicht ganz oben"). Sie am Ende umzuhängen ist billiger als jede
        Einfügestelle um eins zu verschieben und dabei eine zu vergessen.

        **Und nur, solange sie dem Panel gehört.** Hat der Träger sie unter
        den Rollbereich gehängt (:meth:`footer`), steht sie dort richtig; sie
        zurückzuholen brächte sie genau in den Rollinhalt, aus dem sie heraus
        soll.
        """
        if self._footer.parentWidget() is self:
            self._rows.removeWidget(self._footer)
            self._rows.insertWidget(self._rows.count() - 1, self._footer)
        self._settle_tab_order()
        # Wiederverwendete Zeilen bringen ihren alten Zustand mit; offen ist
        # danach genau die scharfe (RM-510), und jede nennt ihre Werte.
        self._open_only(self._armed)
        for row in self._shown_rows.values():
            self._summarise(row)
        if self._armed not in self._runs:
            # Ohne Handlung trägt der Knopf nichts — nach einem Neuaufbau, der
            # die Knopfzeile stehen ließ (``clear(rebuilding=True)``), geht sie
            # hier, und nur hier, wenn nichts mehr kommt.
            for widget in (self._apply, self._armed_title, self._every):
                _set_shown(widget, False)
        self._settle_in_view()
        _set_shown(
            self._cancel, self._cancel_offered and not self._measuring and self._apply_stands()
        )
        self._settle_lock()

    def _settle_tab_order(self) -> None:
        """Die Tabulatortaste geht denselben Weg wie das Auge.

        **Ein Widget im Layout zu verschieben verschiebt es nicht in der
        Fokuskette.** Die folgt der Reihenfolge, in der die Widgets *entstanden*
        sind, und die vier unten entstehen im Aufbau des Panels — also vor
        jedem Feld, das ``show_feature`` später einfügt. Gemessen am gebauten
        Fenster an einer gewählten Bohrung: Die erste Tabulatortaste landete
        auf „Auf alle 4 gleichartigen anwenden", die zweite auf *Im Bild
        einstellen*, die dritte auf *Übernehmen* — und erst die vierte im
        obersten Zahlenfeld. Wer das Fenster mit der Tastatur bedient, kam
        damit am Knopf vorbei, bevor er einen Wert gesehen hatte; und weil der
        Knopf der zuletzt berührten Handlung gilt (:meth:`_arm`), hieß das
        auch: Er meinte etwas anderes, als daneben stand.

        ``setTabOrder`` hängt das zweite Widget hinter das erste, also wird die
        Kette von hinten aufgezogen: letztes Feld → Weg ins Bild → Haken →
        Übernehmen → Abbrechen. Unsichtbare und gesperrte Halte übergeht Qt von
        selbst, der Haken braucht also keinen Sonderfall.
        """
        if self._rows_reused:
            self._settle_row_order()
        anchor = self._last_field()
        chain = (self._in_view, self._every, self._apply, self._cancel)
        if anchor is not None:
            QWidget.setTabOrder(anchor, chain[0])
        for first, second in pairwise(chain):
            QWidget.setTabOrder(first, second)

    def _last_field(self) -> QWidget | None:
        """Das letzte Bedienelement über dem Knopf — der Anker der Kette.

        Von hinten gesucht, weil die letzte gebaute Zeile auch die unterste
        ist. Ein Strich (:meth:`_separate`) trägt nichts Bedienbares und wird
        dabei übergangen; das Textfeld **in** einem Drehfeld ebenso — es ist
        dessen Innenleben und kein eigener Halt.
        """
        for row in reversed(self._built):
            # Was in einem Abschnitt außerhalb steht (der Nahtschutz unter
            # „Filament und Druck“), ist kein Halt vor dem Knopf darunter.
            if not self.isAncestorOf(row):
                continue
            stops = _focus_stops(row)
            if stops:
                return stops[-1]
        return None

    def _separate(self) -> QWidget | None:
        """Zieht einen Strich vor die nächste Handlung — außer vor die erste.

        Eine Handlung ist ein Block aus Überschrift, Feldern und (seit dem
        10.09.2026) keinem eigenen Knopf mehr. Ohne Trennung folgen an einer
        Bohrung auf drei Zahlenfelder wieder drei, und wer nicht auf die
        Überschriften sieht, liest sie als eine Reihe (Robert, 10.09.2026:
        „die unterschiedlichen einstellungen noch abgrenzen durch einen
        strich"). Vor der ersten wäre er ein Strich gegen nichts.
        """
        if not self._built:
            return None
        line = rule(self)
        self._rows.insertWidget(self._rows.count() - 1, line)
        self._built.append(line)
        return line

    def _row_toggled(self, row: _ActionRow, checked: bool) -> None:
        """Ein Klick auf den Kopf öffnet seine Handlung — und macht sie scharf.

        Ein Klick auf den Kopf der offenen schließt sie nicht: Offen ist immer
        genau eine, die, die der Knopf unten übernimmt.
        """
        if checked:
            self._arm(row.key)
        self._open_row(row, row.key == self._armed)

    def _open_row(self, row: _ActionRow, open_now: bool) -> None:
        """Klappt eine Handlung auf oder zu, ohne sie scharf zu machen."""
        if row.toggle is None or row.body is None:
            return
        with QSignalBlocker(row.toggle):
            row.toggle.setChecked(open_now)
        row.toggle.setArrowType(Qt.ArrowType.DownArrow if open_now else Qt.ArrowType.RightArrow)
        if row.title is not None:
            # Die offene Handlung steht in voller Schrift, die zugeklappten in
            # der Nebenstufe — zusammen mit dem Pfeil zwei Kodierungen (Regel 18).
            level = "body" if open_now else "caption"
            if row.title.property("level") != level:
                set_level(row.title, level)
        _set_shown(row.body, open_now)
        if row.summary is not None:
            _set_shown(row.summary, not open_now and bool(row.summary.text()))

    def _open_only(self, key: str | None) -> None:
        """Genau eine Handlung offen: die scharfe (RM-510)."""
        for row in self._shown_rows.values():
            self._open_row(row, row.key == key)

    def _summarise(self, row: _ActionRow) -> None:
        """Was die Handlung gerade einstellt, in einer Zeile unter ihrem Kopf.

        Höchstens drei Werte, ein kurzer Feldname (X, Y, Z) steht davor; was
        ausgeblendet ist, zählt nicht mit. Zu sehen ist die Zeile nur,
        solange die Handlung zugeklappt ist.
        """
        if row.summary is None:
            return
        parts: list[str] = []
        for name, editor in row.widgets.items():
            shown = _field_text(editor) if not editor.isHidden() else ""
            if not shown:
                continue
            label = row.labels.get(name)
            caption = label.text() if label is not None else ""
            parts.append(f"{caption} {shown}" if caption and len(caption) <= 2 else shown)
            if len(parts) == 3:
                break
        row.summary.setText(" · ".join(parts))
        if row.body is not None:
            _set_shown(row.summary, row.body.isHidden() and bool(parts))

    def _arm(self, key: str) -> None:
        """Sagt dem Knopf unten, welche Zeile er meint.

        Aufgerufen beim Aufbau (die erste gilt) und bei jeder Berührung eines
        Feldes. ``key`` ist der **Zeilenschlüssel** aus :meth:`_build_action`
        und nicht der Name der Operation: Ein Baustein bietet drei Handlungen
        an, von denen zwei gar keine Operation tragen.
        """
        entry = self._runs.get(key)
        if entry is None:
            return
        changed = self._armed is not None and self._armed != key
        self._armed = key
        self._open_only(key)
        self._armed_title.setText(entry.title)
        # Beim Messen trägt die Maßgruppe im Bild Titel und Übernehmen.
        _set_shown(self._armed_title, not self._measuring)
        # **Der Titel steht am Knopf, nur nicht auf ihm.** Ein Bildschirmleser
        # liest den zugänglichen Namen, und „Übernehmen" allein sagte dort
        # nicht, was übernommen wird (§19.1).
        self._apply.setAccessibleName(entry.title)
        _set_shown(self._apply, not self._measuring)
        applies_to_all = entry.members > 1
        if applies_to_all:
            promise = str(tr("Eine Handlung für alle — und ein Strg+Z nimmt sie zusammen zurück."))
            self._every.setText(
                str(tr("Auf alle {count} gleichartigen anwenden")).format(count=entry.members)
            )
            self._every.setAccessibleDescription(promise)
        else:
            # **Ein Haken, der nicht gilt, wird auch nicht gehalten.** Sonst
            # stünde er ausgeblendet auf „an" und griffe wieder, sobald jemand
            # eine Handlung mit Gruppe anfasst.
            with QSignalBlocker(self._every):
                self._every.setChecked(False)
        _set_shown(self._every, applies_to_all and not self._measuring)
        self._settle_apply_block()
        if changed and entry.op != NO_OPERATION and not self._active_field_refusal():
            self.handlingArmed.emit(entry.op, entry.values())

    def take_values(self, op: str, values: Mapping[str, Any], *, arm: bool = True) -> bool:
        """Vorgeschlagene Zahlen in die Felder dieser Handlung — und sie scharf.

        Der Gegenweg zu :attr:`valuesChanged`: Ein Zug im Bild schlägt Länge
        und Richtung vor, und sie gehören dorthin, wo das Übernehmen sie
        liest. Bis zum 11.09.2026 ging der Zug in eine **eigene Leiste** unten
        mit eigenen Feldern und eigenem Übernehmen — zwei Bedienstellen über
        demselben Loch (Robert: „die untere leiste uns sparen und nur die
        rechte verwenden mit dem was schon drin ist").

        Der Rückgabewert sagt, ob die Handlung überhaupt angeboten wird: An
        einem Merkmal ohne sie geschieht nichts, und der Aufrufer weiß es.
        Die reine Rückmeldung aus einer Platzierung setzt ``arm=False``: Sie
        aktualisiert Zahlen, ohne die gerade gewählte Handlung zu wechseln.
        """
        found = next(((key, entry) for key, entry in self._runs.items() if entry.op == op), None)
        if found is None or found[1].take is None:
            return False
        key, entry = found
        assert entry.take is not None
        entry.take(values)
        if arm:
            self._arm(key)
        return True

    def _run_armed(self) -> None:
        """Führt aus, was der Knopf unten gerade meint."""
        # interpretText im Tastaturweg kann synchron eine neue Vorschau
        # auslösen und damit die vorherige Freigabe zurücknehmen.
        if not self.can_accept():
            # Ein Klick vor der Vorschau verfällt nicht, er wartet auf sie.
            if self.preview_defer is not None and self._apply_allowed():
                self.preview_defer()
            return
        entry = self._runs.get(self._armed or "")
        if entry is not None:
            entry.run()

    def _show_armed_in_view(self) -> None:
        """Bringt die Maße dieses Merkmals in die Szene, statt auszuführen.

        **Und macht dabei ihre Handlung scharf.** Der Knopf darunter führt
        aus, was zuletzt angefasst wurde; nach einem Klick hier steht im Bild
        aber sichtbar eine Platzierung, und die gehört einer bestimmten
        Handlung. Ohne das Umschalten übernähme der Knopf daneben eine andere
        — gemessen an einer Bohrung: *Merkmal verschieben* stand scharf,
        während im Bild die Maße von *Bohrung ändern* lagen.
        """
        if self._into_view is None:
            return
        if self._in_view_key is not None:
            self._arm(self._in_view_key)
        self._into_view()

    def _settle_in_view(self) -> None:
        """Entscheidet, ob dieses Merkmal den Weg ins Bild anbietet.

        **Einmal je Merkmal, nicht je Handlung**, und das ist der Unterschied
        zum Knopf daneben: Die Maßlinien zeigen die Stelle des *Lochs* — zu
        den Kanten der Fläche und zu den Mitten der Nachbarn —, und die ist
        dieselbe, gleich ob man gerade den Durchmesser oder die Länge ansieht.
        An der scharfen Handlung aufgehängt verschwände der Knopf, sobald
        jemand ein Feld von *Merkmal drehen* anfasst, und wäre damit ein
        Angebot, das man erst suchen muss.

        Angeboten wird er, sobald **eine** Handlung dieses Merkmals dorthin
        führt; welche, sagt :data:`LEADS_INTO_THE_VIEW`.
        """
        found = next(
            ((key, entry) for key, entry in self._runs.items() if entry.in_view is not None),
            None,
        )
        self._in_view_key = found[0] if found is not None else None
        self._into_view = found[1].in_view if found is not None else None
        _set_shown(self._in_view, self._into_view is not None and not self._measuring)
        if self._into_view is None:
            return
        promise = str(tr("Maßlinien zu Kanten und Mitten in der Szene — dort einstellen."))
        self._in_view.setToolTip(promise)
        self._in_view.setAccessibleName(str(tr("Im Bild einstellen")))
        self._in_view.setAccessibleDescription(promise)

    def measure_fields(
        self, op: str, parent: QWidget | None, *, feature: Feature | None = None
    ) -> tuple[Any, QWidget, dict[str, QWidget]] | None:
        """Die aktive Maßgruppe aus derselben fachlichen Feldbeschreibung aufbauen.

        ``parent`` ist ``None``, wenn der Empfänger das Kästchen gleich in sein
        eigenes Layout nimmt: Ein Umweg über die Ansicht machte es nativ
        (``overlay.hold_above_the_view``).

        **Eine zurückgegebene Gruppe derselben Bauart kommt wieder** (RM-232):
        dieselbe Handlung mit denselben Feldern (:meth:`_measure_signature`),
        neu geschrieben werden Werte, Grenzen, Beschriftungen und Erklärungen
        — dieselben Aufrufe wie beim Bau (:meth:`_fill_measure_group`). Nur
        ohne Elternteil: Wer eines vorgibt, bekommt ein frisches Kästchen darin.
        """
        entry = next((entry for entry in self._runs.values() if entry.op == op), None)
        if entry is None or entry.action is None:
            return None
        action = entry.action
        signature = self._measure_signature(action, feature) if parent is None else None
        group = self._spare_measures.pop(signature, None) if signature is not None else None
        if group is not None and not _measure_group_alive(group):
            group = None
        if group is None:
            group = self._new_measure_group(action, parent, feature, signature)
        else:
            for field in action.fields:
                configure_feature_field(group.widgets[str(field.name)], field)
            for line in group.box.findChildren(QLineEdit):
                # Ein frisches Feld gilt als unberührt; was im vorigen Fluss
                # getippt war, hielte sonst ``refresh`` vom Schreiben ab.
                line.setModified(False)
        self._fill_measure_group(group, action, feature)
        # Was nie zurückkam (der Empfänger starb vorher), geht hier aus der
        # Buchführung — samt dem, was an ihm gebunden war.
        self._measure_groups = {
            key: held for key, held in self._measure_groups.items() if isValid(held.box)
        }
        self._measure_groups[id(group.box)] = group
        return action, group.box, dict(group.widgets)

    def _measure_signature(self, action: Any, feature: Feature | None) -> tuple[Any, ...] | None:
        """Woran eine Maßgruppe erkennt, dass sie eine andere Handlung tragen kann.

        Die Signatur der Handlungszeile (:meth:`_row_signature`) und dazu, was
        die Gruppe an Zeilen mehr hat: die Zeile mit dem aktuellen Maß und die
        mit dem Satz zur Lage.
        """
        row = self._row_signature(action)
        if row is None:
            return None
        return (row, feature is not None, bool(action.note))

    def _new_measure_group(
        self,
        action: Any,
        parent: QWidget | None,
        feature: Feature | None,
        signature: tuple[Any, ...] | None,
    ) -> _MeasureGroup:
        """Baut die Widgets einer Maßgruppe — Texte schreibt :meth:`_fill_measure_group`."""
        from app.ui.op_dialog import ValueField, advanced_summary

        box = _MeasureBox(parent)
        form = QFormLayout(box)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(TIGHT)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        title = QLabel(str(action.title), box)
        title.setWordWrap(True)
        set_level(title, "caption")
        form.addRow(title)
        current: QLabel | None = None
        if feature is not None:
            current = QLabel(box)
            current.setObjectName("feature-measure-source")
            current.setWordWrap(True)
            form.addRow(current)
        note: QLabel | None = None
        if action.note:
            note = QLabel(str(action.note), box)
            note.setWordWrap(True)
            form.addRow(note)
        widgets: dict[str, QWidget] = {}
        labels: dict[str, QLabel] = {}
        refusals: dict[str, QLabel] = {}
        # **Die Stelle steht über die Kantenmaße im Bild** (RM-516): X, Y und Z
        # derselben Stelle stehen dahinter, unter „Weitere Werte“ — erreichbar,
        # aber nicht als zweite Zahlenreihe für dieselbe Lage.
        coordinates = _coordinate_fields(action)
        more_form: QFormLayout | None = None
        more_content: QWidget | None = None
        if coordinates:
            more_content = QWidget(box)
            more_form = QFormLayout(more_content)
            more_form.setContentsMargins(0, 0, 0, 0)
            more_form.setSpacing(TIGHT)
            more_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            more_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for field in action.fields:
            target = more_form if more_form is not None and str(field.name) in coordinates else form
            editor = self._build_field(field, box)
            label = QLabel(str(field.label), box)
            label.setWordWrap(True)
            label.setBuddy(editor)
            if isinstance(editor, ValueField):
                editor.captionChanged.connect(label.setText)
                wheel_needs_focus(editor.spin)
            elif isinstance(editor, QAbstractSpinBox | QComboBox):
                wheel_needs_focus(editor)
            target.addRow(label, editor)
            if isinstance(editor, (BoundedSpin, BoundedLengthSpin)):
                refusal = QLabel(box)
                refusal.setObjectName(f"feature-measure-refusal-{field.name}")
                refusal.setWordWrap(True)
                refusal.setVisible(False)
                refusals[str(field.name)] = refusal
                target.addRow(refusal)
                editor.valueRefused.connect(partial(self._refresh_measure_refusal, editor, refusal))
                editor.lineEdit().textEdited.connect(
                    partial(self._refresh_measure_refusal, editor, refusal)
                )
            widgets[str(field.name)] = editor
            labels[str(field.name)] = label
            if isinstance(editor, ValueField):
                editor.changed.connect(box.conditionsChanged)
            elif isinstance(editor, LengthSpin):
                editor.valueChangedMm.connect(box.conditionsChanged)
            elif isinstance(editor, QCheckBox):
                editor.toggled.connect(box.conditionsChanged)
            elif isinstance(editor, QComboBox):
                editor.currentIndexChanged.connect(box.conditionsChanged)
            elif isinstance(editor, QSpinBox | QDoubleSpinBox):
                editor.valueChanged.connect(box.conditionsChanged)
        more: QWidget | None = None
        if more_content is not None:
            names = [str(field.label) for field in action.fields if str(field.name) in coordinates]
            more = collapsible(
                tr("Weitere Werte"),
                more_content,
                open_now=False,
                contents=advanced_summary(names),
            )
            more.setParent(box)
            more.setObjectName("feature-measure-more")
            # In der kleinen Karte keine Abschnittsüberschrift, die lauter ist
            # als der Titel der Handlung darüber.
            heading = more.findChild(QToolButton, "sectionHeading")
            if heading is not None:
                set_level(heading, "body")
            form.addRow(more)
            align_forms(box)
        group = _MeasureGroup(
            box, signature, title, current, note, widgets, labels, refusals, more=more
        )
        box.conditionsChanged.connect(
            weak_slot(self, FeaturePanel._follow_measure_conditions, group)
        )
        return group

    def _fill_measure_group(
        self, group: _MeasureGroup, action: Any, feature: Feature | None
    ) -> None:
        """Was eine Maßgruppe über ihre Handlung sagt — beim Bau und beim Wiederverwenden.

        Die Werte der Felder stehen dann schon (:func:`configure_feature_field`);
        Beschriftung, Kurzhilfe und zugänglicher Name folgen ihnen.
        """
        group.fields = tuple(action.fields)
        group.fixed = tuple(getattr(action, "fixed", ()))
        group.title.setText(str(action.title))
        if group.current is not None and feature is not None:
            # **Die Zahl steht im Feld, hier nur, woher sie kommt** (RM-516).
            # „Aktuell: Ø5,20 mm · eingepasst“ über dem Feld mit 5,20 mm war
            # derselbe Durchmesser ein zweites Mal im Bild. Geblieben ist das
            # Wort, das warnt; eine direkte Quelle sagt nichts, und am
            # fertigen Teil eines Schritts steht im Feld dessen eigener Wert.
            caption = feature_source(feature) if getattr(action, "step", None) is None else ""
            group.current.setText(caption)
            hint = feature_measure_tip(feature)
            group.current.setToolTip(hint)
            group.current.setAccessibleDescription(hint)
            _set_shown(group.current, bool(caption))
            if caption:
                fit_wrapped(group.current)
        if group.more is not None:
            # Jede Maßgruppe beginnt zugeklappt, auch eine wiederverwendete.
            heading = group.more.findChild(QToolButton, "sectionHeading")
            if heading is not None and heading.isChecked():
                heading.setChecked(False)
        if group.note is not None:
            group.note.setText(str(action.note))
            fit_wrapped(group.note)
        for field in action.fields:
            name = str(field.name)
            editor = group.widgets[name]
            label = group.labels[name]
            label.setText(str(field.label))
            label.setToolTip(editor.toolTip())
            label.setAccessibleDescription(editor.accessibleDescription())
            editor.setAccessibleName(f"{action.title} — {field.label}")
            editor.setProperty(FIELD_PROPERTY, name)
            if isinstance(editor, (BoundedSpin, BoundedLengthSpin)):
                refusal = group.refusals.get(name)
                if refusal is not None:
                    self._set_refusal_label(editor, refusal)
        self._follow_measure_conditions(group)

    def _follow_measure_conditions(self, group: _MeasureGroup) -> None:
        """Feld, Titel und Absagesatz folgen derselben Bedingung wie rechts."""
        from app.core.registry.params import inactive_dependency

        values = feature_field_values(group.fields, group.widgets, group.fixed)
        for field in group.fields:
            name = str(field.name)
            active = inactive_dependency(field, group.fields, values) is None
            _set_shown(group.widgets[name], active)
            _set_shown(group.labels[name], active)
            refusal = group.refusals.get(name)
            if refusal is not None:
                _set_shown(refusal, active and bool(refusal.text()))

    def bind_measure_group(self, box: QWidget, release: Callable[[], None]) -> None:
        """Hängt an eine ausgegebene Maßgruppe, was ihr Empfänger beim Zurückgeben löst."""
        group = self._measure_groups.get(id(box))
        if group is not None and group.box is box:
            group.released.append(release)

    def keep_measure_group(self, box: QWidget) -> bool:
        """Eine Maßgruppe zurücknehmen, statt sie zu löschen — ``False``, wenn sie geht.

        Der Empfänger hat sie aus seinem Layout genommen (ohne Elternteil);
        hier löst sich, was er daran gebunden hatte, und sie wartet
        verborgen auf die nächste Handlung gleicher Bauart. Was keine
        Signatur hat, einen Elternteil behielt oder nicht mehr ganz lebt, geht
        wie bisher: Der Aufrufer löscht es.
        """
        group = self._measure_groups.pop(id(box), None)
        if group is None or group.box is not box:
            return False
        for release in group.released:
            release()
        group.released.clear()
        if (
            group.signature is None
            or not _measure_group_alive(group)
            or box.parentWidget() is not None
        ):
            return False
        box.hide()
        # **Was der Empfänger hineingehängt hat, geht mit ihm.** Der Haken
        # *Auf alle anwenden* entsteht im Kästchen und zieht erst in den
        # Umfangsbereich des Flusses um; endet der Fluss vorher, stünde er
        # beim nächsten Merkmal verwaist oben links in der Gruppe.
        own = {
            id(part)
            for part in (group.title, group.current, group.note, group.more)
            if part is not None
        } | {
            id(part)
            for part in (*group.widgets.values(), *group.labels.values(), *group.refusals.values())
        }
        for child in box.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
            if id(child) not in own:
                child.hide()
                child.deleteLater()
        previous = self._spare_measures.pop(group.signature, None)
        if previous is not None and previous is not group:
            _discard_measure_group(previous)
        self._spare_measures[group.signature] = group
        while len(self._spare_measures) > SPARE_MEASURE_GROUPS:
            oldest = next(iter(self._spare_measures))
            _discard_measure_group(self._spare_measures.pop(oldest))
        return True

    def measure_group(self, op: str) -> Any:
        """Das belegte Gruppenangebot zum Binden an den angezeigten Entwurf."""
        return self._groups.get(op)

    @property
    def measuring(self) -> bool:
        """Ob gerade Maße im Bild stehen (:meth:`set_measuring`)."""
        return self._measuring

    def set_measuring(self, active: bool, *, op: str | None = None, begun: bool = False) -> None:
        """Während der Maßgruppe gibt es deren Felder und Abschluss genau einmal.

        Stehen Maße im Bild, trägt die Maßgruppe Übernehmen und Abbrechen; die
        Knöpfe hier unten gehen mit dem Messen und kommen mit seinem Ende zurück
        (``_settle_lock``).
        """
        self._measuring = bool(active)
        self._measure_op = op if active else None
        self._measure_begun = bool(active and begun)
        self._settle_lock()
        _set_shown(
            self._cancel, self._cancel_offered and not self._measuring and self._apply_stands()
        )
        # **Was im Bild steht, steht rechts nicht noch einmal** (Robert,
        # 21.09.2026: „durchmesser ist ja im viewport, kann im merkmalpanel
        # entfernt werden", RM-199). Bis dahin blieben Durchmesser, Umfang und
        # Koordinaten als gesperrte Zwillinge stehen — zwei Stellen für
        # dieselbe Zahl, von denen eine nichts annahm. Der Block geht mit dem
        # Messen und kommt mit seinem Ende zurück; die übrigen Handlungen
        # bleiben, wo sie waren.
        for key, (line, row) in self._blocks.items():
            entry = self._runs.get(key)
            twin = (
                self._measuring
                and entry is not None
                and (
                    entry.op == self._measure_op
                    or (
                        self._measure_op in {"drill_hole", "drill_brep_hole"}
                        and entry.op in LEADS_INTO_THE_VIEW
                    )
                )
            )
            # Beim ursprünglichen Bohrschritt gehören auch Länge und Richtung
            # zu dessen Maßgruppe. Die gemessenen Folgehandlungen erscheinen
            # nach deren Ende wieder, mit ihren eigenen aktuellen Werten.
            _set_shown(row, not twin)
            if line is not None:
                _set_shown(line, not twin)
        # Und im Zwilling daneben die Felder, die die Maßgruppe schon trägt.
        for shown in self._shown_rows.values():
            self._follow_conditions(shown)

    def offer_cancel(self, offered: bool) -> None:
        """Ob *Abbrechen* steht: solange eine Vorschau aus diesem Panel wartet.

        Bis zum 20.09.2026 stand der Knopf beim Messen im Bild; seit die
        Maßgruppe Übernehmen und Abbrechen selbst trägt, hatte er hier keinen
        Ort mehr — sichtbar nur beim Messen, beim Messen verborgen (gemessen am
        21.09.2026). Sein Satz sagt, wozu er da ist: „Verwirft, was im Bild
        wartet — gerechnet wird nichts." Das ist die Feldvorschau, die eine
        getippte Zahl angestoßen hat und die noch kein Schritt ist; wer sie
        nicht will, hatte bis dahin nur Escape aus der Auswahl heraus.
        """
        self._cancel_offered = bool(offered)
        _set_shown(
            self._cancel, self._cancel_offered and not self._measuring and self._apply_stands()
        )

    def armed_by_tab(self) -> bool:
        """Ob die Handlung gerade über Tab oder Umschalt+Tab scharf wird.

        Wer mit der Tastatur durch das Fenster geht, bleibt im Fenster: Ein
        Tab aus dem Tiefenfeld in die Länge des Zwillings wechselte sonst die
        Maßgruppe, der Fokus sprang ins Bild, und das nächste Tab lief dort
        weiter statt hier (Review 24.09.2026). Gefragt beim ``handlingArmed``
        derselben Runde (``MainWindow._hand_the_measures_over``).
        """
        return self._armed_by_tab

    def request_in_view(self) -> None:
        """Denselben Weg nehmen wie der Knopf *Im Bild einstellen* — wenn er steht.

        Für das Hauptfenster, das die Maße nach einem Übernehmen wieder ins
        Bild bringt: Es klickt nicht auf ein Widget, es nimmt den Weg, der am
        Widget hängt. Wo kein Knopf steht, geschieht nichts.

        **Die scharfe Handlung hat Vorrang.** Der Knopf steht einmal je
        Merkmal (``_settle_in_view``) und führt zur ersten Handlung mit Weg
        ins Bild; wer vorher *Zum Langloch ziehen* scharfgeschaltet hat, meint
        aber dessen Maße — sonst stand nach dem Wechsel wieder *Bohrung
        ändern* im Bild (gemessen am 21.09.2026 an vier Fenstertests).
        """
        armed = self._runs.get(self._armed or "")
        if armed is not None and armed.in_view is not None:
            armed.in_view()
            return
        if self._into_view is not None:
            self._into_view()

    def _group_changed(self, _checked: bool) -> None:
        """Ein geänderter Umfang braucht dieselbe Vorschau wie geänderte Maße."""
        entry = self._runs.get(self._armed or "")
        if entry is not None and entry.op != NO_OPERATION:
            self.valuesChanged.emit(entry.op, entry.values())

    def preview_targets(self, op: str) -> tuple[str, ...]:
        """Ziele der Sammelhandlung, gewähltes zuerst; leer bei Einzelanwendung."""
        every = self._every_for(op)
        group = self._groups.get(op)
        if every is None or not every.isChecked() or group is None or self._feature_id is None:
            return ()
        targets = [member.target for member in group.members]
        if self._feature_id in targets:
            targets.remove(self._feature_id)
            targets.insert(0, self._feature_id)
        return tuple(targets)

    def _every_for(self, op: str) -> QCheckBox | None:
        """Der Haken unten — aber nur, wenn diese Handlung eine Gruppe hat.

        Er ist einer für alle Handlungen; wer keine gleichartigen Geschwister
        hat, bekommt ``None`` und damit dieselbe Antwort wie früher, als es
        seinen Haken gar nicht gab.
        """
        entry = self._runs.get(self._armed or "")
        if entry is None or entry.op != op or entry.members <= 1:
            return None
        return self._every

    def _watch(self, editor: QWidget, row: _ActionRow) -> None:
        """Meldet jede Änderung an einem Feld — für die Vorschau, nicht zum Tun.

        **Bei der Länge über ``valueChangedMm``**: Qts ``valueChanged`` trägt
        die Zahl aus dem Feld, also einen Anzeigewert. Wer sie weiterreicht,
        hat die Umrechnung übersprungen, und aus 5 mm werden bei Zoll 0,1969.

        Gelesen wird beim Melden aus der **Zeile** (Schlüssel, Operation,
        Felder), nicht aus dem Stand beim Bau: Eine wiederverwendete Zeile
        meldet für das Merkmal, das gerade dasteht (RM-204). Die Merker für
        Sperre und Fokus setzt :meth:`_fill_row` bei jedem Füllen neu.
        """

        def report(*_ignored: object) -> None:
            # **Wer einen Wert ändert, meint diese Handlung.** Der Knopf unten
            # folgt der Berührung; ohne das zeigte er auf die erste, während
            # jemand in der vierten tippt.
            self._arm(row.key)
            # Eine andere Art der Fase zeigt andere Felder — vor der Meldung,
            # damit die Vorschau schon zur sichtbaren Zeile gehört.
            self._follow_conditions(row)
            self._summarise(row)
            self._settle_apply_block()
            if not self._active_field_refusal():
                self.valuesChanged.emit(row.op, self._row_values(row))

        for target in (editor, *editor.findChildren(QLineEdit)):
            target.installEventFilter(self)
        from app.ui.op_dialog import ValueField

        # **Das Rad dreht ein Feld erst mit Fokus** (Robert, 16.09.2026): Beim
        # Rollen liegt der Zeiger zwangsläufig über Feldern, und jedes
        # Drehfeld darunter nahm die Raste als Wert (Regel in ``oberflaeche.md``).
        if isinstance(editor, ValueField):
            wheel_needs_focus(editor.spin)
        elif isinstance(editor, QAbstractSpinBox | QComboBox):
            wheel_needs_focus(editor)

        if isinstance(editor, ValueField):
            editor.changed.connect(report)
        elif isinstance(editor, LengthSpin):
            editor.valueChangedMm.connect(report)
        elif isinstance(editor, QCheckBox):
            editor.toggled.connect(report)
        elif isinstance(editor, QComboBox):
            editor.currentIndexChanged.connect(report)
        elif isinstance(editor, QSpinBox | QDoubleSpinBox):
            editor.valueChanged.connect(report)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Schnittstelle
        """Schon der Fokus benennt die Handlung, ohne ihren Wert zu ändern.

        **Und die Eingabetaste übernimmt sie** (13.09.2026). Wer eine Zahl
        tippt und Enter drückt, meint den Schritt; gemessen am gebauten
        Fenster blieb der Verlauf bei 1 Schritt, und erst der Klick auf
        *Übernehmen* schrieb ihn — bei einem Knopf, der an dieser
        Fensterhöhe gar nicht zu sehen war (:meth:`footer`).
        """
        from app.ui.leash import stop_watching_the_dying

        if stop_watching_the_dying(self, watched, event):
            return False
        key = watched.property("handlingKey")
        if event.type() == QEvent.Type.FocusIn:
            if isinstance(key, str):
                reason = event.reason() if hasattr(event, "reason") else None
                self._armed_by_tab = reason in (
                    Qt.FocusReason.TabFocusReason,
                    Qt.FocusReason.BacktabFocusReason,
                )
                try:
                    self._arm(key)
                finally:
                    self._armed_by_tab = False
        elif (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and isinstance(key, str)
        ):
            return self._apply_from_the_keyboard(watched, key)
        return super().eventFilter(watched, event)

    def _apply_from_the_keyboard(self, watched: QObject, key: str) -> bool:
        """Die Eingabetaste in einem Feld tut, was der Knopf darunter tut.

        **Nur wenn er es täte:** Ist er gesperrt (die Kette hält an) oder gibt
        es ihn gerade nicht, geschieht nichts — eine Taste, die etwas anderes
        tut als der Knopf daneben, wäre schlimmer als eine, die schweigt.

        Der getippte Text wird vorher **festgeschrieben**
        (``interpretText``): Das Ereignis kommt hier an, bevor das Drehfeld es
        sieht, und ohne das läse das Übernehmen die Zahl von vorhin.
        ``watched`` ist dabei entweder das Drehfeld selbst oder sein inneres
        Textfeld — beide tragen den Merker.
        """
        if not (self._apply.isEnabled() and self._apply_stands()):
            return False
        editor = watched if isinstance(watched, QWidget) else None
        if isinstance(editor, QLineEdit):
            editor = editor.parentWidget()
        if isinstance(editor, QAbstractSpinBox):
            editor.interpretText()
        self._arm(key)
        self._run_armed()
        return True

    def _mark(self, widget: QWidget, key: str) -> None:
        """Ein Bedienelement seiner Handlung zuordnen — und für die Sperre merken."""
        widget.setProperty("handlingKey", key)
        self._keyed.append(widget)

    def _build_field(self, field: Any, parent: QWidget) -> QWidget:
        """Panel und Maßgruppe verwenden dieselben Felder und Ausdruckswerte."""
        return feature_field(
            field,
            parent,
            expression_fields=self._texture_fields,
            part_fields=self._part_fields,
            parameter_values=self._parameter_values,
        )

    def _values(
        self,
        fields: Sequence[Any],
        widgets: Mapping[str, QWidget],
        fixed: Sequence[tuple[str, Any]] = (),
    ) -> dict[str, Any]:
        """Panelwerte mit dem dort angezeigten Merkmal lesen."""
        return feature_field_values(fields, widgets, fixed, feature_id=self._feature_id)

    def _emit(
        self,
        op: str,
        fields: Sequence[Any],
        widgets: Mapping[str, QWidget],
        every: QCheckBox | None = None,
        fixed: Sequence[tuple[str, Any]] = (),
    ) -> None:
        """Die Werte einsammeln und die Operation nennen — gerechnet wird im Kern.

        Ist der Haken gesetzt, gilt sie allen gleichartigen Merkmalen des
        Körpers, und das Fenster macht daraus **eine** Transaktion.
        """
        params = self._values(fields, widgets, fixed)
        if every is not None and every.isChecked() and self._feature_id is not None:
            targets = self.preview_targets(op)
            if not targets:
                return
            self.operationRequestedForEach.emit(op, params, list(targets))
            return
        self.operationRequested.emit(op, params)


#: Welche merkenden Abschnitte offen stehen, unter ihrem Schlüssel.
#:
#: Gebunden an ``UiSettings.open_sections`` des Fensters
#: (:func:`keep_sections_in`), damit das Speichern der Einstellungen den
#: Zustand mitnimmt — auch aus Dialogen, die eine Kopie bearbeiten.
_OPEN_SECTIONS: dict[str, bool] = {}


def keep_sections_in(store: dict[str, bool]) -> None:
    """Merkende Abschnitte schreiben ihren Zustand ab jetzt in ``store``."""
    global _OPEN_SECTIONS
    _OPEN_SECTIONS = store


class _SectionSummary(QLabel):
    """Was in einem zugeklappten Abschnitt steht — ein Klick klappt ihn auf."""

    def __init__(self, text: str, heading: QToolButton, parent: QWidget) -> None:
        super().__init__(text, parent)
        self._heading = heading
        self.setWordWrap(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        set_level(self, "caption")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 — Qt-Name
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self._heading.setChecked(True)
            return
        super().mouseReleaseEvent(event)


class _RowTitle(QLabel):
    """Der Titel einer Handlung — ein Klick öffnet sie wie ihr Pfeil (RM-510)."""

    def __init__(self, text: str, heading: QToolButton, parent: QWidget) -> None:
        super().__init__(text, parent)
        self._heading = heading
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 — Qt-Name
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self._heading.setChecked(True)
            return
        super().mouseReleaseEvent(event)


class _RowSummary(QLabel):
    """Die Werte einer zugeklappten Handlung — ein Klick öffnet sie (RM-510)."""

    def __init__(self, heading: QToolButton, parent: QWidget) -> None:
        super().__init__("", parent)
        self._heading = heading
        self.setWordWrap(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        set_level(self, "caption")
        self.setIndent(heading.sizeHint().width() + TIGHT)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 — Qt-Name
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self._heading.setChecked(True)
            return
        super().mouseReleaseEvent(event)


def _field_text(editor: QWidget) -> str:
    """Wie ein Feld seinen Wert gerade zeigt — für die Kopfzeile einer Handlung."""
    target = getattr(editor, "spin", editor)
    if isinstance(target, QAbstractSpinBox):
        return target.text().strip()
    if isinstance(target, QComboBox):
        return target.currentText()
    if isinstance(target, QLineEdit):
        return target.text().strip()
    return ""


def collapsible(
    title: str,
    content: QWidget,
    *,
    open_now: bool = True,
    contents: str = "",
    remember: str = "",
    heading_row: QBoxLayout | None = None,
) -> QWidget:
    """Ein Abschnitt, der sich zuklappen lässt — §2.5 verlangt genau das.

    Er hieß so und war keiner: eine fette Überschrift über dem Inhalt, ohne
    Umschalter. Wer den Verlauf groß haben wollte, konnte die anderen beiden
    nicht wegklappen, und drei Abschnitte in einer schmalen Spalte teilen sich
    die Höhe, ob sie sie brauchen oder nicht.

    Der Umschalter ist ein Knopf mit dem Titel darauf, kein Zeichen daneben:
    die ganze Zeile ist damit die Fläche, die man trifft, und der gedrückte
    Zustand sagt ohne Farbe, ob offen oder zu ist (Regel 18).

    **Zugeklappt nennt er, was darin steht** (``contents``, RM-491): Hinter
    „Weitere Einstellungen" lagen Tastenbelegung und Fernsteuerung, und von
    außen verriet nichts, dass es sie gibt. Die Zeile steht unter der
    Überschrift, nur solange sie zu ist, und klappt auf, wenn man sie
    anklickt; Kurzhilfe und Bildschirmleser bekommen denselben Satz.

    **Mit ``remember`` merkt er sich, wie der Kunde ihn verließ** — über
    Dialoge und Neustarts hinweg (:func:`keep_sections_in`). Ohne Merker
    gilt ``open_now``.

    **Mit ``heading_row`` steht die Überschrift in einer Zeile mit anderem**
    (RM-508: der Kopf des Prüfberichts ist eine Zeile, „Status · Zähler ·
    Prüfumfang“). Sie ist dann so breit wie ihr Titel, ohne Linie darunter,
    in Grundschrift; der Wrapper trägt nur den Inhalt. Was zugeklappt darin
    steht, nennen Kurzhilfe und Beschreibung, denn eine Zeile darunter wäre
    die zweite, die der Kopf nicht haben soll. Die Überschrift ist das letzte
    Element, das die Funktion in ``heading_row`` legt.
    """
    if remember:
        open_now = _OPEN_SECTIONS.get(remember, open_now)
    wrapper = QWidget()
    heading = QToolButton(wrapper)
    # Eine Kopfzeile ist kein Umschalter im Sinne der Werkzeugzeile: sie steht
    # dauerhaft auf „offen", und ein dauerhaft eingefärbter Balken wäre die
    # lauteste Fläche im Fenster für die Aussage „hier ist nichts geschehen".
    heading.setObjectName("sectionHeading")
    heading.setText(title)
    heading.setCheckable(True)
    # ``open_now=False`` für alles, was hinter „Weitere Einstellungen" gehört
    # (§2.4): die drei Abschnitte der linken Spalte stehen offen, ein
    # Startwert in einem Erzeugungsdialog nicht.
    heading.setChecked(open_now)
    heading.setAutoRaise(True)
    heading.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    heading.setArrowType(Qt.ArrowType.DownArrow if open_now else Qt.ArrowType.RightArrow)
    content.setVisible(open_now)
    inline = heading_row is not None
    set_level(heading, "body" if inline else "section")
    heading.setSizePolicy(
        # Fest: Qt kürzte eine Überschrift in der Zeile sonst mitten im Wort.
        QSizePolicy.Policy.Fixed if inline else QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    if inline:
        heading.setProperty("inline", True)
    summary: _SectionSummary | None = None
    if contents:
        heading.setToolTip(contents)
        heading.setAccessibleDescription(contents)
    if contents and not inline:
        summary = _SectionSummary(contents, heading, wrapper)
        summary.setObjectName("sectionSummary")
        # Eingerückt bis unter den Titel, nicht unter den Pfeil.
        summary.setIndent(heading.iconSize().width() + TIGHT)
        summary.setVisible(not open_now)

    def toggled(open_now: bool) -> None:
        content.setVisible(open_now)
        heading.setArrowType(Qt.ArrowType.DownArrow if open_now else Qt.ArrowType.RightArrow)
        if summary is not None:
            summary.setVisible(not open_now)
        if remember:
            _OPEN_SECTIONS[remember] = open_now

    heading.toggled.connect(toggled)

    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    if heading_row is not None:
        heading_row.addWidget(heading)
    else:
        layout.addWidget(heading)
    if summary is not None:
        layout.addWidget(summary)
    layout.addWidget(content)
    return wrapper


def open_section(content: QWidget) -> None:
    """Klappt den Abschnitt auf, in dem dieser Inhalt steckt — falls er zu ist.

    Der Gegenpart zu :func:`collapsible`, und er fehlte: Wer einen Bereich
    hervorhebt, muss ihn erst sichtbar machen. „Sehen Sie links in den
    Verlauf" ließ einen Rahmen um einen zugeklappten Abschnitt aufleuchten —
    also um eine Kopfzeile, unter der nichts steht.

    Gesucht wird unter den **direkten** Kindern des Wrappers: Der Inhalt hat
    eigene Knöpfe, und einer davon wäre sonst der erste Treffer. Steckt das
    Widget in keinem Abschnitt — der Prüfbericht sitzt in einem Reiter —,
    geschieht nichts.
    """
    wrapper = content.parentWidget()
    if wrapper is None:
        return
    for child in wrapper.children():
        if isinstance(child, QToolButton) and child.objectName() == "sectionHeading":
            if not child.isChecked():
                child.setChecked(True)
            return


def least_number_width(spin: QDoubleSpinBox) -> int:
    """Wie schmal ein Zahlenfeld werden darf, ohne seinen Wert zu verstecken.

    Nicht der Wunsch des Feldes: Der bemisst sich am **Wertebereich**, und ein
    Parameter, der bis 100 000 gehen darf, verlangte damit 156 Punkte für eine
    40. Nicht die reine Textbreite: Rechts sitzen die zwei Knöpfe, und was sie
    verdecken, ist kein Platz.

    Gerechnet wird deshalb der heutige Text plus das, was das Feld **um**
    seinen Text herum braucht — die Differenz zwischen seinem Wunsch und der
    Breite seines längsten möglichen Werts. Damit wächst der Boden mit
    Schriftgröße und Knopfbreite, ohne den Wertebereich mitzuschleppen.

    Eine Ziffer Reserve kommt dazu: Wer 9,99 auf 10,00 stellt, soll nicht
    zusehen, wie das Feld nachwächst.
    """
    metrics = spin.fontMetrics()
    # **Gemessen wird, was dasteht — mit Komma, wenn das Fenster deutsch ist.**
    # ``spin.text()`` unten liefert den lokalisierten Text, die beiden Grenzen
    # kamen mit Punkt, und die Differenz landete über ``frame`` im Ergebnis.
    #
    # **Wie groß sie ist, hängt an der Schrift, und heute ist sie null**: In
    # der Standardschrift sind Punkt und Komma gleich breit (gemessen am
    # 30.08.2026, de_DE und en_GB, beide 108 px). Die Zeile steht trotzdem so,
    # denn genau davon soll die Rechnung nicht abhängen — eine schmalere
    # Ziffernschrift, eine andere Sprache mit anderem Trennzeichen, und aus
    # der Null wird ein Pixel, den niemand mehr sucht.
    widest = max(
        metrics.horizontalAdvance(localised(f"{spin.minimum():.{spin.decimals()}f}")),
        metrics.horizontalAdvance(localised(f"{spin.maximum():.{spin.decimals()}f}")),
    )
    frame = max(0, spin.sizeHint().width() - widest)
    return metrics.horizontalAdvance(spin.text() + "0") + frame


def align_forms(dialog: QWidget, *, apart: tuple[QWidget, ...] = ()) -> None:
    """Alle Formularzeilen eines Dialogs auf eine Beschriftungsspalte legen.

    Ein ``QFormLayout`` rechnet seine linke Spalte für sich, und ein Dialog
    trägt selten nur eines: Die Druckeinstellungen haben zehn (Vorderseite,
    acht Gruppen, Profilzuordnung), der Einstellungsdialog zwei. Gemessen am
    gebauten Fenster begannen die Felder dadurch an **zehn** verschiedenen
    Stellen zwischen 11 und 226 Punkten; im Einstellungsdialog bei 148 oben
    und 70 unten (Befunde B8 und B11 der Design-Durchsicht). Der Blick sucht
    dann in jeder Zeile neu, wo der Wert anfängt.

    Angeglichen wird **nach links, nicht nach rechts**. Die Feldbreiten sind
    eine getroffene Entscheidung — keines breiter, als sein Wert ist, siehe
    ``print_settings_dialog._editor`` —, und ein Feld für „z" so breit wie
    eines für ein Muster wäre die Rückkehr des handbreiten Kastens für
    „0,200". Die Startlinie dagegen hat niemand gewählt; sie ist ein Rest der
    Spaltenrechnung.

    Gerufen wird das am Ende des Aufbaus, wenn alle Zeilen stehen. Ein
    Abschnitt, der später aufgeht, ändert daran nichts: Die Breite ist dann
    schon gesetzt, und Qt vergrößert eine Beschriftung nur, es verkleinert
    sie nicht.

    ``apart`` nennt Bereiche mit eigener Kante — die Reiter der
    Druckeinstellungen stehen in einem Rahmen, ihre Felder beginnen ohnehin
    um dessen Innenrand versetzt. Ihre Formulare teilen eine Spalte unter
    sich; die längste Beschriftung eines verborgenen Reiters („Linienbreite
    erste Schicht“) zog sonst die Vorderseite auf 170 Punkte, wo 110 reichen.
    """

    def inside(form: QFormLayout, area: QWidget) -> bool:
        owner = form.parentWidget()
        return owner is not None and (owner is area or area.isAncestorOf(owner))

    forms = dialog.findChildren(QFormLayout)
    groups = [[form for form in forms if inside(form, area)] for area in apart]
    rest = [form for form in forms if not any(inside(form, area) for area in apart)]
    for group in (rest, *groups):
        labels: list[QWidget] = []
        for form in group:
            for row in range(form.rowCount()):
                item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    labels.append(widget)
        if not labels:
            continue
        widest = max(widget.sizeHint().width() for widget in labels)
        for widget in labels:
            widget.setMinimumWidth(widest)


def even_fields(dialog: QWidget) -> None:
    """Die gedeckelten Zahl- und Auswahlfelder eines Formulars gleich breit.

    Der Deckel je Feld bleibt der Grund (``print_settings_dialog._editor``):
    kein Kasten, der breiter ist als sein Wert. Gedeckelt war aber jedes Feld
    auf seinen **eigenen** Wunsch, und in „Das Wichtigste" standen sieben
    Felder in fünf Breiten zwischen 70 und 112 Punkten untereinander — eine
    Kante, die jede Zeile woanders hat, liest der Blick als Unordnung. Hier
    bekommt jedes Feld eines Formulars den größten Deckel seiner Nachbarn;
    ungedeckelte Felder (Haken, Farbknopf, Texte) bleiben, wie sie sind.
    """
    from PySide6.QtWidgets import QAbstractSpinBox, QComboBox

    unbounded = 16777215

    def editor_of(widget: QWidget | None) -> QWidget | None:
        # Das Feld selbst oder das erste Feld seiner Zeile — die
        # Druckeinstellungen tragen Feld, *Zurücksetzen* und Hinweis in einem
        # Halter.
        if isinstance(widget, (QAbstractSpinBox, QComboBox)):
            return widget
        line = widget.layout() if widget is not None else None
        first = line.itemAt(0) if line is not None and line.count() else None
        inner = first.widget() if first is not None else None
        return inner if isinstance(inner, (QAbstractSpinBox, QComboBox)) else None

    for form in dialog.findChildren(QFormLayout):
        editors: list[QWidget] = []
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            editor = editor_of(item.widget() if item is not None else None)
            if editor is not None and editor.maximumWidth() < unbounded:
                editors.append(editor)
        if len(editors) < 2:
            continue
        # Zahlen unter Zahlen und Auswahlen unter Auswahlen; liegen beide
        # Breiten nahe beieinander, eine Kante für alle. Eine Auswahl mit
        # langen Namen zieht die Zahlen daneben aber nicht mit.
        numbers = [editor for editor in editors if isinstance(editor, QAbstractSpinBox)]
        choices = [editor for editor in editors if isinstance(editor, QComboBox)]
        wanted = {
            id(group): max(editor.sizeHint().width() for editor in group)
            for group in (numbers, choices)
            if group
        }
        joint = len(wanted) == 2 and max(wanted.values()) <= min(wanted.values()) * 1.3
        for group in (numbers, choices):
            if not group:
                continue
            common = max(wanted.values()) if joint else wanted[id(group)]
            for editor in group:
                editor.setMinimumWidth(common)
                editor.setMaximumWidth(max(editor.maximumWidth(), common))


def describe_selection(result: EvaluationResult | None, object_id: ObjectId | None) -> Any:
    """Name, Größe und Volumen des gewählten Objekts, oder None."""
    if result is None or object_id is None:
        return None
    entry = result.scene.objects.get(object_id)
    if entry is None:
        return None
    return entry.name, entry.mesh.bounds.size, entry.mesh.volume


def _preview_pixels(widget: QWidget) -> int:
    """Wie groß ein Vorschaubild wird — an der Zeilenhöhe, nicht in Pixeln.

    Wer seine Schrift größer stellt, bekommt größere Zeilen; ein Bild in
    fester Größe säße dann in einer Zeile, die doppelt so hoch ist.

    **Der Faktor war 1,2 und ist 2,5 — bei Standardschrift also 40 statt 19
    Bildpunkte.** Hier stand vorher, größer gehe nicht: Die Karte sei 260
    Punkte breit, und ab Zeilenhöhe mal 1,7 habe „Dose Deckel" als „Dose Dec…"
    dagestanden. Die erste Zahl stimmt — die Karte ist bei jeder Fensterbreite
    bis 1920 genau 258 Punkte breit. Die Folgerung stimmt nicht mehr:
    Gemessen bleibt die Spalte „Objekt" bei **jeder** Vorschaugröße 165 Punkte
    breit, und `elidedText` kürzt den Namen weder bei 32 noch bei 40 noch bei
    48. Was der Satz beschrieb, war eine Spaltenaufteilung, die es so nicht
    mehr gibt.

    Damit blieb der Grund weg, und der Befund nicht: Bei 19 Punkten war ein
    Quader ein Fleck, in dem auch bei fünffacher Vergrößerung keine Form zu
    sehen ist — ein Bild, das man nicht erkennt, kostet Spaltenbreite und
    liefert nichts. Bei 40 ist die Platte als schräg liegender Körper
    erkennbar, mit Kante und Schattierung; bei 32 erkennt man sie auch, nur
    knapper. Gewählt ist 40, weil der Befund „halbe Größe ist keine Option"
    ausdrücklich ausschließt.

    Bezahlt wird das in Zeilenhöhe: 44 statt 23 Punkte. Das ist der ehrliche
    Preis — eine Karte zeigt halb so viele Objekte ohne Rollen. Er ist es
    wert, solange das Bild seine Aufgabe erfüllt; ein Fleck erfüllte sie nicht.

    Die Obergrenze von 56 hält das Bild aus der Namensspalte heraus, wenn
    jemand seine Schrift sehr groß stellt: Ein Drittel der 165 Punkte ist die
    Grenze, ab der die gemessene Reserve knapp wird.
    """
    return min(max(int(widget.fontMetrics().height() * 2.5), 40), 56)
