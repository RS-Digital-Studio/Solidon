"""Echte lokale KI-Aufrufe für Tutorialaufnahmen, mit Zeit- und Ergebnisbeleg.

Die Aufnahme bedient die vorhandenen Dialoge. Antworten, Netze und Fortschritt
kommen ausschließlich vom gewählten lokalen Backend; Wartezeiten werden beim
Schnitt verkürzt und im Sprechertext ausdrücklich als solche benannt.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from tools.workshop_inventory_capture import _click, _frame, _type


def _proof(tutorial: Any, entry: dict[str, Any]) -> None:
    """Jeden abgeschlossenen Schritt neben seinen Rohbildern belegen."""
    path = tutorial.folder / "ai-evidence.json"
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    entries.append(
        {
            "run_id": tutorial._ai_run_id,
            "run_started_at": tutorial._ai_run_started_at,
            "first_slide": tutorial._ai_step_start,
            "last_slide": len(tutorial.recorder.slides),
            **entry,
        }
    )
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _scene(
    tutorial: Any,
    key: str,
    de: tuple[str, str, str],
    en: tuple[str, str, str],
    *,
    seconds: float = 10.0,
    dialog: Any = None,
    target: Any = None,
    short_voice: tuple[str, str] | None = None,
    first_slide: int | None = None,
    action: Any = None,
) -> None:
    """Jeden lesbaren Bedienzustand als eigenständige Schnittszene festhalten."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QImageReader

    from app.i18n import get_language

    start = len(tutorial.recorder.slides) if first_slide is None else first_slide
    tutorial.add(
        de[0],
        en[0],
        de[1],
        en[1],
        min(4.0, seconds) if action else seconds,
        dialog=dialog,
        target=target,
    )
    action_first = len(tutorial.recorder.slides)
    if action:
        action()
        action_last = len(tutorial.recorder.slides)
        tutorial.add(de[0], en[0], de[1], en[1], max(6.0, seconds - 4.0), dialog=dialog)
    else:
        action_last = action_first
    text = de if get_language() == "de" else en
    frame_size = QImageReader(str(tutorial.recorder.slides[-1].path)).size()
    crop = [0, 0, frame_size.width(), frame_size.height()]
    if dialog is not None:
        point = dialog.mapToGlobal(QPoint(0, 0)) - tutorial.window.mapToGlobal(QPoint(0, 0))
        scale_x = frame_size.width() / tutorial.window.width()
        scale_y = frame_size.height() / tutorial.window.height()
        crop = [
            round(point.x() * scale_x),
            round(point.y() * scale_y),
            round(dialog.width() * scale_x),
            round(dialog.height() * scale_y),
        ]
        if (
            min(crop) < 0
            or crop[0] + crop[2] > frame_size.width()
            or crop[1] + crop[3] > frame_size.height()
        ):
            raise RuntimeError("KI-Dialog liegt außerhalb der Aufnahme; Fensterposition prüfen.")
    tutorial._ai_scenes.append(
        {
            "key": key,
            "action": "ai",
            "title": text[0],
            "detail": text[1],
            "voice": text[2],
            "short_voice": (short_voice[0 if get_language() == "de" else 1] if short_voice else ""),
            "first_slide": start,
            "last_slide": len(tutorial.recorder.slides),
            "short": short_voice is not None,
            "minimum_seconds": seconds,
            "action_first_slide": action_first,
            "action_last_slide": action_last,
            "model_crop": crop,
            "focus": None,
        }
    )


def _caption(tutorial: Any, step: dict[str, Any], *, dialog: Any = None) -> None:
    _scene(
        tutorial,
        step["key"],
        tuple(step["de"][field] for field in ("title", "detail", "voice")),
        tuple(step["en"][field] for field in ("title", "detail", "voice")),
        dialog=dialog,
        seconds=max(10.0, float(step.get("minimum_seconds", 0))),
    )


def _wait(tutorial: Any, predicate: Any, *, timeout: float, reason: str) -> None:
    """Qt weiter bedienen, bis die wirkliche Rückmeldung vorliegt."""
    from PySide6.QtTest import QTest

    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise RuntimeError(f"{reason}: Zeitlimit erreicht; Aufnahme und Backend prüfen.")
        QTest.qWait(80)


