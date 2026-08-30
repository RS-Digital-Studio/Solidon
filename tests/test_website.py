"""Die Startseite behauptet Zahlen — diese Datei prüft, dass sie stimmen.

Auf `website/index.html` steht eine Leiste mit sechs Kennzahlen: wie viele
Operationen im Register stehen, wie viele Bausteine es gibt, wie viele
Normteilmaße hinterlegt sind, wie viele Druckerprofile mitkommen und wie
viele Beispielprojekte beiliegen. Sie sind aus den Quellen abgelesen und
werden falsch, sobald eine Operation dazukommt — eine falsche Zahl auf einer
Verkaufsseite ist kein Schönheitsfehler.

Geprüft wird außerdem, dass beide Sprachversionen dieselben Zahlen führen und
dass jede eingebundene Datei existiert.

Dieselbe Zahl steht ein zweites Mal im Fließtext — auf der Funktionsseite und
in den häufigen Fragen. Die Leiste allein zu prüfen reichte nicht: sie stand
längst auf 85, während der Satz daneben 83 behauptete und die englische
Version 84. Was im Text steht, wird darum über **alle** Seiten geprüft, auch
über die, die diese Datei sonst nicht kennt.
"""

from __future__ import annotations

import itertools
import json
import re
import struct
import tomllib
from datetime import datetime
from html.parser import HTMLParser
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
#: Was ``tools/make_legal.py`` erzeugt — die prüft ``test_legal.py``.
GENERATED = frozenset(
    {"agb.html", "datenschutz.html", "eula.html", "impressum.html", "widerruf.html"}
)


def _sales_pages() -> tuple[str, ...]:
    """Jede von Hand gepflegte Verkaufsseite, in allen Sprachen.

    **Erhoben und nicht aufgezählt.** Die Liste stand hier als Literal — sechs
    Namen, alle deutsch oder englisch — und versprach im Kommentar daneben
    „jede". Seit die Seiten in sechs Sprachen stehen, waren zwölf davon in
    keinem Lauf: Vier gaben für dasselbe Bild eine Höhe an, die es seit einer
    Änderung nicht mehr hatte, und die Suite blieb grün. Gefunden hat es
    Robert am fertigen Bild.

    Draußen bleiben die erzeugten Rechtstexte, das Handbuch und die
    Bestätigungsdatei der Suchmaschine — sie sind keine gepflegten Seiten.
    """
    found = []
    for path in sorted(WEBSITE.rglob("*.html")):
        relative = path.relative_to(WEBSITE).as_posix()
        if path.name in ("handbuch.html", "manual.html") or path.name in GENERATED:
            continue
        if path.name.startswith("google"):
            continue
        found.append(relative)
    return tuple(found)


ALL_PAGES = _sales_pages()
#: Eine Menge aus dem Dateisystem kann leer werden, ohne dass ein Test rot
#: wird — dann liefe jede Prüfung darüber ins Nichts und bestünde.
assert len(ALL_PAGES) >= 18, f"nur {len(ALL_PAGES)} Verkaufsseiten gefunden"
DATA = Path(__file__).resolve().parent.parent / "app" / "core" / "knowledge" / "data"
EXAMPLES = Path(__file__).resolve().parent.parent / "app" / "examples"

#: Ein Eintrag der Leiste sieht aus wie ``<div><b>61</b><span>…</span></div>``.
STAT = re.compile(r"<div><b>(\d+)</b><span>([^<]+)</span></div>")

#: Verweise auf Dateien — Netzadressen, Postadressen und Sprungmarken zählen
#: nicht dazu.
LINK = re.compile(r'(?:src|href)="([^"]+)"')

#: Die einzige absichtliche Außenadresse: Sie wird ausschließlich nach einem
#: Klick auf „Mit PayPal spenden“ geöffnet. Beim Laden der Website bleibt sie
#: komplett außen vor; ein eingebundenes PayPal-Skript wäre keine gleichwertige
#: Alternative, weil es jeden Besuch an den Zahlungsdienst meldete.
PAYPAL_DONATE_URL = "https://www.paypal.com/donate/?hosted_button_id=D7T4A9VYU9MX4"

#: PayPal verarbeitet die Zahlungsdaten erst auf seiner eigenen Seite. Wer
#: den Weg anbietet, muss dort trotzdem direkt zu den Einzelheiten führen —
#: nicht zu einer Suchseite und nicht nur zum allgemeinen Hilfezentrum.
PAYPAL_PRIVACY_URL = "https://www.paypal.com/de/legalhub/paypal/privacy-full?locale.x=de_DE"

#: Die Registergröße im Fließtext: eine Zahl, dahinter das Wort für Operation.
#: Der Stamm trägt durch alle sechs Sprachen — Operationen, operations,
#: operaciones, opérations, operazioni, operações. Eine siebte Sprache ist
#: damit mitgeprüft, ohne dass hier jemand etwas nachträgt.
#:
#: **Das ``é`` steht hier, weil es einmal gefehlt hat.** Das Muster hieß
#: ``[Oo]per\w*``, und der Kommentar darüber zählte „opérations" ausdrücklich
#: mit — gemessen hat das niemand. Französisch schreibt aber ``opér``, und
#: damit lief die eine Sprache ungeprüft, in der dann auch der Fehler stand:
#: drei Stellen nannten 87 Operationen, während der Statistikblock derselben
#: Seite 91 sagte. Ein Wächter, dessen Reichweite nur im Kommentar steht, ist
#: keiner.
OPERATION_COUNT = re.compile(r"(\d+)(?:&nbsp;|\s)+[Oo]p[eé]r\w*")

#: Die Illustrationen sind Inline-SVG und führen erfundene Beispielzahlen
#: („Vorschlag — 3 Operationen“). Das ist keine Aussage über das Register.
INLINE_SVG = re.compile(r"<svg\b.*?</svg>", re.DOTALL)


def _stats(page: str) -> list[int]:
    return [int(m.group(1)) for m in STAT.finditer((WEBSITE / page).read_text(encoding="utf-8"))]


def test_activation_privacy_names_the_daily_counter_without_claiming_ip_storage() -> None:
    """Die kurze Aktivierungsseite und die Einzelheiten dürfen sich nicht widersprechen."""
    page = (WEBSITE / "offline-aktivierung.html").read_text(encoding="utf-8")
    privacy = (WEBSITE / "datenschutz.html").read_text(encoding="utf-8")

    assert "Tageszähler" in page
    assert "IP-Adressen" in page
    assert "gültig signierten Aktivierungsversuche" in privacy
    assert "ohne weiteren Zugriff" in privacy


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


@pytest.mark.parametrize(
    "page",
    sorted(str(p.relative_to(WEBSITE)).replace("\\", "/") for p in WEBSITE.glob("*/index.html")),
)
def test_every_language_states_the_same_numbers(page: str) -> None:
    """Der Statistikblock jeder Sprache gegen den der Quellsprache.

    **Vorher standen hier zwei Sprachen von sechs.** Der Test verglich
    ``index.html`` gegen ``en/index.html``, und für die vier übrigen prüfte
    allein die Operationszahl-Regel darunter — die ausgerechnet bei Französisch
    ein Loch hatte. Eine Zahl, die auf der italienischen Seite altert, ist
    genauso falsch wie auf der deutschen; sie fällt nur später auf, weil
    seltener jemand hinsieht.

    Über ``glob`` und nicht über eine Liste: Eine siebte Sprache ist damit vom
    ersten Einchecken an mitgeprüft, ohne dass hier jemand etwas nachträgt.
    """
    assert _stats(page) == _stats("index.html"), (
        f"{page} nennt {_stats(page)}, die Quellsprache {_stats('index.html')}"
    )


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
    Sprachversionen kommen einzeln dazu, und eine Zahl, die auf der
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
        # Und seit der Download über den Zähler läuft, trägt er eine Abfrage:
        # `/api/count.php?f=Solidon3D-Setup-0.1.1.exe`. Auch hier zählt die
        # Datei davor — was hinter dem Fragezeichen steht, ist ein Argument
        # und kein Pfad, und ohne diese Zeile wäre jeder Verweis mit einer
        # Abfrage ein Fehlbefund.
        target = target.split("?", 1)[0]
        if not target:
            continue
        # **Die Pakete zählen nicht mit.** ``website/dl/`` steht in
        # ``.gitignore``: Eine Setup-Datei wiegt hundertsiebzig Megabyte, und
        # ein Repository ist kein Dateiablage. Auf dem Rechner, der sie gebaut
        # und hochgeladen hat, liegen sie; in einem frischen Klon nie — und
        # dort wurde dieser Test rot, sobald der Download-Kasten zum ersten Mal
        # eine echte Datei nannte. Dass die Datei auf dem Server wirklich
        # liegt, prüft kein Test, sondern der Abruf nach dem Hochladen.
        if target.startswith("/dl/"):
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
        # Der Inhaltsstempel (`tools/stamp_assets.py`) gehört zur Adresse, nicht
        # zum Dateinamen: `bilder/x.png?v=a8bf1166` liegt auf der Platte als
        # `bilder/x.png`. Ohne das Abschneiden fällt jede gestempelte Seite.
        picture = source.parent / path.split("?", 1)[0]
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
    der Auszeichnung für Suchmaschinen ebenfalls. Beide Sprachversionen
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


