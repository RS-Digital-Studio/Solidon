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
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.knowledge.parts.registry import _NAME_PATTERN
from app.core.scene.project import new_project
from app.core.types import Document, Feature, Operation, Parameter, Transaction
from app.ui.catalog import PartCatalog
from app.ui.main_window import MainWindow
from app.ui.recipe_dialog import RecipeDialog, _identifier, taken_name
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
        assert rows["breite"].unit.currentData() == "mm"
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


def test_a_derived_value_is_not_released_behind_the_back(qt_app: QApplication) -> None:
    """Ein abgeleiteter Wert war vorgehakt und verlor still seine Formel.

    Der Kern ersetzt beim Bauen Wert **und** Ausdruck (``_with_values``), und
    das ist dort richtig: Ein überlebender Ausdruck machte aus dem Feld im
    Bausteindialog eine Attrappe. Falsch war, dass niemand gefragt wurde. Ein
    Weg-2-Projekt mit ``breite = 40`` und ``hoehe = =@breite/2`` wurde damit zu
    einem Baustein mit zwei unabhängigen Feldern: „Breite" auf 60 ließ „Höhe"
    auf 20 stehen statt auf 30, ohne ein Wort.

    Verboten ist es nicht — die Bindung zu lösen ist ein zulässiger Wunsch.
    Die Zeile geht nur ohne Haken auf und sagt daneben, was ein Haken dort
    bedeutet.
    """
    document = replace(
        _document(),
        parameters={
            "breite": Parameter(name="breite", value=40.0, unit="mm", title="Breite"),
            "hoehe": Parameter(
                name="hoehe", value=20.0, unit="mm", title="Höhe", expression="=@breite/2"
            ),
        },
    )
    dialog = RecipeDialog(document, {}, (1,), (_feature("hole_1"),), None)  # type: ignore[arg-type]
    try:
        rows = {row.name: row for row in dialog._params}

        assert rows["breite"].take.isChecked(), "ein freier Wert bleibt vorgehakt"
        assert not rows["hoehe"].take.isChecked(), "ein abgeleiteter nicht"

        satz = rows["hoehe"].take.toolTip()
        assert "@breite" in satz, f"der Satz nennt die Formel: {satz!r}"
        assert "Formel" in satz, f"und was ein Haken mit ihr macht: {satz!r}"
        # Regel 18: nicht nur das fehlende Häkchen — der Satz steht sichtbar
        # da und wird vorgelesen.
        assert rows["hoehe"].hint is not None
        assert rows["hoehe"].hint.text() == satz
        assert rows["hoehe"].take.accessibleDescription() == satz
        assert rows["breite"].hint is None, "wo nichts abgeleitet ist, steht kein Satz"

        # Und was der Kern bekommt, folgt dem Haken: der abgeleitete Wert ist
        # nicht dabei, solange niemand ihn angehakt hat.
        freigegeben = {row.name for row in dialog._params if row.take.isChecked()}
        assert freigegeben == {"breite"}

        rows["hoehe"].take.setChecked(True)
        freigegeben = {row.name for row in dialog._params if row.take.isChecked()}
        assert freigegeben == {"breite", "hoehe"}, "wer will, darf — er weiß jetzt nur, was"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_all_derived_says_what_to_do_instead_of_calling_the_part_rigid(
    qt_app: QApplication,
) -> None:
    """Trägt jeder Wert einen Ausdruck, ist keine Zeile vorgehakt.

    „Geben Sie mindestens ein Maß frei — sonst ist das Teil starr" ließe den
    Kunden dann nach einem Haken suchen, den er längst sieht: Er sieht drei,
    und keiner ist gesetzt. Der Satz muss sagen, warum.
    """
    document = replace(
        _document(),
        parameters={
            "hoehe": Parameter(name="hoehe", value=20.0, expression="=@breite/2"),
            "tiefe": Parameter(name="tiefe", value=10.0, expression="=@breite/4"),
        },
    )
    dialog = RecipeDialog(document, {}, (1,), (_feature("hole_1"),), None)  # type: ignore[arg-type]
    try:
        dialog.title.setText("Halter")

        assert not dialog._save.isEnabled()
        grund = dialog._save.toolTip()
        assert "gerechnet" in grund, f"der Grund nennt die Lage: {grund!r}"
        assert "starr" not in grund, f"und schickt nicht auf die falsche Suche: {grund!r}"
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


# --- die drei Funde aus Roberts Komplett-Review vom 25.08.2026 --------------------


def test_every_title_becomes_a_name_the_registry_accepts() -> None:
    """Was der Kunde tippt, muss durch ``^[a-z][a-z0-9_]*$`` passen.

    Zwei Lücken, beide vom Rezept-Reviewer gefunden und hier nachgemessen: Eine
    führende Ziffer bleibt vorn stehen, und ``é`` wie ``ñ`` sind ``isalnum()``
    — sie überlebten den Filter und scheiterten erst im Register. Der Kunde
    tippte „Café-Halter" und bekam einen internen Fehler statt eines Bausteins.

    Geprüft wird gegen **das Muster des Registers**, nicht gegen eine Liste
    erwarteter Namen: Ein Test, der die Umschrift festschreibt, verbietet ihre
    Verbesserung.
    """
    for titel in (
        "3er Halter",
        "Café-Halter",
        "Señor Box",
        "2. Versuch",
        "Größe 3 / Version 2",
        "!!!",
        "Halter für die Werkbank",
        "ÜBERHANG",
    ):
        name = _identifier(titel)
        assert _NAME_PATTERN.match(name), f"{titel!r} ergibt {name!r} — das Register lehnt es ab"

    # **Und der Buchstabe bleibt ein Buchstabe.** Gültig wäre auch
    # ``caf_halter`` — der Filter macht aus jedem fremden Zeichen einen
    # Unterstrich, und das Muster nimmt es an. Der Name soll aber lesbar sein,
    # und dafür wird der Akzent abgetrennt statt das ``e`` weggeworfen. Die
    # Gegenprobe ohne die Faltung blieb sonst grün.
    assert "cafe" in _identifier("Café-Halter"), "aus é wird e, nicht ein Unterstrich"
    assert "senor" in _identifier("Señor Box"), "und aus ñ ein n"


