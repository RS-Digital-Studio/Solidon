"""Die Nähte des Prüfstands: Zustände, die keine Maschine liefert, ohne Weg nach draußen (FD-175).

Neue Version, Browser ohne Antwort, gescheiterte Installation, ComfyUI als
installiert, abstürzender Slicer: Jede Naht setzt den Zustand dort, wo die
Anwendung fragt, und keine öffnet, installiert, lädt oder startet etwas. Ohne
Fenster; jede Naht wird nach dem Test zurückgenommen.
"""

from __future__ import annotations

from typing import Any

import pytest

from tools import function_list, function_seams, function_setup


def test_every_seam_is_a_precondition_of_the_spec_and_back() -> None:
    for name, states in function_seams.SEAMS.items():
        assert function_list.PRECONDITIONS[name] == tuple(states), name
        assert function_setup.PRECONDITIONS[name] == tuple(states), name


def test_a_seam_has_no_counter_run() -> None:
    """Ihr anderer Zustand ist die Maschine selbst — ein Gegenlauf dort ginge nach draußen."""
    base, others = function_setup.spec_variants({"preconditions": {"installation": "scheitert"}})
    assert base == {"preconditions": {"installation": "scheitert"}}
    assert others == []


def test_the_newer_release_names_the_next_version_with_texts_in_every_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.branding import APP_VERSION
    from app.core import updates
    from app.i18n.catalog import available_languages

    monkeypatch.setattr(updates, "check", updates.check)
    function_seams.newer_release()
    release = updates.check()
    assert release is not None and release.newer_than(APP_VERSION)
    for language in available_languages():
        assert release.points(language), language
        assert release.grouped(language), language
    assert function_seams._next_version("0.6.1") == "0.6.2"
    assert function_seams._next_version("1.0") == "1.1"


def test_no_browser_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    monkeypatch.setattr(QDesktopServices, "openUrl", QDesktopServices.openUrl)
    function_seams.browser_refuses()
    assert QDesktopServices.openUrl(QUrl("https://example.invalid/")) is False


def _statuses(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Eine Erhebung ohne Suche: jede angezeigte Anforderung vorhanden."""
    from app.core import install

    found = [install.Status(requirement=entry, present=True) for entry in install.shown()]
    monkeypatch.setattr(install, "statuses", lambda: tuple(found))
    monkeypatch.setattr(install, "install", install.install)
    return found


def test_a_failing_installation_installs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import install

    found = _statuses(monkeypatch)
    function_seams.install_fails()
    first, *rest = install.statuses()
    assert not first.present and first.installable
    assert rest == found[1:]
    result = install.install(first.requirement, lambda line: None)
    assert result.installed is False and result.output == function_seams.INSTALL_OUTPUT


def test_comfyui_stands_installed_and_offers_its_second_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import install

    found = _statuses(monkeypatch)
    monkeypatch.setattr(
        install,
        "statuses",
        lambda: tuple(
            install.Status(requirement=s.requirement, present=s.requirement.id != "comfyui")
            for s in found
        ),
    )
    function_seams.comfyui_installed()
    comfyui = next(s for s in install.statuses() if s.requirement.id == "comfyui")
    assert comfyui.present and comfyui.requirement.follow_up == "comfyui"


def test_loaded_spools_come_from_the_profiles_of_the_slicer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.ui import filament_inventory, filament_picker

    profiles = [
        SimpleNamespace(name=f"Generic {kind} @Elegoo", filament_type=kind)
        for kind in ("PLA", "PETG", "TPU", "ABS", "ASA")
    ]
    monkeypatch.setattr(filament_picker, "slicer_filaments", lambda: tuple(profiles))
    monkeypatch.setattr(
        filament_inventory, "configured_spools", filament_inventory.configured_spools
    )
    function_seams.slicer_spools_loaded()
    spools = filament_inventory.configured_spools(cancelled=None)
    assert [spool.name for spool in spools] == [p.name for p in profiles[:4]]
    assert [spool.colour for spool in spools] == list(function_seams.LOADED_COLOURS)
    assert spools[1].material_type == "PETG" and spools[1].slicer_profile == profiles[1].name


def test_the_slicer_crashes_without_starting(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.export import handover

    monkeypatch.setattr(handover, "_run_slicer", handover._run_slicer)
    function_seams.slicer_crashes()
    completed = handover._run_slicer(["slicer.exe", "--slice"], None, 1.0, None, None)
    assert handover.crashed(completed.returncode)
    assert completed.stdout == function_seams.CRASH_OUTPUT


def test_a_backup_lies_beside_the_project_last_opened(tmp_path: Any) -> None:
    """Neben der Kopie des Falls, jünger als sie: Beim Öffnen fragt die Anwendung."""
    from app.core.scene.project import autosave_path, find_recovery
    from app.ui.settings import load_settings, save_settings

    project = tmp_path / "zweites_projekt.p3d"
    project.write_bytes(b"projekt")
    settings = load_settings()
    settings.recent = [str(project)]
    save_settings(settings)
    function_seams.backup_beside_recent()
    assert autosave_path(project).read_bytes() == b"projekt"
    assert find_recovery(project) == autosave_path(project)


def test_the_local_chat_model_answers_nowhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama auf diesem Rechner, an einem Port ohne Antwort: Der KI-Hinweis fragt lokal."""
    from app.core.backends import llm
    from app.ui.ai_disclosure import target_for_backend

    monkeypatch.setattr(llm, "first_available", llm.first_available)
    function_seams.local_chat_model()
    backend = llm.first_available()
    assert backend is not None and backend.id == "ollama"
    assert backend.url == function_seams.CLOSED_LOCAL_URL
    target = target_for_backend(backend)
    assert target is not None and target.target_class == "local"


def test_the_activation_request_needs_no_key_and_reaches_no_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    from app.core import activation

    monkeypatch.setattr(activation, "remember", activation.remember)
    monkeypatch.setattr(
        activation, "create_activation_request", activation.create_activation_request
    )
    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))
    function_seams.activation_request()
    assert activation.remember("") is activation.state()
    assert json.loads(activation.create_activation_request("Prüfstand")) == {"device": "Prüfstand"}
