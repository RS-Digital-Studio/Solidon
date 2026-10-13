"""Die Güte kürzt die Kette, nie der Aufrufer — und der Behälter rechnet weiter.

FD-6, M1 der Durchsicht welle4-b: Der Behälterbau legte seine Stufen je nach
Güte selbst fest, und seine Absage galt nicht als gekürzt. Der Wächter hält
jeden Aufruf der Netz-Booleschen im Kern, die Auswertungstests den Behälter
im Fensterlauf, in der Vorschau und über die dritte Stufe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.scene import History, OperationDraft, evaluate
from app.core.types import Profile
from tests.evaluation_helpers import short_chain_finds_nothing, window_evaluation

#: Wo die Boolesche des Netzkerns steht, und welche Stufenfolgen ein Aufruf
#: festlegen darf: ein Tupel aus Stufennamen oder eine der zwei Ketten.
_BOOLEAN_MODULE = "app.core.geom.boolean"
_NAMED_CHAINS = frozenset({"DRAFT_CHAIN", "FULL_CHAIN"})


def _boolean_calls(root: Path, path: Path) -> list[tuple[int, str]]:
    """Jeder Aufruf der Netz-Booleschen in ``path`` und sein ``stages=`` als Urteil.

    Aufgelöst über die Importe der Datei, auch relativ: der Name ``boolean`` und
    jeder Alias (``boolean as mesh_boolean``), ein Modulalias
    (``from app.core.geom import boolean as chain`` → ``chain.boolean(…)``) und
    in ``boolean.py`` selbst. Das Urteil ist ``""`` ohne ``stages``, sonst
    ``"erlaubt"`` oder die Schreibweise, die nicht erlaubt ist.
    """
    import ast

    from app.core.geom.boolean import FULL_CHAIN

    relative = path.relative_to(root)
    dotted = ".".join(relative.with_suffix("").parts)
    package = dotted if relative.name == "__init__.py" else dotted.rsplit(".", 1)[0]

    def source_of(node: ast.ImportFrom) -> str:
        if not node.level:
            return node.module or ""
        base = package.split(".")[: len(package.split(".")) - (node.level - 1)]
        return ".".join([*base, node.module] if node.module else base)

    def dotted_of(expression: ast.expr) -> str | None:
        if isinstance(expression, ast.Name):
            return expression.id
        if isinstance(expression, ast.Attribute):
            head = dotted_of(expression.value)
            return f"{head}.{expression.attr}" if head else None
        return None

    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = {"boolean"} if dotted == _BOOLEAN_MODULE else set()
    chains = set(_NAMED_CHAINS) if dotted == _BOOLEAN_MODULE else set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            source = source_of(node)
            for alias in node.names:
                bound = alias.asname or alias.name
                if source == _BOOLEAN_MODULE and alias.name == "boolean":
                    functions.add(bound)
                elif source == _BOOLEAN_MODULE and alias.name in _NAMED_CHAINS:
                    chains.add(bound)
                elif f"{source}.{alias.name}" == _BOOLEAN_MODULE:
                    modules.add(bound)
        elif isinstance(node, ast.Import):
            modules |= {
                alias.asname or alias.name for alias in node.names if alias.name == _BOOLEAN_MODULE
            }

    def verdict(value: ast.expr) -> str:
        if (
            isinstance(value, ast.Tuple)
            and value.elts
            and all(isinstance(e, ast.Constant) and e.value in FULL_CHAIN for e in value.elts)
        ):
            return "erlaubt"
        if isinstance(value, ast.Name) and value.id in chains:
            return "erlaubt"
        if (
            isinstance(value, ast.Attribute)
            and value.attr in _NAMED_CHAINS
            and dotted_of(value.value) in modules
        ):
            return "erlaubt"
        return ast.unparse(value)

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = node.func
        if not (
            (isinstance(called, ast.Name) and called.id in functions)
            or (
                isinstance(called, ast.Attribute)
                and called.attr == "boolean"
                and dotted_of(called.value) in modules
            )
        ):
            continue
        said = ""
        for keyword in node.keywords:
            if keyword.arg is None:
                said = f"**{ast.unparse(keyword.value)}"
            elif keyword.arg == "stages":
                allowed = verdict(keyword.value)
                said = allowed if allowed == "erlaubt" else f"stages={allowed}"
        found.append((node.lineno, said))
    return found


def test_the_quality_shortens_the_chain_never_the_caller() -> None:
    """FD-6: Kürzt die Güte, kürzt ``boolean`` (``cut_short``) — nie der Aufrufer je nach Güte.

    Der Behälterbau gab ``stages=DRAFT_CHAIN if … == "draft" else None`` mit.
    Seine Absage war damit keine gekürzte, die volle Kette lief im Fenster nie
    von selbst, und *Gröber rechnen* war dort der einzige Weg zu ihr.

    **Dicht, nicht nach dem Wort „quality“** (Durchsicht über fix/review-kern,
    L3): Eine vorher berechnete Variable, ein Schalter, eine Hilfsfunktion, ein
    Aufruf über das Modul oder einen Importalias gingen am ersten Wächter
    vorbei. Jetzt ist ein ``stages=`` im Kern nur ein Tupel aus Stufennamen oder
    ``DRAFT_CHAIN``/``FULL_CHAIN`` aus ``boolean.py``, alles andere ist rot —
    auch ``**kwargs``, das eine Folge mitbringen könnte. Der Behälterbau legt
    gar keine fest.
    """
    root = Path(__file__).resolve().parents[1]
    calls = 0
    fixed: list[str] = []
    forbidden: list[str] = []
    for path in sorted((root / "app" / "core").rglob("*.py")):
        place = path.relative_to(root).as_posix()
        for line, said in _boolean_calls(root, path):
            calls += 1
            if said and path.name == "container_ops.py":
                fixed.append(f"{place}:{line}")
            if said not in ("", "erlaubt"):
                forbidden.append(f"{place}:{line} {said}")
    assert calls > 100, f"nur {calls} Aufrufe von boolean gefunden — die Auflösung greift nicht"
    assert not forbidden, "Stufen, die keine feste Folge sind:\n" + "\n".join(forbidden)
    assert not fixed, f"der Behälterbau legt seine Stufen fest: {fixed}"


def _the_first_short_chain_gives_up(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Nur der erste kurze Kettenlauf gibt auf: *direkt* und *verschweißt* des ersten Schnitts.

    Wie ein Kern, der an einer Stelle einmal aufgibt; jeder spätere Aufruf
    rechnet echt. Leert der Test die zurückgegebene Liste, gibt der nächste
    erste Lauf wieder auf. Scheiterten alle verlustfreien Stufen
    (``short_chain_finds_nothing``), rechnete auch der Deckel über die
    Ersatzstufen, und der Test prüfte etwas anderes als die Kette.
    """
    from app.core.geom import boolean as boolean_module

    real = boolean_module._run_stage
    failed: list[str] = []

    def stage(kind: Any, meshes: Any, name: str, seed: Any, cancelled: Any = None) -> Any:
        if name in boolean_module.DRAFT_CHAIN and len(failed) < len(boolean_module.DRAFT_CHAIN):
            failed.append(name)
            raise RuntimeError("Kern gibt auf")
        return real(kind, meshes, name, seed, cancelled)

    monkeypatch.setattr(boolean_module, "_run_stage", stage)
    return failed


