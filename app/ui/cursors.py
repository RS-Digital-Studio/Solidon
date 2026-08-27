"""Mauszeiger für den Viewport (Bauplan §19.3, AGENTS.md Regel 18).

Der Zeiger ist die einzige Stelle der Oberfläche, die **immer** dort ist, wo
der Nutzer hinsieht. Bisher war er überall derselbe Pfeil: beim Drehen, beim
Messen, beim Bemalen, über einer Bohrung. Ein Werkzeug, das man eingeschaltet
hat, war danach nur noch am gedrückten Knopf in der Leiste zu erkennen — und
den sieht niemand an, während er im Bild arbeitet.

Zwei Regeln halten das brauchbar:

* **Nicht jede Form wird selbst gezeichnet.** Wo das System eine Form hat, die
  jeder kennt — die geschlossene Hand beim Schieben, das Verschiebekreuz am
  Griff —, ist sie die bessere: Sie folgt der eingestellten Zeigergröße und dem
  Hochkontrastmodus, unsere täte das nicht. Eigene Zeichnungen gibt es nur
  dort, wo keine Standardform die Sache trifft, und für die eine Rolle, die
  bewusst nach Solidon aussehen soll (:data:`SELECT`).
* **Jeder eigene Zeiger trägt einen dunklen Rand.** Der Akzent ist hell
  (45,9 % Helligkeit); über einem *gewählten* Körper liegt er auf sich selbst
  und wäre ohne Kontur verschwunden. Denselben Grund hat jeder Systemzeiger
  der Welt einen weißen oder schwarzen Saum.

**Die Größe kommt zuerst vom System.** Auf Linux steht sie in
``XCURSOR_SIZE``, und wer seine Zeiger dort auf 24 stellt, meint alle Zeiger
— auch unsere. Nennt das System keine (Windows, macOS), gilt wie bisher die
Zeilenhöhe mal :data:`SCALE`, so wie bei :mod:`app.ui.icons`.

Diese Reihenfolge ist seit dem 27.08.2026 so herum, und der Anlass war ein
Kunde: „Der Cursor ist SEHR gross und viel zu ungenau." Auf einem Schirm mit
großer Textskalierung ergab die Bindung an die Schrift Zeiger von sechzig
Punkten, wo Systemzeiger vierundzwanzig bis zweiunddreißig messen — wer die
Schrift vergrößert, hat damit nichts über seine Zeiger gesagt.

**Was hier bewusst nicht steht: der Pinselkreis.** Der Radius des Pinsels ist
ein Maß in Millimetern (§20). Ein Mauszeiger hat eine feste Pixelgröße und
weiß nichts von der Kamera; beim ersten Zoom würde er die Größe behaupten, die
er nicht mehr hat. Ein Ring, der den Pinsel wirklich zeigt, gehört in die
Szene, nicht an den Zeiger.
"""

from __future__ import annotations

import os
import subprocess
import sys
from importlib import import_module
from typing import Final

from PySide6.QtCore import QByteArray, QPoint, QSize, Qt
from PySide6.QtGui import QCursor, QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget

from app.ui.theme import THEMES

#: Wie viel größer als die Zeilenhöhe ein Zeiger gezeichnet wird. Deutlich
#: größer als der Faktor der Symbole: ein Zeiger steht allein im Bild und nicht
#: neben einem Wort, das seine Größe vorgibt. Bei einer Zeilenhöhe von 16
#: ergibt das 32 Punkte — die Größe, die Windows für seine eigenen setzt.
SCALE: Final = 2.0

#: Obergrenze in Pixeln. Windows lehnt zu große Zeiger ab und zeigt dann gar
#: keinen — ein unsichtbarer Zeiger ist schlimmer als ein kleiner.
MAX_SIZE: Final = 64

_HEAD: Final = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" '
    'fill="none" stroke="{edge}" stroke-width="4.2" '
    'stroke-linecap="round" stroke-linejoin="round">'
)

