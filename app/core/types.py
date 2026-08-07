"""Die Verträge des Kerns (Bauplan §9).

Jedes Modul richtet sich nach den Signaturen hier; sie stehen fest, bevor eine
Umsetzung existiert. Vier Regeln folgen aus ihnen:

1. ``OpContext.scene`` ist nur lesend. Eine Operation erzeugt neue Objekte, sie
   ändert nie bestehende — Leitprinzip 2, verankert in der Typebene.
2. Jede Operation meldet ``findings`` statt zu protokollieren. Der Kern
   entscheidet, was in Prüfbericht und Steckbrief landet.
3. ``progress``, ``ask`` und ``cancelled`` sind Teil des Vertrags, kein Zugriff
   auf globale Objekte — die technische Absicherung der Kern-Oberflächen-Trennung.
4. ``quality`` wird durchgereicht. Jede Operation bedient beide Stufen, notfalls
   indem sie beide gleich behandelt.

Dieses Modul enthält nur Verträge: keine Geometrie, kein IO, keine Fremdimporte.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Protocol, get_args, runtime_checkable

from app.i18n import TranslatableText

# --- Bezeichner ----------------------------------------------------------------

ObjectId = str
"""``obj_2`` — stabil innerhalb eines Dokuments."""

FeatureId = str
"""``hole_3`` (erkannt) oder ``op4.pin_1`` (erzeugt, §21.2)."""

OpId = int
"""Positionsunabhängige Nummer einer Operation im Stapel."""

TransactionId = str
"""``t2`` — die Einheit, auf die sich Undo, Differenzansicht und Chatverlauf
beziehen (§15.5)."""

SourceId = str
"""``src_1`` — ein importiertes oder erzeugtes Netz im Projektcontainer."""

ParameterName = str
"""Name eines Projektparameters, in Ausdrücken als ``@name`` gelesen (§13)."""

Millimetres = float
"""Jede Länge im Kern. Immer (§11.1)."""

# --- Aufzählungen --------------------------------------------------------------

FeatureKind = Literal["hole", "face", "edge_loop", "pin", "thread"]
Provenance = Literal["detected", "generated"]
ObjectKind = Literal["mesh", "brep"]
Quality = Literal["draft", "fine"]
FitKind = Literal["clearance", "press", "thread", "flush"]
FIT_KINDS: Final[tuple[str, ...]] = get_args(FitKind)
"""Dieselben Arten, zur Laufzeit prüfbar.

Aus dem Typ abgeleitet und nicht daneben geschrieben: eine zweite Liste wäre
am Tag nach der nächsten Passungsart falsch, und wer sie prüft, prüfte dann
gegen den alten Stand. Die Oberfläche liest sie hier, der Agent auch — was von
außen kommt, ist geprüft, bevor es in ein Dokument gelangt."""

Severity = Literal["info", "warning", "error"]
Authorship = Literal["user", "agent"]

ChatRole = Literal["user", "agent"]
"""Wer gesprochen hat. Dieselben zwei wie ``Authorship``, benannt fürs
Gespräch (§26.3)."""
SourceKind = Literal["import", "generated", "part"]

SolverStage = Literal["direct", "welded", "jittered", "voxel"]
"""Die Stufen der Booleschen Rückfallkette (§17.2), in ihrer Reihenfolge."""

SOLVER_CHAIN: tuple[SolverStage, ...] = ("direct", "welded", "jittered", "voxel")

MetricSource = Literal["internal", "gcode"]
"""Woher eine Druckkennzahl stammt. Wird nie vermischt (§22.5)."""

# --- Geometrische Grundtypen ---------------------------------------------------

Vec3 = tuple[float, float, float]
Point2 = tuple[float, float]
Ring = tuple[Point2, ...]

Transform = tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]
"""Eine 4x4-Matrix als nackte Zahlen, Zeile für Zeile. Als Tupel statt als
Array gehalten, damit sie unverändert durch Cache und Projektdatei reist."""


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Achsparalleler Hüllquader in Millimetern."""

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
        """Die Modellgröße hinter der relativen Toleranz ``EPS_MATCH`` (§11.2)."""
        width, depth, height = self.size
        return math.sqrt(width * width + depth * depth + height * height)


@dataclass(frozen=True, slots=True)
class Polygon:
    """Eine geschlossene Kontur mit optionalen Löchern, benutzt von der
    Schichtanalyse (§22)."""

    outline: Ring
    holes: tuple[Ring, ...] = ()