def test_every_page_lets_the_keyboard_skip_the_header() -> None:
    """Der Sprung an den Inhalt, auf jeder Seite und vor allem anderen.

    Wer mit der Tastatur bedient, kam auf jeder Seite zuerst durch die
    Kopfzeile: Logo, drei Verweise, das Sprachfeld mit sechs Sprachen darin,
    den Demo-Knopf — elf Elemente, auf jeder der neunundzwanzig Seiten neu.
    ``<main>`` allein hilft dem Vorleser und nicht der Tabulatortaste (WCAG
    2.4.1).

    Geprüft wird über **alle** Seiten unter ``website/``, nicht über
    ``ALL_PAGES``: Die Rechtstexte und die fünf Sprachversionen stehen dort
    nicht, und ausgerechnet sie werden von Hand angelegt. Die Beschriftung
    kommt aus derselben Tabelle, aus der die erzeugten Handbuchseiten sie
    nehmen — zwei Listen wären eine zu viel.

    Wer keine Kopfzeile hat, hat nichts zu überspringen: Der Nachweis der
    Search Console ist eine Zeile Text unter einem ``.html``-Namen, weil Google
    ihn so verlangt. Das Kriterium ist deshalb ``<header``, nicht der Dateiname
    — an einer Liste von Ausnahmen fehlte irgendwann eine.
    """
    from tools.make_manual import SKIP

    wrong = []
    for page in sorted([*WEBSITE.glob("*.html"), *WEBSITE.glob("*/*.html")]):
        text = page.read_text(encoding="utf-8")
        if "<header" not in text:
            continue
        name = page.relative_to(WEBSITE).as_posix()
        language = page.parent.name if page.parent != WEBSITE else "de"
        found = re.search(r'<a class="skip" href="#([^"]+)">([^<]+)</a>', text)
        if found is None:
            wrong.append(f"{name}: kein Sprung an den Inhalt")
            continue
        target, label = found.groups()
        if f'id="{target}"' not in text:
            wrong.append(f"{name}: der Sprung zeigt auf #{target}, das es nicht gibt")
        if label != SKIP[language]:
            wrong.append(f"{name}: {label} statt {SKIP[language]}")
        if found.start() > text.index("<header"):
            wrong.append(f"{name}: der Sprung steht hinter der Kopfzeile")
    assert not wrong, "\n".join(wrong)


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
        # Der ``?v=…``-Teil ist der Inhaltsstempel aus ``tools/stamp_assets.py``
        # und gehört zur eigenen Adresse. Ohne ihn im Muster wäre jeder
        # gestempelte Verweis „von außen" — 36 Seiten fielen so auf einmal.
        allowed = 'type="application/ld+json"' in tag or re.search(
            r'src="/(?!/)[^"]*\.js(\?v=[0-9a-f]{8})?"', tag
        )
        assert allowed, f"{page} bindet ein Skript ein, das nicht von hier kommt: {tag}"
    assert 'src="http' not in text
    external_hrefs = [
        reference
        for reference in LINK.findall(text)
        if reference.startswith("http") and not reference.startswith("https://solidon3d.de")
    ]
    assert all(reference == PAYPAL_DONATE_URL for reference in external_hrefs), (
        f"{page} verweist auf eine nicht freigegebene Außenadresse: {external_hrefs}"
    )
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
#: Der Zähler: seine Markierung ohne Wert, dahinter der übersetzte Rahmensatz.
#: Der Zeitpunkt steht seit dem 20.08.2026 nur noch am ``<body>`` — siehe
#: ``test_the_moment_of_release_stands_exactly_once``.
COUNTDOWN = re.compile(r'data-countdown\s+data-template="([^"]+)"')

#: Der Zeitpunkt, auf den alles zeigt: Zähler und Umschaltung.
RELEASE = re.compile(r'<body[^>]*\sdata-release="([^"]+)"')


def _start_pages() -> list[Path]:
    """Alle Startseiten, auch die vier, die `PAGES` nicht kennt.

    `PAGES` führt Deutsch und Englisch, weil nur dort die Kennzahlenleiste
    geprüft wird. Der Zähler steht auf allen sechs, und genau darum wird hier
    gesucht statt aufgezählt: eine siebte Sprache ist mitgeprüft, sobald ihr
    Ordner ein `index.html` enthält.
    """
    return sorted(WEBSITE.glob("index.html")) + sorted(WEBSITE.glob("*/index.html"))


def test_every_start_page_counts_down_to_the_same_moment() -> None:
    """Sechs Sprachversionen, ein Termin.

    Der Zielzeitpunkt steht im Markup, nicht im Skript — sonst stünde er an
    einer Stelle, die keine Sprachversion liest. Der Preis dafür ist, dass er
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
        body = page.read_text(encoding="utf-8")
        found = COUNTDOWN.findall(body)
        assert len(found) == 1, f"{name} trägt {len(found)} Zähler, erwartet ist genau einer"
        template = found[0]
        at_body = RELEASE.search(body)
        assert at_body, f"{name} nennt am <body> keinen Zeitpunkt"
        moment = at_body.group(1)
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
        # Mit oder ohne Inhaltsstempel (`tools/stamp_assets.py`) — gefragt ist,
        # ob die Datei eingebunden ist, nicht unter welcher Fassung.
        assert re.search(r'src="/site\.js(\?v=[0-9a-f]{8})?"', text), (
            f"{name} trägt einen Zähler, bindet aber site.js nicht ein"
        )


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


def test_every_delivered_page_counts_itself() -> None:
    """Eine Seite ohne ``site.js`` steht in keiner Statistik — und niemand
    merkt es, weil die Statistik dann eben eine Seite weniger nennt.

    **Gefunden am 24.08.2026, von Robert an der Statistikseite:** „die meisten
    seiten werden nicht angezeigt". Gezählt: **12 von 30** Seiten banden das
    Skript ein. Fehlend waren genau die **erzeugten** — das Handbuch in sechs
    Sprachen, die fünf Rechtstexte — und die sechs KI-Seiten. Nichts war
    kaputt: `count.php` zählte tadellos, was bei ihm ankam, und bei ihm kam
    nichts an.

    **Der Fehlerfall ist nicht Vergesslichkeit, sondern eine neue Seitenart.**
    Wer eine Seite von Hand anlegt, kopiert eine bestehende und bekommt die
    Zeile mit. Wer ein *Werkzeug* schreibt, das Seiten erzeugt, schreibt den
    Rahmen neu — und der Rahmen kennt nur, woran der Autor gedacht hat.
    Deshalb prüft dieser Test das Ergebnis und nicht die Werkzeuge.

    Ausgenommen ist allein die Verifikationsdatei der Suchmaschine: Sie ist
    kein Angebot an einen Leser, sondern ein Beleg für einen Dienst, und was
    dort geschieht, gehört in keine Besucherstatistik. ``_delivered_pages``
    lässt sie schon aus.
    """
    ohne = [
        page.relative_to(WEBSITE).as_posix()
        for page in _delivered_pages()
        if "site.js" not in page.read_text(encoding="utf-8")
    ]
    assert not ohne, f"zählen sich nicht: {ohne}"


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
    # Die kompakten technischen Hinweise im Download-Kasten sind kein FAQ.
    written = len(re.findall(r"<summary>", text)) - text.count('<details class="download-notes">')
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
def test_each_start_page_makes_the_no_cad_promise_visible(page: str) -> None:
    """Die Eintrittshürde steht am Aufmacher, nicht erst in den Fragen unten."""
    text = (WEBSITE / page).read_text(encoding="utf-8")
    kicker = re.search(r'<p class="hero-kicker">([^<]+)</p>', text)
    assert kicker and kicker.group(1).strip(), f"{page}: der Nutzen ohne CAD fehlt am Aufmacher"


@pytest.mark.parametrize("page", START_PAGES)
def test_each_start_page_matches_the_sale_activation_policy(
    page: str, shipped_demo_until: object, shipped_trial_from: object
) -> None:
    """Sechs Übersetzungen dürfen die Lizenzgrenze nicht sechsfach erfinden.

    Die maschinenlesbaren Merkmale stehen am jeweiligen Kundensatz. So prüft
    der Test die Bedeutung und hängt nicht an sechs übersetzten Formulierungen.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    expected_deadline = shipped_demo_until.isoformat() if shipped_demo_until is not None else "none"
    assert text.count(f'data-demo-until="{expected_deadline}"') == 1, (
        f"{page}: Demo-Stichtag weicht von store.DEMO_UNTIL ab"
    )
    assert text.count('data-active-devices="1"') == 1, (
        f"{page}: genau ein gleichzeitig aktives Gerät fehlt im Angebot"
    )
    expected_trial = "true" if shipped_trial_from is not None else "false"
    assert text.count(f'data-sale-trial-active="{expected_trial}"') == 1, (
        f"{page}: Testphasen-Aussage weicht von store.TRIAL_FROM ab"
    )