#: Der zweite Durchgang zeichnet dieselben Pfade dünner in der Akzentfarbe
#: über den dicken dunklen — daraus entsteht der Saum, ohne dass jede Form
#: zweimal beschrieben werden muss.
#:
#: Beide Stärken sind das Ergebnis eines Kontaktbogens, nicht einer Rechnung:
#: bei 2,6 zu 1,4 blieb von Bogen und Ebene bei Zeigergröße ein Fleck. Ein
#: Zeiger wird nicht gelesen, er wird an seiner Silhouette erkannt.
_FILL: Final = (
    '<g fill="none" stroke="{accent}" stroke-width="2.2" '
    'stroke-linecap="round" stroke-linejoin="round">{body}</g>'
)

#: Zeichnung und Griffpunkt je Rolle. Der Griffpunkt ist der Bildpunkt, der
#: „gemeint" ist — beim Fadenkreuz die Mitte, beim Pfeil die Spitze. Er steht
#: in denselben 32er-Einheiten wie das SVG und wird mitskaliert.
SHAPES: Final[dict[str, tuple[str, tuple[float, float]]]] = {
    # Der Pfeil für den Ruhezustand über dem Bild: dieselbe Silhouette, die
    # jeder kennt, damit niemand raten muss, wo er greift — nur in unserer
    # Farbe. Die Spitze sitzt im Ursprung.
    "select": (
        '<path d="M5 3.5 5 22 10 17.5 13.5 25 17 23.5 13.5 16.5 20.5 16z" '
        'fill="{accent}" stroke-linejoin="round" />',
        (5.0, 3.5),
    ),
    # Drehen: ein offener Kreis mit einer kräftigen Spitze am Ende. Der Bogen
    # muss weit offen sein — ein fast geschlossener Ring wird bei Zeigergröße
    # zum Punkt, und die Spitze ist das Einzige, was die Drehung erzählt.
    "rotate": (
        '<path d="M25 12a10.5 10.5 0 1 0 2 7" /><path d="M27.5 11 27 19.5 19 18" />',
        (16.0, 16.0),
    ),
    # Zoomen: die Lupe, ohne Plus oder Minus — die Richtung entscheidet die
    # Bewegung, und ein festes Vorzeichen wäre die Hälfte der Zeit falsch.
    "zoom": (
        '<circle cx="14" cy="14" r="8" /><path d="M20 20 27 27" />',
        (14.0, 14.0),
    ),
    # Messen: Fadenkreuz mit einem Loch in der Mitte. Voll gezeichnet
    # verdeckt der Zeiger genau den Punkt, den er angibt.
    "measure": (
        '<path d="M16 3v9M16 20v9M3 16h9M20 16h9" /><circle cx="16" cy="16" r="2.4" />',
        (16.0, 16.0),
    ),
    # Schnitt: die Schnittlinie quer durchs Bild, darüber und darunter je eine
    # Hälfte, die auseinandergeht. Der Körper aus dem Werkzeugsymbol war die
    # bessere Bildidee und die schlechtere Silhouette — bei Zeigergröße blieb
    # ein Sechseck mit Strich, das nichts mehr erzählte.
    "section": (
        '<path d="M2 16h28" /><path d="M9 11 16 5l7 6" /><path d="M9 21 16 27l7-6" />',
        (16.0, 16.0),
    ),
    # Formen: ein Ring auf der Spitze eines Stiels — der Pinsel greift eine
    # Fläche, kein einzelner Punkt. (Die Rolle „paint" stand daneben, bis der
    # Punkt-Radius-Pinsel fiel — Färben ist seither eine Operation am
    # Merkmal und braucht keinen eigenen Zeiger.)
    "sculpt": (
        '<path d="M4 28 12 20" /><circle cx="19" cy="13" r="8" />',
        (4.0, 28.0),
    ),
    # Über einem erkannten Merkmal: derselbe Pfeil, aber mit einem Ring an der
    # Spitze — „hier ist etwas, das einen Namen hat".
    "feature": (
        '<path d="M5 3.5 5 20 9.5 16 12 21.5 14.5 20.5 12 15.5 17.5 15z" '
        'fill="{accent}" stroke-linejoin="round" />'
        '<circle cx="22" cy="22" r="5" />',
        (5.0, 3.5),
    ),
}

