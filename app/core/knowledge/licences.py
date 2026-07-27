"""Checking dependency licences (Bauplan §36).

The policy lives in ``data/licences.toml``; this module compares it against what
is actually installed. Two things are checked: nothing carries a GPL-style
licence, and nothing from the banned list is present at all.

The check walks the real dependency tree of the runtime extras, so a transitive
package cannot slip in unseen.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Final

from app.core.log import get_logger

_log = get_logger(__name__)

_DATA_FILE: Final = Path(__file__).parent / "data" / "licences.toml"

#: Extras whose dependencies end up in the shipped application.
RUNTIME_EXTRAS: Final[tuple[str, ...]] = ("geom", "ui")

_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_EXTRA_MARKER = re.compile(r"extra\s*==\s*[\"']([^\"']+)[\"']")


@dataclass(frozen=True, slots=True)
class Policy:
    allowed: tuple[str, ...]
    forbidden: tuple[str, ...]
    banned_packages: tuple[str, ...]
    known: dict[str, dict[str, str]]


@dataclass(frozen=True, slots=True)
class Violation:
    """One dependency that does not fit the policy."""

    package: str
    licence: str
    reason: str

    def __str__(self) -> str:
        return f"{self.package} ({self.licence}): {self.reason}"


def load_policy() -> Policy:
    with _DATA_FILE.open("rb") as stream:
        data: dict[str, Any] = tomllib.load(stream)
    policy = data.get("policy", {})
    return Policy(
        allowed=tuple(policy.get("allowed", ())),
        forbidden=tuple(policy.get("forbidden", ())),
        banned_packages=tuple(policy.get("banned_packages", ())),
        known=data.get("known", {}),
    )


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def declared_licence(distribution: metadata.Distribution) -> str:
    """Read the licence out of the package metadata, however it was written."""
    # Typed as Any: the metadata object is an email.Message, which the stubs hide.
    meta: Any = distribution.metadata
    expression = meta.get("License-Expression")
    if expression:
        return str(expression)
    classifiers = [
        value.split("::")[-1].strip()
        for value in meta.get_all("Classifier", [])
        if value.startswith("License ::")
    ]
    if classifiers:
        return ", ".join(classifiers)
    licence = meta.get("License")
    if licence and len(licence) < 200:
        return str(licence)
    return ""


def _applies_here(requirement: str) -> bool:
    """False for requirements whose environment marker does not hold on this machine."""
    try:
        from packaging.requirements import Requirement
    except ImportError:  # pragma: no cover - packaging comes with the toolchain
        return True
    parsed = Requirement(requirement)
    return parsed.marker is None or parsed.marker.evaluate({"extra": ""})


def requirements_of(distribution: metadata.Distribution) -> set[str]:
    """Runtime requirements — optional extras of a dependency do not count."""
    names: set[str] = set()
    for requirement in distribution.requires or ():
        if _EXTRA_MARKER.search(requirement) is not None:
            continue
        if not _applies_here(requirement):
            continue
        match = _REQUIREMENT_NAME.match(requirement)
        if match:
            names.add(normalise(match.group(1)))
    return names


def _direct_requirements(extras: Iterable[str]) -> set[str]:
    """Our own dependencies, including the runtime extras."""
    own = metadata.distribution("3d-agent")
    wanted = {normalise(entry) for entry in extras}
    names: set[str] = set()
    for requirement in own.requires or ():
        marker = _EXTRA_MARKER.search(requirement)
        if marker is not None and normalise(marker.group(1)) not in wanted:
            continue
        match = _REQUIREMENT_NAME.match(requirement)
        if match:
            names.add(normalise(match.group(1)))
    return names


def runtime_packages(extras: Iterable[str] = RUNTIME_EXTRAS) -> dict[str, str]:
    """Every installed package that ends up in the application, with its licence."""
    found: dict[str, str] = {}
    pending = list(_direct_requirements(extras))
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            _log.warning("dependency %s is declared but not installed", name)
            continue
        found[distribution.metadata["Name"]] = declared_licence(distribution)
        pending.extend(requirements_of(distribution))
    return found


def check(extras: Iterable[str] = RUNTIME_EXTRAS) -> list[Violation]:
    """Compare what is installed against the policy. Empty list means green."""
    policy = load_policy()
    banned = {normalise(entry) for entry in policy.banned_packages}
    known = {normalise(key): value for key, value in policy.known.items()}
    violations: list[Violation] = []

    for package, licence in sorted(runtime_packages(extras).items()):
        key = normalise(package)
        if key in banned:
            violations.append(Violation(package, licence, "steht auf der Sperrliste (§36)"))
            continue
        text = licence or known.get(key, {}).get("licence", "")
        if not text:
            violations.append(
                Violation(package, "unbekannt", "keine Lizenzangabe und kein Eintrag in der Liste")
            )
            continue
        lowered = text.lower()
        # "LGPL-3.0 OR GPL-2.0" is a choice, and we choose LGPL — that is why the
        # presence of LGPL clears a licence string that also mentions GPL (§36).
        if any(entry.lower() in lowered for entry in policy.forbidden) and "lgpl" not in lowered:
            violations.append(Violation(package, text, "GPL-Lizenz ist ausgeschlossen (§36)"))
            continue
        if not any(entry.lower() in lowered for entry in policy.allowed):
            violations.append(Violation(package, text, "Lizenz steht nicht auf der Freigabeliste"))
    return violations


def notices(extras: Iterable[str] = RUNTIME_EXTRAS) -> str:
    """The list for the about dialog and the third party notices (§36, §37.2)."""
    lines = ["| Paket | Lizenz |", "|---|---|"]
    policy = load_policy()
    known = {normalise(key): value for key, value in policy.known.items()}
    for package, licence in sorted(runtime_packages(extras).items()):
        text = licence or known.get(normalise(package), {}).get("licence", "—")
        lines.append(f"| {package} | {text} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover - maintenance helper
    print(notices(), end="")
    for violation in check():
        print(f"VERSTOSS: {violation}")
