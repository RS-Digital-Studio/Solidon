"""Welche Qt-Plattform die 3D-Ansicht braucht — entschieden, bevor es eine Anwendung gibt.

Die 3D-Ansicht ist ein VTK-Fenster in einem Qt-Fenster, und VTKs Qt-Anbindung
(``vtkmodules.qt.QVTKRenderWindowInteractor``) kennt nur X11: Sie übergibt
``winId()`` als X-Window an ``vtkXOpenGLRenderWindow``. Läuft Qt selbst auf
Wayland, ist diese Nummer kein X-Fenster — VTK findet kein Display, fällt auf
EGL zurück, zeichnet nichts und reißt den Prozess mit
(``std::bad_array_new_length``; Martin Donecker, CachyOS, 28.08.2026).

Qt 6 wählt ohne ``QT_QPA_PLATFORM`` aber genau so: Sobald ``WAYLAND_DISPLAY``
gesetzt ist **oder** ``XDG_SESSION_TYPE`` auf ``wayland`` steht, versucht es
``wayland`` vor ``xcb`` — auch wenn ``DISPLAY`` und damit Xwayland da sind
(``qguiapplication.cpp``, ``createPlatformIntegration``, Qt 6.8 bis 6.11
gelesen). Das Flatpak umgeht das über sein Manifest (nur ``--socket=x11``,
Flatpak entfernt ``WAYLAND_DISPLAY``); AppImage und Archiv haben kein Manifest,
und so entscheidet es hier: **Gibt es ein X11-Display, läuft Qt darauf.**
Flathub macht es bei FreeCAD genauso (``--env=QT_QPA_PLATFORM=xcb``).

Eine reine Funktion mit der Plattform als Parameter, wie ``kern.md`` es für
jede Plattformkette verlangt — der Zweig zündet nur in einer Wayland-Sitzung,
und die sieht weder eine Windows-Maschine noch die Linux-CI unter Xvfb.
Kein Qt-Import: Das Modul läuft, bevor Qt geladen ist, und die Tests prüfen
die Weiche ohne Fenster.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from typing import Final

from app.core.log import get_logger
from app.core.report import QT_PLATFORM_BEFORE_VARIABLE, QT_PLATFORM_UNSET

_log = get_logger(__name__)

#: Die Plattform, auf der VTK sein Fenster bekommt.
X11: Final = "xcb"
#: Dasselbe in einer Wayland-Sitzung: X11 zuerst, Wayland als Netz darunter.
X11_THEN_WAYLAND: Final = "xcb;wayland"


def qpa_platform(platform: str, environ: Mapping[str, str]) -> str | None:
    """Was ``QT_QPA_PLATFORM`` vor dem Anwendungsaufbau bekommen soll — oder
    ``None``, wenn die Umgebung bleibt, wie sie ist.

    X11 genau dann, wenn Linux ein X11-Display anbietet (``DISPLAY``) und
    entweder nichts gesetzt ist oder etwas, das mit ``wayland`` beginnt. Ein
    global gesetztes ``QT_QPA_PLATFORM=wayland`` gilt allen Qt-Programmen und
    meint nicht diese Anwendung, die auf Wayland kein Bild hat; ``offscreen``,
    ``minimal``, ``vnc`` und ``xcb`` selbst bleiben unangetastet — das sind
    Werkzeuge und Tests, die wissen, was sie tun. Ohne ``DISPLAY`` gibt es
    nichts zu wählen: Dann fehlt Xwayland, Qt nimmt Wayland, und die Ansicht
    sagt, was zu tun ist (``viewport.unavailable_hint``).

    **In einer Wayland-Sitzung steht Wayland hinter X11 in der Liste.** Qt
    geht sie der Reihe nach durch (``init_platform``) und bricht erst ab, wenn
    jeder Name scheitert. Das X11-Plugin braucht neun Bibliotheken vom
    System, die das Linux-Paket nicht mitbringt — ``libxcb-cursor0`` fehlt auf
    einem Ubuntu-GNOME regelmäßig, und Qt sagt es seit 6.5 in einer eigenen
    Warnung. Mit ``xcb`` allein hieße das „no Qt platform plugin could be
    initialized" und kein Start; mit Wayland dahinter startet die Anwendung
    ohne 3D-Ansicht, und der Hinweis nennt die Bibliothek.
    """
    if not platform.startswith("linux"):
        return None
    if not environ.get("DISPLAY", "").strip():
        return None
    wanted = environ.get("QT_QPA_PLATFORM", "").strip()
    if wanted and not wanted.casefold().startswith("wayland"):
        return None
    wayland_session = (
        bool(environ.get("WAYLAND_DISPLAY", "").strip())
        or environ.get("XDG_SESSION_TYPE", "").strip().casefold() == "wayland"
        or wanted.casefold().startswith("wayland")
    )
    return X11_THEN_WAYLAND if wayland_session else X11


def prefer_x11_for_the_viewport() -> str | None:
    """Setzt die Plattform in der eigenen Umgebung und hält fest, was dort stand.

    Vor ``QApplication`` und genau einmal wirksam: Steht ``xcb`` erst einmal
    dort, gibt :func:`qpa_platform` beim nächsten Aufruf ``None`` zurück, und
    der gemerkte Vorwert bleibt. Der Fehlerbericht liest ihn und schreibt
    „von Solidon3D gesetzt, vorher …" hinter die Plattform — wer den Bericht
    liest, soll sehen, dass die Anwendung gewählt hat und nicht der Nutzer.
    ``-platform`` auf der Kommandozeile schlägt die Variable weiterhin; das
    ist der Ausweg für den, der Wayland ausdrücklich will.
    """
    chosen = qpa_platform(sys.platform, os.environ)
    if chosen is None:
        return None
    before = os.environ.get("QT_QPA_PLATFORM", "").strip()
    os.environ["QT_QPA_PLATFORM"] = chosen
    os.environ[QT_PLATFORM_BEFORE_VARIABLE] = before or QT_PLATFORM_UNSET
    _log.info("qt platform set to %s for the 3d view (before: %s)", chosen, before or "unset")
    return chosen
