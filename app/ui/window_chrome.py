"""Das Fensterchrom trägt die Farben der Anwendung (G15).

Windows malt Titelleiste und Rahmen selbst, und zwar in seinen eigenen
Farben: ``#202020`` im dunklen Systemthema, ``#f3f3f3`` im hellen. Darunter
beginnt dann die Anwendung mit ``#343a45`` beziehungsweise ``#e7e9ed`` — ein
sichtbarer Absatz quer über die Fensteroberkante, an dem das Fenster in zwei
Teile zerfällt.

Seit Windows 11 lässt sich das sagen, **ohne die Titelleiste selbst zu
malen**. Genau das ist der Punkt: Eine eigene Titelleiste kostet Verschieben,
Andocken, Systemmenü, Mehrschirmbetrieb und Barrierefreiheit — alles Dinge,
die Windows heute richtig macht und die dann wir richtig machen müssten. Und
sie ersetzt die Akzentfarbe, die der Kunde eingestellt hat, durch eine, die
wir gewählt haben. Hier wird nichts ersetzt: Windows zeichnet weiter, es
bekommt nur gesagt, in welcher Farbe.

Gemessen am 30.08.2026 (Build 26200), je Thema an einem Bildschirmausschnitt:

===========  ====================  ====================
Thema        Titelleiste vorher    nachher
===========  ====================  ====================
dunkel       ``(32, 32, 32)``      ``(52, 58, 69)``
hell         ``(243, 243, 243)``   ``(231, 233, 237)``
===========  ====================  ====================

Beide Male exakt der ``window``-Token des Themas.

**Gelesen wird die Palette, nicht ein Themenname.** Sie trägt dieselben Werte
(gemessen: ``QPalette.Window`` ist ``#343a45`` beziehungsweise ``#e7e9ed``),
und sie meldet ihren Wechsel von selbst — ``ApplicationPaletteChange``. Damit
braucht diese Datei keinen Aufruf im Fenster: Wer das Thema umstellt, stellt
die Palette um, und das Chrom folgt. Ein Aufruf, den jemand vergessen kann,
entsteht gar nicht erst.

**Was nicht wirkt, und warum es nicht hier steht:** ``Mica`` (Attribut 38)
wird angenommen und bleibt unsichtbar — das Material scheint durch die
Fensterfläche, und die ist bei einer Anwendung mit 3D-Ansicht undurchsichtig.
``DWMWA_BORDER_COLOR`` ebenso: Das Fenster hat seitlich keinen Rahmen (Rand 0
gemessen), also gibt es nichts zu färben. Beide sind deshalb **nicht** gesetzt;
ein Aufruf, der nichts bewirkt, sieht in einem Jahr aus wie einer, der etwas
bewirkt, und niemand traut sich, ihn zu entfernen.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Any

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from app.core.log import get_logger

_log = get_logger(__name__)

#: Die Fläche der Titelleiste. Seit Windows 11 Build 22000.
_CAPTION_COLOR = 35
#: Ihr Text. Ohne ihn stünde dunkler Text auf dunkler Leiste, sobald das
#: Systemthema hell ist und unseres dunkel.
_TEXT_COLOR = 36

#: Ab diesem Build kennt Windows die beiden Attribute. Darunter antwortet
#: ``DwmSetWindowAttribute`` mit einem Fehler, den niemand sehen würde —
#: deshalb wird vorher gefragt und nicht hinterher geprüft.
_MIN_BUILD = 22000

#: Als allgemeine Zeichenkette halten, damit die Typprüfung den Windows-Zweig
#: auch auf Linux und macOS prüft.
_PLATFORM: str = sys.platform


def available() -> bool:
    """Ob dieses Windows die Attribute kennt. Auf Linux und macOS nie."""
    if _PLATFORM != "win32":
        return False
    version = getattr(sys, "getwindowsversion", None)
    return version is not None and version().build >= _MIN_BUILD


#: Einmal geladen, nicht je Fenster. Bei neunzehn offenen Dialogen wären es
#: sonst neunzehn Ladevorgänge je Themenwechsel — für dieselbe Bibliothek.
_library: Any = None


def _dwm() -> Any:
    """dwmapi beim ersten Mal laden und behalten."""
    global _library
    if _library is None:
        loader = getattr(ctypes, "WinDLL", None)
        if loader is None:
            return None
        try:
            _library = loader("dwmapi")
        except OSError:  # pragma: no cover — auf Windows ist sie da
            _log.debug("dwmapi not available", exc_info=True)
            return None
    return _library


def _colorref(colour: QColor) -> int:
    """Qt hält RGB, Windows will ``0x00BBGGRR`` — die Reihenfolge dreht sich."""
    return (colour.blue() << 16) | (colour.green() << 8) | colour.red()


def paint_chrome(window: QWidget) -> bool:
    """Titelleiste und ihren Text auf die Farben der Palette setzen.

    Gibt zurück, ob es getan wurde — falsch heißt: dieses System kann es
    nicht, und das Fenster sieht aus wie bisher. Kein Fehler, kein Dialog: Ein
    Kunde auf Windows 10 bekommt Windows' Titelleiste, und die ist nicht
    kaputt, nur unbunter.
    """
    if not available() or not window.isWindow():
        return False
    palette = window.palette()
    library = _dwm()
    if library is None:
        return False
    try:
        handle = wintypes.HWND(int(window.winId()))
        for attribute, role in (
            (_CAPTION_COLOR, QPalette.ColorRole.Window),
            (_TEXT_COLOR, QPalette.ColorRole.WindowText),
        ):
            value = ctypes.c_int(_colorref(palette.color(role)))
            library.DwmSetWindowAttribute(
                handle, ctypes.c_uint(attribute), ctypes.byref(value), ctypes.sizeof(value)
            )
    except Exception:  # pragma: no cover — eine fehlende dwmapi ist kein Grund
        _log.debug("window chrome not painted", exc_info=True)
        return False
    return True


def paint_every_window() -> int:
    """Alle offenen Fenster nachziehen. Gibt zurück, wie viele es waren."""
    return sum(
        1
        for window in QApplication.topLevelWidgets()
        if window.isVisible() and paint_chrome(window)
    )


class ChromeWatcher(QObject):
    """Malt das Chrom jedes Fensters, sobald es erscheint — und bei Themenwechsel.

    **Eine Stelle statt neunzehn.** Die Anwendung hat ein Hauptfenster und
    achtzehn Dialoge, und jeder weitere käme dazu — eine Liste von Aufrufen
    vergisst den nächsten, und zwar still: Ein Dialog mit Windows-Titelleiste
    sieht nicht kaputt aus, nur fremd. Der Filter kann nichts vergessen, weil
    er nicht aufzählt, sondern zuhört.

    Zwei Ereignisse tragen ihn. ``Show``, weil es vor dem ersten Anzeigen kein
    Fensterhandle gibt, an das sich etwas setzen ließe. Und
    ``ApplicationPaletteChange``, weil das Umstellen des Themas genau das
    auslöst — dadurch braucht ``action_theme`` im Fenster keine Zeile für das
    Chrom, und niemand kann sie beim nächsten Umbau vergessen.
    """

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt-Name
        kind = event.type()
        if kind == QEvent.Type.ApplicationPaletteChange:
            # **Nur am Anwendungsobjekt.** Qt stellt das Ereignis jedem
            # Empfänger einzeln zu — gemessen sechs Feuerungen bei zwei
            # Fenstern und zwanzig Kindern. Gemalt werden müssen die Fenster
            # aber einmal, nicht einmal je Widget, das zufällig zuhört.
            if watched is QApplication.instance():
                paint_every_window()
        elif kind == QEvent.Type.Show and isinstance(watched, QWidget) and watched.isWindow():
            paint_chrome(watched)
        return False


def install(application: Any) -> ChromeWatcher | None:
    """Den Wächter anmelden und zurückgeben — ``None``, wo es nichts zu tun gibt.

    Der Rückgabewert bekommt die Anwendung als Elternteil: Ein ``QObject``,
    auf das niemand zeigt, räumt Python weg, und der Filter verschwindet
    mitsamt ihm.
    """
    if not available():
        return None
    watcher = ChromeWatcher()
    watcher.setParent(application)
    application.installEventFilter(watcher)
    return watcher
