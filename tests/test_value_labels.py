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
import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from app.ui.labels import (
    _VALUE_NAMES,
    _VALUE_UNITS,
    value_label,
    value_line,
    value_text,
)

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
    for suffix, *_ in _VALUE_UNITS:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


def test_every_value_key_has_a_label() -> None:
    """Ein neuer Schlüssel ohne Beschriftung macht diesen Test rot.

    Das ist der Punkt: Wer einen Befund um eine Zahl erweitert, erfährt es
    hier — und nicht der Nutzer, der drei Wochen später einen Bezeichner im
    Tooltip liest.
    """
    found = keys_in_source()
    # Ohne diese Zeile prüft der Test nichts, sobald die Suche im Quelltext
    # nichts findet — und sie sucht über ein Muster.
    assert found, "keine Wertschlüssel im Quelltext gefunden"
    missing = {key: file for key, file in found.items() if stem(key) not in _VALUE_NAMES}
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


def test_explaining_a_choice_reaches_tooltip_and_screen_reader(qt_app: object) -> None:
    """Der Satz zum Auswahlwert hängt am Eintrag — in beiden Rollen.

    „Gyroid" ist ein Name und keine Entscheidungshilfe; erst der Satz sagt,
    wann man es wählt. ``explain_choices`` liest den rohen Schlüssel aus dem
    ``itemData`` (so legen ihn beide Dialoge ab) und setzt Tooltip **und**
    ``AccessibleDescriptionRole`` — Regel 18, nicht nur eine Kodierung. Ein
    Selbstname wie „M4" bleibt ohne Satz: ein Tooltip, der den Namen
    wiederholt, wäre Tapete.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QComboBox

    from app.ui.labels import choice_label, choice_note, explain_choices

    box = QComboBox()
    box.addItem(choice_label("gyroid"), "gyroid")
    box.addItem(choice_label("M4"), "M4")
    explain_choices(box)

    note = box.itemData(0, Qt.ItemDataRole.ToolTipRole)
    assert note == choice_note("gyroid")
    assert note, "der benannte Wert trägt einen Satz"
    assert box.itemData(0, Qt.ItemDataRole.AccessibleDescriptionRole) == note
    assert box.itemData(1, Qt.ItemDataRole.ToolTipRole) is None
    assert box.itemData(1, Qt.ItemDataRole.AccessibleDescriptionRole) is None


def test_the_unit_comes_from_the_suffix_not_from_the_dictionary(qt_app: object) -> None:
    """``size`` und ``size_mm`` teilen sich einen Eintrag.

    Sonst stünde jede Größe zweimal im Wörterbuch, einmal mit und einmal ohne
    Einheit — und ein neuer Schlüssel mit bekanntem Stamm wäre trotzdem
    unübersetzt.

    Die Einheit **steht dabei am Wert**, nicht in der Beschriftung: „Übermaß
    (mm)" konnte nicht umschalten, und bei einem Volumen wäre sie sogar falsch
    gewesen — der Wert wechselt zwischen mm³ und cm³, je nach Größe.
    """
    assert value_label("size") == "Größe"
    assert value_label("size_mm") == "Größe"
    assert value_label("volume_mm3") == "Volumen"
    assert value_label("share_percent") == "Anteil"

    assert value_text("size_mm", 12.4).endswith("mm")
    assert value_text("volume_mm3", 16387.064).endswith("cm³")
    assert value_text("share_percent", 15.0) == "15 %"


def test_the_longest_suffix_wins(qt_app: object) -> None:
    """``_mm`` steht am Ende von ``_mm3``.

    Wird der Reihe nach von kurz nach lang geprüft, schluckt ``_mm`` das
    ``_mm3``: Die Beschriftung hieße „Volumen3", und der Wert käme als Länge
    heraus. Die Reihenfolge in ``_VALUE_UNITS`` ist deshalb keine
    Geschmacksfrage.
    """
    assert value_label("volume_mm3") == "Volumen", "nicht „Volumen3"

    gezeigt = value_text("volume_mm3", 16387.064)
    assert "cm³" in gezeigt, gezeigt
    assert "mm²" not in gezeigt


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
    assert value_line("oversize_mm", 12.4) == "Übermaß: 12,40 mm"


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


def test_auto_split_findings_offer_a_manual_line_without_repeating_the_search() -> None:
    """Eine gescheiterte Suche führt zur Linie und nicht in dieselbe Suche."""
    from app.core.errors import CHOOSE_PRINTER, SHOW_DETAILS, SPLIT_ALONG_LINE
    from app.ui.panels import FINDING_ACTIONS

    assert FINDING_ACTIONS["split.no_plane"] == (
        SPLIT_ALONG_LINE,
        CHOOSE_PRINTER,
        SHOW_DETAILS,
    )
    assert FINDING_ACTIONS["split.cut_failed"] == (SPLIT_ALONG_LINE, SHOW_DETAILS)
    assert FINDING_ACTIONS["split.too_many_parts"] == (
        SPLIT_ALONG_LINE,
        CHOOSE_PRINTER,
        SHOW_DETAILS,
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


def test_the_offer_button_click_reaches_the_handler(qt_app: object) -> None:
    """Gedrückt, nicht die Methode dahinter gerufen.

    Der Speicherring-Umbau hat den Klickweg der Knopfzeile verlegt: Am Knopf
    hängt nichts mehr — Befund und Handler liest erst der Klick, über
    ``weak_slot``. Damit prüft kein bestehender Test mehr die ganze Kette
    Knopf → gewählte Zeile → Handler des Fensters; dieser hier drückt.
    """
    from PySide6.QtWidgets import QPushButton, QWidget

    from app.core.errors import AppError
    from app.core.scene import EvaluationResult
    from app.core.types import Finding, Report, Scene
    from app.ui.panels import ReportPanel

    received: list[AppError] = []

    class Host(QWidget):
        def error_handlers(self) -> dict[str, object]:
            return {"place_on_bed": received.append}

    host = Host()
    panel = ReportPanel(host)
    try:
        panel.show_result(
            EvaluationResult(
                scene=Scene(
                    report=Report(
                        findings=(
                            Finding(
                                code="arrange.below_bed",
                                severity="info",
                                message="Ein Objekt liegt unter dem Druckbett",
                                object_id="obj_1",
                            ),
                        )
                    )
                )
            )
        )
        panel.list.setCurrentRow(0)
        buttons = panel._offers.findChildren(QPushButton)
        assert len(buttons) == 1, "der below_bed-Befund bietet genau eine Handlung"

        buttons[0].click()
        assert len(received) == 1, "der Klick erreicht den Handler des Fensters"
        assert isinstance(received[0], AppError)
        assert received[0].object_id == "obj_1"
    finally:
        panel.deleteLater()
        host.deleteLater()


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

    Eine Versionsnummer prüft die Grenze mit: „1.2.3" ist keine Zahl mit der
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


def test_the_same_sentence_weighs_the_same() -> None:
    """Zwei Melder mit demselben Satz melden dasselbe — also gleich schwer.

    „Entartete Dreiecke wurden entfernt." stand beim Einlesen als **Warnung**
    und in der Reparatur, mit genau diesem Satz, als **Hinweis**
    (``geom/repair.py``). Am Korpus gemessen traf es fünf von zwanzig
    Modellen: Der Prüfbericht ging bei jedem vierten Import gelb auf, und
    niemand konnte etwas tun — die Dreiecke waren zu diesem Zeitpunkt weg.

    **Eine Warnung fragt nach einer Handlung.** Wo keine gehört, weil die
    Sache erledigt ist, ist der Befund ein Hinweis. Das ist derselbe Gedanke
    wie in ``test_the_same_problem_offers_the_same_actions`` eine Ebene
    darüber, nur über das Gewicht statt über die Hilfe.

    **Geprüft wird über den Satz, nicht über die Familie.** Der Name hinter
    dem Punkt wäre zu grob: ``export.empty`` ist ein Fehler und
    ``sculpt.empty`` ein Hinweis, ``boolean.without_effect`` eine Warnung und
    ``transform.without_effect`` ein Hinweis — dieselbe Kennung, verschiedene
    Sache, zu Recht verschieden schwer. Gemessen wären das drei Fehlalarme.
    Ein **identischer Satz** dagegen behauptet Gleichheit selbst; wer ihn
    zweimal schreibt und verschieden gewichtet, hat sich an einer der beiden
    Stellen geirrt.
    """
    import ast

    import app.core

    def sentence(node: ast.AST) -> str | None:
        """Der Satz aus ``message=`` — auch durch ``_()`` hindurch."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Call) and node.args:
            return sentence(node.args[0])
        return None

    by_sentence: dict[str, dict[str, set[str]]] = {}
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
            code = severity = message = None
            for keyword in node.keywords:
                if keyword.arg == "code" and isinstance(keyword.value, ast.Constant):
                    code = keyword.value.value
                if keyword.arg == "severity" and isinstance(keyword.value, ast.Constant):
                    severity = keyword.value.value
                if keyword.arg == "message":
                    message = sentence(keyword.value)
            if code and severity and message:
                by_sentence.setdefault(message, {}).setdefault(severity, set()).add(code)

    assert by_sentence, "ohne gefundene Befunde prüft dieser Test nichts"

    uneven = [
        f"{message!r}: "
        + ", ".join(f"{rank} bei {sorted(codes)}" for rank, codes in sorted(ranks.items()))
        for message, ranks in sorted(by_sentence.items())
        if len(ranks) > 1
    ]
    assert not uneven, "derselbe Satz, verschiedenes Gewicht:\n" + "\n".join(uneven)


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


