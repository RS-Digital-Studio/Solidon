"""Welche Qt-Plattform die 3D-Ansicht braucht — entschieden, bevor es eine Anwendung gibt.

Die 3D-Ansicht ist eine eigene Grafikfläche (rendercanvas, wgpu) in einem
Qt-Fenster, und dieser Fensterweg ist nur unter X11 und Xwayland geprüft.
Mit dem früheren VTK-Renderer war Wayland tödlich: Seine Qt-Anbindung kannte
nur X11 und riss den Prozess mit (``std::bad_array_new_length``; Martin
Donecker, CachyOS, 28.08.2026). Auch rendercanvas verwendet für Qt unter Linux
ausschließlich X11: Sein Wayland-Zweig in ``_get_surface_ids`` ist deaktiviert.
Deshalb braucht dieser Renderer X11 beziehungsweise Xwayland.

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

import importlib.util
import os
import sys
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Final

from app.core.log import get_logger
from app.core.report import QT_IM_BEFORE_VARIABLE, QT_PLATFORM_BEFORE_VARIABLE, QT_PLATFORM_UNSET

_log = get_logger(__name__)

#: Die Plattform, auf der die 3D-Ansicht ihr Fenster bekommt.
X11: Final = "xcb"
#: Dasselbe in einer Wayland-Sitzung: X11 zuerst, Wayland als Netz darunter.
X11_THEN_WAYLAND: Final = "xcb;wayland"

#: Was ein Fcitx-Nutzer in ``QT_IM_MODULE`` stehen hat.
_FCITX: Final = frozenset({"fcitx", "fcitx5"})
#: Das Eingabemodul, das Qt selbst mitbringt und Fcitx5 ab Werk bedient
#: (``ibusfrontend``, dazu ``org.freedesktop.portal.IBus`` für Flatpaks).
IBUS: Final = "ibus"


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


def im_module(platform: str, environ: Mapping[str, str], modules: Collection[str]) -> str | None:
    """Was ``QT_IM_MODULE`` vor dem Anwendungsaufbau bekommen soll — oder ``None``.

    **Ein Fcitx-Nutzer tippte ins Leere** (RM-062, gemessen am ausgelieferten
    Flatpak 0.5.3): Das Qt aus PySide6 bringt nur die Eingabemodule
    ``compose``, ``ibus`` und ``qtvirtualkeyboard`` mit. Mit
    ``QT_IM_MODULE=fcitx`` fand Qt kein Modul, fiel auf ``compose`` zurück,
    und Fcitx bekam keine Eingabesitzung — kein Kandidatenfenster, keine
    Umschaltung. Mit ``ibus`` legt Fcitx5 über seine IBus-Schnittstelle eine
    an, auch aus dem Sandkasten heraus.

    Gesetzt wird nur, wo es hilft: unter Linux, bei ``fcitx`` oder ``fcitx5``,
    wenn kein Fcitx-Modul beiliegt und ein IBus-Modul schon. Eine Liste in
    ``QT_IM_MODULES`` lässt Qt selbst der Reihe nach probieren; dort gibt es
    nichts zu tun. ``modules`` sind die Dateinamen in
    ``platforminputcontexts`` (:func:`input_modules`).
    """
    if not platform.startswith("linux"):
        return None
    wanted = environ.get("QT_IM_MODULE", "").strip().casefold()
    if wanted not in _FCITX or environ.get("QT_IM_MODULES", "").strip():
        return None
    names = [name.casefold() for name in modules]
    if any("fcitx" in name for name in names) or not any(IBUS in name for name in names):
        return None
    return IBUS


def input_modules() -> tuple[str, ...]:
    """Die Dateinamen der Eingabemodule, die das mitgelieferte Qt laden kann — ohne Qt zu laden."""
    spec = importlib.util.find_spec("PySide6")
    locations = list(spec.submodule_search_locations or ()) if spec is not None else []
    found: list[str] = []
    for location in locations:
        folder = Path(location) / "Qt" / "plugins" / "platforminputcontexts"
        try:
            found.extend(entry.name for entry in folder.iterdir())
        except OSError:
            continue
    return tuple(found)


def prefer_an_input_method_qt_has() -> str | None:
    """Setzt das Eingabemodul in der eigenen Umgebung und hält fest, was dort stand.

    Vor ``QApplication``, dieselbe Bauart wie :func:`prefer_x11_for_the_viewport`:
    Steht ``ibus`` erst einmal dort, gibt :func:`im_module` beim zweiten
    Aufruf ``None`` zurück, und der gemerkte Vorwert bleibt für den
    Fehlerbericht.
    """
    if not sys.platform.startswith("linux"):
        return None
    chosen = im_module(sys.platform, os.environ, input_modules())
    if chosen is None:
        return None
    before = os.environ.get("QT_IM_MODULE", "").strip()
    os.environ["QT_IM_MODULE"] = chosen
    os.environ[QT_IM_BEFORE_VARIABLE] = before or QT_PLATFORM_UNSET
    _log.info("qt input method set to %s, no %s module ships with qt", chosen, before)
    return chosen


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
