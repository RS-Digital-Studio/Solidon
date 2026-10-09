"""Das kontextsensitive Operationsfeld der rechten Spalte."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from app.core.bootstrap import load_operations
from app.core.perceive.actions import ACTION_ORDER
from app.core.registry import REGISTRY, catalogue_operations, needed_inputs
from app.ui.selection_operations import (
    OPEN_UP_TO,
    PICKER_HANDLES,
    QUICK_BODIES,
    QUICK_BODY,
    QUICK_FEATURES,
    QUICK_SEVERAL_FEATURES,
    SelectionOperationsPanel,
    all_quick_names,
    body_operations,
    feature_operations,
    quick_names,
)
from app.ui.style import NORMAL, TARGET_SIZE


def _availability(selected: int):
    """Dieselbe Mindestzahlentscheidung wie der Fensterpfad."""

    def answer(name: str) -> tuple[bool, str]:
        needed = needed_inputs(REGISTRY.get(name))
        return (
            (True, "")
            if selected >= needed
            else (False, f"Dafür müssen {needed} Körper ausgewählt sein.")
        )

    return answer


def test_part_selection_leaves_its_actions_to_the_part_fields(qt_app: QApplication) -> None:
    """Am Baustein stehen keine Flächenhandlungen seiner Einzelmerkmale."""
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(1, _availability(1), feature_kind="face", part_selected=True)
    assert panel.isHidden()
    panel.set_context(1, _availability(1), feature_kind="face")
    assert not panel.isHidden()


def test_a_part_thread_keeps_only_the_pin_in_the_card(qt_app: QApplication) -> None:
    """Am Innengewinde eines Bausteins steht genau *Stift für Bohrung* (RM-536, Robert 07.10.2026).

    Am Außengewinde nimmt ``not_offered_at`` den Stift weg, und mit ihm bleibt
    die Karte verborgen.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(1, _availability(1), feature_kind="thread", part_selected=True)
    assert not panel.isHidden()
    assert {name for name in panel._buttons if panel._fits_the_level(name)} == {"pin_for_bore"}
    panel.set_context(
        1,
        _availability(1),
        feature_kind="thread",
        part_selected=True,
        left_out=frozenset({"pin_for_bore"}),
    )
    assert panel.isHidden()
    panel.set_context(1, _availability(1), feature_kind="thread")
    assert not panel.isHidden() and panel._only is None, "ohne Baustein gilt die Karte ganz"


def test_a_part_bore_offers_its_pin(qt_app: QApplication) -> None:
    """An einer Bausteinbohrung steht wieder *Stift für Bohrung* allein (RM-552).

    Nach dem Review P2 (N2) blieb die Karte dort zu: Der Stift sagte am
    Schraubenloch ab, weil die Bohrung durch die Senkung läuft. Seit er dort
    baut (``tests/test_bore_pin.py``, Schraubenloch und Einpressbuchse je Kern),
    bietet die Karte ihn an jeder Bausteinbohrung an, wie am Innengewinde — und
    nichts sonst. Ohne Baustein gilt die Karte ganz.
    """
    load_operations()
    assert "hole" in REGISTRY.get("pin_for_bore").applies_to, "sonst prüft das nichts"
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(1, _availability(1), feature_kind="hole", part_selected=True)
    assert not panel.isHidden()
    assert {name for name in panel._buttons if panel._fits_the_level(name)} == {"pin_for_bore"}
    panel.set_context(1, _availability(1), feature_kind="hole")
    assert not panel.isHidden() and panel._only is None, "ohne Baustein gilt die Karte ganz"


def test_the_panel_is_the_registry_without_the_parts_catalogue(qt_app: QApplication) -> None:
    """Die Oberfläche pflegt keine zweite Operationsliste.

    **Merkmalsoperationen gehören dazu, seit die Auswahl sie vorn zeigt.** Bis
    zum 07.09.2026 filterte das Panel jedes ``applies_to`` heraus, und eine
    angeklickte Fläche bot darin nichts an. Draußen bleibt allein der
    Bausteinkatalog: Ein räumliches Teil als Textzeile ist die schlechtere
    Darstellung, und der Knopf daneben führt hin.
    """
    load_operations()
    specs = body_operations(REGISTRY.all()) + feature_operations(REGISTRY.all())
    panel = SelectionOperationsPanel(REGISTRY.all())

    assert {spec.name for spec in specs} == set(panel._buttons)
    assert not (set(panel._buttons) & catalogue_operations())
    # **Die Kachel bleibt draußen, die Kategorie nicht** (11.09.2026): Die zwei
    # Deckel ohne Kachel stehen an der Fläche, auf die sie gehören.
    assert {"create_lid", "screw_lid"} <= set(panel._buttons)
    assert {"drill_hole", "resize_hole", "countersink_hole"} <= set(panel._buttons)


