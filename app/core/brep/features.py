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
"""

from __future__ import annotations

from typing import Any

from app.core.brep.kernel import Solid
from app.core.log import get_logger
from app.core.types import Feature, FeatureId, FeatureKind, Vec3
from app.core.units import EPS_GEOM, match_tolerance

_log = get_logger(__name__)

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

    for index, face in enumerate(solid.faces()):
        described = _describe(face, index, inside, neighbours, reach, tolerance)
        if described is None:
            continue
        kind, params = described
        counts[kind] = counts.get(kind, 0) + 1
        identifier = f"{kind}_{counts[kind]}"
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

    _log.info(
        "read %d hole(s), %d pin(s), %d fillet(s) and %d face(s) off a B-Rep body",
        counts["hole"],
        counts["pin"],
        counts["fillet"],
        counts["face"],
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
                "axis": (axis.X(), axis.Y(), axis.Z()),
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
            "axis": (axis.X(), axis.Y(), axis.Z()),
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
    import math

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
