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

from app.core.knowledge.rules import OVERHANG_LIMIT_DEGREES
from app.i18n import TranslatableText, _

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

# --- Aufzählungen --------------------------------------------------------------

FeatureKind = Literal[
    "hole",
    "face",
    "edge_loop",
    "pin",
    "cone",
    "sphere",
    "torus",
    "thread",
    "fillet",
    "void",
    "slot",
    "curved_face",
    "pattern",
]
"""Die Arten, die ein Merkmal haben kann.

``curved_face`` ist eine gerundete Seite: ein glatter, nicht ebener Fleck,
den kein anderes Merkmal beansprucht — der Bogen eines D, der Mantel eines o,
die Schwünge eines S. Kein Zylinder, keine Kugel, keine Verrundung, sondern
das, was nach all diesen Einpassungen an gerundeter Oberfläche übrig bleibt
(Robert, 11.09.2026: „bei den Seiten fehlen die gerundeten flächen"). Eine
eigene Art und nicht ``face`` mit Vermerk, weil zwölf Operationen an ``face``
eine Ebene voraussetzen und eine gerundete Seite keine hat. An ihr gehen
Filament (``paint_slot``, ``clear_filament``), Bohren und das Platzieren von
Grundkörpern und Bausteinen; Zeichnen braucht eine Ebene
(``perceive.actions.NOT_APPLICABLE``).

``slot`` ist das Langloch, und es steht hier, weil die Einpassung es nicht
sieht: Sie findet darin zwei Zylinderausschnitte und nennt sie Verrundungen.
Zusammengesetzt wird es am Netz (:mod:`app.core.perceive.slots`), aus den zwei
Bögen und den zwei ebenen Flanken dazwischen — so wie ein Gewinde aus einer
Wendel entsteht und nicht aus einem Fit.

``void`` ist eine geschlossene Innenschale im Material, ein Hohlraum ohne Weg
nach außen. Robert fand am 10.09.2026 acht davon in ``garden-hose-holder.3mf``,
jeder Ø 2 auf 9 mm — die Erkennung nannte sie bis dahin ``hole``, also acht
Bohrungen, die man weder sehen noch bohren kann.

**Unantastbar ist er deshalb nicht.** Der erste Entwurf sperrte ihn ganz und
begründete es damit, kein Werkzeug komme an ihn heran; gemessen ist das
falsch — Versetzen und Entfernen tragen (:data:`geom.prepare_ops.MOVABLE_KINDS`).
Was fehlt, ist das Maß und nicht der Zugang.

**Und ein Fehler ist er nicht immer.** Die Aussparung für einen eingegossenen
Magneten und ein vergessener Negativkörper sind topologisch dieselbe Sache;
welche vorliegt, weiß nur der Kunde. Solidon benennt, was da ist, und urteilt
nicht."""
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


def as_vec3(values: Sequence[float]) -> Vec3:
    """Drei Zahlen als :data:`Vec3` — ohne Prüfung, für schon geprüfte Werte."""
    return (float(values[0]), float(values[1]), float(values[2]))


def vec3_or_none(value: object) -> Vec3 | None:
    """Ein dreikomponentiger Parameterwert, oder ``None``, wenn er keiner ist.

    Der prüfende Bruder von :func:`as_vec3`, für Werte aus einer Projektdatei
    oder einem Agentenaufruf: Was dort steht, ist erst einmal ``object``.

    Beide standen bis zum 04.09.2026 je zweimal im Baum, und alle vier hießen
    ``_vector`` — zwei verschiedene Bedeutungen unter einem Namen in einem
    Paketbaum. Der Zeilenpreis war klein, die Verwechslungsgefahr nicht.
    """
    if not isinstance(value, list | tuple) or len(value) != 3:
        return None
    try:
        return as_vec3(value)
    except TypeError, ValueError:
        return None


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

IDENTITY_FRAME: Transform = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)
"""Ausgangsrahmen eines neu eingelesenen oder erzeugten Körpers."""


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

    @property
    def deflection(self) -> float:
        """Wie weit die Dreiecke der eigenen Vernetzung von der Fläche
        abweichen dürfen, in mm — die Zahl, mit der ``to_mesh()`` ohne Angabe
        tesselliert."""

    def to_mesh(self, *, deflection: float | None = None) -> Any:
        """Die Einbahntür aus §30: Dreiecke aus dem exakten Körper.

        Ohne Angabe die eigene Vernetzung; mit ``deflection`` eine feinere
        oder gröbere, wie der Export sie für das Verfahren des Druckers
        braucht (:attr:`Profile.export_deflection`)."""

    @property
    def solid_count(self) -> int:
        """Wie viele Körper die Form trägt — topologisch gezählt, nicht über
        Dreiecke: Zwei Körper, die sich nur berühren, sind hier zwei.
        """


def kind_of(mesh: Mesh) -> ObjectKind:
    """Welche Sorte Körper das ist. Eine Regel, ein Ort — der Objektbaum zeigt es."""
    return "brep" if isinstance(mesh, BRepBody) else "mesh"


# --- Merkmale und Objekte ------------------------------------------------------


MeasureSource = Literal["native", "facets", "fit", "parameter"]
"""Die tatsächliche Quelle eines Maßwerts, unabhängig von der Merkmalherkunft."""

MeasureState = Literal["exact", "estimated", "unknown"]

SurfaceKind = Literal["plane", "cylinder", "cone", "sphere", "torus"]
SurfaceSource = Literal["native", "facets", "fit"]


@dataclass(frozen=True, slots=True)
class SurfacePatch:
    """Vorhandener analytischer Träger und sein Anteil an der ursprünglichen Haut.

    Ebene und Zylinder tragen ``centre`` und ``axis``, der Zylinder zusätzlich
    ``radius``. Der gerichtete Kegel trägt ``apex``, ``axis`` und seinen
    ``half_angle`` in Radiant. Die Kugel besitzt ``centre`` und ``radius``,
    der Ringtorus ``centre``, ``axis``, ``ring_radius`` und ``tube_radius``.
    Richtungen werden bei der Auswertung normiert, Zahlen bleiben ungerundet.
    Die Indizes gehören zum aktuellen Körper und zum enthaltenden Feature.
    """

    kind: SurfaceKind
    params: Mapping[str, float | Vec3]
    face_indices: tuple[int, ...]
    source: SurfaceSource


@dataclass(frozen=True, slots=True)
class MeasureStatus:
    """Maßauskunft ohne eigene Zahl; ein Vorgabemaß bleibt als solches erkennbar."""

    state: MeasureState
    source: MeasureSource | None = None
    available: bool = False
    """Ein gültiger Zahlenwert kann vorhanden sein, obwohl seine Quelle unbekannt ist."""


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

    measure_sources: Mapping[str, MeasureSource] = field(default_factory=dict)
    """Quelle je tatsächlich veröffentlichtem Maß in ``params``.

    ``native`` liest die ursprüngliche Modellfläche, ``facets`` die wirklichen
    Dreiecke, ``fit`` eine daran eingepasste Form und ``parameter`` einen
    belegten Vorgabewert. Der Wert entsteht ausschließlich in ``params``.
    Neue Messung und Transformation führen die Quelle mit; ein gleicher
    Name, Erzeuger oder Herkunftsvermerk beweist sie nicht. Fehlend heißt
    unbekannt, auch bei einem exakten Körper oder einem eigenen Baustein.
    """

    surface_patches: tuple[SurfacePatch, ...] = ()
    """Belegte Teilträger; Auswahlmitte und Vorgabemaße ersetzen sie nicht.

    Zusammengefasste Merkmale behalten ihre verschiedenen Träger. Nach neuer
    Geometrie stammen Träger und Dreiecke gemeinsam aus dem neuen Nachweis;
    Name oder Herkunft erlauben keine Übernahme veralteter Flächennummern.
    """


def measure_status(feature: Feature, name: str) -> MeasureStatus:
    """Liest die belegte Maßquelle ohne Geometrie, Nachmessung oder Nennwertraten.

    ``exact`` gilt für die bezeichnete Quelle: Ein Facettenmaß beschreibt das
    vorhandene Netz, ein Vorgabemaß den gespeicherten Wert, keine Druck- oder
    Passungszusage. Deshalb bleibt die Quelle im Ergebnis erhalten.
    """
    value = feature.params.get(name)
    vector = name in {
        "centre",
        "position",
        "arc_centre",
        "mouth_centre",
        "axis",
        "normal",
        "direction",
        "opening_normal",
        "profile_clamp_y",
        "size",
    }
    if isinstance(value, (tuple, list)) != vector:
        return MeasureStatus("unknown")
    values = value if isinstance(value, (tuple, list)) else (value,)
    if not values or any(
        isinstance(item, bool) or not isinstance(item, (int, float)) for item in values
    ):
        return MeasureStatus("unknown")
    try:
        if not all(math.isfinite(item) for item in values):
            return MeasureStatus("unknown")
    except OverflowError:
        return MeasureStatus("unknown")
    if name in {"diameter", "tube_diameter", "radius", "area", "volume", "pitch"} and (
        len(values) != 1 or values[0] <= 0.0
    ):
        return MeasureStatus("unknown")
    if vector and len(values) != 3:
        return MeasureStatus("unknown")
    if name in {"axis", "normal", "direction", "opening_normal", "profile_clamp_y"} and not any(
        abs(item) > 0.0 for item in values
    ):
        return MeasureStatus("unknown")
    if name == "size" and any(item < 0.0 for item in values):
        return MeasureStatus("unknown")
    if name in {
        "depth",
        "length",
        "travel",
        "fit_error",
        "residual",
        "radial_min",
        "radial_max",
    } and (values[0] < 0.0):
        return MeasureStatus("unknown")
    source = feature.measure_sources.get(name)
    if source not in ("native", "facets", "fit", "parameter"):
        return MeasureStatus("unknown", available=True)
    return MeasureStatus("estimated" if source == "fit" else "exact", source, available=True)


def thread_is_left_handed(feature: Feature) -> bool:
    """Ist dieses Gewinde belegt linksgängig?

    Belegt heißt: gesetzt (ein Baustein sagt es, ``parameter``), am exakten
    Körper gelesen (``native``) oder am Netz an den Kanten gemessen
    (``facets``, P2.5: das Vorzeichen der Steigung jeder windenden Kante). Eine
    Auskunft aus ``fit`` ist die Schätzung des Spektrums, und die verfehlt an
    einem gedruckten, abgeflachten Profil die Richtung — gemessen am 21.09.2026
    an ``build.threaded(6, 1, 8)``, dem Gewinde, das diese Anwendung selbst
    baut: Spektrum „left“, exakt „right“. Sie zählt deshalb nicht: Wer sie
    sperren ließe, sperrte manches gedruckte Gewinde. Die eine Stelle für
    beide Fragenden — das Neuschneiden (``geom.prepare_ops``) und das
    Gegenstück (``counterpart``).
    """
    if feature.kind != "thread":
        return False
    if str(feature.params.get("handedness", "right")) == "right":
        return False
    return feature.measure_sources.get("handedness", "parameter") != "fit"


