"""Die Startseite behauptet Zahlen — diese Datei prüft, dass sie stimmen.

Auf `website/index.html` steht eine Leiste mit sechs Kennzahlen: wie viele
Operationen im Register stehen, wie viele Bausteine es gibt, wie viele
Normteilmaße hinterlegt sind, wie viele Druckerprofile mitkommen und wie
viele Beispielprojekte beiliegen. Sie sind aus den Quellen abgelesen und
werden falsch, sobald eine Operation dazukommt — eine falsche Zahl auf einer
Verkaufsseite ist kein Schönheitsfehler.

Geprüft wird außerdem, dass beide Sprachfassungen dieselben Zahlen führen und
dass jede eingebundene Datei existiert.

Dieselbe Zahl steht ein zweites Mal im Fließtext — auf der Funktionsseite und
in den häufigen Fragen. Die Leiste allein zu prüfen reichte nicht: sie stand
längst auf 85, während der Satz daneben 83 behauptete und die englische
Fassung 84. Was im Text steht, wird darum über **alle** Seiten geprüft, auch
über die, die diese Datei sonst nicht kennt.
"""

from __future__ import annotations

import re
import struct
import tomllib
from datetime import datetime
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

#: Die Registergröße im Fließtext: eine Zahl, dahinter das Wort für Operation.
#: Der Stamm „oper“ trägt durch alle sechs Sprachen — Operationen, operations,
#: operaciones, opérations, operazioni, operações. Eine siebte Sprache ist
#: damit mitgeprüft, ohne dass hier jemand etwas nachträgt.
OPERATION_COUNT = re.compile(r"(\d+)(?:&nbsp;|\s)+[Oo]per\w*")

#: Die Illustrationen sind Inline-SVG und führen erfundene Beispielzahlen
#: („Vorschlag — 3 Operationen“). Das ist keine Aussage über das Register.
INLINE_SVG = re.compile(r"<svg\b.*?</svg>", re.DOTALL)


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


def test_no_page_names_a_different_number_of_operations_in_its_text() -> None:
    """Jede Nennung der Registergröße im Fließtext, auf jeder Seite.

    Nicht `ALL_PAGES`, sondern was tatsächlich unter `website/` liegt: die
    Sprachfassungen kommen einzeln dazu, und eine Zahl, die auf der
    portugiesischen Seite veraltet, ist genauso falsch wie auf der deutschen.
    Fehlt eine Sprache noch, prüft der Lauf sie eben nicht — er wird nicht rot,
    weil jemand sie noch nicht eingecheckt hat.
    """
    expected = len(REGISTRY.all())
    wrong = []
    for page in sorted([*WEBSITE.glob("*.html"), *WEBSITE.glob("*/*.html")]):
        prose = INLINE_SVG.sub("", page.read_text(encoding="utf-8"))
        for found in OPERATION_COUNT.finditer(prose):
            if int(found.group(1)) != expected:
                wrong.append(f"{page.relative_to(WEBSITE).as_posix()}: „{found.group(0)}“")
    assert not wrong, f"das Register führt {expected} Operationen, die Seiten sagen {wrong}"


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


def _webp_size(picture: Path) -> tuple[int, int]:
    """Breite und Höhe einer WebP-Datei, ohne sie zu dekodieren.

    Anders als PNG kennt WebP drei Kopfvarianten, und sie schreiben das Maß an
    drei verschiedene Stellen. Wer blind acht Bytes hinter der Signatur liest —
    wie es beim PNG geht — bekommt hier eine Größe wie 167 772 160 × 268 435 456
    heraus und hält sie für ein falsch ausgezeichnetes Bild.
    """
    payload = picture.read_bytes()
    kind = payload[12:16]
    if kind == b"VP8X":
        # Erweitert (das ist die Variante mit Alphakanal): je drei Bytes,
        # niederwertig zuerst, und gespeichert wird das Maß minus eins.
        breite = int.from_bytes(payload[24:27], "little") + 1
        hoehe = int.from_bytes(payload[27:30], "little") + 1
        return breite, hoehe
    if kind == b"VP8L":
        gepackt = int.from_bytes(payload[21:25], "little")
        return (gepackt & 0x3FFF) + 1, ((gepackt >> 14) & 0x3FFF) + 1
    if kind == b"VP8 ":
        return (
            int.from_bytes(payload[26:28], "little") & 0x3FFF,
            int.from_bytes(payload[28:30], "little") & 0x3FFF,
        )
    raise AssertionError(f"{picture.name}: unbekannte WebP-Variante {kind!r}")


