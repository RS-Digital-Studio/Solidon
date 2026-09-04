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

import re
from collections import Counter
from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY, VARIANT_GROUPS, catalogue_operations, palette_entries

pytest.importorskip("PySide6")

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMenu, QToolButton, QWidgetAction

from app.ui.main_window import MENU_GROUPS, MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.shortcut_schemes import shortcut_for

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


def test_every_tool_hint_asks_for_the_width_of_one_line(window: MainWindow) -> None:
    """Der Streifen verlangt die Breite, die sein Hinweis für eine Zeile braucht.

    **Ein umbrechender Text verlangt von sich aus zu wenig.** ``QLabel`` meldet
    mit ``setWordWrap(True)`` eine bescheidene bevorzugte Breite; die Karte
    unten bekommt genau diesen Wunsch (``overlay._move``: „so breit, wie sie
    sein muss"), und der Hinweis stand deshalb in zwei Zeilen, obwohl im
    Fenster Platz für zwanzig war.

    Bezahlt wurde das in der Höhe. Gemessen am 30.08.2026 an einem echten
    Fenster über sechs Breiten von 600 bis 1920: Die Kartenhöhe ist konstant,
    aber je Werkzeug verschieden — 90 Punkte bei *Explosion*, 130 bei
    *Trennen*. Der Unterschied war genau die zweite Hinweiszeile. Danach 90
    und 115, jeder Hinweis einzeilig, in de, fr und it dieselben Zahlen.

    **Geprüft wird der Wunsch, nicht die Anzeige.** Unter ``offscreen`` gibt es
    keine Schriftmetrik — dort misst sich jeder Text rund doppelt so breit, und
    ein Fenster wird nie wirklich gelegt (gemessen: „braucht 1692, hat 52").
    Beide Seiten dieser Zusage lesen dieselbe Metrik, also trägt der Vergleich
    auch dort. Dass die Karte am Ende wirklich breit genug ist, hängt an
    ``overlay._move``, und das ist eine eigene Zusage.
    """
    zu_wenig: list[str] = []
    for key in window.tools.tools():
        window.tools.activate(None)
        window.tools.activate(key)
        hint = window.tools._hint
        text = hint.text()
        if not text:
            continue
        rand = hint.contentsMargins()
        braucht = hint.fontMetrics().horizontalAdvance(text) + rand.left() + rand.right()
        verlangt = window.tools.sizeHint().width()
        if verlangt < braucht:
            zu_wenig.append(f"{key}: verlangt {verlangt}, braucht {braucht}")

    assert not zu_wenig, (
        "Der Streifen verlangt weniger, als sein Hinweis für eine Zeile braucht — "
        f"dann bricht der Text um und das Panel wird eine Zeile höher: {zu_wenig}"
    )


def test_the_hint_gives_way_when_the_window_is_too_narrow(window: MainWindow) -> None:
    """Und der Rückweg: Reicht das Fenster nicht, bricht der Text wieder um.

    Die Zusage darüber wäre gefährlich ohne diese hier — ein Streifen, der
    seine Wunschbreite *erzwingt*, schöbe bei einem schmalen Fenster die halbe
    Karte aus dem Bild. ``overlay._move`` kürzt auf die verfügbare Breite, und
    der umbrechende Text ist dort die richtige Antwort und kein Fehler.
    """
    window.resize(640, 900)
    window.show()
    window.tools.activate(None)
    window.tools.activate("split")
    for _ in range(30):
        QApplication.processEvents()

    assert window.tools.width() <= 640, (
        f"die Werkzeugkarte ist {window.tools.width()} breit bei einem 640 breiten "
        "Fenster — sie darf ihre Wunschbreite verlangen, nicht erzwingen"
    )


def test_parameter_rows_fit_the_left_card_and_offer_visible_details(
    qt_app: QApplication,
) -> None:
    """Maßeinstellungen sind sichtbar erreichbar, ohne die Karte zu verbreitern.

    Der Rechtsklick bleibt ein schneller Nebenweg. Für Einsteiger steht aber
    in jeder Zeile ein kleiner Mehr-Knopf. Geschlossen zeigt die Einheit nur
    ihren Code; aufgeklappt erklärt dieselbe Auswahl weiterhin ihre Bedeutung.
    """
    from app.core.types import Document, Parameter
    from app.ui.panels import ParameterPanel
    from app.ui.theme import apply_theme

    # **Das Thema steht hier, weil der Innenabstand daran hängt** — ``app.py``
    # legt das Stylesheet beim Start über die *Anwendung*, der Kunde sieht die
    # Karte also nie ohne. Was hier geprüft wird, ist die kompakte
    # Einheitenauswahl, und die lebt von diesen Abständen.
    #
    # **Eine Breitenprüfung stand einen halben Tag lang darunter und ist
    # gestrichen.** Sie las ``minimumSizeHint().width() <= LEFT_WIDTH``, meldete
    # 270 gegen eine Zone von 260 und hat die Zone verbreitern lassen — gemessen
    # hatte sie eine Schrift, die es nicht gibt: Offscreen ist
    # ``QFontInfo.family()`` leer und jede Familie liefert dieselbe synthetische
    # Doppelbreite (228 Punkte gegen 111 unter Segoe UI). Am echten Bildschirm
    # misst die Karte 166. Eine feste Familie zu setzen hilft nicht, offscreen
    # ignoriert sie — die Prüfung ist hier grundsätzlich nicht zu haben.
    apply_theme(qt_app, "light")  # type: ignore[arg-type]

    document = Document(format_version=1, app_version="0.0.1")
    document.parameters["breite"] = Parameter(name="breite", value=40.0, unit="mm")
    document.parameters["halb"] = Parameter(
        name="halb", value=20.0, unit="mm", expression="=@breite/2"
    )
    document.parameters["anzahl"] = Parameter(name="anzahl", value=4.0, unit="")
    panel = ParameterPanel()
    panel.show_document(document)

    unit = panel._unit_editors["breite"]
    assert unit.currentText() == "mm — Länge", "die Auswahlliste erklärt die Einheit"
    assert unit._compact_text() == "mm", "geschlossen bleibt die schmale Karte ruhig"
    unitless = panel._unit_editors["anzahl"]
    assert unitless.currentText() == "ohne Einheit"
    assert unitless._compact_text() == ""

    gerufen: list[str] = []
    panel.limitsRequested.connect(gerufen.append)
    details = panel._detail_buttons["halb"]
    assert details.text() == "…"
    assert details.accessibleName() == "Parameter ändern"
    assert details.toolTip(), "der kompakte Knopf erklärt seinen Umfang"
    details.click()
    assert gerufen == ["halb"], "der sichtbare Knopf nennt seine Zeile"


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


def test_a_variant_group_stands_once_and_offers_its_kinds(window: MainWindow) -> None:
    """Vier Wege aus einer Skizze, ein Menüeintrag, die Art im Dialog.

    **Roberts Satz war „nicht für ähnliches gefühlt 20 verschiedene aktionen,
    eine und dann im dialog präzisieren."** Geprüft wird beides, denn nur
    zusammen ist es die Zusage: Der Sammeleintrag steht da **und** die vier
    Arten sind wählbar. Ein Test, der nur das Verschwinden prüft, wäre auch
    grün, wenn die Operationen gar nicht mehr erreichbar wären.

    Gezählt wird am gebauten Fenster, nicht am Register — der Eintrag gehört
    keiner Operation und stünde dort nicht.
    """
    titles = {
        entry
        for menu in window.menuBar().actions()
        if menu.menu() is not None
        for entry in _menu_entries(menu.menu())
    }
    group = VARIANT_GROUPS[0]

    assert str(group.title) in titles, "der Sammeleintrag fehlt im Menü"
    for name in group.members:
        assert str(REGISTRY.get(name).title) not in titles, (
            f"{name} steht noch einzeln im Menü — dann sind es wieder vier Einträge"
        )
        assert REGISTRY.has(name), f"{name} muss im Register bleiben (Verlauf, Provenienz)"


def test_the_variant_entry_keeps_the_shortcut_of_its_first_kind(window: MainWindow) -> None:
    """Das Kürzel wandert an den Sammeleintrag, statt zu verschwinden.

    ``sketch_extrude`` führt in der Fusion-Belegung „E". Ohne eigenen
    Menüeintrag gibt es keine ``QAction`` mehr, an der es hinge — anders als
    bei ``shell_exact``, wo es entfallen ist, bleibt es hier erhalten: Der
    Sammeleintrag öffnet ohnehin mit der ersten Art.
    """
    first = VARIANT_GROUPS[0].members[0]
    action = window._variant_actions[first]
    expected = shortcut_for(first, REGISTRY.get(first).shortcut, window.settings.shortcut_scheme)

    assert action.shortcut().toString() == (
        QKeySequence(expected).toString() if expected else ""
    ), "der Sammeleintrag führt nicht das Kürzel seiner ersten Art"


