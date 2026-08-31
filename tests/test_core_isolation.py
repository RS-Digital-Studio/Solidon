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

    Sechs davon lösen ihre Namen jetzt erst beim Zugriff auf
    (:mod:`app.core.lazy`). Im Subprozess, weil die Module beim Start des Tests
    längst geladen wären und der Fall dann nicht mehr auftritt.
    """
    script = textwrap.dedent(
        """
        import importlib, pkgutil, sys, threading
        import app.core

        # Ein bekannter offener Fall. Er steht in ROADMAP.md; wer ihn behebt,
        # streicht seinen Namen hier -- dann prüft dieser Test ihn mit.
        #
        # ``knowledge.parts``: dort ist der Import die **Registrierung**. Die
        # fünf Modulimporte im ``__init__`` füllen das Bausteinregister, und
        # ``bootstrap.load_operations`` verlässt sich darauf. Verzögert wären
        # sie wirkungslos -- das ist kein Strukturfix mehr, sondern eine
        # Verhaltensänderung mit eigenem Punkt.
        KNOWN_OPEN = {"app.core.knowledge.parts"}

        # **Alles Nachschlagen passiert hier, vor dem ersten Thread.** Der
        # erste Anlauf ließ den zweiten Thread das Paket selbst importieren,
        # um an seine Untermodule zu kommen -- damit war das Paket geladen,
        # bevor der Wettlauf begann, und der Test war grün an einem Paket, das
        # nachweislich deadlockt. Gegenprobe gemacht: ohne KNOWN_OPEN muss er
        # rot werden.
        packages = []
        for info in pkgutil.walk_packages(app.core.__path__, "app.core."):
            if not info.ispkg or info.name in KNOWN_OPEN:
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
