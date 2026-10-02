"""Sculpting: viele Gesten, eine Operation (Bauplan §25, Konzept P16 §7.1).

Eine Figur sind mehrere tausend Striche. Jeder davon als eigener Schritt im
Verlauf wäre kein Verlauf mehr, und die naive Wiedergabe — je Strich ein
Durchgang über alle Eckpunkte — kostet das Produkt aus Strichzahl und
Eckpunktzahl: bei 200 000 Eckpunkten und 1 000 Strichen rund anderthalb
Minuten je Auswertung.

Deshalb rechnet dieses Modul **akkumuliert**: ein KD-Baum über die Eckpunkte,
je Strich eine Kugelabfrage, Gewichte summieren, einmal verschieben. Gemessen
in P16.2 ist das Faktor sechzig, und es ist der Unterschied zwischen „geht
nicht" und „geht".

Der Preis steht als Entscheidung C im Konzept und wird hier nicht versteckt:
Striche derselben Etappe sind **kommutativ**. Zweimal über dieselbe Stelle zu
fahren addiert zwei Gewichte auf die Ausgangsfläche, statt den zweiten Zug auf
das Ergebnis des ersten zu setzen. Drei Werkzeuge lassen sich so nicht rechnen
und beginnen von selbst eine neue Etappe (:data:`ORDERED_TOOLS`), und jeder
Strich kann eine erzwingen (``cut``) — wer die exakte Reihenfolge braucht,
kauft sie sich stückweise statt für die ganze Sitzung.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Sequence
from dataclasses import replace
from typing import Any, Final, cast, get_args

import numpy as np

from app.core.deferred import cKDTree, trimesh
from app.core.errors import CANCEL, SHOW_LOCATION, ValidationError
from app.core.geom.intersections import crossing_face_pairs
from app.core.geom.mesh import MeshData, as_mesh_data, ray_hits_batch, read_mesh
from app.core.registry import op_params, param, register_op
from app.core.types import (
    ORDERED_TOOLS,
    BaseParams,
    CancelToken,
    Finding,
    OpContext,
    OpResult,
    Profile,
    SculptTool,
    Stroke,
    Vec3,
    as_vec3,
)
from app.core.units import EPS_GEOM
from app.i18n import _

#: Die drei Symmetrieebenen als Bit im Feld ``Stroke.symmetry``.
AXIS_BITS: Final[tuple[tuple[int, int], ...]] = ((1, 0), (2, 1), (4, 2))

#: Wie weit ein Strich über seinen Radius hinaus noch etwas bewirkt. Die
#: Gewichtsfunktion fällt glockenförmig ab und wird am Rand nicht exakt null;
#: hart abzuschneiden ist richtig, weil ein Pinsel eine Grenze hat, die man
#: sieht — und weil nur so die Vorschau auf die getroffenen Eckpunkte
#: beschränkt bleiben kann (P16.2).
FALLOFF: Final = 1.0


def stages(strokes: Sequence[Stroke]) -> list[list[Stroke]]:
    """Die Strichliste in Abschnitte zerlegen, die je in einem Durchgang gehen.

    Ein Abschnitt endet vor einem Strich, der den Zustand vor sich liest
    (``smooth``, ``inflate``, ``flatten``), vor einem erzwungenen Schnitt — und
    nach einem solchen Strich wieder, denn was er hinterlässt, muss der
    nächste sehen.

    Der erste Strich beginnt nie eine zweite Etappe: Vor ihm liegt nichts, was
    er lesen könnte, und ein leerer Durchgang kostet nur Zeit.
    """
    parts: list[list[Stroke]] = []
    current: list[Stroke] = []
    for stroke in strokes:
        breaks = stroke.cut or stroke.tool in ORDERED_TOOLS
        if breaks and current:
            parts.append(current)
            current = []
        current.append(stroke)
        if stroke.tool in ORDERED_TOOLS:
            parts.append(current)
            current = []
    if current:
        parts.append(current)
    return parts


def mirror_centre(mesh: MeshData) -> np.ndarray:
    """Wo die Symmetrieebenen eines Körpers liegen: in der Mitte seines
    Hüllquaders vor den Zügen.

    **Nicht am Schwerpunkt** — der wandert beim Formen, und eine
    Symmetrieebene, die sich unter der Hand bewegt, ist die Sorte
    Überraschung, die Vertrauen kostet. **Und nicht am Nullpunkt der Szene**:
    Dort lag sie bis RM-363, und an jedem Körper abseits der Mitte ging die
    Spiegelung ins Leere — Symmetrie Z an keinem Körper auf dem Bett.
    Die Mitte des Körpers vor den Zügen steht fest, solange der Schritt
    davor sich nicht ändert, und wandert mit, wenn er sich bewegt.
    """
    bounds = np.asarray(mesh.raw.bounds, dtype=float)
    if bounds.shape != (2, 3) or not np.isfinite(bounds).all():
        return np.zeros(3)
    middle: np.ndarray = (bounds[0] + bounds[1]) / 2.0
    return middle


def _mirrored(stroke: Stroke, centre: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Punkt und Richtung des Strichs, dazu jede verlangte Spiegelung an den
    Ebenen durch ``centre`` (:func:`mirror_centre`)."""
    point = np.asarray(stroke.point, dtype=float)
    direction = np.asarray(stroke.normal, dtype=float)
    places = [(point, direction)]
    for bit, axis in AXIS_BITS:
        if not stroke.symmetry & bit:
            continue
        flip = np.ones(3)
        flip[axis] = -1.0
        places = [
            *places,
            *[((place - centre) * flip + centre, way * flip) for place, way in places],
        ]
    return places


