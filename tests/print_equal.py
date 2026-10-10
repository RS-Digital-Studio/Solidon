"""Druckgleich: zwei Stände eines Ergebnisses gegeneinander halten (Bauplan §11.2).

Wer eine Beschleunigung oder Speicherersparnis nachweist, hält das Ergebnis
nach der Änderung gegen das davor. **Druckgleich** heißt: diskret gleich (Körper
und ihre Folge, Slots, Merkmale mit Art und Kennung, Befunde, Fragen an den
Nutzer, Rückfallstufe, dicht nach dem Verschweißen wie im Slicer), Maße und
Positionen höchstens um ``PRINT_LIMIT`` verschoben, kein Netz schlechter, und
Export und Wiedereinlesen in STL, 3MF, OBJ und STEP inhaltlich gleich. Dieser
eine Vergleich gilt für jedes Paket, damit nicht jedes seinen eigenen baut.

**Verglichen werden Abbilder, nicht lebende Objekte.** :func:`shot` nimmt ein
Ergebnis als reine Zahlen und Texte auf (:class:`ResultShot`), :func:`save`
legt es ab, :func:`load` liest es wieder. So lässt sich ein Stand in einem Baum
aufnehmen und in einem anderen vergleichen — zwei Codestände laufen nie im
selben Prozess. Darum importiert dieses Modul ``app`` erst in den Funktionen:
Der Baum, der gerade auf ``sys.path`` vorn steht, rechnet
(``tools/check_print_equal.py``).

**Was als Abweichung zählt, ist eine Länge.** Jede Zahl wird in die
Verschiebung umgerechnet, die sie am Druck bedeutet: Längen und Positionen
direkt, eine Richtung oder ein Winkel über den Hebel der Körperdiagonale, eine
Fläche über den kleinsten Umfang, der sie umschließt, ein Volumen über die
kleinste Oberfläche. Die größte davon steht im Urteil (:attr:`Verdict.largest`)
und wird gegen ``PRINT_LIMIT`` gehalten. Dreiecksfolge und Dreieckszahl dürfen
sich ändern: Die Netzabweichung misst den Abstand der Flächen in beide
Richtungen, nicht Dreieck gegen Dreieck. Nur wenn beide Stände dieselbe
Dreiecksliste tragen, sind Dreiecksnummern an Merkmalen und Slots diskret.

Was nicht verglichen wird: der Wortlaut von Befunden (seine Zahlen stehen in
``values`` und werden dort verglichen; die letzte Anzeigestelle darf wandern)
und die Ziffern in Fragen an den Nutzer.
"""

from __future__ import annotations

import dataclasses
import io
import json
import math
import re
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import numpy as np

#: Die Netz- und CAD-Formate der Rundreise (§11.2). STEP nur für exakte Körper.
ROUND_TRIP_FORMATS: Final = ("stl", "3mf", "obj", "step")

#: Richtungen in Merkmalen und Befunden: Ihre Abweichung wirkt über den Hebel
#: der Körperdiagonale.
DIRECTIONS: Final = frozenset(
    {"axis", "normal", "direction", "opening_normal", "profile_clamp_y", "carrier_axis"}
)
#: Winkel in Grad (``features._cone``: ``angle`` ist der volle Öffnungswinkel).
DEGREES: Final = frozenset({"angle"})
#: Winkel im Bogenmaß.
RADIANS: Final = frozenset({"half_angle", "taper"})
#: Verhältnisse ohne Einheit; wirken wie ein Maßstab auf die Körperdiagonale.
RATIOS: Final = frozenset({"coverage", "scale", "ratio", "share", "fraction"})
AREAS: Final = frozenset({"area"})
VOLUMES: Final = frozenset({"volume"})

_DIGITS = re.compile(r"\d+(?:[.,]\d+)?")


def print_limit() -> float:
    """``units.PRINT_LIMIT`` des Baums, der rechnet — ältere Bäume kennen es nicht."""
    try:
        from app.core.units import PRINT_LIMIT
    except ImportError:
        return 0.1 / 40
    return float(PRINT_LIMIT)


# --- Abbilder ------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class MeshHealth:
    """Was an einem Netz schlechter werden kann (§11.2, „kein Netz wird schlechter“).

    ``crossings`` ist ``None``, wenn die Selbstdurchdringung nicht gesucht wurde,
    ``closed_after_weld`` ``None``, wenn die Runde durch STL nicht lief.
    """

    open_edges: int
    branched_edges: int
    degenerate: int
    crossings: int | None = None
    crossings_complete: bool = True
    closed_after_weld: bool | None = None


@dataclasses.dataclass(frozen=True)
class FeatureShot:
    """Ein Merkmal als reine Daten."""

    id: str
    kind: str
    provenance: str
    created_by: int | None
    recognised: bool
    params: Mapping[str, Any]
    measure_sources: Mapping[str, str]
    face_indices: np.ndarray
    patches: tuple[tuple[str, str, Mapping[str, Any], np.ndarray], ...] = ()


@dataclasses.dataclass(frozen=True)
class ExportPart:
    """Ein Körper, wie er aus einer geschriebenen Datei zurückkommt."""

    name: str
    vertices: np.ndarray
    faces: np.ndarray
    colours: tuple[str, ...] = ()
    slot_indices: np.ndarray = dataclasses.field(
        default_factory=lambda: np.zeros(0, dtype=np.int64)
    )


@dataclasses.dataclass(frozen=True)
class ExportShot:
    """Eine Rundreise: geschrieben in ``format`` und wieder gelesen.

    ``problem`` trägt den Grund, wenn Schreiben oder Lesen scheiterte — auch das
    ist ein Ergebnis, das beide Stände teilen müssen.
    """

    format: str
    parts: tuple[ExportPart, ...] = ()
    unit: str = ""
    problem: str = ""


