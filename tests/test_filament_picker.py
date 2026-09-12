"""Der Filamentwähler (Konzept „Filamente statt nummerierter Slots").

Was hier geprüft wird, ist die Frage, an der das alte Zahlenfeld gescheitert
ist: *Welche Farbe hat Slot 1?* Der Wähler muss sie beantworten, ohne dass
jemand erst malt — und er muss die Slotnummer liefern, mit der der Kern
weiterrechnet.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.knowledge import filaments
from app.core.types import MaterialSlot
from app.ui.filament_picker import NEW_FILAMENT, FilamentField, NewFilamentDialog, hex_of


def _assigned_body(slots: list[MaterialSlot], used: tuple[int, ...]):
    """Ein echter kleiner Körper trennt seine benutzten Flächen von alten Slotdefinitionen."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    mesh = MeshData.of(
        trimesh.creation.box(), slots=tuple(used[index % len(used)] for index in range(12))
    )
    return SceneObject(id="part", name="Teil", mesh=mesh, material_slots=slots)


def test_a_colour_from_the_document_becomes_a_hex_value() -> None:
    """Das Dokument führt Anteile, die Oberfläche zeigt Hexwerte."""
    assert hex_of((1.0, 0.0, 0.0)) == "#ff0000"
    assert hex_of((0.0, 0.5, 1.0)) == "#0080ff"
    assert hex_of(None) == "", "keine Farbe ist keine Farbe, nicht Schwarz"


def test_broken_inventory_keeps_project_choice_and_reports_error(qt_app, tmp_path, monkeypatch):
    """Vorwahl und Panel zeigen Lesefehler, Projektfilamente bleiben erhalten."""
    from app.ui.filament_picker import FilamentPanel

    path = tmp_path / "filaments.json"
    monkeypatch.setattr(filaments, "catalogue_path", lambda: path)
    first = filaments.save(filaments.CatalogueFilament("Spule", "#112233"))
    panel = FilamentPanel()
    before = [panel.list.item(row).text() for row in range(panel.list.count())]
    field = FilamentField(2, slots=[MaterialSlot(2, "Projekt")])
    selected = next(row for row in range(field.count()) if "Spule" in field.itemText(row))
    seen = []
    field.choiceNotice.connect(seen.append)
    path.write_text("{kaputt", encoding="utf-8")
    panel.refresh_catalogue()
    assert "Sicherung" in panel.hint.text()
    assert [panel.list.item(row).text() for row in range(panel.list.count())] == before
    field._chosen(selected)
    assert field.currentData() == 2
    assert "Sicherung" in seen[-1]
    fresh = FilamentField(2, slots=[MaterialSlot(2, "Projekt")])
    assert fresh.currentData() == 2
    errors = [row for row in range(fresh.count()) if "Sicherung" in fresh.itemText(row)]
    assert len(errors) == 1
    assert not fresh.model().flags(fresh.model().index(errors[0], 0)) & Qt.ItemFlag.ItemIsEnabled
    assert first.identifier


def test_full_spool_can_be_entered_without_opening_optional_details(qt_app: QApplication) -> None:
    """Die Voraussetzung des Vollspulenknopfs liegt auf derselben sichtbaren Seite."""
    dialog = NewFilamentDialog()
    dialog.show()
    qt_app.processEvents()
    assert not dialog.more.isVisibleTo(dialog)
    assert dialog.spool_weight.isVisibleTo(dialog)
    assert dialog.location.isVisibleTo(dialog)
    dialog.spool_weight.setValue(750)
    assert dialog.entry().remaining_grams is None
    dialog.full_spool_button.click()
    assert dialog.entry().remaining_grams == pytest.approx(750)
    assert dialog.stock_known.isChecked()
    dialog.close()


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


