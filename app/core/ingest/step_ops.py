"""Die ``load_step``-Operation: eine STEP-Datei als Baugruppe (Bauplan §17.1, §30, P7.4).

Laden ist eine Operation wie ``load`` und ``load_outline`` daneben, und sie
wohnt deshalb in der Eingangsstufe, nicht beim zweiten Kern: Sie liest mit
``brep.step``, rechnet aber mit den Werkzeugen der Eingangsstufe — der Lage
aufs Bett (``loader.bed_offset``), der Kopienummer (``plan.copy_name``) und
demselben Befund wie das Netz. Bis P7.4 stand sie in ``brep.ops``; die
Richtung der Kernpakete erlaubt ``ingest → brep``, nicht umgekehrt.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Final, cast

from app.core.brep import step
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, require
from app.core.errors import CANCEL, CORRECT_INPUT, InternalError, ValidationError
from app.core.ingest.loader import bed_offset
from app.core.log import get_logger
from app.core.registry import VARIABLE, op_params, param, register_op
from app.core.registry.params import WHOLE_FILE, body_keys
from app.core.types import (
    MAX_SLOTS,
    BaseParams,
    BoundingBox,
    CancelToken,
    Feature,
    Finding,
    MaterialSlot,
    OpContext,
    OpResult,
    SceneObject,
    Transform,
)
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)


def _object(name: str, solid: Solid, *, cancelled: CancelToken) -> SceneObject:
    """Ein exakter Körper als Szenenobjekt, mit seinen Merkmalen aus der Topologie."""
    return SceneObject(
        id="", name=name, mesh=solid, kind="brep", features=features_of(solid, cancelled=cancelled)
    )


@op_params
class LoadStepParams(BaseParams):
    source: str = param(
        title=_("Quelle"),
        kind="source",
        doc=_("Die eingebettete STEP-Datei im Projekt."),
    )
    bodies: str = param(
        title=_("Körper"),
        kind="step_bodies",
        default="",
        doc=_(
            "Welche Körper der Datei übernommen werden. Leer liest die Datei als einen "
            "Körper, wie in älteren Projekten."
        ),
    )
    name: str = param(
        title=_("Name"),
        default="",
        doc=_("Gilt für einen einzelnen Körper. Leer übernimmt den Namen aus der Datei."),
    )
    place_on_bed: bool = param(
        title=_("Auf das Bett setzen"),
        default=False,
        doc=_("Setzt das Modell mit seiner Unterseite auf das Druckbett."),
    )
    centre: bool = param(
        title=_("Mittig auf das Bett legen"),
        default=False,
        doc=_(
            "Schiebt das Modell in die Mitte der Druckplatte. Ein Modell aus einem "
            "CAD-Programm hat seinen Nullpunkt oft in einer Ecke und liegt sonst weit daneben."
        ),
    )
    copy: int = param(
        title=_("Kopie"),
        default=0,
        minimum=0,
        placement="advanced",
        doc=_(
            "Dieselbe Datei steht schon im Projekt. Ab 2 tragen alle Körper die Nummer "
            "in Klammern hinter ihrem Namen."
        ),
    )


@register_op(
    name="load_step",
    # Liest keinen Prozesswert (Beleg: ``_STEPS_WITHOUT_PROCESS`` in tests/test_cache.py).
    reads_process=False,
    title=_("STEP laden"),
    category="import",
    params=LoadStepParams,
    consumes=0,
    produces=VARIABLE,
    produces_from="bodies",
    doc=_(
        "Liest eine STEP-Datei mit einzeln bearbeitbaren Flächen und Kanten. Eine "
        "Baugruppe kommt als einzelne Körper mit Namen, Farben und Lage an. STEP trägt "
        "seine Einheit selbst — die Einheitenfrage entfällt."
    ),
)
def load_step(ctx: OpContext) -> OpResult:
    """Eine STEP-Datei: die gewählten Körper der Baugruppe, oder der Stand vor P7.4.

    ``bodies`` leer heißt: ein Körper über :func:`step.read`, wie jeder
    Ladeschritt, der vor der Baugruppenlesung gespeichert wurde — derselbe
    Schritt ergibt dasselbe Teil (§15.1). Sonst eine Liste von Kennungen aus
    :func:`step.read_assembly`: je Kennung ein Körper, in der Reihenfolge der
    Liste, mit Weltlage, Namen und Farben. ``*`` ist der gemeldete Rückfall,
    wenn die Datei sich nur als ein Körper lesen ließ.
    """
    params = cast(LoadStepParams, ctx.params)
    require()
    if ctx.sources is None:
        raise InternalError(
            detail="load_step was called without access to the project sources",
            values={"source": params.source},
        )

    source = ctx.sources.describe(params.source)
    if not step.is_step(Path(source.path).suffix):
        raise ValidationError(
            field="source",
            detail=_("Diese Datei ist keine STEP-Datei."),
            value=source.path,
            constraint="not_step",
        )
    payload = ctx.sources.read(params.source)
    stem = Path(source.path).stem
    keys = body_keys(params.bodies)
    if not keys:
        solid = step.read(payload)
        entry = _object(params.name or stem, solid, cancelled=ctx.cancelled)
        findings = [_loaded(solid.face_count, solid.edge_count), *_not_closed(solid)]
        return OpResult(outputs=[entry], findings=findings)
    if keys == (WHOLE_FILE,):
        return _whole_file(ctx, params, payload, stem)
    return _assembly(ctx, params, payload, stem, keys)


def _loaded(faces: int, edges: int) -> Finding:
    return Finding(
        code="brep.loaded",
        severity="info",
        message=_("Flächen und Kanten lassen sich einzeln weiterbearbeiten."),
        values={"faces": faces, "edges": edges},
    )


def _not_closed(solid: Solid, name: str = "") -> list[Finding]:
    """Die Auskunft über eine offene Schale am Einzelkörper — dieselbe wie beim Netz.

    **Dieselbe Auskunft wie beim Netz** (``ingest.not_watertight``): Eine
    offene Fläche aus STEP hat kein Volumen, das ein Slicer füllen könnte, und
    „Reparieren" schließt sie am Netz. Bis zum 22.09.2026 kam eine offene
    Schale hier ohne Wort an — mit einem „Volumen" aus der offenen Hülle
    (833 mm³ für fünf Seiten eines 10er-Würfels) und einem ``is_closed``, das
    immer Ja sagte. Die Baugruppe sagt es je offenem Körper mit seinem Namen —
    ein Befund für dieselbe Lage, nicht zwei (beim Zusammenführen stand dort
    ein eigener Code ``step.open_surfaces`` mit anderem Rat).
    """
    if solid.is_closed:
        return []
    values: dict[str, float | str] = {"open_edges": step.open_edge_count(solid)}
    if name:
        values["name"] = name
    return [
        Finding(
            code="ingest.not_watertight",
            severity="warning",
            # Derselbe Satz wie beim Netzimport (``loader``): Die Handlung
            # steht im Knopf daneben, nicht im Satz.
            message=_("Das Modell ist nicht geschlossen."),
            values=values,
        )
    ]


def _named_copy(name: str, params: LoadStepParams, single: bool) -> str:
    """Der eigene Name eines einzelnen Körpers, die Kopienummer für alle (``ingest.plan``)."""
    if params.name and single:
        return params.name
    if params.copy >= 2:
        from app.core.ingest.plan import copy_name

        return copy_name(name, params.copy)
    return name


def _whole_file(ctx: OpContext, params: LoadStepParams, payload: bytes, stem: str) -> OpResult:
    """Der gemeldete Rückfall: ein Körper über den bisherigen Leser (Konzept §13.9).

    Die Baugruppenlesung hat die Datei beim Einlesen nicht auflösen können;
    der Plan hat deshalb ``*`` gewählt, und dabei bleibt es bei jedem Öffnen —
    ein zweiter Versuch mit XCAF gäbe womöglich eine andere Zahl von Körpern,
    und die Kennungen stehen fest, bevor gerechnet wird (§11).
    """
    from OCP.TopLoc import TopLoc_Location

    solid = step.read(payload)
    findings = [_loaded(solid.face_count, solid.edge_count), _metadata_lost(), *_not_closed(solid)]
    placed = _bed_offset(step.shape_bounds(solid.shape), params, several=False)
    if placed is not None:
        solid = Solid(solid.shape.Moved(TopLoc_Location(placed[0])))
        findings.append(placed[1])
    name = _named_copy(stem, params, single=True)
    return OpResult(outputs=[_object(name, solid, cancelled=ctx.cancelled)], findings=findings)


def _metadata_lost() -> Finding:
    """Namen, Farben und Einzelkörper gingen verloren — und das wird gesagt."""
    return Finding(
        code="step.metadata_lost",
        severity="warning",
        message=_(
            "Namen, Farben und Einzelkörper dieser STEP-Datei ließen sich nicht lesen; sie "
            "kam als ein Körper. Im CAD-Programm neu als STEP gespeichert kommt die "
            "Baugruppe meist mit."
        ),
    )


def _assembly(
    ctx: OpContext, params: LoadStepParams, payload: bytes, stem: str, keys: tuple[str, ...]
) -> OpResult:
    """Die gewählten Körper einer STEP-Baugruppe als unabhängige Szenenkörper."""
    from OCP.TopLoc import TopLoc_Location

    def reading(fraction: float, text: str) -> None:
        ctx.progress(0.3 * fraction, text)

    assembly = step.read_assembly(payload, stem, cancelled=ctx.cancelled, progress=reading)
    by_key = {body.key: body for body in assembly.bodies}
    missing = [key for key in keys if key not in by_key]
    if missing:
        raise ValidationError(
            suggestions=(CORRECT_INPUT, CANCEL),
            field="bodies",
            detail=_(
                "Die Datei enthält nicht mehr alle gewählten Körper. Wählen Sie die Körper "
                "in diesem Schritt neu."
            ),
            constraint="unknown_body",
            values={"missing": len(missing)},
        )
    chosen = [by_key[key] for key in keys]
    findings: list[Finding] = []
    placed = _bed_offset(_group_bounds(chosen), params, several=len(chosen) > 1)
    offset = placed[0] if placed is not None else None
    if placed is not None:
        findings.append(placed[1])
    # Farben sind eine Aussage der Datei erst, wenn sie mehr als eine kennt —
    # dieselbe Regel wie bei der 3MF (``threemf._groups_of``): Die eine Farbe,
    # in der ein CAD-Programm alles zeigt, hat niemand als Filament gewählt.
    colourful = len(assembly.colours) >= 2
    outputs: list[SceneObject] = []
    references: dict[tuple[str, bool], tuple[Any, Solid, dict[str, Feature]]] = {}
    carried = 0
    for index, body in enumerate(chosen):
        ctx.cancelled.raise_if_cancelled()
        ctx.progress(0.3 + 0.7 * index / len(chosen), str(_("STEP laden")))
        shape = body.shape if offset is None else body.shape.Moved(TopLoc_Location(offset))
        slots, materials, dropped = _filaments(body, colourful)
        solid = Solid(shape, face_slots=slots)
        placement = _composed(offset, body.placement)
        reference = references.get((body.geometry, body.mirrored))
        features = (
            _carried_features(reference, solid, placement, cancelled=ctx.cancelled)
            if reference is not None
            else None
        )
        if features is None:
            features = features_of(solid, cancelled=ctx.cancelled)
            references.setdefault((body.geometry, body.mirrored), (placement, solid, features))
        else:
            carried += 1
        name = _named_copy(body.name, params, single=len(chosen) == 1)
        outputs.append(
            SceneObject(
                id="",
                name=name,
                mesh=solid,
                kind="brep",
                features=features,
                material_slots=materials,
            )
        )
        if dropped:
            findings.append(_colours_merged(name, dropped))
        if not body.solid:
            findings.extend(_not_closed(solid, name))
    if carried:
        _log.info("carried the features of %d STEP instance(s) from their first twin", carried)
    findings.insert(
        0,
        _loaded(
            sum(entry.mesh.face_count for entry in outputs if isinstance(entry.mesh, Solid)),
            sum(entry.mesh.edge_count for entry in outputs if isinstance(entry.mesh, Solid)),
        ),
    )
    findings.extend(_assembly_findings(assembly, chosen, stem))
    return OpResult(outputs=outputs, findings=findings)


def _assembly_findings(
    assembly: step.StepAssembly, chosen: list[step.StepBody], stem: str
) -> list[Finding]:
    """Was der Kunde über die eingelesene Baugruppe wissen soll — kurz."""
    findings: list[Finding] = []
    if len(chosen) > 1:
        findings.append(
            Finding(
                code="load.assembly",
                severity="info",
                message=_("Die Datei enthält mehrere Körper — sie kommen als eigene Objekte an."),
                values={"parts": len(chosen), "file": stem},
            )
        )
    if len(chosen) < len(assembly.bodies):
        findings.append(
            Finding(
                code="step.partial",
                severity="info",
                message=_(
                    "Übernommen sind {kept} von {bodies} Körpern der Datei. Die übrigen wählen "
                    "Sie über „Diesen Schritt ändern“ dazu.",
                    kept=len(chosen),
                    bodies=len(assembly.bodies),
                ),
                values={"kept": len(chosen), "bodies": len(assembly.bodies)},
            )
        )
    if not assembly.millimetres:
        findings.append(
            Finding(
                code="ingest.declared_unit",
                severity="info",
                message=_("Die Datei nennt ihre Einheit selbst; sie wurde umgerechnet."),
                values={"unit": assembly.unit},
            )
        )
    mirrored = sum(1 for body in chosen if body.mirrored)
    if mirrored:
        findings.append(
            Finding(
                code="step.mirrored",
                severity="info",
                message=_(
                    "{count} Körper sind in der Datei gespiegelt eingesetzt und kamen als "
                    "Spiegelbild ihres Teils.",
                    count=mirrored,
                ),
                values={"count": mirrored},
            )
        )
    unnamed = sum(1 for body in chosen if not body.named)
    if unnamed and len(chosen) > 1:
        findings.append(
            Finding(
                code="step.unnamed",
                severity="info",
                message=_(
                    "{count} Körper haben in der Datei keinen Namen; sie sind durchnummeriert.",
                    count=unnamed,
                ),
                values={"count": unnamed},
            )
        )
    if assembly.skipped:
        findings.append(
            Finding(
                code="step.skipped",
                severity="info",
                message=_(
                    "{count} Teile der Datei enthalten nur Kanten oder Punkte und wurden "
                    "nicht übernommen.",
                    count=assembly.skipped,
                ),
                values={"count": assembly.skipped},
            )
        )
    return findings


def _group_bounds(
    bodies: list[step.StepBody],
) -> tuple[float, float, float, float, float, float]:
    """Die genauen gemeinsamen Grenzen der gewählten Körper — gemessen nur, wo nötig.

    Jeder Körper trägt einen Quader, der ihn sicher enthält (``StepBody.box``,
    genau bei einer reinen Verschiebung). Für jede der sechs Seiten werden die
    Körper nach diesem Quader sortiert und genau gemessen, bis kein weiterer
    Quader mehr über das bisher genau gemessene Äußerste hinausreicht — dann
    kann es kein Körper mehr. An 200 gerundeten Instanzen kostete das Messen
    jedes Körpers 2 s im Ladeschritt; so misst er eine Handvoll.
    """
    measured: dict[int, tuple[float, float, float, float, float, float]] = {}

    def exact(index: int) -> tuple[float, float, float, float, float, float]:
        known = measured.get(index)
        if known is None:
            known = bodies[index].bounds()
            measured[index] = known
        return known

    loose = [body.box if body.box is not None else exact(n) for n, body in enumerate(bodies)]
    result: list[float] = []
    for side in range(6):
        lower = side < 3
        order = sorted(range(len(bodies)), key=lambda n: loose[n][side] * (1 if lower else -1))
        best: float | None = None
        for index in order:
            reach = loose[index][side]
            if best is not None and (reach >= best if lower else reach <= best):
                break
            value = exact(index)[side]
            best = value if best is None else (min(best, value) if lower else max(best, value))
        result.append(best if best is not None else 0.0)
    return (result[0], result[1], result[2], result[3], result[4], result[5])


def _bed_offset(
    bounds: tuple[float, float, float, float, float, float],
    params: LoadStepParams,
    *,
    several: bool,
) -> tuple[Any, Finding] | None:
    """Der gemeinsame Versatz aufs Bett und in seine Mitte — und sein Befund.

    Dieselbe Regel wie beim Netz (``ingest.ops._group_on_bed``, §17.1 Schritt
    6): Eine Baugruppe geht als Ganzes, die Teile behalten ihre Lage
    zueinander. Verschoben wird über eine Lage an der Form, nicht über Dreiecke
    — der Körper bleibt exakt.
    """
    if not (params.place_on_bed or params.centre):
        return None
    from OCP.gp import gp_Trsf, gp_Vec

    from app.core.ingest.ops import group_on_bed_finding

    group = BoundingBox(bounds[:3], bounds[3:])
    offset = bed_offset(group, place_on_bed=params.place_on_bed, centre=params.centre)
    if all(abs(value) <= EPS_GEOM for value in offset):
        return None
    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(*offset))
    return trsf, group_on_bed_finding(
        offset, place_on_bed=params.place_on_bed, centre=params.centre, several=several
    )


def _composed(offset: Any, placement: Any) -> Any:
    """Die Weltlage nach dem Versatz — ``None`` für die Identität."""
    if offset is None:
        return placement
    if placement is None:
        return offset
    return offset.Multiplied(placement)


def _filaments(
    body: step.StepBody, colourful: bool
) -> tuple[tuple[int, ...], list[MaterialSlot], int]:
    """Aus Flächenfarben werden Filamentslots (§20) — so wie beim 3MF-Import.

    Jede Farbe des Körpers bekommt einen Slot, in der Reihenfolge ihres ersten
    Auftretens. Flächen ohne Farbe bleiben am neutralen Slot null (ohne
    Eintrag, wie nach *Filament entfernen*); dann zählen die Farben ab eins.
    Mehr als acht Slots hat kein Körper (``MAX_SLOTS``): Die Farben mit den
    meisten Flächen bleiben, die übrigen Flächen gehen an den neutralen Slot,
    und der dritte Wert sagt, wie viele Farben das waren.
    """
    if not colourful or not body.colours:
        return (), [], 0
    counts: dict[str, int] = {}
    for colour in body.face_colours:
        if colour is not None:
            counts[colour] = counts.get(colour, 0) + 1
    order = list(body.colours)
    neutral = any(colour is None for colour in body.face_colours)
    room = MAX_SLOTS - (1 if neutral else 0)
    dropped = 0
    if len(order) > room:
        neutral = True
        room = MAX_SLOTS - 1
        ranked = sorted(order, key=lambda colour: (-counts[colour], order.index(colour)))
        kept = set(ranked[:room])
        dropped = len(order) - room
        order = [colour for colour in order if colour in kept]
    start = 1 if neutral else 0
    numbers = {colour: start + position for position, colour in enumerate(order)}
    slots = tuple(numbers.get(colour, 0) if colour else 0 for colour in body.face_colours)
    materials = [
        MaterialSlot(
            index=number,
            name=_("Slot {number}", number=number),
            colour=_rgb(colour),
        )
        for colour, number in numbers.items()
    ]
    return slots, materials, dropped


def _rgb(colour: str) -> tuple[float, float, float]:
    """``#rrggbb`` als Werte zwischen null und eins."""
    value = colour.lstrip("#")
    return (
        int(value[0:2], 16) / 255.0,
        int(value[2:4], 16) / 255.0,
        int(value[4:6], 16) / 255.0,
    )


