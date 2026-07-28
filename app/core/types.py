"""Core contracts (Bauplan §9).

Every module aligns with the signatures below; they are fixed before any
implementation exists. Four rules follow from them:

1. ``OpContext.scene`` is read-only. An operation creates new objects, it never
   changes existing ones — that is Leitprinzip 2 anchored in the type layer.
2. Every operation reports ``findings`` instead of logging. The core decides what
   ends up in the report and the digest.
3. ``progress``, ``ask`` and ``cancelled`` are part of the contract, not access to
   global objects — the technical safeguard of the core/surface separation.
4. ``quality`` is passed through. Every operation serves both levels, if need be
   by treating them the same.

This module holds contracts only: no geometry, no IO, no third-party imports.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from app.i18n import TranslatableText

# --- Identifiers ---------------------------------------------------------------

ObjectId = str
"""``obj_2`` — stable within one document."""

FeatureId = str
"""``hole_3`` (detected) or ``op4.pin_1`` (generated, §21.2)."""

OpId = int
"""Position-independent number of an operation in the stack."""

TransactionId = str
"""``t2`` — the unit undo, diff view and chat history refer to (§15.5)."""

SourceId = str
"""``src_1`` — an imported or generated mesh in the project container."""

ParameterName = str
"""Name of a project parameter, referenced as ``@name`` in expressions (§13)."""

Millimetres = float
"""Every length in the core. Always (§11.1)."""

# --- Enumerations --------------------------------------------------------------

FeatureKind = Literal["hole", "face", "edge_loop", "pin", "thread"]
Provenance = Literal["detected", "generated"]
ObjectKind = Literal["mesh", "brep"]
Quality = Literal["draft", "fine"]
FitKind = Literal["clearance", "press", "thread", "flush"]
Severity = Literal["info", "warning", "error"]
Authorship = Literal["user", "agent"]
SourceKind = Literal["import", "generated", "part"]

SolverStage = Literal["direct", "welded", "jittered", "voxel"]
"""Stages of the boolean fallback chain (§17.2), in order."""

SOLVER_CHAIN: tuple[SolverStage, ...] = ("direct", "welded", "jittered", "voxel")

MetricSource = Literal["internal", "gcode"]
"""Where a print metric comes from. Never mixed (§22.5)."""

# --- Geometry primitives -------------------------------------------------------

Vec3 = tuple[float, float, float]
Point2 = tuple[float, float]
Ring = tuple[Point2, ...]


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned bounds in millimetres."""

    minimum: Vec3
    maximum: Vec3

    @property
    def size(self) -> Vec3:
        return (
            self.maximum[0] - self.minimum[0],
            self.maximum[1] - self.minimum[1],
            self.maximum[2] - self.minimum[2],
        )

    @property
    def centre(self) -> Vec3:
        return (
            (self.maximum[0] + self.minimum[0]) / 2.0,
            (self.maximum[1] + self.minimum[1]) / 2.0,
            (self.maximum[2] + self.minimum[2]) / 2.0,
        )

    @property
    def diagonal(self) -> float:
        """Model size behind the relative tolerance ``EPS_MATCH`` (§11.2)."""
        width, depth, height = self.size
        return math.sqrt(width * width + depth * depth + height * height)


@dataclass(frozen=True, slots=True)
class Polygon:
    """A closed contour with optional holes, used by the layer analysis (§22)."""

    outline: Ring
    holes: tuple[Ring, ...] = ()


@runtime_checkable
class Mesh(Protocol):
    """Hull around the geometry kernel (``manifold3d`` / ``trimesh``).

    The rest of the core talks to this protocol, never to a kernel directly, so
    the kernel stays exchangeable and ``core`` stays importable without it.
    """

    @property
    def vertex_count(self) -> int: ...

    @property
    def triangle_count(self) -> int: ...

    @property
    def bounds(self) -> BoundingBox: ...

    @property
    def volume(self) -> float:
        """Signed volume in mm³; meaningless unless watertight."""

    @property
    def area(self) -> float:
        """Surface area in mm²."""

    @property
    def is_watertight(self) -> bool: ...

    @property
    def component_count(self) -> int:
        """Connected components — small ones are reported, never dropped (§17.1)."""

    @property
    def slot_indices(self) -> Sequence[int]:
        """Material slot index per triangle (§20). Empty means everything on slot 0."""