# --- Dieselbe Zahl, eine Schreibweise -----------------------------------------------

#: Ein Zahlenformat mit Nachkommastelle. ``.0f`` bleibt draußen: ohne Stelle
#: hinter dem Trennzeichen steht dort keines, das falsch sein könnte. ``.{``
#: fängt die berechneten Formate (``f"{x:.{digits}f}"``) mit — wie viele Stellen
#: es werden, weiß der Test nicht, also gilt der ungünstige Fall.
DECIMAL_FORMAT = re.compile(r"\.\{|\.[1-9]\d*f")

#: Die Funktionen, die aus einer Zahl Anzeigetext machen.
LOCALISERS = frozenset({"localised", "localised_value"})

#: Zahlen, die niemand *liest*: Sie gehen als Ausdruck in die
#: Parametergrammatik (§13), und die kennt allein den Punkt —
#: ``expressions.evaluate("30,25")`` lehnt mit „Nach dem Ausdruck steht noch
#: etwas" ab. Beide Stellen füllen dasselbe Maßfeld des Skizzeneditors vor.
GRAMMAR_NOT_LABEL = frozenset({"measured_expression", "place_measured"})


class _Numbers(ast.NodeVisitor):
    """Sammelt Kommazahlen, die **nicht** durch ``localised`` gehen."""

    def __init__(self) -> None:
        self.inside = 0
        self.functions: list[str] = []
        self.loose: list[tuple[int, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        localising = name in LOCALISERS
        self.inside += int(localising)
        self.generic_visit(node)
        self.inside -= int(localising)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(node.name)
        self.generic_visit(node)
        self.functions.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.functions.append(node.name)
        self.generic_visit(node)
        self.functions.pop()

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        for part in node.values:
            if not isinstance(part, ast.FormattedValue) or part.format_spec is None:
                continue
            spec = ast.unparse(part.format_spec)
            if not DECIMAL_FORMAT.search(spec):
                continue
            if self.inside:
                continue
            if self.functions and self.functions[-1] in GRAMMAR_NOT_LABEL:
                continue
            self.loose.append((node.lineno, spec))
        self.generic_visit(node)


@pytest.mark.parametrize(
    "path",
    sorted((Path(__file__).resolve().parents[1] / "app" / "ui").rglob("*.py")),
    ids=lambda path: path.name,
)
def test_no_number_reaches_the_user_past_the_localisation(path: Path) -> None:
    """Zwei Schreibweisen derselben Zahl in einem Blick (§19.3).

    ``localised`` gibt es, seit die Maße im Objektbaum mit Punkt neben einem
    Eingabefeld mit Komma standen. Neun weitere Stellen gingen daran vorbei,
    und keine davon war auf eine Sprache beschränkt: Die Parameterleiste
    schrieb im deutschen Fenster „12.50 mm" direkt neben ein Feld mit „12,50",
    der Chat „+1.25 cm³", die Kalibrierung „Spiel 0.25 mm". Zwei Stellen
    setzten umgekehrt das Komma fest ein — Masse und Maßband zeigten im
    englischen Fenster „8,4 g" und „12,50", wo alles andere einen Punkt trug.

    Geprüft wird das Format und nicht das Ergebnis: Wer eine Kommazahl in einen
    Anzeigetext schreibt, schickt sie durch ``localised``. Was in einen
    Ausdruck geht, ist keine Anzeige und steht in ``GRAMMAR_NOT_LABEL``.
    """
    visitor = _Numbers()
    visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))

    offenders = [f"{path.name}:{line} {spec}" for line, spec in visitor.loose]
    assert not offenders, "Kommazahl ohne localised():\n" + "\n".join(offenders)


