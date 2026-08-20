"""Der Bausteinkatalog (Bauplan §24.3, §2.6).

„Eine Bibliothek, die man nicht sehen kann, existiert für den Nutzer nicht."
Also ist das ein Fenster mit Bildern, einer kurzen Beschreibung und den zwei
wichtigsten Parametern jedes Bausteins — und die Bilder kommen aus den
Bausteinen selbst (§24.3), gerendert beim Öffnen des Katalogs.

Eigene Bausteine sind als solche gekennzeichnet (§24.5). Der Unterschied
zählt: sie existieren nur auf dieser Maschine, und ein Projekt, das einen
benutzt, lässt sich nicht so weitergeben wie der Rest.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QByteArray, QEvent, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.core.knowledge.parts import GROUPS, PARTS
from app.core.knowledge.parts.preview import SIZE, render
from app.core.knowledge.parts.registry import PartSpec
from app.i18n import tr
from app.ui.style import NORMAL

#: Wie viele Parameter ein Katalogeintrag zeigt. §24.3 verlangt die zwei
#: wichtigsten — und das sind die zwei zuerst deklarierten, denn eine
#: Deklaration wird in der Reihenfolge geschrieben, in der jemand über den
#: Baustein nachdenkt.
SHOWN_PARAMETERS = 2

OWN_MARKER = "*"

#: Was „nimmt Material weg" auf einer Kachel anschreibt. Vorher trug das allein
#: die Farbe des Vorschaubilds — orange subtraktiv, grau additiv, ohne Legende
#: (Regel 18). Ein Minuszeichen und ein Wort sagen es auch dem, der die beiden
#: Farben nicht unterscheidet.
SUBTRACTIVE_MARKER = "−"

#: Anzeigegröße des Vorschaubilds in einer Kachel. Gerendert wird weiter in
#: ``SIZE`` — die Reserve zahlt sich auf HiDPI-Bildschirmen aus.
TILE_ICON = 96

#: Grundfläche einer Kachel: breit genug für „Schraubenloch mit Senkung" in
#: zwei Zeilen, hoch genug für Bild, Titel und die zwei Parameter darunter.
TILE_WIDTH = 164
TILE_HEIGHT = 190

#: Mindestbreite der Detailspalte. Schmaler wird aus zwei Sätzen eine
#: Wortkolonne.
DETAIL_WIDTH = 220

#: Die Größe, mit der der Katalog aufgeht — kleinste und größte.
#:
#: Es stand eine Zahl da, 980 mal 640, und die galt auf jedem Bildschirm. Bei
#: 24 Einträgen zeigte sie **vier Kacheln von neunzehn**: die Rasterfläche war
#: 718 mal 562, also vier je Zeile und zweieinhalb Zeilen, und der Rollbalken
#: hatte 1240 Pixel Weg. §2.6 will eine Bibliothek, die man *sieht*; vier von
#: neunzehn ist eine Liste, durch die man sich arbeitet.
#:
#: Die Kachel selbst ist nicht der Grund, obwohl das Verhältnis danach aussieht
#: (164 mal 190 für ein 96er Bild): Ihre Breite kommt vom Text — „Schraubenloch
#: mit Senkung" braucht zwei Zeilen —, und ihre Höhe von Bild plus vier
#: Textzeilen. Wer sie schrumpft, schneidet Titel ab.
CATALOG_MIN = (980, 640)
CATALOG_MAX = (1560, 1000)

#: Wie viel vom freien Bildschirm der Katalog nimmt, wenn er darf.
#:
#: Vier Fünftel und nicht alles: ein Dialog, der den Bildschirm füllt, sieht
#: aus wie ein Fenster, das nicht mehr weggeht, und man verliert den Bezug zu
#: dem, was darunter liegt.
CATALOG_SHARE = 0.8


def catalog_size() -> tuple[int, int]:
    """Wie groß der Katalog aufgeht — nach dem Bildschirm, nicht nach einer Zahl.

    Auf 1920x1080 kommen 1536 mal 864 heraus: sieben Kacheln je Zeile, vier
    Zeilen, alle neunzehn auf einen Blick. Auf einem kleinen Bildschirm bleibt
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


