"""Die nicht betriebene gehostete Tauschstelle bleibt aus dem Webpaket entfernt."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).parent.parent
WEBSITE = ROOT / "website"
ROADMAP = ROOT / "ROADMAP.md"
BLUEPRINT = ROOT / "3d-agent-bauplan.md"
EXCHANGE_CONCEPT = ROOT / "konzepte" / "konzept-tauschboerse-2026-08.md"
UI_FILES = (ROOT / "app" / "ui" / "catalog.py", ROOT / "app" / "ui" / "main_window.py")
LOCALES = ROOT / "app" / "i18n" / "locales"

RETIRED = (
    "api/shared.php",
    "api/shared_common.php",
    "api/shared_store.php",
    "api/shared_moderate.php",
    "api/shared-rules.json",
    "api/shared-texts.json",
    "boerse.html",
    "boerse.js",
    "tauschboerse-bedingungen.html",
    "en/exchange.html",
    "es/exchange.html",
    "fr/exchange.html",
    "it/exchange.html",
    "pt/exchange.html",
)


def test_hosted_shared_implementation_is_absent() -> None:
    """Kein ausführbarer, regelnder oder textlicher Serverbestand reist mit."""

    assert all(not (WEBSITE / relative).exists() for relative in RETIRED)


def test_retired_shared_paths_are_never_selected_for_upload() -> None:
    """Auch versehentlich neu erzeugte Altdateien bleiben außerhalb des Deployments."""

    from tools import upload_website

    for relative in RETIRED:
        assert not upload_website.wanted(WEBSITE / relative)


def test_project_knowledge_contains_no_active_hosted_exchange_promise() -> None:
    """Aktives Wissen verspricht nur den lokalen Dateiaustausch."""

    roadmap = ROADMAP.read_text(encoding="utf-8")
    forbidden_active_promises = (
        "Die T1-Galerie folgt",
        "Börsen-Galerie",
        "Börsen-Leerzustand",
        "Bei der Tauschbörse ist sie der Preis",
    )
    assert not [phrase for phrase in forbidden_active_promises if phrase in roadmap]
    retired_page_lines = [line for line in roadmap.splitlines() if "| boerse.html |" in line]
    assert all("entfällt" in line and "entfernt" in line for line in retired_page_lines)

    blueprint = BLUEPRINT.read_text(encoding="utf-8")
    concept = EXCHANGE_CONCEPT.read_text(encoding="utf-8")
    for text in (blueprint, concept):
        assert "keine öffentliche" in text.casefold()
        assert "lokal" in text.casefold()
        assert "datei" in text.casefold()


def test_app_ui_contains_only_local_part_file_exchange() -> None:
    """Die Oberfläche kennt Dateiimport und -export, aber keinen gehosteten Dienst."""

    source = "\n".join(path.read_text(encoding="utf-8") for path in UI_FILES)
    forbidden_source = (
        "Tauschbörse",
        "Börsendatei",
        "PUBLISHED_SOURCE",
        "for_upload",
        "Baustein veröffentlichen",
        "Veröffentlichten Baustein",
        'spec.source == "published"',
    )
    assert not [phrase for phrase in forbidden_source if phrase in source]
    assert 'tr("Baustein hinzufügen")' in source
    assert 'tr("Baustein weitergeben")' in source
    assert "PartFileIO" in source

    forbidden_values = {
        "en": ("Exchange file (*.json)", "upload this file to the exchange", "published part"),
        "es": (
            "Archivo de intercambio (*.json)",
            "subir este archivo al intercambio",
            "bloque publicado",
        ),
        "fr": ("Fichier d'échange (*.json)", "téléverser ce fichier vers l'échange", "bloc publié"),
        "it": (
            "File di scambio (*.json)",
            "caricare questo file nello scambio",
            "blocco pubblicato",
        ),
        "pt": (
            "Ficheiro de troca (*.json)",
            "carregar este ficheiro para a troca",
            "bloco publicado",
        ),
    }
    for language, forbidden in forbidden_values.items():
        catalog = json.loads((LOCALES / f"{language}.json").read_text(encoding="utf-8"))
        values = "\n".join(str(value) for value in catalog.values())
        assert not [phrase for phrase in forbidden if phrase.casefold() in values.casefold()]
        for key in ("Baustein hinzufügen", "Baustein weitergeben"):
            assert catalog.get(key), f"{language}: {key} ist nicht übersetzt"


def test_local_part_file_runs_through_the_ui_buttons(
    qt_app: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Export und Import erreichen über die echten Signale den Dateivertrag."""

    from PySide6.QtWidgets import QFileDialog

    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts import recipe as recipe_module
    from app.core.knowledge.parts.recipe import Recipe, register, save
    from app.core.registry import REGISTRY
    from app.core.scene.migrations import FORMAT_VERSION
    from app.core.types import Document, Operation
    from app.ui import main_window as main_window_module
    from app.ui.catalog import PartCatalog, detail
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    name = "local_part_file_ui_probe"
    operation_name = f"insert_{name}"
    storage = tmp_path / "user-parts"
    monkeypatch.setattr(recipe_module, "user_parts_dir", lambda: storage)

    document = Document(
        format_version=FORMAT_VERSION,
        app_version="test",
        ops=[
            Operation(
                id=1,
                op="create_box",
                outputs=("obj_1",),
                params={
                    "width": 20.0,
                    "depth": 18.0,
                    "height": 8.0,
                    "anchor": "corner",
                    "name": "",
                },
            )
        ],
    )
    part = Recipe(
        name=name,
        title="Lokale Dateiprobe",
        group="structure",
        document=document,
        license="CC0-1.0",
        author="Probe",
        features={"top": "face_top"},
    )
    register(part)
    source = save(part)

    exported = tmp_path / f"{name}.solidon-part"
    catalogs: list[PartCatalog] = []

    def capture_catalog(dialog: PartCatalog) -> int:
        catalogs.append(dialog)
        return int(PartCatalog.DialogCode.Rejected)

    monkeypatch.setattr(PartCatalog, "exec", capture_catalog)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(exported), "")),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(exported), "")),
    )
    troubles: list[object] = []
    monkeypatch.setattr(
        main_window_module,
        "show_error",
        lambda problem, parent=None, handlers=None: troubles.append(problem),
    )

    window = MainWindow(Session(), UiSettings())
    try:
        window.action_catalog()
        assert catalogs
        catalog = catalogs[0]
        _choose_part(catalog, name)
        assert catalog.share_part.isEnabled()
        assert catalog.share_part.isVisibleTo(catalog)
        assert "weitergeben" in catalog.share_part.text().casefold()
        catalog.share_part.click()
        _wait_until(exported.is_file, "die Weitergabe wurde nicht geschrieben")
        assert not troubles
        assert exported.is_file()

        PARTS.remove(name)
        REGISTRY.remove(operation_name)
        source.unlink()

        catalog.adopt_part.click()
        _wait_until(
            lambda: catalog.file_result.text().startswith("Baustein hinzugefügt"),
            "der sichtbare Worker-Ausgang blieb aus",
        )
        assert not troubles
        imported = PARTS.get(name)
        assert imported.source == recipe_module.IMPORTED_SOURCE
        assert "aus Datei hinzugefügt" in detail(imported)
        assert recipe_module.recipes_dir().joinpath(f"{name}.json").is_file()
        _choose_part(catalog, name)
        assert catalog.share_part.isEnabled(), (
            "die geprüfte Herkunft muss beim lokalen Weiterexport erhalten bleiben"
        )
    finally:
        PARTS.remove(name)
        REGISTRY.remove(operation_name)
        window.close()