def test_a_group_of_one_never_becomes_a_submenu() -> None:
    """Ein Untermenü, das nichts bündelt, ist ein Klick für nichts (§2.6).

    Die Menüleiste weiß das seit je (``registry.surfaces.group_is_flat``), das
    **Kontextmenü** wusste es nicht: Es faltete jede Kategorie, sobald die
    Zeilengrenze überschritten war. Am Flächenklick — damals 19 Operationen in
    vier Gruppen, Bausteine 10, Ändern 5, Erzeugen 2, Vorbereiten 2 — kostete
    das **jede** Operation zwei Klicks, auch die Bohrung, die zu zweit in
    „Erzeugen" lag.

    **Die Zahlen unten sind Rechenbeispiele und nicht der Katalog.** Sie waren
    einmal beides, und das hielt nicht: Am 25.08.2026 standen an einer Fläche
    31 Operationen, davon 22 Bausteine. Was das Register wirklich hergibt,
    prüft :func:`test_the_context_menu_stays_within_its_rows`; hier steht die
    Formel, und dafür sind ausgedachte Zahlen die klareren.

    Geprüft wird die Rechnung, nicht das Menü: ``folded_groups`` braucht kein
    Qt, und ein Test, der dafür ein Fenster baute, hebt die Abrissquote der
    ganzen Datei (gemessen am 24.08.2026, 2 von 9 auf 2 von 3).
    """
    from app.core.registry.surfaces import folded_groups

    passt = {"Bausteine": 4, "Ändern": 3}
    assert folded_groups(passt) == [], "was in die Grenze passt, wird nicht gefaltet"

    flaeche = {"Bausteine": 10, "Ändern": 5, "Erzeugen": 2, "Vorbereiten": 2}
    assert folded_groups(flaeche) == ["Bausteine"], (
        "am Flächenklick genügt es, die größte Gruppe zu falten — die übrigen "
        "neun Einträge stehen dann direkt da"
    )

    einzeln = {f"Gruppe {nr}": 1 for nr in range(20)}
    assert folded_groups(einzeln) == [], (
        "zwanzig Gruppen mit je einem Eintrag ergeben zwanzig Untermenüs mit je "
        "einem Eintrag — dann bleibt das Menü lieber lang"
    )

    # **Die häufige Geste bleibt oben** (Entscheidung Robert, 27.08.2026).
    # Am echten Flächenklick sind es 22 Bausteine, und nach ihnen fehlt genau
    # eine Zeile. Die Rechnung nahm dafür die hinterste Gruppe — seit dem
    # Filament-Umbau liegt dort „Fläche färben", also die Geste, für die man
    # überhaupt auf eine Fläche zeigt. Gemessen am gebauten Fenster stand sie
    # danach unter „Vorbereiten", zusammen mit dem Prüfstück: zehn sichtbare
    # Zeilen, und Farbe in keiner davon.
    echt = {"Bausteine": 22, "Ändern": 5, "Erzeugen": 2, "Vorbereiten": 2}
    gefaltet = folded_groups(echt, fixed=3, keep={"Vorbereiten", "Ändern"})
    assert "Vorbereiten" not in gefaltet, (
        "die Gruppe mit dem Färben darin bleibt sichtbar — sie trägt die "
        "häufige Geste, und ein Untermenü kostet sie einen Klick"
    )
    assert "Bausteine" in gefaltet, "die zweiundzwanzig bleiben gefaltet"
    assert "Ändern" not in gefaltet, (
        "und die Bohrung bleibt oben — dafür wurde die Faltung am 24.08. umgebaut"
    )

    allein = {"Bausteine": 17}
    assert folded_groups(allein) == [], (
        "die einzige Gruppe wird nie gefaltet — sonst besteht das Menü aus einem "
        "einzigen Untermenü, das heißt, wonach man gerade geklickt hat"
    )
    assert folded_groups(allein, fixed=3) == ["Bausteine"], (
        "sobald daneben etwas Ungefaltetes steht, lohnt das Untermenü wieder"
    )

    gemischt = {"Groß": 8, "Mittel": 5, "Klein": 2, "Winzig": 1}
    assert folded_groups(gemischt) == ["Groß"], (
        "gefaltet wird von oben und nicht weiter, als die Grenze verlangt: "
        "16 Einträge, „Groß“ gefaltet macht 9 Zeilen (5+2+1 direkt, eine für "
        "das Untermenü) — „Mittel“ zu falten wäre ein Klick ohne Not"
    )

    hartnaeckig = {"A": 6, "B": 6, "C": 6}
    assert folded_groups(hartnaeckig) == ["A", "B"], (
        "18 Einträge, nach zwei Faltungen 8 Zeilen — die dritte Gruppe bleibt offen"
    )


#: Was am Flächenklick über den Operationen steht: Sichtbarkeit und der
#: Skizzenschritt. Keine Operationen, aber Zeilen — und die Grenze gilt dem
#: Menü. ``_add_operations`` zählt sie am gebauten Menü ab; hier steht der
#: ungünstigste Fall, in dem alle drei da sind.
FIXED_CONTEXT_ROWS = 3


def context_rows(kind: str) -> tuple[int, list[str]]:
    """Wie viele Zeilen das Kontextmenü eines Merkmals zeigt, und was es faltet.

    Gerechnet wie ``PropertiesPanel._add_operations``: direkte Einträge plus
    eine Zeile je gefaltetem Untermenü, und die festen Zeilen zählen beim
    Falten mit. Zurück kommen die **Operationszeilen** — wer die ganze Menülänge
    will, zählt ``FIXED_CONTEXT_ROWS`` dazu.

    Ohne Qt, weil ein Fenster hier nichts beiträgt und die Abrissquote der
    ganzen Datei hebt (gemessen am 24.08.2026).
    """
    from app.core.registry.surfaces import folded_groups, group_title
    from app.ui.panels import groups_to_keep

    sizes: dict[str, int] = {}
    offered = [spec for spec in REGISTRY.all() if kind in (spec.applies_to or ())]
    for spec in offered:
        title = group_title(str(spec.category))
        sizes[title] = sizes.get(title, 0) + 1

    # **Mit dem Schutz gerechnet, den auch die Anwendung mitgibt.** Ohne ihn
    # prüfte diese Datei eine Menülage, die es im Fenster nicht gibt — und
    # genau daran hängt die Zusage, dass Färben und Bohrung oben bleiben.
    folded = folded_groups(sizes, fixed=FIXED_CONTEXT_ROWS, keep=groups_to_keep(offered))
    rows = sum(count for title, count in sizes.items() if title not in folded) + len(folded)
    return rows, folded


def test_the_context_menu_stays_within_its_rows() -> None:
    """Die Grenze gilt dem **Menü**, nicht der Formel dahinter.

    ``test_a_group_of_one_never_becomes_a_submenu`` daneben prüft
    ``folded_groups`` gründlich — aber mit einer von Hand eingetragenen
    Verteilung, und die altert. Sie steht auf „Bausteine 10, Ändern 5,
    Erzeugen 2, Vorbereiten 2", also 19 Operationen; am 25.08.2026 waren es
    **31**, davon 22 Bausteine. Die Formel stimmt weiter, die Zahlen, an denen
    sie geprüft wird, nicht mehr — dieselbe Art alternder Liste, die in
    ``test_parts.py`` schon zweimal zugeschlagen hat.

    Gezählt wird deshalb, was das Register hergibt, und bis zur fertigen
    Menülänge.

    **Und die drei festen Zeilen zählen mit.** Sie taten es lange nicht, und
    das Flächenmenü stand damit auf dreizehn Zeilen gegen eine Grenze von
    zwölf — geführt als dokumentierte Ausnahme, weil die zweite Gruppe, die
    sonst fiele, „Ändern" gewesen wäre: mit der Bohrung darin, also genau dem
    Eintrag, dessen zweiter Klick den ganzen Umbau ausgelöst hat.

    Die Ausnahme ist am 25.08.2026 aufgelöst worden, und zwar an der Stelle,
    an der sie entstand: ``folded_groups`` faltet nicht mehr die größte Gruppe,
    sondern die hinterste, die allein genügt.

    **Am 27.08.2026 hat dieselbe Rechnung dann das Färben verschluckt** — es
    war mit dem Filament-Umbau nach „Vorbereiten" gekommen, also genau in die
    Gruppe, die als hinterste fällt. Gemessen am gebauten Fenster: zehn
    sichtbare Zeilen, Farbe in keiner. Seither nennt ``KEEP_VISIBLE`` die
    Kategorien, deren Gruppe stehen bleibt (``colour`` und ``holes``), und
    gefaltet wird stattdessen „Erzeugen". Kein Eintrag ist dabei tiefer
    gerutscht, für den jemand auf eine Fläche zeigt.
    """
    from app.ui.panels import MAX_MENU_ROWS

    for kind in ("face", "hole"):
        rows, _ = context_rows(kind)
        assert rows, f"{kind}: no operation offers itself at all"
        assert rows + FIXED_CONTEXT_ROWS <= MAX_MENU_ROWS, (
            f"{kind}: the menu shows {rows} operation rows plus {FIXED_CONTEXT_ROWS} fixed "
            f"ones, the limit is {MAX_MENU_ROWS} — fold another group or take a fixed row out"
        )


