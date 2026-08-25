"""Der Dialog „Auswahl als Baustein speichern" (Konzept §16, Schritt 3 bis 5).

Was hier geprüft wird, ist die **Bedienung**: dass der Weg zum eigenen
Baustein im Katalog steht und nicht im Menü, dass er gesperrt ist, solange er
nichts leisten kann — und mit einem Satz sagt warum —, und dass der Dialog
genau die Angaben sammelt, die das Rezeptformat verlangt.

Was der Kern daraus macht, prüft ``tests/test_recipes.py``. Die Naht dazwischen
ist ``recipe.capture``, und sie wird hier mit einer Attrappe gemessen: Der Test
soll sagen, **was der Dialog liefert**, nicht ob die Auswertung stimmt.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from app.core.scene.project import new_project
from app.core.types import Document, Feature, Parameter
from app.ui.catalog import PartCatalog
from app.ui.main_window import MainWindow
from app.ui.recipe_dialog import RecipeDialog, _identifier
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


def _feature(identifier: str) -> Feature:
    """Ein echtes Merkmal, keine Attrappe.

    Die erste Fassung hier war eine Klasse mit einem einzigen Feld ``id`` —
    genug für den Dialog von damals. Seit er die Zeile über ``feature_label``
    beschriftet, braucht er ``kind`` und ``params``, und die Attrappe fiel um.
    Ein Fake, der weniger kann als die Sache, prüft den Tag, an dem er
    geschrieben wurde.
    """
    return Feature(id=identifier, kind="hole", provenance="detected", params={"diameter": 5.2})


def _document() -> Document:
    """Ein Dokument, wie die Anwendung es baut — mit zwei Projektparametern.

    Über ``new_project`` und nicht über ``Document(...)``: Die Formatversion
    ist Pflicht, und ein Test, der sie selbst einträgt, prüft irgendwann eine
    Version, die es nicht mehr gibt.
    """
    return replace(
        new_project().document,
        parameters={
            "breite": Parameter(name="breite", value=40.0, unit="mm", title="Breite"),
            "hoehe": Parameter(
                name="hoehe", value=10.0, unit="mm", title="Höhe", minimum=5.0, maximum=25.0
            ),
        },
    )


def _dialog(qt_app: QApplication, features: tuple[Feature, ...] = ()) -> RecipeDialog:
    profile: Any = None
    return RecipeDialog(_document(), {}, (0,), features, profile)  # type: ignore[arg-type]


def test_an_identifier_survives_umlauts_and_spaces() -> None:
    """Der Titel ist ein Satz, der Bezeichner nicht.

    Das Register verlangt einen Namen ohne Umlaute und ohne Leerzeichen; der
    Kunde tippt „Halter für die Werkbank". Die Umschrift steht im Dialog und
    nicht im Kern, weil sie eine Frage der Eingabe ist — und weil ein Kunde
    den Vorschlag danach noch ändern können soll.
    """
    assert _identifier("Halter für die Werkbank") == "halter_fuer_die_werkbank"
    assert _identifier("  Größe 3 / Version 2  ") == "groesse_3_version_2"
    assert _identifier("!!!") == "eigener_baustein", "leer wäre kein Name"


def test_the_dialog_offers_a_row_for_every_parameter(qt_app: QApplication) -> None:
    """Jeder Projektparameter kann ein einstellbares Maß des Bausteins werden.

    Und die Angaben stehen vorbelegt da: Titel, Einheit und Grenzen hat der
    Kunde beim Anlegen des Parameters schon gesagt (§13). Zweimal danach zu
    fragen wäre die Sorte Dialog, die man wegklickt.
    """
    dialog = _dialog(qt_app, (_feature("hole_1"),))
    try:
        rows = {row.name: row for row in dialog._params}

        assert set(rows) == {"breite", "hoehe"}
        assert rows["breite"].title.text() == "Breite"
        assert rows["breite"].unit.text() == "mm"
        assert rows["breite"].default.value() == pytest.approx(40.0)
        # Gesetzte Grenzen werden übernommen …
        assert rows["hoehe"].minimum.value() == pytest.approx(5.0)
        assert rows["hoehe"].maximum.value() == pytest.approx(25.0)
        # … und wo keine stehen, ist die Vorgabe der Anhaltspunkt. Zwei leere
        # Felder machten den Bereichstest in Schritt 5 wertlos.
        assert rows["breite"].minimum.value() < 40.0 < rows["breite"].maximum.value()
    finally:
        dialog.release()
        dialog.deleteLater()


def test_what_the_dialog_hands_to_the_core(qt_app: QApplication) -> None:
    """Die Naht zu E2: genau die Felder, die ``ExposedParam`` verlangt."""
    dialog = _dialog(qt_app, (_feature("hole_1"),))
    try:
        dialog._params[0].placement.setCurrentIndex(1)
        exposed = dialog._params[0].exposed()

        assert exposed.name == "breite", "der Projektparameter ist die Stelle, wo der Wert fließt"
        assert exposed.title == "Breite"
        assert exposed.placement == "advanced"
        assert exposed.default == pytest.approx(40.0)
    finally:
        dialog.release()
        dialog.deleteLater()


def test_the_button_says_what_is_missing_instead_of_greying_out(qt_app: QApplication) -> None:
    """§2.7: Ein gesperrter Knopf ohne Grund ist eine Sackgasse.

    Drei Bedingungen sperren ihn, und alle drei sind behebbar — deshalb nennt
    der Tooltip sie, statt den Kunden raten zu lassen.
    """
    dialog = _dialog(qt_app, (_feature("hole_1"),))
    try:
        assert not dialog._save.isEnabled(), "ohne Namen kann nichts angelegt werden"
        assert dialog._save.toolTip(), "und der Grund steht daneben"

        dialog.title.setText("Werkbankhalter")
        assert dialog._save.isEnabled()
        assert dialog._save.toolTip() == ""

        # Ohne benanntes Merkmal weist der Kern beim Speichern ab (§18d) — der
        # Dialog fängt es davor ab, wo es behebbar ist.
        dialog._features[0].take.setChecked(False)
        assert not dialog._save.isEnabled()

        # Und ohne freigegebenes Maß wäre der Baustein starr: Er ließe sich
        # anlegen und danach an keiner Stelle anpassen. Diese dritte Bedingung
        # stand ungeprüft da, bis eine Gegenprobe sie mutierte und der Lauf
        # grün blieb.
        dialog._features[0].take.setChecked(True)
        assert dialog._save.isEnabled()
        for row in dialog._params:
            row.take.setChecked(False)
        assert not dialog._save.isEnabled()
    finally:
        dialog.release()
        dialog.deleteLater()


def test_a_body_without_features_is_said_out_loud(qt_app: QApplication) -> None:
    """Ohne erkanntes Merkmal lässt sich kein Baustein anlegen — das gehört gesagt.

    Der Kern wirft beim Speichern (``capture`` weist leere Mengen ab). Hier
    steht der Satz vorher, weil der Kunde dann noch etwas tun kann.
    """
    dialog = _dialog(qt_app, ())
    try:
        dialog.title.setText("Werkbankhalter")

        assert not dialog._save.isEnabled()
        assert dialog._features == []
    finally:
        dialog.release()
        dialog.deleteLater()


def test_the_way_to_an_own_part_starts_in_the_catalogue(qt_app: QApplication) -> None:
    """§16 Schritt 3 und §18c: im Katalog, nicht im Menü.

    Wer ein Teil in die Bibliothek legen will, denkt an die Bibliothek — und
    die Menüleiste ist die Stelle, die von eigenen Bausteinen ohnehin frei
    bleibt (E1).
    """
    catalog = PartCatalog()
    try:
        assert catalog.save_part.text().startswith("Auswahl als Baustein")
        assert not catalog.save_part.isEnabled(), "ohne Zutun des Fensters gesperrt"

        catalog.set_can_save(False, "Dafür muss zuerst etwas gerechnet sein.")
        assert catalog.save_part.toolTip() == "Dafür muss zuerst etwas gerechnet sein."

        catalog.set_can_save(True)
        assert catalog.save_part.isEnabled()
        assert catalog.save_part.toolTip() == ""
    finally:
        release = getattr(type(catalog), "release", None)
        if release is not None:
            release(catalog)
        catalog.deleteLater()


# --- die Naht zum Fenster ---------------------------------------------------------


def test_the_window_hands_over_features_and_not_their_keys(qt_app: QApplication) -> None:
    """Was das Fenster einsammelt, muss der Dialog lesen können.

    Szene und Körper führen ihre Inhalte als **Wörterbuch**. Über sie zu
    iterieren gibt Kennungen, und der Dialog fragt danach ``.id`` einer
    Zeichenkette. Kein Test mit Attrappen kann das sehen — er bekommt seine
    Merkmale ja vom Test und nicht vom Fenster; auffallen würde es erst beim
    ersten echten Klick auf den Knopf.
    """
    window = MainWindow(Session(), UiSettings())
    try:
        window.session.import_model(MESHES / "cube_clean.stl")
        window.session.wait_for_idle()
        window.session.evaluate_now()

        features = window._result_features()

        assert features, "ein Würfel hat erkannte Flächen — sonst prüft der Test nichts"
        assert all(isinstance(entry, Feature) for entry in features)
        # Und genau die Frage, an der es scheiterte: hat jedes ein ``id``?
        assert all(str(entry.id) for entry in features)
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()


def test_the_button_stays_locked_until_the_project_can_carry_a_part(qt_app: QApplication) -> None:
    """Drei Bedingungen, drei Sätze — und keiner davon ist ein grauer Knopf.

    Der Reihe nach: nichts gerechnet, dann gerechnet aber ohne Parameter. Die
    dritte Lage (Schritte vorhanden) ist dabei schon erfüllt, sobald ein Modell
    geladen ist — sie hat ihren Satz für das leere Projekt, in dem jemand den
    Katalog aufmacht, bevor er irgendetwas getan hat.
    """
    window = MainWindow(Session(), UiSettings())
    try:
        can, reason = window._recipe_readiness()
        assert not can
        assert reason, "§2.7: ein gesperrter Knopf ohne Grund ist eine Sackgasse"

        window.session.import_model(MESHES / "cube_clean.stl")
        window.session.wait_for_idle()
        window.session.evaluate_now()

        can, reason = window._recipe_readiness()
        assert not can, "ohne Projektparameter wäre der Baustein starr"
        assert "Projektparameter" in reason

        window.session.project.document.parameters["breite"] = Parameter(
            name="breite", value=20.0, unit="mm", title="Breite"
        )
        can, reason = window._recipe_readiness()
        assert can, reason
        assert reason == ""
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()
