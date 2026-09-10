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
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal, cast

from app.core.brep.kernel import DEFLECTION, Solid, boolean_builder, require
from app.core.errors import CANCEL, CORRECT_INPUT, PROGRAMMING_ERRORS, GeometryError
from app.core.geom.edges import EDGE_CHOICES as SHARED_EDGE_CHOICES
from app.core.geom.edges import EdgeChoice as SharedEdgeChoice
from app.core.geom.edges import choose as choose_by_place
from app.core.geom.edges import named_edges as edges_named
from app.core.geom.edges import wanted as edges_wanted
from app.core.log import get_logger
from app.core.types import PlaneFrame, Point2, Transform, Vec3
from app.core.units import EPS_GEOM, is_close
from app.i18n import _

_log = get_logger(__name__)

#: Welche Kanten eine Auswahl meint — **die Tabelle steht in ``geom.edges``**
#: und gilt für beide Kerne. Hier bleibt der Name, unter dem das Register und
#: die Operationen sie ansprechen; zwei Aufzählungen hießen, dass ein Kern
#: eines Tages eine sechste Art kennt und der andere nicht.
#: Wie weit ein gemessener Rundungsradius vom gesuchten abweichen darf.
#: Der Netz-Kern misst ihn an einem Sehnenzug und kommt deshalb ein wenig zu
#: klein heraus — 2,9772 an einer Rundung, die mit 3,0 gebaut wurde.
FILLET_RADIUS_SLACK = 0.05

EdgeChoice = SharedEdgeChoice
EDGE_CHOICES: tuple[EdgeChoice, ...] = SHARED_EDGE_CHOICES


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


def _seam_edges(solid: Solid) -> Any:
    """Die Nahtkanten des Körpers — als OCCT-Menge, einmal je Körper.

    Eine Naht gehört **einer** Fläche: der Stelle, an der deren
    Parametrisierung umläuft. Gefragt wird deshalb je Fläche nach ihren
    eigenen Kanten und nicht je Kante nach allen Flächen — das erste ist
    linear in den Kantenvorkommen, das zweite ihr Produkt.
    """
    from OCP.BRep import BRep_Tool
    from OCP.collections import (
        IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap,
    )
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    seams = ShapeMap()
    for face in solid.faces():
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            if BRep_Tool.IsClosed_s(TopoDS.Edge(edge), TopoDS.Face(face)):
                seams.Add(edge)
            explorer.Next()
    return seams


def edges_of(solid: Solid) -> list[EdgeInfo]:
    """Jede Kante mit den Zahlen, aus denen sich eine Auswahl treffen lässt."""
    require()
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    # **Nahtkanten gehören nicht dazu.** Wo eine Fläche in sich geschlossen ist
    # — der Mantel eines Zylinders, einer Kugel, eines Kegels —, trägt sie eine
    # Naht: die Stelle, an der ihre Parametrisierung umläuft. Das sieht wie
    # eine Kante aus und ist keine; zwischen zwei Flächen liegt sie nicht,
    # sondern in einer.
    #
    # Verrunden lässt sie sich deshalb nicht, und OpenCASCADE sagt das je nach
    # Plattform verschieden: Unter Windows und Linux meldet der Builder
    # „nicht fertig", auf dem Intel-Mac **stürzt der Prozess ab** (gemessen am
    # 08.09.2026, `test_a_selection_that_matches_nothing_says_so`, Stack in
    # `_built`). Ein Kunde verlöre dabei seine Arbeit. Was gar nicht erst in
    # die Auswahl kommt, kann auch nicht gebaut werden — und der vorhandene
    # Satz „Zu dieser Auswahl gehört keine Kante." trifft die Lage genauer als
    # „Der Radius ist zu groß".
    #
    # **Einmal eingesammelt, nicht je Kante gesucht.** Der erste Anlauf fragte
    # ``any(IsClosed_s(edge, face) for face in faces)`` — Kanten mal Flächen,
    # und an einem Teil mit ein paar hundert von jedem ist das der teuerste
    # Posten der ganzen Auswahl. Eine Naht gehört ohnehin **einer** Fläche;
    # gefragt wird deshalb je Fläche nach ihren eigenen Kanten, und das ist
    # linear in der Zahl der Kantenvorkommen.
    seams = _seam_edges(solid)

    described: list[EdgeInfo] = []
    for edge in solid.edges():
        props = GProp_GProps()
        BRepGProp.LinearProperties_s(edge, props)
        length = float(props.Mass())
        if length <= EPS_GEOM:
            continue
        if seams.Contains(edge):
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