def thread_is_tapered(feature: Feature) -> bool:
    """Ist dieses Gewinde kegelig — ein Rohrgewinde, dessen Durchmesser wächst?

    Der exakte Leser nennt dann ``taper``, den halben Kegelwinkel (P2.5).
    Neuschneiden, Entfernen und das Gegenstück bauen mit Zylindern; an einem
    Kegel trügen sie ein Ende ab und ließen das andere stehen. Die eine Frage
    für alle drei, wie :func:`thread_is_left_handed`.
    """
    if feature.kind != "thread":
        return False
    taper = feature.params.get("taper", 0.0)
    return isinstance(taper, int | float) and not isinstance(taper, bool) and taper != 0.0


def is_a_cavity(feature: Feature) -> bool:
    """Ist dieses Merkmal ein Hohlraum oder Materie?

    ``hole`` ist immer ein Hohlraum, ``pin`` immer Materie. ``cone`` und
    ``sphere`` können beides sein, und die Erkennung sagt es in ``recess`` —
    eine angesenkte Bohrung ist ein Kegel nach innen, eine Kuppe einer nach
    außen.

    **Die einzige Stelle, an der diese Frage beantwortet wird** — seit dem
    07.09.2026. Bis dahin stand sie wortgleich als
    ``geom.prepare_ops._feature_is_a_cavity`` daneben, mit zwei Begründungen,
    die beide nicht trugen: Die Wahrnehmung dürfe die Geometrie nicht
    importieren (``perceive.relations`` importiert ``geom.mesh`` in seiner
    dritten Importzeile), und ``tests/test_features.py`` halte beide zusammen
    (kein Test nannte je eine der beiden Funktionen).

    **Und sie wohnt hier, nicht in ``perceive.relations``.** Gelesen werden
    ausschließlich :attr:`Feature.kind` und ``params["recess"]`` — keine
    Geometrie, kein Netz, keine Erkennung. Eine Aussage wohnt bei dem Ding,
    über das sie etwas sagt (Robert, 27.08.2026), und das Ding ist
    :class:`Feature`. In der Wahrnehmung kostete sie jeden Aufrufer aus
    ``geom`` einen trägen Import gegen die Paketrichtung — sieben waren es,
    und keiner davon brauchte mehr als diese vier Zeilen.

    **Und ein Langloch ist ein Hohlraum wie eine Bohrung.** Es fehlte hier,
    und die Folge war still: ``recess`` trägt es nicht, die Antwort war
    „Materie", und *Merkmal verschieben* trug an der alten Stelle ab statt zu
    füllen und setzte an der neuen an statt zu schneiden — beides an Luft
    beziehungsweise in vollem Material, das Volumen blieb auf ein
    Mikrogramm gleich, und das Merkmal wanderte im Baum an eine Stelle, an der
    kein Loch war (gemessen 11.09.2026, Ø 6 auf 20 mm nach (25|15): Prüfzylinder
    an der neuen Stelle voll, Langloch an der alten noch da).
    """
    if feature.kind in ("hole", "void", "slot"):
        return True
    if feature.kind == "pin":
        return False
    return bool(feature.params.get("recess", False))


#: Wie viele Filamente die Operationen benennen lassen (§20).
#:
#: Mehr als acht ist keine Maschine, die jemand besitzt, und jedes einzelne
#: ist ein Handwechsel oder ein AMS-Slot, den jemand füllen muss.
#:
#: **Die Zahl stand dreimal im Code** — in ``colour_ops``, ``label_ops`` und
#: ``paint``, jedes Mal mit dem Kommentar „wie bei den Farb-Operationen"
#: daneben. Ein Verweis auf die Kopie ist keine geteilte Sache: Wer die Grenze
#: eines Tages ändert, ändert sie an einer Stelle, und zwei Operationen
#: erlauben danach etwas anderes als die dritte. Sie wohnt deshalb hier, bei
#: dem Ding, über das sie eine Aussage macht (Robert, 27.08.2026 — „wir wollen
#: überall eine saubere Architektur").
MAX_SLOTS = 8


#: So viele Farben trägt ein Filament höchstens (Entscheidung Robert,
#: 19.09.2026: „Filament mehrfarbig, bis 4-farbig"). Die Slicer der
#: Orca-Familie zeigen dieselbe Zahl in ihrem Farbfeld. Hier und nicht im
#: Lager, weil Einlesen und Export die Zahl brauchen und ``ingest`` das
#: Wissen nicht importieren darf (Paketkarte).
MAX_FILAMENT_COLOURS: Final = 4


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
    """Name des Herstellerprofils im Slicer, niemals ein Dateipfad."""
    material_type: str | None = None
    """Materialart in der Schreibweise des Slicers, etwa ``PETG``."""
    extra_colours: tuple[tuple[float, float, float], ...] = ()
    """Die zweite bis vierte Farbe eines mehrfarbigen Filaments (§20).

    :attr:`colour` bleibt die erste und damit das, was Ansicht, STL,
    PrusaSlicer und Cura bekommen — sie kennen je Filament eine Farbe. Die
    Orca-Familie kennt alle (``filament_multi_colour``), und die 3MF trägt
    sie dorthin. Nicht Teil der Slotidentität: Zwei Spulen mit demselben Namen
    und derselben ersten Farbe sind dieselbe Spule.
    """


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
    reserved_feature_ids: tuple[FeatureId, ...] = ()
    """Sortierte bisher vergebene Merkmalskennungen, auch nach ihrem Entfernen.

    Die Auswertung rekonstruiert sie aus dem Verlauf; der Ergebniscache trägt
    sie mit, damit ein alter Verweis nie ein späteres anderes Merkmal trifft.
    """
    frame: Transform | None = None
    """Dauerhafter Ausgangsrahmen in Weltkoordinaten (RM-401).

    Die ersten drei Spalten sind die mitbewegten Ausgangsachsen, die vierte
    ihr Ursprung. Die vollständige affine Abbildung erhält Maßstab, Spiegelung
    und Scherung; sie ist nicht notwendig eine reine Drehung. ``None`` ist ein
    noch nicht zugeordneter Rahmen einer rohen Operationsausgabe. Die Auswertung
    setzt bei Import/Erzeugung die Identität, bei einem eindeutigen Vorfahren
    dessen Rahmen. Ein neuer Mehrkörperausgang ohne Bezug bleibt unbekannt.
    Der Rahmen wird aus dem Stapel rekonstruiert, nie aus Hauptachsen geschätzt.
    """


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


@dataclass(frozen=True, slots=True)
class FeatureContinuation:
    """Ein belegter Übergang: das alte Merkmal ``source`` lebt in der Ausgabe
    als ``target`` weiter.

    Ausgestellt wird er nur von der Operation, die den Übergang selbst
    nachgewiesen hat — *Bohrung ändern* kennt die bewusst geänderte Bohrung
    und ihren Boden. Die Auswertung errät ihn weder aus gleichen Namen noch
    aus gleicher Herkunft; sie prüft nur, dass Quelle und Ziel tatsächlich
    existieren. Wie ``OpResult.transform`` ist das abgeleitete Rechenauskunft:
    Sie reist durch den Ergebniscache und wird aus den Parametern neu
    erzeugt, nie in die Projektdatei geschrieben.
    """

    source: FeatureRef
    """Das Merkmal am Eingang, körperqualifiziert — zwei Eingänge mit
    ``hole_1`` sind zwei Quellen."""
    target: FeatureId
    """Das Merkmal der zugehörigen Ausgabe, unter dem die Quelle weiterlebt."""


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
    when_positive: tuple[OpId, str] | None = None
    """Gilt nur, solange dieser Operationsparameter positiv ist, etwa ein Deckelkragen."""


PrintTechnology = Literal["fdm", "resin"]
"""Das Druckverfahren eines Druckers (§38; Resin-Konzept §4).

``fdm`` legt Bahnen aus einer Düse, ``resin`` belichtet Schichten in einem
Harzbad. Der Unterschied ist kein Zahlenwert, sondern ein **Geltungsbereich**:
Düse, Bahnbreite, Brücken, Elefantenfuß, Brim und Filamentwechsel gibt es
beim einen und nicht beim anderen. Bis zum 22.09.2026 setzte Solidon den
FDM-Drucker voraus, ohne je danach zu fragen — Regel 21 in ihrer stillsten
Form: nicht geraten in einer Ausnahme, sondern geraten als Voreinstellung.
"""


