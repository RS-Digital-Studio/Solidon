"""Mesh-Erzeugung, lokal oder gehostet (Bauplan §27, Säule B).

Die Schnittstelle kennt zwei Aufrufe und sonst nichts: ``text_to_mesh`` und
``image_to_mesh``. Kein Nutzercode, keine Dateipfade, kein Zustand — ein
gehosteter Dienst kann später dieselben zwei Aufrufe bedienen, ohne dass
darüber irgendetwas davon merkt (§27).

Lokal ist das ComfyUI, erreicht über seine HTTP-API: ein Workflow-Graph geht
hinein, eine Auftrags-ID kommt zurück, das Ergebnis wird geholt, wenn es
fertig ist. Der Graph ist eine Datendatei, kein Code — wer einen anderen
Generator installiert hat, tauscht die Datei aus, statt Python zu flicken.

Woran die mitgelieferten Graphen hängen, steht deshalb hier und nicht im Code:
an der Knotensammlung ``ComfyUI-Hunyuan3d-2-1`` samt ihren beiden Gewichten
(``hunyuan3d-dit-v2-1-fp16`` und die zugehörige VAE), an ``ComfyUI-RMBG`` fürs
Freistellen, und ``text_to_mesh`` zusätzlich an einem SDXL-Modell. Letzteres
ist kein Umweg, sondern die Sache selbst: Hunyuan3D kennt keinen Texteingang,
Text wird erst zu einem Bild und das Bild zum Körper. Fehlt eines davon, sagt
ComfyUI beim Abschicken, welcher Knoten fehlt — die Meldung reicht bis zum
Nutzer durch. Über die HTTP-API muss dabei **jeder** Eingang gesetzt sein, auch
ein als ``optional`` deklarierter: die Oberfläche schickt sie immer alle mit,
und mancher Knoten liest sie ungeprüft.

Was herauskommt, wird nie geglaubt — Generatoren erzeugen Netze mit Löchern,
losen Komponenten und umgedrehten Normalen als Normalfall. Die Reparaturkette,
die sich darum kümmert, steht aber nicht hier: sie gehört auf den Stapel, wo
sie sichtbar und rücknehmbar ist (§2.2, Weg 3, und :mod:`app.core.generate`).
Ein Backend liefert, es urteilt nicht.
"""

from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Final, Protocol

from app.core.errors import CANCEL, OPEN_SETTINGS, Action, AppError
from app.core.geom.mesh import MeshData, read_mesh
from app.core.log import get_logger
from app.core.types import ProgressFn
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Wie lange eine Erzeugung dauern darf. Minuten, keine Sekunden — das ist ein
#: Diffusionsmodell auf jemandes Grafikkarte, keine Datenbankabfrage.
TIMEOUT_SECONDS = 600.0

#: Wie oft der Auftrag gefragt wird, ob er fertig ist.
POLL_SECONDS = 1.0

#: Wie lange die Prüfung „läuft ComfyUI" dauern darf. Derselbe Grund wie beim
#: Modell-Test: sie passiert, während ein Fenster gebaut wird.
PROBE_SECONDS = 0.25

DEFAULT_COMFY_URL = "http://127.0.0.1:8188"

#: Die mitgelieferten Workflow-Graphen, einer je Aufruf. Platzhalter darin
#: werden vor dem Senden gefüllt: ``{prompt}``, ``{seed}``, ``{image}``.
WORKFLOW_DIR = Path(__file__).parent / "data"

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")

#: Ein Modellplatzhalter nennt nicht die Datei, sondern die Rolle:
#: ``{model:shape}``. Aufgelöst wird er erst gegen den Rechner, auf dem es
#: läuft — siehe :data:`MODEL_ROLES`.
_MODEL_PLACEHOLDER = re.compile(r"^\{model:([a-z_]+)\}$")


