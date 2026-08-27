"""Wo eine Skizze liegt (Bauplan §30.1).

Drei Ebenen sind fest — ``plane:xy``, ``plane:xz``, ``plane:yz``. Die vierte
Möglichkeit ist ``feature:<id>``: eine erkannte planare Fläche eines Körpers.
Sie ist die interessantere, denn sie ist der Weg, auf einem vorhandenen Teil
weiterzubauen, statt daneben.

**Der Rahmen wird berechnet, nicht gespeichert.** In der Projektdatei steht nur
die Feature-ID; Ursprung und Achsen entstehen bei jeder Auswertung neu aus dem
Körper. Wäre es umgekehrt, hinge die Skizze an Zahlen von gestern und würde
still danebenliegen, sobald sich der Körper unter ihr ändert — und genau das
wäre der Fall, für den §21 die stabilen IDs eingeführt hat.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from app.core.errors import Action, ValidationError
from app.core.types import PlaneFrame, Point2, SceneObject, Vec3
from app.i18n import _

#: Zwei Richtungen gelten als parallel, wenn ihr Kreuzprodukt darunter liegt.
#: Kein Toleranzwert im Sinne von Regel 7 — hier geht es nicht um Material,
#: sondern um die Frage, ob eine Rechnung numerisch trägt.
_PARALLEL = 1e-9

#: Ab wann eine Zielebene als parallel zur Extrusionsachse gilt. Deutlich
#: großzügiger als _PARALLEL: bei einem Kosinus von einem Tausendstel steht
#: die Ebene noch fast parallel, und der Schnittpunkt läge tausendmal weiter
#: weg als der Körper groß ist. Eine solche Höhe ist rechnerisch erklärbar und
#: als Antwort unbrauchbar.
_PARALLEL_ENOUGH = 1e-3


def _normalised(vector: Vec3) -> Vec3:
    length = math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)
    if length < _PARALLEL:
        raise ValidationError(
            "plane",
            _("Diese Fläche hat keine brauchbare Richtung."),
            value=str(vector),
            constraint="degenerate_normal",
            suggestions=[
                Action(
                    id="sketch.use_global_plane",
                    label=_("Auf einer der drei Grundebenen zeichnen"),
                )
            ],
        )
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _cross(first: Vec3, second: Vec3) -> Vec3:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _dot(first: Vec3, second: Vec3) -> float:
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2]


def _length(vector: Vec3) -> float:
    return math.sqrt(_dot(vector, vector))


def frame_of(normal: Vec3, origin: Vec3) -> PlaneFrame:
    """Ein rechtshändiger Rahmen zu einer Normalen.

    Die erste Achse ist das Kreuzprodukt aus Z und der Normalen, außer die
    Normale zeigt selbst nach Z — dann ist sie ``X``. Diese Wahl ist nicht die
    einzig mögliche, aber die einzig sinnvolle: sie macht die waagerechte
    Fläche zur globalen XY-Ebene, sodass dieselbe Skizze auf dem Tisch und auf
    dem Deckel gleich herum liegt. Jede andere Regel drehte die Zeichnung um
    einen Winkel, den niemand erklären kann.
    """
    unit = _normalised(normal)
    x_axis = _cross((0.0, 0.0, 1.0), unit)
    if _length(x_axis) < _PARALLEL:
        x_axis = _cross((0.0, 1.0, 0.0), unit)
    x_axis = _normalised(x_axis)
    y_axis = _normalised(_cross(unit, x_axis))
    return PlaneFrame(origin=origin, x_axis=x_axis, y_axis=y_axis, normal=unit)


def _outward(normal: Vec3, centre: Vec3, inside: Vec3) -> Vec3:
    """Die Normale so wenden, dass sie vom Körper wegzeigt.

    Ohne das ist die Richtung Glückssache. OpenCASCADE führt die Normale einer
    planaren Fläche als Achsenrichtung ihrer Ebene, und die hängt an der
    Orientierung der Fläche im Körper, nicht an der Anschauung: der Quader in
    der Suite meldet für die Wand bei x = -20 die Richtung +X. Wer darauf
    extrudiert, baut nach innen.

    ``inside`` ist die Mitte der Hüllbox — ein Punkt, der bei einem gedruckten
    Teil im Material liegt oder wenigstens in seiner Mitte. Für eine stark
    C-förmige Form kann er daneben liegen; dann zeigt die Richtung falsch
    herum, und man dreht sie mit einer negativen Höhe um. Die aufwendigere
    Prüfung (Strahl gegen den Körper) kostet mehr, als sie hier einbringt.
    """
    away = (centre[0] - inside[0], centre[1] - inside[1], centre[2] - inside[2])
    if _dot(normal, away) < 0.0:
        return (-normal[0], -normal[1], -normal[2])
    return normal


def is_feature_plane(plane: str) -> bool:
    """Ob diese Ebenenangabe an einer Fläche hängt statt an der Welt."""
    return plane.startswith("feature:")


def frame_for(
    plane: str,
    objects: Iterable[SceneObject],
    field: str = "plane",
    suggestions: Sequence[Action] | None = None,
) -> PlaneFrame:
    """Der Rahmen zu ``feature:<id>``, gesucht über alle Objekte der Szene.

    Über alle und nicht nur über das Eingangsobjekt, weil ``sketch_extrude``
    nichts verbraucht: sie erzeugt einen Körper aus dem Nichts, und die Fläche,
    auf der sie aufsetzt, gehört einem anderen.

    ``field`` und ``suggestions`` gehören dem Aufrufer: Dieselbe Suche dient
    der Skizzenebene **und** der Zielfläche von ``up_to`` — der Fehler muss
    aber auf das Feld zeigen, in dem der Wert steht, und raten, was dort
    weiterhilft. „Auf einer der drei Grundebenen zeichnen" ist ein guter Rat
    für eine verschwundene Skizzenebene und ein irreführender für ein
    verschwundenes Höhenziel.
    """
    feature_id = plane.partition(":")[2]
    known: list[str] = []
    for entry in objects:
        for candidate, feature in entry.features.items():
            if feature.kind != "face":
                continue
            known.append(candidate)
            if candidate != feature_id:
                continue
            normal = tuple(float(value) for value in feature.params.get("normal", (0.0, 0.0, 1.0)))
            centre = tuple(float(value) for value in feature.params.get("centre", (0.0, 0.0, 0.0)))
            box = entry.mesh.bounds
            pairs = zip(box.minimum, box.maximum, strict=True)
            inside = tuple((low + high) / 2.0 for low, high in pairs)
            outward = _outward(
                (normal[0], normal[1], normal[2]),
                (centre[0], centre[1], centre[2]),
                (inside[0], inside[1], inside[2]),
            )
            return frame_of(outward, (centre[0], centre[1], centre[2]))
    raise ValidationError(
        field,
        _("Diese Fläche gibt es in der Szene nicht mehr."),
        value=feature_id,
        constraint="unknown_feature",
        values={"known_faces": known},
        suggestions=list(suggestions)
        if suggestions is not None
        else [
            Action(id="sketch.pick_face", label=_("Eine andere Fläche wählen"), primary=True),
            Action(
                id="sketch.use_global_plane", label=_("Auf einer der drei Grundebenen zeichnen")
            ),
        ],
    )


#: Die Rahmen der drei Hauptebenen — Ursprung, erste Achse, zweite Achse,
#: Normale.
#:
#: **Abgeschrieben von ``app.core.brep.profiles.PLANES`` und nicht gerechnet.**
#: Wer sie aus der Normalen ableitet, bekommt etwas anderes:
#: ``frame_of((0, 1, 0))`` liefert ``x_axis = (-1, 0, 0)``, wo ``_lift_xz``
#: ``(1, 0, 0)`` verlangt — die Zeichnung läge spiegelverkehrt, und zwar nur
#: auf einer der drei Ebenen. Ein Test hält beide Tabellen gegeneinander;
#: ohne ihn driften sie beim nächsten Nachbessern.
#:
#: **``plane:xz`` ist dabei linkshändig**, entgegen der Zusage im Docstring von
#: :class:`~app.core.types.PlaneFrame`: Dort ist ``x_axis`` kreuz ``y_axis`` gleich
#: ``(0, -1, 0)``, die Normale aber ``(0, 1, 0)``. Das ist kein Fehler, sondern
#: eine Doppelrolle — man zeichnet von vorn und extrudiert nach hinten, und die
#: „Normale" ist hier die **Extrusionsrichtung**. Bei einer Fläche des Körpers
#: fällt beides zusammen, weil :func:`_outward` sie nach außen dreht.
BASE_FRAMES: dict[str, PlaneFrame] = {
    "plane:xy": PlaneFrame(
        origin=(0.0, 0.0, 0.0),
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 1.0, 0.0),
        normal=(0.0, 0.0, 1.0),
    ),
    "plane:xz": PlaneFrame(
        origin=(0.0, 0.0, 0.0),
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 0.0, 1.0),
        normal=(0.0, 1.0, 0.0),
    ),
    "plane:yz": PlaneFrame(
        origin=(0.0, 0.0, 0.0),
        x_axis=(0.0, 1.0, 0.0),
        y_axis=(0.0, 0.0, 1.0),
        normal=(1.0, 0.0, 0.0),
    ),
}


def frame_for_plane(plane: str, objects: Iterable[SceneObject] = ()) -> PlaneFrame | None:
    """Der Rahmen zu **jeder** Ebenenangabe — Grundebene oder Fläche.

    :func:`frame_for` beantwortet nur ``feature:<id>``, und die drei
    Grundebenen liegen in ``app.core.brep.profiles``, also hinter einer
    optionalen Abhängigkeit. Wer eine Skizze **anzeigen** will, braucht beides
    und darf OpenCASCADE nicht voraussetzen.

    Nichts kommt zurück, wenn die Angabe zu keiner Ebene gehört — etwa weil
    eine Fläche nicht mehr existiert. Der Aufrufer entscheidet dann, ob er das
    meldet; eine Ausnahme wäre hier zu scharf, denn eine Ansicht, die nichts
    zeichnen kann, ist kein Fehlerfall (Regel 17 gilt der Handlung, nicht dem
    Bild).
    """
    if is_feature_plane(plane):
        try:
            return frame_for(plane, objects)
        except ValidationError:
            return None
    return BASE_FRAMES.get(plane)


def image_normal(frame: PlaneFrame) -> Vec3:
    """Die Richtung, aus der man auf die Zeichnung **richtig herum** sieht.

    Nicht dasselbe wie ``frame.normal``, und der Unterschied kostet ein
    spiegelverkehrtes Bild. Die Normale ist die Richtung, in die extrudiert
    wird; bei ``plane:xz`` zeigt sie nach hinten, weil man von vorn zeichnet
    und nach hinten aufzieht. Eine Kamera dort würde die Skizze von der
    Rückseite zeigen.

    Gesucht ist die Achse, die zu erster und zweiter Achse ein rechtshändiges
    System bildet: ``x_axis`` kreuz ``y_axis``. Für die beiden rechtshändigen
    Grundebenen und für jede Fläche eines Körpers ist sie mit der Normalen
    identisch — sie unterscheidet sich genau dort, wo es darauf ankommt.
    """
    return _cross(frame.x_axis, frame.y_axis)


def to_world(frame: PlaneFrame, point: Point2) -> Vec3:
    """Ein Zeichenpunkt als Ort im Raum.

    Der Punkt wird als Vielfaches der beiden Rahmenachsen auf den Ursprung
    addiert. Mehr ist es nicht — aber es ist die Rechnung, die darüber
    entscheidet, ob eine Skizze dort liegt, wo sie liegen soll.

    **Sie steht hier und nicht im B-Rep-Kern**, obwohl sie von dort kommt
    (``brep/profiles.py`` hatte sie als privates ``_lift_frame``). Der Grund
    ist die Anzeige: Die Zeichenfläche muss dieselbe Umrechnung machen wie die
    Auswertung, sonst liegt das Bild woanders als das Ergebnis — und sie muss
    es können, wenn OpenCASCADE gar nicht installiert ist. Eine Rechnung, die
    an zwei Orten steht, driftet; eine, die im optionalen Kern steht, fehlt.
    """
    return (
        frame.origin[0] + point[0] * frame.x_axis[0] + point[1] * frame.y_axis[0],
        frame.origin[1] + point[0] * frame.x_axis[1] + point[1] * frame.y_axis[1],
        frame.origin[2] + point[0] * frame.x_axis[2] + point[1] * frame.y_axis[2],
    )


def to_plane(frame: PlaneFrame, point: Vec3) -> Point2:
    """Ein Ort im Raum als Zeichenpunkt — die Umkehrung von :func:`to_world`.

    Projiziert wird auf die beiden Rahmenachsen; der Abstand zur Ebene fällt
    dabei weg. Das ist Absicht und der Zweck: Was der Zeiger im Raum trifft,
    liegt nie exakt auf der Ebene, und die Zeichnung will die zwei Zahlen, mit
    denen sie rechnet, nicht die dritte.

    Weil die Achsen orthonormal sind (:func:`frame_of`), genügt das
    Skalarprodukt — es braucht keine Matrixumkehrung.
    """
    gap = (
        point[0] - frame.origin[0],
        point[1] - frame.origin[1],
        point[2] - frame.origin[2],
    )
    return (_dot(gap, frame.x_axis), _dot(gap, frame.y_axis))


def ray_hit(frame: PlaneFrame, origin: Vec3, direction: Vec3) -> Point2 | None:
    """Wo ein Sichtstrahl die Zeichenebene trifft — als Zeichenpunkt.

    Das ist die Rechnung hinter „der Zeiger steht auf der Skizzenebene": Der
    Viewport liefert den Strahl durch eine Bildschirmstelle, und hier wird
    daraus das Zahlenpaar, mit dem die Zeichnung arbeitet.

    **Sie steht im Kern, weil sie sonst nicht prüfbar wäre.** Offscreen gibt
    es keinen Plotter (``Viewport._available``), also auch keinen Strahl —
    alles, was hinter einem Plotter-Zugriff liegt, ist in der Suite ein
    Rückgabebefehl. Die Rechnung davor zu trennen ist der einzige Weg, sie
    gegen Zahlen zu prüfen statt gegen ein Bild.

    ``direction`` muss nicht normiert sein: Der Strahl kommt als Schritt von
    der nahen zur fernen Ebene, und für den Schnittpunkt zählt nur seine
    Richtung.

    Nichts kommt zurück, wenn der Strahl die Ebene nicht *vorwärts* trifft —
    entweder weil er (beinahe) parallel zu ihr läuft, oder weil sie hinter dem
    Ausgangspunkt liegt. Beides heißt an der Oberfläche dasselbe: Hier ist
    keine Stelle, auf die man zeigen kann.

    **Die Parallelprüfung misst den Winkel, nicht das Skalarprodukt.** Ohne
    die Division durch die Länge hinge sie daran, wie lang der übergebene
    Vektor zufällig ist: Ein Strahl von der nahen zur fernen Ebene ist
    hunderte Millimeter lang, und ein streifender Blick käme damit auf ein
    Skalarprodukt weit über jeder festen Schwelle. Die Prüfung liefe ins Leere,
    ohne je zu melden, dass sie es tut.
    """
    span = _length(direction)
    if span < _PARALLEL:
        return None
    along = _dot(direction, frame.normal) / span
    if abs(along) < _PARALLEL_ENOUGH:
        return None
    along *= span
    gap = (
        frame.origin[0] - origin[0],
        frame.origin[1] - origin[1],
        frame.origin[2] - origin[2],
    )
    reach = _dot(gap, frame.normal) / along
    if reach < 0.0:
        return None
    return to_plane(
        frame,
        (
            origin[0] + reach * direction[0],
            origin[1] + reach * direction[1],
            origin[2] + reach * direction[2],
        ),
    )


def height_to(start: PlaneFrame, target: PlaneFrame) -> float:
    """Wie hoch von der Skizzenebene bis zur Zielebene (D14).

    Die Extrusionsachse läuft vom Ursprung der Skizze entlang ihrer Normalen;
    gesucht ist der Parameter, bei dem sie die Zielebene trifft. Nur die Ebene
    der Zielfläche zählt, nicht ihr Umriss — „bis zu dieser Fläche" heißt im
    CAD seit jeher „bis auf ihre Höhe", und alles andere wäre ein Schnitt, für
    den es die Differenz gibt.

    Zwei Fälle enden hier statt in einer Zahl. Eine Zielebene parallel zur
    Achse wird nie erreicht; ohne diese Prüfung käme aus der Division durch
    beinahe null ein Körper von Kilometerhöhe. Und eine Fläche hinter der
    Skizze ergäbe eine negative Höhe — rückwärts durch die eigene Zeichnung.
    """
    direction = start.normal
    along = _dot(direction, target.normal)
    if abs(along) < _PARALLEL_ENOUGH:
        raise ValidationError(
            "up_to",
            _("Diese Fläche liegt parallel zur Richtung — sie wird nie erreicht."),
            value=str(target.origin),
            constraint="target_parallel",
            suggestions=[
                Action(id="sketch.pick_face", label=_("Eine andere Fläche wählen"), primary=True),
                Action(id="sketch.enter_height", label=_("Die Höhe von Hand eintragen")),
            ],
        )
    gap = (
        target.origin[0] - start.origin[0],
        target.origin[1] - start.origin[1],
        target.origin[2] - start.origin[2],
    )
    height = _dot(gap, target.normal) / along
    if height <= 0.0:
        raise ValidationError(
            "up_to",
            _("Diese Fläche liegt hinter der Skizze — von dort aus geht es nicht vorwärts."),
            value=f"{height:.3f}",
            constraint="target_behind",
            suggestions=[
                Action(
                    id="sketch.pick_face",
                    label=_("Eine Fläche in Richtung der Zeichnung wählen"),
                    primary=True,
                ),
                Action(id="sketch.flip_plane", label=_("Die Skizze auf die andere Fläche legen")),
            ],
        )
    return height


def axis_hit(frame: PlaneFrame, base: Point2, origin: Vec3, direction: Vec3) -> float | None:
    """Wie hoch über der Zeichenebene ein Sichtstrahl ihre Aufzugsachse trifft.

    Das Gegenstück zu :func:`ray_hit`, für den **Ziehgriff** (§30.1): Dort
    wird eine Stelle auf der Ebene gesucht, hier eine Höhe über ihr. Die Achse
    läuft durch ``base`` entlang ``frame.normal`` — also entlang genau der
    Richtung, in die :func:`app.core.brep.profiles.extrude` aufzieht. Der
    Rückgabewert ist deshalb unmittelbar die Höhe der Operation, mit Vorzeichen.

    Getroffen wird eine Gerade selten; gesucht ist die Stelle der **größten
    Annäherung** von Achse und Strahl. Ein Schnitt mit einer Hilfsebene wäre
    der naheliegendere Weg und der schlechtere: Welche Ebene das sein müsste,
    hängt an der Kameradrehung, und in der Querschau — dort, wo gezogen wird —
    steht die Zeichenebene selbst beinahe parallel zum Blick.

    ``direction`` muss nicht normiert sein: Sie kommt als Schritt von der
    nahen zur fernen Ebene und ist hunderte Millimeter lang.

    Nichts kommt zurück, wenn der Strahl (beinahe) **entlang** der Achse
    läuft — dann liegt sie als Punkt im Bild, und keine Mausbewegung könnte
    eine Höhe bedeuten. Geprüft wird der Sinus des Winkels zwischen beiden und
    gegen dieselbe Schwelle wie in :func:`ray_hit`: Dort fällt der Blick aus,
    der die Ebene streift, hier der, der auf sie zeigt. Dieselbe Zahl auf die
    Gegenfrage — nicht eine zweite Schwelle daneben.
    """
    span = _length(direction)
    if span < _PARALLEL:
        return None
    # Kosinus zwischen Strahl und Achse; die Normale ist normiert
    # (:func:`frame_of`), die Richtung nicht.
    along = _dot(direction, frame.normal) / span
    # ``1 - cos²`` kann bei einem Kosinus knapp über eins negativ werden — das
    # ist Fließkomma, kein Fall. ``max`` fängt es ab, statt ``sqrt`` zu
    # überlassen, was es damit tut.
    sideways = math.sqrt(max(1.0 - along * along, 0.0))
    if sideways < _PARALLEL_ENOUGH:
        return None
    anchor = to_world(frame, base)
    gap = (
        anchor[0] - origin[0],
        anchor[1] - origin[1],
        anchor[2] - origin[2],
    )
    # Die Kleinste-Quadrate-Lösung für den Abstand zweier Geraden, in zwei
    # Schritten: erst der Parameter auf dem **Strahl**, dann der auf der Achse.
    #
    # Mit ``w = anchor - origin``, ``n`` der Normalen und ``d`` der Richtung
    # verschwinden beide Ableitungen bei
    #
    #     s = (w·d - (w·n)(n·d)) / (|d|² sin²)
    #     t = s (n·d) - (w·n)
    #
    # und ``|d|² sin²`` ist genau die Größe, die oben schon geprüft ist.
    #
    # **Auf das Vorzeichen des Zählers kommt es an, und es fällt fast nie
    # auf.** Eine erste Fassung rechnete ``(cross_dot·axis_dot - ray_dot)``,
    # also ``-s``, und gab damit ``t`` um ``2 s (n·d)`` verschoben zurück. Der
    # Fehlerterm verschwindet bei ``n·d = 0`` — also bei jedem Blick genau quer
    # zur Aufzugsachse, und das ist der Normalfall der Querschau, an dem man so
    # eine Funktion prüft. Gemessen an einem Strahl, der die Achse in
    # ``(0, 0, 10)`` **exakt trifft**: 90 statt 10 (gefunden von der
    # Review-Sitzung, 27.08.2026). Der exakte Treffer ist deshalb der Testfall,
    # der hier zählt — sein Sollwert steht ohne Rechnung fest.
    axis_dot = _dot(gap, frame.normal)
    ray_dot = _dot(gap, direction)
    cross_dot = _dot(frame.normal, direction)
    reach = (ray_dot - cross_dot * axis_dot) / (span * span * sideways * sideways)
    return reach * cross_dot - axis_dot
