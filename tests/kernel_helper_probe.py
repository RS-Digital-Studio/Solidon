"""Ein Hilfsprozess des Netzkerns, der mitschreibt, was seine Rechnungen nachladen (RM-380).

``spawn`` lädt im Hilfsprozess das Modul seines Startziels. Stünde
:func:`serve_and_note_loads` in ``test_kernel_process.py``, käme mit diesem
Modul ``trimesh`` schon beim Start in den Hilfsprozess, und eine Rechnung, die
es erst zurückgestellt nachlädt, fiele nicht auf. Deshalb steht es in einer
eigenen Datei, und hier oben wird nichts außer der Standardbibliothek geladen.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

#: Die Umgebungsvariable mit der Datei, in die der Hilfsprozess je Rechnung schreibt.
LOADED_MARK = "KERNEL_TEST_LOADED"


def serve_and_note_loads(connection: Any) -> None:
    """``kernel_jobs.serve``, dazu je Rechnung die Module, die sie selbst nachlud.

    Gemessen wird um den Aufruf aus ``JOBS``, also nach der Vorbereitung
    (``kernel_jobs.PREPARATIONS``) und in der Klasse, in der die Rechnung
    rechnet — unter Windows zurückgestellt.
    """
    from app.core.geom import kernel_jobs

    mark = Path(os.environ[LOADED_MARK])
    for name, job in list(kernel_jobs.JOBS.items()):
        kernel_jobs.JOBS[name] = _noting(name, job, mark)
    kernel_jobs.serve(connection)


def _noting(name: str, job: Callable[..., Any], mark: Path) -> Callable[..., Any]:
    def noted(arrays: Any, values: Any, check: Any) -> Any:
        before = set(sys.modules)
        try:
            return job(arrays, values, check)
        finally:
            loaded = sorted(set(sys.modules) - before)
            with mark.open("a", encoding="utf-8") as file:
                file.write(json.dumps({"job": name, "loaded": loaded}) + "\n")

    return noted
