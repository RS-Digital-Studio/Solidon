"""Merkmale aus der Topologie (Bauplan §30, §21).

Auf einem Netz heißt ein Loch zu finden: Dreiecke gruppieren und einen
Zylinder hineinpassen — und ihm einen Namen zu geben, der die nächste
Operation überlebt, heißt gegen die vorigen Namen zuordnen (§21.2). Auf einem
B-Rep-Körper nennt eine analytische Fläche Radius und Achse selbst.
Rationale B-Splines werden zusätzlich über die gemeinsame Trägerbeschreibung
geprüft. Erkennung und Kennzahlen ändern dabei weder Trimmkurven noch Körperform.

Das ist der Sprung, den §30 verspricht, und darum ist diese Datei kurz. Was
sie nicht tut, ist Gewissheit erfinden: eine zylindrische Fläche wird nur als
Loch gemeldet, wenn sie eine volle Umdrehung macht und ins Material zeigt —
eine gerundete Außenecke ist auch ein Zylinder, und sie eine Bohrung zu nennen
setzte eine Schraube durch die Wand.

**Eine Ausnahme von „eine Fläche, ein Merkmal" gibt es**, und es ist dieselbe
wie auf der Netzseite (:mod:`app.core.perceive.slots`): Ein Langloch besteht
aus vier Flächen und ist ein Merkmal. Wer sie einzeln benennt, bekommt zwei
Verrundungen und zwei Wände, und die Handlungen an einem Langloch stehen an
keiner von ihnen — gemessen am 11.09.2026 an einer exakten Platte: `fillet_1`
und `fillet_2`, wo eine Öffnung ist (Robert: „auf einem langloch 2 werden und
nicht mehr wählbar"). :func:`_slots_instead_of_half_bores` setzt sie wieder
zusammen, nachdem jede Fläche für sich beschrieben ist.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.core.brep.canonical import (
    ConeSurface,
    CylinderSurface,
    PlaneSurface,
    SphereSurface,
    Surface,
    TorusSurface,
)
from app.core.brep.kernel import Solid, boolean_builder, face_sources, listed, nearest_distance
from app.core.brep.properties import properties
from app.core.log import get_logger
from app.core.types import (
    CancelToken,
    Feature,
    FeatureId,
    FeatureKind,
    SurfaceKind,
    SurfacePatch,
    Vec3,
)
from app.core.units import EPS_DISPLAY, EPS_GEOM, match_tolerance, positive_axis

_log = get_logger(__name__)


def _oriented(direction: Any) -> Vec3:
    """Die Achse einer Fläche mit dem Vorzeichen, das auch das Netz vergibt.

    OpenCASCADE gibt die Richtung so zurück, wie die Fläche gebaut wurde: Eine
    Bohrung von unten trägt minus Z, und das Langloch aus *Zum Langloch
    ziehen* die Gegenrichtung seiner Bohrung — gemessen 11.09.2026, mit einem
    Feld *Richtung*, das nach einem Zug mit 45 Grad minus 45 zeigte, und
    einem zweiten Zug mit derselben 45, der ein Kreuz schnitt. Der Winkel
    eines Langlochs zählt gegen den Rahmen dieser Achse; welches Vorzeichen
    sie trägt, entscheidet deshalb :func:`app.core.units.positive_axis` für
    beide Kerne gleich.
    """
    return positive_axis((direction.X(), direction.Y(), direction.Z()))


def _full_turn() -> float:
    """Wie viel Umfang eine zylindrische Fläche abdecken muss, um als Bohrung zu
    zählen, im Bogenmaß. Darunter ist sie eine Verrundung oder eine gerundete
    Ecke, kein Loch.

    **Dieselbe Zahl wie am Netz**, von dort gelesen
    (``perceive.features.FULL_TURN_SPAN``, 300 Grad) — träge wie jeder Import
    von ``brep`` nach ``perceive`` (``tests/test_core_package_direction.py``).
    Bis zum 20.09.2026 stand hier eine eigene Zahl, 0,9 der Umdrehung, und ein
    Mantel von 315 Grad war am exakten Körper eine Verrundung und am Netz eine
    Bohrung (P1.5). Was er ist, sagt darüber hinaus ``partial``: Unter der
    vollen Umdrehung ist eine Bohrung angeschnitten, und ob sie für sich
    bearbeitbar ist, entscheidet ihre Nachbarschaft (``perceive.relations``),
    nicht der Winkel.
    """
    from app.core.perceive.features import FULL_TURN_SPAN

    return FULL_TURN_SPAN / 360.0 * math.tau


@dataclass(frozen=True, slots=True)
class _ThroughQuestion:
    """Die Frage „durchgehend?" an eine Bohrung — gestellt erst, wenn sie bleibt.

    :func:`_axis_covered` misst Abstände zwischen Probelinien und den
    Nachbarflächen des Mantels; an den B-Spline-Flanken eines Gewindes kostet
    das 0,2 s je Probe. Jeder Fußstreifen eines Innengewindes ist ein voller
    Zylindermantel und damit zunächst eine Bohrung, die das Gewinde danach
    als Phantom verdrängt: An ``innen_zweigaengig.step`` gingen 4,3 von 5,0 s
    der Erkennung in Antworten, die niemand las (Review 22.09.2026).
    :func:`features_of` beantwortet die Frage deshalb nach dem Gewinde, nur
    für die Bohrungen, die es noch gibt. ``first`` und ``last`` sind die
    Achsgrenzen der Probelinien, die Reichweite schon eingerechnet.
    """

    face: Any
    cylinder: Any
    first: float
    last: float


#: Wie viele Nachbarflächen einer kugeligen Fläche selbst Kantenverrundungen
#: sein müssen, damit sie als Ecke gilt — die Stelle, an der verrundete Kanten
#: zusammenlaufen. Zwei, weil eine Ecke aus mindestens zwei Kanten entsteht.
#:
#: **Nicht über die Größe.** Der erste Versuch maß den Anteil an der Vollkugel
#: (Eckverrundung 0,125, volle Kugel 1,000) und trennte damit falsch: Eine
#: Pfanne ist nie mehr als eine Halbkugel, eine flache Kalotte — eine
#: Magnettasche etwa — kann selbst 0,1 abdecken. Gemessen an einer aus einem
#: Quader geschnittenen Kugel: 1 Nachbar, 0 Verrundungen; an der Ecke eines
#: rundum verrundeten Quaders: 3 Nachbarn, 3 Verrundungen.
CORNER_NEIGHBOURS = 2

# Die drei Toleranzen des Langlochs kommen von der Netzseite und stehen nur
# dort: Wie parallel zwei Bogenachsen sein müssen, wie gleich zwei Radien und
# ab welchem Winkel eine Fläche zum Mantel gehört. Dieselbe Frage, dieselbe
# Zahl, eine Stelle — und der exakte Kern hält sie mit mehr Abstand ein, weil
# seine Bögen aus einem Umriss aufgezogen sind und nicht eingepasst. **Nicht**
# ``match_tolerance`` für die Radien: Die ist ein halbes Prozent der
# Modelldiagonale und hielte an einer Platte von 108 mm Ø 6 und Ø 7 für
# dasselbe Loch.


def features_of(
    solid: Solid,
    *,
    cancelled: CancelToken | None = None,
    known_threads: Sequence[Feature] | None = None,
) -> dict[FeatureId, Feature]:
    """Löcher und ebene Flächen, aus der Topologie abgelesen statt
    eingepasst.

    ``known_threads`` sind Gewinde, die der Erzeuger kennt (``thread_exact``):
    An ihrer Stelle wird nicht gelesen, sie verdrängen aber dieselben
    Phantome wie ein gelesenes. Den Bolzen, den der Erzeuger eben genäht
    hat, las der Leser sonst noch einmal — am M3 x 0,5 x 60 2,7 von 4 Sekunden
    der Erkennung, für eine Auskunft, die danach überschrieben wurde
    (Review 22.09.2026).
    """
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    found: dict[FeatureId, Feature] = {}
    counts = {"hole": 0, "pin": 0, "face": 0, "fillet": 0, "sphere": 0}
    # Einmal je Körper, nicht einmal je Fläche: der Klassierer baut sich eine
    # Beschleunigungsstruktur auf, und die gilt für den ganzen Solid.
    inside = BRepClass3d_SolidClassifier(solid.shape)
    # Welche Flächen an einer Kante zusammenstoßen — auch einmal je Körper. Eine
    # kugelige Fläche ist daran zu erkennen, dass ihre Nachbarn Verrundungen
    # sind: dann ist sie die Ecke, an der die verrundeten Kanten zusammenlaufen.
    neighbours = NeighbourMap()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, neighbours)

    # Wie weit ein Achsstrahl reichen muss, um jede Nachbarfläche zu treffen,
    # und ab wann ein Abstand „auf der Achse" heißt — beides einmal je Körper,
    # aus seiner Größe (§11.2).
    reach = solid.bounds.diagonal
    tolerance = match_tolerance(reach)

    # Welches Merkmal auf welcher Topologiefläche sitzt — der Nachschritt unten
    # braucht den Weg zurück, und ihn hier mitzuschreiben kostet nichts.
    named: dict[int, FeatureId] = {}
    surfaces: dict[int, Surface | None] = {}
    surface_patches: dict[int, SurfacePatch] = {}
    # Die Flächen eines Gewindes, das der Erzeuger kennt, werden nicht erst
    # beschrieben: Was dort entstünde — Zapfen, Kegel, Rundungen auf der
    # Wendel —, verdrängt das Gewinde unten ohnehin als Phantom. Am
    # M3 x 0,5 x 60 sind das 363 Regelflächen und 0,6 s Trägerprüfung, dazu
    # eine Klassierung am ganzen Bolzen (0,4 s) für eine angeschnittene
    # Fußfläche (Review 22.09.2026).
    covered = (
        {face for thread in known_threads for face in solid.faces_of_triangles(thread.face_indices)}
        if known_threads
        else set()
    )
    for index, face in enumerate(solid.faces()):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if index in covered:
            surfaces[index] = None
            continue
        surfaces[index] = solid.surface(index, cancelled=cancelled)
        native_patch = _native_patch(solid, index, surfaces[index], cancelled=cancelled)
        if native_patch is not None:
            surface_patches[index] = native_patch
        described = _describe(
            solid,
            face,
            index,
            inside,
            neighbours,
            reach,
            surface=surfaces[index],
            cancelled=cancelled,
        )
        if described is None:
            continue
        kind, params = described
        counts[kind] = counts.get(kind, 0) + 1
        identifier = f"{kind}_{counts[kind]}"
        named[index] = identifier
        found[identifier] = Feature(
            id=identifier,
            kind=kind,
            provenance="detected",
            params=params,
            measure_sources={
                name: "native"
                for name, value in params.items()
                if not isinstance(value, (bool, _ThroughQuestion))
            },
            # Eine Topologiefläche besteht im Viewport aus vielen Dreiecken.
            # Der nackte ``index`` gehört zur B-Rep-Flächenliste und wäre als
            # Dreiecksindex eine andere Zahl mit zufällig gültigem Bereich.
            face_indices=solid.triangles_of_face(index),
        )

    found = _seam_split_cylinders_joined(
        solid, found, named, surfaces, inside, reach, tolerance, cancelled=cancelled
    )
    found = _short_arcs_dropped(found, named, surfaces)
    found = _slots_instead_of_half_bores(
        solid,
        found,
        named,
        neighbours,
        reach,
        tolerance,
        surfaces,
        cancelled=cancelled,
    )
    found = _mouth_chamfers_folded(
        solid, found, named, surfaces, threads=covered, cancelled=cancelled
    )

    # **Ein Gewinde statt einer Handvoll Erfundener** — dieselbe Regel wie am
    # Netz, gemessen an den Kanten statt an der Konzentration der Dreiecke
    # (``brep.thread``, P2.5). Was auf der Wendel liegt, ist kein Zapfen und
    # kein Kegel; die Züge selbst verändern den Körper nicht.
    from app.core.brep.thread import thread_features
    from app.core.perceive.features import without_phantoms_on

    threads = (
        list(known_threads)
        if known_threads is not None
        else thread_features(solid, cancelled=cancelled)
    )
    for thread in threads:
        found = without_phantoms_on(found, thread.face_indices)
        found[thread.id] = thread
        counts["thread"] = counts.get("thread", 0) + 1
    found = _through_answered(found, neighbours, tolerance, cancelled=cancelled)

    # Der offene Mantel hat an beiden Kernen denselben Randvertrag. Die
    # Dreiecksnummern der Tessellierung sind bereits die Merkmalsnummern.
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import fit_cylinder
    from app.core.perceive.slots import open_slots_instead_of_fillets

    mesh = as_mesh_data(solid)
    fillets = []
    for feature in found.values():
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if feature.kind == "fillet" and feature.params.get("recess"):
            patch = list(feature.face_indices)
            fit = fit_cylinder(
                mesh.raw, patch, check_cancelled=cancelled.raise_if_cancelled if cancelled else None
            )
            if fit is not None:
                fillets.append((fit, patch))
    if fillets:
        found = open_slots_instead_of_fillets(mesh, found, fillets)

    found = _joined_tori(found, mesh, cancelled=cancelled)

    # **Viele gleiche Zellen sind auch am exakten Körper ein Muster** (RM-504).
    # Dieselbe Frage wie am Netz (``perceive.patterns``), an denselben
    # Dreiecken der Tessellierung und mit denselben Schwellen: Eine Wabenplatte
    # aus STEP hatte sonst 90 Flächen, ihr Netzzwilling ein Muster, und der Weg
    # zu den Musterhandlungen führte über *Flächenbearbeitung beenden*. Wie am
    # Netz nach dem Langloch und vor den freien Rundungen — deren Dreiecke
    # wären sonst vergeben, bevor die Zellwände einer Welle gezählt sind.
    from app.core.perceive.patterns import patterns_instead_of_cells

    found = patterns_instead_of_cells(
        mesh, found, check_cancelled=cancelled.raise_if_cancelled if cancelled else None
    )

    from app.core.perceive.features import detect_curved_faces, voids_instead_of_phantom_bores

    # Die Restflächen teilen die fachliche Glättungs- und Innenseitenprüfung
    # mit dem Netz. Vollständige native Flächen liefern ihre exakten Integrale;
    # eine nur teilweise beanspruchte Fläche behält die Netzauskunft.
    for feature in detect_curved_faces(
        mesh, found, check_cancelled=cancelled.raise_if_cancelled if cancelled else None
    ):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        curved_patch = set(feature.face_indices)
        native = solid.faces_of_triangles(feature.face_indices)
        complete = {triangle for index in native for triangle in solid.triangles_of_face(index)}
        params = dict(feature.params)
        measure_sources = dict(feature.measure_sources)
        if complete == curved_patch:
            measured = [solid.face_properties(index, cancelled=cancelled) for index in native]
            area = sum(item.mass for item in measured)
            if area > EPS_GEOM:
                params["area"] = area
                params["centre"] = tuple(
                    sum(item.mass * item.centre[coordinate] for item in measured) / area
                    for coordinate in range(3)
                )
                measure_sources.update(area="native", centre="native")
        found[feature.id] = replace(feature, params=params, measure_sources=measure_sources)

    found = voids_instead_of_phantom_bores(
        found,
        _void_features(solid, cancelled=cancelled),
        check_cancelled=cancelled.raise_if_cancelled if cancelled else None,
    )
    # **Eine Verengung ist am exakten Körper dieselbe wie am Netz** (R3): Die
    # Haltelippe einer Magnettasche öffnet sich zur Tasche hin. Gefragt wird an
    # den Dreiecken der Tessellierung, dieselbe Regel wie in ``detect``.
    from app.core.perceive.features import narrowings_marked

    found = narrowings_marked(
        mesh,
        found,
        source="native",
        check_cancelled=cancelled.raise_if_cancelled if cancelled else None,
    )

    # Erst die endgültigen Auswahlen schneiden die Originalteilträger zu:
    # Langloch, Ring und Luftkammer können mehrere unterschiedliche tragen.
    # Ein Netzfit darf denselben bereits nativ belegten Anteil nicht ersetzen.
    from app.core.perceive.surfaces import clipped_patches

    for identifier, feature in found.items():
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        native = solid.faces_of_triangles(feature.face_indices)
        patches = clipped_patches(
            [surface_patches[index] for index in sorted(native) if index in surface_patches],
            feature.face_indices,
            check_cancelled=cancelled.raise_if_cancelled if cancelled else None,
        )
        covered = {index for patch in patches for index in patch.face_indices}
        remaining = clipped_patches(
            feature.surface_patches,
            set(feature.face_indices) - covered,
            check_cancelled=cancelled.raise_if_cancelled if cancelled else None,
        )
        found[identifier] = replace(feature, surface_patches=patches + remaining)

    # Ein offenes Langloch kam über den Netzweg; was seine nativen Träger
    # belegen — Bogenradius, Achse, Flankenrichtung —, heißt jetzt auch so.
    from app.core.perceive.slots import native_open_slot_measures

    for identifier, feature in found.items():
        if feature.kind == "slot" and feature.params.get("open"):
            found[identifier] = native_open_slot_measures(feature)

    if cancelled is not None:
        cancelled.raise_if_cancelled()

    _log.info(
        "read %d hole(s), %d pin(s), %d fillet(s), %d face(s) and %d thread(s) off a B-Rep body",
        counts["hole"],
        counts["pin"],
        counts["fillet"],
        counts["face"],
        counts.get("thread", 0),
    )
    return found


def _native_patch(
    solid: Solid, index: int, surface: Surface | None, *, cancelled: CancelToken | None = None
) -> SurfacePatch | None:
    """Die bereits gelesene Originalfläche liefert den Träger, nie ihre Auswahlmitte."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone

    from app.core.perceive.surfaces import valid_patch

    params: dict[str, float | Vec3]
    kind: SurfaceKind
    if isinstance(surface, PlaneSurface):
        kind = "plane"
        params = {"centre": surface.plane.Location().Coord(), "axis": surface.normal}
    elif isinstance(surface, CylinderSurface):
        kind = "cylinder"
        params = {
            "centre": surface.cylinder.Location().Coord(),
            "axis": surface.cylinder.Axis().Direction().Coord(),
            "radius": float(surface.cylinder.Radius()),
        }
    elif isinstance(surface, SphereSurface):
        kind = "sphere"
        params = {
            "centre": surface.sphere.Location().Coord(),
            "radius": float(surface.sphere.Radius()),
        }
    elif isinstance(surface, TorusSurface):
        kind = "torus"
        params = {
            "centre": surface.torus.Location().Coord(),
            "axis": surface.torus.Axis().Direction().Coord(),
            "ring_radius": float(surface.torus.MajorRadius()),
            "tube_radius": float(surface.torus.MinorRadius()),
        }
    elif isinstance(surface, ConeSurface):
        # Der rationale Kegel (P2.3): Spitze, Achse in die belegte Nappe und
        # Halbwinkel — dieselben drei Auskünfte wie am nativen darunter.
        kind = "cone"
        params = {"apex": surface.apex, "axis": surface.axis, "half_angle": surface.half_angle}
    else:
        adaptor = BRepAdaptor_Surface(solid.faces()[index])
        if adaptor.GetType() != GeomAbs_Cone:
            return None
        span = _cone_nappe(adaptor, cancelled=cancelled)
        if span is None:
            return None
        direction, _, _ = span
        cone = adaptor.Cone()
        angle = float(cone.SemiAngle())
        kind = "cone"
        axis = cone.Axis().Direction()
        params = {
            "apex": cone.Apex().Coord(),
            "axis": (direction * axis.X(), direction * axis.Y(), direction * axis.Z()),
            "half_angle": abs(angle),
        }
    patch = SurfacePatch(kind, params, solid.triangles_of_face(index), "native")
    return (
        patch
        if valid_patch(
            patch,
            face_count=solid.triangle_count,
            check_cancelled=cancelled.raise_if_cancelled if cancelled else None,
        )
        else None
    )


