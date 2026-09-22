"""Begrenzte funktionale Gegenproben zur komponentenweisen Merkmalszuordnung."""

from __future__ import annotations

from dataclasses import asdict
from itertools import product
from pathlib import Path
from unittest.mock import patch
import sys

import numpy as np
import scipy
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.perceive import matching
from app.core.types import Feature


def components(matrix):
    """Komponenten ausschließlich aus akzeptablen Kanten in Originalreihenfolge."""
    allowed = matrix <= matching.MATCH_THRESHOLD
    remaining = set(range(len(matrix)))
    found = []
    while remaining:
        rows, columns = set(), set()
        pending = [min(remaining)]
        while pending:
            row = pending.pop()
            if row in rows:
                continue
            rows.add(row)
            remaining.discard(row)
            for column in np.flatnonzero(allowed[row]):
                if column in columns:
                    continue
                columns.add(int(column))
                pending.extend(int(other) for other in np.flatnonzero(allowed[:, column]))
        if columns:
            found.append((sorted(rows), sorted(columns)))
    return found


def local_assignment(matrix):
    pairs = []
    for rows, columns in components(matrix):
        local_rows, local_columns = linear_sum_assignment(matrix[np.ix_(rows, columns)])
        pairs.extend((rows[row], columns[column]) for row, column in zip(local_rows, local_columns))
    pairs.sort()
    return (
        np.asarray([row for row, _ in pairs], dtype=np.intp),
        np.asarray([column for _, column in pairs], dtype=np.intp),
    )


def result_for(matrix, *, local):
    old = {f"old_{index}": Feature(f"old_{index}", "hole", "detected", {}) for index in range(len(matrix))}
    new = {f"new_{index}": Feature(f"new_{index}", "hole", "detected", {}) for index in range(matrix.shape[1])}
    solver = local_assignment if local else linear_sum_assignment
    with patch.object(matching, "_cost_matrix", return_value=matrix.copy()), patch.object(
        matching, "linear_sum_assignment", solver
    ):
        return matching.match(old, new, (0.0, 0.0, 0.0), 1.0)


def show(name, matrix):
    global_result = result_for(matrix, local=False)
    local_result = result_for(matrix, local=True)
    print(name)
    print("matrix:", matrix.tolist())
    print("components:", components(matrix))
    print("global:", asdict(global_result))
    print("local:", asdict(local_result))
    print("assignments:", tuple(zip(*linear_sum_assignment(matrix))), tuple(zip(*local_assignment(matrix))))
    return global_result, local_result


def main():
    print("scipy:", scipy.__version__)
    print("numpy:", np.__version__)
    penalty = matching.KIND_PENALTY
    # Vollständige kleine topologische Fallmenge, keine Zeit- oder Bedarfsmessung.
    for height, width in ((2, 3), (3, 2), (3, 3), (3, 4), (4, 3)):
        for entries in product((0.0, penalty), repeat=height * width):
            matrix = np.asarray(entries).reshape(height, width)
            if len(components(matrix)) < 2:
                continue
            old = result_for(matrix, local=False)
            new = result_for(matrix, local=True)
            if old.mapping != new.mapping or set(old.orphaned) != set(new.orphaned):
                show("different-mapped-old-id", matrix)
                return
    print("no mapped/orphaned difference in enumerated zero-cost matrices")


if __name__ == "__main__":
    main()
