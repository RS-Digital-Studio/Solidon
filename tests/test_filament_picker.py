"""Der Filamentwähler (Konzept „Filamente statt nummerierter Slots").

Was hier geprüft wird, ist die Frage, an der das alte Zahlenfeld gescheitert
ist: *Welche Farbe hat Slot 1?* Der Wähler muss sie beantworten, ohne dass
jemand erst malt — und er muss die Slotnummer liefern, mit der der Kern
weiterrechnet.
"""

from __future__ import annotations

import sys

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.knowledge import filaments
from app.core.types import MaterialSlot
from app.ui.filament_picker import NEW_FILAMENT, FilamentField, NewFilamentDialog, hex_of


def test_a_colour_from_the_document_becomes_a_hex_value() -> None:
    """Das Dokument führt Anteile, die Oberfläche zeigt Hexwerte."""
    assert hex_of((1.0, 0.0, 0.0)) == "#ff0000"
    assert hex_of((0.0, 0.5, 1.0)) == "#0080ff"
    assert hex_of(None) == "", "keine Farbe ist keine Farbe, nicht Schwarz"


def test_the_picker_answers_what_colour_slot_one_has(qt_app: QApplication) -> None:
    """Der Anlass des ganzen Umbaus.

    Neben dem alten Zahlenfeld stand nichts: Wer wissen wollte, was Slot 1
    ist, malte einmal und sah nach. Jetzt trägt der Eintrag Namen und Farbe.
    """
    field = FilamentField(
        1,
        slots=[
            MaterialSlot(index=0, name="Unbemalt"),
            MaterialSlot(index=1, name="PETG Rot", colour=(0.8, 0.1, 0.1)),
        ],
    )

    assert field.currentData() == 1, "der übergebene Slot steht gewählt da"
    assert "PETG Rot" in field.currentText(), "der Name des Filaments fehlt"
    assert not field.itemIcon(field.currentIndex()).isNull(), "kein Farbfeld am Eintrag"


def test_the_value_stays_the_slot_number(qt_app: QApplication) -> None:
    """Der Kern rechnet mit der Nummer — der Wähler ist Bedienung, kein
    Formatwechsel."""
    field = FilamentField(2, slots=[MaterialSlot(index=2, name="PLA Schwarz")])

    assert isinstance(field.currentData(), int)
    assert field.currentData() == 2


def test_slot_zero_is_not_called_a_filament(qt_app: QApplication) -> None:
    """Slot 0 ist die Abwesenheit eines Filaments, keine Spule.

    „Filament 0" hätte behauptet, dort läge eines — und der Kunde hätte
    gesucht, welches.
    """
    field = FilamentField(0)

    position = field.findData(0)
    assert position >= 0
    assert "0 —" not in field.itemText(position), "die nackte Null sagt nichts"
    assert "Ohne" in field.itemText(position)