@dataclass(frozen=True, slots=True)
class PrinterProfile:
    """Bauraum und Verfahrensdaten. Nie fest im Code (§38).

    Was gilt, entscheidet ``technology``: Bei ``fdm`` tragen Düse,
    Schichthöhe und Bahnbreite; bei ``resin`` stehen Düse und Bahnbreite auf
    **null** — dieses Verfahren hat keine —, und an ihre Stelle treten
    Pixelgröße und die eigene Mindestwand. Wer eine der FDM-Zahlen liest,
    ohne das Verfahren zu fragen, rechnet bei Resin mit null; dass daraus kein
    Satz über eine Düse wird, prüft ``tests/test_resin.py`` über den
    Befundkatalog.
    """

    id: str
    title: str
    build_volume: Vec3
    nozzle_diameter: float = 0.4
    layer_height: float = 0.2
    extrusion_width: float = 0.42
    technology: PrintTechnology = "fdm"
    """Das Druckverfahren. Ein Profil ohne Angabe — jedes bis zum 22.09.2026
    angelegte — ist ein FDM-Drucker, und zwar ohne Migration."""
    pixel_size: float = 0.0
    """Resin: die Kantenlänge eines Bildpunkts in XY in mm — das kleinste
    Detail, das dieser Drucker abbildet. Bei FDM null: dort ist das kleinste
    Detail die Bahnbreite (:attr:`smallest_detail`)."""
    minimum_wall: float = 0.0
    """Resin: die Mindestwand in mm, die dieses Verfahren stehen lässt.

    Bei Resin ist die Grenze Stabilität, nicht Auflösung — ein Pixel breit
    ließe sich belichten, hielte aber weder das Waschen noch das Abziehen
    von der Folie aus. Bei FDM null: dort sind es zwei Bahnbreiten
    (:attr:`Profile.minimum_wall_thickness`)."""
    enclosed: bool = False
    """Geschlossener Bauraum — entscheidet, ob ASA und ABS überhaupt
    sinnvoll sind."""
    bed_temperature_max: int = 100
    nozzle_temperature_max: int = 260
    vendor: str = ""
    printable_area: tuple[tuple[float, float], ...] = ()
    """Äußere Druckkontur in mm, XY relativ zur nominellen Bettmitte.

    Leer heißt: das Rechteck aus ``build_volume``. Die nominellen Maße bleiben
    unabhängig vom tatsächlich gewählten Maschinenprofil erhalten.
    """
    bed_exclusions: tuple[tuple[tuple[float, float], ...], ...] = ()
    """Feste Sperrkonturen in denselben zentrierten XY-Koordinaten.

    Brim, Skirt und andere auftragsabhängige Abstände stehen nicht hier.
    """
    printable_height: float | None = None
    """Z-Obergrenze ab Bett; ohne Angabe gilt die nominelle Bauraumhöhe."""
    bed_origin: tuple[float, float] | None = None
    """Wo der Nullpunkt der Maschine liegt, in denselben zentrierten
    XY-Koordinaten wie ``printable_area`` (§9, §29).

    Ohne Angabe die vordere linke Ecke des Bauraums, ``(-Breite/2, -Tiefe/2)``
    — so misst der übliche Drucker, und so blieb jedes vor dem 02.10.2026
    angelegte Profil, ohne Migration. ``(0, 0)`` ist ein Bett um den Ursprung
    (Deltas, BIBO); der Dremel 3D45 hat ``(15, 0)``, weil sein Bett von
    -127,5 bis 97,5 reicht. Jede Stelle, die Maschinenkoordinaten schreibt
    oder liest, rechnet über :func:`app.core.build_area.machine_shift`.
    """
    nozzles: int = 1
    """Wie viele Düsen der Drucker zugleich führt.

    Eine Düse mit Wechselstation (AMS, CFS) zählt als **eine**: Sie spült bei
    jedem Filamentwechsel, und genau das entscheidet, ob *Auf dem Bett
    anordnen* und *Druckoptimal ausrichten* die Filamente auf eigene Platten
    legen (§29). Zwei Düsen (IDEX, H2D) drucken zwei Filamente ohne Spülgang,
    ein Werkzeugwechsler mit fünf Köpfen fünf.
    """
    travel_speed: float | None = None
    """Wie schnell der Kopf leer fährt, in mm/s — eine Eigenschaft der Maschine.

    Keine Qualitätsstufe fragt danach, und das Material auch nicht: Die
    Leerfahrt ist die Zeit, in der die Düse ausläuft, und ein schneller
    CoreXY-Drucker fährt sie in einem Drittel. An der Waschschüssel
    (25.09.2026) übergab Solidon dem Centauri Carbon 2 die allgemeinen
    150 mm/s statt der 500 seines Herstellerprofils, bei 530 Leerfahrten je
    Schicht — und schon in den ersten Schichten zog der Druck Fäden. Ohne
    Angabe gilt die Vorgabe von :class:`SpeedSettings`.
    """
    # **Das Standardtempo des Druckers** (26.09.2026), aus dem Standardprozess
    # seines Herstellerprofils. Solidons Qualitätsstufen sind für einen
    # allgemeinen Drucker geschrieben — 40/60/80 mm/s —, und der Centauri
    # Carbon 2 fährt 160/200/200: dieselbe Schüssel 30 h 41 min gegen
    # 18 h 29 min im ElegooSlicer. Steht ein Wert hier, gilt er für die Stufe „Standard", und
    # die übrigen Stufen skalieren ihn mit ihrem Verhältnis zu ihr
    # (``print_settings.resolve``). Ohne Angabe bleibt der Wert der Stufe.
    speed_outer_wall: float | None = None
    speed_inner_wall: float | None = None
    speed_infill: float | None = None
    speed_top_surface: float | None = None
    speed_first_layer: float | None = None
    speed_bridge: float | None = None
    acceleration: float | None = None
    outer_wall_acceleration: float | None = None
    flow_factor: float = 1.0
    """Wie viel mehr das Hotend fördert als das Standard-Hotend, für das die
    Materialwerte ``max_flow`` gelten — aus dem generischen PLA-Profil des
    Herstellers gegen Solidons 12 mm³/s (CC2 21 → 1,75). Ohne ihn drückte die
    Volumenstromregel die Tempi des Druckers gleich wieder herunter. Er gilt
    nur für PLA (``print_settings.HOTEND_FLOW_MATERIAL``); die übrigen
    Materialien begrenzt das Filament."""
    overhang_limit: float | None = None
    """Bis zu welchem Winkel gegen die Senkrechte dieser Drucker ohne Stütze
    druckt — die Stützgrenze aus dem Standardprozess seines Herstellers
    (27.09.2026), umgerechnet aus deren Zählung gegen die Waagerechte.

    Solidon rechnete bis dahin für jeden Drucker mit der Startregel von 45
    Grad und schrieb sie in jede Übergabe. Der Centauri Carbon 2 stützt laut
    Elegoo erst ab 60 Grad; am Minigolf-Satz verlangte die Startregel für die
    Fase einer Bodenplatte und 45 bis 55 Grad geneigte Wände Stützen, der
    ElegooSlicer legte 46 m davon an, und Roberts erste Schicht war ein
    treppenförmiger Stützfuß mit einem Brim aus tausenden Stückchen. Ohne
    Angabe gilt die Startregel (:data:`app.core.knowledge.rules.OVERHANG_LIMIT_DEGREES`);
    eine Kalibrierung geht beidem vor (§28.3)."""
    cura_definition: str = ""
    """Die Druckerdefinition dieses Druckers in Cura, als Kennung
    (``creality_k1max``): Start- und Endcode des Herstellers und die
    Vorgaben seiner Maschine für die Konsolenübergabe
    (``handover._cura_machine``).

    Leer heißt, Cura führt diesen Drucker nicht (Centauri Carbon 2, Bambu,
    Prusa, K1, Ender-3 V3). Dann rechnet CuraEngine auf ``fdmprinter``, und
    die Übergabe sagt es (``handover.machine_missing``): Dessen Startcode
    fährt nach Hause, fördert drei Millimeter Filament in die Luft und legt
    weder eine Spüllinie noch ein Bettnetz an."""
    prusaslicer_printer: str = ""
    """Das Druckerprofil dieses Druckers in PrusaSlicers Herstellerbündel,
    mit seinem Namen dort (``Original Prusa MK4S HF0.4 nozzle``).

    Die Namenssuche trifft dort das falsche Profil: am MINI und XL die
    abgelösten Profile ohne Input Shaper, am MK4S die Düse, die PrusaSlicer
    nicht vorwählt, und den SV06 gar nicht, weil sein Bündel ihn nur „SV06"
    nennt (27.09.2026). Leer heißt, PrusaSlicer führt diesen Drucker nicht;
    dann bleibt die Namenssuche."""
    first_layer_acceleration: float | None = None
    """Die Beschleunigung der ersten Schicht in mm/s², aus demselben
    Standardprozess des Herstellers wie die Tempi (Orca
    ``initial_layer_acceleration``, PrusaSlicer ``first_layer_acceleration``).

    Gebraucht wird sie bei Cura, wo Solidons Satz die Grundlage bleibt: Dort
    erbte die erste Schicht die Druckbeschleunigung — 12 000 mm/s² am
    Ender-3 V3, wo Creality mit 500 anfährt. Die anderen Slicer nehmen sie aus
    dem Profil des Herstellers selbst. Ohne Angabe gilt die Vorgabe der
    Werksprofile (``handover._FIRST_LAYER_ACCELERATION``)."""
    overhang_speed_factors: tuple[float, ...] = ()
    """Wie schnell überhängende Außenwände fahren, in Prozent des
    Außenwandtempos: die Überhangstufen 2/4, 3/4 und 4/4 aus demselben
    Standardprozess wie die Tempi (Orca ``overhang_2_4_speed`` bis
    ``overhang_4_4_speed`` geteilt durch ``outer_wall_speed``; PrusaSlicer
    ``overhang_speed_2``, ``_1`` und ``_0``).

    Nur Cura liest sie (``handover._for_overhangs``), und nötig ist das, seit
    die Stützgrenze mit dem Herstellerprofil auf 60 Grad stieg: Wände
    zwischen 45 und 60 Grad druckten dort ohne Stütze und mit voller
    Wandgeschwindigkeit. Leer heißt, der Hersteller nennt keine."""
    first_layer_line_factor: float | None = None
    """Die Breite der ersten Bahn als Vielfaches der Düse, aus demselben
    Standardprozess wie die Tempi (Orca ``initial_layer_line_width``,
    PrusaSlicer ``first_layer_extrusion_width``: 0,5 mm an der 0,4er Düse sind
    1,25; der Kobra 2 legt 0,8 mm, also 2,0).

    Als Vielfaches und nicht in Millimetern, weil der Druckdialog das Profil
    mit einer anderen Düse kopiert — die erste Bahn geht dann mit. Ohne Angabe
    bleibt Solidons 1,07-fache Bahnbreite (``print_settings.resolve``); sie war
    schmaler als jedes Werksprofil (Prüfbericht Cura, B7)."""

    @property
    def is_resin(self) -> bool:
        """Belichtet dieser Drucker Harz? Die eine Frage hinter jedem Geltungsbereich."""
        return self.technology == "resin"

    @property
    def smallest_detail(self) -> float:
        """Das kleinste Detail, das dieser Drucker in der Ebene abbildet, in mm.

        FDM: die Bahnbreite — schmaler wird keine Spur. Resin: die
        Pixelgröße. Beides ist dieselbe Frage an zwei Verfahren, und sie
        wird hier einmal beantwortet, damit die Analysekarte, die Beschriftung
        und die Textur nicht jede für sich die Düse fragen (Regel 7, §38).
        """
        return self.pixel_size if self.is_resin else self.extrusion_width


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
    youngs_modulus: float = 0.0
    """Elastizitätsmodul in MPa; **0 heißt unbekannt**, nicht null.

    Für alles, was federn soll — ein Schnapphaken, eine Klemmzunge, ein
    Filmscharnier. Ohne diesen Wert lässt sich nicht sagen, ob ein Arm
    zurückfedert oder bricht, und eine Rechnung mit einer geratenen Zahl wäre
    schlechter als keine (Regel 21).
    """
    yield_strength: float = 0.0
    """Streckgrenze in MPa; **0 heißt unbekannt**, nicht null.

    Die Grenze, gegen die eine Biegespannung gehalten wird. Darüber verformt
    sich ein Arm bleibend oder bricht, statt zurückzukommen.
    """
    layer_bond_ratio: float = 0.0
    """Anteil der Streckgrenze quer zur Schichtebene, zwischen 0 und 1; 0 heißt unbekannt."""
    minimum_wall: float | None = None
    """Gemessene druckbare Mindestwand in mm, ausschließlich für den gespeicherten Prozess."""
    overhang_angle: float | None = None
    """Gemessener größter freier Überhangwinkel gegen die Senkrechte in Grad."""
    calibration_printer: str = ""
    calibration_nozzle_diameter: float = 0.0
    calibration_layer_height: float = 0.0
    calibration_extrusion_width: float = 0.0
    """Druckprozess der Wand- und Überhangprobe; fehlende Angaben übernehmen keine Messung."""
    technology: PrintTechnology = "fdm"
    """Zu welchem Verfahren das Material gehört: ein Filament zu ``fdm``, ein
    Harz zu ``resin``. Ein Drucker nimmt nur Material seines Verfahrens an —
    PLA in einem Harzbad wäre eine FDM-Aussage vor dem ersten Klick."""

    def fits(self, printer: PrinterProfile) -> bool:
        """Ob dieses Material in diesen Drucker gehört — dasselbe Verfahren."""
        return self.technology == printer.technology


