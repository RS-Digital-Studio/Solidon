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
from typing import Any

from app.core.errors import Action, AppError
from app.core.geom.boolean import BOOLEAN_OVERLAP, BooleanKind, boolean, without_effect
from app.core.geom.mesh import MeshData, as_mesh_data, concatenated
from app.core.geom.transform import rotation, translation
from app.core.knowledge.parts.registry import PARTS, PartRegistry, PartSpec
from app.core.log import get_logger
from app.core.registry import Registry, op_params, param, register_op
from app.core.types import (
    BaseParams,
    Feature,
    Finding,
    OpContext,
    OpResult,
    PartResult,
    Profile,
    SceneObject,
    Vec3,
)
from app.core.units import DEGREE_UNIT, EPS_GEOM
from app.i18n import TranslatableText, _

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
_PLACEMENT: tuple[tuple[str, str, Any], ...] = (
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
            doc=_(
                "Name eines erkannten Merkmals, zum Beispiel hole_1. Dann zählt "
                "dessen Ort, und die Position darüber wird als Versatz gerechnet."
            ),
        ),
    ),
)


#: Der Namensraum der Bausteinoperationen. Als Konstante, weil ihn zwei
#: Richtungen brauchen: :func:`op_name` setzt ihn, :func:`part_of` nimmt ihn ab.
_PREFIX = "insert_"


def op_name(part: str) -> str:
    """``screw_hole`` wird ``insert_screw_hole`` — ein Namensraum, keine
    Kollisionen.
    """
    return f"{_PREFIX}{part}"


def part_of(operation: str) -> PartSpec | None:
    """Der Baustein hinter einem Operationsnamen — die Umkehrung von
    :func:`op_name`.

    ``None`` für alles, was kein Baustein ist: Der Präfix allein ist kein
    Beweis, und eine Operation, die zufällig so heißt, darf hier nicht in einen
    Fehler laufen.
    """
    if not operation.startswith(_PREFIX):
        return None
    name = operation[len(_PREFIX) :]
    return PARTS.get(name) if PARTS.has(name) else None