def _wait_until(ready: object, what: str, timeout_ms: int = 5000) -> None:
    """Worker-Ausgänge über die Qt-Ereignisschleife abwarten."""

    from collections.abc import Callable

    from PySide6.QtWidgets import QApplication

    check = ready if isinstance(ready, Callable) else lambda: bool(ready)
    deadline = time.monotonic() + timeout_ms / 1000
    while not check():
        if time.monotonic() > deadline:
            raise AssertionError(f"{what} kam in {timeout_ms} ms nicht zustande")
        QApplication.processEvents()


def _choose_part(catalog: object, name: str) -> None:
    """Wählt eine Kachel über denselben Zustand wie ein Mausklick."""

    from PySide6.QtCore import Qt

    entries = catalog.list  # type: ignore[attr-defined]
    for row in range(entries.count()):
        item = entries.item(row)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == name:
            entries.setCurrentItem(item)
            return
    raise AssertionError(f"Baustein {name} fehlt im Katalog")


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_retired_endpoint_is_404_without_state_or_mail(tmp_path: Path, method: str) -> None:
    """Der frühere Endpunkt ist unerreichbar und erzeugt keinerlei Serverzustand."""

    php = shutil.which("php")
    if php is None:
        pytest.skip("PHP fehlt")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    environment = os.environ.copy()
    environment.update(
        {
            "SOLIDON_SHARED_DB": str(tmp_path / "shared.sqlite"),
            "SOLIDON_SHARED_FILES": str(tmp_path / "shared-files"),
            "SOLIDON_TEST_SMTP_PORT": "1",
        }
    )
    process = subprocess.Popen(
        [php, "-S", f"127.0.0.1:{port}", "-t", str(WEBSITE)],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        url = f"http://127.0.0.1:{port}/api/shared.php?do=upload"
        for _attempt in range(50):
            try:
                request = Request(url, data=b"probe" if method == "POST" else None, method=method)
                urlopen(request, timeout=1)
            except HTTPError as problem:
                assert problem.code == 404
                break
            except URLError:
                time.sleep(0.05)
        else:
            pytest.fail("Der PHP-Prüfserver antwortete nicht mit 404")
    finally:
        process.terminate()
        process.wait(timeout=5)

    assert not (tmp_path / "shared.sqlite").exists()
    assert not (tmp_path / "shared-files").exists()
