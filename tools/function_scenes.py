"""Der Szenenkatalog des Funktionsdurchgangs (Bauplan D0 §2.5, RM-737).

Jede Zeile der Funktionsliste beginnt in einer Szene aus
``tests/data/function_scenes.toml``: einem Rezept aus registrierten Operationen, an
beiden Kernen, mit Zusagen — Objekte, Merkmalsarten, Körperzustand, Befunde und
ihre Handlungen. Hier wird der Katalog gelesen und geprüft, jede Szene über
``History.apply`` gebaut, gerechnet, gegen ihre Zusagen gehalten und als
Projektdatei außerhalb des Baums gespeichert.

Was eine Szene über das Rezept hinaus braucht, steht in ihr und wirkt beim Prüfen
wie im Fenster (:func:`check_scene`): eine Projektdatei aus dem Korpus als
Anfang, Drucker und Material samt mitgebrachtem Drucker, erzeugte Quellen,
ausgeschaltete Schritte, geschützte Flächen, eigene Bausteine im Nutzerordner,
äußere Vorbedingungen, die Einfügemarke der Sitzung und ein Auslöser (Export,
*Automatisch teilen*), den der Prüfstand vor der Zeile fährt
(``function_setup.scene_setup``).

Die unterste Schicht der Funktionsliste: :class:`FunctionListError` und das geladene
Register stehen hier, damit ``function_list`` darauf aufbaut und kein Kreis entsteht.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from app.core.registry import Registry
    from app.core.scene.evaluate import EvaluationResult
    from app.core.scene.project import Project
    from app.core.types import Finding

ROOT: Final = Path(__file__).resolve().parent.parent
DATA: Final = ROOT / "tests" / "data"
SCENES: Final = DATA / "function_scenes.toml"


EXACT: Final = "exakt"
MESH: Final = "netz"
KERNELS: Final[tuple[str, ...]] = (EXACT, MESH)


#: Was eine Szene zusagen darf (``promises``).
PROMISE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "objects",
        "kinds",
        "body",
        "findings",
        "actions",
        "stops",
        "triangles_over",
        "seconds_over",
    }
)
BODY_STATES: Final[tuple[str, ...]] = ("closed", "open", "parts", "cavity")

#: Was der Prüfstand vor der Zeile auslöst und :func:`check_scene` im Kern
#: nachrechnet: ``export`` mit ``format``, ``auto_split`` mit ``object``.
CAUSE_KEYS: Final[dict[str, frozenset[str]]] = {
    "export": frozenset({"kind", "format"}),
    "auto_split": frozenset({"kind", "object"}),
}

#: Die Vorbedingung, die im Kern dieses Prozesses herstellbar ist: OpenCASCADE
#: fehlt (``brep.kernel.available``). Die übrigen (KI, ComfyUI, Slicer)
#: stellt der Prüfstand her; den Befund einer Szene ändern sie nicht.
MISSING_KERNEL: Final = ("opencascade", "fehlt")


class FunctionListError(Exception):
    """Die Liste lässt sich nicht vollständig zuordnen — mit allen Fundstellen."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = tuple(problems)


def registry() -> Registry:
    """Das geladene Register der Anwendung."""
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY

    load_operations()
    return REGISTRY


