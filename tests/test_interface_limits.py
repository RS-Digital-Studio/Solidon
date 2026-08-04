"""Obergrenzen der Oberfläche (Konzept P15 §5, Bauplan §2).

Der Bauplan sagt: „Die Anwendung ist vielseitig — genau deshalb muss die
Oberfläche einfach bleiben. Vielseitigkeit gehört in die Tiefe, nicht an die
Oberfläche." Das ist ein Satz, und Sätze halten keine zwei Phasen.

Hier stehen die Zahlen dazu. Sie sind beim Anlegen alle eingehalten — dieser
Lauf ist also von Anfang an grün und schlägt erst an, wenn jemand sie reißt.
Genau das ist der Zweck: eine Grenze, die erst nach dem Überschreiten
eingezogen wird, ist keine Grenze mehr, sondern eine Aufräumaktion.

Wer eine dieser Zahlen erhöhen will, tut das mit Absicht und mit einer
Begründung im Commit. Das ist der Unterschied zu einer Oberfläche, die
wächst, weil niemand hinsah.
"""

from __future__ import annotations

from collections import Counter

import pytest

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY, palette_entries

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMenu

from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

#: Menüs in der Leiste. Vor P14 waren es siebzehn; die Menügruppen haben
#: daraus neun gemacht, und dabei bleibt es.
MAX_MENUS = 9

#: Umschalter in der Werkzeugzeile. Heute sieben. Die achte Funktion, die
#: eine Leiste will, verdrängt eine andere — oder sie ist keine wert.
MAX_TOOLS = 8

#: Felder auf der **Vorderseite** eines Operationsdialogs. Was darüber
#: hinausgeht, gehört hinter „Weitere Einstellungen" (§2.5, `placement`).
MAX_FRONT_PARAMS = 8

#: Einträge in einem Untermenü. Darüber liest niemand mehr, er sucht — und
#: dafür gibt es die Befehlspalette.
MAX_SUBMENU_ENTRIES = 12


@pytest.fixture(autouse=True)
def _the_whole_catalogue() -> None:
    """Das vollständige Register, unabhängig davon, was sonst noch läuft.

    Ohne das misst diese Datei allein das, was zufällig schon importiert war —
    und für einen Test, der Obergrenzen hütet, wäre das die schlechteste
    Eigenschaft von allen: er wäre still, wenn er allein läuft. Es ist
    derselbe Aufruf, den auch die Kommandozeile macht.
    """
    load_operations()


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    return MainWindow(Session(), UiSettings())


def test_the_menu_bar_stays_readable(window: MainWindow) -> None:
    """Neun Menüs, nicht siebzehn (P14, E5 dort)."""
    menus = [action.text() for action in window.menuBar().actions()]
    assert len(menus) <= MAX_MENUS, (
        f"{len(menus)} Menüs in der Leiste, erlaubt sind {MAX_MENUS}: {menus}. "
        "Eine neue Kategorie gehört in eine bestehende Gruppe (MENU_GROUPS), "
        "nicht in ein eigenes Menü."
    )


def test_the_tool_strip_stays_a_single_row(window: MainWindow) -> None:
    """Die Werkzeugzeile ist eine Zeile und bleibt eine."""
    tools = window.tools.tool_titles()
    assert len(tools) <= MAX_TOOLS, (
        f"{len(tools)} Werkzeuge in der Zeile, erlaubt sind {MAX_TOOLS}: "
        f"{sorted(tools)}. Welches soll dafür weichen?"
    )


def test_no_operation_floods_the_front_of_its_dialog() -> None:
    """Tiefe gehört hinter die Klappe, nicht auf die Vorderseite (§2.5)."""
    over = {
        spec.name: len([p for p in spec.params.spec() if p.placement == "front"])
        for spec in REGISTRY.all()
        if len([p for p in spec.params.spec() if p.placement == "front"]) > MAX_FRONT_PARAMS
    }
    assert not over, (
        f"Diese Operationen zeigen mehr als {MAX_FRONT_PARAMS} Felder auf der "
        f"Vorderseite: {over}. Setze die selteneren auf placement='advanced'."
    )


