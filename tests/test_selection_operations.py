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
    scene_creators,
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
    """Am Baustein stehen keine Flächenhandlungen seiner Einzelmerkmale — aber
    das Suchfeld steht, wie an jeder Auswahl (RM-735, Entscheidung Robert
    11.10.2026). Bis dahin war die Karte dort ganz verborgen."""
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(1, _availability(1), feature_kind="face", part_selected=True)
    assert not panel.isHidden() and not panel.search.isHidden(), "das Feld steht"
    assert not any(panel._fits_the_level(name) for name in panel._buttons), "keine Handlung"
    assert not panel._nothing.isHidden(), "der Satz sagt, wo die Handlungen stehen"
    assert panel.catalog_button.isHidden()
    panel.set_context(1, _availability(1), feature_kind="face")
    assert any(panel._fits_the_level(name) for name in panel._buttons)


def test_a_part_thread_keeps_only_the_pin_in_the_card(qt_app: QApplication) -> None:
    """Am Innengewinde eines Bausteins steht genau *Stift für Bohrung* (RM-536, Robert 07.10.2026).

    Am Außengewinde nimmt ``not_offered_at`` den Stift weg, und mit ihm steht in
    der Karte keine Handlung mehr — nur noch das Suchfeld (RM-735).
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
    assert not any(panel._fits_the_level(name) for name in panel._buttons)
    assert not panel.search.isHidden()
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
    Darstellung, und der Knopf daneben führt hin. Die Erzeuger stehen seit
    RM-735 auf der Stufe ohne Auswahl (:func:`scene_creators`).
    """
    load_operations()
    specs = (
        body_operations(REGISTRY.all())
        + feature_operations(REGISTRY.all())
        + scene_creators(REGISTRY.all())
    )
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


def _hit_names(panel: SelectionOperationsPanel) -> list[str]:
    """Die Namen der Treffer in ihrer Reihenfolge — ohne die Kopfzeile der Lockerung."""
    names = [
        panel.hits.item(row).data(Qt.ItemDataRole.UserRole) for row in range(panel.hits.count())
    ]
    return [name for name in names if isinstance(name, str)]


def test_the_search_finds_customer_words_and_names_what_another_choice_needs(
    qt_app: QApplication,
) -> None:
    """„löschen“ findet *Objekt entfernen*, „verschmelzen“ nennt, was *Vereinigen* braucht.

    Fragebogen zu 0.5.3: Ein Anfänger fand weder das Löschen noch das
    Vereinigen. Die Suche der Karte rechnet wie die Befehlspalette, die sie seit
    RM-735 ersetzt. Ein Treffer, der an dieser Auswahl nicht geht, steht mit
    seinem Sperrgrund da und ist nicht wählbar — im Fenster der Satz, der sagt,
    wie das zweite Objekt dazukommt. Ohne Treffer führt ein Knopf ins Handbuch.
    """
    from app.i18n import tr

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(1, _availability(1))

    panel.search.setText("löschen")
    assert _hit_names(panel)[0] == "delete_object", "Kundenwort ohne Titeltreffer"
    assert panel._nothing.isHidden() and panel.scroller.isHidden(), "die Treffer statt der Karte"

    panel.search.setText("verschmelzen")
    assert _hit_names(panel)[0] == "union_objects"
    row = panel.hits.item(panel.hits.currentRow())
    assert row.data(Qt.ItemDataRole.UserRole) == "union_objects", "vorgewählt"
    assert not row.flags() & Qt.ItemFlag.ItemIsEnabled, "gesperrt, nicht wählbar"
    assert "Dafür müssen 2 Körper ausgewählt sein." in row.text(), "der Grund steht in der Zeile"

    panel.search.setText("xyzzy")
    assert panel._nothing.text() == tr("Kein Treffer — versuchen Sie ein anderes Wort.")
    assert not panel._manual.isHidden(), "der Weg ins Handbuch"
    asked: list[str] = []
    panel.manualRequested.connect(asked.append)
    panel._manual.click()
    assert asked == ["xyzzy"], "mit demselben Wort"

    panel.search.setText("")
    assert panel.hits.isHidden() and not panel.scroller.isHidden(), "ohne Text die Karte"
    panel.set_context(2, _availability(2))
    panel.search.setText("verschmelzen")
    row = panel.hits.item(panel.hits.currentRow())
    assert row.flags() & Qt.ItemFlag.ItemIsEnabled, "bei zwei Körpern geht *Vereinigen*"