def _colours_merged(name: str, dropped: int) -> Finding:
    return Finding(
        code="step.colours_merged",
        severity="warning",
        message=_(
            "„{name}“ hat mehr Farben, als ein Körper Filamente trägt. {count} seltene Farben "
            "kamen ohne Filament; „Filament auf eine Fläche“ weist sie zu.",
            name=name,
            count=dropped,
        ),
        values={"name": name, "count": dropped},
    )


#: Maßquellen, die allein an der exakten Form hängen (``Feature.measure_sources``).
#: Nur solche Merkmale folgen einer anderen Instanz über die Lage; was an den
#: Dreiecken gemessen oder eingepasst ist, hängt an der Vernetzung der Instanz.
_FORM_SOURCES: Final = frozenset({"native", "parameter"})


def _carried_features(
    reference: tuple[Any, Solid, dict[str, Feature]],
    solid: Solid,
    placement: Any,
    *,
    cancelled: CancelToken,
) -> dict[str, Feature] | None:
    """Die Merkmale einer weiteren Instanz desselben Teils — übertragen, nicht neu gesucht.

    Eine Baugruppe setzt dasselbe Teil oft vielfach ein; jeder Körper suchte
    seine Merkmale von vorn, gemessen 115 bis 140 ms je Körper an einem
    gerundeten Quader mit Bohrung — an tausend Instanzen über zwei Minuten
    für eine Antwort, die bis auf die Lage schon dastand.

    **Der Beleg ist die Form, nicht das Netz.** Beide Instanzen setzen
    dasselbe Teil ein (``StepBody.geometry``, dieselbe ``TShape`` aus XCAF),
    die Lage zwischen ihnen ist starr, und beide tragen dieselbe Zahl nativer
    Flächen. Übertragen wird nur, was allein an der exakten Form hängt: jedes
    Merkmal aus ganzen nativen Flächen, jedes Maß aus der Form
    (:data:`_FORM_SOURCES`). Dann folgen die Maße der Lage über
    ``transformed_features`` — dieselbe Rechnung wie beim Verschieben
    (``geom.transform.moved_object``) —, und die Dreiecke eines Merkmals sind
    die Dreiecke **seiner nativen Flächen in der Vernetzung der Instanz**,
    wie ``moved_object`` sie über die Flächenzuordnung bestimmt.

    Über die Dreiecke zu gehen reichte nicht: ``BRepMesh`` trianguliert
    dieselbe ebene Fläche an anderer Lage anders — gemessen am Deckel eines
    Zylinders, um 12 mm verschoben: dieselben Ecken, andere Diagonalen. Fehlt
    ein Beleg, wird gesucht.
    """
    import numpy as np

    from app.core.brep.kernel import face_sources
    from app.core.geom.transform import is_rigid
    from app.core.perceive.matching import transformed_features

    first_placement, first, known = reference
    relative = _relative(first_placement, placement)
    if not is_rigid(np.asarray(relative, dtype=float)):
        return None
    if first.face_count != solid.face_count:
        return None
    for feature in known.values():
        if any(source not in _FORM_SOURCES for source in feature.measure_sources.values()):
            return None
    before = face_sources(first.mesh)
    after = face_sources(solid.mesh)
    if len(before) != first.mesh.triangle_count or len(after) != solid.mesh.triangle_count:
        return None
    before_by_face = _triangles_by_native_face(before)
    after_by_face = _triangles_by_native_face(after)
    if set(before_by_face) != set(after_by_face):
        return None

    def renumbered(indices: tuple[int, ...]) -> tuple[int, ...] | None:
        faces = {int(before[index]) for index in indices}
        complete = {int(index) for face in faces for index in before_by_face[face]}
        if complete != set(indices):
            return None
        return tuple(sorted(int(index) for face in faces for index in after_by_face[face]))

    # Erst die Dreiecke der Instanz, dann die Lage: ``transformed_features``
    # misst Hohlraumhüllen am übergebenen Netz, also an dessen Nummerierung.
    renumbered_features: dict[str, Feature] = {}
    for name, feature in known.items():
        indices = renumbered(feature.face_indices)
        patches = [(patch, renumbered(patch.face_indices)) for patch in feature.surface_patches]
        if indices is None or any(moved is None for _patch, moved in patches):
            return None
        renumbered_features[name] = dataclasses.replace(
            feature,
            face_indices=indices,
            surface_patches=tuple(
                dataclasses.replace(patch, face_indices=moved)
                for patch, moved in patches
                if moved is not None
            ),
        )
    cancelled.raise_if_cancelled()
    result = transformed_features(
        renumbered_features,
        relative,
        mesh=solid.mesh,
        check_cancelled=cancelled.raise_if_cancelled,
    )
    if set(result.exact) != set(known):
        return None
    return dict(result.candidates)


