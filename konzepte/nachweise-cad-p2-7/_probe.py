"""Gemeinsame Sondenbibliothek für die P2.7-Nachweise.

Zwei Sorten Helfer, beide bewusst schmal:

* **Exakte Formen über die vorhandene API.** ``brep.edit`` und
  ``brep.profiles`` bauen Quader, Zylinder, Prismen und Drehkörper; ein
  Sechskant, ein Langloch, ein Keil und ein Kegelstumpf sind hier nur ein
  ``Profile`` aus Strecken und Bögen, das ``profiles.extrude`` bzw.
  ``profiles.revolve`` erhält. Es wird kein zweiter Bausteinkern gebaut —
  die Helfer belegen, dass die Formen der Bausteine mit dem heutigen Satz
  entstehen.
* **Messen am exakten Körper.** Native Gültigkeit (``BRepCheck_Analyzer``),
  Körperzahl, Flächenarten, Volumen und Fläche aus den Kernintegralen,
  Punkt-im-Körper-Tests für Funktionsmaße und Richtung, STEP-Rundreise.

Die Ergebnisse werden je Sonde gesammelt; ``finish()`` schreibt die
Zusammenfassung und beendet mit dem echten Exitcode (0 nur, wenn jede
Zusicherung hielt).
"""

from __future__ import annotations

import math
import sys
from collections import Counter
from collections.abc import Sequence
from typing import Any

import _iso  # noqa: F401
import numpy as np

from app.core.brep import edit, profiles, step
from app.core.brep.kernel import Solid
from app.core.geom.mesh import MeshData
from app.core.sketch.profile import Profile, ProfileSegment
from app.core.units import EPS_GEOM

Point2 = tuple[float, float]
Vec3 = tuple[float, float, float]

_RESULTS: list[tuple[bool, str]] = []


# --- Berichten ----------------------------------------------------------------------


def out(line: str = "") -> None:
    print(line)
    sys.stdout.flush()


def check(label: str, ok: bool, detail: str = "") -> bool:
    """Eine Zusicherung mit Text; sammelt für den Exitcode."""
    _RESULTS.append((bool(ok), label))
    mark = "OK " if ok else "ROT"
    out(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def close(label: str, actual: float, expected: float, tol: float = 1e-6) -> bool:
    """Zwei Zahlen, absolute Toleranz, beide im Text."""
    ok = abs(actual - expected) <= tol
    return check(label, ok, f"ist {actual:.6f}, erwartet {expected:.6f} (±{tol:g})")


def ratio(label: str, actual: float, expected: float, rel: float) -> bool:
    """Zwei Zahlen, relative Toleranz — für den Vergleich Netz gegen exakt."""
    if expected == 0.0:
        return check(label, abs(actual) <= rel, f"ist {actual:.6f}, erwartet 0")
    q = actual / expected
    return check(label, abs(q - 1.0) <= rel, f"Verhältnis {q:.6f} (erlaubt ±{rel:g})")


def finish(name: str) -> None:
    failed = [label for ok, label in _RESULTS if not ok]
    out()
    out(f"{name}: {len(_RESULTS) - len(failed)} von {len(_RESULTS)} Zusicherungen halten")
    for label in failed:
        out(f"  ROT: {label}")
    sys.exit(1 if failed else 0)


# --- Exakte Formen über die vorhandene API ---------------------------------------


def polygon(points: Sequence[Point2]) -> Profile:
    segs = []
    for index in range(len(points)):
        a, b = points[index - 1], points[index]
        segs.append(ProfileSegment("line", (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))))
    return Profile(segments=tuple(segs))


def prism(points: Sequence[Point2], height: float, plane: str = "plane:xy") -> Solid:
    """Ein Vieleck, senkrecht zu seiner Ebene aufgezogen."""
    return profiles.extrude(polygon(points), height, plane)


def box(width: float, depth: float, height: float) -> Solid:
    return edit.box(width, depth, height)


def cylinder(diameter: float, height: float) -> Solid:
    return edit.cylinder(diameter, height)


