"""Der Bausteinkatalog (Bauplan §24.3, §2.6).

„Eine Bibliothek, die man nicht sehen kann, existiert für den Nutzer nicht."
Also ist das ein Fenster mit Bildern: je Baustein eine Kachel aus Vorschaubild
und Titel, rechts daneben, was der gewählte tut und welche Maße er hat. Die
Bilder kommen aus den Bausteinen selbst (§24.3), gerendert beim Öffnen des
Katalogs.

Was eine Kachel sonst noch sagt — nimmt Material weg, eigener Baustein,
Bereichstest offen —, steht als Zeichen in einer Ecke des Bildes, mit Wort in
Kurzhilfe, zugänglicher Beschreibung und Detailspalte (Regel 18, RM-517).

Eigene Bausteine sind als solche gekennzeichnet (§24.5). Der Unterschied
zählt: sie existieren nur auf dieser Maschine, und ein Projekt, das einen
benutzt, lässt sich nicht so weitergeben wie der Rest.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from PySide6.QtCore import QByteArray, QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.knowledge.parts import GROUPS, PARTS
from app.core.knowledge.parts.ops import (
    catalog_operation,
    cuts_by_parameter,
    fitting_places,
    op_name,
)
from app.core.knowledge.parts.preview import SIZE, render
from app.core.knowledge.parts.registry import PartSpec
from app.core.registry.registry import FEATURE_TITLES
from app.core.registry.surfaces import choice_label
from app.i18n import tr
from app.ui.leash import stop_watching_the_dying, weak_slot
from app.ui.palette import ROLES
from app.ui.panels import collapsible, open_section
from app.ui.style import (
    NORMAL,
    SPACE,
    WIDE,
    DialogScrollArea,
    fit_dialog_to_screen,
    make_primary,
)

#: Was den gescheiterten oder fehlenden Bereichstest in Worten anführt (§24.5)
#: — in Detailspalte und Kurzhilfe. Auf der Kachel steht dafür ein Warndreieck.
#: §24.5 verlangt den Warnhinweis am Katalogeintrag, kein Verbot: Der Baustein
#: bleibt wählbar, er trägt nur seine Warnung mit.
RANGE_MARKER = "!"

#: Anzeigegröße des Vorschaubilds in einer Kachel. Gerendert wird weiter in
#: ``SIZE`` — die Reserve zahlt sich auf HiDPI-Bildschirmen aus.
TILE_ICON = 96

#: Breite einer Kachel: breit genug für „Kabeldurchführung mit Zugentlastung"
#: in zwei Zeilen. Die Höhe rechnet :func:`tile_size` aus Bild und genau zwei
#: Titelzeilen — ein längerer Titel endet mit „…" und steht ganz in Kurzhilfe
#: und Detailspalte.
TILE_WIDTH = 164

#: Wie viele Zeilen ein Kacheltitel höchstens bekommt (RM-517).
TITLE_LINES = 2

#: Kantenlänge eines Eckzeichens im Verhältnis zum Vorschaubild.
TILE_MARK_SHARE = 0.27

#: Mindestbreite der Detailspalte. Schmaler wird aus zwei Sätzen eine
#: Wortkolonne.
DETAIL_WIDTH = 220

#: Die Größe, mit der der Katalog aufgeht — kleinste und größte.
#:
#: Eine feste Zahl (980 mal 640) zeigte vier Kacheln von neunzehn; §2.6 will
#: eine Bibliothek, die man *sieht*. Die Kachel selbst ist nicht der Grund:
#: Ihre Breite kommt vom Titel, ihre Höhe von Bild und zwei Titelzeilen.
CATALOG_MIN = (980, 640)
#: Die Höhe steht höher als die Breite es verlangt, seit jede Gruppe ihre
#: eigene Zeile bekommt (:meth:`PartCatalog._stretch_headings`): Sieben
#: Überschriften mit je einer Kachelzeile darunter brauchen mehr Platz als
#: siebzehn Kacheln am Stück, und ein Deckel von 1000 ließ ein Drittel davon
#: unter der Kante.
CATALOG_MAX = (1560, 1200)

#: Wie viel vom freien Bildschirm der Katalog nimmt, wenn er darf.
#:
#: Vier Fünftel und nicht alles: ein Dialog, der den Bildschirm füllt, sieht
#: aus wie ein Fenster, das nicht mehr weggeht, und man verliert den Bezug zu
#: dem, was darunter liegt.
CATALOG_SHARE = 0.8


def catalog_size() -> tuple[int, int]:
    """Wie groß der Katalog aufgeht — nach dem Bildschirm, nicht nach einer Zahl.

    Auf 1920x1080 kommen 1536 mal 864 heraus: sieben Kacheln je Zeile, und
    die größte Gruppe steht damit in einer. Auf einem kleinen Bildschirm bleibt
    es bei den 980 mal 640 von vorher — kleiner darf er nicht werden, sonst
    passt die Detailspalte nicht mehr neben das Raster.

    Ohne Bildschirm (offscreen, in der Suite) gilt die Mindestgröße. Gefragt
    wird über ``screens()`` und nicht über ``primaryScreen()``, aus demselben
    Grund wie in ``splash.py``: die Stubs versprechen dort einen Bildschirm,
    und eine Prüfung auf ``None`` gilt mypy als unerreichbar.
    """
    if not QApplication.screens():
        return CATALOG_MIN
    area = QApplication.primaryScreen().availableGeometry()
    return (
        max(CATALOG_MIN[0], min(int(area.width() * CATALOG_SHARE), CATALOG_MAX[0])),
        max(CATALOG_MIN[1], min(int(area.height() * CATALOG_SHARE), CATALOG_MAX[1])),
    )


MarkKind = Literal["range", "removes", "origin"]


@dataclass(frozen=True, slots=True)
class TileMark:
    """Ein Eckzeichen einer Kachel und das, was es in Worten heißt."""

    kind: MarkKind
    words: str


def tile_marks(spec: PartSpec) -> tuple[TileMark, ...]:
    """Was die Kachel außer Bild und Titel sagt — je Aussage ein Eckzeichen.

    Drei Ecken, drei Aussagen: links oben der offene Bereichstest (§24.5),
    rechts oben „nimmt Material weg", links unten die Herkunft eines Bausteins,
    der nicht mitgeliefert ist (§24.5). Vorher standen sie als Textzeilen
    unter dem Titel, und der Strich vor „nimmt Material weg" las sich als Minus (A22).
    """
    marks: list[TileMark] = []
    warning = _range_warning(spec)
    if warning:
        marks.append(TileMark("range", f"{RANGE_MARKER} {warning}"))
    if spec.subtractive:
        marks.append(TileMark("removes", tr("nimmt Material weg")))
    origin = _origin_words(spec)
    if origin:
        marks.append(TileMark("origin", origin))
    return tuple(marks)


def _origin_words(spec: PartSpec) -> str:
    """Woher ein nicht mitgelieferter Baustein kommt — sonst nichts."""
    if spec.source == "travelled":
        # „Um eine Herkunft mehr" (Konzept §17.1): Der Baustein kam mit einer
        # Projektdatei und gehört ihr — nicht dieser Maschine.
        return tr("mitgereister Baustein")
    if spec.source == "imported":
        return tr("aus Datei hinzugefügt")
    if spec.own:
        return tr("eigener Baustein")
    return ""


def _in_own_library(spec: PartSpec) -> bool:
    """Ob der Baustein als Datei im eigenen Bausteinordner liegt.

    Gespeicherte Rezepte und aus Datei hinzugefügte Bausteine: nur sie lassen
    sich weitergeben, bearbeiten und entfernen. **Nicht** ``PartSpec.own`` —
    das zählt den ``.py``-Baustein mit und den hinzugefügten nicht, und ein
    mitgereister gehört der Projektdatei. Eine Quelle für Weitergabe,
    Verwaltungsknöpfe und den offenen Abschnitt (RM-680).
    """
    return getattr(spec, "source", "") in ("recipe", "imported")


def _own_library_is_empty() -> bool:
    """Ob es noch keinen Baustein im eigenen Bausteinordner gibt (RM-680)."""
    return not any(_in_own_library(spec) for spec in PARTS.all())


def describe(spec: PartSpec) -> str:
    """Die Eckzeichen einer Kachel in Worten, eine Zeile — leer ohne Zeichen."""
    return " · ".join(mark.words for mark in tile_marks(spec))


def tile_tip(spec: PartSpec) -> str:
    """Kurzhilfe und zugängliche Beschreibung einer Kachel.

    Der ganze Titel zuerst — auf der Kachel endet ein langer nach zwei Zeilen
    mit „…" —, dann die Eckzeichen in Worten, dann der Satz des Bausteins.
    """
    return "\n".join(part for part in (str(spec.title), describe(spec), str(spec.doc)) if part)


def tile_size(line_spacing: int) -> QSize:
    """Kachelgröße für Bild und genau :data:`TITLE_LINES` Titelzeilen.

    Die Zugabe unter dem Bild bleibt kleiner als eine Zeile: So passt keine
    dritte Titelzeile mehr hinein, und Qt kürzt die zweite mit „…".
    """
    return QSize(TILE_WIDTH, TILE_ICON + TITLE_LINES * line_spacing + NORMAL + SPACE)


def parts_for_feature(kind: str) -> frozenset[str]:
    """Die Bausteine, die das Register an einer Merkmalsart anbietet.

    Gefragt wird das ``applies_to`` ihrer Operation — dieselbe Auskunft, die
    die Karte der Handlungen liest (``Registry.for_feature``), nicht eine
    zweite Liste (``oberflaeche.md``, „Eine Auskunft, eine Quelle").
    """
    from app.core.knowledge.parts.ops import op_name
    from app.core.registry import REGISTRY

    fitting = {operation.name for operation in REGISTRY.for_feature(kind)}
    return frozenset(spec.name for spec in PARTS.all() if op_name(spec.name) in fitting)


def feature_title(kind: str) -> str:
    """Wie eine Merkmalsart heißt — die Namen des Registers.

    Eine unbekannte Art ist ein Fehler des Aufrufers und kein Fall für eine
    Beschriftung: Ihr Schlüssel stünde sonst im Fenster.
    """
    from app.core.registry.registry import FEATURE_TITLES

    if kind not in FEATURE_TITLES:
        raise ValueError(f"unknown feature kind {kind!r}")
    return str(FEATURE_TITLES[kind])


def marked(picture: QPixmap, marks: Sequence[TileMark], ink: QColor) -> QPixmap:
    """Das Vorschaubild mit seinen Eckzeichen — eine Kopie, das Bild bleibt.

    Gezeichnet statt geschrieben: Ein Zeichen aus der Schrift hängt an der
    Schrift der Plattform, und offscreen misst jede gleich. Die Formen sind
    so gewählt, dass sie ohne Farbe auseinandergehen (Regel 18): Dreieck mit
    Ausrufezeichen, Block mit Bohrung, Stern.
    """
    if not marks:
        return picture
    result = QPixmap(picture)
    width = float(result.width() / max(result.devicePixelRatio(), 1.0))
    height = float(result.height() / max(result.devicePixelRatio(), 1.0))
    side = width * TILE_MARK_SHARE
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for mark in marks:
        if mark.kind == "range":
            _warning_mark(painter, QRectF(0.0, 0.0, side, side))
        elif mark.kind == "removes":
            _removes_mark(painter, QRectF(width - side, 0.0, side, side))
        else:
            _origin_mark(painter, QRectF(0.0, height - side, side, side), ink)
    painter.end()
    return result


def _warning_mark(painter: QPainter, box: QRectF) -> None:
    """Ein Warndreieck mit Ausrufezeichen — die Farbe der Warnung."""
    triangle = QPolygonF(
        [
            QPointF(box.center().x(), box.top() + box.height() * 0.06),
            QPointF(box.right() - box.width() * 0.04, box.bottom() - box.height() * 0.08),
            QPointF(box.left() + box.width() * 0.04, box.bottom() - box.height() * 0.08),
        ]
    )
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(ROLES["warning"]))
    painter.drawPolygon(triangle)
    dark = QColor("#1c2026")
    pen = QPen(dark, box.width() * 0.1)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    x = box.center().x()
    painter.drawLine(
        QPointF(x, box.top() + box.height() * 0.36), QPointF(x, box.top() + box.height() * 0.6)
    )
    painter.drawPoint(QPointF(x, box.top() + box.height() * 0.76))


def _removes_mark(painter: QPainter, box: QRectF) -> None:
    """Ein Block mit Bohrung: Hier wird Material weggenommen."""
    margin = box.width() * 0.06
    inset = box.adjusted(margin, margin, -margin, -margin)
    block = QPainterPath()
    block.addRoundedRect(inset, inset.width() * 0.2, inset.width() * 0.2)
    hole = QPainterPath()
    radius = inset.width() * 0.24
    hole.addEllipse(inset.center(), radius, radius)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(ROLES["removes"]))
    painter.drawPath(block.subtracted(hole))


def _origin_mark(painter: QPainter, box: QRectF, ink: QColor) -> None:
    """Ein Stern: Dieser Baustein gehört nicht zur Lieferung."""
    import math

    centre = box.center()
    outer = box.width() * 0.46
    inner = outer * 0.45
    points = []
    for index in range(10):
        radius = outer if index % 2 == 0 else inner
        angle = -math.pi / 2 + index * math.pi / 5
        points.append(
            QPointF(centre.x() + radius * math.cos(angle), centre.y() + radius * math.sin(angle))
        )
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(ink)
    painter.drawPolygon(QPolygonF(points))


class PartCatalog(QDialog):
    """Bilder, Beschreibungen und ein Suchfeld."""

    partChosen = Signal(str)
    saveRequested = Signal()
    """Den gewählten Ausschnitt als eigenen Baustein ablegen (E4).

    Ein Signal und kein Aufruf: Der Katalog hat kein Dokument und keine
    Sitzung. Was daraus wird, entscheidet das Fenster."""
    shareRequested = Signal()
    """Den gewählten Baustein als lokale Datei exportieren.

    Wie ``saveRequested`` nur ein Ruf und keine Handlung: Welche Datei
    entsteht und wohin sie geschrieben wird, weiß das Fenster."""
    adoptRequested = Signal()
    """Eine lokale Bausteindatei dauerhaft in den Katalog aufnehmen.

    Braucht keine Auswahl — anders als der Export ist das Einlesen
    ohne Vorbedingung, und ein Knopf ohne Vorbedingung wird nicht gesperrt."""
    removeRequested = Signal(str)
    draftRequested = Signal(str)
    """Den gewählten eigenen Baustein als bearbeitbaren Entwurf öffnen (E6).

    Trägt den Namen, weil der Katalog kein Dokument hat: Was aus dem Rezept
    ein Projekt macht, weiß das Fenster — und es fragt vorher, ob das offene
    weg darf."""
    scadRequested = Signal(str)
    """Den gewählten Baustein als OpenSCAD-Quelltext schreiben (§24.1).

    Trägt den Namen, weil der Katalog das Schreiben nicht selbst tut: Wohin die
    Datei geht, fragt das Fenster, und dort liegt auch der Weg zu den aktuellen
    Werten des Bausteins."""
    undoFileRequested = Signal()
    """Die letzte Dateiänderung des Katalogs im Fenster rückgängig machen."""
    showAffectedStepRequested = Signal()
    """Den von der Bausteindatei betroffenen Verlaufsschritt im Fenster zeigen."""

    def __init__(self, parent: QWidget | None = None, *, feature_kind: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Bausteine"))
        self.resize(*catalog_size())

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("Suchen — zum Beispiel Mutter, Magnet, Kabel"))
        self.search.setAccessibleName(tr("Bausteine durchsuchen"))
        self.search.textChanged.connect(self.show_parts)

        # **Nur, was an die gewählte Stelle passt** (:meth:`show_for_feature`):
        # An einer Bohrung sind es fünf Bausteine, nicht neunundvierzig. Die
        # Zeile sagt, dass gefiltert ist, und führt mit einem Klick zu allen —
        # ein Filter, den man nicht sieht, sieht aus wie eine kleine Bibliothek.
        self._feature_kind: str | None = None
        self._fitting: frozenset[str] | None = None
        self.filter_note = QLabel("", self)
        self.filter_note.setWordWrap(True)
        self.show_all = QPushButton(tr("Alle Bausteine zeigen"), self)
        self.show_all.setAutoDefault(False)
        self.show_all.clicked.connect(self._show_every_part)
        self.filter_row = QWidget(self)
        filter_layout = QHBoxLayout(self.filter_row)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(NORMAL)
        filter_layout.addWidget(self.filter_note, stretch=1)
        filter_layout.addWidget(self.show_all)
        self.filter_row.setVisible(False)

        # Import und Weitergabe laufen im Hintergrund. Ihr Ergebnis bleibt im
        # Katalog sichtbar, statt nur für wenige Sekunden in der Statuszeile
        # hinter dem Dialog aufzutauchen. Der Text selbst ist zugleich der
        # zugängliche Name der Zeile.
        self.file_result = QLabel("", self)
        self.file_result.setObjectName("partFileResult")
        self.file_result.setWordWrap(True)
        self.file_result.setVisible(False)
        self.file_undo = QPushButton(tr("Rückgängig"), self)
        self.file_undo.setAutoDefault(False)
        self.file_undo.setAccessibleName(tr("Rückgängig"))
        self.file_undo.setVisible(False)
        self.file_undo.clicked.connect(self.undoFileRequested.emit)
        self.show_affected_step = QPushButton(tr("Im Verlauf zeigen"), self)
        self.show_affected_step.setAutoDefault(False)
        self.show_affected_step.setAccessibleName(tr("Im Verlauf zeigen"))
        self.show_affected_step.setVisible(False)
        self.show_affected_step.clicked.connect(self.showAffectedStepRequested.emit)
        file_result_row = QWidget(self)
        file_result_layout = QHBoxLayout(file_result_row)
        file_result_layout.setContentsMargins(0, 0, 0, 0)
        file_result_layout.addWidget(self.file_result, stretch=1)
        file_result_layout.addWidget(self.show_affected_step)
        file_result_layout.addWidget(self.file_undo)

        # §2.6 will eine Bibliothek, die man sieht. Als Liste mit bildhohen
        # Zeilen zeigte das Fenster zweieinhalb von dreizehn Bausteinen — als
        # Kachelraster steht die ganze Gruppe auf einem Blick da, und die
        # Pfeiltasten laufen in beide Richtungen.
        self.list = QListWidget(self)
        self.list.setObjectName("tileGrid")
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setWrapping(True)
        self.list.setSpacing(NORMAL)
        self.list.setIconSize(QSize(TILE_ICON, TILE_ICON))
        self.list.setWordWrap(True)
        # Ein zu langer Titel endet mit „…" in seiner zweiten Zeile, statt die
        # Kachel aufzublähen; ganz steht er in Kurzhilfe und Detailspalte.
        self.list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.list.itemDoubleClicked.connect(self._chosen)
        # Die Überschriften folgen der Breite der Liste, nicht der des
        # Dialogs: dessen resizeEvent feuert, bevor das Layout der Liste ihre
        # Größe gegeben hat, und die Zeile bliebe eine Kachel breit.
        self.list.installEventFilter(self)
        # Waagerecht wird nie gerollt: das Raster bricht um, und eine Leiste
        # darunter hieße, dass es das nicht tut.
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(self._show_detail)

        # Die Detailspalte erklärt die gewählte Kachel: Satz, Herkunft und alle
        # Maße. Die Kachel trägt Bild und Titel, mehr nicht (RM-517) — die
        # Maßnamen standen dort als zweite Zeile und machten jede Kachel zu
        # einem kleinen Absatz.
        self.detail = QLabel(self)
        self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail.setTextFormat(Qt.TextFormat.RichText)
        self.detail.setMargin(NORMAL)
        self.detail.setMinimumWidth(DETAIL_WIDTH)

        # Der Grund für einen gesperrten Speichern-Knopf steht **sichtbar**
        # über der Knopfzeile, nicht nur im Tooltip — die Detailspalte dieses
        # Dialogs sagt selbst, dass ein Tooltip nur findet, wer weiß, dass er
        # da ist. Leer, solange der Knopf frei ist; angelegt vor der
        # Knopfzeile, weil deren Aufbau ``set_can_save`` bereits ruft.
        self.save_hint = QLabel("", self)
        self.save_hint.setWordWrap(True)
        self.save_hint.setVisible(False)
        self.share_hint = QLabel("", self)
        self.share_hint.setWordWrap(True)
        self.share_hint.setVisible(False)
        # Die Schwester für die andere Hälfte der Knopfzeile: warum gerade
        # nichts eingesetzt werden kann. Ohne sie wählte jemand auf der
        # Startseite einen Baustein, bestätigte — und bekam erst dann
        # „Wählen Sie zuerst ein Objekt": zwei Dialoge für eine Absage, die
        # beim Öffnen schon feststand (Robert, 25.08.2026, über 3d-druck-ce).
        # Was die Detailspalte schon sagt („Wählen Sie links einen Baustein"),
        # steht hier nicht ein zweites Mal (D10).
        self.insert_hint = QLabel("", self)
        self.insert_hint.setWordWrap(True)
        self.insert_hint.setVisible(False)
        # **Ein Satz, der einen Weg nennt, bietet ihn an** (RM-356): In der
        # leeren Szene stand hier „legen Sie einen Grundkörper an“, und der
        # modale Katalog ließ keinen Weg dorthin. Die Knöpfe gibt das Fenster
        # (:meth:`offer_ways`); sichtbar sind sie, solange die Sperre gilt.
        self.way_buttons: dict[str, QPushButton] = {}
        self._way: str | None = None
        self._insert_allowed = True
        self._insert_reason = ""
        self._chosen_kinds: tuple[str, ...] = ()
        self._feature_chosen = True
        """Ob im Objektbaum eine Fläche oder Bohrung gewählt ist.

        Die meisten Bausteine werden an eine solche Stelle gesetzt (alle ohne
        ``standalone``); ohne sie wissen sie weder wohin noch in welche
        Richtung, und die Operation bricht mit „Für diesen Baustein fehlt die
        Stelle, an die er soll" ab. Vorgabe ``True``: Wer die Auskunft nicht
        gibt, bekommt den Katalog wie zuvor."""

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        button_layout = buttons.layout()
        assert button_layout is not None
        button_layout.setSpacing(SPACE)
        # „OK" sagt nicht, was es tut — derselbe Befund, der jedem
        # Operationsdialog seinen handelnden Knopf gegeben hat. Dieser hier
        # setzt den gewählten Baustein in die Szene, also heißt er so: „Einsetzen"
        # wie die Bausteinzeilen des Auswahlfensters, nicht „Einfügen" — das
        # ist das Modell aus einer Datei (C19).
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(tr("Einsetzen"))
            # **Der Akzent war die ganze Zeit da — bestellt hatte ihn
            # niemand.** Qt macht beim ersten ``show()`` den ersten
            # autoDefault-Knopf zum Default, und das ist hier „Einsetzen". Er
            # trug damit die Akzentfarbe, aber nicht die halbfette Schrift,
            # die neben ihr die zweite Kodierung ist (Regel 18).
            # ``make_primary`` macht ihn ausdrücklich zu dem, was er ohnehin
            # war, und rechnet seine Breite gegen die Schrift, mit der er
            # gezeichnet wird.
            #
            # Das ist kein Widerspruch zu dem Absatz darunter: Dort ging es um
            # einen Knopf, der **klickbar** war, ohne etwas zu bewirken. Der
            # Akzent auf einem gesperrten Hauptknopf ist dagegen richtig — ein
            # Dialog ohne akzentuierten Knopf lässt suchen, und gesperrt sieht
            # gesperrt aus.
            make_primary(ok)
        # Er kann nichts einfügen, solange nichts gewählt ist. Vorher stand er
        # in voller Akzentfarbe da, nahm den Klick an, schloss den Dialog — und
        # setzte nichts: ``_accept`` rief ``accept()`` auch ohne Baustein. Ein
        # Knopf, der eine Wirkung verspricht und keine hat, ist die stillste
        # Art, jemanden ratlos zu machen. Warum er nicht kann, steht daneben:
        # die Detailspalte sagt „Wählen Sie einen Baustein".
        self._insert = ok

        # **Der Weg zum eigenen Baustein steht im Katalog und nicht im Menü**
        # (Konzept §16 Schritt 3, Begründung in §18c): Wer ein Teil in die
        # Bibliothek legen will, denkt an die Bibliothek — und die Menüleiste
        # ist die Stelle, die von eigenen Bausteinen ohnehin frei bleibt.
        #
        # Der Knopf schickt nur ein Signal. Was gespeichert wird, weiß das
        # Fenster: Ausschnitt des Verlaufs, eingebettete Quellen, Merkmale des
        # gerechneten Körpers. Der Katalog kennt das Dokument nicht und soll es
        # nicht kennen.
        self.save_part = QPushButton(tr("Auswahl als Baustein speichern …"), self)
        self.save_part.clicked.connect(self.saveRequested.emit)
        self.set_can_save(False, "")

        # **Neben dem Speichern und nicht in einem Menü**, aus demselben
        # Grund: Wer eine lokale Bausteindatei erzeugen will, denkt an die
        # Bibliothek, in der das Teil liegt.
        self.share_part = QPushButton(tr("Baustein als Datei weitergeben …"), self)
        self.share_part.clicked.connect(self.shareRequested.emit)
        self.set_can_share(False, "")

        # **Dasselbe Regal, dritter Weg hinaus** (§24.1): Wer einen
        # OpenSCAD-Ablauf hat, nimmt den Baustein dorthin mit — als Datei, die
        # geschrieben und nie ausgeführt wird (Regel 11). Der Knopf steht neben
        # der Weitergabe, weil er dieselbe Frage beantwortet: „wie kommt dieses
        # Teil hier heraus".
        self.export_scad = QPushButton(tr("Als OpenSCAD-Datei schreiben …"), self)
        self.export_scad.setAccessibleName(tr("Als OpenSCAD-Datei schreiben"))
        self.export_scad.clicked.connect(self._request_scad)
        self.set_can_write_scad(False, "")

        # Immer bedienbar: Zum Einlesen braucht es keinen gewählten Baustein.
        self.adopt_part = QPushButton(tr("Baustein aus Datei hinzufügen …"), self)
        self.adopt_part.clicked.connect(self.adoptRequested.emit)

        # **Der Weg zurück in den Verlauf** (E6): Bis hierher hieß „ändern"
        # neu speichern, und wer das Projekt nicht mehr hatte, aus dem sein
        # Baustein geschnitten war, hatte gar keinen Weg — bei einem
        # eingelesenen Rezept gab es dieses Projekt nie. Der Knopf steht neben
        # dem Entfernen, weil beide dieselbe Voraussetzung haben: ein Baustein,
        # der dem Kunden gehört. Beide sind deshalb unsichtbar, solange einer
        # der eingebauten gewählt ist — ein grauer Knopf an
        # jedem eingebauten Eintrag wäre kein Angebot.
        self.edit_part = QPushButton(tr("Zum Bearbeiten öffnen …"), self)
        self.edit_part.setAccessibleName(tr("Baustein zum Bearbeiten öffnen"))
        # Was der Klick bewirkt, steht am Knopf — er tauscht das offene
        # Projekt, und das ist mehr, als „bearbeiten" vermuten lässt. In Kurzhilfe
        # und Beschreibung, weil je nach Bedienung eine ausfällt (Regel 18).
        opens = tr("Legt die Schritte dieses Bausteins als neues Projekt in das Fenster.")
        self.edit_part.setToolTip(opens)
        self.edit_part.setAccessibleDescription(opens)
        self.edit_part.setVisible(False)
        self.edit_part.clicked.connect(self._request_draft)

        self.remove_part = QPushButton(tr("Aus Bibliothek entfernen"), self)
        self.remove_part.setAccessibleName(tr("Aus Bibliothek entfernen"))
        self.remove_part.setVisible(False)
        self.remove_part.clicked.connect(self._request_removal)

        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        self._button_box = buttons

        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.addWidget(self.list)
        detail_scroll = DialogScrollArea(self)
        detail_scroll.setWidget(self.detail)
        detail_scroll.setMinimumWidth(DETAIL_WIDTH)
        split.addWidget(detail_scroll)
        split.setChildrenCollapsible(False)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)

        management = QWidget(self)
        management_layout = QGridLayout(management)
        management_layout.setContentsMargins(0, NORMAL, 0, 0)
        management_layout.setSpacing(NORMAL)
        actions = (
            self.save_part,
            self.adopt_part,
            self.share_part,
            self.export_scad,
            self.edit_part,
            self.remove_part,
        )
        for index, action in enumerate(actions):
            action.setAutoDefault(False)
            management_layout.addWidget(action, index // 2, index % 2)
        management_layout.addWidget(self.save_hint, 3, 0, 1, 2)
        management_layout.addWidget(self.share_hint, 4, 0, 1, 2)
        # **Offen, solange es keinen eigenen Baustein gibt** (RM-680): Wer noch
        # keinen hat, kommt über *Speichern* und *Hinzufügen* zu einem, und die
        # Sperrgründe daneben sagen, was fehlt (§2.7). Hinter der zugeklappten
        # Kopfzeile (48ffcf145) fand das niemand; in 0.5.1 lag es offen. Danach
        # gilt der Merker (``remember``) — auch, wenn :meth:`_show_detail` den
        # Abschnitt für einen eigenen Baustein geöffnet hat (RM-658).
        self.management_section = collapsible(
            tr("Bausteine verwalten"),
            management,
            open_now=_own_library_is_empty(),
            contents=tr(
                "Eigene Bausteine speichern, aus Datei hinzufügen, weitergeben, "
                "als OpenSCAD schreiben, bearbeiten, entfernen"
            ),
            remember="catalog.manage",
        )
        self._management = management

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(NORMAL)
        layout.addWidget(self.search)
        layout.addWidget(self.filter_row)
        layout.addWidget(file_result_row)
        layout.addWidget(split, stretch=1)
        layout.addWidget(self.management_section)
        # Der Satz erklärt, warum *Einsetzen* gesperrt ist — also steht er über
        # *Einsetzen* und nicht über sechs Verwaltungsknöpfen dazwischen.
        layout.addWidget(self.insert_hint)
        layout.addWidget(buttons)
        previous: QWidget = self.list
        heading = self.management_section.findChild(QToolButton)
        if heading is not None:
            QWidget.setTabOrder(previous, heading)
            previous = heading
        for action in actions:
            QWidget.setTabOrder(previous, action)
            previous = action
        QWidget.setTabOrder(previous, buttons.button(QDialogButtonBox.StandardButton.Ok))
        QWidget.setTabOrder(
            buttons.button(QDialogButtonBox.StandardButton.Ok),
            buttons.button(QDialogButtonBox.StandardButton.Cancel),
        )

        self._previews: dict[str, QPixmap] = {}
        self._blank: QPixmap | None = None
        """Der Platzhalter, einmal gezeichnet — siehe :meth:`_placeholder`."""
        if feature_kind is not None:
            self.show_for_feature(feature_kind)
        else:
            self.show_parts()
        self._show_detail()
        self._rendering = True
        QTimer.singleShot(0, self, self._render_pending)

    # --- content ----------------------------------------------------------------

    def set_can_save(self, can: bool, reason: str = "") -> None:
        """Gibt den Knopf frei — oder sagt daneben, was ihm fehlt.

        Ein Knopf, der eine Wirkung verspricht und keine hat, ist die stillste
        Art, jemanden ratlos zu machen; derselbe Befund, der dem „Einsetzen"
        daneben seine Bedingung gegeben hat. Der Grund kommt vom Fenster, weil
        nur das ihn kennt — kein Ausschnitt gewählt, kein Körper gerechnet.
        Er steht als Zeile über den Knöpfen (das Handbuch verspricht „sagt
        daneben, was ihm fehlt" — ein Tooltip löst das nicht ein); der Tooltip
        bleibt als zweite Kodierung dazu.

        **Und am Knopf selbst**, seit dem 03.09.2026: Wer ihn mit der Tastatur
        anfährt, hört die zugängliche Beschreibung und nicht die Zeile daneben.
        ``set_can_share`` setzte sie seit August, dieser Knopf und das Einsetzen
        blieben beim Tooltip zurück — ein Zwilling, den erst der Wächter über
        alle Dialoge sichtbar gemacht hat (Fund 3d-druck-7f).
        """
        hint = "" if can else reason
        self.save_part.setEnabled(can)
        self.save_part.setToolTip(hint)
        self.save_part.setAccessibleDescription(hint)
        self.save_hint.setText(hint)
        self.save_hint.setVisible(bool(reason) and not can)

    def set_can_share(self, can: bool, reason: str = "") -> None:
        """Ob der gewählte Baustein als Datei exportiert werden kann.

        **Der Grund steht sichtbar und am Knopf**, weil Tooltip und
        Bildschirmleser je nach Bedienung ausfallen können. Ein grau
        gewordener Knopf ohne sichtbaren Grund ist derselbe Fehler wie eine
        gesperrte Operation ohne Grund.
        """
        self.share_part.setEnabled(can)
        hint = "" if can else reason
        self.share_part.setToolTip(hint)
        self.share_part.setAccessibleDescription(hint)
        self.share_hint.setText(hint)
        self.share_hint.setVisible(bool(hint))

    def set_can_insert(self, can: bool, reason: str = "") -> None:
        """Gibt das Einsetzen frei — oder sagt daneben, warum nicht.

        Dieselbe Bauart wie :meth:`set_can_save`, und aus demselben Grund:
        Die Bibliothek ansehen ist auch ohne Modell sinnvoll, nur das
        Einsetzen nicht — es braucht einen Körper, auf den der Baustein
        gesetzt wird. Der Grund kommt vom Fenster, weil nur das die Szene
        und die Auswahl kennt; er steht an Knopf und Hinweiszeile (§2.7),
        und der Doppelklick auf einen Eintrag hält sich an dieselbe Sperre.
        """
        self._insert_allowed = can
        self._insert_reason = "" if can else reason
        self._show_detail()

    def offer_ways(self, ways: Sequence[tuple[str, str]]) -> None:
        """Knöpfe unter der Sperre, die zu einem ersten Körper führen (RM-356).

        Je Weg ein Schlüssel und die Beschriftung, die das Fenster seinem
        Menüeintrag gibt. Sie stehen in der Knopfzeile, direkt unter dem Satz,
        der sie nennt. Ein Klick schließt den Katalog; welcher Weg gewählt
        wurde, sagt danach :meth:`way`, und das Fenster geht ihn — ein
        Operationsdialog oder ein Dateidialog über dem modalen Katalog wäre
        einer, den man nicht bedienen kann.
        """
        for key, label in ways:
            button = QPushButton(label, self)
            button.setAutoDefault(False)
            button.clicked.connect(weak_slot(self, PartCatalog._take_way, key))
            self.way_buttons[key] = button
            self._button_box.addButton(button, QDialogButtonBox.ButtonRole.ActionRole)
        self._show_detail()

    def way(self) -> str | None:
        """Der Weg, über den der Katalog geschlossen wurde — sonst ``None``."""
        return self._way

    def _take_way(self, key: str) -> None:
        self._way = key
        self.reject()

    def set_feature_chosen(self, chosen: bool, kinds: Sequence[str] = ()) -> None:
        """Ob eine Fläche oder Bohrung gewählt ist — die zweite Bedingung.

        ``kinds`` sind die Arten der gewählten Stellen; an ihnen entscheidet
        ``catalog_operation``, ob ein eigenständiger Baustein dort ansetzt oder
        frei entsteht.

        Sie gilt **je Baustein** und nicht für den ganzen Katalog: Ein Teil der
        Bausteine wird an eine Stelle gesetzt, der Rest steht frei
        (``standalone``; wie viele, sagt das Register) und entsteht ohne Stelle
        als eigener Körper. Eine pauschale Sperre nähme den freistehenden den
        Weg, den sie haben.

        Und sie **sperrt nicht, sie sagt es** — anders als die Bedingung des
        Fensters darüber. Ein Baustein lässt sich auch über eine eingetragene
        Position setzen (``x``/``y``/``z``); so machen es die ausgelieferten
        Beispielprojekte, und ein Riegel hier nähme ihnen den Weg. Was fehlte,
        war nicht die Erlaubnis, sondern die Auskunft: Robert bekam am
        29.08.2026 die Absage erst als Fehler **nach** dem Klick — derselbe
        Fall wie am 25.08., nur eine Ebene tiefer (dort war es der fehlende
        Körper, hier die fehlende Stelle daran).
        """
        self._feature_chosen = chosen
        self._chosen_kinds = tuple(kinds) if chosen else ()
        self._show_detail()

    def _insert_state(self, spec: PartSpec | None) -> tuple[bool, str]:
        """Ob sich dieser Baustein einsetzen lässt — und was sonst zu tun ist.

        Zwei Bedingungen übereinander, und nur die erste ist ein Riegel: Ohne
        Szene oder ohne gewählten Körper geht gar nichts. Die zweite ist ein
        Hinweis, weil der Weg über eine eingetragene Position offen bleibt.
        """
        if spec is not None and spec.standalone:
            # Ohne passende Stelle entsteht er als eigener Körper (RM-562,
            # ``catalog_operation``). Wo es einen Körper gäbe, an den er passt,
            # sagt der Satz das vorher, statt ihn still daneben zu legen.
            creates = catalog_operation(spec.name, at=self._chosen_kinds) != op_name(spec.name)
            # Ohne Auskunft über die Art bleibt es beim Katalog wie zuvor.
            told = not self._feature_chosen or bool(self._chosen_kinds)
            if not (creates and told and (spec.at_face or spec.at_hole) and self._insert_allowed):
                return True, ""
            return True, standalone_note(spec, chosen=bool(self._chosen_kinds))
        if not self._insert_allowed:
            return False, self._insert_reason
        if spec is None:
            # **Der leere Grund war einer.** Sperren ohne zu sagen, warum, ist
            # genau das, was Regel 18 ausschließt — und diese Lage ist nicht
            # der Randfall, sondern der Anfang: Der Katalog geht auf, links ist
            # nichts gewählt, und *Einsetzen* stand grau und wortlos da. Wer im
            # Suchfeld etwas tippt, das nichts trifft, landet wieder hier.
            # Gefunden vom Wächter über alle Dialoge (3d-druck-7f, 03.09.2026).
            return False, detail(None)
        if (spec.at_hole or spec.at_face) and not self._feature_chosen:
            return True, tr(
                "Dieser Baustein wird an eine Fläche oder Bohrung gesetzt. "
                "Wählen Sie eine im Objektbaum, oder tragen Sie im nächsten "
                "Dialog eine Position ein."
            )
        return True, ""

    def refresh(self) -> None:
        """Die Liste neu aus dem Register — die Suche bleibt, wie sie steht.

        Gerufen, wenn ein eigener Baustein gespeichert wurde. Zwei Fehler
        saßen an dieser Stelle, beide am 25.08.2026 im echten Fenster
        gefunden: ``saved`` trägt den **Namen** des Rezepts, und direkt an
        ``show_parts`` verbunden wurde er zum Suchtext — der Katalog zeigte
        nur noch den neuen Baustein, bei leerem Suchfeld. Ein Slot ohne
        Parameter kann einen Namen nicht als Suche missverstehen.

        Und die Bilderkette läuft wieder an: Sie endet, sobald alle Bilder da
        sind — ein Baustein, der erst danach dazukommt, bliebe sonst ohne
        Vorschau.
        """
        self.show_parts(self.search.text())
        if self._rendering:
            QTimer.singleShot(0, self, self._render_pending)

    def show_file_result(
        self,
        text: str,
        *,
        part_name: str | None = None,
        can_undo: bool = False,
        can_show_affected_step: bool = False,
    ) -> None:
        """Zeigt ein Dateiergebnis und, wenn möglich, den betroffenen Baustein.

        Ein zuvor gesetzter Suchbegriff darf einen frisch hinzugefügten
        Baustein nicht unsichtbar machen. In diesem Fall wird die Suche
        geleert, die Liste neu aufgebaut und der Eintrag ausgewählt. Die
        Datei wird dabei nie still in die Szene eingesetzt.
        """

        self.file_result.setText(text)
        self.file_result.setAccessibleName(text)
        self.file_result.setVisible(bool(text))
        self.file_undo.setVisible(bool(text) and can_undo)
        self.file_undo.setEnabled(bool(text) and can_undo)
        self.show_affected_step.setVisible(bool(text) and can_show_affected_step)
        self.show_affected_step.setEnabled(bool(text) and can_show_affected_step)
        if not part_name:
            return

        item = self._item_named(part_name)
        if item is None:
            if self.search.text():
                self.search.clear()
            else:
                self.refresh()
            item = self._item_named(part_name)
        if item is None:
            return
        self.list.setCurrentItem(item)
        self.list.scrollToItem(item)

    def _item_named(self, name: str) -> QListWidgetItem | None:
        """Den sichtbaren Katalogeintrag zu einer internen Bausteinkennung."""

        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == name:
                return item
        return None

    def invalidate_preview(self, name: str) -> None:
        """Ein entferntes oder wiederhergestelltes Rezept neu zeichnen lassen."""

        self._previews.pop(name, None)
        if self._rendering:
            QTimer.singleShot(0, self, self._render_pending)

    def show_for_feature(self, kind: str | None) -> None:
        """Nur die Bausteine zeigen, die an diese Merkmalsart passen — oder alle.

        ``kind`` ist eine Merkmalsart des Registers (``hole``, ``face``, …);
        gezeigt wird, wessen Operation sie in ``applies_to`` trägt
        (:func:`parts_for_feature`). ``None`` hebt den Filter auf. Die Suche
        bleibt stehen und gilt zusätzlich.
        """
        title = feature_title(kind) if kind is not None else ""
        self._feature_kind = kind
        self._fitting = parts_for_feature(kind) if kind is not None else None
        self.filter_note.setText(tr("Passend für: {kind}", kind=title) if kind else "")
        self.filter_row.setVisible(kind is not None)
        self.show_parts(self.search.text())

    def _show_every_part(self) -> None:
        """*Alle Bausteine zeigen* hebt den Merkmalsfilter auf.

        Eine Methode statt eines Lambdas: Am eigenen Kind hielte es den Katalog
        stark (``wartezeit.md``, „Ein Rückruf an ein eigenes Kind hält schwach“).
        """
        self.show_for_feature(None)

    def feature_kind(self) -> str | None:
        """Nach welcher Merkmalsart gerade gefiltert wird — sonst ``None``."""
        return self._feature_kind

    def show_parts(self, text: str = "") -> None:
        """Füllt die Liste, gruppiert wie der Katalog gruppiert."""
        self.list.clear()
        wanted = PARTS.search(text) if text.strip() else PARTS.all()
        fitting = self._fitting
        if fitting is not None:
            wanted = tuple(spec for spec in wanted if spec.name in fitting)
        by_group: dict[str, list[PartSpec]] = {}
        for spec in wanted:
            by_group.setdefault(spec.group, []).append(spec)

        for group, title in GROUPS.items():
            entries = by_group.get(group)
            if not entries:
                continue
            heading = QListWidgetItem(str(title))
            heading.setFlags(Qt.ItemFlag.NoItemFlags)
            font = QFont(heading.font())
            font.setBold(True)
            heading.setFont(font)
            # Links, nicht mittig: das Kachelraster zentriert seine
            # Beschriftungen, und über einer Zeile voller Breite landete die
            # Überschrift damit in der Bildmitte — bei einer Gruppe aus einem
            # Baustein einen halben Bildschirm neben ihm. Sie gehört an den
            # Anfang dessen, was sie überschreibt.
            heading.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.list.addItem(heading)
            for spec in entries:
                self.list.addItem(self._item(spec))
        if not self.list.count() and (text.strip() or fitting is not None):
            # Ein leeres Raster sagt nicht, ob nichts passt oder ob die Suche
            # hängt — und die Detailspalte daneben forderte weiter auf, einen
            # Baustein zu wählen, den es hier nicht gibt.
            nothing = QListWidgetItem(
                tr("Kein Baustein passt zu „{term}“.").format(term=text.strip())
                if text.strip()
                else tr("Für diese Stelle gibt es keinen passenden Baustein.")
            )
            nothing.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(nothing)
        self._stretch_headings()
        self._show_detail()

    def _stretch_headings(self) -> None:
        """Eine Überschrift nimmt die ganze Zeile.

        Im Raster wäre sie sonst eine Kachel unter vielen, und die Gruppe
        begänne irgendwo in der Zeilenmitte. Die volle Breite erzwingt den
        Umbruch davor und danach — das ist die ganze Abschnittslogik.

        **Und ein ``setSizeHint`` allein tut das nicht.** Der Kachelmodus
        rechnet seine Zeilen einmal beim Einfügen und danach nicht mehr; eine
        Breite, die hinterher kommt, wird gespeichert und nicht angewandt. Zu
        sehen war es erst, als der Dialog breiter aufging: „Verbindungen",
        „Einlegeteile" und „Mechanik" standen nebeneinander in der obersten
        Zeile, jede über fremden Kacheln, und die Gruppen lagen ineinander.
        ``doItemsLayout`` rechnet die Zeilen neu — aber nur, wenn sich wirklich
        etwas geändert hat, sonst stößt jede Größenänderung ein Layout an, das
        die Rollleiste ein- und ausblendet und sich damit selbst wieder ruft.
        """
        width = max(self.list.viewport().width() - 2 * self.list.spacing(), TILE_WIDTH)
        height = self.list.fontMetrics().height() + 10
        changed = False
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) is None:
                wanted = QSize(width, height)
                if item.sizeHint() != wanted:
                    item.setSizeHint(wanted)
                    changed = True
        if changed:
            self.list.doItemsLayout()

    def showEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Die Überschriften stehen, sobald der Dialog steht.

        Über den Resize-Filter allein geschieht das erst, wenn der Zeitgeber
        drankommt — und bis dahin liegen die Gruppen für einen Moment
        ineinander. Auf einem schnellen Rechner ist das ein Zucken, auf einem
        langsamen der erste Eindruck, und in der CI unter Xvfb kam es so spät,
        dass ``test_every_group_starts_its_own_row`` es nicht mehr sah: Die
        Zeilen dort werden über einen echten X-Server zugestellt und nicht
        wie bei ``offscreen`` sofort.

        Hier synchron und ohne Umweg — die Breite steht, sobald das Fenster
        steht. Was danach noch wandert (der Nutzer zieht das Fenster größer),
        holt der Filter unten nach.
        """
        super().showEvent(event)
        fit_dialog_to_screen(self)
        self._stretch_headings()

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qt gibt den Namen
        if stop_watching_the_dying(self, watched, event):
            return False
        if watched is self.list and event.type() == QEvent.Type.Resize:
            # Ein Filter sieht das Ereignis vor dem Ziel — der Viewport hat
            # hier noch die alte Breite. Erst nach der Verarbeitung messen.
            QTimer.singleShot(0, self, self._stretch_headings)
        handled: bool = super().eventFilter(watched, event)
        return handled

    def _item(self, spec: PartSpec) -> QListWidgetItem:
        """Eine Kachel: Bild mit Eckzeichen, darunter der Titel in höchstens zwei Zeilen.

        **Oben bündig** (RM-517): Qt setzt den Titel sonst senkrecht mittig in
        den Raum unter dem Bild, und in einer Reihe aus ein- und zweizeiligen
        Titeln sprangen die ersten Zeilen um eine halbe Zeile. Name, Eckzeichen
        und Satz hören Bildschirmleser über die Rollen der Zeile.
        """
        title = str(spec.title)
        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, spec.name)
        item.setIcon(self._preview(spec))
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        tip = tile_tip(spec)
        item.setToolTip(tip)
        item.setData(Qt.ItemDataRole.AccessibleTextRole, title)
        item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, tip)
        item.setSizeHint(tile_size(self.list.fontMetrics().lineSpacing()))
        return item

    def _preview(self, spec: PartSpec) -> Any:
        """Das Vorschaubild, wenn es schon da ist — sonst ein Platzhalter.

        Jedes Bild wird aus dem Baustein gerechnet (§24.3). Alle beim Öffnen
        nacheinander zu rendern hieß: der Katalog geht auf, wenn das letzte
        fertig ist, und bis dahin hängt das Fenster. Jetzt füllen sie sich
        nach, und die Liste ist sofort lesbar — die Beschreibung daneben steht
        ohnehin von Anfang an.

        **Bis dahin steht ein Platzhalter und nicht nichts.** Gemessen am
        30.08.2026: Nach einer halben Sekunde trägt **eine** von 27 Kacheln
        ihr Bild, nach zwei Sekunden alle. In dieser halben Sekunde sah der
        Katalog aus wie eine Textliste — und §2.6 begründet ihn gerade damit,
        dass ein räumliches Teil als Textzeile die schlechtere Darstellung
        sei. Ein leeres Icon ist außerdem nicht neutral: Qt setzt den Titel
        ohne Bild anders, und die Grundlinien fluchten erst, wenn alle
        Renderings da sind.

        **Ein Balken wäre hier falsch.** ``wartezeit.md`` verlangt ihn ab zwei
        Sekunden; die Kette bleibt darunter, und ein Fortschrittsbalken für
        eine halbe Sekunde ist Lärm. Der Platzhalter sagt dasselbe leiser: Er
        hält den Platz, den das Bild bekommen wird.
        """
        from PySide6.QtGui import QIcon

        found = self._previews.get(spec.name)
        picture = found if found is not None else self._placeholder()
        return QIcon(marked(picture, tile_marks(spec), self._ink()))

    def _ink(self) -> QColor:
        """Die Schriftfarbe des Katalogs — für Platzhalter und Herkunftsstern."""
        return QColor(self.palette().color(self.foregroundRole()))

    def _placeholder(self) -> Any:
        """Die leise Fläche, die ein Vorschaubild vertritt, bis es da ist.

        Einmal gebaut und wiederverwendet: 27 gleiche Bilder je Katalog wären
        27 Zeichnungen desselben Rechtecks.

        Gezeichnet wird ein gerundeter Umriss in der Randfarbe des Themas —
        kein Symbol und kein Fragezeichen. Er soll sagen „hier kommt ein
        Bild", nicht „hier fehlt etwas": Das Bild kommt ja, und zwar in
        Millisekunden.
        """
        if self._blank is not None:
            return self._blank

        size = _icon_size()
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # **Aus der Palette und nicht aus der Thementabelle.** Der Katalog
        # kennt seinen Themennamen nicht; die Textfarbe des Widgets kennt ihn
        # immer und folgt einem Themenwechsel ohne Zutun.
        edge = self._ink()
        # Halb durchsichtig: Der Platzhalter ist eine Ahnung und keine Aussage.
        edge.setAlpha(70)
        painter.setPen(QPen(edge, 1.5))
        width = float(size.width())
        height = float(size.height())
        outline = QPainterPath()
        outline.addRoundedRect(
            QRectF(width * 0.14, height * 0.14, width * 0.72, height * 0.72),
            width * 0.08,
            width * 0.08,
        )
        painter.drawPath(outline)
        painter.end()
        self._blank = pixmap
        return pixmap

    def _render_pending(self) -> None:
        """Rendert das nächste fehlende Bild und reiht sich neu ein.

        Eines je Durchlauf der Ereignisschleife: das Fenster bleibt zwischen
        den Bildern bedienbar, und wer den Katalog gleich wieder schließt,
        hat nicht auf achtzehn Rechnungen gewartet.
        """
        if not self._rendering:
            # Losgelassen, während die Kette lief. Ohne diese Zeile reiht sich
            # der Zeitgeber weiter ein, und jede eingereihte gebundene Methode
            # hält den Katalog am Leben — zehn losgelassene überlebten alle
            # zehn, und ``gc.get_referrers`` nannte genau sie.
            return
        missing = next((spec for spec in PARTS.all() if spec.name not in self._previews), None)
        if missing is None:
            return

        image = render(missing, edges=True)
        pixmap = QPixmap(_icon_size())
        pixmap.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(QByteArray(image.svg.encode("utf-8")))
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self._previews[missing.name] = pixmap

        self._refresh_icon(missing.name)
        QTimer.singleShot(0, self, self._render_pending)

    def release(self) -> None:
        """Die Vorschau-Kette anhalten.

        Derselbe Name wie an den Fenstern, die Arbeiter halten, und aus
        demselben Grund: Es gibt zwei Wege, einen Katalog loszuwerden —
        schließen und wegräumen —, und der zweite kam an der laufenden Kette
        vorbei. ``QTimer.singleShot(0, self, self._render_pending)`` reiht eine
        **gebundene** Methode ein, und die hält ihr Objekt; solange die Kette
        sich selbst neu einreiht, wird der Katalog nie freigegeben.
        """
        self._rendering = False

    def _refresh_icon(self, name: str) -> None:
        """Hängt ein fertiges Bild an seine Zeile, ohne die Liste neu zu bauen —
        ein Neuaufbau würde die Auswahl und die Bildlaufposition mitnehmen.
        """
        spec = next((entry for entry in PARTS.all() if entry.name == name), None)
        if spec is None or name not in self._previews:
            return
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == name:
                item.setIcon(self._preview(spec))
                return

    def _share_state(self, spec: PartSpec | None) -> tuple[bool, str]:
        """Ob dieser Baustein als lokale Datei exportiert werden kann.

        Eigene und zuvor importierte Rezepte liegen als geprüfte Datei vor.
        Ein eingebauter Baustein kommt aus Python und hat keine solche Datei.
        Ein mit einer Projektdatei gereistes Rezept bleibt an deren Herkunft
        gebunden und wird nicht still in eine eigenständige Datei umgedeutet.
        """
        if spec is None:
            # Ohne eigenen Baustein steht dieser Satz vorn im offenen Abschnitt
            # (RM-680); „wählen Sie einen" schickte zu einem eingebauten und
            # damit in die nächste Absage.
            if _own_library_is_empty():
                return False, tr(
                    "Speichern Sie zuerst einen eigenen Baustein, um ihn weiterzugeben."
                )
            return False, tr("Wählen Sie einen Baustein, den Sie als Datei weitergeben möchten.")
        if getattr(spec, "source", "") == "travelled":
            return False, tr(
                "Dieser Baustein gehört zur geöffneten Projektdatei. Speichern Sie ihn "
                "zuerst als eigenen Baustein, um ihn weiterzugeben."
            )
        if not _in_own_library(spec):
            return False, tr(
                "Eingebaute Bausteine sind bereits in Solidon enthalten. Speichern Sie "
                "zuerst einen eigenen Baustein, um ihn weiterzugeben."
            )
        return True, ""

    def _show_detail(self) -> None:
        """Was rechts steht, folgt der Auswahl links — und der Knopf auch.

        Die Hinweiszeile wird **hier** geschrieben und nicht in
        :meth:`set_can_insert`: Ihr Text hängt am gewählten Baustein, und der
        wechselt mit jedem Klick in der Liste.
        """
        name = self.chosen()
        spec = next((entry for entry in PARTS.all() if entry.name == name), None)
        shown = detail(spec)
        self.detail.setText(shown)
        allowed, reason = self._insert_state(spec)
        if self._insert is not None:
            self._insert.setEnabled(spec is not None and allowed)
            self._insert.setToolTip(reason)
            # Dieselbe Auskunft für den, der den Knopf anfährt statt ihn
            # anzusehen — siehe :meth:`set_can_save`.
            self._insert.setAccessibleDescription(reason)
        # **Ein Leertext, nicht zwei** (D10): Ohne Auswahl sagt die
        # Detailspalte, was zu tun ist; dieselbe Zeile über dem Knopf wäre
        # derselbe Satz ein zweites Mal. Knopf und Bildschirmleser
        # bekommen ihn trotzdem (darüber).
        below = "" if reason == shown else reason
        self.insert_hint.setText(below)
        self.insert_hint.setVisible(bool(below))
        # Die Wege zu einem ersten Körper gehören zur Sperre der leeren Szene:
        # Ein freistehender Baustein braucht keinen, dort stünden sie umsonst.
        blocked = not self._insert_allowed and not (spec is not None and spec.standalone)
        for button in self.way_buttons.values():
            button.setVisible(blocked)
        # Derselbe Wechsel entscheidet über den zweiten Knopf. **Hier und
        # nicht in einem eigenen Signalpfad**: Der Zustand hängt an genau
        # derselben Auswahl, und zwei Stellen, die dieselbe Frage
        # beantworten, laufen auseinander.
        self.set_can_share(*self._share_state(spec))
        # **Und der dritte, mit einer weiteren Bedingung als die Weitergabe.**
        # Weitergeben kann nur, wer ein Rezept ist; als OpenSCAD schreiben kann
        # jeder Baustein, denn `to_scad` rechnet die Geometrie aus derselben
        # Funktion wie die Anwendung. Gebraucht wird allein eine Auswahl.
        self.set_can_write_scad(
            spec is not None, tr("Wählen Sie zuerst einen Baustein aus der Bibliothek.")
        )
        own = spec is not None and _in_own_library(spec)
        self.remove_part.setVisible(own)
        # Dieselbe Bedingung, und trotzdem eine eigene Zeile: Entfernen und
        # Bearbeiten sind zwei Handlungen, und die nächste Voraussetzung, die
        # eine von beiden bekommt, gehört dann an ihre Stelle.
        self.edit_part.setVisible(own)
        if own:
            # **Ein eigener Baustein klappt seine Verwaltung auf.** Bearbeiten,
            # Weitergeben und Entfernen gibt es nur an ihm, und seit dem
            # eingeklappten Abschnitt (48ffcf145) standen sie unter einer
            # Kopfzeile, die niemand öffnet — in 0.5.1 lagen sie offen. Ein
            # eingebauter Baustein lässt den Abschnitt, wie der Kunde ihn hat.
            open_section(self._management)

    # --- choosing ---------------------------------------------------------------

    def chosen(self) -> str | None:
        item = self.list.currentItem()
        value: str | None = item.data(Qt.ItemDataRole.UserRole) if item else None
        return value

    def _chosen(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        spec = next((entry for entry in PARTS.all() if entry.name == name), None)
        if name and self._insert_state(spec)[0]:
            self.partChosen.emit(name)
            self.accept()

    def _accept(self) -> None:
        name = self.chosen()
        spec = next((entry for entry in PARTS.all() if entry.name == name), None)
        if name and self._insert_state(spec)[0]:
            self.partChosen.emit(name)
            self.accept()

    def _request_removal(self) -> None:
        """Die sichtbare lokale Auswahl ohne Rückfrage weiterreichen."""

        name = self.chosen()
        if name:
            self.removeRequested.emit(name)

    def _request_scad(self) -> None:
        """Den gewählten Baustein als OpenSCAD-Quelltext anfordern."""

        name = self.chosen()
        if name:
            self.scadRequested.emit(name)

    def _request_draft(self) -> None:
        """Den gewählten eigenen Baustein zum Bearbeiten anfordern (E6)."""

        name = self.chosen()
        if name:
            self.draftRequested.emit(name)

    def set_can_write_scad(self, can: bool, reason: str = "") -> None:
        """Ob der gewählte Baustein als OpenSCAD-Datei geschrieben werden kann.

        Dieselbe Bauart wie :meth:`set_can_share` — der Grund steht am Knopf,
        in der Statuszeile und in der zugänglichen Beschreibung, weil je nach
        Bedienung eine der drei ausfällt (Regel 18). Ein eigener Hinweistext
        daneben steht hier nicht: Der Fall ist derselbe wie bei der Weitergabe
        („kein Baustein gewählt"), und zwei Zeilen mit demselben Satz
        untereinander sind eine zu viel.
        """
        hint = "" if can else reason
        self.export_scad.setEnabled(can)
        self.export_scad.setToolTip(hint)
        self.export_scad.setAccessibleDescription(hint)


def _range_warning(spec: PartSpec) -> str:
    """Der §24.5-Satz zum Bereichstest — oder nichts.

    **Ein mitgelieferter Baustein bekommt ihn, wenn sein Nachweis fehlt.** Bis
    zum 22.09.2026 stand hier, er werde „in der Suite über seinen ganzen
    Bereich gefahren", und die Warnung blieb für ihn aus. Der Lauf war am
    03.09.2026 aus der Suite gefallen, acht Bausteine waren nie gefahren
    worden, und der Katalog sagte trotzdem nichts. Heute fragt er den
    eingecheckten Nachweis (``parts.range_proof``): Passt er zum Stand des
    Bausteins, schweigt die Warnung; ist der Baustein seither geändert, sagt
    sie es; hielt eine Ecke nicht, auch das.

    Für alle anderen Quellen heißt ``range_passed`` ``None``, dass der Test nie
    lief — eine von Hand kopierte Datei etwa —, und ``False``, dass an den
    Grenzen kein brauchbarer Körper herauskam.

    **``user`` fehlte hier, und das war die Quelle, um die §24.5 geht.** Der
    Abschnitt heißt „Eigene Bausteine" und meint die ``.py``-Dateien aus dem
    Nutzerverzeichnis; sein letzter Satz lautet „Dieselben Tests gelten; ohne
    bestandenen Parameterbereichstest erscheint ein Warnhinweis im Katalog".
    Aufgezählt wird deshalb, wovon ausgenommen wird, statt wofür es gilt: Die
    Liste der Quellen wächst, und eine neue soll den Hinweis erben und nicht
    stillschweigend verlieren.
    """
    if spec.source == "shipped":
        from app.core.knowledge.parts import range_proof

        state = range_proof.status(spec)
        if state == "proven":
            return ""
        if state == "failed":
            return tr("an den Grenzen kam kein brauchbarer Körper heraus")
        return tr("der Bereichstest passt nicht mehr zum Stand dieses Bausteins")
    if spec.range_passed is True:
        return ""
    if spec.range_passed is False:
        return tr("an den Grenzen kam kein brauchbarer Körper heraus")
    return tr("der Bereichstest ist für diesen Baustein nie gelaufen")


def standalone_note(spec: PartSpec, *, chosen: bool) -> str:
    """Der Satz über *Einsetzen*, wenn ein eigenständiger Baustein frei entsteht.

    Ist eine Stelle gewählt, die nicht passt, nennt er die passende Art —
    eine Schraube setzt an einer Bohrung an, an einer Fläche entsteht sie frei
    (Review M3). Lässt der Erzeuger eine abtragende Wahl weg, sagt er, welche
    Form bleibt: Der *Passstift und Passbohrung* entsteht frei nur als Stift.
    """
    if chosen:
        fits = ", ".join(str(FEATURE_TITLES.get(kind, kind)) for kind in fitting_places(spec.name))
        text = str(
            tr("Passende Stelle: {fits}. An der gewählten entsteht er als eigener Körper.").format(
                fits=fits
            )
        )
    else:
        text = str(
            tr(
                "Ohne passende Stelle entsteht er als eigener Körper. Wählen Sie im "
                "Objektbaum die Stelle, an der er ansetzen soll."
            )
        )
    cutting = cuts_by_parameter(spec.params)
    if cutting is not None:
        kept = next(entry.default for entry in spec.params.spec() if entry.name == cutting[0])
        form = str(tr("Als eigener Körper entsteht nur die Form „{form}“.")).format(
            form=choice_label(str(kept))
        )
        text = f"{text} {form}"
    return text


def detail(spec: PartSpec | None) -> str:
    """Was die Detailspalte über den gewählten Baustein sagt.

    Die Kachel trägt so viel, wie auf eine Kachel passt; alles Weitere gehört
    daneben und nicht in einen Tooltip, den man erst findet, wenn man weiß,
    dass er da ist.
    """
    if spec is None:
        return tr("Wählen Sie links in der Liste einen Baustein.")

    # Maskiert, denn die Spalte ist RichText und Titel wie Beschreibung sind
    # bei Rezepten Kundeneingaben — und mitgereiste kommen aus fremden
    # Dateien: „<b>Halter" zerrisse sonst die Anzeige, statt dazustehen
    # (Fund des Gesamtreviews vom 25.08.2026).
    from html import escape

    lines = [f"<b>{escape(str(spec.title))}</b>", "", escape(str(spec.doc)), ""]
    if spec.subtractive:
        lines.append(tr("nimmt Material weg"))
    if spec.own:
        lines.append(tr("eigener Baustein"))
    if spec.source == "travelled":
        lines.append(tr("mitgereister Baustein — kam mit einer Projektdatei und bleibt bei ihr"))
    if spec.source == "imported":
        # Eine lokal importierte Datei trägt eine eng begrenzte
        # Herkunftsquittung: Prüfsumme der exakten Eingangsbytes und
        # Importzeit, aber keinen lokalen Pfad und keine erfundene
        # Veröffentlichungsquelle.
        lines.append(
            tr("aus Datei hinzugefügt — Zeitpunkt und eindeutige Dateikennung sind gespeichert")
        )
    warning = _range_warning(spec)
    if warning:
        lines.append(f"<b>{RANGE_MARKER}</b> {warning}")
    else:
        # Die Zusage steht da, wo sie eingelöst ist — und nur dort.
        lines.append(tr("über den ganzen Maßbereich geprüft"))
    lines.append("")

    lines.append(f"<b>{tr('Parameter')}</b>")
    for entry in spec.params.spec():
        unit = f" [{escape(str(entry.unit))}]" if entry.unit else ""
        lines.append(f"· {escape(str(entry.title))}{unit}")
    return "<br>".join(lines)


def _icon_size() -> Any:
    from PySide6.QtCore import QSize

    return QSize(SIZE, SIZE)
