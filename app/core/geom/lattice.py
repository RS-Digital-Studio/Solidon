"""Gitterstrukturen als Füllung im Modell (Konzept P15 §7, Bauplan §25).

Der Slicer füllt mit Gitter, was er für innen hält. Er kennt weder die
Lastrichtung noch die Stelle, an der es dünn sein darf, und seine Füllung
existiert erst im G-Code — sie überlebt keinen Export, keine zweite Maschine
und keinen Slicerwechsel.

Eine Füllung im Modell ist echte Geometrie: sie reist im 3MF mit, sie steht im
Steckbrief als Zahl, und sie ist dieselbe, egal wer sie schneidet. Wer ein Teil
weitergibt, gibt die Füllung mit.

**Kein G-Code-Slicer** (§22.5). Das hier entsteht *vor* dem Slicer und ersetzt
ihn nicht: der Slicer legt weiterhin die Bahnen, er findet nur schon Material
vor, wo sonst sein eigenes Muster hingekommen wäre.

Der Gyroid wird als Isofläche seiner Gleichung gerechnet, Wabe und Würfelgitter
als Prismen — dieselbe Unterscheidung wie bei den Texturen: was eine geschlossene
Formel hat, bekommt sie, und was aus Flächen besteht, wird aus Flächen gebaut.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import replace
from typing import Final, cast

import numpy as np

from app.core import units
from app.core.deferred import trimesh
from app.core.errors import CORRECT_INPUT, ValidationError, require_positive
from app.core.geom.mesh import MeshData, concatenated
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import (
    BaseParams,
    CancelToken,
    Feature,
    FeatureId,
    Finding,
    OpContext,
    OpResult,
    Profile,
    Quality,
    Vec3,
)
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Die Strukturen, die es gibt — ein Auswahlwert, keine drei Menüeinträge (E11).
STRUCTURES: Final[tuple[str, ...]] = ("gyroid", "honeycomb", "cubic")

#: Wie fein das Gitter für den Gyroid abgetastet wird, je Zelle. Zehn Schritte
#: treffen die Fläche gut genug für einen Druck; darüber wächst nur die Datei.
SAMPLES_PER_CELL: Final = 10

#: Wie viele Abtastpunkte eine Achse höchstens bekommt. Ein großer Körper mit
#: feinen Zellen sprengt sonst den Speicher, bevor irgendetwas entsteht.
#:
#: **Eine Grenze, an der abgesagt wird, nicht abgeschnitten.** Bis zum
#: 22.09.2026 wurde die Zahl je Achse still auf diese Grenze gekappt, und der
#: Gyroid bekam damit weniger Stützstellen je Zelle, als er braucht: Ein Würfel
#: von 200 mm mit Zelle 5 wurde mit vier statt zehn abgetastet — 92 Sekunden,
#: 15,7 Millionen Dreiecke in 105 448 losen Stücken, nicht geschlossen.
#: :func:`_gyroid_samples` nennt jetzt die kleinste Zelle, die der Bereich trägt.
MAX_SAMPLES: Final = 160


def _gyroid_samples(size: np.ndarray, cell: float) -> np.ndarray:
    """Die Stützstellen je Achse — oder die Absage mit der Zelle, die noch geht.

    Zehn je Zelle (:data:`SAMPLES_PER_CELL`), mindestens vier je Achse. Wer mehr
    bräuchte, als :data:`MAX_SAMPLES` erlaubt, bekäme keinen Gyroid, sondern
    Bruchstücke; die Absage rechnet deshalb aus, ab welcher Zelle dieser
    Bereich abgetastet werden kann, und rundet auf den nächsten Zehntelmillimeter
    auf, damit der Vorschlag nicht die Zahl nennt, die er gerade ablehnt.
    """
    counts = np.asarray(np.maximum(np.ceil(size / cell * SAMPLES_PER_CELL).astype(int), 4))
    if int(counts.max()) <= MAX_SAMPLES:
        return counts
    reachable = math.ceil(float(size.max()) * SAMPLES_PER_CELL / MAX_SAMPLES * 10.0) / 10.0
    raise ValidationError(
        "cell",
        # Die kleinste mögliche Zelle steht in den Einzelheiten als „Erreichbar"
        # und nicht als Schlüssel im Satz (Durchsicht 0.5.0).
        _(
            "Für diesen Hohlraum ist die Zelle zu fein — der Gyroid ließe sich nicht mehr "
            "sauber abtasten."
        ),
        value=cell,
        constraint="gyroid_samples",
        values={"reachable_mm": reachable, "samples": int(counts.max()), "limit": MAX_SAMPLES},
        suggestions=[replace(CORRECT_INPUT, label=_("Zelle vergrößern"))],
    )


def _gyroid(
    box: tuple[Vec3, Vec3], cell: float, wall: float, cancelled: CancelToken | None = None
) -> MeshData | None:
    """Die Gyroid-Fläche, zu einer Wand aufgedickt.

    ``sin x·cos y + sin y·cos z + sin z·cos x = 0`` ist die Minimalfläche; was
    zwischen ``-t`` und ``+t`` liegt, ist die Wand darum. Sie teilt den Raum in
    zwei Hälften, die beide zusammenhängen — deshalb bleibt beim Drucken nichts
    eingeschlossen, und deshalb ist der Gyroid die Struktur, die Slicer für
    tragende Füllungen anbieten.
    """
    from skimage import measure

    low = np.asarray(box[0], dtype=float)
    high = np.asarray(box[1], dtype=float)
    size = high - low
    counts = _gyroid_samples(size, cell)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    axes = [np.linspace(low[axis], high[axis], counts[axis]) for axis in range(3)]
    grid = np.meshgrid(*axes, indexing="ij")
    scale = 2.0 * math.pi / cell
    x, y, z = (value * scale for value in grid)
    field = np.sin(x) * np.cos(y) + np.sin(y) * np.cos(z) + np.sin(z) * np.cos(x)

    # Die Wand ist der Bereich **zwischen** den beiden Isoflächen: alles, wo
    # der Betrag des Feldes unter der Schwelle liegt. Als ``|field| - level``
    # geschrieben ist ihre Oberfläche wieder eine einzige Isofläche bei null —
    # und damit ein geschlossenes Volumen.
    #
    # Der erste Versuch nahm die beiden Flächen bei ``+level`` und ``-level``
    # einzeln und legte sie zusammen. Das sind zwei offene Flächen, kein
    # Körper; die Boolesche Operation fiel auf die Voxelstufe zurück, und der
    # Kasten wurde von außen 40,18 statt 40 Millimeter groß.
    level = wall * scale / 2.0
    step = tuple(float(size[axis] / max(counts[axis] - 1, 1)) for axis in range(3))

    # **Der Rand muss zu sein.** Marching Cubes zeichnet nur, wo das Feld sein
    # Vorzeichen wechselt; am Rand des Abtastgitters endet die Fläche einfach,
    # und das Ergebnis ist offen. Ein offenes Netz fällt in der Booleschen
    # Rückfallkette bis auf die Voxelstufe durch, und die machte den Kasten von
    # außen 40,18 statt 40 Millimeter groß.
    #
    # Eine Lage „außen“ ringsherum schließt es: dort ist der Wert positiv, das
    # Vorzeichen wechselt, und die Fläche macht den Deckel selbst.
    walled = np.pad(np.abs(field) - level, 1, constant_values=abs(level) + 1.0)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    try:
        points, faces, _normals, _values = measure.marching_cubes(walled, 0.0, spacing=step)
    except ValueError, RuntimeError:
        return None
    # Die Polsterung verschiebt den Ursprung um einen Schritt je Achse zurück.
    origin = low - np.asarray(step, dtype=float)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    built = trimesh.Trimesh(vertices=points + origin, faces=faces, process=True)
    built.fix_normals()
    return MeshData.of(built)


def _honeycomb(
    box: tuple[Vec3, Vec3], cell: float, wall: float, cancelled: CancelToken | None = None
) -> MeshData | None:
    """Sechseckige Zellen, senkrecht durchgehend — die klassische Wabe.

    Sie trägt in der Ebene ihrer Zellen am besten und ist quer dazu weich; wer
    eine Platte aussteift, nimmt sie, wer einen Klotz füllt, den Gyroid.

    **Die Zellen teilen ihre Wände.** Das Raster setzt die Mitten eine Zelle
    auseinander, und genau dort schließen spitz stehende Sechsecke mit dem
    Umkreis ``Zelle/√3`` lückenlos aneinander. Jede Zelle bekommt die halbe
    Wand nach außen und die halbe nach innen; zwei Nachbarn ergeben zusammen
    eine Wand von ``wall``. Bis zum 22.09.2026 war der Umkreis die halbe Zelle,
    und zwischen den Nachbarn blieb ein Spalt von 0,13 Zellen — lauter lose
    Röhren statt einer Wabe (38 im Quader von 40 auf 40 bei Zelle 8).
    """
    from shapely.geometry import Polygon
    from shapely.geometry import box as shapely_box
    from shapely.ops import unary_union

    low = np.asarray(box[0], dtype=float)
    high = np.asarray(box[1], dtype=float)
    radius = cell / math.sqrt(3.0)
    step_y = cell * math.sqrt(3.0) / 2.0
    rings = []
    row = 0
    y = low[1] - cell
    while y <= high[1] + cell:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        offset = (cell / 2.0) if row % 2 else 0.0
        x = low[0] - cell + offset
        while x <= high[0] + cell:
            corners = [
                (
                    # Die (2i+1)-te Ecke eines Zwoelfecks ist genau
                    # ``pi/6 + i*pi/3`` — aus Ganzzahlen und damit auf jeder
                    # Maschine dieselbe Zahl (RM-187).
                    x + radius * units.circle_point(12, 2 * index + 1)[0],
                    y + radius * units.circle_point(12, 2 * index + 1)[1],
                )
                for index in range(6)
            ]
            hexagon = Polygon(corners)
            # Spitz statt rund an den Ecken: Die Wabe hat Knoten, keine Bögen.
            cellwall = hexagon.buffer(wall / 2.0, join_style="mitre").difference(
                hexagon.buffer(-wall / 2.0, join_style="mitre")
            )
            if not cellwall.is_empty and cellwall.area > 0.0:
                rings.append(cellwall)
            x += cell
        y += step_y
        row += 1
    if not rings:
        return None
    # Auf den Bereich beschneiden: gebaut wird eine Zelle über den Rand hinaus,
    # damit am Rand keine halbe Zelle fehlt — stehen bleiben darf sie nicht.
    # Ohne diesen Schnitt füllte die Wabe 133 % ihres eigenen Quaders, und eine
    # Füllung dichter als ein Vollkörper ist keine.
    field = shapely_box(float(low[0]), float(low[1]), float(high[0]), float(high[1]))
    joined = unary_union(rings).intersection(field)
    shapes = list(getattr(joined, "geoms", [joined]))
    height = float(high[2] - low[2])
    parts = [
        trimesh.creation.extrude_polygon(shape, height=height)
        for shape in shapes
        if shape.geom_type == "Polygon" and shape.area > 0.0
    ]
    if not parts:
        return None
    body = concatenated(parts)
    body.apply_translation((0.0, 0.0, float(low[2])))
    return MeshData.of(body)


def _cubic(
    box: tuple[Vec3, Vec3], cell: float, wall: float, cancelled: CancelToken | None = None
) -> MeshData | None:
    """Ein Würfelgitter aus Stäben entlang der drei Achsen.

    Die einfachste Struktur, und die einzige, die in allen drei Richtungen
    gleich trägt. Sie ist steifer als die Wabe und schwerer als der Gyroid.
    """
    low = np.asarray(box[0], dtype=float)
    high = np.asarray(box[1], dtype=float)
    size = high - low
    bars = []
    for axis in range(3):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        first, second = [other for other in range(3) if other != axis]
        # Bis an den Quader, nicht eine ganze Zelle darüber hinaus: eine
        # Stabmitte jenseits von ``high`` liegt außerhalb des Hohlraums, und wo
        # sie zugleich jenseits der Außenwand liegt, überlebt sie die Differenz
        # gegen den Körper und hängt frei neben dem Teil.
        for offset_a in np.arange(low[first], high[first] + EPS_GEOM, cell):
            for offset_b in np.arange(low[second], high[second] + EPS_GEOM, cell):
                extents = [wall, wall, wall]
                extents[axis] = float(size[axis])
                centre = [0.0, 0.0, 0.0]
                centre[axis] = float((low[axis] + high[axis]) / 2.0)
                centre[first] = float(offset_a)
                centre[second] = float(offset_b)
                bars.append(trimesh.creation.box(extents=extents).apply_translation(centre))
    if not bars:
        return None
    return MeshData.of(concatenated(bars))


def build(
    structure: str,
    box: tuple[Vec3, Vec3],
    cell: float,
    wall: float,
    *,
    cancelled: CancelToken | None = None,
) -> MeshData | None:
    """Die Füllung für einen Quader, mittig darin.

    Gibt ``None`` zurück, wenn nichts entsteht — bei einem Bereich, der kleiner
    ist als eine Zelle, ist das kein Fehler, sondern die Antwort.

    ``cancelled`` wird zwischen den Zellen gefragt (§15.6): Ein Würfelgitter
    aus 2 mm Zellen in einem 200er Quader sind hunderttausend Stäbe, und bis
    hierher lief das ohne einen Weg zurück.
    """
    if structure not in STRUCTURES:
        raise ValidationError(
            "structure",
            _("Diese Struktur gibt es nicht."),
            value=structure,
            constraint="known_structure",
        )
    require_positive("cell", cell)
    require_positive("wall", wall)
    if structure == "gyroid":
        return _gyroid(box, cell, wall, cancelled)
    if structure == "honeycomb":
        return _honeycomb(box, cell, wall, cancelled)
    return _cubic(box, cell, wall, cancelled)


def check_printable(wall: float, cell: float, profile: Profile) -> None:
    """Ob diese Füllung auf dieser Maschine entsteht (E1).

    Zwei Fragen, beide ohne Rechnung zu beantworten: ist der Steg breit genug,
    um gedruckt zu werden, und bleibt zwischen den Stegen noch ein Hohlraum.
    Eine Füllung, deren Stege so dick sind wie ihre Zellen, ist ein Vollkörper
    mit mehr Dreiecken.
    """
    minimum = profile.minimum_wall_thickness
    if wall < minimum:
        raise ValidationError(
            "wall",
            # Der Mindestwert steht in den Einzelheiten; „steht in
            # „minimum_mm"" verwies auf einen Schlüssel, den dort niemand liest
            # (Durchsicht 0.5.0, ``test_customer_texts_quote_no_internal_keys``).
            _("Diese Stege sind dünner als zwei Extrusionsbahnen und werden nicht gedruckt."),
            value=wall,
            constraint="minimum_wall",
            values={"minimum_mm": round(minimum, 2)},
            suggestions=[replace(CORRECT_INPUT, label=_("Stege verstärken"))],
        )
    if wall >= cell * 0.5:
        raise ValidationError(
            "cell",
            _(
                "Die Stege sind mindestens halb so dick wie ihre Zelle — daraus wird "
                "ein Vollkörper mit mehr Dreiecken statt einer Füllung."
            ),
            value=cell,
            constraint="cell_size",
            suggestions=[replace(CORRECT_INPUT, label=_("Zelle vergrößern"))],
        )


# --- die Operation (Bauplan §25, Kategorie „Oberfläche") -------------------------


@op_params
class LatticeParams(BaseParams):
    structure: str = param(
        title=_("Struktur"),
        default="gyroid",
        choices=STRUCTURES,
        doc=_(
            "Gyroid trägt in alle Richtungen und schließt nichts ein, die Wabe "
            "steift eine Platte aus, das Würfelgitter ist am steifsten und am "
            "schwersten."
        ),
    )
    cell: float = param(
        title=_("Zellgröße"),
        default=8.0,
        unit="mm",
        minimum=1.0,
        doc=_("Von Zelle zu Zelle. Kleiner heißt mehr Stege und mehr Material."),
    )
    wall: float = param(
        title=_("Stegstärke"),
        default=1.0,
        unit="mm",
        minimum=0.1,
        doc=_(
            "Wie dick die Stege werden. Unter zwei Extrusionsbahnen druckt sie "
            "die Maschine nicht — dann sagt die Operation es, statt es zu "
            "versuchen."
        ),
    )


#: Warum *Gitter füllen* ohne Hohlraum nichts tut — derselbe Satz im Menü
#: (``requires_body="cavity"``, ``labels.body_requirement``) wie beim Rechnen.
NO_CAVITY: Final = _(
    "Der Innenraum lässt sich nicht eindeutig bestimmen. Den Körper mit "
    "Aushöhlen vorbereiten oder ein Modell mit geschlossener Innenfläche wählen."
)


@register_op(
    name="lattice_fill",
    result_kind="mesh",
    # 2: Die Wabe teilt ihre Wände (``_honeycomb``); 3: interne Gitterwerkzeuge
    # umgehen die Vorprüfung überlappender Szenenteile (RM-319).
    cache_version="3",
    title=_("Gitter füllen"),
    category="surface",
    params=LatticeParams,
    consumes=1,
    produces=1,
    requires_body="cavity",
    doc=_(
        "Füllt den Hohlraum eines ausgehöhlten Körpers mit einer Gitterstruktur "
        "als echte Geometrie. Sie reist im 3MF mit und ist dieselbe, egal wer "
        "das Teil schneidet."
    ),
    caveat=_(
        "Nicht für Teile, die dicht sein müssen: Ein Gitter hat Hohlräume, und Wasser "
        "findet sie. Für tragende Teile erst die Wandstärke erhöhen — eine Füllung "
        "ersetzt keine Wand."
    ),
)
def lattice_fill(ctx: OpContext) -> OpResult:
    """Beschneidet die Füllung auf die belegte Innengeometrie des Körpers."""
    from app.core.geom.boolean import boolean, deepest
    from app.core.geom.mesh import as_mesh_data

    params = cast(LatticeParams, ctx.params)
    check_printable(params.wall, params.cell, ctx.profile)

    source = ctx.inputs[0]
    body = as_mesh_data(source.mesh)
    cavity, vented = _cavity_mesh(body, source.features, quality=ctx.quality)
    if cavity is None:
        raise ValidationError(
            "structure",
            NO_CAVITY,
            value=params.structure,
            constraint="no_cavity",
            suggestions=[replace(CORRECT_INPUT, label=_("Erst aushöhlen"))],
        )

    if ctx.progress is not None:
        ctx.progress(0.2, str(_("Gitter bauen")))
    grid = build(
        params.structure,
        (cavity.bounds.minimum, cavity.bounds.maximum),
        params.cell,
        params.wall,
        cancelled=ctx.cancelled,
    )
    if grid is None:
        raise ValidationError(
            "cell",
            _("Der Hohlraum ist kleiner als eine Zelle — daraus entsteht keine Füllung."),
            value=params.cell,
            constraint="cavity_too_small",
            suggestions=[replace(CORRECT_INPUT, label=_("Zelle verkleinern"))],
        )

    # Der Hüllquader dient nur dem Aufbau; erst der Schnitt mit dem echten
    # Innenraum verhindert außen angefügte Gitterstücke an runden oder konkaven Wänden.
    if ctx.progress is not None:
        ctx.progress(0.6, str(_("Gitter beschneiden")))
    # Der Innenraum zuerst: Er gehört zum Körper, das Gitter ist das
    # Werkzeug — und nur am ersten Eingang einer Schnittmenge fragt die Kette,
    # ob Teile ineinanderstecken (``boolean._parts_united_first``).
    inside = boolean(
        "intersection",
        [cavity, grid],
        quality=ctx.quality,
        allow_empty=True,
        cancelled=ctx.cancelled,
    )
    if inside.mesh.triangle_count == 0:
        raise ValidationError(
            "cell",
            _("Der Hohlraum ist kleiner als eine Zelle — daraus entsteht keine Füllung."),
            value=params.cell,
            constraint="cavity_too_small",
            suggestions=[replace(CORRECT_INPUT, label=_("Zelle verkleinern"))],
        )
    if ctx.progress is not None:
        ctx.progress(0.85, str(_("Gitter anfügen")))
    filled = boolean(
        "union",
        [body, inside.mesh],
        quality=ctx.quality,
        cancelled=ctx.cancelled,
        object_ids=(source.id, None),
    )

    _log.info("filled with %r, cell %.1f", params.structure, params.cell)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=filled.mesh, features={})],
        solver=deepest([inside.solver, filled.solver]),
        findings=[
            *inside.findings,
            *filled.findings,
            *([_cavity_from_vents(vented)] if vented else []),
            Finding(
                code="lattice.filled",
                severity="info",
                message=_("Der Hohlraum trägt jetzt eine Gitterstruktur."),
            ),
        ],
    )


def _cavity_from_vents(bores: tuple[str, ...]) -> Finding:
    """Der Befund zum geschätzten Innenraum — er nennt, worüber geschätzt wurde."""
    return Finding(
        code="lattice.cavity_from_vents",
        severity="info",
        message=_(
            "Der Innenraum ist über die Entlüftung bestimmt: {count} durchgehende "
            "Bohrungen wurden dafür probeweise geschlossen. Das Gitter sitzt in dem "
            "Raum, der danach eingeschlossen war.",
            count=len(bores),
        ),
        feature_ids=bores,
        values={"bores": len(bores)},
    )


def _cavity_mesh(
    body: MeshData,
    features: Mapping[FeatureId, Feature] | None = None,
    *,
    quality: Quality = "fine",
) -> tuple[MeshData | None, tuple[FeatureId, ...]]:
    """Der Innenraum und, wenn er geschätzt ist, die Bohrungen, über die es ging.

    Drei Wege, in dieser Reihenfolge. Die **belegte** Schnittgeometrie aus dem
    Aushöhlen ist die beste Auskunft: Dort weiß die Operation, was sie
    herausgenommen hat. Sonst die geschlossenen, nach innen gerichteten
    **Schalen** eines Körpers mit getrennter Innenfläche.

    **Und wenn beides fehlt, die Entlüftung** (RM-041): Ein ausgehöhlter
    Körper, der einmal als STL hinausging und wieder hereinkam, hat keine
    Schnittgeometrie mehr und **eine** Schale — Außen- und Innenfläche hängen
    über die Entlüftungsbohrung zusammen, und genau deshalb fand die Suche
    oben nichts. Werden die durchgehenden Bohrungen probeweise geschlossen,
    zerfällt die Oberfläche wieder in außen und innen, und was dann
    eingeschlossen ist, ist der Innenraum. Geschätzt ist daran die Annahme,
    dass diese Bohrungen Entlüftungen sind und kein Durchgang; deshalb sagt
    der Aufrufer es (:func:`_cavity_from_vents`), statt es zu verschweigen.
    Ohne erkannte Bohrungen bleibt es bei der Absage.
    """
    if body.cavity is not None:
        return body.cavity, ()
    found = _inner_shells(body)
    if found is not None:
        return found, ()
    bores = tuple(
        sorted(
            name
            for name, feature in (features or {}).items()
            if feature.kind == "hole" and feature.params.get("through")
        )
    )
    if not bores or bores_lead_outside(body, features or {}):
        return None, ()
    from app.core.geom.boolean import boolean

    plugs = [_bore_solid((features or {})[name]) for name in bores]
    closed = boolean("union", [body, *plugs], quality=quality, allow_empty=True)
    inner = _inner_shells(closed.mesh)
    return (inner, bores) if inner is not None else (None, ())


#: Wie weit ein Prüfstrahl hinter der Mündung einer Bohrung beginnt: jenseits
#: des Stopfens aus :func:`_bore_solid`, der ``2 · FEATURE_OVERLAP`` über das
#: Bohrungsende hinausreicht.
_MOUTH_STEP: Final = 3.0

#: Die Neigung der Nebenstrahlen gegen die Bohrungsachse. Der Achsstrahl allein
#: sperrte eine Bohrung, vor deren Mündung ein anderer Teil des Körpers steht;
#: schräg daneben ist der Blick ins Freie dann meist frei.
_SIDE_TILT: Final = math.radians(50.0)


def bores_lead_outside(body: MeshData, features: Mapping[FeatureId, Feature]) -> bool:
    """Ob jede durchgehende Bohrung an **beiden** Enden ins Freie führt.

    Die Frage hinter der Entlüftung (:func:`_cavity_mesh`): Eine Entlüftung
    führt aus dem Freien in den Innenraum, eine Bohrung durch eine Platte an
    beiden Enden ins Freie. Nur die erste kann einen Innenraum abschließen,
    wenn sie probeweise gestopft wird. Führen alle ins Freie, entsteht durch
    das Stopfen kein eingeschlossener Raum — die Boolesche Rechnung dafür
    kann entfallen, und das Menü kann *Gitter füllen* ehrlich sperren
    (``labels.body_facts``).

    Entschieden wird mit Strahlen aus jeder Mündung, nach außen gerichtet:
    Trifft einer weder den Körper noch den Stopfen einer **anderen** Bohrung,
    sieht die Mündung ins Unendliche und liegt damit im Freien. Die Stopfen
    zählen mit, weil die Operation beim Rechnen alle zugleich schließt — zwei
    Entlüftungen auf einer Achse sähen sonst durcheinander hindurch ins Freie.

    Jeder Zweifel sagt ``False``: ein offenes Netz (ein Strahl fände seine
    Lücke), eine Mündung, vor der überall Körper steht, eine Messung, die in
    Material beginnt. Dann rechnet die Operation wie bisher.
    """
    from app.core.geom.prepare import FEATURE_OVERLAP

    bores = [
        feature
        for feature in features.values()
        if feature.kind == "hole" and feature.params.get("through")
    ]
    if not bores or not body.raw.is_watertight:
        return False
    plugs = [_plug_axis(feature) for feature in bores]
    if any(plug is None for plug in plugs):
        return False
    sight = _Sight(
        np.asarray(body.raw.triangles, dtype=float),
        [plug for plug in plugs if plug is not None],
    )
    step = _MOUTH_STEP * FEATURE_OVERLAP
    for index, plug in enumerate(plugs):
        assert plug is not None
        centre, axis, half, _radius = plug
        for side in (1.0, -1.0):
            outward = axis * side
            start = centre + outward * (half + step)
            if not any(sight.open(start, ray, index) for ray in _mouth_rays(outward)):
                return False
    return True


#: Welcher Anteil der Dreiecke über den Streifen gesucht wird; die übrigen,
#: breitesten prüft jeder Strahl ganz.
_NARROW_SHARE: Final = 0.99

#: Auf wie viele Stellen eine Strahlrichtung für die geteilte Projektion
#: gerundet wird.
_KEY_DIGITS: Final = 9


@dataclasses.dataclass(frozen=True, slots=True)
class _Frame:
    """Die Dreiecke eines Körpers quer zu einer Strahlrichtung."""

    direction: np.ndarray
    first: np.ndarray
    second: np.ndarray
    low_u: np.ndarray
    high_u: np.ndarray
    low_v: np.ndarray
    high_v: np.ndarray
    far: np.ndarray
    order: np.ndarray
    middles: np.ndarray
    reach: float
    wide: np.ndarray


class _Sight:
    """Strahlen gegen einen Körper und die Stopfen seiner Bohrungen.

    Je Richtung werden die Dreiecke einmal in die Ebene quer zum Strahl
    projiziert und nach der Lage sortiert; ein Strahl prüft danach nur die
    Dreiecke eines schmalen Streifens um sich, und nur die, in deren Rechteck
    er liegt, rechnet er genau. Alle Achsstrahlen einer Platte teilen sich
    zwei Richtungen. Gemessen an einer Platte mit 64 Durchgangsbohrungen
    (22.09.2026): bei 16 652 Dreiecken 18 ms, bei 131 340 Dreiecken 100 bis
    140 ms — die erste Fassung mit einer Umkugel je Dreieck und Strahl
    brauchte 580 ms und 2,3 s.
    """

    def __init__(
        self,
        triangles: np.ndarray,
        plugs: list[tuple[np.ndarray, np.ndarray, float, float]],
    ) -> None:
        self._triangles = triangles
        self._frames: dict[tuple[float, ...], _Frame] = {}
        # Spielraum der Rechtecke: die Geometrietoleranz und was die gerundete
        # Richtung über die Ausdehnung des Körpers verschiebt.
        extent = float(np.abs(triangles).max()) if len(triangles) else 0.0
        self._pad = EPS_GEOM + 10.0 ** (1 - _KEY_DIGITS) * 4.0 * extent
        self._centres = np.array([plug[0] for plug in plugs], dtype=float).reshape(-1, 3)
        self._axes = np.array([plug[1] for plug in plugs], dtype=float).reshape(-1, 3)
        self._halves = np.array([plug[2] for plug in plugs], dtype=float)
        self._radii = np.array([plug[3] for plug in plugs], dtype=float)

    def open(self, start: np.ndarray, direction: np.ndarray, own: int) -> bool:
        """Ob der Strahl ins Freie geht — ohne Dreieck und ohne fremden Stopfen."""
        from app.core.geom.mesh import ray_hits

        frame = self._frame(direction)
        u = float(start @ frame.first)
        v = float(start @ frame.second)
        ahead = float(start @ frame.direction)
        pad = self._pad
        # Nur der Streifen, in dem ein schmales Dreieck den Strahl überhaupt
        # umfassen kann, dazu die breiten — dann die Rechtecke genau.
        lower, upper = np.searchsorted(
            frame.middles, (u - frame.reach - pad, u + frame.reach + pad)
        )
        candidates = np.concatenate((frame.order[lower:upper], frame.wide))
        near = candidates[
            (frame.low_u[candidates] <= u + pad)
            & (frame.high_u[candidates] >= u - pad)
            & (frame.low_v[candidates] <= v + pad)
            & (frame.high_v[candidates] >= v - pad)
            & (frame.far[candidates] >= ahead - pad)
        ]
        if len(near) and len(ray_hits(self._triangles[near], start, direction)[0]):
            return False
        touched = self._plugs_touched(start, direction)
        touched[own] = False
        return not bool(touched.any())

    def _frame(self, direction: np.ndarray) -> _Frame:
        """Die Rechtecke aller Dreiecke quer zu einer Richtung, einmal je Richtung."""
        # Gleiche Achsen tragen aus der Erkennung Rauschen in der letzten
        # Stelle; ohne Rundung bekäme jede Bohrung ihre eigene Projektion.
        # Was die Rundung verschiebt, deckt ``_pad``.
        key = tuple(round(float(value), _KEY_DIGITS) for value in direction)
        known = self._frames.get(key)
        if known is not None:
            return known
        rounded = np.asarray(key, dtype=float)
        rounded /= float(np.linalg.norm(rounded))
        axes = units.plane_axes(key)
        assert axes is not None, "Strahlrichtungen sind normiert"
        first, second = (np.asarray(axis, dtype=float) for axis in axes)
        u = self._triangles @ first
        v = self._triangles @ second
        low_u, high_u = u.min(axis=1), u.max(axis=1)
        middles = (low_u + high_u) / 2.0
        widths = (high_u - low_u) / 2.0
        # Die breitesten Dreiecke — die Deckfläche einer Platte ist eines —
        # prüft jeder Strahl; für die übrigen reicht ein Streifen um ihn.
        reach = float(np.quantile(widths, _NARROW_SHARE)) + EPS_GEOM if len(widths) else 0.0
        wide = np.flatnonzero(widths > reach)
        narrow = np.flatnonzero(widths <= reach)
        order = narrow[np.argsort(middles[narrow], kind="stable")]
        known = _Frame(
            direction=rounded,
            first=first,
            second=second,
            low_u=low_u,
            high_u=high_u,
            low_v=v.min(axis=1),
            high_v=v.max(axis=1),
            far=(self._triangles @ rounded).max(axis=1),
            order=order,
            middles=middles[order],
            reach=reach,
            wide=wide,
        )
        self._frames[key] = known
        return known

    def _plugs_touched(self, start: np.ndarray, direction: np.ndarray) -> np.ndarray:
        """Welche Stopfen der Strahl berührt — jeder als Kapsel gerechnet.

        Die Kapsel (Zylinder mit Halbkugeln an den Enden) ist etwas größer als
        der Stopfen; sie meldet im Zweifel eine Berührung, und die heißt hier
        „nicht im Freien" — die vorsichtige Seite. Gerechnet wird der nächste
        Abstand zwischen Strahl (``t ≥ 0``) und Achsstrecke (``|s| ≤ half``):
        erst über die beiden Geraden, dann abwechselnd geklemmt.
        """
        gap = start - self._centres
        cross = self._axes @ direction
        along_ray = gap @ direction
        along_axis = np.einsum("ij,ij->i", self._axes, gap)
        denominator = 1.0 - cross * cross
        skew = denominator > EPS_GEOM
        t = np.where(
            skew,
            (cross * along_axis - along_ray) / np.where(skew, denominator, 1.0),
            -along_ray,
        )
        t = np.maximum(t, 0.0)
        s = np.clip(along_axis + t * cross, -self._halves, self._halves)
        points = self._centres + s[:, None] * self._axes
        t = np.maximum(np.einsum("ij,j->i", points - start, direction), 0.0)
        s = np.clip(along_axis + t * cross, -self._halves, self._halves)
        points = self._centres + s[:, None] * self._axes
        closest = np.linalg.norm(start + t[:, None] * direction - points, axis=1)
        return np.asarray(closest <= self._radii)


def _plug_axis(feature: Feature) -> tuple[np.ndarray, np.ndarray, float, float] | None:
    """Mitte, Achse, halbe Länge und Halbmesser des Stopfens aus :func:`_bore_solid`."""
    from app.core.geom.prepare import FEATURE_OVERLAP

    axis = np.asarray(feature.params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
    length = float(np.linalg.norm(axis))
    depth = float(feature.params.get("depth", 0.0))
    diameter = float(feature.params.get("diameter", 0.0))
    if length <= EPS_GEOM or depth <= EPS_GEOM or diameter <= EPS_GEOM:
        return None
    centre = np.asarray(feature.params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
    half = depth / 2.0 + 2.0 * FEATURE_OVERLAP
    return centre, axis / length, half, (diameter + FEATURE_OVERLAP) / 2.0


def _mouth_rays(outward: np.ndarray) -> list[np.ndarray]:
    """Der Achsstrahl aus einer Mündung und sechs schräge daneben, alle nach außen."""
    frame = units.plane_axes((float(outward[0]), float(outward[1]), float(outward[2])))
    rays = [outward]
    if frame is None:
        return rays
    first, second = (np.asarray(axis, dtype=float) for axis in frame)
    for turn in range(6):
        angle = turn * math.pi / 3.0
        side = math.cos(angle) * first + math.sin(angle) * second
        rays.append(math.cos(_SIDE_TILT) * outward + math.sin(_SIDE_TILT) * side)
    return rays


def _inner_shells(body: MeshData) -> MeshData | None:
    """Die geschlossenen, nach innen gerichteten Schalen eines Körpers."""
    cavities: list[MeshData] = []
    for shell in body.raw.split(only_watertight=False):
        if shell.is_watertight and shell.volume < -EPS_GEOM:
            inner = shell.copy()
            inner.invert()
            cavities.append(MeshData.of(inner))
    return MeshData.of(concatenated([inner.raw for inner in cavities])) if cavities else None


def _bore_solid(feature: Feature) -> MeshData:
    """Der Zylinder, der diese Bohrung ausfüllt — beidseits über den Körper hinaus.

    Die Länge kommt nicht aus der gemessenen Tiefe: Sie endet an der Wand, und
    ein Stopfen, der dort endet, lässt eine Haut stehen. Und der Durchmesser
    bekommt die Zugabe aus ``prepare.FEATURE_OVERLAP``: Zwei zusammenfallende
    Zylinderflächen sind für eine Boolesche Rechnung kein Fall, den sie
    zuverlässig schließt — ohne Zugabe blieb die Bohrungswand als Spalt
    stehen, und die Oberfläche war danach immer noch eine (§39).
    """
    from app.core.geom.prepare import FEATURE_OVERLAP

    axis = np.asarray(feature.params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
    length = float(np.linalg.norm(axis))
    axis = axis / length if length > EPS_GEOM else np.array([0.0, 0.0, 1.0])
    centre = np.asarray(feature.params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
    diameter = float(feature.params.get("diameter", 0.0)) + FEATURE_OVERLAP
    depth = float(feature.params.get("depth", 0.0))
    # So lang wie die Bohrung, plus die Zugabe an beiden Enden: Ein Stopfen,
    # der weiter reicht, steht als Zapfen im Hohlraum und macht ihn kleiner,
    # als er ist (gemessen: 86 mm³ von 36 977 an der entlüfteten Dose).
    reach = depth + 4.0 * FEATURE_OVERLAP if depth > EPS_GEOM else diameter * 4.0
    plug = trimesh.creation.cylinder(radius=diameter / 2.0, height=reach, sections=48)
    matrix = np.eye(4)
    first, second = units.plane_axes((float(axis[0]), float(axis[1]), float(axis[2]))) or (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )
    matrix[:3, :3] = np.column_stack(
        (np.asarray(first, dtype=float), np.asarray(second, dtype=float), axis)
    )
    matrix[:3, 3] = centre
    plug.apply_transform(matrix)
    return MeshData.of(plug)