def test_the_catalogue_is_offered_and_carries_name_and_colour(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Die Vorwahl ist der Punkt: einmal angelegt, in jedem Projekt zur Wahl.

    Und sie meldet Namen und Farbe weiter, damit der Dialog seine Felder
    füllen kann — sonst hätte der Kunde die Spule gewählt und müsste ihren
    Namen daneben trotzdem abtippen.
    """
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    filaments.remember(
        "PETG Rot",
        "#cc2222",
        material_type="PETG",
        slicer_profile="Elegoo PETG PRO @ECC2",
    )

    field = FilamentField(0)
    position = next(row for row in range(field.count()) if "PETG Rot" in field.itemText(row))

    seen: list[tuple[str, str, str, str]] = []
    field.filamentChosen.connect(
        lambda name, colour, material_type, profile: seen.append(
            (name, colour, material_type, profile)
        )
    )
    field.setCurrentIndex(position)
    field._chosen(position)

    assert seen == [("PETG Rot", "#cc2222", "PETG", "Elegoo PETG PRO @ECC2")], (
        "die ganze Filamentidentität muss weitergehen"
    )
    assert field.currentData() == 1, "die erste freie Nummer, nicht die Null"


def test_a_catalogue_filament_does_not_take_slot_zero(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Null bleibt frei: Sie ist das unbemalte Teil.

    Vergäbe der Wähler sie an das erste Filament der Vorwahl, hieße „Ohne
    Filament" plötzlich „PETG Rot" — und jedes Teil ohne Zuweisung wäre rot.
    """
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    filaments.remember("PLA Weiß", "#eeeeee")

    field = FilamentField(0)

    numbers = [field.itemData(row) for row in range(field.count())]
    assert numbers.count(0) == 1, "die Null steht genau einmal in der Liste"
    white = next(row for row in range(field.count()) if "PLA Weiß" in field.itemText(row))
    assert field.itemData(white) != 0


def test_a_filament_type_can_be_chosen_by_hand(qt_app: QApplication) -> None:
    """Eine selbst angelegte Spule ist nicht auf Name und Farbe beschränkt."""
    dialog = NewFilamentDialog(name="Werkstattrolle", colour="#123456", material_type="PETG")

    assert dialog.material_type.currentData() == "PETG"
    assert dialog.slicer_profile.isReadOnly(), "Profilnamen kommen aus dem Slicer, nie als Pfad"
    assert dialog.filament() == ("Werkstattrolle", "#123456", "PETG", "")


def test_a_typed_known_filament_type_keeps_what_is_visible(qt_app: QApplication) -> None:
    """Tippen und Auswählen müssen denselben Materialtyp ergeben.

    Ein editierbares Kombinationsfeld behält beim Tippen zunächst den alten
    Index. Der sichtbare Text darf dadurch nicht mit dessen unsichtbaren Daten
    gespeichert werden — „PLA" im Feld und „ABS" im Projekt wäre ein
    gefährlicher Bedienfehler.
    """
    dialog = NewFilamentDialog(name="Werkstattrolle", colour="#123456")
    dialog.material_type.setEditText("PLA")

    assert dialog.material_type.currentText() == "PLA"
    assert dialog.filament()[2] == "PLA"


def test_a_new_filament_starts_without_a_guessed_material_type(
    qt_app: QApplication,
) -> None:
    """Die alphabetische Profilreihenfolge ist keine Materialaussage.

    ABS wäre nur der erste Katalogeintrag, PLA nur die allgemeine
    Projektvorgabe. Beides sagt nichts über die Spule in der Hand; der Typ
    beginnt deshalb sichtbar unbekannt und bleibt frei wählbar.
    """
    dialog = NewFilamentDialog()

    assert dialog.material_type.currentData() == ""
    assert dialog.filament()[2] == ""
    assert "PLA" in dialog.material_type.toolTip()
    assert dialog.material_type.accessibleDescription() == dialog.material_type.toolTip()


def test_a_manual_filament_dialog_only_shows_questions_the_user_can_answer(
    qt_app: QApplication,
) -> None:
    """Eine lokale Spule braucht kein Slicer-Profil — aber den Weg dorthin.

    Bis zum 03.09.2026 war das Feld bei einer lokalen Spule **verborgen**, und
    das war die falsche Antwort auf die richtige Frage: Es blieb auch dann
    verborgen, wenn jemand eines zuordnen wollte, und gefüllt wurde es allein
    bei der Ersteinrichtung. Leer bleiben darf es weiterhin — die Werte kommen
    dann aus Solidon allein —, unerreichbar nicht.
    """
    dialog = NewFilamentDialog()

    assert dialog.slicer_profile.text() == "", "leer ist die Vorgabe einer lokalen Spule"
    assert dialog.choose_profile.isEnabled(), "der Weg zum Bestand des Slicers steht offen"
    assert not dialog.clear_profile.isEnabled(), "ohne Profil gibt es nichts zu entfernen"
    assert not dialog._ok_button.isEnabled(), "ein leeres Formular kann nicht wirkungslos enden"

    dialog.name.setText("Werkstattrolle")

    assert dialog._ok_button.isEnabled()


def test_an_imported_slicer_profile_is_visible_but_not_editable(
    qt_app: QApplication,
) -> None:
    """Übernommene Herkunft wird gezeigt, aber nicht als technisches Eingabefeld verkauft."""
    dialog = NewFilamentDialog(
        name="PETG Grau",
        material_type="PETG",
        slicer_profile="Elegoo PETG PRO @ECC2",
    )

    assert not dialog.slicer_profile.isHidden()
    assert not dialog._slicer_profile_label.isHidden()
    assert dialog.slicer_profile.isReadOnly()


def test_every_free_number_stays_reachable(qt_app: QApplication) -> None:
    """Keine Sackgasse (§2.1): Wer genau Slot 5 meint, bekommt ihn.

    Der Wähler ist eine Hilfe und keine Bevormundung — die acht Nummern des
    3MF-Farbwechsels bleiben alle erreichbar.
    """
    field = FilamentField(0, slots=[MaterialSlot(index=1, name="PETG Rot")])

    offered = {field.itemData(row) for row in range(field.count())}
    assert set(range(8)) <= offered, "eine Nummer fehlt in der Liste"


def test_a_cancelled_new_filament_leaves_a_usable_value(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """„Neues Filament …" ist kein Wert, den eine Operation kennt.

    Bliebe die Auswahl nach einem Abbruch darauf stehen, ginge NEW_FILAMENT
    als Slotnummer in die Transaktion — eine Zahl, die es im Schema nicht
    gibt.
    """
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    from app.ui import filament_picker

    class Cancelled:
        def __init__(self, *_args: object, **_kwargs: object) -> None: ...

        def exec(self) -> int:
            return 0  # QDialog.DialogCode.Rejected

    monkeypatch.setattr(filament_picker, "NewFilamentDialog", Cancelled)

    field = FilamentField(0)
    position = field.findData(NEW_FILAMENT)
    field.setCurrentIndex(position)
    field._chosen(position)

    assert field.currentData() != NEW_FILAMENT, "der Abbruch lässt keinen Unwert stehen"
    assert isinstance(field.currentData(), int)


def test_the_panel_shows_what_the_project_uses_and_what_lies_in_the_rack(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Beide Hälften, und je Filament eine Zeile.

    Die Frage, die das Panel beantwortet, hieß „wo wähle ich die Filamente
    und Farben aus?" — beide Antworten standen bis dahin in Dialogen. Oben,
    was die Körper tragen (Anzeige, mit der Zahl der Körper); unten das
    Regal, also die Vorwahl, die in jedem Filamentfeld zur Wahl steht.

    Zusammengelegt wird über Name **und** Farbe, wie beim Export: Zwei Körper
    in derselben Farbe sind eine Spule und nicht zwei.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.knowledge import filaments
    from app.core.types import MaterialSlot, SceneObject
    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    filaments.remember("PETG Rot", "#c0392b")
    filaments.remember("PLA Schwarz", "#1c1c1c")

    box = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    schwarz = MaterialSlot(index=0, name="PLA Schwarz", colour=(0.11, 0.11, 0.11))
    rot = MaterialSlot(index=1, name="PETG Rot", colour=(0.75, 0.22, 0.17))
    panel = FilamentPanel()
    panel.show_scene(
        [
            SceneObject(id="A", name="A", mesh=box, material_slots=[schwarz, rot]),
            SceneObject(id="B", name="B", mesh=box, material_slots=[schwarz]),
        ]
    )

    zeilen = [panel.list.item(index).text() for index in range(panel.list.count())]
    assert "PLA Schwarz — 2 Körper" in zeilen, f"zwei Körper tragen es: {zeilen}"
    assert "PETG Rot — 1 Körper" in zeilen, f"einer trägt es: {zeilen}"
    assert zeilen.count("PETG Rot") == 1, "das Regal nennt es einmal, ohne Zählung"


def test_refreshing_the_rack_keeps_the_project_summary(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Ein Slicer-Abgleich aktualisiert nur die projektübergreifende Hälfte.

    Das Panel ist beim Öffnen der Ersteinrichtung schon gebaut. Nach deren
    Filamentimport sollen die neuen Spulen sofort erscheinen, ohne die gerade
    gezeigten Projektfilamente oder ihre Druckwertmarken zu verlieren.
    """
    from types import SimpleNamespace

    from app.core.knowledge import filaments
    from app.core.types import MaterialSlot
    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    filaments.remember("PLA Weiß", "#ffffff", material_type="PLA")
    panel = FilamentPanel()
    panel.show_scene(
        [
            SimpleNamespace(
                material_slots=[MaterialSlot(index=1, name="PETG Grau", colour=(0.5, 0.5, 0.5))]
            )
        ]
    )
    project_state = panel._used

    filaments.remember("TPU Schwarz", "#111111", material_type="TPU")
    panel.refresh_catalogue()

    assert panel._used is project_state, "die Szenenzusammenfassung bleibt unangetastet"
    lines = [panel.list.item(index).text() for index in range(panel.list.count())]
    assert "PETG Grau — 1 Körper" in lines
    assert any(line.startswith("TPU Schwarz") for line in lines), "die neue Regalspule erscheint"


def test_a_used_filament_separates_colour_from_print_values(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Die Zeile ändert keine Geometrie und öffnet nur ihre Druckwerte.

    Farbe und Flächenzuweisung bleiben am Merkmal und damit in einer
    Operation. Die Temperaturen derselben Spule sind Druckeinstellungen und
    dürfen von hier erreichbar sein. Das Regal darunter bleibt unabhängig
    davon vollständig bedienbar.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.knowledge import filaments
    from app.core.types import MaterialSlot, SceneObject
    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    filaments.remember("PETG Rot", "#c0392b")
    box = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    panel = FilamentPanel()
    panel.show_scene(
        [
            SceneObject(
                id="A",
                name="A",
                mesh=box,
                material_slots=[MaterialSlot(index=1, name="PETG Rot", colour=(0.75, 0.22, 0.17))],
            )
        ]
    )

    benutzt = next(
        panel.list.item(index)
        for index in range(panel.list.count())
        if "Körper" in panel.list.item(index).text()
    )
    regal = next(
        panel.list.item(index)
        for index in range(panel.list.count())
        if panel.list.item(index).text() == "PETG Rot"
    )

    assert benutzt.flags() & Qt.ItemFlag.ItemIsSelectable, "Druckwerte müssen erreichbar sein"
    assert regal.flags() & Qt.ItemFlag.ItemIsSelectable, "das Regal lässt sich bedienen"
    assert "Kontextmenü" in benutzt.toolTip(), "die Farbzuweisung bleibt an der Operation"
    panel.list.setCurrentItem(benutzt)
    assert panel.settings_button.isEnabled(), "die sichtbare Handlung folgt der Auswahl"


def test_the_print_values_button_names_the_exact_filament(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Nicht „Slot 1", sondern Name und Farbe reisen zum Einstellungsdialog."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.knowledge import filaments
    from app.core.types import MaterialSlot, SceneObject
    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    slot = MaterialSlot(index=4, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    panel = FilamentPanel()
    panel.show_scene(
        [
            SceneObject(
                id="A",
                name="A",
                mesh=MeshData.of(trimesh.creation.box()),
                material_slots=[slot],
            )
        ]
    )
    used = next(
        panel.list.item(index)
        for index in range(panel.list.count())
        if "Körper" in panel.list.item(index).text()
    )
    panel.list.setCurrentItem(used)
    seen: list[MaterialSlot] = []
    panel.overrideRequested.connect(seen.append)

    panel.settings_button.click()

    assert seen == [slot]


def test_the_rack_is_written_through(qt_app: QApplication, tmp_path, monkeypatch) -> None:
    """Was das Panel am Regal ändert, steht im Katalog — und umgekehrt.

    Der Katalog ist die Vorwahl aller Projekte; das Panel ist nur die Stelle,
    an der man sie pflegt. Ein Panel, das seine eigene Liste führte, wäre
    beim nächsten Öffnen eine zweite Wahrheit.
    """
    from app.core.knowledge import filaments
    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    filaments.remember("PLA Weiß", "#f2f2f0")
    panel = FilamentPanel()
    panel.show_scene([])
    row = next(
        index for index in range(panel.list.count()) if panel.list.item(index).text() == "PLA Weiß"
    )
    panel.list.setCurrentRow(row)

    panel._remove()

    assert [entry.name for entry in filaments.catalogue()] == [], (
        "aus dem Katalog, nicht nur aus der Liste"
    )
    assert not any(
        panel.list.item(index).text() == "PLA Weiß" for index in range(panel.list.count())
    )


def test_a_filament_without_a_colour_is_never_shown_blank(qt_app: QApplication) -> None:
    """Jedes Filament hat eine Farbe im Bild — auch vor der ersten Wahl.

    Der Viewport ging diese Kette schon (eigene Farbe → Grauleiter →
    Körperfarbe für Slot 0), die Oberfläche daneben brach nach dem ersten
    Glied ab: Wo im Dokument keine Farbe stand, blieb das Kästchen leer —
    im Wähler neben dem Text „Ohne Filament — Farbe des Teils" und im Panel.
    Ein leeres Kästchen sagt „keine Farbe", und das ist hier nie der Fall
    (Robert, 27.08.2026).
    """
    from app.ui.filament_picker import shown_colour, unpainted_colour
    from app.ui.theme import slot_colour

    assert shown_colour(0) == unpainted_colour(), "Slot 0 ist das Teil, und das ist grau"
    assert shown_colour(1) == slot_colour(1), "die Grauleiter, bevor jemand wählt"
    assert shown_colour(1, (1.0, 0.0, 0.0)) == "#ff0000", "eine eigene Farbe schlägt beides"
    assert all(shown_colour(index) for index in range(8)), "keiner bleibt leer"


def test_the_default_slot_carries_its_grey_in_the_picker(qt_app: QApplication) -> None:
    """Und der vorgewählte Eintrag zeigt es auch.

    ``paint_slot`` beginnt bei Filament 1 — der Eintrag, den jeder sieht, der
    zum ersten Mal eine Fläche färbt. Er stand mit leerem Kästchen da; jetzt
    trägt er die Farbe, die er nach dem Klick im Bild hat.
    """
    from app.ui.filament_picker import SWATCH_PIXELS, FilamentField, shown_colour

    field = FilamentField(1)
    position = field.findData(1)

    assert position >= 0, "Filament 1 steht zur Wahl"
    assert field.currentIndex() == position, "und ist vorgewählt"

    # Am Bild gemessen und nicht am Vorhandensein eines Symbols: Ein leeres
    # ``QIcon`` ist auch „nicht null", und genau das stand vorher dort.
    bild = field.itemIcon(position).pixmap(SWATCH_PIXELS, SWATCH_PIXELS).toImage()
    mitte = bild.pixelColor(SWATCH_PIXELS // 2, SWATCH_PIXELS // 2)
    assert mitte.alpha() == 255, "das Feld ist gefüllt, nicht durchsichtig"
    assert mitte.name() == shown_colour(1), f"und trägt die Grauleiter: {mitte.name()}"


def test_a_body_without_a_slot_still_shows_up(qt_app: QApplication, tmp_path, monkeypatch) -> None:
    """Der Normalfall nach jedem STL-Import steht im Panel.

    Ein frisch eingelesenes Modell hat keine Materialslots — und die
    Projekthälfte war damit leer, während im Bild ein Körper stand, der sehr
    wohl in einer Farbe gedruckt wird.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.knowledge import filaments
    from app.core.types import SceneObject
    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    box = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    panel = FilamentPanel()
    panel.show_scene([SceneObject(id="A", name="A", mesh=box)])

    zeilen = [panel.list.item(index).text() for index in range(panel.list.count())]
    assert any("Ohne Filament" in zeile and "1 Körper" in zeile for zeile in zeilen), zeilen


def test_the_unpainted_swatch_follows_the_theme() -> None:
    """Das Feld „Ohne Filament — Farbe des Teils" zeigt die Farbe des Teils.

    Es zeigte sie im dunklen Thema und im hellen nicht: Die Farbe kam fest aus
    dem dunklen Satz, mit der Begründung, ein Feld von vierzehn Bildpunkten
    trage den Unterschied nicht. Gemessen sind es ``#7d8894`` gegen
    ``#b9c4d0`` — zwei klar unterscheidbare Grautöne, und die Beschriftung
    daneben verspricht genau diese eine Farbe.

    Der Fall, in dem eine zutreffend klingende Begründung eine Messung ersetzt
    hat, die niemand gemacht hatte.
    """
    from app.ui import theme
    from app.ui.filament_picker import unpainted_colour

    was = theme.current_theme()
    try:
        for name in ("dark", "light"):
            theme._ACTIVE = name  # type: ignore[assignment]
            assert unpainted_colour() == theme.viewport_colours(name)["object"], name
        # Und die Gegenprobe: die beiden Themen sagen wirklich Verschiedenes,
        # sonst prüfte der Test über einer Gleichheit, die nichts kostet.
        assert theme.viewport_colours("dark")["object"] != theme.viewport_colours("light")["object"]
    finally:
        theme._ACTIVE = was


@pytest.mark.xfail(
    sys.platform == "darwin",
    reason="auf dem Mac rechnet _around_the_list das Beiwerk zu klein — ungemessen, siehe Register",
    strict=False,
)
def test_the_filament_card_shares_the_height_instead_of_taking_it(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Die Karte nimmt an der Zuteilung teil, statt sich zu bedienen.

    ``OverlayHost._share_room`` verteilt die Höhe der linken Spalte nur an
    Kinder, die das ``RoomTaker``-Protokoll erfüllen; wer es nicht erfüllt,
    „behält seine eigene Höhe" und steht damit außerhalb der Verteilung. Diese
    Karte tat das, und bei einem vollen Regal wurde daraus eine Schieflage:
    Gemessen am 30.08.2026 im echten Fenster mit fünfzehn Spulen nahm sie sich
    424 Bildpunkte, während der Verlauf daneben auf 102 gedrückt wurde und 262
    brauchte — die Karte, die laut §2.4 jeden Arbeitsschritt begleitet, verlor
    gegen die, die man einmal am Anfang fragt.
    """
    from app.ui.filament_picker import FilamentPanel
    from app.ui.overlay import RoomTaker

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    panel = FilamentPanel()
    assert isinstance(panel, RoomTaker), (
        "ohne wanted_height, least_height und set_room bleibt die Karte außerhalb der Zuteilung"
    )

    # Und die Zusagen des Protokolls: Der Boden liegt unter dem Wunsch, sonst
    # verteilt _share_room unter etwas, das die Karte selbst durchsetzt.
    assert panel.least_height() <= panel.wanted_height(), (
        f"Boden {panel.least_height()} über Wunsch {panel.wanted_height()}"
    )
    knapp = panel.least_height()
    panel.set_room(knapp)
    assert panel.sizeHint().height() <= knapp + 1, (
        "eine knapp bemessene Karte muss sich auch klein machen"
    )

    # **Und solange niemand zugeteilt hat, gilt der Deckel.** Der Augenblick
    # vor der ersten Zuteilung ist real: Das Fenster baut die Karte, bevor die
    # Überlagerung sie das erste Mal fragt, und ein Regal mit hundert Spulen
    # nähme die Spalte, ehe irgendjemand etwas verteilt.
    from app.ui.panels import MAX_ROWS

    for nummer in range(100):
        filaments.remember(f"Viel {nummer:03d}", "#2980b9")
    ungefragt = FilamentPanel()
    assert ungefragt.list.count() > 2 * MAX_ROWS, "der Deckel wird nur bei vielen Zeilen geprüft"
    zeile = ungefragt.list.sizeHintForRow(0)
    assert ungefragt.list.height() <= (MAX_ROWS + 1) * zeile, (
        f"ohne Zuteilung {ungefragt.list.height()} Punkte bei {ungefragt.list.count()} Zeilen — "
        f"der Deckel von {MAX_ROWS} Zeilen greift nicht"
    )


def test_every_row_fits_when_the_card_gets_the_height_it_asked_for(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Die letzte Zeile fehlte, obwohl ringsum Platz frei war.

    Der Grund war eine Rechnung, die für diese Liste nicht passt:
    ``fit_to_rows`` nimmt die Höhe der *ersten* Zeile mal die Zahl der Zeilen —
    richtig für einen Baum, in dem jede Zeile gleich aussieht. Hier stehen
    zwischen den Spulen zwei fette Überschriften („Im Projekt", „Im Regal"),
    und die sind höher als eine Spulenzeile. Gemessen am 30.08.2026 bei fünf
    Zeilen: 172 Bildpunkte gebraucht, 156 gesetzt, vier von fünf Zeilen zu
    sehen — auch dann, wenn die Spalte ihre volle Wunschhöhe bekam.
    """
    from types import SimpleNamespace

    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    for nummer in range(4):
        filaments.remember(f"Spule {nummer}", "#c0392b", material_type="PETG")

    panel = FilamentPanel()
    panel.show_scene(
        [
            SimpleNamespace(
                material_slots=[MaterialSlot(index=1, name="PETG Grau", colour=(0.5, 0.5, 0.5))]
            )
        ]
    )
    panel.resize(300, 400)
    panel.set_room(panel.wanted_height())

    liste = panel.list
    hoehen = [liste.sizeHintForRow(reihe) for reihe in range(liste.count())]
    # **Der Kontrollfall.** Sind alle Zeilen gleich hoch, rechnen beide Wege
    # dasselbe und dieser Test prüft nichts — die Überschriften sind der Fall,
    # um den es geht.
    assert len(set(hoehen)) > 1, f"gleich hohe Zeilen prüfen die Sache nicht: {hoehen}"

    platz = liste.height() - 2 * liste.frameWidth()
    assert platz >= sum(hoehen), (
        f"{liste.count()} Zeilen brauchen {sum(hoehen)} Punkte, die Liste bietet "
        f"{platz} — die letzten passen nicht hinein"
    )


def test_the_filter_dialog_narrows_by_vendor_material_and_text(qt_app: QApplication) -> None:
    """Der Grund, aus dem es diesen Dialog gibt.

    Der Bestand eines Slicers geht in die Tausende — gemessen 5962
    Filamentprofile aus 48 Herstellern. Eine Auswahlliste ist dafür der
    falsche Behälter; drei Filter sind die Antwort.
    """
    from pathlib import Path as _Path

    from app.core.export import slicer_profiles as sp
    from app.ui.filament_picker import SlicerFilamentDialog

    bestand = [
        sp.SlicerProfile(
            path=_Path(f"/x/{vendor}/filament/{name}.json"),
            name=name,
            kind="filament",
        )
        for vendor, name in (
            ("Elegoo", "Elegoo PLA @EC"),
            ("Elegoo", "Elegoo PLA Matte @EC"),
            ("Elegoo", "Elegoo PETG @EC"),
            ("BBL", "Bambu PLA Basic"),
        )
    ]

    dialog = SlicerFilamentDialog(None, bestand)
    assert dialog.list.count() == 4, "ohne Filter steht alles da"

    dialog.vendor.setCurrentIndex(dialog.vendor.findData("Elegoo"))
    assert dialog.list.count() == 3

    dialog.material.setCurrentIndex(dialog.material.findData("PLA"))
    assert dialog.list.count() == 2, "PETG fällt weg"

    dialog.search.setText("matte")
    assert dialog.list.count() == 1
    assert dialog.chosen_profile() == "Elegoo PLA Matte @EC"


def test_the_dialog_opens_on_the_vendor_of_the_current_choice(qt_app: QApplication) -> None:
    """Wer mit einer Wahl hereinkommt, sucht sie nicht unter 48 Herstellern."""
    from pathlib import Path as _Path

    from app.core.export import slicer_profiles as sp
    from app.ui.filament_picker import SlicerFilamentDialog

    bestand = [
        sp.SlicerProfile(
            path=_Path("/x/BBL/filament/a.json"), name="Bambu PLA Basic", kind="filament"
        ),
        sp.SlicerProfile(
            path=_Path("/x/Elegoo/filament/b.json"), name="Elegoo PLA @EC", kind="filament"
        ),
    ]

    dialog = SlicerFilamentDialog(None, bestand, "Elegoo PLA @EC")

    assert dialog.vendor.currentData() == "Elegoo"
    assert dialog.chosen_profile() == "Elegoo PLA @EC", "die Vorwahl steht markiert"


def test_an_empty_result_says_what_to_do(qt_app: QApplication) -> None:
    """Keine Sackgasse (§2.1): Eine leere Liste ohne Satz ist ein stiller Ausfall."""
    from pathlib import Path as _Path

    from app.core.export import slicer_profiles as sp
    from app.ui.filament_picker import SlicerFilamentDialog

    bestand = [
        sp.SlicerProfile(
            path=_Path("/x/Elegoo/filament/a.json"), name="Elegoo PLA @EC", kind="filament"
        )
    ]

    dialog = SlicerFilamentDialog(None, bestand)
    dialog.search.setText("gibt es nicht")

    assert dialog.list.count() == 0
    assert "Filter" in dialog.count.text(), "der Satz nennt den Weg heraus"
    assert not dialog._ok_button.isEnabled(), "ohne Treffer gibt es nichts zu übernehmen"


def test_the_profile_of_a_spool_can_be_chosen_and_removed(qt_app: QApplication) -> None:
    """Der eigentliche Fund vom 03.09.2026.

    Das Feld war schreibgeschützt, und gefüllt wurde es allein bei der
    Ersteinrichtung. Wer im Slicer dasselbe Material mehrfach mit
    verschiedenen Werten anlegt, konnte in Solidon nicht sagen, welche
    Ausführung gilt — obwohl die Übergabe sie sofort verwendet hätte.
    """
    dialog = NewFilamentDialog(
        None, name="PLA Rot", colour="#ff0000", slicer_profile="Elegoo PLA @EC"
    )

    assert dialog.slicer_profile.isVisibleTo(dialog), "das Feld ist immer erreichbar"
    assert dialog.choose_profile.isEnabled()
    assert dialog.clear_profile.isEnabled()

    dialog._clear_slicer_profile()

    assert dialog.slicer_profile.text() == ""
    assert not dialog.clear_profile.isEnabled()
    assert dialog.filament()[3] == "", "ohne Profil kommen die Werte aus Solidon allein"