@runtime_checkable
class Mesh(Protocol):
    """Die Hülle um den Geometriekern (``manifold3d`` / ``trimesh``).

    Der Rest des Kerns spricht mit diesem Protokoll, nie direkt mit einem
    Kern — so bleibt der Kern austauschbar und ``core`` ohne ihn importierbar.
    """

    @property
    def vertex_count(self) -> int: ...

    @property
    def triangle_count(self) -> int: ...

    @property
    def bounds(self) -> BoundingBox: ...

    @property
    def volume(self) -> float:
        """Vorzeichenbehaftetes Volumen in mm³; ohne Wasserdichtheit bedeutungslos."""

    @property
    def area(self) -> float:
        """Oberfläche in mm²."""

    @property
    def is_watertight(self) -> bool: ...

    @property
    def component_count(self) -> int:
        """Zusammenhängende Komponenten — kleine werden gemeldet, nie
        verworfen (§17.1)."""

    @property
    def slot_indices(self) -> Sequence[int]:
        """Materialslot-Index je Dreieck (§20). Leer heißt: alles auf Slot 0."""


@runtime_checkable
class BRepBody(Protocol):
    """Ein Körper, der seine Flächen und Kanten noch kennt (§30).

    Hier statt im B-Rep-Paket deklariert, damit der Rest des Kerns die beiden
    Sorten unterscheiden kann, ohne OpenCASCADE zu importieren — das ist
    optional, und ``core`` muss ohne es importierbar bleiben.
    """

    @property
    def shape(self) -> Any:
        """Das kerneigene Objekt. Außerhalb des B-Rep-Pakets liest es niemand."""

    def to_mesh(self) -> Any:
        """Die Einbahntür aus §30: Dreiecke aus dem exakten Körper."""


def kind_of(mesh: Mesh) -> ObjectKind:
    """Welche Sorte Körper das ist. Eine Regel, ein Ort — der Objektbaum zeigt es."""
    return "brep" if isinstance(mesh, BRepBody) else "mesh"


# --- Merkmale und Objekte ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Feature:
    """Ein erkanntes Loch, eine Fläche, eine Kante — das gemeinsame Vokabular
    von Maus und Agent."""

    id: FeatureId
    kind: FeatureKind
    provenance: Provenance
    params: Mapping[str, Any]
    """Durchmesser, Achse, Tiefe, Fläche … in Millimetern."""
    face_indices: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class MaterialSlot:
    """Ein Filamentslot eines Objekts (§20)."""

    index: int
    name: str
    colour: tuple[float, float, float] | None = None
    material: str | None = None


@dataclass(slots=True)
class SceneObject:
    """Ein Körper in der Szene."""

    id: ObjectId
    name: str
    mesh: Mesh
    kind: ObjectKind = "mesh"
    features: dict[FeatureId, Feature] = field(default_factory=dict)
    material_slots: list[MaterialSlot] = field(default_factory=list)
    material: str | None = None
    """In welchem Material dieser Körper gedruckt wird — ``None`` heißt: im
    Projektmaterial.

    Eine Szene ist nicht ein Material. Eine TPU-Dichtung im PETG-Gehäuse
    schrumpft anders, will ein anderes Spiel und quetscht ihre erste Schicht
    anders; sie mit dem Projektmaterial zu rechnen liefert eine Zahl, die
    falsch ist statt ungefähr (§12, §38)."""
    plate: int = 0
    """Auf welcher Druckplatte dieses Objekt liegt. Gesetzt vom Anordnen; eine
    Szene mit mehr Teilen, als auf eine Platte passen, ist normal, kein
    Fehler (§25)."""
    created_by: OpId = 0
    visible: bool = True


# --- Parameter, Passungen, Profile ---------------------------------------------


@dataclass(frozen=True, slots=True)
class Parameter:
    """Ein benanntes Projektmaß (§13).

    Entweder ein nackter Wert oder ein Ausdruck über andere Parameter.
    Ausdrücke laufen durch den eigenen Auswerter, nie durch ``eval`` (§13, §32).
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
    """Verweis auf ein Merkmal eines bestimmten Objekts, geschrieben
    ``obj_2:op5.pin_1``."""

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
"""Eine Zahl in Millimetern, oder ``auto:<material>`` als Verweis ins
Profil (§12).

