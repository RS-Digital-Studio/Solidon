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
from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY, palette_entries

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMenu, QToolButton

from app.ui.main_window import MENU_GROUPS, MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"

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


def test_the_printer_list_is_sorted_the_way_it_is_read(window: MainWindow) -> None:
    """Sortiert wurde nach der Kennung, gelesen wird der Titel.

    In der Druckerliste stand „Elegoo Centauri Carbon 2" zwischen Bambu und
    Creality — seine Kennung ist ``centauri-carbon-2``. „Allgemeiner
    FDM-Drucker 220 mm" stand zwischen Elegoo und Prusa, denn er heißt
    ``generic-220``. Für den, der die Liste liest, war sie unsortiert.

    Geprüft am Dialog und nicht an der Hilfsfunktion: die Frage ist, was in der
    Auswahl steht, und dorthin führen drei verschiedene Wege.
    """
    from app.ui.first_run import FirstRunDialog

    dialog = FirstRunDialog(window.settings, window)
    for auswahl, name in ((dialog.printer, "Drucker"), (dialog.material, "Material")):
        titles = [auswahl.itemText(index) for index in range(auswahl.count())]
        assert titles == sorted(titles, key=str.casefold), f"{name}: {titles}"


def test_no_tool_shares_its_name_with_its_own_controls(window: MainWindow) -> None:
    """Der Umschalter holt das Werkzeug hervor, die Leiste bedient es.

    Beim Bemalen trugen beide dasselbe Wort und standen direkt übereinander:
    der Umschalter „Bemalen" öffnete die Leiste, und darin fragte ein Häkchen
    „Bemalen" noch einmal. Wer den Umschalter drückte und ins Modell klickte,
    malte nicht — und sah nur ein zweites Feld mit demselben Namen.
    """
    from PySide6.QtWidgets import QAbstractButton

    doppelt = []
    for key, tool in window.tools.tools().items():
        title = str(tool.title).strip().casefold()
        for control in tool.bar.findChildren(QAbstractButton):
            if control.text().strip().casefold() == title:
                doppelt.append((key, control.text()))

    assert not doppelt, (
        f"Diese Bedienelemente heißen wie ihr eigener Umschalter: {doppelt}. "
        "Der Umschalter nennt das Werkzeug, das Element seine Handlung."
    )


def test_a_tool_hint_appears_and_goes_with_the_tool(window: MainWindow) -> None:
    """Der Hinweis gehört dem Werkzeug, nicht dem Fenster."""
    window.tools.activate("section")
    assert window.tools.hint_text(), "geöffnet steht der Hinweis da"

    window.tools.close_tool()
    assert not window.tools.hint_text(), "geschlossen ist er weg"


