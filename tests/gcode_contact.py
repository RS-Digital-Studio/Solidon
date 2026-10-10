"""Wo die Stütze das Modell berührt, gemessen im G-Code eines echten Slicers (RM-624).

Nur ``test_real_slicers.py`` braucht die Messung, deshalb ein eigenes Modul und
nicht ``tests/helpers.py``: Das importieren über 170 Testdateien, und
``tools/ci_selection.py`` wählte bei jeder Änderung hier 39 Fensterdateien für
Linux und macOS mit.
"""

from __future__ import annotations

import dataclasses
import math
import re
import statistics

from app.core.slice.gcode import _arc_center, _arc_sweep

#: Kantenlänge einer Rasterzelle der Kontaktmessung in der Aufsicht, in mm. Zwei
#: statt einem halben: Eine weite Trennschicht (Lücke 1,2 mm) traf mit 0,5 mm
#: viele Zellen ihrer obersten Lage nicht, und die Messung nahm eine Lage tiefer.
CONTACT_CELL = 2.0
#: Wie viel Luft zwischen Stütze und Modell noch als Kontakt zählt, in mm; mehr
#: ist Stütze neben dem Modell, nicht darunter.
CONTACT_AIR = 1.0
_INTERFACE = ("support interface", "support material interface", "support-interface")
#: Bambus Übergangslage unter der Trennschicht ist Stütze, kein Modell.
_SUPPORT = ("support", "support material", "support transition")
#: PrusaSlicer schreibt Schürze und Rand als einen Typ, ``Skirt/Brim``; als
#: Modell gezählt, zog er die Aufsicht über den Sockel hinaus.
_SKIPPED = ("skirt", "brim", "skirt/brim", "custom", "prime tower", "wipe tower")
#: Bambu Studio schreibt ``; FEATURE:``, die übrigen ``;TYPE:``.
_TYPED = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$")
#: Die Höhe der folgenden Bahnen: ``;HEIGHT:`` in der Orca-Familie und in
#: PrusaSlicer, ``; LAYER_HEIGHT:`` in Bambu Studio — beim Schichtwechsel und
#: wieder, sobald eine Bahn anders hoch ist. So liest sie auch die Vorschau der
#: Programme.
_HEIGHT = re.compile(r"^;\s*(?:HEIGHT|LAYER_HEIGHT)\s*:\s*(-?\d*\.?\d+)\s*$")
#: PrusaSlicer schreibt Koordinaten ohne führende Null („Z.2“).
_NUMBER = re.compile(r"([XYZEIJR])(-?\d*\.?\d+)")
#: Bewegungen: ``G0``/``G1`` gerade, ``G2`` im Uhrzeigersinn, ``G3`` dagegen.
_MOVES = {"G0": 0, "G1": 1, "G2": 2, "G3": 3}
_CARRIED = frozenset({"support", "interface"})

Cell = tuple[int, int]


@dataclasses.dataclass(frozen=True)
class SupportContact:
    """Wo die Stütze das Modell berührt, gemessen im G-Code (:func:`support_contact`).

    Je Seite der Median der Luft zwischen Stütze und Modell in mm und der
    Trennschichten daran, dazu die Zahl der Rasterzellen mit Kontakt — ohne
    Zellen sagt der Median nichts.
    """

    top_gap: float | None
    top_interface_layers: float | None
    top_cells: int
    bottom_gap: float | None
    bottom_interface_layers: float | None
    bottom_cells: int


def _kind(name: str) -> str | None:
    lowered = name.strip().lower()
    if lowered in _INTERFACE:
        return "interface"
    if lowered in _SUPPORT:
        return "support"
    if lowered in _SKIPPED:
        return None
    return "model"


def _layer_heights(levels: set[float]) -> dict[float, float]:
    ordered = sorted(levels)
    return {
        level: round(level - (ordered[index - 1] if index else 0.0), 3)
        for index, level in enumerate(ordered)
    }


