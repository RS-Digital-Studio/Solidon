"""Arbeit am Netz selbst (Bauplan §25, Kategorie „Netz").

Drei Operationen, die ändern, wie ein Körper beschrieben ist, ohne ändern zu
wollen, was er ist: weniger Dreiecke, glattere Dreiecke, gleichmäßigere
Dreiecke. Ihren Platz verdienen sie mit Säule B — ein erzeugtes Netz kommt mit
einer halben Million Dreiecken und den Treppenstufen des Rasters an, von dem
es stammt, und beides steht allem Folgenden im Weg.

Alle drei sind verlustbehaftet, und jede sagt, wie viel sie verloren hat. Eine
Dezimierung, die eine Bohrung still um einen Zehntelmillimeter verschiebt, ist
schlimmer als eine, die es sagt.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, cast

import manifold3d
import numpy as np

from app.core.deferred import trimesh
from app.core.errors import CANCEL, CORRECT_INPUT, Action, NotManifoldError, ValidationError
from app.core.geom.attributes import transfer
from app.core.geom.mesh import MeshData, as_mesh_data, on_surface
from app.core.geom.repair import merge_vertices
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Finding, OpContext, OpResult, Severity
from app.core.units import DEGREE_UNIT
from app.i18n import _

_log = get_logger(__name__)

#: Unter so vielen Dreiecken wird nichts dezimiert. Bei einem so kleinen
#: Körper geht die Zeit nicht verloren, und jede Entfernung kostet Form.
DECIMATE_FLOOR = 500

#: Wie weit eine Dezimierung die Oberfläche verschieben darf, bevor es eine
#: Warnung wert ist — als Anteil der Modelldiagonale. Ein halbes Prozent auf
#: einem 100-mm-Teil sind 0,5 mm, mehr als eine Passung verträgt.
DEVIATION_WARN = 0.005

#: Wie oft das Neuvernetzen höchstens teilt. Jeder Durchgang vervierfacht die
#: Dreieckszahl; nach zwölf wäre aus einem Würfel eine Milliarde geworden,
#: lange bevor die Kantenlänge jemanden noch interessiert.
MAX_SUBDIVISIONS = 12

#: Und die harte Decke davor. Erreicht sie jemand, ist die Kantenlänge falsch
#: gewählt und nicht das Netz zu grob — die Meldung sagt genau das.
MAX_REMESH_TRIANGLES = 8_000_000

#: Ab welchem Zuwachs das Neuvernetzen sagt, was es gekostet hat. Ein Faktor
#: hundert ist kein Feinschliff mehr, sondern ein anderes Netz — und der Grund,
#: warum alles danach langsamer läuft.
DENSE_FACTOR = 100

#: Wie viel Volumen das Glätten kosten darf, bevor es das sagt. Ein Zehntel ist
#: an einer gescannten Oberfläche normal; ein Viertel heißt, dass der Körper
#: nicht mehr der ist, den jemand geglättet haben wollte.
SMOOTH_LOSS_WARN = 0.25


def deviation(before: MeshData, after: MeshData) -> float:
    """Wie weit die neue Oberfläche schlimmstenfalls von der alten sitzt, in mm.

    Gemessen, nicht geschätzt: jeder Eckpunkt des Ergebnisses wird nach seinem
    Abstand zur ursprünglichen Oberfläche gefragt. Das ist die Zahl, an der
    eine Passung lebt oder stirbt.
    """
    if not after.triangle_count or not before.triangle_count:
        return 0.0
    _closest, distance, _triangle = on_surface(
        before.raw, np.asarray(after.raw.vertices, dtype=float)
    )
    return float(np.max(distance)) if len(distance) else 0.0


def decimate(mesh: MeshData, target: int) -> MeshData:
    """Weniger Dreiecke für dieselbe Form, soweit das möglich ist.

    Die Materialslots reisen mit (§20). Sie taten es nicht: Die Dreiecke, die
    herauskommen, sind nicht die, die hineingingen, und ``replacing`` lässt eine
    Zuweisung fallen, deren Länge nicht mehr passt — aus 20 480 Slots wurden
    keine. Ein zweifarbiges Schild kam einfarbig aus der Operation, und im
    Viewport verlor jedes große Modell beim Dezimieren für die Anzeige seine
    Farben.

    **Ohne Grenze übertragen**, anders als nach einer Booleschen Operation: Dort
    trennt die Toleranz die alten Oberflächen von den frisch geschnittenen, die
    zu keiner gehören. Beim Dezimieren gibt es keine frisch geschnittenen — jedes
    Dreieck stammt von der alten Haut, nur gröber. Eine Grenze könnte hier
    nichts richtig machen, aber einiges falsch: Wie weit die Oberfläche wandert,
    ist genau das, was die Dezimierung aushandelt.

    Kostenlos ist das nicht, aber es kostet nur, wo es etwas zu tragen gibt:
    Ohne Slots in der Quelle kehrt die Übertragung sofort zurück, ohne eine
    einzige Näherungsanfrage — und die allermeisten Körper haben ein
    Material. (Bis zum 24.08.2026 lief die Anfrage über einen ``rtree``-Index;
    warum er weg ist, steht an :func:`app.core.geom.mesh.on_surface`.)
    """
    if mesh.triangle_count <= max(target, DECIMATE_FLOOR):
        return mesh
    source = _welded_for_simplify(mesh)
    reduced = source.raw.simplify_quadric_decimation(face_count=target)
    _log.info("decimated %d to %d triangles", mesh.triangle_count, len(reduced.faces))
    return transfer(source.replacing(reduced), [mesh], tolerance=math.inf)


#: Ab welchem Verhältnis Punkte zu Dreiecken ein Netz als unverschweißt gilt.
#: Ein geschlossenes Dreiecksnetz hat etwa halb so viele Punkte wie Dreiecke;
#: eine Dreieckssuppe, in der jedes Dreieck seine eigenen drei Punkte trägt,
#: hat dreimal so viele. Gemessen über den ganzen Korpus: jedes frisch gelesene
#: STL steht auf genau 3,00, ein verschweißter Körper auf 0,50 — dazwischen
#: liegt nichts, und die Eins ist deshalb keine Grenze, an der etwas kippt.
LOOSE_VERTEX_RATIO = 1.0


def _welded_for_simplify(mesh: MeshData) -> MeshData:
    """Verschweißt, falls nötig — die Vereinfachung verlangt geteilte Kanten.

    Quadrik-Dezimierung zieht Kanten zusammen. Wo keine Kante zwei Dreiecke
    verbindet, weil beide ihre eigenen Punkte tragen, zieht sie das Netz
    auseinander statt es zu vereinfachen: **eine Kugel aus 81 920 einzelnen
    Dreiecken kam als 12 450 Teile heraus, nicht wasserdicht.** Verschweißt
    ging dieselbe Kugel auf jedes Ziel als ein wasserdichtes Stück durch, bis
    hinunter zu 2 000 Dreiecken. Das ist der Fund „`decimate` zerlegt glatte
    Körper" (Vase 607 k → 200 k, 60 Teile) — nicht die Glätte war das
    Kennzeichen, sondern das unverschweißte Eingangsnetz, und ein Modell aus
    dem Erzeuger ist genau das.

    **Nur wenn nötig**, denn es ist nicht umsonst: Auf einem schon
    verschweißten Netz kostet `merge_vertices` 37 bis 43 Prozent der
    Vereinfachung obendrauf (103 ms zu 281 bei 328 k Dreiecken, 408 zu 951 bei
    1,3 Mio.) und bewegt dabei null Punkte. `decimate` läuft auch für die
    Anzeige im Viewport; ein Zuschlag von vierzig Prozent für nichts gehört
    dort nicht hin. Das Verhältnis Punkte zu Dreiecken beantwortet die Frage
    umsonst — es sind zwei Längen, keine Rechnung über die Geometrie.

    Die Reparaturkette danach hätte den Schaden nicht geheilt: Sie holt die
    Teilzahl zurück auf eins, die Wasserdichtheit nicht. Was zerrissen ist,
    lässt sich nicht wieder zunähen, ohne zu erfinden — also wird es nicht
    zerrissen.
    """
    if len(mesh.raw.vertices) <= mesh.triangle_count * LOOSE_VERTEX_RATIO:
        return mesh
    welded, gone = merge_vertices(mesh)
    _log.info("welded %d vertices before simplifying", gone)
    return welded


def smooth(mesh: MeshData, iterations: int) -> MeshData:
    """Nimmt das Rauschen von einer Oberfläche, ohne sie einzuziehen.

    Taubin statt Laplace: schlichtes Glätten schrumpft einen Körper mit jedem
    Durchgang ein wenig, und nach zehn Durchgängen passt ein 20-mm-Stift nicht
    mehr in ein 20-mm-Loch.
    """
    body = mesh.raw.copy()
    trimesh.smoothing.filter_taubin(body, iterations=iterations)
    return mesh.replacing(body)


def edge_lengths(mesh: MeshData) -> np.ndarray:
    """Die Länge jeder Kante des Netzes, in mm."""
    return np.asarray(mesh.raw.edges_unique_length, dtype=float)


def _subdivided_on_demand(mesh: MeshData, edge: float) -> MeshData:
    """Jedes Dreieck so oft geteilt, wie **seine** Kanten es verlangen.

    Der billige Weg, und der einzige, der die Zusage genau erfüllt statt sie zu
    übererfüllen. Er hat einen Haken: an der Naht zwischen zwei verschieden oft
    geteilten Flächen bleibt ein Punkt auf einer Kante liegen, die ihn nicht
    kennt — der Körper ist danach oft nicht mehr geschlossen. Ob er es ist,
    entscheidet der Aufrufer.
    """
    vertices, faces = trimesh.remesh.subdivide_to_size(
        np.asarray(mesh.raw.vertices, dtype=float),
        np.asarray(mesh.raw.faces, dtype=np.int64),
        max_edge=edge,
    )
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    body.merge_vertices()
    return mesh.replacing(body)


def _subdivided_evenly(mesh: MeshData, edge: float) -> MeshData:
    """Jedes Dreieck in vier, so oft, bis auch die längste Kante kurz genug ist.

    Konform: es entsteht keine Naht, der Körper bleibt geschlossen. Der Preis
    sind Dreiecke, wo es längst fein genug war — bei einem Netz mit winzigen
    Bohrungsfacetten neben großen Grundflächen wird das teuer.
    """
    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    for _step in range(MAX_SUBDIVISIONS):
        body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        lengths = np.asarray(body.edges_unique_length, dtype=float)
        if not len(lengths) or float(lengths.max()) <= edge:
            break
        if len(faces) * 4 > MAX_REMESH_TRIANGLES:
            raise _too_fine(mesh, edge, len(faces) * 4)
        vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    body.merge_vertices()
    return mesh.replacing(body)


def estimated_triangles(mesh: MeshData, edge: float) -> int:
    """Wie viele Dreiecke eine Kantenlänge ungefähr ergibt.

    Ein gleichseitiges Dreieck der Kantenlänge ``edge`` deckt
    ``√3/4 · edge²`` ab; die Oberfläche geteilt durch diese Fläche ist die
    Zahl, um die es geht. Grob, und das genügt: gefragt ist, ob eine Eingabe
    in der Größenordnung des Machbaren liegt.

    Gebraucht wird sie **vor** dem ersten Schnitt. Ohne die Schätzung lief die
    Operation erst minutenlang und scheiterte dann — der teure Weg wurde
    gegangen, um festzustellen, dass er zu teuer ist.
    """
    if edge <= 0.0:
        return MAX_REMESH_TRIANGLES + 1
    per_triangle = math.sqrt(3.0) / 4.0 * edge * edge
    return int(float(mesh.raw.area) / max(per_triangle, 1e-12))


def _too_fine(mesh: MeshData, edge: float, would_be: int) -> ValidationError:
    """Sagt, welche Kantenlänge noch ginge — die Zahl kennt nur die Operation.

    „Ergäbe mehr Dreiecke, als sich noch rechnen lassen" allein schickt den
    Nutzer ins Raten: er hat eine Zahl eingetippt, sie war zu klein, und die
    nächste ist auch nur geraten. Jede Halbierung der Kantenlänge vervierfacht
    die Dreiecke, also lässt sich die erreichbare Länge ausrechnen.
    """
    growth = would_be / max(MAX_REMESH_TRIANGLES, 1)
    # Aufgerundet, nicht gerundet: bei 0,05 mm und knapp gerissener Decke ergab
    # das Runden auf zwei Stellen wieder 0,05 — der Vorschlag nannte exakt die
    # Zahl, die gerade abgelehnt worden war, und war damit keiner (Regel 17).
    # Aufwärts ist zudem die sichere Richtung: eine längere Kante ergibt
    # weniger Dreiecke, eine kürzere könnte erneut auflaufen.
    reachable = math.ceil(edge * math.sqrt(growth) * 100.0) / 100.0
    return ValidationError(
        field="edge",
        detail=_("Diese Kantenlänge ergäbe mehr Dreiecke, als sich noch rechnen lassen."),
        constraint="maximum",
        values={
            "triangles": would_be,
            "limit": MAX_REMESH_TRIANGLES,
            "reachable": reachable,
        },
        suggestions=(
            Action(id="use_reachable", label=_("Die kleinste Kantenlänge nehmen, die noch geht.")),
            Action(id="decimate_first", label=_("Vorher dezimieren.")),
        ),
    )


def remesh(mesh: MeshData, edge: float) -> MeshData:
    """Teilt jede Kante, die länger als ``edge`` ist, bis keine mehr übrig ist.

    Kein vollwertiger Remesher — er unterteilt nur. Das ist, was eine Analyse
    braucht (eine gleichmäßige Abtastung der Oberfläche), und er verschiebt nie
    einen Punkt, es geht also nichts verloren. Dreiecke dort *gröber* zu
    machen, wo sie dicht sind, ist die Aufgabe der Dezimierung.

    **Zwei Wege, in dieser Reihenfolge** — wie die Rückfallkette der booleschen
    Operationen, und aus demselben Grund: der billige zuerst, der teure, wenn
    er muss.

    ``subdivide_to_size`` teilt nach Bedarf und ist damit sowohl billiger als
    auch genauer am Ziel. Er lässt aber an der Naht zwischen zwei verschieden
    oft geteilten Flächen einen Punkt auf einer Kante liegen, die ihn nicht
    kennt: bei einem Quader 40 x 30 x 10 waren das 192 offene Kanten und drei
    Komponenten, und die nächste boolesche Operation fiel darauf auf die
    Voxelstufe und rundete die Maße.

    ``trimesh.remesh.subdivide`` teilt jedes Dreieck in vier und lässt keine
    solche Naht entstehen — dafür zerteilt es die winzigen mit. Bei
    ``plate_holes`` (796 Dreiecke, feine Bohrungsfacetten neben großen Flächen)
    sind das 815 104 Dreiecke statt 63 040 für dasselbe Ziel.

    Also: nach Bedarf teilen, und nur wenn das Ergebnis aufgeht, gleichmäßig
    nachziehen. Ein Körper, der schon vorher offen war, kann dabei nichts
    verlieren — für ihn bleibt es beim billigen Weg.
    """
    wanted = estimated_triangles(mesh, edge)
    if wanted > MAX_REMESH_TRIANGLES:
        raise _too_fine(mesh, edge, wanted)

    on_demand = _subdivided_on_demand(mesh, edge)
    if on_demand.is_watertight or not mesh.is_watertight:
        _log.info("remeshed %d to %d triangles", mesh.triangle_count, on_demand.triangle_count)
        return on_demand
    even = _subdivided_evenly(mesh, edge)
    _log.info(
        "remeshed %d to %d triangles (evenly, on demand tore the mesh)",
        mesh.triangle_count,
        even.triangle_count,
    )
    return even


# --- gleichmäßig vernetzen und unterteilen ----------------------------------------
#
# Beides rechnet der exakte Netzkern, nicht ``trimesh``. Der Grund steht in
# ``uniform``: Ein Verfahren, das nur teilt, erreicht die *obere* Schranke der
# Kantenlänge und nie die untere — und Gleichmäßigkeit ist genau der Abstand
# zwischen beiden.


def _as_solid(mesh: MeshData) -> Any:
    """Das Netz als Körper des exakten Kerns, oder ein guter Satz dazu, warum
    nicht.

    Der Kern nimmt kein Netz an, das kein Volumen umschließt — er gibt
    wortlos einen leeren Körper zurück. Genau das ist in P16.2 an
    ``generated_figure.stl`` passiert: Die Datei trägt absichtlich die Fehler
    eines Generators, und heraus kam nichts. Ein Objekt, das beim Unterteilen
    verschwindet, ist die Sorte Fehler, die niemand mit seiner Ursache
    verbindet; also wird hier angehalten, mit dem Weg dorthin (Regel 17).
    """
    # ``Mesh64``, nicht ``Mesh``: der einfache Eingang nimmt ``float32``, und
    # der Kern rechnet in doppelter Genauigkeit (Regel 6). Bei einem Eckpunkt
    # auf 100 mm liegt zwischen zwei ``float32`` rund ein hundertstel
    # Mikrometer — unter jeder Fertigungstoleranz, aber es ist ein Verlust, den
    # niemand zu bezahlen hat, wenn der Kern die doppelte Breite selbst anbietet.
    solid = manifold3d.Manifold(
        manifold3d.Mesh64(
            np.asarray(mesh.raw.vertices, dtype=np.float64),
            np.asarray(mesh.raw.faces, dtype=np.uint64),
        )
    )
    if solid.is_empty():
        raise NotManifoldError(
            detail=_(
                "Dieser Körper umschließt kein Volumen — er lässt sich weder gleichmäßig "
                "vernetzen noch unterteilen. Erst reparieren, dann noch einmal."
            ),
            # Jede innere Kante trägt zwei Halbkanten, jede offene eine: aus
            # 3F = 2·E_innen + E_offen und E = E_innen + E_offen folgt
            # E_offen = 2E - 3F. Andersherum gerechnet kommt dieselbe Zahl mit
            # negativem Vorzeichen heraus, und ein Befund über minus achtzehn
            # offene Kanten ist schlimmer als keiner.
            open_edges=int(len(mesh.raw.edges_unique) * 2 - len(mesh.raw.faces) * 3),
        )
    return solid


def _as_mesh(mesh: MeshData, solid: Any) -> MeshData:
    """Zurück ins Netz — und die doppelten Eckpunkte wieder zusammen.

    Der Kern gibt an jeder scharfen Kante mehrere Eckpunkte an derselben
    Stelle heraus, einen je Normalenrichtung. Für einen Renderer ist das
    richtig; hier heißt es, dass ein tadelloser Würfel als sechs Komponenten
    mit offenen Kanten ankommt. Ohne das Verschweißen fällt jede Prüfung
    danach auf ein Netz herein, das nur so aussieht.
    """
    built = solid.to_mesh64()
    body = trimesh.Trimesh(
        vertices=np.asarray(built.vert_properties[:, :3], dtype=float),
        faces=np.asarray(built.tri_verts, dtype=np.int64),
        process=False,
    )
    body.merge_vertices()
    return mesh.replacing(body)


def uniform(mesh: MeshData, edge: float, deviation: float) -> MeshData:
    """Gleichmäßige Kantenlängen — nach oben wie nach unten.

    Der Unterschied zu :func:`remesh`, gemessen an ``plate_holes``: Teilen
    allein lässt das Verhältnis zwischen längster und kürzester Kante, wie es
    war (Streuung 2,22 vorher wie nachher). Es macht das Netz feiner, nicht
    gleichmäßiger — und zahlt dafür 3 260 416 Dreiecke, weil es die winzigen
    Bohrungsfacetten mitzerteilt. Hier sind es rund 30 000 für dieselbe
    Zielkantenlänge.

    Zwei Schritte, und der erste ist der, den ``remesh`` nicht hat:
    ``simplify`` räumt die überflüssig feinen Stellen ab, und zwar in einer
    zugesagten Schranke — kein Punkt der Oberfläche wandert weiter als
    ``deviation``. Erst danach wird geteilt. Mit ``deviation = 0`` fällt der
    erste Schritt aus und die Form bleibt exakt.
    """
    wanted = estimated_triangles(mesh, edge)
    if wanted > MAX_REMESH_TRIANGLES:
        raise _too_fine(mesh, edge, wanted)
    solid = _as_solid(mesh)
    evened = _as_mesh(mesh, solid.simplify(deviation).refine_to_length(edge))
    _log.info("evened %d to %d triangles", mesh.triangle_count, evened.triangle_count)
    return evened


def subdivided(mesh: MeshData, edge: float, angle: float) -> MeshData:
    """Zwischen den Dreiecken interpolieren, scharfe Kanten stehen lassen.

    Reines Teilen setzt neue Punkte in die Ebene der Facette, aus der sie
    stammen — ein Vieleck bleibt ein Vieleck, nur mit mehr Dreiecken. Erst
    Tangenten an den Halbkanten heben die neuen Punkte auf die gekrümmte
    Fläche, die das Vieleck meint. Kanten steiler als ``angle`` bekommen keine
    und bleiben scharf.

    **Über die Normalen, nicht über die Flächen.** Der naheliegende Weg
    (``smooth_out``) leitet die Tangenten aus der Dreiecksgeometrie ab und
    fasst dabei je zwei koplanare Dreiecke zu einem Viereck zusammen, dessen
    Diagonale beim Verfeinern übersprungen wird. Bei einem CAD-Netz, in dem
    jede ebene Fläche aus genau zwei Dreiecken besteht, bricht das zusammen:
    ``plate_holes`` verlor damit ein Sechstel seines Volumens und bekam 2 772
    Kanten der Länge null — und meldete sich weiter als wasserdicht.
    ``smooth_by_normals`` liest stattdessen die zuvor gerechneten
    Eckpunktnormalen und kennt keine Vierecke. Die Kugel wird darüber genauso
    rund (33 436 mm³ von 33 510 möglichen).
    """
    wanted = estimated_triangles(mesh, edge)
    if wanted > MAX_REMESH_TRIANGLES:
        raise _too_fine(mesh, edge, wanted)
    solid = _as_solid(mesh)
    smoothed = solid.calculate_normals(0, angle).smooth_by_normals(0)
    return _as_mesh(mesh, smoothed.refine_to_length(edge))


# --- operations -------------------------------------------------------------------


@op_params
class DecimateParams(BaseParams):
    triangles: int = param(
        title=_("Dreiecke"),
        default=50_000,
        minimum=DECIMATE_FLOOR,
        maximum=5_000_000,
        doc=_("Zielzahl. Weniger heißt schneller und ungenauer — wie viel, sagt der Bericht."),
    )


@register_op(
    name="decimate_mesh",
    # Nicht „Dezimieren". Das Wort ist der Fachbegriff und steht so in jedem
    # Netzwerkzeug — es sagt nur niemandem, der zum ersten Mal ein zu großes
    # Netz vor sich hat, worum es geht. Der Bezeichner bleibt, was er war;
    # geändert ist die Zeile im Menü.
    title=_("Dreiecke verringern"),
    category="mesh",
    params=DecimateParams,
    consumes=1,
    produces=1,
    doc=_(
        "Verringert die Dreieckszahl. Die größte Abweichung zur Ausgangsfläche "
        "wird gemessen und gemeldet."
    ),
    caveat=_(
        "Nicht auf einem Teil, das noch bemaßt wird: Dezimieren verschiebt Flächen, "
        "und eine Bohrung, die danach gesetzt wird, sitzt auf einer anderen Oberfläche "
        "als geplant. Zuerst konstruieren, zuletzt dezimieren."
    ),
)
def decimate_mesh(ctx: OpContext) -> OpResult:
    params = cast(DecimateParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = decimate(before, params.triangles)
    findings = _deviation_findings(before, after, source.id)
    findings.extend(_simplification_findings(before, after, params.triangles, source.id))
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=after)],
        findings=findings,
    )


@op_params
class SmoothParams(BaseParams):
    iterations: int = param(
        title=_("Durchgänge"),
        default=5,
        minimum=1,
        maximum=50,
        doc=_("Mehr Durchgänge heißt glatter. Kanten verschwinden dabei mit."),
    )


@register_op(
    name="smooth_mesh",
    title=_("Glätten"),
    category="mesh",
    params=SmoothParams,
    consumes=1,
    produces=1,
    doc=_(
        "Nimmt die Rauheit aus einer Oberfläche, ohne den Körper zu schrumpfen. "
        "Für erzeugte Netze mit Treppenstufen."
    ),
)
def smooth_mesh(ctx: OpContext) -> OpResult:
    params = cast(SmoothParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = smooth(before, params.iterations)
    findings = _deviation_findings(before, after, source.id)
    findings.extend(_smoothing_cost(before, after, source.id, params.iterations))
    return OpResult(outputs=[dataclasses.replace(source, mesh=after)], findings=findings)


def _smoothing_cost(
    before: MeshData, after: MeshData, object_id: str, iterations: int
) -> list[Finding]:
    """Was das Glätten am Körper selbst gekostet hat.

    Die Abweichungsmessung daneben sagt, wie weit die *Oberfläche* gewandert
    ist. Sie sagt nicht, dass vom Körper kaum etwas übrig ist — und genau das
    passiert an groben Netzen und dünnen Wänden.
    """
    old, new = float(before.volume), float(after.volume)
    if old <= 0.0:
        return []

    if new <= 0.0:
        # Umgestülpt: die Innenwand ist an der Außenwand vorbeigewandert. Das
        # Netz nennt sich weiter wasserdicht und misst minus neunzehntausend
        # Kubikmillimeter; jede Kennzahl danach ist falsch, und exportieren
        # ließ es sich auch. Kein Befund, ein Abbruch.
        raise ValidationError(
            field="iterations",
            detail=_(
                "Der Körper hat sich beim Glätten umgestülpt — für so viele Durchgänge "
                "ist seine Wand zu dünn."
            ),
            value=iterations,
            constraint="inverted",
            suggestions=(
                Action(id="fewer_iterations", label=_("Weniger Durchgänge nehmen.")),
                Action(
                    id="remesh_first", label=_("Vorher neu vernetzen — feiner glättet sanfter.")
                ),
            ),
        )

    lost = 1.0 - new / old
    if lost <= SMOOTH_LOSS_WARN:
        return []
    return [
        Finding(
            code="mesh.smooth_shrank",
            severity="warning",
            message=_(
                "Das Glätten hat den Körper deutlich verkleinert — an einem groben Netz "
                "zieht es die Ecken zusammen. Erst neu vernetzen, dann glätten."
            ),
            object_id=object_id,
            values={"lost": round(lost, 3), "before": round(old, 1), "after": round(new, 1)},
        )
    ]


@op_params
class RemeshParams(BaseParams):
    edge: float = param(
        title=_("Kantenlänge"),
        default=1.0,
        unit="mm",
        minimum=0.05,
        maximum=50.0,
        doc=_("Jede längere Kante wird geteilt. Kürzer heißt gleichmäßiger und größer."),
    )


@register_op(
    name="remesh_mesh",
    title=_("Kanten verfeinern"),
    category="mesh",
    params=RemeshParams,
    consumes=1,
    produces=1,
    doc=_("Teilt lange Kanten, bis das Netz gleichmäßig ist. Die Form bleibt exakt."),
)
def remesh_mesh(ctx: OpContext) -> OpResult:
    params = cast(RemeshParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = remesh(before, params.edge)
    findings = [
        Finding(
            code="mesh.remeshed",
            severity="info",
            message=_("Das Netz wurde feiner unterteilt; die Form ist unverändert."),
            object_id=source.id,
            values={"before": before.triangle_count, "after": after.triangle_count},
        )
    ]
    # Was der zweite Weg kostet, gehört gesagt. Er wird nur gegangen, wenn der
    # erste das Netz zerrissen hätte, und er zerteilt dabei auch die Dreiecke,
    # die längst fein genug waren. Danach ist jede weitere Operation langsamer,
    # und niemand wüsste warum.
    #
    # Wie teuer, hat der Sprung auf trimesh 5 verschoben: dieselbe Lochplatte
    # ging unter 4.12.2 von 796 Dreiecken auf 815 104 (Faktor 1024), unter
    # 5.0.0 auf 22 636 (Faktor 28). Die Schwelle bleibt, wo sie ist — sie
    # meint den Sprung, der eine Anzeige lahmlegt, und den gibt es weiter.
    # Nur löst der Regelfall sie nicht mehr von selbst aus, weshalb
    # `test_a_net_that_explodes_says_so` sie eigens herunterdreht.
    if after.triangle_count > before.triangle_count * DENSE_FACTOR:
        findings.append(
            Finding(
                code="mesh.remesh_dense",
                severity="info",
                message=_(
                    "Das Netz musste gleichmäßig geteilt werden, um geschlossen zu "
                    "bleiben — es trägt jetzt deutlich mehr Dreiecke."
                ),
                object_id=source.id,
                values={"before": before.triangle_count, "after": after.triangle_count},
            )
        )
    # Der Satz oben ist eine Zusicherung, und eine Zusicherung wird geprüft.
    # Solange sie nur dastand, hat sie einen zerrissenen Körper als heil
    # gemeldet — und der Fehler fiel erst zwei Operationen später auf, als die
    # Rückfallkette auf der Voxelstufe landete.
    if not after.is_watertight and before.is_watertight:
        findings.append(
            Finding(
                code="mesh.remesh_open",
                severity="warning",
                message=_(
                    "Das Netz ist beim Unterteilen aufgegangen — es ist nicht mehr "
                    "geschlossen. Reparieren, bevor es boolesch weitergeht."
                ),
                object_id=source.id,
                values={"components": after.component_count},
            )
        )
    elif not after.is_watertight:
        findings.append(
            Finding(
                code="mesh.remesh_open",
                severity="warning",
                message=_(
                    "Dieser Körper war schon vorher nicht geschlossen; das Unterteilen "
                    "ändert daran nichts."
                ),
                object_id=source.id,
                values={"components": after.component_count},
            )
        )
    return OpResult(outputs=[dataclasses.replace(source, mesh=after)], findings=findings)


@op_params
class UniformParams(BaseParams):
    edge: float = param(
        title=_("Kantenlänge"),
        default=1.0,
        unit="mm",
        minimum=0.05,
        maximum=50.0,
        doc=_(
            "Wie lang die Kanten danach ungefähr überall sind. Kürzer heißt feiner "
            "und größer — und feiner ist nur nötig, wo später geformt wird."
        ),
    )
    deviation: float = param(
        title=_("Zulässige Abweichung"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        doc=_(
            "Wie weit die Fläche dafür wandern darf. Null lässt die Form unangetastet; "
            "erst darüber verschwinden auch die überflüssig feinen Stellen."
        ),
    )


@register_op(
    name="remesh_uniform",
    title=_("Dreiecke angleichen"),
    category="mesh",
    params=UniformParams,
    consumes=1,
    produces=1,
    doc=_(
        "Bringt alle Dreiecke auf ungefähr dieselbe Größe — die groben werden geteilt, "
        "die überflüssig feinen zusammengefasst. Die Vorstufe zum Formen von Hand."
    ),
    caveat=_(
        "Nicht zum Verfeinern allein: Wer nur mehr Dreiecke will, ohne dass irgendwo "
        "welche verschwinden, nimmt „Kanten verfeinern“ — das teilt und fasst nie zusammen."
    ),
)
def remesh_uniform(ctx: OpContext) -> OpResult:
    """Gleichmäßige Dreiecke, damit ein Pinsel überall gleich wirkt.

    ``ctx.quality`` ändert hier bewusst nichts. Die Kantenlänge *ist* die
    Zusage dieser Operation; sie im Entwurf stillschweigend zu verdoppeln
    hieße, ein anderes Netz zu liefern als bestelltes — und was danach kommt,
    rechnet mit genau dieser Auflösung.
    """
    params = cast(UniformParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = uniform(before, params.edge, params.deviation)
    findings = [
        Finding(
            code="mesh.evened",
            severity="info",
            message=_("Die Dreiecke liegen jetzt gleichmäßig über der Oberfläche."),
            object_id=source.id,
            values={"before": before.triangle_count, "after": after.triangle_count},
        )
    ]
    # Gemessen wird nur, wenn es etwas zu messen gibt. Ohne zugelassene
    # Abweichung wird kein Eckpunkt verschoben, und die Messung kostet eine
    # Abstandsabfrage über zehntausende Punkte — für eine Zahl, die null ist.
    if params.deviation > 0.0:
        findings.extend(_deviation_findings(before, after, source.id))
    else:
        findings.append(
            Finding(
                code="mesh.deviation",
                severity="info",
                message=_("Die Form ist dabei unverändert geblieben."),
                object_id=source.id,
                values={
                    "deviation_mm": 0.0,
                    "before": before.triangle_count,
                    "after": after.triangle_count,
                },
            )
        )
    return OpResult(outputs=[dataclasses.replace(source, mesh=after)], findings=findings)


@op_params
class SubdivideParams(BaseParams):
    edge: float = param(
        title=_("Kantenlänge"),
        default=1.0,
        unit="mm",
        minimum=0.05,
        maximum=50.0,
        doc=_("Wie fein die neue Fläche wird. Kürzer heißt runder und teurer."),
    )
    angle: float = param(
        title=_("Kantenwinkel"),
        default=52.5,
        unit=DEGREE_UNIT,
        minimum=0.0,
        maximum=180.0,
        doc=_(
            "Ab welchem Winkel eine Kante scharf bleibt. Niedriger rundet mehr ab; "
            "über neunzig verliert auch ein Quader seine Ecken."
        ),
    )


@register_op(
    name="subdivide_surface",
    title=_("Fläche unterteilen"),
    category="mesh",
    params=SubdivideParams,
    consumes=1,
    produces=1,
    doc=_(
        "Macht aus einer kantigen Fläche eine gekrümmte: Die neuen Punkte werden nicht "
        "in die Facette gesetzt, sondern auf die Rundung, die sie meint. Scharfe Kanten "
        "bleiben scharf."
    ),
    caveat=_(
        "Nicht als Ersatz für eine gröbere Vorlage: Was hier entsteht, ist eine "
        "Interpolation der vorhandenen Facetten, keine wiedergewonnene Konstruktion. "
        "Wo es auf ein Maß ankommt, gehört die Rundung in die Skizze."
    ),
)
def subdivide_surface(ctx: OpContext) -> OpResult:
    """Unterteilen als Glättungsverfahren, nicht als Vernetzungswerkzeug.

    ``ctx.quality`` bleibt auch hier ohne Wirkung, aus demselben Grund wie bei
    :func:`remesh_uniform`: Die Kantenlänge ist die Zusage.
    """
    params = cast(SubdivideParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = subdivided(before, params.edge, params.angle)
    findings = _deviation_findings(before, after, source.id)
    findings.append(
        Finding(
            code="mesh.subdivided",
            severity="info",
            message=_("Die Fläche wurde zwischen ihren Facetten interpoliert."),
            object_id=source.id,
            values={"before": before.triangle_count, "after": after.triangle_count},
        )
    )
    return OpResult(outputs=[dataclasses.replace(source, mesh=after)], findings=findings)


#: Ab welchem **Vielfachen des Ziels** eine Vereinfachung eine Auskunft wert ist.
#:
#: Nicht „exakt verfehlt": Die Quadrik-Dezimierung landet regelmäßig ein paar
#: Dreiecke neben der Vorgabe, und daraus einen Befund zu machen hieße, bei
#: jedem zweiten Lauf etwas zu melden.
#:
#: **Die Zahl stand bis zum 31.08.2026 auf 0,95 und maß den Anteil des
#: Eingangs** — also, wie viel reduziert wurde, statt wie weit am Ziel vorbei.
#: Zwei verschiedene Achsen, und bei einem Körper mit Durchgangsloch fallen sie
#: auseinander: Ein Rohr aus 131 072 Dreiecken kommt bei jedem Ziel zwischen
#: 20 000 und 600 mit 74 592 heraus — um 43 Prozent reduziert, also weit unter
#: den fünf Prozent, ab denen gemeldet wurde, und dabei das 124-Fache der
#: verlangten Zahl. Wer 400 verlangte und 992 bekam, wurde gewarnt; wer 600
#: verlangte und 74 592 bekam, erfuhr nichts. Je weiter das Ziel verfehlt war,
#: desto seltener meldete es sich.
#:
#: **Und es ist der Alltagsfall.** Gemessen: Euler-Zahl 2 (Kugel, Quader)
#: trifft jedes Ziel exakt; Euler-Zahl 0 — ein Körper mit Durchgangsloch, also
#: jede Hülse, jeder Ring, jedes Gehäuse mit Durchbruch — bleibt stehen, ohne
#: entartete Dreiecke und ohne eine offene Kante.
SIMPLIFY_MISSED = 1.5


def _simplification_findings(
    before: MeshData, after: MeshData, target: int, object_id: str
) -> list[Finding]:
    """Sagt es, wenn das Vereinfachen sein Ziel nicht erreicht hat.

    **Der Kunde bekam bisher „Die Fläche hat sich dabei kaum verschoben."** Das
    stimmt und ist vollkommen nebensächlich: Er hatte 400 Dreiecke verlangt und
    992 bekommen, im Verlauf steht ein Schritt, und im Bild dasselbe Teil. Wer
    das liest, sucht den Fehler bei sich.

    Dass nichts passiert, ist dabei nicht einmal falsch. Gemessen an der
    Halterung aus Weg 1: 992 Dreiecke, wasserdicht, eine Komponente, keine
    entarteten Dreiecke, Euler-Zahl minus acht — ein CAD-Teil mit fünf
    Durchbrüchen, das bereits minimal trianguliert ist. Jede Kante trennt dort
    zwei Ebenen, und
    eine solche Kante zusammenzuziehen hieße, die Form zu ändern. Dieselbe
    Rechnung erreicht an Kugel und Quader jedes Ziel exakt; sie gibt hier auf,
    weil es nichts zu holen gibt.

    Gemeldet wird deshalb als Auskunft und nicht als Warnung — nichts ist
    schiefgegangen, es gab nur nichts zu tun. Die Handlung dazu ist keine
    Reparatur, sondern die Einordnung: Wer die Dreieckszahl senken will, muss
    die Form vergröbern (Glätten) oder mit dem leben, was die Form kostet.

    **Gefragt wird, wie weit das Ergebnis am Ziel vorbeiliegt** — nicht, wie
    viel es gegenüber dem Eingang eingespart hat. Die zweite Frage ließ genau
    die Fälle durch, in denen kräftig reduziert und das Ziel trotzdem um
    Größenordnungen verfehlt wurde; die Begründung steht an ``SIMPLIFY_MISSED``.
    """
    if after.triangle_count <= target or after.triangle_count > before.triangle_count:
        return []
    if after.triangle_count < target * SIMPLIFY_MISSED:
        return []
    return [
        Finding(
            code="mesh.not_simplified",
            severity="info",
            message=_(
                "Das Netz ließ sich nicht weiter vereinfachen — es trägt die Form "
                "schon mit den wenigsten Dreiecken."
            ),
            object_id=object_id,
            values={
                "target": target,
                "before": before.triangle_count,
                "after": after.triangle_count,
            },
        )
    ]


def _deviation_findings(before: MeshData, after: MeshData, object_id: str) -> list[Finding]:
    """Sagt, was es gekostet hat — gemessen an der Oberfläche, nicht aus
    Zahlen geraten.

    **Und ob der Körper dabei aufgegangen ist.** Die Abweichung allein
    beschreibt nur, wie weit sich Flächen verschoben haben; sie sagt nichts
    darüber, ob danach noch ein Körper da ist. Gemessen an einer
    heruntergeladenen Ente: *Netz vereinfachen* auf 60 000 Dreiecke machte aus
    einem geschlossenen Körper einen offenen, und im Prüfbericht stand dazu
    „Die Fläche hat sich dabei kaum verschoben" — richtig und vollkommen
    nebensächlich. Wer danach exportiert, bekommt den Befund erst dort, einen
    Arbeitsschritt zu spät.

    Die Kennung endet bewusst auf ``not_watertight``: Dieselbe Sache melden
    Einlesen, Export und Agentenzug, und die Familie trägt dieselben zwei
    Handlungen (``FINDING_ACTIONS``).
    """
    moved = deviation(before, after)
    limit = max(before.bounds.diagonal, 1.0) * DEVIATION_WARN
    severity: Severity = "warning" if moved > limit else "info"
    findings = [
        Finding(
            code="mesh.deviation",
            severity=severity,
            message=(
                _("Die Fläche hat sich dabei spürbar verschoben — Passungen neu prüfen.")
                if severity == "warning"
                else _("Die Fläche hat sich dabei kaum verschoben.")
            ),
            object_id=object_id,
            values={
                "deviation_mm": round(moved, 4),
                "before": before.triangle_count,
                "after": after.triangle_count,
            },
        )
    ]
    if before.is_watertight and not after.is_watertight:
        findings.append(
            Finding(
                code="mesh.not_watertight",
                severity="warning",
                message=_(
                    "Der Körper war geschlossen und ist es jetzt nicht mehr — "
                    "„Reparieren“ schließt die offenen Stellen."
                ),
                object_id=object_id,
                values={"before": before.triangle_count, "after": after.triangle_count},
            )
        )
    return findings


# --- Aufdicken (Konzept P15 §7 Etappe 6, D15) -----------------------------------


@op_params
class ThickenParams(BaseParams):
    thickness: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=0.1,
        # **Nach oben begrenzt, nach unten nicht.** Zehn von zwölf Wandstärken
        # im Register tragen ein Maximum (`shell_exact` meint dasselbe und
        # liegt bei 50); `thicken` war die Ausnahme. Unten bleibt es offen,
        # weil der Prüfbericht dort die bessere Auskunft gibt als eine Grenze —
        # was zwei Extrusionsbahnen für **dieses** Material heißen, weiß er,
        # und eine Zahl im Schema wüsste es nicht.
        maximum=50.0,
        doc=_(
            "Wie dick die Wand wird. Unter zwei Extrusionsbahnen ist sie fragil — "
            "was das für dieses Material heißt, sagt der Prüfbericht."
        ),
    )


@register_op(
    name="thicken",
    title=_("Offene Fläche schließen"),
    category="mesh",
    params=ThickenParams,
    consumes=1,
    produces=1,
    doc=_(
        "Gibt einer offenen Fläche eine Wand und macht sie damit zu einem Körper. "
        "Der Weg für ein Netz, das als Fläche ankommt statt als Volumen."
    ),
)
def thicken(ctx: OpContext) -> OpResult:
    """Aus einer Fläche einen Körper machen.

    Sechs von 68 echten Modellen sind nicht geschlossen; das ist bei
    Community-Modellen normal, und bis hierher war es eine Sackgasse. Der
    Prüfbericht meldete es korrekt, und danach ging nichts mehr: eine
    Boolesche Operation braucht ein Volumen, und eine Fläche hat keines.

    Ein Körper, der schon einer ist, bekommt **keine** zweite Haut, sondern
    eine Meldung. Ihn stillschweigend zu verdoppeln wäre ein Ergebnis, das
    aussieht wie das Original und beim Schneiden auffällt.
    """
    params = cast(ThickenParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    if before.raw.is_watertight:
        # **Der häufigste Griff daneben, und er kam vom Titel.** Bis zum
        # 23.08.2026 hieß diese Operation „Fläche aufdicken" und stand im
        # Menü neben „Fläche versetzen". Wer eine Fläche angeklickt hatte und
        # ihre Wand dicker haben wollte, nahm die erste — und bekam hier einen
        # Fehler, der nur „Abbrechen" anbot. Der Schritt blieb im Verlauf und
        # hielt die Auswertung an; in einem Protokoll vom selben Tag neunzehnmal
        # über sieben Minuten, dreimal hintereinander gelegt.
        raise ValidationError(
            "thickness",
            _(
                "Dieser Körper ist schon geschlossen — eine zweite Haut darüber wäre "
                "keine Wand, sondern eine Verdopplung. Eine einzelne Wand dicker "
                "macht „Fläche versetzen“; einen Hohlraum legt „Aushöhlen“ an."
            ),
            value=params.thickness,
            constraint="already_solid",
            suggestions=[
                dataclasses.replace(CORRECT_INPUT, label=_("Stattdessen Fläche versetzen")),
                CANCEL,
            ],
        )

    thickened = _thickened(before, params.thickness)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=thickened, features={})],
        findings=[
            Finding(
                code="mesh.thickened",
                severity="info",
                message=_("Aus einer offenen Fläche wurde ein Körper mit Wandstärke."),
            )
        ],
    )


def _thickened(mesh: MeshData, thickness: float) -> MeshData:
    """Die Fläche nach innen auftragen und die Ränder schließen.

    Drei Teile, und kein einziger boolescher Schnitt: die Fläche selbst bleibt
    die Außenseite, eine um die Wandstärke entlang der Punktnormalen versetzte
    Kopie mit umgedrehten Dreiecken wird die Innenseite, und für jede offene
    Kante schließt ein Viereck den Spalt dazwischen.

    Der naheliegende Weg — jedes Dreieck zu einem Prisma und alle vereinigen —
    war der erste Versuch und ist zweimal falsch: er kostet eine Boolesche
    Operation je Dreieck, und ohne sie bleiben die Innenflächen stehen. Das
    Ergebnis war ein Netz mit achtzig Flächen, das aussah wie ein Körper und
    keiner war.

    **Punktnormalen, nicht Flächennormalen.** Mit Flächennormalen bekommt jedes
    Dreieck seinen eigenen Versatz, und an jeder Kante klafft die Innenseite
    auseinander.
    """
    import numpy as np

    body = mesh.raw
    outer = np.asarray(body.vertices, dtype=float)
    inner = outer - np.asarray(body.vertex_normals, dtype=float) * thickness
    count = len(outer)

    faces = np.asarray(body.faces, dtype=np.int64)
    # Innen läuft die Umlaufrichtung andersherum, sonst zeigen dort alle
    # Normalen in den Körper hinein.
    flipped = faces[:, ::-1] + count

    edges = np.sort(np.asarray(body.edges, dtype=np.int64), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    border = unique[counts == 1]
    walls = [[first, second, second + count, first + count] for first, second in border.tolist()]
    quads = np.asarray(
        [[wall[0], wall[1], wall[2]] for wall in walls]
        + [[wall[0], wall[2], wall[3]] for wall in walls],
        dtype=np.int64,
    ).reshape(-1, 3)

    built = trimesh.Trimesh(
        vertices=np.vstack([outer, inner]),
        faces=np.vstack([faces, flipped, quads]) if len(quads) else np.vstack([faces, flipped]),
        process=True,
    )
    built.fix_normals()
    return mesh.replacing(built)