def test_the_separator_check_would_catch_a_violation() -> None:
    """Ein Wächter für die Prüfung darüber: ein grüner Lauf soll etwas heißen."""

    def loose(source: str) -> list[tuple[int, str]]:
        visitor = _Numbers()
        visitor.visit(ast.parse(source))
        return visitor.loose

    assert loose('label.setText(f"{value:.2f} mm")'), "eine nackte Kommazahl ist ein Fund"
    assert not loose('label.setText(localised(f"{value:.2f} mm"))'), "durch localised: kein Fund"
    assert not loose('label.setText(f"{value:.0f} mm")'), "ohne Nachkommastelle kein Trennzeichen"
    assert loose('label.setText(f"{value:.{digits}f}")'), "berechnete Stellen gelten als Fund"
    assert not loose("def measured_expression():\n    return f'{value:.2f}'"), (
        "ein Ausdruck der Parametergrammatik ist keine Anzeige"
    )
    assert loose("def other():\n    return f'{value:.2f}'"), (
        "und die Ausnahme gilt nur für die zwei benannten Stellen"
    )


def test_a_mass_follows_the_language(qt_app: object) -> None:
    """„8,4 g" im englischen Fenster — das Komma stand hier fest im Code.

    Zu sehen war es nicht, solange man deutsch prüfte: ``.replace(".", ",")``
    trifft in fünf von sechs Sprachen zufällig das Richtige.
    """
    from PySide6.QtCore import QLocale

    from app.ui import facts

    before = QLocale()
    try:
        QLocale.setDefault(QLocale("en"))
        assert facts.mass(8.4) == "8.4 g"
        QLocale.setDefault(QLocale("de"))
        assert facts.mass(8.4) == "8,4 g"
        assert facts.mass(18.4) == "18 g", "über zehn Gramm gibt es keine Stelle zu tauschen"
    finally:
        QLocale.setDefault(before)