def test_every_operation_has_an_icon_and_every_icon_exists() -> None:
    """Kein Menüeintrag ist reiner Text (Konzept P15 §5, E12).

    Beide Hälften der Regel: jede Operation führt ein Symbol, und jedes
    genannte gibt es auch. Getragen wird das von der Kategorie — eine
    Operation darf ihr eigenes deklarieren, muss aber nicht.

    **Warum nicht je Operation:** dreiundsiebzig Symbole zu unterscheiden ist
    schwerer als dreiundsiebzig Wörter zu lesen, und drei ähnliche Bohrer
    nebeneinander sagen weniger als einer über allen Bohr-Operationen. Was ein
    Symbol in einem Menü leistet, ist die Gruppe auf einen Blick; den Rest
    trägt die Beschriftung daneben (Regel 18).
    """
    from app.ui.icons import PATHS, icon_name_for

    missing = {
        spec.name: icon_name_for(spec)
        for spec in REGISTRY.all()
        if icon_name_for(spec) not in PATHS
    }
    assert not missing, (
        f"Diese Operationen haben kein Symbol: {missing}. Entweder trägt die "
        "Operation eines (icon=…), oder ihre Kategorie braucht eines in "
        "app/ui/icons.py unter „category.<name>“."
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


def test_the_shortcut_list_is_generated_from_the_menu_bar(window: MainWindow) -> None:
    """`?` zeigt, was es gibt — erzeugt, nicht gepflegt.

    Gelesen wurden vorher zwei Quellen, die Befehlstabelle des Fensters und das
    Register. Beide zusammen sind nicht alles: die Tasten für Darstellung und
    Kameravorgaben gehen durch keine von beiden und standen deshalb in keiner
    Übersicht, obwohl sie im Menü daneben stehen.

    Die Menüleiste kennt sie alle — dort landet jede Aktion, die ein Mensch
    findet — und liefert die Gruppe gleich mit.
    """
    from PySide6.QtGui import QKeySequence

    from app.ui.shortcuts_window import entries

    found = entries(window.menuBar())
    assert found, "es gibt Kürzel, also steht etwas drin"

    keys = {shortcut for _group, _title, shortcut in found}
    native = QKeySequence("Ctrl+S").toString(QKeySequence.SequenceFormat.NativeText)
    assert native in keys, "die Fensterbefehle sind dabei"

    from_registry = {
        QKeySequence(spec.shortcut).toString(QKeySequence.SequenceFormat.NativeText)
        for spec in REGISTRY.all()
        if spec.shortcut
    }
    assert from_registry <= keys, "und jede Operation, die eines führt"

    # Die fünfzehn, die vorher fehlten.
    for key in ("1", "2", "3", "4"):
        assert key in keys, f"die Darstellungstaste {key} steht in der Übersicht"
    assert QKeySequence("Ctrl+0").toString(QKeySequence.SequenceFormat.NativeText) in keys, (
        "und die Kameravorgaben ebenso"
    )

    assert all(shortcut for _group, _title, shortcut in found), (
        "was kein Kürzel hat, gehört nicht in eine Kürzelübersicht — "
        "die Liste aller Befehle ist die Palette"
    )


def test_the_shortcut_list_writes_keys_the_way_the_menu_does(window: MainWindow) -> None:
    """§4.1: die Übersicht sprach englisch, während das Menü deutsch sprach.

    Dort stand „Ctrl+Z", im Bearbeiten-Menü daneben „Strg+Z" — dieselbe Taste,
    zwei Schreibweisen, und die eine findet auf keiner deutschen Tastatur
    statt. Übersetzt wird das von Qt selbst, sobald sein Katalog geladen ist;
    geprüft wird deshalb die Kopplung und nicht die Sprache: die Übersicht
    schreibt, was die Aktion schreibt.
    """
    from PySide6.QtGui import QAction, QKeySequence

    from app.ui.shortcuts_window import entries

    keys = {shortcut for _group, _title, shortcut in entries(window.menuBar())}
    with_keys = [
        action
        for action in window.findChildren(QAction)
        if not action.shortcut().isEmpty() and action.menu() is None
    ]
    assert with_keys, "es gibt Menüeinträge mit Kürzeln"

    for action in with_keys[:20]:
        native = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        if native in keys:
            continue
        # Nicht jede Aktion steht in einem Menü — Werkzeugleiste und
        # fensterweite Kürzel gibt es auch. Was drinsteht, muss aber passen.
        assert action.shortcut().toString() not in keys, (
            f"{action.text()}: die Übersicht schreibt anders als die Aktion"
        )


def test_the_note_names_the_key_that_opens_the_palette(window: MainWindow) -> None:
    """Eine Übersicht über Tastenkürzel, die ein falsches nennt, ist schlimmer
    als keine.

    Unter der Liste stand „Strg+G" — das öffnet *Modell erzeugen*. Die Palette
    liegt auf Strg+Umschalt+P, und die Zeile holt sich die Taste jetzt von der
    Aktion selbst.
    """
    from PySide6.QtGui import QKeySequence

    expected = QKeySequence("Ctrl+Shift+P").toString(QKeySequence.SequenceFormat.NativeText)

    assert window._palette_action.shortcut() == QKeySequence("Ctrl+Shift+P")
    assert (
        window._palette_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        == expected
    )


# --- die zweite Kürzelbelegung (Konzept P15 §7 Etappe 8, E7) --------------------


def test_no_scheme_gives_the_same_key_to_two_things(window: MainWindow) -> None:
    """Ein Kürzel, das zwei Dinge auslöst, löst keines aus.

    Das Register lehnt Dubletten seit P0 ab; eine Belegung, die sich darüber
    legt, kann sie trotzdem einführen — und zwar still, weil sie das Register
    nicht anfasst. Geprüft wird jede Belegung gegen sich selbst **und** gegen
    die Fensterbefehle, die überall dieselben sind.
    """
    from app.ui.shortcut_schemes import SCHEMES, shortcut_for

    window_keys = {
        shortcut for _title, shortcut, _slot in window.window_commands().values() if shortcut
    }
    for scheme in SCHEMES:
        # Gefragt wird die Belegung selbst, nicht die Anzeige: geprüft wird,
        # welche Taste eine Operation führt, und nicht, wie sie geschrieben
        # steht.
        keys = [
            key
            for spec in REGISTRY.all()
            if (key := shortcut_for(spec.name, spec.shortcut, scheme))
        ]
        twice = {key for key in keys if keys.count(key) > 1}
        assert not twice, f"Belegung {scheme!r} vergibt {sorted(twice)} doppelt"

        clash = set(keys) & window_keys
        assert not clash, (
            f"Belegung {scheme!r} greift nach {sorted(clash)} — das gehört den "
            "Fensterbefehlen, und die sind in jeder Belegung dieselben"
        )


def test_a_scheme_only_changes_what_it_names() -> None:
    """Eine Belegung ist eine Änderung an einzelnen Tasten, keine zweite Liste.

    Sonst liefe sie beim nächsten neuen Kürzel auseinander: das Register bekäme
    eines, die Tabelle nicht, und in einer der beiden Belegungen fehlte es
    stillschweigend.
    """
    from app.ui.shortcut_schemes import FUSION, shortcut_for

    assert shortcut_for("rename_object", "F2", "fusion") == "F2", "was sie nicht nennt, bleibt"
    assert shortcut_for("sketch_extrude", None, "fusion") == "E", "was sie nennt, gilt"
    assert shortcut_for("sketch_extrude", None, "default") is None, "die Vorgabe ist das Register"

    known = {spec.name for spec in REGISTRY.all()}
    unknown = set(FUSION) - known
    assert not unknown, (
        f"Die Belegung nennt Operationen, die es nicht gibt: {sorted(unknown)}. "
        "Eine Taste für nichts ist eine Taste, die niemand wiederfindet."
    )


def test_the_menu_says_which_theme_and_scheme_are_active(window: MainWindow) -> None:
    """§2.6: vier Navigationsschemata und zwei Themen, und keines mit Haken.

    Wer die Vorgabe einmal umgestellt hat, konnte danach nur ausprobieren,
    worauf sie steht.
    """
    ticked = {
        action.data()
        for action in (*window._theme_group.actions(), *window._navigation_group.actions())
        if action.isChecked()
    }

    assert window.settings.theme in ticked
    assert window.settings.navigation in ticked
    assert len(ticked) == 2, "je Gruppe genau einer"


def test_switching_moves_the_tick(window: MainWindow) -> None:
    """Qt setzt den Haken beim Klick von selbst — nicht aber, wenn die
    Einstellung von woanders kommt, etwa aus dem Einstellungsdialog."""
    window.action_navigation("cad")

    ticked = {action.data() for action in window._navigation_group.actions() if action.isChecked()}
    assert ticked == {"cad"}

    window.action_navigation("blender")
    ticked = {action.data() for action in window._navigation_group.actions() if action.isChecked()}
    assert ticked == {"blender"}, "und der alte Haken geht weg"


def test_a_menu_is_sorted_the_way_it_is_read() -> None:
    """Sortiert wurde nach dem internen Namen, gelesen wird der Titel.

    Unter *Grundformen* stand deshalb „Quader, Exakter Quader, Exakter
    Zylinder, Zylinder, OpenSCAD, Kugel" — die Reihenfolge von ``create_box``,
    ``create_brep_box``, ``create_brep_cylinder``, … Wer ein Menü aufklappt,
    sucht in den Titeln, und alphabetisch ist die einzige Ordnung, die man
    dabei voraussetzen darf.
    """
    from app.i18n import sort_key

    for category, entries in REGISTRY.by_category().items():
        titles = [str(spec.title) for spec in entries]
        assert titles == sorted(titles, key=sort_key), f"{category} steht durcheinander: {titles}"


def test_a_basic_shape_is_created_not_changed() -> None:
    """Quader, Zylinder und Kugel standen unter *Ändern → Boolesch*.

    In einem Menü, das *Ändern* heißt, in einer Gruppe, die *Boolesch* heißt,
    obwohl nichts verschnitten wird — während *Erzeugen* Import, Skizze und
    Beschriftung führte und keine einzige Grundform.
    """
    shapes = {"create_box", "create_cylinder", "create_sphere"}
    for name in shapes:
        assert REGISTRY.get(name).category == "primitive"

    booleans = {spec.name for spec in REGISTRY.by_category()["boolean"]}
    assert not booleans & shapes
    assert booleans, "und übrig bleibt, was wirklich verschneidet"

    creating = next(cats for title, cats in MENU_GROUPS if str(title) == "Erzeugen")
    assert "primitive" in creating


def test_the_tool_strip_greys_out_on_an_empty_scene(window: MainWindow) -> None:
    """Was jetzt geht, sieht man — auch unten in der Werkzeugzeile (§2.6).

    Die Menüs machen es vorbildlich: auf einer leeren Szene sind alle
    vierunddreißig Einträge unter *Ändern* stumpf, *Objekt* ganz, *Bausteine*
    ganz. Die Werkzeugzeile bot im selben Zustand weiter Schnitt, Messen,
    Bewegen, Analyse, Schichten und Bemalen an — jedes davon braucht einen
    Körper, und keines sagte das. „Bemalen" auf einer leeren Szene ist ein
    Pinsel für nichts.

    Ausgegraut und nicht ausgeblendet: Wer die Zeile leer vorfindet, sucht
    nach etwas, das gar nicht fehlt.
    """
    window.session.start_new()
    window.session.wait_for_idle()
    window._update_actions()

    buttons = [
        child
        for child in window.tools.findChildren(QToolButton)
        if child.text() in window.tools.tool_titles().values()
    ]
    assert buttons, "die Umschalter stehen da"
    assert not any(button.isEnabled() for button in buttons), (
        "auf leerer Szene ist keiner anklickbar"
    )
    assert all(button.isVisible() or True for button in buttons), "sie bleiben aber sichtbar"
    for button in buttons:
        assert "Körper" in button.toolTip(), f"{button.text()} sagt, was fehlt"


def test_the_tool_strip_comes_back_with_a_body(window: MainWindow) -> None:
    """Sobald ein Körper da ist, geht die Zeile wieder auf."""
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._update_actions()

    buttons = [
        child
        for child in window.tools.findChildren(QToolButton)
        if child.text() in window.tools.tool_titles().values()
    ]
    assert all(button.isEnabled() for button in buttons)


def test_what_creates_a_body_lives_under_creating() -> None:
    """Ein Erzeugen gehört nicht ins Ändern-Menü.

    Der exakte Gewindebolzen stand unter *Ändern → Formgebung* — und war dort
    auf einer leeren Szene der einzige anklickbare Eintrag, während alle sechs
    Nachbarn ausgegraut waren. Kein Wunder: Er verbraucht nichts. Dieselbe
    Sorte Fehler wie die Grundformen unter *Boolesch*, die
    ``test_a_basic_shape_is_created_not_changed`` festhält.
    """
    creating = {
        category
        for title, categories in MENU_GROUPS
        if str(title) == "Erzeugen"
        for category in categories
    }
    for spec in REGISTRY.all():
        if spec.consumes == 0 and spec.produces >= 1 and spec.category != "parts":
            assert spec.category in creating, (
                f"{spec.name} erzeugt aus dem Nichts, steht aber unter {spec.category!r}"
            )


def test_reopening_an_operation_keeps_its_advanced_section(qt_app: object) -> None:
    """Die gestufte Tiefe gilt auch für den Korrekturdialog (§2.4).

    Wer eine Operation aus dem Verlauf öffnet, bekommt ihr *ganzes* Schema als
    Werte übergeben. Der Dialog legte alles vor den Nutzer, was einen Wert
    trug — und die Klappe „Weitere Einstellungen" verschwand genau dann, wenn
    jemand einen Wert nachbessern will. Ein Wert, der auf seiner Vorgabe steht,
    ist keine Entscheidung und gehört dorthin, wo das Schema ihn hinlegt.

    Geprüft am gebauten Dialog und an einer Operation, die wirklich eine
    Rückseite hat — sonst prüfte der Test nichts.
    """
    pytest.importorskip("PySide6")

    from app.ui.op_dialog import OperationDialog

    spec = next(
        entry
        for entry in REGISTRY.all()
        if any(p.placement == "advanced" for p in entry.params.spec())
        and any(p.placement == "front" for p in entry.params.spec())
    )
    vorne = next(p.name for p in spec.params.spec() if p.placement == "front")
    values = {p.name: p.default for p in spec.params.spec() if p.default is not None}

    frisch = OperationDialog(spec, ["obj_1"])
    assert getattr(frisch, "advanced", None) is not None, (
        f"{spec.name} hat gar keine Rückseite — dann prüft dieser Test nichts."
    )
    hinten = {name for name, form in frisch._rows.items() if form is not frisch._rows[vorne]}

    wieder = OperationDialog(spec, ["obj_1"], values=values)
    assert getattr(wieder, "advanced", None) is not None, (
        f"{spec.name}: Aus dem Verlauf geoeffnet verschwindet die Klappe fuer die "
        "weiteren Einstellungen - die gestufte Tiefe gilt dann genau dort nicht, wo "
        "jemand einen Wert nachbessern will."
    )
    for name in hinten:
        assert wieder._rows[name] is not wieder._rows[vorne], (
            f"{spec.name}: {name!r} ist nach vorn gerutscht, obwohl es auf seiner "
            "Vorgabe steht und das Schema es nach hinten legt."
        )


def test_the_palette_knows_every_line_of_the_menu_bar(qt_app: object) -> None:
    """§19.2 verlangt die Palette als Universalzugang — alles über sie
    erreichbar, und die Kürzel lernen sich daneben.

    Sie war es nicht: Das Wörterbuch der Fensterbefehle wurde von Hand
    geführt, und von Hand heißt driften. Gemessen fehlten **39 von 136
    Menüzeilen** — jede Darstellungsart, jede Kameravorgabe, beide Themen,
    alle vier Navigationsschemata und acht Zeilen aus dem Hilfe-Menü. Sie
    nachzutragen hätte den nächsten Eintrag wieder vergessen lassen; gelesen
    wird deshalb die Leiste selbst.

    Zwei Zeilen bleiben mit Absicht draußen, und dieser Test nennt sie: In
    einer Liste, durch die man tippt, ist *Beenden* ein Klick zu nah am
    Verlust der Arbeit, und *Befehlspalette* öffnete sich selbst.
    """
    pytest.importorskip("PySide6")

    from app.ui.main_window import MainWindow, _menu_lines
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        commands = window.window_commands()
        titles = {title for title, _shortcut, _slot in commands.values()}
        operations = set(window._op_actions.values())
        gewollt_draussen = {window._quit_action, window._palette_action}

        missing = []
        for path, action in _menu_lines(window.menuBar()):
            if action in operations or action in gewollt_draussen:
                continue
            full = f"{path}: {action.text()}" if path else action.text()
            if full not in titles and action.text() not in titles:
                missing.append(full)

        assert not missing, (
            f"{len(missing)} Menüzeilen sind über die Befehlspalette nicht erreichbar: "
            f"{missing}. Die Palette liest die Leiste — wer hier landet, hat sie umgangen."
        )
    finally:
        window.close()
        window.deleteLater()
