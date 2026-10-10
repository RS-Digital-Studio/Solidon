"""Verschieben, Drehen und Skalieren (Bauplan §25, §18.11).

Jede Manipulation ist eine Operation — auch die, die als Ziehen im Viewport
begann (§18.11). Also sitzt die Rechnung hier, und der Gizmo entscheidet nur,
welche Zahlen er übergibt; das Undo nimmt ein Ziehen danach genauso zurück wie
einen Menüeintrag.

Das Einrasten gehört zur Interaktion, nicht zur Geometrie: die Oberfläche rundet
den Wert, die Operation speichert, was wirklich angewandt wurde.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal, cast

import numpy as np

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.types import CancelToken, Mesh, SceneObject, Transform, Vec3
from app.core.units import EPS_DISPLAY, EPS_GEOM, dot3, exact_cos_degrees, exact_sin_degrees

Axis = Literal["x", "y", "z"]
Anchor = Literal["centre", "origin", "bed"]
"""Worum eine Drehung oder Skalierung dreht: die Mitte des Körpers, der
Weltursprung, oder der Punkt, an dem der Körper auf der Platte aufsitzt."""

AXIS_VECTORS: dict[Axis, Vec3] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


def anchor_point(mesh: Mesh, anchor: Anchor) -> Vec3:
    """Der Fixpunkt einer Transformation."""
    bounds = mesh.bounds
    if anchor == "origin":
        return (0.0, 0.0, 0.0)
    if anchor == "bed":
        centre = bounds.centre
        return (centre[0], centre[1], bounds.minimum[2])
    return bounds.centre


def pattern_centre_param(
    axis: Axis, depends_on: tuple[str, tuple[str | bool, ...]] | None = None
) -> Any:
    """Eine Koordinate des einmal aufgelösten Dreh- oder Spiegelpunkts."""
    from app.core.registry import param
    from app.core.registry.params import ZERO_BODY_CENTRE
    from app.core.units import FEATURE_REACH
    from app.i18n import _

    titles = {"x": _("Punkt X"), "y": _("Punkt Y"), "z": _("Punkt Z")}
    return param(
        title=titles[axis],
        default=None,
        optional=True,
        unit="mm",
        minimum=-FEATURE_REACH,
        maximum=FEATURE_REACH,
        placement="advanced",
        depends_on=depends_on,
        doc=_("Dreh- oder Spiegelpunkt. Drei leere Koordinaten übernehmen einmal die Körpermitte."),
        zero_text=ZERO_BODY_CENTRE,
    )


def pattern_centre(
    source: SceneObject,
    cx: float | None,
    cy: float | None,
    cz: float | None,
    *,
    anchor: Anchor = "centre",
    follow_anchor: bool = False,
) -> tuple[Vec3, dict[str, float]]:
    """Expliziter Punkt oder einmalige Körpermitte; Altspiegel folgen ihrem Anker."""
    from app.core.errors import CANCEL, CORRECT_INPUT, ValidationError
    from app.i18n import _

    values = (cx, cy, cz)
    if all(value is None for value in values):
        point = anchor_point(source.mesh, anchor)
        return point, {} if follow_anchor else dict(zip(("cx", "cy", "cz"), point, strict=True))
    if any(value is None for value in values):
        raise ValidationError(
            field="cx",
            detail=_(
                "Bitte alle drei Koordinaten des Dreh- oder Spiegelpunkts angeben oder alle leeren."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return cast(Vec3, values), {}


def translation(offset: Vec3) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = np.asarray(offset, dtype=float)
    return matrix


def reference_point(
    objects: Sequence[SceneObject], reference: str = "bed", feature: str = ""
) -> Vec3:
    """Bezug der ganzen Auswahl: Hüllquader, Ecke oder benanntes Merkmal."""
    from app.core.errors import ValidationError
    from app.core.perceive.features import centre_of
    from app.i18n import _

    if not objects:
        raise ValidationError(detail=_("Bitte zuerst einen Körper auswählen."))
    if reference == "feature":
        found = objects[0].features.get(feature)
        centre = centre_of(found) if found is not None else None
        if centre is None:
            raise ValidationError(
                field="reference_feature",
                detail=_("Bitte ein Merkmal mit einem Mittelpunkt wählen."),
            )
        return cast(Vec3, tuple(float(value) for value in centre))
    low = tuple(min(body.mesh.bounds.minimum[axis] for body in objects) for axis in range(3))
    high = tuple(max(body.mesh.bounds.maximum[axis] for body in objects) for axis in range(3))
    centre = tuple((low[axis] + high[axis]) / 2.0 for axis in range(3))
    if reference == "bed":
        return (centre[0], centre[1], low[2])
    if reference.startswith("corner_"):
        bits = reference.removeprefix("corner_")
        if len(bits) == 3 and set(bits) <= {"0", "1"}:
            return cast(
                Vec3,
                tuple(high[axis] if bit == "1" else low[axis] for axis, bit in enumerate(bits)),
            )
    return cast(Vec3, centre)


def orientation_matrix(source: SceneObject) -> np.ndarray:
    """Belegte Körperachsen, ohne positive Skalierung; Spiegelung wird benannt."""
    from app.core.errors import ValidationError
    from app.i18n import _

    if source.frame is not None:
        axes = np.asarray(source.frame, dtype=float)[:3, :3]
        lengths = np.linalg.norm(axes, axis=0)
        if np.all(lengths > EPS_GEOM):
            axes = axes / lengths
            right_handed = dot3(axes[:, 0], np.cross(axes[:, 1], axes[:, 2])) > 0
            orthogonal = all(
                abs(dot3(axes[:, first], axes[:, second])) <= EPS_GEOM
                for first, second in ((0, 1), (0, 2), (1, 2))
            )
            if right_handed and orthogonal:
                return cast(np.ndarray, axes)
    raise ValidationError(
        field="mode",
        detail=_(
            "Dieser Körper hat keine eindeutigen rechtwinkligen Ausgangsachsen. "
            "Wählen Sie „um“, um ihn relativ zu drehen."
        ),
    )


def orientation_angles(source: SceneObject) -> Vec3:
    """Winkel X, dann Y, dann Z um feste Weltachsen zur Ausgangslage.

    An der Polstelle ist Z null; X trägt die gemeinsame Drehung. Die
    kanonische Darstellung bleibt eindeutig, auch wenn mehrere Winkeltripel
    dieselbe Lage beschreiben.
    """
    matrix = np.eye(4)
    matrix[:3, :3] = orientation_matrix(source)
    angles = trimesh.transformations.euler_from_matrix(matrix, axes="sxyz")
    return cast(Vec3, tuple(math.degrees(float(value)) for value in angles))


def absolute_rotation(source: SceneObject, angles: Vec3, pivot: Vec3) -> np.ndarray:
    """Dreht den belegten Rahmen auf gespeicherte Zielwinkel, um denselben Punkt."""
    current = orientation_matrix(source)
    target = composed(rotation("z", angles[2]), rotation("y", angles[1]), rotation("x", angles[0]))
    inverse = np.eye(4)
    inverse[:3, :3] = current.T
    return composed(
        translation(pivot),
        target,
        inverse,
        translation(cast(Vec3, tuple(-value for value in pivot))),
    )


def angles_after_turn(source: SceneObject, axis: Axis, angle: float) -> Vec3:
    """Zielwinkel eines Griffzugs; der gespeicherte Auftrag bleibt absolut."""
    current = np.eye(4)
    current[:3, :3] = orientation_matrix(source)
    matrix = composed(rotation(axis, angle), current)
    return orientation_angles(replace(source, frame=cast(Transform, tuple(map(tuple, matrix)))))


def rotation(axis: Axis, degrees: float, about: Vec3 = (0.0, 0.0, 0.0)) -> np.ndarray:
    return rotation_about(AXIS_VECTORS[axis], about, degrees)


def scaling(factors: Vec3, about: Vec3 = (0.0, 0.0, 0.0)) -> np.ndarray:
    """Gleichmäßige oder achsweise Skalierung um einen Fixpunkt."""
    values = np.asarray(factors, dtype=float)
    if np.any(np.abs(values) <= EPS_GEOM):
        raise ValueError("a scale factor of zero would collapse the body")
    matrix = np.eye(4)
    matrix[0, 0], matrix[1, 1], matrix[2, 2] = values
    pivot = np.asarray(about, dtype=float)
    matrix[:3, 3] = pivot - values * pivot
    return matrix


def moved_points(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Punkte durch eine 4x4-Matrix bewegen — auf jeder Maschine dieselben Bits.

    **Nicht ``points @ matrix[:3, :3].T``** (RM-187): Eine Matrixmultiplikation
    geht durch BLAS, und das blockt, vektorisiert und verwendet FMA, je nachdem
    was die CPU kann. Gemessen über 5000 Punkte betrug der Unterschied zur
    elementweisen Rechnung 1,4·10⁻¹⁴ mm — nichts für sich, und alles, sobald
    eine Boolesche Operation darauf entscheidet, ob zwei Flächen koplanar sind.

    Elementweise ist jede Multiplikation und jede Addition eine eigene
    NumPy-Operation, die ihr Ergebnis nach IEEE-754 korrekt gerundet in ein
    Feld schreibt. Über eine solche Grenze hinweg kann kein Compiler
    zusammenziehen, und damit hängt nichts mehr an der Maschine.

    Der Preis ist gemessen und klein: 0,037 statt 0,027 Millisekunden für
    5000 Punkte.
    """
    cells = np.asarray(matrix, dtype=np.float64)
    raw = np.asarray(points, dtype=np.float64)
    turn = cells[:3, :3]
    x, y, z = raw[:, 0], raw[:, 1], raw[:, 2]
    return np.stack(
        (
            turn[0, 0] * x + turn[0, 1] * y + turn[0, 2] * z + cells[0, 3],
            turn[1, 0] * x + turn[1, 1] * y + turn[1, 2] * z + cells[1, 3],
            turn[2, 0] * x + turn[2, 1] * y + turn[2, 2] * z + cells[2, 3],
        ),
        axis=1,
    )


