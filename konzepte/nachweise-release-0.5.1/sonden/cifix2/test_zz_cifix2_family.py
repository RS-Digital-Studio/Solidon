import contextlib
import time

import numpy as np

import tests.test_refine as tr
from tests.test_platform_identity import platform_noise

refine = tr.refine
features = tr.features
OFF = {"DECISION_MARGIN": -np.inf, "STOP_MARGIN_DECADES": -np.inf, "SHADOW_AGREEMENT": np.inf}


def _real(problem):
    import pytest
    captured = []
    def capture(initial, residual, check, jacobian=None):
        captured.append((np.asarray(initial), residual, jacobian))
        raise tr._CapturedError
    from typing import Any, cast
    start = problem.initial
    plan = features._TorusPlan(support=cast(Any, None), initial=features.TorusFit(axis=tuple(problem.axis), centre=tuple(start[:3]), ring_radius=float(start[5]), tube_radius=float(start[6]), residual=0.0, recess=False), origin=np.zeros(3), scale=1.0, initial_axis=problem.axis, first=problem.first, second=problem.second, solving=problem.points)
    old = features._refined_fit
    features._refined_fit = capture
    try:
        with pytest.raises(tr._CapturedError):
            features._torus_from_plan(plan, None)
    finally:
        features._refined_fit = old
    initial, residual, jacobian = captured[0]
    r = refine.solve(residual, jacobian, initial, precision=features.ROUND_FIT_PRECISION, evaluations=features.ROUND_FIT_EVALUATIONS)
    return r.nfev, r.status


def test_familie(monkeypatch):
    problem = tr._guard_case()
    rows = []
    t0 = time.perf_counter()
    for pattern in [None, *range(48)]:
        ctx = contextlib.nullcontext() if pattern is None else platform_noise(pattern)
        with ctx:
            real = _real(problem)
            mit = tr.verdicts_of([problem], monkeypatch)[0]
            with monkeypatch.context() as m:
                for k, v in OFF.items():
                    m.setattr(refine, k, v)
                ohne = tr.verdicts_of([problem], m)[0]
            alone = []
            for only in OFF:
                with monkeypatch.context() as m:
                    m.setattr(refine, only, OFF[only])
                    alone.append(tr.verdicts_of([problem], m)[0])
            with monkeypatch.context() as m:
                for k, v in OFF.items():
                    if k != "SHADOW_AGREEMENT":
                        m.setattr(refine, k, v)
                m.setattr(refine, "SHADOW_NOISE", 0.0)
                shadow0 = tr.verdicts_of([problem], m)[0]
        false_no = ohne and real[1] != 0
        rows.append((pattern, real, mit, ohne, alone, shadow0, false_no))
        print(pattern, real, "mit", mit, "ohne", ohne, "ohne_einen", alone, "schatten0", shadow0, "falsch", false_no, flush=True)
    print("Zeit", time.perf_counter() - t0)
    print("falsche Neins", sum(r[6] for r in rows), "von", len(rows))
    print("ohne True", sum(r[3] for r in rows), "real antwortet", sum(r[1][1] != 0 for r in rows))
    print("mit True", sum(r[2] for r in rows), "ohne_einen True", sum(any(r[4]) for r in rows))
    print("schatten0 != ohne", sum(r[5] != r[3] for r in rows))