@dataclass(frozen=True, slots=True)
class Profile:
    """Drucker und Material, für die eine Szene gerechnet wird."""

    printer: PrinterProfile
    material: MaterialProfile

    @property
    def has_process_calibration(self) -> bool:
        """Ob die gespeicherte Druckprobe unter denselben Profilbedingungen entstand.

        Bei Resin ist der Prozess Drucker und Schichthöhe — eine Düse und
        eine Bahn, die er nicht hat, können auch nicht abweichen.
        """
        material, printer = self.material, self.printer
        if printer.is_resin:
            measured = material.calibration_layer_height
            return (
                material.calibration_printer == printer.id
                and measured > 0.0
                and math.isclose(measured, printer.layer_height, rel_tol=1e-9, abs_tol=1e-12)
            )
        return material.calibration_printer == printer.id and all(
            measured > 0.0 and math.isclose(measured, current, rel_tol=1e-9, abs_tol=1e-12)
            for measured, current in (
                (material.calibration_nozzle_diameter, printer.nozzle_diameter),
                (material.calibration_layer_height, printer.layer_height),
                (material.calibration_extrusion_width, printer.extrusion_width),
            )
        )

    @property
    def minimum_wall_thickness(self) -> float:
        """Die gemessene Mindestwand; ohne passende Probe zwei Extrusionsbreiten
        — und bei Resin die Mindestwand des Druckerprofils.

        Bei Resin ist die Grenze keine Frage der Auflösung, sondern der
        Stabilität — ohne Probe steht sie im Profil des Druckers
        (Resin-Konzept §4); eine Probe für denselben Drucker und dieselbe
        Schichthöhe gilt auch dort.
        """
        measured = self.material.minimum_wall
        if (
            self.has_process_calibration
            and measured is not None
            and math.isfinite(measured)
            and measured > 0.0
        ):
            return measured
        if self.printer.is_resin:
            return self.printer.minimum_wall
        return 2.0 * self.printer.extrusion_width

    @property
    def overhang_limit_degrees(self) -> float:
        """Die Überhanggrenze gegen die Senkrechte: gemessen, sonst die des
        Druckers laut Hersteller, sonst die Startregel (§28.3)."""
        measured = self.material.overhang_angle
        if self.has_process_calibration and measured is not None and 0.0 < measured < 90.0:
            return measured
        if self.printer.overhang_limit is not None:
            return self.printer.overhang_limit
        return OVERHANG_LIMIT_DEGREES

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

        Bei Resin ist es ein belichtetes Voxel — ein Pixel im Quadrat mal
        eine Schichthöhe. Dieselbe Frage, dasselbe Prinzip, ein anderes
        Verfahren.
        """
        return self.printer.smallest_detail**2 * self.printer.layer_height

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

        **Bei Resin null**, und null heißt in der Orientierungssuche „nicht
        gefragt": Ein Resinteil steht nicht auf einer ersten Schicht, es hängt
        an Stützen oder klebt mit seiner ganzen Fläche an der Plattform — die
        Standbedingung einer Düse hat dort keinen Gegenstand.
        """
        if self.printer.is_resin:
            return 0.0
        return (10.0 * self.printer.extrusion_width) ** 2

    @property
    def export_deflection(self) -> float:
        """Wie weit ein Dreieck beim Export eines exakten Körpers von der
        echten Fläche abweichen darf, in mm (§29, §30).

        Aus dem Verfahren und nicht als Zahl im Code: Was der Drucker nicht
        abbildet, muss die Datei nicht tragen, und was er abbildet, darf ihr
        nicht fehlen. Ein Achtel des kleinsten Details — bei einer 0,4er
        Düse die 0,05 mm, mit denen der Kern ohnehin tesselliert
        (``units.MAX_FACET_SAG``); bei 50 µm Pixeln 0,006 mm, denn dort
        wird eine Facette von fünf Hundertsteln als Stufe sichtbar. Nach
        oben deckelt die Zahl des Kerns: Gröber als er selbst rechnet, wird
        keine Datei. Ohne ein kleinstes Detail — Pixelgröße null in einem
        selbst angelegten Resin-Profil — bleibt es bei der Zahl des Kerns.
        """
        from app.core.units import MAX_FACET_SAG

        detail = self.printer.smallest_detail
        if detail <= 0.0:
            return MAX_FACET_SAG
        return min(MAX_FACET_SAG, detail / 8.0)


# --- Druckeinstellungen (§29) --------------------------------------------------
#
# Solidon hält die Einstellungen, der externe Slicer führt sie aus (§22, §29).
# Das hier ist also kein Slicer-Format, sondern das eine Modell, aus dem
# ``export.handover`` die Konfiguration jedes unterstützten Slicers schreibt.
# Gruppiert statt flach, weil die Oberfläche in denselben Gruppen fragt und die
# Zuordnungstabellen Punktpfade wie ``cooling.fan_speed`` benutzen.

InfillPattern = Literal["grid", "gyroid", "honeycomb", "cubic", "lines", "triangles"]

#: Ob und wie gestützt wird. ``auto`` heißt: Stützen an, die Art bestimmt das
#: Profil des Slicers (Konzept Herstellerprofil, Entscheidung J, 27.09.2026).
#: Bis dahin hieß „Stützen nötig" immer ``grid`` — und Elegoo wie Bambu, deren
#: Standardprozess Bäume stützt, bekamen Gitter, auch wer die Stützen erst im
#: Slicerfenster einschaltete.
SupportStyle = Literal["none", "auto", "grid", "tree"]
SupportPlacement = Literal["everywhere", "build_plate"]
SeamPosition = Literal["aligned", "nearest", "random", "rear"]

#: Wie die Wandbahnen erzeugt werden. ``classic`` legt feste Linienbreiten und
#: füllt, was dazwischen übrig bleibt, mit Lückenfüllung; ``arachne`` verteilt
#: die vorhandene Breite auf so viele Bahnen, wie hineinpassen. Der Unterschied
#: zählt genau dort, wo eine Wand nicht auf ganze Linien aufgeht — bei einem
#: 1,1 mm dicken Federarm etwa liegen zwei Bahnen à 0,55 statt zweier à 0,42
#: mit einer Lücke dazwischen.
WallGenerator = Literal["classic", "arachne"]

#: Was das Teil auf der Platte hält. ``auto`` ist die Haftung, die das Profil
#: des Slicers wählt — in der Orca-Familie ``auto_brim``, das aus Material,
#: Geometrie und Tempo selbst entscheidet und das kein Hersteller abschaltet
#: (Entscheidung J). Solidon schrieb bis zum 27.09.2026 ``no_brim`` und zwei
#: Skirt-Runden darüber.
AdhesionType = Literal["none", "auto", "skirt", "brim", "raft"]
QualityPreset = Literal["draft", "standard", "fine", "strong"]

#: Die zwei Übergabearten aus §29: den Slicer im Konsolenmodus rechnen lassen
#: („slice") oder die geschriebene Datei in seinem Fenster öffnen („open").
HandoverKind = Literal["slice", "open"]


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
    scarf_seam: bool = False
    """Setzt Anfang und Ende der Außenwand schräg übereinander, statt an einer
    Stelle. Eine runde Außenwand hat keine Ecke, in der die Naht verschwindet;
    so bleibt dort keine Linie stehen. Kostet etwas Druckzeit."""
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
    """Kühlung. Lüfterwerte sind Anteile, 1.0 heißt volle Drehzahl.

    Der Bauteillüfter läuft in allen drei Slicer-Familien auf einer Kurve über
    der Schichtzeit: bis zur :attr:`minimum_layer_time` mit :attr:`fan_speed`,
    ab :attr:`fan_below_layer_time` mit :attr:`minimum_fan_speed`, dazwischen
    linear. Bis zum 23.09.2026 kannte Solidon nur einen Wert und schrieb ihn an
    beide Enden — der Lüfter lief bei PLA in jeder Schicht voll (Befund
    Robert, am ElegooSlicer gemessen).
    """

    fan_speed: float = 1.0
    """Das obere Ende: so stark kühlt der Lüfter eine Schicht, die kaum Zeit
    zum Abkühlen hat."""
    minimum_fan_speed: float = 1.0
    """Das untere Ende: so stark läuft er auch bei Schichten, die lange genug
    dauern — über null läuft er nie ganz aus. Höher als :attr:`fan_speed` wird
    er nicht übergeben (``handover.as_mapping`` deckelt). Die Vorgabe gleicht
    :attr:`fan_speed`; eine ältere Projektdatei ohne das Feld ergänzt es aus
    ihrem Material (``serialise.print_settings_from_data``)."""
    fan_below_layer_time: float = 60.0
    """Sekunden. Kürzere Schichten kühlt der Lüfter stärker als mit
    :attr:`minimum_fan_speed`. Die Vorgabe ist der Slicerstandard von Orca und
    PrusaSlicer; die Materialien bringen ihre eigene mit."""
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
    threshold_angle: float = OVERHANG_LIMIT_DEGREES
    """Grad gegen die Senkrechte, ab dem gestützt wird.

    **Abgeleitet und nicht abgeschrieben** (§39). Hier stand 50, und die
    Schichtanalyse rechnete mit 45: Dieselbe Frage, zwei Antworten — der
    Bericht meldete einen Überhang, den der Slicer stehen ließ, und ein
    48-Grad-Dach fiel zwischen beide Zahlen. Die Linie wohnt in der
    Regelsammlung, weil dort das Druckwissen steht; wer sie ändert, ändert
    beides. Bei 45 Grad ist die Zählrichtung übrigens gleichgültig — gegen
    die Senkrechte und gegen die Waagerechte ist dieselbe Zahl."""
    z_gap: float = 0.2
    xy_gap: float = 0.5
    density: float = 0.15
    interface_layers: int = 2
    block_channels: bool = False
    """Stützen aus schmalen Kanälen heraushalten (§22.2).

    Die Übergabe legt dafür eine Stützsperre in die 3MF
    (``export.writer._support_blocker``). Aus steht es, bis ein Vorschlag es
    einschaltet: Was ohne „Vorschläge übernehmen" zum Slicer geht, sind die
    Standardeinstellungen, nichts auf dieses Modell Zugeschnittenes
    (Entscheidung Robert, 26.09.2026)."""


