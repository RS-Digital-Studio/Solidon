"""Schreibt die Erlaubnisliste der geteilten Bausteine neben die PHP-Dateien.

**Zwei Seiten prüfen dasselbe, und sie sprechen verschiedene Sprachen.** Die
Anwendung prüft vor dem Hochladen, der Server beim Empfangen — und PHP liest
kein Python. Wer die Liste zweimal pflegt, pflegt sie einmal falsch: Der
Skizzenlöser und sein Serializer haben am 31.08.2026 vorgeführt, wie das
endet, und dort war es dieselbe Sprache und dieselbe Datei nebenan.

Deshalb erzeugt dieses Werkzeug **eine** Datei, die beide lesen. Sie ist
abgeleitet und nicht geschrieben: Die Operationsnamen kommen aus dem Register,
die Rezeptschlüssel aus der Dataclass, die Grenzen aus dem Modul, das sie
begründet. Wer eine Operation hinzufügt, ändert die Liste, ohne dieses
Werkzeug anzufassen.

Aufruf::

    .venv\\Scripts\\python.exe tools/make_shared_rules.py

``tests/test_shared.py`` prüft, dass die eingecheckte Datei aktuell ist —
eine erzeugte Datei, die niemand neu erzeugt, ist beim nächsten Zuwachs
falsch, und genau das ist am 27.08.2026 einem Paketbau passiert.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.knowledge.parts.shared import rules  # noqa: E402

#: Wohin die Liste geschrieben wird — neben die PHP-Dateien, die sie lesen.
TARGET = ROOT / "website" / "api" / "shared-rules.json"


def written() -> str:
    """Die Liste als Text, wie sie in der Datei steht.

    Sortiert und mit festem Einzug: Zweimal erzeugen ergibt zweimal dieselbe
    Datei, sonst meldet der Wächter einen Unterschied, den niemand gemacht hat.
    """
    load_operations()
    return json.dumps(rules(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    text = written()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    before = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    if before == text:
        print(f"{TARGET.name}: unverändert")
    else:
        print(f"{TARGET.name}: geschrieben, {len(text)} Zeichen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
