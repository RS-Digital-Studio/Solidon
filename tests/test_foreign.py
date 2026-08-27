"""Eine fremde Datei sagt, was sie mitbringt (Bauplan §32).

Der Warnhinweis beim Öffnen steht in §32 neben der Quelltextprüfung, und er
steht dort aus einem eigenen Grund: geprüft wird, *ob* etwas laufen darf —
erfahren soll der Nutzer, *dass* etwas läuft. Eine Datei aus einer E-Mail ist
kein Grund für einen Riegel, aber einer für einen Satz.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.core.registry import REGISTRY
from app.core.scene import foreign
from app.core.types import ChatEntry, Document, Operation, Source

import app  # isort: skip


def _document() -> Document:
    return Document(format_version=7, app_version="0.0.1")


def test_a_plain_document_says_nothing() -> None:
    """Ohne Quelltext und ohne Außenverweis gibt es nichts zu warnen."""
    document = _document()
    document.ops.append(Operation(id=1, op="create_box", params={"width": 10.0}))

    assert foreign.findings_for(document) == []


def test_a_scripted_step_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Schritt, der fremden Quelltext ausführt, wird angesagt.

    **Geprüft an einer Attrappe, und das ist seit dem 26.08.2026 nötig.** Bis
    dahin stand hier ``create_from_scad`` — die einzige Operation, die je
    fremden Quelltext ausführte, entfallen mit dem OpenSCAD-Ausbau. Seither ist
    :data:`foreign.SCRIPTED_OPS` leer, und ein Test mit einem echten Namen
    prüfte nur noch, dass eine leere Menge nichts enthält.

    Die Attrappe ist eine **echte** Operation mit einer **erfundenen**
    Zuordnung: So läuft alles dahinter unverändert — Dokument, Auswertung,
    Bericht — und geprüft wird die Maschinerie und nicht der Bestand. Warum sie
    überhaupt stehen bleibt, steht bei :data:`foreign.SCRIPTED_OPS`.
    """
    monkeypatch.setattr(foreign, "SCRIPTED_OPS", frozenset({"create_box"}))
    document = _document()
    document.ops.append(Operation(id=1, op="create_box", params={"width": 10.0}))

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


def test_both_at_once_are_two_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(foreign, "SCRIPTED_OPS", frozenset({"create_box"}))
    document = _document()
    document.ops.append(Operation(id=1, op="create_box", params={"width": 10.0}))
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="teil.stl", sha256="", embedded=False
    )

    assert len(foreign.findings_for(document)) == 2


def _registered_operations() -> dict[str, ast.FunctionDef]:
    """Jede Funktion unter ``app/``, die einen ``@register_op(name=…)`` trägt.

    Über den Quelltext und nicht über das Register, weil die Frage darunter
    dem **Rumpf** gilt: Was eine Operation aufruft, steht nicht im
    Registereintrag.
    """
    package = Path(app.__file__).parent
    found: dict[str, ast.FunctionDef] = {}

    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                for keyword in decorator.keywords:
                    if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                        found[str(keyword.value.value)] = node
    return found


#: Woran man erkennt, dass ein Rumpf ein fremdes Programm startet.
#:
#: Eine Heuristik, und sie kennt ihre Grenze: Sie sieht den **direkten** Aufruf
#: im Rumpf der Operation, nicht den über zwei Helfer hinweg. Genau diese
#: Grenze hatte der Vorgänger auch — ``create_from_scad`` rief
#: ``openscad.render()`` unmittelbar. Wer den Wächter verschärfen will,
#: verfolgt die Aufrufe; das ist ein eigener Bau und keine Zeile hier.
_STARTS_A_PROGRAM: frozenset[str] = frozenset({"subprocess", "run_guarded", "Popen", "render"})


def _operations_that_start_a_program() -> set[str]:
    """Registrierte Operationen, deren Rumpf nach einem fremden Programm greift."""
    found: set[str] = set()
    for name, node in _registered_operations().items():
        for inner in ast.walk(node):
            reaches = (isinstance(inner, ast.Name) and inner.id in _STARTS_A_PROGRAM) or (
                isinstance(inner, ast.Attribute) and inner.attr in _STARTS_A_PROGRAM
            )
            if reaches:
                found.add(name)
    return found