def _weights(tree: cKDTree, points: np.ndarray, centre: np.ndarray, radius: float) -> Any:
    """Wen dieser Strich trifft und wie stark — Indizes und Gewichte.

    Die Kugelabfrage ist der ganze Trick: Sie kostet die Zahl der
    *tatsächlich* getroffenen Punkte, nicht die Zahl aller. In P16.2 gemessen:
    ein Strich trifft 10 595 von 3 932 160 Eckpunkten, und der Unterschied
    zwischen beiden Zahlen ist das Leistungsbudget.
    """
    near = np.asarray(tree.query_ball_point(centre, radius * FALLOFF), dtype=np.int64)
    if not len(near):
        return near, np.zeros(0)
    away = np.linalg.norm(points[near] - centre, axis=1) / max(radius, 1e-9)
    return near, np.exp(-4.0 * away * away) * (away <= FALLOFF)


def _neighbours(mesh: trimesh.Trimesh, count: int) -> tuple[np.ndarray, np.ndarray]:
    """Für jeden Eckpunkt die Summe seiner Nachbarn und deren Zahl.

    Einmal je Etappe gerechnet, nicht je Strich: Glätten und Flachziehen
    brauchen dieselbe Nachbarschaft, und sie ändert sich innerhalb einer
    Etappe nicht — die Topologie bleibt, wie sie war.
    """
    edges = np.asarray(mesh.edges, dtype=np.int64)
    total = np.zeros((count, 3), dtype=float)
    seen = np.zeros(count, dtype=float)
    vertices = np.asarray(mesh.vertices, dtype=float)
    np.add.at(total, edges[:, 0], vertices[edges[:, 1]])
    np.add.at(seen, edges[:, 0], 1.0)
    return total, np.maximum(seen, 1.0)


def _offsets(
    mesh: MeshData,
    strokes: Iterable[Stroke],
    missed: list[Stroke] | None = None,
    cancelled: CancelToken | None = None,
    centre: np.ndarray | None = None,
    *,
    front_only: bool = True,
    mirror_once: bool = True,
) -> np.ndarray:
    """Das Offsetfeld einer Etappe: alle Striche summiert, ein Durchgang.

    ``missed`` sammelt die Striche, die keinen einzigen Eckpunkt greifen —
    hier und nicht anderswo, weil die Kugelabfrage es ohnehin feststellt.
    Was daraus wird, steht in ``_sculpting_findings``.

    ``cancelled`` wird vor jedem Zug gefragt (§15.6): Eine Sitzung mit
    tausenden Zügen ist ein Suchlauf je Zug, und bis zum 22.09.2026 wirkte der
    Abbrechen-Knopf erst, wenn alle gerechnet waren.
    """
    body = mesh.raw
    points = np.asarray(body.vertices, dtype=float)
    normals = np.asarray(body.vertex_normals, dtype=float)
    tree = cKDTree(points)
    plane = mirror_centre(mesh) if centre is None else np.asarray(centre, dtype=float)
    shift = np.zeros_like(points)

    smoothing = [s for s in strokes if s.tool in ORDERED_TOOLS]
    total, seen = _neighbours(body, len(points)) if smoothing else (points, np.ones(len(points)))
    curvature = np.zeros(len(points))
    if any(s.tool == "inflate" for s in smoothing):
        # Krümmung als Abstand zum Nachbarschaftsmittel entlang der Normale:
        # positiv, wo die Fläche nach innen gewölbt ist. Eine Näherung, und
        # die richtige — sie kostet nichts über die Nachbarn hinaus, die für
        # das Glätten ohnehin gebraucht werden.
        middle = total / seen[:, None]
        curvature = np.einsum("ij,ij->i", middle - points, normals)

    for stroke in strokes:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        touched = False
        places = []
        for centre, direction in _mirrored(stroke, plane):
            near, weight = _weights(tree, points, centre, stroke.radius)
            if not len(near):
                continue
            touched = True
            if front_only:
                weight = weight * _facing(normals[near], direction)
            places.append((centre, direction, near, weight))
        if mirror_once and len(places) > 1:
            places = _strongest_copy(places)
        for centre, direction, near, weight in places:
            if not np.any(weight > 0.0):
                continue
            scale = (weight * stroke.strength)[:, None]
            if stroke.tool == "draw":
                shift[near] += direction * scale
            elif stroke.tool == "carve":
                shift[near] -= direction * scale
            elif stroke.tool == "pinch":
                towards = centre - points[near]
                shift[near] += towards * scale * 0.5
            elif stroke.tool == "smooth":
                middle = total[near] / seen[near, None]
                shift[near] += (middle - points[near]) * scale
            elif stroke.tool == "inflate":
                shift[near] += normals[near] * (curvature[near][:, None] + 1.0) * scale
            elif stroke.tool == "flatten":
                # Die Ebene bildet sich aus dem, was der Pinsel greift: ihr
                # Aufpunkt ist der gewichtete Mittelwert der getroffenen
                # Punkte, ihre Normale die Strichrichtung. Eine feste Ebene
                # durch den Klickpunkt wäre die naheliegende Wahl und die
                # falsche — sie schnitte in den Körper, sobald der Pinsel
                # größer ist als die Wölbung darunter.
                anchor = np.average(points[near], axis=0, weights=weight)
                height = np.einsum("ij,j->i", points[near] - anchor, direction)
                shift[near] -= direction * (height[:, None] * scale)
        if missed is not None and not touched:
            missed.append(stroke)
    return shift


