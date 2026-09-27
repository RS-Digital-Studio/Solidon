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
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from app.core.scene import cache
from app.core.types import Feature, Operation, Profile, Quality

if TYPE_CHECKING:
    from app.core.geom.mesh import MeshData


def _canonical(value: Any) -> Any:
    """Macht aus einem Wert etwas, das json jedes Mal gleich hinschreibt."""
    if isinstance(value, float):
        # repr behält die volle doppelte Genauigkeit; Rundung hier würde
        # verschiedene Läufe zusammenwerfen. ``float()`` davor, weil ein
        # ``np.float64`` sich als ``np.float64(1.5)`` schreibt und nach der
        # Rundreise durch den Plattencache als ``1.5`` — derselbe Wert, zwei
        # Hashes, und jeder Treffer nach dem Wiederöffnen ein Fehltreffer.
        return ["f", repr(float(value))]
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
    """Was an einem Profil ein Ergebnis ändern kann: Toleranzen,
    Düsengeometrie — und das Verfahren, denn ein auf Resin umgestelltes
    Projekt darf seine Befunde nicht aus dem FDM-Cache holen.

    **Und die Zahl der Düsen.** *Auf dem Bett anordnen* und *Druckoptimal
    ausrichten* legen die Filamente nur dann auf eigene Platten, wenn der
    Drucker weniger Düsen als Filamente hat (``prepare_ops._filament_groups``).
    Der Druckdialog speichert eine geänderte Düsenzahl unter derselben
    Druckerkennung und rechnet die Szene neu — ohne die Zahl hier kam die
    Anordnung der alten Düsenzahl aus dem Cache zurück, über das Schließen
    hinaus (Durchsicht 0.5.0, 22.09.2026).

    Welches Feld hier fehlen darf, weil keine Operation es liest, hält
    ``tests/test_cache.py`` je Feld fest: Ein neues Profilfeld ist damit eine
    Entscheidung und keine stille Lücke im Schlüssel."""
    printer = profile.printer
    material = profile.material
    return digest(
        printer.id,
        printer.technology,
        printer.nozzle_diameter,
        printer.layer_height,
        printer.extrusion_width,
        printer.pixel_size,
        printer.minimum_wall,
        printer.build_volume,
        printer.printable_area,
        printer.bed_exclusions,
        printer.printable_height,
        printer.nozzles,
        # Die Überhanggrenze des Herstellers (27.09.2026). Sie wirkt über
        # ``profile.overhang_limit_degrees`` darunter — aber nur ohne passende
        # Probe; das Feld selbst steht hier, damit der Schlüssel nicht davon
        # abhängt, ob gerade eine Messung davorsteht.
        printer.overhang_limit,
        material.id,
        material.clearance,
        material.press,
        material.hole_compensation,
        material.elephant_foot,
        material.shrinkage,
        material.youngs_modulus,
        material.yield_strength,
        material.layer_bond_ratio,
        profile.minimum_wall_thickness,
        profile.overhang_limit_degrees,
    )


def operation_hash(
    operation: Operation,
    params: Mapping[str, Any],
    input_hashes: Sequence[str],
    profile: Profile,
    quality: Quality,
    *,
    implementation_version: str = "",
    material_profiles: Mapping[str, Profile] | None = None,
) -> str:
    """Die Identität eines gerechneten Ergebnisses."""
    return digest(
        cache.CACHE_FORMAT_VERSION,
        operation.op,
        params,
        list(input_hashes),
        profile_key(profile),
        quality,
        operation.seed,
        implementation_version,
        *(
            [{name: profile_key(value) for name, value in material_profiles.items()}]
            if material_profiles
            else []
        ),
    )


#: Teilhashes je Merkmalsobjekt innerhalb einer Auswertung: die Kennung des
#: Objekts, das Objekt selbst (damit die Kennung nicht wiedervergeben wird)
#: und sein Hash.
FeatureMemo = dict[int, tuple[Feature, bytes]]


def _index_bytes(indices: Sequence[int]) -> bytes:
    """Dreiecksindizes als rohe Bytes statt als JSON-Liste.

    Ein Lochblech 20 mal 20 trägt 406 Merkmale mit 156 824 Indizes; als
    JSON-Text gehasht kostete das 88,7 ms je Auswertung, warm 74 Prozent
    eines Kantenschritts (Review, 21.09.2026). Ein ``int64``-Feld ist über
    Prozesse und Plattformen dieselbe Bytefolge.
    """
    return np.asarray(indices, dtype=np.int64).tobytes()


def feature_digest(feature: Feature, name: str) -> bytes:
    """Der Teilhash eines Merkmals unter seinem Namen — derselbe Codec wie auf der Platte."""
    data = cache.feature_to_data(feature)
    indices = data.pop("face_indices")
    patches = data.pop("surface_patches")
    checksum = hashlib.sha256(bytes.fromhex(digest(name, data)))
    checksum.update(_index_bytes(indices))
    for patch in patches:
        patch_indices = patch.pop("face_indices")
        checksum.update(bytes.fromhex(digest(patch)))
        checksum.update(_index_bytes(patch_indices))
    return checksum.digest()


def object_hash(
    operation_key: str,
    position: int,
    reserved_feature_ids: Sequence[str] = (),
    cavity: MeshData | None = None,
    *,
    features: Mapping[str, Feature] | None = None,
    check_cancelled: Callable[[], None] | None = None,
    memo: FeatureMemo | None = None,
) -> str:
    """Die Ausgabe samt tatsächlicher Merkmalsbindung für nachfolgende Operationen.

    ``memo`` hält die Teilhashes je Merkmalsobjekt für eine Auswertung: Ein
    Merkmal, das unverändert durch fünf Schritte reist, ist fünfmal dasselbe
    Objekt (``_inherited_features`` reicht es durch) und wird einmal gehasht.
    """
    if check_cancelled is not None:
        check_cancelled()
    cavity_key = None
    if cavity is not None:
        # Die geometrische Auskunft ist ein weiterer Op-Eingang. Keine
        # JSON-Punktlisten: Die numerischen Arrays lassen sich direkt hashen.
        checksum = hashlib.sha256(cavity.raw.vertices.tobytes())
        checksum.update(cavity.raw.faces.tobytes())
        cavity_key = checksum.hexdigest()
    feature_key = None
    if features:
        checksum = hashlib.sha256()
        # Derselbe vollständige Codec wie auf der Platte. Je Merkmal wird nur
        # ein fester Teilhash gehalten, keine zweite Gesamtkopie aller Träger.
        for name in sorted(features):
            if check_cancelled is not None:
                check_cancelled()
            feature = features[name]
            remembered = memo.get(id(feature)) if memo is not None else None
            if remembered is not None and remembered[0] is feature and remembered[0].id == name:
                part = remembered[1]
            else:
                part = feature_digest(feature, name)
                if memo is not None and feature.id == name:
                    memo[id(feature)] = (feature, part)
            checksum.update(part)
        feature_key = checksum.hexdigest()
    key = digest(operation_key, position, sorted(reserved_feature_ids), cavity_key, feature_key)
    if check_cancelled is not None:
        check_cancelled()
    return key