def _samples(
    code: int, start: tuple[float, float], end: tuple[float, float], words: dict[str, float]
) -> list[tuple[float, float]]:
    """Punkte entlang einer Bahn, höchstens :data:`CONTACT_CELL` auseinander.

    Ein Bogen (``G2``/``G3``) läuft über seinen Mittelpunkt aus ``I``/``J`` oder
    ``R`` (:func:`app.core.slice.gcode._arc_center`), nicht über die Sehne:
    Bambu Studio und PrusaSlicer biegen Wände und Baumstützen in Bögen, und die
    Sehne liefe durch Zellen, die die Bahn nie berührt.
    """
    if code in (2, 3):
        clockwise = code == 2
        centre = _arc_center(start, end, words, clockwise=clockwise)
        if centre is not None:
            radius = math.hypot(start[0] - centre[0], start[1] - centre[1])
            if radius > 0.0:
                begin = math.atan2(start[1] - centre[1], start[0] - centre[0])
                finish = math.atan2(end[1] - centre[1], end[0] - centre[0])
                full = math.isclose(start[0], end[0]) and math.isclose(start[1], end[1])
                sweep = _arc_sweep(begin, finish, clockwise=clockwise, full=full)
                steps = max(1, math.ceil(radius * sweep / CONTACT_CELL))
                turn = -sweep if clockwise else sweep
                return [
                    (
                        centre[0] + radius * math.cos(begin + turn * step / steps),
                        centre[1] + radius * math.sin(begin + turn * step / steps),
                    )
                    for step in range(steps + 1)
                ]
    dx, dy = end[0] - start[0], end[1] - start[1]
    steps = max(1, math.ceil(max(abs(dx), abs(dy)) / CONTACT_CELL))
    return [
        (start[0] + dx * step / steps, start[1] + dy * step / steps) for step in range(steps + 1)
    ]


def _inside(key: Cell, footprint: set[Cell], reach: int) -> bool:
    """Liegt die Zelle mindestens ``reach`` Zellen je Achse innerhalb der Aufsicht?"""
    return all(
        (key[0] + dx, key[1] + dy) in footprint
        for dx in range(-reach, reach + 1)
        for dy in range(-reach, reach + 1)
    )


