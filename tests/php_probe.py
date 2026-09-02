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
import sys
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
