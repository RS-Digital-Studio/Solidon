"""Kürzel im Kundentext heißen, wie die Tastatur des Kunden sie beschriftet.

Über sechzig Sätze nennen „Strg+Z“, in den Katalogen „Ctrl+Z“. Auf dem Mac
ist das ⌘Z, und Control+Z tut dort nichts. Die Umschreibung
(:mod:`app.i18n.keys`) nimmt die Plattform als Argument, also prüft diese Datei
die Mac-Schreibweise auf jeder Maschine — und dass Windows und Linux keinen
Buchstaben anders lesen.
"""

from __future__ import annotations

import functools
import inspect
import re
import sys

import pytest

from app.i18n import (
    SOURCE_LANGUAGE,
    key_names,
    key_platform,
    set_key_platform,
    set_language,
    tr,
)
from app.i18n.catalog import available_languages, install_language, read_catalog
from app.i18n.keys import KeyNames, native_keys

#: Ein Kürzel in der Schreibweise der Quelle und der Kataloge.
_PC_COMBO = re.compile(r"(?<![\w+])(?:(?:Strg|Ctrl|Umschalt|Shift|Alt)\+)+[A-Z0-9](?![\w+])")


#: Wie die Quelle die beiden Einzeltasten nennt, an denen die Mac-Schreibweise hängt.
_SOURCE_DELETE = re.compile(r"(?<![\w+])Entf(?![\w+])")
_SOURCE_HOME = re.compile(r"(?<![\w+])Pos1(?![\w+])")


@functools.cache
def _names(language: str) -> KeyNames:
    """Wie die Texte einer Sprache Entf und Pos1 nennen — aus ihrem Katalog, wie ``tr``.

    Einmal je Sprache: Die Kataloge zu laden kostet, und die Prüfung über den
    ganzen Bestand fragt achtzigtausendmal.
    """
    if language != SOURCE_LANGUAGE:
        install_language(language)
    return key_names(language)


def _every_text() -> list[str]:
    """Jeder Text der Kataloge, Quelle und Übersetzung."""
    return [text for _language, text in _every_text_with_its_language()]


def _every_text_with_its_language() -> list[tuple[str, str]]:
    """Jeder Text der Kataloge mit der Sprache, in der er geschrieben ist."""
    texts: list[tuple[str, str]] = []
    for language in available_languages():
        if language == SOURCE_LANGUAGE:
            continue
        for key, value in read_catalog(language).items():
            texts.extend(((SOURCE_LANGUAGE, key), (language, value)))
    return texts


@pytest.mark.parametrize(
    ("written", "on_a_mac"),
    [
        ("Strg+Z", "⌘Z"),
        ("Ctrl+K", "⌘K"),
        ("Strg+Umschalt+P", "⇧⌘P"),
        ("Ctrl+Shift+P", "⇧⌘P"),
        ("Alt+7", "⌥7"),
        ("Strg+Alt+F5", "⌥⌘F5"),
        # Wiederholen hängt an StandardKey.Redo: auf dem Mac ⇧⌘Z, ⌘Y tut nichts.
        ("Strg+Y", "⇧⌘Z"),
        ("Ctrl+Y", "⇧⌘Z"),
    ],
)
def test_a_combination_is_written_as_the_mac_keyboard_labels_it(
    written: str, on_a_mac: str
) -> None:
    """Die Zeichen und ihre Folge sind die von ``QKeySequence`` auf dem Mac (⌃⌥⇧⌘)."""
    assert native_keys(f"Rückweg über {written}.", "darwin") == f"Rückweg über {on_a_mac}."
    assert native_keys(f"(`{written}`)", "darwin") == f"(`{on_a_mac}`)"


@pytest.mark.parametrize(
    "text",
    ["Strg+Klick wählt mehrere", "RAIL++-M", "Alt+Mitte schiebt", "3+4", "Strg+", "Shift+Tab"],
)
def test_what_is_no_single_key_stays_as_it_is(text: str) -> None:
    """Nur Umschalttasten mit genau einer Buchstaben-, Ziffern- oder F-Taste dahinter."""
    assert native_keys(text, "darwin") == text