def _triangles_by_native_face(sources: Any) -> dict[int, Any]:
    """Die Dreiecksnummern je nativer Fläche einer Tessellation."""
    import numpy as np

    order = np.argsort(sources, kind="stable")
    faces, starts = np.unique(sources[order], return_index=True)
    return {
        int(face): order[start:end]
        for face, start, end in zip(faces, starts, [*starts[1:], len(order)], strict=True)
    }


def _relative(first: Any, second: Any) -> Transform:
    """Die Lage, die die erste Instanz auf die zweite bringt, als 4x4-Matrix.

    Über ``gp_Trsf`` gerechnet, nicht über eine Matrixinverse: Die Umkehrung
    einer starren Lage ist analytisch (``Inverted``), ohne LAPACK (kern.md,
    RM-187).
    """
    from OCP.gp import gp_Trsf

    base = first if first is not None else gp_Trsf()
    target = second if second is not None else gp_Trsf()
    relative = target.Multiplied(base.Inverted())
    return (
        (relative.Value(1, 1), relative.Value(1, 2), relative.Value(1, 3), relative.Value(1, 4)),
        (relative.Value(2, 1), relative.Value(2, 2), relative.Value(2, 3), relative.Value(2, 4)),
        (relative.Value(3, 1), relative.Value(3, 2), relative.Value(3, 3), relative.Value(3, 4)),
        (0.0, 0.0, 0.0, 1.0),
    )
