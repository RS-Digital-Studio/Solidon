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
import math
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, NamedTuple

import numpy as np

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData, face_components, fully_stitched
from app.core.geom.repair import merge_vertices
from app.core.log import get_logger
from app.core.perceive.helix import find_helices
from app.core.types import Feature, FeatureId, Vec3
from app.core.units import EPS_GEOM, weld_digits, weld_tolerance

_log = get_logger(__name__)

#: Wie gut ein Fleck zu einem Zylinder passen muss, um als Bohrung zu zählen:
#: der Radius darf um diesen Anteil streuen, bevor die Einpassung abgelehnt wird.
CYLINDER_TOLERANCE = 0.08

#: Und wie weit die Punkte **absolut** vom eingepassten Kreis abweichen dürfen,
#: gemessen in Facettenbreiten des Netzes.
#:
#: Der Rückstand oben ist relativ zum Radius und kann einen aufgeblähten Kreis
#: deshalb nicht sehen — siehe :attr:`CylinderFit.spread`. Der Wert ist
#: gemessen: Über den Korpus liegen alle vierzehn richtigen Einpassungen bei
#: höchstens 0,0015, ein falsch eingepasster Viertelbogen bei 0,11. Zwei
#: Prozent liegen mit Faktor dreizehn über dem einen und Faktor fünf unter dem
#: anderen.
CYLINDER_SPREAD = 0.02

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
#: Ab welchem Kosinus zwei Flächennormalen als gleichgerichtet gelten — nur
#: dann kann die eine die andere verdecken, also innen liegen.
PARALLEL_FACE_COSINE: Final = 0.99

#: Zylinder unter diesem Durchmesser sind keine Merkmale, sondern Artefakte.
#:
#: Eine Düse legt 0,4 mm breite Bahnen; ein Loch von 0,05 mm hat kein Werkzeug
#: gemacht und keines wird je hineinpassen. Auf einem erzeugten Netz entstehen
#: solche Zylinderfits an jeder Stelle, an der ein paar Dreiecke zufällig um
#: eine Achse herumstehen.
#:
#: **Die Schranke gilt beiden Richtungen, und der Name sagt das.** Sie hieß
#: ``MIN_HOLE_DIAMETER`` und stand nur in :func:`detect_holes`; eine Erhebung
#: von 0,05 mm kam als Zapfen zurück, während die gleich große Vertiefung
#: daneben verworfen wurde. Ein Zapfen ist das, womit man eine Bohrung paart
#: (§14) — was für kein Werkzeug zu klein ist, ist für keine Passung zu klein.
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
#: Die Größenordnung kommt aus derselben Überlegung wie oben — eine Düse legt
#: 0,4 mm breite Bahnen, und was schmaler ist als eine halbe Bahn, hat kein
#: Werkzeug gemacht. Der Platz kommt aus der Messung: Die Streifen sind 0,013
#: bis 0,038 mm breit, das schmalste echte Merkmal über Korpus und
#: Kundendatei 0,379 mm, die schmalste echte Verrundung 0,646 mm. 0,2 liegt
#: mit Faktor fünf von beiden Seiten dazwischen.
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
    spread: float = 0.0
    """Streuung um den eingepassten Kreis, in **Facettenbreiten** des Netzes.

    **Der Rückstand allein kann einen falschen Zylinder nicht sehen**, und der
    Grund ist keine Nachlässigkeit, sondern seine Bauart: Er misst gegen den
    **eingepassten** Kreis, nicht gegen die Wirklichkeit. Ein Bogen von neunzig
    Grad passt auf unendlich viele Kreise fast gleich gut; die Einpassung
    wählt einen, und die Punkte liegen dann tatsächlich fast exakt darauf.

    Dazu kommt, dass der Rückstand **relativ** zum Radius normiert — und damit
    genau das belohnt, was er fangen soll. Gemessen an einem Viertelbogen eines
    Zylinders mit r = 3: Die Einpassung fand **r = 89,79**, dreißigmal zu groß,
    und meldete einen Rückstand von **0,0023** bei einer Schwelle von 0,08.
    Dieselbe absolute Streuung von 0,20 mm ist bei r = 3 ein Viertel des
    Radius und bei r = 90 ein Promille. Ein Fit, der den Radius aufbläht,
    verbessert seinen eigenen Rückstand.

    Dieses Feld misst deshalb **absolut** — und normiert auf die Facettenbreite
    statt auf den Radius, denn die ist die Auflösung des Netzes: Eine
    Abweichung unter einer Facettenbreite ist nicht messbar, darüber ist sie
    wirklich. Über den Korpus liegen alle vierzehn richtigen Einpassungen bei
    höchstens 0,0015, der falsche Viertelbogen bei 0,11 — Faktor
    dreiundsiebzig."""

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

