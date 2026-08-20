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

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

WEBSITE = Path(__file__).resolve().parent.parent / "website"
STORE = WEBSITE / "dl"

#: Die Startseiten, die einen Download-Kasten tragen.
PAGES = ("index.html", *(f"{code}/index.html" for code in ("en", "es", "fr", "it", "pt")))

#: Woran eine Datei ihre Plattform erkennen lässt, und wie die Zeile dann in
#: jeder Sprache heißt. Die Reihenfolge hier ist die Reihenfolge im Kasten —
#: und die erste ist zugleich das Ziel des Knopfes beim Preis.
PLATFORMS: tuple[tuple[str, tuple[str, ...], dict[str, str]], ...] = (
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
DECIMAL_MARK = {"de": ",", "en": ".", "es": ",", "fr": ",", "it": ",", "pt": ","}


@dataclass(frozen=True, slots=True)
class Package:
    """Eine Datei, wie sie auf der Seite erscheint."""

    kind: str
    name: str
    bytes_: int
    hash_: str

    def size(self, language: str) -> str:
        return f"{self.bytes_ / 1_000_000:.0f} MB".replace(".", DECIMAL_MARK[language])


def kind_of(path: Path) -> str:
    """Zu welcher Plattform die Datei gehört — an ihrer Endung."""
    name = path.name.lower()
    for kind, suffixes, _ in PLATFORMS:
        if name.endswith(suffixes):
            return kind
    raise SystemExit(
        f"Zu {path.name} gehört keine bekannte Plattform. Erwartet werden "
        + ", ".join(e for _, suffixes, _ in PLATFORMS for e in suffixes)
        + "."
    )


def read_packages(paths: list[Path]) -> list[Package]:
    """Kopieren, messen, Prüfsumme rechnen — in der Reihenfolge der Plattformen."""
    STORE.mkdir(parents=True, exist_ok=True)
    found: dict[str, Package] = {}
    for path in paths:
        if not path.is_file():
            raise SystemExit(f"{path} gibt es nicht.")
        kind = kind_of(path)
        if kind in found:
            raise SystemExit(f"Für {kind} sind zwei Dateien angegeben — es geht nur eine.")

        target = STORE / path.name
        if not (target.exists() and target.stat().st_size == path.stat().st_size):
            shutil.copy2(path, target)

        # In Blöcken, nicht am Stück: ein Installationspaket ist ein paar
        # hundert Megabyte, und die müssen nicht alle gleichzeitig im Speicher
        # liegen.
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            while chunk := stream.read(1 << 20):
                digest.update(chunk)

        found[kind] = Package(kind, path.name, target.stat().st_size, digest.hexdigest())
        print(f"  {kind:8s} {path.name}  {found[kind].size('de')}  {digest.hexdigest()[:16]}…")

    return [found[kind] for kind, _, _ in PLATFORMS if kind in found]


def links(packages: list[Package], language: str) -> str:
    """Die Verweise, wie sie im Kasten stehen."""
    if not packages:
        return (
            "\n            <!-- Von tools/make_download.py gefüllt. Steht hier nichts,\n"
            "                 bleibt der Kasten bei der Warteliste. -->\n          "
        )

    rows = []
    for position, package in enumerate(packages):
        label = next(names[language] for kind, _, names in PLATFORMS if kind == package.kind)
        css_class = "btn" if position == 0 else "btn ghost"
        rows.append(
            f'\n            <a class="{css_class}" href="/dl/{package.name}" download>\n'
            '              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"'
            ' stroke-width="2" aria-hidden="true">\n'
            '                <path d="M12 3v12" stroke-linecap="round"/>'
            '<path d="m7 11 5 5 5-5" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M4 20h16" stroke-linecap="round"/>\n'
            "              </svg>\n"
            f"              {label} — {package.size(language)}\n"
            "            </a>\n"
            f'            <code class="pruefsumme">SHA-256 {package.hash_}</code>'
        )
    return "".join(rows) + "\n          "


def write_pages(packages: list[Package]) -> None:
    pattern = re.compile(
        r'(<div class="dateien" data-files data-release-show hidden>)(.*?)(</div>)', re.DOTALL
    )
    for page in PAGES:
        p = WEBSITE / page
        text = p.read_text(encoding="utf-8")
        language = page.split("/")[0] if "/" in page else "de"
        updated, count = pattern.subn(
            lambda m, s=language: m.group(1) + links(packages, s) + m.group(3), text, count=1
        )
        if count != 1:
            raise SystemExit(f"{page}: der Dateikasten fehlt oder sieht anders aus.")
        p.write_text(updated, encoding="utf-8")
        print(f"  {page}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("packages", nargs="*", type=Path, help="die fertigen Installationsdateien")
    args = parser.parse_args()

    if not args.packages:
        print("Kein Paket angegeben — der Kasten wird geleert.")
        write_pages([])
        print("\nDie Seite bittet wieder um Nachricht.")
        return 0

    print("Pakete:")
    packages = read_packages(args.packages)
    print("\nSeiten:")
    write_pages(packages)
    print(
        f"\nFertig. {len(packages)} Paket(e) unter website/dl/, eingetragen in "
        f"{len(PAGES)} Sprachfassungen.\nZum Termin schaltet die Seite von "
        "selbst um; ist er schon vorbei, gilt es ab dem nächsten Aufruf."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