def test_a_locked_window_command_stands_with_its_reason(qt_app: QApplication) -> None:
    """Die Befehle des Fensters stehen in derselben Suche, gesperrte mit ihrem Grund.

    Sie kommen vom Fenster (:meth:`SelectionOperationsPanel.set_search_sources`),
    mit Freigabe und Grund aus derselben Aktion, die auch das Menü ausgraut.
    Return auf einer gesperrten Zeile läuft an die Wache des Fensters weiter,
    die den Grund in die Statuszeile setzt; Text und Fokus bleiben.
    """
    from app.core.registry import SearchEntry

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    reason = "Das Teil passt schon auf das Bett."
    command = SearchEntry(
        name="edit.auto_split",
        title="Automatisch teilen …",
        doc="",
        category="edit",
        available=False,
        reason=reason,
    )
    panel.set_search_sources(lambda: [command], lambda _name, declared: declared, frozenset())
    panel.set_context(1, _availability(1))
    chosen: list[str] = []
    panel.searchChosen.connect(chosen.append)

    panel.search.setText("automatisch teilen")
    assert _hit_names(panel)[0] == "edit.auto_split"
    row = panel.hits.item(panel.hits.currentRow())
    assert reason in row.text() and not row.flags() & Qt.ItemFlag.ItemIsEnabled
    panel._choose_item(row)
    assert chosen == ["edit.auto_split"], "die Wache des Fensters sagt den Grund"
    assert panel.search.text() == "automatisch teilen", "Text und Fokus bleiben"


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
    # Robert, 18.09.2026), **für die Handlungen, die alle Körper nehmen**
    # (Robert, 27.09.2026), seit RM-735 alle drei, **und für die Erzeuger**, die
    # bis dahin nur im Menü standen — mit dem Suchfeld über alles (Entscheidung
    # Robert, 11.10.2026).
    panel.set_context(0, _availability(0))
    QApplication.processEvents()
    assert not panel.isHidden()
    assert panel.search.isVisible(), "das Suchfeld steht immer"
    assert panel.catalog_button.isVisible(), "der Weg zu den Bausteinen bleibt"
    for_all = {spec.name for spec in body_operations(REGISTRY.all()) if spec.takes_whole_scene}
    assert {"orient_for_print", "arrange_bed", "check_collisions"} <= for_all
    creators = {spec.name for spec in scene_creators(REGISTRY.all())}
    assert {"create_brep_cone", "create_label", "load_step"} <= creators
    shown = {name for name, button in panel._buttons.items() if button.isVisible()}
    # ``load`` steht am Fenster als Befehl *Modell einfügen …*
    # (``test_the_window_command_takes_the_place_of_its_operation``); die Karte
    # allein kennt nur die Operation.
    assert shown == for_all | creators, shown


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
    # Schmal, aber nicht schmaler als der ungebrochene *Bausteinkatalog …*
    # darunter: Er setzt die Mindestbreite der Karte mit Absicht
    # (``test_a_button_wraps_its_label_instead_of_cutting_it``); geprüft wird
    # hier, dass die Zweierspalte nichts dazulegt.
    margins = panel.layout().contentsMargins()
    narrow = max(
        216, panel.catalog_button.minimumSizeHint().width() + margins.left() + margins.right()
    )
    panel.resize(narrow, 500)
    QApplication.processEvents()
    assert first.y() < second.y()
    assert panel.width() == narrow
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
    ``_operation_availability`` die Körperauswahl fragt und ein gewähltes
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

    **Alle drei stehen da** (RM-735): *Auf dem Bett anordnen* gab es bis dahin
    nur per Kürzel, *Überschneidungen prüfen* nur in der Befehlspalette, die
    mit RM-735 gefallen ist. Daneben die Erzeuger (:func:`scene_creators`).
    """
    load_operations()
    every = {spec.name for spec in body_operations(REGISTRY.all()) if spec.takes_whole_scene}
    assert {"orient_for_print", "arrange_bed", "check_collisions"} <= every
    creators = {spec.name for spec in scene_creators(REGISTRY.all())}
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, 520)
    panel.show()

    def shown() -> set[str]:
        qt_app.processEvents()
        return {name for name, button in panel._buttons.items() if button.isVisible()}

    panel.set_context(0, _availability(0))
    assert shown() == every | creators
    assert panel.chosen_level() == "scene"
    assert panel._nothing.isHidden(), "die Gruppenköpfe sagen, was dasteht"
    assert panel.search.isVisible(), "das Suchfeld steht immer"

    panel.set_context(1, _availability(1))
    assert not shown() & (every | creators), "am gewählten Körper steht keine Handlung für alle"
    panel.set_context(1, _availability(1), feature_kind="face")
    assert not shown() & (every | creators), "an einer Fläche auch nicht"

    # Ein Suchtext bleibt über den Stufenwechsel stehen und sucht weiter —
    # das Feld ist sichtbar, man sieht, warum die Karte zurücktritt.
    panel.set_context(1, _availability(1))
    panel.search.setText("wortdasnichtvorkommt")
    panel.set_context(0, _availability(0))
    assert panel.scroller.isHidden() and not panel._manual.isHidden()
    panel.search.setText("")
    assert shown() == every | creators

    # Ist alles gesperrt, nennt der Satz den Grund, statt Handlungen zuzusagen.
    panel.set_context(0, lambda _name: (False, "Die Lizenz ist abgelaufen."))
    assert not shown()
    assert panel._nothing.text() == "Die Lizenz ist abgelaufen."


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


def _card(panel: SelectionOperationsPanel) -> tuple[set[str], dict[str, bool], dict[str, bool]]:
    """Was die ruhende Karte zeigt: Knöpfe, aufgeklappte und stehende Gruppen."""
    return (
        {name for name, button in panel._buttons.items() if not button.isHidden()},
        {title: toggle.isChecked() for title, (_section, toggle, _b) in panel._groups.items()},
        {title: not section.isHidden() for title, (section, _t, _b) in panel._groups.items()},
    )


def test_the_card_rests_while_searching_and_comes_back_at_the_new_level(
    qt_app: QApplication,
) -> None:
    """Bei Suchtext ruht die Karte; nach dem Leeren steht sie für die Auswahl von jetzt.

    Seit RM-735 tritt sie bei Suchtext hinter die Trefferliste zurück, und
    ``_filter`` rechnet ihre Gruppen dann nicht nach — das spart jeden
    Tastendruck. Ändert sich die Auswahl während der Suche, muss das Leeren des
    Felds die Karte der neuen Stufe zeigen, als wäre nie gesucht worden. Ein
    Klick auf einen ihrer Knöpfe trägt den Registereintrag.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(2, _availability(2))
    # **Aus den sichtbaren**, seit die Sichtbarkeit der Auswahlstufe folgt
    # (Konzept C): Ohne diese Bedingung fiel die Wahl auf eine
    # Merkmalshandlung, die an zwei gewählten Körpern gar nicht dasteht.
    extra = next(
        button
        for name, button in panel._buttons.items()
        if name not in panel._quick_buttons and button.isEnabled() and not button.isHidden()
    )
    received = []
    panel.operationRequested.connect(received.append)
    extra.click()
    assert [entry.name for entry in received] == [str(extra.property("operationName"))]
    at_two = _card(panel)

    panel.search.setText(str(extra.property("operationTitle") or extra.text()))
    qt_app.processEvents()
    assert str(extra.property("operationName")) in _hit_names(panel)
    assert panel.scroller.isHidden() and not panel.hits.isHidden()

    panel.set_context(1, _availability(1), feature_kind="face")
    panel.search.clear()
    qt_app.processEvents()
    fresh = SelectionOperationsPanel(REGISTRY.all())
    fresh.set_context(1, _availability(1), feature_kind="face")
    assert _card(fresh) != at_two, "sonst prüft der Stufenwechsel nichts"
    assert _card(panel) == _card(fresh)
    assert not panel.scroller.isHidden() and panel.hits.isHidden()


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
    """*Bausteinkatalog …* ist ein Hauptknopf: Akzentfarbe **und** halbfett (Regel 18).

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
    zugeklappt hatte — seit RM-735 in der Trefferliste, die bei Suchtext an die
    Stelle der Gruppen tritt.
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
    _title, shown = next(iter(folded.items()))
    wanted = shown[0]
    panel.search.setText(str(wanted.property("operationTitle") or wanted.text()))
    qt_app.processEvents()
    assert panel.hits.isVisibleTo(panel) and not panel.scroller.isVisibleTo(panel)
    assert str(wanted.property("operationName")) in _hit_names(panel), "der Treffer steht da"


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
    Karte wird nie schmaler als ihr breitestes ungebrochenes Element (der
    Katalogknopf, *Bausteinkatalog …* oder *Passende Bausteine …*). Unter
    Windows offscreen ist die Ersatzschrift so breit, dass der Titel dort
    trotzdem nicht passte; unter Linux und macOS rechnet offscreen mit der
    echten Schrift, und dort passt er in die schmalste Karte — ein Umbruch
    wäre falsch. Zugesichert wird deshalb auf jeder Plattform dasselbe: An
    der schmalsten Karte ist keine Zeile beschnitten, und auf einen Platz,
    der nur das längste Wort fasst, bricht der Titel vollständig in zwei
    Zeilen um.
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
    assert panel.search.isVisible(), "das Suchfeld sucht auch hier über alles"
    assert "bei den Maßen" in panel._nothing.text()
    assert not panel.catalog_button.isVisible(), "ein Baustein sitzt nicht auf einer Kante"


@pytest.mark.parametrize(
    ("selected", "kind"),
    [(0, ""), (1, ""), (2, ""), (1, "edge"), (1, "slot"), (1, "fillet"), (1, "hole")],
)
def test_the_search_field_stands_at_every_level(
    qt_app: QApplication, selected: int, kind: str
) -> None:
    """Das Suchfeld steht immer — ohne Auswahl, an jedem Merkmal, an einer Kante.

    Entscheidung Robert, 11.10.2026 (RM-735): Es ersetzt die Befehlspalette und
    sucht über alles, also auch dort, wo die Karte selbst nichts anbietet. Das
    hebt die frühere Entscheidung auf, nach der es mit einer leeren Liste
    verschwand (Befund Robert, 18.09.2026: „weitere Optionen durchsuchen steht
    da, wenn es keine Operationen für die Auswahl gibt") — damals versprach es
    nur die Handlungen dieser Auswahl. Und es findet von dort aus auch, was an
    einer anderen Stufe steht.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.show()

    panel.set_context(selected, _availability(selected), feature_kind=kind)
    QApplication.processEvents()
    assert panel.search.isVisible()

    panel.search.setText("Quader")
    QApplication.processEvents()
    assert "create_brep_box" in _hit_names(panel) or "create_box" in _hit_names(panel)

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

    Derselbe Knopf wie *Bausteinkatalog …*, aber er öffnet den Katalog gefiltert auf
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
    assert panel.catalog_button.text() == tr("Bausteinkatalog …")
    panel.catalog_button.click()
    assert opened == [True] and asked == ["hole"], "an der Fläche der ganze Katalog"


def test_the_search_reaches_every_function_and_its_keys_belong_to_it(
    qt_app: QApplication,
) -> None:
    """Die Suche kennt jede Operation jeder Stufe, und Escape, Return und die
    Pfeiltasten gehören dem Feld (RM-735).

    Bis dahin kannte die Karte nur, was zur Auswahl passt: Wer „gewinde“ an
    einem Körper suchte, fand nichts, obwohl es das gibt, und kam erst über
    *In allen Funktionen suchen* in die Befehlspalette. **Escape** war eine
    Fensteraktion und hob an einem Merkmal die Auswahl auf; jetzt leert es das
    Feld und gibt danach den Fokus ab. **Return** führt den vorgewählten
    Treffer aus — vorher Feld leer und Fokus in die Ansicht, damit Strg+Z den
    Schritt zurücknimmt und nicht das Tippen.
    """
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.show()
    panel.set_context(1, _availability(1))
    chosen: list[str] = []
    left: list[bool] = []
    panel.searchChosen.connect(chosen.append)
    panel.searchLeft.connect(lambda: left.append(True))

    def press(key: Qt.Key) -> bool:
        override = QKeyEvent(QEvent.Type.ShortcutOverride, key, Qt.KeyboardModifier.NoModifier)
        assert panel.eventFilter(panel.search, override), f"{key} gehört dem Feld"
        assert override.isAccepted(), "und das Fenster bekommt die Taste nicht"
        event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        return panel.eventFilter(panel.search, event)

    panel.search.setText("gewinde")
    names = _hit_names(panel)
    assert any(name in catalogue_operations() for name in names), "auch die Bausteine"

    # **Mit mehreren Treffern**, sonst kann die Pfeiltaste nicht zeigen, dass
    # sie etwas tut: „duplizieren“ hat einen, und der Test blieb grün, als
    # ``_step_through_hits`` nichts tat (Review RM-735, F3).
    panel.search.setText("drehen")
    assert len(_hit_names(panel)) > 2, _hit_names(panel)
    first = panel.hits.currentRow()
    assert first + 1 < panel.hits.count()
    press(Qt.Key.Key_Down)
    assert panel.hits.currentRow() == first + 1, "die Pfeiltaste bewegt die Wahl"
    press(Qt.Key.Key_Up)
    assert panel.hits.currentRow() == first

    # Über der gelockerten Liste steht eine Kopfzeile; Pfeil hoch bleibt auf
    # dem ersten Treffer und wählt sie nie.
    panel.search.setText("zacken abrunden")
    heading = panel.hits.item(0)
    assert heading.data(Qt.ItemDataRole.UserRole) is None, "keine Lockerung — Test prüft nichts"
    panel.hits.setCurrentRow(1)
    press(Qt.Key.Key_Up)
    assert panel.hits.currentRow() == 1, "die Kopfzeile ist keine Wahl"

    panel.search.setText("duplizieren")
    assert _hit_names(panel)[0] == "duplicate_object"
    assert press(Qt.Key.Key_Return)
    assert chosen == ["duplicate_object"], "Return führt den vorgewählten aus"
    assert panel.search.text() == "" and left == [True], "Feld leer, Fokus in die Ansicht"

    panel.search.setText("drehen")
    press(Qt.Key.Key_Escape)
    assert panel.search.text() == "" and left == [True], "Escape leert erst das Feld"
    press(Qt.Key.Key_Escape)
    assert left == [True, True], "und gibt dann den Fokus ab"


def test_a_new_report_of_the_selection_keeps_the_hit_chosen_by_arrow(
    qt_app: QApplication,
) -> None:
    """Die mit den Pfeiltasten gewählte Zeile bleibt, wenn das Fenster die Lage
    neu meldet — nach jeder fertigen Auswertung (``_update_actions``).

    Bis dahin baute jede Meldung die Liste neu und wählte wieder den ersten
    Treffer; ein Return in diesem Moment startete eine andere Zeile als die
    gewählte (Review RM-735, F7). Ein anderes Wort wählt neu.
    """
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(1, _availability(1))
    panel.search.setText("drehen")
    first = panel.hits.currentRow()
    down = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
    panel.eventFilter(panel.search, down)
    assert panel.hits.currentRow() == first + 1
    picked = panel.hits.currentItem().data(Qt.ItemDataRole.UserRole)

    panel.set_context(1, _availability(1))
    assert panel.hits.currentItem().data(Qt.ItemDataRole.UserRole) == picked, "die Wahl bleibt"

    from app.core.registry.search import first_choice

    panel.search.setText("drehe")
    assert panel.hits.currentRow() == first_choice(panel._hits, "drehe"), (
        "ein anderes Wort wählt neu"
    )


def test_the_preselection_follows_a_new_selection_unless_chosen_by_hand(
    qt_app: QApplication,
) -> None:
    """Die Vorauswahl der Suche rechnet für die neue Auswahl neu — nur eine Wahl
    mit den Pfeiltasten bleibt.

    „hinlegen“ ohne Auswahl wählt *Druckoptimal ausrichten* (ganze Szene) vor;
    wer dann einen Körper wählt, bekommt *Auf das Bett setzen* oben, und Return
    muss diesen Körper hinlegen, nicht die Szene ausrichten. Der Fix zu F7
    hielt auch die selbsttätige Vorauswahl fest (Nachprüfung RM-735, N2).
    """
    from app.core.registry.search import first_choice

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(0, _availability(0))
    panel.search.setText("hinlegen")
    before = panel.hits.currentItem().data(Qt.ItemDataRole.UserRole)
    panel.set_context(1, _availability(1))
    wanted = panel._hits[first_choice(panel._hits, "hinlegen")].name
    assert wanted != before, "die neue Lage wählt nichts anderes — Test prüft nichts"
    assert panel.hits.currentItem().data(Qt.ItemDataRole.UserRole) == wanted


@pytest.mark.parametrize(
    ("language", "kind", "typed", "meant"),
    [
        ("de", "", "Verschieben", {"translate_object"}),
        ("de", "hole", "Verschieben", {"move_feature"}),
        ("de", "face", "Verschieben", {"translate_object"}),
        ("de", "face", "Wandhalter", {"insert_wall_mount"}),
        ("es", "", "Tornillo", {"create_printed_screw", "insert_printed_screw"}),
        ("fr", "", "Vis", {"create_printed_screw", "insert_printed_screw"}),
        ("it", "", "Vite", {"create_printed_screw", "insert_printed_screw"}),
        ("pt", "face", "Parafuso", {"create_printed_screw", "insert_printed_screw"}),
    ],
)
def test_among_equal_hits_the_place_then_the_whole_title_then_the_word_decides(
    qt_app: QApplication, language: str, kind: str, typed: str, meant: set[str]
) -> None:
    """Bei gleicher Güte entscheidet zuerst, was an der Auswahl steht, dann der
    ganze Titel, dann das Kundenwort — nie das Alphabet.

    „Verschieben“ am Körper verschiebt ihn, an der Bohrung das Merkmal. Der ganze
    Titel „Tornillo“ wählt den Baustein *Tornillo*, nicht das *Agujero para
    tornillo*, das spanisch nach dem Alphabet vorn stand; bei zwei Zeilen
    gleichen Titels („Wandhalter“) entscheidet das Kundenwort, nicht der
    Registername (Nachprüfung RM-735, N1).
    """
    from app.i18n import set_language
    from app.i18n.catalog import install_language

    load_operations()
    install_language(language)
    set_language(language)
    try:
        panel = SelectionOperationsPanel(REGISTRY.all())
        panel.set_context(1, _availability(1), feature_kind=kind)
        panel.search.setText(typed)
        chosen = panel.hits.currentItem().data(Qt.ItemDataRole.UserRole)
        assert chosen in meant, f"„{typed}“ ({language}, {kind or 'Körper'}) wählt {chosen}"
    finally:
        install_language("de")
        set_language("de")


def test_return_in_the_hit_list_ends_there(qt_app: QApplication) -> None:
    """Return in der Trefferliste führt aus und läuft nicht an die Vorfahren weiter.

    Im Feld nahm :meth:`_search_key` die Taste schon ab; in der Liste (Tab,
    Klick) meldete Qt die Aktivierung und reichte das Ereignis danach hinauf —
    an den Filter einer laufenden Platzierung in derselben Spalte, der auf
    Return seine Werte übernimmt (Review RM-735, F11).
    """
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QVBoxLayout

    class Spy(QObject):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[str] = []

        def eventFilter(self, _watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
            if event.type() in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride):
                key = getattr(event, "key", lambda: None)()
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self.seen.append(event.type().name)
            return False

    load_operations()
    zone = QWidget()
    QVBoxLayout(zone)
    panel = SelectionOperationsPanel(REGISTRY.all(), zone)
    zone.layout().addWidget(panel)
    spy = Spy()
    zone.installEventFilter(spy)
    zone.show()
    try:
        panel.set_context(1, _availability(1))
        chosen: list[str] = []
        panel.searchChosen.connect(chosen.append)
        panel.search.setText("drehen")
        panel.hits.setFocus()
        QApplication.processEvents()
        QTest.keyClick(panel.hits, Qt.Key.Key_Return)
        QApplication.processEvents()
        assert chosen == ["rotate_object"], chosen
        assert spy.seen == [], f"Return kam beim Vorfahren an: {spy.seen}"
    finally:
        zone.close()
        zone.deleteLater()


def test_an_operation_registered_later_is_found(qt_app: QApplication) -> None:
    """Ein Baustein, der nach dem Bau der Karte ins Register kommt — eingelesen
    oder im Rezeptdialog gespeichert —, steht sofort in der Suche.

    Die Karte fror ihre Operationen beim Bau ein; die Suche sagte bis zum
    Neustart „Kein Treffer“, wo die Palette ihn in 0.6.0 fand (Review RM-735,
    F10). Auch eine schon gebaute Trefferliste rechnet mit dem neuen Stand.
    """
    import dataclasses

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(0, _availability(0))
    panel.search.setText("halter")
    late = dataclasses.replace(
        REGISTRY.get("create_container"), name="late_sample_part", title="Sondenhalter Zebra"
    )
    REGISTRY.register(late)
    try:
        panel.search.setText("Sondenhalter Zebra")
        assert _hit_names(panel)[:1] == ["late_sample_part"], _hit_names(panel)
        panel.set_context(0, _availability(0))
        assert _hit_names(panel)[:1] == ["late_sample_part"], "auch nach einer neuen Lage"
    finally:
        REGISTRY.remove("late_sample_part")


def test_the_window_command_takes_the_place_of_its_operation(qt_app: QApplication) -> None:
    """Ohne Auswahl steht *Modell einfügen …* einmal — als dieselbe Aktion wie in
    Menü und Leiste, nicht als Operation ``load`` mit eigenem Dialog.

    Die Karte zeigte die Operation als Erzeugerknopf: gleicher Name, andere
    Wirkung (Operationsdialog statt Dateiauswahl), gegen „Ein Text, eine
    Wirkung“ (Review RM-735, F8). Die Aktion nimmt den Platz der Operation ein,
    auf ihrer Stufe.
    """
    from PySide6.QtGui import QAction

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, 600)
    panel.show()
    action = QAction("Modell einfügen …", panel)
    triggered: list[bool] = []
    action.triggered.connect(lambda: triggered.append(True))
    assert panel.add_window_action("file.import", "import", action, replaces="load")

    panel.set_context(0, _availability(0))
    QApplication.processEvents()
    shown = {name for name, button in panel._buttons.items() if button.isVisible()}
    assert "load" not in shown and "load" not in panel._buttons, "kein zweiter Weg"
    assert "file.import" in shown, "die Aktion steht auf der Stufe ohne Auswahl"
    panel._buttons["file.import"].click()
    assert triggered == [True], "derselbe Weg wie Menü und Leiste"

    panel.set_context(1, _availability(1))
    QApplication.processEvents()
    assert not panel._buttons["file.import"].isVisible(), "an einer Auswahl nicht"


