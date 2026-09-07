"""Das kontextsensitive Operationsfeld der rechten Spalte."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY, catalogue_operations, needed_inputs
from app.ui.selection_operations import (
    QUICK_BODIES,
    QUICK_BODY,
    QUICK_FEATURE,
    QUICK_FEATURES,
    SelectionOperationsPanel,
    all_quick_names,
    body_operations,
    feature_operations,
    quick_names,
)
from app.ui.style import TARGET_SIZE


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
    assert all(spec.category != "parts" for spec in specs)
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
        for _heading, buttons in panel._groups.values()
        for button in buttons
    }
    for name in all_quick_names():
        assert name in panel._quick_buttons, f"{name} steht in keiner Lage als Knopf da"
        assert name not in in_the_list, f"{name} stünde oben und in der Liste"

    lagen = {
        (1, ""): QUICK_BODY,
        (2, ""): QUICK_BODIES,
        (5, ""): QUICK_BODIES,
        (1, "face"): QUICK_FEATURES["face"],
        (1, "hole"): QUICK_FEATURES["hole"],
        (1, "edge_loop"): QUICK_FEATURES["edge_loop"],
        # Eine Art ohne eigene Zeile bekommt die generischen
        # Merkmalshandlungen — **solange das Register sie dort anbietet.**
        # Gemessen am 07.09.2026 trägt `pin` sieben Operationen und `sphere`
        # vier, die drei generischen sind darunter.
        (1, "pin"): QUICK_FEATURE,
        (1, "sphere"): QUICK_FEATURE,
        # **Und eine Art, die das Register gar nicht kennt, bekommt nichts.**
        # `applies_to` nennt sechs Arten, die Erkennung liefert mehr: Torus,
        # Verrundung und Gewinde haben null Operationen. Vorher standen dort
        # drei Knöpfe, hinter denen keine einzige lag — und weil
        # `feature_requirement` fragt, ob **der Körper** ein solches Merkmal
        # hat, waren sie auf einem Körper mit Bohrung sogar bedienbar und
        # hätten auf ein anderes Merkmal gewirkt.
        (1, "torus"): (),
        (1, "fillet"): (),
        (1, "thread"): (),
    }
    for (bodies, kind), wanted in lagen.items():
        assert quick_names(bodies, kind) == wanted
        panel.set_context(
            bodies, _availability(bodies), feature_chosen=bool(kind), feature_kind=kind
        )
        shown = tuple(
            name for name, button in panel._quick_buttons.items() if not button.isHidden()
        )
        assert set(shown) == set(wanted), f"{bodies} Körper, {kind or 'kein'} Merkmal: {shown}"

    # **Das Merkmal hat Vorrang vor der Menge.** Wer eine Bohrung angeklickt
    # hat, meint sie und nicht den Körper darunter.
    assert quick_names(2, "hole") == QUICK_FEATURES["hole"]


def test_selection_changes_update_in_place_and_explain_disabled_actions(
    qt_app: QApplication,
) -> None:
    """Eine große Registerliste wird bei jedem Klick nur nachgeführt."""
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, 340)
    panel.show()
    identities = {name: id(button) for name, button in panel._buttons.items()}

    panel.set_context(2, _availability(1), feature_chosen=False)
    joining = panel._buttons["union_objects"]
    panel.set_context(1, _availability(1), feature_chosen=False)
    assert not panel.isHidden()
    assert panel.summary.text() == "1 Objekt gewählt"
    assert not joining.isEnabled()
    assert "2 Körper" in joining.toolTip()
    assert not panel.feature_button.isEnabled()

    panel.set_context(2, _availability(2), feature_chosen=True)
    QApplication.processEvents()
    assert identities == {name: id(button) for name, button in panel._buttons.items()}
    assert joining.isEnabled()
    assert panel.feature_button.isEnabled()
    assert panel.summary.text() == "2 Objekte gewählt"
    for name in QUICK_BODIES:
        button = panel._buttons[name]
        assert button.width() >= button.sizeHint().width(), f"{button.text()} ist abgeschnitten"
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus

    panel.set_context(0, _availability(0), feature_chosen=False)
    assert panel.isHidden()


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

    panel.set_context(1, _availability(1), feature_chosen=False)
    am_koerper_sichtbar = sichtbar()
    assert not am_koerper_sichtbar & am_merkmal, (
        "an einem Körper hat eine Merkmalshandlung nichts zu suchen"
    )

    panel.set_context(1, _availability(1), feature_chosen=True, feature_kind="face")
    an_der_flaeche = sichtbar()
    assert "arrange_bed" not in an_der_flaeche, (
        "eine Fläche wird nie auf dem Bett angeordnet — der Knopf verschwindet"
    )
    assert not an_der_flaeche & am_koerper, "an einer Fläche steht keine Körperhandlung"

    # Und der Weg zurück: die Stufe wechselt, die Knöpfe kommen wieder. Sie
    # verschwinden beim Wechsel der Stufe, nicht beim zufälligen Klick.
    panel.set_context(1, _availability(1), feature_chosen=False)
    assert sichtbar() == am_koerper_sichtbar

    # **Die fehlende Vorbedingung bleibt dagegen stehen.** Eine Handlung, die
    # zwei Körper braucht, ist bei einem grau und nennt den Grund — der Kunde
    # kann ihn erfüllen, und der Grund führt ihn hin. Genommen wird sie aus
    # der Liste und nicht aus den Hauptaktionen: Dort entscheidet
    # ``quick_names``, welche Zeile überhaupt oben steht.
    zweisam = [name for name in am_koerper_sichtbar if needed_inputs(REGISTRY.get(name)) > 1]
    assert zweisam, "kein Fall für die erfüllbare Vorbedingung im Register gefunden"
    for name in zweisam:
        button = panel._buttons[name]
        assert not button.isHidden(), f"{name}: eine erfüllbare Vorbedingung verschwindet nicht"
        assert not button.isEnabled(), f"{name}: sie bleibt aber grau"
        assert "Körper" in button.toolTip(), f"{name}: und sie nennt den Grund"


def test_the_summary_says_what_is_chosen_not_how_many(qt_app: QApplication) -> None:
    """Der zweite Nachweis zu P5: die Zeile nennt die Tiefe (Konzept B).

    „1 Objekt gewählt" stand auch über Merkmalshandlungen — es nannte die
    Körperzahl, während die Knöpfe darunter dem Merkmal galten. Bei mehreren
    Körpern bleibt die Menge die richtige Antwort: einen Namen gibt es dort
    nicht.
    """
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())

    panel.set_context(1, _availability(1), feature_chosen=False, label="Halter")
    assert panel.summary.text() == "Halter"

    panel.set_context(
        1, _availability(1), feature_chosen=True, feature_kind="face", label="Halter · Oberseite"
    )
    assert panel.summary.text() == "Halter · Oberseite"

    panel.set_context(2, _availability(2), feature_chosen=False, label="Halter")
    assert panel.summary.text() == "2 Objekte gewählt", "bei zweien gibt es keinen einen Namen"

    # Ohne Namen bleibt es bei der Menge — das Panel erfindet keinen.
    panel.set_context(1, _availability(1), feature_chosen=False)
    assert panel.summary.text() == "1 Objekt gewählt"


def test_search_filters_existing_buttons_and_a_click_carries_the_register_entry(
    qt_app: QApplication,
) -> None:
    """Suche und Klick bleiben am vorhandenen Registereintrag."""
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(2, _availability(2), feature_chosen=False)
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
    panel.set_context(2, _availability(2), feature_chosen=True)
    panel.show()
    qt_app.processEvents()

    for name in QUICK_BODIES:
        assert panel._buttons[name].height() >= TARGET_SIZE
    assert panel.search.height() >= TARGET_SIZE
    assert panel.catalog_button.height() >= TARGET_SIZE
