"""Der Druckeinstellungsdialog (Bauplan §29, §2.4).

Offscreen wie alle Oberflächentests. Geprüft wird, was der Dialog verspricht:
jede Einstellung des Modells hat ein Feld, die Felder schreiben zurück, die
Vorschläge kommen mit Begründung, und ohne Slicer bleibt er benutzbar.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
)

from app.core.export import handover
from app.core.export.slicer_profiles import SlicerProfile
from app.core.knowledge import print_settings, profiles
from app.core.slice import gcode
from app.core.types import Feature
from app.ui.print_settings_dialog import (
    FIELD_WIDTH,
    FIELDS,
    GROUPS,
    PrintSettingsDialog,
    _ColourButton,
)
from app.ui.session import Session
from app.ui.settings import UiSettings


@pytest.fixture
def session(qt_app: QApplication) -> Session:
    return Session()


@pytest.fixture
def dialog(qt_app: QApplication, session: Session) -> PrintSettingsDialog:
    return PrintSettingsDialog(session, UiSettings())


# --- Vollständigkeit ----------------------------------------------------------------


def test_every_setting_in_the_model_has_a_field() -> None:
    """Eine Einstellung ohne Feld wäre eine, die der Nutzer nie zu sehen
    bekommt — und die er trotzdem an den Slicer schickt."""
    settings = print_settings.resolve(profiles.make_profile())
    covered = {field.path for field in FIELDS}

    for group in (
        "layers",
        "shell",
        "infill",
        "temperature",
        "cooling",
        "speed",
        "support",
        "adhesion",
        "retraction",
        "filament",
    ):
        section = getattr(settings, group)
        for name in section.__slots__:
            assert f"{group}.{name}" in covered, f"{group}.{name} hat kein Feld im Dialog"


def test_every_field_points_at_a_real_setting(dialog: PrintSettingsDialog) -> None:
    for field in FIELDS:
        print_settings.read_path(dialog.settings, field.path)


def test_every_field_lands_in_a_known_group() -> None:
    for field in FIELDS:
        assert field.group in GROUPS


def test_the_front_page_stays_short() -> None:
    """§2.4: vorn die zwei bis drei Werte, die man ändert. Wird das eine
    zweite vollständige Liste, ist die gestufte Tiefe verloren."""
    front = [field for field in FIELDS if field.front]
    assert 3 <= len(front) <= 10


# --- Werte hin und zurück -----------------------------------------------------------


def test_the_editors_start_on_the_resolved_values(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["layers.layer_height"]
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.value() == pytest.approx(dialog.settings.layers.layer_height)


def test_a_speed_survives_being_shown(dialog: PrintSettingsDialog) -> None:
    """Ein Feld, das einen Wert nur anzeigt, darf ihn nicht verändern.

    Die Bahngeschwindigkeiten standen auf null Nachkommastellen. Das ist keine
    Frage der Anzeige: der Wert, den ``advise`` aus dem Volumenstrom errechnet,
    ist selten glatt — bei 5 mm³/s, 0,2 mm Schicht und 0,42 mm Bahn sind es
    59,52 mm/s. Gerundet auf 60 fördert die Düse 5,04 mm³/s, und damit stand
    allein durch das Öffnen des Fensters mehr in der Datei, als das Material
    verträgt.
    """
    genau = 59.52380952380952
    dialog.settings = replace(
        dialog.settings, speed=replace(dialog.settings.speed, outer_wall=genau)
    )
    dialog._load_into_editors()

    zurueck = dialog._collect().speed.outer_wall

    fluss = dialog.settings.layers.layer_height * dialog.settings.layers.line_width
    assert zurueck * fluss <= dialog.settings.filament.max_flow + 1e-9, (
        "der angezeigte Wert darf den Volumenstrom des Materials nicht überschreiten"
    )
    assert zurueck == pytest.approx(genau, abs=0.05), "und er bleibt bei dem, was er war"


def test_choosing_a_filament_adopts_its_values(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Wer eine Spule wählt, bekommt ihre Werte — auch den Volumenstrom.

    Solidon kennt „PETG" und bringt 10 mm³/s mit; Elegoo PETG PRO fährt 5.
    Ohne diese Übernahme rechnet die Beratung gegen eine Grenze, die das
    eingelegte Material nicht hat.
    """
    datei = tmp_path / "Spule.json"
    datei.write_text(
        json.dumps(
            {
                "name": "Spule",
                "nozzle_temperature": ["255"],
                "hot_plate_temp": ["75"],
                "filament_max_volumetric_speed": ["5"],
            }
        ),
        encoding="utf-8",
    )
    dialog.filament_choice.addItem("Spule", str(datei))
    dialog.filament_choice.setCurrentIndex(dialog.filament_choice.count() - 1)

    dialog._filament_chosen(dialog.filament_choice.currentIndex())

    assert dialog.settings.filament.max_flow == 5.0
    assert dialog.settings.temperature.nozzle == 255
    assert dialog.settings.temperature.bed == 75


def test_filling_the_filament_list_changes_nothing(dialog: PrintSettingsDialog) -> None:
    """Was ein Projekt mitbringt, gilt.

    Die Liste wird beim Öffnen befüllt und dabei eine Vorauswahl gesetzt. Käme
    daraus eine Übernahme, überschriebe allein das Aufgehen des Fensters die
    Einstellungen des Projekts — eine Dichtung aus TPU wäre danach keine mehr.
    Deshalb hängt die Übernahme an ``activated`` (der Wahl eines Menschen) und
    nicht an ``currentIndexChanged``.
    """
    vorher = dialog.settings

    dialog._fill_filaments(None)

    assert dialog.settings is vorher, "das Befüllen der Liste ändert keine Einstellung"