#: Ab welchem Skalarprodukt zwischen Eckpunktnormale und Strichrichtung ein
#: Punkt dem Pinsel zugewandt ist. Null heißt: die ganze zugewandte
#: Halbkugel — eine Rundung unter dem Pinsel bleibt erreichbar, die Rückseite
#: einer dünnen Wand nicht (RM-376). Eine Richtung, keine Toleranz.
FACING_LIMIT: Final = 0.0


def _facing(normals: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """1 für Punkte, die dem Pinsel zugewandt sind, sonst 0 (RM-376).

    Der Pinsel griff jeden Eckpunkt in seiner Kugel, auch die Unterseite einer
    dünnen Wand und die Innenwand eines Hohlkörpers: *Abtragen* auf einer
    4-mm-Platte drückte die Unterseite 3,7 mm unter das Bett. Elementweise wie
    jeder Strahl im Kern (RM-187).
    """
    along = (
        normals[:, 0] * direction[0] + normals[:, 1] * direction[1] + normals[:, 2] * direction[2]
    )
    return np.asarray(along > FACING_LIMIT, dtype=float)


def _strongest_copy(places: list[Any]) -> list[Any]:
    """Je Eckpunkt nur die stärkste Kopie eines gespiegelten Zugs (RM-378).

    Ein Zug auf der Symmetrieebene wirkte mit seinem Spiegelbild zweimal am
    selben Ort, je näher an der Ebene, desto mehr. Mit der stärksten Kopie je
    Punkt wirkt er dort wie ein einzelner Zug; wo sich die Kopien nicht
    überdecken, ändert sich nichts. Gleich starke Kopien entscheidet die
    Reihenfolge — reproduzierbar aus den Parametern (Regel 2).
    """
    indices = np.concatenate([near for _centre, _direction, near, _weight in places])
    weights = np.concatenate([weight for _centre, _direction, _near, weight in places])
    owner = np.concatenate(
        [np.full(len(near), number) for number, (_c, _d, near, _w) in enumerate(places)]
    )
    order = np.lexsort((owner, -weights, indices))
    first = np.ones(len(order), dtype=bool)
    first[1:] = indices[order][1:] != indices[order][:-1]
    keep = np.zeros(len(order), dtype=bool)
    keep[order[first]] = True
    kept: list[Any] = []
    start = 0
    for centre, direction, near, weight in places:
        mask = keep[start : start + len(near)]
        start += len(near)
        kept.append((centre, direction, near[mask], weight[mask]))
    return kept


def median_edge(mesh: MeshData) -> float:
    """Die mittlere Kantenlänge — das Maß, an dem ein Pinsel sich messen lässt.

    Der Median und nicht der Mittelwert: Ein einziges entartetes Dreieck zieht
    den Mittelwert nach unten und ließe ein grobes Netz fein aussehen.
    """
    lengths = np.asarray(mesh.raw.edges_unique_length, dtype=float)
    return float(np.median(lengths)) if len(lengths) else 0.0


def stroke_at(
    mesh: MeshData,
    point: Vec3,
    *,
    radius: float,
    strength: float,
    tool: str = "draw",
    symmetry: int = 0,
    cut: bool = False,
) -> Stroke:
    """Aus einem angeklickten Punkt einen Strich machen.

    Die Oberfläche liefert einen Ort, keine Richtung — und die Richtung ist
    das, woran der Strich trägt. Sie kommt hier aus der Normale des nächsten
    Eckpunkts: Bei einem Pinsel von einigen Millimetern ist das genau genug,
    und es geht ohne den Abstandsindex, der auf dieser Maschine danebengreift.

    Im Kern und nicht in der Oberfläche, weil es Geometrie ist. Was das Fenster
    beisteuert, sind zwei Zahlen und ein Klick.
    """
    points = np.asarray(mesh.raw.vertices, dtype=float)
    if not len(points):
        return Stroke(point=point, normal=(0.0, 0.0, 1.0), radius=radius, strength=strength)
    _away, index = cKDTree(points).query(np.asarray(point, dtype=float))
    normal = np.asarray(mesh.raw.vertex_normals, dtype=float)[int(index)]
    return Stroke(
        point=point,
        normal=(float(normal[0]), float(normal[1]), float(normal[2])),
        radius=radius,
        strength=strength,
        tool=tool,  # type: ignore[arg-type]
        symmetry=symmetry,
        cut=cut,
    )


def apply_strokes(
    mesh: MeshData,
    strokes: Sequence[Stroke],
    missed: list[Stroke] | None = None,
    *,
    cancelled: CancelToken | None = None,
    centre: Vec3 | None = None,
    front_only: bool = True,
    mirror_once: bool = True,
) -> MeshData:
    """Die ganze Strichliste auswerten — Etappe für Etappe, jede in einem Zug.

    ``warp`` ändert die Topologie nicht: Es kommen keine Dreiecke dazu, und
    keines verschwindet. Wer eine feine Falte in ein grobes Netz sculpten will,
    braucht vorher Eckpunkte — dafür gibt es ``remesh_uniform`` (Entscheidung
    E), und der Editor misst und sagt es, bevor jemand vergeblich malt.

    ``centre`` ist der Punkt, durch den die Symmetrieebenen gehen. Ohne
    Angabe die Mitte von ``mesh`` vor dem ersten Zug (:func:`mirror_centre`)
    — einmal genommen, nicht je Etappe, damit die Ebene beim Formen steht.

    ``front_only`` lässt nur dem Pinsel zugewandte Punkte wirken (RM-376),
    ``mirror_once`` einen Zug auf der Symmetrieebene nur einmal (RM-378).
    Beide sind die Vorgabe; alte Formschritte tragen ``False`` (Format 41).
    """
    if not strokes:
        return mesh
    plane = mirror_centre(mesh) if centre is None else np.asarray(centre, dtype=float)
    body = mesh.raw
    for part in stages(strokes):
        moved = np.asarray(body.vertices, dtype=float) + _offsets(
            mesh.replacing(body),
            part,
            missed,
            cancelled,
            plane,
            front_only=front_only,
            mirror_once=mirror_once,
        )
        body = trimesh.Trimesh(vertices=moved, faces=body.faces, process=False)
    return mesh.replacing(body)


# --- Serialisierung -------------------------------------------------------------
#
# Als JSON-Text im Parameter, nach dem Vorbild von ``kind="sketch"`` (§30.1).
# Kurze Schlüssel, weil bis zweitausend Striche im ``project.json`` liegen und
# der Unterschied zwischen ``p`` und ``point`` dort das Doppelte an Bytes ist.


def strokes_to_text(strokes: Sequence[Stroke]) -> str:
    """Die Strichliste als kompakter JSON-Text."""
    return json.dumps(
        [
            {
                "p": [round(value, 6) for value in stroke.point],
                "n": [round(value, 6) for value in stroke.normal],
                "r": round(stroke.radius, 6),
                "s": round(stroke.strength, 6),
                "t": stroke.tool,
                "y": stroke.symmetry,
                "c": stroke.cut,
            }
            for stroke in strokes
        ],
        separators=(",", ":"),
    )


def strokes_from_text(text: str) -> list[Stroke]:
    """Zurück aus dem Parameterwert. Leerer Text ist eine leere Sitzung.

    Der Text kommt aus einer Projektdatei oder dem Feld *Striche* — beides
    fremde Eingabe. Ein verdorbener Text endete als „unerwarteter Fehler“ mit
    *Fehler melden*; jetzt ist er ein Eingabefehler mit Ausweg, wie beim
    Skelett (RM-367, W4-3).
    """
    if not text.strip():
        return []
    try:
        entries = json.loads(text)
        strokes = [
            Stroke(
                point=as_vec3(entry["p"]),
                normal=as_vec3(entry["n"]),
                radius=float(entry["r"]),
                strength=float(entry["s"]),
                tool=_tool(entry.get("t", "draw")),
                symmetry=int(entry.get("y", 0)),
                cut=bool(entry.get("c", False)),
            )
            for entry in entries
        ]
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as problem:
        raise ValidationError(
            title=_("Diese Pinselzüge lassen sich nicht lesen."),
            field="strokes",
            detail=_(
                "Erwartet wird die Liste der Züge, wie *Formen* sie schreibt — gemalt, nicht "
                "getippt. Den Schritt neu malen oder das Feld leeren."
            ),
            value=text,
            constraint="unreadable",
        ) from problem
    return strokes


def _tool(value: object) -> SculptTool:
    """Ein Pinselwerkzeug aus dem Text — ein unbekanntes ist ein Lesefehler,
    kein Zug, der still nichts tut."""
    if value not in get_args(SculptTool):
        raise ValueError(f"unknown sculpt tool {value!r}")
    return cast(SculptTool, value)


# --- operation --------------------------------------------------------------------

#: Wie die Symmetrie der Operation auf die Bitmaske eines Strichs fällt.
SYMMETRY_BITS: Final[dict[str, int]] = {
    "none": 0,
    "x": 1,
    "y": 2,
    "z": 4,
    "xy": 3,
    "xz": 5,
    "yz": 6,
    "xyz": 7,
}

#: Ab wie vielen Etappen das Einbacken angeboten wird (Entscheidung D).
#: Jede Etappe ist ein eigener Durchgang über alle Eckpunkte; bei zwanzig
#: kostet jede Auswertung das Zwanzigfache eines einzelnen.
BAKE_STAGES: Final = 20

#: Und ab wie vielen Zügen, unabhängig von den Etappen. Zwanzigtausend sind
#: rund zwei Megabyte Zahlen — spätestens dort ist die Sitzung ein Datenblock
#: und keine Liste von Entscheidungen mehr.
BAKE_STROKES: Final = 20_000

#: Ab wie vielen mittleren Kantenlängen ein Pinsel noch etwas ausrichtet.
#: Darunter liegen im Pinselgebiet zu wenige Eckpunkte, um eine Form zu
#: tragen — es entsteht keine Falte, sondern eine verzogene Facette.
BRUSH_TO_EDGE: Final = 2.0


@op_params
class SculptParams(BaseParams):
    strokes: str = param(
        title=_("Striche"),
        kind="strokes",
        default="",
        placement="advanced",
        doc=_(
            "Die gesammelten Pinselzüge dieser Sitzung. Sie werden gemalt, nicht "
            "getippt — dieses Feld zeigt nur, was dabei entstanden ist."
        ),
    )
    baked: str = param(
        title=_("Eingebacken"),
        kind="source",
        default="",
        placement="advanced",
        doc=_(
            "Ein festgeschriebener Stand dieser Sitzung. Ist er gesetzt, kommt das "
            "Ergebnis von dort und nicht mehr aus den Zügen — die bleiben als Beleg "
            "stehen, wirken aber nicht mehr."
        ),
    )
    symmetry: str = param(
        title=_("Symmetrie"),
        default="none",
        choices=("none", "x", "y", "z", "xy", "xz", "yz", "xyz"),
        doc=_(
            "An welchen Ebenen jeder Strich zusätzlich gespiegelt wird. Nachträglich "
            "änderbar — eine fertige Sitzung lässt sich damit symmetrisch machen."
        ),
    )
    front_only: bool = param(
        title=_("Nur die zugewandte Seite formen"),
        default=True,
        placement="advanced",
        internal=True,
        doc=_("Ein Zug bewegt nur Punkte, die dem Pinsel zugewandt sind."),
    )
    mirror_once: bool = param(
        title=_("Spiegelzug auf der Ebene einmal"),
        default=True,
        placement="advanced",
        internal=True,
        doc=_("Ein Zug auf der Symmetrieebene wirkt einmal, nicht doppelt."),
    )
    mirror_at_body: bool = param(
        title=_("An der Körpermitte spiegeln"),
        default=True,
        placement="advanced",
        doc=_(
            "Die Symmetrieebenen gehen durch die Mitte des Körpers. Ohne Haken gehen "
            "sie durch den Nullpunkt der Szene, wie in älteren Projekten."
        ),
    )


@register_op(
    name="sculpt_strokes",
    result_kind="mesh",
    title=_("Formen"),
    category="mesh",
    params=SculptParams,
    consumes=1,
    produces=1,
    doc=_(
        "Trägt Material mit dem Pinsel auf und ab. Der ganze Vorgang ist ein Schritt "
        "im Verlauf und bleibt änderbar, so viele Züge er auch enthält."
    ),
    caveat=_(
        "Nicht an einem Teil, das noch bemaßt wird: Ein Strich sitzt an einer Stelle im "
        "Raum, und wer die Form darunter ändert, verschiebt die Fläche unter ihm weg. "
        "Erst konstruieren, dann formen."
    ),
)
def sculpt_strokes(ctx: OpContext) -> OpResult:
    """Eine ganze Sitzung als ein Schritt (Regel 2, seit P16.1)."""
    params = cast(SculptParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    strokes = strokes_from_text(params.strokes)

    if params.baked:
        # Entscheidung D: Der Stand ist festgeschrieben. Gerechnet wird nichts
        # mehr — das ist der Sinn der Sache, denn bei zwanzig Etappen kostet
        # jede Auswertung zwanzig Durchgänge. Reproduzierbar bleibt es
        # trotzdem: Die Quelle reist im Container mit wie jede andere, und was
        # aus ihr kommt, hängt an keinem Rechner und an keiner Sitzung.
        return _from_baked(ctx, source, before, strokes)

    extra = SYMMETRY_BITS.get(params.symmetry, 0)
    if extra:
        strokes = [replace(stroke, symmetry=stroke.symmetry | extra) for stroke in strokes]

    missed: list[Stroke] = []
    centre: Vec3 = (0.0, 0.0, 0.0)
    if params.mirror_at_body:
        middle = mirror_centre(before)
        centre = (float(middle[0]), float(middle[1]), float(middle[2]))
    after = apply_strokes(
        before,
        strokes,
        missed,
        cancelled=ctx.cancelled,
        centre=centre,
        front_only=params.front_only,
        mirror_once=params.mirror_once,
    )
    findings = _sculpting_findings(
        before, after, strokes, source.id, missed, ctx.profile, ctx.cancelled
    )
    return OpResult(outputs=[dataclasses.replace(source, mesh=after)], findings=findings)


def _from_baked(
    ctx: OpContext, source: Any, before: MeshData, strokes: Sequence[Stroke]
) -> OpResult:
    """Das eingebackene Netz statt der Rechnung.

    Der Verlust an Änderbarkeit steht als Befund da und nicht nur im Dialog,
    der ihn seinerzeit angekündigt hat: Wer eine Datei ein halbes Jahr später
    öffnet, war bei der Nachfrage nicht dabei.
    """
    params = cast(SculptParams, ctx.params)
    if ctx.sources is None:
        raise ValidationError(
            field="baked",
            detail=_(
                "Der eingebackene Stand lässt sich ohne die Quellen des Projekts nicht lesen."
            ),
            constraint="no_sources",
            suggestions=(CANCEL,),
        )
    payload = ctx.sources.read(params.baked)
    from app.core.ingest.loader import MAX_FILE_BYTES

    # Neue Etappen verwenden dieselbe verlustfreie Form wie der Mesh-Cache.
    # Alte Projekte mit eingebettetem STL bleiben weiterhin lesbar.
    mesh = (
        MeshData.from_bytes(payload, maximum_bytes=MAX_FILE_BYTES)
        if payload.startswith(b"PK\x03\x04")
        else read_mesh(payload, ".stl")
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh)],
        findings=[
            Finding(
                code="sculpt.baked",
                severity="info",
                message=_(
                    "Dieser Stand ist festgeschrieben — die Züge stehen als Beleg da, "
                    "geändert werden kann an ihnen nichts mehr."
                ),
                object_id=source.id,
                values={"strokes": len(strokes), "before": before.triangle_count},
            )
        ],
    )


