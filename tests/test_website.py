"""Die Startseite behauptet Zahlen — diese Datei prüft, dass sie stimmen.

Auf `website/index.html` steht eine Leiste mit sechs Kennzahlen: wie viele
Operationen im Register stehen, wie viele Bausteine es gibt, wie viele
Normteilmaße hinterlegt sind, wie viele Druckerprofile mitkommen und wie
viele Beispielprojekte beiliegen. Sie sind aus den Quellen abgelesen und
werden falsch, sobald eine Operation dazukommt — eine falsche Zahl auf einer
Verkaufsseite ist kein Schönheitsfehler.

Geprüft wird außerdem, dass beide Sprachfassungen dieselben Zahlen führen und
dass jede eingebundene Datei existiert.
"""

from __future__ import annotations

import re
import struct
import tomllib
from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge.parts.registry import PARTS
from app.core.registry import REGISTRY

WEBSITE = Path(__file__).resolve().parent.parent / "website"

#: Die Startseiten. Sie führen die Kennzahlen, das Angebot für Suchmaschinen
#: und die häufigen Fragen — nur sie werden auf diese Inhalte geprüft.
PAGES = ("index.html", "en/index.html")

#: Jede von Hand gepflegte Verkaufsseite. Handbuch und Rechtstexte stehen nicht
#: dabei: die erzeugt ein Werkzeug, und `test_manual.py` beziehungsweise
#: `test_legal.py` prüfen sie. Was hier steht, wird auf Aufbau geprüft —
#: Verweise, Bildmaße, Sprungmarken.
ALL_PAGES = (
    *PAGES,
    "funktionen.html",
    "ki-modelle.html",
    "en/features.html",
    "en/ai-models.html",
)
DATA = Path(__file__).resolve().parent.parent / "app" / "core" / "knowledge" / "data"
EXAMPLES = Path(__file__).resolve().parent.parent / "app" / "examples"

#: Ein Eintrag der Leiste sieht aus wie ``<div><b>61</b><span>…</span></div>``.
STAT = re.compile(r"<div><b>(\d+)</b><span>([^<]+)</span></div>")

#: Verweise auf Dateien — Netzadressen, Postadressen und Sprungmarken zählen
#: nicht dazu.
LINK = re.compile(r'(?:src|href)="([^"]+)"')


def _stats(page: str) -> list[int]:
    return [int(m.group(1)) for m in STAT.finditer((WEBSITE / page).read_text(encoding="utf-8"))]


def _count(table: str) -> int:
    """Zählt die Maßeinträge einer Normteil- oder Druckertabelle.

    ``version`` ist eine Angabe über die Tabelle, kein Eintrag in ihr.
    """
    loaded = tomllib.loads((DATA / table).read_text(encoding="utf-8"))
    return sum(len(v) for k, v in loaded.items() if k != "version" and isinstance(v, list))


@pytest.fixture(scope="module", autouse=True)
def _loaded() -> None:
    load_operations()


def test_the_number_of_operations_on_the_page_matches_the_registry() -> None:
    assert _stats("index.html")[0] == len(REGISTRY.all())


def test_the_number_of_building_blocks_on_the_page_matches_the_library() -> None:
    assert _stats("index.html")[1] == len(PARTS.all())


def test_the_number_of_standard_part_sizes_on_the_page_matches_the_table() -> None:
    assert _stats("index.html")[2] == _count("standards.toml")


def test_the_number_of_printer_profiles_on_the_page_matches_the_table() -> None:
    profiles = tomllib.loads((DATA / "printers.toml").read_text(encoding="utf-8"))
    assert _stats("index.html")[3] == len(profiles)


def test_the_number_of_examples_on_the_page_matches_the_folder() -> None:
    assert _stats("index.html")[4] == len(list(EXAMPLES.glob("*.p3d")))


def test_both_languages_state_the_same_numbers() -> None:
    assert _stats("index.html") == _stats("en/index.html")


def test_the_number_of_agent_cases_on_the_page_matches_the_suite() -> None:
    """Die Seite nennt die Größe der Agenten-Suite — auch diese Zahl wird
    falsch, sobald ein Referenzfall dazukommt oder wegfällt."""
    from tests.agent_cases import ALL_CASES

    for page, pattern in (
        ("index.html", r"(\d+) Referenzanfragen"),
        ("en/index.html", r"(\d+) reference requests"),
    ):
        text = (WEBSITE / page).read_text(encoding="utf-8")
        found = re.search(pattern, text)
        assert found is not None, f"{page} nennt die Suite nicht"
        assert int(found.group(1)) == len(ALL_CASES), page


