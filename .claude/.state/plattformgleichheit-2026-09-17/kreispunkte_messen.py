"""Welche Punkterzeugung ist über Plattformen bitgleich? (RM-187)

**Der Befund, der hierher führt** (17.09.2026, Lauf 35262208955): Die drei
Eingangskörper des Bohrungstests sind nicht auf allen Plattformen gleich. Der
**Klotz** — eine Box ohne jede transzendente Funktion — trägt auf Windows,
Ubuntu und macOS denselben Fingerabdruck. **Hohlraum und Nachbar**, beide aus
``cos`` und ``sin`` gebaut, tragen drei verschiedene. Die Abweichung entsteht
also vor der Booleschen Operation, in unserer eigenen Punkterzeugung.

Diese Sonde fragt weiter: **Welche** Art zu rechnen ist bitgleich? Gemessen
werden drei Wege zu denselben Kreispunkten — der heutige über ``np.cos``, der
über ``math.cos`` je Winkel, und einer, der die Plattform gar nicht fragt.

Ein vierter Weg stand hier und ist gefallen: nur ein Achtel auswerten und den
Rest spiegeln. Er lag **3,2 mm** neben der Wahrheit, weil die Winkelreduktion
in den Oktanten 1, 3, 5 und 7 rückwärts laufen muss und meine Tabelle das nicht
tat. Gefangen hat ihn die Abstandsmessung unten — deshalb steht sie da: Ein
Fingerabdruck allein hätte nur „anders" gesagt, nicht „falsch".

Die Zahlen sind kein Selbstzweck. Ist einer der Wege über alle drei Plattformen
bitgleich, ist der Plattformunterschied bei uns lösbar — und **kein anderer
Boolescher Kern** wäre dafür nötig, denn ein exakter Kern rechnet exakt mit den
Zahlen, die er bekommt.

Aufruf aus dem Wurzelverzeichnis des Arbeitsbaums::

    python .claude/.state/plattformgleichheit-2026-09-17/kreispunkte_messen.py
"""

from __future__ import annotations

import hashlib
import math
import sys
import time
from decimal import Decimal, getcontext

import numpy as np

SECTIONS = 120
RADIUS = 4.5


def fingerprint(values: np.ndarray) -> str:
    """Ein Hash über die rohen Bytes — gleiche Zahl heißt bitgleiches Feld."""
    return hashlib.sha256(np.ascontiguousarray(values, dtype=np.float64).tobytes()).hexdigest()[:16]


def der_heutige_weg() -> np.ndarray:
    """Wie ``_sloping_bore`` und ``trimesh`` es heute tun: NumPy über das ganze Feld.

    NumPy wählt seine Implementierung nach den Fähigkeiten der CPU — AVX-512,
    AVX2, NEON —, und die runden in der letzten Stelle verschieden.
    """
    angles = np.arange(SECTIONS) * math.tau / SECTIONS
    return np.stack([RADIUS * np.cos(angles), RADIUS * np.sin(angles)], axis=1)


def einzeln_durch_die_libm() -> np.ndarray:
    """Dieselbe Rechnung, aber je Winkel über ``math`` statt über das Feld.

    ``math.cos`` geht in die libm des Systems. Das ist eine andere
    Implementierung als NumPys vektorisierte — ob sie plattformgleich ist, ist
    genau die Frage.
    """
    angles = [index * math.tau / SECTIONS for index in range(SECTIONS)]
    return np.asarray(
        [(RADIUS * math.cos(angle), RADIUS * math.sin(angle)) for angle in angles],
        dtype=np.float64,
    )