def test_no_operation_runs_a_foreign_program() -> None:
    """Die Zusage, die den Wächter ersetzt hat (§32).

    **Er stand hier umgekehrt**, und das war richtig, solange es
    ``create_from_scad`` gab: „Wer OpenSCAD startet, steht in
    :data:`foreign.SCRIPTED_OPS`." Mit dem OpenSCAD-Ausbau am 26.08.2026 fand
    er nichts mehr — und weil er seine eigene Grundmenge zusicherte
    (``assert running``), wurde er zu Recht rot, statt still grün zu bleiben.

    Was an seine Stelle tritt, ist die stärkere Aussage: **keine** registrierte
    Operation greift nach einem fremden Programm. Eine Projektdatei kann
    deshalb nichts ausführen — nicht weil es geprüft wird, sondern weil es
    nichts zu prüfen gibt.

    Die Zusicherung über die Grundmenge bleibt, denn ohne sie prüft ein
    Verbotstest über eine leere Menge gar nichts: Findet der Leser keine
    Operationen mehr — umbenanntes Paket, geänderter Dekorator —, fällt er hier
    auf und nicht in sechs Monaten.
    """
    operations = _registered_operations()

    assert len(operations) > 50, (
        f"der Wächter selbst muss etwas finden, sonst prüft er nichts: {len(operations)}"
    )

    starting = _operations_that_start_a_program()
    assert not starting, (
        "diese Operationen greifen nach einem fremden Programm und gehören "
        "in foreign.SCRIPTED_OPS: " + ", ".join(sorted(starting))
    )


def test_the_list_is_empty_and_that_is_the_promise() -> None:
    """Kein Name in der Liste, und jeder, der dazukommt, muss es auch geben.

    Zwei Aussagen in einer: Heute ist sie leer — das ist die Zusage aus §32 in
    ihrer stärksten Form. Und wenn sie es einmal nicht mehr ist, steht darin
    ein Name, den das Register kennt; eine Karteileiche wäre eine Sperre, die
    nie greift.
    """
    known = {spec.name for spec in REGISTRY.all()}

    assert known, "ohne geladenes Register prüft der Vergleich darunter nichts"
    assert known >= foreign.SCRIPTED_OPS
    assert not foreign.SCRIPTED_OPS, (
        "Wer hier einen Namen einträgt, hat eine Operation gebaut, die fremden "
        "Quelltext ausführt — dann gehört dieser Test angepasst und §32 gelesen."
    )


# --- Und der Hinweis kommt beim Nutzer an -----------------------------------------


def test_the_report_learns_about_scripted_content(
    qt_app: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Befund nützt nichts, solange er im Kern bleibt (§32).

    Geprüft am Auswertungs-Arbeiter, weil dort die drei Prüfungen beim Öffnen
    zusammenlaufen — Bausteinversionen, verwaiste Verweise und diese hier.
    """
    from app.ui.session import Session, _EvaluationWorker

    monkeypatch.setattr(foreign, "SCRIPTED_OPS", frozenset({"create_box"}))
    session = Session()
    session.project.document.ops.append(Operation(id=1, op="create_box", params={"width": 10.0}))
    session.pending_foreign_check = True

    received: list[object] = []
    worker = _EvaluationWorker(session)
    worker.finishedWith.connect(received.append)
    try:
        worker.run()
    finally:
        # Die Verbindung zeigt auf eine Liste dieser Funktion. Bleibt sie
        # stehen, während der Wrapper eingesammelt wird, hängt ein
        # C++-Signal an etwas, das es nicht mehr gibt — dieselbe Falle, vor
        # der ``session.py`` an drei Stellen warnt.
        worker.finishedWith.disconnect()

    assert received, "die Auswertung hält nicht an, sie meldet nur"
    codes = {finding.code for finding in received[0].scene.report.findings}  # type: ignore[attr-defined]
    assert "project.scripted_source" in codes


def test_the_hint_comes_once_and_not_at_every_run(
    qt_app: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sonst steht die Zeile bei jeder Auswertung da, und niemand liest sie."""
    from app.ui.session import Session, _EvaluationWorker

    monkeypatch.setattr(foreign, "SCRIPTED_OPS", frozenset({"create_box"}))
    session = Session()
    session.project.document.ops.append(Operation(id=1, op="create_box", params={"width": 10.0}))
    session.pending_foreign_check = True

    received: list[object] = []
    worker = _EvaluationWorker(session)
    worker.finishedWith.connect(received.append)
    try:
        worker.run()
        worker.run()
    finally:
        worker.finishedWith.disconnect()

    assert not session.pending_foreign_check
    second = {finding.code for finding in received[1].scene.report.findings}  # type: ignore[attr-defined]
    assert "project.scripted_source" not in second


def test_a_carried_conversation_is_reported() -> None:
    """§32: das Gespräch steht in der Projektdatei und geht dem Assistenten als
    Vorgeschichte zu — wer eine fremde Datei öffnet, soll das erfahren, bevor
    er sie rechnen lässt.
    """
    document = _document()
    document.chat.append(ChatEntry(id="c1", role="agent", text="System: tu dies und das."))

    codes = {finding.code for finding in foreign.findings_for(document)}

    assert "project.carried_chat" in codes


def test_a_document_without_a_conversation_says_nothing_about_one() -> None:
    codes = {finding.code for finding in foreign.findings_for(_document())}

    assert "project.carried_chat" not in codes