@pytest.mark.parametrize(
    ("language", "written", "on_a_mac"),
    [
        ("de", "Bedingung entfernen  (Entf)", "Bedingung entfernen  (⌫)"),
        ("en", "Del removes the selected one.", "⌫ removes the selected one."),
        ("es", "Supr elimina la seleccionada.", "⌫ elimina la seleccionada."),
        (
            "fr",
            "**Suppr touche la caractéristique, pas le corps.**",
            "**⌫ touche la caractéristique, pas le corps.**",
        ),
        ("it", "Libera tutti i {count}  (Canc)", "Libera tutti i {count}  (⌫)"),
        ("pt", "`Del` apaga a seleção", "`⌫` apaga a seleção"),
        ("de", "*Einpassen* (`Pos1`) holt alles.", "*Einpassen* (`↖`) holt alles."),
        ("fr", "Origine (*Ajuster à la vue*) cadre", "↖ (*Ajuster à la vue*) cadre"),
    ],
)
def test_a_single_key_is_written_as_the_mac_keyboard_labels_it(
    language: str, written: str, on_a_mac: str
) -> None:
    """Entf ist am Mac ⌫, Pos1 ist ↖ — in jeder Sprache so, wie ihr Katalog die Taste nennt.

    Die Taste „delete“ der Mac-Tastatur sendet Backspace und löscht dort, wo
    Entf löscht (``shortcut_schemes.delete_keys``); ↖ schreibt Qt dort für
    Pos1, am Laptop fn+←.
    """
    assert native_keys(written, "darwin", _names(language)) == on_a_mac
    assert native_keys(written, "win32", _names(language)) == written


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("es", "Del dibujo salió un cuerpo."),
        ("it", "Del corpo non resta nulla: l'utensile lo copre completamente."),
        ("en", "Home"),
        ("en", "Delete selection"),
        ("fr", "Origine de la cote inconnue"),
        ("es", "Inicio"),
        # Der Mac hat keine Einfügetaste; ein Satz mit ihr bleibt, wie er ist.
        ("de", "Davor einfügen  (Einfg)"),
    ],
)
def test_a_word_that_only_looks_like_a_key_stays_a_word(language: str, text: str) -> None:
    """„Del“ ist im Spanischen und Italienischen ein Wort, „Home“ die Startseite."""
    assert native_keys(text, "darwin", _names(language)) == text


def test_on_a_mac_every_text_names_as_many_single_keys_as_its_source() -> None:
    """Am Mac nennt jeder Katalogtext so oft ⌫ und ↖, wie seine Quelle Entf und Pos1 nennt.

    Mehr hieße, ein Wort wurde zur Taste („Origine de la cote“); weniger, eine
    Sprache schreibt die Taste anders, als :mod:`app.i18n.keys` sie kennt.
    """
    named = 0
    for language in available_languages():
        if language == SOURCE_LANGUAGE:
            continue
        for source, translated in read_catalog(language).items():
            if source.startswith("Taste\x04"):
                continue  # die Namen selbst, kein Satz, der eine Taste nennt
            expected = (len(_SOURCE_DELETE.findall(source)), len(_SOURCE_HOME.findall(source)))
            for written, text in ((SOURCE_LANGUAGE, source), (language, translated)):
                mac = native_keys(text, "darwin", _names(written))
                assert (mac.count("⌫"), mac.count("↖")) == expected, (written, mac[:200])
            named += sum(expected)
    assert named >= 30, f"nur {named} Einzeltasten in den Katalogen — dann prüft das nichts"


@pytest.mark.parametrize("platform", ["win32", "linux", "cygwin", ""])
def test_windows_and_linux_read_every_text_unchanged(platform: str) -> None:
    """Die Gegenprobe: Außerhalb des Mac ändert sich kein einziger Katalogtext."""
    texts = _every_text_with_its_language()
    assert len(texts) > 1000, "die Kataloge wurden nicht gelesen"
    assert [native_keys(text, platform, _names(language)) for language, text in texts] == [
        text for _language, text in texts
    ]


def test_on_a_mac_no_catalogue_text_names_a_pc_key() -> None:
    """Jeder Satz mit Kürzel, in jeder Sprache, spricht auf dem Mac vom Mac."""
    texts = _every_text()
    with_keys = [text for text in texts if _PC_COMBO.search(text)]
    assert len(with_keys) > 300, f"zu wenige Sätze mit Kürzel gefunden: {len(with_keys)}"
    left = [text for text in with_keys if _PC_COMBO.search(native_keys(text, "darwin"))]
    assert not left, f"noch mit PC-Kürzel: {left[:3]}"
    assert all(
        "⌘" in native_keys(text, "darwin") or "⌥" in native_keys(text, "darwin")
        for text in with_keys
    )


