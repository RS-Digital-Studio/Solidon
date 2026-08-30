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
from app.ui.leash import stop_watching_the_dying
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

#: Was den gescheiterten oder fehlenden Bereichstest anschreibt (§24.5).
#: Ein Ausrufezeichen und ein Satz — §24.5 verlangt den Warnhinweis am
#: Katalogeintrag, kein Verbot: Der Baustein bleibt wählbar, er trägt nur
#: seine Warnung mit. ``range_passed`` wurde bis zum 26.08.2026 geschrieben,
#: geprüft und von keiner Oberfläche gelesen — der Satz im Rezeptdialog
#: („Der Katalog zeigt das an") war unwahr.
RANGE_MARKER = "!"

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


class PartCatalog(QDialog):
    """Bilder, Beschreibungen und ein Suchfeld."""

    partChosen = Signal(str)
    saveRequested = Signal()
    """Der Kunde will den gewählten Ausschnitt als eigenen Baustein ablegen (E4).

    Ein Signal und kein Aufruf: Der Katalog hat kein Dokument und keine
    Sitzung. Was daraus wird, entscheidet das Fenster."""

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
        self.list.currentItemChanged.connect(self._show_detail)

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

        # Der Grund für einen gesperrten Speichern-Knopf steht **sichtbar**
        # über der Knopfzeile, nicht nur im Tooltip — die Detailspalte dieses
        # Dialogs sagt selbst, dass ein Tooltip nur findet, wer weiß, dass er
        # da ist. Leer, solange der Knopf frei ist; angelegt vor der
        # Knopfzeile, weil deren Aufbau ``set_can_save`` bereits ruft.
        self.save_hint = QLabel("", self)
        self.save_hint.setWordWrap(True)
        self.save_hint.setVisible(False)
        # Die Schwester für die andere Hälfte der Knopfzeile: warum gerade
        # nichts eingesetzt werden kann. Ohne sie wählte jemand auf der
        # Startseite einen Baustein, bestätigte — und bekam erst dann
        # „Wählen Sie zuerst ein Objekt": zwei Dialoge für eine Absage, die
        # beim Öffnen schon feststand (Robert, 25.08.2026, über 3d-druck-ce).
        self.insert_hint = QLabel("", self)
        self.insert_hint.setWordWrap(True)
        self.insert_hint.setVisible(False)
        self._insert_allowed = True
        self._insert_reason = ""
        self._feature_chosen = True
        """Ob im Objektbaum eine Fläche oder Bohrung gewählt ist.

        Vierundzwanzig der siebenundzwanzig Bausteine werden an eine solche
        Stelle gesetzt; ohne sie wissen sie weder wohin noch in welche
        Richtung, und die Operation bricht mit „Für diesen Baustein fehlt die
        Stelle, an die er soll" ab. Vorgabe ``True``: Wer die Auskunft nicht
        gibt, bekommt den Katalog wie zuvor."""

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

        # **Der Weg zum eigenen Baustein steht im Katalog und nicht im Menü**
        # (Konzept §16 Schritt 3, Begründung in §18c): Wer ein Teil in die
        # Bibliothek legen will, denkt an die Bibliothek — und die Menüleiste
        # ist die Stelle, die von eigenen Bausteinen ohnehin frei bleibt.
        #
        # Der Knopf schickt nur ein Signal. Was gespeichert wird, weiß das
        # Fenster: Ausschnitt des Verlaufs, eingebettete Quellen, Merkmale des
        # gerechneten Körpers. Der Katalog kennt das Dokument nicht und soll es
        # nicht kennen.
        self.save_part = buttons.addButton(
            tr("Auswahl als Baustein speichern …"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self.save_part.clicked.connect(self.saveRequested.emit)
        self.set_can_save(False, "")

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
        layout.addWidget(self.save_hint)
        layout.addWidget(self.insert_hint)
        layout.addWidget(buttons)

        self._previews: dict[str, QPixmap] = {}
        self.show_parts()
        self._show_detail()
        self._rendering = True
        QTimer.singleShot(0, self, self._render_pending)

    # --- content ----------------------------------------------------------------

    def set_can_save(self, can: bool, reason: str = "") -> None:
        """Gibt den Knopf frei — oder sagt daneben, was ihm fehlt.

        Ein Knopf, der eine Wirkung verspricht und keine hat, ist die stillste
        Art, jemanden ratlos zu machen; derselbe Befund, der dem „Einfügen"
        daneben seine Bedingung gegeben hat. Der Grund kommt vom Fenster, weil
        nur das ihn kennt — kein Ausschnitt gewählt, kein Körper gerechnet.
        Er steht als Zeile über den Knöpfen (das Handbuch verspricht „sagt
        daneben, was ihm fehlt" — ein Tooltip löst das nicht ein); der Tooltip
        bleibt als zweite Kodierung dazu.
        """
        self.save_part.setEnabled(can)
        self.save_part.setToolTip("" if can else reason)
        self.save_hint.setText("" if can else reason)
        self.save_hint.setVisible(bool(reason) and not can)

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

    def set_feature_chosen(self, chosen: bool) -> None:
        """Ob eine Fläche oder Bohrung gewählt ist — die zweite Bedingung.

        Sie gilt **je Baustein** und nicht für den ganzen Katalog: Von den
        siebenundzwanzig werden vierundzwanzig an eine Stelle gesetzt, drei
        Prüfkörper stehen frei. Eine pauschale Sperre nähme diesen dreien den
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
        self._show_detail()

    def _insert_state(self, spec: PartSpec | None) -> tuple[bool, str]:
        """Ob sich dieser Baustein einsetzen lässt — und was sonst zu tun ist.

        Zwei Bedingungen übereinander, und nur die erste ist ein Riegel: Ohne
        Szene oder ohne gewählten Körper geht gar nichts. Die zweite ist ein
        Hinweis, weil der Weg über eine eingetragene Position offen bleibt.
        """
        if not self._insert_allowed:
            return False, self._insert_reason
        if spec is None:
            return False, ""
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
        """Was rechts steht, folgt der Auswahl links — und der Knopf auch.

        Die Hinweiszeile wird **hier** geschrieben und nicht in
        :meth:`set_can_insert`: Ihr Text hängt am gewählten Baustein, und der
        wechselt mit jedem Klick in der Liste.
        """
        name = self.chosen()
        spec = next((entry for entry in PARTS.all() if entry.name == name), None)
        self.detail.setText(detail(spec))
        allowed, reason = self._insert_state(spec)
        if self._insert is not None:
            self._insert.setEnabled(spec is not None and allowed)
            self._insert.setToolTip(reason)
        self.insert_hint.setText(reason)
        self.insert_hint.setVisible(bool(reason))

    # --- choosing ---------------------------------------------------------------

    def chosen(self) -> str | None:
        item = self.list.currentItem()
        value: str | None = item.data(Qt.ItemDataRole.UserRole) if item else None
        return value

    def _chosen(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if name and self._insert_allowed:
            self.partChosen.emit(name)
            self.accept()

    def _accept(self) -> None:
        name = self.chosen()
        if name and self._insert_allowed:
            self.partChosen.emit(name)
        self.accept()


def _range_warning(spec: PartSpec) -> str:
    """Der §24.5-Satz zum Bereichstest — oder nichts.

    Nur für Rezepte: Ein mitgelieferter Baustein wird in der Suite über
    seinen ganzen Bereich gefahren, sein ``None`` heißt „nicht hier
    protokolliert" und nicht „ungeprüft". Bei einem Rezept heißt ``None``,
    dass der Test nie lief — eine von Hand kopierte Datei etwa —, und
    ``False``, dass an den Grenzen kein brauchbarer Körper herauskam.
    """
    if spec.source not in ("recipe", "travelled") or spec.range_passed is True:
        return ""
    if spec.range_passed is False:
        return tr("an den Grenzen kam kein brauchbarer Körper heraus")
    return tr("der Bereichstest ist für diesen Baustein nie gelaufen")


def describe(spec: PartSpec) -> str:
    """Titel, die zwei wichtigsten Parameter, und woher der Baustein kommt."""
    parameters = ", ".join(str(entry.title) for entry in spec.params.spec()[:SHOWN_PARAMETERS])
    marker = f" {OWN_MARKER} {tr('eigener Baustein')}" if spec.own else ""
    if spec.source == "travelled":
        # „Um eine Herkunft mehr" (Konzept §17.1): Der Baustein kam mit einer
        # Projektdatei und gehört ihr — nicht dieser Maschine.
        marker = f" {OWN_MARKER} {tr('mitgereister Baustein')}"
    kind = f"\n{SUBTRACTIVE_MARKER} {tr('nimmt Material weg')}" if spec.subtractive else ""
    warning = _range_warning(spec)
    checked = f"\n{RANGE_MARKER} {warning}" if warning else ""
    return f"{spec.title}{marker}\n{parameters}{kind}{checked}"


def detail(spec: PartSpec | None) -> str:
    """Was die Detailspalte über den gewählten Baustein sagt.

    Die Kachel trägt so viel, wie auf eine Kachel passt; alles Weitere gehört
    daneben und nicht in einen Tooltip, den man erst findet, wenn man weiß,
    dass er da ist.
    """
    if spec is None:
        return tr("Wählen Sie einen Baustein — hier steht dann, was er tut.")

    # Maskiert, denn die Spalte ist RichText und Titel wie Beschreibung sind
    # bei Rezepten Kundeneingaben — und mitgereiste kommen aus fremden
    # Dateien: „<b>Halter" zerrisse sonst die Anzeige, statt dazustehen
    # (Fund des Gesamtreviews vom 25.08.2026).
    from html import escape

    lines = [f"<b>{escape(str(spec.title))}</b>", "", escape(str(spec.doc)), ""]
    if spec.subtractive:
        lines.append(f"{SUBTRACTIVE_MARKER} {tr('nimmt Material weg')}")
    if spec.own:
        lines.append(f"{OWN_MARKER} {tr('eigener Baustein')}")
    if spec.source == "travelled":
        lines.append(
            f"{OWN_MARKER} "
            + tr("mitgereister Baustein — kam mit einer Projektdatei und bleibt bei ihr")
        )
    warning = _range_warning(spec)
    if warning:
        lines.append(f"<b>{RANGE_MARKER}</b> {warning}")
    if spec.subtractive or spec.own or spec.source == "travelled" or warning:
        lines.append("")

    lines.append(f"<b>{tr('Parameter')}</b>")
    for entry in spec.params.spec():
        unit = f" [{escape(str(entry.unit))}]" if entry.unit else ""
        lines.append(f"· {escape(str(entry.title))}{unit}")
    return "<br>".join(lines)


def _icon_size() -> Any:
    from PySide6.QtCore import QSize

    return QSize(SIZE, SIZE)
