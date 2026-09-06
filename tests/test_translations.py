"""Jeder Oberflächentext ist übersetzbar, und die Kataloge sind
vollständig (§4.1, §37.2).
"""

from __future__ import annotations

import ast
import os
import re
import unicodedata
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

#: Statische Meldungsfenster-Aufrufe. Nur an QMessageBox gezählt —
#: ``log.warning`` ist kein Dialog.
BOX_CALLS = frozenset({"information", "question", "warning", "critical"})

#: Widgets, die ihre Beschriftung als erstes Argument nehmen.
LABELLED_WIDGETS = frozenset(
    {"QLabel", "QPushButton", "QAction", "QGroupBox", "QCheckBox", "QToolBar", "QListWidgetItem"}
)


@pytest.mark.parametrize(
    "language", [entry for entry in available_languages() if entry != SOURCE_LANGUAGE]
)
def test_every_text_is_translated(language: str) -> None:
    """Jede Sprache, die dasteht, ist fertig.

    Nicht nur englisch: die Liste kommt aus dem Katalogverzeichnis, also prüft
    dieser Test jede Sprache, die jemand hinzufügt, vom ersten Lauf an. Eine
    halb übersetzte Datei einzuchecken ist damit keine Option — sie wäre eine
    Sprache in der Auswahl, die mitten im Satz nach Deutsch zurückfällt.
    """
    catalog = read_catalog(language)
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
    missing = sorted(key for key in ids if not catalog.get(key))
    assert not missing, f"{language}: {len(missing)} ohne Übersetzung\n" + "\n".join(missing)

    orphaned = sorted(key for key in catalog if key not in ids)
    assert not orphaned, f"{language}: {len(orphaned)} nicht mehr gebraucht\n" + "\n".join(orphaned)


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

    assert str(text) == "12.3 GB frei, 8 gebraucht"
    assert source_text(text) == "12.3 GB frei, 8 gebraucht"


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


@pytest.mark.parametrize("path", sorted(UI_DIR.rglob("*.py")), ids=lambda path: path.name)
def test_no_hard_wired_file_filter(path: Path) -> None:
    """AGENTS.md Regel 20 gilt auch für Dateifilter — und für Konstanten.

    ``test_no_hard_wired_text_in_the_surface`` sieht nur Argumente von
    Anzeige-Aufrufen. ``MODEL_FILTER = "Modelle (*.stl …)"`` stand daneben, auf
    Modulebene, und erschien deshalb auch in der englischen Oberfläche deutsch.
    Ein Filter ist ein Text wie jeder andere: alles vor der Klammer liest ein
    Mensch.

    Ein reiner Formatname („STL (*.stl)") bleibt draußen — er heißt überall so.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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

    assert not offenders, "file filter that never reaches tr():\n" + "\n".join(offenders)


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


@pytest.mark.parametrize("path", surface_files(), ids=lambda path: path.name)
def test_no_hard_wired_text_in_the_surface(path: Path) -> None:
    """AGENTS.md Regel 20: alles, was der Nutzer liest, geht durch tr()."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []

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
#: Einheiten, Achsen, Schriftnamen und der eine Eigenname unter den
#: Gitterstrukturen. Sie heißen in jeder Sprache gleich.
SELF_NAMING = re.compile(r"^(M\d+(\.\d+)?|\d+x\d+|mm|cm|in|m|x|y|z|DejaVu .*|gyroid)$")


def self_naming_sizes() -> frozenset[str]:
    """Dasselbe, aber aus der Normteiltabelle statt aus einem Muster.

    Ein Aluprofil heißt „2020", und zwar in jeder Sprache: Das ist sein
    Querschnitt in Millimetern, zweimal hingeschrieben. Aus der Tabelle geholt
    und nicht als ``\\d{4}`` ans Muster gehängt — dieses Muster ließe auch
    Lagerbezeichnungen wie „6800" durch, ohne dass jemand das entschieden hat,
    und eine neue Profilgröße ist hier von selbst dabei.
    """
    from app.core.knowledge import standards

    return frozenset(standards.profile_sizes())


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
    sizes = self_naming_sizes()

    def named(value: str) -> bool:
        return bool(SELF_NAMING.match(value)) or value in sizes or choice_label(value) != value

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


def test_no_source_text_writes_ae_for_a_umlaut() -> None:
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

    ids = message_ids()
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