def test_the_drag_bar_follows_the_language(qt_app: object) -> None:
    """Dasselbe am Maßband, das beim Ziehen mitläuft — und dort tippt jemand hinein.

    Das Feld liest Punkt *und* Komma (``typed_value``), es zeigte aber immer ein
    Komma. Wer englisch arbeitet, sah eine Schreibweise, die er selbst nie
    eintippt.
    """
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QWidget

    from app.ui.viewport import DragValueBar

    before = QLocale()
    parent = QWidget()
    try:
        bar = DragValueBar(parent)
        QLocale.setDefault(QLocale("en"))
        bar.follow("Höhe", 12.5, "mm", 2)
        assert bar.value.text() == "12.50"
        QLocale.setDefault(QLocale("de"))
        bar.follow("Höhe", 12.5, "mm", 2)
        assert bar.value.text() == "12,50"
    finally:
        QLocale.setDefault(before)
        parent.deleteLater()


def test_the_chat_line_follows_the_language(qt_app: object) -> None:
    """Und im Chat, wo die Zahl mitten in einem Satz steht."""
    from types import SimpleNamespace

    from PySide6.QtCore import QLocale

    from app.core.agent.proposal import Proposal
    from app.core.geom.difference import Difference, SceneDifference
    from app.ui.chat import describe

    # Vorschlag und Differenz sind die echten Klassen — eine Attrappe mit den
    # drei Feldern, die ``describe`` heute liest, wäre beim vierten still
    # falsch. Nur die Vorschau selbst ist eine Hülle: Sie hat keinen Typ, und
    # ``describe`` fragt sie mit ``getattr``.
    preview = SimpleNamespace(
        proposal=Proposal(request="ein Loch"),
        difference=SceneDifference(entries={"obj_1": Difference("obj_1", added_volume=1250.0)}),
    )
    before = QLocale()
    try:
        QLocale.setDefault(QLocale("de"))
        # Die Zusage ist das Dezimaltrennzeichen der Sprache, nicht die
        # Stellenzahl: Die Schreibweise kommt seit dem Zusammenlegen aus
        # ``labels.volume`` und ist damit dieselbe wie im Steckbrief.
        assert "+1,2 cm³" in describe(preview)
        QLocale.setDefault(QLocale("en"))
        assert "+1.2 cm³" in describe(preview)
    finally:
        QLocale.setDefault(before)


# --- Und dieselbe Zahl eingetippt -------------------------------------------------


@pytest.mark.parametrize("language", ["de", "en", "fr"])
@pytest.mark.parametrize("typed", ["12.5", "12,5"])
def test_a_number_field_takes_either_separator(qt_app: object, language: str, typed: str) -> None:
    """**„12.5" im deutschen Fenster ergab 125.** Ohne Fehler, ohne Rückfrage.

    Qt liest den Punkt in einer deutschen Anzeigesprache als Tausendertrennung.
    Wer ein Maß aus einem Datenblatt, einer Fundstelle im Netz oder der eigenen
    Gewohnheit eintippt, bekam ein Teil, das zehnmal zu groß ist — und nichts
    sagte es ihm. Im englischen Fenster genauso, nur mit dem Komma.

    Geprüft wird über Tastendrücke und nicht über ``setValue``: Der Fehler
    saß im Weg vom Text zum Wert, und den nimmt ``setValue`` nicht.
    """
    from PySide6.QtCore import QLocale
    from PySide6.QtTest import QTest

    from app.ui.labels import NumberSpin

    before = QLocale()
    try:
        QLocale.setDefault(QLocale(language))
        field = NumberSpin()
        field.setDecimals(2)
        field.setRange(0.0, 1000.0)
        field.setValue(0.0)
        field.show()

        field.lineEdit().selectAll()
        QTest.keyClicks(field.lineEdit(), typed)
        field.interpretText()

        assert field.value() == pytest.approx(12.5), (
            f"{typed!r} in {language} wurde {field.value()}"
        )
        # Beide Überschreibungen zählen: ``validate`` fängt das Tippen, das
        # Einfügen und ``setText`` — ``valueFromText`` den direkten Aufruf, den
        # Qt selbst tut, wenn der Text nicht durch die Prüfung ging.
        assert field.valueFromText(typed) == pytest.approx(12.5)
    finally:
        QLocale.setDefault(before)


