"""Die Inhaltsschrift eines Funktionsfalls: 14 und 18 pt und der Wechsel zur Laufzeit (RM-737).

Der finale Lauf fuhr nur die Schrift des Systems (Segoe UI 9 pt); große Schrift
(FD-54, FD-185) und ein Wechsel zur Laufzeit (FD-57: 9 → 14 pt, FD-58:
schmal/9 → groß/14 → schmal/9) blieben ungemessen. Die Anwendung nimmt ihre
Schriftgrößen aus der Schrift der ``QApplication``, wie das System sie liefert
(``app.ui.style.apply_style``: „die Schriftgrößen aus der Systemeinstellung“) —
eine eigene Einstellung im Profil hat sie nicht. :func:`set_content_font` setzt die
Schrift der Anwendung deshalb auf die verlangte Punktgröße und gibt sie durch
denselben Stilweg, den die Anwendung beim Start geht. Windows bleibt
unberührt; Familie, Thema und Profil bleiben die des Falls.

* Satz ``schrift``: 14 und 18 pt, gesetzt, bevor das Fenster erscheint
  (``function_setup.place_window``); gemessen wird die offene Fläche wie in
  ``zoll`` oder ``dunkel`` (Phase ``surface``).
* Satz ``schriftwechsel``: die Folge ``font_change`` (Vorgabe 9 → 14 → 9 pt)
  an der offenen Fläche, im Wechsel schmal (kleinste Fläche) und groß
  (maximiert). Je Stufe ein Bild, ob die Fläche zur Ruhe kam, die wirksame
  Schrift und die abgeschnittenen Texte (``font_change`` im Protokoll).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from tools.function_checks import SMALLEST_WINDOW
from tools.function_machine import Step, StepMachine
from tools.function_protocol import unmeasured
from tools.function_setup import place_window

if TYPE_CHECKING:
    from tools.function_bench import FunctionFlow

#: Die Folge des Wechsels (FD-57, FD-58): Grundschrift, groß, zurück.
FONT_CHANGE: Final = (9.0, 14.0, 9.0)


def set_content_font(application: Any, points: float, theme: str) -> float:
    """Setzt die Inhaltsschrift der Anwendung auf ``points`` und gibt sie wirksam zurück.

    Wie ein Wechsel der Systemschrift: neue Schrift der ``QApplication``, dann
    das Stylesheet der Anwendung aus Thema und neuer Größe
    (``style.apply_style``) — jedes Widget bekommt Schrift- und Stilwechsel.
    """
    from PySide6.QtGui import QFont

    from app.ui import style

    font = QFont(application.font())
    font.setPointSizeF(points)
    application.setFont(font)
    style.apply_style(application, theme)  # type: ignore[arg-type]
    return float(application.font().pointSizeF())


def stage_label(number: int, points: float) -> str:
    """Der Name einer Stufe im Bild: Nummer, Punktgröße, schmal oder groß."""
    return f"schrift-{number + 1}-{points:g}pt-{'schmal' if number % 2 == 0 else 'gross'}"


class FontPhase:
    """Der Schriftwechsel als Phase von ``FunctionFlow``, wie ``MatrixPhase``."""

    def phase_fontchange(self: FunctionFlow) -> None:
        """FD-57, FD-58: Weg zur Fläche, dann je Stufe Schrift und Fenstergröße wechseln.

        Gerade Stufen sind schmal (die kleinste Fläche, ``SMALLEST_WINDOW``),
        ungerade groß (maximiert). Nach jedem Wechsel wartet der Fall, bis die
        Fläche stillsteht — eine Größenschleife wie in FD-57 steht dann als
        ``still: false`` und in ``unmeasured`` —, und nimmt sie auf.
        """
        from tools import function_capture as capture

        stages = self.variant.font_change or FONT_CHANGE
        changes: list[dict[str, Any]] = []

        def switch(number: int, points: float) -> Step:
            def act(machine: StepMachine) -> None:
                set_content_font(self.application, points, self.variant.theme)
                if number % 2 == 0:
                    if self.window.isMaximized():
                        self.window.showNormal()
                    self.window.resize(*SMALLEST_WINDOW)
                else:
                    # Groß: wie der Fall das Fenster legt — maximiert, auf einem
                    # Schirm unter der kleinsten Fläche diese (``place_window``).
                    place_window(self.application, self.window, self.variant)

            return Step(f"schrift {points:g} pt", act)

        def take(number: int, points: float) -> Step:
            label = stage_label(number, points)

            def act(machine: StepMachine) -> None:
                root = self.surface()
                start = len(self.data["images"])
                self.picture(label)
                texts = capture.text_entries(root) if root is not None else []
                changes.append(
                    {
                        "points": float(self.application.font().pointSizeF()),
                        "wanted": points,
                        "window": self.window_size(),
                        "still": f"still:{label}" not in self.data["unmeasured"],
                        "image": (self.data["images"][start:] or [""])[0],
                        "cut": [entry["text"] for entry in texts if entry.get("cut")],
                    }
                )

            return Step(f"aufnehmen {label}", act)

        steps: list[Step] = [
            *self.path_steps(),
            self.still_step("fläche steht still", self.surface),
        ]
        for number, points in enumerate(stages):
            steps += [
                switch(number, points),
                self.still_step(f"{stage_label(number, points)}", self.surface),
                take(number, points),
            ]
        if not self.run_steps("schriftwechsel", steps):
            unmeasured(self.data, "font_change", "der Weg zur Fläche oder ein Wechsel brach ab")
        self.data["font_change"] = changes
