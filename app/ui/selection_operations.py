"""Kontextsensitive Operationen zur Auswahl, unter Prüfbericht und Chat.

Die Liste entsteht einmal aus dem Operationsregister. Auswahlwechsel ändern
nur Sichtbarkeit, Freigabe, Hinweise und die Anordnung der vorhandenen
Knöpfe; bei großen Registern wird weder ein Modell noch ein Qt-Baum neu
gebaut.

**Die Hauptaktionen oben richten sich nach der Auswahl** — nach ihrer Art und
nach ihrer Menge (Robert, 07.09.2026: „es sollten immer je nach auswahl und
menge der auswahl die sinnvollsten aktionen dastehen"). Fest verdrahtet waren
es die drei Booleschen: An einem einzelnen Körper standen damit drei graue
Knöpfe, denn eine Vereinigung braucht zwei, und an einer gewählten Fläche
stand gar nichts — Operationen mit ``applies_to`` waren aus dem Panel
gefiltert. Beides beantwortet :func:`quick_names`.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable, Iterable
from dataclasses import replace
from typing import Final, override

from PySide6.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QFontMetrics,
    QFontMetricsF,
    QKeyEvent,
    QPainter,
    QPalette,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from app.core.perceive.actions import OFFERED_AT_A_PART
from app.core.registry import (
    CATEGORIES,
    MENU_GROUPS,
    REGISTRY,
    OperationSpec,
    SearchEntry,
    catalogue_operations,
    caveat_line,
    folded_categories,
    group_title,
    search_entries,
    shown_of_twins,
    variant_members,
)
from app.core.registry.search import first_choice, ranked
from app.core.registry.surfaces import first_sentence, menu_rank
from app.i18n import sort_key, tr
from app.ui.icons import icon, icon_name_for
from app.ui.labels import adding_key
from app.ui.leash import stop_watching_the_dying, weak_slot
from app.ui.overlay import ContentScroller
from app.ui.panels import collapsible
from app.ui.shortcut_schemes import native_key, return_opens
from app.ui.style import NORMAL, TARGET_SIZE, TIGHT, make_large_target, make_primary, set_level

QUICK_BODIES = ("union_objects", "subtract_objects", "intersect_objects")
"""Bei zwei oder mehr Körpern: die Handlungen, wegen derer die Auswahlfläche
zuerst gebraucht wurde."""

QUICK_BODY = ("drill_hole", "hollow_object", "split_pinned")
"""Bei genau einem Körper.

Die drei häufigsten Handlungen an einem einzelnen Druckteil — und keine
davon liegt schon auf einem Griff im Bild oder in der Werkzeugzeile:
Verschieben, Drehen und Skalieren haben ihre Leiste, das Trennen entlang
einer gezeichneten Linie seine. Bohren braucht eine Fläche und findet sie an
jedem Körper; ohne eine erkannte sagt es das selbst (``feature_requirement``).
"""

QUICK_FEATURES: dict[str, tuple[str, ...]] = {
    "face": ("drill_hole", "sketch_pocket", "push_face"),
    # ``resize_hole`` und ``slot_hole`` stehen vorn und werden gleich wieder
    # herausgefiltert — beide haben oben ein Feld (:func:`_shown_as_fields`).
    # Sichtbar bleiben **zwei**: senken und zumachen (gemessen 13.09.2026).
    # Sie bleiben trotzdem in der Reihenfolge stehen: Nimmt der Kern eine der
    # beiden aus ``ACTION_ORDER``, steht sie an der Stelle wieder da, an die
    # sie gehört, statt hinten in der Suchliste.
    "hole": ("resize_hole", "countersink_hole", "slot_hole", "plug_hole", "pattern_feature"),
    # **Am Langloch steht vorn nur das Muster.** Alle sechs übrigen Handlungen
    # des Langlochs stehen oben als Felder, und was dort steht, bekommt hier
    # keinen zweiten Knopf; *Merkmal vervielfachen* (P6.7) hat keine
    # gemessenen Werte und damit keine Zeile oben. Die Zeile hält außerdem die
    # Stelle für den Fall frei, dass *Zum Langloch ziehen* je aufhört, ein Feld
    # zu sein.
    "slot": ("slot_hole", "pattern_feature"),
    "cone": ("countersink_hole", "pattern_feature"),
    "edge_loop": ("repair",),
}
"""Je Merkmalsart die Handlungen, die dort zuerst gesucht werden.

Nur wo die Art eine eigene Antwort hat. Stift und Kugel bieten die
generischen Merkmalshandlungen **mit** an — nicht genau sie: Am Register
gemessen (07.09.2026) trägt `pin` sieben Operationen und `sphere` vier, die
aus :data:`QUICK_FEATURE` sind darunter. Der Rest steht in der Liste
darunter und im Suchfeld. *Merkmal vervielfachen* (P6.7) steht an
jeder Art, die es annimmt, mit vorn: Es hat keine Zeile im Merkmalfenster.

**Der Kegel hat seit dem 09.09.2026 eine eigene Zeile**, und der Grund ist ein
Loch, das vorher niemandem auffiel: Er trägt sechs Operationen, fünf davon
stehen im Merkmalsfenster darüber als Felder (:func:`_shown_as_fields`), und
die sechste — *Senken* — war ein Knopf der Schnellzeile für ``hole``. Was oben
stehen **kann**, steht nicht auch in der Liste darunter; an einer Senkung stand
es aber auch nicht oben, weil der Rückfall :data:`QUICK_FEATURE` sie nicht
nennt. Damit war die einzige Handlung an einer Senkung an keiner der beiden
Stellen zu finden.
"""

QUICK_FEATURE = ("resize_feature", "move_feature", "remove_feature", "pattern_feature")
"""Für jede Merkmalsart ohne eigene Zeile in :data:`QUICK_FEATURES`."""

QUICK_SEVERAL_FEATURES = ("group_pattern",)

#: Der Schlüssel der Hauptaktion *Modell nachbauen* — keine Operation, sondern
#: ein Dialog (``rebuild_dialog``), der eine Transaktion vorschlägt. Sie gilt
#: genau einem gewählten Körper und steht deshalb hier, nicht im Prüfbericht
#: (RM-508, Durchsicht B19: gesperrt und mit einem Satz von elf Wörtern stand
#: sie dort auch ohne Auswahl).
REBUILD: Final = "rebuild_model"
"""Bei mehreren markierten Merkmalszeilen eines Körpers (RM-504).

