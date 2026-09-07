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

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from app.ui.style import NORMAL, TARGET_SIZE, TIGHT, set_level

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
    "hole": ("resize_hole", "countersink_hole", "plug_hole"),
    "edge_loop": ("repair",),
}
"""Je Merkmalsart die Handlungen, die dort zuerst gesucht werden.

Nur wo die Art eine eigene Antwort hat. Kegel, Stift und Kugel bieten die drei
generischen Merkmalshandlungen **mit** an — nicht genau sie: Am Register
gemessen (07.09.2026) trägt `pin` sieben Operationen, `cone` sechs und
`sphere` vier, die drei aus :data:`QUICK_FEATURE` sind darunter. Der Rest steht
in der Suchliste, im Menü und in der Befehlspalette.
"""

QUICK_FEATURE = ("resize_feature", "move_feature", "remove_feature")
"""Für jede Merkmalsart ohne eigene Zeile in :data:`QUICK_FEATURES`."""

PANEL_LEAST_HEIGHT = 280
"""Was das Panel mindestens braucht, in Bildpunkten.

Drei Hauptaktionen, Suche, Trefferliste und die beiden getrennten Wege dürfen
sich auch in einem 720-Pixel-Fenster nicht überlagern. Mit der früheren
190-Pixel-Untergrenze drückte Qt jede Hauptaktion auf rund 15 Pixel und legte
das Suchfeld über „Schnittmenge".

**Benannt, weil eine zweite Datei damit rechnet:** ``MainWindow._fit_right_column``
teilt die Spalte und lässt dem Bericht ``REPORT_RESERVE`` Bildpunkte. Wer eine
der beiden Zahlen ändert, ohne die andere anzusehen, bricht die Annahme der
anderen still — als Literale in zwei Modulen war das nicht zu sehen, und der
Konstanten-Wächter sieht nur benannte Konstanten.
"""

PANEL_MOST_HEIGHT = 420
"""Und was es höchstens nimmt. Darüber wächst der Bericht, nicht die Liste."""


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
        return tuple(name for name in wanted if name in offered)
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


_SEPARATE_CATEGORIES = frozenset({"parts"})


def body_operations(specs: Iterable[OperationSpec]) -> tuple[OperationSpec, ...]:
    """Körperoperationen, ohne den getrennten Bausteinweg.

    Versteckte Rechenkern-Zwillinge sind keine zweite Handlung. Erzeuger ohne
    Eingang gehören ebenfalls nicht an eine Auswahl; sie bleiben im Menü und
    in der Befehlspalette.

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
        and spec.category not in _SEPARATE_CATEGORIES
        and not spec.applies_to
    )


def feature_operations(specs: Iterable[OperationSpec]) -> tuple[OperationSpec, ...]:
    """Was an einem Merkmal gearbeitet wird — Bohren, Senken, Verschließen.

    Dieselbe Zuordnung, aus der das Kontextmenü am Merkmal seine Zeilen baut
    (``applies_to``, §18.5): eine dritte Oberfläche über einer Quelle, keine
    zweite Rechnung. Sie standen bis zum 07.09.2026 nicht im Panel, und damit
    bot eine gewählte Fläche dort nichts an.

    **Die Bausteine bleiben draußen.** Ein räumliches Teil als Textzeile ist
    die schlechtere Darstellung; sie sind durch den Katalogknopf vertreten —
    dieselbe Entscheidung, die auch die Menüleiste trifft.

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
        and spec.category not in _SEPARATE_CATEGORIES
    )