# --- Features and objects ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Feature:
    """A recognised hole, face or edge — the vocabulary shared by mouse and agent."""

    id: FeatureId
    kind: FeatureKind
    provenance: Provenance
    params: Mapping[str, Any]
    """Diameter, axis, depth, area … in millimetres."""
    face_indices: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class MaterialSlot:
    """One filament slot of an object (§20)."""

    index: int
    name: str
    colour: tuple[float, float, float] | None = None
    material: str | None = None


@dataclass(slots=True)
class SceneObject:
    """One body in the scene."""

    id: ObjectId
    name: str
    mesh: Mesh
    kind: ObjectKind = "mesh"
    features: dict[FeatureId, Feature] = field(default_factory=dict)
    material_slots: list[MaterialSlot] = field(default_factory=list)
    created_by: OpId = 0
    visible: bool = True


# --- Parameters, fits, profiles ------------------------------------------------


@dataclass(frozen=True, slots=True)
class Parameter:
    """A named project dimension (§13).

    Either a plain value or an expression over other parameters. Expressions run
    through the own evaluator, never through ``eval`` (§13, §32).
    """

    name: ParameterName
    value: float
    unit: str = "mm"
    title: TranslatableText | str | None = None
    minimum: float | None = None
    maximum: float | None = None
    expression: str | None = None


@dataclass(frozen=True, slots=True)
class FeatureRef:
    """Reference to a feature of a specific object, written ``obj_2:op5.pin_1``."""

    object_id: ObjectId
    feature_id: FeatureId

    @classmethod
    def parse(cls, text: str) -> FeatureRef:
        object_id, separator, feature_id = text.partition(":")
        if not separator or not object_id or not feature_id:
            raise ValueError(f"malformed feature reference: {text!r}")
        return cls(object_id, feature_id)

    def __str__(self) -> str:
        return f"{self.object_id}:{self.feature_id}"


Tolerance = float | str
"""A number in millimetres, or ``auto:<material>`` pointing into the profile (§12).

Rule 7 in AGENTS.md: tolerances are references, not literals — that is what makes
calibration (§28.3) reach existing projects.
"""

AUTO_TOLERANCE_PREFIX = "auto:"


@dataclass(frozen=True, slots=True)
class Fit:
    """A named relation between two features (§14)."""

    name: str
    a: FeatureRef
    b: FeatureRef
    kind: FitKind = "clearance"
    tolerance: Tolerance = "auto:"


@dataclass(frozen=True, slots=True)
class PrinterProfile:
    """Build volume and nozzle data. Never hard-coded (§38)."""

    id: str
    title: str
    build_volume: Vec3
    nozzle_diameter: float = 0.4
    layer_height: float = 0.2
    extrusion_width: float = 0.42
    enclosed: bool = False
    """Closed chamber — decides whether ASA and ABS are sensible at all."""
    bed_temperature_max: int = 100
    nozzle_temperature_max: int = 260
    vendor: str = ""


@dataclass(frozen=True, slots=True)
class MaterialProfile:
    """Material behaviour and the tolerances calibration writes back into (§28.3)."""

    id: str
    title: str
    clearance: float
    """Sliding fit gap in mm."""
    press: float
    """Interference for a press fit in mm (negative means oversize)."""
    hole_compensation: float
    """FDM prints holes tight — add this to the nominal diameter."""
    elephant_foot: float
    """First layer spread to compensate for."""
    shrinkage: float = 0.0
    """Relative shrinkage, 0.004 = 0.4 %."""
    calibrated: bool = False
    """False means the values are the shipped starting point, not measured."""


@dataclass(frozen=True, slots=True)
class Profile:
    """The printer and material a scene is computed for."""

    printer: PrinterProfile
    material: MaterialProfile

    @property
    def minimum_wall_thickness(self) -> float:
        """Two extrusion widths, never less — first rule of the rule set (§39)."""
        return 2.0 * self.printer.extrusion_width


# --- Findings and report -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Finding:
    """One entry of the report (§17.3).

    Operations return findings instead of logging, so the core decides what
    reaches report, digest and status bar.
    """

    code: str
    """Stable identifier such as ``ingest.small_components`` — testable, translatable."""
    severity: Severity
    message: TranslatableText | str
    object_id: ObjectId | None = None
    op_id: OpId | None = None
    feature_ids: tuple[FeatureId, ...] = ()
    values: Mapping[str, float | str] = field(default_factory=dict)
    location: Vec3 | None = None
    """Where to fly the camera when the warning is clicked (§18.4)."""
    source: MetricSource = "internal"


