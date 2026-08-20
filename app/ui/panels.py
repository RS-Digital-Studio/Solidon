"""Die drei Panels links und der Prüfbericht rechts (Bauplan §2.5).

Drei einklappbare Abschnitte, keine drei Fenster: Objektbaum, Parameter,
Verlauf. Sie lesen aus dem Dokument und der letzten Auswertung, und sie ändern
nie selbst Geometrie — jede Änderung geht durch eine Operation (AGENTS.md
Regel 2).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, cast

from PySide6.QtCore import QByteArray, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QImage, QPainter, QPixmap
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

from app.core import drawing
from app.core.drawing import Theme as DrawingTheme
from app.core.errors import (
    REPAIR_AND_RETRY,
    SCALE_TO_FIT,
    SHOW_LOCATIONS,
    SPLIT_MODEL,
    Action,
    AppError,
)
from app.core.log import get_logger
from app.core.registry import REGISTRY
from app.core.scene import EvaluationResult
from app.core.types import Document, Finding, ObjectId
from app.core.units import LengthUnit
from app.i18n import format_decimal, sort_key, tr
from app.ui.dialogs import handlers_of
from app.ui.icons import icon
from app.ui.labels import (
    compact_length,
    feature_measure,
    feature_name,
    group_title,
    kind_requirement,
    length,
    localised_value,
    value_line,
    volume,
)
from app.ui.overlay import LEFT_WIDTH
from app.ui.palette import SEVERITY_ENCODING, Role, text_colour
from app.ui.style import NORMAL, ROOMY, TIGHT, set_level

_log = get_logger(__name__)

#: Zeichen je Schweregrad, aus der gemeinsamen Kodierung — Farbe steht nie
#: allein (§19.1).
SEVERITY_MARKER = {name: entry.symbol for name, entry in SEVERITY_ENCODING.items()}

#: Wie viele Operationen ein Kontextmenü flach zeigt, bevor es nach Kategorie
#: gruppiert. Dieselbe Zahl, die ``MAX_SUBMENU_ENTRIES`` in
#: ``tests/test_interface_limits.py`` der Menüleiste zieht, und aus demselben
#: Grund: darüber liest niemand mehr, er sucht.
MAX_MENU_ROWS = 12


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
    "arrange.out_of_build_volume": (SPLIT_MODEL, SCALE_TO_FIT),
    "export.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    "ingest.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
}


def as_error(finding: Finding) -> AppError:
    """Einen Befund so verpacken, dass die Fehlerhandlungen ihn annehmen.

    Die Handler des Fensters (``error_handlers``) arbeiten auf einem
    ``AppError``, weil sie aus dem Fehlerdialog kommen. Ein Befund ist keiner
    — er trägt aber genau die zwei Angaben, die sie lesen: den Körper und die
    Zahlen. Sie zweimal zu schreiben, einmal für Fehler und einmal für
    Befunde, hieße zwei Wahrheiten über dieselbe Handlung.
    """
    return AppError(
        title=finding.message,
        object_id=finding.object_id,
        op_id=finding.op_id,
        values=dict(finding.values),
    )


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
        # Über ``localised_value``: Ein Befund trägt neben Zahlen auch Pfade,
        # Adressen und Endungen, und ``localised`` tauschte dort jeden Punkt
        # gegen ein Komma — „sources/1_cube_clean,stl".
        f"{localised_value(finding.values[key])} {unit}".strip()
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
        self.tree.setAccessibleName(tr("Objekte"))
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
        """Das Zuletzt-Gezeigte, damit sich der Baum ohne neue Auswertung
        neu zeichnen kann — beim Ausblenden ändert sich nur die Anzeige."""
        self.tree.itemSelectionChanged.connect(self._on_selection)
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
        self._result = result
        self._document = document
        self.tree.clear()
        # Was noch nicht gezeichnet war, gehört zu Zeilen, die es nicht mehr
        # gibt. Der Vorrat bleibt: dieselben Körper kommen meist wieder.
        self._pending.clear()
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
        self._fit()
        # Erst steht der Baum, dann kommen die Bilder nach. Andersherum wartet
        # der Nutzer auf eine Liste, die längst fertig gerechnet ist.
        if self._pending:
            QTimer.singleShot(0, self, self._render_pending)

    def _rows(self) -> int:
        """Die sichtbaren Zeilen — ein zugeklappter Ast zählt als eine."""
        rows = 0
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is None:
                continue
            rows += 1 + (item.childCount() if item.isExpanded() else 0)
        return rows

    def wanted_height(self) -> int:
        """Die Höhe, bei der jede Zeile zu sehen wäre."""
        return view_chrome(self.tree) + self._rows() * row_height_of(self.tree)

    def set_room(self, pixels: int) -> None:
        """Wie hoch diese Karte werden darf (siehe ``fit_to_rows``)."""
        if pixels == self._room:
            return
        self._room = pixels
        self._fit()

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
                (spec for spec in REGISTRY.all() if spec.consumes == 1),
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
        """
        return REGISTRY.for_feature(kind)

    def _feature_kind(self) -> str | None:
        """Die Art des gewählten Merkmals — ``hole``, ``face``, ``edge``.

        Gelesen wurde sie aus der zweiten Spalte des Baums, und dort steht das
        Maß: „Ø3,22 mm" für eine Bohrung, „4334 mm²" für eine Fläche. Als Art
        an ``for_feature`` gereicht, fand die Anfrage nie eine Operation, und
        das Kontextmenü an einem Merkmal bestand aus Ausblenden und Alles
        andere ausblenden — an genau dem Ort, den §18.5 „die wichtigste
        Einzelfunktion" nennt.
        """
        feature_id = self.selected_feature()
        object_id = self.selected()
        if feature_id is None or object_id is None or self._result is None:
            return None
        entry = self._result.scene.objects.get(object_id)
        feature = entry.features.get(feature_id) if entry is not None else None
        return feature.kind if feature is not None else None

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
            self._add_operations(menu, entries, self.kinds_of_selection())
        return menu

    def _add_operations(
        self, menu: QMenu, entries: Sequence[Any], kinds: Sequence[str] = ()
    ) -> None:
        """Die Operationen ins Menü — flach, solange man sie überblickt.

        An einem Merkmal sind es eine Handvoll, und die stehen direkt da: der
        kurze Weg vom Sehen zum Tun (§2.6) verträgt kein Aufklappen. An einem
        ganzen Körper sind es siebenundfünfzig, und eine Liste dieser Länge ist
        kein Menü mehr, sondern ein Register ohne Suchfeld — dieselbe Grenze,
        die `tests/test_interface_limits.py` für die Menüleiste zieht.

        Gruppiert wird dann nach derselben Kategorie, nach der auch die
        Menüleiste gruppiert. Beides kommt aus dem Register, kann also nicht
        auseinanderlaufen.
        """
        if len(entries) <= MAX_MENU_ROWS:
            for spec in entries:
                self._add_operation(menu, spec, kinds)
            return

        groups: dict[str, list[Any]] = {}
        for spec in entries:
            groups.setdefault(group_title(str(spec.category)), []).append(spec)
        # Mit dem Menü als Elternteil erzeugt, nicht über ``addMenu(titel)``:
        # sonst hält nichts auf der Python-Seite das Untermenü, und sein
        # C++-Objekt wird eingesammelt, während es noch im Menü hängt —
        # dieselbe Falle wie in der Menüleiste.
        for title in sorted(groups):
            submenu = QMenu(title, menu)
            for spec in groups[title]:
                self._add_operation(submenu, spec, kinds)
            menu.addMenu(submenu)

    def _add_operation(self, menu: QMenu, spec: Any, kinds: Sequence[str] = ()) -> None:
        action = menu.addAction(str(spec.title))
        action.setStatusTip(str(spec.doc))
        action.setToolTip(str(spec.doc))
        # **Was auf dieser Bauart nicht geht, sagt es vorher.** Hier stand jede
        # Operation mit einem Eingang anklickbar da, auch die sieben des exakten
        # Kerns: Wer am Netz-Körper *Verrunden* wählte, füllte einen Dialog aus
        # und bekam danach eine Absage — die Sackgasse, die Regel 19 ausschließt
        # und die die Menüleiste seit je vermeidet. Der Satz kommt aus
        # ``labels``, damit beide Menüs dasselbe sagen.
        reason = kind_requirement(spec, kinds)
        if reason:
            action.setEnabled(False)
            action.setStatusTip(reason)
            action.setToolTip(reason)
        action.triggered.connect(
            lambda _checked=False, entry=spec: self.operationRequested.emit(entry)
        )

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
        fit_wrapped(self._empty)
        self._form.addRow(self._empty)
        self._editors: dict[str, QDoubleSpinBox] = {}
        # §2.3: das Anlegen war ein Agentenwerkzeug und sonst nichts — wer
        # ohne Sprachmodell arbeitet, brauchte einen Weg mit der Maus.
        self.add_button = QPushButton(tr("Parameter anlegen …"), self)
        self.add_button.clicked.connect(self.addRequested)
        outer.addLayout(self._form)
        outer.addWidget(self.add_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self._outer = outer
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
        """
        self.setMinimumHeight(self._outer.sizeHint().height())
        self.updateGeometry()

    def show_document(self, document: Document) -> None:
        while self._form.rowCount():
            self._form.removeRow(0)
        self._editors.clear()

        if not document.parameters:
            self._empty = QLabel(_empty_parameters_text(), self)
            self._empty.setWordWrap(True)
            fit_wrapped(self._empty)
            self._form.addRow(self._empty)
            self._fit()
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
    bakeRequested = Signal(int)
    """Der Stand einer Formsitzung soll festgeschrieben werden (Entscheidung D).

    Als Signal und nicht als Aufruf: Die Nachfrage stellt das Fenster, denn sie
    ist die einzige im ganzen Programm — die Handlung ist nicht folgenlos
    rücknehmbar, und Regel 19 gilt nur für die, die es sind."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.list = QListWidget(self)
        self.list.setAccessibleName(tr("Verlauf"))
        self.list.itemDoubleClicked.connect(self._on_activated)
        self.list.setToolTip(tr("Doppelklick öffnet die Operation und ihre Parameter."))
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
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

        self._fit()
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
        if int(op_id) in self._bakeable:
            # Nur an einer Formsitzung, und nur an einer, die noch gerechnet
            # wird: Ein Eintrag, der an jedem Schritt steht und an fast keinem
            # etwas tut, ist einer, den man nicht mehr liest.
            frozen = menu.addAction(tr("Stand festschreiben …"))
            frozen.triggered.connect(lambda _checked=False: self.bakeRequested.emit(int(op_id)))
        menu.exec(self.list.viewport().mapToGlobal(position))


class ReportPanel(QWidget):
    """Befunde aus Einlesen, Operationen und Prüfungen (§17.3)."""

    findingActivated = Signal(object)

    contentGrew = Signal()
    """Die Liste hat Zeilen bekommen und will mehr Platz.

    Ein ``QListWidget`` meldet das von sich aus nicht — seine Wunschgröße
    hängt an der Größenrichtlinie, nicht am Inhalt. Und die Karte hängt in
    keinem Layout, das ein ``LayoutRequest`` weiterreichen könnte: sie bekommt
    ihre Geometrie von ``OverlayHost`` zugewiesen. Wer weiß, dass sich etwas
    geändert hat, sagt es — das ist der Weg, den ``OverlayHost.reflow``
    ausdrücklich vorsieht.
    """

    alertsChanged = Signal(int)
    """Wie viele Fehler und Warnungen jetzt im Bericht stehen.

    Der Reiter darüber trägt die Zahl; ohne sie ist eine Warnung unsichtbar,
    solange Chat oder Tour vorn stehen.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._names: Mapping[str, str] = {}
        self._document: Document | None = None
        """Nur für die Herkunftszeile im Tooltip — welcher Schritt das gemeldet
        hat. Der Bericht braucht das Dokument für nichts anderes."""
        """Kennung zu Namen, aus der zuletzt gezeigten Szene."""
        self._alerts = 0
        """Fehler und Warnungen im aktuellen Bericht — siehe :meth:`alerts`."""
        self.list = QListWidget(self)
        self.list.setAccessibleName(tr("Befunde"))
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
        # Und was dagegen hilft, steht im Kontextmenü — siehe :meth:`_on_menu`.
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_menu)
        self.summary = QLabel(tr("Keine Befunde."), self)
        self.summary.setWordWrap(True)
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
        self.search.setPlaceholderText(tr("Befunde durchsuchen …"))
        self.search.setAccessibleName(tr("Befunde durchsuchen"))
        self.search.textChanged.connect(self._refilter)
        self.severity = QComboBox(self)
        self.severity.setAccessibleName(tr("Nach Schweregrad filtern"))
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
        # Wenn der Filter alles wegnimmt, steht sonst ein leerer Rahmen da und
        # sagt nicht, ob nichts passt oder ob der Bericht leer ist. Ein Label
        # und kein Listeneintrag: gefiltert wird über ``setHidden``, die Liste
        # bleibt gefüllt, und ein Eintrag darin wäre beim nächsten Filtern im
        # Weg.
        self._nothing = QLabel("", self)
        self._nothing.setWordWrap(True)
        self._nothing.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        self._nothing.setVisible(False)

        layout.addWidget(self.facts)
        layout.addLayout(filter_row)
        layout.addWidget(self._nothing)
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

        visible = sum(1 for row in range(self.list.count()) if not self.list.item(row).isHidden())
        if visible or not self.list.count():
            self._nothing.setVisible(False)
            return
        begriff = self.search.text().strip()
        stufe = self.severity.currentText().strip()
        if begriff and wanted:
            satz = tr("Kein Befund passt zu „{begriff}“ und „{stufe}“.")
        elif begriff:
            satz = tr("Kein Befund passt zu „{begriff}“.")
        else:
            satz = tr("Kein Befund dieser Stufe: „{stufe}“.")
        self._nothing.setText(str(satz).format(begriff=begriff, stufe=stufe))
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
        self._measure_up(result)
        self._refilter()
        self._grew()

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
        item.setForeground(tone)
        # §22.5: woher eine Zahl kommt, ist Teil des Befunds und wird nie dem
        # Leser zum Annehmen überlassen — eine Schätzung ist keine Messung.
        details = [f"{tr('Herkunft')}: {origin_label(finding.source)}"]
        step = _origin_text(finding.op_id, self._document)
        if step:
            details.append(step)
        details.extend(value_line(key, value) for key, value in finding.values.items())
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
        alerts = counts["error"] + counts["warning"]
        if alerts != self._alerts:
            self._alerts = alerts
            self.alertsChanged.emit(alerts)
        if not any(counts.values()):
            self.summary.setText(tr("Keine Befunde."))
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

        volume = sum(float(mesh.volume) for mesh in meshes)
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
        self.facts.setText(
            f"{closed} · {format_decimal(volume / 1000.0, 1)} cm³ · "
            f"{parts} {tr('Teil') if parts == 1 else tr('Teile')}"
        )
        self.facts.setVisible(True)

    def worst_severity(self, result: EvaluationResult | None) -> str | None:
        if result is None:
            return None
        return result.scene.report.worst_severity

    def _on_activated(self, item: QListWidgetItem) -> None:
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        self.findingActivated.emit(finding)

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
        offers = FINDING_ACTIONS.get(finding.code, ())
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
        picked = cast(QAction | None, menu.exec(self.list.mapToGlobal(position)))
        if picked is None:
            return
        # Die Handler des Fensters arbeiten auf einem ``AppError`` — sie
        # kommen aus dem Fehlerdialog. Ein Befund ist keiner, trägt aber
        # dieselben zwei Angaben, die sie brauchen: den Körper und die Zahlen.
        handlers[chosen[picked].id](as_error(finding))


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
    """
    header = 0
    if isinstance(view, QTreeWidget) and not view.isHeaderHidden():
        head = view.header()
        header = head.height() if head is not None else 0
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
    floor = chrome + MIN_ROWS * row_height
    ceiling = room if room is not None else chrome + MAX_ROWS * row_height
    view.setFixedHeight(max(floor, min(wanted, ceiling)))


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


def _preview_pixels(widget: QWidget) -> int:
    """Wie groß ein Vorschaubild wird — an der Zeilenhöhe, nicht in Pixeln.

    Wer seine Schrift größer stellt, bekommt größere Zeilen; ein Bild in
    fester Größe säße dann in einer Zeile, die doppelt so hoch ist.

    Der Faktor kommt aus dem Bild und nicht aus einer Überlegung: Bei
    Zeilenhöhe mal 1,15 war ein Quader ein Punkt, an dem nichts zu erkennen
    war — und ein Bild, das man nicht erkennt, ist teurer als kein Bild.

    Größer geht trotzdem nicht: Die Karte ist 260 Pixel breit, ein volles
    Kantenmaß nimmt davon gut die Hälfte, und ab Zeilenhöhe mal 1,7 stand
    „Dose Deckel" als „Dose Dec…" da. Ein Name, den man lesen kann, ist mehr
    wert als eine Silhouette, die man erkennt — das Bild bleibt deshalb die
    Wiedererkennung nebenher und wird nie die Auskunft selbst. Eine
    Maßspalte mit Deckel half nicht: Sie war schon am Anschlag.
    """
    return max(int(widget.fontMetrics().height() * 1.2), 18)


def _svg_icon(svg: str, size: int) -> QIcon:
    """Ein SVG als Symbol, scharf auf HiDPI.

    Doppelt gerastert und dann auf die Anzeigegröße gesetzt: Ein Bild in
    genau der Punktgröße franst auf einem skalierten Bildschirm aus.
    """
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return QIcon()
    image = QImage(QSize(size, size) * 2, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.setDevicePixelRatio(2.0)
    return QIcon(QPixmap.fromImage(image))
