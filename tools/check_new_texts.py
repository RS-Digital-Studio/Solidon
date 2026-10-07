"""Ob die **neuen** Oberflächentexte eines Commits in den Katalogen stehen.

Der ``pre-commit``-Hook führt diese statische Prüfung unabhängig vom Ergebnis
der Bezeichnerprüfung aus. Die vollständige Übersetzungs-Fensterdatei bleibt
dem Release vorbehalten. Geprüft werden nur die neuen ``tr()``-Texte des
Commits: Ein älterer unübersetzter Text im gemeinsamen Arbeitsbaum darf einen
anderen, vollständigen Commit nicht aufhalten.

Gefragt wird deshalb: **Steht einer der fehlenden Texte in diesem Commit?**

**Und gefragt wird der Quelltext gegen die Kataloge, nicht die pytest-Ausgabe.**
Der Hook warnt selbst vor dieser Falle: Ein Muster über die Ausgabe scheiterte
schon einmal an der Kodierung, weil die Locale der Hook-Shell eine andere ist
als die der Testausgabe — und ein Muster, das an der Kodierung scheitert,
meldet dasselbe wie eines, das nichts findet. Gelesen wird deshalb die Datei
selbst, in beiden Fassungen: ``git show :datei`` gegen ``git show HEAD:datei``,
je durch ``ast``. Auch die Katalogliste und ihre JSON-Inhalte kommen aus dem
Index; ungestagte Übersetzungen ändern den Commit nicht. Beide Seiten sind
eindeutig, und keine hängt an einer Zeilenform. Warum nicht der Diff, steht
bei :func:`added_texts`.

Aufruf im Hook oder zur gezielten statischen Entwicklungsprüfung::

    python tools/check_new_texts.py

Rückgabe 1, wenn ein neuer Text in einem Katalog fehlt oder leer steht —
dann gehört der Befund diesem Commit — oder wenn der Index gar keinen
Katalog trägt: Ohne Katalog fehlt nichts, und die Prüfung sähe aus wie
bestanden. Rückgabe 0 sonst, auch wenn andere Texte im gemeinsamen
Arbeitsbaum noch unübersetzt sind.
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


def _changed_files() -> list[tuple[str, str]]:
    """Alter und neuer Pfad der Python-Dateien, die dieser Commit mitnimmt."""
    listing = subprocess.run(
        [
            "git",
            "diff",
            "--cached",
            "--name-status",
            "--find-renames",
            "--diff-filter=ACMR",
            "-z",
            "--",
            "*.py",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        check=True,
    ).stdout
    fields = iter(listing.split("\0"))
    changed: list[tuple[str, str]] = []
    for status in fields:
        if not status:
            continue
        before = next(fields)
        after = next(fields) if status.startswith(("R", "C")) else before
        if after.startswith(("app/", "tools/")) and after.endswith(".py"):
            changed.append((before, after))
    return changed


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
            found.add(_catalog_key(node, first.value))
    return found


def _catalog_key(call: ast.Call, text: str) -> str:
    """Der Schlüssel, unter dem der Katalog diesen Text führt.

    **Mit Kontext steht er als ``Kontext\\x04Text`` darin**, wie
    ``TranslatableText`` nachschlägt. Ohne diese Zeile suchte der Wächter die
    Kundenwörter der Befehlspalette (``context="Suchwörter"``, Durchsicht 0.5.1)
    ohne ihren Kontext, fand keinen davon und hielt einen vollständig
    übersetzten Commit an.
    """
    for keyword in call.keywords:
        if (
            keyword.arg == "context"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
            and keyword.value.value
        ):
            return f"{keyword.value.value}\x04{text}"
    return text


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

    **Umbenennungen vergleichen beide Pfade**: den alten unter ``HEAD``, den
    neuen im Index. So bleiben mitgenommene ältere Kataloglücken draußen,
    während neue Texte in derselben Änderung weiterhin geprüft werden.
    """
    found: set[str] = set()
    for before, after in _changed_files():
        found |= _texts_in("", after) - _texts_in("HEAD", before)
    return sorted(found)


class NoCatalogError(RuntimeError):
    """Der Index trägt keinen Sprachkatalog — die Prüfung hätte nichts gefunden."""


def missing(texts: list[str]) -> dict[str, list[str]]:
    """Welche davon in den Katalogen des Index fehlen oder leer stehen.

    Ein Index ohne Katalog ist kein bestandener Fall, sondern ein falscher
    Ort (``NoCatalogError``): Ein leerer Treffer meldete dasselbe wie
    „alles übersetzt" (``.claude/rules/tests.md``, „Zuerst zählen“).
    """
    listing = subprocess.run(
        ["git", "ls-files", "--cached", "-z", "--", ":(glob)app/i18n/locales/*.json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        check=True,
    ).stdout
    paths = sorted(name for name in listing.split("\0") if name)
    if not paths:
        raise NoCatalogError(
            f"Im Index von {ROOT} liegt kein Katalog unter app/i18n/locales/. "
            "Den Hook im Solidon-Repository ausführen oder die Kataloge vormerken."
        )
    gaps: dict[str, list[str]] = {}
    for path in paths:
        source = subprocess.run(
            ["git", "show", f":{path}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(ROOT),
            check=True,
        ).stdout
        catalog = json.loads(source)
        gone = [text for text in texts if not catalog.get(text, "").strip()]
        if gone:
            gaps[Path(path).stem] = gone
    return gaps


def main() -> int:
    texts = added_texts()
    if not texts:
        return 0
    try:
        gaps = missing(texts)
    except NoCatalogError as problem:
        print(problem)
        return 1
    if not gaps:
        return 0
    for language, gone in sorted(gaps.items()):
        print(f"{language}: {len(gone)} neue Texte ohne Übersetzung, z. B. {gone[0][:60]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