def _direct_entries(menu: QMenu) -> int:
    """Wie viele Zeilen dieses Menü selbst zeigt.

    Ein Untermenü zählt als **eine** Zeile, nicht als seine Einträge — genau
    das ist der Sinn einer Zwischenebene, und ein Test, der das anders zählt,
    würde die Lösung für das Problem halten.
    """
    return sum(1 for action in menu.actions() if not action.isSeparator())


def test_no_menu_becomes_a_list_to_search(window: MainWindow) -> None:
    """Ein Menü, das man absuchen muss, ist kein Menü mehr.

    Gezählt wird am gebauten Fenster, nicht an den Kategorien des Registers:
    die Oberfläche darf eine Zwischenebene einziehen (sie tut es bei den
    Bausteinen), und eine Zählung über das Register sähe davon nichts.
    """
    over: dict[str, int] = {}

    def walk(menu: QMenu, path: str) -> None:
        count = _direct_entries(menu)
        if count > MAX_SUBMENU_ENTRIES:
            over[path] = count
        for action in menu.actions():
            submenu = action.menu()
            if submenu is not None:
                walk(submenu, f"{path} > {action.text().replace('&', '')}")

    for action in window.menuBar().actions():
        menu = action.menu()
        if menu is not None:
            walk(menu, action.text().replace("&", ""))

    assert not over, (
        f"Diese Menüs zeigen mehr als {MAX_SUBMENU_ENTRIES} Zeilen: {over}. "
        "Eine Zwischenebene (wie die Bausteingruppen) oder eine Kategorie "
        "weniger — Bauplan §25 und MENU_GROUPS sind die Stellen dafür."
    )


def test_every_tool_says_what_it_expects(window: MainWindow) -> None:
    """Ein Werkzeug, dessen erster Handgriff geraten werden muss, ist eines zu
    viel (Konzept P15 §4, E2).

    Der Satz ist nicht die Beschriftung — die steht auf dem Knopf. Er sagt, was
    jetzt zu tun ist. Deshalb prüft dieser Test auch, dass er länger ist als
    der Titel: „Schnitt" als Hinweis zu „Schnitt" wäre die stille Art, die
    Regel zu erfüllen, ohne sie einzuhalten.
    """
    without = []
    too_short = []
    for key, tool in window.tools.tools().items():
        hint = str(tool.hint).strip()
        if not hint:
            without.append(key)
        elif len(hint) <= len(str(tool.title)) + 10:
            too_short.append((key, hint))

    assert not without, (
        f"Diese Werkzeuge sagen nicht, was sie erwarten: {without}. "
        "ToolStrip.add(..., hint=tr('…')) — ein Satz, kein Titel."
    )
    assert not too_short, f"Diese Hinweise wiederholen nur den Titel: {too_short}."


def test_a_tool_hint_appears_and_goes_with_the_tool(window: MainWindow) -> None:
    """Der Hinweis gehört dem Werkzeug, nicht dem Fenster."""
    window.tools.activate("section")
    assert window.tools.hint_text(), "geöffnet steht der Hinweis da"

    window.tools.close_tool()
    assert not window.tools.hint_text(), "geschlossen ist er weg"


def test_every_declared_icon_really_exists() -> None:
    """Ein Symbolname, den es nicht gibt, ist ein leerer Knopf.

    Die **Vollständigkeit** — keine Operation ohne Symbol — kommt mit den
    gezeichneten Symbolen in P15 Etappe 8. Bis dahin greift diese Hälfte der
    Regel: was deklariert ist, muss es geben. Eine Ausnahmeliste über
    einundsiebzig Operationen wäre keine Prüfung, sondern eine Abschrift.
    """
    from app.ui.icons import PATHS

    wrong = {
        spec.name: spec.icon for spec in REGISTRY.all() if spec.icon and spec.icon not in PATHS
    }
    assert not wrong, (
        f"Diese Operationen nennen ein Symbol, das es in app/ui/icons.py nicht gibt: {wrong}."
    )


