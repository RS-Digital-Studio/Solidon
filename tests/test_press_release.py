"""Die Pressemitteilung behauptet Zahlen — diese Datei prüft, dass sie stimmen.

Dasselbe Anliegen wie ``test_website.py``, eine Stufe schärfer: Eine falsche
Zahl auf der Website ist in einer Minute berichtigt, eine falsche Zahl in
einer verschickten Pressemitteilung steht am nächsten Tag in einem Artikel.
Sie kam schon einmal ins Rutschen — der Faktenblock nannte 77 Arbeitsschritte,
als längst 80 im Register standen.

Geprüft wird außerdem, was den Text für seinen Empfänger brauchbar hält: keine
Dateipfade aus dem Projekt und kein Fachjargon unterhalb der Trennlinie. Wer
die Mitteilung liest, hat das Programm nicht und liest keinen Quelltext.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge.parts.registry import PARTS
from app.core.registry import REGISTRY
from app.i18n.catalog import available_languages

RELEASE = Path(__file__).resolve().parent.parent / "marketing" / "pressemitteilung-demo-2026-08.md"
DATA = Path(__file__).resolve().parent.parent / "app" / "core" / "knowledge" / "data"
EXAMPLES = Path(__file__).resolve().parent.parent / "app" / "examples"

#: Die Umfangszeile des Faktenblocks, aus der jede Zahl einzeln fällt.
SCOPE = re.compile(
    r"\| Umfang \| (\d+) Arbeitsschritte, (\d+) geprüfte Bausteine, "
    r"(\d+) Normteilmaße, (\d+) Druckerprofile, (\d+) Beispielprojekte \|"
)

#: Was ein Empfänger nicht einordnen kann. Die Liste ist absichtlich kurz und
#: nennt nur, was tatsächlich schon dringestanden hat oder unmittelbar
#: droht — eine lange Verbotsliste würde beim ersten Umformulieren umgangen.
JARGON = (
    "auto:",
    "MCP",
    "Werkzeugaufruf",
    "Transaktion",
    "OpContext",
    "Op-Stack",
    "Registry",
    "Undo",
    "API-Schlüssel",
    "Telemetrie",
)

#: Ein Pfad ins Projekt. Der Empfänger hat das Repository nicht.
REPO_PATH = re.compile(r"`[^`]*(?:app|tests|tools|marketing|website)/[^`]*`")


@pytest.fixture(scope="module", autouse=True)
def _loaded() -> None:
    load_operations()


def _text() -> str:
    return RELEASE.read_text(encoding="utf-8")


def _for_the_press() -> str:
    """Nur der Teil, der hinausgeht — die Regieanweisung darüber nicht.

    Die Datei ist beides: Arbeitsblatt und Vorlage. Getrennt werden die
    beiden von der ersten Trennlinie; alles darüber ist für uns.
    """
    _, _, body = _text().partition("\n---\n")
    assert body, "Die Trennlinie zwischen Regieanweisung und Text fehlt"
    return body


def _count(table: str) -> int:
    loaded = tomllib.loads((DATA / table).read_text(encoding="utf-8"))
    return sum(len(v) for k, v in loaded.items() if k != "version" and isinstance(v, list))


def test_the_scope_line_matches_the_sources() -> None:
    """Jede Zahl der Umfangszeile steht so auch im Programm."""
    found = SCOPE.search(_text())
    assert found, "Die Umfangszeile fehlt oder hat eine andere Form"
    operations, parts, standards, printers, examples = (int(g) for g in found.groups())
    assert operations == len(REGISTRY.all())
    assert parts == len(PARTS.all())
    assert standards == _count("standards.toml")
    assert printers == len(tomllib.loads((DATA / "printers.toml").read_text(encoding="utf-8")))
    assert examples == len(list(EXAMPLES.glob("*.p3d")))


def test_every_delivered_language_is_named() -> None:
    """Die Sprachzeile zählt so viele Sprachen, wie ausgeliefert werden."""
    line = next(line for line in _text().splitlines() if line.startswith("| Sprachen |"))
    named = [part.strip() for part in line.split("|")[2].split(",")]
    assert len(named) == len(available_languages())


def test_the_press_text_carries_no_path_into_the_project() -> None:
    """Unterhalb der Trennlinie steht kein Dateipfad.

    Ein Pfad wie ``marketing/drehanleitung-video-1.md`` stand dort und war
    für den Empfänger nicht auflösbar — er hat das Projekt nicht.
    """
    found = REPO_PATH.findall(_for_the_press())
    assert not found, f"Pfade im Pressetext: {found}"


def test_the_press_text_explains_itself_without_the_code() -> None:
    """Unterhalb der Trennlinie steht kein Begriff aus der Entwicklung.

    Die Fähigkeiten dahinter bleiben drin — sie werden in Sätzen erklärt
    statt benannt. „Jeder Vorschlag ist genau eine Transaktion" sagt einem
    Journalisten nichts; „kommt als ein Schritt an, den ein einziges
    Rückgängig zurücknimmt" sagt dasselbe und wird verstanden.
    """
    body = _for_the_press()
    found = [word for word in JARGON if word in body]
    assert not found, f"Fachbegriffe im Pressetext: {found}"
