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
from app.core.units import EPS_GEOM

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

    for index, face in enumerate(solid.faces()):
        described = _describe(face, index, inside, neighbours)
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
    face: Any, index: int, inside: Any, neighbours: Any
) -> tuple[FeatureKind, dict[str, Any]] | None:
    """Was diese Fläche ist, im Vokabular von §21."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere
    from OCP.GProp import GProp_GProps

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
        return "face", {
            "area": round(area, 4),
            "centre": middle,
            "normal": (normal.X(), normal.Y(), normal.Z()),
        }

    if kind == GeomAbs_Cylinder:
        from OCP.TopAbs import TopAbs_REVERSED

        turn = abs(surface.LastUParameter() - surface.FirstUParameter())
        cylinder = surface.Cylinder()
        axis = cylinder.Axis().Direction()
        radius = float(cylinder.Radius())
        depth = abs(surface.LastVParameter() - surface.FirstVParameter())
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

        return "hole" if hollow else "pin", {
            # Der Kern behält das Topologiemaß in doppelter Genauigkeit.
            # Gerundet wird erst in Baum und Dialog: Eine Bearbeitung, die
            # daraus wieder einen exakten Zylinder baut, darf sonst einen
            # losen Ring oder eine hauchdünne alte Lippe erzeugen.
            "diameter": radius * 2.0,
            "centre": middle,
            "axis": (axis.X(), axis.Y(), axis.Z()),
            "depth": depth,
        }

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