#: Rollen, die eine Systemform bekommen statt einer eigenen Zeichnung. Der
#: Grund steht oben: eine bekannte Form, die der Zeigereinstellung des Systems
#: folgt, ist mehr wert als eine hübsche, die es nicht tut.
SYSTEM: Final[dict[str, Qt.CursorShape]] = {
    "pan": Qt.CursorShape.OpenHandCursor,
    "panning": Qt.CursorShape.ClosedHandCursor,
    "move": Qt.CursorShape.SizeAllCursor,
    "busy": Qt.CursorShape.BusyCursor,
    # Das Fadenkreuz beim Zeichnen. Auf der Zeichenfläche stand der Pfeil,
    # gleich ob ein Werkzeug lief oder nicht — wer nach dem Setzen von drei
    # Punkten den mittleren anklickte, um ihn zu ziehen, setzte einen vierten
    # darauf, und zu sehen war das nicht. Systemform und keine eigene
    # Zeichnung: das Fadenkreuz ist die bekannteste Form überhaupt für „hier
    # entsteht etwas", und es folgt der Zeigergröße des Systems.
    "draw": Qt.CursorShape.CrossCursor,
}

#: Gebaute Zeiger, nach Rolle und Größe. Ein Zeiger wird bei jeder
#: Mausbewegung gesetzt; ihn dabei jedes Mal aus SVG zu rastern, wäre die
#: teuerste Zeile der Anwendung.
_CACHE: dict[tuple[str, int], QCursor] = {}


def cursor(role: str, widget: QWidget) -> QCursor:
    """Der Zeiger einer Rolle, in der Größe der Schrift dieses Widgets.

    Unbekannte Rollen geben den gewöhnlichen Pfeil zurück statt zu scheitern:
    Ein Zeiger ist Beiwerk, und eine Ansicht ohne ihn ist immer noch bedienbar.
    """
    shape = SYSTEM.get(role)
    if shape is not None:
        return QCursor(shape)
    if role not in SHAPES:
        return QCursor(Qt.CursorShape.ArrowCursor)

    size = _size_for(widget)
    cached = _CACHE.get((role, size))
    if cached is None:
        cached = _build(role, size)
        _CACHE[(role, size)] = cached
    return cached


def apply_default_cursor(window: QWidget) -> None:
    """Gibt einem Fenster den Auswahlzeiger — und damit allen Panels darin.

    Qt vererbt den Zeiger an jedes Kind, das keinen eigenen gesetzt hat. Genau
    das ist hier erwünscht: Listen, Bäume, Beschriftungen und Flächen erben
    ihn, während ein Eingabefeld seinen Textbalken behält und ein Splitter
    seinen Doppelpfeil — beide setzen ihren selbst und werden deshalb nicht
    überschrieben.

    Ohne diesen Aufruf hing der Zeiger allein am Viewport, und links daneben
    stand der Pfeil des Systems: dieselbe Anwendung mit zwei Handschriften.
    """
    window.setCursor(cursor("select", window))


def known() -> tuple[str, ...]:
    """Alle Rollen — gezeichnete und geerbte. Der Test liest das."""
    return tuple(sorted({*SHAPES, *SYSTEM}))


def forget() -> None:
    """Den Vorrat leeren — nach einem Themen- oder Schriftwechsel.

    Die gemerkte Systemgröße geht mit: Sie ist einmal erfragt, und wer die
    Zeiger neu bauen lässt, soll auch eine inzwischen geänderte Einstellung
    bekommen.
    """
    _CACHE.clear()
    _SYSTEM_SIZE.clear()


def svg_source(role: str) -> str:
    """Das fertige SVG einer Rolle. Getrennt, damit der Test die Zeichnung
    prüfen kann, ohne ein Fenster zu brauchen."""
    entry = SHAPES.get(role)
    if entry is None:
        return ""
    body, _ = entry
    accent, edge = _colours()
    head = _HEAD.format(edge=edge)
    outline = body.format(accent="none")
    fill = _FILL.format(accent=accent, body=body.format(accent=accent))
    return f"{head}{outline}{fill}</svg>"


def _colours() -> tuple[str, str]:
    """Akzent und Saumfarbe. Beide sind in hellem und dunklem Thema dieselben:
    Der Zeiger liegt über dem Viewport, und dessen Hintergrund ist in beiden
    Themen bekannt — er folgt nicht der Fensterfarbe."""
    dark = THEMES["dark"]
    return dark["highlight"], dark["highlight_text"]