class PartCatalog(QDialog):
    """Bilder, Beschreibungen und ein Suchfeld."""

    partChosen = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Bausteine"))
        self.resize(*catalog_size())

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("Suchen — zum Beispiel Mutter, Magnet, Kabel"))
        self.search.setAccessibleName(tr("Bausteine durchsuchen"))
        self.search.textChanged.connect(self.show_parts)

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
        self.list.itemDoubleClicked.connect(self._chosen)
        # Die Überschriften folgen der Breite der Liste, nicht der des
        # Dialogs: dessen resizeEvent feuert, bevor das Layout der Liste ihre
        # Größe gegeben hat, und die Zeile bliebe eine Kachel breit.
        self.list.installEventFilter(self)
        # Waagerecht wird nie gerollt: das Raster bricht um, und eine Leiste
        # darunter hieße, dass es das nicht tut.
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(lambda *_: self._show_detail())

        # Die Detailspalte erklärt die gewählte Kachel in zwei Sätzen. Eine
        # Kachel trägt so viel, wie auf eine Kachel passt; alles Weitere stand
        # vorher in einem Tooltip, den man erst findet, wenn man weiß, dass er
        # da ist.
        self.detail = QLabel(self)
        self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail.setTextFormat(Qt.TextFormat.RichText)
        self.detail.setMargin(NORMAL)
        self.detail.setMinimumWidth(DETAIL_WIDTH)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        # „OK" sagt nicht, was es tut — derselbe Befund, der jedem
        # Operationsdialog seinen handelnden Knopf gegeben hat. Dieser hier
        # setzt den gewählten Baustein in die Szene, also heißt er so.
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(tr("Einfügen"))
        # Er kann nichts einfügen, solange nichts gewählt ist. Vorher stand er
        # in voller Akzentfarbe da, nahm den Klick an, schloss den Dialog — und
        # setzte nichts: ``_accept`` rief ``accept()`` auch ohne Baustein. Ein
        # Knopf, der eine Wirkung verspricht und keine hat, ist die stillste
        # Art, jemanden ratlos zu machen. Warum er nicht kann, steht daneben:
        # die Detailspalte sagt „Wählen Sie einen Baustein".
        self._insert = ok
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.addWidget(self.list)
        split.addWidget(self.detail)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(split, stretch=1)
        layout.addWidget(buttons)

        self._previews: dict[str, QPixmap] = {}
        self.show_parts()
        self._show_detail()
        QTimer.singleShot(0, self, self._render_pending)

    # --- content ----------------------------------------------------------------

    def show_parts(self, text: str = "") -> None:
        """Füllt die Liste, gruppiert wie der Katalog gruppiert."""
        self.list.clear()
        wanted = PARTS.search(text) if text.strip() else PARTS.all()
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
        if not self.list.count() and text.strip():
            # Ein leeres Raster sagt nicht, ob nichts passt oder ob die Suche
            # hängt — und die Detailspalte daneben forderte weiter auf, einen
            # Baustein zu wählen, den es hier nicht gibt.
            nothing = QListWidgetItem(
                tr("Kein Baustein passt zu „{begriff}“.").format(begriff=text.strip())
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
        """
        width = max(self.list.viewport().width() - 2 * self.list.spacing(), TILE_WIDTH)
        height = self.list.fontMetrics().height() + 10
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) is None:
                item.setSizeHint(QSize(width, height))

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qt gibt den Namen
        if watched is self.list and event.type() == QEvent.Type.Resize:
            # Ein Filter sieht das Ereignis vor dem Ziel — der Viewport hat
            # hier noch die alte Breite. Erst nach der Verarbeitung messen.
            QTimer.singleShot(0, self, self._stretch_headings)
        handled: bool = super().eventFilter(watched, event)
        return handled

    def _item(self, spec: PartSpec) -> QListWidgetItem:
        item = QListWidgetItem(describe(spec))
        item.setData(Qt.ItemDataRole.UserRole, spec.name)
        item.setIcon(self._preview(spec))
        item.setToolTip(str(spec.doc))
        item.setSizeHint(QSize(TILE_WIDTH, TILE_HEIGHT))
        return item

    def _preview(self, spec: PartSpec) -> Any:
        """Das Vorschaubild, wenn es schon da ist — sonst nichts.

        Jedes Bild wird aus dem Baustein gerechnet (§24.3). Alle beim Öffnen
        nacheinander zu rendern hieß: der Katalog geht auf, wenn das letzte
        fertig ist, und bis dahin hängt das Fenster. Jetzt füllen sie sich
        nach, und die Liste ist sofort lesbar — die Beschreibung daneben steht
        ohnehin von Anfang an.
        """
        from PySide6.QtGui import QIcon

        found = self._previews.get(spec.name)
        return QIcon(found) if found is not None else QIcon()

    def _render_pending(self) -> None:
        """Rendert das nächste fehlende Bild und reiht sich neu ein.

        Eines je Durchlauf der Ereignisschleife: das Fenster bleibt zwischen
        den Bildern bedienbar, und wer den Katalog gleich wieder schließt,
        hat nicht auf achtzehn Rechnungen gewartet.
        """
        from PySide6.QtGui import QPainter

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

    def _refresh_icon(self, name: str) -> None:
        """Hängt ein fertiges Bild an seine Zeile, ohne die Liste neu zu bauen —
        ein Neuaufbau würde die Auswahl und die Bildlaufposition mitnehmen.
        """
        pixmap = self._previews.get(name)
        if pixmap is None:
            return
        from PySide6.QtGui import QIcon

        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == name:
                item.setIcon(QIcon(pixmap))
                return

    def _show_detail(self) -> None:
        """Was rechts steht, folgt der Auswahl links — und der Knopf auch."""
        name = self.chosen()
        spec = next((entry for entry in PARTS.all() if entry.name == name), None)
        self.detail.setText(detail(spec))
        if self._insert is not None:
            self._insert.setEnabled(spec is not None)

    # --- choosing ---------------------------------------------------------------

    def chosen(self) -> str | None:
        item = self.list.currentItem()
        value: str | None = item.data(Qt.ItemDataRole.UserRole) if item else None
        return value

    def _chosen(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self.partChosen.emit(name)
            self.accept()

    def _accept(self) -> None:
        name = self.chosen()
        if name:
            self.partChosen.emit(name)
        self.accept()


def describe(spec: PartSpec) -> str:
    """Titel, die zwei wichtigsten Parameter, und woher der Baustein kommt."""
    parameters = ", ".join(str(entry.title) for entry in spec.params.spec()[:SHOWN_PARAMETERS])
    marker = f" {OWN_MARKER} {tr('eigener Baustein')}" if spec.own else ""
    kind = f"\n{SUBTRACTIVE_MARKER} {tr('nimmt Material weg')}" if spec.subtractive else ""
    return f"{spec.title}{marker}\n{parameters}{kind}"


def detail(spec: PartSpec | None) -> str:
    """Was die Detailspalte über den gewählten Baustein sagt.

    Die Kachel trägt so viel, wie auf eine Kachel passt; alles Weitere gehört
    daneben und nicht in einen Tooltip, den man erst findet, wenn man weiß,
    dass er da ist.
    """
    if spec is None:
        return tr("Wählen Sie einen Baustein — hier steht dann, was er tut.")

    lines = [f"<b>{spec.title}</b>", "", str(spec.doc), ""]
    if spec.subtractive:
        lines.append(f"{SUBTRACTIVE_MARKER} {tr('nimmt Material weg')}")
    if spec.own:
        lines.append(f"{OWN_MARKER} {tr('eigener Baustein')}")
    if spec.subtractive or spec.own:
        lines.append("")

    lines.append(f"<b>{tr('Parameter')}</b>")
    for entry in spec.params.spec():
        unit = f" [{entry.unit}]" if entry.unit else ""
        lines.append(f"· {entry.title}{unit}")
    return "<br>".join(lines)


def _icon_size() -> Any:
    from PySide6.QtCore import QSize

    return QSize(SIZE, SIZE)
