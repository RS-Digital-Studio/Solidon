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

#: Ruff-Einstellung der Attrappe: Zeilenlänge und Importordnung wie im Projekt, die Regeln
#: ausdrücklich nur ``E``, ``F`` und ``I`` — die Attrappe trägt mit Absicht Formen, die strengere
#: Regeln des Projekts anmahnten (``getattr`` mit festem Namen, Annotation als Zeichenkette).
#: Das Werkzeug formatiert damit und prüft sein Ergebnis gegen genau diese Regeln.
PYPROJECT = """\
[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I"]

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


# ------------------------------------------------------------------- Modulmodus, Randformen

FORMS_TEST = '''
    """Leser in weiteren Formen."""

    from __future__ import annotations

    import importlib
    from typing import TYPE_CHECKING

    import app.core.legacy as lg

    if TYPE_CHECKING:
        from app.core.legacy import Rule

    EVALUATION = importlib.import_module("app.core.legacy")
    KNOWN = ("app.core.legacy",)


    def test_import_module(monkeypatch):
        legacy_module = importlib.import_module("app.core.legacy")
        monkeypatch.setattr(legacy_module, "bump", lambda: None)
        assert legacy_module.read_count() == 0


    def test_inline():
        assert importlib.import_module("app.core.legacy").read_count() == 0


    def test_alias(monkeypatch):
        monkeypatch.setattr(lg.Rule, "apply", lambda self, hidden: 0)
        monkeypatch.setattr("app.core.legacy.Rule.apply", lambda self, hidden: 1)
        assert hasattr(lg, "bump")


    def test_module_level():
        assert EVALUATION.COUNT == 0


    def typed(rule: Rule) -> Rule:
        return rule
'''

FORMS_TEST_NEW = '''
    """Leser in weiteren Formen."""

    from __future__ import annotations

    import importlib
    from typing import TYPE_CHECKING

    from app.core.legacy import rules, state

    if TYPE_CHECKING:
        from app.core.legacy.rules import Rule

    KNOWN = ("app.core.legacy",)


    def test_import_module(monkeypatch):
        from app.core.legacy import state

        monkeypatch.setattr(state, "bump", lambda: None)
        assert state.read_count() == 0


    def test_inline():
        assert importlib.import_module("app.core.legacy.state").read_count() == 0


    def test_alias(monkeypatch):
        monkeypatch.setattr(rules.Rule, "apply", lambda self, hidden: 0)
        monkeypatch.setattr("app.core.legacy.rules.Rule.apply", lambda self, hidden: 1)
        assert hasattr(state, "bump")


    def test_module_level():
        assert state.COUNT == 0


    def typed(rule: Rule) -> Rule:
        return rule
'''

OVERLOADS = '''

    @overload
    def pick(value: int) -> int: ...


    @overload
    def pick(value: str) -> str: ...


    def pick(value: int | str) -> int | str:
        """Gibt den Wert zurück — überladen."""
        return value


    def bounded(*, low: int, high: int = 9) -> dict[str, int]:
        return {**{"low": low}, "high": high}
'''


def _forms() -> tuple[dict[str, str], str, dict[str, str]]:
    """Die Attrappe des Modulmodus mit Randformen: Leser über ``importlib.import_module`` (in
    einer Funktion, auf Modulebene, als Ausdruck), ``import … as``, ``TYPE_CHECKING``, ein
    Patch auf eine Klasse über den Pfad, ``hasattr``, eine erklärt bleibende Zeichenkette und eine
    überladene Funktion in der Quelle."""
    source = "app/core/legacy.py"
    state = "app/core/legacy/state.py"
    old = MODULE_OLD | {"tests/test_forms.py": FORMS_TEST}
    old = edit(
        old,
        source,
        "from typing import TYPE_CHECKING\n",
        "from typing import TYPE_CHECKING, overload\n",
    )
    old = edit(
        old,
        source,
        "def read_count() -> int:\n    return COUNT\n",
        "def read_count() -> int:\n    return COUNT\n" + textwrap.dedent(OVERLOADS),
    )
    cut = MODULE_CUT.replace(
        '"bump", "read_count"]', '"bump", "read_count", "pick", "bounded"]'
    ) + (
        '\n[[name_lists]]\npath = "tests/test_forms.py"\nvalue = "app.core.legacy"\n'
        'to = ["app.core.legacy"]\n'
    )
    new = changed_tree(MODULE_OLD, MODULE_NEW) | {"tests/test_forms.py": FORMS_TEST_NEW}
    new = edit(new, state, "import logging\n", "import logging\nfrom typing import overload\n")
    new = edit(
        new,
        state,
        "def read_count() -> int:\n    return COUNT\n",
        "def read_count() -> int:\n    return COUNT\n" + textwrap.dedent(OVERLOADS),
    )
    return old, cut, new


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


        def merged(*, value: int, extra: int = 1) -> dict[str, object]:
            return {**TABLE, "value": scale(value) + extra}


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


        def merged(*, value: int, extra: int = 1) -> dict[str, object]:
            return {**TABLE, "value": engine.scale(value) + extra}


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


# --------------------------------------------------------------------------- Komponente

#: Ein Wirt ``Board`` (``QObject``) mit Sitzung, einer Komponente ``Area`` im Gerüst (schwache
#: ``_host``/``_parent``, ``release``) und Lesern in ``app/``, ``tools/`` und ``tests/``. Die
#: verschobenen Rümpfe tragen jede Rolle der Ersetzungsliste aus Konzept 3.3.
COMPONENT_OLD: dict[str, str] = BASE | {
    "app/core/bootstrap.py": '''
        """Lädt die Module mit Operationen in fester Reihenfolge."""

        from __future__ import annotations

        import importlib

        _OPERATION_MODULES = ("app.core.other",)


        def load_operations() -> None:
            for name in _OPERATION_MODULES:
                importlib.import_module(name)
    ''',
    "app/ui/__init__.py": '"""Oberfläche der Attrappe."""\n',
    "app/ui/leash.py": '''
        """Besitzer von Arbeitern und Slots, wie in der Anwendung."""

        from __future__ import annotations

        from collections.abc import Callable


        class WorkerLeash:
            def __init__(self, owner: object) -> None:
                self.owner = owner


        def weak_slot(owner: object, method: Callable[..., object]) -> Callable[..., object]:
            return method
    ''',
    "app/ui/session.py": '''
        """Die Sitzung der Attrappe: meldet Änderungen."""

        from PySide6.QtCore import QObject, Signal


        class Session(QObject):
            changed = Signal()
    ''',
    "app/ui/flow.py": '''
        """Ein Fluss, der seinen Wirt kennt (wie ``DrawFlow``)."""


        class Flow:
            def __init__(self, host: object) -> None:
                self.host = host

            def start(self) -> None:
                self.started = True
    ''',
    "app/ui/toast.py": '''
        """Eine Meldung mit eigenem ``notify`` — derselbe Name wie am Wirt."""


        class Toast:
            def notify(self, menu: object) -> None:
                self.last = menu
    ''',
    "app/ui/board_area.py": '''
        """Der Bedienbereich des Bretts als Komponente."""

        from __future__ import annotations

        import weakref
        from typing import TYPE_CHECKING, Protocol

        from PySide6.QtCore import QObject

        if TYPE_CHECKING:
            from PySide6.QtCore import SignalInstance

            from app.ui.session import Session


        class AreaHost(Protocol):
            """Was der Bereich vom Wirt anspricht, erhoben aus seinen Methoden."""

            document: str
            session: Session

            @property
            def changed(self) -> SignalInstance: ...

            def statusBar(self) -> object: ...


        class Area(QObject):
            """Der Bedienbereich; hält Wirt und Elternteil schwach."""

            def __init__(self, host: AreaHost, parent: QObject) -> None:
                super().__init__(parent)
                self._host_ref = weakref.ref(host)
                self._parent_ref = weakref.ref(parent)

            @property
            def _host(self) -> AreaHost:
                host = self._host_ref()
                if host is None:
                    raise RuntimeError("Der Wirt des Bereichs ist fort")
                return host

            @property
            def _parent(self) -> QObject:
                parent = self._parent_ref()
                if parent is None:
                    raise RuntimeError("Der Elternteil des Bereichs ist fort")
                return parent

            def release(self) -> None:
                """Trennt, was der Bereich mit der Sitzung verbunden hat."""
                self._host.session.disconnect(self)
    ''',
    "app/ui/board.py": '''
        """Ein Wirt mit einem Bedienbereich, der Komponente wird."""

        from __future__ import annotations

        import weakref
        from typing import TYPE_CHECKING

        from PySide6.QtCore import QObject, QTimer, Signal
        from PySide6.QtWidgets import QMenu

        from app.ui.board_area import Area
        from app.ui.flow import Flow
        from app.ui.leash import WorkerLeash, weak_slot

        if TYPE_CHECKING:
            from app.ui.session import Session


        class Board(QObject):
            """Der Wirt: hält die Sitzung und den Bereich."""

            changed = Signal()

            def __init__(self, session: Session) -> None:
                super().__init__()
                self.session = session
                self.document = "Plan"
                self.area = Area(self, self)
                self.count = 0
                self.session.changed.connect(self._on_changed)

            def statusBar(self) -> object:
                return self.document

            # Kopfkommentar: gehört zu refresh und wandert mit.
            def refresh(self) -> int:
                """Zählt, baut ein Menü und meldet sich – Umlaute: äöüß."""
                self.count += 1
                menu = QMenu(self)
                self._leash = WorkerLeash(self)
                timer = QTimer(self)
                self.document = self.document.strip()
                self.findChild(QObject)
                self.statusBar()
                weak_slot(self, self.notify)
                ref = weakref.ref(self)
                self.session.installEventFilter(self)

                def inner(self: object) -> object:
                    return self

                Board.notify(self, menu)
                alive = ref() is not None
                return self.count + len(str(timer)) + int(alive) + len(str(inner(menu)))

            def notify(self, menu: object) -> None:
                self.changed.emit()

            def bump(self) -> None:
                self.count += 1

            def attach(self) -> None:
                self.session.changed.connect(self.bump)
                self._flow = Flow(self)
                Flow(self).start()

            def eventFilter(self, watched: QObject, event: object) -> bool:
                return False

            def _on_changed(self) -> None:
                self.bump()

            def release(self) -> None:
                self.area.release()
                self.session.disconnect(self)
    ''',
    "app/ui/board_tools.py": '''
        """Werkzeuge am Brett."""

        from __future__ import annotations

        from app.ui.board import Board
        from app.ui.toast import Toast


        def poke(window: Board) -> int:
            window.count = 2
            return window.refresh()


        def by_class(window: Board) -> int:
            return Board.refresh(window)


        def shout(toast: Toast) -> None:
            toast.notify("x")


        def ring(window: Board) -> None:
            window.notify("y")
    ''',
    "tools/board_probe.py": '''
        """Ein Werkzeug, das das Brett befragt."""


        def probe(window: object) -> object:
            return getattr(window, "refresh")
    ''',
    "tests/test_board.py": '''
        """Patches am Brett."""

        from unittest import mock

        from app.ui import board
        from app.ui.board import Board
        from app.ui.session import Session


        def test_refresh(monkeypatch):
            window = board.Board(Session())
            monkeypatch.setattr(window, "bump", lambda: None)
            with mock.patch.object(Board, "refresh", return_value=1):
                pass
            with mock.patch("app.ui.board.Board.bump"):
                pass
            assert window.count == 0
    ''',
}

COMPONENT_CUT = """\
schema_version = 1
id = "board-area"
mode = "component"
source = "app/ui/board.py"
host = "Board"
component = "app.ui.board_area:Area"
host_attribute = "area"
host_protocol = "AreaHost"
methods = ["refresh", "notify", "bump", "attach", "eventFilter"]
own_attributes = ["count", "_leash", "_flow"]
host_members = ["document", "session", "changed", "statusBar"]
parent_members = ["findChild"]

