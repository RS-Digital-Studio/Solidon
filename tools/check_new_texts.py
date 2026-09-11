"""Ob die **neuen** Oberflächentexte eines Commits in den Katalogen stehen.

**Der Fall, für den es das gibt.** Der ``pre-commit``-Hook hält an, wenn die
Übersetzungsprüfung rot ist und der Commit ``tr()``-Texte anlegt. Das ist zu
grob: Er hält damit auch einen Commit auf, der einen ganz anderen Text
hinzufügt, während irgendwo im Baum ein älterer Text unübersetzt liegt. In der
Nacht auf den 31.08.2026 ist genau das fünfmal passiert, und zweimal war der
Text des Commits längst vollständig.

Gefragt wird deshalb: **Steht einer der fehlenden Texte in diesem Commit?**

**Und gefragt wird der Quelltext gegen die Kataloge, nicht die pytest-Ausgabe.**
Der Hook warnt selbst vor dieser Falle: Ein Muster über die Ausgabe scheiterte
schon einmal an der Kodierung, weil die Locale der Hook-Shell eine andere ist
als die der Testausgabe — und ein Muster, das an der Kodierung scheitert,
meldet dasselbe wie eines, das nichts findet. Gelesen wird deshalb die Datei
selbst, in beiden Fassungen: ``git show :datei`` gegen ``git show HEAD:datei``,
je durch ``ast``. Die Kataloge kommen als JSON daneben; beide Seiten sind
eindeutig, und keine hängt an einer Zeilenform. Warum nicht der Diff, steht
bei :func:`added_texts`.

Aufruf (der Hook tut es, sonst niemand)::

    python tools/check_new_texts.py

Rückgabe 1, wenn ein neuer Text in einem Katalog fehlt oder leer steht —
dann gehört der Verdacht diesem Commit. Rückgabe 0 sonst, auch wenn die
Prüfung insgesamt rot ist: Dann liegt es an fremder Arbeit.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Die Namen, unter denen ein Oberflächentext im Quelltext steht.
CALLS = frozenset({"tr", "_"})


def _changed_files() -> list[str]:
    """Die Python-Dateien unter ``app/`` und ``tools/``, die dieser Commit mitnimmt."""
    listing = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "--", "*.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    ).stdout
    return [
        name
        for name in listing.splitlines()
        if name.startswith(("app/", "tools/")) and name.endswith(".py")
    ]


def _texts_in(revision: str, path: str) -> set[str]:
    """Jeder Oberflächentext einer Fassung dieser Datei.

    ``revision`` ist, was ``git show`` versteht — ``""`` für den gestagten
    Stand (``:datei``), ``HEAD`` für den letzten Commit. Fehlt die Datei dort,
    ist die Antwort leer: Eine neue Datei hat keinen Vorzustand.
    """
    source = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )
    if source.returncode != 0:
        return set()
    try:
        tree = ast.parse(source.stdout)
    except SyntaxError:
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else None
        if name not in CALLS:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            found.add(first.value)
    return found


def added_texts() -> list[str]:
    """Die Texte, die dieser Commit neu anlegt — Menge nachher ohne Menge vorher.

    **Warum der Umweg über zwei Fassungen und nicht über den Diff.** Hier stand
    ein Regex, der die ``+``-Zeilen **zeilenweise** absuchte, mit dem Vermerk,
    mehrzeilige Texte würden absichtlich nicht erfasst — durchrutschen sei
    billiger als jemanden ohne Grund aufhalten. Die Abwägung stimmte, die
    Rechnung nicht: Am 10.09.2026 formulierte ein Commit drei Absagen in
    ``perceive/actions.py`` um, alle drei über vier Zeilen implizit
    zusammengesetzt. Der Wächter fand in 1068 Diff-Zeilen **einen** Text — den
    einzigen einzeiligen —, ließ den Commit durch, und die Übersetzungsprüfung
    stand danach für jeden rot, der das Tor fuhr. Blind war er ausgerechnet für
    die langen, erklärenden Sätze, also für die wertvollsten.

    Ein Regex über mehrere Zeilen hätte den Handel nur verschoben: Ändert
    jemand die **letzte** Zeile eines langen Literals, liegt im Diff ein
    Bruchstück, und ein Bruchstück steht in keinem Katalog — der Wächter hielte
    an, ohne dass etwas fehlt. Genau davor warnte der alte Vermerk zu Recht.

    Deshalb wird nicht der Diff gelesen, sondern zweimal die Datei: ``ast``
    löst implizite Zusammensetzung von sich aus auf und liefert den Text, wie
    Python ihn liest — Escape-Folgen und Umlaute inbegriffen. Damit erledigt
    sich zugleich die Falle aus dem Gesamtreview vom 05.09.2026 (R18), wo ein
    Text mit Umlaut **und** Zeilenumbruch über ``unicode_escape`` zu
    „WÃ¤hlen …" wurde und seine vorhandene Übersetzung als fehlend galt.
    Was in der gestagten Fassung steht und in der von ``HEAD`` nicht, hat
    dieser Commit angelegt — ob neu geschrieben oder umformuliert, denn beides
    ist ein neuer Katalogschlüssel. Alles andere lag schon vorher da und
    gehört jemand anderem.

    **Umbenannte Dateien bleiben draußen** (``--diff-filter=ACM``, ohne ``R``).
    Bei einer Umbenennung nennt ``--name-only`` den **neuen** Namen, und
    ``git show HEAD:neuername`` scheitert — die Vorher-Menge wäre leer, und
    damit gälte **jeder** Text der Datei als neu. Wer eine Datei verschiebt
    und dabei einen alten unübersetzten Text mitnimmt, würde aufgehalten,
    obwohl er nichts angelegt hat; genau dagegen gibt es diesen Wächter.
    """
    found: set[str] = set()
    for path in _changed_files():
        found |= _texts_in("", path) - _texts_in("HEAD", path)
    return sorted(found)


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
