"""Vier Schichten, eine Richtung (``app/CLAUDE.md``).

``core`` rechnet, ``ui`` und ``cli`` sind zwei Oberflächen darüber, ``i18n``
hängt an nichts. Die Karte zeichnet das als Pfeile, und bis hierher stand
nichts dahinter: ``tests/test_core_isolation.py`` hält Qt und ``app.ui`` aus
dem Kern — die drei anderen Pfeile prüfte niemand. Genau einer war gebrochen:
``app/i18n/catalog.py`` holte seinen Logger aus ``app.core.log``, und damit
hing die Schicht, die an nichts hängen soll, am Kern — der Kern an ihr
sowieso. Ein Kreis zwischen Paketen, den kein Import-Deadlock je zeigte, weil
``i18n`` beim ersten Zugriff längst geladen war.

Geprüft wird über den Quelltext, nicht über ``sys.modules``: Ein Import in
einer Funktion oder unter ``TYPE_CHECKING`` ist dieselbe Abhängigkeit — die
Karte sagt ausdrücklich „nicht in einer Hilfsfunktion, nicht nur für den
Typ".
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

import app

APP_DIR: Final = Path(app.__file__).parent

#: Was jede Schicht importieren darf — außer sich selbst und ``app.branding``,
#: das an nichts hängt und allen gehört (§37.1).
ALLOWED: Final[dict[str, frozenset[str]]] = {
    "core": frozenset({"i18n"}),
    "ui": frozenset({"core", "i18n"}),
    "cli": frozenset({"core", "i18n"}),
    "i18n": frozenset(),
}

#: Verzeichnisse unter ``app/``, die keine Schicht sind: Daten, Bilder,
#: Beispiele — dort liegt kein Python, das importiert.
_NOT_A_LAYER: Final = frozenset({"images", "examples"})


def _layer_of(module: str) -> str | None:
    """``app.core.geom.mesh`` → ``core``; ``app.branding`` → ``None``."""
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "app":
        return None
    return parts[1] if parts[1] in ALLOWED else None


def _imports_of(path: Path) -> list[tuple[int, str]]:
    """Jeder Import der Datei mit seiner Zeile — auch träge, auch für Typen."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            # Relativ bleibt in der eigenen Schicht — ``from . import x``
            # kann das Paket nicht verlassen, solange niemand ``...`` bis über
            # ``app/`` hinaus schreibt. Das täte nur ein Import aus ``app``
            # selbst, und dort liegt außer ``branding`` nichts.
            continue
    return found


def _layer_sources() -> dict[str, list[Path]]:
    sources: dict[str, list[Path]] = {layer: [] for layer in ALLOWED}
    for path in sorted(APP_DIR.rglob("*.py")):
        first = path.relative_to(APP_DIR).parts[0]
        if first in sources:
            sources[first].append(path)
    return sources


@pytest.mark.parametrize("layer", sorted(ALLOWED))
def test_a_layer_imports_only_downwards(layer: str) -> None:
    sources = _layer_sources()[layer]
    assert sources, f"keine Quellen unter app/{layer} — der Test hätte nichts geprüft"
    offenders: list[str] = []
    for path in sources:
        for line, module in _imports_of(path):
            target = _layer_of(module)
            if target is None or target == layer or target in ALLOWED[layer]:
                continue
            offenders.append(f"{path.relative_to(APP_DIR.parent)}:{line} importiert {module}")
    assert not offenders, f"app/{layer} importiert gegen die Richtung:\n" + "\n".join(offenders)


def test_every_layer_directory_is_known() -> None:
    """Ein fünftes Verzeichnis mit Python darunter hätte keine Regel."""
    unknown = sorted(
        entry.name
        for entry in APP_DIR.iterdir()
        if entry.is_dir()
        and entry.name not in ALLOWED
        and entry.name not in _NOT_A_LAYER
        and not entry.name.startswith("_")
        and any(entry.rglob("*.py"))
    )
    assert not unknown, f"Verzeichnisse unter app/ ohne Schichtregel: {unknown}"