def test_a_name_that_is_taken_is_recognised_as_taken(tmp_path: Path) -> None:
    """Ein zweiter Baustein desselben Namens darf den ersten nicht überschreiben.

    ``recipes.save`` schreibt ``<name>.json`` bedingungslos, ``register`` meldet
    die Kollision erst danach — wer einen Namen zweimal vergibt, verlöre still
    sein erstes Rezept. Gefragt wird deshalb vor dem Schreiben, und zwar an
    **beiden** Orten: Registriert ist, was beim Start geladen wurde; auf der
    Platte kann eine Datei liegen, die dabei fehlgeschlagen ist.
    """
    from app.core.knowledge.parts import recipe as recipes

    assert not taken_name("nagelneuer_name_ohne_datei")

    ordner = recipes.recipes_dir()
    ordner.mkdir(parents=True, exist_ok=True)
    liegend = ordner / "schon_da.json"
    liegend.write_text("{}", encoding="utf-8")
    try:
        assert taken_name("schon_da"), "eine Datei auf der Platte zählt"
    finally:
        liegend.unlink()

    assert taken_name("nut_trap"), "und ein registrierter Baustein erst recht"


def test_cancelling_during_the_range_check_creates_nothing(qt_app: QApplication) -> None:
    """Wer abbricht, bekommt keinen Baustein — auch wenn der Test schon läuft.

    Der Bereichstest läuft in einem Arbeiter und lässt sich nicht anhalten. Sein
    Ergebnis muss deshalb verfallen: Ohne das legte ``_checked`` an, nachdem der
    Dialog längst zu war — ein Ergebnis auf eine zurückgezogene Frage.
    """
    dialog = _dialog(qt_app, (_feature("hole_1"),))
    try:
        dialog.title.setText("Werkbankhalter")
        geschrieben: list[object] = []

        dialog.reject()
        assert dialog._abandoned, "der Abbruch wird vermerkt"

        # Das Ergebnis kommt jetzt zu spät — es darf nichts mehr auslösen.
        dialog.saved.connect(geschrieben.append)
        dialog._checked(object())

        assert not geschrieben, "nach dem Abbruch entsteht kein Baustein"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_the_range_check_shows_how_far_it_is_and_can_be_stopped(qt_app: QApplication) -> None:
    """§2.8: Was länger als zwei Sekunden dauert, zeigt Fortschritt und lässt sich abbrechen.

    check ruft je Ecke progress(anteil, satz) und fragt davor
    token.is_cancelled — der Balken stand trotzdem auf setRange(0, 0),
    also auf unbestimmt, und abbrechen ließ sich nichts. Bei drei freigegebenen
    Maßen sind es sechs Ecken, und jede rechnet den ganzen Ausschnitt.

    Die Zahl steht dabei **neben** dem Balken: Mittig darauf wandert der Rand
    der Füllung unter ihr durch, und ab sechzig Prozent liegt sie auf Bernstein
    (tests/test_style.py).
    """
    dialog = _dialog(qt_app, (_feature("hole_1"),))
    try:
        assert not dialog.progress.isTextVisible(), "die Zahl gehört nicht auf den Balken"
        assert dialog.progress.maximum() == 100, "und der Balken kennt sein Ziel"

        dialog._show_waiting(True)
        dialog._step(0.5, "Bereichstest, Ecke 3 von 6")

        assert dialog.progress.value() == 50
        assert "50" in dialog.percent.text(), "die Zahl steht daneben"
        assert "Ecke 3 von 6" in dialog.report.text()

        # Abbrechen hält die Prüfung an, ohne den Dialog zu verwerfen.
        dialog._stop_check()

        assert not dialog.progress.isVisible()
        assert not dialog._abandoned, "der Dialog bleibt offen"

        # Und ein Ergebnis, das danach noch eintrifft, legt nichts mehr an.
        angelegt: list[object] = []
        dialog.saved.connect(angelegt.append)
        dialog._checked(object())
        assert not angelegt, "nach dem Abbruch entsteht kein Baustein"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_a_value_of_zero_still_gets_a_range(qt_app: QApplication) -> None:
    """Die Vorbelegung muss auch um die Null herum ein Bereich sein.

    ``min(value/2, value)`` und ``max(value*2, value)`` sind bei 0 beide 0 und
    stehen bei einem negativen Wert verkehrt herum. Beides ergibt
    ``min == max``: Der Bereichstest fährt dann eine einzige Ecke ab und meldet
    sie als bestanden — eine Zusage über einen Bereich, den niemand geprüft hat.
    """
    document = replace(
        new_project().document,
        parameters={
            "null": Parameter(name="null", value=0.0, unit="mm", title="Versatz"),
            "minus": Parameter(name="minus", value=-8.0, unit="mm", title="Tiefe"),
        },
    )
    dialog = RecipeDialog(document, {}, (1,), (_feature("hole_1"),), None)  # type: ignore[arg-type]
    try:
        for row in dialog._params:
            assert row.minimum.value() < row.maximum.value(), (
                f"{row.name}: {row.minimum.value()} bis {row.maximum.value()} ist kein Bereich"
            )
            assert row.ordered(), f"{row.name}: die Vorgabe liegt außerhalb"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_limits_the_wrong_way_round_block_the_button(qt_app: QApplication) -> None:
    """Min 30 bei Max 10 ist kein Bereich — und der Knopf sagt es.

    Der Bereichstest fährt die Ecken zwischen Minimum und Maximum ab. Steht das
    Minimum darüber, prüft er einen Bereich, den es nicht gibt.
    """
    dialog = _dialog(qt_app, (_feature("hole_1"),))
    try:
        dialog.title.setText("Werkbankhalter")
        assert dialog._save.isEnabled()

        dialog._params[0].minimum.setValue(300.0)

        assert not dialog._save.isEnabled(), "verdrehte Grenzen sperren das Anlegen"
        assert "größten" in dialog._save.toolTip(), (
            f"der Grund nennt die Grenzen nicht: {dialog._save.toolTip()!r}"
        )
    finally:
        dialog.release()
        dialog.deleteLater()


