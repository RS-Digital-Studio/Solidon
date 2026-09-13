"""PHP für die Endpunkttests: ohne es ein Skip — in der Linux-CI ein Fehler.

Die Tests gegen ``website/api`` starten PHPs eingebauten Server oder rufen
``php -l``. Auf einem Entwicklerrechner ohne PHP überspringen sie sich, und das
ist richtig. In der CI war dasselbe Überspringen unsichtbar: ``build.yml``
richtete PHP nie ein, der Ubuntu-Runner brachte es zufällig mit, und 88
Testfälle (gemessen am 02.09.2026 über die drei Dateien, die diesen Prüfer
rufen) hätten sich still verabschiedet, sobald das Runner-Bild es weglässt.
Unter ``CI`` auf Linux ist fehlendes PHP deshalb ein roter Test;
Windows und macOS richten dort keines ein und überspringen weiter.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

import pytest


def missing_php(reason: str) -> NoReturn:
    """Überspringt — oder scheitert, wo die CI PHP ausdrücklich einrichtet."""
    if os.environ.get("CI") and sys.platform.startswith("linux"):
        pytest.fail(f"PHP fehlt in der CI — build.yml richtet es im Ubuntu-Lauf ein ({reason})")
    pytest.skip(reason)


def php_executable(reason: str = "PHP fehlt") -> str:
    """Der Pfad zu ``php``; ohne es greift :func:`missing_php`."""
    php = shutil.which("php")
    if php is None:
        missing_php(reason)
    return php


def php_command(*extensions: str) -> list[str]:
    """Lädt benötigte Erweiterungen nur im Prüfprozess, ohne eine php.ini zu ändern."""
    executable = php_executable()
    command = [executable]
    if not extensions:
        return command
    modules = subprocess.run(
        [executable, "-m"], capture_output=True, text=True, timeout=30, check=False
    )
    assert modules.returncode == 0, "PHP kann seine Erweiterungen nicht auflisten"
    loaded = set(modules.stdout.lower().splitlines())
    for name in dict.fromkeys(extensions):
        if name.lower() in loaded:
            continue
        filename = f"php_{name}.dll" if os.name == "nt" else f"{name}.so"
        library = Path(executable).resolve().parent / "ext" / filename
        if not library.is_file():
            missing_php(f"PHP ist ohne die benötigte Erweiterung {name} installiert")
        command.extend(["-d", f"extension={library}"])
    required = " && ".join(f"extension_loaded({name!r})" for name in extensions)
    probe = subprocess.run(
        [*command, "-r", f"exit(({required}) ? 0 : 1);"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert probe.returncode == 0, f"PHP kann benötigte Erweiterungen nicht laden: {extensions}"
    return command
