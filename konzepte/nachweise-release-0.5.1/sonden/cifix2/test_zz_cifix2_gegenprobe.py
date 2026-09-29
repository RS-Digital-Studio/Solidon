"""Sonde Runde 2: Gegenproben und nachgestellte andere Maschinen für die Wächterprobe."""

import numpy as np
import pytest

import tests.test_refine as tr
from tests.test_platform_identity import platform_noise

refine = tr.refine
TESTS = [
    lambda mp: tr.test_the_guard_case_is_a_run_that_answers(mp),
    lambda mp: tr.test_without_any_margin_the_guard_case_is_turned_away(mp),
    lambda mp: tr.test_each_margin_alone_keeps_the_guard_case("DECISION_MARGIN", mp),
    lambda mp: tr.test_each_margin_alone_keeps_the_guard_case("STOP_MARGIN_DECADES", mp),
    lambda mp: tr.test_each_margin_alone_keeps_the_guard_case("SHADOW_AGREEMENT", mp),
]


# Eine „andere Maschine“: ein äußeres Rauschmuster über der ganzen Rechnung,
# die Lagen der Tests legen ihr eigenes darüber. 5, 7, 17: dort sagt der Stapel
# ohne Abstände nichts (wie der Linux-Runner); 2, 4: dort antwortet der echte
# Lauf nicht im Budget (wie der Windows-Runner der ersten Runde).
@pytest.mark.parametrize("machine", [1005, 1007, 1017, 1002, 1004, 2005, 2017])
def test_andere_maschine_gruen(machine, monkeypatch):
    with platform_noise(machine):
        for run in TESTS:
            run(monkeypatch)


@pytest.mark.parametrize(
    "off",
    [
        {"DECISION_MARGIN": -np.inf, "STOP_MARGIN_DECADES": -np.inf, "SHADOW_AGREEMENT": np.inf},
    ],
)
def test_alle_aus_premisse_rot(off, monkeypatch):
    for name, value in off.items():
        monkeypatch.setattr(refine, name, value)
    with pytest.raises(AssertionError, match="in vain"):
        tr.test_the_guard_case_is_a_run_that_answers(monkeypatch)


@pytest.mark.parametrize(
    ("name", "value"),
    [("DECISION_MARGIN", -np.inf), ("STOP_MARGIN_DECADES", -np.inf), ("SHADOW_AGREEMENT", np.inf), ("SHADOW_NOISE", 0.0)],
)
def test_ein_abstand_aus_rot(name, value, monkeypatch):
    monkeypatch.setattr(refine, name, value)
    target = "SHADOW_AGREEMENT" if name == "SHADOW_NOISE" else name
    with pytest.raises(pytest.fail.Exception, match="prevents no false"):
        tr.test_each_margin_alone_keeps_the_guard_case(target, monkeypatch)


def test_zeige_maschinen(monkeypatch):
    problem = tr._guard_case()
    solver = tr._guard_solver(problem)
    for machine in [1005, 1007, 1017, 1002, 1004, 2005, 2017]:
        with platform_noise(machine):
            ohne = tr._verdict(problem, monkeypatch, **tr.MARGINS_OFF)
            real = tr._real_run(solver, 100)
            print("\nMaschine", machine, "ohne", ohne, "echt", (real.nfev, real.status))