def hexagon(width: float, height: float) -> Solid:
    """Sechskantprisma über die Schlüsselweite — wie ``shapes.hexagon``."""
    radius = width / math.sqrt(3.0)
    points = [
        (radius * math.cos(a), radius * math.sin(a))
        for a in (math.pi / 6.0 + k * math.pi / 3.0 for k in range(6))
    ]
    return prism(points, height)


def slot_profile(width: float, length: float) -> Profile:
    """Langloch-Umriss: zwei Strecken, zwei **echte** Halbkreisbögen, Länge in X."""
    r = width / 2.0
    o = (length - width) / 2.0
    if length <= width:
        return Profile(circle=((0.0, 0.0), r))
    return Profile(
        segments=(
            ProfileSegment("line", (-o, -r), (o, -r)),
            ProfileSegment("arc", (o, -r), (o, r), via=(o + r, 0.0)),
            ProfileSegment("line", (o, r), (-o, r)),
            ProfileSegment("arc", (-o, r), (-o, -r), via=(-o - r, 0.0)),
        )
    )


def slot(width: float, length: float, height: float) -> Solid:
    return profiles.extrude(slot_profile(width, length), height)


def wedge(width: float, depth: float, height: float, tip: float = 0.0) -> Solid:
    """Rampe wie ``shapes.wedge``: X breit (zentriert), Y tief, Z hoch."""
    outline: list[Point2] = [(0.0, 0.0), (depth, 0.0), (0.0, height)]
    if tip > 0.0:
        outline = [(0.0, 0.0), (depth, 0.0), (tip, height), (0.0, height)]
    # In YZ zeichnen (x -> Y, y -> Z) und entlang +X aufziehen, dann zentrieren.
    body = profiles.extrude(polygon(outline), width, "plane:yz")
    return edit.moved(body, (-width / 2.0, 0.0, 0.0))


def cone(bottom: float, top: float, height: float) -> Solid:
    """Kegelstumpf auf Z = 0 — als Drehkörper eines Trapezes in XZ."""
    outline = [(0.0, 0.0), (bottom / 2.0, 0.0), (top / 2.0, height), (0.0, height)]
    if top <= 0.0:
        outline = [(0.0, 0.0), (bottom / 2.0, 0.0), (0.0, height)]
    return profiles.revolve(polygon(outline), 360.0)


def revolved(outline: Sequence[Point2]) -> Solid:
    """Ein geschlossener Querschnitt (x = Radius, y = Höhe) um Z gedreht."""
    return profiles.revolve(polygon(outline), 360.0)


def tapered_bar(width: float, narrow: float, length: float, height: float, taper: float) -> Solid:
    if taper <= 0.0 or narrow >= width:
        return box(width, length, height)
    hw, hn = width / 2.0, narrow / 2.0
    end, shoulder = length / 2.0, length / 2.0 - taper
    if shoulder <= 0.0:
        pts = [(-hn, -end), (hn, -end), (hw, 0.0), (hn, end), (-hn, end), (-hw, 0.0)]
    else:
        pts = [
            (-hn, -end),
            (hn, -end),
            (hw, -shoulder),
            (hw, shoulder),
            (hn, end),
            (-hn, end),
            (-hw, shoulder),
            (-hw, -shoulder),
        ]
    return prism(pts, height)


def rounded_rect_profile(width: float, depth: float, radius: float) -> Profile:
    """Gerundetes Rechteck mit **exakten** Viertelkreisen — wie ``rounded_prism``."""
    if radius <= EPS_GEOM:
        return polygon(
            [
                (-width / 2, -depth / 2),
                (width / 2, -depth / 2),
                (width / 2, depth / 2),
                (-width / 2, depth / 2),
            ]
        )
    w, d, r = width / 2.0, depth / 2.0, radius
    s = math.sqrt(0.5)
    segs = (
        ProfileSegment("line", (-w + r, -d), (w - r, -d)),
        ProfileSegment("arc", (w - r, -d), (w, -d + r), via=(w - r + r * s, -d + r - r * s)),
        ProfileSegment("line", (w, -d + r), (w, d - r)),
        ProfileSegment("arc", (w, d - r), (w - r, d), via=(w - r + r * s, d - r + r * s)),
        ProfileSegment("line", (w - r, d), (-w + r, d)),
        ProfileSegment("arc", (-w + r, d), (-w, d - r), via=(-w + r - r * s, d - r + r * s)),
        ProfileSegment("line", (-w, d - r), (-w, -d + r)),
        ProfileSegment("arc", (-w, -d + r), (-w + r, -d), via=(-w + r - r * s, -d + r - r * s)),
    )
    return Profile(segments=segs)


