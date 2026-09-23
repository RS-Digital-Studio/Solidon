"""Die Oberflächen-Einstellungen in ``settings.json`` (Bauplan §38)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")


def test_an_unreadable_settings_file_keeps_the_language_of_the_system(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """Eine kaputte Einstellungsdatei machte aus jedem System ein deutsches.

    Der allererste Start fragt Installer und System nach der Sprache. Eine
    Datei, die sich nicht lesen ließ — halb geschrieben, von Hand verdorben —,
    führte dagegen auf die blanke Vorgabe, und die ist Deutsch. Unlesbar ist
    keine Wahl des Nutzers (Review Fenster 0.5.0, 22.09.2026).
    """
    from app.ui import settings as settings_module

    broken = tmp_path / "settings.json"
    broken.write_text("{ nicht fertig", encoding="utf-8")
    monkeypatch.setattr(settings_module, "settings_path", lambda: broken)
    monkeypatch.setattr(settings_module, "installed_language", lambda: None)
    monkeypatch.setattr(settings_module, "system_language", lambda: "es")

    assert settings_module.load_settings().language == "es"
