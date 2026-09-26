"""Die Zeitspanne der Vollerkennung auf diesem Rechner: Rechenprobe und Schätzung."""

from __future__ import annotations

import pytest
import trimesh

from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshData
from app.core.perceive import features, local
from app.core.perceive import recognition_time as timing

TRIANGLES = timing.RECOGNITION_REFERENCE_TRIANGLES


@pytest.fixture(autouse=True)
def fresh_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jeder Fall misst neu; der Prozess behält die Probe sonst für alle."""
    monkeypatch.setattr(timing, "_probe_seconds", None)


def clocked_probe(monkeypatch: pytest.MonkeyPatch, durations: tuple[float, ...]) -> None:
    """Die echte Rechenprobe läuft, nur die gemessene Dauer je Durchgang ist gesteuert."""
    timestamps = iter(value for duration in durations for value in (0.0, duration))
    monkeypatch.setattr(timing, "_probe_seconds", None)
    monkeypatch.setattr(timing, "perf_counter", lambda: next(timestamps))


def test_the_estimate_follows_the_speed_of_this_computer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein halb so schneller Rechner verdoppelt die Spanne, ein doppelt so schneller halbiert sie.

    Auf dem Referenzrechner dauert die Probe 18 ms und der Drache 72 s; die
    feste Spanne sagte jedem Rechner „1 bis 6 Minuten“.
    """
    clocked_probe(monkeypatch, (0.018,) * 3)
    assert local.recognition_minutes(TRIANGLES) == (1, 6)
    clocked_probe(monkeypatch, (0.009,) * 3)
    assert local.recognition_minutes(TRIANGLES) == (1, 3)
    clocked_probe(monkeypatch, (0.072,) * 3)
    assert local.recognition_minutes(TRIANGLES) == (4, 24)


def test_probe_warms_up_uses_the_median_and_runs_once_per_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Aufwärmlauf, dann drei Messungen; der Median zählt, und nur einmal je Prozess."""
    original = timing.probe_work
    checksums = []

    def measured(check_cancelled=None):
        checksums.append(original(check_cancelled))

    monkeypatch.setattr(timing, "probe_work", measured)
    clocked_probe(monkeypatch, (0.018, 0.054, 0.036))
    assert timing.calibrate() == pytest.approx(0.036)
    assert timing.calibrate() == pytest.approx(0.036)
    assert len(checksums) == 4 and len(set(checksums)) == 1


def test_cancelled_probe_leaves_no_calibration() -> None:
    """Wer die Frage abbricht, während die Probe läuft, hinterlässt keinen halben Messwert."""
    calls = 0

    def cancel_during_the_probe() -> None:
        nonlocal calls
        calls += 1
        if calls > 3:
            raise OperationCancelled()

    with pytest.raises(OperationCancelled):
        local.recognition_minutes(TRIANGLES, check_cancelled=cancel_during_the_probe)
    assert timing._probe_seconds is None


def test_the_recognition_itself_never_starts_the_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Erkennung bleibt eine reine Funktion (§15.1): Sie misst nichts und schreibt nichts.

    Die Probe läuft nur für die Anzeige — in der Frage vor der Vollerkennung
    und in der Statuszeile. Ein Lauf von ``detect`` fragt sie nie an.
    """

    def unexpected(**_kwargs: object) -> float:
        pytest.fail("die Erkennung darf die Rechenprobe nicht starten")

    monkeypatch.setattr(timing, "calibrate", unexpected)
    features.forget_cache()
    features.detect(MeshData.of(trimesh.creation.box()))
    features.forget_cache()