@pytest.mark.parametrize("page", ALL_PAGES)
def test_every_picture_states_the_size_it_actually_has(page: str) -> None:
    """Falsche Maße lassen die Seite beim Laden springen.

    ``width`` und ``height`` reservieren den Platz, bevor das Bild da ist.
    Stimmen sie nicht, rutscht alles darunter im Moment des Ladens — und
    geschätzt hatte hier schon einmal jemand.

    Beide Formate werden gelesen. Solange nur Bildschirmfotos ein Maß trugen,
    reichte der IHDR-Block; seit auch die Musterkachel eines angibt, sind
    dieselben acht Bytes in einer SVG-Datei irgendein Stück XML und ergeben
    eine Größe wie 1 936 682 086 × 1 634 496 032.
    """
    source = WEBSITE / page
    wrong = []
    for match in re.finditer(
        r'<img[^>]*src="([^"]+)"[^>]*width="(\d+)"[^>]*height="(\d+)"',
        source.read_text(encoding="utf-8"),
        re.DOTALL,
    ):
        path, stated = match.group(1), (int(match.group(2)), int(match.group(3)))
        picture = source.parent / path
        if picture.suffix == ".svg":
            # Gezeichnetes hat keine Pixel, nur einen Zeichenbereich.
            box = re.search(
                r'viewBox="[\d.-]+ [\d.-]+ ([\d.]+) ([\d.]+)"',
                picture.read_text(encoding="utf-8")[:2000],
            )
            assert box is not None, f"{path}: gibt ein Maß an, hat aber keine viewBox"
            actual = (round(float(box.group(1))), round(float(box.group(2))))
        elif picture.suffix == ".webp":
            actual = _webp_size(picture)
        else:
            # Die Maße stehen im IHDR-Block, gleich hinter der PNG-Signatur.
            actual = struct.unpack(">II", picture.read_bytes()[16:24])
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


#: Der Zähler im Download-Kasten — Zielzeitpunkt und übersetzter Rahmensatz.
COUNTDOWN = re.compile(r'data-countdown="([^"]+)"\s+data-template="([^"]+)"')


def _start_pages() -> list[Path]:
    """Alle Startseiten, auch die vier, die `PAGES` nicht kennt.

    `PAGES` führt Deutsch und Englisch, weil nur dort die Kennzahlenleiste
    geprüft wird. Der Zähler steht auf allen sechs, und genau darum wird hier
    gesucht statt aufgezählt: eine siebte Sprache ist mitgeprüft, sobald ihr
    Ordner ein `index.html` enthält.
    """
    return sorted(WEBSITE.glob("index.html")) + sorted(WEBSITE.glob("*/index.html"))


def test_every_start_page_counts_down_to_the_same_moment() -> None:
    """Sechs Sprachfassungen, ein Termin.

    Der Zielzeitpunkt steht im Markup, nicht im Skript — sonst stünde er an
    einer Stelle, die keine Sprachfassung liest. Der Preis dafür ist, dass er
    sechsmal dasteht, und der Fehler, der dann passiert, ist immer derselbe:
    fünf werden geändert und eine nicht.

    Die **Zeitzone gehört dazu**. Ohne sie deutet jeder Browser die Angabe als
    Ortszeit seines Besuchers, und der Zähler in Lissabon liefe eine Stunde
    hinter dem in Berlin — beide auf denselben Satz zeigend, der eine Uhrzeit
    nennt.
    """
    pages = _start_pages()
    assert len(pages) >= 2, "keine Startseiten gefunden — stimmt der Pfad?"
    moments = {}
    for page in pages:
        name = page.relative_to(WEBSITE).as_posix()
        found = COUNTDOWN.findall(page.read_text(encoding="utf-8"))
        assert len(found) == 1, f"{name} trägt {len(found)} Zähler, erwartet ist genau einer"
        moment, template = found[0]
        stamp = datetime.fromisoformat(moment)
        assert stamp.tzinfo is not None, (
            f"{name} nennt den Zeitpunkt ohne Zeitzone ({moment}) — "
            "jeder Browser deutet ihn dann als seine eigene Ortszeit"
        )
        assert "{rest}" in template, (
            f"{name} hat einen Rahmensatz ohne Platzhalter ({template!r}) — "
            "der Zähler hätte nichts, wohin er seine Zeit schreiben könnte"
        )
        moments[name] = stamp
    assert len(set(moments.values())) == 1, (
        f"die Startseiten zählen auf verschiedene Termine: {moments}"
    )


