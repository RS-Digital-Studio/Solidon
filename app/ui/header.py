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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.branding import PROJECT_SUFFIX
from app.core.scene import EvaluationResult
from app.core.types import Profile
from app.core.units import LengthUnit
from app.ui.labels import length
from app.ui.style import NORMAL, ROOMY, set_level


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


class HeaderBar(QWidget):
    """Projekt links, Zustand rechts — eine Zeile, die immer steht."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("headerBar")

        self.title = QLabel("", self)
        set_level(self.title, "section")
        self.bounds = QLabel("", self)
        set_level(self.bounds, "caption")

        self.printer = QLabel("", self)
        set_level(self.printer, "caption")
        self.material = QLabel("", self)
        set_level(self.material, "caption")

        row = QHBoxLayout(self)
        row.setContentsMargins(ROOMY, 0, ROOMY, 0)
        row.setSpacing(NORMAL)
        row.addWidget(self.title)
        row.addWidget(self.bounds)
        row.addStretch(1)
        row.addWidget(self.printer)
        row.addWidget(self.material)

        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().Policy.Fixed)

    def show_project(self, name: str, result: EvaluationResult | None, unit: LengthUnit) -> None:
        """Name und Außenmaß des offenen Projekts.

        Die Dateiendung fällt weg: dass ein Formwerk-Projekt ``.p3d`` heißt,
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


#: Die Kopfzeile richtet ihre Beschriftungen senkrecht mittig aus.
ALIGN = Qt.AlignmentFlag.AlignVCenter
