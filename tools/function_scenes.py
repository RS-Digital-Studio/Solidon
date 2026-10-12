"""Der Szenenkatalog des Funktionsdurchgangs (Bauplan D0 §2.5, RM-737).

Jede Zeile der Funktionsliste beginnt in einer Szene aus
``tests/data/function_scenes.toml``: einem Rezept aus registrierten Operationen, an
beiden Kernen, mit Zusagen — Objekte, Merkmalsarten, Körperzustand, Befunde und
ihre Handlungen. Hier wird der Katalog gelesen und geprüft, jede Szene über
``History.apply`` gebaut, gerechnet, gegen ihre Zusagen gehalten und als
Projektdatei außerhalb des Baums gespeichert.

Die unterste Schicht der Funktionsliste: :class:`FunctionListError` und das geladene
Register stehen hier, damit ``function_list`` darauf aufbaut und kein Kreis entsteht.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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
    }
)
PARAMETER_KEYS: Final[frozenset[str]] = frozenset({"value", "unit", "title"})
STEP_KEYS: Final[frozenset[str]] = frozenset({"op", "inputs", "params", "title"})


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
    Wertebereiche prüft :func:`validate_scenes`. Gerechnet wird hier nicht.
    """
    from app.core.scene import History, OperationDraft
    from app.core.scene.project import new_project
    from app.core.types import Parameter, Source

    catalogue = scenes if scenes is not None else load_scenes()
    if not catalogue[key].project:
        raise FunctionListError([f"Szene {key}: der Startbildschirm hat kein Projekt"])
    source = registry()
    sources, steps = recipe(key, catalogue)
    project = new_project()
    for name, relative in sources.items():
        project.document.sources[name] = Source(
            id=name, kind="import", path=f"sources/{Path(relative).name}", sha256=""
        )
        project.sources[name] = (DATA / relative).read_bytes()
    for name, values in parameters_of(key, catalogue).items():
        project.document.parameters[name] = Parameter(
            name=name,
            value=float(values["value"]),
            unit=str(values.get("unit", "mm")),
            title=values.get("title"),
        )
    history = History(project.document)
    for step in steps:
        title = step.title or source.get(step.op).title
        history.apply(
            title, [OperationDraft(op=step.op, inputs=step.inputs, params=dict(step.params))]
        )
    return project


def evaluate_scene(project: Project) -> EvaluationResult:
    """Das Ergebnis einer gebauten Szene mit dem Profil, das die Anwendung einem
    Projekt ohne Druckerwahl gibt (``profiles.scene_profile``)."""
    from app.core.knowledge import profiles
    from app.core.scene import evaluate
    from app.core.scene.project import ProjectSources

    document = project.document
    profile = profiles.scene_profile(document.printer, document.material)
    return evaluate(document, profile, sources=ProjectSources(project))


def broken_promises(scene: Scene, result: EvaluationResult) -> list[str]:
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
        save(build_scene(key, catalogue), path)
        written.append(path)
    return written