@dataclasses.dataclass(frozen=True)
class BodyShot:
    """Ein Körper der Szene als reine Daten."""

    id: str
    name: str
    kind: str
    plate: int
    material: str | None
    visible: bool
    created_by: int
    frame: tuple[float, ...] | None
    material_slots: tuple[tuple[Any, ...], ...]
    vertices: np.ndarray
    faces: np.ndarray
    slot_indices: np.ndarray
    health: MeshHealth
    features: tuple[FeatureShot, ...] = ()
    reserved_feature_ids: tuple[str, ...] = ()
    exports: tuple[ExportShot, ...] = ()

    @property
    def diagonal(self) -> float:
        used = self.vertices[np.unique(self.faces)] if len(self.faces) else self.vertices[:0]
        if not len(used):
            return 0.0
        return float(np.linalg.norm(used.max(axis=0) - used.min(axis=0)))


@dataclasses.dataclass(frozen=True)
class ResultShot:
    """Ein Ergebnis — Szene, Befunde, Rückfallstufen, Antworten, Fragen — als reine Daten."""

    bodies: tuple[BodyShot, ...]
    findings: tuple[Mapping[str, Any], ...] = ()
    solvers: tuple[tuple[int, str, tuple[str, ...], int | None], ...] = ()
    answers: str = "{}"
    matches: str = "{}"
    completed: tuple[int, ...] = ()
    stopped_at: int | None = None
    questions: tuple[tuple[str, tuple[str, ...]], ...] = ()


class QuestionLog:
    """Ein ``ask`` für :func:`~app.core.scene.evaluate.evaluate`, das jede Frage mitschreibt.

    ``answer`` beantwortet sie; ohne Angabe wird nicht geraten, wie bei der
    Vorgabe der Auswertung (``AmbiguityError``).
    """

    def __init__(self, answer: Callable[[str, list[str]], str] | None = None) -> None:
        self.asked: list[tuple[str, tuple[str, ...]]] = []
        self._answer = answer

    def __call__(self, question: str, choices: list[str]) -> str:
        self.asked.append((str(question), tuple(str(choice) for choice in choices)))
        if self._answer is not None:
            return self._answer(question, choices)
        from app.core.errors import AmbiguityError

        raise AmbiguityError(question, candidates=tuple(choices))


