"""Die Kopfzeile: was offen ist, und worauf es gedruckt wird.

Über dem Fenster stand bisher eine Werkzeugleiste mit vier Knöpfen und
tausend Pixeln Leerraum daneben. Die Knöpfe bleiben — neu ist, was rechts
davon steht: der Zustand, in dem sich das Projekt befindet.

**Warum das dort steht und nicht in einem Dialog.** Drucker und Material
entscheiden jede Toleranz im Stapel (§12): eine Passung ist ein Verweis ins
Materialprofil, kein Zahlenwert. Wer nicht weiß, gegen welches Material
gerechnet wird, weiß nicht, was seine Bohrung bedeutet — und musste dafür
bisher ``Strg+P`` drücken und ein Formular lesen.

Die Zeile behauptet nichts, was sie nicht weiß. Ohne offenes Projekt steht
dort nichts, und die Maße erscheinen erst, wenn es etwas zu messen gibt.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QWidget,
)

from app.branding import PROJECT_SUFFIX
from app.core.scene import EvaluationResult
from app.core.types import Profile
from app.core.units import LengthUnit
from app.i18n import tr
from app.ui.labels import length
from app.ui.style import TIGHT, divider, set_level
from app.ui.tool_strip import BarComboBox


def project_name(title: str) -> str:
    """Der Titel ohne seine Dateiendung.

    ``session.title`` liefert den Dateinamen, mit einem Stern für
    Ungesichertes. Der Stern bleibt — er ist eine Aussage; ``.p3d`` fällt weg,
    denn es steht in jedem Projekt und unterscheidet keines vom anderen.
    """
    marker = "*" if title.endswith("*") else ""
    stem = title.removesuffix("*")
    return f"{stem.removesuffix(PROJECT_SUFFIX)}{marker}"


def bounds_text(result: EvaluationResult | None, unit: LengthUnit) -> str:
    """Das Außenmaß über alle Körper, oder nichts.

    Über alle und nicht je Körper: die Zeile beantwortet „passt das auf die
    Platte", und dafür zählt der Hüllquader über das Ganze. Was ein einzelner
    Körper misst, steht im Objektbaum.
    """
    if result is None or not result.scene.objects:
        return ""
    boxes = [entry.mesh.bounds for entry in result.scene.objects.values()]
    size = [
        max(box.maximum[axis] for box in boxes) - min(box.minimum[axis] for box in boxes)
        for axis in range(3)
    ]
    # Die Einheit einmal am Ende, wie im Objektbaum: dreimal „mm" in einer
    # Zeile sagt dreimal dasselbe und liest sich dreimal so lang.
    measures = " × ".join(length(value, unit, with_unit=False) for value in size)
    return f"{measures} {unit}"


#: Wie der Wähler „kein Filter" nennt. Derselbe Wert wie in
#: ``explode_bar``, wo der Wähler herkommt — der Viewport kennt ihn.
ALL_PLATES = -1

#: Ein eigenes Profil darf aus einem einzigen, beliebig langen Wort bestehen.
#: Sein unterscheidendes Ende bleibt zugänglich, darf aber nicht erneut die
#: ganze Werkzeugleiste auf sein Vollmaß zwingen.
MAXIMUM_TAIL_CHARACTERS = 10


class _EphemeralLabel(QLabel):
    """Ein Label, das seinen Text kürzt, statt seine Zeile zu sprengen.

    **Der Grund steht in der Messung** (Befund D6). Die Kopfzeile lebt als
    Widget in der Werkzeugleiste, und Qt gibt einem Widget dort entweder seine
    ``sizeHint``-Breite oder gar keinen Platz: Wer nicht hineinpasst, wandert
    ins Erweiterungsmenü hinter dem Pfeil. Ein ``QLabel`` meldet als
    Mindestbreite die volle Textbreite — gemessen an einem geöffneten Projekt
    waren das 273 px für den Namen, 275 für die Maße und 330 für den Drucker,
    zusammen 968 px für die ganze Zeile. Die Leiste wünschte damit 2283 px.

    Was daraus folgte, sah kein Test: **Auf einem 1920er Bildschirm war die
    Kopfzeile weg**, sobald jemand ein Projekt öffnete — Projektname, Maße,
    Druckplatte, Drucker und Material zusammen, verschwunden hinter einem
    unbeschrifteten Pfeil. Mit leerem Projekt passierte das nicht (dort will
    sie 103 px), und genau deshalb fällt es beim Ausprobieren nicht auf.

    Ein gekürzter Name ist eine schlechtere Auskunft als der ganze. **Keine
    Auskunft ist die schlechteste**: Der volle Text bleibt im Tooltip, und wer
    das Fenster breit zieht, bekommt ihn zurück.
    """

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        *,
        tail_words: int = 0,
        protected_end: str = "",
    ) -> None:
        super().__init__("", parent)
        self._full = ""
        self._tail_words = tail_words
        self._protected_end = protected_end
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        # Konstruktor und späteres Setzen laufen bewusst durch denselben Weg:
        # Volltext, Hilfe und sichtbare Kürzung dürfen nie auseinanderlaufen.
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 — Qt-Name
        """Merkt sich den ganzen Text und zeigt, was hineinpasst."""
        self._full = text
        self.setToolTip(text)
        self.setAccessibleName(text)
        raw_tail, visible_tail = self._bounded_tail()
        if raw_tail:
            metrics = self.fontMetrics()
            full_width = metrics.horizontalAdvance(text)
            body = text[: -len(raw_tail)]
            tail_width = metrics.horizontalAdvance(f"{'…' if body else ''}{visible_tail}")
            # Ein echtes Minimum, kein ``minimumSizeHint`` unter ``Ignored``:
            # Stern, Einheit oder ein begrenztes Modellende passen damit
            # nachweisbar hinein, ohne die Leiste selbst wieder zu verdrängen.
            self.setMinimumWidth(min(full_width, tail_width))
        else:
            self.setMinimumWidth(0)
        self.updateGeometry()
        self._fit()

    def full_text(self) -> str:
        """Was dastünde, wenn der Platz reichte — für Tests und Vorleser."""
        return self._full

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        super().resizeEvent(event)
        self._fit()

    def _tail(self) -> str:
        """Das rohe Ende, dessen Bedeutung eine Kürzung nicht verschlucken darf."""
        if self._protected_end and self._full.endswith(self._protected_end):
            return self._protected_end
        if not self._tail_words:
            return ""
        words = self._full.split()
        return " ".join(words[-self._tail_words :])

    def _bounded_tail(self, room: int | None = None) -> tuple[str, str]:
        """Begrenzt ein unteilbares Ende, nicht den zugänglichen Volltext."""
        raw_tail = self._tail()
        if not raw_tail:
            return "", ""
        metrics = self.fontMetrics()
        limit = max(
            metrics.horizontalAdvance("…"),
            metrics.averageCharWidth() * MAXIMUM_TAIL_CHARACTERS,
        )
        if room is not None:
            limit = min(limit, max(0, room))
        visible_tail = metrics.elidedText(raw_tail, Qt.TextElideMode.ElideMiddle, limit)
        return raw_tail, visible_tail

    def _fit(self) -> None:
        """Kürzt sichtbar und hält das semantische Ende vollständig fest."""
        room = self.width()
        metrics = self.fontMetrics()
        if metrics.horizontalAdvance(self._full) <= room:
            super().setText(self._full)
            return
        raw_tail, visible_tail = self._bounded_tail(room)
        if not raw_tail:
            super().setText(metrics.elidedText(self._full, Qt.TextElideMode.ElideMiddle, room))
            return
        body = self._full[: -len(raw_tail)]
        if not body:
            super().setText(metrics.elidedText(self._full, Qt.TextElideMode.ElideMiddle, room))
            return
        body_room = max(0, room - metrics.horizontalAdvance(visible_tail))
        visible = metrics.elidedText(body, Qt.TextElideMode.ElideMiddle, body_room) + visible_tail
        # Kerning an der neuen Naht kann den getrennt berechneten Text um
        # einzelne Pixel verbreitern. Die sichtbare Zusage gewinnt auch dort.
        while body_room and metrics.horizontalAdvance(visible) > room:
            body_room -= 1
            visible = (
                metrics.elidedText(body, Qt.TextElideMode.ElideMiddle, body_room) + visible_tail
            )
        super().setText(visible)


class HeaderBar(QWidget):
    """Projekt links, Zustand rechts — eine Zeile, die immer steht.

    **Der Plattenwähler wohnte im Explodieren.** Er stand in der Leiste, die
    Teile auseinanderzieht, und erschien nur, wenn dort auch der Schieber etwas
    zu tun hatte: Wer eine einzelne Platte ansehen wollte, suchte ihn unter
    einem Werkzeug für etwas anderes. Hier gehört er hin — die Zeile sagt, was
    offen ist und worauf gedruckt wird, und auf welche Platte man sieht, ist
    dieselbe Art Auskunft.
    """

    plateChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("headerBar")

        # **Die drei langen kürzen mit Bedeutung** (Befund D6). Name, Maße und
        # Drucker tragen zusammen 878 der 968 Pixel, die diese Zeile wünschte;
        # ihre Enden bleiben deshalb fest: Ungespeichert-Stern, Einheit und
        # Druckermodell. Plattenwahl und Material teilen den übrigen Raum
        # responsiv, wobei der Zweck „Platte“ nie abgeschnitten werden darf.
        self.title = _EphemeralLabel("", self, protected_end="*")
        set_level(self.title, "section")
        self.bounds = _EphemeralLabel("", self, tail_words=1)
        set_level(self.bounds, "caption")

        self.plates = BarComboBox(self)
        self.plates.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.plates.setAccessibleName(tr("Druckplatte"))
        self.plates.setToolTip(tr("Zeigt nur die Objekte einer Platte."))
        self.plates.currentIndexChanged.connect(self._on_plate)

        self.printer = _EphemeralLabel("", self, tail_words=2)
        set_level(self.printer, "caption")
        # Das Material steht zusätzlich im Filamentbereich. In der engsten
        # Kopfzeile darf diese Wiederholung deshalb vor dem Plattenwähler
        # kürzen; der vollständige Wert bleibt wie bei den übrigen Auskünften
        # für Tooltip und Hilfstechnik erhalten.
        self.material = _EphemeralLabel("", self, tail_words=1)
        set_level(self.material, "caption")

        self._divider = divider(self)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(TIGHT, 0, TIGHT, 0)
        self._layout.setHorizontalSpacing(TIGHT)
        self._layout.setVerticalSpacing(TIGHT)
        self._compact = False
        self._arrange(False)
        # Dieselbe Trennung wie in der Statuszeile: Plattenwahl links,
        # Drucker und Material rechts — „… 220 mm   PLA" stand sonst als ein
        # Satz da, obwohl das eine eine Auswahl ist und das andere ein
        # Bericht.

        self.show_plates(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Bittet die Werkzeugleiste um das zweizeilige Kompaktmaß.

        ``QToolBar`` gibt einem eingebetteten Widget sonst sein Wunschmaß oder
        verschiebt es vollständig in den Überlauf. Das Kompaktmaß legt den
        Plattenzustand unter die übrigen Angaben; durch ``Expanding`` wächst
        der Header bei mehr Platz weiter und bleibt dann einzeilig.
        """
        preferred = super().sizeHint()
        return QSize(self._compact_width(), preferred.height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Das kleinste responsive Maß statt der Summe einer einzigen Zeile."""
        minimum = super().minimumSizeHint()
        return QSize(self._compact_width(), minimum.height())

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        self._arrange(self._wide_width() > event.size().width())
        super().resizeEvent(event)

    def _compact_width(self) -> int:
        """Breite der zweizeiligen Anordnung: Angaben oben, Filter unten."""
        top = (self.title, self.bounds, self.printer, self.material)
        top_width = sum(widget.minimumWidth() for widget in top) + TIGHT * (len(top) - 1)
        plate_width = self.plates.minimumWidth() if not self.plates.isHidden() else 0
        return max(top_width, plate_width) + TIGHT * 2

    def _wide_width(self) -> int:
        """Mindestbreite, ab der alle Angaben in eine Zeile passen."""
        widgets: list[QWidget] = [self.title, self.bounds]
        if not self.plates.isHidden():
            widgets.extend((self.plates, self._divider))
        widgets.extend((self.printer, self.material))
        return (
            sum(widget.minimumWidth() for widget in widgets)
            + TIGHT * max(0, len(widgets) - 1)
            + TIGHT * 2
        )

    def _arrange(self, compact: bool) -> None:
        """Ordnet denselben Inhalt ohne Duplikat ein- oder zweizeilig an."""
        if compact == self._compact and self._layout.count():
            return
        widgets = (
            self.title,
            self.bounds,
            self.plates,
            self._divider,
            self.printer,
            self.material,
        )
        for widget in widgets:
            self._layout.removeWidget(widget)
        for column in range(7):
            self._layout.setColumnStretch(column, 0)
        if compact:
            self._layout.addWidget(self.title, 0, 0)
            self._layout.addWidget(self.bounds, 0, 1)
            self._layout.addWidget(self.printer, 0, 2)
            self._layout.addWidget(self.material, 0, 3)
            self._layout.addWidget(self.plates, 1, 0, 1, 4)
            for column, stretch in enumerate((2, 3, 3, 1)):
                self._layout.setColumnStretch(column, stretch)
            self._divider.hide()
        else:
            self._layout.addWidget(self.title, 0, 0)
            self._layout.addWidget(self.bounds, 0, 1)
            self._layout.addWidget(self.plates, 0, 3)
            self._layout.addWidget(self._divider, 0, 4)
            self._layout.addWidget(self.printer, 0, 5)
            self._layout.addWidget(self.material, 0, 6)
            for column, stretch in ((0, 2), (1, 3), (2, 1), (3, 1), (5, 3), (6, 1)):
                self._layout.setColumnStretch(column, stretch)
            self._divider.show()
        self._compact = compact
        self._layout.invalidate()
        self._layout.activate()
        self.updateGeometry()

    def _reflow(self) -> None:
        """Zieht nach, wenn ein neuer Text sein semantisches Minimum ändert."""
        self._arrange(self._wide_width() > self.width())

    @property
    def plate(self) -> int:
        """Die Platte, die gezeigt wird, oder :data:`ALL_PLATES`."""
        value = self.plates.currentData()
        return ALL_PLATES if value is None else int(value)

    def show_plates(self, plates: int) -> None:
        """Baut den Wähler neu und behält die Platte, die betrachtet wurde.

        Sichtbar ab zwei Platten: Ein Element, das immer dasteht und meistens
        nichts tut, bringt Leuten bei, es zu ignorieren.
        """
        previous = self.plate
        self.plates.blockSignals(True)
        self.plates.clear()
        self.plates.addItem(tr("Alle Platten"), ALL_PLATES)
        for index in range(plates):
            self.plates.addItem(tr("Platte {number}", number=index + 1), index)
        # Zweck **und Zustand** bleiben vollständig sichtbar. Nur „Platte“ zu
        # zeigen verbarg nach der Wahl, ob alle oder eine einzelne Platte gilt.
        # Der aktive Qt-Stil liefert Innenabstand, Rahmen und Pfeil. Qts
        # ``sizeHint`` speichert dagegen den ersten, noch leeren Inhalt im
        # Cache; nach dem Befüllen war er kleiner als der aktuelle Text.
        metrics = self.plates.fontMetrics()
        texts = [self.plates.itemText(index) for index in range(self.plates.count())]
        widest = max(texts, key=metrics.horizontalAdvance)
        option = QStyleOptionComboBox()
        option.initFrom(self.plates)
        option.currentText = widest
        needed = self.plates.style().sizeFromContents(
            QStyle.ContentsType.CT_ComboBox,
            option,
            QSize(metrics.horizontalAdvance(widest), metrics.height()),
            self.plates,
        )
        self.plates.setMinimumWidth(needed.width())
        if previous != ALL_PLATES and previous < plates:
            self.plates.setCurrentIndex(previous + 1)
        self.plates.blockSignals(False)

        many = plates > 1
        self.plates.setVisible(many)
        self._reflow()
        if not many and previous != ALL_PLATES:
            self.plateChanged.emit(ALL_PLATES)

    def _on_plate(self, index: int) -> None:
        del index
        self.plateChanged.emit(self.plate)

    def show_project(self, name: str, result: EvaluationResult | None, unit: LengthUnit) -> None:
        """Name und Außenmaß des offenen Projekts.

        Die Dateiendung fällt weg: dass ein Solidon-Projekt ``.p3d`` heißt,
        weiß der Dateidialog, und in einer Überschrift ist es Rauschen. Der
        Stern für Ungesichertes bleibt — er ist eine Aussage.
        """
        self.title.setText(project_name(name))
        self.bounds.setText(bounds_text(result, unit))
        self._reflow()

    def show_profile(self, profile: Profile) -> None:
        """Worauf gedruckt wird. Beides, denn beides ändert das Ergebnis."""
        self.printer.setText(str(profile.printer.title))
        self.material.setText(str(profile.material.title))
        self._reflow()

    def state(self) -> tuple[str, str, str, str]:
        """Die vollständige Auskunft — unabhängig von der sichtbaren Kürzung."""
        return (
            self.title.full_text(),
            self.bounds.full_text(),
            self.printer.full_text(),
            self.material.full_text(),
        )


def header_stylesheet(theme: str) -> str:
    """Eine Kante nach unten, sonst nichts.

    Die Kopfzeile ist kein Kasten: sie trägt keine Entscheidung, sie beantwortet
    eine Frage. Ein Rahmen darum machte aus einer Auskunft ein Bedienelement.
    """
    from app.ui.theme import THEMES

    colours = THEMES[theme]  # type: ignore[index]
    return f"""
QWidget#headerBar {{
    background: {colours["window"]};
    border-bottom: 1px solid {colours["line"]};
}}
"""