@pytest.mark.parametrize("page", START_PAGES)
def test_each_start_page_offers_one_voluntary_paypal_donation(page: str) -> None:
    """Jede Sprache zeigt denselben freiwilligen, skriptfreien Spendenweg."""
    text = (WEBSITE / page).read_text(encoding="utf-8")
    links = re.findall(r'<a class="donate-button" href="([^"]+)"', text)
    assert links == [PAYPAL_DONATE_URL], (
        f"{page}: der Spendenknopf fehlt, ist mehrfach da oder trägt eine andere Adresse: {links}"
    )


@pytest.mark.parametrize("page", START_PAGES)
def test_each_start_page_keeps_picture_before_support(page: str) -> None:
    """Sichtbare und technische Leserichtung bleiben in jeder Breite gleich.

    **Die Zusage ist geblieben, ihre Bauart hat sich geändert** (WD2). Vorher
    stand der ganze Download-Kasten im Aufmacher und der Spendenkasten
    unmittelbar unter dem Produktbild — geprüft wurde damals
    ``download < side < picture < support`` innerhalb des Heros. Der Aufmacher
    trägt jetzt nur noch Kicker, Überschrift, Lead, **einen** Knopf und die
    Zusagen; Download und Spende haben eigene Abschnitte.

    Was bleibt, ist die eigentliche Aussage: **Die Handlung kommt vor dem
    Bild, und um Geld wird zuletzt gebeten.** Ein Spendenkasten, den man
    sieht, bevor man das Produkt begehrt hat, war der Befund (WB1); dass er
    jetzt hinter dem Preis steht, macht die Zusage stärker, nicht schwächer.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")

    act = text.index('<p class="hero-act">')
    # **Die Bauart des Produktbilds hat zum zweiten Mal gewechselt** (WD1):
    # Aus dem stehenden Bildschirmfoto (``shot hero-shot``) wurde eine
    # Drehbühne, und die ist kein ``<img>``, sondern ein Sprite im Stylesheet.
    # Geprüft wird deshalb, was von beiden dort **steht** — die Zusage ist der
    # Ort im Lesefluss, nicht die Klasse, mit der er gebaut ist.
    stages = [
        text.index(mark)
        for mark in ('<div class="turn-wrap">', '<div class="shot hero-shot">')
        if mark in text
    ]
    assert stages, f"{page}: im Aufmacher steht kein Produktbild"
    picture = min(stages)
    download = text.index('<section id="download">')
    support = text.index('<div class="donate">')

    assert act < picture < download < support, (
        f"{page}: Handlung, Produktbild, Download und Unterstützung stehen nicht "
        "in ihrer Leserichtung"
    )


@pytest.mark.parametrize("page", START_PAGES)
def test_no_start_page_asks_for_money_in_its_hero(page: str) -> None:
    """Im Aufmacher wird nicht um Geld gebeten (WB1).

    Der Spendenkasten stand dort unter dem Produktbild, mit Rechtstext, auf
    Augenhöhe mit dem Download — er bat um eine Gabe, bevor irgendjemand
    wissen konnte, wofür. Geprüft wird deshalb die **Zone** und nicht der
    Kasten: Alles bis zum Ende des Hero-Gitters bleibt frei davon, gleich wie
    der Kasten später einmal heißt.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    hero = text[text.index('<div class="hero">') : text.index('<section id="download">')]

    assert "donate" not in hero, (
        f"{page}: der Aufmacher enthält wieder einen Spendenblock — "
        "erst begehren lassen, dann fragen"
    )
    assert PAYPAL_DONATE_URL not in hero, f"{page}: PayPal-Adresse im Aufmacher"


def test_hero_keeps_its_picture_in_one_column() -> None:
    """Eine eigene Produktspalte verhindert verteilte Rasterhöhe und Fokus-Sprünge.

    Sie trägt seit WD2 **nur** noch das Bild — die Unterstützung ist heraus.
    Der Platz ist dabei so gebaut, dass ein ``<video>`` das ``<img>`` ersetzen
    kann, ohne dass sich das Layout bewegt; das ist die Vorarbeit für die
    Produkt-Loops (WD1), und deshalb steht die Regel dafür schon hier.
    """
    styles = (WEBSITE / "style.css").read_text(encoding="utf-8")

    side = re.search(r"\.hero-side\s*\{([^}]*)\}", styles, re.DOTALL)
    assert side is not None
    assert "display: grid" in side.group(1)
    assert "gap: 1rem" in side.group(1)
    assert '"copy picture"' not in styles
    assert "grid-area: picture" not in styles
    assert "grid-area: support" not in styles
    assert ".hero-side .stage > video" in styles, (
        "der Platz für einen Produkt-Loop fehlt — ein video müsste das img "
        "ersetzen können, ohne das Layout zu bewegen"
    )


@pytest.mark.parametrize("page", START_PAGES)
def test_each_paypal_donation_says_what_it_does_not_buy(page: str) -> None:
    """Freiwillig steht nicht nur im Konzept, sondern unmittelbar am Knopf."""
    text = (WEBSITE / page).read_text(encoding="utf-8")
    block = re.search(
        r'<div class="donate(?: [^"]*)?">\s*<div>(.*?)</div>\s*'
        r'<a class="donate-button"[^>]*>.*?</a>\s*</div>',
        text,
        re.DOTALL,
    )

    assert block is not None, f"{page}: der Spendenblock fehlt"
    assert block.group(1).count('class="donate-terms"') == 1, (
        f"{page}: der rechtliche Hinweis am Spendenknopf fehlt oder steht mehrfach da"
    )
    assert 'href="/datenschutz.html"' in block.group(1), (
        f"{page}: der Spendenweg erklärt seine Datenverarbeitung nicht"
    )


def test_the_privacy_page_names_paypal_before_any_payment() -> None:
    """Der externe Verweis spart das Einbetten, nicht die Information darüber."""
    text = (WEBSITE / "datenschutz.html").read_text(encoding="utf-8")

    assert "Freiwillige Spende über PayPal" in text
    assert PAYPAL_PRIVACY_URL in text
    assert "Beim Laden unserer Website wird keine Verbindung" in text
    assert "keine Bestellung" in text and "nicht auf einen späteren Kauf angerechnet" in text


@pytest.mark.parametrize("page", START_PAGES)
def test_download_technical_notes_stay_collapsible(page: str) -> None:
    """Der erste Eindruck bleibt beim Download, Details sind trotzdem erreichbar."""
    text = (WEBSITE / page).read_text(encoding="utf-8")
    notes = re.search(r'<details class="download-notes">(.*?)</details>', text, re.DOTALL)
    assert notes is not None, f"{page}: die technischen Download-Hinweise sind nicht einklappbar"
    assert "<summary>" in notes.group(1), f"{page}: die Hinweise haben keine sichtbare Beschriftung"
    assert "data-release-show" in notes.group(1), (
        f"{page}: die Hinweise für Installation und Updates stehen wieder ungebremst im Einstieg"
    )