@dataclass(frozen=True, slots=True)
class AdhesionSettings:
    """Was das Teil auf der Platte hält."""

    kind: AdhesionType = "skirt"
    skirt_loops: int = 2
    skirt_distance: float = 3.0
    brim_width: float = 5.0
    brim_gap: float = 0.0
    raft_layers: int = 3
    raft_gap: float | None = None
    """Luft zwischen Raft und Teil in mm; ohne Zahl bleibt die Slicer-Vorgabe."""


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
    """Name des Filaments; Farbe, Profil und Materialtyp ergänzen seine Identität.

    **Nicht die Position.** Sie stand hier zuerst, und sie war falsch: Was der
    Dialog zeigt, ist die Zusammenlegung der gewählten Platten; gedruckt wird
    Platte für Platte, und jede legt für sich zusammen. Bei Rot auf Platte 1
    und Weiß+Rot auf Platte 2 steht [Rot, Weiß] im Dialog und [Weiß, Rot] im
    Lauf der zweiten — gemessen am 26.08.2026 bekam **Weiß die 210 Grad, die
    für Rot eingestellt waren**, und Rot die 240 des Projekts. Bei den
    Filamentprofilen wandert dabei die Temperatur mit; hier *ist* sie der Wert.

    Derselbe Schlüssel wie in :func:`app.core.export.threemf.merge_slots` —
    nur derselbe Name, dieselbe Farbe, dasselbe Profil und derselbe Materialtyp
    gehören zusammen. Ein Übersteuerer gehört dem Filament, nicht seinem Listenplatz.
    """
    colour: tuple[float, float, float] | None = None
    """Die Farbe des Filaments als Teil seiner Identität."""

    temperature: TemperatureSettings | None = None
    cooling: CoolingSettings | None = None
    retraction: RetractionSettings | None = None
    filament: FilamentSettings | None = None

    material: str | None = None
    material_type: str | None = None

    @property
    def empty(self) -> bool:
        """Ob dieser Slot überhaupt etwas übersteuert."""
        return not any((self.temperature, self.cooling, self.retraction, self.filament))

    @property
    def key(
        self,
    ) -> tuple[TranslatableText | str, tuple[float, float, float] | None, str | None, str | None]:
        """Der Schlüssel, unter dem dieser Übersteuerer sein Filament findet."""
        return (self.name, self.colour, self.material, self.material_type)


@dataclass(frozen=True, slots=True)
class SpoolBinding:
    """Die örtliche Spule eines Druckfilaments, unabhängig vom Slicerprofil (§20)."""

    spool_identifier: str
    name: TranslatableText | str = ""
    colour: tuple[float, float, float] | None = None
    material: str | None = None
    material_type: str | None = None

    @property
    def key(
        self,
    ) -> tuple[TranslatableText | str, tuple[float, float, float] | None, str | None, str | None]:
        """Derselbe Schlüssel wie bei der Zusammenlegung für die Ausgabe."""
        return (self.name, self.colour, self.material, self.material_type)


@dataclass(frozen=True, slots=True)
class SlotProfileBinding:
    """Ein Herstellerprofil bleibt an der vollständigen Druckfilamentidentität."""

    profile_name: str
    name: TranslatableText | str = ""
    colour: tuple[float, float, float] | None = None
    material: str | None = None
    material_type: str | None = None

    @property
    def key(
        self,
    ) -> tuple[TranslatableText | str, tuple[float, float, float] | None, str | None, str | None]:
        """Derselbe Schlüssel wie bei der Zusammenlegung für die Ausgabe."""
        return (self.name, self.colour, self.material, self.material_type)


@dataclass(frozen=True, slots=True)
class PrintSettings:
    """Alle Druckeinstellungen an einer Stelle (§29).

    Die Gruppen tragen immer einen vollständigen Satz — den, der gedruckt
    wird. **Welche Werte davon Solidon dem Slicer schreibt, sagen**
    :attr:`chosen` **und** :attr:`accepted`: die eigene Wahl und der
    übernommene Vorschlag. Alles andere ist Grundlage und kommt aus dem
    Profil des Herstellers (``export.manufacturer.base_settings``), ohne
    eines aus Solidons Tabellen (Konzept Herstellerprofil, 27.09.2026).
    """

    id: str = "standard"
    title: str = "Standard"
    quality: QualityPreset = "standard"
    handover: HandoverKind = "slice"
    """Die gemerkte Übergabeart (§29): rechnen lassen oder im Fenster öffnen.

    Je Projekt und nicht je Rechner — die Art ist eine Präferenz des
    Projekts, während der Slicer-**Pfad** beim Gerät bleibt (der andere
    Rechner hat einen anderen Slicer, aber dieselbe Gewohnheit). Eine
    ältere Datei ohne das Feld bleibt auf „slice", dem bisherigen einzigen
    Weg.
    """
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

    spool_bindings: tuple[SpoolBinding, ...] = ()
    """Örtliche Spulen je Druckfilament; fehlende Kennungen bleiben ungelöst."""
    inventory_project_id: str = ""
    """Beständige Projektkennung für die Wiedererkennung einer Druckvorbereitung."""
    slot_profile_bindings: tuple[SlotProfileBinding, ...] | None = None
    """None liest alte Slotpositionen; eine leere Folge bindet nur nach Identität."""
    chosen: frozenset[str] = frozenset()
    """Die Punktpfade (``shell.wall_count``), die der Kunde selbst gesetzt hat.

    **Alles, was weder hier noch in** :attr:`accepted` **steht, ist
    Grundlage** und wird bei jeder Verwendung neu bestimmt: aus dem gewählten
    Profil des Herstellers, ohne eines aus Solidons Tabellen. Die Werte dazu
    stehen trotzdem in den Gruppen — jeder Leser bekommt einen ganzen Satz —,
    aber zum Slicer geht davon nur die Abweichung.

    Bis zum 27.09.2026 schrieb Solidon jeden Wert über das Herstellerprofil,
    auch die aus seiner eigenen Stufe: am Centauri Carbon 2 45 Prozess- und
    22 Filamentwerte, darunter Gitter statt Baum, kein Auto-Brim und die
    Faustregel von 45 Grad als Stützwinkel. Roberts Minigolf-Druck bekam
    davon einen Stützfuß in Schicht 1 (Konzept Herstellerprofil,
    Entscheidung A).
    """
    accepted: frozenset[str] = frozenset()
    """Die Punktpfade aus übernommenen Vorschlägen (``advise.apply``).

    Getrennt von :attr:`chosen`, weil ein Vorschlag dem Körper gelten soll,
    dessen Geometrie ihn verlangt, und eine eigene Wahl der ganzen Platte
    (Entscheidung G). Bis Stufe E gilt auch ein übernommener Vorschlag der
    Platte. Ein Pfad steht in höchstens einer der beiden Mengen: Wer einen
    übernommenen Wert von Hand ändert, macht ihn zu seiner Wahl.
    """

    plate_choices: tuple[tuple[str, object], ...] = ()
    """Die eigene Wahl der Platte unter einem übernommenen Vorschlag je Teil.

    Wer im Dialog „Skirt“ wählt und danach den Brim für den schlanken Turm
    übernimmt, meint: der Turm mit Brim, die übrigen Teile mit Skirt. Ein Pfad
    hat aber nur einen Wert, und die Übernahme löschte die Wahl; die Platte
    fiel auf das Herstellerprofil zurück (Durchsicht 0.5.1, B2; RM-289). Hier
    bleibt der Wert der eigenen Wahl stehen, solange der Pfad übernommen ist
    (:func:`app.core.knowledge.print_settings.with_accepted`); die Trennung je
    Teil schreibt ihn der Platte (``handover.split_for_parts``). Paare aus
    Punktpfad und Wert, nach Pfad geordnet.
    """

    @property
    def explicit(self) -> frozenset[str]:
        """Was von der Grundlage abweichen soll: eigene Wahl und Vorschläge."""
        return self.chosen | self.accepted

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
class Action:
    """Ein anklickbarer Ausweg, den Fehler und Befunde gemeinsam tragen.

    Der Typ liegt bei den Verträgen, weil eine abgefangene Ausnahme als
    :class:`Finding` weiterreist. Bliebe er in ``errors.py``, müsste
    ``types.py`` zurück in die Fehlerhierarchie importieren — ein Kreis an der
    untersten Schicht.
    """

    id: str
    label: TranslatableText | str
    primary: bool = False


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
    #: **Auch ein übersetzbarer Text.** Ein Wert, der einen Körper nennt,
    #: muss mit der Sprache wandern können — sonst steht im englischen
    #: Fenster ein deutscher Name neben demselben Körper im Objektbaum.
    #: Aufgelöst wird beim Anzeigen und beim Speichern, nicht hier.
    values: Mapping[str, float | str | TranslatableText] = field(default_factory=dict)
    location: Vec3 | None = None
    """Wohin die Kamera fliegt, wenn die Warnung angeklickt wird (§18.4)."""
    outline: tuple[tuple[Vec3, Vec3], ...] = ()
    """Die Randkanten einer Stelle, die eine Fläche ist — *Stelle zeigen* umrandet sie.

    Eine eben geschlossene große Öffnung ist kein Netzfehler mehr, keine
    Karte färbt sie; die Mitte allein zeigte einen Ring auf einem Teil, das
    überall gleich aussieht. Nicht in der Projektdatei: Die Auswertung
    erzeugt den Befund bei jedem Lauf neu."""
    source: MetricSource = "internal"
    suggestions: tuple[Action, ...] = ()
    """Konkrete Auswege, wenn der Befund aus einer Ausnahme entstand (§2.7)."""

    @property
    def converts_exact_body(self) -> bool:
        """Ob eine erlaubte Bauartänderung vor der Übernahme sichtbar sein muss."""
        return self.code in ("evaluate.exact_became_mesh", "brep.converted")