# --- Szenenkatalog ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SceneStep:
    """Ein Schritt eines Szenenrezepts: eine Operation mit Eingängen und Werten."""

    op: str
    inputs: tuple[str, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    title: str = ""
    suppressed: bool = False
    """Ausgeschaltet, so wie die Projektdatei es speichert (``Suppression``) — ohne
    die Schritte mitzunehmen, die auf ihm aufbauen."""


@dataclass(frozen=True, slots=True)
class Scene:
    """Ein Rezept aus ``tests/data/function_scenes.toml`` (Bauplan D0 §2.5)."""

    key: str
    summary: str
    ops: tuple[SceneStep, ...] = ()
    base: str = ""
    sources: Mapping[str, str] = field(default_factory=dict)
    """Quellkennung → Pfad relativ zu ``tests/data``."""
    kernel: str = ""
    heavy: bool = False
    project: bool = True
    """``False`` heißt: kein Projekt, der Startbildschirm."""
    promises: Mapping[str, Any] = field(default_factory=dict)
    select: str = ""
    """Das Merkmal, das eine Zeile mit Merkmalsanforderung wählt: ``obj_<n>.<merkmal>``."""
    parameters: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    """Projektparameter vor dem ersten Schritt: Name → ``{value, unit, title}``."""
    opens: str = ""
    """Eine Projektdatei aus ``tests/data`` als Anfang, geöffnet wie im Fenster."""
    printer: str = ""
    material: str = ""
    printer_like: str = ""
    """Der Drucker ``printer`` ist hier nicht eingerichtet; das Projekt bringt seine
    Beschreibung mit, gleich der des mitgelieferten Druckers dieser Kennung."""
    generated: tuple[str, ...] = ()
    """Quellen, die ein Generator geliefert hat (Weg 3, ``Source.kind`` ``generated``)."""
    protected: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    """Merkmale, die vor Trennnähten geschützt sind (``Document.protected``)."""
    own_parts: tuple[str, ...] = ()
    """Rezepte aus ``tests/data``, die im Nutzerordner liegen, bevor das Projekt öffnet."""
    preconditions: Mapping[str, str] = field(default_factory=dict)
    """Äußere Vorbedingungen der Szene (``function_list.PRECONDITIONS``)."""
    insert_before: int = 0
    """Die Einfügemarke der Sitzung vor diesem Schritt (sichtbare Nummer), sonst 0."""
    cause: Mapping[str, str] = field(default_factory=dict)
    """Was vor der Zeile ausgelöst wird (:data:`CAUSE_KEYS`)."""
    built: Mapping[str, str] = field(default_factory=dict)
    """Quellkennung → Generator aus :data:`GENERATORS`: Die Datei entsteht
    beim Bau der Szene, zu groß für ``tests/data``."""
    recognition: str = ""
    """``declined``: Die Frage nach der vollständigen Merkmalserkennung (§21.1) ist im
    Ladeschritt abgelehnt gespeichert, wie nach einem Import, der sofort lud."""
    spools: tuple[Mapping[str, str], ...] = ()
    """Spulen, die vor dem Start im Filamentlager des Falls liegen (:data:`SPOOL_KEYS`)."""


#: Die Antworten einer Szene auf die Frage vor der langen Vollerkennung.
RECOGNITION_ANSWERS: Final[tuple[str, ...]] = ("", "declined")

#: Was eine Spule im Lager einer Szene trägt: Name und Farbe, dazu die Materialart.
SPOOL_KEYS: Final[frozenset[str]] = frozenset({"name", "colour", "material_type"})


SCENE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "summary",
        "ops",
        "base",
        "sources",
        "kernel",
        "heavy",
        "project",
        "promises",
        "select",
        "parameters",
        "opens",
        "printer",
        "material",
        "printer_like",
        "generated",
        "protected",
        "own_parts",
        "preconditions",
        "insert_before",
        "cause",
        "built",
        "recognition",
        "spools",
    }
)
PARAMETER_KEYS: Final[frozenset[str]] = frozenset({"value", "unit", "title"})
STEP_KEYS: Final[frozenset[str]] = frozenset({"op", "inputs", "params", "title", "suppressed"})


