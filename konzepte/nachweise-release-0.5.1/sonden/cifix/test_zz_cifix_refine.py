import numpy as np
import pytest

import tests.test_refine as tr
from tests import test_platform_identity as tpi

refine = tr.refine


@pytest.mark.parametrize("k", range(12))
def test_unter_rauschen_gruen(k, monkeypatch):
    """Der neue Test hält unter jedem Rauschmuster der Sonde."""
    mult = np.uint64((0x9E3779B97F4A7C15 + 2 * k * 0x632BE59BD9B4E019) % 2**64) if k else tpi._Noise.multiplier
    monkeypatch.setattr(tpi._Noise, "multiplier", np.uint64(mult | 1))
    with tpi.platform_noise():
        tr.test_the_guard_case_is_a_run_that_answers(monkeypatch)


def test_gegenprobe_ohne_abstaende_rot(monkeypatch):
    monkeypatch.setattr(refine, "DECISION_MARGIN", -np.inf)
    monkeypatch.setattr(refine, "STOP_MARGIN_DECADES", -np.inf)
    monkeypatch.setattr(refine, "SHADOW_AGREEMENT", np.inf)
    with pytest.raises(AssertionError, match="keeps quiet"):
        tr.test_the_guard_case_is_a_run_that_answers(monkeypatch)


def test_gegenprobe_knappes_budget_rot(monkeypatch):
    """Mit 50 statt 100 Auswertungen liegt der Fall nicht mehr an der Grenze."""
    monkeypatch.setattr(tr.features, "ROUND_FIT_EVALUATIONS", 50)
    with pytest.raises(AssertionError, match="far from the budget"):
        tr.test_the_guard_case_is_a_run_that_answers(monkeypatch)