@pytest.mark.parametrize("page", START_PAGES)
def test_the_download_box_can_switch_from_waiting_to_loading(page: str) -> None:
    """Am Erscheinungstag muss der Kasten umschalten können, in jeder Sprache.

    Vorher blendete sich um achtzehn Uhr allein der Zähler aus. Die
    Überschrift nannte weiter einen Termin, der vorbei war, und der Knopf bot
    an, Bescheid zu geben, wenn längst etwas zu laden war — wer fünf Minuten
    nach dem Termin kam, fand keinen Download.

    Geprüft wird die Verdrahtung, nicht die Uhrzeit: Steht der Termin am
    Dokument, gibt es einen Kasten für die Dateien, verschwindet die Warteliste
    und erscheint an ihrer Stelle etwas? Eine Sprachversion, in der eines davon
    fehlt, sieht fehlerfrei aus und bleibt am Abend stehen.

    Ob wirklich Dateien eingetragen sind, prüft dieser Test **nicht** — sie
    kommen erst am Tag der Veröffentlichung dazu (`tools/make_download.py`).
    Ein leerer Kasten ist der richtige Zustand davor.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")

    assert re.search(r'<body[^>]*\sdata-release="[^"]+"', text), (
        f"{page}: am <body> steht kein Erscheinungstermin (data-release)"
    )
    assert '<div class="dateien" data-files' in text, (
        f"{page}: der Kasten für die Dateien fehlt — make_download.py findet "
        "keine Stelle zum Eintragen"
    )

    assert text.count("data-release-hide") >= 1, (
        f"{page}: nichts verschwindet nach dem Erscheinen — die Warteliste bliebe stehen"
    )
    assert text.count("data-release-show") >= 1, f"{page}: nichts erscheint nach dem Erscheinen"

    for beschriftung in re.findall(r'data-(?:release|past)-text="([^"]*)"', text):
        assert beschriftung.strip(), f"{page}: ein Text für danach ist leer"

    # Der Kontaktweg im Schlussabschnitt trägt die Anschrift als Beschriftung
    # und bleibt ein Kontaktweg — ein erster Entwurf hatte ihn mitverwandelt.
    schluss = text[text.index('<div class="closing">') :]
    assert "data-release-href" not in schluss.split("</div>")[0], (
        f"{page}: der Kontaktweg im Schlussabschnitt würde zum Ladeknopf"
    )


def test_the_next_linux_release_offers_appimage_and_flatpak_but_not_the_archive() -> None:
    """Linux bekommt einen einfachen und einen verwalteten Weg, kein Terminalarchiv.

    Das AppImage startet nach dem Setzen des Ausführrechts direkt, das Flatpak
    bleibt für die verwaltete Installation. Das tar.gz baut die CI weiterhin,
    ist aber kein Angebot an jemanden, der gerade einfach loslegen will.
    """
    from tools.make_download import DELIVERED, delivery_slot

    assert delivery_slot("Solidon3D-0.2.2-x86_64.AppImage") == "Linux AppImage"
    assert delivery_slot("Solidon3D-0.2.2-x86_64.flatpak") == "Linux Flatpak"
    assert delivery_slot("Solidon3D-0.2.2-linux-x86_64.tar.gz") == ""
    assert len(DELIVERED) == 5, "Windows, zweimal Linux und beide Mac-Architekturen"


def test_no_two_values_share_a_spot_and_a_moment() -> None:
    """Zwei Zahlen an derselben Stelle dürfen sich nicht überblenden.

    Fünf Zeichnungen zeigen einen Wert, der sich ändert — Bohrungsmaß,
    Wandstärke, Durchmesser, Höhe, Urteil. Beide Fassungen stehen auf
    denselben SVG-Koordinaten, und beide wechselten ihre Deckkraft im
    **selben** Zeitfenster: „ø 4,2 mm" und „ø 4,5 mm" lagen sechs Prozent der
    Laufzeit übereinander, zweimal je Durchlauf. Ausgerechnet die Zahlen, um
    die es in der Zeichnung geht, waren in diesem Moment Zeichensalat.

    Der Test sucht die Paare **selbst**, statt eine Liste zu führen: Er liest
    alle animierten `<text>`-Elemente aus den Verkaufsseiten, gruppiert sie
    nach ihren Koordinaten und prüft für jede Stelle, an der mehr als eine
    Beschriftung sitzt, ob deren Keyframes je gleichzeitig sichtbar werden.
    Damit fällt auch ein Paar auf, das später jemand dazulegt.

    Gemessen wird in halben Prozentschritten — ein Übergang von sechs Prozent
    Breite rutscht durch ein gröberes Raster.
    """
    style = (WEBSITE / "style.css").read_text(encoding="utf-8")

    # Die Deckkraftstufen je Keyframe-Satz
    steps: dict[str, list[tuple[float, float]]] = {}
    for block in re.finditer(r"@keyframes\s+([\w-]+)\s*\{(.*?)\n\}", style, re.DOTALL):
        name, body = block.group(1), block.group(2)
        found: list[tuple[float, float]] = []
        for stage in re.finditer(r"([\d%,\s]+)\{([^}]*)\}", body):
            opacity = re.search(r"opacity:\s*([\d.]+)", stage.group(2))
            if opacity:
                found += [
                    (float(p), float(opacity.group(1)))
                    for p in re.findall(r"([\d.]+)%", stage.group(1))
                ]
        if found:
            steps[name] = sorted(found)

    def visible(name: str, moment: float) -> float:
        """Deckkraft zu einem Zeitpunkt, linear zwischen den Stufen."""
        stages = steps[name]
        before = [s for s in stages if s[0] <= moment]
        after = [s for s in stages if s[0] >= moment]
        if not before:
            return after[0][1]
        if not after:
            return before[-1][1]
        (start, low), (end, high) = before[-1], after[0]
        return low if end == start else low + (high - low) * (moment - start) / (end - start)

    # Animierte Beschriftungen je Seite und Ort einsammeln.
    #
    # **Mit einem Parser und nicht mit einem Muster.** Der erste Anlauf suchte
    # `<g class="anim NAME">` und fand von den fünf bekannten Paaren **keines**:
    # Sie hängen als `class="value anim fig-hole-42"` direkt am `<text>`. Der
    # Test lief grün, auch gegen den Zustand, den er melden sollte — die
    # Gegenprobe war der einzige Grund, warum das auffiel.
    #
    # Beide Formen zählen, und ein `<text>` in einer animierten Gruppe erbt
    # deren Namen: Die Gruppe blendet ihren ganzen Inhalt aus.
    class Labels(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.stack: list[list[str]] = []
            self.found: list[tuple[str, str, tuple[str, ...]]] = []

        @staticmethod
        def _animations(attrs: list[tuple[str, str | None]]) -> list[str]:
            classes = dict(attrs).get("class") or ""
            return [part for part in classes.split() if part in steps]

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "g":
                self.stack.append(self._animations(attrs))
                return
            if tag != "text":
                return
            values = dict(attrs)
            if not (values.get("x") and values.get("y")):
                return
            inherited = [name for level in self.stack for name in level]
            names = tuple(sorted(set(inherited + self._animations(attrs))))
            if names:
                self.found.append((values["x"], values["y"], names))

        def handle_endtag(self, tag: str) -> None:
            if tag == "g" and self.stack:
                self.stack.pop()

    spots: dict[tuple[str, str, str], set[str]] = {}
    for page in _sales_pages():
        reader = Labels()
        reader.feed((WEBSITE / page).read_text(encoding="utf-8"))
        for x, y, names in reader.found:
            spots.setdefault((page, x, y), set()).update(names)

    moments = [step / 2 for step in range(201)]
    clashes = []
    for (page, x, y), names in sorted(spots.items()):
        for first, second in itertools.combinations(sorted(names), 2):
            worst = max(min(visible(first, m), visible(second, m)) for m in moments)
            if worst > 0.15:
                clashes.append(f"{page} bei x={x} y={y}: {first} und {second} zu {worst:.2f}")

    assert not clashes, (
        "Beschriftungen teilen sich eine Stelle und einen Moment — beide sind "
        "dann unlesbar:\n" + "\n".join(clashes[:10])
    )


def test_the_mobile_hero_is_visible_without_waiting_for_an_animation() -> None:
    """Der erste Handybildschirm darf nicht wie eine leere Seite wirken.

    Die gestaffelte Ladeanimation hielt Überschrift, Einleitung und Download
    zunächst unsichtbar. Auf 390 Pixeln blieb dadurch unter der Kopfzeile fast
    nur das Hintergrundraster stehen — genau dort, wo der Nutzen sofort lesbar
    sein muss. Der letzte schmale Breakpoint schaltet nur diese Einblendung ab.
    """
    css = (WEBSITE / "style.css").read_text(encoding="utf-8")
    mobile = css.rsplit("@media (max-width: 30rem)", maxsplit=1)[-1]

    assert ".hero-text > * { animation: none; }" in mobile


def test_every_reference_carries_the_stamp_of_the_file_it_points_at() -> None:
    """Jeder Verweis auf eine eigene Datei trägt deren aktuellen Inhaltsstempel.

    Am 27.08.2026 gemeldet: „Ohne STRG+F5 sehe ich noch die alten Bilder auf
    der Webseite." Der Server war dabei richtig eingestellt — er sendet
    ``Cache-Control: no-cache`` für Seiten **und** Bilder, gemessen an der
    laufenden Website. Ein Header wirkt aber nur auf die Antwort, die er
    begleitet: Zwischen dem 20. und dem 25.08. lieferte derselbe Server Bilder
    mit ``max-age=604800``, und wer in jener Woche einmal da war, hält sie bis
    zu sieben Tage für frisch und fragt gar nicht erst nach.

    Dreimal wurde das an den Headern behoben (18.08., 20.08., 25.08.) und kam
    dreimal wieder. Ein **anderer Verweis** ist die eine Auskunft, die jeden
    Cache erreicht — was unter ``bilder/x.png?v=a8bf1166`` angefragt wird, kann
    kein Eintrag unter ``bilder/x.png`` beantworten.

    Dieser Test ist die Stelle, an der das eingelöst wird. Er wird rot, sobald
    eine Datei sich ändert oder eine Seite neu erzeugt wird, ohne dass
    ``python tools/stamp_assets.py`` danach gelaufen ist — und das ist keine
    Schikane, sondern genau die Erinnerung, die viermal gefehlt hat.
    """
    import tools.stamp_assets as stamp

    stale: list[str] = []
    for page in sorted(WEBSITE.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        for _, reference, existing, _ in stamp.LINK.findall(text):
            target = stamp.target_of(page, reference)
            if not target.is_file():
                continue  # Ein Verweis ins Leere ist ein anderer Fund
            wanted = f"?v={stamp.stamp_of(target)}"
            if existing != wanted:
                name = page.relative_to(WEBSITE).as_posix()
                stale.append(f"{name} → {reference}{existing or ' (ohne Stempel)'}")

    assert not stale, (
        f"{len(stale)} Verweise tragen einen veralteten oder keinen Stempel — "
        "`python tools/stamp_assets.py` zieht sie nach:\n" + "\n".join(stale[:12])
    )


@pytest.mark.parametrize("page", START_PAGES)
def test_the_release_run_writes_the_size_span_itself(page: str) -> None:
    """Und der Erzeuger trägt sie nach, statt dass jemand sie tippt.

    Der Wächter darunter fängt eine veraltete Spanne — aber er fängt sie erst,
    wenn ein Release schon gebaut ist, und dann steht jemand vor einem roten
    Lauf und ändert zwei Zahlen von Hand. Genau so ist sie beim Sprung von
    0.1.5 auf 0.2.0 stehen geblieben.

    ``write_size_span`` ersetzt die **Zahlen**, nicht den Satz: Die sechs
    Sprachen formulieren ihn verschieden, und in jeder stehen genau drei
    Zahlen in der Zeile — die installierte Größe und die beiden Enden. Die 750
    bleibt stehen, weil sie sich mit keinem Release ändert.

    Geprüft mit erfundenen Paketgrößen, damit der Test unabhängig davon ist,
    was gerade unter ``dl/`` liegt — aber mit **echten** ``Package``-Objekten.

    Hier stand eine Attrappe mit ``self.path.stat().st_size``, weil die
    geprüfte Funktion die Größe so las. ``Package`` hat kein ``path``: Es
    trägt ``bytes_``, beim Einlesen zusammen mit der Prüfsumme erhoben. Der
    Test war grün, und der Release-Lauf von 0.2.1 brach am 27.08.2026 beim
    Schreiben der Seiten ab — nachdem er die Dateien schon kopiert hatte.

    Eine Attrappe, die nach dem geprüften Code geformt ist statt nach der
    echten Klasse, prüft, dass der Code zu sich selbst passt.
    """
    import tools.make_download as make_download

    text = (WEBSITE / page).read_text(encoding="utf-8")
    fresh = make_download.write_size_span(
        text,
        [
            make_download.Package(
                kind="windows", name=f"Probe-{size}.exe", bytes_=size * 1_000_000, hash_="0" * 64
            )
            for size in (205, 288, 340)
        ],
        page,
    )

    row = next(
        line
        for index, line in enumerate(fresh.splitlines())
        if "750" in line and "<td>" in line
        for line in [" ".join(fresh.splitlines()[index : index + 2])]
    )
    numbers = [n for n in re.findall(r"\b\d{2,4}\b", row) if n != "750"]
    assert numbers == ["205", "340"], f"{page}: die Spanne wurde nicht gesetzt — {numbers}"
    assert "750" in row, f"{page}: die installierte Größe darf nicht mitwandern"


@pytest.mark.parametrize("page", START_PAGES)
def test_the_technical_requirements_name_the_sizes_the_packages_have(page: str) -> None:
    """Die Größenspanne in den Systemvoraussetzungen gegen ``version.json``.

    Sie stand am 27.08.2026 auf „zwischen 180 und 315 MB", in allen sechs
    Sprachen — und die Pakete wogen 192, 274, 294 und 327. **Beide Enden
    falsch, und zwar gegen den Download-Kasten derselben Seite**, der 192 und
    327 anzeigt: Der Kasten wird von ``tools/make_download.py`` geschrieben,
    die Tabellenzeile ist Handarbeit, und sie ist beim Sprung von 0.1.5 auf
    0.2.0 stehen geblieben.

    Geprüft wird gegen ``website/version.json``, weil ``website/dl/`` nicht im
    Repository liegt (``.gitignore``) — die Datei daneben trägt dieselben
    Bytes und reist mit. Solange sie keine Pakete führt, gibt es nichts zu
    prüfen: vor einem Release ist der leere Zustand der richtige.

    Gelesen wird die Zeile mit der installierten Größe, und aus ihr **alle**
    Zahlen. Eine Regel auf „zwischen X und Y" träfe die sechs Sprachen nicht:
    Französisch schreibt „entre 192 et 327&nbsp;Mo", Portugiesisch stellt den
    Halbsatz um. Die Zahlen stehen in jeder Sprache gleich da.
    """
    packages = json.loads((WEBSITE / "version.json").read_text(encoding="utf-8")).get(
        "packages", {}
    )
    sizes = [int(entry["size"]) for entry in packages.values() if entry.get("size")]
    if not sizes:
        pytest.skip("version.json führt noch keine Pakete — vor dem Release ist das richtig")

    # Geteilt wie tools/make_download.py es tut: durch 1 000 000, nicht 1024².
    kleinstes, groesstes = min(sizes) // 1_000_000, max(sizes) // 1_000_000
    text = (WEBSITE / page).read_text(encoding="utf-8")

    zeile = next((z for z in text.splitlines() if "750" in z and "<td>" in z), None)
    assert zeile, f"{page}: keine Zeile mit der installierten Größe gefunden"
    # Die Zeile bricht im Quelltext um; die Spanne steht in der Fortsetzung.
    zeilen = text.splitlines()
    zeile = " ".join(zeilen[zeilen.index(zeile) : zeilen.index(zeile) + 2])

    zahlen = {int(z) for z in re.findall(r"\b(\d{2,4})\b", zeile)} - {750}
    assert len(zahlen) >= 2, (
        f"{page}: in der Größenzeile stehen {sorted(zahlen)} statt einer Spanne"
    )

    # Hineinfallen, nicht gleich sein — und das ist der Unterschied zwischen
    # zwei Mengen, die beide stimmen. ``version.json`` führt die Pakete der
    # **Update-Automatik**: Windows und die beiden Macs (``VERSION_KEYS`` in
    # make_download). Der Download-Kasten derselben Seite bietet mehr an, und
    # ``write_size_span`` rechnet über alles, was dort steht — am 27.08.2026
    # also bis 427 MB für die Linux-tar.gz, während das größte Paket in
    # version.json 328 wog.
    #
    # Auf Gleichheit geprüft war die Zeile damit rot, obwohl sie den Kunden
    # richtig informierte: Ein Linux-Nutzer lädt 427 MB, und eine Spanne, die
    # bei 328 endet, wäre für ihn schlicht falsch. Geprüft wird deshalb, was
    # die Zusage ist — kein angebotenes Paket fällt aus der genannten Spanne.
    assert min(zahlen) <= kleinstes, (
        f"{page}: das kleinste Paket wiegt {kleinstes} MB, die Zeile beginnt bei {min(zahlen)}"
    )
    assert groesstes <= max(zahlen), (
        f"{page}: das größte Paket wiegt {groesstes} MB, die Zeile endet bei {max(zahlen)}"
    )


@pytest.mark.parametrize("page", START_PAGES)
def test_the_moment_of_release_stands_exactly_once(page: str) -> None:
    """Der Termin steht einmal je Seite, und der Zähler liest ihn von dort.

    Bis zum 20.08.2026 stand er zweimal: am Zähler (``data-countdown`` mit
    Wert) und an der Umschaltung von Warten auf Laden (``data-release`` am
    ``<body>``). Ein Test hielt beide gleich — zwölf Stellen für einen
    Zeitpunkt, und wer eine verschob und die andere vergaß, bekam eine Seite,
    die den Download freigibt, während daneben noch etwas herunterzählt.

    Der Zähler behält seine Markierung ohne Wert: Sie sagt, *welcher* Absatz
    zählt, und das ist eine andere Auskunft als *wann*. Geprüft wird deshalb
    beides — dass der Termin am Körper steht, und dass die Markierung keinen
    zweiten mitbringt.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    am_body = re.search(r'<body[^>]*\sdata-release="([^"]+)"', text)

    assert am_body, f"{page}: am <body> steht kein Termin"
    assert 'data-countdown="' not in text, (
        f"{page}: der Zähler trägt wieder einen eigenen Termin — er soll den vom <body> lesen"
    )
    assert "data-countdown" in text, f"{page}: die Markierung des Zählers fehlt"


