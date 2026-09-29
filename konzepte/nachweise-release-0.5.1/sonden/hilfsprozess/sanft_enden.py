"""Wie lange braucht ein untätiger Hilfsprozess, um nach dem Schließen der Leitung selbst zu enden?

Für ``kernel_process.GRACEFUL_SECONDS`` (Durchsicht RM-212, B4): ``shutdown``
schließt die Leitung eines untätigen Hilfsprozesses und wartet, bis er auf dem
gewöhnlichen Weg endet — erst nach der Frist wird er beendet. Gemessen wird
die Dauer von ``shutdown`` und der Ausgang (0 = selbst geendet), zehnmal, mit
weiter Frist.

Aufruf (gebunden, aus dem Arbeitsbaum): python ../sonden/hilfsprozess/sanft_enden.py <baum>
"""

if __name__ == "__main__":
    import sys
    import time
    from pathlib import Path

    TREE = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(TREE))
    from app.core.geom import kernel_process

    kernel_process.GRACEFUL_SECONDS = 30.0  # type: ignore[misc]
    spans = []
    for _round in range(10):
        assert kernel_process.warm_up()
        helper = kernel_process.processes()[0]
        began = time.perf_counter()
        kernel_process.shutdown()
        spans.append(time.perf_counter() - began)
        print(f"shutdown {1000 * spans[-1]:6.0f} ms, Ausgang {helper.exitcode}", flush=True)
    spans.sort()
    print(f"Median {1000 * spans[len(spans) // 2]:.0f} ms, längste {1000 * spans[-1]:.0f} ms")
