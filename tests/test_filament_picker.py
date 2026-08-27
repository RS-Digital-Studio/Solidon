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
from app.ui.filament_picker import NEW_FILAMENT, FilamentField, hex_of


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
    filaments.remember("PETG Rot", "#cc2222")

    field = FilamentField(0)
    position = next(row for row in range(field.count()) if "PETG Rot" in field.itemText(row))

    seen: list[tuple[str, str]] = []
    field.filamentChosen.connect(lambda name, colour: seen.append((name, colour)))
    field.setCurrentIndex(position)
    field._chosen(position)

    assert seen == [("PETG Rot", "#cc2222")], "Name und Farbe müssen weitergehen"
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


def test_a_used_filament_is_not_a_button(qt_app: QApplication, tmp_path, monkeypatch) -> None:
    """Die Projekthälfte ist Anzeige — Ändern wäre Geometrie ohne Operation.

    Ein Filament am Körper zu ändern heißt, den Slot eines Körpers zu ändern,
    und das gehört einer Operation (Regel 2). Die Zeile ist deshalb nicht
    anwählbar, und ihr Hinweis sagt, wo es geht. Das Regal darunter hat
    keinen Körper unter sich und ist voll bedienbar.
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

    assert not benutzt.flags() & Qt.ItemFlag.ItemIsSelectable, "die Anzeige ist kein Knopf"
    assert regal.flags() & Qt.ItemFlag.ItemIsSelectable, "das Regal lässt sich bedienen"
    assert "Kontextmenü" in benutzt.toolTip(), "und sagt, wo es geht"


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