#: Unter dieser Verschiebung gilt ein Eckpunkt als nicht bewegt: Rauschen der
#: doppelten Genauigkeit, keine Geometrie. Weit unter jeder Toleranz eines
#: Druckers und weit über dem, was ``warp`` an Rundung hinterlässt.
MOVED_EPSILON_MM: Final = 1e-9


def _sculpting_findings(
    before: MeshData,
    after: MeshData,
    strokes: Sequence[Stroke],
    object_id: str,
    missed: Sequence[Stroke],
    profile: Profile,
    cancelled: CancelToken | None = None,
) -> list[Finding]:
    """Was die Sitzung gekostet hat — und was ihr im Weg stand.

    Vier Dinge, die der Nutzer nicht sehen kann und wissen muss: ob überhaupt
    etwas geschehen ist, ob das Netz für seinen Pinsel fein genug war
    (Entscheidung E), wie viele Durchgänge seine Etappen kosten
    (Entscheidung C), und ob die Fläche sich dabei selbst durchdrungen hat —
    ``warp`` prüft das nicht (Entscheidung L).

    **Das erste ist am 31.08.2026 dazugekommen und war das teuerste.** Der
    Vorbehalt im Register warnt seit jeher: Ein Zug sitzt an einer Stelle im
    Raum, und wer die Form darunter verschiebt, zieht ihm die Fläche weg.
    Geprüft wurde es nicht — die Sitzung meldete auch dann „übertragen", wenn
    kein einziger Eckpunkt sich bewegt hatte. Gemessen am Schaustück des
    vierten Wegs, dessen drei Fingerrillen 18 mm über dem Körper lagen: null
    Abtrag, ein Schritt im Verlauf, und im Bericht die Erfolgsmeldung.
    """
    if not strokes:
        return [
            Finding(
                code="sculpt.empty",
                severity="info",
                message=_("Diese Formsitzung enthält noch keine Züge."),
                object_id=object_id,
            )
        ]

    parts = stages(strokes)

    # Getroffen ist nicht gewirkt: Der Muldenzug des Schaustücks griff 321 von
    # 5770 Eckpunkten und trug dabei 0,41 mm ab, bei eingestellter Stärke 5,0.
    # Gemessen wird deshalb die Verschiebung, und die Grenze kommt aus dem
    # Profil (Regel 7): Was unter einer Schichthöhe bleibt, zeigt der Druck
    # kaum. **Verändert ist der Körper trotzdem** — bis zum 05.09.2026 hieß
    # so eine Sitzung „hat den Körper nicht verändert", und eine
    # Z-Schichthöhe ist kein Maß für eine seitliche Kontur (Gesamtreview,
    # R39). ``warp`` lässt die Topologie stehen, die Punkte sind vergleichbar.
    shifted = np.linalg.norm(
        np.asarray(after.raw.vertices, dtype=float) - np.asarray(before.raw.vertices, dtype=float),
        axis=1,
    )
    moved = float(shifted.max()) if len(shifted) else 0.0
    layer = profile.printer.layer_height

    changed = moved > MOVED_EPSILON_MM
    findings = [
        Finding(
            code="sculpt.applied",
            severity="info",
            message=_("Die Züge dieser Sitzung wurden auf den Körper übertragen."),
            object_id=object_id,
            values={"strokes": len(strokes), "stages": len(parts), "moved_mm": round(moved, 3)},
        )
        if changed
        else Finding(
            code="sculpt.no_effect",
            severity="warning",
            message=_(
                "Diese Formsitzung hat den Körper nicht verändert — kein Zug hat einen Punkt "
                "der Fläche bewegt. Entweder liegen die Züge neben der Fläche, oder ihre "
                "Stärke ist für dieses Teil zu klein."
            ),
            object_id=object_id,
            values={"strokes": len(strokes), "stages": len(parts)},
        )
    ]
    if changed and moved < layer:
        findings.append(
            Finding(
                code="sculpt.subtle",
                severity="warning",
                message=_(
                    "Die größte Bewegung dieser Sitzung bleibt unter einer Schichthöhe. In "
                    "Druckrichtung entsteht so wenig kaum, seitlich entscheidet der Slicer "
                    "darüber. Wer mehr wollte: Entweder liegen die Züge neben der Fläche, "
                    "oder ihre Stärke ist für dieses Teil zu klein."
                ),
                object_id=object_id,
                values={
                    "strokes": len(strokes),
                    "stages": len(parts),
                    "moved_mm": round(moved, 3),
                    "layer_mm": round(layer, 3),
                },
            )
        )
    if missed:
        findings.append(
            Finding(
                code="sculpt.strokes_missed",
                severity="warning",
                message=_(
                    "Ein Teil der Züge hat den Körper nicht erreicht und trägt nichts ab. Ein "
                    "Zug bleibt an seiner Stelle im Raum — wer die Form darunter nachträglich "
                    "verschiebt, lässt ihn in der Luft stehen. Erst konstruieren, dann formen."
                ),
                object_id=object_id,
                values={"missed": len(missed), "strokes": len(strokes)},
            )
        )

    edge = float(np.median(np.asarray(before.raw.edges_unique_length, dtype=float)))
    finest = min(stroke.radius for stroke in strokes)
    if finest < edge * BRUSH_TO_EDGE:
        findings.append(
            Finding(
                code="sculpt.too_coarse",
                severity="warning",
                message=_(
                    "Der feinste Pinsel ist kleiner als die Dreiecke darunter — dort "
                    "entsteht keine Form, sondern eine verzogene Fläche. Erst gleichmäßig "
                    "vernetzen."
                ),
                object_id=object_id,
                values={"brush_mm": round(finest, 3), "edge_mm": round(edge, 3)},
            )
        )
    if len(parts) >= BAKE_STAGES or len(strokes) >= BAKE_STROKES:
        # Entscheidung D: angeboten, nie automatisch. Das Einbacken ist ein
        # bewusster Verlust an Änderbarkeit und damit die einzige Stelle in
        # diesem Konzept, an der eine Nachfrage richtig ist (Regel 19 greift
        # nicht, weil die Handlung nicht folgenlos rücknehmbar ist).
        findings.append(
            Finding(
                code="sculpt.consider_baking",
                severity="info",
                message=_(
                    "Diese Sitzung ist groß genug, dass jede Auswertung spürbar dauert. "
                    "Der Stand lässt sich festschreiben — danach sind die Züge nicht mehr "
                    "änderbar."
                ),
                object_id=object_id,
                values={"strokes": len(strokes), "stages": len(parts)},
            )
        )
    if not after.is_watertight and before.is_watertight:
        findings.append(
            Finding(
                code="sculpt.torn",
                severity="warning",
                message=_(
                    "Das Netz ist beim Formen aufgegangen. Reparieren, bevor es "
                    "mit Vereinigen oder Abziehen weitergeht."
                ),
                object_id=object_id,
            )
        )
    elif after.volume <= 0.0 < before.volume:
        findings.append(
            Finding(
                code="sculpt.inverted",
                severity="warning",
                message=_(
                    "Der Körper hat sich beim Formen umgestülpt — für diese Stärke ist "
                    "seine Wand zu dünn."
                ),
                object_id=object_id,
            )
        )
    if changed:
        findings.extend(_damage_findings(before, after, shifted, object_id, profile, cancelled))
    return findings


