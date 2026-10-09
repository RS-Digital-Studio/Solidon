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
import heapq
import itertools
import math
import struct
import threading
import weakref
from collections import Counter, OrderedDict
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Any, Final, NamedTuple, cast

import numpy as np

from app.core import units
from app.core.deferred import cKDTree, least_squares, trimesh
from app.core.geom.mesh import (
    MeshData,
    face_components,
    fully_stitched,
    python_values,
    refined_units,
    refined_units_key,
    triple_products,
    unique_edges,
)
from app.core.geom.repair import merge_vertices
from app.core.log import get_logger
from app.core.perceive import refine
from app.core.perceive.helix import Helix, _facet_of_face, find_helices
from app.core.perceive.patterns import patterns_instead_of_cells
from app.core.perceive.slots import ACROSS_THE_AXIS, PARALLEL_AXES, slots_instead_of_half_bores
from app.core.perceive.surfaces import clipped_patches, planar_patch
from app.core.types import Feature, FeatureId, MeasureSource, SurfacePatch, Vec3, is_a_cavity
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
#: unterscheidet. **Gezählt wird höchstens je Umrissecke** (:func:`_flat_counts`):
#: Ein Teiler vermehrt die Dreiecke einer Facette, nicht die Ecken ihres
#: Umrisses, und ein fein geteilter Mantelstreifen ist kein Deckel.
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

#: Bis zu welchem Anteil an den Ecken des Netzes die Ecken eines Flecks
#: sortiert statt markiert gezählt werden.
#:
#: Markieren kostet ein Feld über **alle** Ecken des Netzes, Sortieren nur
#: die des Flecks. An der Ikosphäre, deren Fleck das ganze Netz ist, war
#: Markieren fünfmal schneller; am erzeugten Puppenhausbett mit 615 000
#: Ecken und 96 893 Splittern aus meist unter hundert Ecken kostete es
#: dagegen je Fleck ein bis zwei Millisekunden für nichts, über 30 der 190
#: Sekunden der Erkennung (25.09.2026). Gleich schnell sind beide Wege bei
#: fünf bis zehn Prozent der Netzecken, gemessen an 50 000 bis 1,2 Millionen
#: Ecken. Beide geben dieselbe Antwort; eine Rechengrenze, keine Toleranz.
SORTED_CORNERS_SHARE: Final = 0.05

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
    (:data:`RIGID_KEY_POINTS`). In einer Runde des Stapels antwortet dessen
    Wissen (:func:`_screened_fits` hat die Kennzahl schon gerechnet).
    """
    screened = _SCREENED.get()
    if screened is not None and screened.body is body:
        known = screened.shapes.get(_patch_key(patch), _UNKNOWN)
        if known is not _UNKNOWN:
            return cast("tuple[Any, ...] | None", known)
    return _rigid_key_read(body, patch)


def _rigid_key_read(body: trimesh.Trimesh, patch: Sequence[int]) -> tuple[Any, ...] | None:
    """Die Rechnung von :func:`_rigid_key`."""
    if _face_count(body, patch) < MIN_PATCH_FACES:
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

#: Wie viel Kreis eine Rundform mindestens zeigen muss, in Grad — sonst ist
#: sie eine Kante und keine Rundform (RM-210, Entscheidung Robert 23.09.2026:
#: „konservativ, etwa 5°").
#:
#: Gilt für die Stücke, deren Bogen klein sein kann: Verrundung (Zylinder-
#: ausschnitt), Kegelstück und Torusstück, beim Torus der Bogen der Röhre.
#: Ein Fleck aus acht Dreiecken mit 0,03 mm Wölbung zeigt 2,8 Grad eines
#: Kreises, und die Einpassung extrapoliert daraus einen Radius von 99 mm —
#: für einen Drucker ist das keine Rundung. Gemessen an echten Verrundungen:
#: konstruierte 82,7 bis 86,3 Grad, `drill-holder.3mf` median 151,5, die
#: wackelnden Flecken der Lageprobe 2,0 bis 18,3 Grad.
#:
#: **Nicht** :data:`FLAT_ANGLE`: Der sagt, ab wann ein Winkel überhaupt eine
#: Krümmung ist und nicht Rechenrauschen (0,5 Grad). Diese Schwelle ist eine
#: Aussage über das Erzeugnis; sie steht deshalb für sich.
MIN_ROUND_ARC: Final = 5.0

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

#: Wie weit zwei Nachbarn **eines Prismas** im Radius auseinanderliegen dürfen,
#: bevor ein Bogen dort endet — als Anteil des größeren (RM-219, 25.09.2026).
#:
#: Ein extrudierter Umriss aus tangentialen Bögen ist ein Fleck, und
#: :data:`CURVATURE_JUMP` trennt erst ab dem Doppelten: Am Besenhalter blieben
#: R 1,36 und R 2,72, R 4,76 und R 5,44 beisammen, dazu die Geraden zwischen
#: ihnen, und auf keine seiner acht gerundeten Seiten passte ein Zylinder. An
#: einem Prisma ist der Radius genau, weil jeder Streifen über die ganze Höhe
#: reicht. **Der Wert liegt in der Lücke zwischen Rauschen und Zeichnung**:
#: Innerhalb eines Bogens des Besenhalters streut der Radius um höchstens
#: 2,4 Prozent, der kleinste gezeichnete Wechsel des Korpus beträgt
#: 6,3 Prozent (R 5,10 gegen 5,44). Zwei Prozent lagen im Rauschen — sie
#: zerlegten Bögen an zufälligen Stellen und die geschwungenen Streben des
#: Eiffelturms, deren Radius um zwei bis drei Prozent je Streifen wandert, in
#: kurze Stücke, die auf Kreise passten. Wo der Radius öfter springt, ist er
#: Rauschen, und getrennt wird nicht (:data:`PRISM_QUIET_SHARE`); ein Stück
#: zählt nur als gezeichneter Bogen (:func:`_exactly_an_arc`).
PRISM_ARC_JUMP: Final = 0.05

#: Ab welchem Anteil springender Nähte die Radien eines Prismas Rauschen sind
#: und kein Umriss aus Bögen (RM-219, 25.09.2026).
#:
#: Der Radius je Dreieck ist nur so genau wie die Vernetzung. An einem
#: CAD-Export mit gleichmäßig unterteilten Bögen springt er selten — in jedem
#: Stück des Besenhalters an höchstens 1,3 Prozent der Nähte, und das sind die
#: Grenzen seiner Bögen. An Schriftzügen, Logos und frei geformten Griffen
#: springt er an jeder dritten, und dort zerfällt der Umriss in Splitter von
#: sechs bis zehn Dreiecken, die genau genug auf Kreise passen: gemessen an 15
#: Dateien des Korpus, zurückgehalten Radien wie 4,637, 1,256 und 5,283 am
#: Bohrerhalter oder 21,6 bis 21,8 am Toilettenpapierhalter bei 12 bis 69 Prozent
#: springender Nähte. Wenige echte Bögen in lauten Stücken bleiben dabei, was
#: sie vorher waren — R 2 an der Schwammablage bei 13 Prozent.
PRISM_QUIET_SHARE: Final = 0.1

#: Ab welchem Knick eine Naht **innerhalb** eines Flecks zwei Flächen trennt,
#: in Grad (ERKENNUNG-11). Unter :data:`CURVATURE_LIMIT` gilt ein Knick als
#: Stufe einer Rundung, und der Fleck bleibt beisammen. Die Haltelippe einer
#: Magnettasche steht aber um 20,5 Grad gegen die Wand, und eine flache
#: Senkung, ein Absatz an einer Drehform ebenso: Wand und Lippe lagen in einem
#: Fleck, auf den weder Zylinder noch Kegel passte, und am Netz stand die
#: Tasche als „Gerundete Seite innen“ da, am exakten Körper als Bohrung mit
#: Senkung. Zehn Grad liegen über der Teilung jedes fein vernetzten Mantels
#: (48 Segmente: 7,5 Grad) und unter der Lippe.
SEAM_ANGLE: Final = 10.0
#: … und wie viel schärfer die Naht sein muss als jeder andere weiche Knick
#: ihrer beiden Dreiecke. Eine grob geteilte Verrundung knickt an jeder
#: Reihe gleich stark und ist keine Naht; die Lippe knickt 2,7-mal so stark wie
#: die Teilung des Mantels daneben.
SEAM_RATIO: Final = 2.0
#: … und wie gleich die Naht ringsum knickt: der größte Knick höchstens so
#: viel über dem kleinsten. Eine gedrehte oder gezogene Kante knickt überall
#: gleich; Rauschen nicht.
SEAM_SPREAD: Final = 0.1

#: Wie lang ein Zylinderstück der tangentialen Trennung (:func:`_tangential_pieces`)
#: entlang seiner Achse mindestens ist, als Anteil seines Radius (RM-226).
#:
#: Eine Spalte eines Rings oder einer Kugel zwischen zwei Meridianen ist
#: örtlich ein Zylinder: Ihre Ecken liegen bis auf eine Abweichung zweiter
#: Ordnung auf einem, und ihre Facetten sind symmetrische Trapeze mit Normalen
#: quer zur Achse. Sie ist aber nur eine Facette breit. Gemessen an Quadern
#: R 3 und R 8, gerundeten T R 1 und R 3 und Zapfen mit Kehle R 2, 3 und 4,
#: je als exakte Vernetzung und als STL: Echte Stücke sind mindestens halb so
#: lang wie ihr Radius (die 4 mm kurzen senkrechten Rundungen R 8), Spalten
#: höchstens 0,23-mal. Eine Spalte über dieser Grenze gibt es an einem großen
#: Ring mit dünner Röhre und feiner Vernetzung: Am Elegoo-Fettwerkzeug liegen
#: die Scheiben einer Rundung R 0,5 entlang des Umrisses bis zur
#: Verschweißtoleranz auf je einem Zylinder und sind 0,44- bis 0,58-mal so
#: lang wie ihr Radius. Solche Scheiben fasst :func:`_drawn_chains` zusammen;
#: diese Grenze nimmt nur, was schon für sich zu kurz ist.
TANGENTIAL_MIN_LENGTH: Final = 0.4

#: Wie viele vergebliche Keime :func:`_tangential_cylinders` an einem Ziel
#: bis zum ersten Zylinderstück bearbeitet (``TANGENTIAL_FIRST_SEEDS``) und
#: danach in Folge (``TANGENTIAL_FUTILE_SEEDS``). Die Keime laufen nach
#: Nahtlänge, die längste zuerst, und ein Verbund aus Rundungen zeigt seinen
#: ersten Zylinder an den längsten Nähten, den Mantellinien: Über den Korpus
#: ``F:\3D Dateien`` (225 Körper, 293 Ziele mit Treffern) kam der erste
#: Treffer meist am ersten Keim, spätestens am 756. (Besteckkasten, ein Stück
#: ohne Wirkung auf die Merkmale), sonst bis zum 177.; zwischen zwei Treffern
#: lagen höchstens 2 427 vergebliche (Rucksackhalter, eine echte Rundung
#: R 1,57). Eine organische Haut keimt dagegen an fast jeder Naht — am Baum
#: mit Tablett 49 150 Keime, zwölf Sekunden, für sechs Splitter, die die
#: Freiformprobe ohnehin verwirft. Greift die erste Grenze, bleibt das Ziel,
#: was es ohne die sechste Runde war. Arbeitsgrenzen, keine Toleranzen; sie
#: gelten, solange die Keime nach Länge laufen.
TANGENTIAL_FIRST_SEEDS: Final = 1024
TANGENTIAL_FUTILE_SEEDS: Final = 4096

#: Wie viele Nachbarflächen einer kugeligen Fläche selbst Kantenverrundungen
#: mit ihrem Radius sein müssen (:func:`rounds_the_corner`), damit sie als Ecke
#: gilt — die Stelle, an der verrundete Kanten zusammenlaufen. Zwei, weil eine
#: Ecke aus mindestens zwei Kanten entsteht. Beide Kerne fragen diese Zahl
#: (``brep.features._describe``, :func:`_corners_named_as_fillets`).
#:
#: **Nicht über die Größe.** Der erste Versuch maß den Anteil an der Vollkugel
#: (Eckverrundung 0,125, volle Kugel 1,000) und trennte damit falsch: Eine
#: Pfanne ist nie mehr als eine Halbkugel, eine flache Kalotte — eine
#: Magnettasche etwa — kann selbst 0,1 abdecken. Gemessen an einer aus einem
#: Quader geschnittenen Kugel: 1 Nachbar, 0 Verrundungen; an der Ecke eines
#: rundum verrundeten Quaders: 3 Nachbarn, 3 Verrundungen.
CORNER_NEIGHBOURS: Final = 2

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

#: Ab welchem Anteil an der Oberfläche **raue Tafeln** einen Körper für sich
#: zur Haut machen (RM-235, 25.09.2026). Eine raue Tafel ist eine große
#: Facette, die an der Ebenheitsprüfung scheitert und deren Knicke Rauschen
#: tragen und keine Krümmung (:data:`FREEFORM_ROUGH_MIX`,
#: :data:`FREEFORM_ROUGH_BEND`): Sie ist weder Fläche noch Fleck, und die
#: Splitterregel darüber sieht sie nicht. Das erzeugte Puppenhausbett trägt
#: 57 Prozent seiner Oberfläche darin, galt mit 34 Prozent Splittern nicht als
#: Haut, und seine 96 893 Splitter wurden eingepasst — 98 von 100 Sekunden
#: für null Merkmale.
#:
#: **Gemessen an beiden Seiten** (``F:\3D Dateien``, 189 Körper mit
#: verrauschten Facetten): Erzeugte Möbel, Figurenteile und die Sockel des
#: Zauberturms liegen bei 50 bis 96 Prozent, der nächste Körper bei 30 (ein
#: Kleinteil des Piratenschiffs), Konstruiertes höchstens bei 23 (ein Teil
#: der Kugelbahn), die Siebhalter bei 15. Die Tafeln stattdessen zur
#: Splittersumme zu zählen, ist ebenfalls gemessen und verworfen: Ein
#: konstruiertes Teil mit 56 Prozent Splittern kippte dabei über die Schwelle.
FREEFORM_ROUGH_SHARE: Final = 0.4

#: Wie gemischt die Knicke einer Tafel sein müssen, damit sie rau heißt: der
#: kleinere Anteil konvexer oder konkaver Knicke, mit dem Winkel gewogen.
#: Eine sanft gekrümmte Fläche biegt sich in eine Richtung (nahe null),
#: Rauschen in beide (nahe einhalb).
FREEFORM_ROUGH_MIX: Final = 0.3

#: … und wie stark: der 90-Prozent-Wert ihrer Knickwinkel in Grad. Darunter
#: liegt das Float32-Rauschen fast ebener CAD-Flächen — am Wedge-Lock bleiben
#: gemischte Knicke unter 0,1 Grad, und 40 Prozent seiner Oberfläche wären
#: sonst rau.
FREEFORM_ROUGH_BEND: Final = 0.1

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

#: Das Schloss über :data:`_FEATURE_CACHE` und seine vier Nebentabellen.
#: **Die Erkennung läuft in mehr als einem Faden**: die Auswertung im Arbeiter,
#: die Vorschau eines Dialogs daneben (:func:`known_detection`). Nachschlagen
#: und Nachvornerücken waren zwei Schritte, und ein Verdrängen in einem
#: anderen Faden dazwischen warf ``KeyError`` aus ``move_to_end``; das Ablegen
#: schrieb fünf Tabellen nacheinander. Unter dem Schloss ist jedes davon ein
#: Schritt. Gerechnet wird außerhalb — keine Erkennung wartet auf eine andere.
_CACHE_LOCK = threading.RLock()

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
    """Der Fingerabdruck eines Netzes: Ecken und Dreiecke — und nach *Kanten
    verfeinern* der Ursprung je Dreieck (``geom.mesh.refined_units``), denn
    danach zählt die Erkennung.

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
    key: bytes | None = None
    if cache is not None:
        cache.verify()
        known = cache.cache.get("solidon_mesh_key")
        if known is not None:
            key = bytes(known)
    if key is None:
        # Gestreamt statt als ein Bytestück: ``tobytes`` und die Verkettung
        # kopierten an 5,8 Mio. Dreiecken zweimal 209 MB unter dem GIL; der
        # Abdruck ist derselbe, und ``update`` gibt den GIL beim Rechnen her.
        hasher = hashlib.blake2b(digest_size=16)
        hasher.update(np.ascontiguousarray(body.vertices, dtype=np.float64))
        hasher.update(np.ascontiguousarray(body.faces, dtype=np.int64))
        key = hasher.digest()
        if cache is not None:
            cache["solidon_mesh_key"] = key
    # **Und der Ursprung je Dreieck, wo das Netz einen trägt** (R1): Er
    # entscheidet mit, was die Erkennung liest (``geom.mesh.refined_units``),
    # also gehört er in den Abdruck, unter dem sie ihre Antwort merkt. Ein Netz
    # ohne Teilung behält seinen Abdruck von vorher.
    units = refined_units_key(body)
    if units is None:
        return key
    return hashlib.blake2b(key + units, digest_size=16).digest()


def _detection_key(mesh: MeshData) -> bytes:
    """Unter welchem Abdruck die Erkennung eines Netzes gemerkt wird (RM-592).

    :func:`_mesh_key` sagt, ob zwei Netze dieselbe Geometrie sind — dafür
    gelten Ecken und Dreiecke, und unter ihm reisen Bewegungs- und
    Teilungsvermerke über die Platte. Die Erkennung liest aber mehr: Gedrehte
    Normalen, übernommene Flächeninhalte, Facetten und Nahtwinkel, die eine
    starre Bewegung vom Quellnetz mitträgt (``geom.transform._carry_cache``),
    weichen in den letzten Stellen von dem ab, was ``trimesh`` aus denselben
    Ecken rechnet. Unter dem Netzabdruck allein bekam ein frisch gebautes Netz
    die Erkennung eines bewegten Zwillings, und dieselbe Datei trug je nach
    Vorgeschichte der Sitzung zwei Merkmalsstände (Messbank A1: die Lochplatte
    nach dem Beispiel *Halterung anpassen*). Ein Netz ohne mitgetragene Maße
    behält seinen Netzabdruck; einmal je Netz gerechnet wie dieser.
    """
    from app.core.geom.transform import CARRIED_METRICS

    key = _mesh_key(mesh)
    cache = getattr(mesh.raw, "_cache", None)
    if cache is None:
        return key
    names = cache.cache.get(CARRIED_METRICS)
    if not names:
        return key
    known = cache.cache.get("solidon_detection_key")
    if known is not None:
        return bytes(known)
    hasher = hashlib.blake2b(key, digest_size=16)
    for name in names:
        value = cache.cache.get(name)
        hasher.update(name.encode("ascii"))
        parts = value if isinstance(value, list) else [value]
        for part in parts:
            data = np.ascontiguousarray(np.asarray(part))
            hasher.update(data.dtype.str.encode("ascii"))
            hasher.update(np.asarray(data.shape, dtype=np.int64).tobytes())
            hasher.update(data.tobytes())
    detection_key = hasher.digest()
    cache["solidon_detection_key"] = detection_key
    return detection_key


def forget_cache() -> None:
    """Vergisst die gemerkten Erkennungen — für Tests und Messungen."""
    with _CACHE_LOCK:
        _FEATURE_CACHE.clear()
        _CACHE_INDICES.clear()
        _FREEFORM_DROPPED.clear()
        _FREEFORM.clear()
        _UNREADABLE_VOIDS.clear()
    with _MEMORY_LOCK:
        _SUPPORT_CACHE.clear()
        _DIGESTS.clear()
        _BY_GEOMETRY.clear()
        _GEOMETRY_HOLDERS.clear()
        for memory in _MEMORIES.values():
            memory.answers.clear()
            memory.digests.clear()
            memory.lineage.answers.clear()
            memory.lineage.geometric.clear()


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


def as_its_own_body(mesh: MeshData) -> None:
    """Merkt sich, dass ``mesh`` schon die Geometrie ist, die :func:`_one_body` meint.

    Für einen Ausschnitt aus einem verschweißten Körper (``local._part``):
    Sein Schnittrand ist offen, :func:`fully_stitched` verneint deshalb, und
    ein Verschweißen mit der Toleranz des Ausschnitts änderte seine Topologie
    gegen die des Körpers, aus dem er stammt.
    """
    remembered("one_body", mesh.raw, (), lambda: None)


def _welded(mesh: MeshData) -> MeshData | None:
    """Die verschweißte Kopie — oder nichts, wenn es nichts zu verschweißen gab."""
    welded, gone = merge_vertices(mesh)
    return welded if gone else None


#: In welchen Schritten die Vollerkennung ihren erledigten Anteil meldet: ein
#: Tausendstel. Feiner sieht niemand einen Balken wandern, und eine Meldung je
#: Einpassung wären am Meshy-Murmelbrett 168 000 Signale an das Fenster.
SHARE_STEP: Final = 0.001


class _Told:
    """Was ein Balken zuletzt erfahren hat — geteilt von allen Abschnitten einer Erkennung."""

    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value = -1.0


class _Share:
    """Der erledigte Anteil einer Vollerkennung, für Balken und Restzeit (§2.8).

    **Die Erkennung meldete nur ihren Text.** Den Anteil kannte der Aufrufer
    allein als den seines Schritts, und am Piratenschiff mit 1,2 Millionen
    Dreiecken stand der Balken 48 Sekunden auf „Merkmale erkennen · 0 %“,
    während nur die Uhr lief (Durchsicht 0.5.1, KUNDE-14). Ein Abschnitt ist
    ein Bereich des Ganzen; :meth:`part` teilt ihn weiter, :meth:`reach` sagt,
    wie weit er ist. Die Gewichte in :func:`detect` und :func:`_fitted` sind
    die gemessenen Anteile der Etappen an fünf großen Netzen (Median; Drache,
    Piratenschiff, Puppenhausbett, Voronoi-Spiderman, Gartenschlauchhalter).

    Gemeldet wird nur, was wächst, und in Schritten von :data:`SHARE_STEP`.
    **Eine Uhr liest der Anteil nicht** — die Erkennung ist Teil einer reinen
    Funktion (§15.1); er zählt erledigte Etappen, Flecken und Stücke. Wo
    niemand zuhört (``report`` ist ``None``), kostet er einen Vergleich.
    """

    __slots__ = ("_end", "_report", "_start", "_told")

    def __init__(
        self,
        report: Callable[[float], None] | None,
        start: float = 0.0,
        end: float = 1.0,
        told: _Told | None = None,
    ) -> None:
        self._report = report
        self._start = start
        self._end = end
        self._told = told if told is not None else _Told()

    def part(self, begin: float, finish: float) -> _Share:
        """Der Abschnitt von ``begin`` bis ``finish`` dieses Abschnitts."""
        width = self._end - self._start
        return _Share(
            self._report, self._start + begin * width, self._start + finish * width, self._told
        )

    def reach(self, fraction: float) -> None:
        """Dieser Abschnitt ist zu ``fraction`` erledigt (null bis eins)."""
        if self._report is None:
            return
        value = self._start + (self._end - self._start) * min(1.0, max(0.0, fraction))
        told = self._told.value
        if value < told + SHARE_STEP and not value >= 1.0 > told:
            return
        self._told.value = value
        self._report(value)


#: Der Abschnitt, dem niemand zuhört — für Aufrufer ohne Balken.
_UNHEARD: Final = _Share(None)

#: Wie viele Dreiecke eines Flecks so viel Einpassung kosten wie der Fleck
#: selbst. Gemessen an Piratenschiff, Puppenhausbett und Gartenschlauchhalter
#: (Sonde p33, Durchsicht 0.5.1): ein Fleck unter hundert Dreiecken 5 bis 20 ms,
#: bis zehntausend 12 bis 36 ms, darüber 0,3 bis 1,5 s. Die Zahl dient nur dem
#: Balken — sie verteilt seinen Weg so, wie die Zeit vergeht.
SHARE_FACES_PER_FIT: Final = 2_000


def _fit_weight(patch: Sequence[int]) -> float:
    """Was die Einpassung eines Flecks im Balken wiegt (:data:`SHARE_FACES_PER_FIT`)."""
    return 1.0 + len(patch) / SHARE_FACES_PER_FIT


def detect(
    mesh: MeshData,
    *,
    check_cancelled: Callable[[], None] | None = None,
    progress: Callable[[float], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Alles, was dieses Modul erkennen kann, mit stabilen Namen.

    Bohrungen und Stifte teilen ihre Suche (siehe :func:`_cylinders`) — beide
    zu erfragen kostet also, was früher eines kostete.

    ``check_cancelled`` darf ``OperationCancelled`` werfen (§2.8). Geprüft
    wird zwischen Phasen und Fitflecken; ein laufender nativer Aufruf endet
    vorher. Nur ein vollständiger Durchgang wird im Merkmalscache abgelegt.

    ``progress`` erfährt den erledigten Anteil, von null bis eins und nur
    wachsend (:class:`_Share`); eine Antwort aus dem Merker meldet nichts.
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
    key = _detection_key(mesh)
    if check_cancelled is not None:
        check_cancelled()
    known = _cached_detection(key)
    if known is not None:
        # Eine Kopie, weil der Aufrufer sein Ergebnis behalten darf. Die
        # ``Feature``-Objekte selbst sind unveränderlich (``frozen=True``) und
        # dürfen geteilt werden; die Zuordnung darüber hinein nicht.
        return dict(known)

    share = _Share(progress)
    mesh = _one_body(mesh)
    if check_cancelled is not None:
        check_cancelled()
    # Die Etappen und ihr gemessener Anteil (Median über fünf große Netze):
    # Verschweißen zwei Prozent, Ebenen ein Viertel, Einpassung zwei Drittel,
    # der Rest — Kugeln bis gerundete Seiten — sieben Prozent.
    share.reach(0.02)
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
        planar = _large_facet_faces(
            mesh.raw, check_cancelled=check_cancelled, share=share.part(0.02, 0.28)
        )
        if check_cancelled is not None:
            check_cancelled()
        fitted = _fitted(
            mesh, planar=planar, check_cancelled=check_cancelled, share=share.part(0.28, 0.93)
        )
        rest = share.part(0.93, 1.0)
        sphere_candidates = _sphere_candidates(mesh, fitted.spheres)
        sphere_features = detect_spheres(mesh, sphere_candidates, check_cancelled=check_cancelled)
        torus_candidates = _torus_candidates(mesh, fitted.tori)
        torus_features = detect_tori(mesh, torus_candidates, check_cancelled=check_cancelled)
        rest.reach(0.1)
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
        # verschluckt, braucht beides nie (:func:`_face_candidates`). Ebene
        # Reststücke der tangentialen Trennung zählen wie jede ebene Facette
        # (``Fitted.flat``, RM-226).
        if fitted.flat:
            planar = set(planar).union(*fitted.flat)
        face_entries = _planar_face_entries(mesh, planar=planar, check_cancelled=check_cancelled)
        face_entries = _largest_first(mesh.raw, face_entries)
        rest.reach(0.2)
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
        rest.reach(0.45)
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
        rest.reach(0.6)
        if check_cancelled is not None:
            check_cancelled()
        # **Nach dem Langloch und vor dem Einschluss.** Nach dem Langloch,
        # weil eine Reihe Langlöcher Langlöcher bleibt (``slot`` bildet keine
        # Zelle); vor dem Einschluss, weil der die Träger seiner Flächen
        # einsammelt — und die bekommen die Flächen erst, wenn feststeht,
        # welche bleiben (:func:`_faces_finished_in`): Ein dichtes Rändel hat
        # 32 000 Flächen, nach dem Falten sieben (§21.1, RM-207).
        found = patterns_instead_of_cells(mesh, found, check_cancelled=check_cancelled)
        rest.reach(0.7)
        if check_cancelled is not None:
            check_cancelled()
        found = _faces_finished_in(mesh, found, face_entries, check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        found = _faces_on_a_round_wall(mesh, found, check_cancelled=check_cancelled)
        rest.reach(0.75)
        if check_cancelled is not None:
            check_cancelled()
        # **Vor dem Freiformfilter, und das ist keine Reihenfolge nach Gefühl.**
        # Die Schale eines Einschlusses trägt echte Rundformen; blieben sie in
        # der Liste, zählten sie beim Urteil über das ganze Modell mit und
        # schöben es Richtung Freiform. Hier gehen sie weg, weil sie zu einem
        # Einschluss gehören — nicht, weil das Modell eine Figur wäre.
        voids, unreadable = _detect_voids(mesh, check_cancelled=check_cancelled)
        found = voids_instead_of_phantom_bores(found, voids, check_cancelled=check_cancelled)
        rest.reach(0.85)
        if check_cancelled is not None:
            check_cancelled()
        found = _partial_cones_folded(mesh, found, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        found = _partial_bores_marked(mesh, found, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        found = _corners_named_as_fillets(mesh, found, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        found = narrowings_marked(mesh, found, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        freeform = is_a_freeform(
            found, unpublished_round_shapes=unpublished_round_shapes, skin=fitted.freeform_skin
        )
        found, left_out = _shapes_on_a_freeform(
            found, unpublished_round_shapes=unpublished_round_shapes, skin=fitted.freeform_skin
        )
        rest.reach(0.9)
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
    share.reach(1.0)
    return dict(found)


def known_detection(mesh: MeshData) -> dict[FeatureId, Feature] | None:
    """Die gemerkte Erkennung dieses Netzes — oder ``None``, ohne zu rechnen.

    Für Aufrufer, die eine Antwort nehmen, wenn sie dasteht, und sonst ohne
    auskommen: die Live-Vorschau eines Dialogs zeigt Geometrie, keine
    Merkmale, und eine Erkennung von einer Sekunde je getippter Zahl wäre
    dort eine Sekunde für nichts (``scene.evaluate``, ``detect_features``).
    """
    known = _cached_detection(_detection_key(mesh))
    return None if known is None else dict(known)


def _cached_detection(key: bytes) -> dict[FeatureId, Feature] | None:
    """Die gemerkte Erkennung unter diesem Abdruck, nach vorn gerückt — in einem Schritt."""
    with _CACHE_LOCK:
        known = _FEATURE_CACHE.get(key)
        if known is not None:
            _FEATURE_CACHE.move_to_end(key)
        return known


def _remember(
    key: bytes, found: dict[FeatureId, Feature], left_out: int, unreadable: int, freeform: bool
) -> None:
    """Eine vollständige Erkennung unter dem Abdruck ihres Netzes ablegen.

    Die vier Nebentabellen — Flächenindizes als Gewicht der Verdrängung,
    weggelassene Rundformen, das Freiformurteil und unlesbare Schalen —
    werden zusammen mit dem Ergebnis geführt, damit Verdrängung und Nachfrage
    dieselben Einträge sehen. Ob die Antwort gerechnet wurde (:func:`detect`)
    oder von einem bewegten Zwilling stammt (:func:`carry_detection`), ist für
    die Ablage dasselbe.
    """
    weight = sum(
        len(feature.face_indices)
        + sum(len(patch.face_indices) for patch in feature.surface_patches)
        for feature in found.values()
    )
    with _CACHE_LOCK:
        _FEATURE_CACHE[key] = found
        _FEATURE_CACHE.move_to_end(key)
        _CACHE_INDICES[key] = weight
        _FREEFORM_DROPPED[key] = left_out
        _FREEFORM[key] = freeform
        _UNREADABLE_VOIDS[key] = unreadable
        while len(_FEATURE_CACHE) > CACHE_LIMIT or sum(_CACHE_INDICES.values()) > CACHE_INDEX_LIMIT:
            if len(_FEATURE_CACHE) == 1:
                # Ein einzelner Eintrag über der Grenze bleibt: Ihn wegzuwerfen
                # hieße, ihn beim nächsten Aufruf sofort neu zu rechnen — der
                # Cache wäre dann nicht begrenzt, sondern aus. Bis zum
                # 21.09.2026 warf die Schleife ihn weg und brach erst danach
                # ab; dieser Satz stand darunter und stimmte nicht.
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


def moved_twin(source: MeshData, moved: MeshData, transform: Any) -> bool:
    """Ob ``moved`` belegbar das starr bewegte ``source`` ist.

    Die Matrix ist starr (``is_rigid``), das bewegte Netz trägt **dieselben
    Dreiecke** über denselben Eckennummern, und jede Ecke liegt dort, wo die
    Matrix die Ecke des Quellnetzes hinbewegt (:data:`MOVED_TWIN_TOLERANCE`).
    Dann gilt jede Dreiecksnummer eines Merkmals am bewegten Netz weiter.
    Gefragt von :func:`carry_detection` für den Merker der Vollerkennung und
    von der Auswertung für die örtliche Nachmessung eines großen Körpers
    (Review R6) — eine Auskunft, nicht zwei.
    """
    matrix = np.asarray(transform, dtype=float)
    return bool(
        remembered(
            "moved_twin",
            moved.raw,
            (),
            lambda: _moved_twin_checked(source, moved, matrix),
            extra=(_mesh_key(source), _mesh_key(moved), matrix.shape, matrix.tobytes()),
        )
    )


def _moved_twin_checked(source: MeshData, moved: MeshData, matrix: Any) -> bool:
    """Der vollständige Geometriebeleg; alle Verbraucher teilen dieselbe Antwort."""
    from app.core.geom.transform import is_rigid

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
    return bool(np.allclose(moved_vertices, expected, rtol=0.0, atol=MOVED_TWIN_TOLERANCE))


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

    Übertragen wird nur unter Beleg, nicht auf Zusage der Operation
    (:func:`moved_twin`). Damit gelten die Dreiecksnummern der gemerkten
    Merkmale unverändert, und
    ihre Maße folgen der Bewegung über :func:`transformed_features` — dieselbe
    Rechnung, mit der ``moved_object`` die mitgeführten Merkmale nachführt.
    Bleibt dabei ein Merkmal hinter der Bewegung zurück (kein ``exact``), wird
    nichts übertragen, und die Erkennung rechnet wie zuvor.

    Der Rückgabewert sagt, ob ``detect`` das bewegte Netz jetzt aus dem
    Merker beantwortet; die Nebentabellen — weggelassene Rundformen, unlesbare
    Schalen — wandern mit, denn beides sind Eigenschaften der Form, nicht der
    Lage.
    """
    from app.core.perceive.matching import transformed_features

    if check_cancelled is not None:
        check_cancelled()
    source_key = _detection_key(source)
    with _CACHE_LOCK:
        known = _FEATURE_CACHE.get(source_key)
    if known is None:
        return False
    if not moved_twin(source, moved, transform):
        return False
    if check_cancelled is not None:
        check_cancelled()
    moved_key = _detection_key(moved)
    if _cached_detection(moved_key) is not None:
        return True
    carried = transformed_features(known, transform, mesh=moved, check_cancelled=check_cancelled)
    if set(carried.exact) != set(known):
        return False
    with _CACHE_LOCK:
        if source_key in _FEATURE_CACHE:
            _FEATURE_CACHE.move_to_end(source_key)
        side = (
            _FREEFORM_DROPPED.get(source_key, 0),
            _UNREADABLE_VOIDS.get(source_key, 0),
            _FREEFORM.get(source_key, False),
        )
    _remember(
        moved_key,
        dict(carried.candidates),
        *side,
    )
    _log.info("carried %d features onto a moved twin", len(known))
    return True


#: Unter diesem Schlüssel legt eine starre Bewegung am bewegten Netz ab, aus
#: welchem Netz es mit welcher Matrix entstand (:func:`note_movement`).
MOVED_FROM_KEY: Final = "solidon_moved_from"

#: Wie viele Vorfahren ein Bewegungsvermerk höchstens nennt. Eine Operation
#: bewegt einen Körper selten mehr als zweimal hintereinander (*Druckoptimal
#: ausrichten*: drehen, dann anordnen), und jeder Vorfahr kostet nur einen
#: Abdruck und eine Matrix — die Grenze hält eine lange Kette klein, nicht
#: einen gewöhnlichen Fall.
MOVEMENT_NOTE_DEPTH: Final = 4

#: Ein Bewegungsvermerk: Abdruck eines Vorfahren und die Matrix, die ihn auf
#: dieses Netz bewegt — der nächste Vorfahr zuerst.
MovementNote = tuple[tuple[bytes, np.ndarray], ...]


def note_movement(source: MeshData, moved: MeshData, matrix: Any) -> None:
    """Vermerkt am bewegten Netz, aus welchem Netz es mit welcher Matrix entstand.

    Das Gegenstück zu :func:`note_refinement` für eine Bewegung, gesetzt von
    ``geom.transform.apply`` bei jeder starren Matrix. Die gemeldete Bewegung
    einer Operation (``OpResult.transform``) kennt nur einen Körper; wer
    mehrere Körper je mit eigener Matrix bewegt — *Druckoptimal ausrichten*,
    *Auf dem Bett anordnen*, die Kopien eines Musters —, meldet keine, und die
    Erkennung lief an jedem bewegten Netz vollständig neu (der Anlass steht bei
    ``scene.evaluate._motion_of``).

    Trägt ``source`` selbst einen Vermerk, reist er zusammengesetzt mit: Das
    Ausrichten dreht erst und verschiebt dann, und der Eingang der Operation
    ist der Vorfahr des gedrehten Zwischennetzes. Ein Vermerk ist eine Zusage;
    geglaubt wird er erst von :func:`moved_from`, am Eingang und an der
    Geometrie.
    """
    from app.core.geom.transform import composed

    cells = np.asarray(matrix, dtype=np.float64)
    entries = [(_mesh_key(source), cells.copy())]
    entries.extend((key, composed(cells, earlier)) for key, earlier in movement_note(source))
    restore_movement_note(moved, tuple(entries[:MOVEMENT_NOTE_DEPTH]))


def movement_note(mesh: MeshData) -> MovementNote:
    """Der Vermerk aus :func:`note_movement` — leer, wenn das Netz keinen trägt.

    Für den Plattencache wie :func:`refinement_note`: Ein von der Platte
    gelesenes Netz hätte ihn sonst nicht mehr, und nach dem Wiederöffnen lief
    die Erkennung an jedem ausgerichteten Körper neu.
    """
    cache = getattr(mesh.raw, "_cache", None)
    if cache is None:
        return ()
    cache.verify()
    noted = cache.cache.get(MOVED_FROM_KEY)
    if not noted:
        return ()
    return tuple((bytes(key), np.asarray(cells, dtype=np.float64)) for key, cells in noted)


def restore_movement_note(mesh: MeshData, note: MovementNote) -> None:
    """Legt einen Bewegungsvermerk an ``mesh`` — aus der Bewegung oder von der Platte.

    Auch von der Platte bleibt er eine Zusage; geglaubt wird er erst von
    :func:`moved_from`.
    """
    cache = getattr(mesh.raw, "_cache", None)
    if cache is None or not note:
        return
    cache.verify()
    cache[MOVED_FROM_KEY] = tuple(
        (bytes(key), np.asarray(cells, dtype=np.float64).copy()) for key, cells in note
    )


def moved_from(
    moved: MeshData, sources: Sequence[MeshData]
) -> tuple[MeshData, tuple[tuple[float, ...], ...]] | None:
    """Welcher der ``sources`` ``moved`` belegbar starr bewegt ist — und mit welcher Matrix.

    Gefragt wird der Vermerk aus :func:`note_movement`: Ein Vorfahr, dessen
    Abdruck einer der Quellen gleicht, und eine Matrix, unter der
    :func:`moved_twin` das bewegte Netz als dieselben Dreiecke an den bewegten
    Ecken bestätigt. Ohne Vermerk, ohne passende Quelle oder ohne Beleg:
    ``None``, und die Erkennung rechnet wie zuvor. Eine Spiegelung dreht den
    Umlaufsinn und besteht den Beleg deshalb nie — ihr Gewinde wechselt die
    Hand und wird neu gelesen.

    **Und ein Netz, das selbst eine der Quellen ist, wurde nicht bewegt.** Eine
    Operation, die ihre Eingänge durchreicht (*Überschneidungen prüfen*, das
    Original beim Duplizieren), gibt ein Netz zurück, dessen Vermerk von einer
    früheren Bewegung stammt — und steht dessen Vorfahr ebenfalls in der
    Szene, etwa das Original einer verschobenen Kopie, belegte der Vermerk
    eine Bewegung, die dieser Schritt nie gemacht hat. Die Merkmale wären ein
    zweites Mal verschoben worden.
    """
    note = movement_note(moved)
    if not note:
        return None
    by_key = {_mesh_key(source): source for source in sources}
    if _mesh_key(moved) in by_key:
        return None
    for key, cells in note:
        source = by_key.get(key)
        if source is not None and moved_twin(source, moved, cells):
            return source, tuple(tuple(float(value) for value in row) for row in cells)
    return None


#: Unter diesem Schlüssel legt *Kanten verfeinern* am feineren Netz ab, aus
#: welchem Dreieck welches Netzes jedes neue stammt (:func:`note_refinement`).
REFINED_FROM_KEY: Final = "solidon_refined_from"


def note_refinement(source: MeshData, refined: MeshData, origin: np.ndarray) -> None:
    """Vermerkt am feineren Netz, aus welchem Dreieck von ``source`` jedes stammt.

    Abgelegt im Cache des Netzes selbst, der mit dessen Geometrie verfällt —
    dieselbe Ablage wie der Abdruck in :func:`_mesh_key`. Ein Vermerk ist eine
    Zusage der Operation; geglaubt wird er erst von :func:`refined_twin`.
    """
    restore_refinement_note(refined, _mesh_key(source), origin)


def refinement_note(mesh: MeshData) -> tuple[bytes, np.ndarray] | None:
    """Der Vermerk aus :func:`note_refinement` — Abdruck des Eingangs und Herkunft je Dreieck.

    Für den Plattencache: Der Vermerk lebt im Speicher des Netzes, und ein
    von der Platte gelesenes Netz hatte ihn nicht mehr. Nach dem Wiederöffnen
    lief die Erkennung dann am feineren Netz neu und las dort etwas anderes
    als in der Sitzung (Durchsicht 0.5.1, erkennung-02).
    """
    cache = getattr(mesh.raw, "_cache", None)
    if cache is None:
        return None
    cache.verify()
    noted = cache.cache.get(REFINED_FROM_KEY)
    if noted is None:
        return None
    key, origin = noted
    return bytes(key), np.asarray(origin, dtype=np.int64)


def restore_refinement_note(mesh: MeshData, key: bytes, origin: np.ndarray) -> None:
    """Legt einen Vermerk an ``mesh`` — aus der Operation oder von der Platte.

    Auch von der Platte bleibt er eine Zusage und kein Beleg: Geglaubt wird er
    erst, wenn :func:`refined_twin` ihn am Eingang und an der Geometrie
    nachgeprüft hat.
    """
    cache = getattr(mesh.raw, "_cache", None)
    if cache is None:
        return
    cache.verify()
    cache[REFINED_FROM_KEY] = (bytes(key), np.asarray(origin, dtype=np.int64))


def refined_twin(source: MeshData, refined: MeshData) -> np.ndarray | None:
    """Die Herkunft jedes Dreiecks von ``refined`` — wenn es belegbar ``source`` ist, feiner.

    Das Gegenstück zu :func:`moved_twin` für eine Teilung: Der Vermerk aus
    :func:`note_refinement` muss zu genau diesem Eingang gehören (derselbe
    Abdruck), jede Ecke eines neuen Dreiecks liegt in der Ebene seines
    Ursprungs, jedes neue Dreieck zeigt nach derselben Seite wie er, und die
    neuen Dreiecke eines Ursprungs decken zusammen genau seine Fläche. Dann
    ist die Oberfläche dieselbe, und jede Dreiecksnummer eines Merkmals lebt
    in den Dreiecken weiter, die aus ihr hervorgingen.
    Die Grenze ist :data:`MOVED_TWIN_TOLERANCE`, je Ecke für die Ebene und je
    Umfang für die Fläche — eine Rechengrenze, keine Geometrietoleranz.

    Gerechnet über Kreuzprodukte und Normen über eine Achse, die auf jeder
    Maschine dieselben Bits geben: An der Antwort hängt, ob die Erkennung
    läuft oder übertragen wird.
    """
    noted = refinement_note(refined)
    if noted is None:
        return None
    key, origin = noted
    if key != _mesh_key(source):
        return None
    corners = np.asarray(refined.raw.faces, dtype=np.int64)
    count = len(source.raw.faces)
    if origin.shape != (len(corners),) or not len(origin):
        return None
    if int(origin.min()) < 0 or int(origin.max()) >= count:
        return None
    old = np.asarray(source.raw.triangles, dtype=np.float64)
    first, second, third = old[:, 0], old[:, 1], old[:, 2]
    cross = np.cross(second - first, third - first)
    doubled = np.linalg.norm(cross, axis=1)
    perimeter = (
        np.linalg.norm(second - first, axis=1)
        + np.linalg.norm(third - second, axis=1)
        + np.linalg.norm(first - third, axis=1)
    )
    points = np.asarray(refined.raw.vertices, dtype=np.float64)
    flat = doubled[origin] > MOVED_TWIN_TOLERANCE * perimeter[origin]
    unit = cross[origin][flat] / doubled[origin][flat][:, None]
    anchor = first[origin][flat]
    for column in range(3):
        offset = points[corners[flat, column]] - anchor
        if np.abs((offset * unit).sum(axis=1)).max(initial=0.0) > MOVED_TWIN_TOLERANCE:
            return None
    new = points[corners]
    crossed = np.cross(new[:, 1] - new[:, 0], new[:, 2] - new[:, 0])
    # **Und nach derselben Seite.** In seiner Ebene liegt jedes neue Dreieck
    # schon; längs der alten Normalen misst es deshalb seinen ganzen Inhalt —
    # oder dessen Gegenteil, wenn die Teilung es umgedreht hat. Ebene und
    # Inhalt allein ließen ein umgedrehtes Stück durch, und die übertragenen
    # Merkmale trugen danach Innen und Außen der anderen Seite.
    facing = (crossed[flat] * unit).sum(axis=1)
    if (facing < -MOVED_TWIN_TOLERANCE * perimeter[origin][flat]).any():
        return None
    pieces = np.linalg.norm(crossed, axis=1)
    covered = np.bincount(origin, weights=pieces, minlength=count)
    if (np.abs(covered - doubled) > MOVED_TWIN_TOLERANCE * perimeter).any():
        return None
    return origin


def refined_features(
    features: Mapping[FeatureId, Feature], origin: np.ndarray, count: int
) -> dict[FeatureId, Feature] | None:
    """Die Merkmale eines Netzes auf seine feiner geteilte Kopie — Dreieck für Dreieck.

    Jede Dreiecksnummer eines Merkmals und seiner Teilträger wird durch die
    Nummern der Dreiecke ersetzt, die aus ihr hervorgingen; Maße und Namen
    bleiben, denn die Oberfläche ist dieselbe (:func:`refined_twin`). Eine
    Nummer außerhalb der ``count`` Dreiecke des Eingangs gehört zu keinem
    Merkmal dieses Netzes — dann wird nichts übertragen.
    """
    order = np.argsort(origin, kind="stable")
    starts = np.searchsorted(origin[order], np.arange(count + 1, dtype=np.int64))

    def children(indices: Sequence[int]) -> tuple[int, ...] | None:
        rows = np.asarray(indices, dtype=np.int64)
        if not len(rows):
            return ()
        if int(rows.min()) < 0 or int(rows.max()) >= count:
            return None
        lengths = starts[rows + 1] - starts[rows]
        before = np.cumsum(lengths) - lengths
        places = np.repeat(starts[rows] - before, lengths) + np.arange(int(lengths.sum()))
        # In Stücken zum Tupel (``python_values``): Die größte Fläche des
        # verfeinerten Spielwürfels hat 3 979 168 Dreiecke, und ein Tupel aus
        # einem Stück hielt den Hauptfaden 150 ms an (RM-212).
        return tuple(python_values(np.sort(order[places])))

    carried: dict[FeatureId, Feature] = {}
    for name, feature in features.items():
        faces = children(feature.face_indices)
        patches: list[SurfacePatch] = []
        for patch in feature.surface_patches:
            rows = children(patch.face_indices)
            if rows is None:
                return None
            patches.append(replace(patch, face_indices=rows))
        if faces is None:
            return None
        carried[name] = replace(feature, face_indices=faces, surface_patches=tuple(patches))
    return carried


def carry_refined_detection(
    source: MeshData,
    refined: MeshData,
    origin: np.ndarray,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Die gemerkte Erkennung eines Netzes auf seine feiner geteilte Kopie übertragen.

    Wie :func:`carry_detection` für eine Bewegung: ``detect`` beantwortet das
    feinere Netz danach aus dem Merker. ``origin`` kommt aus
    :func:`refined_twin` — ohne den Beleg wird nicht gerufen.

    **Eine offene Stelle reist nicht mit.** Sie ist eine Auskunft über das
    Netz und nicht über die Oberfläche: :func:`detect_edge_loops` zählt die
    Kanten ohne Partner und mittelt die Ecken des Rands, und die Teilung setzt
    neue darauf. An einem Kasten ohne Deckel stand übertragen weiter „4 offene
    Kanten“, wo das feinere Netz 32 trägt (25.09.2026). Ein offenes Netz wird
    deshalb erkannt wie vor dieser Abkürzung.
    """
    if check_cancelled is not None:
        check_cancelled()
    source_key = _detection_key(source)
    with _CACHE_LOCK:
        known = _FEATURE_CACHE.get(source_key)
    if known is None or any(feature.kind == "edge_loop" for feature in known.values()):
        return False
    refined_key = _detection_key(refined)
    if _cached_detection(refined_key) is not None:
        return True
    carried = refined_features(known, origin, len(source.raw.faces))
    if carried is None:
        return False
    with _CACHE_LOCK:
        if source_key in _FEATURE_CACHE:
            _FEATURE_CACHE.move_to_end(source_key)
        side = (
            _FREEFORM_DROPPED.get(source_key, 0),
            _UNREADABLE_VOIDS.get(source_key, 0),
            _FREEFORM.get(source_key, False),
        )
    _remember(refined_key, carried, *side)
    _log.info("carried %d features onto a refined twin", len(known))
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
    read_helices: Sequence[Helix] = find_helices(mesh) if helices is None else helices
    if not read_helices:
        return found

    # Die Dateireihenfolge ihrer Kantenzüge darf keine Merkmalskennung bestimmen.
    # Gleiche Mittelpunkte werden über die gemessenen Gewindemaße aufgelöst —
    # nach derselben Regel wie jede andere Nummer (:func:`numbering_order`).
    order = numbering_order(
        len(read_helices),
        (
            (lambda index: read_helices[index].centre, NUMBERING_DIGITS),
            (
                lambda index: (
                    read_helices[index].diameter,
                    read_helices[index].pitch,
                    read_helices[index].length,
                    float(read_helices[index].internal),
                ),
                NUMBERING_DIGITS,
            ),
        ),
        lambda index: _corner_key(mesh.raw, np.asarray(read_helices[index].face_indices)),
    )
    helices = [read_helices[index] for index in order]
    kept = dict(found)
    for number, helix in enumerate(helices, start=1):
        kept = without_phantoms_on(kept, helix.face_indices)
        identifier = FeatureId(f"thread_{number}")
        measured: dict[str, Any] = {}
        sources: dict[str, Any] = {
            "diameter": "fit",
            "pitch": "fit",
            "centre": "fit",
            "axis": "fit",
            "length": "facets",
            "handedness": "fit",
        }
        if helix.measured:
            # **An den Kanten gemessen, nicht am Spektrum geschätzt** (P2.5):
            # Die Händigkeit ist das Vorzeichen der Steigung jeder windenden
            # Kante, die Gangzahl die Periodizität aller Wendeln — dieselben
            # Fragen wie am exakten Kern (``brep.thread``). Die Händigkeit
            # heißt deshalb ``facets``: belegt, nicht geraten; ein
            # Linksgewinde am Netz sperrt das Neuschneiden wie am exakten
            # Körper (``types.thread_is_left_handed``). Vorschub und
            # Gangzahl stehen daneben, die Wendelabweichung als ``uncertainty``
            # wie beim exakten Leser — die Passung rechnet damit statt mit
            # einer Rasterstufe (``scene.fits._pitch_uncertainty``).
            root = helix.crest_radius + (helix.depth if helix.internal else -helix.depth)
            measured = {
                "lead": helix.lead,
                "starts": helix.starts,
                "crest_radius": helix.crest_radius,
                "root_radius": root,
                "depth": helix.depth,
                "turns": helix.turns,
                "uncertainty": float(helix.uncertainty or 0.0),
            }
            sources.update(
                handedness="facets",
                lead="fit",
                starts="facets",
                crest_radius="fit",
                root_radius="fit",
                depth="fit",
                turns="facets",
                uncertainty="facets",
            )
        kept[identifier] = Feature(
            id=identifier,
            kind="thread",
            provenance="detected",
            measure_sources=sources,
            # **Ungerundet, wie am exakten Kern** (Regel 6): Hier standen Ø,
            # Steigung und Länge auf vier Stellen gerundet — im Kern, und mit
            # einer gemessenen Wendelabweichung von 4·10⁻⁵ mm hätte die Rundung
            # die Passungsprüfung mehr verschoben als die Messung selbst.
            params={
                "diameter": helix.diameter,
                "pitch": helix.pitch,
                "centre": helix.centre,
                "axis": helix.axis,
                "internal": helix.internal,
                "length": helix.length,
                "handedness": helix.handedness,
                **measured,
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
    return _FREEFORM_DROPPED.get(_detection_key(mesh), 0)


def recognised_as_freeform(mesh: MeshData) -> bool:
    """Ob :func:`detect` dieses Netz als Freiform eingestuft hat.

    ``False`` für jedes konstruierte Teil — und für ein Netz, das ``detect``
    noch nicht gesehen hat. Die Auswertung fragt unmittelbar nach ``detect``
    und macht zusammen mit :func:`freeform_dropped` einen Befund daraus: Eine
    Haut ohne eingepasste Splitter hat nichts weggelassen und ist trotzdem
    eine Freiform, auf der keine Rundformen geführt werden.
    """
    return _FREEFORM.get(_detection_key(mesh), False)


def unreadable_void_shells(mesh: MeshData) -> int:
    """Wie viele Schalen der Körper hat, wenn :func:`detect` seine Einschlüsse nicht lesen konnte.

    Null für jedes Modell, dessen Schalenpaare die native Differenz lesen
    konnte — und null für ein Netz, das ``detect`` noch nicht gesehen hat.
    Die Auswertung fragt unmittelbar nach ``detect`` wie bei
    :func:`freeform_dropped` und macht daraus einen Befund: Ein Einschluss,
    der fehlt, weil ein Schalenpaar nicht lesbar war, verschwindet sonst still.
    """
    return _UNREADABLE_VOIDS.get(_detection_key(mesh), 0)


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
    flat: tuple[tuple[int, ...], ...] = ()
    """Ebene Stücke, die erst die tangentiale Trennung von ihren Rundungen
    gelöst hat (RM-226): Ebenen zwischen tangential anschließenden Rundungen,
    die die Ebenenregel als Mantelstreifen las. :func:`detect` nimmt sie zu
    den Ebenen."""


def _cylinders(mesh: MeshData) -> Cylinders:
    """Nur die Zylinder, für jeden, der die übrigen Formen nicht braucht."""
    return _fitted(mesh).cylinders


def _fitted(
    mesh: MeshData,
    *,
    planar: set[int] | None = None,
    check_cancelled: Callable[[], None] | None = None,
    share: _Share = _UNHEARD,
) -> Fitted:
    """Jeder gekrümmte Fleck des Körpers, einmal eingepasst.

    Bohrungen und Stifte sind dieselbe Suche, zweimal gelesen, und die Suche
    ist die teure Hälfte: an einem Körper mit einer Million Dreiecken kosten
    die Facetten und die zusammenhängenden Flecken Sekunden. Sie zweimal zu
    machen verdoppelte die Erkennungszeit für nichts — also passiert sie hier,
    und beide Aufrufer filtern das Ergebnis.

    ``share`` erfährt, wie weit die Einpassung ist (:class:`_Share`): gezählt
    werden Flecken und Stücke, gewichtet nach den gemessenen Anteilen der
    Runden — Flecken sechs Prozent, ganze Flecken 44, Nachtrennung zehn,
    Stücke 32, Zusammenlegung acht (Median über fünf große Netze).
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
        flat: list[tuple[int, ...]] = []
        areas = np.asarray(body.area_faces, dtype=float)
        total_area = float(areas.sum())
        freeform_skin = False
        #: Die Dreiecke, die als Stücke eines wandernden Umrisses eingepasst
        #: wurden (RM-243) — sie fallen nach der Zusammenlegung.
        outline = np.zeros(len(body.faces), dtype=bool)
        #: Die Dreiecke der ganzen Flecken, die ein wandernder Umriss sind —
        #: an ihnen fragt :func:`_between_corners_of`, ob ein Nachbarfleck
        #: dazugehört (RM-254).
        wandering = np.zeros(len(body.faces), dtype=bool)
        #: Kennzahlen von Flecken, an denen der Kegel nichts hergab. Wer
        #: deckungsgleich zu einem davon ist, bekommt dieselbe leere Antwort,
        #: ohne dass der Löser noch einmal hundert Auswertungen dafür braucht
        #: (:func:`_rigid_key`).
        no_cone_here: set[tuple[Any, ...]] = set()

        def classify_read(patch: list[int]) -> bool:
            """Die erste Form, die auf diesen Fleck passt — oder keine (gerechnet)."""
            ball: SphereFit | None = None
            # Ein bis zur Geometriegenauigkeit belegter Zylinder braucht keinen
            # konkurrierenden Kegellauf. Bei einer nur angenäherten Zylinderhaut
            # wird der Kegel weiterhin gefragt: Eine kurze, flache Verjüngung
            # kann innerhalb der Wandtoleranz auch auf einen Zylinder passen.
            fit = fit_cylinder(body, patch, check_cancelled=check_cancelled)
            if check_cancelled is not None:
                check_cancelled()
            cylinder = (
                fit if fit is not None and fit.good and _fits_in_the_body(mesh, fit) else None
            )
            if cylinder is not None and _cylinder_precludes_a_cone(body, cylinder, patch):
                found.append((cylinder, patch))
                return True
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
            if (
                cone is not None
                and cone.half_angle >= CONE_MIN_ANGLE
                and cone.good
                and _cone_is_recognisable(body, cone, patch, check_cancelled=check_cancelled)
            ):
                ball = fit_sphere(body, patch, check_cancelled=check_cancelled)
                if check_cancelled is not None:
                    check_cancelled()
                if not _a_ball_fits_far_better(cone, ball):
                    # Beide vollständigen Nachweise lesen dieselbe Originalhaut.
                    # Ein zusätzlicher Freiheitsgrad verdrängt den Zylinder nur,
                    # wenn der Kegel diese Haut mindestens ebenso genau trifft.
                    if (
                        cylinder is not None
                        and cylinder.fit_error is not None
                        and cone.fit_error is not None
                        and cylinder.fit_error < cone.fit_error
                    ):
                        found.append((cylinder, patch))
                    else:
                        cones.append((cone, patch))
                    return True
            if cylinder is not None:
                found.append((cylinder, patch))
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

        extents = np.asarray(body.extents, dtype=float)
        diagonal = math.sqrt(float((extents * extents).sum()))
        closed = bool(body.is_watertight)
        consistent = bool(body.is_winding_consistent)

        def classify(patch: list[int]) -> bool:
            """Die erste Form, die auf diesen Fleck passt — oder keine.

            **Auch aus dem Gedächtnis eines früheren Körpers** (RM-592, G2): Was
            :func:`classify_read` liest, steht im Fleckabdruck (Lesung, Normalen,
            Ursprung), in der Diagonale, aus der die Toleranzen der Einpassungen
            kommen, und im Zustand der Runde — ob ein deckungsgleicher Fleck schon
            keinen Kegel hatte (``no_cone_here``). Die Hülle des Körpers fragt ein
            Treffer neu (:data:`_HULL_QUESTIONS`). Gemerkt werden Antwort, Fits und
            ob der Fleck ``no_cone_here`` ergänzte; ein Treffer trägt sie in die
            Listen dieser Runde ein wie die Rechnung.
            """
            if check_cancelled is not None:
                check_cancelled()
            if _face_count(body, patch) < MIN_PATCH_FACES:
                return False
            if not _ACROSS_BODIES[0]:
                return classify_read(patch)
            shape = _rigid_key(body, patch)
            known_shape = shape is not None and shape in no_cone_here
            # Die Körperzahlen der Lesung dazu (:func:`_support_handle`): Ohne
            # sie gab ein Körper mit Loch im Netz die Fits des dichten zurück,
            # in der letzten Stelle anders (Messbank A1, P5).
            key = hashlib.blake2b(
                _patch_print(body, patch)
                + _body_numbers(
                    diagonale=diagonal,
                    dicht=closed,
                    umlauf=consistent,
                    deckungsgleich=_coincident_vertices(body),
                )
                + _exact_bytes(("runde" in _LEFT_OUT or known_shape, _classify_settings())),
                digest_size=16,
            ).digest()
            known = _known_across(_CLASSIFIED, body, key)
            if known is not _UNKNOWN:
                answer, cylinders, kegel, balls, rings, added, asked = known
                if "rueckfrage" in _LEFT_OUT or all(
                    _cylinder_fits(mesh, axis, radius) == fits for axis, radius, fits in asked
                ):
                    found.extend((fit, patch) for fit in cylinders)
                    cones.extend((fit, patch) for fit in kegel)
                    spheres.extend((fit, patch) for fit in balls)
                    for ring in rings:
                        tori.append((ring, patch))
                    if added and shape is not None:
                        no_cone_here.add(shape)
                    return bool(answer)
            marks = (len(found), len(cones), len(spheres), len(tori.entries))
            questions: list[tuple[tuple[float, ...], float, bool]] = []
            asking = _HULL_QUESTIONS.set(questions)
            try:
                answer = classify_read(patch)
            finally:
                _HULL_QUESTIONS.reset(asking)
            added = not known_shape and shape is not None and shape in no_cone_here
            _keep_across(
                _CLASSIFIED,
                body,
                key,
                (
                    answer,
                    tuple(fit for fit, _patch in found[marks[0] :]),
                    tuple(fit for fit, _patch in cones[marks[1] :]),
                    tuple(fit for fit, _patch in spheres[marks[2] :]),
                    tuple(fit for fit, _patch in tori.entries[marks[3] :]),
                    added,
                    tuple(questions),
                ),
            )
            return answer

        # **Nach Größe gefragt, nicht nach der Lage** (RM-210): Die Folge der
        # Flecken entscheidet, welcher von zwei deckungsgleichen zuerst seinen
        # Kegel sucht und für den anderen mitantwortet (:func:`_rigid_key`),
        # und in welcher Folge die Zusammenlegung die Stücke sieht.
        # :func:`in_body_order` ist unabhängig von der Dreiecksfolge, aber nicht
        # drehfest; die Fläche ist beides.
        patches = _in_size_order(
            body, _connected_patches(body, curved, check_cancelled=check_cancelled)
        )
        share.reach(0.06)
        whole = share.part(0.06, 0.5)

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
        fitting = [patch for patch in patches if _face_count(body, patch) >= MIN_PATCH_FACES]
        whole_weight = sum(_fit_weight(patch) for patch in fitting)
        weighed = 0.0
        # **Erst der Stapel, dann die Flecken der Reihe nach** (RM-209): Er sagt
        # für alle zugleich, welcher Kegel- und Ringlauf sicher vergeblich
        # wäre; ``classify`` fragt danach wie immer, und nur diese Läufe
        # entfallen (:func:`_screened_fits`).
        looping = whole.part(SCREEN_SHARE, 1.0)
        with _screening(
            body,
            fitting,
            shapes=no_cone_here,
            check_cancelled=check_cancelled,
            share=whole.part(0.0, SCREEN_SHARE),
        ):
            for patch_index, patch in enumerate(patches):
                if check_cancelled is not None:
                    check_cancelled()
                if _face_count(body, patch) < MIN_PATCH_FACES:
                    continue
                if not classify(patch):
                    unresolved.append(patch_index)
                weighed += _fit_weight(patch)
                looping.reach(weighed / whole_weight)
        share.reach(0.5)

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
            jumps = curvature_jumps(body, check_cancelled)
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
                or _rough_facet_area(body, planar) >= total_area * FREEFORM_ROUGH_SHARE
            )

        share.reach(0.6)

        def heavy(piece: list[int]) -> bool:
            """Ob ein Stück einer Haut Gewicht hat (:data:`FREEFORM_PIECE_SHARE`)."""
            return float(areas[piece].sum()) >= total_area * FREEFORM_PIECE_SHARE

        # Gewogen wird je eingepasstem Stück, ein ungeteilter Fleck als eines.
        planned = max(
            1.0,
            sum(
                (
                    sum(
                        _fit_weight(piece)
                        for piece in curvature_splits[index]
                        if heavy(piece) or not freeform_skin
                    )
                    if len(curvature_splits[index]) > 1
                    else _fit_weight(patches[index])
                )
                for index in unresolved
            ),
        )

        def divided(target: list[int], inside: list[list[int]]) -> list[bool]:
            """Die sechste Runde an einem Ziel (RM-226): trennen, fragen, prüfen.

            Jedes Stück der tangentialen Trennung wird gefragt wie jedes andere.
            Danach zählt nur, was als eigene Rundform steht: Scheiben eines
            gezogenen Zugs werden als Ganzes gefragt (:func:`_drawn_chains`), und
            ein Stück, das nur an den unerklärten Rest seines Ziels grenzt, ist
            ein Stück dieses Rests (:func:`_enclosed_rounds`). Was nicht steht,
            trägt auch nichts ein — seine Einträge aus ``classify`` gehen wieder,
            ebenso die Kugel- und Ringkandidaten der ebenen Reststücke. Steht
            nichts, bleibt das Ziel, wie es war. Steht etwas, ersetzt es die
            Ringkandidaten des Ziels und, war das Ziel der ganze Fleck, die
            seiner Nachtrennungsstücke ``inside``.
            """
            pieces = _tangential_pieces(body, mesh, target, check_cancelled)
            if not pieces:
                return []
            marks = (len(found), len(cones), len(spheres))
            asked = list(pieces)
            answered = [classify(piece) for piece in pieces]
            here = {id(piece): fit for fit, piece in found[marks[0] :]}
            chains = _drawn_chains(
                _touching_pieces(body, pieces), [here.get(id(piece)) for piece in pieces]
            )
            if chains:
                linked = {number for chain in chains for number in chain}
                pieces = [piece for number, piece in enumerate(pieces) if number not in linked]
                answered = [known for number, known in enumerate(answered) if number not in linked]
                for chain in chains:
                    (joined,) = in_body_order(
                        body, [[index for number in chain for index in asked[number]]]
                    )
                    asked.append(joined)
                    pieces.append(joined)
                    answered.append(classify(joined))
            plain = [
                not known and _in_one_plane(body, piece)
                for piece, known in zip(pieces, answered, strict=True)
            ]
            enclosed = _enclosed_rounds(_touching_pieces(body, pieces), answered, plain)
            settled = [known and number not in enclosed for number, known in enumerate(answered)]
            standing = any(settled)
            # Was steht, bleibt eingetragen; neben ihm auch die Kandidaten des
            # unerklärten Rests, auf den keine Form passte — sie zählen weiter
            # für das Freiformurteil, an Stelle der Kandidaten des Ziels.
            kept = {
                id(piece)
                for piece, known, answer, flat_piece in zip(
                    pieces, settled, answered, plain, strict=True
                )
                if known or (standing and not answer and not flat_piece)
            }
            found[marks[0] :] = [entry for entry in found[marks[0] :] if id(entry[1]) in kept]
            cones[marks[1] :] = [entry for entry in cones[marks[1] :] if id(entry[1]) in kept]
            spheres[marks[2] :] = [entry for entry in spheres[marks[2] :] if id(entry[1]) in kept]
            for piece in asked:
                if id(piece) not in kept:
                    tori.drop_patch(piece)
            if standing:
                for done in [target, *inside]:
                    tori.drop_patch(done)
                flat.extend(
                    tuple(piece)
                    for piece, flat_piece in zip(pieces, plain, strict=True)
                    if flat_piece
                )
            return settled

        weighed = 0.0
        by_piece = share.part(0.6, 0.92)
        ordered_pieces = {
            patch_index: _in_size_order(body, curvature_splits[patch_index])
            for patch_index in unresolved
        }
        if not freeform_skin:
            # Ungeteilte Flecken fragt die sechste Runde als Ganzes: ihre
            # Abdrücke samt Nahtwinkeln in einem Zug (:func:`_tangential_pieces`).
            _patch_prints(
                body,
                [
                    patches[patch_index]
                    for patch_index in unresolved
                    if len(ordered_pieces[patch_index]) <= 1
                    and _face_count(body, patches[patch_index]) >= 2 * MIN_PATCH_FACES
                ],
                seams=True,
            )
        # Der Stapel fragt die Stücke, die ``classify`` gleich der Reihe nach
        # fragt: die Stücke jedes geteilten Flecks, auf einer Haut nur die von
        # Gewicht (RM-209, wie in der ersten Runde).
        asked_pieces = [
            piece
            for pieces in ordered_pieces.values()
            if len(pieces) > 1
            for piece in pieces
            if heavy(piece) or not freeform_skin
        ]
        piece_screening = _screening(
            body,
            asked_pieces,
            shapes=no_cone_here,
            check_cancelled=check_cancelled,
            share=by_piece.part(0.0, SCREEN_SHARE),
        )
        by_piece = by_piece.part(SCREEN_SHARE, 1.0)

        # **Zuletzt die Stücke.** Sie kommen nach allen ganzen Flecken und
        # nicht mehr unmittelbar nach ihrem eigenen: Das Urteil über die Haut
        # muss vorher stehen, sonst hinge es daran, welcher Fleck zuerst
        # scheitert.
        with piece_screening:
            for patch_index in unresolved:
                patch = patches[patch_index]
                if check_cancelled is not None:
                    check_cancelled()
                pieces = ordered_pieces[patch_index]
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
                    pieces = [piece for piece in pieces if heavy(piece)]
                # Jedes Stück wird gefragt, nicht nur bis zum ersten Treffer — die
                # Liste ist Absicht, kein ``any`` mit Kurzschluss.
                classified: list[bool] = []
                if split_apart:
                    for piece in pieces:
                        classified.append(classify(piece))
                        weighed += _fit_weight(piece)
                        by_piece.reach(weighed / planned)
                else:
                    weighed += _fit_weight(patch)
                    by_piece.reach(weighed / planned)
                # **Und ein Umriss ist kein Stapel von Kreisen** (RM-243): Reihen
                # sich die Stücke als tangential wandernde Kreise aneinander, ist
                # der Fleck die gerundete Seite eines Schriftzugs, einer Strebe,
                # eines geschwungenen Griffs, und seine Stücke sind keine Merkmale.
                # Stehen bleibt, was ein gezeichneter oder bestätigter Bogen ist —
                # ein CAD-Umriss setzt Bögen und Splines nebeneinander.
                # Zurückgezogen wird erst nach der Zusammenlegung
                # (:func:`_off_the_outline`): Ein Stück, das dort mit einem anderen
                # Fleck zu einer Fläche verschmilzt, ist bestätigt.
                standing = (
                    _wandering_outline(body, pieces, check_cancelled) if any(classified) else None
                )
                if standing is not None:
                    wandering[np.asarray(patch, dtype=np.intp)] = True
                    for number, (piece, known) in enumerate(zip(pieces, classified, strict=True)):
                        if known and number not in standing:
                            outline[np.asarray(piece, dtype=np.intp)] = True
                leftovers: list[list[int]] = [] if split_apart else [patch]
                for piece, known in zip(pieces, classified, strict=False):
                    if not known:
                        separated = _cylinder_beside_a_torus(
                            body, mesh, piece, tori, check_cancelled=check_cancelled
                        )
                        if separated is not None:
                            found.append(separated)
                        else:
                            leftovers.append(piece)
                if not any(classified):
                    # **Dritte Runde, für den Mantel eines knapp aufgezogenen
                    # Langlochs** (RM-155): kein Zylinder, weil der Weg zu groß
                    # ist, und keine zwei Bögen, weil die Flanken für die
                    # Krümmungstrennung zu schmal sind. Als Ganzes ist er trotzdem
                    # eine Form — ein Prisma über einem Stadion —, und die wird hier
                    # eingepasst. Nach dem Split und nicht davor: Was zwei Bögen
                    # ergibt, setzt :mod:`app.core.perceive.slots` zusammen wie
                    # bisher.
                    stadium = fit_stadium(body, patch)
                    if stadium is not None and stadium.good and stadium.inward:
                        stadiums.append((stadium, patch))
                        tori.drop_patch(patch)
                        continue
                # **Vierte Runde, für die Bögen eines Prismas** (RM-219): Ein
                # extrudierter Umriss aus tangentialen Bögen und Geraden zerfällt
                # nach :data:`CURVATURE_JUMP` nicht, und auf das Ganze passt kein
                # Zylinder. An einem Prisma ist der Radius genau genug, um an
                # jedem Wechsel zu trennen (:func:`_arcs_of_a_prism`); eingepasst
                # wird ein Stück nur, wenn es ein gezeichneter Bogen ist (:func:`_exactly_an_arc`).
                arcs = [
                    classify(arc)
                    for leftover in leftovers
                    for arc in _arcs_of_a_prism(body, leftover, check_cancelled)
                    if _exactly_an_arc(body, arc, check_cancelled)
                ]
                # **Fünfte Runde, für eine Wand mit Absatz** (ERKENNUNG-11): Ein
                # ganzer Fleck, den weder Krümmung noch Prisma geteilt haben, kann
                # zwei Formen an einer weichen Naht sein — Wand und Haltelippe
                # einer Magnettasche, Bohrung und flache Senkung. Geteilt wird nur
                # dort (:func:`_pieces_at_a_seam`), und jedes Stück wird gefragt
                # wie jedes andere.
                seams = (
                    [classify(piece) for piece in _pieces_at_a_seam(body, patch, check_cancelled)]
                    if not split_apart and not any(arcs)
                    else []
                )
                # **Sechste Runde, für einen tangentialen Verbund** (RM-226): Rundungen,
                # Kugelecken und Ringe gleichen Radius gehen ineinander über, ohne
                # Knick und ohne Krümmungssprung — ein rundum verrundeter Quader,
                # ein Zapfen mit Kehle. Getrennt wird an den Ecken, die auf einem
                # Zylinder liegen (:func:`_tangential_pieces`); jedes Stück wird
                # gefragt wie jedes andere, und es zählt nur, was danach als
                # eigene Rundform steht (``divided``). Nicht auf einer Haut: Eine
                # Figur ist kein Verbund aus Rundungen.
                # Hat die Nachtrennung nichts erkannt, waren ihre Schnitte für einen
                # solchen Verbund Splitter an den Tangentialnähten: Sie trennten am
                # gerundeten T von jeder Rundung den Randstreifen ab. Dann nimmt die
                # Runde den ganzen Fleck.
                # Was danach eben übrig bleibt, ist eine Fläche zwischen Rundungen,
                # die die Ebenenregel als Mantelstreifen las (``flat``).
                tangential: list[bool] = []
                if not freeform_skin and not any(arcs) and not any(seams):
                    if any(classified):
                        for target in leftovers:
                            tangential.extend(divided(target, []))
                    else:
                        tangential.extend(divided(patch, leftovers))
                if any(classified) or any(arcs) or any(seams) or any(tangential):
                    # Belegte Teilflächen ersetzen die unsichere Gesamtdeutung;
                    # dieselben Dreiecke zählen nicht zusätzlich als verworfener Ring.
                    tori.drop_patch(patch)

        share.reach(0.92)
        if check_cancelled is not None:
            check_cancelled()
        found = _merged_cylinders(body, mesh, found, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        cones = _merged_cones(body, cones, check_cancelled=check_cancelled)
        if check_cancelled is not None:
            check_cancelled()
        rings = _merged_tori(body, tori.entries, check_cancelled=check_cancelled)
        if wandering.any():
            # **Ein Bogen zwischen zwei Ecken eines wandernden Umrisses gehört
            # zu ihm** (RM-254): ein eigener Fleck derselben Seitenwand, den
            # Ecken vom Umriss trennen und der deshalb nie unter dessen Stücken
            # stand — am Screen-Cover das Wandband R 13,73 einer Stufe im
            # Buchstaben. Er bleibt nur, wenn er gezeichnet ist.
            for fit, patch in found:
                if _between_corners_of(body, fit, patch, wandering, check_cancelled):
                    outline[np.asarray(patch, dtype=np.intp)] = True
        if outline.any():
            found = _off_the_outline(found, outline)
            cones = _off_the_outline(cones, outline)
            rings = _off_the_outline(rings, outline)
            spheres = _off_the_outline(spheres, outline)
        if check_cancelled is not None:
            check_cancelled()
        helices = find_helices(mesh, check_cancelled=check_cancelled)
        found = _without_thread_turns(body, found, helices=helices)
        if check_cancelled is not None:
            check_cancelled()
        found, fillets = _split_off_fillets(body, found)
        if check_cancelled is not None:
            check_cancelled()

        # **Die Nummer ist eine Provenienz-ID** (§21.2): Eine Op, die an
        # `hole_2` hängt, muss nach der nächsten Auswertung an derselben
        # Bohrung sitzen. Geordnet wird deshalb nach dem Körper und nie nach
        # der Reihenfolge der Flecken — nach der Mitte auf **allen drei
        # Achsen** (zwei koaxiale Bohrungen einer Durchführung haben dieselbe
        # Mitte in X und Y), und wo Mitten zusammenfallen, nach Maß, Länge,
        # Lage und zuletzt den Ecken (:func:`numbering_order`). Die Mitte
        # allein ließ konzentrische Rundungen unentschieden (RM-211).
        found = _in_numbering_order(body, found, lambda fit: (fit.radius,))
        cones = _in_numbering_order(body, cones, lambda fit: (fit.radius, *fit.apex))
        spheres = _in_numbering_order(body, spheres, lambda fit: (fit.radius,))
        rings = _in_numbering_order(body, rings, lambda fit: (fit.ring_radius, fit.tube_radius))
        fillets = _in_numbering_order(body, fillets, lambda fit: (fit.radius,))
        return Fitted(
            found, cones, spheres, rings, fillets, helices, stadiums, freeform_skin, tuple(flat)
        )


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

    Die Diagonale des kleinsten Rechtecks um die quer projizierte Körperhülle
    ist eine obere Größenschranke. Sie folgt dem Körper und nicht den
    Weltachsen: Eine gedrehte Weltbox wurde größer und ließ am Organizer
    plötzlich vier Rundungen mit Ø277 zu. Wo bereits zwei wirkliche Ecken
    weit genug auseinanderliegen, steht dieselbe Antwort ohne Hüllrechnung
    fest. Das sagt nichts darüber, wo im Teil das Merkmal sitzt.

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
    radius = fit.radius if fit.radial_min is None else fit.radial_min
    return cylinder_fits_in_the_body(mesh, fit.axis, radius)


def cylinder_fits_in_the_body(mesh: MeshData, axis: Sequence[float], radius: float) -> bool:
    """Ob ein Zylinder mit diesem Radius quer zu seiner Achse in den Körper passt.

    Die Frage hinter :func:`_fits_in_the_body`, ohne Einpassung gestellt —
    **der exakte Kern fragt sie mit seinem Topologiemaß an seiner eigenen
    Vernetzung** (``brep.features._oversized_rounds_dropped``, RM-226). Ohne
    sie hieß ein Bogen R 382 über 6 Grad auf einem 40 mm breiten Quader exakt
    „Verrundung R 382“ und am Netzzwilling „gekrümmte Fläche“.

    **Wer die Antwort in eine Frage über die Körpergrenze einrechnet, merkt
    sie sich als Rückfrage** (:func:`_tangential_pieces`, RM-592): Die Hülle
    gehört dem ganzen Körper und steht nicht im Schlüssel; die gemerkte Antwort
    gilt nur, wenn jede Rückfrage am neuen Körper gleich ausfällt.
    """
    answer = _cylinder_fits(mesh, axis, radius)
    asked = _HULL_QUESTIONS.get()
    if asked is not None:
        asked.append((tuple(float(value) for value in axis), float(radius), answer))
    return answer


#: Die Rückfragen an die Hülle, die eine Rechnung über die Körpergrenze stellt
#: (:func:`cylinder_fits_in_the_body`) — nur während dieser Rechnung gesetzt.
_HULL_QUESTIONS: ContextVar[list[tuple[tuple[float, ...], float, bool]] | None] = ContextVar(
    "solidon_hull_questions", default=None
)


def _cylinder_fits(mesh: MeshData, axis: Sequence[float], radius: float) -> bool:
    """Die Rechnung von :func:`cylinder_fits_in_the_body`.

    Das Rechteck über alle Ecken merkt sich der Körper je Achse — sonst
    kostete die Rückfrage einer gemerkten Antwort so viel wie die Frage.
    """
    direction = np.asarray(axis, dtype=float)
    if float(np.max(np.abs(direction))) <= EPS_GEOM:
        return True
    first, second = _plane_basis(direction)
    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    extreme: np.ndarray = remembered(
        "body_extreme_points",
        mesh.raw,
        [],
        lambda: vertices[np.r_[vertices.argmin(axis=0), vertices.argmax(axis=0)]].copy(),
    )
    relative = extreme - extreme[0]
    flat = np.column_stack((relative @ first, relative @ second))
    distance = np.linalg.norm(flat[:, None, :] - flat[None, :, :], axis=2)
    if radius * 2.0 <= float(distance.max()) + EPS_GEOM:
        return True
    # **Ein sicheres Nein ohne Rechteck.** Jede Seite des kleinsten Rechtecks ist
    # die Ausdehnung der Projektion in einer Richtung, also höchstens ihr
    # Durchmesser, und der höchstens die Diagonale des achsparallelen Rahmens
    # in ``first``/``second``: Die Rechteckdiagonale bleibt unter √2 mal dieser
    # Diagonale. Die Schranke mit 1,5 hält Abstand zu jeder Rundung, das Nein
    # ist also dasselbe wie mit Rechteck (``kern.md``, sicheres Nein mit Abstand)
    # — am Eiffelturm verneint sie alle fünf Rechteckfragen einer Erkennung,
    # jede 0,18 s über 157 000 Ecken (RM-592).
    span: tuple[float, float] = remembered(
        "projected_span",
        mesh.raw,
        [],
        lambda: _projected_span(vertices, extreme[0], first, second),
        extra=direction.tobytes(),
    )
    if radius * 2.0 > _ACROSS_BOUND * math.hypot(*span) + EPS_GEOM:
        return False

    across: float = remembered(
        "rectangle_across",
        mesh.raw,
        [],
        lambda: _rectangle_across(vertices, extreme[0], first, second, float(distance.max())),
        extra=direction.tobytes(),
    )
    return radius * 2.0 <= across + EPS_GEOM


#: Wie weit die Rechteckdiagonale von :func:`_cylinder_fits` höchstens über der
#: Diagonale des achsparallelen Rahmens der Projektion liegt — √2 mit Abstand.
_ACROSS_BOUND: Final = 1.5


def _projected_span(
    vertices: np.ndarray, anchor: np.ndarray, first: np.ndarray, second: np.ndarray
) -> tuple[float, float]:
    """Breite und Höhe der quer projizierten Ecken entlang ``first`` und ``second``."""
    relative = vertices - anchor
    along_first = (relative * first).sum(axis=1)
    along_second = (relative * second).sum(axis=1)
    return (
        float(along_first.max() - along_first.min()),
        float(along_second.max() - along_second.min()),
    )


def _rectangle_across(
    vertices: np.ndarray, anchor: np.ndarray, first: np.ndarray, second: np.ndarray, reach: float
) -> float:
    """Die Diagonale des kleinsten Rechtecks um die quer projizierte Hülle (:func:`_cylinder_fits`).

    Gerechnet wie dort, damit die gemerkte Antwort je Achse dieselbe ist.
    """
    from shapely import multipoints

    relative = vertices - anchor
    flat = np.column_stack((relative @ first, relative @ second))
    # **GEOS setzt an entarteten Punktmengen Gleitkomma-Merker** — doppelte
    # oder auf einer Linie liegende Ecken, wie sie jeder Quader liefert. numpy
    # meldet sie nach dem Aufruf als RuntimeWarning, auf macOS arm64 bei 64
    # Tests des Tag-Laufs 0.5.2, unter Windows und Linux nie; das Rechteck
    # selbst ist auf allen dreien dasselbe. Ein nicht endliches Maß zählt wie
    # die größte Ausdehnung der Projektion, die die erste Prüfung schon kennt.
    with np.errstate(divide="ignore", invalid="ignore"):
        rectangle = multipoints(flat).minimum_rotated_rectangle
    if rectangle.geom_type == "Polygon":
        corners = np.asarray(rectangle.exterior.coords, dtype=float)
        across = float(np.linalg.norm(corners[2] - corners[0]))
    else:
        across = float(rectangle.length)
    if not np.isfinite(across):
        across = reach
    return across


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
        if (
            _face_count(body, candidate) < MIN_PATCH_FACES
            or len(_connected_patches(body, candidate)) != 1
        ):
            continue
        beside = neighbour_table[rest]
        beside = beside[beside >= 0]
        if not np.isin(rest, ring_patch).any() and not np.isin(beside, ring_patch).any():
            continue
        rest = rest.tolist()
        cylinder = fit_cylinder(body, candidate, check_cancelled=check_cancelled)
        if cylinder is None or not cylinder.good or not _fits_in_the_body(mesh, cylinder):
            continue
        joined = in_body_order(body, [sorted({*ring_patch, *rest})])[0]
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
    axis_cosine = units.exact_cos_degrees(SINK_AXIS_LIMIT)

    def alike(fit: CylinderFit, among: np.ndarray) -> np.ndarray:
        """Welche der Gemerkten ``among`` Seite, Radius und Achslinie mit ``fit`` teilen."""
        axis = np.asarray(fit.axis, dtype=float)
        centre = np.asarray(fit.centre, dtype=float)
        scale = np.maximum(radii[among], fit.radius)
        offset = centre - centres[among]
        across = offset - axes[among] * (offset * axes[among]).sum(axis=1)[:, None]
        chosen: np.ndarray = among[
            (inward[among] == fit.inward)
            & (np.abs(radii[among] - fit.radius) <= scale * CYLINDER_TOLERANCE)
            & (np.abs(axes[among] @ axis) >= axis_cosine)
            & (np.linalg.norm(across, axis=1) <= scale * SINK_FIT_LIMIT)
        ]
        return chosen

    def remember(index: int, fit: CylinderFit) -> None:
        # Die Spalten beschreiben, was gemerkt ist: Nach dem
        # Zusammenfassen steht dort der gemeinsame Fit. Gemessen ist
        # das nie entscheidend gewesen — unter den Toleranzen von
        # `_same_cylinder` wandert ein Fit über derselben Wand kaum,
        # und eine Probe ohne diese vier Zeilen fiel an keinem der
        # 23 Korpusmodelle und keinem Test auf. Eine Spalte, die
        # einen verworfenen Fit beschreibt, wäre trotzdem eine
        # zweite Wahrheit.
        axes[index] = np.asarray(fit.axis, dtype=float)
        centres[index] = np.asarray(fit.centre, dtype=float)
        radii[index] = fit.radius
        inward[index] = fit.inward

    for fit, patch in found:
        if check_cancelled is not None:
            check_cancelled()
        for index in alike(fit, np.arange(len(merged))).tolist():
            joined = _joined_cylinders(
                body, mesh, (fit, patch), merged[index], check_cancelled=check_cancelled
            )
            if joined is not None:
                merged[index] = joined
                remember(index, joined[0])
                break
        else:
            remember(len(merged), fit)
            merged.append((fit, patch))

    # **Dann die Gruppen untereinander, bis keine zwei mehr zusammengehören**
    # (RM-210). Die erste Runde fragt jeden Fleck nur gegen die Gruppen, die
    # vor ihm kamen; welche Flecken zusammenfanden, hing damit an ihrer
    # Reihenfolge. Am Keilschloss (``Wedge-Lock (Top).stl``) liegen drei
    # Stücke einer Verrundung: In der gelesenen Lage kam zuerst das Paar, das
    # allein keinen Zylinder ergibt, und am Ende standen zwei Verrundungen;
    # um 90 Grad gedreht fanden alle drei zu einer mit 112,9 Grad zusammen.
    # Die zweite Runde gibt beiden Lagen dieselbe Antwort, und den Fit jeder
    # Vereinigung kennt der Merker schon, wenn sie einmal gefragt war.
    return _joined_until_stable(
        merged,
        lambda index, later: alike(merged[index][0], later),
        lambda new, known: _joined_cylinders(
            body, mesh, new, known, check_cancelled=check_cancelled
        ),
        remember,
        check_cancelled,
    )


def _joined_cylinders(
    body: trimesh.Trimesh,
    mesh: MeshData,
    new: tuple[CylinderFit, list[int]],
    known: tuple[CylinderFit, list[int]],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[CylinderFit, list[int]] | None:
    """Der gemeinsame Zylinder zweier Flecken, wenn sie dieselbe Fläche sind — sonst nichts."""
    fit, patch = new
    other, gathered = known
    if not _same_cylinder(body, new, known):
        return None
    # In der Ordnung des Körpers (:func:`in_body_order`), nicht in der
    # zufälligen Folge, in der die zwei Flecken zusammenkamen.
    together = in_body_order(body, [gathered + patch])[0]
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
    #
    # **In beide Richtungen** (RM-210): Welcher der zwei Flecken zuerst da war,
    # ist eine Frage der Reihenfolge und keine der Geometrie. Am Unterteil
    # ``bottom-double.stl`` trägt ein Bogen aus 26 Dreiecken (19,6 Grad) nur
    # r = 5,0143, der anschließende aus 79 Dreiecken r = 5,0004. Der große
    # liegt nicht auf dem Zylinder des kleinen, der kleine aber auf dem des
    # großen; gefragt war nur die erste Richtung, und aus einer Verrundung
    # wurden zwei.
    if (
        again is not None
        and again.good
        and _fits_in_the_body(mesh, again)
        and (
            again.spread <= max(fit.spread, other.spread) + EPS_GEOM
            or _lies_on_the_cylinder(body, other, patch, check_cancelled=check_cancelled)
            or _lies_on_the_cylinder(body, fit, gathered, check_cancelled=check_cancelled)
        )
    ):
        return again, together
    return None


def _joined_until_stable[Fit](
    merged: list[tuple[Fit, list[int]]],
    near: Callable[[int, np.ndarray], np.ndarray],
    join: Callable[[tuple[Fit, list[int]], tuple[Fit, list[int]]], tuple[Fit, list[int]] | None],
    remember: Callable[[int, Fit], None],
    check_cancelled: Callable[[], None] | None,
) -> list[tuple[Fit, list[int]]]:
    """Die zweite Runde jeder Zusammenlegung: die Gruppen untereinander, bis
    keine zwei mehr zusammengehören (RM-210).

    Die erste Runde fragt jeden Fleck nur gegen die Gruppen, die vor ihm
    kamen, und welche Flecken zusammenfinden, hing damit an ihrer
    Reihenfolge — und die folgt seit :func:`in_body_order` den Koordinaten,
    also der Lage des Körpers. Hier fragt jede Gruppe jede spätere, bis sich
    nichts mehr ändert. Den Fit einer Vereinigung, die schon einmal gefragt
    war, kennt der Merker.

    ``near`` liefert von den Nummern ``later`` die, die für ``index``
    überhaupt in Frage kommen (die notwendige Bedingung der Paarprüfung, für
    alle auf einmal); ``join`` stellt die ganze Frage und gibt die
    Vereinigung oder nichts; ``remember`` trägt einen neuen Fit in die
    Spalten ein, aus denen ``near`` liest.
    """
    alive = np.ones(len(merged), dtype=bool)
    changed = True
    while changed:
        changed = False
        for index in range(len(merged)):
            if not alive[index]:
                continue
            later = np.arange(index + 1, len(merged))
            for other in near(index, later[alive[later]]).tolist():
                if check_cancelled is not None:
                    check_cancelled()
                joined = join(merged[other], merged[index])
                if joined is None:
                    continue
                merged[index] = joined
                remember(index, joined[0])
                alive[other] = False
                changed = True
                break
    return [entry for entry, kept in zip(merged, alive, strict=True) if kept]


def _anchored_near(
    anchors: np.ndarray, scales: np.ndarray
) -> Callable[[int, np.ndarray], np.ndarray]:
    """Die notwendige Bedingung von :func:`_same_cone` und :func:`_same_torus`
    für viele auf einmal: Anker höchstens :data:`SINK_FIT_LIMIT` des größeren
    Maßes voneinander entfernt."""

    def near(index: int, later: np.ndarray) -> np.ndarray:
        """Die Nummern aus ``later``, deren Anker nah genug bei dem von ``index`` liegt."""
        reach = np.maximum(scales[later], scales[index]) * SINK_FIT_LIMIT
        chosen: np.ndarray = later[np.linalg.norm(anchors[later] - anchors[index], axis=1) <= reach]
        return chosen

    return near


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


def _shell_of_each_face(body: trimesh.Trimesh) -> np.ndarray:
    """Zu jedem Dreieck die Nummer seines Teils (:func:`face_components`, je Netz gemerkt)."""
    shell = np.empty(len(body.faces), dtype=np.intp)
    for number, component in enumerate(face_components(body)):
        shell[component] = number
    return shell


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

    **Und ein Gewinde ist eine Fläche an einem Teil, deren Gänge in eine
    Richtung zeigen und ineinanderlaufen** (RM-219, 25.09.2026): Gänge, Kern
    und Auslauf liegen auf demselben Teil (:func:`face_components`), die
    Gänge tragen dieselbe Materialseite, und jeder läuft in den nächsten
    (:func:`_one_run`). Über 208 Dateien des Korpus und alle gedruckten
    Gewinde hat die Regel ohne Wendelbeleg vorher kein belegtes Gewinde
    gefunden, aber in 13 Dateien echte Zylinder verworfen: am Flaschenhalter
    die Flaschentaschen R 49 über die volle Höhe, weil ihre Wandstücke um
    Hundertstel versetzt beginnen; am Besenhalter 30 von 45 Zylindern,
    darunter zwölf Bohrungen Ø 6,12 und Ø 5,44, weil ein abgesetzter Zapfen
    R 4,76 · R 5,10 · R 4,76 und Bögen zweier Teile als Lauf galten; am
    Screen-Cover die Bögen der Buchstaben. Ein zusammengelegter Fit über
    mehrere Teile ist kein Gang.
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
    shells = _shell_of_each_face(body)
    parts = np.full(len(found), -1, dtype=np.intp)
    for index, (_fit, patch) in enumerate(found):
        on = np.unique(shells[np.asarray(patch, dtype=np.intp)])
        if len(on) == 1:
            parts[index] = on[0]
    parallel_limit = units.exact_cos_degrees(SINK_AXIS_LIMIT)
    used: set[int] = set()
    for index, (fit, _patch) in enumerate(found):
        if index in used or parts[index] < 0:
            continue
        axis = axes[index]
        offset = centres - centres[index]
        across = offset - (offset @ axis)[:, None] * axis
        # Dieselben Paarbedingungen in einem begrenzten Feld je Ausgangsfit.
        # Kein quadratisches Feld und keine wiederholten Arrays je Taschenbogenpaar.
        coaxial = np.flatnonzero(
            (np.abs(axes @ axis) >= parallel_limit)
            & (np.linalg.norm(across, axis=1) <= fit.radius * SINK_FIT_LIMIT)
            & (parts == parts[index])
        ).tolist()
        stack = [
            index,
            *(
                other_index
                for other_index in coaxial
                if other_index != index
                and other_index not in used
                and found[other_index][0].inward is fit.inward
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
    Lücke dazwischen. Berührung hält den Lauf zusammen — ``EPS_GEOM`` ist die
    Toleranz, mit der :func:`_same_cylinder` dieselbe Frage für ein Paar
    beantwortet —, aber ein weiterer Gang ist nur ein Abschnitt, der die bisher
    erreichte Spanne um mehr als die Schweißtoleranz überlappt und sie um mehr
    verlängert, als er mit ihr teilt. Damit werden weder verschachtelte
    Fragmente derselben Wand noch aufeinandergesetzte Absätze zu Gewindegängen.
    """
    ordered = sorted(spans, key=lambda span: (span[0], -span[1]))
    reach = ordered[0][1]
    advancing = 1
    for low, high in ordered[1:]:
        if low > reach + EPS_GEOM:
            return False
        # **Ein Gang läuft in den nächsten und bringt mehr Neues, als er teilt**
        # (RM-219, 25.09.2026). Die Stücke einer Wand beginnen und enden um
        # Hundertstel versetzt, und jede Verschiebung über der Schweißtoleranz
        # galt als Gang: am Flaschenhalter die Flaschentaschen über 160 mm,
        # 0,01 mm neu, an den Buchstaben des Screen-Covers Bögen über dieselbe
        # Höhe. Und Absätze, die sich nur berühren, laufen nicht ineinander —
        # die Windungen eines Gewindes tun es, weil die Helix stetig steigt.
        shared = reach - low
        new = high - reach
        if shared > advance_tolerance and new > shared:
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
    if abs(float(axis @ np.asarray(second.axis, dtype=float))) < units.exact_cos_degrees(
        SINK_AXIS_LIMIT
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


def _shows_enough_arc(body: trimesh.Trimesh, fit: Any, patch: list[int]) -> bool:
    """Ob eine Rundform mindestens :data:`MIN_ROUND_ARC` ihres Kreises zeigt (RM-210).

    Verrundung und Kegelstück: der Bogen um ihre Achse (:func:`angular_span`).
    Torusstück: der Bogen um die Mittellinie seiner Röhre — das ist das
    Profil einer Verrundung an einer runden Kante; um die Ringachse darf es
    kurz sein wie jede Verrundung an einem kurzen Kantenstück.
    """
    if isinstance(fit, TorusFit):
        return _tube_span(body, fit, patch) >= MIN_ROUND_ARC
    return angular_span(body, fit, patch) >= MIN_ROUND_ARC


def _tube_span(body: trimesh.Trimesh, fit: TorusFit, patch: Sequence[int]) -> float:
    """Wie viel Grad um die Mittellinie seiner Röhre ein Torusstück überdeckt."""
    axis = np.asarray(fit.axis, dtype=float)
    chosen = np.asarray(body.faces)[np.asarray(list(patch), dtype=np.int64)]
    points = np.asarray(body.vertices, dtype=float)[np.unique(chosen)] - np.asarray(
        fit.centre, dtype=float
    )
    along = points @ axis
    radial = np.linalg.norm(points - along[:, None] * axis, axis=1)
    angles = np.sort(np.arctan2(along, radial - float(fit.ring_radius)))
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
    area, reach = _area_and_reach(body, patch, minimum_width=MIN_SURFACE_WIDTH)
    if reach <= EPS_GEOM:
        return True
    return area / reach < MIN_SURFACE_WIDTH


def _area_and_reach(
    body: trimesh.Trimesh, patch: Sequence[int], *, minimum_width: float | None = None
) -> tuple[float, float]:
    """Fläche und größter Abstand wirklicher Fleckecken; ihr Quotient ist seine Breite.

    Die Messung hinter :func:`_a_sliver` — und hinter der Zählregel in
    :func:`_flat_counts`, die aus derselben Breite den Radius liest, auf dem
    ein schmaler Streifen läge. Eine Weltboxdiagonale ist kein Abstand im
    Fleck: Sie wächst beim Drehen und ließ kleine ebene Seiten verschwinden.
    Mit ``minimum_width`` genügen beweisende obere oder untere Schranken;
    ohne Grenze wird der größte Abstand vollständig gemessen.
    """
    faces = np.asarray(patch, dtype=int)
    area = float(body.area_faces[faces].sum())
    # **Über ``np.asarray`` und nicht am Netz selbst indizieren.** Jede Auswahl
    # aus ``body.faces`` oder ``body.vertices`` (trimesh ``TrackedArray``)
    # erklärt deren Prüfsumme für ungültig, und der nächste gemerkte Wert des
    # Netzes rechnet sie neu: an 4,5 Millionen Dreiecken 34 ms für die Flächen,
    # 17 ms für die Ecken — je Fleck. Die Vorschau von *Kanten verfeinern* auf
    # 0,04 mm am Spielwürfel stand damit über zehn Minuten in dieser Zeile
    # (Durchsicht 0.5.1, Stapelabzug unter Last).
    corners = np.asarray(body.vertices)[np.unique(np.asarray(body.faces)[faces])]
    upper = float(np.linalg.norm(corners.max(axis=0) - corners.min(axis=0)))
    if minimum_width is not None and area >= minimum_width * upper:
        return area, upper
    stop_after = None if minimum_width is None else area / minimum_width
    return area, _point_diameter(corners, stop_after=stop_after)


def _point_diameter(points: np.ndarray, *, stop_after: float | None = None) -> float:
    """Größter Eckabstand; der Suchbaum verwirft nur nachweislich kürzere Paare.

    Die Boxen sind ausschließlich obere Schranken, nie das Messergebnis.
    Je Blattpaar werden die tatsächlichen Punkte verglichen. So braucht
    auch eine fein unterteilte schmale Seite kein quadratisch großes Feld.
    ``stop_after`` erlaubt dem Breitenentscheid einen frühen Beweis.
    """
    extremes = points[np.r_[points.argmin(axis=0), points.argmax(axis=0)]]
    best = float(np.linalg.norm(extremes[:, None, :] - extremes[None, :, :], axis=2).max())
    if stop_after is not None and best > stop_after:
        return best
    tree = cKDTree(points)
    bounds: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    def bound(first: Any, second: Any) -> float:
        """Obere Abstandsschranke zwischen zwei Teilmengen des Suchbaums."""
        for node in (first, second):
            if id(node) not in bounds:
                selected = points[node.indices]
                bounds[id(node)] = selected.min(axis=0), selected.max(axis=0)
        low, high = bounds[id(first)]
        other_low, other_high = bounds[id(second)]
        span = np.maximum(np.abs(high - other_low), np.abs(other_high - low))
        return float(np.linalg.norm(span))

    serial = itertools.count()
    pending: list[tuple[float, int, Any, Any]] = [
        (-bound(tree.tree, tree.tree), next(serial), tree.tree, tree.tree)
    ]
    while pending:
        negative, _order, first, second = heapq.heappop(pending)
        if -negative <= best:
            break
        if first.split_dim < 0 and second.split_dim < 0:
            delta = points[first.indices][:, None, :] - points[second.indices][None, :, :]
            best = max(best, float(np.linalg.norm(delta, axis=2).max()))
            if stop_after is not None and best > stop_after:
                return best
            continue
        if first.split_dim < 0 or (second.split_dim >= 0 and second.children > first.children):
            first, second = second, first
        for child in (first.lesser, first.greater):
            upper = bound(child, second)
            if upper > best:
                heapq.heappush(pending, (-upper, next(serial), child, second))
    return best


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
    support = _support_handle(body, patch, check_cancelled)
    if support is None:
        return False
    result: bool = _by_geometry(
        "_sphere_is_recognisable",
        body,
        support,
        lambda: _sphere_is_recognisable_measured(body, fit, patch, support.read(), check_cancelled),
        fit,
    )
    return result


def _sphere_is_recognisable_measured(
    body: trimesh.Trimesh,
    fit: SphereFit,
    patch: list[int],
    support: _SurfaceSupport,
    check_cancelled: Callable[[], None] | None,
) -> bool:
    """Der Kugelnachweis selbst; was er vom Körper liest, trägt die Lesung."""
    if not np.any(support.round_corners):
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
        and _shows_enough_arc(mesh.raw, entry[0], entry[1])
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
        if not _too_small_to_make(entry[0].radius * 2.0)
        and not _a_sliver(mesh.raw, entry[1])
        and _shows_enough_arc(mesh.raw, entry[0], entry[1])
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
    # (:func:`tangent_walls`). Gemessen am 15.09.2026 an sieben
    # Modellen aus dem Netz: 32 Absagen „lässt sich innerhalb ihrer Ränder
    # nicht versetzen" erst nach dem Klick; mit dem Kennzeichen stellt das
    # Panel die Zeile vorher grau.
    radials = [
        radial_cylinder(body, patch, check_cancelled=check_cancelled) for _fitted, patch in big
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


def tangent_walls(
    body: trimesh.Trimesh, walls: Sequence[tuple[Sequence[int], CylinderFit | None]]
) -> list[bool]:
    """Je runder Wand, ob sie tangential in eine Nachbarfläche übergeht — in
    **einem** Gang über die Nachbarschaft des Körpers.

    Eine radiale Verschiebung der Wand bewegt ihre Randecken radial. Eine
    Nachbarfläche bleibt dabei in ihrer Ebene, wenn ihre Normale quer zur
    radialen Richtung steht — Deckel und Boden (Normale entlang der Achse)
    ebenso wie eine radial stehende Lückenwand. Eine Flanke, die tangential
    an die Wand anschließt, hat ihre Normale **in** radialer Richtung und
    würde aus ihrer Ebene geschoben; ``radial_rounding`` sagt dort ab.
    Dieselbe Schwelle wie für die Ebenen neben einer Kante
    (:data:`UPRIGHT_TO_AXIS`).

    Ein Feld nennt zu jedem Dreieck seine Wand; jede Nachbarschaftskante, deren
    Seiten verschiedenen Wänden gehören (oder eine keiner), liefert ein
    Randdreieck mit der Wand, an die es grenzt. Dann wird je Wand die obige
    Frage gerechnet. Eine Wand ohne Einpassung (``None``) ist nie tangential.
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
    :func:`_finished_faces` danach je Fläche rechnet, liest die Maske nicht. Am
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

    **Gemerkt je Körper und gerundeter Seite** (:func:`remembered`, Schlüssel
    Kennung und Flächenabdruck je Seite): Merkmalfenster und Operation fragen
    je Rundung, und am Countercleaner mit 701 900 Dreiecken las jede Frage
    die vier großen gerundeten Seiten neu — 0,1 s je Klick, 4,8 von 5,9
    Sekunden über alle 62 Handlungslisten (RM-181, gemessen am 22.09.2026).
    Die Antwort ist schreibgeschützt; wer sie verknüpft, bekommt ein neues Feld.
    """
    curved = [
        feature
        for feature in features.values()
        if feature.kind == "curved_face" and feature.face_indices
    ]
    if not curved:
        return np.zeros(len(body.faces), dtype=bool)
    with _MEMORY_LOCK:
        memory = _memory_of(body)
    key = tuple(
        (str(feature.id), _patch_digest(memory, feature.face_indices)) for feature in curved
    )

    def read() -> np.ndarray:
        mask = np.zeros(len(body.faces), dtype=bool)
        normals = np.asarray(body.face_normals, dtype=float)
        areas = np.asarray(body.area_faces, dtype=float)
        limit = units.exact_cos_degrees(NEARLY_FLAT_ANGLE)
        for feature in curved:
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
        mask.setflags(write=False)
        return mask

    answer: np.ndarray = remembered("nearly_flat", body, (), read, extra=key)
    return answer


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
        and _shows_enough_arc(mesh.raw, entry[0], entry[1])
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


def partial_cone_patch(
    mesh: MeshData,
    patch: Sequence[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> SurfacePatch | None:
    """Der Kegelträger, den das Netz einem Fleck als Kegelstück gäbe — sonst ``None``.

    Dieselben Fragen wie :func:`detect_cones` (Einpassung, Werkzeugschranke,
    Breite, gezeigter Bogen, belegte Normalen) und wie
    :func:`_partial_cones_folded` (unter dem vollen Umlauf) — für einen Fleck,
    den nicht die Zerlegung des Netzes gebildet hat. Der exakte Kern fragt
    hier an einer Freiformfläche am Mantel eines Langlochs
    (``brep.features._mouth_chamfers_folded``): OpenCASCADE fast einen Bogen
    auf einer schrägen Fläche nicht als Kegel, sondern als BSpline-Fläche,
    und das Netz liest dieselbe Fläche als Kegelstück. Ob sie eines ist,
    entscheidet an beiden Kernen dieselbe Einpassung.
    """
    body = mesh.raw
    faces = sorted({int(index) for index in patch})
    if _face_count(body, faces) < MIN_PATCH_FACES:
        return None
    fit = fit_cone(body, faces, check_cancelled=check_cancelled)
    if fit is None:
        return None
    if (
        _too_small_to_make(fit.radius * 2.0)
        or _a_sliver(body, faces)
        or not _shows_enough_arc(body, fit, faces)
        or not _cone_is_recognisable(body, fit, faces, check_cancelled=check_cancelled)
    ):
        return None
    axis = np.asarray(fit.axis, dtype=float)
    if span_about(body, axis, np.asarray(fit.centre, dtype=float), faces) >= FULL_TURN_SPAN:
        return None
    return SurfacePatch(
        "cone",
        {"apex": fit.apex, "axis": fit.axis, "half_angle": math.radians(fit.half_angle)},
        tuple(faces),
        "fit",
    )


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
    # Die Nachbarn aus dem Index je Dreieck und die Facetten als Tabelle —
    # beides einmal je Körper. Hier stand ein Wörterbuch über alle Nähte des
    # Netzes, in Python gebaut, und je Langloch eine Schleife über **alle**
    # Facetten des Körpers mit einer Mengenfrage je Dreieck.
    table, _rows = _neighbour_index(body)
    facets = list(body.facets)
    members, owner, sizes, _curved = _facet_table(facets, len(body.faces), set())
    facet_of = np.full(len(body.faces), -1, dtype=np.int64)
    facet_of[members] = owner
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
        band = np.zeros(len(body.faces), dtype=bool)
        start = np.fromiter(pieces, dtype=np.int64, count=len(pieces))
        band[start] = True
        frontier = start
        while len(frontier):
            if check_cancelled is not None:
                check_cancelled()
            following = table[frontier].ravel()
            following = np.unique(following[following >= 0])
            following = following[~band[following] & ~taken[following] & tilted[following]]
            band[following] = True
            frontier = following
        band[start] = False
        if not band.any():
            continue
        added = set(np.flatnonzero(band).tolist())
        # Nur Facetten, die ganz im Band liegen.
        inside = np.bincount(facet_of[band & (facet_of >= 0)], minlength=len(facets))
        for number in np.flatnonzero((inside == sizes) & (sizes > 0)).tolist():
            indices = [int(index) for index in facets[number]]
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


def rounds_the_corner(sphere_radius: float, cylinder_radius: float) -> bool:
    """Ob ein Zylinderstück mit diesem Radius an einer Kugelecke liegt (RM-226).

    Eine Kugelecke entsteht, wo verrundete Kanten **desselben** Radius
    zusammenlaufen: Sie ist das Stück der rollenden Kugel, das die Kanten
    verbindet, und trägt deren Radius — mit verschiedenen Radien wird die Ecke
    keine Kugel. Eine Kuppel, an die Rundungen stoßen, ist deshalb keine Ecke.
    Gezählt hatten beide Kerne nur die Nachbarn, und am Minigolfteil Gövde75
    hieß eine Kuppel Ø 178,6 zwischen Rundungen R 3 und R 7 „Verrundung
    R 89,3“. Verglichen wird bis :data:`ROUND_WALL_TOLERANCE`, der Formtoleranz
    einer runden Wand; beide Kerne fragen hier (``brep.features``,
    :func:`_corners_named_as_fillets`).
    """
    return abs(sphere_radius - cylinder_radius) <= ROUND_WALL_TOLERANCE


def _corners_named_as_fillets(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Eine Kugelecke, an der verrundete Kanten zusammenlaufen, heißt Verrundung (RM-226).

    Dieselbe Regel wie am exakten Kern (``brep.features._describe``): Grenzen
    an eine Kugel mindestens :data:`CORNER_NEIGHBOURS` Zylinderstücke unter
    einer vollen Umdrehung mit ihrem Radius (:func:`rounds_the_corner`), ist
    sie die Ecke eines verrundeten Körpers — der Kunde sieht eine verrundete
    Ecke und will ihren Radius, keine „Kuppel Ø 6“. Ein Zylinderstück ist hier
    jeder Zylinderträger einer Kantenrundung, eines Langlochs oder einer
    angeschnittenen Bohrung; jeder zählt einmal, wie am exakten Kern jede
    Fläche. Die Ecke behält Dreiecke, Mitte und Träger der Kugel und bekommt
    wie dort keine Achse und die Länge null; ihre Nummer folgt auf die letzte
    Verrundung, in der Folge der Kugeln. Was nicht an gleich verrundete
    Kanten grenzt — eine Pfanne, eine Kuppel —, bleibt Kugel.

    Erst nach dem Langloch und den angeschnittenen Bohrungen: Beide tragen
    dann ihr endgültiges Wort.
    """
    if check_cancelled is not None:
        check_cancelled()
    spheres = sorted(
        (key for key, feature in found.items() if feature.kind == "sphere"), key=_serial
    )
    if not spheres:
        return dict(found)
    count = len(mesh.raw.faces)
    carrier = np.full(count, -1, dtype=np.int64)
    radii: list[float] = []
    for feature in found.values():
        rounded = (
            feature.kind == "slot"
            or (feature.kind == "fillet" and "axis" in feature.params)
            or (feature.kind in ("hole", "pin") and bool(feature.params.get("partial")))
        )
        if not rounded:
            continue
        for patch in feature.surface_patches:
            if patch.kind == "cylinder" and patch.face_indices:
                carrier[np.asarray(patch.face_indices, dtype=np.intp)] = len(radii)
                # Ein Vektor an dieser Stelle ist kein Radius; NaN gleicht keinem.
                value = patch.params["radius"]
                radii.append(float(value) if isinstance(value, int | float) else math.nan)
    carriers = len(radii)
    if carriers < CORNER_NEIGHBOURS:
        return dict(found)
    ball = np.full(count, -1, dtype=np.int64)
    for number, key in enumerate(spheres):
        ball[np.asarray(found[key].face_indices, dtype=np.intp)] = number
    pairs = np.asarray(mesh.raw.face_adjacency, dtype=np.intp).reshape(-1, 2)
    touching = np.concatenate(
        (
            np.column_stack((ball[pairs[:, 0]], carrier[pairs[:, 1]])),
            np.column_stack((ball[pairs[:, 1]], carrier[pairs[:, 0]])),
        )
    )
    touching = touching[(touching[:, 0] >= 0) & (touching[:, 1] >= 0)]
    codes = np.unique(touching[:, 0] * carriers + touching[:, 1])
    neighbours = [0] * len(spheres)
    for code in codes.tolist():
        number, other = divmod(int(code), carriers)
        if rounds_the_corner(float(found[spheres[number]].params["diameter"]) / 2.0, radii[other]):
            neighbours[number] += 1
    corners = [key for number, key in enumerate(spheres) if neighbours[number] >= CORNER_NEIGHBOURS]
    if not corners:
        return dict(found)
    following = max(
        (_serial(key) for key, feature in found.items() if feature.kind == "fillet"), default=0
    )
    kept = {key: feature for key, feature in found.items() if key not in corners}
    for offset, key in enumerate(corners, start=1):
        sphere = found[key]
        diameter = float(sphere.params["diameter"])
        name = f"fillet_{following + offset}"
        kept[name] = replace(
            sphere,
            id=name,
            kind="fillet",
            params={**sphere.params, "radius": diameter / 2.0, "length": 0.0},
            measure_sources={**sphere.measure_sources, "radius": "fit", "length": "fit"},
        )
    return kept


def _serial(key: FeatureId) -> int:
    """Die laufende Nummer einer Kennung wie ``fillet_12`` — null, wo keine steht."""
    tail = key.rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def narrowings_marked(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    *,
    source: MeasureSource = "facets",
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Ein hohler Kegel, dessen weites Ende an seiner Bohrung liegt, verengt die Öffnung (R3).

    **Die Haltelippe einer Magnettasche hieß „Senkung".** Eine Senkung weitet
    die Öffnung zur Mündung hin, damit ein Schraubenkopf versinkt; die Lippe
    tut das Gegenteil — sie ist zur Mündung hin enger als die Tasche darunter
    (Ø 8,25 → 7,9), damit der Magnet nicht herausfällt. Wer ohne CAD-Kenntnis
    „Senkung" liest, erwartet einen Trichter (Durchsicht 0.5.1, R3).

    **Unterscheidbar ist es am Kegel selbst.** Seine Achse zeigt von der Spitze
    zum weiten Ende, und dort liegt ``centre``, an beiden Kernen gleich. Jede
    Naht nach draußen gehört zu dem Ende, dem sie näher liegt. Sitzt das
    **weite** Ende mehrheitlich auf einer Bohrung und das enge auf keiner,
    öffnet sich der Kegel zur Bohrung hin; ist sein enges Ende dazu offen
    (:func:`_open_at_the_narrow_end`) und eine Öffnung, keine Spitze, verengt
    er die Mündung und trägt ``narrowing``. Eine Senkung sitzt
    mit ihrem engen Ende auf der Bohrung; ein Kegel zwischen zwei Bohrungen
    (eine Stufe mit schrägem Absatz), ein Kegel ohne Bohrung und einer, dessen
    weites Ende nur zum Teil an einer Bohrung liegt, bleiben, wie sie waren —
    dort sagt die Lage allein nicht, wo die Mündung ist (Regel 21). Gemessen am
    Korpus (553 Körper): Ohne die Mehrheit wurde ein eingepasster Kegel am
    Deckel eines Töpfchens Verengung, ohne das offene Ende eine Fase am Grund
    einer Düsenbox, ohne die Frage nach der Spitze zwei flache Kegelböden
    einer Murmelbahn. Eine Verengung trägt dazu ihre
    Öffnung (``opening``): die Weite an ihrem engen Ende, gemessen an den
    Ecken ihrer Dreiecke. ``source`` ist die Herkunft dieses Maßes — am Netz
    ``facets``; am exakten Körper liegen die Ecken der Tessellierung auf dem
    Randkreis der Topologie, dort gibt der Aufrufer ``native`` an.

    Gemessen wird an den Dreiecken, die beide Merkmale tragen: an welcher Höhe
    entlang der Kegelachse ihre gemeinsamen Nähte liegen, gegen die Höhen des
    Kegels selbst. Am exakten Körper sind das die Dreiecke seiner Tessellierung
    (``brep.features.features_of``) — dieselbe Regel für beide Kerne.
    Gerechnet mit Grundrechenarten (RM-187).
    """
    if check_cancelled is not None:
        check_cancelled()
    cones = [
        (identifier, feature)
        for identifier, feature in found.items()
        if feature.kind == "cone"
        and feature.params.get("recess")
        and not feature.params.get("partial")
        and feature.face_indices
    ]
    holes = [
        feature for feature in found.values() if feature.kind == "hole" and feature.face_indices
    ]
    if not cones or not holes:
        return dict(found)
    body = mesh.raw
    count = len(body.faces)
    bore_of = np.full(count, -1, dtype=np.int64)
    for number, hole in enumerate(holes):
        indices = np.asarray(hole.face_indices, dtype=np.int64)
        bore_of[indices[(indices >= 0) & (indices < count)]] = number
    pairs = np.asarray(body.face_adjacency, dtype=np.int64).reshape(-1, 2)
    seams = np.asarray(body.face_adjacency_edges, dtype=np.int64).reshape(-1, 2)
    vertices = np.asarray(body.vertices, dtype=float)
    faces = np.asarray(body.faces, dtype=np.int64)
    tolerance = units.match_tolerance(mesh.bounds.diagonal)
    # **Die Nähte je Dreieck, einmal für alle Kegel** — nicht je Kegel eine
    # Maske über das ganze Netz: So wäre der Aufwand Kegel mal Dreiecke, und
    # genau das kostete die Kanalfrage am Eiffelturm eine halbe Stunde.
    # Gebraucht werden nur Nähte, die einen Kegel berühren; jede steht
    # zweimal, einmal von jeder Seite.
    in_a_cone = np.zeros(count, dtype=bool)
    for _identifier, cone in cones:
        indices = np.asarray(cone.face_indices, dtype=np.int64)
        in_a_cone[indices[(indices >= 0) & (indices < count)]] = True
    near = in_a_cone[pairs[:, 0]] | in_a_cone[pairs[:, 1]]
    pairs, seams = pairs[near], seams[near]
    sides = np.concatenate([pairs[:, 0], pairs[:, 1]])
    across_all = np.concatenate([pairs[:, 1], pairs[:, 0]])
    rims_all = np.concatenate([seams, seams])
    order = np.argsort(sides, kind="stable")
    starts = np.searchsorted(sides[order], np.arange(count + 1, dtype=np.int64))
    kept = dict(found)
    for identifier, cone in cones:
        if check_cancelled is not None:
            check_cancelled()
        axis = axis_of(cone)
        wide = centre_of(cone)
        if axis is None or wide is None:
            continue
        indices = np.asarray(cone.face_indices, dtype=np.int64)
        indices = np.unique(indices[(indices >= 0) & (indices < count)])
        if not len(indices):
            continue
        counts = starts[indices + 1] - starts[indices]
        total = int(counts.sum())
        if not total:
            continue
        first = np.repeat(starts[indices] - (np.cumsum(counts) - counts), counts)
        entries = order[first + np.arange(total, dtype=np.int64)]
        outside = ~np.isin(across_all[entries], indices)
        if not bool(outside.any()):
            continue
        neighbours = across_all[entries][outside]
        rims = rims_all[entries][outside]
        corners = vertices[np.unique(faces[indices])] - wide
        heights = (corners * axis).sum(axis=1)
        narrow_end, wide_end = float(heights.min()), float(heights.max())
        # Jede Naht nach draußen gehört zu dem Ende, dem ihre Mitte näher liegt.
        levels = ((vertices[rims] - wide) * axis).sum(axis=2).sum(axis=1) / 2.0
        at_wide_end = wide_end - levels < levels - narrow_end
        to_a_bore = bore_of[neighbours] >= 0
        # **Das weite Ende sitzt auf seiner Bohrung, das enge auf keiner** — und
        # zwar mehrheitlich: Am Deckel eines Töpfchens lag ein eingepasster
        # Kegel mit dem weiten Ende zur Hälfte an der Außenfläche, zur Hälfte an
        # einer Bohrung, und welches Ende die Mündung ist, sagt das nicht
        # (Regel 21, gemessen am Korpus).
        if 2 * int((at_wide_end & to_a_bore).sum()) <= int(at_wide_end.sum()):
            continue
        if bool((~at_wide_end & to_a_bore).any()):
            continue
        if not _open_at_the_narrow_end(
            vertices, faces, rims[~at_wide_end], neighbours[~at_wide_end], wide, axis, tolerance
        ):
            continue
        # **Und die Weite, die sie lässt** (``opening``): Das Maß des Kegels
        # ist sein weites Ende, an der Lippe also die Tasche selbst — im Baum
        # stand „Verengung Ø 8,25" neben „Sackbohrung Ø 8,25", und wie eng
        # die Mündung ist, sagte keine Zahl. Gemessen an den Ecken ihrer
        # Dreiecke, der engste Abstand zur Achse. Enger als die
        # Vergleichstoleranz des Körpers ist es keine Öffnung, sondern eine
        # Spitze.
        radial = corners - heights[:, None] * axis
        opening = 2.0 * float(np.sqrt((radial * radial).sum(axis=1)).min())
        if opening <= tolerance:
            continue
        kept[identifier] = replace(
            cone,
            params={**cone.params, "narrowing": True, "opening": opening},
            measure_sources={**cone.measure_sources, "opening": source},
        )
    return kept


def _open_at_the_narrow_end(
    vertices: np.ndarray,
    faces: np.ndarray,
    seams: np.ndarray,
    neighbours: np.ndarray,
    wide: np.ndarray,
    axis: np.ndarray,
    tolerance: float,
) -> bool:
    """Ob ein Kegel an seinem engen Ende offen ist — ob dort eine Mündung liegt.

    ``seams`` sind die Nähte seines engen Endes nach draußen, ``neighbours``
    die Dreiecke jenseits davon. Gefragt wird je Dreieck seine dritte Ecke, die
    nicht auf der Naht liegt: Steht sie um mehr als ``tolerance`` weiter von
    der Achse als die Naht, läuft dort die Oberfläche um die Öffnung herum —
    die Deckfläche über einer Haltelippe, eine Rundung an ihrer Kante. Offen
    heißt: mehr als die Hälfte so. Ein Boden unter einer Fase am Grund einer
    Tasche liegt innen, auch ohne Mittelpunkt vernetzt (seine dritten Ecken
    liegen auf dem Rand oder davor); ein Zylinder, der mit der engen Weite
    weiterläuft, bleibt auf ihr — das ist eine Stufe zwischen zwei
    Durchmessern, keine Mündung (die Wulst im Siebring des Korpus). Ohne Naht
    am engen Ende endet der Kegel in einer Spitze. Gerechnet mit
    Grundrechenarten (RM-187).
    """
    if not len(seams):
        return False

    def radial(points: np.ndarray) -> np.ndarray:
        along = (points * axis).sum(axis=-1)
        sideways = points - along[..., None] * axis
        distances: np.ndarray = np.sqrt((sideways * sideways).sum(axis=-1))
        return distances

    corners = faces[neighbours]
    far = (corners != seams[:, :1]) & (corners != seams[:, 1:])
    single = far.sum(axis=1) == 1
    if not bool(single.any()):
        return False
    third = corners[single][far[single]]
    ring = radial(vertices[seams[single]] - wide).max(axis=1)
    outward = int((radial(vertices[third] - wide) > ring + tolerance).sum())
    return 2 * outward > len(seams)


def _face_count(body: trimesh.Trimesh, faces: Sequence[int] | np.ndarray) -> int:
    """Wie viele Dreiecke diese Auswahl vor *Kanten verfeinern* war (R1, Durchsicht 0.5.1).

    Die Stücke eines Ursprungs (``geom.mesh.refined_units``) zählen als eines,
    ein Dreieck ohne Ursprung für sich; an einem ungeteilten Netz ist das
    ``len(faces)``. **Jede Schwelle, die eine Dreieckszahl meint, fragt
    hier** (:data:`MIN_PATCH_FACES`): Sie misst, ob ein Fleck genug Form für
    eine Einpassung trägt, und die Teilung fügt keine Form hinzu. Ohne das
    wurden am Screen-Cover nach 1 mm und einer Bohrung Splitter aus zwei, drei
    Dreiecken eines Schriftzugs eingepasst, die am Original unter der Schwelle
    lagen — 15 Verrundungen mehr als am Original.
    """
    units = refined_units(body)
    if units is None:
        return len(faces)
    chosen = units[np.asarray(faces, dtype=np.intp)]
    kept = chosen[chosen >= 0]
    return int(len(chosen) - len(kept)) + int(np.unique(kept).size)


def _unit_keys(units: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Je Dreieck die Nummer, unter der es zählt: sein Ursprung, oder ohne einen es selbst.

    Die Nummern ohne Ursprung liegen im Negativen (``-1 - Dreieck``), damit sie
    keinem Ursprung gleichen.
    """
    own = units[faces]
    return np.where(own >= 0, own, -1 - faces)


def _unit_sizes(
    body: trimesh.Trimesh, members: np.ndarray, owner: np.ndarray, sizes: np.ndarray
) -> np.ndarray:
    """Je Facette, wie viele Dreiecke sie vor *Kanten verfeinern* hatte (:func:`_face_count`).

    Für alle Facetten in einem Zug: ``members`` und ``owner`` wie bei
    :func:`_facet_table`. An einem ungeteilten Netz kommen ``sizes`` zurück.
    """
    units = refined_units(body)
    if units is None or not len(sizes):
        return np.asarray(sizes, dtype=np.int64)
    keys = _unit_keys(units, np.asarray(members, dtype=np.int64))
    # Facette und Nummer als eine Zahl: die Nummern um ihr Minimum verschoben.
    shifted = keys - int(keys.min())
    span = int(shifted.max()) + 1
    distinct = np.unique(np.asarray(owner, dtype=np.int64) * span + shifted)
    return np.bincount(distinct // span, minlength=len(sizes)).astype(np.int64)


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


def _outline_corners(
    body: trimesh.Trimesh, members: np.ndarray, owner: np.ndarray, sizes: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Je Facette die Ecken ihres Umrisses und die Punkte in ihrem Inneren.

    Gezählt werden die Randecken, an denen der Umriss abknickt — mehr als
    :data:`EPS_ANGLE`, gerechnet mit Grundrechenarten (RM-187). Ein Punkt,
    den eine Teilung auf eine gerade Kante setzt, knickt nicht; eine Ecke, an
    der mehr oder weniger als zwei Randkanten enden, zählt als Ecke. Hat eine
    Facette ein Dreieck ohne genau drei Nachbarn — offener Rand, verzweigte
    Kante —, bleibt es bei ihrer Dreieckszahl: Dort kennt die Nachbarschaft
    den Umriss nicht vollständig. Innere Punkte sind Ecken ihrer Dreiecke,
    die auf keiner Randkante liegen.
    """
    facet_count = len(sizes)
    if not facet_count:
        empty = np.asarray(sizes, dtype=np.int64)
        return empty, empty
    count = len(body.faces)
    label = np.full(count, -1, dtype=np.int64)
    label[members] = owner
    neighbours, _rows = _neighbour_index(body)
    known = (
        (neighbours >= 0).sum(axis=1) if neighbours.shape[1] else np.zeros(count, dtype=np.int64)
    )
    irregular = np.zeros(facet_count, dtype=bool)
    irregular[label[members[known[members] != 3]]] = True
    pairs = np.asarray(body.face_adjacency, dtype=np.int64).reshape(-1, 2)
    seams = np.asarray(body.face_adjacency_edges, dtype=np.int64).reshape(-1, 2)
    first, second = label[pairs[:, 0]], label[pairs[:, 1]]
    on_first = (first >= 0) & (first != second)
    on_second = (second >= 0) & (second != first)
    rim_facet = np.concatenate((first[on_first], second[on_second]))
    rim = np.concatenate((seams[on_first], seams[on_second]))
    # Jede Randkante zweimal, von jeder ihrer Ecken aus gesehen.
    at_facet = np.concatenate((rim_facet, rim_facet))
    at_vertex = np.concatenate((rim[:, 0], rim[:, 1]))
    toward = np.concatenate((rim[:, 1], rim[:, 0]))
    # Alle Ecken je Facette, einmal gezählt; innere sind die ohne Randkante.
    corner_of = np.asarray(body.faces, dtype=np.int64)[members]
    keys = np.unique(np.repeat(owner, 3) * len(body.vertices) + corner_of.ravel())
    # **Nach *Kanten verfeinern* zählen nur die Ecken, die es vorher gab** (R1):
    # Die Teilung setzt Punkte in jede Facette, und ohne diese Zeile wäre jede
    # geteilte Facette ein Teilstück mit inneren Punkten (:func:`_divider_pieces`).
    # Eine Ecke von vorher trägt Stücke von mindestens drei Ursprüngen um sich;
    # ein Teilungspunkt auf einer Kante zwei, einer in einem Dreieck einen.
    before = _corners_before_refining(body, members, corner_of)
    weight = None if before is None else before[keys % len(body.vertices)]
    every = np.bincount(keys // len(body.vertices), weights=weight, minlength=facet_count)
    every = np.rint(every).astype(np.int64)
    if not len(at_facet):
        return np.where(irregular, sizes, 0).astype(np.int64), every
    order = np.lexsort((toward, at_vertex, at_facet))
    at_facet, at_vertex, toward = at_facet[order], at_vertex[order], toward[order]
    fresh = np.r_[True, (at_facet[1:] != at_facet[:-1]) | (at_vertex[1:] != at_vertex[:-1])]
    starts = np.flatnonzero(fresh)
    lengths = np.diff(np.r_[starts, len(at_facet)])
    corner = np.ones(len(starts), dtype=bool)
    through = lengths == 2
    base = starts[through]
    points = np.asarray(body.vertices, dtype=np.float64)
    here = points[at_vertex[base]]
    one = points[toward[base]] - here
    two = points[toward[base + 1]] - here
    crossed = np.cross(one, two)
    span = np.sqrt((one * one).sum(axis=1)) * np.sqrt((two * two).sum(axis=1))
    bent = np.sqrt((crossed * crossed).sum(axis=1)) > units.exact_sin_degrees(EPS_ANGLE) * span
    # Zwei Kanten in dieselbe Richtung sind eine Spitze, keine Gerade.
    folded = (one * two).sum(axis=1) > 0.0
    corner[through] = bent | folded
    corners = np.bincount(at_facet[starts[corner]], minlength=facet_count).astype(np.int64)
    rim_weight = None if before is None else before[at_vertex[starts]]
    on_the_rim = np.rint(np.bincount(at_facet[starts], weights=rim_weight, minlength=facet_count))
    inner = (every - on_the_rim.astype(np.int64)).astype(np.int64)
    return np.where(irregular, np.asarray(sizes, dtype=np.int64), corners), inner


def _corners_before_refining(
    body: trimesh.Trimesh, members: np.ndarray, corner_of: np.ndarray
) -> np.ndarray | None:
    """Je Ecke, ob es sie vor *Kanten verfeinern* gab (``1.0``) — ``None`` an einem
    ungeteilten Netz.

    Gefragt an den Dreiecken der Facetten (``members``, ihre Ecken
    ``corner_of``): Eine Ecke im Inneren einer Facette hat nur Dreiecke dieser
    Facette um sich. Stücke von mindestens drei Ursprüngen um eine Ecke —
    jedes Dreieck ohne Ursprung zählt für sich — machen sie zu einer Ecke von
    vorher; ein Teilungspunkt auf einer alten Kante hat zwei, einer im Inneren
    eines alten Dreiecks einen. Für Randecken gilt die Antwort nicht, und dort
    wird sie auch nicht gefragt.
    """
    units = refined_units(body)
    if units is None:
        return None
    keys = np.repeat(_unit_keys(units, np.asarray(members, dtype=np.int64)), 3)
    shifted = keys - int(keys.min()) if len(keys) else keys
    span = int(shifted.max()) + 1 if len(keys) else 1
    pairs = np.unique(corner_of.ravel() * span + shifted)
    around = np.bincount(pairs // span, minlength=len(body.vertices))
    return (around >= 3).astype(np.float64)


#: Wie viele Ecken ein Teilstück der Vernetzung einer Rundung höchstens hat:
#: Mäntel und Kehlen kommen als Streifen (vier), Kugeln und Ringe als Dreiecke
#: und Vierecke. Eine kleine Ebene mit mehr Ecken — ein Deckel, eine Kerbe, die
#: Kante einer Senkung — ist keines, auch wenn der Exporter innere Punkte in sie
#: gesetzt hat. Gemessen am Korpus (Durchsicht 0.5.1): An einem Lochbrett
#: (``pegboard_pb3041``) fielen Fächer aus neun Dreiecken und sechs Ecken am
#: Rand der Senkungen, nach Ecken gezählt, in deren Fleck und nahmen drei von
#: vier Senkungen; am Siebhalter wurden zwei fast ebene Facetten von 80 mm² zu
#: Rundungsstücken.
_TESSELLATION_CORNERS: Final = 4


def _divider_pieces(corners: np.ndarray, inner: np.ndarray) -> np.ndarray:
    """Je Facette, ob ein Teiler sie zerlegt hat: innere Punkte und höchstens
    :data:`_TESSELLATION_CORNERS` Umrissecken — ein Streifen, ein Dreieck.

    Eine Frage für zwei Leser: die Zählung der Ebenenregel (:func:`_flat_counts`)
    und den Radius im Inneren eines Teilstücks (:func:`_through_the_piece`).
    """
    return (np.asarray(inner) > 0) & (np.asarray(corners) <= _TESSELLATION_CORNERS)


def _flat_counts(
    body: trimesh.Trimesh,
    facets: Sequence[np.ndarray],
    members: np.ndarray,
    owner: np.ndarray,
    sizes: np.ndarray,
) -> np.ndarray:
    """Was :data:`MIN_FLAT_FACES` je Facette zählt: Dreiecke, höchstens so viele wie Umrissecken.

    **Die Regel meint den Umriss, gezählt hat sie die Dreiecke** (ERKENNUNG-04).
    Ein Zylinderdeckel kommt als Fächer mit einem Dreieck je Segment, und acht
    Dreiecke waren acht Ecken. *Kanten verfeinern* setzt aber Punkte auf die
    geraden Ränder und ins Innere einer Facette, ohne die Form zu ändern — und
    jeder Mantelstreifen einer Verrundung trug danach acht und mehr koplanare
    Dreiecke mit vier Ecken. Nach der Dreieckszahl galt jeder Streifen als
    Ebene: am Besenhalter nach 2 mm aus 36 Flächen 552 und aus 93
    Verrundungen 11, an der Säule mit Kehle aus sieben Flächen 102, am
    Screen-Cover nach 1 mm statt einer gerundeten Seite 45 Verrundungen
    (Durchsicht 0.5.1). Dieselbe Stelle stand seit dem 04.09.2026 als offene im
    Kommentar bei :func:`_facet_verdicts_read`.

    **Höchstens, nicht stattdessen, und nur an einem Teilstück.** Die
    Umrissecken allein machten jeden Streifen aus sechs Dreiecken auf einer
    verrauschten Haut zur Ebene — acht Randpunkte, jeder ein Knick: am Korpus
    56 000 Facetten, die Ebene geworden wären. Gedeckelt wird deshalb nur, was
    ein Teiler aufgebläht hat: eine Facette mit inneren Punkten und höchstens
    :data:`_TESSELLATION_CORNERS` Ecken — ein Streifen, ein Dreieck. Kippen
    kann eine Facette damit nur zur Rundung hin, und nur, wo sie ein Stück
    einer Rundung ist.

    **Ein Splitter unter der Erkennungsauflösung behält seine Dreiecke.** Die
    hundertstelbreiten Streifen an den Kanten eines Boolesch gebauten Körpers
    — am Screen-Cover 67 Stück, 131,5 mm lang, 0,02 mm breit, je 520
    Dreiecke mit vier Ecken — knicken gegen ihre Nachbarn wie ein Mantelstreifen
    und hielten sich nur über ihre Dreieckszahl aus der Rundformsuche heraus;
    darin zerfiel die gerundete Seite der Buchstaben in sechzehn Verrundungen.
    Ein solcher Streifen ist keine Rundung: Breite durch Knick ergibt den
    Radius, auf dem er läge — am Screen-Cover 0,1 mm, unter
    :data:`MIN_CYLINDER_DIAMETER`. Der Streifen einer Verrundung R 3 ist nur
    0,2 mm breit, knickt aber um 3,75 Grad und liegt auf 3 mm; er zählt nach
    Ecken. Ein Splitter ohne weichen Rand gehört zu keiner Rundung und bleibt
    ebenfalls bei seinen Dreiecken.

    **Und nach *Kanten verfeinern* zählen die Dreiecke von vorher** (R1-Rest,
    Durchsicht 0.5.1). Die Deckelung oben trifft nur Streifen und Dreiecke; die
    Flanken eines Schriftzugs sind Facetten mit fünf bis neun Ecken, am
    Screen-Cover mit zwei Dreiecken weniger als Ecken — unter der Schwelle, also Teil der
    gerundeten Seite. Geteilt trugen sie Dutzende, wurden eben, und die Seite
    zerfiel nach 1 mm und einer Bohrung in 50 Verrundungen. Aus der Geometrie
    allein lässt sich eine geteilte Facette von einer gleich geformten
    ungeteilten nicht trennen (gemessen am Korpus: eine Schätzung der
    kleinsten Vernetzung kippte an 52 110 Facetten in 204 ungeteilten Körpern);
    der Ursprung je Dreieck (``geom.mesh.refined_units``) sagt es. Gezählt wird
    je Ursprung (:func:`_unit_sizes`), innere Punkte nur, wo es sie vorher gab
    (:func:`_outline_corners`), und jeder Knick am Rand einmal je alter Kante.
    """
    sizes = _unit_sizes(body, members, owner, np.asarray(sizes, dtype=np.int64))
    counted: np.ndarray = sizes.copy()
    # Gefragt werden nur Facetten, die nach Dreiecken als Ebene zählen — die
    # übrigen ändert die Deckelung nicht, und am Drachen sind das 300 000 von
    # 320 000 Facetten: zwei Sekunden Umrissrechnung für nichts.
    wanted = np.flatnonzero(sizes >= MIN_FLAT_FACES)
    if not len(wanted):
        return counted
    keep = np.zeros(len(sizes), dtype=bool)
    keep[wanted] = True
    chosen = keep[owner]
    renumbered = np.full(len(sizes), -1, dtype=np.int64)
    renumbered[wanted] = np.arange(len(wanted))
    corners, inner = _outline_corners(
        body, members[chosen], renumbered[owner[chosen]], sizes[wanted]
    )
    # Gedeckelt wird nur ein Teilstück einer Rundung, das ein Teiler zerlegt hat:
    # innere Punkte und höchstens vier Ecken — ein Streifen, ein Dreieck.
    split_up = _divider_pieces(corners, inner)
    counted[wanted[split_up]] = np.minimum(sizes[wanted[split_up]], corners[split_up])
    doubtful = np.flatnonzero((sizes >= MIN_FLAT_FACES) & (counted < MIN_FLAT_FACES))
    if not len(doubtful):
        return counted
    # Die weichen Randknicke aller fraglichen Facetten in einem Durchgang:
    # je Randkante ihr Knick, der Facette zugeschrieben, auf deren Seite sie
    # liegt — eine Maske über alle Nähte je Facette kostete an einem Netz mit
    # Millionen Dreiecken Minuten.
    asked = np.zeros(len(sizes), dtype=bool)
    asked[doubtful] = True
    label = np.full(len(body.faces), -1, dtype=np.int64)
    label[members] = owner
    pairs = np.asarray(body.face_adjacency, dtype=np.int64).reshape(-1, 2)
    angles = np.asarray(body.face_adjacency_angles, dtype=float)
    first, second = label[pairs[:, 0]], label[pairs[:, 1]]
    rim = (first != second) & (angles < math.radians(CURVATURE_LIMIT))
    rim &= angles > math.radians(EPS_ANGLE)
    on_first = rim & (first >= 0) & asked[np.maximum(first, 0)]
    on_second = rim & (second >= 0) & asked[np.maximum(second, 0)]
    whose = np.concatenate((first[on_first], second[on_second]))
    bends = np.concatenate((angles[on_first], angles[on_second]))
    units = refined_units(body)
    if units is not None and len(whose):
        # Nach *Kanten verfeinern* trägt eine alte Randkante viele Stücke mit
        # demselben Knick; gezählt wird sie einmal — je Paar ihrer Ursprünge,
        # die nur diese eine Kante teilen. Sonst verschöbe die Teilung den
        # Median zu den langen Kanten.
        inside = np.concatenate((pairs[on_first, 0], pairs[on_second, 1]))
        outside = np.concatenate((pairs[on_first, 1], pairs[on_second, 0]))
        seen = np.stack((whose, _unit_keys(units, inside), _unit_keys(units, outside)), axis=1)
        _rows, once = np.unique(seen, axis=0, return_index=True)
        once = np.sort(once)
        whose, bends = whose[once], bends[once]
    order = np.lexsort((bends, whose))
    whose, bends = whose[order], bends[order]
    begins = np.searchsorted(whose, doubtful, side="left")
    ends = np.searchsorted(whose, doubtful, side="right")
    for number, begin, end in zip(doubtful.tolist(), begins.tolist(), ends.tolist(), strict=True):
        facet = np.asarray(facets[number], dtype=np.int64).tolist()
        # Breit genug für eine Fläche: ein Stück einer Rundung, es zählt nach
        # Ecken. Schmaler: Breite durch Knick ist der Radius, auf dem er läge.
        if not _a_sliver(body, facet):
            continue
        area, reach = _area_and_reach(body, facet)
        if (
            reach <= EPS_GEOM
            or end == begin
            or _too_small_to_make(2.0 * area / reach / float(np.median(bends[begin:end])))
        ):
            counted[number] = sizes[number]
    return counted


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


def _rough_facet_area(body: trimesh.Trimesh, planar: set[int]) -> float:
    """Der Inhalt der rauen Tafeln: große Facetten, die Rauschen tragen (RM-235).

    Rau ist eine Facette aus ``planar``, deren Normalen nicht innerhalb
    :data:`EPS_ANGLE` der ersten liegen — dieselbe Prüfung, an der
    :func:`_planar_face_entries` eine Fläche scheitern lässt — und deren
    innere Knicke gemischt (:data:`FREEFORM_ROUGH_MIX`) und stark genug
    (:data:`FREEFORM_ROUGH_BEND`) sind. Gerechnet für alle Facetten in einem
    Zug. Die Knickwinkel kommen aus ``face_adjacency_angles`` wie bei der
    Nachtrennung (:func:`_connected_patches`); alles danach rechnet ohne BLAS,
    mit Grundrechenarten und Zählsummen, denn das Urteil wählt, was
    eingepasst wird (RM-187). An einer Schwelle hängt es am Korpus nicht: Der
    raue Anteil liegt zwischen 30 und 50 Prozent bei keinem Körper.
    """
    facets = body.facets
    if not len(facets) or not planar:
        return 0.0
    lengths = np.fromiter((len(facet) for facet in facets), dtype=np.int64, count=len(facets))
    members = np.concatenate([np.asarray(facet, dtype=np.int64) for facet in facets])
    owner = np.repeat(np.arange(len(facets)), lengths)
    starts = np.concatenate(([0], np.cumsum(lengths)[:-1]))
    in_planar = np.zeros(len(body.faces), dtype=bool)
    in_planar[np.fromiter(planar, dtype=np.int64, count=len(planar))] = True
    # Gezählt, nicht gewogen: Eine Summe aus Gewichten wäre eine Fließkommazahl,
    # und die verglich man mit ``==`` (Regel 6).
    all_planar = np.bincount(owner[~in_planar[members]], minlength=len(facets)) == 0
    normals = np.asarray(body.face_normals, dtype=float)
    first = normals[members[starts]]
    agreement = (normals[members] * first[owner]).sum(axis=1)
    level = np.minimum.reduceat(agreement, starts) >= units.exact_cos_degrees(EPS_ANGLE)
    candidates = all_planar & ~level
    if not candidates.any():
        return 0.0
    facet_of = np.full(len(body.faces), -1, dtype=np.int64)
    facet_of[members] = owner
    pairs = np.asarray(body.face_adjacency, dtype=np.int64).reshape(-1, 2)
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    convex = np.asarray(body.face_adjacency_convex, dtype=bool)
    within = facet_of[pairs[:, 0]]
    inner = (within >= 0) & (within == facet_of[pairs[:, 1]]) & (angles > EPS_ANGLE)
    within, bends, outward = within[inner], angles[inner], convex[inner]
    bulging = np.bincount(within, weights=bends * outward, minlength=len(facets))
    hollow = np.bincount(within, weights=bends * ~outward, minlength=len(facets))
    total = bulging + hollow
    mixed = np.divide(
        np.minimum(bulging, hollow), total, out=np.zeros(len(facets)), where=total > 0.0
    )
    # Der 90-Prozent-Wert je Facette wie ``np.percentile``: linear zwischen den
    # zwei Nachbarn an der Stelle 0,9 · (n - 1) der sortierten Knicke.
    order = np.lexsort((bends, within))
    within, bends = within[order], bends[order]
    counts = np.bincount(within, minlength=len(facets))
    group = np.concatenate(([0], np.cumsum(counts)[:-1]))
    position = 0.9 * np.maximum(counts - 1, 0)
    low = np.floor(position).astype(np.int64)
    high = np.minimum(low + 1, np.maximum(counts - 1, 0))
    strong = np.zeros(len(facets))
    present = counts > 0
    base = group[present]
    below, above = bends[base + low[present]], bends[base + high[present]]
    strong[present] = below + (above - below) * (position[present] - low[present])
    rough = candidates & (mixed >= FREEFORM_ROUGH_MIX) & (strong >= FREEFORM_ROUGH_BEND)
    areas = np.bincount(
        owner, weights=np.asarray(body.area_faces, dtype=float)[members], minlength=len(facets)
    )
    return float(areas[rough].sum())


def _large_facet_faces(
    body: trimesh.Trimesh,
    *,
    check_cancelled: Callable[[], None] | None = None,
    share: _Share = _UNHEARD,
) -> set[int]:
    """Ebene Flecken von den Streifen einer gekrümmten Haut unterscheiden.

    Scharf begrenzte Flächen zählen ab der absoluten Erkennungsauflösung.
    Eine größere Bodenplatte darf kleine Nocken oder Drehwegdächer nicht
    unterdrücken. Viele koplanare Dreiecke oder eine breite Ebene qualifizieren
    sich auch neben einer Rundung; der vollständige Mantelnachweis schützt
    weiterhin vor bloß unterteilten Zylinderstreifen.

    Die Antwort für den ganzen Körper wird gemerkt (:func:`remembered`):
    Jeder Klick auf eine Bohrung fragte sie zweimal, je 0,17 s an der
    Lochplatte mit 360 000 Dreiecken (gemessen am 22.09.2026). Wer nur einzelne
    Facetten fragt — die Erkennung an einer Stelle —, fragt
    :func:`planar_facet`: dieselbe Regel, begrenzt auf ihren Fleck.

    ``share`` erfährt, wie weit die Frage ist (:class:`_Share`).
    """
    if check_cancelled is not None:
        check_cancelled()
    planar: set[int] = remembered(
        "large_facet_faces",
        body,
        (),
        lambda: _large_facet_faces_read(body, check_cancelled=check_cancelled, share=share),
        check_cancelled=check_cancelled,
    )
    return set(planar)


@dataclass(frozen=True, slots=True)
class _FacetVerdicts:
    """Die Ebenenregel der Vollerkennung je Facette, vor dem Mantelnachweis.

    ``members`` hält die Dreiecke aller Facetten hintereinander, ``owner`` je
    Mitglied seine Facette, ``label`` je Dreieck des Körpers seine Facette
    (``-1`` ohne). ``planar`` sagt je Facette, ob sie sich als Ebene
    qualifiziert, ``recoverable``, ob der Mantelnachweis sie wieder
    herausnehmen darf. ``candidate`` markiert je Dreieck, was zu einem
    Fleck des Mantelnachweises gehören kann: alles außer den geschützten
    Ebenen.
    """

    members: np.ndarray
    owner: np.ndarray
    label: np.ndarray
    planar: np.ndarray
    recoverable: np.ndarray
    candidate: np.ndarray


def _facet_verdicts(
    body: trimesh.Trimesh, *, check_cancelled: Callable[[], None] | None = None
) -> _FacetVerdicts:
    """Das Urteil je Facette, einmal je Körper — für den ganzen Körper wie für eine Stelle.

    :func:`_large_facet_faces` fragte es bei jeder angefragten Facette neu,
    und die Erkennung an einer Stelle fragt es seit Review R1 für jede
    gefundene Fläche (:func:`planar_facet`).
    """
    result: _FacetVerdicts = remembered(
        "facet_verdicts",
        body,
        (),
        lambda: _facet_verdicts_read(body, check_cancelled),
        check_cancelled=check_cancelled,
    )
    return result


def _facet_verdicts_read(
    body: trimesh.Trimesh, check_cancelled: Callable[[], None] | None = None
) -> _FacetVerdicts:
    """Der Rumpf von :func:`_facet_verdicts` — die Antwort merkt sich die Hülle.

    Geprüft wird der Abbruch zwischen den Schritten: Am Drachen mit 2,3
    Millionen Dreiecken lagen Facetten, Rundungsnähte, kleine Flächen und die
    Flecken danach 5,3 s ohne Prüfung hintereinander (25.09.2026); übrig ist
    ``body.facets`` selbst, ein Aufruf von 1,8 s.
    """
    facets = list(body.facets)
    if check_cancelled is not None:
        check_cancelled()
    count = len(body.faces)
    if not facets:
        empty = np.zeros(0, dtype=np.int64)
        nothing = np.zeros(0, dtype=bool)
        return _FacetVerdicts(
            empty,
            empty,
            np.full(count, -1, dtype=np.int64),
            nothing,
            nothing,
            np.ones(count, dtype=bool),
        )
    areas = _facet_areas(body, facets)
    # Ein Mantelstreifen eines Zylinders ist groß genug für eine Fläche und
    # trotzdem keine eigene Ebene — die Naht zu seinen Nachbarn sagt es. Der
    # zweite Weg bleibt davon unberührt: ein Fleck aus vielen koplanaren
    # Dreiecken ist eine Fläche, auch wenn er auf einer Rundung sitzt.
    curved = _curved_faces(body)
    if check_cancelled is not None:
        check_cancelled()
    # **Gemessen an der Gesamtoberfläche, nicht an der größten Facette.** Der
    # naheliegende Maßstab ist der falsche, und der Körper, der es zeigt, ist
    # der Torus: Er besteht **nur** aus Mantelstreifen, seine größte Facette
    # ist selbst einer, und jede liegt damit bei fast hundert Prozent. Gegen
    # die größte gemessen zerfiel ``torus_ring.stl`` in 288 ebene Flächen.
    broad = float(body.area) * BROAD_FACE_SHARE
    # **Der erste Zweig prüft die Rundung nicht.** Ein Mantelstreifen, den eine
    # Boolesche neu vernetzt hat, bestand aus mehr als acht koplanaren
    # Dreiecken und kam hier unbesehen durch. Gemessen an einem Mast Ø 5,
    # dessen Zapfen einmal versetzt wurde: fünfzig Facetten qualifizierten sich
    # allein über die Dreieckszahl, alle fünfzig saßen auf der Rundung, und der
    # Zapfen trug danach 720 statt 1630 Dreiecke. Seit der Durchsicht 0.5.1
    # zählt die Regel höchstens je Umrissecke (:func:`_flat_counts`) — ein
    # Streifen hat vier, und dieselbe Stelle hatte nach *Kanten verfeinern*
    # jeden Streifen einer Verrundung zur Fläche gemacht.
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
    if check_cancelled is not None:
        check_cancelled()
    # **Je Facette eine Zahl, nicht je Dreieck eine Mengenfrage.** Die
    # Comprehensions darunter fragten an der unterteilten Lochplatte
    # 115 000-mal ``index in curved`` (gemessen am 22.09.2026: 60 ms je
    # Erkennung); ``_facet_table`` beantwortet „berührt die Facette eine
    # Rundung" für alle Facetten mit einem ``bincount``.
    members, owner, sizes, touches_curved = _facet_table(facets, count, curved)
    # Gezählt werden die Ecken des Umrisses, nicht die Dreiecke (:func:`_flat_counts`).
    counted = _flat_counts(body, facets, members, owner, sizes)
    if check_cancelled is not None:
        check_cancelled()
    area_of = np.asarray(areas, dtype=float)
    stands_apart = np.zeros(len(facets), dtype=bool)
    if apart:
        stands_apart[np.fromiter(apart, dtype=np.int64, count=len(apart))] = True
    planar_facets = (
        (counted >= MIN_FLAT_FACES)
        | (area_of >= broad)
        | ((area_of >= MIN_FACE_AREA) & ~touches_curved)
        | stands_apart
    )
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
    for number in np.flatnonzero(counted >= MIN_FLAT_FACES).tolist():
        recoverable_facets[number] = bool(touches_curved[number]) or _a_sliver(
            body, [int(index) for index in facets[number]]
        )
    label = np.full(count, -1, dtype=np.int64)
    label[members] = owner
    candidate = np.ones(count, dtype=bool)
    candidate[members[(planar_facets & ~recoverable_facets)[owner]]] = False
    return _FacetVerdicts(members, owner, label, planar_facets, recoverable_facets, candidate)


def _round_surface(
    body: trimesh.Trimesh,
    mesh: MeshData,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Der Mantelnachweis: Ist dieser Fleck eine vollständige Rundform?

    Kegel, Kugel, ganzer Zylindermantel oder Torus — was die Vollerkennung
    auch als Merkmal führen würde. Ein Fleck, der das ist, besteht nicht aus
    ebenen Flächen, auch wenn seine Streifen viele koplanare Dreiecke tragen.
    """
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
    return round_surface


def _large_facet_faces_read(
    body: trimesh.Trimesh,
    *,
    check_cancelled: Callable[[], None] | None = None,
    share: _Share = _UNHEARD,
) -> set[int]:
    """Der Rumpf von :func:`_large_facet_faces` — die Antwort merkt sich die Hülle."""
    verdicts = _facet_verdicts(body, check_cancelled=check_cancelled)
    # Gemessen: das Urteil je Facette gut ein Drittel, die Flecken ein Fünftel,
    # der Mantelnachweis den Rest (Sonde p30, Durchsicht 0.5.1).
    share.reach(0.35)
    if not len(verdicts.planar):
        return set()
    members, owner = verdicts.members, verdicts.owner
    planar = set(members[verdicts.planar[owner]].tolist())
    recoverable = set(members[verdicts.recoverable[owner]].tolist())
    if not recoverable:
        return planar
    protected = planar - recoverable
    candidates = _all_but(len(body.faces), protected)
    mesh = MeshData.of(body)
    patches = _connected_patches(body, candidates, check_cancelled=check_cancelled)
    proofs = share.part(0.55, 1.0)
    planned = sum(_fit_weight(patch) for patch in patches)
    weighed = 0.0
    proven = [
        _face_count(body, patch) >= MIN_PATCH_FACES
        and not recoverable.isdisjoint(patch)
        and not _a_sliver(body, patch)
        for patch in patches
    ]
    # Der Mantelnachweis fragt je Fleck Kegel und Ring; welcher Lauf sicher
    # vergeblich wäre, sagt der Stapel vorher für alle (RM-209).
    screening = proofs.part(0.0, SCREEN_SHARE)
    proofs = proofs.part(SCREEN_SHARE, 1.0)
    with _screening(
        body,
        [patch for patch, asked in zip(patches, proven, strict=True) if asked],
        check_cancelled=check_cancelled,
        share=screening,
    ):
        for patch, asked in zip(patches, proven, strict=True):
            weighed += _fit_weight(patch)
            proofs.reach(weighed / planned)
            if check_cancelled is not None:
                check_cancelled()
            if not asked:
                continue
            if _round_surface(body, mesh, patch, check_cancelled=check_cancelled):
                planar.difference_update(patch)
    return planar


def planar_facet(
    body: trimesh.Trimesh,
    triangles: Sequence[int],
    *,
    limit: int,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Ob die Ebenenregel der Vollerkennung diese Dreiecke als eben einstuft (Review R1).

    Gefragt ist nur die Ebenenregel, nicht jede Bedingung einer Fläche:
    Mindestinhalt und Normalenstreuung (:func:`_planar_face_entries`) hängen
    allein an der Facette und stellt die Erkennung am Ausschnitt schon selbst
    — die großen, fast ebenen Facetten der Drachenhaut bekommen hier ``True``
    und kommen an der Stelle trotzdem nicht als Fläche (Review S5).

    Dieselbe Regel wie :func:`_large_facet_faces`, am **ganzen** Körper: das
    Urteil je Facette (:func:`_facet_verdicts`) und, wo der Mantelnachweis
    eine Facette herausnehmen darf, der Nachweis selbst (:func:`_round_surface`)
    über denselben Fleck. Die Erkennung an einer Stelle rechnet ``detect`` an
    einem Ausschnitt; dort waren ein Mantelstreifen leicht fünf Prozent der
    Fläche und ein halber Zapfenmantel kein vollständiger, und die Stelle
    meldete den Mantel eines Zapfens als ebene Fläche — dazu Taschenwände,
    Zapfenflanken und Kanalsohlen, die die Vollerkennung nicht führt.

    **Der Fleck wird ganz geflutet** (:func:`_patch_around`, Ring um Ring),
    **geprüft wird zuerst an wachsenden Teilen**: ab ``limit`` Dreiecken der
    Teil in der Reihenfolge der Ringe, dann der doppelt so große und so fort.
    Trägt ein Teil keine Rundform (:func:`_could_be_round`), trägt das Ganze
    erst recht keine, und die Facette bleibt eben — so bleiben die zwei Sohlen
    des Drachen, die über weiche Kanten an seiner Haut hängen, Flächen, ohne
    dass zwei Millionen Dreiecke eingepasst werden. Trägt jeder Teil eine, wird
    der ganze Fleck geprüft wie in der Vollerkennung: Die Abflachung eines
    Knaufs sitzt auf einer Kugelkuppe, ihr erster Teil passt auf eine Kugel,
    das Ganze samt Mantel auf nichts (Review S1). Unter ``limit`` beginnt die
    Prüfung gleich am Ganzen — ein kleiner Teil eines Mantels passt auf gar
    keine Einpassung (gemessen: unter 512 Dreiecken keiner der Prüfkörper,
    darüber alle), und der Schluss vom Teil aufs Ganze gilt nur für große
    Teile.

    Nicht nachgebildet ist, was benachbarte Flecken beim Schließen ihrer
    fransigen Ränder an sich nehmen (:func:`_without_notches` rechnet sie in
    der Vollerkennung der Reihe nach); der eigene Fleck wird geschlossen wie
    dort. Die Antwort merkt sich die Hülle je Facette.
    """
    indices = np.unique(np.asarray(list(triangles), dtype=np.int64))
    result: bool = remembered(
        "planar_facet",
        body,
        indices.tolist(),
        lambda: _planar_facet_read(body, indices, limit, check_cancelled),
        extra=limit,
        check_cancelled=check_cancelled,
    )
    return result


def _planar_facet_read(
    body: trimesh.Trimesh,
    indices: np.ndarray,
    limit: int,
    check_cancelled: Callable[[], None] | None,
) -> bool:
    """Der Rumpf von :func:`planar_facet` — die Antwort merkt sich die Hülle."""
    verdicts = _facet_verdicts(body, check_cancelled=check_cancelled)
    if not len(indices) or not len(verdicts.planar):
        return False
    labels = np.unique(verdicts.label[indices])
    if (labels < 0).any() or not verdicts.planar[labels].all():
        return False
    # **Die ganze Facette oder keine**: Die Vollerkennung führt eine Fläche mit
    # allen Dreiecken ihrer Facette. Am Ausschnitt beanspruchten Nachbarmerkmale
    # am Schaber sechs von 239 Dreiecken einer Deckfläche, und die Stelle meldete
    # den Rest als vollständige Fläche.
    sizes = np.bincount(verdicts.owner, minlength=len(verdicts.planar))
    if int(sizes[labels].sum()) != len(indices):
        return False
    recoverable = labels[verdicts.recoverable[labels]]
    if not len(recoverable):
        return True
    seeds = indices[np.isin(verdicts.label[indices], recoverable)]
    rings = _patch_around(body, seeds, verdicts.candidate, check_cancelled)
    total = sum(len(ring) for ring in rings)
    size, taken, parts = limit, 0, []
    for ring in rings:
        if size >= total:
            break
        parts.append(ring)
        taken += len(ring)
        if taken < size:
            continue
        part = in_body_order(body, [np.concatenate(parts).tolist()])[0]
        if not _could_be_round(body, part, check_cancelled=check_cancelled):
            return True
        size *= 2
    patch = np.concatenate(rings).tolist()
    requested = set(indices.tolist())
    labelled = verdicts.label >= 0
    mesh = MeshData.of(body)
    for group in in_body_order(body, _without_notches(body, [patch], belongs=verdicts.candidate)):
        if check_cancelled is not None:
            check_cancelled()
        chosen = np.asarray(group, dtype=np.int64)
        if (
            _face_count(body, group) < MIN_PATCH_FACES
            or requested.isdisjoint(group)
            or not (labelled[chosen] & verdicts.recoverable[verdicts.label[chosen]]).any()
        ):
            continue
        if _a_sliver(body, group):
            continue
        if _round_surface(body, mesh, group, check_cancelled=check_cancelled):
            return False
    return True


def _patch_around(
    body: trimesh.Trimesh,
    seeds: np.ndarray,
    candidate: np.ndarray,
    check_cancelled: Callable[[], None] | None,
) -> list[np.ndarray]:
    """Der Fleck um ``seeds`` wie in :func:`_connected_patches`, Ring um Ring.

    Gewachsen wird über dieselben Nähte — unter :data:`CURVATURE_LIMIT` und nur
    zwischen Dreiecken, die ``candidate`` zulässt — und je Runde nur über die
    Nachbarn der letzten; die Ringe kommen in dieser Folge zurück, damit ein
    wachsender Teil immer um die Facette herum liegt.
    """
    neighbours, rows = _neighbour_index(body)
    angles = np.asarray(body.face_adjacency_angles, dtype=float)
    seen = np.zeros(len(body.faces), dtype=bool)
    frontier = np.unique(np.asarray(seeds, dtype=np.int64))
    seen[frontier] = True
    rings = [frontier]
    while True:
        if check_cancelled is not None:
            check_cancelled()
        near, via = neighbours[frontier].ravel(), rows[frontier].ravel()
        present = near >= 0
        near, via = near[present], via[present]
        passable = candidate[near] & ~seen[near] & (np.degrees(angles[via]) < CURVATURE_LIMIT)
        frontier = np.unique(near[passable])
        if not len(frontier):
            return rings
        seen[frontier] = True
        rings.append(frontier)


def _could_be_round(
    body: trimesh.Trimesh,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Ob ein Teil eines Flecks zu einer Rundform gehören kann.

    Die Gegenfrage zu :func:`_round_surface` für einen Fleck, der nur zum Teil
    vorliegt: Jeder Teil einer Rundform lässt sich wie sie einpassen, aber der
    volle Umfang und die Erkennbarkeit fehlen ihm. Gefragt wird deshalb nur,
    ob eine der vier Einpassungen gelingt — gelingt keine, ist das Ganze keine.
    """
    cone = fit_cone(body, patch, check_cancelled=check_cancelled)
    if cone is not None and cone.good:
        return True
    ball = fit_sphere(body, patch, check_cancelled=check_cancelled)
    if ball is not None and ball.good:
        return True
    cylinder = fit_cylinder(body, patch, check_cancelled=check_cancelled)
    if cylinder is not None and cylinder.good:
        return True
    ring = fit_torus(body, patch, check_cancelled=check_cancelled)
    return ring is not None and ring.good


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
    # **Ein Punkt der Kontur, auch wenn ihn zwei Ecken tragen.** Die zwei
    # Enden einer Mantelkante fallen in der Projektion aufeinander — bis auf
    # das Rauschen der Achse, und das hing an der Reihenfolge der Dreiecke im
    # Fleck. An einer Schwammablage trug ein Bogen aus drei Konturpunkten
    # (40°, R 3) je nach Reihenfolge eine vierte „Ecke" 10⁻¹⁵ neben der
    # dritten und galt dann als Rundung; in 119 von 200 Reihenfolgen nicht
    # (22.09.2026). Die Zählung unten verlangt vier unabhängige Ecken.
    flat = _distinct_points(flat)
    hull = MultiPoint(flat).convex_hull
    if hull.geom_type != "Polygon":
        return None
    outline = np.asarray(hull.exterior.coords, dtype=float)[:-1]
    # Zuerst verschwinden alle numerisch geraden Hüllpunkte, vor der
    # Vereinfachung darunter: Wären dort ihre echten Nachbarn schon entfernt,
    # täuschte ein zuvor gerader Sehnenpunkt selbst eine Ecke vor.
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
    outline = _simplified_ring(outline, tolerance)
    boundary = Polygon(outline).exterior
    for start in range(0, len(flat), FIT_SCAN_BLOCK):
        if check_cancelled is not None:
            check_cancelled()
        away = distance(planar_points(flat[start : start + FIT_SCAN_BLOCK]), boundary)
        if float(np.max(away)) > tolerance:
            return None
    return outline


def _simplified_ring(outline: np.ndarray, tolerance: float) -> np.ndarray:
    """Die Ecken eines konvexen Rings ohne die, deren Weglassen höchstens
    ``tolerance`` kostet — gleich, an welcher Ecke der Ring beginnt.

    **Nicht Douglas-Peucker** (RM-210). Der hält den Anfang des Rings fest und
    teilt jeweils am fernsten Punkt; welche Ecken übrig blieben, hing damit
    daran, wo GEOS die Hülle beginnen lässt, und das folgt den Koordinaten.
    Gemessen am 1x1-Tray (Verrundung R 10, zwei Eckenreihen, die innere
    4,6 µm neben dem Kreis): In der gelesenen Lage blieb eine innere Ecke als
    Teilungspunkt stehen — r = 10,058, Streuung 0,11 —, um 37 Grad gedreht
    nicht — r = 10,000, Streuung 0,00. Die Zusammenlegung der zwei Hälften
    der Verrundung kippte daran, und aus einer wurden zwei.

    Weggelassen wird hier immer die Ecke, deren Lücke am wenigsten abweicht:
    Je verbliebener Ecke zählt der größte Abstand aller Ecken zwischen ihren
    zwei Nachbarn — die schon weggelassenen eingeschlossen — von deren
    Sehne. Die Reihenfolge folgt diesen Abständen und nicht der Lage im
    Ring; bei exakt gleichen entscheidet der lexikographisch kleinere Punkt.
    Dieselbe Grenze wie zuvor: Keine weggelassene Ecke liegt weiter als
    ``tolerance`` neben dem Ring, der übrig bleibt.
    """
    count = len(outline)
    if count <= 3:
        return outline
    # **Ein Haufen statt eines Durchgangs über alle Ecken je Schritt, und die
    # Lücken in Python-Zahlen** (RM-568). Der erste Weg suchte je
    # weggelassener Ecke das Minimum über den ganzen Ring und rechnete jede
    # Lücke mit fünf NumPy-Aufrufen über eine Handvoll Punkte — am Eiffelturm
    # 182 532 Lücken und 10,1 s der Erkennung. Dieselben Rechenschritte in
    # derselben Reihenfolge (:func:`_gap_distance`), derselbe Gleichstand:
    # kleinste Kosten, dann der lexikographisch kleinere Punkt, dann die
    # kleinere Nummer.
    xs: list[float] = outline[:, 0].tolist()
    ys: list[float] = outline[:, 1].tolist()
    before = [(index - 1) % count for index in range(count)]
    after = [(index + 1) % count for index in range(count)]
    kept = [True] * count
    costs: list[float] = _segment_distances(
        outline, outline[np.asarray(before)], outline[np.asarray(after)]
    ).tolist()
    version = [0] * count
    heap = [(costs[index], xs[index], ys[index], index, 0) for index in range(count)]
    heapq.heapify(heap)

    def gap_cost(corner: int) -> float:
        """Der größte Abstand der Ecken zwischen den Nachbarn von ``corner`` von deren Sehne."""
        start, end = before[corner], after[corner]
        inside = (
            range(start + 1, end)
            if start < end
            else itertools.chain(range(start + 1, count), range(end))
        )
        return _gap_distance(xs, ys, inside, start, end)

    def update(corner: int) -> None:
        costs[corner] = gap_cost(corner)
        version[corner] += 1
        heapq.heappush(heap, (costs[corner], xs[corner], ys[corner], corner, version[corner]))

    remaining = count
    while remaining > 3:
        lowest, _x, _y, corner, seen = heapq.heappop(heap)
        while not kept[corner] or seen != version[corner]:
            lowest, _x, _y, corner, seen = heapq.heappop(heap)
        if lowest > tolerance:
            break
        kept[corner] = False
        remaining -= 1
        start, end = before[corner], after[corner]
        after[start], before[end] = end, start
        update(start)
        update(end)
    return np.asarray(outline[np.asarray(kept)], dtype=float)


def _gap_distance(
    xs: Sequence[float], ys: Sequence[float], inside: Iterable[int], start: int, end: int
) -> float:
    """Der größte Abstand der Punkte ``inside`` von der Strecke von ``start`` nach ``end``.

    Rechenschritt für Rechenschritt :func:`_segment_distances` für eine
    gemeinsame Strecke, in Python-Zahlen: Produkt und Summe über zwei
    Spalten, dieselbe Untergrenze des Nenners, dieselbe Klammer auf null bis
    eins, die Wurzel aus der Quadratsumme — bitgleich, und für eine Handvoll
    Punkte ohne fünf NumPy-Aufrufe.
    """
    start_x, start_y = xs[start], ys[start]
    along_x, along_y = xs[end] - start_x, ys[end] - start_y
    squares = along_x * along_x + along_y * along_y
    floor = EPS_GEOM * EPS_GEOM
    denominator = max(floor, squares)
    largest = -math.inf
    for index in inside:
        point_x, point_y = xs[index], ys[index]
        share = ((point_x - start_x) * along_x + (point_y - start_y) * along_y) / denominator
        share = share if math.isnan(share) else min(max(share, 0.0), 1.0)
        off_x = point_x - (start_x + share * along_x)
        off_y = point_y - (start_y + share * along_y)
        distance = math.sqrt(off_x * off_x + off_y * off_y)
        if distance > largest:
            largest = distance
    return largest


def _segment_distances(points: np.ndarray, starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """Abstände ebener Punkte von Strecken, je Zeile oder gegen eine gemeinsame.

    Die Skalarprodukte als Produkt und Summe über zwei Spalten, nicht über
    ``einsum`` oder ``@``: Welche Ecke wegfällt, ist eine Wahl, und die soll
    auf jeder Maschine gleich ausgehen (RM-187).
    """
    along = ends - starts
    squares = (along * along).sum(axis=-1)
    share = np.clip(
        ((points - starts) * along).sum(axis=-1) / np.maximum(squares, EPS_GEOM * EPS_GEOM),
        0.0,
        1.0,
    )
    return np.asarray(
        np.linalg.norm(points - (starts + share[..., None] * along), axis=-1), dtype=float
    )


def _distinct_points(points: np.ndarray) -> np.ndarray:
    """Punkte, die höchstens :data:`~app.core.units.EPS_GEOM` auseinanderliegen, als einer.

    Über Ketten und unabhängig von der Reihenfolge: Jede Gruppe steht durch
    ihren lexikographisch kleinsten Punkt. ``EPS_GEOM`` ist die Grenze, unter
    der zwei Längen im Kern gleich sind — hier die zwei Enden einer
    Mantelkante, die in der Projektion auf denselben Punkt fallen.

    **Deckungsgleiche Punkte zuerst, dann die Nachbarschaft.** In der
    Projektion eines Zylindermantels fallen alle Ecken einer Mantellinie auf
    denselben Punkt; die Nachbarsuche über alle Punkte zählte jedes Paar
    davon. Gemessen an der großen Bohrung aus ``test_bore_floor_resize``:
    525 312 Punkte, 1 024 verschiedene, 134 Millionen Paare — 7 bis 21 s je
    Aufruf, viermal je Größenänderung (26.09.2026). Gleiche Punkte liegen
    ohnehin in einer Gruppe; gesucht wird deshalb nur zwischen verschiedenen.
    Welcher Punkt eine Gruppe vertritt, entscheidet weiter die
    lexikographische Reihenfolge über **alle** Punkte, bei Gleichstand die
    kleinere Nummer — dasselbe Ergebnis wie vorher.
    """
    if len(points) < 2:
        return points
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree

    # Lexikographisch sortiert liegen gleiche Punkte nebeneinander; ``lexsort``
    # ist stabil, der erste eines Laufs trägt also die kleinste Nummer.
    order = np.lexsort(points.T[::-1])
    ordered = points[order]
    starts = np.ones(len(points), dtype=bool)
    starts[1:] = np.any(ordered[1:] != ordered[:-1], axis=1)
    distinct = ordered[starts]
    pairs = cKDTree(distinct).query_pairs(EPS_GEOM, output_type="ndarray")
    if not len(pairs) and len(distinct) == len(points):
        return points
    count = len(distinct)
    links = coo_matrix(
        (np.ones(len(pairs), dtype=np.int8), (pairs[:, 0], pairs[:, 1])), shape=(count, count)
    )
    _groups, grouped = connected_components(links, directed=False)
    # Je Gruppe der erste Punkt in lexikographischer Reihenfolge.
    _labels, first = np.unique(grouped[np.cumsum(starts) - 1], return_index=True)
    return np.asarray(points[np.sort(order[first])], dtype=float)


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
    support = _support_handle(body, patch, check_cancelled)
    if support is None:
        return None
    tolerance = max(weld_tolerance(float(np.linalg.norm(body.extents))), ROUND_WALL_TOLERANCE)
    result: CylinderFit | None = _by_geometry(
        "fit_cylinder",
        body,
        support,
        lambda: _fit_cylinder_measured(body, patch, support.read(), tolerance, check_cancelled),
        tolerance,
    )
    return result


def _fit_cylinder_measured(
    body: trimesh.Trimesh,
    patch: list[int],
    support: _SurfaceSupport,
    tolerance: float,
    check_cancelled: Callable[[], None] | None,
) -> CylinderFit | None:
    """Die Zylindereinpassung an einer Lesung.

    Vom Körper liest sie in :func:`_chord_sag` Normalen, Flächen und Ecken des
    Flecks — die Lesung trägt dieselben Zahlen (:data:`GEOMETRY_KEYED_ANSWERS`).
    """
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


def _cylinder_precludes_a_cone(
    body: trimesh.Trimesh, fit: CylinderFit, patch: Sequence[int]
) -> bool:
    """Ein aufgelöster Zylinder braucht keine weitere Kegelnäherung.

    Die übliche Wandtoleranz allein genügt nicht: Eine kurze Verjüngung kann
    innerhalb davon liegen. Hier müssen sowohl die Originalecken als auch die
    senkrechten Mantelnormalen bis zur jeweiligen Geometriegenauigkeit stimmen.
    """
    return (
        fit.fit_error is not None
        and fit.fit_error <= EPS_GEOM
        and bool(
            np.max(np.abs(np.asarray(body.face_normals)[np.asarray(patch)] @ np.asarray(fit.axis)))
            <= units.exact_sin_degrees(EPS_ANGLE)
        )
    )


def radial_cylinder(
    body: trimesh.Trimesh,
    patch: list[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> CylinderFit | None:
    """Derselbe Konturfit mit der zusätzlichen Grenze der radialen Bearbeitung.

    Mindestens ein halber Mantel und die strengere Querstellung seiner
    Normalen schließen einen gewöhnlichen Übergang zwischen Tangentialebenen
    aus. Eingepasst wird hier selbst: Ein anderswo aufgebauter Kandidat
    ersetzt den Formnachweis nicht.
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
    und das ist in genau einer Richtung länger als quer dazu: die Richtung der
    größten Ausdehnung, aus den zwei Scheiteln gelesen — nicht die Hauptachse
    der Punktwolke, die bei wenig Weg quer zeigen kann (siehe den Kommentar
    im Rumpf). Ihre Ausdehnung quer ist der Durchmesser, längs die
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
        # Die Richtungen aus der genauen Kreistafel (RM-187): ``np.cos``
        # rundet auf AVX2, AVX-512 und NEON verschieden, und die breiteste
        # Richtung ist ein ``argmax`` — ein Unterschied in der letzten Stelle
        # wählt dort eine andere.
        sweep = np.asarray(units.circle_cos_sin(2 * STADIUM_SWEEP)[:STADIUM_SWEEP], dtype=float)
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
    """Private Lesezuordnung zwischen Netzpunkten und ihren Mantelfacetten.

    ``digest`` ist der Abdruck der ganzen Lesung samt der Dreiecke des Flecks,
    Bit für Bit — der Schlüssel des Merkers über die Körpergrenze
    (:func:`_by_geometry`).
    """

    points: np.ndarray
    corners: np.ndarray
    normals: np.ndarray
    centres: np.ndarray
    areas: np.ndarray
    round_corners: np.ndarray
    ridges: np.ndarray
    directions: np.ndarray
    digest: bytes = b""

    def read(self) -> _SurfaceSupport:
        """Die Lesung selbst — sie ist es schon (Gegenstück zu :meth:`_SupportPrint.read`)."""
        return self


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
    corners = np.asarray(body.faces)[indices].astype(np.int64).ravel()
    triangles = _counted_at(corners, used, len(body.vertices))
    inner_edges = _counted_at(edges.ravel(), used, len(body.vertices)) // 2
    return np.asarray(triangles - inner_edges, dtype=np.int64)


def _counted_at(values: np.ndarray, used: np.ndarray, vertex_count: int) -> np.ndarray:
    """Wie oft jede Ecke aus ``used`` (aufsteigend) in ``values`` vorkommt.

    ``values`` sind Ecken des Flecks, liegen also alle in ``used``. Gezählt
    wird über ``used`` statt über alle Ecken des Netzes, solange der Fleck
    klein ist (:data:`SORTED_CORNERS_SHARE`) — dieselbe Zahl je Ecke.
    """
    if len(values) < vertex_count * SORTED_CORNERS_SHARE:
        return np.bincount(np.searchsorted(used, values), minlength=len(used))
    return np.asarray(np.bincount(values, minlength=vertex_count)[used], dtype=np.int64)


#: Die zuletzt gelesenen Stützpunkte je Netz und Fleck (:func:`_surface_support`).
#: Acht Fragen an denselben Fleck — Kugel, Kegel, Zylinder, große Facetten —
#: lasen die Ikosphäre mit 327 680 Dreiecken achtmal, je über eine Sekunde
#: (gemessen am 21.09.2026). Der Schlüssel ist die Marke des Netzes und der
#: Abdruck der Flächenliste; die Geometrie dahinter ist unveränderlich
#: (Regel 3). **Nicht der Datenhash des Netzes:** trimesh rechnet ihn bei
#: jeder Frage neu, 0,4 ms an 200 000 Dreiecken — an der Freiform mit 9 589
#: Fragen waren das vier Sekunden, mehr als die Lesungen selbst.
#:
#: **Und eine Kopie antwortet aus dem Merker ihres Originals**
#: (:func:`copy_with_answers`, :class:`_Lineage`, Durchsicht 0.5.1). Die
#: Arbeiterkopie der Platzierung und des Merkmalfensters hatte leere Merker:
#: Die Hohlraumfläche einer Bohrung am Laptop-Ständer kostete an ihr 1,1 s,
#: am Original 0,07 s — die Kopie passte Kegel, Kugeln, Zylinder und Ringe
#: neu ein, die das Original längst kannte. Geteilt wird über die
#: **Abstammung** und nicht über einen Inhaltsabdruck: Der kostete an
#: denselben 173 592 Dreiecken 6,7 ms je Körper, auch an jeder verschweißten
#: Lesung, und hielte zwei gleiche Netze verschiedener Herkunft für eines,
#: obwohl trimesh die Flächennormalen aus der Datei behalten kann. Eine Kopie
#: ist dagegen Bit für Bit ihr Original. Geteilt werden nur die Antworten aus
#: :data:`SHARED_ANSWERS`; was ein Netz oder einen Suchbaum trägt, bleibt am
#: eigenen Körper (:data:`BODY_BOUND_ANSWERS`).
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
#: lebende Körper — der Ergebniscache hält bis zu einem Achtel des
#: Arbeitsspeichers (``scene.cache.MEMORY_SHARE``) — zusammen nicht mehr als
#: acht Lesungen halten.
SUPPORT_CACHE_LIMIT = 8
CACHE_LIMIT_PER_QUESTION = 4096

#: Fragen, deren Antwort so groß ist wie der ganze Körper — dieselbe Grenze
#: wie die Stützpunktlesung. Die verschweißte Kopie und der Oberflächenindex,
#: an denen die Mündungsprobe einer Bohrung jede Frage stellt
#: (``prepare_ops.bore_entrance``), wiegen am Gartenschlauchhalter mit 392 532
#: Dreiecken je rund 15 und gut 90 Megabyte; viertausend davon hielte kein Rechner.
#: Die Facette je Dreieck der Wendelsuche (``helix._facet_of_face``), die nach
#: Größe sortierten Facetten (``helix._facets_by_area``) und der
#: Krümmungssprung je Nachbarschaft (:func:`curvature_jumps`) tragen eine Zahl
#: je Dreieck, Facette oder Paar. Die vorbereitete Trägerfläche der Platzierung
#: (``placement.prepare_surface``) trägt die ganze Kontur einer Fläche und
#: gehört mit derselben Grenze dazu.
WHOLE_BODY_ANSWERS: Final[frozenset[str]] = frozenset(
    {
        "support",
        "merged_copy",
        "surface_index",
        "facet_of_face",
        "facets_by_area",
        "curvature_jumps",
        "face_radii",
        "prepared_surface",
        "surfaces_near",
        "radii_near",
        # Teil und Hüllquader je Hohlraum: ein Feld je Dreieck (Review G, F5).
        "cavity_boxes",
    }
)

#: Fragen, deren Antwort an genau ihren Körper gebunden bleibt — auch gegen
#: seine Kopie (:func:`copy_with_answers`). Sie tragen ein Netz, einen
#: Suchbaum oder eine vorbereitete GEOS-Fläche, und deren träge Merker füllen
#: sich beim Lesen, ohne Schloss: die verschweißte Lesung (``one_body``,
#: ``merged_copy``), der Oberflächenindex mit seinem Körper, der
#: Flächenausschnitt mit seinem ``cKDTree`` (``relations._SurfacePatch``) und
#: die Trägerfläche der Platzierung. Die Arbeiterkopie gibt es gerade, damit
#: der Nebenfaden nichts davon mit dem Hauptfaden teilt
#: (``placement_flow.for_a_worker``). **Eine Frage, die in keiner der beiden
#: Mengen steht, gilt als gebunden** — das Teilen ist die Ausnahme, die
#: jemand geprüft hat; ``test_features`` hält beide Mengen vollständig.
BODY_BOUND_ANSWERS: Final[frozenset[str]] = frozenset(
    {
        "body_extreme_points",
        "one_body",
        "merged_copy",
        "surface_index",
        "surface_patch",
        "prepared_surface",
        "surfaces_near",
        "radii_near",
    }
)

#: Die gebundenen Antworten, die selbst ein Körper sind. Derselbe Eingang
#: ergibt denselben Körper: Die verschweißte Lesung der Kopie teilt deshalb
#: die Antworten mit der verschweißten Lesung des Originals — sonst fingen
#: an einer ungeschweißten STL alle Fits der Kopie wieder von vorn an.
DERIVED_BODY_ANSWERS: Final[frozenset[str]] = frozenset({"one_body", "merged_copy"})

#: Fragen, deren Antwort Original und Kopie teilen: Fits, Nachweise, Zahlen,
#: Mengen und schreibgeschützte Felder — nichts, was beim Lesen etwas
#: nachbaut. Dieselben Antworten lesen Hauptfaden und Auswertung schon heute
#: am Original gemeinsam.
SHARED_ANSWERS: Final[frozenset[str]] = frozenset(
    {
        "a_sliver",
        # Funktionale Gruppen (``perceive.groups``): unveränderliche Namen und Zahlen.
        "functional_groups",
        "_sphere_is_recognisable",
        "_torus_is_recognisable",
        "_cone_is_recognisable",
        "curved_faces",
        "facets_standing_apart",
        "large_facet_faces",
        "facet_verdicts",
        "planar_facet",
        "planar_mask",
        "nearly_flat",
        "fit_cylinder",
        "fit_cone",
        "fit_sphere",
        "fit_torus",
        "support",
        "surface_owners",
        "face_radii",
        "curvature_jumps",
        "connected_patches",
        "facet_of_face",
        "facets_by_area",
        "cavity_surface",
        "same_surface_patch",
        "hole_is_clear",
        "own_part_bore_clear",
        "hole_has_separate_contents",
        "sticks_in_another_bore",
        "cavity_boxes",
        "thread_walls",
        "has_own_body",
        "moved_twin",
        "voids",
        "patch_print",
        "rectangle_across",
        "projected_span",
    }
)


#: Die zuletzt gebildeten Abdrücke je Listenobjekt — mit der Liste selbst als
#: Anker, damit ihre Identität nicht an eine andere Liste fallen kann.
_DIGESTS: OrderedDict[int, tuple[Sequence[int], bytes]] = OrderedDict()
DIGEST_LIMIT = 32


#: Die Marken der Merker: je Körper und je Abstammung eine, nie zweimal
#: vergeben. Eine Adresse geht nach dem Tod eines Körpers an den nächsten,
#: eine Marke nicht.
_TOKENS = itertools.count(1)


class _Lineage:
    """Ein Körper und seine Kopien — die Antworten, die sie teilen.

    ``token`` steht im Schlüssel jeder geteilten Antwort
    (:data:`SHARED_ANSWERS`), ``answers`` nennt sie wie
    :attr:`_BodyMemory.answers`. ``members`` zählt die lebenden Körper
    dieser Abstammung; stirbt der letzte, gehen die Antworten mit ihm.
    ``origin`` ist der Schlüssel in :data:`_DERIVED_LINEAGES`, wenn die
    Körper aus einer gebundenen Antwort stammen (:data:`DERIVED_BODY_ANSWERS`).
    ``geometric`` nennt die Antworten über die Körpergrenze, die diese
    Abstammung gerechnet oder gelesen hat (:func:`_by_geometry`) — sie halten
    sie mit.
    """

    __slots__ = ("answers", "geometric", "members", "origin", "token")

    def __init__(self, origin: tuple[Any, ...] | None = None) -> None:
        self.token = next(_TOKENS)
        self.origin = origin
        self.members = 0
        self.answers: set[tuple[str, tuple[int, bytes, Any, int]]] = set()
        self.geometric: set[tuple[str, bytes]] = set()


#: Je abgeleiteter Abstammung — Elternabstammung, Frage, Schlüssel — die
#: gemeinsame Abstammung ihrer Körper: die verschweißte Lesung des Originals
#: und die jeder Kopie. Der Eintrag geht, wenn der letzte dieser Körper stirbt.
_DERIVED_LINEAGES: dict[tuple[Any, ...], _Lineage] = {}


class _BodyMemory:
    """Was ein Körper in den Merkern hinterlassen hat — damit es mit ihm geht.

    ``answers`` nennt je gemerkter gebundener Antwort
    (:data:`BODY_BOUND_ANSWERS`) die Frage und den Schlüssel in
    :data:`_SUPPORT_CACHE`, ``digests`` die Listenabdrücke in :data:`_DIGESTS`.
    Beides sind Mengen, denn eine verdrängte und neu gerechnete Antwort trägt
    denselben Schlüssel. Die geteilten Antworten führt die Abstammung
    (``lineage``). Der schwache Verweis sagt, ob hinter der Adresse noch
    derselbe Körper steht.
    """

    __slots__ = ("answers", "digests", "lineage", "ref", "token")

    def __init__(self, body: trimesh.Trimesh, lineage: _Lineage) -> None:
        self.ref: weakref.ref[Any] = weakref.ref(body)
        self.token = next(_TOKENS)
        self.lineage = lineage
        lineage.members += 1
        self.answers: set[tuple[str, tuple[int, bytes, Any, int]]] = set()
        self.digests: set[int] = set()


#: Je lebendem Körper sein Merker, unter seiner Adresse.
_MEMORIES: dict[int, _BodyMemory] = {}

#: **Ein Schloss um alle drei Merker.** Das Merkmalfenster fragt
#: ``fillet_blocked`` → ``planar_mask`` im Hauptfaden, während der Arbeiter
#: dasselbe Modul für die nächste Auswertung fragt; ``get`` und
#: ``move_to_end`` an einem ``OrderedDict`` sind zwei Schritte, und wer
#: dazwischen verdrängt wird, bekam einen ``KeyError``. Wiedereintrittsfähig,
#: weil der Abschied eines Körpers (:func:`_forget_body`) aus der
#: Speicherbereinigung heraus in jedem Faden und an jeder Zuweisung laufen
#: kann — auch innerhalb des gehaltenen Schlosses.
_MEMORY_LOCK = threading.RLock()


def _memory_of(body: trimesh.Trimesh, lineage: _Lineage | None = None) -> _BodyMemory:
    """Der Merker eines Körpers, beim ersten Mal angelegt — mit dem Abschied im Gepäck.

    Ein neuer Körper beginnt eine eigene Abstammung, außer ``lineage`` nennt
    die, zu der er gehört (:func:`copy_with_answers`). Nur mit gehaltenem
    :data:`_MEMORY_LOCK` aufrufen.
    """
    key = id(body)
    memory = _MEMORIES.get(key)
    if memory is not None and memory.ref() is body:
        return memory
    memory = _BodyMemory(body, lineage if lineage is not None else _Lineage())
    _MEMORIES[key] = memory
    farewell = weakref.finalize(body, _forget_body, key, memory)
    # Beim Beenden des Prozesses gibt es nichts mehr aufzuräumen — und die
    # Modulvariablen sind dann womöglich schon abgebaut.
    farewell.atexit = False
    return memory


def held_answers(body: trimesh.Trimesh) -> list[Any]:
    """Was die Merker dieses Moduls für diesen Körper halten — zum Zählen, nicht zum Lesen.

    Die gebundenen Antworten, die seiner Abstammung und die über die
    Körpergrenze, die sie mithält. Sie gehen mit dem Körper (:func:`_forget_body`)
    und wiegen deshalb mit dem, der ihn hält: Am Spiderman hielten acht
    Schritte im Ergebniscache so über eine Milliarde Byte, die kein Feld des
    Netzes zeigte (RM-567, 08.10.2026).
    """
    with _MEMORY_LOCK:
        memory = _MEMORIES.get(id(body))
        if memory is None or memory.ref() is not body:
            return []
        found: list[Any] = []
        for name, key in (*memory.answers, *memory.lineage.answers):
            answers = _SUPPORT_CACHE.get(name)
            if answers is not None and key in answers:
                found.append(answers[key])
        for name, geometry_key in memory.lineage.geometric:
            shared = _BY_GEOMETRY.get(name)
            if shared is not None and geometry_key in shared:
                found.append(shared[geometry_key])
        return found


def _forget_body(key: int, memory: _BodyMemory) -> None:
    """Der Abschied: Die Antworten eines gestorbenen Körpers gehen mit ihm.

    Seine gebundenen sofort, die geteilten mit dem letzten Körper seiner
    Abstammung — solange eine Kopie lebt, antwortet sie weiter daraus.
    """
    with _MEMORY_LOCK:
        if _MEMORIES.get(key) is memory:
            del _MEMORIES[key]
        _drop_answers(memory.answers)
        for digest_key in memory.digests:
            _DIGESTS.pop(digest_key, None)
        memory.digests.clear()
        lineage = memory.lineage
        lineage.members -= 1
        if lineage.members <= 0:
            _drop_answers(lineage.answers)
            _release_geometric(lineage.geometric)
            if lineage.origin is not None and _DERIVED_LINEAGES.get(lineage.origin) is lineage:
                del _DERIVED_LINEAGES[lineage.origin]


def _drop_answers(held: set[tuple[str, tuple[int, bytes, Any, int]]]) -> None:
    """Die genannten Antworten aus :data:`_SUPPORT_CACHE` nehmen — nur unter dem Schloss."""
    for name, answer_key in held:
        answers = _SUPPORT_CACHE.get(name)
        if answers is not None:
            answers.pop(answer_key, None)
    held.clear()


def copy_with_answers(body: trimesh.Trimesh) -> trimesh.Trimesh:
    """Eine eigene Kopie eines Netzes, die aus dem Merker des Originals antwortet.

    Für einen Nebenfaden, der an einem Szenennetz rechnen soll, ohne dessen
    träge trimesh-Merker mit dem Hauptfaden zu teilen
    (``placement_flow.for_a_worker``, die Markierung der Ansicht). Kopiert
    wird samt trimesh-Cache — dieselben Felder, schreibgeschützt. Und die
    Kopie gehört zur Abstammung des Originals: Fits, Nachweise und
    Hohlraumflächen, die eines von beiden schon kennt, kennt das andere auch
    (:data:`SHARED_ANSWERS`). Gemessen an Bohrungen des Laptop-Ständers
    (173 592 Dreiecke): die Hohlraumfläche an der Kopie 1,1 s ohne, so schnell
    wie am Original mit. Gebundene Antworten — Netze, Suchbäume — rechnet
    die Kopie selbst.

    Die Kopie darf danach nicht verändert werden, so wenig wie ihr Original
    (Regel 3). Wer eine Kopie zum Umbauen braucht, nimmt ``body.copy()``.
    """
    copy = body.copy(include_cache=True)
    with _MEMORY_LOCK:
        _memory_of(copy, _memory_of(body).lineage)
    return copy


def _derived_from(value: Any, parent: _Lineage, name: str, question: tuple[Any, ...]) -> None:
    """Einen abgeleiteten Körper in die Abstammung seiner Geschwister stellen.

    Die verschweißte Lesung einer Kopie entsteht aus demselben Eingang wie
    die des Originals und ist deshalb derselbe Körper. Ein Körper, der schon
    einen Merker hat, bleibt, wo er ist. Nur unter dem Schloss aufrufen.
    """
    body = getattr(value, "raw", value)
    if not isinstance(body, trimesh.Trimesh):
        return
    known = _MEMORIES.get(id(body))
    if known is not None and known.ref() is body:
        return
    origin = (parent.token, name, *question)
    lineage = _DERIVED_LINEAGES.get(origin)
    if lineage is None:
        lineage = _DERIVED_LINEAGES[origin] = _Lineage(origin)
    _memory_of(body, lineage)


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

    Eine Antwort aus :data:`SHARED_ANSWERS` gilt für die ganze Abstammung
    des Körpers — Original und Kopien (:func:`copy_with_answers`) —, jede
    andere nur für ihn selbst.
    """
    # **Ein abgebrochener Auftrag bekommt auch keine gemerkte Antwort.** Der
    # Abbruch gilt dem Auftrag, nicht der Rechnung; wer schon abgebrochen hat,
    # beginnt nichts — und liest auch nichts nach.
    if check_cancelled is not None:
        check_cancelled()
    with _MEMORY_LOCK:
        memory = _memory_of(body)
    shared = name in SHARED_ANSWERS
    owner = memory.lineage if shared else None
    # Das Löserbudget gehört zum Schlüssel: Ein Test setzt es auf eins und
    # fragt danach noch einmal mit dem vollen — zwei Fragen, zwei Antworten.
    key = (
        memory.token if owner is None else owner.token,
        _patch_digest(memory, patch),
        extra,
        ROUND_FIT_EVALUATIONS,
    )
    with _MEMORY_LOCK:
        answers = _SUPPORT_CACHE.setdefault(name, OrderedDict())
        if key in answers:
            answers.move_to_end(key)
            return answers[key]
    value = compute()
    if check_cancelled is not None:
        check_cancelled()
    with _MEMORY_LOCK:
        answers = _SUPPORT_CACHE.setdefault(name, OrderedDict())
        answers[key] = value
        (memory.answers if owner is None else owner.answers).add((name, key))
        if name in DERIVED_BODY_ANSWERS:
            _derived_from(value, memory.lineage, name, key[1:])
        limit = SUPPORT_CACHE_LIMIT if name in WHOLE_BODY_ANSWERS else CACHE_LIMIT_PER_QUESTION
        while len(answers) > limit:
            answers.popitem(last=False)
    return value


def _known_answer(name: str, body: trimesh.Trimesh) -> Any:
    """Die gemerkte Antwort auf eine Frage an den ganzen Körper — oder ``None``, ohne zu rechnen.

    Für die örtlichen Wege (:func:`face_radii_at`, :func:`curvature_jumps_at`):
    Steht die Antwort für den ganzen Körper schon da, lesen sie daraus, statt
    ihre Umgebung neu zu rechnen. Derselbe Schlüssel wie :func:`remembered`
    mit leerem Fleck.
    """
    with _MEMORY_LOCK:
        memory = _MEMORIES.get(id(body))
        if memory is None or memory.ref() is not body:
            return None
    owner = memory.lineage if name in SHARED_ANSWERS else None
    key = (
        memory.token if owner is None else owner.token,
        _patch_digest(memory, ()),
        None,
        ROUND_FIT_EVALUATIONS,
    )
    with _MEMORY_LOCK:
        answers = _SUPPORT_CACHE.get(name)
        if answers is None or key not in answers:
            return None
        answers.move_to_end(key)
        return answers[key]


#: Die Fragen, deren Antwort auch ein anderer Körper geben darf — derselbe
#: Fleck, Bit für Bit gelesen (RM-261, :func:`_by_geometry`).
#:
#: **Warum es sie braucht.** :func:`remembered` merkt je Körper, und nach
#: jedem Schritt ist der Körper neu: Die Vollerkennung, die §21.1 nach jedem
#: Schritt verlangt, passte am Gartenschlauchhalter (392 532 Dreiecke) je
#: übernommenem Schritt rund 2 700 Kegel, 1 900 Kugeln, 1 700 Ringe und
#: 2 600 Zylinder neu ein — 22 der 30 Sekunden —, obwohl eine Boolesche jedes
#: Dreieck, das sie nicht schneidet, bitgleich übernimmt
#: (``geom.attributes.in_source_layout``). Ein Fleck, dessen Lesung Bit für
#: Bit dieselbe ist, bekommt dieselbe Antwort; gerechnet wird, was neu ist.
#:
#: **Wer hierher gehört**, liest den Körper nur über die Stützpunktlesung
#: (:class:`_SurfaceSupport`, ihr Abdruck deckt jedes Feld und die Dreiecke
#: des Flecks), die Toleranz aus der Körperdiagonale und den Fit, den ein
#: Nachweis prüft — und nichts sonst; die Toleranz bekommt die Rechnung vom
#: Aufrufer, der sie auch in den Schlüssel legt. Was die Rümpfe darüber
#: hinaus vom Körper lesen, enthält die Lesung schon: Normalen und Flächen
#: des Flecks sind ihre Felder, Mitten und Ecken der Dreiecke folgen aus den
#: Dreiecken, und die Ecken des Flecks in der Folge ihrer Nummern gehen allein
#: in ein Minimum oder Maximum ein, das von der Folge nicht abhängt. Wer eine
#: Frage hinzunimmt, prüft ihren Rumpf auf genau das. Eine Antwort ist dabei
#: immer ein unveränderlicher Fit oder ein Wahrheitswert — keine
#: Dreiecksnummer, kein Feld.
GEOMETRY_KEYED_ANSWERS: Final[frozenset[str]] = frozenset(
    {
        "fit_cone",
        "fit_cylinder",
        "fit_sphere",
        "fit_torus",
        "_cone_is_recognisable",
        "_sphere_is_recognisable",
        "_torus_is_recognisable",
    }
)

#: Die Fragen, die über die Körpergrenze unter dem Fleckabdruck antworten
#: (RM-592, :func:`_patch_print`): der Abdruck der Stützpunktlesung und die
#: tangentiale Trennung. Was eine davon vom Körper liest, steht an ihrer Stelle
#: (:func:`_support_handle`, :func:`_tangential_pieces`); ihre Antwort ist ein
#: Abdruck oder Lagen im Fleck, nie eine Dreiecksnummer.
PRINT_KEYED_ANSWERS: Final[frozenset[str]] = frozenset(
    {"support_digest", "tangential_pieces", "classified"}
)

#: Die Antworten über die Körpergrenze, je Frage unter ihrem Inhaltsschlüssel.
#: Dieselbe Grenze wie jede kleine Frage (:data:`CACHE_LIMIT_PER_QUESTION`),
#: und dieselbe Lebensdauer wie :func:`remembered`: Eine Antwort gehört den
#: Abstammungen, die sie gerechnet oder gelesen haben
#: (:attr:`_Lineage.geometric`), und geht mit der letzten.
_BY_GEOMETRY: dict[str, OrderedDict[bytes, Any]] = {}

#: Je Antwort über die Körpergrenze, wie viele lebende Abstammungen sie halten.
_GEOMETRY_HOLDERS: dict[tuple[str, bytes], int] = {}


def _by_geometry(
    name: str,
    body: trimesh.Trimesh,
    support: _SurfaceSupport | _SupportPrint,
    compute: Callable[[], Any],
    *read: Any,
) -> Any:
    """Dieselbe Frage an denselben Fleck — auch an einem anderen Körper (RM-261).

    Der Schlüssel ist der Abdruck der Stützpunktlesung (``support.digest``),
    was die Frage darüber hinaus liest (``read``: der Fit, den ein Nachweis
    prüft, und die Toleranz aus der Körperdiagonale — der Aufrufer rechnet sie
    einmal und gibt sie der Rechnung mit, damit Schlüssel und Rechnung
    dieselbe Zahl sehen) und die Löserbudgets — **Bit für Bit, ohne
    Toleranz**: Zwei Flecken, deren Lesung sich in der letzten Stelle einer
    Normale unterscheidet, sind zwei Fragen. Was :data:`GEOMETRY_KEYED_ANSWERS`
    für eine Frage verlangt, steht dort. Gerechnet wird außerhalb des
    Schlosses, wie in :func:`remembered`. ``body`` bestimmt nur, wer die
    Antwort mithält (:attr:`_Lineage.geometric`). ``support`` darf ein
    Fleckabdruck sein (:class:`_SupportPrint`): Der Schlüssel braucht nur den
    Abdruck der Lesung, die Rechnung liest sie erst, wenn sie rechnet.
    """
    if not _ACROSS_BODIES[0]:
        return compute()
    return _across(name, body, _geometry_key(support, *read), compute)


def _across(name: str, body: trimesh.Trimesh, key: bytes, compute: Callable[[], Any]) -> Any:
    """Die Ablage über die Körpergrenze unter einem fertigen Schlüssel (:func:`_by_geometry`).

    Gerechnet wird außerhalb des Schlosses; ein Abbruch in ``compute`` legt
    nichts ab. ``body`` hält die Antwort mit (:attr:`_Lineage.geometric`).
    """
    with _MEMORY_LOCK:
        lineage = _memory_of(body).lineage
        answers = _BY_GEOMETRY.setdefault(name, OrderedDict())
        if key in answers:
            answers.move_to_end(key)
            _held_geometric(lineage, name, key)
            return answers[key]
    value = compute()
    _keep_across(name, body, key, value)
    return value


def _keep_across(name: str, body: trimesh.Trimesh, key: bytes, value: Any) -> None:
    """Eine fertige Antwort über die Körpergrenze ablegen, gehalten von ``body``."""
    with _MEMORY_LOCK:
        lineage = _memory_of(body).lineage
        answers = _BY_GEOMETRY.setdefault(name, OrderedDict())
        answers[key] = value
        answers.move_to_end(key)
        _held_geometric(lineage, name, key)
        while len(answers) > CACHE_LIMIT_PER_QUESTION:
            answers.popitem(last=False)


def _known_across(name: str, body: trimesh.Trimesh, key: bytes) -> Any:
    """Die abgelegte Antwort über die Körpergrenze — oder :data:`_UNKNOWN`, ohne zu rechnen."""
    if not _ACROSS_BODIES[0]:
        return _UNKNOWN
    with _MEMORY_LOCK:
        answers = _BY_GEOMETRY.get(name)
        if answers is None or key not in answers:
            return _UNKNOWN
        answers.move_to_end(key)
        _held_geometric(_memory_of(body).lineage, name, key)
        return answers[key]


#: Ob Fragen über die Körpergrenze antworten (RM-261, RM-592). Abschalten kann
#: es nur der Testhaken :func:`remember_across_bodies` — für Messbank und Suite,
#: kein Schalter für Kunden (Konzept §9.4).
_ACROSS_BODIES: list[bool] = [True]


def remember_across_bodies(enabled: bool) -> bool:
    """Testhaken: das Gedächtnis über die Körpergrenze an- oder abschalten.

    Abgeschaltet rechnet jede Frage an jedem Körper neu, wie die Vollerkennung
    ohne Merker — die Gegenseite, gegen die Messbank und Suite Bit für Bit
    vergleichen. Zurück kommt der vorige Zustand.
    """
    with _MEMORY_LOCK:
        before = _ACROSS_BODIES[0]
        _ACROSS_BODIES[0] = bool(enabled)
    return before


def _geometry_key(support: _SurfaceSupport | _SupportPrint, *read: Any) -> bytes:
    """Der Schlüssel von :func:`_by_geometry`: Lesung, was die Frage sonst liest, Löserbudgets."""
    return hashlib.blake2b(
        support.digest + _exact_bytes((read, ROUND_FIT_EVALUATIONS, FIT_SOLVER_POINTS)),
        digest_size=16,
    ).digest()


def _answered_by_geometry(name: str, support: _SurfaceSupport | _SupportPrint, *read: Any) -> bool:
    """Ob :func:`_by_geometry` diese Frage an dieser Lesung schon beantwortet hat, ohne Rechnung."""
    if not _ACROSS_BODIES[0]:
        return False
    key = _geometry_key(support, *read)
    with _MEMORY_LOCK:
        answers = _BY_GEOMETRY.get(name)
        return answers is not None and key in answers


def _held_geometric(lineage: _Lineage, name: str, key: bytes) -> None:
    """Die Abstammung hält diese Antwort mit — nur unter dem Schloss."""
    entry = (name, key)
    if entry not in lineage.geometric:
        lineage.geometric.add(entry)
        _GEOMETRY_HOLDERS[entry] = _GEOMETRY_HOLDERS.get(entry, 0) + 1


def _release_geometric(held: set[tuple[str, bytes]]) -> None:
    """Eine gestorbene Abstammung lässt ihre Antworten los; ohne Halter gehen sie.

    Nur unter dem Schloss. Eine Antwort, die die Grenze schon verdrängt hat,
    fehlt hier einfach.
    """
    for entry in held:
        count = _GEOMETRY_HOLDERS.get(entry, 0) - 1
        if count > 0:
            _GEOMETRY_HOLDERS[entry] = count
            continue
        _GEOMETRY_HOLDERS.pop(entry, None)
        answers = _BY_GEOMETRY.get(entry[0])
        if answers is not None:
            answers.pop(entry[1], None)
    held.clear()


def _exact_bytes(value: Any) -> bytes:
    """Ein Wert als Bytes, Bit für Bit — auch ``-0.0`` und ``0.0`` sind zwei.

    Für die Schlüssel von :func:`_by_geometry`: Zahlen, Wahrheitswerte,
    ``None``, Texte, Tupel und die unveränderlichen Fits (ihre Felder in ihrer
    Reihenfolge). Ein Vergleich über ``==`` hielte ``-0.0`` und ``0.0`` für
    gleich, und die Rechnung dahinter muss es nicht.
    """
    if value is None:
        return b"N"
    if isinstance(value, bool):
        return b"T" if value else b"F"
    if isinstance(value, int):
        return b"I" + str(value).encode("ascii") + b";"
    if isinstance(value, float):
        return b"D" + struct.pack("<d", value)
    if isinstance(value, str):
        return b"S" + value.encode("utf-8") + b";"
    if isinstance(value, tuple):
        return b"(" + b"".join(_exact_bytes(item) for item in value) + b")"
    fields = getattr(value, "__dataclass_fields__", None)
    if fields is None:
        raise TypeError(f"no exact key for {type(value).__name__}")
    parts = b"".join(_exact_bytes(getattr(value, field_name)) for field_name in fields)
    return type(value).__name__.encode("ascii") + b"{" + parts + b"}"


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
    if _face_count(body, patch) < MIN_PATCH_FACES:
        return None
    # **In einer Runde des Stapels liegt die Lesung schon vor** (B1 des
    # Reviews): :func:`_screened_fits` liest jeden Fleck der Runde vorab, der
    # Merker hält davon aber nur :data:`SUPPORT_CACHE_LIMIT` — ohne diese
    # Zeile las ``classify`` jede Lesung ein zweites Mal (Freiform der
    # Leistungstests 3 896 statt 1 949 Lesungen).
    screened = _SCREENED.get()
    if screened is not None and screened.body is body:
        known = screened.supports.get(_patch_key(patch))
        if isinstance(known, _SurfaceSupport):
            return known
    return _remembered_support(body, patch, check_cancelled)


def _remembered_support(
    body: trimesh.Trimesh,
    patch: list[int],
    check_cancelled: Callable[[], None] | None = None,
) -> _SurfaceSupport | None:
    """Die Lesung aus dem Merker des Körpers oder gerechnet — ohne den Stapel zu fragen.

    :class:`_SupportPrint` liest hier: Der Stapel hält für denselben Fleck
    womöglich genau diesen Abdruck, und ihn nach der Lesung zu fragen, fragte
    den Abdruck nach sich selbst (am Stand von P2 ein ``RecursionError`` beim
    Vereinigen, Messbank A1).
    """
    support: _SurfaceSupport | None = remembered(
        "support",
        body,
        patch,
        lambda: _read_surface_support(body, patch, check_cancelled),
        check_cancelled=check_cancelled,
    )
    return support


class _SupportPrint:
    """Eine Stützpunktlesung, von der nur ihr Abdruck feststeht (RM-592, Konzept §5.2, G1).

    Hat ein früherer Körper denselben Fleck gelesen — derselbe Fleckabdruck
    (:func:`_patch_print`) und dieselben Körperzahlen —, ist die Lesung Bit für
    Bit dieselbe, also auch ihr Abdruck (``digest``). Der reicht als Schlüssel
    jeder Frage über die Körpergrenze (:func:`_by_geometry`); die Felder liest
    erst, wer wirklich rechnet (:meth:`read`), und dann einmal.
    """

    __slots__ = ("_body", "_check_cancelled", "_patch", "_support", "digest")

    def __init__(
        self,
        body: trimesh.Trimesh,
        patch: list[int],
        digest: bytes,
        check_cancelled: Callable[[], None] | None,
    ) -> None:
        self._body = body
        self._patch = patch
        self.digest = digest
        self._check_cancelled = check_cancelled
        self._support: _SurfaceSupport | None = None

    def read(self) -> _SurfaceSupport:
        """Die Lesung selbst — am selben Körper aus seinem Merker (:func:`_surface_support`)."""
        if self._support is None:
            support = _remembered_support(self._body, self._patch, self._check_cancelled)
            if support is None:
                from app.core.errors import InternalError

                raise InternalError(detail="a remembered surface reading vanished")
            self._support = support
        return self._support


#: Unter diesem Namen hält :func:`_across` je Fleckabdruck und Körperzahlen den
#: Abdruck der Lesung — ``None``, wo die Lesung nichts ergab.
_SUPPORT_DIGEST: Final = "support_digest"


def _support_handle(
    body: trimesh.Trimesh,
    patch: list[int],
    check_cancelled: Callable[[], None] | None = None,
) -> _SurfaceSupport | _SupportPrint | None:
    """Die Lesung eines Flecks für eine Frage über die Körpergrenze — gelesen nur, wenn nötig.

    Dieselbe Antwort wie :func:`_surface_support`, nur kann sie ein Abdruck
    sein (:class:`_SupportPrint`): Kennt das Gedächtnis den Fleckabdruck samt
    Körperzahlen schon, steht der Abdruck der Lesung fest, ohne sie zu rechnen —
    am Spiderman die Hälfte der Erkennung nach einem Schritt. ``None`` heißt
    wie dort: keine Lesung.

    **Was die Lesung vom Körper liest** (:func:`_read_surface_support`): die
    Ecken, Normalen und Flächen der Dreiecke des Flecks, welche Ecken dieselben
    sind und ihre Folge, die Kantennachbarn im Fleck (:func:`_fan_arcs`), den
    Ursprung je Dreieck (:func:`_face_count`), ob das Netz dicht und gleich
    umlaufend ist und ob es deckungsgleiche Ecken trägt — und deren Rang folgt
    allein den Koordinaten (:func:`vertex_rank`). Normalen und Flächen rechnet
    trimesh aus den Ecken; der Abdruck trägt die Ecken. Das sind
    :func:`_patch_print` und die drei Körperzahlen hier.
    """
    if check_cancelled is not None:
        check_cancelled()
    if _face_count(body, patch) < MIN_PATCH_FACES:
        return None
    screened = _SCREENED.get()
    if screened is not None and screened.body is body:
        known = screened.supports.get(_patch_key(patch))
        if known is not None:
            return known
    if not _ACROSS_BODIES[0]:
        return _surface_support(body, patch, check_cancelled)
    key = hashlib.blake2b(
        _patch_print(body, patch)
        + _body_numbers(
            dicht=bool(body.is_watertight),
            umlauf=bool(body.is_winding_consistent),
            deckungsgleich=_coincident_vertices(body),
        ),
        digest_size=16,
    ).digest()
    digest = _known_across(_SUPPORT_DIGEST, body, key)
    if digest is None:
        return None
    if digest is not _UNKNOWN:
        return _SupportPrint(body, patch, digest, check_cancelled)
    support = _surface_support(body, patch, check_cancelled)
    _keep_across(_SUPPORT_DIGEST, body, key, None if support is None else support.digest)
    return support


#: Die Teile des Fleckabdrucks (Konzept §5.2), je mit seinem Namen. Die
#: Messbank lässt für ihre Gegenprobe einen davon weg (``folge.py --weglassen``).
PATCH_PRINT_PARTS: Final = (
    "ecken",
    "eckennummern",
    "ring",
    "ursprung",
    "normalen",
    "flaechen",
    "winkel",
)

#: Die Körperzahlen, die eine Frage liest und die der Aufrufer mitgibt (§5.2).
BODY_NUMBERS: Final = ("dicht", "umlauf", "deckungsgleich", "diagonale")


def _body_numbers(**numbers: Any) -> bytes:
    """Körperzahlen für einen Schlüssel, Bit für Bit und mit ihrem Namen."""
    return _exact_bytes(
        tuple((name, numbers[name]) for name in sorted(numbers) if name not in _LEFT_OUT)
    )


def _patch_print(body: trimesh.Trimesh, patch: Sequence[int], *, seams: bool = False) -> bytes:
    """Der Fleckabdruck (Konzept §5.2), einmal je Körper und Fleck gerechnet.

    Ändert sich ein Dreieck im Fleck oder in seinem ersten Nachbarring, ändert
    sich der Abdruck, und jede Frage an diesen Fleck rechnet. ``seams`` nimmt
    die Winkel der inneren Nähte dazu (:func:`_tangential_pieces`).
    """
    printed: bytes = remembered(
        "patch_print",
        body,
        patch,
        lambda: _print_of(_patch_print_parts(body, patch, seams=seams)),
        extra=seams,
    )
    return printed


def _print_of(parts: Sequence[tuple[str, bytes]]) -> bytes:
    """Die Teile eines Fleckabdrucks als sechzehn Bytes, jedes mit Namen und Länge."""
    digest = hashlib.blake2b(digest_size=16)
    for name, data in parts:
        digest.update(name.encode("ascii"))
        digest.update(len(data).to_bytes(8, "little"))
        digest.update(data)
    return digest.digest()


def _patch_print_parts(
    body: trimesh.Trimesh, patch: Sequence[int], *, seams: bool = False
) -> list[tuple[str, bytes]]:
    """Was eine Frage an einen Fleck vom Körper liest, als Bytes ohne Arithmetik.

    1. ``ecken``: die Ecken seiner Dreiecke in Fleckfolge und Eckenfolge;
    2. ``eckennummern``: welche Ecken dieselben sind, nummeriert in der Folge
       ihrer Nummern im Körper (``np.unique``, wie die Lesung sie ordnet) —
       darüber auch, welche Kanten zwei Dreiecke teilen und in welcher Folge
       die Kanten des Flecks stehen (``face_adjacency`` ordnet nach Ecken);
    3. ``ring``: je Dreieck seine Kantennachbarn — die Lage im Fleck, sonst
       „außen“; eine Kante ohne Nachbarn (offen oder mit drei Dreiecken) trägt
       keinen;
    4. ``ursprung``: welche Dreiecke vor *Kanten verfeinern* eines waren;
    5. ``normalen`` und ``flaechen``: Normale und Inhalt jedes Dreiecks, wie der
       Körper sie hält — eine starre Bewegung trägt beide vom Quellnetz mit
       (``geom.transform._carry_cache``), sie folgen dann nicht Bit für Bit
       den Ecken;
    6. mit ``seams``: ``winkel``, der Knickwinkel jeder Naht zu einem Nachbarn
       im Fleck, in der Folge des Rings — ebenso mitgetragen.

    Nicht darin steht die Folge der Dreiecksnummern: Lesung und Trennung lesen
    den Fleck in seiner Folge und in der Ordnung des Körpers, nie nach Nummern
    (:func:`_tangential_cylinders`, RM-210).
    """
    (parts,) = _patch_prints_parts(body, [patch], seams=seams)
    return parts


def _patch_prints(
    body: trimesh.Trimesh, patches: Sequence[Sequence[int]], *, seams: bool = False
) -> None:
    """Die Fleckabdrücke vieler Flecken in einem Zug — abgelegt, wo :func:`_patch_print` liest.

    Je Fleck einzeln gerechnet, kostete der Abdruck am Eiffelturm nach einer
    Bohrung 1,1 s für 6 111 Flecken, mehr als die Lesungen, die er erspart:
    ein Dutzend kleine numpy-Aufrufe je Fleck. Dieselben Bytes wie einzeln
    (:func:`_patch_print_parts` ruft diese Rechnung mit einem Fleck).
    """
    if not _ACROSS_BODIES[0]:
        return
    chosen = [patch for patch in patches if len(patch)]
    if not chosen:
        return
    for patch, parts in zip(chosen, _patch_prints_parts(body, chosen, seams=seams), strict=True):
        remembered("patch_print", body, patch, _given(_print_of(parts)), extra=seams)


def _given(value: bytes) -> Callable[[], bytes]:
    """Eine schon gerechnete Antwort als Rechnung für :func:`remembered`."""
    return lambda: value


def _patch_prints_parts(
    body: trimesh.Trimesh, patches: Sequence[Sequence[int]], *, seams: bool = False
) -> list[list[tuple[str, bytes]]]:
    """Die Teile der Fleckabdrücke (:func:`_patch_print_parts`) für viele Flecken zugleich.

    Gerechnet über alle Flecken aneinandergehängt, je Fleck nur geschnitten:
    welche Ecken dieselben sind und die Lage der Nachbarn im Fleck über einen
    Schlüssel aus Fleck und Nummer, sortiert einmal für alle.
    """
    sizes = np.fromiter((len(patch) for patch in patches), dtype=np.int64, count=len(patches))
    index = np.fromiter(
        itertools.chain.from_iterable(patches), dtype=np.int64, count=int(sizes.sum())
    )
    starts = np.r_[0, np.cumsum(sizes)]
    segment = np.repeat(np.arange(len(patches), dtype=np.int64), sizes)
    position = np.arange(len(index), dtype=np.int64) - starts[segment]
    faces = np.asarray(body.faces, dtype=np.int64)[index]
    corners = np.asarray(body.vertices, dtype=np.float64)[faces]
    # Welche Ecken dieselben sind, je Fleck in der Folge ihrer Nummern — der
    # Schlüssel Fleck·Ecken+Ecke sortiert erst nach Fleck, dann nach Ecke.
    vertex_count = max(len(body.vertices), 1)
    corner_keys = np.repeat(segment, 3) * vertex_count + faces.ravel()
    _distinct, corner_rank = np.unique(corner_keys, return_inverse=True)
    corner_rank = np.asarray(corner_rank, dtype=np.int64).ravel()
    first_rank = np.full(len(patches), np.iinfo(np.int64).max, dtype=np.int64)
    np.minimum.at(first_rank, np.repeat(segment, 3), corner_rank)
    local = corner_rank - np.repeat(first_rank[segment], 3)
    normals = np.asarray(body.face_normals, dtype=np.float64)[index]
    areas = np.asarray(body.area_faces, dtype=np.float64)[index]
    neighbours, pair_rows = _neighbour_index(body)
    ring_rows: np.ndarray | None = None
    angle_rows: np.ndarray | None = None
    widths = np.zeros(len(patches), dtype=np.int64)
    if len(index) and neighbours.shape[1]:
        face_count = max(len(body.faces), 1)
        own_keys = segment * face_count + index
        order = np.argsort(own_keys, kind="stable")
        ranked = own_keys[order]
        around = neighbours[index]
        wanted = segment[:, None] * face_count + np.maximum(around, 0)
        spot = np.minimum(np.searchsorted(ranked, wanted), len(ranked) - 1)
        inside = (around >= 0) & (ranked[spot] == wanted)
        place = np.where(inside, position[order[spot]], np.where(around >= 0, -1, -2))
        ranking = np.argsort(-place, axis=1, kind="stable")
        ring_rows = np.take_along_axis(place, ranking, axis=1)
        counts = (ring_rows > -2).sum(axis=1)
        widths = np.maximum.reduceat(counts, starts[:-1]) if len(counts) else widths
        if seams:
            angles = np.asarray(body.face_adjacency_angles, dtype=np.float64)[
                np.maximum(pair_rows[index], 0)
            ]
            angle_rows = np.take_along_axis(np.where(inside, angles, 0.0), ranking, axis=1)
    units = refined_units(body)
    pattern: np.ndarray | None = None
    if units is not None:
        own_units = np.asarray(units, dtype=np.int64)[index]
        kept = own_units >= 0
        pattern = np.full(len(index), -1, dtype=np.int64)
        if kept.any():
            unit_count = int(own_units.max()) + 1
            unit_keys = segment[kept] * unit_count + own_units[kept]
            _units, unit_rank = np.unique(unit_keys, return_inverse=True)
            unit_rank = np.asarray(unit_rank, dtype=np.int64).ravel()
            first_unit = np.full(len(patches), np.iinfo(np.int64).max, dtype=np.int64)
            np.minimum.at(first_unit, segment[kept], unit_rank)
            pattern[kept] = unit_rank - first_unit[segment[kept]]
    result: list[list[tuple[str, bytes]]] = []
    for number in range(len(patches)):
        low, high = int(starts[number]), int(starts[number + 1])
        parts = [
            ("ecken", np.ascontiguousarray(corners[low:high]).tobytes()),
            ("eckennummern", np.ascontiguousarray(local[3 * low : 3 * high]).tobytes()),
        ]
        if ring_rows is not None and high > low:
            width = int(widths[number])
            parts.append(("ring", np.ascontiguousarray(ring_rows[low:high, :width]).tobytes()))
            if angle_rows is not None:
                parts.append(
                    ("winkel", np.ascontiguousarray(angle_rows[low:high, :width]).tobytes())
                )
        else:
            parts.append(("ring", b""))
        parts.append(("normalen", np.ascontiguousarray(normals[low:high]).tobytes()))
        parts.append(("flaechen", np.ascontiguousarray(areas[low:high]).tobytes()))
        if pattern is not None:
            parts.append(("ursprung", np.ascontiguousarray(pattern[low:high]).tobytes()))
        result.append([(name, data) for name, data in parts if name not in _LEFT_OUT])
    return result


#: Die Teile, die die Gegenprobe der Messbank weglässt — im Betrieb immer leer.
_LEFT_OUT: set[str] = set()


def _coincident_vertices(body: trimesh.Trimesh) -> bool:
    """Ob zwei Ecken des Netzes dieselben Koordinaten tragen — einmal je Körper.

    Eine ungeschweißte STL schreibt jedes Dreieck mit eigenen Ecken; dann
    fallen deckungsgleiche Punkte in der Lesung zusammen (:func:`_read_surface_support`).
    Ein geschweißtes Netz hat keine, und die Frage kostet einmal so viel wie
    eine Lesung des ganzen Körpers, nicht einmal je Fleck — **deshalb liegt
    die Antwort neben dem Rang im Cache des Netzes**. Bis zur Durchsicht 0.5.1
    stand der Satz hier, und die Rechnung lief trotzdem je Fleck: ein Maximum
    über alle Ecken, am Meshy-Murmelbrett 63 509-mal und 68 s von 866 unter
    dem Profiler (erkennung-05).
    """
    if _COINCIDENT_KEY in body._cache:
        known: bool = body._cache[_COINCIDENT_KEY]
        return known
    canonical = vertex_rank(body)
    answer = bool(int(canonical.max()) + 1 < len(canonical)) if len(canonical) else False
    body._cache[_COINCIDENT_KEY] = answer
    return answer


#: Unter diesem Schlüssel hält der Cache von ``trimesh`` die Antwort von
#: :func:`_coincident_vertices` — sie verfällt mit der Geometrie wie der Rang.
_COINCIDENT_KEY: Final = "solidon_coincident_vertices"


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
    # Die benutzten Ecken eines großen Flecks ohne Sortierung: Markieren,
    # zählen, umnummerieren — an der Ikosphäre zehn statt fünfzig
    # Millisekunden für 983 040 Ecken. Ein kleiner Fleck wird sortiert
    # (:data:`SORTED_CORNERS_SHARE`); beide Wege geben dieselben Ecken in
    # derselben aufsteigenden Folge.
    flat_corners = np.asarray(body.faces)[patch].astype(np.int64).ravel()
    if len(flat_corners) < len(body.vertices) * SORTED_CORNERS_SHARE:
        used, corner_of = np.unique(flat_corners, return_inverse=True)
    else:
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
        # Zeilen zu sortieren (:func:`vertex_rank`). Vertreten wird
        # jeder Punkt von seiner kleinsten benutzten Ecke — ``used`` steigt,
        # also ist das ihr erstes Vorkommen.
        canonical = vertex_rank(body)
        _distinct, first_seen, vertex_of = np.unique(
            canonical[used], return_index=True, return_inverse=True
        )
        points = all_vertices[used[first_seen]]
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
    two_planes = ridges & ~round_corners
    if bool(two_planes.any()):
        # STL-Rundung gibt den Dreiecken derselben Facette geringfügig
        # verschiedene Normalen. Das erste gelesene Dreieck bestimmte deshalb
        # eine andere Mantellinie als das letzte (RM-210). Beide belegten
        # Facettenfamilien tragen ihre flächengewichtete Normale bei.
        other_agreement = np.einsum("ij,ij->i", repeated, second[reverse])
        family = agreement >= other_agreement
        grouped = reverse * 2 + (~family).astype(np.intp)
        sums = np.zeros((len(points) * 2, 3))
        np.add.at(sums, grouped, repeated * np.repeat(areas, 3)[:, None])
        lengths = np.linalg.norm(sums, axis=1)
        sums /= np.where(lengths > EPS_GEOM**2, lengths, 1.0)[:, None]
        pairs = sums.reshape(-1, 2, 3)
        directions[two_planes] = np.cross(pairs[two_planes, 0], pairs[two_planes, 1])
    lengths = np.linalg.norm(directions, axis=1)
    directions /= np.where(lengths > EPS_GEOM, lengths, 1.0)[:, None]
    if check_cancelled is not None:
        check_cancelled()
    return _SurfaceSupport(
        points,
        corners,
        normals,
        triangles.mean(axis=1),
        areas,
        round_corners,
        ridges,
        directions,
        _arrays_digest(
            triangles, points, corners, normals, areas, round_corners, ridges, directions
        ),
    )


def _arrays_digest(*arrays: np.ndarray) -> bytes:
    """Der Abdruck von Feldern, Bit für Bit: Art, Form und Inhalt jedes einzelnen."""
    digest = hashlib.blake2b(digest_size=16)
    for array in arrays:
        plain = np.ascontiguousarray(array)
        digest.update(plain.dtype.str.encode("ascii"))
        digest.update(repr(plain.shape).encode("ascii"))
        digest.update(plain.tobytes())
    return digest.digest()


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
    selected: np.ndarray = support.round_corners | (
        _ridge_endpoints(support, check_cancelled) & (off_line <= tolerance)
    )
    if int(selected.sum()) >= 6:
        return selected
    selected |= _circular_rim_points(support, check_cancelled)
    return selected


def _circular_rim_points(
    support: _SurfaceSupport, check_cancelled: Callable[[], None] | None = None
) -> np.ndarray:
    """Originale Kreisbögen am Fleckrand als eigenständiger Maßbeleg.

    An einer kurzen Fase können die Facettenlinien wegen der STL-Rundung
    keine gemeinsame Spitze belegen. Ein erhaltener Kreisrand trägt seine
    Maße trotzdem. Gezählt werden nur wirkliche Knicke einer zusammenhängenden
    Randkette, deren sämtliche Ecken bis auf Schweißtoleranz in einer Ebene
    und auf einem Kreis liegen. Kollineare Teilungspunkte liefern kein neues
    Maß. Die übrige Haut und ihre Normalen prüfen weiterhin den ganzen Kegel.
    """
    points = support.points
    selected = np.zeros(len(points), dtype=bool)
    raw = np.sort(support.corners[:, ((0, 1), (1, 2), (2, 0))].reshape(-1, 2), axis=1)
    edges, counts = np.unique(raw, axis=0, return_counts=True)
    edges = edges[counts == 1]
    if not len(edges):
        return selected
    directions = points[edges[:, 1]] - points[edges[:, 0]]
    directions /= np.maximum(np.linalg.norm(directions, axis=1), EPS_GEOM)[:, None]
    adjacent: dict[int, list[int]] = {}
    for number, (one, other) in enumerate(edges):
        if check_cancelled is not None and number % FIT_SCAN_BLOCK == 0:
            check_cancelled()
        adjacent.setdefault(int(one), []).append(number)
        adjacent.setdefault(int(other), []).append(number)
    joins = []
    corners = np.ones(len(points), dtype=bool)
    smooth = units.exact_cos_degrees(CURVATURE_LIMIT)
    straight = units.exact_cos_degrees(EPS_ANGLE)
    for at, incident in adjacent.items():
        if len(incident) != 2:
            continue
        one, other = incident
        agreement = abs(float(directions[one] @ directions[other]))
        if agreement >= smooth:
            joins.append((one, other))
        if agreement >= straight:
            corners[at] = False
    if not joins:
        return selected
    groups = trimesh.graph.connected_components(
        np.asarray(joins), nodes=np.arange(len(edges)), min_len=3, engine="scipy"
    )
    tolerance = weld_tolerance(float(np.linalg.norm(np.ptp(points, axis=0))))
    for group in groups:
        if check_cancelled is not None:
            check_cancelled()
        indices = np.unique(edges[group])
        indices = indices[corners[indices]]
        # Drei Punkte bestimmen bereits einen Kreis; der vierte prüft ihn.
        if len(indices) < 4:
            continue
        local = points[indices] - points[indices[0]]
        along = local[int(np.argmax(np.einsum("ij,ij->i", local, local)))]
        crossed = np.cross(along, local)
        normal = crossed[int(np.argmax(np.einsum("ij,ij->i", crossed, crossed)))]
        length = float(np.linalg.norm(normal))
        if length <= EPS_GEOM:
            continue
        normal /= length
        if float(np.abs(local @ normal).max()) > tolerance:
            continue
        first, second = _plane_basis(normal)
        flat = np.column_stack((local @ first, local @ second))
        centre, radius = _fit_circle(flat)
        if radius <= EPS_GEOM:
            continue
        error = np.abs(np.linalg.norm(flat - centre, axis=1) - radius)
        if float(error.max()) <= tolerance:
            selected[indices] = True
    selected &= support.round_corners | support.ridges
    return selected


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
    *,
    spent: list[bool] | None = None,
) -> np.ndarray | None:
    """Begrenzt geometrisch verfeinern und numerisch unbestimmte Maße verwerfen.

    **Die Ableitung kommt geschlossen, wo es sie gibt.** Ohne ``jacobian``
    schätzt der Löser sie aus Differenzen und ruft dafür je Schritt so viele
    Residuen, wie es Größen gibt — an der Freiform mit 200 000 Dreiecken
    14 870 Jacobi-Schätzungen für 1 263 Verfeinerungen, mehr als die Hälfte
    ihrer Zeit (gemessen am 21.09.2026). Kegel, Kugel und Ring bringen ihre
    Ableitung deshalb mit; das Ergebnis ist dasselbe Minimum.

    ``spent`` bekommt ein ``True``, wenn der Lauf sein Budget ausschöpfte —
    die eine Absage, nach der ein zweiter Start lohnt (:func:`_cone_from_plan`).
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

    # **Mit Ableitung rechnet der Nachbau, Schritt für Schritt wie SciPy**
    # (:func:`refine.solve`, bitgleich): Die Hülle um ``least_squares`` —
    # Argumentprüfung, ``VectorFunction``, ``OptimizeResult`` — kostete an der
    # Kumiko-Schale ein Fünftel der Löserzeit. Ohne Ableitung schätzt SciPy sie
    # aus Differenzen wie bisher.
    result: Any
    if jacobian is None:
        result = least_squares(
            checked,
            initial,
            jac="2-point",
            ftol=ROUND_FIT_PRECISION,
            xtol=ROUND_FIT_PRECISION,
            gtol=ROUND_FIT_PRECISION,
            max_nfev=ROUND_FIT_EVALUATIONS,
        )
    else:
        result = refine.solve(
            checked,
            checked_jacobian,
            initial,
            precision=ROUND_FIT_PRECISION,
            evaluations=ROUND_FIT_EVALUATIONS,
        )
    if spent is not None and result.nfev >= ROUND_FIT_EVALUATIONS:
        spent.append(True)
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


#: Was der Stapel einer Runde über ihre Kegel- und Ringläufe weiß (RM-209):
#: je Einpassung und Lesung (``support.digest``, beim Kegel dazu die
#: Linientoleranz) der vorbereitete Plan und ob der Löserlauf sein Budget
#: sicher ausschöpft. Es gilt nur, solange die Runde läuft (:func:`_screening`),
#: und nur im Faden, der sie rechnet — eine Kopie für einen Nebenfaden rechnet
#: ohne und bekommt dieselben Antworten.
@dataclass(frozen=True, slots=True, eq=False)
class _Screened:
    """Das Wissen einer Runde: je Einpassung Plan und Urteil, je Fleck Lesung und Kennzahl.

    ``fits`` ist nach Einpassung und Lesung geschlüsselt (``support.digest``,
    beim Kegel dazu die Linientoleranz), ``supports`` und ``shapes`` nach dem
    Abdruck der Dreiecksliste (:func:`_patch_key`) — für ``body`` und nur für
    ihn. Die Lesungen hält der Stapel ohnehin, solange die Runde läuft: Jeder
    Plan trägt die seine. Wo das Gedächtnis jede Frage an einen Fleck schon
    beantwortet hat, steht statt der Lesung nur ihr Abdruck (:class:`_SupportPrint`).
    """

    body: trimesh.Trimesh
    fits: dict[tuple[Any, ...], tuple[Any, bool]]
    supports: dict[bytes, _SurfaceSupport | _SupportPrint]
    shapes: dict[bytes, tuple[Any, ...] | None]


_SCREENED: ContextVar[_Screened | None] = ContextVar("solidon_screened_fits", default=None)

#: Steht für „nicht im Wissen" — ``None`` ist dort eine Antwort.
_UNKNOWN: Final = object()


def _patch_key(patch: Sequence[int]) -> bytes:
    """Der Abdruck einer Dreiecksliste für das Wissen des Stapels, nur von ihrem Inhalt abhängig."""
    return hashlib.blake2b(np.asarray(patch, dtype=np.int64).tobytes(), digest_size=16).digest()


#: Welcher Anteil einer Runde am Balken auf den Stapel entfällt. Gemessen am
#: Meshy-Murmelbrett und an der Kumiko-Schale — nur fürs Anzeigen, keine Toleranz.
SCREEN_SHARE: Final = 0.2


def _screened_fits(
    body: trimesh.Trimesh,
    patches: Sequence[list[int]],
    *,
    shapes: set[tuple[Any, ...]] | None = None,
    check_cancelled: Callable[[], None] | None = None,
    share: _Share = _UNHEARD,
) -> _Screened:
    """Die Kegel- und Ringläufe vieler Flecken auf einmal: Plan und sicheres Nein.

    **Der Stapel entscheidet, wo gerechnet werden muss, nicht was herauskommt**
    (RM-209). Je Fleck entsteht der Plan, den :func:`_fit_cone_measured` und
    :func:`_fit_torus_measured` ohnehin rechnen würden, und
    :func:`refine.exhausted` sagt für alle zugleich, welcher Löserlauf sein
    Budget sicher ausschöpft und damit nichts geliefert hätte. Nur dieses Nein
    wird übernommen; jeder andere Lauf rechnet der echte Löser Zahl für Zahl
    wie bisher. Die Antwort hängt an keiner Reihenfolge: Welche Flecken im
    Stapel stehen, ändert kein Urteil über einen von ihnen.

    ``shapes`` sind die Kennzahlen deckungsgleicher Flecken, deren Kegel schon
    nichts hergab (:func:`_rigid_key`, ``classify``): Die fragt ``classify``
    nicht mehr, also stehen sie nicht im Stapel, und von mehreren
    deckungsgleichen nur der erste. ``None`` heißt: jeden Fleck fragen (der
    Mantelnachweis teilt nichts). Schon beantwortete Lesungen
    (:func:`_by_geometry`) bleiben draußen.

    Lesung und Kennzahl jedes Flecks legt der Stapel mit ab, damit die Runde
    sie nicht ein zweites Mal rechnet (:func:`_surface_support`,
    :func:`_rigid_key`). ``share`` meldet die Vorbereitung je Fleck in der
    ersten Hälfte seines Anteils und die Solverrunden in der zweiten.
    """
    tolerance = max(weld_tolerance(float(np.linalg.norm(body.extents))), ROUND_WALL_TOLERANCE)
    planning = share.part(0.0, 0.5)
    solving = share.part(0.5, 1.0)
    entries: dict[tuple[Any, ...], tuple[Any, bool]] = {}
    supports: dict[bytes, _SurfaceSupport | _SupportPrint] = {}
    rigid: dict[bytes, tuple[Any, ...] | None] = {}
    asked: list[tuple[tuple[Any, ...], refine.Problem]] = []
    seen = None if shapes is None else set(shapes)
    total_weight = sum(_fit_weight(patch) for patch in patches)
    planned = 0.0
    # Die Abdrücke aller Flecken der Runde in einem Zug (:func:`_support_handle`).
    _patch_prints(body, [patch for patch in patches if _face_count(body, patch) >= MIN_PATCH_FACES])
    for patch in patches:
        weight = _fit_weight(patch)
        if check_cancelled is not None:
            check_cancelled()
        support = _support_handle(body, patch, check_cancelled)
        if support is not None and seen is not None:
            # Die Klassifikation fragt zuerst den vollständigen Zylindernachweis.
            # Für einen belegten Zylinder wird daher auch kein konkurrierender
            # Kegel- oder Ringlauf vorbereitet. Der gesonderte Mantelnachweis
            # (shapes=None) behält seine ausdrücklich gestellte Frage.
            supports[_patch_key(patch)] = support
            cylinder = fit_cylinder(body, patch, check_cancelled=check_cancelled)
            if (
                cylinder is not None
                and cylinder.good
                and _fits_in_the_body(MeshData(raw=body), cylinder)
                and _cylinder_precludes_a_cone(body, cylinder, patch)
            ):
                planned += weight
                planning.reach(planned / total_weight if total_weight else 1.0)
                continue
        if support is not None:
            name = _patch_key(patch)
            supports[name] = support
            shape = None
            if seen is not None:
                shape = rigid[name] if name in rigid else _rigid_key_read(body, patch)
                rigid[name] = shape
            if seen is None or shape is None or shape not in seen:
                if seen is not None and shape is not None:
                    seen.add(shape)
                key: tuple[Any, ...] = ("fit_cone", support.digest, tolerance)
                if key not in entries and not _answered_by_geometry("fit_cone", support, tolerance):
                    cone = _cone_plan(support.read(), tolerance, check_cancelled)
                    entries[key] = (cone, False)
                    if cone is not None:
                        asked.append((key, cone.problem()))
            key = ("fit_torus", support.digest)
            if key not in entries and not _answered_by_geometry("fit_torus", support):
                ring = _torus_plan(support.read())
                entries[key] = (ring, False)
                if ring is not None:
                    asked.append((key, ring.problem()))
        planned += weight
        planning.reach(planned / total_weight if total_weight else 1.0)
    planning.reach(1.0)
    first_runs = solving.part(0.0, 0.8)
    verdicts = refine.exhausted(
        [problem for _key, problem in asked],
        precision=ROUND_FIT_PRECISION,
        evaluations=ROUND_FIT_EVALUATIONS,
        check_cancelled=check_cancelled,
        progress=first_runs.reach,
    )
    # Wer vom ersten Start sicher am Budget endet und einen Quadrikstart hat,
    # rechnet von dort ein zweites Mal (:func:`_cone_from_plan`) — auch dieser
    # Lauf bekommt das sichere Nein des Stapels.
    second: list[tuple[tuple[Any, ...], refine.Problem]] = []
    for (key, _problem), verdict in zip(asked, verdicts, strict=True):
        if verdict:
            plan = entries[key][0]
            entries[key] = (plan, True)
            if key[0] == "fit_cone" and plan.seed is not None:
                seeded = ("fit_cone_seed", *key[1:])
                entries[seeded] = (plan, False)
                second.append((seeded, plan.problem(plan.seed)))
    second_verdicts = refine.exhausted(
        [problem for _key, problem in second],
        precision=ROUND_FIT_PRECISION,
        evaluations=ROUND_FIT_EVALUATIONS,
        check_cancelled=check_cancelled,
        progress=solving.part(0.8, 1.0).reach,
    )
    for (key, _problem), verdict in zip(second, second_verdicts, strict=True):
        if verdict:
            entries[key] = (entries[key][0], True)
    share.reach(1.0)
    return _Screened(body, entries, supports, rigid)


@contextmanager
def _screening(
    body: trimesh.Trimesh,
    patches: Sequence[list[int]],
    *,
    shapes: set[tuple[Any, ...]] | None = None,
    check_cancelled: Callable[[], None] | None = None,
    share: _Share = _UNHEARD,
) -> Iterator[None]:
    """Eine Runde mit dem Wissen des Stapels (:func:`_screened_fits`), danach ohne."""
    screened = _screened_fits(
        body, patches, shapes=shapes, check_cancelled=check_cancelled, share=share
    )
    token = _SCREENED.set(screened)
    try:
        yield
    finally:
        _SCREENED.reset(token)


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
    support = _support_handle(body, patch, check_cancelled)
    if support is None:
        return None
    # Eine gerade Naht zweier Mantelfacetten ist nur dann eine zusätzliche
    # Stütze, wenn sie durch dieselbe Spitze läuft. Schnittpunkte auf einer
    # solchen Mantellinie liegen ebenfalls auf dem analytischen Kegel.
    line_tolerance = max(weld_tolerance(float(np.linalg.norm(body.extents))), ROUND_WALL_TOLERANCE)
    result: ConeFit | None = _by_geometry(
        "fit_cone",
        body,
        support,
        lambda: _fit_cone_measured(support.read(), line_tolerance, check_cancelled),
        line_tolerance,
    )
    return result


def _fit_cone_measured(
    support: _SurfaceSupport,
    line_tolerance: float,
    check_cancelled: Callable[[], None] | None,
) -> ConeFit | None:
    """Die Kegeleinpassung an einer Lesung — sie liest nichts sonst.

    Hat der Stapel dieser Runde den Fleck schon vorbereitet (:data:`_SCREENED`),
    kommt der Plan von dort, und ein sicher vergeblicher Löserlauf entfällt
    (:func:`_screened_fits`); sonst entsteht der Plan hier, Zahl für Zahl
    derselbe.
    """
    screened = _SCREENED.get()
    entry = (
        None
        if screened is None
        else screened.fits.get(("fit_cone", support.digest, line_tolerance))
    )
    seeded = (
        None
        if screened is None
        else screened.fits.get(("fit_cone_seed", support.digest, line_tolerance))
    )
    if entry is None:
        plan = _cone_plan(support, line_tolerance, check_cancelled)
        exhausted = False
    else:
        plan, exhausted = entry
    if plan is None:
        return None
    return _cone_from_plan(
        plan,
        check_cancelled,
        exhausted=exhausted,
        seed_exhausted=seeded is not None and seeded[1],
    )


@dataclass(frozen=True, slots=True, eq=False)
class _ConePlan:
    """Was die Kegeleinpassung vor dem Löser aus der Lesung liest (:func:`_cone_plan`)."""

    support: _SurfaceSupport
    line_tolerance: float
    weights: np.ndarray
    origin: np.ndarray
    basis: np.ndarray
    half_angle: float
    points: np.ndarray
    selected: np.ndarray
    scale: float
    samples: np.ndarray
    apex: np.ndarray
    initial_axis: np.ndarray
    first: np.ndarray
    second: np.ndarray
    solving: np.ndarray
    solving_apex: np.ndarray
    #: Der zweite Start aus der Quadrik der Stützpunkte, wo sie einen gültigen
    #: Kegel gibt (:func:`_quadric_cone_start`), sonst ``None``. Er rechnet nur,
    #: wenn der Lauf vom ersten sein Budget ausschöpft (:func:`_cone_from_plan`).
    seed: np.ndarray | None = None

    def start(self) -> np.ndarray:
        """Der Startwert des Lösers: Spitze, zwei Achsneigungen, Winkel."""
        start: np.ndarray = np.r_[self.apex, 0.0, 0.0, self.half_angle]
        return start

    def problem(self, initial: np.ndarray | None = None) -> refine.ConeProblem:
        """Dieselbe Aufgabe für den Stapel (:func:`refine.exhausted`) — vom ersten
        Start oder von ``initial`` (dem zweiten)."""
        return refine.ConeProblem(
            points=self.solving,
            apex=self.solving[self.solving_apex[0]] if len(self.solving_apex) else None,
            axis=self.initial_axis,
            first=self.first,
            second=self.second,
            initial=self.start() if initial is None else initial.copy(),
        )


def _cone_plan(
    support: _SurfaceSupport,
    line_tolerance: float,
    check_cancelled: Callable[[], None] | None,
) -> _ConePlan | None:
    """Der Teil der Kegeleinpassung vor dem Löser; ``None``: kein Kegel zu verfeinern."""
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
    selected = _cone_support_points(support, origin + apex, line_tolerance, check_cancelled)
    if int(selected.sum()) < 6:
        return None
    # Normierung und Freiheitsgrade gehören in den Rahmen des Flecks. Eine
    # Weltbox wächst beim Drehen; auch die zwei Neigungen gegen Weltachsen
    # verändern den Weg des nichtlinearen Lösers. Beides konnte denselben
    # Fleck einmal konvergieren und einmal am Budget enden lassen (RM-210).
    scale = 2.0 * float(np.linalg.norm(points[selected], axis=1).max())
    if scale <= EPS_GEOM:
        return None
    radial = points[selected] - np.outer(points[selected] @ axis, axis)
    reaches = np.linalg.norm(radial, axis=1)
    longest = float(reaches.max())
    if longest <= EPS_GEOM:
        return None
    # Bei gleich weit entfernten Kreispunkten bleibt die ursprüngliche
    # Punktfolge maßgeblich; Rundungsrauschen wählt keinen anderen Punkt.
    anchor = int(np.flatnonzero(reaches >= longest - EPS_GEOM)[0])
    across = radial[anchor] / reaches[anchor]
    basis = np.column_stack((across, _cross3(axis, across), axis))
    samples = (points[selected] @ basis) / scale
    apex = (apex @ basis) / scale
    initial_axis = np.array((0.0, 0.0, 1.0))
    first, second = np.array((1.0, 0.0, 0.0)), np.array((0.0, 1.0, 0.0))
    at_apex = np.flatnonzero(np.linalg.norm(samples - apex, axis=1) <= EPS_GEOM / scale)
    # Der Löser rechnet an einer Auswahl der Stützpunkte, die Spitze bleibt
    # darin (:data:`FIT_SOLVER_POINTS`); die Kennzahlen unten lesen alle.
    rows = _solver_rows(len(samples), keep=int(at_apex[0]) if len(at_apex) else None)
    solving = samples if rows is None else samples[rows]
    solving_apex = (
        at_apex if rows is None or not len(at_apex) else np.flatnonzero(rows == int(at_apex[0]))
    )
    # Eine belegte Spitze hält den Start ohnehin fest; sonst darf die Quadrik
    # der Stützpunkte ihn ersetzen, wenn sie näher am Kegel liegt (RM-210).
    seed = None if len(solving_apex) else _quadric_cone_start(samples)
    return _ConePlan(
        support=support,
        line_tolerance=line_tolerance,
        weights=weights,
        origin=origin,
        basis=basis,
        half_angle=half_angle,
        points=points,
        selected=selected,
        scale=scale,
        samples=samples,
        apex=apex,
        initial_axis=initial_axis,
        first=first,
        second=second,
        solving=solving,
        solving_apex=solving_apex,
        seed=seed,
    )


def _quadric_cone_start(samples: np.ndarray) -> np.ndarray | None:
    """Ein Kegelstart aus der Quadrik der Stützpunkte — oder ``None`` (RM-210).

    Der Start aus den Normalen (:func:`_cone_plan`) steht an flachen, kurzen
    Kegelstücken weit vom Ziel: Deren Normalen streuen wenig, ihre Achse ist
    kaum bestimmt, und der Winkel aus der mittleren Normale lag am
    Gartenschlauchhalter bei 70 bis 84 statt 35 bis 43 Grad. Fünf Teilstücke
    zweier Kegelgruppen brauchten so 58 bis 100 Auswertungen und endeten je
    nach Lage des Körpers mal knapp unter, mal am Budget
    (:data:`ROUND_FIT_EVALUATIONS`) — dann ohne Kegel. Eine Quadrik durch die
    Stützpunkte ist ein linearer Ausgleich; ist sie ein Kegel oder Hyperboloid
    (eine Eigenrichtung mit anderem Vorzeichen als die beiden übrigen), geben
    ihr Mittelpunkt, diese Richtung und das Verhältnis der Eigenwerte Spitze,
    Achse und Winkel. Von dort kamen dieselben fünf Stücke in 6 bis 40
    Auswertungen an, mit demselben Formfehler (04.10.2026).

    **Er ist der zweite Start, nicht der erste.** Für jeden Kegel gesetzt,
    änderte er Merkmale an elf von 193 Korpusdateien — darunter zehn gleiche
    Kegel Ø 31,6 an einer Minigolfbahn, die vom Normalenstart ankommen und
    vom Quadrikstart nicht. Er rechnet deshalb nur, wo der erste Lauf sein Budget
    ausschöpft (:func:`_cone_from_plan`). Ein Vergleich der Startkosten trennt
    nicht: Der Normalenstart liegt als fast ebener Kegel nahe an den Punkten
    und trotzdem im falschen Tal. Gültig ist der Quadrikstart, wenn der
    Ausgleich eindeutig ist, sein Winkel zwischen :data:`CONE_START_ANGLE` und
    :data:`CONE_MAX_ANGLE` liegt und alle Stützpunkte auf einer Seite der
    Spitze. Löser, Budget und jede Prüfung danach bleiben dieselben.
    Ausgleich und Eigenzerlegung laufen über LAPACK wie der Normalenstart;
    beide sind ein Startwert, keine Antwort.
    """
    if len(samples) < 10:
        return None
    x, y, z = samples[:, 0], samples[:, 1], samples[:, 2]
    design = np.column_stack(
        (x * x, y * y, z * z, 2.0 * x * y, 2.0 * x * z, 2.0 * y * z, x, y, z, np.ones(len(x)))
    )
    _left, singular, right = np.linalg.svd(design, full_matrices=False)
    if singular[-2] <= singular[0] * math.sqrt(float(np.finfo(float).eps)):
        return None
    q = right[-1]
    quadric = np.array(((q[0], q[3], q[4]), (q[3], q[1], q[5]), (q[4], q[5], q[2])))
    values, vectors = np.linalg.eigh(quadric)
    if float(np.abs(values).min()) <= float(np.abs(values).max()) * math.sqrt(
        float(np.finfo(float).eps)
    ):
        return None
    if values[0] < 0.0 < values[1]:
        odd = 0
    elif values[1] < 0.0 < values[2]:
        odd = 2
    else:
        return None
    tip = np.linalg.solve(quadric, -q[6:9] / 2.0)
    axis = vectors[:, odd]
    side = (float(values[(odd + 1) % 3]) + float(values[(odd + 2) % 3])) / 2.0
    angle = math.atan(math.sqrt(-float(values[odd]) / side))
    along = (samples - tip) @ axis
    if float(along.mean()) < 0.0:
        axis, along = -axis, -along
    if float(along.min()) < 0.0 or axis[2] <= math.sqrt(float(np.finfo(float).eps)):
        return None
    if not math.radians(CONE_START_ANGLE) <= angle <= math.radians(CONE_MAX_ANGLE):
        return None
    seed: np.ndarray = np.r_[tip, axis[0] / axis[2], axis[1] / axis[2], angle]
    if not np.isfinite(seed).all():
        return None
    return seed


def _cone_from_plan(
    plan: _ConePlan,
    check_cancelled: Callable[[], None] | None,
    *,
    exhausted: bool = False,
    seed_exhausted: bool = False,
) -> ConeFit | None:
    """Der Löser und das Maß der Kegeleinpassung.

    ``exhausted`` sagt der Stapel (:func:`refine.exhausted`): Der Löserlauf
    schöpft sein Budget sicher aus und hätte nichts geliefert — dann entfällt
    er, und es geht weiter wie nach einem vergeblichen Lauf.

    **Am Budget beginnt ein zweiter Lauf am Quadrikstart** (``plan.seed``,
    RM-210), und nur dort: Wo der erste ankommt, bleibt sein Ergebnis Bit für
    Bit, und eine Antwort, die vom ersten Start an der Lage des Körpers hing,
    bekommt eine zweite Chance aus einem Start, der nicht an den Normalen
    hängt. ``seed_exhausted`` ist das sichere Nein des Stapels für diesen
    zweiten Lauf.
    """
    support, line_tolerance = plan.support, plan.line_tolerance
    weights, origin, half_angle = plan.weights, plan.origin, plan.half_angle
    points, selected, scale, samples = plan.points, plan.selected, plan.scale, plan.samples
    apex, initial_axis, first, second = plan.apex, plan.initial_axis, plan.first, plan.second
    solving, solving_apex = plan.solving, plan.solving_apex

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

    spent: list[bool] = []
    fitted = (
        None
        if exhausted
        else _refined_fit(plan.start(), residual, check_cancelled, jacobian, spent=spent)
    )
    if fitted is None and (exhausted or spent) and plan.seed is not None and not seed_exhausted:
        fitted = _refined_fit(plan.seed.copy(), residual, check_cancelled, jacobian)
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
    apex = (apex @ plan.basis.T) * scale
    axis = axis @ plan.basis.T
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
    support = _support_handle(body, patch, check_cancelled)
    if support is None:
        return None
    result: SphereFit | None = _by_geometry(
        "fit_sphere", body, support, lambda: _fit_sphere_measured(support.read(), check_cancelled)
    )
    return result


def _fit_sphere_measured(
    support: _SurfaceSupport, check_cancelled: Callable[[], None] | None
) -> SphereFit | None:
    """Die Kugeleinpassung an einer Lesung — sie liest nichts sonst."""
    if int(support.round_corners.sum()) < 4:
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
    support = _support_handle(body, patch, check_cancelled)
    if support is None:
        return None
    result: TorusFit | None = _by_geometry(
        "fit_torus", body, support, lambda: _fit_torus_measured(support.read(), check_cancelled)
    )
    return result


def _fit_torus_measured(
    support: _SurfaceSupport, check_cancelled: Callable[[], None] | None
) -> TorusFit | None:
    """Die Ringeinpassung an einer Lesung — sie liest nichts sonst.

    Wie beim Kegel: Den Plan und das Urteil über den Löserlauf kann der
    Stapel dieser Runde schon kennen (:data:`_SCREENED`).
    """
    screened = _SCREENED.get()
    entry = None if screened is None else screened.fits.get(("fit_torus", support.digest))
    if entry is None:
        plan = _torus_plan(support)
        exhausted = False
    else:
        plan, exhausted = entry
    if plan is None:
        return None
    return _torus_from_plan(plan, check_cancelled, exhausted=exhausted)


@dataclass(frozen=True, slots=True, eq=False)
class _TorusPlan:
    """Was die Ringeinpassung vor dem Löser aus der Lesung liest (:func:`_torus_plan`)."""

    support: _SurfaceSupport
    initial: TorusFit
    origin: np.ndarray
    scale: float
    initial_axis: np.ndarray
    first: np.ndarray
    second: np.ndarray
    solving: np.ndarray

    def start(self) -> np.ndarray:
        """Der Startwert des Lösers: Mitte, zwei Achsneigungen, Ring- und Röhrenradius."""
        start: np.ndarray = np.r_[
            (np.asarray(self.initial.centre) - self.origin) / self.scale,
            0.0,
            0.0,
            self.initial.ring_radius / self.scale,
            self.initial.tube_radius / self.scale,
        ]
        return start

    def problem(self) -> refine.TorusProblem:
        """Dieselbe Aufgabe für den Stapel (:func:`refine.exhausted`)."""
        return refine.TorusProblem(
            points=self.solving,
            axis=self.initial_axis,
            first=self.first,
            second=self.second,
            initial=self.start(),
        )


def _torus_plan(support: _SurfaceSupport) -> _TorusPlan | None:
    """Der Teil der Ringeinpassung vor dem Löser; ``None``, wo es keinen Ring zu verfeinern gibt."""
    if int(support.round_corners.sum()) < 7:
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
    return _TorusPlan(
        support=support,
        initial=initial,
        origin=origin,
        scale=scale,
        initial_axis=initial_axis,
        first=first,
        second=second,
        solving=solving,
    )


def _torus_from_plan(
    plan: _TorusPlan,
    check_cancelled: Callable[[], None] | None,
    *,
    exhausted: bool = False,
) -> TorusFit | None:
    """Der Löser und das Maß der Ringeinpassung; ``exhausted`` wie bei :func:`_cone_from_plan`."""
    support, origin, scale = plan.support, plan.origin, plan.scale
    initial_axis, first, second, solving = plan.initial_axis, plan.first, plan.second, plan.solving

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

    if exhausted:
        return None
    fitted = _refined_fit(plan.start(), residual, check_cancelled, jacobian)
    if fitted is None:
        return None
    centre, axis, ring, tube = parameters(fitted)
    if not ring > tube > EPS_GEOM / scale:
        return None
    local_centres = (support.centres - origin) / scale
    mid = _tube_centres(centre, axis, local_centres, ring)
    agreement = np.einsum("ij,ij->i", support.normals, local_centres - mid)
    world_centre = origin + centre * scale
    axis = _ring_axis(axis)
    return TorusFit(
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        centre=(float(world_centre[0]), float(world_centre[1]), float(world_centre[2])),
        ring_radius=ring * scale,
        tube_radius=tube * scale,
        residual=float(np.abs(residual(fitted)).mean()) / tube,
        recess=float(agreement @ support.areas) < 0.0,
        fit_error=float(np.abs(residual(fitted)).max()) * scale,
    )


#: Wohin eine Ringachse zeigt (:func:`_ring_axis`): (1, √2, √3). Auf dieser
#: Richtung steht keine Achse mit rationalen Anteilen senkrecht, also keine,
#: die eine Konstruktion meint — achsparallel, diagonal, in kleinen Verhältnissen.
_RING_AXIS_TOWARD: Final = (1.0, math.sqrt(2.0), math.sqrt(3.0))


def _ring_axis(axis: np.ndarray) -> np.ndarray:
    """Die Achse eines Torus in kanonischer Richtung — ein Ring hat kein Oben.

    Die Einpassung gab das Vorzeichen zurück, das die letzten Stellen ergaben:
    An ``torus_ring.stl`` kippte die Achse, wenn die Datei ihre Dreiecke
    anders ordnete oder ihre Ecken im Umlauf verdrehte (RM-210, Messbank
    Paket E). Gezeigt wird dorthin, wo das Skalarprodukt mit
    :data:`_RING_AXIS_TOWARD` positiv ist.
    """
    toward = (
        axis[0] * _RING_AXIS_TOWARD[0]
        + axis[1] * _RING_AXIS_TOWARD[1]
        + axis[2] * _RING_AXIS_TOWARD[2]
    )
    return -axis if float(toward) < 0.0 else axis


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
    axis = _ring_axis(axis)
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
    support = _support_handle(body, patch, check_cancelled)
    if support is None:
        return False
    weld = weld_tolerance(float(np.linalg.norm(body.extents)))
    result: bool = _by_geometry(
        "_torus_is_recognisable",
        body,
        support,
        lambda: _torus_is_recognisable_measured(
            body, fit, patch, support.read(), weld, check_cancelled
        ),
        fit,
        weld,
    )
    return result


def _torus_is_recognisable_measured(
    body: trimesh.Trimesh,
    fit: TorusFit,
    patch: list[int],
    support: _SurfaceSupport,
    weld: float,
    check_cancelled: Callable[[], None] | None,
) -> bool:
    """Der Ringnachweis selbst; was er vom Körper liest, trägt die Lesung."""
    centres = np.asarray(body.triangles_center[patch], dtype=float)
    corners = np.asarray(body.triangles[patch], dtype=float)
    centre = np.asarray(fit.centre, dtype=float)
    axis = np.asarray(fit.axis, dtype=float)
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
    allowance = max(weld, fit.tube_radius * ROUND_TOLERANCE)
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
    tolerance: float,
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

    vertex_indices = np.unique(np.asarray(body.faces)[patch].astype(np.intp))
    relative = np.asarray(body.vertices, dtype=float)[vertex_indices] - apex
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
    """Der Rumpf von :func:`_cone_is_recognisable` — die Antwort merkt sich die Hülle.

    Ohne Lesung ist kein Kegel belegt (:func:`_cone_vertices_are_consistent`
    fragt sie zuletzt und sagt dann nein).
    """
    support = _support_handle(body, patch, check_cancelled)
    if support is None:
        return False
    tolerance = max(weld_tolerance(float(np.linalg.norm(body.extents))), ROUND_WALL_TOLERANCE)
    result: bool = _by_geometry(
        "_cone_is_recognisable",
        body,
        support,
        lambda: _cone_is_recognisable_measured(body, fit, patch, tolerance, check_cancelled),
        fit,
        tolerance,
    )
    return result


def _cone_is_recognisable_measured(
    body: trimesh.Trimesh,
    fit: ConeFit,
    patch: list[int],
    tolerance: float,
    check_cancelled: Callable[[], None] | None,
) -> bool:
    """Der Kegelnachweis selbst; was er vom Körper liest, trägt die Lesung."""
    if not _cone_vertices_are_consistent(
        body, fit, patch, tolerance, check_cancelled=check_cancelled
    ):
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


def _cross3(first: Any, second: Any) -> np.ndarray:
    """``np.cross`` zweier 3-Vektoren — dieselben Gleitkommaschritte, ohne dessen Umweg.

    ``np.cross`` rechnet je Komponente ein Produkt, ein zweites und ihre
    Differenz, jedes für sich gerundet; genau das tut diese Zeile, also Bit für
    Bit dasselbe Ergebnis, samt Vorzeichen einer Null. Der Umweg dagegen —
    Achsen verschieben, Ausgabefeld anlegen, drei Teilfelder — kostete an einer
    Taschenplatte mit 200 Taschen 70 µs je Aufruf und 0,92 von 9,2 Sekunden
    eines Profils der Erkennung, fast alles aus :func:`_plane_basis`
    (gemessen am 22.09.2026).
    """
    a0, a1, a2 = float(first[0]), float(first[1]), float(first[2])
    b0, b1, b2 = float(second[0]), float(second[1]), float(second[2])
    return np.array([a1 * b2 - a2 * b1, a2 * b0 - a0 * b2, a0 * b1 - a1 * b0])


def _plane_basis(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    helper = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.9 else (0.0, 1.0, 0.0)
    basis_u = _cross3(axis, helper)
    basis_u = basis_u / float(np.linalg.norm(basis_u))
    return basis_u, _cross3(axis, basis_u)


def _fit_circle(points: np.ndarray) -> tuple[np.ndarray, float]:
    """Kåsa-Ausgleich im lokalen Maßrahmen, mit pivotierter Householder-QR.

    Die drei Spalten werden orthogonalisiert, ohne die Kondition durch
    Normalgleichungen zu quadrieren. Produkte, Summen und Rückwärtseinsetzen
    haben eine feste Reihenfolge; kein BLAS-/LAPACK-Kern bestimmt den
    Mittelpunkt, an dem eine Folgeoperation ihren Schneidkörper baut.
    Ein numerisch rangloser Bogen liefert keinen Kreis (Radius null).
    """
    origin = np.array([units.exact_mean(points[:, index].tolist()) for index in range(2)])
    local = points - origin
    scale = float(np.abs(local).max())
    if len(points) < 3 or scale <= 0.0:
        return origin, 0.0
    local /= scale
    matrix = np.column_stack([local[:, 0], local[:, 1], np.ones(len(points))])
    target = local[:, 0] * local[:, 0] + local[:, 1] * local[:, 1]
    order = [0, 1, 2]
    # Die übliche relative Ranggrenze eines Ausgleichs, keine zusätzliche
    # Geometrietoleranz: Maschinengenauigkeit mal Systemgröße und Spaltennorm.
    rank_limit = np.finfo(float).eps * max(matrix.shape) * math.sqrt(len(points))
    for column in range(3):
        # Als Python-Zahlen entpackt: dieselben Werte, ohne je Eintrag ein
        # NumPy-Skalar anzulegen (RM-568).
        norms = [math.hypot(*matrix[column:, index].tolist()) for index in range(column, 3)]
        pivot = column + int(np.argmax(norms))
        length = norms[pivot - column]
        if length <= rank_limit:
            return origin, 0.0
        matrix[:, [column, pivot]] = matrix[:, [pivot, column]]
        order[column], order[pivot] = order[pivot], order[column]
        direction = matrix[column:, column].copy()
        diagonal = -math.copysign(length, float(direction[0]))
        direction[0] -= diagonal
        direction /= math.hypot(*direction.tolist())
        for remaining in range(column + 1, 3):
            projection = 2.0 * math.fsum((direction * matrix[column:, remaining]).tolist())
            matrix[column:, remaining] -= projection * direction
        projection = 2.0 * math.fsum((direction * target[column:]).tolist())
        target[column:] -= projection * direction
        matrix[column, column] = diagonal
        matrix[column + 1 :, column] = 0.0
    solved = [0.0, 0.0, 0.0]
    for row in (2, 1, 0):
        rest = math.fsum(float(matrix[row, index]) * solved[index] for index in range(row + 1, 3))
        solved[row] = (float(target[row]) - rest) / float(matrix[row, row])
    solution = np.empty(3)
    solution[order] = solved
    centre = np.array([solution[0] / 2.0, solution[1] / 2.0])
    radius = math.sqrt(max(float(solution[2] + centre[0] * centre[0] + centre[1] * centre[1]), 0.0))
    return centre * scale + origin, radius * scale


def _axial_span(body: trimesh.Trimesh, patch: list[int], axis: Vec3) -> tuple[float, float]:
    """Von wo bis wo ein Fleck entlang einer Achse reicht."""
    points = np.asarray(body.vertices, dtype=float)[np.unique(np.asarray(body.faces)[patch])]
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
        square = (
            bounds.candidates(axis, basis_u, basis_v, fit, None) if bounds is not None else None
        )
        if (
            _known_answer("surface_owners", mesh.raw) is not None
            or _known_answer("large_facet_faces", mesh.raw) is not None
        ):
            # **Kennt der Körper seine Flächen schon** — die Vollerkennung liest
            # die großen Facetten vor den Bohrungen —, ist die Zuordnung des
            # ganzen Körpers nur noch ein Gang über die Rundflecken, und die
            # Nachbarflächen sind wenige Dreiecke: Gefragt wird an ihnen allein.
            # Am Filterball mit 140 Bohrungen kostete der örtliche Weg sonst
            # 5,4 statt 0,7 s der Erkennung (Durchsicht 0.5.1, rest-erkennung2).
            members = _faces_beside(mesh.raw, patch)
            if square is not None and len(members):
                members = members[square[members]]
            if not len(members):
                return True
            beside = np.asarray(mesh.raw.triangles, dtype=float)[members] - centre
            return not _mouth_covered(beside, basis_u, basis_v, radius)
        # **Erst, ob überhaupt ein Dreieck außerhalb des Flecks die Mündung
        # deckt** (Durchsicht 0.5.1, rest-erkennung2). Die Nachbarflächen kommen
        # aus der Flächenzuordnung des ganzen Körpers (:func:`_surface_owners`,
        # mit dem Mantelnachweis jeder Rundung) — am Gartenschlauchhalter mit
        # 392 532 Dreiecken 2,4 s je neuem Netz, und die örtliche Nachmessung
        # nach jedem Versetzen fragte sie. Deckt kein Dreieck außerhalb des
        # Flecks die Mündung, deckt auch keines einer Nachbarfläche: Die Antwort
        # steht, und sie ist dieselbe. Dieselbe Vorauswahl über das
        # Mündungsquadrat wie darunter.
        outside = np.ones(len(mesh.raw.faces), dtype=bool)
        outside[np.asarray(patch, dtype=np.intp)] = False
        if square is not None:
            # Dieselbe Vorauswahl über das Mündungsquadrat wie oben, ohne den
            # Abschnitt: Die Deckflächen einer Platte mit 200 000 Dreiecken
            # zählen sonst je Bohrung ganz.
            outside &= square
        chosen = np.flatnonzero(outside)
        rest = np.asarray(mesh.raw.triangles, dtype=float)[chosen] - centre
        over = chosen[_covering(rest, basis_u, basis_v, radius)]
        if not len(over):
            return True
        # **Deckt etwas, fragt nur noch, ob es zu einer Nachbarfläche gehört**
        # (:func:`_beside_covers`) — dieselbe Frage wie über alle Dreiecke der
        # Nachbarflächen, gerechnet aus ihrer Umgebung.
        return not _beside_covers(mesh.raw, patch, over)
    return True


def _mouth_covered(
    corners: np.ndarray, basis_u: np.ndarray, basis_v: np.ndarray, radius: float
) -> bool:
    """Liegt eines dieser Dreiecke über der Achse oder einem der Ringe der Mündung?

    ``corners`` sind Dreiecke relativ zur Mitte der Bohrung, ``(n, 3, 3)``.
    Ein Punkt-in-Dreieck-Test in der Projektion senkrecht zur Achse —
    baryzentrische Vorzeichen, kein Strahlwurf und damit kein Raumindex.
    """
    return bool(_covering(corners, basis_u, basis_v, radius).any())


def _covering(
    corners: np.ndarray, basis_u: np.ndarray, basis_v: np.ndarray, radius: float
) -> np.ndarray:
    """Je Dreieck, ob es über der Achse oder einem der Ringe der Mündung liegt
    (:func:`_mouth_covered`)."""
    found = np.zeros(len(corners), dtype=bool)
    if not len(corners):
        return found
    flat = np.stack([corners @ basis_u, corners @ basis_v], axis=-1)
    within = (flat.min(axis=1) <= radius).all(axis=1) & (flat.max(axis=1) >= -radius).all(axis=1)
    flat = flat[within]
    if not len(flat):
        return found
    # Die Stichproben aus der genauen Kreistafel (RM-187), nicht aus ``np.cos``.
    circle = np.asarray(units.circle_cos_sin(THROUGH_SAMPLES), dtype=float)
    samples = np.vstack(
        [
            np.zeros((1, 2)),
            *(circle * (radius * share) for share in THROUGH_RINGS),
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
    found[np.flatnonzero(within)] = covers.any(axis=1)
    return found


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


def _beside_covers(body: trimesh.Trimesh, patch: Sequence[int], over: np.ndarray) -> bool:
    """Ob eines der Dreiecke ``over`` zu einer Fläche gehört, die an ``patch`` grenzt.

    Dieselbe Frage wie ``np.isin(over, _faces_beside(body, patch)).any()``
    (:func:`_is_through`). :func:`_faces_beside` liest die Flächenzuordnung des
    ganzen Körpers (:func:`_surface_owners`) samt dem Mantelnachweis jeder
    Rundung, und an einem neuen Netz ist das ein Gang über alle Dreiecke: am
    Gartenschlauchhalter mit 392 532 Dreiecken 2,4 s der örtlichen
    Nachmessung nach jedem Versetzen — gefragt von der Senkung einer Bohrung,
    deren Schulter die Mündung deckt (Durchsicht 0.5.1, bohrung). Gebraucht
    wird die Zuordnung nur für die Nachbarn des Flecks und für ``over``
    (:func:`_surface_owners_near`). Steht die des ganzen Körpers schon im
    Merker, wird sie gelesen.
    """
    indices = np.asarray(patch, dtype=np.int64)
    inside = np.zeros(len(body.faces), dtype=bool)
    inside[indices] = True
    neighbours, _rows = _neighbour_index(body)
    if not neighbours.shape[1]:
        return False
    beside = neighbours[indices].ravel()
    beside = beside[beside >= 0]
    beside = np.unique(beside[~inside[beside]])
    if not len(beside):
        return False
    seeds = np.union1d(beside, over)
    known = _known_answer("surface_owners", body)
    owners = (
        np.asarray(known, dtype=np.int64)[seeds]
        if known is not None
        else _surface_owners_near(body, seeds)
    )
    near = owners[np.searchsorted(seeds, beside)]
    surfaces = np.unique(near[near != -1])
    if not len(surfaces):
        # Wie :func:`_faces_beside`: ohne eine Fläche zählen die Nachbarn selbst.
        return bool(np.isin(over, beside).any())
    return bool(np.isin(owners[np.searchsorted(seeds, over)], surfaces).any())


def _surface_owners_near(
    body: trimesh.Trimesh,
    seeds: np.ndarray,
    check_cancelled: Callable[[], None] | None = None,
) -> np.ndarray:
    """Die Flächenzuordnung von :func:`_surface_owners` für einzelne Dreiecke — aus ihrer Umgebung.

    Zurück kommt je Dreieck aus ``seeds`` (aufsteigend) eine Nummer: die seiner
    Facette für eine ebene Fläche, ``-2 - kleinstes Dreieck`` für einen
    Rundfleck, ``-1`` ohne Fläche. Zwei Dreiecke tragen dieselbe Nummer, wenn
    :func:`_surface_owners` ihnen dieselbe gibt — die Nummern selbst sind
    andere.

    **Gerechnet wird dieselbe Zuordnung, nur nicht überall.** Eine geschützte
    ebene Facette (:func:`_facet_verdicts`: eben und nicht zurückholbar) ist
    ihre eigene Fläche; jede andere Fläche entsteht aus den übrigen, den
    **ungeschützten** Dreiecken — der Mantelnachweis aus ihren Flecken
    (:func:`_large_facet_faces_read`), die Rundflecken aus dem, was danach
    nicht eben ist (:func:`_surface_owners_read`), beide über Nähte unter
    :data:`CURVATURE_LIMIT`. Gerechnet wird deshalb an den ungeschützten
    Flecken um die gefragten Dreiecke und ihre Nachbarn, mit denselben
    Schritten und jede Kerbe (:func:`_without_notches`) in der Reihenfolge der
    Flecken. Hängt eine Antwort an einem Fleck außerhalb — eine Kerbe, die ein
    früherer Fleck schließen könnte, ein geschütztes Dreieck, das ein Fleck
    als Kerbe nimmt —, wächst die Umgebung um ihn, und es wird neu gerechnet,
    bis keine Frage mehr hinausreicht. Hat das zusammen so viele Dreiecke
    gerechnet, wie der Körper ungeschützte hat, kommen die Nummern von
    :func:`_surface_owners` selbst — dieselbe Zerlegung, einmal gerechnet.
    """
    verdicts = _facet_verdicts(body, check_cancelled=check_cancelled)
    label = verdicts.label
    count = len(body.faces)
    in_planar = np.zeros(count, dtype=bool)
    in_recoverable = np.zeros(count, dtype=bool)
    labelled = label >= 0
    if len(verdicts.planar):
        in_planar[labelled] = verdicts.planar[label[labelled]]
        in_recoverable[labelled] = verdicts.recoverable[label[labelled]]
    loose = verdicts.candidate
    neighbours, rows = _neighbour_index(body)
    soft = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float)) < CURVATURE_LIMIT
    mesh = MeshData.of(body)
    facets = body.facets
    wanted = np.unique(np.asarray(seeds, dtype=np.int64))
    around = neighbours[wanted].ravel()
    start = np.union1d(wanted, around[around >= 0])
    # Auch die Nachbarn des ersten Dreiecks jeder gefragten Facette: Ob sie
    # ihre Nummer trägt, entscheidet dieses Dreieck.
    firsts = np.asarray(
        [int(facets[facet][0]) for facet in np.unique(label[wanted]).tolist() if facet >= 0],
        dtype=np.int64,
    )
    if len(firsts):
        beside_first = neighbours[firsts].ravel()
        start = np.union1d(start, np.union1d(firsts, beside_first[beside_first >= 0]))
    # **Was schon gerechnet ist, gilt weiter** (:class:`_NearSurfaces`): Die
    # Nachmessung fragt je Bohrung, und am Gartenschlauchhalter reichte schon
    # die erste Umgebung über die Hälfte des Körpers.
    known: _NearSurfaces = remembered("surfaces_near", body, (), _NearSurfaces)
    with known.lock:
        if known.zone is not None and _settled(known.zone, start, loose, soft, body, neighbours):
            return _near_owners(known, wanted, label, facets)
        zone = np.zeros(count, dtype=bool) if known.zone is None else known.zone.copy()
        _flood_loose(zone, start, loose, neighbours, rows, soft)
        # **Hat die Umgebung zusammen schon so viel gerechnet, wie der Körper
        # ungeschützte Dreiecke hat, rechnet die nächste Frage den ganzen
        # Körper** — einmal, gemerkt, und jede weitere liest daraus. Jede neue
        # Frage rechnet ihre ganze gewachsene Umgebung neu; an einem Körper mit
        # vielen Bohrungen wurde daraus mehr als das Ganze.
        size = int(zone.sum())
        if known.worked + size > int(loose.sum()):
            owners: np.ndarray = np.asarray(_surface_owners(body), dtype=np.int64)[wanted]
            return owners
        planar, patch_of = _near_surfaces(
            body,
            mesh,
            zone,
            start,
            loose,
            in_planar,
            in_recoverable,
            neighbours,
            rows,
            soft,
            check_cancelled,
        )
        known.zone, known.planar, known.patch_of = zone, planar, patch_of
        known.worked += size
        return _near_owners(known, wanted, label, facets)


def _near_surfaces(
    body: trimesh.Trimesh,
    mesh: MeshData,
    zone: np.ndarray,
    start: np.ndarray,
    loose: np.ndarray,
    in_planar: np.ndarray,
    in_recoverable: np.ndarray,
    neighbours: np.ndarray,
    rows: np.ndarray,
    soft: np.ndarray,
    check_cancelled: Callable[[], None] | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Der Rumpf von :func:`_surface_owners_near`: ``zone`` wächst, bis keine Frage hinausreicht.

    Zurück kommen je Dreieck, ob es eben bleibt (gültig in der Umgebung und für
    die geschützten Dreiecke an ihr), und die Nummer seines Rundflecks
    (``-2 - kleinstes Dreieck``, sonst ``-1``).
    """
    count = len(body.faces)
    while True:
        if check_cancelled is not None:
            check_cancelled()
        requests: set[int] = set()
        # Erster Gang, wie :func:`_large_facet_faces_read`: die Flecken der
        # ungeschützten Dreiecke, ihre Kerben, ihr Mantelnachweis.
        first = _closed_by_notches(
            body,
            _soft_groups(np.flatnonzero(zone), neighbours, rows, soft),
            zone,
            loose,
            loose,
            neighbours,
            requests,
        )
        rounded = np.zeros(count, dtype=bool)
        for group, _core in first:
            if check_cancelled is not None:
                check_cancelled()
            patch = in_body_order(body, [group.tolist()])[0]
            if _face_count(body, patch) < MIN_PATCH_FACES or not in_recoverable[patch].any():
                continue
            if _a_sliver(body, patch):
                continue
            if _round_surface(body, mesh, patch, check_cancelled=check_cancelled):
                rounded[np.asarray(patch, dtype=np.int64)] = True
        planar = in_planar & ~rounded
        # **Ein geschütztes Dreieck, das ein Fleck als Kerbe nimmt, wird
        # Rundfleck** und verbindet danach, was an ihm hängt. Gefragt werden die
        # an den gefragten Dreiecken und die, die weich an einem Rundfleck der
        # Umgebung liegen — und nur dort, wo ein Fleck an einer ihrer Ecken
        # überhaupt ausfransen kann (:func:`_frayable`); dann gehören ihre
        # ungeschützten Nachbarn in die Umgebung.
        rough = np.flatnonzero((zone | rounded) & ~planar)
        beside = neighbours[rough]
        touching = (beside >= 0) & soft[np.maximum(rows[rough], 0)]
        watched = np.union1d(start, beside[touching])
        watched = watched[~loose[watched]]
        if len(watched):
            risky = watched[_frayable(body, watched, loose, soft)]
            if len(risky):
                beyond = neighbours[risky].ravel()
                beyond = beyond[beyond >= 0]
                requests.update(beyond[loose[beyond] & ~zone[beyond]].tolist())
        # Zweiter Gang, wie :func:`_surface_owners_read`: die Rundflecken aus
        # allem, was nicht eben ist, und ihre Kerben.
        second = _closed_by_notches(
            body,
            _soft_groups(np.flatnonzero((zone | rounded) & ~planar), neighbours, rows, soft),
            zone,
            loose,
            ~planar,
            neighbours,
            requests,
        )
        if not requests:
            break
        _flood_loose(zone, np.fromiter(requests, dtype=np.int64), loose, neighbours, rows, soft)
    patch_of = np.full(count, -1, dtype=np.int64)
    for group, core in second:
        patch_of[group] = -2 - int(core)
    return planar, patch_of


@dataclass(slots=True)
class _NearSurfaces:
    """Was :func:`_surface_owners_near` an einem Körper gerechnet hat.

    ``zone`` sind die ungeschützten Dreiecke, deren Flecken vollständig
    gerechnet sind — samt allem, wonach sie fragten —, ``planar`` je Dreieck,
    ob es eben bleibt, ``patch_of`` die Nummer seines Rundflecks. Eine neue
    Frage, deren Umgebung darin liegt (:func:`_settled`), liest daraus; sonst
    wächst die Umgebung um ihre, und es wird neu gerechnet. ``worked`` zählt
    die so gerechneten Dreiecke — über die ungeschützten des Körpers hinaus
    rechnet :func:`_surface_owners_near` den ganzen. Das Schloss hält zwei
    Fäden an demselben Körper auseinander.
    """

    zone: np.ndarray | None = None
    planar: np.ndarray | None = None
    patch_of: np.ndarray | None = None
    worked: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


def _settled(
    zone: np.ndarray,
    start: np.ndarray,
    loose: np.ndarray,
    soft: np.ndarray,
    body: trimesh.Trimesh,
    neighbours: np.ndarray,
) -> bool:
    """Ob eine gerechnete Umgebung eine neue Frage schon trägt.

    Jedes ungeschützte Dreieck ihrer Umgebung liegt darin, und an jedem
    geschützten, an dem ein Fleck ausfransen kann (:func:`_frayable`), auch
    seine ungeschützten Nachbarn — dieselben Bedingungen, unter denen
    :func:`_near_surfaces` nichts mehr nachfragt.
    """
    if not bool(zone[start[loose[start]]].all()):
        return False
    guarded = start[~loose[start]]
    if not len(guarded):
        return True
    risky = guarded[_frayable(body, guarded, loose, soft)]
    if not len(risky):
        return True
    beyond = neighbours[risky].ravel()
    beyond = beyond[beyond >= 0]
    return bool(zone[beyond[loose[beyond]]].all())


def _near_owners(
    known: _NearSurfaces, wanted: np.ndarray, label: np.ndarray, facets: Any
) -> np.ndarray:
    """Die Nummern aus :func:`_surface_owners_near` für ``wanted``, gelesen aus ``known``."""
    assert known.planar is not None and known.patch_of is not None
    owners = np.full(len(wanted), -1, dtype=np.int64)
    for place, facet in enumerate(label[wanted].tolist()):
        # Eine Facette trägt ihre Nummer, wenn ihr erstes Dreieck eben blieb.
        if facet >= 0 and known.planar[int(facets[facet][0])]:
            owners[place] = facet
    rounded = known.patch_of[wanted]
    owners[rounded != -1] = rounded[rounded != -1]
    return owners


def _frayable(
    body: trimesh.Trimesh, triangles: np.ndarray, members: np.ndarray, soft: np.ndarray
) -> np.ndarray:
    """Je Dreieck aus ``triangles``, ob an einer seiner Ecken ein Fleck aus ``members``
    ausfransen kann.

    Ausgefranst ist ein Fleck an einer Ecke, an der mehr als zwei seiner
    Randkanten zusammenlaufen (:func:`_rim_of`) — er setzt dort zweimal an.
    Um eine Ecke bilden die Dreiecke aus ``members`` Bögen, die über weiche
    Nähte zusammenhängen, und ein Fleck besteht dort aus ganzen Bögen. Wo es
    höchstens einen gibt, franst an dieser Ecke kein Fleck aus, und kein
    Dreieck dort wird eine Kerbe. Gezählt als Dreiecke minus Nähte am Fächer
    der Ecke, ein geschlossener Kranz als ein Bogen; eine Ecke, deren Fächer
    kein Kranz und kein Bogen ist (eine verzweigte Kante), gilt als ausfransbar.
    """
    corners = np.asarray(body.faces, dtype=np.int64)
    count = len(body.vertices)
    wanted = np.zeros(count, dtype=bool)
    wanted[corners[np.asarray(triangles, dtype=np.int64)].ravel()] = True
    pairs = np.asarray(body.face_adjacency, dtype=np.int64).reshape(-1, 2)
    seams = np.asarray(body.face_adjacency_edges, dtype=np.int64).reshape(-1, 2)
    fan = np.bincount(corners.ravel(), minlength=count)
    around = np.bincount(seams.ravel(), minlength=count)
    at = corners[np.flatnonzero(members)].ravel()
    nodes = np.bincount(at[wanted[at]], minlength=count)
    joined = soft & members[pairs[:, 0]] & members[pairs[:, 1]]
    ends = seams[joined].ravel()
    links = np.bincount(ends[wanted[ends]], minlength=count)
    closed = (nodes > 0) & (nodes == fan) & (links == nodes)
    runs = nodes - links + closed
    irregular = (around != fan) & (around != fan - 1)
    frayable = wanted & ((runs >= 2) | irregular)
    return np.asarray(frayable[corners[np.asarray(triangles, dtype=np.int64)]].any(axis=1))


def _flood_loose(
    zone: np.ndarray,
    seeds: np.ndarray,
    loose: np.ndarray,
    neighbours: np.ndarray,
    rows: np.ndarray,
    soft: np.ndarray,
) -> None:
    """Markiert in ``zone`` die Flecken aus ungeschützten Dreiecken (``loose``) um ``seeds``.

    Über Nähte unter :data:`CURVATURE_LIMIT`, Ring um Ring, wie
    :func:`_patch_around`; ein geschütztes Dreieck unter ``seeds`` bleibt außen.
    """
    frontier = np.unique(np.asarray(seeds, dtype=np.int64))
    frontier = frontier[loose[frontier] & ~zone[frontier]]
    zone[frontier] = True
    while len(frontier):
        near, via = neighbours[frontier].ravel(), rows[frontier].ravel()
        present = near >= 0
        near, via = near[present], via[present]
        frontier = np.unique(near[soft[via] & loose[near] & ~zone[near]])
        zone[frontier] = True


def _soft_groups(
    nodes: np.ndarray, neighbours: np.ndarray, rows: np.ndarray, soft: np.ndarray
) -> list[np.ndarray]:
    """Die Flecken aus ``nodes`` (aufsteigend) über Nähte unter :data:`CURVATURE_LIMIT`.

    Dieselben Gruppen wie :func:`_connected_patches` vor dem Schließen der
    Kerben, in derselben Folge — nach ihrem kleinsten Dreieck —, und jede
    aufsteigend.
    """
    if not len(nodes):
        return []
    beside = neighbours[nodes]
    via = rows[nodes]
    spot = np.minimum(np.searchsorted(nodes, np.maximum(beside, 0)), len(nodes) - 1)
    joined = (beside >= 0) & (nodes[spot] == beside) & soft[np.maximum(via, 0)]
    own = np.broadcast_to(np.arange(len(nodes))[:, None], beside.shape)
    labels = trimesh.graph.connected_component_labels(
        np.column_stack((own[joined], spot[joined])), node_count=len(nodes)
    )
    order = np.argsort(labels, kind="stable")
    starts = np.flatnonzero(np.r_[True, labels[order][1:] != labels[order][:-1]])
    return [nodes[part] for part in np.split(order, starts[1:])]


def _frayed_groups(body: trimesh.Trimesh, groups: list[np.ndarray]) -> np.ndarray:
    """Je Fleck, ob :func:`_rim_of` an ihm eine ausgefranste Ecke fände — für alle in einem Zug.

    Dieselbe Zählung: Randkanten sind die Kanten, die genau ein Dreieck des
    Flecks trägt, ausgefranst ist eine Ecke mit mehr als zwei davon, und ein
    Fleck mit einer dreifach belegten Kante ist unbrauchbar. Je Fleck ein
    ``np.unique`` kostete an einer Umgebung mit Hunderten Flecken mehr als
    alles andere; ausgefranste Flecken sind selten, und nur sie fragen danach
    einzeln.
    """
    found = np.zeros(len(groups), dtype=bool)
    if not groups:
        return found
    sizes = np.fromiter((len(group) for group in groups), dtype=np.int64, count=len(groups))
    owner = np.tile(np.repeat(np.arange(len(groups), dtype=np.int64), sizes), 3)
    corners = len(body.vertices)
    codes = _edge_codes(np.asarray(body.faces)[np.concatenate(groups)], corners)
    known, code_of = np.unique(codes, return_inverse=True)
    keys, uses = np.unique(owner * len(known) + code_of, return_counts=True)
    group_of, edge_of = keys // len(known), keys % len(known)
    broken = np.zeros(len(groups), dtype=bool)
    broken[group_of[uses > 2]] = True
    border = uses == 1
    ends = known[edge_of[border]]
    whose = group_of[border]
    at_ends = np.concatenate((whose * corners + ends // corners, whose * corners + ends % corners))
    places, degrees = np.unique(at_ends, return_counts=True)
    found[places[degrees > 2] // corners] = True
    return found & ~broken


def _closed_by_notches(
    body: trimesh.Trimesh,
    groups: list[np.ndarray],
    zone: np.ndarray,
    loose: np.ndarray,
    faces: np.ndarray,
    neighbours: np.ndarray,
    requests: set[int],
) -> list[tuple[np.ndarray, int]]:
    """:func:`_without_notches` für die Flecken ``groups`` einer Umgebung.

    ``faces`` markiert, was zu einem Fleck gehört und deshalb nie eine Kerbe
    schließt. Zurück kommt je Fleck sein Dreiecke samt geschlossener Kerbe und
    sein kleinstes Dreieck. Entschieden wird eine Kerbe nur, wo alles über sie
    bekannt ist: jeder ungeschützte Nachbar liegt in der Umgebung — sonst
    könnte ein früherer Fleck sie schließen, oder ihr eigener Stand ist offen.
    Was fehlt, landet in ``requests``.
    """
    taken: set[int] = set()
    closed: list[tuple[np.ndarray, int]] = []
    frayed = _frayed_groups(body, groups)
    for group, open_rim in zip(groups, frayed.tolist(), strict=True):
        core = int(group[0])
        members = group.tolist()
        if not open_rim or _face_count(body, members) < MIN_PATCH_FACES:
            closed.append((group, core))
            continue
        rim = _rim_of(body, members)
        if rim is None or not rim.frayed:
            closed.append((group, core))
            continue
        free: list[int] = []
        for face in sorted(_candidates_at(body, members, rim.frayed)):
            around = neighbours[face]
            around = np.append(around[around >= 0], face)
            missing = around[loose[around] & ~zone[around]]
            if len(missing):
                requests.update(missing.tolist())
                continue
            if not faces[face] and face not in taken:
                free.append(face)
        closing = _closing_set(body, rim, free)
        if closing is None:
            closed.append((group, core))
            continue
        taken.update(closing)
        closed.append((np.union1d(group, np.asarray(closing, dtype=np.int64)), core))
    return closed


def facet_middles(
    body: trimesh.Trimesh, check_cancelled: Callable[[], None] | None = None
) -> np.ndarray:
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
    for number, facet in enumerate(body.facets):
        # Je Facette eine Schleifenrunde, am Drachen 3 s am Stück: geprüft wird
        # blockweise. Die Summe je Facette bleibt dieselbe — an ihrer letzten
        # Stelle hängen Radien und Trennungen.
        if check_cancelled is not None and number % FIT_SCAN_BLOCK == 0:
            check_cancelled()
        members = np.asarray(facet)
        weight = areas[members].sum()
        if weight <= EPS_GEOM:
            continue
        middles[members] = (middles[members] * areas[members][:, None]).sum(axis=0) / weight
    return middles


def pair_radii(
    body: trimesh.Trimesh, check_cancelled: Callable[[], None] | None = None
) -> np.ndarray:
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
    points = np.asarray(body.vertices)
    along = points[edges[:, 1]] - points[edges[:, 0]]
    along = along / np.maximum(np.linalg.norm(along, axis=1), EPS_GEOM)[:, None]

    middles = facet_middles(body, check_cancelled)
    span = middles[pairs[:, 1]] - middles[pairs[:, 0]]
    across = np.linalg.norm(span - np.einsum("ij,ij->i", span, along)[:, None] * along, axis=1)
    return np.where(np.degrees(angles) >= FLAT_ANGLE, across / np.maximum(angles, EPS_GEOM), np.inf)


def face_radii(
    body: trimesh.Trimesh, check_cancelled: Callable[[], None] | None = None
) -> np.ndarray:
    """:func:`_face_radii` über alle Nähte des Körpers, einmal je Körper gemerkt.

    Die Nachtrennung liest daraus die Sprünge (:func:`curvature_jumps`), die
    Trennung der Bögen eines Prismas die Radien selbst (:func:`_arcs_of_a_prism`).
    Ein Teilstück, das ein Teiler zerlegt hat, trägt seinen Radius auch in
    seinem Inneren (:func:`_through_the_piece`).
    """
    result: np.ndarray = remembered(
        "face_radii",
        body,
        (),
        lambda: _through_the_piece(
            body,
            _by_origin(
                body,
                _face_radii(
                    body, np.asarray(body.face_adjacency), pair_radii(body, check_cancelled)
                ),
            ),
            check_cancelled,
        ),
        check_cancelled=check_cancelled,
    )
    return result


def _by_origin(body: trimesh.Trimesh, radii: np.ndarray) -> np.ndarray:
    """Je Dreieck der Radius seines Ursprungs vor *Kanten verfeinern* (R1-Rest).

    Der Radius eines Dreiecks ist das Minimum über seine sanften Nachbarn
    (:func:`_face_radii`). Am Original liegt jedes Dreieck einer schmalen
    Facette an ihrem Rand und trägt so den Radius seiner Naht; geteilt haben
    die Stücke im Inneren nur koplanare Nachbarn und damit keinen. Die Stücke
    am alten Rand tragen dagegen genau die Radien der alten Nähte — dieselben
    Facetten, dieselben Knicke —, und ihr Minimum ist der Radius, den das
    Dreieck vorher hatte. Den bekommt jedes Stück desselben Ursprungs; ein
    Dreieck ohne Ursprung behält seinen eigenen. Die Nachtrennung und die
    Bögen eines Prismas lesen danach, was sie am ungeteilten Netz gelesen
    hätten: Am Screen-Cover nach 1 mm stand sonst die Verrundung R 11,2 des
    Schriftzugs in vier Stücken.
    """
    units = refined_units(body)
    if units is None:
        return radii
    keyed = units >= 0
    if not bool(keyed.any()):
        return radii
    lowest = np.full(int(units.max()) + 1, np.inf, dtype=float)
    np.minimum.at(lowest, units[keyed], radii[keyed])
    carried = np.array(radii, dtype=float, copy=True)
    carried[keyed] = lowest[units[keyed]]
    return carried


def _through_the_piece(
    body: trimesh.Trimesh,
    radii: np.ndarray,
    check_cancelled: Callable[[], None] | None = None,
) -> np.ndarray:
    """Ein Teilstück, das ein Teiler zerlegt hat, trägt seinen Radius auch innen (R1).

    Der Radius eines Dreiecks kommt von seinen sanften Nachbarn
    (:func:`_face_radii`). An einem CAD-Netz ist ein Mantelstreifen zwei
    Dreiecke, und jedes liegt an einer Naht zum Nachbarstreifen. *Kanten
    verfeinern* setzt Punkte in den Streifen: Die Dreiecke in seinem Inneren
    haben nur noch koplanare Nachbarn und damit keinen Radius (``inf``), und
    die Bögen eines Prismas (:func:`_arcs_of_a_prism`) trennten an jeder
    Grenze zwischen Innen und Naht. Am Besenhalter nach *Kanten verfeinern*
    2 mm standen so 21 statt 93 Verrundungen und 8 statt 9 Bohrungen im Baum
    — die Bögen waren in gerundeten Seiten aufgegangen (Durchsicht 0.5.1, R1).

    Welche Facette ein solches Teilstück ist, fragt dieselbe Regel wie die
    Zählung (:func:`_divider_pieces`): innere Punkte und höchstens
    :data:`_TESSELLATION_CORNERS` Ecken. Ihre Dreiecke **ganz im Inneren** —
    alle drei Kanten zu Dreiecken derselben Facette — bekommen den kleinsten
    Radius ihrer Nähte, dasselbe Minimum wie :func:`_face_radii`; ein Dreieck
    am Umriss behält seinen eigenen, auch ``inf`` an einer scharfen Kante.
    Und nur, wo die Nähte des Stücks einen Radius nennen: höchstens
    :data:`PRISM_ARC_JUMP` auseinander. Beide Bedingungen sind am Korpus
    gemessen: Ohne sie änderte die Regel zwei ungeteilte Körper — Fächer aus
    vier Dreiecken um einen Mittelpunkt, deren Nähte R 1,4 und R 4,0 zugleich
    lasen, nahmen am Poolbrunnen eine Verrundung R 2 in eine gerundete Seite
    mit und teilten am Gartenschlauchhalter eine R 7,4 in drei. Mit ihnen
    ändert sie an den 553 Körpern keinen. ``minimum.at`` und ``maximum.at``
    hängen nicht von der Reihenfolge ab.
    """
    facets = body.facets
    if not len(facets):
        return radii
    sizes = np.fromiter((len(facet) for facet in facets), dtype=np.int64, count=len(facets))
    # Ein innerer Punkt braucht mindestens drei Dreiecke um sich.
    wanted = np.flatnonzero(sizes >= 3)
    if not len(wanted):
        return radii
    members = np.concatenate([np.asarray(facets[number], dtype=np.int64) for number in wanted])
    owner = np.repeat(np.arange(len(wanted), dtype=np.int64), sizes[wanted])
    fill, value = _piece_filling(
        body, members, owner, sizes[wanted], radii[members], check_cancelled
    )
    if not bool(fill.any()):
        return radii
    carried = np.array(radii, dtype=float, copy=True)
    carried[members[fill]] = value[fill]
    return carried


def _piece_filling(
    body: trimesh.Trimesh,
    members: np.ndarray,
    owner: np.ndarray,
    sizes: np.ndarray,
    values: np.ndarray,
    check_cancelled: Callable[[], None] | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Der Rumpf von :func:`_through_the_piece` für die gegebenen Facetten.

    ``members`` hält ihre Dreiecke hintereinander, ``owner`` je Dreieck die
    Facette (``0 … len(sizes) - 1``), ``values`` seinen Radius. Zurück kommt je
    Dreieck, ob es den Radius seines Teilstücks bekommt, und welchen. Eine
    Stelle für den ganzen Körper und für einzelne Facetten
    (:func:`face_radii_at`): Jede Frage hängt nur an der eigenen Facette, also
    ist die Antwort je Facette dieselbe.
    """
    fill = np.zeros(len(members), dtype=bool)
    value = np.full(len(members), np.inf, dtype=float)
    finite = np.isfinite(values)
    # Gefüllt werden nur Dreiecke ganz im Inneren ihrer Facette, alle drei
    # Kanten zu ihren eigenen: Eines am Umriss hat seine Naht oder eine scharfe
    # Kante, und dort ist ``inf`` die Antwort von ``_face_radii``, nicht eine
    # Lücke. Gezählt am Nachbarindex — dieselben Nähte wie ``face_adjacency``.
    facet_of = np.full(len(body.faces), -1, dtype=np.int64)
    facet_of[members] = owner
    neighbours, _rows = _neighbour_index(body)
    beside = neighbours[members]
    shared = ((beside >= 0) & (facet_of[np.maximum(beside, 0)] == owner[:, None])).sum(axis=1)
    gap = ~finite & (shared == 3)
    # **Den Umriss nur, wo er etwas entscheidet**: an Facetten mit einer
    # solchen Lücke und einem Radius an einer Naht. Für alle übrigen kostete
    # er am Drachen eine Sekunde (2,3 Millionen Dreiecke), am Bett eine halbe.
    asked = (np.bincount(owner, weights=gap, minlength=len(sizes)) > 0) & (
        np.bincount(owner, weights=finite, minlength=len(sizes)) > 0
    )
    if not bool(asked.any()):
        return fill, value
    if check_cancelled is not None:
        check_cancelled()
    chosen = asked[owner]
    renumbered = np.full(len(sizes), -1, dtype=np.int64)
    renumbered[asked] = np.arange(int(asked.sum()), dtype=np.int64)
    kept, kept_owner = members[chosen], renumbered[owner[chosen]]
    kept_values, kept_finite, kept_gap = values[chosen], finite[chosen], gap[chosen]
    corners, inner = _outline_corners(body, kept, kept_owner, np.asarray(sizes)[asked])
    pieces = _divider_pieces(corners, inner)
    if not bool(pieces.any()):
        return fill, value
    lowest = np.full(len(pieces), np.inf, dtype=float)
    np.minimum.at(lowest, kept_owner[kept_finite], kept_values[kept_finite])
    highest = np.full(len(pieces), -np.inf, dtype=float)
    np.maximum.at(highest, kept_owner[kept_finite], kept_values[kept_finite])
    # Nur wo die Nähte des Stücks einen Radius nennen: innerhalb des Sprungs,
    # an dem die Bögen eines Prismas trennen.
    agreed = pieces & np.isfinite(lowest) & (highest <= lowest * (1.0 + PRISM_ARC_JUMP))
    fill[chosen] = kept_gap & agreed[kept_owner]
    value[chosen] = lowest[kept_owner]
    return fill, value


#: Ab welchem Anteil des Körpers :func:`face_radii_at` den ganzen Körper rechnet
#: statt eines weiteren Ausschnitts. Je Dreieck kostet der örtliche Weg etwa
#: das Doppelte — er sammelt je Ausschnitt Facetten, Ursprünge und Nähte ein:
#: Am Gartenschlauchhalter (391 850 Dreiecke) kosteten 30 verstreute
#: Ausschnitte 1,39 s, der ganze Körper 0,63 s (Durchsicht 0.5.1,
#: rest-erkennung2). Ab einem Viertel rechnet die nächste Frage den ganzen
#: Körper, und jede weitere liest seine gemerkte Antwort: Viele Ausschnitte
#: kosten so höchstens anderthalbmal den ganzen Körper, die Nachmessung eines
#: einzelnen Merkmals bleibt weit darunter.
LOCAL_RADII_SHARE: Final = 0.25


def face_radii_at(
    body: trimesh.Trimesh,
    triangles: np.ndarray,
    check_cancelled: Callable[[], None] | None = None,
) -> np.ndarray:
    """:func:`face_radii` für ausgewählte Dreiecke — dieselben Zahlen, ohne das ganze Netz.

    Für die Erkennung an einer Stelle (:func:`curvature_jumps_at`). Der Radius
    eines Dreiecks hängt an seiner Facette (ihr Mittelpunkt, :func:`pair_radii`;
    ihr Teilstück, :func:`_through_the_piece`), an den Facetten seiner
    Nachbarn und nach *Kanten verfeinern* an den übrigen Stücken seines
    Ursprungs (:func:`_by_origin`) — gerechnet wird genau diese Umgebung, mit
    denselben Schritten wie am ganzen Körper: Summen über dieselben Felder in
    derselben Reihenfolge, Minima unabhängig von ihr. Steht die Antwort für den
    ganzen Körper schon im Merker, wird sie gelesen.

    **Was einmal gerechnet ist, steht fest** (:class:`_NearRadii`): Die
    Nachmessung fragt je Merkmal einen Ausschnitt, und benachbarte Ausschnitte
    überdecken sich. Gerechnet wird nur, was noch fehlt; und reichen die
    Fragen zusammen über :data:`LOCAL_RADII_SHARE` des Körpers, rechnet die
    nächste den ganzen Körper (:func:`face_radii`, gemerkt). Viele Ausschnitte
    an einem Körper kosten so höchstens anderthalbmal den ganzen.
    """
    asked = np.asarray(triangles, dtype=np.int64)
    known = _known_answer("face_radii", body)
    if known is not None:
        return np.asarray(known, dtype=float)[asked]
    near: _NearRadii = remembered("radii_near", body, (), _NearRadii)
    with near.lock:
        if near.done is None or near.values is None:
            near.done = np.zeros(len(body.faces), dtype=bool)
            near.values = np.full(len(body.faces), np.inf, dtype=float)
        missing = np.unique(asked[~near.done[asked]])
        if not len(missing):
            return np.asarray(near.values[asked], dtype=float)
        # Gezählt wird, was der Ausschnitt mitliest: Seine Facetten kommen ganz
        # (das Teilstück, :func:`_through_the_piece`), und an einer Platte ist
        # das schon beim ersten Ausschnitt die Deckfläche.
        facets = body.facets
        labels = _facet_of_face(body)
        own = np.unique(labels[missing])
        own = own[own >= 0]
        sizes = np.fromiter((len(facets[number]) for number in own), dtype=np.int64, count=len(own))
        read_whole = np.isin(labels[missing], own[sizes >= 3])
        reach = int((~read_whole).sum()) + int(sizes[sizes >= 3].sum())
        if near.counted + reach > len(body.faces) * LOCAL_RADII_SHARE:
            return np.asarray(face_radii(body, check_cancelled), dtype=float)[asked]
        base, radii = _face_radii_around(body, missing, own, sizes, near, check_cancelled)
        near.values[base] = radii
        near.done[base] = True
        near.counted += len(base)
        return np.asarray(near.values[asked], dtype=float)


@dataclass(slots=True)
class _NearRadii:
    """Was :func:`face_radii_at` an einem Körper gerechnet hat.

    ``done`` je Dreieck, ob sein Radius feststeht, ``values`` der Radius. Er
    steht fest, sobald eine Frage seine Facette, deren Nachbarn und die Stücke
    seines Ursprungs gelesen hat — und das tut jede, die ihn rechnet
    (:func:`_face_radii_around`). ``counted`` zählt die so gerechneten
    Dreiecke gegen :data:`LOCAL_RADII_SHARE`, ``ranking`` sortiert die
    Ursprünge einmal je Körper. Das Schloss hält zwei Fäden an demselben
    Körper auseinander.
    """

    done: np.ndarray | None = None
    values: np.ndarray | None = None
    counted: int = 0
    ranking: np.ndarray | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


def _face_radii_around(
    body: trimesh.Trimesh,
    asked: np.ndarray,
    own: np.ndarray,
    sizes: np.ndarray,
    near: _NearRadii,
    check_cancelled: Callable[[], None] | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Der Rumpf von :func:`face_radii_at`: die Radien von ``asked`` und allen
    Dreiecken ihrer Facetten (``own`` mit ihren Größen ``sizes``), aufsteigend
    — jeder davon endgültig."""
    facets = body.facets
    # Das Teilstück liest die ganze Facette; eine unter drei Dreiecken hat
    # keinen inneren Punkt (dieselbe Grenze wie :func:`_through_the_piece`).
    whole, whole_sizes = own[sizes >= 3], sizes[sizes >= 3]
    members = (
        np.concatenate([np.asarray(facets[number], dtype=np.int64) for number in whole])
        if len(whole)
        else np.zeros(0, dtype=np.int64)
    )
    base = np.union1d(asked, members)
    units = refined_units(body)
    measured = base
    if units is not None:
        # Das Minimum eines Ursprungs liest alle seine Stücke.
        present = np.unique(units[base])
        present = present[present >= 0]
        if len(present):
            if near.ranking is None:
                near.ranking = np.argsort(units, kind="stable")
            ranking = near.ranking
            ranked = units[ranking]
            starts = np.searchsorted(ranked, present, side="left")
            ends = np.searchsorted(ranked, present, side="right")
            pieces = [ranking[start:end] for start, end in zip(starts, ends, strict=True)]
            measured = np.union1d(base, np.concatenate(pieces))
    raw = _face_radii_of(body, measured, check_cancelled)
    if units is not None:
        own_units = units[measured]
        keyed = own_units >= 0
        if bool(keyed.any()):
            lowest = np.full(int(units.max()) + 1, np.inf, dtype=float)
            np.minimum.at(lowest, own_units[keyed], raw[keyed])
            raw = np.array(raw, dtype=float, copy=True)
            raw[keyed] = lowest[own_units[keyed]]
    radii = raw[np.searchsorted(measured, base)]
    if len(whole):
        owner = np.repeat(np.arange(len(whole), dtype=np.int64), whole_sizes)
        values = radii[np.searchsorted(base, members)]
        fill, value = _piece_filling(body, members, owner, whole_sizes, values, check_cancelled)
        if bool(fill.any()):
            radii = np.array(radii, dtype=float, copy=True)
            radii[np.searchsorted(base, members[fill])] = value[fill]
    return base, np.asarray(radii, dtype=float)


def _face_radii_of(
    body: trimesh.Trimesh,
    triangles: np.ndarray,
    check_cancelled: Callable[[], None] | None,
) -> np.ndarray:
    """:func:`_face_radii` für aufsteigend sortierte Dreiecke — das Minimum über ihre
    sanften Nähte."""
    _neighbours, rows = _neighbour_index(body)
    found = np.full(len(triangles), np.inf, dtype=float)
    if not rows.shape[1] or not len(triangles):
        return found
    around = rows[triangles]
    seams = np.unique(around[around >= 0])
    if not len(seams):
        return found
    if check_cancelled is not None:
        check_cancelled()
    radii = _pair_radii_at(body, seams)
    degrees = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float)[seams])
    usable = (degrees < CURVATURE_LIMIT) & np.isfinite(radii)
    values = np.full(around.shape, np.inf, dtype=float)
    present = around >= 0
    spot = np.searchsorted(seams, around[present])
    values[present] = np.where(usable[spot], radii[spot], np.inf)
    return np.asarray(values.min(axis=1), dtype=float)


def _pair_radii_at(body: trimesh.Trimesh, seams: np.ndarray) -> np.ndarray:
    """:func:`pair_radii` für ausgewählte Nähte — dieselben Schritte je Zeile."""
    pairs = np.asarray(body.face_adjacency)[seams]
    angles = np.asarray(body.face_adjacency_angles, dtype=float)[seams]
    edges = np.asarray(body.face_adjacency_edges)[seams]
    points = np.asarray(body.vertices)
    along = points[edges[:, 1]] - points[edges[:, 0]]
    along = along / np.maximum(np.linalg.norm(along, axis=1), EPS_GEOM)[:, None]
    ends = np.unique(pairs.ravel())
    middles = _facet_middles_at(body, ends)
    span = middles[np.searchsorted(ends, pairs[:, 1])] - middles[np.searchsorted(ends, pairs[:, 0])]
    across = np.linalg.norm(span - np.einsum("ij,ij->i", span, along)[:, None] * along, axis=1)
    return np.where(np.degrees(angles) >= FLAT_ANGLE, across / np.maximum(angles, EPS_GEOM), np.inf)


def _facet_middles_at(body: trimesh.Trimesh, triangles: np.ndarray) -> np.ndarray:
    """:func:`facet_middles` für aufsteigend sortierte Dreiecke — je Facette dieselbe Summe."""
    centres = np.asarray(body.triangles_center, dtype=float)
    middles = centres[triangles].copy()
    areas = np.asarray(body.area_faces, dtype=float)
    labels = _facet_of_face(body)[triangles]
    facets = body.facets
    order = np.argsort(labels, kind="stable")
    numbers, starts = np.unique(labels[order], return_index=True)
    ends = np.append(starts[1:], len(order))
    for number, start, end in zip(numbers.tolist(), starts.tolist(), ends.tolist(), strict=True):
        if number < 0:
            continue
        members = np.asarray(facets[number])
        weight = areas[members].sum()
        if weight <= EPS_GEOM:
            continue
        middles[order[start:end]] = (centres[members] * areas[members][:, None]).sum(
            axis=0
        ) / weight
    return np.asarray(middles, dtype=float)


def _pieces_at_a_seam(
    body: trimesh.Trimesh,
    patch: list[int],
    check_cancelled: Callable[[], None] | None = None,
) -> list[list[int]]:
    """Die Stücke eines Flecks beiderseits einer weichen Naht (ERKENNUNG-11).

    Eine Naht ist ein Knick ab :data:`SEAM_ANGLE`, der von **beiden** Seiten
    aus mindestens :data:`SEAM_RATIO`-mal so scharf ist wie jeder andere
    weiche Knick seines Dreiecks, und der ringsum gleich knickt
    (:data:`SEAM_SPREAD`). Zurück kommen die Stücke ab :data:`MIN_PATCH_FACES`
    Dreiecken, in der Ordnung des Körpers — wenn die Nähte den Fleck in
    mindestens zwei teilen; sonst nichts.

    Gefragt wird nur für einen ganzen Fleck, auf den keine Form passt und den
    weder die Krümmung noch ein Prisma geteilt hat (:func:`_fitted`, fünfte
    Runde). Was heute erkannt wird, bleibt deshalb, wie es ist.
    """
    if check_cancelled is not None:
        check_cancelled()
    neighbours, pair_rows = _neighbour_index(body)
    if not neighbours.shape[1] or _face_count(body, patch) < 2 * MIN_PATCH_FACES:
        return []
    local = np.unique(np.asarray(patch, dtype=np.intp))
    chosen = neighbours[local]
    rows = pair_rows[local]
    spot = np.minimum(np.searchsorted(local, np.maximum(chosen, 0)), len(local) - 1)
    inside = (chosen >= 0) & (local[spot] == chosen)
    adjacency_angles = np.asarray(body.face_adjacency_angles, dtype=float)
    angles = np.where(inside, np.degrees(adjacency_angles[np.maximum(rows, 0)]), 0.0)
    soft = inside & (angles < CURVATURE_LIMIT)
    angles = np.where(soft, angles, 0.0)
    # Je Kante eines Dreiecks der schärfste der anderen weichen Knicke — über
    # alle Plätze, denn an einer verzweigten Kante hat ein Dreieck mehr als drei.
    ranked = np.sort(angles, axis=1)
    top = ranked[:, -1:]
    runner_up = ranked[:, -2:-1] if angles.shape[1] > 1 else np.zeros_like(top)
    others = np.where(angles >= top, runner_up, top)
    sharp = soft & (angles >= SEAM_ANGLE) & (angles >= SEAM_RATIO * others)
    # Naht ist, was von beiden Seiten so aussieht: ihre Zeile zweimal.
    seam_rows, seen = np.unique(rows[sharp], return_counts=True)
    seam_rows = seam_rows[seen == 2]
    if not len(seam_rows):
        return []
    seam_angles = np.degrees(adjacency_angles[seam_rows])
    if float(seam_angles.max()) > float(seam_angles.min()) * (1.0 + SEAM_SPREAD):
        return []
    pairs = np.asarray(body.face_adjacency, dtype=np.intp)
    kept_rows = np.unique(rows[soft])
    kept_rows = kept_rows[~np.isin(kept_rows, seam_rows)]
    if check_cancelled is not None:
        check_cancelled()
    groups = trimesh.graph.connected_components(
        np.searchsorted(local, pairs[kept_rows]),
        nodes=np.arange(len(local)),
        engine="scipy",
    )
    pieces = [
        local[group].tolist()
        for group in groups
        if _face_count(body, local[group]) >= MIN_PATCH_FACES
    ]
    if len(pieces) < 2:
        return []
    return in_body_order(body, pieces)


#: Wie weit der erste Keim der tangentialen Trennung im Querschnitt reicht, in
#: Vielfachen der Ausdehnung seiner Keimnaht: genug Streifen für eine
#: Einpassung, ohne über eine Rundung von 90 Grad hinaus in die Nachbarform zu
#: greifen.
_SEED_REACH: Final = 3.0

#: Wie oft die Achse eines Zylinderstücks über seine Ecken nachgeschärft wird
#: (:func:`_sharpened_axis`) — höchstens; ein Schritt unter der Rundung endet früher.
_SHARPEN_STEPS: Final = 6

#: Der Neigungsschritt der Zahlenableitung beim Nachschärfen, im Bogenmaß.
_SHARPEN_TILT: Final = 1e-7


def _tangential_pieces(
    body: trimesh.Trimesh,
    mesh: MeshData,
    patch: Sequence[int],
    check_cancelled: Callable[[], None] | None = None,
) -> list[list[int]]:
    """Die tangentiale Trennung eines Ziels — auch aus dem Gedächtnis eines früheren Körpers.

    **Gemerkt über die Körpergrenze** (RM-592, Konzept §5.4, G3): Nach einem
    Schritt fragt die sechste Runde dieselben unberührten Ziele noch einmal —
    am Eiffelturm 8,4 s der Erkennung. Geschlüsselt nach dem Fleckabdruck
    (:func:`_patch_print`), der Körperdiagonale, aus der die Rechnung
    Verschweißtoleranz und Größengrenze nimmt, und den Schwellen der Trennung
    (:func:`_tangential_settings`). Die Stücke stehen als Lagen im Ziel, wie
    der Aufrufer es reicht, nie als Dreiecksnummern.

    Die Hülle des Körpers steht nicht im Schlüssel: Was die Rechnung
    :func:`cylinder_fits_in_the_body` fragte, wird am neuen Körper noch einmal
    gefragt, und nur wenn jede Antwort gleich ausfällt, gilt die gemerkte.
    Liest die Rechnung über den Ring hinaus — schließt :func:`_without_notches`
    eine Kerbe mit Dreiecken außerhalb —, wird nichts gemerkt.
    """
    if not _ACROSS_BODIES[0] or _face_count(body, patch) < 2 * MIN_PATCH_FACES:
        # Ein kleines Ziel trennt :func:`_tangential_cylinders` gar nicht erst;
        # sein Abdruck kostete mehr als die Antwort.
        return _tangential_pieces_read(body, mesh, patch, check_cancelled)
    extents = np.asarray(body.extents, dtype=float)
    diagonal = math.sqrt(float((extents * extents).sum()))
    key = hashlib.blake2b(
        _patch_print(body, patch, seams=True)
        + _body_numbers(diagonale=diagonal)
        + _exact_bytes(_tangential_settings()),
        digest_size=16,
    ).digest()
    given = np.asarray(list(patch), dtype=np.int64)
    known = _known_across(_TANGENTIAL, body, key)
    if known is not _UNKNOWN:
        places, asked = known
        if "rueckfrage" in _LEFT_OUT or all(
            _cylinder_fits(mesh, axis, radius) == answer for axis, radius, answer in asked
        ):
            return [given[place].tolist() for place in places]
    questions: list[tuple[tuple[float, ...], float, bool]] = []
    beyond: list[bool] = []
    asking = _HULL_QUESTIONS.set(questions)
    reading = _BEYOND.set(beyond)
    try:
        pieces = _tangential_pieces_read(body, mesh, patch, check_cancelled)
    finally:
        _HULL_QUESTIONS.reset(asking)
        _BEYOND.reset(reading)
    if beyond or len(np.unique(given)) != len(given):
        return pieces
    order = np.argsort(given, kind="stable")
    ranked = given[order]
    places = []
    for piece in pieces:
        wanted = np.asarray(piece, dtype=np.int64)
        spot = np.minimum(np.searchsorted(ranked, wanted), len(ranked) - 1)
        if not np.array_equal(ranked[spot], wanted):
            # Ein Stück außerhalb des Ziels hat keine Lage im Fleck.
            return pieces
        places.append(order[spot].astype(np.int32))
    _keep_across(_TANGENTIAL, body, key, (tuple(places), tuple(questions)))
    return pieces


#: Unter diesem Namen hält :func:`_across` die tangentialen Trennungen.
_TANGENTIAL: Final = "tangential_pieces"

#: Unter diesem Namen hält :func:`_across` den Ausgang von ``classify`` je Fleck
#: (:func:`_fitted`, RM-592 G2).
_CLASSIFIED: Final = "classified"


def _classify_settings() -> tuple[Any, ...]:
    """Die Schwellen, die ``classify`` liest — im Schlüssel, weil Tests sie drehen."""
    return (
        MIN_PATCH_FACES,
        CONE_MIN_ANGLE,
        ROUND_WALL_TOLERANCE,
        ROUND_FIT_EVALUATIONS,
        FIT_SOLVER_POINTS,
        EPS_GEOM,
        EPS_ANGLE,
        MIN_ROUND_ARC,
    )


#: Ob eine Rechnung über die Körpergrenze über den ersten Nachbarring hinaus
#: liest (:func:`_without_notches`) — dann merkt sie sich nichts.
_BEYOND: ContextVar[list[bool] | None] = ContextVar("solidon_reads_beyond", default=None)


def _tangential_settings() -> tuple[Any, ...]:
    """Die Schwellen, die die tangentiale Trennung liest — im Schlüssel, weil Tests sie drehen."""
    return (
        MIN_PATCH_FACES,
        MIN_ROUND_ARC,
        UPRIGHT_TO_AXIS,
        FLAT_ANGLE,
        CURVATURE_LIMIT,
        ROUND_WALL_TOLERANCE,
        TANGENTIAL_MIN_LENGTH,
        TANGENTIAL_FIRST_SEEDS,
        TANGENTIAL_FUTILE_SEEDS,
        EPS_GEOM,
        EPS_ANGLE,
        MIN_SURFACE_WIDTH,
        MIN_CYLINDER_DIAMETER,
        NOTCH_AT_MOST,
        _SEED_REACH,
        _SHARPEN_STEPS,
        _SHARPEN_TILT,
    )


def _tangential_pieces_read(
    body: trimesh.Trimesh,
    mesh: MeshData,
    patch: Sequence[int],
    check_cancelled: Callable[[], None] | None = None,
) -> list[list[int]]:
    """Die Stücke eines tangentialen Verbunds aus Rundungen (RM-226) — oder nichts.

    Gefragt wird nur für ein Stück, auf das keine Form passt und das weder
    Krümmung, Prisma noch Naht geteilt haben (:func:`_fitted`, sechste Runde).
    Ein rundum verrundeter Quader, ein verrundetes T, ein Zapfen mit Kehle:
    Zylinder, Kugelecken und Ringe gehen tangential ineinander über und haben
    oft denselben Radius, also trennt sie weder ein Knick noch ein
    Krümmungssprung. Am Netz stand der ganze Verbund als eine gekrümmte
    Fläche da (am T 2 750 von 2 820 Dreiecken), am exakten Körper als 24
    Verrundungen und zwölf Ecken.

    Getrennt wird an den Ecken, nicht an den Nähten: Zuerst fallen die
    Zylinderstücke heraus (:func:`_tangential_cylinders`), der Rest zerfällt
    an ihnen in zusammenhängende Stücke — Kugelecken, Ringe, Übergänge.
    :func:`_fitted` fragt danach jedes Stück wie jedes andere. Ohne Zylinder
    kommt nichts zurück, und der Fleck bleibt, wie er war.

    **Ein Prisma nicht** (:func:`_prism_axis`): Seine Bögen hat die vierte
    Runde schon an jedem Radiuswechsel getrennt und einzeln gefragt
    (:func:`_arcs_of_a_prism`). Hier keimte dagegen jede Naht ein Band über
    die ganze Wand — an den Buchstabenwänden eines Schriftzugs (Herz mit
    Schrift, 20 468 Dreiecke) 320 Flecken mit zusammen 3,3 s für keinen
    Zylinder.
    """
    if _face_count(body, patch) < 2 * MIN_PATCH_FACES:
        # Dieselbe Antwort wie unten (:func:`_tangential_cylinders` trennt so
        # wenig nicht), ohne vorher das Prisma zu fragen — am Eiffelturm 2 800
        # kleine Ziele je Erkennung (RM-592).
        return []
    if _prism_axis(body, patch) is not None:
        return []
    cylinders = _tangential_cylinders(body, mesh, patch, check_cancelled)
    if not cylinders:
        return []
    taken = np.zeros(len(body.faces), dtype=bool)
    for piece in cylinders:
        taken[np.asarray(piece, dtype=np.intp)] = True
    rest = [index for index in dict.fromkeys(int(index) for index in patch) if not taken[index]]
    remainder = _connected_patches(body, rest, check_cancelled) if rest else []
    return in_body_order(body, [*cylinders, *remainder])


def _in_one_plane(body: trimesh.Trimesh, piece: Sequence[int]) -> bool:
    """Ob ein Reststück der tangentialen Trennung eben ist (RM-226).

    Jede Normale bis :data:`EPS_ANGLE` wie die erste — dieselbe Streuung, die
    :func:`_planar_face_entries` einer Fläche zugesteht. Ein Mantelstreifen
    kommt hier nicht an: Die Trennung nimmt jedes Dreieck, dessen Ecken auf
    einem ihrer Zylinder liegen, und die Streifen eines Zylinders, den sie
    nicht fand, hängen zusammen und knicken gegeneinander.
    """
    normals = np.asarray(body.face_normals, dtype=float)[np.asarray(piece, dtype=np.intp)]
    if not len(normals):
        return False
    alike = (normals * normals[0]).sum(axis=1) >= units.exact_cos_degrees(EPS_ANGLE)
    return bool(alike.all())


def _touching_pieces(body: trimesh.Trimesh, pieces: Sequence[Sequence[int]]) -> list[set[int]]:
    """Je Stück einer Trennung die Stücke, an die es über eine Kante grenzt (RM-226).

    Die Stücke decken ihr Ziel ganz ab; ein Nachbar, der in keinem liegt,
    liegt außerhalb des Ziels und steht als ``-1`` da. Gesucht wird über den
    Nachbarindex des Körpers und die sortierten Dreiecke der Stücke, nie über
    ein Feld in Netzgröße je Ziel.
    """
    neighbours, _rows = _neighbour_index(body)
    members = np.concatenate([np.asarray(piece, dtype=np.int64) for piece in pieces])
    labels = np.repeat(
        np.arange(len(pieces), dtype=np.int64),
        np.fromiter((len(piece) for piece in pieces), dtype=np.int64, count=len(pieces)),
    )
    order = np.argsort(members, kind="stable")
    members, labels = members[order], labels[order]
    touching: list[set[int]] = []
    for number, piece in enumerate(pieces):
        around = neighbours[np.asarray(piece, dtype=np.int64)].ravel()
        around = around[around >= 0]
        position = np.minimum(np.searchsorted(members, around), len(members) - 1)
        beside = np.where(members[position] == around, labels[position], -1)
        touching.append({int(other) for other in np.unique(beside) if other != number})
    return touching


def _drawn_chains(
    touching: Sequence[set[int]], fits: Sequence[CylinderFit | None]
) -> list[list[int]]:
    """Zylinderstücke einer Trennung, die zusammen eine gezogene Fläche sind (RM-226).

    Eine Rundung entlang einer gekrümmten Kante — ein Rohr um einen Bogen,
    eine Kante entlang eines geschwungenen Umrisses — ist vernetzt eine Folge
    kurzer Scheiben, jede bis zur Verschweißtoleranz ein Zylinder, die nächste
    um einen Facettenschritt gedreht. Die Trennung las jede als eigene
    Verrundung: am Elegoo-Fettwerkzeug 342 Scheiben R 0,5 von je 0,22 bis
    0,29 mm Länge, um 1,25 bis 2,56 Grad gegeneinander gedreht, an einer
    Gridfinity-Schale die Ecke eines R-1,5-Rands als zwölf Scheiben um je
    3,0 Grad. Am exakten Körper ist das eine Fläche — ein Ring oder eine
    gezogene Fläche —, keine Reihe von Kantenrundungen.

    Zwei Stücke gehören zusammen, wenn sie sich eine Kante teilen, denselben
    Radius tragen (bis :data:`ROUND_WALL_TOLERANCE`) und ihre Achsen weniger
    als :data:`CURVATURE_LIMIT` gegeneinander gedreht sind: Um diesen Winkel
    knicken die beiden Mäntel dort, wo sie sich treffen, und ein Knick darunter
    ist die Stufe einer Rundung, keine Kante — dieselbe Grenze, an der ein
    Fleck endet. Zwei Rundungen, die an einer Ecke zusammenstoßen, drehen um
    die Ecke (an den Regalteilen und am Schaber 90 Grad); die Scheiben eines
    Zugs drehen um einen Facettenschritt (gemessen 1,0 bis 7,9 Grad).
    Parallele Achsen trennen hier nicht: Rundung und Kehle gleichen Radius,
    die sich zu einem S berühren, sind zwei Merkmale. Zurück kommen die Ketten
    mit mindestens zwei Gliedern; :func:`_fitted` fragt jede als ein Stück.
    """
    least = units.exact_cos_degrees(CURVATURE_LIMIT)
    most = units.exact_cos_degrees(EPS_ANGLE)
    parent = list(range(len(fits)))

    def root(number: int) -> int:
        while parent[number] != number:
            parent[number] = parent[parent[number]]
            number = parent[number]
        return number

    for number, fit in enumerate(fits):
        if fit is None:
            continue
        for other in touching[number]:
            partner = fits[other] if other > number else None
            if partner is None or abs(fit.radius - partner.radius) > ROUND_WALL_TOLERANCE:
                continue
            cosine = abs(sum(a * b for a, b in zip(fit.axis, partner.axis, strict=True)))
            if least < cosine <= most:
                parent[root(other)] = root(number)
    groups: dict[int, list[int]] = {}
    for number in range(len(fits)):
        groups.setdefault(root(number), []).append(number)
    return [group for group in groups.values() if len(group) > 1]


def _enclosed_rounds(
    touching: Sequence[set[int]], settled: Sequence[bool], flat: Sequence[bool]
) -> set[int]:
    """Belegte Stücke, die nur an den unerklärten Rest ihres Ziels grenzen (RM-226).

    Eine Rundform endet an etwas: an einer Fläche, an einer anderen Rundform,
    an einem Knick oder Krümmungssprung, also am Rand ihres Ziels. Ein
    Zylinderstück, das ringsum in den Rest übergeht, aus dem es gelesen wurde,
    ist ein Stück dieses Rests. Am Baum mit Tablett lagen sechs solche Stücke
    von sechs bis sieben Dreiecken in einem glatten Krümmungsstück aus
    172 356 Dreiecken, mit sechs verschiedenen Radien zwischen R 0,92 und
    R 4,54 — genug, um das Freiformurteil zu kippen (Anteil 0,759 → 0,678).

    Ein Stück steht, solange es an den Rand des Ziels (``-1``), an ein ebenes
    Reststück oder an ein stehendes Stück grenzt. Was fällt, nimmt anderen
    ihren Halt; gefragt wird, bis nichts mehr fällt. Das Ergebnis hängt nicht
    an der Reihenfolge: Fallen nimmt nur Halt weg.
    """
    standing = list(settled)
    enclosed: set[int] = set()
    changed = True
    while changed:
        changed = False
        for number, beside in enumerate(touching):
            if not standing[number]:
                continue
            if any(other < 0 or standing[other] or flat[other] for other in beside):
                continue
            standing[number] = False
            enclosed.add(number)
            changed = True
    return enclosed


def _tangential_cylinders(
    body: trimesh.Trimesh,
    mesh: MeshData,
    patch: Sequence[int],
    check_cancelled: Callable[[], None] | None = None,
) -> list[list[int]]:
    """Die Zylinderstücke eines tangentialen Flecks, belegt an ihren Ecken (RM-226).

    **Ein Keim je geknickter Naht**, die längste zuerst — die Mantellinien
    langer Rundungen vor den Splittern einer Kugelecke. Die Achse des Keims
    ist das Kreuzprodukt der beiden Facettennormalen. Um ihn liegt ein
    Prismaband: alle verbundenen freien Dreiecke, deren Normale bis
    :data:`FLAT_ANGLE` quer zu dieser Achse steht. Liegt an den zwei
    Keimdreiecken kein solcher Nachbar, bleibt das Band unter
    :data:`MIN_PATCH_FACES`, und die Naht keimt gar nicht — an einer
    Kugelecke fast jede. Der erste Kreis geht durch die Ecken der
    Banddreiecke nahe der Keimnaht (:func:`_band_seed`) — aus einer einzigen
    Naht ist ein Kreis an langen, schmalen Dreiecken schlecht bestimmt: Am
    gerundeten T lieferten die Nähte derselben Rundung R 3 bis R 34.

    **Dann entscheiden die Ecken.** Das Stück wächst neu über Dreiecke, deren
    Normale quer zur Achse steht und deren drei Ecken auf dem eingepassten
    Zylinder liegen: erst bis :data:`ROUND_WALL_TOLERANCE`, dann bis zur
    zehnfachen und zuletzt, bis es stillsteht, bis zur einfachen
    Verschweißtoleranz, mit neuer Einpassung nach jedem Schritt. Eingepasst
    wird über die Ecken (:func:`_sharpened_axis`), nicht über das
    Normalenmoment von :func:`fit_cylinder`: Das neigt die Achse an
    verdrillt vernetzten Rundungen um bis zu 0,024 Grad, und die Ecken lägen
    dann bis zu 0,003 mm daneben, obwohl sie auf 0,0000026 mm genau auf dem
    Zylinder sitzen. Mitgenommene Polsplitter einer Kugelecke (0,0004 mm
    daneben) verziehen die Achse der lockeren Stufe; erst die wiederholte
    enge Stufe gibt die Rundung ganz. Den vollen Zylinderfit bekommt nur das
    fertige Stück — je Keim und Stufe gerechnet, war er zwei Drittel der
    Laufzeit.

    Angenommen wird ein Stück, das ein gezeichneter Bogen ist — alle Ecken bis
    zur Verschweißtoleranz auf dem Kreis, die Bedingung von
    :func:`_exactly_an_arc` —, mindestens :data:`MIN_ROUND_ARC` zeigt, in den
    Körper passt (:func:`cylinder_fits_in_the_body`), mindestens
    :data:`TANGENTIAL_MIN_LENGTH` seines Radius lang ist und als Verrundung
    überhaupt einen Namen bekäme (:func:`_fillets_worth_naming`: nicht zu
    klein, kein Streifen). **Was verworfen ist, keimt nicht noch einmal**:
    Ein Band, das schon entlang der Achse zu kurz ist (ein Ring einer Kugel
    oder eines Wulsts), und eines, dessen lockeres Stück ein Streifen ist (eine
    Ausrundung mit wanderndem Radius), sind ganz verbraucht; eine Spalte und
    ein zu kleines oder zu kurzes Stück mit ihren Dreiecken. Am Würfel mit
    gerundeten Kanten (250 488 Dreiecke) keimten sonst über 4 000 Nähte für
    keinen Zylinder. **Und ein Ziel, an dem :data:`TANGENTIAL_FIRST_SEEDS`
    Keime vor dem ersten Stück oder :data:`TANGENTIAL_FUTILE_SEEDS` danach in
    Folge nichts tragen, ist kein Verbund aus Rundungen**: Die Suche endet.
    """
    if check_cancelled is not None:
        check_cancelled()
    indices = np.unique(np.asarray(list(patch), dtype=np.intp))
    if _face_count(body, indices) < 2 * MIN_PATCH_FACES:
        return []
    count = len(body.faces)
    member = np.zeros(count, dtype=bool)
    member[indices] = True
    # Die Nähte des Flecks über den Nachbarindex des Körpers, nicht über alle
    # Paare des Netzes: Ein Durchgang über ``face_adjacency`` je Fleck wäre bei
    # vielen Flecken ein Ganznetz-Durchlauf je Fleck. Jede Naht einmal.
    neighbours, rows = _neighbour_index(body)
    if not neighbours.shape[1]:
        return []
    beside = neighbours[indices]
    own = np.broadcast_to(indices[:, None], beside.shape)
    inner = (beside > own) & member[np.where(beside >= 0, beside, 0)]
    rows_of_seams = rows[indices][inner]
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float)[rows_of_seams])
    bends = (angles > FLAT_ANGLE) & (angles < CURVATURE_LIMIT)
    if not bends.any():
        return []
    bending = rows_of_seams[bends]
    # **Die Ordnung des Körpers, nicht die der Datei** (RM-210, RM-592): Keime,
    # Bänder und Stücke folgen dem Platz ihrer Dreiecke in :func:`in_body_order`,
    # und jede Naht wird von ihrem Dreieck mit dem kleineren Platz aus gesehen.
    # Nach der Dreiecksnummer summierten die Kreise der Keime in anderer Folge,
    # sobald die Datei anders ordnete — andere letzte Stellen an den Schwellen
    # der Trennung, und ein Gedächtnis je Fleck müsste die Folge mitschlüsseln.
    # Deckungsgleiche Dreiecke ordnet :func:`in_body_order` nach ihrer Folge im
    # Fleck, nicht nach ihrer Nummer.
    place = np.zeros(count, dtype=np.int64)
    in_order = in_body_order(body, [list(dict.fromkeys(int(index) for index in patch))])[0]
    place[np.asarray(in_order, dtype=np.intp)] = np.arange(len(in_order))
    pairs = np.column_stack((own[inner][bends], beside[inner][bends]))
    sides = np.where((place[pairs[:, 0]] > place[pairs[:, 1]])[:, None], pairs[:, ::-1], pairs)
    vertices = np.asarray(body.vertices, dtype=float)
    faces = np.asarray(body.faces, dtype=np.intp)
    normals = np.asarray(body.face_normals, dtype=float)
    areas = np.asarray(body.area_faces, dtype=float)
    upright = units.exact_sin_degrees(FLAT_ANGLE)
    # Die Keimachsen aller Nähte in einem Zug, und welche Naht überhaupt ein
    # Band trägt: einen weiteren Nachbarn quer zur Achse an einem der zwei
    # Keimdreiecke — ohne ihn bleibt es bei zweien, unter MIN_PATCH_FACES.
    seed_axes = np.cross(normals[sides[:, 0]], normals[sides[:, 1]])
    seed_axes = seed_axes / np.sqrt((seed_axes * seed_axes).sum(axis=1))[:, None]
    around_seed = np.concatenate((neighbours[sides[:, 0]], neighbours[sides[:, 1]]), axis=1)
    beside = (around_seed >= 0) & (around_seed != sides[:, :1]) & (around_seed != sides[:, 1:])
    reached = np.where(beside, around_seed, 0)
    beside &= member[reached]
    tilt = np.abs((normals[reached] * seed_axes[:, None, :]).sum(axis=2))
    carries_a_band = (beside & (tilt <= upright)).any(axis=1)
    if not carries_a_band.any():
        return []
    seams = np.asarray(body.face_adjacency_edges, dtype=np.intp)[bending]
    along_seam = vertices[seams[:, 1]] - vertices[seams[:, 0]]
    seam_lengths = np.sqrt((along_seam * along_seam).sum(axis=1))
    # Gleich lange Nähte in der Folge ihrer Kanten, und die folgt den
    # Eckennummern — wie die Nummern gleich großer Flächen (:func:`_largest_first`)
    # nicht der Dreiecksfolge und nicht der Lage, also keine Wahl nach der
    # Ordnung des Körpers (``kern.md``).
    order = np.lexsort((bending, -seam_lengths))
    order = order[carries_a_band[order]]
    extents = np.asarray(body.extents, dtype=float)
    diagonal = math.sqrt(float((extents * extents).sum()))
    weld = weld_tolerance(diagonal)
    claimed = np.zeros(count, dtype=bool)
    spent = np.zeros(count, dtype=bool)
    # Wer in welcher Flutung schon gesehen wurde, als Nummer der Flutung: ein
    # Feld für alle, statt je Flutung eines in Netzgröße.
    seen = np.zeros(count, dtype=np.int32)
    floods = 0
    found: list[list[int]] = []
    # Vergebliche Keime seit dem Anfang oder dem letzten Treffer
    # (:data:`TANGENTIAL_FIRST_SEEDS`, :data:`TANGENTIAL_FUTILE_SEEDS`).
    futile = 0

    def flood(start: Sequence[int], accept: Callable[[np.ndarray], np.ndarray]) -> list[int]:
        """Die freien Fleckdreiecke, die ``accept`` zulässt und mit ``start`` zusammenhängen.

        Gefragt wird nur an den Dreiecken der wachsenden Front, nie am ganzen
        Fleck: Ein Keim kostet so viel, wie sein Stück groß ist.
        """
        nonlocal floods
        front = np.unique(np.asarray(start, dtype=np.intp))
        if not len(front):
            return []
        floods += 1
        seen[front] = floods
        taken = [front]
        while len(front):
            # Je Ring einmal entdoppelt: Ein Dreieck, das zwei Frontdreiecke
            # zugleich erreichen, stünde sonst zweimal in der nächsten Front,
            # und seine Nachfolger vervielfachten sich von Ring zu Ring.
            # Erst sieben, dann entdoppeln: Die meisten Nachbarn einer Front
            # sind schon gesehen, und das Sortieren über die kleine Rest-
            # menge gibt dieselben Dreiecke in derselben Folge (RM-568).
            around = neighbours[front].ravel()
            around = around[around >= 0]
            around = np.unique(around[member[around] & ~claimed[around] & (seen[around] != floods)])
            seen[around] = floods
            if not len(around):
                break
            front = around[accept(around)]
            taken.append(front)
        merged = np.concatenate(taken)
        return [int(triangle) for triangle in merged[np.argsort(place[merged], kind="stable")]]

    def upright_to(axis: np.ndarray) -> Callable[[np.ndarray], np.ndarray]:
        """Ob die Normale bis :data:`FLAT_ANGLE` quer zur Achse steht."""
        return lambda triangles: np.abs((normals[triangles] * axis).sum(axis=1)) <= upright

    def on_the_cylinder(
        axis: np.ndarray, centre: np.ndarray, radius: float, limit: float
    ) -> Callable[[np.ndarray], np.ndarray]:
        """Normale quer zur Achse und alle drei Ecken bis ``limit`` auf dem Mantel."""

        def accept(triangles: np.ndarray) -> np.ndarray:
            relative = vertices[faces[triangles]] - centre
            radial = relative - ((relative * axis).sum(axis=2))[:, :, None] * axis
            off = np.abs(np.sqrt((radial * radial).sum(axis=2)) - radius).max(axis=1)
            return np.asarray(upright_to(axis)(triangles) & (off <= limit), dtype=bool)

        return accept

    def axial_extent(region: Sequence[int], axis: np.ndarray) -> float:
        """Wie lang das Stück entlang der Achse ist, über seine Ecken."""
        corners = vertices[np.unique(faces[np.asarray(region, dtype=np.intp)])]
        along = (corners * axis).sum(axis=1)
        return float(along.max() - along.min())

    for index in order.tolist():
        if check_cancelled is not None:
            check_cancelled()
        first, second = (int(value) for value in sides[index])
        if claimed[first] or claimed[second] or (spent[first] and spent[second]):
            continue
        if futile >= (TANGENTIAL_FUTILE_SEEDS if found else TANGENTIAL_FIRST_SEEDS):
            break
        futile += 1
        band = flood((first, second), upright_to(seed_axes[index]))
        if _face_count(body, band) < MIN_PATCH_FACES:
            # Nicht verbraucht: Dasselbe Dreieck liegt für die Achse seiner
            # eigenen Rundung in einem anderen, größeren Band.
            continue
        seed, axis = _band_seed(vertices, faces, normals, areas, band, (first, second))
        if _face_count(body, seed) < MIN_PATCH_FACES:
            continue
        circle = _seed_circle(vertices, faces, seed, axis)
        if circle is None:
            continue
        centre, radius = circle
        if 2.0 * radius > diagonal:
            # Ein Kreis, weiter als der ganze Körper, passt nie in ihn
            # (:func:`cylinder_fits_in_the_body`) — eine fast ebene Stelle.
            continue
        if axial_extent(band, axis) < TANGENTIAL_MIN_LENGTH * radius:
            # Schon das ganze Band ist entlang der Achse zu kurz; jedes Stück
            # darin wäre es auch. Verbraucht wird das Band, sonst keimte jede
            # Naht desselben Rings noch einmal.
            spent[np.asarray(band, dtype=np.intp)] = True
            continue
        error = math.inf
        region: list[int] = seed
        loose: list[int] = []
        for stage, limit in enumerate((ROUND_WALL_TOLERANCE, 10.0 * weld, weld, weld, weld)):
            accept = on_the_cylinder(axis, centre, radius, limit)
            previous = np.asarray(region, dtype=np.intp)
            start = previous[accept(previous)]
            grown = flood(start, accept) if len(start) else []
            if _face_count(body, grown) < MIN_PATCH_FACES:
                spent[np.asarray(loose, dtype=np.intp)] = True
                region = []
                break
            if stage > 2 and grown == region:
                # Steht still: Achse und Fehler der letzten Stufe gelten weiter.
                break
            region = grown
            if stage == 0:
                loose = region
                if axial_extent(region, axis) < TANGENTIAL_MIN_LENGTH * radius or _a_sliver(
                    body, region
                ):
                    # Eine Spalte eines Rings oder einer Kugel, schon locker zu
                    # kurz — oder ein Streifen, schon locker zu schmal für eine
                    # Fläche; die engeren Stufen machen ihn nicht breiter. Ein
                    # Streifen liegt auf einer Ausrundung, deren Radius wandert:
                    # Verbraucht wird ihr ganzes Band, sonst keimte jeder
                    # Streifen daneben noch einmal.
                    spent[np.asarray(band, dtype=np.intp)] = True
                    spent[np.asarray(region, dtype=np.intp)] = True
                    region = []
                    break
            sharpened = _sharpened_axis(
                vertices[np.unique(faces[np.asarray(region, dtype=np.intp)])], axis
            )
            if sharpened is None:
                region = []
                break
            axis, centre, radius, error = sharpened
        if not region or error > weld:
            continue
        if _too_small_to_make(2.0 * radius) or _a_sliver(body, region):
            # Was für kein Werkzeug groß genug oder zu schmal ist, wird auch
            # keine Verrundung (:func:`_fillets_worth_naming`) — am
            # Minigolfstück 1 457 Rundungen R 0,1 bis 0,2, am Würfel zwölf
            # Streifen von elf Grad, jedes danach noch eingepasst und verworfen.
            spent[np.asarray(region, dtype=np.intp)] = True
            continue
        # Den vollen Zylinderfit rechnet ``classify`` am angenommenen Stück;
        # hier entscheiden die nachgeschärfte Achse und ihr Kreis, die teure
        # Frage nach dem Körper zuletzt.
        if span_about(body, axis, centre, region) < MIN_ROUND_ARC:
            continue
        if axial_extent(region, axis) < TANGENTIAL_MIN_LENGTH * radius:
            spent[np.asarray(region, dtype=np.intp)] = True
            continue
        if not cylinder_fits_in_the_body(mesh, tuple(float(value) for value in axis), radius):
            continue
        claimed[np.asarray(region, dtype=np.intp)] = True
        found.append(region)
        futile = 0
    return found


def _band_seed(
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    areas: np.ndarray,
    band: Sequence[int],
    seam: tuple[int, int],
) -> tuple[list[int], np.ndarray]:
    """Die Banddreiecke, deren Ecken im Querschnitt nahe der Keimnaht liegen — und die Achse.

    Die Achse des Bandes ist der Eigenvektor seines flächengewichteten
    Normalenmoments mit dem kleinsten Eigenwert (:func:`units.symmetric_eigen3`,
    ohne LAPACK). Quer dazu projiziert liegen die Ecken eines Prismas auf
    seinem Umriss; der Keim nimmt, was dort höchstens :data:`_SEED_REACH`-mal
    so weit von der Mitte der Keimnaht liegt wie deren eigene Ecken.
    """
    chosen = np.asarray(band, dtype=np.intp)
    weighted = normals[chosen] * areas[chosen][:, None]
    moment = [
        [float((weighted[:, row] * normals[chosen][:, column]).sum()) for column in range(3)]
        for row in range(3)
    ]
    _values, vectors = units.symmetric_eigen3(moment)
    axis = np.asarray(vectors[0], dtype=float)
    corners = vertices[faces[chosen]]
    flat = corners - ((corners * axis).sum(axis=2))[:, :, None] * axis
    own = vertices[faces[np.asarray(seam, dtype=np.intp)]].reshape(-1, 3)
    own_flat = own - ((own * axis).sum(axis=1))[:, None] * axis
    middle = own_flat.mean(axis=0)
    offset = own_flat - middle
    reach = _SEED_REACH * math.sqrt(float((offset * offset).sum(axis=1).max()))
    gap = flat - middle
    distance = np.sqrt((gap * gap).sum(axis=2)).max(axis=1)
    return [int(triangle) for triangle in chosen[distance <= reach]], axis


def _seed_circle(
    vertices: np.ndarray, faces: np.ndarray, seed: Sequence[int], axis: np.ndarray
) -> tuple[np.ndarray, float] | None:
    """Der erste Kreis eines Keims, ohne die Dreiecke, die tangential von ihm weglaufen.

    Mit dem Band kommen auch ebene Dreiecke in den Keim, die quer zur Achse
    stehen: die Flächen, in die eine Rundung tangential übergeht. Ihre fernen
    Ecken liegen Millimeter neben dem Kreis und ziehen die lineare Einpassung
    (:func:`_circle_across`) mit — am gerundeten T R 3 so weit, dass von den
    21 Dreiecken einer Rundung keines mehr bis :data:`ROUND_WALL_TOLERANCE`
    auf ihm lag. Deshalb fällt je Runde jedes Dreieck, dessen fernste Ecke in
    der ferneren Hälfte des Fehlerbereichs liegt, bis alle übrigen bis
    :data:`ROUND_WALL_TOLERANCE` auf dem Kreis liegen; bleiben weniger als
    :data:`MIN_PATCH_FACES`, gibt es keinen. Ein Dreieck je Runde brauchte
    am fein vernetzten Quader R 8 (Durchbiegung 0,002 mm) bis zu 431 Runden
    für einen Keim aus 468 Dreiecken, halbierend höchstens zwölf. Zurück
    kommen Mitte und Radius.
    """
    first, second = _across_pair(axis)
    corners = vertices[faces[np.asarray(seed, dtype=np.intp)]]
    origin = corners.reshape(-1, 3).mean(axis=0)
    relative = corners - origin
    # Je Dreieck seine drei Ecken im Querschnitt, einmal gerechnet; eine
    # gemeinsame Ecke zählt je Dreieck mit.
    x = (relative * first).sum(axis=2)
    y = (relative * second).sum(axis=2)
    keep = np.ones(len(x), dtype=bool)
    while int(keep.sum()) >= MIN_PATCH_FACES:
        circle = _kasa_circle(x[keep].ravel(), y[keep].ravel())
        if circle is None:
            return None
        centre_x, centre_y, radius = circle
        dx, dy = x - centre_x, y - centre_y
        off = np.abs(np.sqrt(dx * dx + dy * dy) - radius).max(axis=1)
        worst = float(off[keep].max())
        if worst <= ROUND_WALL_TOLERANCE:
            return origin + centre_x * first + centre_y * second, radius
        # Die fernere Hälfte des Fehlerbereichs fällt, mindestens das fernste
        # Dreieck: Nach wenigen Runden steht der Kreis oder es bleibt zu wenig.
        keep &= off < max(ROUND_WALL_TOLERANCE, worst / 2.0)
    return None


def _sharpened_axis(
    points: np.ndarray, axis: np.ndarray
) -> tuple[np.ndarray, np.ndarray, float, float] | None:
    """Die Achse eines Zylinders über seine Ecken nachgeführt: Achse, Mitte, Radius, Fehler.

    Für eine Achse liegen die quer projizierten Ecken auf einem Kreis, den
    :func:`_circle_across` linear einpasst. Gauß-Newton über die zwei
    Neigungen der Achse senkt die Abstände der Ecken von diesem Kreis; die
    Ableitung ist eine Differenz über :data:`_SHARPEN_TILT`, das 2x2-System
    löst die Cramersche Regel — nur Grundrechenarten und Wurzeln, auf jeder
    Maschine dieselben Bits. Höchstens :data:`_SHARPEN_STEPS` Schritte, und
    keiner mehr, sobald ein Schritt keine Ecke um mehr als :data:`EPS_GEOM`
    bewegt: Danach schwankt nur noch das Rauschen der Ecken (am gerundeten T
    um 0,0000003 mm), und jeder weitere Schritt kostete drei Einpassungen.
    Der Fehler ist der größte Eckenabstand vom Zylinder in mm; ``None`` ohne
    Kreis.
    """
    current = np.asarray(axis, dtype=float)
    current = current / math.sqrt(float((current * current).sum()))
    offsets = points - points.mean(axis=0)
    reach = math.sqrt(float((offsets * offsets).sum(axis=1).max()))
    for _step in range(_SHARPEN_STEPS):
        base = _circle_across(points, current)
        if base is None:
            return None
        first, second = _across_pair(current)
        columns = []
        for direction in (first, second):
            tilted = current + _SHARPEN_TILT * direction
            tilted = tilted / math.sqrt(float((tilted * tilted).sum()))
            moved = _circle_across(points, tilted)
            if moved is None:
                return None
            columns.append((moved[2] - base[2]) / _SHARPEN_TILT)
        one, two = columns
        a11 = float((one * one).sum())
        a12 = float((one * two).sum())
        a22 = float((two * two).sum())
        b1 = -float((one * base[2]).sum())
        b2 = -float((two * base[2]).sum())
        determinant = a11 * a22 - a12 * a12
        if determinant <= EPS_GEOM * EPS_GEOM * max(a11 * a22, EPS_GEOM):
            break
        u = (b1 * a22 - b2 * a12) / determinant
        v = (a11 * b2 - a12 * b1) / determinant
        current = current + u * first + v * second
        current = current / math.sqrt(float((current * current).sum()))
        if max(abs(u), abs(v)) * reach <= EPS_GEOM:
            break
    final = _circle_across(points, current)
    if final is None:
        return None
    centre, radius, distances = final
    return current, centre, radius, float(distances.max())


def _across_pair(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Zwei Einheitsvektoren quer zur Achse und zueinander — in reiner Gleitkommarechnung."""
    ax, ay, az = float(axis[0]), float(axis[1]), float(axis[2])
    hx, hy, hz = (1.0, 0.0, 0.0) if abs(ax) < 0.9 else (0.0, 1.0, 0.0)
    fx, fy, fz = ay * hz - az * hy, az * hx - ax * hz, ax * hy - ay * hx
    length = math.sqrt(fx * fx + fy * fy + fz * fz)
    fx, fy, fz = fx / length, fy / length, fz / length
    return (
        np.asarray((fx, fy, fz), dtype=float),
        np.asarray((ay * fz - az * fy, az * fx - ax * fz, ax * fy - ay * fx), dtype=float),
    )


def _circle_across(
    points: np.ndarray, axis: np.ndarray
) -> tuple[np.ndarray, float, np.ndarray] | None:
    """Der Kreis der quer zur Achse projizierten Punkte: Mitte, Radius, Abstände.

    Eingepasst von :func:`_kasa_circle`. Die Mitte liegt in der Ebene durch
    den Schwerpunkt der Punkte; ``None`` ohne bestimmten Kreis.
    """
    first, second = _across_pair(axis)
    origin = points.mean(axis=0)
    relative = points - origin
    x = (relative * first).sum(axis=1)
    y = (relative * second).sum(axis=1)
    circle = _kasa_circle(x, y)
    if circle is None:
        return None
    centre_x, centre_y, radius = circle
    dx, dy = x - centre_x, y - centre_y
    centre = origin + centre_x * first + centre_y * second
    return centre, radius, np.abs(np.sqrt(dx * dx + dy * dy) - radius)


def _kasa_circle(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float] | None:
    """Der Kreis durch ebene Punkte, linear eingepasst: Mitte x, Mitte y, Radius.

    Über ``x² + y² + D·x + E·y + F = 0`` und die drei Normalgleichungen,
    gelöst mit der Cramerschen Regel — nur Grundrechenarten, kein LAPACK.
    ``None`` ohne bestimmten Kreis.
    """
    z = -(x * x + y * y)
    sxx, sxy, syy = float((x * x).sum()), float((x * y).sum()), float((y * y).sum())
    sx, sy, size = float(x.sum()), float(y.sum()), float(len(x))
    bx, by, bz = float((x * z).sum()), float((y * z).sum()), float(z.sum())
    whole = _determinant3(((sxx, sxy, sx), (sxy, syy, sy), (sx, sy, size)))
    if abs(whole) <= EPS_GEOM * EPS_GEOM:
        return None
    d = _determinant3(((bx, sxy, sx), (by, syy, sy), (bz, sy, size))) / whole
    e = _determinant3(((sxx, bx, sx), (sxy, by, sy), (sx, bz, size))) / whole
    f = _determinant3(((sxx, sxy, bx), (sxy, syy, by), (sx, sy, bz))) / whole
    centre_x, centre_y = -d / 2.0, -e / 2.0
    squared = centre_x * centre_x + centre_y * centre_y - f
    if squared <= 0.0:
        return None
    return centre_x, centre_y, math.sqrt(squared)


def _determinant3(rows: Sequence[Sequence[float]]) -> float:
    """Die Determinante einer 3x3-Matrix, ausgeschrieben."""
    return (
        rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
        - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
        + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
    )


def _arcs_of_a_prism(
    body: trimesh.Trimesh,
    piece: Sequence[int],
    check_cancelled: Callable[[], None] | None = None,
) -> list[list[int]]:
    """Die Bögen und Geraden eines Prismas, getrennt an jedem Radiuswechsel — oder nichts.

    Prisma heißt: Jede Normale steht quer zu einer Achse, im Vertrag von
    :data:`UPRIGHT_TO_AXIS` wie bei :func:`fit_cylinder`. Die Achse ist das
    Kreuzprodukt der ersten Normale mit der, die am meisten quer zu ihr
    steht; steht keine um :data:`MIN_ROUND_ARC` quer, trägt das Stück keinen
    Bogen, der zählte — auch zwei gegenüberliegende ebene Seiten nicht.
    Getrennt wird, wo sich der Radius zweier Nachbarn um
    mehr als :data:`PRISM_ARC_JUMP` ändert und wo ein Bogen in eine Gerade
    übergeht (ein Radius endlich, der andere nicht, :func:`face_radii`) —
    aber nur, wenn die Radien ruhig sind: Springen sie an mehr als
    :data:`PRISM_QUIET_SHARE` der Nähte, ist die Schätzung Rauschen, und
    getrennt wird nichts. Zurück kommen die Stücke in der Ordnung des Körpers,
    und nur, wenn es mehr als eines sind.

    Gelesen wird am Nachbarindex und in der Nummerierung des Stücks, ohne Feld
    über das ganze Netz — ein solches je Fleck kostete am Puppenhausbett über
    30 Sekunden. Entschieden wird mit Grundrechenarten (RM-187); die Winkel
    kommen aus ``face_adjacency_angles`` wie bei der Nachtrennung.
    """
    indices = np.asarray(piece, dtype=np.intp)
    if _face_count(body, indices) < MIN_PATCH_FACES or _prism_axis(body, indices) is None:
        return []
    radii = face_radii(body, check_cancelled)
    neighbours, rows = _neighbour_index(body)
    ordered = np.sort(indices)
    beside = neighbours[ordered]
    spot = np.minimum(np.searchsorted(ordered, np.maximum(beside, 0)), len(ordered) - 1)
    member = (beside >= 0) & (ordered[spot] == beside)
    # Jede Naht zweimal gesehen, einmal von jeder Seite: Die kleinere Nummer spricht.
    own = np.broadcast_to(np.arange(len(ordered))[:, None], beside.shape)
    use = member & (spot > own)
    near, far = radii[ordered[own[use]]], radii[ordered[spot[use]]]
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float)[rows[ordered][use]])
    rounded = np.isfinite(near) & np.isfinite(far)
    steady = ~np.isfinite(near) & ~np.isfinite(far)
    steady[rounded] = np.abs(near[rounded] - far[rounded]) <= PRISM_ARC_JUMP * np.maximum(
        near[rounded], far[rounded]
    )
    jumping = int(np.count_nonzero(rounded & ~steady))
    if jumping > PRISM_QUIET_SHARE * int(np.count_nonzero(rounded)):
        return []
    keep = steady & (angles < CURVATURE_LIMIT)
    if check_cancelled is not None:
        check_cancelled()
    groups = trimesh.graph.connected_components(
        np.column_stack((own[use][keep], spot[use][keep])),
        nodes=np.arange(len(ordered)),
        engine="scipy",
    )
    if len(groups) < 2:
        return []
    return in_body_order(body, [ordered[np.asarray(group)].tolist() for group in groups])


def _prism_axis(body: trimesh.Trimesh, piece: Sequence[int] | np.ndarray) -> np.ndarray | None:
    """Die Achse, quer zu der jede Normale des Stücks steht — oder ``None``: kein Prisma.

    Im Vertrag von :data:`UPRIGHT_TO_AXIS` wie bei :func:`fit_cylinder`. Die
    Achse ist das Kreuzprodukt der ersten Normale mit der, die am meisten quer
    zu ihr steht; steht keine um :data:`MIN_ROUND_ARC` quer, trägt das Stück
    keinen Bogen, der zählte. Gefragt von :func:`_arcs_of_a_prism`, und von
    der tangentialen Trennung, die ein Prisma der vierten Runde überlässt.
    """
    normals = np.asarray(body.face_normals, dtype=float)[np.asarray(piece, dtype=np.intp)]
    if not len(normals):
        return None
    first = normals[0]
    across = int(np.argmin(np.abs((normals * first).sum(axis=1))))
    axis = np.cross(first, normals[across])
    length = math.sqrt(float(axis[0] * axis[0] + axis[1] * axis[1] + axis[2] * axis[2]))
    if length < units.exact_sin_degrees(MIN_ROUND_ARC):
        return None
    axis = axis / length
    if float(np.abs((normals * axis).sum(axis=1)).max()) > UPRIGHT_TO_AXIS:
        return None
    return np.asarray(axis, dtype=float)


def _exactly_an_arc(
    body: trimesh.Trimesh,
    arc: list[int],
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Ob ein Stück aus :func:`_arcs_of_a_prism` ein gezeichneter Bogen ist.

    Zwei Bedingungen, beide aus der Sache. **Ein Bogen hat einen Radius**: Die
    Trennung sichert nur, dass zwei Nachbarn um höchstens
    :data:`PRISM_ARC_JUMP` auseinanderliegen; über das ganze Stück darf der
    Radius je Dreieck (:func:`face_radii`) nicht weiter wandern. Und **ein
    CAD-Export legt seine Ecken auf den Kreis**, bis auf die Rundung seiner
    Zahlen — die liegt unter der Schweißtoleranz, einem Millionstel der
    Diagonale.

    Gemessen am 25.09.2026 (RM-219): Die Bögen des Besenhalters liegen unter
    0,003 µm neben dem Kreis, ihr Radius streut um höchstens 2,4 Prozent. Die
    geschwungenen Streben des Eiffelturms passen stückweise auf Kreise, aber ihr
    Radius wandert in einem Stück um bis zu 12 Prozent; Stücke der
    Flaschentaschen, Schriftzüge und Griffe liegen 1 bis 10 µm neben dem Kreis
    — genau genug für :func:`fit_cylinder`, nicht für einen gezeichneten Bogen.
    """
    radii = face_radii(body, check_cancelled)[np.asarray(arc, dtype=np.intp)]
    radii = radii[np.isfinite(radii)]
    if len(radii) and float(radii.max() - radii.min()) > PRISM_ARC_JUMP * float(radii.max()):
        return False
    fit = fit_cylinder(body, arc, check_cancelled=check_cancelled)
    if fit is None or fit.fit_error is None:
        return False
    extents = np.asarray(body.extents, dtype=float)
    diagonal = math.sqrt(
        float(extents[0] * extents[0] + extents[1] * extents[1] + extents[2] * extents[2])
    )
    return fit.fit_error <= weld_tolerance(diagonal)


def _circle_pairs(
    fits: Mapping[int, CylinderFit],
    numbers: Sequence[int],
    axis_cosine: float,
    check_cancelled: Callable[[], None] | None = None,
) -> list[tuple[int, int]]:
    """Die Kreispaare, die :func:`_wandering_outline` einzeln prüfen muss — in fester Folge.

    Die Bestätigung fragt jedes Paar zweier Kreise nach Seite, Achse, Radius
    und Querversatz, bevor sie misst. Paar für Paar in Python war das
    quadratisch: Am Meshy-Murmelbrett trug ein Fleck 12 961 Stücke mit
    Gewicht, und diese eine Frage kostete 32 s (Durchsicht 0.5.1,
    erkennung-05). Hier fallen die Paare vorher heraus, die keine der vier
    Bedingungen erfüllen können: nach Radius sortiert nur das Fenster, in dem
    zwei Radien um höchstens :data:`CYLINDER_TOLERANCE` des größeren
    auseinanderliegen, und darin feldweise Seite, Achse und Versatz — mit
    einem Spielraum von einem Milliardstel, damit die Rundung keine Antwort
    ändert. Entschieden wird danach je Paar wie bisher; die Folge ist
    dieselbe wie in der Doppelschleife: aufsteigend nach dem ersten, dann nach
    dem zweiten Kreis.
    """
    count = len(numbers)
    if count < 2:
        return []
    radius = np.fromiter((float(fits[n].radius) for n in numbers), dtype=np.float64, count=count)
    inward = np.fromiter((bool(fits[n].inward) for n in numbers), dtype=bool, count=count)
    axes = np.asarray([fits[n].axis for n in numbers], dtype=np.float64).reshape(count, 3)
    centres = np.asarray([fits[n].centre for n in numbers], dtype=np.float64).reshape(count, 3)
    by_radius = np.argsort(radius, kind="stable")
    ordered = radius[by_radius]
    slack = 1.0 + 1e-9
    lowest = np.searchsorted(ordered, radius * (1.0 - CYLINDER_TOLERANCE) / slack, side="left")
    highest = np.searchsorted(ordered, radius / (1.0 - CYLINDER_TOLERANCE) * slack, side="right")
    pairs: list[tuple[int, int]] = []
    for index in range(count):
        if check_cancelled is not None and index % FIT_SCAN_BLOCK == 0:
            check_cancelled()
        near = by_radius[lowest[index] : highest[index]]
        near = near[(near > index) & (inward[near] == inward[index])]
        if not len(near):
            continue
        axis = axes[index]
        dots = axes[near, 0] * axis[0] + axes[near, 1] * axis[1] + axes[near, 2] * axis[2]
        near = near[np.abs(dots) >= axis_cosine - 1e-12]
        if not len(near):
            continue
        offset = centres[near] - centres[index]
        along = offset[:, 0] * axis[0] + offset[:, 1] * axis[1] + offset[:, 2] * axis[2]
        across = offset - along[:, None] * axis
        distance = np.sqrt((across * across).sum(axis=1))
        scale = np.maximum(radius[near], radius[index])
        near = near[distance <= scale * SINK_FIT_LIMIT * slack + 1e-12]
        pairs.extend((numbers[index], numbers[int(other)]) for other in np.sort(near))
    return pairs


def _wandering_outline(
    body: trimesh.Trimesh,
    pieces: Sequence[list[int]],
    check_cancelled: Callable[[], None] | None = None,
) -> set[int] | None:
    """Die Bögen unter den Stücken eines wandernden Umrisses — oder ``None``,
    wenn die Stücke keinen solchen Umriss bilden (RM-243).

    Ein Stück allein verrät nichts: Es liegt 1 bis 10 µm neben seinem Kreis,
    ob es ein Stück Schriftzug ist oder ein Stück einer rauen Flaschentasche.
    Die Antwort steht in der Nachbarschaft, und sie hat zwei Teile.

    **Ein Kreis, den ein zweites Stück bestätigt, ist ein Bogen.** Das
    Rauschen des Radius je Dreieck zerteilt einen echten Bogen in mehrere
    Stücke, und die liegen alle auf seinem Kreis: gleiche Seite, Radius und
    Achse wie in :func:`_same_cylinder`, und eines liegt auf dem Kreis des
    anderen (:func:`_lies_on_the_cylinder`). Beide Richtungen zu verlangen
    ist zu streng — am verrauschten Korbbogen verlören dann echte Bögen ihre
    Bestätigung. **Bestätigen kann nur ein Kreis, den sein eigenes Stück
    festlegt** (:func:`_carries_its_radius`, RM-254): Auf dem Kreis eines
    kurzen Stücks, das ihn nur ungefähr trifft, liegt jedes glatte Nachbarstück
    — am Screen-Cover zwei Buchstabenstücke R 11,27 und R 10,46, am
    Schmierwerkzeug Paare R 2,4, deren Vereinigung R 3,5 ergibt. Ein
    gezeichneter Bogen (:func:`_exactly_an_arc`) ist ohnehin einer. Ein
    Umriss mit wanderndem Radius trägt dagegen auf jedem Stück einen eigenen
    Kreis. Gezählt werden nur diese unbestätigten Kreise von Stücken mit
    Gewicht (:data:`MIN_PATCH_FACES`).

    **Ein Wechsel ist ein Übergang, zwei in dieselbe Richtung sind ein
    Verlauf.** Zwei unbestätigte Kreise, die über Splitter und formlose
    Stücke hinweg aufeinanderfolgen, gehen tangential ineinander über, wenn
    sie auf derselben Seite liegen, ihre Achsen parallel stehen und der
    Querversatz der Achsen so groß ist wie der Unterschied der Radien
    (innerhalb :data:`SINK_FIT_LIMIT`); der Radius ändert sich dabei um
    weniger als :data:`CURVATURE_JUMP` — die Kreise sagen, dass die Krümmung
    nicht sprang, und die Trennung kam aus dem Rauschen. Eine Untergrenze für
    den Schritt gibt es nicht: Buchstaben wandern oft in Schritten von einem
    bis drei Prozent. Der Umriss wandert, wenn ein Kreis so einen engeren und
    einen weiteren Nachbarn hat: Dort
    wächst der Radius über drei Kreise hinweg. Eine Flaschentasche, die in
    eine engere Einlaufrundung übergeht, hat einen Wechsel; ein Korbbogen
    R 10 · R 16 · R 10 zwei gegeneinander. Ein bestätigter Kreis hält die
    Folge an wie ein gezeichneter: Hinter einem Bogen beginnt der Umriss neu.

    Zurück kommen die Nummern der bestätigten und gezeichneten Stücke: Sie
    bleiben Merkmale, auch wenn der Fleck ein Umriss ist. Am Schmierwerkzeug
    von Elegoo liegen im selben Fleck wie die wandernden Splinestücke ein
    Halbrund R 4,2 aus dreizehn Stücken und zwei Bögen R 6,75 über 81 Grad.

    Gelesen wird am Nachbarindex, ohne Feld über das ganze Netz (wie
    :func:`_arcs_of_a_prism`); entschieden wird mit Grundrechenarten (RM-187).
    """
    fits: dict[int, CylinderFit] = {}
    confirmed: set[int] = set()
    for number, piece in enumerate(pieces):
        if _face_count(body, piece) < MIN_PATCH_FACES:
            continue
        if check_cancelled is not None:
            check_cancelled()
        if _exactly_an_arc(body, piece, check_cancelled):
            confirmed.add(number)
        fit = fit_cylinder(body, piece, check_cancelled=check_cancelled)
        if fit is not None and fit.good:
            fits[number] = fit
    # Zwei Wechsel in dieselbe Richtung brauchen drei Kreise.
    if sum(1 for number in fits if number not in confirmed) < 3:
        return None

    axis_cosine = units.exact_cos_degrees(SINK_AXIS_LIMIT)

    def placed(one: int, other: int) -> tuple[float, float, float] | None:
        """Radiusunterschied, Querversatz und Maßstab zweier Kreise gleicher Seite
        und paralleler Achse — sonst nichts."""
        first, second = fits[one], fits[other]
        if first.inward is not second.inward:
            return None
        axis = np.asarray(first.axis, dtype=float)
        if abs(float((axis * np.asarray(second.axis, dtype=float)).sum())) < axis_cosine:
            return None
        offset = np.asarray(second.centre, dtype=float) - np.asarray(first.centre, dtype=float)
        across = offset - axis * float((offset * axis).sum())
        return (
            abs(first.radius - second.radius),
            math.sqrt(float((across * across).sum())),
            max(first.radius, second.radius),
        )

    numbers = sorted(fits)
    for one, other in _circle_pairs(fits, numbers, axis_cosine, check_cancelled):
        if one in confirmed and other in confirmed:
            continue
        place = placed(one, other)
        if place is None:
            continue
        step, across, scale = place
        if step > scale * CYLINDER_TOLERANCE or across > scale * SINK_FIT_LIMIT:
            continue
        if check_cancelled is not None:
            check_cancelled()
        if (
            _carries_its_radius(body, fits[one], pieces[one])
            and _lies_on_the_cylinder(
                body, fits[one], pieces[other], check_cancelled=check_cancelled
            )
        ) or (
            _carries_its_radius(body, fits[other], pieces[other])
            and _lies_on_the_cylinder(
                body, fits[other], pieces[one], check_cancelled=check_cancelled
            )
        ):
            confirmed.update((one, other))
    circles = [number for number in numbers if number not in confirmed]
    if len(circles) < 3:
        return None

    sizes = np.fromiter((len(piece) for piece in pieces), dtype=np.intp, count=len(pieces))
    faces = np.concatenate([np.asarray(piece, dtype=np.intp) for piece in pieces])
    owners = np.repeat(np.arange(len(pieces), dtype=np.intp), sizes)
    order = np.argsort(faces, kind="stable")
    faces, owners = faces[order], owners[order]
    neighbours, _rows = _neighbour_index(body)
    beside = neighbours[faces]
    spot = np.minimum(np.searchsorted(faces, np.maximum(beside, 0)), len(faces) - 1)
    member = (beside >= 0) & (faces[spot] == beside)
    near = np.broadcast_to(owners[:, None], beside.shape)[member]
    far = owners[spot[member]]
    touching = near != far
    adjacent: dict[int, set[int]] = {}
    for one, other in zip(near[touching].tolist(), far[touching].tolist(), strict=True):
        adjacent.setdefault(one, set()).add(other)

    # Je Kreis bis zum nächsten Kreis auf jeder Seite, je Paar einmal gefragt:
    # über Splitter und formlose Stücke hinweg — die gehören zu Gruppen, und
    # welche Kreise eine Gruppe berührt, steht einmal fest (RM-261). Bis dahin
    # suchte jeder Kreis die Gruppen neu ab; am Gartenschlauchhalter waren das
    # 936 000 Schritte und ein Viertel der Erkennung nach dem Merker. Dieselben
    # Paare, dieselbe Frage — gefragt wird nur nicht mehr je Kreis von vorn.
    passable = [
        number for number in range(len(pieces)) if number not in fits and number not in confirmed
    ]
    group: dict[int, int] = {}
    for start in passable:
        if start in group:
            continue
        group[start] = start
        frontier = [start]
        while frontier:
            current = frontier.pop()
            for other in adjacent.get(current, ()):
                if other not in group and other not in fits and other not in confirmed:
                    group[other] = start
                    frontier.append(other)
    circles_beside: dict[int, set[int]] = {}
    for member, label in group.items():
        for other in adjacent.get(member, ()):
            if other in fits and other not in confirmed:
                circles_beside.setdefault(label, set()).add(other)
    smaller: set[int] = set()
    larger: set[int] = set()
    for number in circles:
        if check_cancelled is not None:
            check_cancelled()
        reached: set[int] = set()
        for other in adjacent.get(number, ()):
            if other in confirmed:
                continue
            if other in fits:
                reached.add(other)
            else:
                reached |= circles_beside.get(group[other], set())
        for other in sorted(reached):
            if other <= number:
                continue
            place = placed(number, other)
            if place is None:
                continue
            step, across, scale = place
            if step <= scale * CURVATURE_JUMP and abs(across - step) <= scale * SINK_FIT_LIMIT:
                low, high = sorted((number, other), key=lambda key: fits[key].radius)
                larger.add(low)
                smaller.add(high)
    # Ein Kreis mit einem engeren Nachbarn und einem weiteren: zwei Wechsel in
    # dieselbe Richtung.
    return confirmed if smaller & larger else None


def _carries_its_radius(body: trimesh.Trimesh, fit: CylinderFit, piece: Sequence[int]) -> bool:
    """Ob ein Stück den Radius seines Kreises auf :data:`CYLINDER_TOLERANCE` festlegt (RM-254).

    Ein Stück mit der Sehne ``L`` hat die Pfeilhöhe ``L²/8R``. Liegen seine
    Ecken bis ``e`` neben dem Kreis (``fit_error``), passt derselbe Abstand
    auch auf Kreise, deren Pfeilhöhe um ``e`` anders ist — der Radius ist also
    nur auf ``8·R·e/L²`` relativ bestimmt. Ist das mehr, als
    :func:`_same_cylinder` zwei Radien auseinanderliegen lässt, sagt „das
    andere Stück liegt auf diesem Kreis" nichts: Es läge ebenso auf dem Kreis
    eines Nachbarn mit anderem Radius.

    Gemessen am 04.10.2026: Die Buchstabenstücke R 11,27 und R 10,46 am
    Screen-Cover legen ihren Radius auf 11 und 12 Prozent fest, die Stücke
    R 2,4 am Schmierwerkzeug auf 18 bis 23; die Stücke der 24 verrauschten
    Korbbögen, die einen anderen bestätigen, auf höchstens 3,7, die Stücke,
    die am Schmierwerkzeug die Bögen R 4,2 und R 6,75 bestätigen, auf
    höchstens 0,4.
    """
    if fit.fit_error is None:
        return False
    span = min(angular_span(body, fit, list(piece)), 180.0)
    chord = 2.0 * fit.radius * units.exact_sin_degrees(span / 2.0)
    return 8.0 * fit.radius * fit.fit_error <= CYLINDER_TOLERANCE * chord * chord


def _between_corners_of(
    body: trimesh.Trimesh,
    fit: CylinderFit,
    patch: Sequence[int],
    wandering: np.ndarray,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Ob ein Rundstück zwischen zwei Ecken eines wandernden Umrisses liegt (RM-254).

    ``wandering`` markiert die Dreiecke der Flecken, die
    :func:`_wandering_outline` als gerundete Seite gelesen hat. Ein eigener
    Fleck, der an **beiden** Enden seines Bogens an einen solchen grenzt, ist
    dieselbe Seitenwand, nur durch Ecken abgesetzt — am Screen-Cover das
    0,4 mm hohe Wandband R 13,73 einer Stufe im Buchstaben, dessen Radius je
    Dreieck selbst von 8 bis 14 mm wandert. Er gehört zum Umriss, außer er ist
    gezeichnet (:func:`_exactly_an_arc`): Ein CAD-Umriss setzt Bögen auch
    zwischen Ecken.

    Beide Enden heißt: Ecken (Nähte ab :data:`CURVATURE_LIMIT`) längs der
    Achse (:data:`PARALLEL_AXES`, wie die axialen Seiten in
    :func:`_radial_boundaries_are_planar`) auf beiden Seiten der Bogenmitte,
    gemessen längs der Tangente dort — ohne Winkelfunktion, für jeden Bogen
    unter einem vollen Umlauf (:data:`FULL_TURN_SPAN`; ein ganzer Zylinder hat
    keine Enden). Eine Naht quer zur Achse ist die Stirnkante des Streifens:
    Am Gartenschlauchhalter stoßen zwei von vier Bändern R 6,3 eines
    Kreismusters mit ihrer Stirn an einen wandernden Fleck, und deren
    Berührungen liegen über die ganze Breite verteilt, also auch auf beiden
    Seiten der Mitte.
    """
    faces = np.asarray(patch, dtype=np.intp)
    if bool(wandering[faces].all()):
        return False
    if angular_span(body, fit, list(patch)) >= FULL_TURN_SPAN:
        return False
    neighbours, rows = _neighbour_index(body)
    beside = neighbours[faces].ravel()
    seams = rows[faces].ravel()
    present = beside >= 0
    beside, seams = beside[present], seams[present]
    inside = np.zeros(len(body.faces), dtype=bool)
    inside[faces] = True
    axis = np.asarray(fit.axis, dtype=float)
    centre = np.asarray(fit.centre, dtype=float)
    # Nur über eine Ecke an einem Ende des Bogens: Eine Naht unter
    # CURVATURE_LIMIT ist ein glatter Übergang, und eine Naht quer zur Achse
    # ist eine Stirnkante des Streifens, kein Ende seines Bogens.
    sharp = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float)[seams]) >= (
        CURVATURE_LIMIT
    )
    ends = np.asarray(body.face_adjacency_edges)[seams]
    vertices = np.asarray(body.vertices, dtype=float)
    vectors = vertices[ends[:, 1]] - vertices[ends[:, 0]]
    along = np.abs(vectors[:, 0] * axis[0] + vectors[:, 1] * axis[1] + vectors[:, 2] * axis[2])
    axial = along >= PARALLEL_AXES * np.sqrt((vectors * vectors).sum(axis=1))
    chosen = wandering[beside] & ~inside[beside] & sharp & axial
    if not bool(chosen.any()):
        return False

    def across(points: np.ndarray) -> np.ndarray:
        """Die Punkte quer zur Achse, vom Kreismittelpunkt aus."""
        relative = points - centre
        along = relative[:, 0] * axis[0] + relative[:, 1] * axis[1] + relative[:, 2] * axis[2]
        result: np.ndarray = relative - along[:, None] * axis
        return result

    corners = across(vertices[np.unique(np.asarray(body.faces)[faces])])
    lengths = np.sqrt((corners * corners).sum(axis=1))
    middle = (corners[lengths > EPS_GEOM] / lengths[lengths > EPS_GEOM][:, None]).sum(axis=0)
    size = math.sqrt(float((middle * middle).sum()))
    if size <= EPS_GEOM:
        return False
    middle = middle / size
    tangent = _cross3(axis, middle)
    contacts = across((vertices[ends[chosen, 0]] + vertices[ends[chosen, 1]]) / 2.0)
    sides = contacts[:, 0] * tangent[0] + contacts[:, 1] * tangent[1] + contacts[:, 2] * tangent[2]
    if not (bool((sides > EPS_GEOM).any()) and bool((sides < -EPS_GEOM).any())):
        return False
    return not _exactly_an_arc(body, list(patch), check_cancelled)


def _off_the_outline[Fit](
    entries: list[tuple[Fit, list[int]]], outline: np.ndarray
) -> list[tuple[Fit, list[int]]]:
    """Die Einpassungen ohne die, die ganz auf einem wandernden Umriss liegen (RM-243).

    ``outline`` markiert je Dreieck die Stücke, die :func:`_wandering_outline`
    zur gerundeten Seite erklärt hat. Gefragt wird nach der Zusammenlegung,
    und darum ganz und nicht teilweise: Was dort mit einem Stück von
    woanders zu einer Fläche verschmolz, bleibt mit allen Dreiecken — am
    Eiffelturm die Bögen R 24 über 172 Grad, von denen ein Bruchstück im
    wandernden Nachbarfleck lag.
    """
    return [entry for entry in entries if not bool(outline[entry[1]].all())]


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


def _curvature_jumps(
    body: trimesh.Trimesh, check_cancelled: Callable[[], None] | None = None
) -> np.ndarray:
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

    radii = face_radii(body, check_cancelled)
    if check_cancelled is not None:
        check_cancelled()
    return _jumps_between(radii[pairs[:, 0]], radii[pairs[:, 1]])


def _jumps_between(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Der Sprung zwischen zwei Radien je Naht, als Anteil — eine Rechnung für
    den ganzen Körper (:func:`_curvature_jumps`) und für einzelne Nähte
    (:func:`curvature_jumps_at`)."""
    # Nur wo **beide** Seiten einen Radius haben, gibt es einen Sprung. Zwei
    # ebene Nachbarn tragen ``inf``, und deren Differenz wäre ``nan`` — kein
    # Sprung, sondern keine Aussage. Die Rechnung darf die ``inf`` dabei gar
    # nicht erst sehen: ``where`` schützt die Division, nicht die Differenz
    # davor, und ``inf - inf`` meldet sich als Warnung, die hier ein Fehler ist.
    measured = np.isfinite(first) & np.isfinite(second)
    near = np.where(measured, first, 0.0)
    far = np.where(measured, second, 0.0)
    jump = np.zeros(len(first), dtype=float)
    np.divide(
        np.abs(near - far),
        np.maximum(np.maximum(near, far), EPS_GEOM),
        out=jump,
        where=measured,
    )
    return jump


def curvature_jumps(
    body: trimesh.Trimesh, check_cancelled: Callable[[], None] | None = None
) -> np.ndarray:
    """:func:`_curvature_jumps`, einmal je Körper gemerkt.

    Die Nachtrennung trennt an diesen Sprüngen, und die Erkennung an einer
    Stelle begrenzt an denselben ihre Randsperre (``local._recognise_region``)
    — dort nur an den Nähten ihres Ausschnitts (:func:`curvature_jumps_at`).
    Am Drachen kostet die erste Frage 3 s, geprüft wird der Abbruch dazwischen.
    """
    result: np.ndarray = remembered(
        "curvature_jumps",
        body,
        (),
        lambda: _curvature_jumps(body, check_cancelled),
        check_cancelled=check_cancelled,
    )
    return result


def curvature_jumps_at(
    body: trimesh.Trimesh,
    rows: np.ndarray,
    check_cancelled: Callable[[], None] | None = None,
) -> np.ndarray:
    """:func:`curvature_jumps` an ausgewählten Nähten (Zeilen von ``face_adjacency``) —
    dieselben Zahlen, ohne das ganze Netz zu rechnen.

    Die Erkennung an einer Stelle braucht die Sprünge nur an den Nähten ihres
    Ausschnitts (``local._recognise_region``), fragte sie aber am ganzen
    Körper: Nach jedem Versetzen oder Aufweiten ist das Netz neu, und am
    Gartenschlauchhalter mit 392 532 Dreiecken kostete die Frage 1,15 s der
    örtlichen Nachmessung (Durchsicht 0.5.1, bohrung). Gerechnet werden hier
    nur die Radien an diesen Nähten (:func:`face_radii_at`), mit denselben
    Schritten an denselben Zahlen — der Sprung ist bitgleich. Steht die
    Antwort für den ganzen Körper schon im Merker, wird sie gelesen.
    """
    wanted = np.asarray(rows, dtype=np.int64)
    known = _known_answer("curvature_jumps", body)
    if known is not None:
        return np.asarray(known, dtype=float)[wanted]
    pairs = np.asarray(body.face_adjacency, dtype=np.int64).reshape(-1, 2)
    if not len(wanted) or not len(pairs):
        return np.zeros(len(wanted), dtype=float)
    chosen = pairs[wanted]
    triangles = np.unique(chosen.ravel())
    radii = face_radii_at(body, triangles, check_cancelled)
    return _jumps_between(
        radii[np.searchsorted(triangles, chosen[:, 0])],
        radii[np.searchsorted(triangles, chosen[:, 1])],
    )


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
            # Derselbe Fleck, in seiner Ordnung (:func:`in_body_order`).
            split.append([patch])
            continue
        groups = trimesh.grouping.group(node_labels, min_len=1)
        split.append(in_body_order(body, [nodes[group].tolist() for group in groups]))
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


def _connected_patches(
    body: trimesh.Trimesh,
    faces: list[int],
    check_cancelled: Callable[[], None] | None = None,
) -> list[list[int]]:
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
        lambda: _connected_patches_read(body, faces, check_cancelled),
        check_cancelled=check_cancelled,
    )
    beyond = _BEYOND.get()
    if beyond is not None and getattr(result, "beyond", False):
        beyond.append(True)
    return result


class _Patches(list[list[int]]):
    """Flecken, die wissen, ob ihre Bildung über die gegebenen Dreiecke hinaus las.

    ``beyond``: :func:`_without_notches` hat an einem fransigen Rand nach
    freien Dreiecken gesucht — auch solchen außerhalb. Eine Rechnung über die
    Körpergrenze, die solche Flecken bildet, merkt sich nichts (:data:`_BEYOND`);
    die Angabe reist mit der gemerkten Antwort, damit auch ein Treffer im
    Merker des Körpers sie sagt.
    """

    __slots__ = ("beyond",)

    def __init__(self, patches: Iterable[list[int]], beyond: bool) -> None:
        super().__init__(patches)
        self.beyond = beyond


def _connected_patches_read(
    body: trimesh.Trimesh,
    faces: list[int],
    check_cancelled: Callable[[], None] | None = None,
) -> list[list[int]]:
    """Der Rumpf von :func:`_connected_patches` — die Antwort merkt sich die Hülle.

    Mit Abbruchprüfung zwischen Nähten, Zusammenhang, Kerben und Ordnung: Am
    Drachen kosteten die vier zusammen 4,2 s am Stück (25.09.2026).
    """
    pairs = np.asarray(body.face_adjacency)
    adjacency = pairs[:0]
    local: np.ndarray | None = None
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
        neighbours, pair_rows = _neighbour_index(body)
        if check_cancelled is not None:
            check_cancelled()
        chosen = neighbours[indices]
        if len(indices) < len(body.faces) * SORTED_CORNERS_SHARE:
            # **Ein kleiner Fleck fragt sortiert, nicht über Felder in
            # Netzgröße** (Durchsicht 0.5.1, erkennung-05): Zwei Masken über
            # alle Dreiecke und Nähte je Aufruf, und :func:`_cylinder_beside_a_torus`
            # ruft je Stück — am Meshy-Murmelbrett 3 656 Aufrufe und 71 s von
            # 866 unter dem Profiler. Dieselben Zeilen, aufsteigend wie dort.
            local = np.unique(indices)
            spot = np.minimum(np.searchsorted(local, np.maximum(chosen, 0)), len(local) - 1)
            present = (chosen >= 0) & (local[spot] == chosen)
            rows = np.unique(pair_rows[indices][present])
        else:
            wanted = np.zeros(len(body.faces), dtype=bool)
            wanted[indices] = True
            present = chosen >= 0
            present[present] = wanted[chosen[present]]
            # Dieselben Zeilen in derselben aufsteigenden Ordnung wie
            # ``np.unique``, nur ohne Sortierung: eine Maske über die Nähte.
            seen = np.zeros(len(pairs), dtype=bool)
            seen[pair_rows[indices][present]] = True
            rows = np.flatnonzero(seen)
        angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float)[rows])
        adjacency = pairs[rows[angles < CURVATURE_LIMIT]]
    if check_cancelled is not None:
        check_cancelled()
    if not len(adjacency):
        return _Patches(in_body_order(body, [[index] for index in faces]), beyond=False)
    if local is not None:
        # Der Zusammenhang in eigener, aufsteigender Nummerierung: Die Suche
        # legt sonst einen Graphen über alle Dreiecke des Netzes an. Die
        # Umnummerierung erhält die Ordnung, also Gruppen und ihre Folge.
        within = trimesh.graph.connected_components(
            np.searchsorted(local, adjacency),
            nodes=np.searchsorted(local, np.asarray(faces)),
            engine="scipy",
        )
        groups = [local[group] for group in within]
    else:
        groups = trimesh.graph.connected_components(
            adjacency, nodes=np.asarray(faces), engine="scipy"
        )
    if check_cancelled is not None:
        check_cancelled()
    looked: list[bool] = []
    closed = _without_notches(body, [group.tolist() for group in groups], looked=looked)
    if check_cancelled is not None:
        check_cancelled()
    return _Patches(in_body_order(body, closed), beyond=bool(looked))


def in_body_order(body: trimesh.Trimesh, groups: Sequence[Sequence[int]]) -> list[list[int]]:
    """Flecken und ihre Dreiecke in einer Ordnung, die der Körper vorgibt und nicht die Datei.

    **Die Erkennung hing an der Reihenfolge der Dreiecke** (22.09.2026): Zwölf
    von 101 Körpern des Korpus lieferten mit rückwärts gespeicherten
    Dreiecken andere Merkmale — dieselben Ecken, dieselbe Form. Zwei Wege
    führten dorthin:

    * Die Einpassungen summieren über die Dreiecke eines Flecks, und die
      Reihenfolge der Summe verschiebt die letzte Stelle. An der Kippe eines
      Fits — ein Kegel, der sein Auswertungsbudget ausschöpft — entscheidet
      diese Stelle (Siebhalter: der Kegel sprang zwischen zwei gleichen
      Flächen hin und her).
    * Die Flecken werden der Reihe nach gefragt, und manche Antworten gelten
      für die folgenden mit: ein „kein Kegel" für deckungsgleiche Flecken, die
      Zusammenlegung benachbarter Bögen.

    Geordnet wird deshalb nach den Ecken: jede Ecke bekommt ihren Rang nach
    ihren Koordinaten (:func:`vertex_rank`, einmal je Körper), jedes Dreieck
    die drei Ränge seiner Ecken aufsteigend, und die Dreiecke folgen diesen
    drei Zahlen; die Flecken folgen ihrem ersten Dreieck. Gleich sind nur
    deckungsgleiche Dreiecke, und die tragen zur Summe dasselbe bei.
    Gerechnet wird nicht — die Ränge kommen aus den Ecken selbst, also frei
    von Rundung. Über Ränge statt über die neun Koordinaten, weil deren
    Sortierung am Drachen aus TripoSG (325 244 Dreiecke) 1,5 s kostete.
    """
    kept = [group for group in groups if len(group)]
    if not kept:
        return []
    sizes = np.fromiter((len(group) for group in kept), dtype=np.int64, count=len(kept))
    # Einmal durch alle Flecken statt eines Felds je Fleck: Eine Freiform bringt
    # 120 000 davon mit, und je Fleck ``np.asarray`` und ``np.split`` kosteten
    # dort zusammen 0,4 s (23.09.2026).
    faces = np.fromiter(itertools.chain.from_iterable(kept), dtype=np.int64, count=int(sizes.sum()))
    corners = np.sort(vertex_rank(body)[np.asarray(body.faces, dtype=np.int64)[faces]], axis=1)
    count = int(corners.max()) + 1
    if count <= _RANK_PACKING:
        key = (corners[:, 0] * count + corners[:, 1]) * count + corners[:, 2]
        rank = np.empty(len(faces), dtype=np.int64)
        rank[np.argsort(key, kind="stable")] = np.arange(len(faces))
    else:
        rank = np.empty(len(faces), dtype=np.int64)
        rank[np.lexsort(corners.T[::-1])] = np.arange(len(faces))
    labels = np.repeat(np.arange(len(kept)), sizes)
    order = np.lexsort((rank, labels))
    ordered = faces[order].tolist()
    bounds = np.r_[0, np.cumsum(sizes)]
    firsts = rank[order][bounds[:-1]]
    limits = bounds.tolist()
    return [
        ordered[limits[index] : limits[index + 1]]
        for index in np.argsort(firsts, kind="stable").tolist()
    ]


#: Bis zu wie vielen Ecken sich drei Ränge in eine ganze Zahl packen lassen:
#: ``n³`` muss unter ``2⁶³`` bleiben. Darüber sortiert :func:`in_body_order`
#: die drei Spalten einzeln — dasselbe Ergebnis, nur langsamer.
_RANK_PACKING: Final = 2_097_151


def _in_size_order(body: trimesh.Trimesh, patches: list[list[int]]) -> list[list[int]]:
    """Flecken, der größte zuerst; gleich große in der Ordnung des Körpers.

    Gleich heißt wie bei jeder Flächenordnung: auf :data:`AREA_DIGITS`
    Stellen zusammenfallend, über Ketten (:func:`numbering_order`). Die
    Fläche hängt weder an der Folge der Dreiecke noch an der Lage des
    Körpers — anders als :func:`in_body_order`, das nach Koordinaten ordnet
    und bei einer Drehung eine andere Folge gibt (RM-210).

    Gerechnet wie :func:`numbering_order` mit einer Stufe, aber als Feld:
    In einer Dimension ist eine Kette eine Folge von Lücken unter der Grenze,
    und eine Freiform bringt hunderttausend Flecken mit (am Drachen 120 610).
    """
    if len(patches) < 2:
        return patches
    sizes = np.add.reduceat(
        np.asarray(body.area_faces, dtype=float)[np.concatenate(patches)],
        np.r_[0, np.cumsum([len(patch) for patch in patches])[:-1]],
    )
    order = np.argsort(-sizes, kind="stable")
    group = np.cumsum(np.r_[True, np.diff(-sizes[order]) > 10.0**-AREA_DIGITS]) - 1
    return [patches[index] for index in order[np.lexsort((order, group))].tolist()]


#: Unter diesem Schlüssel hält der Cache von ``trimesh`` den Rang jeder Ecke —
#: er lebt und stirbt mit der Geometrie wie ``face_adjacency``.
_VERTEX_RANK_KEY: Final = "solidon_vertex_rank"


def vertex_rank(body: trimesh.Trimesh) -> np.ndarray:
    """Der Rang jeder Ecke nach ihren Koordinaten (x, dann y, dann z), einmal je Körper.

    Deckungsgleiche Ecken teilen einen Rang: Er ist die Nummer ihres Punkts,
    genau die, die ``np.unique(vertices, axis=0, return_inverse=True)``
    liefert — in derselben lexikographischen Ordnung, fünfmal so schnell
    (an der dichten Platte mit 101 882 Ecken 9 gegen 46 ms). Unabhängig von
    der Reihenfolge der Ecken und Dreiecke im Netz.

    **Die eine Stelle für „welche Ecken sind derselbe Ort".** Die Lesung der
    Stützpunkte fragte sie über ``np.unique`` je Körper, die Ordnung der
    Flecken über diesen Rang, die Nachbarschaft der Platzierung
    (``scene.placement._welded_adjacency``) noch einmal über ``np.unique`` —
    dreimal dieselbe Auskunft (RM-232, 25.09.2026). Einmal je Körper und
    nicht je Fleck: An der Schüssel mit 215 000 Dreiecken und
    deckungsgleichen Ecken sortierte jede der 443 Lesungen ihre Punkte als
    Zeilen (22.09.2026). Der Rang liegt im Cache des Netzes, verfällt mit
    seiner Geometrie und reist mit einer Kopie, die ihren Cache mitnimmt.
    """
    if _VERTEX_RANK_KEY in body._cache:
        cached: np.ndarray = body._cache[_VERTEX_RANK_KEY]
        return cached
    vertices = np.asarray(body.vertices, dtype=float)
    order = np.lexsort(vertices.T[::-1])
    ordered = vertices[order]
    # Bitgleichheit wie in ``np.unique``: Deckungsgleiche Ecken einer
    # ungeschweißten STL tragen dieselben Bits. Kein Vergleich zweier Maße,
    # also keine Toleranz (Regel 6) — der Rang ordnet nur.
    fresh = np.r_[True, np.any(ordered[1:] != ordered[:-1], axis=1)] if len(ordered) else []
    rank = np.empty(len(vertices), dtype=np.int64)
    rank[order] = np.cumsum(fresh) - 1
    body._cache[_VERTEX_RANK_KEY] = rank
    return rank


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
    """Die Dreiecke außerhalb des Flecks, glatt angrenzend, mit einem fransigen Knoten.

    **Glatt heißt: über eine Naht unter** :data:`CURVATURE_LIMIT` — dieselbe
    Schwelle, an der :func:`_connected_patches` einen Fleck enden lässt. Eine
    Kerbe ist ein herausgefallenes Segment derselben Fläche (siehe
    :data:`NOTCH_AT_MOST`), und das setzt sie ohne Kante fort. Was nur über
    eine Kante anliegt, gehört zu einer anderen Fläche: Am Ringabsatz einer
    Senkbohrung schloss sonst ein Paar ebener Dreiecke über einen Knick von
    39° die Kerbe des Senkkegels, und der Kegel las sich danach als Torus — je
    nach Vernetzung des Absatzes, an derselben Bohrung in einer Lage ja, in
    der nächsten nicht (RM-274,
    ``konzepte/nachweise-release-0.5.1/sonden/bohren/p12_kippe.py``).
    """
    inside = np.zeros(len(body.faces), dtype=bool)
    inside[np.asarray(patch, dtype=np.intp)] = True
    neighbours, rows = _neighbour_index(body)
    # Die Winkel im Bogenmaß aus dem Cache von trimesh; in Grad umgerechnet
    # wird je Kandidat nur seine Naht, wie in :func:`_connected_patches`.
    angles = np.asarray(body.face_adjacency_angles, dtype=float)
    ranges, vertex_faces = _vertex_faces_index(body)
    found: set[int] = set()
    for node in frayed:
        for face in vertex_faces[ranges[node] : ranges[node + 1]]:
            if inside[face]:
                continue
            # Nur die unmittelbaren Nachbarn des Flecks kommen in Frage: Ein
            # Dreieck, das den Knoten teilt, aber nirgends anliegt, schließt
            # keine Kerbe.
            present = neighbours[face] >= 0
            beside = neighbours[face][present]
            seams = rows[face][present]
            touching = inside[beside]
            if touching.any() and bool(
                np.any(np.degrees(angles[seams[touching]]) < CURVATURE_LIMIT)
            ):
                found.add(int(face))
    return found


#: Wie viele freie Dreiecke eine Kerbe höchstens schließen dürfen.
#:
#: Eine Kerbe ist eine Lücke von ein, zwei Dreiecken — ein Kegelsegment
#: besteht aus einem koplanaren Paar, und mehr als ein Segment fällt nicht
#: heraus. Was drei und mehr braucht, ist keine Kerbe mehr, sondern ein Loch,
#: und ein Loch zuzunähen wäre eine Erfindung.
NOTCH_AT_MOST: Final = 2


def _without_notches(
    body: trimesh.Trimesh,
    patches: list[list[int]],
    *,
    belongs: np.ndarray | None = None,
    looked: list[bool] | None = None,
) -> list[list[int]]:
    """Fransige Ränder schließen, solange die Menge dafür frei, klein und eindeutig ist.

    **Eindeutig heißt: genau eine Menge ihrer Größe** (Regel 21). Am
    ausgefransten Knoten liegen mehrere freie Dreiecke — auf dem Mac der CI
    gemessen vier —, und keines davon bringt den Rand allein in Ordnung.
    Gesucht wird deshalb die **kleinste** Menge, die es tut; gibt es davon zwei
    derselben Größe, steht dort eine Gabelung, und die zu raten wäre schlimmer,
    als die Kerbe stehen zu lassen.

    **Frei ist, was keinem Fleck gehört.** Ohne ``belongs`` sind das die
    übergebenen Flecken; wer nur einen Fleck kennt (:func:`planar_facet`),
    reicht die Dreiecke aller Flecken als Maske herein.
    """
    taken: set[int] = (
        set() if belongs is not None else {index for patch in patches for index in patch}
    )
    healed: list[list[int]] = []
    for patch in patches:
        # **Nur Flecken, die überhaupt eingepasst werden** (Leistung, gemessen
        # 17.09.2026). Die Randprüfung kostet je Fleck ein ``np.unique`` über
        # seine Kanten; an einer verrauschten Freiform sind es 120 610 Flecken,
        # und drei Leistungstests rissen ihre Schwelle. Was unter
        # ``MIN_PATCH_FACES`` liegt, kommt an ``classify`` ohnehin nicht vorbei
        # — dort steht dieselbe Grenze.
        if _face_count(body, patch) < MIN_PATCH_FACES:
            healed.append(patch)
            continue
        rim = _rim_of(body, patch)
        if rim is None or not rim.frayed:
            healed.append(patch)
            continue
        if looked is not None:
            # Gesucht wird auch außerhalb der gegebenen Dreiecke (RM-592).
            looked.append(True)
        candidates = sorted(
            face
            for face in _candidates_at(body, patch, rim.frayed)
            if face not in taken and (belongs is None or not belongs[face])
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
    # Jeder ausgefranste Knoten muss eine Kante der ergänzten Dreiecke tragen.
    # Mehr als drei Knoten je Dreieck sind unerreichbar; keine Kombination
    # kann dann den Rand schließen, unabhängig von der Zahl der Kandidaten.
    if not candidates or len(rim.frayed) > 3 * NOTCH_AT_MOST:
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
    """Alle ebenen Flächen mit Normale, Fläche, Mittelpunkt, Träger und Innenlage —
    der Prüfweg ohne Musterfalten (§21.1).

    Kein Produktionsaufrufer, mit Absicht: :func:`detect` baut die Flächen in
    denselben Schritten (:func:`_planar_face_entries`, :func:`_largest_first`,
    :func:`_face_candidates`, :func:`_finished_faces`), faltet dazwischen aber
    Muster und lässt verschluckte Flächen weg. Hier kommen alle — Tests holen
    sich so die Flächen vor dem Musterfalten (etwa die Zellen einer Wabe) und
    die Menge, die :func:`planar_mask` trägt. Die Nummerierung erklärt
    :func:`_largest_first`.

    **Gerechnet wird auf dem Netz, wie es kommt.** :func:`detect` schweißt
    vorher (``_one_body``) und nimmt die ebenen Reststücke dazu
    (``fitted.flat``); beides fehlt hier. Ein ungeschweißtes Netz ergibt
    deshalb keine Fläche — ``plate_holes.stl`` mit ``process=False``: hier 0,
    in :func:`detect` 6 (Review 07.10.2026).
    """
    body = mesh.raw
    entries = _planar_face_entries(mesh, planar=planar, check_cancelled=check_cancelled)
    entries = _largest_first(body, entries)
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
    bleiben, fertig (:func:`_finished_faces`); :func:`detect` ruft beide.
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
                # **Ungerundet** (Regel 6), wie am exakten Kern: Gerundet wird
                # in der Anzeige. Wer zwei gleich große Flächen vergleicht,
                # rundet im Schlüssel (:data:`AREA_DIGITS`), nicht im Wert.
                params={
                    "area": float(area),
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
    limit: int,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, bool]:
    """Nur angefragte Ebenen anhand räumlich passender Originalfacetten einordnen.

    Ob eine Gegenfacette als Ebene zählt, sagt dieselbe Auskunft wie für die
    Fläche selbst (:func:`planar_facet` mit ``limit``). Bis zum 25.09.2026
    fragte die Rollenprüfung einen eigenen, begrenzten Weg, der über dem
    Budget der Stelle abbrach: Am Schaber kam eine Deckfläche der
    Vollerkennung an der Stelle als „zu viele Dreiecke“ zurück.
    """
    if not features:
        return {}
    entries = _planar_face_entries(mesh, check_cancelled=check_cancelled, all_facets=True)
    accepted: dict[int, bool] = {}

    def eligible(facet: np.ndarray) -> bool:
        """Nur ein räumlich passender Beleg benötigt die aufwendige Mantelgegenprobe."""
        first = int(facet[0])
        if first not in accepted:
            accepted[first] = planar_facet(
                mesh.raw,
                [int(index) for index in facet],
                limit=limit,
                check_cancelled=check_cancelled,
            )
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
    # ganzen Flächenumriss. Ihre äußere Kontur schließt eine Öffnung
    # mit ein: Der Boden einer Dose liegt unter deren Rand, obwohl durch die
    # Öffnung nach oben freie Sicht besteht. Eine seitlich versetzte Lippe
    # oder ein zweiter Körper belegt dagegen keine Innenlage.
    import shapely
    from shapely.geometry import MultiPoint

    normals = np.asarray([body.face_normals[facet[0]] for facet, _a, _c in entries], dtype=float)
    centres = np.asarray([centre for _f, _a, centre in entries], dtype=float)
    shell = _shell_of_each_face(body)
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

    def covers_face(feature: Feature, other: int) -> bool:
        """Ein Schriftzug über der Mitte umschließt nicht die ganze Außenwand."""
        corners = vertices[np.unique(faces[list(feature.face_indices)])] - centres[other]
        footprint = MultiPoint(
            np.column_stack((corners @ basis_u[other], corners @ basis_v[other]))
        ).convex_hull
        return bool(outline_of(other).covers(footprint))

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
                    and covers_face(feature, int(other))
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
                covers_face(feature, int(other))
                and (eligible is None or eligible(entries[int(other)][0]))
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
    count = len(body.faces)
    rounded = np.zeros(count, dtype=bool)
    rounded[adjacency[(angles > EPS_ANGLE) & smooth].ravel()] = True
    # **Eine koplanare Facette gehört ganz dazu oder gar nicht** (Befund B6
    # der Erkennungsdurchsicht, 24.09.2026). Ein Dreieck zählte nur, wenn es
    # selbst an einer Rundungsnaht lag; war eine Mantelfacette in mehr als zwei
    # Dreiecke geteilt, fiel ihre Mitte heraus. Am Besenhalter, 199 Kanten
    # formgleich geteilt, schrumpften die gerundeten Seiten von 5 436 auf
    # 4 242 mm², und fünf von neun verschwanden.
    flat = angles <= EPS_ANGLE
    if rounded.any() and flat.any():
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components

        graph = coo_matrix(
            (np.ones(int(flat.sum())), (adjacency[flat, 0], adjacency[flat, 1])),
            shape=(count, count),
        )
        _facets, facet_of = connected_components(graph, directed=False)
        rounded = np.isin(facet_of, np.unique(facet_of[rounded]))
    taken = np.zeros(count, dtype=bool)
    taken[np.asarray(sorted(claimed), dtype=np.int64)] = True
    free = np.flatnonzero(rounded & ~taken).astype(np.int64)
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
    # Stabilität wie bei den ebenen Flächen (:func:`_largest_first`).
    entries = _largest_first(body, entries)

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
                    "area": float(area),
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
    return tuple(int(index) for index in np.unique(np.asarray(body.faces)[facet]))


#: Auf wie viele Nachkommastellen der Nummernschlüssel eine Länge in
#: Millimetern liest — drei, wie er es immer tat. **Die Auflösung eines
#: Schlüssels, keine Toleranz** (Regel 7): Sie entscheidet nicht, ob zwei
#: Merkmale gleich sind, sondern nur, wann :func:`numbering_order` die nächste
#: Stufe fragt.
NUMBERING_DIGITS: Final = 3


def numbering_order(
    count: int,
    levels: Sequence[tuple[Callable[[int], Sequence[float] | np.ndarray], int]],
    last: Callable[[int], tuple[int, ...]],
) -> list[int]:
    """In welcher Reihenfolge ``count`` Merkmale einer Art ihre Nummern bekommen (§21.2).

    Die Nummer ist eine Provenienz-ID: Eine Operation oder Passung, die an
    ``fillet_2`` hängt, muss nach der nächsten Auswertung an derselben Rundung
    hängen. Sie darf deshalb an nichts hängen, was nicht der Körper selbst ist
    — nicht an der Reihenfolge seiner Dreiecke oder Flecken, nicht am Rauschen
    in der zwölften Stelle.

    ``levels`` sind die Stufen des Schlüssels, je eine Abfrage und ihre
    Nachkommastellen; ``last`` entscheidet zuletzt und muss für verschiedene
    Merkmale verschieden sein — die Ecken ihrer Flecken (:func:`_corner_key`).
    Die nächste Stufe fragt nur, wer in der vorigen mit einem anderen
    zusammenfällt:

    * **Zusammenfallen heißt: in jeder Stelle höchstens eine Einheit der
      letzten Nachkommastelle auseinander, über Ketten hinweg** — nicht
      „gerundet gleich". Konzentrische Rundungen haben dieselbe Mitte bis auf
      Rauschen. Liegt sie auf einer Rundungsgrenze — RM-211: drei Rundungen
      eines Clips um ``119,0005`` —, fallen sie gerundet auseinander, und das
      Rauschen entscheidet, welche ``fillet_1`` heißt.
    * **Eine Gruppe steht an der Stelle ihres kleinsten gerundeten Werts.**
      Wer allein steht, steht damit genau dort, wo ihn der gerundete Schlüssel
      immer hinstellte, und behält seine Nummer. Neu geordnet wird nur, was
      bisher unentschieden war — und das hing an der Reihenfolge der Flecken:
      Zwei konzentrische Rundungen eines Winkels tauschten ihre Namen, sobald
      die Dreiecke rückwärts im Netz standen (22.09.2026).
    """

    def ordered(members: list[int], depth: int) -> list[int]:
        if len(members) < 2:
            return members
        if depth == len(levels):
            return sorted(members, key=last)
        read, digits = levels[depth]
        values = np.array([[float(value) for value in read(member)] for member in members])
        result: list[int] = []
        for group in _close_groups(values, digits):
            result.extend(ordered([members[position] for position in group], depth + 1))
        return result

    return ordered(list(range(count)), 0)


def _close_groups(values: np.ndarray, digits: int) -> list[list[int]]:
    """Zeilen, die in jeder Stelle höchstens ``10**-digits`` auseinanderliegen — über Ketten.

    Die Gruppen kommen nach ihrem kleinsten gerundeten Wert geordnet, die
    Zeilen darin aufsteigend. Zwei Gruppen haben nie denselben kleinsten
    gerundeten Wert: Sie liegen in mindestens einer Stelle weiter als eine
    Einheit auseinander, und gerundet bleibt dort ein Unterschied.
    """
    count = len(values)
    if count < 2 or values.ndim != 2 or values.shape[1] == 0:
        return [list(range(count))]
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree

    pairs = cKDTree(values).query_pairs(10.0**-digits, p=np.inf, output_type="ndarray")
    links = coo_matrix(
        (np.ones(len(pairs), dtype=np.int8), (pairs[:, 0], pairs[:, 1])), shape=(count, count)
    )
    _count, labels = connected_components(links, directed=False)
    rounded = [tuple(round(float(value), digits) for value in row) for row in values]
    members: dict[int, list[int]] = {}
    for position, label in enumerate(labels.tolist()):
        members.setdefault(label, []).append(position)
    return sorted(members.values(), key=lambda group: min(rounded[position] for position in group))


def _in_numbering_order(
    body: trimesh.Trimesh,
    entries: list[Any],
    size: Callable[[Any], Sequence[float]],
) -> list[Any]:
    """Eingepasste Flecken in der Reihenfolge ihrer Nummern (:func:`numbering_order`).

    Nach der Mitte das Maß (``size``: der Radius, beim Ring beide, beim Kegel
    mit der Spitze), dann die Länge entlang der Achse, wo es eine gibt, dann
    die flächengewichtete Mitte des Flecks — sie trennt zwei gleich große
    Bögen desselben Zylinders —, zuletzt seine Ecken.
    """

    def length(index: int) -> tuple[float, ...]:
        fit, patch = entries[index]
        axis = getattr(fit, "axis", None)
        return () if axis is None else (_patch_extent(body, patch, axis),)

    order = numbering_order(
        len(entries),
        (
            (lambda index: entries[index][0].centre, NUMBERING_DIGITS),
            (lambda index: size(entries[index][0]), NUMBERING_DIGITS),
            (length, NUMBERING_DIGITS),
            (lambda index: _facet_centre(body, np.asarray(entries[index][1])), NUMBERING_DIGITS),
        ),
        lambda index: _corner_key(body, np.asarray(entries[index][1])),
    )
    return [entries[index] for index in order]


#: Auf wie viele Nachkommastellen der Nummernschlüssel eine Fläche in mm² liest
#: — vier, wie er es immer tat. Dieselbe Art Auflösung wie
#: :data:`NUMBERING_DIGITS`, keine Toleranz.
AREA_DIGITS: Final = 4


def _largest_first(body: trimesh.Trimesh, entries: list[Any]) -> list[Any]:
    """Flächen, die größte zuerst, bei gleicher Größe nach ihren Ecken (:func:`numbering_order`).

    ``entries`` beginnen mit den Dreiecken und der Fläche. Gerundet wurde die
    Fläche schon immer, weil zwei gleich große sich im Netz in der zwölften
    Stelle unterscheiden; die Rundung allein ließ aber zwei gleiche Flächen
    auf einer Rundungsgrenze wieder nach dem Rauschen ordnen.

    **Bei gleicher Fläche entscheiden die Eckennummern der Fläche.** Die sechs
    Flächen eines Würfels sind exakt gleich groß; sortiert allein nach Fläche
    hing es an der Reihenfolge der Dreiecke im Netz, welche davon ``face_1``
    wird. Die Zuordnung (§21.2) fängt das im Regelbetrieb über die Lage wieder
    ein; die **Ersterkennung** hat nichts, womit sie vergleichen könnte.

    **Und ausdrücklich nicht der Ort**, obwohl er sich anbietet. Eine
    Nummerierung nach Koordinaten überlebt keine Drehung: Bei einer Platte
    sind Deck- und Bodenfläche gleich groß, und um zwanzig Grad gekippt
    tauschen sie ihre Reihenfolge. ``align`` legt ``face_1`` eines gedrehten
    Teils auf ``face_1`` des festen, und beide müssen dieselbe Fläche des
    Teils meinen. Die kleinste Eckennummer ändert sich weder beim Drehen noch
    beim Umsortieren der Dreiecke. Genommen werden alle Ecken der Fläche und
    nicht bloß die kleinste: An einem Würfel treffen sich drei Flächen in
    derselben Ecke, und drei gleiche Schlüssel sind so gut wie keiner.
    """
    order = numbering_order(
        len(entries),
        ((lambda index: (-float(entries[index][1]),), AREA_DIGITS),),
        lambda index: _corner_key(body, np.asarray(entries[index][0])),
    )
    return [entries[index] for index in order]


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
    # überlebt keine Drehung (siehe ``_largest_first``). Die Original-Nummern tun
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
        middle = np.asarray(body.vertices, dtype=float)[at].mean(axis=0)
        loops.append(
            (
                count,
                (float(middle[0]), float(middle[1]), float(middle[2])),
                tuple(int(index) for index in np.unique(at)),
            )
        )

    # **Bei gleich vielen offenen Kanten entscheiden die Eckennummern, nicht
    # der Ort.** Hier stand der gerundete Mittelpunkt, und damit galt genau
    # das, wovor ``_largest_first`` ausdrücklich warnt: Eine Nummerierung
    # nach Koordinaten überlebt keine Drehung. Zwei
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

    **Nahe an der Schale und elementweise** — dieselbe Rechnung wie
    ``geom.repair._shell_volumes`` (Review R14, 24.09.2026): Auf den Ursprung
    bezogen bestand das Volumen eines kleinen Teils weit draußen aus Rundung,
    und ``np.einsum`` rechnet auf ARM mit FMA (RM-187).
    """
    if triangles is None:
        triangles = np.asarray(body.vertices)[np.asarray(body.faces)[faces]]
    corners = np.asarray(triangles, dtype=np.float64)
    if not len(corners):
        return 0.0
    return math.fsum(triple_products(corners - corners[0, 0]).tolist()) / 6.0


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
            # Elementweise und nicht über ``np.einsum`` (RM-187): Seit die
            # Reparatur mit diesem Strahl entscheidet, ob eine Schale gedreht
            # wird, darf FMA auf ARM das Ergebnis nicht verschieben (Review R11).
            offset = point - corners[parallel, 0]
            facing = normals[parallel]
            distance = np.abs(
                offset[:, 0] * facing[:, 0]
                + offset[:, 1] * facing[:, 1]
                + offset[:, 2] * facing[:, 2]
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
        heights = corners[inside][:, :, axis]
        chosen = weights[inside]
        hit = (
            chosen[:, 0] * heights[:, 0]
            + chosen[:, 1] * heights[:, 1]
            + chosen[:, 2] * heights[:, 2]
        )
        ahead = sign * (hit - point[axis])
        scale = np.abs(corners[inside][:, :, axis]).max(axis=1) + abs(float(point[axis]))
        if np.any(np.abs(ahead) <= _RAY_MARGIN * np.maximum(scale, 1.0)):
            continue
        return bool(np.count_nonzero(ahead > 0.0) % 2 == 1)
    return None


def point_in_shell(
    point: np.ndarray,
    triangles: np.ndarray,
    bounds: tuple[np.ndarray, np.ndarray],
    *,
    undecided: bool,
    axis: np.ndarray | None = None,
) -> bool:
    """Ob ``point`` in der Schale liegt — unentschieden eine Facettenhöhe daneben nachgefragt.

    :func:`_point_inside_shell` kann an geteilten Kanten und Ecken nicht zählen:
    Auf der Achse eines Drehkörpers oder eines mittig gesetzten Bausteins liegt
    jeder Punkt über solchen Kanten. Dann fragt es
    :data:`~app.core.units.MAX_FACET_SAG` daneben nach — quer zu ``axis``, wo
    der Aufrufer eine Richtung hat, deren Höhe bleiben soll, sonst entlang der
    Koordinatenachsen. Bleibt es offen, gilt ``undecided``: Der Aufrufer sagt,
    welcher Irrtum der harmlose ist.

    **Eine Frage, nicht vier** (Nachprüfung G, N-4): ``bore_pin`` wertete
    unentschieden als Luft, ``parts.ops`` fragte daneben nach, ``_air_above``
    nahm Material, ``_void_holds`` „darin“ — an der Rastdrehscheibe sagte das
    Netz deshalb Luft, wo der exakte Kern Material sah.
    """
    answer = _point_inside_shell(point, triangles, bounds)
    if answer is not None:
        return answer
    if axis is not None:
        along = np.asarray(axis, dtype=np.float64)
        helper = (1.0, 0.0, 0.0) if abs(float(along[0])) < 0.7071067811865476 else (0.0, 1.0, 0.0)
        across = np.cross(along, np.asarray(helper, dtype=np.float64))
        across /= float(np.linalg.norm(across, axis=0))
        beside = np.cross(along, across)
        offsets: list[np.ndarray] = [across, beside, -across, -beside]
    else:
        offsets = [*np.eye(3), *(-np.eye(3))]
    for offset in offsets:
        answer = _point_inside_shell(point + offset * units.MAX_FACET_SAG, triangles, bounds)
        if answer is not None:
            return answer
    return undecided


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
            np.asarray(body.vertices, dtype=np.float64)[np.asarray(body.faces)[faces]]
            for faces in components
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

    **Einmal je Körper** (Durchsicht 0.5.1): Die Erkennung an einer Stelle
    fragt die Einschlüsse des ganzen Körpers je Suchbereich
    (``local._recognise_region``), und jede Frage zählte Dichtheit und Teile
    neu — am Gartenschlauchhalter dreimal 0,18 s je Versetzen.
    """
    found, unreadable = remembered(
        "voids",
        mesh.raw,
        (),
        lambda: _detect_voids_read(mesh, check_cancelled),
        check_cancelled=check_cancelled,
    )
    return list(found), int(unreadable)


def _detect_voids_read(
    mesh: MeshData, check_cancelled: Callable[[], None] | None
) -> tuple[tuple[Feature, ...], int]:
    """Der Rumpf von :func:`_detect_voids` — die Antwort merkt sich die Hülle."""
    found, unreadable = _voids_of(mesh, check_cancelled)
    return tuple(found), unreadable


def _voids_of(
    mesh: MeshData, check_cancelled: Callable[[], None] | None
) -> tuple[list[Feature], int]:
    """Die Einschlüsse und die Zahl unlesbarer Schalen, gerechnet (:func:`_detect_voids`)."""
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
        triangles = np.asarray(body.vertices, dtype=np.float64)[np.asarray(body.faces)[faces]]
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
        corners = np.asarray(body.vertices)[np.asarray(body.faces)[faces]].reshape(-1, 3)
        lower, upper = corners.min(axis=0), corners.max(axis=0)
        middle = (lower + upper) / 2.0
        centre: Vec3 = (float(middle[0]), float(middle[1]), float(middle[2]))
        size: Vec3 = (
            float(upper[0] - lower[0]),
            float(upper[1] - lower[1]),
            float(upper[2] - lower[2]),
        )
        measured.append((centre, size, volume, tuple(sorted(int(index) for index in faces))))
    # Nach Mitte, Ausdehnung und Volumen, zuletzt nach den Ecken — dieselbe
    # Regel wie jede andere Nummer (:func:`numbering_order`). Hier stand der
    # ungerundete Vergleich der Mitten, und zwei gleiche Hohlräume auf einer
    # Linie ordnete dann die zwölfte Stelle.
    order = numbering_order(
        len(measured),
        (
            (lambda index: measured[index][0], NUMBERING_DIGITS),
            (lambda index: measured[index][1], NUMBERING_DIGITS),
            (lambda index: (measured[index][2],), NUMBERING_DIGITS),
        ),
        lambda index: _corner_key(body, np.asarray(measured[index][3])),
    )
    found = [
        Feature(
            id=FeatureId(f"void_{number}"),
            kind="void",
            provenance="detected",
            measure_sources={"volume": "facets", "centre": "facets", "size": "facets"},
            params={"volume": volume, "centre": centre, "size": size},
            face_indices=faces,
        )
        for number, (centre, size, volume, faces) in enumerate(
            (measured[index] for index in order), start=1
        )
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
    if abs(float(axis @ np.asarray(second.axis, dtype=float))) < units.exact_cos_degrees(
        SINK_AXIS_LIMIT
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
    if abs(float(axis @ np.asarray(second.axis, dtype=float))) < units.exact_cos_degrees(
        CONE_SAME_AXIS
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

    def join(
        new: tuple[ConeFit, list[int]], known: tuple[ConeFit, list[int]]
    ) -> tuple[ConeFit, list[int]] | None:
        """Der gemeinsame Kegel zweier Flecken, wenn er einer ist."""
        if not _same_cone(new, known):
            return None
        # In der Ordnung des Körpers (:func:`in_body_order`), nicht in der
        # zufälligen Folge, in der die zwei Flecken zusammenkamen.
        together = in_body_order(body, [known[1] + new[1]])[0]
        again = fit_cone(body, together, check_cancelled=check_cancelled)
        if again is not None and again.good and again.residual <= ROUND_TOLERANCE:
            return again, together
        return None

    merged: Cones = []
    for fit, patch in found:
        for index in range(len(merged)):
            if check_cancelled is not None:
                check_cancelled()
            joined = join((fit, patch), merged[index])
            if joined is not None:
                merged[index] = joined
                break
        else:
            merged.append((fit, patch))
    apexes = np.asarray([entry[0].apex for entry in merged], dtype=float).reshape(-1, 3)
    radii = np.asarray([entry[0].radius for entry in merged], dtype=float)

    def remember(index: int, fit: ConeFit) -> None:
        """Spitze und Radius eines neuen gemeinsamen Kegels eintragen."""
        apexes[index] = np.asarray(fit.apex, dtype=float)
        radii[index] = fit.radius

    return _joined_until_stable(
        merged, _anchored_near(apexes, radii), join, remember, check_cancelled
    )


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

    **Auch über einen Durchbruch hinweg**: Zwei Bögen desselben Rings, die
    ein Durchbruch trennt, sind ein Ring — der exakte Kern liest sie ebenso
    (``brep.features._joined_tori``, RM-226 Nachtrag 04.10.2026).
    """
    if len(found) < 2:
        return found

    def join(
        new: tuple[TorusFit, list[int]], known: tuple[TorusFit, list[int]]
    ) -> tuple[TorusFit, list[int]] | None:
        """Der gemeinsame Ring zweier Flecken, wenn er einer ist."""
        if not _same_torus(new, known):
            return None
        # In der Ordnung des Körpers (:func:`in_body_order`), nicht in der
        # zufälligen Folge, in der die zwei Flecken zusammenkamen.
        together = in_body_order(body, [known[1] + new[1]])[0]
        again = fit_torus(body, together, check_cancelled=check_cancelled)
        if again is not None and again.residual <= ROUND_TOLERANCE:
            return again, together
        return None

    merged: Tori = []
    for fit, patch in found:
        for index in range(len(merged)):
            if check_cancelled is not None:
                check_cancelled()
            joined = join((fit, patch), merged[index])
            if joined is not None:
                merged[index] = joined
                break
        else:
            merged.append((fit, patch))
    centres = np.asarray([entry[0].centre for entry in merged], dtype=float).reshape(-1, 3)
    rings = np.asarray([entry[0].ring_radius for entry in merged], dtype=float)

    def remember(index: int, fit: TorusFit) -> None:
        """Mitte und Ringradius eines neuen gemeinsamen Rings eintragen."""
        centres[index] = np.asarray(fit.centre, dtype=float)
        rings[index] = fit.ring_radius

    return _joined_until_stable(
        merged, _anchored_near(centres, rings), join, remember, check_cancelled
    )
