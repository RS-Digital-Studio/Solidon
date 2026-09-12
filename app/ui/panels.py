"""Die drei Panels links und der Prüfbericht rechts (Bauplan §2.5).

Drei einklappbare Abschnitte, keine drei Fenster: Objektbaum, Parameter,
Verlauf. Sie lesen aus dem Dokument und der letzten Auswertung, und sie ändern
nie selbst Geometrie — jede Änderung geht durch eine Operation (AGENTS.md
Regel 2).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from itertools import pairwise
from typing import Any, Final, cast

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QItemSelectionModel,
    QModelIndex,
    QObject,
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
    QFont,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core import drawing, expressions
from app.core.drawing import Theme as DrawingTheme
from app.core.errors import (
    ARRANGE_ON_BED,
    CANCEL,
    CHANGE_SELECTION,
    CHOOSE_PRINTER,
    CORRECT_INPUT,
    DECIMATE_MESH,
    EXPORT_AS_MESH,
    PLACE_ON_BED,
    REMOVE_SMALL_PARTS,
    REPAIR_AND_RETRY,
    SCALE_TO_FIT,
    SHOW_DETAILS,
    SHOW_HISTORY,
    SHOW_LOCATIONS,
    SHOW_STEP_VALUES,
    SPLIT_ALONG_LINE,
    SPLIT_MODEL,
    Action,
    AppError,
)
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.log import get_logger
from app.core.perceive.relations import FeatureActionGroup
from app.core.registry import REGISTRY, shown_of_twins
from app.core.registry.surfaces import MAX_MENU_ROWS as _MAX_MENU_ROWS
from app.core.scene import EvaluationResult
from app.core.scene.history import repair_is_available
from app.core.types import Document, Feature, Finding, MaterialSlot, ObjectId, OpId
from app.core.units import LengthUnit
from app.i18n import TranslatableText, sort_key, tr
from app.ui.dialogs import handlers_of
from app.ui.icons import OVERSAMPLING, icon, icon_name_for
from app.ui.labels import (
    LengthSpin,
    NumberSpin,
    choice_label,
    choice_note,
    compact_length,
    explain_choices,
    feature_label,
    feature_measure,
    feature_name,
    fill_parameter_units,
    kind_requirement,
    length,
    localised,
    spoiled_the_exact_body,
    value_line,
    value_text,
    volume,
)
from app.ui.leash import weak_slot
from app.ui.overlay import LEFT_WIDTH
from app.ui.palette import SEVERITY_ENCODING, Role, text_colour
from app.ui.style import NORMAL, TARGET_SIZE, TIGHT, make_danger, make_primary, rule, set_level
from app.ui.theme import UNDONE_COLOUR

_log = get_logger(__name__)

#: Zeichen je Schweregrad, aus der gemeinsamen Kodierung — Farbe steht nie
#: allein (§19.1).
SEVERITY_MARKER = {name: entry.symbol for name, entry in SEVERITY_ENCODING.items()}

#: Wie viele Operationen ein Kontextmenü flach zeigt, bevor es nach Kategorie
#: gruppiert. Dieselbe Zahl, die ``MAX_SUBMENU_ENTRIES`` in
#: ``tests/test_interface_limits.py`` der Menüleiste zieht, und aus demselben
#: Grund: darüber liest niemand mehr, er sucht.
# **Aus dem Kern, nicht als eigene Zahl.** Dieselbe Grenze aus §35 steht in
# ``registry/surfaces.py``, und dort gehört sie hin: Sie beschreibt, was ein
# Menü tragen kann, und der Kern baut die Menüstruktur. Zwei Zahlen für eine
# Grenze sind zwei Stellen, an denen jemand die eine erhöht.
MAX_MENU_ROWS = _MAX_MENU_ROWS

#: Datenrolle einer Verlaufszeile: **alle** Operationen, die sie umfasst, als
#: Tupel. Neben ``UserRole``, das die *eine* Operation zum Öffnen trägt und
#: bei einer Transaktion aus mehreren Schritten leer bleibt — ein Doppelklick
#: hätte dort keine, die er zeigen könnte. Die Mehrfachauswahl fragt diese
#: Rolle, weil sie die andere Frage stellt: was gehört zu dieser Zeile.
OPS_ROLE = int(Qt.ItemDataRole.UserRole) + 1
#: Die Transaktion, zu der eine Kindzeile gehört — daran hängt das Einklappen.
GROUP_ROLE = int(Qt.ItemDataRole.UserRole) + 2


#: Operationen, die am Kontextmenü **dieser** Merkmalsarten keine Zeile haben,
#: weil ein Griff im Bild sie dort anbietet — Operation → Merkmalsarten.
#:
#: *Zum Langloch ziehen* an der Bohrung: Der Langlochgriff
#: (``viewport.SLOT_HANDLE_OP``) sitzt an jeder Art, die ``slot_hole``
#: annimmt, und ein Zug daran **ist** die Handlung — direkter als eine Zeile,
#: die denselben Dialog öffnet. Die Zeile kostete außerdem die Grenze: Mit ihr
#: trug die Bohrung neun Handlungen, und ab neun genügt „Bausteine" allein
#: nicht mehr, um unter zwölf Zeilen zu kommen — ``folded_groups`` faltete dann
#: „Ändern", also alle neun auf einmal. Gemessen am 11.09.2026 mit fünf
#: Bausteinen und zwei festen Zeilen: bis acht Handlungen zwölf Zeilen und
#: „Bausteine" gefaltet, ab neun neun Zeilen und „Ändern" gefaltet. Dass
#: ``KEEP_VISIBLE`` „Ändern" schützt, half nicht: Der Schutz wählt unter den
#: Gruppen, die allein genügen, und ab neun war das nur noch diese eine.
#: Welche Zeile geht, hat Robert entschieden (11.09.2026): nicht *Prüfstück
#: erzeugen*, nicht die Grenze — die Zeile, die einen Griff hat.
#:
#: **Am Langloch bleibt sie.** Dort ist sie die einzige Operation, und ein Menü
#: aus *Ausblenden* wäre die Sackgasse, vor der ``prepare_ops.SLOT_FROM``
#: warnt. Und was hier steht, verschwindet nur aus diesem Menü: Menüleiste,
#: Befehlspalette, Chat und Kommandozeile lesen ``applies_to``, und das bleibt.
#: Der Griff liest es auch — ``tests/test_interface_limits.py`` prüft, dass er
#: an jeder Art sitzt, die hier steht, denn ohne ihn wäre die Zeile kein
#: Umweg, sondern der einzige Weg.
HANDLE_INSTEAD: Final[dict[str, frozenset[str]]] = {
    "slot_hole": frozenset({"hole"}),
}


def shown_at_feature(kind: str, entries: Sequence[Any]) -> tuple[Any, ...]:
    """Was von den Operationen einer Merkmalsart eine Zeile im Menü bekommt.

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


def _bundled(findings: list[Finding]) -> list[tuple[Finding, list[Finding]]]:
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
        key = (
            finding.code,
            finding.severity,
            str(finding.message),
            finding.source,
            finding.op_id,
            tuple((action.id, str(action.label), action.primary) for action in finding.suggestions),
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
    "export.needs_solid": (EXPORT_AS_MESH, SHOW_DETAILS),
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
    "split.too_many_parts": (SPLIT_ALONG_LINE, CHOOSE_PRINTER, SHOW_DETAILS),
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
    # hat (``gcode.printed_extent``). CuraEngine prüft seinen Bauraum nicht.
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
    "perceive.too_large": (DECIMATE_MESH,),
    # **Und seit dem Nachmittag auch der andere.** Der Absatz darüber begründet,
    # warum ``ingest.very_large`` den Knopf **nicht** bekam: Er trug keine
    # Objektkennung, und eine Handlung ohne Ziel landet auf der zufälligen
    # Auswahl. Seit `c45e70e7` trägt er eine — die Auswertung reicht sie nach,
    # wo der Name des Teils genau eine Ausgabe trifft (3d-druck-85). Damit gilt
    # die Begründung von oben für ihn genauso, und ihn jetzt stumm zu lassen
    # wäre derselbe Fehler in neuer Gestalt: Sein Text ist der, der „Dreiecke
    # verringern" beim Namen nennt, und der Knopf stünde an der Zeile daneben.
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
    # Reparieren hat getan, was ohne erfundene Fläche möglich war. Ein
    # zweiter Reparaturlauf und Kanten verfeinern führen von hier nur zurück;
    # die Defektkarte zeigt dagegen die Kanten, die wirklich übrig sind.
    "repair.still_open": (SHOW_LOCATIONS,),
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
    {"repair.still_open", "repair.self_intersections_skipped"}
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
    live_objects: Collection[ObjectId] | None = None,
) -> tuple[Action, ...]:
    """Nur im aktuellen Dokument ausführbare Handlungen anbieten."""
    offered = list(actions_for(finding))
    if _repair_was_attempted(finding, document) or not repair_is_available(
        document,
        stopped_at=stopped_at,
        op_id=finding.op_id,
        object_id=finding.object_id,
        live_objects=live_objects,
    ):
        offered = [action for action in offered if action.id != REPAIR_AND_RETRY.id]
    target = _object_for_finding(finding, document)
    if target is None or (live_objects is not None and target not in live_objects):
        offered = [action for action in offered if action.id != SHOW_LOCATIONS.id]
    return tuple(offered)