@dataclass(frozen=True, slots=True)
class Report:
    """Findings from ingest, operations and checks (§17.3)."""

    findings: tuple[Finding, ...] = ()

    @property
    def worst_severity(self) -> Severity | None:
        order: tuple[Severity, ...] = ("info", "warning", "error")
        present = [f.severity for f in self.findings]
        return max(present, key=order.index) if present else None

    def for_object(self, object_id: ObjectId) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.object_id == object_id)

    def with_findings(self, findings: Sequence[Finding]) -> Report:
        return Report(findings=(*self.findings, *findings))


# --- Scene ---------------------------------------------------------------------


@dataclass(slots=True)
class Scene:
    """The evaluated state: the result of stack + sources + parameters + profiles."""

    objects: dict[ObjectId, SceneObject] = field(default_factory=dict)
    parameters: dict[ParameterName, Parameter] = field(default_factory=dict)
    fits: list[Fit] = field(default_factory=list)
    profile: Profile | None = None
    report: Report = field(default_factory=Report)


# --- Operation context ---------------------------------------------------------

ProgressFn = Callable[[float, str], None]
"""``(fraction, text) -> None``. Reported often enough to stay honest (§2.8)."""

AskFn = Callable[[str, list[str]], str]
"""``(question, choices) -> chosen``. The only way the core asks (Leitprinzip 6)."""


@runtime_checkable
class CancelToken(Protocol):
    """Cooperative cancellation. Long operations poll it (§15.6)."""

    @property
    def is_cancelled(self) -> bool: ...

    def raise_if_cancelled(self) -> None:
        """Raise ``OperationCancelled`` if cancellation was requested."""


class BaseParams:
    """Base of every validated parameter set of an operation (§10).

    The schema — bounds, units, defaults and front/advanced placement (§2.4) — is
    derived once from the declaration and validates dialog, command line and
    agent call alike.
    """

    __slots__ = ()

    @classmethod
    def spec(cls) -> tuple[ParamSpec, ...]:
        """Parameter schema of this set. Filled in by the registry."""
        return getattr(cls, "__param_spec__", ())

    def as_dict(self) -> dict[str, Any]:
        """Serialisable form, as stored in the op stack."""
        return {name: getattr(self, name) for name in (spec.name for spec in self.spec())}


ParamKind = Literal["float", "int", "bool", "str", "enum", "object", "feature", "part", "source"]
ParamPlacement = Literal["front", "advanced"]
"""Front side or ``More settings`` — the graded depth from §2.4."""


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """One entry of a parameter schema."""

    name: str
    kind: ParamKind
    title: TranslatableText | str
    default: Any = None
    required: bool = False
    """True when there is no default and the caller has to supply a value."""
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()
    placement: ParamPlacement = "front"
    doc: TranslatableText | str | None = None


@runtime_checkable
class SourceAccess(Protocol):
    """Read access to the sources of the project (§16.1).

    An addition to the contract in §9, and a deliberate one: the ``load``
    operation has to read a file, and putting bytes into the operation
    parameters would drag geometry into the stack. Access stays read-only and
    goes through the context like everything else.
    """

    def read(self, source_id: SourceId) -> bytes: ...

    def describe(self, source_id: SourceId) -> Source: ...


@dataclass(slots=True)
class OpContext:
    """Everything an operation may see and use. Nothing global, no dialogs."""

    scene: Scene
    """Read-only. Operations create objects, they do not change them."""
    inputs: list[SceneObject]
    params: BaseParams
    profile: Profile
    quality: Quality
    seed: int | None
    progress: ProgressFn
    ask: AskFn
    cancelled: CancelToken
    sources: SourceAccess | None = None


@dataclass(frozen=True, slots=True)
class SolverInfo:
    """Which fallback stage solved a boolean operation (§17.2)."""

    strategy: SolverStage
    attempted: tuple[SolverStage, ...] = ()
    seed: int | None = None
    note: TranslatableText | str | None = None


@dataclass(slots=True)
class OpResult:
    """What an operation returns. Never a mutated input."""

    outputs: list[SceneObject]
    solver: SolverInfo | None = None
    findings: list[Finding] = field(default_factory=list)


OpFn = Callable[[OpContext], OpResult]