def test_all_six_languages_release_at_the_same_moment() -> None:
    """Eine Sprachversion, die eine Stunde früher umschaltet, ist ein Fehler.

    Sechs Dateien tragen denselben Termin. Beim Verschieben wird erfahrungsgemäß
    eine vergessen, und auffallen würde das erst an dem Abend, an dem es zählt.
    """
    termine = {
        page: re.search(
            r'<body[^>]*\sdata-release="([^"]+)"',
            (WEBSITE / page).read_text(encoding="utf-8"),
        ).group(1)  # type: ignore[union-attr]
        for page in START_PAGES
    }
    assert len(set(termine.values())) == 1, f"verschiedene Termine: {termine}"


def test_the_three_sweeps_over_the_pages_find_something_to_check() -> None:
    """Was die drei Durchgänge zählen, muss es geben — sonst prüfen sie nichts.

    ``test_every_file_the_page_refers_to_exists``,
    ``test_every_jump_onto_another_page_lands_somewhere`` und
    ``test_no_answer_denies_a_platform_the_build_ships`` sammeln in einer
    Schleife und sichern am Ende zu, dass die gesammelte Liste **leer** ist.
    Eine solche Zusicherung ist auch dann grün, wenn die Schleife gar nicht
    läuft — wenn das Muster nicht mehr trifft, die Dateien umziehen oder die
    Seiten leer sind. Sie sagen dann „kein Fehler gefunden" und meinen „nicht
    gesucht".

    Hier steht die Gegenzahl, und zwar über **alle** Seiten summiert: Einzeln
    hat nicht jede Seite Sprungmarken oder einen FAQ-Block, in der Summe aber
    sehr wohl. Die Untergrenzen sind bewusst weit unter dem gemessenen Stand
    (30 Seiten, 1517 Verweise, 12 mit Sprungmarken, 6 mit FAQ) — sie sollen
    einen Zusammenbruch fangen, nicht jede Änderung an der Website melden.
    """
    pages = sorted(WEBSITE.rglob("*.html"))
    assert len(pages) >= 10, f"nur {len(pages)} Seiten gefunden"

    links = jumps = questions = 0
    for page in pages:
        text = page.read_text(encoding="utf-8")
        links += len(LINK.findall(text))
        jumps += len(re.findall(r'href="(/[^"#]*#[^"]+)"', text))
        questions += len(re.findall(r"<summary>", text))

    assert links >= 100, f"nur {links} Verweise — findet LINK noch etwas?"
    assert jumps >= 5, f"nur {jumps} Sprungmarken auf andere Seiten"
    assert questions >= 3, f"nur {questions} FAQ-Blöcke"