def test_changing_a_field_reaches_the_settings(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["shell.wall_count"]
    assert isinstance(editor, QSpinBox)

    editor.setValue(7)

    assert dialog.settings.shell.wall_count == 7


def test_changing_the_quality_reloads_every_field(dialog: PrintSettingsDialog) -> None:
    before = dialog.settings.layers.layer_height
    index = dialog.quality.findData("fine")
    assert index >= 0

    dialog.quality.setCurrentIndex(index)

    assert dialog.settings.quality == "fine"
    assert dialog.settings.layers.layer_height != before
    editor = dialog._editors["layers.layer_height"]
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.value() == pytest.approx(dialog.settings.layers.layer_height)


def test_the_colour_button_says_which_colour_it_is(qt_app: QApplication) -> None:
    """Regel 18: die Farbe allein trägt die Bedeutung nicht.

    Getragen hat sie bisher der Hexwert — richtig als zweite Kodierung und
    trotzdem schwach: „#4A90D9" beschreibt für niemanden eine Spule im Regal.
    Der Name tut beides, und die Zahl steht im Tooltip, wo sie hingehört.

    Die `QApplication` steht nicht aus Gewohnheit in der Signatur: Ein Widget
    ohne sie bringt den ganzen Lauf zum Absturz, und `pytest-randomly`
    entscheidet, ob vorher ein anderer Test eine gebaut hat.
    """
    button = _ColourButton("#3FAE6B")
    assert button.text() == "Grün"
    assert "3FAE6B" in button.toolTip().upper(), "genau bleibt genau"

    button.set_value("#112233")
    assert button.text() == "Schwarz"
    assert "112233" in button.toolTip().upper()


def test_a_checkbox_writes_through(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["shell.outer_wall_first"]
    assert isinstance(editor, QCheckBox)

    editor.setChecked(True)

    assert dialog.settings.shell.outer_wall_first is True


def test_an_enum_writes_through(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["support.style"]
    assert isinstance(editor, QComboBox)

    editor.setCurrentIndex(editor.findData("tree"))

    assert dialog.settings.support.style == "tree"


def test_an_enum_shows_words_and_stores_the_english_value(dialog: PrintSettingsDialog) -> None:
    """§4.1: der gespeicherte Wert geht in die Projektdatei und zum Slicer und
    bleibt englisch; gezeigt wird die Übersetzung."""
    editor = dialog._editors["infill.pattern"]
    assert isinstance(editor, QComboBox)

    index = editor.findData("gyroid")
    assert index >= 0
    editor.setCurrentIndex(index)

    assert dialog.settings.infill.pattern == "gyroid"
    assert editor.itemData(editor.findData("grid")) == "grid"
    assert editor.itemText(editor.findData("grid")) != "grid", "Gitter, nicht grid"


def test_every_choice_entry_says_what_it_does(dialog: PrintSettingsDialog) -> None:
    """Der Name benennt, der Satz erklärt — an jedem Eintrag jeder Auswahl.

    „Gyroid" oder „Baumstruktur" sagen einem Kunden nicht, wann er sie wählen
    soll; der Satz aus ``choice_note`` tut es, als Tooltip über der offenen
    Liste und als ``AccessibleDescriptionRole`` für den Bildschirmleser.
    Geprüft über **alle** Enum-Felder, nicht an einem Beispiel: fünfzehn
    erklärte Einträge von siebenundsechzig wären schlimmer als keine.
    """
    from app.ui.labels import choice_note

    missing = []
    for field in FIELDS:
        if field.kind != "enum":
            continue
        editor = dialog._editors[field.path]
        assert isinstance(editor, QComboBox)
        for index in range(editor.count()):
            value = editor.itemData(index)
            note = choice_note(value)
            if note is None:
                continue
            if editor.itemData(index, Qt.ItemDataRole.ToolTipRole) != note:
                missing.append(f"{field.path}: {value!r} ohne Tooltip")
            if editor.itemData(index, Qt.ItemDataRole.AccessibleDescriptionRole) != note:
                missing.append(f"{field.path}: {value!r} ohne AccessibleDescription")

    assert not missing, "Auswahlwerte ohne Satz am Eintrag:\n" + "\n".join(missing)


def test_slicing_greys_out_before_the_click_when_the_licence_ran_out(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Lizenzgrenze steht vor dem Klick, nicht hinter dem Dialog.

    `handover.slice_model` fragt `activation.require` erst im Arbeiter — mit
    abgelaufener Demo füllte der Kunde den ganzen Dialog aus, drückte
    *Slicen* und bekam dann die Absage (Regel 19). Von den vier Grenzen war
    SLICER die einzige ohne Ausgrauen; CHANGE, EXPORT und CHAT hatten es.
    Der Slicer-Pfad wird gesetzt, damit der Knopf nicht aus dem falschen
    Grund grau ist.
    """
    from app.core import activation

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog._slicer_path = Path("fake-slicer")
    dialog._show_slicer_state()

    assert not dialog.slice_button.isEnabled(), "abgelaufen sperrt vor dem Klick"
    reason = dialog.slice_button.toolTip()
    assert reason, "der Grund steht am Knopf"
    assert dialog.slice_button.statusTip() == reason
    assert dialog.slice_button.accessibleDescription() == reason

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=5))
    dialog._show_slicer_state()

    assert dialog.slice_button.isEnabled(), "Testzeitraum plus Slicer heißt frei"
    assert not dialog.slice_button.toolTip()


def test_slicing_greys_out_until_the_profiles_are_chosen(
    qt_app: QApplication, session: Session
) -> None:
    """Die dritte Hürde derselben Bauart: Profilwahl vor dem Klick.

    Ein Slicer der Orca-Familie ohne gewähltes Drucker- und Prozessprofil
    lehnt jeden Auftrag ab — das stand bisher erst **nach** dem Klick in der
    Statuszeile, der Knopf blieb aktiv (Fund ce, 26.08.2026: Klick ohne
    sichtbare Folge, Prüfstand hing). Der Knopf kennt jetzt die Stufen:
    Suche läuft, Drucker fehlt, Prozess fehlt, frei — und der Grund am Knopf
    ist wörtlich derselbe Satz wie der Wächter in `_slice` (eine Quelle).
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog._slicer_path = Path("fake-orca")
    dialog._needs_profiles = True
    dialog._profiles_pending = True
    dialog._show_slicer_state()

    assert not dialog.slice_button.isEnabled()
    assert "durchgesehen" in dialog.slice_button.toolTip(), "laufende Suche heißt warten"

    dialog._profiles_pending = False
    dialog._show_slicer_state()

    assert not dialog.slice_button.isEnabled()
    assert dialog.slice_button.toolTip() == dialog._machine_missing_line()
    assert dialog.slice_button.statusTip() == dialog.slice_button.toolTip()

    dialog.machine_choice.addItem("Drucker", "m1")
    dialog.machine_choice.setCurrentIndex(0)

    assert not dialog.slice_button.isEnabled()
    assert dialog.slice_button.toolTip() == dialog._process_missing_line()

    dialog.process_choice.addItem("Prozess", "p1")
    dialog.process_choice.setCurrentIndex(0)

    assert dialog.slice_button.isEnabled(), "beide Profile gewählt heißt frei"
    assert not dialog.slice_button.toolTip()


def test_a_share_is_shown_in_percent_and_stored_as_a_fraction(
    dialog: PrintSettingsDialog,
) -> None:
    """Ein Feld mit [%] und einer 0,15 darin ist falsch beschriftet — der Kern
    rechnet in Anteilen, die Werkstatt spricht in Prozent."""
    editor = dialog._editors["infill.density"]
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.value() == pytest.approx(dialog.settings.infill.density * 100.0)

    editor.setValue(35.0)

    assert dialog.settings.infill.density == pytest.approx(0.35)


def test_the_close_button_speaks_german(dialog: PrintSettingsDialog) -> None:
    """Regel 20: Qt beschriftet seine Standardknöpfe selbst — auch der Text
    muss durch tr() gehen."""
    from PySide6.QtWidgets import QDialogButtonBox

    boxes = dialog.findChildren(QDialogButtonBox)
    close = next(
        button
        for box in boxes
        if (button := box.button(QDialogButtonBox.StandardButton.Close)) is not None
    )
    assert close.text() == "Schließen"


# --- Vorschläge ---------------------------------------------------------------------


def test_the_advice_list_names_a_reason(qt_app: QApplication) -> None:
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())

    assert dialog.advice_view.topLevelItemCount() > 0
    first = dialog.advice_view.topLevelItem(0)
    assert first is not None
    assert first.text(2), "die dritte Spalte ist der Grund, und sie darf nicht leer sein"


def test_applying_the_advice_moves_the_editors(qt_app: QApplication) -> None:
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())
    before = dialog.settings.speed.outer_wall

    dialog._apply_advice()

    assert dialog.settings.speed.outer_wall < before
    editor = dialog._editors["speed.outer_wall"]
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.value() == pytest.approx(dialog.settings.speed.outer_wall)


def test_the_layer_analysis_may_arrive_after_the_dialog(qt_app: QApplication) -> None:
    """§2.8: Der Dialog geht sofort auf, die Schichtanalyse wird nachgereicht.

    Vorher wartete der Weg hierher bis zu zwei Sekunden auf sie — mit
    stehendem Fenster und ohne dass irgendwo stand, worauf. Beides ist zu
    haben: Was aus der Geometrie folgt, steht ein paar Zehntel später in der
    Liste, statt den ganzen Dialog aufzuhalten.
    """
    import math

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.geom.transform import place_on_bed
    from app.core.slice.analysis import slice_body

    session = Session()
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.slice_result is None
    before = {
        str(dialog.advice_view.topLevelItem(row).data(0, Qt.ItemDataRole.UserRole))
        for row in range(dialog.advice_view.topLevelItemCount())
    }

    # Ein Kegel auf der Spitze: 63 Grad Wand, also Stützen — ein Vorschlag,
    # den allein die Geometrie hergibt.
    cone = trimesh.creation.cone(radius=20.0, height=10.0, sections=64)
    cone.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]))
    dialog.take_slice_result(slice_body(place_on_bed(MeshData.of(cone)), 0.5))

    after = {
        str(dialog.advice_view.topLevelItem(row).data(0, Qt.ItemDataRole.UserRole))
        for row in range(dialog.advice_view.topLevelItemCount())
    }
    assert dialog.slice_result is not None
    assert after - before, "die nachgereichte Analyse hat die Vorschlagsliste nicht erreicht"


def test_a_missing_layer_analysis_changes_nothing(dialog: PrintSettingsDialog) -> None:
    """Ein ``None`` ist keine Analyse, sondern ihr Ausbleiben — dann bleibt es
    bei dem, was aus Material und Maschine folgt."""
    dialog.take_slice_result(None)

    assert dialog.slice_result is None


def test_the_advice_list_is_never_empty_of_words(dialog: PrintSettingsDialog) -> None:
    """Auch wenn nichts einzuwenden ist, steht das da — eine leere Liste sähe
    aus wie ein Fehler."""
    dialog._refresh_advice()

    assert dialog.advice_view.topLevelItemCount() >= 1
    first = dialog.advice_view.topLevelItem(0)
    assert first is not None and first.text(0)


# --- Aussehen und gestufte Tiefe ----------------------------------------------------


def test_no_field_stretches_across_the_whole_dialog(dialog: PrintSettingsDialog) -> None:
    """Ein Wert wie 0,200 stand in einem 726 Bildpunkte breiten Kasten.

    Ein `QFormLayout` gibt der Spalte der Editoren allen Platz, den es hat —
    gemessen waren das im Kasten „Das Wichtigste" 726 von 970 Bildpunkten je
    Zeile. Die Zahl links, ihre Beschriftung eine Handbreit daneben, und acht
    solche Zeilen sind das erste, was jemand von diesem Dialog sieht.

    Gemessen wird am gezeigten Fenster und nicht an `maximumWidth`: Dass eine
    Grenze gesetzt ist, heißt nicht, dass das Layout sie einhält.
    """
    dialog.resize(960, 760)
    dialog.show()
    QApplication.processEvents()

    assert dialog.width() >= 900, "der Test taugt nur an einem breiten Fenster"
    too_wide = []
    for path, editor in dialog._editors.items():
        limit = FIELD_WIDTH.get(dialog._fields[path].kind)
        if limit is None:
            continue
        allowed = max(limit, editor.sizeHint().width())
        if editor.width() > allowed:
            too_wide.append(f"{path}: {editor.width()} statt höchstens {allowed}")
    assert not too_wide, "\n".join(too_wide)


def test_the_deeper_settings_fold_away_instead_of_greying_out(
    dialog: PrintSettingsDialog,
) -> None:
    """„Weitere Einstellungen ☐" sagt nicht „zugeklappt", es sagt „aus".

    Dieselbe Anwendung hat das an zwei anderen Stellen schon entschieden — der
    Operationsdialog und der Generierungsdialog nehmen den Umschalter mit dem
    Dreieck aus `panels.collapsible`. Hier standen zwei ankreuzbare Gruppen:
    „Weitere Einstellungen" und „Profile des Slicers", letztere über drei
    grauen Auswahlfeldern, was sich wie eine Sperre liest.
    """
    dialog.show()
    QApplication.processEvents()

    gruppen = dialog.findChildren(QGroupBox)
    # **Ohne diese Zeile prüft die nächste nichts.** Findet ``findChildren``
    # keine Gruppe, ist ``checkable`` leer und die Zusicherung darunter grün —
    # sie sagt dann nicht „keine ist ankreuzbar", sondern „es gibt keine".
    # Gemessen sind es zwei („Das Wichtigste", „Was dieses Teil verlangt");
    # geprüft wird trotzdem nur, **dass** es welche gibt, denn eine Zahl hier
    # altert mit der nächsten Gruppe (3d-druck-33).
    assert gruppen, "keine Gruppe im Dialog — dann sagt die Prüfung darunter nichts"
    checkable = [box.title() for box in gruppen if box.isCheckable()]
    assert not checkable, f"ankreuzbar statt aufklappbar: {checkable}"

    for toggle, content in ((dialog.tabs_toggle, dialog.tabs), (dialog.slicer_toggle, None)):
        assert toggle is not None, "ohne Umschalter kommt niemand an den Inhalt"
        assert toggle.arrowType() == Qt.ArrowType.RightArrow, toggle.text()
        assert not toggle.isChecked(), "zu ist der Anfangszustand (§2.4)"
        if content is not None:
            assert not content.isVisibleTo(dialog), "zugeklappt heißt weg, nicht grau"

    dialog.tabs_toggle.setChecked(True)
    QApplication.processEvents()
    assert dialog.tabs.isVisibleTo(dialog)
    assert dialog.tabs_toggle.arrowType() == Qt.ArrowType.DownArrow


