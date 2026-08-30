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
from pathlib import Path
from typing import Any

import pytest

from tests import test_performance as marks


@pytest.fixture
def baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Eine eigene Markendatei je Test — die echte bleibt unberührt."""
    pfad = tmp_path / ".performance.json"
    monkeypatch.setattr(marks, "BASELINE", pfad)
    monkeypatch.setattr(marks, "_context", "probe")
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

    monkeypatch.setattr(marks.time, "perf_counter", perf_counter)
    return dauern


def _entry(baseline: Path, name: str = "probe") -> dict[str, Any]:
    return dict(json.loads(baseline.read_text(encoding="utf-8"))[name]["probe"])


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
    baseline.write_text(
        json.dumps({"probe": {"probe": {"best": 0.451, "strikes": 0}}}), encoding="utf-8"
    )

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
    baseline.write_text(
        json.dumps({"probe": {"probe": {"runs": [0.451, 0.849, 0.838], "strikes": 0}}}),
        encoding="utf-8",
    )

    clock.append(0.840)
    marks.measure("probe", lambda: None)

    assert _entry(baseline)["strikes"] == 0, "der Ausreißer bestimmte die Marke noch immer"


def test_a_real_slowdown_still_turns_the_mark_red(baseline: Path, clock: list[float]) -> None:
    """Die Gegenrichtung, sonst prüfte der Test nur Nachsicht.

    Der Median darf keine echte Verlangsamung verdecken: Wer eine Rechnung um
    mehr als ein Viertel teurer macht, reißt die Schwelle, bevor das Fenster
    nachgezogen ist.
    """
    baseline.write_text(
        json.dumps({"probe": {"probe": {"runs": [0.80, 0.81, 0.82], "strikes": 0}}}),
        encoding="utf-8",
    )

    clock.extend([1.60, 1.62])
    marks.measure("probe", lambda: None)
    with pytest.raises(AssertionError, match="slower than the mark"):
        marks.measure("probe", lambda: None)


# --- Was aus alten Fassungen gelesen wird -------------------------------------------


def test_runs_of_reads_all_three_older_shapes() -> None:
    """Drei Fassungen der Markendatei müssen weiter lesbar sein.

    Eine Marke, die beim Formatwechsel wegfällt, ist zwei Läufe blind — und
    blind ist schlechter als ungenau.
    """
    assert marks._runs_of({"runs": [0.1, 0.2], "strikes": 0}) == [0.1, 0.2]
    assert marks._runs_of({"best": 0.3, "strikes": 4}) == [0.3]
    assert marks._runs_of({"strikes": 0}) == []


def test_a_stored_window_is_cut_to_length() -> None:
    """Eine von Hand gewachsene Datei bestimmt die Fensterbreite nicht."""
    zu_viele = [float(one) for one in range(marks.WINDOW + 3)]

    gelesen = marks._runs_of({"runs": zu_viele, "strikes": 0})

    assert len(gelesen) == marks.WINDOW
    assert gelesen == zu_viele[-marks.WINDOW :], "abgeschnitten wird vorn, nicht hinten"


# --- Das Fenster schiebt -------------------------------------------------------------


def test_the_window_drops_its_oldest_run(baseline: Path, clock: list[float]) -> None:
    """Der Lauf nach dem vollen Fenster wirft den ältesten hinaus.

    Ohne das Schieben wüchse die Datei unbegrenzt, und die Marke bliebe an
    Werten hängen, die eine Maschine von vorgestern gemessen hat.
    """
    voll = [0.10, 0.11, 0.12, 0.13, 0.14][: marks.WINDOW]
    baseline.write_text(
        json.dumps({"probe": {"probe": {"runs": voll, "strikes": 0}}}), encoding="utf-8"
    )

    clock.append(0.15)
    marks.measure("probe", lambda: None)

    gespeichert = _entry(baseline)["runs"]
    assert len(gespeichert) == marks.WINDOW
    assert round(gespeichert[-1], 3) == 0.15
    assert round(gespeichert[0], 3) == round(voll[1], 3), "der älteste blieb stehen"