@pytest.mark.parametrize("page", ALL_PAGES)
def test_every_file_the_page_refers_to_exists(page: str) -> None:
    source = WEBSITE / page
    missing = []
    for match in LINK.finditer(source.read_text(encoding="utf-8")):
        target = match.group(1)
        if target.startswith(("http", "mailto:", "#", "data:")):
            continue
        # Seit die Unterseiten dazugekommen sind, trägt ein Verweis auch eine
        # Sprungmarke: `/#preis` meint die Startseite und darin die Stelle.
        # Hier zählt die Datei davor — die Marke prüft der Test darunter.
        target = target.split("#", 1)[0]
        if not target:
            continue
        # Ein führender Schrägstrich meint die Wurzel der Website, kein
        # Wurzelverzeichnis der Festplatte.
        base = WEBSITE if target.startswith("/") else source.parent
        if not (base / target.lstrip("/")).exists():
            missing.append(target)
    assert not missing, f"{page} verweist auf {missing}"


@pytest.mark.parametrize("page", ALL_PAGES)
def test_every_picture_states_the_size_it_actually_has(page: str) -> None:
    """Falsche Maße lassen die Seite beim Laden springen.

    ``width`` und ``height`` reservieren den Platz, bevor das Bild da ist.
    Stimmen sie nicht, rutscht alles darunter im Moment des Ladens — und
    geschätzt hatte hier schon einmal jemand.
    """
    source = WEBSITE / page
    wrong = []
    for match in re.finditer(
        r'<img[^>]*src="([^"]+)"[^>]*width="(\d+)"[^>]*height="(\d+)"',
        source.read_text(encoding="utf-8"),
    ):
        path, stated = match.group(1), (int(match.group(2)), int(match.group(3)))
        # Die Maße stehen im IHDR-Block, gleich hinter der PNG-Signatur.
        header = (source.parent / path).read_bytes()[16:24]
        actual = struct.unpack(">II", header)
        if actual != stated:
            wrong.append(f"{path}: angegeben {stated}, tatsächlich {actual}")
    assert not wrong, wrong


@pytest.mark.parametrize("page", ALL_PAGES)
def test_every_jump_mark_the_navigation_offers_has_a_target(page: str) -> None:
    """Ein Sprung ins Leere merkt niemand beim Schreiben.

    Die Kopfzeile springt zu ``#funktionen`` und ``#preis``, das Angebot in
    der Auszeichnung für Suchmaschinen ebenfalls. Beide Sprachfassungen
    benennen ihre Abschnitte verschieden — genau deshalb wird hier geprüft
    und nicht verglichen.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([^"]+)"', text))
    marks = {m.lstrip("#") for m in re.findall(r'href="(#[^"]+)"', text)}
    marks |= set(re.findall(r'"https://solidon3d\.de[^"]*#([^"]+)"', text))
    assert marks <= ids, f"{page} springt auf {sorted(marks - ids)}"


@pytest.mark.parametrize("page", ALL_PAGES)
def test_every_jump_onto_another_page_lands_somewhere(page: str) -> None:
    """Die Unterseiten springen zurück in die Startseite — auf eine Stelle.

    ``/#preis`` und ``/en/#pricing`` stehen auf jeder Unterseite, im Kopf und
    am Fuß. Wird ein Abschnitt der Startseite umbenannt, zeigen sie ins Leere,
    und niemand merkt es: der Browser lädt die Seite und bleibt oben stehen.
    Diese Art Verweis gab es erst, seit Funktionen und KI-Modelle eigene
    Seiten haben.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    lost = []
    for target in re.findall(r'href="(/[^"#]*#[^"]+)"', text):
        path, mark = target.split("#", 1)
        name = path.lstrip("/") or "index.html"
        if name.endswith("/"):
            name += "index.html"
        other = WEBSITE / name
        # Ob die Datei überhaupt da ist, sagt der Test über diesem.
        if not other.exists():
            continue
        if mark not in set(re.findall(r'id="([^"]+)"', other.read_text(encoding="utf-8"))):
            lost.append(target)
    assert not lost, f"{page} springt auf eine Stelle, die es nicht gibt: {lost}"


