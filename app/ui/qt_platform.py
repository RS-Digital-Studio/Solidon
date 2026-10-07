"""Welche Qt-Plattform und welches Eingabemodul gelten — entschieden, bevor es eine Anwendung gibt.

Das Eingabemodul steht bei :func:`input_method_environment` (RM-062); hier
zuerst die Plattform.

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
import shutil
import subprocess
import sys
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Final

from app.core.log import get_logger
from app.core.process import run_limited, trusted_cwd
from app.core.report import INPUT_BEFORE_VARIABLES, QT_PLATFORM_BEFORE_VARIABLE, QT_PLATFORM_UNSET

_log = get_logger(__name__)

#: Die Plattform, auf der die 3D-Ansicht ihr Fenster bekommt.
X11: Final = "xcb"
#: Dasselbe in einer Wayland-Sitzung: X11 zuerst, Wayland als Netz darunter.
X11_THEN_WAYLAND: Final = "xcb;wayland"

#: Was ein Fcitx-Nutzer in ``QT_IM_MODULE`` oder ``QT_IM_MODULES`` stehen hat.
_FCITX: Final = frozenset({"fcitx", "fcitx5"})
#: Das Eingabemodul, das Qt selbst mitbringt und Fcitx5 ab Werk bedient
#: (``ibusfrontend``, dazu ``org.freedesktop.portal.IBus`` für Flatpaks).
IBUS: Final = "ibus"
#: Der Name, unter dem Fcitx5 auf dem Sitzungsbus als IBus-Portal antwortet.
IBUS_PORTAL: Final = "org.freedesktop.portal.IBus"
#: Wie lange die Frage danach vor dem Start höchstens dauern darf.
_PORTAL_QUESTION_SECONDS: Final = 2.0


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


def input_method_environment(
    platform: str, environ: Mapping[str, str], modules: Collection[str], *, portal: bool
) -> dict[str, str]:
    """Was vor dem Anwendungsaufbau in der Umgebung stehen soll, damit Fcitx Eingaben bekommt.

    **Ein Fcitx-Nutzer tippte ins Leere** (RM-062, gemessen am ausgelieferten
    Flatpak 0.5.3): Das Qt aus PySide6 bringt nur die Eingabemodule
    ``compose``, ``ibus`` und ``qtvirtualkeyboard`` mit. Mit
    ``QT_IM_MODULE=fcitx`` fand Qt kein Modul, fiel auf ``compose`` zurück,
    und Fcitx bekam keine Eingabesitzung — kein Kandidatenfenster, keine
    Umschaltung. Mit ``ibus`` legt Fcitx5 über seine IBus-Schnittstelle eine
    an.

    Fcitx steht auf drei Arten in der Umgebung, und Qt liest
    ``QT_IM_MODULES`` vor ``QT_IM_MODULE`` (``requested()``, Qt 6.11): eine
    Liste wie ``wayland;fcitx`` (Fcitx-Wiki für GNOME und Sway) bekommt
    ``ibus`` angehängt, ein einzelnes ``fcitx`` wird ``ibus``, und unter KDE,
    wo nur ``XMODIFIERS=@im=fcitx`` steht, kommt ``QT_IM_MODULE=ibus`` dazu —
    die Anwendung läuft dort über XWayland und bekäme sonst ``compose``.

    **Außerhalb des Sandkastens prüft Qt für IBus ``ibus-daemon`` im PATH**
    (``QIBusPlatformInputContextPrivate``), und ein reines Fcitx5-System hat
    keinen. ``portal`` sagt, ob ``IBUS_USE_PORTAL`` dazukommt: Dann spricht
    Qt ``org.freedesktop.portal.IBus`` auf dem Sitzungsbus an, den Fcitx5
    trägt. Gesetzt wird es nur, wo der Name antwortet
    (:func:`fcitx_answers_as_ibus_portal`) — ein gültiger, aber stummer
    IBus-Kontext nähme Qt den Rückfall auf ``compose`` und damit die toten
    Tasten. Im Flatpak nimmt Qt das Portal von selbst.

    Nichts geschieht, wo ein Fcitx-Modul beiliegt, keins für IBus, oder die
    Umgebung schon ein mitgeliefertes Modul nennt. ``modules`` sind die
    Dateinamen in ``platforminputcontexts`` (:func:`input_modules`).
    """
    if not platform.startswith("linux"):
        return {}
    names = [name.casefold() for name in modules]
    if any("fcitx" in name for name in names) or not any(IBUS in name for name in names):
        return {}

    def shipped(entry: str) -> bool:
        return any(entry in name for name in names)

    listed = [
        entry.strip().casefold()
        for entry in environ.get("QT_IM_MODULES", "").split(";")
        if entry.strip()
    ]
    single = environ.get("QT_IM_MODULE", "").strip().casefold()
    only_xim = (
        not single and "@im=fcitx" in environ.get("XMODIFIERS", "").replace(" ", "").casefold()
    )
    chosen: dict[str, str] = {}
    if listed:
        if any(entry in _FCITX for entry in listed) and not any(map(shipped, listed)):
            chosen["QT_IM_MODULES"] = environ["QT_IM_MODULES"].strip().rstrip(";") + ";" + IBUS
    elif single in _FCITX or only_xim:
        chosen["QT_IM_MODULE"] = IBUS
    if chosen and portal and not environ.get("IBUS_USE_PORTAL", "").strip():
        chosen["IBUS_USE_PORTAL"] = "1"
    return chosen


def fcitx_answers_as_ibus_portal() -> bool:
    """Ob auf dem Sitzungsbus jemand :data:`IBUS_PORTAL` trägt — Fcitx5 tut es ab Werk.

    Gefragt über ``dbus-send``, vor Qt und ohne eigene D-Bus-Bibliothek; ohne
    Werkzeug, Bus oder Antwort binnen :data:`_PORTAL_QUESTION_SECONDS` heißt
    es nein, und Qt bleibt beim Weg über ``ibus-daemon``.
    """
    tool = shutil.which("dbus-send")
    if tool is None:
        return False
    try:
        answer = run_limited(
            [
                tool,
                "--session",
                "--print-reply",
                "--dest=org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus.NameHasOwner",
                f"string:{IBUS_PORTAL}",
            ],
            cwd=trusted_cwd(),
            timeout=_PORTAL_QUESTION_SECONDS,
            output_limit=4096,
            graphical=True,
        )
    except OSError, subprocess.SubprocessError:
        return False
    return answer.returncode == 0 and b"boolean true" in answer.stdout


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


def prefer_an_input_method_qt_has() -> dict[str, str]:
    """Setzt die Eingabevariablen in der eigenen Umgebung und hält fest, was dort stand.

    Vor ``QApplication``, dieselbe Bauart wie :func:`prefer_x11_for_the_viewport`:
    Steht ``ibus`` erst einmal dort, ändert :func:`input_method_environment`
    beim zweiten Aufruf nichts mehr, und die gemerkten Vorwerte bleiben für
    den Fehlerbericht (``report.INPUT_BEFORE_VARIABLES``). Nach dem Bus wird
    nur gefragt, wenn sich etwas ändert und Qt nicht schon im Flatpak läuft.
    """
    modules = input_modules()
    chosen = input_method_environment(sys.platform, os.environ, modules, portal=False)
    if not chosen:
        return {}
    if not Path("/.flatpak-info").exists() and fcitx_answers_as_ibus_portal():
        chosen = input_method_environment(sys.platform, os.environ, modules, portal=True)
    for name, value in chosen.items():
        before = os.environ.get(name, "").strip()
        os.environ[name] = value
        os.environ[INPUT_BEFORE_VARIABLES[name]] = before or QT_PLATFORM_UNSET
    _log.info("qt input method set for fcitx: %s", chosen)
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