def as_error(finding: Finding, document: Document | None = None) -> AppError:
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
    return AppError(
        title=finding.message,
        detail=str(detail) if detail is not None else None,
        suggestions=finding.suggestions,
        object_id=_object_for_finding(finding, document),
        op_id=finding.op_id,
        values=dict(finding.values),
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
)


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

    ``names`` löst die Kennung zum Namen auf. Ohne die Zuordnung bleibt die
    Kennung stehen: „obj_2" ist weniger als „Klotz B", aber mehr als nichts.
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
            )
            for key in _LINE_VALUES
            if key in finding.values
            and not (finding.code in {"perceive.mended", "perceive.orphaned"} and key == "feature")
        ]
    )
    if finding.object_id and "object" not in finding.values:
        identifier = str(finding.object_id)
        extra.insert(0, (names or {}).get(identifier, identifier))
    if not extra:
        return str(finding.message)
    return f"{finding.message} — {' · '.join(extra)}"


def _origin_text(created_by: int | None, document: Document | None) -> str:
    """Aus welcher Operation und Transaktion ein Körper stammt (§18.8).

    Die Transaktion ist die Einheit, die der Verlauf zeigt und die ein Undo
    nimmt (§15.5) — sie zu nennen verbindet den Körper im Baum mit der Zeile
    im Verlauf. Fehlt das Dokument, bleibt die Operationsnummer.
    """
    if created_by is None:
        return ""
    text = f"{tr('aus Operation')} {created_by}"
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


