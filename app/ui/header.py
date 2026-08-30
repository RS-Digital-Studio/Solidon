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
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from app.branding import PROJECT_SUFFIX
from app.core.scene import EvaluationResult
from app.core.types import Profile
from app.core.units import LengthUnit
from app.i18n import tr
from app.ui.labels import length
from app.ui.style import NORMAL, ROOMY, divider, set_level
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

#: Wie schmal ein kürzbares Feld der Kopfzeile werden darf, bevor es aufhört,
#: etwas zu sagen. Vier Zeichen und die Auslassung — darunter steht dort „…",
#: und das ist keine Auskunft mehr.
LEAST_CHARACTERS = 5


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

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        # **Auch der Text aus dem Konstruktor bekommt seinen Tooltip.** Er lief
        # an :meth:`setText` vorbei, und damit hätte ein so gebautes Label
        # gekürzt, ohne dass irgendwo noch stünde, was da eigentlich steht. In
        # dieser Datei starten alle Labels leer, der Fall trat also nie ein —
        # eine Zusage, die nur zufällig hält, hält nicht.
        if text:
            self.setToolTip(text)

    def setText(self, text: str) -> None:  # noqa: N802 — Qt-Name
        """Merkt sich den ganzen Text und zeigt, was hineinpasst."""
        self._full = text
        self.setToolTip(text)
        self._fit()

    def full_text(self) -> str:
        """Was dastünde, wenn der Platz reichte — für Tests und Vorleser."""
        return self._full

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Fünf Zeichen statt der vollen Breite.

        Das ist die eine Zeile, an der D6 hängt: Solange hier die volle
        Textbreite steht, kann die Leiste nicht kürzen, sondern nur
        wegnehmen.
        """
        height = super().minimumSizeHint().height()
        return QSize(self.fontMetrics().averageCharWidth() * LEAST_CHARACTERS, height)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        """Kürzt auf die aktuelle Breite — aber nur, wenn es eine gibt.

        **Vor dem ersten Layout ist ``width()`` winzig**, und wer dann kürzt,
        kürzt auf nichts: Gemessen stand nach dem Öffnen eines Projekts ``''``
        im Titel, obwohl der Name gesetzt war. Ein Label, das seinen Text beim
        Setzen verliert, ist schlimmer als eines, das die Zeile sprengt —
        gefunden hat es die Nachmessung, kein Test hätte danach gefragt.
        """
        room = self.width()
        if room <= self.fontMetrics().averageCharWidth() * LEAST_CHARACTERS:
            super().setText(self._full)
            return
        super().setText(
            self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, room)
        )


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

        # **Die drei langen kürzen, die kurzen nicht** (Befund D6). Name, Maße
        # und Drucker tragen zusammen 878 der 968 Pixel, die diese Zeile
        # wünschte; „Druckplatte" und „PLA" sind kurz und fest. Wer alles
        # kürzbar macht, bekommt eine Zeile, in der auch das Material zu „P…"
        # wird, ohne dass es je nötig wäre.
        self.title = _EphemeralLabel("", self)
        set_level(self.title, "section")
        self.bounds = _EphemeralLabel("", self)
        set_level(self.bounds, "caption")

        self.plate_label = QLabel(tr("Druckplatte"), self)
        set_level(self.plate_label, "caption")
        self.plates = BarComboBox(self)
        self.plates.setAccessibleName(tr("Druckplatte"))
        self.plates.setToolTip(tr("Zeigt nur die Objekte einer Platte."))
        self.plates.currentIndexChanged.connect(self._on_plate)

        self.printer = _EphemeralLabel("", self)
        set_level(self.printer, "caption")
        self.material = QLabel("", self)
        set_level(self.material, "caption")

        row = QHBoxLayout(self)
        row.setContentsMargins(ROOMY, 0, ROOMY, 0)
        row.setSpacing(NORMAL)
        row.addWidget(self.title)
        row.addWidget(self.bounds)
        row.addStretch(1)
        row.addWidget(self.plate_label)
        row.addWidget(self.plates)
        # Dieselbe Trennung wie in der Statuszeile: Plattenwahl links,
        # Drucker und Material rechts — „… 220 mm   PLA" stand sonst als ein
        # Satz da, obwohl das eine eine Auswahl ist und das andere ein
        # Bericht.
        row.addWidget(divider(self))
        row.addWidget(self.printer)
        row.addWidget(self.material)

        self.show_plates(0)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().Policy.Fixed)

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
        self.plates.addItem(tr("Alle"), ALL_PLATES)
        for index in range(plates):
            self.plates.addItem(f"{tr('Platte')} {index + 1}", index)
        if previous != ALL_PLATES and previous < plates:
            self.plates.setCurrentIndex(previous + 1)
        self.plates.blockSignals(False)

        many = plates > 1
        self.plates.setVisible(many)
        self.plate_label.setVisible(many)
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

    def show_profile(self, profile: Profile) -> None:
        """Worauf gedruckt wird. Beides, denn beides ändert das Ergebnis."""
        self.printer.setText(str(profile.printer.title))
        self.material.setText(str(profile.material.title))

    def state(self) -> tuple[str, str, str, str]:
        """Was gerade dasteht — die Tests lesen das, nicht die Widgets."""
        return (
            self.title.text(),
            self.bounds.text(),
            self.printer.text(),
            self.material.text(),
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
