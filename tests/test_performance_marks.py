"""Die Mechanik hinter den Leistungsmarken — nicht die Leistung selbst.

**Eigene Datei, und die Frage nach AGENTS.md ist geprüft:** Die Sache gehörte
in ``test_performance.py``, wenn dort nicht ``pytestmark =
pytest.mark.performance`` modulweit stünde. Diese Tests sollen aber gerade ins
**Tor** und nicht in den Sonderlauf: Sie messen nichts, sie prüfen die
Rechnung, mit der jede Marke gebildet wird — und ein Fehler darin fälscht jede
Zahl in ``tests/.performance.json``, ohne dass ein Leistungstest davon rot
würde.

Der Anlass ist gemessen und kein Vorsatz: Der Umbau von Minimum auf Median am
30.08.2026 trug eine Delle, die der **erste** Lauf nicht zeigte (26 von 26
grün) und der zweite schon. Ein Test hier hätte sie sofort gefangen.

Gemessen wird nirgends — die Uhr ist gestellt, die Baseline liegt im
Temp-Ordner. Die Datei kostet Millisekunden.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from tests import test_performance as marks


@pytest.fixture
def baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Eine eigene Markendatei je Test — die echte bleibt unberührt."""
    pfad = tmp_path / ".performance.json"
    monkeypatch.setattr(marks, "BASELINE", pfad)
    return pfad


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Eine gestellte Uhr: Jeder Eintrag ist die Dauer des nächsten Laufs.

    Ohne sie müsste dieser Test echte Sekunden verbrauchen, um über eine
    Schwelle zu kommen — und wäre damit selbst ein Leistungstest.
    """
    dauern: list[float] = []
    stand = [0.0]
    aufrufe = [0]

    def perf_counter() -> float:
        # ``measure`` fragt die Uhr **zweimal** je Messung — vor und nach der
        # Arbeit. Vorgerückt wird deshalb nur beim zweiten: Wer bei jedem
        # Aufruf vorrückt, verbraucht mit der ersten Messung beide Dauern und
        # misst die zweite als null.
        aufrufe[0] += 1
        if aufrufe[0] % 2 == 0 and dauern:
            stand[0] += dauern.pop(0)
        return stand[0]

    monkeypatch.setattr(time, "perf_counter", perf_counter)
    return dauern


def _entry(baseline: Path, name: str = "probe") -> dict[str, Any]:
    contexts = json.loads(baseline.read_text(encoding="utf-8"))[name]
    assert len(contexts) == 1, "die Testmarke hat unerwartet mehrere Aufrufkontexte"
    return dict(next(iter(contexts.values())))


def _store_entry(baseline: Path, entry: dict[str, Any]) -> None:
    """Legt eine Marke im öffentlichen Aufrufkontext von ``measure`` ab."""
    marks.measure("probe", lambda: None)
    contexts = json.loads(baseline.read_text(encoding="utf-8"))["probe"]
    assert len(contexts) == 1, "measure hat keinen einzelnen Aufrufkontext angelegt"
    context = next(iter(contexts))
    baseline.write_text(json.dumps({"probe": {context: entry}}), encoding="utf-8")


# --- Die Delle vom 30.08.2026 -------------------------------------------------------


def test_a_migrated_outlier_does_not_fail_the_next_two_runs(
    baseline: Path, clock: list[float]
) -> None:
    """Der alte Bestwert ist ein Ausreißer und darf keine Regression melden.

    ``best`` war das Minimum über **alle** Läufe; als einzelner Wert in einem
    halb leeren Fenster zieht er den Median nach unten. Gemessen an
    ``boolean_medium``: Marke 451 gegen 849 gemessen, dann Marke 650 gegen 838
    — zwei Überschreitungen, und der Test wäre rot gewesen, ohne dass etwas
    langsamer wurde. ``MIN_RUNS`` hält den Vergleich zurück, bis das Fenster
    trägt.
    """
    _store_entry(baseline, {"best": 0.451, "strikes": 0})

    clock.extend([0.849, 0.838])
    marks.measure("probe", lambda: None)
    marks.measure("probe", lambda: None)

    gespeichert = _entry(baseline)
    assert gespeichert["strikes"] == 0, "der migrierte Ausreißer meldete eine Regression"
    assert [round(one, 3) for one in gespeichert["runs"]] == [0.451, 0.849, 0.838]


def test_from_the_third_run_the_outlier_no_longer_sets_the_mark(
    baseline: Path, clock: list[float]
) -> None:
    """Ab dem dritten Wert steht der Ausreißer außen.

    Das ist die Eigenschaft, wegen der dort ein Median steht und kein
    Mittelwert: 451 zieht den Median von [451, 838, 849] nicht, ein
    Durchschnitt läge bei 713 und meldete den nächsten normalen Lauf als
    Regression.
    """
    _store_entry(baseline, {"runs": [0.451, 0.849, 0.838], "strikes": 0})

    clock.append(0.840)
    marks.measure("probe", lambda: None)

    assert _entry(baseline)["strikes"] == 0, "der Ausreißer bestimmte die Marke noch immer"


def test_a_real_slowdown_still_turns_the_mark_red(baseline: Path, clock: list[float]) -> None:
    """Die Gegenrichtung, sonst prüfte der Test nur Nachsicht.

    Der Median darf keine echte Verlangsamung verdecken: Wer eine Rechnung um
    mehr als ein Viertel teurer macht, reißt die Schwelle, bevor das Fenster
    nachgezogen ist.
    """
    _store_entry(baseline, {"runs": [0.80, 0.81, 0.82], "strikes": 0})

    clock.extend([1.60, 1.62])
    marks.measure("probe", lambda: None)
    with pytest.raises(AssertionError, match="slower than the mark"):
        marks.measure("probe", lambda: None)


# --- Was aus alten Fassungen gelesen wird -------------------------------------------


def test_measure_reads_all_three_older_shapes(baseline: Path, clock: list[float]) -> None:
    """Drei Fassungen der Markendatei müssen weiter lesbar sein.

    Eine Marke, die beim Formatwechsel wegfällt, ist zwei Läufe blind — und
    blind ist schlechter als ungenau.
    """
    cases: tuple[tuple[dict[str, Any], list[float]], ...] = (
        ({"runs": [0.1, 0.2], "strikes": 0}, [0.1, 0.2]),
        ({"best": 0.3, "strikes": 4}, [0.3]),
        ({"strikes": 0}, []),
    )
    for entry, expected in cases:
        _store_entry(baseline, entry)
        clock.append(0.0)
        marks.measure("probe", lambda: None)

        expected_runs = [*expected[-marks.WINDOW :], 0.0][-marks.WINDOW :]
        assert _entry(baseline)["runs"] == expected_runs


def test_measure_cuts_a_stored_window_to_length(baseline: Path, clock: list[float]) -> None:
    """Eine von Hand gewachsene Datei bestimmt die Fensterbreite nicht."""
    zu_viele = [float(one) for one in range(marks.WINDOW + 3)]
    _store_entry(baseline, {"runs": zu_viele, "strikes": 0})
    clock.append(0.0)

    marks.measure("probe", lambda: None)
    gelesen = _entry(baseline)["runs"]

    assert len(gelesen) == marks.WINDOW
    alte_laeufe = zu_viele[-max(marks.WINDOW - 1, 0) :] if marks.WINDOW > 1 else []
    assert gelesen == [*alte_laeufe, 0.0][-marks.WINDOW :], (
        "abgeschnitten wird vorn, und der neue Lauf bleibt hinten"
    )


# --- Das Fenster schiebt -------------------------------------------------------------


def test_the_window_drops_its_oldest_run(baseline: Path, clock: list[float]) -> None:
    """Der Lauf nach dem vollen Fenster wirft den ältesten hinaus.

    Ohne das Schieben wüchse die Datei unbegrenzt, und die Marke bliebe an
    Werten hängen, die eine Maschine von vorgestern gemessen hat.
    """
    voll = [0.10, 0.11, 0.12, 0.13, 0.14][: marks.WINDOW]
    _store_entry(baseline, {"runs": voll, "strikes": 0})

    clock.append(0.15)
    marks.measure("probe", lambda: None)

    gespeichert = _entry(baseline)["runs"]
    assert len(gespeichert) == marks.WINDOW
    assert round(gespeichert[-1], 3) == 0.15
    erwartet = [*voll[1:], 0.15][-marks.WINDOW :]
    assert [round(one, 3) for one in gespeichert] == [round(one, 3) for one in erwartet], (
        "der älteste Lauf fiel heraus, auch bei einem Fenster der Länge eins"
    )


def test_measure_obeys_a_window_of_one(
    baseline: Path, clock: list[float], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bei einer Fensterlänge bleibt nur die soeben gemessene Dauer stehen."""
    monkeypatch.setattr(marks, "WINDOW", 1)
    _store_entry(baseline, {"runs": [0.10, 0.11, 0.12], "strikes": 0})

    clock.append(0.15)
    marks.measure("probe", lambda: None)

    assert _entry(baseline)["runs"] == [0.15]


