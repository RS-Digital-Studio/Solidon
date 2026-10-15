"""Begriffe in den Katalogen: Schreibweise und Trennschärfe einzelner Wörter.

`test_translations.py` prüft Vollständigkeit und Form jedes Eintrags; hier
stehen die Zusagen über **bestimmte** Wörter, die in einer Sprache anders
gelesen werden als im Deutschen — die Merkmalsarten als Kartenkopf, und zwei
deutsche Fachwörter, die in einer Sprache nicht zusammenfallen dürfen.
"""

from __future__ import annotations

import re

import pytest

from app.core.registry.registry import FEATURE_TITLES
from app.i18n.catalog import available_languages, read_catalog

#: Die Übersetzungssprachen — ohne Deutsch, das ist die Quelle.
LANGUAGES = tuple(language for language in available_languages() if language != "de")

#: Das Wort für *Überhang* je Sprache, aus den Glossaren in
#: ``.claude/rules/uebersetzung.md`` — im Englischen das Slicerwort.
OVERHANG_WORDS: dict[str, str] = {
    "en": "overhang",
    "es": "voladizo",
    "fr": "surplomb",
    "it": "sbalzo",
    "pt": "saliência",
}

#: Ein Schlüssel, der von einem *Überstand* spricht — auch „Hakenüberstand“.
PROTRUSION = re.compile(r"[Üü]berstand")
#: Und einer, der vom *Überhang* spricht; wer beides nennt, trennt sie selbst.
OVERHANG = re.compile(r"[Üü]berh[aä]ng")


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_feature_kind_starts_with_a_capital_letter(language: str) -> None:
    """FD-98: Eine Merkmalsart steht als Kopf von Karte und Baumzeile da.

    „peg · Ø6,00 mm“ sah neben „Hole“ und „Face“ wie ein Fehler aus: Der
    Eintrag „Zapfen“ war in fünf Sprachen klein übersetzt. Der Kopf beginnt
    groß wie im Deutschen; braucht ein Satz das Wort klein, bekommt er einen
    eigenen Schlüssel mit Kontext.
    """
    catalog = read_catalog(language)
    small = {
        str(title.msgid): catalog.get(str(title.msgid), "")
        for title in FEATURE_TITLES.values()
        if not catalog.get(str(title.msgid), "")[:1].isupper()
    }
    assert not small, f"{language}: Merkmalsarten beginnen klein: {small}"


def test_every_language_has_a_word_for_an_overhang() -> None:
    """Die Gegenprobe zu den Glossarwörtern: Jedes trifft im Katalog den Überhang."""
    for language in LANGUAGES:
        catalog = read_catalog(language)
        word = OVERHANG_WORDS[language]
        assert any(word in text.lower() for key, text in catalog.items() if OVERHANG.search(key)), (
            f"{language}: „{word}“ steht unter keinem Überhang — das Glossar stimmt nicht mehr"
        )


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_protrusion_is_never_called_an_overhang(language: str) -> None:
    """FD-147: *Überstand* und *Überhang* sind zwei Dinge.

    Der Überhang ist im Slicer die Fläche, die ohne Stütze in die Luft
    ragt; der Überstand ist, wie weit ein Teil über etwas hinaussteht — ein
    Haken über seinen Arm, ein Körper unter das Druckbett. Im Englischen
    hießen beide „overhang“: Ein Kunde las einen Überhang, wo ein Teil unter
    dem Bett steckt, und im Portugiesischen stand der Haken als „saliência“
    da, das Wort der Stützanalyse.
    """
    catalog = read_catalog(language)
    word = OVERHANG_WORDS[language]
    mixed = [
        f"{key[:60]} => {text[:80]}"
        for key, text in catalog.items()
        if PROTRUSION.search(key) and not OVERHANG.search(key) and word in text.lower()
    ]
    assert not mixed, f"{language}: Überstand als „{word}“ übersetzt:\n" + "\n".join(mixed)


#: Die Einleitung von *Parameter anlegen …* (``dialogs.py``) und die Beschreibung
#: von *Schrift einlegen* (``inlay_text``).
PARAMETER_INTRO = (
    "Ein Parameter ist ein benanntes Maß. Operationen und Skizzen verweisen mit @name darauf, "
    "und an der Zahl zu drehen baut das Modell neu."
)
INLAY_DOC = (
    "Legt Text bündig in eine Fläche ein. Die Buchstaben werden aus dem Körper geschnitten und "
    "als eigenes Teil in einer zweiten Farbe zurückgesetzt — ohne Spalt, ohne Überlappung, "
    "die Oberfläche bleibt eben."
)


@pytest.mark.parametrize(
    ("language", "key", "literal"),
    [
        # „An der Zahl drehen“ heißt ändern, nicht am Knopf drehen.
        ("en", PARAMETER_INTRO, "turning"),
        ("fr", PARAMETER_INTRO, "tourner"),
        ("it", PARAMETER_INTRO, "girare"),
        # „bündig“ ist rente/à face; zweimal „face“ hintereinander las sich doppelt.
        ("pt", INLAY_DOC, "à face numa face"),
    ],
)
def test_two_dialog_intros_say_what_the_german_means(language: str, key: str, literal: str) -> None:
    """FD-137: Zwei Einleitungen waren wörtlich oder doppeldeutig übersetzt."""
    text = read_catalog(language)[key]
    assert literal not in text, f"{language}: „{literal}“ in {text!r}"