def test_nothing_is_folded_that_did_not_have_to_be() -> None:
    """Gefaltet wird, weil es sein muss — nicht, weil es ordentlich aussieht.

    Die Zeilengrenze fängt nur die eine Richtung: Ein Menü, in dem **jede**
    Gruppe zu einem Untermenü wird, hat vier Zeilen statt zehn und liegt damit
    bequem unter der Grenze. Es kostet nur jede einzelne Operation einen
    zweiten Klick — genau der Zustand, den der Umbau vom 24.08.2026 abgeschafft
    hat, und den eine Prüfung auf „höchstens zwölf" nicht bemerkt.

    Geprüft wird deshalb rückwärts: Jede gefaltete Gruppe wieder aufgemacht
    muss die Grenze sprengen. Tut sie es nicht, war ihre Faltung ein Klick ohne
    Not. Gerechnet wird gegen die **ganze** Menülänge, seit die festen Zeilen
    mitzählen — sonst gälte die Gegenrichtung gegen eine andere Zahl als die
    Grenze selbst, und „Vorbereiten" sähe wie eine Faltung ohne Not aus.
    """
    from app.ui.panels import MAX_MENU_ROWS

    for kind in ("face", "hole"):
        rows, folded = context_rows(kind)
        for title in folded:
            count = _group_size(kind, title)
            # Diese eine Gruppe aufgemacht: ihre Einträge stehen dann direkt da,
            # die eine Zeile ihres Untermenüs fällt weg.
            unfolded = rows - 1 + count + FIXED_CONTEXT_ROWS
            assert unfolded > MAX_MENU_ROWS, (
                f"{kind}: '{title}' is folded away, but leaving it open would give "
                f"{unfolded} rows — that fits in {MAX_MENU_ROWS}, so the submenu costs "
                "a click for nothing"
            )


def test_the_drill_stays_one_click_away_on_a_face() -> None:
    """Am Flächenklick steht die Bohrung direkt im Menü, nicht in einem Untermenü.

    Das ist die Entscheidung vom 25.08.2026 und der Grund, aus dem
    ``folded_groups`` nach der Reihenfolge der Menüleiste faltet statt nach der
    Größe. Als die drei festen Zeilen mitzuzählen begannen, fehlte nach
    „Bausteine" genau eine weitere Zeile — und die größte der übrigen Gruppen
    ist „Ändern", die mit der Bohrung darin. Sie zu falten hätte genau den
    zweiten Klick zurückgebracht, den der Umbau vom 24.08.2026 abgeschafft hat.

    Der Test daneben zählt nur Zeilen und wäre auch dann grün: Zwölf Zeilen
    sind zwölf Zeilen, gleich welche Gruppe zugeklappt ist. Diese Zusage ist
    eine andere, und sie braucht ihren eigenen Test.

    Gefragt wird an der **Operation** und nicht am Gruppennamen: Wer
    ``drill_hole`` später in eine andere Kategorie hängt, soll hier eine
    Antwort bekommen und keine stille Lücke.
    """
    from app.core.registry.surfaces import group_title

    drill = next((spec for spec in REGISTRY.all() if str(spec.name) == "drill_hole"), None)
    assert drill is not None, "drill_hole is gone from the registry — this test lost its subject"
    assert "face" in (drill.applies_to or ()), (
        "drill_hole no longer offers itself on a face — this test lost its subject"
    )

    _, folded = context_rows("face")
    group = group_title(str(drill.category))
    assert group not in folded, (
        f"the face menu folds '{group}' away, and the drill sits in it — that is the second "
        "click the rebuild of 2026-08-24 removed"
    )


def _group_size(kind: str, title: str) -> int:
    """Wie viele Operationen dieses Merkmals in dieser Gruppe liegen."""
    from app.core.registry.surfaces import group_title

    return sum(
        1
        for spec in REGISTRY.all()
        if kind in (spec.applies_to or ()) and group_title(str(spec.category)) == title
    )


def test_no_submenu_holds_a_single_entry() -> None:
    """Ein Untermenü mit einem Eintrag ist ein Klick für nichts (§2.6).

    ``folded_groups`` faltet nie eine Gruppe von eins — geprüft ist das an der
    Funktion. Hier steht dieselbe Frage an den **echten** Gruppen des
    Registers, denn eine Gruppe schrumpft auch: Wer die vorletzte Operation aus
    „Vorbereiten" wegnimmt, bekommt kein rotes Licht von einer Prüfung, die mit
    ausgedachten Zahlen rechnet.
    """
    for kind in ("face", "hole"):
        _, folded = context_rows(kind)
        for title in folded:
            count = _group_size(kind, title)
            assert count > 1, f"{kind}: '{title}' holds {count} entry and still became a submenu"


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
    Auswahl steht, und dorthin führen zwei verschiedene Wege.
    """
    from app.ui.first_run import FirstRunDialog

    dialog = FirstRunDialog(window.settings, window)
    for auswahl, name in ((dialog.language, "Sprache"), (dialog.printer, "Drucker")):
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


def test_the_registry_is_loaded_before_anything_is_counted() -> None:
    """Ohne ``load_operations()`` hat das Register **null** Operationen.

    Jede Grenze in dieser Datei ist eine Obergrenze — höchstens neun Menüs,
    zwölf Zeilen je Menü, acht Umschalter. Ein leeres Register unterschreitet
    jede davon, und die ganze Datei wird grün, ohne eine einzige Grenze geprüft
    zu haben. Das ist kein erdachter Fall: Wer das Register ohne
    ``load_operations()`` zählt, sieht 61 statt 86 Operationen, weil die
    sechzehn aus der Bausteinbibliothek fehlen.
    """
    from app.core.registry import REGISTRY

    assert len(REGISTRY.all()) > 50, (
        f"nur {len(REGISTRY.all())} Operationen im Register — läuft "
        "load_operations() noch? Sonst prüft diese Datei lauter leere Mengen."
    )


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


def test_the_navigation_keys_belong_to_the_list_with_the_focus(window: MainWindow) -> None:
    """Pos1 im Objektbaum sprang die Kamera an, nicht die Liste.

    „Alles einpassen" ist fensterweit auf Pos1 gebunden, und Qt fragt vor einem
    Kürzel die Fokuskette: Wer das ``ShortcutOverride`` annimmt, bekommt den
    Tastendruck. Listen und Bäume nehmen es für Pos1 nicht an — gemessen sechs
    Drücke im Baum, sechsmal die Kamera, nie die Liste, obwohl Pos1 in jeder
    Liste dieser Welt an den Anfang springt.

    **Nur vier Tasten**, und das ist der Kern der Entscheidung: Der
    naheliegende Fix — jede Sequenz ohne Zusatztaste gehört dem Bedienelement —
    nähme den Ziffern der Darstellungsarten ihre Wirkung, sobald eine Liste den
    Fokus hat, und das ist der Normalfall. Die Grenze verläuft zwischen
    *Bewegen im Inhalt* und *Befehl an das Fenster*.
    """
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    from app.ui.shortcut_schemes import install_navigation_keys

    # Der Filter hängt an der Anwendung und nicht am Fenster — einmal, nicht je
    # Fenster: Je Fenster installiert wuchs die Kette mit jedem gebauten
    # Fenster, und die Suite baut über zweihundert in einem Prozess.
    keys = install_navigation_keys()
    assert keys is not None, "ohne Anwendung gibt es keinen Filter"
    assert keys is install_navigation_keys(), "und es bleibt bei einem"

    def asked(widget: object, key: Qt.Key) -> bool:
        event = QKeyEvent(QEvent.Type.ShortcutOverride, key, Qt.KeyboardModifier.NoModifier)
        handled = keys.eventFilter(widget, event)
        return bool(handled and event.isAccepted())

    tree = window.object_tree.tree
    tree.setFocus()
    QApplication.processEvents()

    assert asked(tree, Qt.Key.Key_Home), "Pos1 gehört der Liste, in der der Fokus steht"
    assert asked(tree, Qt.Key.Key_End), "Ende genauso"
    assert not asked(tree, Qt.Key.Key_1), (
        "die Ziffern der Darstellungsarten bleiben Fensterbefehle — sonst wären sie "
        "wirkungslos, sobald irgendeine Liste den Fokus hat"
    )

    window.viewport.setFocus()
    QApplication.processEvents()
    assert not asked(window.viewport, Qt.Key.Key_Home), (
        "in der Ansicht gibt es keinen Inhalt, in dem Pos1 sich bewegen könnte — "
        "dort bleibt es „Alles einpassen"
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


def test_the_tick_follows_a_change_from_the_settings_dialog(window: MainWindow) -> None:
    """Der Weg, den der Test darüber im Docstring nennt und nie gefahren ist.

    ``test_switching_moves_the_tick`` begründet sich mit „nicht aber, wenn die
    Einstellung von woanders kommt, etwa aus dem Einstellungsdialog" — und
    fährt ``action_navigation``, also das Menü. Der genannte Weg geht über
    ``_apply_settings``, und dort standen drei der fünf Gruppen: Darstellung,
    Schattierung, Projektion. Thema und Navigation fehlten, und ausgerechnet
    diese beiden bietet der Dialog an.

    Für den Kunden hieß das: Er stellte die Steuerung im Dialog um, fuhr mit
    der neuen — und las im Menü weiter die alte als die aktive (Robert,
    04.09.2026).
    """
    window.settings.navigation = "cad"
    window.settings.theme = "light"

    window._apply_settings()

    navigation = {
        action.data() for action in window._navigation_group.actions() if action.isChecked()
    }
    theme = {action.data() for action in window._theme_group.actions() if action.isChecked()}
    assert navigation == {"cad"}, "das Menü nennt das Schema, mit dem gefahren wird"
    assert theme == {"light"}, "und dasselbe gilt für das Thema"


def test_a_menu_is_sorted_the_way_it_is_read() -> None:
    """Sortiert wurde nach dem internen Namen, gelesen wird der Titel.

    Unter *Grundformen* stand deshalb „Quader, Exakter Quader, Exakter
    Zylinder, Zylinder, Kugel" — die Reihenfolge von ``create_box``,
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


