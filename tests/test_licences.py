"""Dependencies against the clearance list (Bauplan §36, AGENTS.md rule 22)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.knowledge import licences

NOTICE_FILE = Path(__file__).parent.parent / "THIRD-PARTY-NOTICES.md"


def test_no_dependency_violates_the_policy() -> None:
    violations = licences.check()
    assert not violations, "licence violations:\n" + "\n".join(str(entry) for entry in violations)


def test_the_runtime_tree_is_actually_walked() -> None:
    packages = {name.lower() for name in licences.runtime_packages()}
    for expected in ("trimesh", "manifold3d", "numpy", "scipy", "pyside6", "pyvista"):
        assert expected in packages, f"{expected} is missing from the checked tree"


def test_gpl_is_refused_and_lgpl_is_not() -> None:
    policy = licences.load_policy()
    assert any("GPL-3" in entry for entry in policy.forbidden)
    assert "LGPL" in policy.allowed, "PySide6 is LGPL and is allowed when linked dynamically"


def test_the_banned_packages_are_not_installed() -> None:
    installed = {licences.normalise(name) for name in licences.runtime_packages()}
    for banned in licences.load_policy().banned_packages:
        assert licences.normalise(banned) not in installed, f"{banned} must not be installed"


def test_a_gpl_package_would_be_caught() -> None:
    """Ein Wächter für die Prüfung selbst — sonst bewiese ein grüner Lauf
    nichts.
    """
    policy = licences.load_policy()
    text = "GPL-3.0-or-later".lower()
    assert any(entry.lower() in text for entry in policy.forbidden)
    assert "lgpl" not in text


def test_notices_list_every_package() -> None:
    text = licences.notices()
    assert text.startswith("| Paket | Lizenz |")
    for name in licences.runtime_packages():
        assert name in text


def test_the_notice_file_names_every_runtime_package() -> None:
    """Die eingecheckte Datei, nicht die erzeugte Liste (§36).

    ``notices()`` gegen sich selbst zu prüfen beweist nichts: die Liste ist
    per Bauart vollständig. Was mit dem Paket ausgeliefert wird, ist
    ``THIRD-PARTY-NOTICES.md`` — sie steht in ``packaging/formwerk.spec`` und
    ist der Hinweis, den BSD und MIT bei einer Binärverteilung verlangen. Sie
    war elf Pakete hinterher, weil niemand sie mit dem Baum verglichen hat.

    Geprüft wird nur der **Name**. Die Lizenzangabe eines Pakets ändert
    zwischen zwei Fassungen schon mal ihre Schreibweise („BSD License" gegen
    „BSD-3-Clause"), und daran soll kein Lauf scheitern — ein fehlendes Paket
    ist der Fehler, den es zu fangen gilt.
    """
    text = NOTICE_FILE.read_text(encoding="utf-8")
    missing = sorted(name for name in licences.runtime_packages() if name not in text)
    assert not missing, (
        "THIRD-PARTY-NOTICES.md nennt diese Laufzeitpakete nicht:\n"
        + "\n".join(missing)
        + "\n\nNeu erzeugen: python -m app.core.knowledge.licences"
    )


@pytest.mark.parametrize("package", ["pymeshlab", "PyQt5", "PyQt6"])
def test_the_plan_names_these_as_forbidden(package: str) -> None:
    assert package in licences.load_policy().banned_packages