def test_only_filaments_that_exist_are_offered(qt_app: QApplication) -> None:
    """Die Liste zeigt Spulen, keine leeren Plätze.

    **Hier stand das Gegenteil.** „Keine Sackgasse (§2.1): Wer genau Slot 5
    meint, bekommt ihn" — und dafür trug die Liste alle acht Nummern des
    3MF-Farbwechsels, auch die sieben, hinter denen nichts lag. Gemessen an
    einem Projekt mit einem einzigen zugewiesenen Filament waren das neun
    Einträge, von denen zwei etwas bedeuteten.

    Robert am 08.09.2026: „Im Projektbaum sollen nur Filamente erscheinen, die
    wir bei Filamenten schon hinzugefügt haben." §2.1 verspricht keine
    Sackgassen bei **rücknehmbaren** Handlungen, und eine Filamentzuweisung
    ist eine Op wie jede andere — Strg+Z nimmt sie zurück. Wer eine Nummer
    braucht, die es noch nicht gibt, legt die Spule an; sie bekommt ihre
    Nummer beim Wählen.

    Was stehen bleibt: was am Körper liegt, was im Katalog steht, Slot 0 als
    Abwesenheit — und der vorgewählte Wert, damit die Vorgabe nicht ins Leere
    zeigt.
    """
    field = FilamentField(0, slots=[MaterialSlot(index=1, name="PETG Rot")])

    offered = {field.itemData(row) for row in range(field.count())}
    assert 1 in offered, "was am Körper liegt, steht zur Wahl"
    assert 0 in offered, "und die Abwahl — sonst wird man ein Filament nicht mehr los"
    leer = set(range(2, 8)) & offered
    assert not leer, f"leere Plätze gehören nicht in die Liste, gefunden: {sorted(leer)}"


def test_the_preselected_slot_is_in_the_list_even_when_empty(qt_app: QApplication) -> None:
    """Was vorgewählt ist, muss man auch sehen können.

    ``paint_slot`` beginnt bei Filament 1. Stünde die Vorgabe nicht in der
    Liste, zeigte das Feld beim Öffnen etwas anderes an, als die Operation
    ausführen würde — der Fehler, den das Aufräumen der leeren Plätze fast
    eingebaut hätte.
    """
    field = FilamentField(1)

    assert field.findData(1) >= 0, "die Vorwahl steht in der Liste"
    assert field.currentData() == 1, "und sie ist auch gewählt"


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

    monkeypatch.setattr(filament_picker.NewFilamentDialog, "exec", lambda _dialog: 0)

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
            _assigned_body([schwarz, rot], (0, 1)),
            SceneObject(id="B", name="B", mesh=box, material_slots=[schwarz]),
        ]
    )

    zeilen = [panel.list.item(index).text() for index in range(panel.list.count())]
    assert "PLA Schwarz — 2 Körper" in zeilen, f"zwei Körper tragen es: {zeilen}"
    assert "PETG Rot — 1 Körper" in zeilen, f"einer trägt es: {zeilen}"
    assert sum(line.startswith("PETG Rot ·") for line in zeilen) == 1
    assert any("Bestand unbekannt" in line for line in zeilen), "Altbestand wird nicht geraten"


