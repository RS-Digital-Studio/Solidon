"""Wo die bash der Suite liegt — eine Quelle für jede Testdatei, die Skripte wirklich fährt.

``tests/helpers.py`` reicht ``bash_executable`` weiter, und
``tests/packaging_helpers.py`` baut ``workflow_shell`` darauf: Zwei Finder
derselben Auskunft laufen auseinander, sobald einer eine Falle kennt, die der
andere nicht kennt.

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
    executable = shutil.which("bash")
    if executable and "system32" not in Path(executable).parts[-2].lower():
        return Path(executable)
    git = shutil.which("git")
    roots = [Path(git).parent.parent] if git else []
    for variable, suffix in (("ProgramFiles", "Git"), ("LOCALAPPDATA", "Programs/Git")):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value) / suffix)
    folder = "usr/bin" if keep_path else "bin"
    return next(
        (root / folder / "bash.exe" for root in roots if (root / folder / "bash.exe").is_file()),
        None,
    )