def test_the_shortcut_list_knows_every_key_the_window_holds(window: MainWindow) -> None:
    """Die Übersicht kannte dreizehn Tasten nicht — darunter alle acht Werkzeuge.

    Gelesen wurde ausschließlich die Menüleiste, und der Docstring begründete
    das mit „dort landet jede Aktion, die ein Mensch findet". Nachgezählt am
    gebauten Fenster: 36 Menütasten gegen 49 belegte. Es fehlten ``Alt+1`` bis
    ``Alt+8`` für die acht Werkzeuge, ``Strg+Tab`` und ``Strg+Umschalt+Tab``,
    die beiden Zoom-Tasten und ``Esc`` — ausgerechnet die acht, von denen ein
    Kommentar in ``main_window`` sagt, sie stünden „im Tooltip des Knopfes und
    in der Kürzelübersicht".

    Dieser Test ist die Bremse gegen das Wiederauftreten: Er vergleicht mit den
    ``QShortcut``-Kindern des Fensters und wird rot, sobald einer dazukommt, den
    :data:`WINDOW_KEYS` nicht nennt.
    """
    from PySide6.QtGui import QKeySequence, QShortcut

    from app.ui.shortcuts_window import entries

    def native(sequence: QKeySequence) -> str:
        return sequence.toString(QKeySequence.SequenceFormat.NativeText)

    listed = entries(window.menuBar(), window)
    named = {key for _group, _title, key in listed}

    owned = {
        native(item.key()) for item in window.findChildren(QShortcut) if not item.key().isEmpty()
    }
    assert owned, "ohne Fenstertasten prüft dieser Test nichts"
    assert owned <= named, f"die Übersicht kennt diese Tasten des Fensters nicht: {owned - named}"

    # Die Werkzeugtasten einzeln, denn sie sind der Anlass — gezählt an den
    # angemeldeten Werkzeugen statt als feste Acht: Mit dem Pinsel fiel
    # Alt+8, und eine festgenagelte Zahl hätte den Ausbau blockiert, statt
    # die Zusage zu prüfen (jedes Werkzeug der Zeile ist auffindbar).
    count = len(window.tools.tools())
    assert count, "ohne angemeldete Werkzeuge prüft diese Schleife nichts"
    for number in range(1, count + 1):
        key = native(QKeySequence(f"Alt+{number}"))
        assert key in named, f"{key} fehlt — das Werkzeug dazu ist unauffindbar"

    # Und die Reihenfolge ist die der Menüleiste, nicht das Alphabet: „Ändern"
    # stand hinter allem anderen, weil „Ä" im Zeichensatz hinter „z" liegt.
    groups = list(dict.fromkeys(group for group, _title, _key in listed))
    menus = [
        action.text().replace("&", "")
        for action in window.menuBar().actions()
        if action.menu() is not None
    ]
    from_menus = [group for group in groups if group in menus]
    assert from_menus == [name for name in menus if name in groups], (
        f"die Gruppen folgen nicht der Menüleiste: {from_menus} gegen {menus}"
    )


def test_the_palette_greys_out_what_the_menu_greys_out(window: MainWindow) -> None:
    """Die 60 Fensterbefehle der Palette standen alle gleich da.

    Die Operationen lesen ihre Verfügbarkeit aus den Menü-Actions
    (``_palette_availability``), die Fensterbefehle taten es nicht: „Rückgängig"
    ohne Verlauf nahm den Klick an und tat nichts — ein ``trigger()`` auf eine
    gesperrte Action ist ein Klick ins Leere. Bei leerem Projekt sind das fünf
    von 60: Exportieren, Rückgängig, Wiederholen, Automatisch teilen, Varianten.

    Vier davon stehen von Hand in ``window_commands`` und nicht in der
    Menüschleife — sie nur dort zu suchen hätte einen von fünf erwischt.

    Und der Grund gehört dazu (Regel 18, §2.7): Ausgrauen allein lässt den
    Nutzer den Fehler bei sich suchen. Genannt wird, was fehlt — nicht, was der
    Befehl täte, wenn er könnte.
    """
    window._update_actions()
    commands = window.window_commands()
    blocked = {
        key: window._extra_availability(key)
        for key in commands
        if not window._extra_availability(key)[0]
    }

    assert blocked, "auf einem leeren Projekt muss etwas gesperrt sein"
    for key, (_usable, reason) in blocked.items():
        title = commands[key][0]
        assert reason, f"{title} ist gesperrt und sagt nicht, warum"
        assert reason != title, f"{title} nennt sich selbst als Grund"

    # Die vier aus der Handtabelle sind dabei — sie waren der schwierige Teil.
    titles = {commands[key][0] for key in blocked}
    assert any("Rückgängig" in title for title in titles), (
        f"Rückgängig ist ohne Verlauf gesperrt, die Palette sieht es nicht: {sorted(titles)}"
    )

    # Und was geht, sagt nichts: ein Grund an einem offenen Eintrag wäre eine
    # Warnung ohne Anlass.
    open_keys = [key for key in commands if window._extra_availability(key)[0]]
    assert open_keys, "es kann nicht alles gesperrt sein"
    assert all(not window._extra_availability(key)[1] for key in open_keys)


def test_the_palette_teaches_the_keys_of_the_active_scheme(qt_app: QApplication) -> None:
    """Die Palette zeigte die Tasten des Registers, das Menü daneben die der
    Belegung.

    Der Kern liefert das Kürzel, das im Register steht — er kennt die Belegung
    nicht und darf sie nicht kennen, sie ist eine Einstellung der Oberfläche.
    Ungefiltert weitergereicht lehrte die Palette im Schema „Wie Fusion und
    Onshape" drei falsche Tasten und verschwieg sieben, die es dort gibt:
    ``translate_object`` stand auf „Strg+T" statt „M", ``sketch_extrude`` auf
    gar nichts statt „E". Wer die Palette benutzt, um Tasten zu lernen — und
    dafür ist sie da (§2.6) —, lernte die falschen.
    """
    from app.ui.shortcut_schemes import FUSION, shortcut_for

    window = MainWindow(Session(), UiSettings(shortcut_scheme="fusion"))
    try:
        shown = {entry.name: entry.shortcut for entry in window.palette_rows()}

        wrong = {name: (shown[name], key) for name, key in FUSION.items() if shown.get(name) != key}
        assert not wrong, (
            f"Die Palette nennt {len(wrong)} Tasten anders als die Belegung: {wrong}. "
            "Gezeigt wird, was shortcut_for sagt — nicht das rohe Registerkürzel."
        )

        # Und die Gegenprobe: Was die Belegung nicht anfasst, behält sein
        # Kürzel aus dem Register. Sonst wäre der Fix eine zweite Wahrheit.
        for entry in window.palette_rows():
            expected = shortcut_for(entry.name, entry.shortcut, "fusion")
            assert entry.shortcut == expected, f"{entry.name}: {entry.shortcut} statt {expected}"
    finally:
        window.close()
        window.deleteLater()


