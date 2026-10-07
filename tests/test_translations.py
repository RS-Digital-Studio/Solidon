"""Jeder Oberflächentext ist übersetzbar, und die Kataloge sind
vollständig (§4.1, §37.2).
"""

from __future__ import annotations

import ast
import os
import re
import unicodedata
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

import app
from app.core.knowledge.parts.registry import GROUPS
from app.i18n import SOURCE_LANGUAGE, TranslatableText, format_decimal, set_language
from app.i18n.catalog import available_languages, install_language, read_catalog
from app.i18n.extract import message_ids

PACKAGE_DIR = Path(app.__file__).parent
UI_DIR = PACKAGE_DIR / "ui"

#: Qt-Aufrufe, die einen Text vor den Nutzer bringen.
DISPLAY_CALLS = frozenset(
    {
        "setText",
        "setWindowTitle",
        "setToolTip",
        "setStatusTip",
        "setPlaceholderText",
        "addTab",
        "addItem",
        "addItems",
        "setSuffix",
        "setPrefix",
    }
)


def test_english_feature_names_distinguish_a_ring_groove_from_a_fillet() -> None:
    """Zwei verschiedene erkannte Formen dürfen nicht beide Fillet heißen."""
    from app.core.types import Feature
    from app.ui.labels import feature_name

    install_language("en")
    set_language("en")
    try:
        groove = Feature(id="torus_1", kind="torus", provenance="detected", params={"recess": True})
        fillet = Feature(
            id="fillet_1", kind="fillet", provenance="detected", params={"recess": False}
        )
        assert feature_name(groove.id, groove) == "Groove"
        assert feature_name(fillet.id, fillet) == "Fillet"
    finally:
        set_language("de")


@pytest.mark.parametrize(
    "example,parameter",
    [
        ("weg2-halter-konstruieren", "breite"),
        ("gehaeuse-mit-bausteinen", "wand"),
    ],
)
def test_english_tour_names_the_visible_parameter(example: str, parameter: str) -> None:
    """Die Anleitung führt zum Feldtitel des wirklich geladenen Beispiels."""
    from app.core import examples
    from app.core.scene.project import load
    from app.core.tour import tour_for

    install_language("en")
    set_language("en")
    try:
        project = load(examples.directory() / f"{example}.p3d")
        title = str(project.document.parameters[parameter].title)
        tour = tour_for(example)
        assert tour is not None
        assert any(title in str(step.text) for step in tour.steps)
        assert all(not re.search(rf"\b{parameter}\b", str(step.text)) for step in tour.steps)
    finally:
        set_language("de")


def test_spanish_tours_name_the_visible_actions() -> None:
    """Transaktion, Werkzeug und Abschluss heißen wie ihre echten Gegenstücke."""
    from app.core import examples
    from app.core.scene.project import load
    from app.core.tour import tour_for
    from app.i18n import tr

    install_language("es")
    set_language("es")
    try:
        project = load(examples.directory() / "drucker-kalibrieren.p3d")
        ops = {op.id for op in project.document.ops if op.op == "arrange_bed"}
        title = next(
            str(tx.title) for tx in project.document.transactions if ops.intersection(tx.ops)
        )
        tour = tour_for("drucker-kalibrieren")
        assert tour is not None and any(title in str(step.text) for step in tour.steps)
        sculpt = tour_for("weg4-figur-formen")
        assert sculpt is not None
        assert any(
            str(tr("Formen")) in str(step.text) and str(tr("Fertig")) in str(step.text)
            for step in sculpt.steps
        )
    finally:
        set_language("de")


@pytest.mark.parametrize(
    ("language", "foreign"),
    [("es", r"\b(?:elementos?|detalles?)\b"), ("pt", r"\b(?:elementos?|pormenor(?:es)?)\b")],
)
def test_a_feature_keeps_the_programs_word_in_spanish_and_portuguese(
    language: str, foreign: str
) -> None:
    """Ein Merkmal heißt „característica“, im Programm wie im Handbuch (Einheitlichkeit).

    Die Knöpfe sagten es längst, Handbuch und einige Meldungen sagten daneben
    „detalle(s)“ beziehungsweise „elemento(s)“ — der Kunde suchte einen
    Unterschied, den es nicht gibt (Handbuch-Wächter, Entscheidung zum
    Fließtext). Ein anderes Wort ist nur dort richtig, wo die Quelle selbst
    ein anderes nennt: *Element*, *Gegenstück*, *Detail*, *Einzelheit*.
    """
    catalog = read_catalog(language)
    other_word = re.compile(r"element|gegenstück|detail|einzelheit", re.IGNORECASE)
    drifted = [
        f"{key[:70]!r} → {value[:90]!r}"
        for key, value in catalog.items()
        if re.search(r"merkmal", key, re.IGNORECASE)
        and re.search(foreign, value, re.IGNORECASE)
        and not other_word.search(key)
    ]
    assert not drifted, "\n".join(drifted)
    named = [value for key, value in catalog.items() if re.search(r"merkmal", key, re.IGNORECASE)]
    assert sum("característica" in value.casefold() for value in named) > 50, (
        "Voraussetzung: das Programm nennt Merkmale „característica“"
    )


def test_french_range_check_warns_for_any_failed_corner() -> None:
    """Ein einziger gescheiterter Eckpunkt ist bereits ein Warnfall."""
    catalog = read_catalog("fr")
    body = next(
        value for key, value in catalog.items() if key.startswith("Der Halter für die Werkbank")
    )
    assert "à l'un des points testés, aucun corps utilisable" in body
    assert "Si nulle part" not in body


def test_italian_sculpt_manual_names_the_actual_modify_menu() -> None:
    """Die Formen-Seite nennt die Handlungen rechts, nicht mehr ein Menü.

    Bis zum 11.09.2026 stand *Weich verschmelzen* im Menü *Ändern*, und die
    italienische Fassung musste „Cambia" von „Modifica" (dem Bearbeiten-Menü)
    auseinanderhalten. Seit die Handlungen einer Auswahl rechts im Fenster
    stehen, gibt es das Menü nicht mehr — ein Text, der es noch nennt,
    schickt den Kunden an eine Stelle, die es nicht gibt.
    """
    catalog = read_catalog("it")
    body = next(
        value for key, value in catalog.items() if key.startswith("Manche Formen lassen sich")
    )
    assert f"nel menu «{catalog['Ändern']}»" not in body
    assert f"nel menu «{catalog['Bearbeiten']}»" not in body
    assert f"*{catalog['Weich verschmelzen']}*" in body
    assert catalog["Dreiecke angleichen"] in body


def test_italian_painted_strokes_are_painted_again_not_redrawn() -> None:
    """Was der Formpinsel malt, malt der Kunde neu — er zeichnet es nicht.

    „Ridisegna" ist das Wort für eine neu gezeichnete Kontur; im selben Satz
    hieß der Zug eben noch „dipinto". Jeder Text, der in der Quelle vom Malen
    spricht, bleibt im Italienischen beim Malen (RM-436).
    """
    catalog = read_catalog("it")
    painted = {
        key: value
        for key, value in catalog.items()
        if isinstance(value, str) and re.search(r"\b(malen|gemalt)\b", key)
    }
    assert painted, "kein Quelltext spricht mehr vom Malen — stimmt das Muster noch?"
    redrawn = [key for key, value in painted.items() if "disegn" in value.lower()]
    assert not redrawn, redrawn


#: Statische Meldungsfenster-Aufrufe. Nur an QMessageBox gezählt —
#: ``log.warning`` ist kein Dialog.
BOX_CALLS = frozenset({"information", "question", "warning", "critical"})

#: Widgets, die ihre Beschriftung als erstes Argument nehmen.
LABELLED_WIDGETS = frozenset(
    {"QLabel", "QPushButton", "QAction", "QGroupBox", "QCheckBox", "QToolBar", "QListWidgetItem"}
)


def test_every_text_is_translated() -> None:
    """Jede Sprache, die dasteht, ist fertig.

    Nicht nur englisch: die Liste kommt aus dem Katalogverzeichnis, also prüft
    dieser Test jede Sprache, die jemand hinzufügt, vom ersten Lauf an. Eine
    halb übersetzte Datei einzuchecken ist damit keine Option — sie wäre eine
    Sprache in der Auswahl, die mitten im Satz nach Deutsch zurückfällt.

    Alle Kataloge und die Umlautprüfung nutzen dieselbe Extraktion. Das spart
    auch bei xdist Mehrfacharbeit, ohne Quellen im Anwendungscode zu cachen.
    """
    ids = message_ids()
    # **Ohne diese Zeile ist der Test grün, wenn er nichts findet.** Ein
    # Verbotstest über eine gefilterte Menge prüft nichts, sobald die
    # Grundmenge leer ist — und message_ids() sammelt über den
    # Quelltext, also über etwas, das sich verschieben kann.
    assert ids, "keine Texte gefunden — sonst prüft dieser Test nichts"

    # **Die Zahl steht vorn, nicht nur die Liste.** pytest kürzt eine lange
    # Assert-Meldung mit „...“ — wer neun tote Schlüssel hat, sieht drei und
    # muss den Rest außerhalb des Tests nachbauen. Die Zahl im Kopf sagt
    # sofort, ob die Liste vollständig dasteht.
    languages = [entry for entry in available_languages() if entry != SOURCE_LANGUAGE]
    assert languages, "keine Übersetzungskataloge gefunden — sonst prüft dieser Test nichts"
    errors: list[str] = []
    for language in languages:
        catalog = read_catalog(language)
        missing = sorted(key for key in ids if not catalog.get(key))
        if missing:
            errors.append(f"{language}: {len(missing)} ohne Übersetzung\n" + "\n".join(missing))
        orphaned = sorted(key for key in catalog if key not in ids)
        if orphaned:
            errors.append(
                f"{language}: {len(orphaned)} nicht mehr gebraucht\n" + "\n".join(orphaned)
            )
    # Zusammengelegt heißt nicht verdeckt: Die Umlautprüfung meldet neben
    # den Katalogen, nicht an ihrer Stelle.
    try:
        _assert_source_text_uses_umlauts(ids)
    except AssertionError as error:
        errors.append(str(error))
    assert not errors, "\n".join(errors)


#: Ein Platzhalter im Quelltext: ``{name}``, nicht ``{}`` und nicht ``{0}``.
#: Die Oberfläche setzt sie namentlich (``.format(adresse=…)`` oder
#: ``.replace("{slicer}", …)``), und beide Wege brauchen den Namen.
#: Der Name darf Umlaute tragen — die Quelle ist deutsch, und ein Muster, das
#: bei ASCII endet, ließ einen verlorenen deutschen Platzhalter grün durch.
PLACEHOLDER = re.compile(r"\{([^\W\d]\w*)\}")


