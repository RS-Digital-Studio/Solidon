"""Die Schlüssel in ``values`` sind Bezeichner — der Nutzer liest Beschriftungen.

``Finding.values`` und ``AppError.values`` tragen die Zahlen zu einem Befund.
Ihre Schlüssel sind englisch, mit Unterstrich, mit Einheitensuffix — und die
Oberfläche schrieb sie **roh** hin: „oversize_mm: 12.4" im Befund-Tooltip,
„open_edges: 6" in den Einzelheiten eines Fehlers. Das ist eine feste
Zeichenkette in der Oberfläche mit einem Umweg (Regel 20).

Diese Datei hält das Wörterbuch vollständig, **ohne dass jemand daran denken
muss**. Von Hand gepflegt heißt driften — genau daran war das
Palettenwörterbuch gescheitert, das neben der Menüleiste stand.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from app.ui.labels import _VALUE_NAMES, _VALUE_UNITS, value_label, value_line

CORE = Path(__file__).resolve().parents[1] / "app" / "core"


def keys_in_source() -> dict[str, str]:
    """Jeden ``values={...}``-Schlüssel aus ``app/core``, mit seiner Datei.

    Per AST und nicht per Suchmuster: ``values={"a": 1}`` steht über mehrere
    Zeilen, in Bedingungen, in Aufrufen von Aufrufen.

    **Gesehen wird auch die Variable.** Sie zu übergehen war eine Lücke mit
    Folgen: Wer den Satz erst zusammenbaut —

        values: dict[str, Any] = {"object": index, "excess": ...}
        findings.append(Finding(..., values=values))

    — kam hier nie vor, und genau so entstehen die längeren Befunde. Drei
    Schlüssel standen dadurch als rohes Englisch beim Nutzer: ``excess``,
    ``checked``, ``materials``. Gesucht wird deshalb jede Zuweisung an einen
    Namen ``values`` mit einem Wörterbuch als Wert, mit und ohne Annotation.

    **Und die Schlüssel, die eine Ausnahme selbst beisteuert.** ``errors.py``
    setzt sie über ``_with_values(kwargs, tool=…, exit_code=…)`` — ein Aufruf,
    kein Wörterbuch. Genau so standen ``tool`` und ``exit_code`` als rohes
    Englisch im Tooltip jedes Fehlers eines externen Programms.

    **Und die Zuweisung an einen einzelnen Schlüssel.** ``values["shared"] =
    format_volume(shared)`` steht in keinem Wörterbuch-Literal, also fiel sie
    durch dasselbe Loch: ``shared`` und ``detail`` standen als rohes Englisch im
    Tooltip, obwohl der Docstring darüber genau diese Sorte Fund als behoben
    beschreibt. Die Lücke war im Satz danach sogar benannt — „ein Wörterbuch,
    das schrittweise gefüllt wird" —, und benannt ist nicht geschlossen.

    Was weiter nicht gesehen wird, ist ein ``values=dict(...)`` mit Namen als
    Argumenten. Dort greift die Sicherung in ``value_label``, die Unbekanntes
    durchlässt, statt den Tooltip zu leeren.
    """
    found: dict[str, str] = {}

    def collect(node: ast.Dict, name: str) -> None:
        # Auch die Wörterbücher **im** Wörterbuch: ``**({"materials": …} if …
        # else {})`` trägt seinen Schlüssel in einem eigenen ``ast.Dict``, und
        # in ``keys`` steht für einen ``**``-Verbund nur ``None``. Genau so
        # blieb ``materials`` unbenannt.
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Dict):
                continue
            for key in inner.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    found.setdefault(key.value, name)

    for path in sorted(CORE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "values" and isinstance(keyword.value, ast.Dict):
                        collect(keyword.value, path.name)
                named = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
                if named == "_with_values":
                    for keyword in node.keywords:
                        if keyword.arg and keyword.arg != "values":
                            found.setdefault(keyword.arg, path.name)
            elif isinstance(node, ast.AnnAssign):
                if (
                    isinstance(node.target, ast.Name)
                    and node.target.id == "values"
                    and isinstance(node.value, ast.Dict)
                ):
                    collect(node.value, path.name)
            elif isinstance(node, ast.Assign):
                names = [entry.id for entry in node.targets if isinstance(entry, ast.Name)]
                if "values" in names and isinstance(node.value, ast.Dict):
                    collect(node.value, path.name)
                # ``values["shared"] = …`` — ein Schlüssel, den niemand als
                # Literal schreibt und der genauso beim Nutzer landet.
                for target in node.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "values"
                        and isinstance(target.slice, ast.Constant)
                        and isinstance(target.slice.value, str)
                    ):
                        found.setdefault(target.slice.value, path.name)
    return found


def stem(key: str) -> str:
    for suffix, _unit in _VALUE_UNITS:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


def test_every_value_key_has_a_label() -> None:
    """Ein neuer Schlüssel ohne Beschriftung macht diesen Test rot.

    Das ist der Punkt: Wer einen Befund um eine Zahl erweitert, erfährt es
    hier — und nicht der Nutzer, der drei Wochen später einen Bezeichner im
    Tooltip liest.
    """
    missing = {key: file for key, file in keys_in_source().items() if stem(key) not in _VALUE_NAMES}
    assert not missing, "ohne Beschriftung landet der Bezeichner selbst im Tooltip: " + ", ".join(
        f"{key} ({file})" for key, file in sorted(missing.items())
    )


def test_the_dictionary_carries_nothing_dead() -> None:
    """Und andersherum: Was niemand mehr benutzt, wird auch nicht übersetzt.

    Fünf Kataloge tragen jeden Eintrag mit. Eine Beschriftung zu einem
    Schlüssel, den es nicht mehr gibt, ist Arbeit für fünf Sprachen ohne
    Leser.
    """
    used = {stem(key) for key in keys_in_source()}
    dead = sorted(set(_VALUE_NAMES) - used)
    assert not dead, f"Beschriftung ohne Schlüssel: {dead}"


def test_the_unit_comes_from_the_suffix_not_from_the_dictionary() -> None:
    """``size`` und ``size_mm`` teilen sich einen Eintrag.

    Sonst stünde jede Größe zweimal im Wörterbuch, einmal mit und einmal ohne
    Einheit — und ein neuer Schlüssel mit bekanntem Stamm wäre trotzdem
    unübersetzt.
    """
    assert value_label("size") == "Größe"
    assert value_label("size_mm") == "Größe (mm)"
    assert value_label("volume_mm3") == "Volumen (mm³)"
    assert value_label("share_percent") == "Anteil (%)"


def test_the_longest_suffix_wins() -> None:
    """``_mm`` steht am Ende von ``_mm3``.

    Wird der Reihe nach von kurz nach lang geprüft, schluckt ``_mm`` das
    ``_mm3``, und aus einem Volumen wird „Volumen3 (mm)". Die Reihenfolge in
    ``_VALUE_UNITS`` ist deshalb keine Geschmacksfrage.
    """
    assert "mm³" in value_label("volume_mm3")
    assert "mm²" not in value_label("volume_mm3")


def test_an_unknown_key_survives_instead_of_vanishing() -> None:
    """Was der Test nicht sieht, darf die Anzeige nicht leeren.

    Ein zusammengebautes ``values=dict(...)`` steht in keinem Wörterbuch. Der
    rohe Schlüssel ist dann die schlechtere, aber immer noch eine Auskunft —
    ein leerer Tooltip wäre gar keine.
    """
    assert value_label("etwas_ganz_neues") == "etwas_ganz_neues"


def test_a_line_reads_like_a_line() -> None:
    """Beschriftung, Doppelpunkt, Wert — und die Zahl in der Anzeigesprache.

    Die Einzelheiten eines Fehlers sind kein Sonderfall von §13: Wo die
    Sprache ein Komma will, steht ein Komma.
    """
    assert value_line("open_edges", 6) == "Offene Kanten: 6"
    assert value_line("oversize_mm", 12.4).startswith("Übermaß (mm): 12")


def test_the_report_offers_what_helps(qt_app: object) -> None:
    """Ein Befund, der nur sagt was nicht stimmt, ist die halbe Antwort.

    Drei Handlungen zum Bauraum waren vollstaendig gebaut — teilen,
    verkleinern, anderes Profil — und wurden **nie angeboten**: Sie hingen an
    ``OutOfBuildVolume``, einer Ausnahme, die niemand wirft. Bauraum ist ein
    Bericht und keine Sperre (§29), und damit war der einzige Weg zu ihnen
    zugemauert.

    **Und dann waren es zwei von drei.** Teilen und Verkleinern kamen mit dem
    Kontextmenü des Berichts; „anderes Druckerprofil" blieb liegen, weil ihr
    Handler fehlte. Für den Kunden mit zwei Maschinen ist sie die
    naheliegendste der drei — der Drucker eines offenen Projekts wird in den
    Druckeinstellungen gewechselt, und genau dorthin führt sie jetzt.
    """
    from app.core.errors import CHOOSE_PRINTER, SCALE_TO_FIT, SPLIT_MODEL
    from app.ui.panels import FINDING_ACTIONS

    assert FINDING_ACTIONS["arrange.out_of_build_volume"] == (
        SPLIT_MODEL,
        SCALE_TO_FIT,
        CHOOSE_PRINTER,
    )


def test_a_body_below_the_bed_gets_the_click_that_helps() -> None:
    """Teilen und Verkleinern helfen dem verrutschten Koerper nicht.

    Beide Faelle liefen unter einer Kennung, und die Kennung entscheidet, was
    der Pruefbericht anbietet. Damit bekam der haeufigste Fall von Weg 1 — ein
    heruntergeladenes Modell sitzt mittig auf z = 0 und steckt zur Haelfte
    unter der Platte — genau die zwei Handlungen angeboten, die nichts
    ausrichten. §17.1 sagt zum Aufsetzen „anbieten, nicht erzwingen"; angeboten
    war es nirgends.
    """
    from app.core.errors import ARRANGE_ON_BED, PLACE_ON_BED
    from app.ui.panels import FINDING_ACTIONS

    assert FINDING_ACTIONS["arrange.below_bed"] == (PLACE_ON_BED,)
    assert FINDING_ACTIONS["arrange.off_the_plate"] == (ARRANGE_ON_BED,)


def test_a_finding_reaches_the_handlers_that_expect_an_error(qt_app: object) -> None:
    """Die Handler kommen aus dem Fehlerdialog und wollen einen ``AppError``.

    Zweimal zu schreiben — einmal fuer Fehler, einmal fuer Befunde — hiesse
    zwei Wahrheiten ueber dieselbe Handlung. Der Befund wird verpackt, und
    dabei muessen genau die zwei Angaben ankommen, die die Handler lesen: der
    Koerper und die Zahlen.
    """
    from app.core.types import Finding
    from app.ui.panels import as_error

    finding = Finding(
        code="arrange.out_of_build_volume",
        severity="warning",
        message="Das Objekt steht über den Bauraum hinaus.",
        object_id="obj_1",
        values={"axes": "z", "excess": "12.4 mm"},
    )
    error = as_error(finding)

    assert error.object_id == "obj_1"
    assert error.values["axes"] == "z"
    assert str(error.title) == "Das Objekt steht über den Bauraum hinaus."


def test_the_estimate_reaches_the_status_bar_too() -> None:
    """Die Schaetzung ueber zehn Sekunden gab es nur bei leerem Bild.

    §2.8 verlangt sie fuer lange Rechnungen — und sie hing am Ladeschleier,
    den es nur gibt, solange **kein** Koerper dasteht. Bei jeder langen
    Rechnung an einem geladenen Modell, also genau im gemeinten Fall, stand in
    der Statusleiste Prozent ohne jede Zeitangabe.
    """
    import time as clock

    from app.ui.loading import ESTIMATE_AFTER_S, remaining_time

    # Zwoelf Sekunden gelaufen, ein Viertel geschafft: rund 36 Sekunden Rest.
    started = clock.monotonic() - (ESTIMATE_AFTER_S + 2.0)
    assert "noch etwa" in remaining_time(started, 0.25)

    # Und vorher steht nichts da — geraten ist schlechter als geschwiegen.
    assert remaining_time(clock.monotonic() - 1.0, 0.25) == ""
    assert remaining_time(None, 0.25) == ""


def test_a_path_keeps_its_dots_and_a_number_gets_its_comma(qt_app: object) -> None:
    """Das Dezimaltrennzeichen gehört an Zahlen, nicht an Pfade.

    ``localised`` tauscht **jeden** Punkt gegen das Trennzeichen der Sprache,
    und es lag auf jedem Wert eines Befunds. Befunde tragen aber Pfade,
    Adressen und Dateiendungen: In der deutschen Oberfläche stand
    ``Pfad: sources/1_cube_clean,stl``, ``Adresse: https://example,com/x,stl``
    und ``Endung: ,step`` — ein Pfad, den niemand benutzen kann, und eine
    Adresse, die falsch ist.

    Eine Fassungsnummer prüft die Grenze mit: „1.2.3" ist keine Zahl mit der
    Einheit „.3", und genau daran scheitert die naive Prüfung „enthält Ziffern
    und einen Punkt".
    """
    from PySide6.QtCore import QLocale

    from app.ui.labels import localised_value

    before = QLocale()
    QLocale.setDefault(QLocale("de"))
    try:
        for text in (
            "sources/1_cube_clean.stl",
            "https://example.com/model.stl",
            ".step",
            "1.2.3",
            "obj_1",
        ):
            assert localised_value(text) == text, f"{text!r} wurde angefasst"

        assert localised_value("12.30") == "12,30"
        assert localised_value("0.5 mm") == "0,5 mm"
        assert localised_value(12.5) == "12,5"
    finally:
        QLocale.setDefault(before)


def _finding_codes() -> dict[str, set[str]]:
    """Jeder ``Finding(code=...)``, den ``app/core`` erzeugt, mit seinen Rängen.

    Per AST und nicht per Textsuche, aus demselben Grund wie in
    ``test_every_value_key_has_a_label``: Ein Befund entsteht als Aufruf, und
    die Kennung steht als Literal darin.
    """
    import ast
    from pathlib import Path

    import app.core

    found: dict[str, set[str]] = {}
    for path in Path(app.core.__file__).parent.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - nur bei kaputtem Baum
            continue
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Finding"
            ):
                continue
            code = severity = None
            for keyword in node.keywords:
                if keyword.arg == "code" and isinstance(keyword.value, ast.Constant):
                    code = keyword.value.value
                if keyword.arg == "severity" and isinstance(keyword.value, ast.Constant):
                    severity = keyword.value.value
            if isinstance(code, str):
                found.setdefault(code, set()).add(severity or "?")
    return found


def test_the_same_problem_offers_the_same_actions(qt_app: object) -> None:
    """Wer den Befund meldet, ändert nicht, was dagegen hilft.

    „Nicht geschlossen" meldet der Kern an drei Stellen — beim Einlesen, beim
    Exportieren und nach jedem Zug des Agenten. Zwei trugen *Reparieren und
    erneut versuchen* und *Stellen zeigen*, der dritte nichts: Wer über den
    Chat ein Objekt aufriss, bekam den Satz und kein Menü, obwohl beide
    Handler gebaut und verdrahtet sind.

    Geprüft wird die **Familie** und nicht der Einzelfall: Befunde mit
    demselben Namen hinter dem Punkt melden dasselbe Problem. Ein vierter
    Melder wird damit rot statt still, und das ist der Sinn — der dritte war
    still.
    """
    from app.ui.panels import FINDING_ACTIONS

    families: dict[str, set[str]] = {}
    for code in _finding_codes():
        if "." not in code:
            continue
        families.setdefault(code.split(".", 1)[1], set()).add(code)

    uneven: list[str] = []
    for problem, codes in families.items():
        offered = {code: FINDING_ACTIONS.get(code) for code in codes}
        distinct = {actions for actions in offered.values() if actions is not None}
        if not distinct:
            continue  # kein Melder trägt eine Handlung — dann ist das die Aussage
        without = sorted(code for code, actions in offered.items() if actions is None)
        if without:
            uneven.append(
                f"{problem}: {', '.join(without)} ohne Handlung, die Geschwister haben eine"
            )
        if len(distinct) > 1:
            uneven.append(f"{problem}: verschiedene Handlungen für dasselbe Problem")

    assert not uneven, "\n".join(uneven)


# --- Längenfelder sprechen die Anzeigeeinheit (§19.3) ---------------------------


def test_a_length_field_shows_the_unit_and_returns_millimetres(qt_app: object) -> None:
    """Außen die Anzeigeeinheit, innen Millimeter.

    Die dreizehn Längenfelder der Leisten waren gewöhnliche ``QDoubleSpinBox``
    mit festem ``mm``-Suffix, und ihre Leisten gaben ``value()`` an den Kern.
    Nur das Suffix zu tauschen wäre deshalb kein halber Schritt gewesen,
    sondern ein falscher: „20,00 in" über einem Wert von 20 mm behauptet
    20 Zoll.
    """
    from app.ui.labels import LengthSpin, set_display_unit

    field = LengthSpin()
    field.set_range_mm(0.1, 100.0)
    field.set_value_mm(6.0)

    assert field.suffix().strip() == "mm"
    assert field.value_mm() == pytest.approx(6.0)

    set_display_unit("in")
    field.refresh_unit()

    assert field.suffix().strip() == "in"
    assert field.value() == pytest.approx(6.0 / 25.4, abs=1e-4), "der Wert wird mitgenommen"
    assert field.value_mm() == pytest.approx(6.0), "der Kern bekommt Millimeter"
    # Die Grenzen wandern mit, sonst wäre eine Untergrenze von 0,1 mm in Zoll
    # eine von 0,1 in — dem Fünfundzwanzigfachen.
    assert field.minimum() == pytest.approx(0.1 / 25.4, abs=1e-4)
    assert field.maximum() == pytest.approx(100.0 / 25.4, abs=1e-3)
    # Und die Feinheit: mit zwei Stellen wäre die Untergrenze auf null gerundet.
    assert field.decimals() >= 4


def test_a_length_field_keeps_its_value_across_the_unit(qt_app: object) -> None:
    """Hin und zurück ändert nichts — derselbe Schutz wie im Operationsdialog.

    40 mm sind 1,5748 Zoll, und aus 1,5748 Zoll werden 39,99992 mm. Ohne das
    Gedächtnis für den Kernwert verschöbe jedes Umschalten jedes Maß.
    """
    from app.ui.labels import LengthSpin, set_display_unit

    field = LengthSpin()
    field.set_range_mm(0.0, 1000.0)
    field.set_value_mm(40.0)

    for unit in ("in", "mm", "in", "mm"):
        set_display_unit(unit)
        field.refresh_unit()
        assert field.value_mm() == pytest.approx(40.0, abs=1e-9), unit


def test_a_typed_value_is_read_in_the_shown_unit(qt_app: object) -> None:
    """Wer in Zoll „1" tippt, meint 25,4 Millimeter."""
    from app.ui.labels import LengthSpin, set_display_unit

    set_display_unit("in")
    field = LengthSpin()
    field.set_range_mm(0.0, 1000.0)
    field.setValue(1.0)

    assert field.value_mm() == pytest.approx(25.4)


