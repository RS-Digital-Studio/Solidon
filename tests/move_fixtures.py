"""Attrappen für das Verschiebewerkzeug (``tools/move_names.py``), ohne Testfälle.

Je Modus ein kleiner Baum mit echten Paketformen — Kopf- und späte Importe, Modulalias,
Patches als Text, über ``patch.object`` und als Dekorator, ein Quelltextleser, ein ``global``-
Schreiber, ``TYPE_CHECKING``, ein Register mit fester Reihenfolge und ein eigener Registerabzug
(``tools/registry_dump.py`` mit derselben Befehlszeile wie das echte W3-Werkzeug) — dazu der
Zuschnitt und der **von Hand geschriebene** Sollbaum danach. Der Sollbaum ist der Wert von außen:
Der Beweis muss ihn annehmen und jede gezielte Abweichung davon ablehnen, und der Schreiber muss
ihn Byte für Byte erzeugen.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

#: Ruff-Einstellung der Attrappe wie im Projekt; das Werkzeug formatiert damit.
PYPROJECT = """\
[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint.isort]
known-first-party = ["app", "tools", "tests"]
"""

REGISTRY_DUMP = '''\
"""Registerabzug der Attrappe: Name und Prüffeld in Registerreihenfolge, nie die Funktion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    from app.core import bootstrap, registry

    bootstrap.load_operations()
    lines = [f"[op:{name}]\\ncheck = {check!r}" for name, _fn, check in registry.REGISTRY]
    args.out.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

#: Was jede Attrappe teilt: Register, Bootstrap, ein zweites Modul mit Operation, Formen.
BASE: dict[str, str] = {
    "pyproject.toml": PYPROJECT,
    "app/__init__.py": "",
    "app/core/__init__.py": '"""Kern der Attrappe."""\n',
    "app/core/registry.py": '''
        """Ein kleines Register wie ``register_op``: Die Reihenfolge der Registrierung zählt."""

        from __future__ import annotations

        from collections.abc import Callable

        REGISTRY: list[tuple[str, Callable[..., object], str]] = []


        Fn = Callable[..., object]


        def register(name: str, check: str = "") -> Callable[[Fn], Fn]:
            """Trägt die Funktion unter ``name`` ein; ``check`` ist ein Feld wie ein Prüfwert."""

            def wrap(fn: Fn) -> Fn:
                REGISTRY.append((name, fn, check))
                return fn

            return wrap
    ''',
    "app/core/bootstrap.py": '''
        """Lädt die Module mit Operationen in fester Reihenfolge."""

        from __future__ import annotations

        import importlib

        _OPERATION_MODULES = (
            "app.core.legacy",
            "app.core.other",
        )


        def load_operations() -> None:
            for name in _OPERATION_MODULES:
                importlib.import_module(name)
    ''',
    "app/core/other.py": '''
        """Ein zweites Modul mit Operation, damit die Reihenfolge sichtbar wird."""

        from __future__ import annotations

        from app.core.registry import register


        @register("other", check="ok")
        def other_op() -> int:
            return 2
    ''',
    "app/core/shapes.py": '''
        """Formen."""


        class Shape:
            points: tuple[int, ...] = ()


        class Hidden(Shape):
            pass
    ''',
    "tools/__init__.py": "",
    "tools/registry_dump.py": REGISTRY_DUMP,
    "tests/__init__.py": "",
}

# ---------------------------------------------------------------------------- Modulmodus