def test_the_front_row_follows_the_kind_and_the_count_of_the_selection(
    qt_app: QApplication,
) -> None:
    """Robert, 07.09.2026: „je nach auswahl und menge der auswahl die
    sinnvollsten aktionen".

    Vorher standen dort drei feste Boolesche — an einem einzelnen Körper also
    drei graue Knöpfe, denn eine Vereinigung braucht zwei.

    Geprüft wird beides: dass jede Lage die ihren zeigt und **nur** die, und
    dass jeder Name der Tabellen einen Knopf hat. Ohne das Zweite wäre ein
    Tippfehler unsichtbar — der Knopf fehlte einfach, und die Zeile wäre kurz.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())

    # **Am Namen verglichen, nicht am Knopf.** Eine Menge von Widgets enthält
    # nie eine Zeichenkette — die Zusage wäre immer erfüllt und wertlos.
    in_the_list = {
        str(button.property("operationName"))
        for _section, _toggle, buttons in panel._groups.values()
        for button in buttons
    }
    # **Jede Hauptaktion hat auch ihre Zeile in der Liste**, verborgen, wo sie
    # oben steht (Fragebogen zu 0.5.3). Bis zum 06.10.2026 verbot dieser Test
    # die Zeile ganz — und hielt damit die Lücke fest: *Aushöhlen* an einer
    # Fläche und *Reparieren* am ganzen Körper gelten dort, stehen dort nicht
    # oben und standen deshalb nirgends. Die Zusage ist „nie oben und unten
    # zugleich“, und die prüft die Schleife unten je Lage.
    for name in all_quick_names():
        assert name in panel._quick_buttons, f"{name} steht in keiner Lage als Knopf da"
        assert name in in_the_list, f"{name} fehlt in der Liste, wo es gilt, ohne oben zu stehen"

    # **Ausgeschrieben, nicht aus der Tabelle gelesen.** Für die Merkmalsarten
    # ist die Erwartung seit dem 09.09.2026 nicht mehr die Tabelle selbst: Was
    # das Merkmalsfenster darüber als Feld zeigt, bekommt hier keinen zweiten
    # Knopf, und *Bohrung ändern* fällt damit aus der Zeile. Eine Erwartung,
    # die weiter `QUICK_FEATURES["hole"]` läse, ginge mit jeder künftigen
    # Änderung mit und prüfte nichts mehr.
    lagen = {
        (1, ""): QUICK_BODY,
        (2, ""): QUICK_BODIES,
        (5, ""): QUICK_BODIES,
        # *Fläche versetzen* steht seit RM-535 als Zeile mit dem Weg darüber.
        (1, "face"): ("drill_hole", "sketch_pocket"),
        (1, "hole"): ("countersink_hole", "plug_hole", "pattern_feature"),
        (1, "cone"): ("countersink_hole", "pattern_feature"),
        (1, "slot"): ("pattern_feature",),
        (1, "edge_loop"): QUICK_FEATURES["edge_loop"],
        # Gemessene Merkmalshandlungen stehen bereits als Felder darüber.
        # Das Muster hat keine solche Zeile und bleibt an jeder vom Register
        # unterstützten Art als eigene Hauptaktion sichtbar.
        (1, "pin"): ("pattern_feature",),
        (1, "sphere"): ("pattern_feature",),
        (1, "torus"): ("pattern_feature",),
        # Verrundung und Gewinde bieten kein Muster; ihre übrigen
        # Merkmalshandlungen erscheinen bereits als Felder.
        (1, "fillet"): (),
        (1, "thread"): (),
        (1, "unknown-feature"): (),
    }
    for (bodies, kind), wanted in lagen.items():
        assert quick_names(bodies, kind) == wanted
        panel.set_context(bodies, _availability(bodies), feature_kind=kind)
        shown = tuple(
            name for name, button in panel._quick_buttons.items() if not button.isHidden()
        )
        assert set(shown) == set(wanted), f"{bodies} Körper, {kind or 'kein'} Merkmal: {shown}"
        twice = [name for name in shown if not panel._list_twins[name].isHidden()]
        assert not twice, f"oben und in der Liste zugleich: {twice}"

    # **Das Merkmal hat Vorrang vor der Menge.** Wer eine Bohrung angeklickt
    # hat, meint sie und nicht den Körper darunter.
    assert quick_names(2, "hole") == quick_names(1, "hole")


def test_a_main_action_of_another_level_stands_in_the_list(qt_app: QApplication) -> None:
    """*Aushöhlen* an einer Fläche: nicht oben, aber in der Liste — und klickbar.

    Fragebogen zu 0.5.3. Die Hauptaktion des Körpers gilt an einer Fläche
    (die Fläche wird die Öffnung), steht dort aber nicht oben; ihr Knopf in
    der Liste tritt dann an ihre Stelle und trägt dieselbe Freigabe.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    requested: list[str] = []
    panel.operationRequested.connect(lambda spec: requested.append(spec.name))

    panel.set_context(1, _availability(1))
    assert not panel._buttons["hollow_object"].isHidden(), "am Körper oben"
    assert panel._list_twins["hollow_object"].isHidden(), "und deshalb nicht darunter"

    panel.set_context(1, _availability(1), feature_kind="face")
    assert panel._buttons["hollow_object"].isHidden(), "an der Fläche nicht oben"
    twin = panel._list_twins["hollow_object"]
    assert not twin.isHidden() and twin.isEnabled(), "aber in der Liste"
    twin.click()
    assert requested == ["hollow_object"], "und er führt in dieselbe Handlung"

    panel.set_context(
        1,
        lambda name: (False, "Gesperrt.") if name == "hollow_object" else (True, ""),
        feature_kind="face",
    )
    assert twin.isHidden(), "eine gesperrte Handlung steht wie oben nicht da"
    assert twin.toolTip() == "Gesperrt.", "und trägt den Grund wie ihr Knopf oben"


def test_the_button_of_an_action_is_the_one_that_stands(qt_app: QApplication) -> None:
    """``button_for`` nennt den Knopf, an dem die Handlung gerade steht — oben oder in der Liste.

    Anleitungen und Tour fragen danach (``guide_targets``). Sie lasen nur den
    oberen Knopf, und an einer Fläche zeigte ``operation:hollow_object`` auf
    einen verborgenen — der Rahmen fand kein Ziel, obwohl die Handlung in der
    Liste stand.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())

    panel.set_context(1, _availability(1))
    assert panel.button_for("hollow_object") is panel._buttons["hollow_object"], "am Körper oben"

    panel.set_context(1, _availability(1), feature_kind="face")
    assert panel.button_for("hollow_object") is panel._list_twins["hollow_object"], (
        "an der Fläche ihre Zeile in der Liste"
    )
    plain = next(name for name in panel._buttons if name not in panel._list_twins)
    assert panel.button_for(plain) is panel._buttons[plain], (
        "ohne Listenzwilling bleibt es der eine Knopf"
    )
    assert panel.button_for("no_such_operation") is None


def test_what_the_feature_does_not_offer_leaves_the_front_row() -> None:
    """Am Kegel, der die Mündung verengt, steht *Senken* nicht vorn (R3).

    Die Hauptaktionen folgen der Merkmalsart, und am Kegel war *Senken* die
    erste — auch an der Haltelippe einer Magnettasche, wo der Trichter die
    Lippe mitnahm. Was am gewählten Merkmal nichts Sinnvolles tut, nennt der
    Kern (``perceive.actions.not_offered_at``); ohne gewähltes Merkmal gilt
    die Menge nicht.
    """
    load_operations()
    narrowing = frozenset({"countersink_hole"})

    assert quick_names(1, "cone")[0] == "countersink_hole"
    assert quick_names(1, "cone", left_out=narrowing) == ("pattern_feature",)
    assert quick_names(1, "", left_out=narrowing) == QUICK_BODY


def test_several_marked_features_offer_the_grouping_first() -> None:
    """Mehrere markierte Merkmalszeilen eines Körpers: vorn *Als Muster zusammenfassen*.

    Unter den Schwellen der Erkennung bleibt ein kleines Feld Einzelmerkmale
    (RM-504); wer mehrere davon markiert, findet den Weg zur Zusammenfassung
    oben, nicht in der Suchliste. Ein einzelnes Merkmal und mehrere Körper
    bleiben bei ihren Zeilen.
    """
    load_operations()
    assert REGISTRY.get("group_pattern").consumes == 1
    assert quick_names(1, "", features=2) == QUICK_SEVERAL_FEATURES == ("group_pattern",)
    assert quick_names(1, "", features=1) == QUICK_BODY
    assert quick_names(2, "", features=4) == QUICK_BODIES
    assert quick_names(1, "hole", features=2) == quick_names(1, "hole")
    assert "group_pattern" in all_quick_names()


def test_the_panel_leaves_out_what_the_feature_does_not_offer(qt_app: QApplication) -> None:
    """*Senken* steht an einer Verengung weder vorn noch in der Liste (R3).

    Dieselbe Menge für beide Stellen (:meth:`SelectionOperationsPanel.set_context`):
    Stünde der Knopf unten weiter, führte er zu einer Handlung, die das Panel
    oben gerade weggelassen hat. An einem anderen Kegel kommt er zurück.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())

    def listed() -> set[str]:
        return {
            str(button.property("operationName"))
            for _section, _toggle, buttons in panel._groups.values()
            for button in buttons
            if not button.isHidden()
        }

    def front() -> set[str]:
        return {name for name, button in panel._quick_buttons.items() if not button.isHidden()}

    panel.set_context(
        1, _availability(1), feature_kind="cone", left_out=frozenset({"countersink_hole"})
    )
    assert "countersink_hole" not in front() | listed()
    assert "pattern_feature" in front()

    panel.set_context(1, _availability(1), feature_kind="cone")
    assert "countersink_hole" in front()