def test_a_body_with_every_action_locked_says_why(qt_app: QApplication) -> None:
    """Am gewählten Körper, an dem alles gesperrt ist, nennt die Karte den Grund.

    Sie sagte „steht oben bei den Maßen“ — am Körper stehen oben keine
    (Review RM-735, F9). Den Satz zu den Maßen gibt es nur an einer Stufe ohne
    eigene Handlungen.
    """
    from app.i18n import tr

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    reason = "Die Lizenz ist abgelaufen."
    panel.set_context(1, lambda _name: (False, reason))
    assert not panel._nothing.isHidden()
    assert panel._nothing.text() == reason

    panel.set_context(1, _availability(1), feature_kind="face", part_selected=True)
    assert panel._nothing.text() == tr("Was sich hier tun lässt, steht oben bei den Maßen.")


def test_the_hit_list_draws_with_its_own_rows(qt_app: QApplication) -> None:
    """Die Trefferliste zeichnet mit ``_HitRows`` — Kürzel in einer Spalte,
    darunter Satz oder Grund. Mit Qts Zeichner stünde die Taste nach einem
    Tabulator an jeder Zeile woanders (Review RM-735, F4)."""
    from app.ui.selection_operations import _HitRows

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    assert isinstance(panel.hits.itemDelegate(), _HitRows)


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