#: Was das System zuletzt als Zeigergröße genannt hat — einmal gefragt.
#:
#: Auf macOS kostet die Auskunft einen Prozessaufruf; ihn bei jedem Zeigerbau
#: zu wiederholen hieße, die Oberfläche für eine Zahl anzuhalten, die sich im
#: Betrieb praktisch nie ändert. :func:`forget` leert ihn mit.
_SYSTEM_SIZE: dict[str, int] = {}

#: Wie groß ein Zeiger ohne jede Einstellung ist. Windows nennt diese Zahl in
#: ``CursorBaseSize`` selbst, macOS rechnet seinen Faktor darauf.
BASE_SIZE: Final = 32


def _from_windows_registry() -> int:
    """``HKCU\\Control Panel\\Cursors\\CursorBaseSize`` — 0, wenn nichts dasteht.

    Windows schreibt hier, was der Nutzer unter „Zeigergröße" gewählt hat: 32
    ist der Normalwert, der Regler geht bis 256. Der Schlüssel fehlt, solange
    niemand ihn verstellt hat — dann gilt die Zeilenhöhe wie bisher.
    """
    # Geholt wird das Modul über ``import_module`` und nicht mit ``import``,
    # und der Grund ist nicht Geschmack: ``winreg`` gibt es auf zwei von drei
    # Plattformen nicht, und typeshed führt seine Namen als Windows-only.
    # ``mypy --platform linux`` meldet daraufhin drei ``attr-defined`` an
    # Code, der dort nie läuft — und drei ``type: ignore`` wären genau die
    # Sorte Rauschen, die man beim nächsten Mal nicht mehr liest.
    try:
        winreg = import_module("winreg")
    except ImportError:  # pragma: no cover - nur auf Windows vorhanden
        return 0
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors") as key:
            value, _kind = winreg.QueryValueEx(key, "CursorBaseSize")
    except OSError:
        return 0
    return int(value) if isinstance(value, int) else 0