def test_two_places_may_not_share_one_name(qt_app: QApplication) -> None:
    """Zwei gleiche Namen überschreiben sich still im Wörterbuch.

    ``capture`` bekommt die Merkmale als ``{öffentlicher Name: Kennung}``. Wer
    zwei Bohrungen denselben Namen gibt, bekommt einen Baustein mit einer — ohne
    Meldung, ohne Fehler.
    """
    dialog = _dialog(qt_app, (_feature("hole_1"), _feature("hole_2")))
    try:
        dialog.title.setText("Werkbankhalter")
        assert dialog._save.isEnabled()

        dialog._features[0].name.setText("bohrung")
        dialog._features[1].name.setText("bohrung")

        assert not dialog._save.isEnabled(), "zwei gleiche Namen sperren das Anlegen"
        assert "denselben Namen" in dialog._save.toolTip()

        dialog._features[1].name.setText("bohrung_2")
        assert dialog._save.isEnabled(), "verschiedene Namen gehen wieder"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_a_full_disk_says_so_instead_of_falling_through(qt_app: QApplication) -> None:
    """``OSError`` beim Schreiben ist kein ``AppError`` — und darf nicht durchfallen.

    Volle Platte, Schreibschutz, ein Ordner, den jemand weggezogen hat: ``save``
    reicht den Fehler durch. Ungefangen verlässt er den Slot, und der Dialog
    steht mit laufendem Balken da und sagt nichts (Regel 17).
    """
    from app.core.knowledge.parts import recipe as recipes

    dialog = _dialog(qt_app, (_feature("hole_1"),))
    original = recipes.replace
    try:
        dialog._show_waiting(True)

        def voll(*_args: object, **_kwargs: object) -> None:
            raise OSError(28, "No space left on device")

        recipes.replace = voll  # type: ignore[assignment]
        dialog._checked(object())

        assert not dialog._checking, "der Balken bleibt nicht stehen"
        assert dialog.report.text().strip(), "und der Dialog sagt, was war"
        assert "space" in dialog.report.text() or "Datei" in dialog.report.text()
    finally:
        recipes.replace = original  # type: ignore[assignment]
        dialog.release()
        dialog.deleteLater()


def test_a_second_click_does_not_start_a_second_worker(qt_app: QApplication) -> None:
    """Zwei Klicks, ein Arbeiter — sonst prüft der erste ins Leere.

    Nach einem Fehlschlag gibt ``_update_enabled`` den Knopf wieder frei. Wer
    dann noch einmal drückt, während die erste Prüfung läuft, überschrieb
    ``self._worker``: Der erste lief ohne Halter weiter und meldete in einen
    Dialog, der ihn nicht mehr kennt — und setzte dabei den Balken des zweiten
    auf null zurück.

    Geprüft wird der Wächter, nicht die Aufnahme: ``capture`` und die
    Namensprüfung sind hier Attrappen, der Arbeiter dagegen ein echter, der
    nur nicht fertig wird.
    """
    import app.ui.recipe_dialog as module

    dialog = _dialog(qt_app, (_feature("hole_1"),))
    started: list[object] = []

    class Endless(module._CheckWorker):  # type: ignore[misc]
        """Ein Arbeiter, der nicht fertig wird — wie einer, der wirklich rechnet."""

        def work(self) -> None:
            while not self.is_cancelled:
                self.msleep(10)

    original_worker = module._CheckWorker
    original_capture = module.recipes.capture
    original_taken = module.taken_name
    original_start = dialog._leash.start
    try:
        module._CheckWorker = Endless  # type: ignore[misc]
        module.recipes.capture = lambda *a, **k: SimpleNamespace(name="werkbankhalter")  # type: ignore[assignment]
        module.taken_name = lambda name: False  # type: ignore[assignment]
        dialog._leash.start = lambda worker: (  # type: ignore[method-assign]
            started.append(worker),
            original_start(worker),
        )[-1]
        dialog.title.setText("Werkbankhalter")

        dialog._store()
        first = dialog.report.text()
        dialog._store()

        assert len(started) == 1, f"{len(started)} Arbeiter statt einem: {dialog.report.text()!r}"
        assert dialog.report.text() == first, "und der zweite Klick hat nichts zurückgesetzt"
    finally:
        module._CheckWorker = original_worker  # type: ignore[misc]
        module.recipes.capture = original_capture  # type: ignore[assignment]
        module.taken_name = original_taken  # type: ignore[assignment]
        dialog._leash.start = original_start  # type: ignore[method-assign]
        dialog.reject()
        dialog.release()
        dialog.deleteLater()