def test_the_palette_puts_what_fits_the_selection_first() -> None:
    """Wer eine Bohrung angeklickt hat, sucht Senken — nicht das, was vorn im
    Register steht (Konzept P15 §5, E13).

    Und es bleibt eine Reihenfolge: die Zahl der Zeilen ändert sich nicht.
    Eine Palette, die aussortiert, wäre eine Betriebsart mit anderem Namen.
    """
    plain = palette_entries()
    sorted_for_hole = palette_entries(for_feature="hole")
    assert len(plain) == len(sorted_for_hole)
    assert {entry.name for entry in plain} == {entry.name for entry in sorted_for_hole}

    for_hole = {spec.name for spec in REGISTRY.all() if "hole" in spec.applies_to}
    assert for_hole, "keine Operation deklariert sich für Bohrungen — Test wertlos"
    leading = {entry.name for entry in sorted_for_hole[: len(for_hole)]}
    assert leading == for_hole, (
        f"Diese Operationen sollten bei ausgewählter Bohrung vorn stehen: "
        f"{sorted(for_hole)}, vorn stehen aber {sorted(leading)}."
    )


def _menu_entries(menu: QMenu) -> list[str]:
    """Alle Einträge eines Menüs, auch die in Untermenüs."""
    found: list[str] = []
    for action in menu.actions():
        submenu = action.menu()
        if submenu is not None:
            found.extend(_menu_entries(submenu))
        elif not action.isSeparator():
            found.append(action.text())
    return found


def test_every_operation_has_exactly_one_menu_entry(window: MainWindow) -> None:
    """Zwei Wege zur selben Handlung sind zwei Stellen, an denen einer fehlen
    kann — und für den Nutzer die Frage, ob sie dasselbe tun.

    Verglichen wird über den Titel, denn das ist, was ein Mensch sieht. Qt
    schreibt Kürzel als ``&`` in den Text; das kommt vorher heraus.
    """
    titles = [
        entry.replace("&", "")
        for menu in window.menuBar().actions()
        if menu.menu() is not None
        for entry in _menu_entries(menu.menu())
    ]
    counts = Counter(titles)
    operations = {str(spec.title) for spec in REGISTRY.all()}
    twice = {title: n for title, n in counts.items() if n > 1 and title in operations}
    assert not twice, (
        f"Diese Operationen stehen mehrfach in der Menüleiste: {twice}. "
        "Eine Operation, ein Eintrag — alles Weitere ist Kontextmenü, "
        "Palette oder Kürzel."
    )


# --- die Kürzelübersicht (Konzept P15 §7 Etappe 8, D6) --------------------------


def test_the_shortcut_list_is_generated_from_both_sources(window: MainWindow) -> None:
    """`?` zeigt, was es gibt — erzeugt, nicht gepflegt.

    Eine von Hand geschriebene Liste wäre am Tag nach dem nächsten Kürzel
    falsch, und niemand würde es merken. Diese liest das Register und die
    Befehlstabelle des Fensters; damit steht sie auch in beiden Sprachen, ohne
    dass jemand sie übersetzt.
    """
    from app.ui.shortcuts_window import entries

    found = entries(window.window_commands())
    assert found, "es gibt Kürzel, also steht etwas drin"

    keys = {shortcut for _group, _title, shortcut in found}
    assert "Ctrl+S" in keys, "die Fensterbefehle sind dabei"
    from_registry = {spec.shortcut for spec in REGISTRY.all() if spec.shortcut}
    assert from_registry <= keys, "und jede Operation, die eines führt"

    assert all(shortcut for _group, _title, shortcut in found), (
        "was kein Kürzel hat, gehört nicht in eine Kürzelübersicht — "
        "die Liste aller Befehle ist die Palette"
    )
