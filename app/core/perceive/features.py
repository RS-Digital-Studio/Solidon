"""Merkmalserkennung (Bauplan §21.1).

Was ein STL nicht sagt, arbeitet dieses Modul heraus: wo die Bohrungen sind,
welche Flächen eben sind, wo das Netz offen ist. Dieses Vokabular macht den
Rest erst möglich — das Kontextmenü an einer Bohrung, den Agenten, der „das
Loch auf der Oberseite" sagt statt Koordinaten, die Passung zwischen einem
Stift und seinem Loch.

Bohrungen werden gefunden, indem ein Zylinder eingepasst wird, nicht indem
nach runden Kanten gesucht wird: eine Einpassung hat eine Achse, einen Radius
und einen Restfehler — die Antwort lässt sich also beurteilen statt glauben.
Flächen kommen aus koplanaren Flecken, offene Kanten aus dem Netz selbst.

Nichts hier rät im Stillen. Was zu keiner Form passt, ist schlicht kein
Merkmal, und der Steckbrief sagt, wie viele gefunden wurden.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData, face_components
from app.core.log import get_logger
from app.core.types import Feature, FeatureId, Vec3
from app.core.units import EPS_GEOM

_log = get_logger(__name__)

#: Wie gut ein Fleck zu einem Zylinder passen muss, um als Bohrung zu zählen:
#: der Radius darf um diesen Anteil streuen, bevor die Einpassung abgelehnt wird.
CYLINDER_TOLERANCE = 0.08

#: Ein Fleck braucht mindestens so viele Dreiecke, um überhaupt beurteilt zu
#: werden.
MIN_PATCH_FACES = 6

#: Flächen unter diesem Anteil der größten werden nicht eigens gemeldet.
MIN_FACE_SHARE = 0.02

#: …und unter dieser absoluten Größe erst recht nicht, egal wie groß der Rest ist.
#:
#: Der relative Anteil allein hilft nur bei einem konstruierten Teil, wo eine
#: Fläche gegen eine viel größere antritt. Auf einem erzeugten Netz sind alle
#: Facetten gleich groß, also ist jede „mindestens zwei Prozent der größten" —
#: eine Kugel aus 3 400 Dreiecken meldete daraufhin 180 Flächen. Danach war
#: jede Zuordnung mehrdeutig, und die Auswertung hielt bei jeder Operation an
#: (§21.3), womit Weg 3 nach der Reparatur nicht weiterkam.
#:
#: Zwei mal zwei Millimeter ist die kleinste Fläche, an der jemand etwas
#: ansetzt: darunter passt weder ein Schraubenkopf noch ein lesbarer Buchstabe.
MIN_FACE_AREA = 4.0

#: Zylinder unter diesem Durchmesser sind keine Bohrungen, sondern Artefakte.
#:
#: Eine Düse legt 0,4 mm breite Bahnen; ein Loch von 0,05 mm hat kein Werkzeug
#: gemacht und keines wird je hineinpassen. Auf einem erzeugten Netz entstehen
#: solche Zylinderfits an jeder Stelle, an der ein paar Dreiecke zufällig um
#: eine Achse herumstehen.
MIN_HOLE_DIAMETER = 0.5

#: … außer sie bestehen aus mindestens so vielen koplanaren Dreiecken. Ein
#: Zylinderdeckel kommt aus dem Kern als ein Dreieck je Segment — sie zu zählen
#: ist also das, was eine kleine ebene Fläche von einer Scheibe einer gekrümmten
#: unterscheidet.
MIN_FLAT_FACES = 8

#: Ab welchem Knick zwischen zwei Dreiecken eine Kante eine Kante ist und keine
#: Rundung mehr, in Grad.
#:
#: Ein Netz hat keine krummen Flächen, es hat viele gerade. Der Unterschied
#: zwischen einem Zylinder und einem Prisma steht in genau dieser Zahl: bei 48
#: Segmenten stehen benachbarte Mantelstreifen 7,5 Grad auseinander, bei zwölf
#: sind es 30, bei acht 45. Unter der Grenze ist es eine Oberfläche, die
#: jemand als *eine* Fläche anfasst; darüber sind es Seiten eines Vielecks,
#: und die einzeln zu melden ist richtig.
#:
#: Ohne diese Unterscheidung galt jeder Mantelstreifen als eigene ebene
#: Fläche: ein Ø-50-Zylinder mit einer Bohrung trug einundfünfzig Merkmale der
#: Art ``face``. Fusion zeigt für denselben Körper drei Flächen, und ein
#: Merkmalsbaum von ``face_1`` bis ``face_51`` ist keine Auswahl, sondern eine
#: Liste.
CURVATURE_LIMIT = 30.0

#: Ab wann zwei Dreiecke nicht mehr in derselben Ebene liegen, in Grad. Ein
#: Netz aus einer Booleschen Operation ist nie exakt koplanar.
EPS_ANGLE = 0.01


@dataclass(frozen=True, slots=True)
class CylinderFit:
    """Ein Zylinder, eingepasst durch einen Fleck von Dreiecken."""

    axis: Vec3
    centre: Vec3
    radius: float
    residual: float
    """Mittlere Abweichung vom eingepassten Radius, bezogen auf den Radius."""
    inward: bool
    """Wahr, wenn die Normalen zur Achse zeigen — das ist eine Bohrung, kein Zapfen."""

    @property
    def good(self) -> bool:
        return self.residual <= CYLINDER_TOLERANCE and self.radius > EPS_GEOM


@dataclass(frozen=True, slots=True)
class ConeFit:
    """Ein eingepasster Kegel: Spitze, Achse, halber Öffnungswinkel."""

    axis: Vec3
    """Zeigt von der Spitze in den Fleck hinein."""
    apex: Vec3
    centre: Vec3
    """Die Mitte des weitesten Kreises — dort, wo der Kegel die Oberfläche
    trifft.

    **Der Ort des Merkmals, und er ist keine Zierde.** Die Zuordnung liest
    ``params["centre"]`` und nimmt (0, 0, 0), wenn es fehlt (§21.2). Ohne
    diesen Punkt lagen zwei Senkungen an verschiedenen Stellen für sie am
    selben Ort, waren gleich groß und gleich ausgerichtet — und damit
    mehrdeutig. Gemessen am Beispielprojekt *weg2*: zwei Schraubenlöcher, und
    die Auswertung hielt an und fragte, welche Senkung welche ist.

    Die Spitze wäre der falsche Punkt dafür: Sie liegt außerhalb des Körpers,
    wandert mit jedem Winkel und ist bei einem flachen Kegel weit weg."""
    half_angle: float
    """In Grad, zwischen Achse und Mantellinie."""
    radius: float
    """Der Radius an der weitesten Stelle des Flecks."""
    residual: float
    """Mittlere Abweichung vom eingepassten Kegel, bezogen auf den Radius."""
    recess: bool
    """Wahr bei einer Senkung — der Kegel ist ausgehöhlt, nicht aufgesetzt."""

    @property
    def good(self) -> bool:
        return (
            self.residual <= CONE_TOLERANCE
            and self.radius > EPS_GEOM
            and CONE_MIN_ANGLE <= self.half_angle <= CONE_MAX_ANGLE
        )


#: Wie schräg ein Fleck mindestens stehen muss, um als Kegel zu zählen.
#:
#: Darunter ist er ein Zylinder — und zwar auch dann, wenn die Einpassung einen
#: winzigen Öffnungswinkel findet: Ein gebohrtes Loch ist nie ganz gerade, und
#: aus einer Messabweichung einen Kegel mit einer Spitze in 150 000 km
#: Entfernung zu machen, ist keine Erkennung.
CONE_MIN_ANGLE = 5.0

#: Und ab wann er wieder keiner ist: bei 85 Grad Halbwinkel liegt der Fleck
#: fast in einer Ebene, und Ebenen erkennt :func:`detect_faces`.
CONE_MAX_ANGLE = 85.0

#: Wie gut ein Fleck zum eingepassten Kegel passen muss. Dieselbe Schwelle wie
#: beim Zylinder, weil es dieselbe Frage ist.
CONE_TOLERANCE = 0.08

#: Die Merkmalsarten, die diese Datei aus einem Netz lesen kann.
#:
#: Gebraucht wird die Liste außerhalb, und zwar für eine Unterscheidung, die
#: sonst niemand treffen kann: Ein **erzeugtes** Merkmal (§21.2) lässt sich nur
#: dann gegen die Geometrie prüfen, wenn die Erkennung seine Art überhaupt
#: sieht. Ein Gewinde sieht sie nicht — es entsteht in einem Baustein und
#: trägt seinen Namen von dort. Wer es wie eine Bohrung prüfte, verlöre es bei
#: jeder Operation, weil kein Partner zu finden ist.
DETECTABLE_KINDS: frozenset[str] = frozenset({"hole", "pin", "face", "edge_loop", "cone"})


def detect(mesh: MeshData) -> dict[FeatureId, Feature]:
    """Alles, was dieses Modul erkennen kann, mit stabilen Namen.

    Bohrungen und Stifte teilen ihre Suche (siehe :func:`_cylinders`) — beide
    zu erfragen kostet also, was früher eines kostete.
    """
    # **Einmal suchen, zweimal lesen** — hier, und nicht in den beiden
    # Aufrufern. Der Docstring von :func:`_cylinders` beschreibt genau das seit
    # es ihn gibt; die Verdrahtung tat es nicht: ``detect_holes`` und
    # ``detect_pins`` riefen jede für sich, und damit lief die teure Hälfte
    # zweimal je Erkennung.
    #
    # Gemessen an einer Platte mit 81 Bohrungen und 83 280 Dreiecken, beide
    # Wege warm und je der beste von vier Läufen: **464 ms gegen 367 ms, also
    # einundzwanzig Prozent.** Nicht die Hälfte, obwohl ein einzelner Durchgang
    # kalt 210 ms braucht — ``trimesh`` legt Nachbarschaften und Facetten am
    # Körper ab, der zweite Durchgang fand sie also schon vor. Wer hier die
    # kalte Zahl verdoppelt, verspricht das Doppelte des Erreichbaren.
    cylinders, cones = _fitted(mesh)
    found: dict[FeatureId, Feature] = {}
    for feature in [
        *detect_holes(mesh, cylinders),
        *detect_pins(mesh, cylinders),
        *detect_cones(mesh, cones),
        *detect_faces(mesh),
        *detect_edge_loops(mesh),
    ]:
        found[feature.id] = feature
    _log.info("detected %d features", len(found))
    return found


# --- Bohrungen -------------------------------------------------------------------


#: Eine eingepasste Zylinderfläche mit den Dreiecken, auf denen sie sitzt.
Cylinders = list[tuple["CylinderFit", list[int]]]

#: Dasselbe für die Kegel.
Cones = list[tuple["ConeFit", list[int]]]


def _cylinders(mesh: MeshData) -> Cylinders:
    """Nur die Zylinder, für jeden, der die Kegel nicht braucht."""
    return _fitted(mesh)[0]


def _fitted(mesh: MeshData) -> tuple[Cylinders, Cones]:
    """Jeder gekrümmte Fleck des Körpers, einmal eingepasst.

    Bohrungen und Stifte sind dieselbe Suche, zweimal gelesen, und die Suche
    ist die teure Hälfte: an einem Körper mit einer Million Dreiecken kosten
    die Facetten und die zusammenhängenden Flecken Sekunden. Sie zweimal zu
    machen verdoppelte die Erkennungszeit für nichts — also passiert sie hier,
    und beide Aufrufer filtern das Ergebnis.
    """
    body = mesh.raw
    if not len(body.faces):
        return [], []

    # Eine Bohrungswand besteht aus vielen schmalen ebenen Segmenten — „gehört zu
    # einer Facette" ist also nicht die Trennlinie, „gehört zu einer *großen*
    # Facette" schon.
    planar = _large_facet_faces(body)
    curved = [index for index in range(len(body.faces)) if index not in planar]
    if not curved:
        return [], []

    found: Cylinders = []
    cones: Cones = []
    for patch in _connected_patches(body, curved):
        if len(patch) < MIN_PATCH_FACES:
            continue
        # **Die Normalen entscheiden, welche Form es ist — nicht der
        # Rückstand.** Der naheliegende Weg wäre, zuerst einen Zylinder
        # einzupassen und den Kegel als Auffang zu nehmen. Er ist falsch, und
        # der Fall, der es zeigt, ist ein aufgesetzter Kegel: Jede seiner
        # Facetten ist **ein** Dreieck von der Grundfläche zur Spitze, deren
        # Schwerpunkt liegt auf einem Drittel der Höhe — und damit liegen alle
        # Schwerpunkte auf **einem Kreis**. Die Zylindereinpassung rechnet über
        # die Schwerpunkte und findet einen tadellosen Zylinder, Rückstand
        # 0,0000, an einem Kegel mit 31 Grad. Ein Rückstand kann das nicht
        # sehen; die Normalen können es: Beim Zylinder stehen sie senkrecht auf
        # der Achse, beim Kegel um ``sin`` des Halbwinkels daneben.
        #
        # Also: Die Form kommt aus dem Winkel, die Güte aus dem Rückstand.
        cone = fit_cone(body, patch)
        if cone is not None and cone.half_angle >= CONE_MIN_ANGLE:
            if cone.good and _fits_in_the_body(mesh, cone):
                cones.append((cone, patch))
            continue
        fit = fit_cylinder(body, patch)
        if fit is not None and fit.good and _fits_in_the_body(mesh, fit):
            found.append((fit, patch))

    # Nach Position sortiert, damit die Nummerierung für denselben Körper
    # reproduzierbar ist. **Alle drei Achsen**, nicht nur X und Y: Zwei
    # koaxiale Bohrungen — eine Durchführung durch zwei Wände, die häufigste
    # Doppelbohrung überhaupt — haben dieselbe Mitte in X und Y. Der Vergleich
    # endete dort unentschieden, und welche von beiden `hole_1` wurde, hing an
    # der Reihenfolge der Flecken. Genau das darf eine Provenienz-ID nicht
    # (§21.2): Eine Op, die an `hole_2` hängt, sitzt nach der nächsten
    # Auswertung an der anderen.
    found.sort(
        key=lambda entry: (
            round(entry[0].centre[0], 3),
            round(entry[0].centre[1], 3),
            round(entry[0].centre[2], 3),
        )
    )
    # Kegel nach ihrer Spitze, aus demselben Grund: Die Nummer eines Merkmals
    # ist eine Provenienz-ID, und die darf nicht an der Reihenfolge der Flecken
    # hängen (§21.2).
    cones.sort(
        key=lambda entry: (
            round(entry[0].centre[0], 3),
            round(entry[0].centre[1], 3),
            round(entry[0].centre[2], 3),
        )
    )
    return found, cones


def detect_holes(mesh: MeshData, cylinders: Cylinders | None = None) -> list[Feature]:
    """Zylindrische Flecken, deren Normalen nach innen zeigen (§21.1).

    ``cylinders`` ist die schon gefundene Einpassung. Wer sie mitgibt, spart den
    teuren Teil; wer sie auslässt, bekommt ihn — die Funktion bleibt allein
    aufrufbar, weil sie es überall ist, wo nur die Bohrungen gebraucht werden.
    """
    body = mesh.raw
    found = [
        entry
        for entry in (_cylinders(mesh) if cylinders is None else cylinders)
        if entry[0].inward and entry[0].radius * 2.0 >= MIN_HOLE_DIAMETER
    ]
    return [
        Feature(
            id=f"hole_{number}",
            kind="hole",
            provenance="detected",
            params={
                "diameter": round(fit.radius * 2.0, 4),
                "axis": fit.axis,
                "centre": fit.centre,
                "depth": round(_patch_extent(body, patch, fit.axis), 4),
                "through": _is_through(mesh, fit),
                "residual": round(fit.residual, 4),
            },
            face_indices=tuple(patch),
        )
        for number, (fit, patch) in enumerate(found, start=1)
    ]


def _fits_in_the_body(mesh: MeshData, fit: CylinderFit | ConeFit) -> bool:
    """Passt dieser Zylinder überhaupt in den Körper, der ihn tragen soll?

    Kein Grenzwert, ein Widerspruch: Eine Bohrung oder ein Zapfen von Ø 631 mm
    kann nicht auf einem Teil sitzen, das quer zu seiner Achse 231 mm misst.
    Gemessen wird darum **quer zur eigenen Achse** und nicht an der dünnsten
    Kante — ein Loch Ø 7,1 durch eine 6,4 mm dünne Scheibe ist normal, dort
    liegt die dünne Richtung ja in der Achse. Diese Unterscheidung ist der
    ganze Punkt: nach der dünnsten Kante gemessen fielen 92 von 165 Bohrungen
    durch, davon die meisten zu Recht vorhanden.

    **Warum es das braucht.** Die Einpassung ist geometrisch nicht falsch: ein
    sanft gebogener Arm *ist* örtlich ein Zylinder mit großem Radius, und der
    Rückstand bleibt klein. Als *Merkmal* ist er trotzdem keines — ein Zapfen
    ist das, was man mit einer Bohrung paart (§14), und mit einem Ø 631 paart
    niemand etwas. Gemessen an sieben heruntergeladenen Modellen: 21 von 112
    Zapfen und 19 von 165 Bohrungen waren breiter als ihr eigener Körper.

    Und es blieb nicht bei der Anzeige. Der Vorschlag *Wände* im
    Druckeinstellungen-Dialog rechnet aus dem dicksten Verbinder, wie viele
    Wände sich in seiner Mitte treffen — aus Ø 631,6 wurden **376 Wände**, an
    einem anderen Modell 185 784. Das ist an seiner Wurzel behoben (nur erzeugte
    Zapfen zählen dort), aber ein Merkmal, das nicht in seinen Körper passt,
    gehört in keine Liste und in kein Kontextmenü.
    """
    import numpy as np

    size = mesh.bounds.size
    axis = np.abs(np.asarray(fit.axis, dtype=float))
    if float(np.max(axis)) <= EPS_GEOM:
        return True
    along = int(np.argmax(axis))
    across = max(size[index] for index in range(3) if index != along)
    return fit.radius * 2.0 <= across + EPS_GEOM


def detect_pins(mesh: MeshData, cylinders: Cylinders | None = None) -> list[Feature]:
    """Zylindrische Flecken, deren Normalen nach außen zeigen (§21.1).

    Dieselbe Einpassung wie bei einer Bohrung, andersherum gelesen. Sie lohnt
    aus einem Grund: ein Stift ist das, womit eine Bohrung gepaart wird (§14),
    und eine Passung braucht beide Enden. Auto Split benennt die Stifte, die es
    selbst macht — dieser hier ist für das Teil, das von woanders kam.
    """
    body = mesh.raw
    found = [
        entry
        for entry in (_cylinders(mesh) if cylinders is None else cylinders)
        if not entry[0].inward
    ]
    return [
        Feature(
            id=f"pin_{number}",
            kind="pin",
            provenance="detected",
            params={
                "diameter": round(fit.radius * 2.0, 4),
                "axis": fit.axis,
                "centre": fit.centre,
                "depth": round(_patch_extent(body, patch, fit.axis), 4),
                "residual": round(fit.residual, 4),
            },
            face_indices=tuple(patch),
        )
        for number, (fit, patch) in enumerate(found, start=1)
    ]


def detect_cones(mesh: MeshData, cones: Cones | None = None) -> list[Feature]:
    """Kegelige Flecken (§21.1): Senkungen, Fasen an Bohrungen, Verjüngungen.

    Warum es die Art überhaupt braucht: Ohne sie ist eine Senkung eine Bohrung
    plus ein namenloser Haufen Dreiecke — der Agent kann nicht auf sie zeigen,
    und Leitprinzip 5 lässt ihm keinen zweiten Weg, weil er Koordinaten nicht
    erzeugt. Der Winkel steht als **Öffnungswinkel** in den Parametern und
    nicht als Halbwinkel: Eine Senkung heißt „90 Grad", und das ist der ganze
    Kegel.
    """
    found = _fitted(mesh)[1] if cones is None else cones
    return [
        Feature(
            id=f"cone_{number}",
            kind="cone",
            provenance="detected",
            params={
                "diameter": round(fit.radius * 2.0, 4),
                "angle": round(fit.half_angle * 2.0, 3),
                "axis": fit.axis,
                # Die Spitze steht **nicht** in den Parametern, obwohl die
                # Einpassung sie kennt: ``moved_features`` nimmt „centre",
                # „position", „axis" und „normal" mit, sonst nichts (§21.2).
                # Ein Punkt, der eine Drehung nicht mitmacht, ist nach der
                # ersten Transformation eine falsche Zahl im Steckbrief — und
                # aus Mitte, Achse und Winkel ist die Spitze ohnehin zu rechnen.
                "centre": fit.centre,
                "recess": fit.recess,
                "residual": round(fit.residual, 4),
            },
            face_indices=tuple(patch),
        )
        for number, (fit, patch) in enumerate(found, start=1)
    ]


def _curved_faces(body: trimesh.Trimesh) -> set[int]:
    """Dreiecke, die auf einer gerundeten Oberfläche sitzen.

    Erkannt an der Naht zu ihren Nachbarn: koplanar (null Grad) ist dieselbe
    Fläche, ein deutlicher Knick ist eine Kante, und alles dazwischen ist die
    Stufe einer Rundung, die das Netz nur nicht rund darstellen kann.
    """
    if not len(body.face_adjacency):
        return set()
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    rounded = (angles > EPS_ANGLE) & (angles < CURVATURE_LIMIT)
    if not rounded.any():
        return set()
    pairs = np.asarray(body.face_adjacency)[rounded]
    return {int(index) for index in pairs.ravel()}


def _large_facet_faces(body: trimesh.Trimesh) -> set[int]:
    """Dreiecke, die zu einem ebenen Fleck gehören, der groß genug für eine
    eigene Fläche ist.

    Zwei Wege sich zu qualifizieren, und der zweite ist keine Zierde. Die
    Fläche allein wird gegen die größte Fläche des Körpers gemessen, und auf
    einer Platte mit einem Stift darauf ist die Stiftoberseite unter zwei
    Prozent der Platte — sie zählte also als gekrümmt, schloss sich der
    Stiftwand an, und die Zylinder-Einpassung über Wand-plus-Deckel kam als gar
    nichts heraus. Ein Fleck aus vielen koplanaren Dreiecken ist eine Fläche,
    egal welche Größe er neben dem Rest des Teils hat.
    """
    facets = list(body.facets)
    if not facets:
        return set()
    areas = [float(body.area_faces[facet].sum()) for facet in facets]
    limit = max(areas) * MIN_FACE_SHARE
    # Ein Mantelstreifen eines Zylinders ist groß genug für diese Schwelle und
    # trotzdem keine eigene Fläche — die Naht zu seinen Nachbarn sagt es. Der
    # zweite Weg bleibt davon unberührt: ein Fleck aus vielen koplanaren
    # Dreiecken ist eine Fläche, auch wenn er auf einer Rundung sitzt.
    curved = _curved_faces(body)
    return {
        int(index)
        for facet, area in zip(facets, areas, strict=True)
        if len(facet) >= MIN_FLAT_FACES
        or (area >= limit and not any(int(index) in curved for index in facet))
        for index in facet
    }


def fit_cylinder(body: trimesh.Trimesh, patch: list[int]) -> CylinderFit | None:
    """Kleinste-Quadrate-Zylinder durch einen Fleck von Dreiecken.

    Die Achse ist die Richtung, auf der jede Normale senkrecht steht — der
    Eigenvektor der Normalen-Kovarianz mit dem kleinsten Eigenwert.
    """
    normals = np.asarray(body.face_normals[patch], dtype=float)
    centres = np.asarray(body.triangles_center[patch], dtype=float)

    _values, vectors = np.linalg.eigh(normals.T @ normals)
    axis = vectors[:, 0]
    axis = axis / float(np.linalg.norm(axis))

    # In die Ebene senkrecht zur Achse projizieren und dort einen Kreis einpassen.
    basis_u, basis_v = _plane_basis(axis)
    flat = np.column_stack([centres @ basis_u, centres @ basis_v])
    centre_2d, radius = _fit_circle(flat)
    if radius <= EPS_GEOM:
        return None

    distances = np.linalg.norm(flat - centre_2d, axis=1)
    residual = float(np.mean(np.abs(distances - radius)) / radius)

    origin = centres.mean(axis=0)
    along = float(origin @ axis)
    centre = basis_u * centre_2d[0] + basis_v * centre_2d[1] + axis * along

    towards = centre - centres
    towards = towards - np.outer(towards @ axis, axis)
    inward = bool(np.mean(np.einsum("ij,ij->i", normals, towards)) > 0)

    return CylinderFit(
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        centre=(float(centre[0]), float(centre[1]), float(centre[2])),
        radius=float(radius),
        residual=residual,
        inward=inward,
    )


def fit_cone(body: trimesh.Trimesh, patch: list[int]) -> ConeFit | None:
    """Kleinste-Quadrate-Kegel durch einen Fleck von Dreiecken.

    Drei Schritte, alle drei linear — kein Zufall, keine Iteration, kein
    Startwert (§11.3):

    **Die Achse** kommt aus den Normalen. Bei einem Zylinder liegen sie auf
    einem Großkreis der Einheitskugel, bei einem Kegel auf einem **Kleinkreis**;
    die Ebene dieses Kreises hat die Kegelachse als Normale. Also derselbe
    Eigenvektor wie beim Zylinder, nur an den **zentrierten** Normalen — und
    genau der Versatz, den das Zentrieren herausnimmt, ist die Auskunft: Er
    ist ``sin`` des halben Öffnungswinkels. Null heißt Zylinder.

    **Die Spitze** liegt auf jeder Tangentialebene des Kegels — das ist die
    Eigenschaft, die ihn vom Zylinder trennt und sie ist exakt. Aus ``n · p``
    je Dreieck wird damit ein überbestimmtes lineares Gleichungssystem, dessen
    Lösung die Spitze ist. Beim Zylinder ist dasselbe System entartet, und die
    Lösung wandert ins Unendliche — auch das eine brauchbare Auskunft.

    **Der Rückstand** vergleicht den gemessenen Abstand zur Achse mit dem, den
    der Kegel an dieser Höhe verlangt. Gemessen an einer 90°-Senkung aus dem
    Korpus: Halbwinkel 44,94 Grad bei echten 45, Spitze auf vier Stellen
    getroffen, Rückstand 0,0003.
    """
    normals = np.asarray(body.face_normals[patch], dtype=float)
    centres = np.asarray(body.triangles_center[patch], dtype=float)

    _values, vectors = np.linalg.eigh(_centred_moment(normals))
    axis = vectors[:, 0]
    axis = axis / float(np.linalg.norm(axis))

    apex, *_ = np.linalg.lstsq(normals, np.einsum("ij,ij->i", normals, centres), rcond=None)
    towards = centres - apex
    # Die Achse zeigt von der Spitze in den Fleck. Ohne diese Festlegung wäre
    # das Vorzeichen des Versatzes bedeutungslos, und mit ihm die Unterscheidung
    # zwischen einer Senkung und einem aufgesetzten Kegel.
    if float(np.mean(towards @ axis)) < 0.0:
        axis = -axis
    offset = float(np.mean(normals @ axis))
    sine = min(1.0, abs(offset))
    half_angle = math.degrees(math.asin(sine))
    if sine <= EPS_GEOM:
        return None

    along = towards @ axis
    radial = np.linalg.norm(towards - np.outer(along, axis), axis=1)
    mean_radius = float(np.mean(radial))
    if mean_radius <= EPS_GEOM:
        return None
    expected = along * math.tan(math.radians(half_angle))
    residual = float(np.mean(np.abs(radial - expected)) / mean_radius)

    # Der weiteste Punkt kommt aus den **Ecken** und nicht aus den
    # Dreiecksmitten: Die Mitte einer Facette liegt ein Stück unterhalb ihrer
    # oberen Kante, und der Durchmesser einer Senkung ist der, den man messen
    # kann — nicht der, den die Facettenmitten hergeben.
    corners = np.asarray(body.vertices[np.unique(body.faces[patch])], dtype=float)
    reach = (corners - apex) @ axis
    widest = float(reach.max())
    outer = np.linalg.norm(corners - apex - np.outer(reach, axis), axis=1)

    return ConeFit(
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        apex=(float(apex[0]), float(apex[1]), float(apex[2])),
        centre=tuple(float(value) for value in apex + axis * widest),  # type: ignore[arg-type]
        half_angle=half_angle,
        radius=float(outer.max()),
        residual=residual,
        # Der äußere Normalenvektor einer **Senkung** zeigt in die Mulde und
        # damit in Achsenrichtung; bei einem aufgesetzten Kegel weg von ihr.
        # Hergeleitet: n · a = -sin(Halbwinkel) für den massiven Kegel, +sin für
        # die Mulde.
        recess=offset > 0.0,
    )


def _centred_moment(normals: np.ndarray) -> np.ndarray:
    """Das zweite Moment der Normalen **um ihren Mittelwert**.

    Der Unterschied zu :func:`fit_cylinder` ist genau dieses Zentrieren, und er
    ist der ganze Unterschied zwischen den beiden Formen.
    """
    centred = normals - normals.mean(axis=0)
    return centred.T @ centred


def _plane_basis(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    basis_u = np.cross(axis, helper)
    basis_u = basis_u / float(np.linalg.norm(basis_u))
    return basis_u, np.cross(axis, basis_u)


def _fit_circle(points: np.ndarray) -> tuple[np.ndarray, float]:
    """Algebraische Kreiseinpassung (Kåsa): linear, stabil genug für ein
    gebohrtes Loch.
    """
    matrix = np.column_stack([points[:, 0], points[:, 1], np.ones(len(points))])
    target = points[:, 0] ** 2 + points[:, 1] ** 2
    solution, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    centre = np.array([solution[0] / 2.0, solution[1] / 2.0])
    radius = math.sqrt(max(solution[2] + centre @ centre, 0.0))
    return centre, radius


def _patch_extent(body: trimesh.Trimesh, patch: list[int], axis: Vec3) -> float:
    """Wie weit der Fleck entlang seiner eigenen Achse reicht — die Tiefe der
    Bohrung.
    """
    points = np.asarray(body.vertices[np.unique(body.faces[patch])], dtype=float)
    along = points @ np.asarray(axis, dtype=float)
    return float(along.max() - along.min())


def _is_through(mesh: MeshData, fit: CylinderFit) -> bool:
    """Eine Bohrung ist durchgehend, wenn sie so tief ist, wie der Körper
    entlang ihrer Achse dick ist.
    """
    axis = np.asarray(fit.axis, dtype=float)
    corners = np.asarray(mesh.raw.vertices, dtype=float) @ axis
    thickness = float(corners.max() - corners.min())
    return thickness > 0 and _bore_depth(mesh, fit) >= thickness - EPS_GEOM * 10


def _bore_depth(mesh: MeshData, fit: CylinderFit) -> float:
    axis = np.asarray(fit.axis, dtype=float)
    centre = np.asarray(fit.centre, dtype=float)
    points = np.asarray(mesh.raw.vertices, dtype=float)
    radial = points - centre
    radial = radial - np.outer(radial @ axis, axis)
    on_wall = np.abs(np.linalg.norm(radial, axis=1) - fit.radius) < fit.radius * 0.1
    if not on_wall.any():
        return 0.0
    along = points[on_wall] @ axis
    return float(along.max() - along.min())


def _connected_patches(body: trimesh.Trimesh, faces: list[int]) -> list[list[int]]:
    """Gruppiert die gegebenen Dreiecke in zusammenhängende Flecken.

    **Ein Fleck endet an einer Kante.** Zusammenhängend allein war die falsche
    Trennlinie, und der Fall, der es zeigt, ist die häufigste Bohrung in einem
    Druckteil: Bei einer gesenkten Bohrung hängen Kegelwand und Bohrungswand
    aneinander. Ohne Trennung wurden sie **ein** Fleck, die Zylindereinpassung
    darüber kam als nichts heraus — und damit war nicht nur die Senkung
    unerkannt, sondern die Bohrung selbst. Gemessen an
    ``plate_countersunk.stl``: null Bohrungen statt einer, und kein Befund
    darüber.

    Getrennt wird an derselben Schwelle, die :func:`_curved_faces` schon
    benutzt (``CURVATURE_LIMIT``, 30 Grad) — dort steht der Satz, der sie
    begründet: „ein deutlicher Knick ist eine Kante, und alles dazwischen ist
    die Stufe einer Rundung". Der Übergang Bohrung → 90°-Senkung ist ein Knick
    von 45 Grad; die Facetten eines gebohrten Zylinders liegen bei vier Grad.
    Ein Zylinder mit weniger als zwölf Segmenten zerfällt dabei — der hat aber
    Facetten, die groß genug für eigene Flächen sind, und wird ohnehin nicht
    als Zylinder gelesen.
    """
    wanted = set(faces)
    pairs = np.asarray(body.face_adjacency)
    if len(pairs):
        angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
        pairs = pairs[angles < CURVATURE_LIMIT]
    adjacency = [pair for pair in pairs if pair[0] in wanted and pair[1] in wanted]
    if not adjacency:
        return [[index] for index in faces]
    groups = trimesh.graph.connected_components(
        np.asarray(adjacency), nodes=np.asarray(faces), engine="scipy"
    )
    return [[int(index) for index in group] for group in groups]


# --- Flächen ---------------------------------------------------------------------


def detect_faces(mesh: MeshData) -> list[Feature]:
    """Koplanare Flecken: Normale, Fläche, Mittelpunkt (§21.1)."""
    body = mesh.raw
    facets = list(body.facets)
    if not facets:
        return []

    areas = [float(body.area_faces[facet].sum()) for facet in facets]
    largest = max(areas)
    # Dieselbe Schwelle, die die Bohrungserkennung benutzt — ein Fleck ist also
    # entweder eine Fläche oder Teil einer gekrümmten Oberfläche, nie beides,
    # nie keines. Was auf einer Rundung sitzt, wird dort als Zylinder gemeldet
    # und hier nicht noch einmal als achtundvierzig Rechtecke.
    planar = _large_facet_faces(body)
    entries = [
        (facet, area)
        for facet, area in zip(facets, areas, strict=True)
        if area >= largest * MIN_FACE_SHARE
        and area >= MIN_FACE_AREA
        and all(int(index) in planar for index in facet)
    ]
    entries.sort(key=lambda entry: -entry[1])

    features: list[Feature] = []
    for number, (facet, area) in enumerate(entries, start=1):
        normal = np.asarray(body.face_normals[facet[0]], dtype=float)
        # Flächengewichtet, nicht als Mittel über die Dreiecke: sonst hängt der
        # Mittelpunkt an der Vernetzung statt an der Form. Eine Bohrung in eine
        # Platte lässt rund um sich viele kleine Dreiecke entstehen, und der
        # ungewichtete Mittelwert wandert daraufhin zum Loch — bei einem
        # 60-auf-40-Deckel um 16,8 mm. Die Zuordnung (§21.2) hielt die Fläche
        # danach für eine andere und meldete die alte als verwaist.
        weights = np.asarray(body.area_faces[facet], dtype=float)
        points = np.asarray(body.triangles_center[facet], dtype=float)
        total = float(weights.sum())
        centre = (
            (points * weights[:, None]).sum(axis=0) / total
            if total > EPS_GEOM
            else points.mean(axis=0)
        )
        features.append(
            Feature(
                id=f"face_{number}",
                kind="face",
                provenance="detected",
                params={
                    "area": round(area, 4),
                    "normal": (float(normal[0]), float(normal[1]), float(normal[2])),
                    "centre": (float(centre[0]), float(centre[1]), float(centre[2])),
                },
                face_indices=tuple(int(index) for index in facet),
            )
        )
    return features


# --- Offene Kanten ---------------------------------------------------------------


def detect_edge_loops(mesh: MeshData) -> list[Feature]:
    """Offene Kanten sind Defekte, und zu wissen wo sie sind, ist die halbe
    Reparatur.
    """
    body = mesh.raw
    single = trimesh.grouping.group_rows(body.edges_sorted, require_count=1)
    if not len(single):
        return []

    edges = np.asarray(body.edges_sorted)[single]
    points = np.asarray(body.vertices[np.unique(edges)], dtype=float)
    centre = points.mean(axis=0)
    return [
        Feature(
            id="edge_loop_1",
            kind="edge_loop",
            provenance="detected",
            params={
                "open_edges": len(single),
                "centre": (float(centre[0]), float(centre[1]), float(centre[2])),
            },
        )
    ]


# --- Komponenten -----------------------------------------------------------------


def component_count(mesh: MeshData) -> int:
    """Wie viele getrennte Körper das Netz enthält (§21.1)."""
    return len(face_components(mesh.raw))
