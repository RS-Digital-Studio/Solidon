"""Trägt die Pakete in den Download-Kasten aller Sprachversionen ein.

Am Tag der Veröffentlichung liegen zwei bis drei Dateien bereit, und für jede
gehören drei Angaben auf die Seite: wofür sie ist, wie groß sie ist und was
ihre Prüfsumme ist. Mal sechs Sprachversionen sind das achtzehn Stellen, an
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
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.branding import APP_VERSION
from app.core import changes

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

WEBSITE = Path(__file__).resolve().parent.parent / "website"
STORE = WEBSITE / "dl"

#: Worüber die Verweise laufen. Nicht ``/dl/`` unmittelbar: Dazwischen steht
#: ``api/count.php``, das den Download zählt und dann auf die Datei
#: weiterleitet — sonst wüsste niemand, ob die Demo überhaupt geladen wird.
#: Ausgeliefert wird sie danach wieder vom Webserver selbst, damit ein
#: abgebrochener Download fortsetzbar bleibt. Fehlt die PHP-Datei auf dem
#: Server, führt der Verweis ins Leere — sie gehört zu jedem Hochladen dazu,
#: so wie ``api/support.php``.
COUNTER = "/api/count.php?f="

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
        (".appimage", ".tar.gz", ".tar.xz", ".flatpak"),
        dict.fromkeys(("de", "en", "es", "fr", "it", "pt"), "Linux"),
    ),
    (
        "macos",
        (".dmg", ".pkg", ".zip"),
        dict.fromkeys(("de", "en", "es", "fr", "it", "pt"), "macOS"),
    ),
)

#: Woran der Dateiname sagt, welche der mehreren Dateien einer Plattform er
#: ist — Architektur und Format. Die Reihenfolge ist die der Klammer hinter
#: dem Plattformnamen: „macOS (Apple Silicon, Archiv)".
#:
#: Marken werden nicht übersetzt (AppImage, Flatpak, Apple Silicon, Intel);
#: „Archiv" schon, denn das ist ein Wort und kein Name.
VARIANT_MARKS: tuple[tuple[str, dict[str, str]], ...] = (
    (
        "arm64",
        dict.fromkeys(("de", "en", "es", "fr", "it", "pt"), "Apple Silicon"),
    ),
    (
        "x86_64.pkg",
        dict.fromkeys(("de", "en", "es", "fr", "it", "pt"), "Intel"),
    ),
    (
        "x86_64.zip",
        dict.fromkeys(("de", "en", "es", "fr", "it", "pt"), "Intel"),
    ),
    (
        ".appimage",
        dict.fromkeys(("de", "en", "es", "fr", "it", "pt"), "AppImage"),
    ),
    (
        ".flatpak",
        dict.fromkeys(("de", "en", "es", "fr", "it", "pt"), "Flatpak"),
    ),
    (
        ".tar.gz",
        {
            "de": "Archiv mit Installationsskript",
            "en": "archive with install script",
            "es": "archivo con script de instalación",
            "fr": "archive avec script d'installation",
            "it": "archivio con script di installazione",
            "pt": "arquivo com script de instalação",
        },
    ),
    (
        ".zip",
        {
            "de": "Archiv",
            "en": "archive",
            "es": "archivo",
            "fr": "archive",
            "it": "archivio",
            "pt": "arquivo",
        },
    ),
)

#: Wie die Systeme im Fehlt-noch-Satz heißen. „Windows" heißt überall Windows,
#: die anderen beiden auch — die Namen sind Marken und werden nicht übersetzt.
SYSTEM_NAMES = {"windows": "Windows", "linux": "Linux", "macos": "macOS"}

#: Das Wort zwischen den letzten beiden Namen einer Aufzählung.
CONJUNCTION = {"de": "und", "en": "and", "es": "y", "fr": "et", "it": "e", "pt": "e"}

#: Der Satz, der im Kasten steht, solange nicht jede Plattform ein Paket hat.
#:
#: **Er steht da, weil die Seite drei Systeme nennt.** In den
#: Systemanforderungen und in der Zusicherungsliste verspricht sie Windows,
#: macOS und Linux; wer das liest und dann einen einzigen Knopf findet, hält
#: entweder die Seite für kaputt oder das Versprechen für eine Lüge. Der Satz
#: verschwindet von selbst, sobald alle Pakete übergeben werden — gepflegt
#: wird er nicht.
MISSING_NOTE = {
    "de": "Für {systems} sind die Pakete noch im Bau. Eine Nachricht, sobald sie liegen:",
    "en": "The {systems} packages are still building. A note as soon as they are up:",
    "es": "Los paquetes para {systems} aún se están creando. Aviso en cuanto estén:",
    "fr": "Les paquets pour {systems} sont encore en construction. Un message dès qu'ils sont là :",
    "it": "I pacchetti per {systems} sono ancora in costruzione. Un avviso appena ci sono:",
    "pt": "Os pacotes para {systems} ainda estão a ser criados. Um aviso assim que existirem:",
}

#: Welche Version dort liegt und seit wann.
#:
#: **Von Hand gepflegt wäre das die Zeile, die als Erste driftet.** Sie steht
#: neben Knöpfen, deren Dateinamen die Nummer schon tragen — und genau deshalb
#: fällt es niemandem auf, wenn sie eine Version hinterherhinkt. Geschrieben
#: wird sie deshalb hier, aus ``APP_VERSION`` und dem Tag des Laufs.
#:
#: Das Datum ist der Tag, an dem die Pakete entstehen, und nicht der des
#: Hochladens: Zwischen beiden liegt eine Viertelstunde, und wer es später von
#: Hand nachträgt, trägt es irgendwann nicht mehr nach.
VERSION_LINE = {
    "de": "Version {version}, erschienen am {date}.",
    "en": "Version {version}, released on {date}.",
    "es": "Versión {version}, publicada el {date}.",
    "fr": "Version {version}, parue le {date}.",
    "it": "Versione {version}, pubblicata il {date}.",
    "pt": "Versão {version}, publicada a {date}.",
}

#: Wie das Datum je Sprache geschrieben wird. Der Kunde liest es in seiner
#: Schreibweise, nicht in unserer — 23.08.2026 in Deutschland, 23/08/2026 in
#: Frankreich, „23 August 2026" im Englischen.
DATE_FORMAT = {
    "de": "{day}.{month}.{year}",
    "en": "{day} {month_name} {year}",
    "es": "{day}/{month}/{year}",
    "fr": "{day}/{month}/{year}",
    "it": "{day}/{month}/{year}",
    "pt": "{day}/{month}/{year}",
}

#: Nur Englisch schreibt den Monat aus.
MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


@dataclass(frozen=True, slots=True)
class Package:
    """Eine Datei, wie sie auf der Seite erscheint."""

    kind: str
    name: str
    bytes_: int
    hash_: str

    @property
    def size(self) -> str:
        """Ganze Megabyte — in jeder Sprache dieselbe Zeichenkette.

        Hier nahm die Methode eine Sprache und ersetzte den Dezimalpunkt durch
        das Trennzeichen des Landes. Bei ``:.0f`` steht nie einer da: Die
        Tabelle für sechs Sprachen war ohne Wirkung, solange der Kasten steht.
        Wer sie zurückholen will, braucht zuerst eine Dezimalstelle.
        """
        return f"{self.bytes_ / 1_000_000:.0f} MB"


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


def variant_of(name: str, language: str) -> str:
    """Wie die Zeile heißt, wenn eine Plattform mehr als eine Datei hat.

    **Eine Plattform, mehrere Wege.** Linux bekommt drei (AppImage, Archiv mit
    Installationsskript, Flatpak), macOS zwei mal zwei (Installationspaket und
    Archiv, je für Apple Silicon und Intel). Bis hierher ging nur eine Datei je
    Plattform, und die zweite war ein Abbruch mit „es geht nur eine".

    Die Plattform steht vorn und kommt aus :data:`PLATFORMS`; was hier
    dazukommt, ist die Unterscheidung dahinter. Erkannt wird sie am Dateinamen,
    denn dort steht sie ohnehin — die Bauwerkzeuge schreiben Architektur und
    Format hinein.
    """
    name = name.lower()
    marks: list[str] = []
    for needle, label in VARIANT_MARKS:
        if needle in name:
            marks.append(label[language])
    if not marks:
        return ""
    return " (" + ", ".join(marks) + ")"


def read_packages(paths: list[Path]) -> list[Package]:
    """Kopieren, messen, Prüfsumme rechnen — in der Reihenfolge der Plattformen."""
    STORE.mkdir(parents=True, exist_ok=True)
    found: list[Package] = []
    seen: set[str] = set()
    for path in paths:
        if not path.is_file():
            raise SystemExit(f"{path} gibt es nicht.")
        kind = kind_of(path)
        if path.name in seen:
            raise SystemExit(f"{path.name} ist zweimal angegeben.")
        seen.add(path.name)

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

        package = Package(kind, path.name, target.stat().st_size, digest.hexdigest())
        found.append(package)
        print(f"  {kind:8s} {path.name}  {package.size}  {digest.hexdigest()[:16]}…")

    # Die Reihenfolge im Kasten ist die der Plattformen, und innerhalb einer
    # Plattform die der übergebenen Dateien. Die erste ist zugleich das Ziel
    # des Knopfes beim Preis — deshalb steht Windows in PLATFORMS vorn.
    order = [kind for kind, _, _ in PLATFORMS]
    return sorted(found, key=lambda package: order.index(package.kind))


#: Der Pfeil nach unten, der auf jedem Ladeknopf steht.
ARROW = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"'
    ' aria-hidden="true">'
    '<path d="M12 3v12" stroke-linecap="round"/>'
    '<path d="m7 11 5 5 5-5" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M4 20h16" stroke-linecap="round"/></svg>'
)

#: Was auf dem Knopf einer Plattform steht, die mehrere Dateien hat.
CHOICE_LABEL = {
    "de": "{count} Pakete",
    "en": "{count} packages",
    "es": "{count} paquetes",
    "fr": "{count} paquets",
    "it": "{count} pacchetti",
    "pt": "{count} pacotes",
}

#: Die Zeile über der Auswahl im Dialog.
CHOICE_NOTE = {
    "de": "Welches passt, hängt von deinem System ab — jedes enthält dieselbe Anwendung.",
    "en": "Which one fits depends on your system — each contains the same application.",
    "es": "Cuál encaja depende de tu sistema: todos contienen la misma aplicación.",
    "fr": "Lequel convient dépend de votre système — tous contiennent la même application.",
    "it": "Quale sia adatto dipende dal sistema — ognuno contiene la stessa applicazione.",
    "pt": "Qual serve depende do teu sistema — todos contêm a mesma aplicação.",
}

#: Der Knopf, der den Dialog wieder zumacht.
CLOSE_LABEL = {
    "de": "Schließen",
    "en": "Close",
    "es": "Cerrar",
    "fr": "Fermer",
    "it": "Chiudi",
    "pt": "Fechar",
}


def download_link(package: Package, label: str, css_class: str) -> str:
    """Ein Ladeknopf für genau eine Datei."""
    return (
        f'\n            <a class="{css_class}" href="{COUNTER}{quote(package.name)}"'
        f' download="{package.name}">'
        f"{ARROW} {label} — {package.size}</a>"
    )


def links(packages: list[Package], language: str) -> str:
    """Die Verweise, wie sie im Kasten stehen — ein Knopf je Plattform.

    **Warum nicht eine Zeile je Datei.** Acht Pakete sind acht Knöpfe, und
    sieben davon gehen den Leser nichts an: Wer auf einem Mac sitzt, braucht
    keine Auswahl zwischen Flatpak und AppImage. Also trägt jede Plattform
    einen Knopf; hat sie mehr als eine Datei, öffnet er einen Dialog mit
    dieser einen Frage.

    **Keine ``<div>`` im erzeugten Text.** ``write_pages`` schneidet den
    Kasten mit einem Ausdruck heraus, der beim ersten ``</div>`` endet — ein
    Behälter hier drin würde ihn mitten im Kasten abschneiden. ``dialog``,
    ``form`` und ``p`` tun dasselbe und tun es nicht.
    """
    if not packages:
        return (
            "\n            <!-- Von tools/make_download.py gefüllt. Steht hier nichts,\n"
            "                 bleibt der Kasten bei der Warteliste. -->\n          "
        )

    rows: list[str] = []
    for position, (kind, _, names) in enumerate(
        entry for entry in PLATFORMS if any(p.kind == entry[0] for p in packages)
    ):
        mine = [package for package in packages if package.kind == kind]
        system = names[language]
        # Der erste Knopf ist der gefüllte; alles Weitere steht daneben.
        css_class = "btn" if position == 0 else "btn ghost"

        if len(mine) == 1:
            # Die Bauart steht auch dann dabei, wenn es nur eine gibt: Hinter
            # „Linux" ein Flatpak zu finden, das erst eingerichtet sein will,
            # ist eine Überraschung an der falschen Stelle. Bei Windows liefert
            # `variant_of` nichts, und dann steht auch nichts da.
            rows.append(
                download_link(mine[0], system + variant_of(mine[0].name, language), css_class)
            )
            continue

        count = CHOICE_LABEL[language].format(count=len(mine))
        choices = "".join(
            download_link(package, variant_of(package.name, language).strip(" ()"), "btn")
            for package in mine
        )
        rows.append(
            f'\n            <button class="{css_class}" type="button"'
            f' data-choice="{kind}">{ARROW} {system} — {count}</button>'
            f'\n            <dialog class="auswahl" id="wahl-{kind}"'
            f' aria-label="{system}">'
            f"\n              <h3>{system}</h3>"
            f'\n              <p class="hinweis">{CHOICE_NOTE[language]}</p>'
            f"{choices}"
            '\n              <form method="dialog">'
            f'<button class="btn ghost" value="zu">{CLOSE_LABEL[language]}</button></form>'
            "\n            </dialog>"
        )
    return (
        "".join(rows) + version_line(language) + missing_note(packages, language) + "\n          "
    )


def version_line(language: str, today: date | None = None) -> str:
    """Welche Version im Kasten liegt und seit wann.

    Robert wollte beides sichtbar, und er hat recht: Die Dateinamen tragen die
    Nummer, aber niemand liest einen Dateinamen, um zu erfahren, ob sich seit
    dem letzten Besuch etwas getan hat. Ein Datum beantwortet das in einem
    Blick.

    Das Datum ist der Tag des **Laufs**, nicht des Hochladens — die
    Viertelstunde dazwischen ist keine, die jemand nachträgt.
    """
    stamp = today or date.today()
    fmt = DATE_FORMAT[language]
    written = fmt.format(
        day=stamp.day,
        month=f"{stamp.month:02d}",
        year=stamp.year,
        month_name=MONTH_NAMES[stamp.month - 1],
    )
    text = VERSION_LINE[language].format(version=APP_VERSION, date=written)
    return f'\n            <p class="version">{text}</p>'


def missing_note(packages: list[Package], language: str) -> str:
    """Was noch fehlt, in einem Satz — oder nichts, wenn nichts fehlt."""
    from app.branding import SUPPORT_ADDRESS

    missing = [
        SYSTEM_NAMES[kind]
        for kind, _, _ in PLATFORMS
        if not any(package.kind == kind for package in packages)
    ]
    if not missing or not packages:
        return ""

    if len(missing) == 1:
        systems = missing[0]
    else:
        systems = f"{', '.join(missing[:-1])} {CONJUNCTION[language]} {missing[-1]}"
    return (
        f'\n            <p class="pruefhinweis">'
        f"{MISSING_NOTE[language].format(systems=systems)} "
        f'<a href="mailto:{SUPPORT_ADDRESS}">{SUPPORT_ADDRESS}</a></p>'
    )


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


#: Die Versionsdatei. Sie sagt der laufenden Anwendung, dass es etwas Neueres
#: gibt — und seit §37.2 auch, wo es liegt und woran man es erkennt.
VERSION_FILE = WEBSITE / "version.json"

#: Welcher Paketschlüssel in der Versionsdatei zu welcher Datei gehört.
#:
#: **Nur was sich starten lässt, steht dort.** Ein ``.zip`` entpackt sich, ein
#: AppImage ersetzt sich nicht selbst, ein Flatpak will ``flatpak update`` —
#: sie alle stehen im Download-Kasten, aber ein Eintrag in der Versionsdatei
#: heißt für die Anwendung „das kannst du holen und starten". Ein Paket dort,
#: das beim Doppelklick nichts tut, wäre schlimmer als keines.
#:
#: Die Architektur steht nur bei macOS im Schlüssel: Ein für arm64 gebautes
#: Programm startet auf einem Intel-Mac nicht.
VERSION_KEYS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("windows", ".exe", ()),
    ("macos-arm64", ".pkg", ("arm64",)),
    ("macos-x86_64", ".pkg", ("x86_64", "x64", "intel")),
)


def version_key(package: Package) -> str:
    """Unter welchem Schlüssel das Paket in der Versionsdatei steht, wenn
    überhaupt."""
    name = package.name.lower()
    for key, suffix, marks in VERSION_KEYS:
        if not name.endswith(suffix):
            continue
        if not marks or any(mark in name for mark in marks):
            return key
    return ""


#: Wo die kundenlesbaren Punkte je Sprache stehen. Je Sprache eine Datei, wie
#: bei den Katalogen — und keine davon ist eine Liste der Änderungen: Was hier
#: steht, ist die Auswahl, die jemand getroffen hat.
CHANGELOG = Path(__file__).resolve().parent.parent / "changelog"

#: Die Zeile, die einen Versionsabschnitt eröffnet: ``## 0.1.2``.
SECTION = re.compile(r"^##\s+(\S+)\s*$")

#: Eine Zeile der Liste darunter.
BULLET = re.compile(r"^[-*]\s+(.*\S)\s*$")


def changelog_for(version: str, language: str) -> list[str]:
    """Die Punkte einer Version in einer Sprache, oder eine leere Liste.

    **Gelesen wird im Kern** (``app.core.changes``), seit der Verlauf auch in
    der Anwendung steht — unter *Hilfe → Neuerungen*. Zwei Umsetzungen wären
    der Weg zu einem Verlauf, der sich unterscheidet, je nachdem wer ihn liest:
    Das Bauwerkzeug schriebe eine Auswahl in die Versionsdatei und das Fenster
    zeigte eine andere.

    Ohne Rückfall auf die Quellsprache, anders als :func:`changes.history`: Was
    hier entsteht, wird je Sprache in die Versionsdatei geschrieben, und dort
    ist eine fehlende Sprache eine Auskunft — die Anwendung fällt selbst zurück
    (``updates.Release.points``). Ein deutscher Satz unter ``"it"`` sähe dagegen
    aus wie eine Übersetzung, die es nicht gibt.
    """
    return list(changes.points_for(version, language) if file_of(language).is_file() else ())


def file_of(language: str) -> Path:
    """Die Changelog-Datei einer Sprache — hier im Repository."""
    return CHANGELOG / f"{language}.md"


def changes_for(version: str) -> dict[str, list[str]]:
    """Die Punkte in jeder Sprache, die eine Datei hat.

    Eine Sprache ohne Abschnitt fehlt hier, statt leer dazustehen: Die
    Anwendung fällt dann auf Deutsch zurück, und ein deutscher Satz ist besser
    als eine Überschrift ohne Inhalt darunter.
    """
    found: dict[str, list[str]] = {}
    for file in sorted(CHANGELOG.glob("*.md")):
        points = changelog_for(version, file.stem)
        if points:
            found[file.stem] = points
    return found


def write_version(packages: list[Package]) -> None:
    """Trägt Version und Pakete in ``website/version.json`` ein.

    Von Hand gepflegt wäre das eine Prüfsumme an einer zweiten Stelle, und die
    zweite Stelle ist immer die, die driftet. Gerechnet sind sie hier ohnehin
    schon — für den Kasten.

    ``url``, ``notes`` und ``notes_by_language`` bleiben unberührt: Die eine
    ist die Adresse der Seite, die anderen ein Satz, den ein Mensch schreibt —
    einmal ohne Sprachangabe für die Fassungen bis 0.1.5, die das zweite Feld
    noch nicht kennen, und einmal je Sprache für alle seither. Ohne Pakete — also
    beim Zurückziehen — verschwindet nur die Paketliste. Die Anwendung fällt
    dann auf den Hinweis zurück und zeigt auf die Download-Seite, statt etwas
    anzubieten, das nicht mehr liegt.
    """
    if not VERSION_FILE.is_file():
        raise SystemExit(
            f"{VERSION_FILE.name} gibt es nicht. Sie trägt die Adresse der Seite und "
            "den Hinweistext; angelegt wird sie von Hand, nicht hier."
        )
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    site = str(data.get("url") or "").rstrip("/")
    if not site.startswith("https://"):
        raise SystemExit(
            f"In {VERSION_FILE.name} steht keine https-Adresse unter 'url'. "
            "Die Anwendung holt ein Paket nur von demselben Rechnernamen (§37.2)."
        )

    entries: dict[str, dict[str, object]] = {}
    for package in packages:
        key = version_key(package)
        if not key:
            continue
        entries[key] = {
            "file": package.name,
            "url": f"{site}{COUNTER}{quote(package.name)}",
            "size": package.bytes_,
            "sha256": package.hash_,
        }

    data["version"] = APP_VERSION
    changes = changes_for(APP_VERSION)
    if changes:
        data["changes"] = changes
    else:
        data.pop("changes", None)
    if entries:
        data["packages"] = entries
    else:
        data.pop("packages", None)
    # **Die alte Unterschrift ist mit diesem Schreiben hinfällig** (§37.2): Sie
    # galt dem alten Inhalt, und der ist gerade ersetzt worden. Stehen lassen
    # wäre schlimmer als weglassen — eine Datei mit einer Unterschrift, die
    # nicht trägt, sieht unterschrieben aus.
    data.pop("signature", None)
    VERSION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "  version.json: ohne Unterschrift geschrieben — vor dem Hochladen:\n"
        "    python tools/sign_version.py --private <datei>"
    )

    if entries:
        print(f"  version.json: {APP_VERSION}, {len(entries)} startbare(s) Paket(e)")
        if changes:
            count = len(next(iter(changes.values())))
            print(f"    {count} Punkt(e) in {len(changes)} Sprache(n)")
        else:
            print(
                f"    kein Abschnitt ## {APP_VERSION} in changelog/ — "
                "das Fenster zeigt dann nur den Hinweistext"
            )
        for key in entries:
            print(f"    {key}")
    else:
        print(f"  version.json: {APP_VERSION}, ohne Pakete — die Anwendung zeigt auf die Seite")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("packages", nargs="*", type=Path, help="die fertigen Installationsdateien")
    args = parser.parse_args()

    if not args.packages:
        print("Kein Paket angegeben — der Kasten wird geleert.")
        write_pages([])
        write_version([])
        print("\nDie Seite bittet wieder um Nachricht.")
        return 0

    print("Pakete:")
    packages = read_packages(args.packages)
    print("\nSeiten:")
    write_pages(packages)
    print("\nVersionsdatei:")
    write_version(packages)
    print(
        f"\nFertig. {len(packages)} Paket(e) unter website/dl/, eingetragen in "
        f"{len(PAGES)} Sprachversionen.\nZum Termin schaltet die Seite von "
        "selbst um; ist er schon vorbei, gilt es ab dem nächsten Aufruf."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