def turned(vectors: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Richtungen durch den linearen Teil einer Matrix drehen — ohne Verschiebung.

    Dasselbe wie :func:`moved_points` für Normalen und Achsen: elementweise
    statt ``vectors @ matrix[:3, :3].T``, damit keine BLAS-Rundung der
    Maschine hineinkommt (RM-187).
    """
    cells = np.asarray(matrix, dtype=np.float64)
    raw = np.asarray(vectors, dtype=np.float64)
    turn = cells[:3, :3]
    x, y, z = raw[..., 0], raw[..., 1], raw[..., 2]
    return np.stack(
        (
            turn[0, 0] * x + turn[0, 1] * y + turn[0, 2] * z,
            turn[1, 0] * x + turn[1, 1] * y + turn[1, 2] * z,
            turn[2, 0] * x + turn[2, 1] * y + turn[2, 2] * z,
        ),
        axis=-1,
    )


def along(points: np.ndarray, axis: Sequence[float] | np.ndarray) -> np.ndarray:
    """Die Lage jedes Punkts entlang einer Richtung — ``points @ axis`` ohne BLAS.

    Drei Produkte und zwei Summen je Punkt, jede als eigene NumPy-Operation
    und damit nach IEEE-754 gerundet: auf jeder Maschine dieselben Bits
    (RM-187). ``axis`` wird nicht normiert.
    """
    raw = np.asarray(points, dtype=np.float64)
    a = (float(axis[0]), float(axis[1]), float(axis[2]))
    return np.asarray(raw[..., 0] * a[0] + raw[..., 1] * a[1] + raw[..., 2] * a[2])


def composed(*matrices: np.ndarray) -> np.ndarray:
    """Das Produkt 4x4-Matrizen, von links nach rechts — ohne BLAS.

    ``composed(a, b)`` ist ``a @ b``: erst ``b``, dann ``a`` auf einen Punkt
    angewandt. Jeder Eintrag entsteht als Summe von vier Produkten in fester
    Reihenfolge, in Pythons ``float``. ``@`` ginge durch BLAS, und dessen
    Blockung und FMA-Nutzung hängen an der CPU — die gemeldete Bewegung einer
    Operation, mit der die Auswertung Merkmale nachführt, und jede Matrix,
    die danach ein Netz bewegt, gehören auf jeder Maschine zu denselben Bits
    (RM-187).
    """
    if not matrices:
        return np.eye(4, dtype=np.float64)
    result = [[float(value) for value in row] for row in np.asarray(matrices[-1], dtype=float)]
    for matrix in reversed(matrices[:-1]):
        left = [[float(value) for value in row] for row in np.asarray(matrix, dtype=float)]
        result = [
            [
                left[row][0] * result[0][column]
                + left[row][1] * result[1][column]
                + left[row][2] * result[2][column]
                + left[row][3] * result[3][column]
                for column in range(4)
            ]
            for row in range(4)
        ]
    return np.asarray(result, dtype=np.float64)


def inverse_affine(matrix: np.ndarray) -> np.ndarray | None:
    """Eine endliche affine Matrix ohne LAPACK umkehren; singulär ergibt ``None``.

    Die Kofaktoren rechnen in fester Folge. Die Singularitätsgrenze gilt den
    Richtungen, nicht dem gemeinsamen Maßstab eines kleinen Körpers.
    """
    cells = np.asarray(matrix, dtype=np.float64)
    if cells.shape != (4, 4) or not np.isfinite(cells).all():
        return None
    if not np.allclose(cells[3], (0.0, 0.0, 0.0, 1.0), atol=EPS_GEOM, rtol=0.0):
        return None
    rows = cells[:3, :3]
    lengths = np.linalg.norm(rows, axis=1)
    if np.any(lengths <= 0.0):
        return None
    unit = rows / lengths[:, None]
    cofactors = np.asarray(
        (np.cross(unit[1], unit[2]), np.cross(unit[2], unit[0]), np.cross(unit[0], unit[1]))
    )
    determinant = dot3(unit[0], cofactors[0])
    if abs(determinant) <= EPS_GEOM:
        return None
    result = np.eye(4)
    result[:3, :3] = cofactors.T / determinant / lengths[None, :]
    result[:3, 3] = -turned(cells[:3, 3], result)
    return result if np.isfinite(result).all() else None


def moved(body: object, matrix: np.ndarray) -> None:
    """Ein Netz an Ort und Stelle bewegen — der Ersatz für ``apply_transform``.

    Die Ecken kommen aus :func:`moved_points`; die Normalen lässt ``trimesh``
    neu rechnen, wie es das nach einer Zuweisung an ``vertices`` ohnehin tut.
    Eine Spiegelung dreht zusätzlich den Umlaufsinn um — dieselbe Regel, die
    ``apply_transform`` anwendet, und ohne sie zeigte ein gespiegelter Körper
    nach innen.
    """
    cells = np.asarray(matrix, dtype=np.float64)
    body.vertices = moved_points(np.asarray(body.vertices, dtype=np.float64), cells)  # type: ignore[attr-defined]
    if float(np.linalg.det(cells[:3, :3])) < 0.0:
        body.faces = np.fliplr(np.asarray(body.faces))  # type: ignore[attr-defined]


#: Was ``trimesh`` an einem Netz gemerkt hat und was eine Bewegung nicht
#: ändert — dieselbe Liste, die ``Trimesh.apply_transform`` behält, dazu
#: Solidons eigene Einträge derselben Art: die Teilezahl und die Nachbarschaft
#: der Flecken (``scene.placement``), beide nach Ort gruppiert, und der Ort
#: bewegt sich mit.
_TOPOLOGY_IN_CACHE: tuple[str, ...] = (
    "face_adjacency",
    "face_adjacency_edges",
    "face_adjacency_unshared",
    "edges",
    "edges_face",
    "edges_sorted",
    "edges_unique",
    "edges_unique_idx",
    "edges_unique_inverse",
    "edges_sparse",
    "body_count",
    "faces_unique_edges",
    "euler_number",
    "solidon_component_count",
    "solidon_patch_adjacency",
)

#: Was zusätzlich eine **starre** Bewegung überlebt: Winkel, Radien und
#: Flächen zwischen Nachbardreiecken, die Facetten, die Flächeninhalte — und
#: die Randringe der Merkmalsketten (``perceive.relations``), deren Schlüssel
#: seit dem 22.09.2026 keine Lage mehr nennt.
_METRIC_IN_CACHE: tuple[str, ...] = (
    "face_adjacency_angles",
    "face_adjacency_convex",
    "face_adjacency_projections",
    "face_adjacency_radius",
    "face_adjacency_span",
    "facets",
    "facets_area",
    "facets_boundary",
    "area_faces",
    "area",
    "solidon_cavity_links",
)


def _carry_cache(source: trimesh.Trimesh, body: trimesh.Trimesh, matrix: np.ndarray) -> None:
    """Was das Quellnetz über sich wusste und die Bewegung nicht ändert, weiß
    die bewegte Kopie sofort.

    ``copy()`` gibt ein Netz mit leerem Gedächtnis, und die Auswertung fragte
    danach alles neu: Nachbarschaften, Facetten, Teilezahl, Randringe — an der
    unterteilten Lochplatte 107 ms Teilezahl, 102 ms Facetten, 188 ms Ringe je
    Verschieben, für Antworten, die am Quellnetz schon dastanden (gemessen am
    22.09.2026). ``Trimesh.apply_transform`` behält seine Topologie genauso;
    hier kommt hinzu, was eine starre Bewegung obendrein erhält.

    **Eine Spiegelung dreht den Umlaufsinn**, und damit die Richtung jeder
    Kante — die Kantentabellen des Quellnetzes stimmen dann nicht mehr. Bei
    negativer Determinante wird nichts übertragen; gespiegelt wird selten, und
    ein falscher Eintrag wäre teurer als jede Ersparnis. Die Normalen werden
    wie bei ``trimesh`` mitgedreht, nicht neu gerechnet.
    """
    cells = np.asarray(matrix, dtype=np.float64)
    if float(np.linalg.det(cells[:3, :3])) < 0.0:
        return
    kept = getattr(source, "_cache", None)
    target = getattr(body, "_cache", None)
    if kept is None or target is None:
        return
    kept.verify()
    names = list(_TOPOLOGY_IN_CACHE)
    rigid = is_rigid(cells)
    if rigid:
        names.extend(_METRIC_IN_CACHE)
    carried = {name: kept.cache[name] for name in names if name in kept.cache}
    if rigid:
        # Elementweise gedreht (:func:`turned`), nicht über ``@``: Aus den
        # Normalen entscheidet die Erkennung danach über Ebenen und Kanten,
        # und dieselbe Frage soll auf jeder Maschine dieselbe Antwort haben.
        for name in ("face_normals", "vertex_normals"):
            if name in kept.cache:
                carried[name] = turned(np.asarray(kept.cache[name], dtype=np.float64), cells)
        # **Die Facettennormalen drehen mit, ihre Aufpunkte wandern mit**:
        # ``trimesh`` legt beide in einem Zug ab (``facets_origin`` liest nur
        # den Cache). Unverändert übernommen zeigten die Normalen nach einer
        # Drehung in die alte Richtung, und ``facets_origin`` gab ``None``.
        # Zeilenweise gerechnet sind es dieselben Bits wie frisch am bewegten
        # Netz: die Normale des größten Dreiecks, die erste Ecke darin.
        if "facets_normal" in kept.cache and "facets_origin" in kept.cache:
            normals = np.asarray(kept.cache["facets_normal"], dtype=np.float64).reshape(-1, 3)
            origins = np.asarray(kept.cache["facets_origin"], dtype=np.float64).reshape(-1, 3)
            carried["facets_normal"] = turned(normals, cells)
            carried["facets_origin"] = moved_points(origins, cells)
    if not carried:
        return
    target.verify()
    target.cache.update(carried)
    # Den Stempel auf den bewegten Stand setzen, sonst wirft die nächste
    # Prüfung alles weg, was eben übernommen wurde.
    target.id_set()


def _copy_to_move(raw: trimesh.Trimesh) -> trimesh.Trimesh:
    """``Trimesh.copy()`` für :func:`moved` — Ecken und Dreiecke geteilt statt kopiert.

    :func:`moved` setzt die Ecken neu und bei einer Spiegelung auch die
    Dreiecke; geschrieben wird in keines der beiden Felder. Die tiefe Kopie
    von ``copy()`` hielt deshalb nur eine zweite Dreiecksliste: 24 Byte je
    Dreieck und Bewegung, am Spiderman 21 MB je Verschieben, bei einem Muster
    je Kopie. Ein Netz gilt als unveränderlich (``geom.mesh``); wer an seinen
    Feldern etwas ändert, kopiert vorher (``repair.wind_consistently``,
    ``turn_shells_outward``). Schreibgeschützt ist die geteilte Liste nicht:
    ``fast_simplification`` (*Dreiecke verringern*) nimmt nur beschreibbare
    Felder an, auch wenn es nicht hineinschreibt (Review 1 zu RM-698). Farben,
    Attribute und Metadaten werden kopiert wie bei ``copy()``.
    """
    from copy import deepcopy

    copied = trimesh.Trimesh()
    copied._data.data = dict(raw._data.data)
    if raw.visual is not None:
        copied.visual = raw.visual.copy()
    copied.vertex_attributes.update({k: deepcopy(v) for k, v in raw.vertex_attributes.items()})
    copied.face_attributes.update({k: deepcopy(v) for k, v in raw.face_attributes.items()})
    copied.metadata = deepcopy(raw.metadata)
    copied._cache.verify()
    return copied


def apply(mesh: MeshData, matrix: np.ndarray) -> MeshData:
    """Gibt eine transformierte Kopie zurück. Die Eingabe wird nie
    angefasst (AGENTS.md Regel 3).

    Bewegt wird über :func:`moved` und nicht über ``apply_transform``, damit
    dieselbe Bewegung auf jeder Maschine dieselben Zahlen gibt (RM-187). Was
    das Quellnetz über seine Topologie wusste, nimmt die Kopie mit
    (:func:`_carry_cache`).

    **Und eine starre Bewegung vermerkt, woher das Netz kommt**
    (``perceive.features.note_movement``): Die Auswertung überträgt damit die
    erkannten Merkmale des Eingangs, statt sie am bewegten Netz neu zu suchen —
    auch dort, wo die Operation mehrere Körper je mit eigener Matrix bewegt und
    deshalb keine meldet. Eine Spiegelung dreht den Umlaufsinn und bekommt
    keinen Vermerk; ihr Gewinde wechselt die Hand.
    """
    from app.core.perceive.features import note_movement

    body = _copy_to_move(mesh.raw)
    moved(body, matrix)
    _carry_cache(mesh.raw, body, matrix)
    result = replace(
        mesh.replacing(body),
        cavity=apply(mesh.cavity, matrix) if mesh.cavity is not None else None,
        cavity_open=mesh.cavity_open,
    )
    cells = np.asarray(matrix, dtype=np.float64)
    if is_rigid(cells) and float(np.linalg.det(cells[:3, :3])) > 0.0:
        note_movement(mesh, result, cells)
    return result


def is_rigid(matrix: np.ndarray) -> bool:
    """Ob die Matrix eine starre Bewegung ist — Drehung, Spiegelung, Verschiebung.

    Solche Matrizen bewahren auch Längen und Winkel. Eine achsweise Skalierung
    kann ebenfalls exakt rechnen, verändert aber die Form der Merkmale.
    Geprüft wird die obere 3x3 auf Orthonormalität; die Spiegelung
    (Determinante -1) gehört dazu, ``mirror_object`` ist eine.
    """
    cells = np.asarray(matrix, dtype=float)
    if cells.shape != (4, 4) or not np.all(np.isfinite(cells)):
        return False
    if not np.allclose(cells[3], (0.0, 0.0, 0.0, 1.0), atol=EPS_GEOM, rtol=0.0):
        return False
    linear = cells[:3, :3]
    product = linear @ linear.T
    return bool(np.allclose(product, np.eye(3), atol=EPS_GEOM, rtol=0.0))


def moved_body(mesh: Mesh, matrix: np.ndarray, *, cancelled: CancelToken | None = None) -> Mesh:
    """Bewegt einen Körper und behält dabei seine Darstellung.

    **Der Unterschied zu :func:`apply` ist der Rückweg.** ``apply`` arbeitet
    auf Dreiecken, und wer ihm einen exakten Körper gibt, bekommt Dreiecke
    zurück — eine Einbahnstraße (§30). Für eine Bewegung ist das unnötig:
    Verschieben, Drehen, Spiegeln und Aufs-Bett-Setzen ändern die Form nicht,
    und der B-Rep-Kern führt sie exakt aus.

    Gemessen am 06.09.2026: Ein Filamenthalter aus einer Skizze — exakter
    Körper — war nach „Auf dem Bett anordnen“ ein Netz, und *Verrunden* stand
    danach ausgegraut im Menü mit dem Hinweis, man möge die Schritte
    zurücknehmen. Die Bewegung war der ganze Grund.

    Der native Kern verarbeitet auch Skalierungen und allgemeine affine
    Matrizen. Nur ein bereits vernetzter Körper wird über Dreiecke bewegt.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if isinstance(mesh, MeshData):
        return apply(mesh, matrix)
    from app.core.brep import edit
    from app.core.brep.kernel import Solid

    if isinstance(mesh, Solid):
        rows = np.asarray(matrix, dtype=float)
        cells = cast(Transform, tuple(tuple(float(value) for value in row) for row in rows))
        return edit.transformed(mesh, cells, cancelled=cancelled)
    return apply(as_mesh_data(mesh), matrix)


#: Eine Fläche ohne Dreiecke — der Vorgabewert der Umkehrabbildung.
_NO_TRIANGLES: np.ndarray = np.empty(0, dtype=np.int64)


def _triangles_by_face(solid: Any) -> dict[int, np.ndarray]:
    """Fläche → Dreiecke der Tessellation, einmal je exaktem Körper.

    ``Solid.triangles_of_face`` sucht je Aufruf über alle Dreiecke; beim
    Bewegen einer Platte mit 31 Merkmalen waren das 124 Suchläufe über 4312
    Dreiecke für alten und neuen Körper, 63 von 130 ms (Review, 21.09.2026).
    Die Umkehrabbildung entsteht hier einmal aus derselben Zuordnung, die der
    Kern je Dreieck führt, und liegt im Cache des Körpers — der mit dessen
    Tessellation neu entsteht.
    """
    from app.core.brep.kernel import _FACE_ATTRIBUTE

    cached = solid._cache.get("triangles_by_face")
    if cached is not None:
        return cast(dict[int, np.ndarray], cached)
    source = np.asarray(solid.raw.face_attributes.get(_FACE_ATTRIBUTE, ()), dtype=np.int64)
    table: dict[int, np.ndarray] = {}
    if len(source) == solid.triangle_count and len(source):
        order = np.argsort(source, kind="stable")
        faces, starts = np.unique(source[order], return_index=True)
        ends = np.append(starts[1:], len(order))
        table = {
            int(face): order[start:end]
            for face, start, end in zip(faces.tolist(), starts.tolist(), ends.tolist(), strict=True)
        }
    solid._cache["triangles_by_face"] = table
    return table


def moved_object(
    source: SceneObject, matrix: np.ndarray, *, cancelled: CancelToken | None = None
) -> SceneObject:
    """Bewegt Körper und Merkmale gemeinsam in den Ergebnisraum.

    Beim exakten Körper verbindet die Builder-Zuordnung die ursprünglichen
    Topologieflächen mit den neuen Dreiecken. Eine Teilmenge einer Fläche
    wird dabei nicht heimlich zur gesamten Fläche erweitert: Sie folgt Dreieck
    für Dreieck, wo die Bewegung die Vernetzung behält, und ein erkanntes
    Merkmal, das das nicht kann, fällt der Erkennung des Ergebnisses zu.
    """
    from app.core.brep import edit
    from app.core.brep.kernel import Solid
    from app.core.errors import CANCEL, CORRECT_INPUT, GeometryError
    from app.core.perceive.matching import transformed_features
    from app.core.perceive.surfaces import valid_patch
    from app.i18n import _

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    cells = cast(Transform, tuple(tuple(float(value) for value in row) for row in matrix))
    features = dict(source.features)
    check_cancelled = cancelled.raise_if_cancelled if cancelled is not None else None
    body: Mesh
    if isinstance(source.mesh, Solid):
        solid, face_map = edit.transformed_with_faces(source.mesh, cells, cancelled=cancelled)
        if solid is source.mesh:
            return source
        body = solid
        before = _triangles_by_face(source.mesh)
        after = _triangles_by_face(solid)

        def triangles_of(table: dict[int, np.ndarray], faces: Sequence[int]) -> set[int]:
            return {
                int(index)
                for face in faces
                for index in table.get(int(face), _NO_TRIANGLES).tolist()
            }

        images: dict[int, dict[int, int] | None] = {}

        def image_of(face: int) -> dict[int, int] | None:
            """Dreieck → Dreieck einer Fläche, wo die Bewegung ihre Vernetzung behielt.

            Eine starre Bewegung legt dieselbe Vernetzung nur anders
            (gemessen an ``gegen_naht.step``: alle 23 Flächen, Abweichung 0).
            Belegt wird das Dreieck für Dreieck an den bewegten Ecken, nicht
            angenommen; Maßstab und allgemeine Abbildung vernetzen neu.
            """
            if face not in images:
                old = before.get(face, _NO_TRIANGLES)
                new = after.get(face_map[face], _NO_TRIANGLES)
                images[face] = None
                if len(old) == len(new):
                    old_mesh, new_mesh = as_mesh_data(source.mesh).raw, as_mesh_data(solid).raw
                    rows = np.asarray(matrix, dtype=np.float64)
                    moved = old_mesh.vertices[old_mesh.faces[old]] @ rows[:3, :3].T + rows[:3, 3]
                    placed = new_mesh.vertices[new_mesh.faces[new]]
                    if np.abs(moved - placed).max(initial=0.0) <= EPS_GEOM:
                        images[face] = dict(zip(old.tolist(), new.tolist(), strict=True))
            return images[face]

        def image_of_part(triangles: set[int], faces: Sequence[int]) -> set[int] | None:
            pairs: dict[int, int] = {}
            for face in faces:
                image = image_of(int(face))
                if image is None:
                    return None
                pairs.update(image)
            return {pairs[index] for index in triangles}

        unfollowed: list[str] = []
        for name, feature in features.items():
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            if not feature.face_indices:
                continue
            selected = set(feature.face_indices)
            native_faces = source.mesh.faces_of_triangles(feature.face_indices)
            complete = triangles_of(before, native_faces)
            followed = (
                triangles_of(after, [face_map[face] for face in native_faces])
                if selected == complete
                else image_of_part(selected, native_faces)
            )
            if followed is None:
                if feature.recognised:
                    # Die Erkennung des Ergebnisses findet es wieder oder
                    # meldet seinen Verlust (RM-407, ``curve_1`` deckt 3 647
                    # von 3 649 Dreiecken seiner Flächen).
                    unfollowed.append(name)
                    continue
                raise GeometryError(
                    _("Diese Teilauswahl lässt sich beim Verformen nicht eindeutig nachführen."),
                    detail=_(
                        "Wählen Sie vollständige Flächen aus und wiederholen Sie die Änderung."
                    ),
                    suggestions=(CORRECT_INPUT, CANCEL),
                )
            patches = []
            for patch in feature.surface_patches:
                if not valid_patch(
                    patch, allowed_indices=selected, check_cancelled=check_cancelled
                ):
                    continue
                patch_faces = source.mesh.faces_of_triangles(patch.face_indices)
                patch_triangles = set(patch.face_indices)
                patch_followed = (
                    triangles_of(after, [face_map[face] for face in patch_faces])
                    if triangles_of(before, patch_faces) == patch_triangles
                    else image_of_part(patch_triangles, patch_faces)
                )
                if patch_followed is None:
                    # Die neue Tessellierung besitzt keine belegte Abbildung
                    # eines willkürlichen Ausschnitts einer nativen Fläche.
                    continue
                patches.append(replace(patch, face_indices=tuple(sorted(patch_followed))))
            features[name] = replace(
                feature, surface_patches=tuple(patches), face_indices=tuple(sorted(followed))
            )
        for name in unfollowed:
            del features[name]
    else:
        body = moved_body(source.mesh, matrix, cancelled=cancelled)
    mapped = transformed_features(
        features, cells, mesh=as_mesh_data(body), check_cancelled=check_cancelled
    )
    return replace(
        source,
        mesh=body,
        frame=None
        if source.frame is None
        else cast(
            Transform,
            tuple(
                tuple(float(value) for value in row)
                for row in matrix @ np.asarray(source.frame, dtype=float)
            ),
        ),
        features={
            name: feature for name, feature in mapped.candidates.items() if name in mapped.exact
        },
    )


def place_on_bed(mesh: MeshData) -> MeshData:
    """Setzt den Körper auf Z = 0, ohne ihn seitlich zu verschieben
    (§17.1 Schritt 6)."""
    return apply(mesh, translation((0.0, 0.0, -mesh.bounds.minimum[2])))


@dataclass(frozen=True, slots=True)
class TransformSteps:
    """Ein Gizmo-Ziehen, zerlegt in Dinge, die eine Operation ausdrücken
    kann (§18.11).

    Eine gezogene Matrix ist danach nicht mehr änderbar; ``verschieben 12 mm``
    schon. Also wird die Matrix einmal zerlegt, hier, und was den Stapel
    erreicht, sind Operationen, deren Zahlen sich weiter ändern lassen (§2.1).
    """

    offset: Vec3 = (0.0, 0.0, 0.0)
    axis: Axis | None = None
    angle: float = 0.0
    scale: float = 1.0

    @property
    def moves(self) -> bool:
        return any(abs(value) > EPS_DISPLAY for value in self.offset)

    @property
    def turns(self) -> bool:
        return self.axis is not None and abs(self.angle) > EPS_DISPLAY

    @property
    def resizes(self) -> bool:
        return abs(self.scale - 1.0) > 1e-4


def decompose_transform(matrix: np.ndarray) -> TransformSteps:
    """Zerlegt eine Transformation in Versatz, Drehung um eine Hauptachse
    und Skalierung.

    Der Gizmo dreht um seine eigenen Achsen, eine Drehung landet also auf x, y
    oder z; ein kombiniertes Ziehen ergibt schlicht mehrere Schritte, die dann
    als eine Transaktion reisen (§15.5).
    """
    scales, _shear, angles, offset, _perspective = trimesh.transformations.decompose_matrix(
        np.asarray(matrix, dtype=float)
    )
    from scipy.spatial.transform import Rotation

    # Eulerwinkel wechseln jenseits von ±90° ihre Darstellung. Der
    # Rotationsvektor bewahrt dagegen die tatsächlich gezogene Hauptachse.
    degrees = np.degrees(Rotation.from_euler("xyz", angles).as_rotvec())
    largest = max(range(3), key=lambda index: abs(degrees[index]))
    axis: Axis | None = ("x", "y", "z")[largest]
    angle = degrees[largest]
    if abs(angle) <= EPS_DISPLAY:
        axis, angle = None, 0.0

    scale = float(np.mean(scales))
    return TransformSteps(
        offset=(float(offset[0]), float(offset[1]), float(offset[2])),
        axis=axis,
        angle=angle,
        scale=scale,
    )


def snap_to_step(value: float, step: float) -> float:
    """Raster- und Winkeleinrasten. Schrittweite null heißt: kein
    Einrasten (§18.11)."""
    if step <= EPS_GEOM:
        return value
    return round(value / step) * step


def snap_to_marks(value: float, marks: Sequence[float], zone: float) -> float:
    """Rastet in der Nähe **benannter Stellen** ein — Mitte, Kante, Boden.

    Das Geschwister von :func:`snap_near`, und der Unterschied ist der Anlass:
    Jenes rastet auf einem gleichmäßigen Raster ein (alle 45 Grad), dieses auf
    einer Handvoll Stellen, die etwas **bedeuten** — die halbe Wandstärke, die
    Rückseite, der Grund einer Tasche. Robert, 09.09.2026: „schön wäre auch
    wenn wir auch bei anderen operationen die sowas machen bei mitten und
    außenkanten immer so leicht einrasten, wenn wir in der nähe sind."

    Dieselbe Zusage wie dort: **freie Fahrt, kurzes Einrasten.** Innerhalb der
    Zone gilt die Marke, außerhalb der rohe Wert, und wer weiterzieht, kommt
    heraus. Ohne Marken oder ohne Zone bleibt der Wert, wie er ist.

    Liegen zwei Marken so dicht, dass beide in Reichweite sind, gewinnt die
    nähere; bei genau gleichem Abstand die kleinere, damit dieselbe Eingabe
    immer dasselbe ergibt (§15.1).
    """
    if zone <= EPS_GEOM:
        return value
    reachable = [mark for mark in marks if abs(value - mark) <= zone]
    if not reachable:
        return value
    return min(reachable, key=lambda mark: (abs(value - mark), mark))


def snap_near(value: float, step: float, zone: float) -> float:
    """Rastet **nur in der Nähe** eines Vielfachen ein — sonst freie Fahrt.

    Der Unterschied zu :func:`snap_to_step` ist die Zone: Jenes zieht jeden
    Wert auf das nächste Vielfache, also **jeden**. Beim Drehen ist das
    falsch herum — man dreht frei, und ein Raster, das immer greift, macht
    aus einer Geste eine Auswahl aus acht Möglichkeiten. Vorher stand die
    Winkelvorgabe deshalb auf null, also gar kein Einrasten, und dann trifft
    niemand genau 45 Grad.

    Hier ist beides zu haben (Robert, 03.09.2026): „freies drehen, aber kurzes
    einrasten bei allen 45 grad winkeln außer man dreht weiter". Innerhalb der
    Zone um ein Vielfaches gilt das Vielfache — der Wert bleibt einen Moment
    stehen, obwohl die Maus weiterzieht. Außerhalb gilt der rohe Wert, und wer
    weiterdreht, kommt heraus.

    Zone null oder Schritt null heißt: kein Magnet, der Wert bleibt, wie er
    ist. Eine Zone von der halben Schrittweite ergäbe wieder
    :func:`snap_to_step`, also ist sie darauf begrenzt.
    """
    if step <= EPS_GEOM or zone <= EPS_GEOM:
        return value
    nearest = round(value / step) * step
    if abs(value - nearest) <= min(zone, step / 2.0):
        return nearest
    return value


def rotation_about(direction: Vec3, origin: Vec3, degrees: float) -> np.ndarray:
    """Die Matrix, die um eine Achse durch einen Punkt dreht.

    Hier und nicht in der Ansicht, weil die Ansicht keine Geometrie rechnet
    (§8) — sie braucht die Matrix, um einen laufenden Zug auf seine Raste zu
    ziehen, und das ist eine Drehung wie jede andere.

    **Aus den exakten Winkelfunktionen** (`units.exact_cos_degrees`,
    `exact_sin_degrees`, RM-187), nicht aus ``math.sin(math.radians(…))``:
    Der Sinus von 180 Grad ist dort 1,2 · 10⁻¹⁶ statt null, und eine um 180
    Grad gedrehte Rampe lag mit ihrer Rückseite um dieses Haar neben der
    Stirnfläche der Rippe, an die sie gehört — die Vereinigung ließ beide
    Flächen als Doppelwand ohne Dicke stehen, und der Bereichslauf der Rippe
    meldete an sechs Ecken Selbstdurchdringung (21.09.2026). Ein rechter
    Winkel und eine halbe Drehung sind hier exakt, und beide Kerne drehen
    mit derselben Matrix (``knowledge/parts/shapes.turned`` und ``exact.turned``).
    """
    axis = np.asarray(direction, dtype=float)
    # ``math.hypot`` und ``units.dot3`` statt ``np.linalg.norm`` und ``@``:
    # beides ginge durch BLAS (RM-187). Bis zum 22.09.2026 stand hier
    # ``centre - turn @ centre`` — die Verschiebung jeder Drehung um die Mitte
    # eines Körpers, und damit jede Ecke nach *Drehen*, trug die Rundung der
    # Maschine.
    length = math.hypot(float(axis[0]), float(axis[1]), float(axis[2]))
    if length <= EPS_GEOM:
        raise ValueError("a rotation axis needs a direction")
    x, y, z = (float(value) for value in axis / length)
    cos, sin = exact_cos_degrees(degrees), exact_sin_degrees(degrees)
    rest = 1.0 - cos
    turn = (
        (cos + x * x * rest, x * y * rest - z * sin, x * z * rest + y * sin),
        (y * x * rest + z * sin, cos + y * y * rest, y * z * rest - x * sin),
        (z * x * rest - y * sin, z * y * rest + x * sin, cos + z * z * rest),
    )
    matrix = np.eye(4)
    matrix[:3, :3] = turn
    centre = (float(origin[0]), float(origin[1]), float(origin[2]))
    matrix[:3, 3] = [centre[row] - dot3(turn[row], centre) for row in range(3)]
    return matrix


def along_normal(offset: Vec3, normal: Vec3) -> float:
    """Wie weit ein Zug entlang einer Flächennormalen führt (§18.11).

    Die Maus zieht in drei Richtungen, eine Fläche wandert nur in einer — was
    quer dazu passiert, ist keine Bewegung dieser Fläche und wird verworfen.
    Ohne diese Projektion hätte ein Griff an die Fläche denselben Effekt wie
    ein Griff ans Objekt, und Press/Pull wäre nur ein Verschieben mit einem
    anderen Namen.

    Das Vorzeichen bleibt: nach außen ist positiv, nach innen negativ — genau
    die Zählung, die ``push_face`` erwartet.
    """
    length = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
    if length <= EPS_GEOM:
        return 0.0
    return (offset[0] * normal[0] + offset[1] * normal[1] + offset[2] * normal[2]) / length


def rotation_between(
    source: Sequence[float] | np.ndarray, target: Sequence[float] | np.ndarray
) -> np.ndarray:
    """Die Drehung, die ``source`` auf ``target`` legt — auf jeder Maschine dieselbe.

    **Der Ersatz für ``trimesh.geometry.align_vectors``** (RM-187). Jenes
    rechnet über ``np.linalg.svd``, also durch LAPACK, und LAPACK ist die
    plattformabhängigste Bibliothek im ganzen Stapel: andere Algorithmen,
    andere Blockgrößen, andere Pivotierung. Die Matrix fiel damit auf jeder
    Plattform anders aus — und weil ein ganzes Netz damit gedreht wird, war
    danach jeder Punkt anders.

    Hier steht stattdessen die Formel von Rodrigues, ausgeschrieben: Kein
    Gleichungssystem, keine Zerlegung, nur Produkte und Summen, die NumPy
    einzeln und nach IEEE-754 korrekt gerundet ausführt.

    **Sie liefert die kürzeste Drehung**, ``align_vectors`` eine beliebige aus
    derselben Familie — beide legen ``source`` auf ``target``, sie
    unterscheiden sich im Drehwinkel um die gemeinsame Achse. Für einen
    Rotationskörper ist das die Lage seiner Facetten und kein Maß; dass es
    trotzdem sichtbar wird, weil die Facettierung sich mitdreht, gehört zur
    Umstellung und ist an den Tests gemessen.

    Sind die Richtungen entgegengesetzt, gibt es keine kürzeste Drehung — jede
    Achse senkrecht zu ``source`` tut es. Gewählt wird die, die aus der
    **kleinsten** Komponente entsteht; das ist wohldefiniert und damit auf
    jeder Maschine dieselbe.
    """
    a = _unit(np.asarray(source, dtype=np.float64))
    b = _unit(np.asarray(target, dtype=np.float64))
    cross = np.array(
        (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ),
        dtype=np.float64,
    )
    cosine = float(a[0] * b[0] + a[1] * b[1] + a[2] * b[2])
    sine = math.hypot(float(cross[0]), float(cross[1]), float(cross[2]))
    matrix = np.eye(4, dtype=np.float64)
    if sine <= EPS_GEOM:
        if cosine > 0.0:
            return matrix
        # Gegenrichtung: eine halbe Drehung um irgendeine senkrechte Achse.
        # „Irgendeine" wäre geraten — genommen wird die aus der kleinsten
        # Komponente, damit das Kreuzprodukt am weitesten von null weg ist.
        helper = np.zeros(3, dtype=np.float64)
        helper[int(np.argmin(np.abs(a)))] = 1.0
        axis = _unit(
            np.array(
                (
                    a[1] * helper[2] - a[2] * helper[1],
                    a[2] * helper[0] - a[0] * helper[2],
                    a[0] * helper[1] - a[1] * helper[0],
                ),
                dtype=np.float64,
            )
        )
        matrix[:3, :3] = 2.0 * np.outer(axis, axis) - np.eye(3, dtype=np.float64)
        return matrix
    x, y, z = float(cross[0]), float(cross[1]), float(cross[2])
    if cosine < 0.0:
        # Jenseits von 90° löscht ``1 + cos`` sich aus: bei 175,7° verstärkt
        # der Kehrwert das Rundungsrauschen 350-fach, und die Matrix ist keine
        # Drehung mehr (RM-407). Über die Einheitsachse steht dort ``1 - cos``.
        x, y, z = x / sine, y / sine, z / sine
        rest = 1.0 - cosine
        matrix[:3, :3] = np.array(
            (
                (cosine + x * x * rest, x * y * rest - z * sine, x * z * rest + y * sine),
                (x * y * rest + z * sine, cosine + y * y * rest, y * z * rest - x * sine),
                (x * z * rest - y * sine, y * z * rest + x * sine, cosine + z * z * rest),
            ),
            dtype=np.float64,
        )
        return matrix
    # Rodrigues, ausgeschrieben: I + K + K·K · 1/(1+cos).
    share = 1.0 / (1.0 + cosine)
    matrix[:3, :3] = np.array(
        (
            (1.0 - (y * y + z * z) * share, -z + x * y * share, y + x * z * share),
            (z + x * y * share, 1.0 - (x * x + z * z) * share, -x + y * z * share),
            (-y + x * z * share, x + y * z * share, 1.0 - (x * x + y * y) * share),
        ),
        dtype=np.float64,
    )
    return matrix


def _unit(vector: np.ndarray) -> np.ndarray:
    """Auf Länge eins, über ``math.hypot`` statt ``np.linalg.norm`` (RM-187)."""
    length = math.hypot(float(vector[0]), float(vector[1]), float(vector[2]))
    if length <= EPS_GEOM:
        raise ValueError("a direction of zero length has no rotation")
    return vector / length