Wer mehrere Einzelmerkmale markiert, hat sie meist als Gruppe gemeint — das
kleine Wabenfeld, die drei Rillen, das Ornament, das die Erkennung ohne
Erzeugerwissen nicht zusammenfasst. Der Dialog übernimmt die markierten
Zeilen (``MainWindow._values_for_selection`` füllt ``at_features``).
"""


#: Bis zu so vielen sichtbaren Handlungen beginnt eine Gruppe offen; darüber
#: zugeklappt. Es ist dieselbe Zahl wie ``MAX_SUBMENU_ENTRIES`` in
#: ``tests/test_interface_limits.py``, und der Test hält beide zusammen: Die
#: vier Operationsmenüs sind am 11.09.2026 in diese Karte gewandert, und
#: mitgewandert war die Zahl der Einträge, nicht die Grenze — an einem
#: gewählten Körper standen 42 Knöpfe offen da, 24 davon unter „Ändern"
#: (Durchsicht 14.09.2026). Ein Klick mehr für den, der tief greift; ein
#: überschaubares Bild für den, der zum ersten Mal hinsieht. Wer eine Gruppe
#: von Hand auf- oder zuklappt, behält das über Auswahlwechsel hinweg.
OPEN_UP_TO: Final = 12

#: Handlungen, die der Filament-Schnellwähler über dieser Liste trägt
#: (``filament_assignment.QuickFilamentPicker``, vom Fenster an zweiter Stelle
#: in diese Karte gehängt). *Filament entfernen* stand zweimal in derselben
#: Karte: oben am Wähler, gesperrt mit Grund, solange nichts zugewiesen ist —
#: darunter als Operation, bedienbar (Durchsicht 14.09.2026). Derselbe Text
#: mit entgegengesetzter Aussage. Was oben stehen kann, steht nicht auch
#: darunter — dieselbe Regel wie bei den Hauptaktionen und bei
#: :func:`_shown_as_fields`.
#:
#: *Filament zuweisen* und *Filament auf eine Fläche* gehören dazu (RM-510):
#: Am Körper und an der Fläche gab es Färben zweimal, als Wähler und als Knopf.
PICKER_HANDLES: Final = frozenset({"assign_slot", "clear_filament", "paint_slot"})

#: An welcher Merkmalsart der Knopf unten *Passende Bausteine …* heißt und den
#: Katalog auf das filtert, was dort ansetzt (Robert, 05.10.2026; der Filter
#: ist ``catalog.parts_for_feature``).
MATCHING_PARTS_AT: Final = frozenset({"hole"})


#: Kategorien, die ein Werkzeug der Werkzeugzeile schon trägt — *Bewegen*
#: verschiebt, dreht und skaliert. In der Karte stehen sie am Ende ihrer
#: Gruppe: Vorn steht, was es nur hier gibt (RM-506; gemessen bei 1600 x 1000
#: lag *Verrunden* sonst 58 px unter dem Ausschnitt, hinter sieben
#: Transformationen).
TOOL_STRIP_CATEGORIES: Final = frozenset({"transform"})


def _card_group(spec: OperationSpec) -> tuple[tuple[int, int, int, int], str]:
    """Wo eine Handlung in der Karte steht: Rang und Titel ihrer Gruppe.

    **Dieselbe Folge wie die Menüleiste, in jeder Sprache** (RM-506): Die
    Gruppen standen nach ``str.casefold`` ihres Titels, auf Deutsch also
    „Ändern“ mit 32 Einträgen am Ende, in jeder Sprache anders. Jetzt gilt
    ``MENU_GROUPS``. Eine Kategorie, die das Menü in ein Untermenü faltet
    (``folded_categories``), ist hier eine eigene Gruppe hinter den direkten
    ihrer Menügruppe — so wird „Ändern“ am Körper keine Wand.
    """
    return _category_group(spec.category)


def _category_group(category: str) -> tuple[tuple[int, int, int, int], str]:
    """:func:`_card_group` für eine Kategorie — auch für eine Handlung ohne Registereintrag."""
    group = str(group_title(category))
    rank = menu_rank(group)
    if category not in folded_categories(category):
        return (rank, 0, 0, 0), group
    categories = next((members for _title, members in MENU_GROUPS if category in members), ())
    place = categories.index(category) if category in categories else len(categories)
    behind = int(category in TOOL_STRIP_CATEGORIES)
    return (rank, 1, behind, place), str(CATEGORIES.get(category, category))


#: Wie hoch eine Zeile der Operationsliste ist (RM-510).
#:
#: Die Liste war eine Wand gleicher 44-Punkte-Kacheln mit Rahmen, gleich laut
#: wie die Hauptaktionen darüber. Flache Zeilen mit Hover setzen die Liste
#: hinter die Hauptaktionen zurück und zeigen bei gleicher Höhe ein Drittel
#: mehr; die Hauptaktionen behalten die volle Zielgröße.
LIST_ROW_HEIGHT: Final = 32


def _shown_as_fields() -> frozenset[str]:
    """Welche Handlungen das Merkmalsfenster darüber schon als Felder zeigt.

    Die Liste steht im Kern (:data:`~app.core.perceive.actions.ACTION_ORDER`)
    und wird hier nur gelesen — dasselbe Register, aus dem
    :class:`~app.ui.panels.FeaturePanel` seine Zeilen baut.

    **Was dort ein Feld hat, bekommt hier keinen Knopf.** Beide Panels liegen
    im selben Fenster übereinander, und an einer gewählten Bohrung standen
    *Bohrung ändern*, *Merkmal drehen* und *Merkmal verdoppeln* damit zweimal:
    oben mit dem gemessenen Wert und einem Knopf, darunter als Knopf, der
    denselben Weg nochmal anbietet (Befund Robert, 09.09.2026: „hier soll
    immer nur für das ausgewählte etwas stehen"). Zwei Wege zu einer Handlung
    sind eine Frage ohne Antwort — dieselbe Regel, nach der eine Hauptaktion
    nicht auch in der Liste darunter steht.
    """
    from app.core.perceive.actions import ACTION_ORDER

    return frozenset(name for row in ACTION_ORDER for name in row)


PANEL_LEAST_HEIGHT = 280
"""Was das Panel mindestens braucht, in Bildpunkten.

Drei Hauptaktionen, Suche, Trefferliste und der Weg zum Bausteinkatalog dürfen
sich auch in einem 720-Pixel-Fenster nicht überlagern. Mit der früheren
190-Pixel-Untergrenze drückte Qt jede Hauptaktion auf rund 15 Pixel und legte
das Suchfeld über „Schnittmenge".

**Die zweite Zahl daneben ist mit dem Umzug weggefallen** (07.09.2026): Solange
das Panel in der Overlay-Spalte lag, teilte ``MainWindow._fit_right_column``
diese Spalte zwischen ihm und dem Prüfbericht, und beide Untergrenzen mussten
gegeneinander stehen. Jetzt liegt es im Fenster rechts, das rollt — eine
Untergrenze genügt, und eine Obergrenze braucht es gar nicht mehr.

**Und sie gilt dem vollen Zustand, nicht jedem.** Seit dem 18.09.2026 hat die
Karte zwei leere Gestalten, in denen Suche und Liste fehlen: ohne Auswahl in
einer leeren Szene (Hauptaktionen weg, Katalogknopf und ein Satz; stehen
Körper da, kommen die Handlungen für alle Körper dazu) und an einer Auswahl, deren
Handlungen oben im Merkmalfenster stehen — ein Langloch, eine Kante. Dort
reserviert die Zahl mehr, als dasteht. Das ist Absicht und kein Rest: Eine
Untergrenze, die mit dem Inhalt schwankte, ließe die Karte bei jedem
Auswahlwechsel springen, und der Raum darunter kostet nichts — die Spalte
rollt, und was frei bleibt, zeigt das Modell.
"""


def quick_names(
    bodies: int,
    feature_kind: str = "",
    *,
    left_out: frozenset[str] = frozenset(),
    features: int = 0,
) -> tuple[str, ...]:
    """Die Hauptaktionen für diese Auswahl, in ihrer Rangfolge.

    ``features`` zählt die markierten Merkmale eines Körpers, wenn kein
    einzelnes gewählt ist — mehrere Zeilen im Baum. Ab zweien steht vorn
    :data:`QUICK_SEVERAL_FEATURES`.

    ``left_out`` nennt, was am gewählten Merkmal nicht angeboten wird, obwohl
    seine Art es trägt — am Kegel, der keine Senkung ist, *Senken* (R3). Die
    Menge kommt aus dem Kern (``perceive.actions.not_offered_at``).

    **Das Merkmal hat Vorrang vor der Menge.** Wer eine Bohrung angeklickt
    hat, meint die Bohrung und nicht den Körper darunter — und mehr als ein
    Körper *und* ein Merkmal gibt es nicht zugleich: Der Baum gibt kein
    gewähltes Merkmal zurück, sobald mehrere Zeilen markiert sind.

    Eine **Empfehlung, keine Aufzählung**: Was hier fehlt, steht in der
    Liste darunter und im Suchfeld über alles. Deshalb ist eine
    unvollständige Liste hier kein Fehler, anders als bei einer Angabe, die
    eine Fähigkeit ausspricht — dort gehört sie ins Register.

    **Empfohlen wird nur, was es an dieser Art überhaupt gibt.** Das Register
    kennt sechs Merkmalsarten in ``applies_to`` (gemessen 07.09.2026: `face`,
    `hole`, `cone`, `pin`, `sphere`, `edge_loop`); die Erkennung liefert mehr,
    unter anderem Torus, Verrundung und Gewinde. Für die bot der Rückfall
    :data:`QUICK_FEATURE` drei Knöpfe an, hinter denen keine einzige Operation
    steht — und schlimmer als graue Knöpfe: ``feature_requirement`` fragt, ob
    **der Körper** ein solches Merkmal hat, nicht ob das **gewählte** eines
    ist. Auf einem Körper mit Bohrung waren sie deshalb bedienbar und hätten
    auf ein anderes Merkmal gewirkt. Eine leere Zeile ist ehrlicher.

    Für die sechs bekannten Arten ändert die Schnittmenge nichts — gemessen
    3→3, 3→3, 3→3, 3→3, 3→3 und 1→1.
    """
    if feature_kind:
        wanted = QUICK_FEATURES.get(feature_kind, QUICK_FEATURE)
        offered = {spec.name for spec in REGISTRY.for_feature(feature_kind)}
        fields = _shown_as_fields()
        return tuple(
            name
            for name in wanted
            if name in offered and name not in fields and name not in left_out
        )
    if bodies == 1 and features > 1:
        return QUICK_SEVERAL_FEATURES
    return QUICK_BODIES if bodies > 1 else QUICK_BODY


def all_quick_names() -> tuple[str, ...]:
    """Jeder Name, der in irgendeiner Lage vorn stehen kann — ohne Wiederholung.

    Der Aufbau braucht sie: Die Hauptaktionen bekommen ihre Knöpfe **einmal**
    und werden bei Auswahlwechseln nur noch ein- und ausgeblendet. In der
    Reihenfolge ihrer Tabellen, damit die Zeile oben von links nach rechts so
    steht, wie :func:`quick_names` sie nennt.
    """
    found: list[str] = []
    for group in (
        QUICK_BODIES,
        QUICK_BODY,
        *QUICK_FEATURES.values(),
        QUICK_FEATURE,
        QUICK_SEVERAL_FEATURES,
    ):
        found.extend(name for name in group if name not in found)
    return tuple(found)


def body_operations(specs: Iterable[OperationSpec]) -> tuple[OperationSpec, ...]:
    """Körperoperationen, ohne den getrennten Bausteinweg.

    Versteckte Rechenkern-Zwillinge sind keine zweite Handlung. Erzeuger ohne
    Eingang gehören ebenfalls nicht an eine Auswahl; sie stehen auf der Stufe
    ohne Auswahl (:func:`scene_creators`).

    **Draußen bleibt die Kachel, nicht die Kategorie** (11.09.2026). Hier stand
    dazu ``_SEPARATE_CATEGORIES = {"parts"}``, und das nahm zwei Operationen
    mit, die gar keine Kachel haben: *Deckel erzeugen* und *Drehdeckel
    erzeugen* bauen einen Deckel auf eine Fläche, statt einen fertigen
    einzusetzen — und standen damit nirgends an der Fläche, auf die sie gehören
    (Entscheidung Robert: „Deckel/Drehdeckel zusätzlich rechts an einer
    Fläche"). ``catalogue_operations()`` zieht die Linie dort, wo sie hingehört.

    **Die Zwillingsregel kommt aus dem Kern** und steht nicht ein drittes Mal
    hier (:func:`~app.core.registry.shown_of_twins`, 07.09.2026): Der Bezug
    ist die Menge selbst, damit ein Zwilling, dessen sichtbarer Partner hier
    gar nicht vorkommt, nicht spurlos herausfällt.
    """
    catalogue = catalogue_operations()
    return shown_of_twins(
        spec
        for spec in specs
        if (spec.consumes != 0 or spec.takes_whole_scene)
        and spec.name not in catalogue
        and (not spec.applies_to or spec.also_on_body)
    )


def feature_operations(specs: Iterable[OperationSpec]) -> tuple[OperationSpec, ...]:
    """Was an einem Merkmal gearbeitet wird — Bohren, Senken, Verschließen.

    Die Handlungen, die das Auswahlfenster am Merkmal anbietet (``applies_to``,
    §18.5): eine Oberfläche über einer Quelle, keine zweite Rechnung. Sie
    standen bis zum 07.09.2026 nicht im Panel, und damit bot eine gewählte
    Fläche dort nichts an.

    **Die Bausteine mit Kachel bleiben draußen.** Ein räumliches Teil als
    Textzeile ist die schlechtere Darstellung; sie sind durch den Katalogknopf
    vertreten — dieselbe Entscheidung, die auch die Menüleiste trifft. Die
    zwei Deckel ohne Kachel stehen hier an der Fläche (siehe
    :func:`body_operations`).

    **Und dieselbe Erzeuger-Schranke wie bei :func:`body_operations`.** Ein
    Erzeuger ohne Eingang gehört an keine Auswahl, gleich ob sie einen Körper
    oder ein Merkmal meint; er steht auf der Stufe ohne Auswahl. Am
    Register trifft die Bedingung heute keinen Eintrag mit ``applies_to`` —
    sie steht hier, damit die beiden Filter dieselbe Regel tragen und nicht der
    nächste Eintrag durch die Lücke fällt.
    """
    catalogue = catalogue_operations()
    return shown_of_twins(
        spec
        for spec in specs
        if spec.applies_to
        and (spec.consumes != 0 or spec.takes_whole_scene)
        and spec.name not in catalogue
    )


def scene_creators(specs: Iterable[OperationSpec]) -> tuple[OperationSpec, ...]:
    """Was ohne Auswahl einen neuen Körper anlegt — Grundformen, Schriftzug, Import.

    Sie standen bis RM-735 nur im Menü *Erzeugen* und in der Befehlspalette;
    die Einladung der leeren Szene zeigt zwei von ihnen und verschwindet mit
    dem ersten Körper — genau dann, wenn man einen zweiten anlegen will. Jetzt
    stehen sie rechts, wenn nichts gewählt ist (Entscheidung Robert,
    11.10.2026: alles über das Auswahlpanel oder in der Ansicht).

    **Dieselben Schranken wie die Menüleiste:** keine Kachel des Katalogs, kein
    versteckter Zwilling (:func:`~app.core.registry.shown_of_twins`), keine
    Art einer Variantengruppe — *Zeichnen* ist ein Eintrag mit Art im Schritt
    und steht oben in der Werkzeugleiste.
    """
    catalogue = catalogue_operations()
    members = variant_members()
    return shown_of_twins(
        spec
        for spec in specs
        if spec.consumes == 0
        and not spec.takes_whole_scene
        and spec.name not in catalogue
        and spec.name not in members
    )


#: Wie weit die Tastenspalte der Trefferliste vom rechten Rand einrückt.
SHORTCUT_MARGIN: Final = 12

#: Wie viele Zeilen die zweite Zeile eines Treffers höchstens umbricht. Die
#: Karte ist schmaler als der Dialog der Befehlspalette, und ein Sperrgrund,
#: der nach drei Wörtern abbricht, sagt nicht mehr, was fehlt.
DETAIL_LINES: Final = 3

#: Wie viele Treffer die Liste zeigt, bevor sie in sich rollt.
HITS_SHOWN: Final = 12

#: Wie viele gemessene Umbrüche der Zeilenzeichner behält: alle Zeilen der
#: Suche in einigen Breiten, und mehr wird es auch nach vielen Größenwechseln
#: nicht.
MEASURED_KEPT: Final = 2048


class _HitRows(QStyledItemDelegate):
    """Zeichnet je Treffer den Titel links, das Kürzel **rechtsbündig** in einer
    Spalte und darunter Beschreibung oder Sperrgrund.

    Aus der Befehlspalette übernommen (RM-735): Mit einem Tabulator am Titel
    begann die Taste bei jedem Titel an einer anderen Stelle, und wer die
    Kürzel nebenbei lernen soll (§19.2), muss sie untereinander finden. Die
    zweite Zeile bricht in der schmalen Karte um (:data:`DETAIL_LINES`); der
    vorgewählte Treffer steht halbfett — die zweite Kodierung neben der
    Markierungsfarbe (Regel 18).
    """

    def __init__(self, view: QListWidget) -> None:
        super().__init__(view)
        self._view = view
        self._measured: dict[tuple[int, str, str], int] = {}

    def _parts(self, index: QModelIndex | QPersistentModelIndex) -> tuple[str, str, str]:
        """Titel, Kürzel und zweite Zeile aus dem unveränderten Modelltext."""
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        first_line, _separator, detail = text.partition("\n")
        title, _tab, shortcut = first_line.partition("\t")
        return title, shortcut, " ".join(detail.split())

    @staticmethod
    def _detail_lines(width: int, detail: str, metrics: QFontMetrics) -> int:
        """Wie viele Zeilen die zweite Zeile bei dieser Breite braucht."""
        if not detail or width <= 0:
            return 0
        line = max(1, metrics.height())
        bound = metrics.boundingRect(
            QRect(0, 0, width, line * (DETAIL_LINES + 1)), int(Qt.TextFlag.TextWordWrap), detail
        )
        return min(DETAIL_LINES, max(1, math.ceil(bound.height() / line)))

    def _lines_of(self, width: int, detail: str, plain: QStyleOptionViewItem) -> int:
        """:meth:`_detail_lines`, gemerkt je Breite, Schrift und Text.

        Qt fragt die Höhe einer Zeile je Tastendruck mehrmals ab — Wunschhöhe
        der Liste, Layout, Rollbereich, gemessen rund zehnmal je Zeile —, und
        das Umbrechen ist das Teure daran.
        """
        key = (width, plain.font.key(), detail)
        lines = self._measured.get(key)
        if lines is None:
            if len(self._measured) >= MEASURED_KEPT:
                self._measured.clear()
            lines = self._detail_lines(width, detail, plain.fontMetrics)
            self._measured[key] = lines
        return lines

    @override
    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        plain = QStyleOptionViewItem(option)
        self.initStyleOption(plain, index)
        _title, _shortcut, detail = self._parts(index)
        line = plain.fontMetrics.height()
        width = self._view.viewport().width() - NORMAL - SHORTCUT_MARGIN
        lines = 1 + self._lines_of(width, detail, plain)
        # Die Liste gibt die Breite vor, der Text darf sie nicht aufziehen.
        return QSize(0, lines * line + (lines - 1) * TIGHT + 2 * TIGHT)

    @override
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        plain = QStyleOptionViewItem(option)
        self.initStyleOption(plain, index)
        title, shortcut, detail = self._parts(index)
        plain.text = ""
        widget = option.widget or self._view
        widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, plain, painter, widget)

        painter.save()
        painter.setClipRect(option.rect)
        group = (
            QPalette.ColorGroup.Disabled
            if not plain.state & QStyle.StateFlag.State_Enabled
            else plain.palette.currentColorGroup()
        )
        chosen = bool(plain.state & QStyle.StateFlag.State_Selected)
        role = QPalette.ColorRole.HighlightedText if chosen else QPalette.ColorRole.Text
        painter.setPen(plain.palette.color(group, role))
        area = option.rect.adjusted(NORMAL, TIGHT, -SHORTCUT_MARGIN, -TIGHT)
        metrics = plain.fontMetrics
        line = metrics.height()
        title_font = plain.font
        if chosen:
            title_font.setBold(True)
        painter.setFont(title_font)
        title_area = QRect(area.left(), area.top(), area.width(), line)
        # **Gebrochen gemessen und aufgerundet.** ``QFontMetrics`` gibt ganze
        # Pixel, das Kürzen rechnet mit der echten Breite: Mit Cocoas
        # gebrochenen Metriken stand „Ctrl+B“ als „Ctrl…“ da (RM-531).
        shortcut_width = (
            min(math.ceil(QFontMetricsF(plain.font).horizontalAdvance(shortcut)), area.width() // 2)
            if shortcut
            else 0
        )
        if shortcut_width:
            title_area.setWidth(max(0, title_area.width() - shortcut_width - NORMAL))
        flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        shown = painter.fontMetrics().elidedText(
            title, Qt.TextElideMode.ElideRight, title_area.width()
        )
        painter.drawText(title_area, flags, shown)
        painter.setFont(plain.font)
        if shortcut:
            painter.drawText(
                QRect(area.right() - shortcut_width + 1, area.top(), shortcut_width, line),
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                metrics.elidedText(shortcut, Qt.TextElideMode.ElideRight, shortcut_width),
            )
        lines = self._lines_of(area.width(), detail, plain)
        if lines:
            painter.drawText(
                QRect(area.left(), area.top() + line + TIGHT, area.width(), lines * line),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                | int(Qt.TextFlag.TextWordWrap),
                detail,
            )
        painter.restore()


class _HitList(QListWidget):
    """Die Treffer der Suche — so hoch, wie die ersten :data:`HITS_SHOWN` verlangen.

    Ohne eigene Wunschhöhe nimmt die Liste Qts feste 192 Punkte: drei Treffer
    in einem großen leeren Feld oder zwanzig in einem Schlitz. Die Karte
    deckelt am Fenster, und darüber rollt die Liste in sich.
    """

    @override
    def sizeHint(self) -> QSize:
        rows = min(self.count(), HITS_SHOWN)
        height = sum(self.sizeHintForRow(row) for row in range(rows))
        return QSize(super().sizeHint().width(), height + 2 * self.frameWidth())

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Eine andere Breite bricht die zweiten Zeilen anders um."""
        super().resizeEvent(event)
        self.doItemsLayout()
        self.updateGeometry()


#: Die Tasten, die im Suchfeld ihm gehören und nicht dem Fenster
#: (:meth:`SelectionOperationsPanel._search_key`).
_SEARCH_KEYS: Final = frozenset(
    {Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Up, Qt.Key.Key_Down}
)

#: Die Ereignisse, nach denen die Klappe „Filament und Druck“ neu bewertet wird.
_SHOWN_OR_HIDDEN: Final = (QEvent.Type.ShowToParent, QEvent.Type.HideToParent)
_CAME_OR_WENT: Final = (QEvent.Type.ChildAdded, QEvent.Type.ChildRemoved)


class _ListScroller(ContentScroller):
    """Der Rollbereich der Operationsliste — so hoch, wie die sichtbaren Knöpfe es verlangen.

    **Qt fragt seinen Inhalt nur einmal** (RM-232, 25.09.2026):
    ``QScrollArea.sizeHint`` merkt sich die Wunschhöhe des Inhalts beim
    ersten Fragen, und das war beim Aufbau, als alle Handlungen sichtbar
    waren. An einer Bohrung stehen darin drei Knöpfe, 81 Punkte hoch; die
    Liste verlangte weiter 384. Hier wird der Inhalt bei jeder Frage gefragt
    (:class:`~app.ui.overlay.ContentScroller`), und jeder Umbau seines Layouts
    meldet die neue Höhe nach oben weiter.

    **Ohne eigene Grenze** (RM-510): Bis dahin hielt die Liste bei 24
    Schriftzeilen an und rollte, während die Karte darüber noch Platz hatte —
    bei 1600 x 1000 standen am Körper 15 Einträge sichtbar. Jetzt deckelt die
    Karte am Fenster (``overlay.natural_height``), und wo das nicht reicht,
    rollt die Liste in sich; Hauptaktionen und Suche bleiben dabei stehen.
    """

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # ``setWidget`` hat den Rollbereich selbst als Filter am Inhalt
        # eingetragen; ein neu gelegter Inhalt heißt eine neue Wunschhöhe.
        if watched is self.widget() and event.type() == QEvent.Type.LayoutRequest:
            self.updateGeometry()
        return super().eventFilter(watched, event)


class SelectionOperationsPanel(QWidget):
    """Alle Handlungen für die aktuelle Auswahl, dauerhaft aufgebaut."""

    operationRequested = Signal(object)
    catalogRequested = Signal()
    matchingPartsRequested = Signal(str)
    """Der Katalog, gefiltert auf diese Merkmalsart (:data:`MATCHING_PARTS_AT`)."""
    searchChosen = Signal(str)
    """Ein Treffer der Suche soll laufen — eine Operation oder ein Fensterbefehl,
    beim Namen genannt. Das Fenster prüft die Freigabe ein zweites Mal."""
    searchLeft = Signal()
    """Der Fokus geht vom Suchfeld zurück in die Ansicht (Escape, Ausführen)."""
    manualRequested = Signal(str)
    """*Im Handbuch suchen* mit dem Wort, das hier nichts fand."""
    rebuildRequested = Signal()
    """*Modell nachbauen* am gewählten Körper (:data:`REBUILD`)."""

    def __init__(self, specs: Iterable[OperationSpec], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("selectionOperations")
        self.setAccessibleName(tr("Operationen für die Auswahl"))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(PANEL_LEAST_HEIGHT)

        # **Einmal aufgezählt, nicht zweimal durchlaufen.** Die Signatur nimmt
        # ein ``Iterable``, und ein Generator wäre beim zweiten Filter leer.
        specs = tuple(specs)
        # Eine Handlung an beiden Stufen (``also_on_body``) steht in beiden
        # Filtern und bekommt trotzdem nur einen Knopf.
        by_name = {
            spec.name: spec
            for spec in (
                *body_operations(specs),
                *feature_operations(specs),
                *scene_creators(specs),
            )
        }
        operations = tuple(by_name.values())
        self._creators = frozenset(spec.name for spec in scene_creators(specs))
        """Was ohne Auswahl einen Körper anlegt (:func:`scene_creators`) — es steht
        auf der Stufe ohne Auswahl und auf keiner anderen."""
        self._searched = frozenset(spec.name for spec in specs)
        """Welche Operationen die Suche kennt: alle, die das Panel bekommen hat,
        jeder Stufe — auch die Bausteine des Katalogs (RM-735)."""
        self._commands: Callable[[], list[SearchEntry]] = list
        """Die Befehle des Fensters als Zeilen der Suche (:meth:`set_search_sources`)."""
        self._key_of: Callable[[str, str | None], str | None] = lambda _name, declared: declared
        """Die Taste einer Operation in der eingestellten Belegung."""
        self._as_commands: frozenset[str] = frozenset()
        """Operationen, die die Suche als Fensterbefehl zeigt (*Modell einfügen*)."""
        self._availability: Callable[[str], tuple[bool, str]] = lambda _name: (True, "")
        """Die Freigabe aus dem letzten :meth:`set_context` — auch für die Suche."""
        self._rows: list[SearchEntry] | None = None
        """Die Zeilen der Suche zu dieser Auswahl, gebaut beim ersten Zeichen
        und verworfen, sobald sich Auswahl oder Freigabe ändern."""
        self._hits: list[SearchEntry] = []
        """Was die Trefferliste gerade zeigt, in ihrer Reihenfolge."""
        self._at_a_feature = frozenset(spec.name for spec in feature_operations(specs))
        """Welche Handlungen einem **Merkmal** gelten.

        Die Stufe steht schon im Register (``applies_to``), und genau daraus
        entsteht diese Menge — ein eigenes Feld daneben wäre die zweite
        Wahrheit. Gebraucht wird sie in :meth:`set_context`, das nach der
        gewählten Stufe ein- und ausblendet (Konzept „Ein Ort für die
        Auswahl", C)."""
        self._at_which_kind = {
            spec.name: frozenset(spec.applies_to) for spec in feature_operations(specs)
        }
        """Und an **welcher Art** von Merkmal jede von ihnen etwas tut.

        Dieselbe Quelle, einen Schritt genauer: ``applies_to`` nennt nicht nur
        *dass* eine Handlung einem Merkmal gilt, sondern welchem. Ohne diesen
        Schritt beantwortete :meth:`_fits_the_level` nur die gröbere Frage, und
        an einer gewählten Bohrung standen alle 18 Merkmalshandlungen — auch
        *Text aufbringen* und *Filament auf eine Fläche*, die beide nur an
        ``face`` etwas tun. Zuständig sind an einer Bohrung neun, an einer
        Senkung sechs (gemessen 09.09.2026; Robert: „bei einer Bohrung oder
        Senkung brauchen wir Filament und die Körperliste gar nicht")."""
        self._on_body = frozenset(spec.name for spec in specs if spec.also_on_body)
        """Merkmalshandlungen, die auch am ganzen Körper gelten (``also_on_body``)."""
        self._for_all_bodies = frozenset(spec.name for spec in operations if spec.takes_whole_scene)
        """Handlungen, die alle Körper der Szene nehmen — Ausrichten, Anordnen,
        Überschneidungen prüfen.

        **Sie stehen da, wenn nichts gewählt ist, und nicht an einer Auswahl**
        (Robert, 27.09.2026: „sollten wir aber anzeigen, wenn keins ausgewählt
        ist und nicht wenn eins ausgewählt ist, da es eine operation für alle
        ist"). Am gewählten Körper sagte der Knopf, er gelte diesem Körper, und
        tat es nicht."""
        self._nothing_chosen = False
        """Ob gerade nichts gewählt ist — die Stufe der ganzen Szene."""
        self._buttons: dict[str, QToolButton] = {}
        self._list_twins: dict[str, QToolButton] = {}
        """Je Hauptaktion ihr Knopf in der Liste — verborgen, solange sie oben steht.

        Eine Hauptaktion der einen Stufe kann an einer anderen gelten, ohne dort
        oben zu stehen: *Aushöhlen* an einer Fläche, *Reparieren* am ganzen
        Körper. Ohne Listenknopf stand sie dann nirgends (gemessen 06.10.2026;
        Fragebogen zu 0.5.3)."""
        self._groups: dict[str, tuple[QWidget, QToolButton, tuple[QToolButton, ...]]] = {}
        """Je Gruppe ihr Abschnitt, sein Umschalter und ihre Knöpfe.

        Der Abschnitt ist das, was die Suche ein- und ausblendet; der
        Umschalter das, was sie beim Treffer öffnet — ein Treffer in einer
        zugeklappten Gruppe wäre sonst einer, den niemand sieht."""
        self._states: dict[str, tuple[bool, str]] = {}
        self._grids: dict[str, QGridLayout] = {}
        """Je Gruppe das Raster ihrer Zeilen."""
        self._arranged: dict[str, tuple[int, tuple[int, ...]]] = {}
        """Je Gruppe die Spaltenzahl und die Zeilen, für die zuletzt gelegt wurde."""
        self._quick_buttons: dict[str, QToolButton] = {}
        self._quick_shown: list[str] = []
        self._quick_columns = 1
        self._query = ""
        """Der zuletzt eingegebene Suchtext — ein Stufenwechsel darf ihn nicht
        vergessen."""
        self._wrapped_for: tuple[int, int, tuple[str, ...], tuple[int, ...]] | None = None
        """Für welche Breiten und Hauptaktionen die Beschriftungen zuletzt
        umbrochen wurden (:meth:`_wrap_labels`)."""
        self._folded_by_hand: set[str] = set()
        """Die Gruppen, deren Klappe jemand selbst bewegt hat.

        Für sie gilt die Regel aus :data:`OPEN_UP_TO` nicht mehr: Wer „Ändern"
        aufgeklappt hat, will es nach dem nächsten Klick auf einen Körper nicht
        wieder zu vorfinden. ``clicked`` feuert nur bei einer Geste, nicht bei
        ``setChecked`` — das ist genau die Unterscheidung."""
        self._feature_kind: str | None = None
        """Die Art des gewählten Merkmals, leer auf der Körperstufe.

        ``None`` heißt „noch nie gesetzt" und ist von der Körperstufe (``""``)
        zu unterscheiden: Beim Aufbau stehen alle Knöpfe sichtbar da, und der
        erste :meth:`set_context` muss deshalb filtern, auch wenn er die
        Körperstufe meldet. Mit ``""`` als Startwert tat er es nicht — und an
        einem Körper standen die Merkmalshandlungen weiter in der Liste."""
        self._left_out: frozenset[str] = frozenset()
        """Was am gewählten Merkmal nicht angeboten wird, obwohl seine Art es
        trägt — am Kegel, der keine Senkung ist, *Senken* (R3)."""
        self._only: frozenset[str] | None = None
        """An einem Bausteinmerkmal die einzigen Handlungen der Karte
        (:data:`~app.core.perceive.actions.OFFERED_AT_A_PART`), sonst ``None``."""
        self._window_actions: dict[str, QAction] = {}
        """Handlungen des Fensters ohne Registereintrag, je Name ihre Aktion
        (:meth:`add_window_action`). Freigabe und Grund kommen von der Aktion."""

        self.summary = QLabel("", self)
        self.summary.setWordWrap(True)
        set_level(self.summary, "section")
        self.summary.setAccessibleName(tr("Aktuelle Auswahl"))

        # Die Hauptaktionen jeder Lage bekommen ihren Knopf hier und behalten
        # ihn: eingehängt wird bei jedem Auswahlwechsel, gebaut nie wieder.
        # Verborgen, solange sie nicht in der Zeile stehen — ein Kind ohne
        # Layoutplatz zeichnete Qt sonst in der linken obersten Ecke.
        quick = QGridLayout()
        quick.setContentsMargins(0, 0, 0, 0)
        quick.setHorizontalSpacing(TIGHT)
        quick.setVerticalSpacing(TIGHT)
        quick.setColumnStretch(0, 1)
        quick.setColumnStretch(1, 1)
        self._quick = quick
        for name in all_quick_names():
            spec = by_name.get(name)
            if spec is None:
                continue
            button = self._operation_button(spec)
            # Die Zweierspalte darf nicht selbst die Mindestbreite des Docks
            # erzwingen: Bei wenig Platz werden ihre Knöpfe untereinander gesetzt.
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            button.setObjectName("quickOperation")
            button.hide()
            self._quick_buttons[name] = button
        rebuild = QToolButton(self)
        title = tr("Modell nachbauen")
        rebuild.setText(title)
        rebuild.setProperty("operationTitle", title)
        rebuild.setIcon(icon("category.primitive", rebuild))
        rebuild.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        rebuild.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        rebuild.setMinimumHeight(TARGET_SIZE)
        rebuild.setObjectName("quickOperation")
        tip = tr("Baut den Körper aus erkannten Formen nach; seine Maße werden danach änderbar.")
        rebuild.setToolTip(tip)
        rebuild.setAccessibleDescription(tip)
        rebuild.clicked.connect(self.rebuildRequested)
        rebuild.hide()
        self._quick_buttons[REBUILD] = rebuild
        self.rebuild_button = rebuild

        # **Der Weg zu den Booleschen bei einem gewählten Körper** (RM-734): Wer
        # aus Fusion kommt, sucht erst das Werkzeug; hier stehen die drei oben,
        # sobald zwei Körper gewählt sind. Die Zeile sagt, wie der zweite
        # dazukommt (:meth:`_say_how_to_pair`).
        self.pairing_hint = QLabel(self)
        self.pairing_hint.setWordWrap(True)
        set_level(self.pairing_hint, "caption")
        self.pairing_hint.setVisible(False)

        # **Ein Suchfeld, immer da, über alles** (RM-735, Entscheidung Robert
        # 11.10.2026): Es ersetzt die Befehlspalette. Gesucht wird über jede
        # Operation jeder Stufe, die Bausteine des Katalogs und die Befehle des
        # Fensters; was an der Auswahl geht, steht vorn, was nicht, nennt den
        # Grund. Das Wort heißt wie der Knopf oben, der hierher führt
        # (:meth:`set_search_words`).
        self.search = QLineEdit(self)
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(TARGET_SIZE)
        self.search.setPlaceholderText(tr("Funktion suchen …"))
        self.search.setAccessibleName(tr("Funktion suchen"))
        self.search.textChanged.connect(self._filter)
        # Escape, Return und die Pfeiltasten gehören dem Feld
        # (:meth:`eventFilter`): Escape war eine Fensteraktion und hob an einem
        # Merkmal die Auswahl samt Entwurf auf; Return lief an eine laufende
        # Platzierung in derselben Spalte weiter.
        self.search.installEventFilter(self)

        self._nothing = QLabel(self)
        self._nothing.setWordWrap(True)
        set_level(self._nothing, "caption")
        self._nothing.setVisible(False)
        # **Ohne Treffer weiter ins Handbuch** (§2.7): Es kennt Wörter, die
        # keine Operation sind, und sucht mit denselben Kundenwörtern.
        self._manual = QPushButton(tr("Im Handbuch suchen"), self)
        self._manual.setVisible(False)
        self._manual.clicked.connect(self._search_the_manual)

        self.hits = _HitList(self)
        self.hits.setObjectName("searchHits")
        self.hits.setAccessibleName(tr("Gefundene Funktionen"))
        self.hits.setItemDelegate(_HitRows(self.hits))
        self.hits.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hits.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.hits.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.hits.setVisible(False)
        # Ein Klick führt aus wie jeder Knopf der Karte, Return in der Liste
        # ebenso — am Mac über :func:`return_opens`. Ein Doppelklick führt
        # einmal aus: Der erste Klick leert die Liste.
        self.hits.itemClicked.connect(self._choose_item)
        self.hits.itemActivated.connect(self._choose_item)
        return_opens(self.hits, sys.platform)

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        # Zwischen den Gruppen Luft, innerhalb eng: Die Gruppe ist die
        # Einheit, die man überblickt, nicht der einzelne Knopf.
        content_layout.setSpacing(NORMAL)

        grouped: dict[str, list[OperationSpec]] = {}
        ranks: dict[str, tuple[int, int, int, int]] = {}
        for spec in operations:
            # **Was oben steht, steht nicht auch darunter** — zwei Knöpfe für
            # dieselbe Handlung sind eine Frage ohne Antwort. Entschieden wird
            # das je Stufe in :meth:`_filter`, nicht hier: Bis zum 06.10.2026
            # bekam eine Hauptaktion gar keinen Listenknopf, und wo sie galt,
            # ohne oben zu stehen, fehlte sie ganz (:attr:`_list_twins`).
            rank, title = _card_group(spec)
            ranks[title] = min(rank, ranks.get(title, rank))
            grouped.setdefault(title, []).append(spec)
        for title in sorted(grouped, key=lambda name: (ranks[name], sort_key(name))):
            # **Jede Gruppe ein Abschnitt, der sich zuklappen lässt** — mit
            # der Kopfzeile und der Linie darunter, die auch die linke Spalte
            # trägt (:func:`collapsible`). Eine graue Zwischenüberschrift über
            # einer Liste gleicher Knöpfe machte aus fünfzig Handlungen eine
            # Wand (Robert, 11.09.2026: „sieht alles ziemlich monoton und
            # dadurch unübersichtlich aus").
            box = QWidget(content)
            # Ein Raster statt einer Spalte: Wo die Karte breit genug ist,
            # stehen die Zeilen einer Gruppe zu zweit (:meth:`_arrange_groups`).
            box_layout = QGridLayout(box)
            box_layout.setContentsMargins(0, TIGHT, 0, 0)
            box_layout.setHorizontalSpacing(TIGHT)
            box_layout.setVerticalSpacing(0)
            self._grids[title] = box_layout
            buttons: list[QToolButton] = []
            for spec in sorted(grouped[title], key=lambda entry: sort_key(entry.title)):
                button = self._operation_button(spec, box, twin=spec.name in self._quick_buttons)
                button.setObjectName("operationRow")
                button.setAutoRaise(True)
                button.setMinimumHeight(LIST_ROW_HEIGHT)
                box_layout.addWidget(button, len(buttons), 0)
                buttons.append(button)
            section = collapsible(title, box)
            section.setParent(content)
            toggle = section.findChild(QToolButton, "sectionHeading")
            assert toggle is not None
            toggle.clicked.connect(
                weak_slot(self, SelectionOperationsPanel._folded_by_a_click, title)
            )
            content_layout.addWidget(section)
            self._groups[title] = (section, toggle, tuple(buttons))
        content_layout.addStretch(1)

        self.scroller = _ListScroller(self)
        self.scroller.setWidget(content)
        self.scroller.setWidgetResizable(True)
        self.scroller.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroller.setMinimumHeight(TARGET_SIZE)
        self.scroller.setAccessibleName(tr("Passende Operationen"))

        # **Der Knopf *Merkmale* ist mit dem Umzug entfallen** (Konzept „Ein
        # Ort für die Auswahl", A und C). Er tat nichts, als vom einen Ort zum
        # anderen zu führen — und seit die Maße des Gewählten über diesen
        # Handlungen stehen, führt er nirgendwohin.
        # **Ein Hauptknopf, kein Listeneintrag.** Er stand als grauer
        # Werkzeugknopf unter der Liste und ging zwischen den Handlungen
        # unter — dabei ist der Katalog an einem Körper oder einer Fläche der
        # Weg zu 27 Teilen auf einmal (Robert, 11.09.2026: „wäre es auch gut in
        # Orange zu machen damit er auch auffällt"). Akzentfarbe und halbfett
        # kommen aus :func:`make_primary`, wie beim Übernehmen im
        # Merkmalfenster — Fett ist die zweite Kodierung (Regel 18).
        # ``make_large_target`` **und** ``setMinimumHeight``: Das Stylesheet
        # setzt seine ``min-height`` beim Polieren erneut, und aus 44 Punkten
        # würden 26 (siehe :func:`make_large_target`) — ohne Stylesheet gilt
        # umgekehrt nur die Mindesthöhe am Widget.
        self.catalog_button = make_large_target(
            make_primary(QPushButton(tr("Bausteinkatalog …"), self))
        )
        self.catalog_button.setIcon(icon("category.parts", self.catalog_button))
        self.catalog_button.setMinimumHeight(TARGET_SIZE)
        self.catalog_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.catalog_button.setToolTip(
            tr("Öffnet den vollständigen Bausteinkatalog mit Bildern und Suche.")
        )
        self.catalog_button.setAccessibleDescription(self.catalog_button.toolTip())
        self.catalog_button.clicked.connect(self._catalog_clicked)
        self._catalog_kind = ""
        """Die Merkmalsart, auf die der Knopf den Katalog filtert — oder keine."""

        separate = QHBoxLayout()
        separate.setContentsMargins(0, 0, 0, 0)
        separate.setSpacing(TIGHT)
        separate.addWidget(self.catalog_button)

        # **Filament zugeklappt unter der Liste** (RM-510): Vor *Bohrung
        # setzen* standen zehn Bedienelemente und 44 Wörter zu Filament und
        # Nahtschutz. Die Reihenfolge ist jetzt Kopf, Hauptaktionen, Liste,
        # Bausteine und dann das Filament; zugeklappt nennt die Zeile die
        # Zuweisung (:meth:`describe_print`). Den Wähler hängt das Fenster ein
        # (:meth:`add_print_widget`).
        self._print_widget: QWidget | None = None
        self._print_box = QWidget(self)
        self._print_rows = QVBoxLayout(self._print_box)
        self._print_rows.setContentsMargins(0, 0, 0, 0)
        self._print_rows.setSpacing(TIGHT)
        # Kommt oder geht ein Inhalt — der Nahtschutz des Merkmalfensters
        # entsteht je Merkmal neu —, wird die Klappe neu bewertet.
        self._print_box.installEventFilter(self)
        self.print_section = collapsible(
            tr("Filament und Druck"),
            self._print_box,
            open_now=False,
            contents=tr("Noch kein Filament zugewiesen"),
            remember="selection.filament",
        )
        self.print_section.setParent(self)
        self.print_section.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, NORMAL)
        layout.setSpacing(TIGHT)
        layout.addWidget(self.summary)
        layout.addLayout(quick)
        layout.addWidget(self.pairing_hint)
        layout.addWidget(self.search)
        layout.addWidget(self._nothing)
        layout.addWidget(self._manual)
        layout.addWidget(self.hits, 1)
        layout.addWidget(self.scroller, 1)
        layout.addLayout(separate)
        layout.addWidget(self.print_section)
        self.hide()

    def add_print_widget(self, widget: QWidget) -> None:
        """Hängt den Filamentwähler in den zugeklappten Abschnitt unter der Liste.

        Der Abschnitt steht, solange der Wähler steht: Das Fenster blendet ihn
        je nach Auswahl ein und aus, und eine leere Klappe wäre ein Angebot
        ohne Inhalt.
        """
        self._print_rows.insertWidget(0, widget)
        self._print_widget = widget
        widget.installEventFilter(self)
        self._settle_print_section()

    def print_rows(self) -> QVBoxLayout:
        """Wohin weitere Druckangaben gehören — der Nahtschutz des Merkmalfensters."""
        return self._print_rows

    def _settle_print_section(self) -> None:
        """Die Klappe steht, solange etwas in ihr steht."""
        shown = any(
            not child.isHidden()
            for child in self._print_box.children()
            if isinstance(child, QWidget) and isValid(child)
        )
        self.print_section.setVisible(shown)

    def describe_print(self, text: str) -> None:
        """Was zugeklappt unter „Filament“ steht — die aktuelle Zuweisung."""
        summary = self.print_section.findChild(QLabel, "sectionSummary")
        heading = self.print_section.findChild(QToolButton, "sectionHeading")
        if summary is not None:
            summary.setText(text)
        if heading is not None:
            heading.setToolTip(text)
            heading.setAccessibleDescription(text)

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if stop_watching_the_dying(self, watched, event):
            return False
        if watched is self.search and isinstance(event, QKeyEvent):
            return self._search_key(event)
        if (watched is self._print_widget and event.type() in _SHOWN_OR_HIDDEN) or (
            watched is self._print_box and event.type() in _CAME_OR_WENT
        ):
            self._settle_print_section()
        return super().eventFilter(watched, event)

    def _search_key(self, event: QKeyEvent) -> bool:
        """Was das Suchfeld mit Escape, Return und den Pfeiltasten tut — und dass
        sie ihm gehören.

        **Escape geht eine Stufe zurück, im Feld zuerst** (§18.5): Mit Text
        leert es das Feld, ohne Text gibt es den Fokus an die Ansicht. Bis
        RM-735 lief es an die Fensteraktion und hob an einem Merkmal mit Maßen
        im Bild die Auswahl samt Entwurf auf. **Return führt den vorgewählten
        Treffer aus** und läuft nicht an eine laufende Platzierung in derselben
        Spalte weiter (``placement_flow``). Die Pfeiltasten bewegen die
        Vorauswahl, wie in jeder Suchliste.
        """
        key = Qt.Key(event.key())
        if key not in _SEARCH_KEYS:
            return False
        if event.type() == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        if event.type() != QEvent.Type.KeyPress:
            return False
        if key == Qt.Key.Key_Escape:
            if self.search.text():
                self.search.clear()
            else:
                self.searchLeft.emit()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self.hits.currentItem() if self.hits.isVisible() else None
            if item is not None:
                self._choose_item(item)
        else:
            self._step_through_hits(1 if key == Qt.Key.Key_Down else -1)
        return True

    def _step_through_hits(self, step: int) -> None:
        """Die Vorauswahl einen Treffer weiter — über die Kopfzeile der Lockerung hinweg."""
        row = self.hits.currentRow()
        while 0 <= row + step < self.hits.count():
            row += step
            item = self.hits.item(row)
            if item is not None and item.flags() & Qt.ItemFlag.ItemIsSelectable:
                self.hits.setCurrentRow(row)
                return

    def _choose_item(self, item: QListWidgetItem) -> None:
        """Ein Treffer soll laufen.

        **Ausführbar: Feld leer, Fokus in die Ansicht, dann die Handlung** —
        in dieser Reihenfolge. Bliebe der Fokus im Feld, nähme Strg+Z das Tippen
        zurück statt des Schritts, und ein Dialog gibt beim Schließen den Fokus
        dorthin zurück, wo er vorher war. **Gesperrt:** Das Fenster nennt den
        Grund, Text und Fokus bleiben, damit Wort oder Auswahl nachzubessern sind.
        """
        if not isValid(item) or self.hits.row(item) < 0:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(name, str):
            return
        if item.flags() & Qt.ItemFlag.ItemIsEnabled:
            self.search.clear()
            self.searchLeft.emit()
        self.searchChosen.emit(name)

    def _search_the_manual(self, _checked: bool = False) -> None:
        """*Im Handbuch suchen* — mit dem Wort, das hier nichts fand."""
        self.manualRequested.emit(self._query.strip())

    def set_search_words(self, words: str) -> None:
        """Was im leeren Feld steht — dasselbe wie am Knopf *Funktion suchen* oben."""
        self.search.setPlaceholderText(words)

    def set_search_sources(
        self,
        commands: Callable[[], list[SearchEntry]],
        key_of: Callable[[str, str | None], str | None],
        as_commands: frozenset[str],
    ) -> None:
        """Was die Suche außer den Operationen kennt — die Befehle des Fensters.

        ``commands`` liefert sie mit Freigabe und Kürzel, ``key_of`` die Taste
        einer Operation in der eingestellten Belegung, ``as_commands`` die
        Operationen, die dort schon als Befehl stehen (*Modell einfügen*).
        Gefragt wird erst beim ersten Zeichen (:meth:`_search_rows`).
        """
        self._commands = commands
        self._key_of = key_of
        self._as_commands = as_commands
        self._rows = None

    def focus_search(self) -> None:
        """Der Cursor ins Suchfeld, vorhandener Text markiert (*Funktion suchen*)."""
        self.search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search.selectAll()

    def _operation_button(
        self, spec: OperationSpec, parent: QWidget | None = None, *, twin: bool = False
    ) -> QToolButton:
        """Einen Registereintrag als direkte, tastaturfähige Handlung bauen.

        ``twin`` baut den Listenknopf einer Hauptaktion (:attr:`_list_twins`);
        unter ihrem Namen in :attr:`_buttons` bleibt der Knopf oben.
        """
        button = QToolButton(parent or self)
        button.setText(str(spec.title))
        button.setIcon(icon(icon_name_for(spec), button))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setMinimumHeight(TARGET_SIZE)
        warning = caveat_line(spec)
        tip = f"{spec.doc}\n\n{warning}" if warning else str(spec.doc)
        button.setToolTip(tip)
        button.setAccessibleDescription(tip)
        button.clicked.connect(weak_slot(self, SelectionOperationsPanel._request_operation, spec))
        button.setProperty("operationName", spec.name)
        # Der ungebrochene Titel bleibt am Knopf: :meth:`_wrap_label` schreibt
        # ``text()`` um, und ein zweiter Lauf darf nicht auf seinem eigenen
        # Ergebnis weiterrechnen. Die Suche liest ebenfalls von hier — mit
        # einem Umbruch mitten im Titel fände „bohrung verschließen" sich
        # selbst nicht mehr.
        button.setProperty("operationTitle", str(spec.title))
        (self._list_twins if twin else self._buttons)[spec.name] = button
        return button

    def add_window_action(self, name: str, category: str, action: QAction) -> bool:
        """Eine Handlung des Fensters als Zeile der Gruppe ihrer Kategorie.

        *Automatisch teilen* ist ein Ablauf über mehreren Operationen und kein
        Registereintrag; es stand deshalb im Menü *Bearbeiten*, weit weg von
        den übrigen Wegen, ein Teil zu teilen (RM-507). Hier steht es bei
        ihnen, am gewählten Körper, sortiert wie die Registerzeilen. Freigabe
        und Grund liest :meth:`_take_availability` von der Aktion — dieselbe,
        die Suche und Kürzel auslösen.

        ``False``, wenn es die Gruppe nicht gibt (keine Operation der Kategorie
        im Register): Dann sucht sich der Aufrufer einen anderen Platz — ein
        Eintrag darf umziehen, nicht verschwinden.
        """
        _rank, title = _category_group(category)
        if title not in self._groups:
            return False
        section, toggle, buttons = self._groups[title]
        grid = self._grids[title]
        box = grid.parentWidget()
        button = QToolButton(box)
        label = action.text()
        button.setText(label)
        button.setIcon(action.icon())
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setObjectName("operationRow")
        button.setAutoRaise(True)
        button.setMinimumHeight(LIST_ROW_HEIGHT)
        button.setToolTip(action.toolTip())
        button.setAccessibleDescription(action.toolTip())
        button.clicked.connect(action.trigger)
        button.setProperty("operationName", name)
        button.setProperty("operationTitle", label)
        self._buttons[name] = button
        self._window_actions[name] = action
        ordered = sorted(
            (*buttons, button),
            key=lambda entry: sort_key(str(entry.property("operationTitle") or entry.text())),
        )
        self._groups[title] = (section, toggle, tuple(ordered))
        self._arranged.pop(title, None)
        self._rows = None
        self._filter()
        return True

    def _request_operation(self, spec: OperationSpec) -> None:
        """Den Registereintrag ohne dauerhafte Lambda-Rückbindung weiterreichen."""
        self.operationRequested.emit(spec)

    def _lay_out_quick(self, names: Iterable[str]) -> None:
        """Die Hauptaktionen dieser Lage in die Zeile oben hängen.

        Zwei kurze teilen die erste Zeile, wenn ihre vollständigen Titel
        nebeneinander passen. In der schmalen Auswahlspalte stehen sie
        untereinander; die Breite des Fensters folgt nicht der Zweierspalte.

        Steht schon das Richtige da, passiert nichts: Auswahlereignisse kommen
        in Serie, und ein Layout, das bei jedem neu hängt, wirft bei jedem ein
        ``LayoutRequest`` — dasselbe Ereignis, an dem die Überlagerung ihre
        Karten neu verteilt.
        """
        wanted = [name for name in names if name in self._quick_buttons]
        layout = self.layout()
        margins = layout.contentsMargins() if layout is not None else self.contentsMargins()
        available = self.width() - margins.left() - margins.right()
        # **Der breitere von beiden entscheidet, nicht ihre Summe.** Die zwei
        # Spalten stehen auf gleicher Dehnung, teilen den Platz also hälftig:
        # Ein Knopf von 120 und einer von 60 Punkten passen zusammen in 190,
        # aber der breitere bekommt nur 95 davon. Genau so stand „Bohrung
        # ändern" neben „Senken" und las sich „Bohru…ndern" (Befund Robert,
        # 09.09.2026). Gefragt ist deshalb, ob **jeder** von beiden in seine
        # Hälfte passt.
        paired_width = (
            2 * max(self._quick_buttons[name].sizeHint().width() for name in wanted[:2])
            + self._quick.horizontalSpacing()
            if wanted
            else 0
        )
        columns = 2 if len(wanted) > 1 and paired_width <= available else 1
        if wanted == self._quick_shown and columns == self._quick_columns:
            return
        for name in self._quick_shown:
            button = self._quick_buttons[name]
            self._quick.removeWidget(button)
            button.hide()
        self._quick_shown = wanted
        self._quick_columns = columns
        self._quick.setColumnStretch(1, 1 if columns == 2 else 0)
        # Nach der ersten Zeile stehen zwei weitere nebeneinander, wenn beide in
        # ihre Hälfte passen (am Körper *Teilen* und *Modell nachbauen*), sonst
        # nimmt einer die ganze Breite.
        half = (available - self._quick.horizontalSpacing()) // 2
        row = 0
        index = 0
        while index < len(wanted):
            pair = wanted[index : index + 2] if columns == 2 else wanted[index : index + 1]
            if len(pair) == 2 and (
                index == 0
                or max(self._quick_buttons[name].sizeHint().width() for name in pair) <= half
            ):
                for column, name in enumerate(pair):
                    self._quick.addWidget(self._quick_buttons[name], row, column)
            else:
                pair = pair[:1]
                self._quick.addWidget(self._quick_buttons[pair[0]], row, 0, 1, columns)
            for name in pair:
                self._quick_buttons[name].show()
            index += len(pair)
            row += 1

    def _wrap_label(self, button: QToolButton, room: int) -> None:
        """Die Beschriftung auf die verfügbare Breite umbrechen, nicht abschneiden.

        „Bohrung verschließen" will 292 Bildpunkte; das Auswahlfenster ist am
        rechten Rand rund 180 breit, und Qt schnitt den Titel dann zu
        „Bohrung versch…" (Befund Robert, 09.09.2026). Ein abgeschnittener
        Titel ist keine Auskunft — er nennt die Handlung nicht mehr, und
        anders als bei einem Hinweis gibt es hier keinen zweiten Ort, an dem
        sie stünde.

        Gemessen wird gegen die Schrift, mit der wirklich gezeichnet wird, und
        das Beiwerk des Knopfes — Symbol, Rand, Innenabstand — kommt aus der
        Differenz zu seinem Wunschmaß, nicht aus einer Zahl im Stylesheet: Die
        Suite fährt ohne Stylesheet, und eine geratene Konstante wäre dort
        eine andere als beim Kunden.

        **Höchstens zwei Zeilen.** Ein Knopf, der drei Zeilen hoch wird, ist
        keine Handlung mehr, sondern ein Absatz; wo zwei nicht reichen, bleibt
        Qts Auslassung der ehrlichere Rest.
        """
        title = str(button.property("operationTitle") or button.text())
        words = title.split()
        metrics = button.fontMetrics()
        # Das Wunschmaß muss denselben ungebrochenen Titel messen wie die
        # Schriftbreite; sonst wechselt der Umbruch beim nächsten Aufruf.
        button.setText(title)
        chrome = button.sizeHint().width() - metrics.horizontalAdvance(title.replace(chr(10), " "))
        space = room - chrome
        if len(words) < 2 or space <= 0 or metrics.horizontalAdvance(title) <= space:
            if button.text() != title:
                button.setText(title)
            return
        # Gierig füllen, aber nur eine Umbruchstelle suchen: Die zweite Zeile
        # nimmt den Rest, und ob der passt, entscheidet Qt wie bisher.
        first = words[0]
        cut = 1
        for index in range(1, len(words)):
            wider = f"{first} {words[index]}"
            if metrics.horizontalAdvance(wider) > space:
                break
            first = wider
            cut = index + 1
        rest = " ".join(words[cut:])
        broken = f"{first}\n{rest}" if cut < len(words) else title
        if button.text() != broken:
            button.setText(broken)

    def _wrap_labels(self) -> None:
        """Jede sichtbare Beschriftung an die heutige Breite anpassen.

        Die Hauptaktionen teilen sich ihre Zeile, die Liste darunter läuft über
        die ganze Breite des Rollbereichs — beide Male ist die Frage dieselbe,
        und beide Male ändert sie sich nur, wenn das Fenster sich ändert.
        """
        layout = self.layout()
        margins = layout.contentsMargins() if layout is not None else self.contentsMargins()
        inner = self.width() - margins.left() - margins.right()
        share = (
            (inner - self._quick.horizontalSpacing()) // 2 if self._quick_columns == 2 else inner
        )
        room = self.scroller.viewport().width()
        columns = tuple(self.columns_of(title) for title in self._groups)
        # **Nur, wenn sich eine Breite oder die Hauptaktionen geändert haben.**
        # Jeder Merkmalklick änderte die Höhe der Karte darüber, und jede
        # Höhenänderung lief hierher: gut hundert Knöpfe, jeder zweimal neu
        # beschriftet (erst ganz, dann umbrochen) — im gebauten Fenster am
        # Halter mit Wabenmuster 37 ms je Klick (22.09.2026). Eine Höhe bricht
        # keine Zeile um; der Rollbalken, der mit ihr kommt, ändert ``room``
        # und steht damit im Schlüssel.
        key = (share, room, tuple(self._quick_shown), columns)
        if key == self._wrapped_for:
            return
        self._wrapped_for = key
        for name in self._quick_shown:
            self._wrap_label(self._quick_buttons[name], share)
        for title, (_section, _toggle, buttons) in self._groups.items():
            grid = self._grids.get(title)
            spacing = grid.horizontalSpacing() if grid is not None else 0
            cell = (room - spacing) // 2 if self.columns_of(title) == 2 else room
            for button in buttons:
                self._wrap_label(button, cell)

    def _natural_width(self, button: QToolButton) -> int:
        """Wie breit der Knopf mit seinem ungebrochenen Titel sein will."""
        title = str(button.property("operationTitle") or button.text())
        shown = button.text()
        if shown == title:
            return button.sizeHint().width()
        button.setText(title)
        width = button.sizeHint().width()
        button.setText(shown)
        return width

    def _arrange_groups(self) -> None:
        """Die Zeilen jeder Gruppe zu zweit, wo jeder Titel in die halbe Breite passt.

        Robert, 05.10.2026: die rechte Karte breiter machen „und es dann auch
        sinnvoll nutzen“. In einer Spalte stand ein Titel von 170 Punkten in
        einer Zeile von 500; zu zweit zeigt dieselbe Höhe doppelt so viele
        Handlungen. Entschieden wird je Gruppe und an der echten Breite: Passt
        ein Titel nicht ungebrochen in seine Hälfte, bleibt die Gruppe einspaltig
        — ein Umbruch in einer flachen Zeile wäre abgeschnitten. Gelegt wird
        zeilenweise, in der Reihenfolge der Liste.
        """
        room = self.scroller.viewport().width()
        for title, (_section, _toggle, buttons) in self._groups.items():
            grid = self._grids.get(title)
            if grid is None:
                continue
            shown = [button for button in buttons if not button.isHidden()]
            half = (room - grid.horizontalSpacing()) // 2
            two = len(shown) > 1 and all(self._natural_width(button) <= half for button in shown)
            columns = 2 if two else 1
            key = (columns, tuple(id(button) for button in shown))
            if self._arranged.get(title) == key:
                continue
            self._arranged[title] = key
            for button in buttons:
                grid.removeWidget(button)
            for index, button in enumerate(shown):
                grid.addWidget(button, index // columns, index % columns)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1 if columns == 2 else 0)

    def columns_of(self, title: str) -> int:
        """Wie viele Spalten die Gruppe ``title`` gerade hat — für Prüfungen."""
        arranged = self._arranged.get(title)
        return arranged[0] if arranged is not None else 1

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Hauptaktionen und Liste passen sich der tatsächlichen Spaltenbreite an."""
        super().resizeEvent(event)
        self._lay_out_quick(self._quick_shown)
        self._arrange_groups()
        self._wrap_labels()

    def set_context(
        self,
        selected: int,
        availability: Callable[[str], tuple[bool, str]],
        *,
        feature_kind: str = "",
        label: str = "",
        part_selected: bool = False,
        left_out: frozenset[str] = frozenset(),
        features: int = 0,
        rebuild: bool = False,
        pairing: bool = False,
    ) -> None:
        """Auswahl, Lage und Freigaben nachführen, ohne die Liste neu zu bauen.

        ``rebuild`` sagt, ob *Modell nachbauen* am gewählten Körper geht
        (``MainWindow._rebuild_allowed``); die Hauptaktion steht an genau einem
        Körper ohne gewähltes Merkmal.

        ``pairing`` sagt, ob sich ein zweiter Körper dazuwählen ließe
        (``MainWindow._pairing_possible``): Dann nennt an genau einem gewählten
        Körper eine Zeile den Weg zu den Booleschen (RM-734).

        ``features`` ist die Zahl markierter Merkmale am gewählten Körper, wenn
        kein einzelnes gewählt ist (:func:`quick_names`).

        ``feature_kind`` ist die Art des gewählten Merkmals — ``face``,
        ``hole`` und so fort — und leer, solange nur Körper gewählt sind. Sie
        entscheidet zusammen mit ``selected``, welche Hauptaktionen oben
        stehen (:func:`quick_names`) und **welche Handlungen überhaupt
        dastehen** (:meth:`_fits_the_level`). ``left_out`` nennt dazu, was am
        gewählten Merkmal nicht angeboten wird (``perceive.actions.not_offered_at``,
        R3): Es steht dann weder oben noch in der Liste.

        **``feature_chosen`` ist mit dem Knopf *Merkmale* weggefallen**
        (07.09.2026). Es beantwortete dieselbe Frage wie ``feature_kind`` — ob
        ein Merkmal gewählt ist —, und zwei Antworten auf eine Frage laufen
        beim nächsten Nachbessern auseinander.

        ``label`` ist der Name der Auswahl, wie ihn das Fenster kennt —
        ``Halter`` oder ``Halter · Oberseite`` (Konzept B). Er kommt von dort
        und wird hier nicht gebaut: Der Name eines Körpers und die
        Beschriftung eines Merkmals stehen in der Szene, nicht im Panel, und
        eine zweite Rechnung dafür wäre eine zweite Wahrheit. Fehlt er, bleibt
        es bei der Menge.
        """
        # Die Bausteinfelder darüber bedienen den erzeugenden Schritt. Seine
        # Einzelmerkmale sind hier kein Ziel für allgemeine Flächenoperationen.
        # **Was den Baustein ergänzt, bleibt** (RM-536, Entscheidung Robert
        # 07.10.2026): An einem gedruckten Innengewinde steht *Stift für
        # Bohrung* — das Gegenstück, nicht eine Änderung des Gewindes.
        only = (
            frozenset(
                name
                for name in OFFERED_AT_A_PART
                if name in self._buttons
                and name not in left_out
                and feature_kind in OFFERED_AT_A_PART[name]
                and feature_kind in self._at_which_kind.get(name, frozenset())
            )
            if part_selected and feature_kind
            else frozenset()
        )
        # **Die Karte steht immer, mit dem Suchfeld** (RM-735): An einem
        # Bausteinmerkmal ohne eigene Handlung war sie bis dahin ganz verborgen;
        # jetzt steht dort das Feld und der Satz, wo die Handlungen stehen.
        self.setVisible(True)
        self._availability = availability
        self._rows = None
        self._say_how_to_pair(
            pairing and selected == 1 and not feature_kind and features <= 1 and not part_selected
        )
        self._only = only if part_selected else None
        self._nothing_chosen = selected <= 0
        if self._nothing_chosen:
            # **Ohne Auswahl bleibt der Weg zu den Bausteinen** (Befund
            # Robert, 18.09.2026: „bei keiner Auswahl sollte das merkmalpanel
            # auch da sein um Bausteine setzen zu können"). Die Karte
            # verschwand ganz, und damit war der einzige sichtbare Zugang zum
            # Katalog weg — übrig blieben Strg+K und zwei Menüwege, die
            # niemand sucht, der gerade auf eine leere Fläche klickt. Ein Teil
            # der Bausteine steht frei (``standalone``; wie viele, sagt das
            # Register) und braucht gar keinen Körper; der Katalog lässt sie
            # durch, nimmt bei genau einem Körper diesen und bietet in der
            # leeren Szene den Weg zu einem ersten (RM-356). Dazu kommen die
            # Handlungen für alle Körper (:attr:`_for_all_bodies`).
            self._without_a_selection(availability)
            return
        # **Bausteine setzt man auf eine Fläche, nicht in ein Loch** (Robert,
        # 10.09.2026: „ganz unten wenn wir runterscrollen noch bauteile, das
        # brauchen wir bei gewählten merkmalen garnicht, nur flächen/Körper").
        # Ein Baustein braucht Material, auf dem er sitzt; an einer Bohrung,
        # einer Verrundung oder einem Zapfen führt der Knopf in einen Katalog,
        # aus dem nichts an diese Stelle passt — und er stand dabei unter einer
        # Liste, für die man scrollen muss.
        # **An einer Bohrung die passenden** (Robert, 05.10.2026): dieselbe
        # Stelle, ein Knopf, der Katalog auf das gefiltert, was dort ansetzt.
        self._catalog_kind = feature_kind if feature_kind in MATCHING_PARTS_AT else ""
        self.catalog_button.setText(
            tr("Passende Bausteine …") if self._catalog_kind else tr("Bausteinkatalog …")
        )
        self.catalog_button.setVisible(
            self._only is None and (feature_kind in ("", "face") or bool(self._catalog_kind))
        )
        if not feature_kind:
            left_out = frozenset()
        if self._feature_kind != feature_kind or self._left_out != left_out:
            self._feature_kind = feature_kind
            self._left_out = left_out
            self._filter()
        # **Was gewählt ist, nicht wie viel.** „1 Objekt gewählt" stand über
        # Merkmalshandlungen und nannte dabei die Körperzahl, während die
        # Knöpfe darunter dem Merkmal galten (Befund Robert, 07.09.2026). Die
        # Menge bleibt die Antwort, wo es keinen einen Namen gibt: bei zwei
        # Körpern.
        self.summary.setText(
            label
            if label and selected == 1
            else tr("{count} Objekte gewählt").replace("{count}", str(selected))
            if selected != 1
            else tr("1 Objekt gewählt")
        )
        # **Ein Name der Auswahl** (RM-510): An einem Merkmal nennt es das
        # Merkmalfenster darüber schon, mit Maß; hier stand derselbe Name ein
        # zweites Mal, nur mit dem Körper davor.
        self.summary.setVisible(not feature_kind)
        self._take_availability(availability)
        quick = [
            name
            for name in quick_names(selected, feature_kind, left_out=left_out, features=features)
            if self._buttons[name].isEnabled() and (self._only is None or name in self._only)
        ]
        if selected == 1 and not feature_kind and rebuild:
            # Wie die Registerknöpfe der Zeile: Steht er da, geht er auch.
            quick.append(REBUILD)
        self._lay_out_quick(tuple(quick))
        self._filter()

    def _say_how_to_pair(self, shown: bool) -> None:
        """Die Zeile zu den Booleschen bei einem gewählten Körper (RM-734).

        Reiner Text, kein grauer Knopf (Entscheidung Robert, 07.09.2026): Ein
        Klick müsste raten, welcher zweite Körper gemeint ist. Die Titel kommen
        aus dem Register (:data:`QUICK_BODIES`), die Taste je Plattform.
        """
        if shown:
            first, second, third = (str(REGISTRY.get(name).title) for name in QUICK_BODIES)
            self.pairing_hint.setText(
                tr(
                    "Für „{first}“, „{second}“ und „{third}“ ein zweites Objekt mit Umschalt"
                    " oder {key} und Klick hinzuwählen.",
                    first=first,
                    second=second,
                    third=third,
                    key=adding_key(),
                )
            )
        self.pairing_hint.setVisible(shown)

    def _filter(self, query: str | None = None) -> None:
        """Nur die Darstellung filtern; Registereinträge und Knöpfe bleiben bestehen.

        **Suchtext und Auswahlstufe entscheiden zusammen**, und deshalb an
        einer Stelle: Zwei Stellen, die dieselbe Sichtbarkeit setzen, machen
        sie abwechselnd — die eine blendet ein, was die andere gerade
        ausgeblendet hat. Ohne Argument gilt der zuletzt eingegebene Suchtext;
        so kann ein Stufenwechsel dieselbe Rechnung anstoßen wie eine
        Eingabe.

        **Bei Suchtext ruht die Karte:** Sie ist verdeckt, und ihre Gruppen
        nachzurechnen kostete jeden Tastendruck. Das Leeren des Felds läuft
        hierher und rechnet sie für die Auswahl von dann.
        """
        if query is not None:
            self._query = query
        wanted = self._query.strip()
        if wanted:
            self._show_hits(wanted)
            self._wrap_labels()
            return
        found = 0
        for title, (section, toggle, buttons) in self._groups.items():
            shown = 0
            for button in buttons:
                name = str(button.property("operationName"))
                visible = (
                    self._fits_the_level(name)
                    and button.isEnabled()
                    and name not in self._quick_shown
                )
                button.setVisible(visible)
                shown += visible
            section.setVisible(shown > 0)
            if title not in self._folded_by_hand:
                # Die Grenze (:data:`OPEN_UP_TO`): Was ein Menü nicht mehr
                # zeigte, beginnt hier zugeklappt — an einem Körper „Ändern"
                # mit 24, an einer Fläche dieselbe Gruppe mit zweien offen.
                # Gerechnet wird an der Stufe, nicht am Bestand.
                toggle.setChecked(shown <= OPEN_UP_TO)
            found += shown
        self._say_there_is_nothing(found)
        # Welche Knöpfe dastehen, hat sich gerade geändert — und ob ihre
        # Beschriftung in die Spalte passt, ist eine Frage je Knopf.
        self._arrange_groups()
        self._wrap_labels()

    def _show_hits(self, wanted: str) -> None:
        """Bei Suchtext tritt die Karte zurück, und die Treffer stehen da (RM-735).

        **Die Rangfolge der Suche** (:func:`~app.core.registry.search.ranked`):
        Güte zuerst, denn das Wort ist die Absicht; bei gleicher Güte vorn, was
        an dieser Auswahl geht (:meth:`_search_rows`). **Was nicht geht, steht
        mit seinem Grund da** und ist nicht wählbar — eine Antwort auf eine
        Frage, kein grauer Knopf in der ruhenden Karte. Die Hauptaktionen oben
        bleiben stehen, damit das Feld nicht unter dem Cursor springt; ihre
        Treffer stehen trotzdem in der Liste, denn Return und die Pfeiltasten
        arbeiten auf ihr.
        """
        hits, loosened = ranked(self._search_rows(), wanted)
        self._hits = hits
        self.scroller.setVisible(False)
        self.hits.clear()
        if not hits:
            self.hits.setVisible(False)
            self._nothing.setText(tr("Kein Treffer — versuchen Sie ein anderes Wort."))
            self._nothing.setVisible(True)
            self._manual.setVisible(True)
            return
        self._nothing.setVisible(False)
        self._manual.setVisible(False)
        if loosened:
            # Nicht wählbar und ohne Namen: Die Vorauswahl übergeht sie, und
            # Return löst über sie nichts aus.
            heading = QListWidgetItem(
                tr("Keine Funktion passt auf alle Wörter — das Folgende passt auf einzelne.")
            )
            heading.setFlags(Qt.ItemFlag.NoItemFlags)
            heading.setToolTip(heading.text())
            self.hits.addItem(heading)
        for entry in hits:
            self.hits.addItem(self._hit_item(entry))
        self.hits.setCurrentRow(first_choice(hits, wanted) + int(loosened))
        self.hits.setVisible(True)
        self.hits.updateGeometry()

    @staticmethod
    def _hit_item(entry: SearchEntry) -> QListWidgetItem:
        """Eine Zeile der Trefferliste: Titel, Kürzel, darunter Satz oder Grund."""
        title = str(entry.title)
        key = native_key(entry.shortcut or "")
        label = f"{title}\t{key}" if key else title
        detail = first_sentence(str(entry.doc)).strip()
        # Fensterbefehle tragen ihren Titel als Beschreibung; dieselbe Zeile
        # zweimal wäre keine Auskunft.
        if detail == title.strip():
            detail = ""
        if not entry.available and entry.reason:
            # **Gesperrt sagt die zweite Zeile nur den Grund** (Regel 18): Das
            # Grau allein wäre die halbe Antwort.
            detail = str(entry.reason).strip()
        if detail:
            label = f"{label}\n{detail}"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, entry.name)
        lines: list[str] = []
        where = str(entry.where).strip()
        for text in (
            title,
            str(entry.reason) if not entry.available else "",
            str(entry.doc),
            # Der Ort, wie das Kürzel: nebenbei gelernt (RM-506).
            tr("Ort: {place}", place=where) if where else "",
        ):
            text = text.strip()
            if text and text not in lines:
                lines.append(text)
        item.setToolTip("\n".join(lines))
        # Ein Vorleser liest den Titel mit Taste, nicht den Tabulator der Anzeige.
        item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{title}, {key}" if key else title)
        item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, "\n".join(lines[1:]))
        if not entry.available:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        return item

    def _search_rows(self) -> list[SearchEntry]:
        """Was die Suche durchsucht — in der Reihenfolge, die bei gleicher Güte gilt.

        **Jede Operation jeder Stufe** (auch die Bausteine des Katalogs, die
        Erzeuger und die Handlungen für alle Körper) **und jeder Befehl des
        Fensters** (:meth:`set_search_sources`): dieselbe Menge, die die
        Befehlspalette hatte. Bis RM-735 fand das Feld nur 81 der 273, und
        ohne Auswahl war es verborgen.

        **Vorn steht, was die ruhende Karte an dieser Auswahl zeigt**, dann was
        sonst geht, zuletzt das Gesperrte, je nach Titel. Gebaut beim ersten
        Zeichen und verworfen, sobald sich Auswahl oder Freigabe ändern
        (:meth:`set_context`) — ein Tastendruck rechnet nur die Rangfolge.
        """
        if self._rows is None:
            operations = [
                replace(
                    entry,
                    available=usable,
                    reason=reason,
                    shortcut=self._key_of(entry.name, entry.shortcut),
                )
                for entry in search_entries()
                if entry.name in self._searched and entry.name not in self._as_commands
                for usable, reason in (self._availability(entry.name),)
            ]
            rows = sorted(
                [*operations, *self._commands()], key=lambda entry: sort_key(str(entry.title))
            )
            standing = {entry.name for entry in rows if self._stands_here(entry.name)}
            self._rows = sorted(
                rows, key=lambda entry: (not entry.available, entry.name not in standing)
            )
        return self._rows

    def _stands_here(self, name: str) -> bool:
        """Ob die ruhende Karte diese Handlung an der aktuellen Auswahl zeigt."""
        if name in self._quick_shown:
            return True
        button = self._buttons.get(name)
        return button is not None and button.isEnabled() and self._fits_the_level(name)

    def button_for(self, name: str) -> QToolButton | None:
        """Der Knopf, an dem die Handlung gerade steht — oben oder ihre Zeile in der Liste.

        Eine Hauptaktion hat zwei (:attr:`_list_twins`), und sichtbar ist
        höchstens einer. Wer auf die Handlung zeigt — Anleitung, Tour —, fragt
        hier und nicht nach dem oberen: An einer Fläche steht *Aushöhlen* nur
        in der Liste. Steht sie gerade nirgends (Suche, Stufe), ist es der
        Knopf, der an dieser Stufe für sie gilt.
        """
        twin = self._list_twins.get(name)
        if twin is not None and name not in self._quick_shown:
            return twin
        return self._buttons.get(name)

    def _take_availability(self, availability: Callable[[str], tuple[bool, str]]) -> None:
        """Freigabe und Hinweis jedes Knopfes nachführen — nur, wo sie sich ändern."""
        for name, button in self._buttons.items():
            action = self._window_actions.get(name)
            if action is not None:
                # Die Aktion sagt beides selbst (``MainWindow._say_why``).
                window_state = (action.isEnabled(), action.toolTip())
                if self._states.get(name) != window_state:
                    self._states[name] = window_state
                    button.setEnabled(window_state[0])
                    button.setToolTip(window_state[1])
                    button.setAccessibleDescription(window_state[1])
                continue
            enabled, reason = availability(name)
            state = (enabled, reason)
            if self._states.get(name) == state:
                continue
            self._states[name] = state
            for shown in (button, self._list_twins.get(name)):
                if shown is None:
                    continue
                shown.setEnabled(enabled)
                spec_tip = shown.property("operationTip")
                if spec_tip is None:
                    spec_tip = shown.toolTip()
                    shown.setProperty("operationTip", spec_tip)
                tip = str(spec_tip) if enabled or not reason else reason
                shown.setToolTip(tip)
                shown.setAccessibleDescription(tip)

    def _without_a_selection(self, availability: Callable[[str], tuple[bool, str]]) -> None:
        """Ohne Auswahl: die Handlungen für alle Körper, die Erzeuger, die Suche
        und der Weg zu den Bausteinen.

        Keine Hauptaktionen — sie gelten einer Auswahl, und die gibt es nicht.
        Was dasteht, sind die Handlungen, die ohnehin jeden Körper nehmen
        (:attr:`_for_all_bodies`), und was einen neuen anlegt
        (:attr:`_creators`), freigegeben wie an jeder anderen Stelle, dazu der
        Knopf zum Katalog und das Suchfeld über alles (RM-735).
        """
        # **Die Hauptaktionen gehen über ihren eigenen Weg weg, nicht über
        # ``setVisible``.** `_lay_out_quick` kürzt ab, wenn dieselbe Liste
        # schon steht — wer die Knöpfe hier von Hand versteckte, ließ
        # ``_quick_shown`` gefüllt zurück, und beim nächsten gewählten Körper
        # kehrte die Rechnung sofort zurück: Die Zeile blieb leer. Dieselbe
        # Falle, vor der der Docstring von :meth:`_filter` warnt — zwei
        # Stellen, die dieselbe Sichtbarkeit setzen, machen sie abwechselnd.
        self._lay_out_quick(())
        self.summary.setText(tr("Nichts gewählt"))
        self.summary.setVisible(True)
        self._catalog_kind = ""
        self.catalog_button.setText(tr("Bausteinkatalog …"))
        self.catalog_button.setVisible(True)
        self._take_availability(availability)
        self._filter()

    def _catalog_clicked(self, _checked: bool = False) -> None:
        """Der Katalog — gefiltert, wo der Knopf *Passende Bausteine …* heißt."""
        if self._catalog_kind:
            self.matchingPartsRequested.emit(self._catalog_kind)
        else:
            self.catalogRequested.emit()

    def _say_there_is_nothing(self, found: int) -> None:
        """Die ruhende Karte ohne Suchtext — und ein Satz, wenn ihre Liste leer ist.

        **Das Suchfeld bleibt immer stehen** (Entscheidung Robert,
        11.10.2026): Es sucht über alles, auch dort, wo die Karte selbst nichts
        anbietet. Bis RM-735 verschwand es mit der Liste, denn es versprach nur
        die Handlungen dieser Auswahl (Befund Robert, 18.09.2026).

        Leer ist die Liste an einer Auswahl, deren Handlungen oben im
        Merkmalfenster stehen — am Langloch, an der Kante —, und ohne Auswahl
        nur, wenn alles gesperrt ist: Dann nennt der Satz den Grund, statt
        Handlungen zuzusagen, die gerade nicht gehen.
        """
        self.hits.clear()
        self.hits.setVisible(False)
        self._hits = []
        self._manual.setVisible(False)
        self.scroller.setVisible(found > 0)
        if found > 0:
            self._nothing.setVisible(False)
            return
        if self._nothing_chosen:
            reasons = (
                self._states.get(name, (True, ""))[1]
                for name in sorted(self._creators | self._for_all_bodies)
            )
            text = next((reason for reason in reasons if reason), "")
        else:
            text = tr("Was sich hier tun lässt, steht oben bei den Maßen.")
        self._nothing.setText(text)
        self._nothing.setVisible(bool(text))

    def _folded_by_a_click(self, title: str) -> None:
        """Eine von Hand bewegte Klappe bleibt, wie sie ist (:data:`OPEN_UP_TO`)."""
        self._folded_by_hand.add(title)

    def _fits_the_level(self, name: str) -> bool:
        """Ob diese Handlung zur Stufe der aktuellen Auswahl gehört (Konzept C).

        Die Stufe ist eine Grenze neben der Freigabe: Eine Fläche wird
        nicht auf dem Bett angeordnet. Fehlende Vorbedingungen blendet
        zusätzlich ``_filter`` aus, bis die Auswahl dazu passt.

        **Die Stufe ist die Art, nicht nur die Ebene** (09.09.2026). Bis dahin
        genügte „Merkmalshandlung ja oder nein", und damit stand an einer
        Bohrung auch, was nur an einer Fläche etwas tut. Eine Bohrung wird
        nicht beschriftet und trägt kein eigenes Filament — der Baum weiß das
        längst und gibt ihr keine Filamentspalte (``paint_slot`` gilt für
        ``face`` und für nichts sonst). Beide Orte lesen jetzt dieselbe Auskunft
        aus dem Register.
        """
        if name in PICKER_HANDLES:
            return False
        # Die Handlungen für alle Körper und die Erzeuger gehören zur Stufe ohne
        # Auswahl und zu keiner anderen (:attr:`_for_all_bodies`,
        # :attr:`_creators`); ohne Auswahl steht nichts sonst da.
        if name in self._for_all_bodies or name in self._creators:
            return self._nothing_chosen
        if self._nothing_chosen:
            return False
        if self._feature_kind:
            if name in _shown_as_fields():
                return False
            if name in self._left_out:
                return False
            if self._only is not None and name not in self._only:
                return False
            return self._feature_kind in self._at_which_kind.get(name, frozenset())
        # Eine Handlung, die auch ohne Merkmal gilt (``also_on_body``), steht
        # an beiden Stufen — die Formschräge am ganzen Körper und an Flächen.
        return name not in self._at_a_feature or name in self._on_body

    def chosen_level(self) -> str:
        """Die Stufe, auf die das Panel gerade eingestellt ist.

        Für Tests und für das Fenster: ``""`` heißt Körperstufe, ein
        Merkmalsname die Art des gewählten Merkmals, ``"scene"`` nichts gewählt
        — dann stehen die Handlungen für alle Körper da.
        """
        if self._nothing_chosen:
            return "scene"
        return self._feature_kind or ""