SINK_AXIS_LIMIT = 2.0


#: Ab welcher Überdeckung um die Achse ein Zylinderfleck ein **ganzer**
#: Zylinder ist — darunter ist er ein Ausschnitt und damit eine Verrundung.
#:
#: Gemessen über den Korpus: Bohrungen und Zapfen überdecken 345 bis 354 Grad,
#: eine verrundete Quaderkante 90. Dreihundert Grad liegen mit weitem Abstand
#: dazwischen; die Facettierung kostet die vollen Zylinder je nach Segmentzahl
#: sechs bis fünfzehn Grad, und mehr als das darf die Schwelle nicht fordern.
FULL_TURN_SPAN = 300.0

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

#: Die Merkmalsarten, die diese Datei aus einem Netz lesen kann.
#:
#: Gebraucht wird die Liste außerhalb, und zwar für eine Unterscheidung, die
#: sonst niemand treffen kann: Ein **erzeugtes** Merkmal (§21.2) lässt sich nur
#: dann gegen die Geometrie prüfen, wenn die Erkennung seine Art überhaupt
#: sieht. Ein Gewinde sieht sie nicht — es entsteht in einem Baustein und
#: trägt seinen Namen von dort. Wer es wie eine Bohrung prüfte, verlöre es bei
#: jeder Operation, weil kein Partner zu finden ist.
DETECTABLE_KINDS: frozenset[str] = frozenset(
    {"hole", "pin", "face", "edge_loop", "cone", "sphere", "torus", "fillet"}
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
    """
    body = mesh.raw
    return hashlib.blake2b(
        np.ascontiguousarray(body.vertices, dtype=np.float64).tobytes()
        + np.ascontiguousarray(body.faces, dtype=np.int64).tobytes(),
        digest_size=16,
    ).digest()


def forget_cache() -> None:
    """Vergisst die gemerkten Erkennungen — für Tests und Messungen."""
    _FEATURE_CACHE.clear()
    _CACHE_INDICES.clear()


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
    welded, gone = merge_vertices(mesh)
    return welded if gone else mesh


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
    # **Erst das Teil, dann die Suche.** Ohne diese Zeile sieht alles
    # Folgende an einer ungeschweißten Datei null Nachbarschaften und
    # findet nichts — siehe :func:`_one_body`.
    # **Dasselbe Netz wird nicht zweimal untersucht.** Die Erkennung läuft nach
    # jeder Operation, auch nach einem Cache-Treffer, wo die Geometrie gar
    # nicht gerechnet wurde — und ein bitgleiches Netz kann keine anderen
    # Merkmale haben. Der Grund und die Zahlen stehen bei :data:`_FEATURE_CACHE`.
    key = _mesh_key(mesh)
    remembered = _FEATURE_CACHE.get(key)
    if remembered is not None:
        _FEATURE_CACHE.move_to_end(key)
        # Eine Kopie, weil der Aufrufer sein Ergebnis behalten darf. Die
        # ``Feature``-Objekte selbst sind unveränderlich (``frozen=True``) und
        # dürfen geteilt werden; die Zuordnung darüber hinein nicht.
        return dict(remembered)

    mesh = _one_body(mesh)
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
        fitted = _fitted(mesh)
        found: dict[FeatureId, Feature] = {}
        for feature in [
            *detect_holes(mesh, fitted.cylinders, fitted.cones),
            *detect_pins(mesh, fitted.cylinders),
            *detect_fillets(mesh, fitted.fillets),
            *detect_cones(mesh, fitted.cones),
            *detect_spheres(mesh, fitted.spheres),
            *detect_tori(mesh, fitted.tori),
            *detect_faces(mesh),
            *detect_edge_loops(mesh),
        ]:
            found[feature.id] = feature
        found = _threads_instead_of_phantoms(mesh, found)
    _log.info("detected %d features", len(found))
    _FEATURE_CACHE[key] = found
    _CACHE_INDICES[key] = sum(len(feature.face_indices) for feature in found.values())
    while len(_FEATURE_CACHE) > CACHE_LIMIT or sum(_CACHE_INDICES.values()) > CACHE_INDEX_LIMIT:
        oldest, _ = _FEATURE_CACHE.popitem(last=False)
        _CACHE_INDICES.pop(oldest, None)
        if not _FEATURE_CACHE:
            # Ein einzelner Eintrag über der Grenze bleibt: Ihn wegzuwerfen
            # hieße, ihn beim nächsten Aufruf sofort neu zu rechnen — der Cache
            # wäre dann nicht begrenzt, sondern aus.
            break
    return dict(found)


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


def _threads_instead_of_phantoms(
    mesh: MeshData, found: dict[FeatureId, Feature]
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
    helices = find_helices(mesh)
    if not helices:
        return found

    kept = dict(found)
    for number, helix in enumerate(helices, start=1):
        on_the_helix = set(helix.face_indices)
        for name, feature in list(kept.items()):
            if feature.kind not in _SWALLOWED_BY_A_HELIX or not feature.face_indices:
                continue
            inside = sum(1 for index in feature.face_indices if index in on_the_helix)
            if inside * 2 > len(feature.face_indices):
                del kept[name]
        identifier = FeatureId(f"thread_{number}")
        kept[identifier] = Feature(
            id=identifier,
            kind="thread",
            provenance="detected",
            params={
                "diameter": round(helix.diameter, 4),
                "pitch": round(helix.pitch, 4),
                "centre": helix.centre,
                "axis": helix.axis,
                "internal": helix.internal,
                "length": round(helix.length, 4),
            },
            face_indices=helix.face_indices,
        )
    return kept


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
        return Fitted([], [], [], [], [])

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
        planar = _large_facet_faces(body)
        curved = [index for index in range(len(body.faces)) if index not in planar]
        if not curved:
            return Fitted([], [], [], [], [])

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
                if (
                    cone.good
                    and _fits_in_the_body(mesh, cone)
                    and not _a_ball_fits_far_better(body, patch, cone)
                ):
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

        found = _merged_cylinders(body, mesh, found)
        cones = _merged_cones(body, cones)
        tori = _merged_tori(body, tori)
        found = _without_thread_turns(body, found)
        found, fillets = _split_off_fillets(body, found)

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
        for entry_list in (fillets,):
            entry_list.sort(
                key=lambda entry: (
                    round(entry[0].centre[0], 3),
                    round(entry[0].centre[1], 3),
                    round(entry[0].centre[2], 3),
                )
            )
        return Fitted(found, cones, spheres, tori, fillets)


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
                "through": _is_through(mesh, fit, cones, patch),
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
    along = int(np.argmax(axis))
    across = max(size[index] for index in range(3) if index != along)
    return fit.radius * 2.0 <= across + EPS_GEOM


def _merged_cylinders(body: trimesh.Trimesh, mesh: MeshData, found: Cylinders) -> Cylinders:
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
    for fit, patch in found:
        for index, (other, gathered) in enumerate(merged):
            if not _same_cylinder(body, (fit, patch), (other, gathered)):
                continue
            together = gathered + patch
            again = fit_cylinder(body, together)
            # **Die Vereinigung muss sich selbst rechtfertigen.** Dass zwei
            # Flecken zueinander passen, heißt nicht, dass ihre Summe eine
            # Fläche ist: An einem hohlen Quader stehen die verrundeten
            # Innenkanten oben und unten koaxial und gleich groß, und
            # zusammengefasst kam ein Zylinder heraus, den es nicht gibt —
            # samt zwei weiteren Fehlbefunden daneben. Der neue Fit darf
            # deshalb **nicht schlechter streuen** als der schlechtere der
            # beiden, aus denen er entsteht.
            if (
                again is not None
                and again.good
                and _fits_in_the_body(mesh, again)
                and again.spread <= max(fit.spread, other.spread) + EPS_GEOM
            ):
                merged[index] = (again, together)
                break
        else:
            merged.append((fit, patch))
    return merged


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


def _without_thread_turns(body: trimesh.Trimesh, found: Cylinders) -> Cylinders:
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

    Ein Gewinde ist ein **durchgehender Lauf**, und darin liegt der
    Unterschied: Seine Gänge berühren oder überlappen sich auf der Achse.
    Gemessen an ``printed_thread`` über sechs Größen, beide Richtungen und
    drei Längen ist die größte Lücke innerhalb eines Gangstapels **0,0000 mm**
    — die Windungen laufen ineinander, weil die Helix stetig steigt. Drei
    Wände dagegen haben Lücken von Millimetern (0…6, 10…16, 20…26). Verlangt
    wird deshalb, dass der Stapel **eine** Spanne bildet; die Toleranz dafür
    ist ``EPS_GEOM``, denn gemessen wird keine, und dieselbe Zahl trennt in
    :func:`_same_cylinder` schon heute überlappende von getrennten
    Abschnitten.
    """
    if len(found) < THREAD_TURNS:
        return found

    used: set[int] = set()
    for index, (fit, _patch) in enumerate(found):
        if index in used:
            continue
        axis = np.asarray(fit.axis, dtype=float)
        centre = np.asarray(fit.centre, dtype=float)
        stack = [index]
        coaxial = [index]
        for other_index, (other, _other_patch) in enumerate(found):
            if other_index == index or other_index in used:
                continue
            if abs(float(axis @ np.asarray(other.axis, dtype=float))) < math.cos(
                math.radians(SINK_AXIS_LIMIT)
            ):
                continue
            offset = np.asarray(other.centre, dtype=float) - centre
            across = offset - float(offset @ axis) * axis
            if float(np.linalg.norm(across)) > fit.radius * SINK_FIT_LIMIT:
                continue
            coaxial.append(other_index)
            if abs(other.radius - fit.radius) <= fit.radius * CYLINDER_TOLERANCE:
                stack.append(other_index)

        thread_stack: list[int] = []
        if len(stack) >= THREAD_TURNS and _one_run(
            [_axial_span(body, found[entry][1], fit.axis) for entry in stack]
        ):
            thread_stack = stack
        elif len(coaxial) >= THREAD_TURNS:
            # Nach einer robusteren Vereinigung erscheinen die Windungen nicht
            # mehr als viele gleich große Ringe, sondern als drei koaxiale
            # Zylinder verschiedener Radien, die sich über denselben axialen
            # Abschnitt überlagern. Drei gewöhnliche Stufen liegen dagegen
            # hintereinander. Nur eine echte gemeinsame Spanne macht aus der
            # zweiten Form deshalb ebenfalls einen Gewindestapel — eine
            # schärfere Forderung als der Lauf oben, und deshalb bleibt sie,
            # wie sie ist.
            spans = [_axial_span(body, found[entry][1], fit.axis) for entry in coaxial]
            if min(high for _low, high in spans) > max(low for low, _high in spans) + EPS_GEOM:
                thread_stack = coaxial

        if len(thread_stack) >= THREAD_TURNS:
            used.update(thread_stack)
            # **Und was zwischen den Windungen liegt, gehört dazu.** Der Kern
            # und der Auslauf eines Gewindes sind koaxial, aber dicker als ein
            # Gang; über den Durchmesser fallen sie nicht in den Stapel. Am
            # M6-Gewinde blieb sonst einer von acht übrig — ein Phantom weniger
            # als vorher und immer noch eins.
            low = min(_axial_span(body, found[entry][1], fit.axis)[0] for entry in thread_stack)
            high = max(_axial_span(body, found[entry][1], fit.axis)[1] for entry in thread_stack)
            for other_index, (other, other_patch) in enumerate(found):
                if other_index in used:
                    continue
                if abs(float(axis @ np.asarray(other.axis, dtype=float))) < math.cos(
                    math.radians(SINK_AXIS_LIMIT)
                ):
                    continue
                offset = np.asarray(other.centre, dtype=float) - centre
                across = offset - float(offset @ axis) * axis
                if float(np.linalg.norm(across)) > fit.radius * SINK_FIT_LIMIT:
                    continue
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


def _one_run(spans: list[tuple[float, float]]) -> bool:
    """Bilden diese Abschnitte **einen** durchgehenden Lauf auf der Achse?

    Die Frage, die ein Gewinde von einem Stapel Wände trennt: Die Gänge einer
    Helix gehen ineinander über, zwei Bohrungen durch zwei Wände haben eine
    Lücke dazwischen. Berührung zählt als Zusammenhang — ``EPS_GEOM`` ist die
    Toleranz, mit der :func:`_same_cylinder` dieselbe Frage für ein Paar
    beantwortet.
    """
    ordered = sorted(spans)
    reach = ordered[0][1]
    for low, high in ordered[1:]:
        if low > reach + EPS_GEOM:
            return False
        reach = max(reach, high)
    return True


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


def angular_span(body: trimesh.Trimesh, fit: CylinderFit, patch: list[int]) -> float:
    """Wie viel Grad um die Achse ein Fleck wirklich überdeckt.

    **Die Zahl, die eine Verrundung von einem Zapfen trennt.** Ein Zapfen ist
    ein voller Zylinder, eine Kantenverrundung ein Viertel davon — gemessen
    über den Korpus 345 bis 354 Grad gegen 90.

    Gerechnet wird über die **größte Lücke** zwischen zwei benachbarten
    Winkeln: Was übrig bleibt, ist die Überdeckung. Der Mittelwert oder die
    Spanne von kleinstem zu größtem Winkel taugten nicht — beide sind bei einem
    Fleck, der die Nahtstelle bei ±180 Grad überschreitet, bedeutungslos.
    """
    axis = np.asarray(fit.axis, dtype=float)
    centre = np.asarray(fit.centre, dtype=float)
    basis_u, basis_v = _plane_basis(axis)
    points = np.asarray(body.vertices[np.unique(body.faces[patch])], dtype=float) - centre
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
    """Ob ein Maß unter dem liegt, was überhaupt herstellbar ist.

    **Die Begründung ist wörtlich die von** :data:`MIN_CYLINDER_DIAMETER`: Was
    für kein Werkzeug groß genug ist, ist auch kein Merkmal. Sie galt für
    Bohrung und Zapfen, seit dem 03.09.2026 auch für die Verrundung — und für
    Kegel, Kugel und Torus fehlte sie weiter. Als eigene Frage, damit die
    nächste Merkmalsart sie nicht wieder übersieht.

    **Der Befund, an Roberts Modellen gemessen (03.09.2026):**
    `garden-hose-holder.3mf` (392 532 Dreiecke) lieferte **1130 Merkmale** —
    497 Kugeln, 421 Tori, 183 Kegel —, und **257 davon trugen ein Maß unter
    einer Extrusionsbahn** (0,42 mm), der kleinste Kegel 0,0074 mm. Ein
    Objektbaum mit tausend Einträgen, von denen ein Viertel Tesselierung ist,
    beantwortet keine Frage; er verdeckt die Antwort.

    Robert dazu am selben Tag: „wir brauchen auch nur Merkmale usw, die auch
    von der Größenordnung zum 3D-Drucker passen und sinnvoll sind."

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


def _a_ball_fits_far_better(body: trimesh.Trimesh, patch: list[int], cone: ConeFit) -> bool:
    """Ob dieser Fleck in Wahrheit eine Kugelfläche ist.

    **Gefragt wird nur, wenn der Kegel schon durchgekommen ist** — die
    Reihenfolge Kegel-vor-Kugel bleibt unangetastet, und ein Fleck, den der
    Kegel ablehnt, erreicht den Kugelzweig ohnehin. Diese Frage kostet also
    einen Kugelfit je *angenommenem* Kegel und nichts sonst.

    Die Zahlen und der Fall stehen bei :data:`SPHERE_BEATS_CONE`. Kurz: Eine
    Pfanne wurde zur Senkung, sobald das Netz fein genug war, weil der
    Kegelrückstand mit der Feinheit unter die Toleranz rutscht — während der
    Kugelrückstand um zwei bis vier Größenordnungen darunter liegt.
    """
    if cone.residual <= EPS_GEOM:
        # Ein exakter Kegel ist ein Kegel. Ohne diesen Zweig teilte die
        # Rechnung unten durch fast null.
        return False
    ball = fit_sphere(body, patch)
    if ball is None or not ball.good:
        return False
    return cone.residual >= ball.residual * SPHERE_BEATS_CONE


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
    # Dieselbe Werkzeugschranke wie bei Bohrung, Zapfen und Verrundung
    # (:data:`MIN_CYLINDER_DIAMETER`) — siehe :func:`_too_small_to_make`.
    big = [
        entry
        for entry in found
        if not _too_small_to_make(entry[0].radius * 2.0) and not _a_sliver(mesh.raw, entry[1])
    ]
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
        for number, (fit, patch) in enumerate(big, start=1)
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
    # **Das kleinere der beiden Maße entscheidet**, und das ist meist die
    # Röhre: Ein Ring von 40 mm aus einem Rohr von drei Zehnteln ist nichts,
    # was ein Drucker legen kann. Umgekehrt gibt es den ausgearteten Fall
    # (Röhre größer als Ring) auch, und ``min`` fängt beide, ohne dass man
    # entscheiden müsste, welcher der häufigere ist.
    big = [
        entry
        for entry in found
        if not _too_small_to_make(min(entry[0].ring_radius, entry[0].tube_radius) * 2.0)
        and not _a_sliver(mesh.raw, entry[1])
    ]
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
        for number, (fit, patch) in enumerate(big, start=1)
    ]


def detect_fillets(mesh: MeshData, fillets: Fillets | None = None) -> list[Feature]:
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
    found = _fitted(mesh).fillets if fillets is None else fillets
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
    big = [
        entry
        for entry in found
        if not _too_small_to_make(entry[0].radius * 2.0) and not _a_sliver(mesh.raw, entry[1])
    ]
    return [
        Feature(
            id=f"fillet_{number}",
            kind="fillet",
            provenance="detected",
            params={
                "radius": round(fit.radius, 4),
                "diameter": round(fit.radius * 2.0, 4),
                "axis": fit.axis,
                "centre": fit.centre,
                "length": round(_patch_extent(body, patch, fit.axis), 4),
                "recess": fit.inward,
                "residual": round(fit.residual, 4),
            },
            face_indices=tuple(patch),
        )
        for number, (fit, patch) in enumerate(big, start=1)
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
    # Dieselbe Werkzeugschranke wie bei Bohrung, Zapfen und Verrundung
    # (:data:`MIN_CYLINDER_DIAMETER`) — siehe :func:`_too_small_to_make`.
    big = [
        entry
        for entry in found
        if not _too_small_to_make(entry[0].radius * 2.0) and not _a_sliver(mesh.raw, entry[1])
    ]
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
        for number, (fit, patch) in enumerate(big, start=1)
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
    # Dieselbe Abweichung noch einmal, aber **absolut** und auf die
    # Facettenbreite bezogen: Was der Rückstand nicht sehen kann, sieht sie.
    width = float(np.sqrt(np.mean(body.area_faces[patch]) * 2.0))
    spread = float(np.mean(np.abs(distances - radius)) / width) if width > EPS_GEOM else 0.0

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
        spread=spread,
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


def _is_through(
    mesh: MeshData,
    fit: CylinderFit,
    cones: Cones | None = None,
    patch: Sequence[int] | None = None,
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
    corners = np.asarray(mesh.raw.triangles, dtype=float) - centre

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

    flat = np.stack([corners @ basis_u, corners @ basis_v], axis=-1)

    first, second, third = flat[:, 0], flat[:, 1], flat[:, 2]

    def turn(edge: np.ndarray, towards: np.ndarray) -> np.ndarray:
        """Das Kreuzprodukt zweier ebener Vektoren — von Hand, weil ``np.cross``
        seit NumPy 2 nur noch dreidimensional rechnet."""
        return np.asarray(edge[:, 0] * towards[:, 1] - edge[:, 1] * towards[:, 0], dtype=float)

    side_a = turn(second - first, -first)
    side_b = turn(third - second, -second)
    side_c = turn(first - third, -third)
    covers = ((side_a >= 0.0) & (side_b >= 0.0) & (side_c >= 0.0)) | (
        (side_a <= 0.0) & (side_b <= 0.0) & (side_c <= 0.0)
    )
    return not bool(covers.any())


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
        (facet, area, _facet_centre(body, facet))
        for facet, area in zip(facets, areas, strict=True)
        if area >= largest * MIN_FACE_SHARE
        and area >= MIN_FACE_AREA
        and all(int(index) in planar for index in facet)
    ]
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

    # **Innen oder außen — entschieden hier, wo alle Flächen bekannt sind.**
    # Die Innenwand einer ausgehöhlten Dose zeigt in dieselbe Richtung wie die
    # gegenüberliegende Außenwand, und benannt nach der Normalen hießen beide
    # „Rückseite" (Handbuchbild vom 02.09.2026: viermal derselbe Name, nur die
    # Fläche in mm² unterschied sie). Innen ist eine Fläche, wenn eine andere
    # mit gleicher Richtung in dieser Richtung weiter außen liegt. Die
    # Aufrufer von ``feature_name`` lesen das nur noch.
    normals = [np.asarray(body.face_normals[facet[0]], dtype=float) for facet, _a, _c in entries]
    centres = [np.asarray(centre, dtype=float) for _f, _a, centre in entries]
    inner_flags: list[bool] = []
    for index, (normal, centre) in enumerate(zip(normals, centres, strict=True)):
        inner_flags.append(
            any(
                other != index
                and float(np.dot(normals[other], normal)) > PARALLEL_FACE_COSINE
                and float(np.dot(centres[other] - centre, normal)) > EPS_GEOM
                for other in range(len(entries))
            )
        )

    features: list[Feature] = []
    for number, ((facet, area, centre), normal, inner) in enumerate(
        zip(entries, normals, inner_flags, strict=True), start=1
    ):
        features.append(
            Feature(
                id=f"face_{number}",
                kind="face",
                provenance="detected",
                params={
                    "area": round(area, 4),
                    "normal": (float(normal[0]), float(normal[1]), float(normal[2])),
                    "centre": (float(centre[0]), float(centre[1]), float(centre[2])),
                    "inner": inner,
                },
                face_indices=tuple(int(index) for index in facet),
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


def _merged_cones(body: trimesh.Trimesh, found: Cones) -> Cones:
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
            if not _same_cone((fit, patch), (other, gathered)):
                continue
            together = gathered + patch
            again = fit_cone(body, together)
            if again is not None and again.good and again.residual <= ROUND_TOLERANCE:
                merged[index] = (again, together)
                break
        else:
            merged.append((fit, patch))
    return merged


def _merged_tori(body: trimesh.Trimesh, found: Tori) -> Tori:
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
            if not _same_torus((fit, patch), (other, gathered)):
                continue
            together = gathered + patch
            again = fit_torus(body, together)
            if again is not None and again.residual <= ROUND_TOLERANCE:
                merged[index] = (again, together)
                break
        else:
            merged.append((fit, patch))
    return merged
