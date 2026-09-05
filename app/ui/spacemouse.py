"""Die 3D-Maus — eine zweite Hand an derselben Kamera (§2.9, §18).

Ein Zahntechniker, der acht Stunden am Tag die linke Hand auf einer
SpaceMouse hat, steckt sie in Solidon ein und drückt — und das Bild soll
folgen, ohne dass er etwas einrichtet (Konzept ``konzept-3d-maus-2026-08``).
Vier Zusagen tragen dieses Modul:

1. **Kein Gerät, keine Spur.** Ohne 3D-Maus ist die Anwendung Zeile für
   Zeile dieselbe; die Einstellungszeile erscheint erst ab dem ersten
   gesehenen Gerät (``spacemouse_seen``) und bleibt dann.
2. **Es fährt die Kamera und sonst nichts.** Keine Operation, keine Auswahl,
   keine Geometrie — Regel 2 wird nicht berührt, weil nichts ins Dokument
   gelangt.
3. **Es ist kein Modus.** Die vier Navigationsschemata beantworten „welche
   Maustaste dreht"; die Frage stellt sich hier nicht.
4. **Die Maus behält alles.** Eine Gerätetaste löst *Einpassen* aus —
   die häufigste Belegung —, und mehr gibt es nicht zu belegen.

Das Modul zerfällt in zwei Teile, wie das Konzept es verlangt:

* **Lesen** — :class:`HidReader`. Das Gerät wird direkt über HID gelesen
  (``hidapi``, BSD-3 aus der Dreifachlizenz gewählt), so wie PrusaSlicer es
  tut und wie Assist es auf demselben Rechner tut. Der Herstellertreiber
  3DxWare darf daneben laufen: Er liest dieselben Berichte, ohne sie
  wegzunehmen (gemessen am 02.09.2026, 4572 Berichte in fünfzig Sekunden
  bei laufendem 3DxWare). Nicht blockierend, im Hauptthread, kein eigener
  Faden — ein ``QTimer`` fragt mit ~60 Hz, was seit dem letzten Mal ankam;
  eine leere Lesung kostet unter einer Mikrosekunde (gemessen).

  **Auf dem Mac gilt der Satz vom Nebeneinander nicht.** Dort hält 3DxWare
  das Gerät exklusiv, und ``hidapi`` öffnet seinerseits exklusiv — wer den
  Treiber installiert hat, bekommt über HID keinen Bericht (der erste
  Mac-Bericht eines Kunden, 05.09.2026: „die Maus tut nichts"). Der Weg
  führt dort durch den Treiber: :class:`DriverReader` lädt das
  ``3DconnexionClient``-Framework des Kunden zur Laufzeit und schreibt
  seine Zustandsmeldungen in dieselben Berichte um, die das Gerät roh
  liefert. Nichts wird mitgeliefert, und ohne Treiber bleibt HID.
  :func:`default_reader` entscheidet je Rechner.
* **Abbilden** — :func:`camera_step`. Eine reine Funktion: sechs Achsen in
  [-1, 1], die Kamerastellung, die Zeitspanne und zwei Einstellungen hinein,
  eine neue Kamerastellung heraus. Sie kennt kein Qt, kein VTK und kein HID
  und ist damit offscreen vollständig prüfbar — hier sitzt jeder künftige
  Fehler (Achsen, Vorzeichen, Bezugssystem).

Die Bedienung folgt dem, was der Hersteller *Objektmodus* nennt und was in
jedem CAD-Programm die Vorgabe ist: **Die Kappe ist das Teil, mit allen
sechs Achsen** (Robert, 02.09.2026: „wir wollen alle 6 Achsen nutzen").
Schiebt man sie nach rechts, wandert das Teil nach rechts; zieht man sie zu
sich, kommt es näher; dreht man sie, dreht sich das Teil um die Bildsenkrechte;
kippt man sie, kippt es um die Bildwaagerechte; rollt man sie, rollt es um
die Blickrichtung. „Richtung umkehren" in den Einstellungen macht aus dem
Objektmodus den Kameramodus, in dem die Kappe die Kamera ist.

Was 3DxWare daneben noch tut, ist nicht unsere Sache und steht im Register:
Für Programme, die es nicht kennt, spielt es Mausbewegungen ein. Wer das
nicht will, schaltet es in den 3Dconnexion-Einstellungen für Solidon ab.
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import math
import struct
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from PySide6.QtCore import QObject, QTimer, Signal

_log = logging.getLogger(__name__)

Vec3 = tuple[float, float, float]

#: Der Bericht mit den drei Schubachsen (x, y, z je int16).
REPORT_TRANSLATION: Final = 1
#: Der Bericht mit den drei Drehachsen (rx, ry, rz je int16).
REPORT_ROTATION: Final = 2
#: Der Bericht mit den Tasten als Bitmaske.
REPORT_BUTTONS: Final = 3
#: Vollausschlag der Kappe in Rohschritten. Der Compact liefert ±350 bei
#: voller Auslenkung (gemessen); alles darüber wird abgeschnitten.
AXIS_RANGE: Final = 350.0
#: Unterhalb dieses Anteils des Vollausschlags gilt eine Achse als Ruhe.
#: Hardware-Tatsache, keine Einstellung: Eine losgelassene Kappe meldet ein
#: paar Rohschritte Rauschen, und die dürfen die Kamera nicht kriechen lassen.
DEADZONE: Final = 0.03
#: Kommt so lange kein Bericht mehr, gilt die Kappe als losgelassen — das
#: Gerät meldet Null beim Loslassen, aber ein abgezogenes Gerät meldet nichts.
HOLD_SECONDS: Final = 0.25
#: Takt des Lesens und der Kamerafahrt in Millisekunden (~60 Hz).
TICK_MS: Final = 16
#: Wie oft nach einem Gerät gesucht wird, solange keines offen ist — erst
#: alle zwei Sekunden, dann mit jeder leeren Suche doppelt so selten bis zur
#: Obergrenze. ``hid.enumerate()`` kostet auf einem Rechner mit zwei Dutzend
#: HID-Geräten 37 ms (gemessen am 02.09.2026, erste Lesung 106 ms) — alle
#: zwei Sekunden ein Ruckler im Hauptthread, auf jedem Rechner ohne 3D-Maus.
#: Eingesteckt wird ein Gerät damit spätestens nach einer halben Minute
#: gefunden; die erste Suche wartet, bis das Fenster steht.
SCAN_MS: Final = 2000
SCAN_FIRST_MS: Final = 1500
SCAN_MAX_MS: Final = 30_000
#: Mehr Berichte je Takt werden nicht gelesen — ein Gerät, das schneller
#: sendet, als wir zeichnen, darf den Takt nicht auffressen.
REPORTS_PER_TICK: Final = 32

#: Wie weit die Kamera bei Vollausschlag je Sekunde schiebt — als Anteil der
#: Entfernung zum Blickpunkt, damit sich der Schub am Bildschirm immer gleich
#: schnell anfühlt, ob das Teil 10 mm oder 1 m groß ist.
PAN_RATE: Final = 1.2
#: Zoom bei Vollausschlag: der natürliche Logarithmus des Faktors je Sekunde.
ZOOM_RATE: Final = 1.6
#: Drehung bei Vollausschlag in Bogenmaß je Sekunde.
ORBIT_RATE: Final = math.radians(110.0)
#: Näher als das geht die Kamera nicht an den Blickpunkt (Millimeter).
MIN_DISTANCE: Final = 0.5
#: Weiter als das geht sie nicht weg — jenseits ist ohnehin nur Bauraum.
MAX_DISTANCE: Final = 50_000.0
#: Die Geschwindigkeitsstufe, bei der die Raten oben unverändert gelten.
NEUTRAL_SPEED: Final = 5

#: Herstellerkennungen, deren Berichte wir zu lesen wissen: 3Dconnexion,
#: dazu die älteren Geräte, die noch unter Logitech gemeldet werden
#: (SpaceNavigator, SpaceExplorer, SpacePilot).
KNOWN_VENDORS: Final = frozenset({0x256F, 0x046D})
#: HID-Nutzungsseite „Generic Desktop" und Nutzung „Multi-axis Controller" —
#: so meldet sich die Schnittstelle, die die Bewegung trägt. Ein Logitech-
#: Empfänger meldet sich unter derselben Herstellerkennung als Tastatur und
#: Maus; die Nutzung hält ihn heraus.
USAGE_PAGE_GENERIC_DESKTOP: Final = 0x01
USAGE_MULTI_AXIS_CONTROLLER: Final = 0x08

#: Der Herstellertreiber auf dem Mac. 3DxWare öffnet das Gerät dort exklusiv,
#: und ``hidapi`` käme an keinen Bericht heran; die Berichte kommen dann über
#: sein Framework — dieselbe Tür, durch die Blender, FreeCAD und PrusaSlicer
#: auf dem Mac gehen. Das Framework wird **nicht mitgeliefert**: Es liegt beim
#: Kunden, und Solidon lädt es zur Laufzeit oder lässt es bleiben.
DRIVER_FRAMEWORK: Final = "/Library/Frameworks/3DconnexionClient.framework/3DconnexionClient"
#: Aus ``ConnexionClientAPI.h`` des Treibers — die ersten beiden sind
#: Viererzeichen (``'3dSR'``, ``'****'``), als Zahl gelesen.
DRIVER_MSG_DEVICE_STATE: Final = 0x33645352
DRIVER_CLIENT_WILDCARD: Final = 0x2A2A2A2A
DRIVER_STATE_VERSION: Final = 0x6D33
DRIVER_CMD_HANDLE_BUTTONS: Final = 2
DRIVER_CMD_HANDLE_AXIS: Final = 3
DRIVER_MODE_TAKE_OVER: Final = 1
DRIVER_MASK_ALL: Final = 0x3FFF
DRIVER_MASK_ALL_BUTTONS: Final = 0xFFFFFFFF

#: Die Hochachse des Bauraums — der Rückfall für ein „Oben", das mit der
#: Blickrichtung zusammenfällt.
WORLD_UP: Final[Vec3] = (0.0, 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class Motion:
    """Die sechs Achsen der Kappe in [-1, 1] und die Tasten als Bitmaske.

    Bezugssystem: ``x`` rechts, ``y`` vom Nutzer weg, ``z`` nach oben —
    rechtshändig, und die Drehungen folgen der Rechte-Hand-Regel um genau
    diese Achsen: ``rx`` positiv kippt die Vorderkante nach unten, ``ry``
    positiv senkt die rechte Kante, ``rz`` positiv dreht gegen den
    Uhrzeigersinn (von oben gesehen).
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0
    buttons: int = 0

    def active(self) -> bool:
        """Ob irgendeine Achse aus der Ruhe heraus ist."""
        axes = (self.x, self.y, self.z, self.rx, self.ry, self.rz)
        return any(abs(value) >= DEADZONE for value in axes)