def test_a_length_field_takes_either_separator(qt_app: object) -> None:
    """Dasselbe am Längenfeld, wo eine Zehnerpotenz Millimeter bedeutet."""
    from PySide6.QtCore import QLocale
    from PySide6.QtTest import QTest

    from app.ui.labels import LengthSpin, set_display_unit

    before = QLocale()
    try:
        set_display_unit("mm")
        for language, typed in (("de", "12.5"), ("en", "12,5"), ("de", "12,5")):
            QLocale.setDefault(QLocale(language))
            field = LengthSpin()
            field.set_range_mm(0.0, 1000.0)
            field.show()

            field.lineEdit().selectAll()
            QTest.keyClicks(field.lineEdit(), typed)
            field.interpretText()

            assert field.value_mm() == pytest.approx(12.5), f"{typed!r} in {language}"
    finally:
        QLocale.setDefault(before)


@pytest.mark.parametrize(
    "path",
    sorted((Path(__file__).resolve().parents[1] / "app" / "ui").rglob("*.py")),
    ids=lambda path: path.name,
)
def test_no_surface_builds_a_bare_decimal_field(path: Path) -> None:
    """Neun Felder waren gewöhnliche ``QDoubleSpinBox`` — und jedes las falsch.

    Die Klasse bleibt als Typprüfung richtig (``isinstance(editor,
    QDoubleSpinBox)`` fragt „ist das ein Dezimalfeld"), gebaut wird aber
    ``NumberSpin``: Sonst kommt das nächste Feld wieder mit Qts Lesart, und die
    Suche danach fängt von vorn an.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bare = [
        f"{path.name}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "QDoubleSpinBox"
    ]
    assert not bare, "nacktes QDoubleSpinBox gebaut:\n" + "\n".join(bare)


def test_an_area_reaches_the_user_in_his_unit(qt_app: object) -> None:
    """Vier Stellen zeigen Flächen, und alle vier standen in mm².

    Wer in Zoll arbeitet, sieht Maße in Zoll und Volumen in Kubikzoll — die
    Fläche daneben blieb bei „4334 mm²" (§19.3). Geprüft werden alle vier: der
    Wert selbst, die Merkmalsangabe im Objektbaum, die Zeile der
    Schichtanalyse und die Beschriftung des Flächensprungs.
    """
    from PySide6.QtCore import QLocale

    from app.core.types import Feature
    from app.ui.labels import area, feature_measure, set_display_unit

    before = QLocale()
    try:
        QLocale.setDefault(QLocale("de"))
        face = Feature(id="face_1", kind="face", params={"area": 4334.0}, provenance=())

        set_display_unit("mm")
        assert area(4334.0) == "4334 mm²"
        assert feature_measure(face) == "4334 mm²"

        set_display_unit("in")
        assert area(4334.0) == "6,72 in²", "Zoll, und mit dem Komma der Sprache"
        assert feature_measure(face) == "6,72 in²"
    finally:
        set_display_unit("mm")
        QLocale.setDefault(before)


def test_a_finding_value_follows_the_display_unit(qt_app: object) -> None:
    """„Übermaß (mm): 12,4" stand auch dann da, wenn die Oberfläche auf Zoll
    stand.

    Die Einheit kam aus dem Suffix des Schlüssels und war Teil der
    *Beschriftung* — dort konnte sie nicht umschalten. Damit gab es zwei
    Antworten auf dieselbe Frage: Der Objektbaum zeigte Zoll, der Befund
    daneben Millimeter. Dreißig Schlüssel tragen so ein Suffix, und alle sind
    Längen, Flächen oder Volumen.

    Geprüft werden alle vier Sorten und dazu die Grenze: Ein Pfad ist keine
    Zahl und behält seine Punkte.
    """
    from PySide6.QtCore import QLocale

    from app.ui.labels import set_display_unit, value_line

    before = QLocale()
    try:
        QLocale.setDefault(QLocale("de"))

        set_display_unit("mm")
        assert value_line("oversize_mm", 12.4) == "Übermaß: 12,40 mm"
        assert value_line("first_layer_mm2", 4334.0) == "Erste Schicht: 4334 mm²"
        assert value_line("removed_mm3", 16387.064) == "Entfernt: 16,4 cm³"
        assert value_line("removed_cm3", 16.387064) == "Entfernt: 16,4 cm³"

        set_display_unit("in")
        assert value_line("oversize_mm", 12.4) == "Übermaß: 0,4882 in"
        assert value_line("first_layer_mm2", 4334.0) == "Erste Schicht: 6,72 in²"
        assert value_line("removed_mm3", 16387.064) == "Entfernt: 1,00 in³"

        # Ohne Einheit im Schlüssel bleibt alles, wie es war.
        assert value_line("open_edges", 6) == "Offene Kanten: 6"
        assert value_line("path", "sources/1_cube.stl") == "Pfad: sources/1_cube.stl"
        assert value_line("share_percent", 15.0) == "Anteil: 15 %"
    finally:
        set_display_unit("mm")
        QLocale.setDefault(before)


def test_a_value_that_is_no_number_keeps_the_unit_of_its_key(qt_app: object) -> None:
    """Und wenn dort keine Zahl steht, gibt es nichts umzurechnen.

    Dann bleibt die Einheit des Schlüssels stehen: Sie ist die einzige
    Auskunft, die es über die Größenordnung noch gibt. Der Fall kommt aus
    einem zusammengebauten ``values=dict(...)``, das der Test nicht statisch
    sieht — und eine leere Zeile wäre schlechter als eine ungenaue.
    """
    from app.ui.labels import value_text

    assert value_text("size_mm", "unbekannt") == "unbekannt mm"
    assert value_text("volume_mm3", None) == "None mm³"


@pytest.mark.parametrize(
    ("language", "typed", "expected"),
    [
        ("de", "12.5", 12.5),
        ("de", "12,5", 12.5),
        ("de", "1.000,50", 1000.5),
        ("de", "0.100", 0.1),
        ("en", "12,5", 12.5),
        ("en", "1,000.50", 1000.5),
        ("en", "0,100", 0.1),
        # Die Schreibweise der *anderen* Sprache, wie sie aus einem Datenblatt
        # oder einer Fundstelle im Netz kommt. Ohne das Zusammenziehen der
        # Gruppen scheitert hier beides: der eigene Auswerter am zweiten
        # Trennzeichen und Qts an der fremden Gruppierung.
        ("de", "1,234.56", 1234.56),
        ("en", "1.234,56", 1234.56),
        ("de", "1.234.567,89", 1234567.89),
        ("en", "12,345,678.9", 12345678.9),
    ],
)
def test_a_number_field_reads_groups_and_decimals_apart(
    qt_app: object, language: str, typed: str, expected: float
) -> None:
    """**Der erste Anlauf tauschte jeden Punkt und baute damit denselben Fehler
    ein, nur umgekehrt.**

    Er gab den getauschten Text an Qt zurück, Qt übernahm ihn ins Feld — und
    damit war die Absicht beim zweiten Tastendruck entschieden: Wer im deutschen
    Fenster „1.000,50" tippte, sah nach dem Punkt „1," stehen, die dritte Null
    fiel an ``decimals`` weg, und heraus kam 100,50. Um den Faktor tausend
    falsch, wie das Problem, das die Klasse lösen soll.

    Jetzt bleibt der getippte Text stehen, geprüft wird gegen beide Lesarten,
    und gelesen wird beim Übernehmen: **das letzte Trennzeichen ist das
    Dezimaltrennzeichen, alle davor sind Tausendertrennungen.** Ein Satz, der
    sich aufschreiben lässt — und deshalb steht er auch im Docstring.
    """
    from PySide6.QtCore import QLocale
    from PySide6.QtTest import QTest

    from app.ui.labels import NumberSpin

    before = QLocale()
    try:
        QLocale.setDefault(QLocale(language))
        field = NumberSpin()
        field.setDecimals(2)
        field.setRange(0.0, 20_000_000.0)
        field.setValue(0.0)
        field.show()

        field.lineEdit().selectAll()
        QTest.keyClicks(field.lineEdit(), typed)
        assert field.lineEdit().text() == typed, "der getippte Text bleibt stehen"

        field.interpretText()
        assert field.value() == pytest.approx(expected), (
            f"{typed!r} in {language} wurde {field.value()}"
        )
    finally:
        QLocale.setDefault(before)


def test_a_number_without_a_decimal_part_stays_ambiguous(qt_app: object) -> None:
    """„1.000" bleibt zweideutig, und die Regel entscheidet es.

    Tausend oder eins — das sagt kein Zeichen im Text. Nach der Regel ist das
    letzte Trennzeichen das Dezimaltrennzeichen, also eins. Festgehalten wird
    das hier, damit die Entscheidung sichtbar ist und nicht aus Versehen
    kippt: Wer sie ändert, ändert einen Test und nicht nur ein Verhalten.

    Zu sehen ist es außerdem — nach dem Übernehmen steht „1,00" im Feld, nicht
    „1.000".
    """
    from PySide6.QtCore import QLocale
    from PySide6.QtTest import QTest

    from app.ui.labels import NumberSpin

    before = QLocale()
    try:
        QLocale.setDefault(QLocale("de"))
        field = NumberSpin()
        field.setDecimals(2)
        field.setRange(0.0, 30000.0)
        field.setValue(0.0)
        field.show()

        field.lineEdit().selectAll()
        QTest.keyClicks(field.lineEdit(), "1.000")
        field.interpretText()

        assert field.value() == pytest.approx(1.0)
        assert field.lineEdit().text() == "1,00", "und das Feld zeigt, was es gelesen hat"
    finally:
        QLocale.setDefault(before)


def test_an_unknown_step_offers_the_way_to_its_values() -> None:
    """Der Befund verspricht „Ihre Werte bleiben erhalten" — dann muss es einen
    Weg zu ihnen geben.

    Ohne *Werte ansehen* wäre der Satz eine Sackgasse: Der Operationsdialog
    wird aus einem Registereintrag gebaut, den es für diesen Schritt nicht
    gibt. Löschen kann ihn der Verlauf inzwischen (§15.4), doch die Arbeit
    wäre damit nur weg. Was hier gebraucht wird, sind die Werte selbst — bei
    einer Datei aus 0.1.3 der OpenSCAD-Quelltext.
    """
    from app.ui.panels import FINDING_ACTIONS

    offered = FINDING_ACTIONS["evaluate.unknown_operation"]

    assert [action.id for action in offered] == ["show_step_values", "show_history"], (
        "der Weg zu den Werten steht vorn, das Zeigen im Verlauf daneben"
    )
    assert offered[0].primary, "die Handlung, um die es geht, ist die Hauptsache"


def test_a_finding_says_the_same_number_in_its_line_and_in_its_tooltip() -> None:
    """Zeile und Tooltip desselben Eintrags dürfen nicht auseinandergehen.

    Gemessen am 27.08.2026: Die Zeile schrieb „1,2 mm · 3,456 cm³", der
    Tooltip an demselben ``QListWidgetItem`` „Wandstärke: 1,20 mm · Entfernt:
    3,5 cm³" — zwei Zahlen für denselben Wert, sichtbar in einem Blick, ohne
    dass man mehr tun müsste als hinzusehen und die Maus draufzuhalten. Der
    Grund war eine zweite Einheitentabelle in ``panels``, die entschied, was
    ``labels._VALUE_UNITS`` schon entschieden hatte.

    **Und in Zoll war es keine Abweichung mehr, sondern falsch:** Eine feste
    Einheit kann nicht umschalten, also blieb die Zeile bei Millimetern
    stehen, während jede Länge daneben in Zoll stand.
    """
    from app.core.types import Finding
    from app.ui import labels
    from app.ui.panels import _line_for

    finding = Finding(
        code="hollow.done",
        severity="info",
        message="Ausgehöhlt.",
        values={"wall_mm": 1.2, "removed_cm3": 3.456},
    )

    for unit in ("mm", "in"):
        labels.set_display_unit(unit)
        line = _line_for(finding)
        for key, value in finding.values.items():
            written = labels.value_text(key, value)
            assert written in line, f"{unit}: {written!r} fehlt in der Zeile {line!r}"


#: Befunde, die denselben Sachverhalt melden und deshalb dasselbe anbieten
#: müssen. Der Familientest darüber gruppiert nach dem Namen **hinter** dem
#: Punkt und sieht diese Paare nicht: „collision" und „bodies_in_one_place"
#: sind zwei Familien mit je einem Mitglied, also immer gleich versorgt.
#:
#: Kuratiert, wie die Stammliste in ``test_language_rules``: Wer zwei Befunde
#: findet, die derselbe Knopf löst, trägt sie hier ein.
GLEICHER_SACHVERHALT: tuple[tuple[str, ...], ...] = (
    # Zwei Teile am selben Ort — einmal genau aufeinander, einmal teilweise
    # ineinander. Der Kunde sieht in beiden Fällen zwei Körper, die er
    # nebeneinander haben will.
    ("arrange.collision", "arrange.bodies_in_one_place"),
)


@pytest.mark.parametrize("gruppe", GLEICHER_SACHVERHALT, ids=lambda g: g[0])
def test_findings_of_the_same_matter_offer_the_same_way_out(gruppe: tuple[str, ...]) -> None:
    """Dasselbe Problem bietet dieselben Handlungen, gleich wie es heißt.

    ``arrange.collision`` stand ohne Knopf da, während sein Nachbar
    ``arrange.bodies_in_one_place`` *Auf dem Bett anordnen* trug — dieselbe
    Handlung, dieselbe Lage, und sie war bereits gebaut und verdrahtet.

    Der Familientest oben sah es nicht, weil er nach dem Namen hinter dem Punkt
    gruppiert: Beide bilden dort eine Familie für sich und sind damit trivial
    gleich versorgt. Die sachliche Verwandtschaft läuft über das Präfix, und
    die lässt sich nicht ableiten — deshalb steht sie oben als Liste.
    """
    from app.ui.panels import FINDING_ACTIONS

    vorhanden = _finding_codes()
    fehlend = [code for code in gruppe if code not in vorhanden]
    assert not fehlend, f"diese Kennungen erzeugt der Kern nicht (mehr): {fehlend}"

    ohne = [code for code in gruppe if not FINDING_ACTIONS.get(code)]
    assert not ohne, f"ohne Handlung: {ohne} — die Nachbarn in {gruppe} tragen eine"

    angebote = {code: tuple(a.id for a in FINDING_ACTIONS[code]) for code in gruppe}
    assert len(set(angebote.values())) == 1, f"verschiedene Angebote: {angebote}"


def test_a_finding_line_is_plain_text_and_its_symbol_carries_the_colour(qt_app: object) -> None:
    """Der ganze Satz trug die Rollenfarbe — die dringlichste am schlechtesten.

    Gemessen auf dem Listengrund: Rot bringt **4,52**, Bernstein 7,46, Blau
    6,19, und der gewöhnliche Text hätte 13,59. Ein Fehler war damit der am
    schlechtesten lesbare Befund des Berichts, und ein ganzer eingefärbter
    Satz war zugleich die lauteste Auszeichnung des Fensters für eine
    Auskunft, die ihre zweite Kodierung längst hat.

    Die Form des Symbols trägt den Schweregrad weiter (Regel 18) — Dreieck,
    Kreis, Punkt —, und sie trug ihn auch vorher schon; die Farbe steht dort
    und nicht mehr im Satz.
    """
    from PySide6.QtCore import Qt

    from app.core.scene import EvaluationResult
    from app.core.types import Finding, Report, Scene
    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(
                scene=Scene(
                    report=Report(
                        findings=(
                            Finding(code="a.error", severity="error", message="Ein Fehler"),
                            Finding(code="a.warning", severity="warning", message="Eine Warnung"),
                            Finding(code="a.info", severity="info", message="Ein Hinweis"),
                        )
                    )
                )
            )
        )
        assert panel.list.count() == 3
        for row in range(panel.list.count()):
            item = panel.list.item(row)
            assert not item.icon().isNull(), "der Schweregrad steht am Symbol"
            # Keine eigene Vordergrundfarbe: Die Zeile nimmt die des Themas.
            brush = item.foreground()
            assert brush.style() == Qt.BrushStyle.NoBrush, (
                f"Zeile {row} färbt ihren Satz selbst: {brush.color().name()}"
            )
    finally:
        panel.deleteLater()


def test_no_value_key_speaks_german() -> None:
    """Ein Wertschlüssel ist ein Schlüssel, und Schlüssel sind englisch.

    **Die Sprachprüfung kann diese Stelle nicht sehen.** Sie liest Bezeichner
    — Variablen, Funktionen, Parameter — und ein Wörterbuchschlüssel ist keiner
    davon; `"grund"` stand am 30.08.2026 in ``sketch/ops.py``, während
    ``grund`` längst in ``GERMAN_STEMS`` stand. Gefunden hat es der Test
    darüber, und zwar aus dem falschen Grund: über die fehlende
    **Beschriftung**, nicht über die Sprache. Wer den Schlüssel eingedeutscht
    *und* beschriftet hätte, wäre durchgekommen.

    Die Erhebung steht schon da (:func:`keys_in_source`), also kostet der
    Wächter nichts — und er sitzt hier und nicht in
    ``test_language_rules.py``, weil dort die Bezeichner erhoben werden und
    hier die Schlüssel.
    """
    from tests.test_language_rules import GERMAN_STEMS, GERMAN_WORDS

    assert GERMAN_STEMS and GERMAN_WORDS, "ohne Stammliste prüft dieser Test nichts"

    found = keys_in_source()
    assert found, "keine Wertschlüssel im Quelltext gefunden"

    german = {}
    for key, file in found.items():
        parts = key.split("_")
        if any(part in GERMAN_WORDS for part in parts) or any(stem in key for stem in GERMAN_STEMS):
            german[key] = file
    assert not german, (
        "Ein Wertschlüssel reist in die Projektdatei und ins Protokoll — er ist "
        f"englisch, auch wenn der Kommentar daneben deutsch ist: {german}"
    )
