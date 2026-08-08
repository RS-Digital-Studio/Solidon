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
import tomllib
from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge.parts.registry import PARTS
from app.core.registry import REGISTRY

WEBSITE = Path(__file__).resolve().parent.parent / "website"
PAGES = ("index.html", "en/index.html")
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


@pytest.mark.parametrize("page", PAGES)
def test_every_file_the_page_refers_to_exists(page: str) -> None:
    source = WEBSITE / page
    missing = []
    for match in LINK.finditer(source.read_text(encoding="utf-8")):
        target = match.group(1)
        if target.startswith(("http", "mailto:", "#", "data:")):
            continue
        # Ein führender Schrägstrich meint die Wurzel der Website, kein
        # Wurzelverzeichnis der Festplatte.
        base = WEBSITE if target.startswith("/") else source.parent
        if not (base / target.lstrip("/")).exists():
            missing.append(target)
    assert not missing, f"{page} verweist auf {missing}"


@pytest.mark.parametrize("page", PAGES)
def test_the_page_stays_free_of_scripts_and_outside_hosts(page: str) -> None:
    """Die Seite lädt nichts nach und führt nichts aus.

    Das einzige ``<script>`` ist die Auszeichnung für Suchmaschinen —
    ``application/ld+json`` ist Daten, kein Code. Alles andere wäre ein
    Bruch mit `website/README.md`.
    """
    text = (WEBSITE / page).read_text(encoding="utf-8")
    scripts = re.findall(r"<script([^>]*)>", text)
    assert all('type="application/ld+json"' in tag for tag in scripts), scripts
    assert 'src="http' not in text
    assert 'href="http' not in text.replace('href="https://solidon3d.de', "")