Regel 7 in AGENTS.md: Toleranzen sind Verweise, keine Literale — genau das
lässt die Kalibrierung (§28.3) bestehende Projekte erreichen.
"""

AUTO_TOLERANCE_PREFIX = "auto:"


@dataclass(frozen=True, slots=True)
class Fit:
    """Eine benannte Beziehung zwischen zwei Merkmalen (§14)."""

    name: str
    a: FeatureRef
    b: FeatureRef
    kind: FitKind = "clearance"
    tolerance: Tolerance = "auto:"


@dataclass(frozen=True, slots=True)
class PrinterProfile:
    """Bauraum und Düsendaten. Nie fest im Code (§38)."""

    id: str
    title: str
    build_volume: Vec3
    nozzle_diameter: float = 0.4
    layer_height: float = 0.2
    extrusion_width: float = 0.42
    enclosed: bool = False
    """Geschlossener Bauraum — entscheidet, ob ASA und ABS überhaupt
    sinnvoll sind."""
    bed_temperature_max: int = 100
    nozzle_temperature_max: int = 260
    vendor: str = ""


@dataclass(frozen=True, slots=True)
class MaterialProfile:
    """Materialverhalten und die Toleranzen, in die die Kalibrierung
    zurückschreibt (§28.3)."""

    id: str
    title: str
    clearance: float
    """Spiel einer Gleitpassung in mm."""
    press: float
    """Übermaß einer Presspassung in mm (negativ heißt Übergröße)."""
    hole_compensation: float
    """FDM druckt Löcher zu eng — dieser Wert kommt auf den Nenndurchmesser."""
    elephant_foot: float
    """Die Breite, um die die erste Schicht auseinanderläuft."""
    shrinkage: float = 0.0
    """Relativer Schrumpf, 0.004 = 0,4 %."""
    calibrated: bool = False
    """False heißt: die Werte sind der mitgelieferte Startpunkt, nicht gemessen."""


@dataclass(frozen=True, slots=True)
class Profile:
    """Drucker und Material, für die eine Szene gerechnet wird."""

    printer: PrinterProfile
    material: MaterialProfile

    @property
    def minimum_wall_thickness(self) -> float:
        """Zwei Extrusionsbreiten, nie weniger — die erste Regel der
        Regelsammlung (§39)."""
        return 2.0 * self.printer.extrusion_width


# --- Druckeinstellungen (§29) --------------------------------------------------
#
# Solidon hält die Einstellungen, der externe Slicer führt sie aus (§22, §29).
# Das hier ist also kein Slicer-Format, sondern das eine Modell, aus dem
# ``export.handover`` die Konfiguration jedes unterstützten Slicers schreibt.
# Gruppiert statt flach, weil die Oberfläche in denselben Gruppen fragt und die
# Zuordnungstabellen Punktpfade wie ``cooling.fan_speed`` benutzen.

InfillPattern = Literal["grid", "gyroid", "honeycomb", "cubic", "lines", "triangles"]
SupportStyle = Literal["none", "grid", "tree"]
SupportPlacement = Literal["everywhere", "build_plate"]
SeamPosition = Literal["aligned", "nearest", "random", "rear"]

#: Wie die Wandbahnen erzeugt werden. ``classic`` legt feste Linienbreiten und
#: füllt, was dazwischen übrig bleibt, mit Lückenfüllung; ``arachne`` verteilt
#: die vorhandene Breite auf so viele Bahnen, wie hineinpassen. Der Unterschied
#: zählt genau dort, wo eine Wand nicht auf ganze Linien aufgeht — bei einem
#: 1,1 mm dicken Federarm etwa liegen zwei Bahnen à 0,55 statt zweier à 0,42
#: mit einer Lücke dazwischen.
WallGenerator = Literal["classic", "arachne"]
AdhesionType = Literal["none", "skirt", "brim", "raft"]
QualityPreset = Literal["draft", "standard", "fine", "strong"]


@dataclass(frozen=True, slots=True)
class LayerSettings:
    """Schichthöhen und Extrusionsbreiten in Millimetern."""

    layer_height: float = 0.2
    first_layer_height: float = 0.25
    line_width: float = 0.42
    first_layer_line_width: float = 0.45


@dataclass(frozen=True, slots=True)
class ShellSettings:
    """Wände, Deckel und Boden — was die Festigkeit und die Oberfläche macht."""

    wall_count: int = 3
    top_layers: int = 5
    bottom_layers: int = 4
    outer_wall_first: bool = False
    """Außenwand zuerst gibt die genauere Kontur, innen zuerst die bessere
    Haftung an Überhängen."""
    seam_position: SeamPosition = "aligned"
    wall_generator: WallGenerator = "arachne"
    """Vorgabe ist ``arachne``: es trifft schmale Stege, die auf keine ganze
    Zahl von Bahnen aufgehen, statt eine Lücke zu lassen (§2.4)."""
    precise_outer_wall: bool = False
    """Rechnet die Außenwand auf das Sollmaß statt auf die Bahnmitte. Kostet
    etwas Zeit und ist überall dort richtig, wo ein Maß eingehalten werden
    muss — also bei Passungen."""
    ironing: bool = False
    """Bügelt die oberste Fläche nach. Für Sicht- und Gleitflächen; sonst
    kostet es nur Zeit."""


@dataclass(frozen=True, slots=True)
class InfillSettings:
    """Füllung. ``density`` ist ein Anteil, 0.15 sind 15 Prozent."""

    density: float = 0.15
    pattern: InfillPattern = "grid"
    angle: float = 45.0
    """Grad zur X-Achse."""


@dataclass(frozen=True, slots=True)
class TemperatureSettings:
    """Grad Celsius. ``chamber`` bleibt 0, wo der Drucker keine Kammer hat."""

    nozzle: int = 210
    nozzle_first_layer: int = 215
    bed: int = 60
    bed_first_layer: int = 60
    chamber: int = 0


@dataclass(frozen=True, slots=True)
class CoolingSettings:
    """Kühlung. ``fan_speed`` ist ein Anteil, 1.0 heißt volle Drehzahl."""

    fan_speed: float = 1.0
    bridge_fan_speed: float = 1.0
    disable_first_layers: int = 1
    """So viele erste Schichten laufen ohne Lüfter — sonst löst sich das Teil."""
    minimum_layer_time: float = 8.0
    """Sekunden. Kürzere Schichten werden gebremst, damit sie erstarren."""


@dataclass(frozen=True, slots=True)
class SpeedSettings:
    """Millimeter je Sekunde."""

    outer_wall: float = 40.0
    inner_wall: float = 60.0
    infill: float = 80.0
    top_surface: float = 40.0
    first_layer: float = 20.0
    travel: float = 150.0
    bridge: float = 25.0
    """Über einer Lücke trägt nichts von unten — langsam gefahren hängt die
    Bahn weniger durch."""
    acceleration: float = 8000.0
    """mm/s². Was die Maschine kann, ist nicht immer, was das Teil verträgt:
    hohe Beschleunigung schwingt die Kontur aus, und das kostet genau die
    Zehntelmillimeter, auf die eine Passung gerechnet ist."""
    outer_wall_acceleration: float = 5000.0
    """Für die Bahn, die man sieht und misst, gesondert und niedriger."""


@dataclass(frozen=True, slots=True)
class SupportSettings:
    """Stützen. ``style='none'`` schaltet sie ab, ohne die Werte zu verlieren."""

    style: SupportStyle = "none"
    placement: SupportPlacement = "everywhere"
    threshold_angle: float = 50.0
    """Grad gegen die Senkrechte, ab dem gestützt wird."""
    z_gap: float = 0.2
    xy_gap: float = 0.5
    density: float = 0.15
    interface_layers: int = 2


@dataclass(frozen=True, slots=True)
class AdhesionSettings:
    """Was das Teil auf der Platte hält."""

    kind: AdhesionType = "skirt"
    skirt_loops: int = 2
    skirt_distance: float = 3.0
    brim_width: float = 5.0
    raft_layers: int = 3


@dataclass(frozen=True, slots=True)
class RetractionSettings:
    """Rückzug gegen Fäden. Millimeter und mm/s."""

    length: float = 0.8
    speed: float = 35.0
    z_hop: float = 0.2
    wipe: bool = True
    avoid_crossing_walls: bool = True
    """Fahrwege um Wände herumführen, statt über offene Flächen zu ziehen.

    Der Rückzug allein reicht nicht: eine Düse, die über einen Hohlraum fährt,
    tropft auch ohne Druck nach, und der Faden fällt hinein statt sich am
    nächsten Rand abzustreifen. Der Umweg kostet Zeit; einen Becher voller
    Fäden kostet er nicht."""


@dataclass(frozen=True, slots=True)
class FilamentSettings:
    """Was im Slicer am Filament hängt — inklusive der Farbe (§20, §29)."""

    diameter: float = 1.75
    density: float = 1.24
    """g/cm³ — geht in Gewicht und Kostenschätzung."""
    flow_ratio: float = 1.0
    colour: str = "#4A90D9"
    """Als ``#RRGGBB``. Reicht bis in die 3MF-Farbgruppen durch."""
    cost_per_kg: float = 0.0
    """0 heißt unbekannt, nicht kostenlos — die Kostenschätzung schweigt dann."""
    max_flow: float = 12.0
    """Wie viel Material die Düse je Sekunde aufschmelzen kann, in mm³/s.

    Die Grenze, an der Schichthöhe, Bahnbreite und Geschwindigkeit
    zusammenlaufen: darüber fördert der Antrieb mehr, als das Hotend flüssig
    bekommt, und die Bahn wird dünner als gerechnet. Ein Wert je Material,
    denn TPU braucht ein Vielfaches der Zeit von PLA.
    """