MODULE_OLD: dict[str, str] = BASE | {
    "app/core/legacy.py": '''
        """Alte Datei: Zähler, Regeln und eine Operation."""

        from __future__ import annotations

        import logging
        from typing import TYPE_CHECKING

        from app.core.registry import register
        from app.core.shapes import Shape

        if TYPE_CHECKING:
            from app.core.shapes import Hidden

        logger = logging.getLogger(__name__)

        COUNT = 0


        def bump() -> None:
            """Zählt einen Schritt."""
            global COUNT
            COUNT += 1
            logger.debug("Zähler %s", COUNT)


        def read_count() -> int:
            return COUNT


        # Kopfkommentar: gehört zu _adjust und wandert mit.
        @register(
            "adjust",
            check="points",
        )
        def _adjust(shape: Shape) -> int:
            """Ändert nichts, liefert die Zahl der Punkte – Umlaute: äöüß."""
            return len(shape.points) + read_count()


        class Rule:
            """Eine Regel, die zählt und anpasst."""

            def apply(self, hidden: Hidden) -> int:
                bump()
                return _adjust(hidden)
    ''',
    "app/core/consumer.py": '''
        """Leser in allen Formen."""

        from __future__ import annotations

        import app.core.legacy
        from app.core import legacy as module
        from app.core.legacy import _adjust as local_adjust


        def direct(shape: object) -> int:
            return local_adjust(shape)


        def via_alias(shape: object) -> int:
            return module._adjust(shape)


        def via_full() -> int:
            return app.core.legacy.read_count()


        def late(shape: object) -> int:
            from app.core.legacy import _adjust

            return _adjust(shape)


        def shadow(module: object) -> object:
            return module._adjust  # Parameter, kein Modul: bleibt


        def by_name() -> object:
            return getattr(module, "bump")


        def store() -> None:
            module.COUNT = 5
    ''',
    "tools/check_legacy.py": '''
        """Ein Werkzeug mit Kopf- und spätem Import."""

        from __future__ import annotations

        from app.core.legacy import read_count


        def show() -> int:
            return read_count()


        def late() -> object:
            from app.core import legacy

            return legacy.Rule
    ''',
    "tests/test_legacy.py": '''
        """Patches in allen Formen und ein Quelltextleser."""

        from __future__ import annotations

        from pathlib import Path
        from unittest import mock
        from unittest.mock import patch

        from app.core import legacy
        from app.core.legacy import _adjust


        def test_paths(monkeypatch):
            monkeypatch.setattr("app.core.legacy._adjust", lambda shape: 1)
            monkeypatch.setattr(legacy, "bump", lambda: None)
            with patch("app.core.legacy.read_count", return_value=3):
                pass
            with patch.object(legacy, "_adjust", lambda shape: 4):
                pass
            with mock.patch.object(legacy, "COUNT", 7):
                pass
            assert _adjust is not None


        @patch("app.core.legacy.bump")
        def test_decorated(bump_mock):
            assert bump_mock is not None


        def test_source():
            text = Path(legacy.__file__).read_text(encoding="utf-8")
            assert "def bump" in text
    ''',
}

MODULE_CUT = """\
schema_version = 1
id = "legacy-split"
mode = "module"
source = "app/core/legacy.py"
package_docstring = "Zähler, Regeln und eine Operation der Attrappe."

[[targets]]
module = "app.core.legacy.state"
docstring = "Zustand: der Zähler und sein Protokoll."
definitions = ["logger", "COUNT", "bump", "read_count"]

[[targets]]
module = "app.core.legacy.rules"
docstring = "Regeln und die Operation."
definitions = ["_adjust", "Rule"]

[[renames]]
name = "_adjust"
to = "adjust"

[[identity]]
name = "logger"
reason = "Der Logger heißt danach app.core.legacy.state; die Hierarchie trägt seine Meldungen."

[[name_lists]]
path = "app/core/bootstrap.py"
value = "app.core.legacy"
to = ["app.core.legacy.rules"]

[[source_readers]]
path = "tests/test_legacy.py"
scope = "test_source"
module = "app.core.legacy.state"
"""

