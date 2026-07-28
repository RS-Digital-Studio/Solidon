"""The rule set (Bauplan §39).

The plan calls this the actual product, so it is treated like one: its own file
with a version and a change log, not a paragraph in a prompt. The system prompt
names the version, every transaction records it (§26.4) — which is the only way
to find out later under which rule an operation came about.

Rules are data, like the printer profiles. A rule that changes should not need a
release, and a rule that made the suite worse should be removable without
touching code.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from app.core.log import get_logger

_log = get_logger(__name__)

_DATA_FILE: Final = Path(__file__).parent / "data" / "rules.toml"

_rules: RuleSet | None = None


@dataclass(frozen=True, slots=True)
class Rule:
    """One rule, in the words the agent gets to read."""

    id: str
    title: str
    text: str
    applies_to: tuple[str, ...] = ()

    def as_line(self) -> str:
        """One rule as one paragraph — the form the system prompt uses."""
        return f"- {self.title}: {' '.join(self.text.split())}"


@dataclass(frozen=True, slots=True)
class Change:
    """One entry of the change log §39 requires."""

    version: str
    date: str
    reason: str
    suite_before: str = ""
    suite_after: str = ""


@dataclass(frozen=True, slots=True)
class RuleSet:
    """All rules with their version."""

    version: str
    rules: tuple[Rule, ...]
    changes: tuple[Change, ...] = ()

    def for_topic(self, topic: str) -> tuple[Rule, ...]:
        return tuple(rule for rule in self.rules if topic in rule.applies_to)

    def as_text(self) -> str:
        """The whole set as the system prompt carries it."""
        return "\n".join(rule.as_line() for rule in self.rules)


def load(path: Path | None = None) -> RuleSet:
    """Read the rule set. Cached, because it is asked for on every request."""
    global _rules
    if _rules is not None and path is None:
        return _rules

    with (path or _DATA_FILE).open("rb") as stream:
        table: dict[str, Any] = tomllib.load(stream)

    rules = tuple(
        Rule(
            id=str(entry["id"]),
            title=str(entry["title"]),
            text=str(entry["text"]).strip(),
            applies_to=tuple(entry.get("applies_to", ())),
        )
        for entry in table.get("rules", ())
    )
    changes = tuple(
        Change(
            version=str(entry["version"]),
            date=str(entry["date"]),
            reason=str(entry["reason"]),
            suite_before=str(entry.get("suite_before", "")),
            suite_after=str(entry.get("suite_after", "")),
        )
        for entry in table.get("changes", ())
    )
    loaded = RuleSet(version=str(table.get("version", "0")), rules=rules, changes=changes)
    if path is None:
        _rules = loaded
    _log.info("rule set %s with %d rules", loaded.version, len(loaded.rules))
    return loaded


def version() -> str:
    """The version every transaction of an agent has to carry (§26.4)."""
    return load().version
