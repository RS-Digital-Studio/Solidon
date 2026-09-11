"""Merkmale aus der Topologie (Bauplan §30, §21).

Auf einem Netz heißt ein Loch zu finden: Dreiecke gruppieren und einen
Zylinder hineinpassen — und ihm einen Namen zu geben, der die nächste
Operation überlebt, heißt gegen die vorigen Namen zuordnen (§21.2). Auf einem
B-Rep-Körper ist nichts davon nötig: eine zylindrische Fläche *ist* eine
zylindrische Fläche, und sie nennt ihren Radius und ihre Achse selbst.

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
from typing import Any

from app.core.brep.kernel import Solid
from app.core.log import get_logger
from app.core.types import Feature, FeatureId, FeatureKind, Vec3
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


#: Wie viel einer vollen Umdrehung eine zylindrische Fläche abdecken muss, um
#: als Bohrung zu zählen. Darunter ist sie eine Verrundung oder eine gerundete
#: Ecke, kein Loch.
FULL_TURN = 0.9

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


def features_of(solid: Solid) -> dict[FeatureId, Feature]:
    """Löcher und ebene Flächen, aus der Topologie abgelesen statt
    eingepasst.
    """
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp

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
    for index, face in enumerate(solid.faces()):
        described = _describe(face, index, inside, neighbours, reach, tolerance)
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
            # Eine Topologiefläche besteht im Viewport aus vielen Dreiecken.
            # Der nackte ``index`` gehört zur B-Rep-Flächenliste und wäre als
            # Dreiecksindex eine andere Zahl mit zufällig gültigem Bereich.
            face_indices=solid.triangles_of_face(index),
        )

    found = _slots_instead_of_half_bores(solid, found, named, neighbours, reach, tolerance)

    # Der offene Mantel hat an beiden Kernen denselben Randvertrag. Die
    # Dreiecksnummern der Tessellierung sind bereits die Merkmalsnummern.
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import fit_cylinder
    from app.core.perceive.slots import open_slots_instead_of_fillets

    mesh = as_mesh_data(solid)
    fillets = []
    for feature in found.values():
        if feature.kind == "fillet" and feature.params.get("recess"):
            patch = list(feature.face_indices)
            fit = fit_cylinder(mesh.raw, patch)
            if fit is not None:
                fillets.append((fit, patch))
    if fillets:
        found = open_slots_instead_of_fillets(mesh, found, fillets)

    _log.info(
        "read %d hole(s), %d pin(s), %d fillet(s) and %d face(s) off a B-Rep body",
        counts["hole"],
        counts["pin"],
        counts["fillet"],
        counts["face"],
    )
    return found


def _slots_instead_of_half_bores(
    solid: Solid,
    found: dict[FeatureId, Feature],
    named: dict[int, FeatureId],
    neighbours: Any,
    reach: float,
    tolerance: float,
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

    **Gerechnet wird nur um die Bögen herum.** Die Nachbarschaft wird für die
    Bögen und ihre Nachbarn gebaut, nicht für jede Fläche des Körpers — ein
    STEP-Körper mit zweitausend Flächen hat davon meist keine zwei.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.TopoDS import TopoDS

    # Träge, wie jeder Import von ``brep`` nach ``perceive``
    # (``tests/test_core_package_direction.py``): Die Karte erlaubt die
    # Richtung nur im Funktionskörper.
    from app.core.perceive.slots import ACROSS_THE_AXIS

    faces = solid.faces()
    if len(faces) < 4:
        return found

    # Einmal je Fläche und nicht einmal je Paar: Ein Adaptor kostet, und an
    # hundert Bögen fragt die Paarung unten jede Fläche viele Male.
    adaptors: dict[int, Any] = {}

    def surface_of(index: int) -> Any:
        adaptor = adaptors.get(index)
        if adaptor is None:
            adaptor = adaptors[index] = BRepAdaptor_Surface(TopoDS.Face(faces[index]))
        return adaptor

    # Die Bögen: zylindrisch, angeschnitten, ins Loch gewölbt.
    arcs: list[int] = []
    for index, identifier in named.items():
        feature = found.get(identifier)
        if feature is None or feature.kind != "fillet" or not feature.params.get("recess"):
            continue
        surface = surface_of(index)
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        turn = abs(surface.LastUParameter() - surface.FirstUParameter())
        if turn < FULL_TURN * 2.0 * math.pi:
            arcs.append(index)
    if len(arcs) < 2:
        return found

    # Die Nummer einer Fläche in ``faces`` — über dieselbe Karte, aus der
    # ``Solid.faces`` die Liste gebaut hat, in O(1) statt über einen
    # ``IsSame``-Vergleich mit jeder Fläche des Körpers.
    numbered = ShapeMap()
    for face in faces:
        numbered.Add(face)

    def neighbours_of(index: int) -> set[int]:
        return _neighbouring_faces(faces[index], neighbours, numbered)

    # Von den Nachbarn eines Bogens interessiert nur, was eine Flanke sein
    # kann: eine Ebene längs zur Achse. Deckel und Boden einer Platte grenzen
    # an **jedes** Loch darin und tragen entsprechend viele Kanten — ihre
    # Nachbarschaft zu bauen kostete an einer Platte mit 150 Löchern 85 ms je
    # Fläche (gemessen 11.09.2026), und gebraucht wird sie nie.
    around: dict[int, set[int]] = {}
    for index in arcs:
        around[index] = neighbours_of(index)
        axis = surface_of(index).Cylinder().Axis().Direction()
        for other in around[index]:
            if other in around:
                continue
            surface = surface_of(other)
            if surface.GetType() != GeomAbs_Plane:
                continue
            if abs(surface.Plane().Axis().Direction().Dot(axis)) >= ACROSS_THE_AXIS:
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
            )
            used.update({first, second, *flanks})
            break
    return found


def _neighbouring_faces(face: Any, neighbours: Any, numbered: Any) -> set[int]:
    """Die Nummern der Flächen, die an ``face`` grenzen — über ``numbered``."""
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    touching: set[int] = set()
    walk = TopExp_Explorer(face, TopAbs_EDGE)
    while walk.More():
        edge = walk.Current()
        walk.Next()
        for other in neighbours.FindFromKey(edge):
            if other.IsSame(face):
                continue
            number = numbered.FindIndex(other)
            if number > 0:
                touching.add(number - 1)
    return touching


def _flanks_of_a_slot(
    around: dict[int, set[int]],
    first: int,
    second: int,
    surface_of: Any,
) -> tuple[int, int] | None:
    """Die zwei Wände zwischen zwei Bögen — oder ``None``, wenn es keine sind."""
    from OCP.GeomAbs import GeomAbs_Plane

    from app.core.perceive.slots import ACROSS_THE_AXIS, PARALLEL_AXES, SAME_RADIUS

    one, other = surface_of(first).Cylinder(), surface_of(second).Cylinder()
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
    for index in shared:
        surface = surface_of(index)
        if surface.GetType() != GeomAbs_Plane:
            continue
        plane = surface.Plane()
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
    normals = [surface_of(flank).Plane().Axis().Direction() for flank in flanks]
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
) -> dict[FeatureId, Feature]:
    """Baut das Langloch und nimmt die vier Flächen aus der Liste."""
    first, second = arcs
    one, other = surface_of(first).Cylinder(), surface_of(second).Cylinder()
    radius = (float(one.Radius()) + float(other.Radius())) / 2.0
    across = _across_between(one, other)
    travel = math.sqrt(sum(value * value for value in across))

    surface = surface_of(first)
    first_v, last_v = float(surface.FirstVParameter()), float(surface.LastVParameter())
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
        neighbours, faces[first], one, first_v - reach, last_v + reach, tolerance
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
            "diameter": round(radius * 2.0, 4),
            "length": round(travel + radius * 2.0, 4),
            "travel": round(travel, 4),
            "axis": _oriented(axis),
            "direction": direction,
            "centre": centre,
            "depth": round(depth, 4),
            "through": through,
        },
        face_indices=tuple(indices),
    )
    return found


def _describe(
    face: Any, index: int, inside: Any, neighbours: Any, reach: float, tolerance: float
) -> tuple[FeatureKind, dict[str, Any]] | None:
    """Was diese Fläche ist, im Vokabular von §21."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_REVERSED

    surface = BRepAdaptor_Surface(face)
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    area = float(props.Mass())
    if area <= EPS_GEOM:
        return None
    centre = props.CentreOfMass()
    middle: Vec3 = (centre.X(), centre.Y(), centre.Z())

    kind = surface.GetType()
    if kind == GeomAbs_Plane:
        plane = surface.Plane()
        normal = plane.Axis().Direction()
        if face.Orientation() == TopAbs_REVERSED:
            normal.Reverse()
        return "face", {
            "area": round(area, 4),
            "centre": middle,
            "normal": (normal.X(), normal.Y(), normal.Z()),
        }

    if kind == GeomAbs_Cylinder:
        turn = abs(surface.LastUParameter() - surface.FirstUParameter())
        cylinder = surface.Cylinder()
        axis = cylinder.Axis().Direction()
        radius = float(cylinder.Radius())
        first_v = float(surface.FirstVParameter())
        last_v = float(surface.LastVParameter())
        depth = abs(last_v - first_v)
        # Loch oder Zapfen — das entscheidet, auf welcher Seite das Material
        # liegt, und das steht in der Orientierung der Fläche. Ohne diese
        # Unterscheidung war jeder Rundstab eine Bohrung: ein Ø-8-Zapfen aus
        # Fusion kam in Solidon als „hole, diameter 8.0, depth 40" an, und
        # dasselbe galt für jede Säule und jeden Dom.
        hollow = face.Orientation() == TopAbs_REVERSED

        # **Ein Ausschnitt ist eine Verrundung, kein verworfener Rest.** Wer
        # weniger als eine volle Umdrehung abdeckt, war bis hierher nichts —
        # dabei steht sein Radius exakt in der Topologie, weil die Fläche so
        # konstruiert wurde. Auf der Netzseite muss ihn ``detect_fillets``
        # aus Normalen einpassen und über den Winkelbogen von einem Zapfen
        # trennen; hier ist beides schon entschieden. Dieselben Schlüssel wie
        # dort, nur ohne ``residual``: Es wurde nichts eingepasst.
        if turn < FULL_TURN * 2.0 * 3.141592653589793:
            # **``recess`` kommt hier nicht aus der Orientierung.** Für einen
            # vollen Zylinder trennt ``REVERSED`` Loch von Zapfen zuverlässig;
            # für einen Ausschnitt tut es das nicht — an den vier gleichen
            # Außenkanten eines Quaders kam es zweimal so und zweimal anders
            # heraus. Gefragt ist ohnehin etwas Geometrisches: Liegt die Achse
            # im Material, ist es eine Verrundung, liegt sie außerhalb, eine
            # Kehle. Gemessen an einem L-Profil mit verrundeten Kanten: 26
            # Verrundungen, 2 Kehlen an der einspringenden Ecke.
            return "fillet", {
                "radius": round(radius, 4),
                "diameter": round(radius * 2.0, 4),
                "centre": middle,
                "axis": _oriented(axis),
                "length": round(depth, 4),
                "recess": not _axis_in_material(inside, cylinder, centre),
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
            params["through"] = not _axis_covered(
                neighbours, face, cylinder, first_v - reach, last_v + reach, tolerance
            )
        return "hole" if hollow else "pin", params

    if kind == GeomAbs_Sphere:
        ball = surface.Sphere()
        radius = float(ball.Radius())
        hollow = not _point_in_material(inside, ball.Location())
        if _rounded_neighbours(neighbours, face) >= CORNER_NEIGHBOURS:
            # **Als Verrundung, nicht als Kugel.** Was hier steht, ist die
            # Ecke, an der drei verrundete Kanten zusammentreffen. Sie ist
            # gerechnet ein Kugelstück und benannt eine Verrundung: „Kuppel
            # Ø4" an einer Quaderecke wäre richtig gerechnet und falsch
            # gesagt. Der Kunde sieht eine verrundete Ecke und will ihren
            # Radius. Keine Achse — eine Ecke hat keine.
            return "fillet", {
                "radius": round(radius, 4),
                "diameter": round(radius * 2.0, 4),
                "centre": middle,
                "length": 0.0,
                "recess": hollow,
            }
        return "sphere", {
            "diameter": round(radius * 2.0, 4),
            "centre": middle,
            "recess": hollow,
        }

    del index
    return None


def _axis_point(cylinder: Any, along: float) -> Vec3:
    """Der Punkt auf der Zylinderachse beim Parameter ``along``.

    ``V`` einer Zylinderfläche ist die Länge entlang der Achse ab ihrem
    Ursprung — derselbe Maßstab wie ``FirstVParameter``/``LastVParameter``.
    """
    origin = cylinder.Location()
    direction = cylinder.Axis().Direction()
    return (
        float(origin.X() + direction.X() * along),
        float(origin.Y() + direction.Y() * along),
        float(origin.Z() + direction.Z() * along),
    )


def _axis_covered(
    neighbours: Any, face: Any, cylinder: Any, first: float, last: float, tolerance: float
) -> bool:
    """Reicht eine Nachbarfläche dieses Mantels bis an die Bohrachse?

    Ein Sackloch endet an einer Fläche, die über der Achse liegt — ein ebener
    Boden, der Kegel einer Spitzenbohrung, die Kalotte eines Kugelfräsers —,
    und die stößt an den Mantel an. Bei einer Durchgangsbohrung stoßen nur
    Flächen an, in denen das Loch selbst liegt: Ihr Rand ist der Rand des
    Lochs, und der bleibt einen Radius von der Achse entfernt.

    **Nachbarn, nicht der ganze Körper.** Der Netzzwilling (``_is_through``)
    zählt Dreiecke über der Achse im Abschnitt der Bohrung; hier sagt es die
    Topologie: Der gegenüberliegende Schenkel eines U-Profils liegt zwar über
    der Achse, grenzt aber nicht an den Mantel — und die Bohrung im ersten
    Schenkel ist durchgehend.

    **Abstand, nicht Schnitt.** Der erste Versuch schnitt die Achse als Gerade
    mit jeder Nachbarfläche (``IntCurvesFace_Intersector``) und fand die
    Spitze eines Bohrkegels nicht: Sie ist in der Flächenparametrisierung ein
    entarteter Punkt, und der Schnitt meldet dort nichts. Der kleinste Abstand
    zwischen Achse und Fläche kennt diese Ausnahme nicht — eine Spitze ist ein
    Knoten der Fläche, und Knoten zählen mit. Gemessen an zehn Bauarten:
    Platte, Sackloch, Spitzenbohrung, schräger Austritt, zylindrische und
    kegelige Senkung, U-Profil, Kugelfräser, Kreuzbohrung, Stufenbohrung.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Lin
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    probe = BRepBuilderAPI_MakeEdge(gp_Lin(cylinder.Axis()), first, last).Edge()
    seen: list[Any] = []
    walk = TopExp_Explorer(face, TopAbs_EDGE)
    while walk.More():
        edge = walk.Current()
        walk.Next()
        for other in neighbours.FindFromKey(edge):
            if other.IsSame(face) or any(other.IsSame(known) for known in seen):
                continue
            seen.append(other)
    for other in seen:
        distance = BRepExtrema_DistShapeShape(probe, other)
        if distance.IsDone() and distance.Value() <= tolerance:
            return True
    return False


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


def _rounded_neighbours(neighbours: Any, face: Any) -> int:
    """Wie viele Flächen an dieser hier grenzen und selbst Kantenverrundungen
    sind — zylindrisch und weniger als eine volle Umdrehung.

    Eine Fläche wird nur einmal gezählt, auch wenn sie über zwei Kanten
    anstößt; ``TopoDS_Shape`` hat keine Gleichheit, die ein ``set`` versteht,
    darum der ``IsSame``-Vergleich gegen das schon Gesehene.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    seen: list[Any] = []
    walk = TopExp_Explorer(face, TopAbs_EDGE)
    while walk.More():
        edge = walk.Current()
        walk.Next()
        for other in neighbours.FindFromKey(edge):
            if other.IsSame(face) or any(other.IsSame(known) for known in seen):
                continue
            seen.append(other)

    rounded = 0
    for other in seen:
        surface = BRepAdaptor_Surface(TopoDS.Face(other))
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        turn = abs(surface.LastUParameter() - surface.FirstUParameter())
        if turn < FULL_TURN * 2.0 * math.pi:
            rounded += 1
    return rounded