#: Halbe Bildhöhe gegen Abstand bei 30° Öffnungswinkel — damit ein Schub in
#: der Parallelprojektion so weit trägt wie derselbe Schub perspektivisch.
PARALLEL_REACH: Final = 1.0 / math.tan(math.radians(15.0))


@dataclass(frozen=True, slots=True)
class CameraPose:
    """Eine Kamerastellung, so wie VTK sie führt: Standort, Blickpunkt, Oben.

    ``parallel_scale`` ist die halbe sichtbare Höhe, wenn die Projektion
    parallel ist — dann zoomt nur sie, und der Standort bleibt, wo er ist.
    ``None`` heißt perspektivisch: Zoom ist Abstand.
    """

    position: Vec3
    focal_point: Vec3
    view_up: Vec3
    parallel_scale: float | None = None


def _normalise_axis(raw: int) -> float:
    return max(-1.0, min(1.0, raw / AXIS_RANGE))


def decode_report(data: bytes, previous: Motion) -> Motion:
    """Ein HID-Bericht wird auf den letzten Zustand gelegt.

    Die Geräte melden Schub und Drehung in getrennten Berichten (Kennung 1
    und 2), neuere in einem einzigen zwölf Byte langen Bericht mit Kennung 1;
    die Tasten kommen mit Kennung 3. Was nicht im Bericht steht, bleibt, wie
    es war — sonst stünde die Drehung still, sobald ein Schubbericht kommt.
    Unbekannte Kennungen ändern nichts.

    **Die Vorzeichen sind gemessen, nicht angenommen** — SpaceMouse Compact,
    geführte Aufzeichnungen am 02.09.2026, Korpusdatei
    ``tests/data/spacemouse/compact-2026-09-02.jsonl``. Das Gerät zählt
    ``x`` nach rechts, ``y`` **zum Nutzer** und ``z`` **nach unten**; seine
    drei Drehwerte stehen alle gegen die Rechte-Hand-Regel um die Achsen von
    :class:`Motion` (Vorderkante runter, rechte Kante runter, Uhrzeigersinn
    von oben — je ein negativer Rohwert). Deshalb wechseln ``y``, ``z`` und
    alle drei Drehungen das Vorzeichen, ``x`` nicht.
    """
    if len(data) < 2:
        return previous
    report_id, payload = data[0], data[1:]
    if report_id == REPORT_TRANSLATION and len(payload) >= 6:
        x, y, z = struct.unpack_from("<hhh", payload, 0)
        motion = replace(
            previous, x=_normalise_axis(x), y=-_normalise_axis(y), z=-_normalise_axis(z)
        )
        if len(payload) >= 12:
            rx, ry, rz = struct.unpack_from("<hhh", payload, 6)
            motion = replace(
                motion, rx=-_normalise_axis(rx), ry=-_normalise_axis(ry), rz=-_normalise_axis(rz)
            )
        return motion
    if report_id == REPORT_ROTATION and len(payload) >= 6:
        rx, ry, rz = struct.unpack_from("<hhh", payload, 0)
        return replace(
            previous, rx=-_normalise_axis(rx), ry=-_normalise_axis(ry), rz=-_normalise_axis(rz)
        )
    if report_id == REPORT_BUTTONS:
        # Zwei Byte Tasten. Das Gerät füllt den Bericht auf seine feste Länge
        # auf, und hinter den zwei Byte steht, was vorher im Puffer lag —
        # gemessen: ``03 00 00 00 b8 ff``, vier Byte gelesen hießen vier
        # Milliarden Tasten.
        return replace(previous, buttons=int.from_bytes(payload[:2], "little"))
    return previous


