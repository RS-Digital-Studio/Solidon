"""Übersetzung ohne Qt.

Operationen, Bausteine und Fehler werden beim Import deklariert, lange bevor
eine Sprache gewählt ist — ``_()`` darf also nicht sofort übersetzen. Es gibt
einen trägen :class:`TranslatableText` zurück, der sich erst auflöst, wenn der
Text wirklich angezeigt wird (Bauplan §4.1, AGENTS.md Regel 20).

Der Kern erzeugt übersetzbare Texte; auflösen tut sie nur die Oberfläche.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Sprachen, mit denen die Anwendung ausgeliefert wird. Deutsch ist die
#: Quellsprache.
SOURCE_LANGUAGE: Final = "de"
SUPPORTED_LANGUAGES: Final = ("de", "en")

#: Wie eine Sprache heißt — **in sich selbst**, nicht übersetzt. Wer die
#: Anwendung in einer Sprache vorfindet, die er nicht liest, sucht in der
#: Auswahl nach dem Wort, das er kennt: „Deutsch" steht auch in der englischen
#: Oberfläche als „Deutsch" da. Aus demselben Grund steht hier kein ``_()``.
LANGUAGE_NAMES: Final[dict[str, str]] = {
    "de": "Deutsch",
    "en": "English",
}


def language_name(language: str) -> str:
    """Der anzeigbare Name einer Sprache. Rückfall ist ihr Kürzel."""
    return LANGUAGE_NAMES.get(language, language)


_catalogs: dict[str, dict[str, str]] = {}
_language: str = SOURCE_LANGUAGE


@dataclass(frozen=True, slots=True)
class TranslatableText:
    """Ein Text, der seinen Übersetzungsschlüssel selbst trägt.

    Vergleich und Hashing laufen über die Message-ID — die
    Registerkonsistenz-Prüfungen können diese Texte so wie Zeichenketten
    behandeln, ohne sie aufzulösen.
    """

    msgid: str
    context: str | None = None

    def translate(self, language: str | None = None) -> str:
        """Löst gegen den aktiven Katalog auf; Rückfall ist die Message-ID."""
        catalog = _catalogs.get(language or _language, {})
        return catalog.get(self._key(), self.msgid)

    def _key(self) -> str:
        return f"{self.context}\x04{self.msgid}" if self.context else self.msgid

    def __str__(self) -> str:
        return self.translate()


def _(msgid: str, context: str | None = None) -> TranslatableText:
    """Markiert einen Text zur Übersetzung. Der kanonische Name in
    Deklarationen."""
    return TranslatableText(msgid, context)


def tr(msgid: str, context: str | None = None) -> str:
    """Übersetzt sofort. Für Oberflächen, die jetzt eine nackte Zeichenkette
    brauchen."""
    return TranslatableText(msgid, context).translate()


def set_language(language: str) -> None:
    """Wechselt die aktive Sprache. Unbekannte fallen auf die Message-ID
    zurück."""
    global _language
    _language = language


def get_language() -> str:
    return _language


def install_catalog(language: str, catalog: dict[str, str]) -> None:
    """Registriert (oder erweitert) den Katalog einer Sprache."""
    _catalogs.setdefault(language, {}).update(catalog)


def known_languages() -> tuple[str, ...]:
    """Sprachen mit installiertem Katalog, plus die Quellsprache."""
    return tuple(dict.fromkeys((SOURCE_LANGUAGE, *sorted(_catalogs))))


#: Was beim Sortieren wie ein Grundbuchstabe zählt (DIN 5007-1). Ohne das
#: landet „Ändern" hinter „Zylinder": Python sortiert nach Codepunkt, und
#: „ä" steht dort hinter „z".
_FOLDED = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "Ä": "a", "Ö": "o", "Ü": "u", "ß": "ss"})


def sort_key(text: object) -> str:
    """Ein Schlüssel, nach dem sich Texte so ordnen, wie jemand sie liest.

    Menüs und Listen wurden bisher nach dem internen Namen sortiert — im Menü
    *Grundformen* stand deshalb „Quader, Exakter Quader, Exakter Zylinder,
    Zylinder, OpenSCAD, Kugel", weil die englischen Bezeichner ``create_box``,
    ``create_brep_box``, … in dieser Reihenfolge stehen. Der Nutzer liest die
    Titel und sucht darin.
    """
    return str(text).casefold().translate(_FOLDED)