def _from_macos_defaults() -> int:
    """``mouseDriverCursorSize`` mal :data:`BASE_SIZE` — 0, wenn nichts dasteht.

    macOS führt keine Pixelgröße, sondern einen **Faktor** zwischen 1,0 und
    4,0 („Zeigergröße" in der Bedienungshilfe). Ein Nutzer, der ihn auf 2
    stellt, will Zeiger von 64 — auch unsere.

    Der Schlüssel fehlt, solange niemand ihn verstellt hat; ``defaults`` endet
    dann mit einem Fehlercode, und das ist keine Störung, sondern die Antwort
    „Normalgröße".
    """
    try:
        answer = subprocess.run(
            ["defaults", "read", "com.apple.universalaccess", "mouseDriverCursorSize"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=2.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    if answer.returncode != 0:
        return 0
    try:
        factor = float(answer.stdout.strip())
    except ValueError:
        return 0
    return round(BASE_SIZE * factor) if factor > 0 else 0


def system_size(platform: str) -> int:
    """Was das Betriebssystem als Zeigergröße nennt — 0, wenn es nichts sagt.

    **Die Plattform kommt als Parameter**, aus demselben Grund wie bei
    :func:`app.core.discover.parts_for`: Ein Zweig, den nur ein Mac sehen kann,
    wird nirgends geprüft. Und ``mypy`` prüft die Plattform, auf der es läuft —
    eine Kette aus ``sys.platform``-Vergleichen ist auf zwei von drei Maschinen
    tot und wird dort gemeldet.

    Bis zum 27.08.2026 fragte nur Linux (``XCURSOR_SIZE``). Das war die
    Behebung des Kundenberichts und blieb auf halbem Weg stehen: Wer unter
    Windows die Zeigergröße hochstellt oder unter macOS den Faktor, hat damit
    genauso alle Zeiger gemeint. Auf beiden blieb es bei der Zeilenhöhe, also
    bei derselben Rechnung, die dem Kunden einen Zeiger von 60 Punkten
    beschert hat — nur unbemerkt, weil dort selten jemand die Schrift so weit
    hochstellt.
    """
    if platform in _SYSTEM_SIZE:
        return _SYSTEM_SIZE[platform]
    if platform == "win32":
        size = _from_windows_registry()
    elif platform == "darwin":
        size = _from_macos_defaults()
    else:
        named = os.environ.get("XCURSOR_SIZE", "").strip()
        size = int(named) if named.isdigit() else 0
    _SYSTEM_SIZE[platform] = size
    return size


def _size_for(widget: QWidget) -> int:
    """Wie groß ein eigener Zeiger wird — und wer das entscheidet.

    **Erste Quelle ist die Systemeinstellung**, und zwar auf allen drei
    Plattformen (:func:`system_size`): ``XCURSOR_SIZE`` unter Linux,
    ``CursorBaseSize`` in der Windows-Registry, ``mouseDriverCursorSize`` als
    Faktor auf macOS. Wer seine Zeiger auf 24 stellt, meint alle Zeiger, auch
    unsere.

    **Zweite Quelle ist die Zeilenhöhe**, und sie war bis zum 27.08.2026 die
    einzige. Das ist auf Windows und macOS unauffällig geblieben und auf Linux
    nicht: Ein Kunde auf CachyOS mit GNOME meldete „Der Cursor ist SEHR gross
    und viel zu ungenau". Gerechnet ergibt die Bindung an die Schrift bei einer
    Zeilenhöhe von 30 Punkten einen Zeiger von **60** — Systemzeiger sind 24
    bis 32, und wer die Textgröße hochstellt, hat damit nichts über seine
    Zeiger gesagt.

    Die Regel dahinter stand längst in ``.claude/rules/ansicht.md``, nur als
    Feststellung statt als Lösung: Eine Systemform „folgt der eingestellten
    Zeigergröße, unsere täte das nicht". Jetzt tut sie es, wo das System sie
    nennt.

    Qt hilft dabei nicht — ``styleHints()`` kennt nur ``cursorFlashTime``.
    """
    system = system_size(sys.platform)
    if system > 0:
        return max(min(system, MAX_SIZE), 16)
    height = widget.fontMetrics().height() if widget is not None else 16
    return max(min(int(height * SCALE), MAX_SIZE), 16)


def _build(role: str, size: int) -> QCursor:
    source = svg_source(role)
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    if not renderer.isValid():
        return QCursor(Qt.CursorShape.ArrowCursor)

    ratio = _ratio()
    image = QImage(QSize(size, size) * ratio, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.setDevicePixelRatio(float(ratio))

    _, hotspot = SHAPES[role]
    # **Der Griffpunkt steht in denselben Pixeln wie die Zeichnung.**
    #
    # Hier stand die Umrechnung auf die *angeforderte* Größe, mit dem Kommentar
    # „QCursor rechnet das Verhältnis selbst heraus". Gemessen am 27.08.2026
    # tut es das nicht: Bei einer Zeichnung von 64 mal 64 Pixeln und einer
    # angeforderten Größe von 32 Punkten kam der Punkt der Pfeilspitze bei
    # 7,8 % der Breite an, wo er bei 15,6 % liegen muss — **um den
    # Überabtastungsfaktor zu weit oben links.** Gemeldet hat es ein Kunde:
    # „klickt nicht an der Spitze sondern in der Mitte des Symbols."
    #
    # Gerechnet wird deshalb gegen die Kantenlänge des Bildes, das entsteht.
    # Ob Qt danach durch die Gerätepixelrate teilt oder nicht, ist damit keine
    # Frage mehr, die dieser Code beantworten muss — beide Zahlen stehen in
    # derselben Einheit.
    drawn = image.width()
    scale = drawn / 32.0
    point = QPoint(round(hotspot[0] * scale), round(hotspot[1] * scale))
    return QCursor(QPixmap.fromImage(image), point.x(), point.y())


def _ratio() -> int:
    """Überabtastung für scharfe Kanten auf HiDPI. Ganzzahlig, weil ein
    krummes Verhältnis den Griffpunkt um einen halben Pixel verschiebt — und
    genau der halbe Pixel ist beim Messen der Unterschied."""
    if QApplication.instance() is None:
        return 2
    # Über ``QGuiApplication`` und nicht über die Instanz: ``instance()`` ist
    # als ``QCoreApplication`` angegeben, und die kennt keinen Bildschirm.
    screen = QGuiApplication.primaryScreen()
    return max(int(screen.devicePixelRatio()) if screen is not None else 2, 2)