# --- Was der Download-Kasten verspricht (§35 „Anschluss") --------------------------------


def _als_zahlen(fassung: str) -> tuple[int, ...]:
    """``"0.1.10"`` als ``(0, 1, 10)`` — damit 10 nach 9 kommt und nicht davor."""
    return tuple(int(teil) for teil in fassung.split(".") if teil.isdigit())


def test_the_version_file_says_what_the_application_is() -> None:
    """``website/version.json`` ist die einzige Stelle, an der der Kunde erfährt,
    dass es etwas Neues gibt — und bis zum 23.08.2026 sah sie kein Test an.

    **Was daran hängt.** Die Update-Prüfung (``app/core/updates.py``) liest diese
    Datei: Versionsnummer, Größe, Prüfsumme. Steht darin eine falsche Zahl,
    bricht das Update **bei jedem Kunden gleichzeitig**, und zwar erst nach dem
    Hochladen — der Fehler entsteht auf einem Rechner und wirkt auf allen.

    **Warum es keiner gemerkt hätte.** Am Tag des 0.1.3-Releases trugen drei
    erzeugte Paketmanifeste noch ``0.1.2``, während die Anwendung schon ``0.1.3``
    war; gefunden hat das ``test_packaging.py``, weil es die erzeugten Dateien
    gegen ihr Werkzeug hält. Für ``version.json`` gab es kein solches Gegenüber:
    Sie wird von Hand gepflegt, liegt außerhalb von ``app/``, und
    ``test_website.py`` prüfte Verweise, nicht Inhalte.

    Geprüft wird deshalb das, was zusammengehören **muss** und aus zwei Quellen
    kommt: die Zahl in der Datei und die Zahl im Programm.
    """
    import json

    from app.branding import APP_VERSION

    payload = json.loads((WEBSITE / "version.json").read_text(encoding="utf-8"))
    veroeffentlicht = str(payload["version"])

    # **Die Website darf zurückliegen, aber nie vorauseilen.** Zwischen der
    # Versionserhöhung und dem Hochladen liegt bei jedem Release eine halbe
    # Stunde, in der die Anwendung schon 0.1.4 ist und die Seite noch 0.1.3
    # anbietet — und das ist richtig so: `version.json` sagt, was
    # **veröffentlicht** ist, und das stimmt erst, wenn die Pakete oben liegen.
    # Größe und Prüfsumme gibt es vorher gar nicht.
    #
    # **Die erste Fassung dieses Tests verlangte Gleichstand und hat damit den
    # Paketbau blockiert** — ein Kreis: Die Website braucht die Pakete, die
    # Pakete brauchen eine grüne Suite, die Suite verlangte die Website.
    # Gefunden von 3d-druck-bd am 23.08.2026, als 0.1.4 daran hängenblieb.
    #
    # Was hier bleibt, ist die Richtung: Eine Seite, die eine **neuere** Fassung
    # nennt als die gebaute, verspricht etwas, das es nicht gibt.
    assert _als_zahlen(veroeffentlicht) <= _als_zahlen(APP_VERSION), (
        f"version.json nennt {veroeffentlicht}, gebaut ist erst {APP_VERSION} — "
        "die Seite verspricht eine Fassung, die es nicht gibt"
    )
    assert payload["packages"], "kein einziges Paket genannt — dann prüft der Rest nichts"
    for key, entry in payload["packages"].items():
        assert entry.get("url"), f"{key} ohne Adresse"
        assert isinstance(entry.get("size"), int) and entry["size"] > 0, f"{key} ohne Größe"
        assert re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))), (
            f"{key}: sha256 ist keine sechzigstellige Hexzahl"
        )
        # **Beide Namensfelder, und zwar gegeneinander.** ``updates.py`` liest
        # ``url`` *und* ``file`` — das eine, um zu laden, das andere, um zu
        # benennen. Ein Test, der nur eines prüft, lässt das andere altern: Die
        # Gegenprobe zu diesem Test blieb genau daran grün, weil der Paketname
        # zweimal in der Datei steht und die Mutation das ungeprüfte Feld traf.
        # **Mit Wortgrenze, nicht als Teilzeichenkette.** ``"0.1.3" in name``
        # ist auch für ``Solidon3D-Setup-0.1.30.exe`` wahr — bei 1.1.3 gegen
        # 1.1.30 ist das kein erdachter Fall. Geprüft wird deshalb, dass hinter
        # der Fassung keine weitere Ziffer und kein Punkt mit Ziffer steht. Der
        # Punkt vor ``exe`` ist ein Trennzeichen und muss durch — die erste
        # Fassung schloss ihn mit aus und machte den Test rot.
        # Gegen die **veröffentlichte** Fassung, nicht gegen die gebaute: Die
        # Datei beschreibt sich selbst, und ihre Einträge müssen zu ihrer
        # eigenen Versionsnummer passen — das ist die Aussage, die trägt,
        # solange die Seite noch zurückliegen darf.
        aktuell = re.compile(rf"{re.escape(veroeffentlicht)}(?!\d)(?!\.\d)")
        for feld in ("url", "file"):
            assert aktuell.search(str(entry.get(feld, ""))), (
                f"{key}.{feld} ist {entry.get(feld)!r} — das ist nicht Fassung {veroeffentlicht}"
            )
        assert str(entry["url"]).endswith(str(entry["file"])), (
            f"{key}: url endet auf {str(entry['url']).rsplit('=', 1)[-1]!r}, "
            f"file sagt {entry['file']!r} — die Anwendung lädt das eine und "
            "benennt es nach dem anderen"
        )

    # **Der Hinweistext steht über der übersetzten Punkteliste** und gehört
    # deshalb selbst übersetzt (``updates.Release.note``). Geprüft wird nur,
    # *wenn* das Feld dasteht: ``notes_by_language`` ist neu in 0.2.0, und eine
    # Datei ohne es ist keine kaputte, sondern eine ältere — dann greift der
    # Rückfall auf ``notes``. Steht es aber da, muss es vollständig sein; eine
    # fehlende Sprache fällt sonst erst dem Kunden auf, der sie spricht.
    sprachen = payload.get("notes_by_language")
    if sprachen:
        from app.i18n.catalog import available_languages

        fehlend = sorted(set(available_languages()) - set(sprachen))
        assert not fehlend, (
            f"notes_by_language kennt {sorted(sprachen)}, es fehlen {fehlend} — "
            "diese Kunden lesen den Hinweis in einer fremden Sprache"
        )
        for sprache, satz in sprachen.items():
            assert isinstance(satz, str) and satz.strip(), f"{sprache}: leerer Hinweis"


