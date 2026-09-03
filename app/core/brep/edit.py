"""Einen B-Rep-Körper formen (Bauplan §30, §25).

Die zwei Operationen, die der Grund für einen zweiten Kern sind: Verrundung
und Fase an echten Kanten. Auf einem Netz sind beide Näherungen einer
Näherung — die Kante ist schon eine Kette von Segmenten, und sie zu runden
rundet die Segmente. Hier ist die Kante eine Kurve, und das Ergebnis ist
exakt.

Welche Kanten behandelt werden, ist eine Auswahl, und die Auswahl läuft über
Geometrie, nicht über Indizes: ein Index in die Topologie eines Körpers
ändert sich, sobald sich irgendetwas anderes an ihm ändert, und eine
Verrundung, die wandert, wenn ein unbeteiligtes Loch gebohrt wird, ist
schlimmer als gar keine (§21.2, derselbe Grund, aus dem Merkmalsbezeichner
zugeordnet werden).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from app.core.brep.kernel import Solid, require
from app.core.errors import CANCEL, CORRECT_INPUT, PROGRAMMING_ERRORS, GeometryError
from app.core.log import get_logger
from app.core.types import Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

EdgeChoice = Literal["all", "vertical", "horizontal", "top", "bottom"]

#: Welche Kanten eine Auswahl meint. „Senkrecht" ist, was jemand mit „runde
#: die Ecken dieser Box" meint: die vier Stehenden, nicht die Plattenkanten.
EDGE_CHOICES: tuple[EdgeChoice, ...] = ("all", "vertical", "horizontal", "top", "bottom")


@dataclass(frozen=True, slots=True)
class EdgeInfo:
    """Eine Kante, beschrieben über das, was sie ist, statt über ihren
    Speicherplatz.
    """

    edge: Any
    length: float
    direction: Vec3
    middle: Vec3

    @property
    def upright(self) -> bool:
        return abs(self.direction[2]) > 0.9

    @property
    def flat(self) -> bool:
        return abs(self.direction[2]) < 0.1


def box(width: float, depth: float, height: float) -> Solid:
    """Ein Quader auf dem Bett, in X und Y zentriert — derselbe Ankerpunkt wie
    auf der Mesh-Seite.
    """
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    corner = gp_Pnt(-width / 2.0, -depth / 2.0, 0.0)
    return Solid(BRepPrimAPI_MakeBox(corner, width, depth, height).Shape())


def cylinder(diameter: float, height: float) -> Solid:
    """Ein Zylinder, stehend auf Z = 0."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    return Solid(BRepPrimAPI_MakeCylinder(diameter / 2.0, height).Shape())


def edges_of(solid: Solid) -> list[EdgeInfo]:
    """Jede Kante mit den Zahlen, aus denen sich eine Auswahl treffen lässt."""
    require()
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    described: list[EdgeInfo] = []
    for edge in solid.edges():
        props = GProp_GProps()
        BRepGProp.LinearProperties_s(edge, props)
        length = float(props.Mass())
        if length <= EPS_GEOM:
            continue

        curve = BRepAdaptor_Curve(edge)
        start = curve.Value(curve.FirstParameter())
        end = curve.Value(curve.LastParameter())
        span = (end.X() - start.X(), end.Y() - start.Y(), end.Z() - start.Z())
        norm = max((span[0] ** 2 + span[1] ** 2 + span[2] ** 2) ** 0.5, EPS_GEOM)
        centre = props.CentreOfMass()
        described.append(
            EdgeInfo(
                edge=edge,
                length=length,
                direction=(span[0] / norm, span[1] / norm, span[2] / norm),
                middle=(centre.X(), centre.Y(), centre.Z()),
            )
        )
    return described


