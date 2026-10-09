"""Genaue Job- und Schrittblöcke für die Verträge unserer CI-Dateien.

Kein allgemeiner YAML-Parser: Die eingecheckten Workflows verwenden zwei
Leerzeichen je Ebene. Mehrdeutige oder fehlende Blöcke sind ein Fehler.
Dazu ein Auswerter für die Teilmenge der GitHub-Ausdrücke, die die Workflows
benutzen: Er sagt, welcher Job bei welchem Ereignis auf welchen Läufern läuft.
"""

from __future__ import annotations

import json
import re
import textwrap
from collections.abc import Mapping
from typing import Any, Final


def job_block(workflow: str, name: str) -> str:
    """Liest genau den benannten Job, ohne spätere Nachbarjobs mitzunehmen."""
    jobs = workflow.split("\njobs:\n", 1)[1]
    matches = re.findall(rf"(?ms)^  {re.escape(name)}:\n.*?(?=^  [a-zA-Z0-9_-]+:\n|\Z)", jobs)
    assert len(matches) == 1, f"Workflow-Job fehlt oder ist doppelt: {name}"
    return matches[0]


def step_block(job: str, name: str) -> str:
    """Liest einen benannten Schritt bis zum nächsten Schritt, gleich womit er beginnt."""
    matches = re.findall(rf"(?ms)^      - name: {re.escape(name)}\n.*?(?=^      - |\Z)", job)
    assert len(matches) == 1, f"Workflow-Schritt fehlt oder ist doppelt: {name}"
    return matches[0]


def step_script(step: str) -> str:
    """Liefert den eingerückten Shellblock ohne nachfolgende Schrittattribute."""
    match = re.search(r"(?m)^        run: \|\n((?: {10}.*\n|\n)+)", step + "\n")
    assert match is not None, "Workflow-Schritt enthält keinen Shellblock"
    return textwrap.dedent(match.group(1))


# --- GitHub-Ausdrücke: welcher Job bei welchem Ereignis läuft -----------------------

#: Die Teilmenge der Ausdruckssprache, die unsere Workflows benutzen: Literale,
#: Kontextnamen mit Punkten, ``!``, ``==``, ``!=``, ``&&``, ``||``, Klammern und
#: einige Funktionen. Was darüber hinausgeht, ist ein Fehler, kein stilles Falsch.
_TOKEN = re.compile(
    r"\s*(?:(?P<string>'(?:[^']|'')*')|(?P<number>\d+(?:\.\d+)?)"
    r"|(?P<op>&&|\|\||==|!=|!|\(|\)|,)|(?P<name>[A-Za-z_][\w.-]*))"
)


def _tokens(expression: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    position = 0
    text = expression.strip()
    while position < len(text):
        match = _TOKEN.match(text, position)
        assert match is not None and match.end() > position, f"unbekannt: {text[position:]!r}"
        kind = match.lastgroup
        assert kind is not None
        found.append((kind, match.group(kind)))
        position = match.end()
    return found


def _truthy(value: object) -> bool:
    return value not in (None, False, 0, "")


def _number(value: object) -> float:
    if value is None or value is False:
        return 0.0
    if value is True:
        return 1.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value)) if str(value).strip() else 0.0
    except ValueError:
        return float("nan")


def _equal(left: object, right: object) -> bool:
    """Gleichheit wie bei GitHub: Text ohne Groß- und Kleinschreibung, sonst als Zahl."""
    if isinstance(left, str) and isinstance(right, str):
        return left.lower() == right.lower()
    if type(left) is type(right) and not isinstance(left, (bool, int, float)) and left is not None:
        return left == right
    return _number(left) == _number(right)