def test_a_container_goes_the_full_chain_where_the_short_one_ends(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FD-6, RM-534: Am Behälter kürzt die Güte die Kette, und das Fenster rechnet weiter.

    Gab der erste Schnitt im Entwurf auf, hielt der Behälter an Schritt 1 mit
    *Gröber rechnen* als Ausweg — sein Aufruf legte die Entwurfskette selbst
    fest, und die Absage galt nicht als gekürzt. Jetzt rechnet der Fensterlauf
    den Schritt mit der vollen Kette zu Ende, eine Vorschau hält als schnelle
    Rechnung (*Übernehmen* bleibt frei), und ein gelungener Entwurf fragt die
    Güte gar nicht: Druck und Export rechnen ihn nicht noch einmal (RM-494).
    """
    from app.core.bootstrap import load_operations
    from app.core.scene.project import new_project

    load_operations()
    document = new_project("centauri-carbon-2", "petg").document
    History(document).apply(
        "Behälter",
        [
            OperationDraft(
                op="create_container",
                params={"shape": "rectangular", "lid": "push", "kernel": "mesh"},
            )
        ],
    )
    step = document.ops[-1].id

    plain = window_evaluation(document, profile)
    assert plain.complete, [str(finding.message) for finding in plain.scene.report.findings]

    failed = _the_first_short_chain_gives_up(monkeypatch)
    rescued = window_evaluation(document, profile)
    assert failed == ["direct", "welded"], f"Voraussetzung: der erste Schnitt gab auf: {failed}"
    assert rescued.stopped_at is None, [
        str(finding.message) for finding in rescued.scene.report.findings
    ]
    assert rescued.reads_quality, "ein fein nachgerechneter Schritt fragt nach der Güte"
    assert rescued.object_hashes == plain.object_hashes, "die volle Kette baut denselben Behälter"

    failed.clear()
    preview = evaluate(document, profile, quality="draft")
    assert preview.stopped_at == step, "Voraussetzung: die Vorschau rechnet die volle Kette nie"
    assert preview.short_chain_only, "der Halt der Vorschau sperrt Übernehmen"
    assert preview.reads_quality
    assert not plain.reads_quality, "ein gelungener Entwurf ist schon die feine Rechnung"


def test_a_container_carried_by_the_third_stage_keeps_its_opening(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Beobachtung der Durchsicht welle4-b: Trägt erst Stufe 3, entsteht derselbe Behälter.

    Liefern *direkt* und *verschweißt* an jedem Schnitt nichts, rechnet der
    Fensterlauf voll, und der Stups der dritten Stufe ließ über der Öffnung
    des Gehäuses eine Haut stehen. Der Steckdeckel stieß mit seinem Kragen
    darauf und hielt an: „Der Kragen stößt unter dem Rand auf die Wand“ —
    ein falscher Grund, und sein Rat (Kragentiefe null) hätte die Haut im
    Behälter gelassen.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene.project import new_project

    load_operations()
    document = new_project("centauri-carbon-2", "petg").document
    History(document).apply(
        "Behälter",
        [
            OperationDraft(
                op="create_container",
                params={"shape": "rectangular", "lid": "push", "kernel": "mesh"},
            )
        ],
    )
    step = document.ops[-1].id
    called = short_chain_finds_nothing(monkeypatch, nor_the_full=False)

    rescued = window_evaluation(document, profile)

    assert "jittered" in called, f"Voraussetzung: die dritte Stufe trägt: {called}"
    assert rescued.stopped_at is None, [
        str(finding.message) for finding in rescued.scene.report.findings
    ]
    assert rescued.solvers[step].strategy == "jittered", rescued.solvers[step]
    assert len(rescued.scene.objects) == 2, "Behälter und Deckel"
