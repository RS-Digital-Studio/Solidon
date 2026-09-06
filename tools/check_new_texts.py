"""Ob die **neuen** Oberflächentexte eines Commits in den Katalogen stehen.

**Der Fall, für den es das gibt.** Der ``pre-commit``-Hook hält an, wenn die
Übersetzungsprüfung rot ist und der Commit ``tr()``-Texte anlegt. Das ist zu
grob: Er hält damit auch jeden auf, der einen ganz anderen Text hinzufügt,
während irgendwo im geteilten Baum ein fremder Text unübersetzt liegt. In der
Nacht auf den 31.08.2026 ist genau das fünfmal passiert — drei Sitzungen
warteten auf eine vierte, und zweimal war der eigene Text längst vollständig.

Gefragt wird deshalb: **Steht einer der fehlenden Texte in diesem Commit?**

**Und gefragt wird der Diff gegen die Kataloge, nicht die pytest-Ausgabe.**
Der Hook warnt selbst vor dieser Falle: Ein Muster über die Ausgabe scheiterte
schon einmal an der Kodierung, weil die Locale der Hook-Shell eine andere ist
als die der Testausgabe — und ein Muster, das an der Kodierung scheitert,
meldet dasselbe wie eines, das nichts findet. Der Diff kommt über
``git diff --cached`` als UTF-8 herein, die Kataloge als JSON; beide Seiten
sind eindeutig.

Aufruf (der Hook tut es, sonst niemand)::

    python tools/check_new_texts.py

Rückgabe 1, wenn ein neuer Text in einem Katalog fehlt oder leer steht —
dann gehört der Verdacht diesem Commit. Rückgabe 0 sonst, auch wenn die
Prüfung insgesamt rot ist: Dann liegt es an fremder Arbeit.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Ein ``tr("…")`` oder ``_("…")`` mit einfachem Text — mehrzeilige und über
#: ``+`` zusammengesetzte werden absichtlich nicht erfasst: Was hier
#: durchrutscht, kostet einen zu wenig angehaltenen Commit; was falsch
#: erfasst würde, hielte jemanden ohne Grund auf.
CALL = re.compile(r'(?:\btr|\b_)\(\s*"((?:[^"\\]|\\.)*)"')


def added_texts() -> list[str]:
    """Die Texte, die dieser Commit neu anlegt."""
    diff = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--", "app/*.py", "tools/*.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    ).stdout
    found: list[str] = []
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        found.extend(CALL.findall(line))
    return [_literal(text) for text in found]


def _literal(text: str) -> str:
    """Der Text, wie Python ihn liest — Escape-Folgen aufgelöst, Umlaute heil.

    Hier stand ``text.encode().decode("unicode_escape")``, und das las die
    UTF-8-Bytes als einzelne Codepunkte: Ein Text mit Umlaut **und**
    Zeilenumbruch wurde zu „WÃ¤hlen …", und seine vorhandene Übersetzung galt
    als fehlend (Gesamtreview 05.09.2026, R18).
    """
    if "\\" not in text:
        return text
    try:
        value = ast.literal_eval(f'"{text}"')
    except SyntaxError, ValueError:
        return text
    return value if isinstance(value, str) else text


def missing(texts: list[str]) -> dict[str, list[str]]:
    """Welche davon in welchem Katalog fehlen oder leer stehen."""
    gaps: dict[str, list[str]] = {}
    for path in sorted((ROOT / "app" / "i18n" / "locales").glob("*.json")):
        catalog = json.loads(path.read_text(encoding="utf-8"))
        gone = [text for text in texts if not catalog.get(text, "").strip()]
        if gone:
            gaps[path.stem] = gone
    return gaps


def main() -> int:
    texts = added_texts()
    if not texts:
        return 0
    gaps = missing(texts)
    if not gaps:
        return 0
    for language, gone in sorted(gaps.items()):
        print(f"{language}: {len(gone)} neue Texte ohne Übersetzung, z. B. {gone[0][:60]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