@dataclass(frozen=True, slots=True)
class CheckState:
    """Durchführung einer Prüfung auf der Grundlage ihres aktuellen Auftrags.

    ``completed`` belegt die vollständige Durchführung; Warnungen und Fehler
    stehen getrennt als Befunde. Fehlende Grundlagen bleiben ``not_started``.
    ``not_applicable`` setzt eine fachlich belegte Unzuständigkeit voraus.
    Der Aufrufer bindet die Werte an Dokumentrevision, Geometrie und Profile;
    sie sind keine gespeicherten Fertigmarken einer Projektdatei.
    """

    key: str
    object_id: ObjectId | None = None
    applicable: bool | None = None
    required_basis: tuple[str, ...] = ()
    missing_basis: tuple[str, ...] = ()
    state: Literal[
        "not_started", "running", "completed", "cancelled", "failed", "not_applicable"
    ] = "not_started"
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

    def unused_name(self, wanted: TranslatableText | str) -> TranslatableText | str:
        """Der Name, wenn er frei ist — sonst derselbe mit einem Zähler.

        **Zwei Objekte mit demselben Namen sind im Baum eines** (RM-097).
        *Prüfstück* und *Drehdeckel* trugen ihren Namen als festes Wort; wer
        zwei Toleranzleitern anlegte oder zwei Dosen verschloss, fand zwei
        Zeilen, die gleich heißen, und musste die richtige durch Anklicken
        suchen. Die Kopie macht es seit je anders (``scene.ops._copy_name``).

        Der Zähler beginnt bei zwei, denn der erste heißt, wie er heißt — „Deckel
        1" neben nichts wäre eine Nummer ohne Reihe. Dieselbe Zählweise wie bei
        den Passungen (``lid_flow._unused_name``); zwei Fassungen derselben
        Frage liefen auseinander.

        **Und ein übersetzbarer Name bleibt übersetzbar.** Bis zum 22.09.2026
        nahm diese Funktion ein ``str``, und die Aufrufer reichten
        ``str(_("Drehdeckel"))`` — das Wort in der Sprache, die beim Rechnen
        eingestellt war, vom Ergebnis-Cache festgehalten. Verglichen wird in
        der eingestellten Sprache, zurück kommt der Text selbst oder der Text
        mit Zähler (``{name} {number}``).
        """
        taken = {str(entry.name) for entry in self.objects.values()}
        if str(wanted) not in taken:
            return wanted
        number = 2
        while f"{wanted} {number}" in taken:
            number += 1
        if isinstance(wanted, TranslatableText):
            return _("{name} {number}", name=wanted, number=number)
        return f"{wanted} {number}"


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
    "features",
    "part",
    "filament",
    "material",
    "source",
    "image",
    "sketch",
    "strokes",
    "armature",
    "edges",
    "contours",
    "organizer",
    "step_bodies",
    "points",
]
"""``image`` ist eine Quelle, die ein Bild sein muss: Der Dialog listet nur
Bildquellen und bietet daneben an, eine von der Platte zu holen — ein
``source``-Feld bot dort jede Quelle an, also STLs in einem Feld namens
„Bild", und einen Weg zu einem Bild gab es nicht.

``contours`` speichert eine JSON-Liste geometrischer Profilkennungen. Die
Oberfläche zeigt Anzahl und Konturauswahl; Agent und Projekt behalten reine
Daten, keine Zeichengesten oder ausführbaren Inhalte.

``step_bodies`` speichert eine JSON-Liste von Körperkennungen einer
STEP-Baugruppe (P7.4, ``brep.step.StepBody.key``) — welche Körper der Datei
übernommen werden. Die Liste nennt zugleich die Zahl der Ausgänge
(``produces_from``); der leere Text ist der Stand vor P7.4, die ganze Datei als
ein Körper. Die Oberfläche zeigt die Anzahl und die Körperauswahl.

``organizer`` trägt einen begrenzten Baum von Fachteilungen und Wiederholungen.
Seine Maße benutzen denselben Ausdrucksauswerter wie gewöhnliche Parameter;
die Oberfläche zeigt dafür eine maßliche Fachaufteilung.

``sketch`` trägt eine gezeichnete Skizze als JSON-Text (§30.1) — gedacht für
den Skizzeneditor; bis er da ist, zeigt der Dialog ein Textfeld. Der Agent
bekommt diesen Parameter nicht: Grundformen statt roher Punktlisten (§26).

``strokes`` trägt eine Liste von Pinselstrichen, ebenfalls als JSON-Text und
aus demselben Grund ohne den Agenten: Ein Strich *ist* eine Koordinate, und
die KI erzeugt keine (Leitprinzip 5). ``armature`` trägt ein Skelett, dessen
Knochen ebenfalls Koordinaten sind. ``points`` trägt Punkte im Raum als Text
``x,y,z;x,y,z;x,y,z`` — die drei einer Schnittebene (RM-400), im Bild
angeklickt. Sie alle unterliegen den fünf Prüfungen aus
:mod:`tests.test_gesture_ops`.

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

    targets_feature: bool = False
    """Dieser Parameter nennt ein **Merkmal als Ziel**, ohne ``kind="feature"``
    zu sein (§30.1, D14).

    Der Unterschied zu ``kind="feature"``: Ein Ziel ersetzt nicht den Ort. Die
    Skizze liegt, wo sie liegt; ``up_to`` sagt nur, bis wohin ihre Extrusion
    reicht. Der Wert ist trotzdem eine Merkmalskennung und wird trotzdem an den
    eigenen Eingängen vorbei in der Szene nachgeschlagen — und genau daran
    hängen zwei Dinge, die es sonst am Namen festmachen müssten: der
    Auswertungs-Cache muss die Hashes der Träger in seinen Schlüssel nehmen
    (sonst bleibt die Extrusion bei z = 10, wenn der Quader auf 30 wächst), und
    ein Klick auf eine Fläche trägt sich hier ein.

    **Am Parameter und nicht als Namensvergleich**, aus demselben Grund wie
    :attr:`subtractive_on`. Vorher stand an beiden Stellen ``spec.name ==
    "up_to"``: Eine zweite Operation mit Zielfläche hätte ihren Parameter exakt
    so nennen müssen, sonst hätte der Cache still ein veraltetes Ergebnis
    geliefert."""
    reads_scene: bool = False
    """Solange dieser Schalter an ist, liest die Operation die übrigen Körper
    der Szene (Regel 3: lesen, nie ändern).

    Die Schwester von ``OperationSpec.reads_other_bodies``, nur an einem Wert
    statt an der ganzen Operation: *An eine freie Stelle legen* (``free_spot``,
    §17.1 Schritt 6) muss wissen, was schon liegt. Ein Schritt ohne den
    Schalter liest nichts davon und rechnet nicht neu, wenn davor etwas anderes
    geändert wird. Ob gelesen wird, sagt :func:`registry.params.reads_scene` —
    für den Cache-Schlüssel (``evaluate._with_nested_context``) und für die
    Frage, ob ein späterer Schritt eine Importgruppe benutzt
    (``ingest.plan.imported_group``)."""
    answered_by: tuple[str, ...] = ()
    """Die Felder, in denen der Schritt festhält, was er beim Lesen der Szene
    gefunden hat. Sind sie gesetzt, liest ``reads_scene`` nicht mehr: Die
    freie Stelle wird einmal gerechnet und kommt als Antwort in den Schritt
    (§15.7, Entscheidung Robert)."""
    feature_kinds: tuple[str, ...] = ()
    """Welche Merkmalsarten dieser Merkmalsparameter annimmt — leer heißt jede.

    Gebraucht, wo die Operation selbst keinem Merkmal gilt (kein
    ``applies_to``) und trotzdem Merkmale nennt: Die Öffnungen des Aushöhlens
    sind Flächen des Körpers, der ausgehöhlt wird (P6.3). Ein Klick auf eine
    Bohrung trägt sich dort nicht ein (``scene.placement.values_for``), und
    die Operation prüft dieselbe Menge, bevor sie rechnet — eine Auskunft,
    zwei Leser, am Parameter statt in einer Tabelle der Oberfläche."""
    optional: bool = False
    """Dieser Zahlenparameter kennt „nicht gesagt" — sein Wert darf ``None`` sein.

    **Für Zahlen, bei denen die Null ein gültiger Wert ist** (RM-154). Ein
    Textfeld hat den leeren Text dafür, ein Merkmalsfeld die leere Kennung; eine
    Koordinate hat nichts dergleichen: ``x = 0`` ist die Mitte des Teils, und
    Solidon legt einen Quader **um** den Ursprung. ``slot_hole`` und
    ``resize_hole`` lasen drei Nullen in ``x/y/z`` deshalb als „lass das Loch,
    wo es ist" — womit es sich in jede Stelle versetzen ließ außer in die
    Teilemitte, also ausgerechnet in den häufigsten Ort.

    Wo eine Null **physisch unmöglich** ist — eine Länge, ein Durchmesser —,
    braucht es das nicht: Dort ist die Null selbst schon eindeutig „nicht
    gesagt", und ein zweiter Mechanismus daneben wäre einer, der mit dem ersten
    auseinanderlaufen kann.

    Der Wert reist als ``null`` in der Projektdatei, fehlt im Werkzeugschema
    des Agenten als Pflichtfeld und steht im Dialog als leeres Feld mit einem
    Sondertext am Mindestwert."""
    internal: bool = False
    """Ein Marker, den eine Migration setzt, und kein Feld für den Kunden.

    Er reist in der Projektdatei und wirkt bei der Auswertung, steht aber
    weder im Dialog noch im Werkzeugschema des Agenten: ``measured_frame``
    hieß dort „Richtung aus einem älteren Projekt“ und stand unter jeder neuen
    Langlochbohrung, die ihn nie braucht (RM-332, N5)."""
    dropped_on_change: bool = False
    """Ein interner Marker, den eine bewusste Änderung des Schritts aufhebt.

    Die Migration setzt ihn, damit ein gespeicherter Schritt rechnet wie beim
    Speichern; wer den Schritt ändert, bekommt die heutige Rechnung, und
    ``History.change_params`` nimmt ihn heraus, sobald sich ein anderer Wert
    ändert (``legacy_slot_tool``, Migration 45 → 46). ``measured_frame`` trägt
    ihn nicht: Dort meint der Marker, wie ein Winkel gelesen wird, und gilt bei
    jeder Länge weiter."""
    sketch_planes: tuple[str, ...] = ()
    """Auf welchen Ebenen die Zeichnung dieses Skizzenfelds liegen darf.

    Leer heißt: auf jeder. Die erste ist die Vorgabe für eine leere Zeichnung.
    **Am Parameter und nicht im Editor**, aus demselben Grund wie
    :attr:`depends_on`: Die Operation weiß, was sie annimmt — die Bahn eines
    Sweeps steht senkrecht zum Querschnitt, also auf der Vorder- oder
    Seitenansicht (``brep.profiles.PATH_PLANES``). Ohne diese Angabe öffnete
    der Editor der Bahn auf der Draufsicht, der Kunde zeichnete dort, und die
    Operation lehnte ab, nachdem alles fertig war (RM-183, gefahren am
    22.09.2026)."""
    zero_text: TranslatableText | str | None = None
    """Wie die Null dieses Zahlenfelds heißt, wenn sie mehr ist als eine Zahl.

    „automatisch“, „keine“, „aus dem Material“: Bei rund hundert Parametern
    sagt die Null etwas anderes als null Millimeter, und im Feld stand
    „0,00 mm“ (RM-513). Der Dialog zeigt den Namen am Mindestwert
    (``setSpecialValueText``) — deshalb nur an Feldern mit Mindestwert 0;
    ``tests/test_registry_consistency.py`` hält beides."""


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
    bound_edges: Mapping[str, tuple[int, ...]] = field(default_factory=dict)
    """Je Kantenfeld (``kind="edges"``) die **einmal gebundene** aktuelle Auswahl.

    Die Auswertung löst ausdrücklich gewählte Kanten vor dem Cache am
    aktuellen Eingang auf, fragt bei einer Kollision den Kunden und gibt der
    Operation das Ergebnis als Indizes in den Kantenraum ihres Kerns —
    ``solid.edges()`` am exakten Körper, ``edges_of(mesh)`` am Netz
    (``scene.edge_binding``, P1.4c). Die Operation reicht sie als
    ``selected_edges`` an den Kern und löst keinen Schlüssel ein zweites Mal
    auf: Ein gerundeter Schlüssel könnte wieder zwei Kanten treffen. Leer,
    wenn kein Feld aktiv ist oder die Operation direkt aufgerufen wird — dann
    gilt der Schlüsselweg wie bisher."""


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

    feature_continuations: tuple[tuple[FeatureContinuation, ...], ...] = ()
    """Je Ausgabe die belegten Übergänge alter Merkmale — leer, wenn die
    Operation keinen nachgewiesen hat.

    Die Ausgabe ist über ihre **Position** zugeordnet, denn ihre endgültige
    Objektkennung bekommt sie erst beim Einhängen. Eine leere Folge sagt
    „kein zusätzlicher Beleg", nicht „nichts hat überlebt": Was die Operation
    unverändert durchreicht, belegt sich selbst, und für alles andere fragt
    die Auswertung die geometrische Zuordnung."""


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


RevisionKind = Literal["insert", "move", "suppress", "reactivate"]
"""Welche Handlung eine Transaktion am Verlauf selbst vorgenommen hat (P7).