def edge_points(entry: EdgeInfo, deflection: float = DEFLECTION) -> tuple[Vec3, ...]:
    """Die Kante als Punktfolge — was die Ansicht braucht, um sie zu treffen.

    :class:`EdgeInfo` beschreibt eine Kante über Mitte, Richtung und Länge,
    und für die Auswahl nach Lage reicht das. Für einen Klick reicht es
    nicht: Ein Bogen liegt nirgends dort, wo Mitte und Richtung ihn
    vermuten lassen — der Viertelkreis einer Verrundung hat seinen
    Schwerpunkt neben sich selbst, und ein Zeiger, der auf die Sehne
    zielt, trifft die Kante nie.

    Abgetastet wird nach **Abweichung**, nicht nach fester Punktzahl: Eine
    Strecke kommt mit zwei Punkten zurück, ein Kreis mit so vielen, wie
    ``deflection`` verlangt. Dieselbe Zahl, mit der der Kern tesselliert
    — was im Bild rund aussieht, soll sich auch rund anklicken lassen.

    Scheitert die Abtastung, stehen wenigstens Anfang und Ende da: Eine
    Kante ohne Punkte wäre für den Zeiger nicht vorhanden, und das ist
    schlechter als eine, die nur an ihren Enden getroffen wird.
    """
    require()
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection

    curve = BRepAdaptor_Curve(entry.edge)
    sampler = GCPnts_QuasiUniformDeflection(curve, max(deflection, EPS_GEOM))
    if not sampler.IsDone() or sampler.NbPoints() < 2:
        first = curve.Value(curve.FirstParameter())
        last = curve.Value(curve.LastParameter())
        return ((first.X(), first.Y(), first.Z()), (last.X(), last.Y(), last.Z()))
    points = (sampler.Value(index) for index in range(1, sampler.NbPoints() + 1))
    return tuple((point.X(), point.Y(), point.Z()) for point in points)


def edge_key(entry: EdgeInfo) -> str:
    """Der stabile Verweis auf **eine** Kante (E4, RM-147, §21).

    Eine Kante hat keine Kennung, die eine zweite Auswertung überlebt: Ihr
    nativer Handle gehört dem Lauf, der ihn erzeugt hat, und ihr Platz in
    ``solid.edges()`` verschiebt sich, sobald eine Operation davor etwas
    ändert. Beides in eine Projektdatei zu schreiben hieße, beim nächsten
    Öffnen eine andere Kante zu verrunden — still.

    Der Schlüssel kommt deshalb aus der **Geometrie**: Mittelpunkt und
    Richtung, auf hundertstel Millimeter beziehungsweise drei Stellen
    gerundet. Zwei verschiedene Kanten teilen beides nicht — sie lägen
    aufeinander.

    **Die Richtung ohne Vorzeichen**, denn dieselbe Kante kann in beide
    Richtungen laufen, je nachdem, welche Fläche sie beschreibt: Die erste
    Komponente ungleich null wird positiv gemacht. Ohne das trüge dieselbe
    Kante nach einer Booleschen Operation einen anderen Schlüssel, und die
    Verrundung fiele aus, statt zu greifen.

    Gerundet wird auf ein Hundertstel, weil das die Größenordnung ist, in der
    dieser Drucker arbeitet (§11) — feiner hieße, dass ein Kern mit anderer
    Toleranz denselben Punkt anders schreibt.
    """
    # **Die Formatierung steht einmal**, in ``geom.edges``: Sie gilt für
    # beide Kerne, und dieselbe Kante muss aus beiden denselben Schlüssel
    # bekommen. Zwei Fassungen liefen daran schon auseinander — an der
    # negativen Null, die sich als ``-0.000`` schreibt.
    from app.core.geom.edges import edge_key as shared

    return shared(entry)


def named_edges(solid: Solid, keys: Sequence[str]) -> list[EdgeInfo]:
    """Die Kanten zu diesen Schlüsseln — in der Reihenfolge der Schlüssel.

    Was nicht mehr da ist, fehlt in der Antwort; **wer daraus einen Fehler
    macht, entscheidet der Aufrufer.** Eine Kante kann verschwunden sein, weil
    ein Schritt davor sie weggenommen hat, und dann ist das eine Auskunft an
    den Kunden und kein Programmfehler (Regel 17).
    """
    return edges_named(edges_of(solid), keys)


