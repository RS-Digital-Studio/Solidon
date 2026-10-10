"""Nachbau von numpys paarweiser Summe — welche Fassung trifft ``a.sum()`` Bit für Bit?"""

import numpy as np


def pairwise(a: np.ndarray) -> float:
    n = len(a)
    if n < 8:
        res = 0.0
        for value in a:
            res += value
        return res
    if n <= 128:
        r = [float(x) for x in a[:8]]
        i = 8
        while i < n - (n % 8):
            for j in range(8):
                r[j] += a[i + j]
            i += 8
        res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]))
        while i < n:
            res += a[i]
            i += 1
        return res
    n2 = n // 2
    n2 -= n2 % 8
    return pairwise(a[:n2]) + pairwise(a[n2:])


rng = np.random.default_rng(3)
bad = {"null": 0, "erstes": 0}
for trial in range(4000):
    n = int(rng.integers(1, 700))
    a = rng.random(n) * 10 ** rng.uniform(-3, 3)
    ref = a.sum()
    if np.float64(pairwise(a)).tobytes() != ref.tobytes():
        bad["null"] += 1
    if np.float64(a[0] + pairwise(a[1:]) if n > 1 else a[0]).tobytes() != ref.tobytes():
        bad["erstes"] += 1
print(bad)