#: Der Runner-Name eines Auftrags sagt, für welche Familie gepackt wird. Die
#: Paketmatrix steht als Liste da; die Suite-Matrix daneben baut ihre über
#: ``fromJSON`` und packt nichts — die eckige Klammer trennt beide.
PACKAGE_MATRIX = re.compile(r"^\s*os:\s*\[([^\]]+)\]", re.MULTILINE)

#: Wie ein Runner heißt und wie die Seite die Plattform nennt.
FAMILIES = {"windows": "Windows", "ubuntu": "Linux", "macos": "macOS"}

#: Womit eine Frage nach einer Plattform anfangen kann, wenn die Antwort Nein
#: lautet. Mehr braucht es nicht — geprüft wird der Satzanfang.
DENIALS = ("nein", "no,", "no.", "not for now", "nicht für jetzt")


def _packaged_platforms() -> set[str]:
    """Die Plattformen, für die die CI ein Paket baut.

    Gelesen wird der Auftrag selbst und keine gepflegte Liste daneben: Eine
    zweite Aufzählung würde genau dann falsch, wenn jemand die erste ändert.
    """
    workflow = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "build.yml"
    found = set()
    for match in PACKAGE_MATRIX.finditer(workflow.read_text(encoding="utf-8")):
        for runner in match.group(1).split(","):
            for prefix, name in FAMILIES.items():
                if runner.strip().startswith(prefix):
                    found.add(name)
    return found


@pytest.mark.parametrize("page", PAGES)
def test_the_markup_promises_exactly_the_platforms_the_build_produces(page: str) -> None:
    """Die Auszeichnung für Suchmaschinen ist die formalste Zusage der Seite.

    Sie ist auch die, die niemand liest — deshalb steht sie hier gegen den
    Bauauftrag. Nennt sie eine Plattform zu viel, sucht jemand ein Paket, das
    es nicht gibt; nennt sie eine zu wenig, findet ein Kunde uns gar nicht.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    found = re.search(r'"operatingSystem":\s*"([^"]+)"', text)
    assert found is not None, f"{page} zeichnet kein Betriebssystem aus"
    stated = found.group(1)
    for name in _packaged_platforms():
        assert name in stated, f"{page} lässt {name} aus, obwohl dafür gepackt wird"
    for name in set(FAMILIES.values()) - _packaged_platforms():
        assert name not in stated, f"{page} nennt {name}, dafür wird nichts gepackt"


@pytest.mark.parametrize("page", PAGES)
def test_no_answer_denies_a_platform_the_build_ships(page: str) -> None:
    """Eine Seite darf von einer Plattform nicht abraten, die sie ausliefert.

    Genau das stand hier: Vier Stellen nannten den Mac, und die FAQ-Antwort
    begann mit „Nein, vorerst nicht" — während `build.yml` seit je zwei
    Mac-Pakete baut, für Intel und Apple Silicon getrennt. Von den vier
    Stellen ist die Antwort die, die ein Kunde wirklich liest, und sie hat ihn
    weggeschickt. Der Widerspruch fiel keinem der übrigen Tests auf, weil
    keiner die Seite gegen den Bauauftrag hielt.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    shipped = _packaged_platforms()
    # Der Mac heißt in einer Frage „Mac", nicht „macOS".
    asked = {"macOS": ("mac",), "Windows": ("windows",), "Linux": ("linux",)}
    denied = []
    for block in re.finditer(
        r"<summary>(.*?)</summary>\s*<p>(.*?)[<.]", text, re.DOTALL | re.IGNORECASE
    ):
        question, answer = block.group(1).lower(), block.group(2).strip().lower()
        for name in shipped:
            if any(word in question for word in asked[name]) and answer.startswith(DENIALS):
                denied.append(f'{name}: „{block.group(2).strip()[:40]}…"')
    assert not denied, f"{page} rät von einer ausgelieferten Plattform ab: {denied}"


