"""Kein Qt unterhalb von ``app.ui`` (AGENTS.md Regel 1, Bauplan §8) — und der
Kern für sich importierbar.

Drei Prüfungen für die Qt-Frage, denn jede allein ist zu schwach: jedes
Kernmodul zu importieren und nachzusehen, was in ``sys.modules`` gelandet ist,
fängt Laufzeit-Importe; die Quellen zu lesen fängt die trägen in Funktionen.

Die vierte gilt einer anderen Frage, die lange niemand gestellt hat: ob jedes
Kernmodul auch **als erstes** geladen werden kann. „Alle zusammen laden" ist
schwächer, als es aussieht — ein Import-Kreis zwischen zwei Modulen fällt nicht
auf, solange das eine schon fertig ist, wenn das andere beginnt.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import subprocess
import sys
import textwrap
from pathlib import Path

import app.core

FORBIDDEN_ROOTS = ("PySide6", "PyQt5", "PyQt6", "PySide2", "app.ui")
CORE_DIR = Path(app.core.__file__).parent


def core_modules() -> list[str]:
    names = ["app.core"]
    for info in pkgutil.walk_packages(app.core.__path__, prefix="app.core."):
        names.append(info.name)
    return names


def core_sources() -> list[Path]:
    return sorted(CORE_DIR.rglob("*.py"))


def test_every_core_module_imports() -> None:
    for name in core_modules():
        importlib.import_module(name)


def test_every_core_module_imports_first() -> None:
    """Jedes Modul auch **als erstes** — sonst bleibt ein Kreis unsichtbar.

    Der Test darüber lädt die Kernmodule der Reihe nach in einem Prozess. Was
    er damit prüft, ist „alle zusammen laden", und das ist schwächer, als es
    aussieht: Ein Kreis zwischen zwei Modulen fällt nicht auf, solange das
    eine schon fertig geladen ist, wenn das andere beginnt.

    Genau so entkam einer. ``geom.pose`` braucht den Ausdrucksauswerter und
    importiert ``scene.expressions``; Python lädt dabei das ganze Paket
    ``scene``, dessen ``__init__`` ``scene.evaluate`` zieht — und das
    importierte ``geom.pose``. In der Suite lief das durch, weil ``scene``
    immer vorher dran war. Wer ``app.core.geom.pose`` als Erstes lud — ein
    Skript, ein Werkzeug, eine Kommandozeile — bekam einen ``ImportError``.

    **Im Subprozess, und das ist keine Bequemlichkeit.** Der erste Anlauf lief
    hier und räumte zwischen den Modulen alles unter ``app.`` aus
    ``sys.modules``. Das trifft ``app.ui`` mit — und in einem Lauf, der
    danach noch Oberflächentests fährt, lädt Qt seine Widgetklassen ein
    zweites Mal. Zwei Klassenobjekte für dasselbe Widget sind genau die Sorte
    Zugriffsverletzung ohne Zeile, die in dieser Suite ohnehin schon gesucht
    wird; ein Test, der eine Absturzquelle einbaut, um eine Fehlerklasse zu
    finden, hat sich nicht gelohnt.

    Der Nachbar unten fährt aus demselben Grund einen eigenen Prozess. Innen
    genügt dann das Ausräumen von ``sys.modules``, weil dort nie Qt lag: 151
    Module in rund neun Sekunden statt in einer Minute mit einem Prozess je
    Modul.
    """
    script = textwrap.dedent(
        """
        import importlib, pkgutil, sys
        import app.core

        names = ['app.core'] + [
            info.name
            for info in pkgutil.walk_packages(app.core.__path__, prefix='app.core.')
        ]
        broken = []
        for name in names:
            for loaded in [entry for entry in sys.modules if entry.startswith('app.')]:
                del sys.modules[loaded]
            try:
                importlib.import_module(name)
            except Exception as problem:
                broken.append(f'{name}: {type(problem).__name__}: {problem}')
        print(len(names))
        print('; '.join(broken))
        """
    )
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
    )
    assert finished.returncode == 0, finished.stderr

    counted, _, broken = finished.stdout.partition("\n")
    assert int(counted) > 100, f"nur {counted} Module gesehen — der Lauf hat nichts geprüft"
    assert not broken.strip(), f"als erstes geladen bricht: {broken.strip()}"


def test_importing_core_pulls_in_no_surface_dependency() -> None:
    """In einem frischen Prozess ausgeführt: in diesem hier haben die
    Oberflächentests Qt längst importiert.
    """
    script = (
        "import importlib, pkgutil, sys\n"
        "import app.core\n"
        "for info in pkgutil.walk_packages(app.core.__path__, prefix='app.core.'):\n"
        "    importlib.import_module(info.name)\n"
        f"forbidden = {FORBIDDEN_ROOTS!r}\n"
        "loaded = sorted(m for m in sys.modules if m.split('.')[0] in forbidden)\n"
        "print(','.join(loaded))\n"
    )
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    assert not finished.stdout.strip(), f"core pulled in a surface dependency: {finished.stdout}"


def test_loading_the_registry_defers_geometry_libraries() -> None:
    """Das vollständige Register kostet noch keinen Geometriekern.

    ``load_operations`` läuft vor dem bedienbaren Fenster, weil Menü, Dialog,
    Kommandozeile und Agent dieselben Deklarationen brauchen (§10). Früher zog
    dieser reine Katalogimport schon trimesh, scipy und networkx herein: warm
    rund 800 Millisekunden, kalt mehrere Sekunden. Die erste wirkliche
    Geometrie darf sie laden; die 86 Deklarationen dürfen es nicht.
    """
    script = textwrap.dedent(
        """
        import sys
        from app.core.bootstrap import load_operations
        from app.core.registry import REGISTRY

        load_operations()
        assert len(REGISTRY.all()) >= 80, 'das Register wurde nicht vollständig geladen'
        heavy = sorted(name for name in ('trimesh', 'scipy', 'networkx') if name in sys.modules)
        print(','.join(heavy))
        """
    )
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    assert not finished.stdout.strip(), (
        "das Operationsregister lud schon schwere Geometriebibliotheken: " + finished.stdout
    )


def test_core_sources_never_reference_the_surface() -> None:
    offenders: list[str] = []
    for path in core_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                if any(module == root or module.startswith(f"{root}.") for root in FORBIDDEN_ROOTS):
                    offenders.append(f"{path.name}:{node.lineno} imports {module}")
    assert not offenders, "\n".join(offenders)


def test_two_threads_may_import_the_same_package() -> None:
    """Zwei Threads dürfen gleichzeitig an verschiedenen Stellen einsteigen.

    Am 23.08.2026 durften sie das nicht: ``from app.core.scene import History``
    und ``from app.core.scene.history import History`` nebeneinander gaben
    **fünf von fünf Läufen** einen ``_DeadlockError``. Der Grund ist eine
    Reihenfolge und kein Kreis — der eine Weg nimmt erst den Lock auf das
    **Paket** und dann den auf das **Untermodul**, der andere umgekehrt.

    **Geprüft wird jedes Kernpaket, dessen ``__init__`` etwas lädt**, und
    dieser Zuschnitt ist der eigentliche Ertrag: Der Punkt stand in der Roadmap
    als Einzelfall in ``scene``. Gemessen waren es **sieben** — ``scene``,
    ``registry``, ``sketch``, ``agent``, ``brep``, ``activation`` und
    ``knowledge.parts``. Die drei Pakete mit einer Zeile Docstring als
    ``__init__`` (``geom``, ``perceive``, ``knowledge``) waren sauber, und das
    ist der Unterschied. Ein Test nur auf ``scene`` hätte genau den einen Fall
    festgehalten, den jemand schon behoben hat.

    Sieben davon lösen ihre Namen jetzt erst beim Zugriff auf
    (:mod:`app.core.lazy`). Im Subprozess, weil die Module beim Start des Tests
    längst geladen wären und der Fall dann nicht mehr auftritt.
    """
    script = textwrap.dedent(
        """
        import importlib, pkgutil, sys, threading
        import app.core

        # **Alles Nachschlagen passiert hier, vor dem ersten Thread.** Der
        # erste Anlauf ließ den zweiten Thread das Paket selbst importieren,
        # um an seine Untermodule zu kommen -- damit war das Paket geladen,
        # bevor der Wettlauf begann, und der Test war grün an einem Paket, das
        # nachweislich deadlockt.
        packages = []
        for info in pkgutil.walk_packages(app.core.__path__, "app.core."):
            if not info.ispkg:
                continue
            module = importlib.import_module(info.name)
            # Nur Pakete, deren __init__ überhaupt etwas lädt -- ein Docstring
            # allein kann sich nicht verklemmen.
            names = [n for n in dir(module) if not n.startswith("_")]
            submodules = [m.name for m in pkgutil.iter_modules(module.__path__)]
            if names and submodules:
                packages.append((info.name, names[0], submodules))

        broken = []
        for name, target, submodules in packages:
            for stale in [m for m in sys.modules if m.startswith("app.")]:
                del sys.modules[stale]

            def through_package(name=name, target=target):
                try:
                    __import__(name, fromlist=[target])
                except BaseException as error:
                    broken.append(f"{name} (package): {type(error).__name__}: {error}")

            def through_submodule(name=name, submodules=submodules):
                try:
                    for submodule in submodules:
                        __import__(f"{name}.{submodule}")
                except BaseException as error:
                    broken.append(f"{name} (modules): {type(error).__name__}: {error}")

            first = threading.Thread(target=through_package)
            second = threading.Thread(target=through_submodule)
            first.start()
            second.start()
            first.join(timeout=60)
            second.join(timeout=60)
            if first.is_alive() or second.is_alive():
                broken.append(f"{name}: still running after 60 s")

        if not packages:
            broken.append("no packages examined -- this test would pass on anything")
        for line in broken:
            print(line)
        """
    )
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    assert not finished.stdout.strip(), (
        "two threads deadlocked while importing the same package:\n" + finished.stdout
    )


def test_parts_package_defers_registration_and_survives_parallel_imports() -> None:
    """§24-Registrierung gehört in den Bootstrap, nicht in den Paketimport.

    Der öffentliche ``PARTS``-Import bleibt der bequeme Bibliotheksvertrag und
    lädt die mitgelieferten Bausteine bei seinem ersten Zugriff. Ein bloßes
    ``import app.core.knowledge.parts`` bleibt dagegen frei von registrierenden
    Untermodulen. Der 50-fache Wettlauf hält genau die beiden früher
    verklemmten Wege gegeneinander.
    """
    script = textwrap.dedent(
        """
        import importlib, sys, threading

        shipped = (
            "fasteners",
            "mechanics",
            "mounting",
            "structure",
            "testbodies",
        )
        prefix = "app.core.knowledge.parts."

        import app.core.knowledge.parts as parts
        eager = sorted(name for name in sys.modules if name.startswith(prefix))
        assert not eager, eager

        broken = []
        for attempt in range(50):
            for stale in [name for name in sys.modules if name.startswith("app.")]:
                del sys.modules[stale]

            def through_package():
                try:
                    package = importlib.import_module("app.core.knowledge.parts")
                    assert package.PARTS.all()
                except BaseException as error:
                    broken.append(
                        f"{attempt} (package): {type(error).__name__}: {error}"
                    )

            def through_submodules():
                try:
                    for name in shipped:
                        importlib.import_module(f"app.core.knowledge.parts.{name}")
                except BaseException as error:
                    broken.append(
                        f"{attempt} (modules): {type(error).__name__}: {error}"
                    )

            first = threading.Thread(target=through_package)
            second = threading.Thread(target=through_submodules)
            first.start()
            second.start()
            first.join(timeout=10)
            second.join(timeout=10)
            if first.is_alive() or second.is_alive():
                broken.append(f"{attempt}: nach 10 s noch nicht beendet")
                break

        print("\\n".join(broken))
        """
    )
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
        timeout=90,
    )

    assert finished.returncode == 0, finished.stderr or finished.stdout
    assert not finished.stdout.strip(), finished.stdout


def test_public_part_version_helpers_load_only_the_default_registry() -> None:
    """§24.4-Helfer sehen den Bestand, ohne Test-Register zu beladen.

    Beide Prozesse greifen absichtlich nie auf ``PARTS`` zu. Damit beweist der
    erste, dass der öffentliche Helfer selbst die mitgelieferten Gruppen lädt;
    der zweite hält die Gegenrichtung: Ein ausdrücklich übergebenes Register
    bleibt vollständig isoliert und importiert keine Gruppe als Nebenwirkung.
    """
    default_script = textwrap.dedent(
        """
        import sys
        import app.core.knowledge.parts as parts

        prefix = "app.core.knowledge.parts."
        shipped = parts.changed_since({"screw_hole": "0"})
        missing = parts.missing_parts(
            {"screw_hole": "0", "not_installed": "1"}
        )

        assert shipped == ("screw_hole",), shipped
        assert missing == ("not_installed",), missing
        assert all(
            f"{prefix}{name}" in sys.modules
            for name in ("fasteners", "mechanics", "mounting", "structure", "testbodies")
        )
        """
    )
    explicit_script = textwrap.dedent(
        """
        import sys
        import app.core.knowledge.parts as parts

        registry = parts.PartRegistry()
        assert parts.changed_since({"screw_hole": "0"}, registry) == ()
        assert parts.missing_parts({"own_part": "1"}, registry) == ("own_part",)
        assert not any(
            f"app.core.knowledge.parts.{name}" in sys.modules
            for name in ("fasteners", "mechanics", "mounting", "structure", "testbodies")
        )
        """
    )

    for script in (default_script, explicit_script):
        finished = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=Path(app.core.__file__).parents[2],
            check=False,
        )
        assert finished.returncode == 0, finished.stderr or finished.stdout


def test_bootstrap_loads_shipped_parts_exactly_once() -> None:
    """Der Anwendungstakt lädt die fünf Bausteingruppen genau einmal."""
    script = textwrap.dedent(
        """
        import importlib, sys, typing

        loader = importlib.import_module("app.core.knowledge.parts.builtin")
        operations = importlib.import_module("app.core.knowledge.parts.ops")
        registry = importlib.import_module("app.core.knowledge.parts.registry")
        assert typing.get_type_hints(loader.load)["return"] is registry.PartRegistry
        original_load = loader.load
        original_register = operations.register_all
        calls = []

        def counted_load():
            calls.append("parts")
            return original_load()

        def counted_register():
            calls.append("ops")
            return original_register()

        loader.load = counted_load
        operations.register_all = counted_register
        from app.core.bootstrap import load_operations
        load_operations()
        load_operations()

        assert calls == ["parts", "ops"], calls
        assert loader.SHIPPED_MODULES == (
            "fasteners",
            "mechanics",
            "mounting",
            "structure",
            "testbodies",
        )
        assert all(
            f"app.core.knowledge.parts.{name}" in sys.modules
            for name in loader.SHIPPED_MODULES
        )
        from app.core.knowledge.parts import PARTS
        assert PARTS.all()
        """
    )
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
    )

    assert finished.returncode == 0, finished.stderr or finished.stdout


def test_parts_loader_recovers_from_a_partial_module_import() -> None:
    """Ein abgebrochener Dekoratorlauf darf das Register nicht vergiften.

    Python entfernt ein Modul nach einem Importfehler aus ``sys.modules``,
    nimmt dessen bereits ausgeführte Dekoratoren aber nicht zurück. Ohne eine
    Transaktion trifft der nächste Versuch deshalb auf den ersten gebliebenen
    Baustein und meldet ihn als doppelt registriert.
    """
    script = textwrap.dedent(
        """
        import importlib, sys

        loader = importlib.import_module("app.core.knowledge.parts.builtin")
        registry = importlib.import_module("app.core.knowledge.parts.registry")
        original = registry.PARTS.register
        calls = 0

        def fail_after_one(spec):
            global calls
            calls += 1
            if calls == 2:
                raise RuntimeError("erzwungener Abbruch im Gruppenimport")
            return original(spec)

        registry.PARTS.register = fail_after_one
        try:
            loader.load()
        except RuntimeError:
            pass
        else:
            raise AssertionError("der erzwungene Teilimport ist nicht abgebrochen")
        finally:
            registry.PARTS.register = original

        assert not registry.PARTS.all(), [spec.name for spec in registry.PARTS.all()]
        assert loader._loaded is False

        complete = loader.load()
        assert complete.all()
        assert loader._loaded is True
        assert all(
            f"app.core.knowledge.parts.{name}" in sys.modules
            for name in loader.SHIPPED_MODULES
        )
        """
    )
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
    )

    assert finished.returncode == 0, finished.stderr or finished.stdout


def test_parts_loader_keeps_a_parallel_completed_group_when_the_next_group_fails() -> None:
    """Rollback betrifft das Fehler-Modul, nicht eine parallel beendete Gruppe.

    ``fasteners`` steckt beim Snapshot schon in ``sys.modules``, hat aber noch
    keinen Dekorator abgeschlossen. Danach registriert es vollständig;
    ``mechanics`` bricht beim zweiten Baustein ab. Der Retry muss beide Gruppen
    vollständig sehen — die erste aus dem Cache, die zweite aus dem Neuimport.
    """
    script = textwrap.dedent(
        """
        import importlib, sys, threading

        loader = importlib.import_module("app.core.knowledge.parts.builtin")
        registry = importlib.import_module("app.core.knowledge.parts.registry")
        original_import = importlib.import_module
        original_register = registry.PARTS.register
        fasteners = "app.core.knowledge.parts.fasteners"
        mechanics = "app.core.knowledge.parts.mechanics"
        expected_fasteners = {
            "heatset_m4",
            "nut_trap",
            "printed_nut",
            "printed_screw",
            "printed_thread",
            "screw_hole",
        }
        entered_fasteners = threading.Event()
        release_fasteners = threading.Event()
        loader_waiting = threading.Event()
        failed = []
        parallel_failed = []
        mechanics_calls = 0

        def controlled_register(spec):
            global mechanics_calls
            if spec.fn.__module__ == fasteners and not entered_fasteners.is_set():
                entered_fasteners.set()
                assert release_fasteners.wait(10), "fasteners wurde nicht freigegeben"
            if spec.fn.__module__ == mechanics:
                mechanics_calls += 1
                if mechanics_calls == 2:
                    raise RuntimeError("erzwungener Abbruch in mechanics")
            return original_register(spec)

        def tracked_import(name):
            if name == fasteners and threading.current_thread().name == "loader":
                loader_waiting.set()
            return original_import(name)

        registry.PARTS.register = controlled_register
        loader.importlib.import_module = tracked_import

        def load_fasteners():
            try:
                original_import(fasteners)
            except BaseException as error:
                parallel_failed.append(error)

        first = threading.Thread(target=load_fasteners, name="fasteners")

        def load_with_failure():
            try:
                loader.load()
            except BaseException as error:
                failed.append(error)

        second = threading.Thread(target=load_with_failure, name="loader")
        first.start()
        assert entered_fasteners.wait(10), "fasteners erreichte keinen Dekorator"
        second.start()
        assert loader_waiting.wait(10), "loader wartete nicht auf fasteners"
        release_fasteners.set()
        first.join(10)
        second.join(10)
        assert not first.is_alive() and not second.is_alive(), "Import-Deadlock"
        assert not parallel_failed, parallel_failed
        assert len(failed) == 1 and isinstance(failed[0], RuntimeError), failed
        assert loader._loaded is False
        after_failure = registry.PARTS.all()
        assert {
            spec.name for spec in after_failure if spec.fn.__module__ == fasteners
        } == expected_fasteners
        assert not any(spec.fn.__module__ == mechanics for spec in after_failure)

        registry.PARTS.register = original_register
        loader.importlib.import_module = original_import
        complete = loader.load()
        modules = {spec.fn.__module__ for spec in complete.all()}

        assert len(complete.all()) == 27
        assert {
            spec.name for spec in complete.all() if spec.fn.__module__ == fasteners
        } == expected_fasteners
        assert fasteners in modules, sorted(modules)
        assert mechanics in modules, sorted(modules)
        assert all(
            f"app.core.knowledge.parts.{name}" in modules
            for name in loader.SHIPPED_MODULES
        ), sorted(modules)
        assert loader._loaded is True
        """
    )
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
        timeout=90,
    )

    assert finished.returncode == 0, finished.stderr or finished.stdout


def test_activation_keeps_its_public_names_without_eager_submodules() -> None:
    """Die Deadlock-Reparatur darf weder die API noch die Lizenzgrenze laden.

    Der Paketimport allein ist der sichere Zustand; erst der Zugriff auf einen
    zugesagten Namen lädt genau dessen Untermodul. Im Subprozess ist der
    Modulcache leer und kann die Aussage nicht versehentlich grün machen.
    """
    script = textwrap.dedent(
        """
        import importlib, inspect, sys, threading, typing
        import app.core.activation as activation

        prefix = "app.core.activation."
        eager = sorted(name for name in sys.modules if name.startswith(prefix))
        assert not eager, eager
        assert "TRIAL_DAYS" in dir(activation)
        assert activation.Activation.__annotations__["licence"] == "Licence | None"
        assert (
            activation.Activation.__annotations__["certificate"]
            == "ActivationCertificate | None"
        )
        hints = typing.get_type_hints(activation.Activation)
        annotations = inspect.get_annotations(activation.Activation, eval_str=True)
        assert hints["licence"] == activation.Licence | None
        assert hints["certificate"] == activation.ActivationCertificate | None
        assert annotations["licence"] == activation.Licence | None
        assert annotations["certificate"] == activation.ActivationCertificate | None
        return_hints = typing.get_type_hints(activation.install_certificate)
        return_annotations = inspect.get_annotations(
            activation.install_certificate,
            eval_str=True,
        )
        assert return_hints["return"] is activation.ActivationCertificate
        assert return_annotations["return"] is activation.ActivationCertificate
        assert isinstance(activation.TRIAL_DAYS, int)
        loaded = sorted(name for name in sys.modules if name.startswith(prefix))
        assert "app.core.activation.store" in loaded, loaded

        broken = []
        submodules = ("certificate", "device", "ed25519", "integrity", "key", "store")
        for attempt in range(50):
            for stale in [name for name in sys.modules if name.startswith("app.core.activation")]:
                del sys.modules[stale]

            def through_package():
                try:
                    package = importlib.import_module("app.core.activation")
                    assert package.Activation.__name__ == "Activation"
                    assert package.Licence.__name__ == "Licence"
                except BaseException as error:
                    broken.append(
                        f"{attempt} (package): {type(error).__name__}: {error}"
                    )

            def through_submodules():
                try:
                    for name in submodules:
                        importlib.import_module(f"app.core.activation.{name}")
                except BaseException as error:
                    broken.append(
                        f"{attempt} (modules): {type(error).__name__}: {error}"
                    )

            first = threading.Thread(target=through_package)
            second = threading.Thread(target=through_submodules)
            first.start()
            second.start()
            first.join(timeout=10)
            second.join(timeout=10)
            if first.is_alive() or second.is_alive():
                broken.append(f"{attempt}: nach 10 s noch nicht beendet")
                break

        assert not broken, "\\n".join(broken)
        """
    )
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
    )

    assert finished.returncode == 0, finished.stderr or finished.stdout
