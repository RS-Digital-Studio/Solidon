"""Hängt jedem Verweis auf eine eigene Datei ihren Inhaltsstempel an.

Aus ``href="style.css"`` wird ``href="style.css?v=a3f21c07"``, und der Stempel
ist die ersten acht Zeichen des SHA-256 über den Dateiinhalt. Ändert sich die
Datei, ändert sich der Verweis; ändert sie sich nicht, bleibt er Zeichen für
Zeichen gleich.

**Warum das nötig ist, obwohl `.htaccess` alles auf ``no-cache`` stellt.** Ein
Header wirkt auf die Antwort, die er begleitet — nicht auf einen Eintrag, der
längst im Browser liegt. Zwischen dem 20. und dem 25.08.2026 lieferte der
Server Bilder mit ``max-age=604800``; wer in jener Woche einmal da war, hält
sie bis zu sieben Tage für frisch und fragt gar nicht erst nach. Genau das ist
am 27.08. gemeldet worden: „Ohne STRG+F5 sehe ich noch die alten Bilder."

Dreimal wurde das schon an den Headern behoben (18.08., 20.08., 25.08.) und
kam dreimal wieder, weil es an den Headern nicht zu beheben ist. Ein
**anderer Verweis** ist die eine Auskunft, die jeden Cache erreicht: Was unter
einem neuen Namen angefragt wird, kann kein Eintrag unter dem alten
beantworten.

Die Seiten selbst brauchen keinen Stempel — sie kommen mit ``no-cache`` und
werden vor jeder Nutzung gegen den Server geprüft. Sie sind der Weg, über den
die neuen Verweise überhaupt ankommen.

Aufruf::

    python tools/stamp_assets.py           # stempelt und meldet
    python tools/stamp_assets.py --check   # meldet nur, ändert nichts

Der Lauf ist **idempotent**: Ein vorhandener Stempel wird durch den aktuellen
ersetzt, nicht ein zweiter angehängt. Er gehört ans Ende des Erzeugens, nach
Handbuch, Rechtstexten und Download-Kasten — jeder von ihnen schreibt HTML,
und ungestempelt hilft der beste Inhalt nichts.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"

#: Was gestempelt wird. HTML steht nicht dabei (siehe Modul-Docstring), und
#: ``.php`` auch nicht: Was der Server ausführt, liefert bei jedem Aufruf eine
#: eigene Antwort.
#:
#: **``mp4`` und ``webm`` gehören dazu, seit die Wege sich bewegen** (WD1).
#: Ein Loop ist die größte Datei der Seite; wer ihn ohne Stempel ausliefert,
#: lässt einen Besucher, der die Seite kennt, den alten sehen — und merkt es
#: nicht, weil die Seite drumherum neu ist.
SUFFIXES = (
    "css",
    "js",
    "png",
    "jpg",
    "jpeg",
    "webp",
    "avif",
    "svg",
    "woff2",
    "mp4",
    "webm",
)

#: Ein Verweis auf eine **eigene** Datei. Fremde Adressen, Sprungmarken,
#: ``mailto:`` und der Zähler unter ``/api/`` bleiben außen vor — der letzte,
#: weil seine Antwort von der Anfrage abhängt und nicht vom Dateiinhalt.
#: **``poster`` gehört dazu, und das ist leicht zu übersehen.** Ein Video
#: trägt sein Standbild nicht in ``src``, sondern in einem eigenen Attribut;
#: ohne es hier bliebe genau das Bild ungestempelt, das ein Besucher **zuerst**
#: sieht — und bei ``prefers-reduced-motion`` das einzige, das er je sieht.
LINK = re.compile(
    r'((?:src|href|poster)=")((?!https?:|mailto:|data:|#|/api/)[^"?]+\.(?:'
    + "|".join(SUFFIXES)
    + r'))(\?v=[0-9a-f]{8})?(")'
)

#: Wie viele Zeichen des Hashes mitreisen. Acht sind 4,3 Milliarden
#: Möglichkeiten — für die Frage „ist das dieselbe Datei wie vorhin?" mehr als
#: genug, und kurz genug, dass ein Verweis lesbar bleibt.
STAMP_LENGTH = 8


#: Wo die Zeilenenden vor dem Hashen vereinheitlicht werden. Bilder und
#: Schriften stehen nicht dabei: Dort wäre ein ``\r\n`` im Datenstrom keine
#: Zeilenschaltung, sondern ein Wert, und Ersetzen zerstörte die Datei.
TEXT_SUFFIXES = frozenset({".css", ".js", ".svg"})


def stamp_of(path: Path) -> str:
    """Die ersten acht Zeichen des SHA-256 über den Dateiinhalt.

    **Zeilenenden werden vorher vereinheitlicht**, sonst hängt der Stempel
    daran, wie git die Datei ausgecheckt hat. Gemessen am 27.08.2026:
    ``style.css`` wiegt im Arbeitsbaum dieser Maschine 68 006 Bytes mit 2 215
    CRLF und ergibt ``6c6561f6``; dieselbe Datei im Repository hat 65 791
    Bytes ohne ein einziges CRLF und ergibt ``c1a16e11``.

    Die Seiten trugen den ersten Wert. In einem frisch ausgecheckten Baum
    stimmte damit **kein einziger** der 142 Textverweise, und der Wächter
    daneben meldete sie alle als veraltet — im Hauptbaum blieb er grün, weil
    er dieselben Bytes las wie das Werkzeug. Gefunden hat es eine
    Nachbarsitzung, die in einem sauberen Arbeitsbaum maß.

    Derselbe Fehler säße auf dem Server: Was dort liegt, hängt davon ab, aus
    welchem Baum es hochgeladen wurde.
    """
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:STAMP_LENGTH]


def target_of(page: Path, reference: str) -> Path:
    """Wohin ein Verweis zeigt — absolute Pfade ab ``website/``, sonst relativ.

    Ein Verweis wie ``/site.js`` meint die Wurzel des Dokumentenstamms und
    nicht die Wurzel der Platte; ``bilder/x.png`` meint den Ordner der Seite,
    die ihn trägt. Eine englische Seite in ``en/`` verweist damit auf
    ``en/bilder/…`` — und wer das verwechselt, stempelt eine Datei mit dem
    Hash einer anderen.
    """
    if reference.startswith("/"):
        return WEBSITE / reference.lstrip("/")
    return page.parent / reference


def stamp_page(page: Path, *, write: bool) -> tuple[int, int, list[str]]:
    """Stempelt eine Seite. Gibt zurück: gestempelt, unverändert, Fehlstellen."""
    text = page.read_text(encoding="utf-8")
    fresh = 0
    same = 0
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        nonlocal fresh, same
        prefix, reference, existing, suffix = match.groups()
        target = target_of(page, reference)
        if not target.is_file():
            missing.append(reference)
            return match.group(0)
        wanted = f"?v={stamp_of(target)}"
        if existing == wanted:
            same += 1
        else:
            fresh += 1
        return f"{prefix}{reference}{wanted}{suffix}"

    stamped = LINK.sub(replace, text)
    if write and stamped != text:
        page.write_text(stamped, encoding="utf-8")
    return fresh, same, missing


def main(argv: list[str]) -> int:
    check = "--check" in argv
    pages = sorted(WEBSITE.rglob("*.html"))
    if not pages:
        print("Keine Seiten unter website/ gefunden.")
        return 1

    total_fresh = total_same = 0
    all_missing: list[tuple[Path, str]] = []
    for page in pages:
        fresh, same, missing = stamp_page(page, write=not check)
        total_fresh += fresh
        total_same += same
        all_missing.extend((page, reference) for reference in missing)
        if fresh:
            print(f"  {page.relative_to(WEBSITE)}: {fresh} Verweise gestempelt")

    for page, reference in all_missing:
        print(f"  FEHLT: {page.relative_to(WEBSITE)} verweist auf {reference}")

    verb = "wären zu stempeln" if check else "gestempelt"
    print(f"{total_fresh} Verweise {verb}, {total_same} schon aktuell, {len(pages)} Seiten")
    if all_missing:
        print(f"{len(all_missing)} Verweise zeigen ins Leere — die bleiben ungestempelt")
    return 1 if (check and total_fresh) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