def test_one_chosen_body_says_how_to_reach_the_boolean_operations(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bei einem gewählten Körper und einem zweiten in der Szene steht eine Zeile,
    wie man zu Vereinigen, Abziehen und Schnittmenge kommt (RM-734).

    Fragebogen zu 0.5.3: „Boolesche Operationen wären toll.“ Es gab sie, aber
    oben stehen sie erst bei zwei gewählten Körpern, und bei einem sagte die
    Karte nichts davon. Reiner Text, kein grauer Knopf (Entscheidung vom
    07.09.2026); die Titel kommen aus dem Register, die Taste je Plattform.
    """
    from PySide6.QtWidgets import QToolButton

    from app import i18n
    from app.ui.labels import adding_key

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())

    def knoepfe() -> int:
        return len(panel.findChildren(QPushButton)) + len(panel.findChildren(QToolButton))

    vorher = knoepfe()
    panel.set_context(1, _availability(1), pairing=True)
    assert not panel.pairing_hint.isHidden(), "ein Körper gewählt, ein zweiter da"
    text = panel.pairing_hint.text()
    for name in QUICK_BODIES:
        assert str(REGISTRY.get(name).title) in text, name
    assert adding_key() in text

    for weg, gewaehlt, weiter in (
        ("kein zweiter Körper oder eine Sperre", 1, {"pairing": False}),
        ("zwei gewählt — die drei stehen oben", 2, {"pairing": True}),
        ("nichts gewählt", 0, {"pairing": True}),
        ("ein Merkmal gewählt", 1, {"pairing": True, "feature_kind": "face"}),
        ("mehrere Merkmalszeilen", 1, {"pairing": True, "features": 2}),
    ):
        panel.set_context(gewaehlt, _availability(gewaehlt), **weiter)
        assert panel.pairing_hint.isHidden(), weg

    monkeypatch.setattr(i18n, "key_platform", lambda: "darwin")
    panel.set_context(1, _availability(1), pairing=True)
    assert "⌘" in panel.pairing_hint.text(), "am Mac die Befehlstaste"
    assert knoepfe() == vorher, "die Zeile ist Text, kein Knopf"


def test_the_window_offers_the_second_body_only_where_there_is_one(qt_app: QApplication) -> None:
    """Das Fenster sagt der Karte, ob sich ein zweiter Körper dazuwählen ließe:
    zwei Körper in der Szene und keine Sperre, die die Booleschen auch mit zweien
    verweigerte (RM-734)."""
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.run_remote("create_box", {"width": 20.0, "depth": 20.0, "height": 20.0})
        assert window.session.wait_for_idle(60_000)
        result = window.session.last_result
        assert result is not None
        first = next(iter(result.scene.objects))
        window.object_tree.select_object(first)
        window._update_actions()
        assert window.selection_operations.pairing_hint.isHidden(), "ein Körper allein"
        # **Und der Grund sagt, was fehlt** (Befund F4, bedienlogik 11.10.2026):
        # Mit einem Körper in der Szene schickte er zum Dazuwählen eines
        # zweiten, den es nicht gibt. Jetzt nennt er den Weg zu einem zweiten.
        usable, reason = window._operation_availability("union_objects")
        assert not usable
        assert str(REGISTRY.get("duplicate_object").title) in reason, reason
        assert "Klick" not in reason, "kein Dazuwählen, wo nichts dazuzuwählen ist"

        window.run_remote("create_box", {"width": 10.0, "depth": 10.0, "height": 10.0})
        assert window.session.wait_for_idle(60_000)
        window.object_tree.select_object(first)
        window._update_actions()
        assert not window.selection_operations.pairing_hint.isHidden(), "ein zweiter steht da"
        assert window._pairing_possible(locked=False, gesturing=False)
        assert not window._pairing_possible(locked=True, gesturing=False), "Lizenzsperre"
        assert not window._pairing_possible(locked=False, gesturing=True), "Formen oder Skelett"
    finally:
        window.wait_for_workers()