def test_the_cut_runs_off_the_main_thread(qt_app: QApplication) -> None:
    """``capture`` rechnet — und rechnete im Qt-Hauptthread (§2.8).

    Der Name täuscht: ``capture`` liest nicht nur Werte ab, es rechnet den
    Ausschnitt einmal durch (die Probe aus Konzept §18a). Gemessen am
    25.08.2026 an einem echten Ausschnitt: 85 ms für einunddreißig Boolesche an
    Grundkörpern, aber **3900 ms** für Kugel → glätten → aushöhlen. Das lief im
    Hauptthread, und zwar bevor der Fortschrittsbalken sichtbar wurde — der
    Kunde sah vier Sekunden ein totes Fenster und danach einen Balken.

    Geprüft wird die Thread-Kennung, nicht die Dauer: Eine Zeitmessung sagt
    „schnell genug auf dieser Maschine", die Kennung sagt „woanders". Die Dauer
    steht als zweite Aussage daneben, weil eine Attrappe, die im richtigen
    Thread liefe und trotzdem blockierte, den ersten Satz erfüllte.
    """
    import threading
    import time

    import app.ui.recipe_dialog as module
    from app.core.errors import ValidationError

    dialog = _dialog(qt_app, (_feature("hole_1"),))
    main_thread = threading.get_ident()
    seen: dict[str, int] = {}
    release = threading.Event()

    def slow_cut(*_args: object, **_kwargs: object) -> None:
        seen["thread"] = threading.get_ident()
        release.wait(3.0)
        # Ein Fehler statt eines Rezepts: Der Test will den Schnitt messen,
        # nicht den Bereichstest danach mitrechnen.
        raise ValidationError(field="op_ids", detail="Probe", constraint="empty")

    original_capture = module.recipes.capture
    original_taken = module.taken_name
    try:
        module.recipes.capture = slow_cut  # type: ignore[assignment]
        module.taken_name = lambda name: False  # type: ignore[assignment]
        dialog.title.setText("Werkbankhalter")

        started = time.perf_counter()
        dialog._store()
        took = time.perf_counter() - started

        assert dialog._checking, "der Balken steht schon da, während gerechnet wird"

        for _ in range(400):
            if "thread" in seen:
                break
            qt_app.processEvents()
            time.sleep(0.005)

        assert seen.get("thread") is not None, "der Schnitt wurde nie betreten"
        assert seen["thread"] != main_thread, "der Schnitt läuft im Oberflächen-Thread"
        assert took < 0.5, f"_store hat {took:.2f} s blockiert — es wartet auf den Schnitt"
    finally:
        release.set()
        module.recipes.capture = original_capture  # type: ignore[assignment]
        module.taken_name = original_taken  # type: ignore[assignment]
        dialog.release()
        dialog.deleteLater()


def test_a_refused_cut_keeps_its_own_words(qt_app: QApplication) -> None:
    """Der Satz des Kerns überlebt die Fahrt aus dem Arbeiter heraus (Regel 17).

    ``Worker.crashed`` gibt eine Zeichenkette. Käme der Fehler des Schnitts auf
    diesem Weg, fände ``_failed`` weder ``title`` noch ``detail`` und zeigte
    seinen Notsatz — und der Kunde läse „ließ sich nicht anlegen" statt
    „wählen Sie mindestens einen Schritt".
    """
    import time

    import app.ui.recipe_dialog as module
    from app.core.errors import ValidationError

    dialog = _dialog(qt_app, (_feature("hole_1"),))

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise ValidationError(
            field="op_ids",
            detail="Der Ausschnitt ist leer — wählen Sie mindestens einen Schritt.",
            constraint="empty",
        )

    original_capture = module.recipes.capture
    original_taken = module.taken_name
    try:
        module.recipes.capture = refuse  # type: ignore[assignment]
        module.taken_name = lambda name: False  # type: ignore[assignment]
        dialog.title.setText("Werkbankhalter")
        dialog._store()

        for _ in range(400):
            if not dialog._checking:
                break
            qt_app.processEvents()
            time.sleep(0.005)

        assert "mindestens einen Schritt" in dialog.report.text(), (
            f"der Grund kam nicht an: {dialog.report.text()!r}"
        )
        assert not dialog._checking, "und der Balken bleibt nicht stehen"
    finally:
        module.recipes.capture = original_capture  # type: ignore[assignment]
        module.taken_name = original_taken  # type: ignore[assignment]
        dialog.release()
        dialog.deleteLater()