@dataclass(frozen=True, slots=True)
class ModelRole:
    """Woran ein Modell für seine Aufgabe erkannt wird.

    ``prefer`` ist eine Rangfolge, nicht eine Menge: das erste Muster, auf das
    etwas passt, gewinnt. ``avoid`` schließt vorher aus, denn manche Namen
    liegen im selben Ordner und sehen nur ähnlich aus — der Formkern und die
    Bildmodelle wohnen beide unter ``checkpoints``.
    """

    prefer: tuple[str, ...]
    avoid: tuple[str, ...] = ()


#: Die Rollen, die ein mitgelieferter Graph benennen darf. Wer einen eigenen
#: Graphen einsetzt, benutzt dieselben Namen — oder trägt die Datei fest ein,
#: was weiterhin erlaubt ist und dann eben nicht mitwandert.
MODEL_ROLES: Final[dict[str, ModelRole]] = {
    "image": ModelRole(
        prefer=("juggernaut", "dreamshaper", "sd_xl", "sdxl", "xl"),
        avoid=("hunyuan", "3d", "vae", "refiner", "inpaint", "turbo"),
    ),
    "shape": ModelRole(prefer=("hunyuan3d-dit", "hunyuan3d", "hunyuan"), avoid=("vae",)),
    "shape_vae": ModelRole(prefer=("hunyuan3d-vae", "hunyuan3d", "vae"), avoid=("dit",)),
}


def _silent(fraction: float, text: str) -> None:
    del fraction, text


def _configured_url() -> str:
    """Die eingetragene ComfyUI-Adresse, sonst die auf dieser Maschine.

    Der Import steht hier und nicht oben, weil :mod:`app.core.discover` die
    Nutzerkonfiguration liest — das gehört in den Aufruf und nicht in den
    Modulimport, damit eine Testumgebung sie noch umlenken kann.
    """
    from app.core import discover

    return discover.service_url("comfyui", DEFAULT_COMFY_URL)


@dataclass(frozen=True, slots=True)
class GeneratedMesh:
    """Ein erzeugter Körper, wie er kam, plus woher er kam (§11.3).

    Die Bytes werden mit Absicht neben dem geparsten Körper aufgehoben: sie
    sind das, was ins Projekt eingebettet wird (§16.1), und sie hier neu zu
    kodieren würfe die Textur weg, an der der ganze Farbweg von Säule B
    hängt (§20).
    """

    mesh: MeshData
    payload: bytes
    suffix: str
    backend: str
    prompt: str = ""
    seed: int = 0


class MeshBackend(Protocol):
    """Die zwei Aufrufe aus §27, und nicht mehr."""

    @property
    def id(self) -> str: ...

    @property
    def available(self) -> bool:
        """False, wenn nichts läuft — die Erzeugen-Aktion graut aus."""
        ...

    def text_to_mesh(
        self, prompt: str, *, seed: int = 0, progress: ProgressFn = _silent
    ) -> GeneratedMesh: ...

    def image_to_mesh(
        self, image: bytes, *, seed: int = 0, progress: ProgressFn = _silent
    ) -> GeneratedMesh: ...


class GenerationFailed(AppError):
    """Der Generator hat keinen Körper geliefert."""

    default_title = _("Die Mesh-Erzeugung hat kein Modell geliefert.")

    def __init__(
        self,
        detail: TranslatableText | str = "",
        *,
        title: TranslatableText | str | None = None,
        values: dict[str, Any] | None = None,
        suggestions: tuple[Action, ...] = (),
    ) -> None:
        # Ein anderer Titel ist nicht Zierde: „hat kein Modell geliefert" ist
        # falsch, wenn der Lauf nie begonnen hat — weil eine Modelldatei fehlt
        # oder weil ComfyUI gar nicht antwortet.
        super().__init__(
            title=title,
            detail=detail or None,
            values=values or {},
            suggestions=suggestions,
        )


# --- Transporte -------------------------------------------------------------------

Fetch = Callable[[str, bytes | None, dict[str, str]], bytes]
"""``url, body, headers -> bytes``. Austauschbar — genau das lässt die Suite
den ganzen Weg ohne Grafikkarte fahren."""