#: Wie viele der am tiefsten abgetragenen Eckpunkte die Wandprobe misst. Die
#: dünnste Stelle liegt dort, wo am meisten abgetragen wurde; jeden bewegten
#: Punkt zu messen kostete an einer feinen Figur Sekunden je Auswertung.
WALL_PROBES: Final = 256

#: Blockgröße für die Hüllquader der Dreiecke — begrenzt den Speicher an
#: Netzen mit Millionen Dreiecken.
_BOX_BLOCK: Final = 262_144


def _damage_findings(
    before: MeshData,
    after: MeshData,
    shifted: np.ndarray,
    object_id: str,
    profile: Profile,
    cancelled: CancelToken | None,
) -> list[Finding]:
    """Hat ein Zug die Wand durchstoßen oder unter die Mindestwand gedünnt?

    Gefunden in der Gebietsprüfung von Weg 4 (RM-364): Ein *Abtragen* an
    einer 4-mm-Platte drückte die Oberseite durch die Unterseite, ein
    flacherer ließ 0,44 mm Restwand — beide Male stand im Bericht nur
    „übertragen“, und der Export lief ohne Warnung. „Aufgerissen“ kann es
    nicht sehen, denn ``warp`` ändert die Topologie nicht.

    Geprüft wird nur um die bewegten Punkte, mit dem Rand, in dem ein
    Gegenüber dünner als die Mindestwand liegen kann. Gemeldet wird nur, was
    der Zug verursacht hat: mehr schneidende Paare mit einem bewegten
    Dreieck als vorher, eine Wand, die dünner wurde.
    """
    moved_points = shifted > MOVED_EPSILON_MM
    if not moved_points.any():
        return []
    minimum = profile.minimum_wall_thickness
    vertices = np.asarray(after.raw.vertices, dtype=float)
    earlier = np.asarray(before.raw.vertices, dtype=float)
    faces = np.asarray(after.raw.faces, dtype=np.int64)
    margin = 2.0 * minimum
    low = np.minimum(vertices[moved_points].min(axis=0), earlier[moved_points].min(axis=0))
    high = np.maximum(vertices[moved_points].max(axis=0), earlier[moved_points].max(axis=0))
    near = _faces_in_box(vertices, faces, low - margin, high + margin)
    if not len(near):
        return []
    local = faces[near]
    touched = moved_points[local].any(axis=1)

    pierced = _new_crossings(earlier, vertices, local, touched, cancelled)
    if pierced is not None:
        count, where = pierced
        return [
            Finding(
                code="sculpt.pierced",
                severity="warning",
                message=_(
                    "Ein Zug hat die Fläche durch die Wand dahinter gedrückt — der Körper "
                    "durchdringt sich dort selbst. So gedruckt bleibt die Stelle offen oder "
                    "doppelt. Den Zug schwächer setzen oder zurücknehmen."
                ),
                object_id=object_id,
                values={"triangles": count},
                location=where,
                suggestions=(SHOW_LOCATION,),
            )
        ]

    thinnest = _thinned_wall(before, after, local, minimum, cancelled)
    if thinnest is None:
        return []
    thickness, where = thinnest
    return [
        Finding(
            code="sculpt.thin_wall",
            severity="warning",
            message=_(
                "Ein Zug hat die Wand dünner gemacht, als dieses Material sicher druckt. "
                "Den Zug schwächer setzen oder an dieser Stelle Material auftragen."
            ),
            object_id=object_id,
            values={"thickness_mm": round(thickness, 2), "minimum_mm": round(minimum, 2)},
            location=where,
            suggestions=(SHOW_LOCATION,),
        )
    ]