def test_no_bar_nails_a_length_field_to_millimetres() -> None:
    """Bauart-Prüfung: kein Längenfeld greift den ersten Eintrag der Tabelle.

    Dreizehn taten es, und das war nicht Bequemlichkeit, sondern die
    Umschaltung aus §19.3, die an der Eingabe aufhörte. ``DISPLAY_UNITS[0]``
    ist der **erste Eintrag** und damit immer „mm" — wer so schreibt, meint die
    Tabelle und nimmt die Einstellung.

    Gelesen wird der **Syntaxbaum** und nicht der Text: Der Docstring von
    ``LengthSpin`` nennt das alte Muster, um zu erklären, warum es weg ist. Eine
    Textsuche fände genau die Erklärung.

    Der Einstellungsdialog darf die Tabelle weiter lesen — er baut daraus die
    Auswahl, und das ist ihr Zweck.
    """
    import app.ui

    erlaubt = {"settings_dialog.py"}
    schuldig: list[str] = []
    for path in sorted(Path(app.ui.__file__).parent.glob("*.py")):
        if path.name in erlaubt:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            target = node.value
            if isinstance(target, ast.Name) and target.id == "DISPLAY_UNITS":
                schuldig.append(f"{path.name}:{node.lineno}")
    assert not schuldig, (
        "Längenfeld auf Millimeter festgenagelt — LengthSpin nehmen:\n" + "\n".join(schuldig)
    )