``insert`` und ``move`` planen den Suffix ab der ersten geänderten Stelle mit
neuen Kennungen neu — die Reihenfolge des Stapels **ist** die seiner Kennungen
(§15). ``suppress`` und ``reactivate`` wechseln nur die Fassung der Schritte."""


@dataclass(frozen=True, slots=True)
class ReferenceExpectation:
    """Welches Merkmal ein Verweis traf, als sein Schritt zuletzt gerechnet wurde (P7.3).

    Ein ausgeschalteter Schritt rechnet nicht, und seine Verweise tragen nur
    Namen. Namen neuer Merkmale hängen aber an der Erkennungsreihenfolge: Wer
    die erste von zwei Bohrungen ausschaltet, gibt ihren Namen für die zweite
    frei. Beim Wiedereinschalten muss sich prüfen lassen, dass der Verweis
    **dasselbe** Merkmal trifft — deshalb Herkunft und Abdruck, nicht der Name
    allein (§15.7, §21.3). Ein abgeleiteter Vermerk, keine Anweisung: Er
    entscheidet nur, ob der wieder eingeschaltete Schritt ungefragt rechnen darf.
    """

    key: str
    """Die Stelle im Schritt: Parametername, bei Listen ``name:index``, bei einer
    Skizzenebene ``plane:name``."""
    feature: FeatureId
    kind: FeatureKind
    creator: OpId | None = None
    """``Feature.created_by`` des getroffenen Merkmals, falls bekannt."""
    fingerprint: Mapping[str, Any] = field(default_factory=dict)
    """``perceive.matching.fingerprint`` im Rahmen des damaligen Eingangskörpers."""


@dataclass(frozen=True, slots=True)
class ReferenceSight:
    """Was ein Verweis traf, als sein Schritt gerechnet wurde (P7) — abgeleitet, nie gespeichert.

    Die Auswertung hält es je Schritt fest, unmittelbar bevor er rechnet, und
    für die Passungen am Endstand. Ein Umbau des Verlaufs vergleicht damit
    Grundstand und Vorschlag: Trifft derselbe Verweis danach **dasselbe**
    Merkmal — gleiche Herkunft oder gleicher Abdruck —, oder hat sich nur sein
    Name verschoben, oder ist es verloren? Ohne diesen Vergleich bekäme ein
    späteres *Bohrung vergrößern* nach dem Umsortieren still die andere
    Bohrung (§21.3: nie still umbiegen).
    """

    key: str
    """:attr:`app.core.scene.orphans.Reference.key` — die Stelle ohne Schrittkennung."""
    ref: FeatureRef
    feature: Feature | None
    """Das getroffene Merkmal, oder ``None``, wenn der Name nicht auflöste."""
    candidates: Mapping[FeatureId, Feature] = field(default_factory=dict)
    """Alle Merkmale des Körpers in diesem Augenblick."""
    centre: Vec3 = (0.0, 0.0, 0.0)
    diagonal: float = 0.0
    """Der Bezugsrahmen der Zuordnung (``mesh.bounds``) — derselbe wie in ``matching``."""


@dataclass(frozen=True, slots=True)
class Suppression:
    """Warum ein Schritt nicht gerechnet wird (P7.3, seit Format v31).

    **Ausdrücklich gespeichert, auch für die Mitgenommenen.** Wer eine Bohrung
    ausschaltet, deren Loch ein späteres *Bohrung vergrößern* benennt, schaltet
    dieses mit aus (``chosen=False``) — die Auswertung überspringt nur, was
    hier steht, und errät keine Abhängigkeit. Eingeschaltet wird ein
    mitgenommener Schritt zusammen mit dem, der ihn mitnahm.
    """

    chosen: bool = True
    """Vom Nutzer gewählt — oder mitgenommen, weil er ohne einen gewählten nicht rechnen kann."""
    expects: tuple[ReferenceExpectation, ...] = ()
    fits: tuple[str, ...] = ()
    """Passungen, die ruhen, solange dieser Schritt aus ist — ihr Merkmal oder
    Körper entsteht in ihm (§14)."""


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
    matches: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    """Antworten auf mehrdeutige Merkmalszuordnungen (§15.7, §21.3).

    **Warum das nicht in ``params`` steht.** ``validate`` wiese einen
    Schlüssel ab, den das Schema der Operation nicht kennt, und richtig so: Das
    hier ist keine Eingabe der Operation, sondern eine festgehaltene Antwort auf
    eine Rückfrage, die *bei* ihr entstand. Der Präzedenzfall steht eine Zeile
    höher — ``seed`` ist ebenfalls ein Wert auf Operationsebene, der eine nicht
    von selbst reproduzierbare Prozedur reproduzierbar macht. Eine
    festgehaltene Antwort tut für eine Rückfrage dasselbe.

    Ein Eintrag bezeichnet einen Ausgabekörper und seine vollständige Gruppe
    alter Ansprüche. Kandidaten stehen als geometrische Fingerabdrücke in
    einer lokalen Tabelle; Entscheidungen wählen deren Index oder halten
    ausdrücklich ``not_carried`` fest. Neue Erkennungskennungen werden nicht
    gespeichert. ``perceive.match_records`` prüft die gemeinsame Struktur.
    Alte Einzelantworten bleiben unverändert unter ``legacy`` lesbar.

    Fingerabdrücke tragen ``kind``, ``relative``, ``axis``, ``diameter`` und
    ``directional``. Nur die Lage ist relativ zur Körperdiagonale; das
    Rohmaß ``diameter`` wird nicht normiert. Eine Antwort gilt erst nach der
    vollständigen geometrischen Wiedererkennung ihrer Kandidaten und
    Anspruchskanten. Fehlender Beleg führt erneut zur Frage (Regel 21).

    **Und es gehört nicht in den Op-Hash.** Die Zuordnung passiert *nach* dem
    Cache — ``_with_features`` läuft in beiden Zweigen, auch nach einem
    Treffer. Eine Antwort ändert also kein gecachtes Ergebnis, und nach dem
    Antworten rechnet nichts neu; anders als bei der Einheitenrückfrage, die
    ein Parameter ist. Wer das später „zur Sicherheit" in den Hash einträgt,
    macht jede beantwortete Frage zu einer vollständigen Neuberechnung.
    """
    suppressed: Suppression | None = None
    """Ausgeschaltet (P7.3): Der Schritt bleibt im Verlauf und in der Datei,
    wird aber nicht gerechnet. ``None`` ist der Normalfall."""


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
    edited_ops: Mapping[OpId, Operation | None] | None = None
    """Je Schrittkennung die vollständige Fassung dieser Seite (§15.4, §15.5).

    Für das nachträgliche Ändern eines Schritts — andere Parameter, andere
    Eingänge, der Zwilling im anderen Rechenkern: Der Schritt behält Kennung
    und Platz, nur seine Fassung wechselt, und die Transaktion trägt beide.
    Ohne dieses Feld schrieben die drei Änderungswege am Verlauf vorbei, und
    ein Strg+Z traf einen anderen Schritt, während der alte Wert
    unwiederbringlich weg war. Seit Format v12 in der Datei.

    Seit Format v17 bedeutet ``None`` als *Wert*: Der Schritt ist auf dieser
    Seite gelöscht. Die andere Seite trägt seine vollständige Fassung, damit
    Undo ihn wieder an genau seiner alten Stelle einsetzen kann."""

    spool_bindings: tuple[SpoolBinding, ...] | None = None
    """Spulenzuordnung derselben Filamentgeste; leer ist beteiligt, None unbeteiligt."""


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
    Slicer und stehen darum nicht im Verlauf. Die örtliche Spulenbindung
    gehört jedoch zur selben Filamentzuweisung wie die sichtbare Farbe und
    wird mit dieser gemeinsam zurückgenommen. Andere Druckwerte und die
    stabile Lager-Projektkennung bleiben dabei erhalten.
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
    revision: RevisionKind | None = None
    """Gesetzt, wenn die Transaktion den Verlauf selbst umbaut (P7, seit v31).

    Der Verlauf zeigt die neu geplanten Schritte einer eingefügten oder
    verschobenen Folge an ihrer neuen Stelle und blendet ihre alten Zeilen
    aus — anders als beim Löschen, wo die alte Zeile durchgestrichen als
    Geschichte stehen bleibt (§15.4)."""
    renumbered: Mapping[OpId, OpId] = field(default_factory=dict)
    """Belegte alte zu neuer Schrittkennung bei Einfügen/Verschieben (Format 45).

    Die Herkunft erhält sichtbare Benutzertitel über wiederholte Umbauten.
    Geometrie und Undo benutzen weiterhin die unveränderten stabilen Kennungen.
    """


@dataclass(frozen=True, slots=True)
class ChatEntry:
    """Ein Gesprächsbeitrag, gekoppelt an das, was er geändert hat (§26.3).

    Die Kopplung ist der Punkt: ein Beitrag nennt die Transaktion, die er
    erzeugt hat, und wird sie zurückgenommen, gilt der Beitrag als verworfen.
    Ohne das argumentiert der Agent nach jedem Undo mit einem Zustand, den es
    nicht mehr gibt.

    Eine ausdrückliche Ablehnung wird gespeichert. Bei angenommenen Vorschlägen
    folgt der Zustand weiterhin aus der Transaktion; ein Redo holt diese von
    selbst zurück.
    """

    id: str
    role: ChatRole
    text: str
    transaction_id: TransactionId | None = None
    origin: Origin | None = None
    """Gefüllt bei Agentenbeiträgen: Modell, Prompt- und Regelversion,
    Temperatur (§26.4)."""
    discarded: bool = False
    """Ausdrücklich verworfen, bevor eine Transaktion übernommen wurde."""


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
    export_format: str = ""
    """Das zuletzt benutzte Ausgabeformat dieses Projekts (§29, RM-141).

    §29 sagt „Ordner, Format und Übergabeart werden je Projekt gemerkt", und
    die Übergabeart steht mit derselben Begründung in
    :attr:`PrintSettings.handover`: Sie gehört zum Teil und nicht zum Rechner.
    Ein Gehäuse, das als 3MF zum Slicer geht, geht beim nächsten Mal wieder
    als 3MF; ein Modell für einen Dienstleister bleibt STL.

    Leer heißt „noch nie exportiert" — dann gilt 3MF, der vorgeschlagene
    Kundenweg. Als ``str`` und nicht als ``ExportFormat``: Der Literal-Typ
    lebt in ``export/writer.py``, und der Kern der Szene kennt den Schreiber
    nicht. Eine Datei mit einem unbekannten Wert fällt beim Lesen auf die
    Vorgabe zurück, statt den Export zu verweigern.

    **Der Ordner steht ausdrücklich nicht hier**: Er ist ein absoluter Pfad
    und gehört damit nicht in eine Projektdatei (Regel 12). Er bleibt beim
    Gerät, in ``UiSettings.export_dirs`` — derselbe Schnitt wie beim
    Slicer-Pfad neben der Übergabeart.
    """
    export_scheme: str = ""
    """Wie die Dateien heißen, wenn eine je Körper entsteht (§29, RM-141).

    Ein Muster mit Platzhaltern, ``{project}_{object}_{index}von{count}`` als
    Vorgabe — die Felder zählt ``export.writer.SCHEME_FIELDS`` auf. Leer heißt
    „die Vorgabe, passend zur Zahl der Teile und Platten"; gemerkt wird nur,
    was jemand ausdrücklich getippt hat.
    """
    protected: dict[ObjectId, tuple[FeatureId, ...]] = field(default_factory=dict)
    """Welche Merkmale je Körper als Sichtflächen gesperrt sind (§22.3, RM-080).

    „Diese Fläche soll schön bleiben": Die Trennebenensuche von *Automatisch
    teilen* legt keine Naht durch ein gesperrtes Merkmal. **Im Dokument und
    nicht in der Ansicht**, weil eine Sichtfläche eine Aussage über das Teil
    ist und nicht über die Sitzung — als Ansichtszustand war sie nach dem
    Schließen weg, und der Kunde erfuhr es an dem Schnitt, der durch die
    Fläche ging, die er schützen wollte (Entscheidung 31.08.2026).

    Gespeichert werden **Merkmalkennungen**, keine Dreiecke und keine Punkte:
    Kennungen sind stabil über Auswertungen hinweg (§21), Dreiecksnummern
    nicht, und die Punktwolke rechnet die Suche einmal beim Start aus dem
    ausgewerteten Netz (:func:`app.core.split.protected_patches`). Ein
    Eintrag zu einem Körper, den es gerade nicht gibt — gelöscht, noch nicht
    wieder hergestellt —, bleibt stehen: Ein Undo bringt den Körper zurück,
    und seine Sperre soll dann noch da sein.

    Keine Operation und keine Transaktion, aus demselben Grund wie die
    Druckeinstellungen: Es entsteht keine Geometrie und es ändert sich keine.
    Der Umschalter am Merkmal ist sein eigener Rückweg. Seit Format v24 in der
    Datei.
    """
    carried_profiles: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    """Die eigenen Drucker und Materialien, die das Projekt mitnimmt (seit Format v30).

    ``{"printers": {Kennung: Tabelle}, "materials": {…}}`` — dieselbe Form wie
    ``printers.toml`` und ``materials.toml`` des Nutzers: Maße, Zahlen, Namen,
    kein Pfad und kein Code. Ein Projekt mit einem eigenen Drucker rechnet so
    auch auf einem Rechner, der ihn nicht kennt (``profiles.carry``); vorher
    endete es dort bei „Dieses Druckerprofil ist nicht bekannt." Das Speichern
    füllt das Feld aus dem Bestand des Rechners
    (``profiles.carried_definitions``), mitgelieferte Profile stehen nie darin.
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
    taper_length: float = 0.0
    """Wie viel Außenkontur dieser Schicht auf einem **Keil** liegt, in
    Millimetern (§22.2): einer Wand, deren Stärke stetig über mehrere Bahnen
    läuft, statt zu springen oder gleich zu bleiben.

    Ein runder Becher, der eine Außenwand von innen berührt, macht aus zwei
    Wänden von je einem Millimeter auf zwei Zentimetern Umfang eine von drei —
    und ein Slicer mit variabler Bahnbreite wechselt dort die Wandzahl Bahn
    für Bahn. Zuerst gelegte Innenwände zeichnen diese Übergänge durch die
    Außenwand ab (Organizer vom 20.09.2026). Null heißt: keine solche Stelle.

    Gemessen an jeder :data:`~app.core.slice.analysis.TAPER_SAMPLE`. gemessenen
    Schicht, dazwischen fortgeschrieben — ein Keil ist eine Eigenschaft der
    Wand über ihre Höhe, und die Messung kostete an einer Vase ein Drittel der
    ganzen Analyse."""


