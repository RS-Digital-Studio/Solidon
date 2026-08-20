"""Trägt die Pakete in den Download-Kasten aller Sprachfassungen ein.

Am Tag der Veröffentlichung liegen zwei bis drei Dateien bereit, und für jede
gehören drei Angaben auf die Seite: wofür sie ist, wie groß sie ist und was
ihre Prüfsumme ist. Mal sechs Sprachfassungen sind das achtzehn Stellen, an
denen sich eine Ziffer verlaufen kann — und eine falsche Prüfsumme ist
schlimmer als keine, weil sie genau die Kontrolle scheitern lässt, für die sie
da ist.

Also rechnet das hier. Aufgerufen wird es mit den fertigen Paketen:

    python tools/make_download.py Releases/Solidon3D-0.1.0-Setup.exe \\
                                  Releases/Solidon3D-0.1.0-x86_64.AppImage

Die Dateien werden nach ``website/dl/`` kopiert, Größe und SHA-256 daraus
gerechnet und in die sechs ``index.html`` geschrieben. Danach schaltet die
Seite zum Termin von selbst um: Das Skript sieht die Verweise im Kasten und
weiß daran, dass es etwas zu laden gibt.

Ohne Argumente räumt es den Kasten wieder leer — für den Fall, dass ein Paket
zurückgezogen werden muss. Die Seite fällt dann auf die Warteliste zurück,
statt auf eine Datei zu zeigen, die nicht mehr liegt.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

for _strom in (sys.stdout, sys.stderr):
    if hasattr(_strom, "reconfigure"):
        _strom.reconfigure(encoding="utf-8", errors="replace")

WEBSITE = Path(__file__).resolve().parent.parent / "website"
ABLAGE = WEBSITE / "dl"

#: Die Startseiten, die einen Download-Kasten tragen.
SEITEN = ("index.html", *(f"{code}/index.html" for code in ("en", "es", "fr", "it", "pt")))

#: Woran eine Datei ihre Plattform erkennen lässt, und wie die Zeile dann in
#: jeder Sprache heißt. Die Reihenfolge hier ist die Reihenfolge im Kasten —
#: und die erste ist zugleich das Ziel des Knopfes beim Preis.
PLATTFORMEN: tuple[tuple[str, tuple[str, ...], dict[str, str]], ...] = (
    (
        "windows",
        (".exe", ".msi"),
        {
            "de": "Windows 10/11",
            "en": "Windows 10/11",
            "es": "Windows 10/11",
            "fr": "Windows 10/11",
            "it": "Windows 10/11",
            "pt": "Windows 10/11",
        },
    ),
    (
        "linux",
        (".appimage", ".tar.gz", ".tar.xz"),
        {
            "de": "Linux (AppImage)",
            "en": "Linux (AppImage)",
            "es": "Linux (AppImage)",
            "fr": "Linux (AppImage)",
            "it": "Linux (AppImage)",
            "pt": "Linux (AppImage)",
        },
    ),
    (
        "macos",
        (".dmg", ".pkg"),
        {
            "de": "macOS (Apple Silicon)",
            "en": "macOS (Apple silicon)",
            "es": "macOS (Apple Silicon)",
            "fr": "macOS (Apple Silicon)",
            "it": "macOS (Apple Silicon)",
            "pt": "macOS (Apple Silicon)",
        },
    ),
)

#: „245 MB" heißt in sechs Sprachen fast gleich — das Trennzeichen der
#: Dezimalstelle nicht.
KOMMA = {"de": ",", "en": ".", "es": ",", "fr": ",", "it": ",", "pt": ","}


@dataclass(frozen=True, slots=True)
class Paket:
    """Eine Datei, wie sie auf der Seite erscheint."""

    art: str
    name: str
    bytes_: int
    hash_: str

    def groesse(self, sprache: str) -> str:
        return f"{self.bytes_ / 1_000_000:.0f} MB".replace(".", KOMMA[sprache])


def erkennen(pfad: Path) -> str:
    """Zu welcher Plattform die Datei gehört — an ihrer Endung."""
    name = pfad.name.lower()
    for art, endungen, _ in PLATTFORMEN:
        if name.endswith(endungen):
            return art
    raise SystemExit(
        f"Zu {pfad.name} gehört keine bekannte Plattform. Erwartet werden "
        + ", ".join(e for _, endungen, _ in PLATTFORMEN for e in endungen)
        + "."
    )


def einlesen(pfade: list[Path]) -> list[Paket]:
    """Kopieren, messen, Prüfsumme rechnen — in der Reihenfolge der Plattformen."""
    ABLAGE.mkdir(parents=True, exist_ok=True)
    gefunden: dict[str, Paket] = {}
    for pfad in pfade:
        if not pfad.is_file():
            raise SystemExit(f"{pfad} gibt es nicht.")
        art = erkennen(pfad)
        if art in gefunden:
            raise SystemExit(f"Für {art} sind zwei Dateien angegeben — es geht nur eine.")

        ziel = ABLAGE / pfad.name
        if not (ziel.exists() and ziel.stat().st_size == pfad.stat().st_size):
            shutil.copy2(pfad, ziel)

        # In Blöcken, nicht am Stück: ein Installationspaket ist ein paar
        # hundert Megabyte, und die müssen nicht alle gleichzeitig im Speicher
        # liegen.
        digest = hashlib.sha256()
        with ziel.open("rb") as strom:
            while block := strom.read(1 << 20):
                digest.update(block)

        gefunden[art] = Paket(art, pfad.name, ziel.stat().st_size, digest.hexdigest())
        print(f"  {art:8s} {pfad.name}  {gefunden[art].groesse('de')}  {digest.hexdigest()[:16]}…")

    return [gefunden[art] for art, _, _ in PLATTFORMEN if art in gefunden]


def block(pakete: list[Paket], sprache: str) -> str:
    """Die Verweise, wie sie im Kasten stehen."""
    if not pakete:
        return (
            "\n            <!-- Von tools/make_download.py gefüllt. Steht hier nichts,\n"
            "                 bleibt der Kasten bei der Warteliste. -->\n          "
        )

    zeilen = []
    for stelle, paket in enumerate(pakete):
        beschriftung = next(namen[sprache] for art, _, namen in PLATTFORMEN if art == paket.art)
        klasse = "btn" if stelle == 0 else "btn ghost"
        zeilen.append(
            f'\n            <a class="{klasse}" href="/dl/{paket.name}" download>\n'
            '              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"'
            ' stroke-width="2" aria-hidden="true">\n'
            '                <path d="M12 3v12" stroke-linecap="round"/>'
            '<path d="m7 11 5 5 5-5" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M4 20h16" stroke-linecap="round"/>\n'
            "              </svg>\n"
            f"              {beschriftung} — {paket.groesse(sprache)}\n"
            "            </a>\n"
            f'            <code class="pruefsumme">SHA-256 {paket.hash_}</code>'
        )
    return "".join(zeilen) + "\n          "


def schreiben(pakete: list[Paket]) -> None:
    muster = re.compile(
        r'(<div class="dateien" data-files data-release-show hidden>)(.*?)(</div>)', re.DOTALL
    )
    for seite in SEITEN:
        p = WEBSITE / seite
        text = p.read_text(encoding="utf-8")
        sprache = seite.split("/")[0] if "/" in seite else "de"
        neu, anzahl = muster.subn(
            lambda m, s=sprache: m.group(1) + block(pakete, s) + m.group(3), text, count=1
        )
        if anzahl != 1:
            raise SystemExit(f"{seite}: der Dateikasten fehlt oder sieht anders aus.")
        p.write_text(neu, encoding="utf-8")
        print(f"  {seite}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pakete", nargs="*", type=Path, help="die fertigen Installationsdateien")
    args = parser.parse_args()

    if not args.pakete:
        print("Kein Paket angegeben — der Kasten wird geleert.")
        schreiben([])
        print("\nDie Seite bittet wieder um Nachricht.")
        return 0

    print("Pakete:")
    pakete = einlesen(args.pakete)
    print("\nSeiten:")
    schreiben(pakete)
    print(
        f"\nFertig. {len(pakete)} Paket(e) unter website/dl/, eingetragen in "
        f"{len(SEITEN)} Sprachfassungen.\nZum Termin schaltet die Seite von "
        "selbst um; ist er schon vorbei, gilt es ab dem nächsten Aufruf."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