# --- Ergebnisprüfung vor dem Markenschreiben ----------------------------------------


@pytest.mark.parametrize("existing", [False, True], ids=["new-mark", "existing-mark"])
@pytest.mark.parametrize(
    "problem",
    [AssertionError("helper not used"), ValueError("result bytes differ"), KeyboardInterrupt()],
    ids=["wrong-helper-path", "wrong-result", "interrupted"],
)
def test_rejected_work_never_creates_or_changes_a_mark(
    baseline: Path, clock: list[float], existing: bool, problem: BaseException
) -> None:
    """Kein gültiger Weg oder Inhalt: Auch eine alte Vergleichsreihe bleibt unangetastet.

    Die Nachprüfung kommt nach der gestellten Uhr, aber vor jedem Markenzugriff.
    Ein Rückfall, veränderte Ergebnisbytes oder eine Unterbrechung dürfen weder
    eine neue Hilfsprozessmarke anlegen noch eine vorhandene Reihe verschieben.
    """
    if existing:
        _store_entry(baseline, {"runs": [0.10, 0.11, 0.12], "strikes": 0})
    previous = baseline.read_bytes() if baseline.exists() else None
    calls: list[str] = []

    def verify() -> None:
        calls.append("verify")
        raise problem

    clock.append(0.25)
    with pytest.raises(type(problem), match=str(problem) or None):
        marks.measure("probe", lambda: calls.append("work"), verify=verify)

    assert calls == ["work", "verify"]
    current = baseline.read_bytes() if baseline.exists() else None
    assert current == previous, "die abgewiesene Arbeit hat die Vergleichsmarke verändert"


def test_verification_is_outside_the_clock_and_before_the_first_mark(
    baseline: Path, clock: list[float]
) -> None:
    """Die Prüfung zählt nicht zur API-Zeit; erst gültige Arbeit schreibt eine Marke."""
    calls: list[str] = []
    clock.extend([0.25, 99.0])

    def verify() -> None:
        calls.append("verify")
        assert not baseline.exists(), "die Marke wurde schon vor ihrer Prüfung gespeichert"
        # Die 99 gestellten Sekunden gehören nur zur Nachprüfung.
        time.perf_counter()
        time.perf_counter()

    taken = marks.measure("probe", lambda: calls.append("work"), verify=verify)

    assert calls == ["work", "verify"]
    assert taken == pytest.approx(0.25)
    assert _entry(baseline)["runs"] == pytest.approx([0.25])
    assert not clock, "die Nachprüfung wurde nicht vollständig ausgeführt"