def choose(solid: Solid, choice: EdgeChoice) -> list[EdgeInfo]:
    """Die Kanten, die eine benannte Auswahl meint."""
    described = edges_of(solid)
    if choice == "all":
        return described
    if choice == "vertical":
        return [entry for entry in described if entry.upright]
    if choice == "horizontal":
        return [entry for entry in described if entry.flat]

    heights = [entry.middle[2] for entry in described]
    if not heights:
        return []
    wanted = max(heights) if choice == "top" else min(heights)
    return [
        entry
        for entry in described
        if entry.flat and abs(entry.middle[2] - wanted) <= EPS_GEOM * 1000
    ]


def fillet(solid: Solid, radius: float, choice: EdgeChoice = "all") -> Solid:
    """Rundet die gewählten Kanten. Exakt, weil die Kante eine Kurve
    ist (§30).
    """
    require()
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet

    chosen = choose(solid, choice)
    if not chosen:
        raise GeometryError(
            detail=_("Zu dieser Auswahl gehört keine Kante."),
            values={"choice": choice},
        )

    builder = BRepFilletAPI_MakeFillet(solid.shape)
    for entry in chosen:
        builder.Add(radius, entry.edge)
    return _built(solid, builder, "fillet", radius, len(chosen))


def chamfer(solid: Solid, distance: float, choice: EdgeChoice = "all") -> Solid:
    """Bricht die gewählten Kanten im 45-Grad-Winkel."""
    require()
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer

    chosen = choose(solid, choice)
    if not chosen:
        raise GeometryError(
            detail=_("Zu dieser Auswahl gehört keine Kante."),
            values={"choice": choice},
        )

    builder = BRepFilletAPI_MakeChamfer(solid.shape)
    for entry in chosen:
        builder.Add(distance, entry.edge)
    return _built(solid, builder, "chamfer", distance, len(chosen))


def _too_large(kind: str) -> Any:
    """Der Satz zum gescheiterten Bau — in den Worten des Feldes, das ihn
    ausgelöst hat.

    Beide Wege endeten in „Der Radius ist für diese Kanten zu groß.", auch die
    Fase. Deren Feld heißt aber **Breite** (``distance``, Titel „Breite"), und
    einen Radius gibt es dort nirgends: Wer *Fase anbringen* mit der Vorgabe
    1,0 mm auf ein eingelesenes STEP-Teil anwendet, bekommt eine Absage über
    eine Größe, die in seinem Dialog nicht vorkommt, und sucht ein Feld, das es
    nicht gibt. Gemessen an ``build_tray_v3.step`` aus dem Kundenbestand:
    0,2 mm geht, 0,5 mm und darüber nicht — der Satz kommt also im Normalfall
    und nicht im Ausnahmefall.
    """
    if kind == "chamfer":
        return _("Die Breite ist für diese Kanten zu groß.")
    return _("Der Radius ist für diese Kanten zu groß.")


def _built(solid: Solid, builder: Any, kind: str, size: float, edges: int) -> Solid:
    """Führt den Builder aus und macht aus seinem Scheitern einen Satz, auf
    den jemand reagieren kann.
    """
    try:
        builder.Build()
        if not builder.IsDone():
            raise GeometryError(
                detail=_too_large(kind),
                # **Nicht die Vorgabe des Geometriefehlers.** Die heißt
                # „Reparieren und erneut versuchen" und „Stellen zeigen" — an
                # einem exakten Körper gibt es nichts zu reparieren, und
                # Stellen nennt dieser Fehler keine. Beide Handlungen haben
                # einen Handler, erscheinen also als Knopf, und beide täten
                # nichts: Regel 17 wäre optisch erfüllt und in der Sache
                # verletzt. Die Antwort auf einen zu großen Radius ist ein
                # kleinerer.
                suggestions=(CORRECT_INPUT, CANCEL),
                values={"size_mm": round(size, 3), "edges": edges},
            )
        shape = builder.Shape()
    except GeometryError:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # OpenCASCADE raises its own exception types
        raise GeometryError(
            detail=_too_large(kind),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={"size_mm": round(size, 3), "edges": edges},
        ) from problem
    _log.info("%s of %.2f mm on %d edge(s)", kind, size, edges)
    return solid.replacing(shape)