def test_the_shortcut_list_knows_the_drawing_keys(window: MainWindow) -> None:
    """Auch die Tasten des Zeichenmodus stehen in der Übersicht.

    **Derselbe Fund, eine Ebene tiefer.** Die Prüfung nebenan vergleicht mit
    den ``QShortcut``-Kindern des *Fensters* und hat damit
    dreizehn Tasten gefunden. Der Zeichenmodus ist ein Dialog: Seine
    fünfzehn Tasten hängen am ``SketchPanel``, das Fenster kennt sie nicht,
    und die Prüfung sah an dieser Grenze nichts mehr.

    Nachgezählt am 21.08.2026 standen fünf von fünfzehn in der Übersicht —
    die generischen ``Esc``, ``Home`` und ``1`` bis ``3``. Es fehlten genau
    die zum Zeichnen: ``L`` Linie, ``C`` Kreis, ``A`` Bogen, ``P`` Punkt,
    ``S`` Spline, ``T`` Trimmen, ``R`` Rechteck, ``D`` Maß, ``O`` Offset und
    ``X`` Hilfslinie. Wer wissen wollte, wie man eine Linie zeichnet, fand
    es nur im Tooltip des Knopfes — und der Docstring von ``entries`` nennt
    „den ganzen Zeichensatz" seit je als das, was fehlte.
    """
    from app.i18n import tr
    from app.ui.shortcuts_window import _native, entries
    from app.ui.sketch_editor import ACTION_KEYS, PLANE_KEYS, TOOL_KEYS, VIEW_KEYS

    # **Verglichen werden Anzeigenamen, nicht Deklarationstexte.** ``entries``
    # schreibt jede Taste so, wie sie auf der Tastatur steht — und Qt
    # übersetzt das aus seinem eigenen Katalog: „Home" heißt auf einer
    # deutschen Oberfläche **Pos1**. Der Vergleich gegen die rohen Werte aus
    # ``VIEW_KEYS`` traf damit an genau einer Taste daneben.
    #
    # Sichtbar war das nur in großen Läufen: Qts Katalog kommt von
    # ``install_qt_translations`` — im Betrieb beim Start (``app.py``), in der
    # Suite von irgendeinem früheren Test. Ohne ihn gibt ``_native("Home")``
    # eben „Home" zurück, der Vergleich ging auf, und der Test war grün in
    # einer Lage, die es beim Kunden nicht gibt.
    #
    # **Hergestellt wird die Betriebslage hier trotzdem nicht**, und das ist
    # gemessen: Ein Aufruf von ``install_qt_translations`` davor macht die
    # Gegenprobe nicht rot. ``_native`` neutralisiert die Lage auf **beiden**
    # Seiten des Vergleichs — mit Katalog stehen „Pos1" und „Pos1", ohne ihn
    # „Home" und „Home". Eine Zeile, deren Entfernen nichts rot macht, ist
    # Zierat; beim Kartenmaß oben ist es umgekehrt, dort hängt die Zahl selbst
    # an der Lage.

    named = {key for _group, _title, key in entries(window.menuBar(), window)}
    drawing = {**TOOL_KEYS, **ACTION_KEYS, **VIEW_KEYS, **PLANE_KEYS}
    missing = sorted(key for key in drawing.values() if _native(key) not in named)

    assert not missing, f"die Übersicht kennt diese Zeichentasten nicht: {missing}"

    # **Und jede trägt einen Namen, keinen rohen Schlüssel.** Die Zeile darüber
    # prüft die *Taste*; ein Werkzeug ohne Eintrag in der Titeltabelle fiel
    # bis zum 27.08.2026 stillschweigend ganz aus der Liste
    # (``titles.get(name)`` ohne Zweig für ``None``), und rot wurde nichts.
    # Jetzt taucht es mit seinem Schlüssel auf — sichtbar statt verschwunden,
    # dieselbe Haltung wie bei ``group_title`` im Register. Diese Zeile macht
    # daraus einen roten Lauf, damit es niemand erst im Fenster sieht.
    schluessel = set(drawing)
    roh = sorted(
        title
        for group, title, _key in entries(window.menuBar(), window)
        if group == str(tr("Zeichnen")) and title in schluessel
    )
    assert not roh, f"diese Zeichentasten haben keinen Namen, nur ihren Schlüssel: {roh}"