class _LocalNotice:
    """Den echten KI-Hinweis lesen; unerwartete Rückfragen halten die Aufnahme an."""

    def __init__(self, tutorial: Any, backend: str, key: str, owner: Any = None) -> None:
        from PySide6.QtCore import QTimer

        self.tutorial = tutorial
        self.backend = backend
        self.owner = owner
        self.key = key
        self.error: RuntimeError | None = None
        self.seen: set[int] = set()
        self.timer = QTimer(tutorial.window)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.visit)

    def visit(self) -> None:
        from PySide6.QtWidgets import QApplication, QDialog, QLabel

        from app.ui.ai_disclosure import AiDisclosureDialog

        dialog = QApplication.activeModalWidget()
        if dialog is None or dialog is self.owner or id(dialog) in self.seen:
            return
        if isinstance(dialog, AiDisclosureDialog):
            target = dialog.target
            if target.backend != self.backend or target.target_class != "local":
                self.error = RuntimeError("KI-Ziel ist nicht das gewählte lokale Backend.")
                self.seen.add(id(dialog))
                dialog.reject()
                return
            self.seen.add(id(dialog))
            try:
                dialog.setMinimumSize(960, 850)
                self.tutorial.settle(15)
                bar = dialog.scroll_area.verticalScrollBar()
                bar.setValue(bar.minimum())
                self.tutorial.settle(10)
                notice_text = "\n".join(
                    [dialog.heading.text(), dialog.general_text.text(), dialog.provider_text.text()]
                )
                duration = max(10.0, math.ceil(len(notice_text.split()) / 3))
                positions = [0]
                while positions[-1] < bar.maximum():
                    positions.append(
                        min(
                            bar.maximum(),
                            positions[-1] + dialog.scroll_area.viewport().height() - 80,
                        )
                    )
                for index, position in enumerate(positions, 1):
                    bar.setValue(position)
                    self.tutorial.settle(10)
                    _scene(
                        self.tutorial,
                        f"{self.key}-notice-{index}",
                        (
                            "Den lokalen KI-Hinweis lesen",
                            "Datenweg und Grenzen vor dem Start prüfen.",
                            "Vor dem ersten Modellaufruf lese ich den Hinweis. Hier stehen das "
                            "lokale Ziel, die übertragenen Arbeitsdaten und die Grenzen der KI. "
                            "Ich prüfe die Adresse und bestätige erst danach. Auch ein lokales "
                            "Ergebnis kann Fehler enthalten.",
                        ),
                        (
                            "Read the local AI notice",
                            "Check the destination and limitations before starting.",
                            "Before the first model call, I read this notice. It identifies the "
                            "local destination, the work data sent there and the limitations of "
                            "AI. I check the address before continuing. A local result can still "
                            "contain errors.",
                        ),
                        seconds=max(10.0, duration / len(positions)),
                        dialog=dialog,
                    )
                _proof(
                    self.tutorial,
                    {
                        "kind": "local_notice",
                        "backend": target.backend,
                        "address": target.address,
                        "text": notice_text,
                        "words": len(notice_text.split()),
                        "minimum_seconds": duration,
                        "pages": len(positions),
                    },
                )
                if not dialog.continue_button.isEnabled():
                    raise RuntimeError("Der KI-Hinweis ist noch nicht vollständig bereit.")
                _scene(
                    self.tutorial,
                    f"{self.key}-notice-continue",
                    (
                        "Die lokale Anfrage starten",
                        "KI-Anfrage fortsetzen",
                        "Ich bestätige mit „KI-Anfrage fortsetzen“.",
                    ),
                    (
                        "Start the local request",
                        "Continue AI request",
                        "Click Continue AI request.",
                    ),
                    seconds=4.0,
                    dialog=dialog,
                    target=dialog.continue_button,
                )
                continue_scene = self.tutorial._ai_scenes[-1]
                continue_scene["action_first_slide"] = len(self.tutorial.recorder.slides)
                _click(self.tutorial, dialog.continue_button, dialog=dialog)
                continue_scene["action_last_slide"] = len(self.tutorial.recorder.slides)
                continue_scene["last_slide"] = len(self.tutorial.recorder.slides)
            except Exception as error:
                self.error = RuntimeError(f"KI-Hinweis konnte nicht aufgenommen werden: {error}")
                dialog.reject()
            return
        self.seen.add(id(dialog))
        message = "\n".join(label.text() for label in dialog.findChildren(QLabel))
        _proof(
            self.tutorial,
            {"kind": "unexpected_dialog", "title": dialog.windowTitle(), "text": message},
        )
        self.tutorial.add(
            "Rückfrage prüfen", "Inspect the question", message, message, 5.0, dialog=dialog
        )
        self.error = RuntimeError(f"Unerwartete Rückfrage: {dialog.windowTitle()}: {message}")
        if isinstance(dialog, QDialog):
            dialog.reject()

    def __enter__(self) -> _LocalNotice:
        self.timer.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.timer.stop()
        self.timer.deleteLater()
        if self.error is not None:
            raise self.error