def _faces_in_box(
    vertices: np.ndarray, faces: np.ndarray, low: np.ndarray, high: np.ndarray
) -> np.ndarray:
    """Die Dreiecke, deren Hüllquader den Quader ``low`` … ``high`` berührt."""
    kept: list[np.ndarray] = [np.zeros(0, dtype=np.int64)]
    for start in range(0, len(faces), _BOX_BLOCK):
        corners = vertices[faces[start : start + _BOX_BLOCK]]
        inside = np.all(corners.max(axis=1) >= low, axis=1) & np.all(
            corners.min(axis=1) <= high, axis=1
        )
        kept.append(np.flatnonzero(inside) + start)
    return np.concatenate(kept)


def _new_crossings(
    earlier: np.ndarray,
    vertices: np.ndarray,
    local: np.ndarray,
    touched: np.ndarray,
    cancelled: CancelToken | None,
) -> tuple[int, Vec3] | None:
    """Wie viele Dreiecke sich jetzt an einem bewegten schneiden, wenn es mehr
    schneidende Paare sind als vorher — und wo das erste liegt."""
    now = crossing_face_pairs(vertices, local, cancelled)
    hits = touched[now.first] | touched[now.second]
    if not hits.any():
        return None
    then = crossing_face_pairs(earlier, local, cancelled)
    if int(hits.sum()) <= int((touched[then.first] | touched[then.second]).sum()):
        return None
    crossing = np.unique(np.concatenate([now.first[hits], now.second[hits]]))
    face = int(now.first[np.flatnonzero(hits)[0]])
    centre = vertices[local[face]].mean(axis=0)
    return len(crossing), (float(centre[0]), float(centre[1]), float(centre[2]))