#: Der Sollbaum nach dem Schnitt, von Hand geschrieben (``None``: Datei entfällt).
MODULE_NEW: dict[str, str | None] = {
    "app/core/legacy.py": None,
    "app/core/legacy/__init__.py": '"""Zähler, Regeln und eine Operation der Attrappe."""\n',
    "app/core/legacy/state.py": '''
        """Zustand: der Zähler und sein Protokoll."""

        from __future__ import annotations

        import logging

        logger = logging.getLogger(__name__)

        COUNT = 0


        def bump() -> None:
            """Zählt einen Schritt."""
            global COUNT
            COUNT += 1
            logger.debug("Zähler %s", COUNT)


        def read_count() -> int:
            return COUNT
    ''',
    "app/core/legacy/rules.py": '''
        """Regeln und die Operation."""

        from __future__ import annotations

        from typing import TYPE_CHECKING

        from app.core.legacy import state
        from app.core.registry import register
        from app.core.shapes import Shape

        if TYPE_CHECKING:
            from app.core.shapes import Hidden


        # Kopfkommentar: gehört zu _adjust und wandert mit.
        @register(
            "adjust",
            check="points",
        )
        def adjust(shape: Shape) -> int:
            """Ändert nichts, liefert die Zahl der Punkte – Umlaute: äöüß."""
            return len(shape.points) + state.read_count()


        class Rule:
            """Eine Regel, die zählt und anpasst."""

            def apply(self, hidden: Hidden) -> int:
                state.bump()
                return adjust(hidden)
    ''',
    "app/core/bootstrap.py": '''
        """Lädt die Module mit Operationen in fester Reihenfolge."""

        from __future__ import annotations

        import importlib

        _OPERATION_MODULES = (
            "app.core.legacy.rules",
            "app.core.other",
        )


        def load_operations() -> None:
            for name in _OPERATION_MODULES:
                importlib.import_module(name)
    ''',
    "app/core/consumer.py": '''
        """Leser in allen Formen."""

        from __future__ import annotations

        import app.core.legacy.state
        from app.core.legacy import rules, state
        from app.core.legacy.rules import adjust as local_adjust


        def direct(shape: object) -> int:
            return local_adjust(shape)


        def via_alias(shape: object) -> int:
            return rules.adjust(shape)


        def via_full() -> int:
            return app.core.legacy.state.read_count()


        def late(shape: object) -> int:
            from app.core.legacy.rules import adjust as _adjust

            return _adjust(shape)


        def shadow(module: object) -> object:
            return module._adjust  # Parameter, kein Modul: bleibt


        def by_name() -> object:
            return getattr(state, "bump")


        def store() -> None:
            state.COUNT = 5
    ''',
    "tools/check_legacy.py": '''
        """Ein Werkzeug mit Kopf- und spätem Import."""

        from __future__ import annotations

        from app.core.legacy.state import read_count


        def show() -> int:
            return read_count()


        def late() -> object:
            from app.core.legacy import rules

            return rules.Rule
    ''',
    "tests/test_legacy.py": '''
        """Patches in allen Formen und ein Quelltextleser."""

        from __future__ import annotations

        from pathlib import Path
        from unittest import mock
        from unittest.mock import patch

        from app.core.legacy import rules, state
        from app.core.legacy.rules import adjust as _adjust


        def test_paths(monkeypatch):
            monkeypatch.setattr("app.core.legacy.rules.adjust", lambda shape: 1)
            monkeypatch.setattr(state, "bump", lambda: None)
            with patch("app.core.legacy.state.read_count", return_value=3):
                pass
            with patch.object(rules, "adjust", lambda shape: 4):
                pass
            with mock.patch.object(state, "COUNT", 7):
                pass
            assert _adjust is not None


        @patch("app.core.legacy.state.bump")
        def test_decorated(bump_mock):
            assert bump_mock is not None


        def test_source():
            text = Path(state.__file__).read_text(encoding="utf-8")
            assert "def bump" in text
    ''',
}


# ------------------------------------------------------------------------------ copies

