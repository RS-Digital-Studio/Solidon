"""Jeder Baustein als Operation (Bauplan §24.1, §10).

Ein Baustein wird einmal deklariert und wird aus dieser Deklaration eine
Operation — Menüeintrag, Dialog, Kommandozeile, Agentenwerkzeug und
Katalogeintrag folgen alle daraus (Leitprinzip 3). Nichts hier ist je Baustein
geschrieben; einen Baustein zur Bibliothek hinzuzufügen fügt ihn überall hinzu.

Die Operation nimmt die eigenen Parameter des Bausteins plus den Ort, an den er
gehört: Position, Achse, Winkel. Ein abziehender Baustein wird aus dem Körper
geschnitten, ein hinzufügender mit ihm vereint, und welcher von beiden es ist,
kommt aus der Deklaration — der Nutzer muss nicht wissen, dass eine
Mutternfalle ein Loch ist und eine Rippe nicht.

Das Spiel, das eine Passung braucht, steht auch nicht im Baustein. Ein Baustein
deklariert ``play`` und lässt es auf null; hier wird es aus dem kalibrierten
Materialprofil gefüllt (AGENTS.md Regel 7) — und genau das lässt eine spätere
Kalibrierung alte Projekte erreichen.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Container, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final, cast, overload

from app.core.errors import (
    CANCEL,
    CHANGE_SIZE,
    CORRECT_INPUT,
    SHOW_LOCATION,
    Action,
    AppError,
    GeometryError,
    InternalError,
    ValidationError,
)
from app.core.expressions import resolve as resolve_parameters
from app.core.geom.boolean import (
    BOOLEAN_OVERLAP,
    BooleanKind,
    body_split,
    boolean,
    deepest,
    fell_apart,
    pieces,
    without_effect,
)
from app.core.geom.mesh import MeshData, as_mesh_data, concatenated
from app.core.geom.transform import along as lying_along
from app.core.geom.transform import composed, rotation, rotation_about, translation
from app.core.knowledge.parts.registry import PARTS, PartRegistry, PartSpec
from app.core.knowledge.parts.shapes import Kernel, building
from app.core.knowledge.profiles import for_object
from app.core.knowledge.strength import spring_load
from app.core.log import get_logger
from app.core.registry import Registry, op_params, param, register_op
from app.core.registry.params import SurfaceBoundParams
from app.core.types import (
    BaseParams,
    BRepBody,
    CancelToken,
    Feature,
    Finding,
    Mesh,
    OpContext,
    OpResult,
    PartResult,
    Profile,
    Quality,
    SceneObject,
    Vec3,
)
from app.core.units import (
    DEGREE_UNIT,
    EPS_GEOM,
    MAX_FACET_SAG,
    dot3,
    exact_acos_degrees,
    format_length,
)
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from app.core.brep.kernel import Solid

_log = get_logger(__name__)

#: Name des Parameters, den ein Baustein für die Toleranz benutzt, die er
#: braucht. Null heißt: aus dem Profil füllen.
PLAY_FIELD = "play"

#: Das Gegenstück zum Spiel: ein Übermaß, mit dem ein Teil klemmt statt
#: gleitet. Es steht im Profil als ``press`` und dort negativ — Regel 7 gilt
#: für beide Richtungen.
GRIP_FIELD = "grip"

#: Ortsangaben, die jede Baustein-Operation zusätzlich zu ihren eigenen bekommt.
#: Die Erklärungen stehen hier und nicht bei den achtzehn Bausteinen: dieselbe
#: Zahl bedeutet überall dasselbe, und einmal geschrieben kann sie nicht an
#: siebzehn Stellen anders lauten.
#:
#: **Die drei Koordinaten liegen hinten** (Konzept P15 §5): sie sind bei jedem
#: Baustein dieselben und sagen nichts über ihn — vorn standen damit drei
#: Felder, die vom eigentlichen Maß ablenken. Wer eine Fläche angeklickt hat,
#: bekommt sie ohnehin eingetragen; wer den Baustein danach bewegt, nimmt das
#: Gizmo (§18.11). ``at_feature`` bleibt vorn, denn das ist die fachliche
#: Frage „wohin" und keine abgelesene Zahl.
_PLACEMENT: tuple[tuple[str, Any, Any], ...] = (
    (
        "x",
        "float",
        param(
            title=_("Position X"),
            default=0.0,
            unit="mm",
            placement="advanced",
            doc=_(
                "Wo der Baustein sitzt, gemessen im Koordinatensystem des Objekts. "
                "Eine angeklickte Fläche trägt den Wert selbst ein."
            ),
        ),
    ),
    (
        "y",
        "float",
        param(
            title=_("Position Y"),
            default=0.0,
            unit="mm",
            placement="advanced",
            doc=_("Zweite Achse der Position — siehe Position X."),
        ),
    ),
    (
        "z",
        "float",
        param(
            title=_("Position Z"),
            default=0.0,
            unit="mm",
            placement="advanced",
            doc=_("Höhe über der Grundfläche des Objekts."),
        ),
    ),
    (
        "nx",
        "float",
        param(
            title=_("Richtung X"),
            default=0.0,
            placement="advanced",
            doc=_(
                "Richtung nach außen an der gewählten Oberfläche. Drei Nullen verwenden die Achse."
            ),
        ),
    ),
    (
        "ny",
        "float",
        param(
            title=_("Richtung Y"),
            default=0.0,
            placement="advanced",
            doc=_("Zweite Komponente der Oberflächenrichtung — siehe Richtung X."),
        ),
    ),
    (
        "nz",
        "float",
        param(
            title=_("Richtung Z"),
            default=0.0,
            placement="advanced",
            doc=_("Dritte Komponente der Oberflächenrichtung — siehe Richtung X."),
        ),
    ),
    (
        "axis",
        "str",
        param(
            title=_("Achse"),
            default="z",
            choices=("x", "y", "z"),
            placement="advanced",
            doc=_(
                "Richtung, in die der Baustein zeigt — solange kein Merkmal "
                "gewählt ist. Eine angeklickte Fläche bestimmt sie selbst."
            ),
        ),
    ),
    (
        "angle",
        "float",
        param(
            title=_("Drehung"),
            default=0.0,
            unit=DEGREE_UNIT,
            minimum=-360.0,
            maximum=360.0,
            placement="advanced",
            doc=_(
                "Dreht den Baustein um seine eigene Achse. Wichtig bei allem, was "
                "nicht rund ist — eine Mutternfalle muss zur Wand passen, durch die "
                "die Mutter eingeschoben wird."
            ),
        ),
    ),
    (
        "at_feature",
        "str",
        param(
            title=_("An Merkmal"),
            kind="feature",
            default="",
            # Hinten wie die Lage selbst: Vorn nennt der Dialog die gewählte
            # Stelle in einer Lesezeile (RM-513), ein Klick ins Bild setzt sie.
            placement="advanced",
            doc=_(
                "Name eines erkannten Merkmals, zum Beispiel hole_1. Dann zählt "
                "dessen Ort, und die Position darüber wird als Versatz gerechnet."
            ),
        ),
    ),
    (
        "at_features",
        "tuple[str, ...]",
        param(
            title=_("An mehreren Merkmalen"),
            kind="features",
            default=(),
            placement="advanced",
            doc=_(
                "Mehrere erkannte Merkmale auf einmal. Der Baustein wird an jedes "
                "davon gesetzt — ein Schritt im Verlauf, ein Strg+Z. Leer heißt: "
                "es gilt das einzelne Merkmal darüber."
            ),
        ),
    ),
)

#: Die gespeicherte Flächenbindung (§17.1): gewählte Fläche, Ansatzpunkt und
#: die beiden Kantenabstände. Sie reist an jedem Baustein mit, gehört aber
#: nicht zu den Ortsangaben, die der Agent liest — die Bindung entsteht am
#: Fenster. Deshalb eine eigene Gruppe neben :data:`_PLACEMENT`, dessen Namen
#: ``registry.surfaces.PART_PLACEMENT_PARAMS`` wörtlich spiegelt.
_SURFACE_BINDING: tuple[tuple[str, Any, Any], ...] = tuple(
    (entry.name, entry.type, entry) for entry in SurfaceBoundParams.fields()
)


#: Der Namensraum der Bausteinoperationen. Als Konstante, weil ihn zwei
#: Richtungen brauchen: :func:`op_name` setzt ihn, :func:`part_of` nimmt ihn ab.
_PREFIX = "insert_"


def op_name(part: str) -> str:
    """``screw_hole`` wird ``insert_screw_hole`` — ein Namensraum, keine
    Kollisionen.
    """
    return f"{_PREFIX}{part}"


def creator_name(part: str) -> str:
    """``wall_hook`` wird ``create_wall_hook`` — der Name des Erzeugers, ob es ihn
    gibt oder nicht. Welche Operation den Baustein anlegt, sagt
    :func:`creation_name`; welche ihm gehören, :func:`operation_names`.
    """
    return f"create_{part}"


def creation_name(part: str) -> str:
    """Die Operation, die diesen Baustein ohne Träger anlegt — sonst die, die ihn einsetzt."""
    spec = PARTS.get(part)
    return creator_name(part) if spec.standalone else op_name(part)


#: Welche Merkmalsart als welche Stelle zählt. Eine gerundete Seite trägt einen
#: Flächenbaustein, wie das Handbuch es verspricht (Review M3); der Einsetzweg
#: nimmt jedes Merkmal mit Mitte und Richtung.
_PLACES: Final = {"face": "face", "curved_face": "face", "hole": "hole"}


def catalog_operation(part: str, *, at: Sequence[str] = ()) -> str:
    """Was der Katalog für diesen Baustein ausführt (RM-562).

    ``at`` sind die Arten der gewählten Merkmale (``face``, ``hole`` …), eine
    je markierter Zeile. Ein eigenständiger Baustein setzt sich an, wenn
    **jede** gewählte Stelle zu ihm passt (:func:`fitting_places`) — vier
    markierte Seitenflächen ergeben vier Rippen in einem Schritt (Review M2);
    sonst entsteht er als eigener Körper, eine Schraube an einer Fläche also
    frei. **Ein gewählter Körper allein zählt nicht als Stelle**: Jeder
    Erzeugerschritt wählt seinen neuen Körper, und der zweite Kabelclip hinge
    sonst am ersten. Die übrigen Bausteine werden immer eingesetzt.
    """
    spec = PARTS.get(part)
    fits = fitting_places(part)
    if not spec.standalone or (at and all(_PLACES.get(kind) in fits for kind in at)):
        return op_name(part)
    return creation_name(part)


def fitting_places(part: str) -> tuple[str, ...]:
    """Die Arten von Stellen, an die dieser Baustein gehört — ``face``, ``hole``."""
    return tuple(_applies_to(PARTS.get(part)))


def footprint_at_once(part: str) -> bool:
    """Ob der Umriss eines Bausteins ohne nennenswerte Rechnung da ist (Review N3).

    Die Bibliothek baut ihre Vorgaben in höchstens 0,36 s (Gewindebolzen,
    gemessen über alle eigenständigen). Ein Rezept rechnet dafür seinen ganzen
    Stapel, mit dem Rezept wachsend — das gehört nicht vor einen Dialog in den
    Hauptthread.
    """
    return PARTS.get(part).source == "shipped"


def free_spot_for(
    part: str, objects: Sequence[SceneObject], profile: Profile, *, rough: bool = False
) -> dict[str, float]:
    """Wohin ein eigenständiger Baustein aus dem Katalog kommt, wenn schon Körper stehen.

    Ohne Lage entsteht ein Erzeuger im Ursprung — dort, wo meist der erste
    Grundkörper steht, und eine Rippe lag dann ganz in ihm (Review M1). Die
    Stelle sucht dieselbe Regel wie beim Laden eines weiteren Modells
    (``prepare.first_free_spot``), für den Umriss mit den Vorgaben; gibt der
    Baustein ohne Zeichnung keinen Umriss her, gilt ein kleiner Platzhalter.
    ``rough`` nimmt den Platzhalter ohne zu rechnen: die erste Antwort, bis ein
    Arbeiter den echten Umriss hat (:func:`footprint_at_once`).
    Zurück kommen die Ortsfelder des Erzeugers, leer ohne vorhandene Körper.
    """
    from app.core.geom.prepare import first_free_spot
    from app.core.types import BoundingBox

    if not objects:
        return {}
    spec = PARTS.get(part)
    if rough or any(entry.required for entry in spec.params.spec()):
        footprint = BoundingBox(minimum=(-5.0, -5.0, 0.0), maximum=(5.0, 5.0, 10.0))
    else:
        footprint = placement_tools(spec, {}, profile, standalone=True)[0].bounds
    shift, _plate, _crowded = first_free_spot(
        footprint, profile, [(entry.mesh.bounds, entry.plate) for entry in objects]
    )
    fields = placement_fields(build_params(spec, standalone=True))
    return {fields["x"]: float(shift[0]), fields["y"]: float(shift[1])}


def part_of(operation: str) -> PartSpec | None:
    """Der Baustein hinter einem Operationsnamen — die Umkehrung von
    :func:`op_name`.

    ``None`` für alles, was kein Baustein ist: Der Präfix allein ist kein
    Beweis, und eine Operation, die zufällig so heißt, darf hier nicht in einen
    Fehler laufen.
    """
    for prefix in (_PREFIX, "create_"):
        if operation.startswith(prefix):
            name = operation[len(prefix) :]
            if PARTS.has(name):
                spec = PARTS.get(name)
                if prefix == _PREFIX or spec.standalone:
                    return spec
    return None


def build_params(spec: PartSpec, *, standalone: bool = False) -> type[BaseParams]:
    """Die Parameter des Bausteins plus den Ort, an den er gehört, als ein
    Schema (§10).

    Der Erzeuger (``standalone``) hat keinen Träger, von dem etwas abzutragen
    wäre: Die abtragende Wahl (``subtractive_on``) fehlt in seinem Schema, und
    der Baustein baut mit ihrer Vorgabe, der aufgesetzten Form — das Register
    stellt sicher, dass es genau eine gibt.
    """
    cutting = cuts_by_parameter(spec.params) if standalone else None
    normal = ("nx", "ny", "nz")
    owned = {entry.name for entry in spec.params.fields()}
    while owned.intersection(normal):
        normal = (f"surface_{normal[0]}", f"surface_{normal[1]}", f"surface_{normal[2]}")
    names = dict(zip(("nx", "ny", "nz"), normal, strict=True))
    occupied = owned | set(normal)
    for field, _annotation, _declaration in (*_PLACEMENT, *_SURFACE_BINDING):
        if field in names:
            continue
        public = field
        while public in occupied:
            public = f"placement_{public}"
        names[field] = public
        occupied.add(public)
    namespace: dict[str, Any] = {
        "__annotations__": {},
        "_surface_normal_fields": normal,
        "_placement_fields": names,
    }
    for entry in spec.params.fields():
        if cutting is not None and entry.name == cutting[0]:
            continue
        namespace["__annotations__"][entry.name] = entry.type
        namespace[entry.name] = (
            dataclasses.field(default=entry.default, metadata=entry.metadata)
            if entry.default is not dataclasses.MISSING
            else dataclasses.field(metadata=entry.metadata)
        )
    for name, annotation, declaration in (*_PLACEMENT, *_SURFACE_BINDING):
        if standalone and name == "at_feature":
            continue
        if standalone and name == "at_features":
            # Ein Erzeuger setzt an kein Merkmal. Das Feld bleibt, damit ein
            # gespeicherter Schritt mit einer Liste darin weiter lädt, steht aber
            # weder im Dialog noch beim Agenten und fällt bei der nächsten
            # Änderung weg (Review B, Feld ohne Wirkung).
            declaration = param(
                title=_("An mehreren Merkmalen"),
                kind="features",
                default=(),
                placement="advanced",
                internal=True,
                dropped_on_change=True,
                doc=_(
                    "Mehrere erkannte Merkmale auf einmal. Der Baustein wird an jedes "
                    "davon gesetzt — ein Schritt im Verlauf, ein Strg+Z. Leer heißt: "
                    "es gilt das einzelne Merkmal darüber."
                ),
            )
        name = names.get(name, name)
        namespace["__annotations__"][name] = annotation
        # Dataclass setzt Field.name beim Aufbau. Geteilte Deklarationen
        # würden dadurch nachträglich frühere Schemas umbenennen.
        namespace[name] = dataclasses.field(
            default=declaration.default, metadata=declaration.metadata
        )

    made = type(f"{_camel(spec.name)}OpParams", (BaseParams,), namespace)
    return op_params(made)


def placement_fields(params: type[BaseParams]) -> dict[str, str]:
    """Ordnet fachliche Platzierungsnamen kollisionsfrei den gespeicherten Feldern zu."""
    declared = getattr(params, "_placement_fields", None)
    if declared is not None:
        return dict(declared)
    return {name: name for name, _annotation, _declaration in (*_PLACEMENT, *_SURFACE_BINDING)}


def _placement_value(params: Any, name: str, default: Any = None) -> Any:
    """Liest eine Ortsangabe, ohne ein gleichnamiges Bausteinmaß zu verwenden."""
    return getattr(params, placement_fields(type(params))[name], default)


def normal_fields(params: type[BaseParams]) -> tuple[str, str, str]:
    """Die Richtungsfelder des Op-Schemas, getrennt von gleichnamigen Rezeptmaßen."""
    names = getattr(params, "_surface_normal_fields", ("nx", "ny", "nz"))
    return names[0], names[1], names[2]


def depth_field(
    operation: str, params: type[BaseParams], values: BaseParams | None = None
) -> str | None:
    """Das Feld, das angibt, wie tief ein platziertes Werkzeug ins Material geht.

    Es beantwortet die Frage, ob ein Ort allein die Platzierung schon fertig
    macht: Eine Bohrung hat eine Tiefe und ist mit dem Klick erst zur Hälfte
    gesetzt, ein Lochwand-Einhänger hat keine und ist fertig. Die
    Oberflächenplatzierung liest das, um nach dem Klick in die Tiefenstufe zu
    gehen (Robert, 09.09.2026: „wenn wir klicken wollen wir die bohrung von der
    seitenansicht sehen und dann die tiefe runterziehen").

    **Der Name allein trägt die Auskunft nicht.** Zwölf Operationen führen ein
    Längenfeld ``depth``, und bei dreien kann es nach *außen* gehen: die Nase
    von ``insert_latch`` steht vor und trägt nur als Aussparung ab,
    Beschriftung und Textur sind erhaben oder eingelassen, je nach ``mode``.
    Ein Zug nach unten hätte dort einen Wert vergrößert, der nichts abträgt —
    genau die Verwechslung, vor der ``placement_fields`` warnt, nur eine Ebene
    tiefer. Gefragt wird deshalb
    zusätzlich nach der **Richtung**, und zwar aus derselben Quelle, aus der
    auch die Boolesche Operation und die Vorschaufarbe sie lesen
    (:func:`cuts`, :func:`cuts_by_parameter`).

    Ohne Werte zählt ein Umschalter als abtragend — er **kann** es sein, und
    die Tiefenstufe ist ein Angebot und keine Sperre; sobald der Dialog Werte
    hat, entscheidet der gewählte Wert.
    """
    for entry in params.spec():
        if entry.name == "depth" and entry.unit == "mm":
            break
    else:
        return None
    part = part_of(operation)
    if part is not None:
        return "depth" if cuts(part, values) else None
    declared = cuts_by_parameter(params)
    if declared is None:
        # Keine Richtungsangabe und kein Baustein: eine Operation, die ein
        # ``depth`` führt und nirgends sagt, dass sie aufträgt, trägt ab —
        # ``drill_hole``, ``plug_hole``, ``sketch_pocket``.
        return "depth"
    name, wanted = declared
    if values is None:
        return "depth"
    return "depth" if getattr(values, name, None) in wanted else None


def _camel(name: str) -> str:
    return "".join(word.capitalize() for word in name.split("_"))


def register_all(
    parts: PartRegistry | None = None, registry: Registry | None = None
) -> tuple[str, ...]:
    """Deklariert eine Operation je Baustein. Gibt die Operationsnamen zurück."""
    source = parts or PARTS
    made: list[str] = []
    for spec in source.all():
        name = op_name(spec.name)
        target = registry or _default_registry()
        if not target.has(name):
            _register_one(spec, build_params(spec), registry)
            made.append(name)
        if spec.standalone and not target.has(creator_name(spec.name)):
            _register_creator(spec, registry)
            made.append(creator_name(spec.name))
    _log.info("registered %d part operations", len(made))
    return tuple(made)


def _default_registry() -> Registry:
    from app.core.registry import REGISTRY

    return REGISTRY


def cuts_by_parameter(params: type[BaseParams]) -> tuple[str, tuple[str | bool, ...]] | None:
    """Der Parameter, der über die Richtung entscheidet, und seine Werte —
    oder ``None``, wenn der Baustein eine feste Richtung hat.

    Gelesen aus ``ParamSpec.subtractive_on``, also von dort, wo die Wahl
    getroffen wird. Drei Stellen brauchen die Auskunft, und ohne diese Funktion
    hätte jede ihre eigene Version: die Operation (welche Boolesche Op), der
    Registereintrag (ob ein Flächenklick den Baustein anbietet) und die
    Vorschau (welche Farbe).
    """
    for entry in params.spec():
        if entry.subtractive_on is not None:
            return entry.name, tuple(entry.subtractive_on)
    return None


def cuts(spec: PartSpec, values: BaseParams | None) -> bool:
    """Trägt dieser Baustein mit diesen Werten ab?

    Ohne Werte — beim Anlegen der Operation, wo noch niemand etwas gewählt hat
    — zählt ein Baustein mit Richtungsparameter als abtragend: er **kann** es
    sein, und ``applies_to`` ist eine Reihenfolge und keine Sperre.
    """
    declared = cuts_by_parameter(spec.params)
    if declared is None:
        return spec.subtractive
    name, wanted = declared
    if values is None:
        return True
    return getattr(values, name, None) in wanted


def _applies_to(spec: PartSpec) -> list[str]:
    """An welchen Merkmalen der Baustein im Kontextmenü erscheint.

    Beides sagt der Baustein selbst (``at_face``, ``at_hole``) — hier wird nur
    übersetzt. Bis zum 24.08.2026 wurde die Fläche stattdessen **geraten**,
    und die Regel war die falsche: „trägt Material ab" bot sie an, und damit
    fehlten Wandhalter, Rippe und vier weitere in jedem Flächenmenü. Warum
    Abtragen und Anbauen nicht dieselbe Frage sind, steht am Feld
    (``registry.PartSpec.at_face``).
    """
    at: list[str] = []
    if spec.at_hole:
        at.append("hole")
    if spec.at_face:
        at.append("face")
    return at


def register_one(spec: PartSpec, registry: Registry | None = None) -> None:
    """Einen einzelnen Baustein als Operation registrieren — der Weg der
    Rezepte. ``register_all`` bleibt der der Bibliothek; beide enden hier.

    Ein eigenständiger Baustein bekommt auch hier seinen Erzeuger: Ein Rezept
    ist genau ein Körper (RM-574). Scheitert der Erzeuger, geht das Einsetzen
    mit zurück — halb registriert wäre ein Katalogknopf ohne Rechnung.
    """
    _register_one(spec, build_params(spec), registry)
    if spec.standalone:
        try:
            _register_creator(spec, registry)
        except Exception:
            (registry or _default_registry()).remove(op_name(spec.name))
            raise


def operation_names(part: str, parts: PartRegistry | None = None) -> tuple[str, ...]:
    """Die Operationen, die diesem Baustein gehören — Einsetzen immer, Erzeugen,
    wenn er für sich steht (RM-574).

    Wer einen Baustein abmeldet oder ersetzt, nimmt genau diese. Den Erzeuger
    nur nach dem Namen zu nehmen träfe bei einem Rezept „box“ den Quader
    ``create_box``, der keinem Baustein gehört — dieselbe Zugehörigkeit, die
    :func:`part_of` liest. Deshalb vor dem Abmelden des Katalogeintrags fragen.
    """
    source = parts or PARTS
    if source.has(part) and source.get(part).standalone:
        return op_name(part), creator_name(part)
    return (op_name(part),)


def _register_one(spec: PartSpec, params: type[BaseParams], registry: Registry | None) -> None:
    title = _title_for(spec)

    @register_op(
        name=op_name(spec.name),
        title=title,
        category="parts",
        # targets:4 — ein abtragender Baustein, der keine Schicht wegnimmt,
        # sagt es (``parts.cuts_no_layer``, Durchsicht 0.5.1); targets:5 — ein
        # lösbares Teil urteilt selbst, ob sein Träger zerfallen ist
        # (``_host_split``), und ein schräg gesetzter abtragender Baustein
        # öffnet bis über seine Fläche (``_opened_to_the_face``): Ein Ergebnis
        # von davor trüge weder den Satz noch die freie Öffnung. targets:7 —
        # in einer Bohrung, die schon weiter ist, sagt er das statt „neben
        # dem Körper“ (``parts.bore_too_wide``).
        cache_version=f"{_result_version(spec)}:targets:7",
        params=params,
        consumes=1,
        produces=1,
        applies_to=_applies_to(spec),
        touches_features=True,
        leaves_separate_parts=spec.separate_from_host,
        doc=spec.doc or title,
        caveat=spec.caveat,
        registry=registry,
    )
    def run(ctx: OpContext, _spec: PartSpec = spec) -> OpResult:
        return insert(ctx, _spec)


def _exact_kernel_here() -> bool:
    """Ob der exakte Kern auf dieser Maschine rechnet — die Probe des Registers, gemerkt."""
    from app.core.registry.registry import probe_exact_kernel

    return probe_exact_kernel()


def _creates_exactly(spec: PartSpec) -> bool:
    """Ob der Erzeuger dieses Bausteins im exakten Kern baut, wo der Kern da ist.

    **Eine Vorlage entsteht wie ein Grundkörper** (RM-443, ``menu_twins``): Sie
    ist der Anfang einer Konstruktion — Maße als Parameter, danach Bohrungen,
    Rundungen, Fasen —, und dafür braucht sie echte Flächen und Kanten. Die
    Halter bauten bis hierher im Kundenweg immer ein Netz; ihre exakte Fassung
    war nur im Test erreichbar. Prüfkörper, Organizerteile und Dichtungen sind
    keine Vorlage und bleiben beim Netz, wie ihre gespeicherten Schritte seit
    jeher rechnen.
    """
    return spec.template and spec.name in EXACT_PARTS


def _register_creator(spec: PartSpec, registry: Registry | None) -> None:
    """Legt einen eigenständigen Baustein ohne Träger an — kein künstlicher Körper im Projekt."""
    schema = build_params(spec, standalone=True)
    # exact:1 — eine Vorlage entsteht exakt, wo der Kern da ist (RM-443); ein
    # Ergebnis von davor wäre ein Netz.
    # guards:3 — ohne Träger steht er auf dem Bett, ein Mündungsbaustein kopfüber (RM-562).
    version = f"{_result_version(spec)}:guards:3" + (":exact:1" if _creates_exactly(spec) else "")

    @register_op(
        name=creator_name(spec.name),
        title=spec.title,
        category="parts",
        params=schema,
        consumes=0,
        produces=1,
        touches_features=True,
        doc=spec.doc or spec.title,
        cache_version=version,
        caveat=spec.caveat,
        registry=registry,
    )
    def run(ctx: OpContext) -> OpResult:
        exact = _creates_exactly(spec) and _exact_kernel_here()
        part_params, produced = _built_part(
            spec,
            ctx.params,
            ctx.profile,
            ctx.quality,
            parameters=resolve_parameters(ctx.scene.parameters),
            kernel="brep" if exact else "mesh",
        )
        direction = _free_direction(ctx.params)
        turned, sink = _on_its_own_bed(spec, ctx.params, produced.mesh, direction)
        # Ein Rezept rechnet seinen Ausschnitt mit dem Auswerter und bringt einen
        # exakten Körper mit, wenn sein Stapel exakt rechnet (RM-574); der bleibt
        # exakt. Am Netz gebaut kommt hier nie ein exakter Körper an.
        solid = _solid_of(produced.mesh)
        # **Das Netz rollt hier ohne ``keeps_up``, die Merkmale mit** — so rechnete
        # der Erzeuger schon immer. Der einzige eigenständige Baustein mit
        # ``keeps_up`` ist die Rohrschelle, und sie ist unter der halben Drehung
        # symmetrisch; rollte das Netz mit, tauschten ihre erkannten Flächen in
        # alten Projekten die Kennung, und ein Schritt an ``face_1`` träfe die
        # Gegenseite (Review G1, Entscheidung des Koordinators).
        # ``test_every_creator_keeps_its_old_placement`` hält beides fest.
        placed: Mesh = (
            _place_solid(solid, ctx.params, sink=sink, direction=turned, cancelled=ctx.cancelled)
            if solid is not None
            else _place(as_mesh_data(produced.mesh), ctx.params, sink=sink, direction=turned)
        )
        features = _placed_features(
            produced, spec, ctx.params, (0.0, 0.0, 0.0), sink, turned, spec.keeps_up, False
        )
        from app.i18n import source_text

        findings = list(produced.findings)
        for finding in (
            _lying_flat(spec, ctx.params, direction),
            _standing_on_edge(spec, ctx.params, direction),
            _spring_finding(spec.name, part_params, ctx.profile),
        ):
            if finding is not None:
                findings.append(finding)
        made = SceneObject(
            id="",
            name=source_text(spec.title),
            mesh=placed,
            kind="brep" if solid is not None else "mesh",
            features=features,
        )
        # Am exakten Körper liest niemand sonst die Merkmale nach: die
        # erklärten suchen ihren Partner in der Topologie (:func:`_read_exactly`).
        return _read_exactly(ctx, OpResult(outputs=[made], findings=findings))


#: Bausteine, deren Gewindemerkmal das gebaute Maß und das Nennmaß nennt statt
#: nur das Nennmaß — die Geometrie blieb gleich, ein Ergebnis aus dem Cache
#: trüge aber das alte Merkmal, und die Gewindepassung maß dort 0,00 mm. Seit
#: RM-544 (Stand 3) nennt es dazu Größe, Profil, Drehsinn, Gangzahl und Kegel.
PRINTED_THREADS: Final = frozenset(
    {"printed_thread", "printed_screw", "printed_nut", "threaded_rod"}
)


def _result_version(spec: PartSpec) -> str:
    """Der Bausteinstand einschließlich der materialabhängigen Federprüfung
    und des Gewindemerkmals (:data:`PRINTED_THREADS`)."""
    if spec.name in SPRING_ARMS:
        return f"{spec.version}:spring:2"
    return f"{spec.version}:thread:3" if spec.name in PRINTED_THREADS else spec.version


def _title_for(spec: PartSpec) -> TranslatableText | str:
    return spec.title


def _hanging_loose(before: Mesh, after: Mesh, spec: PartSpec, subtractive: bool) -> Finding | None:
    """Ist etwas neben dem Träger stehengeblieben, statt an ihm zu hängen?

    **Der Fall, den Roberts Würfel gezeigt hat.** Zwei Haken im Vierzigerraster
    stehen ±22,5 mm von der Mitte; auf einem 20 mm breiten Würfel berühren sie
    ihn nicht mehr. Heraus kamen drei lose Stücke, wasserdicht und mit
    plausiblem Volumen — der Prüfbericht führte „3 Teile" als **Angabe**, nicht
    als Befund, und wer nicht weiß, dass dort eine Eins stehen müsste, druckt
    sie.

    Gemessen wird am Ergebnis und nicht an der Breite der Zielfläche. Eine
    Fläche ist schnell nachgerechnet, aber sie trifft nicht jeden Fall: eine
    schmale Fläche auf einem breiten Teil, ein Loch dazwischen, eine Rundung —
    da stimmt die Rechnung und der Körper zerfällt trotzdem. Die Teilezahl
    lügt nicht.

    Nur für **angebaute** Bausteine: Ein abziehender darf teilen, das ist bei
    manchen sein Zweck.
    """
    return fell_apart(
        before,
        after,
        applies=not subtractive or spec.host_add is not None,
        code="parts.hanging_loose",
        message=lambda _loose: _loose_advice(spec),
        values={"part": spec.name},
    )


def _host_split(before: Mesh, host: Mesh, spec: PartSpec, source: SceneObject) -> Finding | None:
    """Ist der **Träger** eines lösbaren Teils zerfallen?

    Eine gedruckte Schraube liegt als eigenes Teil neben ihrem Träger
    (``separate_from_host``), und die Teilezahl des Szenenobjekts steigt
    gewollt; die Auswertung fragt sie deshalb nicht
    (``OperationSpec.leaves_separate_parts``). Was bleibt, ist der Träger:
    Die Senkung einer M5 in einem Streifen, der schmaler ist als ihr Kopf,
    schneidet ihn ganz durch — das ist der Zerfall, den ``feature.body_split``
    meint, und nur hier sind Träger und Schraube noch getrennte Körper.

    Gezählt wie :func:`_hanging_loose`, am exakten Träger die Körper der Form
    (``geom.boolean.pieces``) — keine Vernetzung eines Zwischenstands.
    """
    return body_split(pieces(before), pieces(host), op=op_name(spec.name), object_id=source.id)


#: Die Felder, mit denen sich ein Lochwand-Einhänger einfangen lässt. Wer sie
#: hat, bekommt den Satz dazu; wer nicht, bekommt ihn nicht.
_REACH_FIELDS = ("plate", "steps")


def _loose_advice(spec: PartSpec) -> TranslatableText:
    """Was gegen lose Stücke hilft — und zwar an **diesem** Baustein.

    Der Satz nannte bis zum 26.08.2026 immer die Rückplatte und die
    Rasterschritte. Das sind die Felder des Lochwand-Einhängers, und der Befund
    gilt jedem anbauenden Baustein: Eine Rippe, ein Scharnierauge, ein
    Kabelclip haben beides nicht, und der Kunde suchte zwei Felder, die es in
    seinem Dialog nicht gibt. Ein Vorschlag, der nicht einzulösen ist, ist
    keiner (Regel 17).

    Gefragt wird das Parameterschema und nicht der Name des Bausteins — sonst
    steht hier beim nächsten Einhänger wieder eine Liste, die niemand pflegt.

    **Beide Sätze stehen ganz da.** Aus einer gemeinsamen ersten Hälfte und
    zwei Enden zusammengesetzt wäre einer der beiden Teile ein Satzfragment,
    und ein Katalog übersetzt Fragmente nicht: Was im Deutschen hinten steht,
    steht anderswo vorn.
    """
    names = {entry.name for entry in spec.params.spec()}
    if all(field in names for field in _REACH_FIELDS):
        return _(
            "Ein Teil des Bausteins sitzt neben dem Objekt und hängt in der Luft — "
            "gedruckt würden lose Stücke. Geben Sie eine Rückplatte an, dann "
            "verbindet sie, was danebensteht; oder verringern Sie die "
            "Rasterschritte, damit alles enger zusammenrückt."
        )
    return _(
        "Ein Teil des Bausteins sitzt neben dem Objekt und hängt in der Luft — "
        "gedruckt würden lose Stücke. Setzen Sie den Baustein an ein Merkmal des "
        "Objekts oder rücken Sie seine Position näher heran."
    )


def _cuts_no_layer(
    before: Mesh, after: Mesh, built: Mesh, spec: PartSpec, profile: Profile | None
) -> Finding | None:
    """Schneidet ein abtragender Baustein nicht einmal eine Schicht tief ins Teil?

    **Der Fall, den der Prüfer bohrung gemessen hat** (Durchsicht 0.5.1): eine
    Magnettasche, auf der Unterseite eines Deckels 80 x 60 x 5 eingetippt
    (z = 0), ohne angeklickte Fläche. Ihre Richtung ist dann die Achse Z, die
    Öffnung zeigt nach oben, und die Tasche hing unter dem Deckel in der Luft.
    Abgetragen wurden 0,5 mm³: die Haut von ``BOOLEAN_OVERLAP``, mit der jede
    Öffnung über ihre Fläche reicht. Das ist mehr als ein Stück Extrusionsbahn,
    also schwieg ``boolean.without_effect`` — an beiden Kernen.

    **Gemessen wird die Wirkung, nicht der Treffer** (``operationen.md``): Das
    Abgetragene über den mittleren Querschnitt des Bausteins verteilt — sein
    Volumen durch seine Länge entlang der eigenen Achse — ist eine Tiefe, und
    was unter einer Schichthöhe bleibt, entsteht im Druck nicht (dieselbe
    Grenze wie ``sculpt.no_effect``). Eine Durchgangsbohrung, die länger ist als
    die Platte, schneidet die ganze Plattendicke tief und schweigt; eine Tasche
    an einer Kante, die zur Hälfte hinausragt, auch.

    **Keine geratene Richtung** (Regel 21): Die Fläche unter der eingetippten
    Stelle gäbe hier die richtige, aber schon auf einer Kante sind es zwei, und
    eine Stelle im Material hat keine. Gespeicherte Schritte, die ihre Lage so
    eintragen, rechneten danach still anders. Der Befund sagt, was geschah,
    und nennt beide Wege: die Fläche anklicken oder im Schritt Position und
    Richtung prüfen.

    Ein Baustein, der gar nichts abträgt, bleibt bei ``boolean.without_effect``
    (der Aufrufer fragt diese Funktion nur, wenn jener schweigt). Ohne Profil
    gibt es keine Schichthöhe und keine Aussage.
    """
    if profile is None:
        return None
    tool = as_mesh_data(built)
    length = float(tool.bounds.maximum[2]) - float(tool.bounds.minimum[2])
    if length <= EPS_GEOM:
        return None
    section = abs(float(tool.volume)) / length
    removed = float(as_mesh_data(before).volume) - float(as_mesh_data(after).volume)
    if removed > section * profile.printer.layer_height:
        return None
    return Finding(
        code="parts.cuts_no_layer",
        severity="warning",
        message=_(
            "Dieser Baustein nimmt keine Schicht weg, er liegt außerhalb des Objekts. Eine "
            "angeklickte Fläche gibt ihm Ort und Richtung."
        ),
        values={"part": spec.name, "removed_mm3": round(max(removed, 0.0), 3)},
        # Regel 17: Position und Richtung stehen im Schritt.
        suggestions=(CORRECT_INPUT,),
    )


def _seated_bore(source: SceneObject, spec: PartSpec, mouth: Vec3, outward: Vec3) -> Feature | None:
    """Die Bohrung des Trägers, in der ein Baustein für Bohrungen sitzt — sonst ``None``.

    Sitzen heißt: Ihre Achse läuft durch die Mündung des Bausteins, den Ort
    nach der gespeicherten Platzierung (:func:`_mouth_frame`), nicht den
    Merkmalsanker, der bei freier Lage der Ursprung ist
    (:func:`app.core.scene.placement.bore_through`). Gefragt wird nur bei
    Bausteinen, die in Bohrungen gehören; die übrigen schneiden ihre Öffnung
    selbst. Die Randprüfung lässt die Öffnung dieser Bohrung aus, und
    :func:`_in_a_wider_bore` misst an ihr.
    """
    from app.core.scene.placement import bore_through

    if not spec.at_hole:
        return None
    bore = bore_through(mouth, outward, source.features)
    if bore is None or not isinstance(bore.params.get("diameter"), int | float):
        return None
    return bore


def _inside_the_bore(points: Any, bore: Feature) -> Any:
    """Welche Punkte innerhalb des Radius einer Bohrung um ihre Achse liegen.

    Auf :data:`~app.core.units.MAX_FACET_SAG` großzügig: Die Wand einer
    Netzbohrung ist ein Vieleck, ihr gemessener Durchmesser eingepasst.
    """
    import numpy as np

    axis = np.asarray(bore.params["axis"], dtype=np.float64)
    axis = axis / float(np.sqrt(np.sum(axis * axis)))
    offset = np.asarray(points, dtype=np.float64) - np.asarray(bore.params["centre"])
    along = np.sum(offset * axis, axis=1)
    across = offset - along[:, None] * axis
    radius = float(bore.params["diameter"]) / 2.0 + MAX_FACET_SAG
    return np.sum(across * across, axis=1) <= radius * radius


def _in_a_wider_bore(spec: PartSpec, bore: Feature, built: Mesh) -> Finding | None:
    """Ein Baustein für Bohrungen sitzt in einer, deren Wand er nicht erreicht.

    **Der Fall der Kundenmeldung zu 0.5.2**: *Schraubenloch mit Senkung* M6
    bohrt Ø 6,6, ein *Druckbares Gewinde* M6 darin reicht nur bis Ø 6 plus
    Spiel. Gemessen am exakten Quader 34,13 x 40,74 x 14,15: Das Loch ist ein
    Sackloch von 10 mm, das Gewinde 12 mm lang, und abgetragen wurden 52 mm³
    — die zwei Millimeter unter dem Lochboden, an der Wand nichts. Kein
    Befund kam; in einer durchgehenden Bohrung kam „das Werkzeug liegt neben
    dem Körper“, und auch das stimmte nicht. Gefragt wird deshalb nicht, ob
    etwas abgetragen wurde, sondern ob der Baustein die Wand erreicht: sein
    größter Abstand von der eigenen Achse gegen den Radius der Bohrung, in
    der er sitzt (:func:`_seated_bore`). Ein Baustein entsteht um seine Achse
    Z im Ursprung, also ist das der größte Abstand seiner Ecken von ihr, vor
    dem Setzen gemessen. Der Satz nennt die Bohrung und darunter, was in sie
    passt (``PartSpec.at_hole_advice``, derselbe Satz wie über dem Dialog).
    """
    import numpy as np

    diameter = float(bore.params["diameter"])
    corners = np.asarray(as_mesh_data(built).raw.vertices, dtype=np.float64)
    reach = float(np.max(corners[:, 0] * corners[:, 0] + corners[:, 1] * corners[:, 1]))
    radius = diameter / 2.0
    if reach > radius * radius:
        return None
    advice = spec.at_hole_advice(diameter) if spec.at_hole_advice is not None else None
    wider = _(
        "Die Bohrung ist mit {diameter} weiter als dieser Baustein, an ihrer Wand trägt er "
        "nichts ab.",
        diameter=format_length(diameter),
    )
    return Finding(
        code="parts.bore_too_wide",
        severity="warning",
        message=wider if advice is None else _("{wider} {advice}", wider=wider, advice=advice),
        values={"part": spec.name, "field": "size"},
        suggestions=(CHANGE_SIZE,),
    )


def _bore_check(
    spec: PartSpec,
    params: Any,
    bore: Feature,
    host: Any,
    profile: Profile | None,
    mouth: Vec3,
    outward: Vec3,
) -> list[Finding]:
    """Was der Baustein selbst über die Bohrung sagt, in der er sitzt (``at_hole_check``).

    ``host`` ist der Träger vor dem Schnitt, ``mouth`` die Mündung und
    ``outward`` die Richtung aus ihr heraus (:func:`_mouth_frame`). Alles, was der
    Baustein sagt, kommt in den Bericht — Restwand und Aufbohren können
    zugleich gelten.
    """
    if spec.at_hole_check is None:
        return []
    return list(spec.at_hole_check(params, bore, host, profile, mouth, outward))


#: Ab welchem Anteil der Senkrechten eine Fläche als waagerecht gilt.
#: cos(30°) — darunter laufen genug Schichten längs der Biegung, dass
#: die dünne Stelle eines Filmscharniers reißt.
_FLAT_ENOUGH = 0.866


def _standing_on_edge(spec: PartSpec, params: Any, direction: Vec3 | None) -> Finding | None:
    """Steht ein Baustein hochkant, dessen Festigkeit an der Druckrichtung hängt?

    **Der Fall, den die Klappbox gezeigt hat** (31.08.2026). Sie setzt ihr
    Filmscharnier mit ``axis="x"``, weil das nach der Biegeachse klingt;
    ``axis`` ist aber die Richtung, in die der Baustein *zeigt*. Die Hülle der
    Box sprang damit von 28 mm Höhe auf 90 — das Scharnier stand hochkant, und
    seine Schichten liefen längs der Biegung statt quer. Es bricht beim ersten
    Öffnen, und die Operation lief ohne einen Befund durch.

    Anders als bei :func:`_lying_flat` **hilft hier eine gewählte Fläche nicht
    von selbst**: Sie gibt dem Baustein ihre Normale, und eine senkrechte Wand
    legt ihn genau so hin, wie er nicht darf. Geprüft werden deshalb beide
    Wege — die eingetippte Achse und die Normale der Fläche.

    **Warnung und nicht Fehler**, wie beim Nachbarn: Das Teil entsteht, ist
    wasserdicht und druckt. Es hält nur nicht, und das sieht man ihm nicht an.
    Wer es bewusst hochkant will, darf das — er soll es nur nicht
    versehentlich tun.
    """
    if not spec.lies_flat:
        return None
    if direction is None:
        if str(_placement_value(params, "axis", "z") or "z") == "z":
            return None
    else:
        # Waagerecht heißt: Die Normale zeigt nach oben oder unten. Alles
        # dazwischen legt das Scharnier auf die Kante, und ab etwa dreißig Grad
        # laufen genug Schichten längs, dass die dünne Stelle reißt.
        if abs(float(direction[2])) >= _FLAT_ENOUGH:
            return None
    return Finding(
        code="parts.standing_on_edge",
        severity="warning",
        # Der Vorschlag steht im Satz, wie bei den Nachbarn.
        message=_(
            "Dieser Baustein bricht hochkant gedruckt beim ersten Öffnen. Er gehört auf eine "
            "waagerechte Fläche oder auf die Achse Z."
        ),
        values={"part": spec.name},
        # Regel 17: Die Richtung des Bausteins steht im Schritt.
        suggestions=(CORRECT_INPUT,),
    )


def _lying_flat(spec: PartSpec, params: Any, direction: Vec3 | None) -> Finding | None:
    """Ein Baustein mit einem Oben, dessen Oben nirgendwohin zeigt.

    **Der Fall, den Robert am Bild gesehen hat** (30.08.2026, an den Haken
    eines Lochwandhalters für die Website): „eigentlich sind sie falsch gesetzt
    und man könnte sie so nie einhaken". Gemessen stimmte es — hinter der
    Lochwand standen 0,8 mm Material statt der 3,7 mm, mit denen die Nase
    hinter den Steg greift. Der Zapfen zeigte nach hinten statt nach oben.

    Die Ursache ist eine Vorgabe, die für diese Bausteine nicht passt.
    ``PartSpec.keeps_up`` sagt, dass ein Baustein eine Oberseite hat, und
    :func:`_roll_upright` richtet sie auf — **aber nur entlang einer Richtung**,
    und eine Richtung gibt es nur mit einer gewählten Fläche. Wer die Position
    stattdessen eintippt, behält die Vorgabe *Achse = Z*: Der Baustein liegt
    dann, als säße er auf einem Deckel, und sein eigenes -Y bleibt Welt -Y.

    Das ist nicht zu reparieren, sondern zu sagen. Um Z gedreht kommt ein -Y
    nie nach oben — die Achse liegt in der Ebene, in der es sich bewegt. Wer
    einen Einhänger an eine Wand setzen will, wählt die Wand; sie trägt die
    Richtung, und ``keeps_up`` erledigt den Rest. Regel 21: nie stillschweigend
    raten, und ein Haken, der nichts hält, ist die stillste aller Antworten.

    **Warnung und nicht Fehler**, anders als bei :func:`_hanging_loose`. Dort
    zerfällt das Teil in Stücke, hier steht es da und ist druckbar; es hält nur
    nicht. Und flach liegend ist es nicht unmöglich, nur beinahe immer
    unbeabsichtigt — dieselbe Einschätzung, die :func:`_roll_upright` für den
    Deckel trifft.
    """
    if not spec.keeps_up or direction is not None:
        return None
    if str(_placement_value(params, "axis", "z") or "z") != "z":
        return None
    return Finding(
        code="parts.up_points_nowhere",
        severity="warning",
        # Der Vorschlag steht im Satz, wie nebenan: erst was ist, dann was hilft.
        message=_(
            "Dieser Baustein trägt nur mit dem Zapfen nach oben. Eine angeklickte Fläche oder "
            "die Achse Y richtet ihn auf."
        ),
        values={"part": spec.name},
        # Regel 17: Die Richtung des Bausteins steht im Schritt.
        suggestions=(CORRECT_INPUT,),
    )


def insert(ctx: OpContext, spec: PartSpec) -> OpResult:
    """Setzt den Baustein an sein Ziel — oder an jedes von mehreren (§24.3).

    **Ein Schritt, ein Undo, gleich wie viele Merkmale gewählt sind.** Wer vier
    Bohrungen markiert und eine Einpressbuchse setzt, meint eine Handlung; vier
    Zeilen im Verlauf wären vier Rücknahmen für etwas, das zusammen gedacht war
    (Regel 16 in ihrer Haltung, auch wenn sie dem Agenten gilt).

    Gerechnet wird der Reihe nach, und das Ergebnis jedes Durchgangs ist der
    Eingang des nächsten: Der zweite Baustein sitzt auf dem Körper, der den
    ersten schon trägt. Anders wäre es nicht dasselbe Teil — zwei Bausteine,
    die sich überschneiden, müssen einander sehen.

    Ohne ``at_features`` bleibt alles, wie es war: :func:`_insert_at` ist der
    Weg, den es seit je gibt, und die Schleife darüber ist bei einem Ziel eine
    Wiederholung mit einem Durchgang.

    Ein exaktes Ergebnis liest seine Merkmale danach **einmal** aus der
    Topologie (:func:`_read_exactly`) — nach dem letzten Ziel und nicht je
    Durchgang, denn jedes Ziel wird am Merkmal des Eingangs aufgelöst.
    """
    targets = _chosen_features(ctx.params)
    if not targets:
        return _read_exactly(ctx, _insert_at(ctx, spec))
    if len(targets) == 1:
        return _read_exactly(
            ctx,
            _insert_at(dataclasses.replace(ctx, params=_aimed_at(ctx.params, targets[0])), spec),
        )

    source = ctx.inputs[0]
    findings: list[Finding] = []
    solver = None
    for target in targets:
        step = dataclasses.replace(
            ctx,
            inputs=[source],
            params=_aimed_at(ctx.params, target),
        )
        outcome = _insert_at(step, spec)
        if not outcome.outputs:
            # Ein Durchgang ohne Ausgabe gibt es am Bausteinweg nicht; käme er,
            # wäre der Körper der letzte gültige und nicht None.
            return outcome
        source = outcome.outputs[0]
        for finding in outcome.findings:
            if finding not in findings:
                findings.append(finding)
        solver = deepest((solver, outcome.solver))
    return _read_exactly(ctx, OpResult(outputs=[source], solver=solver, findings=findings))


def _read_exactly(ctx: OpContext, outcome: OpResult) -> OpResult:
    """Die Merkmale eines exakten Ergebnisses, aus seiner Topologie gelesen.

    **Am Netz liest die Auswertung neu, am exakten Körper niemand sonst.** Ein
    Solid hat keine Dreiecke, an denen die Erkennung messen könnte; seine
    Merkmale liest ``brep.features.features_of`` in der Operation, die ihn
    baut (``scene.evaluate._with_features``). Der Baustein gab stattdessen die
    Merkmale seines Trägers durch — ohne Dreiecke, denn deren Nummern gehören
    dem Netz vor dem Schnitt (:func:`_merged_features`), und mit ihren alten
    Maßen. Nach einer Magnettasche im Quader des Kundenwegs stand die
    Oberseite mit 1 179 statt 1 129 mm² „aus der Konstruktion“ da, kein
    Merkmal des Körpers ließ sich im Bild treffen, und Boden und Haltelippe
    der Tasche fehlten (Durchsicht 0.5.1, ERKENNUNG-10). Der Nachweis zu P2.7
    hatte das Lesen einmal verworfen, weil es die Namen neu vergab und das
    zweite Ziel einer Mehrfachwahl dann die erste Bohrung traf (B3); gelesen
    wird deshalb erst nach dem letzten Ziel.

    Wie in jeder exakten Merkmalshandlung (``geom.prepare_ops._exact_features_after``)
    geht der Name über die eindeutige Zuordnung weiter: Die erklärten Merkmale
    — die des Bausteins und die früher eingesetzter — suchen ihren Partner an
    ihrer Stelle und nehmen dessen Oberfläche auf
    (``matching.declared_partners``, ``on_their_partners``, derselbe Weg wie
    am Netz), die übrigen Merkmale des Trägers bekommen ihre Nachfolger über
    ``match`` und ``apply_mapping``. Was neu dazukommt — der Boden einer
    Tasche —, bekommt einen freien Namen und in der Auswertung den Schritt als
    Erzeuger.
    """
    if not outcome.outputs or outcome.outputs[0].kind != "brep":
        return outcome
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid
    from app.core.perceive.matching import (
        apply_mapping,
        declared_partners,
        match,
        on_their_partners,
        settled_twins,
    )

    body = outcome.outputs[0]
    solid = body.mesh
    if not isinstance(solid, Solid):
        return outcome
    watch = ctx.cancelled.raise_if_cancelled
    detected = features_of(solid, cancelled=ctx.cancelled)
    bounds = solid.bounds
    declared = {
        name: entry for name, entry in body.features.items() if entry.provenance == "generated"
    }
    carried = {name: entry for name, entry in body.features.items() if name not in declared}
    seen = declared_partners(
        declared, detected, bounds.centre, bounds.diagonal, check_cancelled=watch
    )
    partners = set(seen.mapping.values())
    remaining = {name: entry for name, entry in detected.items() if name not in partners}
    matched = match(carried, remaining, bounds.centre, bounds.diagonal, check_cancelled=watch)
    if matched.ambiguous and ctx.inputs and ctx.inputs[0].kind == "brep":
        # Zwillinge nach der Lage ihrer Oberfläche wie in jedem zuordnenden Weg
        # (``kern.md``). Die durchgereichten Merkmale tragen keine Dreiecke
        # mehr; ihre Orte stehen am Träger vor dem ersten Ziel.
        host = ctx.inputs[0]
        matched = settled_twins(
            matched,
            {name: entry for name, entry in host.features.items() if name in carried},
            as_mesh_data(host.mesh),
            remaining,
            as_mesh_data(solid),
            bounds.diagonal,
        )
    features = {
        **apply_mapping(remaining, matched, previous=carried, reserved=set(declared)),
        **on_their_partners(declared, detected, seen),
    }
    return dataclasses.replace(outcome, outputs=[dataclasses.replace(body, features=features)])


def _chosen_features(params: Any) -> tuple[str, ...]:
    """Die gewählten Zielmerkmale — die Liste, sonst das einzelne Feld.

    **Die Liste hat Vorrang, und das einzelne Feld bleibt lesbar.** Dieselbe
    Regel wie bei ``clear_filament``: Ein Projekt, das vor dieser Erweiterung
    gespeichert wurde, trägt nur ``at_feature``, und es soll weiter rechnen.
    """
    many = _placement_value(params, "at_features", ()) or ()
    if many:
        return tuple(str(entry) for entry in many if str(entry))
    single = str(_placement_value(params, "at_feature", "") or "")
    return (single,) if single else ()


def _aimed_at(params: Any, target: str) -> Any:
    """Denselben Parametersatz, auf genau ein Merkmal gerichtet.

    Die Liste wird dabei geleert, sonst liefe der Durchgang wieder in die
    Schleife. Geschrieben wird über die **Feldnamen dieses Schemas**
    (:func:`placement_fields`) — ein Rezeptmaß darf „at_feature" heißen, und
    dann steht der Ort woanders.
    """
    fields = placement_fields(type(params))
    return dataclasses.replace(params, **{fields["at_feature"]: target, fields["at_features"]: ()})


def _insert_at(ctx: OpContext, spec: PartSpec) -> OpResult:
    """Baut den Baustein, setzt ihn an seinen Platz und verbindet oder schneidet."""
    source = ctx.inputs[0]
    profile = for_object(ctx.profile, source) if ctx.profile is not None else None
    parameters = resolve_parameters(ctx.scene.parameters)
    if _builds_exactly(spec, source):
        # Ein exakter Träger bekommt einen exakten Baustein (P2.7): dieselbe
        # Formbeschreibung, im anderen Kern gerechnet — der Träger bleibt, was
        # er ist, statt für den Baustein zum Netz zu werden.
        part_params, produced = _built_part(
            spec, ctx.params, profile, ctx.quality, parameters=parameters, kernel="brep"
        )
        return _insert_at_exact(ctx, spec, source, profile, part_params, produced)
    part_params, produced = _built_part(
        spec, ctx.params, profile, ctx.quality, parameters=parameters
    )
    built = as_mesh_data(produced.mesh)
    anchor, direction = _anchor(source, ctx.params, spec, built)
    flat = _lying_flat(spec, ctx.params, direction)
    on_edge = _standing_on_edge(spec, ctx.params, direction)
    # Ein aufgesetzter Baustein sinkt ein Hundertstel ein. Zwei Volumen, die
    # sich nur in einer Fläche berühren, sind das eine, woran eine boolesche
    # Operation zuverlässig scheitert (§39) — die Rastnase steht mit 6 mal 1 mm
    # auf, und heraus kam ein wasserdichtes Netz aus zwei Komponenten, beim
    # nächsten Bohren drei. Die breiteren Bausteine fielen nie auf, weil
    # manifold sie verschmolz; die Frage ist für alle dieselbe und steht darum
    # hier und nicht in jedem einzelnen. Ein subtraktiver braucht es nicht: sein
    # Werkzeug reicht ohnehin über die Fläche hinaus. Ein lösbares Teil darf es
    # nicht: Das Hundertstel würde Schraube oder Mutter gerade in das Werkstück
    # drücken, von dem sie getrennt bleiben sollen.
    subtractive = cuts(spec, ctx.params)
    sink = 0.0 if subtractive or spec.separate_from_host else BOOLEAN_OVERLAP
    flip = subtractive and _builds_upward_on_a_face(source, ctx.params, built)
    placed = _place(built, ctx.params, anchor, sink, direction, spec.keeps_up, flip)
    body = as_mesh_data(source.mesh)
    original_body = body
    lip = None
    rim = None
    bore: Feature | None = None
    if subtractive:
        mouth, outward = _mouth_frame(ctx.params, anchor, direction, spec.keeps_up)
        bore = _seated_bore(source, spec, mouth, outward)
        rim = _over_the_rim(
            body,
            placed,
            mouth,
            outward,
            surface=_surface_at_anchor(source, mouth),
            bore=bore,
            cancelled=ctx.cancelled,
        )
        placed = _opened_to_the_face(placed, body, ctx.params, anchor, direction, spec.keeps_up)
        lip = _lip_on_a_slant(spec, part_params, body, ctx.params, anchor, direction, spec.keeps_up)
    addition = spec.host_add(part_params) if spec.host_add is not None else None
    added_features: dict[str, Feature] = {}
    added_findings: list[Finding] = []
    addition_solver = None
    if addition is not None:
        placed_addition = _place(
            as_mesh_data(addition.mesh), ctx.params, anchor, 0.0, direction, spec.keeps_up, False
        )
        joined = boolean("union", [body, placed_addition], quality=ctx.quality)
        addition_solver = joined.solver
        body = as_mesh_data(joined.mesh)
        added_findings = [*addition.findings, *joined.findings]
        added_features = _placed_features(
            addition, spec, ctx.params, anchor, 0.0, direction, spec.keeps_up, False
        )
    if spec.separate_from_host:
        prepared = body
        host_features: dict[str, Feature] = {}
        findings: list[Finding] = []
        solver = None
        nothing = None
        host_cut = spec.host_cut(part_params) if spec.host_cut is not None else None
        if host_cut is not None:
            # Ein lösbares Teil darf nicht mit dem Träger vereinigt werden;
            # seine Sitzfläche darf den Träger aber sehr wohl vorbereiten.
            # Beides wird hier innerhalb **derselben Operation** gerechnet:
            # ein Undo nimmt Schraube und Senkung gemeinsam zurück, und Agent,
            # Menü sowie Kommandozeile benutzen denselben Vertrag.
            cutter = as_mesh_data(host_cut.mesh)
            placed_cutter = _place(
                cutter,
                ctx.params,
                anchor,
                0.0,
                direction,
                spec.keeps_up,
                False,
            )
            cut = boolean("difference", [body, placed_cutter], quality=ctx.quality)
            prepared = as_mesh_data(cut.mesh)
            solver = cut.solver
            findings.extend(cut.findings)
            findings.extend(host_cut.findings)
            nothing = without_effect(body, prepared, "difference", ctx.profile) or _cuts_no_layer(
                body, prepared, cutter, spec, ctx.profile
            )
            host_features = _placed_features(
                host_cut,
                spec,
                ctx.params,
                anchor,
                0.0,
                direction,
                spec.keeps_up,
                False,
            )
        # Schraube und Mutter liegen im selben Projekt, dürfen aber nicht zu
        # einem unlösbaren Körper verschweißen. Eine Zusammenfügung hält beide
        # geschlossenen Netze in einem Szenenobjekt, ohne ihre Berührung als
        # Boolesche Verbindung zu deuten.
        mesh = _concatenated_with_slots(prepared, placed)
    else:
        host_features = {}
        kind: BooleanKind = "difference" if subtractive else "union"
        outcome = boolean(kind, [body, placed], quality=ctx.quality)
        mesh = as_mesh_data(outcome.mesh)
        solver = outcome.solver
        findings = outcome.findings
        # Ein Baustein, der den Körper nicht getroffen hat, sagt das. Hier und
        # nicht in jedem einzelnen: die Frage ist für alle dieselbe, und die
        # Antwort steht im Volumen (§2.7). Ein abtragender, der ihn nur mit der
        # Haut über seiner Öffnung streift, auch (:func:`_cuts_no_layer`).
        nothing = without_effect(body, mesh, kind, ctx.profile)
        if nothing is None and subtractive:
            nothing = _cuts_no_layer(body, mesh, built, spec, ctx.profile)
        if bore is not None:
            wider = _in_a_wider_bore(spec, bore, built)
            said = (
                []
                if wider is not None
                else _bore_check(spec, part_params, bore, body, ctx.profile, mouth, outward)
            )
            nothing = wider or (None if said else nothing)
            findings = [*findings, *said]

    features = _merged_features(
        source,
        produced,
        spec,
        ctx.params,
        anchor,
        sink,
        direction,
        flip,
        host_features,
        added_features,
    )

    # Und die Gegenprobe zu „hat nichts bewirkt": Er hat etwas hinzugefügt, nur
    # nicht **am** Teil. Ein lösbares Teil fragt stattdessen, ob sein Träger
    # zerfallen ist (:func:`_host_split`).
    loose = (
        _host_split(original_body, prepared, spec, source)
        if spec.separate_from_host
        else _hanging_loose(original_body, mesh, spec, subtractive)
    )

    spring = _spring_finding(spec.name, part_params, profile)

    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh, features=features)],
        solver=deepest((addition_solver, solver)),
        findings=[
            *findings,
            *added_findings,
            *produced.findings,
            *([nothing] if nothing else []),
            *([lip] if lip else []),
            *([rim] if rim else []),
            *([loose] if loose else []),
            *([flat] if flat else []),
            *([on_edge] if on_edge else []),
            *([spring] if spring else []),
        ],
    )


#: Welcher Parameter eines Bausteins die Armlänge, die Dicke und den Federweg
#: nennt — je Baustein, weil nur er weiß, was seine Maße bedeuten.
#:
#: Eine Tabelle und keine Angabe am Registereintrag, und das ist eine
#: Abwägung: Am Eintrag stünde sie näher bei der Sache, kostete aber ein
#: weiteres Feld an ``register_part``, das siebenundzwanzig Bausteine tragen
#: und fünfundzwanzig leer lassen. Wer einen federnden Baustein hinzufügt,
#: trägt ihn hier ein; ``test_parts.py`` prüft, dass jeder Name existiert und
#: seine drei Parameter auch.
#:
#: **``snap_connector`` steht bewusst nicht dabei**, obwohl er der zweite
#: Federbaustein ist. Seine Armdicke ist kein Parameter, sondern abgeleitet:
#: ``min(length / SNAP_RATIO, (room - play) / 3)``, und ``room`` kommt aus
#: Durchmesser und Spiel. Diese Kette hier nachzubauen hieße, dieselbe Regel
#: an zwei Stellen zu pflegen — sie liefe beim ersten Maßwechsel auseinander,
#: und dann prüfte die Warnung einen Arm, den es nicht gibt.
#:
#: Der Weg dorthin ist ein anderer und größer als diese Tabelle: Ein Baustein
#: müsste den Befund selbst zurückgeben können — ``PartResult.findings`` gibt
#: es dafür bereits —, und dazu bräuchte ``PartFn`` das Materialprofil, das
#: es heute nicht bekommt. Bis dahin ist ein geprüfter Baustein besser als
#: zwei halb geprüfte.
SPRING_ARMS: Final[dict[str, tuple[str, str, str]]] = {
    # Baustein: (Armlänge, Armdicke, Federweg beim Einrasten)
    "snap_fit": ("length", "thickness", "hook"),
}


def _mouth_frame(
    params: Any, anchor: Vec3, direction: Vec3 | None, keeps_up: bool
) -> tuple[Vec3, Vec3]:
    """Tatsächlicher Mündungsort und Außenrichtung nach der gespeicherten Platzierung."""
    frame = _matrix(params, anchor, direction=direction, keeps_up=keeps_up)
    point = (float(frame[0][3]), float(frame[1][3]), float(frame[2][3]))
    outward = (float(frame[0][2]), float(frame[1][2]), float(frame[2][2]))
    length = math.hypot(*outward)
    return point, (outward[0] / length, outward[1] / length, outward[2] / length)


def _surface_at_anchor(source: SceneObject, anchor: Vec3) -> Feature | None:
    """Die belegte Fläche am Ansatzpunkt, auch bei einer freien Platzierung."""
    import numpy as np

    from app.core.geom.mesh import on_surface

    body = as_mesh_data(source.mesh)
    _points, distances, triangles = on_surface(body.raw, np.asarray([anchor], dtype=np.float64))
    if float(distances[0]) > MAX_FACET_SAG:
        return None
    triangle = int(triangles[0])
    return next(
        (
            feature
            for feature in source.features.values()
            if feature.kind == "face" and triangle in feature.face_indices
        ),
        None,
    )


def _over_the_rim(
    body: Mesh,
    tool: Mesh,
    anchor: Vec3,
    direction: Vec3 | None,
    *,
    surface: Feature | None = None,
    bore: Feature | None = None,
    cancelled: CancelToken,
) -> Finding | None:
    """Reicht ein abtragender Baustein seitlich über den Rand seiner Fläche?

    Gefunden im Nachbau-Test (RM-392): Ein Schlüsselloch an der Vorderseite
    eines 10 mm hohen Quaders setzte den Kopf in die Flächenmitte, und der
    Einhängeweg endete 3 mm über der Oberkante — die Oberseite verlor 26 mm²,
    die Schraube rutscht oben heraus, und der Prüfbericht war leer. Für
    Bohrungen sagt das ``bore.over_the_edge``; hier fragt dieselbe Stelle für
    jeden abtragenden Baustein.

    **Gefragt wird am Umriss, nicht am Hüllquader.** Jeder Punkt des
    Werkzeugs bis einschließlich der Mündung wird auf die Mündungsebene gelegt und von
    außen entlang der Flächennormalen beschossen: Trifft der Strahl den Körper
    nicht, liegt unter diesem Teil des Umrisses keine Fläche — er reicht über
    den Rand. Eine gewölbte Fläche, etwa eine Zylinderwand, trifft der Strahl
    weiter, solange der Umriss über ihr liegt; ein Durchgangsloch tritt nach
    hinten aus und nicht seitlich, sein Umriss liegt ganz über der Fläche.
    Bei einer gewählten ebenen Fläche zählt nur ihr eigener Umriss: Eine
    Seitenwand hinter ihrem Rand ist keine Fortsetzung des Rinnenbodens.

    **Die Öffnung der Bohrung, in der er sitzt, ist kein Rand** (``bore``,
    :func:`_seated_bore`). Ein Gewinde oder eine Einpressbuchse in einer
    Durchgangsbohrung liegt mit dem halben Umriss über der Luft der Bohrung;
    der Strahl dort trifft nichts, und an der Lochplatte aus dem Korpus kam
    „schneidet die Nachbarfläche an“ für jeden Baustein in jeder Bohrung, fünf
    Millimeter vom Plattenrand. Was innerhalb ihres Radius liegt, zählt nicht —
    wie beim Setzen, wo ``placement.seat_of`` dieselbe Öffnung füllt.
    """
    if direction is None:
        return None
    import numpy as np

    from app.core.geom.mesh import ray_hits_batch

    normal = np.asarray(direction, dtype=float)
    length = float(np.sqrt(np.sum(normal * normal)))
    if length <= EPS_GEOM:
        return None
    normal = normal / length
    origin = np.asarray(anchor, dtype=float)
    points = np.asarray(as_mesh_data(tool).raw.vertices, dtype=float)
    depth = np.sum((points - origin) * normal, axis=1)
    below = depth <= EPS_GEOM
    if not below.any():
        return None
    footprint = points[below] - depth[below][:, None] * normal
    # Ein Werkzeug kann über die Mündung hinausreichen. Seine Kanten tragen
    # dann den Umriss an der Ebene, auch ohne einen Eckpunkt genau bei null.
    edges = np.asarray(as_mesh_data(tool).raw.edges_unique)
    edge_depth = depth[edges]
    crossing = (edge_depth[:, 0] < 0.0) & (edge_depth[:, 1] > 0.0)
    crossing |= (edge_depth[:, 1] < 0.0) & (edge_depth[:, 0] > 0.0)
    if crossing.any():
        cuts = edges[crossing]
        fractions = depth[cuts[:, 0]] / (depth[cuts[:, 0]] - depth[cuts[:, 1]])
        mouth = points[cuts[:, 0]] + fractions[:, None] * (points[cuts[:, 1]] - points[cuts[:, 0]])
        footprint = np.concatenate((footprint, mouth))
    if bore is not None:
        footprint = footprint[~_inside_the_bore(footprint, bore)]
        if not len(footprint):
            return None
    host = as_mesh_data(body)
    low, high = host.bounds.minimum, host.bounds.maximum
    reach = float(np.sqrt(np.sum((np.asarray(high) - np.asarray(low)) ** 2))) + float(
        np.max(-depth[below])
    )
    starts = footprint + reach * normal
    triangles = np.asarray(host.raw.triangles, dtype=float)
    if surface is not None and surface.kind == "face" and surface.face_indices:
        triangles = triangles[list(surface.face_indices)]
    distances, _hit = ray_hits_batch(
        triangles,
        starts,
        np.broadcast_to(-normal, starts.shape).copy(),
        cancelled=cancelled,
    )
    cancelled.raise_if_cancelled()
    missed = ~np.isfinite(distances)
    if not missed.any():
        return None
    if missed.all():
        # Liegt der ganze Umriss neben dem Körper, ragt nichts über einen Rand:
        # Der Baustein verfehlt seinen Träger, und das sagen schon
        # ``boolean.without_effect`` und ``parts.hanging_loose``. Bei einer
        # gewählten Fläche entscheidet der ganze Körper, nicht nur ihr Umriss.
        if surface is None or not (surface.kind == "face" and surface.face_indices):
            return None
        whole, _hit = ray_hits_batch(
            np.asarray(host.raw.triangles, dtype=float),
            starts,
            np.broadcast_to(-normal, starts.shape).copy(),
            cancelled=cancelled,
        )
        if not np.isfinite(whole).any():
            return None
    outside = footprint[missed]
    farthest = outside[int(np.argmax(np.sum((outside - origin) ** 2, axis=1)))]
    suggestion = (
        _rim_placement_suggestion(triangles, footprint, anchor, direction, cancelled)
        if surface is not None and surface.kind == "face"
        else None
    )
    return Finding(
        code="part.over_the_edge",
        severity="warning",
        message=_(
            "Der Baustein reicht über den Rand der Fläche hinaus und schneidet die Nachbarfläche "
            "an."
        ),
        location=(float(farthest[0]), float(farthest[1]), float(farthest[2])),
        values={"suggestion": suggestion} if suggestion is not None else {},
        # Regel 17: Die Lage steht im Schritt; die Stelle zeigt, wo er hinausragt.
        suggestions=(CORRECT_INPUT, SHOW_LOCATION),
    )


def _rim_placement_suggestion(
    triangles: Any, footprint: Any, origin: Vec3, normal: Vec3, cancelled: CancelToken
) -> TranslatableText | None:
    """Eine mittige Lage nur vorschlagen, wenn der ganze Umriss auf die Fläche passt."""
    import numpy as np
    from shapely import union_all
    from shapely.affinity import translate
    from shapely.geometry import MultiPoint, Polygon

    from app.core.sketch.planes import frame_of
    from app.core.units import format_length

    frame = frame_of(normal, origin)
    # Elementweise statt ``@ basis``: Das ginge durch BLAS (RM-187).
    face_offsets = np.asarray(triangles, dtype=np.float64) - np.asarray(origin)
    tool_offsets = np.asarray(footprint, dtype=np.float64) - np.asarray(origin)
    face_points = np.stack(
        (lying_along(face_offsets, frame.x_axis), lying_along(face_offsets, frame.y_axis)), axis=-1
    )
    tool_points = np.stack(
        (lying_along(tool_offsets, frame.x_axis), lying_along(tool_offsets, frame.y_axis)), axis=-1
    )
    cancelled.raise_if_cancelled()
    area = union_all([Polygon(points) for points in face_points])
    outline = MultiPoint(tool_points).convex_hull
    cancelled.raise_if_cancelled()
    if area.is_empty or outline.is_empty:
        return None
    low_u, low_v, high_u, high_v = area.bounds
    tool_low_u, tool_low_v, tool_high_u, tool_high_v = outline.bounds
    du = (low_u + high_u - tool_low_u - tool_high_u) / 2.0
    dv = (low_v + high_v - tool_low_v - tool_high_v) / 2.0
    moved = translate(outline, xoff=du, yoff=dv)
    # Auch innere Ausschnitte gehören zum Flächenrand. Ein Hüllquader allein
    # wäre hier wieder derselbe falsche Beleg wie bei der ursprünglichen Warnung.
    if not area.buffer(EPS_GEOM).covers(moved):
        return None
    shift = (
        np.asarray(frame.x_axis, dtype=np.float64) * du
        + np.asarray(frame.y_axis, dtype=np.float64) * dv
    )
    return _(
        "Zusätzlicher Versatz in die Fläche: X {x}, Y {y}, Z {z}.",
        x=format_length(float(shift[0])),
        y=format_length(float(shift[1])),
        z=format_length(float(shift[2])),
    )


def _spring_finding(name: str, params: BaseParams, profile: Profile | None) -> Finding | None:
    """Trägt der Federarm, den dieser Baustein gerade gebaut hat?

    Die Bausteine halten die Verhältnisregel ein — Armstärke ein Zehntel der
    Länge —, und die ist gut, solange der Federweg im üblichen Rahmen bleibt.
    Sie kennt aber weder den Weg noch das Material: Derselbe Arm aus TPU ist
    etwas anderes als aus PETG-CF, und einer, der sich um zwei Millimeter
    aufbiegen muss, etwas anderes als einer mit zwei Zehnteln.

    **Gemeldet wird nur, was nicht trägt.** Ein Arm mit Reserve bekommt keinen
    Befund: Ein Bericht, der jeden gelungenen Fall bestätigt, ist einer, den
    man zu überblättern lernt.

    Ohne Materialprofil oder ohne mechanische Kennwerte darin bleibt die
    Prüfung stumm, statt mit einem geratenen E-Modul zu rechnen (Regel 21).
    Die endgültige Druckausrichtung ist hier nicht festgelegt. Deshalb gilt
    ausdrücklich der vorsichtige Fall quer zu den Druckschichten.
    """
    fields = SPRING_ARMS.get(name)
    if fields is None or profile is None:
        return None
    arm_length, arm_thickness, travel = (getattr(params, field, None) for field in fields)
    if not all(isinstance(value, int | float) for value in (arm_length, arm_thickness, travel)):
        return None

    if name == "snap_fit":
        from app.core.knowledge.parts.mechanics import SnapFitParams, snap_arm_length

        arm_length = snap_arm_length(cast(SnapFitParams, params))
    load = spring_load(
        profile.material,
        length=float(cast(float, arm_length)),
        thickness=float(cast(float, arm_thickness)),
        deflection=float(cast(float, travel)),
        across_layers=True,
    )
    if load is None or load.holds:
        return None
    return Finding(
        code="part.spring_overloaded",
        severity="warning",
        message=_(
            "Der Federarm hat bei Belastung quer zu den Druckschichten zu wenig Reserve. Ein "
            "längerer Arm oder weniger Federweg hilft."
        ),
        values={
            "stress": round(load.stress, 1),
            "limit": round(load.limit, 1),
            "safety": round(load.safety, 2),
            "material": profile.material.title,
        },
        # Regel 17: Armlänge und Last, die der Satz nennt, stehen im Schritt.
        suggestions=(CORRECT_INPUT,),
    )


def _merged_features(
    source: SceneObject,
    produced: PartResult,
    spec: PartSpec,
    params: Any,
    anchor: Vec3,
    sink: float,
    direction: Vec3 | None,
    flip: bool,
    host_features: Mapping[str, Feature],
    added_features: Mapping[str, Feature],
) -> dict[str, Feature]:
    """Die Merkmale des Trägers, dazu die des Bausteins — unter freien Namen.

    **Was der Körper schon trägt, wird nicht überschrieben.** ``update``
    stand hier zweimal, und der zweite Baustein derselben Sorte nahm dem
    ersten den Namen weg — siehe :func:`_free_name`. Beide Kerne fragen
    dasselbe: Die Merkmale eines Bausteins sind Provenienz, gerechnet aus
    seinen Parametern und mit derselben Matrix bewegt wie seine Form.

    **Und die Dreiecke des Wirts reisen nicht mit.** Seine Merkmale zeigen
    auf das Netz **vor** dem Baustein; die Boolesche Operation nummeriert
    neu, und im Ergebnis bezeichneten die alten Nummern fremde Dreiecke — bis
    über die letzte hinaus (Dose mit Deckel: Merkmale bis Index 40 284 an
    40 254 Dreiecken, und der Plattencache verwarf den Eintrag bei jedem
    Öffnen, gemessen am 21.09.2026). Eine Operation gibt nur Merkmale ihres
    Ausgangsnetzes zurück: Ort und Maß bleiben, die Oberfläche gibt ihnen
    die Auswertung an der neuen Erkennung zurück (``evaluate._with_features``,
    „Der Name bleibt, die aktuelle Oberfläche geht mit").
    """
    features = {
        name: dataclasses.replace(feature, face_indices=(), surface_patches=())
        if feature.face_indices or feature.surface_patches
        else feature
        for name, feature in source.features.items()
    }
    for extra in (
        _placed_features(
            produced,
            spec,
            params,
            anchor,
            sink,
            direction,
            spec.keeps_up,
            flip,
            taken=features,
        ),
        host_features,
        added_features,
    ):
        for name, feature in extra.items():
            public = _free_name(name, features)
            features[public] = (
                feature if public == name else dataclasses.replace(feature, id=public)
            )
    return features


#: Die Bausteine, die an einem exakten Träger im exakten Kern bauen (P2.7).
#: Die Menge wächst gruppenweise: Ein Baustein steht hier, sobald seine ganze
#: Beschreibung ohne ``shapes.mesh_only`` auskommt und die Paritätstabelle
#: (``tests/test_exact_body_parity.py``) ihn als ``KEEP`` führt. Was nicht hier
#: steht, nimmt den Netzweg samt Konvertierungsmeldung, wie bisher.
EXACT_PARTS: Final = frozenset(
    {
        # Verbindungen
        "screw_hole",
        "heatset_m4",
        "nut_trap",
        "printed_thread",
        "printed_screw",
        "printed_nut",
        "threaded_rod",
        # Mechanik
        "barrel_hinge",
        "bayonet",
        "bearing_seat",
        "detent_disc",
        "dowel",
        "hinge_eye",
        "latch",
        "living_hinge",
        "snap_connector",
        "snap_fit",
        # Befestigung
        "foot",
        "keyhole",
        "lug",
        "magnet_pocket",
        "pegboard_hook",
        "pipe_clamp",
        "wall_mount",
        "profile_clamp_liner",
        "profile_clamp_shell",
        # Halter
        "holder_u",
        "holder_ring",
        "holder_fork",
        "holder_shelf",
        # Struktur und Kabel
        "rib",
        "gusset",
        "profile_tongue",
        "cable_gland",
        "cable_clip",
        "hose_barb",
        "channel_joint",
        # Stangen und Raumplatten
        "rod_connector",
        "room_floor",
        "room_wall",
        "room_pane",
        # Organizer
        "organizer_tray",
        "organizer_divider",
        "organizer_rim",
        "organizer_foot",
        # Dichtungen
        "seal_groove",
        "seal_gasket",
        # Kalibrierung
        "fit_ladder",
        "wall_ladder",
        "overhang_fan",
    }
)


def _builds_exactly(spec: PartSpec, source: SceneObject) -> bool:
    """Ob dieser Baustein an diesem Träger im exakten Kern gebaut wird."""
    return spec.name in EXACT_PARTS and _solid_of(source.mesh) is not None


def _solid_of(mesh: Mesh) -> Solid | None:
    """Der exakte Körper hinter dem Vertrag — oder ``None`` an einem Netz.

    Gefragt wird die Sorte über ``types.BRepBody`` (eine Regel, ein Ort), nicht
    über einen Import des optionalen Kerns.
    """
    return cast("Solid", mesh) if isinstance(mesh, BRepBody) else None


def _place_solid(
    solid: Solid,
    params: Any,
    anchor: Vec3 = (0.0, 0.0, 0.0),
    sink: float = 0.0,
    direction: Vec3 | None = None,
    keeps_up: bool = False,
    flip: bool = False,
    *,
    cancelled: CancelToken | None = None,
) -> Solid:
    """Der exakte Baustein an seinem Platz — dieselbe Matrix wie :func:`_place`."""
    from app.core.brep import edit
    from app.core.geom.ops import as_transform

    matrix = as_transform(_matrix(params, anchor, sink, direction, keeps_up, flip))
    return edit.transformed(solid, matrix, cancelled=cancelled)


def _insert_at_exact(
    ctx: OpContext,
    spec: PartSpec,
    source: SceneObject,
    profile: Profile | None,
    part_params: BaseParams,
    produced: PartResult,
) -> OpResult:
    """Der Baustein am exakten Träger: dieselbe Lage, dieselben Befunde, kein Netz.

    Zeile für Zeile der Netzweg aus :func:`_insert_at`, mit dem exakten Kern
    an den drei Stellen, an denen dort Dreiecke gerechnet werden: Platzieren
    (``edit.transformed`` mit derselben Matrix), Vereinigen und Schneiden
    (``edit.boolean``) und das Anhängen eines lösbaren Teils (ein Verbund
    statt einer Verkettung, Befund B9 des Berichts). Das Einsenken um
    ``BOOLEAN_OVERLAP`` bleibt: Es schadet exakt nicht und hält beide Wege
    auf demselben Maß (B4). Die Merkmale sind Provenienz und reisen wie am
    Netz mit der Matrix; die Merkmale des Trägers liest :func:`insert` nach
    dem letzten Ziel aus der Topologie des Ergebnisses (:func:`_read_exactly`,
    B3). Trägeraufbau und Sitzvorbereitung
    entstehen im selben Kern; was ihre Formen melden, wird Befund.
    """
    from app.core.brep import edit
    from app.core.knowledge.parts.exact import compound

    built = _solid_of(produced.mesh)
    if built is None:
        raise InternalError(detail=f"part {spec.name} built a mesh under the exact kernel")
    anchor, direction = _anchor(source, ctx.params, spec, built)
    flat = _lying_flat(spec, ctx.params, direction)
    on_edge = _standing_on_edge(spec, ctx.params, direction)
    subtractive = cuts(spec, ctx.params)
    sink = 0.0 if subtractive or spec.separate_from_host else BOOLEAN_OVERLAP
    flip = subtractive and _builds_upward_on_a_face(source, ctx.params, built)
    placed = _place_solid(
        built, ctx.params, anchor, sink, direction, spec.keeps_up, flip, cancelled=ctx.cancelled
    )
    body = _solid_of(source.mesh)
    if body is None:
        raise InternalError(detail="the exact part path needs an exact host")
    original_body = body
    lip = None
    rim = None
    bore: Feature | None = None
    if subtractive:
        mouth, outward = _mouth_frame(ctx.params, anchor, direction, spec.keeps_up)
        bore = _seated_bore(source, spec, mouth, outward)
        rim = _over_the_rim(
            body,
            placed,
            mouth,
            outward,
            surface=_surface_at_anchor(source, mouth),
            bore=bore,
            cancelled=ctx.cancelled,
        )
        placed = _opened_to_the_face(placed, body, ctx.params, anchor, direction, spec.keeps_up)
        lip = _lip_on_a_slant(spec, part_params, body, ctx.params, anchor, direction, spec.keeps_up)
    added_features: dict[str, Feature] = {}
    added_findings: list[Finding] = []
    with building("brep") as notes:
        addition = spec.host_add(part_params) if spec.host_add is not None else None
    added_findings.extend(notes)
    if addition is not None:
        placed_addition = _place_solid(
            _exact_form(spec, addition),
            ctx.params,
            anchor,
            0.0,
            direction,
            spec.keeps_up,
            False,
            cancelled=ctx.cancelled,
        )
        body = edit.unified(edit.boolean("union", [body, placed_addition]))
        added_findings.extend(addition.findings)
        added_features = _placed_features(
            addition, spec, ctx.params, anchor, 0.0, direction, spec.keeps_up, False
        )
    findings: list[Finding] = []
    host_features: dict[str, Feature] = {}
    nothing = None
    if spec.separate_from_host:
        prepared = body
        with building("brep") as notes:
            host_cut = spec.host_cut(part_params) if spec.host_cut is not None else None
        findings.extend(notes)
        if host_cut is not None:
            cutter = _exact_form(spec, host_cut)
            placed_cutter = _place_solid(
                cutter,
                ctx.params,
                anchor,
                0.0,
                direction,
                spec.keeps_up,
                False,
                cancelled=ctx.cancelled,
            )
            prepared = edit.unified(edit.boolean("difference", [body, placed_cutter]))
            findings.extend(host_cut.findings)
            nothing = without_effect(body, prepared, "difference", ctx.profile) or _cuts_no_layer(
                body, prepared, cutter, spec, ctx.profile
            )
            host_features = _placed_features(
                host_cut, spec, ctx.params, anchor, 0.0, direction, spec.keeps_up, False
            )
        # Schraube und Mutter liegen im selben Projekt, dürfen aber nicht zu
        # einem unlösbaren Körper verschweißen: ein Verbund aus zwei Körpern.
        mesh = compound(prepared, placed)
    else:
        kind: BooleanKind = "difference" if subtractive else "union"
        mesh = edit.unified(edit.boolean(kind, [body, placed]))
        nothing = without_effect(body, mesh, kind, ctx.profile)
        if nothing is None and subtractive:
            nothing = _cuts_no_layer(body, mesh, built, spec, ctx.profile)
        if bore is not None:
            wider = _in_a_wider_bore(spec, bore, built)
            said = (
                []
                if wider is not None
                else _bore_check(spec, part_params, bore, body, ctx.profile, mouth, outward)
            )
            nothing = wider or (None if said else nothing)
            findings = [*findings, *said]
    _exact_result_checked(mesh)
    features = _merged_features(
        source,
        produced,
        spec,
        ctx.params,
        anchor,
        sink,
        direction,
        flip,
        host_features,
        added_features,
    )
    loose = (
        _host_split(original_body, prepared, spec, source)
        if spec.separate_from_host
        else _hanging_loose(original_body, mesh, spec, subtractive)
    )
    spring = _spring_finding(spec.name, part_params, profile)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh, kind="brep", features=features)],
        findings=[
            *findings,
            *added_findings,
            *produced.findings,
            *([nothing] if nothing else []),
            *([lip] if lip else []),
            *([rim] if rim else []),
            *([loose] if loose else []),
            *([flat] if flat else []),
            *([on_edge] if on_edge else []),
            *([spring] if spring else []),
        ],
    )


@overload
def _opened_to_the_face(
    tool: MeshData,
    host: Mesh,
    params: Any,
    anchor: Vec3,
    direction: Vec3 | None,
    keeps_up: bool,
) -> MeshData: ...


@overload
def _opened_to_the_face(
    tool: Solid,
    host: Mesh,
    params: Any,
    anchor: Vec3,
    direction: Vec3 | None,
    keeps_up: bool,
) -> Solid: ...


def _opened_to_the_face(
    tool: MeshData | Solid,
    host: Mesh,
    params: Any,
    anchor: Vec3,
    direction: Vec3 | None,
    keeps_up: bool,
) -> MeshData | Solid:
    """Ein abtragendes Werkzeug, dessen Öffnung bis über die Fläche an seiner Mündung reicht.

    Jeder abtragende Baustein endet ein Hundertstel über seiner Mündung
    (``BOOLEAN_OVERLAP``, §39) — genug, solange seine Achse senkrecht auf der
    Fläche steht. **Mit einer Richtung, die schräg zur Fläche steht** (von
    Hand eingetragen, vom Assistenten, von der Kommandozeile), liegt die
    Fläche auf der tiefen Seite der Öffnung um bis zu ``R · tan(Neigung)`` über der
    Mündung, und dort blieb ein Keil Material stehen: Durchsicht 0.5.1 (Prüfer
    rest-lippe, rest-schraube) — 17 von 36 Strahlen entlang der Achse trafen
    an der Magnettasche unter 10° Material, am Schraubenloch und am Lagersitz
    608 ebenso, an beiden Kernen und ohne Befund. Der Magnet, die Schraube,
    das Lager kamen nicht hinein.

    Der Deckel der Öffnung wird deshalb entlang der Achse angehoben, bis er
    die Fläche überall um das Hundertstel verlässt: am exakten Kern ein Prisma
    über der Deckfläche (``edit.collared``), am Netz dieselbe Rechnung an den
    Dreiecken (``geom.mesh.lifted_caps``). Was die Richtung sagt, bleibt: Die
    Achse steht, wie eingetragen; nur die Öffnung wird nicht mehr zugedeckt.

    **Gefragt wird die Fläche an der Mündung, nicht der Körper darüber.** Ihre
    Ebene kommt vom Dreieck unter dem Ansatzpunkt; Strahlen durch den ganzen
    Körper hätten eine Tasche neben einer Wand durch die Wand gezogen. Liegt
    der Ansatzpunkt nicht auf der Oberfläche (weiter als die Facettengrenze
    ``MAX_FACET_SAG`` davon, etwa tief im Körper eingetippt), bleibt das
    Werkzeug, wie es ist — ebenso eines, das nicht an der Mündung öffnet (eine
    Magnettasche mit Deckschicht), und eines, dessen Achse von der Fläche
    wegzeigt (das sagt ``parts.cuts_no_layer``).

    Nur bei eingetragener Stelle: An einem benannten Merkmal kommt die
    Richtung von dessen Fläche oder Achse (:func:`_anchor`) und steht nie
    schräg dazu — dort kostete die Frage nach der Oberfläche nur Zeit
    (``on_surface`` an großen Netzen rund 70 ms).
    """
    import numpy as np

    if _placement_value(params, "at_feature", ""):
        return tool

    from app.core.geom.mesh import lifted_caps, stable_normals
    from app.core.geom.section import SectionPlane

    def along_axis(rows: Any, axis: Any) -> Any:
        # Die Höhe entlang einer Richtung, komponentenweise: Sie setzt die
        # Geometrie des Werkzeugs und rechnet deshalb ohne BLAS (RM-187).
        return rows[:, 0] * axis[0] + rows[:, 1] * axis[1] + rows[:, 2] * axis[2]

    # Der Rahmen der Mündung: derselbe wie beim Setzen, ohne Einsenken und
    # Spiegelung — beide geschehen im eigenen System unter der Mündung.
    frame = np.asarray(_matrix(params, anchor, 0.0, direction, keeps_up, False), dtype=np.float64)
    mouth = frame[:3, 3]
    outward = frame[:3, 2] / math.hypot(*(float(value) for value in frame[:3, 2]))
    shape = as_mesh_data(tool)
    points = np.asarray(shape.raw.vertices, dtype=np.float64)
    heights = along_axis(points, outward) - dot3(mouth, outward)
    top = float(heights.max())
    if not EPS_GEOM < top <= BOOLEAN_OVERLAP + EPS_GEOM:
        return tool
    ground = as_mesh_data(host)
    face = _face_under_mouth(ground, mouth, outward)
    if face is None:
        return tool
    closest, facing, along = face
    # Je Randpunkt des Deckels, auf die Mündungsebene gelegt: wie weit die
    # Ebene der Fläche dort entlang der Achse darüber liegt.
    on_level = np.abs(heights - top) <= EPS_GEOM
    rim = points[on_level] - top * outward
    rise = float(along_axis(closest - rim, facing).max()) / along
    if rise <= EPS_GEOM:
        return tool
    # So weit, dass der Deckel die Fläche um dasselbe Hundertstel verlässt wie
    # an einer senkrechten Mündung — höchstens durch den ganzen Körper.
    reach = min(rise, float(ground.bounds.diagonal)) + BOOLEAN_OVERLAP - top
    if isinstance(tool, MeshData):
        normals = np.asarray(stable_normals(shape.raw)[0], dtype=np.float64)
        corners = np.asarray(shape.raw.faces, dtype=np.int64)
        facing_up = along_axis(normals, outward) >= 1.0 - EPS_GEOM
        cap = np.nonzero(facing_up & on_level[corners].all(axis=1))[0]
        if not len(cap):
            return tool
        widened = lifted_caps(shape.raw, [(cap, outward, reach)])
        if not widened.is_watertight or widened.volume <= shape.volume - EPS_GEOM:
            return tool
        if not shape.slots:
            return MeshData.of(widened)
        # Die neue Wand trägt das Filament ihres Deckels.
        walls = len(widened.faces) - shape.triangle_count
        return MeshData.of(widened, slots=(*shape.slots, *[shape.slots[int(cap[0])]] * walls))
    from app.core.brep import edit

    level = dot3(mouth, outward) + top
    normal = (float(outward[0]), float(outward[1]), float(outward[2]))
    return edit.collared(tool, [(SectionPlane(normal=normal, position=level), reach)])


def _face_under_mouth(ground: MeshData, mouth: Any, outward: Any) -> tuple[Any, Any, float] | None:
    """Die Fläche an der Mündung: nächster Punkt, Richtung, Anteil der Achse entlang ihrer Richtung.

    ``None``, wenn die Mündung nicht auf der Oberfläche liegt (weiter als die
    Facettengrenze ``MAX_FACET_SAG`` davon) oder die Achse von der Fläche
    wegzeigt. Gefragt wird das Dreieck unter dem Ansatzpunkt, nicht der Körper
    darüber (:func:`_opened_to_the_face`).
    """
    import numpy as np

    from app.core.geom.mesh import on_surface, stable_normals

    closest, distance, triangle = on_surface(ground.raw, np.asarray(mouth)[None, :])
    if float(distance[0]) > MAX_FACET_SAG:
        return None
    facing = np.asarray(stable_normals(ground.raw)[0][int(triangle[0])], dtype=np.float64)
    along = dot3(outward, facing)
    if along <= EPS_GEOM:
        return None
    return closest[0], facing, along


def _lip_on_a_slant(
    spec: PartSpec,
    part_params: BaseParams,
    host: Mesh,
    params: Any,
    anchor: Vec3,
    direction: Vec3 | None,
    keeps_up: bool,
) -> Finding | None:
    """Hält die Haltelippe noch ringsum, wenn der Baustein schräg zur Fläche steht? (RM-277)

    Die Richtung bleibt Eingabe, und die Öffnung reicht seit
    :func:`_opened_to_the_face` bis über die Fläche. Die Lippe aber liegt knapp
    unter der Mündung (an der Magnettasche 0,4 mm), und auf der Seite, auf der die
    Fläche abfällt, liegt diese am Rand der Lippe um bis zu ``R · tan(Neigung)``
    tiefer. Durchsicht 0.5.1 (rest-schraube): Unter 10° fehlte die Lippe einer
    Magnettasche 8x3 auf 31 % des Umfangs, unter 20° auf 41 %, ohne Befund.

    **Die Grenze kommt aus der Geometrie**, nicht aus einer Gradzahl: Je Punkt
    des Umrisses, an dem die Lippe halten muss (:class:`RetainingLip`), wie tief
    die Ebene der Fläche entlang der Achse unter der Mündung liegt; tiefer als
    die Lippe reicht, fehlt sie dort. Gesagt wird es als Warnung mit *Eingabe
    korrigieren*, gedreht wird nichts (Regel 21) — die Richtung steht im Schritt,
    und senkrecht zur Fläche gesetzt hält die Lippe ringsum.

    Wie beim Öffnen nur bei eingetragener Stelle: An einem Merkmal kommt die
    Richtung aus dessen Fläche und steht nie schräg dazu.
    """
    import numpy as np

    if spec.retaining_lip is None or _placement_value(params, "at_feature", ""):
        return None
    lip = spec.retaining_lip(part_params)
    if lip is None or not lip.rim:
        return None
    frame = np.asarray(_matrix(params, anchor, 0.0, direction, keeps_up, False), dtype=np.float64)
    mouth = frame[:3, 3]
    outward = frame[:3, 2] / math.hypot(*(float(value) for value in frame[:3, 2]))
    face = _face_under_mouth(as_mesh_data(host), mouth, outward)
    if face is None:
        return None
    closest, facing, along = face
    rim = np.asarray(lip.rim, dtype=np.float64)
    points = rim[:, :1] * frame[:3, 0] + rim[:, 1:2] * frame[:3, 1] + mouth
    # Wie weit die Ebene der Fläche je Randpunkt entlang der Achse unter der Mündung liegt.
    below = lying_along(points - closest, facing) / along
    if float(below.max()) <= lip.height + EPS_GEOM:
        return None
    return Finding(
        code="parts.lip_on_a_slant",
        severity="warning",
        message=_(
            "{lip} hält nur auf einer Seite, weil der Baustein schräg zur Fläche steht. Er "
            "gehört senkrecht auf die Fläche.",
            lip=lip.name,
        ),
        values={
            "part": spec.name,
            "angle_deg": round(exact_acos_degrees(along), 1),
        },
        # Regel 17: Die Richtung steht im Schritt.
        suggestions=(CORRECT_INPUT,),
    )


def _exact_form(spec: PartSpec, produced: PartResult) -> Solid:
    """Der exakte Körper eines Begleitteils (Trägeraufbau, Vorbereitung des Sitzes)."""
    solid = _solid_of(produced.mesh)
    if solid is None:
        raise InternalError(detail=f"part {spec.name} built a mesh under the exact kernel")
    return solid


def _exact_result_checked(solid: Solid) -> None:
    """Nach dem Schnitt muss noch ein geschlossener Körper da sein — dieselben Sätze
    wie bei den exakten Hohlraumhandlungen.
    """
    from app.core.geom.boolean import NOTHING_LEFT_DETAIL, NOTHING_LEFT_TITLE

    if solid.volume <= EPS_GEOM or solid.face_count == 0:
        raise GeometryError(
            title=NOTHING_LEFT_TITLE,
            detail=NOTHING_LEFT_DETAIL,
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    if not solid.is_closed:
        raise GeometryError(
            detail=_(
                "Nach diesem Baustein ist der Körper nicht mehr geschlossen. Den Baustein "
                "an einer anderen Stelle oder mit anderen Maßen setzen."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )


def _concatenated_with_slots(body: MeshData, placed: MeshData) -> MeshData:
    """Hängt ein lösbares Teil an und erhält jede Materialzuweisung.

    ``trimesh.concatenate`` lässt die Flächen beider Netze in ihrer Reihenfolge
    stehen. Damit können auch die Slots ohne räumliche Näherung angehängt
    werden. Hat nur eines der Netze eine Zuweisung, bekommt das andere den
    Standard-Slot null — eine unvollständige Liste wäre beim Export nicht
    eindeutig und ``MeshData.replacing`` müsste sie deshalb ganz verwerfen.
    """
    mesh = concatenated([body.raw, placed.raw])
    if not body.slots and not placed.slots:
        return MeshData.of(mesh)

    body_slots = body.slots or ((0,) * body.triangle_count)
    placed_slots = placed.slots or ((0,) * placed.triangle_count)
    return MeshData.of(mesh, slots=(*body_slots, *placed_slots))


def _built_part(
    spec: PartSpec,
    params: BaseParams,
    profile: Profile | None,
    quality: Quality,
    *,
    parameters: Mapping[str, float] | None = None,
    kernel: Kernel = "mesh",
) -> tuple[BaseParams, PartResult]:
    """Vorschau und Operation bauen dieselben Maße mit demselben Materialprofil.

    ``kernel`` wählt, in welchem Kern die Formbeschreibung gerechnet wird
    (P2.7); was die Formen dabei zu sagen haben (``shapes.note``), hängt an
    den Befunden des Teils.
    """
    values = _part_values(spec, params, profile)
    for field in spec.params.spec():
        if field.kind == "sketch" and values.get(field.name):
            from app.core.sketch.serialize import resolve_sketch_values

            values[field.name] = resolve_sketch_values(values[field.name], parameters)
    part_params = spec.params(**values)
    with building(kernel) as notes:
        if spec.build_with_profile is not None:
            produced = spec.build_with_profile(part_params, profile, quality)
        else:
            produced = spec.fn(part_params)
    produced.findings.extend(notes)
    return part_params, produced


def placed_tool(
    source: SceneObject,
    spec: PartSpec,
    params: BaseParams,
    profile: Profile | None,
    *,
    parameters: Mapping[str, float] | None = None,
) -> MeshData:
    """Der Werkzeugkörper eines gesetzten Bausteins, dort, wo sein Schritt ihn hinsetzt.

    Im Rahmen des Objekts und mit genau der Lage der Operation — Anker am
    Merkmal oder an der eingetragenen Stelle, Richtung, Rolle, Einsenken,
    Spiegelung (:func:`_insert_at`). Für den Geist beim Zug an einem Baustein
    (RM-174): Die Ansicht zeigte bis dahin nur die Marke des einen Merkmals,
    das man angefasst hatte; der Rest des Bausteins folgte erst beim Loslassen.
    Mit diesem Körper wandert der ganze Umriss. Er wird einmal zu Beginn des
    Zugs gebaut (im Arbeiter, ``wartezeit.md``) und dann nur verschoben — ein
    Versatz in ``x``/``y``/``z`` ist eine reine Verschiebung.

    ``source`` ist der Körper, an dem der Schritt ansetzt; ein benanntes
    Merkmal muss dort stehen. Ein Trägeraufbau (``host_add``) ist nicht Teil
    des Werkzeugs, er wächst mit.
    """
    profile = for_object(profile, source) if profile is not None else None
    _part_params, produced = _built_part(spec, params, profile, "fine", parameters=parameters)
    built = as_mesh_data(produced.mesh)
    anchor, direction = _anchor(source, params, spec, built)
    subtractive = cuts(spec, params)
    sink = 0.0 if subtractive or spec.separate_from_host else BOOLEAN_OVERLAP
    flip = subtractive and _builds_upward_on_a_face(source, params, built)
    return _place(built, params, anchor, sink, direction, spec.keeps_up, flip)


def lands_on(host: Mesh, tool: MeshData) -> bool:
    """Ob ein Werkzeugkörper den Träger überhaupt erreicht.

    Die zweite Hälfte von RM-174: Ein Zug neben die Fläche soll schon vor dem
    Loslassen zeigen, dass der Baustein dort nicht landet. Gefragt wird das
    Volumen der Überdeckung, nicht die Hüllquader: Ein Werkzeug neben einem
    L-förmigen Teil liegt in dessen Hülle und trifft trotzdem nichts. Ein
    aufgesetzter Baustein sinkt ein Hundertstel ein und überdeckt damit
    einen dünnen Streifen — auch das zählt.
    """
    body = as_mesh_data(host)
    low = [max(a, b) for a, b in zip(body.bounds.minimum, tool.bounds.minimum, strict=True)]
    high = [min(a, b) for a, b in zip(body.bounds.maximum, tool.bounds.maximum, strict=True)]
    if any(top < bottom - EPS_GEOM for bottom, top in zip(low, high, strict=True)):
        return False
    overlap = boolean("intersection", [body, tool], quality="fine", allow_empty=True)
    return float(overlap.mesh.volume) > EPS_GEOM


def placement_tool(
    spec: PartSpec,
    values: Mapping[str, Any],
    profile: Profile,
    *,
    parameters: Mapping[str, float] | None = None,
) -> MeshData:
    """Der Hauptkörper der Platzierung; Begleitgeometrie liefert placement_tools."""
    return placement_tools(spec, values, profile, parameters=parameters)[0]


def placement_tools(
    spec: PartSpec,
    values: Mapping[str, Any],
    profile: Profile,
    *,
    standalone: bool = False,
    parameters: Mapping[str, float] | None = None,
) -> tuple[MeshData, MeshData | None]:
    """Der wirkliche Baustein lokal an einer Oberfläche, vor deren Rahmenmatrix.

    Drehung, Einsenken und Schnittspiegelung sind enthalten. Der Aufrufer legt
    nur noch ``frame_of`` darüber. Ausdruckswerte müssen vorher wie für die
    Operation aufgelöst werden; ein Zielmaterial übergibt er über ``for_object``.
    """
    from app.core.registry import validate

    schema = build_params(spec)
    known = {entry.name for entry in schema.fields()}
    local = {name: value for name, value in values.items() if name in known}
    local.update(
        {
            placement_fields(schema)[name]: value
            for name, value in {"x": 0.0, "y": 0.0, "z": 0.0, "at_feature": ""}.items()
        }
    )
    local.update(zip(normal_fields(schema), (0.0, 0.0, 1.0), strict=True))
    params = validate(schema, local)
    part_params, produced = _built_part(spec, params, profile, "fine", parameters=parameters)
    mesh = as_mesh_data(produced.mesh)
    subtractive = cuts(spec, params)
    sink = 0.0 if standalone or subtractive or spec.separate_from_host else BOOLEAN_OVERLAP
    flip = subtractive and _extends_above_mouth(mesh)
    primary = _place(
        mesh, params, sink=sink, direction=(0.0, 0.0, 1.0), keeps_up=spec.keeps_up, flip=flip
    )
    extra = spec.host_add(part_params) if spec.host_add is not None else None
    addition = (
        None
        if extra is None
        else _place(
            as_mesh_data(extra.mesh), params, direction=(0.0, 0.0, 1.0), keeps_up=spec.keeps_up
        )
    )
    return primary, addition


def _part_values(spec: PartSpec, params: Any, profile: Profile | None) -> dict[str, Any]:
    """Die eigenen Parameter des Bausteins aus denen der Operation, mit dem
    eingefüllten Spiel.
    """
    wanted = {entry.name for entry in spec.params.fields()}
    values = {name: getattr(params, name) for name in wanted if hasattr(params, name)}
    if PLAY_FIELD in values and not values[PLAY_FIELD] and profile is not None:
        # Regel 7: die Toleranz ist ein Verweis ins Materialprofil, nie eine Zahl
        # in der Datei.
        values[PLAY_FIELD] = profile.material.clearance
    if (
        spec.grip_from_profile
        and GRIP_FIELD in values
        and not values[GRIP_FIELD]
        and profile is not None
    ):
        # Dasselbe für das Übermaß, und ``press`` steht im Profil negativ:
        # gemeint ist der Betrag, um den es enger wird.
        values[GRIP_FIELD] = abs(profile.material.press)
    return values


def _placed_by_hand(params: Any) -> bool:
    """Ob jemand die Position selbst eingetragen hat.

    **Ohne Merkmal ist nicht dasselbe wie ohne Wahl.** Die ausgelieferten
    Beispielprojekte setzen ihre Bausteine über *x/y/z* — die Mutternfalle des
    Gehäuses steht auf (-25, -15, 4), und ``at_feature`` ist dort leer, weil
    sie es sein soll. Eine Prüfung, die nur nach dem Merkmal fragt, hält diese
    Projekte an: gemessen am 25.08.2026 mit 37 roten Tests, davon sieben
    Beispieldateien, die seit Monaten rechnen.

    Gefragt wird deshalb nach beidem. Erst wenn weder eine Stelle gewählt noch
    eine Position eingetragen ist, hat wirklich niemand etwas gesagt — und
    genau das ist der Zustand, in dem ein frisch geöffneter Dialog steht.

    Ein Parameterausdruck (``=@wand``) zählt als eingetragen, auch wenn er sich
    zu null auswertet: Wer ihn hinschreibt, hat eine Absicht.
    """
    for field in (
        *(placement_fields(type(params))[name] for name in ("x", "y", "z")),
        *normal_fields(type(params)),
    ):
        value = getattr(params, field, 0.0)
        if isinstance(value, str):
            return True
        try:
            if float(value) != 0.0:
                return True
        except TypeError, ValueError:
            return True
    return False


def _anchor(
    source: SceneObject,
    params: Any,
    spec: PartSpec | None = None,
    built: Mesh | None = None,
) -> tuple[Vec3, Vec3 | None]:
    """Wohin der Baustein kommt **und wohin er schaut** — an ein benanntes
    Merkmal, oder an den Ursprung (§25).

    §25 verlangt „einen Baustein an ein erkanntes Merkmal setzen". Der Name
    genügt dafür — es ist derselbe Name, den der Nutzer angeklickt und über den
    der Agent gesprochen hat (§18.5), und ein Merkmal, das nicht da ist, sagt
    das, statt den Baustein irgendwo Plausiblem abzusetzen.

    **Die Richtung stand hier lange nicht, und das war der teuerste Handgriff
    der ganzen Bibliothek.** Gelesen wurde nur ``centre``; wohin der Baustein
    zeigt, kam aus dem Feld *Achse*, und dessen Vorgabe ist Z. Wer eine
    Seitenwand anklickte, bekam ein Schraubenloch, das nach oben bohrt —
    gemessen an einem Würfel: Loch-Achse [0 0 1] gegen Flächennormale
    [-1 0 0], Skalarprodukt 0,00, exakt quer. Und es ist der häufigste
    Handgriff überhaupt: Man zeigt auf eine Wand, und was man bekommt, steckt
    in der Decke.

    Eine Fläche schaut entlang ihrer Normalen, eine Bohrung entlang ihrer
    Achse. Eine Kantenschleife hat weder noch; dann bleibt die Richtung
    ``None``, und es gilt wieder, was unter *Achse* gewählt ist.

    **Und eine Bohrung wird an ihrer Mündung angesetzt, nicht in ihrer
    Mitte** — dafür ist ``built`` da (:func:`_at_the_mouth`).
    """
    name = str(_placement_value(params, "at_feature", "") or "")
    if not name:
        if spec is not None and (spec.at_face or spec.at_hole) and not _placed_by_hand(params):
            # **Nie stillschweigend raten** (Regel 21). Hier stand ein
            # kommentarloses ``(0, 0, 0), None``, und damit landete ein
            # Anbauteil ohne gewählte Fläche im Ursprung: mitten im Körper,
            # halb unter dem Druckbett, mit Richtung Z statt der Flächen-
            # normalen. Am Lochwand-Einhänger gemessen — 717 mm³ statt 2358,
            # dazu vier Befunde, von denen keiner sagte, was fehlt.
            #
            # Aufgefallen ist es erst, als jemand den Weg **durch die
            # Oberfläche** ging: Im Katalog wählt man einen Baustein, nicht
            # eine Fläche, und „An Merkmal" steht dann auf „— keines —".
            # Jeder Test hatte es gesetzt, weil jeder Test wusste, dass es
            # gebraucht wird.
            raise AppError(
                _("Für diesen Baustein fehlt die Stelle, an die er soll."),
                detail=_(
                    "Er wird an eine Fläche oder eine Bohrung gesetzt, und ohne "
                    "sie weiß er weder wohin noch in welche Richtung. Es ist auch "
                    "keine Position eingetragen — so säße er im Nullpunkt des "
                    "Objekts, halb darin und halb darunter."
                ),
                values={"part": spec.name},
                suggestions=(
                    Action(
                        id="pick_feature",
                        label=_("Klicken Sie die Fläche im Viewport an, dann den Baustein."),
                    ),
                    Action(
                        id="pick_in_tree",
                        label=_("Oder wählen Sie sie unter „An Merkmal“ im Dialog."),
                    ),
                ),
            )
        return (0.0, 0.0, 0.0), _free_direction(params)

    feature = source.features.get(name)
    if feature is None:
        raise AppError(
            _("Dieses Merkmal gibt es an diesem Objekt nicht."),
            detail=_(
                "Der Name muss eines der Merkmale sein, die dieses Objekt trägt — "
                "sie stehen unten als bekannte Namen."
            ),
            values={"feature": name, "known": ", ".join(sorted(source.features))},
            suggestions=(
                Action(id="pick_feature", label=_("Wählen Sie das Merkmal im Objektbaum aus.")),
            ),
        )
    centre = feature.params.get("centre", (0.0, 0.0, 0.0))
    point: Vec3 = (float(centre[0]), float(centre[1]), float(centre[2]))
    direction = direction_of(feature)
    return _at_the_mouth(point, direction, feature, built, spec), direction


def _at_the_mouth(
    point: Vec3,
    direction: Vec3 | None,
    feature: Feature,
    built: Mesh | None,
    spec: PartSpec | None,
) -> Vec3:
    """Der Ansatzpunkt an einer Bohrung — ihre Mündung statt ihrer Mitte.

    Ein Bohrungsmerkmal nennt als ``centre`` die **Mitte** des Zylinders, und
    genau die stand hier lange als Ansatzpunkt. Ein abtragender Baustein liegt
    aber unter seiner Mündung (§24.1): Das Innengewinde beginnt bei z = 0 und
    reicht nach -Z. Zusammen hieß das, dass ein 12 mm langes Gewinde in einer
    10 mm dicken Platte bei z = 5 anfing — die untere Hälfte geschnitten, die
    obere glatt, und sieben Millimeter Werkzeug hingen unter der Platte in der
    Luft. Über eine *Fläche* gesetzt war derselbe Handgriff immer richtig, und
    deshalb ist es an keiner Stelle aufgefallen.

    Die Mündung ist das Ende in Richtung der Achse: Das Werkzeug baut in die
    Gegenrichtung, also deckt es von dort aus die ganze Bohrung ab. **Das gilt
    für beide Vorzeichen** — die Achse einer erkannten Bohrung kommt aus einem
    Eigenvektor und darf zeigen, wohin sie will. Zeigt sie nach unten, liegt
    die Mündung unten und das Werkzeug wächst nach oben; gedeckt ist derselbe
    Bereich.

    **Nur für einen Baustein, der unter seinem Ursprung liegt.** Die
    Mutternfalle tut das nicht — ihre Tasche wächst nach oben, weil die Mutter
    im Material sitzt. An die Mündung gesetzt stünde sie vollständig über dem
    Teil und trüge nichts ab. Gefragt wird deshalb der gebaute Körper und
    nicht eine Liste von Namen: Wer einen Baustein dazunimmt, der unter seiner
    Mündung liegt, bekommt die richtige Behandlung, ohne sie irgendwo
    einzutragen.

    **An einer Fläche fängt das die Mutternfalle nicht ab.** Der Satz oben,
    über eine Fläche sei der Handgriff immer richtig, galt nur für Bausteine,
    die nach unten bauen: Deren Körper sinkt an der Deckfläche von selbst ins
    Material. Ein nach oben bauender wächst dort in die Luft über der Fläche
    und trägt nichts ab — das übernimmt :func:`_builds_upward_on_a_face` mit
    einer Spiegelung, nicht diese Funktion.
    """
    if feature.kind != "hole" or direction is None or built is None:
        return point
    depth = float(feature.params.get("depth") or 0.0)
    if depth <= EPS_GEOM:
        return point
    if (
        not (spec is not None and spec.at_hole_mouth)
        and float(built.bounds.maximum[2]) > BOOLEAN_OVERLAP + EPS_GEOM
    ):
        return point
    reach = depth / 2.0
    return (
        point[0] + direction[0] * reach,
        point[1] + direction[1] * reach,
        point[2] + direction[2] * reach,
    )


def _builds_upward_on_a_face(source: SceneObject, params: Any, built: Mesh) -> bool:
    """Ob ein abtragender Baustein an einer Fläche nach oben in die Luft bauen
    würde — dann wird er in Z gespiegelt (§24.1).

    Ein abtragender Baustein liegt unter seiner Mündung: An eine Deckfläche
    gesetzt sinkt sein Körper ins Material, weil er nach -Z baut. Die
    Mutternfalle ist die Ausnahme — ihre Tasche wächst nach +Z, weil die Mutter
    im Material sitzt (:func:`_at_the_mouth`). An eine **Fläche** gesetzt stünde
    sie damit vollständig über deren Oberfläche und trüge nichts ab: gemessen
    an einer Deckfläche kam ``boolean.without_effect`` zurück, das Volumen der
    Platte blieb unverändert.

    Erkannt wird das am gebauten Körper und nicht an einer Namensliste, wie bei
    der Mündung: Reicht er über die Mündung hinaus (``bounds.maximum[2]`` über
    dem Überlappungsmaß) und sitzt er an einer Fläche, wird er in Z gespiegelt.
    Danach liegt seine Öffnung an der Fläche und die Tasche darunter im Material
    — genau wie bei jedem anderen abtragenden Baustein. An einer Bohrung
    geschieht nichts: Dort hält ``_at_the_mouth`` die Tasche schon in der Mitte.
    """
    name = str(_placement_value(params, "at_feature", "") or "")
    feature = source.features.get(name) if name else None
    if not name and _free_direction(params) is not None:
        return _extends_above_mouth(built)
    if feature is None or feature.kind != "face":
        return False
    return _extends_above_mouth(built)


def _on_its_own_bed(
    spec: PartSpec, params: Any, built: Mesh, direction: Vec3 | None
) -> tuple[Vec3 | None, float]:
    """Richtung und Einsenken eines Bausteins ohne Träger (RM-562).

    Am Träger beginnt ein Baustein an der Mündung: Eine Schraube hat den Kopf
    darüber und den Schaft darunter, eine lösbare Mutter steht um das Spiel
    über der Fläche (``separate_from_host``). Ohne Träger hinge der Schaft unter
    dem Druckbett und die Mutter schwebte. Hier steht die Unterseite auf der
    Ebene des Ursprungs, und was an einer Mündung sitzt (``at_hole_mouth``),
    steht auf dem Kopf, wie man eine Schraube druckt. Eine eingetragene
    Richtung oder Achse gilt, wie sie ist.
    """
    low = float(built.bounds.minimum[2])
    upright = direction is None and _placement_value(params, "axis", "z") == "z"
    if spec.at_hole_mouth and upright:
        return (0.0, 0.0, -1.0), float(built.bounds.maximum[2])
    return direction, low if abs(low) > EPS_GEOM else 0.0


def _extends_above_mouth(built: Mesh) -> bool:
    """Die eine Spiegelungsentscheidung für Schnittvorschau und tatsächliche Op."""
    return float(built.bounds.maximum[2]) > BOOLEAN_OVERLAP + EPS_GEOM


def _free_direction(params: Any) -> Vec3 | None:
    """Normiert die gespeicherte Oberflächenrichtung, ohne Null auf eine Achse zu raten."""
    names = normal_fields(type(params))
    values = tuple(float(getattr(params, name, 0.0)) for name in names)
    length = math.hypot(*values)
    if not math.isfinite(length):
        raise ValidationError(
            field=names[0],
            detail=_("Die Oberflächenrichtung ist ungültig. Die Fläche erneut wählen."),
        )
    if not length:
        return None
    return (values[0] / length, values[1] / length, values[2] / length)


def direction_of(feature: Feature) -> Vec3 | None:
    """Wohin ein Merkmal schaut — oder ``None``, wenn es das nicht sagt.

    Dieselbe Frage beantwortet ``geom.align.frame_of`` fürs Ausrichten, und
    dort ist eine Art ohne Richtung ein Fehler mit Handlungsvorschlag. Hier
    ist sie keiner: Ein Baustein an einer Kantenschleife hat einen Ort und
    behält seine gewählte Achse. Die Antworten sind gleich, die Folgen nicht —
    deshalb steht die Frage zweimal da.

    **Öffentlich, weil der Griff dieselbe Achse braucht** (14.09.2026): Ein
    Baustein an einem benannten Merkmal dreht sich um dessen Richtung, und
    ``MainWindow._part_turned`` muss dieselbe Antwort bekommen wie
    :func:`_matrix` — sonst dreht der Ring um eine Achse, die der Schritt
    nicht kennt.
    """
    raw = feature.params.get("normal") or feature.params.get("axis")
    if raw is None:
        return None
    values = tuple(float(value) for value in raw)
    # ``math.hypot`` rechnet CPython selbst; ``** 0.5`` ruft das ``pow`` der
    # Plattform (RM-187).
    length = math.hypot(*values)
    if length <= EPS_GEOM:
        return None
    return (values[0] / length, values[1] / length, values[2] / length)


def _place(
    mesh: MeshData,
    params: Any,
    anchor: Vec3 = (0.0, 0.0, 0.0),
    sink: float = 0.0,
    direction: Vec3 | None = None,
    keeps_up: bool = False,
    flip: bool = False,
) -> MeshData:
    """Der Baustein an seinem Platz.

    **Eine Quelle für zwei Antworten.** Diese Funktion und :func:`_matrix`
    bauten dieselbe Kette aus Einsenken, Drehen und Verschieben zweimal — als
    Netz und als Matrix, die eine für die Geometrie, die andere für die
    Merkmale. Zwei Kopien derselben Rechnung laufen auseinander, sobald eine
    von beiden erweitert wird, und das Einbauen der Flächenrichtung wäre genau
    so eine Erweiterung gewesen. Jetzt rechnet :func:`_matrix`, und hier wird
    sie angewendet.
    """
    from app.core.geom.transform import apply

    return apply(mesh, _matrix(params, anchor, sink, direction, keeps_up, flip))


def _placed_features(
    produced: PartResult,
    spec: PartSpec,
    params: Any,
    anchor: Vec3 = (0.0, 0.0, 0.0),
    sink: float = 0.0,
    direction: Vec3 | None = None,
    keeps_up: bool = False,
    flip: bool = False,
    taken: Iterable[str] = (),
) -> dict[str, Feature]:
    """Die Merkmale des Bausteins, mitbewegt und mit einem Namen, den es hier
    noch nicht gibt.

    ``bore_1`` des dritten eingefügten Bausteins überschriebe sonst das des
    ersten. Der Bausteinname trennt die Sorten (``screw_hole_bore_1`` gegen
    ``heatset_bore_1``); was **danach** noch gleich heißt, bekommt in
    :func:`_free_name` eine Ziffer.

    **Hier stand, der Bausteinname und die Position machten es eindeutig — und
    die Position stand nie im Namen.** Der Satz las sich wie eine geprüfte
    Entscheidung, und deshalb hat die Stelle jahrelang niemand nachgerechnet;
    was ``taken`` heute leistet, leistete bis zum 04.09.2026 niemand. Wer die
    Namensgebung ändert, ändert diesen Absatz mit.
    """
    from app.core.perceive.matching import moved_features

    matrix = _matrix(params, anchor, sink, direction, keeps_up, flip)
    moved = moved_features(dict(produced.features), matrix)
    used = set(taken)
    placed: dict[str, Feature] = {}
    for name, feature in moved.items():
        public = _free_name(f"{spec.name}_{name}", used)
        used.add(public)
        placed[public] = dataclasses.replace(feature, id=public)
    return placed


def _free_name(wanted: str, taken: Container[str]) -> str:
    """``wanted``, oder der nächste freie Name daneben.

    **Der Docstring über dieser Stelle versprach Kollisionsfreiheit, und der
    Code löste sie nicht ein.** „Bausteinname und Position machen es
    eindeutig" stand dort — im Namen stand aber nur der Bausteinname. Wer
    denselben Baustein zweimal einfügt, bekam zweimal `printed_thread_thread_1`,
    und `features.update()` beim Aufrufer behielt das letzte.

    Gemessen an der Projektdatei eines Kunden (M4, M6 und M8 auf einer Platte,
    04.09.2026): Von drei erzeugten Gewindemerkmalen blieb **eines** übrig,
    ohne Befund und ohne Meldung. Bei zehn Millimetern Länge fiel es kaum auf,
    weil die Wendelerkennung für die zwei verlorenen einsprang; bei fünf
    Millimetern greift sie nicht mehr, und dann standen statt zwei Gewinden
    **vier Zapfen und ein Kegel** im Baum — die Unterdrückung der Phantome
    hängt am erzeugten Merkmal, und das war weg.

    **Der erste behält seinen Namen.** Nur wer kollidiert, bekommt eine Ziffer
    — so bleibt jede vorhandene Projektdatei gültig, denn die zweiten und
    dritten Merkmale gab es dort bisher gar nicht. Gezählt wird wie bei der
    Erkennung (`hole_1`, `hole_2`), weil das die Schreibweise des Hauses ist;
    dass ein gelöschter Schritt die Nummern verschieben kann, ist der bekannte
    Fall aus §21.3, und dafür fragt die Zuordnung nach.
    """
    if wanted not in taken:
        return wanted
    number = 2
    while f"{wanted}_{number}" in taken:
        number += 1
    return f"{wanted}_{number}"


def _roll_upright(direction: Vec3) -> Any:
    """Die Drehung um ``direction``, die das eigene -Y des Bausteins aufrichtet.

    ``rotation_between`` legt fest, wohin das +Z eines Bausteins zeigt, und
    lässt offen, wie er dabei um diese Achse **rollt**. Für eine Bohrung ist
    das gleichgültig. Für einen Baustein mit einem Oben ist es der Unterschied
    zwischen Halten und Herunterfallen (``PartSpec.keeps_up``).

    Gesucht ist die Drehung um die Flächennormale, nach der das **-Y** so weit
    nach oben zeigt, wie die Fläche es zulässt: Von der Welt-Senkrechten bleibt
    in der Flächenebene der Anteil senkrecht zur Normalen, und auf den wird das
    -Y gedreht. Steht die Fläche waagerecht, ist dieser Anteil null — in der Ebene
    eines Deckels gibt es kein Oben, und dann bleibt es bei der kürzesten
    Drehung. Der Rückgabewert ist dort die Einheitsmatrix, nicht etwa ein
    Fehler: Ein Einhänger auf einem Deckel ist eine merkwürdige Wahl, aber
    keine unmögliche.
    """
    import numpy as np

    from app.core.geom.align import rotation_between
    from app.core.geom.transform import turned as turned_by
    from app.core.units import dot3, exact_atan2_degrees

    # Längen über ``math.hypot``, Skalarprodukte über ``dot3``, der Winkel über
    # ``exact_atan2_degrees`` (RM-187): ``np.linalg.norm``, ``np.dot``, ``@``
    # und ``math.atan2`` runden die letzte Stelle je Maschine anders, und am
    # Schlüsselloch drehte das Rauschen eines ULP den ganzen Baustein mit.
    normal = np.asarray(direction, dtype=float)
    length = math.hypot(float(normal[0]), float(normal[1]), float(normal[2]))
    if length < 1e-9:
        return np.eye(4)
    normal = normal / length
    # Als Tripel aus echten ``float``: ``tuple(np.ndarray)`` gibt ``float64``,
    # und die Signaturen hier erwarten ``tuple[float, float, float]``.
    unit: Vec3 = (float(normal[0]), float(normal[1]), float(normal[2]))

    # Was von der Welt-Senkrechten in der Flächenebene übrig bleibt.
    up = np.array([0.0, 0.0, 1.0])
    up_in_face = up - dot3(up, normal) * normal
    reach = math.hypot(float(up_in_face[0]), float(up_in_face[1]), float(up_in_face[2]))
    if reach < 1e-6:
        return np.eye(4)
    up_in_face = up_in_face / reach

    # Wo das +Y nach der kürzesten Drehung liegt, ebenfalls auf die Ebene
    # bezogen — nur der Anteil in der Ebene lässt sich durch Rollen bewegen.
    # **Oben ist -Y, nicht +Y.** Das ist die Konvention des Hauses und nicht
    # frei gewählt: Der zweite Weg, einen Baustein umzulegen, ist ``axis="y"``,
    # und der dreht mit ``rotation("x", -90)`` das eigene +Y nach Welt **unten**.
    # Das Schlüsselloch baut seit je danach — sein Docstring sagt es wörtlich,
    # „der Schlitz läuft in -Y, damit er nach dem Umlegen aufwärts zeigt". Die
    # erste Fassung dieser Funktion richtete +Y auf, also genau andersherum, und
    # machte damit die Bauweise **eines** Bausteins zur Regel für alle: Am
    # Schlüsselloch saß der Schraubensitz danach unten und der Kopfdurchlass
    # oben — aufgehängt wäre das Teil beim Loslassen von der Wand gefallen.
    lying = turned_by(np.array([0.0, -1.0, 0.0]), rotation_between((0.0, 0.0, 1.0), unit))
    own = lying - dot3(lying, normal) * normal
    span = math.hypot(float(own[0]), float(own[1]), float(own[2]))
    if span < 1e-6:
        return np.eye(4)
    own = own / span

    # Der Winkel von ``own`` nach ``up_in_face``, um die Normale gemessen —
    # ``atan2`` gibt ihn mit Vorzeichen, ein ``arccos`` allein nicht.
    degrees = exact_atan2_degrees(dot3(np.cross(own, up_in_face), normal), dot3(own, up_in_face))
    if abs(degrees) < 1e-9:
        return np.eye(4)
    # Dieselbe Drehung wie überall (``transform.rotation_about``, RM-187): Mit
    # ``math.sin(math.radians(180))`` blieb an einer -Y-Wand 1,2·10⁻¹⁶ statt null
    # in der Matrix, und ein Keil lag um dieses Haar neben seiner Fläche.
    return rotation_about(unit, (0.0, 0.0, 0.0), degrees)


def _matrix(
    params: Any,
    anchor: Vec3 = (0.0, 0.0, 0.0),
    sink: float = 0.0,
    direction: Vec3 | None = None,
    keeps_up: bool = False,
    flip: bool = False,
) -> Any:
    """Einsenken, drehen, verschieben — als eine Matrix.

    Die Reihenfolge trägt die Bedeutung von *Drehung*: Mit einer Richtung aus
    dem Merkmal dreht ``angle`` **zuerst** um die eigene Achse des Bausteins,
    und die Fläche legt ihn danach um. Damit heißt „um 30 Grad drehen"
    dasselbe, gleich ob die Fläche oben liegt oder an der Seite — ein Winkel
    um die Weltachse wäre an einer Wand etwas anderes als auf dem Deckel.

    Das Einsenken bleibt vor allen Drehungen: Es geschieht im eigenen System
    des Bausteins, wo -Z in den Träger hineingeht, gleich wohin er danach
    gelegt wird.

    ``flip`` spiegelt den Baustein zuallererst an seiner XY-Ebene — für einen
    abtragenden Baustein, der nach oben baut und an eine Fläche gesetzt sonst in
    die Luft darüber wüchse (:func:`_builds_upward_on_a_face`). Die Spiegelung
    geschieht ebenfalls im eigenen System, vor dem Einsenken und Drehen, damit
    die Fläche danach die gespiegelte Öffnung auf sich zu legt.
    """
    import numpy as np

    from app.core.geom.ops import as_transform

    axis = _placement_value(params, "axis", "z")
    angle = float(_placement_value(params, "angle", 0.0))
    matrix = np.eye(4)
    if flip:
        mirror = np.eye(4)
        mirror[2, 2] = -1.0
        # Nach der Spiegelung reicht die Öffnung ein Hundertstel über die
        # Mündung hinaus. Sonst fiele die Öffnungsfläche mit der Trägerfläche
        # zusammen — der klassische Weg, eine boolesche Operation zu brechen
        # (§39). Ein aufsitzender Baustein bekommt das über ``sink``, ein
        # abtragender reicht sonst von selbst hinaus; nur dieser gespiegelte
        # endet genau an der Mündung und braucht den Überstand eigens.
        matrix = composed(translation((0.0, 0.0, BOOLEAN_OVERLAP)), mirror, matrix)
    if sink:
        matrix = composed(translation((0.0, 0.0, -sink)), matrix)
    if direction is not None:
        from app.core.geom.align import rotation_between

        if not _placement_value(params, "at_feature", "") and _free_direction(params) is not None:
            from app.core.sketch.planes import frame_of

            frame = frame_of(direction, (0.0, 0.0, 0.0))
            basis = np.eye(4, dtype=np.float64)
            basis[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
            # Im Flächenrahmen zeigt +Y nach oben; die Bausteine hängen an -Y.
            local_angle = angle + (180.0 if keeps_up else 0.0)
            matrix = composed(basis, rotation("z", local_angle), matrix)
        else:
            if angle:
                matrix = composed(rotation("z", angle), matrix)
            matrix = composed(rotation_between((0.0, 0.0, 1.0), direction), matrix)
            if keeps_up:
                matrix = composed(_roll_upright(direction), matrix)
    else:
        if axis != "z":
            # Den Baustein so umlegen, dass sein eigenes +Z entlang der
            # gewählten Achse zeigt.
            matrix = composed(rotation("y", 90.0) if axis == "x" else rotation("x", -90.0), matrix)
        if angle:
            matrix = composed(rotation(axis, angle), matrix)
    matrix = composed(
        translation(
            (
                float(_placement_value(params, "x", 0.0)) + anchor[0],
                float(_placement_value(params, "y", 0.0)) + anchor[1],
                float(_placement_value(params, "z", 0.0)) + anchor[2],
            )
        ),
        matrix,
    )
    return as_transform(matrix)
