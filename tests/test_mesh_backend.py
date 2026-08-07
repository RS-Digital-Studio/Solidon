"""Die Mesh-Backends aus §27, ohne eine Grafikkarte in Sicht.

Alles, was ComfyUI über HTTP tut, sind drei Anfragen, und alle drei gehen durch
eine austauschbare Funktion — der ganze Weg lässt sich hier also durchspielen,
samt dem Nachfragen und den Platzhaltern im Workflow.
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


#: Was ein Rechner mit dieser Ausstattung zur Auswahl stellt, samt der Fallen:
#: der Formkern liegt unter denselben Checkpoints wie die Bildmodelle, und im
#: VAE-Ordner liegt nicht nur die eine, die gemeint ist.
OFFERED: dict[str, list[str]] = {
    "CheckpointLoaderSimple.ckpt_name": [
        "hunyuan_3d_v2.1.safetensors",
        "Juggernaut-X-v10.safetensors",
        "animagine-xl-4.0-opt.safetensors",
    ],
    "Hy3DMeshGenerator.model": ["hunyuan3d-dit-v2-1-fp16.ckpt"],
    "Hy3D21VAELoader.model_name": ["sdxl_vae.safetensors", "Hunyuan3D-vae-v2-1-fp16.ckpt"],
}


def described(class_type: str) -> bytes:
    """Die Antwort von ``/object_info/<knoten>``, so aufgebaut wie die echte."""
    required: dict[str, object] = {}
    for key, names in OFFERED.items():
        node, field = key.split(".")
        if node == class_type:
            required[field] = [names, {}]
    return json.dumps({class_type: {"input": {"required": required}}}).encode("utf-8")


class Comfy:
    """Ein ComfyUI, das aus einem Skript antwortet statt von einer Grafikkarte."""

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
        if "/object_info/" in url:
            return described(url.rsplit("/", 1)[1])
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
    """ComfyUI prüft den Typ jedes Eingangs — ein Startwert als Text wird
    abgelehnt.

    Geprüft wird der Graph als Ganzes, nicht eine Knotennummer: welcher Knoten
    den Text bekommt, hängt am mitgelieferten Workflow und darf sich ändern,
    ohne dass dieser Test etwas anderes zu prüfen beginnt.
    """
    server = Comfy()

    backend(server).text_to_mesh("ein Halter", seed=17)

    graph = server.graphs[0]
    texts = [
        node["inputs"]["text"]
        for node in graph.values()
        if isinstance(node["inputs"].get("text"), str)
    ]
    assert any("ein Halter" in entry for entry in texts), "der Prompt steht im Graphen"

    seeds = [node["inputs"]["seed"] for node in graph.values() if "seed" in node["inputs"]]
    assert seeds, "irgendwo wird ein Startwert gesetzt"
    assert all(entry == 17 for entry in seeds), 'a number, not the string "17"'
    assert all(isinstance(entry, int) for entry in seeds)


def test_a_picture_is_uploaded_before_the_job() -> None:
    server = Comfy()

    backend(server).image_to_mesh(b"\x89PNG fake", seed=3)

    assert any(entry.endswith("/upload/image") for entry in server.requests)
    names = [
        node["inputs"]["image"]
        for node in server.graphs[0].values()
        if isinstance(node["inputs"].get("image"), str)
    ]
    assert names == ["uploaded.png"], "der hochgeladene Name steht im Graphen"


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


def test_an_output_that_is_a_bare_path_is_found_too() -> None:
    """Die 3D-Vorschau meldet einen blanken Pfad, keinen Eintrag mit Feldern.

    Das ist keine Theorie: gegen eine echte Installation ist genau das die
    einzige Ausgabe eines erfolgreichen Auftrags. Wer nur Einträge mit Feldern
    liest, meldet nach einer gelungenen Erzeugung „kein Modell geliefert".
    """

    class Preview(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if "/history/" in url:
                return json.dumps(
                    {
                        "job-1": {
                            "outputs": {"8": {"result": ["formwerk\\text_00001_.stl", None, None]}}
                        }
                    }
                ).encode()
            return super().__call__(url, body, headers)

    server = Preview()
    result = backend(server).text_to_mesh("ein Halter")

    assert result.mesh.triangle_count == 12
    holt = [entry for entry in server.requests if "/view?" in entry][-1]
    assert "filename=text_00001_.stl" in holt
    assert "subfolder=formwerk" in holt, "der Ordner wird vom Namen getrennt"


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


def test_the_models_come_from_the_machine_it_runs_on() -> None:
    """Ein Graph mit fest eingetragenen Dateinamen läuft nur auf einem Rechner.

    Der mitgelieferte nennt deshalb Rollen, und was sie ausfüllt, entscheidet
    sich gegen den laufenden Server.
    """
    server = Comfy()

    backend(server).text_to_mesh("ein Halter")

    graph = server.graphs[0]
    chosen = {
        node["class_type"]: node["inputs"]
        for node in graph.values()
        if node["class_type"] in ("CheckpointLoaderSimple", "Hy3DMeshGenerator", "Hy3D21VAELoader")
    }
    assert chosen["Hy3DMeshGenerator"]["model"] == "hunyuan3d-dit-v2-1-fp16.ckpt"
    assert chosen["Hy3D21VAELoader"]["model_name"] == "Hunyuan3D-vae-v2-1-fp16.ckpt", (
        "nicht die sdxl_vae, die im selben Ordner liegt"
    )
    assert chosen["CheckpointLoaderSimple"]["ckpt_name"] == "Juggernaut-X-v10.safetensors", (
        "nicht der Formkern, der unter denselben Checkpoints liegt"
    )
    assert not any("{model:" in json.dumps(node) for node in graph.values())


def test_an_unknown_model_is_better_than_none() -> None:
    """Wer ein Bildmodell hat, das wir nicht kennen, soll trotzdem erzeugen
    können — geraten wird hier nichts, es gibt schlicht nur eines.
    """

    class Exotic(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if "/object_info/CheckpointLoaderSimple" in url:
                return json.dumps(
                    {
                        "CheckpointLoaderSimple": {
                            "input": {"required": {"ckpt_name": [["eigenbau_v3.safetensors"], {}]}}
                        }
                    }
                ).encode()
            return super().__call__(url, body, headers)

    server = Exotic()
    backend(server).text_to_mesh("ein Halter")

    names = [
        node["inputs"]["ckpt_name"]
        for node in server.graphs[0].values()
        if node["class_type"] == "CheckpointLoaderSimple"
    ]
    assert names == ["eigenbau_v3.safetensors"]


def test_a_missing_model_names_the_role_not_the_setting() -> None:
    """Fehlt die Datei, hilft „Einstellungen öffnen" niemandem — es fehlt das
    Modell, und der Satz muss das sagen.
    """

    class Empty(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if "/object_info/" in url:
                node = url.rsplit("/", 1)[1]
                return json.dumps({node: {"input": {"required": {}}}}).encode()
            return super().__call__(url, body, headers)

    with pytest.raises(GenerationFailed) as problem:
        backend(Empty()).text_to_mesh("ein Halter")

    assert problem.value.suggestions, "jede Ausnahme trägt einen Vorschlag"
    assert "Modelldatei" in str(problem.value.detail)


def test_the_machine_is_asked_once_per_input_not_once_per_node() -> None:
    """Drei Rollen heißen drei Fragen, nicht eine je Knoten des Graphen."""
    server = Comfy()

    backend(server).text_to_mesh("ein Halter")

    asked = [entry for entry in server.requests if "/object_info/" in entry]
    assert len(asked) == len(set(asked)) == 3


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
