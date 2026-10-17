"""Fundstellen des Prüfpunkts 11 „Versprechen“ (RM-737, FD-150).

Was Website und Handbuch einer Funktion versprechen, findet Stufe A über ihr
Register: den Titel einer Operation auf den Funktionsseiten und ihre Stelle im
Handbuch (``function_report.manual_place``, ``_website_hits``). Fensterbefehle,
Dialoge und Befundhandlungen stehen in keinem Register — ihre Fundstellen nennt
die Zeilenspezifikation (``tests/data/function_rows/dNN.toml``):

* ``manual = "<seite>"`` oder ``"<ref-seite>#<anker>"`` — eine Seite des
  Handbuchs (``app.core.manual.pages``), auf einer Referenzseite mit der
  Sprungmarke einer Operation;
* ``website = ["funktionen.html#<anker>", …]`` — Abschnitte der deutschen
  Funktionsseite. Ihre Übersetzungen (``<sprache>/features.html``) tragen
  dieselben Abschnitte in derselben Folge; gefunden wird der Abschnitt an
  derselben Stelle.

Eine Spezifikation, die eine Stelle nennt, die es nicht gibt, ist ein Fehler
der Spezifikation (:func:`reference_problems`): Prüfpunkt 11 ist dann nicht
prüfbar, nie erfüllt. Der durchsuchte Text einer Seite schließt Bildtexte
(``alt``) und Titel (``title``) ein (:func:`page_text`) — ein Versprechen in
einer Bildunterschrift ist eines.
"""

from __future__ import annotations

import functools
import html
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
WEBSITE: Final = ROOT / "website"
#: Die deutsche Funktionsseite, an der die Spezifikation ihre Abschnitte nennt.
FEATURES_SOURCE: Final = "funktionen.html"
#: Die übersetzte Funktionsseite je Sprache, relativ zu ``website``.
FEATURES_TRANSLATED: Final = "{language}/features.html"

_TAG: Final = re.compile(r"<[^>]+>")
_SPOKEN: Final = re.compile(r"""\b(?:alt|title)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_ID: Final = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""")


def _attribute_text(tag: re.Match[str]) -> str:
    """Was ein Tag sagt, ohne gezeigt zu sein: Bildtext und Titel."""
    spoken = [first or second for first, second in _SPOKEN.findall(tag.group(0))]
    return " " + " ".join(spoken) + " "


@functools.cache
def page_text(path: Path) -> str:
    """Der lesbare Text einer Seite, klein: Fließtext samt ``alt`` und ``title`` (FD-150)."""
    raw = path.read_text(encoding="utf-8")
    return html.unescape(_TAG.sub(_attribute_text, raw)).lower()


@functools.cache
def _ids(path: Path) -> tuple[str, ...]:
    return tuple(_ID.findall(path.read_text(encoding="utf-8")))


@functools.cache
def _manual() -> tuple[frozenset[str], dict[str, frozenset[str]]]:
    """Seiten und Sprungmarken der Referenzseiten des Handbuchs."""
    from app.core import manual

    keys = frozenset(page.key for page in manual.pages())
    anchors = {
        key: frozenset(anchor for anchor, _title in manual.reference_anchors(key))
        for key in keys
        if key.startswith(manual.REFERENCE_PAGE_PREFIX)
    }
    return keys, anchors


def manual_problem(value: Any) -> str | None:
    """Warum ``manual`` keine Stelle im Handbuch nennt — ``None``, wenn es eine ist."""
    page, separator, anchor = str(value or "").partition("#")
    keys, anchors = _manual()
    if page not in keys:
        return f"Handbuchseite {page!r} gibt es nicht"
    if separator and anchor not in anchors.get(page, frozenset()):
        return f"Sprungmarke {anchor!r} gibt es auf {page} nicht"
    return None


def _languages() -> tuple[str, ...]:
    from app.i18n import SOURCE_LANGUAGE
    from app.i18n.catalog import available_languages

    return tuple(language for language in available_languages() if language != SOURCE_LANGUAGE)


def website_places(values: Sequence[Any]) -> tuple[list[str], list[str]]:
    """Die Abschnitte der Website in allen Sprachen und was an den Angaben nicht stimmt.

    Je Angabe ``funktionen.html#<anker>`` der deutsche Abschnitt und der an
    derselben Stelle jeder übersetzten Funktionsseite. Eine Seite, die nicht
    dieselbe Zahl Abschnitte trägt, ist nicht übersetzt, sondern verschieden —
    das ist ein Problem, kein Treffer.
    """
    places: list[str] = []
    problems: list[str] = []
    source = WEBSITE / FEATURES_SOURCE
    for value in values:
        name, _separator, anchor = str(value).partition("#")
        if name != FEATURES_SOURCE or not anchor:
            problems.append(f"Websitestelle {value!r} ist kein Abschnitt von {FEATURES_SOURCE}")
            continue
        own = _ids(source)
        if anchor not in own:
            problems.append(f"Abschnitt {anchor!r} gibt es auf {FEATURES_SOURCE} nicht")
            continue
        places.append(f"website/{FEATURES_SOURCE}#{anchor}")
        position = own.index(anchor)
        for language in _languages():
            translated = WEBSITE / FEATURES_TRANSLATED.format(language=language)
            theirs = _ids(translated) if translated.is_file() else ()
            if len(theirs) != len(own):
                problems.append(
                    f"{translated.relative_to(ROOT).as_posix()} folgt nicht der Gliederung"
                )
                continue
            places.append(f"{translated.relative_to(ROOT).as_posix()}#{theirs[position]}")
    return places, problems


def reference_problems(spec: Mapping[str, Any]) -> list[str]:
    """Was an den Fundstellen einer Zeilenspezifikation nicht stimmt — leer, wenn alles trifft."""
    problems = []
    if "manual" in spec and (problem := manual_problem(spec["manual"])) is not None:
        problems.append(problem)
    given = spec.get("website")
    if given is not None:
        if not isinstance(given, list) or not given:
            problems.append("website ist keine Liste von Abschnitten")
        else:
            problems += website_places(given)[1]
    return problems