def test_refreshing_the_rack_keeps_the_project_summary(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Ein Slicer-Abgleich aktualisiert nur die projektübergreifende Hälfte.

    Das Panel ist beim Öffnen der Ersteinrichtung schon gebaut. Nach deren
    Filamentimport sollen die neuen Spulen sofort erscheinen, ohne die gerade
    gezeigten Projektfilamente oder ihre Druckwertmarken zu verlieren.
    """
    from app.core.knowledge import filaments
    from app.core.types import MaterialSlot
    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    filaments.remember("PLA Weiß", "#ffffff", material_type="PLA")
    panel = FilamentPanel()
    panel.show_scene(
        [_assigned_body([MaterialSlot(index=1, name="PETG Grau", colour=(0.5, 0.5, 0.5))], (1,))]
    )
    project_state = panel._used

    filaments.remember("TPU Schwarz", "#111111", material_type="TPU")
    panel.refresh_catalogue()

    assert panel._used is project_state, "die Szenenzusammenfassung bleibt unangetastet"
    lines = [panel.list.item(index).text() for index in range(panel.list.count())]
    assert "PETG Grau — 1 Körper" in lines
    assert any(line.startswith("TPU Schwarz") for line in lines), "die neue Regalspule erscheint"


def test_project_summary_counts_used_surfaces_and_keeps_unassigned_faces(
    qt_app: QApplication,
) -> None:
    """Eine Altdefinition zählt nicht als Bedarf; ein unbenutzter Slot ersetzt keine Fläche."""
    from app.ui.filament_picker import FilamentPanel

    active = MaterialSlot(index=1, name="Aktiv", colour=(1, 0, 0))
    stale = MaterialSlot(index=2, name="Früher", colour=(0, 0, 1))
    panel = FilamentPanel()
    panel.show_scene([_assigned_body([active, stale], (0, 1))])
    used = {
        (str(slot.name) if slot else None): count
        for slot, _name, _colour, count, _own in panel._used
    }
    assert used == {"Aktiv": 1, None: 1}


def test_same_print_filament_counts_each_body_only_once(qt_app: QApplication) -> None:
    """Zwei belegte Plätze mit derselben Druckidentität sind kein zweiter Körper."""
    from app.ui.filament_picker import FilamentPanel

    slots = [MaterialSlot(index=index, name="Gleich", colour=(1, 0, 0)) for index in (1, 2)]
    panel = FilamentPanel()
    panel.show_scene([_assigned_body(slots, (1, 2))])
    assert len(panel._used) == 1
    assert panel._used[0][3] == 1


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
    box = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)), slots=(1,) * 12)
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
        if panel.list.item(index).text().startswith("PETG Rot ·")
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
                mesh=MeshData.of(trimesh.creation.box(), slots=(4,) * 12),
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
        index
        for index in range(panel.list.count())
        if panel.list.item(index).text().startswith("PLA Weiß ·")
    )
    panel.list.setCurrentRow(row)

    panel._remove()
    _wait_for_catalogue(panel)

    assert [entry.name for entry in filaments.catalogue()] == [], (
        "aus dem Katalog, nicht nur aus der Liste"
    )
    assert not any(
        panel.list.item(index).text().startswith("PLA Weiß ·")
        for index in range(panel.list.count())
    )
    assert filaments.catalogue(include_archived=True)[0].archived


def _wait_for_catalogue(widget) -> None:
    """Der Fachabschluss muss im Widget ankommen, nicht nur auf der Platte."""
    from time import monotonic

    from PySide6.QtTest import QTest

    deadline = monotonic() + 5
    while not widget.wait_for_workers(0) and monotonic() < deadline:
        QTest.qWait(10)
    assert widget.wait_for_workers(0)


@pytest.mark.parametrize("action", ["create", "edit", "archive", "field"])
def test_catalogue_writes_leave_qt_free_until_the_atomic_result_arrives(
    qt_app: QApplication, tmp_path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    """Vier Schreibwege halten Qt frei und übernehmen nur den gespeicherten Stand."""
    from threading import Event, get_ident

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog

    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    original_entry = filaments.save(filaments.CatalogueFilament("Alt", "#ffffff"))
    panel = FilamentPanel()
    panel.list.setCurrentRow(
        next(
            row
            for row in range(panel.list.count())
            if panel.list.item(row).text().startswith("Alt")
        )
    )
    field = FilamentField(0)
    selected = []
    field.spoolChosen.connect(selected.append)
    entered, released = Event(), Event()
    qt_thread = get_ident()
    threads = []
    original = filaments.archive if action == "archive" else filaments.save

    def write(*args, **kwargs):
        threads.append(get_ident())
        entered.set()
        if get_ident() != qt_thread:
            assert released.wait(5)
        return original(*args, **kwargs)

    def confirm(dialog):
        dialog.name.setText("Neu")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(filaments, "archive" if action == "archive" else "save", write)
    monkeypatch.setattr(NewFilamentDialog, "exec", confirm)
    owner = field if action == "field" else panel
    try:
        if action == "create":
            panel.add_button.click()
        elif action == "edit":
            panel.list.itemDoubleClicked.emit(panel.list.currentItem())
        elif action == "archive":
            panel._remove()
        else:
            field._make_one(field.findData(NEW_FILAMENT))
        assert entered.wait(2)
        assert threads[0] != qt_thread
        assert not owner.wait_for_workers(0)
        responsive = []
        QTimer.singleShot(0, lambda: responsive.append(True))
        QApplication.processEvents()
        assert responsive
        if action == "field":
            assert not field.isEnabled()
            assert field.currentData() == 0
            assert not selected
        else:
            assert not panel.list.isEnabled()
            assert not panel.add_button.isEnabled()
            assert "gespeichert" in panel.hint.text()
    finally:
        released.set()
        if hasattr(owner, "wait_for_workers"):
            _wait_for_catalogue(owner)
    entries = filaments.catalogue(include_archived=True)
    if action == "archive":
        assert entries[0].archived
    elif action == "edit":
        assert len(entries) == 1
        assert entries[0].name == "Neu"
        assert entries[0].identifier == original_entry.identifier
    else:
        assert {entry.name for entry in entries} == {"Alt", "Neu"}
    if action == "field":
        assert field.isEnabled()
        assert len(selected) == 1 and selected[0].name == "Neu"
        assert "Neu" in field.currentText()
    else:
        assert panel.list.isEnabled()
        assert panel.add_button.isEnabled()


@pytest.mark.parametrize("owner_kind", ["field", "panel"])
@pytest.mark.parametrize("failure", ["expected", "unexpected"])
def test_a_failed_catalogue_write_keeps_the_old_selection_and_can_be_retried(
    qt_app: QApplication,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    owner_kind: str,
    failure: str,
) -> None:
    """Eine Absage oder Ausnahme löst die Sperre und übernimmt keine ungespeicherte Spule."""
    from PySide6.QtWidgets import QDialog

    from app.core.errors import FileWriteError
    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    owner = FilamentField(0) if owner_kind == "field" else FilamentPanel()
    notices = []
    if owner_kind == "field":
        owner.choiceNotice.connect(notices.append)
    original = filaments.save

    def save(_entry):
        if failure == "expected":
            raise FileWriteError(detail="Die Datei ist gesperrt.")
        raise RuntimeError("Die Datei ist gesperrt.")

    def confirm(dialog):
        dialog.name.setText("Neue Spule")
        return QDialog.DialogCode.Accepted

    def choose():
        if owner_kind == "field":
            owner._make_one(owner.findData(NEW_FILAMENT))
        else:
            owner.add_button.click()
        _wait_for_catalogue(owner)

    monkeypatch.setattr(filaments, "save", save)
    monkeypatch.setattr(NewFilamentDialog, "exec", confirm)
    choose()
    assert "gesperrt" in (notices[-1] if owner_kind == "field" else owner.hint.text())
    assert filaments.catalogue() == ()
    if owner_kind == "field":
        assert owner.isEnabled()
        assert owner.currentData() == 0
    else:
        assert owner.add_button.isEnabled()
    monkeypatch.setattr(filaments, "save", original)
    choose()
    assert [entry.name for entry in filaments.catalogue()] == ["Neue Spule"]


@pytest.mark.parametrize("kind", ["quick", "inventory", "panel", "usage"])
def test_inventory_errors_keep_advice_and_retry_their_own_read(
    qt_app: QApplication, tmp_path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Der Rat bleibt sichtbar, der Knopf lädt diese Ansicht und ein alter Knopf wird unwirksam."""
    from time import monotonic

    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton
    from shiboken6 import isValid

    from app.core.errors import RETRY, Action, UserError
    from app.core.filament_usage import UsageRequest
    from app.ui import filament_usage as usage_ui
    from app.ui.filament_assignment import QuickFilamentPicker
    from app.ui.filament_inventory import InventoryView
    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    filaments.save(filaments.CatalogueFilament("Vorhanden", "#123456"))
    if kind == "quick":
        owner = QuickFilamentPicker()
        notice, refresh = owner.notice, owner.refresh
    elif kind == "inventory":
        owner = InventoryView()
        notice, refresh = owner.message, owner.refresh
    elif kind == "panel":
        owner = FilamentPanel()
        notice, refresh = owner.hint, owner._fill
    else:
        owner = usage_ui.UsageDialog(UsageRequest("geometry", "Projekt", 0, ()))
        notice, refresh = owner.state, owner._load

    def settle():
        if kind != "usage":
            return
        deadline = monotonic() + 5
        while not owner.wait_for_workers(0) and monotonic() < deadline:
            QTest.qWait(10)
        assert owner.wait_for_workers(0)

    settle()
    source, name = (usage_ui, "_snapshot") if kind == "usage" else (filaments, "catalogue")
    original = getattr(source, name)
    broken = True
    calls = []
    advice = "Prüfen Sie die Sicherung des Lagers."

    def read(*args, **kwargs):
        calls.append(True)
        if broken:
            raise UserError(
                detail="Das Lager ist nicht lesbar.",
                suggestions=(RETRY, Action("check_inventory_backup", advice)),
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(source, name, read)
    try:
        refresh()
        settle()
        assert advice in notice.text(), "der fachliche Rat ging bei str(error) verloren"
        retry = next(
            button
            for button in notice.findChildren(QPushButton)
            if button.text() == str(RETRY.label)
        )
        refresh()
        settle()
        if isValid(retry):
            retry.click()
        assert len(calls) == 2, "ein alter Fehlerknopf darf keine neue Meldung auslösen"
        retry = next(
            button
            for button in notice.findChildren(QPushButton)
            if button.text() == str(RETRY.label) and not button.isHidden()
        )
        broken = False
        retry.click()
        settle()
        assert len(calls) == 3
        assert "nicht lesbar" not in notice.text()
        if isValid(retry):
            retry.click()
        settle()
        assert len(calls) == 3, "ein abgeräumter Fehlerknopf darf keinen neuen Auftrag starten"
    finally:
        owner.close()
        owner.deleteLater()


@pytest.mark.parametrize("kind", ["panel", "operation"])
def test_catalogue_error_retries_the_confirmed_spool_without_a_second_entry_dialog(
    qt_app: QApplication, tmp_path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Eine wieder verfügbare Datei erhält genau den bereits bestätigten Spuleneintrag."""
    from PySide6.QtWidgets import QDialog, QPushButton

    from app.core.errors import RETRY, FileWriteError
    from app.core.registry import REGISTRY
    from app.ui.filament_picker import FilamentPanel
    from app.ui.op_dialog import OperationDialog

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    original = filaments.save
    broken = True
    writes, confirmations = [], []

    def save(entry):
        writes.append(entry)
        if broken:
            raise FileWriteError(detail="Das Lager ist gesperrt.", suggestions=(RETRY,))
        return original(entry)

    def confirm(dialog):
        confirmations.append(True)
        dialog.name.setText("Bestätigte Spule")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(filaments, "save", save)
    monkeypatch.setattr(NewFilamentDialog, "exec", confirm)
    if kind == "panel":
        owner = writer = FilamentPanel()
        notice = owner.hint
        owner.add_button.click()
    else:
        owner = OperationDialog(REGISTRY.get("assign_slot"), ["obj_1"], values={"slot": 0})
        writer = owner.findChild(FilamentField)
        assert writer is not None
        notice = owner._filament_notice
        writer._make_one(writer.findData(NEW_FILAMENT))
    try:
        _wait_for_catalogue(writer)
        assert "gesperrt" in notice.text()
        retry = next(
            button
            for button in notice.findChildren(QPushButton)
            if button.text() == str(RETRY.label)
        )
        broken = False
        retry.click()
        _wait_for_catalogue(writer)
        assert len(writes) == 2 and writes[0] is writes[1]
        assert confirmations == [True]
        assert [entry.name for entry in filaments.catalogue()] == ["Bestätigte Spule"]
        assert "gesperrt" not in notice.text()
    finally:
        owner.close()
        owner.deleteLater()


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
    from app.ui.overlay import is_room_taker

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    panel = FilamentPanel()
    assert is_room_taker(panel), (
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
    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    for nummer in range(4):
        filaments.remember(f"Spule {nummer}", "#c0392b", material_type="PETG")

    panel = FilamentPanel()
    panel.show_scene(
        [_assigned_body([MaterialSlot(index=1, name="PETG Grau", colour=(0.5, 0.5, 0.5))], (1,))]
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


@pytest.mark.parametrize("font_points", [10, 16])
@pytest.mark.parametrize("width", [260, 420])
@pytest.mark.parametrize("row_count", [0, 25])
def test_filament_card_room_includes_wrapped_hint_and_visible_controls(
    qt_app: QApplication, tmp_path, monkeypatch, font_points, width, row_count
) -> None:
    """Knapper und freier Raum enthalten den Hinweis und lassen der Nachbarkarte Platz."""
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from app.ui.filament_picker import FilamentPanel

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    for index in range(row_count):
        filaments.remember(f"Spule {index:02d}", "#2980b9")
    host = QWidget()
    host.setFixedWidth(width)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    panel = FilamentPanel()
    panel.setFont(QFont(qt_app.font().family(), font_points))
    panel.hint.setText("Der lange Hinweis erklärt die Auswahl und die Druckwerte. " * 5)
    layout.addWidget(panel)
    neighbour = QPushButton("Nachbarkarte")
    neighbour.setFixedHeight(neighbour.sizeHint().height())
    layout.addWidget(neighbour)
    host.resize(width, 700)
    host.show()
    qt_app.processEvents()
    try:
        for back_visible in (False, True):
            panel.return_to_print_button.setVisible(back_visible)
            qt_app.processEvents()
            for full_room in (False, True):
                room = panel.wanted_height() if full_room else panel.least_height()
                panel.set_room(room)
                layout.activate()
                host.resize(width, room + neighbour.height())
                qt_app.processEvents()
                assert panel.height() == room
                assert panel.minimumHeight() <= room
                assert panel.hint.height() >= panel.hint.heightForWidth(panel.hint.width())
                assert neighbour.geometry().top() >= panel.geometry().bottom()
                assert neighbour.geometry().bottom() < host.height()
                assert panel.wanted_height() >= panel.least_height()
                if full_room:
                    assert panel.list.verticalScrollBar().maximum() == 0
    finally:
        host.close()


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


@pytest.mark.parametrize("lookup", ["empty", "broken"])
def test_profile_choice_reports_an_empty_search_beside_an_existing_profile(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    lookup: str,
) -> None:
    """Ein vorhandener Profilname darf den Hinweis einer erfolglosen Suche nicht verdecken."""
    from pathlib import Path

    from PySide6.QtWidgets import QToolButton

    from app.core.export import handover, slicer_profiles
    from app.ui import filament_picker as module

    executable = Path("prusa-slicer.exe")
    monkeypatch.setattr(module.discover, "find_programs", lambda *_args: [executable])
    monkeypatch.setattr(module.discover, "remembered_path", lambda *_args: str(executable))
    monkeypatch.setattr(module, "detect", lambda _path: handover.SlicerSetup(executable, "prusa"))

    def find(*_args, **_kwargs):
        if lookup == "broken":
            raise OSError("Unlesbarer Profilbestand")
        return []

    monkeypatch.setattr(slicer_profiles, "find_profiles", find)
    dialog = NewFilamentDialog(name="PETG", slicer_profile="Bestehendes PETG")
    heading = dialog.more_section.findChild(QToolButton, "sectionHeading")
    assert heading is not None
    heading.click()
    dialog.choose_profile.click()
    assert dialog.slicer_profile.text() == "Bestehendes PETG"
    assert dialog.validation.isVisibleTo(dialog)
    assert "Keine Filamentprofile" in dialog.validation.text()
    assert "Einstellungen" in dialog.validation.text()
    assert QApplication.overrideCursor() is None
    if lookup == "broken":
        assert "Unlesbarer Profilbestand" in caplog.text

    selected = slicer_profiles.SlicerProfile(Path("new.json"), "PETG Neu", "filament")
    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *_args, **_kwargs: [selected])
    monkeypatch.setattr(
        module.SlicerFilamentDialog, "exec", lambda _self: module.QDialog.DialogCode.Accepted
    )
    dialog.choose_profile.click()
    assert dialog.slicer_profile.text() == "PETG Neu"
    assert not dialog.validation.text()


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

    from PySide6.QtWidgets import QToolButton

    heading = dialog.more_section.findChild(QToolButton, "sectionHeading")
    assert heading is not None
    heading.click()

    assert dialog.slicer_profile.isVisibleTo(dialog), (
        "das Profil bleibt unter Weitere Angaben erreichbar"
    )
    assert dialog.choose_profile.isEnabled()
    assert dialog.clear_profile.isEnabled()

    dialog._clear_slicer_profile()

    assert dialog.slicer_profile.text() == ""
    assert not dialog.clear_profile.isEnabled()
    assert dialog.filament()[3] == "", "ohne Profil kommen die Werte aus Solidon allein"


def test_cancelling_a_new_filament_returns_to_the_previous_choice(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesamtreview 05.09.2026, UI-24: Nach einem Abbruch sprang die Auswahl
    auf die Zeile über „Neues Filament …" — den letzten freien Slot — statt
    auf die Spule, die vorher gewählt war. Der Operationsdialog las danach
    die falsche Nummer als Auftrag."""
    from PySide6.QtWidgets import QDialog

    field = FilamentField(
        1,
        slots=[
            MaterialSlot(index=1, name="PETG Rot", colour=(0.8, 0.1, 0.1)),
            MaterialSlot(index=3, name="PLA Blau", colour=(0.1, 0.1, 0.8)),
        ],
    )
    third = field.findData(3)
    field.setCurrentIndex(third)
    field._chosen(third)
    assert field.currentData() == 3
    monkeypatch.setattr(NewFilamentDialog, "exec", lambda _dialog: QDialog.DialogCode.Rejected)

    field._make_one(field.findData(NEW_FILAMENT))

    assert field.currentData() == 3, "zurück auf die vorige Wahl"


def test_every_spool_on_the_shelf_can_be_chosen_for_an_unpainted_body(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesamtreview 05.09.2026, UI-25: Beim Auflisten bekam jede Spule einen
    freien Slot vorgemerkt, und nach sieben brach die Schleife ab — die achte
    verschwand aus der Wahl, obwohl der Körper noch keine trug."""
    shelf = tuple(
        filaments.CatalogueFilament(name=f"Spule {index}", colour="#336699", material_type="PLA")
        for index in range(1, 9)
    )
    monkeypatch.setattr(filaments, "catalogue", lambda: shelf)

    field = FilamentField(0)

    names = [field.itemText(row) for row in range(field.count())]
    assert all(any(f"Spule {index}" in text for text in names) for index in range(1, 9)), names
    eighth = next(row for row in range(field.count()) if "Spule 8" in field.itemText(row))
    assert field.itemData(eighth) is None, "ohne vorgemerkte Nummer"
    assert field.model().item(eighth).isEnabled(), "aber wählbar — der Körper hat Platz"

    field._chosen(eighth)

    assert field.itemData(eighth) == 1, "beim Wählen bekommt sie die erste freie Nummer"


def test_same_print_filament_keeps_both_physical_spools_selectable(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Gleiche Druckwerte teilen den Slot, die Spulenauswahl bleibt ausdrücklich."""
    from app.ui.filament_picker import _ID_ROLE, spool_slot

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    first = filaments.save(filaments.CatalogueFilament("PLA", "#abcdef", "PLA", location="A"))
    second = filaments.save(filaments.CatalogueFilament("PLA", "#abcdef", "PLA", location="B"))
    slot = spool_slot(first, 3)
    field = FilamentField(3, slots=[slot])
    seen = []
    field.spoolChosen.connect(seen.append)
    first_row = field.findData(first.identifier, _ID_ROLE)
    second_row = field.findData(second.identifier, _ID_ROLE)
    assert first_row != second_row
    assert field.itemData(first_row) == field.itemData(second_row) == 3
    field._chosen(second_row)
    assert seen == [second]
    assert slot == spool_slot(first, 3)


def test_default_slot_does_not_pretend_a_catalogue_spool_was_chosen(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Die Slotvorgabe ist keine Zustimmung zur zufällig ersten Spule im Lager."""
    from app.ui.filament_picker import _ID_ROLE

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    entry = filaments.save(filaments.CatalogueFilament("PLA Rot", "#ff0000", "PLA"))
    field = FilamentField(1)
    assert field.currentData() == 1
    assert field.currentData(_ID_ROLE) is None
    assert entry.name not in field.currentText()
    assert "noch keines" in field.currentText()
    assert field.findData(entry.identifier, _ID_ROLE) >= 0


@pytest.mark.parametrize("change", ["rename", "archive", "remove"])
def test_stale_catalogue_choice_requires_a_new_explicit_choice(
    qt_app: QApplication, tmp_path, monkeypatch, change
) -> None:
    """Überholte Etiketten dürfen weder alte Druckwerte noch eine neue Bindung melden."""
    from dataclasses import replace

    from app.ui.filament_picker import _ID_ROLE

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    entry = filaments.save(filaments.CatalogueFilament("Alt", "#112233", "PLA"))
    field = FilamentField(0)
    row = field.findData(entry.identifier, _ID_ROLE)
    values, spools, notices = [], [], []
    field.filamentChosen.connect(lambda *args: values.append(args))
    field.spoolChosen.connect(spools.append)
    field.choiceNotice.connect(notices.append)
    if change == "rename":
        fresh = filaments.save(replace(entry, name="Neu", colour="#445566", material_type="PETG"))
    elif change == "archive":
        filaments.archive(entry.identifier)
    else:
        monkeypatch.setattr(filaments, "get", lambda _identifier: None)
    field.setCurrentIndex(row)
    field._chosen(row)
    assert not values
    assert not spools
    assert "erneut" in notices[-1]
    if change == "rename":
        row = field.findData(entry.identifier, _ID_ROLE)
        field.setCurrentIndex(row)
        field._chosen(row)
        assert values == [("Neu", "#445566", "PETG", "")]
        assert spools == [fresh]
        assert notices[-1] == ""


def test_full_body_offers_named_replacement_and_cancel_keeps_selection(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Die achte Belegung sperrt den Kunden nicht aus und ersetzt nichts ungefragt."""
    from PySide6.QtWidgets import QInputDialog

    from app.ui.filament_picker import _ID_ROLE

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    entry = filaments.save(filaments.CatalogueFilament("Neue Spule", "#abcdef"))
    field = FilamentField(
        3, slots=[MaterialSlot(index=index, name=f"Alte Spule {index}") for index in range(8)]
    )
    row = field.findData(entry.identifier, _ID_ROLE)
    seen = []
    field.spoolChosen.connect(seen.append)
    monkeypatch.setattr(QInputDialog, "getItem", lambda *_args: ("", False))
    field._chosen(row)
    assert not seen
    assert field.currentData() == 3

    def choose(_parent, _title, explanation, labels, _current, _editable):
        assert "Strg+Z" in explanation
        assert "bisherigen Flächen" in explanation
        return labels[5], True

    monkeypatch.setattr(QInputDialog, "getItem", choose)
    field.setCurrentIndex(row)
    field._chosen(row)
    assert field.currentData() == 5
    assert seen == [entry]

    body_field = FilamentField(
        3,
        slots=[MaterialSlot(index=index, name=f"Alt {index}") for index in range(8)],
        whole_body=True,
    )
    body_row = body_field.findData(entry.identifier, _ID_ROLE)
    monkeypatch.setattr(
        QInputDialog, "getItem", lambda *_args: pytest.fail("keine Tauschfrage für ganzen Körper")
    )
    body_field.setCurrentIndex(body_row)
    body_field._chosen(body_row)
    assert body_field.currentData() == 0
