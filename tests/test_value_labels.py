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

    Was weiter nicht gesehen wird, ist ein ``values=dict(...)`` oder ein
    Wörterbuch, das schrittweise gefüllt wird — dort greift die Sicherung in
    ``value_label``, die Unbekanntes durchlässt, statt den Tooltip zu leeren.
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
    """
    from app.core.errors import SCALE_TO_FIT, SPLIT_MODEL
    from app.ui.panels import FINDING_ACTIONS

    assert FINDING_ACTIONS["arrange.out_of_build_volume"] == (SPLIT_MODEL, SCALE_TO_FIT)


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