def _cone_nappe(
    adaptor: Any, *, cancelled: CancelToken | None = None
) -> tuple[float, float, float] | None:
    """Richtung, weiter V-Rand und Radius einer vollständig belegten Kegelnappe.

    Der native Träger setzt sich jenseits seiner Spitze fort. Das Vorzeichen
    des Halbwinkels allein benennt deshalb weder die gewählte Nappe noch den
    weiten Rand. Eine Trimmung über beide Nappen bleibt ohne eindeutigen Bezug.
    """
    cone = adaptor.Cone()
    angle = float(cone.SemiAngle())
    radius = float(cone.RefRadius())
    first, last = float(adaptor.FirstVParameter()), float(adaptor.LastVParameter())
    if not all(math.isfinite(value) for value in (angle, radius, first, last)):
        return None
    sine = math.sin(angle)
    first_radius = math.fsum((radius, first * sine))
    last_radius = math.fsum((radius, last * sine))
    if min(first_radius, last_radius) < 0.0 < max(first_radius, last_radius):
        near_v, near_radius = min(
            ((first, first_radius), (last, last_radius)), key=lambda item: abs(item[1])
        )
        # Native Spitzenparameter und sin() sind bereits gerundete Werte.
        # Nur ihre arithmetische Endpunktklammer darf null enthalten, und
        # zusätzlich muss der Originalrand topologisch die Spitze sein.
        # Eine EPS_GEOM-breite Typentscheidung würde echte kleine Nappen löschen.
        rounding = math.fsum(
            (
                math.ulp(radius),
                abs(near_v) * math.ulp(sine),
                abs(sine) * math.ulp(near_v),
                math.ulp(near_v * sine),
            )
        )
        if abs(near_radius) > rounding or not _cone_apex_end(
            adaptor, near_v, rounding / abs(sine), cancelled=cancelled
        ):
            return None
    wide_v, wide_radius = max(
        ((first, first_radius), (last, last_radius)), key=lambda item: abs(item[1])
    )
    if abs(wide_radius) <= EPS_GEOM:
        return None
    direction = (1.0 if angle > 0.0 else -1.0) * (1.0 if wide_radius > 0.0 else -1.0)
    return direction, wide_v, abs(wide_radius)