def test_every_page_with_a_countdown_loads_the_script_that_runs_it() -> None:
    """Ein Zähler ohne Skript ist ein leerer Absatz.

    Er steht als `hidden` im Markup und wird erst sichtbar, wenn `site.js`
    ihn füllt. Fehlt die Einbindung, fällt das niemandem auf: die Seite sieht
    aus wie vorher, nur zählt nichts. Ein Fehler, der nichts kaputt macht,
    wird sonst erst bemerkt, wenn der Termin vorbei ist.
    """
    for page in _start_pages():
        text = page.read_text(encoding="utf-8")
        if "data-countdown" not in text:
            continue
        name = page.relative_to(WEBSITE).as_posix()
        assert 'src="/site.js"' in text, f"{name} trägt einen Zähler, bindet aber site.js nicht ein"


# --------------------------------------------------------------------------
# Was Suchmaschinen zuerst holen — erzeugt von `tools/make_seo.py`.
# --------------------------------------------------------------------------


#: Der Nachweis für die Search Console — eine Zeile Text mit der Endung
#: ``.html``, keine Seite. Er muss unter seinem Namen erreichbar sein und
#: gehört genau deshalb weder in die Sitemap noch in eine Prüfung, die
#: Seiten meint.
VERIFICATION = re.compile(r"^google[0-9a-f]+\.html$")


def _delivered_pages() -> list[Path]:
    """Jede ausgelieferte Seite: oberste Ebene und Sprachordner."""
    found = [*WEBSITE.glob("*.html"), *WEBSITE.glob("*/*.html")]
    return sorted(p for p in found if not VERIFICATION.match(p.name))


def _address(page: Path) -> str:
    """Die Adresse einer Seite — die Startseite heißt nach ihrem Ordner."""
    rest = re.sub(r"(^|/)index\.html$", r"\1", page.relative_to(WEBSITE).as_posix())
    return "https://solidon3d.de/" + rest


def test_the_sitemap_lists_every_page_that_is_delivered() -> None:
    """Eine Seite, die nicht in der Sitemap steht, wird über Links gefunden.

    Bei einer Domain ohne eingehende Verweise heißt „über Links" Monate. Die
    Sitemap wird erzeugt, deshalb ist der Fehlerfall nicht, dass jemand einen
    Eintrag vergisst — sondern dass jemand eine Seite anlegt und das Werkzeug
    nicht laufen lässt.
    """
    sitemap = (WEBSITE / "sitemap.xml").read_text(encoding="utf-8")
    listed = set(re.findall(r"<loc>([^<]+)</loc>", sitemap))
    expected = {
        _address(p) for p in _delivered_pages() if "noindex" not in p.read_text(encoding="utf-8")
    }
    assert expected <= listed, f"nicht in der Sitemap: {sorted(expected - listed)}"


def test_the_sitemap_offers_no_page_that_asks_not_to_be_indexed() -> None:
    """Die fünf Rechtstexte tragen `noindex`, und das ist eine Entscheidung.

    Eine Sitemap, die sie trotzdem anbietet, sagt das Gegenteil dessen, was
    auf der Seite selbst steht. Die Search Console meldet den Widerspruch als
    Fehler, und welches der beiden Signale gewinnt, entscheidet dann Google
    statt uns.
    """
    sitemap = (WEBSITE / "sitemap.xml").read_text(encoding="utf-8")
    listed = set(re.findall(r"<loc>([^<]+)</loc>", sitemap))
    contradicting = listed & {
        _address(p) for p in _delivered_pages() if "noindex" in p.read_text(encoding="utf-8")
    }
    assert not contradicting, f"noindex und trotzdem in der Sitemap: {sorted(contradicting)}"


def test_the_sitemap_names_no_page_that_is_gone() -> None:
    """Der umgekehrte Fall: eine gelöschte Seite bleibt in der Liste stehen."""
    sitemap = (WEBSITE / "sitemap.xml").read_text(encoding="utf-8")
    for address in re.findall(r"<loc>([^<]+)</loc>", sitemap):
        rest = address.removeprefix("https://solidon3d.de/")
        target = WEBSITE / (rest if rest.endswith(".html") else rest + "index.html")
        assert target.exists(), f"die Sitemap führt {address}, die Datei fehlt"