def test_a_hint_that_points_into_a_folded_section_opens_it(
    dialog: PrintSettingsDialog,
) -> None:
    """Drei Hinweise zeigen auf die Profilauswahl. Zugeklappt wäre das ein
    Rat, dem man nicht folgen kann."""
    dialog._open_slicer_section()

    assert dialog.slicer_toggle is not None
    assert dialog.slicer_toggle.isChecked()
    assert dialog.slicer_inner.isVisibleTo(dialog.slicer_box)


def test_every_field_says_what_it_does(dialog: PrintSettingsDialog) -> None:
    """Sechsundfünfzig Felder, und keines erklärte sich.

    „Naht", „Bahnerzeuger", „Genaue Außenwand", „Flussverhältnis" — wer diese
    Wörter kennt, braucht den Dialog nicht, und wer sie nicht kennt, findet
    hier nichts, was ihn hineinlässt. Der Satz steht am Feld und ist keine
    Wiederholung des Titels: Er sagt, was passiert, wenn man den Wert bewegt.
    """
    stumm = [field.path for field in FIELDS if not field.note]
    assert not stumm, f"ohne Erklärung: {stumm}"

    schlecht = []
    for field in FIELDS:
        satz = str(field.note)
        if not satz.endswith((".", "!", "?")):
            schlecht.append(f"{field.path}: kein Satz — {satz!r}")
        if satz.strip().lower() == str(field.title).strip().lower():
            schlecht.append(f"{field.path}: nur der Titel wiederholt")
        if len(satz) > 220:
            schlecht.append(f"{field.path}: {len(satz)} Zeichen sind kein Tooltip mehr")
    assert not schlecht, "\n".join(schlecht)


def test_the_explanation_arrives_at_the_field_and_at_its_label(
    dialog: PrintSettingsDialog,
) -> None:
    """Am Feld, an der Beschriftung und in der Statuszeile.

    Wer eine Zeile nicht versteht, zeigt auf ihre Beschriftung — dort steht das
    unverständliche Wort. Ein Tooltip nur am Eingabefeld findet, wer schon
    weiß, wohin er greifen muss. Und ``accessibleDescription`` ist derselbe
    Satz für den, der den Bildschirm nicht liest.
    """
    fehlt = []
    for field in FIELDS:
        editor = dialog._editors[field.path]
        satz = str(field.note)
        if satz not in editor.toolTip():
            fehlt.append(f"{field.path}: Tooltip {editor.toolTip()!r}")
        # Der Farbknopf nennt zuerst den Hexwert und hängt den Satz an: der
        # Wert ist am Knopf nirgends sonst zu lesen, auf ihm steht der Name.
        # Der Satz darf ihn nicht verdrängen — beides oder keins.
        if isinstance(editor, _ColourButton) and "#" not in editor.toolTip():
            fehlt.append(f"{field.path}: der Farbwert ist aus dem Tooltip gefallen")
        if editor.statusTip() != satz:
            fehlt.append(f"{field.path}: statusTip {editor.statusTip()!r}")
        if editor.accessibleDescription() != satz:
            fehlt.append(f"{field.path}: accessibleDescription fehlt")
    assert not fehlt, "\n".join(fehlt)

    beschriftungen = 0
    stumm = []
    for form in dialog.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            widget = item.widget() if item is not None else None
            if not isinstance(widget, QLabel):
                continue
            titel = widget.text().split(" [")[0]
            if titel not in {str(f.title) for f in FIELDS}:
                continue  # Drucker, Grundprofil, Filament — keine Einstellung
            beschriftungen += 1
            if not widget.toolTip():
                stumm.append(titel)
    assert not stumm, f"Beschriftung ohne Erklärung: {stumm}"
    assert beschriftungen >= 8, f"nur {beschriftungen} Beschriftungen gefunden"


def test_a_dialog_built_after_a_language_change_speaks_that_language(
    qt_app: QApplication, session: Session
) -> None:
    """Sechsundfünfzig Felder standen deutsch in einem englischen Fenster.

    ``FIELDS`` ist ein Modulrumpf, und ``tr()`` darin übersetzte **beim
    Import** — also in der Sprache, die zu diesem Zeitpunkt galt, und beim
    Start ist das noch keine. ``main_window.py`` zieht dieses Modul auf
    Modulebene nach, ``install_language`` läuft danach; und ein Sprachwechsel
    zur Laufzeit (``app.rebuild_for_language``) baut die **Fenster** neu auf,
    nicht die Module. Der größte Dialog der Anwendung blieb damit in der
    Startsprache.

    **Beide Schritte, sonst misst der Test seinen eigenen Aufbau**:
    ``install_language`` lädt den Katalog, ``set_language`` schaltet ihn
    scharf. Wer nur den zweiten ruft, bekommt überall die Message-ID zurück —
    also Deutsch — und hält den Rückfall für den Fehler.

    ``source_text`` gibt die Message-ID (den deutschen Quelltext), ``tr`` die
    Fassung in der jetzt gültigen Sprache: Damit braucht der Test keinen
    einzigen englischen Satz als Literal und altert nicht mit dem Katalog.
    """
    from app.i18n import get_language, set_language, source_text, tr
    from app.i18n.catalog import install_language

    vorher = get_language()
    try:
        install_language("en")
        set_language("en")

        gewandert = 0
        stehengeblieben = []
        for field in FIELDS:
            for teil, wert in (("Titel", field.title), ("Satz", field.note)):
                deutsch = source_text(wert)
                if not deutsch:
                    continue
                englisch = tr(deutsch)
                if englisch != deutsch:
                    gewandert += 1
                if str(wert) != englisch:
                    stehengeblieben.append(f"{field.path} ({teil}): {str(wert)!r}")
        assert not stehengeblieben, "in der Startsprache hängengeblieben:\n" + "\n".join(
            stehengeblieben
        )
        # Ohne diese Zusicherung wäre der Test auch dann grün, wenn der
        # englische Katalog gar nicht angekommen ist: Dann ist jede
        # Übersetzung gleich ihrer Message-ID, und die Schleife oben findet
        # nichts (`tests.md`, „Ein Verbotstest über eine leere Menge").
        assert gewandert >= 100, f"nur {gewandert} übersetzte Texte — kam der Katalog an?"

        # Und am gebauten Fenster, nicht nur an der Tabelle: Der Dialog liest
        # die Texte in ``_label`` und ``_editor``, und dort muss das ``str()``
        # stehen.
        gebaut = PrintSettingsDialog(session, UiSettings())
        hoehe = next(f for f in FIELDS if f.path == "layers.layer_height")
        texte = {label.text() for label in gebaut.findChildren(QLabel)}
        assert f"{tr(source_text(hoehe.title))} [mm]" in texte
        assert f"{source_text(hoehe.title)} [mm]" not in texte
        assert gebaut._editors[hoehe.path].statusTip() == tr(source_text(hoehe.note))
    finally:
        set_language(vorher)


def test_a_freshly_built_colour_row_carries_both(dialog: PrintSettingsDialog) -> None:
    """Am gebauten Dialog rettet ``_load_into_editors`` den Tooltip.

    Es ruft ``set_value`` und damit ``_refresh``, und der schreibt den Tooltip
    neu — der Hexwert wäre auch da, wenn ``_editor`` ihn vorher überschrieben
    hätte. Geprüft wird deshalb die Zeile, wie ``_editor`` sie verlässt: Dort
    liegt der Wächter, und dort fällt der Wert weg, wenn ihn jemand entfernt.
    """
    field = next(f for f in FIELDS if f.path == "filament.colour")

    editor = dialog._editor(field)

    assert isinstance(editor, _ColourButton)
    assert "#" in editor.toolTip(), "der Farbwert steht nirgends sonst"
    assert str(field.note) in editor.toolTip()


def test_the_colour_button_keeps_its_value_and_its_sentence(qt_app: QApplication) -> None:
    """Der eine Knopf, der seinen Tooltip selbst schreibt.

    Er trägt den Namen der Farbe und im Tooltip ihren Hexwert — den steht
    sonst nirgends. Nach jedem Klick baut ``_refresh`` den Tooltip neu; ein von
    außen gesetzter Satz wäre danach weg.
    """
    button = _ColourButton("#4a90d9", None, note="Die Farbe für die Vorschau.")

    assert "#4A90D9" in button.toolTip()
    assert "Die Farbe für die Vorschau." in button.toolTip()

    button.set_value("#101010")
    assert "#101010".upper() in button.toolTip()
    assert "Die Farbe für die Vorschau." in button.toolTip()


# --- ohne Slicer --------------------------------------------------------------------