def support_contact(text: str, inset: float = 0.0) -> SupportContact:
    """Abstand und Trennschichten zwischen Stütze und Modell in einem G-Code (RM-624).

    Ein Raster von :data:`CONTACT_CELL` in der Aufsicht; je Zelle die Ebenen mit
    Modell-, Stütz- und Trennschichtbahn. Höchstens :data:`CONTACT_AIR` Luft ist
    Kontakt.

    **Oben** zählt eine Ebene nur mit Modell über einer mit Trennschicht: Luft
    ist die Unterkante der Modellschicht (Ebene minus Schichthöhe des Modells)
    minus die Ebene darunter, dazu die Trennschichten direkt darunter.

    **Unten** zählt die unterste Stützebene über einer Ebene nur mit Modell. Ihre
    Unterkante ist die Ebene minus die Höhe der Stützbahn dort, wie der Slicer
    sie schreibt (``;HEIGHT:``, ``; LAYER_HEIGHT:``). Aus allen Stützebenen des
    Drucks zusammen gerechnet, mischte sie die Stapel verschiedener Stellen: Mit
    eigener Stützschichthöhe liegen Säulen neben dem Sockel auf anderen Ebenen
    als die Stütze darauf, und die Unterseite maß 0 mm. Ohne Höhenangabe —
    CuraEngine schreibt keine — gilt der Schritt zur nächsten Stützebene
    derselben Zelle.

    **Extrusion wird gezählt, wie der Drucker sie fährt**: relativ (``M83``) ist
    jeder positive ``E``-Wert Material, absolut (``M82``) jeder Anstieg — und
    ``G92 E…`` setzt den Zähler zurück. Die historischen Messleser kannten das
    Rücksetzen nicht; nach ``G92 E0`` galt jede Bahn als Leerfahrt, bis der
    Zähler den alten Stand wieder überstieg. Bögen (``G2``/``G3``) zählen wie
    Geraden und führen die Position nach (:func:`_samples`).

    ``inset`` nimmt nur Zellen, deren Mitte je Achse mindestens so weit von jeder
    Zelle außerhalb der Aufsicht entfernt ist; die Aufsicht sind alle Zellen mit
    einer Modellbahn auf irgendeiner Ebene. Am Rand teilen sich Außenwand und eine
    Stützsäule daneben eine Zelle, und die Säule auf dem Bett zählte als Stütze
    mit 0 mm Luft auf dem Modell — am ElegooSlicer 898 solcher Zellen gegen die
    echten.
    """
    cells: dict[Cell, dict[float, set[str]]] = {}
    #: Je Zelle und Ebene die größte Höhe einer Stützbahn: die tiefste Unterkante.
    carried_height: dict[tuple[Cell, float], float] = {}
    x = y = z = e = 0.0
    height: float | None = None
    kind: str | None = None
    relative_e = False
    model_levels: set[float] = set()
    for line in text.splitlines():
        typed = _TYPED.match(line)
        if typed:
            kind = _kind(typed.group(1))
            continue
        tall = _HEIGHT.match(line)
        if tall:
            height = float(tall.group(1))
            continue
        command = line.split(";", 1)[0].strip()
        if not command:
            continue
        word = command.split(maxsplit=1)[0].upper()
        if word == "M83":
            relative_e = True
            continue
        if word == "M82":
            relative_e = False
            continue
        values = {key: float(number) for key, number in _NUMBER.findall(command)}
        if word == "G92":
            e = values.get("E", e)
            continue
        code = _MOVES.get(word)
        if code is None:
            continue
        new_x, new_y = values.get("X", x), values.get("Y", y)
        z = values.get("Z", z)
        extruded = "E" in values and (values["E"] > 0.0 if relative_e else values["E"] > e)
        if "E" in values and not relative_e:
            e = values["E"]
        if extruded and kind is not None:
            level = round(z, 3)
            if kind == "model":
                model_levels.add(level)
            for px, py in _samples(code, (x, y), (new_x, new_y), values):
                key = (int(px // CONTACT_CELL), int(py // CONTACT_CELL))
                cells.setdefault(key, {}).setdefault(level, set()).add(kind)
                if kind in _CARRIED and height is not None:
                    slot = (key, level)
                    carried_height[slot] = max(carried_height.get(slot, 0.0), height)
        x, y = new_x, new_y
    # Die Schichthöhe des Modells aus seinen Ebenen, nicht aus der Bahnhöhe:
    # Brücken schreiben PrusaSlicer und Bambu Studio mit der Bahnhöhe 0,4, auch
    # über der Stütze, und deren Unterkante läge eine Schicht zu tief.
    model_height = _layer_heights(model_levels)
    footprint = {
        key for key, column in cells.items() if any("model" in kinds for kinds in column.values())
    }
    # Je Achse so viele Zellen, wie die Mitte vom Rand mindestens entfernt sein
    # muss: Die nächste Kante einer Zelle d Schritte weiter liegt (d - 0,5)
    # Zellen von der Mitte.
    reach = max(0, math.ceil(inset / CONTACT_CELL + 0.5) - 1)
    top: list[tuple[float, int]] = []
    bottom: list[tuple[float, int]] = []
    for key, column in cells.items():
        if len(column) < 2 or not _inside(key, footprint, reach):
            continue
        levels = sorted(column)
        for index in range(1, len(levels)):
            here, below = column[levels[index]], column[levels[index - 1]]
            # Steht Modell jenseits des Kontakts in derselben Zelle — unter der
            # Trennschicht oder über der untersten Stützebene —, stehen Wand und
            # Stütze nebeneinander: Mit eigener Stützschichthöhe wechseln sich
            # dort Modell- und Stützebenen ab, und jede Paarung maß zwischen
            # -0,24 und 0,13 mm.
            under = column[levels[index - 2]] if index >= 2 else set()
            over = column[levels[index + 1]] if index + 1 < len(levels) else set()
            if (
                "model" in here
                and not here & _CARRIED
                and "interface" in below
                and "model" not in under
            ):
                top_gap = round(
                    levels[index] - model_height.get(levels[index], 0.2) - levels[index - 1], 3
                )
                if top_gap <= CONTACT_AIR:
                    count = 0
                    for lower in reversed(levels[:index]):
                        if "interface" not in column[lower]:
                            break
                        count += 1
                    top.append((top_gap, count))
            if (
                here & _CARRIED
                and "model" in below
                and not below & _CARRIED
                and "model" not in over
            ):
                thickness = carried_height.get((key, levels[index]))
                if thickness is None:
                    above = [level for level in levels[index + 1 :] if column[level] & _CARRIED]
                    if not above:
                        continue
                    thickness = above[0] - levels[index]
                bottom_gap = round(levels[index] - thickness - levels[index - 1], 3)
                if bottom_gap <= CONTACT_AIR:
                    count = 0
                    for upper in levels[index:]:
                        if "interface" not in column[upper]:
                            break
                        count += 1
                    bottom.append((bottom_gap, count))

    def median(values: list[float]) -> float | None:
        return round(statistics.median(values), 3) if values else None

    return SupportContact(
        top_gap=median([gap for gap, _ in top]),
        top_interface_layers=median([float(count) for _, count in top]),
        top_cells=len(top),
        bottom_gap=median([gap for gap, _ in bottom]),
        bottom_interface_layers=median([float(count) for _, count in bottom]),
        bottom_cells=len(bottom),
    )
