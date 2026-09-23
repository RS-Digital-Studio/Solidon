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

import hashlib
import itertools
import math
import threading
import weakref
from collections import Counter, OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final, NamedTuple, cast

import numpy as np

from app.core import units
from app.core.deferred import cKDTree, least_squares, trimesh
from app.core.geom.mesh import MeshData, face_components, fully_stitched, unique_edges
from app.core.geom.repair import merge_vertices
from app.core.log import get_logger
from app.core.perceive.helix import Helix, find_helices
from app.core.perceive.patterns import patterns_instead_of_cells
from app.core.perceive.slots import ACROSS_THE_AXIS, PARALLEL_AXES, slots_instead_of_half_bores
from app.core.perceive.surfaces import clipped_patches, planar_patch
from app.core.types import Feature, FeatureId, SurfacePatch, Vec3, is_a_cavity
from app.core.units import (
    EPS_GEOM,
    TANGENT_TO_THE_ARC,
    UPRIGHT_TO_AXIS,
    positive_axis,
    weld_digits,
    weld_tolerance,
)

_log = get_logger(__name__)

#: Wie gut ein Fleck zu einem Zylinder passen muss, um als Bohrung zu zählen:
#: der Radius darf um diesen Anteil streuen, bevor die Einpassung abgelehnt wird.
CYLINDER_TOLERANCE = 0.08

#: Welche Merkmale eine runde Wand haben, auf der eine ebene Fläche liegen
#: kann: Bohrung und Zapfen (:func:`_faces_on_a_round_wall`).
ROUND_WALL_KINDS: Final[frozenset[str]] = frozenset({"hole", "pin"})

#: Wie weit die Normale einer Fläche von der Senkrechten zu einer Achse
#: abweichen darf, damit sie auf deren Mantel liegen kann — der Kosinus, also
#: rund drei Grad.
PLANE_ON_A_WALL: Final = 0.05

#: Und wie weit die Punkte **absolut** vom eingepassten Kreis abweichen dürfen,
#: gemessen in Sehnenhöhen der Polygonnäherung — siehe
#: :attr:`CylinderFit.spread`.
#:
#: Der Rückstand oben ist relativ zum Radius und kann einen aufgeblähten Kreis
#: deshalb nicht sehen. Der Wert ist gemessen (17.09.2026): Über den Korpus
#: liegen alle achtzehn richtigen Einpassungen bei höchstens 0,39, ein
#: Fleck aus Verrundung R 3 samt anschließenden Ebenen — der Fall, an dem die
#: Einpassung r = 89,79 fand — bei 32,7 bis 62,6, über drei Flankenlängen und
#: vier Unterteilungsstufen. Zwei liegen mit Faktor fünf über dem einen und
#: Faktor sechzehn unter dem anderen.
CYLINDER_SPREAD = 2.0

#: Wie weit die Ecken einer **runden Wand** vom gemeinsamen Kreis abliegen
#: dürfen, in Millimetern — die Frage von :func:`radial_cylinder`.
#:
#: Dort galt allein die Schweißtoleranz, und die ist am Bauplan §17.1 für
#: Solidons eigene Netze bemessen: ein Millionstel der Diagonale, an einem
#: Körper von 170 mm also 0,2 µm. Ein eingelesenes Netz hält das nicht, auch
#: wenn es aus einer Konstruktion stammt. Gemessen am Siebhalter eines Kunden
#: (15.09.2026): Der Kragen Ø 57,00 liegt 0,3 µm neben seinem Kreis — das ist
#: das Float32 der STL, aus der die 3MF entstand —, der Nutboden Ø 54,36 mit
#: 281 Grad Überdeckung 3,9 µm, weil seine zwei Eckenreihen um 2 µm
#: verschieden groß sind. Beides sind Zylinder, und beide fielen durch; der
#: Nutboden stand als Verrundung im Baum, und das Panel schrieb an jede
#: Zeile, er gehöre zu einer Kante.
#:
#: Zehn Mikrometer sind ein Fünftel der Sehnenhöhe, mit der der exakte Kern
#: tesselliert (``units.MAX_FACET_SAG``): feiner löst kein Netz einen Kreis
#: auf, und keine Einbuchtung, die ein Werkzeug sähe, ist kleiner. Das
#: Stadion mit dem kleinsten Weg, das :data:`STADIUM_TOLERANCE` noch
#: annimmt, liegt an Ø 12 rund 60 µm neben dem Kreis — Faktor sechs darüber.
ROUND_WALL_TOLERANCE = 0.01

#: Ein Fleck braucht mindestens so viele Dreiecke, um überhaupt beurteilt zu
#: werden.
MIN_PATCH_FACES = 6

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

#: Wie viel von der Oberfläche eines Körpers eine gerundete Seite mindestens
#: einnimmt, um als Merkmal zu gelten — siehe :func:`detect_curved_faces`.
CURVED_SIDE_SHARE = 0.01

#: …und unter dieser absoluten Größe erst recht nicht, egal wie groß der Rest ist.
#:
#: Der relative Anteil allein hilft nur bei einem konstruierten Teil, wo eine
#: Fläche gegen eine viel größere antritt. Auf einem erzeugten Netz sind alle
#: Facetten gleich groß, also ist jede „mindestens zwei Prozent der größten" —
#: eine Kugel aus 3 400 Dreiecken meldete daraufhin 180 Flächen. Danach war
#: jede Zuordnung mehrdeutig, und die Auswertung hielt bei jeder Operation an
#: (§21.3), womit Weg 3 nach der Reparatur nicht weiterkam.
#:
#: Zwei mal zwei Millimeter ist die kleinste Fläche, die ohne weiteren Beleg
#: als Fläche gilt. **Mit Beleg gilt auch eine kleinere** (P1.5, 20.09.2026):
#: Ein 1-mm-Nocken auf einer Platte hat fünf Flächen zu je 1 mm², und der
#: exakte Kern nennt sie alle — das Netz nannte keine. Was die Schranke
#: überwindet, ist nicht die Fläche, sondern ihre Ränder: ein Fleck, der an
#: **jedem** Rand mit einem scharfen Knick an einen Nachbarn stößt, der nicht
#: zu ihm gehört, und der auf keiner Rundung sitzt (:func:`_facets_standing_apart`).
#: Die Facette einer Kugel und der Streifen eines Mantels haben an ihren
#: Rändern nur die Stufe der Rundung — sie bleiben unter der Schranke.
MIN_FACE_AREA = 4.0
#: Ab welchem Kosinus zwei Flächennormalen als gleichgerichtet gelten — nur
#: dann kann die eine die andere verdecken, also innen liegen.
PARALLEL_FACE_COSINE: Final = 0.99

#: Wie viele parallele Kandidatenflächen :func:`_face_roles` je Block prüft,
#: bevor es beim ersten Treffer aufhört — ein Arbeitsstück, keine Toleranz.
FACE_ROLE_BLOCK: Final = 64

#: Kleinster Durchmesser der automatischen geometrischen Einpassung.
#:
#: Unter dieser Erkennungsauflösung werden keine Rundformen veröffentlicht.
#: Erzeugte Netze tragen dort zahlreiche zufällige Fits aus wenigen Dreiecken
#: (siehe :func:`_too_small_to_make`). Das ist eine Grenze der automatischen
#: Erkennung, keine Aussage über die Herstellbarkeit. Sie bleibt bei Drucker-
#: und Materialwechsel gleich (§11.2, §21.1); die Druckbarkeit prüft die Analyse.
#:
#: **Die Schranke gilt beiden Richtungen, und der Name sagt das.** Sie hieß
#: ``MIN_HOLE_DIAMETER`` und stand nur in :func:`detect_holes`; eine Erhebung
#: von 0,05 mm kam als Zapfen zurück, während die gleich große Vertiefung
#: daneben verworfen wurde. Beide Formen teilen dieselbe Erkennungsauflösung.
MIN_CYLINDER_DIAMETER = 0.5

#: Wie breit ein Fleck mindestens sein muss, um eine Fläche zu sein.
#:
#: Gemessen als **Fläche geteilt durch die Ausdehnung** des Flickens — bei
#: einem langen Streifen ist das seine Breite, bei einem kompakten Fleck eine
#: Zahl in der Größe seines Radius. Verworfen wird nur nach unten, also
#: schadet die Ungenauigkeit nach oben nicht.
#:
#: **Der Anlass ist die Neuvernetzung nach einer Booleschen Operation.** Ein
#: eingelesener Mast Ø 5 auf 115 mm Länge mit drei Merkmalen kam nach ``move_feature``
#: mit 72 zurück und nach ``remove_feature`` mit 87 — zwanzig „Verrundungen",
#: vierzehn Kegel, zwei Kugeln, dazu ein Torus Ø 89,91 auf einem Körper von
#: Ø 5. Es sind die schmalen Dreiecksstreifen, die eine Boolesche Operation
#: an den Nahtstellen hinterlässt: sechs bis neun Dreiecke, über die ganze
#: Länge des Körpers gezogen, und aus jedem liest die Einpassung eine Form.
#:
#: :data:`MIN_CYLINDER_DIAMETER` greift dort nicht — die Streifen messen
#: 0,52 bis 89,91 mm im Durchmesser und liegen damit über der Schranke. Die
#: falsche Achse: Nicht ihr Durchmesser ist zu klein, sondern ihre **Breite**.
#:
#: Die Grenze trennt die gemessenen Nahtstreifen von echten Flächen und bleibt
#: unabhängig vom Druckerprofil (§11.2). Die Streifen sind 0,013
#: bis 0,038 mm breit, das schmalste echte Merkmal über Korpus und
#: Kundendatei 0,379 mm, die schmalste echte Verrundung 0,646 mm. 0,2 liegt
#: zwischen diesen beiden gemessenen Bereichen.
MIN_SURFACE_WIDTH = 0.2

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

#: Blöcke begrenzen Speicher und Abbruchlatenz der Konturprüfung. Die Anzahl
#: ändert weder den Formnachweis noch eine geometrische Toleranz.
FIT_SCAN_BLOCK: Final = 16_384

#: Feste Arbeitsgrenze einer deterministischen Endmaßeinpassung; keine
#: geometrische Toleranz. Jede Residuen-/Jacobi-Auswertung bleibt abbrechbar.
ROUND_FIT_EVALUATIONS: Final = 100

#: Dimensionslose Lösergenauigkeit im auf Einheitsgröße skalierten Rahmen.
#: Aus der Float64-Auflösung abgeleitet, nicht aus einem Fertigungsspiel.
ROUND_FIT_PRECISION: Final = float(np.finfo(float).eps ** 0.75)

#: An wie vielen Stützpunkten der Löser einer Rundform höchstens rechnet.
#:
#: Sechs Kegelgrößen aus hunderttausend Punkten sind keine bessere Antwort
#: als aus viertausend gleichmäßig verteilten — sie sind dieselbe, ein
#: Rundungsrauschen später und ein Vielfaches teurer: Die Schüssel mit
#: 215 000 Dreiecken trägt ihre Haut als einen Fleck, und zwei Kegelfits
#: daran kosteten 1,95 der 2,7 Sekunden der Facettenfrage (22.09.2026). Die
#: Auswahl ist deterministisch — jeder k-te der koordinatensortierten
#: Punkte, also räumlich gestreut —, und **gemessen wird danach an allen**:
#: Residuum und Punktfehler lesen jeden belegten Punkt, nicht die Auswahl.
#: Eine Rechengrenze, keine Geometrietoleranz.
FIT_SOLVER_POINTS: Final = 4096

#: Bis zu wie vielen Punkten ein Fleck seine Deckungsgleichheit ausweist.
#:
#: Die Kennzahl in :func:`_rigid_key` steht auf **allen** paarweisen
#: Punktabständen und kostet damit quadratisch. Für einen Splitterfleck aus
#: sieben Dreiecken ist das ein Zehntel einer Millisekunde, für die Haut einer
#: Figur mit dreihunderttausend wäre es teurer als jede Einpassung, die sie
#: spart. Darüber bekommt ein Fleck keine Kennzahl und wird einzeln gerechnet.
RIGID_KEY_POINTS: Final = 96


def _solver_rows(count: int, *, keep: int | None = None) -> np.ndarray | None:
    """Die Zeilen, an denen der Löser rechnet — ``None`` heißt: alle.

    ``keep`` ist eine Zeile, die in der Auswahl stehen muss (die belegte
    Spitze eines Kegels); sie kommt hinten dazu, wenn der Schritt sie nicht
    ohnehin trifft.
    """
    if count <= FIT_SOLVER_POINTS:
        return None
    step = -(-count // FIT_SOLVER_POINTS)
    rows = np.arange(0, count, step, dtype=np.int64)
    if keep is not None and keep % step != 0:
        rows = np.append(rows, keep)
    return rows


def _rigid_key(body: trimesh.Trimesh, patch: Sequence[int]) -> tuple[Any, ...] | None:
    """Woran zwei Flecken als dasselbe Stück Geometrie zu erkennen sind.

    Ein Muster besteht aus wiederholten Zellen, und seine Streben sind
    deckungsgleich bis auf eine starre Bewegung: An der Kumiko-Schale sind von
    1 990 eingepassten Flecken nur 445 verschieden (22.09.2026). Weil ein
    Kegelwinkel, ein Rückstand und eine Güte unter Drehung und Verschiebung
    unverändert bleiben, ist die zweite Einpassung dieselbe Rechnung mit
    denselben Zahlen.

    Die Kennzahl steht deshalb auf der sortierten Menge **aller** paarweisen
    Punktabstände, dazu den Kantenlängen jedes einzelnen Dreiecks: Abstände
    überleben eine starre Bewegung, und die Dreiecke trennen dieselbe
    Punktwolke mit anderer Vernetzung. Gerundet wird auf :data:`EPS_GEOM` —
    gröber ginge auch, aber nicht genauer: Bei einem Nanometer entstehen
    dieselben Klassen wie bei einem Mikrometer, das Muster ist also exakt
    kopiert und nicht bloß ähnlich.

    ``None`` heißt: Dieser Fleck weist sich nicht aus — er ist zu klein zum
    Einpassen oder zu groß für die quadratischen Kosten
    (:data:`RIGID_KEY_POINTS`).
    """
    if len(patch) < MIN_PATCH_FACES:
        return None
    corners = np.asarray(body.faces, dtype=np.int64)[list(patch)]
    used = np.unique(corners)
    if len(used) > RIGID_KEY_POINTS or len(used) < 3:
        return None
    points = np.asarray(body.vertices, dtype=float)
    local = points[used]
    upper = np.triu_indices(len(used), k=1)
    gaps = np.sort(_row_lengths((local[:, None, :] - local[None, :, :])[upper]))
    triangle = points[corners]
    sides = np.sort(np.linalg.norm(triangle - triangle[:, (1, 2, 0), :], axis=2), axis=1)
    shape = np.round(sides / EPS_GEOM).astype(np.int64)
    # Die Dreiecke tragen keine Reihenfolge, also werden sie in eine gebracht:
    # erst jedes für sich (die drei Kanten aufsteigend), dann alle zusammen.
    return (
        len(patch),
        len(used),
        np.round(gaps / EPS_GEOM).astype(np.int64).tobytes(),
        shape[np.lexsort(shape.T[::-1])].tobytes(),
    )


@dataclass(frozen=True, slots=True)
class CylinderFit:
    """Ein Zylinder, eingepasst durch einen Fleck von Dreiecken."""

    axis: Vec3
    centre: Vec3
    radius: float
    residual: float
    """Mittlerer radialer Fehler der geprüften Konturecken, geteilt durch den Radius."""
    inward: bool
    """Wahr, wenn die Normalen zur Achse zeigen — das ist eine Bohrung, kein Zapfen."""
    spread: float = 0.0
    """Mittlerer Kontureckenfehler in Sehnenhöhen der Polygonnäherung.

    Die Sehnenhöhe kommt aus Facettenwinkeln und summierten Flächen, nicht
    aus Dreiecksbreiten; Unterteilung verändert ihren Maßstab nicht.
    ROUND_WALL_TOLERANCE begrenzt ihn gegen numerisches Rauschen nach unten.
    Die zusätzliche Prüfung aller Konturecken und Flächennormalen fängt
    Ausreißer und falsche Achsen, die ein mittlerer relativer Fehler verdeckt.
    Der Abstand einer Facettenmitte zum Kreis gehört nicht zum Fitfehler,
    sondern zum getrennten radialen Netzband.
    """

    fit_error: float | None = None
    """Größter radialer Fehler der Konturecken in mm; keine Nennmaßunsicherheit."""
    radial_min: float | None = None
    """Kleinster Abstand der wirklichen Manteldreiecke zur Fitachse in mm."""
    radial_max: float | None = None
    """Größter Abstand der wirklichen Manteldreiecke zur Fitachse in mm.

    Das Netzband ist weder Fertigungsspiel noch eine Einbaugarantie. Fehlende
    Werte an älteren, von Hand aufgebauten Fits sind keine Nullabweichung.
    """

    @property
    def good(self) -> bool:
        return (
            self.residual <= CYLINDER_TOLERANCE
            and self.radius > EPS_GEOM
            and self.spread <= CYLINDER_SPREAD
        )


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
    fit_error: float | None = None
    """Größter orthogonaler Stützpunktabstand in mm; keine Nennmaßunsicherheit."""
    normal_constrained: bool = False
    """Bei nur einem belegten Kreis bestimmen Mantelnormalen Achse und Winkel.

    Auch ein Stützpunktfehler von null belegt dann keinen Ursprungswinkel.
    Alle veröffentlichten Kegelmaße bleiben geschätzte Fitwerte.
    """

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
    fit_error: float | None = None
    """Größter geometrischer Stützpunktabstand in mm, kein Fehlerband der Haut."""

    @property
    def good(self) -> bool:
        return self.residual <= ROUND_TOLERANCE and self.radius > EPS_GEOM


@dataclass(frozen=True, slots=True)
class StadiumFit:
    """Ein Langloch, als **ein** Mantel eingepasst — nicht aus zwei Bögen.

    Der Auffangweg für RM-155: Zwischen „ein Zylinder passt noch" und „zwei
    Bögen lassen sich trennen" liegt ein Streifen, in dem ein knapp
    aufgezogenes Langloch weder das eine noch das andere ist. Gemessen am
    11.09.2026 über Ø 2 bis Ø 40: unterhalb von rund fünf Prozent Weg passt
    ein Zylinder, knapp darüber passt nichts — Ø 12 auf 12,5 mm ergab **kein**
    Merkmal, Ø 20 auf 20,5 ebenso. Solidon schneidet seit demselben Tag nicht
    mehr so knapp (:func:`app.core.geom.prepare.shortest_slot`); ein
    eingelesenes Netz kommt trotzdem dorthin.

    Gefragt wird deshalb am ganzen Fleck: Liegen alle Normalen quer zu einer
    Achse (ein Prisma), und liegen die Ecken in der Projektion auf einem
    Stadion — zwei Halbkreise über einer Strecke —, ist es ein Langloch.
    """

    axis: Vec3
    centre: Vec3
    """Die Mitte, auf halber Länge und halber Tiefe."""
    direction: Vec3
    """Die Richtung der Mittellinie, senkrecht zur Achse."""
    radius: float
    travel: float
    """Der Weg zwischen den beiden Bogenmittelpunkten."""
    depth: float
    residual: float
    """Mittlere Abweichung von der Stadionkontur, bezogen auf den Radius."""
    inward: bool

    @property
    def good(self) -> bool:
        # **Ein Weg innerhalb der eigenen Toleranz ist keine Messung, sondern
        # ein Kreis.** ``travel > EPS_GEOM`` hielt hier nur die Division auf;
        # ein Kreis, den der Zylinderfit an seiner Streuung ablehnt, kam
        # deshalb als Stadion mit Weg 0,00005 mm durch — gemessen am Ring
        # eines Bajonettverschlusses (Siebhalter, 15.09.2026): die Bohrung
        # Ø 57,4 trägt drei Nasen 1,4 mm nach innen, der Zylinderfit sagte
        # ab, und im Objektbaum stand „Langloch Ø 57,39 auf 57,39 mm" mit
        # sechs Handlungen, von denen jede die Nasen still weggeschnitten
        # hätte. Der Rückstand ist relativ zum Radius und die Frage nach der
        # Form muss dieselbe Auflösung haben: Unter zwei Prozent des Radius
        # unterscheidet dieser Fit ein Stadion nicht von einem Kreis, und was
        # er nicht unterscheiden kann, behauptet er nicht (§41).
        return (
            self.residual <= STADIUM_TOLERANCE
            and self.radius > EPS_GEOM
            and self.travel > STADIUM_TOLERANCE * self.radius
        )


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
    fit_error: float | None = None
    """Größter geometrischer Stützpunktabstand in mm; Kandidaten haben noch keinen."""

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

#: Ab welchem **gemessenen** Winkel die Einpassung überhaupt beginnt.
#:
#: :data:`CONE_MIN_ANGLE` fragt den verfeinerten Winkel, und um ihn zu
#: bekommen, läuft der Löser. Der Winkel steht aber schon vorher da:
#: :func:`_fit_cone_read` liest ihn aus den Normalen, bevor es verfeinert —
#: er ist der ``asin`` ihres mittleren Versatzes zur Achse. Liegt er unter
#: einem halben Grad, stehen die Normalen praktisch senkrecht auf der Achse,
#: und das ist ein Zylinder; der Löser würde hundert Auswertungen lang
#: bestätigen, was die Normalen schon sagen, und `classify` ginge danach in
#: denselben Zweig.
#:
#: Ein Zehntel von :data:`CONE_MIN_ANGLE`, und an drei echten Modellen
#: gemessen: Der kleinste Startwinkel, aus dem noch ein Kegel wurde, war 0,88
#: Grad (22.09.2026). Keine Fertigungstoleranz, sondern die Auflösung, ab der
#: eine Schräge eine Schräge ist.
CONE_START_ANGLE = 0.5

#: Wie gut ein Fleck zum eingepassten Kegel passen muss.
#:
#: **Dieselbe Schwelle wie beim Zylinder, weil es dieselbe Frage ist** — und
#: deshalb abgeleitet statt abgeschrieben. Der Satz stand hier schon, die
#: Zahl daneben aber ein zweites Mal; wer den Zylinder eines Tages
#: nachjustiert, hätte den Kegel zurückgelassen (27.08.2026).
#:
#: Dass beide zusammengehören, sagt der Code an dritter Stelle selbst: Der
#: Kommentar an :data:`SPHERE_TOLERANCE` spricht von „der Schwelle von 0,08,
#: die für Zylinder und Kegel gilt" — im Singular, für beide.
CONE_TOLERANCE = CYLINDER_TOLERANCE

#: Höchster Winkelfehler einer Kegelnormale nach Abzug der
#: Facettenauflösung, in Grad.
#:
#: Vier echte Senkungsübergänge und ein eigenständiger Kegel aus dem
#: Gartenhalter bleiben nach dieser Korrektur praktisch ausreißerfrei. Der
#: belegte Freiformfleck ``cone_48`` trägt dagegen auf 46,38 Prozent seiner
#: Fläche einen größeren Widerspruch. Ein selbst erzeugter 45°-Teilbogen in
#: drei Vernetzungen und beiden Flächenrichtungen bleibt ohne Ausreißer.
SURFACE_NORMAL_ERROR = 5.0
CONE_NORMAL_ERROR = SURFACE_NORMAL_ERROR

#: Mindestens 95 Prozent der belegten Fläche müssen die Kegelnormalen tragen.
SURFACE_NORMAL_OUTLIER_SHARE = 0.05
CONE_NORMAL_OUTLIER_SHARE = SURFACE_NORMAL_OUTLIER_SHARE

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

#: Wie gut die Ecken eines Flecks auf einem Stadion liegen müssen, damit er
#: ein Langloch ist — mittlere Abweichung, bezogen auf den Radius.
#:
#: Dieselbe Zahl wie :data:`ROUND_TOLERANCE`, und aus demselben Grund
#: **streng**: Ein Verfahren, das Grundformen sucht, findet auch welche, die
#: niemand gemeint hat (§41). Die Ecken eines geschnittenen Langlochs liegen
#: auf der Kontur — gemessen 0,0011 an Ø 12 auf 12,5 mm —, und ein
#: eingelesenes Netz liegt dort ebenso, solange es aus einer Konstruktion
#: stammt. Was zwei Prozent daneben liegt, ist etwas anderes: die vier Ecken
#: einer verrundeten Tasche etwa, deren gerade Kurzseiten neben dem Bogen
#: liegen, den das Stadion dort verlangt.
STADIUM_TOLERANCE = 0.02

#: In wie vielen Richtungen über einen halben Kreis die Ausdehnung eines
#: Flecks gemessen wird, um die Mittellinie eines Stadions grob zu finden —
#: ein Grad. Fein wird sie danach aus den zwei Scheiteln, die in dieser
#: Richtung außen liegen; die Zahl bestimmt nur, dass die richtigen zwei
#: gefunden werden.
STADIUM_SWEEP = 180

#: Höchster Winkelfehler zwischen der Flächennormale und der Normalen des
#: eingepassten Torus nach Abzug der Facettenauflösung, in Grad.
#:
#: Der Punktabstand allein ist kein Formbeweis: Am Gartenhalter bestanden acht
#: örtlich doppelt gekrümmte Freiformflecken den Torusfit, obwohl ihre Normalen
#: um 9,97 bis 19,90 Grad abwichen. Der echte Ring, die echte Kantenrundung und
#: ein in beiden Richtungen beschnittener analytischer Torus liegen bei
#: höchstens 4,51 Grad. Fünf Grad liegen in der gemessenen Lücke.
TORUS_NORMAL_ERROR = SURFACE_NORMAL_ERROR

#: Höchster Flächenanteil außerhalb des Normalenwinkels oben.
#:
#: Die analytische Torusnormale ändert sich schon **innerhalb** eines groben
#: Dreiecks. Diese Änderung wird je Facette abgezogen; damit bleiben selbst
#: zwölfseitige Röhren bei zwei verschiedenen Ringauflösungen ohne Ausreißer.
#: Beim echten Garten-Ring gilt dasselbe. Die acht falschen Funde tragen danach
#: auf 6,31 bis 33,24 Prozent ihrer Fläche einen größeren Fehler. Fünf Prozent
#: verlangen die Zusage für mindestens 95 Prozent der belegten Oberfläche.
TORUS_NORMAL_OUTLIER_SHARE = SURFACE_NORMAL_OUTLIER_SHARE

#: Höchste Konditionszahl für einen bestimmbaren Kugelmittelpunkt.
#:
#: Die Auskunft kommt ausschließlich aus den **zentrierten Einheitsnormalen**:
#: Sie ist damit unabhängig von Lage, Maßstab und Einheit. Zwei selbst erzeugte
#: 5°-Kalotten mit verschiedener Triangulierung liegen bei 852 und 952; eine
#: nur 0,049 mm hohe 2°-Kalotte bei 6615. Die größten falschen Kugeln des
#: Gartenhalters lagen bei 4427 und 6178. Zweitausend hält die echte flache
#: Kalotte mit Faktor zwei Abstand und gibt keinen unbestimmten Fernmittelpunkt
#: als bearbeitbares Merkmal aus.
SPHERE_MAX_CENTRED_CONDITION = 2_000.0

#: Kleinster Anteil der zweiten an der ersten Normalen-Krümmungsrichtung.
#:
#: Eine Kugelkalotte belegt ihre Krümmung in zwei Richtungen. Die beiden
#: verschieden triangulierten 5°-Kalotten liegen bei 0,96 und 1,00, die
#: Referenzpfanne bei 0,99. Ein 40° langer, aber nur 4° breiter Kugelstreifen
#: liegt bei 0,10: Seine Punkte stammen zwar von einer Kugel, der Ausschnitt
#: allein belegt aber kein sicher bearbeitbares Kugelmerkmal. Die Hälfte lässt
#: der Triangulierung weiten Abstand, ohne solche Bänder umzudeuten.
SPHERE_MIN_CURVATURE_BALANCE = 0.5

#: Größter geometrischer Stützpunktfehler als Anteil der lokalen Fleckausdehnung.
#:
#: Der relative Rückstand bleibt für die Formauswahl auf den Radius bezogen.
#: Ein großer Radius darf jedoch örtliche Formabweichungen nicht kleinrechnen.
#: Die vorhandene lokale Kugelgrenze gilt deshalb auch an den maßführenden
#: Kegel-/Torusecken, jeweils am geometrischen Abstand und am schlechtesten
#: Punkt. Die unabhängigen Kalotten, Teilkegel und Teilringe bleiben erhalten;
#: die bisherigen Freiform-Gegenfälle werden nach dem Endmaßfit weiterhin
#: verworfen. Sehnenpunkte sind keine Stütze und tragen ihre eigene Hautprüfung.
ROUND_LOCAL_TOLERANCE = 0.002

#: Um wie viel besser eine Kugel passen muss, um einen brauchbaren Kegelfit zu
#: verdrängen — als Verhältnis der Rückstände.
#:
#: **Der Fall (03.09.2026):** Eine Kugelpfanne Ø 16 in einem Quader wurde als
#: *Senkung* erkannt, sobald das Netz fein genug war. Der Kegelzweig kommt vor
#: dem Kugelzweig, und sein Rückstand rutscht mit steigender Feinheit unter
#: :data:`CONE_TOLERANCE` (0,08):
#:
#: | Netz | Kegel-Rückstand | Kugel-Rückstand | Verhältnis | erkannt als |
#: |---|---|---|---|---|
#: | grob (482 Dreiecke) | 0,0891 | 0,00049 | 182 | Kugel — Kegel fiel durch |
#: | fein (1602) | **0,0779** | 0,00009 | 848 | **Kegel** |
#: | sehr fein (5746) | 0,0736 | 0,00002 | 3733 | **Kegel** |
#:
#: Ein feineres Netz machte die Erkennung also **schlechter**, und zwar genau
#: an heruntergeladenen Modellen, die fein vernetzt sind.
#:
#: **Die Reihenfolge Kegel-vor-Kugel bleibt**, und sie hat ihren Grund: Eine
#: Senkung passt auf eine Kugel besser, als man denkt, und ein `hole_1`, das
#: plötzlich `sphere_1` hieße, wäre für jede Bohrungs-Operation unsichtbar.
#: Deshalb verdrängt die Kugel den Kegel nicht, wenn sie *etwas* besser ist,
#: sondern nur, wenn sie **um Größenordnungen** besser ist. An einer echten
#: Senkung ist der Kegel der bessere Fit (Verhältnis 0,7); an einer Pfanne
#: liegt es bei 182 aufwärts. Zwischen 0,7 und 182 ist Platz für jede Zahl —
#: zehn liegt in der Mitte der Lücke, gemessen an vier Körpern.
SPHERE_BEATS_CONE = 10.0

#: Wie weit zwei Kegelstücke im Halbwinkel auseinanderliegen dürfen, um noch
#: derselbe Kegel zu sein — in Grad.
#:
#: **Gemessen an Senkungen Ø 12 über Bohrungen Ø 6** (03.09.2026): Der Mantel
#: zerfällt in Ausschnitte, und je kleiner ein Ausschnitt, desto weiter fittet
#: er den Winkel daneben — 44,94° bei 72 Dreiecken, 47,14° bei 37, **50,68°
#: bei 28**. Fünf Grad standen hier zuerst, nach dem ersten gemessenen Fall;
#: der zweite lag bei 5,74 und blieb draußen. Das ist die Lehre an der Zahl:
#: Eine Schranke aus **einer** Messung ist geraten, nicht gemessen.
#:
#: **Zehn Grad sind gefahrlos, weil die Schranke nicht die trennende ist.** Zwei
#: Kegel mit derselben Spitze **und** derselben Achse, aber verschiedenem
#: Winkel, schneiden einander — das ist keine Oberfläche, die es an einem
#: Körper gibt. Getrennt wird über die Spitze (gemessen 30 mm zwischen zwei
#: Senkungen gegen 0,15 mm innerhalb einer), und der gemeinsame Fit muss
#: danach immer noch ``good`` sein. Diese Schranke fängt nur den groben
#: Ausreißer ab, bevor ein Fit dafür gerechnet wird.
CONE_SAME_ANGLE = 10.0

#: Wie weit zwei Kegelstücke in der Achse auseinanderstehen dürfen, um noch
#: derselbe Kegel zu sein — in Grad.
#:
#: **Eine eigene Schranke und nicht** :data:`SINK_AXIS_LIMIT`, die zwei Grad
#: erlaubt: Das ist die Schranke des Rings, und dort trennt sie zwei *fertige*
#: Einpassungen. Hier steht auf einer Seite oft ein Splitter aus wenigen
#: Dreiecken, und der fittet die Achse so ungenau wie den Winkel — gemessen
#: 3,6 Grad an dem Ausschnitt, der eine Senkung zum dritten Merkmal machte.
#: Mit zwei Grad blieb er draußen und der Objektbaum zeigte zwei Senkungen
#: statt einer.
#:
#: **Weiten ist hier gefahrlos, weil die Trennung woanders liegt:** Zwei
#: verschiedene Senkungen unterscheiden sich in der **Spitze** (gemessen
#: 30 mm gegen 0,15 mm innerhalb einer), nicht in der Achse — bei
#: gleichgerichteten Bohrungen ist die Achse sogar identisch. Und der
#: gemeinsame Fit muss danach immer noch ``good`` sein.
CONE_SAME_AXIS = 8.0

#: Wie stark die Achse einer Senkung von der ihrer Bohrung abweichen darf, in
#: Grad. Beide entstehen in derselben Aufspannung — was hier streut, ist die
#: Einpassung und nicht die Fertigung.
SINK_AXIS_LIMIT = 2.0


#: Ab welcher Überdeckung um die Achse ein Zylinderfleck ein **ganzer**
#: Zylinder ist — darunter ist er ein Ausschnitt und damit eine Verrundung.
#:
#: Gemessen über den Korpus: Bohrungen und Zapfen überdecken 345 bis 354 Grad,
#: eine verrundete Quaderkante 90. Dreihundert Grad liegen mit weitem Abstand
#: dazwischen; die Facettierung kostet die vollen Zylinder je nach Segmentzahl
#: sechs bis fünfzehn Grad, und mehr als das darf die Schwelle nicht fordern.
FULL_TURN_SPAN = 300.0

#: Eine Kante hat zwei Seiten. Eine Rundung, die genau an zwei ebene Flächen
#: quer zu ihrer Achse grenzt, ersetzt die Kante zwischen ihnen; jede andere
#: Nachbarschaft macht sie zur Wand.
SIDES_OF_AN_EDGE: Final = 2

#: Ab wie vielen koaxialen Zylindern gleichen Durchmessers ein Stapel als
#: Gewinde gilt und nicht als Zapfen.
#:
#: Gemessen über den Korpus: Es gibt genau einen Fall mit **zwei** solchen
#: Zylindern — die gespiegelten Gliedmaßen der Figur — und keinen mit dreien.
#: Ein M6-Gewinde bringt acht mit, eine je Windung.
THREAD_TURNS = 3

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

#: Ab welchem Anteil Kugeln und Ringe an **allen** Merkmalen das Modell eine
#: Freiform ist — ein Scan, eine Figur, ein Segel.
#:
#: **Der Grund ist geometrisch, nicht statistisch.** Eine gekrümmte Fläche
#: lässt sich örtlich immer an eine Kugel anpassen — das ist die Definition
#: der Krümmung. :func:`_split_patches_by_curvature` teilt eine Freiform an ihren
#: Krümmungssprüngen in Flecken annähernd gleicher Krümmung, und auf jeden
#: davon passt eine Kugel oder ein Ring innerhalb der Toleranz. Ein
#: Kiefer-Scan eines Kunden (05.09.2026) trug so 162 Kuppeln, 98 Pfannen,
#: 15 Wülste und 6 Kehlen; ein Segel hat keine 222 Kugeln.
#:
#: **Gemessen am 05.09.2026, alle Modelle auf 60 000 Dreiecke verkleinert:**
#:
#: | Modell | Art | Merkmale | Kugel + Ring |
#: |---|---|---|---|
#: | Korpus, Kundenzylinder, Mast, Besenhalter | konstruiert | 1 bis 26 | 0 bis 14 % |
#: | Screen-Cover | konstruiert | 93 | 48 % |
#: | Nozzle-Box | konstruiert | 116 | **59 %** |
#: | Retro-Maus, Spiderman, Rumpf, Katze, Segel | Figur/Scan | 112 bis 958 | **77 bis 95 %** |
#:
#: Das Register vom 04.09.2026 nannte für Konstruiertes „0 bis 7 %, keine
#: Überlappung" — das galt für dessen 21 Modelle. Die Nozzle-Box mit ihren
#: verrundeten Kanten liegt bei 59 und zeigt, wie nah die Lücke ist: 59 zu 77.
#: Sieben Zehntel liegen dazwischen, und keine der beiden Seiten hat mit
#: siebzehn Modellen einen Beweis; der Vorbehalt steht im Register.
#:
#: **Zwei Schranken, die nicht getrennt haben, stehen hier, damit sie niemand
#: ein zweites Mal misst:** Ob ein runder Fleck an Knicken oder Ebenen endet
#: (ein gemachtes Merkmal tut das, ein Freiformfleck geht glatt in den nächsten
#: über), trennt das Segel und die Katze (Median 0,00) von Konstruiertem
#: (0,75 bis 1,00) — aber nicht den Voronoi-Spiderman, dessen Streben lauter
#: Knicke sind, und nicht die verkleinerten Netze, deren grobe Dreiecke
#: überall Knicke bilden; und eine echte tangentiale Verrundung am Fuß einer
#: Säule endet an gar keinem Knick (0,00). Die Merkmals**zahl** allein trennt
#: ebenfalls nicht: 116 an der Nozzle-Box gegen 112 an der Katze.
FREEFORM_ROUND_SHARE: Final = 0.7

#: … und ab wie vielen Kugeln und Ringen der Anteil überhaupt zählt.
#:
#: Ein Ring allein ist zu hundert Prozent rund und trotzdem ein Ring
#: (``torus_ring.stl``: ein Merkmal, ein Torus). Zwölf sind mehr, als ein
#: konstruiertes Teil des Korpus oder der Kundenmodelle je hatte (höchstens
#: eine Pfanne, ein Ring, zwei Kegel), und weniger als die kleinste Figur
#: brachte (96 an der Katze).
FREEFORM_ROUND_COUNT: Final = 12

#: Ab welchem Anteil an der Oberfläche die **zerfallende Fläche** eines
#: Körpers seine Haut ist (RM-193, Entscheidung Robert 22.09.2026): die
#: gekrümmten Flecken, auf die keine Grundform passt und die nach Krümmung in
#: Splitter zerfallen (:data:`FREEFORM_SPLINTERS` Stücke unter
#: :data:`FREEFORM_PIECE_SHARE`), über **alle** Flecken zusammen. Darüber ist
#: der Körper eine Figur, ein Scan, ein erzeugtes Netz, und seine Splitter
#: werden nicht eingepasst.
#:
#: **Zwei Drittel, und dazwischen liegt eine breite Lücke** — gemessen am
#: 22.09.2026 an ``F:\3D Dateien`` (170 Dateien, 464 Körper): Konstruiertes
#: liegt bei null bis 60 Prozent, und die vier höchsten Fälle sind ein Rohr
#: mit Gewinde (Pool-Brunnen, 57 und 60), ein Scraper-Griff (51) und ein
#: Wandhalter (55); Figuren, Scans und erzeugte Netze liegen bei 71 bis 94
#: (Katze 71, Zauberturm 75 bis 88 — in **zwei** Flecken zu 44 und 32
#: Prozent, deshalb die Summe —, Schüssel 89, Drache 93, Retro-Maus 94). Die
#: Schwelle sitzt in der Lücke, näher an den Figuren als an der Mitte: Ein
#: konstruiertes Teil, das hier durchrutscht, verliert seine Verrundungen und
#: Senkungen; eine Figur, die es nicht tut, kostet nur Zeit — und wird von
#: der Zählung darunter (:func:`is_a_freeform`) weiter gefangen. Eine Kapsel
#: oder ein Ring liegen bei hundert Prozent gekrümmter Fläche, zerfallen aber
#: nicht (ein Stück) und bleiben, was sie sind.
FREEFORM_SKIN_SHARE: Final = 0.65

#: Wie viele Splitter — Stücke unter :data:`FREEFORM_PIECE_SHARE` — die
#: Nachtrennung aus einem Fleck machen muss, damit er zur formlosen Fläche
#: zählt und mit seinen Stücken wartet. Gemessen am 22.09.2026: der Drache aus TripoSG 27 554
#: Splitter, Roberts Schüssel 2 670, der Scan-Körper der Tests 1 640; ein
#: Buchstabe, eine Kapsel, ein Ellipsoid, ``generated_figure.stl`` null bis
#: einen. Eine gestaltete Fläche zerfällt in Stücke von Gewicht, Rauschen in
#: Splitter — hundert liegt eine Größenordnung über dem einen und eine unter
#: den 1 640.
FREEFORM_SPLINTERS: Final = 100

#: Wie groß ein Splitstück einer Haut sein muss, damit es eingepasst wird —
#: als Anteil an der Oberfläche des Körpers. Ein Splitter aus sieben bis
#: fünfzig Dreiecken einer glatten Haut ist ihre Tesselierung, nicht ihre
#: Form: Seine Normalen spreizen drei Grad, und aus drei Grad bestimmt kein
#: Löser eine Achse (2 275 Kegelverfeinerungen am Drachen, alle ``None``, 33
#: der 37 Sekunden für null Merkmale). Ein tangential eingeblendeter Zapfen
#: oder eine Verrundung auf einer Haut ist dagegen ein Stück von Gewicht: Ein
#: Zapfen Ø 10 auf einer Figur von 100 000 mm² liegt bei drei Tausendsteln
#: und wird weiter eingepasst; am Drachen bleiben 23 Stücke, an der Schüssel
#: 13.
FREEFORM_PIECE_SHARE: Final = 0.001

#: Was auf einer Freiform keine Merkmale sind: die vier eingepassten
#: Rundformen. Bohrung und Zapfen bleiben — eine Zylindereinpassung verlangt
#: Normalen senkrecht zur Achse und einen engen Kreis, das erfüllt eine
#: Freiform nur dort, wo wirklich ein Zylinder steckt: Der Kiefer-Scan trug
#: genau einen Zapfen, und der war echt. Flächen, Kantenzüge und Gewinde
#: stehen ohnehin nicht zur Debatte.
_SHAPES_ON_A_FREEFORM: Final[frozenset[str]] = frozenset({"sphere", "torus", "cone", "fillet"})

#: Die Merkmalsarten, die diese Datei aus einem Netz lesen kann.
#:
#: Gebraucht wird die Liste außerhalb, und zwar für eine Unterscheidung, die
#: sonst niemand treffen kann: Ein **erzeugtes** Merkmal (§21.2) lässt sich nur
#: dann gegen die Geometrie prüfen, wenn die Erkennung seine Art überhaupt
#: sieht. Ein Gewinde sieht sie nicht — es entsteht in einem Baustein und
#: trägt seinen Namen von dort. Wer es wie eine Bohrung prüfte, verlöre es bei
#: jeder Operation, weil kein Partner zu finden ist.
DETECTABLE_KINDS: frozenset[str] = frozenset(
    {
        "hole",
        "pin",
        "face",
        "edge_loop",
        "cone",
        "sphere",
        "torus",
        "fillet",
        "void",
        "slot",
        "curved_face",
        "pattern",
    }
)


#: Erkennungsergebnisse je Netz, solange der Prozess läuft.
#:
#: Die Erkennung läuft nach **jeder** Operation, und das ist richtig (§21.2):
#: Sonst wäre ``hole_3`` in Schritt fünf ein anderes Loch als in Schritt vier.
#: Falsch war nur, dass sie auch dann lief, wenn das Netz nachweislich dasselbe
#: ist — nach einem Cache-Treffer nämlich, wo gar nichts gerechnet wurde.
#:
#: Gemessen an den neun Beispielprojekten, je drei Auswertungen wie beim
#: Öffnen: **11,65 s Erkennung, davon 7,52 s auf bitgleichen Netzen** — 65
#: Prozent. Bei „Aushöhlen und teilen" sind es 3,53 s von 5,28, bei „Dose mit
#: Deckel" 2,88 von 3,88.
#:
#: **Was hier liegt, ist genau so weit gefasst, wie es sicher ist.**
#: ``detect`` hängt an nichts als am Netz; die *Zuordnung* der Namen hängt
#: dagegen an den vorigen Merkmalen und an ``operation.matches`` (§15.7), und
#: die bleibt außen vor. Ein Cache, der auch sie überspränge, gäbe beim zweiten
#: Öffnen andere Namen zurück als beim ersten — schlimmer als jede Wartezeit.
_FEATURE_CACHE: OrderedDict[bytes, dict[FeatureId, Feature]] = OrderedDict()

#: Je Eintrag die Zahl seiner Flächenindizes — das Gewicht, das
#: :data:`CACHE_INDEX_LIMIT` deckelt. Getrennt geführt, weil die Summe sonst
#: bei jeder Verdrängung über alle Merkmale aller Einträge neu zu rechnen wäre.
_CACHE_INDICES: OrderedDict[bytes, int] = OrderedDict()

#: Je Eintrag, wie viele Rundformen :func:`_shapes_on_a_freeform` weggelassen
#: hat — null für jedes Modell, das keine Freiform ist. Neben dem Ergebnis
#: statt darin, weil ``detect`` seit je ein Wörterbuch von Merkmalen
#: zurückgibt und zwei Dutzend Aufrufer genau das erwarten; die Auswertung
#: fragt über :func:`freeform_dropped` nach und macht einen Befund daraus.
_FREEFORM_DROPPED: OrderedDict[bytes, int] = OrderedDict()

#: Je Eintrag die Komponentenzahl des Körpers, wenn :func:`detect_voids` seine
#: Schalen nicht lesen konnte — sonst null. Dieselbe Bauart wie
#: :data:`_FREEFORM_DROPPED`, aus demselben Grund: Acht Einschlüsse, die
#: verschwinden, weil eine native Differenz scheiterte, sind sonst nirgends
#: zu sehen (Regel 17); :func:`unreadable_void_shells` nennt der Auswertung
#: die Zahl.
_UNREADABLE_VOIDS: OrderedDict[bytes, int] = OrderedDict()

#: Je Eintrag, ob :func:`detect` das Modell als Freiform eingestuft hat.
#: Neben :data:`_FREEFORM_DROPPED`, weil die Zahl allein es nicht mehr sagt:
#: Seit RM-193 werden die Splitter einer Haut gar nicht erst eingepasst, und
#: eine Freiform kann so null weggelassene Rundformen tragen — der Befund
#: der Auswertung fragt über :func:`recognised_as_freeform` nach dem Urteil.
_FREEFORM: OrderedDict[bytes, bool] = OrderedDict()

#: Wie viele Zwischenkörper der Cache behält. Eine Auswertung untersucht nicht
#: nur die fertigen Objekte, sondern nach jeder Operation deren damaliges Netz.
#: Der gemessene Kundenverlauf hat bei 163 Operationen 132 verschiedene Netze;
#: eine kleinere LRU-Grenze verdrängt beim nächsten Durchlauf die später noch
#: benötigten Einträge und macht aus lauter Treffern eine vollständige
#: Neuberechnung. 256 lässt dafür Luft und bleibt trotzdem fest begrenzt.
CACHE_LIMIT = 256

#: Wie viele Flächenindizes der Cache insgesamt behält — die zweite Schranke
#: neben :data:`CACHE_LIMIT`, und die einzige, die bei großen Modellen greift.
#:
#: **Gemessen am 03.09.2026:** Ein Eintrag für `garden-hose-holder.3mf`
#: (392 532 Dreiecke, 797 Merkmale) wiegt **3,9 MiB**, davon 2,7 allein an
#: Flächenindizes — 97 425 Stück zu je 28 Byte. Mit 256 solcher Einträge hielte
#: der Cache **991 MiB**; schon der oben genannte Kundenverlauf mit 132
#: verschiedenen Netzen käme auf gut 500.
#:
#: **Die Anzahl war die falsche Größe, um zu zählen.** Sie stimmt für kleine
#: Modelle — ein Teil mit tausend Indizes je Eintrag füllt bei 256 Einträgen
#: sieben Megabyte, und dort soll der Cache voll ausgenutzt werden. Bei einem
#: großen kostet derselbe Zähler das Hundertfache. Deshalb zwei Schranken: Die
#: Anzahl deckelt die kleinen, die Menge die großen; der Übergang liegt bei
#: rund 47 000 Indizes je Eintrag.
#:
#: **Zwölf Millionen sind rund 320 MiB** und tragen den gemessenen
#: Kundenverlauf an einem 400 000-Dreieck-Modell fast vollständig (132 Netze
#: bräuchten 12,8). Wer ein noch größeres Modell fährt, verliert die ältesten
#: Einträge früher — das ist der Preis dafür, nicht ein Gigabyte zu halten,
#: und er ist eine Abwägung und keine Messung.
CACHE_INDEX_LIMIT = 12_000_000


def _mesh_key(mesh: MeshData) -> bytes:
    """Der Fingerabdruck eines Netzes: Ecken und Dreiecke, sonst nichts.

    Nicht die Objektkennung und nicht ``id()`` — ein freigegebenes Objekt gibt
    seine Adresse wieder her, und der nächste Körper an derselben Stelle bekäme
    fremde Merkmale. Die Slots gehören auch nicht dazu: Sie färben, sie ändern
    keine Geometrie.

    Kostet 1,4 bis 1,8 Prozent eines Erkennungslaufs (gemessen an 1 280 und
    81 920 Dreiecken) — der Preis dafür, die Frage überhaupt stellen zu dürfen.

    **Und er wird je Netz einmal gezahlt.** Die Auswertung fragt nach jedem
    Schritt dieselben Netze wieder — ``detect``, ``freeform_dropped``,
    ``unreadable_void_shells``, dazu die Übertragung auf ein bewegtes Netz —,
    und jede Frage rechnete den Abdruck neu: 9 ms an 204 000 Dreiecken, sechs
    Aufrufe je Auswertung (gemessen am 22.09.2026). Abgelegt wird er im Cache
    des Netzes selbst, der mit dessen Geometrie verfällt — dieselbe Ablage wie
    ``MeshData.component_count``, aus demselben Grund: Ein eigenes Feld gibt es
    an der eingefrorenen Klasse nicht, und ``id()`` wäre der Fehler von oben.
    """
    body = mesh.raw
    cache = getattr(body, "_cache", None)
    if cache is not None:
        cache.verify()
        known = cache.cache.get("solidon_mesh_key")
        if known is not None:
            return bytes(known)
    key = hashlib.blake2b(
        np.ascontiguousarray(body.vertices, dtype=np.float64).tobytes()
        + np.ascontiguousarray(body.faces, dtype=np.int64).tobytes(),
        digest_size=16,
    ).digest()
    if cache is not None:
        cache["solidon_mesh_key"] = key
    return key


def forget_cache() -> None:
    """Vergisst die gemerkten Erkennungen — für Tests und Messungen."""
    _FEATURE_CACHE.clear()
    _CACHE_INDICES.clear()
    _FREEFORM_DROPPED.clear()
    _FREEFORM.clear()
    _UNREADABLE_VOIDS.clear()
    with _MEMORY_LOCK:
        _SUPPORT_CACHE.clear()
        _DIGESTS.clear()
        for memory in _MEMORIES.values():
            memory.answers.clear()
            memory.digests.clear()


def _one_body(mesh: MeshData) -> MeshData:
    """Dasselbe Teil, gefragt nach seiner Geometrie statt nach seiner Speicherform.

    **Der Zwilling des Fundes vom 26.08.2026.** Eine STL kennt keine
    gemeinsamen Ecken: Sie schreibt jedes Dreieck mit seinen eigenen drei
    Punkten hin. Ungeschweißt geladen — ``generate.into_project`` tut das für
    jedes erzeugte Modell — hat ein solches Netz **null** Nachbarschaften und
    **null** Facetten, gemessen an ``plate_holes.stl``: 796 Dreiecke, 2 388
    Ecken, 0 Nachbarschaften. Verschweißt sind es 392 Ecken und 1 194
    Nachbarschaften.

    Darauf baut jede Erkennung auf. ``detect_edge_loops`` hat den Fall für sich
    gelöst und meldete danach die wahren sechs offenen Stellen statt 3 372; die
    übrigen ``detect_*`` fragten weiter dasselbe Falsche — und dort fällt es
    nicht als Übermaß auf, sondern als **Schweigen**: null Merkmale statt zehn,
    neun und einem. Ein Übermaß sieht jeder, ein Schweigen niemand.

    Zusammengelegt wird nur **rechnerisch**: Das Netz im Dokument bleibt, wie
    es der Kunde geladen hat, und die Dreiecke behalten ihren Platz — daran
    hängen die Merkmalsnummern (§21.3), und ein Merkmal, das nach dem Laden
    anders heißt, zeigt ins Leere. Gemessen an ``plate_holes.stl``: 1 996 Ecken
    zusammengelegt, 796 Dreiecke vorher wie nachher, alle an derselben Stelle.

    Über dieselbe Toleranz wie ``repair.merge_vertices`` und
    ``detect_edge_loops`` (``weld_tolerance`` an der Modelldiagonale) — zwei
    Antworten auf „ist das dieselbe Ecke" wären zwei Topologien desselben
    Körpers.

    Vorgeschaltet ist :func:`fully_stitched`, und zwar erst nach einer
    Messung: An einer Kugel mit 327 680 Dreiecken, an der es nichts zu
    verschweißen gibt, kostete der Versuch allein rund 160 ms — die Erkennung
    stieg von 571 auf 733 ms, achtundzwanzig Prozent für eine Antwort, die
    schon dastand. Die Abkürzung rechnet dabei nichts nach, was sie abkürzt:
    Sie liest die Nachbarschaftszahl, die ohnehin gebraucht wird.
    """
    if fully_stitched(mesh.raw):
        return mesh
    # **Einmal je Eingangskörper.** Merkmalfenster, Steckbrief und Ansicht
    # fragen nach jedem Klick dieselbe Geometrie, und jede Frage schweißte
    # neu — mit einem neuen Körper, an dem kein Merker eine Antwort fand.
    # Gemerkt wird nur die verschweißte Kopie, nie das Netz selbst: Es im
    # Merker seines eigenen Körpers zu halten hielte den Körper für immer.
    welded: MeshData | None = remembered("one_body", mesh.raw, (), lambda: _welded(mesh))
    return welded if welded is not None else mesh


def _welded(mesh: MeshData) -> MeshData | None:
    """Die verschweißte Kopie — oder nichts, wenn es nichts zu verschweißen gab."""
    welded, gone = merge_vertices(mesh)
    return welded if gone else None


def detect(
    mesh: MeshData, *, check_cancelled: Callable[[], None] | None = None
) -> dict[FeatureId, Feature]:
    """Alles, was dieses Modul erkennen kann, mit stabilen Namen.

    Bohrungen und Stifte teilen ihre Suche (siehe :func:`_cylinders`) — beide
    zu erfragen kostet also, was früher eines kostete.

    ``check_cancelled`` darf ``OperationCancelled`` werfen (§2.8). Geprüft
    wird zwischen Phasen und Fitflecken; ein laufender nativer Aufruf endet
    vorher. Nur ein vollständiger Durchgang wird im Merkmalscache abgelegt.
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
    # **Erst das Teil, dann die Suche.** Ohne diese Zeile sieht alles
    # Folgende an einer ungeschweißten Datei null Nachbarschaften und
    # findet nichts — siehe :func:`_one_body`.
    # **Dasselbe Netz wird nicht zweimal untersucht.** Die Erkennung läuft nach
    # jeder Operation, auch nach einem Cache-Treffer, wo die Geometrie gar
    # nicht gerechnet wurde — und ein bitgleiches Netz kann keine anderen
    # Merkmale haben. Der Grund und die Zahlen stehen bei :data:`_FEATURE_CACHE`.
    if check_cancelled is not None:
        check_cancelled()
    key = _mesh_key(mesh)
    if check_cancelled is not None:
        check_cancelled()
    known = _FEATURE_CACHE.get(key)
    if known is not None:
        _FEATURE_CACHE.move_to_end(key)
        # Eine Kopie, weil der Aufrufer sein Ergebnis behalten darf. Die
        # ``Feature``-Objekte selbst sind unveränderlich (``frozen=True``) und
        # dürfen geteilt werden; die Zuordnung darüber hinein nicht.
        return dict(known)

    mesh = _one_body(mesh)
    if check_cancelled is not None:
        check_cancelled()
    # **Die Sperre gehört um den ganzen Durchgang, nicht nur um die
    # Einpassung.** Die Begründung steht bei ihrer Schwester in
    # :func:`_fitted`; hier zählt die Reichweite. Gemessen am selben Segel mit
    # 421 194 Dreiecken: nur in ``_fitted`` gesperrt bleiben 127 317 Hashes
    # und 8,20 s, um den ganzen Durchgang gelegt sind es 6,38 s — die acht
    # ``detect_*`` unten lesen dieselben Normalen noch einmal.
    #
    # Auf dem Netz **nach** ``_one_body`` und nicht auf dem übergebenen: Jenes
    # gibt bei mehreren Komponenten ein neues zurück, und eine Sperre auf dem
    # alten hielte ein Netz still, das niemand mehr liest.
    with mesh.raw._cache:
        planar = _large_facet_faces(mesh.raw, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        fitted = _fitted(mesh, planar=planar, check_cancelled=check_cancelled)
        sphere_candidates = _sphere_candidates(mesh, fitted.spheres)
        sphere_features = detect_spheres(mesh, sphere_candidates, check_cancelled=check_cancelled)
        torus_candidates = _torus_candidates(mesh, fitted.tori)
        torus_features = detect_tori(mesh, torus_candidates, check_cancelled=check_cancelled)
        recognised_round_faces = {
            frozenset(feature.face_indices) for feature in (*sphere_features, *torus_features)
        }
        helix_faces = [set(helix.face_indices) for helix in fitted.helices]
        unpublished_round_shapes = sum(
            1
            for _fit, patch in (*sphere_candidates, *torus_candidates)
            if frozenset(patch) not in recognised_round_faces
            and not any(
                sum(face in faces for face in patch) * 2 > len(patch) for faces in helix_faces
            )
        )
        # **Einmal gefiltert, dann weitergereicht.** ``detect_fillets`` fragte
        # ``_fillets_worth_naming`` selbst, und die Langlochsuche darunter
        # fragte es ein zweites Mal auf derselben rohen Eingabe. Jetzt rechnet
        # es ``detect`` einmal, und beide bekommen dasselbe.
        #
        # **Der Gewinn ist klein, und die Zahl gehört dazu:** an einer Platte
        # mit 64 verrundeten Taschen **0,2 ms** von 1324 — der zweite Aufruf in
        # ``detect_fillets`` bleibt und arbeitet auf der bereits gesiebten
        # Liste, die dort nichts ausgesiebt hat (256 Bögen rein, 256 raus).
        # Die 5,7 ms, die hier einmal standen, waren die Dauer **eines**
        # Aufrufs und nicht die Ersparnis. Der Grund für die Änderung ist
        # deshalb weniger die Zeit als
        # die Quelle: Zwei Stellen, die dieselbe Frage stellen, geben eines
        # Tages zwei Antworten.
        worth_naming = _fillets_worth_naming(mesh, fitted.fillets)
        # Die Flächen zuerst ohne Träger und Innenlage — was das Muster gleich
        # verschluckt, braucht beides nie (:func:`_face_candidates`).
        face_entries = _planar_face_entries(mesh, planar=planar, check_cancelled=check_cancelled)
        face_entries.sort(key=lambda entry: (-round(entry[1], 4), _corner_key(mesh.raw, entry[0])))
        found: dict[FeatureId, Feature] = {}
        for phase in (
            lambda: detect_holes(mesh, fitted.cylinders, fitted.cones),
            lambda: detect_pins(mesh, fitted.cylinders),
            lambda: detect_fillets(mesh, worth_naming, check_cancelled=check_cancelled),
            lambda: detect_cones(mesh, fitted.cones, check_cancelled=check_cancelled),
            lambda: sphere_features,
            lambda: torus_features,
            lambda: _face_candidates(mesh.raw, face_entries),
            lambda: detect_edge_loops(mesh),
        ):
            if check_cancelled is not None:
                check_cancelled()
            for feature in phase():
                found[feature.id] = feature
        if check_cancelled is not None:
            check_cancelled()
        found = _threads_instead_of_phantoms(mesh, found, helices=fitted.helices)
        if check_cancelled is not None:
            check_cancelled()
        # **Nach dem Gewinde und vor dem Freiformfilter.** Nach dem Gewinde,
        # weil eine Wendel dieselben Zylinderausschnitte verschluckt und die
        # engere Aussage ist: Was ein Gewindegang ist, ist kein Langloch. Vor
        # dem Freiformfilter aus demselben Grund wie beim Einschluss darunter —
        # die zwei Bögen zählten sonst beim Urteil über das ganze Modell mit
        # und schöben es Richtung Figur, obwohl sie zu einer Öffnung gehören.
        found = slots_instead_of_half_bores(
            mesh,
            found,
            worth_naming,
            stadiums=[
                entry
                for entry in fitted.stadiums
                if not _too_small_to_make(entry[0].radius * 2.0)
                and not _a_sliver(mesh.raw, entry[1])
            ],
            check_cancelled=check_cancelled,
        )
        if check_cancelled is not None:
            check_cancelled()
        # **Nach dem Langloch und vor dem Einschluss.** Nach dem Langloch,
        # weil eine Reihe Langlöcher Langlöcher bleibt (``slot`` bildet keine
        # Zelle); vor dem Einschluss, weil der die Träger seiner Flächen
        # einsammelt — und die bekommen die Flächen erst, wenn feststeht,
        # welche bleiben (:func:`_faces_finished_in`): Ein dichtes Rändel hat
        # 32 000 Flächen, nach dem Falten sieben (§21.1, RM-207).
        found = patterns_instead_of_cells(mesh, found, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        found = _faces_finished_in(mesh, found, face_entries, check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        found = _faces_on_a_round_wall(mesh, found, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        # **Vor dem Freiformfilter, und das ist keine Reihenfolge nach Gefühl.**
        # Die Schale eines Einschlusses trägt echte Rundformen; blieben sie in
        # der Liste, zählten sie beim Urteil über das ganze Modell mit und
        # schöben es Richtung Freiform. Hier gehen sie weg, weil sie zu einem
        # Einschluss gehören — nicht, weil das Modell eine Figur wäre.
        voids, unreadable = _detect_voids(mesh, check_cancelled=check_cancelled)
        found = voids_instead_of_phantom_bores(found, voids, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        found = _partial_cones_folded(mesh, found, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        found = _partial_bores_marked(mesh, found, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        freeform = is_a_freeform(
            found, unpublished_round_shapes=unpublished_round_shapes, skin=fitted.freeform_skin
        )
        found, left_out = _shapes_on_a_freeform(
            found, unpublished_round_shapes=unpublished_round_shapes, skin=fitted.freeform_skin
        )
        if check_cancelled is not None:
            check_cancelled()
        # **Zuletzt, denn sie nehmen den Rest.** Eine gerundete Seite ist,
        # was nach Bohrungen, Stiften, Verrundungen, Kugeln, Ringen, Gewinden
        # und ebenen Flächen an glatter, gerundeter Oberfläche übrig bleibt —
        # deshalb nach allen anderen und nach dem Freiformfilter: Auf einer
        # Figur wäre die ganze Haut eine einzige Seite, und die sagt nichts.
        if not freeform:
            for feature in detect_curved_faces(mesh, found, check_cancelled=check_cancelled):
                found[feature.id] = feature
    if check_cancelled is not None:
        check_cancelled()
    _log.info(
        "detected %d features, %d left out as freeform%s",
        len(found),
        left_out,
        " (skin)" if fitted.freeform_skin else "",
    )
    _remember(key, found, left_out, unreadable, freeform)
    return dict(found)


def known_detection(mesh: MeshData) -> dict[FeatureId, Feature] | None:
    """Die gemerkte Erkennung dieses Netzes — oder ``None``, ohne zu rechnen.

    Für Aufrufer, die eine Antwort nehmen, wenn sie dasteht, und sonst ohne
    auskommen: die Live-Vorschau eines Dialogs zeigt Geometrie, keine
    Merkmale, und eine Erkennung von einer Sekunde je getippter Zahl wäre
    dort eine Sekunde für nichts (``scene.evaluate``, ``detect_features``).
    """
    known = _FEATURE_CACHE.get(_mesh_key(mesh))
    if known is None:
        return None
    _FEATURE_CACHE.move_to_end(_mesh_key(mesh))
    return dict(known)


def _remember(
    key: bytes, found: dict[FeatureId, Feature], left_out: int, unreadable: int, freeform: bool
) -> None:
    """Eine vollständige Erkennung unter dem Abdruck ihres Netzes ablegen.

    Die drei Nebentabellen werden zusammen mit dem Ergebnis geführt, damit
    Verdrängung und Nachfrage dieselben Einträge sehen — ob die Antwort
    gerechnet wurde (:func:`detect`) oder von einem bewegten Zwilling stammt
    (:func:`carry_detection`), ist für die Ablage dasselbe.
    """
    _FEATURE_CACHE[key] = found
    _CACHE_INDICES[key] = sum(
        len(feature.face_indices)
        + sum(len(patch.face_indices) for patch in feature.surface_patches)
        for feature in found.values()
    )
    _FREEFORM_DROPPED[key] = left_out
    _FREEFORM[key] = freeform
    _UNREADABLE_VOIDS[key] = unreadable
    while len(_FEATURE_CACHE) > CACHE_LIMIT or sum(_CACHE_INDICES.values()) > CACHE_INDEX_LIMIT:
        if len(_FEATURE_CACHE) == 1:
            # Ein einzelner Eintrag über der Grenze bleibt: Ihn wegzuwerfen
            # hieße, ihn beim nächsten Aufruf sofort neu zu rechnen — der Cache
            # wäre dann nicht begrenzt, sondern aus. Bis zum 21.09.2026 warf
            # die Schleife ihn weg und brach erst danach ab; dieser Satz stand
            # darunter und stimmte nicht.
            break
        oldest, _ = _FEATURE_CACHE.popitem(last=False)
        _CACHE_INDICES.pop(oldest, None)
        _FREEFORM_DROPPED.pop(oldest, None)
        _FREEFORM.pop(oldest, None)
        _UNREADABLE_VOIDS.pop(oldest, None)


#: Wie weit eine Ecke des bewegten Netzes von der rechnerisch bewegten Ecke
#: des Quellnetzes liegen darf, damit beide dasselbe Netz sind — in
#: Millimetern. Eine Rechengrenze, keine Geometrietoleranz: ``moved_body``
#: multipliziert dieselben Zahlen mit derselben Matrix, und was dabei
#: auseinanderläuft, sind die letzten Bits einer Summe — an einem Körper von
#: einem Meter rund 1e-10. Die Grenze liegt drei Größenordnungen darüber und
#: sechs unter dem, was irgendeine Erkennung als Unterschied sähe.
MOVED_TWIN_TOLERANCE: Final = 1e-7


def carry_detection(
    source: MeshData,
    moved: MeshData,
    transform: Any,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Die gemerkte Erkennung eines Netzes auf seine starr bewegte Kopie übertragen.

    §21.2 verlangt, dass ein Merkmal nach *Verschieben* oder *Drehen* dasselbe
    bleibt — und bis zum 22.09.2026 wurde das teuer eingelöst: Die Erkennung
    lief am bewegten Netz vollständig neu, und die Zuordnung fand danach heraus,
    dass alles beim Alten war. Gemessen 1,3 s je Verschieben an 204 000
    Dreiecken, 3,9 s an einer Freiform mit 200 000 — für eine Antwort, die
    bis auf die Lage schon dastand.

    Übertragen wird nur unter Beleg, nicht auf Zusage der Operation: Die
    Matrix ist starr (``is_rigid``), das bewegte Netz trägt **dieselben
    Dreiecke** über denselben Eckennummern, und jede Ecke liegt dort, wo die
    Matrix die Ecke des Quellnetzes hinbewegt (:data:`MOVED_TWIN_TOLERANCE`).
    Damit gelten die Dreiecksnummern der gemerkten Merkmale unverändert, und
    ihre Maße folgen der Bewegung über :func:`transformed_features` — dieselbe
    Rechnung, mit der ``moved_object`` die mitgeführten Merkmale nachführt.
    Bleibt dabei ein Merkmal hinter der Bewegung zurück (kein ``exact``), wird
    nichts übertragen, und die Erkennung rechnet wie zuvor.

    Der Rückgabewert sagt, ob ``detect`` das bewegte Netz jetzt aus dem
    Merker beantwortet; die Nebentabellen — weggelassene Rundformen, unlesbare
    Schalen — wandern mit, denn beides sind Eigenschaften der Form, nicht der
    Lage.
    """
    from app.core.geom.transform import is_rigid
    from app.core.perceive.matching import transformed_features

    if check_cancelled is not None:
        check_cancelled()
    source_key = _mesh_key(source)
    known = _FEATURE_CACHE.get(source_key)
    if known is None:
        return False
    matrix = np.asarray(transform, dtype=float)
    if not is_rigid(matrix):
        return False
    source_faces = np.asarray(source.raw.faces)
    moved_faces = np.asarray(moved.raw.faces)
    if source_faces.shape != moved_faces.shape or not np.array_equal(source_faces, moved_faces):
        return False
    source_vertices = np.asarray(source.raw.vertices, dtype=float)
    moved_vertices = np.asarray(moved.raw.vertices, dtype=float)
    if source_vertices.shape != moved_vertices.shape:
        return False
    expected = source_vertices @ matrix[:3, :3].T + matrix[:3, 3]
    if not np.allclose(moved_vertices, expected, rtol=0.0, atol=MOVED_TWIN_TOLERANCE):
        return False
    if check_cancelled is not None:
        check_cancelled()
    moved_key = _mesh_key(moved)
    if moved_key in _FEATURE_CACHE:
        _FEATURE_CACHE.move_to_end(moved_key)
        return True
    carried = transformed_features(known, transform, mesh=moved, check_cancelled=check_cancelled)
    if set(carried.exact) != set(known):
        return False
    _FEATURE_CACHE.move_to_end(source_key)
    _remember(
        moved_key,
        dict(carried.candidates),
        _FREEFORM_DROPPED.get(source_key, 0),
        _UNREADABLE_VOIDS.get(source_key, 0),
        _FREEFORM.get(source_key, False),
    )
    _log.info("carried %d features onto a moved twin", len(known))
    return True


# --- Gewinde ---------------------------------------------------------------------


#: Welche Arten eine Wendel verschluckt, wenn eine gefunden wird.
#:
#: Die sechs eingepassten Grundformen — sie entstehen an der Wendel und
#: bezeichnen dort nichts. ``face`` und ``edge_loop`` stehen bewusst nicht
#: dabei: Gemessen an fünf Größen fand die Erkennung auf dem Gewinde selbst
#: keine einzige Fläche, wohl aber die sechs der Platte darunter, und die
#: gehören dem Kunden.
_SWALLOWED_BY_A_HELIX: Final[frozenset[str]] = frozenset(
    {"hole", "pin", "cone", "sphere", "torus", "fillet"}
)


def without_phantoms_on(
    found: Mapping[FeatureId, Feature], on_the_helix: Sequence[int]
) -> dict[FeatureId, Feature]:
    """Ohne die Einpassungen, die überwiegend auf dieser Wendel liegen.

    Die Regel gilt an beiden Kernen — das Netz misst seine Wendel an den
    Dreiecken, der exakte Körper an seinen Kanten (``brep.thread``), und
    beide sagen mit derselben Dreiecksmenge, was ein Gewinde ist und kein
    Kegel, Zapfen, Kugel, Ring oder Rundung (:data:`_SWALLOWED_BY_A_HELIX`).
    """
    covered = set(on_the_helix)
    kept = dict(found)
    for name, feature in list(kept.items()):
        if feature.kind not in _SWALLOWED_BY_A_HELIX or not feature.face_indices:
            continue
        inside = sum(1 for index in feature.face_indices if index in covered)
        if inside * 2 > len(feature.face_indices):
            del kept[name]
    return kept


def _threads_instead_of_phantoms(
    mesh: MeshData,
    found: dict[FeatureId, Feature],
    *,
    helices: Sequence[Helix] | None = None,
) -> dict[FeatureId, Feature]:
    """Wo eine Wendel liegt, steht ein Gewinde statt einer Handvoll Erfundener.

    Ein eingelesener Bolzen brachte je nach Größe einen Kegel und zwei Zapfen,
    neunzehn Kegel und einen Zapfen oder drei Kegel und zwei Kugeln — alles
    Einpassungen auf die Flanke eines Gewindegangs, die dort örtlich eine
    Kegelfläche ist. Sie verschwinden hier, und an ihrer Stelle steht, was
    wirklich da ist: :mod:`app.core.perceive.helix` misst Achse, Steigung und
    Gangtiefe aus der Geometrie.

    **Ein Gewinde aus einem Baustein ist davon nicht betroffen.** Es steht
    ohnehin in der Szene und läuft nie durch ``detect``; hier entsteht die
    Auskunft für alles, was von außen kommt.
    """
    if helices is None:
        helices = find_helices(mesh)
    if not helices:
        return found

    # Die Dateireihenfolge ihrer Kantenzüge darf keine Merkmalskennung bestimmen.
    # Gleiche Mittelpunkte werden über die gemessenen Gewindemaße aufgelöst.
    helices = sorted(
        helices,
        key=lambda entry: (
            tuple(round(value, 3) for value in entry.centre),
            round(entry.diameter, 3),
            round(entry.pitch, 3),
            round(entry.length, 3),
            entry.internal,
        ),
    )
    kept = dict(found)
    for number, helix in enumerate(helices, start=1):
        kept = without_phantoms_on(kept, helix.face_indices)
        identifier = FeatureId(f"thread_{number}")
        kept[identifier] = Feature(
            id=identifier,
            kind="thread",
            provenance="detected",
            measure_sources={
                "diameter": "fit",
                "pitch": "fit",
                "centre": "fit",
                "axis": "fit",
                "length": "facets",
                "handedness": "fit",
            },
            params={
                "diameter": round(helix.diameter, 4),
                "pitch": round(helix.pitch, 4),
                "centre": helix.centre,
                "axis": helix.axis,
                "internal": helix.internal,
                "length": round(helix.length, 4),
                # Die Händigkeit kennt das Netz seit B1 (P2.5); die Gangzahl
                # kennt es nicht — ein Vielfaches der Steigung konzentriert
                # nicht, und ohne Kanten je Wendel bleibt sie ungemessen.
                "handedness": helix.handedness,
            },
            face_indices=helix.face_indices,
        )
    return kept


# --- Lage zweier Merkmale zueinander ---------------------------------------------


def axis_of(feature: Feature) -> Any | None:
    """Die Achse eines Merkmals als Einheitsvektor, oder nichts."""
    raw = feature.params.get("axis")
    if raw is None:
        return None
    axis = np.asarray(raw, dtype=float)
    length = float(np.linalg.norm(axis))
    if axis.shape != (3,) or length <= EPS_GEOM:
        return None
    return axis / length


def centre_of(feature: Feature) -> Any | None:
    """Die Mitte eines Merkmals, oder nichts."""
    raw = feature.params.get("centre")
    if raw is None:
        return None
    centre = np.asarray(raw, dtype=float)
    return centre if centre.shape == (3,) else None


def sits_at_the_mouth_of(bore: Feature, wider: Feature) -> bool:
    """Ob ``wider`` sich über einer Mündung von ``bore`` aufweitet — die
    Senkung über einer Bohrung.

    **Die eine Antwort auf diese Frage, und sie wohnt hier**, weil hier die
    Schwellen wohnen (:data:`SINK_AXIS_LIMIT`, :data:`SINK_FIT_LIMIT`). Zwei
    Aufrufer stellen sie aus entgegengesetzten Richtungen:
    :func:`app.core.perceive.relations.widening_at_the_mouth` sucht von der
    Bohrung aus die Senkung, :func:`_shapes_on_a_freeform` fragt umgekehrt, ob
    eine Rundform an einer Bohrung hängt und damit keine Erfindung ist. Zwei
    Fassungen derselben fünf Bedingungen wären zwei Antworten auf dieselbe
    Frage — und die eine würde beim nächsten Messwert nachgezogen, die andere
    nicht.

    Fünf Bedingungen, alle an den Merkmalen und keine an der Geometrie:

    * beide sind **Hohlräume** — ein Zapfen um eine Bohrung ist ein Rohr und
      keine Aufweitung ihrer Öffnung (:func:`app.core.types.is_a_cavity`).
      Das war der eine Fehlgriff der ersten Fassung, und zwar an Roberts
      eigenem Halter: Die Bohrung Ø 34 steckt im Zapfen Ø 40,80, beide auf
      derselben Achse, und die Mitte des Zapfens liegt in ihrer Strecke. Er
      umgibt die Bohrung, er mündet nicht in sie,
    * dieselbe Achsrichtung (:data:`SINK_AXIS_LIMIT`),
    * die Mitten auf **einer** Linie und nicht bloß parallel
      (:data:`SINK_FIT_LIMIT`) — zwei Bohrungen nebeneinander haben dieselbe
      Richtung und sind trotzdem zwei,
    * die Mitte der Aufweitung liegt auf der Strecke der Bohrung, denn eine
      Senkung sitzt an einer ihrer Mündungen und nicht drei Zentimeter daneben,
    * und sie ist **weiter** — eine Senkung, die enger wäre als ihre Bohrung,
      gibt es nicht.

    ``False``, wo die Zahlen für die Frage nicht reichen: ein Merkmal ohne
    Achse, ohne Mitte oder ohne Durchmesser.
    """
    if not is_a_cavity(bore) or not is_a_cavity(wider):
        return False
    axis, centre = axis_of(bore), centre_of(bore)
    other_axis, other_centre = axis_of(wider), centre_of(wider)
    if axis is None or centre is None or other_axis is None or other_centre is None:
        return False
    diameter = float(bore.params.get("diameter") or 0.0)
    other_diameter = float(wider.params.get("diameter") or 0.0)
    if diameter <= EPS_GEOM or other_diameter <= diameter:
        return False
    if abs(float(axis @ other_axis)) < units.exact_cos_degrees(SINK_AXIS_LIMIT):
        return False
    across_limit = (diameter / 2.0) * SINK_FIT_LIMIT
    offset = other_centre - centre
    along = float(offset @ axis)
    across = offset - along * axis
    if float(np.linalg.norm(across)) > across_limit:
        return False
    depth = float(bore.params.get("depth") or 0.0)
    # Nur die obere Hälfte: ``abs(along)`` ist nie negativ und ``across_limit``
    # nie kleiner als null, die untere Schranke konnte also nie greifen. Sie
    # stand hier als ``-across_limit <= abs(along) <= …`` und las sich wie eine
    # Bedingung, die etwas prüft.
    return abs(along) <= depth + across_limit


# --- Freiformen ------------------------------------------------------------------


def is_a_freeform(
    found: Mapping[FeatureId, Feature],
    *,
    unpublished_round_shapes: int = 0,
    skin: bool = False,
) -> bool:
    """Ob diese Merkmalsliste von einer Freiform stammt.

    Zuerst die Haut: Liegt über :data:`FREEFORM_SKIN_SHARE` der Oberfläche in
    gekrümmten Flecken ohne Grundform, die nach Krümmung in Splitter zerfallen
    (``skin`` aus :class:`Fitted`), ist der Körper eine Freiform — gleich, wie
    viele Rundformen die Ränder hergaben. Das ist seit RM-193 das Urteil für
    die glatte Haut, deren Splitter nicht mehr eingepasst werden und deshalb
    auch keine Rundformen mehr zählen.

    Dann zwei Zahlen, beide an den gefundenen Flecken gezählt: Wie viele Kugeln
    und Ringe es sind (:data:`FREEFORM_ROUND_COUNT`) und welchen Anteil sie an
    allen Merkmalen haben (:data:`FREEFORM_ROUND_SHARE`). Algebraische Kugel-
    und Toruskandidaten, die für ein bearbeitbares Merkmal zu schlecht bestimmt
    sind, reisen dafür nur als Zahl mit. Die Kegel zählen hier **nicht** mit,
    weil sie auf Konstruiertem häufig und echt sind (Nozzle-Box: 22 Senkungen).
    Diese Zählung trägt weiter die verrauschte Freiform, die schon bei der
    30-Grad-Trennung in Tausende Flecken zerfällt und keine Haut hat.
    """
    if skin:
        return True
    total = len(found) + unpublished_round_shapes
    if not total:
        return False
    round_shapes = unpublished_round_shapes + sum(
        1 for feature in found.values() if feature.kind in ("sphere", "torus")
    )
    return round_shapes >= FREEFORM_ROUND_COUNT and round_shapes / total >= FREEFORM_ROUND_SHARE


def _shapes_on_a_freeform(
    found: dict[FeatureId, Feature],
    *,
    unpublished_round_shapes: int = 0,
    skin: bool = False,
) -> tuple[dict[FeatureId, Feature], int]:
    """Auf einer Freiform bleiben Bohrung, Zapfen, Fläche und Gewinde — die
    Rundformen gehen.

    Der Kiefer-Scan des Kunden zeigte im Objektbaum 162 Kuppeln, 98 Pfannen,
    14 Verjüngungen, 9 Verrundungen und darunter, kaum zu finden, den einen
    Zapfen, den es wirklich gab. Ein Baum mit dreihundert Einträgen, von denen
    dreihundert Tesselierung sind, beantwortet keine Frage; er verdeckt die
    Antwort — dieselbe Überlegung wie bei :func:`_too_small_to_make`, nur eine
    Größenordnung weiter oben (Robert, 03.09.2026: „nur Merkmale, die auch
    von der Größenordnung zum 3D-Drucker passen und sinnvoll sind").

    **Nicht still.** Die Zahl der weggelassenen Formen wird neben dem Ergebnis
    festgehalten (:func:`freeform_dropped`), und die Auswertung macht einen
    Befund daraus — ein Merkmal, das verschwindet, ohne dass ein Satz sagt
    warum, ist schlimmer als eines, das dasteht (Regel 17).

    **Was es kostete, stand hier als offener Preis** — „auf einer Figur mit
    einer echten Senkung geht die Senkung mit […] gemessen ist er noch an
    keinem Modell". Am 10.09.2026 war er gemessen: Roberts
    ``garden-hose-holder.3mf`` ist ein konstruierter Halter mit einem
    organisch geschwungenen Bogen, und der Bogen allein trägt 194 nicht
    veröffentlichte Kugel- und Ringkandidaten. Damit liegt das Teil bei einem
    Rundformanteil von **0,701 gegen die Schwelle 0,700** — ein Tausendstel —,
    und mit den 51 erfundenen Kegeln fielen auch seine vier echten
    90-Grad-Senkungen (Ø 11, halber Winkel 44,998°, Rückstand 7·10⁻⁵). Ohne
    sie fand ``relations.cavity_chain_at`` die Kette Bohrung-Senkung-Bohrung
    an keiner der vier Schraubstellen mehr.

    **Nicht die Schwelle wurde nachgezogen, sondern die Frage geschärft.** Ein
    Zehntel Prozent an einer Zahl zu drehen, die siebzehn Modelle trennt,
    hieße den nächsten Grenzfall mit demselben Fehler zu treffen. Stattdessen
    bleibt, was sich **belegen** lässt: eine Rundform, die an der Mündung
    einer Bohrung sitzt, die selbst bleibt (:func:`sits_at_the_mouth_of`).
    Eine Freiform hat dort keine Bohrung, an der eine Erfindung hängen könnte.

    **Zwei Messungen, und sie sagen Verschiedenes** — die zweite stand hier
    zuerst als Beleg für die erste, und das war sie nicht:

    * *Diese Funktion* rettet am Halter genau **4 von 55** Kegeln; an jeder
      Figur des Korpus null, weil dort keine Bohrung steht, an der etwas
      hängen könnte.
    * *Die Bedingung* :func:`sits_at_the_mouth_of` trifft daneben an
      ``plate_countersunk.stl``, ``plate_countersunk_blind.stl`` und
      ``plate_chamfer_and_taper.stl`` je die echte Senkung und nicht die
      Verjüngung. Diese drei sind **keine Freiformen** (``freeform_dropped``
      ist dort null) und kommen an dieser Zeile nie an; sie belegen die
      Bedingung, nicht den Filter.

    Was ohne diesen Beleg bleibt, geht weiter: die 51 Kegel des Bogens, sechs
    Verrundungen und ein Ring.
    """
    if not is_a_freeform(found, unpublished_round_shapes=unpublished_round_shapes, skin=skin):
        return found, 0
    bores = [
        feature
        for feature in found.values()
        if feature.kind not in _SHAPES_ON_A_FREEFORM and is_a_cavity(feature)
    ]
    kept = {
        name: feature
        for name, feature in found.items()
        if feature.kind not in _SHAPES_ON_A_FREEFORM
        or any(sits_at_the_mouth_of(bore, feature) for bore in bores)
    }
    return kept, len(found) - len(kept) + unpublished_round_shapes


def freeform_dropped(mesh: MeshData) -> int:
    """Wie viele Rundformen :func:`detect` an diesem Netz als Freiform wegließ.

    Null für jedes Modell, das keine Freiform ist — und null für ein Netz, das
    ``detect`` noch nicht gesehen hat oder dessen Eintrag der Cache schon
    verdrängt hat. Die Auswertung fragt unmittelbar nach ``detect`` und trifft
    damit immer den frischen Eintrag.
    """
    return _FREEFORM_DROPPED.get(_mesh_key(mesh), 0)


def recognised_as_freeform(mesh: MeshData) -> bool:
    """Ob :func:`detect` dieses Netz als Freiform eingestuft hat.

    ``False`` für jedes konstruierte Teil — und für ein Netz, das ``detect``
    noch nicht gesehen hat. Die Auswertung fragt unmittelbar nach ``detect``
    und macht zusammen mit :func:`freeform_dropped` einen Befund daraus: Eine
    Haut ohne eingepasste Splitter hat nichts weggelassen und ist trotzdem
    eine Freiform, auf der keine Rundformen geführt werden.
    """
    return _FREEFORM.get(_mesh_key(mesh), False)


def unreadable_void_shells(mesh: MeshData) -> int:
    """Wie viele Schalen der Körper hat, wenn :func:`detect` seine Einschlüsse nicht lesen konnte.

    Null für jedes Modell, dessen Schalenpaare die native Differenz lesen
    konnte — und null für ein Netz, das ``detect`` noch nicht gesehen hat.
    Die Auswertung fragt unmittelbar nach ``detect`` wie bei
    :func:`freeform_dropped` und macht daraus einen Befund: Ein Einschluss,
    der fehlt, weil ein Schalenpaar nicht lesbar war, verschwindet sonst still.
    """
    return _UNREADABLE_VOIDS.get(_mesh_key(mesh), 0)


# --- Bohrungen -------------------------------------------------------------------


#: Eine eingepasste Zylinderfläche mit den Dreiecken, auf denen sie sitzt.
Cylinders = list[tuple["CylinderFit", list[int]]]

#: Dasselbe für die Kegel.
Cones = list[tuple["ConeFit", list[int]]]

#: Und für die beiden runden Formen aus der Ausbaustufe (§41).
Spheres = list[tuple["SphereFit", list[int]]]
Tori = list[tuple["TorusFit", list[int]]]


#: Zylinderausschnitte, die keine ganzen Zylinder sind — Verrundungen.
Fillets = list[tuple["CylinderFit", list[int]]]
Stadiums = list[tuple["StadiumFit", list[int]]]


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
    fillets: Fillets
    helices: list[Helix]
    stadiums: Stadiums
    """Mäntel, deren Querschnitt ein Stadion ist — Langlöcher aus einem Stück
    (:class:`StadiumFit`)."""
    freeform_skin: bool = False
    """Ob der Körper eine Haut trägt: in Splitter zerfallende Fläche über
    :data:`FREEFORM_SKIN_SHARE` der Oberfläche, über alle Flecken zusammen.
    Dann ist das Modell eine Freiform (:func:`is_a_freeform`), und seine
    Splitter wurden nicht eingepasst."""


def _cylinders(mesh: MeshData) -> Cylinders:
    """Nur die Zylinder, für jeden, der die übrigen Formen nicht braucht."""
    return _fitted(mesh).cylinders


def _fitted(
    mesh: MeshData,
    *,
    planar: set[int] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> Fitted:
    """Jeder gekrümmte Fleck des Körpers, einmal eingepasst.

    Bohrungen und Stifte sind dieselbe Suche, zweimal gelesen, und die Suche
    ist die teure Hälfte: an einem Körper mit einer Million Dreiecken kosten
    die Facetten und die zusammenhängenden Flecken Sekunden. Sie zweimal zu
    machen verdoppelte die Erkennungszeit für nichts — also passiert sie hier,
    und beide Aufrufer filtern das Ergebnis.
    """
    if check_cancelled is not None:
        check_cancelled()
    body = mesh.raw
    if not len(body.faces):
        return Fitted([], [], [], [], [], [], [])

    # **Der Cache bleibt stehen, solange hier gemessen wird — und das ist
    # dreiviertel der Erkennungszeit.**
    #
    # Jeder Zugriff auf ``body.face_normals`` lässt ``trimesh`` prüfen, ob sich
    # das Netz seit dem letzten Mal geändert hat, und diese Prüfung hasht das
    # **ganze** Netz (``tobytes`` plus xxhash). Die vier Einpassungen unten
    # lesen die Normalen einmal je Fleck; an einem Segel mit 421 194 Dreiecken
    # und 3362 Flecken waren das 227 036 Hashes und **17,3 von 26,6 Sekunden**
    # (cProfile, 04.09.2026), allein 4832 Aufrufe aus ``fit_sphere``.
    #
    # ``Cache.__enter__`` setzt einen Zähler, und ``verify`` kehrt dann sofort
    # zurück. Gemessen an denselben Dateien:
    #
    #     421 194 Dreiecke:    24,08 s ohne,   6,38 s mit Sperre
    #     1 223 836 Dreiecke: 562,72 s ohne, 153,20 s mit Sperre
    #
    # Beide Male dasselbe Ergebnis, Merkmal für Merkmal verglichen — 73 Prozent
    # über den Faktor drei in der Modellgröße hinweg konstant.
    #
    # **Sicher ist es, weil hier niemand schreiben kann.** ``_one_body`` gibt
    # bei Bedarf ein *neues* ``MeshData`` zurück und lässt das übergebene in
    # Ruhe; im gesperrten Abschnitt lesen die vier ``fit_*`` nur
    # ``face_normals``, ``faces`` und ``vertices``. Der Cache darf nicht
    # verifizieren, weil sich nichts ändert — nicht, weil wir es ihm verbieten.
    #
    # ``_cache`` trägt einen Unterstrich: Wir hängen uns an ``trimesh``-Interna.
    # ``Cache.__enter__``/``__exit__`` sind genau dafür da, aber wer die Version
    # in ``constraints.txt`` hebt (heute ``trimesh==5.0.0``), sieht dort nach.
    with body._cache:
        # Eine Bohrungswand besteht aus vielen schmalen ebenen Segmenten — „gehört zu
        # einer Facette" ist also nicht die Trennlinie, „gehört zu einer *großen*
        # Facette" schon.
        if planar is None:
            planar = _large_facet_faces(body, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        curved = _all_but(len(body.faces), planar)
        if not curved:
            return Fitted([], [], [], [], [], [], [])

        found: Cylinders = []
        cones: Cones = []
        spheres: Spheres = []
        tori = _TorusCandidates(len(body.faces))
        stadiums: Stadiums = []
        areas = np.asarray(body.area_faces, dtype=float)
        total_area = float(areas.sum())
        freeform_skin = False
        #: Kennzahlen von Flecken, an denen der Kegel nichts hergab. Wer
        #: deckungsgleich zu einem davon ist, bekommt dieselbe leere Antwort,
        #: ohne dass der Löser noch einmal hundert Auswertungen dafür braucht
        #: (:func:`_rigid_key`).
        no_cone_here: set[tuple[Any, ...]] = set()

        def classify(patch: list[int]) -> bool:
            """Die erste Form, die auf diesen Fleck passt — oder keine."""
            if check_cancelled is not None:
                check_cancelled()
            if len(patch) < MIN_PATCH_FACES:
                return False
            ball: SphereFit | None = None
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
            #
            # **Ein Muster fragt dieselbe Frage hundertfach.** Die Streben eines
            # Gitters sind deckungsgleich, und ein Kegelwinkel ändert sich unter
            # einer starren Bewegung nicht: Wo der Kegel schon an einem
            # deckungsgleichen Fleck nichts hergab, gibt er auch hier nichts her.
            # Geteilt wird nur dieses Nein — ein gefundener Kegel wird weiterhin
            # einzeln gerechnet, denn seine Achse und seine Spitze liegen woanders.
            # An der Kumiko-Schale sind 1 325 der 1 990 Kegelfits Wiederholungen
            # und kosten 7,71 der 21,66 Sekunden (22.09.2026).
            shape = _rigid_key(body, patch)
            if shape is not None and shape in no_cone_here:
                cone = None
            else:
                cone = fit_cone(body, patch, check_cancelled=check_cancelled)
                if cone is None and shape is not None:
                    no_cone_here.add(shape)
            if check_cancelled is not None:
                check_cancelled()
            if cone is not None and cone.half_angle >= CONE_MIN_ANGLE:
                if cone.good and _cone_is_recognisable(
                    body, cone, patch, check_cancelled=check_cancelled
                ):
                    ball = fit_sphere(body, patch, check_cancelled=check_cancelled)
                    if check_cancelled is not None:
                        check_cancelled()
                    if not _a_ball_fits_far_better(cone, ball):
                        cones.append((cone, patch))
                        return True
                # Ein Kegelwinkel schließt den Zylinder aus — das sagen die
                # Normalen, und daran ändert ein schlechter Rückstand nichts. Die
                # runden Formen sind damit aber nicht ausgeschlossen: Eine Kalotte
                # hat einen Kegelwinkel, ohne ein Kegel zu sein.
            else:
                fit = fit_cylinder(body, patch, check_cancelled=check_cancelled)
                if check_cancelled is not None:
                    check_cancelled()
                if fit is not None and fit.good and _fits_in_the_body(mesh, fit):
                    found.append((fit, patch))
                    return True

            # **Erst hier, und das ist die halbe Antwort auf §41.** Kugel und Torus
            # werden gefragt, nachdem Zylinder und Kegel abgelehnt haben — nicht
            # daneben. Eine Senkung passt auf eine Kugel besser, als man denkt
            # (Rückstand 0,054), und ein `hole_1`, das plötzlich `sphere_1` hieße,
            # wäre für jede Bohrungs-Operation unsichtbar. Die andere Hälfte der
            # Antwort ist ``ROUND_TOLERANCE``.
            if ball is None:
                ball = fit_sphere(body, patch, check_cancelled=check_cancelled)
            if check_cancelled is not None:
                check_cancelled()
            if ball is not None and ball.good:
                spheres.append((ball, patch))
                if _sphere_is_recognisable(body, ball, patch, check_cancelled=check_cancelled):
                    return True
            ring = fit_torus(body, patch, check_cancelled=check_cancelled)
            if check_cancelled is not None:
                check_cancelled()
            if ring is not None and ring.good:
                tori.append((ring, patch))
                # Ein algebraisch passender Ring ist erst mit passenden Normalen
                # ein Treffer. Sonst muss die Nachtrennung seine Zylinderwand
                # noch finden können. Der Kandidat bleibt für die Freiformauskunft.
                return _torus_is_recognisable(body, ring, patch, check_cancelled=check_cancelled)
            # Ein nur algebraisch passender, örtlich unbestimmter Kandidat
            # bleibt Diagnose. Er darf die Suche nach belegten Teilflächen
            # (etwa einer Bohrung mit Rastnasen) nicht als Treffer beenden.
            return False

        patches = _connected_patches(body, curved)

        def splinters_in(pieces: list[list[int]]) -> int:
            """Wie viele Stücke unter :data:`FREEFORM_PIECE_SHARE` der Oberfläche liegen."""
            return sum(
                1
                for piece in pieces
                if float(areas[piece].sum()) < total_area * FREEFORM_PIECE_SHARE
            )

        # **Erst jeder Fleck als Ganzes.** Was hier eine Form ergibt, ist
        # fertig und zählt für das Urteil unten nicht mehr mit.
        unresolved: list[int] = []
        for patch_index, patch in enumerate(patches):
            if check_cancelled is not None:
                check_cancelled()
            if len(patch) < MIN_PATCH_FACES:
                continue
            if not classify(patch):
                unresolved.append(patch_index)

        # **Dann die Nachtrennung — und mit ihr das Urteil über die Haut**
        # (RM-193, Entscheidung Robert 22.09.2026). Eine Verrundung schließt
        # tangential an, also trennt kein Knick sie ab: Mantel und Kehle einer
        # Säule liegen in einem Fleck, auf den keine Form passt. Nachgetrennt
        # wird deshalb nur, was nichts ergeben hat — wo eine Form erkannt
        # wurde, bleibt es, wie es ist (siehe
        # :func:`_split_patches_by_curvature`).
        #
        # **Und genau diese Flecken zählt auch das Urteil**: Welcher Anteil
        # der Oberfläche liegt in Flecken *ohne Grundform*, die nach Krümmung
        # in :data:`FREEFORM_SPLINTERS` oder mehr Stücke unter
        # :data:`FREEFORM_PIECE_SHARE` zerfallen? Über
        # :data:`FREEFORM_SKIN_SHARE` ist der Körper eine Figur, ein Scan, ein
        # erzeugtes Netz — dann werden von diesen Flecken nur die Stücke von
        # Gewicht eingepasst.
        #
        # **Der Zusatz „ohne Grundform" kostete am 22.09.2026 drei Kugeln.**
        # Eine Bowlingkugel aus `BowlingGame.3mf` ist ein einziger Fleck über
        # 65 024 Dreiecke mit Rückstand 0,0 — und sie zerfällt nach Krümmung
        # in 662 Stücke, 659 davon Splitter. Wer sie mitzählt, erklärt eine
        # perfekte Kugel zur Haut und nimmt sie mit :func:`is_a_freeform` weg.
        # Dasselbe an einer Kugel auf einem Sockel mit 0,02 mm Rauschen: Kugel
        # und Zapfen verschwanden. Ein Donut, ein Kegel, ein Ball — jede
        # Grundform, die ein ganzes Modell ist, zerfällt nach Krümmung wie
        # eine Figur. Nur der Fit trennt sie, also entscheidet er zuerst.
        curvature_splits: list[list[list[int]]] = []
        if unresolved:
            if check_cancelled is not None:
                check_cancelled()
            jumps = _curvature_jumps(body)
            # Nur die Flecken, deren Stücke unten überhaupt gelesen werden
            # (RM-132) — ein Stück ist nie größer als sein Fleck.
            worth_splitting = np.zeros(len(patches), dtype=bool)
            worth_splitting[np.fromiter(unresolved, dtype=np.intp, count=len(unresolved))] = True
            curvature_splits = _split_patches_by_curvature(
                body,
                patches,
                jumps,
                worth_splitting=worth_splitting,
                check_cancelled=check_cancelled,
            )
            freeform_skin = (
                sum(
                    float(areas[patches[index]].sum())
                    for index in unresolved
                    if len(curvature_splits[index]) > 1
                    and splinters_in(curvature_splits[index]) >= FREEFORM_SPLINTERS
                )
                > total_area * FREEFORM_SKIN_SHARE
            )

        # **Zuletzt die Stücke.** Sie kommen nach allen ganzen Flecken und
        # nicht mehr unmittelbar nach ihrem eigenen: Das Urteil über die Haut
        # muss vorher stehen, sonst hinge es daran, welcher Fleck zuerst
        # scheitert.
        for patch_index in unresolved:
            patch = patches[patch_index]
            if check_cancelled is not None:
                check_cancelled()
            pieces = curvature_splits[patch_index]
            split_apart = len(pieces) > 1
            if split_apart and freeform_skin:
                # Die Haut einer Figur wird nicht in ihre Splitter zerlegt und
                # eingepasst: am Drachen 27 554 Stücke aus zwei bis fünfzig
                # Dreiecken mit drei Grad Normalenspreizung, deren Achse kein
                # Löser bestimmen kann — 33 der 37 Sekunden für null Merkmale.
                # Eingepasst wird, was Gewicht hat: der tangential
                # eingeblendete Zapfen, die Verrundung, die Kugelecke (am
                # Drachen 23 Stücke). Was die Haut an Bohrungen und Flächen
                # trägt, liegt an ihren Rändern und ist längst ein eigener
                # Fleck.
                pieces = [
                    piece
                    for piece in pieces
                    if float(areas[piece].sum()) >= total_area * FREEFORM_PIECE_SHARE
                ]
            # Jedes Stück wird gefragt, nicht nur bis zum ersten Treffer — die
            # Liste ist Absicht, kein ``any`` mit Kurzschluss.
            classified = [classify(piece) for piece in pieces] if split_apart else []
            for piece, known in zip(pieces, classified, strict=False):
                if not known:
                    separated = _cylinder_beside_a_torus(
                        body, mesh, piece, tori, check_cancelled=check_cancelled
                    )
                    if separated is not None:
                        found.append(separated)
            if any(classified):
                # Belegte Teilflächen ersetzen die unsichere Gesamtdeutung;
                # dieselben Dreiecke zählen nicht zusätzlich als verworfener Ring.
                tori.drop_patch(patch)
                continue
            # **Dritte Runde, für den Mantel eines knapp aufgezogenen
            # Langlochs** (RM-155): kein Zylinder, weil der Weg zu groß ist,
            # und keine zwei Bögen, weil die Flanken für die Krümmungstrennung
            # zu schmal sind. Als Ganzes ist er trotzdem eine Form — ein
            # Prisma über einem Stadion —, und die wird hier eingepasst. Nach
            # dem Split und nicht davor: Was zwei Bögen ergibt, setzt
            # :mod:`app.core.perceive.slots` zusammen wie bisher.
            stadium = fit_stadium(body, patch)
            if stadium is not None and stadium.good and stadium.inward:
                stadiums.append((stadium, patch))
                tori.drop_patch(patch)

        if check_cancelled is not None:
            check_cancelled()
        found = _merged_cylinders(body, mesh, found, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        cones = _merged_cones(body, cones, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        rings = _merged_tori(body, tori.entries, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        helices = find_helices(mesh, check_cancelled=check_cancelled)
        found = _without_thread_turns(body, found, helices=helices)
        if check_cancelled is not None:
            check_cancelled()
        found, fillets = _split_off_fillets(body, found)
        if check_cancelled is not None:
            check_cancelled()

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
        for round_shapes in (spheres, rings):
            round_shapes.sort(
                key=lambda entry: (
                    round(entry[0].centre[0], 3),
                    round(entry[0].centre[1], 3),
                    round(entry[0].centre[2], 3),
                )
            )
        for entry_list in (fillets,):
            entry_list.sort(
                key=lambda entry: (
                    round(entry[0].centre[0], 3),
                    round(entry[0].centre[1], 3),
                    round(entry[0].centre[2], 3),
                )
            )
        return Fitted(found, cones, spheres, rings, fillets, helices, stadiums, freeform_skin)


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
        if entry[0].inward
        and not _too_small_to_make(entry[0].radius * 2.0)
        and not _a_sliver(mesh.raw, entry[1])
    ]
    through_bounds = _ThroughBounds(body)
    return [
        Feature(
            id=f"hole_{number}",
            kind="hole",
            provenance="detected",
            measure_sources={"diameter": "fit", "axis": "fit", "centre": "fit", "depth": "facets"},
            params={
                "diameter": fit.radius * 2.0,
                "axis": fit.axis,
                "centre": fit.centre,
                "depth": _patch_extent(body, patch, fit.axis),
                "through": _is_through(mesh, fit, cones, patch, bounds=through_bounds),
                "residual": fit.residual,
                **_cylinder_measures(fit),
            },
            face_indices=tuple(patch),
            surface_patches=(_cylinder_surface(fit, patch),),
        )
        for number, (fit, patch) in enumerate(found, start=1)
    ]


def _cylinder_surface(fit: CylinderFit, patch: Sequence[int]) -> SurfacePatch:
    """Der akzeptierte Zylinder bleibt derselbe, unabhängig vom semantischen Namen."""
    return SurfacePatch(
        "cylinder",
        {"centre": fit.centre, "axis": fit.axis, "radius": fit.radius},
        tuple(int(index) for index in patch),
        "fit",
    )


def _fits_in_the_body(mesh: MeshData, fit: CylinderFit) -> bool:
    """Passt dieser Zylinder überhaupt in den Körper, der ihn tragen soll?

    Kein Grenzwert, ein Widerspruch: Eine Bohrung oder ein Zapfen von Ø 631 mm
    kann nicht auf einem Teil sitzen, das quer zu seiner Achse 231 mm misst.
    Gemessen wird darum **quer zur eigenen Achse** und nicht an der dünnsten
    Kante — ein Loch Ø 7,1 durch eine 6,4 mm dünne Scheibe ist normal, dort
    liegt die dünne Richtung ja in der Achse. Diese Unterscheidung ist der
    ganze Punkt: nach der dünnsten Kante gemessen fielen 92 von 165 Bohrungen
    durch, davon die meisten zu Recht vorhanden.

    **„Quer zur Achse" heißt dabei die weitere der beiden übrigen Richtungen,
    nicht die engere.** Ein Hüllquader ist nicht der Körper: Ein L-Profil ist
    in einer Richtung 160 mm breit und trägt trotzdem nirgends ein Loch dieser
    Größe. Die Schranke ist deshalb bewusst die lässigere von beiden — sie
    fängt den Widerspruch (breiter als das ganze Teil) und maßt sich kein
    Urteil darüber an, wo im Teil das Merkmal sitzt.

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
    if fit.radial_min is not None:
        # Das Umkreismaß kann breiter sein als seine facettierte Außenhaut.
        # Der Größenfilter vergleicht deshalb das wirkliche radiale Band
        # mit einer oberen Schranke der Körperausdehnung quer zur Fitachse.
        # Die projizierte Boxdiagonale schließt auch gedrehte Halbmäntel ein;
        # einzelne Weltachsenbreiten können deren Durchmesser unterschätzen.
        first, second = _plane_basis(np.asarray(fit.axis, dtype=float))
        across = math.hypot(
            float(np.asarray(size) @ np.abs(first)), float(np.asarray(size) @ np.abs(second))
        )
        return fit.radial_min * 2.0 <= across + EPS_GEOM
    along = int(np.argmax(axis))
    across = max(size[index] for index in range(3) if index != along)
    return fit.radius * 2.0 <= across + EPS_GEOM


#: Ein Dreieck, das mehr Ringkandidaten trägt, als die Karte Plätze hat.
_CROWDED: Final = -2


class _TorusCandidates:
    """Die Ringkandidaten von :func:`_fitted` samt Karte Dreieck → Kandidat.

    :func:`_cylinder_beside_a_torus` fragte je Splitstück **jeden** Kandidaten,
    ob das Stück an ihn grenzt — am Drachen aus TripoSG 27 168 Stücke mal alle
    Ringe, 18 der 72 Sekunden eines Profils (gemessen am 21.09.2026), und die
    Antwort war fast immer nein. Die Karte nennt je Dreieck den Kandidaten,
    der es trägt; ein Stück fragt seine eigenen Dreiecke und deren Nachbarn
    und bekommt die Handvoll Ringe, die überhaupt in Frage kommen.

    **Ein Dreieck kann zwei Kandidaten tragen**: der ursprüngliche Fleck, der
    als Ring passte, aber nicht belegt war, und ein Splitstück daraus, das
    ebenfalls als Ring passte — oder ein Stück und die Vereinigung, die
    :func:`_cylinder_beside_a_torus` an seine Stelle setzt. Dafür hat die
    Karte zwei Plätze; ein dritter Kandidat macht das Dreieck ``_CROWDED``,
    und wer ein solches trifft, fragt wie früher alle. Die Karte ist eine
    Vorauswahl: Ob ein Stück wirklich angrenzt, prüft der Aufrufer weiter
    an den Dreiecken selbst.
    """

    __slots__ = ("_next", "entries", "first", "second", "serials")

    def __init__(self, count: int) -> None:
        self.entries: Tori = []
        self.serials: list[int] = []
        self.first = np.full(count, -1, dtype=np.int64)
        self.second = np.full(count, -1, dtype=np.int64)
        self._next = 0

    def __len__(self) -> int:
        return len(self.entries)

    def _mark(self, serial: int, faces: Sequence[int]) -> None:
        indices = np.asarray(faces, dtype=np.int64)
        free = self.first[indices] == -1
        self.first[indices[free]] = serial
        taken = indices[~free]
        free = self.second[taken] == -1
        self.second[taken[free]] = serial
        self.second[taken[~free]] = _CROWDED

    def _unmark(self, serial: int, faces: Sequence[int]) -> None:
        indices = np.asarray(faces, dtype=np.int64)
        self.first[indices[self.first[indices] == serial]] = -1
        self.second[indices[self.second[indices] == serial]] = -1

    def append(self, entry: tuple[TorusFit, list[int]]) -> None:
        serial = self._next
        self._next += 1
        self.entries.append(entry)
        self.serials.append(serial)
        self._mark(serial, entry[1])

    def replace(self, index: int, entry: tuple[TorusFit, list[int]]) -> None:
        """Ein Kandidat wächst: dieselbe Nummer, mehr Dreiecke."""
        self._unmark(self.serials[index], self.entries[index][1])
        self.entries[index] = entry
        self._mark(self.serials[index], entry[1])

    def drop_patch(self, patch: list[int]) -> None:
        """Belegte Teilflächen ersetzen die unsichere Gesamtdeutung des Flecks."""
        kept: Tori = []
        serials: list[int] = []
        for entry, serial in zip(self.entries, self.serials, strict=True):
            if entry[1] is patch:
                self._unmark(serial, entry[1])
            else:
                kept.append(entry)
                serials.append(serial)
        self.entries = kept
        self.serials = serials

    def positions_beside(self, faces: np.ndarray) -> list[int] | None:
        """Die Kandidaten, die eines dieser Dreiecke tragen — ``None`` heißt: alle fragen."""
        marks = np.concatenate((self.first[faces], self.second[faces]))
        marks = np.unique(marks[marks != -1])
        if len(marks) and marks[0] == _CROWDED:
            return None
        wanted = set(marks.tolist())
        return [index for index, serial in enumerate(self.serials) if serial in wanted]


def _cylinder_beside_a_torus(
    body: trimesh.Trimesh,
    mesh: MeshData,
    patch: list[int],
    tori: _TorusCandidates,
    *,
    check_cancelled: Callable[[], None] | None,
) -> tuple[CylinderFit, list[int]] | None:
    """Trennt eine Zylinderwand von der letzten Facette einer belegten Rundung.

    Der Krümmungssplit kann eine tangentiale Torusfacette am Zylinder lassen.
    Sie darf weder dessen Kreismaß verändern noch unbemerkt verloren gehen.
    Die bestehende Torusachse schlägt eine Teilung vor; beide vollständigen
    Teilflächen müssen danach ihre gewöhnlichen Formprüfungen bestehen.
    """
    if not len(tori):
        return None
    indices = np.asarray(patch, dtype=np.int64)
    normals = np.asarray(body.face_normals)[indices]
    # Die Nachbarn der Restdreiecke aus dem Index je Dreieck, nicht aus
    # einem ``np.isin`` über alle Nähte des Netzes je Ring: 3 778 Aufrufe an
    # der verrauschten Freiform kosteten so 0,27 s (gemessen am 21.09.2026).
    neighbour_table, _rows = _neighbour_index(body)
    # Nur die Ringe, die das Stück oder seine Nachbarn tragen — in der
    # Reihenfolge der Kandidaten, damit der erste Treffer derselbe bleibt.
    around = neighbour_table[indices]
    around = np.concatenate((indices, around[around >= 0]))
    positions = tori.positions_beside(around)
    if positions is None:
        positions = list(range(len(tori)))
    for index in positions:
        ring, ring_patch = tori.entries[index]
        if check_cancelled is not None:
            check_cancelled()
        perpendicular = np.abs(normals @ np.asarray(ring.axis)) <= ACROSS_THE_AXIS
        if perpendicular.all() or not perpendicular.any():
            continue
        candidate = indices[perpendicular].tolist()
        rest = indices[~perpendicular]
        if len(candidate) < MIN_PATCH_FACES or len(_connected_patches(body, candidate)) != 1:
            continue
        beside = neighbour_table[rest]
        beside = beside[beside >= 0]
        if not np.isin(rest, ring_patch).any() and not np.isin(beside, ring_patch).any():
            continue
        rest = rest.tolist()
        cylinder = fit_cylinder(body, candidate, check_cancelled=check_cancelled)
        if cylinder is None or not cylinder.good or not _fits_in_the_body(mesh, cylinder):
            continue
        joined = sorted({*ring_patch, *rest})
        again = fit_torus(body, joined, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        if (
            again is not None
            and again.good
            and _same_torus((ring, ring_patch), (again, joined))
            and _torus_is_recognisable(body, again, joined, check_cancelled=check_cancelled)
        ):
            tori.replace(index, (again, joined))
            return cylinder, candidate
    return None


def _merged_cylinders(
    body: trimesh.Trimesh,
    mesh: MeshData,
    found: Cylinders,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> Cylinders:
    """Zylinderflecken, die **dieselbe Fläche** beschreiben, zu einem machen.

    **Der Fall ist die gefaste Bohrung, und sie ist der Standardfall.** Jede
    Schraubenbohrung eines Druckteils bekommt eine Fase; die Vereinigung von
    Bohrer und Fasenkegel legt zusätzliche Punkte auf die Bohrungswand, und die
    Boolesche Operation trianguliert sie darunter mit Knicken von siebzig bis
    neunzig Grad. Die Fleckenbildung trennt dort zu Recht — nur zerfällt die
    Wand damit in vier Stücke, und heraus kamen **vier Bohrungen für ein
    Loch**, zwei davon mit ``through=True`` und zwei mit ``through=False``.

    Für den Nutzer ist das schlimmer als eine fehlende Bohrung: Vier Merkmale
    an derselben Stelle sind für die Zuordnung vier gleich gute Kandidaten,
    also hält die Auswertung an und fragt — bei **jeder** Auswertung, und mit
    einer Frage, auf die es keine richtige Antwort gibt (§21.3).

    Zusammengefasst wird nur, was ohnehin dasselbe ist: gleicher Radius,
    kollineare Achse, gleiche Richtung der Normalen — und **überlappende**
    Abschnitte auf der Achse. Das Letzte trennt den Fall von seinem Gegenteil,
    den die Sortierung unten schon einmal nennt: zwei koaxiale Bohrungen durch
    zwei Wände sind zwei Bohrungen und bleiben es, denn zwischen ihnen liegt
    eine Lücke.
    """
    if len(found) < 2:
        return found

    merged: Cylinders = []
    # **Die Kandidaten kommen aus vier Spalten, nicht aus einer Schleife.**
    # Jeder neue Fleck fragte bisher jeden schon gemerkten einzeln, ob sie
    # dieselbe Fläche sind — bei einem Noppenfeld mit 1 403 Kuppen sind das
    # 984 906 Aufrufe und 10,9 von 14 Sekunden der Erkennung (22.09.2026).
    # Drei der vier Fragen in :func:`_same_cylinder` stehen in den Fits
    # selbst — Seite, Radius, Achsrichtung und Kollinearität —, und die
    # lassen sich für alle Gemerkten auf einmal beantworten. Gefragt wird
    # danach nur, wer sie besteht; die Antwort ist dieselbe, nur die
    # Reihenfolge der Fragen ist eine andere.
    axes = np.zeros((len(found), 3))
    centres = np.zeros((len(found), 3))
    radii = np.zeros(len(found))
    inward = np.zeros(len(found), dtype=bool)
    axis_cosine = math.cos(math.radians(SINK_AXIS_LIMIT))
    for fit, patch in found:
        if check_cancelled is not None:
            check_cancelled()
        axis = np.asarray(fit.axis, dtype=float)
        centre = np.asarray(fit.centre, dtype=float)
        count = len(merged)
        scale = np.maximum(radii[:count], fit.radius)
        offset = centre - centres[:count]
        across = offset - axes[:count] * (offset * axes[:count]).sum(axis=1)[:, None]
        alike = (
            (inward[:count] == fit.inward)
            & (np.abs(radii[:count] - fit.radius) <= scale * CYLINDER_TOLERANCE)
            & (np.abs(axes[:count] @ axis) >= axis_cosine)
            & (np.linalg.norm(across, axis=1) <= scale * SINK_FIT_LIMIT)
        )
        for index in (int(number) for number in np.flatnonzero(alike)):
            other, gathered = merged[index]
            if not _same_cylinder(body, (fit, patch), (other, gathered)):
                continue
            together = gathered + patch
            again = fit_cylinder(body, together, check_cancelled=check_cancelled)
            # **Die Vereinigung muss sich selbst rechtfertigen.** Dass zwei
            # Flecken zueinander passen, heißt nicht, dass ihre Summe eine
            # Fläche ist: An einem hohlen Quader stehen die verrundeten
            # Innenkanten oben und unten koaxial und gleich groß, und
            # zusammengefasst kam ein Zylinder heraus, den es nicht gibt —
            # samt zwei weiteren Fehlbefunden daneben. Der neue Fit darf
            # deshalb **nicht schlechter streuen** als der schlechtere der
            # beiden, aus denen er entsteht.
            #
            # **Oder der neue Fleck liegt nachweislich auf dem Zylinder, der
            # schon da ist.** Die Regel darüber ist für die Frage gebaut, ob
            # zwei Flecken überhaupt dieselbe Fläche sind; sie sieht nicht,
            # dass ein Fit über mehr Punkte immer ein wenig mehr streut. An
            # einem Uhrenteil (``REMONTOIRE ESCAPEMENT-12``, 15.09.2026) kam
            # eine Bohrung Ø 30 nach dem Ändern einer **anderen** Bohrung in
            # vier Bögen zurück: drei fanden zusammen (226°), der vierte lag
            # mit 0,003 mm auf demselben Kreis, hob die Streuung aber von
            # 0,00076 auf 0,00114 — damals noch in Facettenbreiten gemessen,
            # heute in Sehnenhöhen — und blieb draußen. Im Baum
            # standen zwei Hohlkehlen R 15 statt einer Bohrung, und die
            # Kennung ``hole_5`` ging verloren. Liegt der Fleck innerhalb des
            # Fitvertrags (:data:`CYLINDER_SPREAD`) auf der vorhandenen
            # Wand, beschreibt er sie — dann trägt die Streuung des
            # gemeinsamen Fits nichts mehr zur Frage bei.
            if (
                again is not None
                and again.good
                and _fits_in_the_body(mesh, again)
                and (
                    again.spread <= max(fit.spread, other.spread) + EPS_GEOM
                    or _lies_on_the_cylinder(body, other, patch, check_cancelled=check_cancelled)
                )
            ):
                merged[index] = (again, together)
                # Die Spalten beschreiben, was gemerkt ist: Nach dem
                # Zusammenfassen steht dort der gemeinsame Fit. Gemessen ist
                # das nie entscheidend gewesen — unter den Toleranzen von
                # `_same_cylinder` wandert ein Fit über derselben Wand kaum,
                # und eine Probe ohne diese vier Zeilen fiel an keinem der
                # 23 Korpusmodelle und keinem Test auf. Eine Spalte, die
                # einen verworfenen Fit beschreibt, wäre trotzdem eine
                # zweite Wahrheit.
                axes[index] = np.asarray(again.axis, dtype=float)
                centres[index] = np.asarray(again.centre, dtype=float)
                radii[index] = again.radius
                inward[index] = again.inward
                break
        else:
            axes[len(merged)] = axis
            centres[len(merged)] = centre
            radii[len(merged)] = fit.radius
            inward[len(merged)] = fit.inward
            merged.append((fit, patch))
    return merged


def _lies_on_the_cylinder(
    body: trimesh.Trimesh,
    fit: CylinderFit,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Ob dieselben geprüften Konturecken auf dem vorhandenen Zylinder liegen.

    Gemessen wie :attr:`CylinderFit.spread`: der mittlere Abstand vom
    Zylinder, bezogen auf die Sehnenhöhe der Polygonnäherung dieses Flecks —
    und mit derselben Grenze (:data:`CYLINDER_SPREAD`). Eine Wand, die den
    Vertrag des Fits erfüllt, ohne dass er für sie gerechnet wurde, ist
    dieselbe Wand.
    """
    axis = np.asarray(fit.axis, dtype=float)
    points = np.asarray(body.vertices)[np.unique(np.asarray(body.faces)[patch])]
    relative = points - np.asarray(fit.centre, dtype=float)
    first, second = _plane_basis(axis)
    tolerance = max(weld_tolerance(float(np.linalg.norm(body.extents))), ROUND_WALL_TOLERANCE)
    outline = _cylinder_contour(
        np.column_stack((relative @ first, relative @ second)), tolerance, check_cancelled
    )
    if outline is None:
        return False
    errors = np.abs(np.linalg.norm(outline, axis=1) - fit.radius)
    sag = max(_chord_sag(body, patch, axis), ROUND_WALL_TOLERANCE)
    return float(errors.max()) <= tolerance and float(errors.mean() / sag) <= CYLINDER_SPREAD


def _split_off_fillets(body: trimesh.Trimesh, found: Cylinders) -> tuple[Cylinders, Fillets]:
    """Zylinder von Zylinder**ausschnitten** trennen — Zapfen von Verrundungen.

    **Eine verrundete Kante ist heute ein Zapfen**, und der Kunde liest an dem,
    was er als „Verrundung R 3" kennt, ein „Zapfen Ø 6". §14 nennt einen
    Zapfen das, womit man eine Bohrung paart; mit einer Kantenverrundung paart
    niemand etwas, und ``applies_to`` bot ihm trotzdem Passungs-Operationen an.

    Getrennt wird an der **Überdeckung um die Achse**, und die Zahlen lassen
    keinen Zweifel: Über den ganzen Korpus überdecken Bohrungen und Zapfen 345
    bis 356 Grad, eine verrundete Quaderkante 90. Das ist keine Schwelle, die
    kalibriert werden muss, sondern ein Loch, durch das nichts fällt.

    **Nur die gerade Kante.** An einer runden ist die Verrundung ein
    Torusstück, und ``tube_radius`` ist dort bereits ihr Radius — aber ein
    Kehlstück ist von einem vollen Ring über diese Zahl nicht zu trennen, und
    eine Schwelle, die sich nicht messen lässt, gehört nicht gebaut.
    """
    whole: Cylinders = []
    fillets: Fillets = []
    for fit, patch in found:
        if angular_span(body, fit, patch) < FULL_TURN_SPAN:
            fillets.append((fit, patch))
        else:
            whole.append((fit, patch))
    return whole, fillets


def _without_thread_turns(
    body: trimesh.Trimesh,
    found: Cylinders,
    *,
    helices: Sequence[Helix] = (),
) -> Cylinders:
    """Gewindegänge sind keine Zapfen, und sie treten in Rudeln auf.

    **Ein M6-Gewinde meldete acht.** Jede Windung ist für sich ein
    Zylinderstück, koaxial zu den anderen, gleich dick und einen Millimeter
    darüber — die Steigung. Erkannt wurden sie als acht Zapfen, die es nicht
    gibt: §14 nennt einen Zapfen das, womit man eine Bohrung paart, und mit
    einem Gewindegang paart niemand etwas. Schlimmer als die Anzeige ist die
    Zuordnung, für die acht koaxiale gleich große Merkmale acht gleich gute
    Kandidaten sind.

    **Das Gewinde selbst geht dabei nicht verloren.** Es entsteht in einem
    Baustein und trägt seinen Namen von dort (§21.1: „Ein Gewinde sieht sie
    nicht"); als erzeugtes Merkmal steht es unabhängig von dieser Erkennung in
    der Szene. Verworfen wird nur, was die Erkennung fälschlich **daneben**
    stellt.

    Drei sind die Grenze, und sie ist gemessen: Über den ganzen Korpus gibt es
    genau einen Fall mit **zwei** koaxialen Zylindern gleichen Durchmessers —
    die gespiegelten Gliedmaßen der Figur —, und keinen mit dreien. Ein
    Gewinde bringt acht mit.

    **Die Zahl allein reichte nicht, und das kostete jede mehrfache
    Durchführung.** Der Stapel entstand aus paralleler Achse, kleinem
    Querversatz und gleichem Radius — ohne eine Bedingung entlang der Achse.
    Drei Lappen übereinander mit einer durchgehenden Bohrung Ø 6 erfüllen alle
    drei, und ab dem dritten galten sie als Gewindegänge: gemessen eine
    Bohrung bei einer Wand, zwei bei zweien, **null** bei dreien und null bei
    vieren. Ein Scharnier, ein Gelenk, eine Kabeldurchführung — alle drei
    verloren ihre Bohrungen still.

    Ein Gewinde ist ein **fortschreitender Lauf**, und darin liegt der
    Unterschied: Seine Gänge berühren oder überlappen sich auf der Achse und
    jeder weitere Gang verlängert den Lauf. Ineinander liegende Restflecken
    derselben Zylinderwand tun das nicht. Beim Verkleinern einer Bohrung im
    Gartenhalter lagen zwölf solche Flecken zusammen mit dem neuen Mantel vor;
    der Filter entfernte damit die richtig erkannte Bohrung.

    Gemessen an ``printed_thread`` über sechs Größen, beide Richtungen und
    drei Längen ist die größte Lücke innerhalb eines Gangstapels **0,0000 mm**
    — die Windungen laufen ineinander, weil die Helix stetig steigt. Drei
    Wände dagegen haben Lücken von Millimetern (0…6, 10…16, 20…26). Für den
    Zusammenhang gilt deshalb ``EPS_GEOM``. Ob ein Abschnitt die Spanne
    wirklich verlängert, wird gegen die Schweißtoleranz des Netzes geprüft;
    kleinere Abweichungen bezeichnen denselben Endring.

    Eine geometrisch erkannte Wendel belegt ihre Fitflecken unabhängig von
    deren Anzahl. Die Vereinigung kann ihre Gänge auf einen oder zwei Fits
    zusammenführen; der Flächenbeleg bleibt derselbe. Ohne Wendelbeleg gilt
    weiterhin ausschließlich der fortschreitende Lauf aus mindestens drei
    Abschnitten. Verschachtelte Reste einer Bohrungswand reichen nicht.
    """
    for helix in helices:
        faces = set(helix.face_indices)
        found = [
            entry for entry in found if sum(face in faces for face in entry[1]) * 2 <= len(entry[1])
        ]
    if len(found) < THREAD_TURNS:
        return found

    advance_tolerance = weld_tolerance(float(np.linalg.norm(body.extents)))
    axes = np.asarray([fit.axis for fit, _patch in found], dtype=float)
    centres = np.asarray([fit.centre for fit, _patch in found], dtype=float)
    radii = np.asarray([fit.radius for fit, _patch in found], dtype=float)
    parallel_limit = units.exact_cos_degrees(SINK_AXIS_LIMIT)
    used: set[int] = set()
    for index, (fit, _patch) in enumerate(found):
        if index in used:
            continue
        axis = axes[index]
        offset = centres - centres[index]
        across = offset - (offset @ axis)[:, None] * axis
        # Dieselben Paarbedingungen in einem begrenzten Feld je Ausgangsfit.
        # Kein quadratisches Feld und keine wiederholten Arrays je Taschenbogenpaar.
        coaxial = np.flatnonzero(
            (np.abs(axes @ axis) >= parallel_limit)
            & (np.linalg.norm(across, axis=1) <= fit.radius * SINK_FIT_LIMIT)
        ).tolist()
        stack = [
            index,
            *(
                other_index
                for other_index in coaxial
                if other_index != index
                and other_index not in used
                and abs(radii[other_index] - fit.radius) <= fit.radius * CYLINDER_TOLERANCE
            ),
        ]

        thread_stack: list[int] = []
        if len(stack) >= THREAD_TURNS and _one_run(
            [_axial_span(body, found[entry][1], fit.axis) for entry in stack],
            advance_tolerance=advance_tolerance,
        ):
            thread_stack = stack
        if len(thread_stack) >= THREAD_TURNS:
            used.update(thread_stack)
            # **Und was zwischen den Windungen liegt, gehört dazu.** Der Kern
            # und der Auslauf eines Gewindes sind koaxial, aber dicker als ein
            # Gang; über den Durchmesser fallen sie nicht in den Stapel. Am
            # M6-Gewinde blieb sonst einer von acht übrig — ein Phantom weniger
            # als vorher und immer noch eins.
            low = min(_axial_span(body, found[entry][1], fit.axis)[0] for entry in thread_stack)
            high = max(_axial_span(body, found[entry][1], fit.axis)[1] for entry in thread_stack)
            for other_index in coaxial:
                if other_index in used:
                    continue
                other_patch = found[other_index][1]
                other_low, other_high = _axial_span(body, other_patch, fit.axis)
                if other_low >= low - EPS_GEOM and other_high <= high + EPS_GEOM:
                    used.add(other_index)
    # ``index not in used`` ist die ganze Antwort: Verworfen wird genau, was in
    # einen Gewindestapel geraten ist. Hier stand zusätzlich ``entry in keep``
    # gegen eine nebenher geführte Liste — ein Fließkommavergleich über die
    # eingepassten Radien (Regel 6), quadratisch in der Zahl der Zylinder, und
    # ohne Wirkung: Jeder Eintrag, der nicht in ``used`` landete, stand
    # ohnehin darin.
    return [entry for index, entry in enumerate(found) if index not in used]


def _one_run(
    spans: list[tuple[float, float]],
    *,
    advance_tolerance: float = EPS_GEOM,
) -> bool:
    """Bilden mindestens drei Abschnitte einen fortschreitenden Achslauf?

    Die Frage, die ein Gewinde von einem Stapel Wände trennt: Die Gänge einer
    Helix gehen ineinander über, zwei Bohrungen durch zwei Wände haben eine
    Lücke dazwischen. Berührung zählt als Zusammenhang — ``EPS_GEOM`` ist die
    Toleranz, mit der :func:`_same_cylinder` dieselbe Frage für ein Paar
    beantwortet. Ein Abschnitt zählt nur, wenn er die bisher erreichte Spanne
    um mehr als die Schweißtoleranz des Netzes verlängert. Damit werden
    verschachtelte Fragmente derselben Wand nicht zu mehreren Gewindegängen.
    """
    ordered = sorted(spans, key=lambda span: (span[0], -span[1]))
    last_start = ordered[0][0]
    reach = ordered[0][1]
    advancing = 1
    for low, high in ordered[1:]:
        if low > reach + EPS_GEOM:
            return False
        if low > last_start + advance_tolerance and high > reach + advance_tolerance:
            last_start = low
            advancing += 1
        reach = max(reach, high)
    return advancing >= THREAD_TURNS


def _same_cylinder(
    body: trimesh.Trimesh,
    one: tuple[CylinderFit, list[int]],
    two: tuple[CylinderFit, list[int]],
) -> bool:
    """Beschreiben diese zwei Flecken dieselbe Zylinderfläche?"""
    first, first_patch = one
    second, second_patch = two
    if first.inward is not second.inward:
        return False
    scale = max(first.radius, second.radius)
    if abs(first.radius - second.radius) > scale * CYLINDER_TOLERANCE:
        return False

    axis = np.asarray(first.axis, dtype=float)
    if abs(float(axis @ np.asarray(second.axis, dtype=float))) < math.cos(
        math.radians(SINK_AXIS_LIMIT)
    ):
        return False
    # Kollinear und nicht bloß parallel: zwei Bohrungen nebeneinander haben
    # dieselbe Achsrichtung und sind trotzdem zwei.
    offset = np.asarray(second.centre, dtype=float) - np.asarray(first.centre, dtype=float)
    across = offset - float(offset @ axis) * axis
    if float(np.linalg.norm(across)) > scale * SINK_FIT_LIMIT:
        return False

    # Und sie müssen sich auf der Achse **überlappen**. Sonst sind es zwei
    # Bohrungen durch zwei Wände, und die bleiben zwei.
    low, high = _axial_span(body, first_patch, first.axis)
    other_low, other_high = _axial_span(body, second_patch, first.axis)
    return not (other_low > high + EPS_GEOM or other_high < low - EPS_GEOM)


def angular_span(body: trimesh.Trimesh, fit: CylinderFit | ConeFit, patch: list[int]) -> float:
    """Wie viel Grad um die Achse ein Fleck wirklich überdeckt.

    **Die Zahl, die eine Verrundung von einem Zapfen trennt.** Ein Zapfen ist
    ein voller Zylinder, eine Kantenverrundung ein Viertel davon — gemessen
    über den Korpus 345 bis 354 Grad gegen 90.

    Gerechnet wird über die **größte Lücke** zwischen zwei benachbarten
    Winkeln: Was übrig bleibt, ist die Überdeckung. Der Mittelwert oder die
    Spanne von kleinstem zu größtem Winkel taugten nicht — beide sind bei einem
    Fleck, der die Nahtstelle bei ±180 Grad überschreitet, bedeutungslos.
    """
    return span_about(
        body, np.asarray(fit.axis, dtype=float), np.asarray(fit.centre, dtype=float), patch
    )


def span_about(
    body: trimesh.Trimesh, axis: np.ndarray, centre: np.ndarray, patch: Sequence[int]
) -> float:
    """Dasselbe wie :func:`angular_span`, an Achse und Mitte statt am Fit —
    für ein fertiges Merkmal, das seinen Fit nicht mehr trägt."""
    basis_u, basis_v = _plane_basis(axis)
    chosen = np.asarray(body.faces)[np.asarray(list(patch), dtype=np.int64)]
    points = np.asarray(body.vertices, dtype=float)[np.unique(chosen)] - centre
    angles = np.sort(np.arctan2(points @ basis_v, points @ basis_u))
    if len(angles) < 3:
        return 0.0
    gaps = np.diff(np.concatenate([angles, [angles[0] + 2.0 * math.pi]]))
    return float(math.degrees(2.0 * math.pi - gaps.max()))


def _a_sliver(body: trimesh.Trimesh, patch: list[int]) -> bool:
    """Ob ein Fleck zu schmal ist, um eine Fläche zu sein.

    **Die Schwester von** :func:`_too_small_to_make`, und aus demselben Grund
    eine eigene Frage: Was für kein Werkzeug groß genug ist, ist kein Merkmal
    — nur misst jene den Durchmesser und diese die Breite. Ein Streifen aus
    sechs Dreiecken über die ganze Länge eines Mastes hat einen stattlichen
    Durchmesser und keine Breite; die alte Schranke ließ ihn deshalb durch.

    Die Begründung der Zahl steht bei :data:`MIN_SURFACE_WIDTH`.
    """
    result: bool = remembered(
        "a_sliver",
        body,
        patch,
        lambda: _a_sliver_read(body, patch),
    )
    return result


def _a_sliver_read(body: trimesh.Trimesh, patch: list[int]) -> bool:
    """Der Rumpf von :func:`_a_sliver` — die Antwort merkt sich die Hülle."""
    if not patch:
        return True
    faces = np.asarray(patch, dtype=int)
    area = float(body.area_faces[faces].sum())
    corners = np.asarray(body.vertices[body.faces[faces].reshape(-1)], dtype=float)
    reach = float(np.linalg.norm(corners.max(axis=0) - corners.min(axis=0)))
    if reach <= EPS_GEOM:
        return True
    return area / reach < MIN_SURFACE_WIDTH


def _too_small_to_make(size: float) -> bool:
    """Ob ein Maß unter der automatischen Erkennungsauflösung liegt.

    **Die gemeinsame Grenze steht in** :data:`MIN_CYLINDER_DIAMETER`. Sie galt für
    Bohrung und Zapfen, seit dem 03.09.2026 auch für die Verrundung — und für
    Kegel, Kugel und Torus fehlte sie weiter. Als eigene Frage, damit die
    nächste Merkmalsart sie nicht wieder übersieht.

    **Der Befund, an Roberts Modellen gemessen (03.09.2026):**
    `garden-hose-holder.3mf` (392 532 Dreiecke) lieferte **1130 Merkmale** —
    497 Kugeln, 421 Tori, 183 Kegel —, und **257 davon trugen ein Maß unter
    0,42 mm**, der kleinste Kegel 0,0074 mm. Ein
    Objektbaum mit tausend Einträgen, von denen ein Viertel Tesselierung ist,
    beantwortet keine Frage; er verdeckt die Antwort.

    Die Erkennung veröffentlicht unter ihrer festen Auflösung keine Rundform;
    sie behauptet damit weder deren Abwesenheit noch deren Undruckbarkeit.
    Ein Profilwechsel verändert diese geometrische Entscheidung nicht.

    **Und sie ist die einzige Stelle, an der verglichen wird.** Als sie entstand,
    bekamen nur die drei neuen Erkenner sie; Bohrung, Zapfen und Verrundung
    prüften weiter von Hand gegen :data:`MIN_CYLINDER_DIAMETER` — dieselbe
    Bedingung, aber unauffindbar für die Frage „wer beantwortet sie nicht?".
    Genau dagegen gibt es die Funktion, und eine halbe Vereinheitlichung ist
    schlechter als keine: Sie sieht vollständig aus.
    `tests/test_features.py::test_every_fitted_kind_asks_the_same_question`
    hält es fest.
    """
    return size < MIN_CYLINDER_DIAMETER


def _a_ball_fits_far_better(cone: ConeFit, ball: SphereFit | None) -> bool:
    """Ob dieser Fleck in Wahrheit eine Kugelfläche ist.

    **Gefragt wird nur, wenn der Kegel schon durchgekommen ist** — die
    Reihenfolge Kegel-vor-Kugel bleibt unangetastet, und ein Fleck, den der
    Kegel ablehnt, erreicht den Kugelzweig ohnehin. Der bereits berechnete Fit
    reist danach in den Kugelzweig weiter; derselbe Fleck wird nicht zweimal
    eingepasst.

    Die Zahlen und der Fall stehen bei :data:`SPHERE_BEATS_CONE`. Kurz: Eine
    Pfanne wurde zur Senkung, sobald das Netz fein genug war, weil der
    Kegelrückstand mit der Feinheit unter die Toleranz rutscht — während der
    Kugelrückstand um zwei bis vier Größenordnungen darunter liegt.
    """
    if cone.residual <= EPS_GEOM:
        # Ein exakter Kegel ist ein Kegel. Ohne diesen Zweig teilte die
        # Rechnung unten durch fast null.
        return False
    if ball is None or not ball.good:
        return False
    return cone.residual >= ball.residual * SPHERE_BEATS_CONE


def detect_spheres(
    mesh: MeshData,
    spheres: Spheres | None = None,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Feature]:
    """Kugelige Flecken (§21.1, Ausbaustufe §41).

    ``recess`` trennt die Pfanne von der Kuppel — dieselbe Unterscheidung, die
    der Kegel zwischen Senkung und aufgesetztem Kegel trifft, und aus demselben
    Grund: In eine Pfanne setzt man etwas hinein, auf eine Kuppel nicht.
    """
    found = _fitted(mesh, check_cancelled=check_cancelled).spheres if spheres is None else spheres
    big = [
        entry
        for entry in _sphere_candidates(mesh, found)
        if _sphere_is_recognisable(mesh.raw, entry[0], entry[1], check_cancelled=check_cancelled)
    ]
    return [
        Feature(
            id=f"sphere_{number}",
            kind="sphere",
            provenance="detected",
            measure_sources={"diameter": "fit", "centre": "fit"},
            params={
                "diameter": fit.radius * 2.0,
                "centre": fit.centre,
                "recess": fit.recess,
                "residual": fit.residual,
                **_round_measures(fit),
            },
            face_indices=tuple(patch),
            surface_patches=(
                SurfacePatch(
                    "sphere",
                    {"centre": fit.centre, "radius": fit.radius},
                    tuple(patch),
                    "fit",
                ),
            ),
        )
        for number, (fit, patch) in enumerate(big, start=1)
    ]


def _sphere_candidates(mesh: MeshData, spheres: Spheres) -> Spheres:
    """Kugelfits mit herstellbarem Maß und ausreichend breiter Oberfläche."""
    # Dieselbe Werkzeugschranke wie bei Bohrung, Zapfen und Verrundung
    # (:data:`MIN_CYLINDER_DIAMETER`) — siehe :func:`_too_small_to_make`.
    return [
        entry
        for entry in spheres
        if not _too_small_to_make(entry[0].radius * 2.0) and not _a_sliver(mesh.raw, entry[1])
    ]


def _sphere_is_recognisable(
    body: trimesh.Trimesh,
    fit: SphereFit,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Bestimmtheit und Punktgüte unabhängig von der Facettenunterteilung prüfen."""
    result: bool = remembered(
        "_sphere_is_recognisable",
        body,
        patch,
        lambda: _sphere_is_recognisable_read(body, fit, patch, check_cancelled=check_cancelled),
        extra=fit,
        check_cancelled=check_cancelled,
    )
    return result


def _sphere_is_recognisable_read(
    body: trimesh.Trimesh,
    fit: SphereFit,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Der Rumpf von :func:`_sphere_is_recognisable` — die Antwort merkt sich die Hülle."""
    support = _surface_support(body, patch, check_cancelled)
    if support is None or not np.any(support.round_corners):
        return False
    weights = support.areas / support.areas.sum()
    normals = support.normals
    centred_normals = (normals - weights @ normals) * np.sqrt(weights)[:, None]
    curvature = np.linalg.svd(centred_normals, compute_uv=False)
    if (
        curvature[0] <= EPS_GEOM
        or curvature[1] < curvature[0] * SPHERE_MIN_CURVATURE_BALANCE
        or curvature[-1] * SPHERE_MAX_CENTRED_CONDITION < 1.0
    ):
        return False
    points = support.points[support.round_corners]
    local = points - points.mean(axis=0)
    local_span = float(2.0 * np.linalg.norm(local, axis=1).max())
    errors = np.abs(np.linalg.norm(points - fit.centre, axis=1) - fit.radius)
    # Ungestützte Sehnenpunkte dürfen nach innen liegen; ein fremder Punkt
    # außerhalb der Kugel wird dadurch nicht unsichtbar.
    outside = float(np.linalg.norm(support.points - fit.centre, axis=1).max()) - fit.radius
    if not (
        local_span > EPS_GEOM
        and float(errors.max()) <= local_span * ROUND_LOCAL_TOLERANCE
        and outside <= fit.radius * ROUND_TOLERANCE
    ):
        return False

    def expected_normals(points: np.ndarray) -> np.ndarray | None:
        """Auch ein schmaler Torusring muss die behaupteten Kugelnormalen tragen."""
        if check_cancelled is not None:
            check_cancelled()
        relative = points - fit.centre
        lengths = np.linalg.norm(relative, axis=1)
        if np.any(lengths <= EPS_GEOM):
            return None
        return np.asarray(relative / lengths[:, None], dtype=float)

    expected = expected_normals(support.centres)
    corner_expected = expected_normals(support.points[support.corners].reshape(-1, 3))
    if expected is None or corner_expected is None:
        return False
    return _surface_normals_are_consistent(
        body,
        patch,
        expected,
        corner_expected.reshape(-1, 3, 3),
        max_error=SURFACE_NORMAL_ERROR,
        max_outlier_share=SURFACE_NORMAL_OUTLIER_SHARE,
    )


def detect_tori(
    mesh: MeshData,
    tori: Tori | None = None,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Feature]:
    """Torusförmige Flecken (§21.1, Ausbaustufe §41).

    Zwei Durchmesser, und der zweite ist der interessante: ``diameter`` ist der
    Ring, ``tube_diameter`` die Röhre — an einer Verrundung um eine runde Kante
    ist die Röhre ihr Maß. Ein ausreichend bestimmtes Torus**stück** reicht;
    vor der Veröffentlichung müssen neben dem Punktabstand auch seine
    Flächennormalen zur eingepassten Ringfläche gehören.
    """
    found = _fitted(mesh, check_cancelled=check_cancelled).tori if tori is None else tori
    big = [
        entry
        for entry in _torus_candidates(mesh, found)
        if _torus_is_recognisable(mesh.raw, entry[0], entry[1], check_cancelled=check_cancelled)
    ]
    return [
        Feature(
            id=f"torus_{number}",
            kind="torus",
            provenance="detected",
            measure_sources={
                "diameter": "fit",
                "tube_diameter": "fit",
                "axis": "fit",
                "centre": "fit",
            },
            params={
                # **``diameter`` und nicht ``ring_diameter``**, obwohl der
                # Name unschärfer ist: Die Zuordnung liest die Größe eines
                # Merkmals aus genau diesem Schlüssel (``feature_vector``),
                # und zwar für jede Art gleich. Unter einem eigenen Namen war
                # sie null — zwei Tori mit Ringdurchmesser 40 und 60 kosteten
                # gegeneinander 0,0 und waren damit dasselbe Merkmal (§21.2).
                "diameter": fit.ring_radius * 2.0,
                "tube_diameter": fit.tube_radius * 2.0,
                "axis": fit.axis,
                "centre": fit.centre,
                "recess": fit.recess,
                "residual": fit.residual,
                **_round_measures(fit),
            },
            face_indices=tuple(patch),
            surface_patches=(
                SurfacePatch(
                    "torus",
                    {
                        "centre": fit.centre,
                        "axis": fit.axis,
                        "ring_radius": fit.ring_radius,
                        "tube_radius": fit.tube_radius,
                    },
                    tuple(patch),
                    "fit",
                ),
            ),
        )
        for number, (fit, patch) in enumerate(big, start=1)
    ]


def _torus_candidates(mesh: MeshData, tori: Tori) -> Tori:
    """Torusfits mit herstellbarem Maß und ausreichend breiter Oberfläche."""
    # **Das kleinere der beiden Maße entscheidet**, und das ist meist die
    # Röhre: Ein Ring von 40 mm aus einem Rohr von drei Zehnteln ist nichts,
    # was ein Drucker legen kann. Umgekehrt gibt es den ausgearteten Fall
    # (Röhre größer als Ring) auch, und ``min`` fängt beide, ohne dass man
    # entscheiden müsste, welcher der häufigere ist.
    return [
        entry
        for entry in tori
        if not _too_small_to_make(min(entry[0].ring_radius, entry[0].tube_radius) * 2.0)
        and not _a_sliver(mesh.raw, entry[1])
    ]


def _fillets_worth_naming(mesh: MeshData, found: Fillets) -> Fillets:
    """Die Zylinderausschnitte, die groß genug sind, um etwas zu bezeichnen.

    **Die Frage steht hier und nicht in zwei Aufrufern**, denn genau darum
    gibt es :func:`_too_small_to_make`. Zwei lesen sie: :func:`detect_fillets`,
    das daraus ``fillet_N`` macht, und :func:`detect` für
    :mod:`app.core.perceive.slots` — ein Langloch besteht aus zwei solchen
    Ausschnitten, und was für keine Verrundung groß genug ist, ist auch kein
    Loch.

    Der Anlass ist gemessen (10.09.2026): ``find_slots`` bekam die
    **ungefilterte** Liste und veröffentlichte ein Langloch Ø 0,1 auf 0,4 mm,
    während die gleich große runde Bohrung daneben zu Recht keine war. Der
    Wächter ``test_every_fitted_kind_asks_the_same_question`` sieht das nicht:
    Er liest den Quelltext **dieses** Moduls, und die neue Art wohnt in einem
    anderen.
    """
    return [
        entry
        for entry in found
        if not _too_small_to_make(entry[0].radius * 2.0) and not _a_sliver(mesh.raw, entry[1])
    ]


def detect_fillets(
    mesh: MeshData,
    fillets: Fillets | None = None,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Feature]:
    """Verrundete Kanten (§21.1) — Zylinder**ausschnitte**, keine Zapfen.

    ``radius`` statt ``diameter``, und das ist Absicht: Eine Verrundung wird
    mit ihrem Radius bestellt, gezeichnet und gemessen — „R 3", nie „Ø 6". Der
    Durchmesser steht trotzdem daneben, weil die Zuordnung die Größe eines
    Merkmals aus genau diesem Schlüssel liest (§21.2); wer ihn wegließe,
    machte zwei verschieden große Verrundungen für sie ununterscheidbar.

    ``recess`` trennt die innen liegende Kehle von der außen liegenden Rundung
    — dieselbe Unterscheidung wie bei Kegel, Kugel und Torus, aus demselben
    Grund: hinein oder heraus.
    """
    if check_cancelled is not None:
        check_cancelled()
    found = _fitted(mesh, check_cancelled=check_cancelled).fillets if fillets is None else fillets
    body = mesh.raw
    # **Dieselbe Schranke wie bei Bohrung und Zapfen**
    # (:data:`MIN_CYLINDER_DIAMETER`). Hier stand „und sie fehlte hier als
    # Einziger" — das war falsch, gemessen eine Stunde später: Sie fehlte auch
    # bei Kegel, Kugel und Torus, und ich hatte beim Suchen nur die Aufrufer
    # derselben Zylinder-Einpassung angesehen. An
    # „Blessed Family — Heart Script Decor" gemessen: 109 erkannte
    # Verrundungen, die kleinste mit **0,0007 mm** Radius; vier zeigte der
    # Objektbaum als „R0,00 mm" — eine Zahl, die eine Messung behauptet, die
    # es nicht gibt. Zweiundzwanzig lagen unter einer Extrusionsbahn
    # (0,42 mm) und waren damit nicht druckbar (Fund 3d-druck-7f, 03.09.2026).
    #
    # Was dort steht, ist Tesselierung und keine Kante: Wo ein paar Dreiecke
    # zufällig um eine Achse stehen, findet der Fit einen Zylinderausschnitt.
    # Die Begründung ist wörtlich die von :data:`MIN_CYLINDER_DIAMETER` — was
    # für kein Werkzeug groß genug ist, ist auch keine Verrundung.
    big = _fillets_worth_naming(mesh, found)
    # **Eine runde Wand sagt dazu, ob sie in ihre Nachbarn übergeht**
    # (``tangent``): Ihr Radius lässt sich nur ändern, wenn jede angrenzende
    # Fläche dabei in ihrer Ebene bleibt — Deckel, Boden und radial stehende
    # Wände tun das, eine tangential anschließende Flanke nicht
    # (:func:`blends_into_its_neighbours`). Gemessen am 15.09.2026 an sieben
    # Modellen aus dem Netz: 32 Absagen „lässt sich innerhalb ihrer Ränder
    # nicht versetzen" erst nach dem Klick; mit dem Kennzeichen stellt das
    # Panel die Zeile vorher grau.
    radials = [
        radial_cylinder(body, fitted, patch, check_cancelled=check_cancelled)
        for fitted, patch in big
    ]
    # Ein Durchlauf über die Nachbarschaft für alle runden Wände zusammen, nicht
    # einer je Wand: Am Hemmungsrad sind es 531 Verrundungen, und jede einzeln
    # gefragt hieße 531 Gänge über ``face_adjacency``.
    tangent = tangent_walls(
        body, [(patch, radial) for (_fitted, patch), radial in zip(big, radials, strict=True)]
    )
    return [
        Feature(
            id=f"fillet_{number}",
            kind="fillet",
            provenance="detected",
            measure_sources={
                "radius": "fit",
                "diameter": "fit",
                "axis": "fit",
                "centre": "fit",
                "length": "facets",
            },
            params={
                "radius": fit.radius,
                "diameter": fit.radius * 2.0,
                "axis": fit.axis,
                "centre": fit.centre,
                "length": _patch_extent(body, patch, fit.axis),
                "recess": fit.inward,
                "residual": fit.residual,
                **_cylinder_measures(fit),
                **({"radial": True} if radial is not None else {}),
                **({"tangent": True} if radial is not None and blends else {}),
            },
            face_indices=tuple(patch),
            surface_patches=(_cylinder_surface(fit, patch),),
        )
        for number, ((fitted, patch), radial, blends) in enumerate(
            zip(big, radials, tangent, strict=True), start=1
        )
        for fit in (radial or fitted,)
    ]


def blends_into_its_neighbours(
    body: trimesh.Trimesh, patch: Sequence[int], fit: CylinderFit
) -> bool:
    """Ob eine runde Wand tangential in eine Nachbarfläche übergeht.

    Eine radiale Verschiebung der Wand bewegt ihre Randecken radial. Eine
    Nachbarfläche bleibt dabei in ihrer Ebene, wenn ihre Normale quer zur
    radialen Richtung steht — Deckel und Boden (Normale entlang der Achse)
    ebenso wie eine radial stehende Lückenwand. Eine Flanke, die tangential
    an die Wand anschließt, hat ihre Normale **in** radialer Richtung und
    würde aus ihrer Ebene geschoben; ``radial_rounding`` sagt dort ab.
    Dieselbe Schwelle wie für die Ebenen neben einer Kante
    (:data:`UPRIGHT_TO_AXIS`). Für eine Wand allein; die Erkennung fragt alle
    Wände eines Körpers zusammen (:func:`tangent_walls`).
    """
    return tangent_walls(body, [(patch, fit)])[0]


def tangent_walls(
    body: trimesh.Trimesh, walls: Sequence[tuple[Sequence[int], CylinderFit | None]]
) -> list[bool]:
    """Je runder Wand, ob sie tangential in eine Nachbarfläche übergeht — in
    **einem** Gang über die Nachbarschaft des Körpers.

    Ein Feld nennt zu jedem Dreieck seine Wand; jede Nachbarschaftskante, deren
    Seiten verschiedenen Wänden gehören (oder eine keiner), liefert ein
    Randdreieck mit der Wand, an die es grenzt. Dann wird je Wand gerechnet,
    was :func:`blends_into_its_neighbours` beschreibt. Eine Wand ohne
    Einpassung (``None``) ist nie tangential.
    """
    verdict = [False] * len(walls)
    if not walls:
        return verdict
    adjacency = np.asarray(body.face_adjacency, dtype=np.int64)
    if not len(adjacency):
        return verdict
    owner = np.full(len(body.faces), -1, dtype=np.int64)
    for index, (patch, _fit) in enumerate(walls):
        owner[list(patch)] = index
    left, right = owner[adjacency[:, 0]], owner[adjacency[:, 1]]
    across = left != right
    # Je Randkante: die Wand auf der einen Seite, das fremde Dreieck auf der anderen.
    walls_of = np.concatenate((left[across & (left >= 0)], right[across & (right >= 0)]))
    outside = np.concatenate(
        (adjacency[across & (left >= 0), 1], adjacency[across & (right >= 0), 0])
    )
    if not len(outside):
        return verdict
    middles = np.asarray(body.triangles_center, dtype=float)[outside]
    normals = np.asarray(body.face_normals, dtype=float)[outside]
    order = np.argsort(walls_of, kind="stable")
    walls_of, middles, normals = walls_of[order], middles[order], normals[order]
    starts = np.searchsorted(walls_of, np.arange(len(walls)), side="left")
    ends = np.searchsorted(walls_of, np.arange(len(walls)), side="right")
    for index, (_patch, fit) in enumerate(walls):
        if fit is None or ends[index] <= starts[index]:
            continue
        axis = np.asarray(fit.axis, dtype=float)
        relative = middles[starts[index] : ends[index]] - np.asarray(fit.centre, dtype=float)
        radial = relative - np.outer(relative @ axis, axis)
        lengths = np.linalg.norm(radial, axis=1)
        steady = lengths > EPS_GEOM
        if not np.any(steady):
            continue
        radial = radial[steady] / lengths[steady, None]
        facing = normals[starts[index] : ends[index]][steady]
        verdict[index] = bool(
            np.any(np.abs(np.einsum("ij,ij->i", facing, radial)) > UPRIGHT_TO_AXIS)
        )
    return verdict


def face_mask(mesh: MeshData, faces: Sequence[Feature]) -> np.ndarray:
    """Je Dreieck, ob es zu einer erkannten ebenen Fläche gehört."""
    mask = np.zeros(len(mesh.raw.faces), dtype=bool)
    for feature in faces:
        if feature.face_indices:
            mask[list(feature.face_indices)] = True
    return mask


#: Der Fleck, unter dem :func:`planar_mask` seine Antwort merkt — sie gilt dem
#: ganzen Körper und keinem Ausschnitt.
_WHOLE_BODY: Final[tuple[int, ...]] = ()


def planar_mask(mesh: MeshData) -> np.ndarray:
    """Je Dreieck, ob es zu einer ebenen Fläche gehört — einmal je Körper.

    Dieselbe Menge wie ``face_mask(mesh, detect_faces(mesh))``: Die Flächen
    tragen als ``face_indices`` genau die Facetten, die
    :func:`_planar_face_entries` findet; Träger und Innenlage, die
    :func:`detect_faces` danach je Fläche rechnet, liest die Maske nicht. Am
    Halter mit Wabenmuster waren das 320 ms je Rundungsklick im Hauptfaden
    (``actions.fillet_blocked``), für eine Antwort, die sich mit dem Körper
    nicht ändert (Regel 3). Gemerkt wird sie deshalb am Körper
    (:func:`remembered`) und geht mit ihm; das Feld ist schreibgeschützt,
    weil jeder Leser dieselbe Antwort bekommt.
    """

    def compute() -> np.ndarray:
        mask = np.zeros(len(mesh.raw.faces), dtype=bool)
        for facet, _area, _centre in _planar_face_entries(mesh):
            mask[np.asarray(facet, dtype=np.int64)] = True
        mask.flags.writeable = False
        return mask

    return cast(np.ndarray, remembered("planar_mask", mesh.raw, _WHOLE_BODY, compute))


#: Bis zu diesem Winkel (in Grad) zwischen der Mittelnormale und jeder Facette
#: gilt eine gewölbte Fläche des Baums als **ebene** Nachbarin einer Rundung.
#: Gemessen am 16.09.2026 an ``2x1-tray.stl``: Die Vorderwand eines Halters
#: lag mit vier Dreiecken und 0,05 mm Wölbung über 10 mm Höhe (2,8 Grad) als
#: ``curved_face`` im Baum, die Seitenwände mit 2,8 und 8,9 Grad — und
#: *Entfernen* wie *Radius ändern* an den R-10-Ecken daneben lehnten ab:
#: „grenzt nicht an zwei ebene Flächen". Für den Kunden sind das ebene Wände.
#: Ein Zylindermantel bleibt draußen: Seine Facetten spannen 90 Grad und mehr.
NEARLY_FLAT_ANGLE: Final = 10.0


def nearly_flat_mask(body: trimesh.Trimesh, features: Mapping[str, Feature]) -> np.ndarray:
    """Je Dreieck, ob es zu einer gewölbten Fläche gehört, die eben genug ist.

    Gefragt wird je ``curved_face`` des Baums — die Erkennung hat die Haut
    dort schon von den Rundungen getrennt, an die sie tangential anschließt;
    ein Wachsen über Knickwinkel könnte das nicht, denn der Übergang in eine
    Rundung ist der flachste Knick von allen. Eben genug heißt: Jede Facette
    liegt innerhalb :data:`NEARLY_FLAT_ANGLE` um die flächengewichtete
    Mittelnormale. :func:`planes_beside` nimmt solche Flächen als Ebene mit,
    und die Frage „ist daneben eine Ebene" bekommt für eine Wand mit
    Formschräge dieselbe Antwort wie für eine ohne.
    """
    mask = np.zeros(len(body.faces), dtype=bool)
    normals = np.asarray(body.face_normals, dtype=float)
    areas = np.asarray(body.area_faces, dtype=float)
    limit = units.exact_cos_degrees(NEARLY_FLAT_ANGLE)
    for feature in features.values():
        if feature.kind != "curved_face" or not feature.face_indices:
            continue
        chosen = np.asarray(feature.face_indices, dtype=np.int64)
        if chosen.max() >= len(body.faces):
            continue
        mean = (normals[chosen] * areas[chosen, None]).sum(axis=0)
        length = float(np.linalg.norm(mean))
        if length <= EPS_GEOM:
            continue
        mean /= length
        if float(np.min(normals[chosen] @ mean)) >= limit:
            mask[chosen] = True
    return mask


def planes_beside(
    body: trimesh.Trimesh,
    patch: Sequence[int],
    axis: np.ndarray,
    planar_faces: np.ndarray,
    *,
    centre: np.ndarray | None = None,
) -> list[tuple[np.ndarray, np.ndarray]] | None:
    """Die ebenen Nachbarflächen quer zur Achse eines Bogens — je Ebene ihre
    Normale und ein Punkt darauf.

    Mit ``centre`` — der Achsenmitte des Bogens — müssen die Ebenen den Bogen
    außerdem **tangential** fortsetzen: Am gemeinsamen Rand zeigt die radiale
    Richtung des Bogens in die Normale der Ebene. Ein Bogen, der zwei Ebenen
    schräg trifft, ersetzt keine Kante zwischen ihnen. Gemessen am 15.09.2026
    an den Gleisen einer Modellscheune: eine Hohlkehle R 28 zwischen zwei
    Bögen und zwei Ebenen, die sie nicht berühren — *Entfernen* rechnete aus
    den beiden Ebenen eine Kante, die es nicht gibt, trug 2,7 Prozent des
    Volumens ab, und die Hohlkehle stand danach unverändert im Baum.

    **Nur die quer zur Achse.** Eine Rundung an einer senkrechten Kante grenzt
    auch an Deckel und Boden, und die beiden sind einander entgegengesetzt:
    Der erste Anlauf der Bearbeitung nahm sie als das gesuchte Paar und bekam
    „diese Flächen sind parallel" zurück. Gesucht sind die Flächen, zwischen
    denen die Rundung *liegt*, und die stehen senkrecht auf ihrer Achse
    (:data:`UPRIGHT_TO_AXIS`).

    ``None``, sobald eine quer stehende Nachbarfläche **nicht** eben ist: Eine
    Mantelfacette besitzt ebenfalls eine Normale, aber keine Ebene, und ihre
    lokale Tangente ergäbe eine falsche Kante. Eben heißt, was die
    Flächenerkennung als Fläche ausweist (:func:`face_mask`).

    **Eine Frage, zwei Leser:** ``geom/edges.py`` stellt sie, bevor es die
    Kante unter einer Rundung zurückrechnet, und ``perceive/actions.py``,
    bevor es *Entfernen* und *Radius ändern* an einer Rundung anbietet.
    Gemessen am 15.09.2026 über 34 Modelle aus dem Netz: An 50 von 52
    Umrissbögen (Uhrenanker, Laschen, Aussparungen) bot das Panel an, was die
    Operation dann mit „grenzt nicht an zwei ebene Flächen" ablehnte. Der
    Name bleibt — eine Verrundung zwischen einer Ebene und einem
    Zylindermantel ist eine verrundete Kante, auch wenn sie sich nicht auf
    zwei Ebenen zurückführen lässt —, die Zeile wird vorher grau.
    """
    member = np.zeros(len(body.faces), dtype=bool)
    member[list(patch)] = True
    adjacency = np.asarray(body.face_adjacency, dtype=np.int64)
    if not len(adjacency):
        return []
    inside_a = member[adjacency[:, 0]]
    inside_b = member[adjacency[:, 1]]
    crossing_rows = np.concatenate(
        (np.flatnonzero(inside_a & ~inside_b), np.flatnonzero(inside_b & ~inside_a))
    )
    outside = np.concatenate(
        (adjacency[inside_a & ~inside_b, 1], adjacency[inside_b & ~inside_a, 0])
    )
    if not len(outside):
        return []
    face_normals = np.asarray(body.face_normals, dtype=float)
    across = np.abs(face_normals[outside] @ axis) <= UPRIGHT_TO_AXIS
    outside = outside[across]
    crossing_rows = crossing_rows[across]
    if not len(outside):
        return []
    if not bool(np.all(planar_faces[outside])):
        return None
    if centre is not None:
        # Der gemeinsame Rand jeder Nachbarfläche: Zeigt die radiale Richtung
        # des Bogens dort nicht in die Normale der Ebene, setzt die Ebene den
        # Bogen nicht tangential fort — und darunter liegt keine Kante.
        edges = np.asarray(body.face_adjacency_edges, dtype=np.int64)[crossing_rows]
        vertices = np.asarray(body.vertices, dtype=float)
        middles = (vertices[edges[:, 0]] + vertices[edges[:, 1]]) / 2.0 - centre
        radial = middles - np.outer(middles @ axis, axis)
        lengths = np.linalg.norm(radial, axis=1)
        steady = lengths > EPS_GEOM
        if np.any(steady):
            grazing = np.abs(
                np.einsum(
                    "ij,ij->i",
                    radial[steady] / lengths[steady, None],
                    face_normals[outside][steady],
                )
            )
            if bool(np.any(grazing < TANGENT_TO_THE_ARC)):
                return None
    centres = np.asarray(body.triangles_center, dtype=float)
    areas = np.asarray(body.area_faces, dtype=float)
    # Die Reihenfolge der Nachbarschaftsliste bleibt, damit die Bearbeitung
    # dieselbe erste und zweite Ebene sieht wie bisher. **Facetten einer
    # fast ebenen Haut zählen als eine Ebene** (:data:`NEARLY_FLAT_ANGLE`):
    # Normale und Punkt werden flächengewichtet gemittelt, sonst stünden für
    # eine Wand mit Formschräge zwei Ebenen da, wo eine gemeint ist.
    limit = units.exact_cos_degrees(NEARLY_FLAT_ANGLE)
    groups: list[list[int]] = []
    for face in outside.tolist():
        normal = face_normals[face]
        for group in groups:
            if float(np.dot(normal, face_normals[group[0]])) >= limit:
                group.append(face)
                break
        else:
            groups.append([face])
    planes: list[tuple[np.ndarray, np.ndarray]] = []
    for group in groups:
        chosen = np.asarray(group, dtype=np.int64)
        weight = areas[chosen, None]
        normal = (face_normals[chosen] * weight).sum(axis=0)
        normal /= float(np.linalg.norm(normal)) or 1.0
        place = (centres[chosen] * weight).sum(axis=0) / float(weight.sum())
        planes.append((normal, place))
    return planes


def replaces_an_edge(
    body: trimesh.Trimesh,
    patch: Sequence[int],
    axis: Sequence[float],
    planar_faces: np.ndarray,
    *,
    centre: Sequence[float] | None = None,
) -> bool:
    """Ob dieser Bogen die Kante zwischen genau zwei Ebenen ersetzt — die ihn
    tangential fortsetzen, wenn seine Mitte bekannt ist."""
    beside = planes_beside(
        body,
        patch,
        np.asarray(axis, dtype=float),
        planar_faces,
        centre=None if centre is None else np.asarray(centre, dtype=float),
    )
    return beside is not None and len(beside) == SIDES_OF_AN_EDGE


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
        # **Dieselbe Schranke wie bei der Bohrung** (:data:`MIN_CYLINDER_DIAMETER`).
        # Sie stand hier nicht, und damit meldete dieselbe Platte einen Zapfen
        # Ø 0,05 neben einer Vertiefung Ø 0,05, die zu Recht keine Bohrung war.
        if not entry[0].inward
        and not _too_small_to_make(entry[0].radius * 2.0)
        and not _a_sliver(mesh.raw, entry[1])
    ]
    return [
        Feature(
            id=f"pin_{number}",
            kind="pin",
            provenance="detected",
            measure_sources={"diameter": "fit", "axis": "fit", "centre": "fit", "depth": "facets"},
            params={
                "diameter": fit.radius * 2.0,
                "axis": fit.axis,
                "centre": fit.centre,
                "depth": _patch_extent(body, patch, fit.axis),
                "residual": fit.residual,
                **_cylinder_measures(fit),
            },
            face_indices=tuple(patch),
            surface_patches=(_cylinder_surface(fit, patch),),
        )
        for number, (fit, patch) in enumerate(found, start=1)
    ]


def detect_cones(
    mesh: MeshData,
    cones: Cones | None = None,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Feature]:
    """Kegelige Flecken (§21.1): Senkungen, Fasen an Bohrungen, Verjüngungen.

    Warum es die Art überhaupt braucht: Ohne sie ist eine Senkung eine Bohrung
    plus ein namenloser Haufen Dreiecke — der Agent kann nicht auf sie zeigen,
    und Leitprinzip 5 lässt ihm keinen zweiten Weg, weil er Koordinaten nicht
    erzeugt. Der Winkel steht als **Öffnungswinkel** in den Parametern und
    nicht als Halbwinkel: Eine Senkung heißt „90 Grad", und das ist der ganze
    Kegel.
    """
    found = _fitted(mesh, check_cancelled=check_cancelled).cones if cones is None else cones
    # Dieselbe Werkzeugschranke wie bei Bohrung, Zapfen und Verrundung
    # (:data:`MIN_CYLINDER_DIAMETER`) — siehe :func:`_too_small_to_make`.
    big = [
        entry
        for entry in found
        if not _too_small_to_make(entry[0].radius * 2.0)
        and not _a_sliver(mesh.raw, entry[1])
        and _cone_is_recognisable(mesh.raw, entry[0], entry[1], check_cancelled=check_cancelled)
    ]
    return [
        Feature(
            id=f"cone_{number}",
            kind="cone",
            provenance="detected",
            measure_sources={"diameter": "fit", "angle": "fit", "axis": "fit", "centre": "fit"},
            params={
                "diameter": fit.radius * 2.0,
                "angle": fit.half_angle * 2.0,
                "axis": fit.axis,
                # Die Auswahlmitte bleibt hier; die tatsächliche Spitze steht
                # am getrennten Träger und wird mit dessen gerichteter Nappe bewegt.
                "centre": fit.centre,
                "recess": fit.recess,
                "residual": fit.residual,
                **_round_measures(fit),
            },
            face_indices=tuple(patch),
            surface_patches=(
                SurfacePatch(
                    "cone",
                    {
                        "apex": fit.apex,
                        "axis": fit.axis,
                        "half_angle": math.radians(fit.half_angle),
                    },
                    tuple(patch),
                    "fit",
                ),
            ),
        )
        for number, (fit, patch) in enumerate(big, start=1)
    ]


def _partial_cones_folded(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Kegelstücke unter dem vollen Umlauf: zum Langloch, zur Bohrung — oder Fase.

    **Der Fall, der die Regel gebraucht hat:** Der Rahmen eines
    Schreibtisch-Organizers (MakerWorld, 15.09.2026) trägt 33 Langlöcher mit
    gefaster Mündung, und die Erkennung machte daraus **126 „Senkung 90°
    Ø 5,80"** — je Langloch vier Halbkegel von 180 Grad, an beiden Enden und
    beiden Seiten. Die Fächer desselben Modells zeigten Viertelkegel an ihren
    Kastenecken als „Verjüngung 96°", ein Hemmungsrad fünf „Verjüngungen 12°"
    mit zehn Dreiecken auf Zahnflanken. Und an jedem davon sagten Ändern,
    Versetzen, Drehen, Verdoppeln und Entfernen ab: Der Rand eines Teilkegels
    liegt in keiner Ebene, aus ihm wird kein Körper (``_body_from_faces``) —
    280 Abbrüche im Lauf, während das Panel jede Zeile anbot.

    Ein Kegel unter :data:`FULL_TURN_SPAN` ist eine **Fase an einer Kante**, so
    wie ein Zylinder darunter eine Verrundung ist (:func:`_split_off_fillets`) —
    dieselbe Grenze, aus demselben Grund. Wem er gehört, sagt die
    Nachbarschaft:

    * grenzt er an den Mantel eines **Langlochs**, ist er dessen Mündungsfase
      und geht im Langloch auf — so wie die Bögen der Enden;
    * grenzt er an eine **Bohrung**, bleibt er, was er war: die Senkung einer
      Bohrung, die eine Kante oder ein zweites Merkmal angeschnitten hat, und
      die Kette (``relations.cavity_chain_at``) nimmt ihn mit;
    * sonst bleibt er als Auskunft im Baum — als **Kegelfläche** (``partial``),
      ohne Körperhandlungen: Ein Stück Kegel hat keinen ebenen Rand, aus dem
      ein Werkzeug entstünde, und das Panel sagt es vorher
      (``actions.CONE_PIECE_HAS_NO_BODY``). Wegzulassen war er nicht: Die
      Blütenblätter eines Gewindeprüfers sind Kegel von 259 Grad, und ohne sie
      im Bestand hielt die Freiformprobe vier Körper eines Minigolf-Satzes für
      Figuren und nahm ihnen 23 Ringe gleich mit (gemessen 15.09.2026).

    Ein voller Kegel bleibt unberührt. Die dokumentierte Zusage, dass
    Teilbogenkegel die Normalenprobe nicht am Vollumfang scheitern lassen
    (``_cone_is_recognisable``), gilt weiter: Sie entscheidet, ob ein Fleck ein
    Kegel ist; hier entscheidet sich, wem er gehört.
    """
    if check_cancelled is not None:
        check_cancelled()
    body = mesh.raw
    cones = [
        (identifier, feature)
        for identifier, feature in found.items()
        if feature.kind == "cone" and feature.face_indices
    ]
    if not cones:
        return dict(found)
    partial = [
        (identifier, feature)
        for identifier, feature in cones
        if span_about(
            body,
            np.asarray(feature.params["axis"], dtype=float),
            np.asarray(feature.params["centre"], dtype=float),
            feature.face_indices,
        )
        < FULL_TURN_SPAN
    ]
    if not partial:
        return dict(found)

    owner = np.full(len(body.faces), -1, dtype=np.int64)
    names: list[FeatureId] = []
    for identifier, feature in found.items():
        if feature.kind in ("slot", "hole") and feature.face_indices:
            owner[list(feature.face_indices)] = len(names)
            names.append(identifier)
    adjacency = np.asarray(body.face_adjacency, dtype=np.int64)

    # Ein Gang über die Nachbarschaft für alle Kegelstücke: Je Randkante die
    # Nummer des Stücks auf der einen und der Besitzer des Dreiecks auf der
    # anderen Seite — gezählt je Stück und Nachbar, denn ein Stück zwischen
    # zwei Langlöchern gehört zu dem, mit dem es mehr Kanten teilt, nicht zum
    # alphabetisch ersten.
    piece = np.full(len(body.faces), -1, dtype=np.int64)
    for index, (_identifier, feature) in enumerate(partial):
        piece[list(feature.face_indices)] = index
    left, right = piece[adjacency[:, 0]], piece[adjacency[:, 1]]
    from_left = (left >= 0) & (right < 0)
    from_right = (right >= 0) & (left < 0)
    pieces_of = np.concatenate((left[from_left], right[from_right]))
    beside = np.concatenate((adjacency[from_left, 1], adjacency[from_right, 0]))
    shared: list[Counter[FeatureId]] = [Counter() for _ in partial]
    for index, neighbour in zip(pieces_of.tolist(), owner[beside].tolist(), strict=True):
        if neighbour >= 0:
            shared[index][names[neighbour]] += 1

    kept = dict(found)
    grown: dict[FeatureId, set[int]] = {}
    grown_patches: dict[FeatureId, list[SurfacePatch]] = {}
    for index, (identifier, feature) in enumerate(partial):
        if check_cancelled is not None:
            check_cancelled()
        neighbours = shared[index]
        slots = [name for name in neighbours if found[name].kind == "slot"]
        if slots:
            most = max(neighbours[name] for name in slots)
            leaders = [name for name in slots if neighbours[name] == most]
            if len(leaders) != 1:
                # **Gleichstand ist kein Beleg** (Regel 21). Eine Senkung Ø 12
                # zwischen zwei Langlöchern Ø 6 bei y = ±4 teilt mit beiden
                # acht Kanten; bis zum 21.09.2026 gewann der alphabetisch
                # spätere Name, und der Kegel verschwand im zweiten Langloch,
                # während der exakte Kern ihn als Kegelfläche stehen ließ.
                kept[identifier] = replace(feature, params={**feature.params, "partial": True})
                continue
            closest = leaders[0]
            grown.setdefault(closest, set()).update(int(face) for face in feature.face_indices)
            grown_patches.setdefault(closest, []).extend(feature.surface_patches)
            del kept[identifier]
        elif not any(found[name].kind == "hole" for name in neighbours):
            kept[identifier] = replace(feature, params={**feature.params, "partial": True})
    if grown:
        _mouth_flanks_folded(
            mesh, found, kept, grown, grown_patches, check_cancelled=check_cancelled
        )
    for name, faces in grown.items():
        # Nur die Flächen wachsen; Länge, Tiefe und Durchgang des Langlochs
        # bleiben bewusst die Nennmaße ohne die Fase.
        slot = kept[name]
        kept[name] = replace(
            slot,
            face_indices=tuple(sorted({*slot.face_indices, *faces})),
            surface_patches=slot.surface_patches + tuple(grown_patches[name]),
        )
    return kept


def _mouth_flanks_folded(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    kept: Mapping[FeatureId, Feature],
    grown: dict[FeatureId, set[int]],
    grown_patches: dict[FeatureId, list[SurfacePatch]],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> None:
    """Die geraden Flanken der Mündungsfase gehören zum Langloch wie ihre Kegel.

    Zwischen den zwei Halbkegeln liegen zwei schräge Ebenen — an einem
    Langloch Ø 6 auf 26 mit 1-mm-Fase je 20·√2 mm². Sie sind keine Flächen
    (ihre Ränder zu den Kegelfacetten sind Rundungsstufen) und gehörten bisher
    niemandem; der exakte Kern nannte sie als Flächen. Jetzt gilt an beiden
    Kernen dieselbe Regel: Ein ebener Fleck, der an einen übernommenen Kegel
    **und** an den Mantel desselben Langlochs grenzt und schräg zu dessen
    Achse steht, ist die gerade Flanke derselben Fase — er geht mit seinem
    Ebenenträger im Langloch auf (P1.5, 20.09.2026).
    """
    from app.core.perceive.slots import ACROSS_THE_AXIS
    from app.core.perceive.surfaces import planar_patch

    body = mesh.raw
    taken = np.zeros(len(body.faces), dtype=bool)
    for feature in found.values():
        if feature.face_indices:
            taken[list(feature.face_indices)] = True
    normals = np.asarray(body.face_normals, dtype=float)
    neighbours: dict[int, list[int]] = {}
    for left, right in np.asarray(body.face_adjacency, dtype=np.int64).tolist():
        neighbours.setdefault(left, []).append(right)
        neighbours.setdefault(right, []).append(left)
    for name, pieces in grown.items():
        if check_cancelled is not None:
            check_cancelled()
        axis = np.asarray(kept[name].params["axis"], dtype=float)
        along = np.abs(normals @ axis)
        tilted = (along >= ACROSS_THE_AXIS) & (along < units.exact_cos_degrees(1.0))
        # Das Band der Fase: von den Kegelstücken aus über freie, schräge
        # Nachbarn. Das sind die letzten Kegelfacetten, die der Fit an der
        # Naht zur Flanke ausließ, und die geraden Flanken dazwischen —
        # Deckel (quer) und Mantel (längs) gehören nicht dazu.
        band = set(pieces)
        frontier = list(pieces)
        while frontier:
            if check_cancelled is not None:
                check_cancelled()
            following = [
                index
                for triangle in frontier
                for index in neighbours.get(triangle, ())
                if index not in band and not taken[index] and tilted[index]
            ]
            band.update(following)
            frontier = following
        added = band - pieces
        if not added:
            continue
        for facet in body.facets:
            indices = [int(index) for index in facet]
            if not all(index in added for index in indices):
                continue
            centre = _facet_centre(body, np.asarray(indices, dtype=np.int64))
            normal = normals[indices[0]]
            patch = planar_patch(
                mesh,
                indices,
                (float(centre[0]), float(centre[1]), float(centre[2])),
                (float(normal[0]), float(normal[1]), float(normal[2])),
                check_cancelled=check_cancelled,
            )
            if patch is not None:
                grown_patches.setdefault(name, []).append(patch)
        taken[list(added)] = True
        pieces.update(added)


def _partial_bores_marked(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Eine Bohrung, deren Mantel zwei Schnittlinien längs der Achse begrenzen,
    ist angeschnitten — ``partial``, dasselbe Wort wie am exakten Körper.

    Ein Mantel über :data:`FULL_TURN_SPAN` ist eine Bohrung; ob er **ganz** ist,
    sagt nicht der Winkel — ein volles Loch misst am Netz je nach Facettierung
    345 bis 354 Grad —, sondern sein Rand: Ein ganzer Mantel endet nur an
    seinen zwei Ringen, ein angeschnittener zusätzlich an **zwei geraden
    Linien längs der Achse**, die seine ganze Tiefe durchlaufen (P1.5,
    Gegenfall 2: zwei überlappende Bohrungen zu je 315 Grad). Ein Querloch
    durch den Mantel hat solche Linien nicht; es bleibt eine ganze Bohrung mit
    einem Loch in der Wand.

    Was ein angeschnittener Mantel bedeutet, entscheidet danach die
    Nachbarschaft (``relations._cavity_links``): Grenzt er an eine andere
    Höhlung, ist er berührt und hat keinen eigenen Körper.
    """
    if check_cancelled is not None:
        check_cancelled()
    body = mesh.raw
    holes = [
        (identifier, feature)
        for identifier, feature in found.items()
        if feature.kind == "hole" and feature.face_indices and not feature.params.get("partial")
    ]
    if not holes:
        return dict(found)
    vertices = np.asarray(body.vertices, dtype=float)
    faces = np.asarray(body.faces, dtype=np.int64)
    tolerance = weld_tolerance(float(np.linalg.norm(body.extents)))
    kept = dict(found)
    for identifier, feature in holes:
        if check_cancelled is not None:
            check_cancelled()
        axis = np.asarray(feature.params["axis"], dtype=float)
        chosen = faces[np.asarray(feature.face_indices, dtype=np.int64)]
        # Die Kanten als eine Zahl je Kante zählen (``_edge_codes``): ein
        # ``np.unique`` über Zeilenpaare sortierte an der Lochplatte je Bohrung
        # 73 000 Zeilen in dreißig Millisekunden, die Zahl in drei.
        codes = _edge_codes(chosen, len(vertices))
        unique_codes, count = np.unique(codes, return_counts=True)
        boundary_codes = unique_codes[count == 1]
        boundary = np.column_stack(
            (boundary_codes // len(vertices), boundary_codes % len(vertices))
        )
        if not len(boundary):
            continue
        vectors = vertices[boundary[:, 1]] - vertices[boundary[:, 0]]
        lengths = np.linalg.norm(vectors, axis=1)
        axial = (lengths > tolerance) & (np.abs(vectors @ axis) >= PARALLEL_AXES * lengths)
        if not axial.any():
            continue
        points = vertices[boundary[axial]].reshape(-1, 3)
        projected = points - np.outer(points @ axis, axis)
        lines = np.unique(np.round(projected / max(tolerance, EPS_GEOM)).astype(np.int64), axis=0)
        if len(lines) != 2:
            continue
        # Beide Linien laufen durch die ganze Tiefe des Mantels.
        heights = vertices[np.unique(chosen)] @ axis
        depth = float(heights.max() - heights.min())
        for line in lines:
            on_line = np.all(
                np.round(projected / max(tolerance, EPS_GEOM)).astype(np.int64) == line, axis=1
            )
            reach = points[on_line] @ axis
            if float(reach.max() - reach.min()) < depth - units.MAX_FACET_SAG:
                break
        else:
            kept[identifier] = replace(feature, params={**feature.params, "partial": True})
    return kept


def _curved_faces(body: trimesh.Trimesh) -> set[int]:
    """Dreiecke, die auf einer gerundeten Oberfläche sitzen.

    Erkannt an der Naht zu ihren Nachbarn: koplanar (null Grad) ist dieselbe
    Fläche, ein deutlicher Knick ist eine Kante, und alles dazwischen ist die
    Stufe einer Rundung, die das Netz nur nicht rund darstellen kann.
    """
    result: set[int] = remembered(
        "curved_faces",
        body,
        (),
        lambda: _curved_faces_read(body),
    )
    return result


def _curved_faces_read(body: trimesh.Trimesh) -> set[int]:
    """Der Rumpf von :func:`_curved_faces` — die Antwort merkt sich die Hülle."""
    if not len(body.face_adjacency):
        return set()
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    rounded = (angles > EPS_ANGLE) & (angles < CURVATURE_LIMIT)
    if not rounded.any():
        return set()
    pairs = np.asarray(body.face_adjacency)[rounded]
    return {int(index) for index in pairs.ravel()}


def _facets_standing_apart(
    body: trimesh.Trimesh, facets: Sequence[np.ndarray], curved: set[int]
) -> set[int]:
    """Die Flecken, die auch unter :data:`MIN_FACE_AREA` eine eigene Fläche sind.

    Der Beleg kommt aus den Rändern, nicht aus der Größe: Jede Naht des Flecks
    zu einem Dreieck, das nicht zu ihm gehört, ist ein scharfer Knick
    (mindestens :data:`CURVATURE_LIMIT`), kein Dreieck des Flecks liegt auf
    einer Rundung, und der Fleck ist kein Streifen. Ein 1-mm-Nocken erfüllt das
    an allen fünf Seiten; die Facette einer Kugel stößt an ihre Nachbarn nur
    mit der Stufe der Rundung, ein Mantelstreifen ebenso — beide bleiben, wo
    sie sind. Zurück kommen die **Positionen** in ``facets``.

    **Und jede Randkante muss einen Nachbarn haben.** „Jede Naht ist scharf"
    gilt nur über die Nähte, die das Netz kennt; wo eine Kante keinen
    Nachbarn hat, ist der Rand unbelegt, nicht scharf. An
    ``plate_countersunk.stl`` stoßen die Mantelstreifen der Bohrung nicht
    aneinander — die STL schreibt sie mit T-Stößen —, und ohne diese Zeile
    hatte jeder zweite Streifen nur den Boden und die Senkung als Nachbarn,
    beide scharf: 30 „Flächen" zu je 1,9 mm² auf einem Mantel (gemessen
    20.09.2026). Ein Fleck aus ``n`` Dreiecken hat ``3n`` Kanten; jede innere
    Nachbarschaft deckt zwei, jede äußere eine.

    **Und was hinter der Naht liegt, ist selbst eine Fläche.** Der Nocken
    stößt an allen Seiten an Flächen, die nicht zu ihm gehören — seine vier
    Seiten, die Platte. Auf einer verrauschten Freiform sind zwei zufällig
    ebene Dreiecke ringsum scharf geknickt, weil das Rauschen jeden Knick
    scharf macht, und hinter jeder Naht liegt ein Dreieck, das zu keinem
    Fleck gehört: gemessen am 21.09.2026 an der Freiform mit 200 000
    Dreiecken, zwei „Flächen" von 0,22 und 0,16 mm². Eine Naht zu einem
    Dreieck ohne Fleck ist deshalb kein Beleg, sondern eine Absage.

    Ein Durchgang über die Nachbarschaft, nicht einer je Fleck: An einem Netz
    mit einer Million Dreiecken zählt das.
    """
    # Beide Aufrufer reichen ``body.facets`` und ``_curved_faces(body)`` herein —
    # die Antwort hängt am Körper, und ``_large_facet_faces`` wie
    # ``_planar_face_entries`` fragen sie je Erkennung einmal.
    result: set[int] = remembered(
        "facets_standing_apart",
        body,
        (),
        lambda: _facets_standing_apart_read(body, facets, curved),
    )
    return result


def _facets_standing_apart_read(
    body: trimesh.Trimesh, facets: Sequence[np.ndarray], curved: set[int]
) -> set[int]:
    """Der Rumpf von :func:`_facets_standing_apart` — die Antwort merkt sich die Hülle."""
    if not facets or not len(body.face_adjacency):
        return set()
    owner = np.full(len(body.faces), -1, dtype=np.int64)
    for number, facet in enumerate(facets):
        owner[np.asarray(facet, dtype=np.int64)] = number
    pairs = np.asarray(body.face_adjacency, dtype=np.int64)
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    first, second = owner[pairs[:, 0]], owner[pairs[:, 1]]
    boundary = first != second
    soft = boundary & ((angles < CURVATURE_LIMIT) | (first < 0) | (second < 0))
    disqualified = {int(index) for index in first[soft]} | {int(index) for index in second[soft]}
    disqualified.discard(-1)
    counted = np.zeros(len(facets), dtype=np.int64)
    inner = first == second
    np.add.at(counted, first[inner & (first >= 0)], 2)
    np.add.at(counted, first[boundary & (first >= 0)], 1)
    np.add.at(counted, second[boundary & (second >= 0)], 1)
    _members, _owner, sizes, touches_curved = _facet_table(facets, len(body.faces), curved)
    eligible = (counted == 3 * sizes) & ~touches_curved
    if disqualified:
        eligible[np.fromiter(disqualified, dtype=np.int64, count=len(disqualified))] = False
    apart: set[int] = set()
    for number in np.flatnonzero(eligible).tolist():
        if _a_sliver(body, [int(index) for index in facets[number]]):
            continue
        apart.add(number)
    return apart


def _all_but(count: int, left_out: set[int]) -> list[int]:
    """Die Dreiecksnummern ``0 … count - 1`` ohne die genannten, aufsteigend.

    Als Maske statt als Prüfung je Nummer gegen die Menge: an 327 680
    Dreiecken vier statt fünfzehn Millisekunden (gemessen am 21.09.2026).
    """
    mask = np.ones(count, dtype=bool)
    if left_out:
        mask[np.fromiter(left_out, dtype=np.int64, count=len(left_out))] = False
    return np.flatnonzero(mask).tolist()


def _facet_table(
    facets: Sequence[np.ndarray], face_count: int, curved: set[int]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Alle Facetten als vier Felder: Mitglieder, Besitzer je Mitglied,
    Größe je Facette und ob eine Facette ein gerundetes Dreieck trägt.

    Dieselbe Bauart wie :func:`_facet_areas`, für die Fragen, die
    :func:`_large_facet_faces_read` und :func:`_facets_standing_apart_read`
    je Facette stellen — einmal gebaut statt je Frage eine Schleife.
    """
    sizes = np.fromiter((len(facet) for facet in facets), dtype=np.int64, count=len(facets))
    members = (
        np.concatenate([np.asarray(facet, dtype=np.int64) for facet in facets])
        if len(facets)
        else np.zeros(0, dtype=np.int64)
    )
    owner = np.repeat(np.arange(len(facets)), sizes)
    curved_mask = np.zeros(face_count, dtype=bool)
    if curved:
        curved_mask[np.fromiter(curved, dtype=np.int64, count=len(curved))] = True
    touches_curved = np.bincount(owner, weights=curved_mask[members], minlength=len(facets)) > 0
    return members, owner, sizes, touches_curved


def _facet_areas(body: trimesh.Trimesh, facets: Sequence[np.ndarray]) -> list[float]:
    """Die Fläche je Facette — eine Summe über alle Dreiecke statt einer je Facette.

    41 310 Facetten der glatten Freiform kosteten als Schleife 38 ms, als
    ``bincount`` acht (gemessen am 21.09.2026); die Zahlen sind dieselben
    bis auf die Reihenfolge der Summanden.
    """
    if not facets:
        return []
    lengths = np.fromiter((len(facet) for facet in facets), dtype=np.int64, count=len(facets))
    members = np.concatenate([np.asarray(facet, dtype=np.int64) for facet in facets])
    owner = np.repeat(np.arange(len(facets)), lengths)
    weights = np.asarray(body.area_faces, dtype=float)[members]
    summed: list[float] = np.bincount(owner, weights=weights, minlength=len(facets)).tolist()
    return summed


def _large_facet_faces(
    body: trimesh.Trimesh,
    *,
    check_cancelled: Callable[[], None] | None = None,
    requested: set[int] | None = None,
    check_patch_size: Callable[[int], None] | None = None,
) -> set[int]:
    """Ebene Flecken von den Streifen einer gekrümmten Haut unterscheiden.

    Scharf begrenzte Flächen zählen ab der absoluten Erkennungsauflösung.
    Eine größere Bodenplatte darf kleine Nocken oder Drehwegdächer nicht
    unterdrücken. Viele koplanare Dreiecke oder eine breite Ebene qualifizieren
    sich auch neben einer Rundung; der vollständige Mantelnachweis schützt
    weiterhin vor bloß unterteilten Zylinderstreifen.

    Die Antwort für den ganzen Körper wird gemerkt (:func:`remembered`):
    Jeder Klick auf eine Bohrung fragte sie zweimal, je 0,17 s an der
    Lochplatte mit 360 000 Dreiecken (gemessen am 22.09.2026). Die lokale
    Erkennung mit ``requested`` oder Flächenbudget rechnet weiter selbst.
    """
    if check_cancelled is not None:
        check_cancelled()
    if requested is None and check_patch_size is None:
        planar: set[int] = remembered(
            "large_facet_faces",
            body,
            (),
            lambda: _large_facet_faces_read(body, check_cancelled=check_cancelled),
            check_cancelled=check_cancelled,
        )
        return set(planar)
    return _large_facet_faces_read(
        body,
        check_cancelled=check_cancelled,
        requested=requested,
        check_patch_size=check_patch_size,
    )


def _large_facet_faces_read(
    body: trimesh.Trimesh,
    *,
    check_cancelled: Callable[[], None] | None = None,
    requested: set[int] | None = None,
    check_patch_size: Callable[[int], None] | None = None,
) -> set[int]:
    """Der Rumpf von :func:`_large_facet_faces` — die Antwort merkt sich die Hülle."""
    facets = list(body.facets)
    if not facets:
        return set()
    areas = _facet_areas(body, facets)
    # Ein Mantelstreifen eines Zylinders ist groß genug für eine Fläche und
    # trotzdem keine eigene Ebene — die Naht zu seinen Nachbarn sagt es. Der
    # zweite Weg bleibt davon unberührt: ein Fleck aus vielen koplanaren
    # Dreiecken ist eine Fläche, auch wenn er auf einer Rundung sitzt.
    curved = _curved_faces(body)
    # **Gemessen an der Gesamtoberfläche, nicht an der größten Facette.** Der
    # naheliegende Maßstab ist der falsche, und der Körper, der es zeigt, ist
    # der Torus: Er besteht **nur** aus Mantelstreifen, seine größte Facette
    # ist selbst einer, und jede liegt damit bei fast hundert Prozent. Gegen
    # die größte gemessen zerfiel ``torus_ring.stl`` in 288 ebene Flächen.
    broad = float(body.area) * BROAD_FACE_SHARE
    # **Der erste Zweig prüft die Rundung nicht, und das ist eine offene
    # Stelle.** Ein Mantelstreifen, den eine Boolesche neu vernetzt hat, besteht
    # aus mehr als acht koplanaren Dreiecken und kommt hier unbesehen durch.
    # Gemessen an einem Mast Ø 5, dessen Zapfen einmal versetzt wurde:
    # fünfzig Facetten qualifizieren sich allein über die Dreieckszahl, alle
    # fünfzig sitzen auf der Rundung, und der Zapfen trägt danach 720 statt
    # 1630 Dreiecke — 43 ebene Flächen stehen daneben, die alle zu ihm gehören.
    #
    # **Die naheliegende Ergänzung ``and not any(... in curved ...)`` ist
    # gemessen und wieder ausgebaut** (04.09.2026): Sie bringt den Mast von 47
    # Merkmalen auf 8 und gibt ihm seinen Zapfen zurück, nimmt aber die
    # Deckfläche eines Gewindebolzens mit — deren *Rand* grenzt an den
    # Gewindekamm, und schon ein einziges Dreieck darin verwirft die ganze
    # Facette. Danach passt die Erkennung dort eine Kugel Ø 23 ein.
    # Der Anteil statt des Vorkommens trennt es nicht: die Streifen liegen bei
    # 0,00 bis 0,85, die echte Deckfläche bei 0,15.
    apart = _facets_standing_apart(body, facets, curved)
    # **Je Facette eine Zahl, nicht je Dreieck eine Mengenfrage.** Die
    # Comprehensions darunter fragten an der unterteilten Lochplatte
    # 115 000-mal ``index in curved`` (gemessen am 22.09.2026: 60 ms je
    # Erkennung); ``_facet_table`` beantwortet „berührt die Facette eine
    # Rundung" für alle Facetten mit einem ``bincount``.
    members, owner, sizes, touches_curved = _facet_table(facets, len(body.faces), curved)
    area_of = np.asarray(areas, dtype=float)
    stands_apart = np.zeros(len(facets), dtype=bool)
    if apart:
        stands_apart[np.fromiter(apart, dtype=np.int64, count=len(apart))] = True
    planar_facets = (
        (sizes >= MIN_FLAT_FACES)
        | (area_of >= broad)
        | ((area_of >= MIN_FACE_AREA) & ~touches_curved)
        | stands_apart
    )
    planar = set(members[planar_facets[owner]].tolist())
    # Viele Dreiecke machen aus einem Mantelstreifen noch keine eigenständige
    # Ebene. Das gilt auch dann, wenn der Streifen breiter als
    # ``MIN_SURFACE_WIDTH`` ist: Der Boolesche Kern unterteilt einen
    # 48-seitigen Bohrungsmantel längs und erzeugt so zehn koplanare Dreiecke
    # je Facette. Ihre Naht zu den Nachbarfacetten belegt die Rundung.
    #
    # Zurückgegeben wird trotzdem nicht jede berührte Facette. Erst der
    # vollständige, gemeinsam eingepasste Mantel unten darf sie aus ``planar``
    # herausnehmen. Eine Deckfläche am Gewinde bleibt dadurch geschützt: Sie
    # kann eine Rundung berühren, ergibt aber keinen vollständigen Zylinder.
    # Auch eine breite Facette muss den vollständigen Rundträgernachweis
    # erfüllen. Ein kleines Teilstück darf ihren Rest nicht verschlucken.
    recoverable_facets = np.zeros(len(facets), dtype=bool)
    for number in np.flatnonzero(sizes >= MIN_FLAT_FACES).tolist():
        recoverable_facets[number] = bool(touches_curved[number]) or _a_sliver(
            body, [int(index) for index in facets[number]]
        )
    recoverable = set(members[recoverable_facets[owner]].tolist())
    if not recoverable or (requested is not None and requested.isdisjoint(recoverable)):
        return planar
    protected = planar - recoverable
    candidates = _all_but(len(body.faces), protected)
    mesh = MeshData.of(body)
    for patch in _connected_patches(body, candidates):
        if check_cancelled is not None:
            check_cancelled()
        if (
            len(patch) < MIN_PATCH_FACES
            or recoverable.isdisjoint(patch)
            or (requested is not None and requested.isdisjoint(patch))
        ):
            continue
        if check_patch_size is not None:
            check_patch_size(len(patch))
        if _a_sliver(body, patch):
            continue
        cone = fit_cone(body, patch, check_cancelled=check_cancelled)
        ball = fit_sphere(body, patch, check_cancelled=check_cancelled)
        round_surface = (
            cone is not None
            and cone.good
            and _cone_is_recognisable(body, cone, patch, check_cancelled=check_cancelled)
            and not _a_ball_fits_far_better(cone, ball)
        ) or (
            ball is not None
            and ball.good
            and _sphere_is_recognisable(body, ball, patch, check_cancelled=check_cancelled)
        )
        if not round_surface:
            cylinder = fit_cylinder(body, patch, check_cancelled=check_cancelled)
            round_surface = (
                cylinder is not None
                and cylinder.good
                and _fits_in_the_body(mesh, cylinder)
                and angular_span(body, cylinder, patch) >= FULL_TURN_SPAN
            )
        if not round_surface:
            ring = fit_torus(body, patch, check_cancelled=check_cancelled)
            round_surface = (
                ring is not None
                and ring.good
                and _torus_is_recognisable(body, ring, patch, check_cancelled=check_cancelled)
            )
        if round_surface:
            planar.difference_update(patch)
    return planar


def _patch_axial_midpoint(body: trimesh.Trimesh, patch: list[int], axis: np.ndarray) -> float:
    """Die Mitte der echten Patch-Ausdehnung entlang einer Achse.

    Dreiecksschwerpunkte gewichten dicht unterteilte Bereiche stärker. Die
    Endpunkte beschreiben dagegen dieselbe Zylinderlage unabhängig davon, wie
    viele Ringe dazwischen trianguliert wurden.
    """
    indices = np.unique(np.asarray(body.faces)[patch])
    positions = np.asarray(body.vertices)[indices] @ axis
    return float((positions.min() + positions.max()) / 2.0)


def _chord_sag(body: trimesh.Trimesh, patch: list[int], axis: np.ndarray) -> float:
    """Die Sehnenhöhe der Polygonnäherung dieses Flecks, in Millimetern.

    Ein Netz hat keinen Kreis, es hat ein Vieleck. Zwischen beiden liegt genau
    dieser Betrag: der Abstand von der Mitte einer Sehne zu dem Bogen, den sie
    abkürzt. Er ist die Auflösung, mit der dieser Fleck eine Rundung überhaupt
    beschreiben kann, und damit der Maßstab für :attr:`CylinderFit.spread`.

    Gemessen wird er aus zwei Größen, die eine **Unterteilung nicht ändert** —
    darauf kommt es an, denn die Sehnenhöhe ist eine Eigenschaft der Form und
    nicht der Dreiecke darauf:

    * dem Winkelschritt zwischen benachbarten Facetten. Die Normalen werden um
      die Achse sortiert; jeder Sprung über :data:`FLAT_ANGLE` trennt zwei
      Facetten, alles darunter ist dieselbe Ebene. Eine Unterteilung legt neue
      Dreiecke **in** eine vorhandene Facette und erzeugt keine neue Richtung.
    * der Breite einer Facette, als ihre Fläche geteilt durch die Länge des
      Flecks entlang der Achse. Auch das ist unterteilungsfest: Die Summe der
      Dreiecksflächen bleibt, und die Länge wird aus den äußersten Ecken
      genommen.

    Beides über den **Median**, nicht das Mittel: Ein Fleck, der neben der
    Rundung noch eine Ebene mitgenommen hat, trägt eine Facette, die zehnmal so
    breit ist wie die anderen — und genau dieser Fleck ist der Fall, den
    ``spread`` fangen soll. Er darf seinen eigenen Maßstab nicht aufblähen.

    Aus Sehnenlänge ``w`` und Schritt ``a`` folgt die Höhe geometrisch:
    ``w = 2r·sin(a/2)`` und ``sag = r·(1 - cos(a/2))``, zusammen also
    ``sag = (w/2)·tan(a/4)`` — ohne den Radius, der ja gerade in Frage steht.

    **Null heißt „nicht messbar", nicht „perfekt".** Der Maßstab gilt nur für
    einen Fleck, der wirklich ein Vieleck um diese Achse ist, und drei Fälle
    sind es nicht: einer ohne Sprung über :data:`FLAT_ANGLE` — dann ist sein
    Schritt jedenfalls kleiner als der, und seine Sehnenhöhe liegt unter der
    Grenze, die der Aufrufer ohnehin setzt —, einer ohne Ausdehnung entlang
    der Achse, und einer, dessen Normalen nicht senkrecht auf ihr stehen.

    **Der dritte ist der gefährliche.** Ein Fleck, der sich auch *längs* der
    Achse wölbt, weicht in einer Richtung ab, die quer dazu gemessen gar nicht
    vorkommt — sein Maßstab käme zu groß heraus und entschuldigte damit die
    Abweichung, die er messen soll. Gemessen an einem Ring Ø 34 mit R 0,5
    (17.09.2026): Der Zylinderfit über sein Band meldete r = 17,37 und eine
    Sehnenhöhe von 0,045 mm, vierzehnmal die eines Mantels gleicher Teilung,
    und die Streuung fiel von 6,2 auf 1,4 — der Ring stand danach als Bohrung
    und Zapfen im Baum statt als Torus. Dieselbe Falle beim Viertelbogen aus
    ``test_the_residual_cannot_see_a_blown_up_circle``, dessen Fleck zur Hälfte
    aus Deckeldreiecken besteht: Die eingepasste Achse liegt dort quer zum
    Zylinder, und was sie an Sehnenhöhe sieht, hat mit der Rundung nichts zu
    tun. :data:`~app.core.units.UPRIGHT_TO_AXIS` ist dieselbe Grenze, an der
    die Erkennung sonst Deckel von Mantel trennt.
    """
    chosen = np.asarray(patch)
    basis_u, basis_v = _plane_basis(axis)
    normals = np.asarray(body.face_normals[chosen], dtype=float)
    if float(np.mean(np.abs(normals @ axis))) > UPRIGHT_TO_AXIS:
        return 0.0
    angles = np.arctan2(normals @ basis_v, normals @ basis_u)
    order = np.argsort(angles)
    steps = np.diff(angles[order])
    breaks = np.flatnonzero(steps > math.radians(FLAT_ANGLE))
    if not len(breaks):
        return 0.0
    low, high = _axial_span(body, patch, (float(axis[0]), float(axis[1]), float(axis[2])))
    if high - low <= EPS_GEOM:
        return 0.0
    facets = np.add.reduceat(
        np.asarray(body.area_faces, dtype=float)[chosen][order],
        np.concatenate([[0], breaks + 1]),
    )
    width = float(np.median(facets)) / (high - low)
    return (width / 2.0) * float(np.tan(float(np.median(steps[breaks])) / 4.0))


def _cylinder_contour(
    flat: np.ndarray,
    tolerance: float,
    check_cancelled: Callable[[], None] | None,
) -> np.ndarray | None:
    """Prüft die projizierte Originalhaut und entfernt Sehnenunterteilungen.

    GEOS liefert die konvexe Hülle ohne Qhulls temporäre Dateien. Ihre
    Vereinfachung hält Originalecken, erzeugt aber keine neue Geometrie.
    Auch der zyklische Anfangspunkt wird auf Kollinearität geprüft: Bleibt
    dort ein Sehnenmittelpunkt stehen, würde er den Kreisradius verkürzen.
    Alle ursprünglichen Punkte müssen auf der belegten Kontur bleiben;
    eine Hülle allein könnte Einbuchtungen verstecken.
    """
    from shapely import distance
    from shapely import points as planar_points
    from shapely.geometry import MultiPoint, Polygon

    if check_cancelled is not None:
        check_cancelled()
    hull = MultiPoint(flat).convex_hull
    if hull.geom_type != "Polygon":
        return None
    outline = np.asarray(hull.exterior.coords, dtype=float)[:-1]
    # Douglas-Peucker hält den Anfang eines geschlossenen Rings fest. Zuerst
    # müssen deshalb alle numerisch geraden Hüllpunkte verschwinden. Nach
    # der Vereinfachung könnten ihre echten Nachbarn schon entfernt sein,
    # sodass ein zuvor gerader Sehnenpunkt selbst eine Ecke vortäuscht.
    while len(outline) > 3:
        if check_cancelled is not None:
            check_cancelled()
        before = outline - np.roll(outline, 1, axis=0)
        after = np.roll(outline, -1, axis=0) - outline
        lengths = np.linalg.norm(before, axis=1) * np.linalg.norm(after, axis=1)
        cosine = np.einsum("ij,ij->i", before, after) / np.maximum(lengths, EPS_GEOM**2)
        candidates = np.flatnonzero(cosine >= units.exact_cos_degrees(FLAT_ANGLE))
        if not len(candidates):
            break
        outline = np.delete(outline, int(candidates[np.argmax(cosine[candidates])]), axis=0)
    # Drei Punkte bestimmen schon den Kreis; eine vierte Originalecke muss
    # ihn unabhängig tragen. Zwei ebene Streifen sind noch keine Rundung.
    if len(outline) < 4:
        return None
    outline = np.asarray(Polygon(outline).simplify(tolerance).exterior.coords, dtype=float)[:-1]
    boundary = Polygon(outline).exterior
    for start in range(0, len(flat), FIT_SCAN_BLOCK):
        if check_cancelled is not None:
            check_cancelled()
        away = distance(planar_points(flat[start : start + FIT_SCAN_BLOCK]), boundary)
        if float(np.max(away)) > tolerance:
            return None
    return outline


def _cylinder_band(
    triangles: np.ndarray,
    check_cancelled: Callable[[], None] | None,
) -> tuple[float, float]:
    """Radiales Netzband aus echten Dreiecken in der Ebene quer zur Achse.

    Das Minimum liegt auf einer Kante oder bei null im Dreiecksinneren;
    das Maximum liegt immer an einer Ecke. Eine fehlende Mantelpartie wird
    dabei nicht durch die Schließsehne einer konvexen Hülle ersetzt.
    """
    minimum, maximum = math.inf, 0.0
    for start in range(0, len(triangles), FIT_SCAN_BLOCK):
        if check_cancelled is not None:
            check_cancelled()
        points = triangles[start : start + FIT_SCAN_BLOCK]
        ends = np.roll(points, -1, axis=1)
        vectors = ends - points
        squares = np.einsum("ijk,ijk->ij", vectors, vectors)
        along = np.clip(
            -np.einsum("ijk,ijk->ij", points, vectors) / np.maximum(squares, EPS_GEOM**2),
            0.0,
            1.0,
        )
        closest = points + along[:, :, None] * vectors
        distances = np.linalg.norm(closest, axis=2).min(axis=1)
        # Nur ein flächiges projiziertes Dreieck kann die Achse im Inneren
        # tragen. Ein kollinearer Mantelstreifen hat ansonsten überall null
        # Kreuzprodukt und würde fälschlich einen Radius von null erhalten.
        cross = points[:, :, 0] * ends[:, :, 1] - points[:, :, 1] * ends[:, :, 0]
        nonzero = np.abs(cross.sum(axis=1)) > EPS_GEOM**2
        inside = nonzero & (np.all(cross >= 0.0, axis=1) | np.all(cross <= 0.0, axis=1))
        distances[inside] = 0.0
        minimum = min(minimum, float(distances.min()))
        maximum = max(maximum, float(np.linalg.norm(points, axis=2).max()))
    return minimum, maximum


def fit_cylinder(
    body: trimesh.Trimesh,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> CylinderFit | None:
    """Ein Kreis durch geprüfte Konturecken, mit separat gemessenem Netzband.

    Die Achse minimiert das flächengewichtete Normalenmoment. Axiale Ringe
    und Dreiecksdiagonalen erhalten damit dieselbe Bedeutung. Weltkoordinaten
    werden vor Projektion und quadratischen Termen zentriert. Der Fit belegt
    eine Kreisnäherung der Haut, keine unbekannte Konstruktionsabsicht.
    """
    result: CylinderFit | None = remembered(
        "fit_cylinder",
        body,
        patch,
        lambda: _fit_cylinder_read(body, patch, check_cancelled=check_cancelled),
        check_cancelled=check_cancelled,
    )
    return result


def _fit_cylinder_read(
    body: trimesh.Trimesh,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> CylinderFit | None:
    """Der Rumpf von :func:`fit_cylinder` — die Antwort merkt sich die Hülle."""
    support = _surface_support(body, patch, check_cancelled)
    if support is None:
        return None
    normals, areas = support.normals, support.areas
    _values, vectors = np.linalg.eigh(normals.T @ (normals * areas[:, None]))
    axis = vectors[:, 0]
    axis = np.asarray(positive_axis((float(axis[0]), float(axis[1]), float(axis[2]))), dtype=float)
    if np.max(np.abs(normals @ axis)) > UPRIGHT_TO_AXIS:
        return None
    first, second = _plane_basis(axis)
    # Drei nicht kollineare Punkte tragen stets einen Umkreis. Erst mehrere
    # aufgelöste, glatte Normalenwechsel belegen eine Rundung statt eines
    # absichtlichen Vielecks. Die vorhandenen Winkelgrenzen bleiben dieselben.
    angles = np.sort(np.arctan2(normals @ second, normals @ first))
    steps = np.diff(np.r_[angles, angles[0] + math.tau])
    # FLAT_ANGLE gilt der gesamten aufgelösten Krümmung, nicht dem einzelnen
    # Facettenschritt: Ein 1024-Eck hat kleinere Schritte und bleibt rund.
    if math.tau - steps.max() < math.radians(FLAT_ANGLE) or np.sort(steps)[-2] >= math.radians(
        CURVATURE_LIMIT - EPS_ANGLE
    ):
        return None
    points, reverse = support.points, support.corners
    origin = (points.min(axis=0) + points.max(axis=0)) / 2.0
    relative = points - origin
    flat = np.column_stack((relative @ first, relative @ second))
    tolerance = max(weld_tolerance(float(np.linalg.norm(body.extents))), ROUND_WALL_TOLERANCE)
    outline = _cylinder_contour(flat, tolerance, check_cancelled)
    if outline is None:
        return None
    # Ein Schnitt kann einen Mantel mitten in einer Facette begrenzen. Seine
    # Endpunkte sind dann Ecken der Hülle, aber keine Ecken des ursprünglichen
    # Kreisvielecks. Nur Punkte mit zwei verschiedenen Mantelnormalen tragen
    # das Kreismaß. Getrennte, deckungsgleiche STL-Ecken zählen gemeinsam.
    supported = support.ridges
    # Die äußere Hülle kann ausschließlich neue Schnittpunkte enthalten,
    # während die ursprünglichen Kreisecken knapp darunter liegen. Deshalb
    # tragen die belegten Ecken eine eigene Kontur; die gesamte Originalhaut
    # wurde oben unabhängig davon geprüft.
    outline = _cylinder_contour(flat[supported], tolerance, check_cancelled)
    if outline is None:
        return None
    circle, radius = _fit_circle(outline)
    if not math.isfinite(radius) or radius <= tolerance:
        return None
    errors = np.abs(np.linalg.norm(outline - circle, axis=1) - radius)
    error = float(np.abs(np.linalg.norm(flat[supported] - circle, axis=1) - radius).max())
    if error > tolerance:
        return None
    radial_triangles = (flat - circle)[reverse].reshape(-1, 3, 2)
    radial_centres = radial_triangles.mean(axis=1)
    radial_normals = np.column_stack((normals @ first, normals @ second))
    signs = np.einsum("ij,ij->i", radial_centres, radial_normals)
    if not (np.all(signs > EPS_GEOM) or np.all(signs < -EPS_GEOM)):
        return None
    inward = bool(np.all(signs < 0.0))
    radial_min, radial_max = _cylinder_band(radial_triangles, check_cancelled)
    # Auch ungestützte Schnittendpunkte gehören zur geprüften Haut. Lange
    # Tangentenflanken können denselben Bogen tragen, reichen aber aus seinem
    # Umkreis heraus und sind deshalb kein Bestandteil des Zylinders.
    if radial_max > radius + tolerance:
        return None
    along = relative @ axis
    centre = (
        origin + first * circle[0] + second * circle[1] + axis * ((along.min() + along.max()) / 2.0)
    )
    sag = max(_chord_sag(body, patch, axis), ROUND_WALL_TOLERANCE)
    if check_cancelled is not None:
        check_cancelled()
    return CylinderFit(
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        centre=(float(centre[0]), float(centre[1]), float(centre[2])),
        radius=radius,
        residual=float(errors.mean()) / radius,
        inward=inward,
        spread=float(errors.mean()) / sag,
        fit_error=error,
        radial_min=radial_min,
        radial_max=radial_max,
    )


def radial_cylinder(
    body: trimesh.Trimesh,
    fit: CylinderFit,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> CylinderFit | None:
    """Derselbe Konturfit mit der zusätzlichen Grenze der radialen Bearbeitung.

    Mindestens ein halber Mantel und die strengere Querstellung seiner
    Normalen schließen einen gewöhnlichen Übergang zwischen Tangentialebenen
    aus. Auch ein extern aufgebauter Kandidat ersetzt den Formnachweis nicht.
    """
    refined = fit_cylinder(body, patch, check_cancelled=check_cancelled)
    if refined is None or not refined.good:
        return None
    axis = np.asarray(refined.axis, dtype=float)
    if np.max(np.abs(np.asarray(body.face_normals)[patch] @ axis)) > ACROSS_THE_AXIS:
        return None
    if angular_span(body, refined, patch) < 180.0 - EPS_GEOM:
        return None
    return refined if _radial_boundaries_are_planar(body, axis, patch, check_cancelled) else None


def _radial_boundaries_are_planar(
    body: trimesh.Trimesh,
    axis: np.ndarray,
    patch: list[int],
    check_cancelled: Callable[[], None] | None,
) -> bool:
    """Der vollständige Mantel endet an axialen Seiten und ebenen Trimmkurven.

    Der Krümmungssplit kann eine Delle aus einer ansonsten runden Wand
    heraustrennen. Deren Rest bleibt ein messbarer Zylinder, aber seine
    ausgezackte Grenze belegt keine vollständige radial bearbeitbare Wand.
    Tangentiale Nachbarflächen werden weiterhin separat ausgewiesen.
    """
    if check_cancelled is not None:
        check_cancelled()
    adjacency = np.asarray(body.face_adjacency)
    within = adjacency[np.isin(adjacency, patch).all(axis=1)]
    if (
        len(
            trimesh.graph.connected_components(
                within, nodes=np.asarray(patch), min_len=1, engine="scipy"
            )
        )
        != 1
    ):
        return False
    faces = np.asarray(body.faces)[patch]
    edges = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges, count = unique_edges(edges, return_counts=True)
    if (count > 2).any():
        return False
    boundary = edges[count == 1]
    if not len(boundary):
        return False
    points = np.asarray(body.vertices)
    vectors = points[boundary[:, 1]] - points[boundary[:, 0]]
    tolerance = max(weld_tolerance(float(np.linalg.norm(body.extents))), ROUND_WALL_TOLERANCE)
    along = vectors @ axis
    # Die Längengrenze allein würde kurze unterteilte Ringkanten für axiale
    # Seiten halten. Richtung und radialer Abstand müssen beide passen.
    axial = (np.abs(along) >= PARALLEL_AXES * np.linalg.norm(vectors, axis=1)) & (
        np.linalg.norm(vectors - np.outer(along, axis), axis=1) <= tolerance
    )
    transverse = boundary[~axial]
    if not len(transverse):
        return False
    groups = trimesh.graph.connected_components(
        transverse, nodes=np.unique(transverse), min_len=1, engine="scipy"
    )
    for group in groups:
        if check_cancelled is not None:
            check_cancelled()
        relative = points[group] - points[group].mean(axis=0)
        if len(relative) < 4:
            continue
        _left, _singular, directions = np.linalg.svd(relative, full_matrices=False)
        if np.max(np.abs(relative @ directions[-1])) > tolerance:
            return False
    return True


def _round_measures(fit: ConeFit | SphereFit | TorusFit) -> dict[str, float]:
    """Nur tatsächlich berechnete Stützpunktfehler ausgeben, nie einen Nullersatz."""
    return {} if fit.fit_error is None else {"fit_error": fit.fit_error}


def _cylinder_measures(fit: CylinderFit) -> dict[str, float]:
    """Nur tatsächlich erhobene Diagnosemaße werden am Merkmal veröffentlicht."""
    return {
        name: value
        for name in ("fit_error", "radial_min", "radial_max")
        if (value := getattr(fit, name)) is not None
    }


def fit_stadium(
    body: trimesh.Trimesh, patch: list[int], *, direction_hint: Vec3 | None = None
) -> StadiumFit | None:
    """Ein Stadion durch einen Fleck: zwei Halbkreise über einer Strecke.

    Dieselbe Bauart wie :func:`fit_cylinder` — die Achse ist der Eigenvektor
    der Normalen mit dem kleinsten Eigenwert, gemessen wird in der Projektion
    senkrecht dazu —, nur dass nicht ein Kreis eingepasst wird, sondern die
    Kontur eines Langlochs. Drei Schritte, keine Iteration (§11.3):

    **Das Prisma.** Jede Normale des Flecks muss quer zur Achse stehen — ein
    Deckel, eine Fase, eine Kalotte im Fleck sind keine Wand des Lochs, und
    mit ihnen ist es kein Stadion. Dieselbe Maske wie in
    :mod:`app.core.perceive.slots` (``ACROSS_THE_AXIS``).

    **Die Mittellinie.** In der Projektion liegen die Ecken auf einem Stadion,
    und das ist in genau einer Richtung länger als quer dazu: die Hauptachse
    der Punktwolke. Ihre Ausdehnung quer ist der Durchmesser, längs die
    Gesamtlänge; die Differenz ist der Weg zwischen den Bogenmitten.

    **Der Rückstand** vergleicht jede Ecke mit der Kontur: über der Strecke
    mit dem Abstand zur Mittellinie, an den Enden mit dem Abstand zum
    näheren Bogenmittelpunkt. Ein Kreis bekommt hier einen Weg von null und
    ist keines; ein Sechseck oder eine verrundete Tasche liegen an den Enden
    neben dem Bogen und fallen über den Rückstand heraus.

    Gerechnet wird an den **Ecken**, nicht an den Dreiecksschwerpunkten wie
    beim Zylinder: Der Schwerpunkt einer Bogenfacette liegt um die Sehnenhöhe
    innerhalb der Kontur, die Ecke liegt darauf — und bei einem Weg von einer
    Sehnenbreite ist das der Unterschied zwischen Form und Rauschen.

    Eine bereits belegte Flankenrichtung darf die Scheitelsuche ersetzen.
    An groben Bögen liegen deren äußerste Netzecken neben dem Scheitel;
    ihre Verbindung kippt dann gegen die tatsächlichen parallelen Flanken.
    """
    normals = np.asarray(body.face_normals[patch], dtype=float)
    _values, vectors = np.linalg.eigh(normals.T @ normals)
    axis = vectors[:, 0]
    axis = axis / float(np.linalg.norm(axis))
    axis = np.asarray(positive_axis((float(axis[0]), float(axis[1]), float(axis[2]))), dtype=float)
    if float(np.abs(normals @ axis).max()) >= ACROSS_THE_AXIS:
        return None

    corners = np.asarray(body.triangles[patch], dtype=float).reshape(-1, 3)
    basis_u, basis_v = _plane_basis(axis)
    flat = np.column_stack([corners @ basis_u, corners @ basis_v])
    mean = flat.mean(axis=0)
    centred = flat - mean
    # **Die Mittellinie ist die Richtung der größten Ausdehnung — und nicht
    # die Hauptachse der Punktwolke.** Ein Stadion mit zwei Prozent Weg ist
    # fast ein Kreis; seine Kovarianz ist fast isotrop, und wo die Ecken
    # dichter liegen (auf den Bögen) und wo nicht (auf den zwei Flanken),
    # entscheidet dann über den Eigenvektor. Gemessen an Ø 40 mit 0,8 mm Weg:
    # Die Hauptachse zeigte quer, der Weg kam negativ heraus, das Loch war
    # keines. Die Ausdehnung dagegen ist in genau einer Richtung um den Weg
    # größer — grob über einen halben Kreis gesucht, dann exakt aus den zwei
    # Scheiteln, die dort ganz außen liegen.
    if direction_hint is None:
        angles = np.linspace(0.0, np.pi, STADIUM_SWEEP, endpoint=False)
        sweep = np.column_stack([np.cos(angles), np.sin(angles)])
        projected = centred @ sweep.T
        widest = int(np.argmax(projected.max(axis=0) - projected.min(axis=0)))
        apex_a = centred[int(np.argmax(projected[:, widest]))]
        apex_b = centred[int(np.argmin(projected[:, widest]))]
        chord = apex_a - apex_b
    else:
        hint = np.asarray(direction_hint, dtype=float)
        chord = np.array([hint @ basis_u, hint @ basis_v])
    if float(np.linalg.norm(chord)) <= EPS_GEOM:
        return None
    along_2d = chord / float(np.linalg.norm(chord))
    across_2d = np.array([-along_2d[1], along_2d[0]])
    along = centred @ along_2d
    across = centred @ across_2d
    radius = float(across.max() - across.min()) / 2.0
    half_length = float(along.max() - along.min()) / 2.0
    if radius <= EPS_GEOM:
        return None
    travel = 2.0 * (half_length - radius)
    if travel <= EPS_GEOM:
        return None
    middle_2d = (
        float(along.max() + along.min()) / 2.0,
        float(across.max() + across.min()) / 2.0,
    )
    along = along - middle_2d[0]
    across = across - middle_2d[1]

    over_the_line = np.abs(along) <= travel / 2.0
    to_the_arc = np.hypot(np.abs(along) - travel / 2.0, across)
    distance = np.where(over_the_line, np.abs(np.abs(across) - radius), np.abs(to_the_arc - radius))
    residual = float(np.mean(distance) / radius)
    # Der Mittelwert darf örtliche Rastmulden nicht zu einem Stadion glätten.
    # Auch dessen schlechteste Ecke muss die zugesagte Kontur einhalten.
    if float(distance.max()) > radius * STADIUM_TOLERANCE:
        return None

    depth_along = corners @ axis
    depth = float(depth_along.max() - depth_along.min())
    centre_flat = mean + middle_2d[0] * along_2d + middle_2d[1] * across_2d
    centre = (
        basis_u * centre_flat[0]
        + basis_v * centre_flat[1]
        + axis * float(depth_along.max() + depth_along.min()) / 2.0
    )
    direction = basis_u * along_2d[0] + basis_v * along_2d[1]

    # Nach innen gewölbt, wie beim Zylinder: Die Normalen zeigen zur
    # Mittellinie hin — gemessen am nächsten Punkt der Strecke, nicht an der
    # Mitte, sonst zeigte an einem langen Loch die halbe Wand daran vorbei.
    centres = np.asarray(body.triangles_center[patch], dtype=float)
    relative = centres - centre
    span = np.clip(relative @ direction, -travel / 2.0, travel / 2.0)
    nearest = centre + np.outer(span, direction)
    towards = nearest - centres
    towards = towards - np.outer(towards @ axis, axis)
    inward = bool(np.mean(np.einsum("ij,ij->i", normals, towards)) > 0)

    return StadiumFit(
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        centre=(float(centre[0]), float(centre[1]), float(centre[2])),
        direction=(float(direction[0]), float(direction[1]), float(direction[2])),
        radius=radius,
        travel=travel,
        depth=depth,
        residual=residual,
        inward=inward,
    )


class _SurfaceSupport(NamedTuple):
    """Private Lesezuordnung zwischen Netzpunkten und ihren Mantelfacetten."""

    points: np.ndarray
    corners: np.ndarray
    normals: np.ndarray
    centres: np.ndarray
    areas: np.ndarray
    round_corners: np.ndarray
    ridges: np.ndarray
    directions: np.ndarray


def _one_vertex_fan(
    points: np.ndarray,
    vertex: int,
    neighbours: np.ndarray,
    check_cancelled: Callable[[], None] | None,
) -> bool:
    """Die Kantenstrahlen eines Punkts müssen einen gemeinsamen Flächenfächer tragen."""

    def connected(edges: np.ndarray) -> bool:
        """Der Link des Eckpunkts ist ein zusammenhängender Graph seiner Nachbarn."""
        graph: dict[int, list[int]] = {}
        for index, (first, second) in enumerate(edges):
            if check_cancelled is not None and index % FIT_SCAN_BLOCK == 0:
                check_cancelled()
            graph.setdefault(int(first), []).append(int(second))
            graph.setdefault(int(second), []).append(int(first))
        seen = {int(edges[0, 0])}
        pending = list(seen)
        while pending:
            if check_cancelled is not None and len(seen) % FIT_SCAN_BLOCK == 0:
                check_cancelled()
            for neighbour in graph[pending.pop()]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    pending.append(neighbour)
        return len(seen) == len(graph)

    if connected(neighbours):
        return True
    # Eine T-Unterteilung speichert auf derselben alten Kante verschieden
    # lange Teilkanten. Ihre Strahlen sind gleich, auch wenn die Endpunkte
    # andere Indizes tragen. Nur im Leseindex verbinden, nicht verschweißen.
    unique = np.unique(neighbours)
    rays = points[unique] - points[vertex]
    lengths = np.linalg.norm(rays, axis=1)
    if np.any(lengths <= EPS_GEOM):
        return False
    if check_cancelled is not None:
        check_cancelled()
    close = cKDTree(rays / lengths[:, None]).query_pairs(
        2.0 * units.exact_sin_degrees(EPS_ANGLE / 2.0), output_type="ndarray"
    )
    return bool(len(close)) and connected(np.vstack((neighbours, unique[close])))


def _fan_arcs(body: trimesh.Trimesh, patch: Sequence[int], used: np.ndarray) -> np.ndarray | None:
    """Wie viele getrennte Bögen die Dreiecke des Flecks um jede benutzte Ecke legen.

    Dieselbe Frage wie ``connected`` in :func:`_one_vertex_fan`, für alle Ecken
    in einem Zug über den Fleck: Um eine Ecke liegen die Dreiecke des Flecks
    in Bögen, und ein Bogen aus ``k`` Dreiecken hat ``k - 1`` innere Kanten —
    Kanten, deren beide Dreiecke zum Fleck gehören. Die Zahl der Bögen ist
    also Dreiecke minus innere Kanten, und ein Fächer hängt zusammen, wenn es
    genau ein Bogen ist — oder null, wenn die Dreiecke um die Ecke einen
    geschlossenen Ring bilden, der so viele innere Kanten hat wie Dreiecke.

    **Gelesen wird der Fleck, nicht das Netz** (:func:`_neighbour_index`): Ein
    erster Anlauf maskierte je Fleck alle Dreiecke und alle Nähte des Netzes
    und war an 2 843 kleinen Flecken langsamer als die Komponentenrechnung,
    die er ablösen sollte (gemessen am 21.09.2026). An einer Kante mit drei
    Dreiecken kennt der Index keine Naht, die Bogenzahl fällt zu hoch aus, und
    die Ecke geht den Einzelweg — dort ist die Antwort dann wie bisher die des
    Graphen. Zurück kommt die Bogenzahl je Eintrag in ``used``; ``None``, wenn
    das Netz keine Nachbarschaft kennt.
    """
    neighbours, pair_rows = _neighbour_index(body)
    if not neighbours.shape[1]:
        return None
    indices = np.asarray(patch, dtype=np.int64)
    chosen = neighbours[indices]
    inner = chosen >= 0
    inner[inner] = np.isin(chosen[inner], indices)
    # Jede innere Kante steht zweimal da, einmal je Seite — halbiert statt
    # eindeutig gemacht: ``np.unique`` über eine Million Nähte kostete an der
    # Ikosphäre hundert Millisekunden, das Halbieren nichts.
    rows = pair_rows[indices][inner]
    edges = np.asarray(body.face_adjacency_edges, dtype=np.int64)[rows]
    corners = np.asarray(body.faces[indices], dtype=np.int64).ravel()
    triangles = np.bincount(corners, minlength=len(body.vertices))
    inner_edges = np.bincount(edges.ravel(), minlength=len(body.vertices)) // 2
    return np.asarray(triangles[used] - inner_edges[used], dtype=np.int64)


#: Die zuletzt gelesenen Stützpunkte je Netz und Fleck (:func:`_surface_support`).
#: Acht Fragen an denselben Fleck — Kugel, Kegel, Zylinder, große Facetten —
#: lasen die Ikosphäre mit 327 680 Dreiecken achtmal, je über eine Sekunde
#: (gemessen am 21.09.2026). Der Schlüssel ist die Identität des Netzes und
#: der Abdruck der Flächenliste; die Geometrie dahinter ist unveränderlich
#: (Regel 3). **Nicht der Datenhash des Netzes:** trimesh rechnet ihn bei
#: jeder Frage neu, 0,4 ms an 200 000 Dreiecken — an der Freiform mit 9 589
#: Fragen waren das vier Sekunden, mehr als die Lesungen selbst.
#:
#: **Und die Antworten eines Körpers gehen mit ihm** (:class:`_BodyMemory`).
#: Die erste Fassung hielt sie, bis die Grenze je Frage sie verdrängte — und
#: die Stützpunktlesung eines toten Körpers wiegt so viel wie sein Fleck:
#: Nach vier Ikosphären lagen 369 MiB an Antworten zu Netzen, die niemand
#: mehr hatte (gemessen am 21.09.2026). Jeder Körper führt deshalb die
#: Schlüssel, die er hier hinterlassen hat, und ein ``weakref.finalize``
#: räumt sie aus, sobald er stirbt — bevor seine Adresse an einen neuen
#: Körper gehen kann, denn CPython ruft den Abschied beim letzten Verweis
#: und die Speicherbereinigung ihn vor dem Freigeben.
_SUPPORT_CACHE: dict[str, OrderedDict[tuple[int, bytes, Any, int], Any]] = {}

#: Wie viele Antworten je Frage gehalten werden. Die Stützpunktlesung trägt
#: Felder in der Größe des Flecks — an der Ikosphäre dreißig Megabyte — und
#: wird je Fleck ein Dutzend Mal gefragt, nacheinander: acht reichen. Fits,
#: Nachweise und die Streifenprüfung sind klein und kommen zu Hunderten je
#: Erkennung; ein Fleck, der beim zweiten Durchgang schon vergessen wäre,
#: hätte den Merker umsonst gehabt (gemessen am 21.09.2026: 218 Streifen-
#: fragen an der Lochplatte verdrängten die Facettenantwort zwischen ihren
#: zwei Lesern). Die Grenzen gelten über alle Körper, damit auch viele
#: lebende Körper — der Ergebniscache hält bis zu zwanzig Millionen Dreiecke
#: — zusammen nicht mehr als acht Lesungen halten.
SUPPORT_CACHE_LIMIT = 8
CACHE_LIMIT_PER_QUESTION = 4096


#: Die zuletzt gebildeten Abdrücke je Listenobjekt — mit der Liste selbst als
#: Anker, damit ihre Identität nicht an eine andere Liste fallen kann.
_DIGESTS: OrderedDict[int, tuple[Sequence[int], bytes]] = OrderedDict()
DIGEST_LIMIT = 32


class _BodyMemory:
    """Was ein Körper in den Merkern hinterlassen hat — damit es mit ihm geht.

    ``answers`` nennt je gemerkter Antwort die Frage und den Schlüssel in
    :data:`_SUPPORT_CACHE`, ``digests`` die Listenabdrücke in :data:`_DIGESTS`.
    Beides sind Mengen, denn eine verdrängte und neu gerechnete Antwort trägt
    denselben Schlüssel. Der schwache Verweis sagt, ob hinter der Adresse noch
    derselbe Körper steht.
    """

    __slots__ = ("answers", "digests", "ref")

    def __init__(self, body: trimesh.Trimesh) -> None:
        self.ref: weakref.ref[Any] = weakref.ref(body)
        self.answers: set[tuple[str, tuple[int, bytes, Any, int]]] = set()
        self.digests: set[int] = set()


#: Je lebendem Körper sein Merker, unter seiner Adresse.
_MEMORIES: dict[int, _BodyMemory] = {}

#: **Ein Schloss um alle drei Merker.** Das Merkmalfenster fragt
#: ``fillet_blocked`` → ``detect_faces`` im Hauptfaden, während der Arbeiter
#: dasselbe Modul für die nächste Auswertung fragt; ``get`` und
#: ``move_to_end`` an einem ``OrderedDict`` sind zwei Schritte, und wer
#: dazwischen verdrängt wird, bekam einen ``KeyError``. Wiedereintrittsfähig,
#: weil der Abschied eines Körpers (:func:`_forget_body`) aus der
#: Speicherbereinigung heraus in jedem Faden und an jeder Zuweisung laufen
#: kann — auch innerhalb des gehaltenen Schlosses.
_MEMORY_LOCK = threading.RLock()


def _memory_of(body: trimesh.Trimesh) -> _BodyMemory:
    """Der Merker eines Körpers, beim ersten Mal angelegt — mit dem Abschied im Gepäck.

    Nur mit gehaltenem :data:`_MEMORY_LOCK` aufrufen.
    """
    key = id(body)
    memory = _MEMORIES.get(key)
    if memory is not None and memory.ref() is body:
        return memory
    memory = _BodyMemory(body)
    _MEMORIES[key] = memory
    farewell = weakref.finalize(body, _forget_body, key, memory)
    # Beim Beenden des Prozesses gibt es nichts mehr aufzuräumen — und die
    # Modulvariablen sind dann womöglich schon abgebaut. (``atexit`` ist zur
    # Laufzeit eine Eigenschaft der Klasse; der Stub führt sie als Feld neben
    # leeren ``__slots__``, daher die Ausnahme für mypy.)
    farewell.atexit = False  # type: ignore[misc]
    return memory


def _forget_body(key: int, memory: _BodyMemory) -> None:
    """Der Abschied: Die Antworten eines gestorbenen Körpers gehen mit ihm."""
    with _MEMORY_LOCK:
        if _MEMORIES.get(key) is memory:
            del _MEMORIES[key]
        for name, answer_key in memory.answers:
            answers = _SUPPORT_CACHE.get(name)
            if answers is not None:
                answers.pop(answer_key, None)
        for digest_key in memory.digests:
            _DIGESTS.pop(digest_key, None)
        memory.answers.clear()
        memory.digests.clear()


def _patch_digest(memory: _BodyMemory, patch: Sequence[int]) -> bytes:
    """Der Abdruck einer Flächenliste — sechzehn Bytes für 327 680 Indizes in 7 ms.

    Dieselbe Liste wird je Erkennung zwei Dutzend Mal gefragt (Kegel, Zylinder,
    Kugel, Ring, Nachweise, Streifen), und jedes Mal kostete das Feld aus der
    Python-Liste fünf Millisekunden — an der Ikosphäre 140 ms für nichts. Der
    Abdruck bleibt deshalb am Listenobjekt gemerkt; die Liste wird dabei
    festgehalten, damit ihre Adresse nicht an eine neue Liste geht, und eine
    Fleckenliste ändert nach ihrer Bildung niemand. Gerechnet wird außerhalb
    des Schlosses — der Hauptfaden soll nicht auf ein Feld aus 327 680 Ecken
    warten.
    """
    key = id(patch)
    with _MEMORY_LOCK:
        known = _DIGESTS.get(key)
        if known is not None and known[0] is patch:
            _DIGESTS.move_to_end(key)
            return known[1]
    digest = hashlib.blake2b(np.asarray(patch, dtype=np.int64).tobytes(), digest_size=16).digest()
    with _MEMORY_LOCK:
        _DIGESTS[key] = (patch, digest)
        memory.digests.add(key)
        while len(_DIGESTS) > DIGEST_LIMIT:
            _DIGESTS.popitem(last=False)
    return digest


def remembered(
    name: str,
    body: trimesh.Trimesh,
    patch: Sequence[int],
    compute: Callable[[], Any],
    extra: Any = None,
    check_cancelled: Callable[[], None] | None = None,
) -> Any:
    """Dieselbe Frage an dasselbe Netz und denselben Fleck wird einmal beantwortet.

    ``classify`` fragt je Fleck Kegel, Zylinder, Kugel und Ring; die Nachweise
    dahinter und ``_large_facet_faces`` stellen dieselben Fragen noch einmal —
    an der Ikosphäre zwei Kegelfits mit je achtzig Residualauswertungen über
    160 000 Punkte (gemessen am 21.09.2026). Die Antworten sind reine
    Funktionen von Netz und Fleck (Regel 3: eine Eingabe ändert niemand);
    ``extra`` trägt, was die Frage sonst noch bestimmt, etwa den Fit, den ein
    Nachweis prüft. Gerechnet wird außerhalb des Schlosses; fragen zwei Fäden
    zugleich dasselbe, rechnen beide und legen dieselbe Antwort ab.
    """
    # **Ein abgebrochener Auftrag bekommt auch keine gemerkte Antwort.** Der
    # Abbruch gilt dem Auftrag, nicht der Rechnung; wer schon abgebrochen hat,
    # beginnt nichts — und liest auch nichts nach.
    if check_cancelled is not None:
        check_cancelled()
    with _MEMORY_LOCK:
        memory = _memory_of(body)
    # Das Löserbudget gehört zum Schlüssel: Ein Test setzt es auf eins und
    # fragt danach noch einmal mit dem vollen — zwei Fragen, zwei Antworten.
    key = (id(body), _patch_digest(memory, patch), extra, ROUND_FIT_EVALUATIONS)
    with _MEMORY_LOCK:
        answers = _SUPPORT_CACHE.setdefault(name, OrderedDict())
        if key in answers:
            answers.move_to_end(key)
            return answers[key]
    value = compute()
    with _MEMORY_LOCK:
        answers = _SUPPORT_CACHE.setdefault(name, OrderedDict())
        answers[key] = value
        memory.answers.add((name, key))
        limit = SUPPORT_CACHE_LIMIT if name == "support" else CACHE_LIMIT_PER_QUESTION
        while len(answers) > limit:
            answers.popitem(last=False)
    return value


def _surface_support(
    body: trimesh.Trimesh,
    patch: list[int],
    check_cancelled: Callable[[], None] | None = None,
) -> _SurfaceSupport | None:
    """Unveränderte Netzecken von Punkten auf Facetten und Sehnen unterscheiden.

    Drei verschiedene angrenzende Mantelnormalen belegen einen Netzeckpunkt.
    Unterteilung in einer Facette erzeugt nur eine Normale, an einer alten
    Kante höchstens zwei. Deckungsgleiche STL-Punkte teilen nur diesen Index;
    die ursprünglichen Dreiecke und Koordinaten bleiben unangetastet.
    """
    if check_cancelled is not None:
        check_cancelled()
    if len(patch) < MIN_PATCH_FACES:
        return None
    support: _SurfaceSupport | None = remembered(
        "support",
        body,
        patch,
        lambda: _read_surface_support(body, patch, check_cancelled),
        check_cancelled=check_cancelled,
    )
    return support


def _coincident_vertices(body: trimesh.Trimesh) -> bool:
    """Ob zwei Ecken des Netzes dieselben Koordinaten tragen — einmal je Körper.

    Eine ungeschweißte STL schreibt jedes Dreieck mit eigenen Ecken; dann
    fallen deckungsgleiche Punkte in der Lesung zusammen (:func:`_read_surface_support`).
    Ein geschweißtes Netz hat keine, und die Frage kostet einmal so viel wie
    eine Lesung des ganzen Körpers, nicht einmal je Fleck.
    """
    canonical = _canonical_vertices(body)
    return bool(int(canonical.max()) + 1 < len(canonical)) if len(canonical) else False


def _canonical_vertices(body: trimesh.Trimesh) -> np.ndarray:
    """Je Ecke die Nummer ihres Punkts — deckungsgleiche Ecken teilen sie.

    Die Nummern folgen der lexikographischen Ordnung der Koordinaten, also
    genau der Reihenfolge, die ``np.unique(vertices, axis=0)`` je Fleck
    lieferte. Einmal je Körper gerechnet statt einmal je Fleck: An der
    Schüssel mit 215 000 Dreiecken und deckungsgleichen Ecken sortierte jede
    der 443 Lesungen ihre Punkte als Zeilen (gemessen am 22.09.2026).
    """
    result: np.ndarray = remembered(
        "canonical_vertices",
        body,
        (),
        lambda: np.asarray(
            np.unique(np.asarray(body.vertices, dtype=float), axis=0, return_inverse=True)[1],
            dtype=np.int64,
        ).reshape(-1),
    )
    return result


def _fans_connected(
    points_count: int, vertex: np.ndarray, first: np.ndarray, second: np.ndarray
) -> np.ndarray:
    """Für viele Ecken auf einmal: Trägt der Link jeder Ecke einen zusammenhängenden Graphen?

    Dieselbe Frage wie ``connected`` in :func:`_one_vertex_fan`, gestellt an
    alle Ecken zugleich: Je Vorkommen einer Ecke ``vertex`` in einem Dreieck
    verbindet eine Kante dessen zwei andere Ecken ``first`` und ``second``.
    Alle Kanten aller Ecken bilden **einen** Graphen, in dem jeder Knoten
    ``(Ecke, Nachbar)`` heißt, und eine Ecke hängt zusammen, wenn ihre Knoten
    eine Komponente bilden. Der Einzelweg in Python kostete an der Schüssel
    368 217 Aufrufe und 5,8 der 21 Sekunden der Erkennung (22.09.2026).

    **Die Komponenten findet eine Markenweitergabe in NumPy**, kein
    ``scipy``-Graph: Jeder Knoten trägt zu Beginn seine eigene Nummer, jede
    Kante gibt die kleinere Nummer an beide Enden weiter, bis sich nichts
    mehr ändert. Ein Fächer ist ein Kreis oder Bogen aus wenigen Dreiecken,
    also braucht es so viele Runden wie der halbe Fächer lang ist — sieben
    an einer Ecke mit zwölf Dreiecken. Der Graph über ``coo_matrix`` und
    ``connected_components`` kostete je Aufruf zwei Millisekunden Aufbau,
    219-mal je Erkennung an der Schüssel, bei Flecken mit zwanzig Ecken.

    Zurück kommt je Ecke in ``np.unique(vertex)``-Reihenfolge, ob ihr Fächer
    zusammenhängt — die Ecken selbst gibt der Aufrufer über ``np.unique``.
    """
    owners = np.asarray(vertex, dtype=np.int64)
    keys = np.concatenate((owners * points_count + first, owners * points_count + second))
    nodes, numbered = np.unique(keys, return_inverse=True)
    numbered = numbered.reshape(-1)
    half = len(owners)
    left, right = numbered[:half], numbered[half:]
    labels = np.arange(len(nodes), dtype=np.int64)
    while True:
        lowest = np.minimum(labels[left], labels[right])
        before = labels.copy()
        np.minimum.at(labels, left, lowest)
        np.minimum.at(labels, right, lowest)
        if np.array_equal(labels, before):
            break
    node_owner = nodes // points_count
    # Je Ecke die Zahl ihrer Komponenten: verschiedene (Ecke, Marke)-Paare,
    # als eine Zahl kodiert — die Marke ist eine Knotennummer, also kleiner
    # als die Knotenzahl.
    pairs = np.unique(node_owner * len(nodes) + labels)
    seen_owners, counts = np.unique(pairs // len(nodes), return_counts=True)
    ordered = np.unique(owners)
    connected = np.ones(len(ordered), dtype=bool)
    connected[np.searchsorted(ordered, seen_owners)] = counts == 1
    return connected


def _read_surface_support(
    body: trimesh.Trimesh,
    patch: list[int],
    check_cancelled: Callable[[], None] | None,
) -> _SurfaceSupport | None:
    """Die Lesung selbst — :func:`_surface_support` merkt sie sich."""
    triangles = np.asarray(body.triangles[patch], dtype=float)
    normals = np.asarray(body.face_normals[patch], dtype=float)
    areas = np.asarray(body.area_faces[patch], dtype=float)
    if (
        not np.isfinite(triangles).all()
        or not np.isfinite(normals).all()
        or not np.isfinite(areas).all()
        or areas.sum() <= EPS_GEOM**2
    ):
        return None
    # **Erst die Ecken des Netzes, dann die deckungsgleichen darunter.** Die
    # Eindeutigkeit der Koordinaten über alle 3n Dreiecksecken sortierte an
    # der Ikosphäre mit 327 680 Dreiecken 983 040 Zeilen; die Ecken, die das
    # Netz selbst kennt, sind ein Sechstel davon, und deckungsgleiche
    # STL-Punkte fallen unter ihnen genauso zusammen. Das Ergebnis ist
    # dasselbe sortierte Punktfeld mit derselben Zuordnung.
    # Die benutzten Ecken ohne Sortierung: Markieren, zählen, umnummerieren —
    # an der Ikosphäre zehn statt fünfzig Millisekunden für 983 040 Ecken.
    flat_corners = np.asarray(body.faces[patch], dtype=np.int64).ravel()
    present = np.zeros(len(body.vertices), dtype=bool)
    present[flat_corners] = True
    used = np.flatnonzero(present)
    renumbered = np.full(len(body.vertices), -1, dtype=np.int64)
    renumbered[used] = np.arange(len(used))
    corner_of = renumbered[flat_corners]
    all_vertices = np.asarray(body.vertices, dtype=float)
    if _coincident_vertices(body):
        # Über die Punktnummern des Körpers, nicht über die Koordinaten des
        # Flecks: dieselben Punkte in derselben Reihenfolge, ohne je Fleck
        # Zeilen zu sortieren (:func:`_canonical_vertices`).
        canonical = _canonical_vertices(body)
        distinct, vertex_of = np.unique(canonical[used], return_inverse=True)
        representative = np.full(int(canonical.max()) + 1, -1, dtype=np.int64)
        representative[canonical[used][::-1]] = used[::-1]
        points = all_vertices[representative[distinct]]
    else:
        # **Ohne deckungsgleiche Ecken ist jede Ecke ihr eigener Punkt** — die
        # Sortierung der Koordinaten je Fleck entfällt; sie kostete an 2 843
        # kleinen Flecken so viel wie die Lesung selbst (gemessen 21.09.2026).
        points = all_vertices[used]
        vertex_of = np.arange(len(used))
    reverse = vertex_of.ravel()[corner_of.ravel()]
    corners = reverse.reshape(-1, 3)
    repeated = np.repeat(normals, 3, axis=0)
    occurrence = np.arange(len(reverse))
    first_index = np.full(len(points), len(reverse), dtype=np.intp)
    np.minimum.at(first_index, reverse, occurrence)
    first = repeated[first_index]
    agreement = np.einsum("ij,ij->i", repeated, first[reverse])
    lowest = np.full(len(points), math.inf)
    np.minimum.at(lowest, reverse, agreement)
    second_index = np.full(len(points), len(reverse), dtype=np.intp)
    furthest = agreement <= lowest[reverse]
    np.minimum.at(second_index, reverse[furthest], occurrence[furthest])
    second = repeated[second_index]
    limit = units.exact_cos_degrees(EPS_ANGLE)
    # Gegenläufige Häute am selben Punkt sind keine weiteren Mantelfacetten.
    # Sie würden aus einem Sehnenpunkt mit zwei Ebenen eine vermeintliche
    # ursprüngliche Netzecke machen. Ein kohärenter Rundträger besitzt an
    # einem Punkt keine zwei entgegengesetzten orientierten Tangentialebenen.
    if np.any(lowest < -limit):
        return None
    ridges = lowest < limit
    third = (agreement < limit) & (np.einsum("ij,ij->i", repeated, second[reverse]) < limit)
    round_corners = np.zeros(len(points), dtype=bool)
    np.logical_or.at(round_corners, reverse, third)
    order = np.argsort(reverse, kind="stable")
    offsets = np.r_[0, np.cumsum(np.bincount(reverse, minlength=len(points)))]
    # **Alle Fächer auf einmal, die Einzelprüfung nur für die zerrissenen.**
    # Je Netzecke in Python zu fragen, ob ihr Fächer zusammenhängt, kostete an
    # der Ikosphäre mit 327 680 Dreiecken 1,3 Millionen Aufrufe und 37 der 39
    # Sekunden der Erkennung (gemessen am 21.09.2026 gegen das Ziel von einer
    # Sekunde aus §31). An einem geschlossenen Netz hängt jeder Fächer
    # zusammen; die Ausnahme — T-Unterteilungen, doppelte Punkte — verdient
    # den teuren Weg, die Regel nicht.
    # **Und an einem geschlossenen Netz hängt jeder innere Fächer zusammen.**
    # Eine Ecke, deren sämtliche Dreiecke im Fleck liegen, trägt an einem
    # wasserdichten, gleich orientierten Netz genau einen Ring — die Frage
    # stellt sich nur am Rand des Flecks, wo der Ring angeschnitten ist, und
    # bei zusammengelegten deckungsgleichen Punkten, deren Ring das Netz
    # nicht kennt. An der Ikosphäre ist der Fleck das ganze Netz: keine Ecke
    # am Rand, keine Frage (gemessen am 21.09.2026: 0,5 s je Lesung).
    torn = ridges.copy()
    if len(points) == len(used):
        # Ohne zusammengelegte deckungsgleiche Punkte ist jede Ecke genau eine
        # Netzecke, und die Bogenzahl aus der Nachbarschaft beantwortet die
        # Frage für alle auf einmal; nur wer mehr als einen Bogen trägt, geht
        # den Einzelweg mit dem Strahlenvergleich.
        if check_cancelled is not None:
            check_cancelled()
        arcs = _fan_arcs(body, patch, used)
        if arcs is not None:
            arcs_of_point = np.empty(len(points), dtype=np.int64)
            arcs_of_point[vertex_of.ravel()] = arcs
            # Ein offener Bogen zählt eins, ein geschlossener Ring null — und
            # null ist nur an einem wasserdichten, gleich orientierten Netz
            # ein einziger Ring; sonst könnten es zwei sein, und die Ecke geht
            # den Einzelweg.
            whole = (
                arcs_of_point == 0
                if bool(body.is_watertight) and bool(body.is_winding_consistent)
                else np.zeros(len(points), dtype=bool)
            )
            torn &= (arcs_of_point != 1) & ~whole
    open_fans = np.flatnonzero(torn)
    if len(open_fans):
        # Alle zerrissenen Ecken in einem Zug (:func:`_fans_connected`); nur
        # wer dort auseinanderfällt, geht den Einzelweg mit dem
        # Strahlenvergleich der T-Unterteilungen.
        if check_cancelled is not None:
            check_cancelled()
        occurrence_of = np.flatnonzero(torn[reverse])
        rows, local = occurrence_of // 3, occurrence_of % 3
        whole_fans = _fans_connected(
            len(points),
            reverse[occurrence_of],
            corners[rows, (local + 1) % 3],
            corners[rows, (local + 2) % 3],
        )
        open_fans = open_fans[~whole_fans]
    for index in open_fans:
        if check_cancelled is not None:
            check_cancelled()
        occurrences = order[offsets[index] : offsets[index + 1]]
        rows, local = occurrences // 3, occurrences % 3
        neighbours = np.column_stack(
            (corners[rows, (local + 1) % 3], corners[rows, (local + 2) % 3])
        )
        if not _one_vertex_fan(points, int(index), neighbours, check_cancelled):
            ridges[index] = False
            round_corners[index] = False
    directions = np.cross(first, second)
    lengths = np.linalg.norm(directions, axis=1)
    directions /= np.where(lengths > EPS_GEOM, lengths, 1.0)[:, None]
    if check_cancelled is not None:
        check_cancelled()
    return _SurfaceSupport(
        points, corners, normals, triangles.mean(axis=1), areas, round_corners, ridges, directions
    )


def _ridge_endpoints(
    support: _SurfaceSupport, check_cancelled: Callable[[], None] | None = None
) -> np.ndarray:
    """Kollineare Zwischenpunkte tragen kein zweites Maß einer Mantellinie."""
    (edges,) = unique_edges(support.corners[:, ((0, 1), (1, 2), (2, 0))].reshape(-1, 2))
    directions = support.points[edges[:, 1]] - support.points[edges[:, 0]]
    lengths = np.linalg.norm(directions, axis=1)
    unit = directions / np.where(lengths > EPS_GEOM, lengths, 1.0)[:, None]
    forward = np.zeros(len(support.points), dtype=bool)
    backward = np.zeros(len(support.points), dtype=bool)
    for side in (0, 1):
        if check_cancelled is not None:
            check_cancelled()
        index = edges[:, side]
        along = np.einsum("ij,ij->i", unit, support.directions[index]) * (
            1.0 if side == 0 else -1.0
        )
        valid = (lengths > EPS_GEOM) & (np.abs(along) >= units.exact_cos_degrees(EPS_ANGLE))
        np.logical_or.at(forward, index, valid & (along > 0.0))
        np.logical_or.at(backward, index, valid & (along < 0.0))
    return support.ridges & ~(forward & backward)


def _round_points_are_consistent(
    support: _SurfaceSupport, errors: np.ndarray, selected: np.ndarray
) -> bool:
    """Jede belegte Netzecke muss örtlich passen; ein großer Fitradius hilft nicht."""
    if not np.any(selected):
        return False
    points = support.points[selected]
    local_span = float(2.0 * np.linalg.norm(points - points.mean(axis=0), axis=1).max())
    return (
        local_span > EPS_GEOM
        and float(np.abs(errors[selected]).max()) <= local_span * ROUND_LOCAL_TOLERANCE
    )


def _cone_support_points(
    support: _SurfaceSupport,
    apex: np.ndarray,
    tolerance: float,
    check_cancelled: Callable[[], None] | None = None,
) -> np.ndarray:
    """Belegte Netzecken und nachgewiesene gemeinsame Mantellinien des Kegels."""
    off_line = np.linalg.norm(np.cross(support.points - apex, support.directions), axis=1)
    return support.round_corners | (
        _ridge_endpoints(support, check_cancelled) & (off_line <= tolerance)
    )


def _row_lengths(vectors: np.ndarray) -> np.ndarray:
    """``np.linalg.norm(vectors, axis=1)`` ohne dessen Umweg — dieselben Zahlen, Bit für Bit.

    ``norm`` rechnet für reelle Felder genau ``sqrt(add.reduce(x * x, axis))``,
    prüft davor aber Art, Achse und Ordnung in Python. Die Residuen und
    Ableitungen der Verfeinerung rufen das je Löserschritt an kleinen Feldern
    — am Drachen aus TripoSG 2,5 Millionen Mal, acht der 72 Sekunden eines
    Profils (21.09.2026).
    """
    lengths: np.ndarray = np.sqrt(np.add.reduce(vectors * vectors, axis=1))
    return lengths


def _length(vector: np.ndarray) -> float:
    """``np.linalg.norm(vector)`` für einen Vektor: ``sqrt(v · v)``, Bit für Bit dasselbe."""
    return math.sqrt(float(vector.dot(vector)))


def _refined_fit(
    initial: np.ndarray,
    residual: Callable[[np.ndarray], np.ndarray],
    check_cancelled: Callable[[], None] | None,
    jacobian: Callable[[np.ndarray], np.ndarray] | None = None,
) -> np.ndarray | None:
    """Begrenzt geometrisch verfeinern und numerisch unbestimmte Maße verwerfen.

    **Die Ableitung kommt geschlossen, wo es sie gibt.** Ohne ``jacobian``
    schätzt der Löser sie aus Differenzen und ruft dafür je Schritt so viele
    Residuen, wie es Größen gibt — an der Freiform mit 200 000 Dreiecken
    14 870 Jacobi-Schätzungen für 1 263 Verfeinerungen, mehr als die Hälfte
    ihrer Zeit (gemessen am 21.09.2026). Kegel, Kugel und Ring bringen ihre
    Ableitung deshalb mit; das Ergebnis ist dasselbe Minimum.
    """

    def checked(values: np.ndarray) -> np.ndarray:
        """Auch die numerischen Jacobi-Schritte lesen denselben Abbruchauftrag."""
        if check_cancelled is not None:
            check_cancelled()
        return residual(values)

    def checked_jacobian(values: np.ndarray) -> np.ndarray:
        if check_cancelled is not None:
            check_cancelled()
        assert jacobian is not None
        return jacobian(values)

    result = least_squares(
        checked,
        initial,
        jac="2-point" if jacobian is None else checked_jacobian,
        ftol=ROUND_FIT_PRECISION,
        xtol=ROUND_FIT_PRECISION,
        gtol=ROUND_FIT_PRECISION,
        max_nfev=ROUND_FIT_EVALUATIONS,
    )
    if not result.success or not np.isfinite(result.x).all() or not np.isfinite(result.fun).all():
        return None
    # **Wer sein Budget ausschöpft, hat nicht gerechnet, sondern aufgehört**
    # (RM-210). Ein Lauf am Limit steht irgendwo im Tal, und ob `success`
    # dort noch zufällig gesetzt ist, entscheidet die letzte Stelle — also die
    # Lage des Körpers im Raum: Derselbe Fleck aus 32 Dreiecken lieferte um
    # 13,7 mm verschoben einen Kegel von 53,50 Grad und an seinem Platz
    # keinen, bei Bit für Bit gleichem Startwert (gemessen am 22.09.2026).
    # Eine Antwort, die von der Lage abhängt, ist keine Aussage über die
    # Geometrie.
    if result.nfev >= ROUND_FIT_EVALUATIONS:
        return None
    singular = np.linalg.svd(result.jac, compute_uv=False)
    # Unterhalb dieser Grenze verstärkt die Lösung Float64-Rauschen über
    # dessen halbe signifikante Stellen hinaus. Fachliche Krümmungs- und
    # Normalengrenzen werden anschließend weiterhin separat geprüft.
    if len(singular) < len(initial) or singular[-1] <= singular[0] * np.sqrt(np.finfo(float).eps):
        return None
    return np.asarray(result.x, dtype=float)


def fit_cone(
    body: trimesh.Trimesh,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> ConeFit | None:
    """Achse, Spitze und Winkel gemeinsam an belegten Mantelpunkten einpassen."""
    result: ConeFit | None = remembered(
        "fit_cone",
        body,
        patch,
        lambda: _fit_cone_read(body, patch, check_cancelled=check_cancelled),
        check_cancelled=check_cancelled,
    )
    return result


def _fit_cone_read(
    body: trimesh.Trimesh,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> ConeFit | None:
    """Der Rumpf von :func:`fit_cone` — die Antwort merkt sich die Hülle."""
    support = _surface_support(body, patch, check_cancelled)
    if support is None:
        return None
    weights = support.areas / support.areas.sum()
    origin = weights @ support.centres
    centres = support.centres - origin
    normal_mean = weights @ support.normals
    centred_normals = support.normals - normal_mean
    _values, vectors = np.linalg.eigh(centred_normals.T @ (centred_normals * weights[:, None]))
    axis = vectors[:, 0]
    root_weight = np.sqrt(weights)
    apex, _residual, rank, _singular = np.linalg.lstsq(
        support.normals * root_weight[:, None],
        np.einsum("ij,ij->i", support.normals, centres) * root_weight,
        rcond=None,
    )
    if rank < 3:
        return None
    if float(weights @ ((centres - apex) @ axis)) < 0.0:
        axis = -axis
    offset = float(normal_mean @ axis)
    half_angle = math.asin(min(1.0, abs(offset)))
    if half_angle <= EPS_GEOM:
        return None
    # **Der Winkel steht hier schon, und darunter gibt es nichts zu verfeinern**
    # (:data:`CONE_START_ANGLE`). Die Normalen stehen dann praktisch senkrecht
    # auf der Achse — das ist ein Zylinder, und den fragt `classify` gleich
    # danach ohnehin. An `Elegoo_erster_Druck.3mf` sparte das 45,6 Prozent der
    # Kegelzeit, ohne einen einzigen Kegel zu verlieren (22.09.2026).
    if math.degrees(half_angle) < CONE_START_ANGLE:
        return None
    points = support.points - origin
    # Eine gerade Naht zweier Mantelfacetten ist nur dann eine zusätzliche
    # Stütze, wenn sie durch dieselbe Spitze läuft. Schnittpunkte auf einer
    # solchen Mantellinie liegen ebenfalls auf dem analytischen Kegel.
    line_tolerance = max(weld_tolerance(float(np.linalg.norm(body.extents))), ROUND_WALL_TOLERANCE)
    selected = _cone_support_points(support, origin + apex, line_tolerance, check_cancelled)
    if int(selected.sum()) < 6:
        return None
    scale = float(np.linalg.norm(np.ptp(points[selected], axis=0)))
    if scale <= EPS_GEOM:
        return None
    samples = points[selected] / scale
    apex = apex / scale
    initial_axis = axis
    first, second = _plane_basis(initial_axis)
    at_apex = np.flatnonzero(np.linalg.norm(samples - apex, axis=1) <= EPS_GEOM / scale)
    # Der Löser rechnet an einer Auswahl der Stützpunkte, die Spitze bleibt
    # darin (:data:`FIT_SOLVER_POINTS`); die Kennzahlen unten lesen alle.
    rows = _solver_rows(len(samples), keep=int(at_apex[0]) if len(at_apex) else None)
    solving = samples if rows is None else samples[rows]
    solving_apex = (
        at_apex if rows is None or not len(at_apex) else np.flatnonzero(rows == int(at_apex[0]))
    )

    def parameters(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
        """Die Achse besitzt genau zwei Freiheitsgrade, keine freie Länge."""
        direction = initial_axis + first * values[3] + second * values[4]
        return values[:3], direction / _length(direction), float(values[5])

    def residual(values: np.ndarray) -> np.ndarray:
        """Geometrischer Abstand zum Kegel; eine belegte Spitze bleibt ein Punkt."""
        tip, direction, angle = parameters(values)
        relative = solving - tip
        along = relative @ direction
        radial = _row_lengths(relative - along[:, None] * direction)
        errors = radial * math.cos(angle) - along * math.sin(angle)
        if len(solving_apex):
            errors = np.r_[errors, tip - solving[solving_apex[0]]]
        return np.asarray(errors, dtype=float)

    def jacobian(values: np.ndarray) -> np.ndarray:
        """Die Ableitung des Kegelabstands nach Spitze, Achsneigung und Winkel."""
        tip, direction, angle = parameters(values)
        raw_direction = initial_axis + first * values[3] + second * values[4]
        relative = solving - tip
        along = relative @ direction
        perpendicular = relative - along[:, None] * direction
        radial = _row_lengths(perpendicular)
        safe = np.where(radial > EPS_GEOM, radial, EPS_GEOM)
        unit = perpendicular / safe[:, None]
        cosine, sine = math.cos(angle), math.sin(angle)
        columns = np.empty((len(solving), 6))
        columns[:, :3] = -cosine * unit + sine * direction
        length = _length(raw_direction)
        for column, basis in ((3, first), (4, second)):
            turned = (basis - direction * float(direction @ basis)) / length
            d_along = relative @ turned
            d_radial = -along * (unit @ turned)
            columns[:, column] = cosine * d_radial - sine * d_along
        columns[:, 5] = -radial * sine - along * cosine
        if len(solving_apex):
            apex_rows = np.zeros((3, 6))
            apex_rows[:, :3] = np.eye(3)
            columns = np.vstack((columns, apex_rows))
        return columns

    fitted = _refined_fit(np.r_[apex, 0.0, 0.0, half_angle], residual, check_cancelled, jacobian)
    normal_constrained = False
    if fitted is None and float(np.ptp(samples @ initial_axis)) <= line_tolerance / scale:
        # Ein einziger erhaltener Kreis bestimmt nicht sechs Kegelgrößen.
        # Die übrigen Beobachtungen sind die tatsächlichen Mantelnormalen;
        # sie binden hier ausdrücklich Achse und Winkel. Sehnenschnittpunkte
        # werden dafür nicht nachträglich als Kreispunkte ausgegeben.
        def tip_residual(tip: np.ndarray) -> np.ndarray:
            """Drei bestimmte Spitzenkoordinaten bei beobachteter Achse und Winkel."""
            return residual(np.r_[tip, 0.0, 0.0, half_angle])

        tip = _refined_fit(apex, tip_residual, check_cancelled)
        if tip is not None:
            fitted = np.r_[tip, 0.0, 0.0, half_angle]
            normal_constrained = True
    if fitted is None:
        return None
    apex, axis, angle = parameters(fitted)
    if not 0.0 < angle < math.pi / 2:
        return None
    apex = apex * scale
    relative = points - apex
    along = relative @ axis
    if float(along.min()) < -EPS_GEOM:
        return None
    radial = np.linalg.norm(relative - np.outer(along, axis), axis=1)
    mean_radius = float(radial[selected].mean())
    if mean_radius <= EPS_GEOM:
        return None
    errors = radial[selected] - along[selected] * math.tan(angle)
    widest = float(along.max())
    world_apex = origin + apex
    centre = world_apex + axis * widest
    return ConeFit(
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        apex=(float(world_apex[0]), float(world_apex[1]), float(world_apex[2])),
        centre=(float(centre[0]), float(centre[1]), float(centre[2])),
        half_angle=math.degrees(angle),
        radius=widest * math.tan(angle),
        residual=float(np.abs(errors).mean()) / mean_radius,
        recess=float(weights @ (support.normals @ axis)) > 0.0,
        fit_error=float(np.abs(errors).max()) * math.cos(angle),
        normal_constrained=normal_constrained,
    )


def fit_sphere(
    body: trimesh.Trimesh,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> SphereFit | None:
    """Mittelpunkt und Radius aus belegten Netzecken, nicht aus Facettenebenen."""
    result: SphereFit | None = remembered(
        "fit_sphere",
        body,
        patch,
        lambda: _fit_sphere_read(body, patch, check_cancelled=check_cancelled),
        check_cancelled=check_cancelled,
    )
    return result


def _fit_sphere_read(
    body: trimesh.Trimesh,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> SphereFit | None:
    """Der Rumpf von :func:`fit_sphere` — die Antwort merkt sich die Hülle."""
    support = _surface_support(body, patch, check_cancelled)
    if support is None or int(support.round_corners.sum()) < 4:
        return None
    points = support.points[support.round_corners]
    origin = points.mean(axis=0)
    scale = float(np.linalg.norm(np.ptp(points, axis=0)))
    if scale <= EPS_GEOM:
        return None
    local = (points - origin) / scale
    system = np.column_stack((2.0 * local, np.ones(len(local))))
    solution, _residuals, rank, _singular = np.linalg.lstsq(
        system, np.einsum("ij,ij->i", local, local), rcond=None
    )
    if rank < 4:
        return None
    square = float(solution[3] + solution[:3] @ solution[:3])
    if square <= 0.0:
        return None
    rows = _solver_rows(len(local))
    solving = local if rows is None else local[rows]

    def residual(values: np.ndarray, at: np.ndarray = solving) -> np.ndarray:
        """Radialer Abstand der belegten Punkte in der lokalen Längeneinheit."""
        return np.asarray(_row_lengths(at - values[:3]) - values[3], dtype=float)

    def jacobian(values: np.ndarray) -> np.ndarray:
        """Die Ableitung des radialen Abstands nach Mittelpunkt und Radius."""
        relative = solving - values[:3]
        distance = _row_lengths(relative)
        safe = np.where(distance > EPS_GEOM, distance, EPS_GEOM)
        columns = np.empty((len(solving), 4))
        columns[:, :3] = -relative / safe[:, None]
        columns[:, 3] = -1.0
        return columns

    fitted = _refined_fit(
        np.r_[solution[:3], math.sqrt(square)], residual, check_cancelled, jacobian
    )
    if fitted is None or fitted[3] * scale <= EPS_GEOM:
        return None
    centre = origin + fitted[:3] * scale
    radius = float(fitted[3] * scale)
    agreement = np.einsum(
        "ij,ij->i", support.normals, (support.centres - origin) - fitted[:3] * scale
    )
    errors = np.abs(residual(fitted, local))
    return SphereFit(
        centre=(float(centre[0]), float(centre[1]), float(centre[2])),
        radius=radius,
        residual=float(errors.mean()) * scale / radius,
        recess=float(agreement @ support.areas) < 0.0,
        fit_error=float(errors.max()) * scale,
    )


def fit_torus(
    body: trimesh.Trimesh,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> TorusFit | None:
    """Den gemeinsamen Toruskandidaten an belegten Netzecken geometrisch verfeinern."""
    result: TorusFit | None = remembered(
        "fit_torus",
        body,
        patch,
        lambda: _fit_torus_read(body, patch, check_cancelled=check_cancelled),
        check_cancelled=check_cancelled,
    )
    return result


def _fit_torus_read(
    body: trimesh.Trimesh,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> TorusFit | None:
    """Der Rumpf von :func:`fit_torus` — die Antwort merkt sich die Hülle."""
    support = _surface_support(body, patch, check_cancelled)
    if support is None or int(support.round_corners.sum()) < 7:
        return None
    initial = fit_torus_samples(support.centres, support.normals, weights=support.areas)
    if initial is None:
        return None
    points = support.points[support.round_corners]
    origin = points.mean(axis=0)
    scale = float(np.linalg.norm(np.ptp(points, axis=0)))
    if scale <= EPS_GEOM:
        return None
    local = (points - origin) / scale
    initial_axis = np.asarray(initial.axis)
    first, second = _plane_basis(initial_axis)
    rows = _solver_rows(len(local))
    solving = local if rows is None else local[rows]

    def parameters(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
        """Ringmitte, zweiachsige Richtung und beide positiven Radien."""
        direction = initial_axis + first * values[3] + second * values[4]
        return values[:3], direction / _length(direction), float(values[5]), float(values[6])

    def residual(values: np.ndarray, at: np.ndarray = solving) -> np.ndarray:
        """Geometrischer Abstand zum Meridiankreis an jedem belegten Netzpunkt."""
        centre, direction, ring, tube = parameters(values)
        relative = at - centre
        along = relative @ direction
        radial = _row_lengths(relative - along[:, None] * direction)
        return np.asarray(np.hypot(radial - ring, along) - tube, dtype=float)

    def jacobian(values: np.ndarray) -> np.ndarray:
        """Die Ableitung des Meridianabstands nach Mitte, Achsneigung und Radien."""
        centre, direction, ring, _tube = parameters(values)
        raw_direction = initial_axis + first * values[3] + second * values[4]
        relative = solving - centre
        along = relative @ direction
        perpendicular = relative - along[:, None] * direction
        radial = _row_lengths(perpendicular)
        safe_radial = np.where(radial > EPS_GEOM, radial, EPS_GEOM)
        unit = perpendicular / safe_radial[:, None]
        offset = radial - ring
        distance = np.hypot(offset, along)
        safe = np.where(distance > EPS_GEOM, distance, EPS_GEOM)
        columns = np.empty((len(solving), 7))
        columns[:, :3] = -unit * (offset / safe)[:, None] - (along / safe)[:, None] * direction
        length = _length(raw_direction)
        for column, basis in ((3, first), (4, second)):
            turned = (basis - direction * float(direction @ basis)) / length
            d_along = relative @ turned
            d_radial = -along * (unit @ turned)
            columns[:, column] = (offset * d_radial + along * d_along) / safe
        columns[:, 5] = -offset / safe
        columns[:, 6] = -1.0
        return columns

    fitted = _refined_fit(
        np.r_[
            (np.asarray(initial.centre) - origin) / scale,
            0.0,
            0.0,
            initial.ring_radius / scale,
            initial.tube_radius / scale,
        ],
        residual,
        check_cancelled,
        jacobian,
    )
    if fitted is None:
        return None
    centre, axis, ring, tube = parameters(fitted)
    if not ring > tube > EPS_GEOM / scale:
        return None
    local_centres = (support.centres - origin) / scale
    mid = _tube_centres(centre, axis, local_centres, ring)
    agreement = np.einsum("ij,ij->i", support.normals, local_centres - mid)
    world_centre = origin + centre * scale
    return TorusFit(
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        centre=(float(world_centre[0]), float(world_centre[1]), float(world_centre[2])),
        ring_radius=ring * scale,
        tube_radius=tube * scale,
        residual=float(np.abs(residual(fitted)).mean()) / tube,
        recess=float(agreement @ support.areas) < 0.0,
        fit_error=float(np.abs(residual(fitted)).max()) * scale,
    )


def fit_torus_samples(
    centres: np.ndarray, normals: np.ndarray, *, weights: np.ndarray | None = None
) -> TorusFit | None:
    """Gemeinsamer Toruskandidat aus Punkten und Normalen beider Darstellungsarten.

    Der Aufrufer prüft, ob sein gesamter Fleck den Kandidaten trägt. Native
    Flächen verwenden echte Ableitungen und einen anschließenden Formnachweis;
    Netze bleiben beim eigenständigen Eckpunkt- und Normalenvertrag.
    """
    if len(normals) < MIN_PATCH_FACES:
        return None

    if weights is None:
        weights = np.ones(len(centres))
    weights = np.asarray(weights, dtype=float) / float(np.sum(weights))
    root_weight = np.sqrt(weights)
    middle = weights @ centres
    scale = float(np.abs(centres - middle).max())
    if scale <= EPS_GEOM:
        return None
    scaled = (centres - middle) / scale

    system = np.column_stack([np.cross(scaled, normals), -normals]) * root_weight[:, None]
    *_, right = np.linalg.svd(system, full_matrices=False)
    axis = right[-1][:3]
    length = float(np.linalg.norm(axis))
    if length <= EPS_GEOM:
        return None
    axis = axis / length

    on_axis, *_ = np.linalg.lstsq(
        np.cross(normals, axis) * root_weight[:, None],
        np.einsum("ij,ij->i", normals, np.cross(axis, centres - middle)) * root_weight,
        rcond=None,
    )

    relative = (centres - middle) - on_axis
    along = relative @ axis
    radial = np.linalg.norm(relative - np.outer(along, axis), axis=1)
    meridian, tube_radius = _fit_circle(np.column_stack([radial, along]))
    ring_radius = float(meridian[0])
    if tube_radius <= EPS_GEOM or ring_radius <= tube_radius:
        return None

    # Der Meridiankreis sagt auch, wo die Mitte auf der Achse liegt — der
    # Achsenpunkt aus dem zweiten System ist irgendeiner, dieser ist der.
    centre = middle + on_axis + float(meridian[1]) * axis

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


def _torus_is_recognisable(
    body: trimesh.Trimesh,
    fit: TorusFit,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Nur Flecken mit belegten Normalen des eingepassten Torus veröffentlichen.

    :func:`fit_torus` bleibt für die Formauswahl und Diagnose verfügbar. Erst
    diese Prüfung entscheidet, ob der algebraisch passende Fleck auch als
    sicher bearbeitbares Merkmal in den Objektbaum darf.
    """
    result: bool = remembered(
        "_torus_is_recognisable",
        body,
        patch,
        lambda: _torus_is_recognisable_read(body, fit, patch, check_cancelled=check_cancelled),
        extra=fit,
        check_cancelled=check_cancelled,
    )
    return result


def _torus_is_recognisable_read(
    body: trimesh.Trimesh,
    fit: TorusFit,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Der Rumpf von :func:`_torus_is_recognisable` — die Antwort merkt sich die Hülle."""
    centres = np.asarray(body.triangles_center[patch], dtype=float)
    corners = np.asarray(body.triangles[patch], dtype=float)
    centre = np.asarray(fit.centre, dtype=float)
    axis = np.asarray(fit.axis, dtype=float)
    support = _surface_support(body, patch, check_cancelled)
    if support is None:
        return False
    relative = support.points - centre
    along = relative @ axis
    across = np.linalg.norm(relative - np.outer(along, axis), axis=1)
    errors = np.hypot(across - fit.ring_radius, along) - fit.tube_radius
    if not _round_points_are_consistent(support, errors, support.round_corners):
        return False
    # Lineare Unterteilung eines Torusdreiecks bleibt zwischen seinen
    # axialen Tangentialebenen und innerhalb seines äußeren Zylinders.
    # Das gilt auch für ungestützte Randpunkte. Eine lange Zylinderwand
    # neben der Rundung darf daher nicht im Stützpunktfit verschwinden.
    allowance = max(
        weld_tolerance(float(np.linalg.norm(body.extents))), fit.tube_radius * ROUND_TOLERANCE
    )
    if np.any(np.abs(along) > fit.tube_radius + allowance) or np.any(
        across > fit.ring_radius + fit.tube_radius + allowance
    ):
        return False

    def expected_normals(points: np.ndarray) -> np.ndarray | None:
        """Torusnormalen an Punkten, unabhängig von ihrer Flächenrichtung."""
        if check_cancelled is not None:
            check_cancelled()
        tube_centres = _tube_centres(centre, axis, points, fit.ring_radius)
        radial = points - tube_centres
        lengths = np.linalg.norm(radial, axis=1)
        if bool(np.any(lengths <= EPS_GEOM)):
            return None
        return np.asarray(radial / lengths[:, None], dtype=float)

    expected = expected_normals(centres)
    corner_expected = expected_normals(corners.reshape(-1, 3))
    if expected is None or corner_expected is None:
        return False
    corner_expected = corner_expected.reshape(-1, 3, 3)
    return _surface_normals_are_consistent(
        body,
        patch,
        expected,
        corner_expected,
        max_error=TORUS_NORMAL_ERROR,
        max_outlier_share=TORUS_NORMAL_OUTLIER_SHARE,
    )


def _cone_vertices_are_consistent(
    body: trimesh.Trimesh,
    fit: ConeFit,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Ob alle wirklichen Facettenecken den eingepassten Kegelmantel tragen.

    Maßführende Netzecken und die übrige Haut bleiben getrennte Belege.
    Die bestehende Hauttoleranz gilt weiterhin an jeder ursprünglichen Ecke;
    eine breite Facette darf nicht hinter wenigen passenden Stützpunkten
    verschwinden. Der örtliche Maximalfehler prüft zusätzlich die Stützen.
    """
    axis = np.asarray(fit.axis, dtype=float)
    apex = np.asarray(fit.apex, dtype=float)
    centres = np.asarray(body.triangles_center[patch], dtype=float)
    centre_relative = centres - apex
    centre_along = centre_relative @ axis
    centre_radial = np.linalg.norm(centre_relative - np.outer(centre_along, axis), axis=1)
    mean_radius = float(centre_radial.mean())
    if mean_radius <= EPS_GEOM:
        return False

    vertex_indices = np.unique(np.asarray(body.faces[patch], dtype=np.intp))
    relative = np.asarray(body.vertices[vertex_indices], dtype=float) - apex
    along = relative @ axis
    radial = np.linalg.norm(relative - np.outer(along, axis), axis=1)
    expected = along * math.tan(math.radians(fit.half_angle))
    if float(np.max(np.abs(radial - expected))) > mean_radius * CONE_TOLERANCE:
        return False
    support = _surface_support(body, patch, check_cancelled)
    if support is None:
        return False
    relative = support.points - apex
    along = relative @ axis
    radial = np.linalg.norm(relative - np.outer(along, axis), axis=1)
    angle = math.radians(fit.half_angle)
    errors = radial * math.cos(angle) - along * math.sin(angle)
    tolerance = max(weld_tolerance(float(np.linalg.norm(body.extents))), ROUND_WALL_TOLERANCE)
    return _round_points_are_consistent(
        support, errors, _cone_support_points(support, apex, tolerance, check_cancelled)
    )


def _cone_is_recognisable(
    body: trimesh.Trimesh,
    fit: ConeFit,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Nur Flecken mit belegten Punkten und Normalen als Kegel veröffentlichen."""
    result: bool = remembered(
        "_cone_is_recognisable",
        body,
        patch,
        lambda: _cone_is_recognisable_read(body, fit, patch, check_cancelled=check_cancelled),
        extra=fit,
        check_cancelled=check_cancelled,
    )
    return result


def _cone_is_recognisable_read(
    body: trimesh.Trimesh,
    fit: ConeFit,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Der Rumpf von :func:`_cone_is_recognisable` — die Antwort merkt sich die Hülle."""
    if not _cone_vertices_are_consistent(body, fit, patch, check_cancelled=check_cancelled):
        return False
    centres = np.asarray(body.triangles_center[patch], dtype=float)
    corners = np.asarray(body.triangles[patch], dtype=float)
    apex = np.asarray(fit.apex, dtype=float)
    axis = np.asarray(fit.axis, dtype=float)
    sine = units.exact_sin_degrees(fit.half_angle)
    cosine = units.exact_cos_degrees(fit.half_angle)

    def expected_normals(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Kegelnormalen und ihre Gültigkeit an beliebigen Punkten."""
        if check_cancelled is not None:
            check_cancelled()
        relative = points - apex
        along = relative @ axis
        radial = relative - np.outer(along, axis)
        lengths = np.linalg.norm(radial, axis=1)
        valid = lengths > EPS_GEOM
        directions = radial / np.where(valid, lengths, 1.0)[:, None]
        return np.asarray(directions * cosine - axis * sine, dtype=float), valid

    expected, centre_valid = expected_normals(centres)
    if not bool(np.all(centre_valid)):
        return False
    corner_expected, corner_valid = expected_normals(corners.reshape(-1, 3))
    corner_expected = corner_expected.reshape(-1, 3, 3)
    corner_valid = corner_valid.reshape(-1, 3)
    # An der Kegelspitze gibt es keine eindeutige glatte Normale. Sie trägt
    # keine zusätzliche Auflösung bei und übernimmt deshalb die Normale des
    # zugehörigen Dreiecksschwerpunkts.
    corner_expected = np.where(corner_valid[:, :, None], corner_expected, expected[:, None, :])
    return _surface_normals_are_consistent(
        body,
        patch,
        expected,
        corner_expected,
        max_error=CONE_NORMAL_ERROR,
        max_outlier_share=CONE_NORMAL_OUTLIER_SHARE,
    )


def _surface_normals_are_consistent(
    body: trimesh.Trimesh,
    patch: list[int],
    expected: np.ndarray,
    corner_expected: np.ndarray,
    *,
    max_error: float,
    max_outlier_share: float,
) -> bool:
    """Ob eine analytische Normalenfamilie den Fleck flächengewichtet trägt."""
    normals = np.asarray(body.face_normals[patch], dtype=float)
    areas = np.asarray(body.area_faces[patch], dtype=float)
    total_area = float(areas.sum())
    if total_area <= EPS_GEOM:
        return False

    agreement = np.einsum("ij,ij->i", normals, expected)
    orientation = 1.0 if float(agreement @ areas) >= 0.0 else -1.0
    error = np.degrees(np.arccos(np.clip(agreement * orientation, -1.0, 1.0)))
    # Ein grobes Dreieck darf nicht an der glatten Schwerpunktnormale gemessen
    # werden. Die größte Änderung bis zu seinen drei Ecken ist genau die
    # Winkelauskunft, welche die gewählte Vernetzung selbst noch auflösen kann.
    resolution = np.degrees(
        np.arccos(np.clip(np.einsum("fvi,fi->fv", corner_expected, expected), -1.0, 1.0))
    ).max(axis=1)
    outlier_area = float(areas[error > resolution + max_error].sum())
    return outlier_area <= total_area * max_outlier_share


def _plane_basis(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    basis_u = np.cross(axis, helper)
    basis_u = basis_u / float(np.linalg.norm(basis_u))
    return basis_u, np.cross(axis, basis_u)


def _fit_circle(points: np.ndarray) -> tuple[np.ndarray, float]:
    """Algebraische Kreiseinpassung (Kåsa): linear, stabil genug für ein
    gebohrtes Loch.
    """
    # Die Quadrate gehören in den lokalen Maßrahmen. Weltkoordinaten machen
    # dieselbe Kreisform je Plattenposition unterschiedlich schlecht bedingt.
    origin = points.mean(axis=0)
    local = points - origin
    matrix = np.column_stack([local[:, 0], local[:, 1], np.ones(len(points))])
    target = local[:, 0] ** 2 + local[:, 1] ** 2
    solution, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    centre = np.array([solution[0] / 2.0, solution[1] / 2.0])
    radius = math.sqrt(max(solution[2] + centre @ centre, 0.0))
    return centre + origin, radius


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


#: Wie viele Punkte je Ring und welche Ringe :func:`_is_through` in der Mündung
#: einer Bohrung abfragt. Die Ringe liegen innerhalb der Sehnen des Mantels,
#: damit die eigene Wand nie „über" einem Punkt liegt — und innerhalb des
#: Kerns eines groben Gewindes: Bei Tr 10x3 ist der Kern 0,65 des
#: Nenndurchmessers, bei metrischen Regelgewinden 0,82 bis 0,90; ein Ring bei
#: 0,75 läge auf der Flanke, und eine durchgehende Gewindebohrung hieße
#: Sackloch. Der Becherboden mit einer Bohrung Ø 8 in Ø 116, der diese Ringe
#: veranlasst hat, liegt bei 0,07 und wird von beiden getroffen.
THROUGH_SAMPLES: Final = 8
THROUGH_RINGS: Final = (0.3, 0.6)


class _ThroughBounds:
    """Dreiecksgrenzen für alle Bohrungen eines unveränderlichen Körpers.

    Bei exakten Koordinatenachsen ist die Projektion nur eine Koordinate mit
    Vorzeichen. Eine konstante Subtraktion erhält deren Reihenfolge, deshalb
    dürfen Minima und Maxima vorgezogen werden. Kein neuer Rundungsweg und
    keine größere Toleranz: Die nachfolgende Prüfung sieht dieselben Kandidaten.
    Schiefe Achsen gehen vollständig durch den bisherigen Weg.
    """

    def __init__(self, body: trimesh.Trimesh) -> None:
        """Grenzen erst bei der ersten exakt achsenparallelen Bohrung aufbauen."""
        self._body = body
        self._limits: tuple[np.ndarray, np.ndarray] | None = None

    def candidates(
        self,
        axis: np.ndarray,
        basis_u: np.ndarray,
        basis_v: np.ndarray,
        fit: CylinderFit,
        patch: Sequence[int] | None,
    ) -> np.ndarray | None:
        """Nur Dreiecke im bisherigen Achsabschnitt und Mündungsquadrat auswählen."""
        directions: list[tuple[int, bool]] = []
        for direction in (axis, basis_u, basis_v):
            index = int(np.argmax(np.abs(direction)))
            exact = np.zeros(3)
            exact[index] = np.copysign(1.0, direction[index])
            # Identität für eine Rechenabkürzung, keine geometrische Nähe:
            # Auch eine noch so kleine Neigung muss den vollständigen Weg nehmen.
            if not np.array_equal(direction, exact):
                return None
            directions.append((index, bool(np.signbit(direction[index]))))

        if self._limits is None:
            corners = np.asarray(self._body.triangles, dtype=float)
            self._limits = corners.min(axis=1), corners.max(axis=1)
        minimum, maximum = self._limits
        keep = np.ones(len(minimum), dtype=bool)
        for number, (index, reverse) in enumerate(directions):
            if number == 0 and patch is None:
                continue
            low = minimum[:, index] - fit.centre[index]
            high = maximum[:, index] - fit.centre[index]
            if reverse:
                low, high = -high, -low
            if number == 0 and patch is not None:
                start, end = _axial_span(self._body, list(patch), fit.axis)
                offset = float(np.asarray(fit.centre) @ axis)
                keep &= (low <= end - offset + EPS_GEOM) & (high >= start - offset - EPS_GEOM)
            else:
                keep &= (low <= fit.radius) & (high >= -fit.radius)
        return keep


def _is_through(
    mesh: MeshData,
    fit: CylinderFit,
    cones: Cones | None = None,
    patch: Sequence[int] | None = None,
    *,
    bounds: _ThroughBounds | None = None,
) -> bool:
    """Eine Bohrung ist durchgehend, wenn man durch sie hindurchsieht.

    **Wörtlich gemeint, und es ist fast die ganze Prüfung:** Liegt ein Dreieck
    des Körpers über der Bohrachse, ist da Material — ein Boden, ein Steg, eine
    Rückwand —, und das Loch endet. Liegt keines dort, geht es durch. Gemessen
    am Korpus: null Dreiecke über der Achse bei jeder durchgehenden Bohrung,
    dreiundzwanzig bei der gesenkten Sackbohrung.

    **„Über der Achse" allein war zu weit gefasst**, und ein U-Profil zeigt das
    in einer Zeile: Der gegenüberliegende Schenkel liegt in der Projektion
    senkrecht zur Achse genau über der Bohrung im ersten — verschließt sie aber
    nicht, er steht zwei Zentimeter daneben. Die Durchgangsbohrung galt damit
    als Sackloch, und im Steckbrief stand „Sackbohrung Ø 6" über einem Loch,
    durch das man hindurchsieht.

    Gezählt wird deshalb nur, was **entlang der Achse im Abschnitt der
    Bohrung** liegt: von ihrem Anfang bis zu ihrem Ende, mit einer halben
    Facettenbreite Zugabe an beiden Enden, denn der Boden eines Sacklochs sitzt
    genau auf dieser Grenze. Ohne ``patch`` — also ohne den Fleck, der den
    Abschnitt kennt — bleibt es bei der alten, weiteren Frage.

    **Vorher stand hier eine Rechnung, und sie war an drei Stellen angreifbar.**
    Sie verglich die Höhe der Zylinderwand mit der Dicke des Körpers und
    brauchte dafür: die Senkung dazugerechnet, weil deren Stück nicht zur Wand
    gehört (sonst galt jedes gesenkte Loch als Sackloch); eine Toleranz, weil
    ein reales Netz die Dicke nie auf den Mikrometer trifft (an einer gefasten
    Bohrung fehlten elf Tausendstel); und die Dicke **an der Bohrung** statt
    über den Körper, weil ein 15 mm hoher Zapfen daneben aus einer 10 mm
    dicken Platte sonst eine 25 mm dicke machte. Jede dieser drei Stellen war
    ein eigener Fehler, und jeder wurde einzeln gefunden.

    Diese Prüfung braucht keine davon. Eine Senkung ist ihr gleichgültig, ein
    Zapfen nebenan ebenso, und eine Toleranz gibt es nicht: Ein Dreieck liegt
    über der Achse oder nicht.

    Gerechnet wird über einen Punkt-in-Dreieck-Test in der Projektion senkrecht
    zur Achse — baryzentrische Vorzeichen, kein Strahlwurf und damit kein
    Raumindex. ``rtree`` war der Grund für diese Bauart und ist seit dem
    24.08.2026 ganz aus dem Prozess (Heap-Korruption; die Geschichte steht an
    :func:`app.core.geom.mesh.on_surface`) — die Rechnung hier bleibt auch
    ohne den alten Grund die billigere.
    """
    del cones  # Die Senkung geht in diese Frage nicht mehr ein.
    axis = np.asarray(fit.axis, dtype=float)
    centre = np.asarray(fit.centre, dtype=float)
    basis_u, basis_v = _plane_basis(axis)
    corners = np.asarray(mesh.raw.triangles, dtype=float)
    if bounds is not None:
        candidates = bounds.candidates(axis, basis_u, basis_v, fit, patch)
        if candidates is not None:
            corners = corners[candidates]
    corners = corners - centre

    if patch is not None:
        along = corners @ axis
        low, high = _axial_span(mesh.raw, list(patch), fit.axis)
        # Der Boden eines Sacklochs sitzt exakt auf dem Ende des Flecks — die
        # Grenzen gehören also dazu, und ``EPS_GEOM`` fängt, was das Netz an
        # dieser Kante an Rundung übriglässt.
        offset = float(centre @ axis)
        reach = (along.min(axis=1) <= high - offset + EPS_GEOM) & (
            along.max(axis=1) >= low - offset - EPS_GEOM
        )
        corners = corners[reach]
        if not len(corners):
            return True

    # **Nicht nur die Achse, die ganze Mündung.** Ein Becherboden mit einer
    # kleinen Bohrung in der Mitte ließ über der Achse kein Dreieck stehen —
    # und der Topf Ø 116 galt als durchgehend; *Versetzen* schnitt ihn daraufhin
    # mit einem Messer von Durchmesserlänge quer durch den Boden (Minigolf-
    # Becher, minus 7,7 Prozent Volumen, 15.09.2026). Geprüft werden deshalb
    # die Achse und zwei Ringe im Innern der Mündung; nur wenn über keinem
    # dieser Punkte ein Dreieck liegt, sieht man hindurch. Vorher fallen alle
    # Dreiecke weg, deren Projektion die Mündungsscheibe gar nicht erreicht.
    radius = float(fit.radius)
    if _mouth_covered(corners, basis_u, basis_v, radius):
        return False
    # **Und die Flächen, die an den Mantel grenzen, in ganzer Länge** — die
    # Frage des exakten Kerns (``brep.features._axis_covered``: seine Nachbar-
    # flächen über den ganzen Körper). Der Abschnitt oben sah vom Übergangs-
    # kegel einer Aufweitung Ø 9 über Ø 5 nur das Band, das seine Endebene
    # berührt: Am netzgebohrten Zwilling ist das der ganze Kegel, an der
    # Tessellierung des exakten Körpers ein Streifen von 3,8 bis 4,5 mm
    # Radius, und der Ring bei 0,6 (2,7 mm) blieb frei — die Aufweitung hieß
    # dort durchgehend, am exakten Körper nicht (Kreuzbefund Paket A,
    # 22.09.2026). Der gegenüberliegende Schenkel eines U-Profils grenzt nicht
    # an den Mantel und zählt weiter nicht.
    if patch is not None:
        members = _faces_beside(mesh.raw, patch)
        if bounds is not None and len(members):
            # Dieselbe Vorauswahl über das Mündungsquadrat wie oben, ohne den
            # Abschnitt: Die Deckflächen einer Platte mit 200 000 Dreiecken
            # zählen sonst je Bohrung ganz.
            square = bounds.candidates(axis, basis_u, basis_v, fit, None)
            if square is not None:
                members = members[square[members]]
        if len(members):
            beside = np.asarray(mesh.raw.triangles, dtype=float)[members] - centre
            if _mouth_covered(beside, basis_u, basis_v, radius):
                return False
    return True


def _mouth_covered(
    corners: np.ndarray, basis_u: np.ndarray, basis_v: np.ndarray, radius: float
) -> bool:
    """Liegt eines dieser Dreiecke über der Achse oder einem der Ringe der Mündung?

    ``corners`` sind Dreiecke relativ zur Mitte der Bohrung, ``(n, 3, 3)``.
    Ein Punkt-in-Dreieck-Test in der Projektion senkrecht zur Achse —
    baryzentrische Vorzeichen, kein Strahlwurf und damit kein Raumindex.
    """
    if not len(corners):
        return False
    flat = np.stack([corners @ basis_u, corners @ basis_v], axis=-1)
    within = (flat.min(axis=1) <= radius).all(axis=1) & (flat.max(axis=1) >= -radius).all(axis=1)
    flat = flat[within]
    if not len(flat):
        return False
    angles = np.linspace(0.0, 2.0 * np.pi, THROUGH_SAMPLES, endpoint=False)
    samples = np.vstack(
        [
            np.zeros((1, 2)),
            *(
                np.column_stack([np.cos(angles), np.sin(angles)]) * (radius * share)
                for share in THROUGH_RINGS
            ),
        ]
    )

    # Alle Stichpunkte in einem Zug: ``(Dreiecke, Punkte)`` statt einer
    # Schleife über die Punkte mit je zehn Feldoperationen — an der
    # unterteilten Lochplatte 50 der 180 ms der Durchgangsfrage (22.09.2026).
    # Das Kreuzprodukt zweier ebener Vektoren von Hand, weil ``np.cross`` seit
    # NumPy 2 nur noch dreidimensional rechnet.
    corners_a, corners_b, corners_c = flat[:, 0], flat[:, 1], flat[:, 2]
    edge_ab, edge_bc, edge_ca = corners_b - corners_a, corners_c - corners_b, corners_a - corners_c
    first = samples[None, :, :] - corners_a[:, None, :]
    second = samples[None, :, :] - corners_b[:, None, :]
    third = samples[None, :, :] - corners_c[:, None, :]
    side_a = edge_ab[:, None, 0] * first[:, :, 1] - edge_ab[:, None, 1] * first[:, :, 0]
    side_b = edge_bc[:, None, 0] * second[:, :, 1] - edge_bc[:, None, 1] * second[:, :, 0]
    side_c = edge_ca[:, None, 0] * third[:, :, 1] - edge_ca[:, None, 1] * third[:, :, 0]
    covers = ((side_a >= 0.0) & (side_b >= 0.0) & (side_c >= 0.0)) | (
        (side_a <= 0.0) & (side_b <= 0.0) & (side_c <= 0.0)
    )
    return bool(covers.any())


def _surface_owners(body: trimesh.Trimesh) -> np.ndarray:
    """Je Dreieck die Nummer der Fläche, auf der es liegt — einmal je Körper.

    Das Netzgegenstück zu den Flächen des exakten Körpers: Die ebenen Facetten,
    die :func:`_large_facet_faces` als Flächen liest, sind je eine; was übrig
    bleibt, zerfällt an seinen Kanten in glatte Rundflecken
    (:func:`_connected_patches`, dieselbe Teilung wie in :func:`_fitted`) —
    der Übergangskegel einer Aufweitung, der Boden eines Sacklochs, der Mantel
    der Bohrung darunter. ``-1`` trägt ein Dreieck ohne Fläche.
    """
    owners: np.ndarray = remembered("surface_owners", body, (), lambda: _surface_owners_read(body))
    return owners


def _surface_owners_read(body: trimesh.Trimesh) -> np.ndarray:
    """Der Rumpf von :func:`_surface_owners` — die Antwort merkt sich die Hülle."""
    planar = _large_facet_faces(body)
    owners = np.full(len(body.faces), -1, dtype=np.int64)
    number = 0
    for facet in body.facets:
        members = np.asarray(facet, dtype=np.int64)
        if len(members) and int(members[0]) in planar:
            owners[members] = number
            number += 1
    for patch in _connected_patches(body, _all_but(len(body.faces), planar)):
        owners[np.asarray(patch, dtype=np.int64)] = number
        number += 1
    return owners


def _faces_beside(body: trimesh.Trimesh, patch: Sequence[int]) -> np.ndarray:
    """Alle Dreiecke der Flächen, die an diesen Fleck grenzen — ohne den Fleck selbst."""
    indices = np.asarray(patch, dtype=np.int64)
    if not len(indices):
        return np.zeros(0, dtype=np.int64)
    neighbours, _rows = _neighbour_index(body)
    if not neighbours.shape[1]:
        return np.zeros(0, dtype=np.int64)
    inside = np.zeros(len(body.faces), dtype=bool)
    inside[indices] = True
    beside = neighbours[indices]
    beside = beside[beside >= 0]
    beside = beside[~inside[beside]]
    if not len(beside):
        return np.zeros(0, dtype=np.int64)
    owners = _surface_owners(body)
    surfaces = np.unique(owners[beside])
    surfaces = surfaces[surfaces >= 0]
    members = np.flatnonzero(np.isin(owners, surfaces)) if len(surfaces) else beside
    return members[~inside[members]]


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
    degrees = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    usable = (degrees < CURVATURE_LIMIT) & np.isfinite(radii)
    found = np.full(len(body.faces), np.inf, dtype=float)
    if not bool(usable.any()):
        return found
    neighbours = np.asarray(pairs[usable], dtype=np.intp)
    values = np.asarray(radii[usable], dtype=float)
    # Dasselbe Minimum wie die frühere Python-Schleife, vektorisiert auf
    # beiden Seiten jedes Nachbarpaars. Am merkmalsreichen 200k-Prüfkörper
    # sind das 18 ms statt 235; die Zahlen sind bitgleich, denn ``minimum``
    # hängt nicht von der Reihenfolge der Paare ab.
    np.minimum.at(found, neighbours[:, 0], values)
    np.minimum.at(found, neighbours[:, 1], values)
    return found


def _curvature_jumps(body: trimesh.Trimesh) -> np.ndarray:
    """Der Sprung des Krümmungsradius über jede Nachbarschaft, als Anteil.

    **Einmal je Körper, nicht einmal je Fleck.** Sie ist hier eine eigene
    Funktion, weil sie über *alle* Nachbarpaare rechnet: Aus
    :func:`_split_patches_by_curvature` heraus aufgerufen lief sie für jeden Fleck neu,
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


def _split_patches_by_curvature(
    body: trimesh.Trimesh,
    patches: list[list[int]],
    jump: np.ndarray,
    *,
    worth_splitting: np.ndarray | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> list[list[list[int]]]:
    """Flecken am **Sprung der Krümmung** in einem Körperdurchgang teilen.

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

    ``patches`` sind disjunkte Komponenten der kantenbegrenzten Suche. Der
    Besitz jedes Dreiecks ordnet deshalb ein Nachbarpaar eindeutig einem Fleck
    zu. Ein gemeinsamer Komponentenlauf beschriftet den ganzen Graphen; die
    anschließende Gruppierung je Originalfleck bewahrt dieselbe Reihenfolge von
    Gruppen und Dreiecken wie der frühere einzelne Durchgang.

    ``worth_splitting`` sagt je Fleck, ob seine Teilung überhaupt gebraucht
    wird; wo nicht, kommt der Fleck ungeteilt zurück (RM-132). Der Aufrufer
    weiß das und die Funktion nicht: :func:`_fitted` sieht ein Stück nur an,
    wenn sein Fleck mindestens :data:`MIN_PATCH_FACES` Dreiecke hat, und ein
    Stück ist nie größer als sein Fleck. **Auf einer Freiform ist das fast
    alles**: Der 200 000-Dreiecke-Körper aus den Leistungstests zerfällt in
    120 610 Flecken, von denen 1 650 groß genug sind. Die übrigen 118 960
    kosteten je einen ``np.unique``-Lauf und bei 8 229 von ihnen eine
    Gruppierung — 0,56 von 1,40 Sekunden der ganzen Erkennung, für Stücke, die
    niemand liest. Ohne die Maske bleibt es beim alten Verhalten: Jeder Fleck
    wird geteilt.
    """
    if check_cancelled is not None:
        check_cancelled()
    if not patches:
        return []

    pairs = np.asarray(body.face_adjacency)
    if not len(pairs):
        return [[patch] for patch in patches]

    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    owners = np.full(len(body.faces), -1, dtype=np.intp)
    for patch_index, patch in enumerate(patches):
        if check_cancelled is not None:
            check_cancelled()
        owners[np.asarray(patch, dtype=np.intp)] = patch_index

    eligible = (angles < CURVATURE_LIMIT) & (jump <= CURVATURE_JUMP)
    adjacency = np.asarray(pairs[eligible], dtype=np.intp)
    if len(adjacency):
        edge_owners = owners[adjacency[:, 0]]
        same_patch = (edge_owners >= 0) & (edge_owners == owners[adjacency[:, 1]])
        adjacency = adjacency[same_patch]
        edge_owners = edge_owners[same_patch]
    else:
        edge_owners = np.zeros(0, dtype=np.intp)
    if check_cancelled is not None:
        check_cancelled()

    order = np.argsort(edge_owners, kind="stable")
    edge_owners = edge_owners[order]
    adjacency = adjacency[order]
    boundaries = np.searchsorted(edge_owners, np.arange(len(patches) + 1), side="left")

    active = boundaries[1:] > boundaries[:-1]
    split: list[list[list[int]]] = []
    if not bool(active.any()):
        for patch in patches:
            if check_cancelled is not None:
                check_cancelled()
            split.append([patch])
        return split

    if check_cancelled is not None:
        check_cancelled()
    labels = trimesh.graph.connected_component_labels(adjacency, node_count=len(body.faces))
    if check_cancelled is not None:
        check_cancelled()

    for patch_index, patch in enumerate(patches):
        if check_cancelled is not None:
            check_cancelled()
        if not active[patch_index] or (
            worth_splitting is not None and not worth_splitting[patch_index]
        ):
            split.append([patch])
            continue
        nodes = np.unique(np.asarray(patch, dtype=np.intp))
        node_labels = labels[nodes]
        # Der häufige Fall bleibt trotz vorhandener Kanten ein Fleck. Dafür
        # 48 000 einzelne Sorts anzustoßen kostete am 200k-Freiformkörper
        # 808 ms. Gleichheit aller Labels beantwortet dieselbe Frage direkt;
        # nur eine wirkliche Teilung braucht die allgemeine Gruppierung.
        if bool(np.all(node_labels == node_labels[0])):
            split.append([[int(index) for index in nodes]])
            continue
        groups = trimesh.grouping.group(node_labels, min_len=1)
        split.append([[int(index) for index in nodes[group]] for group in groups])
    return split


#: Unter diesem Schlüssel hält der Cache von ``trimesh`` den Nachbarindex eines
#: Körpers — er lebt und stirbt mit dessen Geometrie wie ``face_adjacency``.
_NEIGHBOUR_INDEX_KEY: Final = "solidon_neighbour_index"


def _neighbour_index(body: trimesh.Trimesh) -> tuple[np.ndarray, np.ndarray]:
    """Je Dreieck seine Kantennachbarn und die Nummer der Naht dazu, einmal je Körper.

    ``face_adjacency`` ist eine Liste von Paaren über das ganze Netz. Wer
    daraus die Nachbarn **eines** Flecks lesen will, muss sie ganz durchgehen
    — und das taten :func:`_connected_patches` und :func:`_notch_faces` bei
    jedem Aufruf. Gemessen am Drachen aus TripoSG (325 244 Dreiecke, 190 mm,
    20.09.2026): 5 576 Aufrufe der Fleckenbildung und 23 610 der Randprüfung,
    jeder mit einer Maske über alle Dreiecke und einem Filter über alle
    488 000 Paare — 40 und 82 Sekunden, die nichts über den Fleck sagen.

    Zurück kommen zwei gepolsterte Felder derselben Form: die Nachbarn je
    Dreieck und die Zeile in ``face_adjacency``, aus der der Nachbar stammt
    (``-1`` wo keiner ist). Über die Zeilennummer bleibt die **Reihenfolge**
    der Paare erhalten — wer daraus wieder eine Paarliste baut, bekommt
    dieselbe Teilmenge in derselben Ordnung wie über den Filter, und damit
    dieselben Flecken in derselben Folge.
    """
    if _NEIGHBOUR_INDEX_KEY in body._cache:
        cached: tuple[np.ndarray, np.ndarray] = body._cache[_NEIGHBOUR_INDEX_KEY]
        return cached
    count = len(body.faces)
    pairs = np.asarray(body.face_adjacency, dtype=np.int64)
    if not len(pairs):
        empty = np.full((count, 0), -1, dtype=np.int64)
        body._cache[_NEIGHBOUR_INDEX_KEY] = (empty, empty)
        return empty, empty
    # Jede Naht zweimal, einmal von jeder Seite gesehen.
    faces = np.concatenate((pairs[:, 0], pairs[:, 1]))
    others = np.concatenate((pairs[:, 1], pairs[:, 0]))
    rows = np.concatenate((np.arange(len(pairs)), np.arange(len(pairs))))
    order = np.argsort(faces, kind="stable")
    faces, others, rows = faces[order], others[order], rows[order]
    # Spalte = laufende Nummer innerhalb desselben Dreiecks. Drei sind es an
    # einem sauberen Netz; die Breite folgt trotzdem dem Netz, damit ein
    # Dreieck mit mehr Nachbarn keinen davon verliert.
    first = np.r_[0, np.flatnonzero(np.diff(faces)) + 1]
    sizes = np.diff(np.r_[first, len(faces)])
    slot = np.arange(len(faces)) - np.repeat(first, sizes)
    width = int(sizes.max()) if len(sizes) else 0
    neighbours = np.full((count, width), -1, dtype=np.int64)
    pair_rows = np.full((count, width), -1, dtype=np.int64)
    neighbours[faces, slot] = others
    pair_rows[faces, slot] = rows
    body._cache[_NEIGHBOUR_INDEX_KEY] = (neighbours, pair_rows)
    return neighbours, pair_rows


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
    result: list[list[int]] = remembered(
        "connected_patches",
        body,
        faces,
        lambda: _connected_patches_read(body, faces),
    )
    return result


def _connected_patches_read(body: trimesh.Trimesh, faces: list[int]) -> list[list[int]]:
    """Der Rumpf von :func:`_connected_patches` — die Antwort merkt sich die Hülle."""
    pairs = np.asarray(body.face_adjacency)
    adjacency = pairs[:0]
    if len(pairs):
        # **Nur die Nähte dieses Flecks, nicht alle des Netzes** (20.09.2026).
        # Die Auswahl lief als Winkelfilter über alle Paare und eine Maske
        # über alle Dreiecke — je Aufruf, und :func:`_cylinder_beside_a_torus`
        # ruft je Splitstück. Am Drachen aus TripoSG waren das 5 576 Aufrufe
        # und 40 Sekunden. Der Nachbarindex liefert dieselben Paare über die
        # Nummer ihrer Zeile in ``face_adjacency``; ``np.unique`` darüber gibt
        # sie in derselben Reihenfolge zurück wie der Filter — die Flecken
        # kommen also in derselben Folge heraus.
        #
        # **Beide Enden werden geprüft, obwohl ``connected_components`` das
        # auch tut** (es verwirft Kanten, deren Knoten nicht in ``nodes``
        # stehen). Die Aussage „ein Fleck besteht nur aus den gewünschten
        # Dreiecken" gehört hierher und nicht in eine fremde Bibliothek. Ein
        # Test dafür gibt es aus demselben Grund nicht: Weggelassen ändert
        # sich keine Antwort.
        indices = np.asarray(faces, dtype=np.intp)
        wanted = np.zeros(len(body.faces), dtype=bool)
        wanted[indices] = True
        neighbours, pair_rows = _neighbour_index(body)
        chosen = neighbours[indices]
        present = chosen >= 0
        present[present] = wanted[chosen[present]]
        # Dieselben Zeilen in derselben aufsteigenden Ordnung wie ``np.unique``,
        # nur ohne Sortierung: eine Maske über die Nähte.
        seen = np.zeros(len(pairs), dtype=bool)
        seen[pair_rows[indices][present]] = True
        rows = np.flatnonzero(seen)
        angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float)[rows])
        adjacency = pairs[rows[angles < CURVATURE_LIMIT]]
    if not len(adjacency):
        return [[index] for index in faces]
    groups = trimesh.graph.connected_components(adjacency, nodes=np.asarray(faces), engine="scipy")
    return _without_notches(body, [group.tolist() for group in groups])


class _Rim(NamedTuple):
    """Der Rand eines Flecks, so gezählt, dass ein Dreieck mehr sich lokal prüfen lässt."""

    #: Kantencode → wie viele Dreiecke des Flecks an dieser Kante liegen (eins
    #: oder zwei; eine dritte macht den Fleck unbrauchbar).
    counts: dict[int, int]
    #: Knoten → wie viele Randkanten des Flecks dort zusammenlaufen.
    degrees: dict[int, int]
    #: Die Knoten, an denen mehr als zwei Randkanten zusammenlaufen.
    frayed: frozenset[int]


def _edge_codes(faces: np.ndarray, corners: int) -> np.ndarray:
    """Die drei Kanten jedes Dreiecks als je eine Zahl, in Dreiecksreihenfolge."""
    edges = np.sort(np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1)
    return np.asarray(edges[:, 0].astype(np.int64) * corners + edges[:, 1], dtype=np.int64)


def _rim_of(body: trimesh.Trimesh, patch: Sequence[int]) -> _Rim | None:
    """Rand und ausgefranste Knoten eines Flecks — ``None``, wenn er unbrauchbar ist.

    Unbrauchbar heißt: eine Kante trägt drei Dreiecke des Flecks. Dort ist
    nichts zu heilen, und es wird auch nichts gezählt.
    """
    indices = np.asarray(patch, dtype=np.int64)
    if len(indices) < 3:
        return None
    faces = np.asarray(body.faces)[indices]
    # **Eine Kante als eine Zahl** (Leistung, gemessen 17.09.2026). ``np.unique``
    # über ein zweispaltiges Feld sortiert lexikografisch und kostete an einem
    # merkmalsreichen Körper mit 204 000 Dreiecken ein Drittel der ganzen
    # Erkennung. Dieselbe Kodierung benutzt ``relations._shoulder_connections``,
    # und aus demselben Grund.
    corners = len(body.vertices)
    codes = _edge_codes(faces, corners)
    unique, count = np.unique(codes, return_counts=True)
    if (count > 2).any():
        return None
    border = unique[count == 1]
    if not len(border):
        return _Rim({}, {}, frozenset())
    ends = np.column_stack((border // corners, border % corners))
    vertices, degrees = np.unique(ends, return_counts=True)
    frayed = frozenset(int(node) for node in vertices[degrees > 2])
    if not frayed:
        return _Rim({}, {}, frozenset())
    # Die Wörterbücher entstehen nur, wenn jemand sie liest — an einem Fleck
    # aus dreihunderttausend Dreiecken sind es eine Million Kanten.
    return _Rim(
        dict(zip(unique.tolist(), count.tolist(), strict=True)),
        dict(zip(vertices.tolist(), degrees.tolist(), strict=True)),
        frayed,
    )


def _notch_faces(body: trimesh.Trimesh, patch: Sequence[int]) -> set[int]:
    """Die Dreiecke, die einen ausgefransten Randknoten dieses Flecks schließen.

    Ein Fleck ist erst brauchbar, wenn sein Rand aus geschlossenen Ringen
    besteht: ``relations.boundary_rings`` verlangt an jedem Randknoten genau
    zwei Randkanten und gibt sonst gar nichts zurück — und ohne Ringe gibt es
    keine Nachbarschaft, also keine Bohrungskette. Fehlt einem Band von
    Dreiecken ein einziges, laufen dort vier Randkanten zusammen, und der
    ganze Zusammenhang ist weg.

    **Der Fall ist gemessen und plattformabhängig** (17.09.2026). Die Senkung
    aus ``test_shrinking_keeps_the_countersink_and_recognises_the_new_shoulder``
    hat auf Windows und Ubuntu 241 Dreiecke, auf dem Mac der CI 240 — bei
    identischen Maßen (Ø 11,928 bei 89,838 Grad) und identischen Bohrungen
    daneben. Welches Dreieck herausfällt, entscheidet die letzte Stelle einer
    Normalen; dass **eines** herausfällt, macht aus zwei Randringen einen und
    kostet die ganze Kette.

    Geheilt wird nur die Kerbe, und nur wenn sie eindeutig ist: Das Dreieck
    liegt am ausgefransten Knoten, gehört keinem anderen Fleck, und der Rand
    ist danach sauber. Alles andere bleibt, wie die Einpassung es vorfindet —
    ein Fleck, der aus einem anderen Grund offen ist, wird hier nicht zugenäht.

    **Gesucht wird am Knoten, nicht im Netz** (20.09.2026). Die Nachbarn kamen
    aus einem Filter über alle Paare von ``face_adjacency``, je Aufruf — und
    :func:`_closing_set` ruft je Kandidatenmenge. Am Drachen aus TripoSG trug
    ein Fleck aus 307 063 Dreiecken 65 Kandidaten, das sind 2 145 Mengen, und
    jede Prüfung lief noch einmal über den ganzen Fleck und das ganze Netz:
    264 von 482 Sekunden. Jetzt sagt der Index Ecke → Dreiecke
    (:func:`_vertex_faces_index`), welche Dreiecke am ausgefransten Knoten
    liegen, und der Nachbarindex, welche davon an den Fleck grenzen — dieselbe
    Menge, gelesen an der Stelle, um die es geht.
    """
    rim = _rim_of(body, patch)
    if rim is None or not rim.frayed:
        return set()
    return _candidates_at(body, patch, rim.frayed)


#: Unter diesem Schlüssel hält der Cache von ``trimesh`` den Index Ecke → Dreiecke
#: eines Körpers — wie :data:`_NEIGHBOUR_INDEX_KEY` lebt er mit der Geometrie.
_VERTEX_FACES_KEY: Final = "solidon_vertex_faces"


def _vertex_faces_index(body: trimesh.Trimesh) -> tuple[np.ndarray, np.ndarray]:
    """Je Ecke die Dreiecke, die sie tragen — als gepackter Index, einmal je Körper.

    ``trimesh.vertex_faces`` baut dieselbe Auskunft über ein dünnbesetztes
    Produkt und fällt, sobald **ein** Dreieck entartet ist, in eine
    Python-Schleife je Ecke über alle Dreiecke: 37 ms bei 10 000, 20 s bei
    300 000, sechs Minuten bei 1,3 Millionen (gemessen 21.09.2026) — und ein
    Generatornetz aus TripoSG löst das je Auswertung zweimal aus. Hier: die
    Ecken aller Dreiecke stabil sortiert, die Dreiecksnummer ist die Position
    durch drei, und die Zähler je Ecke geben die Ränge. 19 ms bei 300 000,
    entartet oder nicht.

    Zurück kommen ``ranges`` mit ``len(vertices) + 1`` Einträgen und die
    Dreiecke; die Dreiecke der Ecke ``v`` stehen in
    ``faces[ranges[v] : ranges[v + 1]]``. Ein entartetes Dreieck ``(a, a, b)``
    steht bei ``a`` zweimal — wer Mengen bildet, merkt es nicht.
    """
    if _VERTEX_FACES_KEY in body._cache:
        cached: tuple[np.ndarray, np.ndarray] = body._cache[_VERTEX_FACES_KEY]
        return cached
    corners = np.asarray(body.faces, dtype=np.int64).ravel()
    order = np.argsort(corners, kind="stable")
    counts = np.bincount(corners, minlength=len(body.vertices))
    ranges = np.zeros(len(counts) + 1, dtype=np.int64)
    np.cumsum(counts, out=ranges[1:])
    faces = order // 3
    body._cache[_VERTEX_FACES_KEY] = (ranges, faces)
    return ranges, faces


def _candidates_at(body: trimesh.Trimesh, patch: Sequence[int], frayed: frozenset[int]) -> set[int]:
    """Die Dreiecke außerhalb des Flecks, die an ihn grenzen und einen fransigen Knoten tragen."""
    inside = np.zeros(len(body.faces), dtype=bool)
    inside[np.asarray(patch, dtype=np.intp)] = True
    neighbours, _rows = _neighbour_index(body)
    ranges, vertex_faces = _vertex_faces_index(body)
    found: set[int] = set()
    for node in frayed:
        for face in vertex_faces[ranges[node] : ranges[node + 1]]:
            if inside[face]:
                continue
            # Nur die unmittelbaren Nachbarn des Flecks kommen in Frage: Ein
            # Dreieck, das den Knoten teilt, aber nirgends anliegt, schließt
            # keine Kerbe.
            beside = neighbours[face]
            beside = beside[beside >= 0]
            if len(beside) and inside[beside].any():
                found.add(int(face))
    return found


#: Wie viele freie Dreiecke eine Kerbe höchstens schließen dürfen.
#:
#: Eine Kerbe ist eine Lücke von ein, zwei Dreiecken — ein Kegelsegment
#: besteht aus einem koplanaren Paar, und mehr als ein Segment fällt nicht
#: heraus. Was drei und mehr braucht, ist keine Kerbe mehr, sondern ein Loch,
#: und ein Loch zuzunähen wäre eine Erfindung.
NOTCH_AT_MOST: Final = 2


def _without_notches(body: trimesh.Trimesh, patches: list[list[int]]) -> list[list[int]]:
    """Fransige Ränder schließen, solange die Menge dafür frei, klein und eindeutig ist.

    **Eindeutig heißt: genau eine Menge ihrer Größe** (Regel 21). Am
    ausgefransten Knoten liegen mehrere freie Dreiecke — auf dem Mac der CI
    gemessen vier —, und keines davon bringt den Rand allein in Ordnung.
    Gesucht wird deshalb die **kleinste** Menge, die es tut; gibt es davon zwei
    derselben Größe, steht dort eine Gabelung, und die zu raten wäre schlimmer,
    als die Kerbe stehen zu lassen.
    """
    taken = {index for patch in patches for index in patch}
    healed: list[list[int]] = []
    for patch in patches:
        # **Nur Flecken, die überhaupt eingepasst werden** (Leistung, gemessen
        # 17.09.2026). Die Randprüfung kostet je Fleck ein ``np.unique`` über
        # seine Kanten; an einer verrauschten Freiform sind es 120 610 Flecken,
        # und drei Leistungstests rissen ihre Schwelle. Was unter
        # ``MIN_PATCH_FACES`` liegt, kommt an ``classify`` ohnehin nicht vorbei
        # — dort steht dieselbe Grenze.
        if len(patch) < MIN_PATCH_FACES:
            healed.append(patch)
            continue
        rim = _rim_of(body, patch)
        if rim is None or not rim.frayed:
            healed.append(patch)
            continue
        candidates = sorted(
            face for face in _candidates_at(body, patch, rim.frayed) if face not in taken
        )
        closing = _closing_set(body, rim, candidates)
        if closing is None:
            healed.append(patch)
            continue
        taken.update(closing)
        healed.append([*patch, *closing])
    return healed


def _closing_set(
    body: trimesh.Trimesh, rim: _Rim, candidates: Sequence[int]
) -> tuple[int, ...] | None:
    """Die kleinste eindeutige Menge freier Dreiecke, die den Rand schließt.

    **Geprüft wird am Rand, nicht am Fleck.** Ob eine Menge den Rand in
    Ordnung bringt, entscheidet sich an ihren eigenen Kanten: Eine Randkante,
    die ein Dreieck der Menge belegt, hört auf, Rand zu sein; eine Kante, die
    der Fleck nicht kannte, wird Rand. Beides ändert den Grad nur an den Ecken
    der Menge. Die Zählung des Flecks (:class:`_Rim`) steht einmal, und jede
    Menge kostet danach ein Dutzend Nachschläge statt eines Durchgangs über
    alle Dreiecke — am Drachen aus TripoSG waren es 2 145 Durchgänge über
    307 063 Dreiecke.

    **Sauber heißt sauber.** Vorher galt eine Menge als schließend, wenn danach
    keine Kandidaten mehr zu finden waren — das traf auch eine Kante mit drei
    Dreiecken und einen Knoten, der fransig blieb, aber am Rand des Netzes
    ohne freie Nachbarn lag. Jetzt heißt schließend: keine Kante dreifach, kein
    Randknoten mit mehr als zwei Randkanten. An geschlossenen Netzen ist das
    dieselbe Antwort; an offenen die ehrlichere.
    """
    if not candidates:
        return None
    corners = len(body.vertices)
    triangles = np.asarray(body.faces)
    for size in range(1, NOTCH_AT_MOST + 1):
        found = [
            group
            for group in itertools.combinations(candidates, size)
            if _closes(rim, _edge_codes(triangles[list(group)], corners), corners)
        ]
        if len(found) == 1:
            return found[0]
        if found:
            # Mehrere Mengen derselben Größe: eine Gabelung, keine Kerbe.
            return None
    return None


def _closes(rim: _Rim, codes: np.ndarray, corners: int) -> bool:
    """Ob die Dreiecke mit diesen Kanten jeden fransigen Knoten des Rands in Ordnung bringen."""
    added: dict[int, int] = {}
    for code in codes.tolist():
        added[code] = added.get(code, 0) + 1
    change: dict[int, int] = {}
    for code, more in added.items():
        before = rim.counts.get(code, 0)
        after = before + more
        if after > 2:
            return False
        if before == 1:
            # Eine Randkante wird zur Innenkante.
            step = -1
        elif after == 1:
            # Eine neue Kante wird Rand.
            step = 1
        else:
            continue
        for node in (code // corners, code % corners):
            change[node] = change.get(node, 0) + step
    if any(rim.degrees.get(node, 0) + step > 2 for node, step in change.items()):
        return False
    return all(node in change for node in rim.frayed)


# --- Flächen ---------------------------------------------------------------------


def _planar_face_entries(
    mesh: MeshData,
    *,
    planar: set[int] | None = None,
    check_cancelled: Callable[[], None] | None = None,
    all_facets: bool = False,
) -> list[tuple[np.ndarray, float, np.ndarray]]:
    """Dieselben belegten Ebenen für vollständige Erkennung und lokale Rollenprüfung."""
    body = mesh.raw
    facets = list(body.facets)
    if not facets:
        return []

    areas = _facet_areas(body, facets)
    # Dieselbe Schwelle, die die Bohrungserkennung benutzt — ein Fleck ist also
    # entweder eine Fläche oder Teil einer gekrümmten Oberfläche, nie beides,
    # nie keines. Was auf einer Rundung sitzt, wird dort als Zylinder gemeldet
    # und hier nicht noch einmal als achtundvierzig Rechtecke.
    if planar is None and not all_facets:
        planar = _large_facet_faces(body, check_cancelled=check_cancelled)
    if check_cancelled is not None:
        check_cancelled()
    # Unter der Schranke zählt nur, was seine Ränder belegen — derselbe
    # Beleg, den ``_large_facet_faces`` liest, auch bei ``all_facets``: Die
    # lokale Rollenprüfung darf eine echte kleine Fläche nicht übergehen.
    apart = _facets_standing_apart(body, facets, _curved_faces(body))
    return [
        (facet, area, _facet_centre(body, facet))
        for number, (facet, area) in enumerate(zip(facets, areas, strict=True))
        if (area >= MIN_FACE_AREA or number in apart)
        and (planar is None or all(int(index) in planar for index in facet))
        and bool(
            np.all(
                np.asarray(body.face_normals)[facet] @ body.face_normals[int(facet[0])]
                >= units.exact_cos_degrees(EPS_ANGLE)
            )
        )
    ]


def detect_faces(
    mesh: MeshData,
    *,
    planar: set[int] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Feature]:
    """Koplanare Flecken: Normale, Fläche, Mittelpunkt (§21.1)."""
    body = mesh.raw
    entries = _planar_face_entries(mesh, planar=planar, check_cancelled=check_cancelled)
    # **Bei gleicher Fläche entscheiden die Eckennummern der Fläche.**
    # Die sechs Flächen eines Würfels sind exakt gleich groß; sortiert allein
    # nach Fläche hing es an der Reihenfolge der Dreiecke im Netz, welche davon
    # ``face_1`` wird — dieselbe Geometrie mit anders nummerierten Dreiecken
    # gab eine andere Zuordnung. Die Zuordnung (§21.2) fängt das im
    # Regelbetrieb wieder ein, weil sie über die Lage vergleicht; die
    # **Ersterkennung** hat nichts, womit sie vergleichen könnte.
    #
    # **Und ausdrücklich nicht der Ort**, obwohl er sich anbietet. Eine
    # Nummerierung nach Koordinaten überlebt keine Drehung: Bei einer Platte
    # sind Deck- und Bodenfläche gleich groß, und um zwanzig Grad gekippt
    # tauschen sie ihre Reihenfolge. Genau darauf steht ein Teil des
    # Bestands — ``align`` legt ``face_1`` eines gedrehten Teils auf
    # ``face_1`` des festen, und beide müssen dieselbe Fläche des Teils
    # meinen. Die kleinste Eckennummer ändert sich weder beim Drehen noch beim
    # Umsortieren der Dreiecke. Genommen werden alle Ecken der Fläche und
    # nicht bloß die kleinste: An einem Würfel treffen sich drei Flächen in
    # derselben Ecke, und drei gleiche Schlüssel sind so gut wie keiner.
    #
    # Gerundet wird auch die Fläche, aus demselben Grund: Zwei gleich große
    # Flächen unterscheiden sich im Netz gern in der zwölften Stelle, und dann
    # entschiede wieder diese Stelle.
    entries.sort(key=lambda entry: (-round(entry[1], 4), _corner_key(body, entry[0])))
    return _finished_faces(mesh, _face_candidates(body, entries), entries, check_cancelled)


#: Die Facetten einer Flächensuche, für das Fertigstellen der Flächen, die
#: nach dem Musterfalten übrig sind — siehe :func:`_face_candidates`.
FaceEntries = list[tuple[np.ndarray, float, np.ndarray]]


def _face_candidates(body: trimesh.Trimesh, entries: FaceEntries) -> list[Feature]:
    """Die Flächen mit Name, Fläche, Normale und Mitte — ohne Träger und Innenlage.

    Träger (:func:`planar_patch`) und Innenlage (:func:`_face_roles`) kosten
    je Fläche, und ein dichtes Rändel hat 32 000 Flächen, von denen nach dem
    Musterfalten sieben bleiben (22.09.2026: 3,7 und 2,9 s von 17). Deshalb
    entstehen die Flächen in zwei Schritten: erst alle, billig, dann die, die
    bleiben, fertig (:func:`_finished_faces`). Wer :func:`detect_faces` ruft,
    bekommt beides in einem.
    """
    features: list[Feature] = []
    for number, (facet, area, centre) in enumerate(entries, start=1):
        normal = body.face_normals[facet[0]]
        features.append(
            Feature(
                id=f"face_{number}",
                kind="face",
                provenance="detected",
                measure_sources={"area": "facets", "normal": "facets", "centre": "facets"},
                params={
                    "area": round(area, 4),
                    "normal": (float(normal[0]), float(normal[1]), float(normal[2])),
                    "centre": (float(centre[0]), float(centre[1]), float(centre[2])),
                },
                face_indices=tuple(int(index) for index in facet),
            )
        )
    return features


def _finished_faces(
    mesh: MeshData,
    features: Sequence[Feature],
    entries: FaceEntries,
    check_cancelled: Callable[[], None] | None,
) -> list[Feature]:
    """Träger und Innenlage für diese Flächen — die Facetten aller bleiben die Zeugen."""
    finished: list[Feature] = []
    for feature in features:
        if check_cancelled is not None:
            check_cancelled()
        centre = feature.params["centre"]
        normal = feature.params["normal"]
        plane = planar_patch(
            mesh,
            np.asarray(feature.face_indices, dtype=np.int64),
            (float(centre[0]), float(centre[1]), float(centre[2])),
            (float(normal[0]), float(normal[1]), float(normal[2])),
            check_cancelled=check_cancelled,
        )
        finished.append(replace(feature, surface_patches=(plane,) if plane is not None else ()))
    roles = _face_roles(mesh, finished, entries, check_cancelled)
    return [
        replace(feature, params={**feature.params, "inner": roles[feature.id]})
        for feature in finished
    ]


def _faces_on_a_round_wall(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Eine ebene Fläche auf dem Mantel eines erkannten Zylinders gehört ihm.

    Ein Mantelstreifen ist eine Facette der Rundung und keine Fläche. Das
    sagt sonst die Naht zu seinen Nachbarn (:func:`_curved_faces`): Zwischen
    zwei Facetten steht ein kleiner Winkel, und daran hängt die ganze
    Rückgewinnung in :func:`_large_facet_faces`. **Wo links und rechts eine
    Nut liegt, hat ein Streifen diese Naht nicht mehr** — er grenzt nur noch
    an Wände unter 90 Grad. Nach dem Neuzeichnen eines umlaufenden Musters
    blieb so ein Streifen von 0,45 mm Breite und 10 mm² als eigene Fläche im
    Baum stehen (22.09.2026, RM-207); im Bild ist er ein Stück Mantel.

    Gefragt wird deshalb die **Lage**, und erst hier, wo die Einpassungen
    stehen: Die Normale der Fläche steht senkrecht auf der Achse, ihre Ecken
    liegen auf dem Mantel, und ihre Dreiecksmitten sinken nicht tiefer als
    eine Tessellierung darunter (:data:`units.MAX_FACET_SAG`). Der dritte
    Punkt trennt sie von einer **Abflachung**: Deren Ecken liegen ebenfalls
    auf dem Mantel — sie sind sein Schnittkreis —, ihre Mitte aber
    Millimeter darunter (gemessen am 22.09.2026 an einem Zylinder Ø 30 mit
    einer Abflachung von 449 mm²: Ecken 0,0007 mm, Mitten 7,4 mm).
    """
    walls = [
        feature
        for feature in found.values()
        if feature.kind in ROUND_WALL_KINDS and "axis" in feature.params and feature.face_indices
    ]
    faces = [
        feature for feature in found.values() if feature.kind == "face" and feature.face_indices
    ]
    if not walls or not faces:
        return dict(found)
    body = _one_body(mesh).raw
    points = np.asarray(body.vertices, dtype=float)
    triangles = np.asarray(body.faces, dtype=np.int64)
    centres = np.asarray(body.triangles_center, dtype=float)
    axes = np.array([feature.params["axis"] for feature in walls], dtype=float)
    axes = axes / np.maximum(np.linalg.norm(axes, axis=1), EPS_GEOM)[:, None]
    origins = np.array([feature.params["centre"] for feature in walls], dtype=float)
    radii = np.array([float(feature.params.get("diameter", 0.0)) / 2.0 for feature in walls])
    swallowed: dict[FeatureId, list[int]] = {}
    for feature in faces:
        if check_cancelled is not None:
            check_cancelled()
        normal = np.asarray(feature.params.get("normal", (0.0, 0.0, 0.0)), dtype=float)
        centre = np.asarray(feature.params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
        # Zwei billige Fragen an alle Mäntel auf einmal: Steht die Fläche
        # tangential, und liegt ihre Mitte auf dem Radius? Erst was beides
        # besteht, wird Ecke für Ecke geprüft.
        offset = centre - origins
        beside = offset - axes * (offset * axes).sum(axis=1)[:, None]
        near = (np.abs(axes @ normal) <= PLANE_ON_A_WALL) & (
            np.abs(np.linalg.norm(beside, axis=1) - radii) <= units.MAX_FACET_SAG
        )
        indices = np.asarray(feature.face_indices, dtype=np.int64)
        indices = indices[(indices >= 0) & (indices < len(triangles))]
        if not near.any() or indices.size == 0:
            continue
        corners = points[np.unique(triangles[indices])]
        for number in np.flatnonzero(near):
            axis, origin, radius = axes[number], origins[number], radii[number]
            if radius <= EPS_GEOM:
                continue
            reach = np.linalg.norm(_beside_axis(corners - origin, axis), axis=1)
            if float(np.abs(reach - radius).max()) > units.MAX_FACET_SAG:
                continue
            sunk = np.linalg.norm(_beside_axis(centres[indices] - origin, axis), axis=1)
            if float((radius - sunk).max()) > units.MAX_FACET_SAG:
                continue
            swallowed.setdefault(walls[int(number)].id, []).extend(int(index) for index in indices)
            break
    if not swallowed:
        return dict(found)
    taken = {name for name, feature in found.items() if feature.kind == "face"}
    kept: dict[FeatureId, Feature] = {}
    for name, feature in found.items():
        if name in swallowed:
            kept[name] = replace(
                feature,
                face_indices=tuple(sorted({*feature.face_indices, *swallowed[name]})),
            )
            continue
        if feature.kind == "face" and name in taken:
            own = set(feature.face_indices)
            if any(own <= set(indices) for indices in swallowed.values()):
                continue
        kept[name] = feature
    return kept


def _beside_axis(offset: np.ndarray, axis: np.ndarray) -> np.ndarray:
    """Der Anteil eines Versatzes quer zur Achse — der Abstand davon ist der Radius."""
    return np.asarray(offset - np.outer(offset @ axis, axis), dtype=float)


def _faces_finished_in(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    entries: FaceEntries,
    check_cancelled: Callable[[], None] | None,
) -> dict[FeatureId, Feature]:
    """Dieselbe Merkmalsliste, die übrigen Flächen fertig — Reihenfolge und Namen bleiben."""
    pending = [feature for feature in found.values() if feature.kind == "face"]
    finished = _finished_faces(mesh, pending, entries, check_cancelled)
    done = {feature.id: feature for feature in finished}
    return {name: done.get(name, feature) for name, feature in found.items()}


def face_roles(
    mesh: MeshData,
    features: Sequence[Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
    check_patch_size: Callable[[int], None] | None = None,
) -> dict[FeatureId, bool]:
    """Nur angefragte Ebenen anhand räumlich passender Originalfacetten einordnen."""
    if not features:
        return {}
    entries = _planar_face_entries(mesh, check_cancelled=check_cancelled, all_facets=True)
    accepted: dict[int, bool] = {}

    def eligible(facet: np.ndarray) -> bool:
        """Nur ein räumlich passender Beleg benötigt die aufwendige Mantelgegenprobe."""
        first = int(facet[0])
        if first not in accepted:
            requested = {int(index) for index in facet}
            planar = _large_facet_faces(
                mesh.raw,
                check_cancelled=check_cancelled,
                requested=requested,
                check_patch_size=check_patch_size,
            )
            accepted[first] = requested <= planar
        return accepted[first]

    return _face_roles(mesh, features, entries, check_cancelled, eligible)


def _face_roles(
    mesh: MeshData,
    features: Sequence[Feature],
    entries: Sequence[tuple[np.ndarray, float, np.ndarray]],
    check_cancelled: Callable[[], None] | None,
    eligible: Callable[[np.ndarray], bool] | None = None,
) -> dict[FeatureId, bool]:
    """Eine gemeinsame Innenregel; der Suchradius begrenzt keine räumlichen Belege."""
    if not entries or not features:
        return {feature.id: False for feature in features}
    body = mesh.raw

    # Eine parallele Fläche zählt nur auf derselben Schale und über dem
    # örtlichen Flächenmittelpunkt. Ihre äußere Kontur schließt eine Öffnung
    # mit ein: Der Boden einer Dose liegt unter deren Rand, obwohl durch die
    # Öffnung nach oben freie Sicht besteht. Eine seitlich versetzte Lippe
    # oder ein zweiter Körper belegt dagegen keine Innenlage.
    import shapely
    from shapely.geometry import MultiPoint

    normals = np.asarray([body.face_normals[facet[0]] for facet, _a, _c in entries], dtype=float)
    centres = np.asarray([centre for _f, _a, centre in entries], dtype=float)
    shell = np.empty(len(body.faces), dtype=np.intp)
    for number, component in enumerate(face_components(body)):
        shell[component] = number
    entry_shells = np.asarray([shell[int(facet[0])] for facet, _a, _c in entries])
    vertices = np.asarray(body.vertices)
    faces = np.asarray(body.faces)
    # Die zwei Basisvektoren jeder Fläche in einem Zug — dieselbe Rechnung
    # wie :func:`_plane_basis`, über alle Flächen zugleich.
    helpers = np.where(
        (np.abs(normals[:, 0]) < 0.9)[:, None],
        np.array([1.0, 0.0, 0.0])[None, :],
        np.array([0.0, 1.0, 0.0])[None, :],
    )
    basis_u = np.cross(normals, helpers)
    basis_u = basis_u / np.linalg.norm(basis_u, axis=1)[:, None]
    basis_v = np.cross(normals, basis_u)
    # Je Kandidatenfläche ihre Kontur in der eigenen Ebene — einmal gebildet,
    # für jede Fläche, die sie fragt.
    outlines: dict[int, Any] = {}

    def outline_of(other: int) -> Any:
        if other not in outlines:
            corners = vertices[np.unique(faces[entries[other][0]])] - centres[other]
            footprint = MultiPoint(
                np.column_stack((corners @ basis_u[other], corners @ basis_v[other]))
            )
            outlines[other] = footprint.convex_hull
        return outlines[other]

    # **Gleichgerichtete Flächen fragen einen Baum, nicht jede Fläche jede.**
    # Ein Kreuzrändel mit 6 645 Rauten trägt 32 140 Wände in vier Richtungen;
    # jede Wand hatte rund 770 parallele Kandidaten, und die Frage „deckt
    # eine davon meine Mitte?" lief blockweise über alle — 24,7 Millionen
    # Konturen, 32 von 40 s der Erkennung (22.09.2026). Flächen mit
    # **derselben** Normalen (auf sechs Stellen) teilen dieselbe Ebenenbasis,
    # und dann ist die Frage eine an einen STRtree über ihre Konturen:
    # dieselbe Antwort, denn die Kontur in der eigenen Basis um die eigene
    # Mitte ist die Kontur in der gemeinsamen Basis um den Ursprung, nur
    # verschoben. Was nur *fast* gleichgerichtet ist (bis
    # :data:`PARALLEL_FACE_COSINE`), geht weiter den blockweisen Weg — dort
    # trägt jede Kontur ihre eigene Basis, und eine gemeinsame verschöbe den
    # Punkt um bis zu 14 mm auf 100.
    keys = np.round(normals, 6)
    unique_keys, key_of = np.unique(keys, axis=0, return_inverse=True)
    key_of = np.asarray(key_of).ravel()
    key_index = {tuple(row): number for number, row in enumerate(unique_keys.tolist())}
    trees: dict[int, tuple[Any, np.ndarray]] = {}

    def tree_of(key: int) -> tuple[Any, np.ndarray]:
        """Der Baum über die Konturen aller Flächen einer Richtung, einmal gebaut."""
        if key not in trees:
            members = np.flatnonzero(key_of == key)
            # Eine Basis für alle — die des ersten Mitglieds. Nahe der
            # Hilfsvektorgrenze wählten zwei fast gleiche Normalen sonst zwei
            # verschiedene Basen, und der Punkt läge in der falschen Kontur.
            along, across = basis_u[members[0]], basis_v[members[0]]
            hulls = []
            for other in members:
                corners = vertices[np.unique(faces[entries[int(other)][0]])]
                hulls.append(
                    MultiPoint(np.column_stack((corners @ along, corners @ across))).convex_hull
                )
            trees[key] = (shapely.STRtree(hulls), members)
        return trees[key]

    # Welche anderen Richtungen einer Richtung noch nahe genug sind — eine
    # Frage je Richtungspaar, nicht je Fläche: Vier Wandrichtungen und zwei
    # Deckel sind sechs, die Flächen sind 32 000.
    unit_normals = unique_keys / np.maximum(np.linalg.norm(unique_keys, axis=1), EPS_GEOM)[:, None]
    near = (unit_normals @ unit_normals.T > PARALLEL_FACE_COSINE) & ~np.eye(
        len(unique_keys), dtype=bool
    )
    roles: dict[FeatureId, bool] = {}
    for feature in features:
        if check_cancelled is not None:
            check_cancelled()
        normal = np.asarray(feature.params["normal"], dtype=float)
        centre = np.asarray(feature.params["centre"], dtype=float)
        own_shell = shell[feature.face_indices[0]]
        inner = False
        own_key = key_index.get(tuple(np.round(normal, 6).tolist()))
        if own_key is not None:
            tree, members = tree_of(own_key)
            axis = members[0]
            flat = [[float(centre @ basis_u[axis]), float(centre @ basis_v[axis])]]
            point = shapely.points(flat)[0]
            # ``covered_by``: der Punkt, den eine Kontur des Baums deckt — das
            # Prädikat gilt vom Anfragepunkt aus, nicht von der Kontur.
            for other in members[tree.query(point, predicate="covered_by")]:
                if (
                    entry_shells[other] == own_shell
                    and float((centres[other] - centre) @ normal) > EPS_GEOM
                    and (eligible is None or eligible(entries[int(other)][0]))
                ):
                    inner = True
                    break
        if inner:
            roles[feature.id] = True
            continue
        if own_key is not None and not near[own_key].any():
            # Keine zweite Richtung nahe der eigenen: nichts mehr zu fragen —
            # und keine Maske über alle Flächen für eine leere Antwort.
            roles[feature.id] = False
            continue
        same_shell = entry_shells == own_shell
        above = (centres - centre) @ normal > EPS_GEOM
        alike = normals @ normal > PARALLEL_FACE_COSINE
        candidates = np.flatnonzero(same_shell & alike & above & (key_of != own_key))
        # **Blockweise, nicht ein Punkt und ein ``covers`` je Kandidat** —
        # und wie bisher nur bis zum ersten Treffer: Am Kumiko-Gitter mit
        # 7 295 Flächen hat jede Fläche rund 200 parallele Kandidaten, und
        # ein Punkt je Kandidat kostete 5,5 s im Hauptweg der
        # Flächenerkennung (gemessen am 21.09.2026).
        for start in range(0, len(candidates), FACE_ROLE_BLOCK):
            block = candidates[start : start + FACE_ROLE_BLOCK]
            offsets = centre - centres[block]
            coordinates = np.column_stack(
                (
                    np.einsum("ij,ij->i", offsets, basis_u[block]),
                    np.einsum("ij,ij->i", offsets, basis_v[block]),
                )
            )
            covered = shapely.covers(
                np.asarray([outline_of(int(other)) for other in block], dtype=object),
                shapely.points(coordinates),
            )
            if any(
                eligible is None or eligible(entries[int(other)][0])
                for other in block[np.asarray(covered, dtype=bool)]
            ):
                inner = True
                break
        roles[feature.id] = inner
    return roles


def detect_curved_faces(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Feature]:
    """Gerundete Seiten: glatte, nicht ebene Flecken, die kein Merkmal beansprucht.

    **Der Anlass** (Robert, 11.09.2026, am Schriftzug: „bei den Seiten fehlen
    die gerundeten flächen"): Ein D trug im Objektbaum Ober- und Unterseite,
    die linke und die rechte ebene Seite — den Bogen außen und den Bogen
    innen nicht. Die Einpassung fragt nach Zylindern, Kugeln, Ringen und
    Verrundungen, und ein Bogen über ein Drittel eines Kreises ist keines
    davon; die ebenen Flächen fragen nach Koplanarität. Dazwischen fiel die
    gerundete Seite durch — und Filament ließ sich ihr nicht zuweisen.

    **Der Rest, nicht die Regel.** Genommen wird, was die Rundungsnaht kennt
    (:func:`_curved_faces`: Dreiecke mit einem Nachbarn zwischen null Grad
    und :data:`CURVATURE_LIMIT`) und was **kein** anderes Merkmal in seinen
    ``face_indices`` führt; zusammenhängend über glatte Nähte, damit die
    zwei Bögen einer 3 zwei Seiten bleiben und nicht an ihrer scharfen Kante
    eine werden. Gemessen am Korpus (28 Netze, `tests/data/meshes`): keine
    einzige gerundete Seite auf Platten, Bohrungen, Stiften, Kugeln, Ringen
    und verrundeten Klötzen — alles dort ist beansprucht. Die ovale Öffnung
    eines o bleibt ebenfalls eine gerundete Seite; ein ähnlicher mittlerer
    Rückstand macht daraus noch kein Langloch.

    ``inner`` sagt, ob der Fleck hohl ist — wie die Innenwand eines D — und
    kommt aus der Konvexität seiner Nähte, nicht aus einem Vergleich mit
    anderen Flächen: Eine gerundete Seite hat keine Gegenseite mit gleicher
    Normale. Die Normale ist das flächengewichtete Mittel und bei einem
    geschlossenen Mantel entsprechend kurz — benannt wird über ``inner``,
    nicht über sie.
    """
    if check_cancelled is not None:
        check_cancelled()
    body = mesh.raw
    adjacency = np.asarray(body.face_adjacency, dtype=np.int64).reshape(-1, 2)
    if not len(adjacency):
        return []
    claimed: set[int] = set()
    for feature in found.values():
        if check_cancelled is not None:
            check_cancelled()
        claimed.update(feature.face_indices)
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    smooth = angles < CURVATURE_LIMIT
    rounded = set(adjacency[(angles > EPS_ANGLE) & smooth].ravel().tolist())
    free = np.asarray(sorted(rounded - claimed), dtype=np.int64)
    if not len(free):
        return []
    keep = np.isin(adjacency[:, 0], free) & np.isin(adjacency[:, 1], free) & smooth
    groups = trimesh.graph.connected_components(
        adjacency[keep], nodes=free, min_len=1, engine="scipy"
    )
    if check_cancelled is not None:
        check_cancelled()
    areas = np.asarray(body.area_faces, dtype=float)
    convex = np.asarray(body.face_adjacency_convex, dtype=bool)
    # **Gegen die ganze Oberfläche gemessen**, wie :data:`BROAD_FACE_SHARE`
    # bei den ebenen Flächen, nur enger: Auf ``generated_figure.stl`` blieben
    # zwischen sechs Kugeln sechs Flecken von 4 bis 40 mm² übrig — Übergänge,
    # keine Seiten. Ein Prozent der Haut lässt die zwei Bögen eines D (2315
    # und 3311 mm² an rund 20 000) stehen und die Übergänge fallen.
    floor = max(MIN_FACE_AREA, float(body.area) * CURVED_SIDE_SHARE)
    entries: list[tuple[np.ndarray, float]] = []
    for group in groups:
        if check_cancelled is not None:
            check_cancelled()
        patch = np.asarray(sorted(int(index) for index in group), dtype=np.int64)
        area = float(areas[patch].sum())
        if area < floor:
            continue
        entries.append((patch, area))
    # Größte zuerst, bei gleicher Fläche die Eckennummern — dieselbe
    # Stabilität wie bei den ebenen Flächen (:func:`detect_faces`).
    entries.sort(key=lambda entry: (-round(entry[1], 4), _corner_key(body, entry[0])))

    features: list[Feature] = []
    for number, (patch, area) in enumerate(entries, start=1):
        if check_cancelled is not None:
            check_cancelled()
        weights = areas[patch]
        normals = np.asarray(body.face_normals, dtype=float)[patch]
        mean = (normals * weights[:, None]).sum(axis=0) / max(float(weights.sum()), EPS_GEOM)
        # Koplanare Diagonalen im Mantel haben keine Krümmungsrichtung.
        # Mitgezählt stimmten sie an einer hohlen Rundwand genau halb gegen
        # die konkaven Nähte und machten deren Innenseite zur Außenseite.
        inside = (
            np.isin(adjacency[:, 0], patch) & np.isin(adjacency[:, 1], patch) & (angles > EPS_ANGLE)
        )
        seams = convex[inside]
        inner = bool(len(seams)) and float(np.count_nonzero(~seams)) > len(seams) / 2.0
        centre = _facet_centre(body, patch)
        features.append(
            Feature(
                id=f"curve_{number}",
                kind="curved_face",
                provenance="detected",
                measure_sources={"area": "facets", "normal": "facets", "centre": "facets"},
                params={
                    "area": round(area, 4),
                    "normal": (float(mean[0]), float(mean[1]), float(mean[2])),
                    "centre": (float(centre[0]), float(centre[1]), float(centre[2])),
                    "inner": inner,
                },
                face_indices=tuple(int(index) for index in patch),
            )
        )
    return features


def _corner_key(body: trimesh.Trimesh, facet: np.ndarray) -> tuple[int, ...]:
    """Die Eckennummern einer ebenen Fläche, aufsteigend — ihr Ausweis im Netz.

    Was diese Reihenfolge tragen muss, steht bei ihrem einzigen Aufrufer: Sie
    entscheidet bei gleich großen Flächen und darf sich deshalb weder beim
    Drehen des Körpers noch beim Umsortieren seiner Dreiecke ändern.
    """
    return tuple(int(index) for index in np.unique(body.faces[facet]))


def _facet_centre(body: trimesh.Trimesh, facet: np.ndarray) -> np.ndarray:
    """Der Mittelpunkt einer ebenen Fläche, **flächengewichtet**.

    Nicht als Mittel über die Dreiecke: sonst hängt der Mittelpunkt an der
    Vernetzung statt an der Form. Eine Bohrung in eine Platte lässt rund um
    sich viele kleine Dreiecke entstehen, und der ungewichtete Mittelwert
    wandert daraufhin zum Loch — bei einem 60-auf-40-Deckel um 16,8 mm. Die
    Zuordnung (§21.2) hielt die Fläche danach für eine andere und meldete die
    alte als verwaist.
    """
    weights = np.asarray(body.area_faces[facet], dtype=float)
    points = np.asarray(body.triangles_center[facet], dtype=float)
    total = float(weights.sum())
    if total <= EPS_GEOM:
        return np.asarray(points.mean(axis=0), dtype=float)
    return np.asarray((points * weights[:, None]).sum(axis=0) / total, dtype=float)


# --- Offene Kanten ---------------------------------------------------------------


#: Wie viele offene Stellen einzeln benannt werden; der Rest kommt als **eine**
#: zusammenfassende Zeile.
#:
#: Die Zahl ist eine Bedienzahl und keine Rechengrenze. Zwanzig Einträge im
#: Merkmalsbaum geht jemand durch, klickt sie an, springt sie ab; bei
#: dreitausend tut das niemand, und die Liste ist dann keine Bedienung mehr,
#: sondern ein Protokoll.
#:
#: Was die Grenze **nicht** antastet, ist der Fall, für den die Aufteilung in
#: einzelne Schleifen gebaut wurde: Bei zwei Löchern in einer Schale bleiben es
#: zwei Merkmale an zwei Orten. Erst jenseits von zwanzig fasst sie zusammen.
#:
#: Und sie ist die **zweite** Linie, nicht die erste. Der Fall, der sie
#: gefunden hat — 3 372 Merkmale aus einer ungeschweißten STL —, war kein Netz
#: mit dreitausend Defekten, sondern eine falsche Frage an die Datei; das
#: beantwortet ``detect_edge_loops`` selbst. Hier bleibt der Fall, dass ein
#: Netz wirklich in dreitausend Stücken ankommt.
EDGE_LOOP_LIMIT = 20


def detect_edge_loops(mesh: MeshData) -> list[Feature]:
    """Offene Kanten sind Defekte, und zu wissen wo sie sind, ist die halbe
    Reparatur.

    **Gefragt wird nach dem Teil, nicht nach der Speicherform.** Eine STL kennt
    keine gemeinsamen Ecken: Sie schreibt jedes Dreieck mit seinen eigenen drei
    Punkten hin, und damit hat *jede* Kante topologisch keinen Partner. Wird
    eine solche Datei ungeschweißt geladen — ``generate.into_project`` tut das
    für jedes erzeugte Modell, mit guter Begründung —, meldete diese Funktion
    eine offene Stelle je Dreieck: 2 388 offene Kanten an ``plate_holes.stl``,
    6 912 an ``torus_ring.stl``, 36 an ``cube_clean.stl``. Alle drei Netze sind
    dicht; über die zusammengeführte Topologie sind es null, null und null.

    Warum das nicht bloß eine Laufzeitfrage ist: Weg 1 aus §2.2 verspricht dem
    Kunden, dass er ein heruntergeladenes Teil hereinzieht und **abgelesen**
    bekommt, was damit ist. Der Prüfbericht ist dieses Versprechen. Eine Zahl,
    die das Dateiformat beschreibt statt sein Teil, gehört dort nicht hin —
    auch nicht gekürzt. Und einstellen soll er dafür nichts: Die richtige
    Auskunft muss ohne sein Zutun herauskommen.

    Zusammengeführt wird deshalb **vor** dem Urteil, und zwar nur rechnerisch:
    Zwei Punkte am selben Ort bekommen dieselbe Nummer, das Netz im Dokument
    bleibt unangetastet. Eine Erkennung ist eine Auskunft und kein Schritt
    (Regel 2).

    **Das ist etwas anderes als das Verschweißen beim Laden, und der
    Unterschied trägt diese Entscheidung.** ``loader.normalise`` nimmt sein
    Verschweißen zurück, wenn das Netz danach offen ist (``ingest.weld_skipped``)
    — es *ändert* dort Geometrie, und zwei zusammengelegte Blätter einer Fläche
    können ein dichtes Netz aufreißen. Hier wird keine Fläche angefasst und
    keine Ecke gelöscht, nur gezählt; und Ecken zusammenzulegen kann die Zahl
    der Kanten ohne Partner allein **senken**, nie erhöhen. Es gibt also nichts
    zurückzunehmen. Aus demselben Grund greift auch der Vorbehalt aus
    ``generate.py`` hier nicht: Dort zerstörte das Aufräumen die Form eines
    zwei Millimeter großen Modells; hier bleibt die Form unberührt, und die
    Toleranz folgt ohnehin der Modellgröße (``weld_tolerance``, ein
    Zehntausendstel Prozent der Diagonale — bei 2 mm so streng wie bei 500).

    Ein **echtes** Loch übersteht das unbeschadet: Zusammengelegt werden nur
    Ecken am selben Ort, und eine Kante, die wirklich am Rand sitzt, findet
    auch dann keinen Partner. Genau das hält
    ``test_a_real_hole_survives_the_merge`` fest — ohne diese Zusage nähme die
    Änderung der Reparatur ihre Grundlage.

    **Eine Schleife ist ein Merkmal, nicht alle zusammen.** Hier entstand ein
    einziges ``edge_loop_1`` über den Schwerpunkt sämtlicher offener Kanten —
    und der liegt bei zwei Löchern genau zwischen ihnen, also im Leeren. Die
    Kamera flog auf einen Punkt, an dem nichts ist (§18.4), und die Zahl
    daneben zählte zwei Stellen zusammen, die nichts miteinander zu tun haben.

    Zusammengehörig heißt: über gemeinsame Ecken verbunden. Nummeriert wird
    nach Größe, dann nach Ort — eine Provenienz-ID muss die nächste Auswertung
    überleben (§21.2), und die Reihenfolge der Kanten im Netz tut das nicht.

    **Ab ``EDGE_LOOP_LIMIT`` kommt der Rest als eine Zeile** — für das Netz,
    das wirklich in Stücken ankommt.
    """
    body = mesh.raw
    if not len(body.faces):
        return []

    # **Welche Ecken derselbe Ort sind, wird einmal ausgerechnet.**
    # ``unique_rows`` gruppiert über dasselbe Gitter, über das auch
    # ``repair.merge_vertices`` verschweißt (``weld_digits``) — zwei Antworten
    # auf „ist das dieselbe Ecke" wären zwei Topologien desselben Körpers.
    #
    # ``same[k]`` ist dabei die **kleinste** Original-Eckennummer an diesem Ort,
    # und darauf ruht die Nummernstabilität weiter unten: Die Gruppen selbst
    # sind nach Koordinaten geordnet, und eine Ordnung nach Koordinaten
    # überlebt keine Drehung (siehe ``detect_faces``). Die Original-Nummern tun
    # es — sie ändern sich weder beim Drehen noch beim Umsortieren.
    digits = weld_digits(weld_tolerance(mesh.bounds.diagonal))
    same, place = trimesh.grouping.unique_rows(
        np.asarray(body.vertices, dtype=float), digits=digits
    )
    at_place = np.asarray(place, dtype=np.int64)

    edges_all = np.sort(at_place[np.asarray(body.edges_sorted, dtype=np.int64)], axis=1)
    single = trimesh.grouping.group_rows(edges_all, require_count=1)
    if not len(single):
        return []

    edges = edges_all[single]
    # Eine Kante, deren beide Enden derselbe Ort sind, ist keine offene Stelle,
    # sondern ein Nadeldreieck — ein Defekt, den ``repair`` als entartetes
    # Dreieck entfernt und nicht als Loch schließt. Erst das Zusammenlegen
    # macht sie überhaupt sichtbar; sie mitzuzählen hieße, den einen Defekt
    # unter dem Namen des anderen zu melden.
    edges = edges[edges[:, 0] != edges[:, 1]]
    if not len(edges):
        return []

    corners = np.unique(edges)
    groups = trimesh.graph.connected_components(edges, nodes=corners, engine="scipy")

    # Zurück auf die Original-Eckennummern: An ihnen hängen Sortierung und
    # Koordinaten, und nur sie überstehen eine Drehung.
    original = np.asarray(same, dtype=np.int64)

    # **Welche Ecke zu welcher Schleife gehört, steht einmal in einer Tabelle**
    # — es wird nicht je Schleife über sämtliche offenen Kanten gesucht. Hier
    # stand ``np.isin(edges[:, 0], members)`` mitten in der Schleife, also ein
    # Durchgang über alle Kanten je Gruppe. Bei zwei Löchern sind das zwei
    # Durchgänge und niemand merkt es; bei einem ungeschweißten Netz ist jedes
    # Dreieck eine Gruppe, und die Rechnung wächst mit dem Produkt statt mit
    # der Summe. Gemessen an ungeschweißten Kugeln: 5 120 Dreiecke 0,21 s,
    # 20 480 Dreiecke 2,09 s — viermal so viele Dreiecke, zehnmal so viel Zeit.
    # Über die Tabelle zählt ``bincount`` alle Kanten in einem Durchgang.
    label = np.full(int(corners.max()) + 1, -1, dtype=np.int64)
    for number, group in enumerate(groups):
        label[np.asarray(group, dtype=np.int64)] = number
    counts = np.bincount(label[edges[:, 0]], minlength=len(groups))

    loops: list[tuple[int, tuple[float, float, float], tuple[int, ...]]] = []
    for number, group in enumerate(groups):
        members = np.asarray(group, dtype=np.int64)
        if not len(members):
            continue
        count = int(counts[number])
        if not count:
            # Eine Ecke ohne offene Kante gehört keiner Schleife — ``nodes``
            # nimmt sie mit, das Merkmal nicht.
            continue
        at = original[members]
        middle = np.asarray(body.vertices[at], dtype=float).mean(axis=0)
        loops.append(
            (
                count,
                (float(middle[0]), float(middle[1]), float(middle[2])),
                tuple(int(index) for index in np.unique(at)),
            )
        )

    # **Bei gleich vielen offenen Kanten entscheiden die Eckennummern, nicht
    # der Ort.** Hier stand der gerundete Mittelpunkt, und damit galt genau
    # das, wovor ``detect_faces`` neunzig Zeilen weiter oben ausdrücklich
    # warnt: Eine Nummerierung nach Koordinaten überlebt keine Drehung. Zwei
    # gleich große Ausschnitte in einer Platte tauschen gekippt ihre Plätze,
    # ``edge_loop_1`` meint danach die andere Schleife — und daran hängen
    # Ops und Passungen (§21.2). Die Eckennummern ändern sich weder beim
    # Drehen noch beim Umsortieren der Dreiecke; genommen werden alle, denn
    # eine einzelne teilen sich benachbarte Schleifen.
    loops.sort(key=lambda entry: (-entry[0], entry[2]))

    named = loops[:EDGE_LOOP_LIMIT]
    features = [
        Feature(
            id=f"edge_loop_{number}",
            kind="edge_loop",
            provenance="detected",
            measure_sources={"centre": "facets"},
            params={"open_edges": count, "centre": centre},
        )
        for number, (count, centre, _corners) in enumerate(named, start=1)
    ]

    rest = loops[EDGE_LOOP_LIMIT:]
    if rest:
        # **Der Sammeleintrag sitzt auf einer echten Stelle, nicht auf dem
        # Schwerpunkt aller.** Genau dieser Schwerpunkt war der Fehler, den die
        # Aufteilung behoben hat: Er liegt zwischen den Löchern, also im
        # Leeren, und die Kamera flog auf einen Punkt, an dem nichts ist
        # (§18.4). ``rest`` ist absteigend sortiert; genommen wird also die
        # größte der zusammengefassten Stellen. Das ist nicht der Ort *aller*
        # — aber es ist ein Ort, an dem der Nutzer wirklich eine offene Kante
        # vorfindet, und das ist die Zusage, die diese Zahl daneben tragen muss.
        #
        # ``loops`` sagt, wie viele Stellen darin stecken; ohne diese Zahl
        # stünde im Baum eine einzelne Schleife mit zehntausend offenen Kanten,
        # und das wäre eine falsche Auskunft statt einer verkürzten.
        features.append(
            Feature(
                id=f"edge_loop_{len(named) + 1}",
                kind="edge_loop",
                provenance="detected",
                measure_sources={"centre": "facets"},
                params={
                    "open_edges": sum(count for count, _centre, _corners in rest),
                    "centre": rest[0][1],
                    "loops": len(rest),
                },
            )
        )
    return features


# --- Komponenten -----------------------------------------------------------------


def component_count(mesh: MeshData) -> int:
    """Wie viele getrennte Körper das Netz enthält (§21.1)."""
    return len(face_components(mesh.raw))


def _enclosed_volume(
    body: trimesh.Trimesh, faces: Any, triangles: np.ndarray | None = None
) -> float:
    """Das Volumen, das diese Dreiecke einschließen — mit Vorzeichen.

    Über das Divergenztheorem an den Dreiecken selbst, ohne ein Teilnetz zu
    bauen: ``Trimesh.split`` kostet an einem Modell mit 390 000 Dreiecken das
    Vielfache und repariert dabei, was die Eingangsstufe noch gar nicht
    entschieden hat (derselbe Grund, aus dem :func:`face_components` die
    Nachbarschaft liest). Wer die Dreiecke als Feld ``(n, 3, 3)`` schon hat,
    reicht sie herein und spart den zweiten Griff ins Netz.

    Eine geschlossene Schale, deren
    Normalen nach außen zeigen, schließt positives Volumen ein; zeigen sie
    nach innen, ist es negativ. Erst ihre geometrische Verschachtelung belegt
    eine Luftkammer statt eines umgestülpten Körpers.
    """
    if triangles is None:
        triangles = body.vertices[body.faces[faces]]
    first, second, third = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    return float(np.einsum("ij,ij->i", first, np.cross(second, third)).sum() / 6.0)


#: Die Enthaltenseinsprüfung verwendet ausschließlich den direkten Float64-Kern,
#: wo sie ihn braucht. Keine verschobenen oder neu vernetzten Ersatzformen bei
#: der Erkennung.

#: Die Strahlrichtungen für :func:`_point_inside_shell`, der Reihe nach: Wer
#: an einer Kante oder Ecke vorbeischrammt, nimmt die nächste.
_RAY_AXES: Final = ((0, 1), (1, 1), (2, 1), (0, -1), (1, -1), (2, -1))

#: Wie nah ein Treffer an Kante, Ecke oder Ausgangspunkt liegen darf, bevor er
#: als unentscheidbar gilt — relativ, in baryzentrischen Koordinaten.
_RAY_MARGIN: Final = 1e-9

#: Wie viele Gitterzellen je Achse das Zertifikat höchstens anlegt.
_CROSSING_GRID: Final = 128

#: Wie viele große Elterndreiecke der Zellenweg einzeln prüft, bevor er das
#: Zertifikat aufgibt und der exakten Differenz das Wort lässt.
_CROSSING_BIG_TRIANGLES: Final = 4096


def _triangle_bounds(triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Hüllquader je Dreieck aus einem Feld ``(n, 3, 3)`` — je Schale einmal gerechnet.

    Drei Eckenvergleiche statt einer Reduktion über die mittlere Achse: Die
    kostet an 393 216 Dreiecken sechs Millisekunden, die Vergleiche eine. Der
    Aufrufer reicht das Ergebnis an Zertifikat und Strahltest weiter, statt es
    je Paar neu zu bilden.
    """
    first, second, third = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    return (
        np.minimum(np.minimum(first, second), third),
        np.maximum(np.maximum(first, second), third),
    )


def _shells_do_not_cross(
    child_bounds: tuple[np.ndarray, np.ndarray],
    parent_bounds: tuple[np.ndarray, np.ndarray],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Das Zertifikat: Kein Dreieck der Elternschale kommt einem der Kindschale nahe.

    Zwei Dreiecke können sich nur schneiden, wenn ihre Hüllquader sich
    überlappen. Die Kinddreiecke belegen ein Gitter über dem Hüllquader des
    Kinds — die Zelle so groß wie das größte Kinddreieck, damit jedes höchstens
    zwei Zellen je Achse deckt —, und jedes Elterndreieck, dessen Hüllquader in
    den des Kinds ragt, fragt seine Zellen ab. Bleibt jede leer, ist keine
    Berührung möglich, und der Strahltest an einer Ecke entscheidet exakt. Ein
    ``False`` behauptet nichts: Dann rechnet die native Differenz wie bisher.

    Die Hüllquader tragen :data:`EPS_GEOM` Zuschlag, damit auch eine Berührung
    an der Rechengrenze den exakten Weg nimmt.
    """
    if check_cancelled is not None:
        check_cancelled()
    child_low = child_bounds[0] - EPS_GEOM
    child_high = child_bounds[1] + EPS_GEOM
    origin = child_low.min(axis=0)
    extent = child_high.max(axis=0) - origin
    parent_low, parent_high = parent_bounds
    corner = origin + extent
    candidates = np.flatnonzero(
        (parent_high[:, 0] >= origin[0])
        & (parent_high[:, 1] >= origin[1])
        & (parent_high[:, 2] >= origin[2])
        & (parent_low[:, 0] <= corner[0])
        & (parent_low[:, 1] <= corner[1])
        & (parent_low[:, 2] <= corner[2])
    )
    if not len(candidates):
        return True
    # Die Zelle: so groß wie das größte Kinddreieck, aber nicht so klein, dass
    # das Gitter über die Grenze wächst.
    cell = float(max((child_high - child_low).max(), extent.max() / _CROSSING_GRID, EPS_GEOM))
    shape = np.minimum(np.floor(extent / cell).astype(np.int64) + 1, _CROSSING_GRID)
    occupied = np.zeros(int(np.prod(shape)), dtype=bool)

    def cells_of(low: np.ndarray, high: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Zellbereich je Dreieck, an das Gitter geklemmt."""
        first = np.clip(np.floor((low - origin) / cell).astype(np.int64), 0, shape - 1)
        last = np.clip(np.floor((high - origin) / cell).astype(np.int64), 0, shape - 1)
        return first, last

    first, last = cells_of(child_low, child_high)
    if check_cancelled is not None:
        check_cancelled()
    for offset in itertools.product((0, 1), repeat=3):
        step = np.asarray(offset, dtype=np.int64)
        here = first + step
        within = np.all(here <= last, axis=1)
        if within.any():
            occupied[np.ravel_multi_index(here[within].T, shape)] = True
    # Die Elterndreiecke: kleine über dieselben acht Ecken, große Zelle für
    # Zelle — und zu viele große sind kein Zertifikat, sondern eine Absage.
    first, last = cells_of(parent_low[candidates], parent_high[candidates])
    spans = last - first
    small = np.all(spans <= 1, axis=1)
    if check_cancelled is not None:
        check_cancelled()
    for offset in itertools.product((0, 1), repeat=3):
        step = np.asarray(offset, dtype=np.int64)
        here = first[small] + step
        within = np.all(here <= last[small], axis=1)
        if within.any() and occupied[np.ravel_multi_index(here[within].T, shape)].any():
            return False
    big = np.flatnonzero(~small)
    if len(big) > _CROSSING_BIG_TRIANGLES:
        return False
    if len(big):
        block = occupied.reshape(tuple(int(size) for size in shape))
        for number, index in enumerate(big):
            if check_cancelled is not None and number % FIT_SCAN_BLOCK == 0:
                check_cancelled()
            low, high = first[index], last[index]
            if block[low[0] : high[0] + 1, low[1] : high[1] + 1, low[2] : high[2] + 1].any():
                return False
    return True


def _point_inside_shell(
    point: np.ndarray,
    triangles: np.ndarray,
    bounds: tuple[np.ndarray, np.ndarray],
) -> bool | None:
    """Liegt der Punkt in der geschlossenen Schale? Ein Strahl zählt die Durchstöße.

    Achsenparallel, damit die Vorauswahl zwei Vergleiche je Dreieck kostet
    statt einer Raumwinkelsumme über alle: Nur Dreiecke, deren Hüllquader den
    Strahl quer zur Richtung deckt, werden geschnitten. Trifft der Strahl eine
    Kante, eine Ecke oder ein fast paralleles Dreieck, ist die Zählung nicht
    zu entscheiden, und die nächste Richtung ist dran; bleibt keine, kommt
    ``None`` zurück, und der Aufrufer rechnet exakt.
    """
    low, high = bounds
    for axis, sign in _RAY_AXES:
        across = [index for index in range(3) if index != axis]
        chosen = np.flatnonzero(
            (low[:, across[0]] <= point[across[0]])
            & (high[:, across[0]] >= point[across[0]])
            & (low[:, across[1]] <= point[across[1]])
            & (high[:, across[1]] >= point[across[1]])
            & ((high[:, axis] >= point[axis]) if sign > 0 else (low[:, axis] <= point[axis]))
        )
        if not len(chosen):
            return False
        corners = triangles[chosen]
        first = corners[:, 1, across] - corners[:, 0, across]
        second = corners[:, 2, across] - corners[:, 0, across]
        to_point = point[across] - corners[:, 0, across]
        determinant = first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]
        # Ein Dreieck, dessen Projektion gegen seine wahre Fläche verschwindet,
        # liegt fast parallel zum Strahl. Trifft der Strahl seine Ebene — der
        # Punkt liegt darin —, ist nichts zu entscheiden; liegt die Ebene
        # abseits, kann der Strahl es nicht kreuzen, und es zählt nicht mit.
        edges_first = corners[:, 1] - corners[:, 0]
        edges_second = corners[:, 2] - corners[:, 0]
        normals = np.cross(edges_first, edges_second)
        true_area = np.linalg.norm(normals, axis=1)
        parallel = np.abs(determinant) <= _RAY_MARGIN * true_area
        if parallel.any():
            distance = np.abs(
                np.einsum("ij,ij->i", point - corners[parallel, 0], normals[parallel])
            ) / np.maximum(true_area[parallel], EPS_GEOM)
            if np.any(distance <= EPS_GEOM):
                continue
            keep = ~parallel
            corners, first, second = corners[keep], first[keep], second[keep]
            to_point, determinant = to_point[keep], determinant[keep]
            if not len(corners):
                return False
        weight_second = (
            to_point[:, 0] * second[:, 1] - to_point[:, 1] * second[:, 0]
        ) / determinant
        weight_third = (first[:, 0] * to_point[:, 1] - first[:, 1] * to_point[:, 0]) / determinant
        weight_first = 1.0 - weight_second - weight_third
        weights = np.stack((weight_first, weight_second, weight_third), axis=1)
        inside = np.all(weights > _RAY_MARGIN, axis=1)
        near_edge = np.all(weights > -_RAY_MARGIN, axis=1) & ~inside
        if near_edge.any():
            continue
        if not inside.any():
            return False
        hit = np.einsum("ij,ij->i", weights[inside], corners[inside][:, :, axis])
        ahead = sign * (hit - point[axis])
        scale = np.abs(corners[inside][:, :, axis]).max(axis=1) + abs(float(point[axis]))
        if np.any(np.abs(ahead) <= _RAY_MARGIN * np.maximum(scale, 1.0)):
            continue
        return bool(np.count_nonzero(ahead > 0.0) % 2 == 1)
    return None


def _shells_inside_the_material(
    body: trimesh.Trimesh,
    components: Sequence[Any],
    hollow: Sequence[int],
    volumes: Sequence[float],
    *,
    corners: Sequence[np.ndarray] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[list[tuple[int, ...]], bool]:
    """Die Grenzschalen jeder Luftkammer aus ihrer Verschachtelung — und ob sie lesbar waren.

    Der nächste positive Mantel kann eine Materialinsel sein und bezeichnet
    dann gerade nicht den umgebenden Körper. Vollständiges Enthaltensein heißt:
    Die Schalen kreuzen sich nicht (:func:`_shells_do_not_cross`), und eine
    Ecke des Kinds liegt in der Elternschale (:func:`_point_inside_shell`) —
    für geschlossene Schalen, die einander nicht schneiden, ist das dieselbe
    Aussage wie eine leere Differenz, nur ohne einen Manifold je Paar. Fehlt
    das Zertifikat, entscheidet die native Differenz gegen eine private
    positive Schalenform wie bisher: Am Quader mit acht Kammern aus 434 176
    Dreiecken kostete sie 1,2 s, der Strahl 30 ms (gemessen 21.09.2026).
    Die Bounds verwerfen unmögliche Paare; sie beweisen kein Enthaltensein.
    Eltern sind die jeweils kleinste umfassende Schale. Material und Luft
    wechseln entlang einer gültigen Kette ihre Orientierung.
    """
    from app.core.errors import GeometryError
    from app.core.geom.boolean import boolean

    def check() -> None:
        """Abbruch zwischen Schalen und den einzelnen nativen Differenzen."""
        if check_cancelled is not None:
            check_cancelled()

    # Ein Griff je Schale: die Dreiecke als Feld (vom Aufrufer, der sie für
    # das Volumen schon gelesen hat), ihre Hüllquader und daraus der
    # Hüllquader der Schale — Zertifikat und Strahltest lesen dieselben
    # Felder, kein Paar greift noch einmal ins Netz.
    if corners is None:
        corners = [
            np.asarray(body.vertices[body.faces[faces]], dtype=np.float64) for faces in components
        ]
    triangle_bounds: list[tuple[np.ndarray, np.ndarray]] = []
    bounds = []
    for triangles in corners:
        check()
        low, high = _triangle_bounds(triangles)
        triangle_bounds.append((low, high))
        bounds.append((low.min(axis=0), high.max(axis=0)))
    positive: dict[int, MeshData] = {}

    def form(index: int) -> MeshData:
        """Eine eigene, positiv orientierte Hülle ohne Änderung des Originals."""
        check()
        if index not in positive:
            faces = np.asarray(body.faces)[components[index]].copy()
            if volumes[index] < 0.0:
                faces = faces[:, ::-1]
            shell = trimesh.Trimesh(vertices=body.vertices.copy(), faces=faces, process=False)
            shell.remove_unreferenced_vertices()
            positive[index] = MeshData.of(shell)
        return positive[index]

    def contained(child: int, parent: int) -> bool:
        """Liegt die Kindschale vollständig in der Elternschale?"""
        if _shells_do_not_cross(
            triangle_bounds[child], triangle_bounds[parent], check_cancelled=check_cancelled
        ):
            check()
            answer = _point_inside_shell(
                corners[child][0, 0], corners[parent], triangle_bounds[parent]
            )
            if answer is not None:
                return answer
        check()
        remainder = boolean(
            "difference",
            [form(child), form(parent)],
            stages=("direct",),
            allow_empty=True,
        ).mesh
        return not remainder.triangle_count

    parents: list[int | None] = [None] * len(components)
    order = sorted(range(len(components)), key=lambda index: abs(volumes[index]))
    for child in order:
        check()
        low, high = bounds[child]
        for parent in order:
            if abs(volumes[parent]) <= abs(volumes[child]):
                continue
            lower, upper = bounds[parent]
            # Berührung an einer äußeren Grenze belegt keine eingeschlossene Luft.
            if not (np.all(low > lower + EPS_GEOM) and np.all(high < upper - EPS_GEOM)):
                continue
            check()
            try:
                inside = contained(child, parent)
            except GeometryError as problem:
                # Ein nicht verlässlich lesbares Schalenpaar begründet kein
                # Merkmal — und es verschwindet nicht still: Der Aufrufer
                # trägt es der Auswertung zu (:func:`unreadable_void_shells`),
                # die einen Befund daraus macht (Regel 17).
                _log.warning(
                    "void shells unreadable: %d components, pair (%d, %d): %s",
                    len(components),
                    child,
                    parent,
                    problem,
                )
                return [()] * len(hollow), False
            check()
            if inside:
                parents[child] = parent
                break

    groups = []
    for cavity in hollow:
        check()
        cursor: int | None = cavity
        valid = True
        while cursor is not None:
            ancestor = parents[cursor]
            if ancestor is None:
                valid = volumes[cursor] > 0.0
                break
            if (volumes[cursor] > 0.0) == (volumes[ancestor] > 0.0):
                valid = False
                break
            cursor = ancestor
        children = [index for index, parent in enumerate(parents) if parent == cavity]
        if any(volumes[index] < 0.0 for index in children):
            valid = False
        groups.append((cavity, *children) if valid else ())
    return groups, True


def detect_voids(
    mesh: MeshData, *, check_cancelled: Callable[[], None] | None = None
) -> list[Feature]:
    """Geschlossene Luftkammern samt Materialinseln, ohne geratene Öffnungen (§21.1).

    Dichtheit und einheitlicher Umlaufsinn sind Voraussetzungen. Eine negative
    Außenschale allein ist kein Innenraum. Die Verschachtelung ordnet jede
    Insel ihrer umgebenden Kammer zu; eigene Luftkammern in dieser Insel bleiben
    getrennte Merkmale. Volumen und Auswahl beschreiben dieselbe vollständige
    Luftgrenze. Verschieben und Entfernen verwenden genau diese Flächen.
    """
    return _detect_voids(mesh, check_cancelled=check_cancelled)[0]


def _detect_voids(
    mesh: MeshData, *, check_cancelled: Callable[[], None] | None = None
) -> tuple[list[Feature], int]:
    """:func:`detect_voids` samt der Zahl der Schalen, wenn sie nicht lesbar waren.

    Die zweite Zahl ist null, solange jede Differenz gerechnet werden konnte;
    sonst die Komponentenzahl des Körpers — :func:`detect` merkt sie sich für
    :func:`unreadable_void_shells`, damit die Auswertung sagen kann, dass hier
    Einschlüsse fehlen könnten.
    """
    if check_cancelled is not None:
        check_cancelled()
    body = mesh.raw
    if not (bool(body.is_watertight) and bool(body.is_winding_consistent)):
        return [], 0
    components = face_components(body)
    if len(components) < 2:
        return [], 0
    corners = []
    volumes = []
    for faces in components:
        if check_cancelled is not None:
            check_cancelled()
        triangles = np.asarray(body.vertices[body.faces[faces]], dtype=np.float64)
        corners.append(triangles)
        volumes.append(_enclosed_volume(body, faces, triangles))
    if not all(math.isfinite(volume) for volume in volumes):
        return [], 0
    hollow = [number for number, volume in enumerate(volumes) if volume < 0.0]
    if not hollow:
        return [], 0
    groups, readable = _shells_inside_the_material(
        body, components, hollow, volumes, corners=corners, check_cancelled=check_cancelled
    )
    if not readable:
        return [], len(components)
    measured: list[tuple[Vec3, Vec3, float, tuple[int, ...]]] = []
    for group in groups:
        if check_cancelled is not None:
            check_cancelled()
        if not group:
            continue
        faces = np.concatenate([components[index] for index in group])
        volume = -math.fsum(volumes[index] for index in group)
        if volume <= 0.0:
            continue
        corners = body.vertices[body.faces[faces]].reshape(-1, 3)
        lower, upper = corners.min(axis=0), corners.max(axis=0)
        middle = (lower + upper) / 2.0
        centre: Vec3 = (float(middle[0]), float(middle[1]), float(middle[2]))
        size: Vec3 = (
            float(upper[0] - lower[0]),
            float(upper[1] - lower[1]),
            float(upper[2] - lower[2]),
        )
        measured.append((centre, size, volume, tuple(sorted(int(index) for index in faces))))
    found = [
        Feature(
            id=FeatureId(f"void_{number}"),
            kind="void",
            provenance="detected",
            measure_sources={"volume": "facets", "centre": "facets", "size": "facets"},
            params={"volume": volume, "centre": centre, "size": size},
            face_indices=faces,
        )
        for number, (centre, size, volume, faces) in enumerate(sorted(measured), start=1)
    ]
    if check_cancelled is not None:
        check_cancelled()
    return found, 0


def voids_instead_of_phantom_bores(
    found: dict[FeatureId, Feature],
    voids: Sequence[Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Wo ein Einschluss liegt, steht er selbst statt der Bohrung, die keine ist.

    Dieselbe Bauart wie :func:`_threads_instead_of_phantoms`, und aus demselben
    Grund: Die Flächen eines Einschlusses tragen echte Zylinder- und
    Kegeleinpassungen — sie sind ja wirklich rund —, aber keine einzelnen
    Öffnungen nach außen. Ein Merkmal, dessen Flächen mehrheitlich auf
    einer Einschlussschale liegen, verschwindet deshalb, und der Einschluss
    steht an seiner Stelle.

    **Die Mehrheit und nicht die Berührung**: Ein Merkmal, das einen
    Einschluss nur streift, gehört weiter dem Körper. Dieselbe Schwelle wie
    bei der Wendel, damit zwei Nachbarschaften nicht zwei Antworten geben.
    """
    if check_cancelled is not None:
        check_cancelled()
    if not voids:
        return found
    kept = dict(found)
    carriers = [
        feature for feature in found.values() if feature.kind != "void" and feature.surface_patches
    ]
    for void in voids:
        on_the_shell = set(void.face_indices)
        patches = list(void.surface_patches)
        # Die Träger gehören den Originaldreiecken. Das Entfernen eines
        # semantischen Namens darf keinen Anteil einer späteren Kammer löschen.
        for feature in carriers:
            if check_cancelled is not None:
                check_cancelled()
            if not on_the_shell.isdisjoint(feature.face_indices):
                patches.extend(
                    clipped_patches(
                        feature.surface_patches,
                        on_the_shell,
                        check_cancelled=check_cancelled,
                    )
                )
        for name, feature in list(kept.items()):
            if check_cancelled is not None:
                check_cancelled()
            if feature.kind == "void" or not feature.face_indices:
                continue
            inside = sum(1 for index in feature.face_indices if index in on_the_shell)
            if inside * 2 > len(feature.face_indices):
                del kept[name]
        kept[void.id] = replace(void, surface_patches=tuple(patches))
    return kept


def _same_torus(one: tuple[TorusFit, list[int]], two: tuple[TorusFit, list[int]]) -> bool:
    """Beschreiben diese zwei Flecken denselben Ring?

    **Ein Torus zerfällt genauso wie ein Zylinder, nur fiel es später auf.**
    Ein einzelner Ring aus dem Korpus kam in jeder geprüften Vernetzung als
    *zwei* Merkmale heraus — Ø 33,93 und Ø 33,94 bei 48 Segmenten, Ø 33,73 und
    Ø 33,75 bei 24. Im Bildschirmfoto eines Kunden standen drei Wülste mit
    34,09, 34,06 und 34,03 mm untereinander, und niemand konnte sagen, ob das
    drei Kanten sind oder eine.

    Der Unterschied zum Zylinder liegt im letzten Prüfschritt: Dort trennt der
    **Abschnitt auf der Achse** zwei Bohrungen durch zwei Wände voneinander.
    Ein Ring hat keinen solchen Abschnitt — er hat einen Mittelpunkt, und zwei
    Ringe mit derselben Achse und demselben Mittelpunkt sind derselbe Ring.
    """
    first, _ = one
    second, _ = two
    if first.recess is not second.recess:
        return False

    scale = max(first.ring_radius, second.ring_radius)
    if abs(first.ring_radius - second.ring_radius) > scale * CYLINDER_TOLERANCE:
        return False
    tube = max(first.tube_radius, second.tube_radius)
    if abs(first.tube_radius - second.tube_radius) > tube * CYLINDER_TOLERANCE:
        return False

    axis = np.asarray(first.axis, dtype=float)
    if abs(float(axis @ np.asarray(second.axis, dtype=float))) < math.cos(
        math.radians(SINK_AXIS_LIMIT)
    ):
        return False

    # Der Mittelpunkt, in ganzer Länge — nicht nur quer zur Achse. Zwei
    # gleich große Ringe übereinander auf derselben Achse sind zwei Ringe.
    offset = np.asarray(second.centre, dtype=float) - np.asarray(first.centre, dtype=float)
    return float(np.linalg.norm(offset)) <= scale * SINK_FIT_LIMIT


def _same_cone(one: tuple[ConeFit, list[int]], two: tuple[ConeFit, list[int]]) -> bool:
    """Beschreiben diese zwei Flecken denselben Kegel?

    **Das dritte Geschwister, und es hatte die Zusammenführung nicht.** Für
    Zylinder gibt es sie seit je (:func:`_merged_cylinders`), für Ringe seit
    dem Befund an einem Kundenbild (:func:`_merged_tori`) — der Kegel ging
    beide Male leer aus.

    Gemessen an einem Quader mit **einer** Senkung Ø 12 über einer Bohrung
    Ø 6 (Befund 3d-druck-a0, 03.09.2026): Der Objektbaum zeigte **drei**
    Senkungen. Die Flecken sind dabei disjunkt — 56, 8 und 37 Dreiecke, keine
    gemeinsame Fläche —, es ist also **ein** Mantel in drei Stücken und kein
    dreifacher Fit. Zwei davon treffen die Sache genau (Ø 11,98, Achse Z,
    Rest 0,0003), der dritte ist der schlechte Ausschnitt: Achse drei Grad
    verkippt, Ø 12,88, Rest 0,0245.

    **Der Anker ist die Spitze**, wie beim Ring der Mittelpunkt — und aus
    demselben Grund: Der Radius eines Ausschnitts hängt davon ab, wie viel vom
    Mantel er trägt (hier 11,98 gegen 12,88), die Spitze nicht. Gemessen liegen
    die drei Spitzen 0,000 und 0,153 mm auseinander; zwischen **zwei** Senkungen
    in demselben Quader sind es **30 mm**. Die Schwelle sitzt bei einem Viertel
    des Radius (:data:`SINK_FIT_LIMIT`), also rund 1,6 mm — Faktor zehn nach
    unten, Faktor zwanzig nach oben.
    """
    first, _ = one
    second, _ = two
    if first.recess is not second.recess:
        return False
    if abs(first.half_angle - second.half_angle) > CONE_SAME_ANGLE:
        return False

    axis = np.asarray(first.axis, dtype=float)
    if abs(float(axis @ np.asarray(second.axis, dtype=float))) < math.cos(
        math.radians(CONE_SAME_AXIS)
    ):
        return False

    scale = max(first.radius, second.radius)
    offset = np.asarray(second.apex, dtype=float) - np.asarray(first.apex, dtype=float)
    return float(np.linalg.norm(offset)) <= scale * SINK_FIT_LIMIT


def _merged_cones(
    body: trimesh.Trimesh,
    found: Cones,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> Cones:
    """Kegelflecken, die denselben Kegel beschreiben, zu einem machen.

    Wie :func:`_merged_tori`, und mit derselben Rechtfertigung: Der gemeinsame
    Fit muss beweisen, dass er überhaupt ein Kegel ist — nicht, dass er besser
    streut als seine Teile. Ein Fit über mehr Punkte streut immer etwas mehr.

    An der gemessenen Senkung: die drei Stücke einzeln 0,0003, 0,0003 und
    0,0245, zusammen **0,0099** über alle 101 Dreiecke — unter
    :data:`ROUND_TOLERANCE`, und damit besser als der schlechteste Teil. Der
    zusammengeführte Kegel trägt Ø 12,07 statt dreier Zahlen zwischen 11,98
    und 12,88.

    ``good`` prüft die Bauart mit (Rückstand **und** Winkelbereich); ein
    Zusammenschluss, der aus dem Kegelfenster fällt, bleibt getrennt.
    """
    if len(found) < 2:
        return found

    merged: Cones = []
    for fit, patch in found:
        for index, (other, gathered) in enumerate(merged):
            if check_cancelled is not None:
                check_cancelled()
            if not _same_cone((fit, patch), (other, gathered)):
                continue
            together = gathered + patch
            again = fit_cone(body, together, check_cancelled=check_cancelled)
            if again is not None and again.good and again.residual <= ROUND_TOLERANCE:
                merged[index] = (again, together)
                break
        else:
            merged.append((fit, patch))
    return merged


def _merged_tori(
    body: trimesh.Trimesh,
    found: Tori,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> Tori:
    """Ringflecken, die denselben Ring beschreiben, zu einem machen.

    Wie :func:`_merged_cylinders`, und aus demselben Grund: Mehrere Merkmale
    an derselben Stelle sind für die Zuordnung mehrere gleich gute Kandidaten,
    also hält die Auswertung an und fragt — bei jeder Auswertung, und mit einer
    Frage, auf die es keine richtige Antwort gibt (§21.3).

    Die Vereinigung muss sich rechtfertigen, aber **anders als beim Zylinder**.
    Dort darf der gemeinsame Fit nicht schlechter streuen als der schlechtere
    der beiden; hier wäre das zu streng und träfe zudem nichts. Gemessen an
    zwei Hälften eines Rings: einzeln 0,00005, zusammen 0,00040 — die
    Vereinigung streut immer etwas mehr, weil sie mehr Punkte trägt. Und an
    zwei **verschiedenen** Ringen, fälschlich zusammengelegt: ebenfalls
    0,00040. Der Rest trennt die beiden Fälle also gar nicht.

    Getrennt werden sie von :func:`_same_torus` über den Mittelpunkt, und zwar
    sauber: An zwei Ringen 8 mm übereinander sagt es für die vier Flecken
    zweimal *ja* und viermal *nein*. Der Fit muss deshalb nur noch beweisen,
    dass er überhaupt ein Ring ist — dass er unter der Gütegrenze bleibt, ab
    der eine Fläche als rund gilt.
    """
    if len(found) < 2:
        return found

    merged: Tori = []
    for fit, patch in found:
        for index, (other, gathered) in enumerate(merged):
            if check_cancelled is not None:
                check_cancelled()
            if not _same_torus((fit, patch), (other, gathered)):
                continue
            together = gathered + patch
            again = fit_torus(body, together, check_cancelled=check_cancelled)
            if again is not None and again.residual <= ROUND_TOLERANCE:
                merged[index] = (again, together)
                break
        else:
            merged.append((fit, patch))
    return merged