def rounded_prism(width: float, depth: float, height: float, radius: float) -> Solid:
    return profiles.extrude(rounded_rect_profile(width, depth, radius), height)


def moved(solid: Solid, offset: Vec3) -> Solid:
    return edit.moved(solid, offset)


def turned(solid: Solid, degrees: float, axis: Vec3 = (0.0, 0.0, 1.0)) -> Solid:
    """Drehung um eine Achse durch den Ursprung — als exakte Transformation."""
    a = np.asarray(axis, dtype=float)
    a = a / np.linalg.norm(a)
    t = math.radians(degrees)
    c, s = math.cos(t), math.sin(t)
    x, y, z = a
    rot = np.array(
        [
            [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s, 0.0],
            [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s, 0.0],
            [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c), 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    matrix = tuple(tuple(float(v) for v in row) for row in rot)
    return edit.transformed(solid, matrix)  # type: ignore[arg-type]


def union(*parts: Solid) -> Solid:
    bodies = [p for p in parts if p is not None]
    if len(bodies) == 1:
        return bodies[0]
    return edit.boolean("union", bodies)


def subtract(base: Solid, *cutters: Solid) -> Solid:
    return edit.boolean("difference", [base, *cutters])


def intersect(first: Solid, second: Solid) -> Solid:
    return edit.boolean("intersection", [first, second])


# --- Messen am exakten Körper ------------------------------------------------------


def is_valid(solid: Solid) -> bool:
    from OCP.BRepCheck import BRepCheck_Analyzer

    return bool(BRepCheck_Analyzer(solid.shape).IsValid())


def face_types(solid: Solid) -> Counter[str]:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.TopoDS import TopoDS

    names = {
        0: "plane",
        1: "cylinder",
        2: "cone",
        3: "sphere",
        4: "torus",
        5: "bezier",
        6: "bspline",
        7: "revolution",
        8: "extrusion",
        9: "offset",
        10: "other",
    }
    found: Counter[str] = Counter()
    for face in solid.faces():
        kind = BRepAdaptor_Surface(TopoDS.Face(face)).GetType()
        found[names.get(int(kind), str(kind))] += 1
    return found


def bounds(solid: Solid) -> tuple[float, float, float, float, float, float]:
    return profiles.bounds(solid)


def inside(solid: Solid, point: Vec3, tolerance: float = 1e-7) -> bool:
    """Liegt der Punkt im Material des Körpers (ON zählt als innen)?"""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON

    classifier = BRepClass3d_SolidClassifier(solid.shape, gp_Pnt(*point), tolerance)
    return classifier.State() in (TopAbs_IN, TopAbs_ON)


def radial_extent(
    solid: Solid, z: float, direction: Point2 = (1.0, 0.0), limit: float = 200.0
) -> float:
    """Wie weit das Material bei Höhe z entlang einer Richtung von der Achse reicht.

    Bisektion über den Punkttest: robust gegen Nähte und ohne Strahlaufruf.
    Erwartet Material auf der Achse; für Werkzeuge misst es die Werkzeugweite.
    """
    dx, dy = direction
    n = math.hypot(dx, dy)
    dx, dy = dx / n, dy / n
    lo, hi = 0.0, limit
    if not inside(solid, (0.0, 0.0, z)):
        return 0.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if inside(solid, (mid * dx, mid * dy, z)):
            lo = mid
        else:
            hi = mid
    return lo


def report(name: str, solid: Solid) -> dict[str, Any]:
    """Der Steckbrief eines exakten Körpers, ausgegeben und zurückgegeben."""
    info: dict[str, Any] = {
        "valid": is_valid(solid),
        "closed": solid.is_closed,
        "solids": solid.solid_count,
        "faces": solid.face_count,
        "edges": solid.edge_count,
        "volume": solid.volume,
        "area": solid.area,
        "types": dict(face_types(solid)),
        "bounds": tuple(round(v, 6) for v in bounds(solid)),
    }
    out(
        f"  {name}: valid={info['valid']} closed={info['closed']} solids={info['solids']} "
        f"faces={info['faces']} V={info['volume']:.6f} A={info['area']:.4f}"
    )
    out(f"      types={info['types']} bounds={info['bounds']}")
    return info


def expect_solid(name: str, solid: Solid, *, solids: int = 1) -> dict[str, Any]:
    info = report(name, solid)
    check(f"{name}: nativ gültig", info["valid"])
    check(f"{name}: geschlossen", info["closed"])
    check(f"{name}: Körperzahl {solids}", info["solids"] == solids, f"ist {info['solids']}")
    return info


def step_roundtrip(name: str, solid: Solid, *, faces: bool = True) -> Solid:
    """STEP hinaus und wieder hinein; Volumen und Flächenzahl müssen halten."""
    payload = step.write(solid, name)
    back = step.read(payload)
    check(f"{name}: STEP-Rundreise gültig", is_valid(back))
    close(
        f"{name}: STEP-Rundreise Volumen", back.volume, solid.volume, 1e-6 * max(1.0, solid.volume)
    )
    if faces:
        check(
            f"{name}: STEP-Rundreise Flächenzahl",
            back.face_count == solid.face_count,
            f"{back.face_count} gegen {solid.face_count}",
        )
    return back


# --- Netzweg -----------------------------------------------------------------------


def mesh_report(name: str, mesh: MeshData) -> dict[str, Any]:
    info = {
        "watertight": mesh.is_watertight,
        "components": mesh.component_count,
        "volume": float(mesh.volume),
        "bounds": tuple(round(float(v), 6) for v in np.asarray(mesh.raw.bounds).ravel()),
        "triangles": int(mesh.raw.faces.shape[0]),
    }
    out(
        f"  {name} (Netz): watertight={info['watertight']} components={info['components']} "
        f"V={info['volume']:.6f} tris={info['triangles']}"
    )
    out(f"      bounds={info['bounds']}")
    return info


def polygon_ratio(segments: int) -> float:
    """Fläche eines regelmäßigen n-Ecks im Umkreis, geteilt durch die Kreisfläche.

    Das ist der **erlaubte Facettierungsunterschied** eines Zylinder- oder
    Kegelvolumens zwischen Netzweg (48 Segmente) und exaktem Weg.
    """
    return segments / (2.0 * math.pi) * math.sin(2.0 * math.pi / segments)


def mesh_distance(mesh: MeshData, solid: Solid, samples: int = 400, seed: int = 7) -> float:
    """Größter Abstand abgetasteter Netzpunkte zur exakten Oberfläche (einseitig).

    Ein Facettenpunkt eines 48-Ecks liegt höchstens ``r·(1-cos(π/48))`` unter
    dem Kreis; alles darüber ist ein Formunterschied, keine Facettierung.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt

    raw = mesh.raw
    rng = np.random.default_rng(seed)
    points, _ = (
        raw.sample(samples, return_index=True) if hasattr(raw, "sample") else (raw.vertices, None)
    )
    points = np.asarray(points, dtype=float)
    if points.shape[0] > samples:
        points = points[rng.choice(points.shape[0], samples, replace=False)]
    worst = 0.0
    for p in points:
        vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(float(p[0]), float(p[1]), float(p[2]))).Vertex()
        dist = BRepExtrema_DistShapeShape(vertex, solid.shape)
        if dist.IsDone() and dist.NbSolution() > 0:
            worst = max(worst, float(dist.Value()))
    return worst


def radial_minmax(solid: Solid, z: float, samples: int = 36) -> tuple[float, float]:
    """Kleinste und größte radiale Materialreichweite bei Höhe z über den Umfang.

    Bei einem Gewinde ist das Minimum der Kern und das Maximum der Gang;
    ``bounds`` taugt dafür nicht, weil die NURBS-Hülle einen Zuschlag trägt.
    """
    values = []
    for index in range(samples):
        angle = 2.0 * math.pi * index / samples
        values.append(radial_extent(solid, z, (math.cos(angle), math.sin(angle))))
    return min(values), max(values)


class Timed:
    """Zeitstempel als Beobachtung im Bericht — keine Leistungsprüfung, kein Budget."""

    def __init__(self, label: str) -> None:
        self.label = label

    def __enter__(self) -> Timed:
        import time

        self.start = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        import time

        out(f"  (Dauer {self.label}: {time.perf_counter() - self.start:.1f} s — Beobachtung)")


def thread_ridge_exact(
    diameter: float,
    pitch: float,
    length: float,
    *,
    internal: bool = False,
    depth: float | None = None,
) -> Solid:
    """Prototyp: der Gewindegang des **Netzwegs** als exakter Helix-Sweep.

    Dasselbe Vier-Punkt-Profil wie ``shapes.thread_body`` (Fuß 0,8·p, Kamm
    zwischen 0,25·p und 0,55·p abgeflacht, Tiefe 0,55·p), entlang derselben
    Helix, mit ``BRepOffsetAPI_MakePipeShell`` wie ``profiles.threaded_rod``.
    Kern plus Gang, auf Länge geschnitten. Das ist die Eigenentwicklung, die
    P2.7 für die Gewindebausteine braucht, wenn das Gangprofil des Netzwegs
    erhalten bleiben soll — ``threaded_rod`` trägt ein anderes Profil.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.BRepLib import BRepLib
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.Geom import Geom_CylindricalSurface
    from OCP.Geom2d import Geom2d_Line
    from OCP.gp import gp_Ax2d, gp_Ax3, gp_Dir2d, gp_Pnt, gp_Pnt2d

    from app.core.knowledge.parts import shapes as mesh_shapes

    if depth is None:
        depth = pitch * mesh_shapes.RIDGE_SHARE
    radius = diameter / 2.0
    root_radius = radius if internal else radius - depth
    crest_radius = radius + depth if internal else radius
    turns = length / pitch + 2.0
    surface = Geom_CylindricalSurface(gp_Ax3(), root_radius)
    line = Geom2d_Line(gp_Ax2d(gp_Pnt2d(0.0, -pitch), gp_Dir2d(2.0 * math.pi, pitch)))
    span = math.hypot(2.0 * math.pi, pitch) * turns
    helix = BRepBuilderAPI_MakeEdge(line, surface, 0.0, span).Edge()
    BRepLib.BuildCurves3d_s(helix)
    spine = BRepBuilderAPI_MakeWire(helix).Wire()
    # Profil in der XZ-Ebene am Helixstart (Winkel 0, Höhe -pitch), radial x, axial z.
    inward = root_radius - 0.1
    corners = (
        (inward, -pitch),
        (root_radius, -pitch),
        (crest_radius, -pitch + pitch * 0.25),
        (crest_radius, -pitch + pitch * mesh_shapes.RIDGE_SHARE),
        (root_radius, -pitch + pitch * mesh_shapes.RIDGE_END),
        (inward, -pitch + pitch * mesh_shapes.RIDGE_END),
    )
    outline = BRepBuilderAPI_MakeWire()
    for index in range(len(corners)):
        a, b = corners[index - 1], corners[index]
        outline.Add(
            BRepBuilderAPI_MakeEdge(gp_Pnt(a[0], 0.0, a[1]), gp_Pnt(b[0], 0.0, b[1])).Edge()
        )
    pipe = BRepOffsetAPI_MakePipeShell(spine)
    pipe.SetMode(True)
    pipe.Add(outline.Wire())
    pipe.Build()
    if not pipe.IsDone():
        raise RuntimeError("Gewindegang: MakePipeShell scheiterte")
    pipe.MakeSolid()
    ridge = Solid(pipe.Shape())
    # Innen: der Kern ist das Werkzeug selbst (Ø + 2·Überlappung), der Gang wächst
    # nach außen; außen: der Kern liegt zwei Gangtiefen unter dem Außenmaß.
    core = cylinder(diameter + 0.02 if internal else 2.0 * root_radius + 0.02, length)
    slab = cylinder(2.0 * crest_radius + 2.0, length)
    trimmed = edit.boolean("intersection", [ridge, slab])
    # Der Zuschnitt kommt als Compound zurück; die Vereinigung bekommt den Solid darin.
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    explorer = TopExp_Explorer(trimmed.shape, TopAbs_SOLID)
    ridge_solid = Solid(TopoDS.Solid(explorer.Current()))
    # **Ohne Fuzzy-Toleranz verschluckt die Vereinigung den Gang still**: gültig,
    # ein Körper, Volumen = Kern (gemessen, s3b). ``profiles.threaded_rod`` kennt
    # dieselbe Stufenleiter (``ROD_FUZZ_RATIOS``); hier gilt sie ebenso.
    from OCP.BRepCheck import BRepCheck_Analyzer

    from app.core.brep.kernel import boolean_builder, copy_shape

    core_volume = core.volume
    for ratio_ in (1e-4, 1e-3, 1e-2):
        # Jede Stufe auf privaten Kopien: dieselben Eingaben mehrfach durch
        # Fuzzy-Booleans zu schicken riss den Prozess (s3b, Exit 139).
        left, _ = copy_shape(core.shape)
        right, _ = copy_shape(ridge_solid.shape)
        operation = boolean_builder("union", left, right, tolerance=ratio_ * pitch)
        operation.Build()
        if not operation.IsDone():
            continue
        candidate = Solid(operation.Shape())
        if (
            candidate.solid_count == 1
            and candidate.is_closed
            and BRepCheck_Analyzer(candidate.shape).IsValid()
            and candidate.volume > core_volume * 1.05
        ):
            return candidate
    raise RuntimeError("Kern und Gang ließen sich auf keiner Fuzzy-Stufe vereinigen")


def mesh_contains(mesh: MeshData, points: Sequence[Vec3]) -> list[bool]:
    """Punkt-im-Netz-Test ohne ``rtree``: Strahl in +X, Schnitte mit den Dreiecken zählen.

    Möller-Trumbore über alle Dreiecke in NumPy — für die kleinen Bausteinnetze
    der Sonden ausreichend; ``trimesh.contains`` verlangt ``rtree``, das in der
    Umgebung nicht installiert ist.
    """
    tri = np.asarray(mesh.raw.triangles, dtype=float)
    v0, v1, v2 = tri[:, 0], tri[:, 1], tri[:, 2]
    e1, e2 = v1 - v0, v2 - v0
    direction = np.array([1.0, 0.3e-3, 0.7e-3])
    direction /= np.linalg.norm(direction)
    results = []
    for p in points:
        origin = np.asarray(p, dtype=float)
        h = np.cross(direction, e2)
        a = np.einsum("ij,ij->i", e1, h)
        ok = np.abs(a) > 1e-12
        f = np.zeros_like(a)
        f[ok] = 1.0 / a[ok]
        s = origin - v0
        u = f * np.einsum("ij,ij->i", s, h)
        q = np.cross(s, e1)
        v = f * np.einsum("ij,j->i", q, direction)
        t = f * np.einsum("ij,ij->i", e2, q)
        hit = ok & (u >= 0.0) & (v >= 0.0) & (u + v <= 1.0) & (t > 1e-9)
        results.append(bool(int(hit.sum()) % 2 == 1))
    return results


def offset_face(profile: Profile, distance: float) -> Any:
    """Exakter Normalversatz einer Kontur über ``BRepOffsetAPI_MakeOffset``.

    Der eine Baustein, den Klemmen und Dichtungen zusätzlich brauchen: Die
    Kontur kommt als ``Profile`` (Strecken, Bögen, Kreis), der Versatz bleibt
    exakt — Bögen werden Bögen, Ecken erhalten Kreisbögen (``GeomAbs_Arc``).
    ``_face`` ist der Sondenzugriff auf den vorhandenen Flächenbau.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
    from OCP.GeomAbs import GeomAbs_Arc
    from OCP.TopoDS import TopoDS

    face = profiles._face(profile, profiles._lift_xy)
    if abs(distance) <= EPS_GEOM:
        return face
    offset = BRepOffsetAPI_MakeOffset(TopoDS.Face(face), GeomAbs_Arc)
    offset.Perform(distance)
    if not offset.IsDone():
        raise RuntimeError("Offset scheiterte")
    wire = TopoDS.Wire(offset.Shape())
    return BRepBuilderAPI_MakeFace(wire, True).Face()


def prism_of_face(face: Any, height: float, z0: float = 0.0) -> Solid:
    """Eine fertige Fläche senkrecht aufziehen — für Offset-Konturen."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    body = Solid(BRepPrimAPI_MakePrism(face, gp_Vec(0.0, 0.0, height)).Shape())
    return edit.moved(body, (0.0, 0.0, z0)) if z0 else body


def band(profile: Profile, width: float, height: float, z0: float = 0.0) -> Solid:
    """Das Band beiderseits eines geschlossenen Wegs — wie ``seal._band``, exakt."""
    outside = prism_of_face(offset_face(profile, width / 2.0), height, z0)
    inside = prism_of_face(offset_face(profile, -width / 2.0), height + 2.0, z0 - 1.0)
    return edit.boolean("difference", [outside, inside])


def sphere(radius: float, centre: Vec3) -> Solid:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCP.gp import gp_Pnt

    return Solid(BRepPrimAPI_MakeSphere(gp_Pnt(*centre), radius).Shape())


def torus(major: float, minor: float, centre_z: float) -> Solid:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    axis = gp_Ax2(gp_Pnt(0.0, 0.0, centre_z), gp_Dir(0.0, 0.0, 1.0))
    return Solid(BRepPrimAPI_MakeTorus(axis, major, minor).Shape())


def capsule_chain(points: Sequence[Point2], radius: float, centre_z: float) -> Solid:
    """Kugel-Sweep entlang eines geschlossenen Polygonwegs, exakt.

    Je Strecke ein Zylinder, je Ecke eine Kugel; die Vereinigung ist die
    Minkowski-Summe des Wegs mit der Kugel — dieselbe Form, die
    ``seal._round_tube`` als Hüllenkette facettiert baut.
    """
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    parts: list[Solid] = []
    for index, (x, y) in enumerate(points):
        nx, ny = points[(index + 1) % len(points)]
        dx, dy = nx - x, ny - y
        length = math.hypot(dx, dy)
        axis = gp_Ax2(gp_Pnt(x, y, centre_z), gp_Dir(dx / length, dy / length, 0.0))
        parts.append(Solid(BRepPrimAPI_MakeCylinder(axis, radius, length).Shape()))
        parts.append(sphere(radius, (x, y, centre_z)))
    result = parts[0]
    for part in parts[1:]:
        result = edit.boolean("union", [result, part])
    return result


def extent_along(solid: Solid, origin: Vec3, direction: Vec3, limit: float = 200.0) -> float:
    """Abstand vom Ursprung bis zum **ersten** Zustandswechsel (Material/Luft) in einer Richtung.

    Liegt der Ursprung im Material, ist das die Wandreichweite; liegt er in der
    Luft (etwa auf einer Bohrungsachse), der Radius bis zur Wand. Erst eine
    lineare Vorsuche in kleinen Schritten, dann Bisektion — eine reine
    Bisektion fände an einer Leiter irgendeine Wand, nicht die nächste.
    """
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    o = np.asarray(origin, dtype=float)

    def state_at(t: float) -> bool:
        p = o + t * d
        return inside(solid, (float(p[0]), float(p[1]), float(p[2])))

    state = state_at(0.0)
    step = 0.02
    lo, hi = 0.0, step
    while hi <= limit and state_at(hi) == state:
        lo = hi
        step = min(step * 1.5, 1.0)
        hi = lo + step
    if hi > limit:
        return limit
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if state_at(mid) == state:
            lo = mid
        else:
            hi = mid
    return lo


def hole_diameter(solid: Solid, axis_xy: Point2, z: float) -> float:
    """Durchmesser einer Bohrung um eine Achse bei Höhe z — aus der Luft heraus gemessen."""
    x, y = axis_xy
    return extent_along(solid, (x, y, z), (1.0, 0.0, 0.0)) + extent_along(
        solid, (x, y, z), (-1.0, 0.0, 0.0)
    )
