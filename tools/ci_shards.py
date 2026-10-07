"""Dieselbe vollständige Testmenge, auf mehrere CI-Runner verteilt.

    gh run download <lauf> --pattern "tests-*" --dir berichte
    .venv\\Scripts\\python.exe tools/ci_shards.py core \\
        berichte/tests-core-windows-latest-*/junit.xml
    .venv\\Scripts\\python.exe tools/ci_shards.py windows berichte/tests-windows-*/tests__*.xml \\
        berichte/tests-contracts-windows-latest/tests__*.xml

``gh run download`` legt je Artefakt einen Ordner mit dessen Namen an. Die
Kerntabelle nimmt die Berichte **einer** Plattform — alle drei Teile, sonst
fehlen Dateien und bekommen nur das Ersatzgewicht; gemischt über Plattformen
summierte sie dieselbe Datei dreimal. Die Fenstertabelle nimmt die drei
Windows-Gruppen **und** die Windows-Berichte der zwei Fensterverträge: Diese
verteilt sie nicht, sie führt aber jede Fensterdatei, die unter Windows läuft,
und ``tests/test_ci_runner.py`` verlangt beide Verträge darin.

Zwei Verbraucher teilen diese Verteilung: ``run_suite_isolated.py`` legt die
Fensterdateien auf die Windows-Gruppen, und ``tests/conftest.py`` wählt mit
``--ci-shard I/N`` den Teil der Kernsuite, den ein Kernjob fährt. Beide
verteilen **je Datei**, längste zuerst auf die bisher leichteste Gruppe,
Gleichstand über den Pfad und die Gruppennummer. Je Datei, weil Fixtures mit
Modulumfang sonst in jeder Gruppe neu entstünden.

**Die Laufzeittabellen verteilen nur.** Welche Tests laufen, sagt die
aktuelle Sammlung; eine neue oder umbenannte Datei bekommt das
Ersatzgewicht der Tabelle und bleibt dabei, ein alter Eintrag ohne Datei
schafft keine. Jede Gruppe rechnet denselben Plan aus derselben Sammlung,
also fällt nichts zwischen zwei Gruppen und nichts läuft doppelt
(``konzepte/konzept-ci-testlaufzeiten-2026-09.md``, CI-01).

Als Befehl schreibt das Werkzeug eine Tabelle neu: aus den JUnit-Berichten
eines vollständigen Laufs, die Sekunden je Datei als Summe ihrer Fälle, das
Ersatzgewicht als 90. Perzentil. Die Herkunft steht in der Tabelle; was sie
misst, ist die Verteilung eines Laufs und keine Laufzeitzusage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: Historische Sekunden je Fensterdatei, für die Windows-Gruppen.
WINDOW_DURATIONS = ROOT / "tests" / "data" / "ci_window_durations.json"

#: Historische Sekunden je Datei der Kernsuite, für die Kernjobs.
CORE_DURATIONS = ROOT / "tests" / "data" / "ci_core_durations.json"

TABLES = {"core": CORE_DURATIONS, "windows": WINDOW_DURATIONS}


def read_durations(path: Path) -> tuple[dict[str, float], float]:
    """Liest geprüfte Gewichte; ein Tabellenfehler verteilt nie still zufällig."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != 1:
        raise ValueError("Unbekannte Laufzeittabelle; die Fassung der CI-Zeiten prüfen.")
    weights = document["durations_seconds"]
    fallback = document["unknown_file_seconds"]
    if not isinstance(weights, dict) or not all(isinstance(name, str) for name in weights):
        raise ValueError("Die Laufzeittabelle braucht eine Zuordnung von Dateien zu Sekunden.")
    for value in [fallback, *weights.values()]:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Laufzeitgewichte müssen positive endliche Sekunden sein.")
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Laufzeitgewichte müssen positive endliche Sekunden sein.")
    return {name: float(value) for name, value in weights.items()}, float(fallback)


def balanced(weights: Mapping[str, float], count: int) -> tuple[tuple[str, ...], ...]:
    """Längste Datei zuerst in die leichteste Gruppe; Gleichstand über Pfad, dann Gruppe."""
    if count < 1:
        raise ValueError("Mindestens eine CI-Gruppe; Gruppenzahl prüfen.")
    groups: list[list[str]] = [[] for _ in range(count)]
    totals = [0.0] * count
    for name in sorted(weights, key=lambda name: (-weights[name], name)):
        index = min(range(count), key=lambda index: (totals[index], index))
        groups[index].append(name)
        totals[index] += weights[name]
    return tuple(tuple(group) for group in groups)


def parse_shard(value: str) -> tuple[int, int]:
    """``I/N`` mit ``0 <= I < N``; alles andere ist eine Bedienungsfrage, kein Plan."""
    index, separator, count = value.partition("/")
    if not separator or not index.isdigit() or not count.isdigit():
        raise ValueError(f"--ci-shard erwartet I/N, etwa 0/3, nicht {value!r}.")
    if not 0 <= int(index) < int(count):
        raise ValueError(f"--ci-shard {value}: I muss zwischen 0 und N minus 1 liegen.")
    return int(index), int(count)