def _ollama_setup(tutorial: Any, step: dict[str, Any]) -> None:
    """Den bereits eingerichteten lokalen Zugang in der echten Chatansicht prüfen."""
    from app.core.backends.llm import ollama_endpoint

    _wait(
        tutorial,
        lambda: tutorial.session.backend_known,
        timeout=40,
        reason="Chat-Zielprüfung",
    )
    backend = tutorial.session.agent_backend
    model = step["model"]
    if (
        backend is None
        or backend.id != "ollama"
        or backend.model != model
        or ollama_endpoint(backend.url)
        not in ("http://127.0.0.1:11434/api/chat", "http://localhost:11434/api/chat")
    ):
        raise RuntimeError(
            "Der vorhandene Chat-Zugang ist nicht das gewählte lokale Ollama-Modell."
        )
    tutorial.window._focus_chat()
    from PySide6.QtTest import QTest

    QTest.qWait(500)
    tutorial.settle(15)
    if not tutorial.window.chat.hint.isVisible() or model not in tutorial.window.chat.hint.text():
        raise RuntimeError("Die lokale Modellanzeige ist noch nicht sichtbar.")
    _caption(tutorial, step)
    _proof(
        tutorial,
        {"kind": "ollama_setup", "model": model, "url": backend.url, "setup_preexists": True},
    )