@dataclass(frozen=True, slots=True)
class PrintSettings:
    """Alle Druckeinstellungen an einer Stelle (§29).

    Der Slicer bekommt sie geschrieben und führt sie aus; er wird nicht mehr
    von Hand bedient. Was hier fehlt, bleibt beim Slicer-Grundprofil stehen —
    dieses Modell überschreibt, es ersetzt nicht.
    """

    id: str = "standard"
    title: str = "Standard"
    quality: QualityPreset = "standard"
    layers: LayerSettings = field(default_factory=LayerSettings)
    shell: ShellSettings = field(default_factory=ShellSettings)
    infill: InfillSettings = field(default_factory=InfillSettings)
    temperature: TemperatureSettings = field(default_factory=TemperatureSettings)
    cooling: CoolingSettings = field(default_factory=CoolingSettings)
    speed: SpeedSettings = field(default_factory=SpeedSettings)
    support: SupportSettings = field(default_factory=SupportSettings)
    adhesion: AdhesionSettings = field(default_factory=AdhesionSettings)
    retraction: RetractionSettings = field(default_factory=RetractionSettings)
    filament: FilamentSettings = field(default_factory=FilamentSettings)

    @property
    def wall_thickness(self) -> float:
        """Was die Wände am Ende messen — die Zahl, gegen die eine Konstruktion
        geprüft wird."""
        return self.shell.wall_count * self.layers.line_width


