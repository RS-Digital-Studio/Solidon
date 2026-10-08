"""Das Handbuch nennt Bedienelemente so, wie das Programm sie zeigt und belegt.

Robert, Oktober 2026: „Handbuch — die richtige Bedienung über die Oberfläche
kontrollieren, hatte schon 2 Fälle, wo das Handbuch nicht zum Programm
passt.“ Ein Satz, der den Kunden an einen Knopf schickt, den es so nicht
gibt, liest sich so glatt wie ein richtiger.

Was schon anderswo gehalten wird, steht hier nicht noch einmal:

- Menüwege der geschriebenen Seiten je Sprache gegen Katalog und Leiste:
  ``test_manual.test_a_way_in_a_written_page_is_the_one_the_interface_shows``;
  am gebauten Fenster über die Rohtexte von ``manual.py`` und ``tour.py``:
  ``test_wording.test_every_menu_path_in_the_texts_exists_in_the_menu_bar``.
- Kursive Namen gegen jeden Katalogschlüssel:
  ``test_wording.test_every_control_the_texts_name_is_one_the_application_says``.
- Die Ziele der Bildanleitungen: ``test_guides``.

Dazu kommt hier, was jene nicht sehen:

1. **Kursive Namen gegen Texte außerhalb des Handbuchs.** Der Katalog führt
   auch die Absätze und Überschriften des Handbuchs selbst; ein Name, den nur
   das Handbuch sagt, bestand dort gegen sich selbst. Hier zählt nur, was
   Oberfläche, Kern, Register und Bausteine sagen, dazu die Titel und
   Zusammenfassungen der Handbuchseiten — die zeigt das Handbuchfenster in
   seiner Liste.
2. **„Menü *X*“** nennt ein Menü der Leiste.
3. **Menüwege der Bildanleitungen** — ihre Seiten entstehen aus
   ``guides.py``, und den liest keiner der Menüwegtests. Geprüft wird jeder
   kursive Weg jeder geschriebenen Seite am gebauten Fenster, und zwar genau
   so, wie er dasteht, ohne Wörter am Rand abzuschneiden.
4. **Tasten.** Jede genannte Taste ist im Fenster belegt, und steht sie
   neben einem Namen — *Datei → Bausteinkatalog …*, Strg+K —, dann gehört sie
   genau diesem Eintrag.

Geprüft wird die deutsche Quelle; dass jede Übersetzung Weg und Name der
Quelle folgt, halten ``test_manual`` und ``test_wording``.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Final

import pytest

from app.core import manual
from app.core.bootstrap import load_operations

ROOT: Final = Path(__file__).resolve().parent.parent

#: Ein kursiv ausgezeichneter Name: ein Sternchen, kein zweites daneben, und
#: innen kein Leerraum am Rand — sonst lesen sich Listenpunkt und Name einer
#: Zeile „* *Merkmal verschieben*“ als leerer Name „* *“.
NAME: Final = re.compile(r"(?<![*\w])\*([^*\s](?:[^*\n]{0,58}[^*\s])?)\*(?!\*)")

#: Was hinter einem Namen stehen darf, wenn das Programm ihn als Anfang eines
#: längeren Textes zeigt: „Bestimmt — jedes Maß steht fest.“ Dieselben
#: Trenner wie ``test_wording.TRENNER``.
SEPARATORS: Final = (" — ", " – ", ": ", " …", "…", " (")

#: Quellen, deren Texte selbst Anleitung sind und deshalb keinen Namen belegen.
INSTRUCTIONS: Final = frozenset({"manual.py", "tour.py", "guides.py"})

#: Ein kursiver Name, der kein Bedienelement meint → warum er so dasteht.
#: Jede Ausnahme muss noch gebraucht werden, sonst fliegt sie heraus.
NOT_A_CONTROL: Final[dict[str, str]] = {}

#: Ein Wort vor einem Pfeil, das kein Menü ist (``test_wording.KEIN_MENUE``).
NOT_A_MENU: Final = ("Rechtsklick",)

#: Eine Taste aus dem Handbuch, wie Qt sie schreibt. Deutsch ist die Quelle.
KEY: Final = re.compile(
    r"(?<![\w+`])(?:(?:Strg|Umschalt|Alt)\+)+(?:F\d{1,2}|Tab|Entf|Pos1|[A-Z0-9])(?![\w+])"
    r"|(?<![\w+])(?:F\d{1,2}|Entf|Esc|Escape|Pos1)(?![\w+])"
    r"|`[1-9]`"
)
_KEY_WORDS: Final = (
    ("Strg", "Ctrl"),
    ("Umschalt", "Shift"),
    ("Entf", "Del"),
    ("Escape", "Esc"),
    ("Pos1", "Home"),
)

#: Ein Name, unmittelbar gefolgt von seiner Taste: „*Datei → An den Slicer
#: übergeben* (Strg+P)“, „*Datei → Bausteinkatalog …*, `Strg+K`“.
NAME_AND_KEY: Final = re.compile(
    r"(?<![*\w])\*([^*\n]{1,80})\*,?\s\(?`?((?:(?:Strg|Umschalt|Alt)\+)+[^\s`),.;]+|F\d{1,2})`?"
)


def _plain(text: str) -> str:
    """Ein Bedientext, wie ihn ein Satz schreibt: ohne Mnemonic, Auslassung, Satzpunkt."""
    return text.replace("&", "").replace("…", "").replace("...", "").strip(" .:")


def _portable(key: str) -> str:
    """Eine Taste aus dem Handbuch in Qts portabler Schreibweise."""
    from PySide6.QtGui import QKeySequence

    key = key.strip("`")
    for german, portable in _KEY_WORDS:
        key = re.sub(rf"\b{german}\b", portable, key)
    return QKeySequence(key).toString(QKeySequence.SequenceFormat.PortableText)


def _written_pages() -> list[manual.Page]:
    """Die geschriebenen Seiten, Bildanleitungen eingeschlossen, in der Quellsprache."""
    load_operations()
    return [page for page in manual.pages() if not page.generated]


def _names(text: str) -> list[str]:
    """Die kursiven Namen eines Textes, die kein Menüweg sind."""
    return [_plain(name) for name in NAME.findall(text) if "→" not in name]


def _literals(files: Iterable[Path]) -> set[str]:
    """Jeder Text, den die Dateien über ``tr`` oder ``_`` ausgeben."""
    found: set[str] = set()
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("tr", "_")
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.add(_plain(node.args[0].value))
    return found


def _program_texts() -> set[str]:
    """Was das Programm außerhalb seiner Anleitungen sagt, und die Seitenliste des Handbuchs."""
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry.registry import REGISTRY

    load_operations()
    files = [path for path in (ROOT / "app").rglob("*.py") if path.name not in INSTRUCTIONS]
    texts = _literals(files)
    for spec in REGISTRY.all():
        texts.add(_plain(str(spec.title)))
        for entry in getattr(spec.params, "__param_spec__", ()):
            texts.add(_plain(str(entry.title)))
    texts |= {_plain(str(part.title)) for part in PARTS.all()}
    for page in manual.pages():
        texts |= {_plain(str(page.title)), _plain(str(page.summary))}
    texts |= {_plain(str(title)) for title in manual.PART_TITLES.values()}
    return texts


def _said(name: str, texts: set[str]) -> bool:
    """Sagt das Programm diesen Namen — allein oder als Anfang eines Textes?"""
    return name in texts or any(
        text.startswith(name + separator) for text in texts for separator in SEPARATORS
    )


def _unsaid_names(pages: Iterable[tuple[str, str]], texts: set[str]) -> list[str]:
    """Je Seite die kursiven Namen, die das Programm nicht sagt."""
    return [
        f"{key}: *{name}*"
        for key, text in pages
        for name in dict.fromkeys(_names(text))
        if name not in NOT_A_CONTROL and not _said(name, texts)
    ]


def test_every_italic_name_is_one_the_program_says_outside_the_manual() -> None:
    """Ein kursiver Name ist ein Text des Programms, nicht nur einer des Handbuchs."""
    pages = [(page.key, page.text()) for page in _written_pages()]
    texts = _program_texts()
    seen = {name for _key, text in pages for name in _names(text)}
    assert len(seen) >= 150, f"nur {len(seen)} Namen gefunden — das Muster greift nicht mehr"

    findings = _unsaid_names(pages, texts)
    assert not findings, f"{len(findings)} Namen sagt nur das Handbuch:\n" + "\n".join(findings)
    unused = sorted(set(NOT_A_CONTROL) - seen)
    assert not unused, f"Ausnahmen ohne Stelle im Handbuch — austragen: {unused}"


def test_a_falsified_name_is_found() -> None:
    """Gegenprobe: ein verschriebener Knopf fällt auf, ein richtiger nicht."""
    texts = _program_texts()
    findings = _unsaid_names(
        [("probe", "Erst *Bohrung setzen*, dann *Bohrung setzten* und *Übernehmen*.")], texts
    )
    assert findings == ["probe: *Bohrung setzten*"]


def _translated_program_texts(language: str, german: set[str]) -> set[str]:
    """Was das Programm in ``language`` für die deutschen Programmtexte sagt.

    Ein Schlüssel mit Kontext steht als ``Kontext\\x04Text`` im Katalog.
    """
    from app.i18n.catalog import read_catalog

    return {
        _plain(value)
        for key, value in read_catalog(language).items()
        if _plain(key.split("\x04")[-1]) in german
    }


def _translated_pages(language: str) -> list[tuple[str, str]]:
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        return [(page.key, page.text()) for page in _written_pages()]
    finally:
        set_language("de")


def _other_languages() -> list[str]:
    from app.i18n import SOURCE_LANGUAGE
    from app.i18n.catalog import available_languages

    return [language for language in available_languages() if language != SOURCE_LANGUAGE]


@pytest.mark.parametrize("language", _other_languages())
def test_an_italic_name_in_a_translation_is_the_translated_control(language: str) -> None:
    """Die Übersetzung nennt den Knopf so, wie ihn das übersetzte Programm zeigt.

    Spanisch und Portugiesisch nannten *Merkmal bearbeiten* im Handbuch
    „Editar detalle“ und „Editar elemento“, das Programm zeigt „Editar
    característica“ — der Kunde sucht einen Knopf, den es nicht gibt.
    """
    texts = _translated_program_texts(language, _program_texts())
    pages = _translated_pages(language)
    findings = _unsaid_names(pages, texts)
    assert not findings, f"{language}: {len(findings)} Namen zeigt das Programm so nicht:\n" + (
        "\n".join(findings)
    )
    assert _unsaid_names([("probe", "*Bohrung setzten*")], texts) == ["probe: *Bohrung setzten*"]


def _foreign_fields(pages: Iterable[tuple[str, str]], controls: set[str]) -> list[str]:
    """Felder, die zu keiner Operation gehören, die dieselbe Seite nennt.

    *Schriftgröße* auf der Seite von *Text aufbringen* ist ein Feld dieses
    Dialogs; steht es auf einer Seite, die nur *Bohrung setzen* nennt, sucht
    der Kunde es im falschen Dialog. Ein Name, den auch ein Knopf, Reiter
    oder eine Feldzeile der Oberfläche trägt (``controls``), darf überall
    stehen — dort ist er ein Ort und kein Dialogfeld.
    """
    from app.core.registry.registry import REGISTRY

    load_operations()
    titled: dict[str, list[set[str]]] = {}
    for spec in REGISTRY.all():
        fields = {_plain(str(entry.title)) for entry in getattr(spec.params, "__param_spec__", ())}
        titled.setdefault(_plain(str(spec.title)), []).append(fields)
    every_field = set().union(*(fields for found in titled.values() for fields in found))
    findings: list[str] = []
    for key, text in pages:
        names = list(dict.fromkeys(_names(text)))
        mine: set[str] = set()
        for name in names:
            for fields in titled.get(name, ()):
                mine |= fields
        findings.extend(
            f"{key}: Feld *{name}* gehört zu keiner Operation der Seite"
            for name in names
            if name in every_field
            and name not in titled
            and name not in mine
            and name not in controls
        )
    return findings


def test_a_field_the_manual_names_belongs_to_an_operation_on_the_same_page() -> None:
    """Ein Feldname steht bei der Operation, deren Dialog ihn zeigt."""
    pages = [(page.key, page.text()) for page in _written_pages()]
    ui = sorted((ROOT / "app" / "ui").rglob("*.py"))
    controls = _literals([*ui, ROOT / "app" / "core" / "errors.py"])
    findings = _foreign_fields(pages, controls)
    assert not findings, "\n".join(findings)
    assert _foreign_fields(
        [("probe", "*Bohrung setzen* mit *Position X* und *Schriftgröße*.")], controls
    ) == ["probe: Feld *Schriftgröße* gehört zu keiner Operation der Seite"]


def _bar_menus() -> set[str]:
    """Die Menüs der Leiste ohne gebautes Fenster: Quelltext und Registergruppen.

    Dieselbe Lesart wie ``test_manual._menus_of_the_bar``; welche Einträge
    darunter stehen, weiß erst das Fenster (unten).
    """
    from app.core.registry.registry import CATEGORIES, group_title, in_the_menu_bar
    from app.i18n import tr

    source = (ROOT / "app" / "ui" / "main_window.py").read_text(encoding="utf-8")
    fixed = [
        node.args[0].args[0].value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_menu"
        and node.args
        and isinstance(node.args[0], ast.Call)
        and isinstance(node.args[0].func, ast.Name)
        and node.args[0].func.id == "tr"
        and isinstance(node.args[0].args[0], ast.Constant)
        and isinstance(node.args[0].args[0].value, str)
    ]
    assert len(fixed) >= 4, f"nur {fixed} als Menü gefunden — das Muster greift nicht mehr"
    grouped = {
        _plain(group_title(category)) for category in CATEGORIES if in_the_menu_bar(category)
    }
    return {_plain(tr(title)) for title in fixed} | grouped


MENU_NAMED: Final = re.compile(r"\bMenü\s+\*([^*\n→]+)\*")


def _menus_not_in_the_bar(pages: Iterable[tuple[str, str]], bar: set[str]) -> list[str]:
    return [
        f"{key}: Menü *{name}*"
        for key, text in pages
        for name in MENU_NAMED.findall(text)
        if _plain(name) not in bar
    ]


def test_a_menu_the_manual_names_is_a_menu_of_the_bar() -> None:
    """„Im Menü *Erzeugen*“ schickt den Kunden in die Leiste — dort muss es stehen."""
    pages = [(page.key, page.text()) for page in _written_pages()]
    bar = _bar_menus()
    named = [name for _key, text in pages for name in MENU_NAMED.findall(text)]
    assert named, "kein „Menü *…*“ gefunden — das Muster greift nicht mehr"
    findings = _menus_not_in_the_bar(pages, bar)
    assert not findings, "\n".join(findings)
    assert _menus_not_in_the_bar([("probe", "im Menü *Werkzeuge*")], bar) == [
        "probe: Menü *Werkzeuge*"
    ]


# --- am gebauten Fenster (Release) ------------------------------------------------


@pytest.fixture(scope="module")
def built(qt_app: object) -> tuple[set[str], set[tuple[str, str]], set[str]]:
    """Alle Menüwege des Fensters, jede belegte Taste mit ihrem Titel, alle Reiter."""
    from PySide6.QtGui import QKeySequence
    from PySide6.QtWidgets import QMenu, QTabBar

    from app.ui import shortcuts_window
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    load_operations()
    window = MainWindow(Session(), UiSettings())
    ways: set[str] = set()

    def collect(menu: QMenu, before: str) -> None:
        for action in menu.actions():
            name = _plain(action.text())
            if action.isSeparator() or not name:
                continue
            way = f"{before} → {name}"
            ways.add(way)
            submenu = action.menu()
            if isinstance(submenu, QMenu):
                collect(submenu, way)

    for action in window.menuBar().actions():
        submenu = action.menu()
        if isinstance(submenu, QMenu):
            collect(submenu, _plain(action.text()))

    native = QKeySequence.SequenceFormat.NativeText
    portable = QKeySequence.SequenceFormat.PortableText
    keys = {
        (_plain(title), QKeySequence.fromString(key, native).toString(portable))
        for _group, title, key in shortcuts_window.entries(window.menuBar(), window)
    }
    tabs = {
        _plain(bar.tabText(index))
        for bar in window.findChildren(QTabBar)
        for index in range(bar.count())
    }
    window.close()
    window.deleteLater()
    return ways, keys, tabs


def _unknown_ways(pages: Iterable[tuple[str, str]], ways: set[str]) -> list[str]:
    found: list[str] = []
    for key, text in pages:
        for name in NAME.findall(text):
            if "→" not in name:
                continue
            way = " → ".join(_plain(part) for part in name.split("→"))
            if way.split(" → ")[0] not in NOT_A_MENU and way not in ways:
                found.append(f"{key}: *{name}*")
    return found


def test_every_italic_way_of_every_written_page_is_in_the_menu_bar(
    built: tuple[set[str], set[tuple[str, str]], set[str]],
) -> None:
    """Jeder kursive Weg *A → B* — auch in den Bildanleitungen — steht genau so in der Leiste."""
    ways, _keys, _tabs = built
    pages = [(page.key, page.text()) for page in _written_pages()]
    named = sum("→" in name for _key, text in pages for name in NAME.findall(text))
    assert named >= 15, f"nur {named} Wege gefunden — das Muster greift nicht mehr"
    findings = _unknown_ways(pages, ways)
    assert not findings, f"{len(findings)} Wege stehen nicht in der Leiste:\n" + "\n".join(findings)
    assert _unknown_ways([("probe", "*Datei → Bausteinkatalg …*")], ways) == [
        "probe: *Datei → Bausteinkatalg …*"
    ]


#: Eine Tastenkombination in jeder Sprache: Strg+K, Ctrl+K, Maj+…, F9.
_MODIFIER: Final = r"(?:Strg|Ctrl|Control|Umschalt|Shift|Maj|Mayús|Alt|Cmd)"
ANY_LANGUAGE_KEY: Final = re.compile(
    rf"(?<![\w+]){_MODIFIER}\+(?:{_MODIFIER}\+)*(?:F\d{{1,2}}|[A-Z0-9])(?![\w+])"
    r"|(?<![\w+])F\d{1,2}(?![\w+])"
)
_SAME_MODIFIER: Final = {"Strg": "Ctrl", "Control": "Ctrl", "Umschalt": "Shift", "Maj": "Shift"}


def _keys_of(text: str) -> list[str]:
    """Die Kombinationen eines Textes, gleich geschrieben in jeder Sprache."""
    found = []
    for key in ANY_LANGUAGE_KEY.findall(text):
        for said, same in _SAME_MODIFIER.items():
            key = key.replace(said, same)
        found.append(key.replace("Mayús", "Shift"))
    return sorted(found)


@pytest.mark.parametrize("language", _other_languages())
def test_a_translation_names_the_keys_the_source_names(language: str) -> None:
    """Strg+K im Deutschen ist Ctrl+K in der Übersetzung, nicht Ctrl+J.

    Welche Taste im Fenster belegt ist, prüft der Fenstertest an der Quelle;
    hier folgt jede Übersetzung ihr Seite für Seite.
    """
    source = {key: _keys_of(text) for key, text in _written_pages_text()}
    translated = _translated_pages(language)
    assert sum(len(keys) for keys in source.values()) >= 10, "zu wenige Tasten gefunden"
    findings = [
        f"{key}: {source[key]} → {_keys_of(text)}"
        for key, text in translated
        if _keys_of(text) != source[key]
    ]
    assert not findings, f"{language}:\n" + "\n".join(findings)
    assert _keys_of("Ctrl+J, Maj+F9") != _keys_of("Strg+K, Umschalt+F9")


def _written_pages_text() -> list[tuple[str, str]]:
    return [(page.key, page.text()) for page in _written_pages()]


#: Tasten, die das Handbuch nennt und die keine Belegung im Fenster sind → wo sie wirken.
KEYS_IN_PLACE: Final[dict[str, str]] = {}


def _unbound_keys(pages: Iterable[tuple[str, str]], bound: set[str]) -> list[str]:
    return [
        f"{key}: {said}"
        for key, text in pages
        for said in dict.fromkeys(KEY.findall(text))
        if _portable(said) not in bound and said.strip("`") not in KEYS_IN_PLACE
    ]


def _wrong_pairs(pages: Iterable[tuple[str, str]], keys: set[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    for page, text in pages:
        for name, said in NAME_AND_KEY.findall(text):
            title = _plain(name.split("→")[-1])
            if (title, _portable(said)) not in keys:
                bound = sorted(key for owner, key in keys if owner == title) or ["keine"]
                found.append(f"{page}: *{name}* mit {said}, belegt: {', '.join(bound)}")
    return found


def test_every_key_the_manual_names_is_bound(
    built: tuple[set[str], set[tuple[str, str]], set[str]],
) -> None:
    """Strg+Z, Entf, F9 … — jede genannte Taste tut im Fenster etwas."""
    _ways, keys, _tabs = built
    bound = {key for _title, key in keys}
    pages = [(page.key, page.text()) for page in _written_pages()]
    named = {said for _key, text in pages for said in KEY.findall(text)}
    assert len(named) >= 6, f"nur {sorted(named)} als Taste gefunden — das Muster greift nicht"
    findings = _unbound_keys(pages, bound)
    assert not findings, "Tasten ohne Belegung:\n" + "\n".join(findings)
    assert _unbound_keys([("probe", "Strg+Umschalt+F12 tut etwas.")], bound) == [
        "probe: Strg+Umschalt+F12"
    ]


def test_a_key_beside_a_name_belongs_to_that_name(
    built: tuple[set[str], set[tuple[str, str]], set[str]],
) -> None:
    """„*Datei → Bausteinkatalog …*, Strg+K“ — Strg+K öffnet genau den Bausteinkatalog."""
    _ways, keys, _tabs = built
    pages = [(page.key, page.text()) for page in _written_pages()]
    pairs = [pair for _key, text in pages for pair in NAME_AND_KEY.findall(text)]
    assert len(pairs) >= 2, f"nur {pairs} als Name mit Taste gefunden — das Muster greift nicht"
    findings = _wrong_pairs(pages, keys)
    assert not findings, "\n".join(findings)
    assert _wrong_pairs([("probe", "*Datei → Bausteinkatalog …*, Strg+J")], keys)


#: Ein Satz, der von Reitern spricht.
TAB_SENTENCE: Final = re.compile(r"[^.!?\n]*\bReiter\b[^.!?\n]*")


def _unknown_tabs(pages: Iterable[tuple[str, str]], tabs: set[str]) -> list[str]:
    return [
        f"{key}: Reiter *{name}*"
        for key, text in pages
        for sentence in TAB_SENTENCE.findall(text)
        for name in _names(sentence)
        if name not in tabs
    ]


def test_a_tab_the_manual_names_is_a_tab_of_the_window(
    built: tuple[set[str], set[tuple[str, str]], set[str]],
) -> None:
    """„Rechts daneben drei Reiter: *Auswahl*, *Prüfbericht* und *Chat*“ — so heißen sie."""
    _ways, _keys, tabs = built
    pages = [(page.key, page.text()) for page in _written_pages()]
    named = [n for _k, text in pages for s in TAB_SENTENCE.findall(text) for n in _names(s)]
    assert len(named) >= 3, f"nur {named} als Reiter gefunden — das Muster greift nicht mehr"
    findings = _unknown_tabs(pages, tabs)
    assert not findings, "\n".join(findings)
    assert _unknown_tabs([("probe", "Der Reiter *Merkmale* rechts.")], tabs) == [
        "probe: Reiter *Merkmale*"
    ]