def test_switching_the_unit_says_nothing_in_between(qt_app: object) -> None:
    """Ein Einheitenwechsel ist keine Wertänderung — und meldet keine.

    ``_apply_unit`` legt die neue Spanne, während noch der Wert der alten
    steht: Bei 10 mm klemmt Qt die 10 auf die Zolluntergrenze und feuert
    damit. Ein Empfänger, der daraufhin ``value_mm()`` liest, bekam 99,9998 —
    einen Wert, den niemand eingestellt hat, vor dem richtigen.

    In Millimetern ändert sich hier nichts. Also darf nichts gemeldet werden,
    weder roh noch umgerechnet.
    """
    from app.ui.labels import LengthSpin, set_display_unit

    field = LengthSpin()
    field.set_range_mm(0.0, 100.0)
    field.set_value_mm(10.0)

    raw: list[float] = []
    millimetres: list[float] = []
    field.valueChanged.connect(raw.append)
    field.valueChangedMm.connect(millimetres.append)

    set_display_unit("in")
    field.refresh_unit()

    assert raw == [], f"der Wechsel meldete Zwischenwerte: {raw}"
    assert millimetres == [], f"der Wechsel meldete Zwischenwerte: {millimetres}"
    assert field.value_mm() == pytest.approx(10.0), "und der Wert steht danach richtig"


def test_a_length_field_announces_millimetres(qt_app: object) -> None:
    """``valueChangedMm`` ist die Lesestelle, die ``valueChanged`` nicht sein kann.

    Qts Signal trägt die Zahl aus dem Feld. Wer sie weitergibt, hat die
    Umrechnung übersprungen, ohne ``value()`` geschrieben zu haben — genau so
    kam der Pinselradius als 0,1969 in der Szene an, wo 5 mm gemeint waren.
    """
    from app.ui.labels import LengthSpin, set_display_unit

    set_display_unit("in")
    field = LengthSpin()
    field.set_range_mm(0.0, 1000.0)

    raw: list[float] = []
    millimetres: list[float] = []
    field.valueChanged.connect(raw.append)
    field.valueChangedMm.connect(millimetres.append)

    field.setValue(1.0)

    assert raw == [pytest.approx(1.0)], "das rohe Signal trägt weiter die Anzeige"
    assert millimetres == [pytest.approx(25.4)], "das andere trägt, was der Kern braucht"