@dataclass(frozen=True, slots=True)
class SettingAdvice:
    """Eine Einstellung, die die Geometrie selbst verlangt (§28.2).

    Ein Vorschlag trägt seinen Grund mit: eine Zahl ohne Begründung ist im
    Zweifel schlechter als die Vorgabe, weil niemand sie nachprüfen kann.
    """

    path: str
    """Punktpfad ins Modell, etwa ``support.style``."""
    value: object
    was: object
    reason: TranslatableText | str
    severity: Severity = "info"


# --- Befunde und Prüfbericht ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class Finding:
    """Ein Eintrag des Prüfberichts (§17.3).

    Operationen geben Befunde zurück statt zu protokollieren — der Kern
    entscheidet, was Prüfbericht, Steckbrief und Statusleiste erreicht.
    """

    code: str
    """Stabiler Bezeichner wie ``ingest.small_components`` — testbar,
    übersetzbar."""
    severity: Severity
    message: TranslatableText | str
    object_id: ObjectId | None = None
    op_id: OpId | None = None
    feature_ids: tuple[FeatureId, ...] = ()
    values: Mapping[str, float | str] = field(default_factory=dict)
    location: Vec3 | None = None
    """Wohin die Kamera fliegt, wenn die Warnung angeklickt wird (§18.4)."""
    source: MetricSource = "internal"


@dataclass(frozen=True, slots=True)
class Report:
    """Befunde aus Einlesen, Operationen und Prüfungen (§17.3)."""

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


# --- Szene ---------------------------------------------------------------------


@dataclass(slots=True)
class Scene:
    """Der ausgewertete Zustand: das Ergebnis aus Stapel + Quellen +
    Parametern + Profilen."""

    objects: dict[ObjectId, SceneObject] = field(default_factory=dict)
    parameters: dict[ParameterName, Parameter] = field(default_factory=dict)
    fits: list[Fit] = field(default_factory=list)
    profile: Profile | None = None
    report: Report = field(default_factory=Report)


# --- Operationskontext ----------------------------------------------------------

ProgressFn = Callable[[float, str], None]
"""``(fraction, text) -> None``. Oft genug gemeldet, um ehrlich zu
bleiben (§2.8)."""

AskFn = Callable[[str, list[str]], str]
"""``(question, choices) -> chosen``. Der einzige Weg, auf dem der Kern
fragt (Leitprinzip 6)."""


@runtime_checkable
class CancelToken(Protocol):
    """Kooperativer Abbruch. Lange Operationen fragen ihn regelmäßig ab (§15.6)."""

    @property
    def is_cancelled(self) -> bool: ...

    def raise_if_cancelled(self) -> None:
        """Wirft ``OperationCancelled``, wenn der Abbruch verlangt wurde."""


class BaseParams:
    """Die Basis jedes validierten Parametersatzes einer Operation (§10).

    Das Schema — Grenzen, Einheiten, Vorgaben und die Vorderseiten-Zuordnung
    aus §2.4 — wird einmal aus der Deklaration abgeleitet und validiert Dialog,
    Kommandozeile und Agentenaufruf gleichermaßen.
    """

    __slots__ = ()

    @classmethod
    def spec(cls) -> tuple[ParamSpec, ...]:
        """Das Parameterschema dieses Satzes. Trägt das Register ein."""
        return getattr(cls, "__param_spec__", ())

    @classmethod
    def fields(cls) -> tuple[Any, ...]:
        """Die Dataclass-Felder, für Code, der einen Satz aus einem anderen baut.

        Die Baustein-Operationen tun genau das (§24.1): die Parameter eines
        Bausteins plus eine Platzierung werden ein Schema, und der Neuaufbau
        braucht die Deklarationen, nicht nur das abgeleitete Schema.
        """
        import dataclasses

        return tuple(dataclasses.fields(cls))  # type: ignore[arg-type]

    def as_dict(self) -> dict[str, Any]:
        """Serialisierbare Form, wie sie im Op-Stapel liegt."""
        return {name: getattr(self, name) for name in (spec.name for spec in self.spec())}


ParamKind = Literal[
    "float", "int", "bool", "str", "enum", "object", "feature", "part", "source", "sketch"
]
"""``sketch`` trägt eine gezeichnete Skizze als JSON-Text (§30.1) — gedacht für
den Skizzeneditor; bis er da ist, zeigt der Dialog ein Textfeld. Der Agent
bekommt diesen Parameter nicht: Grundformen statt roher Punktlisten (§26)."""
ParamPlacement = Literal["front", "advanced"]
"""Vorderseite oder „Weitere Einstellungen" — die gestufte Tiefe aus §2.4."""


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """Ein Eintrag eines Parameterschemas."""

    name: str
    kind: ParamKind
    title: TranslatableText | str
    default: Any = None
    required: bool = False
    """True, wenn es keine Vorgabe gibt und der Aufrufer einen Wert
    liefern muss."""
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()
    placement: ParamPlacement = "front"
    doc: TranslatableText | str | None = None