def boolean(kind: Literal["union", "difference", "intersection"], parts: list[Solid]) -> Solid:
    """Präzise Boolesche Ops: keine Tessellation, also keine
    Tessellations-Artefakte (§30).

    Eine Rückfallkette gibt es hier nicht, und das ist keine Auslassung — die
    Kette aus §17.2 existiert, weil Netze sich uneinig sind, was innen ist.
    Zwei B-Rep-Volumen sind das nicht, und wo das hier scheitert, ist die
    Antwort ein echter Fehler statt eines gröberen Versuchs.
    """
    require()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse

    if len(parts) < 2:
        raise ValueError("a boolean operation needs at least two bodies")
    makers = {
        "union": BRepAlgoAPI_Fuse,
        "difference": BRepAlgoAPI_Cut,
        "intersection": BRepAlgoAPI_Common,
    }
    shape = parts[0].shape
    for other in parts[1:]:
        operation = makers[kind](shape, other.shape)
        operation.Build()
        if not operation.IsDone():
            # Nicht „fehlgeschlagen" (Regel 17), und nicht die geerbten
            # Vorschläge: Mesh-Reparatur und offene Kanten gibt es für einen
            # B-Rep-Körper nicht. Der häufigste Grund ist eine Berührung
            # ohne Überlappung — und die behebt eine Bewegung, keine
            # Reparatur.
            raise GeometryError(
                detail=_(
                    "Die gewählte Bearbeitung funktioniert mit diesen Körpern in ihrer "
                    "jetzigen Lage nicht — meist berühren sie sich nur an einer Fläche "
                    "oder Kante. Verschieben Sie einen der beiden so weit, dass sich die "
                    "Körper wirklich überlappen."
                ),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        shape = operation.Shape()
    return parts[0].replacing(shape)


def bore(
    solid: Solid,
    *,
    position: Vec3,
    axis: Literal["x", "y", "z"],
    diameter: float,
    depth: float = 0.0,
    anchor: Literal["mouth", "centre"] = "mouth",
) -> Solid:
    """Schneidet eine zylindrische Bohrung. Tiefe null bohrt ganz durch.

    Die Semantik ist wörtlich die von :func:`app.core.geom.prepare.drill` —
    dieselben Parameter bedeuten dasselbe, sonst wäre das Umschalten zwischen
    den Kernen (``MENU_TWINS``) kein Umschalten, sondern eine andere Bohrung.
    ``mouth`` ist, was jemand meint, der eine Fläche anklickt: dort fängt die
    Bohrung an und geht ins Material. Für eine durchgehende macht es keinen
    Unterschied.

    **Der Zylinder entsteht gleich an seiner Stelle**, über ``gp_Ax2``, statt
    stehend und dann gedreht. Eine Drehung um eine Achse, die nicht durch den
    Ursprung geht, ist zwei Bewegungen und eine Gelegenheit, sich um ein
    Vorzeichen zu irren; die Achse mitzugeben ist eine Zeile.

    **Die Toleranz gehört nicht hierher.** ``diameter`` ist das Maß, das
    geschnitten wird — was das Material frisst, rechnet
    :func:`app.core.geom.prepare.bore_diameter` einmal für beide Kerne aus.
    Zweimal gerechnet wäre sie zweimal drauf.
    """
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    index = {"x": 0, "y": 1, "z": 2}[axis]
    box = solid.bounds
    through = depth <= EPS_GEOM
    if through:
        # Lang genug, um von jeder Position aus in beide Richtungen
        # hinauszureichen — dieselbe Überlegung wie auf der Mesh-Seite, nur
        # ohne den Überlappungszuschlag: Zwei B-Rep-Volumen sind sich einig,
        # was innen ist, und eine bündige Fläche ist hier kein Sonderfall.
        span = box.size[index]
        length = span * 2.0 + abs(position[index] - box.centre[index]) * 2.0
        start = box.centre[index] - length / 2.0
    else:
        length = depth
        if anchor == "mouth":
            # Ins Material hinein, und das ist die Richtung, in der der Körper
            # liegt: Wer die Oberseite anklickt, bohrt nach unten. Der
            # Gleichstand — die Achsmitte, die Vorgabeposition — geht wie auf
            # der Mesh-Seite (``into_the_body``, ``>=``) nach unten; sonst
            # bohrt ein Umschalten zwischen create_box und create_brep_box in
            # die Gegenrichtung, und MENU_TWINS ist kein Umschalten mehr.
            into = -1.0 if position[index] >= box.centre[index] else 1.0
            start = position[index] if into > 0 else position[index] - length
        else:
            start = position[index] - length / 2.0

    origin = [position[0], position[1], position[2]]
    origin[index] = start
    direction = [0.0, 0.0, 0.0]
    direction[index] = 1.0

    frame = gp_Ax2(gp_Pnt(*origin), gp_Dir(*direction))
    cutter = Solid(BRepPrimAPI_MakeCylinder(frame, diameter / 2.0, length).Shape())
    return boolean("difference", [solid, cutter])


def resize_bore(
    solid: Solid,
    *,
    position: Vec3,
    direction: Vec3,
    previous_diameter: float,
    diameter: float,
    depth: float,
) -> Solid:
    """Ändert eine erkannte Bohrung und erhält den exakten Körper.

    Dieselbe Konstruktion wie beim Netz-Zwilling: Vergrößern trägt einen
    Zylinder ab, Verkleinern vereinigt einen Ring mit der vorhandenen Wand.
    Der Ring greift um ``EPS_GEOM`` ins Material, damit zwei Flächen nicht nur
    aufeinanderliegen. Das Ergebnismaß bleibt der innere Radius und damit
    exakt der gewählte Durchmesser.
    """
    if abs(diameter - previous_diameter) <= EPS_GEOM:
        return solid
    if depth <= EPS_GEOM:
        raise ValueError("a detected bore must have a positive depth")

    length = math.sqrt(sum(float(value) ** 2 for value in direction))
    if length <= EPS_GEOM:
        raise ValueError("a bore direction must not be zero")
    unit: Vec3 = (
        float(direction[0]) / length,
        float(direction[1]) / length,
        float(direction[2]) / length,
    )
    start: Vec3 = (
        float(position[0]) - unit[0] * depth / 2.0,
        float(position[1]) - unit[1] * depth / 2.0,
        float(position[2]) - unit[2] * depth / 2.0,
    )
    cutter = _oriented_cylinder(start, unit, diameter / 2.0, depth)
    if diameter > previous_diameter:
        return boolean("difference", [solid, cutter])

    outer = _oriented_cylinder(
        start,
        unit,
        previous_diameter / 2.0 + EPS_GEOM,
        depth,
    )
    ring = boolean("difference", [outer, cutter])
    return boolean("union", [solid, ring])


def _oriented_cylinder(origin: Vec3, direction: Vec3, radius: float, height: float) -> Solid:
    """Ein exakter Zylinder an freier Achse, gemeinsam für die Ringrechnung."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    frame = gp_Ax2(gp_Pnt(*origin), gp_Dir(*direction))
    return Solid(BRepPrimAPI_MakeCylinder(frame, radius, height).Shape())


def moved(solid: Solid, offset: Vec3) -> Solid:
    """Verschiebt einen Körper. Starre Bewegungen bleiben auf einem B-Rep exakt."""
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec

    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(offset[0], offset[1], offset[2]))
    return solid.replacing(BRepBuilderAPI_Transform(solid.shape, transform, True).Shape())