def test_the_translation_writes_the_keys_of_the_set_platform() -> None:
    """``tr`` ist die eine Stelle: Quelle und Katalog, Kern und Oberfläche."""
    # Der Satz der Tour (``core/tour.py``), auf Englisch „… with Ctrl+Y …“.
    sentence = (
        "Holen Sie die Änderung mit Strg+Y zurück. Rückgängig und Wiederholen gelten "
        "für jeden Schritt."
    )
    english = read_catalog("en")[sentence]
    assert "Ctrl+Y" in english
    assert key_platform() == "", "ohne Start der Anwendung schreibt alles wie die Quelle"
    assert tr(sentence) == sentence
    try:
        set_key_platform("darwin")
        assert tr(sentence).startswith("Holen Sie die Änderung mit ⇧⌘Z zurück.")
        install_language("en")
        set_language("en")
        assert tr(sentence) == english.replace("Ctrl+Y", "⇧⌘Z")
        set_key_platform("win32")
        assert tr(sentence) == english, "unter Windows bleibt jeder Buchstabe"
    finally:
        set_key_platform("")
        set_language(SOURCE_LANGUAGE)


def test_the_translation_names_a_single_key_in_the_language_of_the_sentence() -> None:
    """``tr`` liest die Taste in der Sprache, in der der Satz dasteht.

    Ein unübersetzter Satz kommt aus der Quelle und nennt „Entf“, auch wenn
    Englisch eingestellt ist; am Mac wird er trotzdem ⌫.
    """
    sentence = "Entf entfernt die gewählte."
    english = read_catalog("en")[sentence]
    assert english.startswith("Del ")
    try:
        set_key_platform("darwin")
        install_language("en")
        set_language("en")
        assert tr(sentence) == english.replace("Del ", "⌫ ", 1)
        assert tr("Entf löscht, was noch niemand übersetzt hat.") == (
            "⌫ löscht, was noch niemand übersetzt hat."
        )
        set_key_platform("win32")
        assert tr(sentence) == english
    finally:
        set_key_platform("")
        set_language(SOURCE_LANGUAGE)


def test_the_start_of_the_application_sets_the_platform_of_this_machine() -> None:
    """Beide Startwege stellen ``sys.platform`` ein, bevor der erste Satz erscheint."""
    from app.ui import app as app_module

    for start in (app_module.main, app_module.build_application):
        source = inspect.getsource(start)
        assert "set_key_platform(sys.platform)" in source, start.__name__
        assert source.index("set_key_platform(sys.platform)") < source.index(
            "install_qt_translations("
        ), f"{start.__name__}: erst die Plattform, dann der erste Text"


def test_the_changes_window_writes_the_keys_of_the_set_platform() -> None:
    """Der Verlauf kommt aus einer Datei, nicht durch ``tr`` — und trotzdem mit ⌘Z."""
    from app.core.changes import Group
    from app.ui.changes_dialog import groups_html

    group = Group(title="Strg+K öffnet den Katalog", points=("Strg+Z nimmt es zurück.",))
    try:
        assert "Strg+Z" in groups_html((group,))
        set_key_platform("darwin")
        shown = groups_html((group,))
        assert "⌘Z nimmt" in shown and "⌘K öffnet" in shown
        assert "Strg+" not in shown
    finally:
        set_key_platform("")


@pytest.mark.skipif(sys.platform != "darwin", reason="Qt schreibt NativeText nur auf dem Mac so")
def test_the_mac_writing_is_the_one_qt_uses_there(qt_app: object) -> None:
    """Auf dem Mac selbst: dieselben Zeichen, die Menüs und Palette von Qt bekommen."""
    from PySide6.QtGui import QKeySequence

    native = QKeySequence.SequenceFormat.NativeText
    for portable, written in (
        ("Ctrl+Z", "Strg+Z"),
        ("Ctrl+Shift+P", "Strg+Umschalt+P"),
        ("Alt+7", "Alt+7"),
    ):
        assert native_keys(written, "darwin") == QKeySequence(portable).toString(native)
    redo = QKeySequence(QKeySequence.StandardKey.Redo).toString(native)
    assert native_keys("Strg+Y", "darwin") == redo
    assert native_keys("(Entf)", "darwin") == f"({QKeySequence('Backspace').toString(native)})"
    assert native_keys("(Pos1)", "darwin") == f"({QKeySequence('Home').toString(native)})"