@runtime_checkable
class SourceAccess(Protocol):
    """Lesezugriff auf die Quellen des Projekts (§16.1).

    Eine bewusste Ergänzung zum Vertrag aus §9: die ``load``-Operation muss
    eine Datei lesen, und Bytes in den Operationsparametern würden Geometrie
    in den Stapel ziehen. Der Zugriff bleibt lesend und läuft über den
    Kontext wie alles andere.
    """

    def read(self, source_id: SourceId) -> bytes: ...

    def describe(self, source_id: SourceId) -> Source: ...


@dataclass(slots=True)
class OpContext:
    """Alles, was eine Operation sehen und benutzen darf. Nichts Globales,
    keine Dialoge."""

    scene: Scene
    """Nur lesend. Operationen erzeugen Objekte, sie ändern keine."""
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
    """Welche Rückfallstufe eine Boolesche Operation gelöst hat (§17.2)."""

    strategy: SolverStage
    attempted: tuple[SolverStage, ...] = ()
    seed: int | None = None
    note: TranslatableText | str | None = None


@dataclass(slots=True)
class OpResult:
    """Was eine Operation zurückgibt. Nie eine veränderte Eingabe."""

    outputs: list[SceneObject]
    solver: SolverInfo | None = None
    findings: list[Finding] = field(default_factory=list)
    transform: Transform | None = None
    """Die starre Bewegung, die diese Operation ausgeführt hat — wenn sie
    eine war.

    Nur Transformations-Operationen füllen das Feld, und nur sie können es:
    die Operation weiß, was sie mit dem Körper getan hat, während die
    Merkmalszuordnung danach es aus dem Ergebnis zurückraten müsste (§21.2).
    Mit der Matrix überleben die alten Bezeichner eine Drehung; ohne sie
    sieht eine gedrehte Platte aus wie eine andere Platte."""


OpFn = Callable[[OpContext], OpResult]


# --- Stapel, Transaktionen, Dokument ---------------------------------------------


@dataclass(frozen=True, slots=True)
class Origin:
    """Wer eine Transaktion erzeugt hat, und unter welchen Bedingungen (§26.4)."""

    by: Authorship
    model: str | None = None
    prompt_version: str | None = None
    rules_version: str | None = None
    temperature: float | None = None


