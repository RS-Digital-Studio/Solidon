"""Prüft eine Commit-Meldung auf Ersatzschreibung statt Umlaut.

    .venv\\Scripts\\python.exe tools/check_message.py <datei>

**Warum es diesen Wächter gibt.** Am 30./31.08.2026 sind an einem Abend
**fünf** Meldungen und Oberflächentexte mit „ae"/„oe"/„ue"/„ss" statt echter
Umlaute entstanden — „faellt", „unvollstaendiger", „liess", „Waehlen",
„prueft". Jedes Mal war deutscher Text durch die Shell gegangen (Heredoc,
`printf`), und jedes Mal hatte die Vorsicht vor dem Quoting die Sprachregel
gebrochen, die sie schützen sollte.

Die Erinnerung dazu existierte, war zweimal geschärft worden und hat es
trotzdem nicht verhindert. Was hilft, ist keine bessere Formulierung, sondern
**eine Prüfung, die zum Zeitpunkt der Arbeit anschlägt** — dieselbe Einsicht,
aus der `test_no_source_text_writes_ae_for_a_umlaut` entstanden ist. Der Test
deckt die Oberflächentexte ab, dieser Wächter die Commit-Meldungen; beide
lesen dieselbe kuratierte Liste, damit es nicht zwei Wahrheiten gibt.

**Kuratiert und nicht geraten**, aus demselben Grund wie bei ``GERMAN_STEMS``:
Deutsch und Englisch überlappen zu stark. „Success" und „Business" tragen
„ss", „Baseline" ein „ae" — geprüft wird deshalb auf **ganze Wörter** aus
einer Liste, die nur enthält, was schon einmal jemand falsch geschrieben hat.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


#: Was hier schon einmal jemand falsch geschrieben hat — die Grundliste.
#:
#: Sie steht neben der des Übersetzungstests und **ersetzt sie nicht**: Der
#: erste Entwurf nahm die eine *oder* die andere, und weil ihre vorhanden ist,
#: kam diese nie zum Zug. Gemessen an den fünf Fällen, die diesen Wächter
#: ausgelöst haben, rutschten damit zwei durch — „unvollstaendiger" und
#: „Koerper" kennt ihre Liste nicht. Zwei kuratierte Listen sind kein
#: Widerspruch, sie sind zwei Sammlungen desselben Fehlers; gebraucht wird
#: ihre Vereinigung.
BASE_REPLACEMENTS = {
    "aendern": "ändern",
    "faellt": "fällt",
    "fuer": "für",
    "groesse": "Größe",
    "groesser": "größer",
    "gross": "groß",
    "hoehe": "Höhe",
    "koerper": "Körper",
    "liess": "ließ",
    "loeschen": "löschen",
    "muss": "",
    "naechste": "nächste",
    "prueft": "prüft",
    "unvollstaendig": "unvollständig",
    "waehlen": "wählen",
    "zurueck": "zurück",
}


def replacements() -> dict[str, str]:
    """Die Grundliste, vereinigt mit der des Übersetzungstests.

    Der Test ist der ältere Ort und wird von der Suite ohnehin gefahren —
    was dort dazukommt, gilt hier sofort mit. Fehlt er (etwa in einem Paket
    ohne ``tests/``), bleibt die Grundliste allein arbeitsfähig, statt den
    Commit durchzulassen: **Ein Wächter, der bei fehlender Zutat schweigt,
    ist keiner.**
    """
    table = dict(BASE_REPLACEMENTS)
    try:
        from tests.test_translations import ASCII_STATT_UMLAUT

        table.update({word: correct for word, correct in ASCII_STATT_UMLAUT.items() if correct})
    except Exception:
        pass
    return table


def findings(text: str) -> dict[str, str]:
    """Welche Ersatzschreibungen in diesem Text stehen, und wie es richtig wäre."""
    table = {word: correct for word, correct in replacements().items() if correct}
    if not table:
        return {}
    # **Als Stamm, nicht als ganzes Wort.** Die Liste kennt
    # „unvollstaendig", geschrieben wird „unvollstaendiger"; sie kennt
    # „gross", geschrieben wird „grosses". Eine Prüfung auf ganze Wörter
    # ließe genau die Formen durch, die im Fließtext die häufigeren sind —
    # sechs von sieben Proben richtig ist kein Wächter, sondern Zufall.
    # Nach vorn bleibt die Grenze hart, damit ein Wort, das zufällig auf
    # einen Eintrag endet, nicht anschlägt.
    pattern = re.compile(
        r"(?<![\wäöüßÄÖÜ])(" + "|".join(sorted(table)) + r")\w*",
        re.IGNORECASE,
    )
    found: dict[str, str] = {}
    for word in pattern.findall(text):
        found[word.lower()] = table[word.lower()]
    return found


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("check_message.py <datei>", file=sys.stderr)
        return 2
    source = Path(argv[1])
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as problem:
        print(f"commit-msg: {source} nicht lesbar: {problem}", file=sys.stderr)
        return 0  # Ein unlesbarer Puffer ist kein Sprachfehler.

    # Kommentarzeilen gehören git, nicht dem Autor.
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    found = findings(body)
    if not found:
        return 0

    print("commit-msg: Ersatzschreibung statt Umlaut in der Meldung.", file=sys.stderr)
    for wrong, right in sorted(found.items()):
        print(f"  {wrong} → {right}", file=sys.stderr)
    print(
        "\nDeutsch heißt echte Umlaute (AGENTS.md). Der häufigste Grund ist ein\n"
        "Bash-Heredoc oder printf, in dem aus Vorsicht ASCII getippt wurde —\n"
        "beide übertragen Umlaute gemessen sauber. Sicher ist: die Meldung mit\n"
        "dem Write-Werkzeug in eine Datei schreiben und mit -F übergeben.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