def _response(value: float) -> float:
    """Totzone weg, dann eine sanfte Kurve: fein in der Mitte, voll am Rand.

    Mit linearer Antwort ist die kleinste bewusste Bewegung schon ein Ruck;
    die Kurve gibt der Hand in der Mitte Platz, ohne den Vollausschlag zu
    kappen. So macht es der Herstellertreiber auch.
    """
    magnitude = abs(value)
    if magnitude < DEADZONE:
        return 0.0
    scaled = min(1.0, (magnitude - DEADZONE) / (1.0 - DEADZONE))
    return math.copysign(scaled**1.5, value)


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec3, factor: float) -> Vec3:
    return (a[0] * factor, a[1] * factor, a[2] * factor)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Vec3) -> Vec3:
    length = _length(a)
    return (0.0, 0.0, 0.0) if length == 0.0 else _scale(a, 1.0 / length)


def _rotate(vector: Vec3, axis: Vec3, angle: float) -> Vec3:
    """Rodrigues: ``vector`` um die Einheitsachse ``axis`` um ``angle`` drehen."""
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return _add(
        _add(_scale(vector, cos_a), _scale(_cross(axis, vector), sin_a)),
        _scale(axis, _dot(axis, vector) * (1.0 - cos_a)),
    )


def speed_factor(level: int) -> float:
    """Die Stufe des Reglers (1 bis 10) als Faktor auf die Raten; 5 ist 1,0."""
    return max(1, min(10, int(level))) / NEUTRAL_SPEED


def camera_step(
    pose: CameraPose,
    motion: Motion,
    dt: float,
    *,
    speed: float = 1.0,
    invert: bool = False,
    orbit: bool = True,
    fly: bool = False,
) -> CameraPose:
    """Eine Zeitspanne Kappenbewegung auf eine Kamerastellung anwenden.

    Reine Funktion, deterministisch: gleiche Eingaben, gleiche Stellung —
    Wert für Wert. Objektmodus (``invert=False``): Die Kappe ist das Teil,
    und die drei Achsen der Kappe sind die drei Achsen des Bildes — rechts,
    oben, Blickrichtung. Das Teil bewegt sich wie die Kappe; die Kamera fährt
    dazu die Gegenbewegung.

    | Kappe | Wirkung |
    |---|---|
    | schieben links/rechts (``x``) | das Teil wandert mit — die Kamera fährt gegen |
    | ziehen/drücken (``z``) | das Teil hebt und senkt sich |
    | zu sich ziehen/wegschieben (``y``) | näher heran / weiter weg |
    | kippen vor/zurück (``rx``) | das Teil kippt um die Bildwaagerechte |
    | rollen links/rechts (``ry``) | das Teil rollt um die Blickrichtung |
    | drehen (``rz``) | das Teil dreht sich um die Bildsenkrechte |

    ``orbit=False`` lässt die Drehachsen aus — im Zeichenmodus bleibt die
    Blickrichtung auf der Zeichenebene, geschoben und gezoomt wird trotzdem.
    Schub und Zoom skalieren mit der Entfernung zum Blickpunkt, damit die
    Bewegung am Bildschirm immer gleich schnell ist.

    ``fly=True`` legt ``y`` anders aus: **fliegen statt zoomen.** Standort und
    Blickpunkt wandern gemeinsam entlang der Blickrichtung, statt nur den
    Abstand zu ändern — die Kamera fährt also ins Teil hinein und nicht bis
    davor. Für die Tastatursteuerung (W/S, Entscheidung Robert, 03.09.2026):
    Dort liegt der Zoom auf dem Mausrad, und eine zweite Zoomgeste wäre keine
    neue Bewegung. Der Blickpunkt mitzunehmen ist dabei das Entscheidende —
    ohne ihn dreht sich die nächste Kamerabewegung weiter um einen Punkt, den
    der Kunde längst hinter sich gelassen hat.
    """
    if dt <= 0.0 or not motion.active():
        return pose
    sign = 1.0 if invert else -1.0
    gain = speed * dt
    position, focal, up = pose.position, pose.focal_point, pose.view_up
    offset = _sub(position, focal)
    distance = _length(offset)
    if distance == 0.0:
        return pose
    forward = _scale(offset, -1.0 / distance)
    # Der Rechtsvektor darf nie null werden: Eine Drehung um eine Nullachse
    # staucht statt zu drehen (Rodrigues wird zu ``vector * cos``). Blickt die
    # Kamera entlang ihres eigenen Oben, hilft die Hochachse des Bauraums;
    # blickt sie auch entlang der, hilft die Tiefenachse — parallel zu beiden
    # kann sie nicht sein.
    right = _unit(_cross(forward, up))
    for helper in (WORLD_UP, (0.0, 1.0, 0.0)):
        if _length(right) > 0.0:
            break
        right = _unit(_cross(forward, helper))
    # VTK verlangt kein senkrechtes „Oben"; gerechnet wird mit dem senkrechten,
    # sonst hängt jede Drehung davon ab, wie schief der Wert gerade steht.
    up = _unit(_cross(right, forward))

    changed = False
    # Schieben: Kamera und Blickpunkt gemeinsam, in der Bildebene. Jeder
    # Anteil wird nur gerechnet, wenn er da ist — sonst kostete eine ruhende
    # Achse Rundungsfehler, und eine Kamera, die niemand bewegt hat, stünde
    # ein Bit neben sich.
    scale = pose.parallel_scale
    extent = distance if scale is None else scale * PARALLEL_REACH
    push, lift = _response(motion.x), _response(motion.z)
    if push or lift:
        pan = _add(_scale(right, push * sign), _scale(up, lift * sign))
        shift = _scale(pan, PAN_RATE * gain * extent)
        position, focal = _add(position, shift), _add(focal, shift)
        changed = True

    # Zoom: Kappe zu sich ziehen (y negativ) holt das Teil näher — als
    # Abstand in der Perspektive, als Bildhöhe in der Parallelprojektion.
    # Dort den Standort zu verschieben änderte am Bild nichts und schob die
    # Kamera unsichtbar bis auf einen halben Millimeter an das Teil heran.
    reach = _response(motion.y)
    if reach and fly:
        # Fliegen: dieselbe Rechnung wie beim Schieben darüber, nur entlang
        # der Blickrichtung. Beide Punkte wandern, also bleibt der Abstand —
        # und mit ihm die Empfindlichkeit jeder folgenden Drehung.
        # **Dasselbe Vorzeichen wie der Zoom, den dieser Zweig ersetzt.**
        # Dort heißt ``y`` positiv „weiter weg" (die Kappe wegschieben), und
        # eine Achse, die je nach Schalter in die andere Richtung zieht,
        # wäre die Falle für den Nächsten, der ``fly`` an ein Gerät hängt.
        # Die Tastatur legt W deshalb auf einen negativen Wert.
        shift = _scale(forward, _response(motion.y) * PAN_RATE * gain * extent * sign)
        position, focal = _add(position, shift), _add(focal, shift)
        changed = True
    elif reach:
        factor = math.exp(reach * ZOOM_RATE * gain * -sign)
        if scale is None:
            new_distance = max(MIN_DISTANCE, min(MAX_DISTANCE, distance * factor))
            position = _add(focal, _scale(_unit(_sub(position, focal)), new_distance))
        else:
            scale = max(MIN_DISTANCE, min(MAX_DISTANCE, scale * factor))
        changed = True

    if orbit:
        # Drei Drehungen um die drei Bildachsen, jede nur, wenn sie da ist.
        # Die Achsen werden mitgedreht, damit die nächste Drehung im schon
        # gedrehten Bild stattfindet — so wie die Kappe es tut.
        rate = ORBIT_RATE * gain * sign
        spin = _response(motion.rz) * rate
        if spin:
            position = _add(focal, _rotate(_sub(position, focal), up, spin))
            right = _rotate(right, up, spin)
            forward = _rotate(forward, up, spin)
            changed = True
        tilt = _response(motion.rx) * rate
        if tilt:
            position = _add(focal, _rotate(_sub(position, focal), right, tilt))
            up = _rotate(up, right, tilt)
            forward = _rotate(forward, right, tilt)
            changed = True
        roll = _response(motion.ry) * rate
        if roll:
            up = _rotate(up, forward, roll)
            changed = True

    if not changed:
        return pose
    return CameraPose(position, focal, _unit(up), scale)


def _is_motion_interface(info: dict[str, Any]) -> bool:
    return (
        info.get("vendor_id") in KNOWN_VENDORS
        and info.get("usage_page") == USAGE_PAGE_GENERIC_DESKTOP
        and info.get("usage") == USAGE_MULTI_AXIS_CONTROLLER
    )


class HidReader:
    """Liest die 3D-Maus direkt über HID — nicht blockierend, im Hauptthread.

    ``hidapi`` wird erst beim Öffnen importiert: Ohne das Paket bleibt der
    Leser still, ohne Fehler und ohne Protokollzeile (Konzept, Abnahme 2).
    Ein abgezogenes Gerät meldet sich beim nächsten Lesen als ``OSError``;
    der Leser schließt und lässt sich später wieder öffnen — Wiedereinstecken
    wirkt ohne Neustart (Abnahme 6).
    """

    def __init__(self) -> None:
        self._device: Any = None
        self._module: Any = None
        self._unavailable = False

    @property
    def is_open(self) -> bool:
        return self._device is not None

    def _hid(self) -> Any:
        if self._module is None and not self._unavailable:
            try:
                import hid
            except ImportError:
                self._unavailable = True
            else:
                self._module = hid
        return self._module

    def open(self) -> bool:
        """Die Bewegungsschnittstelle des ersten bekannten Geräts öffnen."""
        if self._device is not None:
            return True
        hid = self._hid()
        if hid is None:
            return False
        try:
            devices = list(hid.enumerate())
            candidates = [info for info in devices if _is_motion_interface(info)]
            if not candidates:
                # Linux (hidraw) nennt Nutzungsseite und Nutzung nicht immer.
                # Dann zählt allein die Herstellerkennung von 3Dconnexion —
                # nicht die von Logitech, unter der auch Tastaturempfänger
                # laufen.
                candidates = [info for info in devices if info.get("vendor_id") == 0x256F]
            if not candidates:
                return False
            device = hid.device()
            device.open_path(candidates[0]["path"])
            device.set_nonblocking(True)
        except (OSError, ValueError, KeyError) as problem:
            _log.debug("3D mouse not opened: %s", problem)
            return False
        self._device = device
        return True

    def read(self) -> list[bytes]:
        """Was seit dem letzten Aufruf ankam — leer, wenn nichts."""
        if self._device is None:
            return []
        reports: list[bytes] = []
        try:
            for _ in range(REPORTS_PER_TICK):
                data = self._device.read(64)
                if not data:
                    break
                reports.append(bytes(data))
        except (OSError, ValueError) as problem:
            _log.debug("3D mouse lost: %s", problem)
            self.close()
        return reports

    def close(self) -> None:
        device, self._device = self._device, None
        if device is not None:
            with contextlib.suppress(OSError, ValueError):
                device.close()


class DriverState(ctypes.Structure):
    """``ConnexionDeviceState`` aus dem SDK-Header, Byte für Byte.

    Der Header packt die Struktur auf zwei Byte (``#pragma pack(push, 2)``):
    ``time`` liegt damit bei Byte 12 und nicht bei 16, die sechs Achsen bei
    30, die Tasten bei 44 — 48 Byte insgesamt. Ein Test hält die Zahlen fest,
    denn ein falsches Packen gibt keine Fehlermeldung, sondern Rauschen als
    Bewegung.
    """

    _pack_ = 2
    _fields_ = (
        ("version", ctypes.c_uint16),
        ("client", ctypes.c_uint16),
        ("command", ctypes.c_uint16),
        ("param", ctypes.c_int16),
        ("value", ctypes.c_int32),
        ("time", ctypes.c_uint64),
        ("report", ctypes.c_uint8 * 8),
        ("buttons8", ctypes.c_uint16),
        ("axis", ctypes.c_int16 * 6),
        ("address", ctypes.c_uint16),
        ("buttons", ctypes.c_uint32),
    )


#: Die Rückruffunktionen des Treibers: Zustandsmeldung (Produkt, Art, Zeiger
#: auf :class:`DriverState`) und Gerät gekommen oder gegangen (Produkt).
_MESSAGE_HANDLER = ctypes.CFUNCTYPE(None, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
_DEVICE_HANDLER = ctypes.CFUNCTYPE(None, ctypes.c_uint32)


def load_driver(path: str = DRIVER_FRAMEWORK) -> Any | None:
    """Das Framework des Herstellertreibers — ``None``, wo es fehlt oder nicht lädt.

    Fünf Einsprungpunkte bekommen ihre Signaturen aus dem Header; fehlt einer
    (ein Treiber vor 10.x kannte ``SetConnexionHandlers`` noch nicht), gilt
    der Treiber als nicht vorhanden. Die Datei wird vor dem Laden geprüft:
    ``CDLL`` auf einen fehlenden Pfad kostet eine Ausnahme, und diese
    Funktion läuft bei jeder Suche nach einem Gerät.
    """
    if not Path(path).exists():
        return None
    try:
        library = ctypes.CDLL(path)
        library.SetConnexionHandlers.argtypes = [
            _MESSAGE_HANDLER,
            _DEVICE_HANDLER,
            _DEVICE_HANDLER,
            ctypes.c_bool,
        ]
        library.SetConnexionHandlers.restype = ctypes.c_int16
        library.RegisterConnexionClient.argtypes = [
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint16,
            ctypes.c_uint32,
        ]
        library.RegisterConnexionClient.restype = ctypes.c_uint16
        library.SetConnexionClientButtonMask.argtypes = [ctypes.c_uint16, ctypes.c_uint32]
        library.SetConnexionClientButtonMask.restype = None
        library.UnregisterConnexionClient.argtypes = [ctypes.c_uint16]
        library.UnregisterConnexionClient.restype = None
        library.CleanupConnexionHandlers.argtypes = []
        library.CleanupConnexionHandlers.restype = None
    except (OSError, AttributeError) as problem:
        _log.debug("3D mouse driver not loaded: %s", problem)
        return None
    return library


class DriverReader:
    """Liest die 3D-Maus über den Herstellertreiber — der Weg auf dem Mac.

    Dieselbe Naht wie :class:`HidReader` (``open``, ``read``, ``close``,
    ``is_open``), dahinter ein anderer Kanal: Der Treiber ruft eine
    Rückruffunktion über die Ereignisschleife des Hauptthreads (Qt fährt auf
    dem Mac dieselbe ``CFRunLoop``), und was er meldet, wird hier zu
    **denselben Berichten** umgeschrieben, die das Gerät roh liefert —
    Kennung 1 mit sechs Achsen, Kennung 3 mit den Tasten.
    :func:`decode_report` und alles dahinter kennen den Unterschied nicht.
    Achsenfolge und Vorzeichen des Treibers sind die des rohen Berichts;
    Blender rechnet beide Wege mit derselben Zuordnung um
    (``GHOST_NDOFManagerCocoa`` gegen ``GHOST_SystemWin32``). **Am Gerät
    gemessen ist dieser Weg nicht** — die erste Rückmeldung eines Kunden
    prüft ihn.

    Angemeldet wird mit dem Platzhalter statt mit einem Programmnamen, so wie
    FreeCAD und Blender es tun: Der Treiber richtet seine Zustandsmeldungen an
    den Client des vordersten Programms und trägt dessen Kennung im Feld
    ``client``; was an einen anderen gerichtet ist, wird hier verworfen. So
    liest Solidon nur, wenn es vorn ist, und ein CAD daneben behält seine
    Maus.

    Offen ist der Leser, wenn der Treiber ein Gerät gemeldet hat oder
    Berichte anstehen. Die Anmeldung allein ist kein Gerät: Wer 3DxWare
    installiert, aber die Maus nicht eingesteckt hat, sieht weiterhin keine
    Einstellungszeile (Zusage 1). Verweigert der Treiber die Anmeldung —
    installiert, aber angehalten —, hält er auch das Gerät nicht, und der
    Rückfall auf HID übernimmt für den Rest der Sitzung.
    """

    def __init__(
        self,
        driver: Any | None = None,
        *,
        loader: Callable[[], Any | None] = load_driver,
        fallback: HidReader | None = None,
    ) -> None:
        self._driver = driver
        self._loader = loader
        self._fallback = fallback
        self._delegate: HidReader | None = None
        self._unavailable = False
        self._client = 0
        self._devices = 0
        self._pending: list[bytes] = []
        self._handlers: tuple[Any, ...] = ()

    @property
    def is_open(self) -> bool:
        if self._delegate is not None:
            return self._delegate.is_open
        return self._client != 0 and (self._devices > 0 or bool(self._pending))

    def open(self) -> bool:
        """Anmelden, wenn noch nicht geschehen; offen erst mit einem Gerät."""
        if self._delegate is not None:
            return self._delegate.open()
        if self._client == 0 and not self._register():
            if self._fallback is None:
                return False
            self._delegate = self._fallback
            return self._delegate.open()
        return self.is_open

    def _register(self) -> bool:
        if self._unavailable:
            return False
        if self._driver is None:
            self._driver = self._loader()
            if self._driver is None:
                self._unavailable = True
                return False
        handlers = (
            _MESSAGE_HANDLER(self._on_message),
            _DEVICE_HANDLER(self._on_added),
            _DEVICE_HANDLER(self._on_removed),
        )
        try:
            if self._driver.SetConnexionHandlers(*handlers, False) != 0:
                return False
            client = int(
                self._driver.RegisterConnexionClient(
                    DRIVER_CLIENT_WILDCARD, None, DRIVER_MODE_TAKE_OVER, DRIVER_MASK_ALL
                )
            )
            if client == 0:
                self._driver.CleanupConnexionHandlers()
                return False
            self._driver.SetConnexionClientButtonMask(client, DRIVER_MASK_ALL_BUTTONS)
        except (OSError, ValueError, ctypes.ArgumentError) as problem:
            _log.debug("3D mouse driver refused the client: %s", problem)
            return False
        # Die Rückruffunktionen leben so lange wie die Anmeldung: Ein vom
        # Aufräumer eingesammeltes ctypes-Objekt wäre für den Treiber ein
        # Sprung ins Leere.
        self._handlers = handlers
        self._client = client
        return True

    def _on_message(self, _product: int, kind: int, argument: int | None) -> None:
        if kind != DRIVER_MSG_DEVICE_STATE or not argument:
            return
        state = DriverState.from_address(argument)
        if state.version != DRIVER_STATE_VERSION or state.client != self._client:
            return
        if state.command == DRIVER_CMD_HANDLE_AXIS:
            self._queue(bytes([REPORT_TRANSLATION]) + struct.pack("<6h", *state.axis))
        elif state.command == DRIVER_CMD_HANDLE_BUTTONS:
            self._queue(bytes([REPORT_BUTTONS]) + struct.pack("<H", state.buttons & 0xFFFF))

    def _queue(self, report: bytes) -> None:
        self._pending.append(report)
        # Mehr, als ein Takt liest, wird nicht aufbewahrt: Steht die Schleife
        # eine Sekunde, zählt danach die letzte Lage der Kappe, nicht die erste.
        del self._pending[:-REPORTS_PER_TICK]

    def _on_added(self, _product: int) -> None:
        self._devices += 1

    def _on_removed(self, _product: int) -> None:
        self._devices = max(0, self._devices - 1)
        if self._devices == 0:
            self._pending.clear()

    def read(self) -> list[bytes]:
        """Was der Treiber seit dem letzten Takt gemeldet hat — leer, wenn nichts."""
        if self._delegate is not None:
            return self._delegate.read()
        reports, self._pending = self._pending, []
        return reports

    def close(self) -> None:
        if self._delegate is not None:
            self._delegate.close()
            self._delegate = None
        client, self._client = self._client, 0
        self._devices = 0
        self._pending = []
        if client and self._driver is not None:
            # Zwei Blöcke, nicht einer: Scheitert das Abmelden, müssen die
            # Rückrufe trotzdem abgehängt werden, bevor ihre Objekte fallen.
            with contextlib.suppress(OSError, ValueError, ctypes.ArgumentError):
                self._driver.UnregisterConnexionClient(client)
            with contextlib.suppress(OSError, ValueError, ctypes.ArgumentError):
                self._driver.CleanupConnexionHandlers()
        self._handlers = ()


def default_reader(
    platform: str | None = None, *, driver_installed: Callable[[], bool] | None = None
) -> HidReader | DriverReader:
    """Der Leser dieses Rechners.

    Auf dem Mac mit installiertem 3DxWare der Treiber, HID als Rückfall für
    den angehaltenen Treiber; überall sonst HID. Die Plattform ist ein
    Parameter und keine Abfrage im Rumpf — dieselbe Überlegung wie bei
    ``updates.install_kind``: Ein Zweig hinter ``sys.platform`` wird auf der
    Maschine, auf der entwickelt wird, nie ausgeführt und nie geprüft.
    """
    chosen = sys.platform if platform is None else platform
    installed = driver_installed or (lambda: Path(DRIVER_FRAMEWORK).exists())
    if chosen == "darwin" and installed():
        return DriverReader(fallback=HidReader())
    return HidReader()


class SpaceMouseController(QObject):
    """Verbindet Leser und Abbildung mit der Kamera des Viewports.

    Berichte kommen über :meth:`handle_report` herein — vom :class:`HidReader`
    im Takt oder, im Test, direkt. Ein ``QTimer`` im Hauptthread liest und
    fährt die Kamera mit ~60 Hz; steht die Kappe, wird nichts gezeichnet. Es
    stauen sich keine Bilder: Je Takt ein Schritt mit der wirklich vergangenen
    Zeit, nach dem Loslassen steht die Kamera, wo die Hand aufhörte. Ohne
    offenes Gerät läuft nur die Suche, alle zwei Sekunden einmal.
    """

    deviceSeen = Signal()
    """Zum ersten Mal hat ein Gerät gemeldet — die Einstellungszeile darf erscheinen."""

    def __init__(
        self,
        viewport: Any,
        settings: Any,
        fit: Callable[[], None],
        parent: QObject | None = None,
        reader: HidReader | DriverReader | None = None,
    ) -> None:
        super().__init__(parent)
        self._viewport = viewport
        self._settings = settings
        self._fit = fit
        self._reader: HidReader | DriverReader = reader or default_reader()
        self._motion = Motion()
        self._last_report = 0.0
        self._last_tick = 0.0
        self._poll = QTimer(self)
        self._poll.setInterval(TICK_MS)
        self._poll.timeout.connect(self._tick)
        self._scan = QTimer(self)
        self._scan.setSingleShot(True)
        self._scan.timeout.connect(self._look_for_device)
        self._scan_wait = SCAN_MS
        self._was_active = False

    def start(self) -> None:
        """Nach einem Gerät sehen — erst wenn das Fenster steht, dann immer seltener."""
        if self._reader.is_open:
            return
        self._scan_wait = SCAN_MS
        self._scan.start(SCAN_FIRST_MS)

    def stop(self) -> None:
        """Gerät schließen, Takt anhalten."""
        self._poll.stop()
        self._scan.stop()
        self._reader.close()

    @property
    def motion(self) -> Motion:
        """Der zuletzt gelesene Zustand der Kappe."""
        return self._motion

    def _look_for_device(self) -> None:
        if self._reader.open():
            self._scan.stop()
            self._scan_wait = SCAN_MS
            self._last_tick = time.monotonic()
            self._poll.start()
            # Eingesteckt heißt gesehen: Die Einstellungszeile soll da sein,
            # bevor jemand die Kappe zum ersten Mal anfasst.
            self._mark_seen()
            return
        self._scan.start(self._scan_wait)
        self._scan_wait = min(SCAN_MAX_MS, self._scan_wait * 2)

    def _mark_seen(self) -> None:
        if not self._settings.spacemouse_seen:
            self._settings.spacemouse_seen = True
            self.deviceSeen.emit()

    def handle_report(self, data: bytes) -> None:
        """Ein Bericht des Geräts — Kappe oder Tasten."""
        previous = self._motion
        motion = decode_report(bytes(data), previous)
        self._motion = motion
        self._last_report = time.monotonic()
        self._mark_seen()
        if not self._settings.spacemouse_enabled:
            return
        # Eine Taste wirkt beim Drücken, nicht beim Halten — Flanke, nicht Pegel.
        if motion.buttons & ~previous.buttons:
            self._fit()

    def _tick(self) -> None:
        for report in self._reader.read():
            self.handle_report(report)
        if not self._reader.is_open:
            # Abgezogen: zurück zur Suche, die Kappe gilt als losgelassen.
            self._poll.stop()
            self._motion = Motion(buttons=self._motion.buttons)
            self._settle()
            self._scan_wait = SCAN_MS
            self._scan.start(self._scan_wait)
            return
        now = time.monotonic()
        dt = min(now - self._last_tick, 0.1)
        self._last_tick = now
        if self._motion.active() and now - self._last_report > HOLD_SECONDS:
            self._motion = replace(self._motion, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0)
        if self._motion.active():
            self._was_active = self.advance(dt) or self._was_active
        else:
            self._settle()

    def _settle(self) -> None:
        """Die Kappe ruht: was nach der Fahrt fällig ist, einmal erledigen."""
        if not self._was_active:
            return
        self._was_active = False
        settle = getattr(self._viewport, "settle_camera", None)
        if settle is not None:
            settle()

    def advance(self, dt: float) -> bool:
        """Einen Schritt fahren; wahr, wenn sich die Kamera bewegt hat."""
        plotter = getattr(self._viewport, "plotter", None)
        if plotter is None or not self._motion.active() or not self._settings.spacemouse_enabled:
            return False
        pose = CameraPose(*self._viewport.camera_pose())
        moved = camera_step(
            pose,
            self._motion,
            dt,
            speed=speed_factor(self._settings.spacemouse_speed),
            invert=bool(self._settings.spacemouse_invert),
            orbit=not bool(getattr(self._viewport, "sketch_active", False)),
        )
        if moved == pose:
            return False
        self._viewport.set_camera_pose(
            moved.position, moved.focal_point, moved.view_up, moved.parallel_scale
        )
        return True