@dataclass(frozen=True, slots=True)
class Operation:
    """Ein Eintrag des Stapels (§12). ``inputs``/``outputs`` bilden den DAG."""

    id: OpId
    op: str
    inputs: tuple[ObjectId, ...] = ()
    outputs: tuple[ObjectId, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    solver: SolverInfo | None = None
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentState:
    """Eine Seite einer Dokumentänderung — nur die betroffenen Felder.

    ``None`` heißt „dieses Feld war nicht beteiligt", nicht „leer". Bei den
    Parametern steht ``None`` als *Wert* dagegen für „gab es zu diesem
    Zeitpunkt nicht": so wird aus einem Undo, das einen neu angelegten
    Parameter zurücknimmt, ein Löschen und keine Null.
    """

    parameters: Mapping[ParameterName, Parameter | None] | None = None
    fits: tuple[Fit, ...] | None = None
    printer: str | None = None
    material: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentChange:
    """Was eine Transaktion außerhalb des Stapels geändert hat (§15.5).

    Parameter, Passungen, Drucker und Material sind keine Operationen und
    standen deshalb lange außerhalb des Undo — eine gedrehte Zahl ließ sich
    nicht zurücknehmen, und ein angenommener Agentenvorschlag ging nur zur
    Hälfte zurück, obwohl Regel 16 ihn ganz verlangt.

    Die Transaktion trägt jetzt beide Seiten: ``before`` legt ein Undo zurück,
    ``after`` wiederholt ein Redo. Zwei Momentaufnahmen statt einer Liste von
    Einzelschritten, weil dieselbe Funktion dann beide Richtungen bedient.

    Was hier hineingehört, entscheidet eine Frage: ändert es, was die
    Auswertung rechnet? Drucker und Material tun das über Bauraum und
    Toleranzverweise (§12), Parameter über die Ausdrücke (§13), Passungen über
    die Prüfung (§14). Die Druckeinstellungen tun es nicht — sie reisen zum
    Slicer und stehen darum nicht im Verlauf.
    """

    before: DocumentState = DocumentState()
    after: DocumentState = DocumentState()


@dataclass(frozen=True, slots=True)
class Transaction:
    """Eine Gruppe von Operationen, die gemeinsam zurückgenommen wird (§15.5)."""

    id: TransactionId
    title: TranslatableText | str
    ops: tuple[OpId, ...]
    origin: Origin = Origin(by="user")
    changes: DocumentChange | None = None
    """Was die Transaktion neben ihren Operationen geändert hat, oder None."""


@dataclass(frozen=True, slots=True)
class ChatEntry:
    """Ein Gesprächsbeitrag, gekoppelt an das, was er geändert hat (§26.3).

    Die Kopplung ist der Punkt: ein Beitrag nennt die Transaktion, die er
    erzeugt hat, und wird sie zurückgenommen, gilt der Beitrag als verworfen.
    Ohne das argumentiert der Agent nach jedem Undo mit einem Zustand, den es
    nicht mehr gibt.

    Ob ein Beitrag verworfen ist, wird nicht gespeichert — es folgt daraus, ob
    seine Transaktion noch im Dokument steht; ein Redo holt ihn so von selbst
    zurück.
    """

    id: str
    role: ChatRole
    text: str
    transaction_id: TransactionId | None = None
    origin: Origin | None = None
    """Gefüllt bei Agentenbeiträgen: Modell, Prompt- und Regelversion,
    Temperatur (§26.4)."""


@dataclass(frozen=True, slots=True)
class SourceOrigin:
    """Woher ein importiertes Modell kam, und unter welcher Lizenz (§16.3)."""

    url: str | None = None
    title: str | None = None
    author: str | None = None
    licence: str | None = None
    retrieved: str | None = None
    prompt: str | None = None
    """Wonach gefragt wurde, als die Quelle erzeugt wurde (§27, Säule B)."""
    seed: int | None = None
    """Der Startwert, mit dem die Erzeugung lief (§11.3)."""


@dataclass(frozen=True, slots=True)
class IngestInfo:
    """Was die Eingangsstufe mit einer Quelle getan hat (§17.1)."""

    unit: str = "mm"
    scale: float = 1.0
    welded: bool = False
    removed_triangles: int = 0
    components: int = 1


@dataclass(frozen=True, slots=True)
class Source:
    """Ein eingebettetes oder verknüpftes Eingangsnetz. Pfade sind immer
    relativ (§32)."""

    id: SourceId
    kind: SourceKind
    path: str
    sha256: str
    embedded: bool = True
    """Eingebettet ist die Vorgabe fürs Weitergeben eines Projekts (§16.1);
    verknüpft bleibt relativ."""
    ingest: IngestInfo = IngestInfo()
    origin: SourceOrigin | None = None


@dataclass(slots=True)
class Document:
    """Das gespeicherte Projekt: Stapel, Parameter, Passungen, Transaktionen,
    Quellen (§12).

    Die Szene ist, was die Auswertung dieses Dokuments erzeugt — das Dokument
    ist die Wahrheit, die Szene das Ergebnis.
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
    chat: list[ChatEntry] = field(default_factory=list)
    """Das Gespräch, das zu diesem Stapel geführt hat (§26.3). Mit dem Projekt
    gespeichert: ein Container ist ein Fehlerbericht (§16.2), und ein halber
    Fehlerbericht ist einer ohne den Satz, der die Operation ausgelöst hat."""
    print_settings: PrintSettings | None = None
    """Womit dieses Projekt gedruckt wird (§29).

    Beim Projekt und nicht bei der Anwendung, weil es zum Teil gehört und
    nicht zum Rechner: eine Dichtung aus TPU bleibt eine Dichtung aus TPU,
    auch wenn dazwischen etwas anderes gedruckt wurde. ``None`` heißt: noch
    nichts eingestellt, es gilt die Auflösung aus Stufe, Material und Drucker.
    """


# --- Schichtanalyse (§22) ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LayerInfo:
    """Kennzahlen einer Schnittebene."""

    z: float
    contours: tuple[Polygon, ...]
    area: float
    overhang_area: float
    islands: tuple[Polygon, ...]
    min_width: float
    overhangs: tuple[Polygon, ...] = ()
    """*Wo* die ungestützte Fläche dieser Schicht liegt, nicht nur wie viel.

    Aufgehoben, weil Stützkarte (§18.4) und Schichtvorschau (§18.10) auf die
    Stelle zeigen müssen — sie aus den Konturen neu zu rechnen wäre dieselbe
    Arbeit zweimal."""
    bridge_width: float = 0.0
    """Die längste freie Spannweite dieser Schicht in Millimetern (§22.2).

    Gemessen wurde sie schon immer; sie kam nur nie hier an. Genau diese Zahl
    unterscheidet einen Überhang, der sich selbst trägt, von einer Decke, die
    quer durch die Luft spannt — und dass niemand sie las, hat einen Satz
    Behälter gekostet, deren Ringschulter der Slicer mit 24 mm freien Bahnen
    überspannte."""


@dataclass(frozen=True, slots=True)
class SliceResult:
    """Ergebnis des Analyse-Schneiders. Seine Zahlen werden nie mit G-Code
    vermischt (§22.5)."""

    layers: tuple[LayerInfo, ...]
    support_volume: float
    first_layer_area: float
    source: MetricSource = "internal"


# --- Skizzen (§30.1) -----------------------------------------------------------

SketchElementKind = Literal["point", "line", "arc", "circle", "spline"]
SketchConstraintKind = Literal[
    "distance",
    "coincident",
    "horizontal",
    "vertical",
    "parallel",
    "perpendicular",
    "tangent",
    "symmetric",
    "fixed",
    "reference",
]


@dataclass(frozen=True, slots=True)
class SketchElement:
    """Ein Element einer Skizze. ``points`` trägt je nach ``kind``:

    ``point`` einen Punkt, ``line`` Anfang und Ende, ``circle`` Mittelpunkt und
    einen Punkt auf dem Rand, ``arc`` Mittelpunkt, Anfang und Ende — der Bogen
    läuft **gegen den Uhrzeigersinn** von Anfang nach Ende. Damit sind alle
    Freiheitsgrade Punktkoordinaten, und der Solver kennt genau eine Sorte
    Variable.

    ``spline`` ist die einzige Art ohne feste Punktzahl: er läuft durch so
    viele, wie jemand gesetzt hat, mindestens zwei. Die Invariante darüber
    bleibt unberührt — auch seine Punkte sind Punkte."""

    kind: SketchElementKind
    points: tuple[Point2, ...]
    construction: bool = False
    """Hilfsgeometrie: trägt Bedingungen, bildet aber kein Profil (§30.1).

    Eine Mittellinie, an der zwei Bohrungen symmetrisch hängen, soll nicht als
    Kante im extrudierten Körper landen. In jedem CAD ist das eine eigene
    Sorte Linie; hier ist es ein Kennzeichen an derselben, denn für den Solver
    ist sie dieselbe Geometrie — nur die Profilbildung übergeht sie."""


@dataclass(frozen=True, slots=True)
class SketchConstraint:
    """Eine Zwangsbedingung. ``targets`` sind Punktindizes über die flache
    Punktliste der Skizze — Elemente der Reihe nach, Punkte je Element der
    Reihe nach. ``value`` ist ein Ausdruck der Parametergrammatik (§13) und
    darf Projektparameter lesen; nur ein Maß (``distance``) trägt einen."""

    kind: SketchConstraintKind
    targets: tuple[int, ...]
    value: str = ""


@dataclass(frozen=True, slots=True)
class Sketch:
    """Eine 2D-Skizze auf einer Ebene (§30.1).

    ``plane`` ist ``plane:xy``, ``plane:xz``, ``plane:yz`` oder
    ``feature:<id>`` für eine erkannte planare Fläche."""

    plane: str
    elements: tuple[SketchElement, ...]
    constraints: tuple[SketchConstraint, ...] = ()


@dataclass(frozen=True, slots=True)
class PlaneFrame:
    """Wohin eine Skizzenebene im Raum zeigt (§30.1).

    Der Ursprung ist der Nullpunkt der Zeichnung, ``x_axis`` und ``y_axis``
    sind ihre beiden Richtungen, ``normal`` steht senkrecht darauf und ist die,
    in die extrudiert wird. Alle drei sind Einheitsvektoren und rechtshändig.

    Bei den drei Hauptebenen steht das fest. Bei ``feature:<id>`` wird der
    Rahmen aus der Fläche gerechnet — siehe ``app.core.sketch.planes``."""

    origin: Vec3
    x_axis: Vec3
    y_axis: Vec3
    normal: Vec3


@dataclass(frozen=True, slots=True)
class SolvedSketch:
    """Das Ergebnis des Solvers: dieselben Elemente mit gelösten Koordinaten.

    ``free_dof`` zählt die verbleibenden Freiheitsgrade — unterbestimmt ist
    kein Fehler, sondern ein Befund (§30.1). ``max_residual`` ist der größte
    verbliebene Restfehler; läge er über der Toleranz, hätte der Solver
    angehalten statt zu liefern."""

    elements: tuple[SketchElement, ...]
    free_dof: int
    max_residual: float


# --- Weitere feste Verträge ------------------------------------------------------


@dataclass(slots=True)
class PartResult:
    """Was ein Baustein zurückgibt: Geometrie plus benannte
    Provenienz-Merkmale (§24.1)."""

    mesh: Mesh
    features: dict[FeatureId, Feature] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)


PartFn = Callable[[BaseParams], PartResult]


class MeshBackend(Protocol):
    """Mesh-Erzeugung, lokal oder gehostet — derselbe Aufruf so oder so (§27).

    Kennt nur Text und Bild: kein Nutzercode, keine Dateipfade, kein Zustand.
    """

    def text_to_mesh(self, prompt: str, seed: int | None = None) -> Mesh: ...

    def image_to_mesh(self, image: bytes, seed: int | None = None) -> Mesh: ...


class LLMBackend(Protocol):
    """Cloud- oder lokales Modell hinter einer Schnittstelle (§27)."""

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
    """Ein Schritt der Format-Migrationskette (§16.2). Schritte werden nie
    zusammengefasst."""

    @property
    def from_version(self) -> int: ...

    @property
    def to_version(self) -> int: ...

    def apply(self, data: dict[str, Any]) -> dict[str, Any]: ...
