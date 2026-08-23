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


def features_of(solid: Solid) -> dict[FeatureId, Feature]:
    """Löcher und ebene Flächen, aus der Topologie abgelesen statt
    eingepasst.
    """
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier

    found: dict[FeatureId, Feature] = {}
    counts = {"hole": 0, "pin": 0, "face": 0, "fillet": 0}
    # Einmal je Körper, nicht einmal je Fläche: der Klassierer baut sich eine
    # Beschleunigungsstruktur auf, und die gilt für den ganzen Solid.
    inside = BRepClass3d_SolidClassifier(solid.shape)

    for index, face in enumerate(solid.faces()):
        described = _describe(face, index, inside)
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
            face_indices=(index,),
        )

    _log.info(
        "read %d hole(s), %d pin(s), %d fillet(s) and %d face(s) off a B-Rep body",
        counts["hole"],
        counts["pin"],
        counts["fillet"],
        counts["face"],
    )
    return found


def _describe(face: Any, index: int, inside: Any) -> tuple[FeatureKind, dict[str, Any]] | None:
    """Was diese Fläche ist, im Vokabular von §21."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
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
            "diameter": round(radius * 2.0, 4),
            "centre": middle,
            "axis": (axis.X(), axis.Y(), axis.Z()),
            "depth": round(depth, 4),
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
    from OCP.TopAbs import TopAbs_IN

    origin = cylinder.Location()
    direction = cylinder.Axis().Direction()
    along = (
        (centre.X() - origin.X()) * direction.X()
        + (centre.Y() - origin.Y()) * direction.Y()
        + (centre.Z() - origin.Z()) * direction.Z()
    )
    inside.Perform(
        gp_Pnt(
            origin.X() + along * direction.X(),
            origin.Y() + along * direction.Y(),
            origin.Z() + along * direction.Z(),
        ),
        EPS_GEOM,
    )
    return bool(inside.State() == TopAbs_IN)
