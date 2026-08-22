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
from typing import NamedTuple

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

#: Ab welchem Anteil an der größten Fläche ein ebener Fleck **auch dann** eine
#: Fläche ist, wenn er eine Rundung berührt.
#:
#: Der Ausschluss über die Berührung ist gegen **Mantelstreifen** gebaut: Ein
#: Streifen einer Zylinderwand ist koplanar und groß genug für die kleine
#: Schwelle, aber keine eigene Fläche. Er traf jedoch auch das Gegenteil. An
#: einem Quader mit **einer** verrundeten Kante galten zwei ebene Facetten von
#: 1110 und 510 mm² als gekrümmt — auf einem Körper, dessen größte Fläche 1200
#: mm² misst —, weil sie an die Rundung stoßen. Sie hängten sich dem
#: Verrundungsfleck an, und die Kreiseinpassung darüber gab **14,46 statt 3**:
#: Kåsa gewichtet quadratisch, und vier Punkte in bis zu 25 mm Abstand ziehen
#: den Kreis auf. Aus einer Verrundung R 3 wurde so ein Zapfen Ø 28,9, den es
#: nicht gibt.
#:
#: Der Abstand zwischen beiden Fällen ist groß: An der **Gesamtoberfläche**
#: gemessen sind die zwei Facetten 21 und 10 Prozent, ein Mantelstreifen
#: desselben Körpers 0,11 Prozent und einer des Torus 0,09. Fünf Prozent
#: liegen mit Faktor fünfzig Abstand dazwischen.
BROAD_FACE_SHARE = 0.05

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

#: Und ab wann ein Winkel überhaupt eine Krümmung ist. Darunter ist er
#: Rechenrauschen einer ebenen Fläche: Aus 0,001 Grad auf 3 mm Kantenlänge
#: würde ein Radius von 170 Metern.
FLAT_ANGLE = 0.5


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


@dataclass(frozen=True, slots=True)
class SphereFit:
    """Eine eingepasste Kugel: Mittelpunkt und Radius."""

    centre: Vec3
    radius: float
    residual: float
    """Mittlere Abweichung vom eingepassten Radius, bezogen auf den Radius."""
    recess: bool
    """Wahr bei einer Pfanne — die Kugel ist ausgehöhlt, nicht aufgesetzt."""

    @property
    def good(self) -> bool:
        return self.residual <= ROUND_TOLERANCE and self.radius > EPS_GEOM