def test_the_search_finds_customer_words_and_names_what_another_choice_needs(
    qt_app: QApplication,
) -> None:
    """„löschen“ findet *Objekt entfernen*, „verschmelzen“ nennt, was *Vereinigen* braucht.

    Fragebogen zu 0.5.3: Ein Anfänger fand weder das Löschen noch das
    Vereinigen. Die Suche der Karte verglich nur Titel und Gruppe; sie rechnet
    jetzt wie die Palette (``found_in_rounds``). Und ein Treffer, der an
    dieser Auswahl nicht geht, ist kein „Kein Treffer“: Der Satz nennt seinen
    Sperrgrund — im Fenster der, der sagt, wie das zweite Objekt dazukommt.
    """
    from app.i18n import tr

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(1, _availability(1))

    panel.search.setText("löschen")
    assert not panel._buttons["delete_object"].isHidden(), "Kundenwort ohne Titeltreffer"
    assert panel._nothing.isHidden()

    panel.search.setText("verschmelzen")
    assert not panel._nothing.isHidden()
    assert panel._nothing.text() == tr(
        "{name}: {value}",
        name=str(REGISTRY.get("union_objects").title),
        value="Dafür müssen 2 Körper ausgewählt sein.",
    )
    assert not panel._everywhere.isHidden(), "der Weg in alle Funktionen bleibt"

    panel.search.setText("xyzzy")
    assert panel._nothing.text() == tr("Kein Treffer — versuchen Sie ein anderes Wort.")

    panel.search.setText("")
    panel.set_context(2, _availability(2))
    panel.search.setText("verschmelzen")
    assert panel._nothing.isHidden(), "bei zwei Körpern ist *Vereinigen* oben ein Treffer"


def test_a_locked_window_action_is_named_without_its_menu_ellipsis(
    qt_app: QApplication,
) -> None:
    """Der Satz zu einer gesperrten Fensterhandlung nennt ihren Namen, nicht die Menüzeile.

    *Automatisch teilen* hat keinen Registereintrag; Titel und Grund kommen
    von der Aktion des Fensters (:meth:`SelectionOperationsPanel.add_window_action`).
    Ihre Beschriftung trägt die Auslassung des Menüs — vor dem Doppelpunkt
    stand sie als „Automatisch teilen …: …“ im Satz.
    """
    from PySide6.QtGui import QAction

    from app.i18n import tr

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    action = QAction(tr("Automatisch teilen …"), panel)
    reason = "Das Teil passt schon auf das Bett."
    action.setToolTip(reason)
    action.setEnabled(False)
    assert panel.add_window_action("auto_split", "prepare", action)
    # Alles andere gesperrt und ohne Grund: Getroffen wird die Handlung über
    # ihre Gruppe, und nur sie hat einen Satz.
    panel.set_context(1, lambda name: (False, ""))

    panel.search.setText(tr("Vorbereiten"))
    assert panel._buttons["auto_split"].isHidden(), "gesperrt steht der Knopf nicht da"
    assert not panel._nothing.isHidden()
    assert panel._nothing.text() == tr(
        "{name}: {value}", name=tr("Automatisch teilen …").removesuffix(" …"), value=reason
    )
    assert "…" not in panel._nothing.text()


def test_selection_changes_update_in_place_and_explain_disabled_actions(
    qt_app: QApplication,
) -> None:
    """Eine große Registerliste wird bei jedem Klick nur nachgeführt."""
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, 340)
    panel.show()
    identities = {name: id(button) for name, button in panel._buttons.items()}

    panel.set_context(2, _availability(1))
    joining = panel._buttons["union_objects"]
    panel.set_context(1, _availability(1))
    assert not panel.isHidden()
    assert panel.summary.text() == "1 Objekt gewählt"
    assert not joining.isEnabled()
    assert joining.isHidden()
    assert "2 Körper" in joining.toolTip()

    panel.set_context(2, _availability(2))
    QApplication.processEvents()
    assert identities == {name: id(button) for name, button in panel._buttons.items()}
    assert joining.isEnabled()
    assert not joining.isHidden()
    assert panel.summary.text() == "2 Objekte gewählt"
    # Der Knopf *Merkmale* ist am 07.09.2026 entfallen (Konzept A): Seit die
    # Maße des Gewählten über diesen Handlungen stehen, führt er nirgendwohin.
    assert not hasattr(panel, "feature_button")
    for name in QUICK_BODIES:
        button = panel._buttons[name]
        assert button.width() >= button.sizeHint().width(), f"{button.text()} ist abgeschnitten"
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus

    # **Ohne Auswahl bleibt die Karte stehen: für die Bausteine** (Entscheidung
    # Robert, 18.09.2026) **und für die Handlungen, die alle Körper nehmen**
    # (Robert, 27.09.2026), davon aber nur ``SCENE_ACTIONS_IN_THE_CARD``
    # (RM-506): Anordnen und Überschneidungen stehen in der Palette. Bis zum
    # 18.09. verschwand die Karte ganz, und damit der einzige sichtbare Zugang
    # zum Katalog.
    from app.core.registry.surfaces import SCENE_ACTIONS_IN_THE_CARD

    panel.set_context(0, _availability(0))
    QApplication.processEvents()
    assert not panel.isHidden()
    assert not panel.search.isVisible(), "ohne Auswahl gibt es nichts zu durchsuchen"
    assert panel.catalog_button.isVisible(), "der Weg zu den Bausteinen bleibt"
    for_all = {spec.name for spec in body_operations(REGISTRY.all()) if spec.takes_whole_scene}
    in_the_card = for_all & SCENE_ACTIONS_IN_THE_CARD
    assert in_the_card, "ohne Handlung für alle prüft der Test nichts"
    shown = {name for name, button in panel._buttons.items() if button.isVisible()}
    assert shown == in_the_card, shown


def test_quick_actions_reflow_when_the_selection_column_narrows(qt_app: QApplication) -> None:
    """Die Mindestbreite einer Zweierspalte darf die schmale Auswahl nicht aufweiten."""
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(1, _availability(1))
    panel.resize(500, 500)
    panel.show()
    QApplication.processEvents()
    first, second = (panel._quick_buttons[name] for name in QUICK_BODY[:2])
    assert first.y() == second.y()
    panel.resize(216, 500)
    QApplication.processEvents()
    assert first.y() < second.y()
    assert panel.width() == 216
    for name in QUICK_BODY:
        control = panel._quick_buttons[name]
        assert control.x() + control.width() <= panel.width()
    panel.resize(500, 500)
    QApplication.processEvents()
    assert first.y() == second.y()