class _Parser:
    """Rekursiver Abstieg über die Token eines Ausdrucks."""

    def __init__(self, expression: str, context: Mapping[str, Any]) -> None:
        self.tokens = _tokens(expression)
        self.position = 0
        self.context = context

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self, value: str | None = None) -> tuple[str, str]:
        token = self.peek()
        assert token is not None, "Ausdruck endet zu früh"
        assert value is None or token[1] == value, f"erwartet {value}, gefunden {token[1]}"
        self.position += 1
        return token

    def parse(self) -> Any:
        value = self.either()
        assert self.peek() is None, f"Rest im Ausdruck: {self.tokens[self.position :]}"
        return value

    def either(self) -> Any:
        value = self.both()
        while self.peek() == ("op", "||"):
            self.take()
            right = self.both()
            value = value if _truthy(value) else right
        return value

    def both(self) -> Any:
        value = self.negated()
        while self.peek() == ("op", "&&"):
            self.take()
            right = self.negated()
            value = right if _truthy(value) else value
        return value

    def negated(self) -> Any:
        if self.peek() == ("op", "!"):
            self.take()
            return not _truthy(self.negated())
        return self.compared()

    def compared(self) -> Any:
        left = self.primary()
        token = self.peek()
        if token in (("op", "=="), ("op", "!=")):
            self.take()
            right = self.primary()
            same = _equal(left, right)
            return same if token == ("op", "==") else not same
        return left

    def primary(self) -> Any:
        kind, value = self.take()
        if kind == "string":
            return value[1:-1].replace("''", "'")
        if kind == "number":
            return float(value)
        if value == "(":
            inner = self.either()
            self.take(")")
            return inner
        assert kind == "name", f"unerwartet: {value}"
        if value in {"true", "false"}:
            return value == "true"
        if value == "null":
            return None
        if self.peek() == ("op", "("):
            self.take()
            arguments = []
            while self.peek() != ("op", ")"):
                arguments.append(self.either())
                if self.peek() == ("op", ","):
                    self.take()
            self.take(")")
            return self.call(value, arguments)
        found: Any = self.context
        for part in value.split("."):
            found = found.get(part) if isinstance(found, Mapping) else None
        return found

    def call(self, name: str, arguments: list[Any]) -> Any:
        status = self.context.get("status", "success")
        functions: dict[str, Any] = {
            "startsWith": lambda text, start: (
                str(text or "").lower().startswith(str(start).lower())
            ),
            "endsWith": lambda text, end: str(text or "").lower().endswith(str(end).lower()),
            "contains": lambda text, part: str(part).lower() in str(text or "").lower(),
            "fromJSON": lambda text: json.loads(text),
            "success": lambda: status == "success",
            "failure": lambda: status == "failure",
            "cancelled": lambda: status == "cancelled",
            "always": lambda: True,
        }
        assert name in functions, f"unbekannte Funktion: {name}"
        return functions[name](*arguments)


def evaluate(expression: str, context: Mapping[str, Any]) -> Any:
    """Wertet einen GitHub-Ausdruck aus, mit oder ohne ``${{ }}``, gegen ``context``.

    ``context`` hält ``github``, ``inputs``, ``vars``, ``needs`` und als
    ``status`` das Ergebnis der Vorgänger (``success``, ``failure``, …).
    """
    text = expression.strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2]
    return _Parser(text, context).parse()


def job_condition(block: str) -> str | None:
    """Die Bedingung eines Jobs, auch über mehrere Zeilen (``if: >-``)."""
    match = re.search(r"(?m)^    if: (.*)$", block)
    if match is None:
        return None
    if match.group(1).strip() != ">-":
        return match.group(1)
    lines = block[match.end() + 1 :].splitlines()
    taken = []
    for line in lines:
        if not line.startswith("      "):
            break
        taken.append(line.strip())
    return " ".join(taken)


def job_needs(block: str) -> list[str]:
    """Die Vorgänger eines Jobs."""
    match = re.search(r"(?m)^    needs: (?:\[([^\]]+)\]|([a-z0-9-]+))$", block)
    if match is None:
        return []
    return [name.strip() for name in (match.group(1) or match.group(2)).split(",")]


