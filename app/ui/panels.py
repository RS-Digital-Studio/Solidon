"""Die drei Panels links und der Prüfbericht rechts (Bauplan §2.5).

Drei einklappbare Abschnitte, keine drei Fenster: Objektbaum, Parameter,
Verlauf. Sie lesen aus dem Dokument und der letzten Auswertung, und sie ändern
nie selbst Geometrie — jede Änderung geht durch eine Operation (AGENTS.md
Regel 2).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError
from app.core.registry import REGISTRY
from app.core.scene import EvaluationResult
from app.core.types import Document, Finding, ObjectId
from app.core.units import LengthUnit
from app.i18n import tr
from app.ui.icons import icon
from app.ui.labels import (
    compact_length,
    feature_measure,
    feature_name,
    length,
    localised,
    volume,
)
from app.ui.palette import SEVERITY_ENCODING
from app.ui.style import NORMAL, ROOMY, set_level

#: Zeichen je Schweregrad, aus der gemeinsamen Kodierung — Farbe steht nie
#: allein (§19.1).
SEVERITY_MARKER = {name: entry.symbol for name, entry in SEVERITY_ENCODING.items()}

#: In welcher Reihenfolge die Schweregrade stehen. Die Zeile über der Liste
#: zählt Fehler, Warnungen und Hinweise getrennt — sie verspricht damit eine
#: Rangfolge, und die Liste darunter hielt sie nicht: sie hängte an, wie es
#: kam, also stand bei zwei Warnungen und vier Hinweisen zuoberst ein Hinweis.
#: Wer einen Fehler suchte, musste ihn filtern statt lesen.
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _by_severity(findings: Iterable[Finding]) -> list[Finding]:
    """Schweres zuerst, sonst in der Reihenfolge, in der es entstanden ist.

    Stabil sortiert: innerhalb eines Grades bleibt die Kette der Operationen
    lesbar, und die erzählt, an welcher Stelle etwas schiefging.
    """
    return sorted(findings, key=lambda entry: SEVERITY_ORDER.get(entry.severity, 3))


#: Farbe der zurückgenommenen Schritte im Verlauf — dieselbe wie für einen
#: verworfenen Chatbeitrag, und aus demselben Grund.
UNDONE_COLOUR = "#7a828c"


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
_LINE_VALUES: dict[str, str] = {
    "object": "",
    "a": "",
    "b": "",
    "excess": "",
    "shared": "",
    # Aushöhlen sagte „Die Wandstärke stimmt im Rahmen des Rasters", ohne die
    # Wandstärke zu nennen — und wie viel Material dabei gespart wurde, also
    # die Frage, für die man die Operation überhaupt aufruft, stand nur im
    # Tooltip.
    "wall_mm": "mm",
    "removed_cm3": "cm³",
}


def _op_title(name: str) -> str:
    """Der Titel einer Operation, wie das Menü ihn zeigt.

    Der Verlauf schrieb den Registernamen: zwischen „Grundkörper" und
    „Versteifung" stand `insert_screw_hole`. Beides sind dieselben Schritte,
    nur kommt der eine Text aus der Transaktion und der andere aus dem Code.

    Eine Operation, die das Register nicht kennt, behält ihren Namen — eine
    Projektdatei aus einer neueren Fassung ist kein Grund, eine Zeile leer zu
    lassen.
    """
    try:
        return str(REGISTRY.get(name).title)
    except AppError:
        return name


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
    extra = [
        f"{localised(str(finding.values[key]))} {unit}".strip()
        for key, unit in _LINE_VALUES.items()
        if key in finding.values
    ]
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


class ObjectTree(QWidget):
    """Objekte der Szene mit ihren Merkmalen, Herkunft und Größe (§18.8,
    §18.5).
    """

    selectionChanged = Signal(object)
    featureSelected = Signal(object)
    """Ein im Baum gewähltes Merkmal — trägt seine ID, oder None."""
    operationRequested = Signal(object)
    """Eine aus dem Kontextmenü gewählte Operation — trägt ihre ``OperationSpec``."""
    visibilityRequested = Signal(object, bool)
    """Ein- oder ausblenden (§18.8) — trägt die Kennungen und den Wunsch."""
    isolateRequested = Signal(object)
    """Nur diese zeigen — trägt die Kennungen. Ein zweiter Aufruf hebt es auf."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([tr("Objekt"), tr("Maße")])
        # Die Maßspalte nimmt, was sie braucht; der Rest gehört den Namen.
        # Vorher standen beide auf derselben festen Breite, und auf dreifache
        # Fensterbreite gezogen blieb die Maßspalte schmal, während links
        # jeder Merkmalsname abgeschnitten war.
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        # §25: Vereinigen, Abziehen und Schnittmenge nehmen zwei Körper. Mit
        # Einfachauswahl war keine davon über das Menü ausführbar — die
        # Operation bekam einen Eingang, wo sie zwei erwartet, und lehnte ab.
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setRootIsDecorated(True)
        self._order: list[ObjectId] = []
        """Die Reihenfolge, in der angeklickt wurde. „A minus B" ist nicht „B
        minus A", und die Reihenfolge im Baum weiß davon nichts."""
        self._hidden: frozenset[ObjectId] = frozenset()
        self._unit: LengthUnit = "mm"
        self._result: EvaluationResult | None = None
        self._document: Document | None = None
        """Das Zuletzt-Gezeigte, damit sich der Baum ohne neue Auswertung
        neu zeichnen kann — beim Ausblenden ändert sich nur die Anzeige."""
        self.tree.itemSelectionChanged.connect(self._on_selection)
        self.tree.setAcceptDrops(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
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

    def show_scene(self, result: EvaluationResult | None, document: Document | None = None) -> None:
        selected = self.selected_objects()
        selected_feature = self.selected_feature()
        self._result = result
        self._document = document
        self.tree.clear()
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
            item = QTreeWidgetItem([entry.name, f"{measures} {self._unit}"])
            item.setData(0, Qt.ItemDataRole.UserRole, object_id)
            state = tr("geschlossen") if entry.mesh.is_watertight else tr("offen")
            # §30: welche Sorte Körper das ist, gehört in den Baum, denn sie
            # entscheidet, was sich noch mit ihm tun lässt — und der Weg von
            # B-Rep zu Mesh ist eine Einbahnstraße.
            kind = tr("exakt") if entry.kind == "brep" else tr("Netz")
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
            if entry.kind == "brep":
                item.setText(0, f"{entry.name}  ·  {kind}")
            if object_id in self._hidden:
                # Zeichen und Wort: eine ausgegraute Zeile allein wäre Farbe als
                # einzige Kodierung (Regel 18).
                item.setIcon(0, icon("hidden", self.tree))
                item.setText(0, f"{item.text(0)}  ·  {tr('ausgeblendet')}")
            if entry.material:
                # §12: ein Körper, der nicht im Material des Projekts ist, muss das
                # dort sagen, wo die Teile aufgezählt werden — sonst zeigt sich
                # der Unterschied nur an einer Passung, die auf einmal ein
                # anderes Spiel will.
                item.setText(1, f"{item.text(1)}  ·  {entry.material}")
            for feature_id, feature in entry.features.items():
                # Name links, Maß rechts. Vorher stand die ganze Beschriftung
                # links und rechts der Typ („hole", „face") — links war damit
                # abgeschnitten, was rechts gefehlt hat.
                child = QTreeWidgetItem(
                    [feature_name(feature_id, feature), feature_measure(feature)]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, object_id)
                child.setData(1, Qt.ItemDataRole.UserRole, feature_id)
                child.setToolTip(0, f"{feature_id} · {feature.provenance}")
                item.addChild(child)
            self.tree.addTopLevelItem(item)
            item.setExpanded(object_id in selected)
        self.tree.resizeColumnToContents(0)
        self._restore(selected, selected_feature)

    def _restore(self, objects: Sequence[ObjectId], feature_id: str | None) -> None:
        """Behält die Auswahl über eine Neuauswertung hinweg — sie zu verlieren
        kostet den Nutzer die Stelle, an der er gearbeitet hat.

        Das Merkmal gilt nur, wenn genau ein Körper gewählt war; bei mehreren
        gibt es keines, auf das es sich beziehen könnte.
        """
        if not objects:
            return
        wanted = set(objects)
        self._order = list(objects)
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is None or item.data(0, Qt.ItemDataRole.UserRole) not in wanted:
                continue
            if feature_id is not None and len(wanted) == 1:
                for child_index in range(item.childCount()):
                    child = item.child(child_index)
                    if child is not None and child.data(1, Qt.ItemDataRole.UserRole) == feature_id:
                        child.setSelected(True)
                        break
                else:
                    item.setSelected(True)
                continue
            item.setSelected(True)

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

    def select_object(self, object_id: ObjectId | None) -> None:
        """Wählt einen Körper von außen aus — der Fehlerdialog tut das, wenn er
        zeigt, worum es ging, und ein Klick in der Ansicht ebenso.

        ``None`` hebt die Auswahl auf: wer neben das Modell klickt, will sie
        loswerden.
        """
        self.tree.clearSelection()
        if object_id is not None:
            self._restore((object_id,), None)

    def select_feature(self, object_id: ObjectId, feature_id: str) -> None:
        """Folgt einem Klick im Viewport — die zwei Ansichten zeigen eine
        Auswahl (§18.5).
        """
        self.tree.clearSelection()
        self._restore((object_id,), feature_id)

    def _on_selection(self) -> None:
        self._remember_order()
        self.selectionChanged.emit(self.selected())
        self.featureSelected.emit(self.selected_feature())

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
        """
        return tuple(spec for spec in REGISTRY.all() if spec.consumes == 1)

    def operations_for_feature(self, kind: str) -> tuple[Any, ...]:
        """Was eine Bohrung oder eine Fläche anbietet, direkt aus ``applies_to``
        (§10, §18.5).
        """
        return REGISTRY.for_feature(kind)

    def _feature_kind(self) -> str | None:
        items = self.tree.selectedItems()
        if not items or self.selected_feature() is None:
            return None
        return items[0].text(1)

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
        self._add_visibility(menu, chosen)

        kind = self._feature_kind()
        entries = self.operations_for_feature(kind) if kind else self.operations_for_object()
        if entries:
            menu.addSeparator()
            for spec in entries:
                action = menu.addAction(str(spec.title))
                action.triggered.connect(
                    lambda _checked=False, entry=spec: self.operationRequested.emit(entry)
                )
        return menu

    def _on_context_menu(self, position: QPoint) -> None:
        menu = self.context_menu()
        if menu is not None:
            menu.exec(self.tree.viewport().mapToGlobal(position))

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

        isolated = self._hidden and all(object_id not in self._hidden for object_id in chosen)
        isolate = menu.addAction(
            tr("Alles andere ausblenden") if not isolated else tr("Alle zeigen")
        )
        isolate.triggered.connect(lambda _checked=False: self.isolateRequested.emit(chosen))


def _empty_parameters_text() -> str:
    """Der leere Zustand sagt, wozu die Leiste da ist — „Noch keine
    Parameter." allein ließ die Frage offen, wie denn einer entsteht."""
    return tr(
        "Noch keine Parameter. Ein Parameter ist ein benanntes Maß — "
        "Operationen und Skizzen rechnen mit ihm."
    )


class ParameterPanel(QWidget):
    """Benannte Projektmaße; an einer Zahl zu drehen baut das Modell
    neu (§13).
    """

    parameterEdited = Signal(str, float)
    addRequested = Signal()
    """Der Nutzer will ein Maß benennen — das Fenster öffnet den Dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        self._form = QFormLayout()
        self._form.setContentsMargins(0, 0, 0, 0)
        self._empty = QLabel(_empty_parameters_text(), self)
        self._empty.setWordWrap(True)
        self._form.addRow(self._empty)
        self._editors: dict[str, QDoubleSpinBox] = {}
        # §2.3: das Anlegen war ein Agentenwerkzeug und sonst nichts — wer
        # ohne Sprachmodell arbeitet, brauchte einen Weg mit der Maus.
        self.add_button = QPushButton(tr("Parameter anlegen …"), self)
        self.add_button.clicked.connect(self.addRequested)
        outer.addLayout(self._form)
        outer.addWidget(self.add_button, alignment=Qt.AlignmentFlag.AlignLeft)
        outer.addStretch(1)

    def show_document(self, document: Document) -> None:
        while self._form.rowCount():
            self._form.removeRow(0)
        self._editors.clear()

        if not document.parameters:
            self._empty = QLabel(_empty_parameters_text(), self)
            self._empty.setWordWrap(True)
            self._form.addRow(self._empty)
            return

        for name, parameter in document.parameters.items():
            if parameter.expression:
                # Abgeleitete Werte werden gezeigt, nicht bearbeitet — der Ausdruck
                # besitzt sie.
                label = QLabel(f"{parameter.value:.2f} {parameter.unit}", self)
                label.setToolTip(parameter.expression)
                self._form.addRow(f"{parameter.title or name}", label)
                continue
            editor = QDoubleSpinBox(self)
            editor.setDecimals(2)
            editor.setSuffix(f" {parameter.unit}")
            editor.setMinimum(parameter.minimum if parameter.minimum is not None else -100_000.0)
            editor.setMaximum(parameter.maximum if parameter.maximum is not None else 100_000.0)
            editor.setValue(parameter.value)
            editor.setKeyboardTracking(False)
            editor.valueChanged.connect(
                lambda value, key=name: self.parameterEdited.emit(key, value)
            )
            self._editors[name] = editor
            self._form.addRow(f"{parameter.title or name}", editor)


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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.list = QListWidget(self)
        self.list.itemDoubleClicked.connect(self._on_activated)
        self.list.setToolTip(tr("Doppelklick öffnet die Operation und ihre Parameter."))
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list)

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
        for transaction in document.transactions:
            # Nur was abweicht, wird ausgeschrieben (§26.4). „(Nutzer)" stand
            # vorher an jeder Zeile — in einem Projekt ohne Agenten also
            # überall, und was überall steht, liest niemand mehr. Dieselbe
            # Überlegung wie beim Material im Steckbrief: genannt wird, was
            # nicht die Regel ist.
            by = f"  ({tr('Agent')})" if transaction.origin.by == "agent" else ""
            item = QListWidgetItem(f"{transaction.title}{by}")
            if stopped_at is not None and stopped_at in transaction.ops:
                # §15.3: die betroffenen Operationen werden im Verlauf markiert.
                item.setText(f"! {item.text()}")
            item.setToolTip(
                f"{transaction.id} · {tr('Ops')} "
                + ", ".join(str(entry) for entry in transaction.ops)
            )
            if len(transaction.ops) == 1:
                item.setData(Qt.ItemDataRole.UserRole, transaction.ops[0])
            self.list.addItem(item)

            if len(transaction.ops) > 1:
                for op_id in transaction.ops:
                    child = QListWidgetItem(f"    {op_id}  {titles.get(op_id, '')}")
                    child.setData(Qt.ItemDataRole.UserRole, op_id)
                    self.list.addItem(child)

        for transaction in reversed(list(undone)):
            item = QListWidgetItem(f"{transaction.title}  ({tr('zurückgenommen')})")
            font = QFont(item.font())
            font.setStrikeOut(True)
            item.setFont(font)
            item.setForeground(QColor(UNDONE_COLOUR))
            item.setToolTip(tr("Ein Wiederholen holt diesen Schritt zurück."))
            self.list.addItem(item)

        self.list.scrollToBottom()

    def _on_activated(self, item: QListWidgetItem) -> None:
        op_id = item.data(Qt.ItemDataRole.UserRole)
        if op_id is not None:
            self.operationActivated.emit(int(op_id))

    def _on_context_menu(self, position: QPoint) -> None:
        """Was man mit einem Schritt tun kann, dort, wo er steht.

        Bisher gab es nur den Doppelklick, und den findet, wer ihn probiert.
        Angeboten wird, was der Stapel wirklich kann: einen Schritt öffnen und
        seine Zahlen ändern (§15.4). Einen Schritt aus der Mitte zu entfernen
        steht nicht dabei — spätere Operationen bauen auf seinen Ausgaben auf,
        und ein Menüeintrag, der manchmal geht, ist schlimmer als keiner.
        """
        item = self.list.itemAt(position)
        op_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if op_id is None:
            return

        menu = QMenu(self)
        action = menu.addAction(tr("Parameter ändern …"))
        action.triggered.connect(lambda _checked=False: self.operationActivated.emit(int(op_id)))
        menu.exec(self.list.viewport().mapToGlobal(position))


class ReportPanel(QWidget):
    """Befunde aus Einlesen, Operationen und Prüfungen (§17.3)."""

    findingActivated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._names: Mapping[str, str] = {}
        """Kennung zu Namen, aus der zuletzt gezeigten Szene."""
        self.list = QListWidget(self)
        # §2.7 schreibt die Sätze, die hier stehen — im schmalen rechten
        # Bereich endeten sie mitten im Wort hinter einer horizontalen
        # Bildlaufleiste. Umbruch statt Abschneiden: die Leiste bleibt aus,
        # und kein Befund wird auf „…" gekürzt.
        self.list.setWordWrap(True)
        self.list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # §18.4 sagt „Klick auf eine Warnung fährt die Kamera hin" —
        # ``itemActivated`` allein hieß aber Doppelklick oder Eingabetaste,
        # und wer einmal klickte, bekam nichts. Beide Wege führen zum Ort;
        # dass ein Doppelklick dann zweimal fährt, ist dasselbe Ziel.
        self.list.itemClicked.connect(self._on_activated)
        self.list.itemActivated.connect(self._on_activated)
        self.summary = QLabel(tr("Keine Befunde."), self)
        self.summary.setWordWrap(True)

        # Ein Bericht mit hundert Hinweisen und zwei Fehlern versteckt die zwei.
        # Gefiltert wird über den Text und über den Schweregrad; beides
        # zusammen, weil „Wandstärke" und „nur die Fehler" verschiedene Fragen
        # sind (§17.3).
        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("Befunde durchsuchen …"))
        self.search.textChanged.connect(self._refilter)
        self.severity = QComboBox(self)
        self.severity.addItem(tr("Alle"), "")
        for name in ("error", "warning", "info"):
            self.severity.addItem(f"{SEVERITY_MARKER[name]} {_severity_label(name)}", name)
        self.severity.currentIndexChanged.connect(self._refilter)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.addWidget(self.search, stretch=1)
        filter_row.addWidget(self.severity)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        layout.addWidget(self.summary)
        layout.addLayout(filter_row)
        layout.addWidget(self.list)

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

    def show_result(self, result: EvaluationResult | None) -> None:
        # Die Namen der Körper, damit ein Befund sagen kann, welchen er meint.
        # Sie stehen im Ergebnis, das ohnehin hereinkommt — die Kennung „obj_2"
        # wäre die zweitbeste Antwort auf „welcher denn".
        self._names = (
            {str(key): entry.name for key, entry in result.scene.objects.items()} if result else {}
        )
        self.list.clear()
        for finding in _by_severity(result.scene.report.findings if result else ()):
            self._append(finding)
        self._count_up()
        self._refilter()

    def add_findings(self, findings: list[Finding]) -> None:
        """Hängt Befunde an, die nicht aus der Auswertung kamen — die
        G-Code-Gegenprobe etwa (§28.2). Sie behalten ihre eigene
        Herkunft (§22.5).

        Was schon dasteht, kommt nicht noch einmal. Mehrere Prüfungen sehen
        dieselbe Sache: „Kollisionen prüfen" und die Exportprüfung melden beide,
        dass ein Körper über den Bauraum hinaussteht, und nach beiden stand die
        Zeile zweimal da. Zweimal gemeldet ist nicht zweimal passiert — ein
        Zähler daneben wäre eine Zahl, die etwas anderes behauptet.
        """
        known = self._known()
        fresh = []
        for finding in findings:
            key = _identity(finding)
            if key in known:
                continue
            known.add(key)
            self._append(finding)
            fresh.append(key)
        self._resort()
        self._count_up()
        self._refilter()
        if fresh:
            # Nach dem Ordnen steht der neue Befund nicht mehr unten, sondern
            # dort, wo sein Gewicht ihn hinstellt — also wird er gesucht und
            # nicht die Liste ans Ende gefahren.
            self._show_first_of(fresh)

    def _resort(self) -> None:
        """Die ganze Liste nach Schwere ordnen.

        Nach jedem Anhängen und nicht nur beim Aufbau: ein Fehler, der über
        ``add_findings`` nachkommt, gehört nach oben und nicht ans Ende
        dessen, was schon dasteht.
        """
        findings = [
            self.list.item(row).data(Qt.ItemDataRole.UserRole) for row in range(self.list.count())
        ]
        self.list.clear()
        for finding in _by_severity(findings):
            self._append(finding)

    def _show_first_of(self, keys: list[tuple[Any, ...]]) -> None:
        """Zum obersten der genannten Befunde scrollen."""
        for row in range(self.list.count()):
            item = self.list.item(row)
            if _identity(item.data(Qt.ItemDataRole.UserRole)) in keys:
                self.list.scrollToItem(item)
                return

    def _known(self) -> set[tuple[Any, ...]]:
        """Woran die Liste einen Befund wiedererkennt."""
        return {
            _identity(self.list.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self.list.count())
        }

    def _append(self, finding: Finding) -> None:
        """Einen Befund als Eintrag anhängen."""
        encoding = SEVERITY_ENCODING[finding.severity]
        item = QListWidgetItem(_line_for(finding, self._names))
        # Die Form trägt den Schweregrad, die Farbe verstärkt ihn nur: ein
        # Dreieck bleibt ein Dreieck, auch wo die Farbe nicht ankommt.
        item.setIcon(
            icon(f"severity-{finding.severity}", self.list, colour=QColor(encoding.colour))
        )
        item.setData(Qt.ItemDataRole.UserRole, finding)
        item.setForeground(QColor(encoding.colour))
        # §22.5: woher eine Zahl kommt, ist Teil des Befunds und wird nie dem
        # Leser zum Annehmen überlassen — eine Schätzung ist keine Messung.
        details = [f"{tr('Herkunft')}: {origin_label(finding.source)}"]
        details.extend(f"{key}: {value}" for key, value in finding.values.items())
        item.setToolTip(" · ".join(details))
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
            finding: Finding = self.list.item(row).data(Qt.ItemDataRole.UserRole)
            counts[finding.severity] += 1
        if not any(counts.values()):
            self.summary.setText(tr("Keine Befunde."))
            return
        self.summary.setText(
            f"{counts['error']} × {tr('Fehler')} · "
            f"{counts['warning']} × {tr('Warnung')} · "
            f"{counts['info']} × {tr('Hinweis')}"
        )

    def worst_severity(self, result: EvaluationResult | None) -> str | None:
        if result is None:
            return None
        return result.scene.report.worst_severity

    def _on_activated(self, item: QListWidgetItem) -> None:
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        self.findingActivated.emit(finding)


class ChatPlaceholder(QWidget):
    """Ohne LLM-Schlüssel funktioniert alles außer dem Chat — ein Hinweis,
    kein Nörgeln (§2.3).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        hint = QLabel(
            tr(
                "Der Chat braucht einen Zugang zu einem Sprachmodell. "
                "Alles andere funktioniert ohne."
            ),
            self,
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ROOMY, ROOMY, ROOMY, ROOMY)
        layout.addWidget(hint)
        layout.addStretch(1)


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

    def show_object(self, name: str, size: tuple[float, float, float], content: float) -> None:
        self.setText(
            f"{name}   "
            f"{length(size[0], self._unit, with_unit=False)} × "
            f"{length(size[1], self._unit, with_unit=False)} × "
            f"{length(size[2], self._unit)}   "
            f"{volume(content, self._unit)}"
        )


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


def describe_selection(result: EvaluationResult | None, object_id: ObjectId | None) -> Any:
    """Name, Größe und Volumen des gewählten Objekts, oder None."""
    if result is None or object_id is None:
        return None
    entry = result.scene.objects.get(object_id)
    if entry is None:
        return None
    return entry.name, entry.mesh.bounds.size, entry.mesh.volume