def test_actions_of_the_wrong_level_leave_instead_of_greying_out(qt_app: QApplication) -> None:
    """Der Abnahmenachweis zu P5: die Sichtbarkeit folgt der Auswahltiefe.

    Konzept „Ein Ort für die Auswahl", C — zwei Sorten Nichtverfügbarkeit, und
    nur eine verschwindet. *Auf dem Bett anordnen*, *Objekt duplizieren* und
    *Objekt umbenennen* standen an einer gewählten Fläche bedienbar da, weil
    ``_palette_availability`` die Körperauswahl fragt und ein gewähltes
    Merkmal immer einen Körper unter sich hat. Von 102 Registereinträgen
    betraf das 38.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, 340)
    panel.show()

    am_koerper = {spec.name for spec in body_operations(REGISTRY.all())} - set(panel._quick_buttons)
    am_merkmal = {spec.name for spec in feature_operations(REGISTRY.all())} - set(
        panel._quick_buttons
    )
    assert am_koerper and am_merkmal, "ohne beide Mengen prüft der Test nichts"
    shared = am_koerper & am_merkmal
    assert shared == {"draft_faces"}, "Formschräge gilt ganzen Körpern und gewählten Flächen"
    draft = REGISTRY.get("draft_faces")
    assert draft.also_on_body and tuple(draft.applies_to) == ("face",)

    def sichtbar() -> set[str]:
        """Die Knöpfe der **Liste**, ohne die Hauptaktionen oben.

        Die Zeile oben ist eine Empfehlung mit eigener Regel
        (:func:`quick_names`), und die darf von der Stufe abweichen: *Bohrung
        setzen* steht dort auch an einem Körper, weil eine Bohrung ihre Fläche
        an jedem Körper findet und ohne eine erkannte selbst Bescheid sagt.
        Der Stufenfilter gilt der Liste darunter, und nur die zählt hier.
        """
        qt_app.processEvents()
        return {
            name
            for name, button in panel._buttons.items()
            if not button.isHidden() and name not in panel._quick_buttons
        }

    panel.set_context(1, _availability(1))
    am_koerper_sichtbar = sichtbar()
    assert am_koerper_sichtbar & am_merkmal == shared, (
        "am Körper steht nur die ausdrücklich auch dort geltende Merkmalshandlung"
    )

    panel.set_context(1, _availability(1), feature_kind="face")
    an_der_flaeche = sichtbar()
    assert "arrange_bed" not in an_der_flaeche, (
        "eine Fläche wird nie auf dem Bett angeordnet — der Knopf verschwindet"
    )
    assert an_der_flaeche & am_koerper == shared, (
        "an einer Fläche steht nur die ausdrücklich auch dort geltende Körperhandlung"
    )

    # Und der Weg zurück: die Stufe wechselt, die Knöpfe kommen wieder. Sie
    # verschwinden beim Wechsel der Stufe, nicht beim zufälligen Klick.
    panel.set_context(1, _availability(1))
    assert sichtbar() == am_koerper_sichtbar

    # Fehlende Vorbedingungen nehmen die Zeile ebenfalls heraus. Bei einer
    # passenden Auswahl kehrt dasselbe Bedienelement wieder zurück.
    zweisam = [name for name in am_koerper if needed_inputs(REGISTRY.get(name)) > 1]
    assert zweisam, "kein Fall für die erfüllbare Vorbedingung im Register gefunden"
    for name in zweisam:
        button = panel._buttons[name]
        assert button.isHidden(), name
        assert not button.isEnabled(), f"{name}: sie bleibt aber grau"
        assert "Körper" in button.toolTip(), f"{name}: und sie nennt den Grund"


def test_actions_for_all_bodies_stand_without_a_selection_and_not_at_one(
    qt_app: QApplication,
) -> None:
    """Robert, 27.09.2026: „sollten wir aber anzeigen, wenn keins ausgewählt
    ist und nicht wenn eins ausgewählt ist, da es eine operation für alle ist".

    Am gewählten Körper sagte *Druckoptimal ausrichten*, es gelte diesem
    Körper — und richtete jeden aus.

    **Und von den dreien steht nur eine** (Robert, 05.10.2026: „Eigentlich
    reicht hier druckoptimal ausrichten“): Anordnen und Überschneidungen
    prüfen bleiben über Menü und Befehlspalette erreichbar.
    """
    from app.i18n import tr
    from app.ui.selection_operations import SCENE_ACTIONS_IN_THE_CARD

    load_operations()
    every = {spec.name for spec in body_operations(REGISTRY.all()) if spec.takes_whole_scene}
    assert every > SCENE_ACTIONS_IN_THE_CARD, "die Karte zeigt eine Auswahl der Szenenhandlungen"
    for_all = set(SCENE_ACTIONS_IN_THE_CARD)
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, 520)
    panel.show()

    def shown() -> set[str]:
        qt_app.processEvents()
        return {name for name, button in panel._buttons.items() if button.isVisible()}

    panel.set_context(0, _availability(0))
    assert shown() == for_all
    assert panel.chosen_level() == "scene"
    assert panel._nothing.isVisible() and panel._nothing.text() == tr("Gilt für alle Körper.")
    assert not panel.search.isVisible(), "eine Handlung sucht niemand"

    panel.set_context(1, _availability(1))
    assert not shown() & every, "am gewählten Körper steht keine Handlung für alle"
    panel.set_context(1, _availability(1), feature_kind="face")
    assert not shown() & every, "an einer Fläche auch nicht"

    # Ein Suchtext von der letzten Auswahl filtert ohne Auswahl nichts weg:
    # Das Feld ist dann verborgen, und niemand sähe, warum etwas fehlt.
    panel.set_context(1, _availability(1))
    panel.search.setText("wortdasnichtvorkommt")
    panel.set_context(0, _availability(0))
    assert shown() == for_all

    # In einer leeren Szene ist nichts freigegeben — dann steht der Satz da.
    panel.set_context(0, lambda _name: (False, "Die Szene ist leer."))
    assert not shown()
    assert "Bausteine gehen auch so" in panel._nothing.text()


def test_only_the_actions_of_that_kind_of_feature_stay(qt_app: QApplication) -> None:
    """An einer Bohrung steht nichts, was nur an einer Fläche etwas tut.

    Robert am 09.09.2026: „bei einer Bohrung oder Senkung brauchen wir Filament
    und die Körperliste gar nicht". Die Stufe reichte bis dahin nur bis
    „Merkmalshandlung ja oder nein" — und damit standen an einer Bohrung auch
    *Text aufbringen* (`label_text`) und *Filament auf eine Fläche*
    (`paint_slot`), beide ``applies_to=("face",)``.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, 340)
    panel.show()

    def sichtbar() -> set[str]:
        qt_app.processEvents()
        return {
            name
            for name, button in panel._buttons.items()
            if not button.isHidden() and name not in panel._quick_buttons
        }

    # **Der Kegel steht nicht mehr dabei**, und das ist kein Rückschritt: Seine
    # sechs Operationen sind seit dem 09.09.2026 vollständig eingelöst — fünf
    # als Felder im Merkmalsfenster darüber, *Senken* als Knopf der
    # Schnellzeile. Was übrig bleibt, ist nichts, und eine leere Liste ist
    # dort die richtige Antwort (gemessen am Register, siehe
    # ``test_no_action_stands_twice_in_the_selection_window``).
    for kind in ("hole", "face"):
        panel.set_context(1, _availability(1), feature_kind=kind)
        gezeigt = sichtbar()
        assert gezeigt, f"{kind}: eine leere Liste prüft nichts"
        for name in gezeigt:
            applies = REGISTRY.get(name).applies_to
            assert kind in applies, f"{name} gilt für {applies}, gezeigt wurde es an {kind}"

    # Und die Gegenprobe, damit der Test nicht bloß eine leere Menge lobt: Was
    # nur an der Fläche geht, war an der Bohrung wirklich zu sehen.
    panel.set_context(1, _availability(1), feature_kind="face")
    nur_flaeche = sichtbar()
    panel.set_context(1, _availability(1), feature_kind="hole")
    assert nur_flaeche - sichtbar(), "ohne Unterschied zwischen den Arten misst der Test nichts"
    assert "label_text" not in sichtbar(), "eine Bohrung wird nicht beschriftet"
    assert "paint_slot" not in sichtbar(), "eine Bohrung trägt kein eigenes Filament"