def _thinned_wall(
    before: MeshData,
    after: MeshData,
    local: np.ndarray,
    minimum: float,
    cancelled: CancelToken | None,
) -> tuple[float, Vec3] | None:
    """Die dünnste Wand unter den am tiefsten abgetragenen Punkten, wenn sie
    unter ``minimum`` liegt und der Zug sie dünner gemacht hat."""
    earlier = np.asarray(before.raw.vertices, dtype=float)
    vertices = np.asarray(after.raw.vertices, dtype=float)
    normals_then = np.asarray(before.raw.vertex_normals, dtype=float)
    # Abgetragen heißt: gegen die Normale von vorher bewegt.
    inward = -np.sum((vertices - earlier) * normals_then, axis=1)
    candidates = np.flatnonzero(inward > MOVED_EPSILON_MM)
    if not len(candidates):
        return None
    probes = candidates[np.argsort(-inward[candidates], kind="stable")[:WALL_PROBES]]
    normals_now = np.asarray(after.raw.vertex_normals, dtype=float)[probes]
    # Dieselben Schwellen wie die Wandstärke (``measure.ray_distances``): Das
    # Dreieck unter dem Startpunkt ist kein Gegenüber.
    now, _hit = ray_hits_batch(
        vertices[local],
        vertices[probes],
        -normals_now,
        edge_margin=EPS_GEOM,
        minimum_travel=EPS_GEOM * 100.0,
        cancelled=cancelled,
    )
    then, _hit = ray_hits_batch(
        earlier[local],
        earlier[probes],
        -normals_then[probes],
        edge_margin=EPS_GEOM,
        minimum_travel=EPS_GEOM * 100.0,
        cancelled=cancelled,
    )
    thinner = np.isfinite(now) & (now < minimum) & (now < then)
    if not thinner.any():
        return None
    index = int(np.flatnonzero(thinner)[np.argmin(now[thinner])])
    point = vertices[probes[index]]
    return float(now[index]), (float(point[0]), float(point[1]), float(point[2]))
