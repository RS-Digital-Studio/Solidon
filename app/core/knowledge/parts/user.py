"""Own parts from the user directory (Bauplan §24.5).

The same registration, read from ``<user data>/parts/*.py`` at start. **This is
not a plugin system**, and the difference is the reach:

* own parts count on the machine they lie on and **never travel in a project
  file** — otherwise the rule from §32 would be circumvented, that an
  incoming file never executes code;
* opening a project that uses an unknown own part **stops** and says what is
  missing (§15.2), rather than computing something else;
* they extend the library, not the application: no new operations, no changes
  to the surface, no access to the operation stack.

A file that fails to import is reported and skipped. One broken own part must
not stop the application from starting.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.core.knowledge.parts.registry import PARTS, PartRegistry
from app.core.log import get_logger
from app.core.paths import user_parts_dir
from app.core.types import Finding
from app.i18n import _

_log = get_logger(__name__)

#: Prefix of the module names own parts are imported under, so they cannot
#: collide with anything the application ships.
MODULE_PREFIX = "formwerk_user_parts"


@dataclass(slots=True)
class LoadResult:
    """What came out of the user directory."""

    loaded: tuple[str, ...] = ()
    findings: list[Finding] = field(default_factory=list)


def load(directory: Path | None = None, registry: PartRegistry | None = None) -> LoadResult:
    """Read own parts. Missing directory is not an error, it is the normal case."""
    target = directory or user_parts_dir()
    result = LoadResult()
    if not target.is_dir():
        return result

    before = set((registry or PARTS).versions())
    for path in sorted(target.glob("*.py")):
        try:
            _import_file(path)
        except Exception as problem:  # a user file fails in user ways
            _log.warning("own part %s could not be loaded: %s", path.name, problem)
            result.findings.append(
                Finding(
                    code="parts.user_failed",
                    severity="warning",
                    message=_("Ein eigener Baustein ließ sich nicht laden."),
                    values={"file": path.name, "reason": str(problem)[:200]},
                )
            )

    after = (registry or PARTS).versions()
    result.loaded = tuple(sorted(set(after) - before))
    for name in result.loaded:
        _mark_as_own(name, registry)
    if result.loaded:
        _log.info("loaded %d own parts", len(result.loaded))
    return result


def _import_file(path: Path) -> None:
    """Import one file under its own module name.

    The user's directory is not on the import path, and it does not become part
    of it: the module is loaded from its location and named so it cannot shadow
    anything (§32).
    """
    name = f"{MODULE_PREFIX}.{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"{path.name} is not importable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)


def _mark_as_own(name: str, registry: PartRegistry | None) -> None:
    """The catalogue marks own parts (§24.5), so the source has to be recorded."""
    (registry or PARTS).mark_source(name, "user")


def travelling_parts(used: dict[str, str], registry: PartRegistry | None = None) -> tuple[str, ...]:
    """Own parts a project would need — the ones that never travel with it.

    Used when saving and when opening: on the way out to warn, on the way in to
    stop rather than compute something else.
    """
    source = registry or PARTS
    return tuple(name for name in sorted(used) if source.has(name) and source.get(name).own)
