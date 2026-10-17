"""Wo bash und sh der Suite liegen — eine Quelle für jede Testdatei, die Skripte wirklich fährt.

``tests/helpers.py`` reicht ``bash_executable`` weiter,
``tests/packaging_helpers.py`` baut ``workflow_shell`` darauf, und die
Linux-Installationsfälle in ``tests/test_packaging.py`` fragen ``posix_shell``:
Zwei Finder derselben Auskunft laufen auseinander, sobald einer eine Falle
kennt, die der andere nicht kennt. Dass keine Testdatei selbst sucht, hält
``test_packaging_platform.py::test_only_the_shell_helpers_look_for_bash_or_sh``.

Das Modul lädt nur die Standardbibliothek. Viele Testdateien importieren
``tests/helpers.py``, und ``tools/affected_tests.py`` folgt auch Importen in
Funktionen: Ein Finder in ``tests/packaging_helpers.py`` zöge über
``helpers.py`` dessen träge Importe aus ``app`` und ``tools`` für alle diese
Dateien nach, und jede Änderung an den Paketwerkzeugen wählte sie alle mit aus.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def bash_executable(*, keep_path: bool = False) -> Path | None:
    """Die bash aus dem Suchpfad oder neben dem tatsächlich installierten Git.

    ``System32\\bash.exe`` ist der Starter von WSL und keine Git-bash: Er fährt
    ein Skript in einem Linux mit eigenem Dateisystem, nicht in der bash, für
    die es gemessen wird. Steht keine andere bash im Suchpfad — der Installer
    von Git für Windows trägt in der Vorgabe nur ``Git\\cmd`` ein —, sucht der
    Finder neben ``git``, unter ``ProgramFiles`` und in der Installation je
    Nutzer, und dort gibt es zwei:

    - ``bin\\bash.exe``, der Starter, stellt ``/mingw64/bin`` und ``/usr/bin``
      selbst vor den ``PATH``. Ein Skript findet ``head`` und ``grep`` ohne
      Zutun des Aufrufers; die Vorgabe.
    - ``usr\\bin\\bash.exe`` mit ``keep_path`` ist die bash selbst und lässt den
      ``PATH`` des Aufrufers, wie er ist. Das brauchen Aufrufer, die Attrappen
      für ``git`` oder ``python`` vorn eintragen — der Starter überdeckte sie
      mit den echten. Dafür trägt der Aufrufer den Ordner dieser bash selbst
      ein, wenn das Skript ``head`` oder ``grep`` braucht.
    """
    return _shell("bash", keep_path=keep_path)


def posix_shell() -> Path | None:
    """Die POSIX-``sh`` aus dem Suchpfad oder neben dem tatsächlich installierten Git.

    Das Linux-Installationsskript ist bewusst POSIX-``sh``. Git für Windows
    bringt ``usr\\bin\\sh.exe`` mit und trägt es in der Vorgabe nicht in den
    ``PATH`` ein; gesucht wird an denselben Stellen wie bei ``bash_executable``.
    Die ``sh`` dort lässt den ``PATH`` des Aufrufers, wie er ist — die Fälle
    brauchen nur, was die Shell selbst kann.
    """
    return _shell("sh", keep_path=True)


def _shell(name: str, *, keep_path: bool) -> Path | None:
    """``name`` aus dem Suchpfad außer ``System32``, sonst aus dem Ordner von Git."""
    executable = shutil.which(name)
    if executable and "system32" not in Path(executable).parts[-2].lower():
        return Path(executable)
    git = shutil.which("git")
    roots = [Path(git).parent.parent] if git else []
    for variable, suffix in (("ProgramFiles", "Git"), ("LOCALAPPDATA", "Programs/Git")):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value) / suffix)
    program = Path("usr/bin" if keep_path else "bin") / f"{name}.exe"
    return next((root / program for root in roots if (root / program).is_file()), None)