def _ollama_chat(tutorial: Any, step: dict[str, Any]) -> None:
    from app.core.backends.llm import ollama_endpoint
    from app.i18n import get_language

    window = tutorial.window
    backend = tutorial.session.agent_backend
    if (
        backend is None
        or backend.id != "ollama"
        or ollama_endpoint(backend.url)
        not in ("http://127.0.0.1:11434/api/chat", "http://localhost:11434/api/chat")
    ):
        raise RuntimeError("Live-Aufnahme verlangt das geprüfte lokale Ollama-Ziel.")
    language = get_language()
    prompt = step[language]["prompt"]
    window._focus_chat()
    tutorial.settle(12)
    _scene(
        tutorial,
        f"{step['key']}-prompt",
        (
            "Den Auftrag konkret formulieren",
            "Überhangfächer aus der Bausteinbibliothek.",
            "Ich bitte den lokalen Assistenten, einen Überhangfächer aus der "
            "Bausteinbibliothek mit den Standardwerten anzulegen. Das ist ein "
            "konkreter Auftrag mit einem prüfbaren Ergebnis.",
        ),
        (
            "Write a specific request",
            "An overhang fan from the parts library.",
            "I ask the local assistant to create an overhang fan from the parts "
            "library using its default values. This is a specific request with a "
            "result I can check.",
        ),
        short_voice=(
            "Ein konkreter Auftrag an das lokale Ollama: einen Überhangfächer anlegen.",
            "A specific request to local Ollama: create an overhang fan.",
        ),
        target=window.chat.input,
        action=lambda: _type(tutorial, window.chat.input, prompt, commit=False, frame_stride=8),
    )
    if window.chat.input.toPlainText() != prompt:
        raise RuntimeError("Der sichtbare Chat-Auftrag stimmt nicht mit dem Rezept überein.")
    if not window.chat.send.isEnabled():
        raise RuntimeError("Chat ist nicht sendebereit; sichtbaren Hinweis prüfen.")
    before = len(tutorial.session.project.document.ops)
    started = time.monotonic()
    updates: list[dict[str, Any]] = []
    with _LocalNotice(tutorial, "ollama", step["key"]) as notice:
        _click(tutorial, window.chat.send)
        _wait(
            tutorial,
            lambda: window.chat.busy or notice.error is not None or window._proposal is not None,
            timeout=15,
            reason="Chat-Start",
        )
        wait_start = len(tutorial.recorder.slides)
        while window.chat.busy and notice.error is None:
            if time.monotonic() - started > 900:
                tutorial.session.cancel_agent()
                raise RuntimeError("Ollama überschreitet 15 Minuten; Backend und Aufnahme prüfen.")
            tutorial.settle(12)
            elapsed = time.monotonic() - started
            if not updates or elapsed - updates[-1]["elapsed_seconds"] >= 20:
                updates.append({"elapsed_seconds": round(elapsed, 3)})
                tutorial.add(
                    "Ollama arbeitet · Wartezeit im Schnitt verkürzt",
                    "Ollama is working · waiting shortened in the edit",
                    "Die Antwort entsteht jetzt auf diesem Rechner.",
                    "The response is being generated on this computer.",
                    2.0,
                )
                print(f"Ollama arbeitet seit {elapsed:.0f} Sekunden", flush=True)
        tutorial.settle(20)
        _scene(
            tutorial,
            f"{step['key']}-waiting",
            (
                "Ollama arbeitet lokal",
                "Die echte Wartezeit ist im Schnitt verkürzt.",
                "Ollama verarbeitet den Auftrag auf diesem Rechner. Die Wartezeit ist "
                "im Film verkürzt. Ob daraus ein brauchbarer Vorschlag entsteht, prüfe "
                "ich an der Rückmeldung und am Modell.",
            ),
            (
                "Ollama is working locally",
                "The real waiting time is shortened in the edit.",
                "Ollama processes the request on this computer. The video shortens the "
                "waiting time. I check the response and the model to see whether the "
                "proposal is useful.",
            ),
            seconds=5.0,
            first_slide=wait_start,
        )
        if window._proposal is not None:
            _scene(
                tutorial,
                f"{step['key']}-proposal",
                (
                    "Den Vorschlag vor dem Übernehmen prüfen",
                    "Auftrag, Vorschau und Befunde vergleichen.",
                    "Hier steht der tatsächliche Vorschlag des Assistenten. Ich "
                    "vergleiche ihn mit meinem Auftrag und prüfe die Vorschau und die "
                    "angezeigten Befunde. Erst dann übernehme ich ihn.",
                ),
                (
                    "Inspect the proposal before applying it",
                    "Compare the request, preview and findings.",
                    "This is the assistant's actual proposal. I compare it with my "
                    "request and inspect the preview and the reported findings before "
                    "applying it.",
                ),
            )
            if not window.chat.accept_button.isEnabled():
                raise RuntimeError("KI-Vorschlag ist nicht übernehmbar; Befunde prüfen.")
            _click(tutorial, window.chat.accept_button)
    elapsed = time.monotonic() - started
    after = len(tutorial.session.project.document.ops)
    if after <= before:
        _proof(
            tutorial,
            {
                "kind": "ollama_no_operations",
                "model": backend.model,
                "prompt": prompt,
                "operations_before": before,
                "operations_after": after,
                "total_workflow_seconds": round(elapsed, 3),
            },
        )
        raise RuntimeError("Der echte Ollama-Zug hat keine Geometrieänderung geliefert.")
    added = tutorial.session.project.document.ops[before:]
    expected = step.get("expected_operation")
    if expected and (len(added) != 1 or added[0].op != expected):
        _proof(
            tutorial,
            {
                "kind": "ollama_unexpected_operations",
                "model": backend.model,
                "prompt": prompt,
                "expected_operation": expected,
                "actual_operations": [operation.op for operation in added],
                "total_workflow_seconds": round(elapsed, 3),
            },
        )
        raise RuntimeError(
            "Der KI-Auftrag erzeugte andere Schritte als beauftragt; Ergebnis prüfen."
        )
    tutorial.checked("Echter Ollama-Vorschlag übernommen")
    _scene(
        tutorial,
        f"{step['key']}-applied",
        (
            "Den tatsächlichen Modellzustand prüfen",
            "Die neue Geometrie ist im Verlauf angekommen.",
            "Der Vorschlag ist jetzt im Projekt angekommen. Ich kontrolliere die "
            "entstandene Geometrie und die neuen Schritte im Verlauf. Die folgenden "
            "Ansichten zeigen genau dieses Ergebnis.",
        ),
        (
            "Check the actual model state",
            "The new geometry is part of the editing history.",
            "The proposal is now part of the project. I inspect the resulting geometry "
            "and the new steps in the history. The following views show this actual "
            "result.",
        ),
    )
    _proof(
        tutorial,
        {
            "kind": "ollama_chat",
            "model": backend.model,
            "url": backend.url,
            "prompt": prompt,
            "total_workflow_seconds": round(elapsed, 3),
            "waiting_shortened": True,
            "operations_before": before,
            "operations_after": len(tutorial.session.project.document.ops),
            "progress": updates,
        },
    )


