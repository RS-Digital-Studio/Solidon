"""Was ein Modell braucht und ob dieser Rechner es hat — vor dem Laden gesagt (RM-564).

Entscheidung Robert (08.10.2026): Bevor Solidon etwas herunterlädt, nennt es die
Voraussetzungen — Grafikspeicher (auf dem Mac den Anteil des gemeinsamen
Speichers), Platz auf dem Datenträger, ob eine Grafikkarte nötig ist — und ob
dieser Rechner sie erfüllt. Fehlt etwas, steht der Ausweg daneben: ein
kleineres Modell oder ein eigener Schlüssel. Eine Messung auf einem Mac gibt es
nicht; was für den Mac gesagt wird, ist gerechnet und heißt so.

**Eine Quelle.** Die Zahlen kommen aus den gemessenen Tabellen
(``llm.OLLAMA_SUGGESTIONS``, ``llm.OLLAMA_MEMORY_GB``, ``comfy_setup``), die
Lage des Rechners aus ``machine.this_machine()``; *Chat einrichten*, *ComfyUI
einrichten* und die Chatleiste lesen hier und rechnen nicht selbst.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Final

from app.core.backends import comfy_setup, llm
from app.core.backends import machine as _machine
from app.core.backends.machine import Machine
from app.core.log import get_logger
from app.i18n import _, format_decimal

_log = get_logger(__name__)

#: Wo der Linux-Dienst von Ollama seine Umgebung herbekommt — gelesen, nie
#: ausgeführt. Das Installationsskript legt die Unit hier an.
_SYSTEMD_UNITS: Final = (
    Path("/etc/systemd/system/ollama.service"),
    Path("/etc/systemd/system/ollama.service.d"),
)

#: Das Zuhause des Linux-Dienstes; seine Modelle liegen darunter.
_SERVICE_HOME: Final = Path("/usr/share/ollama")

_MODELS_SETTING: Final = re.compile(r"OLLAMA_MODELS=([^\"\s]+)")


def ollama_models_folder() -> Path | None:
    """Wo Ollama seine Modelle ablegt — wie Ollama selbst, sonst ``None``.

    ``OLLAMA_MODELS`` aus der eigenen Umgebung, unter Linux aus der
    systemd-Unit des Dienstes (dort setzt man es, wer die Modelle auf eine
    andere Platte legt), sonst das Zuhause des Dienstes oder ``~/.ollama``.
    Gibt es weder den Ordner noch seinen ``.ollama``-Ordner, ist der Ort
    unbekannt, und geraten wird nicht (Review K, M5).

    **Im eigenen Flatpak ist er unbekannt** (Nachprüfung K, N3): Umgebung, Unit
    und Dienstordner wären die des Sandkastens, und Ollama läuft auf dem
    Rechner. Der Satz sagt dann „Freier Platz unbekannt.“ statt eines
    falschen Laufwerks.
    """
    from app.core import discover

    if discover.in_flatpak():
        return None
    configured = os.environ.get("OLLAMA_MODELS", "").strip()
    if configured:
        return Path(configured)
    if sys.platform.startswith("linux"):
        from_unit = _models_from_units()
        if from_unit is not None:
            return from_unit
        if _SYSTEMD_UNITS[0].is_file() and _SERVICE_HOME.is_dir():
            return _SERVICE_HOME / ".ollama" / "models"
    folder = Path.home() / ".ollama" / "models"
    return folder if folder.exists() or folder.parent.exists() else None


def _models_from_units() -> Path | None:
    """``OLLAMA_MODELS`` aus der Unit des Dienstes und ihren Ergänzungen."""
    files: list[Path] = []
    for place in _SYSTEMD_UNITS:
        try:
            if place.is_file():
                files.append(place)
            elif place.is_dir():
                files.extend(sorted(place.glob("*.conf")))
        except OSError:
            continue
    found: Path | None = None
    for unit in files:
        try:
            text = unit.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _MODELS_SETTING.finditer(text):
            found = Path(match.group(1))
    return found


def _already_there(folder: Path, model: str) -> bool:
    """Ob das Modell schon ganz da ist: Sein Manifest liegt bei Ollama.

    **Ein abgebrochener Download zählt nicht als geladen** (Nachprüfung K, N5).
    Ollama legt jede ``…-partial``-Datei beim Start auf die volle Größe des
    Teils an (``server/download.go``: ``file.Truncate(b.Total)``), ihre Größe
    sagt also nichts über das Geladene, und welchem Modell sie gehört, steht
    erst im Manifest am Ende. Lieber den ganzen Download nennen als zu wenig.
    """
    name, _colon, tag = llm.normalised_model_name(model).partition(":")
    manifest = folder / "manifests" / "registry.ollama.ai" / "library" / name / (tag or "latest")
    try:
        if not manifest.is_file():
            return False
        json.loads(manifest.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return False
    return True


def chat_disk_need(model: str) -> tuple[float, float | None] | None:
    """Wie viel Platz das Modell noch braucht und wie viel frei ist — ``None`` ohne Größe.

    Gebraucht wird der ganze Download plus dieselbe
    Luft wie bei ComfyUI (``comfy_setup.HEADROOM_GIGABYTES``); frei ist
    ``None``, wenn der Ort unbekannt ist oder Ollama woanders rechnet.
    """
    suggestion = llm.known_model_suggestion(model)
    if suggestion is None:
        return None
    folder = ollama_models_folder() if llm.ollama_runs_here() else None
    if folder is None:
        return suggestion[0] + comfy_setup.HEADROOM_GIGABYTES, None
    if _already_there(folder, model):
        return 0.0, None
    needed = suggestion[0] + comfy_setup.HEADROOM_GIGABYTES
    try:
        free = comfy_setup.free_gigabytes(folder)
    except OSError:
        return needed, None
    return needed, free


def graphics_verdict(model: str, machine: Machine | None = None) -> str | None:
    """Ob das Modell hier ganz über die Grafik läuft, als Satz samt Ausweg.

    ``None``, wenn Ollama woanders rechnet, die Grafik unbekannt ist oder das
    Modell keine Messung hat. Auf dem Mac ist es gerechnet und sagt das.
    """
    found = machine or _machine.this_machine()
    need = llm.OLLAMA_MEMORY_GB.get(llm.normalised_model_name(model))
    budget = found.graphics_gb
    if need is None or budget is None or not llm.ollama_runs_here():
        return None
    if found.apple_silicon and found.memory_gb is not None:
        values = {
            "graphics": format_decimal(budget, 1),
            "total": format_decimal(found.memory_gb, 0),
        }
        said = (
            _(
                "Auf diesem Mac sollte es in den Speicher passen, den die Grafik nutzt: rund "
                "{graphics} von {total} GB, gerechnet, auf einem Mac nicht nachgemessen.",
                **values,
            )
            if need <= budget
            else _(
                "Für diesen Mac voraussichtlich zu groß: Die Grafik nutzt hier rund {graphics} "
                "von {total} GB (gerechnet), der Rest rechnet auf dem Prozessor, und jede "
                "Anfrage dauert Minuten.",
                **values,
            )
        )
    else:
        values = {"card": found.card_name, "size": format_decimal(found.card_gb or 0.0, 0)}
        said = (
            _("Die Grafikkarte {card} hat {size} GB, das reicht.", **values)
            if need <= budget
            else _(
                "Die Grafikkarte {card} hat {size} GB, das reicht nicht ganz, ein Teil rechnet "
                "auf dem Prozessor, und jede Anfrage dauert Minuten.",
                **values,
            )
        )
    if need <= budget:
        return str(said)
    better = llm.recommended_ollama_model(found)
    way = (
        _("Hier hilft ein Schlüssel für ein gehostetes Modell.")
        if better is None
        else _("Passend ist {model}.", model=better)
    )
    return f"{said!s} {way!s}"


def chat_needs(model: str, machine: Machine | None = None) -> str | None:
    """Voraussetzungen des Modells und ob dieser Rechner sie erfüllt — vor dem Holen.

    ``None`` für ein Modell ohne Messung; dafür hat der Dialog seinen eigenen
    Satz (Werkzeugprobe nach dem Holen).
    """
    found = machine or _machine.this_machine()
    need = llm.OLLAMA_MEMORY_GB.get(llm.normalised_model_name(model))
    disk = chat_disk_need(model)
    if need is None or disk is None:
        return None
    needed, free = disk
    parts: list[str] = []
    if not llm.ollama_runs_here():
        parts.append(
            str(_("Ollama rechnet auf einem anderen Rechner, dort zählen Grafik und Platz."))
        )
        return " ".join(parts)
    values = {"memory": format_decimal(need, 1), "disk": format_decimal(needed, 1)}
    parts.append(
        str(
            _(
                "Braucht rund {memory} GB gemeinsamen Speicher für die Grafik und {disk} GB Platz.",
                **values,
            )
            if found.apple_silicon
            else _(
                "Braucht rund {memory} GB Grafikspeicher für zügige Antworten und {disk} GB Platz.",
                **values,
            )
        )
    )
    verdict = graphics_verdict(model, found)
    if verdict is not None:
        parts.append(verdict)
    elif found.card_asked:
        parts.append(
            str(
                _(
                    "Eine NVIDIA-Karte erkennt Solidon hier nicht. Rechnet keine Grafikkarte, "
                    "dauert jede Anfrage Minuten."
                )
            )
        )
    if needed <= 0.0:
        parts.append(str(_("Das Modell liegt schon hier.")))
    elif free is None:
        parts.append(str(_("Freier Platz unbekannt.")))
    elif free >= needed:
        parts.append(str(_("Frei: {free} GB.", free=format_decimal(free, 1))))
    else:
        parts.append(
            str(
                _(
                    "Frei sind nur {free} GB. Schaffen Sie Platz oder wählen Sie ein kleineres "
                    "Modell.",
                    free=format_decimal(free, 1),
                )
            )
        )
    return " ".join(parts)


def pull_space_problem(model: str) -> str | None:
    """Der Satz, wenn das Modell nach dieser Rechnung nicht auf die Platte passt.

    Der Dialog sagt ihn beim ersten Klick als Warnung und holt beim zweiten
    trotzdem (Review K, M5): Die Rechnung kann irren, der Kunde nicht.
    """
    disk = chat_disk_need(model)
    if disk is None:
        return None
    needed, free = disk
    if free is None or free >= needed:
        return None
    return str(
        _(
            "Auf dem Laufwerk der Modelle sind {free} GB frei, das Modell braucht rund {needed} "
            "GB. Schaffen Sie Platz oder wählen Sie ein kleineres Modell, „Modell holen“ lädt es "
            "sonst trotzdem.",
            free=format_decimal(free, 1),
            needed=format_decimal(needed, 1),
        )
    )


def generator_needs(
    weights: bool, image_model: bool, free: float | None, machine: Machine | None = None
) -> tuple[str, bool]:
    """Voraussetzungen für Weg 3 in ComfyUI und ob dieser Rechner sie erfüllt.

    Zurück kommen der Satz und ob etwas fehlt (dann färbt der Dialog ihn als
    Warnung). Gebraucht werden die gewählten Dateien plus Luft
    (``comfy_setup``), eine Grafikkarte — gemessen ist Weg 3 nur auf einer
    NVIDIA-Karte mit ``MEASURED_GRAPHICS_GB`` — und dazu die gemessene Dauer.
    """
    found = machine or _machine.this_machine()
    download = (comfy_setup.WEIGHT_GIGABYTES if weights else 0.0) + (
        comfy_setup.IMAGE_MODEL_GIGABYTES if image_model else 0.0
    )
    measured = comfy_setup.MEASURED_GRAPHICS_GB
    parts: list[str] = []
    short = False
    if download:
        needed = download + comfy_setup.HEADROOM_GIGABYTES
        parts.append(
            str(
                _(
                    "Voraussetzung: eine Grafikkarte, gemessen ist Weg 3 auf einer NVIDIA-Karte "
                    "mit {memory} GB, und {disk} GB freier Platz.",
                    memory=measured,
                    disk=format_decimal(needed, 1),
                )
            )
        )
        if free is not None and free < needed:
            short = True
            parts.append(
                str(
                    _(
                        "Frei sind nur {free} GB. Schaffen Sie Platz oder laden Sie nur das "
                        "Modell für den Weg aus Bild.",
                        free=format_decimal(free, 1),
                    )
                    if weights and image_model
                    else _(
                        "Frei sind nur {free} GB. Schaffen Sie vorher Platz auf diesem Laufwerk.",
                        free=format_decimal(free, 1),
                    )
                )
            )
        elif free is not None:
            parts.append(str(_("Frei: {free} GB.", free=format_decimal(free, 1))))
    if found.apple_silicon and found.memory_gb is not None:
        parts.append(
            str(
                _(
                    "Auf dem Mac rechnet ComfyUI über den gemeinsamen Speicher, der Grafik "
                    "stehen rund {graphics} von {total} GB zur Verfügung (gerechnet). Ob das "
                    "reicht, ist auf einem Mac nicht gemessen.",
                    graphics=format_decimal(found.graphics_gb or 0.0, 1),
                    total=format_decimal(found.memory_gb, 0),
                )
            )
        )
    elif found.card_gb is not None:
        enough = round(found.card_gb) >= measured
        short = short or not enough
        parts.append(
            str(
                _(
                    "Die Grafikkarte {card} hat {size} GB, das reicht.",
                    card=found.card_name,
                    size=format_decimal(found.card_gb, 0),
                )
                if enough
                else _(
                    "Die Grafikkarte {card} hat {size} GB, mit weniger als {memory} GB ist Weg 3 "
                    "nicht geprüft.",
                    card=found.card_name,
                    size=format_decimal(found.card_gb, 0),
                    memory=measured,
                )
            )
        )
    elif found.card_asked:
        short = True
        parts.append(
            str(
                _(
                    "Eine NVIDIA-Karte erkennt Solidon hier nicht. Ohne sie rechnet ComfyUI um "
                    "ein Vielfaches länger. Ein Modell aus einem anderen Generator lässt sich "
                    "jederzeit als GLB- oder STL-Datei einfügen."
                )
            )
        )
    parts.append(duration_text(mac_note=found.apple_silicon))
    return " ".join(parts), short


def duration_text(*, mac_note: bool) -> str:
    """Die gemessene Dauer eines Auftrags — dieselbe im Dialog und im Handbuch (Review K, G1).

    ``mac_note`` hängt an, dass sie auf einem Mac nicht gemessen ist; das
    Handbuch sagt es immer, der Dialog auf dem Mac.
    """
    said = str(
        _(
            "Gemessen auf einer NVIDIA RTX 4080 mit {memory} GB dauert der erste Auftrag nach "
            "dem Start von ComfyUI aus einem Bild rund {image} Minuten, aus Text rund {text}, "
            "jeder weitere {low} bis {high} Sekunden, je nachdem, was der Rechner nebenher tut.",
            memory=comfy_setup.MEASURED_GRAPHICS_GB,
            image=round(comfy_setup.FIRST_IMAGE_SECONDS / 60),
            text=round(comfy_setup.FIRST_TEXT_SECONDS / 60),
            low=comfy_setup.WARM_SECONDS_LOW,
            high=comfy_setup.WARM_SECONDS_HIGH,
        )
    )
    if mac_note:
        return f"{said} {_('Auf einem Mac ist das noch nicht gemessen.')!s}"
    return said
