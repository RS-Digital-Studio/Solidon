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


def php_extension(name: str, reason: str = "") -> str:
    """Der Pfad zu ``php``, wenn es die Erweiterung ``name`` lädt — sonst greift
    :func:`missing_php`.

    Dieselbe Trennung wie beim fehlenden PHP, eine Stufe tiefer: Auf Roberts
    Rechner lag am 02.09.2026 ein PHP 8.4 **ohne php.ini**, das sodium und
    pdo_sqlite nicht lädt. ``activation.php`` prüft sodium vor Rumpf und
    Ratenbegrenzung und antwortet 503, und drei Tests, die erst *hinter* dieser
    Prüfung ihre Frage stellen (Medientyp, Kennungen im Zähler), waren rot,
    ohne dass am Endpunkt etwas falsch war — mit geladener Erweiterung 92 von
    92 grün. Ein Test, der seine Frage nicht stellen kann, überspringt sich
    und sagt, was ihm fehlt; in der Linux-CI, die die Erweiterungen ausdrücklich
    einrichtet, bleibt das ein roter Test.
    """
    php = php_executable(reason or f"PHP fehlt; der Test braucht die Erweiterung {name}")
    loaded = subprocess.run(
        [php, "-r", f"exit(extension_loaded({name!r}) ? 0 : 1);"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if loaded.returncode != 0:
        missing_php(
            reason
            or f"PHP lädt die Erweiterung {name} nicht — in der php.ini "
            f"`extension={name}` eintragen (Windows: extension_dir auf ext/ zeigen lassen)"
        )
    return php
