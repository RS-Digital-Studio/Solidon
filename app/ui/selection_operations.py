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

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
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

from app.core.registry import (
    REGISTRY,
    OperationSpec,
    catalogue_operations,
    caveat_line,
    group_title,
    shown_of_twins,
)
from app.i18n import tr
from app.ui.icons import icon, icon_name_for
from app.ui.leash import weak_slot
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
    "hole": ("resize_hole", "countersink_hole", "slot_hole", "plug_hole"),
    # **Am Langloch ist die Karte leer, und das ist die richtige Antwort.**
    # Alle sechs Handlungen des Langlochs stehen oben als Felder, und was dort
    # steht, bekommt hier keinen zweiten Knopf. Die Zeile hält die Stelle für
    # den Fall frei, dass *Zum Langloch ziehen* je aufhört, ein Feld zu sein —
    # der Rückfall :data:`QUICK_FEATURE` träfe an dieser Art nichts, denn
    # `quick_names` schneidet ihn gegen das Register.
    "slot": ("slot_hole",),
    "cone": ("countersink_hole",),
    "edge_loop": ("repair",),
}
"""Je Merkmalsart die Handlungen, die dort zuerst gesucht werden.

Nur wo die Art eine eigene Antwort hat. Stift und Kugel bieten die drei
generischen Merkmalshandlungen **mit** an — nicht genau sie: Am Register
gemessen (07.09.2026) trägt `pin` sieben Operationen und `sphere` vier, die
drei aus :data:`QUICK_FEATURE` sind darunter. Der Rest steht in der Suchliste,
im Menü und in der Befehlspalette.

**Der Kegel hat seit dem 09.09.2026 eine eigene Zeile**, und der Grund ist ein
Loch, das vorher niemandem auffiel: Er trägt sechs Operationen, fünf davon
stehen im Merkmalsfenster darüber als Felder (:func:`_shown_as_fields`), und
die sechste — *Senken* — war ein Knopf der Schnellzeile für ``hole``. Was oben
stehen **kann**, steht nicht auch in der Liste darunter; an einer Senkung stand
es aber auch nicht oben, weil der Rückfall :data:`QUICK_FEATURE` sie nicht
nennt. Damit war die einzige Handlung an einer Senkung an keiner der beiden
Stellen zu finden.
"""

QUICK_FEATURE = ("resize_feature", "move_feature", "remove_feature")
"""Für jede Merkmalsart ohne eigene Zeile in :data:`QUICK_FEATURES`."""


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
PICKER_HANDLES: Final = frozenset({"clear_filament"})


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
Karte zwei leere Gestalten, in denen Suche und Liste fehlen: ohne Auswahl
(Hauptaktionen weg, Katalogknopf und ein Satz) und an einer Auswahl, deren
Handlungen oben im Merkmalfenster stehen — ein Langloch, eine Kante. Dort
reserviert die Zahl mehr, als dasteht. Das ist Absicht und kein Rest: Eine
Untergrenze, die mit dem Inhalt schwankte, ließe die Karte bei jedem
Auswahlwechsel springen, und der Raum darunter kostet nichts — die Spalte
rollt, und was frei bleibt, zeigt das Modell.
"""


def quick_names(bodies: int, feature_kind: str = "") -> tuple[str, ...]:
    """Die Hauptaktionen für diese Auswahl, in ihrer Rangfolge.

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
        return tuple(name for name in wanted if name in offered and name not in fields)
    return QUICK_BODIES if bodies > 1 else QUICK_BODY


def all_quick_names() -> tuple[str, ...]:
    """Jeder Name, der in irgendeiner Lage vorn stehen kann — ohne Wiederholung.

    Der Aufbau braucht sie: Die Hauptaktionen bekommen ihre Knöpfe **einmal**
    und werden bei Auswahlwechseln nur noch ein- und ausgeblendet. In der
    Reihenfolge ihrer Tabellen, damit die Zeile oben von links nach rechts so
    steht, wie :func:`quick_names` sie nennt.
    """
    found: list[str] = []
    for group in (QUICK_BODIES, QUICK_BODY, *QUICK_FEATURES.values(), QUICK_FEATURE):
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
        and not spec.applies_to
    )


