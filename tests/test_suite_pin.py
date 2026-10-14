"""W6 f: Der Lebensdauer-Pin der Suite löst jede Klasse auf und greift nach dem Import.

**Warum es diese Datei gibt** (Konzept Codestruktur 4.1, W6; Fund CS-10).
``tests/conftest.py`` hält Hauptfenster, Viewport und elternlose Widgets mit
Arbeitern bis zum geordneten Abbau ihres Tests; ohne diesen Pin stirbt ein
Fenster mit seiner letzten Referenz mitten im Lauf und reißt ihn mit
(0xc0000374). Gepinnt wird beim Import der Module aus ``UI_PINS``. Der Pin fragte
früher jedes Modul nach ``MainWindow`` und ``Viewport`` und übersprang still, was
fehlte — ein Schnitt, der ``MainWindow`` in ein neues Modul zieht, hätte den Pin
abgeschaltet, ohne dass ein Test rot wird.

Geprüft wird hier:

- jede Klasse aus ``UI_PINS`` steht in genau dem Modul, das der Eintrag nennt;
- Fenster, Viewport und Leine sind nach dem Import gepinnt;
- der Import-Haken pinnt ein Modul bei seinem ersten Import, und ein Modul ohne
  seine Klasse bricht den Import ab (die Mutation, die vorher still grün war);
- ein noch nicht geladenes Modul hat nichts zu pinnen und bleibt ungeladen;
- ``tests.conftest`` ist dasselbe Modul wie die von pytest geladene ``conftest``
  — sonst brächte jeder solche Import einen zweiten Haken mit eigener Pinliste.
"""

from __future__ import annotations

import gc
import importlib
import os
import sys
import textwrap
import weakref
from pathlib import Path
from types import ModuleType

import pytest

CONFTEST = Path(__file__).resolve().parent / "conftest.py"

#: Die Klassen, die der Pin halten muss: Fenster und Viewport nennt das Konzept
#: (W6 f), die Leine hält elternlose Widgets mit Arbeitern.
PINNED_CLASSES = frozenset({"MainWindow", "Viewport", "WorkerLeash"})


@pytest.fixture
def suite(request: pytest.FixtureRequest) -> ModuleType:
    """Die ``tests/conftest.py``, die pytest geladen hat — über den Plugin-Verwalter
    gesucht, damit diese Datei sie nie selbst ein zweites Mal ausführt."""
    loaded = [
        plugin
        for plugin in request.config.pluginmanager.get_plugins()
        if isinstance(plugin, ModuleType)
        and Path(getattr(plugin, "__file__", None) or ".").resolve() == CONFTEST
    ]
    assert len(loaded) == 1, loaded
    return loaded[0]


def _fake_module(folder: Path, name: str, source: str) -> None:
    (folder / f"{name}.py").write_text(textwrap.dedent(source), encoding="utf-8")
    importlib.invalidate_caches()


def test_every_pinned_class_is_defined_in_the_module_its_entry_names(suite: ModuleType) -> None:
    """Eindeutig und nicht leer: jede Klasse einmal, an ihrem Definitionsmodul.

    Zieht ein Schnitt ``MainWindow`` nach ``app/ui/main_window/window.py``, ist
    dieser Test rot, bis der Eintrag mitzieht — und nicht erst der native Abriss
    eines ungepinnten Fensters.
    """
    pins = suite.UI_PINS
    names = [class_name for class_name, _pin in pins.values()]
    assert sorted(names) == sorted(PINNED_CLASSES), pins
    for module_name, (class_name, _pin) in pins.items():
        pinned = getattr(importlib.import_module(module_name), class_name)
        assert pinned.__module__ == module_name, (module_name, pinned.__module__)


def test_window_viewport_and_leash_are_pinned_after_their_import() -> None:
    """Die Zusage selbst, ohne ``UI_PINS`` zu lesen: Wer die Zuordnung leert, ist rot."""
    from app.ui.leash import WorkerLeash
    from app.ui.main_window import MainWindow
    from app.ui.viewport import Viewport

    assert getattr(MainWindow, "_suite_pinned", False)
    assert getattr(Viewport, "_suite_pinned", False)
    assert getattr(WorkerLeash, "_suite_owner_pinned", False)