def fetch(url: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> bytes:
    """Eine Anfrage, Bytes zurück. POST, wenn es einen Rumpf gibt, sonst GET."""
    request = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:
            return bytes(answer.read())
    except urllib.error.HTTPError as error:
        raise GenerationFailed(
            detail=f"{error.code}: {error.read().decode('utf-8', errors='replace')[:300]}"
        ) from error
    except urllib.error.URLError as error:
        # Hier endet der häufigste Fall überhaupt: ComfyUI läuft nicht mehr.
        # Ohne eigenen Satz stünde davon „[WinError 10061] Es konnte keine
        # Verbindung hergestellt werden" im Dialog — Fremdtext, technisch, und
        # ohne einen Hinweis, was jetzt hilft. Der Titel ist derselbe Fehler:
        # geliefert hat der Generator nichts, weil er nie angefangen hat.
        raise GenerationFailed(
            title=_("Die Mesh-Erzeugung konnte nicht starten."),
            # Die Adresse gehört in die Werte daneben, nicht als Platzhalter in
            # den Satz: einen Fehlertext formatiert niemand nach, er wird
            # angezeigt wie er ist.
            detail=_(
                "ComfyUI antwortet nicht. Läuft es? Steht es auf einem anderen "
                "Rechner, gehört seine Adresse in die Einstellungen."
            ),
            values={"url": _origin(url), "reason": str(error.reason)},
            suggestions=(OPEN_SETTINGS, CANCEL),
        ) from error


def _origin(url: str) -> str:
    """Nur Rechner und Port — der Pfad dahinter sagt einem Nutzer nichts."""
    parts = urllib.parse.urlparse(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.netloc else url


def reachable(url: str, seconds: float = PROBE_SECONDS) -> bool:
    """Ein Socket, keine Anfrage: ein geschlossener Port antwortet sofort,
    HTTP nicht.
    """
    parts = urllib.parse.urlparse(url)
    try:
        with socket.create_connection((parts.hostname or "", parts.port or 80), timeout=seconds):
            return True
    except OSError:
        return False


# --- ComfyUI ----------------------------------------------------------------------


@dataclass(slots=True)
class ComfyBackend:
    """ComfyUI auf diesem Rechner, über seine HTTP-API (§27).

    Drei Anfragen: den Graphen abschicken, auf den Auftrag warten, die Datei
    holen. Die Client-ID ist jedes Mal neu — das Backend führt keinen Zustand,
    also tut dieses hier es auch nicht (§27).
    """

    # Die Adresse ist nicht fest: wer ComfyUI auf einem zweiten Rechner oder
    # auf einem anderen Port betreibt, trägt sie einmal ein (§38). Ohne
    # Eintrag bleibt es bei dieser Maschine.
    url: str = field(default_factory=lambda: _configured_url())
    transport: Fetch = fetch
    poll_seconds: float = POLL_SECONDS
    timeout_seconds: float = TIMEOUT_SECONDS
    workflows: Path = WORKFLOW_DIR

    @property
    def id(self) -> str:
        return "comfyui"

    @property
    def available(self) -> bool:
        return reachable(self.url)

    def text_to_mesh(
        self, prompt: str, *, seed: int = 0, progress: ProgressFn = _silent
    ) -> GeneratedMesh:
        if not prompt.strip():
            raise GenerationFailed(detail="empty prompt")
        graph = self._graph("text_to_mesh", {"prompt": prompt, "seed": seed})
        return self._run(graph, prompt=prompt, seed=seed, progress=progress)

    def image_to_mesh(
        self, image: bytes, *, seed: int = 0, progress: ProgressFn = _silent
    ) -> GeneratedMesh:
        if not image:
            raise GenerationFailed(detail="empty image")
        progress(0.05, str(_("Bild übertragen")))
        name = self._upload(image)
        graph = self._graph("image_to_mesh", {"image": name, "seed": seed})
        return self._run(graph, prompt="", seed=seed, progress=progress)

    # --- the three steps ---

    def _graph(self, name: str, values: dict[str, Any]) -> dict[str, Any]:
        """Lädt den mitgelieferten Workflow und setzt die Werte hinein."""
        path = self.workflows / f"{name}.json"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as problem:
            raise GenerationFailed(detail=f"workflow {name} is missing") from problem
        graph = self._with_models(json.loads(text))
        return dict(_filled(graph, values))

    def _with_models(self, graph: dict[str, Any]) -> dict[str, Any]:
        """Setzt für jede Modellrolle ein, was auf diesem Rechner wirklich liegt.

        Ein Graph mit fest eingetragenen Dateinamen läuft nur dort, wo genau
        diese Dateien liegen — überall sonst bricht er mit einer Meldung über
        einen Wert, den der Nutzer nie gesetzt hat. Deshalb nennt der Graph die
        Rolle, und welche Datei sie ausfüllt, entscheidet sich hier gegen den
        laufenden Server.

        Gefragt wird nur, wenn wirklich eine Rolle im Graphen steht: ein
        Graph mit festen Namen kostet weiterhin keine einzige Anfrage.
        """
        offered: dict[str, list[str]] = {}
        for node in graph.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            for key, value in list(inputs.items()):
                if not isinstance(value, str):
                    continue
                found = _MODEL_PLACEHOLDER.match(value)
                if found is None:
                    continue
                inputs[key] = self._pick(
                    found.group(1), str(node.get("class_type", "")), key, offered
                )
        return graph

    def _pick(self, role: str, class_type: str, field: str, offered: dict[str, list[str]]) -> str:
        """Die Datei, die diese Rolle auf diesem Rechner ausfüllt."""
        wanted = MODEL_ROLES.get(role)
        if wanted is None:
            raise GenerationFailed(detail=f"the workflow asks for an unknown model role {role!r}")

        key = f"{class_type}.{field}"
        if key not in offered:
            offered[key] = self._offered(class_type, field)
        options = offered[key]
        if not options:
            raise GenerationFailed(
                detail=_(
                    "ComfyUI hat für diese Aufgabe kein Modell anzubieten. Es "
                    "fehlt die Modelldatei, nicht die Einstellung."
                ),
                values={"role": role, "node": class_type},
            )

        usable = [
            entry for entry in options if not any(bad in entry.lower() for bad in wanted.avoid)
        ] or options
        for hint in wanted.prefer:
            for entry in usable:
                if hint in entry.lower():
                    return entry
        # Keines der Muster passte. Das ist kein Fehler: der Nutzer hat ein
        # Modell, das wir nicht kennen, und eines ist besser als keines.
        _log.info("no model matched role %s, taking %s", role, usable[0])
        return usable[0]

    def _offered(self, class_type: str, field: str) -> list[str]:
        """Was ComfyUI für diesen Eingang zur Auswahl stellt."""
        answer = self.transport(
            f"{self.url}/object_info/{urllib.parse.quote(class_type)}", None, {}
        )
        try:
            described = json.loads(answer.decode("utf-8"))
        except ValueError as problem:
            raise GenerationFailed(
                detail=f"ComfyUI described {class_type} in a way we cannot read"
            ) from problem

        inputs = described.get(class_type, {}).get("input", {})
        for group in ("required", "optional"):
            entry = (inputs.get(group) or {}).get(field)
            # Eine Auswahlliste steht als erstes Element der Beschreibung —
            # ein Typname wie "INT" steht an derselben Stelle und ist keine.
            if isinstance(entry, list) and entry and isinstance(entry[0], list):
                return [str(name) for name in entry[0]]
        return []

    def _upload(self, image: bytes) -> str:
        """Legt das Bild dorthin, wo ComfyUI es sehen kann, und gibt den Namen
        zurück, den es bekommen hat.
        """
        name = f"solidon_{uuid.uuid4().hex}.png"
        boundary = uuid.uuid4().hex
        body = b"".join(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'.encode(),
                b"Content-Type: image/png\r\n\r\n",
                image,
                f"\r\n--{boundary}--\r\n".encode(),
            ]
        )
        answer = self.transport(
            f"{self.url}/upload/image",
            body,
            {"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        given = json.loads(answer.decode("utf-8")).get("name")
        return str(given or name)

    def _run(
        self, graph: dict[str, Any], *, prompt: str, seed: int, progress: ProgressFn
    ) -> GeneratedMesh:
        progress(0.1, str(_("Auftrag abschicken")))
        payload = json.dumps({"prompt": graph, "client_id": uuid.uuid4().hex}).encode("utf-8")
        answer = self.transport(f"{self.url}/prompt", payload, {"Content-Type": "application/json"})
        job = json.loads(answer.decode("utf-8")).get("prompt_id")
        if not job:
            raise GenerationFailed(detail="the backend accepted no job")

        outputs = self._wait(str(job), progress)
        progress(0.9, str(_("Modell holen")))
        payload_bytes, suffix = self._download(outputs)
        return GeneratedMesh(
            mesh=read_mesh(payload_bytes, suffix),
            payload=payload_bytes,
            suffix=suffix,
            backend=self.id,
            prompt=prompt,
            seed=seed,
        )

    def _wait(self, job: str, progress: ProgressFn) -> dict[str, Any]:
        """Fragt, bis der Auftrag im Verlauf steht. Es gibt kein Push zum Zuhören.

        Der Satz dazu sagt die verstrichene Zeit, und das ist keine Zierde: ein
        Lauf dauert hier vierzig bis siebzig Sekunden, und „Modell wird
        erzeugt" allein steht die ganze Zeit unbewegt da — von einem Programm,
        das hängt, ist das nicht zu unterscheiden (§2.8). Eine erfundene
        Prozentzahl wäre die schlechtere Antwort: ComfyUI meldet echten
        Fortschritt nur über seinen Websocket, und was hier zählbar ist, ist
        die Zeit.

        Wartet der Auftrag noch hinter anderen, steht das dort statt der Zeit —
        wer eine Warteschlange vor sich hat, wartet auf etwas anderes als auf
        seine eigene Rechnung.
        """
        started = time.monotonic()
        deadline = started + self.timeout_seconds
        while time.monotonic() < deadline:
            answer = self.transport(f"{self.url}/history/{job}", None, {})
            history = json.loads(answer.decode("utf-8"))
            entry = history.get(job)
            if entry and entry.get("outputs"):
                return dict(entry["outputs"])
            progress(0.5, self._waiting_text(job, time.monotonic() - started))
            time.sleep(self.poll_seconds)
        raise GenerationFailed(detail="the generation ran into its time limit")

    def _waiting_text(self, job: str, seconds: float) -> str:
        ahead = self._ahead_in_queue(job)
        if ahead:
            return f"{_('Wartet auf den Generator')} ({ahead})"
        return f"{_('Modell wird erzeugt')} ({seconds:.0f} s)"

    def _ahead_in_queue(self, job: str) -> int:
        """Wie viele Aufträge vor diesem liegen. Null heißt: er ist an der Reihe.

        Ein Fehlschlag hier ist keiner — die Warteschlange ist eine Zugabe zum
        Text, und ein Lauf soll nicht daran scheitern, dass sie sich nicht
        abfragen ließ.
        """
        try:
            answer = self.transport(f"{self.url}/queue", None, {})
            queue = json.loads(answer.decode("utf-8"))
        except (AppError, OSError, ValueError):
            return 0
        pending = queue.get("queue_pending") or ()
        for index, entry in enumerate(pending):
            if isinstance(entry, list) and job in [str(field) for field in entry]:
                return index + 1
        return 0

    def _download(self, outputs: dict[str, Any]) -> tuple[bytes, str]:
        """Findet das Netz unter den Ausgaben und holt es."""
        for node in outputs.values():
            for key in ("meshes", "3d", "result", "files"):
                for entry in node.get(key, ()) or ():
                    located = _located(entry)
                    if located is None:
                        continue
                    query, suffix = located
                    return self.transport(f"{self.url}/view?{query}", None, {}), suffix
        raise GenerationFailed(detail="the job produced no mesh file")


# --- Geskriptet, für die Suite ------------------------------------------------------


@dataclass(slots=True)
class ScriptedMeshBackend:
    """Ein Generator, der eine vorbereitete Datei zurückgibt (§35).

    Weg 3 muss ohne Grafikkarte testbar sein, und ein Test, der nur saubere
    Geometrie zu sehen bekäme, bewiese nichts — vorbereitet werden hier also
    die kaputten Körper, die ein Generator wirklich liefert.
    """

    answers: dict[str, bytes] = field(default_factory=dict)
    fallback: bytes | None = None
    suffix: str = ".stl"
    calls: list[tuple[str, int]] = field(default_factory=list)

    @property
    def id(self) -> str:
        return "scripted"

    @property
    def available(self) -> bool:
        return bool(self.answers) or self.fallback is not None

    def text_to_mesh(
        self, prompt: str, *, seed: int = 0, progress: ProgressFn = _silent
    ) -> GeneratedMesh:
        self.calls.append((prompt, seed))
        progress(0.5, str(_("Modell wird erzeugt")))
        payload = self.answers.get(prompt, self.fallback)
        if payload is None:
            raise GenerationFailed(detail=f"nothing scripted for {prompt!r}")
        return self._as_result(payload, prompt, seed)

    def image_to_mesh(
        self, image: bytes, *, seed: int = 0, progress: ProgressFn = _silent
    ) -> GeneratedMesh:
        self.calls.append((f"<image {len(image)}>", seed))
        if self.fallback is None:
            raise GenerationFailed(detail="nothing scripted for an image")
        return self._as_result(self.fallback, "", seed)

    def _as_result(self, payload: bytes, prompt: str, seed: int) -> GeneratedMesh:
        return GeneratedMesh(
            mesh=read_mesh(payload, self.suffix),
            payload=payload,
            suffix=self.suffix,
            backend=self.id,
            prompt=prompt,
            seed=seed,
        )


#: Endungen, unter denen ein Körper unter den Ausgaben erkannt wird. Ein
#: Auftrag legt neben ihm auch Bilder ab — die gehören nicht uns.
MESH_SUFFIXES = (".glb", ".obj", ".ply", ".stl")


def _located(entry: Any) -> tuple[str, str] | None:
    """Aus einem Ausgabeeintrag die Abfrage für ``/view`` und die Endung.

    Zwei Schreibweisen kommen wirklich vor, und beide müssen ankommen: ein
    Eintrag mit Feldern, wie ihn die Bildknoten liefern, und ein blanker Pfad
    relativ zum Ausgabeordner, wie ihn die 3D-Vorschau zurückgibt. Wer nur die
    erste liest, findet nach einem erfolgreichen Auftrag nichts und meldet, es
    sei kein Modell erzeugt worden.

    ``None`` heißt „nicht unsere Datei" — kein Fehler, der Aufrufer sieht weiter.
    """
    if isinstance(entry, str):
        path = PurePosixPath(entry.replace("\\", "/"))
        name = path.name
        subfolder = "" if str(path.parent) == "." else str(path.parent)
        kind = "output"
    elif isinstance(entry, dict):
        name = str(entry.get("filename", ""))
        subfolder = str(entry.get("subfolder", ""))
        kind = str(entry.get("type", "output"))
    else:
        return None

    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in MESH_SUFFIXES:
        return None
    query = urllib.parse.urlencode({"filename": name, "subfolder": subfolder, "type": kind})
    return query, suffix


def _filled(node: Any, values: dict[str, Any]) -> Any:
    """Setzt die Werte in den Graphen ein und behält ihren Typ.

    Ein Platzhalter, der allein steht, wird zum Wert selbst — ``"{seed}"``
    kommt also als Zahl an: ComfyUI prüft die Typen seiner Eingänge, und ein
    Startwert als Text wird vom Knoten abgelehnt, nicht von uns.
    """
    if isinstance(node, dict):
        return {key: _filled(value, values) for key, value in node.items()}
    if isinstance(node, list):
        return [_filled(entry, values) for entry in node]
    if isinstance(node, str):
        alone = _PLACEHOLDER.fullmatch(node)
        if alone is not None and alone.group(1) in values:
            return values[alone.group(1)]
        return _PLACEHOLDER.sub(lambda found: str(values.get(found.group(1), found.group(0))), node)
    return node