def _cone_apex_end(
    adaptor: Any, value: float, rounding: float, *, cancelled: CancelToken | None
) -> bool:
    """Nur ein degenerierter Originalrand mit wirklichem Spitzenknoten belegt das Ende."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    face = adaptor.Face()
    apex = adaptor.Cone().Apex().Coord()
    edges = TopExp_Explorer(face, TopAbs_EDGE)
    while edges.More():
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        edge = TopoDS.Edge(edges.Current())
        edges.Next()
        if not BRep_Tool.Degenerated_s(edge):
            continue
        _, _, first, last = BRepTools.UVBounds_s(face, edge)
        if any(abs(at - value) > math.ulp(at) + math.ulp(value) for at in (first, last)):
            continue
        vertices = TopExp_Explorer(edge, TopAbs_VERTEX)
        at_apex = vertices.More()
        while vertices.More():
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            point = BRep_Tool.Pnt_s(TopoDS.Vertex(vertices.Current())).Coord()
            position_rounding = rounding + math.fsum(
                math.ulp(actual) + math.ulp(expected)
                for actual, expected in zip(point, apex, strict=True)
            )
            if math.dist(point, apex) > position_rounding:
                at_apex = False
                break
            vertices.Next()
        if at_apex:
            return True
    return False


def _joined_tori(
    found: dict[FeatureId, Feature], mesh: Any, *, cancelled: CancelToken | None = None
) -> dict[FeatureId, Feature]:
    """Angrenzende Teilflächen desselben exakten Rings bilden eine einzige Auswahl.

    Geometrische Gleichheit allein verbindet keine getrennten Ringstücke.
    Die tatsächliche Tessellierungsnachbarschaft belegt zusätzlich den Anschluss.
    """
    import numpy as np

    rings = {name: feature for name, feature in found.items() if feature.kind == "torus"}
    if len(rings) < 2:
        return found
    owners = {index: name for name, feature in rings.items() for index in feature.face_indices}
    graph: dict[FeatureId, set[FeatureId]] = {name: set() for name in rings}
    pairs = set()
    for first, second in mesh.raw.face_adjacency:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        left, right = owners.get(int(first)), owners.get(int(second))
        if left is None or right is None or left == right:
            continue
        pairs.add(tuple(sorted((left, right))))
    for left, right in sorted(pairs):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        one, two = rings[left].params, rings[right].params
        if one["recess"] is not two["recess"]:
            continue
        if any(
            abs(float(one[key]) - float(two[key])) > EPS_GEOM
            for key in ("diameter", "tube_diameter")
        ):
            continue
        if any(
            float(np.linalg.norm(np.asarray(one[key]) - np.asarray(two[key]))) > EPS_GEOM
            for key in ("centre", "axis")
        ):
            continue
        graph[left].add(right)
        graph[right].add(left)
    result = dict(found)
    unseen = set(rings)
    for name, feature in rings.items():
        if name not in unseen:
            continue
        group, pending = set(), [name]
        while pending:
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            current = pending.pop()
            if current not in unseen:
                continue
            unseen.remove(current)
            group.add(current)
            pending.extend(graph[current])
        for member in group:
            del result[member]
        result[name] = replace(
            feature,
            face_indices=tuple(
                sorted({index for member in group for index in rings[member].face_indices})
            ),
        )
    return result


def _void_features(solid: Solid, *, cancelled: CancelToken | None = None) -> list[Feature]:
    """Geschlossene Luftkammern mit allen Grenzflächen, auch an Materialinseln.

    Die Orientierung der kopierten Innenschale bestimmt die private positive
    Messform. Weitere Materialkörper werden davon abgezogen. Die gespeicherte
    Form bleibt unverändert; Builderhistorie belegt jede ausgewählte Quellfläche.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy, BRepBuilderAPI_MakeSolid
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepClass3d import BRepClass3d, BRepClass3d_SolidClassifier
    from OCP.BRepLib import BRepLib
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE, TopAbs_OUT, TopAbs_SHELL, TopAbs_SOLID
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from app.core.errors import (
        CANCEL,
        CORRECT_INPUT,
        PROGRAMMING_ERRORS,
        GeometryError,
        OperationCancelled,
    )
    from app.i18n import _

    def check() -> None:
        """Abbruch vor und nach jedem nativen Arbeitsschritt beachten."""
        if cancelled is not None:
            cancelled.raise_if_cancelled()

    def mapped(shape: Any, kind: Any) -> Any:
        """Unveränderte Unterformen einmal über ihre nativen Identitäten lesen."""
        check()
        result = ShapeMap()
        TopExp.MapShapes_s(shape, kind, result)
        check()
        return result

    check()
    bodies = mapped(solid.shape, TopAbs_SOLID)
    # **Ohne Innenschale keine Kammer** — und das ist der Normalfall. Die
    # Gültigkeitsprüfung darunter ging über den ganzen Körper, auch wenn jeder
    # Körper genau eine Schale hat: am Gewindebolzen M3 x 0,5 x 60 0,21 s je
    # Erkennung für eine Antwort, die die Schalenzahl schon gab (22.09.2026).
    if mapped(solid.shape, TopAbs_SHELL).Extent() <= bodies.Extent():
        return []
    if not bodies.Extent() or not solid.is_closed or not BRepCheck_Analyzer(solid.shape).IsValid():
        return []
    original_faces = solid.faces()
    measured: list[tuple[Vec3, Vec3, float, tuple[int, ...]]] = []
    seen: set[tuple[int, ...]] = set()
    try:
        for body_index in range(1, bodies.Extent() + 1):
            check()
            owner = TopoDS.Solid(bodies.FindKey(body_index))
            classifier = BRepClass3d_SolidClassifier(owner)
            classifier.PerformInfinitePoint(EPS_GEOM)
            check()
            if classifier.State() != TopAbs_OUT:
                continue
            outer = BRepClass3d.OuterShell_s(owner)
            if outer.IsNull():
                continue
            shells = mapped(owner, TopAbs_SHELL)
            for shell_index in range(1, shells.Extent() + 1):
                check()
                shell = TopoDS.Shell(shells.FindKey(shell_index))
                if shell.IsSame(outer):
                    continue
                shell_faces = mapped(shell, TopAbs_FACE)
                copy = BRepBuilderAPI_Copy(shell, True, False)
                check()
                positive = BRepBuilderAPI_MakeSolid(TopoDS.Shell(copy.Shape())).Solid()
                if not BRepLib.OrientClosedSolid_s(positive):
                    raise ValueError("The private cavity shell has no closed orientation")
                check()
                if not BRepCheck_Analyzer(positive).IsValid():
                    raise ValueError("The private cavity solid is invalid")
                # Auch eine geschlossene Kammer kann mehrere Grenzschalen haben:
                # eine Materialinsel gehört nicht zum gemeldeten Luftvolumen.
                cut = None
                air = positive
                if bodies.Extent() > 1:
                    cut = boolean_builder("difference", positive, solid.shape)
                    check()
                    cut.Build()
                    check()
                    if not cut.IsDone():
                        raise ValueError("The material inside a cavity could not be separated")
                    air = cut.Shape()
                air_bodies = mapped(air, TopAbs_SOLID)
                if not air_bodies.Extent() or not BRepCheck_Analyzer(air).IsValid():
                    raise ValueError("The resulting air region has no valid solid")
                for air_index in range(1, air_bodies.Extent() + 1):
                    check()
                    region = air_bodies.FindKey(air_index)
                    result_faces = mapped(region, TopAbs_FACE)
                    selected: list[int] = []
                    covered: set[int] = set()
                    for face_index, original in enumerate(original_faces):
                        check()
                        candidates = [original]
                        if shell_faces.Contains(original):
                            candidates.append(copy.ModifiedShape(original))
                        represented: set[int] = set()
                        for candidate in candidates:
                            if result_faces.Contains(candidate):
                                represented.add(result_faces.FindIndex(candidate))
                            if cut is not None:
                                for modified in listed(cut.Modified(candidate)):
                                    if result_faces.Contains(modified):
                                        represented.add(result_faces.FindIndex(modified))
                        if represented:
                            selected.append(face_index)
                            covered.update(represented)
                    if covered != set(range(1, result_faces.Extent() + 1)):
                        raise ValueError("The air boundary has no complete source-face history")
                    selection = tuple(selected)
                    # Eine Kammer in einer Insel ist auch aus der umgebenden
                    # Luftform erreichbar. Dieselben Quellflächen belegen sie
                    # erneut, nicht eine zweite Kammer am gleichen Ort.
                    if selection in seen:
                        continue
                    seen.add(selection)
                    volume = properties(region, "volume", cancelled=cancelled).mass
                    check()
                    bounds = Solid(region).bounds
                    check()
                    if volume <= 0.0:
                        raise ValueError("The air region has no positive volume")
                    measured.append((bounds.centre, bounds.size, volume, selection))
    except OperationCancelled:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:
        raise GeometryError(
            detail=_(
                "Die geschlossenen Innenflächen lassen sich nicht zuverlässig zuordnen. "
                "Prüfen Sie den Körper oder reparieren Sie eine Arbeitskopie."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        ) from problem
    found = []
    for number, (centre, size, volume, native_indices) in enumerate(sorted(measured), start=1):
        check()
        triangles = tuple(
            sorted(
                {
                    index
                    for face_index in native_indices
                    for index in solid.triangles_of_face(face_index)
                }
            )
        )
        found.append(
            Feature(
                id=f"void_{number}",
                kind="void",
                provenance="detected",
                params={"volume": volume, "centre": centre, "size": size},
                measure_sources=dict.fromkeys(("volume", "centre", "size"), "native"),
                face_indices=triangles,
            )
        )
    check()
    return found


def _slots_instead_of_half_bores(
    solid: Solid,
    found: dict[FeatureId, Feature],
    named: dict[int, FeatureId],
    neighbours: Any,
    reach: float,
    tolerance: float,
    surfaces: dict[int, Surface | None],
    *,
    cancelled: CancelToken | None = None,
) -> dict[FeatureId, Feature]:
    """Setzt zwei Halbzylinder und ihre zwei Flanken zu einem Langloch zusammen.

    **Dieselbe Aussage wie auf der Netzseite, nur billiger zu haben.** Dort
    muss :mod:`app.core.perceive.slots` am Netz messen, welche Dreiecke zum
    Mantel gehören und ob er zwischen den Bögen geschlossen ist; hier steht es
    in der Topologie. Ein Langloch ist danach genau das:

    * zwei zylindrische Flächen, jede weniger als eine volle Umdrehung, mit
      gleichem Radius und paralleler Achse, beide ins Loch gewölbt
      (``recess``),
    * die sich **genau zwei** ebene Nachbarflächen teilen — die Flanken —,
    * und diese beiden Ebenen grenzen ihrerseits an **beide** Bögen, stehen
      parallel zur Achse und je einen Radius neben ihr.

    Die dritte Bedingung ist die, auf die es ankommt. Zwei gleich große
    Verrundungen mit paralleler Achse gibt es an jeder verrundeten Kante eines
    Quaders, und eine Tasche mit vier verrundeten Ecken hat sie gleich viermal.
    Was ein Langloch daraus macht, ist der geschlossene Mantel: Zwei
    benachbarte Ecken einer Tasche teilen **eine** Wand, nicht zwei.

    Die Flanken gehen im Langloch auf, der **Boden** eines Sacklangloch nicht —
    seine Normale zeigt entlang der Achse, er liegt gar nicht im Mantel.
    Dieselbe Entscheidung und dieselbe Begründung wie bei
    :data:`app.core.perceive.slots.SWALLOWED_BY_A_SLOT`.

    **Gerechnet wird nur um die Bögen herum.** Gefragt wird die Nachbarschaft
    der Bögen und ihrer Nachbarn, nicht jeder Fläche des Körpers — ein
    STEP-Körper mit zweitausend Flächen hat davon meist keine zwei. Die
    Nachbarkarte selbst baut der Körper einmal (``Solid.face_neighbours``).
    """
    # Träge, wie jeder Import von ``brep`` nach ``perceive``
    # (``tests/test_core_package_direction.py``): Die Karte erlaubt die
    # Richtung nur im Funktionskörper.
    from app.core.perceive.slots import ACROSS_THE_AXIS

    faces = solid.faces()
    if len(faces) < 4:
        return found

    # Dieselben geprüften Träger wie bei der Einzelbeschreibung, ohne neue
    # Erkennung je Nachbarpaar und ohne eine andere Auslegung der UV-Parameter.
    surface_of = surfaces.__getitem__

    # Die Bögen: zylindrisch, angeschnitten, ins Loch gewölbt.
    arcs: list[int] = []
    for index, identifier in named.items():
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        feature = found.get(identifier)
        if feature is None or feature.kind != "fillet" or not feature.params.get("recess"):
            continue
        surface = surface_of(index)
        if not isinstance(surface, CylinderSurface):
            continue
        if surface.turn < _full_turn():
            arcs.append(index)
    if len(arcs) < 2:
        return found

    # Die Nachbarn einer Fläche kennt der Körper selbst, einmal gebaut
    # (``Solid.face_neighbours``) — nicht je Frage über einen Explorer.
    def neighbours_of(index: int) -> set[int]:
        return set(solid.face_neighbours(index))

    # Von den Nachbarn eines Bogens interessiert nur, was eine Flanke sein
    # kann: eine Ebene längs zur Achse. Deckel und Boden einer Platte grenzen
    # an **jedes** Loch darin und tragen entsprechend viele Kanten — ihre
    # Nachbarschaft zu bauen kostete an einer Platte mit 150 Löchern 85 ms je
    # Fläche (gemessen 11.09.2026), und gebraucht wird sie nie.
    around: dict[int, set[int]] = {}
    for index in arcs:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        around[index] = neighbours_of(index)
        cylinder = surface_of(index)
        assert isinstance(cylinder, CylinderSurface)
        axis = cylinder.cylinder.Axis().Direction()
        for other in around[index]:
            if other in around:
                continue
            surface = surface_of(other)
            if not isinstance(surface, PlaneSurface):
                continue
            if abs(surface.plane.Axis().Direction().Dot(axis)) >= ACROSS_THE_AXIS:
                continue
            around[other] = neighbours_of(other)

    # **Gepaart wird über die Nachbarschaft, nicht über alle Bögen.** Der
    # zweite Bogen eines Langlochs grenzt an dieselbe Flanke wie der erste —
    # er steht also zwei Schritte entfernt in der Nachbarschaft. Hundert Bögen
    # sind so hundert kleine Fragen und nicht fünftausend Paare (gemessen
    # 11.09.2026 an 306 Flächen: 1,6 s über alle Paare, 0,1 s so).
    used: set[int] = set()
    slots = 0
    for first in arcs:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if first in used:
            continue
        two_steps_away: set[int] = set()
        for neighbour in around.get(first, ()):
            two_steps_away |= around.get(neighbour, set())
        for second in arcs:
            if second == first or second in used or second not in two_steps_away:
                continue
            flanks = _flanks_of_a_slot(around, first, second, surface_of)
            if flanks is None:
                continue
            slots += 1
            found = _one_slot(
                solid,
                found,
                named,
                neighbours,
                reach,
                tolerance,
                faces=faces,
                arcs=(first, second),
                flanks=flanks,
                number=slots,
                surface_of=surface_of,
                cancelled=cancelled,
            )
            used.update({first, second, *flanks})
            break
    return found


def _seam_split_cylinders_joined(
    solid: Solid,
    found: dict[FeatureId, Feature],
    named: dict[int, FeatureId],
    surfaces: dict[int, Surface | None],
    inside: Any,
    reach: float,
    tolerance: float,
    *,
    cancelled: CancelToken | None = None,
) -> dict[FeatureId, Feature]:
    """Ein Mantel, den eine Naht in zwei Flächen teilt, ist **ein** Merkmal.

    OpenCASCADE legt die Naht eines Zylinders dorthin, wo seine Parametrisierung
    beginnt; schneidet eine zweite Bohrung den Mantel an, bleiben von der
    ersten zwei Flächen zu je 157,5 Grad, obwohl der Träger 315 Grad überdeckt
    (P1.5, Gegenfall 2). Je Fläche gelesen wären das zwei Verrundungen — und am
    Netz, das keine Naht kennt, eine angeschnittene Bohrung.

    Zusammengeführt werden zwei zylindrische Nachbarflächen mit **derselben
    Achslinie**, demselben Radius und derselben Materialseite, die sich eine
    Kante teilen. Der gemeinsame Umfang entscheidet dann wie an einer einzelnen
    Fläche: Verrundung unter :func:`_full_turn`, sonst Bohrung oder Zapfen, mit
    ``partial`` unter der vollen Umdrehung. Der Träger bleibt je Fläche
    erhalten — der Zuschnitt am Ende von :func:`features_of` liest ihn von den
    nativen Flächen ab.

    **Umfang und Länge sind Vereinigungen, keine Summen.** Die geteilte Kante
    kann längs der Achse laufen (die Naht: die Winkel ergänzen sich) oder
    quer dazu (ein Mantel, den eine Vereinigung ohne Zusammenlegen der
    Flächen in drei Stücke schnitt: die Winkel decken sich, die Längen
    ergänzen sich). Am verrundeten Kreuz aus ``test_brep`` wurden drei
    kollineare Viertelmäntel mit summierten Winkeln zu einer „radialen"
    Verrundung von 270 Grad; gemeint war ein Viertelmantel von 34 mm.
    :func:`_cylinder_group_extent` misst deshalb beides im Rahmen der
    ersten Fläche und vereinigt Bögen und Spannen.
    """
    from app.core.perceive.features import MIN_ROUND_ARC
    from app.core.perceive.slots import PARALLEL_AXES, SAME_RADIUS

    cylinders = [
        index
        for index, surface in surfaces.items()
        if isinstance(surface, CylinderSurface)
        and named.get(index) in found
        and found[named[index]].kind in ("fillet", "hole", "pin")
    ]
    if len(cylinders) < 2:
        return found
    faces = solid.faces()
    candidates = set(cylinders)

    def same_line(one: Any, other: Any) -> bool:
        axis, second = one.Axis().Direction(), other.Axis().Direction()
        if abs(axis.Dot(second)) < PARALLEL_AXES:
            return False
        radius = max(float(one.Radius()), float(other.Radius()))
        if abs(float(one.Radius()) - float(other.Radius())) > radius * SAME_RADIUS:
            return False
        return _plane_free_distance(one.Axis().Location(), other) <= tolerance

    groups: list[list[int]] = []
    seen: set[int] = set()
    for index in cylinders:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if index in seen:
            continue
        group = [index]
        seen.add(index)
        frontier = [index]
        while frontier:
            current = frontier.pop()
            surface = surfaces[current]
            assert isinstance(surface, CylinderSurface)
            for other in sorted(solid.face_neighbours(current)):
                if other in seen or other not in candidates:
                    continue
                candidate = surfaces[other]
                assert isinstance(candidate, CylinderSurface)
                if candidate.inward != surface.inward or not same_line(
                    surface.cylinder, candidate.cylinder
                ):
                    continue
                seen.add(other)
                group.append(other)
                frontier.append(other)
        if len(group) > 1:
            groups.append(sorted(group))

    for group in groups:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        first = surfaces[group[0]]
        assert isinstance(first, CylinderSurface)
        cylinder = first.cylinder
        turn, low, high = _cylinder_group_extent(solid, group, surfaces)
        if turn < math.radians(MIN_ROUND_ARC):
            # Auch zusammen zu wenig Bogen (RM-210): keine Rundform, und die
            # Stücke bleiben Oberfläche wie in :func:`_short_arcs_dropped`.
            for index in group:
                found.pop(named.pop(index), None)
            continue
        radius = float(cylinder.Radius())
        axis = cylinder.Axis().Direction()
        depth = high - low
        indices: list[int] = []
        weight = 0.0
        middle = [0.0, 0.0, 0.0]
        for index in group:
            indices.extend(solid.triangles_of_face(index))
            found.pop(named[index], None)
            props = solid.face_properties(index, cancelled=cancelled)
            weight += props.mass
            for axis_number in range(3):
                middle[axis_number] += props.mass * props.centre[axis_number]
        if weight <= EPS_GEOM:
            continue
        # Die Innenprobe braucht die Höhe der Fläche. Die veröffentlichte
        # Mitte liegt dagegen wie beim Netzfit auf der begrenzten Achse.
        surface_middle: Vec3 = (middle[0] / weight, middle[1] / weight, middle[2] / weight)
        if turn < _full_turn():
            kind: FeatureKind = "fillet"
            params: dict[str, Any] = {
                "radius": radius,
                "diameter": radius * 2.0,
                "centre": _axis_point(cylinder, (low + high) / 2.0),
                "axis": _oriented(axis),
                "length": depth,
                "recess": first.inward
                if turn >= math.pi - EPS_GEOM
                else not _axis_in_material(inside, cylinder, gp_point(surface_middle)),
                **({"radial": True} if turn >= math.pi - EPS_GEOM else {}),
            }
        else:
            kind = "hole" if first.inward else "pin"
            params = {
                "diameter": radius * 2.0,
                "centre": _axis_point(cylinder, (low + high) / 2.0),
                "axis": _oriented(axis),
                "depth": depth,
            }
            if first.inward:
                params["through"] = _ThroughQuestion(
                    faces[group[0]], cylinder, low - reach, high + reach
                )
                if turn < math.tau - EPS_GEOM:
                    params["partial"] = True
        number = 1 + max(
            (
                int(identifier.rsplit("_", 1)[-1])
                for identifier in found
                if identifier.startswith(f"{kind}_")
            ),
            default=0,
        )
        identifier = f"{kind}_{number}"
        for index in group:
            named[index] = identifier
        found[identifier] = Feature(
            id=identifier,
            kind=kind,
            provenance="detected",
            params=params,
            measure_sources={
                name: "native"
                for name, value in params.items()
                if not isinstance(value, (bool, _ThroughQuestion))
            },
            face_indices=tuple(sorted(indices)),
        )
    return found


def _short_arcs_dropped(
    found: dict[FeatureId, Feature],
    named: dict[int, FeatureId],
    surfaces: dict[int, Surface | None],
) -> dict[FeatureId, Feature]:
    """Einzelne Zylinderstücke unter dem Mindestbogen sind keine Verrundung (RM-210).

    **Dieselbe Schranke wie am Netz** (:data:`app.core.perceive.features.MIN_ROUND_ARC`,
    Entscheidung Robert vom 23.09.2026): Eine Rundform, die weniger als fünf
    Grad ihres Kreises zeigt, ist eine Kante. Am exakten Körper ist ihr Radius
    zwar kein Schätzwert, aber der Steckbrief darf nicht am Dateiformat hängen:
    Dasselbe Teil als STL meldete die Rundung nicht, als STEP schon.

    Gefragt wird **nach** :func:`_seam_split_cylinders_joined`: Ein schmales
    Stück, das eine Naht oder ein Schnitt von einem Mantel abtrennt, gehört zu
    diesem und zählt dort mit. Was hier wegfällt, stand allein — ein Merkmal
    aus genau einer Fläche. Seine Dreiecke bleiben Oberfläche, und die
    Restflächen am Ende von :func:`features_of` lesen sie wie am Netz.
    """
    from app.core.perceive.features import MIN_ROUND_ARC

    least_turn = math.radians(MIN_ROUND_ARC)
    faces_of: dict[FeatureId, list[int]] = {}
    for index, identifier in named.items():
        faces_of.setdefault(identifier, []).append(index)
    kept = dict(found)
    for identifier, indices in faces_of.items():
        feature = kept.get(identifier)
        if feature is None or feature.kind != "fillet" or len(indices) != 1:
            continue
        surface = surfaces.get(indices[0])
        if isinstance(surface, CylinderSurface) and surface.turn < least_turn:
            del kept[identifier]
            del named[indices[0]]
    return kept


def _cylinder_group_extent(
    solid: Solid, group: list[int], surfaces: dict[int, Surface | None]
) -> tuple[float, float, float]:
    """Winkelabdeckung und axiale Spanne koaxialer Flächen im Rahmen der ersten.

    Der Bogen jeder Fläche kommt aus den Winkeln ihrer Tessellationspunkte um
    die gemeinsame Achse: Sie liegen auf dem Mantel, und die äußersten liegen
    auf den Randkanten — der Bogen ist das Komplement der größten Lücke
    zwischen ihnen, damit eine Naht bei null Grad ihn nicht in zwei Hälften
    reißt. Die Bögen werden als Vereinigung modulo einer Umdrehung gezählt;
    zwei Nahthälften ergänzen sich, drei kollineare Stücke decken sich. Die
    axiale Spanne ist die Vereinigung der Parameterspannen, jede um den
    Versatz ihres Trägerursprungs längs der gemeinsamen Achse verschoben.

    Rückgabe: Bogen im Bogenmaß, unterer und oberer Achsparameter — beide ab
    dem Ursprung des ersten Trägers gemessen, so dass :func:`_axis_point` und
    :func:`_axis_covered` sie unmittelbar lesen.
    """
    import numpy as np

    first = surfaces[group[0]]
    assert isinstance(first, CylinderSurface)
    frame = first.cylinder.Position()
    origin = np.asarray(frame.Location().Coord(), dtype=float)
    direction = np.asarray(frame.Direction().Coord(), dtype=float)
    across = np.asarray(frame.XDirection().Coord(), dtype=float)
    upward = np.asarray(frame.YDirection().Coord(), dtype=float)
    vertices = np.asarray(solid.mesh.raw.vertices, dtype=float)
    triangles = np.asarray(solid.mesh.raw.faces, dtype=int)

    arcs: list[tuple[float, float]] = []
    low = math.inf
    high = -math.inf
    for index in group:
        surface = surfaces[index]
        assert isinstance(surface, CylinderSurface)
        own = surface.cylinder.Position()
        offset = float(np.dot(np.asarray(own.Location().Coord(), dtype=float) - origin, direction))
        forward = float(np.dot(np.asarray(own.Direction().Coord(), dtype=float), direction)) > 0.0
        ends = (
            (offset + surface.first, offset + surface.last)
            if forward
            else (offset - surface.last, offset - surface.first)
        )
        low = min(low, *ends)
        high = max(high, *ends)

        corners = vertices[np.unique(triangles[list(solid.triangles_of_face(index))].ravel())]
        relative = corners - origin
        angles = np.sort(np.arctan2(relative @ upward, relative @ across) % math.tau)
        if angles.size < 2:
            continue
        gaps = np.diff(np.append(angles, angles[0] + math.tau))
        widest = int(np.argmax(gaps))
        start = float(angles[(widest + 1) % angles.size])
        arcs.append((start, math.tau - float(gaps[widest])))

    # Jeder Bogen einmal so und einmal um eine Umdrehung zurückgeschoben:
    # Dann liegt, was über null Grad hinausreicht, neben dem, was dort beginnt.
    pieces = sorted(
        (start + shift, start + shift + width)
        for start, width in arcs
        for shift in (0.0, -math.tau)
    )
    merged: list[list[float]] = []
    for begin, end in pieces:
        if merged and begin <= merged[-1][1] + EPS_GEOM:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([begin, end])
    turn = sum(max(0.0, min(end, math.tau) - max(begin, 0.0)) for begin, end in merged)
    return min(turn, math.tau), low, high


def _plane_free_distance(point: Any, cylinder: Any) -> float:
    """Der Abstand eines Punkts von der Achslinie eines Zylinders."""
    axis = cylinder.Axis()
    origin, direction = axis.Location(), axis.Direction()
    offset = (point.X() - origin.X(), point.Y() - origin.Y(), point.Z() - origin.Z())
    along = offset[0] * direction.X() + offset[1] * direction.Y() + offset[2] * direction.Z()
    lateral = (
        offset[0] - along * direction.X(),
        offset[1] - along * direction.Y(),
        offset[2] - along * direction.Z(),
    )
    return math.sqrt(sum(value * value for value in lateral))


def gp_point(centre: Vec3) -> Any:
    """Ein OCCT-Punkt aus einem Tupel — für die Materialprobe an der Achse."""
    from OCP.gp import gp_Pnt

    return gp_Pnt(*centre)


def _mouth_chamfers_folded(
    solid: Solid,
    found: dict[FeatureId, Feature],
    named: dict[int, FeatureId],
    surfaces: dict[int, Surface | None],
    *,
    threads: Collection[int] = (),
    cancelled: CancelToken | None = None,
) -> dict[FeatureId, Feature]:
    """Die Mündungsfase eines Langlochs geht im Langloch auf — wie am Netz.

    **Dieselbe Zugehörigkeit an beiden Kernen** (P1.5, 20.09.2026). Das Netz
    nimmt seit dem 15.09.2026 ein Kegelstück unter dem vollen Umlauf, das an
    den Mantel eines Langlochs grenzt, in dessen Auswahl auf
    (``perceive.features._partial_cones_folded``); hier standen dieselben
    zwei Halbkegel als ``cone`` mit ``partial`` daneben, und die zwei schrägen
    ebenen Flanken der Fase als Flächen. Ein gefastes Langloch war damit am
    exakten Körper drei Merkmale mehr als am Netz — und jedes davon ohne
    Körperhandlung.

    Die Regel ist topologisch, nicht nach Kantenzahl oder Name:

    * Ein Teilkegel, der genau **ein** Langloch berührt, gehört zu dessen
      Mündung. Berührt er zwei, bleibt er, was er ist — welcher Öffnung er
      gehört, hat dann niemand belegt.
    * **Eine Fläche ohne Merkmal, die das Netz als Kegelstück liest**
      (``perceive.features.partial_cone_patch``), ist ebenso ein Teilkegel.
      Auf einer schrägen Fläche fast OpenCASCADE einen Bogen nicht als Kegel,
      sondern als BSpline-Fläche; die Erkennung zählte sie nirgends hin, und
      am Teppichclip (``carpet-corner-clip.step``) blieb die untere Fase beim
      Versetzen stehen (Durchsicht 0.5.1). Ob sie ein Kegelstück ist,
      entscheidet dieselbe Einpassung wie am Netz, an ihren Dreiecken; ihr
      Träger reist als eingepasster Kegel im Langloch mit.
    * Von den Teilkegeln aus wächst die Fase über Nachbarn, die ebenfalls an
      den Mantel grenzen und schräg zu dessen Achse stehen: eine ebene Fläche
      (die gerade Flanke) oder eine Fläche ohne Merkmal, deren Dreiecke alle
      schräg stehen — die Zwickel, mit denen OpenCASCADE Bogen und Flanke
      verbindet. Am Netz ist das das Band über freie, schräge Dreiecke
      (``perceive.features._mouth_flanks_folded``). Deckel und Boden stehen
      quer zur Achse, die Wände des Langlochs längs — beide sind keine.

    Die Träger bleiben: Kegel mit Spitze und Halbwinkel, Ebene mit Normale —
    der abschließende Zuschnitt in :func:`features_of` liest sie von den
    nativen Flächen ab. Maße des Langlochs bleiben die Nennmaße ohne Fase.
    ``threads`` sind die Flächen eines bekannten Gewindes: Sie tragen hier
    noch kein Merkmal und gehören trotzdem keiner Fase.
    """
    import numpy as np

    from app.core.perceive.features import partial_cone_patch
    from app.core.perceive.slots import ACROSS_THE_AXIS
    from app.core.units import exact_cos_degrees

    slots = {
        identifier: set(solid.faces_of_triangles(feature.face_indices))
        for identifier, feature in found.items()
        if feature.kind == "slot"
    }
    if not slots:
        return found
    cones = [
        index
        for index, identifier in named.items()
        if identifier in found
        and found[identifier].kind == "cone"
        and found[identifier].params.get("partial")
    ]
    # Welche Flächen schon ein Merkmal tragen, in einem Zug aus der Zuordnung
    # der Tessellation — nicht je Merkmal über :meth:`Solid.faces_of_triangles`,
    # das jede Dreiecksnummer einzeln prüft.
    sources = face_sources(solid.mesh)
    chosen = np.zeros(len(sources), dtype=bool)
    for feature in found.values():
        if feature.face_indices:
            chosen[np.asarray(feature.face_indices, dtype=np.intp)] = True
    owned = set(np.unique(sources[chosen]).tolist())
    loose = {index for index in surfaces if index not in owned and index not in threads}
    if not cones and not loose:
        return found

    def check() -> None:
        if cancelled is not None:
            cancelled.raise_if_cancelled()

    def owner_of(index: int) -> FeatureId | None:
        """Das eine Langloch, an dessen Mantel die Fläche grenzt — sonst ``None``."""
        beside = solid.face_neighbours(index)
        owners = [name for name, members in slots.items() if beside & members]
        return owners[0] if len(owners) == 1 else None

    def along_the_axis(normals: np.ndarray, axis: np.ndarray) -> np.ndarray:
        """|n·Achse| je Zeile, komponentenweise: Die Antwort entscheidet, welche
        Flächen zur Fase gehören, und entscheidet deshalb ohne BLAS (RM-187,
        ``.claude/rules/kern.md``) — wie die Fassung vor der Durchsicht 0.5.1."""
        rows = np.atleast_2d(np.asarray(normals, dtype=np.float64))
        along = rows[:, 0] * axis[0] + rows[:, 1] * axis[1] + rows[:, 2] * axis[2]
        return np.abs(np.asarray(along, dtype=np.float64))

    def tilted(along: np.ndarray) -> bool:
        """Ob alle Werte |n·Achse| schräg sind: weder Deckel (quer) noch Wand (längs)."""
        return bool(
            len(along) and np.all((along >= ACROSS_THE_AXIS) & (along < exact_cos_degrees(1.0)))
        )

    folded: dict[FeatureId, set[int]] = {}
    fitted: dict[FeatureId, list[SurfacePatch]] = {}
    for index in cones:
        check()
        name = owner_of(index)
        if name is not None:
            folded.setdefault(name, set()).add(index)
    for index in sorted(loose):
        check()
        name = owner_of(index)
        if name is None:
            continue
        patch = partial_cone_patch(
            solid.mesh,
            solid.triangles_of_face(index),
            check_cancelled=cancelled.raise_if_cancelled if cancelled is not None else None,
        )
        if patch is None:
            continue
        folded.setdefault(name, set()).add(index)
        fitted.setdefault(name, []).append(patch)
    if not folded:
        return found

    normals = np.asarray(solid.mesh.raw.face_normals, dtype=np.float64)
    for name, pieces in folded.items():
        check()
        slot = found[name]
        axis = np.asarray(slot.params["axis"], dtype=np.float64)
        members = slots[name]
        band = set(pieces)
        frontier = sorted(pieces)
        while frontier:
            check()
            following: set[int] = set()
            for piece in frontier:
                for index in sorted(solid.face_neighbours(piece)):
                    if index in members or index in band or index in following:
                        continue
                    if owner_of(index) != name:
                        continue
                    if index in loose:
                        triangles = np.asarray(solid.triangles_of_face(index), dtype=np.intp)
                        if tilted(along_the_axis(normals[triangles], axis)):
                            following.add(index)
                        continue
                    surface = surfaces.get(index)
                    identifier = named.get(index)
                    if (
                        isinstance(surface, PlaneSurface)
                        and identifier is not None
                        and identifier in found
                        and found[identifier].kind == "face"
                        and tilted(along_the_axis(np.asarray(surface.normal), axis))
                    ):
                        following.add(index)
            band.update(following)
            frontier = sorted(following)
        indices = set(slot.face_indices)
        for index in sorted(band):
            indices.update(solid.triangles_of_face(index))
            identifier = named.get(index)
            if identifier is not None:
                found.pop(identifier, None)
        # Nur die Auswahl wächst; Länge, Tiefe und Durchgang bleiben die
        # Nennmaße ohne die Fase — wie am Netz.
        found[name] = replace(
            slot,
            face_indices=tuple(sorted(indices)),
            surface_patches=slot.surface_patches + tuple(fitted.get(name, ())),
        )
    return found


def _flanks_of_a_slot(
    around: dict[int, set[int]],
    first: int,
    second: int,
    surface_of: Any,
) -> tuple[int, int] | None:
    """Die zwei Wände zwischen zwei Bögen — oder ``None``, wenn es keine sind."""
    from app.core.perceive.slots import ACROSS_THE_AXIS, PARALLEL_AXES, SAME_RADIUS

    one, other = surface_of(first).cylinder, surface_of(second).cylinder
    radius = max(float(one.Radius()), float(other.Radius()))
    if abs(one.Radius() - other.Radius()) > radius * SAME_RADIUS:
        return None
    axis, second_axis = one.Axis().Direction(), other.Axis().Direction()
    if abs(axis.Dot(second_axis)) < PARALLEL_AXES:
        return None
    # Zwei Mäntel auf **derselben** Achse sind eine Bohrung in zwei Stücken und
    # kein Langloch: Ohne Weg zwischen den Bogenmitten gibt es keine Flanken.
    # ``EPS_DISPLAY``, nicht ``match_tolerance``: Ein halbes Prozent der
    # Modelldiagonale wären an einer Platte 0,5 mm — und ein Langloch mit
    # 0,4 mm Weg ist eines, auch wenn niemand es so konstruiert.
    across = _across_between(one, other)
    span = math.sqrt(sum(value * value for value in across))
    if span <= EPS_DISPLAY:
        return None

    shared = around.get(first, set()) & around.get(second, set())
    flanks: list[int] = []
    for index in sorted(shared):
        surface = surface_of(index)
        if not isinstance(surface, PlaneSurface):
            continue
        plane = surface.plane
        normal = plane.Axis().Direction()
        # Eine Flanke steht **längs** zur Achse; Deckel und Boden stehen quer
        # und sind deshalb keine. Ohne diese Zeile zählte ein durchgehendes
        # Langloch vier gemeinsame Nachbarn statt zwei.
        if abs(normal.Dot(axis)) >= ACROSS_THE_AXIS:
            continue
        # **Und je einen Radius neben der Achse**, sonst ist die Ebene keine
        # Tangente, sondern eine Sekante — und der Bogen kein halber.
        if abs(_plane_distance(plane, one.Axis().Location()) - radius) > radius * SAME_RADIUS:
            continue
        flanks.append(index)
    if len(flanks) != 2:
        return None
    # **Und der Mantel ist geschlossen.** Beide Wände grenzen an beide Bögen —
    # zwei benachbarte Ecken einer verrundeten Tasche teilen nur eine Wand.
    for flank in flanks:
        if not {first, second} <= around.get(flank, set()):
            return None
    # Die zwei Wände stehen sich gegenüber.
    normals = [surface_of(flank).plane.Axis().Direction() for flank in flanks]
    if abs(normals[0].Dot(normals[1])) < PARALLEL_AXES:
        return None
    return (flanks[0], flanks[1])


def _across_between(one: Any, other: Any) -> tuple[float, float, float]:
    """Der Vektor von der ersten Bogenachse zur zweiten, quer zur Bohrrichtung.

    **Quer, und nicht einfach von Ursprung zu Ursprung.** Wo eine Zylinderfläche
    ihren Parameterursprung hat, entscheidet der Erzeuger; an einem aus einem
    Umriss aufgezogenen Langloch liegen beide auf einer Höhe, an einem
    eingelesenen STEP-Körper nicht unbedingt. Der Anteil entlang der Achse
    gehört deshalb nicht zum Weg.
    """
    first = one.Axis().Location()
    second = other.Axis().Location()
    axis = one.Axis().Direction()
    offset = (second.X() - first.X(), second.Y() - first.Y(), second.Z() - first.Z())
    along = offset[0] * axis.X() + offset[1] * axis.Y() + offset[2] * axis.Z()
    return (
        offset[0] - along * axis.X(),
        offset[1] - along * axis.Y(),
        offset[2] - along * axis.Z(),
    )


def _plane_distance(plane: Any, point: Any) -> float:
    """Der Abstand eines Punkts von einer Ebene, ohne Vorzeichen."""
    origin = plane.Location()
    normal = plane.Axis().Direction()
    return float(
        abs(
            (point.X() - origin.X()) * normal.X()
            + (point.Y() - origin.Y()) * normal.Y()
            + (point.Z() - origin.Z()) * normal.Z()
        )
    )


def _one_slot(
    solid: Solid,
    found: dict[FeatureId, Feature],
    named: dict[int, FeatureId],
    neighbours: Any,
    reach: float,
    tolerance: float,
    *,
    faces: list[Any],
    arcs: tuple[int, int],
    flanks: tuple[int, int],
    number: int,
    surface_of: Any,
    cancelled: CancelToken | None = None,
) -> dict[FeatureId, Feature]:
    """Baut das Langloch und nimmt die vier Flächen aus der Liste."""
    first, second = arcs
    one, other = surface_of(first).cylinder, surface_of(second).cylinder
    radius = (float(one.Radius()) + float(other.Radius())) / 2.0
    across = _across_between(one, other)
    travel = math.sqrt(sum(value * value for value in across))

    surface = surface_of(first)
    first_v, last_v = surface.first, surface.last
    depth = abs(last_v - first_v)
    # Die Mitte liegt auf halbem Weg zwischen den Achsen, auf halber Tiefe des
    # **ersten** Bogens — der zweite hat denselben Mantel, aber vielleicht
    # einen anderen Parameterursprung (siehe :func:`_across_between`).
    first_centre = _axis_point(one, (first_v + last_v) / 2.0)
    centre: Vec3 = (
        first_centre[0] + across[0] / 2.0,
        first_centre[1] + across[1] / 2.0,
        first_centre[2] + across[2] / 2.0,
    )
    # Auch die Richtung bekommt ihr Vorzeichen von ``positive_axis``: Ein
    # Langloch hat keine Vorder- und keine Rückseite, aber das Feld
    # *Richtung* zeigt eine Zahl, und die soll an beiden Kernen dieselbe sein
    # — nicht die, die von der Reihenfolge der zwei Bögen abhängt.
    direction = positive_axis((across[0] / travel, across[1] / travel, across[2] / travel))
    axis = one.Axis().Direction()

    through = not _axis_covered(
        neighbours,
        faces[first],
        one,
        first_v - reach,
        last_v + reach,
        tolerance,
        cancelled=cancelled,
    )

    identifier = f"slot_{number}"
    indices: list[int] = []
    for index in (first, second, *flanks):
        indices.extend(solid.triangles_of_face(index))
        name = named.get(index)
        if name is not None:
            found.pop(name, None)
    found[identifier] = Feature(
        id=identifier,
        kind="slot",
        provenance="detected",
        params={
            "diameter": radius * 2.0,
            "length": travel + radius * 2.0,
            "travel": travel,
            "axis": _oriented(axis),
            "direction": direction,
            "centre": centre,
            "depth": depth,
            "through": through,
        },
        measure_sources=dict.fromkeys(
            ("diameter", "length", "travel", "axis", "direction", "centre", "depth"), "native"
        ),
        face_indices=tuple(indices),
    )
    return found


def _describe(
    solid: Solid,
    face: Any,
    index: int,
    inside: Any,
    neighbours: Any,
    reach: float,
    *,
    surface: Surface | None,
    cancelled: CancelToken | None = None,
) -> tuple[FeatureKind, dict[str, Any]] | None:
    """Was diese Fläche ist, im Vokabular von §21.

    ``face`` ist die Fläche ``index`` von ``solid``; Maße und Träger kommen
    aus dessen Memo, damit dieselbe Fläche nicht je Frage neu integriert wird.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_REVERSED

    from app.core.perceive.features import MIN_ROUND_ARC

    # **Dieselbe Schranke wie am Netz** (RM-210, :func:`_short_arcs_dropped`):
    # Torus- und Kegelstücke unter dem Mindestbogen sind schon hier keine
    # Rundform. Ein Zylinderstück wird erst nach der Nahtzusammenführung
    # gefragt — ein schmaler Rest neben einem Mantel gehört zu diesem.
    least_turn = math.radians(MIN_ROUND_ARC)

    adaptor = BRepAdaptor_Surface(face)
    kind = adaptor.GetType()
    if surface is None and kind not in (GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus):
        return None
    props = solid.face_properties(index, cancelled=cancelled)
    area = props.mass
    if area <= EPS_GEOM:
        return None
    middle = props.centre
    centre = gp_Pnt(*middle)

    if isinstance(surface, PlaneSurface):
        return "face", {
            "area": area,
            "centre": middle,
            "normal": surface.normal,
        }

    if isinstance(surface, TorusSurface):
        # Der Bogen der Röhre läuft beim echten Torusträger in V; ein als Torus
        # erkannter Freiformträger hat keine solche Parameterlinie und bleibt,
        # wie er ist.
        if (
            kind == GeomAbs_Torus
            and abs(float(adaptor.LastVParameter() - adaptor.FirstVParameter())) < least_turn
        ):
            return None
        torus = surface.torus
        return "torus", {
            "diameter": float(torus.MajorRadius()) * 2.0,
            "tube_diameter": float(torus.MinorRadius()) * 2.0,
            "axis": _oriented(torus.Axis().Direction()),
            "centre": tuple(float(value) for value in torus.Location().Coord()),
            "recess": surface.inward,
        }

    if isinstance(surface, CylinderSurface):
        turn = surface.turn
        cylinder = surface.cylinder
        axis = cylinder.Axis().Direction()
        radius = float(cylinder.Radius())
        first_v, last_v = surface.first, surface.last
        depth = abs(last_v - first_v)
        # Innen und außen ergeben sich gemeinsam aus Flächenorientierung
        # und Händigkeit der Parametrisierung. Ein Kreisprisma kann auch
        # einen indirekten Zylinder tragen: REVERSED allein vertauscht dann
        # die Bohrung mit dem massiven Zapfen.
        hollow = surface.inward

        # **Ein Ausschnitt ist eine Verrundung, kein verworfener Rest.** Wer
        # weniger als eine volle Umdrehung abdeckt, war bis hierher nichts —
        # dabei steht sein Radius exakt in der Topologie, weil die Fläche so
        # konstruiert wurde. Auf der Netzseite muss ihn ``detect_fillets``
        # aus Normalen einpassen und über den Winkelbogen von einem Zapfen
        # trennen; hier ist beides schon entschieden. Dieselben Schlüssel wie
        # dort, nur ohne ``residual``: Es wurde nichts eingepasst.
        if turn < _full_turn():
            # **``recess`` kommt hier nicht aus der Orientierung.** Für einen
            # vollen Zylinder trennt ``REVERSED`` Loch von Zapfen zuverlässig;
            # für einen Ausschnitt tut es das nicht — an den vier gleichen
            # Außenkanten eines Quaders kam es zweimal so und zweimal anders
            # heraus. Gefragt ist ohnehin etwas Geometrisches: Liegt die Achse
            # im Material, ist es eine Verrundung, liegt sie außerhalb, eine
            # Kehle. Gemessen am umgekehrten T aus ``test_brep`` mit
            # verrundeten Kanten: 22 Verrundungen, 2 Kehlen an den
            # einspringenden Ecken — seit die Nahtzusammenführung die von der
            # Vereinigung zerschnittenen Mäntel wieder zu einem macht.
            # Mindestens halbe Mäntel sind radiale Wände: Ihre Achse kann
            # beiderseits im Hohlraum liegen. Dort zählt die Mantelnormale
            # einschließlich der Händigkeit des Zylinderrahmens.
            return "fillet", {
                "radius": radius,
                "diameter": radius * 2.0,
                "centre": _axis_point(cylinder, (first_v + last_v) / 2.0),
                "axis": _oriented(axis),
                "length": depth,
                "recess": hollow
                if turn >= math.pi - EPS_GEOM
                else not _axis_in_material(inside, cylinder, centre),
                **({"radial": True} if turn >= math.pi - EPS_GEOM else {}),
            }

        # **Der Mittelpunkt liegt auf der Achse, nicht im Flächenschwerpunkt.**
        # Ein Mantel, den eine schräge Fläche beschneidet, ist auf einer Seite
        # länger als auf der anderen, und sein Schwerpunkt wandert dorthin:
        # radial von der Achse weg und axial zur längeren Seite. An der
        # Teppichklammer (Datei 19 der Durchsicht vom 05.09.2026) lag er
        # 0,026 mm neben und 0,2 mm über der Achsmitte, und der Zylinder, den
        # ``edit.resize_bore`` daraus baute, war nicht koaxial zur Bohrung:
        # unten blieb ein Rest des alten Mantels stehen, oben stand er über,
        # und die Tessellation ging auf. Der Mantel nennt Achse und
        # Parameterspanne selbst; seine Mitte ist der Achspunkt in der Mitte
        # der Spanne — die Netzseite rechnet aus demselben Grund über die
        # Endringe (``perceive``: „Ein Zylindermittelpunkt kommt aus seinen
        # Endringen").
        params: dict[str, Any] = {
            # Der Kern behält das Topologiemaß in doppelter Genauigkeit.
            # Gerundet wird erst in Baum und Dialog: Eine Bearbeitung, die
            # daraus wieder einen exakten Zylinder baut, darf sonst einen
            # losen Ring oder eine hauchdünne alte Lippe erzeugen.
            "diameter": radius * 2.0,
            "centre": _axis_point(cylinder, (first_v + last_v) / 2.0),
            "axis": _oriented(axis),
            "depth": depth,
        }
        if hollow:
            # Dasselbe Wort wie auf der Netzseite, und der Steckbrief liest es
            # („Durchgang" oder „Sackloch"). Ohne den Schlüssel stand an jeder
            # exakten Bohrung „Sackloch", auch an einem Loch durch eine Platte.
            params["through"] = _ThroughQuestion(face, cylinder, first_v - reach, last_v + reach)
            # **Angeschnitten, nicht verworfen**: ein Mantel unter der vollen
            # Umdrehung ist eine Bohrung, die ein Nachbar geöffnet hat — eine
            # zweite Bohrung, ein Rand. Dasselbe Wort wie am Netz
            # (``perceive.features._partial_bores_marked``); ob sie für sich
            # bearbeitbar ist, sagt die Nachbarschaft (P1.5).
            if turn < math.tau - EPS_GEOM:
                params["partial"] = True
        return "hole" if hollow else "pin", params

    if isinstance(surface, ConeSurface):
        # **Derselbe Kegel als B-Spline** (P2.3): Manche Programme schreiben
        # jede Fläche als NURBS nach STEP, und eine Senkung oder ein
        # Kegelstumpf kam dann als gerundete Fläche ohne Maße in den Baum.
        # ``canonical`` hat den Träger an allen Bézier-Koeffizienten belegt;
        # die Maße sind die des nativen Zweigs darunter — Durchmesser und
        # Mitte am weiten Ende, Achse von der Spitze in die Nappe.
        axis = surface.axis
        wide = surface.far
        return "cone", {
            "diameter": 2.0 * wide * math.tan(surface.half_angle),
            "angle": math.degrees(surface.half_angle) * 2.0,
            "axis": axis,
            "centre": (
                surface.apex[0] + wide * axis[0],
                surface.apex[1] + wide * axis[1],
                surface.apex[2] + wide * axis[2],
            ),
            "recess": surface.inward,
            **({"partial": True} if surface.turn < _full_turn() else {}),
        }

    if kind == GeomAbs_Cone:
        span = _cone_nappe(adaptor, cancelled=cancelled)
        if span is None:
            return None
        direction, wide_v, radius = span
        cone = adaptor.Cone()
        angle = float(cone.SemiAngle())
        axis = cone.Axis().Direction()
        location = cone.Location()
        along = wide_v * math.cos(angle)
        turn = abs(adaptor.LastUParameter() - adaptor.FirstUParameter())
        if turn < least_turn:
            return None
        return "cone", {
            "diameter": 2.0 * radius,
            "angle": math.degrees(abs(angle)) * 2.0,
            "axis": (direction * axis.X(), direction * axis.Y(), direction * axis.Z()),
            "centre": (
                location.X() + along * axis.X(),
                location.Y() + along * axis.Y(),
                location.Z() + along * axis.Z(),
            ),
            # Spiegelung kehrt auch am Kegel die Flächenparametrisierung um;
            # die Materialseite folgt beiden Orientierungen gemeinsam.
            "recess": (face.Orientation() == TopAbs_REVERSED) == cone.Position().Direct(),
            **({"partial": True} if turn < _full_turn() else {}),
        }

    if isinstance(surface, SphereSurface):
        ball = surface.sphere
        radius = float(ball.Radius())
        hollow = surface.inward
        if _rounded_neighbours(solid, neighbours, face, cancelled=cancelled) >= CORNER_NEIGHBOURS:
            # **Als Verrundung, nicht als Kugel.** Was hier steht, ist die
            # Ecke, an der drei verrundete Kanten zusammentreffen. Sie ist
            # gerechnet ein Kugelstück und benannt eine Verrundung: „Kuppel
            # Ø4" an einer Quaderecke wäre richtig gerechnet und falsch
            # gesagt. Der Kunde sieht eine verrundete Ecke und will ihren
            # Radius. Keine Achse — eine Ecke hat keine.
            return "fillet", {
                "radius": radius,
                "diameter": radius * 2.0,
                "centre": tuple(float(value) for value in ball.Location().Coord()),
                "length": 0.0,
                "recess": hollow,
            }
        return "sphere", {
            "diameter": radius * 2.0,
            "centre": tuple(float(value) for value in ball.Location().Coord()),
            "recess": hollow,
        }

    return None


def _axis_point(cylinder: Any, along: float) -> Vec3:
    """Der Punkt bei einer gemessenen axialen Länge ab dem Trägerursprung."""
    origin = cylinder.Location()
    direction = cylinder.Axis().Direction()
    return (
        float(origin.X() + direction.X() * along),
        float(origin.Y() + direction.Y() * along),
        float(origin.Z() + direction.Z() * along),
    )


def _through_answered(
    found: dict[FeatureId, Feature],
    neighbours: Any,
    tolerance: float,
    *,
    cancelled: CancelToken | None = None,
) -> dict[FeatureId, Feature]:
    """Beantwortet die aufgeschobenen Fragen „durchgehend?" (:class:`_ThroughQuestion`).

    Erst hier, nach dem Gewinde: Was es als Phantom verdrängt hat, fragt
    niemand mehr. In der Reihenfolge der Kennungen, damit dieselbe Eingabe
    dieselben Fragen in derselben Folge stellt.
    """
    answered = dict(found)
    for identifier in sorted(found):
        feature = found[identifier]
        question = feature.params.get("through")
        if not isinstance(question, _ThroughQuestion):
            continue
        through = not _axis_covered(
            neighbours,
            question.face,
            question.cylinder,
            question.first,
            question.last,
            tolerance,
            cancelled=cancelled,
        )
        answered[identifier] = replace(feature, params={**feature.params, "through": through})
    return answered


def _axis_covered(
    neighbours: Any,
    face: Any,
    cylinder: Any,
    first: float,
    last: float,
    tolerance: float,
    *,
    cancelled: CancelToken | None = None,
) -> bool:
    """Reicht eine Nachbarfläche dieses Mantels in die Mündung — über die Achse
    oder über einen der zwei Ringe darin?

    Ein Sackloch endet an einer Fläche, die über der Achse liegt — ein ebener
    Boden, der Kegel einer Spitzenbohrung, die Kalotte eines Kugelfräsers —,
    und die stößt an den Mantel an. Bei einer Durchgangsbohrung stoßen nur
    Flächen an, in denen das Loch selbst liegt: Ihr Rand ist der Rand des
    Lochs, und der bleibt einen Radius von der Achse entfernt.

    **Nicht nur die Achse, die ganze Mündung** — dieselbe Frage wie im
    Netzzwilling (``perceive.features._is_through``, ``THROUGH_RINGS``,
    ``THROUGH_SAMPLES``): Die Aufweitung einer gesenkten Durchgangsbohrung
    (Ø 9 über Ø 5) hat über ihrer Achse nichts, und doch endet sie am
    Übergangskegel — der liegt über den Ringen. Am exakten Körper hieß sie
    bis zum 22.09.2026 ``through``, am Netz nicht (Kreuzbefund Paket C), und
    ``prepare_ops._exact_cavity_tool`` hätte mit dem Flag die ganze Zielhülle
    als Tiefe genommen. Die Ringe liegen innerhalb des Mantels, damit die
    eigene Wand nie zählt; die Achse bleibt die erste und billigste Probe.

    **Nachbarn, nicht der ganze Körper.** Der Netzzwilling zählt Dreiecke über
    der Mündung im Abschnitt der Bohrung; hier sagt es die Topologie: Der
    gegenüberliegende Schenkel eines U-Profils liegt zwar über der Achse,
    grenzt aber nicht an den Mantel — und die Bohrung im ersten Schenkel ist
    durchgehend.

    **Abstand, nicht Schnitt.** Der erste Versuch schnitt die Achse als Gerade
    mit jeder Nachbarfläche (``IntCurvesFace_Intersector``) und fand die
    Spitze eines Bohrkegels nicht: Sie ist in der Flächenparametrisierung ein
    entarteter Punkt, und der Schnitt meldet dort nichts. Der kleinste Abstand
    zwischen Achse und Fläche kennt diese Ausnahme nicht — eine Spitze ist ein
    Knoten der Fläche, und Knoten zählen mit. Gemessen an zehn Bauarten:
    Platte, Sackloch, Spitzenbohrung, schräger Austritt, zylindrische und
    kegelige Senkung, U-Profil, Kugelfräser, Kreuzbohrung, Stufenbohrung.
    """
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.gp import gp_Ax1, gp_Lin, gp_Pnt
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS_Compound

    # Träge, damit ``brep`` keine eifrige Kante zur Wahrnehmung bekommt.
    from app.core.perceive.features import THROUGH_RINGS, THROUGH_SAMPLES

    seen: list[Any] = []
    walk = TopExp_Explorer(face, TopAbs_EDGE)
    while walk.More():
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        edge = walk.Current()
        walk.Next()
        for other in listed(neighbours.FindFromKey(edge)):
            if other.IsSame(face) or any(other.IsSame(known) for known in seen):
                continue
            seen.append(other)
    if not seen:
        return False

    def assembled(shapes: Any) -> Any:
        """Ein Verbund, der nur liest — keine neue Geometrie, keine Kopie."""
        builder = BRep_Builder()
        compound = TopoDS_Compound()
        builder.MakeCompound(compound)
        for shape in shapes:
            builder.Add(compound, shape)
        return compound

    # **Ein Abstand je Probe, nicht je Probe und Nachbar.** Gefragt ist, ob
    # irgendeine der Linien irgendeinem Nachbarn auf ``tolerance`` nahekommt —
    # das ist der kleinste Abstand zwischen beiden Verbünden. Einzeln gefragt
    # waren es an einer Durchgangsbohrung 17 Linien mal jeder Nachbar, an
    # zwei Bohrungen des Teppichclips aus STEP 1,4 s (Review 22.09.2026).
    around = assembled(seen)

    def covered(lines: list[Any]) -> bool:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        probe = assembled(BRepBuilderAPI_MakeEdge(line, first, last).Edge() for line in lines)
        away = nearest_distance(probe, around)
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        return away is not None and away <= tolerance

    axis = cylinder.Axis()
    if covered([gp_Lin(axis)]):
        return True
    origin = cylinder.Location()
    direction = axis.Direction()
    across, along = cylinder.XAxis().Direction(), cylinder.YAxis().Direction()
    radius = float(cylinder.Radius())
    rings: list[Any] = []
    for share in THROUGH_RINGS:
        for sample in range(THROUGH_SAMPLES):
            angle = math.tau * sample / THROUGH_SAMPLES
            reach_x = radius * share * math.cos(angle)
            reach_y = radius * share * math.sin(angle)
            point = gp_Pnt(
                origin.X() + reach_x * across.X() + reach_y * along.X(),
                origin.Y() + reach_x * across.Y() + reach_y * along.Y(),
                origin.Z() + reach_x * across.Z() + reach_y * along.Z(),
            )
            rings.append(gp_Lin(gp_Ax1(point, direction)))
    return covered(rings)


def _axis_in_material(inside: Any, cylinder: Any, centre: Any) -> bool:
    """Liegt die Achse dieser Zylinderfläche im Körper?

    Nicht der Ursprung des Zylindersystems — der liegt irgendwo auf der Achse,
    bei einem Quader ab z=0 genau auf der Grundfläche, und der Klassierer
    antwortet dann ``ON`` statt ``IN``. Gefragt ist der Achsenpunkt **auf Höhe
    der Fläche**, also die Projektion ihres Schwerpunkts.
    """
    from OCP.gp import gp_Pnt

    origin = cylinder.Location()
    direction = cylinder.Axis().Direction()
    along = (
        (centre.X() - origin.X()) * direction.X()
        + (centre.Y() - origin.Y()) * direction.Y()
        + (centre.Z() - origin.Z()) * direction.Z()
    )
    return _point_in_material(
        inside,
        gp_Pnt(
            origin.X() + along * direction.X(),
            origin.Y() + along * direction.Y(),
            origin.Z() + along * direction.Z(),
        ),
    )


def _point_in_material(inside: Any, point: Any) -> bool:
    """Liegt dieser Punkt im Körper? Der Klassierer sagt es, einmal gebaut.

    Getrennt von der Achsenfrage, weil eine Kugel keine Achse hat: Dort ist der
    gefragte Punkt ihr Mittelpunkt, und der liegt bei einer Eckverrundung im
    Material, bei einer Pfanne in der Mulde davor.
    """
    from OCP.TopAbs import TopAbs_IN

    inside.Perform(point, EPS_GEOM)
    return bool(inside.State() == TopAbs_IN)


def _rounded_neighbours(
    solid: Solid, neighbours: Any, face: Any, *, cancelled: CancelToken | None = None
) -> int:
    """Wie viele Flächen an dieser hier grenzen und selbst Kantenverrundungen
    sind — zylindrisch und weniger als eine volle Umdrehung.

    Eine Fläche wird nur einmal gezählt, auch wenn sie über zwei Kanten
    anstößt; die Nachbarkarte gibt sie als nacktes Handle zurück, und
    ``Solid.face_index`` führt sie über ``IsSame`` auf ihre Nummer zurück —
    deren Träger das Memo des Körpers schon kennt.
    """
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    seen: set[int] = set()
    walk = TopExp_Explorer(face, TopAbs_EDGE)
    while walk.More():
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        edge = walk.Current()
        walk.Next()
        for other in listed(neighbours.FindFromKey(edge)):
            if other.IsSame(face):
                continue
            number = solid.face_index(other)
            if number >= 0:
                seen.add(number)

    rounded = 0
    for number in sorted(seen):
        surface = solid.surface(number, cancelled=cancelled)
        if not isinstance(surface, CylinderSurface):
            continue
        if surface.turn < _full_turn():
            rounded += 1
    return rounded