def test_a_taken_name_offers_replacing_instead_of_refusing(
    qt_app: QApplication,
) -> None:
    """„Ändern heißt neu speichern" — das verspricht das Handbuch (§Eigene Bausteine).

    Wer die Breite seines Halters nachträglich ändert, soll keinen zweiten
    Namen erfinden müssen. Der Weg war nie eingelöst: Vor dem 25.08.2026 endete
    er im Datenverlust (``save`` überschrieb, ``register`` lehnte danach ab),
    danach in einer ehrlichen Absage. Jetzt ist er ein Weg.

    Geprüft wird gegen einen **wirklich vergebenen** Namen — die
    Bausteinbibliothek trägt ``pegboard_hook``. Eine Attrappe für ``taken_name``
    prüfte, ob der Dialog eine Attrappe ruft; sie sagte nichts darüber, ob die
    echte Prüfung anschlägt.
    """
    from app.core.knowledge.parts import PARTS

    assert PARTS.has("pegboard_hook"), "der Name ist die Grundlage dieses Tests"

    dialog = _dialog(qt_app, (_feature("hole_1"),))
    try:
        dialog.title.setText("Werkbankhalter")
        assert dialog._save.isEnabled()
        assert dialog._save.text() == "Baustein anlegen", "ein freier Name legt an"
        assert not dialog._save.toolTip(), "und braucht keine Warnung"

        dialog.title.setText("Pegboard Hook")

        assert dialog._save.isEnabled(), "ein vergebener Name ist kein Hindernis"
        assert dialog._save.text() == "Baustein ersetzen", (
            f"der Knopf sagt, was er tut: {dialog._save.text()!r}"
        )
        assert "Ersetzt den vorhandenen" in dialog._save.toolTip(), (
            f"und daneben steht, was mit dem alten Stand geschieht: {dialog._save.toolTip()!r}"
        )

        dialog.title.setText("Pegboard Hook 2")
        assert dialog._save.text() == "Baustein anlegen", "und zurück, sobald der Name frei ist"
        assert not dialog._save.toolTip()
    finally:
        dialog.release()
        dialog.deleteLater()