@dataclass(frozen=True, slots=True)
class TorusFit:
    """Ein eingepasster Torus: Achse, Mittelpunkt, Ring- und Röhrenradius."""

    axis: Vec3
    centre: Vec3
    """Die Mitte des Rings, auf der Achse."""
    ring_radius: float
    """Vom Mittelpunkt zur Mittellinie der Röhre."""
    tube_radius: float
    """Der Radius der Röhre selbst — an einer Verrundung ihr Radius."""
    residual: float
    recess: bool
    """Wahr bei einer Kehle — die Röhre ist ausgehöhlt, nicht aufgesetzt."""

    @property
    def good(self) -> bool:
        return (
            self.residual <= ROUND_TOLERANCE
            and self.tube_radius > EPS_GEOM
            # Ein Torus, dessen Ring nicht weiter ist als seine Röhre, hat kein
            # Loch in der Mitte — das ist keine Form, die jemand meint.
            and self.ring_radius > self.tube_radius
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

#: Wie gut ein Fleck zur eingepassten Kugel oder zum Torus passen muss —
#: **strenger als bei Zylinder und Kegel, und das ist gemessen.**
#:
#: Eine 90°-Senkung passt erstaunlich gut auf eine Kugel: Rückstand 0,054, also
#: unter der Schwelle von 0,08, die für Zylinder und Kegel gilt. Die echte
#: Kalotte aus ``sphere_socket.stl`` liefert 0,0003 — zwei Größenordnungen
#: darunter. Zwischen beiden liegt 0,02 mit Sicherheit nach beiden Seiten.
#:
#: Genau davor warnt §41: Ein Verfahren, das Grundformen sucht, findet auch
#: welche, die niemand gemeint hat. Die Schwelle ist die eine Hälfte der
#: Antwort, die Reihenfolge in :func:`_fitted` die andere — Kugel und Torus
#: werden erst gefragt, wenn Zylinder und Kegel abgelehnt haben.
ROUND_TOLERANCE = 0.02

#: Wie stark die Achse einer Senkung von der ihrer Bohrung abweichen darf, in
#: Grad. Beide entstehen in derselben Aufspannung — was hier streut, ist die
#: Einpassung und nicht die Fertigung.
SINK_AXIS_LIMIT = 2.0

#: Wie weit eine Senkung von ihrer Bohrung abliegen darf, quer zur Achse wie
#: längs, jeweils als Anteil des Bohrungsradius.
#:
#: Der Maßstab ist die Bohrung, denn die Senkung gehört zu ihr oder zu nichts.
#: Längs ist der Wert die Antwort auf den Fall, den die Sortierung in
#: :func:`_fitted` schon einmal nennt: zwei koaxiale Bohrungen durch zwei
#: Wände, jede mit eigener Senkung. Ohne diese Grenze zählte die Senkung der
#: zweiten Wand zur Bohrung der ersten, und ein Sackloch in der ersten Wand
#: wäre plötzlich durchgehend.
SINK_FIT_LIMIT = 0.25

#: Die Merkmalsarten, die diese Datei aus einem Netz lesen kann.
#:
#: Gebraucht wird die Liste außerhalb, und zwar für eine Unterscheidung, die
#: sonst niemand treffen kann: Ein **erzeugtes** Merkmal (§21.2) lässt sich nur
#: dann gegen die Geometrie prüfen, wenn die Erkennung seine Art überhaupt
#: sieht. Ein Gewinde sieht sie nicht — es entsteht in einem Baustein und
#: trägt seinen Namen von dort. Wer es wie eine Bohrung prüfte, verlöre es bei
#: jeder Operation, weil kein Partner zu finden ist.
DETECTABLE_KINDS: frozenset[str] = frozenset(
    {"hole", "pin", "face", "edge_loop", "cone", "sphere", "torus"}
)


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
    fitted = _fitted(mesh)
    found: dict[FeatureId, Feature] = {}
    for feature in [
        *detect_holes(mesh, fitted.cylinders, fitted.cones),
        *detect_pins(mesh, fitted.cylinders),
        *detect_cones(mesh, fitted.cones),
        *detect_spheres(mesh, fitted.spheres),
        *detect_tori(mesh, fitted.tori),
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

#: Und für die beiden runden Formen aus der Ausbaustufe (§41).
Spheres = list[tuple["SphereFit", list[int]]]
Tori = list[tuple["TorusFit", list[int]]]


class Fitted(NamedTuple):
    """Was eine Fleckensuche an Grundformen hergibt.

    Ein benanntes Tupel und keine vier Rückgabewerte: Die Liste wächst mit
    jeder Form, die §41 noch vorsieht, und ``fitted.spheres`` liest sich auch
    dann noch, wenn es sechs sind.
    """

    cylinders: Cylinders
    cones: Cones
    spheres: Spheres
    tori: Tori


def _cylinders(mesh: MeshData) -> Cylinders:
    """Nur die Zylinder, für jeden, der die übrigen Formen nicht braucht."""
    return _fitted(mesh).cylinders


def _fitted(mesh: MeshData) -> Fitted:
    """Jeder gekrümmte Fleck des Körpers, einmal eingepasst.

    Bohrungen und Stifte sind dieselbe Suche, zweimal gelesen, und die Suche
    ist die teure Hälfte: an einem Körper mit einer Million Dreiecken kosten
    die Facetten und die zusammenhängenden Flecken Sekunden. Sie zweimal zu
    machen verdoppelte die Erkennungszeit für nichts — also passiert sie hier,
    und beide Aufrufer filtern das Ergebnis.
    """
    body = mesh.raw
    if not len(body.faces):
        return Fitted([], [], [], [])

    # Eine Bohrungswand besteht aus vielen schmalen ebenen Segmenten — „gehört zu
    # einer Facette" ist also nicht die Trennlinie, „gehört zu einer *großen*
    # Facette" schon.
    planar = _large_facet_faces(body)
    curved = [index for index in range(len(body.faces)) if index not in planar]
    if not curved:
        return Fitted([], [], [], [])

    found: Cylinders = []
    cones: Cones = []
    spheres: Spheres = []
    tori: Tori = []

    def classify(patch: list[int]) -> bool:
        """Die erste Form, die auf diesen Fleck passt — oder keine."""
        if len(patch) < MIN_PATCH_FACES:
            return False
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
                return True
            # Ein Kegelwinkel schließt den Zylinder aus — das sagen die
            # Normalen, und daran ändert ein schlechter Rückstand nichts. Die
            # runden Formen sind damit aber nicht ausgeschlossen: Eine Kalotte
            # hat einen Kegelwinkel, ohne ein Kegel zu sein.
        else:
            fit = fit_cylinder(body, patch)
            if fit is not None and fit.good and _fits_in_the_body(mesh, fit):
                found.append((fit, patch))
                return True

        # **Erst hier, und das ist die halbe Antwort auf §41.** Kugel und Torus
        # werden gefragt, nachdem Zylinder und Kegel abgelehnt haben — nicht
        # daneben. Eine Senkung passt auf eine Kugel besser, als man denkt
        # (Rückstand 0,054), und ein `hole_1`, das plötzlich `sphere_1` hieße,
        # wäre für jede Bohrungs-Operation unsichtbar. Die andere Hälfte der
        # Antwort ist ``ROUND_TOLERANCE``.
        ball = fit_sphere(body, patch)
        if ball is not None and ball.good and _fits_in_the_body_by_size(mesh, ball.radius):
            spheres.append((ball, patch))
            return True
        ring = fit_torus(body, patch)
        if ring is not None and ring.good and _fits_in_the_body_by_size(mesh, ring.ring_radius):
            tori.append((ring, patch))
            return True
        return False

    jumps: np.ndarray | None = None
    for patch in _connected_patches(body, curved):
        if len(patch) < MIN_PATCH_FACES or classify(patch):
            continue
        # **Zweite Runde für das, was nichts ergeben hat.** Eine Verrundung
        # schließt tangential an, also trennt kein Knick sie ab — Mantel und
        # Kehle einer Säule liegen in einem Fleck, auf den keine Form passt.
        # Nachgetrennt wird deshalb erst hier: Wo etwas erkannt wurde, bleibt
        # es, wie es ist (siehe :func:`_split_by_curvature`).
        if jumps is None:
            # **Träge, und das ist der Punkt.** Die Rechnung geht über alle
            # Nachbarpaare des Körpers; ein Netz, an dem jede Form auf Anhieb
            # passt, soll sie gar nicht erst bezahlen.
            jumps = _curvature_jumps(body)
        pieces = _split_by_curvature(body, patch, jumps)
        if len(pieces) > 1:
            for piece in pieces:
                classify(piece)

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
    # Kugeln und Tori nach demselben Schlüssel und aus demselben Grund (§21.2).
    for round_shapes in (spheres, tori):
        round_shapes.sort(
            key=lambda entry: (
                round(entry[0].centre[0], 3),
                round(entry[0].centre[1], 3),
                round(entry[0].centre[2], 3),
            )
        )
    return Fitted(found, cones, spheres, tori)


def detect_holes(
    mesh: MeshData,
    cylinders: Cylinders | None = None,
    cones: Cones | None = None,
) -> list[Feature]:
    """Zylindrische Flecken, deren Normalen nach innen zeigen (§21.1).

    ``cylinders`` ist die schon gefundene Einpassung. Wer sie mitgibt, spart den
    teuren Teil; wer sie auslässt, bekommt ihn — die Funktion bleibt allein
    aufrufbar, weil sie es überall ist, wo nur die Bohrungen gebraucht werden.

    **Die Kegel gehören dazu, auch wenn hier keine Kegel herauskommen.** Ob
    eine Bohrung durchgeht, entscheidet ihre Senkung mit (:func:`_is_through`),
    und was fehlt, wird nachgeschlagen statt weggelassen: Eine Bohrung, die
    allein gelesen ein Sackloch ist und in einer vollen Erkennung
    durchgehend, wäre der teuerste Fehler von allen — jeder Test innerhalb
    eines der beiden Wege bliebe grün.
    """
    body = mesh.raw
    if cylinders is None or cones is None:
        fitted = _fitted(mesh)
        cylinders = fitted.cylinders if cylinders is None else cylinders
        cones = fitted.cones if cones is None else cones
    found = [
        entry
        for entry in cylinders
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
                "through": _is_through(mesh, fit, cones),
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


def _fits_in_the_body_by_size(mesh: MeshData, radius: float) -> bool:
    """Dieselbe Frage wie :func:`_fits_in_the_body`, aber ohne Achse.

    Eine Kugel hat keine, und beim Torus wäre die falsche Richtung gemessen.
    Verglichen wird deshalb gegen die **größte** Ausdehnung des Körpers und
    nicht gegen die quer zur Achse — eine Pfanne Ø 16 in einem Block, der nur
    15 mm dick ist, ist völlig normal, weil nur die halbe Kugel darin steckt.
    Die Schranke fängt damit weniger als die des Zylinders; sie fängt das, was
    sie fangen soll: eine Einpassung, die größer ist als das ganze Teil.
    """
    return radius * 2.0 <= float(max(mesh.bounds.size)) + EPS_GEOM


def detect_spheres(mesh: MeshData, spheres: Spheres | None = None) -> list[Feature]:
    """Kugelige Flecken (§21.1, Ausbaustufe §41).

    ``recess`` trennt die Pfanne von der Kuppel — dieselbe Unterscheidung, die
    der Kegel zwischen Senkung und aufgesetztem Kegel trifft, und aus demselben
    Grund: In eine Pfanne setzt man etwas hinein, auf eine Kuppel nicht.
    """
    found = _fitted(mesh).spheres if spheres is None else spheres
    return [
        Feature(
            id=f"sphere_{number}",
            kind="sphere",
            provenance="detected",
            params={
                "diameter": round(fit.radius * 2.0, 4),
                "centre": fit.centre,
                "recess": fit.recess,
                "residual": round(fit.residual, 4),
            },
            face_indices=tuple(patch),
        )
        for number, (fit, patch) in enumerate(found, start=1)
    ]


def detect_tori(mesh: MeshData, tori: Tori | None = None) -> list[Feature]:
    """Torusförmige Flecken (§21.1, Ausbaustufe §41).

    Zwei Durchmesser, und der zweite ist der interessante: ``diameter`` ist der
    Ring, ``tube_diameter`` die Röhre — an einer Verrundung um eine runde Kante
    ist die Röhre ihr Maß. Ein Torus**stück** wird
    hier noch nicht erkannt — die Einpassung liest Ring- und Röhrenradius aus
    den Extremen des Flecks, und das setzt einen ganzen Ring voraus. Was fehlt,
    steht als eigener Punkt in der Roadmap.
    """
    found = _fitted(mesh).tori if tori is None else tori
    return [
        Feature(
            id=f"torus_{number}",
            kind="torus",
            provenance="detected",
            params={
                # **``diameter`` und nicht ``ring_diameter``**, obwohl der
                # Name unschärfer ist: Die Zuordnung liest die Größe eines
                # Merkmals aus genau diesem Schlüssel (``feature_vector``),
                # und zwar für jede Art gleich. Unter einem eigenen Namen war
                # sie null — zwei Tori mit Ringdurchmesser 40 und 60 kosteten
                # gegeneinander 0,0 und waren damit dasselbe Merkmal (§21.2).
                "diameter": round(fit.ring_radius * 2.0, 4),
                "tube_diameter": round(fit.tube_radius * 2.0, 4),
                "axis": fit.axis,
                "centre": fit.centre,
                "recess": fit.recess,
                "residual": round(fit.residual, 4),
            },
            face_indices=tuple(patch),
        )
        for number, (fit, patch) in enumerate(found, start=1)
    ]


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
    # **Gemessen an der Gesamtoberfläche, nicht an der größten Facette.** Der
    # naheliegende Maßstab ist der falsche, und der Körper, der es zeigt, ist
    # der Torus: Er besteht **nur** aus Mantelstreifen, seine größte Facette
    # ist selbst einer, und jede liegt damit bei fast hundert Prozent. Gegen
    # die größte gemessen zerfiel ``torus_ring.stl`` in 288 ebene Flächen.
    broad = float(body.area) * BROAD_FACE_SHARE
    return {
        int(index)
        for facet, area in zip(facets, areas, strict=True)
        if len(facet) >= MIN_FLAT_FACES
        or area >= broad
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


def fit_sphere(body: trimesh.Trimesh, patch: list[int]) -> SphereFit | None:
    """Kleinste-Quadrate-Kugel durch einen Fleck von Dreiecken — linear.

    **Ein Schritt, und es ist derselbe wie beim Kegel, nur mit einer Zahl mehr
    rechts.** Die Tangentialebene eines Kegels geht durch die Spitze, also gilt
    ``n · p = n · apex``. Bei der Kugel ist der Abstand vom Mittelpunkt nicht
    null, sondern der Radius: ``n · p = n · c + R``. Das ist ein
    überbestimmtes lineares System mit vier Unbekannten, und es ist derselbe
    Ansatz — kein Zufall, keine Iteration, kein Startwert (§11.3).

    Dieser Unterschied ist keine Feinheit. Mit der Kegelgleichung an einer
    Kalotte eingepasst kam ein Mittelpunkt 12 mm neben dem richtigen heraus und
    ein Radius von 10,2 statt 8, bei einem Rückstand von 0,24 — plausibel
    genug, um nicht aufzufallen, und falsch. Mit der richtigen Gleichung liegt
    der Mittelpunkt auf drei Nachkommastellen und der Rückstand bei 0,0003.

    Das **Vorzeichen** des Radius ist die Auskunft, die den Rest trägt: Zeigen
    die Normalen nach außen, kommt +R heraus, bei einer Pfanne -R. Das trennt
    die Kalotte von der Kuppel, ohne dass jemand nachmisst.
    """
    normals = np.asarray(body.face_normals[patch], dtype=float)
    centres = np.asarray(body.triangles_center[patch], dtype=float)

    system = np.column_stack([normals, np.ones(len(normals))])
    solution, *_ = np.linalg.lstsq(system, np.einsum("ij,ij->i", normals, centres), rcond=None)
    centre, signed = solution[:3], float(solution[3])
    radius = abs(signed)
    if radius <= EPS_GEOM:
        return None

    distance = np.linalg.norm(centres - centre, axis=1)
    residual = float(np.mean(np.abs(distance - radius)) / radius)
    return SphereFit(
        centre=(float(centre[0]), float(centre[1]), float(centre[2])),
        radius=radius,
        residual=residual,
        recess=signed < 0.0,
    )


def fit_torus(body: trimesh.Trimesh, patch: list[int]) -> TorusFit | None:
    """Torus durch einen Fleck — Achse aus den Normalen, Radien aus dem
    Meridiankreis. Drei Schritte, alle drei linear (§11.3).

    **Die Achse** nutzt eine Eigenschaft jeder Rotationsfläche: Ihre Normale
    schneidet die Achse, ``n``, ``a`` und ``p - c`` sind also koplanar. Als
    Gleichung ``dot(a, cross(p, n)) = dot(cross(a, c), n)`` — homogen und **linear in
    ``a`` und ``cross(a, c)`` zusammen**, also sechs Unbekannte und eine
    Singulärwertzerlegung. Die Punkte werden davor zentriert und auf
    Einheitsgröße gebracht: ``cross(p, n)`` liegt sonst in der Größenordnung des
    Körpers und ``n`` bei eins, und der größere Block bestimmt die Lösung
    allein. Ohne diese Skalierung kam an einem Viertelring eine Achse von
    (0,70 | -0,70 | -0,13) heraus statt (0 | 0 | 1).

    **Der Achsenpunkt** kommt danach aus einem zweiten, kleineren System:
    ``dot(c, cross(n, a)) = dot(n, cross(a, p))``, drei Unbekannte bei bekannter Achse. Ihn aus
    dem ``cross(a, c)`` des ersten Schritts zurückzurechnen ist der naheliegende Weg
    und der falsche — am vollen Ring stimmt er (das Zentrum ist der Ursprung),
    an einem Viertelring landete er 25 mm neben der Achse.

    **Die Radien** aus dem **Meridiankreis**: Der Meridianschnitt eines Torus
    *ist* ein Kreis, sein Mittelpunkt liegt beim Ringradius und sein Radius ist
    der Röhrenradius. Dafür gibt es :func:`_fit_circle` schon, und eine
    Kreiseinpassung braucht keinen ganzen Kreis — genau darin liegt der
    Gewinn gegenüber dem früheren Weg, der Ring- und Röhrenradius aus den
    **Rändern** des Flecks las und damit einen ganzen Ring voraussetzte.

    Gemessen an einem Torus mit R 20 und r 5, in Segmenten:

    ========  =======  ======
    Fleck     R        r
    ========  =======  ======
    voll      19,99    4,99
    90 Grad   19,99    4,99
    45 Grad   19,71    4,98
    22 Grad    5,65    4,37
    ========  =======  ======

    Zwei Dinge stehen darin, auf die sich später jemand verlassen will.
    **Unter etwa 45 Grad bricht die Einpassung** — der Rückstand meldet es,
    und dann wird die Form abgelehnt statt geraten (Regel 21). Und **der
    Röhrenradius bleibt stabil, während der Ringradius zuerst wegbricht**:
    Bei 22 Grad ist R um das Vierfache daneben und r um zwölf Prozent. Für
    eine Verrundung ist der Röhrenradius das Gesuchte, für einen Ring der
    Ringradius — die schwierigere Zahl ist also die, die seltener gebraucht
    wird.

    Der frühere Weg über die Ränder traf den vollen Ring mit 19,96 und 4,93;
    dieser trifft ihn mit 19,99 und 4,99.
    """
    normals = np.asarray(body.face_normals[patch], dtype=float)
    centres = np.asarray(body.triangles_center[patch], dtype=float)
    if len(normals) < MIN_PATCH_FACES:
        return None

    middle = centres.mean(axis=0)
    scale = float(np.abs(centres - middle).max())
    if scale <= EPS_GEOM:
        return None
    scaled = (centres - middle) / scale

    system = np.column_stack([np.cross(scaled, normals), -normals])
    *_, right = np.linalg.svd(system, full_matrices=False)
    axis = right[-1][:3]
    length = float(np.linalg.norm(axis))
    if length <= EPS_GEOM:
        return None
    axis = axis / length

    on_axis, *_ = np.linalg.lstsq(
        np.cross(normals, axis),
        np.einsum("ij,ij->i", normals, np.cross(axis, centres)),
        rcond=None,
    )

    relative = centres - on_axis
    along = relative @ axis
    radial = np.linalg.norm(relative - np.outer(along, axis), axis=1)
    meridian, tube_radius = _fit_circle(np.column_stack([radial, along]))
    ring_radius = float(meridian[0])
    if tube_radius <= EPS_GEOM or ring_radius <= tube_radius:
        return None

    # Der Meridiankreis sagt auch, wo die Mitte auf der Achse liegt — der
    # Achsenpunkt aus dem zweiten System ist irgendeiner, dieser ist der.
    centre = on_axis + float(meridian[1]) * axis

    tube = np.sqrt((radial - ring_radius) ** 2 + (along - float(meridian[1])) ** 2)
    residual = float(np.mean(np.abs(tube - tube_radius)) / tube_radius)
    # Zeigen die Normalen zur Mittellinie der Röhre hin, ist der Torus
    # ausgehöhlt — eine Kehle und kein Wulst. Dieselbe Frage wie ``inward``
    # beim Zylinder, nur um einen Ring herum gestellt.
    mid = _tube_centres(centre, axis, centres, ring_radius)
    towards = np.einsum("ij,ij->i", normals, centres - mid)
    return TorusFit(
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        centre=(float(centre[0]), float(centre[1]), float(centre[2])),
        ring_radius=ring_radius,
        tube_radius=float(tube_radius),
        residual=residual,
        recess=bool(np.mean(towards) < 0.0),
    )


def _tube_centres(
    centre: np.ndarray, axis: np.ndarray, points: np.ndarray, ring_radius: float
) -> np.ndarray:
    """Zu jedem Punkt der nächste Punkt auf der Mittellinie des Rings."""
    relative = points - centre
    across = relative - np.outer(relative @ axis, axis)
    length = np.linalg.norm(across, axis=1)
    length = np.where(length > EPS_GEOM, length, 1.0)
    return np.asarray(centre + across / length[:, None] * ring_radius, dtype=float)


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


def _axial_span(body: trimesh.Trimesh, patch: list[int], axis: Vec3) -> tuple[float, float]:
    """Von wo bis wo ein Fleck entlang einer Achse reicht."""
    points = np.asarray(body.vertices[np.unique(body.faces[patch])], dtype=float)
    along = points @ np.asarray(axis, dtype=float)
    return float(along.min()), float(along.max())


def _patch_extent(body: trimesh.Trimesh, patch: list[int], axis: Vec3) -> float:
    """Wie weit der Fleck entlang seiner eigenen Achse reicht — die Tiefe der
    Bohrung.
    """
    low, high = _axial_span(body, patch, axis)
    return high - low


def _is_through(mesh: MeshData, fit: CylinderFit, cones: Cones | None = None) -> bool:
    """Eine Bohrung ist durchgehend, wenn sie so tief ist, wie der Körper
    entlang ihrer Achse dick ist — **die Senkung mitgerechnet**.

    Ohne sie war die häufigste Bohrung eines Druckteils ein Sackloch: An einem
    gesenkten M5-Durchgangsloch in 8 mm gehören die oberen 2,4 mm zum Kegel und
    nicht zum Zylinder, gemessen wurden aber nur 5,6 mm Zylinderwand gegen 8 mm
    Plattendicke. Das blieb nicht bei der Anzeige — eine Passung sucht ihr
    Gegenstück über die Merkmalsart (§14), und in ein Sackloch geht keine
    durchgesteckte Schraube.

    Gerechnet wird über die **Vereinigung** der Abschnitte auf der Achse, nicht
    über die Summe der Tiefen: Wo Bohrung und Senkung sich überlappen, zählt
    das Stück einmal.
    """
    axis = np.asarray(fit.axis, dtype=float)
    corners = np.asarray(mesh.raw.vertices, dtype=float) @ axis
    thickness = float(corners.max() - corners.min())
    if thickness <= 0:
        return False
    span = _bore_span(mesh, fit)
    if span is None:
        return False
    low, high = span
    for cone, patch in cones or []:
        if not _sinks_into(fit, cone):
            continue
        sink_low, sink_high = _axial_span(mesh.raw, patch, fit.axis)
        # Koaxial allein genügt nicht: Der Kegel muss an die Bohrung stoßen.
        # Sonst gehört er zu der Bohrung in der nächsten Wand.
        if max(sink_low - high, low - sink_high) > fit.radius * SINK_FIT_LIMIT:
            continue
        low, high = min(low, sink_low), max(high, sink_high)
    return high - low >= thickness - EPS_GEOM * 10


def _sinks_into(fit: CylinderFit, cone: ConeFit) -> bool:
    """Gehört dieser Kegel zu dieser Bohrung — ist er also ihre Senkung?

    Drei Bedingungen, und jede schließt einen wirklichen Fall aus: Ein
    aufgesetzter Kegel ist keine Senkung, ein Kegel neben der Achse gehört zu
    einer anderen Bohrung, und ein Kegel, der schmaler ist als die Bohrung,
    kann sie nicht erweitern.
    """
    if not cone.recess or cone.radius < fit.radius:
        return False
    axis = np.asarray(fit.axis, dtype=float)
    # Der **Betrag**: Die Kegelachse zeigt von der Spitze in den Fleck, die
    # Bohrachse aus ihrer eigenen Einpassung — an derselben gesenkten Bohrung
    # stehen sie damit gegeneinander, gemessen (0, 0, -1) gegen (0, 0, 1).
    aligned = abs(float(axis @ np.asarray(cone.axis, dtype=float)))
    if aligned < math.cos(math.radians(SINK_AXIS_LIMIT)):
        return False
    offset = np.asarray(cone.centre, dtype=float) - np.asarray(fit.centre, dtype=float)
    across = offset - float(offset @ axis) * axis
    return float(np.linalg.norm(across)) <= fit.radius * SINK_FIT_LIMIT


def _bore_span(mesh: MeshData, fit: CylinderFit) -> tuple[float, float] | None:
    """Von wo bis wo die **Zylinderwand** der Bohrung auf ihrer Achse reicht.

    ``None``, wenn kein Punkt des Körpers auf der eingepassten Wand liegt — die
    Einpassung beschreibt dann nichts, was da ist.
    """
    axis = np.asarray(fit.axis, dtype=float)
    centre = np.asarray(fit.centre, dtype=float)
    points = np.asarray(mesh.raw.vertices, dtype=float)
    radial = points - centre
    radial = radial - np.outer(radial @ axis, axis)
    on_wall = np.abs(np.linalg.norm(radial, axis=1) - fit.radius) < fit.radius * 0.1
    if not on_wall.any():
        return None
    along = points[on_wall] @ axis
    return float(along.min()), float(along.max())


#: Wie weit zwei benachbarte Dreiecke im Krümmungsradius auseinanderliegen
#: dürfen, ohne dass ein Fleck dort endet — als Anteil des größeren Radius.
#:
#: Der Fall, für den es die Grenze gibt, ist eine **Verrundung**: Sie schließt
#: tangential an, hat also keinen Knick, an dem :func:`_connected_patches`
#: trennen könnte. An einer Säule Ø 12 mit R 3 am Fuß lagen Mantel und Kehle
#: deshalb in **einem** Fleck, und darauf passte weder ein Zylinder noch ein
#: Torus — die Säule hatte keine Mantelfläche, auf die der Agent hätte zeigen
#: können.
#:
#: **Der Wert ist gemessen und nicht gewählt.** Über den Korpus verteilen sich
#: die Sprünge in zwei Gruppen mit einer breiten Lücke dazwischen:
#:
#: ==================  ======  ======
#: Körper              p90     größter
#: ==================  ======  ======
#: ``torus_ring``      0,002   0,002
#: ``plate_holes``     0,000   0,000
#: ``clean_figure``    0,120   0,312
#: Säule mit Kehle     0,802   0,997
#: ==================  ======  ======
#:
#: Zwischen 0,31 und 0,80 liegt nichts. Ein Viertel hätte an
#: ``generated_figure.stl`` drei Kugeln in neun zerlegt; die Hälfte trennt,
#: was getrennt gehört, und lässt beisammen, was eine Fläche ist.
CURVATURE_JUMP = 0.5


def facet_middles(body: trimesh.Trimesh) -> np.ndarray:
    """Zu jedem Dreieck die Mitte der **ebenen Fläche**, auf der es liegt.

    **Nicht sein eigener Schwerpunkt**, und der Unterschied ist keine Feinheit:
    An einer Zylinderwand sind die zwei Dreiecke eines Mantelrechtecks
    koplanar. Der Winkel sitzt allein an der Rechteckgrenze, der Weg dorthin
    wird aber vom Dreiecksschwerpunkt aus gemessen — und der liegt bei einem
    Drittel. Gemessen kamen so an einem Zylinder Ø 10 durchweg 3,33 mm heraus
    statt 5, also genau zwei Drittel, und zwar bei jeder Netzfeinheit gleich
    falsch. Über die Flächenmitte sind es 4,97.

    Wo ein Dreieck allein steht — auf einer Kugel etwa —, ist die Flächenmitte
    sein Schwerpunkt, und es ändert sich nichts.
    """
    middles = np.asarray(body.triangles_center, dtype=float).copy()
    areas = np.asarray(body.area_faces, dtype=float)
    for facet in body.facets:
        members = np.asarray(facet)
        weight = areas[members].sum()
        if weight <= EPS_GEOM:
            continue
        middles[members] = (middles[members] * areas[members][:, None]).sum(axis=0) / weight
    return middles


def pair_radii(body: trimesh.Trimesh) -> np.ndarray:
    """Der Krümmungsradius über jede Nachbarschaft zweier Dreiecke, in mm.

    Radius ist Bogenlänge durch Winkel. Beide naheliegenden Strecken sind die
    falschen: Die **gemeinsame Kante** ist an einer Zylinderwand die
    senkrechte, ihre Länge also die Höhe des Zylinders; der bloße Abstand der
    Flächenmitten trägt dieselbe Höhe anteilig mit. Gemessen wird deshalb der
    Anteil des Mittenabstands **senkrecht zur gemeinsamen Kante**.

    ``inf`` steht, wo die Nachbarn zu flach zueinander stehen, um eine Krümmung
    zu tragen — eine ebene Fläche ist nicht unendlich rund, sie ist gar nicht
    rund, und ``0,001`` Grad auf 3 mm ergäben einen Radius von 170 Metern.
    """
    pairs = np.asarray(body.face_adjacency)
    if not len(pairs):
        return np.zeros(0, dtype=float)

    angles = np.asarray(body.face_adjacency_angles, dtype=float)
    edges = np.asarray(body.face_adjacency_edges)
    along = body.vertices[edges[:, 1]] - body.vertices[edges[:, 0]]
    along = along / np.maximum(np.linalg.norm(along, axis=1), EPS_GEOM)[:, None]

    middles = facet_middles(body)
    span = middles[pairs[:, 1]] - middles[pairs[:, 0]]
    across = np.linalg.norm(span - np.einsum("ij,ij->i", span, along)[:, None] * along, axis=1)
    return np.where(np.degrees(angles) >= FLAT_ANGLE, across / np.maximum(angles, EPS_GEOM), np.inf)


def _face_radii(body: trimesh.Trimesh, pairs: np.ndarray, radii: np.ndarray) -> np.ndarray:
    """Je Dreieck der engste Radius unter seinen **sanften** Nachbarn.

    Eine Kante bleibt außen vor: Sie sagt nichts darüber, wie die Fläche
    gekrümmt ist, auf der das Dreieck liegt.

    **Das Minimum und nicht der Median**, obwohl der Median nach der
    robusteren Wahl aussieht. Eine Fläche hat zwei Hauptkrümmungen, und ein
    Median mischt sie: An einem Torus schwankt der Radius längs zwischen
    ``R - r`` und ``R + r``, quer bleibt er ``r``. Über den Median gemittelt
    wandert der Wert über den Ring, und ``torus_ring.stl`` zerfiel in einen
    Torus, einen Zapfen, eine Bohrung und vier Kegel. Das Minimum greift
    dagegen immer dieselbe Hauptkrümmung — die engste —, und der Ring bleibt
    einer: gemessen ein Sprung von höchstens 0,002 über das ganze Netz.
    """
    found = np.full(len(body.faces), np.inf, dtype=float)
    degrees = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    for (first, second), radius, angle in zip(pairs, radii, degrees, strict=True):
        if angle >= CURVATURE_LIMIT or not np.isfinite(radius):
            continue
        for index in (int(first), int(second)):
            found[index] = min(found[index], float(radius))
    return found


def _curvature_jumps(body: trimesh.Trimesh) -> np.ndarray:
    """Der Sprung des Krümmungsradius über jede Nachbarschaft, als Anteil.

    **Einmal je Körper, nicht einmal je Fleck.** Sie ist hier eine eigene
    Funktion, weil sie über *alle* Nachbarpaare rechnet: Aus
    :func:`_split_by_curvature` heraus aufgerufen lief sie für jeden Fleck neu,
    der keine Form ergeben hatte, und das ist bei einem großen Körper einmal zu
    oft. Gemessen an einem Netz aus 150 000 Dreiecken riss der Speicher
    (``MemoryError`` beim Anlegen eines Feldes über 225 000 Nachbarschaften) —
    an einer Stelle, an der die Zahl selbst für alle Flecken dieselbe ist.
    """
    pairs = np.asarray(body.face_adjacency)
    if not len(pairs):
        return np.zeros(0, dtype=float)

    radii = _face_radii(body, pairs, pair_radii(body))
    first, second = radii[pairs[:, 0]], radii[pairs[:, 1]]
    # Nur wo **beide** Seiten einen Radius haben, gibt es einen Sprung. Zwei
    # ebene Nachbarn tragen ``inf``, und deren Differenz wäre ``nan`` — kein
    # Sprung, sondern keine Aussage. Die Rechnung darf die ``inf`` dabei gar
    # nicht erst sehen: ``where`` schützt die Division, nicht die Differenz
    # davor, und ``inf - inf`` meldet sich als Warnung, die hier ein Fehler ist.
    measured = np.isfinite(first) & np.isfinite(second)
    near = np.where(measured, first, 0.0)
    far = np.where(measured, second, 0.0)
    jump = np.zeros(len(pairs), dtype=float)
    np.divide(
        np.abs(near - far),
        np.maximum(np.maximum(near, far), EPS_GEOM),
        out=jump,
        where=measured,
    )
    return jump


def _split_by_curvature(
    body: trimesh.Trimesh, patch: list[int], jump: np.ndarray
) -> list[list[int]]:
    """Denselben Fleck noch einmal teilen, jetzt am **Sprung der Krümmung**.

    **Die zweite Runde, und nur für Flecken, auf die keine Form gepasst hat.**
    Eine Verrundung schließt tangential an — das ist ihr Zweck —, und
    :func:`_connected_patches` trennt an Knicken. An einer Säule Ø 12 mit R 3
    am Fuß lagen Mantel und Kehle deshalb in **einem** Fleck, auf den weder
    ein Zylinder noch ein Torus passte: Die Säule hatte keine Mantelfläche, auf
    die der Agent hätte zeigen können, und keine Passung fand sie. Nach der
    Nachtrennung kommen ein Zapfen Ø 12,00 und ein Torus mit Ring Ø 18,0 und
    Röhre Ø 6,0 heraus.

    **Warum erst als zweite Runde und nicht gleich mit.** Ein Kegel hat keine
    feste Krümmung: Sein Querradius wächst zur Grundfläche hin stetig, und über
    eine lange Senkung summiert sich das zu einem Sprung. Grundsätzlich
    nachgetrennt zerfiel im Beispielprojekt *Aushöhlen und Teilen* ein Kegel in
    zwei — und weil zwei gespiegelte Senkungen für die Zuordnung ohnehin gleich
    aussehen, hielt die Auswertung an und fragte den Nutzer viermal, welches
    Merkmal ``cone_1`` entspricht. In einem **mitgelieferten Beispiel**, dem
    freundlichsten Weg, den die Anwendung hat.

    So herum kann das nicht passieren: Wo eine Form erkannt wurde, wird nicht
    nachgetrennt. Es ändert sich also nichts an dem, was heute funktioniert —
    es kommt nur dort etwas dazu, wo bisher nichts war.
    """
    pairs = np.asarray(body.face_adjacency)
    if not len(pairs):
        return [patch]

    wanted = set(patch)
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    adjacency = [
        pair
        for pair, angle, step in zip(pairs, angles, jump, strict=True)
        if angle < CURVATURE_LIMIT
        and step <= CURVATURE_JUMP
        and int(pair[0]) in wanted
        and int(pair[1]) in wanted
    ]
    if not adjacency:
        return [patch]
    groups = trimesh.graph.connected_components(
        np.asarray(adjacency), nodes=np.asarray(patch), engine="scipy"
    )
    return [[int(index) for index in group] for group in groups]


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
