"""Stabile Hashes für den Auswertungs-Cache (Bauplan §15, §38).

Der Hash einer Operation deckt alles, wovon ihr Ergebnis abhängt: die
Operation selbst, ihre aufgelösten Parameter, die Hashes ihrer Eingaben,
Profil, Qualitätsstufe und Startwert. Daraus fallen zwei Folgen:

* eine Parameteränderung entwertet nur den Zweig darunter — der Rest kommt aus
  dem Cache, und genau das hält eine Parameteränderung unter zwei
  Sekunden (§31);
* der Hash ist über Prozesse hinweg stabil und kann darum eine Datei im
  Platten-Cache benennen.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.types import Operation, Profile, Quality


def _canonical(value: Any) -> Any:
    """Macht aus einem Wert etwas, das json jedes Mal gleich hinschreibt."""
    if isinstance(value, float):
        # repr behält die volle doppelte Genauigkeit; Rundung hier würde
        # verschiedene Läufe zusammenwerfen.
        return ["f", repr(value)]
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, str | bytes):
        return value.decode() if isinstance(value, bytes) else value
    if isinstance(value, Sequence):
        return [_canonical(entry) for entry in value]
    return value


def digest(*parts: Any) -> str:
    """Ein kurzer, stabiler Hash über alles, was json darstellen kann."""
    text = json.dumps([_canonical(part) for part in parts], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def profile_key(profile: Profile) -> str:
    """Was an einem Profil ein Ergebnis ändern kann: Toleranzen und
    Düsengeometrie."""
    printer = profile.printer
    material = profile.material
    return digest(
        printer.id,
        printer.nozzle_diameter,
        printer.layer_height,
        printer.extrusion_width,
        printer.build_volume,
        material.id,
        material.clearance,
        material.press,
        material.hole_compensation,
        material.elephant_foot,
        material.shrinkage,
    )


def operation_hash(
    operation: Operation,
    params: Mapping[str, Any],
    input_hashes: Sequence[str],
    profile: Profile,
    quality: Quality,
) -> str:
    """Die Identität eines gerechneten Ergebnisses."""
    return digest(
        operation.op,
        params,
        list(input_hashes),
        profile_key(profile),
        quality,
        operation.seed,
    )


def object_hash(operation_key: str, position: int) -> str:
    """Die Identität eines Ausgabeobjekts einer Operation."""
    return digest(operation_key, position)