def test_the_summary_says_what_is_chosen_not_how_many(qt_app: QApplication) -> None:
    """Der zweite Nachweis zu P5: die Zeile nennt die Tiefe (Konzept B).

    „1 Objekt gewählt" stand auch über Merkmalshandlungen — es nannte die
    Körperzahl, während die Knöpfe darunter dem Merkmal galten. Bei mehreren
    Körpern bleibt die Menge die richtige Antwort: einen Namen gibt es dort
    nicht.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())

    panel.set_context(1, _availability(1), label="Halter")
    assert panel.summary.text() == "Halter"

    # Am Merkmal nennt es das Merkmalfenster darüber, mit Maß — die Zeile
    # hier tritt zurück, damit der Name einmal dasteht (RM-510).
    panel.set_context(1, _availability(1), feature_kind="face", label="Halter · Oberseite")
    assert panel.summary.isHidden(), "ein Name der Auswahl, nicht zwei"

    panel.set_context(2, _availability(2), label="Halter")
    assert not panel.summary.isHidden()
    assert panel.summary.text() == "2 Objekte gewählt", "bei zweien gibt es keinen einen Namen"

    # Ohne Namen bleibt es bei der Menge — das Panel erfindet keinen.
    panel.set_context(1, _availability(1))
    assert panel.summary.text() == "1 Objekt gewählt"


def test_search_filters_existing_buttons_and_a_click_carries_the_register_entry(
    qt_app: QApplication,
) -> None:
    """Suche und Klick bleiben am vorhandenen Registereintrag."""
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(2, _availability(2))
    # **Aus den sichtbaren**, seit die Sichtbarkeit der Auswahlstufe folgt
    # (Konzept C): Ohne diese Bedingung fiel die Wahl auf eine
    # Merkmalshandlung, die an zwei gewählten Körpern gar nicht dasteht — und
    # der Test hätte einen Knopf gesucht, den die Suche nicht zeigen kann.
    extra = next(
        button
        for name, button in panel._buttons.items()
        if name not in panel._quick_buttons and button.isEnabled() and not button.isHidden()
    )
    received = []
    panel.operationRequested.connect(received.append)

    panel.search.setText(extra.text())
    QApplication.processEvents()
    assert not extra.isHidden()
    assert any(
        button.isHidden()
        for name, button in panel._buttons.items()
        if name not in panel._quick_buttons
    )

    extra.click()
    assert [entry.name for entry in received] == [str(extra.property("operationName"))]


def test_every_action_row_keeps_a_keyboard_sized_height(qt_app: QApplication) -> None:
    """Der Bericht darf die Hauptaktionen nicht zu überlappenden Zeilen drücken."""
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, panel.minimumHeight())
    panel.set_context(2, _availability(2))
    panel.show()
    qt_app.processEvents()

    for name in QUICK_BODIES:
        assert panel._buttons[name].height() >= TARGET_SIZE
    assert panel.search.height() >= TARGET_SIZE
    assert panel.catalog_button.height() >= TARGET_SIZE


def test_the_catalog_button_is_the_main_button_of_the_panel(qt_app: QApplication) -> None:
    """*Bausteine* ist ein Hauptknopf: Akzentfarbe **und** halbfett (Regel 18).

    Er stand als grauer Werkzeugknopf unter der Liste und ging zwischen den
    Handlungen unter (Robert, 11.09.2026: „damit er auch auffällt"). Die Farbe
    kommt aus ``QPushButton:default`` des Stylesheets, das Gewicht aus
    ``make_primary`` — beides zusammen, nicht eines allein.
    """
    from PySide6.QtGui import QFont

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    assert panel.catalog_button.isDefault(), "die Akzentfarbe hängt am Default-Zustand"
    assert panel.catalog_button.font().weight() >= QFont.Weight.DemiBold, "und fett dazu"


def test_every_group_folds_and_a_search_hit_unfolds_it(qt_app: QApplication) -> None:
    """Jede Gruppe ist ein Abschnitt zum Zuklappen — und ein Suchtreffer klappt ihn auf.

    Graue Zwischenüberschriften über einer Wand gleicher Knöpfe (Robert,
    11.09.2026: „monoton und dadurch unübersichtlich"). Jetzt trägt jede
    Gruppe die Kopfzeile der linken Spalte: ein Umschalter mit Linie darunter.
    Wer sucht, soll den Treffer sehen, auch wenn er die Gruppe vorher
    zugeklappt hatte.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(1, _availability(1))
    panel.show()
    qt_app.processEvents()

    assert panel._groups, "sonst prüft dieser Test nichts"
    folded: dict[str, list] = {}
    for title, (section, toggle, buttons) in panel._groups.items():
        assert toggle.isCheckable(), title
        # Offen beginnt, was ein Menü noch zeigte; was darüber liegt, beginnt
        # zu (``OPEN_UP_TO``, eigener Test unten).
        listed = sum(not button.isHidden() for button in buttons)
        assert toggle.isChecked() == (listed <= OPEN_UP_TO), f"{title}: {listed} Einträge"
        shown = [button for button in buttons if button.isVisibleTo(panel)]
        if not shown:
            continue
        toggle.setChecked(False)
        qt_app.processEvents()
        assert not any(button.isVisibleTo(panel) for button in shown), f"{title} klappt zu"
        assert section.isVisibleTo(panel), "die Kopfzeile bleibt stehen"
        folded[title] = shown

    # Zugeklappt lassen — und nach einem Knopf daraus suchen.
    title, shown = next(iter(folded.items()))
    toggle = panel._groups[title][1]
    wanted = shown[0]
    panel.search.setText(str(wanted.property("operationTitle") or wanted.text()))
    qt_app.processEvents()
    assert toggle.isChecked(), f"ein Treffer öffnet {title}"
    assert wanted.isVisibleTo(panel), "und der Treffer steht da"


def test_a_group_over_the_menu_limit_starts_folded_unless_opened_by_hand(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was ein Menü nicht mehr zeigte, beginnt in der Karte zugeklappt.

    Die vier Operationsmenüs sind am 11.09.2026 hierher gewandert, weil 69
    gesperrte Zeilen Lärm waren — mitgewandert war die Zahl der Einträge, nicht
    die Grenze: An einem gewählten Körper standen 42 Knöpfe offen da, 24 davon
    unter „Ändern", und das ist der Zustand direkt nach jedem Import
    (Durchsicht 14.09.2026). Die Grenze ist die der Menüs (zwölf), gerechnet an
    der Stufe: Dieselbe Gruppe hat an einer Fläche zwei Einträge und steht dort
    offen. Und wer sie selbst aufklappt, findet sie nach dem nächsten Klick auf
    einen Körper nicht wieder zu — die Regel gilt nur, solange niemand
    entschieden hat.
    """
    from app.ui import selection_operations

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(1, _availability(1))
    panel.show()
    qt_app.processEvents()

    def listed(title: str) -> int:
        return sum(not button.isHidden() for button in panel._groups[title][2])

    # **Seit RM-506 liegt am Körper keine Gruppe mehr über zwölf**: Große
    # Kategorien teilt die Karte in Untergruppen von höchstens einem Menü.
    # Die Regel gilt weiter für jede, die darüber läge; geprüft wird sie mit
    # einer Grenze, die eine Gruppe am Körper überschreitet und an der Fläche
    # einhält — dieselbe Stufenfrage wie mit zwölf.
    at_the_body = {title: listed(title) for title in panel._groups}
    panel.set_context(1, _availability(1), feature_kind="face")
    qt_app.processEvents()
    at_the_face = {title: listed(title) for title in panel._groups}
    staged = sorted(
        (
            (at_the_body[title] - at_the_face[title], title)
            for title in panel._groups
            if 0 < at_the_face[title] < at_the_body[title]
        ),
        reverse=True,
    )
    assert staged, "ohne eine Gruppe, die an der Fläche schrumpft, prüft der Test nichts"
    limit = at_the_face[staged[0][1]]
    monkeypatch.setattr(selection_operations, "OPEN_UP_TO", limit)
    panel.set_context(1, _availability(1))
    qt_app.processEvents()

    big = [title for title in panel._groups if listed(title) > limit]
    assert big, "ohne eine Gruppe über der Grenze prüft der Test nichts"
    for title, (_section, toggle, _buttons) in panel._groups.items():
        if listed(title):
            assert toggle.isChecked() == (listed(title) <= limit), title

    title = staged[0][1]
    assert title in big
    toggle = panel._groups[title][1]
    panel.set_context(1, _availability(1), feature_kind="face")
    qt_app.processEvents()
    assert listed(title) <= limit, f"{title} hat an einer Fläche weniger Einträge"
    assert toggle.isChecked(), f"{title} steht an der Fläche offen"

    panel.set_context(1, _availability(1))
    qt_app.processEvents()
    assert not toggle.isChecked(), f"{title} ist am Körper wieder zu"

    toggle.click()
    qt_app.processEvents()
    assert toggle.isChecked(), "von Hand geöffnet"
    panel.set_context(1, _availability(1), feature_kind="face")
    panel.set_context(1, _availability(1))
    qt_app.processEvents()
    assert toggle.isChecked(), "und das bleibt über den Stufenwechsel hinweg"


def test_the_picker_above_the_list_shows_its_handling_no_second_time(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*Filament entfernen* steht einmal in der Karte — am Wähler, nicht darunter.

    Der Schnellwähler hängt an zweiter Stelle in derselben Karte und trägt den
    Knopf mit Grund (gesperrt, solange nichts zugewiesen ist); die Operation
    darunter stand mit demselben Text bedienbar da (Durchsicht 14.09.2026).
    Zwei gleiche Knöpfe mit entgegengesetzter Aussage. Geprüft wird beides:
    dass der Wähler die Handlung wirklich trägt, und dass die Liste sie an
    Körper und Fläche nicht mehr zeigt.
    """
    from app.core.knowledge import filaments
    from app.ui.filament_assignment import QuickFilamentPicker

    load_operations()
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    picker = QuickFilamentPicker()
    try:
        texts = {button.text() for button in picker.findChildren(QPushButton)}
        assert PICKER_HANDLES, "ohne Eintrag prüft der Test nichts"
        # Entfernen trägt der Wähler als Knopf, Zuweisen und Färben über seine
        # Auswahlliste (RM-510: Färben stand am Körper und an der Fläche
        # zweimal da).
        assert str(REGISTRY.get("clear_filament").title) in texts, "Entfernen fehlt am Wähler"
        assert picker.picker.accessibleName(), "die Auswahlliste des Wählers weist zu"
    finally:
        picker.close()

    panel = SelectionOperationsPanel(REGISTRY.all())
    for kind in ("", "face"):
        panel.set_context(1, _availability(1), feature_kind=kind)
        qt_app.processEvents()
        listed = {name for name in PICKER_HANDLES if not panel._buttons[name].isHidden()}
        assert not listed, f"{kind or 'Körper'}: {sorted(listed)} stehen ein zweites Mal"


def test_no_action_stands_twice_in_the_selection_window(qt_app: QApplication) -> None:
    """Was oben ein Feld hat, bekommt hier keinen zweiten Knopf.

    Merkmalsfenster und Auswahlkarte liegen im selben Fenster übereinander
    (``MainWindow._build_feature_dock``). Das obere zeigt die Handlungen aus
    ``ACTION_ORDER`` als Felder samt gemessenem Wert und einem Knopf; die Karte
    darunter bot dieselben Handlungen ein zweites Mal an — an einer gewählten
    Bohrung standen *Bohrung ändern*, *Merkmal drehen* und *Merkmal verdoppeln*
    zweimal (Befund Robert, 09.09.2026: „hier soll immer nur für das ausgewählte
    etwas stehen").

    Dieselbe Regel, nach der eine Hauptaktion nicht auch in der Suchliste steht,
    nur eine Karte höher.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, 340)
    panel.show()
    als_feld = {name for row in ACTION_ORDER for name in row}
    assert als_feld, "ohne die Kernliste prüft der Test nichts"

    for kind in ("hole", "cone", "pin", "sphere", "face"):
        panel.set_context(1, _availability(1), feature_kind=kind)
        qt_app.processEvents()
        gezeigt = {name for name, button in panel._buttons.items() if not button.isHidden()} | set(
            panel._quick_shown
        )
        doppelt = gezeigt & als_feld
        assert not doppelt, f"{kind}: {sorted(doppelt)} stehen oben als Feld und hier als Knopf"

    # **Und die Gegenprobe, damit der Test nicht bloß eine leere Karte lobt:**
    # An einer Fläche gilt keine der fünf Feldhandlungen, und dort steht die
    # Karte weiterhin voll.
    panel.set_context(1, _availability(1), feature_kind="face")
    qt_app.processEvents()
    an_der_flaeche = set(panel._quick_shown) | {
        name for name, button in panel._buttons.items() if not button.isHidden()
    }
    assert len(an_der_flaeche) >= 5, f"an einer Fläche bleibt die Karte gefüllt: {an_der_flaeche}"


def test_a_button_wraps_its_label_instead_of_cutting_it(qt_app: QApplication) -> None:
    """Eine Beschriftung, die nicht passt, bricht um — sie wird nicht beschnitten.

    „Bohrung verschließen" will mehr Platz, als das Auswahlfenster am rechten
    Rand hat, und Qt schnitt den Titel dann zu „Bohrung versch…" (Befund
    Robert, 09.09.2026, an „Bohru…ndern"). Ein abgeschnittener Titel nennt die
    Handlung nicht mehr, und anders als bei einem Hinweis gibt es hier keinen
    zweiten Ort, an dem sie stünde.

    **Gemessen wird relativ, nicht absolut.** Welche Zahl „passt" bedeutet,
    sagt dieselbe ``fontMetrics``, mit der auch gezeichnet wird — der Test
    rechnet die Prüfbreiten daraus aus, statt eine Bildpunktzahl zu behaupten.

    **Der Umbruch wird am Knopf erzwungen, nicht über die Kartenbreite.** Die
    Karte wird nie schmaler als ihr breitestes ungebrochenes Element
    (*Passende Bausteine …*). Unter Windows offscreen ist die Ersatzschrift so
    breit, dass der Titel dort trotzdem nicht passte; unter Linux und macOS
    rechnet offscreen mit der echten Schrift, und dort passt er in die
    schmalste Karte — ein Umbruch wäre falsch. Zugesichert wird deshalb auf
    jeder Plattform dasselbe: An der schmalsten Karte ist keine Zeile
    beschnitten, und auf einen Platz, der nur das längste Wort fasst, bricht
    der Titel vollständig in zwei Zeilen um.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.show()
    knopf = panel._quick_buttons["plug_hole"]
    titel = str(knopf.property("operationTitle"))
    assert " " in titel, f"der Titel muss mehrteilig sein, sonst gibt es nichts zu brechen: {titel}"

    metrics = knopf.fontMetrics()
    beiwerk = knopf.sizeHint().width() - metrics.horizontalAdvance(titel)
    laengstes = max(metrics.horizontalAdvance(wort) for wort in titel.split())

    # Breit genug für den ganzen Titel: eine Zeile.
    panel.resize(metrics.horizontalAdvance(titel) + beiwerk + 4 * NORMAL, 600)
    panel.set_context(1, _availability(1), feature_kind="hole")
    qt_app.processEvents()
    assert "\n" not in knopf.text(), f"wo der Platz reicht, bleibt es eine Zeile: {knopf.text()!r}"

    # Die schmalste Karte: Keine Zeile ist breiter als ihr Knopf, ob er nun
    # umbricht (Windows offscreen) oder der Titel ganz passt (echte Schrift).
    panel.resize(1, 600)
    qt_app.processEvents()
    for zeile in knopf.text().split("\n"):
        assert metrics.horizontalAdvance(zeile) + beiwerk <= knopf.width(), (
            f"an der schmalsten Karte ist {zeile!r} beschnitten ({knopf.width()} breit)"
        )

    # Zu schmal für den Titel, breit genug für sein längstes Wort: zwei Zeilen,
    # und keine davon breiter als der Platz — viermal dieselbe Antwort.
    raum = laengstes + beiwerk + 4 * NORMAL
    panel._wrap_label(knopf, raum)
    gebrochen = knopf.text()
    for _ in range(4):
        panel._wrap_label(knopf, raum)
        assert knopf.text() == gebrochen
    assert "\n" in gebrochen, f"hier muss umgebrochen werden: {gebrochen!r}"
    assert gebrochen.replace("\n", " ") == titel, f"der Titel bleibt vollständig: {gebrochen!r}"
    for zeile in gebrochen.split("\n"):
        assert metrics.horizontalAdvance(zeile) <= laengstes, (
            f"die Zeile {zeile!r} ist breiter als das längste Wort — dann wird sie beschnitten"
        )


def test_a_taller_panel_does_not_rewrap_a_hundred_labels(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Höhe bricht keine Zeile um — umbrochen wird nur bei anderer Breite.

    Jeder Merkmalklick ändert die Höhe der Karte darüber, und jede
    Höhenänderung beschriftete bis zum 22.09.2026 alle gut hundert Knöpfe
    zweimal neu (erst ganz, dann umbrochen): im gebauten Fenster am Halter mit
    Wabenmuster 37 ms je Klick. Eine andere Breite oder andere Hauptaktionen
    brechen weiter neu um.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, 600)
    panel.show()
    panel.set_context(1, _availability(1), feature_kind="hole")
    qt_app.processEvents()
    wrapped: list[object] = []
    original = SelectionOperationsPanel._wrap_label

    def counted(self: SelectionOperationsPanel, button: object, room: int) -> None:
        wrapped.append(button)
        original(self, button, room)  # type: ignore[arg-type]

    monkeypatch.setattr(SelectionOperationsPanel, "_wrap_label", counted)

    panel.resize(320, 700)
    qt_app.processEvents()
    panel.set_context(1, _availability(1), feature_kind="hole")
    qt_app.processEvents()
    assert not wrapped, f"{len(wrapped)} Knöpfe neu beschriftet, nur weil die Höhe wuchs"

    panel.resize(260, 700)
    qt_app.processEvents()
    assert wrapped, "eine andere Breite bricht neu um"


def test_a_chosen_edge_leaves_the_body_operations_out(qt_app: QApplication) -> None:
    """An einer Kante steht nicht die Liste des Körpers.

    **Befund Robert, 18.09.2026:** „bei einer kante zu viele optionen die
    sinnlos bei kanten sind". Der Kantenklick setzt die Baumauswahl auf den
    **Körper** zurück — eine Kante ist kein Merkmal und steht in keiner
    Baumzeile —, und damit stand hier die volle Körperliste: Aushöhlen, Auf
    dem Bett anordnen, Teilen. Was an einer Kante gilt, sind Verrunden, Fase
    und Wulst, und die stehen oben im Merkmalfenster.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.show()

    panel.set_context(1, _availability(1), feature_kind="")
    QApplication.processEvents()
    at_a_body = sum(1 for button in panel._buttons.values() if button.isVisible())
    assert at_a_body > 0, "die Voraussetzung: am Körper steht etwas"

    panel.set_context(1, _availability(1), feature_kind="edge")
    QApplication.processEvents()

    assert not any(button.isVisible() for button in panel._buttons.values())
    assert not panel.search.isVisible(), "und kein Feld, das zum Suchen einlädt"
    assert "bei den Maßen" in panel._nothing.text()
    assert not panel.catalog_button.isVisible(), "ein Baustein sitzt nicht auf einer Kante"


def test_the_search_field_goes_with_the_list_it_searches(qt_app: QApplication) -> None:
    """Kein Suchfeld über einer Liste, die leer ist und leer bleibt.

    **Befund Robert, 18.09.2026:** „weitere Optionen durchsuchen steht da,
    wenn es keine Operationen für die Auswahl gibt". Wer **sucht** und nichts
    findet, behält es — dort ist das Feld die Ursache und der Weg zurück.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.show()

    panel.set_context(1, _availability(1), feature_kind="")
    QApplication.processEvents()
    assert panel.search.isVisible()

    panel.search.setText("wortdasnichtvorkommt")
    QApplication.processEvents()
    assert panel.search.isVisible(), "wer sucht, behält sein Feld"
    assert "anderes Wort" in panel._nothing.text()


def test_the_draft_stands_on_the_body_and_at_a_face_but_not_at_a_hole(qt_app: QApplication) -> None:
    """P6.4: Die Formschräge gilt dem ganzen Körper (alle Wände) und einer gewählten Fläche.

    Mit ``applies_to=("face",)`` allein verschwände sie aus der Körperstufe —
    dort stand sie seit je (``also_on_body``). An einer Bohrung hat sie nichts
    zu tun, und einen zweiten Knopf bekommt sie nicht.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    assert "draft_faces" in panel._buttons
    in_the_list = [
        str(button.property("operationName"))
        for _section, _toggle, buttons in panel._groups.values()
        for button in buttons
    ]
    assert in_the_list.count("draft_faces") <= 1, "ein Knopf, nicht zwei"
    panel.set_context(1, _availability(1))
    assert panel._fits_the_level("draft_faces")
    panel.set_context(1, _availability(1), feature_kind="face")
    assert panel._fits_the_level("draft_faces")
    panel.set_context(1, _availability(1), feature_kind="hole")
    assert not panel._fits_the_level("draft_faces")


def test_the_groups_follow_the_menu_bar_in_every_language(qt_app: QApplication) -> None:
    """RM-506: Die Karte ordnet ihre Gruppen wie die Menüleiste, nicht nach dem Titel.

    Sortiert wurde nach ``str.casefold`` des übersetzten Titels: Auf Deutsch
    stand „Ändern“ mit 32 Einträgen am Ende, und jede Sprache hatte ihre eigene
    Folge. Jetzt gilt ``MENU_GROUPS`` — dieselbe Folge in allen sechs Sprachen —,
    und eine Kategorie, die das Menü faltet, ist eine eigene Gruppe, so dass
    keine Gruppe am Körper mehr als zwölf Einträge zeigt.
    """
    from app.core.registry import MENU_GROUPS, folded_categories
    from app.i18n import set_language
    from app.i18n.catalog import available_languages, install_language

    load_operations()

    def menu_order(panel: SelectionOperationsPanel) -> list[tuple[int, int]]:
        order = []
        for _section, _toggle, buttons in panel._groups.values():
            name = str(buttons[0].property("operationName"))
            category = REGISTRY.get(name).category
            group = next(
                index for index, (_t, members) in enumerate(MENU_GROUPS) if category in members
            )
            folded = int(category in folded_categories(category))
            order.append((group, folded))
        return order

    orders = {}
    try:
        for language in available_languages():
            install_language(language)
            set_language(language)
            panel = SelectionOperationsPanel(REGISTRY.all())
            orders[language] = menu_order(panel)
            assert orders[language] == sorted(orders[language]), (
                f"{language}: Gruppen nicht in der Folge der Menüleiste"
            )
    finally:
        set_language("de")
    assert len({tuple(order) for order in orders.values()}) == 1, "jede Sprache gleich"

    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.show()
    panel.set_context(1, _availability(1))
    QApplication.processEvents()
    for title, (section, _toggle, buttons) in panel._groups.items():
        shown = sum(1 for button in buttons if not button.isHidden())
        if not section.isHidden():
            assert shown <= OPEN_UP_TO, f"{title}: {shown} Einträge am Körper"


def test_a_hole_offers_the_matching_parts(qt_app: QApplication) -> None:
    """RM-506 (Robert, 05.10.2026): An einer Bohrung *Passende Bausteine …*.

    Derselbe Knopf wie *Bausteine*, aber er öffnet den Katalog gefiltert auf
    das, was dort ansetzt; an einer Kante steht er weiter nicht.
    """
    from app.i18n import tr

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.show()
    asked: list[str] = []
    opened: list[bool] = []
    panel.matchingPartsRequested.connect(asked.append)
    panel.catalogRequested.connect(lambda: opened.append(True))

    panel.set_context(1, _availability(1), feature_kind="hole")
    QApplication.processEvents()
    assert panel.catalog_button.isVisible()
    assert panel.catalog_button.text() == tr("Passende Bausteine …")
    panel.catalog_button.click()
    assert asked == ["hole"] and not opened

    panel.set_context(1, _availability(1), feature_kind="face")
    QApplication.processEvents()
    assert panel.catalog_button.text() == tr("Bausteine")
    panel.catalog_button.click()
    assert opened == [True] and asked == ["hole"], "an der Fläche der ganze Katalog"


def test_no_hit_offers_to_search_every_function(qt_app: QApplication) -> None:
    """RM-506: Ohne Treffer führt ein Knopf in die Befehlspalette, mit demselben Wort.

    Die Suche der Karte kennt nur, was zur Auswahl passt; wer „gewinde“ an
    einem Körper sucht, fand nichts, obwohl es das gibt.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.show()
    wanted: list[str] = []
    panel.paletteRequested.connect(wanted.append)
    panel.set_context(1, _availability(1))
    panel.search.setText("wortdasnichtvorkommt")
    QApplication.processEvents()
    assert panel._everywhere.isVisible(), "kein Treffer: der Weg in alle Funktionen"
    panel._everywhere.click()
    assert wanted == ["wortdasnichtvorkommt"]
    panel.search.setText("")
    QApplication.processEvents()
    assert not panel._everywhere.isVisible(), "mit Treffern steht er nicht"


def test_the_list_stands_in_two_columns_where_every_title_fits(qt_app: QApplication) -> None:
    """RM-510: Flache Zeilen, und wo die Karte breit genug ist, zu zweit.

    Robert, 05.10.2026: die rechte Karte breiter machen „und es dann auch
    sinnvoll nutzen“. Zweispaltig wird nur eine Gruppe, deren Titel alle
    ungebrochen in die halbe Breite passen; in einer schmalen Karte bleibt
    jede einspaltig.
    """
    from app.ui.selection_operations import LIST_ROW_HEIGHT

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(900, 900)
    panel.show()
    panel.set_context(1, _availability(1))
    QApplication.processEvents()
    shown = [title for title, (section, _t, _b) in panel._groups.items() if not section.isHidden()]
    assert shown, "ohne Gruppen prüft der Test nichts"
    assert any(panel.columns_of(title) == 2 for title in shown), "breit: zu zweit"
    rows = [
        button
        for _s, _t, buttons in panel._groups.values()
        for button in buttons
        if not button.isHidden()
    ]
    assert all(button.objectName() == "operationRow" for button in rows), "flache Zeilen"
    assert all(button.minimumHeight() == LIST_ROW_HEIGHT for button in rows)

    panel.resize(240, 900)
    QApplication.processEvents()
    assert all(panel.columns_of(title) == 1 for title in shown), "schmal: untereinander"


def test_filament_waits_folded_below_the_list(qt_app: QApplication) -> None:
    """RM-510: Filament und Druck stehen zugeklappt unter der Liste, nicht vor ihr.

    Vor *Bohrung setzen* standen zehn Bedienelemente und 44 Wörter zu Filament
    und Nahtschutz. Der Abschnitt steht nur, solange etwas in ihm steht, und
    zugeklappt nennt er die Zuweisung.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.show()
    assert panel.print_section.isHidden(), "leer steht keine Klappe"
    picker = QWidget()
    panel.add_print_widget(picker)
    QApplication.processEvents()
    assert not panel.print_section.isHidden()
    layout = panel.layout()
    assert layout is not None
    assert layout.indexOf(panel.print_section) > layout.indexOf(panel.scroller), "unter der Liste"
    panel.describe_print("Im Projekt: PLA Rot")
    summary = panel.print_section.findChild(QLabel, "sectionSummary")
    assert summary is not None and summary.text() == "Im Projekt: PLA Rot"
    picker.hide()
    QApplication.processEvents()
    assert panel.print_section.isHidden(), "ohne Inhalt geht die Klappe mit"


def test_the_operation_list_asks_for_the_height_of_its_visible_buttons(
    qt_app: QApplication,
) -> None:
    """Die Liste verlangt, was ihre sichtbaren Knöpfe brauchen, nicht den Aufbaustand (RM-232).

    ``QScrollArea.sizeHint`` merkt sich die Wunschhöhe des Inhalts beim ersten
    Fragen; beim Aufbau stehen alle Handlungen da. An einer Bohrung sind es
    drei Knöpfe, und die Liste verlangte weiter 24 Zeilen: Zusammen mit dem
    Merkmalfenster stand der Inhalt des Auswahlfensters an der Kante seines
    Sichtfelds, und der Rollbalken sprang an und brach alle Texte neu um.

    Seit RM-510 ohne eigene Grenze: Die Karte deckelt am Fenster, und eine
    lange Liste rollt erst dann in sich.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(244, 900)
    panel.show()
    panel.set_context(1, _availability(1))
    QApplication.processEvents()
    body = panel.scroller.sizeHint().height()
    content = panel.scroller.widget()
    assert content is not None
    assert body >= content.sizeHint().height(), "am Körper wünscht die Liste alle Knöpfe"

    panel.set_context(1, _availability(1), feature_kind="hole", label="Platte · Bohrung 1")
    QApplication.processEvents()
    wanted = panel.scroller.sizeHint().height()
    assert wanted >= content.sizeHint().height(), "die Wunschhöhe folgt den sichtbaren Knöpfen"
    assert wanted < body, "an einer Bohrung stehen weniger Knöpfe als am Körper"


def test_auto_split_stands_with_the_other_ways_to_split(qt_app: QApplication) -> None:
    """*Automatisch teilen* steht am Körper unter *Vorbereiten*, nicht unter *Bearbeiten* (RM-507).

    Der Ablauf ist kein Registereintrag; die Karte trägt ihn über die Aktion
    des Fensters: dieselbe Freigabe, derselbe Grund, derselbe Klick. An einem
    Merkmal und ohne Auswahl steht er nicht da.
    """
    from PySide6.QtGui import QAction

    from app.ui.selection_operations import _category_group

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    action = QAction("Automatisch teilen …", panel)
    action.setToolTip("Ein zu großes Teil zerschneiden.")
    fired: list[bool] = []
    action.triggered.connect(lambda: fired.append(True))
    panel.add_window_action("auto_split", "prepare", action)
    _rank, group = _category_group("prepare")
    row = panel._buttons["auto_split"]
    assert row in panel._groups[group][2], "die Zeile steht in der Gruppe der Teilen-Wege"

    panel.set_context(1, _availability(1))
    assert row.isVisibleTo(panel) and row.isEnabled()
    row.click()
    assert fired == [True], "der Klick löst dieselbe Aktion aus wie Palette und Kürzel"

    action.setEnabled(False)
    action.setToolTip("Dafür muss ein Körper ausgewählt sein.")
    panel.set_context(1, _availability(1))
    assert not row.isEnabled() and row.toolTip() == action.toolTip(), "Sperre und Grund"

    action.setEnabled(True)
    panel.set_context(1, _availability(1), feature_kind="face")
    assert not row.isVisibleTo(panel), "an einer Fläche gilt er nicht"
    panel.set_context(0, _availability(0))
    assert not row.isVisibleTo(panel), "ohne Auswahl auch nicht"
    # Ohne Gruppe sagt die Karte nein, und das Fenster legt die Aktion ins Menü.
    assert not panel.add_window_action("anders", "keine_kategorie", action)