@pytest.mark.parametrize("page", ALL_PAGES)
def test_the_page_loads_nothing_from_outside(page: str) -> None:
    """Die Seite holt sich nichts von einem fremden Rechner.

    Das ist die Zusage, die auf der Seite selbst steht — kein Konto, keine
    Telemetrie —, und sie hängt nicht an gutem Willen: was nicht eingebunden
    ist, kann nicht mitlesen. Kein CDN, keine Schriftart von außen, keine
    Bibliothek, kein Zählpixel.

    Skripte **von der eigenen Seite** sind erlaubt, seit die Funktionsseite
    ihre Sprungliste markiert (`site.js`). Diese Prüfung sagt nicht mehr „kein
    JavaScript", sondern „nichts von außen" — der engere Teil der alten Regel,
    und der, der die Zusage trägt.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    for tag in re.findall(r"<script([^>]*)>", text):
        # Ein einzelner Schrägstrich meint die eigene Wurzel, zwei meinen einen
        # fremden Rechner mit dem Protokoll der Seite. ``//cdn.example.com/x.js``
        # sah wie ein eigener Pfad aus und bestand die Prüfung; das ``(?!/)``
        # ist der ganze Unterschied.
        allowed = 'type="application/ld+json"' in tag or re.search(r'src="/(?!/)[^"]*\.js"', tag)
        assert allowed, f"{page} bindet ein Skript ein, das nicht von hier kommt: {tag}"
    assert 'src="http' not in text
    assert 'href="http' not in text.replace('href="https://solidon3d.de', "")
    # Protokollrelativ, also ohne ``http`` im Text — die beiden Zeilen darüber
    # sehen davon nichts, und ein Zählpixel schreibt sich genau so.
    assert 'src="//' not in text, f"{page} lädt protokollrelativ von außen"
    assert 'href="//' not in text, f"{page} verweist protokollrelativ nach außen"


def test_no_self_arranging_grid_stops_shrinking_above_phone_width() -> None:
    """Ein `auto-fit`-Raster, das auf dem Telefon nicht mehr nachgibt.

    ``repeat(auto-fit, minmax(X, 1fr))`` nimmt Spalten weg, wenn das Fenster
    schmaler wird — aber die *letzte* verbleibende Spalte macht es **nicht**
    schmaler als ``X``. Bei den Wegekarten stand dort 34rem: Unter 544 px
    Fensterbreite stand eine Spalte da, und die war weiter 544 px breit. Weil
    `html` und `body` `overflow-x: clip` tragen, scrollte da auch nichts — auf
    einem 390er Telefon fehlten die rechten 150 px jeder Karte, und man kam
    nicht hin. Gemessen im laufenden Chromium; hier steht die Regel dagegen.

    **Geprüft wird nur `auto-fit` und `auto-fill`**, denn nur die geben das
    Versprechen, sich dem Fenster anzupassen. Ein von Hand gesetztes
    Spaltenpaar wie das der Kopfzeile ist etwas anderes: Es steht in einem
    ``@media (min-width: 68rem)``, gilt also erst, wo der Platz erwiesen da
    ist. Ein Test, der beide über einen Kamm schert, meldet dort einen Fehler,
    wo eine Entscheidung steht.

    Zwei Auswege gelten: ein Mindestmaß, das auf das schmalste verbreitete
    Telefon passt (320 px, also 20rem), oder ``min(X, 100%)`` — dann gibt die
    Spalte auf schmalen Fenstern nach und behält auf breiten ihr Maß.
    """
    css = (WEBSITE / "style.css").read_text(encoding="utf-8")
    # 320 px ist das schmalste noch verbreitete Telefon; die Seitenränder des
    # Rumpfes gehen davon ab, deshalb wird nicht ganz bis dorthin gemessen.
    narrowest_rem = 20.0
    too_wide = []
    for match in re.finditer(r"repeat\(\s*auto-(?:fit|fill)\s*,\s*minmax\(\s*([^,]+?)\s*,", css):
        floor = match.group(1).strip()
        if floor.startswith("min(") or floor in {"0", "auto", "min-content"}:
            continue
        size = re.fullmatch(r"([\d.]+)rem", floor)
        if size is None:
            continue
        if float(size.group(1)) > narrowest_rem:
            too_wide.append(match.group(0))
    assert not too_wide, (
        "Ein auto-fit-Raster hört über Telefonbreite auf zu schrumpfen und "
        f"wird dort abgeschnitten — min(…, 100%) um das Mindestmaß: {too_wide}"
    )