LAZY = '''
    """Träge Pakete wie ``app.core.lazy``: Ein eingetragener Name gewinnt vor dem Untermodul."""

    from __future__ import annotations

    import importlib
    import sys
    from types import ModuleType
    from typing import Any


    def install(package: str, exports: dict[str, tuple[str, str]]) -> None:
        module = sys.modules[package]

        class LazyPackage(ModuleType):
            def __getattribute__(self, name: str) -> Any:
                if not name.startswith("_"):
                    entry = exports.get(name)
                    if entry is not None:
                        submodule, attribute = entry
                        loaded = importlib.import_module(f"{package}.{submodule}")
                        return getattr(loaded, attribute)
                return ModuleType.__getattribute__(self, name)

        module.__class__ = LazyPackage
'''

#: Originale in ``engine`` und hinter einem trägen Export, Halter mit Kopfkopien als Import (mit
#: und ohne ``as``), als Zuweisung und als Kopie einer Kopie, Patches auf Kopien in allen Formen.
COPIES_OLD: dict[str, str] = BASE | {
    "app/core/bootstrap.py": '''
        """Lädt die Module mit Operationen in fester Reihenfolge."""

        from __future__ import annotations

        import importlib

        _OPERATION_MODULES = (
            "app.core.engine",
            "app.core.other",
        )


        def load_operations() -> None:
            for name in _OPERATION_MODULES:
                importlib.import_module(name)
    ''',
    "app/core/lazy.py": LAZY,
    "app/core/engine.py": '''
        """Rechenkern der Attrappe: die Originale."""

        from __future__ import annotations

        from app.core.registry import register

        LIMIT = 3


        @register("compute", check="value")
        def compute(value: int) -> int:
            return value + 1


        def scale(value: int) -> int:
            return value * 2


        class Settings:
            factor = 3


        def direct(value: int) -> int:
            return compute(value)
    ''',
    "app/core/kit/__init__.py": '''
        """Ein träges Paket: ``measure`` heißt wie sein Untermodul."""

        from app.core.lazy import install

        _EXPORTS = {"measure": ("measure", "measure")}

        install(__name__, _EXPORTS)
    ''',
    "app/core/kit/measure.py": '''
        """Das Original hinter dem trägen Export."""


        def measure(text: str) -> int:
            return len(text)
    ''',
    "app/core/consumer.py": '''
        """Halter mit Kopfkopien in allen Formen."""

        from __future__ import annotations

        from app.core.engine import LIMIT, Settings, scale
        from app.core.engine import compute as operation
        from app.core.kit import measure

        TABLE = {"op": operation}


        def read(value: int) -> int:
            return operation(value) + scale(value)


        def settings() -> Settings:
            return Settings()


        def shadow(operation: object) -> object:
            return operation


        def late(value: int) -> int:
            from app.core.engine import compute

            return compute(value)


        def size(text: str) -> int:
            return measure(text)


        def typed(value: "Settings") -> int:
            return value.factor


        def limit() -> int:
            return LIMIT
    ''',
    "app/core/relay.py": '''
        """Eine Kopie der Kopie."""

        from app.core.consumer import operation


        def relay(value: int) -> int:
            return operation(value)
    ''',
    "tools/engine_tool.py": '''
        """Ein Werkzeug mit einer Kopie als Zuweisung."""

        from app.core import engine

        operation = engine.compute


        def read(value: int) -> int:
            return operation(value)
    ''',
    "tests/test_engine.py": '''
        """Patches auf Kopien und Originale."""

        import importlib
        from unittest.mock import patch

        from app.core import consumer, relay
        from app.core.consumer import operation


        def test_copy(monkeypatch):
            monkeypatch.setattr(consumer, "operation", lambda value: 0)
            monkeypatch.setattr("app.core.relay.operation", lambda value: 0)
            with patch.object(consumer, "scale", lambda value: 0):
                pass
            monkeypatch.setattr("app.core.engine.compute", lambda value: 5)
            monkeypatch.setattr("tools.engine_tool.operation", lambda value: 6)
            assert operation is not None
            assert relay is not None


        def test_late(monkeypatch):
            holder = importlib.import_module("app.core.consumer")
            monkeypatch.setattr(holder, "Settings", object)
            assert holder.LIMIT == 3
    ''',
}

