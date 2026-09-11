"""Das kontextsensitive Operationsfeld der rechten Spalte."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.core.perceive.actions import ACTION_ORDER
from app.core.registry import REGISTRY, catalogue_operations, needed_inputs
from app.ui.selection_operations import (
    QUICK_BODIES,
    QUICK_BODY,
    QUICK_FEATURES,
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
        (1, "face"): QUICK_FEATURES["face"],
        (1, "hole"): ("countersink_hole", "plug_hole"),
        (1, "cone"): ("countersink_hole",),
        (1, "edge_loop"): QUICK_FEATURES["edge_loop"],
        # Eine Art ohne eigene Zeile bekommt die generischen
        # Merkmalshandlungen — **solange das Register sie dort anbietet und
        # das Merkmalsfenster sie nicht schon als Feld zeigt.** Alle drei aus
        # :data:`QUICK_FEATURE` stehen in ``ACTION_ORDER`` und damit oben mit
        # ihrem gemessenen Wert; die Zeile bleibt an Stift und Kugel deshalb
        # leer. Gemessen am 09.09.2026: `pin` trägt sieben Operationen, davon
        # fünf als Feld, und die zwei übrigen stehen in der Liste darunter.
        (1, "pin"): (),
        (1, "sphere"): (),
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
        panel.set_context(bodies, _availability(bodies), feature_kind=kind)
        shown = tuple(
            name for name, button in panel._quick_buttons.items() if not button.isHidden()
        )
        assert set(shown) == set(wanted), f"{bodies} Körper, {kind or 'kein'} Merkmal: {shown}"

    # **Das Merkmal hat Vorrang vor der Menge.** Wer eine Bohrung angeklickt
    # hat, meint sie und nicht den Körper darunter.
    assert quick_names(2, "hole") == quick_names(1, "hole")


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
    assert "2 Körper" in joining.toolTip()

    panel.set_context(2, _availability(2))
    QApplication.processEvents()
    assert identities == {name: id(button) for name, button in panel._buttons.items()}
    assert joining.isEnabled()
    assert panel.summary.text() == "2 Objekte gewählt"
    # Der Knopf *Merkmale* ist am 07.09.2026 entfallen (Konzept A): Seit die
    # Maße des Gewählten über diesen Handlungen stehen, führt er nirgendwohin.
    assert not hasattr(panel, "feature_button")
    for name in QUICK_BODIES:
        button = panel._buttons[name]
        assert button.width() >= button.sizeHint().width(), f"{button.text()} ist abgeschnitten"
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus

    panel.set_context(0, _availability(0))
    assert panel.isHidden()


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
    assert not am_koerper_sichtbar & am_merkmal, (
        "an einem Körper hat eine Merkmalshandlung nichts zu suchen"
    )

    panel.set_context(1, _availability(1), feature_kind="face")
    an_der_flaeche = sichtbar()
    assert "arrange_bed" not in an_der_flaeche, (
        "eine Fläche wird nie auf dem Bett angeordnet — der Knopf verschwindet"
    )
    assert not an_der_flaeche & am_koerper, "an einer Fläche steht keine Körperhandlung"

    # Und der Weg zurück: die Stufe wechselt, die Knöpfe kommen wieder. Sie
    # verschwinden beim Wechsel der Stufe, nicht beim zufälligen Klick.
    panel.set_context(1, _availability(1))
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

    panel.set_context(1, _availability(1), feature_kind="face", label="Halter · Oberseite")
    assert panel.summary.text() == "Halter · Oberseite"

    panel.set_context(2, _availability(2), label="Halter")
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

    **Gemessen wird relativ, nicht absolut.** Offscreen gibt es keine echte
    Schrift; welche Zahl „passt" bedeutet, sagt deshalb dieselbe
    ``fontMetrics``, mit der auch gezeichnet wird — der Test rechnet die
    Prüfbreiten daraus aus, statt eine Bildpunktzahl zu behaupten.
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

    # Zu schmal für den Titel, breit genug für sein längstes Wort: zwei Zeilen,
    # und keine davon breiter als der Platz.
    panel.resize(laengstes + beiwerk + 4 * NORMAL, 600)
    qt_app.processEvents()
    gebrochen = knopf.text()
    for _ in range(4):
        panel._wrap_labels()
        assert knopf.text() == gebrochen
    assert "\n" in gebrochen, f"hier muss umgebrochen werden: {gebrochen!r}"
    assert gebrochen.replace("\n", " ") == titel, f"der Titel bleibt vollständig: {gebrochen!r}"
    for zeile in gebrochen.split("\n"):
        assert metrics.horizontalAdvance(zeile) <= laengstes, (
            f"die Zeile {zeile!r} ist breiter als das längste Wort — dann wird sie beschnitten"
        )