def _open_generator(tutorial: Any, key: str) -> None:
    """Den wirklichen Menüweg vor dem Erzeugen-Dialog zeigen und anklicken."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.i18n import get_language

    action = tutorial.window.generate_action
    menus = [menu for menu in tutorial.window._menus if action in menu.actions()]
    if len(menus) != 1 or not action.isEnabled():
        raise RuntimeError("Modell erzeugen ist nicht über den erwarteten Menüweg erreichbar.")
    menu = menus[0]
    bar = tutorial.window.menuBar()
    first = len(tutorial.recorder.slides)
    tutorial.add(
        "Datei → Modell erzeugen",
        "File → Generate model",
        "Den Erzeugen-Dialog öffnen.",
        "Open the generation dialog.",
        4.0,
        target=bar.mapToGlobal(bar.actionGeometry(menu.menuAction()).center()),
    )
    QTest.mouseClick(
        bar,
        Qt.MouseButton.LeftButton,
        pos=bar.actionGeometry(menu.menuAction()).center(),
        delay=100,
    )
    QTest.qWait(350)
    if not menu.isVisible():
        raise RuntimeError("Das echte Datei-Menü ist nicht sichtbar.")
    point = menu.actionGeometry(action).center()
    QTest.mouseMove(menu, point, 100)
    _frame(tutorial, seconds=6.0, overlays=(menu,))
    text = (
        (
            "Datei → Modell erzeugen",
            "Den Erzeugen-Dialog öffnen.",
            "Im Menü Datei wähle ich Modell erzeugen.",
        )
        if get_language() == "de"
        else (
            "File → Generate model",
            "Open the generation dialog.",
            "In the File menu, I choose Generate model.",
        )
    )
    tutorial._ai_scenes.append(
        {
            "key": f"{key}-menu",
            "action": "ai",
            "title": text[0],
            "detail": text[1],
            "voice": text[2],
            "short_voice": "",
            "short": False,
            "minimum_seconds": 10.0,
            "first_slide": first,
            "last_slide": len(tutorial.recorder.slides),
            "model_crop": [0, 0, *tutorial.recorder.frame_size],
            "focus": None,
        }
    )
    QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=point, delay=100)


def _comfy_generate(tutorial: Any, step: dict[str, Any]) -> None:
    from PySide6.QtWidgets import QDialogButtonBox, QToolButton

    from app.core.backends.mesh import ComfyBackend, Readiness
    from app.i18n import get_language
    from app.ui.generate_dialog import GenerateDialog

    phase = step["phase"]
    key = step["key"]
    evidence: dict[str, Any] = {
        "kind": phase,
        "seed": step["seed"],
        "waiting_shortened": True,
    }

    def fill(dialog: Any) -> None:
        if not isinstance(dialog, GenerateDialog):
            raise RuntimeError("Erzeugen-Dialog fehlt; Aufnahme prüfen.")
        if not isinstance(dialog.backend, ComfyBackend) or dialog.backend.base not in (
            "http://127.0.0.1:8188",
            "http://localhost:8188",
        ):
            raise RuntimeError("ComfyUI zeigt nicht auf den freigegebenen lokalen Dienst.")
        dialog.setMinimumSize(960, 850)
        tutorial.settle(12)
        _scene(
            tutorial,
            f"{key}-open",
            (
                "Modell erzeugen öffnen",
                "ComfyUI ist auf diesem Rechner eingerichtet.",
                "Ich öffne Modell erzeugen. ComfyUI und die benötigten Modelle sind "
                "auf diesem Rechner bereits eingerichtet. Der Dialog zeigt die "
                "Beschreibung, die Bildauswahl und den Bereitschaftshinweis.",
            ),
            (
                "Open model generation",
                "ComfyUI is configured on this computer.",
                "I open model generation. ComfyUI and the required models are already "
                "configured on this computer. The dialog shows the description, the "
                "image selector and its readiness status.",
            ),
            dialog=dialog,
        )
        if phase == "image":
            image = Path(step["image"]).resolve()
            if not image.is_file():
                raise RuntimeError("Bildvorlage fehlt; Rezept prüfen.")
            image_sha = hashlib.sha256(image.read_bytes()).hexdigest()
            _scene(
                tutorial,
                f"{key}-reference",
                (
                    "Bildvorlage",
                    "Die tatsächliche Eulenbildvorlage für diesen Lauf.",
                    "Dieses Eulenbild ist meine Vorlage. Daraus lasse ich gleich eine "
                    "Form erzeugen.",
                ),
                (
                    "Reference image",
                    "The actual owl image used for this run.",
                    "This owl image is my reference. I will use it to generate a shape.",
                ),
                seconds=7.0,
                dialog=dialog,
                short_voice=(
                    "Aus diesem Eulenbild lasse ich ein Modell erzeugen.",
                    "I use this owl image to generate a model.",
                ),
            )
            tutorial._ai_scenes[-1]["reference_image"] = {
                "path": str(image),
                "sha256": image_sha,
                "labels": {"de": "Bildvorlage", "en": "Reference image"},
            }
            tutorial.file_dialog(lambda: _click(tutorial, dialog.picture, dialog=dialog), image)
            file_scene = dict(tutorial._file_capture)
            text = (
                (
                    "Die Eulenbildvorlage auswählen",
                    "Eine neu erstellte, eigene Bildvorlage.",
                    "Ich wähle die neu erstellte Eulenbildvorlage aus. Eine einzelne, "
                    "vollständig sichtbare Figur vor einfachem Hintergrund macht die "
                    "beabsichtigte Form deutlich.",
                )
                if get_language() == "de"
                else (
                    "Choose the owl reference image",
                    "A newly created original reference image.",
                    "I choose the newly created owl reference image. A single, fully "
                    "visible figure against a simple background makes the intended "
                    "shape clear.",
                )
            )
            tutorial._ai_scenes.append(
                {
                    **file_scene,
                    "key": f"{key}-file",
                    "action": "ai",
                    "title": text[0],
                    "detail": text[1],
                    "voice": text[2],
                    "short_voice": "",
                    "short": False,
                    "minimum_seconds": 10.0,
                    "focus": None,
                }
            )
            evidence.update(
                {
                    "image": str(image),
                    "image_sha256": image_sha,
                }
            )
        else:
            prompt = step[get_language()]["prompt"]
            _scene(
                tutorial,
                f"{key}-description",
                (
                    "Die Drachenfigur beschreiben",
                    "Sitzend, kompakt, mit angelegten Flügeln.",
                    "Für den zweiten Weg beschreibe ich eine sitzende Drachenfigur. "
                    "Der Text nennt die kompakte Körperform, breite Füße und eng "
                    "angelegte Flügel. Ich verwende hier eine englische Beschreibung. "
                    "Das formuliert meine Absicht, garantiert aber keine bestimmte "
                    "Geometrie.",
                ),
                (
                    "Describe the dragon figure",
                    "Seated, compact, with folded wings.",
                    "For the second route, I describe a seated dragon. The prompt "
                    "specifies a compact body, broad feet and closely folded wings. I "
                    "use an English description here. It describes my intention but "
                    "does not guarantee a particular geometry.",
                ),
                dialog=dialog,
                target=dialog.prompt,
                action=lambda: _type(
                    tutorial, dialog.prompt, prompt, dialog=dialog, frame_stride=12
                ),
                short_voice=(
                    "Für den zweiten Weg beschreibe ich einen sitzenden Drachen.",
                    "For the second route, I describe a seated dragon.",
                ),
            )
            if dialog.prompt.text() != prompt:
                raise RuntimeError(
                    "Die sichtbare Beschreibung stimmt nicht mit dem Rezept überein."
                )
            from PySide6.QtCore import Qt
            from PySide6.QtTest import QTest

            # Ein echtes Home zeigt den Anfang des langen Auftrags, ohne Text nachzuzeichnen.
            _click(tutorial, dialog.prompt, dialog=dialog)
            QTest.keyClick(dialog.prompt, Qt.Key.Key_Home)
            tutorial.settle(8)
            _frame(tutorial, dialog=dialog, seconds=5.0)
            description_scene = tutorial._ai_scenes[-1]
            description_scene["action_last_slide"] = len(tutorial.recorder.slides) - 1
            description_scene["last_slide"] = len(tutorial.recorder.slides)
            evidence["prompt"] = dialog.prompt.text()
        _wait(
            tutorial,
            lambda: dialog.readiness is not None,
            timeout=45.0,
            reason="Bereitschaft des sichtbaren Generatorwegs",
        )
        if dialog.readiness != Readiness.READY:
            raise RuntimeError(f"Generator nicht bereit: {dialog.state.text()}")
        heading = dialog.advanced.findChild(QToolButton, "sectionHeading")
        if heading is None:
            raise RuntimeError("Weitere Einstellungen fehlen; Erzeugen-Dialog prüfen.")
        if not heading.isChecked():
            _scene(
                tutorial,
                f"{key}-advanced",
                (
                    "Weitere Einstellungen öffnen",
                    "Den Startwert für diesen Lauf festlegen.",
                    "Ich öffne Weitere Einstellungen. Hier kann ich den Startwert eintragen.",
                ),
                (
                    "Open additional settings",
                    "Set the seed for this run.",
                    "I open the additional settings. This is where I can enter the seed.",
                ),
                dialog=dialog,
                target=heading,
                action=lambda: _click(tutorial, heading, dialog=dialog),
            )
        tutorial.settle(12)
        evidence["models"] = {
            role: field.currentText() for role, field in dialog._model_fields.items()
        }
        _scene(
            tutorial,
            f"{key}-settings",
            (
                "Bereitschaft und Startwert prüfen",
                f"Startwert: {step['seed']}",
                "Der Dialog meldet, dass dieser Erzeugungsweg bereit ist. Ich trage "
                "den Startwert ein. Mit diesem Wert und meiner Eingabe lässt sich "
                "der Lauf später zuordnen. Für das gleiche Ergebnis müssten außerdem "
                "die verwendeten Modelle und Programme übereinstimmen.",
            ),
            (
                "Check readiness and seed",
                f"Seed: {step['seed']}",
                "The dialog says this generation route is ready. I enter the seed. "
                "Together with my input, this value identifies the run. Matching the "
                "result would also require the same models and software.",
            ),
            dialog=dialog,
            target=dialog.seed,
            action=lambda: _type(tutorial, dialog.seed, str(step["seed"]), dialog=dialog),
        )
        if dialog.seed.value() != int(step["seed"]):
            raise RuntimeError("Der eingetragene Startwert wurde nicht übernommen.")
        button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if not button.isEnabled():
            raise RuntimeError(f"Erzeugen bleibt gesperrt: {dialog.state.text()}")
        started = time.monotonic()
        progress: list[dict[str, Any]] = []
        with _LocalNotice(tutorial, "comfyui", key, owner=dialog) as notice:
            _scene(
                tutorial,
                f"{key}-start",
                (
                    "Die lokale Erzeugung starten",
                    "Bereit → Erzeugen",
                    "Der Dialog meldet „Bereit“. Ich klicke auf „Erzeugen“.",
                ),
                (
                    "Start local generation",
                    "Ready → Generate",
                    "The dialog reports Ready. Click Generate.",
                ),
                seconds=4.0,
                dialog=dialog,
                target=button,
            )
            start_scene = tutorial._ai_scenes[-1]
            start_click = len(tutorial.recorder.slides)
            _click(tutorial, button, dialog=dialog)
            # Der Klick kann den eigenen Hinweisdialog öffnen. Dessen Rohbilder
            # gehören zu seinen Leseszenen, nicht zur Erzeugen-Taste.
            start_scene.update(
                action_first_slide=start_click,
                action_last_slide=start_click + 1,
                last_slide=start_click + 1,
            )
            wait_start = len(tutorial.recorder.slides)
            while dialog._busy and notice.error is None:
                if time.monotonic() - started > 1800:
                    dialog.reject()
                    raise RuntimeError("ComfyUI überschreitet 30 Minuten; Backend prüfen.")
                tutorial.settle(12)
                elapsed = time.monotonic() - started
                if not progress or elapsed - progress[-1]["elapsed_seconds"] >= 30:
                    # Der Dialog tritt während des Laufs zur Seite (RM-371); der
                    # Lauf steht in der Statusleiste des bedienbaren Fensters.
                    status = tutorial.window.status_message.text()
                    progress.append({"elapsed_seconds": round(elapsed, 3), "text": status})
                    tutorial.add(
                        "ComfyUI rechnet · Wartezeit im Schnitt verkürzt",
                        "ComfyUI is generating · waiting shortened in the edit",
                        status,
                        status,
                        2.0,
                    )
                    print(f"ComfyUI {phase}: {elapsed:.0f}s {status}", flush=True)
            _scene(
                tutorial,
                f"{key}-waiting",
                (
                    "Die lokale Erzeugung abwarten",
                    "Wartezeit im Film verkürzt.",
                    "Die Berechnung läuft jetzt in ComfyUI auf diesem Rechner. "
                    "Fortschritt und Abbrechen stehen unten in der Statusleiste, und "
                    "Solidon bleibt währenddessen bedienbar. Ich lasse die Berechnung "
                    "bis zur tatsächlichen Rückmeldung laufen. Die Wartezeit "
                    "ist im Film verkürzt; daraus lässt sich keine feste "
                    "Geschwindigkeit für andere Rechner ableiten.",
                ),
                (
                    "Wait for local generation",
                    "Waiting time is shortened in the video.",
                    "ComfyUI is now calculating on this computer. Progress and Cancel "
                    "are in the status bar at the bottom, and Solidon stays usable "
                    "meanwhile. I wait for its actual response. The video shortens the "
                    "waiting time; it does not "
                    "establish a fixed speed for other computers.",
                ),
                seconds=5.0,
                first_slide=wait_start,
            )
        if dialog.result_mesh is None or not dialog.tries:
            _proof(tutorial, {**evidence, "status": "failed", "message": dialog.state.text()})
            raise RuntimeError(f"ComfyUI lieferte kein Modell: {dialog.state.text()}")
        result = dialog.result_mesh
        payload = tutorial.folder / f"generated-{phase}{result.suffix}"
        payload.write_bytes(result.payload)
        evidence.update(
            {
                "total_workflow_seconds": round(time.monotonic() - started, 3),
                "payload": payload.name,
                "payload_sha256": hashlib.sha256(result.payload).hexdigest(),
                "triangles": result.mesh.triangle_count,
                "watertight": result.mesh.is_watertight,
                "backend": result.backend,
                "progress": progress,
            }
        )
        _scene(
            tutorial,
            f"{key}-generated",
            (
                "Die wirkliche Rückmeldung lesen",
                "Das erzeugte Modell ins Projekt übernehmen.",
                "Der Generator hat ein Modell zurückgegeben. Ich lese die Rückmeldung "
                "und übernehme dieses Ergebnis ins Projekt. Danach prüfe ich es von "
                "mehreren Seiten. Eine erfolgreiche Erzeugung ist noch kein "
                "Drucknachweis.",
            ),
            (
                "Read the actual result message",
                "Add the generated model to the project.",
                "The generator has returned a model. I read the result message and add "
                "this result to the project. I then inspect it from several sides. "
                "Successful generation is not proof of printability.",
            ),
            dialog=dialog,
        )
        generated_scene = tutorial._ai_scenes[-1]
        generated_scene["action_first_slide"] = len(tutorial.recorder.slides)
        _click(tutorial, button, dialog=dialog)
        generated_scene["action_last_slide"] = len(tutorial.recorder.slides)
        generated_scene["last_slide"] = len(tutorial.recorder.slides)

    # Der Dialog ist nichtmodal (RM-371): Der Menüweg öffnet ihn und kehrt
    # zurück, statt in einer eigenen Ereignisschleife zu warten.
    _open_generator(tutorial, key)
    _wait(
        tutorial,
        lambda: tutorial.window._generator is not None,
        timeout=60.0,
        reason="Erzeugen-Dialog",
    )
    generator = tutorial.window._generator
    try:
        fill(generator)
    except BaseException:
        if generator is not None:
            generator.reject()
        raise
    tutorial.checked(f"Echte ComfyUI-Erzeugung: {phase}")
    _proof(tutorial, evidence)


def capture_step(tutorial: Any, step: dict[str, Any]) -> list[dict[str, Any]]:
    """Einen ausdrücklich benannten Aufnahmeweg aufrufen."""
    if not hasattr(tutorial, "_ai_run_id"):
        tutorial._ai_run_id = str(uuid4())
        tutorial._ai_run_started_at = datetime.now(UTC).isoformat()
    tutorial._ai_step_start = len(tutorial.recorder.slides)
    tutorial._ai_scenes = []
    phase = (step["kind"], step["phase"])
    if phase == ("ollama", "setup"):
        _ollama_setup(tutorial, step)
    elif phase == ("ollama", "chat"):
        _ollama_chat(tutorial, step)
    elif phase in (("comfyui", "image"), ("comfyui", "text")):
        _comfy_generate(tutorial, step)
    else:
        raise ValueError(f"Unbekannter KI-Aufnahmeschritt: {phase}")
    return list(tutorial._ai_scenes)


def finalize_evidence(tutorial: Any) -> None:
    """Den Lauf an die wirklich gespeicherten Projekte und Rohaufnahmen binden."""
    if not hasattr(tutorial, "_ai_run_id"):
        return
    files = [*tutorial.folder.glob("*.p3d"), *tutorial.folder.glob("*.stl")]
    capture = tutorial.folder / "capture.json"
    if not files or not capture.is_file():
        raise RuntimeError("KI-Lauf ohne gespeicherten Projekt-/Aufnahmebeleg; Abschluss prüfen.")
    files.append(capture)
    _proof(
        tutorial,
        {
            "kind": "finished_capture",
            "files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
        },
    )