# --- Stack, transactions, document ---------------------------------------------


@dataclass(frozen=True, slots=True)
class Origin:
    """Who created a transaction, and under which conditions (§26.4)."""

    by: Authorship
    model: str | None = None
    prompt_version: str | None = None
    rules_version: str | None = None
    temperature: float | None = None


@dataclass(frozen=True, slots=True)
class Operation:
    """One entry of the stack (§12). ``inputs``/``outputs`` form the DAG."""

    id: OpId
    op: str
    inputs: tuple[ObjectId, ...] = ()
    outputs: tuple[ObjectId, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    solver: SolverInfo | None = None
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class Transaction:
    """A group of operations that undo together (§15.5)."""

    id: TransactionId
    title: TranslatableText | str
    ops: tuple[OpId, ...]
    origin: Origin = Origin(by="user")


@dataclass(frozen=True, slots=True)
class SourceOrigin:
    """Where an imported model came from, and under which licence (§16.3)."""

    url: str | None = None
    title: str | None = None
    author: str | None = None
    licence: str | None = None
    retrieved: str | None = None


@dataclass(frozen=True, slots=True)
class IngestInfo:
    """What the input stage did to a source (§17.1)."""

    unit: str = "mm"
    scale: float = 1.0
    welded: bool = False
    removed_triangles: int = 0
    components: int = 1


@dataclass(frozen=True, slots=True)
class Source:
    """An embedded or linked input mesh. Paths are always relative (§32)."""

    id: SourceId
    kind: SourceKind
    path: str
    sha256: str
    embedded: bool = True
    """Embedded is the default for passing a project on (§16.1); linked stays relative."""
    ingest: IngestInfo = IngestInfo()
    origin: SourceOrigin | None = None


@dataclass(slots=True)
class Document:
    """The saved project: stack, parameters, fits, transactions, sources (§12).

    The scene is what evaluating this document produces — the document is the
    truth, the scene is the result.
    """

    format_version: int
    app_version: str
    libs: dict[str, str] = field(default_factory=dict)
    parts_version: str = "0"
    printer: str = ""
    material: str = ""
    parameters: dict[ParameterName, Parameter] = field(default_factory=dict)
    sources: dict[SourceId, Source] = field(default_factory=dict)
    fits: list[Fit] = field(default_factory=list)
    transactions: list[Transaction] = field(default_factory=list)
    ops: list[Operation] = field(default_factory=list)


# --- Layer analysis (§22) ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LayerInfo:
    """Metrics of one slicing plane."""

    z: float
    contours: tuple[Polygon, ...]
    area: float
    overhang_area: float
    islands: tuple[Polygon, ...]
    min_width: float
    overhangs: tuple[Polygon, ...] = ()
    """*Where* the unsupported area of this layer lies, not only how much of it.

    Kept because the support map (§18.4) and the layer preview (§18.10) have to
    point at the spot, and recomputing it from the contours would be the same
    work twice."""


@dataclass(frozen=True, slots=True)
class SliceResult:
    """Result of the analysis slicer. Its numbers are never mixed with G-code (§22.5)."""

    layers: tuple[LayerInfo, ...]
    support_volume: float
    first_layer_area: float
    source: MetricSource = "internal"


# --- Further fixed contracts ---------------------------------------------------


@dataclass(slots=True)
class PartResult:
    """What a part returns: geometry plus named provenance features (§24.1)."""

    mesh: Mesh
    features: dict[FeatureId, Feature] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)


PartFn = Callable[[BaseParams], PartResult]


class MeshBackend(Protocol):
    """Mesh generation, local or hosted — same call either way (§27).

    Knows text and image only: no user code, no file paths, no state.
    """

    def text_to_mesh(self, prompt: str, seed: int | None = None) -> Mesh: ...

    def image_to_mesh(self, image: bytes, seed: int | None = None) -> Mesh: ...


class LLMBackend(Protocol):
    """Cloud or local model behind one interface (§27)."""

    @property
    def name(self) -> str: ...

    def complete(
        self,
        system: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        temperature: float = 0.2,
    ) -> Mapping[str, Any]: ...


class Migration(Protocol):
    """One step of the format migration chain (§16.2). Steps are never merged."""

    @property
    def from_version(self) -> int: ...

    @property
    def to_version(self) -> int: ...

    def apply(self, data: dict[str, Any]) -> dict[str, Any]: ...
