"""Eine fremde Datei sagt, was sie mitbringt (Bauplan §32).

Der Warnhinweis beim Öffnen steht in §32 neben der Quelltextprüfung, und er
steht dort aus einem eigenen Grund: geprüft wird, *ob* etwas laufen darf —
erfahren soll der Nutzer, *dass* etwas läuft. Eine Datei aus einer E-Mail ist
kein Grund für einen Riegel, aber einer für einen Satz.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.core.registry import REGISTRY
from app.core.scene import foreign
from app.core.types import Document, Operation, Source

import app  # isort: skip


def _document() -> Document:
    return Document(format_version=7, app_version="0.0.1")


def test_a_plain_document_says_nothing() -> None:
    """Ohne Quelltext und ohne Außenverweis gibt es nichts zu warnen."""
    document = _document()
    document.ops.append(Operation(id=1, op="create_box", params={"width": 10.0}))

    assert foreign.findings_for(document) == []


def test_scad_in_the_stack_is_reported() -> None:
    document = _document()
    document.ops.append(Operation(id=1, op="create_from_scad", params={"source": "cube(10);"}))

    findings = foreign.findings_for(document)

    assert [entry.code for entry in findings] == ["project.scripted_source"]
    assert findings[0].severity == "warning"
    assert findings[0].values["count"] == 1
    assert "1" in str(findings[0].values["operations"]), "der Befund nennt die Stelle"


def test_a_source_outside_the_container_is_reported() -> None:
    """§16.1: eingebettet ist die Vorgabe. Was daneben liegt, kann fehlen."""
    document = _document()
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="teil.stl", sha256="", embedded=False
    )

    findings = foreign.findings_for(document)

    assert [entry.code for entry in findings] == ["project.external_source"]
    assert "src_1" in str(findings[0].values["sources"])


def test_an_embedded_source_is_not_a_warning() -> None:
    document = _document()
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/teil.stl", sha256="abc"
    )

    assert foreign.findings_for(document) == []


def test_both_at_once_are_two_findings() -> None:
    document = _document()
    document.ops.append(Operation(id=1, op="create_from_scad", params={"source": "cube(10);"}))
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="teil.stl", sha256="", embedded=False
    )

    assert len(foreign.findings_for(document)) == 2


def _ops_that_call_openscad() -> set[str]:
    """Jede registrierte Operation, deren Rumpf ``openscad.render`` aufruft.

    Über den Quelltext und nicht über eine gepflegte Liste: eine Liste neben
    dem Code ist an dem Tag falsch, an dem jemand die zweite solche Operation
    schreibt — und genau dann fehlt der Warnhinweis.
    """
    package = Path(app.__file__).parent
    found: set[str] = set()

    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            calls_openscad = any(
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Attribute)
                and inner.func.attr == "render"
                and isinstance(inner.func.value, ast.Name)
                and inner.func.value.id == "openscad"
                for inner in ast.walk(node)
            )
            if not calls_openscad:
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                for keyword in decorator.keywords:
                    if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                        found.add(str(keyword.value.value))
    return found


def test_every_op_that_runs_openscad_is_named() -> None:
    """Der Wächter über ``SCRIPTED_OPS``.

    Ohne ihn veraltet die Liste still, und eine Datei mit der zweiten
    quelltextführenden Operation öffnet sich wortlos.
    """
    running = _ops_that_call_openscad()

    assert running, "der Wächter selbst muss etwas finden, sonst prüft er nichts"
    assert running <= foreign.SCRIPTED_OPS, (
        "diese Operationen starten OpenSCAD und fehlen in foreign.SCRIPTED_OPS:\n"
        + "\n".join(sorted(running - foreign.SCRIPTED_OPS))
    )


def test_the_named_ops_exist() -> None:
    """Keine Karteileiche: was in der Liste steht, gibt es auch."""
    known = {spec.name for spec in REGISTRY.all()}
    assert known >= foreign.SCRIPTED_OPS


# --- Und der Hinweis kommt beim Nutzer an -----------------------------------------


def test_the_report_learns_about_scripted_content(qt_app: object) -> None:
    """Der Befund nützt nichts, solange er im Kern bleibt (§32).

    Geprüft am Auswertungs-Arbeiter, weil dort die drei Prüfungen beim Öffnen
    zusammenlaufen — Bausteinversionen, verwaiste Verweise und diese hier.
    """
    from app.ui.session import Session, _EvaluationWorker

    session = Session()
    session.project.document.ops.append(
        Operation(id=1, op="create_from_scad", params={"source": "cube(10);"})
    )
    session.pending_foreign_check = True

    received: list[object] = []
    worker = _EvaluationWorker(session)
    worker.finishedWith.connect(received.append)
    worker.run()

    assert received, "die Auswertung hält nicht an, sie meldet nur"
    codes = {finding.code for finding in received[0].scene.report.findings}  # type: ignore[attr-defined]
    assert "project.scripted_source" in codes


def test_the_hint_comes_once_and_not_at_every_run(qt_app: object) -> None:
    """Sonst steht die Zeile bei jeder Auswertung da, und niemand liest sie."""
    from app.ui.session import Session, _EvaluationWorker

    session = Session()
    session.project.document.ops.append(
        Operation(id=1, op="create_from_scad", params={"source": "cube(10);"})
    )
    session.pending_foreign_check = True

    received: list[object] = []
    worker = _EvaluationWorker(session)
    worker.finishedWith.connect(received.append)
    worker.run()
    worker.run()

    assert not session.pending_foreign_check
    second = {finding.code for finding in received[1].scene.report.findings}  # type: ignore[attr-defined]
    assert "project.scripted_source" not in second