@pytest.mark.parametrize(
    "language", [entry for entry in available_languages() if entry != SOURCE_LANGUAGE]
)
def test_every_translation_keeps_its_placeholders(language: str) -> None:
    """Eine Übersetzung, die einen Platzhalter verliert, ist ein Kundenfehler.

    Die Prüfung darüber sagt, dass **eine** Übersetzung dasteht — nicht, dass
    sie einsetzbar ist. Wer ``{anzahl}`` verschreibt oder wegübersetzt, dessen
    Text zeigt beim Kunden entweder die Klammer wörtlich oder eine Zahl, die
    fehlt; welches von beiden, entscheidet allein die Einsetzweise:
    ``.format`` wirft bei einem **fremden** Namen und schweigt bei einem
    **fehlenden**, ``.replace`` schweigt in beiden Fällen. Keiner der beiden
    Wege bemerkt es also von selbst.

    Der Kern führt denselben Fehler seit je als Erinnerung — Platzhalter, die
    in ``detail`` und ``title`` stehen blieben. Für die Kataloge gab es die
    Prüfung nicht, und bei sechs Sprachen ist das eine Klasse, die wiederkommt.

    Verglichen werden **Mengen** und nicht Reihenfolgen: Eine Sprache darf ihre
    Satzstellung ändern. Nur fehlen darf keiner, und dazukommen auch nicht — ein
    Platzhalter, den die Quelle nicht kennt, wird nie gefüllt und steht als
    Klammer da.
    """
    catalog = read_catalog(language)
    assert catalog, f"{language}: leerer Katalog — sonst prüft dieser Test nichts"

    with_placeholders = [key for key in catalog if PLACEHOLDER.search(key)]
    assert with_placeholders, "keine Texte mit Platzhaltern — Muster prüfen"

    broken = []
    for key in sorted(with_placeholders):
        wanted = set(PLACEHOLDER.findall(key))
        found = set(PLACEHOLDER.findall(str(catalog[key])))
        if wanted != found:
            broken.append(f"  soll {sorted(wanted)} ist {sorted(found)}\n    {key}")

    assert not broken, f"{language}: {len(broken)} mit falschen Platzhaltern\n" + "\n".join(broken)


def test_a_broken_catalog_file_does_not_end_the_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Eine beschädigte Katalogdatei beendet nicht den Start.

    ``read_catalog`` war die einzige ungesicherte Dateilesung des Gebiets:
    ein halb geschriebenes ``fr.json`` — Update, voller Datenträger — hieß
    roher ``JSONDecodeError`` beim ersten ``install_language``. Jede
    Nachbarlesung fängt; jetzt fängt auch diese, mit Protokollzeile und
    Quellsprache als Ausweg.
    """
    from pathlib import Path

    from app.i18n import catalog

    broken = Path(str(tmp_path)) / "fr.json"
    broken.write_text('{"kaputt": ', encoding="utf-8")
    monkeypatch.setattr(catalog, "catalog_path", lambda language: broken)
    assert catalog.read_catalog("fr") == {}


def test_the_collector_knows_the_context_argument(tmp_path: object) -> None:
    """Ein Text mit Kontext wird unter seinem echten Schlüssel eingesammelt.

    ``_(…, Kontext)`` schlägt unter ``Kontext + chr(4) + Text`` nach — der
    Einsammler kannte nur das erste Argument. Der erste solche Aufruf bliebe
    in jeder Sprache deutsch, und die Übersetzungsprüfung (dieselbe
    Sammlung) merkte nichts. Latent, aber billig zu schließen.
    """
    from pathlib import Path

    probe = """from app.i18n import _, tr