def file_of_item(item: pytest.Item, root: Path) -> str:
    """Der Pfad der Testdatei relativ zum Repository, wie ihn die Tabellen führen."""
    path = Path(str(item.path)).resolve()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


class CoreShard:
    """Laufplugin: behält die Dateien, die der Plan dieser Gruppe gibt.

    Es rechnet nach der Markerwahl (``trylast``) — verteilt wird also die
    Menge, die dieser Lauf tatsächlich fährt. Unter xdist sammelt jeder
    Worker selbst; gleiche Sammlung, gleicher Plan, gleiche Auswahl.
    """

    def __init__(self, index: int, count: int, weights: Mapping[str, float], fallback: float):
        self.index = index
        self.count = count
        self.weights = dict(weights)
        self.fallback = fallback

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(
        self, config: pytest.Config, items: list[pytest.Item]
    ) -> None:
        root = Path(str(config.rootpath)).resolve()
        # Einmal je Datei aufgelöst, nicht je Fall und Durchgang: ``resolve``
        # fragt das Dateisystem, und dreimal über rund 17 000 Fälle kostete
        # das jeden Prozess Sekunden (gemessen am 25.09.2026).
        names: dict[Path, str] = {}
        files = []
        for item in items:
            if item.path not in names:
                names[item.path] = file_of_item(item, root)
            files.append(names[item.path])
        weights = {name: self.weights.get(name, self.fallback) for name in names.values()}
        mine = set(balanced(weights, self.count)[self.index])
        kept = [item for item, name in zip(items, files, strict=True) if name in mine]
        dropped = [item for item, name in zip(items, files, strict=True) if name not in mine]
        if dropped:
            config.hook.pytest_deselected(items=dropped)
        items[:] = kept


def add_option(parser: pytest.Parser) -> None:
    """``--ci-shard I/N`` für ``tests/conftest.py``."""
    parser.addoption(
        "--ci-shard",
        default=None,
        help="nur den I-ten von N Teilen der Sammlung fahren, je Datei verteilt (CI)",
    )


def register(config: pytest.Config) -> None:
    """Hängt das Plugin ein, wenn ``--ci-shard`` gesetzt ist; sonst ändert sich nichts."""
    value = config.getoption("--ci-shard", default=None)
    if value is None:
        return
    try:
        index, count = parse_shard(value)
        weights, fallback = read_durations(CORE_DURATIONS)
    except (OSError, ValueError, KeyError) as error:
        raise pytest.UsageError(f"CI-Teil lässt sich nicht planen: {error}") from error
    config.pluginmanager.register(CoreShard(index, count, weights, fallback), "ci-shard")


def junit_file_seconds(paths: Iterable[Path]) -> dict[str, float]:
    """Summiert die Fallzeiten je Testdatei aus pytest-JUnit (``tests.test_x[.Klasse]``)."""
    seconds: dict[str, float] = {}
    for path in paths:
        for case in ET.parse(path).getroot().iter("testcase"):
            parts = case.attrib["classname"].split(".")
            module = next(
                (index for index, part in enumerate(parts) if part.startswith("test_")), None
            )
            if module is None:
                raise ValueError(f"{path}: Fall ohne Testmodul im Klassennamen {parts!r}.")
            name = "/".join(parts[: module + 1]) + ".py"
            seconds[name] = seconds.get(name, 0.0) + float(case.attrib.get("time") or 0.0)
    return seconds


def table_from(seconds: Mapping[str, float], sources: Sequence[Path], note: str) -> dict[str, Any]:
    """Die Tabelle samt Herkunft; Dateien ohne messbare Zeit bekommen das Ersatzgewicht."""
    measured = sorted(value for value in seconds.values() if value > 0)
    if not measured:
        raise ValueError("Die Berichte enthalten keine gemessenen Fälle.")
    fallback = measured[min(len(measured) - 1, math.ceil(0.9 * len(measured)) - 1)]
    digest = hashlib.sha256()
    for path in sorted(sources):
        digest.update(path.read_bytes())
    return {
        "schema": 1,
        "source": {"reports": len(sources), "sha256": digest.hexdigest(), "note": note},
        "unknown_file_seconds": round(fallback, 2),
        "unknown_file_policy": "90. Perzentil der gemessenen Dateizeiten; neue und "
        "umbenannte Dateien bleiben immer in der aktuellen Sammlung.",
        "durations_seconds": {
            name: max(round(value, 2), 0.01) for name, value in sorted(seconds.items()) if value > 0
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("table", choices=sorted(TABLES), help="welche Tabelle neu entsteht")
    parser.add_argument("reports", nargs="+", type=Path, help="JUnit-Berichte eines Laufs")
    parser.add_argument("--note", default="", help="Herkunft: Lauf, Commit, Plattform")
    arguments = parser.parse_args(argv)
    try:
        seconds = junit_file_seconds(arguments.reports)
        table = table_from(seconds, arguments.reports, arguments.note)
    except (OSError, ET.ParseError, KeyError, ValueError) as error:
        print(f"Tabelle nicht geschrieben: {error}", file=sys.stderr)
        return 1
    target = TABLES[arguments.table]
    target.write_text(
        json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"{target.relative_to(ROOT).as_posix()}: {len(table['durations_seconds'])} Dateien")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