class SelectionOperationsPanel(QWidget):
    """Alle Handlungen für die aktuelle Auswahl, dauerhaft aufgebaut."""

    operationRequested = Signal(object)
    catalogRequested = Signal()
    featurePanelRequested = Signal()

    def __init__(self, specs: Iterable[OperationSpec], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("selectionOperations")
        self.setAccessibleName(tr("Operationen für die Auswahl"))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(PANEL_LEAST_HEIGHT)
        self.setMaximumHeight(PANEL_MOST_HEIGHT)

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
        self._buttons: dict[str, QToolButton] = {}
        self._groups: dict[str, tuple[QLabel, tuple[QToolButton, ...]]] = {}
        self._states: dict[str, tuple[bool, str]] = {}
        self._quick_buttons: dict[str, QToolButton] = {}
        self._quick_shown: list[str] = []
        self._query = ""
        """Der zuletzt eingegebene Suchtext — ein Stufenwechsel darf ihn nicht
        vergessen."""
        self._feature_kind: str | None = None
        """Die Art des gewählten Merkmals, leer auf der Körperstufe.

        ``None`` heißt „noch nie gesetzt" und ist von der Körperstufe (``""``)
        zu unterscheiden: Beim Aufbau stehen alle Knöpfe sichtbar da, und der
        erste :meth:`set_context` muss deshalb filtern, auch wenn er die
        Körperstufe meldet. Mit ``""`` als Startwert tat er es nicht — und an
        einem Körper standen die Merkmalshandlungen weiter in der Liste."""

        self.summary = QLabel("", self)
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
            button.setObjectName("quickOperation")
            button.hide()
            self._quick_buttons[name] = button

        self.search = QLineEdit(self)
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(TARGET_SIZE)
        self.search.setPlaceholderText(tr("Weitere Operationen durchsuchen"))
        self.search.setAccessibleName(tr("Operationen durchsuchen"))
        self.search.textChanged.connect(self._filter)

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(TIGHT)

        grouped: dict[str, list[OperationSpec]] = {}
        for spec in operations:
            # Was oben stehen kann, steht nicht auch darunter: zwei Knöpfe für
            # dieselbe Handlung sind eine Frage ohne Antwort.
            if spec.name in self._quick_buttons:
                continue
            grouped.setdefault(str(group_title(spec.category)), []).append(spec)
        for title in sorted(grouped, key=str.casefold):
            heading = QLabel(title, content)
            set_level(heading, "caption")
            content_layout.addWidget(heading)
            buttons: list[QToolButton] = []
            for spec in sorted(grouped[title], key=lambda entry: str(entry.title).casefold()):
                button = self._operation_button(spec, content)
                content_layout.addWidget(button)
                buttons.append(button)
            self._groups[title] = (heading, tuple(buttons))
        content_layout.addStretch(1)

        self.scroller = QScrollArea(self)
        self.scroller.setWidget(content)
        self.scroller.setWidgetResizable(True)
        self.scroller.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroller.setMinimumHeight(TARGET_SIZE)
        self.scroller.setAccessibleName(tr("Passende Operationen"))

        self.feature_button = QToolButton(self)
        self.feature_button.setText(tr("Merkmale"))
        self.feature_button.setIcon(icon("category.holes", self.feature_button))
        self.feature_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.feature_button.setMinimumHeight(TARGET_SIZE)
        self.feature_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.feature_button.clicked.connect(self.featurePanelRequested)

        self.catalog_button = QToolButton(self)
        self.catalog_button.setText(tr("Bausteine"))
        self.catalog_button.setIcon(icon("category.parts", self.catalog_button))
        self.catalog_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
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
        separate.addWidget(self.feature_button)
        separate.addWidget(self.catalog_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, NORMAL)
        layout.setSpacing(TIGHT)
        layout.addWidget(self.summary)
        layout.addLayout(quick)
        layout.addWidget(self.search)
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
        self._buttons[spec.name] = button
        return button

    def _request_operation(self, spec: OperationSpec) -> None:
        """Den Registereintrag ohne dauerhafte Lambda-Rückbindung weiterreichen."""
        self.operationRequested.emit(spec)

    def _lay_out_quick(self, names: Iterable[str]) -> None:
        """Die Hauptaktionen dieser Lage in die Zeile oben hängen.

        Zwei kurze teilen die erste Zeile, jede weitere bekommt ihre eigene
        über die ganze Breite — bei einer einzigen ist das die erste. Das
        spart dem Bericht auf 720 Pixel Höhe eine volle Zeile, ohne einen
        Titel zu kürzen.

        Steht schon das Richtige da, passiert nichts: Auswahlereignisse kommen
        in Serie, und ein Layout, das bei jedem neu hängt, wirft bei jedem ein
        ``LayoutRequest`` — dasselbe Ereignis, an dem die Überlagerung ihre
        Karten neu verteilt.
        """
        wanted = [name for name in names if name in self._quick_buttons]
        if wanted == self._quick_shown:
            return
        for name in self._quick_shown:
            button = self._quick_buttons[name]
            self._quick.removeWidget(button)
            button.hide()
        self._quick_shown = wanted
        for index, name in enumerate(wanted):
            button = self._quick_buttons[name]
            if len(wanted) > 1 and index < 2:
                self._quick.addWidget(button, 0, index)
            else:
                self._quick.addWidget(button, max(index - 1, 0), 0, 1, 2)
            button.show()

    def set_context(
        self,
        selected: int,
        availability: Callable[[str], tuple[bool, str]],
        *,
        feature_chosen: bool,
        feature_kind: str = "",
        label: str = "",
    ) -> None:
        """Auswahl, Lage und Freigaben nachführen, ohne die Liste neu zu bauen.

        ``feature_kind`` ist die Art des gewählten Merkmals — ``face``,
        ``hole`` und so fort — und leer, solange nur Körper gewählt sind. Sie
        entscheidet zusammen mit ``selected``, welche Hauptaktionen oben
        stehen (:func:`quick_names`) und **welche Handlungen überhaupt
        dastehen** (:meth:`_fits_the_level`).

        ``label`` ist der Name der Auswahl, wie ihn das Fenster kennt —
        ``Halter`` oder ``Halter · Oberseite`` (Konzept B). Er kommt von dort
        und wird hier nicht gebaut: Der Name eines Körpers und die
        Beschriftung eines Merkmals stehen in der Szene, nicht im Panel, und
        eine zweite Rechnung dafür wäre eine zweite Wahrheit. Fehlt er, bleibt
        es bei der Menge.
        """
        self.setVisible(selected > 0)
        if selected <= 0:
            return
        self._lay_out_quick(quick_names(selected, feature_kind))
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

        self.feature_button.setEnabled(feature_chosen)
        feature_tip = (
            tr("Öffnet rechts die Maße und Handlungen des gewählten Merkmals.")
            if feature_chosen
            else tr("Wählen Sie zuerst eine Fläche, Bohrung oder ein anderes Merkmal im Bild.")
        )
        self.feature_button.setToolTip(feature_tip)
        self.feature_button.setStatusTip(feature_tip)
        self.feature_button.setAccessibleDescription(feature_tip)

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
        for title, (heading, buttons) in self._groups.items():
            visible = False
            for button in buttons:
                match = not wanted or wanted in f"{title} {button.text()}".casefold()
                fits = self._fits_the_level(str(button.property("operationName")))
                button.setVisible(match and fits)
                visible = visible or (match and fits)
            heading.setVisible(visible)

    def _fits_the_level(self, name: str) -> bool:
        """Ob diese Handlung zur Stufe der aktuellen Auswahl gehört (Konzept C).

        **Zwei Sorten Nichtverfügbarkeit, und nur eine verschwindet.** Eine
        fehlende Vorbedingung — Vereinigen braucht zwei Körper, gewählt ist
        einer — bleibt grau mit Grund: Der Kunde kann sie erfüllen, und der
        Grund führt ihn hin. Eine Handlung der **falschen Stufe** dagegen hat
        nichts zu erfüllen: Eine Fläche wird nie auf dem Bett angeordnet, und
        *Auf dem Bett anordnen*, *Objekt duplizieren* und *Objekt umbenennen*
        standen an einer gewählten Fläche bedienbar da (38 von 102
        Operationen, gemessen am 07.09.2026).

        Das bricht die Menüregel vom 23.08.2026 nicht, sondern setzt sie eine
        Ebene tiefer fort: Dort bleibt eine graue Zeile stehen, weil die
        Erklärung **neben einem Eintrag steht, der geht**. Hier kommt die
        Handlung beim Wechsel der Stufe wieder — nicht beim zufälligen Klick.
        """
        return (name in self._at_a_feature) == bool(self._feature_kind)

    def chosen_level(self) -> str:
        """Die Stufe, auf die das Panel gerade eingestellt ist.

        Für Tests und für das Fenster: ``""`` heißt Körperstufe, ein
        Merkmalsname die Art des gewählten Merkmals, ``None`` noch gar nichts.
        """
        return self._feature_kind or ""