def test_the_import_hook_pins_a_module_on_its_first_import(
    suite: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Haken greift beim Import selbst, nicht erst beim nächsten Teststart —
    und ein Exemplar lebt danach bis zum Abbau des Tests, ohne eigene Referenz."""
    name = "suite_pin_probe_window"
    _fake_module(
        tmp_path,
        name,
        """
        class Window:
            def __init__(self):
                self.built = True
        """,
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(suite.UI_PINS, name, ("Window", suite.UI_PINS["app.ui.main_window"][1]))
    assert name not in sys.modules
    try:
        module = importlib.import_module(name)
        assert module.Window._suite_pinned
        held = weakref.ref(module.Window())
        gc.collect()
        assert held() is not None, "der Pin hält das Exemplar bis zum Testabbau"
        assert held().built
    finally:
        sys.modules.pop(name, None)


def test_a_module_without_its_class_stops_the_import(
    suite: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Mutation: Das Modul hat seine Klasse verloren. Bis CS-10 sprang der Pin
    still darüber, jetzt endet der Import mit einem Satz, der sagt, was zu tun ist."""
    name = "suite_pin_probe_empty"
    _fake_module(tmp_path, name, "class SomethingElse:\n    pass\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(suite.UI_PINS, name, ("Window", suite.UI_PINS["app.ui.main_window"][1]))
    try:
        with pytest.raises(LookupError, match=r"definiert die Klasse Window nicht mehr.*UI_PINS"):
            importlib.import_module(name)
        assert name not in sys.modules, "ein abgebrochener Import hinterlässt kein Modul"
    finally:
        sys.modules.pop(name, None)


def test_a_module_not_loaded_yet_has_nothing_to_pin(
    suite: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Griff am Teststart pinnt nur, was schon geladen ist — ein ungeladenes Modul
    ist kein Fehler und wird nicht geladen; ein geladenes ohne seine Klasse schon."""
    absent = "suite_pin_probe_never_loaded"
    instance_pin = suite.UI_PINS["app.ui.main_window"][1]
    monkeypatch.setitem(suite.UI_PINS, absent, ("Window", instance_pin))
    assert absent not in sys.modules

    suite.pin_loaded_ui_modules()

    assert absent not in sys.modules

    loaded = "suite_pin_probe_loaded_empty"
    monkeypatch.setitem(suite.UI_PINS, loaded, ("Window", instance_pin))
    monkeypatch.setitem(sys.modules, loaded, ModuleType(loaded))
    with pytest.raises(LookupError, match="definiert die Klasse Window nicht mehr"):
        suite.pin_loaded_ui_modules()


def test_tests_conftest_is_the_conftest_pytest_loaded(suite: ModuleType) -> None:
    """``from tests.conftest import …`` (``test_packaging.py``, ``test_toolchain.py``)
    führte die Datei ein zweites Mal aus: zweiter Import-Haken vorn in
    ``sys.meta_path``, dessen Pinliste kein Abbau leert, und die Profilvariablen auf
    einem neuen Ordner. Die erste Zusicherung steht vorn, damit ein Rückfall hier
    keine zweite Ausführung auslöst."""
    from app.core.paths import PROFILE_VARIABLES

    assert sys.modules.get("tests.conftest") is suite
    hooks = list(sys.meta_path)
    profile = {variable: os.environ.get(variable) for variable in PROFILE_VARIABLES}

    from tests.conftest import REQUIRE_SLICERS

    assert REQUIRE_SLICERS == suite.REQUIRE_SLICERS
    assert importlib.import_module("tests.conftest") is suite
    assert sys.meta_path == hooks, "die conftest lief ein zweites Mal"
    assert {variable: os.environ.get(variable) for variable in PROFILE_VARIABLES} == profile