COPIES_CUT = """\
schema_version = 1
id = "engine-copies"
mode = "copies"

[[bindings]]
module = "app.core.engine"
name = "compute"

[[bindings]]
module = "app.core.engine"
name = "scale"

[[bindings]]
module = "app.core.engine"
name = "Settings"

[[bindings]]
module = "app.core.kit.measure"
name = "measure"
"""

#: Der Sollbaum nach dem Schnitt im Modus ``copies``, von Hand geschrieben.
COPIES_NEW: dict[str, str | None] = {
    "app/core/consumer.py": '''
        """Halter mit Kopfkopien in allen Formen."""

        from __future__ import annotations

        from app.core import engine, kit
        from app.core.engine import LIMIT

        TABLE = {"op": engine.compute}


        def read(value: int) -> int:
            return engine.compute(value) + engine.scale(value)


        def settings() -> engine.Settings:
            return engine.Settings()


        def shadow(operation: object) -> object:
            return operation


        def late(value: int) -> int:
            from app.core.engine import compute

            return compute(value)


        def size(text: str) -> int:
            return kit.measure(text)


        def typed(value: "engine.Settings") -> int:
            return value.factor


        def limit() -> int:
            return LIMIT
    ''',
    "app/core/relay.py": '''
        """Eine Kopie der Kopie."""

        from app.core import engine


        def relay(value: int) -> int:
            return engine.compute(value)
    ''',
    "tools/engine_tool.py": '''
        """Ein Werkzeug mit einer Kopie als Zuweisung."""

        from app.core import engine


        def read(value: int) -> int:
            return engine.compute(value)
    ''',
    "tests/test_engine.py": '''
        """Patches auf Kopien und Originale."""

        import importlib
        from unittest.mock import patch

        from app.core import engine, relay
        from app.core.engine import compute as operation


        def test_copy(monkeypatch):
            monkeypatch.setattr(engine, "compute", lambda value: 0)
            monkeypatch.setattr("app.core.engine.compute", lambda value: 0)
            with patch.object(engine, "scale", lambda value: 0):
                pass
            monkeypatch.setattr("app.core.engine.compute", lambda value: 5)
            monkeypatch.setattr("app.core.engine.compute", lambda value: 6)
            assert operation is not None
            assert relay is not None


        def test_late(monkeypatch):
            holder = importlib.import_module("app.core.consumer")
            from app.core import engine

            monkeypatch.setattr(engine, "Settings", object)
            assert holder.LIMIT == 3
    ''',
}


# --------------------------------------------------------------------------- Werkzeuge


def text_of(content: str) -> str:
    """Ein Dateiinhalt der Tabellen oben: eingerückt notiert, ohne führende Leerzeile."""
    if not content.strip():
        return content
    return textwrap.dedent(content).lstrip("\n")


def write_tree(root: Path, files: dict[str, str]) -> Path:
    """Schreibt einen Baum nach ``root`` (UTF-8, ``\\n``) und gibt ``root`` zurück."""
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text_of(content).encode("utf-8"))
    return root


def changed_tree(files: dict[str, str], changes: dict[str, str | None]) -> dict[str, str]:
    """Der Baum ``files`` mit ``changes`` (``None`` entfernt eine Datei)."""
    result = dict(files)
    for relative, content in changes.items():
        if content is None:
            result.pop(relative, None)
        else:
            result[relative] = content
    return result


def edit(files: dict[str, str], path: str, old: str, new: str, count: int = 1) -> dict[str, str]:
    """Eine Kopie von ``files`` mit genau ``count`` Ersetzungen in ``path`` — für Mutanten.
    Fehlt die Stelle, ist der Mutant falsch gebaut, nicht der Beweis grün."""
    text = text_of(files[path])
    assert text.count(old) == count, f"{path}: {old!r} steht {text.count(old)}-mal"
    return files | {path: text.replace(old, new)}


def tree_bytes(root: Path) -> dict[str, bytes]:
    """Jede Datei unter ``root`` (ohne ``__pycache__``) mit ihrem Inhalt."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }
