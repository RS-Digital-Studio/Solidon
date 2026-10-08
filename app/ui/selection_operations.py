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

from collections.abc import Callable, Iterable
from typing import Final, override

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QAction, QResizeEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
    PaletteEntry,
    catalogue_operations,
    caveat_line,
    folded_categories,
    group_title,
    shown_of_twins,
)
from app.core.registry.surfaces import SCENE_ACTIONS_IN_THE_CARD, menu_rank
from app.i18n import sort_key, tr
from app.ui.command_palette import fold, found_in_rounds
from app.ui.icons import icon, icon_name_for
from app.ui.leash import stop_watching_the_dying, weak_slot
from app.ui.overlay import ContentScroller
from app.ui.panels import collapsible
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
aus :data:`QUICK_FEATURE` sind darunter. Der Rest steht in der Suchliste,
im Menü und in der Befehlspalette. *Merkmal vervielfachen* (P6.7) steht an
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
    Suchliste darunter, im Menü und in der Befehlspalette. Deshalb ist eine
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
    Eingang gehören ebenfalls nicht an eine Auswahl; sie bleiben im Menü und
    in der Befehlspalette.

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
    oder ein Merkmal meint; er bleibt im Menü und in der Befehlspalette. Am
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
    paletteRequested = Signal(str)
    """Die Befehlspalette mit diesem Suchtext — „In allen Funktionen suchen“."""
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
            spec.name: spec for spec in (*body_operations(specs), *feature_operations(specs))
        }
        operations = tuple(by_name.values())
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
        self._entries = {
            spec.name: PaletteEntry(
                name=spec.name, title=spec.title, category=spec.category, doc=spec.doc
            )
            for spec in operations
        }
        """Je Handlung die Zeile, gegen die gesucht wird — wie in der Palette
        (:func:`~app.ui.command_palette.found_in_rounds`): Titel, Name,
        Beschreibung und Kundenwörter, gefaltet."""
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

        self.search = QLineEdit(self)
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(TARGET_SIZE)
        self.search.setPlaceholderText(tr("Weitere Operationen durchsuchen"))
        self.search.setAccessibleName(tr("Operationen durchsuchen"))
        self.search.textChanged.connect(self._filter)

        # **Steht nichts in der Liste, wird nicht zum Durchsuchen eingeladen**
        # (Befund Robert, 18.09.2026: „weitere Optionen durchsuchen steht da,
        # wenn es keine Operationen für die Auswahl gibt"). Das Feld stand
        # fest im Layout und war immer sichtbar; an einer Auswahl mit leerer
        # Karte — einem Langloch, einer Kante — versprach es etwas zu finden,
        # wo es nichts gibt. Der Satz nennt stattdessen, wo die Handlungen
        # dieser Auswahl stehen.
        self._nothing = QLabel(self)
        self._nothing.setWordWrap(True)
        set_level(self._nothing, "caption")
        self._nothing.setVisible(False)
        # **Ohne Treffer weiter in allen Funktionen** (RM-506): Die Suche hier
        # kennt nur, was zur Auswahl passt; wer „gewinde“ an einem Körper
        # sucht, findet nichts, obwohl es das gibt. Der Knopf öffnet die
        # Befehlspalette mit demselben Wort.
        self._everywhere = QPushButton(tr("In allen Funktionen suchen"), self)
        self._everywhere.setVisible(False)
        self._everywhere.clicked.connect(self._search_everywhere)

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
        self.catalog_button = make_large_target(make_primary(QPushButton(tr("Bausteine"), self)))
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
        layout.addWidget(self.search)
        layout.addWidget(self._nothing)
        layout.addWidget(self._everywhere)
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
        if (watched is self._print_widget and event.type() in _SHOWN_OR_HIDDEN) or (
            watched is self._print_box and event.type() in _CAME_OR_WENT
        ):
            self._settle_print_section()
        return super().eventFilter(watched, event)

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
        die Palette und Kürzel auslösen.

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
    ) -> None:
        """Auswahl, Lage und Freigaben nachführen, ohne die Liste neu zu bauen.

        ``rebuild`` sagt, ob *Modell nachbauen* am gewählten Körper geht
        (``MainWindow._rebuild_allowed``); die Hauptaktion steht an genau einem
        Körper ohne gewähltes Merkmal.

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
        self.setVisible(not part_selected or bool(only))
        if part_selected and not only:
            return
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
            tr("Passende Bausteine …") if self._catalog_kind else tr("Bausteine")
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

    def _search_everywhere(self) -> None:
        """*In allen Funktionen suchen*: die Befehlspalette mit demselben Wort.

        Eine Methode statt eines Lambdas: Am eigenen Kind hielte es die Karte
        stark (``wartezeit.md``, „Ein Rückruf an ein eigenes Kind hält schwach“).
        """
        self.paletteRequested.emit(self._query.strip())

    def _filter(self, query: str | None = None) -> None:
        """Nur die Darstellung filtern; Registereinträge und Knöpfe bleiben bestehen.

        **Suchtext und Auswahlstufe entscheiden zusammen**, und deshalb an
        einer Stelle: Zwei Stellen, die dieselbe Sichtbarkeit setzen, machen
        sie abwechselnd — die eine blendet ein, was die andere gerade
        ausgeblendet hat. Ohne Argument gilt der zuletzt eingegebene Suchtext;
        so kann ein Stufenwechsel dieselbe Rechnung anstoßen wie eine
        Eingabe.
        """
        if query is not None:
            self._query = query
        # Ohne Auswahl ist das Suchfeld verborgen; ein Suchtext von der
        # letzten Auswahl filterte sonst unsichtbar die Handlungen weg.
        wanted = "" if self._nothing_chosen else self._query.strip()
        hits = self._search_hits(wanted)
        # Ein getroffener Hauptknopf oben ist ein Treffer — sonst sagte die
        # Liste „Kein Treffer“ unter dem Knopf, der gesucht war.
        found = sum(1 for name in self._quick_shown if name in hits) if wanted else 0
        for title, (section, toggle, buttons) in self._groups.items():
            shown = 0
            for button in buttons:
                name = str(button.property("operationName"))
                visible = (
                    (not wanted or name in hits)
                    and self._fits_the_level(name)
                    and button.isEnabled()
                    and name not in self._quick_shown
                )
                button.setVisible(visible)
                shown += visible
            section.setVisible(shown > 0)
            if wanted and shown and not toggle.isChecked():
                # Ein Treffer öffnet seine Gruppe: Wer sucht, will sehen, was
                # er gefunden hat — nicht erst aufklappen.
                toggle.setChecked(True)
            elif not wanted and title not in self._folded_by_hand:
                # Ohne Suchtext gilt die Grenze (:data:`OPEN_UP_TO`): Was ein
                # Menü nicht mehr zeigte, beginnt hier zugeklappt — an einem
                # Körper „Ändern" mit 24, an einer Fläche dieselbe Gruppe mit
                # zweien offen. Gerechnet wird an der Stufe, nicht am Bestand.
                toggle.setChecked(shown <= OPEN_UP_TO)
            found += shown
        self._say_there_is_nothing(found, bool(wanted), self._needs_another_choice(hits))
        # Welche Knöpfe dastehen, hat sich gerade geändert — und ob ihre
        # Beschriftung in die Spalte passt, ist eine Frage je Knopf.
        self._arrange_groups()
        self._wrap_labels()

    def _search_hits(self, wanted: str) -> frozenset[str]:
        """Welche Handlungen der Suchtext trifft — wie in der Befehlspalette.

        Titel, Name, Beschreibung und Kundenwörter, gefaltet, in den Runden
        von :func:`~app.ui.command_palette.found_in_rounds`: „verschmelzen“
        findet *Vereinigen*, „aushoehlen“ das *Aushöhlen*, „löschen“ das
        *Objekt entfernen*. Bis zum 06.10.2026 verglich die Karte nur Titel
        und Gruppe und fand keines davon (Fragebogen zu 0.5.3). **Eine
        getroffene Gruppe** nimmt ihre Handlungen mit, wie bisher: „formgebung“
        zeigt die ganze Gruppe.
        """
        if not wanted:
            return frozenset()
        found, _loosened = found_in_rounds(tuple(self._entries.values()), wanted)
        parts = fold(wanted).split()
        in_a_group = {
            str(button.property("operationName"))
            for title, (_section, _toggle, buttons) in self._groups.items()
            if all(part in fold(title) for part in parts)
            for button in buttons
        }
        return frozenset(str(entry.name) for entry in found) | in_a_group

    def _needs_another_choice(self, hits: frozenset[str]) -> str:
        """Der Satz zu einem Treffer, der an dieser Auswahl nicht geht — oder nichts.

        Wer an einem Körper „verschmelzen“ sucht, meint *Vereinigen*, und das
        braucht zwei. Ein „Kein Treffer“ wäre falsch und eine Sackgasse; der
        Grund aus der Freigabe (:meth:`_take_availability`) sagt, wie das
        zweite Objekt dazukommt. Genannt wird der erste Treffer in der
        Reihenfolge des Titels, der einen Grund trägt.
        """
        locked = [
            name
            for name in hits
            if name in self._buttons
            and self._states.get(name, (True, ""))[1]
            and not self._states.get(name, (True, ""))[0]
        ]
        if not locked:
            return ""

        # Der Titel steht am Knopf: Eine Fensterhandlung (*Automatisch teilen*,
        # :meth:`add_window_action`) hat keinen Registereintrag in ``_entries``.
        # Ihr Knopf trägt die Menübeschriftung mit Auslassung („…“, öffnet
        # einen Dialog); im Satz ist sie ein Name, und vor dem Doppelpunkt
        # stünde sie falsch.
        def title(entry: str) -> str:
            return str(self._buttons[entry].property("operationTitle")).removesuffix(" …")

        name = min(locked, key=lambda entry: sort_key(title(entry)))
        return tr("{name}: {value}", name=title(name), value=self._states[name][1])

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
        """Ohne Auswahl: die Handlungen für alle Körper und der Weg zu den Bausteinen.

        Keine Hauptaktionen und keine Suche — beides gilt einer Auswahl, und
        die gibt es nicht. Was dasteht, sind die Handlungen, die ohnehin jeden
        Körper nehmen (:attr:`_for_all_bodies`), freigegeben wie an jeder
        anderen Stelle, und der Knopf zum Katalog. Ist die Szene leer, bleiben
        der Knopf und ein Satz, der sagt, woran es liegt
        (:meth:`_say_there_is_nothing`).
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
        self.catalog_button.setText(tr("Bausteine"))
        self.catalog_button.setVisible(True)
        self._take_availability(availability)
        self._filter()

    def _catalog_clicked(self, _checked: bool = False) -> None:
        """Der Katalog — gefiltert, wo der Knopf *Passende Bausteine …* heißt."""
        if self._catalog_kind:
            self.matchingPartsRequested.emit(self._catalog_kind)
        else:
            self.catalogRequested.emit()

    def _say_there_is_nothing(self, found: int, searching: bool, elsewhere: str = "") -> None:
        """Die leere Liste sagt, warum sie leer ist — und lädt nicht zum Suchen ein.

        Zwei verschiedene Leeren, und sie brauchen zwei Sätze: Wer **sucht**,
        hat nichts gefunden und soll es anders versuchen; wer **nicht** sucht,
        steht an einer Auswahl, deren Handlungen woanders stehen — am
        Langloch und an der Kante oben im Merkmalfenster, und das ist die
        richtige Antwort und kein Mangel.

        Das Suchfeld verschwindet im zweiten Fall mit: Ein Feld, das
        „Weitere Operationen durchsuchen" verspricht, während die Liste
        darunter leer ist und leer bleibt, stellt eine Frage, auf die es
        keine Antwort gibt (Befund Robert, 18.09.2026).

        ``elsewhere`` ist der Satz zu einem Treffer, der eine andere Auswahl
        braucht (:meth:`_needs_another_choice`) — er tritt an die Stelle von
        „Kein Treffer“, denn es gibt einen, nur nicht hier.
        """
        if self._nothing_chosen:
            # Ohne Auswahl gibt es nichts zu durchsuchen: Was dasteht, sind
            # die wenigen Handlungen für alle Körper, und der Satz sagt das.
            if found > 0:
                self.search.setVisible(False)
                self.scroller.setVisible(True)
                self._nothing.setText(tr("Gilt für alle Körper."))
                self._nothing.setVisible(True)
            else:
                self._only_this_sentence(
                    tr("Wählen Sie einen Körper oder eine Fläche — Bausteine gehen auch so.")
                )
            return
        self._everywhere.setVisible(searching and found == 0 and not self._nothing_chosen)
        if found > 0:
            self.search.setVisible(True)
            self.scroller.setVisible(True)
            self._nothing.setVisible(False)
            return
        if searching:
            # Wer sucht, behält sein Feld: Dort ist es die Ursache der leeren
            # Liste und zugleich der Weg zurück.
            self.search.setVisible(True)
            self.scroller.setVisible(False)
            self._nothing.setText(elsewhere or tr("Kein Treffer — versuchen Sie ein anderes Wort."))
            self._nothing.setVisible(True)
            return
        self._only_this_sentence(tr("Was sich hier tun lässt, steht oben bei den Maßen."))

    def _only_this_sentence(self, text: str) -> None:
        """Statt Suchfeld und Liste steht ein Satz da — an **einer** Stelle.

        Zwei Leeren enden hier: keine Auswahl und eine Auswahl, deren
        Handlungen oben im Merkmalfenster stehen. Sie sagen Verschiedenes und
        verbergen dasselbe, und wer beides getrennt setzt, setzt es beim
        nächsten Nachbessern abwechselnd — dieselbe Falle, die
        :meth:`_empty_but_for_the_catalogue` schon bei den Hauptaktionen
        beschreibt.
        """
        self.search.setVisible(False)
        self.scroller.setVisible(False)
        self._nothing.setText(text)
        self._nothing.setVisible(True)

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
        # Die Handlungen für alle Körper gehören zur Stufe ohne Auswahl und zu
        # keiner anderen (:attr:`_for_all_bodies`); ohne Auswahl steht nichts
        # sonst da.
        if name in self._for_all_bodies:
            return self._nothing_chosen and name in SCENE_ACTIONS_IN_THE_CARD
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