def job_names(workflow: str) -> list[str]:
    """Die Jobnamen eines Workflows in ihrer Reihenfolge."""
    return re.findall(r"(?m)^  ([a-z][a-z0-9-]*):\n", workflow.split("\njobs:\n", 1)[1])


def running_jobs(
    workflow: str,
    context: Mapping[str, Any],
    outputs: Mapping[str, Mapping[str, str]] | None = None,
) -> set[str]:
    """Welche Jobs bei diesem Ereignis laufen, wenn jeder laufende grün endet.

    Ein Job, dessen Vorgänger nicht alle liefen, läuft nur, wenn seine Bedingung
    das Ergebnis selbst liest (``always()`` und ``needs.<job>.result``). ``outputs``
    sind die Ausgaben der Vorgänger (``needs.<job>.outputs``).
    """
    names = job_names(workflow)
    decided: dict[str, bool] = {}

    def runs(name: str) -> bool:
        if name in decided:
            return decided[name]
        block = job_block(workflow, name)
        needs = job_needs(block)
        results = {need: "success" if runs(need) else "skipped" for need in needs}
        condition = job_condition(block) or "success()"
        status = "success" if all(value == "success" for value in results.values()) else "skipped"
        if status != "success" and "always()" not in condition:
            decided[name] = False
            return False
        scope = {
            **context,
            "needs": {
                need: {"result": result, "outputs": dict((outputs or {}).get(need, {}))}
                for need, result in results.items()
            },
            "status": status,
        }
        decided[name] = _truthy(evaluate(condition, scope))
        return decided[name]

    return {name for name in names if runs(name)}


def job_runners(block: str, context: Mapping[str, Any]) -> tuple[str, ...]:
    """Die Läufer eines Jobs bei diesem Ereignis: Matrixliste, Matrixausdruck,
    ``include`` oder fester ``runs-on``."""
    listed = re.search(r"(?m)^        os: \[([^\]]+)\]$", block)
    if listed is not None:
        return tuple(label.strip() for label in listed.group(1).split(","))
    computed = re.search(r"(?m)^        os: (\$\{\{.*\}\})$", block)
    if computed is not None:
        return tuple(evaluate(computed.group(1), context))
    included = re.findall(r"(?m)^          - os: ([a-z0-9.-]+)$", block)
    if included:
        return tuple(included)
    fixed = re.search(r"(?m)^    runs-on: ([a-z0-9.-]+)$", block)
    assert fixed is not None, "Job ohne erkennbare Läufer"
    return (fixed.group(1),)


def workflow_triggers(workflow: str) -> dict[str, list[str]]:
    """Die Ereignisse unter ``on:`` mit ihren Zweig- und Tagfiltern."""
    section = workflow.split("\non:\n", 1)[1]
    section = re.split(r"(?m)^\S", section, maxsplit=1)[0]
    found: dict[str, list[str]] = {}
    current = ""
    for line in section.splitlines():
        event = re.match(r"^  ([a-z_]+):", line)
        if event:
            current = event.group(1)
            found[current] = []
            continue
        filtered = re.match(r"^    (branches|tags): \[(.*)\]$", line)
        if filtered and current:
            found[current] += [
                f"{filtered.group(1)}:{entry.strip().strip(chr(34))}"
                for entry in filtered.group(2).split(",")
            ]
    return found


#: Die Ereignisse, um die es in den Verträgen geht.
TAG_PUSH: Final = {
    "github": {
        "event_name": "push",
        "ref": "refs/tags/v1.0.0",
        "event": {"repository": {"private": False}},
    },
    "inputs": {},
    "vars": {},
}
MAIN_PUSH: Final = {
    "github": {
        "event_name": "push",
        "ref": "refs/heads/main",
        "event": {"repository": {"private": False}},
    },
    "inputs": {},
    "vars": {},
}
