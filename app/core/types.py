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

FeatureKind = Literal[
    "hole", "face", "edge_loop", "pin", "cone", "sphere", "torus", "thread", "fillet"
]
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
SourceKind = Literal["import", "generated", "part", "image"]
"""``image`` ist eine Quelle, die nie ein Körper wird: das Graustufenbild
eines Reliefs (§25, ``displace_image``). Es reist eingebettet wie ein Modell,
bekommt aber keine load-Operation — es gehört einer Operation als Wert."""

SolverStage = Literal["direct", "welded", "jittered", "voxel"]
"""Die Stufen der Booleschen Rückfallkette (§17.2), in ihrer Reihenfolge.

Die Kette als Wert steht in :data:`app.core.geom.boolean.FULL_CHAIN`, neben
``DRAFT_CHAIN`` und der Stelle, die sie durchläuft. Hier stand sie bis zum
24.08.2026 ein zweites Mal als ``SOLVER_CHAIN`` — mit identischem Inhalt, von
niemandem gelesen, und damit ein dritter Ort für dieselbe Reihenfolge neben
diesem Literal und ``FULL_CHAIN``.
"""

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
    recognised: bool = True
    """Ob die Erkennung dieses Merkmal an seiner Stelle **auch** findet.

    **Warum das nicht dasselbe ist wie eine erkennbare Art.** Ein Baustein
    benennt seine Bohrungen beim Bauen (§24.1); die Erkennung sieht sie nie —
    an einer Einpressbuchse in einem Gehäuseboden findet sie null von drei.
    Beim nächsten Schritt wurden sie trotzdem an ihr gemessen, weil ``hole``
    in ``DETECTABLE_KINDS`` steht, fanden keinen Partner und verwaisten. Ein
    Gewinde aus demselben Baustein reiste dagegen ungeprüft mit, weil
    ``thread`` dort nicht steht.

    Die Unterscheidung hing damit daran, ob zufällig eine *andere* Art denselben
    Namen trägt, und nicht an der Sache. Dieses Feld beantwortet die Frage, die
    gemeint war: nicht „ist die Art erkennbar", sondern „wurde **dieses**
    Merkmal je erkannt".

    **Die Vorgabe ist ``True``, und zwar mit Absicht:** Ein erkanntes Merkmal
    ist per Definition erkannt, und alles, was ohne Angabe entsteht, soll sich
    verhalten wie bisher. Abgewichen wird nur dort, wo es besser bekannt ist —
    beim Einhängen eines erzeugten Merkmals, das die frische Erkennung an
    seiner Stelle nicht wiederfindet.
    """
    created_by: OpId | None = None
    """Welcher Schritt dieses Merkmal erzeugt hat — ``None`` bei erkannten.

    **Die Antwort auf die eine Handlung, die §21.2 jedem erzeugten Merkmal
    zusagt:** den Schritt zu ändern, der es erzeugt hat. Ohne dieses Feld gab
    es sie nirgends. ``provenance`` sagt nur *dass* ein Merkmal erzeugt wurde;
    das ID-Präfix ``op4.pin_1``, das §21.2 als Beispiel führt, wird im
    Produktivcode nirgends vergeben und nirgends gelesen — es steht allein in
    Tests, die es von Hand hinschreiben. Und :attr:`SceneObject.created_by`
    beantwortet eine andere Frage: Es wird bei **jeder** Operation neu gesetzt,
    die das Objekt ausgibt, und zeigt damit auf die zuletzt beteiligte statt
    auf die erzeugende.

    Gesetzt wird es **einmal**, wenn das Merkmal entsteht, und danach nie
    wieder — sonst hätte es denselben Fehler wie das Feld am Objekt. Ein
    erkanntes Merkmal behält ``None``, und der Eintrag „diesen Schritt ändern"
    entfällt dort ersatzlos: Es hat keinen Erzeuger, und ein Menüeintrag, der
    ins Leere führt, ist schlechter als keiner (§21.2)."""


