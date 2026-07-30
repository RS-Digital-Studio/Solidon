"""Mesh generation, locally or hosted (Bauplan §27, pillar B).

The interface knows two calls and nothing else: ``text_to_mesh`` and
``image_to_mesh``. No user code, no file paths, no state — a hosted service can
satisfy the same two calls later without anything above noticing (§27).

Locally that is ComfyUI, reached over its HTTP API: a workflow graph goes in, a
job id comes back, the result is fetched when it is done. The graph is a data
file, not code — whoever has a different generator installed replaces the file
instead of patching Python.

What comes out is never trusted — generators produce meshes with holes, stray
components and inverted normals as a matter of course. The repair chain that
deals with that is not here though: it belongs on the stack, where it is
visible and can be taken back (§2.2, way 3, and :mod:`app.core.generate`). A
backend delivers, it does not judge.
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
from pathlib import Path
from typing import Any, Protocol

from app.core.errors import AppError
from app.core.geom.mesh import MeshData, read_mesh
from app.core.log import get_logger
from app.core.types import ProgressFn
from app.i18n import _

_log = get_logger(__name__)

#: How long a generation may take. Minutes, not seconds — this is a diffusion
#: model on somebody's graphics card, not a database query.
TIMEOUT_SECONDS = 600.0

#: How often the job is asked whether it is done.
POLL_SECONDS = 1.0

#: How long the check "is ComfyUI running" may take. Same reason as the model
#: probe: it happens while a window is being built.
PROBE_SECONDS = 0.25

DEFAULT_COMFY_URL = "http://127.0.0.1:8188"

#: The shipped workflow graphs, one per call. Placeholders in them are filled
#: in before sending: ``{prompt}``, ``{seed}``, ``{image}``.
WORKFLOW_DIR = Path(__file__).parent / "data"

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


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
    """A generated body, as it came, plus where it came from (§11.3).

    The bytes are kept beside the parsed body on purpose: they are what gets
    embedded in the project (§16.1), and re-encoding them here would throw away
    the texture that pillar B's whole colour path depends on (§20).
    """

    mesh: MeshData
    payload: bytes
    suffix: str
    backend: str
    prompt: str = ""
    seed: int = 0


class MeshBackend(Protocol):
    """The two calls of §27, and nothing more."""

    @property
    def id(self) -> str: ...

    @property
    def available(self) -> bool:
        """False when nothing is running — the generate action greys out."""
        ...

    def text_to_mesh(
        self, prompt: str, *, seed: int = 0, progress: ProgressFn = _silent
    ) -> GeneratedMesh: ...

    def image_to_mesh(
        self, image: bytes, *, seed: int = 0, progress: ProgressFn = _silent
    ) -> GeneratedMesh: ...


class GenerationFailed(AppError):
    """The generator did not deliver a body."""

    default_title = _("Die Mesh-Erzeugung hat kein Modell geliefert.")

    def __init__(self, detail: str = "") -> None:
        super().__init__(detail=detail or None)


# --- transports -------------------------------------------------------------------

Fetch = Callable[[str, bytes | None, dict[str, str]], bytes]
"""``url, body, headers -> bytes``. Replaceable, which is what lets the suite
run the whole way without a graphics card."""


def fetch(url: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> bytes:
    """One request, bytes back. POST when there is a body, GET otherwise."""
    request = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:
            return bytes(answer.read())
    except urllib.error.HTTPError as error:
        raise GenerationFailed(
            detail=f"{error.code}: {error.read().decode('utf-8', errors='replace')[:300]}"
        ) from error
    except urllib.error.URLError as error:
        raise GenerationFailed(detail=str(error.reason)) from error


def reachable(url: str, seconds: float = PROBE_SECONDS) -> bool:
    """A socket, not a request: a closed port answers instantly, HTTP does not."""
    parts = urllib.parse.urlparse(url)
    try:
        with socket.create_connection((parts.hostname or "", parts.port or 80), timeout=seconds):
            return True
    except OSError:
        return False


# --- ComfyUI ----------------------------------------------------------------------


@dataclass(slots=True)
class ComfyBackend:
    """ComfyUI on this machine, over its HTTP API (§27).

    Three requests: post the graph, wait for the job, fetch the file. The
    client id is new every time — the backend keeps no state, so neither does
    this (§27).
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
        """Load the shipped workflow and put the values into it."""
        path = self.workflows / f"{name}.json"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as problem:
            raise GenerationFailed(detail=f"workflow {name} is missing") from problem
        return dict(_filled(json.loads(text), values))

    def _upload(self, image: bytes) -> str:
        """Put the image where ComfyUI can see it, and return the name it got."""
        name = f"formwerk_{uuid.uuid4().hex}.png"
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
        """Poll until the job is in the history. There is no push to listen to."""
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            answer = self.transport(f"{self.url}/history/{job}", None, {})
            history = json.loads(answer.decode("utf-8"))
            entry = history.get(job)
            if entry and entry.get("outputs"):
                return dict(entry["outputs"])
            progress(0.5, str(_("Modell wird erzeugt")))
            time.sleep(self.poll_seconds)
        raise GenerationFailed(detail="the generation ran into its time limit")

    def _download(self, outputs: dict[str, Any]) -> tuple[bytes, str]:
        """Find the mesh among the outputs and fetch it."""
        for node in outputs.values():
            for key in ("meshes", "3d", "result", "files"):
                for entry in node.get(key, ()) or ():
                    if not isinstance(entry, dict):
                        continue
                    name = str(entry.get("filename", ""))
                    suffix = Path(name).suffix.lower()
                    if suffix not in (".glb", ".obj", ".ply", ".stl"):
                        continue
                    query = urllib.parse.urlencode(
                        {
                            "filename": name,
                            "subfolder": entry.get("subfolder", ""),
                            "type": entry.get("type", "output"),
                        }
                    )
                    return self.transport(f"{self.url}/view?{query}", None, {}), suffix
        raise GenerationFailed(detail="the job produced no mesh file")


# --- scripted, for the suite ------------------------------------------------------


@dataclass(slots=True)
class ScriptedMeshBackend:
    """A generator that hands back a prepared file (§35).

    Way 3 has to be testable without a graphics card, and a test that only ever
    sees clean geometry would prove nothing — so what gets prepared here are
    the broken bodies a generator really delivers.
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


def _filled(node: Any, values: dict[str, Any]) -> Any:
    """Put the values into the graph, keeping their type.

    A placeholder standing alone becomes the value itself, so ``"{seed}"``
    arrives as a number — ComfyUI checks the types of its inputs and a seed as
    text is rejected by the node, not by us.
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