def test_the_dialog_opens_without_a_slicer(
    monkeypatch: pytest.MonkeyPatch, session: Session
) -> None:
    """§27: das Backend meldet sich ab, es nörgelt nicht — die Einstellungen
    bleiben trotzdem pflegbar."""
    monkeypatch.setattr("app.core.discover.find_program", lambda *args, **kwargs: None)

    dialog = PrintSettingsDialog(session, UiSettings())

    assert not dialog.slice_button.isEnabled()
    assert dialog.state.text()
    assert dialog._editors["layers.layer_height"].isEnabled()


def test_slicing_without_a_scene_says_what_is_missing(dialog: PrintSettingsDialog) -> None:
    dialog._slice()
    assert dialog.state.text()


class WaitingWorker:
    """Ein Arbeiter, der nur Buch führt: läuft, bis jemand auf ihn wartet.

    Der echte startet nur, wenn ein Slicer installiert ist und zur
    Orca-Familie gehört — ein Test, der das voraussetzt, prüft die Maschine des
    Bauservers.
    """

    def __init__(self) -> None:
        self.waited: list[int | None] = []
        self.cancelled = False

    def isRunning(self) -> bool:  # noqa: N802 — Qt gibt den Namen vor
        return not self.waited

    def cancel(self) -> None:
        self.cancelled = True

    def wait(self, timeout_ms: int | None = None) -> bool:
        self.waited.append(timeout_ms)
        return True


def test_every_way_out_waits_for_the_profile_search(dialog: PrintSettingsDialog) -> None:
    """Ein Thread, der sein Fenster überlebt, nimmt den Prozess mit.

    Der Dialog wartete im ``closeEvent`` — und das kommt nur, wenn das Fenster
    geschlossen wird. *Slicen* und *Abbrechen* gehen über ``done``, und Qt
    schickt dabei kein Schließereignis: Gemessen lief die Profilsuche nach
    ``accept()`` weiter, während der Aufrufer seine Referenz fallen ließ.

    Der dritte Weg ist der der Suite: Dort wird ein Dialog **weggeräumt**, nicht
    geschlossen. Die Aufräumhilfe in ``tests/conftest.py`` sucht dafür
    ``wait_for_workers`` an jedem obersten Fenster — ein Dialog ohne diesen
    Namen bleibt unbeachtet, mit laufendem Arbeiter.
    """
    worker = WaitingWorker()
    dialog._profile_worker = worker  # type: ignore[assignment]

    dialog.accept()

    assert worker.waited, "der Knopf ging hinaus, ohne auf die Suche zu warten"

    second = PrintSettingsDialog(dialog.session, UiSettings())
    later = WaitingWorker()
    second._profile_worker = later  # type: ignore[assignment]
    try:
        second.wait_for_workers()
        assert later.waited, "und weggeräumt wird auch gewartet"
        assert later.waited[0] is not None, "dort mit Grenze — ein hängender Arbeiter fällt auf"
    finally:
        second.deleteLater()


def test_a_slicer_without_profiles_gets_a_way_out(dialog: PrintSettingsDialog) -> None:
    """Regel 17: „Keine Profile gefunden — ohne sie lehnt dieser Slicer den
    Auftrag ab." war die ganze Auskunft.

    Ein Satz über den Zustand, und dann nichts. Wer einen Slicer gerade
    installiert hat, hat genau diesen Zustand — die Profile entstehen erst,
    wenn er einmal gelaufen ist und einen Drucker kennt. Das steht jetzt dabei.

    Geprüft wird an der Zahl der Sätze und nicht am Wortlaut: ein Text, den
    der Test buchstäblich mitliest, prüft sich selbst.
    """
    dialog._profiles_found([])

    note = dialog.profile_note.text()
    assert note, "ohne Profile bleibt der Hinweis vom Suchen stehen"
    sentences = [part for part in note.replace("!", ".").split(".") if part.strip()]
    assert len(sentences) >= 2, f"der Hinweis endet bei der Feststellung: {note!r}"
    assert not dialog.machine_choice.isEnabled(), "und die Auswahl bleibt leer und gesperrt"


def test_both_orca_profiles_are_asked_for_before_the_run(qt_app: QApplication) -> None:
    """Die Orca-Familie braucht zwei Profile, geprüft wurde nur eines.

    Ohne Prozessprofil hat Solidons Datei kein Systemprofil, auf das sie sich
    legen kann (siehe `handover._orca_process`), und der Slicer bricht ab,
    bevor er das Modell ansieht. Gemessen gegen ElegooSlicer 1.5.3.4: mit dem
    Systemprofil darunter läuft derselbe Aufruf durch, ohne es endet er in
    „Der Slicer hat keine Druckdatei geschrieben" — ein Satz über das Ende,
    nicht über die Ursache.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "app" / "ui" / "print_settings_dialog.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    guarded: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        condition = ast.unparse(node.test)
        if "setup.flavour" not in condition:
            continue
        for field in ("machine_profile", "base_process"):
            if f"setup.{field}" in condition:
                guarded.add(field)

    assert guarded == {"machine_profile", "base_process"}, (
        f"nur diese Profile werden vor dem Lauf verlangt: {sorted(guarded)}"
    )


# --- was bleibt, wenn der Dialog zugeht ---------------------------------------------


def test_the_chosen_profiles_are_kept_without_a_slicer_run(qt_app: QApplication) -> None:
    """Was im Dialog stand, gilt auch für den Export (§29, A5).

    Gemerkt wurde die Profilwahl nur beim **Slicen**. Wer sie hier einstellte
    und danach über *Datei → Exportieren* eine 3MF schrieb, bekam die Auswahl
    vom vorletzten Mal — für den Nutzer ist es dieselbe Entscheidung, und der
    Docstring von ``remembered_setup`` verspricht sie.
    """
    settings = UiSettings()
    session = Session()
    dialog = PrintSettingsDialog(session, settings)
    dialog.machine_choice.addItem("Centauri", "C:/profile/machine/centauri.json")
    dialog.machine_choice.setCurrentIndex(dialog.machine_choice.count() - 1)
    dialog.process_choice.addItem("0.20 fein", "C:/profile/process/fein.json")
    dialog.process_choice.setCurrentIndex(dialog.process_choice.count() - 1)
    dialog.filament_choice.addItem("PETG PRO", "C:/profile/filament/petg-pro.json")
    dialog.filament_choice.setCurrentIndex(dialog.filament_choice.count() - 1)

    dialog.reject()

    assert settings.slicer_machine_profile == "C:/profile/machine/centauri.json"
    assert settings.slicer_base_process == "C:/profile/process/fein.json"
    assert settings.slicer_base_filament == "C:/profile/filament/petg-pro.json"
    assert settings.slicer_profile_printer == session.profile.printer.id
    assert (
        settings.slicer_filament_per_material[session.profile.material.id]
        == "C:/profile/filament/petg-pro.json"
    )


def test_closing_early_does_not_wipe_what_was_remembered(qt_app: QApplication) -> None:
    """Die Profilsuche läuft im Hintergrund.

    Wer den Dialog vorher wieder zumacht, hat eine leere Auswahl vor sich —
    sie zu übernehmen hieße, eine gemerkte Einstellung zu löschen, weil
    niemand hingesehen hat.
    """
    settings = UiSettings()
    settings.slicer_machine_profile = "C:/profile/machine/centauri.json"
    settings.slicer_base_process = "C:/profile/process/fein.json"
    dialog = PrintSettingsDialog(Session(), settings)

    dialog.reject()

    assert settings.slicer_machine_profile == "C:/profile/machine/centauri.json"
    assert settings.slicer_base_process == "C:/profile/process/fein.json"


def _pretend_a_slicer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein gefundener Slicer, ohne einen auf der Maschine zu verlangen."""
    from app.ui import print_settings_dialog as module

    monkeypatch.setattr(
        module.discover, "find_program", lambda *args, **kwargs: Path("elegoo-slicer.exe")
    )
    monkeypatch.setattr(
        module.handover,
        "detect",
        lambda found: handover.SlicerSetup(executable=found, flavour="orca"),
    )


def test_a_profile_of_another_printer_is_not_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A6: Ein Maschinenprofil gehört zu genau einem Drucker.

    Ohne diesen Abgleich trägt die 3MF eines Prusa-Projekts das Profil des
    Elegoo, mit dem zuletzt gearbeitet wurde — richtig gerechnet, falsch
    adressiert. Schlimmer als gar keines: Die Datei sieht vollständig aus.
    """
    from app.ui.print_settings_dialog import remembered_setup

    _pretend_a_slicer(monkeypatch)
    settings = UiSettings()
    settings.slicer_machine_profile = "Centauri Carbon 0.4"
    settings.slicer_profile_printer = "centauri-carbon"

    assert remembered_setup(settings, "petg", "prusa-mk4") is None, "anderer Drucker, nichts gilt"

    same = remembered_setup(settings, "petg", "centauri-carbon")
    assert same is not None
    assert same.machine_profile == "Centauri Carbon 0.4", "derselbe Drucker, alles gilt"


def test_an_old_settings_file_still_carries_its_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne Vermerk wird nicht verglichen.

    Eine Einstellung aus einer älteren Version kennt den Drucker nicht, für
    den sie gewählt wurde. Sie deshalb zu verwerfen wäre eine Verschlechterung
    für jeden, der schon eingerichtet hat.
    """
    from app.ui.print_settings_dialog import remembered_setup

    _pretend_a_slicer(monkeypatch)
    settings = UiSettings()
    settings.slicer_machine_profile = "Centauri Carbon 0.4"

    setup = remembered_setup(settings, "petg", "prusa-mk4")
    assert setup is not None
    assert setup.machine_profile == "Centauri Carbon 0.4"