A = _("Zug", "Skizze")
B = tr("Zug", context="Verlauf")
C = _("Ohne")
"""
    source = Path(str(tmp_path)) / "probe.py"
    source.write_text(probe, encoding="utf-8")
    marker = chr(4)
    found = message_ids([source])
    assert found == {f"Skizze{marker}Zug", f"Verlauf{marker}Zug", "Ohne"}


def test_the_catalog_actually_switches_the_language() -> None:
    install_language("en")
    text = TranslatableText("Abbrechen")
    assert text.translate("en") == "Cancel"
    assert text.translate("de") == "Abbrechen"

    set_language("en")
    try:
        assert str(text) == "Cancel"
    finally:
        set_language(SOURCE_LANGUAGE)


def test_each_catalog_defines_its_decimal_separator() -> None:
    """Eine neue Sprache braucht keine zweite feste Liste für Zahlen."""

    try:
        for language in available_languages():
            install_language(language)
            set_language(language)
            sample = "0,1" if language == SOURCE_LANGUAGE else read_catalog(language).get("0,1", "")
            assert sample, f"{language}: Dezimalmetadatum fehlt"
            shown = "1,5" if "," in sample else "1.5"
            assert format_decimal(1.5, 1) == shown
    finally:
        set_language(SOURCE_LANGUAGE)


def test_a_nested_value_follows_the_language_that_was_asked_for() -> None:
    """Ein Platzhalterwert kann selbst übersetzbar sein — und muss mitziehen.

    ``perceive.actions._no_way`` baut ``_("Dafür ist „{title}“ da.",
    title=<Titel einer Operation>)``. Über ``format`` löste der Titel sich bis
    zum 04.09.2026 über ``__str__`` auf, also gegen die **global** gesetzte
    Sprache statt gegen die genannte: ``translate("fr")`` gab einen
    französischen Satz mit deutschem Kern zurück, solange die Anwendung auf
    Deutsch stand.

    Geprüft wird deshalb mit einer Sprache, die **nicht** die aktive ist —
    andernfalls bliebe der Test grün, weil beide zufällig dasselbe liefern.
    Genau daran ist der Fehler so lange vorbeigekommen.
    """
    install_language("fr")
    innen = TranslatableText("Bohrung ändern")
    aussen = TranslatableText("Dafür ist „{title}“ da.", None, {"title": innen})

    assert innen.translate("fr") != innen.msgid, (
        "ohne übersetzten Kern misst dieser Test nichts — Katalogeintrag fehlt"
    )
    assert innen.translate("fr") in aussen.translate("fr"), (
        f"der eingebettete Titel blieb in der aktiven Sprache: {aussen.translate('fr')!r}"
    )


def test_the_source_language_stays_the_source_language_all_the_way_down() -> None:
    """Das Gegenstück: :func:`app.i18n.source_text` verspricht die Quellsprache.

    Für Dateinamen und Schlüssel darf nichts mit der Anzeige wandern. Ein
    verschachtelter Wert tat es trotzdem — er ging über ``__str__`` und kam
    übersetzt zurück. Gemessen am 04.09.2026: Bei aktivem Englisch lieferte
    ``source_text`` „Dafür ist „Change bore" da." — deutsche Hülle, fremder
    Kern, aus der einen Funktion, deren ganze Zusage die Quellsprache ist.
    """
    from app.i18n import source_text

    install_language("en")
    innen = TranslatableText("Bohrung ändern")
    aussen = TranslatableText("Dafür ist „{title}“ da.", None, {"title": innen})

    set_language("en")
    try:
        stabil = source_text(aussen)
    finally:
        set_language(SOURCE_LANGUAGE)

    assert stabil == "Dafür ist „Bohrung ändern“ da.", (
        f"die Anzeigesprache ist in die Quellsprache durchgeschlagen: {stabil!r}"
    )


def test_a_numeric_value_keeps_its_format_specification() -> None:
    """Die Gegenprobe zu den beiden darüber: Nur Texte werden aufgelöst.

    ``{free:.1f}`` steht so in den Katalogen. Wer die Werte pauschal durch
    ``str`` schickte, um die Verschachtelung zu erschlagen, machte aus der
    Formatangabe einen ``ValueError`` — der Fix wäre dann teurer als der
    Fehler.
    """
    from app.i18n import source_text

    text = TranslatableText(
        "{free:.1f} GB frei, {needed:.0f} gebraucht",
        None,
        {
            "free": 12.345,
            "needed": 7.6,
        },
    )

    assert str(text) == "12,3 GB frei, 8 gebraucht"
    assert source_text(text) == "12.3 GB frei, 8 gebraucht"


def test_a_number_in_a_value_takes_the_decimal_mark_of_the_language() -> None:
    """Eine Länge aus dem Kern steht im Satz so, wie die Sprache sie schreibt.

    ``format_length`` lässt den Punkt stehen, und der Kern reicht die Zahl als
    Platzhalterwert in seine Sätze. Am Fenster stand so im deutschen
    *Verrunden* „Wählen Sie einen Radius unter 15.00 mm“ — im Vorschauband und
    in der Absage, zwei Zeilen über einem Feld mit „40,00 mm“
    (Fensterabnahme 04.10.2026, RM-395). Pfade, Versionen und Adressen in einem
    Wert bleiben, wie sie sind; die Quellsprache für Dateinamen auch.
    """
    from app.core.units import format_length
    from app.i18n import source_text

    install_language("en")
    text = TranslatableText(
        "Wählen Sie einen Radius unter {largest}.", None, {"largest": format_length(15.0)}
    )
    assert text.translate("de") == "Wählen Sie einen Radius unter 15,00 mm."
    assert "15.00 mm" in text.translate("en")
    assert source_text(text) == "Wählen Sie einen Radius unter 15.00 mm."

    signed = TranslatableText("{x} bis {y}", None, {"x": format_length(-25.0), "y": 2.5})
    assert signed.translate("de") == "-25,00 mm bis 2,5"

    kept = TranslatableText(
        "{printer} {part} {version}",
        None,
        {"printer": "Snapmaker 2.0 A350", "part": "1.2", "version": "0.5.1"},
    )
    assert kept.translate("de") == "Snapmaker 2.0 A350 1.2 0.5.1", "Namen sind keine Zahlen"
    count = TranslatableText("{count} Teile", None, {"count": 3})
    assert count.translate("de") == "3 Teile", "eine ganze Zahl bleibt, wie sie ist"


def test_qt_standard_buttons_speak_the_application_language(qt_app: object) -> None:
    """Qt beschriftet OK/Abbrechen/Schließen selbst — ohne geladenen
    qtbase-Katalog stand dort „Cancel", mitten im deutschen Programm.

    Geprüft am echten Artefakt: einer QDialogButtonBox, nicht am Katalog.
    """
    from PySide6.QtCore import QTranslator
    from PySide6.QtWidgets import QDialogButtonBox

    from app.ui.app import install_qt_translations

    expected = {
        "de": ("Speichern", "Abbrechen", "OK", "Schließen"),
        "en": ("Save", "Cancel", "OK", "Close"),
        "es": ("Guardar", "Cancelar", "Aceptar", "Cerrar"),
        "fr": ("Enregistrer", "Annuler", "OK", "Fermer"),
        "it": ("Salva", "Annulla", "OK", "Chiudi"),
        "pt": ("Salvar", "Cancelar", "OK", "Fechar"),
    }
    assert set(expected) == set(available_languages()), (
        "jede angebotene Sprache braucht geprüfte Qt-Standardknöpfe"
    )
    standards = (
        QDialogButtonBox.StandardButton.Save,
        QDialogButtonBox.StandardButton.Cancel,
        QDialogButtonBox.StandardButton.Ok,
        QDialogButtonBox.StandardButton.Close,
    )

    # Absichtlich Deutsch vor Englisch: Qts englischer Katalog enthält nicht
    # jeden englischen Ausgangstext. Ein liegen gebliebener deutscher
    # Übersetzer machte den englischen Dialog deshalb zweisprachig.
    for language, labels in expected.items():
        translator = install_qt_translations(qt_app, language)  # type: ignore[arg-type]
        assert translator is not None, (
            f"PySide6 liefert qtbase_{language}.qm mit — Laden darf nicht scheitern"
        )
        selected = QDialogButtonBox.StandardButton.NoButton
        for standard in standards:
            selected |= standard
        box = QDialogButtonBox(selected)
        actual = tuple(box.button(standard).text().replace("&", "") for standard in standards)
        assert actual == labels

    ours = [
        translator
        for translator in qt_app.findChildren(QTranslator)  # type: ignore[attr-defined]
        if translator.objectName() == "solidon.qtbase.translator"
    ]
    assert len(ours) == 1, "beim Sprachwechsel darf nur der aktuelle Qt-Katalog bleiben"
    qt_app.removeTranslator(ours[0])  # type: ignore[attr-defined]


def test_every_used_qt_standard_button_is_covered_by_the_language_test() -> None:
    """Eine neue Qt-Knopfart braucht vor ihrem ersten Einsatz sechs geprüfte Texte."""
    pattern = re.compile(r"QDialogButtonBox\.StandardButton\.([A-Za-z]+)")
    used = {
        match
        for path in UI_DIR.rglob("*.py")
        for match in pattern.findall(path.read_text(encoding="utf-8"))
    }
    assert used == {"Save", "Cancel", "Ok", "Close"}


#: Ein Dateifilter für Qt: eine Beschriftung, dann die Endungen in Klammern.
FILE_FILTER = re.compile(r"^(?P<label>[^(]*)\(\s*\*\.")

#: Eine Beschriftung, die keine ist: ein Formatname wie „STL" oder „3MF".
#: Großbuchstaben, Ziffern, Punkt und Bindestrich — sonst nichts. So etwas
#: heißt in jeder Sprache gleich und braucht keine Übersetzung.
FORMAT_NAME = re.compile(r"^[A-Z0-9.\- ]*$")


class _Literals(ast.NodeVisitor):
    """Sammelt Zeichenketten, die **nicht** durch ``tr()`` oder ``_()`` gehen."""

    def __init__(self) -> None:
        self.depth = 0
        self.free: list[ast.Constant] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = ""
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        translated = name in {"tr", "_", "translate", "TranslatableText"}
        self.depth += int(translated)
        self.generic_visit(node)
        self.depth -= int(translated)

    def visit_Constant(self, node: ast.Constant) -> None:
        if not self.depth and isinstance(node.value, str):
            self.free.append(node)


def _file_filter_offenders(path: Path, tree: ast.AST) -> list[str]:
    """AGENTS.md Regel 20 gilt auch für Dateifilter — und für Konstanten.

    Die Prüfung der Anzeige-Aufrufe sieht nur deren Argumente.
    ``MODEL_FILTER = "Modelle (*.stl …)"`` stand daneben, auf
    Modulebene, und erschien deshalb auch in der englischen Oberfläche deutsch.
    Ein Filter ist ein Text wie jeder andere: alles vor der Klammer liest ein
    Mensch.

    Ein reiner Formatname („STL (*.stl)") bleibt draußen — er heißt überall so.
    """
    visitor = _Literals()
    visitor.visit(tree)

    offenders = []
    for node in visitor.free:
        match = FILE_FILTER.match(node.value)
        if match is None:
            continue
        label = match.group("label").strip()
        if FORMAT_NAME.match(label):
            continue
        offenders.append(f"{path.name}:{node.lineno} {node.value!r}")

    return offenders


def test_the_filter_check_would_catch_a_violation() -> None:
    """Ein Wächter für die Prüfung darüber: ein grüner Lauf soll etwas heißen."""
    assert FILE_FILTER.match("Modelle (*.stl *.3mf)")
    assert not FORMAT_NAME.match("Modelle")
    assert FORMAT_NAME.match("STL"), "ein Formatname bleibt draußen"
    assert FORMAT_NAME.match("3MF")
    assert FILE_FILTER.match("Bilder (*.png)")
    assert not FILE_FILTER.match("Ein Satz ohne Endung."), "kein Filter, kein Fund"


def surface_files() -> list[Path]:
    return sorted(UI_DIR.rglob("*.py"))


def _fixed_translated_colons(tree: ast.AST) -> set[int]:
    """Findet feste Doppelpunkte neben Übersetzungen und in Maßpräfixen.

    Ein dynamischer Titel oder Wert bleibt ein Platzhalter im vollständigen
    Rahmen. Die Prüfung verfolgt keine Variablen; dafür prüfen die Textfälle
    unten die wirklichen Ausgaben der gemeinsamen Beschriftungshelfer.
    """

    def translated(node: ast.AST) -> bool:
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            function = child.func
            if isinstance(function, ast.Name) and function.id in {"tr", "_", "TranslatableText"}:
                return True
            if isinstance(function, ast.Attribute) and function.attr in {"tr", "translate"}:
                return True
        return False

    def starts_with_colon(node: ast.AST) -> bool:
        if isinstance(node, ast.JoinedStr) and node.values:
            node = node.values[0]
        return (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and re.match(r"^\s*(?:</[^>]+>\s*)*:", node.value) is not None
        )

    def ends_with_colon(node: ast.AST) -> bool:
        while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            node = node.right
        if isinstance(node, ast.JoinedStr) and node.values:
            node = node.values[-1]
        return (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and re.search(r":\s*$", node.value) is not None
        )

    offenders: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr) and translated(node):
            if any(starts_with_colon(part) for part in node.values):
                offenders.add(node.lineno)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            # Auch davor: ``f"{x}: " + tr(…)`` — der Doppelpunkt steht vor dem
            # übersetzten Teil (Review RM-285, ``analysis.py``).
            if (translated(node.left) and starts_with_colon(node.right)) or (
                translated(node.right) and ends_with_colon(node.left)
            ):
                offenders.add(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "setPrefix"
            and node.args
        ):
            prefix = node.args[0]
            if (
                isinstance(prefix, ast.BinOp)
                and isinstance(prefix.op, ast.Add)
                and starts_with_colon(prefix.right)
            ) or (
                isinstance(prefix, ast.JoinedStr)
                and any(starts_with_colon(part) for part in prefix.values)
            ):
                offenders.add(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"format", "format_map"}
            and isinstance(node.func.value, ast.Constant)
            and isinstance(node.func.value.value, str)
            and re.search(r"}\s*(?:</[^>]+>\s*)*:", node.func.value.value)
            and any(
                translated(value) for value in (*node.args, *(kw.value for kw in node.keywords))
            )
        ):
            offenders.add(node.lineno)
    return offenders


@pytest.mark.parametrize(
    "source,expected",
    [
        ("f\"{tr('Wert')}: {value}\"", True),
        ("f\"{str(tr('Wert'))}: {value}\"", True),
        ("f\"{tr('Schritt')} {step}: {label}\"", True),
        ("f\"<b>{tr('Wert')}</b>: {value}\"", True),
        ("f\"{tr('Fehler') if error else tr('Warnung')}: {message}\"", True),
        ('tr("Wert") + ": " + value', True),
        ('_("Wert") + f": {value}"', True),
        ('"{}: {}".format(tr("Wert"), value)', True),
        ('"{name}: {value}".format_map({"name": tr("Wert"), "value": value})', True),
        ('tr("Sicherheitsproblem melden") + f": <a>{address}</a>"', True),
        ('field.setPrefix(reference_name + ": ")', True),
        ('f"{object_id}: " + tr("bessere Lage gefunden")', True),
        ('"Wert: " + _("Text")', True),
        ('tr("A") + f" {n}: " + tr("B")', True),
        ('f"{host}:" + str(port)', False),
        ('f"{object_id}: " + name', False),
        ('field.setPrefix(f"{reference_name}: ")', True),
        ('field.setPrefix(tr("{name}: {value}", name=reference_name, value=""))', False),
        ('tr("Wert: {value}", value=value)', False),
        ('tr("{name}: {value}", name=_("Wert"), value=value)', False),
        ('tr("Wert: {value}").format(value=value)', False),
        ('f"{object_id}:{feature_id}"', False),
        ('f"{host}:{port}"', False),
        ('"QComboBox::drop-down { width: 12px; }"', False),
        ("f\"{tr('Wert')} {value:.2f}\"", False),
    ],
)
def test_the_colon_guard_distinguishes_labels_from_internal_syntax(
    source: str, expected: bool
) -> None:
    """Gegenproben schützen echte Treffer, Platzhalter und technische Syntax."""
    assert bool(_fixed_translated_colons(ast.parse(source))) is expected


def test_translated_surface_labels_do_not_append_a_fixed_colon() -> None:
    """Auch die Interpunktion einer Beschriftung kommt aus ihrem Katalog."""
    paths = surface_files()
    assert paths, "die Oberflächenprüfung muss Quellen lesen"
    offenders = [
        f"{path.relative_to(PACKAGE_DIR)}:{line}"
        for path in paths
        for line in sorted(_fixed_translated_colons(ast.parse(path.read_text(encoding="utf-8"))))
    ]
    assert not offenders, "feste Doppelpunkte neben Übersetzungen:\n" + "\n".join(offenders)


@pytest.fixture
def display_language() -> Iterator[Callable[[str], None]]:
    """Stellt Katalog und Zahlenformat wie die Anwendung um und danach zurück.

    Die Anwendung setzt mit der Sprache auch ``QLocale.setDefault``
    (``install_qt_translations``); ohne das käme das Dezimaltrennzeichen vom
    Betriebssystem, und ein Test wäre auf einem deutschen Rechner grün und auf
    einem englischen rot.
    """
    from PySide6.QtCore import QLocale

    from app.i18n import get_language

    previous, previous_locale = get_language(), QLocale()

    def use(language: str) -> None:
        install_language(language)
        set_language(language)
        QLocale.setDefault(QLocale(language))

    try:
        yield use
    finally:
        set_language(previous)
        QLocale.setDefault(previous_locale)


@pytest.mark.parametrize("language", available_languages())
def test_dynamic_value_labels_keep_catalogue_punctuation_and_raw_paths(
    language: str,
    monkeypatch: pytest.MonkeyPatch,
    display_language: Callable[[str], None],
) -> None:
    """Sechs Sprachen behalten ihre Zahlen, Werte und eigene Zeichensetzung."""
    from app.ui import labels

    display_language(language)
    monkeypatch.setattr(app.i18n, "_DISPLAY_UNIT", "mm")
    separator = " : " if language == "fr" else ": "
    assert labels.value_line("diameter_mm", 12.5) == (
        labels.value_label("diameter_mm") + separator + labels.length(12.5)
    )
    path = "pieces/12.5_box.stl"
    assert labels.value_line("output_path", path) == "output_path" + separator + path
    decimal = "12.50" if language == "en" else "12,50"
    assert labels.length(12.5) == f"{decimal} mm", "Dezimaltrennzeichen der Sprache"
    if language == "fr":
        assert labels.value_line("diameter_mm", 12.5) == "Diamètre : 12,50 mm"


def test_french_history_labels_translate_colons_without_changing_names_or_values(
    monkeypatch: pytest.MonkeyPatch,
    display_language: Callable[[str], None],
) -> None:
    """Anlegen, Löschen, Werte und Grenzen nutzen denselben übersetzten Rahmen."""
    from app.core.types import DocumentChange, DocumentState, Parameter, Transaction
    from app.ui.panels import _changed_parameters

    display_language("fr")
    monkeypatch.setattr(app.i18n, "_DISPLAY_UNIT", "mm")
    old = Parameter("width", 12.5, title=TranslatableText("Breite"), minimum=3.0, maximum=20.0)
    new = Parameter("width", 14.5, title=old.title, maximum=22.5)
    added = Parameter("added", 5.0, title="Cale:12.5")
    removed = Parameter("removed", 2.0, title="Ancien:3.2")
    transaction = Transaction(
        id="test",
        title="test",
        ops=(),
        changes=DocumentChange(
            before=DocumentState(parameters={"width": old, "removed": removed}),
            after=DocumentState(parameters={"width": new, "added": added, "removed": None}),
        ),
    )
    assert _changed_parameters(transaction).splitlines() == [
        "Largeur : 12,50 mm → 14,50 mm",
        "Largeur · Borne inférieure : 3,00 mm → –",
        "Largeur · Borne supérieure : 20,00 mm → 22,50 mm",
        "Cale:12.5 : 5,00 mm",
        "Ancien:3.2 : 2,00 mm → –",
    ]


@pytest.mark.parametrize(
    "direction,expected",
    [
        ((-1.0, 0.0, 0.0), "Arête extérieure à gauche : "),
        ((0.0, -1.0, 0.0), "Arête extérieure avant : "),
    ],
)
def test_french_placement_prefix_uses_its_actual_resolved_reference_frame(
    direction: tuple[float, float, float], expected: str
) -> None:
    """Der echte Präfixaufruf trägt den Seitenbezug durch den Katalog (RM-516).

    Die Quelle bindet den Rahmen an den wirklichen setPrefix-Aufruf; die reine
    Textprüfung löst dessen Referenznamen auf, ohne eine Maßansicht aufzubauen.
    """
    from app.i18n import get_language, tr
    from app.ui.placement_flow import reference_names

    tree = ast.parse((UI_DIR / "placement_flow.py").read_text(encoding="utf-8"))
    frames = [
        node.args[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "setPrefix"
        and node.args
        and isinstance(node.args[0], ast.Call)
        and isinstance(node.args[0].func, ast.Name)
        and node.args[0].func.id == "tr"
        and any(
            keyword.arg == "name"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "reference_name"
            for keyword in node.args[0].keywords
        )
    ]
    assert len(frames) == 1
    frame = frames[0]
    assert len(frame.args) == 1 and isinstance(frame.args[0], ast.Constant)
    assert frame.args[0].value == "{name}: {value}"
    values = {keyword.arg: keyword.value for keyword in frame.keywords}
    assert set(values) == {"name", "value"}
    assert isinstance(values["value"], ast.Constant) and values["value"].value == ""

    previous = get_language()
    install_language("fr")
    set_language("fr")
    try:
        name = reference_names([("edge_3", "outer", direction, (0.0, 0.0, 0.0))])["edge_3"]
        assert tr(frame.args[0].value, name=name, value=values["value"].value) == expected
    finally:
        set_language(previous)


def test_french_measurement_warnings_and_advice_keep_complete_text_frames(
    monkeypatch: pytest.MonkeyPatch,
    display_language: Callable[[str], None],
) -> None:
    """Reale Texthelfer prüfen dynamische Titel ohne Fenster oder Arbeiter."""
    from types import SimpleNamespace

    from app.core.types import Finding, SettingAdvice
    from app.i18n import tr
    from app.ui.chat import _named, _warnings
    from app.ui.print_settings_dialog import PrintSettingsDialog, _TargetedAdvice
    from app.ui.section_bar import MeasureBar

    display_language("fr")
    monkeypatch.setattr(app.i18n, "_DISPLAY_UNIT", "mm")
    readouts: list[str] = []
    bar = SimpleNamespace(readout=SimpleNamespace(setText=readouts.append))
    MeasureBar.show_measurement(bar, "distance", 12.5, 3)
    assert readouts == ["Distance : 12,50 mm   (3)"]

    message = "Vérifier pieces/12.5_box.stl : entrée A."
    proposal = SimpleNamespace(
        findings=(
            Finding("test.warning", "warning", message),
            Finding("test.info", "info", "invisible"),
            Finding(
                "test.error",
                "error",
                TranslatableText("Objekt: {object_id}", values={"object_id": "cube:12.5"}),
            ),
        )
    )
    assert _warnings(proposal) == [
        "avertissement : " + message,
        "erreur : Objet : cube:12.5",
    ]
    assert _named([SimpleNamespace(op="cube:12.5")], tr("Operation")) == (
        str(tr("Operation")) + " : cube:12.5"
    )

    plain = SettingAdvice("layers.height", 0.2, 0.25, "test")
    advice = _TargetedAdvice(
        "layers.height", 0.2, 0.25, "test", parts=("12.5_A.stl", "cube:reference")
    )
    assert PrintSettingsDialog._advice_parts(advice) == (
        "S'applique à : 12.5_A.stl, cube:reference"
    )
    assert PrintSettingsDialog._advice_parts(plain) == ""
    assert (
        PrintSettingsDialog._advice_parts(_TargetedAdvice("layers.height", 0.2, 0.25, "test")) == ""
    )


@pytest.mark.parametrize("path", surface_files(), ids=lambda path: path.name)
def test_no_hard_wired_text_in_the_surface(path: Path) -> None:
    """Regel 20: Anzeigen und Dateifilter laufen über tr(), mit gemeinsamem AST."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = _file_filter_offenders(path, tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = ""
        owner = ""
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
            if isinstance(node.func.value, ast.Name):
                owner = node.func.value.id
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        is_box = name in BOX_CALLS and owner == "QMessageBox"
        if not is_box and name not in DISPLAY_CALLS and name not in LABELLED_WIDGETS:
            continue
        for argument in node.args:
            if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
                continue
            # Stilvorlagen und leere Zeichenketten sind keine Texte, die jemand liest.
            if argument.value.strip() and not argument.value.startswith(("#", "font", "QFrame")):
                offenders.append(f"{path.name}:{argument.lineno} {argument.value!r}")

    assert not offenders, "text that never reaches tr():\n" + "\n".join(offenders)


def test_a_new_catalogue_is_all_it_takes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """§4.1: Eine Sprache meldet sich über ihre Datei an, nicht über eine Liste.

    Der Nachweis, dass das Gerüst offen ist: ein Katalog im Verzeichnis, und
    die Sprache steht in der Auswahl. Vorher hing sie an ``SUPPORTED_LANGUAGES``
    im Quelltext, und daneben an vier weiteren Stellen, die man einzeln
    nachtragen musste.
    """
    from app.i18n import catalog as catalogue_module

    for language in ("en", "es"):
        (tmp_path / f"{language}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(catalogue_module, "LOCALES_DIR", tmp_path)

    assert catalogue_module.available_languages() == (SOURCE_LANGUAGE, "en", "es")


def test_an_unnamed_language_still_shows_up() -> None:
    """Ein Kürzel ohne Eintrag in ``LANGUAGE_NAMES`` verschwindet nicht — es
    steht als Kürzel da. Die Namensliste ist ein Wörterbuch, keine Anmeldung."""
    from app.i18n import language_name

    assert language_name("es") == "Español"
    assert language_name("xx") == "xx"


def test_the_manual_finds_a_place_for_a_new_language(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Sprachauswahl darf der Anwendung nicht davonlaufen: der
    Handbuchbauer kannte zwei Sprachen und brach bei der dritten ab.

    **Das `monkeypatch` ist kein Beiwerk.** Die Werkzeuge unter ``tools/``
    setzen `QT_QPA_PLATFORM` zurück, weil sie eine echte Plattform brauchen —
    und bis zu dieser Sitzung taten sie es beim *Import*. Dieser Test führt
    genau diesen Import aus, also galt die Änderung danach für den ganzen
    Prozess: `viewport._available()` sah keine Offscreen-Plattform mehr und
    baute in jedem späteren Fenster einen echten Renderer — damals VTKs
    Interactor ohne OpenGL-Kontext, und das nahm den Prozess mit.

    Das war beide Abstürze, die dieses Repository als „A" und „B" führte, und
    dass sie zu wandern schienen, lag an der zufälligen Dateireihenfolge:
    lief diese Datei vor `test_ui.py`, starb der Fensteraufbau dort; lief sie
    vor `test_sketch_editor.py`, starb er da. Der Import selbst ist harmlos
    geworden (`main()` setzt jetzt zurück, nicht das Modul), aber ein Test,
    der fremden Modulcode ausführt, gibt die Umgebung von sich aus zurück —
    das nächste Werkzeug hat vielleicht wieder eine Zeile davon.
    """
    import importlib.util

    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))

    spec = importlib.util.spec_from_file_location(
        "make_manual", Path(app.__file__).parent.parent / "tools" / "make_manual.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.page_for("de") == ("handbuch.html", "handbuch/de")
    assert module.page_for("es") == ("es/manual.html", "../handbuch/es")


#: Auswahlwerte, die ihr eigener Name sind: Normteilgrößen (M4), Maße (6x3),
#: Einheiten, Achsen und der eine Eigenname unter den Gitterstrukturen. Sie
#: heißen in jeder Sprache gleich.
SELF_NAMING = re.compile(r"^(M\d+(\.\d+)?|\d+x\d+|mm|cm|in|m|x|y|z|gyroid)$")


def self_naming_sizes() -> frozenset[str]:
    """Dasselbe, aber aus der Normteiltabelle statt aus einem Muster.

    Ein Aluprofil heißt „2020", und zwar in jeder Sprache: Das ist sein
    Querschnitt in Millimetern, zweimal hingeschrieben. Aus der Tabelle geholt
    und nicht als ``\\d{4}`` ans Muster gehängt — dieses Muster ließe auch
    Lagerbezeichnungen wie „6800" durch, ohne dass jemand das entschieden hat,
    und eine neue Profilgröße ist hier von selbst dabei.

    Dasselbe gilt für die Rohrreihe der Rohrschelle (RM-398): „22" ist der
    Außendurchmesser in Millimetern und die Handelsbezeichnung des Rohrs —
    in jeder Sprache dieselbe Zahl.
    """
    from app.core.knowledge import standards

    return frozenset(standards.profile_sizes()) | frozenset(standards.pipe_sizes())


def self_naming_fonts() -> frozenset[str]:
    """Die Schriftnamen, und zwar aus der Liste, die der Dialog anbietet.

    **Schriftnamen sind Marken und keine Wörter.** „Liberation Sans" heißt auf
    Französisch nicht „Libération Sans" — der Name steht so in der
    Schriftdatei, und wer ihn übersetzte, machte aus einer Auswahl eine
    Behauptung über eine Schrift, die es nicht gibt. Die **Schnitte** daneben
    (Normal, Fett, Kursiv) sind das Gegenteil: gewöhnliche Wörter, die jede
    Sprache selbst hat, und die stehen deshalb in ``_CHOICE_NAMES``.

    Aus ``FONTS`` geholt und nicht als ``DejaVu .*|Liberation .*`` ins Muster
    geschrieben — dieselbe Entscheidung wie bei den Profilgrößen darüber, und
    hier ist sie am 10.09.2026 einmal fällig geworden: Zwei neue Familien
    machten diesen Test rot, weil die Liste an zwei Stellen gepflegt war und
    nur eine nachzog. Eine siebte Schrift ist hier von selbst dabei.
    """
    from app.core.geom.label_ops import FONTS

    return frozenset(FONTS)


def test_every_choice_has_a_name_someone_can_read() -> None:
    """Regel 20 gilt auch für Auswahlwerte.

    Gefunden im laufenden Fenster, nicht in der Suite: im Texturdialog stand
    „Art: raised" und „Auflegen: flat", und dieselbe Sorte Wert steckte über
    das ganze Register verteilt sechsundzwanzigmal. Ein Schlüssel ist kein
    Text, den jemand liest — auch dann nicht, wenn er zufällig ein englisches
    Wort ist.

    **Und geprüft war nur die eine Hälfte.** Auswahlwerte stehen an zwei
    Stellen: im Parameterschema der Operationen und in den sechsundfünfzig
    Feldern der Druckeinstellungen (``print_settings_dialog.FIELDS``). Die
    zweite lief hier vorbei, und im deutschen Fenster stand deshalb „Naht:
    aligned", „Wandbahnen: arachne", „Plattenhaftung: brim" — im Füllmuster
    sogar englische Schlüssel **neben** deutschen Namen (grid, lines,
    triangles, Wabe, Würfelgitter). Sechzehn Werte, in dem Dialog, den jeder
    vor dem Drucken öffnet.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.ui.labels import choice_label
    from app.ui.print_settings_dialog import FIELDS

    load_operations()
    by_itself = self_naming_sizes() | self_naming_fonts()

    def named(value: str) -> bool:
        return bool(SELF_NAMING.match(value)) or value in by_itself or choice_label(value) != value

    offenders = []
    for spec in REGISTRY.all():
        for entry in spec.params.spec():
            for choice in entry.choices or ():
                value = str(choice)
                if not named(value):
                    offenders.append(f"{spec.name}.{entry.name}: {value!r}")
    for field in FIELDS:
        for choice in field.choices or ():
            value = str(choice)
            if not named(value):
                offenders.append(f"Druckeinstellungen {field.path}: {value!r}")

    assert not offenders, "choice values shown as keys:\n" + "\n".join(sorted(offenders))


def test_every_named_choice_also_says_what_it_does() -> None:
    """Der Satz zum Namen — vollständig oder gar nicht.

    ``_CHOICE_NAMES`` benennt einen Auswahlwert, ``_CHOICE_NOTES`` daneben
    sagt, was er bewirkt (Tooltip und Bildschirmleser, über
    ``explain_choices``). Fünfzehn erklärte Werte von siebenundsechzig wären
    schlimmer als keine — dann lernt niemand, dass es die Sätze gibt; dieselbe
    Regel wie bei den ``note``-Sätzen der Druckeinstellungen.

    Beide Richtungen, wie beim Katalogabgleich: Ein Name ohne Satz ist die
    Lücke, ein Satz ohne Name ist tot — ``choice_note`` wird nur erreicht, wo
    ``choice_label`` den Wert kennt, und ein verwaister Satz überlebte sonst
    jede Umbenennung. Selbstnamen (M4, mm, z) stehen absichtlich in keiner
    der beiden Tabellen.
    """
    from app.ui.labels import _CHOICE_NAMES, _CHOICE_NOTES

    unexplained = set(_CHOICE_NAMES) - set(_CHOICE_NOTES)
    orphaned = set(_CHOICE_NOTES) - set(_CHOICE_NAMES)
    assert not unexplained, "named choices without a note: " + ", ".join(sorted(unexplained))
    assert not orphaned, "notes for unnamed choices: " + ", ".join(sorted(orphaned))


#: Ab wie vielen gemeinsamen Anfangsbuchstaben zwei Katalogruppen einer Sprache
#: als derselbe Name gelten. Gefunden am französischen Paar
#: „Fixations" (Verbindungen) und „Fixation" (Befestigung): ein Buchstabe
#: Unterschied, und im Katalog stehen sie untereinander. Portugiesisch hatte
#: dasselbe mit „Fixações" gegen „Fixação" — von einem Abstandsmaß über die
#: ganzen Wörter unbemerkt, weil drei Zeichen dazwischen liegen. Was die zwei
#: Fälle verbindet, ist nicht der Abstand, sondern der gemeinsame Wortstamm,
#: und den sieht man am Anfang.
GROUP_STEM = 5


def _stem(text: str) -> str:
    """Der Wortanfang ohne Akzente und Kleinschreibung — soweit er zählt."""
    stripped = unicodedata.normalize("NFKD", text.casefold())
    letters = "".join(sign for sign in stripped if not unicodedata.combining(sign))
    return letters[:GROUP_STEM]


@pytest.mark.parametrize("language", list(available_languages()))
def test_two_catalogue_groups_never_read_almost_the_same(language: str) -> None:
    """Sieben Gruppen ordnen den Bausteinkatalog (§24.3), und sie ordnen nur,
    solange der Nutzer sie auseinanderhalten kann.

    Geprüft wird der Wortstamm, nicht die Gleichheit: Zwei verschiedene
    Zeichenketten sind noch kein Unterschied, den jemand im Vorbeigehen sieht.
    """
    install_language(language)
    names = {key: title.translate(language) for key, title in GROUPS.items()}
    assert language == SOURCE_LANGUAGE or names != {
        key: title.msgid for key, title in GROUPS.items()
    }, f"{language}: nothing was translated — the test would be measuring German"

    seen: dict[str, str] = {}
    clashes = []
    for key, name in sorted(names.items()):
        stem = _stem(name)
        if stem in seen:
            clashes.append(f"{seen[stem]} / {key}: {names[seen[stem]]!r} vs {name!r}")
        else:
            seen[stem] = key

    assert not clashes, f"{language}: catalogue groups too alike\n" + "\n".join(clashes)


@pytest.mark.parametrize(
    "language", [entry for entry in available_languages() if entry != SOURCE_LANGUAGE]
)
def test_translated_manual_pages_keep_their_paragraph_structure(language: str) -> None:
    """Eine übersetzte Handbuchseite hat die Absatzstruktur ihrer Quelle.

    Die Falle dahinter ist am 30.08.2026 zugeschnappt: Beim Tauschen eines
    geänderten Absatzes traf ein positionsbasiertes Skript in fünf Sprachen
    den falschen — der GLB-Absatz war überschrieben, der alte Slicer-Absatz
    stand doppelt neben dem neuen, und kein Test sah es. Gefunden hat es die
    Lektüre der Freigabe, nicht die Suite.

    Geprüft wird die Struktur, nicht die Wortstellung: gleiche Absatzzahl,
    Abbildungen an denselben Positionen mit derselben Kennung, und kein
    fetter Absatzkopf doppelt. Wo ein Kopf im Satz wandern darf („Bewährt
    hat sich **qwen3:14b**" gegen „**qwen3:14b** has proven itself"), bleibt
    das erlaubt — genau dieser Fall war der Fehlalarm der ersten Sonde.
    """
    from app.core import manual

    catalog = read_catalog(language)
    troubles: list[str] = []
    for page in manual.INTRODUCTION:
        source = str(page.body)
        translated = catalog.get(source)
        if not translated:
            # Fehlende Übersetzungen meldet ``test_every_text_is_translated``.
            continue
        source_parts = source.split("\n\n")
        translated_parts = translated.split("\n\n")
        if len(source_parts) != len(translated_parts):
            troubles.append(
                f"{page.key}: {len(translated_parts)} Absätze statt {len(source_parts)}"
            )
            continue
        for index, (original, other) in enumerate(zip(source_parts, translated_parts, strict=True)):
            original_figure = original.strip().startswith("![](")
            other_figure = other.strip().startswith("![](")
            if original_figure != other_figure:
                troubles.append(f"{page.key}[{index}]: Abbildung an falscher Position")
            elif original_figure and original.strip() != other.strip():
                troubles.append(f"{page.key}[{index}]: andere Abbildung")
        heads = [
            part.split("**")[1]
            for part in translated_parts
            if part.startswith("**") and part.count("**") >= 2
        ]
        doubled = sorted({head for head in heads if heads.count(head) > 1})
        if doubled:
            troubles.append(f"{page.key}: doppelte Absatzköpfe {doubled}")

    assert not troubles, f"{language}: Absatzstruktur weicht von der Quelle ab\n" + "\n".join(
        troubles
    )


#: Deutsche Stämme, die als **Platzhaltername** nicht vorkommen dürfen.
#:
#: Platzhalter sind Schlüssel, und Schlüssel sind laut ``AGENTS.md`` englisch —
#: anders als der Text drumherum, dessen Quelle deutsch ist. Am 30.08.2026
#: standen hier 22 deutsche Namen in 38 Quelltexten, sieben davon neben ihrem
#: englischen Zwilling im selben Katalog: ``{adresse}`` siebenmal neben
#: ``{address}`` viermal, ``{anzahl}`` und ``{zahl}`` neben ``{count}``. Ein
#: Satz trug beide Sorten zugleich — „Platte {nummer} von {anzahl}".
#:
#: **Kuratiert wie ``GERMAN_STEMS``, nicht erraten.** Der automatische Weg
#: scheitert an der Überlappung technischer Wörter; wer ein deutsches Wort in
#: einem Platzhalter findet, trägt es hier ein.
GERMAN_PLACEHOLDERS = frozenset(
    {
        "adresse",
        "anzahl",
        "begriff",
        "beispiel",
        "datei",
        "etappen",
        "grund",
        "gruppe",
        "maß",
        "minuten",
        "nummer",
        "ordner",
        "ort",
        "platz",
        "profil",
        "quelle",
        "sekunden",
        "striche",
        "stufe",
        "titel",
        "weg",
        "zahl",
    }
)


def test_no_placeholder_name_speaks_german() -> None:
    """Ein Platzhaltername ist ein Schlüssel und darf deshalb nicht deutsch sein.

    Der Text um ihn herum ist es sehr wohl — die Quelle dieser Anwendung ist
    Deutsch. Der Name in der Klammer aber ist ein Bezeichner: Er steht
    unverändert in jeder der fünf Übersetzungen und im ``format()``-Aufruf
    daneben. ``{anzahl}`` im französischen Katalog ist so wenig Französisch
    wie Deutsch.

    **Die Liste ist die Messgrenze, nicht der Bestand** — deshalb steht
    unten die Zusicherung über die Zahl der überhaupt gefundenen Namen. Beim
    Aufstellen dieser Prüfung meldete eine kuratierte Wortliste 13 Verstöße;
    erst das Auflisten *aller* 81 Namen zeigte neun weitere (``etappen``,
    ``gruppe``, ``minuten``, ``ordner``, ``sekunden``, ``striche``, ``stufe``,
    ``titel``, ``weg``). Wer diesen Test erweitert, lässt sich die
    Vollauflistung ausgeben und liest sie, statt der Liste zu glauben.
    """
    catalog = read_catalog("en")
    names = {name for key in catalog for name in PLACEHOLDER.findall(key)}
    assert len(names) > 50, (
        f"nur {len(names)} Platzhalternamen im Katalog — die Grundmenge ist leer "
        "oder das Muster trifft nicht mehr"
    )

    offenders = sorted(names & GERMAN_PLACEHOLDERS)
    assert not offenders, (
        f"Deutsche Platzhalternamen: {offenders}. Ein Platzhalter ist ein Schlüssel "
        f"und bleibt englisch. Alle {len(names)} vorhandenen Namen: {sorted(names)}"
    )


#: Ersatzschreibungen, die in einem deutschen Oberflächentext nichts zu suchen
#: haben — gesucht als **ganzes Wort**, damit kein englisches Wort mit `ss`
#: oder `ue` darin fällt.
#:
#: Die Liste ist kuratiert wie ``GERMAN_STEMS``, und aus demselben Grund: Eine
#: Regel „jedes `ae` ist verdächtig" träfe `Fläche` nicht und `value` schon.
#: Wer eine neue Ersatzschreibung findet, trägt sie hier ein.
ASCII_STATT_UMLAUT = {
    "liess": "ließ",
    "liessen": "ließen",
    "waehlen": "wählen",
    "waehle": "wähle",
    "groesse": "Größe",
    "groessen": "Größen",
    "fuer": "für",
    "koennen": "können",
    "koennte": "könnte",
    "muessen": "müssen",
    "muss": None,  # richtig geschrieben, steht hier als Merkposten
    "oeffnen": "öffnen",
    "schliessen": "schließen",
    "loeschen": "löschen",
    "aendern": "ändern",
    "hoehe": "Höhe",
    "laenge": "Länge",
    "staerke": "Stärke",
    "groesser": "größer",
    "spaeter": "später",
    "zurueck": "zurück",
    "ueber": "über",
    "haelt": "hält",
    "faellt": "fällt",
    "waere": "wäre",
    # Die Beugungen gehören dazu: Eine Liste, die „gross" kennt und „grosses"
    # nicht, lässt genau den Fall durch, der im Fließtext häufiger ist.
    "gross": "groß",
    "grosse": "große",
    "grosses": "großes",
    "grossen": "großen",
    "grosser": "großer",
    "grossem": "großem",
    "heisst": "heißt",
    "weiss": "weiß",
    "strasse": "Straße",
    "massnahme": "Maßnahme",
}


def _assert_source_text_uses_umlauts(ids: set[str]) -> None:
    """Ein deutscher Quelltext ist hier nicht nur Text, sondern die **Kennung**.

    Deshalb ist ein `ss` statt `ß` hier teurer als anderswo. Er wird zur
    Message-ID, sobald jemand ihn übersetzt — und die Berichtigung danach
    kostet fünf Kataloge, weil der berichtigte Satz ein **anderer Schlüssel**
    ist und alle Übersetzungen daran hängen bleiben.

    Bei einem Bezeichner schlägt ``test_language_rules`` an; bei einem
    Oberflächentext prüfte bisher nichts. Am 31.08.2026 sind an einem Abend
    vier Fälle aufgelaufen — drei Commit-Meldungen und zwei Texte
    („Die Datei liess sich dort nicht anlegen. Waehlen Sie einen anderen
    Ordner."), alle über ein Bash-Heredoc geschrieben und alle vorsorglich in
    ASCII. Der Weg überträgt Umlaute gemessen sauber; die Vorsicht war
    unbegründet und teuer.

    Gesucht wird als **ganzes Wort** und gegen eine kuratierte Liste, nicht
    nach dem Muster „irgendwo steht `ae`". Sonst fiele jedes englische Wort mit
    `ss` und jede Zeichenkette mit `ue` darin.
    """
    import re as _re

    assert ids, "keine Oberflächentexte gefunden — dann prüft dieser Test nichts"

    muster = _re.compile(
        r"(?<![\wäöüßÄÖÜ])(" + "|".join(sorted(ASCII_STATT_UMLAUT)) + r")(?![\wäöüßÄÖÜ])",
        _re.IGNORECASE,
    )
    treffer: dict[str, list[str]] = {}
    for text in ids:
        gefunden = {wort.lower() for wort in muster.findall(text)}
        gefunden -= {wort for wort in gefunden if ASCII_STATT_UMLAUT[wort] is None}
        if gefunden:
            treffer[text[:70]] = sorted(gefunden)

    assert not treffer, (
        "Ersatzschreibung statt Umlaut in einem Oberflächentext. Das ist die "
        "Message-ID: Wer sie später berichtigt, macht alle fünf Übersetzungen "
        f"tot. {treffer}"
    )


@pytest.mark.parametrize("language", ["en", "es", "fr", "it", "pt"])
def test_context_keywords_reach_the_runtime_catalog(language: str) -> None:
    from app.i18n import _, tr

    install_language(language)
    expected = read_catalog(language)["Druckgeschwindigkeit\x04Oberfläche"]
    text = _("Oberfläche", context="Druckgeschwindigkeit")
    assert text.context == "Druckgeschwindigkeit"
    assert text.values is None
    assert text.translate(language) == expected
    assert _("Oberfläche", "Druckgeschwindigkeit").translate(language) == expected
    set_language(language)
    try:
        assert tr("Oberfläche", context="Druckgeschwindigkeit") == expected
        assert tr("Oberfläche", "Druckgeschwindigkeit") == expected
        assert tr("Feld {msgid}", msgid="Wert") == "Feld Wert"
        assert str(_("Slot {number}", number=3)).endswith("3")
    finally:
        set_language(SOURCE_LANGUAGE)


#: Werkzeuge der Zeile, die eine Operation auslösen, dürfen wie sie heißen.
#: *Bewegen* legt Schritte *Verschieben* an — zwei deutsche Wörter für einen
#: Handgriff, in den anderen Sprachen eines.
TOOL_IS_ITS_OPERATION = frozenset({("Bewegen", "Verschieben")})


def _first_word_stem(text: str) -> str:
    """Der Aktionsanfang bleibt auch vor einer Ergänzung vergleichbar."""
    return _stem(text.split(maxsplit=1)[0])


def _toolbar_names() -> list[str]:
    """Die Namen der Werkzeugzeile, gelesen an ``self.tools.add(…, tr("…"))``."""
    tree = ast.parse((UI_DIR / "main_window.py").read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "tools"
            and len(node.args) > 1
        ):
            continue
        label = node.args[1]
        if (
            isinstance(label, ast.Call)
            and label.args
            and isinstance(label.args[0], ast.Constant)
            and isinstance(label.args[0].value, str)
        ):
            names.append(label.args[0].value)
    return names


@pytest.mark.parametrize(
    "language", [entry for entry in available_languages() if entry != SOURCE_LANGUAGE]
)
def test_no_tool_or_operation_shares_its_name_with_another(language: str) -> None:
    """Zwei Dinge unter einem Namen sucht der Kunde am falschen Ort.

    Gemessen in der Durchsicht 0.5.1: Das Werkzeug *Trennen* (eine gezogene
    Linie) und die Operation *Teilen* (eine eingetippte Ebene) hießen en, es,
    fr und pt gleich — „Split“, „Separar“, „Séparer“ —, it „Dividi“ gegen
    „Dividere“, dasselbe Verb. Seit RM-507 sagen alle Wege „teilen“: das
    Werkzeug *Teilen*, die Operation *An Ebene teilen*. Verglichen werden ganze
    Namen und bei Einwortnamen der Wortstamm (:data:`GROUP_STEM`), wie bei den
    Kataloggruppen. *Teilen* und *Abschneiden* vergleichen außerdem das
    erste Verb: Eine Ergänzung wie „away“ macht daraus keine andere Aktion.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY

    load_operations()
    catalog = read_catalog(language)
    tools = _toolbar_names()
    titles = sorted({spec.title.msgid for spec in REGISTRY.all()})
    assert "Teilen" in tools and len(tools) >= 5, f"Werkzeugzeile nicht gelesen: {tools}"
    assert len(titles) > 100, f"nur {len(titles)} Operationstitel — dann prüft das nichts"

    def said(text: str) -> str:
        return catalog.get(text) or text

    clashes = []
    seen: dict[str, str] = {}
    for title in titles:
        name = said(title)
        if name in seen:
            clashes.append(f"{seen[name]!r} und {title!r} heißen beide {name!r}")
        seen[name] = title
    for tool in tools:
        for title in titles:
            if title == tool or (tool, title) in TOOL_IS_ITS_OPERATION:
                continue
            a, b = said(tool), said(title)
            one_word = " " not in a and " " not in b
            separate_cutting_actions = (tool, title) == ("Teilen", "Abschneiden")
            if a == b or (
                (one_word or separate_cutting_actions)
                and _first_word_stem(a) == _first_word_stem(b)
            ):
                clashes.append(f"Werkzeug {tool!r} ({a!r}) und Operation {title!r} ({b!r})")
    assert not clashes, f"{language}: gleiche Namen\n" + "\n".join(clashes)


#: Handbuchseiten, die fr noch „Esc“ schreiben. Die Seiten gehören der
#: Handbuch-Sitzung; ist eine nachgezogen, fliegt sie hier heraus.
FRENCH_ESC_ON_MANUAL_PAGES: tuple[str, ...] = ()


def test_french_names_the_escape_key_as_its_keyboard_does() -> None:
    """Französische Tastaturen beschriften die Taste „Échap“.

    Durchsicht 0.5.1: 15-mal „Échap“ gegen 7-mal „Esc“, zum Teil im selben
    Fenster. Entscheidung der Release-Sitzung: „Échap“ überall
    (``.claude/rules/uebersetzung.md``, Tastennamen).
    """
    catalog = read_catalog("fr")
    escape_keys = [key for key in catalog if re.search(r"\bEsc(?:ape)?\b", key)]
    assert escape_keys, "fr: keine Quelltexte zur Escape-Taste — sonst prüft dieser Test nichts"

    found = sorted(key for key, value in catalog.items() if re.search(r"\bEsc\b", value))
    unexpected = [key for key in found if not key.startswith(FRENCH_ESC_ON_MANUAL_PAGES)]
    assert not unexpected, "fr sagt „Esc“ statt „Échap“:\n" + "\n".join(unexpected)
    stale = [
        start for start in FRENCH_ESC_ON_MANUAL_PAGES if not any(k.startswith(start) for k in found)
    ]
    assert not stale, f"nachgezogen — aus FRENCH_ESC_ON_MANUAL_PAGES austragen: {stale}"


#: Woran man die Anrede „voi“ erkennt: Pronomen, Hilfsverben und die
#: Imperative, mit denen Befunde und Hinweise einen Satz beginnen. Kuratiert
#: wie ``GERMAN_STEMS`` — ein Partizip im Plural („facce selezionate“) sieht
#: aus wie ein Imperativ, deshalb nur am Satzanfang.
ITALIAN_VOI = re.compile(
    r"\b(voi|vostr[oaie]|avete|potete|potrete|dovete|volete|avevate)\b"
    r"|(?:^|[.!?:;—]\s+)(Selezionate|Scegliete|Modificate|Aumentate|Riducete|Spostate|"
    r"Ruotate|Verificate|Inserite|Annullate|Trascinate|Disegnate|Convertite|Liberate|"
    r"Assegnate|Associate|Inseritela|Annullatelo|Aumentatene|Modificateli)\b",
    re.MULTILINE,
)

#: Dasselbe für die Höflichkeitsform „Lei“. Die Imperative von -are-Verben
#: („Incolli“, „Configuri“) sind zugleich Du-Indikative; sie zählen nur am
#: Satzanfang und großgeschrieben — ohne IGNORECASE, sonst träfe „controlli“
#: jedes Substantiv —, oder mit vorangestelltem Pronomen („Lo selezioni“).
_LEI_FORMS = [
    "Scelga",
    "Verifichi",
    "Modifichi",
    "Riprovi",
    "Inserisca",
    "Sposti",
    "Aumenti",
    "Riduca",
    "Trascini",
    "Imposti",
    "Salvi",
    "Chiuda",
    "Metta",
    "Apra",
    "Attenda",
    "Riavvii",
    "Indichi",
    "Allunghi",
    "Incolli",
    "Allinei",
    "Configuri",
    "Reinstalli",
    "Renda",
    "Ridisegni",
    "Rimuova",
    "Aggiunga",
    "Aggiungale",
    "Parli",
    "Consegni",
    "Assegni",
    "Clicchi",
    "Scriva",
    "Rivolga",
    "Tolga",
    "Lasci",
]
#: Lei-Formen, die zugleich Substantive im Plural sind („Selezioni salvate“,
#: „Disegni e schizzi“, „Raccordi e smussi“, „Usi tipici“, „Controlli“,
#: „Termini“, „Ripari“, „Spunti“, „Copi“): Sie zählen nur mit einem Objekt
#: dahinter („Selezioni il contorno“, „Raccordi di nuovo“).
_LEI_OR_NOUN = [
    "Selezioni",
    "Disegni",
    "Raccordi",
    "Spunti",
    "Usi",
    "Copi",
    "Controlli",
    "Termini",
    "Ripari",
]
_OBJECT = (
    r"(?=\s+(?:il|lo|la|l'|i|gli|le|un|una|uno|di nuovo|nuovamente|questo|questa|quello|"
    r"quella|altre|altri|esattamente|prima|invece)\b)"
)
ITALIAN_LEI = re.compile(
    r"(?:^|[.!?:;—]\s+)(?:"
    r"(?:" + "|".join(_LEI_FORMS) + r")\b"
    r"|(?:"
    + "|".join(_LEI_OR_NOUN)
    + r")\b"
    + _OBJECT
    + r"|(?:Lo|La|Li|Ne)\s+(?:"
    + "|".join(word.lower() for word in (*_LEI_FORMS, *_LEI_OR_NOUN))
    + r")\b"
    r"|Faccia(?: di nuovo)? clic\b)",
    re.MULTILINE,
)
#: Nach einer Konjunktion nur Lei-Formen, die nie ein Du-Indikativ sind (-a statt -i),
#: und Wendungen, die es in keiner anderen Person gibt — „faccia clic“ ist nie ein
#: Substantiv, auch klein nach einem Strich.
ITALIAN_LEI_INSIDE = re.compile(
    r"\b(?:oppure|o|poi|e|quindi)\s+(?:(?:lo|la|li|ne|mi)\s+)?(?:scelga|inserisca|riduca|"
    r"chiuda|metta|apra|attenda|rimuova|aggiunga|scriva|rivolga|tolga|renda)\b"
    r"|\b(?:si rivolga|può rivolgersi|mi scriva|lo apra|la apra|ne clicchi)\b"
    r"|\bfaccia(?: di nuovo)? clic\b"
    # Klein nach Doppelpunkt, Semikolon oder Strich: dieselben eindeutigen
    # Formen, und die mehrdeutigen nur mit Objekt („: raccordi invece di nuovo“).
    r"|[:;—]\s+(?:scelga|inserisca|riduca|chiuda|metta|apra|attenda|rimuova|aggiunga|"
    r"scriva|rivolga|tolga|renda)\b"
    r"|[:;—]\s+(?:" + "|".join(word.lower() for word in _LEI_OR_NOUN) + r")\b" + _OBJECT
)
# Ein Lei-Indikativ im Nebensatz ist ohne Pronomen nicht vom Modell als
# Satzgegenstand unterscheidbar. Er zählt nur bei belegter Kundenanrede.
GERMAN_CUSTOMER_CLAUSE = re.compile(r"\b(?:bis|wenn|solange|sobald|bevor|nachdem) Sie\b")
ITALIAN_LEI_CUSTOMER_CLAUSE = re.compile(r"\b(?:finché|quando|se|mentre)\s+(?:non\s+)?modifica\b")
#: Wo die Quelle „Ihr“ oder „Sie“ als Anrede sagt, darf it nicht „sua“, „può“
#: oder „lei“ sagen — außer der Satz enthält die Du-Form. „Ihr“ nach einem
#: Satzzeichen ist oft „ihr“ am Satzanfang und zählt nicht; „si può“ ist
#: unpersönlich.
GERMAN_YOUR = re.compile(
    r"^Ihr(?:e|en|em|er|es)?\b|(?<![.!?:;]\s)\bIhr(?:e|en|em|er|es)?\b|\bIhnen\b"
)
GERMAN_YOU = re.compile(
    r"\b(?:können|könnten|sehen|haben|möchten|wollen) Sie\b|\bSie (?:können|haben|möchten|sehen)\b"
    r"|\bfür Sie\b|\bwie Sie\b"
)
ITALIAN_FORMAL = re.compile(r"\b(?:sua|suo|sue|suoi|lei)\b", re.IGNORECASE)
ITALIAN_FORMAL_VERB = re.compile(r"(?<!\bsi )(?<!\bSi )\b(?:può|Può)\b|\b(?:lei|Lei)\b")
ITALIAN_TU = re.compile(r"\b(?:tuo|tua|tuoi|tue|ti|te|tu)\b", re.IGNORECASE)


def _italian_formal(key: str, value: str) -> str | None:
    """Warum ein it-Eintrag „Lei“ oder „voi“ spricht — oder ``None``."""
    for pattern in (ITALIAN_VOI, ITALIAN_LEI, ITALIAN_LEI_INSIDE):
        match = pattern.search(value)
        if match:
            return match.group(0).strip()
    if GERMAN_CUSTOMER_CLAUSE.search(key):
        match = ITALIAN_LEI_CUSTOMER_CLAUSE.search(value)
        if match:
            return match.group(0).strip()
    if not ITALIAN_TU.search(value):
        if GERMAN_YOUR.search(key) and ITALIAN_FORMAL.search(value):
            return "sua/suo/lei für „Ihr“"
        if GERMAN_YOU.search(key) and ITALIAN_FORMAL_VERB.search(value):
            return "può/lei für „Sie“"
    return None


def _manual_only() -> set[str]:
    """Texte, die nur auf Handbuchseiten und in Anleitungen stehen — die gehören
    der Handbuch-Sitzung und ziehen dort nach."""
    return message_ids(
        [
            PACKAGE_DIR / "core" / "manual.py",
            PACKAGE_DIR / "core" / "guides.py",
            PACKAGE_DIR.parent / "tools" / "make_guides.py",
        ]
    ) - message_ids(
        [
            path
            for path in sorted(PACKAGE_DIR.rglob("*.py"))
            if path.name not in {"manual.py", "guides.py"}
        ]
    )


@pytest.mark.parametrize(
    ("text", "formal"),
    [
        # Pluralsubstantive nach einem Satzzeichen — kein „Lei“.
        ("Selezioni salvate: 3.", False),
        ("Disegni e schizzi restano nel passaggio.", False),
        ("Raccordi e smussi: tutti conservati.", False),
        ("Usi tipici: supporti.", False),
        ("Nota: controlli e verifiche.", False),
        ("Controlla il profilo della stampante.", False),
        ("Seleziona di nuovo lo spigolo.", False),
        # Die Lei-Formen schlagen weiter an.
        ("Selezioni il contorno.", True),
        ("Raccordi invece di nuovo.", True),
        ("Il raccordo non si riconduce: raccordi invece di nuovo.", True),
        ("Lo selezioni nella vista.", True),
        ("Incolli la chiave dall'e-mail.", True),
        ("Di solito è superato — faccia di nuovo clic sulla faccia.", True),
        ("Parli di Solidon, oppure mi scriva.", True),
    ],
)
def test_the_italian_formal_check_tells_nouns_from_imperatives(text: str, formal: bool) -> None:
    """Der Wächter unten trifft „Lei“, nicht gleich geschriebene Substantive.

    Sprachreview 0.5.1: Mit ``re.IGNORECASE`` hätte der erste Satz „Selezioni
    salvate …“ oder „Raccordi e smussi …“ die Suite rot gemacht.
    """
    assert (_italian_formal("Beliebig.", text) is not None) is formal, text


def test_italian_says_tu_outside_the_manual() -> None:
    """Italienisch spricht den Kunden mit „tu“ an (Imperativ der 2. Person).

    Entschieden am 27.09.2026 nach Kundensicht: 429 Einträge mit „tu“ gegen 31
    mit „voi“, daneben rund hundert mit „Lei“. Das Sprachreview fand danach
    37 weitere Lei-Stellen mitten im Satz („oppure mi scriva“), mit Pronomen
    („Faccia di nuovo clic“) und als „sua“/„può“ für „Ihr“/„Sie“; die prüft
    :func:`_italian_formal` mit. Die Handbuchseiten und Anleitungen stellt die
    Handbuch-Sitzung um; sie sind hier ausgenommen, solange sie nur dort
    stehen.
    """
    manual_only = _manual_only()
    catalog = read_catalog("it")
    reviewed = {key: value for key, value in catalog.items() if key not in manual_only}
    assert reviewed, "it: keine Einträge außerhalb des Handbuchs — sonst prüft dieser Test nichts"

    voi = [
        f"{key[:50]!r}: {why!r}"
        for key, value in reviewed.items()
        for why in [_italian_formal(key, value)]
        if why
    ]
    assert not voi, "it spricht „voi“ oder „Lei“:\n" + "\n".join(voi)


@pytest.mark.parametrize("language", ["fr", "it"])
def test_no_entry_mixes_two_apostrophes(language: str) -> None:
    """Ein Text schreibt den Apostroph auf eine Art (``uebersetzung.md``).

    Durchsicht 0.5.1: „Supprimer l’étape“ neben „l'étape“ im Satz, der den
    Menüeintrag zitiert; für den Kunden derselbe Knopf, für die Zitatprüfung
    ein anderer.
    """
    manual_only = _manual_only()
    catalog = read_catalog(language)
    reviewed = {key: value for key, value in catalog.items() if key not in manual_only}
    assert reviewed, (
        f"{language}: keine Einträge außerhalb des Handbuchs — sonst prüft dieser Test nichts"
    )

    mixed = [key[:60] for key, value in reviewed.items() if "'" in value and "’" in value]
    assert not mixed, f"{language}: beide Apostrophe in einem Text:\n" + "\n".join(mixed)


def model_text_files() -> list[Path]:
    """Was das Sprachmodell liest: die Agentenschicht und der Steckbrief."""
    return [
        *sorted((PACKAGE_DIR / "core" / "agent").glob("*.py")),
        PACKAGE_DIR / "core" / "perceive" / "digest.py",
    ]


def non_model_surface_files() -> list[Path]:
    """Kommandozeile und der ganze Kern außer den Modelltexten.

    Bis RM-285 las die Prüfung im Kern nur ``install.py``, ``log.py`` und
    ``support.py``; der Einrichtungsdialog für ComfyUI setzte derweil feste
    Doppelpunkte vor übersetzte Sätze. Was sonst ans Modell oder an den Kunden
    geht (``registry/surfaces``, ``knowledge/rules``, ``perceive/actions``),
    war ungeschützt.
    """
    model = set(model_text_files())
    return sorted((PACKAGE_DIR / "cli").rglob("*.py")) + [
        path for path in sorted((PACKAGE_DIR / "core").rglob("*.py")) if path not in model
    ]


def test_model_texts_do_not_append_a_fixed_colon() -> None:
    """RM-285, der Rest: Auch was das Sprachmodell liest, setzt seinen
    Doppelpunkt im Katalog — Steckbrief, Werkzeugbeschreibungen („Ort: …“),
    Werkzeugantworten. Im Französischen stand davor sonst kein Leerzeichen,
    und ein Agententitel („Vorschlag: …“) landet als Transaktionstitel im
    Verlauf des Kunden. Auf Deutsch bleibt jeder Text Zeichen für Zeichen,
    was er war.
    """
    paths = model_text_files()
    assert len(paths) > 5, "die Agentenschicht muss Quellen haben"
    offenders = [
        f"{path.relative_to(PACKAGE_DIR)}:{line}"
        for path in paths
        for line in sorted(_fixed_translated_colons(ast.parse(path.read_text(encoding="utf-8"))))
    ]
    assert not offenders, "feste Doppelpunkte neben Übersetzungen:\n" + "\n".join(offenders)


def test_non_model_surface_labels_do_not_append_a_fixed_colon() -> None:
    """Modellkontext und Bereichsnachweis gehören zu ihren getrennten Abnahmen."""
    paths = non_model_surface_files()
    assert len(paths) > 100, "die Kundentextprüfung muss den Kern lesen"
    offenders = [
        f"{path.relative_to(PACKAGE_DIR)}:{line}"
        for path in paths
        for line in sorted(_fixed_translated_colons(ast.parse(path.read_text(encoding="utf-8"))))
    ]
    assert not offenders, "feste Doppelpunkte neben Übersetzungen:\n" + "\n".join(offenders)


@pytest.mark.parametrize("language", ("fr", "it"))
def test_feature_edit_and_change_have_distinct_action_names(language: str) -> None:
    """Örtliches Bearbeiten und die Änderungsoperation bleiben unterscheidbar."""
    catalog = read_catalog(language)
    edit = catalog["Merkmal bearbeiten"]
    change = catalog["Merkmal ändern"]
    assert _first_word_stem(edit) != _first_word_stem(change), (language, edit, change)
    assert catalog["Merkmal bearbeiten …"] == edit + " …"


@pytest.mark.parametrize(
    ("tool", "operation", "same"),
    (
        ("Cut", "Cut away", True),
        ("Taglia", "Tagliare via", True),
        ("Séparer", "Séparer le long d'une ligne", True),
        ("Cut", "Crop", False),
        ("Taglia", "Tronca", False),
        ("Séparer", "Découper", False),
    ),
)
def test_action_stem_control_includes_multiword_names(
    tool: str, operation: str, same: bool
) -> None:
    """Eine Ergänzung hinter demselben Verb versteckt die Kollision nicht."""
    assert (_first_word_stem(tool) == _first_word_stem(operation)) is same


@pytest.mark.parametrize(
    ("key", "expected"),
    (
        ("Abschneiden", "Tronca"),
        ("Dreiecke angleichen", "Uniforma i triangoli"),
        ("Fügeweg prüfen", "Verifica il percorso di montaggio"),
        ("Lochfeld schneiden", "Taglia un campo di fori"),
        ("Dreiecke verringern", "Riduci i triangoli"),
    ),
)
def test_italian_reviewed_operation_titles_use_the_second_person(key: str, expected: str) -> None:
    """Die fünf beanstandeten Operationstitel sprechen den Kunden direkt an."""
    assert read_catalog("it")[key] == expected


@pytest.mark.parametrize(
    ("key", "value", "formal"),
    (
        (
            "Gedruckt wird er, solange Sie das Feld nicht ändern.",
            "Viene stampato finché non modifica il campo.",
            True,
        ),
        (
            "Gedruckt wird er, solange Sie das Feld nicht ändern.",
            "Viene stampato finché non modifichi il campo.",
            False,
        ),
        (
            "Gedruckt wird er, solange Sie das Feld nicht ändern.",
            "Viene stampato finché non modifichi il campo della stampante.",
            False,
        ),
        (
            "Der Agent wiederholt, bis er das Feld ändert.",
            "L'agente ripete finché non modifica il campo.",
            False,
        ),
        ("Wenn Sie eine Änderung wünschen.", "Se vuoi una modifica del campo.", False),
        ("Solange Sie das Feld ändern.", "Il modello non cambia.", False),
    ),
)
def test_italian_customer_clause_guard_keeps_model_and_noun_counterexamples(
    key: str, value: str, formal: bool
) -> None:
    """Nur die belegte Kundenanrede macht den Indikativ zur falschen Person."""
    assert (_italian_formal(key, value) is not None) is formal


def _typographic_apostrophe_entries(catalog: dict[str, str]) -> list[str]:
    """Einheitliche Apostrophe gelten auch zwischen verschiedenen Katalogeinträgen."""
    return [key for key, value in catalog.items() if "’" in value]


@pytest.mark.parametrize("language", ("fr", "it"))
def test_french_and_italian_use_straight_apostrophes_everywhere(language: str) -> None:
    """Menütitel und ihre Zitate im Handbuch schreiben denselben Apostroph."""
    catalog = read_catalog(language)
    assert catalog, f"{language}: leerer Katalog prüft keine Apostrophe"
    unexpected = _typographic_apostrophe_entries(catalog)
    assert not unexpected, f"{language}: typografische Apostrophe in {len(unexpected)} Einträgen"


@pytest.mark.parametrize(
    ("catalog", "expected"),
    (
        ({"Titel": "Modifier l’élément", "Zitat": "Modifier l'élément"}, ["Titel"]),
        ({"Hinweis": "Aspetta un po’.", "Zitat": "Aspetta un po'."}, ["Hinweis"]),
        ({"Titel": "Modifier l'élément", "Zitat": "Modifier l'élément"}, []),
    ),
)
def test_apostrophe_guard_control_checks_separate_entries(
    catalog: dict[str, str], expected: list[str]
) -> None:
    """Auch zwei je einzeln konsistente Einträge können den Katalog mischen."""
    assert _typographic_apostrophe_entries(catalog) == expected


def test_italian_empty_feature_hint_uses_second_person() -> None:
    """Auch der Leersatz gibt eine direkte Handlungsanweisung mit tu."""
    key = (
        "Kein Merkmal gewählt. Klicken Sie eine Fläche, eine Kante oder eine Bohrung an — "
        "im Objektbaum oder im Bild."
    )
    value = read_catalog("it").get(key)
    assert value, "Der Leersatz muss im italienischen Katalog stehen."
    assert "Fai clic" in value, value
    assert "Fare clic" not in value, value