def test_robots_points_at_the_sitemap() -> None:
    """Ohne diese Zeile muss ein Crawler die Sitemap erraten."""
    robots = (WEBSITE / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap: https://solidon3d.de/sitemap.xml" in robots


@pytest.mark.parametrize("page", PAGES)
def test_the_questions_are_marked_up_the_way_they_are_written(page: str) -> None:
    """Die Auszeichnung der Fragen wird aus dem Markup abgeleitet.

    Läuft `tools/make_seo.py` nach einer neuen Frage nicht, steht in der
    Auszeichnung eine Frage weniger als auf der Seite — und was Google als
    Rich Result zeigt, ist dann nicht, was dort steht.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    written = len(re.findall(r"<summary>", text))
    marked = len(re.findall(r'"@type": "Question"', text))
    assert written == marked, f"{page}: {written} Fragen geschrieben, {marked} ausgezeichnet"


@pytest.mark.parametrize("page", PAGES)
def test_the_questions_point_at_the_section_that_holds_them(page: str) -> None:
    """Die Sprungmarke im `@id` heißt in jeder Sprache anders.

    Sie wird abgelesen, nicht angenommen — und beim ersten Versuch las das
    Werkzeug die erste Section des Dokuments statt der mit den Fragen. Beide
    bestehen die Sprungmarkenprüfung darüber, denn beide Marken gibt es. Was
    zählt, ist, dass die Marke den Fragenblock umschließt.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    match = re.search(r'"@type": "FAQPage",\s*\n\s*"@id": "[^"#]*#([^"]+)"', text)
    assert match is not None, f"{page} zeichnet keine Fragen aus"
    mark = match.group(1)
    section = re.search(rf'<section id="{re.escape(mark)}"(.*?)</section>', text, re.DOTALL)
    assert section is not None, f'{page}: kein Abschnitt mit id="{mark}"'
    assert '<div class="faq">' in section.group(1), (
        f'{page}: die Auszeichnung zeigt auf "{mark}", dort stehen aber keine Fragen'
    )


@pytest.mark.parametrize("page", ALL_PAGES)
def test_the_preview_picture_exists(page: str) -> None:
    """Was beim Teilen erscheint, wird sonst von niemandem geprüft.

    Der Verweistest darüber sieht `og:image` nicht: das Bild steht dort in
    einem `content`-Attribut und nicht in `src`. Fehlt die Datei, bleibt die
    Seite fehlerfrei und die geteilte Karte leer — bemerkt wird das erst, wenn
    jemand den Link in ein Forum stellt.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    match = re.search(r'<meta property="og:image" content="([^"]+)"', text)
    assert match is not None, f"{page} zeigt beim Teilen kein Bild"
    picture = WEBSITE / match.group(1).removeprefix("https://solidon3d.de/")
    assert picture.exists(), f"{page} verweist auf {match.group(1)}, die Datei fehlt"


#: Die Startseiten aller sechs Sprachen. Sie tragen den Download-Kasten, und
#: nur sie.
START_PAGES = ("index.html", *(f"{code}/index.html" for code in ("en", "es", "fr", "it", "pt")))


@pytest.mark.parametrize("page", START_PAGES)
def test_the_download_box_can_switch_from_waiting_to_loading(page: str) -> None:
    """Am Erscheinungstag muss der Kasten umschalten können, in jeder Sprache.

    Vorher blendete sich um achtzehn Uhr allein der Zähler aus. Die
    Überschrift nannte weiter einen Termin, der vorbei war, und der Knopf bot
    an, Bescheid zu geben, wenn längst etwas zu laden war — wer fünf Minuten
    nach dem Termin kam, fand keinen Download.

    Geprüft wird die Verdrahtung, nicht die Uhrzeit: Steht der Termin am
    Dokument, ist die Stelle für die Datei da, und tragen beide Knöpfe einen
    Text für danach? Eine Sprachfassung, in der eines davon fehlt, sieht
    fehlerfrei aus und bleibt am Abend stehen.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")

    assert re.search(r'<body[^>]*\sdata-release="[^"]+"', text), (
        f"{page}: am <body> steht kein Erscheinungstermin (data-release)"
    )
    assert re.search(r'<body[^>]*\sdata-download="', text), (
        f"{page}: am <body> fehlt die Stelle für die Datei (data-download)"
    )

    knoepfe = text.count("data-release-href")
    assert knoepfe == 2, (
        f"{page}: {knoepfe} umschaltende Knöpfe statt zwei — erwartet werden "
        "der im Download-Kasten und der beim Preis. Der Kontaktweg im "
        "Schlussabschnitt gehört ausdrücklich nicht dazu."
    )

    for beschriftung in re.findall(r'data-release-text="([^"]*)"', text):
        assert beschriftung.strip(), f"{page}: ein Text für danach ist leer"

    # Symbol und Beschriftung wechseln zusammen: ein Knopf, der „laden" heißt
    # und einen Briefumschlag trägt, ist auf halbem Weg stehengeblieben.
    assert text.count("data-release-hide") == text.count("data-release-show") == 2, (
        f"{page}: die Symbole wechseln nicht paarweise mit den Knöpfen"
    )
