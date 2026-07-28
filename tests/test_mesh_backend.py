"""The mesh backends of §27, with no graphics card in sight.

Everything ComfyUI does over HTTP is three requests, and all three go through
one replaceable function — so the whole way, including the polling and the
placeholders in the workflow, can be played through here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.backends.mesh import (
    WORKFLOW_DIR,
    ComfyBackend,
    GenerationFailed,
    ScriptedMeshBackend,
    reachable,
)

MESHES = Path(__file__).parent / "data" / "meshes"


def stl(name: str = "cube_clean.stl") -> bytes:
    return (MESHES / name).read_bytes()


class Comfy:
    """A ComfyUI that answers from a script instead of from a graphics card."""

    def __init__(self, *, ready_after: int = 1, payload: bytes | None = None) -> None:
        self.ready_after = ready_after
        self.payload = payload if payload is not None else stl()
        self.requests: list[str] = []
        self.graphs: list[dict] = []

    def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        self.requests.append(url)
        if url.endswith("/prompt"):
            self.graphs.append(json.loads((body or b"{}").decode("utf-8"))["prompt"])
            return b'{"prompt_id": "job-1"}'
        if "/history/" in url:
            asked = sum(1 for entry in self.requests if "/history/" in entry)
            if asked < self.ready_after:
                return b"{}"
            return json.dumps(
                {"job-1": {"outputs": {"4": {"meshes": [{"filename": "out.stl"}]}}}}
            ).encode("utf-8")
        if url.endswith("/upload/image"):
            return b'{"name": "uploaded.png"}'
        return self.payload


def backend(server: Comfy) -> ComfyBackend:
    return ComfyBackend(transport=server, poll_seconds=0.0)


def test_a_prompt_goes_through_the_shipped_workflow() -> None:
    server = Comfy()

    result = backend(server).text_to_mesh("ein Halter", seed=17)

    assert result.mesh.triangle_count == 12
    assert result.backend == "comfyui"
    assert result.prompt == "ein Halter"
    assert result.seed == 17
    assert result.payload == stl(), "the file is kept as it came (§16.1)"


def test_the_placeholders_arrive_with_their_type() -> None:
    """ComfyUI checks the type of every input — a seed as text is rejected."""
    server = Comfy()

    backend(server).text_to_mesh("ein Halter", seed=17)

    graph = server.graphs[0]
    assert graph["2"]["inputs"]["text"] == "ein Halter"
    assert graph["3"]["inputs"]["seed"] == 17, 'a number, not the string "17"'


def test_a_picture_is_uploaded_before_the_job() -> None:
    server = Comfy()

    backend(server).image_to_mesh(b"\x89PNG fake", seed=3)

    assert any(entry.endswith("/upload/image") for entry in server.requests)
    assert server.graphs[0]["2"]["inputs"]["image"] == "uploaded.png"


def test_the_job_is_polled_until_it_is_done() -> None:
    server = Comfy(ready_after=3)

    backend(server).text_to_mesh("ein Halter")

    assert sum(1 for entry in server.requests if "/history/" in entry) == 3


def test_a_job_that_never_finishes_gives_up() -> None:
    server = Comfy(ready_after=10_000)
    generator = ComfyBackend(transport=server, poll_seconds=0.0, timeout_seconds=0.05)

    with pytest.raises(GenerationFailed):
        generator.text_to_mesh("ein Halter")


def test_an_empty_prompt_never_reaches_the_backend() -> None:
    server = Comfy()

    with pytest.raises(GenerationFailed):
        backend(server).text_to_mesh("   ")

    assert server.requests == []


def test_a_job_without_a_mesh_file_says_so() -> None:
    class NoMesh(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if "/history/" in url:
                return json.dumps({"job-1": {"outputs": {"4": {"images": ["x.png"]}}}}).encode()
            return super().__call__(url, body, headers)

    with pytest.raises(GenerationFailed):
        backend(NoMesh()).text_to_mesh("ein Halter")


def test_a_missing_workflow_is_a_clear_error(tmp_path: Path) -> None:
    generator = ComfyBackend(transport=Comfy(), workflows=tmp_path)

    with pytest.raises(GenerationFailed) as problem:
        generator.text_to_mesh("ein Halter")

    assert "workflow" in str(problem.value.detail)


@pytest.mark.parametrize("name", ["text_to_mesh", "image_to_mesh"])
def test_the_shipped_workflows_are_valid_graphs(name: str) -> None:
    graph = json.loads((WORKFLOW_DIR / f"{name}.json").read_text(encoding="utf-8"))

    assert all("class_type" in node for node in graph.values())
    assert any("{seed}" in json.dumps(node) for node in graph.values())


def test_nothing_running_means_not_available() -> None:
    assert not reachable("http://127.0.0.1:1", seconds=0.05)


def test_the_scripted_backend_answers_what_it_was_given() -> None:
    generator = ScriptedMeshBackend(answers={"ein Halter": stl()})

    assert generator.available
    result = generator.text_to_mesh("ein Halter", seed=4)
    assert result.mesh.triangle_count == 12
    assert generator.calls == [("ein Halter", 4)]

    with pytest.raises(GenerationFailed):
        generator.text_to_mesh("etwas anderes")