[[self_roles]]
scope = "Board.refresh"
call = "QMenu"
argument = 0
role = "qt_parent"

[[self_roles]]
scope = "Board.attach"
call = "Flow"
argument = 0
role = "flow_host"

[[accesses]]
path = "tools/board_probe.py"
scope = "probe"
member = "refresh"
decision = "component"
"""

#: Der Sollbaum nach dem Schnitt der Komponente, von Hand geschrieben.
COMPONENT_NEW: dict[str, str | None] = {
    "app/ui/board_area.py": '''
        """Der Bedienbereich des Bretts als Komponente."""

        from __future__ import annotations

        import weakref
        from typing import TYPE_CHECKING, Protocol

        from PySide6.QtCore import QObject, QTimer
        from PySide6.QtWidgets import QMenu

        from app.ui.flow import Flow
        from app.ui.leash import WorkerLeash, weak_slot

        if TYPE_CHECKING:
            from PySide6.QtCore import SignalInstance

            from app.ui.session import Session


        class AreaHost(Protocol):
            """Was der Bereich vom Wirt anspricht, erhoben aus seinen Methoden."""

            document: str
            session: Session

            @property
            def changed(self) -> SignalInstance: ...

            def statusBar(self) -> object: ...


        class Area(QObject):
            """Der Bedienbereich; hält Wirt und Elternteil schwach."""

            def __init__(self, host: AreaHost, parent: QObject) -> None:
                super().__init__(parent)
                self._host_ref = weakref.ref(host)
                self._parent_ref = weakref.ref(parent)

            @property
            def _host(self) -> AreaHost:
                host = self._host_ref()
                if host is None:
                    raise RuntimeError("Der Wirt des Bereichs ist fort")
                return host

            @property
            def _parent(self) -> QObject:
                parent = self._parent_ref()
                if parent is None:
                    raise RuntimeError("Der Elternteil des Bereichs ist fort")
                return parent

            def release(self) -> None:
                """Trennt, was der Bereich mit der Sitzung verbunden hat."""
                self._host.session.disconnect(self)

            # Kopfkommentar: gehört zu refresh und wandert mit.
            def refresh(self) -> int:
                """Zählt, baut ein Menü und meldet sich – Umlaute: äöüß."""
                self.count += 1
                menu = QMenu(self._parent)
                self._leash = WorkerLeash(self)
                timer = QTimer(self)
                self._host.document = self._host.document.strip()
                self._parent.findChild(QObject)
                self._host.statusBar()
                weak_slot(self, self.notify)
                ref = weakref.ref(self)
                self._host.session.installEventFilter(self)

                def inner(self: object) -> object:
                    return self

                Area.notify(self, menu)
                alive = ref() is not None
                return self.count + len(str(timer)) + int(alive) + len(str(inner(menu)))

            def notify(self, menu: object) -> None:
                self._host.changed.emit()

            def bump(self) -> None:
                self.count += 1

            def attach(self) -> None:
                self._host.session.changed.connect(self.bump)
                self._flow = Flow(self)
                Flow(self._host).start()

            def eventFilter(self, watched: QObject, event: object) -> bool:
                return False
    ''',
    "app/ui/board.py": '''
        """Ein Wirt mit einem Bedienbereich, der Komponente wird."""

        from __future__ import annotations

        from typing import TYPE_CHECKING

        from PySide6.QtCore import QObject, Signal

        from app.ui.board_area import Area

        if TYPE_CHECKING:
            from app.ui.session import Session


        class Board(QObject):
            """Der Wirt: hält die Sitzung und den Bereich."""

            changed = Signal()

            def __init__(self, session: Session) -> None:
                super().__init__()
                self.session = session
                self.document = "Plan"
                self.area = Area(self, self)
                self.area.count = 0
                self.session.changed.connect(self._on_changed)

            def statusBar(self) -> object:
                return self.document

            def _on_changed(self) -> None:
                self.area.bump()

            def release(self) -> None:
                self.area.release()
                self.session.disconnect(self)
    ''',
    "app/ui/board_tools.py": '''
        """Werkzeuge am Brett."""

        from __future__ import annotations

        from app.ui.board import Board
        from app.ui.board_area import Area
        from app.ui.toast import Toast


        def poke(window: Board) -> int:
            window.area.count = 2
            return window.area.refresh()


        def by_class(window: Board) -> int:
            return Area.refresh(window.area)


        def shout(toast: Toast) -> None:
            toast.notify("x")


        def ring(window: Board) -> None:
            window.area.notify("y")
    ''',
    "tools/board_probe.py": '''
        """Ein Werkzeug, das das Brett befragt."""


        def probe(window: object) -> object:
            return getattr(window.area, "refresh")
    ''',
    "tests/test_board.py": '''
        """Patches am Brett."""

        from unittest import mock

        from app.ui import board
        from app.ui.board_area import Area
        from app.ui.session import Session


        def test_refresh(monkeypatch):
            window = board.Board(Session())
            monkeypatch.setattr(window.area, "bump", lambda: None)
            with mock.patch.object(Area, "refresh", return_value=1):
                pass
            with mock.patch("app.ui.board_area.Area.bump"):
                pass
            assert window.area.count == 0
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


FORMS_OLD, FORMS_CUT, FORMS_NEW = _forms()