def exakt_gerundet() -> np.ndarray:
    """Mit ``decimal`` auf fünfzig Stellen rechnen und einmal auf ``float`` runden.

    Das ist der einzige Weg in dieser Liste, der **von der Plattform nichts
    wissen will**: ``decimal`` ist reine Python-Ganzzahlarithmetik, und fünfzig
    Stellen liegen so weit über den sechzehn eines ``float``, dass die Rundung
    auf die letzte Stelle eindeutig ist. Der Preis ist Rechenzeit — für einen
    Kreis mit 120 Punkten ist er vernachlässigbar, für ein Netz mit
    Hunderttausenden Punkten wäre er es nicht.
    """
    getcontext().prec = 50
    zwei_pi = Decimal(2) * _pi()
    radius = Decimal(RADIUS)
    values = np.zeros((SECTIONS, 2), dtype=np.float64)
    for index in range(SECTIONS):
        angle = zwei_pi * Decimal(index) / Decimal(SECTIONS)
        values[index] = (float(radius * _cos(angle)), float(radius * _sin(angle)))
    return values


def _pi() -> Decimal:
    """Pi als feste Ziffernfolge — 88 Stellen, weit über den fünfzig der Rechnung.

    Keine Reihe: Pi ändert sich nicht, und eine Konstante kann nicht
    plattformweise streuen. Genau darum geht es hier.
    """
    return Decimal(
        "3.1415926535897932384626433832795028841971693993751"
        "0582097494459230781640628620899862803"
    )


def _cos(angle: Decimal) -> Decimal:
    """Kosinus über die Taylorreihe, abgebrochen wenn der Term nichts mehr ändert."""
    getcontext().prec += 5
    index, fact, num, sign, total = 0, Decimal(1), Decimal(1), 1, Decimal(1)
    while True:
        index += 2
        fact *= index * (index - 1)
        num *= angle * angle
        sign *= -1
        term = num / fact * sign
        if total + term == total:
            break
        total += term
    getcontext().prec -= 5
    return +total


def _sin(angle: Decimal) -> Decimal:
    """Sinus über die Taylorreihe, gleiche Bauart wie :func:`_cos`."""
    getcontext().prec += 5
    index, fact, num, sign, total = 1, Decimal(1), Decimal(angle), 1, Decimal(angle)
    while True:
        index += 2
        fact *= index * (index - 1)
        num *= angle * angle
        sign *= -1
        term = num / fact * sign
        if total + term == total:
            break
        total += term
    getcontext().prec -= 5
    return +total


def main() -> int:
    print(f"Plattform: {sys.platform} {getattr(sys.implementation, '_multiarch', '')}")
    print(f"NumPy    : {np.__version__}")
    print(f"SIMD     : {np.show_config('dicts').get('SIMD Extensions', '—')}\n")

    wege = (
        ("np.cos über das Feld (heute)", der_heutige_weg),
        ("math.cos je Winkel", einzeln_durch_die_libm),
        ("decimal, 50 Stellen", exakt_gerundet),
    )
    ergebnisse = {}
    for name, funktion in wege:
        werte = funktion()
        ergebnisse[name] = werte
        print(f"{name:32s} {fingerprint(werte)}")

    # Was der plattformfreie Weg kostet — gemessen, nicht geschätzt. Er ist der
    # einzige Kandidat, also entscheidet seine Rechenzeit, ob er infrage kommt.
    global SECTIONS
    print("\nWas decimal kostet:")
    for punkte in (120, 1_200, 12_000):
        vorher, SECTIONS = SECTIONS, punkte
        begonnen = time.perf_counter()
        exakt_gerundet()
        dauer = time.perf_counter() - begonnen
        SECTIONS = vorher
        print(f"  {punkte:6d} Punkte: {dauer * 1000:8.1f} ms")

    # Wie weit liegen die Wege auseinander? Eine Abweichung in der letzten
    # Stelle ist etwas anderes als ein Rechenfehler.
    print("\nAbstand zum genauesten Weg (decimal):")
    genau = ergebnisse["decimal, 50 Stellen"]
    for name, werte in ergebnisse.items():
        abstand = float(np.max(np.abs(werte - genau)))
        print(f"  {name:32s} {abstand:.3e} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