def choose(solid: Solid, choice: EdgeChoice) -> list[EdgeInfo]:
    """Die Kanten, die eine benannte Auswahl meint."""
    return choose_by_place(edges_of(solid), choice)


def _wanted(solid: Solid, choice: EdgeChoice, keys: Sequence[str]) -> list[EdgeInfo]:
    """Die Kanten, die dieser Aufruf behandelt — genannte vor Gruppe (E4).

    **Die Auswahl selbst steht in ``geom.edges``**, aus demselben Grund wie
    :func:`edge_key`: Sie fragt nur nach ``upright``, ``flat`` und der Mitte,
    und beide Kerne beantworten das gleich. Zwei Fassungen hießen, dass
    „alle senkrechten Kanten" hier bald etwas anderes bedeutet als am Netz —
    bei derselben Menüzeile und demselben Parameter.
    """
    return edges_wanted(edges_of(solid), choice, keys)


def fillet(
    solid: Solid,
    radius: float,
    choice: EdgeChoice = "all",
    keys: Sequence[str] = (),
) -> Solid:
    """Rundet die gewählten Kanten. Exakt, weil die Kante eine Kurve
    ist (§30).

    ``keys`` sind einzelne Kanten (:func:`edge_key`, E4). Sind welche genannt,
    gelten sie und nicht die Gruppe: Wer eine bestimmte Kante angibt, meint
    sie — nicht alle senkrechten dazu.
    """
    require()
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet

    working = Solid(solid.shape, deflection=solid.deflection)
    chosen = _wanted(working, choice, keys)

    _fits_the_wall(working, radius, len(chosen), "fillet")
    builder = BRepFilletAPI_MakeFillet(working.shape)
    for entry in chosen:
        builder.Add(radius, entry.edge)
    return _built(solid, builder, "fillet", radius, len(chosen))


def chamfer(
    solid: Solid,
    distance: float,
    choice: EdgeChoice = "all",
    keys: Sequence[str] = (),
) -> Solid:
    """Bricht die gewählten Kanten im 45-Grad-Winkel.

    ``keys`` wie bei :func:`fillet`: einzelne Kanten haben Vorrang vor der
    Gruppe.
    """
    require()
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer

    working = Solid(solid.shape, deflection=solid.deflection)
    chosen = _wanted(working, choice, keys)

    _fits_the_wall(working, distance, len(chosen), "chamfer")
    builder = BRepFilletAPI_MakeChamfer(working.shape)
    for entry in chosen:
        builder.Add(distance, entry.edge)
    return _built(solid, builder, "chamfer", distance, len(chosen))


