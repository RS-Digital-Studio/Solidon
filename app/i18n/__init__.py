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

#: Deutsch ist die Quellsprache: ihre Texte sind die Message-IDs, sie braucht
#: keinen Katalog. Welche Sprachen es sonst gibt, sagt nicht diese Datei,
#: sondern das Katalogverzeichnis — :func:`app.i18n.catalog.available_languages`.
SOURCE_LANGUAGE: Final = "de"

#: Wie eine Sprache heißt — **in sich selbst**, nicht übersetzt. Wer die
#: Anwendung in einer Sprache vorfindet, die er nicht liest, sucht in der
#: Auswahl nach dem Wort, das er kennt: „Deutsch" steht auch in der englischen
#: Oberfläche als „Deutsch" da. Aus demselben Grund steht hier kein ``_()``.
#:
#: Die Liste ist keine Anmeldung, sondern ein Wörterbuch: ein Eintrag hier
#: liefert keine Sprache aus, und eine Sprache ohne Eintrag erscheint mit
#: ihrem Kürzel statt ihrem Namen.
LANGUAGE_NAMES: Final[dict[str, str]] = {
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "pt": "Português",
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


#: Sprachen, die das Komma als Dezimaltrennzeichen schreiben. Englisch ist
#: unter den europäischen Sprachen die Ausnahme, nicht die Regel — wer eine
#: Sprache hinzufügt und sie hier vergisst, bekommt „0.2 mm" neben einer
#: Oberfläche, die „2,40 mm" anzeigt.
_DECIMAL_COMMA: Final = frozenset({"de", "es", "fr", "it", "pt"})


def format_decimal(value: float | int, digits: int | None = None) -> str:
    """Eine Zahl so geschrieben, wie die aktive Sprache sie schreibt.

    ``format_length`` im Kern lässt den Punkt ausdrücklich stehen, weil sein
    Ergebnis durch die Oberfläche geht und dort lokalisiert wird. Für Text, den
    der Kern **fertig** ausliefert, gilt das nicht: die erzeugte Hälfte des
    Handbuchs ging so mit 252 Zahlen der Form ``0.2`` in ein deutsches
    Handbuch, neben eine Anwendung, die im selben Bild ``2,40 mm`` anzeigt.

    ``digits`` gibt die Nachkommastellen vor; ohne Angabe steht die Zahl so
    kurz da, wie sie exakt ist — ``5`` bleibt ``5``, nicht ``5,0``.
    """
    text = f"{value:.{digits}f}" if digits is not None else f"{value:g}"
    return text.replace(".", ",") if _language in _DECIMAL_COMMA else text