@pytest.mark.parametrize(
    "page",
    sorted(WEBSITE.glob("**/index.html")),
    ids=lambda p: p.parent.name or "de",
)
def test_every_download_link_names_the_current_version(page: Path) -> None:
    """Der Download-Kasten darf nicht auf die Vorfassung zeigen.

    **Die Lücke, die das schließt.** Der Verweistest oben überspringt ``/dl/``
    ausdrücklich, und das zu Recht: Die Pakete wiegen zusammen fast ein Gigabyte
    und liegen nicht im Repository. Sein Kommentar sagt selbst, was daraus folgt
    — *„Dass die Datei auf dem Server wirklich liegt, prüft kein Test."*

    Prüfbar ist trotzdem etwas, und zwar ohne ein einziges Megabyte: **ob der
    Name die Fassung trägt, die die Anwendung ist.** Ein Kasten, der nach einer
    Versionserhöhung noch die alten Dateien nennt, führt jeden Besucher auf einen
    404 — die Pakete der Vorfassung werden beim Veröffentlichen gelöscht, damit
    niemand versehentlich eine alte Fassung zieht.

    Das ist derselbe Fehler wie bei den Paketmanifesten, nur eine Ebene weiter
    außen: Eine Stelle, die die Versionsnummer trägt und beim Erhöhen vergessen
    wird.
    """
    import json

    # **Gegen ``version.json``, nicht gegen die gebaute Fassung.** Die Seite und
    # die Versionsdatei gehören zusammen: Sie werden im selben Zug hochgeladen
    # und beschreiben denselben Stand. Ob dieser Stand der neueste ist, prüft
    # der Test darüber — hier geht es darum, dass Kasten und Datei **einander**
    # nicht widersprechen. Ein Kasten, der etwas anderes anbietet als
    # ``version.json`` verspricht, führt ins Leere, ganz gleich welche Fassung
    # gerade gebaut ist.
    veroeffentlicht = str(
        json.loads((WEBSITE / "version.json").read_text(encoding="utf-8"))["version"]
    )

    html = page.read_text(encoding="utf-8")
    names = set(re.findall(r"/dl/([A-Za-z0-9._-]+)", html))
    names |= set(re.findall(r"count\.php\?f=([A-Za-z0-9._-]+)", html))
    assert names, f"{page.parent.name or 'de'}/index.html nennt kein einziges Paket"

    aktuell = re.compile(rf"{re.escape(veroeffentlicht)}(?!\d)(?!\.\d)")
    stale = sorted(name for name in names if not aktuell.search(name))
    assert not stale, (
        f"{page.parent.name or 'de'}/index.html bietet noch: {stale}\n"
        f"version.json nennt {veroeffentlicht}, und die alten Pakete werden beim "
        "Veröffentlichen vom Server gelöscht — die Verweise gingen ins Leere."
    )


#: Wie viele Tage vor dem Demo-Ende die Website ihre Datumssätze umstellen muss.
#:
#: Fünf Tage sind kein runder Wert, sondern der Abstand, in dem sich beides
#: noch ausgeht: die für den Verkauf bereits entschiedenen Sätze in sechs
#: Sprachen umschreiben und hochladen. Wer am 30. merkt, dass die Seite den 30.
#: verspricht, hat keinen Tag mehr.
TRANSITION_LEAD_DAYS = 5


def test_the_pages_do_not_promise_a_date_that_is_about_to_pass(
    shipped_demo_until: object,
) -> None:
    """Erinnert rechtzeitig an die Umstellung der vier Demo-Datumssätze.

    „Die Demo läuft bis zum 30. Oktober 2026" steht auf den Startseiten in
    sechs Sprachen an mehreren Stellen, dazu die Frage „Was passiert am
    30. Oktober?" und der Einführungspreis bis 31.01.2027. Am 31. Oktober
    werden diese Sätze **still** falsch: Sie sehen aus wie vorher, und niemand
    bekommt eine Meldung.

    **Nicht zu verwechseln mit dem Wecker in ``test_activation.py``**
    (``test_the_shipped_deadline_has_not_passed``). Der fragt, ob die
    ausgelieferte Demo noch läuft, und wird am **31.10.** rot — für die
    Website ist das der Tag zu spät. Dieser hier fragt, ob noch Zeit bleibt,
    die Sätze zu ändern, und schlägt fünf Tage vorher an. Zwei Fragen, zwei
    Tests, dieselbe Quelle.

    Was danach gilt, ist seit dem 28.08.2026 entschieden: Verkauf ab 01.11.,
    keine zusätzliche Testphase, 69 Euro bis 31.01.2027 und danach 99 Euro.
    Die heutigen Zukunftssätze sind bis zum Demo-Ende richtig; dieser Test
    sorgt dafür, dass sie rechtzeitig in Gegenwartsform umgeschrieben werden.

    **Er hängt an ``DEMO_UNTIL`` und nicht an einer zweiten Zahl.** Wird die
    Demo verlängert, verschiebt sich die Erinnerung von selbst mit; ein hier
    eingetragenes Datum wäre der Zwilling, den die Frist überlebt.

    Der echte Stichtag kommt über ``shipped_demo_until`` und nicht aus dem
    Modul: ``conftest`` setzt ``DEMO_UNTIL`` für die ganze Suite auf ``None``,
    sonst wäre sie ab dem Stichtag an Dutzenden Stellen rot. Ohne die Fixture
    übersprang dieser Test sich selbst — grün, und ohne je etwas geprüft zu
    haben.
    """
    from datetime import date, timedelta

    if shipped_demo_until is None:
        pytest.skip("Verkaufsversion ohne Stichtag — es gibt keinen Tag, an dem die Sätze kippen")

    assert isinstance(shipped_demo_until, date)
    faellig = shipped_demo_until - timedelta(days=TRANSITION_LEAD_DAYS)
    heute = date.today()
    assert heute < faellig, (
        f"Die Demo endet am {shipped_demo_until:%d.%m.%Y}, heute ist der "
        f"{heute:%d.%m.%Y}. "
        "Vier Datumsangaben auf den Startseiten werden danach still falsch: der "
        "Satz „läuft bis zum 30. Oktober“ (sechs Sprachen, mehrere Stellen), die "
        "FAQ-Frage „Was passiert am 30. Oktober?“ und der Einführungspreis bis "
        "31.01.2027. "
        "Die Sätze auf den bereits entschiedenen Verkaufszustand umschreiben. "
        "Nur eine neue ausdrückliche Entscheidung darf stattdessen DEMO_UNTIL "
        "in app/core/activation/store.py verschieben; dann wandert diese "
        "Erinnerung mit."
    )


@pytest.mark.parametrize("page", START_PAGES)
def test_the_generated_faq_markup_keeps_no_gap_before_a_comma(page: str) -> None:
    """Die erzeugte FAQ-Auszeichnung trägt keine Lücke vor Komma oder Punkt.

    ``make_seo.py`` leitet die ``FAQPage``-Auszeichnung aus dem sichtbaren
    FAQ-Block ab und ersetzt dabei jedes Tag durch ein Leerzeichen — sonst
    klebte das Ende eines Absatzes am Anfang des nächsten. Steht hinter dem Tag
    ein Satzzeichen, entstand daraus eine Lücke davor: ``…als Baustein
    speichern .`` und ``…Version 1.0 , die``. Am 28.08.2026 stand das an neun
    Stellen in fünf Sprachen, sichtbar für jede Suchmaschine.

    Geprüft wird nur vor Komma und Punkt. Vor ``; : ! ?`` setzt die
    französische Fassung bewusst ein Leerzeichen; ein Wächter über alle
    Satzzeichen würde sie fälschlich anklagen.
    """
    daten = (WEBSITE / page).read_text(encoding="utf-8")
    bloecke = re.findall(r'<script type="application/ld\+json">(.*?)</script>', daten, re.DOTALL)
    antworten = [
        eintrag["acceptedAnswer"]["text"]
        for daten_block in (json.loads(block) for block in bloecke)
        if daten_block.get("@type") == "FAQPage"
        for eintrag in (daten_block.get("mainEntity") or [])
    ]
    assert antworten, f"{page} trägt keine FAQ-Auszeichnung — prüft dieser Test noch etwas?"

    for text in antworten:
        luecken = re.findall(r"\S (?=[,.])", text)
        assert not luecken, (
            f"{page}: Auszeichnung endet vor einem Satzzeichen und hinterlässt eine "
            f"Lücke — {luecken}. Im sichtbaren Text die Auszeichnung ans Satzende "
            "ziehen, oder _plain in tools/make_seo.py prüfen."
        )


def test_the_offline_activation_page_is_one_plain_three_step_path() -> None:
    """Der Ausnahmeweg erklärt sich ohne Konto-, CAD- oder Serverwissen."""
    html = (WEBSITE / "offline-aktivierung.html").read_text(encoding="utf-8")

    assert html.count('class="activation-steps"') == 1
    assert html.count('class="activation-stepmark"') == 1
    assert html.count(">2</p>") == 1
    assert 'id="request-file"' in html
    assert 'id="request-text"' in html, "Einfügen bleibt als barrierearmer Rückfall"
    assert 'class="activation-paste"' in html, (
        "der technische Rückfall dominiert nicht den Hauptweg"
    )
    assert html.count('type="submit"') == 1, "ein Arbeitsgang hat einen Hauptknopf"
    assert "support@solidon3d.de" in html


def test_the_offline_activation_page_localises_visible_and_accessible_text() -> None:
    """Die aus der Anwendung übergebene Sprache gilt auch für Screenreader."""
    html = (WEBSITE / "offline-aktivierung.html").read_text(encoding="utf-8")
    script = (WEBSITE / "activation.js").read_text(encoding="utf-8")

    languages = set(re.findall(r"^    (de|en|es|fr|it|pt): \{", script, re.MULTILINE))
    assert languages == {"de", "en", "es", "fr", "it", "pt"}
    assert 'new URLSearchParams(window.location.search).get("lang")' in script
    assert html.count("data-i18n-aria=") >= 3
    assert 'querySelectorAll("[data-i18n-aria]")' in script
    for key in (
        "skip",
        "brand_home",
        "language_navigation",
        "steps_label",
        "no_file",
        "selected_file",
    ):
        assert script.count(f"{key}:") == 6, key
    assert 'id="request-file-name"' in html
    assert "updateFileName();" in script