def _wall_not_proven() -> GeometryError:
    """Erzeugt die sichere Absage für eine unbelegte Wandmessung.

    **Nicht ``RETRY``, und aus demselben Grund, den ``_built`` unten
    aufschreibt.** *Erneut versuchen* ist im Fenster genau dann verdrahtet,
    solange ein gescheitertes Schreiben ansteht (``main_window.error_handlers``,
    Zweig ``_write_failure``; ``tests/test_ui.py`` führt ``retry`` deshalb in
    ``postponed``). Hier steht kein solches Schreiben an, der Rat käme also nur
    als Satz an — und er wäre auch dann falsch: Dieselbe Wandkarte über
    demselben Netz scheitert beim zweiten Anlauf genauso. Regel 17 wäre
    optisch erfüllt und in der Sache verletzt.

    Was bleibt, ist der Weg zurück in den Schritt: An einem Körper, dessen
    Wand sich nicht belegen lässt, gibt es keine Größe, die durchkommt — die
    Antwort ist ein anderer Schritt oder keiner, und *Eingabe korrigieren*
    öffnet genau ihn (``main_window._correct_after_error``). Damit gibt jede
    Absage dieser Datei denselben Rat, und der Kunde bekommt für „die
    Verrundung ist nicht entstanden" einen Knopf statt zwei verschiedene.
    """
    return GeometryError(
        detail=_("Die Wandstärke konnte für diese Kanten nicht sicher geprüft werden."),
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def _thinnest_wall(solid: Solid) -> float:
    """Die dünnste belegte Stelle des Körpers in Millimetern.

    **Warum das vor einer Verrundung steht: ein Absturz.** An Roberts
    Filamenthalter, einem auf 3 mm ausgehöhlten Kasten, nahm ein Radius von
    3 mm auf den oberen Kanten den ganzen Prozess mit — Zugriffsverletzung in
    ``BRepFilletAPI_MakeFillet::Build``, kein Traceback, kein Dialog, die
    Arbeit des Kunden weg (06.09.2026). Eine Rundung, die dicker ist als die
    Wand, hat keinen Platz; OpenCASCADE merkt es erst mitten im Bau.

    Gemessen wird auf der Tessellation über dieselbe Karte, die auch das
    Messwerkzeug und die Analyseansicht benutzen (§18.3) — an dem Kasten
    0,23 Sekunden und 2,09 mm für eine 3-mm-Wand. Die Karte misst also etwas
    zu knapp, und das ist die richtige Richtung: Die Schranke fällt eher zu
    streng aus als zu großzügig, und wo sie greift, steht ein Satz statt
    eines Absturzes.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.maps import wall_thickness_map

    try:
        values = [
            value
            for value in wall_thickness_map(as_mesh_data(solid)).values
            if math.isfinite(value) and value > 0.0
        ]
    except GeometryError:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # ohne Messung ist der native Aufruf nicht sicher
        raise _wall_not_proven() from problem
    if not values:
        raise _wall_not_proven()
    return min(values)


def _fits_the_wall(solid: Solid, size: float, edges: int, kind: str) -> None:
    """Hält an, wo die Rundung dicker wäre als die dünnste Wand."""
    thinnest = _thinnest_wall(solid)
    if size < thinnest:
        return
    raise GeometryError(
        detail=_too_large(kind),
        suggestions=(CORRECT_INPUT, CANCEL),
        values={"size_mm": round(size, 3), "edges": edges, "wall_mm": round(thinnest, 2)},
    )


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
    # **Gebaut heißt nicht heil.** Zwischen der Größe, die OpenCASCADE
    # ablehnt, und der, die es abstürzen lässt, liegt ein Bereich, in dem es
    # ein Ergebnis liefert und ``IsDone()`` meldet — und der Körper darin ist
    # kaputt: An Roberts Kasten trennte ein Radius von 2 mm die 3 mm dicke
    # Wand auf, aus einem Solid wurden zwei, und das Volumen wuchs um acht
    # Prozent. ``BRepCheck_Analyzer`` sagt es in Millisekunden; ohne diese
    # Zeile reist der kaputte Körper weiter, bis eine spätere Operation an ihm
    # scheitert oder der Drucker ihn nicht drucken kann.
    from OCP.BRepCheck import BRepCheck_Analyzer

    if not BRepCheck_Analyzer(shape).IsValid():
        raise GeometryError(
            detail=_too_large(kind),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={"size_mm": round(size, 3), "edges": edges},
        )
    outcome = solid.replacing(shape)
    if (
        outcome.solid_count != solid.solid_count
        or not outcome.is_closed
        or outcome.volume <= EPS_GEOM
    ):
        raise GeometryError(
            detail=_too_large(kind),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={"size_mm": round(size, 3), "edges": edges},
        )
    _log.info("%s of %.2f mm on %d edge(s)", kind, size, edges)
    return outcome


def boolean(kind: Literal["union", "difference", "intersection"], parts: list[Solid]) -> Solid:
    """Präzise Boolesche Ops: keine Tessellation, also keine
    Tessellations-Artefakte (§30).

    Eine Rückfallkette gibt es hier nicht, und das ist keine Auslassung — die
    Kette aus §17.2 existiert, weil Netze sich uneinig sind, was innen ist.
    Zwei B-Rep-Volumen sind das nicht, und wo das hier scheitert, ist die
    Antwort ein echter Fehler statt eines gröberen Versuchs.
    """
    require()
    if len(parts) < 2:
        raise ValueError("a boolean operation needs at least two bodies")
    shape = parts[0].shape
    for other in parts[1:]:
        operation = boolean_builder(kind, shape, other.shape)
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


def bore_profile(solid: Solid, outline: list[Point2], frame: PlaneFrame) -> Solid:
    """Schneidet das gemeinsame Bohrungsprofil als exakten Rotationskörper."""
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt

    wire = BRepBuilderAPI_MakePolygon()
    previous: Point2 | None = None
    # Der erste Punkt schließt sich über Close; doppelte Punkte entstehen
    # bei einer Aufweitung ohne geraden Abschnitt und bilden keine Kante.
    for radius, height in outline[:-1]:
        if (
            previous is not None
            and math.hypot(radius - previous[0], height - previous[1]) <= EPS_GEOM
        ):
            continue
        wire.Add(
            gp_Pnt(
                *(
                    frame.origin[i] + radius * frame.x_axis[i] + height * frame.normal[i]
                    for i in range(3)
                )
            )
        )
        previous = (radius, height)
    wire.Close()
    face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
    axis = gp_Ax1(gp_Pnt(*frame.origin), gp_Dir(*frame.normal))
    tool = BRepPrimAPI_MakeRevol(face, axis, math.tau)
    if not tool.IsDone():
        raise GeometryError(
            detail=_("Aus diesen Bohrungsmaßen entsteht kein geschlossener Schneidkörper."),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return boolean("difference", [solid, Solid(tool.Shape())])


def slot_bore(
    solid: Solid,
    *,
    position: Vec3,
    direction: Vec3,
    diameter: float,
    depth: float,
    length: float,
    angle_deg: float,
    overlap: float,
) -> Solid:
    """Zieht eine erkannte Bohrung zu einem Langloch — exakt, mit echten Bögen.

    Das Gegenstück zu :func:`app.core.geom.prepare.slot_bore`. Der Umriss ist
    derselbe, aufgezogen wird er als Prisma statt als abgetastetes Netz: Die
    beiden Enden bleiben Zylinderflächen, und der STEP-Export trägt sie mit.

    ``overlap`` ist die Zugabe auf den Durchmesser; sie hält die alte
    Bohrungswand von der neuen fern (§39) und kommt vom Aufrufer, damit beide
    Kerne dieselbe Zahl verwenden.
    """
    from app.core.brep.profiles import extrude
    from app.core.geom.prepare import slot_profile, slot_travel
    from app.core.sketch.planes import frame_of

    if depth <= EPS_GEOM:
        raise ValueError("a detected bore must have a positive depth")
    span = math.sqrt(sum(float(value) ** 2 for value in direction))
    if span <= EPS_GEOM:
        raise ValueError("a bore direction must not be zero")
    unit: Vec3 = (
        float(direction[0]) / span,
        float(direction[1]) / span,
        float(direction[2]) / span,
    )
    frame = frame_of(unit, position)
    floor = replace(
        frame,
        origin=cast(
            Vec3,
            tuple(float(position[i]) - frame.normal[i] * depth / 2.0 for i in range(3)),
        ),
    )
    tool = extrude(
        slot_profile(
            radius=(diameter + overlap) / 2.0,
            travel=slot_travel(diameter=diameter, length=length),
            angle_deg=angle_deg,
        ),
        depth,
        frame=floor,
    )
    return boolean("difference", [solid, tool])


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
    if is_close(diameter, previous_diameter):
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


def fill_bore(
    solid: Solid,
    *,
    position: Vec3,
    direction: Vec3,
    diameter: float,
    depth: float,
) -> Solid:
    """Schließt eine erkannte Bohrung wieder — das Gegenstück zum Bohren.

    Ohne diesen Weg konnte am exakten Körper kein Merkmal die Stelle wechseln:
    Die alte Bohrung wäre stehen geblieben und die neue daneben entstanden.
    Der Netz-Kern löst das seit dem 03.09.2026 mit
    ``prepare_ops._closed_at``; hier ist die exakte Hälfte davon, damit
    zwischen den beiden Kernen kein Unterschied bleibt (Robert, 10.09.2026:
    „zwischen den beiden soll es keinen unterschied geben bei garnichts").

    **Der Füllkörper ist breiter als der Hohlraum und genauso lang.** Radial
    greift er um ``EPS_GEOM`` ins volle Material — dieselbe Bauart, mit der
    :func:`resize_bore` seinen Ring aufsetzt —, denn ``diameter`` ist am
    tessellierten Netz gemessen und ein Vieleck liegt innerhalb seines
    Umkreises. Axial bleibt er exakt: Die Mündungen liegen in ebenen Flächen,
    und die tesselliert OpenCASCADE ohne Sehnenfehler; eine Zugabe dort ließe
    einen Zapfen stehen, den beim exakten Körper nichts wieder abschneidet.
    """
    return boolean("union", [solid, _centred_bore(position, direction, diameter, depth, EPS_GEOM)])


def cut_bore(
    solid: Solid,
    *,
    position: Vec3,
    direction: Vec3,
    diameter: float,
    depth: float,
) -> Solid:
    """Schneidet eine Bohrung an einer freien Achse, gemessen von ihrer Mitte.

    :func:`bore` nimmt eine der drei Hauptachsen und die **Mündung**; das ist
    die Sicht dessen, der eine Fläche anklickt. Hier ist die Sicht eines
    erkannten Merkmals: eine freie Achse, und die Mitte als Bezug — dieselben
    zwei Zahlen, die :func:`fill_bore` und :func:`resize_bore` lesen. Gebraucht
    wird das beim Versetzen: An der neuen Stelle gibt es noch keine Bohrung,
    also lässt sich dort auch keine ändern.
    """
    return boolean("difference", [solid, _centred_bore(position, direction, diameter, depth, 0.0)])


def _centred_bore(
    position: Vec3, direction: Vec3, diameter: float, depth: float, gain: float
) -> Solid:
    """Der Zylinder einer erkannten Bohrung: Mitte auf ``position``, Achse frei.

    ``gain`` weitet den Radius. Beim Füllen ist er nötig — ``diameter`` ist am
    tessellierten Netz gemessen, und ein Vieleck liegt innerhalb seines
    Umkreises —, beim Schneiden wäre er ein Maßfehler. In der Länge bleibt der
    Körper in beiden Fällen exakt: Die Mündungen liegen in ebenen Flächen, die
    OpenCASCADE ohne Sehnenfehler tesselliert, und eine Zugabe dort ließe beim
    Füllen einen Zapfen stehen, den am exakten Körper nichts wieder abschneidet.
    """
    require()
    if depth <= EPS_GEOM:
        raise ValueError("a detected bore must have a positive depth")
    span = math.sqrt(sum(float(value) ** 2 for value in direction))
    if span <= EPS_GEOM:
        raise ValueError("a bore direction must not be zero")
    unit: Vec3 = (
        float(direction[0]) / span,
        float(direction[1]) / span,
        float(direction[2]) / span,
    )
    start: Vec3 = (
        float(position[0]) - unit[0] * depth / 2.0,
        float(position[1]) - unit[1] * depth / 2.0,
        float(position[2]) - unit[2] * depth / 2.0,
    )
    return _oriented_cylinder(start, unit, diameter / 2.0 + gain, depth)


def _oriented_cylinder(origin: Vec3, direction: Vec3, radius: float, height: float) -> Solid:
    """Ein exakter Zylinder an freier Achse, gemeinsam für die Ringrechnung."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    frame = gp_Ax2(gp_Pnt(*origin), gp_Dir(*direction))
    return Solid(BRepPrimAPI_MakeCylinder(frame, radius, height).Shape())


def transformed(solid: Solid, matrix: Transform) -> Solid:
    """Eine starre Bewegung — Drehung und Verschiebung — exakt auf den Körper.

    Dieselbe Matrix, die der Netz-Zwilling auf seine Dreiecke legt
    (``primitive_ops.placement_transform``), damit ein Umschalten zwischen
    den Kernen (``MENU_TWINS``) den Körper an derselben Stelle lässt.
    ``gp_Trsf`` nimmt nur starre Bewegungen an; eine Matrix mit Scherung oder
    Maßstab weist OpenCASCADE zurück, und das ist richtig so — ein B-Rep
    bleibt nur unter starren Bewegungen exakt. Die Einheitsmatrix lässt den
    Körper, wie er ist, ohne eine Bewegung anzulegen.
    """
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf

    cells = [float(value) for row in matrix[:3] for value in row[:4]]
    identity = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    if all(is_close(cell, wanted) for cell, wanted in zip(cells, identity, strict=True)):
        return solid
    transform = gp_Trsf()
    transform.SetValues(*cells)
    return solid.replacing(BRepBuilderAPI_Transform(solid.shape, transform, False).Shape())


def moved(solid: Solid, offset: Vec3) -> Solid:
    """Verschiebt einen Körper. Starre Bewegungen bleiben auf einem B-Rep exakt."""
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec

    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(offset[0], offset[1], offset[2]))
    # Die Translation ändert nur die Location. Der neue Solid übernimmt
    # anschließend die eigene Geometrie; hier noch einmal tief zu kopieren
    # wäre dieselbe Kopie zweimal.
    return solid.replacing(BRepBuilderAPI_Transform(solid.shape, transform, False).Shape())


def unround(solid: Solid, centre: Vec3, radius: float) -> Solid:
    """Nimmt eine Verrundung weg und stellt die scharfe Kante her (§30).

    Über ``BRepAlgoAPI_Defeaturing`` und nicht über einen Füllkörper: Der
    Kern kennt die Rundungsfläche als Ding und weiß, welche Nachbarn sie
    verlängern muss. Gemessen an einem Quader mit vier Rundungen zu R = 3:
    23884,115 mm³ nach dem Wegnehmen einer, analytisch 23845,487 + 1,9314·20 —
    dieselbe Zahl auf vier Stellen, in 18 ms.

    Gesucht wird die Fläche über ihre **Lage** und ihren Radius, nicht ueber
    einen Index: Ein Index in die Topologie verschiebt sich, sobald davor etwas
    anderes passiert (§21.2, derselbe Grund wie bei :func:`edge_key`).
    """
    require()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Defeaturing

    face = _cylinder_at(solid, centre, radius)
    if face is None:
        raise GeometryError(
            detail=_(
                "An dieser Stelle findet der Kern keine Rundung mehr — ein Schritt "
                "davor hat den Körper verändert. Wählen Sie sie neu."
            ),
            values={"radius_mm": round(radius, 3)},
        )
    builder = BRepAlgoAPI_Defeaturing()
    builder.SetShape(solid.shape)
    builder.AddFaceToRemove(face)
    builder.Build()
    if not builder.IsDone():
        raise GeometryError(
            detail=_(
                "Diese Rundung lässt sich nicht wegnehmen — die Nachbarflächen "
                "treffen sich danach nicht. Nehmen Sie sie zusammen mit den "
                "angrenzenden weg, oder verrunden Sie stattdessen neu."
            ),
        )
    return Solid(builder.Shape())


def _cylinder_at(solid: Solid, centre: Vec3, radius: float) -> Any | None:
    """Die Zylinderfläche dieses Radius an dieser Stelle — oder ``None``."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    best: Any | None = None
    closest = math.inf
    explorer = TopExp_Explorer(solid.shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face(explorer.Current())
        surface = BRepAdaptor_Surface(face)
        explorer.Next()
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        cylinder = surface.Cylinder()
        if abs(cylinder.Radius() - radius) > FILLET_RADIUS_SLACK * max(radius, 1.0):
            continue
        away = _off_the_axis(cylinder, centre)
        if away < closest:
            best, closest = face, away
    return best


def _off_the_axis(cylinder: Any, centre: Vec3) -> float:
    """Wie weit der Punkt von der **Achse** liegt — nicht von ihrem Ursprung.

    ``gp_Cylinder.Location()`` ist irgendein Punkt auf der Achse, den die
    Parametrisierung gewählt hat; bei einer langen Rundung liegt er weit von
    der Stelle entfernt, die der Kunde meint. Gemessen wird deshalb der
    Abstand zur Geraden, und der ist von der Parametrisierung unabhängig.
    """
    spot = cylinder.Location()
    direction = cylinder.Axis().Direction()
    origin = (spot.X(), spot.Y(), spot.Z())
    along = (direction.X(), direction.Y(), direction.Z())
    towards = [centre[index] - origin[index] for index in range(3)]
    reach = sum(towards[index] * along[index] for index in range(3))
    return math.dist(centre, [origin[index] + reach * along[index] for index in range(3)])


def reround(solid: Solid, centre: Vec3, radius: float, wanted: float) -> Solid:
    """Ändert den Radius einer Verrundung — wegnehmen, neu verrunden.

    Dieselbe Zweiteilung wie am Netz (``geom.edges.reround``), und aus
    demselben Grund: Dazwischen liegt die scharfe Kante, und die ist der
    Zustand, an dem beide Hälften prüfbar sind.

    Die Kante wird über ihre **Lage** wiedergefunden: die nächste an der
    Achse der alten Rundung. Ein Index in die Topologie wäre nach dem
    Defeaturing ein anderer.
    """
    sharp = unround(solid, centre, radius)
    described = edges_of(sharp)
    if not described:
        raise GeometryError(
            detail=_(
                "Nach dem Wegnehmen der Rundung ist an dieser Stelle keine Kante "
                "übrig, die sich verrunden ließe."
            ),
        )
    nearest = min(described, key=lambda entry: math.dist(entry.middle, centre))
    return fillet(sharp, wanted, "named", [edge_key(nearest)])