def test_a_crashed_worker_does_not_show_a_python_method(qt_app: QApplication) -> None:
    """``crashed`` gibt eine Zeichenkette — und die hat ein ``title``.

    ``str.title()`` ist eine Methode, ``getattr(text, "title")`` gibt sie
    zurück, und sie ist wahr. Ohne Verpackung in einen ``InternalError`` las
    ``_failed`` sie als Titel, und im Fenster stand wörtlich
    ``<built-in method title of str object at 0x…>`` (3d-druck-43, K-4).

    Der Fall entsteht nur bei einem **unerwarteten** Absturz des Arbeiters —
    ein ``AppError`` fährt über ``failed`` und war nie betroffen. Genau deshalb
    fiel es niemandem auf.
    """
    import time

    import app.ui.recipe_dialog as module

    dialog = _dialog(qt_app, (_feature("hole_1"),))

    def burst(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("manifold3d ist abgestürzt")

    original_capture = module.recipes.capture
    original_taken = module.taken_name
    try:
        module.recipes.capture = burst  # type: ignore[assignment]
        module.taken_name = lambda name: False  # type: ignore[assignment]
        dialog.title.setText("Werkbankhalter")
        dialog._store()

        for _ in range(400):
            if not dialog._checking:
                break
            qt_app.processEvents()
            time.sleep(0.005)

        shown = dialog.report.text()
        assert "built-in method" not in shown, f"eine Python-Innerei im Fenster: {shown!r}"
        assert "abgestürzt" in shown, f"und der Grund fehlt: {shown!r}"
    finally:
        module.recipes.capture = original_capture  # type: ignore[assignment]
        module.taken_name = original_taken  # type: ignore[assignment]
        dialog.release()
        dialog.deleteLater()


def test_equal_limits_are_not_a_range(qt_app: QApplication) -> None:
    """``min == max`` liest sich wie eine Ordnung und ist eine einzige Ecke.

    Der Bereichstest fährt sie ab und meldet „bestanden" — dieselbe
    Falschaussage wie bei verdrehten Grenzen, nur unauffälliger (K-14). Dazu
    wäre ein freigegebenes Maß, das sich nicht ändern lässt, ein Feld, das der
    Kunde vergeblich anfasst: Wer einen festen Wert will, gibt ihn nicht frei.
    """
    dialog = _dialog(qt_app, (_feature("hole_1"),))
    try:
        dialog.title.setText("Werkbankhalter")
        assert dialog._save.isEnabled()

        row = dialog._params[0]
        row.minimum.setValue(40.0)
        row.default.setValue(40.0)
        row.maximum.setValue(40.0)

        assert not row.ordered(), "gleich ist kein Bereich"
        assert not dialog._save.isEnabled(), "und der Knopf sagt es"
        assert "zwei verschiedene Enden" in dialog._save.toolTip()
    finally:
        dialog.release()
        dialog.deleteLater()


def test_the_button_cannot_while_the_check_runs(qt_app: QApplication) -> None:
    """Während gerechnet wird, kann der Knopf nicht — und sagt warum (K-20).

    Der Wächter in ``_store`` kehrte wortlos zurück. Er bleibt als Riegel, aber
    die Auskunft gehört an den Knopf: Ein gesperrter Knopf mit Grund ist eine
    Antwort, ein Klick ohne Wirkung ist keine.
    """
    import app.ui.recipe_dialog as module

    dialog = _dialog(qt_app, (_feature("hole_1"),))
    started: list[object] = []

    class Endless(module._CheckWorker):  # type: ignore[misc]
        def work(self) -> None:
            while not self.is_cancelled:
                self.msleep(10)

    original_worker = module._CheckWorker
    original_taken = module.taken_name
    original_start = dialog._leash.start
    try:
        module._CheckWorker = Endless  # type: ignore[misc]
        module.taken_name = lambda name: False  # type: ignore[assignment]
        dialog._leash.start = lambda worker: (  # type: ignore[method-assign]
            started.append(worker),
            original_start(worker),
        )[-1]
        dialog.title.setText("Werkbankhalter")
        dialog._store()

        assert not dialog._save.isEnabled(), "während der Prüfung kann er nicht"
        assert "einen Augenblick" in dialog._save.toolTip(), (
            f"und sagt warum: {dialog._save.toolTip()!r}"
        )

        # Und ein Signal, das _update_enabled auslöst, gibt ihn nicht frei —
        # genau daran scheiterte der alte Stand.
        dialog.title.setText("Werkbankhalter 2")
        assert not dialog._save.isEnabled(), "auch nach einem Tastendruck nicht"
        assert len(started) == 1
    finally:
        module._CheckWorker = original_worker  # type: ignore[misc]
        module.taken_name = original_taken  # type: ignore[assignment]
        dialog._leash.start = original_start  # type: ignore[method-assign]
        dialog.reject()
        dialog.release()
        dialog.deleteLater()


def test_a_failed_range_check_leaves_the_dialog_with_the_signal(qt_app: QApplication) -> None:
    """Der Warnsatz überlebt das Schließen, weil er mit dem Signal hinausfährt.

    Er stand im Dialog und wurde einen Atemzug später von ``accept()``
    unlesbar gemacht (K-15). §24.5 verlangt den Hinweis, nicht die
    Verweigerung — also muss er dorthin, wo nach dem Schließen noch jemand
    hinsieht: in die Statuszeile des Fensters.
    """
    from types import SimpleNamespace

    import app.ui.recipe_dialog as module

    dialog = _dialog(qt_app, (_feature("hole_1"),))
    heard: list[tuple[str, bool]] = []
    dialog.saved.connect(lambda name, passed: heard.append((name, passed)))

    original_replace = module.recipes.replace
    try:
        module.recipes.replace = lambda *a, **k: None  # type: ignore[assignment]
        dialog._show_waiting(True)
        dialog._checked(
            SimpleNamespace(name="werkbankhalter", range_report=SimpleNamespace(passed=False))
        )

        assert heard == [("werkbankhalter", False)], (
            f"der gescheiterte Bereichstest reist nicht mit: {heard!r}"
        )

        heard.clear()
        dialog._show_waiting(True)
        dialog._checked(
            SimpleNamespace(name="werkbankhalter", range_report=SimpleNamespace(passed=True))
        )
        assert heard == [("werkbankhalter", True)]
    finally:
        module.recipes.replace = original_replace  # type: ignore[assignment]
        dialog.release()
        dialog.deleteLater()


def test_the_unit_is_chosen_not_typed(qt_app: QApplication) -> None:
    """„cm" schaltete die Umrechnung ab, und niemand sagte es (K-10).

    ``op_dialog.shown_unit`` zeigt ein Feld genau dann in der eingestellten
    Anzeigeeinheit, wenn seine Einheit ``mm`` ist (§19.3); der Kern bekommt in
    jedem Fall Millimeter (§11.1). Als Freitextfeld war das eine Falle: Das
    Feld sagte danach [cm], gebaut wurden mm.

    Eine unbekannte Einheit des Projektparameters wird trotzdem nicht still
    umgedeutet, sondern steht als eigener Eintrag da (Regel 21).
    """
    from app.core.units import DEGREE_UNIT
    from app.ui.recipe_dialog import UNITS

    # Gefragt wird der Kern, nicht eine zweite Schreibweise daneben. Hier stand
    # ``"grad"`` ausgeschrieben — und behauptete in derselben Zeile, die
    # Auswahl bilde den Kern ab, während der seit dem 20.08.2026 ``"°"``
    # führt. Der Test hat die Abweichung nicht gefunden, er hat sie
    # festgehalten.
    assert [code for code, _ in UNITS] == ["mm", DEGREE_UNIT, ""], (
        "die Auswahl bildet ab, was der Kern unterscheidet"
    )

    document = replace(
        _document(),
        parameters={
            "breite": Parameter(name="breite", value=40.0, unit="mm", title="Breite"),
            "krumm": Parameter(name="krumm", value=4.0, unit="cm", title="Tiefe"),
        },
    )
    dialog = RecipeDialog(document, {}, (1,), (_feature("hole_1"),), None)  # type: ignore[arg-type]
    try:
        rows = {row.name: row for row in dialog._params}

        assert rows["breite"].unit.currentData() == "mm"
        assert rows["krumm"].unit.currentData() == "cm", "die vorhandene Einheit bleibt stehen"
        assert "nicht umgerechnet" in rows["krumm"].unit.currentText(), (
            f"und sagt, was das bedeutet: {rows['krumm'].unit.currentText()!r}"
        )
        assert rows["krumm"].unit.findData("mm") >= 0, "und lässt sich zu mm ändern"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_the_unit_list_follows_a_language_change(qt_app: QApplication) -> None:
    """``UNITS`` steht im Modulrumpf, und ``tr()`` dort übersetzt beim Import.

    Beim Import gilt noch keine Sprache: Die drei Einträge blieben deutsch,
    auch nachdem ``app.rebuild_for_language`` das Fenster neu gebaut hatte —
    denn neu gebaut werden Fenster, nicht Module. ``_()`` gibt einen trägen
    Text, der seine Sprache erst beim ``str()`` sucht, und ``addItem`` ruft
    dieses ``str()`` beim Bauen der Zeile.

    **Beide Schritte**: ``install_language`` lädt den Katalog,
    ``set_language`` schaltet ihn scharf. Wer nur den zweiten ruft, bekommt
    die Message-ID zurück — also Deutsch — und misst seinen eigenen Aufbau.
    """
    from app.i18n import get_language, set_language, source_text, tr
    from app.i18n.catalog import install_language
    from app.ui.recipe_dialog import UNITS

    vorher = get_language()
    try:
        install_language("en")
        set_language("en")

        englisch = [tr(source_text(label)) for _code, label in UNITS]
        deutsch = [source_text(label) for _code, label in UNITS]
        # Zusicherung gegen die leere Menge: Ohne angekommenen Katalog wäre
        # jede „Übersetzung" ihre eigene Message-ID, und alles unten grün.
        assert englisch != deutsch, "kam der englische Katalog an?"

        dialog = RecipeDialog(_document(), {}, (1,), (_feature("hole_1"),), None)  # type: ignore[arg-type]
        try:
            box = dialog._params[0].unit
            gezeigt = [box.itemText(index) for index in range(box.count())]
            assert gezeigt == englisch, f"in der Startsprache hängengeblieben: {gezeigt}"
        finally:
            dialog.release()
            dialog.deleteLater()
    finally:
        set_language(vorher)


def test_the_window_says_when_the_range_check_did_not_pass(qt_app: QApplication) -> None:
    """Die andere Hälfte von K-15: Was mitreist, muss auch ankommen.

    Der Dialog gibt seit dem Umbau mit, ob der Bereichstest bestand — das
    allein hilft niemandem, wenn das Fenster beide Fälle gleich meldet. §24.5
    verlangt den Hinweis, nicht die Verweigerung: Der Baustein steht im
    Katalog, er trägt nur die Warnung mit.

    Dieser Test entstand aus einer **Falschmeldung meiner eigenen
    Gegenprobe**: Sie hielt einen Lauf ohne passenden Test für rot, weil
    pytest bei ``-k`` ohne Treffer mit 5 endet und „302 deselected" schreibt,
    nicht „no tests ran". Die Fensterseite war ungeprüft, und die Prüfung sagte
    das Gegenteil.
    """
    window = MainWindow(Session(), UiSettings())
    try:
        window._part_saved("werkbankhalter", True)
        good = window.status_message.text()

        window._part_saved("werkbankhalter", False)
        warned = window.status_message.text()

        assert good != warned, "beide Fälle sagen dasselbe"
        assert "kein brauchbarer Körper" in warned, f"die Warnung fehlt: {warned!r}"
        assert "Katalog" in warned, "und dass er trotzdem da ist, auch"
    finally:
        window.session._dirty = False
        window.close()
        window.deleteLater()


def _history_document() -> Document:
    """Ein Dokument mit vier Schritten in drei Transaktionen.

    Die mittlere fasst zwei Operationen zusammen — der Fall, den der Verlauf
    aufklappt und der die Mehrfachauswahl interessant macht: Wer die
    Sammelzeile wählt, meint beide darunter.
    """
    ops = tuple(
        Operation(id=number, op="create_box", inputs=(), outputs=(f"body_{number}",), params={})
        for number in (1, 2, 3, 4)
    )
    return replace(
        new_project().document,
        ops=ops,
        transactions=(
            Transaction(id="t1", title="Quader anlegen", ops=(1,)),
            Transaction(id="t2", title="Teilung in zwei", ops=(2, 3)),
            Transaction(id="t3", title="Bohrung setzen", ops=(4,)),
        ),
    )


def _history_row(panel: Any, title: str) -> int:
    """Findet die Verlaufszeile zu einem Schritt — an ihrem Titel, nicht an
    ihrem ganzen Text.

    **Eine Verlaufszeile heißt nicht mehr wie ihr Schritt.** Seit
    ``a6d197d4`` trägt sie die Nummer davor und ein Kategoriesymbol daneben:
    aus „Bohrung setzen" wurde „4  Bohrung setzen". Zwei Tests hier bauten
    sich ein Wörterbuch aus dem nackten Zeilentext und schlugen den Titel
    darin nach; einer davon lag danach vier Tage rot auf ``main``
    (``ec58c62e`` zog zwei andere nach, diesen nicht — er steht in einer
    Datei, die nach Rezepten heißt und nicht nach Verlauf).

    Und die Nummer ist zugleich das, was das alte Wörterbuch **vorher**
    zusammenfallen ließ: Drei Schritte dieses Dokuments heißen „Quader
    anlegen", und ohne Nummer davor waren das drei gleiche Schlüssel, von
    denen ein Wörterbuch stumm den letzten behält. Gemessen an der heutigen
    Zeile stimmt es wieder — 5 Zeilen, 5 Schlüssel —, aber nur, weil die
    Nummer sie unterscheidet. Eine Eindeutigkeit, die an der Zählung eines
    Präfixes hängt, ist keine.

    Deshalb wird hier über den **Titel** gesucht und nicht über den ganzen
    Text nachgeschlagen, und die Eindeutigkeit steht als eigene Zusicherung
    daneben: „Quader anlegen" trifft drei Zeilen und macht den Test rot,
    statt ihn eine davon raten zu lassen (gemessen).
    """
    treffer = [
        index
        for index in range(panel.list.count())
        if panel.list.item(index).text().strip().endswith(title)
    ]
    assert treffer, (
        f"keine Verlaufszeile endet auf „{title}“ — "
        f"vorhanden: {[panel.list.item(i).text().strip() for i in range(panel.list.count())]}"
    )
    assert len(treffer) == 1, (
        f"„{title}“ trifft {len(treffer)} Zeilen — der Test würde eine davon raten"
    )
    return treffer[0]


def test_the_history_hands_over_what_is_chosen(qt_app: QApplication) -> None:
    """Der Verlauf gibt die gewählten Schritte heraus — aufsteigend und ganz.

    Das ist die fehlende Hälfte von §24.5: Das Rezeptformat nimmt seit je
    beliebige ``op_ids``, aber der Verlauf kannte nur einen Index, und deshalb
    wanderte immer der ganze Stapel in jeden Baustein.

    Zwei Zusagen, die man leicht übersieht. Eine gewählte **Sammelzeile**
    zählt mit allen ihren Operationen — sie trägt keine ``UserRole``, weil ein
    Doppelklick dort keine einzelne Operation zeigen könnte, und eine Auswahl,
    die daran scheitert, wäre stumm falsch. Und die Reihenfolge ist die des
    Stapels, nicht die der Klicks: Ein Rezept aus „Schritt 7, dann Schritt 3"
    gibt es nicht.
    """
    from app.ui.panels import HistoryPanel

    panel = HistoryPanel()
    panel.show_document(_history_document())

    assert panel.selected_operations() == (), "ohne Auswahl ist die Auswahl leer"

    panel.list.item(_history_row(panel, "Bohrung setzen")).setSelected(True)
    assert panel.selected_operations() == (4,), "eine Zeile, ihre eine Operation"

    panel.list.item(_history_row(panel, "Teilung in zwei")).setSelected(True)
    assert panel.selected_operations() == (2, 3, 4), (
        "die Sammelzeile bringt beide Schritte mit, und sortiert wird nach dem Stapel"
    )

    panel.list.clearSelection()
    assert panel.selected_operations() == (), "und Aufheben hebt auf"


def test_the_chosen_steps_reach_the_recipe(qt_app: QApplication, monkeypatch: Any) -> None:
    """Was der Verlauf hergibt, muss im Rezeptdialog ankommen.

    Der Test daneben prüft die Auswahl, ``scope_text`` prüft den Satz darüber
    — beides wäre grün, während das Fenster weiter den ganzen Stapel
    übergibt. Genau diese Lücke hat am 25.08.2026 schon einmal zugeschlagen:
    ``_save_as_part`` reichte ``enumerate``-Plätze statt ``Operation.id``
    weiter, acht grüne Tests standen daneben, und der letzte Schritt fiel
    still aus jedem Rezept. Eine Kette endet am letzten Glied.

    Geprüft werden beide Wege: die leere Auswahl (dann der ganze Stapel, der
    häufige Fall) und die getroffene.
    """
    seen: list[tuple[int, ...]] = []

    class _Spy:
        def __init__(self, document: Any, payloads: Any, op_ids: Any, *rest: Any, **kw: Any):
            seen.append(tuple(op_ids))
            self.saved = SimpleNamespace(connect=lambda *_args: None)

        def exec(self) -> int:
            return 0

        def release(self) -> None: ...

        def deleteLater(self) -> None:  # noqa: N802 — Qt-Name
            ...

    window = MainWindow(Session(), UiSettings())
    try:
        monkeypatch.setattr("app.ui.main_window.RecipeDialog", _Spy)
        monkeypatch.setattr(window, "_result_features", lambda: ())
        window.session.last_result = SimpleNamespace()  # type: ignore[assignment]
        window.session.project = replace(window.session.project, document=_history_document())
        window.history_panel.show_document(window.session.project.document)
        # Der Katalog wird nur als Elternteil gereicht und bekommt ``refresh``
        # ans Signal gehängt — mehr braucht dieser Weg von ihm nicht.
        catalog: Any = SimpleNamespace(refresh=lambda: None)

        window._save_as_part(catalog)
        assert seen[-1] == (1, 2, 3, 4), "ohne Auswahl geht der ganze Stapel mit"

        zeile = _history_row(window.history_panel, "Teilung in zwei")
        window.history_panel.list.item(zeile).setSelected(True)
        window._save_as_part(catalog)
        assert seen[-1] == (2, 3), "mit Auswahl genau sie — und nicht mehr"
    finally:
        window.session._dirty = False
        window.close()
        window.deleteLater()


def test_the_dialog_says_what_it_takes(qt_app: QApplication) -> None:
    """Über dem Dialog steht, welche Schritte in den Baustein wandern.

    „Auswahl als Baustein speichern" nennt eine Auswahl, und welche es ist,
    entscheidet sich außerhalb des Dialogs — im Verlauf, mit einem Klick, den
    der Kunde vielleicht gar nicht gemacht hat. Eine Vorgabe, die
    stillschweigend greift, ist eine Vermutung (§2.4), also sagt der Satz auch
    den Normalfall an.

    Ohne Fenster: eine Rechnung über zwei Zahlen, wie ``folded_groups``.
    """
    from app.ui.recipe_dialog import SCOPE_NUMBERS_SHOWN, scope_text

    whole = scope_text((1, 2, 3, 4), 4)
    assert "4" in whole, f"die Zahl fehlt: {whole!r}"

    part = scope_text((2, 3), 4)
    assert "2, 3" in part, f"die gewählten Schritte stehen da: {part!r}"
    assert "4" in part, "und wie viele es insgesamt sind"
    assert part != whole, "beide Fälle sagen dasselbe"

    one = scope_text((2,), 4)
    assert "1 Schritt" in one, f"kein „alle 1 Schritte“: {one!r}"

    many = scope_text(tuple(range(1, SCOPE_NUMBERS_SHOWN + 5)), 40)
    assert many.endswith("…"), f"eine lange Liste wird gekürzt: {many!r}"
    assert str(SCOPE_NUMBERS_SHOWN) in many, "bis zur Grenze zählt sie auf"

    assert scope_text((), 4), "und auch der leere Fall sagt etwas"