def test_the_offline_activation_page_explains_errors_instead_of_claiming_success() -> None:
    """Netz-, Datei- und Serverfehler behalten Überschrift und nächsten Schritt."""
    script = (WEBSITE / "activation.js").read_text(encoding="utf-8")

    for key in (
        "error_title",
        "error_file",
        "error_network",
        "error_device_limit",
        "error_rate_limit",
        "error_wrong_major",
        "error_licence_blocked",
        "error_service_unavailable",
        "error_invalid_request",
    ):
        assert script.count(f"{key}:") == 6, key
    assert 'kind === "loading" ? "checking_title" : "error_title"' in script
    assert "problem instanceof TypeError" in script
    assert "MAX_REQUEST_BYTES = 32768" in script
    assert 'form.setAttribute("aria-busy", "true")' in script
    assert 'kind === "error" ? "alert" : "status"' in script


def test_a_new_offline_request_clears_every_previous_answer() -> None:
    """Eine kaputte zweite Datei darf nie die Antwort der ersten zum Download lassen."""
    script = (WEBSITE / "activation.js").read_text(encoding="utf-8")

    assert "const resetResult = () =>" in script
    assert 'answer = "";' in script
    assert "result.hidden = true;" in script
    assert "delete result.dataset.state;" in script
    assert "download.hidden = true;" in script
    file_handler = script.split('file.addEventListener("change"', 1)[1]
    assert file_handler.index("resetResult();") < file_handler.index("chosen.size")
    assert 'text.addEventListener("input", () =>' in script


def test_a_video_and_its_poster_both_carry_a_stamp() -> None:
    """Ein Loop ist die größte Datei der Seite — und sein Standbild das erste.

    Beide brauchen den Inhaltsstempel, und beide fielen bisher durch:
    ``mp4``/``webm`` standen nicht in ``SUFFIXES``, und das Standbild hängt an
    einem **eigenen Attribut**. Ein Video trägt es in ``poster=``, nicht in
    ``src=`` — der Ausdruck kannte nur ``src`` und ``href``.

    Was das kostet, wenn es fehlt: Ein Besucher, der die Seite kennt, bekommt
    beim nächsten Besuch den **alten** Loop aus dem Browser-Cache, während die
    Seite drumherum neu ist. Und bei ``prefers-reduced-motion`` ist das
    Standbild das einzige, was er überhaupt sieht.
    """
    from tools.stamp_assets import LINK, SUFFIXES

    assert "mp4" in SUFFIXES and "webm" in SUFFIXES, SUFFIXES

    trifft = [
        '<source src="bilder/hero.mp4" type="video/mp4">',
        '<source src="bilder/hero.webm" type="video/webm">',
        '<video poster="bilder/hero-standbild.png" muted loop>',
        # Und das Bestehende bleibt, wie es war.
        '<img src="bilder/beleg-eins.png" alt="x">',
        '<link href="style.css" rel="stylesheet">',
    ]
    for zeile in trifft:
        assert LINK.search(zeile), f"ungestempelt: {zeile}"

    # Die Gegenprobe, sonst prüfte der Test einen Ausdruck, der alles trifft:
    # Fremde Adressen und eingebettete Daten bleiben außen vor.
    daneben = [
        '<source src="https://fremd.example/hero.mp4">',
        '<video poster="data:image/png;base64,AAAA">',
        '<a href="#preis">',
        '<img src="/api/count.php">',
    ]
    for zeile in daneben:
        assert not LINK.search(zeile), f"hätte nicht treffen dürfen: {zeile}"


#: Tags, die ohne schließendes Gegenstück stehen dürfen (HTML-Leerelemente).
#: Alles andere ist paarig, und wo ein Partner fehlt, hat jemand beim Umbauen
#: einen Block falsch geschnitten.
VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)

#: Die Container, deren Balance zählt. Genau sie tragen die Seitenstruktur,
#: und genau bei ihnen kostet ein fehlender Partner die Anordnung.
PAIRED_TAGS = ("div", "section", "ul", "ol", "li", "details", "dialog", "form", "p")


@pytest.mark.parametrize("page", ALL_PAGES)
def test_every_page_closes_the_tags_it_opens(page: str) -> None:
    """Ein fehlendes ``</div>`` sieht im Browser aus wie gar nichts.

    **Der Anlass, am 30.08.2026 gemessen.** Der Umbau des Aufmachers (WD2)
    verschob ganze Blöcke; in der englischen Fassung fing die Endmarke des
    Download-Kastens **zwei** schließende Tags, und nur eines gehörte ihm. Die
    Seite hatte danach ein ``</div>`` zu wenig — und sah im Browser
    **vollständig heil aus**: Ein Browser repariert unbalanciertes Markup
    stillschweigend und ohne ein Wort in der Konsole.

    Kein bestehender Test hätte es gemeldet. Diese Datei prüft Verweise,
    Zahlen, Bildgrößen, Stempel und Sprungmarken — alles Dinge, die von einer
    verschobenen Verschachtelung unberührt bleiben. Gefunden hat es eine
    Zählung von Hand, gefahren an *einer* Sprache, bevor die anderen vier
    liefen; ohne diesen Zwischenschritt wären fünf Dateien beschädigt gewesen.

    Gezählt wird und nicht geparst: Ein vollständiger HTML-Parser wäre hier
    die schwerere Antwort auf eine leichtere Frage. Was schiefgeht, wenn
    jemand Blöcke verschiebt, ist die **Anzahl** — ein Partner fehlt oder
    steht doppelt.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    # Kommentare heraus: Sie tragen Beispiel-Markup, das nichts öffnet.
    ohne_kommentar = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    schief = []
    for tag in PAIRED_TAGS:
        assert tag not in VOID_TAGS, f"{tag} ist ein Leerelement und hat nie einen Partner"
        auf = len(re.findall(rf"<{tag}\b", ohne_kommentar))
        zu = len(re.findall(rf"</{tag}>", ohne_kommentar))
        if auf != zu:
            schief.append(f"{tag}: {auf} geöffnet, {zu} geschlossen")

    assert not schief, (
        f"{page}: die Verschachtelung geht nicht auf — {', '.join(schief)}. "
        "Im Browser fällt das nicht auf, er repariert es stumm."
    )


def test_the_showpiece_only_uses_operations_that_exist() -> None:
    """Jeder Schritt des Schaustücks nennt eine Operation, die es gibt.

    Das Schaustück wird **nicht** in der Suite gebaut: Die zwölf Schritte
    rechnen achtzigtausend Dreiecke, und eine Verrundung über den exakten Kern
    dauert. Was hier geprüft wird, ist deshalb das, was ohne Rechnen prüfbar
    ist und trotzdem der häufigste Fehler war — ein Operationsname, den es
    nicht gibt, und ein Parameter, den die Operation nicht kennt.

    Beim Bauen kostete genau das vier Anläufe: ``thickness`` statt ``wall``,
    ``vents=12`` bei einem Maximum von sechs, ``create_box`` statt
    ``create_brep_box``. Die Namen stehen im Register; wer sie rät, merkt es
    erst an der angehaltenen Kette.
    """
    import dataclasses

    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from tools.make_showpiece import steps

    load_operations()
    schritte = steps()
    assert len(schritte) >= 10, f"das Schaustück ist auf {len(schritte)} Schritte geschrumpft"

    for title, drafts in schritte:
        assert drafts, f"{title}: ein Schritt ohne Operation"
        for draft in drafts:
            operation = REGISTRY.get(draft.op)
            bekannt = {
                feld.name
                for feld in dataclasses.fields(operation.params)
                if dataclasses.is_dataclass(operation.params)
            }
            fremd = set(draft.params) - bekannt
            assert not fremd, (
                f"{title}: {draft.op} kennt {sorted(fremd)} nicht — es hat {sorted(bekannt)}"
            )


def test_the_showpiece_shows_its_own_work() -> None:
    """Der Deckel liegt daneben, und beide Körper tragen eine eigene Farbe.

    **Der erste Aufbau setzte den Deckel auf**, und das Bild zeigte eine
    geschlossene Kiste: Schraubdome, Rippen, Wandstärke und Aushöhlung — die
    ganze Arbeit — waren unsichtbar. Ein Schaustück, das seine eigene Arbeit
    versteckt, zeigt eine Kiste, und dafür braucht niemand ein CAD-Programm.

    Geprüft wird die Absicht am Drehbuch, nicht am gerechneten Teil: dass ein
    Schritt den Deckel versetzt, und dass zwei verschiedene Materialslots
    vergeben werden.
    """
    from tools.make_showpiece import steps

    alle = [draft for _title, drafts in steps() for draft in drafts]

    versetzt = [d for d in alle if d.op == "translate_object"]
    assert versetzt, "ohne Versatz liegt der Deckel auf dem Gehäuse und verdeckt alles"
    assert any(abs(float(d.params.get("dx", 0) or 0)) > 50 for d in versetzt), (
        "der Versatz ist zu klein, um den Deckel neben das Gehäuse zu legen"
    )

    slots = {d.params.get("slot") for d in alle if d.op == "assign_slot"}
    assert len(slots) >= 2, f"zwei Farben machen aus einer grauen Kiste ein Produkt: {slots}"