def test_the_project_settings_win_over_the_preset(qt_app: QApplication) -> None:
    """§29: was eingestellt wurde, gilt beim nächsten Öffnen weiter — sonst
    wäre der Dialog eine Sitzung lang gültig und danach vergessen."""
    session = Session()
    stored = print_settings.with_path(
        print_settings.resolve(session.profile), "shell.wall_count", 9
    )
    session.project.document.print_settings = stored

    dialog = PrintSettingsDialog(session, UiSettings())

    assert dialog.settings.shell.wall_count == 9


def test_a_project_without_settings_falls_back_to_the_preset(dialog: PrintSettingsDialog) -> None:
    """Kein eigener Satz heißt „noch nichts entschieden", nicht „alles null"."""
    assert dialog.settings.shell.wall_count > 0


def test_the_session_takes_the_settings_and_marks_the_project(qt_app: QApplication) -> None:
    session = Session()
    changed = print_settings.with_path(
        print_settings.resolve(session.profile), "infill.density", 0.42
    )

    session.set_print_settings(changed)

    assert session.project.document.print_settings == changed
    assert session.modified


def test_setting_the_same_values_changes_nothing(qt_app: QApplication) -> None:
    """Den Dialog zu öffnen und ohne Änderung zu schließen darf ein Projekt
    nicht als geändert markieren."""
    session = Session()
    same = print_settings.resolve(session.profile)
    session.set_print_settings(same)
    session._dirty = False

    session.set_print_settings(same)

    assert not session.modified


# --- Vorschläge einzeln wählen ------------------------------------------------------


def test_advice_can_be_taken_one_at_a_time(qt_app: QApplication) -> None:
    """Alles oder nichts hieße: wer einen Vorschlag nicht will, gibt die
    übrigen mit auf."""
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.advice_view.topLevelItemCount() >= 2

    first = dialog.advice_view.topLevelItem(0)
    assert first is not None
    first.setCheckState(0, Qt.CheckState.Unchecked)
    skipped = str(first.data(0, Qt.ItemDataRole.UserRole))
    before = print_settings.read_path(dialog.settings, skipped)

    dialog._apply_advice()

    assert print_settings.read_path(dialog.settings, skipped) == before


def test_every_advice_starts_checked(qt_app: QApplication) -> None:
    """Die Vorschläge sind begründet — sie vorbelegt zu lassen ist die gute
    Vorgabe, nicht die bequeme."""
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())

    for index in range(dialog.advice_view.topLevelItemCount()):
        item = dialog.advice_view.topLevelItem(index)
        assert item is not None and item.checkState(0) == Qt.CheckState.Checked


# --- die Druckdatei -----------------------------------------------------------------


def test_the_save_button_stays_off_until_something_was_sliced(
    dialog: PrintSettingsDialog,
) -> None:
    """Ein Knopf, der eine Datei speichern soll, die es nicht gibt, ist eine
    Sackgasse."""
    assert not dialog.save_button.isEnabled()