@dataclass(frozen=True, slots=True)
class MaterialSlot:
    """Ein Filamentslot eines Objekts (§20)."""

    index: int
    name: TranslatableText | str
    """Wie das Filament heißt — wie bei :attr:`SceneObject.name` **beides**.

    Hier stand ``str``, und der Typ hat gelogen: ``assign_slot`` und *Malen*
    reichen ``params.name`` unverändert weiter, und die Auswertung macht daraus
    ein :class:`TranslatableText`, sobald die Operation den Parameter als
    Message-ID vermerkt (``Operation.translatable``, §4.1) — so tun es die
    mitgelieferten Beispiele. Der Ergebnis-Cache legte den Wert daraufhin roh
    in ``json.dumps``, bekam einen ``TypeError`` und verwarf den Eintrag der
    **ganzen** Auswertung; ``scene/cache.py`` erzählt den Fall.

    Wer den Namen anzeigt oder in eine Datei schreibt, nimmt ``str(...)`` —
    das löst die Übersetzung in der eingestellten Sprache auf. Wer ihn
    **ablegt**, nimmt ``_name_to_data``: Die Übersetzung wechselt mit der
    Sprache, die Message-ID nicht.
    """
    colour: tuple[float, float, float] | None = None
    material: str | None = None


@dataclass(slots=True)
class SceneObject:
    """Ein Körper in der Szene."""

    id: ObjectId
    name: TranslatableText | str
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

    @property
    def smallest_printable_volume(self) -> float:
        """Das kleinste Volumen, das dieser Drucker überhaupt hinterlässt — ein
        Stück Extrusionsbahn von einer Bahnbreite Länge.

        Die Grenze zwischen „hat etwas getan" und „hat nichts getan". Ein
        Rechenepsilon taugt dafür nicht: eine Bohrung, die den Körper nur
        streift, trägt ein Tausendstel Kubikmillimeter ab — das ist mehr als
        ``EPS_GEOM`` und trotzdem nichts, was jemand je zu sehen bekommt.
        Gemessen an der Düse und nicht an einer Zahl im Code, weil dieselbe
        Geometrie an einer 0,8er Düse eine andere Antwort verdient (Regel 7,
        §38).
        """
        return self.printer.extrusion_width**2 * self.printer.layer_height

    @property
    def smallest_first_layer(self) -> float:
        """Die kleinste Aufstandsfläche, auf der ein Teil stehen kann — zehn
        Extrusionsbahnen im Quadrat, bei einer 0,4er Düse also 4,2 auf 4,2 mm.

        Gebraucht von der Orientierungssuche (§22.2). Gemessen an einer
        Verbinderstange von 157 mm: die Suche stellte sie diagonal auf
        **0,1 mm²** erste Schicht, weil diese Lage 0,6 mm³ Stützmaterial
        braucht statt 11,1 — ihre Flanken stehen 47° zur Waagerechten und
        tragen sich selbst. Der Vergleich war richtig, nur fehlte ihm die
        Bedingung, dass eine Lage stehen muss, bevor sie sparen darf.

        **Warum zehn und nicht vier.** Vier Bahnen wären das Wenigste, was ein
        Slicer als geschlossene Insel legt — als Grenze für „kann stehen" ist
        das zu tief: Im Kandidatenfeld derselben Stange kam die diagonale Lage
        damit auf 4,5 mm² und gewann weiter. Dasselbe Feld zeigt aber eine
        breite Lücke: die achtzehn Lagen, die auf einer Fläche liegen, tragen
        76 bis 2765 mm², die auf einer Kante stehenden 0,06 bis 4,5. Zehn
        Bahnen liegen mit 17,6 mm² dazwischen, mit Abstand nach beiden Seiten.
        Eine gewählte Zahl also, aber eine mit Messung dahinter — und keine, die
        auf ein Zehntel ankommt.

        Aus dem Profil und nicht als Zahl im Code (Regel 7): an einer 0,8er
        Düse ist dieselbe Fläche eine andere. Ein Teil, dessen **jede** Lage
        darunter bleibt, wird davon nicht abgelehnt — dann tragen alle
        Kandidaten dieselbe Antwort, und es bleibt beim alten Vergleich.
        """
        return (10.0 * self.printer.extrusion_width) ** 2


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
class SlotOverride:
    """Was für einen Materialslot anders gilt als für den Rest (§20, §29).

    Vier Spulen bedeuten nicht vier Farben desselben Materials: Ein Schriftzug
    in PLA auf einem Gehäuse aus PETG fährt 210 Grad statt 250, und wer beide
    mit einem Satz Werte druckt, bekommt entweder eine verkohlte Schrift oder
    ein Gehäuse, das nicht hält.

    **Übersteuerbar ist, was an der Spule hängt** — Temperaturen, Kühlung,
    Rückzug, Materialkennwerte. Geometrie steht ausdrücklich nicht hier:
    Wandstärke und Schichthöhe sind Eigenschaften des *Teils*, und ein Feld,
    das beides vermischte, machte aus einem zweifarbigen Teil zwei
    verschiedene Teile (Entscheidung Robert, 26.08.2026).

    **Gruppenweise, nicht feldweise.** Wer die Düsentemperatur ändern will,
    setzt die ganze ``temperature``-Gruppe — vorbelegt mit den Projektwerten,
    ein Wert anders. Das ist gröber als einzelne Felder und dafür ehrlich:
    ``None`` heißt „gilt wie im Projekt", und diese Frage muss die Oberfläche
    beantworten können, ohne zwanzig Häkchen zu führen.

    Die Reihenfolge der Einträge in :attr:`PrintSettings.slot_overrides` ist
    die der Slots und damit die Extruderbelegung — dieselbe Regel wie bei
    :attr:`PrintSettings.slot_profiles` nebenan.
    """

    name: TranslatableText | str = ""
    """Zu welchem Filament das gehört — zusammen mit :attr:`colour` der Schlüssel.

    **Nicht die Position.** Sie stand hier zuerst, und sie war falsch: Was der
    Dialog zeigt, ist die Zusammenlegung der gewählten Platten; gedruckt wird
    Platte für Platte, und jede legt für sich zusammen. Bei Rot auf Platte 1
    und Weiß+Rot auf Platte 2 steht [Rot, Weiß] im Dialog und [Weiß, Rot] im
    Lauf der zweiten — gemessen am 26.08.2026 bekam **Weiß die 210 Grad, die
    für Rot eingestellt waren**, und Rot die 240 des Projekts. Bei den
    Filamentprofilen wandert dabei die Temperatur mit; hier *ist* sie der Wert.

    Derselbe Schlüssel wie in :func:`app.core.export.threemf.merge_slots` —
    zwei Teile in derselben Farbe sind ein Filament, und ein Übersteuerer
    gehört dem Filament, nicht dem Platz in einer Liste.
    """
    colour: tuple[float, float, float] | None = None
    """Die Farbe des Filaments, zweite Hälfte des Schlüssels."""

    temperature: TemperatureSettings | None = None
    cooling: CoolingSettings | None = None
    retraction: RetractionSettings | None = None
    filament: FilamentSettings | None = None

    @property
    def empty(self) -> bool:
        """Ob dieser Slot überhaupt etwas übersteuert."""
        return not any((self.temperature, self.cooling, self.retraction, self.filament))

    @property
    def key(self) -> tuple[TranslatableText | str, tuple[float, float, float] | None]:
        """Der Schlüssel, unter dem dieser Übersteuerer sein Filament findet."""
        return (self.name, self.colour)


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
    slot_overrides: tuple[SlotOverride | None, ...] = ()
    """Was je Materialslot anders gilt als im Projekt (§20).

    Ein Eintrag je Slot, in der Reihenfolge der Slots — die *ist* die
    Extruderbelegung, dieselbe Regel wie bei :attr:`slot_profiles`
    darunter. ``None`` und eine kürzere Liste heißen dasselbe: Für
    diesen Slot gelten die Werte des Projekts.

    Der Filamentkatalog liefert die Vorgabe, das hier schlägt sie —
    dieselben drei Ebenen wie sonst auch (§29).
    """

    slot_profiles: tuple[str, ...] = ()
    """Welches Filamentprofil des Slicers auf welchem Materialslot liegt (§20).

    Ein Eintrag je Slot, in der Reihenfolge der Slots — die *ist* die
    Extruderbelegung. Gespeichert wird der **Name** des Profils, nicht sein
    Pfad: er reist mit dem Projekt und zeigt auf einem zweiten Rechner nicht
    ins Leere (Regel 12).

    Kürzer als die Slotliste zu sein ist erlaubt und der Normalfall: wo nichts
    steht, gilt das Filament der Platte. Ein Gehäuse in Schwarz mit weißer
    Schrift braucht genau einen Eintrag mehr als ein einfarbiges Teil.
    """

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

        **Ein Satz ohne Felder gibt nichts zurück und wirft nicht.** Eine
        Operation darf parameterlos sein — *Objekt löschen* ist es, und ihr
        Parametersatz ist deshalb diese Klasse selbst. ``dataclasses.fields``
        wirft dort ein nacktes ``TypeError`` („must be called with a dataclass
        type or instance"), und das ist auf zwei Weisen falsch: Es ist kein
        ``AppError`` und trägt damit keinen Handlungsvorschlag (Regel 17), und
        es gibt gar nichts zu beheben — kein Parameter *ist* eine gültige
        Antwort, sie heißt leer.
        """
        import dataclasses

        # Gefragt wird nach dem Merkmal und nicht über ``is_dataclass``: dessen
        # ``TypeGuard`` engt die Ja-Seite auf einen Dataclass-Typ ein, und weil
        # diese Klasse selbst keiner ist, hält mypy die Zeile darunter für
        # unerreichbar. Das Merkmal ist dasselbe, nur ohne die Verengung.
        if not hasattr(cls, "__dataclass_fields__"):
            return ()
        return tuple(dataclasses.fields(cls))  # type: ignore[arg-type]

    def as_dict(self) -> dict[str, Any]:
        """Serialisierbare Form, wie sie im Op-Stapel liegt."""
        return {name: getattr(self, name) for name in (spec.name for spec in self.spec())}


ParamKind = Literal[
    "float",
    "int",
    "bool",
    "str",
    "enum",
    "object",
    "feature",
    "part",
    "filament",
    "source",
    "image",
    "sketch",
    "strokes",
    "armature",
]
"""``image`` ist eine Quelle, die ein Bild sein muss: Der Dialog listet nur
Bildquellen und bietet daneben an, eine von der Platte zu holen — ein
``source``-Feld bot dort jede Quelle an, also STLs in einem Feld namens
„Bild", und einen Weg zu einem Bild gab es nicht.

``sketch`` trägt eine gezeichnete Skizze als JSON-Text (§30.1) — gedacht für
den Skizzeneditor; bis er da ist, zeigt der Dialog ein Textfeld. Der Agent
bekommt diesen Parameter nicht: Grundformen statt roher Punktlisten (§26).

``strokes`` trägt eine Liste von Pinselstrichen, ebenfalls als JSON-Text und
aus demselben Grund ohne den Agenten: Ein Strich *ist* eine Koordinate, und
die KI erzeugt keine (Leitprinzip 5). ``armature`` trägt ein Skelett, dessen
Knochen ebenfalls Koordinaten sind. Alle drei unterliegen den fünf Prüfungen
aus :mod:`tests.test_gesture_ops`.

``filament`` ist die Nummer eines Materialslots — im Kern eine Zahl wie
zuvor, in der Oberfläche der Filamentwähler mit Farbfeld, Namen und der
Vorwahl aus :mod:`app.core.knowledge.filaments`. Die Art steht am Parameter
und nicht sein Name in einer Tabelle der Oberfläche: „slot" heißt anderswo
Langloch, und ein Dialog, der Felder am Namen erkennt, färbt irgendwann eine
Schraubenaufnahme ein."""
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
    depends_on: tuple[str, tuple[str | bool, ...]] | None = None
    """Der Parameter, der diesen wirksam macht, und die Werte, bei denen er es tut.

    ``("kind", ("linear",))`` heißt: Dieses Feld wirkt nur, solange *Art* auf
    „linear" steht — sonst übergeht die Operation es. Elf Parameter in fünf
    Operationen sind so gebaut, und keiner sagte es: Wer bei *Kopien in Reihe
    oder Kreis* auf „kreisförmig" stellte, sah *Abstand* und *Richtung X/Y/Z*
    bedienbar dastehen.

    **Im Schema und nicht in der Oberfläche**, weil vier Oberflächen dieselbe
    Auskunft brauchen: Der Dialog graut das Feld aus und sagt warum, das
    Handbuch schreibt die Bedingung in die Parametertabelle, und der Agent soll
    einen Wert nicht setzen, den die Operation gleich verwirft. Als Tabelle in
    ``op_dialog`` hat genau eine davon sie gehabt.

    Die Werte sind Auswahlwerte oder Wahrheitswerte — ein Haken ist ein
    Umschalter wie ein Aufklappmenü, nur mit zwei Ständen."""
    subtractive_on: tuple[str | bool, ...] | None = None
    """Die Werte dieses Parameters, bei denen der Baustein **abträgt** statt
    aufzusetzen (§24).

    ``("bore",)`` am Parameter *Art* heißt: Auf „bore" wird das Werkzeug
    abgezogen, sonst vereinigt. Gebraucht, weil ``PartSpec.subtractive`` eine
    Eigenschaft des **Bausteins** ist und für zwei von ihnen an der falschen
    Stelle sitzt: *Passstift und Passbohrung* und *Schnappverbinder* sind je
    ein Paar, und welche Hälfte gemeint ist, entscheidet ein Parameter.

    Gemessen an einem Klotz von 30 auf 30 auf 20, bevor das hier stand: Die
    Passbohrung rechnete ihr Spiel dazu (``diameter + play``), gab ein
    ``bore``-Merkmal zurück — und setzte **+411,7 mm³** auf, also einen etwas
    dickeren Zapfen als der Zapfen. Beim Schnappverbinder war die „Tasche mit
    der Rastkante" +108,5 mm³.

    **Am Parameter und nicht in einer Tabelle**, aus demselben Grund wie
    :attr:`depends_on`: Dieselbe Auskunft brauchen die Operation (welche
    Boolesche Op), der Registereintrag (ob ein Flächenklick den Baustein
    anbietet) und die Vorschau (welche Farbe) — und sie steht dort, wo die
    Wahl getroffen wird."""


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

    def identity(self, source_id: SourceId) -> str:
        """Was diese Quelle **inhaltlich** ist — für den Cache-Schlüssel (§15).

        Nicht der Bezeichner: Der ist ``src_1``, und zwar in jedem Projekt. Ein
        Schlüssel, der ihn nimmt, hält zwei völlig verschiedene Dateien für
        dieselbe — gefunden am 22.08.2026, als eine Cache-Ebene dazukam, die
        länger lebt als eine Sitzung, und ein Projekt die Geometrie eines
        anderen bekam.
        """


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
    answered: dict[str, Any] = field(default_factory=dict)
    """Parameter, die diese Operation über eine **Rückfrage** entschieden hat
    (§15.7).

    Nur die fragende Operation kann das Feld füllen: Sie weiß, welchen ihrer
    Parameter die Antwort betrifft — die Auswertung sieht nur, *dass* gefragt
    wurde. Der Aufrufer schreibt die Werte danach in den Stapel zurück, wie er
    es mit den Rückfallstufen tut (§17.2).

    Warum das nötig ist: §15.1 macht die Auswertung zu einer reinen Funktion aus
    Stack, Quellen, Parametern, Profilen und Startwerten. Eine Antwort, die nur
    in der Sitzung lebt, wäre ein sechster Eingang — zweimal ausgewertet käme
    zweimal etwas anderes heraus. Gemessen kostete das eine Bauplatte mit 52
    Teilen 99 modale Fenster für 7 Entscheidungen, und mit einem Cache, der
    länger lebt als eine Sitzung, wird daraus stillschweigend eine Annahme."""

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
    translatable: tuple[str, ...] = ()
    """Welche Parameter dieser Operation **Message-IDs** tragen statt Text (§4.1).

    **Warum ein Vermerk und kein anderer Typ im Parameter.** In der Projektdatei
    steht die Message-ID als schlichte Zeichenkette — genau wie bei einem
    Transaktionstitel, wo ``title_translatable`` dasselbe tut. Damit bleibt
    ``operation_hash`` sprachfrei, ohne dass jemand etwas dafür tun muss: Er
    liest ``op``, ``params``, Eingangs-Hashes, Profil, Qualität und Startwert,
    und in ``params`` steht die ID, nicht die Übersetzung. Ein Cache-Schlüssel,
    der von der Anzeigesprache abhinge, wäre derselbe Fehler wie ein
    Dateiname, der es tut.

    **Und warum leer der Normalfall ist.** Ein Name, den ein Nutzer selbst
    getippt hat, ist wörtlich gemeint und wird nie übersetzt. Der Vermerk steht
    nur dort, wo der Text aus dem Code oder aus einem mitgelieferten Beispiel
    kommt — dieselbe Unterscheidung, die ``title_translatable`` seit Format 6
    trifft.
    """
    matches: Mapping[FeatureId, Mapping[str, Any]] = field(default_factory=dict)
    """Antworten auf mehrdeutige Merkmalszuordnungen (§15.7, §21.3).

    **Warum das nicht in ``params`` steht.** ``validate`` wiese einen
    Schlüssel ab, den das Schema der Operation nicht kennt, und richtig so: Das
    hier ist keine Eingabe der Operation, sondern eine festgehaltene Antwort auf
    eine Rückfrage, die *bei* ihr entstand. Der Präzedenzfall steht eine Zeile
    höher — ``seed`` ist ebenfalls ein Wert auf Operationsebene, der eine nicht
    von selbst reproduzierbare Prozedur reproduzierbar macht. Eine
    festgehaltene Antwort tut für eine Rückfrage dasselbe.

    **Gespeichert wird ein geometrischer Fingerabdruck, kein Bezeichner.**
    ``alt → neu`` wäre fragil: Die Erkennung nummeriert beim nächsten Lauf
    womöglich anders, und dann zeigte die gespeicherte Antwort auf ein fremdes
    Merkmal — aus „fragt zu oft" würde „nimmt stillschweigend das falsche", und
    das ist der schlechtere Fehler (Regel 21). Der Abdruck ist lesbares JSON
    (``kind``, ``centre``, ``axis``, ``diameter``) und wird mit derselben
    Rivalenlogik aufgelöst, die die Frage überhaupt erst gestellt hat: Gewinnt
    der Beste nicht mit Abstand, wird wieder gefragt.

    **Und es gehört nicht in den Op-Hash.** Die Zuordnung passiert *nach* dem
    Cache — ``_with_features`` läuft in beiden Zweigen, auch nach einem
    Treffer. Eine Antwort ändert also kein gecachtes Ergebnis, und nach dem
    Antworten rechnet nichts neu; anders als bei der Einheitenrückfrage, die
    ein Parameter ist. Wer das später „zur Sicherheit" in den Hash einträgt,
    macht jede beantwortete Frage zu einer vollständigen Neuberechnung.
    """


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
    edited_ops: Mapping[OpId, Operation] | None = None
    """Je Schrittkennung die vollständige Fassung dieser Seite (§15.4, §15.5).

    Für das nachträgliche Ändern eines Schritts — andere Parameter, andere
    Eingänge, der Zwilling im anderen Rechenkern: Der Schritt behält Kennung
    und Platz, nur seine Fassung wechselt, und die Transaktion trägt beide.
    Ohne dieses Feld schrieben die drei Änderungswege am Verlauf vorbei, und
    ein Strg+Z traf einen anderen Schritt, während der alte Wert
    unwiederbringlich weg war. Seit Format v12 in der Datei."""


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
    highest_transaction: int = 0
    """Die höchste je vergebene Transaktionsnummer — mit ``highest_op`` und
    ``highest_object`` die Wasserlinie der Nummernvergabe (§15.4).

    **Im Dokument und nicht im Verlaufsobjekt**, weil mehr als ein
    Verlaufsobjekt über demselben Dokument schreibt: Trennen, Deckeln und Auto
    Split bauen sich ihr eigenes, und der Redo-Stapel der Sitzung ist für sie
    unsichtbar. Wer nur zählt, was im Dokument steht, vergibt eine
    zurückgenommene Nummer ein zweites Mal — und ein Redo hängt danach eine
    Transaktion ein, deren Kennung inzwischen einer anderen gehört.

    Nur wachsend, nie zurückgesetzt: vergeben ist vergeben, auch nach einem
    Undo. ``0`` heißt „noch nichts vergeben oder Datei ohne dieses Feld"; dann
    zählt der Verlauf aus dem Bestand (siehe
    :meth:`app.core.scene.history.History._highest_transaction_number`).

    **Kein Schritt der Formatkette, und das ist eine Entscheidung.** Das Feld
    ist additiv und optional: Eine ältere Datei hat es nicht, und aus ihrem
    Bestand — Stapel, Transaktionen und die Transaktionsverweise des Chats —
    lässt sich jede Nummer zurückgewinnen, auf die überhaupt noch etwas
    zeigt. Eine neuere Datei bricht ältere Fassungen nicht: Sie überlesen den
    Schlüssel und rechnen aus dem Bestand weiter, also genau so, wie sie es
    immer getan haben. Der Unterschied zu ``title_translatable`` (Schritt
    5 → 6) liegt genau hier — dort trug die Markierung eine Bedeutung, die im
    Bestand nicht steht, und ein Verwerfen hätte den Sinn eines gespeicherten
    Titels verändert. Hier geht nichts verloren als eine Untergrenze, die sich
    neu berechnen lässt.
    """
    highest_op: int = 0
    """Die höchste je vergebene Op-Kennung — dieselbe Wasserlinie für den
    Stapel."""
    highest_object: int = 0
    """Der höchste je vergebene Objektindex (``obj_<n>``)."""


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


SculptTool = Literal["draw", "carve", "smooth", "inflate", "flatten", "pinch"]
"""Die sechs Pinselwerkzeuge (§25, Konzept P16 §7.1). Sechs, nicht sechzig —
Konsistenz vor Vollständigkeit.

Drei davon lassen sich nicht akkumulieren: ``smooth`` mittelt über die
Nachbarschaft, ``inflate`` folgt der Krümmung, ``flatten`` zieht auf eine
Ebene, die es erst aus dem Getroffenen bildet. Alle drei lesen den Zustand,
den die Striche davor hinterlassen haben, und beginnen deshalb eine neue
Etappe."""

#: Werkzeuge, die den Zustand vor sich lesen und deshalb eine Etappe beginnen.
ORDERED_TOOLS: Final[frozenset[str]] = frozenset({"smooth", "inflate", "flatten"})


@dataclass(frozen=True, slots=True)
class Stroke:
    """Ein Pinselstrich (Konzept P16, Entscheidung B).

    **In Weltkoordinaten, nicht auf einem Eckpunkt.** Der Strich merkt sich,
    *wo im Raum* er lag und wie die Fläche dort stand — kein Vertex-Index,
    keine Dreiecksnummer. Damit übersteht er jede Änderung der Vernetzung
    darunter: Dezimieren, Reparieren, eine andere Qualitätsstufe. Präzedenzfall
    ist ``paint_slot``, dessen Klickpunkt aus demselben Grund in
    Weltkoordinaten liegt.

    Was er *nicht* übersteht, ist eine Änderung der **Form** darunter: Dann
    steht er an einer Stelle im Raum, an der keine Fläche mehr ist. Er
    verschwindet dort nicht still, sondern wird gemeldet.
    """

    point: Vec3
    normal: Vec3
    """Die Flächennormale zum Zeitpunkt des Strichs — die Richtung, in die er
    trägt. Aus der Ursprungsform genommen und nicht aus der laufenden, damit
    die Summe vieler Striche eine Näherung bleibt und keine Drift wird."""
    radius: float
    strength: float
    tool: SculptTool = "draw"
    symmetry: int = 0
    """Bitmaske der Ebenen, an denen dieser Strich gespiegelt gemeint war:
    1 = X, 2 = Y, 4 = Z. Am Strich und nicht nur an der Operation, damit sich
    die Symmetrie einer Sitzung nachträglich ändern lässt, ohne dass ältere
    Striche mitwandern."""
    cut: bool = False
    """Erzwingt eine Etappengrenze vor diesem Strich (Entscheidung C).

    Die akkumulierte Auswertung macht Striche kommutativ — zweimal über
    dieselbe Stelle addiert zwei Gewichte auf die Ausgangsfläche, statt den
    zweiten Zug auf das Ergebnis des ersten zu setzen. Wer die exakte
    Reihenfolge braucht, kauft sie sich hier stückweise: Ein gesetzter Schnitt
    kostet einen zusätzlichen Durchgang und gilt nur für diese Stelle, statt
    die ganze Sitzung zu verlangsamen."""


@dataclass(frozen=True, slots=True)
class Bone:
    """Ein Knochen des Skeletts (Konzept P16, Entscheidung I).

    Zwei Punkte und ein Elternteil, mehr nicht. ``head`` sitzt am Gelenk,
    ``tail`` zeigt, wohin der Knochen weist; ein Kind hängt mit seinem Kopf am
    Fuß seines Elternteils, und die Kette daraus ist das Skelett.

    **Keine Gewichte.** Welcher Eckpunkt zu welchem Knochen gehört, wird
    gerechnet und nicht gespeichert: aus dem Abstand zum Knochensegment mit
    einem Abfall darüber. Gespeicherte Gewichte wären ein zweiter
    Dokumentbegriff neben dem Stapel — und beim nächsten Vernetzen darunter
    falsch, ohne dass jemand es merkt.
    """

    name: str
    head: Vec3
    tail: Vec3
    parent: str = ""
    """Name des Elternteils, leer für die Wurzel."""


@dataclass(frozen=True, slots=True)
class Pose:
    """Die Stellung **eines** Knochens: drei Winkel in Grad.

    Eine Pose, keine Animation (§13): Gedruckt wird ein Zustand. Keine
    Zeitachse, keine Interpolation, keine Kurven — das ist der größte
    Streichposten gegenüber einem Animationsprogramm.

    Die Winkel dürfen aus Projektparametern kommen; das ist der Punkt, an dem
    Posing zu Solidon gehört statt zu Blender. ``=@arm_angle`` in einer Pose,
    und die Passung am Sockel rechnet mit.
    """

    bone: str
    angles: Vec3 = (0.0, 0.0, 0.0)


# --- Weitere feste Verträge ------------------------------------------------------


@dataclass(slots=True)
class PartResult:
    """Was ein Baustein zurückgibt: Geometrie plus benannte
    Provenienz-Merkmale (§24.1)."""

    mesh: Mesh
    features: dict[FeatureId, Feature] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)


PartFn = Callable[[BaseParams], PartResult]

HoleValues = Callable[[float], "dict[str, Any]"]
"""Aus dem gemessenen Durchmesser einer Bohrung die Parameter, die dazu passen.

Leer, wo keine Größe passt — die Vorgabe des Schemas bleibt dann stehen. Nie
die nächstbeste (Regel 21): Ein Vorschlag, den niemand hergeleitet hat, sieht
im Dialog genauso aus wie ein gemessener.
"""


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