def build_params(spec: PartSpec) -> type[BaseParams]:
    """Die Parameter des Bausteins plus den Ort, an den er gehört, als ein
    Schema (§10).
    """
    namespace: dict[str, Any] = {"__annotations__": {}}
    for entry in spec.params.fields():
        namespace["__annotations__"][entry.name] = entry.type
        namespace[entry.name] = (
            dataclasses.field(default=entry.default, metadata=entry.metadata)
            if entry.default is not dataclasses.MISSING
            else dataclasses.field(metadata=entry.metadata)
        )
    for name, annotation, declaration in _PLACEMENT:
        namespace["__annotations__"][name] = annotation
        namespace[name] = declaration

    made = type(f"{_camel(spec.name)}OpParams", (BaseParams,), namespace)
    return op_params(made)


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
        target = registry or None
        if (target or _default_registry()).has(name):
            continue
        _register_one(spec, build_params(spec), registry)
        made.append(name)
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
    Rezepte. ``register_all`` bleibt der der Bibliothek; beide enden hier."""
    _register_one(spec, build_params(spec), registry)


def _register_one(spec: PartSpec, params: type[BaseParams], registry: Registry | None) -> None:
    title = _title_for(spec)

    @register_op(
        name=op_name(spec.name),
        title=title,
        category="parts",
        params=params,
        consumes=1,
        produces=1,
        applies_to=_applies_to(spec),
        touches_features=True,
        doc=spec.doc or title,
        caveat=spec.caveat,
        registry=registry,
    )
    def run(ctx: OpContext, _spec: PartSpec = spec) -> OpResult:
        return insert(ctx, _spec)


def _title_for(spec: PartSpec) -> TranslatableText | str:
    return spec.title


def _hanging_loose(
    before: MeshData, after: MeshData, spec: PartSpec, subtractive: bool
) -> Finding | None:
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
    if subtractive or after.component_count <= before.component_count:
        return None
    loose = after.component_count - before.component_count
    return Finding(
        code="parts.hanging_loose",
        severity="error",
        # **Der Vorschlag steht im Satz.** Ein ``Finding`` trägt keine
        # ``Action``-Liste — das kann nur eine Ausnahme. Regel 17 verlangt
        # trotzdem einen Weg nach vorn, und ``without_effect`` macht es
        # nebenan genauso: erst was ist, dann was hilft.
        message=_loose_advice(spec),
        values={
            "part": spec.name,
            "loose": str(loose),
            "before": str(before.component_count),
            "after": str(after.component_count),
        },
    )


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
        if str(getattr(params, "axis", "z") or "z") == "z":
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
            "Dieser Baustein hält nur flach gedruckt: Seine dünne Stelle trägt, "
            "solange die Schichten quer zur Biegung laufen. Hochkant laufen sie "
            "längs, und er bricht beim ersten Öffnen. Setzen Sie ihn auf eine "
            "waagerechte Fläche — oder lassen Sie die Achse auf Z, wenn Sie die "
            "Stelle eintippen."
        ),
        values={"part": spec.name},
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
    if str(getattr(params, "axis", "z") or "z") != "z":
        return None
    return Finding(
        code="parts.up_points_nowhere",
        severity="warning",
        # Der Vorschlag steht im Satz, wie nebenan: erst was ist, dann was hilft.
        message=_(
            "Dieser Baustein hat ein Oben — eingehängt trägt er nur, wenn sein "
            "Zapfen nach oben zeigt. Waagerecht ausgerichtet zeigt er zur Seite, "
            "und seine Nase greift hinter nichts. Klicken Sie die Fläche an, an "
            "die er kommt: Sie gibt ihm die Richtung, und er richtet sich selbst "
            "auf. Soll er ohne Fläche stehen, setzen Sie die Achse auf Y."
        ),
        values={"part": spec.name},
    )


def insert(ctx: OpContext, spec: PartSpec) -> OpResult:
    """Baut den Baustein, setzt ihn an seinen Platz und verbindet oder schneidet."""
    source = ctx.inputs[0]
    values = _part_values(spec, ctx.params, ctx.profile)
    # Ein Rezept baut mit dem Profil des Dokuments (``build_with_profile``):
    # eine ``auto:``-Toleranz darin gehört mit dem Material des Kunden
    # aufgelöst. Für die ``.py``-Bausteine bleibt ``fn`` der ganze Vertrag.
    part_params = spec.params(**values)
    if spec.build_with_profile is not None:
        produced = spec.build_with_profile(part_params, ctx.profile, ctx.quality)
    else:
        produced = spec.fn(part_params)

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
            nothing = without_effect(body, prepared, "difference", ctx.profile)
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
        # Antwort steht im Volumen (§2.7).
        nothing = without_effect(body, mesh, kind, ctx.profile)

    features = dict(source.features)
    features.update(
        _placed_features(produced, spec, ctx.params, anchor, sink, direction, spec.keeps_up, flip)
    )
    features.update(host_features)

    # Und die Gegenprobe zu „hat nichts bewirkt": Er hat etwas hinzugefügt, nur
    # nicht **am** Teil.
    loose = (
        None
        if spec.separate_from_host
        else _hanging_loose(body, as_mesh_data(outcome.mesh), spec, subtractive)
    )

    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh, features=features)],
        solver=solver,
        findings=[
            *findings,
            *produced.findings,
            *([nothing] if nothing else []),
            *([loose] if loose else []),
            *([flat] if flat else []),
            *([on_edge] if on_edge else []),
        ],
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
    if GRIP_FIELD in values and not values[GRIP_FIELD] and profile is not None:
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
    for field in ("x", "y", "z"):
        value = getattr(params, field, 0.0)
        if isinstance(value, str):
            return True
        try:
            if float(value) != 0.0:
                return True
        except (TypeError, ValueError):
            return True
    return False


def _anchor(
    source: SceneObject,
    params: Any,
    spec: PartSpec | None = None,
    built: MeshData | None = None,
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
    name = str(getattr(params, "at_feature", "") or "")
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
        return (0.0, 0.0, 0.0), None

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
    direction = _direction_of(feature)
    return _at_the_mouth(point, direction, feature, built, spec), direction


def _at_the_mouth(
    point: Vec3,
    direction: Vec3 | None,
    feature: Feature,
    built: MeshData | None,
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


def _builds_upward_on_a_face(source: SceneObject, params: Any, built: MeshData) -> bool:
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
    name = str(getattr(params, "at_feature", "") or "")
    feature = source.features.get(name) if name else None
    if feature is None or feature.kind != "face":
        return False
    return float(built.bounds.maximum[2]) > BOOLEAN_OVERLAP + EPS_GEOM


def _direction_of(feature: Feature) -> Vec3 | None:
    """Wohin ein Merkmal schaut — oder ``None``, wenn es das nicht sagt.

    Dieselbe Frage beantwortet ``geom.align.frame_of`` fürs Ausrichten, und
    dort ist eine Art ohne Richtung ein Fehler mit Handlungsvorschlag. Hier
    ist sie keiner: Ein Baustein an einer Kantenschleife hat einen Ort und
    behält seine gewählte Achse. Die Antworten sind gleich, die Folgen nicht —
    deshalb steht die Frage zweimal da.
    """
    raw = feature.params.get("normal") or feature.params.get("axis")
    if raw is None:
        return None
    values = tuple(float(value) for value in raw)
    length = sum(value * value for value in values) ** 0.5
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
) -> dict[str, Feature]:
    """Die Merkmale des Bausteins, mitbewegt und so benannt, dass sie nicht
    kollidieren können.

    ``bore_1`` des dritten eingefügten Bausteins überschriebe sonst das des
    ersten. Bausteinname und Position machen es eindeutig, ohne einen Zähler zu
    erfinden, den niemand vorhersagen kann.
    """
    from app.core.perceive.matching import moved_features

    matrix = _matrix(params, anchor, sink, direction, keeps_up, flip)
    moved = moved_features(dict(produced.features), matrix)
    return {
        f"{spec.name}_{name}": dataclasses.replace(feature, id=f"{spec.name}_{name}")
        for name, feature in moved.items()
    }


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

    normal = np.asarray(direction, dtype=float)
    length = float(np.linalg.norm(normal))
    if length < 1e-9:
        return np.eye(4)
    normal = normal / length
    # Als Tripel aus echten ``float``: ``tuple(np.ndarray)`` gibt ``float64``,
    # und die Signaturen hier erwarten ``tuple[float, float, float]``.
    unit: Vec3 = (float(normal[0]), float(normal[1]), float(normal[2]))

    # Was von der Welt-Senkrechten in der Flächenebene übrig bleibt.
    up = np.array([0.0, 0.0, 1.0])
    up_in_face = up - float(np.dot(up, normal)) * normal
    if float(np.linalg.norm(up_in_face)) < 1e-6:
        return np.eye(4)
    up_in_face = up_in_face / float(np.linalg.norm(up_in_face))

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
    turned = rotation_between((0.0, 0.0, 1.0), unit)[:3, :3] @ np.array([0.0, -1.0, 0.0])
    own = turned - float(np.dot(turned, normal)) * normal
    if float(np.linalg.norm(own)) < 1e-6:
        return np.eye(4)
    own = own / float(np.linalg.norm(own))

    # Der Winkel von ``own`` nach ``up_in_face``, um die Normale gemessen —
    # ``atan2`` gibt ihn mit Vorzeichen, ein ``arccos`` allein nicht.
    degrees = math.degrees(
        math.atan2(
            float(np.dot(np.cross(own, up_in_face), normal)),
            float(np.dot(own, up_in_face)),
        )
    )
    if abs(degrees) < 1e-9:
        return np.eye(4)
    return _rotation_about(unit, degrees)


def _rotation_about(axis: Vec3, degrees: float) -> Any:
    """Eine Drehung um eine beliebige Achse durch den Ursprung (Rodrigues)."""
    import numpy as np

    unit = np.asarray(axis, dtype=float)
    unit = unit / float(np.linalg.norm(unit))
    angle = math.radians(degrees)
    cross = np.array(
        [
            [0.0, -unit[2], unit[1]],
            [unit[2], 0.0, -unit[0]],
            [-unit[1], unit[0], 0.0],
        ]
    )
    turn = np.eye(3) + math.sin(angle) * cross + (1.0 - math.cos(angle)) * (cross @ cross)
    matrix = np.eye(4)
    matrix[:3, :3] = turn
    return matrix


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

    axis = getattr(params, "axis", "z")
    angle = float(getattr(params, "angle", 0.0))
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
        matrix = translation((0.0, 0.0, BOOLEAN_OVERLAP)) @ mirror @ matrix
    if sink:
        matrix = translation((0.0, 0.0, -sink)) @ matrix
    if direction is not None:
        from app.core.geom.align import rotation_between

        if angle:
            matrix = rotation("z", angle) @ matrix
        matrix = rotation_between((0.0, 0.0, 1.0), direction) @ matrix
        if keeps_up:
            matrix = _roll_upright(direction) @ matrix
    else:
        if axis != "z":
            # Den Baustein so umlegen, dass sein eigenes +Z entlang der
            # gewählten Achse zeigt.
            matrix = (rotation("y", 90.0) if axis == "x" else rotation("x", -90.0)) @ matrix
        if angle:
            matrix = rotation(axis, angle) @ matrix  # type: ignore[arg-type]
    matrix = (
        translation(
            (
                float(getattr(params, "x", 0.0)) + anchor[0],
                float(getattr(params, "y", 0.0)) + anchor[1],
                float(getattr(params, "z", 0.0)) + anchor[2],
            )
        )
        @ matrix
    )
    return as_transform(matrix)