def load_scenes(path: Path = SCENES) -> dict[str, Scene]:
    """Der Szenenkatalog in seiner Reihenfolge. Unbekannte Schlüssel halten an."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    scenes: dict[str, Scene] = {}
    for key, entry in data.get("scene", {}).items():
        unknown = set(entry) - SCENE_KEYS
        if unknown:
            problems.append(f"Szene {key}: unbekannte Schlüssel {sorted(unknown)}")
        steps: list[SceneStep] = []
        for step in entry.get("ops", []):
            extra = set(step) - STEP_KEYS
            if extra or "op" not in step:
                problems.append(f"Szene {key}: Schritt {step} mit {sorted(extra) or 'ohne op'}")
                continue
            steps.append(
                SceneStep(
                    op=step["op"],
                    inputs=tuple(step.get("inputs", ())),
                    params=dict(step.get("params", {})),
                    title=step.get("title", ""),
                    suppressed=bool(step.get("suppressed", False)),
                )
            )
        scenes[key] = Scene(
            key=key,
            summary=entry.get("summary", ""),
            ops=tuple(steps),
            base=entry.get("base", ""),
            sources=dict(entry.get("sources", {})),
            kernel=entry.get("kernel", ""),
            heavy=bool(entry.get("heavy", False)),
            project=bool(entry.get("project", True)),
            promises=dict(entry.get("promises", {})),
            select=entry.get("select", ""),
            parameters={name: dict(values) for name, values in entry.get("parameters", {}).items()},
            opens=entry.get("opens", ""),
            printer=entry.get("printer", ""),
            material=entry.get("material", ""),
            printer_like=entry.get("printer_like", ""),
            generated=tuple(entry.get("generated", ())),
            protected={
                name: tuple(features) for name, features in entry.get("protected", {}).items()
            },
            own_parts=tuple(entry.get("own_parts", ())),
            preconditions=dict(entry.get("preconditions", {})),
            insert_before=int(entry.get("insert_before", 0)),
            cause=dict(entry.get("cause", {})),
            built=dict(entry.get("built", {})),
            recognition=str(entry.get("recognition", "")),
            spools=tuple(dict(spool) for spool in entry.get("spools", ())),
        )
    if problems:
        raise FunctionListError(problems)
    return scenes


def recipe(key: str, scenes: Mapping[str, Scene]) -> tuple[dict[str, str], list[SceneStep]]:
    """Quellen und Schritte einer Szene samt ihrer Basis, die Basis zuerst."""
    chain: list[Scene] = []
    current: str = key
    while current:
        if current not in scenes:
            raise FunctionListError([f"Szene {key}: Basis {current!r} gibt es nicht"])
        if any(entry.key == current for entry in chain):
            raise FunctionListError([f"Szene {key}: Basis im Kreis über {current!r}"])
        chain.append(scenes[current])
        current = scenes[current].base
    sources: dict[str, str] = {}
    steps: list[SceneStep] = []
    for scene in reversed(chain):
        sources.update(scene.sources)
        steps.extend(scene.ops)
    return sources, steps


def row_scenes(row: Mapping[str, Any]) -> tuple[str, ...]:
    """Die Startszenen eines Falls: die der Zeile, dann die eigene des Fehlfalls.

    Der Fehlfall läuft im selben Prozess und Profil wie der Rest des Falls; was
    seine Szene verlangt — Vorbedingungen, eigene Bausteine im Nutzerordner —,
    muss deshalb vor dem Start des Falls stehen (Durchsicht welle4 C-L4).
    Widersprechen sich die Vorbedingungen beider, hält ``function_list.validate_specs``
    die Spezifikation an.
    """
    spec = row.get("spec") or {}
    main = str(spec.get("start_scene") or row.get("start_scene") or "")
    fault = str((spec.get("fault_case") or {}).get("start_scene") or "")
    return tuple(key for key in dict.fromkeys((main, fault)) if key)


def parameters_of(key: str, scenes: Mapping[str, Scene]) -> dict[str, Mapping[str, Any]]:
    """Die Projektparameter einer Szene samt ihrer Basis."""
    chain: list[Scene] = []
    current = key
    while current and current in scenes and scenes[current] not in chain:
        chain.append(scenes[current])
        current = scenes[current].base
    found: dict[str, Mapping[str, Any]] = {}
    for scene in reversed(chain):
        found.update(scene.parameters)
    return found


def validate_scenes(scenes: Mapping[str, Scene]) -> list[str]:
    """Was an den Rezepten nicht stimmt, ohne zu rechnen: Basis, Operationen,
    Quellen, Kern, Zusagen."""
    from app.core import expressions
    from app.core.errors import AppError
    from app.core.registry import FEATURE_KINDS, validate

    source = registry()
    issues: list[str] = []
    for key, scene in scenes.items():
        if not scene.summary:
            issues.append(f"Szene {key}: ohne summary")
        if scene.kernel not in ("", *KERNELS):
            issues.append(f"Szene {key}: Kern {scene.kernel!r} unbekannt")
        for suffix in KERNELS:
            if key.endswith(f".{suffix}") and scene.kernel != suffix:
                issues.append(f"Szene {key}: der Name sagt {suffix}, kernel sagt {scene.kernel!r}")
        try:
            sources, steps = recipe(key, scenes)
        except FunctionListError as error:
            issues.extend(error.problems)
            continue
        for name, relative in sources.items():
            if not (DATA / relative).is_file():
                issues.append(f"Szene {key}: Quelle {name} → {relative} fehlt in tests/data")
        issues += [f"Szene {key}: {issue}" for issue in _built_problems(scene, sources, steps)]
        parameters = parameters_of(key, scenes)
        for name, values in parameters.items():
            if set(values) - PARAMETER_KEYS or not isinstance(values.get("value"), int | float):
                issues.append(f"Szene {key}: Parameter {name} braucht value, unit, title")
        numbers = {name: float(values.get("value", 0.0)) for name, values in parameters.items()}
        for step in steps:
            if not source.has(step.op):
                issues.append(f"Szene {key}: Operation {step.op!r} gibt es nicht")
                continue
            # Grenzen und Arten wie beim Rechnen: ``History.apply`` prüft nur
            # Kennungen und Namen, ein Wert außerhalb des Bereichs käme durch.
            try:
                resolved = expressions.resolve_params(dict(step.params), numbers)
                validate(source.get(step.op).params, resolved)
            except AppError as error:
                issues.append(f"Szene {key}: {step.op} — {error.detail or error.title}")
        if not scene.project and steps:
            issues.append(f"Szene {key}: ohne Projekt, aber mit Schritten")
        unknown = set(scene.promises) - PROMISE_KEYS
        if unknown:
            issues.append(f"Szene {key}: unbekannte Zusagen {sorted(unknown)}")
        for kind in scene.promises.get("kinds", ()):
            if kind not in FEATURE_KINDS:
                issues.append(f"Szene {key}: Merkmalsart {kind!r} gibt es nicht")
        body = scene.promises.get("body")
        if body is not None and body not in BODY_STATES:
            issues.append(f"Szene {key}: Körperzustand {body!r} unbekannt")
        if scene.heavy and not ({"triangles_over", "seconds_over"} & set(scene.promises)):
            issues.append(f"Szene {key}: schwer, aber ohne Zusage zu Dreiecken oder Sekunden")
        for action, code in scene.promises.get("actions", {}).items():
            if code not in scene.promises.get("findings", ()):
                issues.append(f"Szene {key}: Handlung {action} an {code}, der nicht zugesagt ist")
        issues += [f"Szene {key}: {issue}" for issue in _setting_problems(scene, sources, steps)]
    return issues


def _built_problems(
    scene: Scene, sources: Mapping[str, str], steps: Sequence[SceneStep]
) -> list[str]:
    """Erzeugte Quellen und die gespeicherte Erkennungsantwort (``built``, ``recognition``)."""
    issues = [
        f"Quelle {name}: Generator {generator!r} gibt es nicht"
        for name, generator in scene.built.items()
        if generator not in GENERATORS
    ]
    issues += [
        f"Quelle {name} steht in sources und built" for name in set(scene.built) & set(sources)
    ]
    if scene.recognition not in RECOGNITION_ANSWERS:
        issues.append(f"Erkennungsantwort {scene.recognition!r} unbekannt")
    elif scene.recognition and not any(step.op == "load" for step in steps):
        issues.append("Erkennungsantwort ohne Ladeschritt, an dem sie stehen könnte")
    issues += [
        f"Spule {dict(spool)}: braucht name und colour, kennt nur {sorted(SPOOL_KEYS)}"
        for spool in scene.spools
        if set(spool) - SPOOL_KEYS or not {"name", "colour"} <= set(spool)
    ]
    return issues


def _setting_problems(
    scene: Scene, sources: Mapping[str, str], steps: Sequence[SceneStep]
) -> list[str]:
    """Was an den Angaben über das Rezept hinaus nicht stimmt (Anfang, Drucker, Auslöser …)."""
    from app.core.export.writer import FORMAT_SUFFIX
    from app.core.knowledge import profiles

    issues: list[str] = []
    files = ([scene.opens] if scene.opens else []) + list(scene.own_parts)
    issues += [
        f"{relative} fehlt in tests/data" for relative in files if not (DATA / relative).is_file()
    ]
    if scene.opens and scene.base:
        issues.append("beginnt mit einer Datei und hat zugleich eine Basis")
    known = profiles.printer_profiles()
    if scene.printer_like and (not scene.printer or scene.printer in known):
        issues.append(
            f"printer_like braucht einen Drucker, den es hier nicht gibt, nicht {scene.printer!r}"
        )
    if scene.printer_like and scene.printer_like not in known:
        issues.append(f"printer_like {scene.printer_like!r} ist kein mitgelieferter Drucker")
    if scene.printer and not scene.printer_like and scene.printer not in known:
        issues.append(f"Drucker {scene.printer!r} gibt es nicht")
    if scene.material and scene.material not in profiles.material_profiles():
        issues.append(f"Material {scene.material!r} gibt es nicht")
    issues += [
        f"erzeugte Quelle {name} fehlt in sources"
        for name in scene.generated
        if name not in sources
    ]
    if scene.insert_before and not (scene.opens or 1 <= scene.insert_before <= len(steps)):
        issues.append(f"Einfügemarke vor Schritt {scene.insert_before}, es gibt {len(steps)}")
    if scene.cause:
        kind = scene.cause.get("kind", "")
        wanted = CAUSE_KEYS.get(kind)
        if wanted is None:
            issues.append(f"Auslöser {kind!r} unbekannt")
        elif set(scene.cause) != wanted:
            issues.append(f"Auslöser {kind} braucht {sorted(wanted)}")
        elif kind == "export" and scene.cause["format"] not in FORMAT_SUFFIX:
            issues.append(f"Exportformat {scene.cause['format']!r} gibt es nicht")
    return issues


def needs_exact_kernel(key: str, scenes: Mapping[str, Scene]) -> bool:
    """Ob ein Schritt der Szene eine Operation des zweiten Kerns ist (``app.core.brep``) —
    dann braucht auch eine Netzszene OpenCASCADE (``merkmal.thread.netz``)."""
    source = registry()
    _sources, steps = recipe(key, scenes)
    return any(
        getattr(source.get(step.op).fn, "__module__", "").startswith("app.core.brep")
        for step in steps
    )


def build_scene(key: str, scenes: Mapping[str, Scene] | None = None) -> Project:
    """Das Projekt einer Szene, aus ihrem Rezept über die Operationen gebaut.

    Jeder Schritt ist eine Transaktion über ``History.apply`` — derselbe Weg wie
    ``tools/make_examples.py``; ``apply`` prüft Kennungen und Parameternamen,
    Wertebereiche prüft :func:`validate_scenes`. Gerechnet wird hier nur für eine
    gespeicherte Erkennungsantwort (``recognition``): Ihr Netzabdruck entsteht
    erst beim Laden.
    """
    from app.core.scene import History, OperationDraft
    from app.core.scene.project import load, new_project
    from app.core.types import Parameter, Source, Suppression

    catalogue = scenes if scenes is not None else load_scenes()
    scene = catalogue[key]
    if not scene.project:
        raise FunctionListError([f"Szene {key}: der Startbildschirm hat kein Projekt"])
    source = registry()
    sources, steps = recipe(key, catalogue)
    project = load(DATA / scene.opens) if scene.opens else new_project()
    document = project.document
    document.printer = scene.printer or document.printer
    document.material = scene.material or document.material
    if scene.printer_like:
        document.carried_profiles = {
            **document.carried_profiles,
            "printers": {scene.printer: _carried_printer(scene.printer_like)},
        }
    for name, relative in sources.items():
        project.document.sources[name] = Source(
            id=name,
            kind="generated" if name in scene.generated else "import",
            path=f"sources/{Path(relative).name}",
            sha256="",
        )
        project.sources[name] = (DATA / relative).read_bytes()
    for name, generator in scene.built.items():
        payload, suffix = GENERATORS[generator]()
        project.document.sources[name] = Source(
            id=name, kind="import", path=f"sources/{generator}{suffix}", sha256=""
        )
        project.sources[name] = payload
    for name, values in parameters_of(key, catalogue).items():
        project.document.parameters[name] = Parameter(
            name=name,
            value=float(values["value"]),
            unit=str(values.get("unit", "mm")),
            title=values.get("title"),
        )
    history = History(project.document)
    resting: set[int] = set()
    for step in steps:
        title = step.title or source.get(step.op).title
        history.apply(
            title, [OperationDraft(op=step.op, inputs=step.inputs, params=dict(step.params))]
        )
        if step.suppressed:
            resting.add(document.ops[-1].id)
    # Erst nach dem letzten Schritt, so wie die Datei es speichert, und ohne die
    # Schritte, die auf ihm aufbauen — der Zustand einer von Hand bearbeiteten
    # Datei. Vorher nähme ``apply`` den nächsten Schritt nicht an.
    document.ops = [
        replace(entry, suppressed=Suppression()) if entry.id in resting else entry
        for entry in document.ops
    ]
    document.protected = {name: tuple(found) for name, found in scene.protected.items()}
    if scene.recognition:
        _store_recognition_answers(project, allowed=False)
    return project


def _store_recognition_answers(project: Project, *, allowed: bool) -> None:
    """Die Antwort auf die Frage vor der langen Vollerkennung, in ihren Ladeschritten.

    So wie die Anwendung sie festhält, wenn der Kunde beim Import wählt
    (``evaluate.on_recognition_answer`` → ``Operation.matches``): mit dem
    Netzabdruck, den erst das Laden ergibt. Ohne sie fragte das Fenster beim
    Öffnen der Szene, und *Alle Merkmale erkennen* fände keine Wahl, die sich
    nachholen ließe (``history.recognition_reopenable``).
    """
    from app.core.knowledge import profiles
    from app.core.scene import evaluate
    from app.core.scene.project import ProjectSources

    document = project.document
    answers: list[tuple[int, str, Mapping[str, Any]]] = []

    def answer(question: str, choices: Sequence[str]) -> str:
        return choices[1] if allowed else choices[0]

    evaluate(
        document,
        profiles.scene_profile(document.printer, document.material),
        sources=ProjectSources(project),
        ask=answer,
        on_recognition_answer=lambda op_id, key, record: answers.append((op_id, key, record)),
    )
    stored: dict[int, dict[str, Any]] = {}
    for op_id, key, record in answers:
        stored.setdefault(op_id, {})[key] = dict(record)
    document.ops = [
        replace(entry, matches={**entry.matches, **stored[entry.id]})
        if entry.id in stored
        else entry
        for entry in document.ops
    ]


# --- Quellen, die beim Bau entstehen (``built``, FD-101) ---------------------------
#
# Ein Netz über der automatischen Erkennungsgrenze (anderthalb Millionen Dreiecke,
# ``perceive.local.FEATURE_LIMIT_TRIANGLES``) wäre als Datei zig Megabyte groß und
# gehört nicht in tests/data. Erzeugt wird es aus einer festen Vorschrift ohne
# Zufall — gleiche Eingabe, gleiche Bytes. Hier und nicht in einem eigenen Modul:
# Die Funktionsliste importiert nur ``function_scan`` und ``function_scenes``
# (``test_function_report``), damit kein Kreis zu den Urteilsmodulen entsteht.

#: Kanten der Oberseite und der Unterseite der dichten Platte. 4 · n² + 8 · n
#: Dreiecke: bei 620 sind es 1 542 560 — über der automatischen Grenze von
#: 1 500 000 und unter der bestätigbaren von 5 000 000 (§21.1).
DENSE_PLATE_CELLS: Final = 620


def dense_plate() -> tuple[bytes, str]:
    """Eine geschlossene Platte 200 x 200 x 10 mm, Ober- und Unterseite fein gerastert.

    Gibt die Datei als binäres PLY und ihre Endung zurück. Die Seiten verbinden
    die Randpunkte beider Raster; alle Dreiecke zeigen nach außen.
    """
    import io

    import numpy as np
    import trimesh

    cells = DENSE_PLATE_CELLS
    side = cells + 1
    axis = np.linspace(-100.0, 100.0, side)
    xs, ys = np.meshgrid(axis, axis, indexing="xy")
    flat = np.column_stack([xs.ravel(), ys.ravel()])
    top = np.column_stack([flat, np.full(len(flat), 10.0)])
    bottom = np.column_stack([flat, np.zeros(len(flat))])
    vertices = np.vstack([top, bottom])
    offset = side * side

    rows, columns = np.meshgrid(np.arange(cells), np.arange(cells), indexing="ij")
    a = (rows * side + columns).ravel()
    b = a + 1
    c = a + side
    d = c + 1
    top_faces = np.vstack([np.column_stack([a, b, d]), np.column_stack([a, d, c])])
    bottom_faces = np.vstack([np.column_stack([a, d, b]), np.column_stack([a, c, d])]) + offset

    # Der Rand im Umlauf gegen den Uhrzeigersinn, von oben gesehen.
    steps = np.arange(cells)
    ring = np.concatenate(
        [
            steps,  # unten: y = -100, x wächst
            cells + steps * side,  # rechts: x = +100, y wächst
            side * side - 1 - steps,  # oben: y = +100, x fällt
            (cells - steps) * side,  # links: x = -100, y fällt
        ]
    )
    following = np.roll(ring, -1)
    upper, upper_next = ring, following
    lower, lower_next = ring + offset, following + offset
    side_faces = np.vstack(
        [
            np.column_stack([lower, lower_next, upper_next]),
            np.column_stack([lower, upper_next, upper]),
        ]
    )
    faces = np.vstack([top_faces, bottom_faces, side_faces]).astype(np.int64)
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    payload = io.BytesIO()
    body.export(payload, file_type="ply", encoding="binary")
    return payload.getvalue(), ".ply"


#: Name → Generator; :func:`build_scene` ruft ihn beim Bau der Szene.
GENERATORS: Final[dict[str, Callable[[], tuple[bytes, str]]]] = {
    "dichte_platte": dense_plate,
}


def _carried_printer(like: str) -> dict[str, Any]:
    """Die Beschreibung eines Druckers, die ein Projekt mitbringt — gleich der eines
    mitgelieferten, unter eigenem Titel (``profiles.carry``)."""
    from app.core.knowledge import profiles

    return {**profiles.printer_definition(profiles.printer(like)), "title": "Werkstattdrucker"}


def evaluate_scene(project: Project) -> EvaluationResult:
    """Das Ergebnis einer gebauten Szene mit dem Profil, das die Anwendung einem
    Projekt ohne Druckerwahl gibt (``profiles.scene_profile``)."""
    from app.core.knowledge import profiles
    from app.core.scene import evaluate
    from app.core.scene.project import ProjectSources

    document = project.document
    profile = profiles.scene_profile(document.printer, document.material)
    return evaluate(document, profile, sources=ProjectSources(project))


@contextmanager
def scene_environment(scene: Scene) -> Iterator[None]:
    """Was um eine Szene herum gilt, solange sie gebaut und gerechnet wird.

    Eigene Bausteine stehen im Katalog, wie aus dem Nutzerordner geladen; fehlt
    OpenCASCADE (:data:`MISSING_KERNEL`), antwortet ``brep.kernel.available`` mit
    nein. Danach ist alles wie vorher: die Bausteine und Operationen, die dazukamen
    — auch die mitgereisten eines geöffneten Projekts —, sind wieder weg, die
    mitgebrachten Drucker ebenso.
    """
    import json

    from app.core.brep import kernel
    from app.core.knowledge import profiles
    from app.core.knowledge.parts import recipe as part_recipes
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    registry()  # erst laden: Was danach dazukommt, gehört der Szene
    parts_before = {spec.name for spec in PARTS.all()}
    ops_before = {spec.name for spec in REGISTRY.all()}
    probe = kernel.available
    try:
        name, missing = MISSING_KERNEL
        if scene.preconditions.get(name) == missing:
            # Dieselbe Nahtstelle wie die Suite (``tests/test_threads.py``) und der
            # Prüfstand (``function_setup.apply_preconditions``).
            kernel.available = lambda: False
        for relative in scene.own_parts:
            stored = json.loads((DATA / relative).read_text(encoding="utf-8"))
            part_recipes.register(part_recipes.from_data(stored))
        yield
    finally:
        kernel.available = probe
        for name in {spec.name for spec in REGISTRY.all()} - ops_before:
            REGISTRY.remove(name)
        for name in {spec.name for spec in PARTS.all()} - parts_before:
            PARTS.remove(name)
        profiles.carry(None)


def check_scene(key: str, scenes: Mapping[str, Scene] | None = None) -> list[str]:
    """Baut und rechnet eine Szene wie das Fenster und nennt, was sie nicht hält.

    Wie beim Öffnen gelten die mitgebrachten Drucker (``profiles.carry``); die
    Befunde des Fensters über die Auswertung hinaus prüft :func:`broken_promises`
    mit dem Projekt.
    """
    from app.core.knowledge import profiles

    catalogue = scenes if scenes is not None else load_scenes()
    scene = catalogue[key]
    with scene_environment(scene):
        project = build_scene(key, catalogue)
        profiles.carry(project.document.carried_profiles)
        result = evaluate_scene(project)
        return broken_promises(scene, result, project)


def window_findings(scene: Scene, project: Project, result: EvaluationResult) -> list[Finding]:
    """Was das Fenster neben der Auswertung in den Bericht stellt, für diese Szene.

    Den mitgebrachten oder fehlenden Drucker (``profiles.carried_findings``), beim
    Öffnen einer Datei die Prüfung ihrer Bausteine und ihrer Herkunft, den Satz
    zur Einfügemarke (``session.inserting_finding``) und die Befunde des Auslösers:
    die Prüfung vor dem Export (``writer.check_before_export``) oder die Suche von
    *Automatisch teilen* (``split.plan_split``) samt geschützten Flächen.
    """
    from app.core.export.writer import check_before_export
    from app.core.geom.mesh import as_mesh_data
    from app.core.knowledge import profiles
    from app.core.knowledge.parts import check as part_check
    from app.core.scene.foreign import findings_for
    from app.core.split import plan_split, protected_patches
    from app.ui.session import inserting_finding

    document = project.document
    found = list(profiles.carried_findings(document.printer, document.material))
    if scene.opens:
        found += [*findings_for(document), *part_check.check(document)]
    if scene.insert_before:
        found.append(inserting_finding(document, document.ops[scene.insert_before - 1].id))
    profile = result.scene.profile or profiles.scene_profile(document.printer, document.material)
    kind = scene.cause.get("kind")
    if kind == "export":
        found += check_before_export(
            list(result.scene.objects.values()),
            profile,
            dict(document.sources),
            scene.cause["format"],  # type: ignore[arg-type]
            scene=result.scene,
            document=document,
            evaluated=result.scene.report.findings,
        )
    elif kind == "auto_split":
        entry = result.scene.objects[scene.cause["object"]]
        plan = plan_split(
            as_mesh_data(entry.mesh),
            entry.id,
            profiles.for_object(profile, entry),
            features=entry.features,
            protect=protected_patches(entry, document.protected.get(entry.id, ())),
        )
        found += plan.outcome.findings
    return found


def broken_promises(
    scene: Scene, result: EvaluationResult, project: Project | None = None
) -> list[str]:
    """Was die gerechnete Szene von ihren Zusagen nicht hält — leer, wenn alles stimmt.

    ``seconds_over`` prüft hier niemand: Eine Dauer hängt an der Maschine; der
    Prüfstand misst sie auf die Referenzmaschine umgerechnet und wertet eine zu
    schnelle Szene als „nicht prüfbar“ (Bauplan D0 §4.2, Prüfpunkt 14).
    """
    from app.core.geom.mesh import as_mesh_data
    from app.ui.panels import actions_for

    objects = list(result.scene.objects.values())
    promises = scene.promises
    issues: list[str] = []
    stops = bool(promises.get("stops", False))
    if stops != (result.stopped_at is not None):
        issues.append(f"hält an: {result.stopped_at!r}, zugesagt {stops}")
    if "objects" in promises and len(objects) != promises["objects"]:
        issues.append(f"{len(objects)} Körper, zugesagt {promises['objects']}")
    wanted_kind = {"exakt": "brep", "netz": "mesh"}.get(scene.kernel)
    if wanted_kind is not None:
        wrong = [entry.id for entry in objects if entry.kind != wanted_kind]
        if wrong:
            issues.append(f"Kern {scene.kernel}, aber {wrong} sind es nicht")
    shown = {feature.kind for entry in objects for feature in entry.features.values()}
    missing = sorted(set(promises.get("kinds", ())) - shown)
    if missing:
        issues.append(f"Merkmalsarten {missing} fehlen, erkannt {sorted(shown)}")
    body = promises.get("body")
    if body is not None:
        meshes = [as_mesh_data(entry.mesh).raw for entry in objects]
        states = {
            "closed": all(mesh.is_watertight for mesh in meshes),
            "open": any(not mesh.is_watertight for mesh in meshes),
            "parts": any(len(mesh.split(only_watertight=False)) > 1 for mesh in meshes),
            "cavity": "void" in shown,
        }
        if not states[body]:
            issues.append(f"Körperzustand {body} nicht erfüllt")
    findings = list(result.scene.report.findings)
    if project is not None:
        findings += window_findings(scene, project, result)
    codes = {finding.code for finding in findings}
    wanted_codes = set(promises.get("findings", ())) | set(promises.get("actions", {}).values())
    if wanted_codes - codes:
        # Die Befunde der Druckprüfung (Schichtanalyse, Druckrat) stellt das Fenster
        # nach der Auswertung in denselben Bericht — gerechnet wie dort.
        findings += _print_findings(result)
        codes = {finding.code for finding in findings}
    missing_findings = sorted(set(promises.get("findings", ())) - codes)
    if missing_findings:
        issues.append(f"Befunde {missing_findings} fehlen, gemeldet {sorted(codes)}")
    # Die Handlungen am echten Befund — samt denen, die er selbst mitbringt.
    for action, code in promises.get("actions", {}).items():
        offered = {
            entry.id
            for finding in findings
            if finding.code == code
            for entry in actions_for(finding)
        }
        if action not in offered:
            issues.append(f"Handlung {action} fehlt an {code}, angeboten {sorted(offered)}")
    if scene.select:
        object_id, _dot, feature_id = scene.select.partition(".")
        chosen = result.scene.objects.get(object_id)
        feature = chosen.features.get(feature_id) if chosen is not None else None
        wanted = scene.key.split(".")[1] if scene.key.startswith("merkmal.") else None
        if feature is None:
            issues.append(f"gewähltes Merkmal {scene.select} gibt es nicht")
        elif wanted is not None and feature.kind != wanted:
            issues.append(f"gewähltes Merkmal {scene.select} ist {feature.kind}, nicht {wanted}")
    for name in parameters_of(scene.key, {scene.key: scene}):
        if name not in result.scene.parameters:
            issues.append(f"Projektparameter {name} fehlt in der Szene")
    if "triangles_over" in promises:
        largest = max((len(as_mesh_data(entry.mesh).raw.faces) for entry in objects), default=0)
        if largest <= promises["triangles_over"]:
            issues.append(f"{largest} Dreiecke, zugesagt über {promises['triangles_over']}")
    return issues


def _print_findings(result: EvaluationResult) -> list[Finding]:
    """Die Befunde der Druckprüfung einer gerechneten Szene (``slice.findings``)."""
    from app.core.knowledge import print_settings, profiles
    from app.core.slice.findings import print_findings

    profile = result.scene.profile or profiles.scene_profile("", "")
    return print_findings(result.scene, profile, print_settings.resolve(profile))


def save_scenes(out: Path, *, heavy: bool = False) -> list[Path]:
    """Baut die Szenen und speichert sie als Projekt nach ``out`` — nie in den Baum."""
    from app.core.scene.project import save

    target = out.resolve()
    if target == ROOT or ROOT in target.parents:
        raise FunctionListError(
            [f"{out}: Erzeugtes wird nicht im Baum abgelegt (tests/data/CLAUDE.md)"]
        )
    target.mkdir(parents=True, exist_ok=True)
    catalogue = load_scenes()
    written: list[Path] = []
    for key, scene in catalogue.items():
        if not scene.project or (scene.heavy and not heavy):
            continue
        path = target / f"{key}.p3d"
        if _opened_as_is(scene):
            # Unverändert geöffnet heißt: dieselbe Datei. Neu gespeichert bekäme
            # sie den Abdruck ihrer Bausteine von heute (``parts.check.stamp``),
            # und der Befund, um den es geht, wäre weg.
            path.write_bytes((DATA / scene.opens).read_bytes())
        else:
            with scene_environment(scene):
                save(build_scene(key, catalogue), path)
        written.append(path)
    return written


def _opened_as_is(scene: Scene) -> bool:
    """Ob die Szene eine Korpusdatei ist, an der sie nichts ändert."""
    return bool(scene.opens) and not (
        scene.ops
        or scene.sources
        or scene.parameters
        or scene.printer
        or scene.material
        or scene.printer_like
        or scene.protected
    )
