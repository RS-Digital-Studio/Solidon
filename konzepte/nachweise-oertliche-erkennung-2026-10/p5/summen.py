"""Welche Summenform gleicht ``a.sum()`` und ``(k,3).sum(axis=0)`` Bit für Bit?"""

import numpy as np

rng = np.random.default_rng(1)
bad = {"reduceat_1d": 0, "reduceat_2d": 0, "cumsum_2d": 0, "loop": 0}
for trial in range(3000):
    k = int(rng.integers(2, 60))
    a = rng.random(k) * 10 ** rng.uniform(-3, 3)
    m = rng.random((k, 3)) * 100 - 50
    w = m * a[:, None]
    ref1 = a.sum()
    ref2 = w.sum(axis=0)
    pad = np.concatenate((rng.random(3), a, rng.random(4)))
    if np.add.reduceat(pad, [0, 3, 3 + k])[1].tobytes() != ref1.tobytes():
        bad["reduceat_1d"] += 1
    padw = np.vstack((rng.random((2, 3)), w, rng.random((5, 3))))
    if np.add.reduceat(padw, [0, 2, 2 + k], axis=0)[1].tobytes() != ref2.tobytes():
        bad["reduceat_2d"] += 1
    acc = np.zeros(3)
    for row in w:
        acc = acc + row
    if acc.tobytes() != ref2.tobytes():
        bad["loop"] += 1
print(bad)
