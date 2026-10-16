"""Nahtstellen des Prüfstands für Zustände, die keine Maschine liefert (FD-175).

Manche Fenster erscheinen nur in einem Zustand, den ein Fallprozess nicht
herstellen kann, ohne etwas außerhalb des Falls zu berühren: eine neue Version
auf dem Server, ein Browser, der eine Adresse nicht annimmt, eine Installation,
die scheitert, ein Slicer, der beim Schneiden abstürzt. Wie ``fehlt`` in
``function_setup.apply_preconditions`` setzt eine Vorbedingung hier den Zustand
über die Stelle, an der die Anwendung danach fragt — und die Antwort darauf
baut die Anwendung selbst: die Fehlermeldung, die Rückfrage, das Fenster.

**Keine Naht geht nach draußen.** Ein Fall mit ``browser = fehlt`` öffnet keinen
Browser, ``installation`` installiert nichts, ``update`` fragt keinen Server,
``slicerlauf`` startet keinen Slicer. Das gilt am echten Fenster genauso:
Ein Klick auf *PayPal im Browser öffnen* im nativen Lauf bliebe sonst nicht im
Fall.

Die Zustände stehen zugleich in ``function_list.PRECONDITIONS`` (die
Funktionsliste zieht keine fremden Module); ``tests/test_function_seams.py``
hält beide gleich. Eine Naht bildet keinen Gegenlauf
(``function_setup.spec_variants``): Ihr anderer Zustand ist die Maschine selbst.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any, Final

#: Was der nachgestellte Slicer ausgibt, bevor er abstürzt — wie Creality Print
#: 7.2 am 12.09.2026 (``handover.crashed``): eine Startzeile, dann nichts.
CRASH_OUTPUT: Final = b"crealityprint_main start\n"
#: ``0xC0000005``, Zugriffsverletzung unter Windows: ein Absturz, keine Absage.
CRASH_CODE: Final = 0xC0000005
#: Was der nachgestellte Installer zuletzt sagt.
INSTALL_OUTPUT: Final = "Installer exited with code 1603"


def _next_version(version: str) -> str:
    """Die Fassung nach dieser: die letzte Zahl um eins höher."""
    head, _dot, last = version.rpartition(".")
    digits = "".join(character for character in last if character.isdigit()) or "0"
    return f"{head}.{int(digits) + 1}" if head else str(int(digits) + 1)


def newer_release() -> None:
    """``update = neu``: Die Versionsdatei nennt die nächste Fassung.

    Ihre Punkte sind die der jüngsten Fassung aus ``changelog/`` in jeder
    Sprache — echte Kundentexte, keine Platzhalter, die der Sprachfall mäße.
    """
    from app.branding import APP_VERSION
    from app.core import changes, updates
    from app.i18n.catalog import available_languages

    languages = available_languages()
    source = changes.history(languages[0])[0].version
    release = updates.Release(
        version=_next_version(APP_VERSION),
        changes={language: changes.points_for(source, language) for language in languages},
        groups={language: changes.groups_for(source, language) for language in languages},
    )

    def check(url: str = updates.VERSION_URL, fetch: Any = None) -> Any:
        return release

    updates.check = check


def browser_refuses() -> None:
    """``browser = fehlt``: Kein Programm nimmt eine Adresse an (``openUrl`` sagt ``False``)."""
    from PySide6.QtGui import QDesktopServices

    QDesktopServices.openUrl = staticmethod(lambda url: False)  # type: ignore[method-assign]


def _forced_statuses(change: Callable[[Any], Any]) -> None:
    """Die Erhebung der Zusatzprogramme mit einer geänderten Zeile je Anforderung."""
    from app.core import install

    real = install.statuses

    def statuses() -> tuple[Any, ...]:
        return tuple(change(status) for status in real())

    install.statuses = statuses


def install_fails() -> None:
    """``installation = scheitert``: Die erste Zeile fehlt, und ihr Installer gibt auf.

    Die erste angezeigte Anforderung steht als fehlend und installierbar da;
    *Installieren* ruft ``install.install``, und das antwortet ohne Lauf mit
    dem Ende einer Installerausgabe — *Details anzeigen* zeigt sie.
    """
    from app.core import install

    first = install.shown()[0].id

    def absent(status: Any) -> Any:
        if status.requirement.id != first:
            return status
        return replace(status, present=False, installable=True, reason="", by_hand="")

    def failed(requirement: Any, progress: Any = None) -> Any:
        return install.InstallResult(
            requirement=requirement, installed=False, output=INSTALL_OUTPUT
        )

    _forced_statuses(absent)
    install.install = failed


def comfyui_installed() -> None:
    """``installation = comfyui_installiert``: ComfyUI steht als installiert in der Liste.

    Dann bietet seine Zeile den zweiten Schritt an (*ComfyUI einrichten …*,
    ``Requirement.follow_up``), der den Einrichtungsdialog öffnet.
    """
    from app.core import tools

    def present(status: Any) -> Any:
        if status.requirement.id != "comfyui":
            return status
        tool = tools.by_id("comfyui")
        address = tool.address() if tool is not None else ""
        return replace(status, present=True, location=address, address=address)

    _forced_statuses(present)


def slicer_crashes() -> None:
    """``slicerlauf = absturz``: Der Slicer stürzt beim Schneiden ab, ohne Druckdatei.

    Ersetzt wird nur der Lauf des Programms (``handover._run_slicer``); die
    Meldung samt *Ausgabe des Slicers zeigen* baut ``slice_model`` selbst.
    """
    from app.core.export import handover

    def crashed(command: Sequence[str], *arguments: Any, **named: Any) -> Any:
        return subprocess.CompletedProcess(
            args=list(command), returncode=CRASH_CODE, stdout=CRASH_OUTPUT, stderr=b""
        )

    handover._run_slicer = crashed


#: Farben der eingelegten Filamente, die :func:`slicer_spools_loaded` vorgibt — der
#: Slicer führt sie in seiner Anwendungskonfiguration, die ein Fallprofil nicht hat.
LOADED_COLOURS: Final = ("#f5f5f5", "#202020", "#d23c3c", "#2f6fd6")


def slicer_spools_loaded() -> None:
    """``slicerfilamente = eingelegt``: Im Slicer sind Filamente eingelegt.

    Welche Filamente im Slicer liegen, steht in seiner Anwendungskonfiguration
    im Nutzerordner; das Profil eines Falls hat keine. Die Naht nimmt die ersten
    Filamentprofile des eingerichteten Slicers (``slicer_filaments``, echte
    Namen und Typen) und gibt ihnen Farben — *Aus dem Slicer übernehmen* zeigt
    sie dann zur Auswahl.
    """
    from app.core.knowledge import filaments
    from app.ui import filament_inventory, filament_picker

    def configured(*, cancelled: Any = None) -> tuple[Any, ...]:
        profiles = filament_picker.slicer_filaments()[: len(LOADED_COLOURS)]
        return tuple(
            filaments.CatalogueFilament(entry.name, colour, entry.filament_type, entry.name)
            for entry, colour in zip(profiles, LOADED_COLOURS, strict=False)
        )

    filament_inventory.configured_spools = configured


def backup_beside_recent() -> None:
    """``sicherung = neben_projekt``: Neben dem zuletzt geöffneten Projekt liegt eine Sicherung.

    Wie nach einem Absturz: Die Anwendung schreibt sie beim Arbeiten
    (``project.write_autosave``) und fragt beim nächsten Öffnen, ob sie die
    Sicherung öffnet (``MainWindow._offer_recovery``). Das Projekt ist die Kopie
    im Fallordner (``function_setup.case_scene``), die Sicherung entsteht
    daneben, jünger als die Datei. Lehnt der Kunde ab, räumt die Anwendung sie
    selbst weg.
    """
    import shutil
    from pathlib import Path

    from app.core.scene.project import autosave_path
    from app.ui.settings import load_settings

    recent = load_settings().recent
    if not recent:
        raise RuntimeError("sicherung = neben_projekt: Das Profil nennt kein zuletzt geöffnetes")
    project = Path(recent[0])
    shutil.copyfile(project, autosave_path(project))


#: Wo das nachgestellte lokale Sprachmodell steht: dieser Rechner, ein Port, an dem
#: keiner antwortet (``discard``). Eine Anfrage scheitert dort sofort.
CLOSED_LOCAL_URL: Final = "http://127.0.0.1:9"


def local_chat_model() -> None:
    """``chatmodell = lokal``: Der Chat spricht mit einem lokalen Sprachmodell (Ollama).

    ``llm.first_available`` nennt Ollama auf diesem Rechner (:data:`CLOSED_LOCAL_URL`).
    Vor dem ersten Zug fragt der KI-Hinweis, ob die Anfrage dorthin geht
    (``ensure_ai_disclosure``); geht sie, scheitert sie mit der Meldung, die der
    Chat dafür hat. Kein Modell rechnet, nichts verlässt den Rechner.
    """
    from app.core.backends import llm

    def first_available() -> Any:
        return llm.OllamaBackend(url=CLOSED_LOCAL_URL)

    llm.first_available = first_available


def activation_request() -> None:
    """``aktivierung = anfrage``: Der Kaufcode im Feld gilt, und die Geräteanfrage entsteht.

    Einen echten Kaufcode gibt es ohne private Schlüssel nicht (Plan D0, B12);
    dass er auf die Freischaltung dieses Rechners wartet, setzt die Lizenz des
    Falls (``needs_activation``). Die Naht nimmt den Schlüssel im Feld ohne
    Prüfung an (``activation.remember``) und gibt eine Anfrage ohne Unterschrift
    zurück (``create_activation_request``). Kein Server sieht sie.
    """
    import json

    from app.core import activation

    def remember(text: str) -> Any:
        return activation.state()

    def create_activation_request(device_name: str) -> str:
        return json.dumps({"device": device_name}, ensure_ascii=False)

    activation.remember = remember
    activation.create_activation_request = create_activation_request


#: Kantenlänge des Würfels, den der nachgestellte Generator liefert (mm).
GENERATED_EDGE: Final = 20.0


def generator_answers() -> None:
    """``erzeugung = antwortet``: Der Generator ist bereit und liefert sofort einen Würfel.

    ComfyUI an seiner Adresse auf diesem Rechner, ohne dass es läuft: Die
    Bereitschaft ist „bereit“, und ein Wurf liefert ohne Anfrage einen Würfel
    als STL — einen Versuch, wie ein echter Lauf ihn brächte. Den KI-Hinweis vor
    dem ersten Wurf zeigt die Anwendung wie sonst. Nichts rechnet, nichts geht
    nach draußen.
    """
    import trimesh

    from app.core.backends import mesh
    from app.core.geom.mesh import MeshData
    from app.ui import generate_dialog

    def cube(backend: Any, prompt: str, seed: int) -> Any:
        body = trimesh.creation.box((GENERATED_EDGE,) * 3)
        payload = body.export(file_type="stl")
        return mesh.GeneratedMesh(
            MeshData.of(body), bytes(payload), ".stl", backend.id, prompt, seed
        )

    class Answering(mesh.ComfyBackend):
        """ComfyUI, das bereit ist und ohne Anfrage antwortet."""

        def readiness(self, workflow: str = "image_to_mesh") -> Any:
            return mesh.Readiness.READY

        def model_choices(self, workflow: str = "image_to_mesh") -> dict[str, tuple[str, ...]]:
            return {}

        def text_to_mesh(self, prompt: str, *, seed: int = 0, **_named: Any) -> Any:
            return cube(self, prompt, seed)

        def image_to_mesh(self, image: bytes, *, seed: int = 0, **_named: Any) -> Any:
            return cube(self, "", seed)

    generate_dialog.ComfyBackend = Answering  # type: ignore[misc]


#: Vorbedingung → Zustand → Naht. Die Zustände stehen gleich in
#: ``function_list.PRECONDITIONS``.
SEAMS: Final[dict[str, dict[str, Callable[[], None]]]] = {
    "update": {"neu": newer_release},
    "browser": {"fehlt": browser_refuses},
    "installation": {"scheitert": install_fails, "comfyui_installiert": comfyui_installed},
    "slicerlauf": {"absturz": slicer_crashes},
    "slicerfilamente": {"eingelegt": slicer_spools_loaded},
    "sicherung": {"neben_projekt": backup_beside_recent},
    "chatmodell": {"lokal": local_chat_model},
    "aktivierung": {"anfrage": activation_request},
    "erzeugung": {"antwortet": generator_answers},
}