def _plain(value: Any) -> Any:
    """Ein Wert als JSON-taugliche Daten: Zahlen, Texte, Listen, Wörterbücher."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value)
    if isinstance(value, np.ndarray):
        return [_plain(item) for item in value.tolist()]
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=repr) if isinstance(value, (set, frozenset)) else value
        return [_plain(item) for item in items]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _plain(getattr(value, field.name)) for field in dataclasses.fields(value)
        }
    return str(value)


def edge_defects(faces: np.ndarray) -> tuple[int, int]:
    """Offene Kanten (ein Dreieck) und verzweigte (mehr als zwei), über die Eckennummern."""
    if not len(faces):
        return 0, 0
    faces = np.asarray(faces, dtype=np.int64)
    edges = np.sort(faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    width = int(faces.max()) + 1
    # Die Nummer ``a·n + b`` in int64: über 46 341 Ecken liefe int32 über.
    _, counts = np.unique(edges[:, 0] * width + edges[:, 1], return_counts=True)
    return int(np.count_nonzero(counts == 1)), int(np.count_nonzero(counts > 2))


def health_of(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    crossings: bool = True,
    weld: bool = True,
) -> MeshHealth:
    """Offene und verzweigte Kanten, entartete Dreiecke, Selbstdurchdringung, dicht im Slicer.

    Entartet heißt wie beim Einlesen: niedriger als ``EPS_GEOM``
    (``Trimesh.nondegenerate_faces``). Dicht im Slicer heißt: als binäre STL
    geschrieben (Ecken in einfacher Genauigkeit) und über Solidons eigenen
    Einleseweg verschweißt, ohne Lochfüllung — so las ein Slicer den Fall
    RM-166, der per Index dicht war.
    """
    from app.core.deferred import trimesh
    from app.core.units import EPS_GEOM

    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    open_edges, branched = edge_defects(faces)
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False, validate=False)
    degenerate = (
        len(faces) - int(np.count_nonzero(body.nondegenerate_faces(height=EPS_GEOM)))
        if len(faces)
        else 0
    )
    crossing_count: int | None = None
    complete = True
    if crossings and len(faces):
        from app.core.geom.intersections import crossing_face_pairs

        found = crossing_face_pairs(vertices, faces)
        crossing_count, complete = len(found.first), bool(found.complete)
    closed: bool | None = None
    if weld and len(faces):
        closed = closed_after_weld(vertices, faces)
    return MeshHealth(open_edges, branched, degenerate, crossing_count, complete, closed)


def closed_after_weld(vertices: np.ndarray, faces: np.ndarray) -> bool | None:
    """Ob das Netz nach binärer STL und dem Verschweißen beim Einlesen dicht ist."""
    from app.core.deferred import trimesh
    from app.core.geom.mesh import MeshData, read_mesh
    from app.core.ingest.loader import normalise

    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False, validate=False)
    payload = MeshData.of(body).to_stl()
    try:
        read = normalise(
            read_mesh(payload, ".stl"),
            "mm",
            weld=True,
            weld_is_reading=True,
            remove_degenerate=True,
            unify_normals=False,
            mend=False,
            wide_holes=False,
        )
    except TypeError:
        return None
    return bool(read.mesh.is_watertight)


def _feature_shot(feature: Any) -> FeatureShot:
    patches = tuple(
        (
            str(patch.kind),
            str(patch.source),
            _plain(dict(patch.params)),
            np.asarray(patch.face_indices, dtype=np.int64),
        )
        for patch in getattr(feature, "surface_patches", ())
    )
    created = getattr(feature, "created_by", None)
    return FeatureShot(
        id=str(feature.id),
        kind=str(feature.kind),
        provenance=str(feature.provenance),
        created_by=None if created is None else int(created),
        recognised=bool(getattr(feature, "recognised", True)),
        params=_plain(dict(feature.params)),
        measure_sources={
            str(key): str(value)
            for key, value in dict(getattr(feature, "measure_sources", {})).items()
        },
        face_indices=np.asarray(feature.face_indices, dtype=np.int64),
        patches=patches,
    )


def _exported(obj: Any, mesh: Any, export_format: str) -> ExportShot:
    """Schreibt den Körper wie *Exportieren* und liest die Datei wie *Öffnen* zurück."""
    from app.core.export.writer import export_bytes
    from app.core.geom.mesh import read_mesh

    slots = list(obj.material_slots)
    name = str(obj.name)
    try:
        payload = export_bytes(mesh, export_format, slots, name, obj.mesh)
        if export_format in ("stl", "obj"):
            read = read_mesh(payload, f".{export_format}")
            part = ExportPart(
                "",
                np.asarray(read.raw.vertices, dtype=np.float64),
                np.asarray(read.raw.faces, dtype=np.int64),
            )
            return ExportShot(export_format, (part,))
        if export_format == "3mf":
            from app.core.ingest.threemf import declared_unit, read_objects

            parts = tuple(
                ExportPart(
                    str(part.name),
                    np.asarray(part.mesh.raw.vertices, dtype=np.float64),
                    np.asarray(part.mesh.raw.faces, dtype=np.int64),
                    tuple(str(_plain(slot.colour)) for slot in part.slots),
                    np.asarray(part.mesh.slots, dtype=np.int64),
                )
                for part in read_objects(payload)
            )
            return ExportShot(export_format, parts, str(declared_unit(payload)))
        from app.core.brep import step

        assembly = step.read_assembly(payload, name)
        tessellated = step.read(payload).to_mesh()
        parts = (
            ExportPart(
                ",".join(body.name for body in assembly.bodies),
                np.asarray(tessellated.raw.vertices, dtype=np.float64),
                np.asarray(tessellated.raw.faces, dtype=np.int64),
                assembly.colours,
            ),
        )
        return ExportShot(export_format, parts, assembly.unit)
    except Exception as problem:  # das Scheitern selbst ist das Ergebnis
        return ExportShot(export_format, problem=f"{type(problem).__name__}: {problem}")


def body_shot(
    obj: Any,
    *,
    crossings: bool = True,
    weld: bool = True,
    exports: Sequence[str] = ROUND_TRIP_FORMATS,
) -> BodyShot:
    """Ein Körper der Szene als :class:`BodyShot`; ein exakter über seine Vernetzung."""
    from app.core.geom.mesh import as_mesh_data

    mesh = as_mesh_data(obj.mesh)
    vertices = np.array(mesh.raw.vertices, dtype=np.float64)
    faces = np.array(mesh.raw.faces, dtype=np.int64)
    frame = getattr(obj, "frame", None)
    kind = str(getattr(obj, "kind", "mesh"))
    wanted = tuple(name for name in exports if name != "step" or kind == "brep")
    return BodyShot(
        id=str(obj.id),
        name=str(obj.name),
        kind=kind,
        plate=int(getattr(obj, "plate", 0)),
        material=getattr(obj, "material", None),
        visible=bool(getattr(obj, "visible", True)),
        created_by=int(getattr(obj, "created_by", 0)),
        frame=None if frame is None else tuple(float(x) for row in frame for x in row),
        material_slots=tuple(
            tuple(_plain(dataclasses.asdict(slot)).values()) for slot in obj.material_slots
        ),
        vertices=vertices,
        faces=faces,
        slot_indices=np.asarray(mesh.slots, dtype=np.int64),
        health=health_of(vertices, faces, crossings=crossings, weld=weld),
        features=tuple(
            _feature_shot(feature)
            for _, feature in sorted(obj.features.items(), key=lambda item: str(item[0]))
        ),
        reserved_feature_ids=tuple(str(name) for name in getattr(obj, "reserved_feature_ids", ())),
        exports=tuple(_exported(obj, mesh, name) for name in wanted),
    )


def _finding_shot(finding: Any) -> dict[str, Any]:
    return {
        "code": str(finding.code),
        "severity": str(finding.severity),
        "object_id": None if finding.object_id is None else str(finding.object_id),
        "op_id": None if finding.op_id is None else int(finding.op_id),
        "feature_ids": [str(name) for name in finding.feature_ids],
        "object_ids": [str(name) for name in getattr(finding, "object_ids", ())],
        "source": str(getattr(finding, "source", "internal")),
        "suggestions": [str(action.id) for action in getattr(finding, "suggestions", ())],
        "values": _plain(dict(finding.values)),
        "location": _plain(finding.location),
        "outline": _plain(getattr(finding, "outline", ())),
    }


def shot(
    result: Any,
    *,
    questions: QuestionLog | Iterable[tuple[str, Sequence[str]]] = (),
    crossings: bool = True,
    weld: bool = True,
    exports: Sequence[str] = ROUND_TRIP_FORMATS,
) -> ResultShot:
    """Ein ``EvaluationResult`` (oder eine nackte ``Scene``) als :class:`ResultShot`.

    ``crossings=False`` spart die Suche nach Selbstdurchdringung, ``weld=False``
    die STL-Runde, ``exports=()`` die Rundreise — bei Netzen mit Millionen
    Dreiecken, wo sie Minuten kosten; das Urteil sagt dann, was nicht geprüft
    wurde.
    """
    scene = getattr(result, "scene", result)
    asked = questions.asked if isinstance(questions, QuestionLog) else questions
    solvers = getattr(result, "solvers", {}) or {}
    return ResultShot(
        bodies=tuple(
            body_shot(obj, crossings=crossings, weld=weld, exports=exports)
            for obj in scene.objects.values()
        ),
        findings=tuple(_finding_shot(finding) for finding in scene.report.findings),
        solvers=tuple(
            (
                int(op_id),
                str(info.strategy),
                tuple(str(stage) for stage in info.attempted),
                None if info.seed is None else int(info.seed),
            )
            for op_id, info in sorted(solvers.items())
        ),
        answers=json.dumps(_plain(dict(getattr(result, "answers", {}) or {})), sort_keys=True),
        matches=json.dumps(_plain(dict(getattr(result, "matches", {}) or {})), sort_keys=True),
        completed=tuple(int(op) for op in getattr(result, "completed", ())),
        stopped_at=(
            None if getattr(result, "stopped_at", None) is None else int(result.stopped_at)
        ),
        questions=tuple((str(text), tuple(str(c) for c in choices)) for text, choices in asked),
    )


# --- Ablage --------------------------------------------------------------------


def save(result: ResultShot, path: Path) -> Path:
    """Legt ein Abbild als ``.npz`` ab: Felder als Felder, alles andere als JSON."""
    arrays: dict[str, np.ndarray] = {}

    def keep(key: str, array: np.ndarray) -> str:
        arrays[key] = np.asarray(array)
        return key

    bodies = []
    for b, body in enumerate(result.bodies):
        bodies.append(
            {
                **{
                    field.name: _plain(getattr(body, field.name))
                    for field in dataclasses.fields(body)
                    if field.name
                    not in ("vertices", "faces", "slot_indices", "health", "features", "exports")
                },
                "vertices": keep(f"b{b}v", body.vertices),
                "faces": keep(f"b{b}f", body.faces),
                "slot_indices": keep(f"b{b}s", body.slot_indices),
                "health": dataclasses.asdict(body.health),
                "features": [
                    {
                        "id": feature.id,
                        "kind": feature.kind,
                        "provenance": feature.provenance,
                        "created_by": feature.created_by,
                        "recognised": feature.recognised,
                        "params": feature.params,
                        "measure_sources": dict(feature.measure_sources),
                        "face_indices": keep(f"b{b}m{m}", feature.face_indices),
                        "patches": [
                            [kind, source, params, keep(f"b{b}m{m}p{p}", indices)]
                            for p, (kind, source, params, indices) in enumerate(feature.patches)
                        ],
                    }
                    for m, feature in enumerate(body.features)
                ],
                "exports": [
                    {
                        "format": export.format,
                        "unit": export.unit,
                        "problem": export.problem,
                        "parts": [
                            {
                                "name": part.name,
                                "colours": list(part.colours),
                                "vertices": keep(f"b{b}x{x}q{q}v", part.vertices),
                                "faces": keep(f"b{b}x{x}q{q}f", part.faces),
                                "slot_indices": keep(f"b{b}x{x}q{q}s", part.slot_indices),
                            }
                            for q, part in enumerate(export.parts)
                        ],
                    }
                    for x, export in enumerate(body.exports)
                ],
            }
        )
    meta = {
        "bodies": bodies,
        "findings": [_plain(finding) for finding in result.findings],
        "solvers": _plain(result.solvers),
        "answers": result.answers,
        "matches": result.matches,
        "completed": list(result.completed),
        "stopped_at": result.stopped_at,
        "questions": _plain(result.questions),
    }
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    target = path.with_suffix(".npz")
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("arrays.npz", buffer.getvalue())
        archive.writestr("meta.json", json.dumps(meta, sort_keys=True))
    return target


def load(path: Path) -> ResultShot:
    """Liest ein Abbild, das :func:`save` abgelegt hat."""
    with zipfile.ZipFile(path) as archive:
        meta = json.loads(archive.read("meta.json"))
        with np.load(io.BytesIO(archive.read("arrays.npz"))) as stored:
            arrays = {key: stored[key] for key in stored.files}

    def body_of(entry: Mapping[str, Any]) -> BodyShot:
        features = tuple(
            FeatureShot(
                id=feature["id"],
                kind=feature["kind"],
                provenance=feature["provenance"],
                created_by=feature["created_by"],
                recognised=feature["recognised"],
                params=feature["params"],
                measure_sources=feature["measure_sources"],
                face_indices=arrays[feature["face_indices"]],
                patches=tuple(
                    (kind, source, params, arrays[key])
                    for kind, source, params, key in feature["patches"]
                ),
            )
            for feature in entry["features"]
        )
        exports = tuple(
            ExportShot(
                export["format"],
                tuple(
                    ExportPart(
                        part["name"],
                        arrays[part["vertices"]],
                        arrays[part["faces"]],
                        tuple(part["colours"]),
                        arrays[part["slot_indices"]],
                    )
                    for part in export["parts"]
                ),
                export["unit"],
                export["problem"],
            )
            for export in entry["exports"]
        )
        frame = entry["frame"]
        return BodyShot(
            id=entry["id"],
            name=entry["name"],
            kind=entry["kind"],
            plate=entry["plate"],
            material=entry["material"],
            visible=entry["visible"],
            created_by=entry["created_by"],
            frame=None if frame is None else tuple(frame),
            material_slots=tuple(tuple(slot) for slot in entry["material_slots"]),
            vertices=arrays[entry["vertices"]],
            faces=arrays[entry["faces"]],
            slot_indices=arrays[entry["slot_indices"]],
            health=MeshHealth(**entry["health"]),
            features=features,
            reserved_feature_ids=tuple(entry["reserved_feature_ids"]),
            exports=exports,
        )

    return ResultShot(
        bodies=tuple(body_of(entry) for entry in meta["bodies"]),
        findings=tuple(meta["findings"]),
        solvers=tuple(
            (op, strategy, tuple(attempted), seed)
            for op, strategy, attempted, seed in meta["solvers"]
        ),
        answers=meta["answers"],
        matches=meta["matches"],
        completed=tuple(meta["completed"]),
        stopped_at=meta["stopped_at"],
        questions=tuple((text, tuple(choices)) for text, choices in meta["questions"]),
    )


# --- Vergleich -----------------------------------------------------------------


@dataclasses.dataclass
class Verdict:
    """Das Urteil über zwei Abbilder: druckgleich oder nicht, und warum.

    ``discrete`` nennt jeden diskreten Unterschied, ``worse`` jede
    Verschlechterung eines Netzes, ``unchecked`` was nicht geprüft werden
    konnte. ``largest`` ist die größte Abweichung in Millimetern, ``where`` wo
    sie lag; ``deviations`` hält jede Abweichung über null mit ihrem Ort.
    """

    limit: float
    discrete: list[str] = dataclasses.field(default_factory=list)
    worse: list[str] = dataclasses.field(default_factory=list)
    unchecked: list[str] = dataclasses.field(default_factory=list)
    largest: float = 0.0
    where: str = ""
    deviations: list[tuple[float, str]] = dataclasses.field(default_factory=list)

    @property
    def print_equal(self) -> bool:
        return not self.discrete and not self.worse and self.largest <= self.limit

    def deviate(self, gap: float, where: str) -> None:
        if not math.isfinite(gap):
            self.discrete.append(f"{where}: nicht vergleichbar ({gap})")
            return
        if gap > 0.0:
            self.deviations.append((gap, where))
        if gap > self.largest:
            self.largest, self.where = gap, where

    def report(self) -> str:
        lines = [
            ("druckgleich" if self.print_equal else "NICHT druckgleich")
            + f": größte Abweichung {micrometres(self.largest)}"
            + (f" ({self.where})" if self.where else "")
            + f", Grenze {self.limit * 1000:.2f} µm"
        ]
        lines += [f"  diskret: {entry}" for entry in self.discrete]
        lines += [f"  schlechter: {entry}" for entry in self.worse]
        lines += [f"  nicht geprüft: {entry}" for entry in self.unchecked]
        over = sorted((entry for entry in self.deviations if entry[0] > self.limit), reverse=True)
        lines += [f"  über der Grenze: {gap * 1000:.4f} µm {where}" for gap, where in over[:20]]
        return "\n".join(lines)


def micrometres(gap_mm: float) -> str:
    """Eine Abweichung in µm; genau null heißt so, statt in „0,0000 µm“ zu verschwinden."""
    return "genau 0 µm" if gap_mm == 0.0 else f"{gap_mm * 1000:.4f} µm"


def surface_gap(
    first: tuple[np.ndarray, np.ndarray],
    second: tuple[np.ndarray, np.ndarray],
    *,
    enough: float = 0.0,
) -> float:
    """Wie weit die Flächen zweier Netze höchstens auseinanderliegen, in beide Richtungen.

    Tragen beide dieselbe Dreiecksliste, ist die größte Verschiebung einer
    benutzten Ecke eine obere Schranke: Jeder Flächenpunkt ist eine
    Konvexkombination seiner Ecken. Liegt sie bei ``enough`` oder darunter,
    gilt sie. Sonst wird gemessen — jede Ecke und jeder Schwerpunkt des einen
    Netzes gegen die Fläche des anderen, und umgekehrt
    (``geom.mesh.max_distance_to_surface``, exakt). Die Schranke allein wäre
    zu grob: Eine STL-Suppe in anderer Dreiecksfolge trägt dieselbe Liste
    ``0, 1, 2, …`` und ganz andere Ecken dahinter.
    """
    (va, fa), (vb, fb) = first, second
    if not len(fa) and not len(fb):
        return 0.0
    if not len(fa) or not len(fb):
        return math.inf
    if fa.shape == fb.shape and va.shape == vb.shape and np.array_equal(fa, fb):
        used = np.unique(fa)
        bound = float(np.linalg.norm(va[used] - vb[used], axis=1).max())
        if bound <= enough:
            return bound
    from app.core.deferred import trimesh
    from app.core.geom.mesh import max_distance_to_surface

    meshes = [
        trimesh.Trimesh(vertices=v, faces=f, process=False, validate=False)
        for v, f in ((va, fa), (vb, fb))
    ]
    gaps = []
    for mesh, other in ((meshes[0], meshes[1]), (meshes[1], meshes[0])):
        points = np.vstack(
            [np.asarray(mesh.vertices)[np.unique(mesh.faces)], np.asarray(mesh.triangles_center)]
        )
        gaps.append(max_distance_to_surface(other, points))
    return float(max(gaps))


def _area_gap(first: float, second: float) -> float:
    """Eine Flächenänderung als Verschiebung: geteilt durch den kleinsten Umfang (Kreis)."""
    reach = 2.0 * math.sqrt(math.pi * max(abs(first), abs(second), 1e-300))
    return abs(first - second) / reach


def _volume_gap(first: float, second: float) -> float:
    """Eine Volumenänderung als Verschiebung: geteilt durch die kleinste Oberfläche (Kugel)."""
    largest = max(abs(first), abs(second), 1e-300)
    reach = (36.0 * math.pi * largest * largest) ** (1.0 / 3.0)
    return abs(first - second) / reach


def _kind_of(key: str) -> str:
    if key in DIRECTIONS:
        return "direction"
    if key in DEGREES or key.endswith("_degrees"):
        return "degrees"
    if key in RADIANS or key.endswith("_angle"):
        return "radians"
    if key in RATIOS or key.endswith(("_ratio", "_share")):
        return "ratio"
    if key in AREAS or key.endswith("_area"):
        return "area"
    if key in VOLUMES or key.endswith("_volume"):
        return "volume"
    return "length"


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def compare_values(
    key: str, first: Any, second: Any, *, lever: float, where: str, verdict: Verdict
) -> None:
    """Zwei Werte unter einem Schlüssel: Zahlen als Verschiebung, alles andere diskret."""
    if isinstance(first, Mapping) and isinstance(second, Mapping):
        if set(first) != set(second):
            verdict.discrete.append(f"{where}: Schlüssel {sorted(first)} → {sorted(second)}")
            return
        for name in first:
            compare_values(
                name,
                first[name],
                second[name],
                lever=lever,
                where=f"{where}.{name}",
                verdict=verdict,
            )
        return
    if isinstance(first, list) and isinstance(second, list):
        if len(first) != len(second):
            verdict.discrete.append(f"{where}: Länge {len(first)} → {len(second)}")
            return
        kind = _kind_of(key)
        if kind == "direction" and all(map(_number, first + second)):
            gap = math.dist(first, second) * max(lever, 1.0)
            verdict.deviate(gap, where)
            return
        if all(map(_number, first + second)) and kind == "length":
            verdict.deviate(math.dist(first, second) if first else 0.0, where)
            return
        for index, (a, b) in enumerate(zip(first, second, strict=True)):
            compare_values(key, a, b, lever=lever, where=f"{where}[{index}]", verdict=verdict)
        return
    if isinstance(first, float) or isinstance(second, float):
        if not (_number(first) and _number(second)):
            verdict.discrete.append(f"{where}: {first!r} → {second!r}")
            return
        a, b = float(first), float(second)
        if not (math.isfinite(a) and math.isfinite(b)):
            if not (a == b or (math.isnan(a) and math.isnan(b))):
                verdict.discrete.append(f"{where}: {a!r} → {b!r}")
            return
        kind = _kind_of(key)
        if kind == "degrees":
            gap = abs(a - b) * math.pi / 180.0 * max(lever, 1.0)
        elif kind in ("radians", "ratio"):
            gap = abs(a - b) * max(lever, 1.0)
        elif kind == "area":
            gap = _area_gap(a, b)
        elif kind == "volume":
            gap = _volume_gap(a, b)
        else:
            gap = abs(a - b)
        verdict.deviate(gap, where)
        return
    if first != second:
        verdict.discrete.append(f"{where}: {first!r} → {second!r}")


def _area_of(vertices: np.ndarray, faces: np.ndarray) -> float:
    if not len(faces):
        return 0.0
    corners = vertices[faces]
    crossed = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    return float(np.linalg.norm(crossed, axis=1).sum() / 2.0)


def _region(body: BodyShot, indices: np.ndarray) -> tuple[float, np.ndarray | None]:
    """Fläche und flächengewichtete Mitte der genannten Dreiecke."""
    if not len(indices) or not len(body.faces):
        return 0.0, None
    picked = np.asarray(indices, dtype=np.int64)
    picked = picked[(picked >= 0) & (picked < len(body.faces))]
    corners = body.vertices[body.faces[picked]]
    crossed = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    areas = np.linalg.norm(crossed, axis=1) / 2.0
    total = float(areas.sum())
    if total <= 0.0:
        return 0.0, corners.mean(axis=(0, 1))
    return total, (corners.mean(axis=1) * areas[:, None]).sum(axis=0) / total


def _compare_triangles(
    before: BodyShot,
    after: BodyShot,
    first: np.ndarray,
    second: np.ndarray,
    *,
    same_triangles: bool,
    where: str,
    verdict: Verdict,
) -> None:
    """Eine Dreiecksauswahl: bei gleicher Dreiecksliste diskret, sonst als Fläche und Lage."""
    if same_triangles:
        if not np.array_equal(np.sort(first), np.sort(second)):
            verdict.discrete.append(f"{where}: andere Dreiecke bei gleicher Dreiecksliste")
        return
    if bool(len(first)) != bool(len(second)):
        verdict.discrete.append(f"{where}: Dreiecke {len(first)} → {len(second)}")
        return
    area_a, centre_a = _region(before, first)
    area_b, centre_b = _region(after, second)
    verdict.deviate(_area_gap(area_a, area_b), f"{where} (Fläche)")
    if centre_a is not None and centre_b is not None:
        verdict.deviate(float(np.linalg.norm(centre_a - centre_b)), f"{where} (Mitte)")


def _compare_slots(
    before: BodyShot, after: BodyShot, *, same_triangles: bool, verdict: Verdict
) -> None:
    where = f"{before.id}.slots"
    if before.material_slots != after.material_slots:
        verdict.discrete.append(f"{where}: {before.material_slots} → {after.material_slots}")
    # Leer heißt: alles auf Slot 0 (``Mesh.slot_indices``).
    first = before.slot_indices if len(before.slot_indices) else np.zeros(len(before.faces))
    second = after.slot_indices if len(after.slot_indices) else np.zeros(len(after.faces))
    if same_triangles:
        if not np.array_equal(first, second):
            verdict.discrete.append(f"{where}: Slot je Dreieck geändert")
        return
    used_a = sorted(set(first.tolist()))
    used_b = sorted(set(second.tolist()))
    if used_a != used_b:
        verdict.discrete.append(f"{where}: benutzte Slots {used_a} → {used_b}")
        return
    if len(used_a) < 2:
        return
    for slot in used_a:
        _compare_triangles(
            before,
            after,
            np.flatnonzero(first == slot),
            np.flatnonzero(second == slot),
            same_triangles=False,
            where=f"{where}[{slot}]",
            verdict=verdict,
        )


def _compare_health(before: BodyShot, after: BodyShot, verdict: Verdict) -> None:
    a, b = before.health, after.health
    where = before.id
    for name in ("open_edges", "branched_edges", "degenerate"):
        old, new = getattr(a, name), getattr(b, name)
        if new > old:
            verdict.worse.append(f"{where}: {name} {old} → {new}")
    if a.crossings is None or b.crossings is None:
        verdict.unchecked.append(f"{where}: Selbstdurchdringung")
    elif b.crossings > a.crossings or (a.crossings_complete and not b.crossings_complete):
        verdict.worse.append(f"{where}: Selbstdurchdringung {a.crossings} → {b.crossings}")
    if a.closed_after_weld is None or b.closed_after_weld is None:
        verdict.unchecked.append(f"{where}: dicht nach dem Verschweißen")
    elif a.closed_after_weld != b.closed_after_weld:
        entry = (
            f"{where}: dicht nach dem Verschweißen {a.closed_after_weld} → {b.closed_after_weld}"
        )
        verdict.discrete.append(entry)
        if a.closed_after_weld:
            verdict.worse.append(entry)


def _compare_features(
    before: BodyShot, after: BodyShot, *, same_triangles: bool, lever: float, verdict: Verdict
) -> None:
    old = {feature.id: feature for feature in before.features}
    new = {feature.id: feature for feature in after.features}
    if set(old) != set(new):
        verdict.discrete.append(
            f"{before.id}: Merkmale weg {sorted(set(old) - set(new))},"
            f" neu {sorted(set(new) - set(old))}"
        )
    if before.reserved_feature_ids != after.reserved_feature_ids:
        verdict.discrete.append(f"{before.id}: reservierte Merkmalskennungen geändert")
    for name in sorted(set(old) & set(new)):
        a, b = old[name], new[name]
        where = f"{before.id}.{name}"
        for field in ("kind", "provenance", "created_by", "recognised"):
            if getattr(a, field) != getattr(b, field):
                verdict.discrete.append(
                    f"{where}.{field}: {getattr(a, field)!r} → {getattr(b, field)!r}"
                )
        if dict(a.measure_sources) != dict(b.measure_sources):
            verdict.discrete.append(f"{where}: Maßquellen geändert")
        compare_values(
            "", dict(a.params), dict(b.params), lever=lever, where=where, verdict=verdict
        )
        _compare_triangles(
            before,
            after,
            a.face_indices,
            b.face_indices,
            same_triangles=same_triangles,
            where=f"{where}.Dreiecke",
            verdict=verdict,
        )
        if len(a.patches) != len(b.patches):
            verdict.discrete.append(f"{where}: Teilträger {len(a.patches)} → {len(b.patches)}")
            continue
        for index, (pa, pb) in enumerate(zip(a.patches, b.patches, strict=True)):
            spot = f"{where}.Träger[{index}]"
            if pa[:2] != pb[:2]:
                verdict.discrete.append(f"{spot}: {pa[:2]} → {pb[:2]}")
            compare_values("", dict(pa[2]), dict(pb[2]), lever=lever, where=spot, verdict=verdict)
            _compare_triangles(
                before,
                after,
                pa[3],
                pb[3],
                same_triangles=same_triangles,
                where=f"{spot}.Dreiecke",
                verdict=verdict,
            )


def _compare_exports(before: BodyShot, after: BodyShot, verdict: Verdict) -> None:
    old = {export.format: export for export in before.exports}
    new = {export.format: export for export in after.exports}
    if set(old) != set(new):
        verdict.discrete.append(f"{before.id}: Rundreise {sorted(old)} → {sorted(new)}")
    for name in sorted(set(old) & set(new)):
        a, b = old[name], new[name]
        where = f"{before.id}.{name}"
        if a.problem or b.problem:
            if a.problem.split(":")[0] != b.problem.split(":")[0]:
                verdict.discrete.append(
                    f"{where}: {a.problem or 'gelesen'} → {b.problem or 'gelesen'}"
                )
            else:
                verdict.unchecked.append(f"{where}: {a.problem}")
            continue
        if a.unit != b.unit:
            verdict.discrete.append(f"{where}: Einheit {a.unit!r} → {b.unit!r}")
        if len(a.parts) != len(b.parts):
            verdict.discrete.append(f"{where}: Körper {len(a.parts)} → {len(b.parts)}")
            continue
        for index, (pa, pb) in enumerate(zip(a.parts, b.parts, strict=True)):
            spot = f"{where}[{index}]"
            if pa.name != pb.name:
                verdict.discrete.append(f"{spot}: Name {pa.name!r} → {pb.name!r}")
            if pa.colours != pb.colours:
                verdict.discrete.append(f"{spot}: Farben {pa.colours} → {pb.colours}")
            if sorted(set(pa.slot_indices.tolist())) != sorted(set(pb.slot_indices.tolist())):
                verdict.discrete.append(f"{spot}: Slots geändert")
            verdict.deviate(
                surface_gap((pa.vertices, pa.faces), (pb.vertices, pb.faces), enough=verdict.limit),
                spot,
            )


def _compare_bodies(before: BodyShot, after: BodyShot, verdict: Verdict) -> None:
    where = before.id
    for field in ("name", "kind", "plate", "material", "visible", "created_by"):
        if getattr(before, field) != getattr(after, field):
            verdict.discrete.append(
                f"{where}.{field}: {getattr(before, field)!r} → {getattr(after, field)!r}"
            )
    lever = max(before.diagonal, after.diagonal)
    if (before.frame is None) != (after.frame is None):
        verdict.discrete.append(f"{where}.frame: {before.frame} → {after.frame}")
    elif before.frame is not None and after.frame is not None:
        a = np.asarray(before.frame).reshape(4, 4)
        b = np.asarray(after.frame).reshape(4, 4)
        verdict.deviate(
            float(np.abs(a[:3, :3] - b[:3, :3]).max()) * max(lever, 1.0), f"{where}.frame (Drehung)"
        )
        verdict.deviate(float(np.linalg.norm(a[:3, 3] - b[:3, 3])), f"{where}.frame (Lage)")
    verdict.deviate(
        surface_gap(
            (before.vertices, before.faces),
            (after.vertices, after.faces),
            enough=verdict.limit,
        ),
        f"{where} (Fläche)",
    )
    same_triangles = before.faces.shape == after.faces.shape and np.array_equal(
        before.faces, after.faces
    )
    _compare_slots(before, after, same_triangles=same_triangles, verdict=verdict)
    _compare_health(before, after, verdict)
    _compare_features(before, after, same_triangles=same_triangles, lever=lever, verdict=verdict)
    _compare_exports(before, after, verdict)


def _masked(text: str) -> str:
    return _DIGITS.sub("#", text)


def compare(before: ResultShot, after: ResultShot, *, limit: float | None = None) -> Verdict:
    """Das Urteil: ist ``after`` druckgleich zu ``before`` (§11.2)?"""
    verdict = Verdict(print_limit() if limit is None else limit)
    ids_a = [body.id for body in before.bodies]
    ids_b = [body.id for body in after.bodies]
    if ids_a != ids_b:
        verdict.discrete.append(f"Körper und Folge: {ids_a} → {ids_b}")
    after_by_id = {body.id: body for body in after.bodies}
    for body in before.bodies:
        if body.id in after_by_id:
            _compare_bodies(body, after_by_id[body.id], verdict)
    scene_lever = max((body.diagonal for body in before.bodies), default=1.0)
    levers = {body.id: body.diagonal for body in before.bodies}
    if len(before.findings) != len(after.findings):
        verdict.discrete.append(
            "Befunde: "
            f"{[f['code'] for f in before.findings]} → {[f['code'] for f in after.findings]}"
        )
    else:
        for index, (a, b) in enumerate(zip(before.findings, after.findings, strict=True)):
            where = f"Befund[{index}] {a['code']}"
            lever = levers.get(a.get("object_id") or "", scene_lever)
            for key in sorted(set(a) | set(b)):
                if key in ("values", "location", "outline"):
                    continue
                if a.get(key) != b.get(key):
                    verdict.discrete.append(f"{where}.{key}: {a.get(key)!r} → {b.get(key)!r}")
            compare_values(
                "", a["values"], b["values"], lever=lever, where=f"{where}.values", verdict=verdict
            )
            if (a["location"] is None) != (b["location"] is None):
                verdict.discrete.append(f"{where}.location: {a['location']} → {b['location']}")
            elif a["location"] is not None:
                verdict.deviate(math.dist(a["location"], b["location"]), f"{where}.location")
            _compare_outline(a["outline"], b["outline"], f"{where}.outline", verdict)
    if [s[:3] for s in before.solvers] != [s[:3] for s in after.solvers]:
        verdict.discrete.append(f"Rückfallstufe: {before.solvers} → {after.solvers}")
    for name in ("answers", "matches", "completed", "stopped_at"):
        if getattr(before, name) != getattr(after, name):
            verdict.discrete.append(f"{name}: {getattr(before, name)} → {getattr(after, name)}")
    asked_a = [(_masked(text), tuple(map(_masked, choices))) for text, choices in before.questions]
    asked_b = [(_masked(text), tuple(map(_masked, choices))) for text, choices in after.questions]
    if asked_a != asked_b:
        verdict.discrete.append(f"Fragen: {before.questions} → {after.questions}")
    return verdict


def _compare_outline(first: list[Any], second: list[Any], where: str, verdict: Verdict) -> None:
    """Randkanten eines Befunds: Endpunkte beidseitig zum nächsten Endpunkt."""
    if bool(first) != bool(second):
        verdict.discrete.append(f"{where}: {len(first)} → {len(second)} Kanten")
        return
    if not first:
        return
    from scipy.spatial import cKDTree

    a = np.asarray(first, dtype=np.float64).reshape(-1, 3)
    b = np.asarray(second, dtype=np.float64).reshape(-1, 3)
    gap = max(float(cKDTree(b).query(a)[0].max()), float(cKDTree(a).query(b)[0].max()))
    verdict.deviate(gap, where)


def compare_results(
    before: Any, after: Any, *, limit: float | None = None, **options: Any
) -> Verdict:
    """Zwei lebende Ergebnisse desselben Baums: Abbild beider, dann :func:`compare`."""
    return compare(shot(before, **options), shot(after, **options), limit=limit)