def part_step_of(created_by: int | None, document: Document | None) -> tuple[Any, Any] | None:
    """Der Schritt und sein Registereintrag, wenn er einen **Baustein** setzte.

    Sonst ``None``. Gefragt wird über die Kategorie ``parts`` und nicht über
    den Namen der Operation: ``drill_hole`` erzeugt ebenfalls Merkmale mit
    Provenienz und ist kein Baustein, und ein Namensmuster wie ``insert_*``
    schwiege beim nächsten der siebenundzwanzig.

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
        return (entry, spec) if spec.category == "parts" else None
    return None


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


def _visible_rows(item: QTreeWidgetItem | None) -> int:
    """Wie viele Zeilen dieser Ast zeigt: er selbst plus, was offen darunter steht.

    Der Nachbar von ``_feature_item`` und aus demselben Grund rekursiv — der
    Baum ist unter einem Körper zwei Ebenen tief, seit die Merkmale eines
    Bausteins unter seinem Knoten stehen.
    """
    if item is None:
        return 0
    rows = 1
    if item.isExpanded():
        rows += sum(_visible_rows(item.child(index)) for index in range(item.childCount()))
    return rows


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
        painter.drawRoundedRect(
            QRectF(inset, inset, side - 2 * inset, side - 2 * inset),
            2.0 * scale,
            2.0 * scale,
        )
    finally:
        painter.end()
    return QIcon(image)


class ObjectTree(QWidget):
    """Objekte der Szene mit ihren Merkmalen, Herkunft und Größe (§18.8,
    §18.5).
    """

    selectionChanged = Signal(object)
    featureSelected = Signal(object)
    #: Alle gewählten Merkmale als Paare aus Körper und Kennung — für die
    #: Frage, wie weit zwei voneinander stehen.
    featuresSelected = Signal(list)
    """Ein im Baum gewähltes Merkmal — trägt seine ID, oder None."""
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
        self.tree = QTreeWidget(self)
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
        """Zeichnet die vorgemerkten Bilder — eines je Aufruf.

        Eines und nicht alle: Bei einem gescannten Teil kostet ein Bild achtzig
        Millisekunden, und fünf davon am Stück sind eine halbe Sekunde, in der
        das Fenster steht. So kommt jedes Bild einzeln nach, und dazwischen
        bleibt die Anwendung bedienbar — dasselbe Verfahren wie im Katalog.
        """
        if not self._pending:
            return
        item, stamp, entry = self._pending.pop(0)
        try:
            image = drawing.thumbnail(
                entry.mesh.raw,
                _preview_pixels(self.tree),
                theme=self._theme,
            )
        except Exception as problem:  # pragma: no cover - hängt am Netz
            # Ein Vorschaubild ist Beiwerk. Scheitert es, bleibt die Zeile, wie
            # sie war — eine Ansicht, die wegen eines Bildes nicht aufgeht,
            # wäre der teuerste mögliche Umgang mit einer Nebensache.
            _log.info("no preview for %s: %s", stamp, problem)
        else:
            found = _svg_icon(image, _preview_pixels(self.tree))
            self._previews[stamp] = found
            # Die Zeile kann inzwischen weg sein — eine neue Auswertung räumt
            # den Baum, während hier noch gezeichnet wird.
            if self.tree.indexFromItem(item).isValid():
                item.setIcon(0, found)
        if self._pending:
            QTimer.singleShot(0, self, self._render_pending)

    def show_scene(self, result: EvaluationResult | None, document: Document | None = None) -> None:
        selected = self.selected_objects()
        selected_feature = self.selected_feature()
        selected_features = self.selected_features()
        self._result = result
        self._document = document
        self.tree.clear()
        # Was noch nicht gezeichnet war, gehört zu Zeilen, die es nicht mehr
        # gibt. Der Vorrat bleibt: dieselben Körper kommen meist wieder.
        self._pending.clear()
        self._faces.clear()
        if result is None:
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
                tr("Flächen und Kanten einzeln bearbeitbar")
                if entry.kind == "brep"
                else tr("Einzelne Flächen und Kanten nicht bearbeitbar")
            )
            tip = f"{object_id} · {kind} · {entry.mesh.triangle_count} {tr('Dreiecke')} · {state}"
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
            if entry.kind == "brep":
                # Die ausführliche Folge steht im Tooltip; im schmalen Baum
                # muss die zweite Kodierung vollständig lesbar bleiben.
                item.setText(0, f"{entry.name}  ·  {tr('weiter bearbeitbar')}")
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
            alike: dict[tuple[str, str], int] = {}
            for other_id, other in entry.features.items():
                if _part_group(other.created_by, document) is None:
                    schluessel = (feature_name(other_id, other), feature_measure(other))
                    alike[schluessel] = alike.get(schluessel, 0) + 1
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
            made: dict[str, QTreeWidgetItem] = {}
            waiting: list[tuple[str, QTreeWidgetItem]] = []
            for feature_id, feature in entry.features.items():
                # Name links, Maß rechts. Vorher stand die ganze Beschriftung
                # links und rechts der Typ („hole", „face") — links war damit
                # abgeschnitten, was rechts gefehlt hat.
                child = QTreeWidgetItem(
                    [feature_name(feature_id, feature), feature_measure(feature)]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, object_id)
                child.setData(1, Qt.ItemDataRole.UserRole, feature_id)
                tip = _feature_tip(feature_id, feature, document)
                # An beiden Spalten, wie der Regelsatz es für Zeilen verlangt:
                # Wer eine Zeile nicht versteht, zeigt auf das unverständliche
                # Wort und nicht auf die Zahl daneben.
                child.setToolTip(0, tip)
                child.setToolTip(1, tip)
                child.setStatusTip(0, tip.replace("\n", " · "))
                child.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, tip)
                # Nur Flächen tragen ein eigenes Filament — `paint_slot` gilt
                # für `face` und `curved_face` und für nichts sonst. Eine
                # Bohrung bekommt deshalb kein Feld, das nichts täte.
                if getattr(feature, "kind", "") in ("face", "curved_face"):
                    self._faces.add((object_id, feature_id))
                    face_slots = {
                        mesh.slots[face] if mesh.slots else 0 for face in feature.face_indices
                    }
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
                    if alike[label] < BUNDLE_FROM:
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
                        roof.setStatusTip(0, note)
                        roof.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, note)
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
                # fehlt. Auch der Bausteinname bleibt: ``_feature_tip`` nennt die
                # Herkunft jeder Zeile.
                only = group.takeChild(0) if group.childCount() == 1 else None
                if only is not None:
                    where = item.indexOfChild(group)
                    item.removeChild(group)
                    item.insertChild(where, only)
                    only.setExpanded(True)
                    continue
                group.setExpanded(True)
            self.tree.addTopLevelItem(item)
            item.setExpanded(object_id in selected)
        self.tree.resizeColumnToContents(0)
        if len(selected_features) > 1:
            self.select_features(selected_features)
        else:
            self._restore(selected, selected_feature)
        self._fit()
        # Erst steht der Baum, dann kommen die Bilder nach. Andersherum wartet
        # der Nutzer auf eine Liste, die längst fertig gerechnet ist.
        if self._pending:
            QTimer.singleShot(0, self, self._render_pending)

    def _rows(self) -> int:
        """Die sichtbaren Zeilen — ein zugeklappter Ast zählt als eine.

        **Über alle Ebenen, nicht nur die erste.** Gezählt wurden lange die
        direkten Kinder, und das stimmte, solange der Baum zwei Ebenen hatte.
        Seit die Merkmale eines eingesetzten Bausteins unter seinem Knoten
        stehen, sind es drei — und dieser Knoten steht **immer** offen: Ein
        Körper mit sechs Verrundungen unter einem Einhänger meldete zwei
        Zeilen und zeigte acht. Die Karte bekam damit Höhe für zwei und einen
        Rollbalken, den es an dieser Stelle nicht geben soll.

        Dieselbe Ebenenblindheit hatte ``_restore`` schon einmal: Ein Klick im
        Viewport fand das Merkmal nicht, weil es eine Ebene tiefer lag. Wer
        eine Ebene einzieht, sucht die Stellen, die über Ebenen laufen.
        """
        return sum(
            _visible_rows(self.tree.topLevelItem(index))
            for index in range(self.tree.topLevelItemCount())
        )

    def wanted_height(self) -> int:
        """Die Höhe, bei der jede Zeile zu sehen wäre."""
        return view_chrome(self.tree) + self._rows() * row_height_of(self.tree)

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
        from app.ui.filament_picker import shown_colour, unpainted_colour

        if slots:
            slot = slots[0]
            colour = shown_colour(int(slot.index), slot.colour)
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
        item.setStatusTip(FILAMENT_COLUMN, hint)
        # Regel 18: Der Bildschirmleser bekommt den Namen, nicht die Farbe.
        item.setData(FILAMENT_COLUMN, Qt.ItemDataRole.AccessibleDescriptionRole, hint)
        item.setData(FILAMENT_COLUMN, Qt.ItemDataRole.UserRole, feature_id)

    def _on_cell_clicked(self, index: QModelIndex) -> None:
        """Ein Klick in die Filamentspalte fragt nach dem Filament."""
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
        fit_to_rows(self.tree, self._rows(), room=self._room)
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
            self.tree.clearSelection()
            if chosen:
                self._restore(tuple(chosen), None)
            else:
                self._on_selection()
            return
        self.tree.clearSelection()
        if object_id is not None:
            self._restore((object_id,), None)

    def select_objects(self, object_ids: Sequence[ObjectId]) -> None:
        """Mehrere Körper auf einmal wählen — die Sammelzeile des Prüfberichts.

        Eine Zeile „(9) Ausrichtung über die Schichtanalyse gesucht." meint
        neun Körper; ihr Klick zeigt alle neun, nie den ersten zufälligen.
        Derselbe Weg wie ``add`` in :meth:`select_object`, nur in einem Zug.
        """
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
        dasselbe Menü, wenn jemand mit rechts auf einen Körper klickt. §18.5
        nennt das Kontextmenü am Merkmal den Ort für Weg 1 — zwei Menüs mit
        derselben Aufgabe wären zwei Gelegenheiten, auseinanderzulaufen.
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
        item = self.tree.itemAt(position)
        if item is not None:
            # Der Rechtsklick meint die Zeile darunter. Ohne diese Auswahl
            # öffnete sich zwar das passende Kontextmenü, der Dialog erbte
            # aber ein vorher gewähltes Merkmal oder keines — ein Gewinde
            # stand dann nicht in der gerade angeklickten Bohrung.
            self.tree.clearSelection()
            item.setSelected(True)
            self.tree.setCurrentItem(item)
        menu = self.context_menu()
        if menu is not None:
            menu.exec(self.tree.viewport().mapToGlobal(position))

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
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        outer.addWidget(self._scroll)
        outer.addWidget(self.add_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self._outer = outer
        self._fit()

    def _around_the_rows(self) -> int:
        """Was fest um die Zeilen herum steht: Knopf, Ränder, Abstände.

        Aus den Wunschhöhen gerechnet und nicht aus den gelegten — dieselbe
        Bedingung, unter der die ganze Verteilung stillsteht
        (``OverlayHost._share_room``). Wortgleich mit
        ``FilamentPanel._around_the_list`` ist das nicht: Dort stehen ein
        Hinweis und drei Knöpfe, hier einer.
        """
        margins = self._outer.contentsMargins()
        gaps = max(self._outer.count() - 1, 0) * self._outer.spacing()
        return margins.top() + margins.bottom() + gaps + self.add_button.sizeHint().height()

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
        fill_parameter_units(editor, selected)
        editor.setProperty("parameterName", name)
        editor.setAccessibleName(tr("Einheit"))
        editor.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        editor.activated.connect(self._unit_activated)
        self._unit_editors[name] = editor
        return editor

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
        details.setStatusTip(note)
        details.setAccessibleName(tr("Parameter ändern"))
        details.setProperty("parameterName", name)
        details.clicked.connect(self._details_clicked)
        layout.addWidget(details)
        self._detail_buttons[name] = details
        self._form.addRow(title, row)
        self._remember_row(name, row)

    def show_document(self, document: Document) -> None:
        while self._form.rowCount():
            self._form.removeRow(0)
        self._editors.clear()
        self._unit_editors.clear()
        self._detail_buttons.clear()
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
                self._add_parameter_row(name, f"{parameter.title or name}", label, unit)
                # Auch die abgeleitete Zeile: Ihr Ausdruck ist genau das, was
                # man an ihr ändern will, und bearbeiten lässt sie sich sonst
                # nirgends.
                continue
            editor = NumberSpin(self)
            editor.setDecimals(2)
            editor.setMinimum(parameter.minimum if parameter.minimum is not None else -100_000.0)
            editor.setMaximum(parameter.maximum if parameter.maximum is not None else 100_000.0)
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
            self._editors[name] = editor
            self._add_parameter_row(name, f"{parameter.title or name}", editor, unit)
        self._fit()


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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._open_groups: set[str] = set()
        """Die Transaktionen, deren Teilschritte gerade offen stehen.

        Gemerkt über den Neuaufbau hinweg: ``show_document`` läuft nach jeder
        Änderung, und ein Verlauf, der bei jedem Schritt wieder zuklappt,
        nähme dem Kunden gerade das, was er sich eben aufgemacht hat.
        """
        self.list = QListWidget(self)
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
                "Doppelklick öffnet die Operation und ihre Parameter. "
                "Mit Strg oder Umschalt mehrere Schritte wählen."
            )
        )
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
        self.remove_action = QAction(tr("Schritt löschen …"), self.list)
        self.remove_action.setShortcut(QKeySequence("Del"))
        self.remove_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.remove_action.triggered.connect(self._request_selected_removal)
        self.list.addAction(self.remove_action)
        self._room: int | None = None
        """Wie beim Objektbaum: die zugeteilte Höhe, ``None`` bis sie kommt."""
        self._bakeable: frozenset[int] = frozenset()
        """Formsitzungen, deren Stand sich festschreiben lässt — also die, die
        noch aus ihren Zügen gerechnet werden."""
        # Wie beim Objektbaum: ein Satz statt eines stummen Kastens.
        self._empty = QLabel(_empty_history_text(), self)
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._empty.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        fit_wrapped(self._empty)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._empty)
        layout.addWidget(self.list)

    def wanted_height(self) -> int:
        """Die Höhe, bei der jeder Schritt zu sehen wäre."""
        return view_chrome(self.list) + self.list.count() * row_height_of(self.list)

    def least_height(self) -> int:
        """Und die, unter die diese Karte nicht geht (siehe ``fit_to_rows``).

        Der leere Verlauf ist der Fall, an dem es auffiel: ``wanted_height``
        meldete vier Pixel, der Boden gab hundertzwölf, und die Überlagerung
        verteilte nach den vier.
        """
        if self.list.count() == 0:
            return least_empty_height(self._empty)
        return least_height_of(self.list)

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
        fit_to_rows(self.list, self.list.count(), room=self._room)
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
        self.list.clear()
        titles = {entry.id: _op_title(entry.op) for entry in document.ops}
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
        deleted_ids = frozenset(deleted)
        self._bakeable = frozenset(
            entry.id
            for entry in document.ops
            if entry.op == "sculpt_strokes" and not entry.params.get("baked")
        )
        for transaction in document.transactions:
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
            number = f"{single}  " if single is not None else ""
            item = QListWidgetItem(f"{number}{transaction.title}{by}")
            if stopped_at is not None and stopped_at in transaction.ops:
                # §15.3: die betroffenen Operationen werden im Verlauf markiert.
                item.setText(f"! {item.text()}")
            item.setToolTip(
                f"{transaction.id} · {tr('Ops')} "
                + ", ".join(str(entry) for entry in transaction.ops)
            )
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
            active_ops = tuple(op_id for op_id in transaction.ops if op_id not in deleted_ids)
            if transaction.ops and not active_ops:
                item.setText(f"{item.text()}  ({tr('gelöscht')})")
                font = QFont(item.font())
                font.setStrikeOut(True)
                item.setFont(font)
                item.setForeground(QColor(UNDONE_COLOUR))
            if len(transaction.ops) == 1 and active_ops:
                item.setData(Qt.ItemDataRole.UserRole, transaction.ops[0])
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
                    child = QListWidgetItem(f"    {op_id}  {titles.get(op_id, '')}")
                    child.setData(GROUP_ROLE, transaction.id)
                    child_symbol = _op_icon_name(
                        next((entry.op for entry in document.ops if entry.id == op_id), "")
                    )
                    if child_symbol:
                        child.setIcon(icon(child_symbol, self.list))
                    if op_id not in deleted_ids:
                        child.setData(Qt.ItemDataRole.UserRole, op_id)
                        child.setData(OPS_ROLE, (op_id,))
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

        self._fit()
        self.list.scrollToBottom()

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
        single_op = int(op_id) if op_id is not None and len(op_ids) == 1 else None
        if single_op is not None:
            action = menu.addAction(tr("Parameter ändern …"))
            action.triggered.connect(
                lambda _checked=False, chosen=single_op: self.operationActivated.emit(chosen)
            )
        remove = menu.addAction(tr("Schritt löschen …"))
        remove.triggered.connect(
            lambda _checked=False, chosen=op_ids: self.removalRequested.emit(chosen)
        )
        if single_op is not None and single_op in self._bakeable:
            # Nur an einer Formsitzung, und nur an einer, die noch gerechnet
            # wird: Ein Eintrag, der an jedem Schritt steht und an fast keinem
            # etwas tut, ist einer, den man nicht mehr liest.
            frozen = menu.addAction(tr("Stand festschreiben …"))
            frozen.triggered.connect(
                lambda _checked=False, chosen=single_op: self.bakeRequested.emit(chosen)
            )
        menu.exec(self.list.viewport().mapToGlobal(position))


#: Ab wie vielen Befunden der Bericht seine Filterzeile zeigt.
#:
#: Zwei, denn bei einem einzigen Befund kann ein Filter nur ihn treffen oder die
#: Zeile „Kein Befund passt zu …" erzeugen — und bei null zeigte der Bericht ein
#: Suchfeld, eine Filterauswahl und einen leeren Kasten für nichts.
FILTER_FROM = 2


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
        self.ok_button.setStatusTip(why)
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
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return ()
        return dialog.chosen()


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
        """Kennung zu Namen — aus der gezeigten Szene und aus allen Namen, die
        die Auswertung je vergeben hat. Siehe :meth:`show_result`."""
        self._document: Document | None = None
        """Für Herkunft, Zielableitung und ausführbare Berichtshandlungen."""
        self._stopped_at: OpId | None = None
        """Der wirklich angehaltene Schritt der gerade gezeigten Auswertung."""
        self._live_objects: frozenset[ObjectId] = frozenset()
        """Die wirklich ausgewerteten Körper, nicht nur geplante Ausgänge."""
        self._findings: list[Finding] = []
        """Die rohen Befunde hinter den Zeilen. Die Liste im Fenster ist eine
        *Darstellung* davon (gebündelt, sortiert) — wer Zeilen aus Zeilen neu
        baut, liest ersetzte Bündel-Findings zurück und zerlegt die Bündelung.
        Genau das tat ``_resort`` nach dem ersten ``add_findings``."""
        self._alerts = 0
        """Fehler und Warnungen im aktuellen Bericht — siehe :meth:`alerts`."""
        self.list = QListWidget(self)
        self.list.setObjectName("reportFindings")
        self.list.setAccessibleName(tr("Befunde"))
        # §2.7 schreibt die Sätze, die hier stehen — im schmalen rechten
        # Bereich endeten sie mitten im Wort hinter einer horizontalen
        # Bildlaufleiste. Umbruch statt Abschneiden: die Leiste bleibt aus,
        # und kein Befund wird auf „…" gekürzt.
        self.list.setWordWrap(True)
        self.list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setMinimumHeight(TARGET_SIZE)
        # §18.4 sagt „Klick auf eine Warnung fährt die Kamera hin" —
        # ``itemActivated`` allein hieß aber Doppelklick oder Eingabetaste,
        # und wer einmal klickte, bekam nichts. Beide Wege führen zum Ort;
        # dass ein Doppelklick dann zweimal fährt, ist dasselbe Ziel.
        self.list.itemClicked.connect(self._on_activated)
        self.list.itemActivated.connect(self._on_activated)
        # Und was dagegen hilft, steht im Kontextmenü — siehe :meth:`_on_menu`.
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_menu)
        self.summary = QLabel(tr("Keine Befunde."), self)
        self.summary.setWordWrap(True)
        # Der letzte Meter: Ist nichts zu beanstanden und liegt ein Körper da,
        # steht der nächste Klick genau hier — nicht drei Menüs weiter.
        self.to_slicer = QPushButton(tr("An den Slicer übergeben …"), self)
        self.to_slicer.setMinimumHeight(TARGET_SIZE)
        self.to_slicer.setToolTip(
            tr("Druckeinstellungen prüfen und das Teil an den eingerichteten Slicer geben.")
        )
        self.to_slicer.setStatusTip(self.to_slicer.toolTip())
        # Kein Hauptknopf: Im Ruhezustand trägt genau ein Element den Akzent,
        # und das ist *Auf das Bett setzen* (`tests/test_resting_state.py`).
        self.to_slicer.setVisible(False)
        self.to_slicer.clicked.connect(self.slicerRequested)
        # Die Kennzahlen darunter: was der Bericht in Sätzen sagt, hier als
        # Zahlen zum Vergleichen und Weitergeben.
        self.facts = QLabel("", self)
        self.facts.setWordWrap(True)
        self.facts.setProperty("level", "caption")
        self.facts.setVisible(False)

        # Ein Bericht mit hundert Hinweisen und zwei Fehlern versteckt die zwei.
        # Gefiltert wird über den Text und über den Schweregrad; beides
        # zusammen, weil „Wandstärke" und „nur die Fehler" verschiedene Fragen
        # sind (§17.3).
        self.search = QLineEdit(self)
        self.search.setMinimumHeight(TARGET_SIZE)
        self.search.setPlaceholderText(tr("Befunde durchsuchen …"))
        self.search.setAccessibleName(tr("Befunde durchsuchen"))
        self.search.textChanged.connect(self._refilter)
        self.severity = QComboBox(self)
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
        # Der leere Bericht ist der häufigste — und er zeigte ein Suchfeld, eine
        # Filterauswahl und einen leeren Kasten darunter. Drei Bedienelemente
        # für nichts, und der Satz „Keine Befunde." dazwischen. Was es nicht zu
        # filtern gibt, bekommt keinen Filter (siehe ``_show_controls``).

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        layout.addWidget(self.summary)
        layout.addWidget(self.to_slicer)
        # Wenn der Filter alles wegnimmt, steht sonst ein leerer Rahmen da und
        # sagt nicht, ob nichts passt oder ob der Bericht leer ist. Ein Label
        # und kein Listeneintrag: gefiltert wird über ``setHidden``, die Liste
        # bleibt gefüllt, und ein Eintrag darin wäre beim nächsten Filtern im
        # Weg.
        self._nothing = QLabel("", self)
        self._nothing.setWordWrap(True)
        self._nothing.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        self._nothing.setVisible(False)

        # **Was gegen den gewählten Befund hilft, steht darunter.** Gebaut waren
        # die Handlungen längst, nur hingen sie an einem Rechtsklick auf eine
        # Listenzeile — und §2.7 verspricht „anklickbare Handlungen", nicht
        # welche zum Suchen. Der Fehlerdialog hat dafür seit je Knöpfe; der
        # Bericht, in dem die häufigeren Fälle landen, hatte keine. Leer bleibt
        # die Zeile unsichtbar, wie die Filterzeile über der leeren Liste.
        self._offers = QWidget(self)
        self._offers.setVisible(False)
        # Untereinander und über die ganze Breite: Zwei längere Handlungen
        # passten im schmalen Prüfbericht nicht nebeneinander. Der primäre
        # Knopf begann sichtbar außerhalb der Karte und verlor „Re“ von
        # „Reparieren“. Übersetzungen dürfen die Handlung nicht abschneiden.
        self._offer_row = QVBoxLayout(self._offers)
        self._offer_row.setContentsMargins(0, TIGHT, 0, 0)
        self._offer_row.setSpacing(TIGHT)
        self.list.itemSelectionChanged.connect(self._show_offers)

        layout.addWidget(self.facts)
        layout.addLayout(filter_row)
        layout.addWidget(self._nothing)
        layout.addWidget(self.list)
        layout.addWidget(self._offers)

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
        row = self._offer_row
        while row.count():
            item = row.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                # **Verstecken, nicht elternlos machen** (RM-101).
                # ``setParent(None)`` macht aus einem Kind-Widget ein
                # Top-Level-Fenster — ein Knopf „Auf das Bett setzen", der
                # allein auf dem Bildschirm steht, bis ``deleteLater`` die
                # nächste Runde der Ereignisschleife erreicht. Gemessen am
                # 12.09.2026: vier solche Knöpfe nach einem Befundwechsel,
                # zwei davon sichtbar. Dasselbe Wissen steht seit dem
                # Skizzeneditor zweimal im Code
                # (``MainWindow._close_sketch``, ``SketchEditor.take_side_box``)
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
            [
                action
                for action in actions_for_document(
                    finding,
                    self._document,
                    stopped_at=self._stopped_at,
                    live_objects=self._live_objects,
                )
                if action.id in handlers
            ]
            if finding is not None
            else []
        )
        for action in offered:
            button = QPushButton(str(action.label), self._offers)
            button.setToolTip(str(finding.message) if finding is not None else "")
            if action.primary:
                make_primary(button)
            # ``weak_slot`` und nicht ein Lambda: ``handlers`` hält gebundene
            # Methoden des Fensters, und ein Lambda, das es fängt, schließt
            # den Ring Panel → Knopf → Handler → Fenster — gemessen hielten
            # zehn von zehn Wirten mit gewähltem Befund ihr Loslassen aus.
            # Die Handler holt der Klick deshalb selbst, frisch.
            button.clicked.connect(weak_slot(self, ReportPanel._run_action, action.id))
            row.addWidget(button)
        self._offers.setVisible(bool(offered))

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
            members: dict[str, Finding] = item.data(_MEMBERS_ROLE) or {}
            if handler is not None:
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
        Suchfeld, eine Filterauswahl und einen leeren Listenkasten. Drei
        Elemente, von denen keines etwas tun kann, und der einzige Satz mit
        Inhalt („Keine Befunde.") stand darüber wie eine Überschrift.

        Die Schwelle ist **zwei**, nicht eins: Bei einem einzigen Befund kann
        ein Filter nur ihn selbst treffen oder die Zeile „Kein Befund passt zu
        …" erzeugen. Beides ist keine Auskunft, die jemand gesucht hat.
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
        self._live_objects = frozenset(result.scene.objects) if result is not None else frozenset()
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
        for finding, members in _bundled(_by_severity(self._findings)):
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
            if any(
                action.id in handlers
                for action in actions_for_document(
                    finding,
                    self._document,
                    stopped_at=self._stopped_at,
                    live_objects=self._live_objects,
                )
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
            message = f"({len(members)}) {sentence}"
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
            if len(bodies) == 1:
                context.append(self._names.get(bodies[0], bodies[0]))
            if finding.op_id is not None:
                step = f"{tr('Schritt')} {finding.op_id}"
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
            item = QListWidgetItem(message)
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
            if any(one.location != location for one in members[1:]):
                location = None
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
                "count": len(members),
                listed: names,
            }
            finding = dataclasses.replace(
                finding,
                message=message,
                feature_ids=feature_ids,
                values=values,
                location=location,
                # Verschiedene Vorschläge trennen schon den Gruppenschlüssel:
                # Eine verdichtete Fehlerzeile darf nie ihren Ausweg verlieren.
                suggestions=members[0].suggestions,
            )
        else:
            if finding.code == "perceive.orphaned":
                # Der Kernbefund bleibt für Agent, CLI und Datei kanalneutral.
                # Erst die sichtbare Zeile darf den konkreten UI-Klick nennen.
                finding = dataclasses.replace(
                    finding,
                    message=tr(
                        "Ein Formdetail ist nach diesem Schritt nicht mehr automatisch "
                        "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; "
                        "die Bearbeitung bleibt erhalten."
                    ),
                )
            item = QListWidgetItem(_line_for(finding, self._names))
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
        details = [f"{tr('Herkunft')}: {origin_label(finding.source)}"]
        step = _origin_text(finding.op_id, self._document)
        if step:
            details.append(step)
        details.extend(value_line(key, value) for key, value in finding.values.items())
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
        if alerts != self._alerts:
            self._alerts = alerts
            self.alertsChanged.emit(alerts)
        # Der Knopf zum Slicer steht, sobald kein Fehler mehr im Weg ist und
        # ein Körper da ist — auch neben Warnungen und Hinweisen, die den
        # Druck nicht verhindern. Ohne Körper gibt es nichts zu übergeben.
        self.to_slicer.setVisible(counts["error"] == 0 and bool(self._live_objects))
        if not any(counts.values()):
            self.summary.setText(
                tr("Keine Befunde. Das Teil ist druckbereit.")
                if self._live_objects
                else tr("Keine Befunde.")
            )
            return
        self.summary.setText(
            f"{counts['error']} × {tr('Fehler')} · "
            f"{counts['warning']} × {tr('Warnung')} · "
            f"{counts['info']} × {tr('Hinweis')}"
        )

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

    def _measure_up(self, result: EvaluationResult | None) -> None:
        """Die Kennzahlen über den Befunden — wasserdicht, Volumen, Teile.

        Ein Bericht aus Sätzen sagt, *was* zu tun ist; er sagt nicht, woran man
        gerade ist. Diese drei Zahlen tun das, und sie kosten nichts: Sie
        stehen im ausgewerteten Netz und werden nicht gerechnet.

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
            tr("wasserdicht")
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
        self.facts.setText(
            f"{closed} · {volume(content)} · {parts} {tr('Teil') if parts == 1 else tr('Teile')}"
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
        parts.extend(
            value_line(key, value)
            for key, value in finding.values.items()
            if key not in ("count", "object", "objects", "entries", "name")
        )
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
        offers = actions_for_document(
            finding,
            self._document,
            stopped_at=self._stopped_at,
            live_objects=self._live_objects,
        )
        handlers = handlers_of(self)
        offered = [action for action in offers if action.id in handlers]
        if not offered:
            return

        menu = QMenu(self)
        chosen: dict[Any, Any] = {}
        for action in offered:
            chosen[menu.addAction(str(action.label))] = action
        # Die Stubs versprechen eine Aktion; wer das Menü wegklickt, bekommt
        # None. Dieselbe Notlüge wie bei ``currentItem`` in der Palette.
        picked = cast(QAction | None, menu.exec(self.list.viewport().mapToGlobal(position)))
        if picked is None:
            return
        self._run_action_for(item, chosen[picked].id)


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

    Zur Laufzeit übersetzt, nicht beim Import — die Sprache kann wechseln.
    ``test_feature_panel`` hält die Schlüssel mit dem Literal des Kerns
    deckungsgleich; ein neuer Wert dort ist sonst ein ``KeyError`` mitten in
    der Merkmalsauswahl.
    """
    return {
        "same_target_dimensions": tr("Gleiches Ausgangsmaß für diese Änderung."),
        "complete_surface_patch": tr("Die vollständige bearbeitete Form stimmt überein."),
        "parallel_axes": tr("Die Achsen sind parallel ausgerichtet."),
        "shared_boundary_role": tr("Die Merkmale haben dieselbe Rolle in ihrer Bohrungskette."),
        "translation_consistent": tr("Die zugehörigen Abschnitte liegen gleich zueinander."),
    }


def _group_reason_texts() -> dict[str, str]:
    """Ein Satz je Grund, warum ein Merkmal nicht sicher dazugehört."""
    return {
        "selected_feature_unavailable": tr("Das gewählte Merkmal ist nicht mehr vorhanden."),
        "action_not_applicable": tr("Diese Handlung passt nicht zu den weiteren Merkmalen."),
        "ambiguous_cavity_chain": tr("Die zugehörigen Bohrungsabschnitte sind nicht eindeutig."),
        "cavity_topology_unavailable": tr(
            "Die Verbindung der Bohrungsabschnitte ist nicht sicher erkannt."
        ),
        "dimensions_unavailable": tr("Die benötigten Maße sind nicht sicher erkannt."),
        "complete_shape_unavailable": tr("Die vollständige Form ist nicht sicher vergleichbar."),
        "orientation_unavailable": tr("Die Ausrichtung ist nicht sicher erkannt."),
        "relative_position_unavailable": tr(
            "Die Lage der zugehörigen Abschnitte ist nicht sicher erkannt."
        ),
    }


#: Die Handlungen, deren Knopf unmittelbar in die Platzierung führt.
#:
#: **Eine Aufzählung und keine Regel**, weil es eine Bedienentscheidung ist und
#: keine Fähigkeit: *Merkmal verschieben* und *verdoppeln* tragen ihre Zahlen
#: als Felder daneben und tun auf Klick, was dort steht; *Zum Langloch ziehen*
#: ändert die **Form** eines Lochs, und wer sie ändert, will dabei sehen, wo es
#: sitzt (Robert, 10.09.2026). Wer eine weitere Handlung so haben will, trägt
#: sie hier ein — und nimmt ihr damit den unmittelbaren Klick.
LEADS_INTO_THE_VIEW: Final[frozenset[str]] = frozenset({"slot_hole", "resize_hole"})


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
    take: Callable[[Mapping[str, Any]], None] | None = None
    """Werte von außen in die Felder dieser Handlung schreiben.

    Der Gegenweg zu :attr:`run`: Ein Zug im Bild schlägt Zahlen vor, und sie
    gehören in die Felder, aus denen das Übernehmen liest — nicht in eine
    eigene Leiste daneben (Robert, 11.09.2026: „die untere leiste uns sparen
    und nur die rechte verwenden mit dem was schon drin ist")."""
    in_view: Callable[[], None] | None = None
    """Der Weg ins Bild — oder nichts, wo die Handlung keine Stelle hat.

    Getrennt von :attr:`run`, seit der 11.09.2026 die beiden auseinanderhält:
    Bis dahin *war* das Übernehmen der Weg ins Bild, und wer eine Bohrung
    ändern wollte, landete in der Platzierung statt bei seinem Ergebnis
    (Robert: „auch 2 mal übernehmen einmal unten und einmal rechts")."""


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

    **Was nicht geht, steht als Satz und nicht als graues Feld.** Eine
    Handlung ohne Operation bringt ihren Grund mit („Eine Verrundung folgt
    ihrer Kante"); eine Lücke ließe den Kunden raten, ob sie fehlt oder
    vergessen wurde (Regel 17 dem Geist nach).
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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows = QVBoxLayout(self)
        self._rows.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        self._rows.setSpacing(TIGHT)
        # Der leere Zustand ist ein Satz und keine leere Fläche: Wer nichts
        # gewählt hat, soll lesen, was ihn hierher bringt (§2.7).
        self._empty = QLabel(
            tr(
                "Kein Merkmal gewählt. Klicken Sie eine Bohrung, eine Fläche oder eine "
                "Verrundung an — im Objektbaum oder im Bild."
            ),
            self,
        )
        self._empty.setWordWrap(True)
        fit_wrapped(self._empty)
        self._rows.addWidget(self._empty)
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
        self._every = QCheckBox("", self)
        self._every.setVisible(False)
        self._rows.addWidget(self._every)
        self._armed_title = QLabel("", self)
        self._armed_title.setWordWrap(True)
        self._armed_title.hide()
        self._rows.addWidget(self._armed_title)
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
        self._in_view = QPushButton(tr("Im Bild einstellen"), self)
        self._in_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._in_view.clicked.connect(self._show_armed_in_view)
        self._in_view.setVisible(False)
        self._rows.addWidget(self._in_view)
        self._apply = make_primary(QPushButton(tr("Übernehmen"), self))
        self._apply.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply.clicked.connect(self._run_armed)
        self._apply.setVisible(False)
        self._rows.addWidget(self._apply)
        self._cancel = make_danger(QPushButton(tr("Abbrechen"), self))
        self._cancel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._cancel.setToolTip(tr("Verwirft, was im Bild wartet — gerechnet wird nichts."))
        self._cancel.setStatusTip(self._cancel.toolTip())
        self._cancel.clicked.connect(self.cancelRequested)
        self._cancel.setVisible(False)
        self._rows.addWidget(self._cancel)
        self._measuring = False
        """Ob die Maße des gezeigten Merkmals gerade im Bild stehen — dann
        steht *Abbrechen* unter dem Übernehmen."""
        self._rows.addStretch(1)
        self._built: list[QWidget] = []
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
        """Je Handlung ihr Titel, ihr Satz und was sie tut.

        Die Knöpfe je Handlung sind am 10.09.2026 gefallen; was bleibt, ist
        **einer** unten, und der braucht die Handlungen als Nachschlagewerk."""
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

    def clear(self) -> None:
        """Zurück auf den leeren Zustand.

        Versteckt und gelöscht, nicht elternlos gemacht: ``setParent(None)``
        macht aus einem Kind-Widget ein eigenes Fenster, bis der Löschauftrag
        die Ereignisschleife erreicht (RM-101, dieselbe Stelle wie in
        :meth:`ReportPanel._show_offers`).
        """
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
        self._armed = None
        self._explanations.clear()
        self._dots.clear()
        self._apply.setVisible(False)
        self._in_view.setVisible(False)
        self._cancel.setVisible(False)
        self._into_view = None
        self._in_view_key = None
        self._armed_title.hide()
        self._every.setVisible(False)
        self._every.setChecked(False)
        self._empty.setVisible(True)

    def show_feature(
        self,
        feature_id: str,
        feature: Feature,
        *,
        features: Mapping[str, Feature] | None = None,
        mesh: MeshData | None = None,
        alone: bool = False,
    ) -> None:
        """Die Handlungen dieses Merkmals als Zeilen — Reihenfolge aus dem Kern.

        ``alone`` sagt, dass dieser Körper der einzige im Projekt ist: Dann gibt
        es kein Gegenstück, und der Satz über die Passung entfällt.

        Gleichartige Merkmale werden je Handlung durch den Kern belegt:
        Eine Maßänderung braucht andere Übereinstimmungen als das Versetzen
        einer ganzen Bohrungskette. ``mesh``
        belegt die topologische Kette einer mehrteiligen Senkung; optional bleibt
        es für Aufrufer, die nur die einzelne Merkmalsauskunft brauchen.
        """
        from app.core.perceive import relations
        from app.core.perceive.actions import actions_for

        cavity: tuple[Feature, ...] = ()
        if features is not None:
            cavity = (
                relations.cavity_chain_at(feature, features, mesh)
                if mesh is not None
                else relations.bore_and_widening_at(feature, features)
            ) or ()
        self.clear()
        self._feature_id = feature_id
        self._empty.setVisible(False)

        heading = QLabel(f"{feature_name(feature_id, feature)}  ·  {feature_measure(feature)}")
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
                measured=localised(f"{float(diameter):.2f}"),
                feature=feature,
                features=features,
                mesh=mesh,
                cavity=cavity,
            )
            note = QLabel(said, self)
            note.setWordWrap(True)
            note.setStatusTip(said)
            fit_wrapped(note)
            self._rows.insertWidget(self._rows.count() - 1, note)
            self._built.append(note)

        actions = actions_for(feature, features, mesh=mesh, cavity=cavity)
        if features is not None and mesh is not None:
            self._groups = {
                group.action: group
                for group in relations.alike_for_actions(
                    (str(action.op) for action in actions if action.op),
                    feature_id,
                    features,
                    mesh,
                )
            }
        # **Derselbe Grund steht einmal da, nicht fünfmal.** Die abgelehnten
        # Handlungen tragen ihren Satz je Zeile, und bei den Arten, an denen
        # gar nichts geht, ist es immer wieder derselbe: An einer Fläche
        # sagten fünf Zeilen wörtlich „Eine Fläche gehört zur Oberfläche des
        # Körpers …", an einer Verrundung vier von fünf „Eine Verrundung
        # gehört zu ihrer Kante …". Roberts Halter hat zehn Flächen und neun
        # Verrundungen; wer eine davon anklickt, liest fünf Zeilen und findet
        # in keiner etwas, das er tun kann (Messung 04.09.2026).
        #
        # Weggelassen wird dabei **nichts**: Die Zeile nennt weiter jede
        # Handlung beim Namen, damit niemand rät, ob sie fehlt oder vergessen
        # wurde (`actions_for` begründet genau das). Sie nennt sie nur
        # zusammen, wenn sie denselben Satz teilen.
        for action in _folded(actions):
            self._separate()
            row = self._build_action(action)
            self._rows.insertWidget(self._rows.count() - 1, row)
            self._built.append(row)

        # **Wo nichts gilt, steht der Weg, der gilt.** An einer Fläche ist
        # jede der vier Handlungen abgelehnt — dort setzen dafür
        # fünfundzwanzig Bausteine an, und der Katalog lag hinter Rechtsklick
        # und Untermenü. Ein Panel aus vier grauen Zeilen ist eine Sackgasse
        # mit Begründung; eine Sackgasse bleibt es trotzdem.
        if not any(action.op for action in actions):
            catalog = QPushButton(tr("Baustein einsetzen …"), self)
            catalog.setStatusTip(
                tr("Öffnet den Katalog — Bohrung, Mutternfalle, Magnettasche und die übrigen.")
            )
            catalog.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            catalog.clicked.connect(lambda _checked=False: self.catalogRequested.emit())
            self._rows.insertWidget(self._rows.count() - 1, catalog)
            self._built.append(catalog)
        self._settle_apply()

    def show_part(self, operation: Any, spec: Any, *, title: str = "") -> None:
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

        self.clear()
        self._feature_id = None
        # **Woran die Live-Vorschau erkennt, dass sie einen Schritt meint.**
        # Ohne ihn baute sie aus denselben Werten einen *neuen* Baustein und
        # zeigte beim Drehen an der Schraubengröße ein zweites Schlüsselloch
        # an der Vorgabelage — der Fehler, den der Knopf daneben schon
        # vermeidet (``stepChangeRequested``).
        self._part_operation = int(operation.id)
        self._empty.setVisible(False)

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

    def show_edge(self, key: str, title: str) -> None:
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
        """
        from app.core.perceive.actions import edge_actions

        self.clear()
        self._feature_id = None
        self._empty.setVisible(False)

        heading = QLabel(title, self)
        heading.setWordWrap(True)
        fit_wrapped(heading)
        set_level(heading, "section")
        self._rows.insertWidget(self._rows.count() - 1, heading)
        self._built.append(heading)

        for action in edge_actions(key):
            self._separate()
            row = self._build_action(action)
            self._rows.insertWidget(self._rows.count() - 1, row)
            self._built.append(row)
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
        self._empty.setVisible(False)

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
        choice = QComboBox(box)
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
                    widget.setStatusTip(note)
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
            self._fit_button.setStatusTip(note)
            self._fit_button.setAccessibleDescription(
                note or tr("Speichert die Prüfbeziehung. Rückgängig entfernt sie wieder.")
            )

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
        """
        box = QWidget(self)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, TIGHT)
        layout.setSpacing(TIGHT)

        step = getattr(action, "step", None)
        if action.op is None and step is None:
            # Titel und Grund in **einer** umbrechenden Zeile: Der Grund ist
            # ein Satz, und ein Satz gehört nicht in eine Formularspalte.
            name = QLabel(f"{action.title} — {action.reason}", box)
            name.setWordWrap(True)
            name.setStatusTip(str(action.reason))
            name.setAccessibleDescription(str(action.reason))
            fit_wrapped(name)
            layout.addWidget(name)
            return box

        widgets: dict[str, QWidget] = {}
        # **Der Schlüssel ist die Zeile, nicht die Operation.** Ein Baustein
        # bietet *Maße ändern*, *verschieben* und *entfernen* an, und zwei
        # davon tragen gar keine Operation (der Schritt ist die Handlung);
        # unter ``str(action.op)`` hießen beide „None" und die letzte
        # überschrieb die vorige — im Panel stand danach eine Handlung von
        # dreien.
        key = f"{len(self._runs)}|{action.op}"
        if action.fields:
            # **Die Gruppe sagt selbst, wozu sie gehört.** Bis hierher benannte
            # sie nur der Knopf **darunter**, und das trägt genau einmal: Beim
            # ersten Feldpaar liest man die Bedeutung noch von unten nach, beim
            # zweiten nicht mehr. An einer Bohrung stehen vier Gruppen
            # untereinander — X/Y/Z für *Verschieben*, ein Durchmesser für
            # *Ändern*, Achse und Winkel für *Drehen*, wieder X/Y/Z für
            # *Verdoppeln* —, und der Kunde sieht zweimal dieselben drei Felder
            # ohne erkennbaren Unterschied (Alexanders Bildschirmfoto, gemessen
            # von 3d-druck-4d am 04.09.2026).
            #
            # Die Überschrift wiederholt den Knopftext, und das ist Absicht: Sie
            # beantwortet „wozu sind diese Felder", er „und jetzt ausführen".
            # Zwei verschiedene Wörter dafür wären zwei Namen für eine Handlung.
            group_title = QLabel(str(action.title), box)
            group_title.setWordWrap(True)
            set_level(group_title, "caption")
            fit_wrapped(group_title)
            # **Die Erklärung steht an der Überschrift, nicht unter ihr.** Drei
            # Zeilen Fließtext je Handlung füllten das Fenster, und an einer
            # Bohrung stehen vier davon (Robert, 10.09.2026: „die beschreibungen
            # die über den buttons zum übernehmen dastehen auch in einen
            # tooltipp passen bei der überschrift von den werten mit einem i für
            # infos"). Weg ist sie damit nicht: Der Tooltip trägt sie, die
            # Statuszeile ebenso, und ``setAccessibleDescription`` reicht sie an
            # den Bildschirmleser weiter — Qt liest einen Tooltip nicht von
            # selbst vor.
            head = QHBoxLayout()
            head.setContentsMargins(0, 0, 0, 0)
            head.setSpacing(TIGHT)
            head.addWidget(group_title, 1)
            # **Jede Handlung hat eine Erklärung.** Drei Quellen in dieser
            # Reihenfolge: der Satz zur Lage (``note``, „Bohrung und Senkung
            # gehen gemeinsam"), der Grund der Handlung, und zuletzt der
            # ``doc``-Satz aus dem Register — die Beschreibung, die dieselbe
            # Operation auch im Menü und im Dialog trägt. Ein Zeichen, das nur
            # an einer von fünf Zeilen auftaucht, sieht aus wie ein Fehler und
            # nicht wie ein Angebot (Robert, 11.09.2026: „ist nur hinter
            # material verschieben").
            self._explain(box, head, _explained(action), group_title)
            layout.addLayout(head)

            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.setSpacing(TIGHT)
            # Bricht um, statt abzuschneiden: Bei schmaler Spalte rutscht das
            # Feld unter seine Beschriftung, und beide bleiben ganz.
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for field in action.fields:
                editor = self._build_field(field, box)
                widgets[str(field.name)] = editor
                self._watch(
                    editor,
                    str(action.op),
                    key,
                    tuple(action.fields),
                    widgets,
                    tuple(getattr(action, "fixed", ())),
                )
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
                # ist die Zusage, die überall trägt; die Überschrift der
                # Handlung kommt davor, weil „Durchmesser" allein nicht sagt,
                # welcher — an einer Bohrung stehen vier Handlungen mit je
                # eigenen Feldern.
                label.setBuddy(editor)
                editor.setAccessibleName(f"{action.title} — {field.label}")
                form.addRow(label, editor)
            layout.addLayout(form)

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
        entries = tuple(action.fields)
        fixed = tuple(getattr(action, "fixed", ()))

        def run(_checked: bool = False) -> None:
            # **Ein Baustein ändert seinen Schritt, er legt keinen zweiten an.**
            # Ohne diese Weiche stünde nach jeder Maßkorrektur ein weiteres
            # Schlüsselloch im Verlauf, an derselben Stelle über dem alten.
            if step is not None:
                if action.op is None:
                    self.stepRemoveRequested.emit(step)
                else:
                    self.stepChangeRequested.emit(step, self._values(entries, widgets, fixed))
                return
            self._emit(op_name, entries, widgets, self._every_for(op_name), fixed)

        def take(proposed: Mapping[str, Any]) -> None:
            """Vorgeschlagene Zahlen in die Felder dieser Handlung.

            Ohne Meldung nach außen: Die Zahlen kommen aus dem Bild, und die
            Vorschau dort zeigt sie bereits. Ein ``valuesChanged`` von hier
            liefe zurück zu dem, der gerade gezogen hat.
            """
            for name, value in proposed.items():
                editor = widgets.get(str(name))
                if not isinstance(editor, QDoubleSpinBox):
                    continue
                with QSignalBlocker(editor):
                    # **Eine Länge kommt in Millimetern herein** und wird über
                    # `set_value_mm` gesetzt; wer `setValue` nähme, schriebe
                    # den Kernwert in ein Feld, das in Zoll anzeigt (§19.3).
                    if isinstance(editor, LengthSpin):
                        editor.set_value_mm(float(value))
                    else:
                        editor.setValue(float(value))

        def in_view() -> None:
            """Dieselbe Handlung, aber im Bild eingestellt.

            **Ein eigener Knopf, seit dem 11.09.2026.** Bis dahin führte das
            *Übernehmen* selbst ins Bild, wo die Handlung eine Stelle hat —
            und damit konnte man an einer Bohrung nichts mehr übernehmen,
            ohne vorher durch die Platzierung zu gehen. Zwei Absichten
            brauchen zwei Knöpfe (Robert, 11.09.2026: „das über den viewport
            wieder über einen button aktivieren").
            """
            self.inViewRequested.emit(op_name, self._values(entries, widgets, fixed))

        # **Ein Knopf unten statt einer je Handlung** (Robert, 10.09.2026: „die
        # ganzen buttons um werte zu übernehmen durch einen unten ersetzen,
        # damit wir bisschen platz sparen"). Fünf Knöpfe untereinander
        # kosteten fünf Zeilen und sagten fünfmal dasselbe: „tu das hier".
        # Was der eine unten tut, entscheidet die Handlung, an der zuletzt
        # jemand etwas angefasst hat — und sein Text nennt sie beim Namen,
        # damit niemand raten muss (:meth:`_arm`).
        members = len(group.members) if group is not None else 0
        self._runs[key] = _Handling(
            title=str(action.title),
            reason=str(action.reason) or str(action.title),
            run=run,
            take=take,
            in_view=in_view if step is None and _leads_into_the_view(op_name) else None,
            op=op_name,
            members=members,
        )
        if not entries:
            button = QPushButton(str(action.title), box)
            button.setToolTip(_explained(action))
            button.clicked.connect(run)
            layout.addWidget(button)
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
        return box

    def _explain(self, box: QWidget, row: QHBoxLayout, text: str, title: QLabel) -> None:
        """Hängt das Info-Zeichen an eine Überschrift — oder lässt es weg.

        Ohne Text kein Zeichen: Ein Kreis, hinter dem nichts steht, ist eine
        Ankündigung, die niemand einlöst.
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
        self._dots[id(box)] = (dot, title)
        if text:
            self._extend_explanation(box, text)

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
            widget.setStatusTip(gathered)
        # **Der Bildschirmleser bekommt ihn am Titel**, nicht am Zeichen: Der
        # Kreis ist ein Bild, die Überschrift ist die Sache, zu der der Absatz
        # gehört. Am Zeichen allein fände ihn niemand, der die Zeile vorgelesen
        # bekommt (§19.1).
        title.setAccessibleDescription(gathered)
        dot.setAccessibleName(str(tr("Erklärung zu {title}")).format(title=title.text()))
        dot.setVisible(True)

    def _settle_apply(self) -> None:
        """Schiebt den Knopf ans Ende, nachdem alle Zeilen stehen.

        Er wird beim Aufbau des Panels **einmal** angelegt und liegt damit vor
        den Zeilen, die ``show_feature`` und die anderen später einfügen —
        sichtbar stand er dann ganz oben, über der Überschrift der Auswahl
        (Robert, 10.09.2026: „ich hab doch gesagt der button soll unten sein
        nicht ganz oben"). Ihn am Ende umzuhängen ist billiger als jede
        Einfügestelle um eins zu verschieben und dabei eine zu vergessen.
        """
        # **Die Reihenfolge ist eine Aussage:** Titel, der Weg ins Bild, der
        # Haken, das Übernehmen. Der Haken gehört unmittelbar über den Knopf,
        # dessen Umfang er ändert — ein Knopf dazwischen machte aus „für alle"
        # eine Frage, auf die zwei Knöpfe antworten.
        for widget in (self._armed_title, self._in_view, self._every, self._apply, self._cancel):
            self._rows.removeWidget(widget)
            self._rows.insertWidget(self._rows.count() - 1, widget)
        self._settle_in_view()
        self._cancel.setVisible(self._measuring and self._apply.isVisibleTo(self))

    def _separate(self) -> None:
        """Zieht einen Strich vor die nächste Handlung — außer vor die erste.

        Eine Handlung ist ein Block aus Überschrift, Feldern und (seit dem
        10.09.2026) keinem eigenen Knopf mehr. Ohne Trennung folgen an einer
        Bohrung auf drei Zahlenfelder wieder drei, und wer nicht auf die
        Überschriften sieht, liest sie als eine Reihe (Robert, 10.09.2026:
        „die unterschiedlichen einstellungen noch abgrenzen durch einen
        strich"). Vor der ersten wäre er ein Strich gegen nichts.
        """
        if not self._built:
            return
        line = rule(self)
        self._rows.insertWidget(self._rows.count() - 1, line)
        self._built.append(line)

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
        self._armed = key
        self._armed_title.setText(entry.title)
        self._armed_title.show()
        # **Der Titel steht am Knopf, nur nicht auf ihm.** Ein Bildschirmleser
        # liest den zugänglichen Namen, und „Übernehmen" allein sagte dort
        # nicht, was übernommen wird (§19.1).
        self._apply.setStatusTip(f"{entry.title} — {entry.reason}")
        self._apply.setToolTip(entry.title)
        self._apply.setAccessibleName(entry.title)
        self._apply.setAccessibleDescription(entry.reason)
        self._apply.setVisible(True)
        applies_to_all = entry.members > 1
        if applies_to_all:
            promise = str(tr("Eine Handlung für alle — und ein Strg+Z nimmt sie zusammen zurück."))
            self._every.setText(
                str(tr("Auf alle {count} gleichartigen anwenden")).format(count=entry.members)
            )
            self._every.setStatusTip(promise)
            self._every.setAccessibleDescription(promise)
        else:
            # **Ein Haken, der nicht gilt, wird auch nicht gehalten.** Sonst
            # stünde er ausgeblendet auf „an" und griffe wieder, sobald jemand
            # eine Handlung mit Gruppe anfasst.
            self._every.setChecked(False)
        self._every.setVisible(applies_to_all)

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
        self._in_view.setVisible(self._into_view is not None)
        if self._into_view is None:
            return
        promise = str(tr("Maßlinien zu Kanten und Mitten in der Szene — dort einstellen."))
        self._in_view.setStatusTip(promise)
        self._in_view.setToolTip(promise)
        self._in_view.setAccessibleName(str(tr("Im Bild einstellen")))
        self._in_view.setAccessibleDescription(promise)

    def set_measuring(self, active: bool) -> None:
        """Ob die Maße dieses Merkmals im Bild stehen — *Abbrechen* steht dann mit.

        Das Fenster sagt es beim Start und beim Ende der Platzierung; das
        Merkmalfenster weiß sonst nichts davon, es hält nur die Felder.
        """
        self._measuring = bool(active)
        self._cancel.setVisible(self._measuring and self._apply.isVisibleTo(self))

    def request_in_view(self) -> None:
        """Denselben Weg nehmen wie der Knopf *Im Bild einstellen* — wenn er steht.

        Für das Hauptfenster, das die Maße nach einem Übernehmen wieder ins
        Bild bringt: Es klickt nicht auf ein Widget, es nimmt den Weg, der am
        Widget hängt. Wo kein Knopf steht, geschieht nichts.
        """
        if self._into_view is not None:
            self._into_view()

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

    def _watch(
        self,
        editor: QWidget,
        op: str,
        key: str,
        fields: Sequence[Any],
        widgets: Mapping[str, QWidget],
        fixed: Sequence[tuple[str, Any]] = (),
    ) -> None:
        """Meldet jede Änderung an einem Feld — für die Vorschau, nicht zum Tun.

        **Bei der Länge über ``valueChangedMm``**: Qts ``valueChanged`` trägt
        die Zahl aus dem Feld, also einen Anzeigewert. Wer sie weiterreicht,
        hat die Umrechnung übersprungen, und aus 5 mm werden bei Zoll 0,1969.
        """

        def report(*_ignored: object) -> None:
            # **Wer einen Wert ändert, meint diese Handlung.** Der Knopf unten
            # folgt der Berührung; ohne das zeigte er auf die erste, während
            # jemand in der vierten tippt.
            self._arm(key)
            self.valuesChanged.emit(op, self._values(fields, widgets, fixed))

        for target in (editor, *editor.findChildren(QLineEdit)):
            target.setProperty("handlingKey", key)
            target.installEventFilter(self)
        if isinstance(editor, LengthSpin):
            editor.valueChangedMm.connect(report)
        elif isinstance(editor, QCheckBox):
            editor.toggled.connect(report)
        elif isinstance(editor, QComboBox):
            editor.currentIndexChanged.connect(report)
        elif isinstance(editor, QDoubleSpinBox):
            editor.valueChanged.connect(report)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Schnittstelle
        """Schon der Fokus benennt die Handlung, ohne ihren Wert zu ändern."""
        from app.ui.leash import stop_watching_the_dying

        if stop_watching_the_dying(self, watched, event):
            return False
        if event.type() == QEvent.Type.FocusIn:
            key = watched.property("handlingKey")
            if isinstance(key, str):
                self._arm(key)
        return super().eventFilter(watched, event)

    def _build_field(self, field: Any, parent: QWidget) -> QWidget:
        """Das Feld zur Art — Länge rechnet Zoll zurück, ein Winkel nicht."""
        kind = str(field.kind)
        if kind == "bool":
            check = QCheckBox("", parent)
            check.setChecked(bool(field.value))
            return check
        if kind == "choice":
            combo = QComboBox(parent)
            for value, text in field.choices or ():
                combo.addItem(str(text), value)
            index = combo.findData(field.value)
            if index >= 0:
                combo.setCurrentIndex(index)
            return combo
        if kind == "length":
            spin = LengthSpin(parent)
            spin.set_range_mm(
                float(field.minimum) if field.minimum is not None else -100000.0,
                float(field.maximum) if field.maximum is not None else 100000.0,
            )
            spin.set_value_mm(float(field.value))
            return spin
        angle = NumberSpin(parent)
        angle.setRange(
            float(field.minimum) if field.minimum is not None else -360.0,
            float(field.maximum) if field.maximum is not None else 360.0,
        )
        angle.setSuffix(f" {field.unit}" if field.unit else "")
        angle.setValue(float(field.value))
        return angle

    def _values(
        self,
        fields: Sequence[Any],
        widgets: Mapping[str, QWidget],
        fixed: Sequence[tuple[str, Any]] = (),
    ) -> dict[str, Any]:
        """Was in den Feldern dieser Handlung steht, in der Einheit des Kerns.

        ``fixed`` sind die Werte, die die Handlung mitbringt und die niemand
        eingibt — an einer angeklickten Kante die Auswahl ``named`` und ihr
        Schlüssel (:attr:`~app.core.perceive.actions.FeatureAction.fixed`).
        Sie stehen **vor** den Feldern, damit ein Feld gleichen Namens gewinnt:
        Was der Kunde sieht, gilt.
        """
        params: dict[str, Any] = {}
        if self._feature_id is not None:
            # ``at_feature`` ist kein Feld: Welches Merkmal gemeint ist, steht
            # in der Auswahl, und eine Frage danach hätte ihre Antwort schon.
            params["at_feature"] = self._feature_id
        params.update(dict(fixed))
        for field in fields:
            widget = widgets.get(str(field.name))
            if isinstance(widget, LengthSpin):
                params[str(field.name)] = widget.value_mm()
            elif isinstance(widget, QCheckBox):
                params[str(field.name)] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                params[str(field.name)] = widget.currentData()
            elif isinstance(widget, QDoubleSpinBox):
                params[str(field.name)] = float(widget.value())
        return params

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
            group = self._groups.get(op)
            if group is None:
                return
            targets = [member.target for member in group.members]
            if self._feature_id in targets:
                targets.remove(self._feature_id)
                targets.insert(0, self._feature_id)
            self.operationRequestedForEach.emit(op, params, targets)
            return
        self.operationRequested.emit(op, params)


def collapsible(title: str, content: QWidget, *, open_now: bool = True) -> QWidget:
    """Ein Abschnitt, der sich zuklappen lässt — §2.5 verlangt genau das.

    Er hieß so und war keiner: eine fette Überschrift über dem Inhalt, ohne
    Umschalter. Wer den Verlauf groß haben wollte, konnte die anderen beiden
    nicht wegklappen, und drei Abschnitte in einer schmalen Spalte teilen sich
    die Höhe, ob sie sie brauchen oder nicht.

    Der Umschalter ist ein Knopf mit dem Titel darauf, kein Zeichen daneben:
    die ganze Zeile ist damit die Fläche, die man trifft, und der gedrückte
    Zustand sagt ohne Farbe, ob offen oder zu ist (Regel 18).
    """
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
    set_level(heading, "section")
    heading.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def toggled(open_now: bool) -> None:
        content.setVisible(open_now)
        heading.setArrowType(Qt.ArrowType.DownArrow if open_now else Qt.ArrowType.RightArrow)

    heading.toggled.connect(toggled)

    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(heading)
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


def align_forms(dialog: QWidget) -> None:
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
    """
    labels: list[QWidget] = []
    for form in dialog.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            widget = item.widget() if item is not None else None
            if widget is not None:
                labels.append(widget)
    if not labels:
        return
    widest = max(widget.sizeHint().width() for widget in labels)
    for widget in labels:
        widget.setMinimumWidth(widest)


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


def _svg_icon(svg: str, size: int) -> QIcon:
    """Ein SVG als Symbol, scharf auf HiDPI.

    Überzählig gerastert und dann auf die Anzeigegröße gesetzt: Ein Bild in
    genau der Punktgröße franst auf einem skalierten Bildschirm aus. Der Faktor
    ist :data:`app.ui.icons.OVERSAMPLING` — hier stand er als nackte 2 und
    wäre bei der nächsten Anpassung dort allein geblieben.
    """
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return QIcon()
    image = QImage(QSize(size, size) * OVERSAMPLING, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.setDevicePixelRatio(float(OVERSAMPLING))
    return QIcon(QPixmap.fromImage(image))