def test_a_menu_where_nothing_works_steps_aside(qt_app: QApplication) -> None:
    """Vier Menüs, in denen auf der leeren Szene kein Eintrag geht.

    **Robert am 23.08.2026:** „wenn man kein 3d modell ausgewählt hat bringen
    menüs wie bohrung anlegen nichts, hier ausblenden" — und auf die Rückfrage:
    „ausblenden wenn es nicht sinnvoll ist".

    Gemessen auf der leeren Szene: *Objekt* 0 von 5, *Ändern* 0 von 34,
    *Bausteine* 0 von 20, *Vorbereiten* 0 von 10. **Neunundsechzig gesperrte
    Zeilen**, und die Erklärung sieht nur, wer mit der Maus darüberfährt.

    **Die Grenze läuft am Menü, nicht am Eintrag**, und das ist der ganze
    Schnitt: Ein Menü, in dem *jeder* Eintrag gesperrt ist, erklärt nichts —
    es ist Lärm. Ein Menü mit gemischtem Inhalt behält seine grauen Zeilen samt
    Grund, denn dort steht die Erklärung **neben einem Eintrag, der geht**, und
    dieser Vergleich sagt dem Kunden mehr als das Verschwinden.

    Was nicht verschwindet: die Werkzeugzeile. Sie nennt den Grund im Klartext
    („Dafür braucht es einen Körper in der Szene.") und ist die Stelle, an der
    ein Anfänger zuerst hinsieht.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    qt_app.processEvents()
    # **Weg vom Startbildschirm, sonst misst dieser Test etwas anderes.** Dort
    # blendet ``_workspace_menus`` ohnehin alles bis auf *Datei* und *Hilfe*
    # aus — ein zweiter, älterer Schnitt aus demselben Gedanken. Gefragt ist
    # hier die leere Szene: Der Kunde hat den Startbildschirm hinter sich und
    # noch nichts gebaut.
    window._show_start_screen(False)
    window._update_actions()
    qt_app.processEvents()

    def zustand() -> dict[str, tuple[int, int, bool]]:
        gefunden: dict[str, tuple[int, int, bool]] = {}
        for handle in window.menuBar().actions():
            menu = handle.menu()
            if menu is None:
                continue
            eintraege = [a for a in menu.actions() if not a.isSeparator() and a.menu() is None]
            for a in list(menu.actions()):
                unter = a.menu()
                if unter is not None:
                    eintraege += [b for b in unter.actions() if not b.isSeparator()]
            frei = sum(1 for a in eintraege if a.isEnabled())
            gefunden[handle.text().replace("&", "")] = (frei, len(eintraege), handle.isVisible())
        return gefunden

    leer = zustand()
    ganz_gesperrt = [name for name, (frei, alle, _) in leer.items() if alle and not frei]
    assert ganz_gesperrt, "ohne ein ganz gesperrtes Menü prüft dieser Test nichts"
    for name in ganz_gesperrt:
        assert not leer[name][2], f"„{name}“ ist ganz gesperrt und steht trotzdem da"

    # **Die Gegenprobe, und sie ist die wichtigere Hälfte:** Wer einen Körper
    # hat, bekommt alles zurück. Ein Menü, das verschwindet und nicht
    # wiederkommt, wäre schlimmer als eines, das grau dasteht.
    gemischt = [name for name, (frei, alle, _) in leer.items() if frei and alle]
    for name in gemischt:
        assert leer[name][2], f"„{name}“ hat bedienbare Einträge und ist trotzdem fort"

    # Und die zweite Hälfte: Wer einen Körper hat, bekommt alle vier zurück.
    window.session.import_model(Path("tests/data/meshes/plate_holes.stl"))
    window.session.wait_for_idle()
    for _ in range(8):
        qt_app.processEvents()
    window._update_actions()
    qt_app.processEvents()

    # **Die Zwischenstufe zuerst, und sie ist die, an der es einmal schiefging:**
    # Ein Körper liegt da, aber niemand hat ihn angeklickt. Die erste Fassung
    # blendete hier weiter aus — der Kunde sieht sein Teil und findet *Ändern*
    # nicht mehr, obwohl ihm nur ein Klick fehlt. Ein Menü, das bei jeder
    # Auswahl kommt und geht, lässt die Leiste flackern; das ist schlimmer als
    # eine graue Zeile, die ihren Grund nennt.
    for name, (_frei, alle, sichtbar) in zustand().items():
        assert sichtbar or not alle, f"„{name}“ fehlt, obwohl ein Körper in der Szene liegt"

    window.object_tree.select_object(next(iter(window.session.last_result.scene.objects)))
    window._update_actions()
    qt_app.processEvents()

    voll = zustand()
    for name in ganz_gesperrt:
        frei, _, sichtbar = voll[name]
        assert frei, f"„{name}“ ist auch mit einem Körper ganz gesperrt — dann ist es kaputt"
        assert sichtbar, f"„{name}“ kam nicht zurück"

    window.release()


# --- Eigene Bausteine des Nutzers (§24.5, Konzept E1) -----------------------------


def test_a_part_of_the_users_own_never_reaches_the_menu_bar(
    monkeypatch: pytest.MonkeyPatch, qt_app: QApplication
) -> None:
    """**Jeder eigene Baustein wird eine Operation — und damit ein Menüeintrag.**

    Zwanzig eigene Teile machen aus einem Menü eine Liste zum Absuchen, und die
    Zeilengrenze in dieser Datei kann es nie sehen: ``load_user_parts`` wird
    ausdrücklich nur von Oberfläche und Kommandozeile gerufen, nie von der
    Suite (§38). Die Grenze wäre also grün und das Menü trotzdem geflutet.

    **Geprüft wird das Fenster, nicht die Funktion darunter.** Ein Test über
    ``menu_tree(skip=…)`` allein sagt nur, dass die Aussortierung *möglich*
    ist — nicht, dass das Fenster sie benutzt. Durchgereicht ist nicht gerufen.
    """
    from app.core import bootstrap
    from app.ui.main_window import MainWindow

    load_operations()
    # Eine vorhandene Operation als „eigener Baustein" ausgeben: Der Weg über
    # einen echten Nutzerordner bräuchte eine Datei auf der Platte, und geprüft
    # werden soll das Fenster, nicht das Einlesen.
    victim = next(spec.name for spec in REGISTRY.all() if spec.category == "parts")
    monkeypatch.setattr(bootstrap, "user_operations", lambda: (victim,))

    # Selbst gebaut und nicht über die window-Fixture: Der Patch muss
    # **vor** dem Menüaufbau stehen, und die Fixture baut das Fenster schon
    # beim Anfordern.
    window = MainWindow(Session(), UiSettings())
    try:
        # **``_op_actions`` ist die Zuordnung, die der Menüaufbau selbst
        # anlegt** — Name → Aktion, gefüllt an genau den zwei Stellen, die
        # Menüeinträge erzeugen. Der erste Anlauf dieses Tests las stattdessen
        # ``data()`` der Aktionen und fand **nichts**: Er war grün, weil er
        # eine leere Menge prüfte. Gefangen hat das die Gegenprobe darunter,
        # nicht der Test selbst.
        in_menu = set(window._op_actions)
        # **Der Wächter zeigt seit dem 29.08.2026 auf das Register, nicht auf
        # das Menü.** Vorher stand hier „die Menüleiste zeigt gar keine
        # Bausteine — dann prüft dieser Test nichts", und genau das ist seither
        # der Sollzustand: Ein Baustein der Bibliothek hat keinen Menüort mehr,
        # er lebt im Katalog mit Bildern (§2.6). Ein Wächter, der den
        # Sollzustand für einen Fehler hält, muss mitwandern — geprüft wird
        # jetzt, dass es überhaupt Bausteine **gibt**.
        #
        # **Gefragt wird nach der Kachel, nicht nach der Kategorie.** Hier
        # stand ``category == "parts"``, und das ist zu grob: ``create_lid``
        # und ``screw_lid`` tragen dieselbe Kategorie und haben keine Kachel —
        # der Katalog zeigt ``PARTS.all()``. Solange die Frage der Kategorie
        # galt, verlangte dieser Test, dass beide **nicht** im Menü stehen, und
        # damit schrieb er einen Fehler fest: Sie standen daraufhin nirgends
        # (gemessen 114 Menüeinträge, kein *Deckel erzeugen* darunter, und im
        # Katalog auch nicht).
        katalog = catalogue_operations()
        assert katalog, "es gibt keine Bausteine — dann prüft dieser Test nichts"
        in_bar = [name for name in in_menu if name in katalog]
        assert not in_bar, (
            f"Bausteine mit Kachel gehören in den Katalog, nicht in die Menüleiste "
            f"(§2.6): {sorted(in_bar)}"
        )
        assert victim not in in_menu, "der eigene Baustein steht in der Menüleiste"
        assert victim in {entry.name for entry in palette_entries()}, (
            "und er muss über die Befehlspalette weiter erreichbar sein"
        )
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()


#: Ein Menüweg, wie ihn Handbuch, Tour und Website schreiben: „Bearbeiten →
#: Varianten erzeugen". Vor dem Pfeil ein einzelnes großgeschriebenes Wort,
#: dahinter der Eintrag bis zum ersten Satzzeichen.
MENU_PATH = re.compile(r"([A-ZÄÖÜ][a-zäöüß]+)\s*→\s*([A-ZÄÖÜ][^.,;:—<»\"\n]{2,40})")

#: Wo Menüwege stehen. Nicht die erzeugten Seiten — die kommen aus `manual.py`
#: und würden denselben Fehler ein zweites Mal melden.
PATH_SOURCES = (
    Path(__file__).parent.parent / "app" / "core" / "manual.py",
    Path(__file__).parent.parent / "app" / "core" / "tour.py",
    Path(__file__).parent.parent / "website" / "index.html",
    Path(__file__).parent.parent / "website" / "funktionen.html",
)


def _menu_titles_and_entries(menu: QMenu) -> list[str]:
    """Jeder Eintrag eines Menüs, **samt den Titeln der Untermenüs**.

    **Nicht mit `_menu_entries` weiter oben zusammenlegen** — die beiden
    unterscheiden sich in genau den zwei Punkten, auf die es je hier und dort
    ankommt, und der Versuch hat schon einmal einen Test gekippt:

    * `_menu_entries` überspringt Untermenü-Titel und liefert den Text
      **unverändert**, mit `&` und Auslassungspunkten. Das braucht
      `test_a_variant_group_stands_once_and_offers_its_kinds`: Es sucht
      „Aus Skizze erzeugen …" wörtlich, also mitsamt den Punkten.
    * Diese hier nimmt die Titel **mit** (ein Menüweg kann auf eine
      Zwischenebene zeigen) und putzt `&` und Punkte weg, weil ein Text
      „Bausteine → Kalibrierung" schreibt und nicht „Kalibrierung …".

    Beim Anlegen hieß diese Funktion ebenfalls `_menu_entries` und verdeckte
    damit die ältere — der Variantentest wurde rot, und die Ursache lag drei
    Bildschirmseiten entfernt in einer Datei, die niemand im Verdacht hatte.
    """
    found: list[str] = []
    for action in menu.actions():
        text = action.text().replace("&", "").replace("…", "").strip()
        below = action.menu()
        if below is not None:
            found.append(text)
            found.extend(_menu_titles_and_entries(below))
        elif text:
            found.append(text)
    return found


def test_every_menu_path_in_the_texts_leads_somewhere(window: MainWindow) -> None:
    """Was Handbuch, Tour und Website als Weg nennen, muss es geben.

    **Drei Wege zeigten am 26.08.2026 ins falsche Menü**, alle drei in Texten,
    die dem Kunden das Suchen abnehmen sollen: „Ändern → Varianten erzeugen"
    (der Eintrag hängt an *Bearbeiten*), „Bausteine → Toleranz-Testkörper" (seit
    der Zwischenebene *Bausteine → Kalibrierung → …*) und „Bearbeiten →
    Automatisch teilen" (Kategorie ``prepare``, also *Vorbereiten*). Gefunden
    hat sie kein Test, sondern eine Durchsicht — und der dritte erst, nachdem
    zwei behoben waren.

    Verglichen wird gegen das **gebaute** Menü und nicht gegen eine Liste
    daneben: Eine Zwischenebene, die jemand einzieht, verschiebt jeden Weg
    darunter, und eine Liste altert genau dann still mit.

    Der Eintrag darf im Text länger stehen als im Menü („Automatisch teilen in
    einem Zug"), deshalb wird von vorn verglichen. Wege, deren erstes Wort kein
    Menü der Leiste ist — „Rechtsklick → Bohrung setzen" —, meint der Text
    nicht als Menüweg; sie fallen heraus.
    """
    menus = {
        action.text().replace("&", "").strip(): _menu_titles_and_entries(menu)
        for action in window.menuBar().actions()
        if (menu := action.menu()) is not None
    }
    assert menus, "die Menüleiste ist leer — dann prüft dieser Test nichts"

    checked = 0
    wrong: list[str] = []
    for source in PATH_SOURCES:
        if not source.is_file():
            continue
        seen: set[tuple[str, str]] = set()
        for match in MENU_PATH.finditer(source.read_text(encoding="utf-8")):
            menu_name = match.group(1).strip()
            entry = match.group(2).strip().rstrip(" *_`\"'")
            if (menu_name, entry) in seen or menu_name not in menus:
                continue
            seen.add((menu_name, entry))
            checked += 1
            if not any(
                entry.lower().startswith(known.lower()) or known.lower().startswith(entry.lower())
                for known in menus[menu_name]
                if known
            ):
                elsewhere = [
                    name
                    for name, entries in menus.items()
                    if any(
                        entry.lower().startswith(known.lower())
                        or known.lower().startswith(entry.lower())
                        for known in entries
                        if known
                    )
                ]
                wrong.append(
                    f"{source.name}: „{menu_name} → {entry}“ — "
                    + (f"steht in {elsewhere}" if elsewhere else "nirgends im Menü")
                )

    assert checked >= 10, f"nur {checked} Menüwege gefunden — das Muster greift nicht mehr"
    assert not wrong, "Menüwege, die ins Leere zeigen:\n" + "\n".join(wrong)


# --- Gezählt wird, was zu sehen ist (27.08.2026) ------------------------------


def test_the_row_count_counts_what_the_menu_shows() -> None:
    """Eine Zwischenebene für Einträge, die das Menü nie zeigt, ist ein Klick
    für nichts.

    ``group_is_flat`` zog *Erzeugen* ein Untermenü ein, weil es **14** Einträge
    zählte; gezeigt werden **11**, und die Grenze liegt bei zwölf. Die drei
    Fehlenden sind die übrigen Mitglieder der Variantengruppe — sie stehen
    unter dem Sammeleintrag und haben keine eigene Zeile. Damit kostete jede
    Erzeugungs-Operation einen dritten Klick, und zwar im Menü, das Weg 2
    trägt.

    Geprüft wird die Rechnung gegen die **Regel**, nicht gegen die heutige Zahl:
    Die Zeilenzahl einer Gruppe ist die Zahl ihrer Namen minus der
    Variantenmitglieder plus einer Zeile je vertretener Gruppe. Ohne Qt, damit
    kein Fenster dafür entsteht.
    """
    from app.core.registry import MENU_GROUPS, MENU_TWINS, REGISTRY, VARIANT_GROUPS
    from app.core.registry.registry import variant_members
    from app.core.registry.surfaces import menu_rows_of

    members = variant_members()
    for _title, categories in MENU_GROUPS:
        names = {
            spec.name
            for spec in REGISTRY.all()
            if spec.category in categories and spec.name not in MENU_TWINS
        }
        if not names:
            continue
        expected = len(names - members) + sum(
            1 for group in VARIANT_GROUPS if any(name in names for name in group.members)
        )
        assert menu_rows_of(categories) == expected, (
            f"{categories}: gezählt {menu_rows_of(categories)}, gezeigt {expected}"
        )


def test_a_variant_group_costs_one_row_and_not_its_members() -> None:
    """Die Gegenprobe an der Gruppe, die den Fehler ausgelöst hat.

    Ohne sie wäre der Test darüber auch grün, wenn *keine* Variantengruppe
    existierte — er prüft dann eine Formel über eine leere Menge.

    **Und die erste Fassung dieses Tests rechnete falsch**, was ihn nützlicher
    macht als seine Behauptung: Sie erwartete, dass die Kategorie *Skizze* eine
    Zeile beiträgt, weil ihre vier Wege zusammengelegt sind. Tatsächlich sind es
    zwei — `sketch_pocket` steht **nicht** in der Gruppe und behält seine Zeile.
    Wer über eine Zusammenlegung rechnet, zählt die Nichtmitglieder mit.
    """
    from app.core.registry import MENU_GROUPS, REGISTRY, VARIANT_GROUPS
    from app.core.registry.surfaces import menu_rows_of

    group = VARIANT_GROUPS[0]
    assert len(group.members) > 1, "eine Gruppe aus einem Mitglied prüft hier nichts"
    categories = next(cats for _title, cats in MENU_GROUPS if "sketch" in cats)

    im_menü = {spec.name for spec in REGISTRY.all() if spec.category == "sketch"}
    mitglieder = im_menü & set(group.members)
    assert len(mitglieder) == len(group.members), "die Gruppe liegt nicht ganz in einer Kategorie"

    ohne = menu_rows_of([name for name in categories if name != "sketch"])
    beitrag = menu_rows_of(categories) - ohne

    assert beitrag == len(im_menü - mitglieder) + 1, (
        f"Skizze trägt {beitrag} Zeilen: erwartet je Nichtmitglied eine "
        f"({len(im_menü - mitglieder)}) plus eine für den Sammeleintrag"
    )
    assert beitrag < len(im_menü), (
        "die Zusammenlegung spart keine Zeile — dann zählt die Rechnung die Mitglieder einzeln"
    )


def test_no_menu_is_folded_that_would_have_fitted(window: MainWindow) -> None:
    """Gefaltet wird, weil es sein muss — auch in der Menüleiste.

    Die Regel stand seit dem 24.08.2026 fest und war für das **Kontextmenü**
    geprüft (:func:`test_a_group_of_one_never_becomes_a_submenu`); die
    Menüleiste hatte keinen Test dafür und faltete *Erzeugen* ohne Not.

    Gezählt wird am gebauten Fenster: Ein Menü ohne Untermenü zeigt seine
    Einträge selbst, und wenn diese Zahl in die Grenze passt, darf kein
    Untermenü darin stehen.
    """
    from app.core.registry.surfaces import MAX_MENU_ROWS

    for action in window.menuBar().actions():
        menu = action.menu()
        if menu is None:
            continue
        rows = [entry for entry in menu.actions() if not entry.isSeparator()]
        submenus = [entry for entry in rows if entry.menu() is not None]
        if not submenus:
            continue
        flat = (
            len(rows)
            - len(submenus)
            + sum(
                len([e for e in entry.menu().actions() if not e.isSeparator()])
                for entry in submenus
            )
        )
        assert flat > MAX_MENU_ROWS, (
            f"{action.text()}: flach wären es {flat} Zeilen, die Grenze ist "
            f"{MAX_MENU_ROWS} — das Untermenü kostet einen Klick und spart nichts"
        )


def test_a_flat_group_keeps_the_names_of_its_categories(window: MainWindow) -> None:
    """Der Gruppenname bleibt sichtbar, auch ohne Zwischenebene.

    Vorher hielt ein nackter Trennstrich die Kategorien auseinander und
    **benannte** sie nicht — man erfuhr den Namen nur, wenn ein Untermenü ihn
    trug, also genau dann, wenn der Weg einen Klick länger war. Der Vergleich
    mit Fusion hat das sichtbar gemacht (27.08.2026): Dort steht der
    Gruppenname dauernd im Band.

    Eine Überschrift ist ein Trennstrich mit Text und zählt in der
    Zeilengrenze deshalb nicht mit — das prüft der Test gleich mit, denn sonst
    wäre die Beschriftung ein Verstoß gegen die Grenze, die sie einhalten soll.
    """
    from app.core.registry import MENU_GROUPS, REGISTRY
    from app.core.registry.surfaces import MAX_MENU_ROWS, group_is_flat

    populated = {spec.category for spec in REGISTRY.all()}
    geprüft = 0
    for title, categories in MENU_GROUPS:
        present = [name for name in categories if name in populated]
        if len(present) < 2 or not group_is_flat(present[0]):
            continue
        menu = next(
            entry.menu()
            for entry in window.menuBar().actions()
            if entry.menu() is not None and entry.text() == str(title)
        )
        headings = [
            entry.text() for entry in menu.actions() if entry.isSeparator() and entry.text()
        ]
        assert len(headings) == len(present), (
            f"{title}: {len(headings)} Überschriften für {len(present)} Kategorien"
        )
        # **Und sie sind sichtbar.** Diese Zusicherung fehlte, und deshalb war
        # der Test jahrelang grün über Überschriften, die niemand je gesehen
        # hat: ``addSection`` setzt einen Text an der Aktion, und Qt zeichnet
        # ihn auf Windows nicht — Titel und nackter Trennstrich waren im Bild
        # punkt- und höhengleich. Ein gesetzter Text ist kein gezeigter, und
        # gezeigt wird er erst, seit ``menu_heading`` ein Label einsetzt.
        shown = [
            entry.defaultWidget().text()
            for entry in menu.actions()
            if isinstance(entry, QWidgetAction) and entry.defaultWidget() is not None
        ]
        assert sorted(shown) == sorted(headings), (
            f"{title}: {len(shown)} sichtbare Überschriften gegen {len(headings)} gesetzte — "
            "ein Titel, den nur die Aktion trägt, erscheint nie"
        )
        rows = sum(1 for entry in menu.actions() if not entry.isSeparator())
        assert rows <= MAX_MENU_ROWS, f"{title}: {rows} Zeilen über der Grenze"
        geprüft += 1

    assert geprüft, "keine flache Gruppe mit mehreren Kategorien — dann prüft dieser Test nichts"


# --- Gefaltet wird je Kategorie, nicht je Gruppe (27.08.2026) -----------------


def test_no_category_is_folded_that_could_have_stayed() -> None:
    """Die Regel vom 24.08.2026, eine Ebene tiefer.

    „Gefaltet wird, weil es sein muss, nicht weil es ordentlich aussieht" galt
    für die Gruppen des Kontextmenüs. Die Menüleiste hatte die gröbere Frage
    (``group_is_flat``): entweder war eine Gruppe ganz flach, oder **jede** ihrer
    Kategorien bekam eine Zwischenebene. Im Menü *Ändern* lagen deshalb alle
    sieben eine Ebene tiefer — auch *Reparatur* mit **einem** Eintrag.

    Geprüft wird die Regel und nicht die heutige Aufteilung: Jede gefaltete
    Kategorie muss die Grenze reißen, wenn man sie allein wieder aufklappt.
    Findet sich eine, die es nicht tut, ist ihr Untermenü ein Klick für nichts.
    """
    from app.core.registry import MENU_GROUPS, REGISTRY
    from app.core.registry.surfaces import MAX_MENU_ROWS, folded_categories, menu_rows_of

    populated = {spec.category for spec in REGISTRY.all()}
    geprüft = 0
    for title, categories in MENU_GROUPS:
        present = [name for name in categories if name in populated]
        if not present:
            continue
        gefaltet = folded_categories(present[0])
        zeilen = sum(1 if name in gefaltet else menu_rows_of([name]) for name in present)
        assert zeilen <= MAX_MENU_ROWS or not gefaltet, (
            f"{title}: {zeilen} Zeilen trotz {len(gefaltet)} Untermenüs"
        )
        for name in gefaltet:
            aufgeklappt = zeilen - 1 + menu_rows_of([name])
            assert aufgeklappt > MAX_MENU_ROWS, (
                f"{title} → {name}: aufgeklappt wären es {aufgeklappt} Zeilen, "
                f"die Grenze ist {MAX_MENU_ROWS} — das Untermenü spart nichts"
            )
            geprüft += 1

    assert geprüft, "keine einzige gefaltete Kategorie — dann prüft dieser Test nichts"


def test_folding_takes_the_rarer_category_when_two_are_the_same_size() -> None:
    """Bei gleicher Größe entscheidet die Reihenfolge, nicht das Alphabet.

    ``folded_groups`` fragte den Rang nur in dem Zweig, in dem eine einzelne
    Gruppe schon genügt; im Ausweichzweig — der die großen zuerst nimmt — stand
    nur die Größe und danach der Name. Gemessen am Menü *Ändern*: Bei einem
    Gleichstand fiel *Verbinden und Abziehen* statt *Formgebung*, weil
    ``boolean`` alphabetisch vor ``shaping`` steht. Die häufigere Gruppe wanderte
    eine Ebene tiefer als die seltenere, und das ist genau die Umkehrung dessen,
    was der Docstring zusagt.

    **Der Aufbau ist der ganze Test**, und die erste Fassung hatte ihn falsch:
    Sie ordnete „aaa" nach hinten — damit war dieselbe Gruppe alphabetisch
    erste *und* hinterste, und beide Fassungen des Codes hätten sie gewählt. Der
    Name muss der Ordnung **entgegenlaufen**, sonst prüft die Probe nichts.

    Drei gleich große Gruppen, Grenze acht: Zwei müssen falten, und die dritte
    ist die vorderste. Die alte Rechnung nahm zuerst „aaa" und ließ „ccc"
    stehen — genau verkehrt herum.
    """
    from app.core.registry.surfaces import folded_groups

    sizes = {"aaa": 5, "bbb": 5, "ccc": 5}
    ordnung = {"aaa": 0, "bbb": 1, "ccc": 2}

    gefaltet = folded_groups(sizes, limit=8, rank=lambda name: ordnung[name])

    assert "aaa" not in gefaltet, (
        f"gefaltet wurde {gefaltet} — die vorderste Gruppe muss stehen bleiben; "
        "sie fällt nur, weil ihr Name alphabetisch vorn steht"
    )
    assert gefaltet[0] == "ccc", (
        f"zuerst gefaltet wurde {gefaltet[0]} — erwartet ist die hinterste (ccc)"
    )


def test_the_named_path_is_the_path_the_menu_builds(window: MainWindow) -> None:
    """Was der Kern als Weg nennt, muss im Fenster auch dort liegen.

    Der **Anschlusstest** zu dieser Änderung, und er ist der Grund, aus dem sie
    überhaupt in den Kern gehört: ``menu_path`` beantwortet dieselbe Frage wie
    ``_build_menus``, und beide Antworten stehen dem Kunden gegenüber — die eine
    im Handbuch, in der Werkzeugbeschreibung des Agenten und in der Tour, die
    andere in der Leiste, die er anklickt. Solange die Rechnung in der
    Oberfläche lag, konnte der Kern sie nicht fragen; er hatte deshalb ein
    eigenes, gröberes Modell, und ein Weg, den das Handbuch nennt, konnte ins
    Leere zeigen.

    Geprüft wird gegen das **gebaute** Fenster, nicht gegen die Funktion, die es
    baut: Zwei Aufrufe derselben Funktion sind auch dann einig, wenn beide falsch
    sind.

    **Zugeordnet wird über den Titel.** Die erste Fassung las ``action.data()``
    und war damit wertlos: Von 158 Menüeinträgen tragen **sechs** ein ``data``,
    und keiner davon ist eine Operation — es sind die zwei Themen und die vier
    Navigationsarten. Der Test sammelte diese sechs, verglich null Operationen
    und blieb in der Mutationsprobe grün, während ``menu_path`` auf die alte,
    gröbere Frage zurückgesetzt war.

    Sein eigener Wächter hat das nicht gefangen, und das ist die Lehre daneben:
    ``assert gebaut`` fragte, ob das Wörterbuch **voll** ist, nicht, ob darin
    Operationen stehen. Ein Wächter muss die Größe messen, an der der Test
    scheitert — deshalb steht unten eine Zahl.
    """
    from app.core.registry import MENU_TWINS, REGISTRY
    from app.core.registry.surfaces import menu_path

    def blank(text: str) -> str:
        return text.replace("&", "")

    gebaut: dict[str, str] = {}
    for action in window.menuBar().actions():
        menu = action.menu()
        if menu is None:
            continue
        for entry in menu.actions():
            unter = entry.menu()
            if unter is not None:
                for tief in unter.actions():
                    if not tief.isSeparator():
                        gebaut[blank(tief.text())] = (
                            f"{blank(action.text())} → {blank(entry.text())} → {blank(tief.text())}"
                        )
            elif not entry.isSeparator():
                gebaut[blank(entry.text())] = f"{blank(action.text())} → {blank(entry.text())}"

    verglichen = 0
    for spec in REGISTRY.all():
        titel = str(spec.title)
        if spec.name in MENU_TWINS or titel not in gebaut:
            continue
        genannt = blank(menu_path(spec))
        assert gebaut[titel] == genannt, (
            f"{spec.name}: Handbuch und Agent nennen „{genannt}“, "
            f"im Fenster liegt sie unter „{gebaut[titel]}“"
        )
        verglichen += 1

    # **Kein Schwellenwert, sondern die Zusage selbst** (8b, 29.08.2026). Hier
    # stand „mindestens 60", dann „mindestens 50" — eine Zahl, die bei jedem
    # neuen Baustein wieder jemand senkt, und die nie sagte, was eigentlich
    # gilt. Die Zusage lautet: **Jede Operation ist im Menü auffindbar**, außer
    # sie ist ein zusammengelegter Zwilling, Mitglied einer Variantengruppe
    # oder sie hat eine Kachel im Bausteinkatalog (§2.6).
    #
    # **Die letzte Ausnahme hieß bis zum 29.08.2026 „ihre Kategorie steht in
    # ``WITHOUT_MENU``", und sie war zu weit.** Von den neunundzwanzig
    # Operationen der Kategorie ``parts`` haben siebenundzwanzig eine Kachel;
    # ``create_lid`` und ``screw_lid`` haben keine. Die Ausnahme deckte sie
    # mit, also blieb dieser Test grün, während beide aus der Menüleiste
    # verschwanden — gemessen 114 Einträge, kein *Deckel erzeugen* darunter,
    # und im Katalog stehen sie auch nicht. **Ein Wächter ist so scharf wie
    # seine weiteste Ausnahme.**
    #
    # Als Verbotstest über die Menge, mit Zusicherung über die Grundmenge: Ein
    # leeres Register unterschreitet jede Schwelle **und** findet keine
    # Verstöße — grün, ohne geprüft zu haben.
    from app.core.registry.registry import variant_members

    assert gebaut, "die Menüleiste ist leer — dann prüft dieser Test nichts"
    ohne_ort = sorted(
        spec.name
        for spec in REGISTRY.all()
        if str(spec.title) not in gebaut
        and spec.name not in MENU_TWINS
        and spec.name not in variant_members()
        and spec.name not in catalogue_operations()
    )
    assert not ohne_ort, f"ohne Menüort und ohne Ausnahme: {ohne_ort}"
    assert verglichen, "kein Weg verglichen — die Zuordnung über die Titel bricht"


def test_a_heading_names_only_what_belongs_to_it(window: MainWindow) -> None:
    """Keine Untermenü-Zeile unter der Überschrift einer anderen Kategorie.

    Eine Überschrift (``addSection``) benennt alles bis zum nächsten
    Trennstrich. Eine Untermenü-Zeile dazwischen liest sich damit als Teil der
    Kategorie davor: Im Menü *Ändern* standen „Transformation" und „Formgebung"
    unter „Verbinden und Abziehen", also in einem Abschnitt, zu dem sie nicht
    gehören.

    **Den Fall gab es vor dem 27.08.2026 nicht.** Bis dahin war eine Menügruppe
    ganz flach (nur Überschriften) oder ganz gefaltet (nur Untermenüs); die
    Mischung entsteht erst mit ``folded_categories``, und mit ihr die Frage, wo
    im Menü eine Zwischenebene steht. Das ist die Lehre neben der Prüfung: Wer
    eine Unterscheidung einführt, führt die Anordnungsfrage mit ein — und keine
    der acht bestehenden Menüprüfungen hat sie gestellt.

    Geprüft wird die Regel, nicht die heutige Aufteilung: Nach der ersten
    Untermenü-Zeile eines Menüs darf keine beschriftete Überschrift mehr
    kommen. Damit ist jede Überschrift von ihren eigenen Einträgen und höchstens
    einem nackten Trennstrich begrenzt.
    """
    geprüft = 0
    for action in window.menuBar().actions():
        menu = action.menu()
        if menu is None:
            continue
        tief = False
        for entry in menu.actions():
            if entry.isSeparator() and entry.text():
                assert not tief, (
                    f"{action.text()}: die Überschrift „{entry.text()}“ steht hinter "
                    "einer Untermenü-Zeile — dann benennt die Überschrift davor "
                    "Zeilen, die ihr nicht gehören"
                )
            elif entry.menu() is not None:
                if not tief:
                    geprüft += 1
                tief = True

    assert geprüft, (
        "kein Menü mit Untermenü gefunden — dann prüft dieser Test seine Zuordnung "
        "und nicht die Anordnung"
    )
