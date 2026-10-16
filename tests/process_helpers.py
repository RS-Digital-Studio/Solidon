"""Ein Kindprozess der Suite, dessen Zeitgrenze den ganzen Baum trifft (CS-35).

``subprocess.run(…, timeout=…)`` und ``Popen.kill()`` beenden nur das direkte
Kind. Unter Windows ist die bash von Git (``Git\\bin\\bash.exe``,
``tests/shell_helpers.bash_executable``) ein Starter mit der Shell als Kind:
Nach einer Zeitüberschreitung lief die Shell weiter — eine Schreibschleife aus
``test_suite_script.py`` hinterließ je Lauf 200–250 MB in ``%TEMP%``.
:func:`run_bounded` startet über ``app.core.process.start_bounded`` und beendet
bei Zeitablauf mit ``terminate_process_tree``; sonst verhält es sich wie
``subprocess.run``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import Any


def run_bounded(
    command: Sequence[str],
    *,
    timeout: float,
    capture_output: bool = False,
    check: bool = False,
    **options: Any,
) -> subprocess.CompletedProcess[Any]:
    """Wie ``subprocess.run``; bei ``timeout`` endet der ganze Prozessbaum (``TimeoutExpired``).

    Auch nach einem normalen Ende bleibt kein Nachkomme: Was im Hintergrund weiterlief,
    beendet die Prozessgrenze wie bei ``process.run_limited`` (RC2-9).
    """
    from app.core.process import start_bounded, terminate_process_tree

    if capture_output:
        options.setdefault("stdout", subprocess.PIPE)
        options.setdefault("stderr", subprocess.PIPE)
    process = start_bounded(command, **options)
    try:
        output, errors = process.communicate(timeout=timeout)
    except BaseException:
        terminate_process_tree(process)
        process.communicate()
        raise
    terminate_process_tree(process)  # der Starter ist fertig; übrige Nachkommen enden mit ihm
    completed = subprocess.CompletedProcess(list(command), process.returncode, output, errors)
    if check:
        completed.check_returncode()
    return completed
