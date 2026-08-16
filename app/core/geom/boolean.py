"""Boolesche Operationen mit der Rückfallkette (Bauplan §17.2).

| Stufe | Was sie tut                                     | Vermerk     |
|-------|-------------------------------------------------|-------------|
| 1     | direkt durch den Kern                           | ``direct``  |
| 2     | verschweißen, aufräumen, erneut                 | ``welded``  |
| 3     | die Eingangsgeometrie minimal stören            | ``jittered``|
| 4     | auf Voxeln rechnen, das Ergebnis neu vernetzen  | ``voxel``   |
| 5     | aufgeben, mit Befund und Weg nach vorn          | —           |

Die Stufe, die es geschafft hat, wird in die Operation geschrieben — so
rechnet dieselbe Datei gleich nach (§11.3), und der Bericht kann sagen, was
die Zahlen wert sind. Stufe 4 kostet Genauigkeit und läuft nie
stillschweigend.

In Entwurfsqualität endet die Kette nach Stufe 2 — das Iterieren bleibt
schnell (§31).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import trimesh

from app.core.errors import CANCEL, CORRECT_INPUT, PROGRAMMING_ERRORS, BooleanFailedError
from app.core.geom.attributes import DEFAULT_CUT_SLOT, transfer
from app.core.geom.mesh import MeshData
from app.core.geom.repair import merge_vertices, remove_degenerate_faces
from app.core.log import get_logger
from app.core.types import CancelToken, Finding, Quality, SolverInfo, SolverStage
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

BooleanKind = Literal["union", "difference", "intersection"]

#: Die volle Kette, und die verkürzte für Entwurfsqualität (§31).
FULL_CHAIN: tuple[SolverStage, ...] = ("direct", "welded", "jittered", "voxel")
DRAFT_CHAIN: tuple[SolverStage, ...] = ("direct", "welded")

#: Wie weit Stufe 3 die Eckpunkte bewegt: genug, um ein Zusammenfallen zu
#: brechen, weit unter allem, was ein Drucker auflösen könnte.
JITTER_AMPLITUDE = 1e-4

#: Kantenlänge des Voxelrasters in Stufe 4, relativ zur Modelldiagonale.
VOXEL_PITCH_RELATIVE = 0.004


@dataclass(slots=True)
class BooleanOutcome:
    """Das Ergebnis, plus wie es erreicht wurde."""

    mesh: MeshData
    solver: SolverInfo
    findings: list[Finding] = field(default_factory=list)


def boolean(
    kind: BooleanKind,
    meshes: list[MeshData],
    *,
    quality: Quality = "fine",
    seed: int | None = None,
    stages: tuple[SolverStage, ...] | None = None,
    cut_slot: int = DEFAULT_CUT_SLOT,
    allow_empty: bool = False,
    cancelled: CancelToken | None = None,
) -> BooleanOutcome:
    """Führt eine Boolesche Operation aus und fällt Stufe um Stufe zurück, bis
    eine hält.

    ``cut_slot`` ist, was eine frisch geschnittene Fläche bekommt (§20): per
    Vorgabe der Slot des Körpers, der geschnitten wird — ein Loch durch ein
    zweifarbiges Teil streicht seine Wand so nicht in der Farbe, die das
    Werkzeug zufällig hatte.

    ``allow_empty`` sagt: Nichts ist eine Antwort. Bei einer Differenz, die
    jemand wollte, heißt ein leeres Ergebnis, dass der Kern aufgegeben hat und
    die nächste Stufe dran ist — dafür ist die Kette da. Bei einer
    Verschneidung kann es heißen, dass die zwei Körper sich schlicht nicht
    treffen — und drei weitere Stufen laufen zu lassen, um dasselbe noch
    einmal zu hören, macht aus einer Tatsache eine Ausnahme, die der Aufrufer
    auseinandernehmen muss.
    """
    if len(meshes) < 2:
        raise ValueError("a boolean operation needs at least two bodies")

    chain = stages if stages is not None else (FULL_CHAIN if quality == "fine" else DRAFT_CHAIN)
    attempted: list[SolverStage] = []
    emptied = False
    """Ob eine Stufe sauber gerechnet hat und dabei nichts übrig blieb.

    Das ist kein Scheitern des Verfahrens, sondern eine Aussage über die
    Eingabe: eine Bohrung mit 200 mm Durchmesser in einer 80er Platte frisst
    sie ganz. Ohne diese Unterscheidung liefen alle vier Stufen durch und der
    Nutzer las am Ende „Auch die letzte Rückfallstufe hat kein brauchbares
    Ergebnis geliefert" — die Sprache des Rechenkerns für etwas, das aus den
    Maßen folgt.
    """

    for stage in chain:
        # Zwischen den Stufen, nicht mittendrin: eine Stufe ist ein nativer
        # Aufruf und kooperativ nicht zu unterbrechen — aber vier Versuche
        # plus Voxelisierung an einem großen Netz waren als Ganzes
        # unabbrechbar, und §15.6 verlangt „jederzeit abbrechbar".
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        attempted.append(stage)
        try:
            result = _run_stage(kind, meshes, stage, seed)
        except PROGRAMMING_ERRORS:
            # Die Stufen rufen mit eigenen Argumenten — ``voxelized(pitch=...)``,
            # ``matrix_to_marching_cubes(matrix=..., pitch=...)``. Fiele ein
            # falscher Aufruf in den Handler darunter, sähe er aus wie vier
            # Kerne, die nacheinander aufgeben, und der Nutzer läse am Ende, es
            # liege an seiner Geometrie.
            raise
        except Exception as problem:  # Kerne scheitern auf kerneigene Arten
            _log.info("boolean stage %s failed: %s", stage, problem)
            continue
        if result is None or not _plausible(result, allow_empty):
            if result is not None and result.triangle_count == 0:
                emptied = True
            _log.info("boolean stage %s produced nothing usable", stage)
            continue
        return BooleanOutcome(
            # Nichts hat keine Flächen zum Färben, und die Übertragung suchte
            # die nächste Oberfläche eines Körpers, der keine hat.
            mesh=result
            if result.triangle_count == 0
            else _keep_slots(result, meshes, kind, stage, cut_slot),
            solver=SolverInfo(
                strategy=stage,
                attempted=tuple(attempted),
                seed=seed if stage == "jittered" else None,
            ),
            findings=list(_findings_for(stage)),
        )

    if emptied:
        # Kein Rückfall hilft gegen Maße. Der Satz sagt, was zu sehen wäre,
        # und die Handlung dazu ist eine andere als beim Kernversagen: nicht
        # reparieren, sondern nachrechnen.
        raise BooleanFailedError(
            detail=_(
                "Von dem Körper bleibt nichts übrig — das Werkzeug deckt ihn "
                "vollständig ab. Prüfen Sie Maß und Lage."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
            attempted=tuple(attempted),
            seed=seed,
        )
    raise BooleanFailedError(
        detail=_("Auch die letzte Rückfallstufe hat kein brauchbares Ergebnis geliefert."),
        attempted=tuple(attempted),
        seed=seed,
    )


def _keep_slots(
    result: MeshData,
    sources: list[MeshData],
    kind: BooleanKind,
    stage: SolverStage,
    cut_slot: int,
) -> MeshData:
    """§20: die Slot-Zuweisung überlebt die Operation.

    Belassen wird sie nur, wo der Kern die Dreiecke wirklich unverändert
    durchgereicht hat. Nach der Voxelstufe ist das nie der Fall — die
    Vernetzung wurde ersetzt —, dort läuft die Übertragung immer.

    Nur die Körper, die noch *im* Ergebnis sind, geben ihre Farbe weiter. Bei
    einer Differenz ist das Werkzeug fort, und die Bohrungswand, die es
    hinterließ, ist eine neue Oberfläche, kein Stück des Bohrers — sonst käme
    ein Loch durch ein rotes Teil in der Farbe heraus, die das Werkzeug
    zufällig hatte.
    """
    if stage != "voxel" and len(result.slots) == len(result.raw.faces) and result.slots:
        return result
    tolerance = None
    if stage == "voxel":
        # Die Treppe des Rasters ist überall einen halben Voxel tief; enger
        # gemessen verlöre der Körper seine Farbe an die eigene Vernetzung
        # statt an die Operation.
        diagonal = max(mesh.bounds.diagonal for mesh in sources)
        tolerance = max(diagonal * VOXEL_PITCH_RELATIVE, 0.05) * 1.5
    carriers = sources[:1] if kind == "difference" else sources
    return transfer(result, carriers, cut_slot=cut_slot, tolerance=tolerance)


def _run_stage(
    kind: BooleanKind, meshes: list[MeshData], stage: SolverStage, seed: int | None
) -> MeshData | None:
    if stage == "direct":
        return _kernel(kind, [mesh.raw for mesh in meshes], meshes[0])
    if stage == "welded":
        cleaned = [remove_degenerate_faces(merge_vertices(mesh)[0])[0] for mesh in meshes]
        return _kernel(kind, [mesh.raw for mesh in cleaned], meshes[0])
    if stage == "jittered":
        disturbed = [_jitter(mesh, seed, index) for index, mesh in enumerate(meshes)]
        return _kernel(kind, [mesh.raw for mesh in disturbed], meshes[0])
    return _voxel(kind, meshes)


def _kernel(kind: BooleanKind, bodies: list[trimesh.Trimesh], like: MeshData) -> MeshData | None:
    operation = {
        "union": trimesh.boolean.union,
        "difference": trimesh.boolean.difference,
        "intersection": trimesh.boolean.intersection,
    }[kind]
    result = operation(bodies)
    if result is None:
        return None
    # Ein leerer Körper wird weitergereicht statt hier verschluckt: ob Nichts
    # eine Antwort oder ein Scheitern ist, entscheidet _plausible — die
    # einzige Stelle, die weiß, was der Aufrufer wollte.
    return like.replacing(result)


def _jitter(mesh: MeshData, seed: int | None, index: int) -> MeshData:
    """Stufe 3: die Eckpunkte anstupsen, damit zusammenfallende Flächen
    aufhören zusammenzufallen.

    Der Startwert wird bei der Operation gespeichert, damit derselbe Stups
    wieder passiert (§11.3) — ohne ihn wäre das Ergebnis unreproduzierbar.
    """
    generator = np.random.default_rng((seed or 0) + index)
    body = mesh.raw.copy()
    scale = max(mesh.bounds.diagonal, 1.0) * JITTER_AMPLITUDE
    body.vertices = body.vertices + generator.normal(scale=scale, size=body.vertices.shape)
    return mesh.replacing(body)


def _voxel(kind: BooleanKind, meshes: list[MeshData]) -> MeshData | None:
    """Stufe 4: die Frage auf einem Raster entscheiden, die Antwort neu
    vernetzen.

    Robust, wo die Topologie es nicht ist, und es kostet Genauigkeit — darum
    sagt der Bericht es jedes Mal, wenn diese Stufe benutzt wurde (§17.3).
    """
    diagonal = max(mesh.bounds.diagonal for mesh in meshes)
    pitch = max(diagonal * VOXEL_PITCH_RELATIVE, 0.05)

    # Ein Raster für alle Körper. Eine Differenz macht den ersten nur kleiner,
    # alles andere darf über ihn hinauswachsen — das Raster spannt sich also
    # über alle.
    low = np.min([np.asarray(mesh.bounds.minimum) for mesh in meshes], axis=0) - pitch * 2
    high = np.max([np.asarray(mesh.bounds.maximum) for mesh in meshes], axis=0) + pitch * 2
    shape = tuple(int(np.ceil(value)) for value in (high - low) / pitch + 1)

    combined = _rasterise(meshes[0], low, pitch, shape)
    for mesh in meshes[1:]:
        other = _rasterise(mesh, low, pitch, shape)
        if kind == "union":
            combined = combined | other
        elif kind == "difference":
            combined = combined & ~other
        else:
            combined = combined & other

    if not combined.any():
        # Leer, und Marching Cubes hat nichts zum Ablaufen. Wie bei den
        # Kernstufen: der leere Körper geht weiter, _plausible urteilt.
        return meshes[0].replacing(trimesh.Trimesh())
    body = trimesh.voxel.ops.matrix_to_marching_cubes(matrix=combined, pitch=pitch)
    # matrix_to_marching_cubes legt Zelle (0,0,0) an den Ursprung; aufs Raster
    # zurückschieben.
    body.apply_translation(low)
    return meshes[0].replacing(body)


def _rasterise(
    mesh: MeshData, origin: np.ndarray, pitch: float, shape: tuple[int, ...]
) -> np.ndarray:
    """Legt einen Körper auf das gemeinsame Raster."""
    grid = mesh.raw.voxelized(pitch=pitch).fill()
    offset = np.round((np.asarray(grid.transform)[:3, 3] - origin) / pitch).astype(int)
    target = np.zeros(shape, dtype=bool)
    source = np.asarray(grid.matrix, dtype=bool)

    starts = np.maximum(offset, 0)
    ends = np.minimum(offset + np.array(source.shape), np.array(shape))
    if np.any(ends <= starts):
        return target

    target_slice = tuple(slice(int(a), int(b)) for a, b in zip(starts, ends, strict=True))
    source_slice = tuple(
        slice(int(a - o), int(b - o)) for a, b, o in zip(starts, ends, offset, strict=True)
    )
    target[target_slice] = source[source_slice]
    return target


def shared_volume(first: trimesh.Trimesh, second: trimesh.Trimesh) -> float:
    """Wie viel Volumen zwei Körper gemeinsam haben — Berührung zählt als
    keines.

    Körper, die sich nur an einer Fläche treffen — ein Deckel auf seinem Rand,
    ein Teil auf der Platte, zwei Hälften einer Teilung — verschneiden sich zu
    einer flachen Schale. Die ist geschlossen, nennt sich also wasserdicht,
    hat aber in einer Richtung keine Ausdehnung. trimesh nach ihrem Volumen zu
    fragen rechnet null und teilt dann den Schwerpunkt dadurch — eine Warnung
    über eine Zahl, die niemand wollte: Berühren ist kein geteiltes Volumen,
    und der Hüllquader sagt das, bevor irgendein Integral läuft.
    """
    try:
        shared = trimesh.boolean.intersection([first, second])
    except PROGRAMMING_ERRORS:
        raise
    except Exception:  # Kerne scheitern auf kerneigene Arten
        return 0.0
    if shared is None or not len(shared.faces):
        return 0.0
    extent = shared.bounds[1] - shared.bounds[0]
    if float(np.min(extent)) <= EPS_GEOM:
        return 0.0
    return abs(float(shared.volume))


def _plausible(mesh: MeshData, allow_empty: bool = False) -> bool:
    """Ein Ergebnis muss Volumen haben; ein leerer oder umgestülpter Körper ist
    keine Antwort.

    Außer der Aufrufer sagt es anders — siehe ``allow_empty`` in
    :func:`boolean`.
    """
    if allow_empty and mesh.triangle_count == 0:
        return True
    return mesh.triangle_count > 0 and abs(mesh.volume) > EPS_GEOM


def _findings_for(stage: SolverStage) -> list[Finding]:
    if stage == "direct":
        return []
    if stage == "welded":
        return [
            Finding(
                code="boolean.welded",
                severity="info",
                message=_("Die Operation gelang erst nach dem Verschweißen."),
            )
        ]
    if stage == "jittered":
        return [
            Finding(
                code="boolean.jittered",
                severity="warning",
                message=_(
                    "Die Eingangsgeometrie wurde minimal gestört, um die Operation zu lösen."
                ),
            )
        ]
    return [
        Finding(
            code="boolean.voxel",
            severity="warning",
            message=_("Über die Voxelstufe gelöst — die Maße sind gerundet."),
        )
    ]


def without_effect(before: MeshData, after: MeshData, kind: BooleanKind) -> Finding | None:
    """Hat die Operation am Körper überhaupt etwas geändert? (Regel 17, §2.7)

    Eine Magnettasche, die neben dem Körper liegt, schnitt nichts und sagte
    nichts: keine Ausnahme, kein Befund, kein Hinweis in der Statusleiste. Im
    Verlauf stand ein Schritt, im Viewport lag dasselbe Teil wie vorher, und
    der Nutzer sucht den Fehler in der Geometrie statt in der Position. Das
    steht unterhalb dessen, was Regel 17 überhaupt erfasst — dort geht es um
    Ausnahmen, und hier gab es keine.

    Gemessen am Volumen und nicht an den Dreiecken: eine Differenz, die eine
    Fläche nur streift, ändert die Vernetzung, ohne etwas abzutragen, und wäre
    sonst eine Meldung wert, die niemanden weiterbringt.

    Ein Befund und kein Fehler: die Operation ist gelaufen, sie hat nur nichts
    bewirkt — und was daran falsch war, weiß der Nutzer besser als der Kern.
    """
    change = abs(after.volume - before.volume)
    if change > EPS_GEOM:
        return None
    return Finding(
        code="boolean.without_effect",
        severity="warning",
        message=(
            _(
                "Der Schnitt hat nichts abgetragen — das Werkzeug liegt neben dem Körper. "
                "Position prüfen oder an einer Fläche ausrichten."
            )
            if kind == "difference"
            else _(
                "Die Vereinigung hat nichts hinzugefügt — der Körper steckt schon ganz im "
                "anderen. Position prüfen."
            )
        ),
        values={"volume_mm3": round(before.volume, 3)},
    )
