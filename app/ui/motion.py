"""Bewegung an der Oberfläche — an einer Stelle, nicht an zwanzig.

Wozu überhaupt: Ein Wechsel, der ohne Übergang geschieht, zwingt das Auge,
die neue Anordnung von vorn zu lesen. Eine kurze Blende sagt „dasselbe
Fenster, andere Ansicht" und kostet weniger Aufmerksamkeit als der harte
Schnitt. Das ist keine Zierde, sondern Orientierung.

Die Regeln, die hier gelten:

* **Kurz.** Über 250 ms wird eine Bewegung zur Wartezeit. Die Werte unten sind
  Obergrenzen, keine Vorschläge.
* **Nie im Weg.** Jede Animation läuft auf einem Widget, das schon steht; sie
  verzögert keine Handlung und hält keine Eingabe auf.
* **Abschaltbar, und in Tests aus.** Offscreen gibt es niemanden, der zusieht,
  und eine laufende Animation macht aus einem Test eine Wette auf das Timing
  (§38).
* **Nie die einzige Aussage.** Was eine Bewegung zeigt, steht auch ohne sie da
  — Regel 18 gilt für Zeit wie für Farbe.

Und die Falle aus ``.claude/rules/oberflaeche.md`` gilt hier genauso: Eine
``QPropertyAnimation`` ohne Elternteil hält niemand fest. Jede bekommt hier
das Widget, auf dem sie läuft — fällt das weg, fällt sie mit.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QVariantAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget, QTabWidget, QWidget

#: Für alles, was nur bestätigt: ein Panel erscheint, ein Hinweis geht.
SHORT_MS = 140

#: Für den Wechsel einer ganzen Ansicht — Startbildschirm, rechte Spalte.
MEDIUM_MS = 220

#: Für einen Wechsel im 3D-Fenster: die Auswahl wandert von einem Körper zum
#: nächsten. Kürzer als ``SHORT_MS``, weil hier jedes Bild ein Neuzeichnen der
#: ganzen Szene ist und nicht ein Deckkraft-Effekt auf einem Widget.
ACCENT_MS = 110

#: Die Kurve für alles: schnell los, weich aus. Eine Bewegung, die linear
#: endet, wirkt abgeschnitten.
CURVE = QEasingCurve.Type.OutCubic

#: Womit sich Bewegung abschalten lässt, ohne den Quelltext anzufassen.
ENVIRONMENT_SWITCH = "SOLIDON3D_MOTION"


def animations_enabled() -> bool:
    """Ob überhaupt bewegt wird.

    Aus unter ``offscreen`` — dort sitzt niemand davor, und ein Test, der auf
    das Ende einer Animation wartet, prüft die Uhr statt das Verhalten. Aus
    auch, wenn ``SOLIDON3D_MOTION=aus`` gesetzt ist; wer Bewegung nicht
    verträgt, soll sie loswerden, ohne eine Einstellung zu suchen.
    """
    if os.environ.get(ENVIRONMENT_SWITCH, "").strip().lower() in {"aus", "off", "0"}:
        return False
    return os.environ.get("QT_QPA_PLATFORM", "") != "offscreen"


def _opacity(widget: QWidget) -> QGraphicsOpacityEffect:
    """Der Deckkraft-Effekt des Widgets, notfalls ein neuer.

    Wiederverwendet statt ersetzt: Zwei Effekte übereinander ergeben zwei
    Multiplikationen, und das Widget bliebe sichtbar blasser als gewollt.
    """
    existing = widget.graphicsEffect()
    if isinstance(existing, QGraphicsOpacityEffect):
        return existing
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    return effect


def fade_in(widget: QWidget, *, duration: int = SHORT_MS) -> None:
    """Blendet ein Widget ein. Sichtbar ist es danach in jedem Fall."""
    widget.setVisible(True)
    if not animations_enabled():
        widget.setGraphicsEffect(None)  # type: ignore[arg-type]
        return
    effect = _opacity(widget)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setEasingCurve(CURVE)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    # Der Effekt kostet bei jedem Zeichnen eine eigene Zwischenfläche. Nach der
    # Blende hat er nichts mehr zu tun, also kommt er weg — sonst zahlt der
    # Viewport ihn für den Rest der Sitzung.
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))  # type: ignore[arg-type]
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


def fade_out(widget: QWidget, *, duration: int = SHORT_MS, hide: bool = True) -> None:
    """Blendet ein Widget aus und versteckt es danach.

    ``hide=False`` lässt es stehen — für den Fall, dass etwas anderes an seiner
    Stelle erscheint und die Lücke sonst aufblitzt.
    """
    if not animations_enabled():
        if hide:
            widget.setVisible(False)
        return
    effect = _opacity(widget)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setEasingCurve(CURVE)
    animation.setStartValue(1.0)
    animation.setEndValue(0.0)

    def done() -> None:
        if hide:
            widget.setVisible(False)
        widget.setGraphicsEffect(None)  # type: ignore[arg-type]

    animation.finished.connect(done)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


def switch(
    stack: QStackedWidget | QTabWidget, target: QWidget, *, duration: int = MEDIUM_MS
) -> None:
    """Wechselt die Seite eines Stapels oder Reiters mit einer Blende.

    Beide tragen dieselben zwei Methoden, und für die Blende zählt nur, was
    danach vorn liegt — der Reiter oben wechselt ohnehin sofort.

    Ohne Blende springt der ganze Inhalt, und bei einem Wechsel zwischen
    Startbildschirm und Arbeitsbereich ist das der härteste Schnitt, den die
    Anwendung hat.

    Der Wechsel selbst geschieht **sofort** — animiert wird nur, wie die neue
    Seite auftaucht. Wer direkt danach auf ``currentWidget`` sieht, bekommt die
    richtige Antwort, und kein Test hängt an einer Uhr.
    """
    if stack.currentWidget() is target:
        return
    stack.setCurrentWidget(target)
    if animations_enabled():
        fade_in(target, duration=duration)


def reveal(widget: QWidget, visible: bool, *, duration: int = SHORT_MS) -> None:
    """Zeigt oder verbirgt ein Widget — mit Blende, aber ohne Umbau.

    Bewusst keine Höhenanimation: Ein Widget, das seine Höhe über mehrere Bilder
    ändert, verschiebt alles darunter mit, und im Viewport daneben bedeutet das
    ein Neuzeichnen je Bild. Für eine Werkzeugleiste ist die Blende die
    ruhigere und die billigere Bewegung.
    """
    if visible:
        fade_in(widget, duration=duration)
    else:
        fade_out(widget, duration=duration)


def flash(widget: QWidget, *, duration: int = MEDIUM_MS) -> None:
    """Hebt ein Widget kurz hervor, ohne es zu bewegen.

    Für den Fall, dass etwas an einer Stelle erscheint, auf die gerade niemand
    sieht — ein neuer Befund im Prüfbericht etwa. Die Aufmerksamkeit holt hier
    die Bewegung; **was** dort steht, sagt weiterhin der Text daneben.
    """
    if not animations_enabled():
        return
    effect = _opacity(widget)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
    animation.setKeyValueAt(0.0, 1.0)
    animation.setKeyValueAt(0.45, 0.35)
    animation.setKeyValueAt(1.0, 1.0)
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))  # type: ignore[arg-type]
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


def mix(start: Sequence[float], end: Sequence[float], fraction: float) -> tuple[float, ...]:
    """Mischt zwei Farben — ``fraction`` 0 ist ``start``, 1 ist ``end``.

    Absichtlich ohne Qt und ohne Uhr: Das ist die Hälfte einer Blende, die sich
    prüfen lässt, ohne auf ein Bild zu warten. Und sie ist nicht auf drei Werte
    festgelegt — ein RGBA-Ton mischt sich genauso.

    Ausserhalb von 0..1 wird beschnitten. Eine Kurve wie ``OutBack`` schiesst
    über das Ziel hinaus, und eine Farbkomponente über 1 ist keine Farbe mehr.
    """
    step = max(0.0, min(fraction, 1.0))
    return tuple(a + (b - a) * step for a, b in zip(start, end, strict=True))


def tween(
    owner: QObject,
    *,
    on_step: Callable[[float], None],
    duration: int = ACCENT_MS,
    curve: QEasingCurve.Type = CURVE,
    on_done: Callable[[], None] | None = None,
) -> QVariantAnimation | None:
    """Läuft von 0 auf 1 und ruft ``on_step`` bei jedem Bild.

    Der Unterschied zu allem darüber: Hier bewegt sich **kein Widget**. Was
    ``on_step`` mit der Zahl tut, entscheidet der Aufrufer — eine Farbe an
    einem VTK-Aktor mischen, einen Bogen wachsen lassen, einen Schatten
    nachziehen. ``motion`` weiss davon nichts und soll es nicht wissen.

    **Ist Bewegung abgeschaltet, bekommt ``on_step`` genau einmal die 1.0.**
    Das ist die eigentliche Zusage dieser Funktion: Der Endzustand steht immer,
    auch offscreen, auch bei ``SOLIDON3D_MOTION=aus``. Ein Aufrufer, der die
    Zielfarbe nur über die Animation setzt, ist damit trotzdem richtig — und
    kein Test misst je eine halb gemischte Farbe.

    ``owner`` hält die Animation am Leben; fällt er weg, fällt sie mit (die
    Falle aus ``.claude/rules/oberflaeche.md``).
    """
    if not animations_enabled():
        on_step(1.0)
        if on_done is not None:
            on_done()
        return None
    animation = QVariantAnimation(owner)
    animation.setDuration(duration)
    animation.setEasingCurve(curve)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.valueChanged.connect(lambda value: on_step(float(value)))

    # Der Endwert kommt aus der Kurve und wird hier **nicht** noch einmal
    # gesetzt. Gemessen an zwölf Läufen (1 bis 220 ms, `OutCubic` und
    # `OutBack`): Qt meldet die 1,0 immer als letzten `valueChanged`. Ein
    # zweiter Aufruf wäre kein Gürtel zum Hosenträger, sondern ein zusätzliches
    # Neuzeichnen der ganzen Szene für einen Wert, der schon steht.
    if on_done is not None:
        animation.finished.connect(on_done)
    animation.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


__all__ = [
    "ACCENT_MS",
    "CURVE",
    "MEDIUM_MS",
    "SHORT_MS",
    "animations_enabled",
    "fade_in",
    "fade_out",
    "flash",
    "mix",
    "reveal",
    "switch",
    "tween",
]