def test_slicing_makes_the_file_available(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Ohne diesen Schritt wäre der ganze Lauf eine Zahl auf dem Bildschirm
    und nichts, was auf einen Drucker geht."""
    produced = tmp_path / "plate_1.gcode"
    produced.write_text("; nur ein Test\n", encoding="utf-8")
    outcome = handover.SliceOutcome(gcode_path=produced, metrics=gcode.GcodeMetrics())

    dialog._sliced([outcome])

    assert dialog.save_button.isEnabled()
    assert dialog._gcode == [produced]


def test_every_plate_keeps_its_own_print_file(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Zwei Platten sind zwei Druckdateien — und zwei Zahlen, die sich addieren.

    Das ist der Punkt, an dem die Übergabe lange stehen blieb: Sie schrieb die
    erste Platte und sagte das auch, aber wer den Satz übersah, hielt eine halbe
    Druckdatei für die ganze.
    """
    outcomes = []
    for index in (1, 2):
        produced = tmp_path / f"platte-{index}.gcode"
        produced.write_text("; nur ein Test\n", encoding="utf-8")
        outcomes.append(
            handover.SliceOutcome(
                gcode_path=produced,
                metrics=gcode.GcodeMetrics(print_seconds=600.0, filament_grams=10.0),
            )
        )

    dialog._sliced(outcomes)

    assert dialog._gcode == [entry.gcode_path for entry in outcomes]
    # Zwanzig Minuten und zwanzig Gramm, nicht zehn: gedruckt wird zweimal.
    # Das Komma ist keine Schreibweise dieses Tests, sondern die der
    # Anzeigesprache — die Zeile geht durch ``localised``, und ``conftest``
    # steht auf Deutsch.
    assert "20 min" in dialog.state.text()
    assert "20,0 g" in dialog.state.text()
    assert "2" in dialog.state.text()


def _two_plate_scene() -> object:
    """Eine Szene mit zwei Platten: rot allein, dann weiß und rot."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import MaterialSlot, Scene, SceneObject

    def body(name: str, plate: int, slots: tuple[MaterialSlot, ...]) -> SceneObject:
        mesh = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
        mesh.apply_translation((0.0, 0.0, 10.0))
        return SceneObject(
            id=name, name=name, mesh=MeshData.of(mesh), plate=plate, material_slots=slots
        )

    rot = MaterialSlot(index=0, name="Rot", colour=(1.0, 0.0, 0.0))
    weiss = MaterialSlot(index=0, name="Weiss", colour=(1.0, 1.0, 1.0))
    return EvaluationResult(
        scene=Scene(
            objects={
                "a": body("a", 0, (rot,)),
                "b": body("b", 1, (weiss,)),
                "c": body("c", 1, (rot,)),
            }
        )
    )


def test_the_plate_choice_appears_only_when_there_is_a_choice(
    dialog: PrintSettingsDialog,
) -> None:
    """Eine Wahl ohne Alternative ist keine — und der Kunde liest sie doch.

    Bei einer Platte bleibt die Zeile verborgen; ab der zweiten erscheint sie
    mit „Alle Platten" als Vorgabe, denn das ist der bisherige Weg. Wer nichts
    wählt, bekommt weiterhin jede Platte als eigene Druckdatei.
    """
    # ``isHidden`` und nicht ``isVisible``: Letzteres antwortet ``False``,
    # solange der Dialog nicht angezeigt wurde, und zwar für jedes Widget.
    assert dialog.plate_row.isHidden(), "leere Szene: keine Wahl"

    dialog.session.last_result = _two_plate_scene()  # type: ignore[assignment]
    dialog._refresh_plates()

    assert not dialog.plate_row.isHidden(), "zwei Platten: jetzt gibt es etwas zu wählen"
    assert dialog.plate_choice.count() == 3, "die Sammelzeile und zwei einzelne"
    assert dialog.plate_choice.currentData() is None, "Vorgabe ist die Sammelzeile"
    assert dialog._chosen_plates() == [0, 1], "und die umfasst beide"


def test_choosing_one_plate_narrows_the_run_and_the_filament_rows(
    dialog: PrintSettingsDialog,
) -> None:
    """Die Wahl wirkt auf beides — den Lauf und die Spulen, die er braucht.

    Solange ``_plate_slots`` fest die erste Platte nahm, ordnete der Kunde
    Filamente einer Platte zu, die er gar nicht slicte. Der Fehler wäre erst
    am fertigen Druck zu sehen gewesen.
    """
    dialog.session.last_result = _two_plate_scene()  # type: ignore[assignment]
    dialog._refresh_plates()

    # Platte 1 trägt nur Rot, Platte 2 trägt Weiß und Rot.
    dialog.plate_choice.setCurrentIndex(1)
    assert dialog._chosen_plates() == [0]
    assert [slot.name for slot in dialog._plate_slots()] == ["Rot"]

    dialog.plate_choice.setCurrentIndex(2)
    assert dialog._chosen_plates() == [1]
    assert sorted(slot.name for slot in dialog._plate_slots()) == ["Rot", "Weiss"]

    # Und zurück auf „Alle": beide Platten, alle Spulen.
    dialog.plate_choice.setCurrentIndex(0)
    assert dialog._chosen_plates() == [0, 1]
    assert sorted(slot.name for slot in dialog._plate_slots()) == ["Rot", "Weiss"]


def test_every_plate_becomes_its_own_run(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Die Übergabe nimmt alle Platten, nicht die erste.

    Der Fund, aus dem das entstand: `_slice` schrieb die Baugruppe von
    `plates[0]`, meldete „geslicet wird die erste" und hörte auf. Der Export
    konnte längst alle. Geprüft wird an der Stelle, die je Platte ihre Datei
    baut — jede trägt nur ihre eigenen Teile und einen eigenen Namen.
    """
    import trimesh

    from app.core.export import handover
    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    def body(size: float, name: str, plate: int) -> SceneObject:
        mesh = trimesh.creation.box(extents=(size, size, size))
        mesh.apply_translation((0.0, 0.0, size / 2.0))
        return SceneObject(id=name, name=name, mesh=MeshData.of(mesh), plate=plate)

    objects = [body(20.0, "A", 0), body(30.0, "B", 1), body(15.0, "C", 1)]
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    runs = [
        dialog._plate_run(objects, plate, tmp_path, "satz", setup)
        for plate in sorted({entry.plate for entry in objects})
    ]

    assert [entry.plate for entry in runs] == [0, 1]
    # Zwei Dateien, nicht eine: sonst schriebe die zweite Platte die erste über.
    assert len({entry.model for entry in runs}) == 2
    assert all(entry.model.is_file() for entry in runs)


def test_the_chosen_slot_profile_reaches_the_run(
    dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """Was die Slot-Zeile einsammelt, steht am Slot des Laufs (§20).

    Der Fund dazu: `slot_profiles` wurde eingesammelt, gemeldet („{slot}
    druckt mit {profil}.") und nie an `write_config` gereicht —
    `MaterialSlot.material` setzte niemand, alle Slots slicten mit dem
    Basisfilament, nur die Farbe stimmte.
    """
    import trimesh

    from app.core.export import handover
    from app.core.geom.mesh import MeshData
    from app.core.types import MaterialSlot, SceneObject

    mesh = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    mesh.apply_translation((0.0, 0.0, 10.0))
    slotted = SceneObject(
        id="A",
        name="A",
        mesh=MeshData.of(mesh),
        material_slots=[
            MaterialSlot(index=0, name="Gehäuse"),
            MaterialSlot(index=1, name="Schrift"),
        ],
    )
    dialog.settings = replace(dialog.settings, slot_profiles=("", "Elegoo PLA"))
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    run = dialog._plate_run([slotted], 0, tmp_path, "satz", setup)

    assert run.slots[0].material is None, "ohne Wahl gilt das Filament der Platte"
    assert run.slots[1].material == "Elegoo PLA"


def test_an_unknown_printer_leaves_the_dialog_responsive(dialog: PrintSettingsDialog) -> None:
    """Ohne passenden Drucker bleibt die Filamentliste leer — und still.

    Der Fund dahinter ist der Normalfall und kein Sonderfall: Solidons Vorgabe
    ist der „Allgemeine FDM-Drucker 220 mm", und dazu hat kein Slicer ein
    Profil. Die Vorbelegungssuche lief trotzdem, schlug ohne Drucker den
    ganzen Filamentbestand auf (5962 Profile statt 42, je eines mit Erbkette
    aus Dateien) und blockierte dabei den Qt-Hauptthread. Wirkungslos war sie
    obendrein: gesucht wurde ein Eintrag in einer Liste, die leer ist.
    """
    dialog._profiles = []

    begonnen = time.perf_counter()
    dialog._fill_filaments(None)

    assert time.perf_counter() - begonnen < 0.5, "ohne Drucker wird nichts aufgeschlagen"
    assert dialog.filament_choice.count() == 0
    assert dialog.filament_choice.currentIndex() == -1, "und nichts steht da, was nicht da ist"


def test_a_connector_of_infill_reaches_the_advice_list(
    qt_app: QApplication, session: Session
) -> None:
    """Der Vorschlag zum Verbinder steht in der Liste, nicht nur in der Rechnung.

    Gemessen am Querschnitt, so wie man es am geschnittenen Teil nachmisst: Ein
    Zapfen mit Ø 5,04 mm ist bei zwei Wänden à 0,42 mm innen 3,36 mm Füllmuster
    und außen 1,68 mm Material — mehr Muster als Material, und genau dort sitzt
    die Verbindung. Bei drei Wänden (der Vorgabe) hält es sich die Waage, und
    dann sagt Solidon nichts.
    """
    session.import_model(Path(__file__).parent / "data" / "meshes" / "cube_clean.stl")
    session.wait_for_idle()
    result = session.last_result
    assert result is not None, "die Szene steht"

    # Ein Zapfen, wie ihn `split_pinned` erzeugt — die Planung rechnet ihn aus
    # der Schnittfläche, er ist also kein Parameter, den jemand einträgt.
    entry = next(iter(result.scene.objects.values()))
    entry.features["pin_1"] = Feature(
        id="pin_1", kind="pin", provenance="generated", params={"diameter": 5.04}
    )

    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog._connector_diameters() == (5.04,)

    dialog._editors["shell.wall_count"].setValue(3)
    titel = {
        dialog.advice_view.topLevelItem(row).text(0)
        for row in range(dialog.advice_view.topLevelItemCount())
    }
    assert not any("Wände" in eintrag for eintrag in titel), "bei drei Wänden trägt der Zapfen"

    dialog._editors["shell.wall_count"].setValue(2)
    zeilen = [
        (
            dialog.advice_view.topLevelItem(row).text(0),
            dialog.advice_view.topLevelItem(row).text(1),
        )
        for row in range(dialog.advice_view.topLevelItemCount())
    ]

    passend = [zeile for zeile in zeilen if "Wände" in zeile[0]]
    assert passend, f"der Vorschlag fehlt in der Liste: {zeilen}"
    assert "2 → 3" in passend[0][1], "und er nennt beide Zahlen"


def test_a_guessed_pin_never_sets_a_setting(qt_app: QApplication, session: Session) -> None:
    """Ein „Zapfen" aus der Merkmalserkennung ist eine Vermutung, keine Vorgabe.

    Gemessen an einem heruntergeladenen Sockel von 160 auf 231 auf 14 mm: Die
    Erkennung fand zehn Zapfen, den dicksten mit Ø 631,6 mm — an einem Teil,
    das an seiner schmalsten Stelle 14 mm misst. Die Wandregel rechnete daraus
    **376 Wände**, und *Vorschläge übernehmen* schrieb sie ins Projekt.
    """
    session.import_model(Path(__file__).parent / "data" / "meshes" / "cube_clean.stl")
    session.wait_for_idle()
    result = session.last_result
    assert result is not None
    entry = next(iter(result.scene.objects.values()))
    entry.features["pin_9"] = Feature(
        id="pin_9", kind="pin", provenance="detected", params={"diameter": 631.582}
    )

    dialog = PrintSettingsDialog(session, UiSettings())

    assert dialog._connector_diameters() == (), "eine Vermutung zählt nicht mit"
    dialog._editors["shell.wall_count"].setValue(2)
    zeilen = [
        (
            dialog.advice_view.topLevelItem(row).text(0),
            dialog.advice_view.topLevelItem(row).text(1),
        )
        for row in range(dialog.advice_view.topLevelItemCount())
    ]
    assert not [zeile for zeile in zeilen if "Wände" in zeile[0]], zeilen

    # Und die Gegenprobe in derselben Szene: ein **erzeugter** Zapfen zählt.
    entry.features["pin_1"] = Feature(
        id="pin_1", kind="pin", provenance="generated", params={"diameter": 5.04}
    )
    zweiter = PrintSettingsDialog(session, UiSettings())

    assert zweiter._connector_diameters() == (5.04,), "der geplante Zapfen schon"


# --- Profilauswahl (§29) ------------------------------------------------------------


def _profile(name: str, kind: str, **kwargs: object) -> SlicerProfile:
    return SlicerProfile(path=Path(f"/x/{name}.json"), name=name, kind=kind, **kwargs)  # type: ignore[arg-type]


def test_the_found_profiles_fill_both_choices(dialog: PrintSettingsDialog) -> None:
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
        default_process="0.20mm Standard",
    )
    found = [
        machine,
        _profile("0.20mm Standard", "process", compatible_printers=(machine.name,)),
        _profile("0.12mm Fein", "process", inherits="0.20mm Standard"),
    ]

    dialog._profiles_found(found)

    assert dialog.machine_choice.count() == 1
    assert dialog.machine_choice.isEnabled()
    assert dialog.process_choice.count() == 2


def test_switching_the_slicer_empties_the_profile_choice(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Wer zwei Slicer hat, wechselt — und die Auswahl darf nicht stehenbleiben.

    Gemessen: Mit gefüllter Orca-Auswahl und danach eingestelltem CuraEngine
    ging ein ``-j`` auf eine Orca-Datei hinaus, und der Slicer war nach einer
    Zehntelsekunde tot. ``_start_profile_search`` kehrt für ``cura`` und
    ``prusa`` früh zurück; geleert wird deshalb am Anfang, nicht am Ende.

    Und die gemerkte Wahl bleibt: das Leere zu merken löschte das Profil, das
    zum nächsten Orca-Lauf gehört.
    """
    from app.core import discover

    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
        default_process="0.20mm Standard",
    )
    dialog._profiles_found([machine, _profile("0.20mm Standard", "process")])
    assert dialog.machine_choice.count() == 1, "so weit ist es der Orca-Fall"
    dialog.ui_settings.slicer_machine_profile = str(machine.path)

    engine = tmp_path / "CuraEngine.exe"
    engine.write_text("")
    monkeypatch.setattr(discover, "find_program", lambda *_args, **_kwargs: engine)

    dialog.recheck_slicer()

    assert dialog.machine_choice.count() == 0, "kein Orca-Profil für CuraEngine"
    assert not dialog.machine_choice.isEnabled()
    assert dialog.process_choice.count() == 0
    assert dialog.filament_choice.count() == 0
    assert dialog._profiles == []

    # Und die zweite Zusicherung: was nicht gewählt werden kann, wird nicht
    # gemerkt — sonst stünde beim nächsten Orca-Lauf nichts mehr da.
    dialog._remember_slicer_choice(require_machine=False)

    assert dialog.ui_settings.slicer_machine_profile == str(machine.path)


def test_the_matching_profile_is_preselected(qt_app: QApplication) -> None:
    """§2.4: eine gute Vorgabe ist mehr wert als eine gute
    Einstellmöglichkeit. Das Maschinenprofil nennt seinen Drucker und sein
    Standard-Prozessprofil selbst — es gibt nichts zu erfragen."""
    session = Session()
    session.project.document.printer = "centauri-carbon-2"
    dialog = PrintSettingsDialog(session, UiSettings())
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
        default_process="0.20mm Standard",
    )
    other = _profile(
        "Ganz anderes Gerät", "machine", printer_model="Ganz anderes Gerät", nozzle=0.4
    )

    dialog._profiles_found(
        [
            other,
            machine,
            _profile("0.12mm Fein", "process", compatible_printers=(machine.name,)),
            _profile("0.20mm Standard", "process", compatible_printers=(machine.name,)),
        ]
    )

    assert dialog.machine_choice.currentData() == str(machine.path)
    assert dialog.process_choice.currentText().startswith("0.20mm Standard")


def test_processes_of_other_printers_stay_out(dialog: PrintSettingsDialog) -> None:
    """Ungefiltert stünden hier zweitausend Einträge, von denen einer stimmt —
    und der Slicer lehnte jeden anderen ab, ohne zu sagen warum."""
    machine = _profile("Meiner 0.4 nozzle", "machine", printer_model="Meiner", nozzle=0.4)
    dialog._profiles_found(
        [
            machine,
            _profile("Passt", "process", compatible_printers=(machine.name,)),
            _profile("Passt nicht", "process", compatible_printers=("Ein anderer",)),
        ]
    )

    shown = [
        dialog.process_choice.itemText(index) for index in range(dialog.process_choice.count())
    ]
    assert shown == ["Passt"]


def test_an_own_profile_is_marked_in_words(dialog: PrintSettingsDialog) -> None:
    machine = _profile("Meiner 0.4 nozzle", "machine", printer_model="Meiner", nozzle=0.4)
    dialog._profiles_found([machine, _profile("Meine Version", "process", from_user=True)])

    assert "(" in dialog.process_choice.itemText(0)


def test_no_profiles_found_says_what_that_means(dialog: PrintSettingsDialog) -> None:
    dialog._profiles_found([])

    assert dialog.profile_note.text()
    assert not dialog.machine_choice.isEnabled()


def test_a_remembered_choice_wins_over_the_match(qt_app: QApplication) -> None:
    """Wer einmal abgewichen ist, meinte es so."""
    session = Session()
    session.project.document.printer = "centauri-carbon-2"
    settings = UiSettings()
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
    )
    other = _profile("Etwas anderes", "machine", printer_model="Etwas anderes", nozzle=0.4)
    settings.slicer_machine_profile = str(other.path)
    dialog = PrintSettingsDialog(session, settings)

    dialog._profiles_found([machine, other])

    assert dialog.machine_choice.currentData() == str(other.path)


def test_a_built_fit_counts_like_an_entered_one(session: Session, qt_app) -> None:
    """§29: die Regeln für Passungen greifen auch ohne Eintrag im Dokument.

    Der Deckel aus ``create_lid`` bekommt sein Spiel aus dem Materialprofil und
    trägt es nirgends ein — im gedruckten Gewürzset liefen deshalb genau die
    Regeln nicht, die es für Passungen gibt: genaue Außenwand, gebremste
    Beschleunigung, Bügeln der Gleitfläche. Der Stapel weiß es trotzdem.
    """
    from app.core.scene import History, OperationDraft
    from app.ui.print_settings_dialog import PrintSettingsDialog

    dialog = PrintSettingsDialog(session, UiSettings())
    try:
        assert not dialog._fits_in_play(), "ein leeres Projekt hat keine Passung"

        History(session.project.document).apply(
            "Grundkörper",
            [OperationDraft(op="create_cylinder", params={"diameter": 40.0, "height": 20.0})],
        )
        assert not dialog._fits_in_play(), "ein Zylinder ist noch keine"

        History(session.project.document).apply(
            "Deckel",
            [OperationDraft(op="create_lid", inputs=("obj_1",), params={"thickness": 2.4})],
        )
        assert dialog._fits_in_play(), "ein Deckel legt zwei Flächen mit Spiel aufeinander"
    finally:
        dialog.deleteLater()


# --- ein Filament je Materialslot (§20) -----------------------------------------


def _two_slots() -> list[object]:
    """Zwei Materialslots, wie ein Schild mit Schriftzug sie hat.

    Der Dialog liest sie über ``_plate_slots`` aus der Szene; hier wird genau
    diese eine Auskunft ersetzt. Ein wirklich erzeugter Schriftzug kostete in
    einem Oberflächentest mehr Zeit als der ganze Rest der Datei — und geprüft
    wird der Dialog, nicht die Beschriftungs-Op.
    """
    from app.core.types import MaterialSlot

    return [
        MaterialSlot(index=0, name="Gehäuse", colour=(0.0, 0.0, 0.0)),
        MaterialSlot(index=1, name="Schrift", colour=(1.0, 1.0, 1.0)),
    ]


def test_one_slot_shows_no_list(dialog: PrintSettingsDialog) -> None:
    """Ein einfarbiges Teil hat eine Farbe und braucht keine Liste darüber.

    Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche (§2): die Zeile
    „Filament" ist dann die ganze Aussage.
    """
    assert dialog.slot_rows == []


def test_a_second_slot_gets_its_own_choice(
    qt_app: QApplication, session: Session, tmp_path: Path, monkeypatch
) -> None:
    """Zwei Slots, zwei Auswahlen — und die Wahl bleibt im Projekt.

    Ein Schriftzug in Weiß auf schwarzem Gehäuse sind zwei Spulen mit zwei
    Temperaturen. Ohne diese Zeilen ließe sich das drucken, aber nicht sagen,
    und die zweite Farbe liefe mit den Werten der ersten.
    """
    monkeypatch.setattr(PrintSettingsDialog, "_plate_slots", lambda _self: _two_slots())
    dialog = PrintSettingsDialog(session, UiSettings())

    assert len(dialog.slot_rows) == 2, "je Slot eine Zeile"
    assert "Gehäuse" in dialog.slot_rows[0][0].text()
    assert "Schrift" in dialog.slot_rows[1][0].text()

    box = dialog.slot_rows[1][1]
    box.addItem("Haus PLA weiß", str(tmp_path / "pla.json"))
    box.setCurrentIndex(box.count() - 1)
    dialog._slot_filament_chosen(1)

    gemerkt = dialog.settings.slot_profiles
    assert len(gemerkt) == 2, "ein Eintrag je Slot"
    assert gemerkt[1] == "Haus PLA weiß", "der Name reist mit, nicht der Pfad"


def test_a_slot_stores_the_profile_name_and_not_its_caption(
    qt_app: QApplication, session: Session, monkeypatch
) -> None:
    """Gespeichert wurde die **Beschriftung**, und die ist übersetzt.

    ``currentText()`` gibt bei einem selbst angelegten Profil „Haus PLA weiß
    (eigenes)" — im englischen Fenster „(own)". Der Slicer kennt weder das eine
    noch das andere: Die Slot-Wahl kam nie an, und beim nächsten Öffnen fand
    die Vorbelegung ihren eigenen Eintrag nicht wieder.

    **Der Test daneben konnte es nicht sehen**, und das ist der zweite Teil
    des Befunds: Er legte den Eintrag mit ``addItem("Haus PLA weiß", pfad)``
    an, also mit einer Beschriftung, die dem Namen gleicht. Zwei Wege, die
    dasselbe zurückgeben, unterscheidet keine Zusicherung — hier wird der
    Datensatz deshalb entzerrt, indem das Profil ein eigenes ist und seine
    Beschriftung damit einen Zusatz trägt.
    """
    monkeypatch.setattr(PrintSettingsDialog, "_plate_slots", lambda _self: _two_slots())
    dialog = PrintSettingsDialog(session, UiSettings())
    eigenes = _profile("Haus PLA weiß", "filament", from_user=True, filament_type="PLA")
    dialog._profiles = [eigenes]

    box = dialog.slot_rows[1][1]
    box.addItem(eigenes.title("eigenes"), str(eigenes.path))
    box.setCurrentIndex(box.count() - 1)
    assert box.currentText() != eigenes.name, "sonst prüft der Test zwei gleiche Zahlen"

    dialog._slot_filament_chosen(1)

    assert dialog.settings.slot_profiles[1] == "Haus PLA weiß"
    assert "(" not in dialog.settings.slot_profiles[1], "kein Anhang, den kein Slicer kennt"
    # Und die Vorbelegung findet die Wahl wieder — ohne sie wäre der Name zwar
    # richtig abgelegt und beim nächsten Öffnen trotzdem verloren.
    assert dialog._filament_index(box, "Haus PLA weiß") == box.count() - 1


def test_the_slot_assignment_outlives_a_quality_change(
    qt_app: QApplication, session: Session, monkeypatch
) -> None:
    """Der Zwilling des Druckerwechsels, eine Stufe weiter.

    ``_quality_changed`` löst neu auf, und das ist richtig: Eine Stufe zu
    wechseln *heißt*, sich neue Vorgaben geben zu lassen. Die Slotbelegung
    fällt nicht darunter — sie sagt, **welche Spule auf welchem Materialslot
    des Modells liegt** (§20), und das ändert sich nicht, weil jemand von 0,2
    auf 0,12 mm geht.

    Der Beweis steht im Code und nicht in der Meinung: ``resolve`` ist eine
    reine Funktion aus Profil und Stufe, und ``slot_profiles`` ist das einzige
    Feld, für das sie keine Quelle hat. „Rücknehmbar über die Stufe, aus der
    man kam" gilt deshalb für jeden anderen Wert und für diesen einen nicht —
    er kommt von keiner Stufe zurück, weil er von keiner kam.

    Schlimmer als der Verlust war, dass man ihn nicht sah: Die zwei
    Auswahlfelder standen unverändert da, während das Modell nichts mehr von
    ihnen wusste, und beim Export lief die weiße Schrift mit dem Filament der
    Platte.

    **Beide Hälften**, sonst wäre „es ändert sich nichts mehr" auch grün.
    """
    monkeypatch.setattr(PrintSettingsDialog, "_plate_slots", lambda _self: _two_slots())
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog.settings = replace(dialog.settings, slot_profiles=("Haus PETG", "Haus PLA weiß"))
    assert dialog.settings.quality == "standard"
    assert print_settings.read_path(dialog.settings, "layers.layer_height") == pytest.approx(0.2)

    _select_quality(dialog, "fine")

    assert dialog.settings.slot_profiles == ("Haus PETG", "Haus PLA weiß"), (
        "die Spule je Slot ist keine Vorgabe der Stufe"
    )
    assert print_settings.read_path(dialog.settings, "layers.layer_height") == pytest.approx(
        0.12
    ), "und die Stufe wirkt weiterhin auf alles, was ihr gehört"


def test_the_slot_assignment_outlives_a_printer_change(
    qt_app: QApplication, session: Session, monkeypatch
) -> None:
    """Derselbe Verlust an der zweiten Stelle — der dritte Zwilling.

    ``_scene_profile_changed`` rettet seit heute die übersteuerten Werte, und
    zwar über die 56 Pfade aus ``FIELDS``. ``slot_profiles`` steht in keinem
    Feld des Dialogs und fiel damit durch dasselbe Loch wie beim
    Stufenwechsel: Die Rettung, die den Fehler behob, ließ genau diesen einen
    Wert liegen.
    """
    monkeypatch.setattr(PrintSettingsDialog, "_plate_slots", lambda _self: _two_slots())
    dialog = PrintSettingsDialog(session, UiSettings())
    try:
        _select_printer(dialog, "generic-220")
        dialog.settings = replace(dialog.settings, slot_profiles=("Haus PETG", "Haus PLA weiß"))

        _select_printer(dialog, "prusa-mini")

        assert dialog.settings.slot_profiles == ("Haus PETG", "Haus PLA weiß")
        assert print_settings.read_path(dialog.settings, "layers.line_width") == pytest.approx(
            0.45
        ), "und der Druckerwechsel wirkt weiterhin"
    finally:
        session.wait_for_idle()


def _select_quality(dialog: PrintSettingsDialog, quality: str) -> None:
    """Die Stufe über die Auswahl wechseln, wie ein Kunde es tut."""
    index = dialog.quality.findData(quality)
    assert index >= 0, quality
    dialog.quality.setCurrentIndex(index)


def test_a_different_printer_keeps_what_the_customer_set(
    qt_app: QApplication, session: Session
) -> None:
    """Ein Druckerwechsel warf jeden eigenen Wert weg — wortlos.

    ``_scene_profile_changed`` löste den ganzen Satz neu auf. Übersteuerte
    Werte und mitgebrachte Werte (aus einer eingelesenen 3MF) waren damit fort:
    62 % Füllung wurden beim Umstellen des Druckers zu 15 %, ohne Ansage und
    ohne Undo — der Dialog ist kein Verlaufsschritt.

    Ein Drucker wechselt **Vorgaben**. Was von der alten Vorgabe abweicht, ist
    keine Vorgabe, sondern eine Entscheidung, und die bleibt. Beide Hälften
    stehen hier: Ohne die zweite wäre „nichts ändert sich mehr" auch grün, und
    das wäre der nächste Fehler.
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    try:
        _select_printer(dialog, "generic-220")
        assert print_settings.read_path(dialog.settings, "layers.line_width") == pytest.approx(0.42)

        fuellung = dialog._editors["infill.density"]
        assert isinstance(fuellung, QDoubleSpinBox)
        fuellung.setValue(62.0)  # das Feld zeigt Prozent, das Modell 0…1
        assert print_settings.read_path(dialog.settings, "infill.density") == pytest.approx(0.62)

        _select_printer(dialog, "prusa-mini")

        assert print_settings.read_path(dialog.settings, "infill.density") == pytest.approx(0.62), (
            "die eigene Entscheidung überlebt den Wechsel"
        )
        assert print_settings.read_path(dialog.settings, "layers.line_width") == pytest.approx(
            0.45
        ), "und die unangetastete Vorgabe folgt der neuen Düse"
        assert dialog._editors["infill.density"].value() == pytest.approx(62.0), (
            "auch im Feld, nicht nur im Modell"
        )
    finally:
        # **Der Druckerwechsel wertet neu aus, und zwar nebenher.** Ein
        # Arbeiter, der den Test überlebt, nimmt beim Abbau den Prozess mit —
        # der Lauf riss danach in ``_no_worker_outlives_its_window``, mit
        # „passed" davor und Exit 139 dahinter (siehe ``Session.wait_for_idle``).
        session.wait_for_idle()


def _select_printer(dialog: PrintSettingsDialog, printer_id: str) -> None:
    """Den Drucker über die Auswahl wechseln, wie ein Kunde es tut.

    Über den Index und nicht über ``_scene_profile_changed``: Am Signal hängt
    die halbe Zusicherung, und ein Test, der die Methode selbst ruft, prüft
    den Weg nicht (`.claude/rules/tests.md`, „Am Weg vorbei").
    """
    index = dialog.printer_choice.findData(printer_id)
    assert index >= 0, printer_id
    dialog.printer_choice.setCurrentIndex(index)


def test_the_slot_choice_survives_the_project_file(tmp_path: Path) -> None:
    """Die Zuordnung gehört ins Projekt und nicht an den Rechner.

    Sie beschreibt das Teil — welcher Slot aus welcher Spule kommt —, und ein
    Projekt, das man weitergibt, soll das mitbringen. Der **Name** reist,
    nicht der Pfad (Regel 12).
    """
    from app.core.scene.serialise import print_settings_from_data, print_settings_to_data

    settings = replace(
        print_settings.resolve(profiles.make_profile()),
        slot_profiles=("Haus PETG", "Haus PLA weiß"),
    )

    zurueck = print_settings_from_data(print_settings_to_data(settings))

    assert zurueck.slot_profiles == ("Haus PETG", "Haus PLA weiß")


def test_a_late_profile_search_does_not_overwrite_a_choice(qt_app: QApplication) -> None:
    """**Der Wettlauf, an dem ein Test einmal unter Last hing.**

    Die Profilsuche läuft in einem Arbeiter und antwortet nachgereicht. Wer in
    der Zwischenzeit selbst eine Maschine gewählt hatte, sah sie danach auf
    etwas anderes springen — und beim Schließen wurde die *neue* gemerkt, nicht
    seine. Dieselbe Regel wie beim Druckervorschlag der Erstinbetriebnahme:
    Eine Vorgabe, die eine Wahl überschreibt, ist keine Vorgabe mehr (§2.4).

    Sichtbar wurde es, seit ``recheck_slicer`` die Suche ein zweites Mal
    startet: Beim ersten Öffnen ist die Auswahl leer, danach nicht mehr.
    """
    session = Session()
    settings = UiSettings()
    dialog = PrintSettingsDialog(session, settings)

    # So sieht es aus, wenn jemand gewählt hat, bevor die Suche antwortet.
    dialog.machine_choice.addItem("Meine Maschine", "C:/meine/maschine.json")
    dialog.machine_choice.setCurrentIndex(dialog.machine_choice.count() - 1)

    dialog._profiles_found(
        [
            _profile("Etwas anderes", "machine", printer_model="Etwas anderes", nozzle=0.4),
            _profile("Und noch was", "machine", printer_model="Und noch was", nozzle=0.6),
        ]
    )

    assert dialog.machine_choice.currentData() == "C:/meine/maschine.json"


def test_the_chosen_machine_survives_until_the_dialog_closes(qt_app: QApplication) -> None:
    """Und sie ist danach gemerkt — das ist der Punkt der Sache (§29, A5).

    Der Test daneben prüft die Auswahl, dieser die Folge: Was im Dialog stand,
    gilt auch für den Export.
    """
    session = Session()
    settings = UiSettings()
    dialog = PrintSettingsDialog(session, settings)
    dialog.machine_choice.addItem("Meine Maschine", "C:/meine/maschine.json")
    dialog.machine_choice.setCurrentIndex(dialog.machine_choice.count() - 1)

    # Zwei Profile, nicht eines: Bei genau einem fällt ``_profiles_found`` auf
    # Index 0 zurück, und der wäre zufällig der eigene Eintrag — der Test wäre
    # grün, ohne etwas zu prüfen.
    dialog._profiles_found(
        [
            _profile("Etwas anderes", "machine", printer_model="Etwas anderes", nozzle=0.4),
            _profile("Und noch was", "machine", printer_model="Und noch was", nozzle=0.6),
        ]
    )
    dialog.reject()

    assert settings.slicer_machine_profile == "C:/meine/maschine.json"


def test_a_failed_slicer_run_leaves_its_reason_in_the_dialog(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Fenster darf den Lauf nicht vergessen, wenn das Fehlerfenster zugeht.

    Gemessen im Kundendurchgang: PrusaSlicer lehnte eine Platte in
    Bettkoordinaten ab — „Der Slicer sagt, die Teile liegen außerhalb seines
    Bauraums", mit *Auf dem Bett anordnen* als erster Handlung. Der Satz
    erschien einmal; danach stand in der Zeile, die eben noch „Der Slicer
    rechnet …" sagte, nichts mehr.

    Geprüft wird über den Slot, der am Signal des Arbeiters hängt, und der
    Fehlerdialog wird dabei stillgelegt: ``exec`` wartet auf einen Menschen.
    """
    from app.core.errors import ARRANGE_ON_BED, ExternalToolError
    from app.ui import print_settings_dialog as modul

    gezeigt: list[object] = []
    monkeypatch.setattr(modul, "show_error", lambda problem, parent=None: gezeigt.append(problem))
    dialog.state.setText("Der Slicer rechnet …")

    dialog._slice_failed(
        ExternalToolError(
            tool="prusa-slicer",
            detail="Der Slicer sagt, die Teile liegen außerhalb seines Bauraums.",
            suggestions=(ARRANGE_ON_BED,),
        )
    )

    assert gezeigt, "das Fehlerfenster kommt weiterhin"
    assert "außerhalb seines Bauraums" in dialog.state.text(), dialog.state.text()