@dataclass(frozen=True, slots=True)
class SliceResult:
    """Ergebnis des Analyse-Schneiders. Seine Zahlen werden nie mit G-Code
    vermischt (§22.5)."""

    layers: tuple[LayerInfo, ...]
    support_volume: float
    first_layer_area: float
    source: MetricSource = "internal"


# --- Skizzen (§30.1) -----------------------------------------------------------

SketchElementKind = Literal["point", "line", "arc", "circle", "spline", "ellipse", "elliptical_arc"]
SketchConstraintKind = Literal[
    "distance",
    "radius",
    "diameter",
    "coincident",
    "horizontal",
    "vertical",
    "parallel",
    "perpendicular",
    "tangent",
    "symmetric",
    "fixed",
    "reference",
    "angle",
    "equal",
    "midpoint",
    "on_curve",
    "smooth",
    "curvature",
]
"""Die Arten von Zwangsbedingungen (§30.1).

``angle`` misst den Winkel zwischen zwei Linien in Grad, ``equal`` hält zwei
Spannen gleich lang (zwei Linien, zwei Radien), ``midpoint`` setzt einen Punkt
auf die Mitte einer Linie.

**Drei Arten nennen Kurven statt Punkte** (RM-188 P6.6b): Eine Kurve steht
als der flache Index des ersten Punkts ihres Elements im Ziel. ``on_curve``
(Punkt, Kurve) setzt einen Punkt auf eine Linie — die Gerade durch sie —,
einen Kreis, Bogen, eine Ellipse, einen Ellipsenbogen oder einen Spline.
``smooth`` (Punkt an A, Kurve A, Punkt an B, Kurve B) macht zwei Kurven an
einer Stelle tangentenstetig, ``curvature`` mit denselben Zielen zusätzlich
krümmungsstetig — beides ohne die Deckung der Punkte, die dafür eine eigene
``coincident`` trägt. Bei einem Spline ist die Stelle einer seiner Punkte,
bei ``curvature`` eines seiner Enden.

**Konzentrisch steht hier nicht**, und das ist eine Entscheidung: Zwei Kreise
mit gemeinsamer Mitte sind die Deckung ihrer Mittelpunkte — ``coincident`` auf
zwei Punkten. Eine eigene Art wäre ein zweiter Name für denselben Sachverhalt
und damit zwei Wege, ihn zu speichern. Die Oberfläche bietet den Griff unter
dem Wort an, das ein CAD-Kunde sucht; das Datenmodell bleibt eines."""


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
    bleibt unberührt — auch seine Punkte sind Punkte.

    ``ellipse`` trägt Mittelpunkt, das Ende der ersten Achse und das Ende der
    zweiten (RM-188 P6.6a). Die zweite steht senkrecht auf der ersten — das
    ist die eigene Gleichung des Elements, wie beim Bogen die gleich langen
    Schenkel —, und ihre Länge ist die zweite Halbachse. Welche der beiden die
    längere ist, legt die Reihenfolge nicht fest: Gezeichnet wird meist die
    Hauptachse zuerst, gezogen darf jede werden. ``elliptical_arc`` trägt
    dieselben drei Punkte und dazu Anfang und Ende, die auf der Ellipse liegen;
    der Bogen läuft wie ein Kreisbogen **gegen den Uhrzeigersinn** vom Anfang
    zum Ende. Auch hier sind alle Freiheitsgrade Punktkoordinaten."""

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
    darf Projektparameter lesen; nur ein Maß trägt einen — ``distance``,
    ``radius`` und ``diameter`` in Millimetern, ``angle`` in Grad."""

    kind: SketchConstraintKind
    targets: tuple[int, ...]
    value: str = ""


@dataclass(frozen=True, slots=True)
class Sketch:
    """Eine 2D-Skizze auf einer Ebene (§30.1).

    ``plane`` ist ``plane:xy``, ``plane:xz``, ``plane:yz`` oder
    ``feature:<object_id>:<feature_id>`` für eine erkannte planare Fläche.
    Die ältere Schreibweise ``feature:<feature_id>`` bleibt lesbar."""

    plane: str
    elements: tuple[SketchElement, ...]
    constraints: tuple[SketchConstraint, ...] = ()


@dataclass(frozen=True, slots=True)
class PlaneFrame:
    """Wohin eine Skizzenebene im Raum zeigt (§30.1).

    Der Ursprung ist der Nullpunkt der Zeichnung, ``x_axis`` und ``y_axis``
    sind ihre beiden Richtungen, ``normal`` steht senkrecht darauf und ist die,
    in die extrudiert wird. Alle drei sind Einheitsvektoren und rechtshändig.

    Bei den drei Hauptebenen steht das fest. Bei einer ``feature:``-Ebene wird
    der Rahmen aus der Fläche gerechnet — siehe ``app.core.sketch.planes``."""

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
    gesture: int = 0
    """Gemeinsame Kennung aller Proben eines Mauszuges. Null bezeichnet
    einen einzeln rücknehmbaren Altzug; die Kennung verändert keine Geometrie."""


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