def feature_operations(specs: Iterable[OperationSpec]) -> tuple[OperationSpec, ...]:
    """Was an einem Merkmal gearbeitet wird — Bohren, Senken, Verschließen.

    Dieselbe Zuordnung, aus der das Kontextmenü am Merkmal seine Zeilen baut
    (``applies_to``, §18.5): eine dritte Oberfläche über einer Quelle, keine
    zweite Rechnung. Sie standen bis zum 07.09.2026 nicht im Panel, und damit
    bot eine gewählte Fläche dort nichts an.

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


class SelectionOperationsPanel(QWidget):
    """Alle Handlungen für die aktuelle Auswahl, dauerhaft aufgebaut."""

    operationRequested = Signal(object)
    catalogRequested = Signal()

    def __init__(self, specs: Iterable[OperationSpec], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("selectionOperations")
        self.setAccessibleName(tr("Operationen für die Auswahl"))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(PANEL_LEAST_HEIGHT)

        # **Einmal aufgezählt, nicht zweimal durchlaufen.** Die Signatur nimmt
        # ein ``Iterable``, und ein Generator wäre beim zweiten Filter leer.
        specs = tuple(specs)
        operations = body_operations(specs) + feature_operations(specs)
        by_name = {spec.name: spec for spec in operations}
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
        self._buttons: dict[str, QToolButton] = {}
        self._groups: dict[str, tuple[QWidget, QToolButton, tuple[QToolButton, ...]]] = {}
        """Je Gruppe ihr Abschnitt, sein Umschalter und ihre Knöpfe.

        Der Abschnitt ist das, was die Suche ein- und ausblendet; der
        Umschalter das, was sie beim Treffer öffnet — ein Treffer in einer
        zugeklappten Gruppe wäre sonst einer, den niemand sieht."""
        self._states: dict[str, tuple[bool, str]] = {}
        self._quick_buttons: dict[str, QToolButton] = {}
        self._quick_shown: list[str] = []
        self._quick_columns = 1
        self._query = ""
        """Der zuletzt eingegebene Suchtext — ein Stufenwechsel darf ihn nicht
        vergessen."""
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

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        # Zwischen den Gruppen Luft, innerhalb eng: Die Gruppe ist die
        # Einheit, die man überblickt, nicht der einzelne Knopf.
        content_layout.setSpacing(NORMAL)

        grouped: dict[str, list[OperationSpec]] = {}
        for spec in operations:
            # Was oben stehen kann, steht nicht auch darunter: zwei Knöpfe für
            # dieselbe Handlung sind eine Frage ohne Antwort.
            if spec.name in self._quick_buttons:
                continue
            grouped.setdefault(str(group_title(spec.category)), []).append(spec)
        for title in sorted(grouped, key=str.casefold):
            # **Jede Gruppe ein Abschnitt, der sich zuklappen lässt** — mit
            # der Kopfzeile und der Linie darunter, die auch die linke Spalte
            # trägt (:func:`collapsible`). Eine graue Zwischenüberschrift über
            # einer Liste gleicher Knöpfe machte aus fünfzig Handlungen eine
            # Wand (Robert, 11.09.2026: „sieht alles ziemlich monoton und
            # dadurch unübersichtlich aus").
            box = QWidget(content)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(0, TIGHT, 0, 0)
            box_layout.setSpacing(TIGHT)
            buttons: list[QToolButton] = []
            for spec in sorted(grouped[title], key=lambda entry: str(entry.title).casefold()):
                button = self._operation_button(spec, box)
                box_layout.addWidget(button)
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

        self.scroller = QScrollArea(self)
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
        self.catalog_button.setStatusTip(self.catalog_button.toolTip())
        self.catalog_button.setAccessibleDescription(self.catalog_button.toolTip())
        self.catalog_button.clicked.connect(self.catalogRequested)

        separate = QHBoxLayout()
        separate.setContentsMargins(0, 0, 0, 0)
        separate.setSpacing(TIGHT)
        separate.addWidget(self.catalog_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, NORMAL)
        layout.setSpacing(TIGHT)
        layout.addWidget(self.summary)
        layout.addLayout(quick)
        layout.addWidget(self.search)
        layout.addWidget(self._nothing)
        layout.addWidget(self.scroller, 1)
        layout.addLayout(separate)
        self.hide()

    def _operation_button(self, spec: OperationSpec, parent: QWidget | None = None) -> QToolButton:
        """Einen Registereintrag als direkte, tastaturfähige Handlung bauen."""
        button = QToolButton(parent or self)
        button.setText(str(spec.title))
        button.setIcon(icon(icon_name_for(spec), button))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setMinimumHeight(TARGET_SIZE)
        warning = caveat_line(spec)
        tip = f"{spec.doc}\n\n{warning}" if warning else str(spec.doc)
        button.setToolTip(tip)
        button.setStatusTip(str(spec.doc))
        button.setAccessibleDescription(tip)
        button.clicked.connect(weak_slot(self, SelectionOperationsPanel._request_operation, spec))
        button.setProperty("operationName", spec.name)
        # Der ungebrochene Titel bleibt am Knopf: :meth:`_wrap_label` schreibt
        # ``text()`` um, und ein zweiter Lauf darf nicht auf seinem eigenen
        # Ergebnis weiterrechnen. Die Suche liest ebenfalls von hier — mit
        # einem Umbruch mitten im Titel fände „bohrung verschließen" sich
        # selbst nicht mehr.
        button.setProperty("operationTitle", str(spec.title))
        self._buttons[spec.name] = button
        return button

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
        for index, name in enumerate(wanted):
            button = self._quick_buttons[name]
            if columns == 1:
                self._quick.addWidget(button, index, 0)
            elif index < 2:
                self._quick.addWidget(button, 0, index)
            else:
                self._quick.addWidget(button, max(index - 1, 0), 0, 1, 2)
            button.show()

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
        for name in self._quick_shown:
            self._wrap_label(self._quick_buttons[name], share)
        for _section, _toggle, buttons in self._groups.values():
            for button in buttons:
                self._wrap_label(button, self.scroller.viewport().width())

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Die Hauptaktionen passen sich der tatsächlichen Spaltenbreite an."""
        super().resizeEvent(event)
        self._lay_out_quick(self._quick_shown)
        self._wrap_labels()

    def set_context(
        self,
        selected: int,
        availability: Callable[[str], tuple[bool, str]],
        *,
        feature_kind: str = "",
        label: str = "",
        part_selected: bool = False,
    ) -> None:
        """Auswahl, Lage und Freigaben nachführen, ohne die Liste neu zu bauen.

        ``feature_kind`` ist die Art des gewählten Merkmals — ``face``,
        ``hole`` und so fort — und leer, solange nur Körper gewählt sind. Sie
        entscheidet zusammen mit ``selected``, welche Hauptaktionen oben
        stehen (:func:`quick_names`) und **welche Handlungen überhaupt
        dastehen** (:meth:`_fits_the_level`).

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
        self.setVisible(not part_selected)
        if part_selected:
            return
        if selected <= 0:
            # **Ohne Auswahl bleibt der Weg zu den Bausteinen** (Befund
            # Robert, 18.09.2026: „bei keiner Auswahl sollte das merkmalpanel
            # auch da sein um Bausteine setzen zu können"). Die Karte
            # verschwand ganz, und damit war der einzige sichtbare Zugang zum
            # Katalog weg — übrig blieben Strg+K und zwei Menüwege, die
            # niemand sucht, der gerade auf eine leere Fläche klickt. Drei
            # der siebenundzwanzig Bausteine stehen frei (``standalone``) und
            # brauchen gar keinen Körper; der Katalog lässt sie durch und
            # sagt bei den übrigen selbst, was fehlt.
            self._empty_but_for_the_catalogue()
            return
        # **Bausteine setzt man auf eine Fläche, nicht in ein Loch** (Robert,
        # 10.09.2026: „ganz unten wenn wir runterscrollen noch bauteile, das
        # brauchen wir bei gewählten merkmalen garnicht, nur flächen/Körper").
        # Ein Baustein braucht Material, auf dem er sitzt; an einer Bohrung,
        # einer Verrundung oder einem Zapfen führt der Knopf in einen Katalog,
        # aus dem nichts an diese Stelle passt — und er stand dabei unter einer
        # Liste, für die man scrollen muss.
        self.catalog_button.setVisible(feature_kind in ("", "face"))
        if self._feature_kind != feature_kind:
            self._feature_kind = feature_kind
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
        for name, button in self._buttons.items():
            enabled, reason = availability(name)
            state = (enabled, reason)
            if self._states.get(name) == state:
                continue
            self._states[name] = state
            button.setEnabled(enabled)
            spec_tip = button.property("operationTip")
            if spec_tip is None:
                spec_tip = button.toolTip()
                button.setProperty("operationTip", spec_tip)
            tip = str(spec_tip) if enabled or not reason else reason
            button.setToolTip(tip)
            button.setStatusTip(tip)
            button.setAccessibleDescription(tip)
        self._lay_out_quick(
            tuple(
                name
                for name in quick_names(selected, feature_kind)
                if self._buttons[name].isEnabled()
            )
        )
        self._filter()

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
        wanted = self._query.strip().casefold()
        found = 0
        for title, (section, toggle, buttons) in self._groups.items():
            shown = 0
            for button in buttons:
                label = str(button.property("operationTitle") or button.text())
                match = not wanted or wanted in f"{title} {label}".casefold()
                fits = self._fits_the_level(str(button.property("operationName")))
                visible = match and fits and button.isEnabled()
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
        self._say_there_is_nothing(found, bool(wanted))
        # Welche Knöpfe dastehen, hat sich gerade geändert — und ob ihre
        # Beschriftung in die Spalte passt, ist eine Frage je Knopf.
        self._wrap_labels()

    def _empty_but_for_the_catalogue(self) -> None:
        """Ohne Auswahl bleibt nur der Weg zu den Bausteinen.

        Keine Operationsliste — die gilt einer Auswahl, und die gibt es
        nicht. Was bleibt, ist der Knopf und ein Satz, der sagt, woran es
        liegt.
        """
        for section, _toggle, _buttons in self._groups.values():
            section.setVisible(False)
        # **Die Hauptaktionen gehen über ihren eigenen Weg weg, nicht über
        # ``setVisible``.** `_lay_out_quick` kürzt ab, wenn dieselbe Liste
        # schon steht — wer die Knöpfe hier von Hand versteckte, ließ
        # ``_quick_shown`` gefüllt zurück, und beim nächsten gewählten Körper
        # kehrte die Rechnung sofort zurück: Die Zeile blieb leer. Dieselbe
        # Falle, vor der der Docstring von :meth:`_filter` warnt — zwei
        # Stellen, die dieselbe Sichtbarkeit setzen, machen sie abwechselnd.
        self._lay_out_quick(())
        self.summary.setText(tr("Nichts gewählt"))
        self.catalog_button.setVisible(True)
        self._only_this_sentence(
            tr("Wählen Sie einen Körper oder eine Fläche — Bausteine gehen auch so.")
        )

    def _say_there_is_nothing(self, found: int, searching: bool) -> None:
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
        """
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
            self._nothing.setText(tr("Kein Treffer — versuchen Sie ein anderes Wort."))
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
        if self._feature_kind:
            if name in _shown_as_fields():
                return False
            return self._feature_kind in self._at_which_kind.get(name, frozenset())
        return name not in self._at_a_feature

    def chosen_level(self) -> str:
        """Die Stufe, auf die das Panel gerade eingestellt ist.

        Für Tests und für das Fenster: ``""`` heißt Körperstufe, ein
        Merkmalsname die Art des gewählten Merkmals, ``None`` noch gar nichts.
        """
        return self._feature_kind or ""
