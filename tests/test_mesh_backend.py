"""Die Mesh-Backends aus §27, ohne eine Grafikkarte in Sicht.

Alles, was ComfyUI über HTTP tut, sind drei Anfragen, und alle drei gehen durch
eine austauschbare Funktion — der ganze Weg lässt sich hier also durchspielen,
samt dem Nachfragen und den Platzhaltern im Workflow.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from app.core.backends.mesh import (
    WORKFLOW_DIR,
    ComfyBackend,
    GenerationFailed,
    reachable,
)
from tests.scripted_backend import ScriptedMeshBackend

MESHES = Path(__file__).parent / "data" / "meshes"


def stl(name: str = "cube_clean.stl") -> bytes:
    return (MESHES / name).read_bytes()


#: Was ein Rechner mit dieser Ausstattung zur Auswahl stellt, samt der Fallen:
#: Unter ``diffusion_models`` liegen Formkern, Bildmodell und fremde Modelle
#: nebeneinander, dazu die 9B-Fassung (nicht-kommerzielle Lizenz) und das nicht
#: destillierte Basismodell von FLUX.2 [klein]; unter ``vae`` die Textur-VAE von
#: TRELLIS.2 und eine fremde. Die Fallen stehen mit Absicht vor der richtigen
#: Antwort.
OFFERED: dict[str, list[str]] = {
    "UNETLoader.unet_name": [
        "flux-2-klein-9b-fp8.safetensors",
        "flux-2-klein-base-4b.safetensors",
        "pixal3d_int8_convrot.safetensors",
        "wan2.2_t2v_14B.safetensors",
        "trellis_2_int8_convrot.safetensors",
        "flux-2-klein-4b-fp8.safetensors",
    ],
    "VAELoader.vae_name": [
        "ae.safetensors",
        "trellis_2_texture_vae_bf16.safetensors",
        "flux2-vae.safetensors",
        "trellis_2_shape_vae_bf16.safetensors",
    ],
    "CLIPLoader.clip_name": ["umt5_xxl_fp8.safetensors", "qwen_3_4b_fp4_flux2.safetensors"],
    "CLIPVisionLoader.clip_name": ["clip_vision_h.safetensors", "dino_v3_vit_l.safetensors"],
    # Freistellen: ComfyUI kann es seit 0.33 selbst, und beide Gewichte sind
    # BiRefNet unter MIT. ``lucida`` steht hinter ``birefnet``, damit die
    # Rangfolge etwas zu entscheiden hat.
    "LoadBackgroundRemovalModel.bg_removal_name": [
        "birefnet.safetensors",
        "lucida.safetensors",
    ],
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
        self.posts: list[tuple[str, bytes | None]] = []
        self.graphs: list[dict] = []

    def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        self.requests.append(url)
        if body is not None:
            self.posts.append((url, body))
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


def test_comfy_waiting_reports_progress_and_cancels_without_submitting_a_job() -> None:
    from app.core.backends.resources import local_ai_slot
    from app.core.errors import OperationCancelled

    server = Comfy()
    generator = ComfyBackend(url="http://localhost:8188", transport=server, poll_seconds=0.0)
    seen: list[tuple[float, str]] = []
    stopped = False

    def progress(fraction: float, text: str) -> None:
        nonlocal stopped
        seen.append((fraction, text))
        stopped = True

    with local_ai_slot("http://localhost:11434", None), pytest.raises(OperationCancelled):
        generator.text_to_mesh("ein Halter", progress=progress, cancelled=lambda: stopped)
    assert len(seen) == 1 and seen[0][0] == 0.0
    assert "Grafikkarte" in seen[0][1]
    assert not server.posts, "a waiting cancellation must not submit, cancel or unload a job"


def _opened_by(fake: object) -> Callable[[str], SimpleNamespace]:
    """Lenkt ``opener_for`` auf eine Attrappe um.

    Seit dem 27.08.2026 geht keine Anfrage mehr durch ``urlopen``, sondern
    durch einen Öffner, den :func:`app.core.discover.opener_for` je nach
    Adresse baut — für einen Dienst auf **diesem** Rechner ohne den
    Firmenproxy, für alles andere mit. Gepatcht wird deshalb der Öffner und
    nicht mehr ``urlopen``.

    Dass die acht Tests bei der Umstellung rot wurden, ist der Beleg, dass sie
    den echten Weg messen und nicht einen daneben.
    """
    return lambda url: SimpleNamespace(open=fake)


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


def test_the_wait_says_how_long_it_has_been_waiting() -> None:
    """Ein Lauf dauert vierzig bis siebzig Sekunden, und der Satz stand die
    ganze Zeit unbewegt da — von einem Programm, das hängt, nicht zu
    unterscheiden (§2.8).
    """
    server = Comfy(ready_after=4)
    seen: list[str] = []

    backend(server).text_to_mesh("ein Halter", progress=lambda _f, text: seen.append(text))

    waiting = [text for text in seen if "erzeugt" in text]
    assert waiting, "während des Wartens wird etwas gesagt"
    assert all("s)" in text for text in waiting), "und zwar mit der Zeit darin"


def test_a_queued_job_says_that_it_is_queued() -> None:
    """Wer hinter zwei anderen wartet, wartet auf etwas anderes als auf seine
    eigene Rechnung — und soll das lesen können.
    """

    class Busy(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if url.endswith("/queue"):
                return json.dumps(
                    {"queue_running": [], "queue_pending": [[0, "other"], [1, "job-1"]]}
                ).encode()
            return super().__call__(url, body, headers)

    server = Busy(ready_after=3)
    seen: list[str] = []

    backend(server).text_to_mesh("ein Halter", progress=lambda _f, text: seen.append(text))

    assert any("Wartet auf den Generator" in text for text in seen)
    assert any("(2)" in text for text in seen), "die Position steht dabei"


def test_a_queue_that_cannot_be_asked_costs_nothing() -> None:
    """Die Warteschlange ist eine Zugabe zum Text. Ein Lauf scheitert nicht
    daran, dass sie sich nicht abfragen ließ.
    """

    class NoQueue(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if url.endswith("/queue"):
                raise OSError("kein Weg dorthin")
            return super().__call__(url, body, headers)

    result = backend(NoQueue(ready_after=2)).text_to_mesh("ein Halter")

    assert result.mesh.triangle_count == 12


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
                            "outputs": {"8": {"result": ["solidon\\text_00001_.stl", None, None]}}
                        }
                    }
                ).encode()
            return super().__call__(url, body, headers)

    server = Preview()
    result = backend(server).text_to_mesh("ein Halter")

    assert result.mesh.triangle_count == 12
    holt = [entry for entry in server.requests if "/view?" in entry][-1]
    assert "filename=text_00001_.stl" in holt
    assert "subfolder=solidon" in holt, "der Ordner wird vom Namen getrennt"


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

    assert "workflow" in str(problem.value.detail).lower()


@pytest.mark.parametrize("name", ["text_to_mesh", "image_to_mesh"])
def test_the_shipped_workflows_are_valid_graphs(name: str) -> None:
    graph = json.loads((WORKFLOW_DIR / f"{name}.json").read_text(encoding="utf-8"))

    assert all("class_type" in node for node in graph.values())
    assert any("{seed}" in json.dumps(node) for node in graph.values())


def test_the_models_come_from_the_machine_it_runs_on() -> None:
    """Ein Graph mit fest eingetragenen Dateinamen läuft nur auf einem Rechner.

    Der mitgelieferte nennt deshalb Rollen, und was sie ausfüllt, entscheidet
    sich gegen den laufenden Server — im geteilten Ordner nach Muster, nicht
    nach Reihenfolge.
    """
    server = Comfy()

    backend(server).text_to_mesh("ein Halter")

    graph = server.graphs[0]
    chosen = [
        (node["class_type"], value)
        for node in graph.values()
        for field, value in node["inputs"].items()
        if field in ("unet_name", "vae_name", "clip_name")
    ]
    assert ("UNETLoader", "trellis_2_int8_convrot.safetensors") in chosen
    assert ("UNETLoader", "flux-2-klein-4b-fp8.safetensors") in chosen, (
        "nicht die 9B-Fassung, nicht das Basismodell, nicht Pixal3D"
    )
    assert ("VAELoader", "trellis_2_shape_vae_bf16.safetensors") in chosen, "nicht die Textur-VAE"
    assert ("VAELoader", "flux2-vae.safetensors") in chosen, "nicht die fremde VAE"
    assert ("CLIPLoader", "qwen_3_4b_fp4_flux2.safetensors") in chosen
    assert ("CLIPVisionLoader", "dino_v3_vit_l.safetensors") in chosen
    assert not any("{model:" in json.dumps(node) for node in graph.values())


def test_an_unknown_model_is_better_than_none() -> None:
    """Im eigenen Ordner kann jede Datei die Aufgabe — dort ist eine besser als keine.

    Das gilt nur fürs Freistellen: ``background_removal`` hält nichts anderes,
    und wer ein Freistellmodell hat, das wir nicht kennen, soll trotzdem
    erzeugen können.
    """

    class Exotic(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if "/object_info/LoadBackgroundRemovalModel" in url:
                return json.dumps(
                    {
                        "LoadBackgroundRemovalModel": {
                            "input": {
                                "required": {"bg_removal_name": [["eigenbau_v3.safetensors"], {}]}
                            }
                        }
                    }
                ).encode()
            return super().__call__(url, body, headers)

    server = Exotic()
    backend(server).image_to_mesh(b"\x89PNG fake")

    names = [
        node["inputs"]["bg_removal_name"]
        for node in server.graphs[0].values()
        if node["class_type"] == "LoadBackgroundRemovalModel"
    ]
    assert names == ["eigenbau_v3.safetensors"]


def test_a_foreign_file_in_a_shared_folder_is_not_the_model() -> None:
    """**Im geteilten Ordner ist „irgendeine Datei“ die falsche** (``ModelRole.strict``).

    Unter ``diffusion_models`` liegen Formkern und Bildmodell neben den
    Modellen anderer Abläufe. Nähme der Bildweg die erste Datei, scheiterte der
    Auftrag mitten im Lauf an einem Videomodell — und die Bereitschaft hätte
    „bereit“ gesagt. Was kein Muster trifft, fehlt.
    """
    from app.core.backends import mesh as mesh_module

    class Foreign(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if "/object_info/UNETLoader" in url:
                return json.dumps(
                    {
                        "UNETLoader": {
                            "input": {"required": {"unet_name": [["wan2.2_t2v.safetensors"], {}]}}
                        }
                    }
                ).encode()
            return super().__call__(url, body, headers)

    server = Foreign()
    generator = backend(server)

    assert "shape" in generator.missing_models("image_to_mesh")
    with pytest.raises(GenerationFailed) as problem:
        generator.image_to_mesh(b"\x89PNG fake")
    assert "Modelldatei" in str(problem.value.detail)
    assert problem.value.values.get("role") == "shape"
    assert not any(url.endswith("/prompt") for url in server.requests), "nichts abgeschickt"
    assert mesh_module.role_candidates("shape", ["wan2.2_t2v.safetensors"]) == []


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
    """Je Eingang eine Frage, nicht eine je Knoten des Graphen.

    Die Zahl steht nicht fest im Test: Wie viele Rollen der mitgelieferte
    Graph benennt, ist eine Frage des Graphen und ändert sich mit ihm. Fest
    steht, dass keine zweimal gefragt wird.
    """
    server = Comfy()
    graph = json.loads((WORKFLOW_DIR / "text_to_mesh.json").read_text(encoding="utf-8"))
    rollen = {
        f"{node['class_type']}.{field}"
        for node in graph.values()
        for field, value in node["inputs"].items()
        if isinstance(value, str) and value.startswith("{model:")
    }

    backend(server).text_to_mesh("ein Halter")

    asked = [entry for entry in server.requests if "/object_info/" in entry]
    assert len(asked) == len(set(asked)) == len(rollen)


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


# --- ComfyUI einrichten (§27, §36) ------------------------------------------------


def test_no_node_of_our_own_travels_with_the_application() -> None:
    """Seit TRELLIS.2 ist jeder Knoten der Abläufe ein eingebauter (RM-003).

    Hier lag ``ComfyUI-TripoSG-Solidon``, ein eigener Knoten samt Abruf eines
    fremden Quelltexts, von dem ein Teil unter einer Tencent-Lizenz ohne EU
    steht. Geprüft wird beides: Es liegt kein Knoten mehr bei den Daten, und
    jede Knotenart der Abläufe stammt laut ComfyUIs eigener Beschreibung aus
    seinem Kern (``nodes`` oder ``comfy_extras``), nicht aus ``custom_nodes``.
    """
    assert not (WORKFLOW_DIR / "comfyui").exists(), "kein eigener Knoten bei den Daten"
    described_nodes = _core_nodes()["nodes"]
    for name in ("image_to_mesh", "text_to_mesh"):
        graph = json.loads((WORKFLOW_DIR / f"{name}.json").read_text(encoding="utf-8"))
        for kind in {str(node["class_type"]) for node in graph.values()}:
            module = described_nodes[kind]["python_module"]
            assert module == "nodes" or module.startswith("comfy_extras."), (name, kind, module)


def test_no_text_the_user_reads_points_at_a_script_the_customer_lacks() -> None:
    """Kein Oberflächentext nennt mehr ``tools/setup_comfyui.py``.

    Zwei taten es: die Zeile der Liste der zusätzlichen Programme und der
    Fehler, der meldet, dass die Knotensammlung fehlt. Beide sprachen zu
    jemandem, der diese Datei nicht hat — sie reist im Paket nicht mit.

    Geprüft werden die Texte, die durch ``_()`` oder ``tr()`` gehen, und nicht
    der Quelltext: Die Kommentare, die diesen Fund erklären, nennen das Skript
    weiterhin, und das sollen sie.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "app"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in ("_", "tr"):
                continue
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    assert "setup_comfyui" not in argument.value, path.name


def _comfyui_folder(tmp_path: Path, version: str | None = "0.37.0") -> Path:
    """Ein ComfyUI-Ordner, wie die Einrichtung ihn findet — mit oder ohne Versionsdatei."""
    comfyui = tmp_path / "ComfyUI"
    (comfyui / "custom_nodes").mkdir(parents=True)
    if version is not None:
        (comfyui / "comfyui_version.py").write_text(
            "# This file is automatically generated by the build process when version is\n"
            "# updated in pyproject.toml.\n"
            f'__version__ = "{version}"\n',
            encoding="utf-8",
        )
    return comfyui


def test_a_comfyui_that_is_too_old_stops_before_any_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Ein zu altes ComfyUI kennt die Knoten nicht — und das sagt die Einrichtung vorher.**

    TRELLIS.2 kam mit v0.34.0 in den Kern, Solidon rechnet ab v0.35.0. Acht
    Gigabyte zu laden und erst beim Erzeugen „unbekannter Knoten“ zu lesen,
    wäre eine halbe Stunde zu spät. Der Satz nennt beide Fassungen und den Weg
    (Regel 17); geladen wird nichts.
    """
    from app.core.backends import comfy_setup

    comfyui = _comfyui_folder(tmp_path, "0.33.2")
    started: list[object] = []
    monkeypatch.setattr(comfy_setup, "_run", lambda *a, **k: started.append(a))
    monkeypatch.setattr(comfy_setup, "_run_repeatedly", lambda *a, **k: started.append(a))

    with pytest.raises(comfy_setup.SetupFailed) as raised:
        comfy_setup.setup(comfyui, weights=True, image_model=True)

    gesagt = str(raised.value)
    assert "0.33.2" in gesagt, "die gefundene Fassung"
    assert "0.35.0" in gesagt, "die nötige Fassung"
    assert "aktualisieren" in gesagt, "und der Weg"
    assert not started, "kein Prozess, kein Download"


@pytest.mark.parametrize("version", [None, "0.35.0", "0.39.0", "1.0.0"])
def test_a_new_enough_or_unknown_comfyui_is_not_stopped(
    tmp_path: Path, version: str | None
) -> None:
    """Ab 0.35.0 geht es weiter — und ohne Versionsdatei auch.

    ComfyUI Desktop hält seinen Programmcode getrennt von dem Ordner, in dem
    Modelle und ``custom_nodes`` liegen; dort steht keine Versionsdatei.
    „Unbekannt“ ist nicht „zu alt“ — dann fragt die Bereitschaft den laufenden
    Server nach seinen Knoten.
    """
    from app.core.backends import comfy_setup

    comfyui = _comfyui_folder(tmp_path, version)

    comfy_setup.check_version(comfyui)
    result = comfy_setup.setup(comfyui, weights=False, image_model=False)
    assert result.done


def test_the_version_is_read_and_never_executed(tmp_path: Path) -> None:
    """Die Versionsdatei gehört einem fremden Programm — gelesen, nicht ausgeführt (Regel 11)."""
    from app.core.backends import comfy_setup

    comfyui = tmp_path
    (comfyui / "comfyui_version.py").write_text(
        'raise SystemExit("ausgeführt")\n__version__ = "0.36.1"\n', encoding="utf-8"
    )
    assert comfy_setup.comfyui_version(comfyui) == (0, 36, 1)
    (comfyui / "comfyui_version.py").write_text("kaputt", encoding="utf-8")
    assert comfy_setup.comfyui_version(comfyui) is None


def test_the_legacy_triposg_setup_is_removed_and_nothing_else(tmp_path: Path) -> None:
    """Was Solidon für TripoSG selbst angelegt hat, geht — am eigenen Zeichen erkannt.

    Der Knotenordner lädt sonst bei jedem Start von ComfyUI den TripoSG-Quelltext
    (RM-003), und die 7,5 GB Gewichte liest kein Ablauf mehr. Was jemand selbst
    in denselben Ordner gelegt hat — ohne unsere Marke —, bleibt.
    """
    from app.core.backends import comfy_setup

    comfyui = _comfyui_folder(tmp_path)
    nodes = comfyui / comfy_setup.LEGACY_NODES
    nodes.mkdir(parents=True)
    for name in ("nodes.py", "__init__.py"):
        (nodes / name).write_text("# alt", encoding="utf-8")
    (nodes / "triposg").mkdir()
    weights = comfyui / comfy_setup.LEGACY_WEIGHTS
    weights.mkdir(parents=True)
    (weights / comfy_setup.LEGACY_MARKER).write_text("{}", encoding="utf-8")
    (weights / "model_index.json").write_text("{}", encoding="utf-8")
    leftover = weights.with_name(weights.name + ".previous-abc")
    leftover.mkdir()
    foreign = comfyui / "custom_nodes" / "ComfyUI-Fremd"
    foreign.mkdir()
    (foreign / "nodes.py").write_text("# fremd", encoding="utf-8")
    seen: list[str] = []

    assert comfy_setup.remove_legacy(comfyui, lambda step: seen.append(str(step))) is True

    assert not nodes.exists() and not weights.exists() and not leftover.exists()
    assert foreign.is_dir(), "ein fremder Knoten bleibt"
    assert seen, "der Schritt sagt, was er tut"
    assert comfy_setup.remove_legacy(comfyui) is False, "beim zweiten Mal ist nichts zu tun"

    # Ohne unsere Marke bleiben Gewichte, die jemand selbst dorthin gelegt hat.
    (weights / "model_index.json").parent.mkdir(parents=True)
    (weights / "model_index.json").write_text("{}", encoding="utf-8")
    assert comfy_setup.remove_legacy(comfyui) is False
    assert (weights / "model_index.json").is_file()


def test_a_folder_without_custom_nodes_is_not_comfyui(tmp_path: Path) -> None:
    """Und der Satz sagt, woran man es erkennt — nicht bloß „nicht gefunden"."""
    from app.core.backends import comfy_setup

    with pytest.raises(comfy_setup.SetupFailed) as raised:
        comfy_setup.find_comfyui(tmp_path)

    assert "custom_nodes" in str(raised.value)


def test_the_folder_above_comfyui_is_accepted_too(tmp_path: Path) -> None:
    """Ein Nutzer zeigt genauso oft auf den Ordner darüber wie auf den richtigen."""
    from app.core.backends import comfy_setup

    (tmp_path / "ComfyUI" / "custom_nodes").mkdir(parents=True)

    assert comfy_setup.find_comfyui(tmp_path) == tmp_path / "ComfyUI"


def test_a_cancelled_setup_keeps_what_it_has(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abgebrochen wird zwischen und in den Schritten, und der Satz dazu sagt,
    dass ein neuer Lauf fortsetzt — sonst fängt jemand von vorn an.
    """
    from app.core.backends import comfy_setup

    comfyui = _comfyui_folder(tmp_path)
    monkeypatch.setattr(comfy_setup, "find_python", lambda _folder: Path("python"))
    started: list[object] = []
    monkeypatch.setattr(comfy_setup, "_run_repeatedly", lambda *a, **k: started.append(a))

    result = comfy_setup.setup(comfyui, cancelled=lambda: True)

    assert not result.done
    assert "setzt fort" in str(result.reason)
    assert not started, "nach dem Abbruch beginnt kein Download"


# --- läuft es, und kennt es die Knoten? (§27) -------------------------------------


def _object_info(known: bool, node: str = "Trellis2Conditioning") -> bytes:
    """Was ComfyUI auf ``/object_info/<knoten>`` antwortet.

    Ein ComfyUI ohne diesen Knoten antwortet mit einem **leeren Objekt** und
    nicht mit einem Fehler — genau daran hängt die Unterscheidung.
    """
    return json.dumps({node: {"input": {}}} if known else {}).encode("utf-8")


def _answers_for(known: set[str], *, with_models: bool = True):
    """Ein ComfyUI, das genau diese Knoten kennt und die übrigen nicht.

    Ein Transport, der auf **jede** Frage denselben Knoten zurückgibt, kann die
    Prüfung nicht abbilden, seit sie den ganzen Ablauf durchgeht — er machte
    aus fünf unbeantworteten Fragen fünf beantwortete.

    ``with_models`` bedient zusätzlich die Modellfragen: Seit die Bereitschaft
    auch prüft, ob die Rollen des Ablaufs zu füllen sind, ist ein Server ohne
    Modelle nicht bereit — und das ist richtig, macht aber einen Fake-Server
    ohne Modelle zum Sonderfall statt zum Normalfall.
    """

    def answer(url: str, data: object, headers: object) -> bytes:
        asked = url.rsplit("/", 1)[-1]
        if with_models and asked in OFFERED_NODES:
            return described(asked)
        return _object_info(asked in known, asked)

    return answer


#: Die Knoten, für die :data:`OFFERED` eine Auswahlliste führt.
OFFERED_NODES = {key.split(".")[0] for key in OFFERED}


def test_a_comfy_that_knows_every_node_of_the_workflow_is_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.backends import mesh as mesh_module

    nodes = mesh_module.ComfyBackend()._graph_nodes()
    assert len(nodes) > 1, "der mitgelieferte Ablauf spricht mehrere Knoten an"

    backend = ComfyBackend(transport=_answers_for(set(nodes)))
    monkeypatch.setattr(mesh_module, "reachable", lambda url, seconds=0.25: True)

    assert backend.readiness() is mesh_module.Readiness.READY
    assert backend.missing_nodes() == ()


def test_some_nodes_alone_are_not_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    """**„Bereit" stand da, und der Auftrag scheiterte trotzdem.**

    Geprüft wurde einmal nur ein Knoten des Ablaufs; abgeschickt scheiterte
    der Auftrag an einem *anderen*. Heute ist der Fall ein ComfyUI vor 0.34:
    Freistellen und Sampler kennt es, TRELLIS.2 nicht. Und der fehlende Name
    gehört in die Auskunft: „ein Knoten fehlt" schickt niemanden weiter
    (Regel 17).
    """
    from app.core.backends import mesh as mesh_module

    nodes = mesh_module.ComfyBackend()._graph_nodes()
    neue = {kind for kind in nodes if "Trellis" in kind}
    alte = set(nodes) - neue
    assert neue and alte, "der Ablauf spricht alte und neue Knoten an"

    # ``with_models=False``: Dieser Test prüft die Knotenfrage. Ein Server, der
    # die Modelle mitbeantwortet, würde damit auch die Knoten bejahen, für die
    # er eine Auswahlliste führt.
    backend = ComfyBackend(transport=_answers_for(alte, with_models=False))
    monkeypatch.setattr(mesh_module, "reachable", lambda url, seconds=0.25: True)

    assert backend.readiness() is mesh_module.Readiness.NO_NODES
    assert set(backend.missing_nodes()) == neue


def test_a_missing_node_says_that_comfyui_is_too_old() -> None:
    """Fehlt ein Knoten, kann Solidon ihn nicht nachlegen — der Weg ist ein neueres ComfyUI.

    Der Satz sagte „Die Knotensammlung fehlt — einrichten unter Zusätzliche
    Programme“. Seit alle Knoten eingebaut sind, wäre das ein Weg ins Leere.
    Die nötige Fassung steht in den Werten, der Satz trägt keine Zahl (§33.1).
    """
    from app.core.backends import mesh as mesh_module
    from app.core.errors import INSTALL_MISSING

    generator = ComfyBackend(transport=lambda url, data, headers: b"{}")

    with pytest.raises(GenerationFailed) as raised:
        generator._offered("Trellis2Conditioning", "clip_vision_model")

    assert "älter" in str(raised.value.detail)
    assert "aktualisieren" in str(raised.value.detail)
    assert raised.value.values["node"] == "Trellis2Conditioning"
    assert raised.value.values["needed"] == mesh_module.MINIMUM_COMFYUI_TEXT
    assert INSTALL_MISSING in raised.value.suggestions


def test_a_comfy_without_our_nodes_says_so_before_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Der Fall, der einen Kunden Minuten kostete.**

    Geprüft wurde, ob ein Port antwortet — und dann stand „Bereit" da, auch
    wenn dieses ComfyUI die Knoten des Ablaufs nicht kennt. Wer es installiert
    und gestartet hatte, ohne sie einzurichten, tippte seinen Satz, drückte
    *Erzeugen*, wartete, und erfuhr es danach.
    """
    from app.core.backends import mesh as mesh_module

    backend = ComfyBackend(transport=lambda url, data, headers: _object_info(False))
    monkeypatch.setattr(mesh_module, "reachable", lambda url, seconds=0.25: True)

    assert backend.readiness() is mesh_module.Readiness.NO_NODES


def test_a_silent_port_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.backends import mesh as mesh_module

    monkeypatch.setattr(mesh_module, "reachable", lambda url, seconds=0.25: False)

    assert ComfyBackend().readiness() is mesh_module.Readiness.ABSENT


def test_something_that_answers_but_not_this_question_claims_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auf dem Port kann alles liegen. Behauptet wird dann nichts."""
    from app.core.backends import mesh as mesh_module

    def gibberish(url: str, data: object, headers: object) -> bytes:
        return b"<html>not comfyui</html>"

    backend = ComfyBackend(transport=gibberish)
    monkeypatch.setattr(mesh_module, "reachable", lambda url, seconds=0.25: True)

    assert backend.readiness() is mesh_module.Readiness.UNKNOWN


def test_the_node_comes_from_the_workflow_and_not_from_a_list() -> None:
    """Wer den Ablauf austauscht, tauscht auch, was geprüft wird (§27).

    Eine zweite Liste im Code wäre am Tag nach dem nächsten Generator falsch.
    """
    nodes = ComfyBackend()._graph_nodes()

    assert nodes, "der Ablauf nennt seine Knoten selbst"
    assert "Trellis2Conditioning" in nodes
    graph = json.loads((WORKFLOW_DIR / "image_to_mesh.json").read_text(encoding="utf-8"))
    assert set(nodes) == {str(entry.get("class_type")) for entry in graph.values()}


def test_a_step_can_be_cancelled_while_it_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Abbrechen wirkte beim längsten Schritt nicht.**

    ``subprocess.run`` blockiert bis zum Ende, und die Abbruchprüfung lag
    *zwischen* den Schritten — einer davon lädt mehrere Gigabyte. Wer abbrach,
    wartete eine halbe Stunde auf einen Download, den er nicht mehr wollte.
    """
    from app.core.backends import comfy_setup

    getoetet: list[bool] = []

    class Endlos:
        """Ein Prozess, der weiterschreibt, bis ihn jemand beendet."""

        def __init__(self) -> None:
            self.stdout = iter(f"lade {n} %\n" for n in range(10_000))

        def __enter__(self) -> object:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def kill(self) -> None:
            getoetet.append(True)

        def wait(self) -> int:
            return 0

    monkeypatch.setattr(comfy_setup.subprocess, "Popen", lambda *a, **k: Endlos())
    gesehen: list[str] = []
    abfragen = iter((False, True))

    with pytest.raises(comfy_setup.Cancelled):
        comfy_setup._run(
            ["python", "-c", "laden"],
            "Modell laden",
            lambda step: gesehen.append(str(step)),
            cancelled=lambda: next(abfragen, True),
        )

    assert getoetet == [True], "der Kindprozess wird beendet, nicht abgewartet"


def test_a_cancelled_setup_says_that_a_new_run_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Und der Satz dazu ist keine Höflichkeit: Es stimmt.

    ``huggingface_hub`` lässt teilweise geladene Dateien im Zwischenordner
    liegen und setzt beim nächsten Lauf fort.
    """
    from app.core.backends import comfy_setup

    comfyui = _comfyui_folder(tmp_path)
    monkeypatch.setattr(comfy_setup, "find_python", lambda _folder: Path("python"))

    def bricht_ab(*_args: object, **_kwargs: object) -> None:
        raise comfy_setup.Cancelled("Modell laden")

    monkeypatch.setattr(comfy_setup, "fetch_background", bricht_ab)

    result = comfy_setup.setup(comfyui, cancelled=lambda: False)

    assert not result.done
    assert "setzt fort" in str(result.reason)


def test_comfyui_desktop_is_found_where_it_says_it_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Der Weg, den ein Kunde am ehesten geht, war der einzige unbekannte.**

    ``comfy.org`` bietet die Desktop-Anwendung als Erstes an, und sie legt ihr
    ComfyUI sechs Ebenen tief unter ``AppData/Local/Comfy-Desktop/`` ab —
    keine der geratenen Stellen trifft das. Gemessen auf dieser Maschine: Der
    Server lief, die Knoten fehlten, und die Einrichtung sagte „an den
    üblichen Stellen nicht gefunden". Die Antwort lag daneben, in einer Datei,
    die die Anwendung selbst schreibt.
    """
    from app.core.backends import comfy_setup

    installiert = tmp_path / "irgendwo" / "ComfyUI"
    (installiert / "ComfyUI" / "custom_nodes").mkdir(parents=True)
    record = tmp_path / comfy_setup.DESKTOP_RECORD
    record.parent.mkdir(parents=True)
    record.write_text(
        json.dumps([{"id": "inst-1", "name": "ComfyUI", "installPath": str(installiert)}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(comfy_setup, "_config_home", lambda: tmp_path)
    # Ohne diese Zeile fände der Test das ComfyUI der Maschine, auf der er läuft.
    monkeypatch.setattr(comfy_setup, "GUESSES", ())

    assert comfy_setup.find_comfyui() == installiert / "ComfyUI"


def test_a_desktop_record_that_makes_no_sense_costs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Datei gehört jemand anderem — ihr Aufbau ist nirgends zugesagt.

    Eine Anwendung, die an fremdem JSON scheitert, ist schlechter als eine,
    die weiter rät. Geprüft werden die vier Formen, in denen es schiefgehen
    kann: nicht da, kein JSON, keine Liste, kein Eintrag mit Pfad.
    """
    from app.core.backends import comfy_setup

    monkeypatch.setattr(comfy_setup, "_config_home", lambda: tmp_path)
    record = tmp_path / comfy_setup.DESKTOP_RECORD
    record.parent.mkdir(parents=True)

    assert comfy_setup._from_desktop() == [], "es gibt die Datei nicht"
    for inhalt in ("{kaputt", '{"nicht": "eine Liste"}', '[{"name": "ohne Pfad"}]', "[7]"):
        record.write_text(inhalt, encoding="utf-8")
        assert comfy_setup._from_desktop() == [], inhalt


def test_the_desktop_record_lives_where_the_platform_puts_it() -> None:
    """Je Plattform ein Ort, und alle drei sind von hier aus prüfbar.

    Eine Funktion statt eines ``if sys.platform`` mitten im Code: Sonst wäre
    diese Zuordnung nur auf der Plattform prüfbar, die gerade läuft — und die
    beiden anderen erst beim Kunden.
    """
    from app.core.backends import comfy_setup

    assert comfy_setup.DESKTOP_RECORD.startswith("Comfy Desktop/")
    assert comfy_setup._desktop_record().name == "installations.json"
    assert comfy_setup._config_home().is_absolute()


def test_setting_up_checks_the_version_first_and_fetches_the_small_part_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Erst die Fassung, dann das Kleine, dann das Große.

    Die Fassung zu lesen kostet nichts und gehört vor jeden Download
    (``kern.md``, „Einrichten heißt nicht laufen“). Das Freistellmodell vor
    TRELLIS.2: Wer abbricht, hat dann wenigstens den Teil, der schnell ging.
    """
    from app.core.backends import comfy_setup

    comfyui = _comfyui_folder(tmp_path)
    reihenfolge: list[str] = []
    real_check = comfy_setup.check_version

    def check(folder: Path) -> None:
        reihenfolge.append("fassung")
        real_check(folder)

    monkeypatch.setattr(comfy_setup, "check_version", check)
    monkeypatch.setattr(comfy_setup, "find_python", lambda _folder: Path("python"))
    monkeypatch.setattr(
        comfy_setup, "fetch_background", lambda *a, **k: reihenfolge.append("freistellen")
    )
    monkeypatch.setattr(
        comfy_setup, "fetch_weights", lambda *a, **k: reihenfolge.append("gewichte")
    )

    comfy_setup.setup(comfyui)

    assert reihenfolge == ["fassung", "freistellen", "gewichte"]


def test_the_weights_are_downloaded_through_a_short_folder() -> None:
    """**MAX_PATH ist 260, und der Pfad war 261 Zeichen lang.**

    ``huggingface_hub`` legt seine halbfertigen Dateien unter dem Ziel ab;
    zusammen mit dem Installationspfad von ComfyUI Desktop riss das die Grenze
    um ein Zeichen. Geladen wird deshalb in einen kurzen Zwischenordner im
    Nutzer-Cache — nicht im gemeinsamen Temp, wo ein fester Name unter Linux
    von jedem anderen Konto vorbelegbar ist — und erst die geprüfte Datei
    wandert ans Ziel. Geprüft wird der Programmtext und nicht ein Lauf: Der
    Lauf lädt Gigabyte.
    """
    from app.core.backends import comfy_setup
    from app.core.paths import user_cache_dir

    programm = comfy_setup._FETCH_FILE
    assert "tempfile" not in programm, "der Zwischenordner kommt nicht aus dem Temp"
    assert "sys.argv[4]" in programm, "sondern von außen, aus app.core.paths"
    assert "shutil.move" in programm, "und danach an seinen Platz gebracht"

    ordner = comfy_setup.scratch_dir("dl-shape")
    assert user_cache_dir() in ordner.parents, "er liegt im Nutzer-Cache"
    assert ordner.is_dir(), "und er ist angelegt, bevor jemand hineinlädt"


def test_the_trellis_files_use_their_fixed_revision_and_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jede Datei mit festem Modellstand und Prüfsumme — bei jedem Einrichten derselbe Stand.

    Ein Modellstand ist ein Commit, keine Gruppe: Wer nach ``main`` lädt,
    bekommt nächste Woche eine andere Datei unter demselben Namen. Und jede
    Datei landet in dem Ordner, in dem ComfyUIs Lader sie suchen.
    """
    from app.core.backends import comfy_setup

    monkeypatch.setattr(comfy_setup, "scratch_dir", lambda name: tmp_path / name)
    monkeypatch.setattr(comfy_setup, "free_gigabytes", lambda _where: 500.0)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        comfy_setup,
        "_run_repeatedly",
        lambda command, *_args, **_kwargs: commands.append(command),
    )
    comfyui = tmp_path / "ComfyUI"

    comfy_setup.fetch_weights(comfyui, Path("python"))

    assert [command[3] for command in commands] == [comfy_setup._FETCH_FILE] * 3
    assert [command[4:7] for command in commands] == [
        [
            str(comfyui / "models" / "diffusion_models"),
            "Comfy-Org/TRELLIS.2",
            "diffusion_models/trellis_2_int8_convrot.safetensors",
        ],
        [
            str(comfyui / "models" / "vae"),
            "Comfy-Org/TRELLIS.2",
            "vae/trellis_2_shape_vae_bf16.safetensors",
        ],
        [
            str(comfyui / "models" / "clip_vision"),
            "Comfy-Org/TRELLIS.2",
            "clip_vision/dino_v3_vit_l.safetensors",
        ],
    ]
    assert [command[-2:] for command in commands] == [
        [
            "430a9d09b2416687018c8fe8edced2ad4858a439",
            "d01952ad137213f6a868f86b6b877026276f84af5eec23069217475a0bad3a31",
        ],
        [
            "430a9d09b2416687018c8fe8edced2ad4858a439",
            "de0cb4949a76c59ee5c091a995a69bcc8c51d5aeda939f0c641a50d2a72341f4",
        ],
        [
            "430a9d09b2416687018c8fe8edced2ad4858a439",
            "5cb785e458de7c460579082418af81f5c62380c181599344bdc60898c63468ee",
        ],
    ]


def test_every_model_file_names_a_fixed_state_a_hash_and_a_role() -> None:
    """Kein Eintrag ohne Commit, Prüfsumme und Rolle — und jede Rolle steht im Ablauf.

    Die Rolle verbindet die Datei mit dem Platzhalter im Ablauf: Liegt sie
    nicht unter einer Rolle, die ein Ablauf benutzt, lädt die Einrichtung
    etwas, das nie gelesen wird.
    """
    import re

    from app.core.backends import comfy_setup
    from app.core.backends.mesh import MODEL_ROLES, role_candidates

    used: set[str] = set()
    for name in ("image_to_mesh", "text_to_mesh"):
        used |= set(
            re.findall(r"\{model:([a-z_]+)\}", (WORKFLOW_DIR / f"{name}.json").read_text("utf-8"))
        )
    files = (*comfy_setup.SHAPE_FILES, comfy_setup.BACKGROUND, *comfy_setup.IMAGE_MODEL_FILES)
    for entry in files:
        assert re.fullmatch(r"[0-9a-f]{40}", entry.revision), entry
        assert re.fullmatch(r"[0-9a-f]{64}", entry.sha256), entry
        assert entry.size > 100_000_000, entry
        assert entry.folder.startswith("models/"), entry
        assert entry.role in MODEL_ROLES and entry.role in used, entry
        assert role_candidates(entry.role, [entry.name]) == [entry.name], (
            f"die Rolle {entry.role} nähme die eigene Datei {entry.name} nicht"
        )
    assert {entry.role for entry in files} == used, "jede Rolle der Abläufe wird geladen"


def test_background_weights_use_a_fixed_revision_and_verify_the_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.backends import comfy_setup

    monkeypatch.setattr(comfy_setup, "scratch_dir", lambda name: tmp_path / name)
    monkeypatch.setattr(comfy_setup, "free_gigabytes", lambda _where: 500.0)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        comfy_setup,
        "_run_repeatedly",
        lambda command, *_args, **_kwargs: commands.append(command),
    )

    comfy_setup.fetch_background(tmp_path / "ComfyUI", Path("python"))

    command = commands[0]
    assert command[-2:] == [
        "5a1bd8ae750548f8cd42e3c8afa854fd3eba0fb1",
        "9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154",
    ]

    payload = "geprüfte Gewichte".encode()
    expected = hashlib.sha256(payload).hexdigest()
    scratch = tmp_path / "scratch"
    target = tmp_path / "target"
    calls: list[tuple[str, str, str]] = []

    def download(
        repo: str,
        name: str,
        *,
        revision: str,
        local_dir: str,
    ) -> str:
        calls.append((repo, name, revision))
        downloaded = Path(local_dir) / name
        downloaded.parent.mkdir(parents=True, exist_ok=True)
        downloaded.write_bytes(payload)
        return str(downloaded)

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(hf_hub_download=download),
    )
    # ``hashlib.file_digest`` gibt es erst ab Python 3.11. Das Programm läuft
    # in ComfyUIs Python, und ComfyUI unterstützt ausdrücklich auch 3.10.
    monkeypatch.setitem(sys.modules, "hashlib", SimpleNamespace(sha256=hashlib.sha256))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "-c",
            str(target),
            "repo",
            "split_files/vae/weights.bin",
            str(scratch),
            "revision",
            expected,
        ],
    )

    exec(comfy_setup._FETCH_FILE, {})

    assert calls == [("repo", "split_files/vae/weights.bin", "revision")]
    assert (target / "weights.bin").read_bytes() == payload, "am Ziel ohne den Repo-Pfad"
    assert not scratch.exists(), "der Zwischenordner ist geräumt"


def test_background_weights_with_a_wrong_hash_never_reach_the_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.backends import comfy_setup

    target = tmp_path / "target"
    scratch = tmp_path / "scratch"

    def download(_repo: str, name: str, **kwargs: object) -> str:
        downloaded = Path(str(kwargs["local_dir"])) / name
        downloaded.parent.mkdir(parents=True, exist_ok=True)
        downloaded.write_bytes(b"falscher Inhalt")
        return str(downloaded)

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(hf_hub_download=download),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["-c", str(target), "repo", "weights.bin", str(scratch), "revision", "0" * 64],
    )

    with pytest.raises(RuntimeError, match="Prüfsumme"):
        exec(comfy_setup._FETCH_FILE, {})

    assert not target.exists()


def test_an_interrupted_background_copy_never_looks_installed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Abbruch beim Laufwerkswechsel darf keine gültig benannte Teildatei lassen."""
    from app.core.backends import comfy_setup

    payload = b"richtige Gewichte"
    comfyui = tmp_path / "ComfyUI"
    target = comfyui / "models" / "background_removal"
    scratch = tmp_path / "scratch"

    def download(_repo: str, name: str, **kwargs: object) -> str:
        downloaded = Path(str(kwargs["local_dir"])) / name
        downloaded.parent.mkdir(parents=True, exist_ok=True)
        downloaded.write_bytes(payload)
        return str(downloaded)

    def interrupted(_source: object, destination: object) -> None:
        Path(str(destination)).write_bytes(b"Teil")
        raise OSError("Kopie unterbrochen")

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(hf_hub_download=download),
    )
    monkeypatch.setattr(shutil, "move", interrupted)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "-c",
            str(target),
            "repo",
            "birefnet.safetensors",
            str(scratch),
            "revision",
            hashlib.sha256(payload).hexdigest(),
        ],
    )

    with pytest.raises(OSError, match="unterbrochen"):
        exec(comfy_setup._FETCH_FILE, {})

    assert not (target / "birefnet.safetensors").exists()
    assert not comfy_setup.background_present(comfyui)


def test_a_broken_download_is_resumed_and_not_thrown_away() -> None:
    """**Der Docstring versprach Fortsetzen, und der Code löschte.**

    Der Ordner hieß ``mkdtemp``, also jedes Mal anders, und ein ``finally``
    räumte ihn auf — zusammen war „setzt beim nächsten Lauf fort" eine Lüge.
    Gemessen an drei Abbrüchen hintereinander auf einer wackeligen Leitung.
    Der feste Name steht in :func:`comfy_setup.scratch_dir`: Zweimal gefragt,
    zweimal derselbe Ordner.
    """
    from app.core.backends import comfy_setup

    programm = comfy_setup._FETCH_FILE
    assert comfy_setup.scratch_dir("dl-shape") == comfy_setup.scratch_dir("dl-shape"), (
        "der Ordner trägt einen festen Namen"
    )
    assert "mkdtemp" not in programm, "sonst liegt das Halbgeladene beim nächsten Mal woanders"
    assert "finally" not in programm, "aufgeräumt wird nur, was gelungen ist"


def test_a_retry_needs_a_new_process_and_not_a_new_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Die Schleife stand im Programm, und dort konnte sie nichts bewirken.**

    ``huggingface_hub`` hält einen globalen HTTP-Client. Sobald ein Fehler ihn
    schließt, antwortet jeder weitere Versuch im selben Prozess mit „Cannot
    send a request, as the client has been closed" — der zweite Anlauf
    scheiterte schneller als der erste und aus einem anderen Grund. Gemessen
    genau so, beim Laden des Freistell-Modells.

    Ein neuer Prozess hat einen neuen Client. Und weil das Halbgeladene in
    einem Ordner mit festem Namen liegt, kostet der Anlauf nur, was fehlt.
    """
    from app.core.backends import comfy_setup

    assert "range(" not in comfy_setup._FETCH_FILE, "die Wiederholung gehört nicht ins Kind"

    laeufe: list[int] = []

    def zweimal_scheitern(command, what, progress, cancelled=None) -> None:
        laeufe.append(1)
        if len(laeufe) < 3:
            raise comfy_setup.SetupFailed("Netz weg")

    monkeypatch.setattr(comfy_setup, "_run", zweimal_scheitern)
    monkeypatch.setattr(comfy_setup, "RETRY_SECONDS", 0.0)
    gesagt: list[str] = []

    comfy_setup._run_repeatedly(["x"], "laden", lambda text: gesagt.append(str(text)))

    assert len(laeufe) == 3, "drei Prozesse, nicht drei Runden in einem"
    assert any("neuer Anlauf" in text for text in gesagt), "und es steht dabei"


def test_a_download_that_never_works_gives_up_and_says_why(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drei Anläufe, dann durch — mit dem Grund des letzten (Regel 17)."""
    from app.core.backends import comfy_setup

    def immer(command, what, progress, cancelled=None) -> None:
        raise comfy_setup.SetupFailed("Netz weg")

    monkeypatch.setattr(comfy_setup, "_run", immer)
    monkeypatch.setattr(comfy_setup, "RETRY_SECONDS", 0.0)

    with pytest.raises(comfy_setup.SetupFailed) as raised:
        comfy_setup._run_repeatedly(["x"], "laden", lambda _text: None)

    assert "Netz weg" in str(raised.value)


def test_the_config_home_is_named_for_every_platform() -> None:
    """Alle drei Orte von hier aus prüfbar — nicht nur der eigene.

    Die Plattform ist ein Parameter, kein ``sys.platform`` mitten im Code:
    Sonst wäre diese Zuordnung nur auf der Plattform prüfbar, die gerade läuft,
    und mypy hielte die anderen Zweige für unerreichbar. Dieselbe Bauart wie
    ``discover.parts_for``.
    """
    from app.core.backends import comfy_setup

    assert comfy_setup._config_home("darwin").parts[-2:] == (
        "Library",
        "Application Support",
    )
    assert comfy_setup._config_home("win32").is_absolute()

    # Der Linux-Zweig folgt ``XDG_CONFIG_HOME`` — geprüft wird das und nicht
    # der Vorgabename: Die Suite biegt die Nutzerverzeichnisse ohnehin um
    # (§38), und ein Test, der auf ``.config`` besteht, prüft die Testumgebung
    # statt den Code.
    import os

    davor = os.environ.get("XDG_CONFIG_HOME")
    try:
        os.environ["XDG_CONFIG_HOME"] = str(Path("/anderswo"))
        assert comfy_setup._config_home("linux") == Path("/anderswo")
        del os.environ["XDG_CONFIG_HOME"]
        assert comfy_setup._config_home("linux").name == ".config"
    finally:
        if davor is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = davor


@pytest.mark.parametrize("name", ["image_to_mesh", "text_to_mesh"])
def test_no_shipped_workflow_needs_a_gpl_node(name: str) -> None:
    """**Regel 15 hing an einer Datendatei, und niemand hatte hingesehen.**

    Beide Abläufe sprachen ``RMBG`` an — den Knoten aus ``ComfyUI-RMBG``, und
    der steht unter GPL-3.0. Damit verlangte Solidon vom Kunden, eine
    GPL-Sammlung zu installieren, damit der Bildweg läuft. Aufgefallen ist es
    erst, als der Weg zum ersten Mal wirklich gefahren wurde: Der Knoten
    fehlte, und in seiner Lizenzdatei stand es in der ersten Zeile.

    ComfyUI kann es seit 0.33 selbst, und die Gewichte sind BiRefNet unter MIT.
    Geprüft wird der Name, weil die Lizenz an ihm hängt — nicht an einer Liste
    daneben, die beim nächsten Ablauf falsch wäre.
    """
    graph = json.loads((WORKFLOW_DIR / f"{name}.json").read_text(encoding="utf-8"))
    kinds = {str(entry.get("class_type")) for entry in graph.values()}

    assert "RMBG" not in kinds, "GPL-3.0 (Regel 15)"
    assert "RemoveBackground" in kinds, "freigestellt wird mit ComfyUIs eigenem Knoten"
    assert "LoadBackgroundRemovalModel" in kinds


@pytest.mark.parametrize("name", ["image_to_mesh", "text_to_mesh"])
def test_every_node_of_a_workflow_gets_its_inputs(name: str) -> None:
    """Jeder Verweis zeigt auf einen Knoten, der da ist, und auf einen Ausgang.

    Der Ablauf ist eine Datendatei, und beim Umbauen verschiebt sich leicht
    eine Nummer — ComfyUI meldet das erst beim Abschicken, und dann steht ein
    Fremdtext im Dialog.
    """
    graph = json.loads((WORKFLOW_DIR / f"{name}.json").read_text(encoding="utf-8"))
    for key, entry in graph.items():
        for field, value in (entry.get("inputs") or {}).items():
            if not isinstance(value, list):
                continue
            assert len(value) == 2, f"{name}.{key}.{field}"
            quelle, ausgang = value
            assert str(quelle) in graph, f"{name}.{key}.{field} zeigt auf {quelle}"
            assert isinstance(ausgang, int), f"{name}.{key}.{field}"


#: Was ComfyUI selbst über die Knoten der Abläufe sagt — erzeugt mit
#: ``tools/comfy_node_info.py`` aus einer echten Installation, nicht getippt.
CORE_NODES = Path(__file__).parent / "data" / "comfyui" / "object_info.json"

#: Platzhalter, die ``mesh._filled`` vor dem Senden durch einen Wert ersetzt.
_VALUE_PLACEHOLDERS = {"{seed}": "INT", "{image}": "COMBO"}

_DYNAMIC_COMBO = "COMFY_DYNAMICCOMBO_V3"


def _core_nodes() -> dict:
    return json.loads(CORE_NODES.read_text(encoding="utf-8"))


def _value_breaks(where: str, spec: list, value: object) -> list[str]:
    """Was an einem festen Wert gegen seine Beschreibung verstößt."""
    from app.core.backends.mesh import _MODEL_PLACEHOLDER, MODEL_ROLES

    kind = spec[0]
    options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    choices = (
        kind if isinstance(kind, list) else options.get("options") if kind == "COMBO" else None
    )
    if isinstance(value, str):
        role = _MODEL_PLACEHOLDER.match(value)
        if role is not None:
            if choices is None:
                return [f"{where}: Modellrolle an einem Eingang ohne Auswahl"]
            return [] if role.group(1) in MODEL_ROLES else [f"{where}: unbekannte Rolle {value}"]
        if value in _VALUE_PLACEHOLDERS:
            expected = _VALUE_PLACEHOLDERS[value]
            matches = choices is not None if expected == "COMBO" else kind == expected
            return [] if matches else [f"{where}: {value} an einem Eingang vom Typ {kind}"]
    if choices is not None:
        return [] if value in choices else [f"{where}: {value!r} steht nicht in der Auswahl"]
    if kind == "INT":
        if not isinstance(value, int) or isinstance(value, bool):
            return [f"{where}: {value!r} ist keine ganze Zahl"]
    elif kind == "FLOAT":
        if not isinstance(value, int | float) or isinstance(value, bool):
            return [f"{where}: {value!r} ist keine Zahl"]
    elif kind == "BOOLEAN":
        return [] if isinstance(value, bool) else [f"{where}: {value!r} ist kein Wahrheitswert"]
    elif kind in ("STRING", "COLOR"):
        return [] if isinstance(value, str) else [f"{where}: {value!r} ist kein Text"]
    else:
        return [f"{where}: ein Wert an einem Eingang vom Typ {kind}, der eine Verbindung will"]
    low, high = options.get("min"), options.get("max")
    if (low is not None and value < low) or (high is not None and value > high):
        return [f"{where}: {value!r} liegt außerhalb von {low}…{high}"]
    return []


def _expected_inputs(definition: dict, given: dict) -> tuple[dict[str, list], list[str]]:
    """Jeder Eingang, den ComfyUI für diesen Knoten mit diesen Werten erwartet.

    Pflicht und optional zählen gleich: Über die HTTP-API muss jeder gesetzt
    sein, denn mancher Knoten liest einen optionalen ungeprüft. Eine
    dynamische Auswahl (``DynamicCombo``) bringt die Eingänge der gewählten
    Option mit, unter ``<auswahl>.<eingang>`` — so baut ComfyUI sie zusammen
    (``comfy_api/latest/_io.py``, ``finalize_prefix``).
    """
    expected: dict[str, list] = {}
    breaks: list[str] = []
    for group in ("required", "optional"):
        for name, spec in (definition.get(group) or {}).items():
            if spec[0] != _DYNAMIC_COMBO:
                expected[name] = spec
                continue
            keys = [option["key"] for option in spec[1]["options"]]
            chosen = given.get(name)
            if chosen not in keys:
                breaks.append(f"{name}: {chosen!r} ist keine Option von {keys}")
                continue
            expected[name] = ["COMBO", {"options": keys}]
            option = next(option for option in spec[1]["options"] if option["key"] == chosen)
            for inner_group in ("required", "optional"):
                for inner, inner_spec in (option["inputs"].get(inner_group) or {}).items():
                    expected[f"{name}.{inner}"] = inner_spec
    return expected, breaks


def _contract_breaks(graph: dict, nodes: dict) -> list[str]:
    """Was dieser Ablauf gegen die Knotenbeschreibungen von ComfyUI verletzt."""
    breaks: list[str] = []
    for key, node in graph.items():
        kind = str(node.get("class_type"))
        where = f"{key}:{kind}"
        if kind not in nodes:
            breaks.append(f"{where}: kein eingebauter Knoten")
            continue
        given = node.get("inputs") or {}
        expected, dynamic = _expected_inputs(nodes[kind]["input"], given)
        breaks += [f"{where}.{entry}" for entry in dynamic]
        breaks += [f"{where}.{name}: fehlt" for name in expected if name not in given]
        breaks += [
            f"{where}.{name}: kennt der Knoten nicht" for name in given if name not in expected
        ]
        for name, value in given.items():
            spec = expected.get(name)
            if spec is None:
                continue
            if isinstance(value, list):
                source, slot = value
                source_kind = str(graph.get(str(source), {}).get("class_type"))
                outputs = nodes.get(source_kind, {}).get("output", [])
                if not isinstance(slot, int) or slot >= len(outputs):
                    breaks.append(f"{where}.{name}: Ausgang {slot} von {source_kind} gibt es nicht")
                    continue
                offered = set(str(outputs[slot]).split(","))
                accepted = set(str(spec[0]).split(",")) if isinstance(spec[0], str) else set()
                if not offered & accepted and "*" not in offered | accepted:
                    breaks.append(f"{where}.{name}: {sorted(offered)} passt nicht zu {spec[0]}")
                continue
            breaks += _value_breaks(f"{where}.{name}", spec, value)
    if not any(
        nodes.get(str(node.get("class_type")), {}).get("output_node") for node in graph.values()
    ):
        breaks.append("kein Ausgabeknoten — ComfyUI führte nichts aus")
    return breaks


def test_the_node_descriptions_come_from_a_comfyui_new_enough() -> None:
    """Geprüft wird gegen eine Fassung, die Solidon voraussetzt — nicht gegen eine ältere."""
    from app.core.backends.mesh import MINIMUM_COMFYUI

    found = tuple(int(part) for part in _core_nodes()["comfyui"].split("."))
    assert found >= MINIMUM_COMFYUI


@pytest.mark.parametrize("name", ["image_to_mesh", "text_to_mesh"])
def test_every_input_of_every_core_node_is_set_as_comfyui_describes_it(name: str) -> None:
    """**Jeder Eingang jedes Knotens, gegen ComfyUIs eigene Beschreibung.**

    Der Ablauf ist eine Datendatei, die ComfyUI erst beim Abschicken prüft —
    und dann steht ein Fremdtext im Dialog. Über die HTTP-API muss jeder
    Eingang gesetzt sein, auch ein optionaler, und kein unbekannter darf
    dabei sein; jede Verbindung führt vom passenden Ausgangstyp, jeder feste
    Wert steht in seiner Auswahl und seinen Grenzen. Die Beschreibungen sind
    die von ComfyUI selbst (``/object_info``), nicht eine Liste in diesem Test.
    """
    graph = json.loads((WORKFLOW_DIR / f"{name}.json").read_text(encoding="utf-8"))

    assert _contract_breaks(graph, _core_nodes()["nodes"]) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("drop", "fehlt"),
        ("extra", "kennt der Knoten nicht"),
        ("choice", "nicht in der Auswahl"),
        ("range", "außerhalb"),
        ("link", "passt nicht"),
        ("dynamic", "keine Option"),
    ],
)
def test_the_contract_check_catches_what_it_promises(change: str, expected: str) -> None:
    """Die Gegenprobe: Jede Art von Bruch, die die Prüfung zusagt, findet sie."""
    graph = json.loads((WORKFLOW_DIR / "image_to_mesh.json").read_text(encoding="utf-8"))
    by_kind = {node["class_type"]: node for node in graph.values()}
    if change == "drop":
        del by_kind["RemeshMesh"]["inputs"]["sign_mode.drop_inverted_components"]
    elif change == "extra":
        by_kind["LoadImage"]["inputs"]["upload"] = "image"
    elif change == "choice":
        by_kind["VaeDecodeStructureTrellis2"]["inputs"]["resolution"] = "48"
    elif change == "range":
        by_kind["Trellis2UpsampleStage"]["inputs"]["target_resolution"] = 512
    elif change == "link":
        by_kind["Trellis2Conditioning"]["inputs"]["image"] = by_kind["RemoveBackground"]["inputs"][
            "bg_removal_model"
        ]
    elif change == "dynamic":
        by_kind["RemeshMesh"]["inputs"]["sign_mode"] = "fast"

    breaks = _contract_breaks(graph, _core_nodes()["nodes"])

    assert any(expected in entry for entry in breaks), breaks


@pytest.mark.parametrize("name", ["image_to_mesh", "text_to_mesh"])
def test_the_remesh_drops_the_inner_hull_and_the_cascade_fits_sixteen_gigabytes(
    name: str,
) -> None:
    """Die zwei Abweichungen von ComfyUIs Vorlage, festgehalten.

    ``RemeshMesh`` im Modus ``udf`` legt um jede geschlossene Fläche eine
    zweite, nach innen gewendete Hülle („the UDF inner shell“, sein eigener
    Tooltip); ``sdf`` taugt nicht, weil das Rohnetz von TRELLIS.2 keinen
    einheitlichen Umlaufsinn hat. Also ``udf`` mit beiden Schaltern, die die
    Innenhülle wegnehmen, und davor ``FillHoles``, damit Außen- und Innenhülle
    nicht durch ein Loch zusammenlaufen. Und die Kaskade endet bei 1024 statt
    1536 Voxeln — 1536 trägt nach den Angaben Dritter erst ab 24 GB.
    """
    graph = json.loads((WORKFLOW_DIR / f"{name}.json").read_text(encoding="utf-8"))
    by_kind = {node["class_type"]: (key, node) for key, node in graph.items()}

    _key, remesh = by_kind["RemeshMesh"]
    assert remesh["inputs"]["sign_mode"] == "udf"
    assert remesh["inputs"]["sign_mode.drop_inverted_components"] is True
    assert remesh["inputs"]["sign_mode.drop_enclosed_components"] is True
    fill_key, _fill = by_kind["FillHoles"]
    assert remesh["inputs"]["mesh"][0] == fill_key, "erst Löcher schließen, dann neu vernetzen"
    _key, upsample = by_kind["Trellis2UpsampleStage"]
    assert upsample["inputs"]["target_resolution"] == 1024
    _key, save = by_kind["SaveGLB"]
    assert save["inputs"]["filename_prefix"].startswith("solidon/")


def _history(job: str, *, error: str = "", node: str = "") -> bytes:
    """Was ``/history/<auftrag>`` sagt, wenn ComfyUI abgebrochen hat."""
    status: dict[str, object] = {"status_str": "error" if error else "success", "completed": False}
    if error:
        status["messages"] = [
            ["execution_start", {"prompt_id": job}],
            ["execution_error", {"node_type": node, "node_id": "5", "exception_message": error}],
        ]
    return json.dumps({job: {"status": status, "outputs": {}}}).encode("utf-8")


def test_a_job_that_failed_says_so_instead_of_waiting_out_the_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Zehn Minuten auf einen toten Auftrag gewartet.**

    Geprüft wurde nur, ob Ausgaben da sind — ein Auftrag, den ComfyUI nach
    Sekunden mit ``execution_error`` beendet hatte, sah genauso aus wie einer,
    der noch rechnet. Am Ende stand „Die Erzeugung hat ihr Zeitlimit erreicht",
    und der Grund hatte die ganze Zeit im Verlauf gestanden: „Torch not
    compiled with CUDA enabled", gemeldet vom Knoten mit Namen. Gemessen an
    einer Maschine mit Intel-Arc-Grafik, wo genau das der Fall ist.

    Der Satz von ComfyUI reist mit: Was dort steht, ist genauer als jede
    Umschreibung, und wer damit zum Support geht, bringt die Zeile mit, die
    weiterhilft.
    """
    from app.core.backends import mesh as mesh_module

    def antwortet(url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        if url.endswith("/prompt"):
            return b'{"prompt_id": "job-1"}'
        if "/object_info/" in url:
            return described(url.rsplit("/", 1)[1])
        if "/history/" in url:
            return _history(
                "job-1", error="Torch not compiled with CUDA enabled", node="TripoSGImageToMesh"
            )
        if url.endswith("/upload/image"):
            return b'{"name": "uploaded.png"}'
        return b""

    generator = ComfyBackend(transport=antwortet, poll_seconds=0.0, timeout_seconds=0.0)

    with pytest.raises(mesh_module.GenerationFailed) as raised:
        generator.image_to_mesh(b"bild")

    problem = raised.value
    assert "abgebrochen" in str(problem.title).lower(), "nicht „Zeitlimit“ — der Auftrag ist tot"
    assert problem.values["reason"] == "Torch not compiled with CUDA enabled"
    assert problem.values["node"] == "TripoSGImageToMesh", "in welchem Schritt es riss"


def test_a_job_still_running_is_not_given_up_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """**Das Zeitlimit gilt dem Hängen, nicht der Langsamkeit.**

    Es stand auf zehn Minuten, gemessen an einer RTX 4080, auf der ein Körper
    dreizehn Sekunden braucht. Auf einer schwächeren Karte dauerte derselbe Lauf
    länger als das Limit: Solidon gab auf, ComfyUI rechnete weiter, und der
    Kunde hatte zehn Minuten gewartet und nichts.
    """

    fragen = {"history": 0}

    def antwortet(url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        if url.endswith("/prompt"):
            return b'{"prompt_id": "job-1"}'
        if "/object_info/" in url:
            return described(url.rsplit("/", 1)[1])
        if url.endswith("/queue"):
            return json.dumps({"queue_running": [[0, "job-1", {}]], "queue_pending": []}).encode()
        if "/history/" in url:
            fragen["history"] += 1
            if fragen["history"] < 4:
                return b"{}"
            return json.dumps(
                {"job-1": {"outputs": {"7": {"meshes": [{"filename": "out.stl"}]}}}}
            ).encode("utf-8")
        if url.endswith("/upload/image"):
            return b'{"name": "uploaded.png"}'
        return stl()

    # Das Limit ist längst um — der Auftrag läuft trotzdem, also wird gewartet.
    generator = ComfyBackend(transport=antwortet, poll_seconds=0.0, timeout_seconds=0.0)

    got = generator.image_to_mesh(b"bild")

    assert got.backend == "comfyui"
    assert fragen["history"] >= 4, "es wurde über das Limit hinaus weitergefragt"


def test_a_queue_that_does_not_know_the_job_lets_the_clock_win(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne Beweis für Leben greift die Zeit — sonst wartete es endlos."""
    from app.core.backends import mesh as mesh_module

    def antwortet(url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        if url.endswith("/prompt"):
            return b'{"prompt_id": "job-1"}'
        if "/object_info/" in url:
            return described(url.rsplit("/", 1)[1])
        if url.endswith("/queue"):
            return json.dumps({"queue_running": [], "queue_pending": []}).encode()
        if "/history/" in url:
            return b"{}"
        if url.endswith("/upload/image"):
            return b'{"name": "uploaded.png"}'
        return b""

    generator = ComfyBackend(transport=antwortet, poll_seconds=0.0, timeout_seconds=0.0)

    with pytest.raises(mesh_module.GenerationFailed) as raised:
        generator.image_to_mesh(b"bild")

    assert "Zeitlimit" in str(raised.value)


@pytest.mark.parametrize(
    ("form", "beschrieben"),
    [
        ("klassisch", {"required": {"bg_removal_name": [["birefnet.safetensors"], {}]}}),
        (
            "neu",
            {"required": {"bg_removal_name": ["COMBO", {"options": ["birefnet.safetensors"]}]}},
        ),
    ],
)
def test_both_shapes_of_a_choice_list_are_read(form: str, beschrieben: dict) -> None:
    """**Zwei Formen, und beide kommen aus demselben Server.**

    Klassisch steht die Auswahlliste als erstes Element
    (``[["a.safetensors"], {…}]``) — ein Typname wie ``"INT"`` steht an
    derselben Stelle und ist keine. Die neuen eingebauten Knoten schreiben
    statt der Liste ``"COMBO"`` und legen die Namen daneben.

    Gemessen an einem ComfyUI 0.33: ``UNETLoader`` klassisch,
    ``LoadBackgroundRemovalModel`` neu. Wer nur die alte Form liest, hält jede
    neue Auswahl für leer und meldet „es fehlt die Modelldatei", obwohl sie
    daliegt — genau das ist passiert, und jeder künftige eingebaute Knoten wird
    die neue Form haben.
    """

    def antwortet(url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        return json.dumps({"LoadBackgroundRemovalModel": {"input": beschrieben}}).encode("utf-8")

    generator = ComfyBackend(transport=antwortet)

    assert generator._offered("LoadBackgroundRemovalModel", "bg_removal_name") == [
        "birefnet.safetensors"
    ], form


def test_a_type_name_is_not_a_choice_list() -> None:
    """``["INT", {...}]`` steht an derselben Stelle und ist keine Auswahl.

    Die Unterscheidung ist der Grund, warum die neue Form ausdrücklich auf
    ``"COMBO"`` prüft und nicht einfach jede Zeichenkette nimmt.
    """

    def antwortet(url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        return json.dumps(
            {"KSampler": {"input": {"required": {"steps": ["INT", {"default": 20}]}}}}
        ).encode("utf-8")

    assert ComfyBackend(transport=antwortet)._offered("KSampler", "steps") == []


def test_the_text_way_is_checked_against_its_own_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Der Textweg wurde am Bildweg gemessen.**

    Er spricht andere Knoten an und braucht ein Modell mehr: TRELLIS.2 kennt
    keinen Texteingang, Text wird erst mit FLUX.2 zu einem Bild. Geprüft wurde
    immer ``image_to_mesh`` — wer kein Bildmodell hatte, las „Bereit" und
    erfuhr es beim Abschicken.
    """
    from app.core.backends import mesh as mesh_module

    bild = set(ComfyBackend()._graph_nodes("image_to_mesh"))
    text = set(ComfyBackend()._graph_nodes("text_to_mesh"))
    assert text - bild, "der Textweg spricht Knoten an, die der Bildweg nicht braucht"

    # Ein ComfyUI, das nur den Bildweg kennt. ``with_models=False``, weil
    # dieser Test die Knotenfrage prüft: Ein Server, der die Modelle
    # mitbeantwortet, bejaht damit auch die Knoten, für die er eine
    # Auswahlliste führt.
    backend = ComfyBackend(transport=_answers_for(bild, with_models=False))
    monkeypatch.setattr(mesh_module, "reachable", lambda url, seconds=0.25: True)

    # Ohne Modelle ist der Bildweg nicht „bereit", aber er hat alle Knoten —
    # und genau das trennt die beiden Lagen.
    assert backend.missing_nodes("image_to_mesh") == ()
    assert backend.readiness("text_to_mesh") is mesh_module.Readiness.NO_NODES
    assert set(backend.missing_nodes("text_to_mesh")) == text - bild


def test_a_missing_model_is_its_own_state_and_not_a_missing_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Ein fehlendes Modell ist kein zu altes ComfyUI.**

    Beides führte zu „Erzeugen" und dann zu einem Fehler, aber die Handlungen
    sind verschieden: Modelle lädt Solidons Einrichtung, ein neueres ComfyUI
    holt der Kunde selbst. Vier Lagen statt drei, und jede zieht einen anderen
    Satz nach sich.
    """
    from app.core.backends import mesh as mesh_module

    nodes = set(ComfyBackend()._graph_nodes("text_to_mesh"))
    # Alle Knoten da, aber keine Auswahllisten — also kein Modell.
    backend = ComfyBackend(transport=_answers_for(nodes, with_models=False))
    monkeypatch.setattr(mesh_module, "reachable", lambda url, seconds=0.25: True)

    assert backend.readiness("text_to_mesh") is mesh_module.Readiness.NO_MODEL
    assert {"image", "shape"} <= set(backend.missing_models("text_to_mesh"))


def test_a_ready_comfy_says_nothing_about_missing_models() -> None:
    """Wo alles da ist, fehlt nichts — auch keine Rolle."""
    nodes = set(ComfyBackend()._graph_nodes("image_to_mesh"))
    backend = ComfyBackend(transport=_answers_for(nodes))

    assert backend.missing_models("image_to_mesh") == ()


# --- Platz vor dem Download -------------------------------------------------------


def _shape_gigabytes() -> float:
    """Was der Bildweg an Platz verlangt: seine Dateien und die Luft dazu."""
    from app.core.backends import comfy_setup

    return (
        sum(entry.size for entry in comfy_setup.SHAPE_FILES) / 1_000_000_000
        + comfy_setup.HEADROOM_GIGABYTES
    )


def test_the_weights_are_not_fetched_onto_a_full_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein großer Download stirbt an einer vollen Platte, und die Meldung lügt.

    Am 23.08.2026 lief er dreimal an und starb dreimal nach Minuten, weil ``C:``
    voll war. Was huggingface dabei meldet, nennt den Grund mit keinem Wort:

        RuntimeError: File reconstruction error: Internal Writer Error:
        Background writer channel closed

    Geprüft wird deshalb **vorher**: Ein Problem nach zwei Sekunden zu melden
    ist mehr wert als nach zwanzig Minuten.
    """
    from app.core.backends import comfy_setup

    monkeypatch.setattr(comfy_setup, "free_gigabytes", lambda _where: 2.5)

    with pytest.raises(comfy_setup.SetupFailed) as fehler:
        comfy_setup.fetch_weights(tmp_path, Path("python"))

    gesagt = str(fehler.value)
    assert "2.5" in gesagt or "2,5" in gesagt, f"nennt den freien Platz nicht: {gesagt}"
    needed = f"{_shape_gigabytes():.1f}".replace(".", ",")
    assert needed in gesagt, f"nennt nicht, wie viel gebraucht wird: {gesagt}"


def test_enough_room_lets_the_download_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenrichtung: Bei genug Platz hält die Prüfung nicht auf.

    Ohne diesen Test wäre eine Prüfung, die **immer** wirft, genauso grün.
    """
    from app.core.backends import comfy_setup

    monkeypatch.setattr(comfy_setup, "free_gigabytes", lambda _where: 500.0)
    gerufen: list[str] = []
    monkeypatch.setattr(comfy_setup, "_run_repeatedly", lambda *a, **k: gerufen.append("los"))

    comfy_setup.fetch_weights(tmp_path, Path("python"))

    assert gerufen == ["los"] * len(comfy_setup.SHAPE_FILES), (
        "die Prüfung hat den Download aufgehalten, obwohl Platz war"
    )


def test_a_half_finished_download_is_not_blocked_by_the_space_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was schon liegt, zählt mit — sonst verweigert die Prüfung die Wiederaufnahme.

    ``_run_repeatedly`` setzt einen abgebrochenen Download dort fort, wo er
    stand: Nur was fehlt, wird noch geholt. Eine Platzprüfung, die den bereits
    belegten Platz ignoriert, blockiert **ausgerechnet den zweiten Anlauf**.
    Die Bruchstücke liegen im Zwischenordner, nicht am Ziel.
    """
    from app.core.backends import comfy_setup

    needed = _shape_gigabytes()
    scratch = comfy_setup.scratch_dir("dl-shape")

    # 6 MB statt der echten Gigabyte: Der Test soll die **Rechnung** prüfen,
    # nicht die Platte füllen. Die freie Menge liegt darum knapp unter der
    # Schwelle, sodass erst der Zuschlag sie überschreitet.
    (scratch / "halb.safetensors").write_bytes(b"x" * 6_000_000)

    monkeypatch.setattr(
        comfy_setup,
        "free_gigabytes",
        lambda where: needed - 0.003 if where == scratch else 500.0,
    )
    gerufen: list[str] = []
    monkeypatch.setattr(comfy_setup, "_run_repeatedly", lambda *a, **k: gerufen.append("los"))

    comfy_setup.fetch_weights(tmp_path, Path("python"))

    assert gerufen, "die Prüfung hat den zweiten Anlauf blockiert"


def test_the_space_is_measured_where_the_download_lands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gemessen wurde der falsche Datenträger — und zwar seit dem Umbau.

    Geladen wird in den Nutzer-Cache (unter Windows ``%LOCALAPPDATA%``). Roberts
    Aufbau ist genau der Fall: ComfyUI liegt auf ``D:`` mit viel Platz, ``C:``
    ist knapp — die Prüfung meldete grün, und der Download starb zwanzig
    Minuten später an der vollen Platte.

    Und die Absage nennt den Ort (Regel 17): „auf dem Datenträger ist zu wenig
    Platz" schickt niemanden weiter, der zwei Datenträger hat.
    """
    from app.core.backends import comfy_setup

    scratch = comfy_setup.scratch_dir("dl-shape")
    monkeypatch.setattr(
        comfy_setup, "free_gigabytes", lambda where: 2.5 if where == scratch else 500.0
    )
    gerufen: list[str] = []
    monkeypatch.setattr(comfy_setup, "_run_repeatedly", lambda *a, **k: gerufen.append("los"))

    with pytest.raises(comfy_setup.SetupFailed) as fehler:
        comfy_setup.fetch_weights(tmp_path, Path("python"))

    gesagt = str(fehler.value)
    assert not gerufen, "der Download lief trotz voller Platte an"
    assert str(scratch) in gesagt, f"nennt den Ort nicht, an dem der Platz fehlt: {gesagt}"


def test_the_target_volume_is_checked_as_well(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Und der Zwischenordner allein genügt nicht.

    ``shutil.move`` verschiebt innerhalb eines Datenträgers und **kopiert** über
    seine Grenze hinweg. Liegt der Cache auf ``C:`` und ComfyUI auf ``D:``, muss
    der Platz zweimal da sein — einmal zum Laden, einmal am Ziel. Geprüft werden
    deshalb beide, und die Meldung sagt, welcher der beiden es ist.
    """
    from app.core.backends import comfy_setup

    scratch = comfy_setup.scratch_dir("dl-shape")
    ziel = tmp_path / "models"
    monkeypatch.setattr(
        comfy_setup, "free_gigabytes", lambda where: 500.0 if where == scratch else 1.0
    )
    gerufen: list[str] = []
    monkeypatch.setattr(comfy_setup, "_run_repeatedly", lambda *a, **k: gerufen.append("los"))

    with pytest.raises(comfy_setup.SetupFailed) as fehler:
        comfy_setup.fetch_weights(tmp_path, Path("python"))

    gesagt = str(fehler.value)
    assert not gerufen, "der Download lief an, obwohl das Ziel ihn nicht fassen kann"
    assert str(ziel) in gesagt, f"nennt den Ort nicht, an dem der Platz fehlt: {gesagt}"


def test_the_sizes_come_from_the_files_and_not_from_the_keyboard() -> None:
    """Was Dialog, Handbuch und Fortschritt an Größe nennen, rechnet sich aus den Dateien.

    Bis zum 24.08.2026 standen die Größen von Hand im Fortschrittstext, und
    eine Konstante daneben las niemand — der Kommentar sprach von 444 MB, die
    Konstante von 445. Jetzt setzt der Text die Zahl aus der Konstante ein,
    und die Konstante ist die Summe der Dateien. Keine Zeichenkette, die durch
    ``_()`` geht, trägt mehr eine getippte Größe.
    """
    import ast
    import math
    import re

    from app.core.backends import comfy_setup

    shape = sum(entry.size for entry in (*comfy_setup.SHAPE_FILES, comfy_setup.BACKGROUND))
    image = sum(entry.size for entry in comfy_setup.IMAGE_MODEL_FILES)
    assert round(shape / 1e9, 1) == comfy_setup.WEIGHT_GIGABYTES
    assert round(image / 1e9, 1) == comfy_setup.IMAGE_MODEL_GIGABYTES
    assert math.ceil(comfy_setup.BACKGROUND.size / 1e6) == comfy_setup.BACKGROUND_MEGABYTES

    tree = ast.parse(Path(comfy_setup.__file__).read_text(encoding="utf-8"))
    texts = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]
    sized = [text for text in texts if re.search(r"\b[GM]B\b", text)]
    assert sized, "kein Text mit Größe gefunden — der Test prüfte nichts"
    for text in sized:
        assert not re.search(r"\d\s*[GM]B\b", text), f"getippte Größe in {text!r}"


# --- Eine Adresse aus Nutzerhand (24.08.2026) -------------------------------------


def test_a_folder_in_the_comfy_address_is_unreachable_and_not_a_crash() -> None:
    """Derselbe Fall wie bei Ollama, zweite Datei.

    ComfyUI ist der zweite Dienst, dessen Adresse jemand von Hand einträgt —
    und ``reachable`` fing hier nur ``OSError``. Mit einem Pfad im Feld liest
    ``urlparse`` alles hinter ``C:`` als Port und wirft beim Zugriff darauf.
    """
    from app.core.backends import mesh

    assert mesh.reachable(r"http://C:\Users\Jemand\ComfyUI") is False
    assert mesh.reachable(r"C:\Users\Jemand\ComfyUI") is False


def test_a_broken_comfy_address_says_what_belongs_there() -> None:
    """Und sie sagt es **anders** als „ComfyUI antwortet nicht".

    Zwei Lagen, zwei Handlungen: Läuft der Dienst nicht, hilft der Dienst;
    ist die Adresse Unsinn, hilft nur das Feld in den Einstellungen. Der Satz
    nennt deshalb ein Beispiel — wer noch nie eine Dienstadresse eingetragen
    hat, weiß sonst nicht, wie eine aussieht (Regel 17).
    """
    from app.core.backends import mesh
    from app.core.errors import AppError

    with pytest.raises(AppError) as raised:
        mesh.fetch(r"http://C:\Users\Jemand\ComfyUI")

    text = f"{raised.value.title} {raised.value.detail}"
    assert "127.0.0.1:8188" in text, "ohne Beispiel weiß niemand, wie eine Adresse aussieht"
    assert raised.value.suggestions, "ein Fehler endet nie ohne Handlung"


# --- Die Adresse, so wie sie weitergegeben wird (Review 25.08.2026) ----------------


def test_an_address_without_a_scheme_is_the_normal_way_to_write_one() -> None:
    """**„127.0.0.1:8188" war dauerhaft „nicht erreichbar".**

    So schreibt ComfyUI seine eigene Adresse in die Startzeile, und so gibt
    jeder sie weiter. ``urlparse`` fand darin keinen Rechnernamen, der
    Generator blieb ausgegraut, und der einzige Satz, der auf das Feld gezeigt
    hätte („Die Adresse von ComfyUI ist keine Adresse"), war unerreichbar —
    weil vorher schon niemand mehr fragte.
    """
    from app.core.backends.mesh import comfy_base

    assert comfy_base("127.0.0.1:8188") == "http://127.0.0.1:8188"
    assert comfy_base("http://127.0.0.1:8188/") == "http://127.0.0.1:8188"
    assert comfy_base("") == "http://127.0.0.1:8188", "leer heißt: diese Maschine"
    assert comfy_base("https://rechner:8188/comfy") == "https://rechner:8188/comfy", (
        "ein eigener Pfad bleibt stehen — hinter einem Reverse-Proxy liegt er dort"
    )


def test_every_request_goes_to_the_normalised_address() -> None:
    server = Comfy()
    generator = ComfyBackend(transport=server, poll_seconds=0.0, url="127.0.0.1:8188")

    generator.text_to_mesh("ein Halter", seed=1)

    assert all(entry.startswith("http://127.0.0.1:8188/") for entry in server.requests), (
        server.requests
    )


# --- Abbrechen wirkt, solange gewartet wird ----------------------------------------


def _cancel_and_collect(server: Comfy) -> list[tuple[str, dict]]:
    """Bricht einen laufenden Auftrag ab und gibt zurück, was dabei gesendet wurde."""
    from app.core.errors import OperationCancelled

    generator = ComfyBackend(transport=server, poll_seconds=0.0)
    versuche = {"n": 0}

    def abgebrochen() -> bool:
        versuche["n"] += 1
        return versuche["n"] > 2

    with pytest.raises(OperationCancelled):
        generator.text_to_mesh("ein Halter", cancelled=abgebrochen)

    return [
        (urlsplit(url).path.lstrip("/"), json.loads((body or b"{}").decode("utf-8")))
        for url, body in server.posts
    ]


def test_a_running_generation_can_be_cancelled() -> None:
    """Der aktuelle Server bekommt einen atomaren Abbruch genau der eigenen ID."""

    class Running(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if url.endswith("/api/jobs/job-1/cancel"):
                self.posts.append((url, body))
                return b'{"cancelled": true}'
            return super().__call__(url, body, headers)

    posts = _cancel_and_collect(Running(ready_after=99))

    assert ("api/jobs/job-1/cancel", {}) in posts
    assert not [entry for entry in posts if entry[0] in {"interrupt", "queue"}]
    assert ("free", {"unload_models": True, "free_memory": True}) in posts


def test_cancelling_a_waiting_job_leaves_a_foreign_job_alone() -> None:
    """Ohne Job-Endpunkt wird nur die eigene wartende ID entfernt."""

    class Queued(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if url.endswith("/api/jobs/job-1/cancel"):
                self.posts.append((url, body))
                raise GenerationFailed()
            if url.endswith("/queue") and body is None:
                return json.dumps(
                    {"queue_running": [[0, "fremd", {}]], "queue_pending": [[1, "job-1"]]}
                ).encode()
            return super().__call__(url, body, headers)

    posts = _cancel_and_collect(Queued(ready_after=99))

    assert ("queue", {"delete": ["job-1"]}) in posts
    assert not [entry for entry in posts if entry[0] == "interrupt"], (
        "der eigene Auftrag wartete nur — unterbrochen worden wäre der fremde"
    )


@pytest.mark.parametrize("reply", (None, b"", b"[]", b'{"cancelled": "true"}', b'{"cancelled": 1}'))
def test_legacy_cancellation_never_interrupts_the_next_job(reply: bytes | None) -> None:
    """Der eigene Auftrag endet zwischen Anfrage und Löschversuch; der nächste bleibt heil."""
    running = "job-1"
    pending = ["job-1", "foreign-pending"]
    interrupted: list[str] = []
    posts: list[tuple[str, dict]] = []

    def transport(url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        nonlocal running
        path = urlsplit(url).path.lstrip("/")
        if body is None:
            return json.dumps({"queue_running": [[0, running, {}]], "queue_pending": []}).encode()
        values = json.loads(body)
        posts.append((path, values))
        if path == "api/jobs/job-1/cancel":
            if reply is None:
                raise GenerationFailed()
            return reply
        if path == "queue":
            pending[:] = [job for job in pending if job not in values.get("delete", [])]
            running = "foreign-running"
        elif path == "interrupt":
            # ComfyUI 0.3.51 ignoriert den Rumpf des globalen Endpunkts.
            interrupted.append(running)
        return b"{}"

    ComfyBackend(transport=transport)._cancel_job("job-1")

    assert not interrupted
    assert pending == ["foreign-pending"]
    assert posts == [("api/jobs/job-1/cancel", {}), ("queue", {"delete": ["job-1"]})]


@pytest.mark.parametrize("cancelled", (True, False))
def test_job_cancellation_acknowledgement_needs_no_global_fallback(cancelled: bool) -> None:
    """Auch ein bestätigtes No-op für einen fertigen Job löst keinen weiteren Eingriff aus."""
    posts: list[tuple[str, bytes | None]] = []

    def transport(url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        posts.append((url, body))
        return json.dumps({"cancelled": cancelled}).encode()

    ComfyBackend(url="http://127.0.0.1:8188/comfy", transport=transport)._cancel_job("id/+?#")

    assert posts == [("http://127.0.0.1:8188/comfy/api/jobs/id%2F%2B%3F%23/cancel", b"{}")]


def test_legacy_running_job_releases_the_local_wait_and_ai_slot() -> None:
    """Der alte Server darf weiterrechnen; Solidons Abbruch und lokale Sperre enden trotzdem."""
    from app.core.backends import resources

    class Legacy(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if url.endswith("/api/jobs/job-1/cancel"):
                self.posts.append((url, body))
                raise GenerationFailed()
            if url.endswith("/queue") and body is None:
                return b'{"queue_running": [[0, "job-1", {}]], "queue_pending": []}'
            return super().__call__(url, body, headers)

    posts = _cancel_and_collect(Legacy(ready_after=99))

    assert ("queue", {"delete": ["job-1"]}) in posts
    assert not [entry for entry in posts if entry[0] == "interrupt"]
    acquired = resources._LOCAL_AI_LOCK.acquire(blocking=False)
    try:
        assert acquired, "der aufgegebene Lauf hält Solidons lokale KI-Sperre weiter"
    finally:
        if acquired:
            resources._LOCAL_AI_LOCK.release()


def test_failed_cancel_endpoints_do_not_hide_the_requested_cancellation() -> None:
    """Fehler der Gegenstelle ersetzen OperationCancelled nicht durch einen Folgefehler."""

    class Unreachable(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            if url.endswith(("/cancel", "/queue")) and body is not None:
                self.posts.append((url, body))
                raise GenerationFailed()
            return super().__call__(url, body, headers)

    posts = _cancel_and_collect(Unreachable(ready_after=99))
    assert ("api/jobs/job-1/cancel", {}) in posts
    assert ("queue", {"delete": ["job-1"]}) in posts
    assert not [entry for entry in posts if entry[0] == "interrupt"]


def test_a_successful_local_generation_releases_comfy_models() -> None:
    """Nach dem Import gehört der Grafikspeicher wieder Viewport und Schichtanalyse."""
    server = Comfy()

    ComfyBackend(transport=server, poll_seconds=0.0).text_to_mesh("ein Halter")

    assert any(
        url.endswith("/free")
        and json.loads((body or b"{}").decode("utf-8"))
        == {"unload_models": True, "free_memory": True}
        for url, body in server.posts
    )


def test_a_remote_comfy_server_is_not_unloaded() -> None:
    """Ein geteilter Server auf einem anderen Rechner gehört nicht Solidon allein."""
    server = Comfy()

    ComfyBackend(url="http://192.0.2.1:8188", transport=server, poll_seconds=0.0).text_to_mesh(
        "ein Halter"
    )

    assert not any(url.endswith("/free") for url, _body in server.posts)


def test_without_a_callback_nothing_changes() -> None:
    """Ein Backend ohne Abbruchwunsch läuft wie zuvor — der Rückruf ist eine
    Zugabe, keine Voraussetzung."""
    server = Comfy()

    result = ComfyBackend(transport=server, poll_seconds=0.0).text_to_mesh("ein Halter")

    assert result.mesh.triangle_count == 12


def test_the_scripted_backend_answers_the_same_question() -> None:
    """Damit ein Test den Abbruchweg fahren kann, ohne eine Grafikkarte."""
    from app.core.errors import OperationCancelled

    doppel = ScriptedMeshBackend(fallback=stl())

    with pytest.raises(OperationCancelled):
        doppel.text_to_mesh("egal", cancelled=lambda: True)


# --- Ein schweigender Kindprozess friert die Einrichtung nicht mehr ein ------------


def test_a_silent_child_process_is_still_cancellable() -> None:
    """**„Zwischen den Zeilen fragen" reichte nicht, denn manche Schritte
    schweigen.**

    ``for raw in process.stdout`` blockiert, bis eine Zeile kommt. Kommt keine
    — ein Klon, der auf eine Anmeldung wartet, ein Download hinter einer toten
    Verbindung —, kam auch die Abbruchprüfung nicht dran: *Abbrechen* wirkte
    nicht, und die Stunde aus ``STEP_TIMEOUT_SECONDS`` verstrich nie, weil
    niemand auf die Uhr sah.

    Gefahren wird gegen ein echtes Python, das nichts ausgibt und wartet.
    """
    import sys
    import time

    from app.core.backends import comfy_setup

    begonnen = time.monotonic()
    with pytest.raises(comfy_setup.Cancelled):
        comfy_setup._run(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            "Warten auf nichts",
            comfy_setup._silent,
            lambda: True,
        )

    assert time.monotonic() - begonnen < 10.0, "der Abbruch wartet nicht auf den Prozess"


def test_a_step_cancelled_before_launch_never_starts_a_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein schon gesetzter Abbruch gilt vor dem nächsten Teilprozess."""
    from app.core.backends import comfy_setup

    started: list[list[str]] = []

    def start(command: list[str], **_kwargs: object) -> object:
        started.append(command)
        raise AssertionError("Der Kindprozess hätte nicht starten dürfen")

    monkeypatch.setattr(comfy_setup.subprocess, "Popen", start)

    with pytest.raises(comfy_setup.Cancelled):
        comfy_setup._run(
            [sys.executable, "-c", "pass"],
            "Schon abgebrochen",
            comfy_setup._silent,
            lambda: True,
        )

    assert not started


def test_a_silent_child_process_still_hits_its_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dieselbe Stelle, die andere Richtung: Die Frist gilt auch ohne Ausgabe."""
    import sys

    from app.core.backends import comfy_setup

    monkeypatch.setattr(comfy_setup, "STEP_TIMEOUT_SECONDS", 0.3)

    with pytest.raises(comfy_setup.SetupFailed):
        comfy_setup._run(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            "Warten auf nichts",
            comfy_setup._silent,
        )


def test_a_talking_child_process_still_gets_its_output_read() -> None:
    """Und was gesagt wird, kommt weiter an — sonst stünde im Fehlerfall nichts
    da."""
    import sys

    from app.core.backends import comfy_setup

    with pytest.raises(comfy_setup.SetupFailed) as gefangen:
        comfy_setup._run(
            [sys.executable, "-c", "print('so nicht'); raise SystemExit(3)"],
            "Ein Schritt",
            comfy_setup._silent,
        )

    assert "so nicht" in str(gefangen.value)


def test_a_dropped_connection_is_not_a_program_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    """ComfyUI legt mitten in der Antwort auf — und Solidon sagt, was hilft.

    **Der Zwilling eines Kundenfehlers vom 26.08.2026** (S-20260826-1db075):
    Dort war es Ollama, hier ist es ComfyUI, und die Lücke ist dieselbe.
    ``fetch`` fing ``HTTPError``, ``URLError`` und kaputte Adressen; urllib
    wickelt einen Verbindungsfehler beim **Aufbau** in ``URLError``, beim
    **Lesen der Antwort** nicht. Dort kam ``ConnectionResetError`` nackt durch
    und wurde zu „Im Programm ist ein unerwarteter Fehler aufgetreten."

    Der eigene Satz lohnt sich, weil der Kunde etwas anderes tun muss als bei
    „ComfyUI läuft nicht": Hier hat es angefangen und mittendrin aufgelegt —
    meist, weil ein Modell den Speicher sprengt. „Läuft es?" wäre die falsche
    Frage.
    """
    from app.core.backends import mesh

    def abgerissen(request: object, timeout: float = 0.0) -> object:
        raise ConnectionResetError(10054, "An existing connection was forcibly closed")

    monkeypatch.setattr(mesh, "opener_for", _opened_by(abgerissen))

    with pytest.raises(GenerationFailed) as gefangen:
        mesh.fetch("http://127.0.0.1:8188/prompt", b"{}")

    satz = str(gefangen.value.title)
    assert "unerwartet" not in satz.lower(), "kein Programmfehler, sondern ein Fremdprogramm"
    assert "unterbrochen" in satz.lower(), "und der Satz nennt, was geschah"
    # Regel 17: nie ohne Weg. Der Grund steht daneben, nicht im Satz.
    assert str(gefangen.value.detail)


def test_a_chosen_model_beats_every_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    """**Die Rollenauflösung rät gut und rät trotzdem.**

    ``prefer`` trifft das Übliche. Aber wer die fp8- und die bf16-Fassung
    nebeneinander hat, hat sie aus einem Grund, und der steht in keinem
    Muster. Genau wie beim Sprachmodell gehört die Wahl dem Kunden.
    """
    from app.core.backends import mesh as mesh_module

    gemerkt: dict[str, str] = {}
    monkeypatch.setattr(
        mesh_module, "configured_model", lambda role: gemerkt.get(role, mesh_module.AUTOMATIC)
    )

    backend = mesh_module.ComfyBackend()
    angeboten = {
        "UNETLoader.unet_name": [
            "flux-2-klein-9b.safetensors",
            "flux-2-klein-4b-fp8.safetensors",
            "flux-2-klein-4b.safetensors",
        ]
    }

    # Ohne Wahl gewinnt das Muster — die 9B-Fassung ist ausgeschlossen.
    ohne = backend._pick("image", "UNETLoader", "unet_name", dict(angeboten))
    assert ohne == "flux-2-klein-4b-fp8.safetensors"

    # Mit Wahl gewinnt der Kunde — auch gegen die eigene Rangfolge.
    gemerkt["image"] = "flux-2-klein-4b.safetensors"
    mit = backend._pick("image", "UNETLoader", "unet_name", dict(angeboten))
    assert mit == "flux-2-klein-4b.safetensors"


def test_a_chosen_model_that_is_gone_falls_back_quietly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine gemerkte Datei kann gelöscht oder umbenannt worden sein.

    Dann ist der stille Rückfall auf die Rollenauflösung besser als ein
    Auftrag, der an einem Namen scheitert, den niemand mehr kennt — der Kunde
    hat die Datei bewegt, nicht Solidon.
    """
    from app.core.backends import mesh as mesh_module

    monkeypatch.setattr(mesh_module, "configured_model", lambda role: "gibtsnichtmehr.safetensors")

    backend = mesh_module.ComfyBackend()
    angeboten = {"UNETLoader.unet_name": ["flux-2-klein-4b-fp8.safetensors"]}

    assert (
        backend._pick("image", "UNETLoader", "unet_name", angeboten)
        == "flux-2-klein-4b-fp8.safetensors"
    )


def test_the_choices_come_from_the_same_walk_as_the_missing_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wer eine Rolle in den Ablauf schreibt, taucht in beiden Antworten auf.

    ``missing_models`` sagt, welche Rolle **keine** Datei hat;
    ``model_choices`` sagt, **welche** sie hat. Zwei Durchgänge über denselben
    Graphen wären zwei Gelegenheiten auseinanderzulaufen.
    """
    from app.core.backends import mesh as mesh_module

    backend = mesh_module.ComfyBackend()
    alles = [name for names in OFFERED.values() for name in names]
    monkeypatch.setattr(mesh_module.ComfyBackend, "_offered", lambda self, kind, field: alles)

    choices = backend.model_choices("text_to_mesh")

    assert set(choices) == {
        "image",
        "text_encoder",
        "image_vae",
        "shape",
        "shape_vae",
        "image_encoder",
        "background",
    }
    assert choices["image"] == ("flux-2-klein-4b-fp8.safetensors",), (
        "nur, was die Rolle ausfüllt — keine 9B-Fassung, kein Formkern"
    )
    assert all(files for files in choices.values())
    assert backend.missing_models("text_to_mesh") == ()


def test_every_role_that_can_be_chosen_has_a_name() -> None:
    """Ein Auswahlfeld ohne Namen fragt nach einem Schlüssel (Regel 20).

    Zur Wahl stehen die drei Aufgaben, die ein Kunde versteht: Bild aus Text,
    Körper aus Bild, Freistellen. Textkodierer, VAEs und Bildkodierer gehören
    fest zu ihrem Modell und tragen bewusst keinen Namen — ein Feld dafür wäre
    eine Frage, die niemand beantworten kann.
    """
    from app.core.backends import mesh as mesh_module

    benutzt: set[str] = set()
    for name in ("image_to_mesh", "text_to_mesh"):
        graph = json.loads((mesh_module.WORKFLOW_DIR / f"{name}.json").read_text(encoding="utf-8"))
        for node in graph.values():
            for value in (node.get("inputs") or {}).values():
                if isinstance(value, str):
                    found = mesh_module._MODEL_PLACEHOLDER.match(value)
                    if found is not None:
                        benutzt.add(found.group(1))

    named = {role for role in benutzt if str(mesh_module.MODEL_ROLES[role].title)}
    assert named == {"image", "shape", "background"}


def test_the_reachability_probe_takes_the_port_from_the_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gesamtreview 05.09.2026, CORE-25: ``reachable`` prüfte ohne Portangabe
    immer Port 80 — ein HTTPS-ComfyUI hinter einem Proxy antwortet auf 443,
    und die Bereitschaft meldete ABSENT, der Erzeugen-Knopf blieb gesperrt."""
    import socket

    from app.core.backends import mesh

    asked: list[tuple[str, int]] = []

    class _Connection:
        def __enter__(self) -> _Connection:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def fake_connection(address: tuple[str, int], timeout: float = 0.0) -> _Connection:
        asked.append(address)
        return _Connection()

    monkeypatch.setattr(socket, "create_connection", fake_connection)

    assert mesh.reachable("https://rechner/comfy") is True
    assert mesh.reachable("http://rechner/comfy") is True
    assert mesh.reachable("https://rechner:8188/comfy") is True
    assert asked == [("rechner", 443), ("rechner", 80), ("rechner", 8188)]


def test_the_image_model_is_fetched_with_a_fixed_revision_and_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Das Bildmodell für den Textweg holt Solidon seit dem 21.09.2026 selbst.

    Robert tippte einen Satz, und der Dialog verlangte ein Bild — das Modell
    sollte der Kunde selbst besorgen. Jetzt geht es denselben Weg wie das
    Freistellmodell: je Datei fester Stand, gestreamte Prüfsumme, Tausch am
    Ziel erst nach der Prüfung — FLUX.2 [klein] 4B nach ``diffusion_models``,
    Qwen3-4B nach ``text_encoders``, die VAE nach ``vae``.
    """
    from app.core.backends import comfy_setup

    monkeypatch.setattr(comfy_setup, "scratch_dir", lambda name: tmp_path / name)
    monkeypatch.setattr(comfy_setup, "_space_or_stop", lambda *_args, **_kwargs: None)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        comfy_setup,
        "_run_repeatedly",
        lambda command, *_args, **_kwargs: commands.append(command),
    )
    comfyui = tmp_path / "ComfyUI"

    comfy_setup.fetch_image_model(comfyui, Path("python"))

    assert [command[3] for command in commands] == [comfy_setup._FETCH_FILE] * 3
    assert [command[4:7] for command in commands] == [
        [
            str(comfyui / "models" / "diffusion_models"),
            "black-forest-labs/FLUX.2-klein-4b-fp8",
            "flux-2-klein-4b-fp8.safetensors",
        ],
        [
            str(comfyui / "models" / "text_encoders"),
            "Comfy-Org/vae-text-encorder-for-flux-klein-4b",
            "split_files/text_encoders/qwen_3_4b_fp4_flux2.safetensors",
        ],
        [
            str(comfyui / "models" / "vae"),
            "Comfy-Org/vae-text-encorder-for-flux-klein-4b",
            "split_files/vae/flux2-vae.safetensors",
        ],
    ]
    assert [command[-2:] for command in commands] == [
        [
            "5b4408e59397a4a37ccb46afe426d8ed86379441",
            "97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6",
        ],
        [
            "5f526678002e43af5551dadb73ce2e8c91b43afe",
            "3eab03a77adb0ee5304a4e677d5c10ac22f9049c1d7c894adca4f8bb39206ca8",
        ],
        [
            "5f526678002e43af5551dadb73ce2e8c91b43afe",
            "868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3",
        ],
    ]

    # Und nur, was fehlt — eine bf16-Fassung zählt wie die fp8-Fassung, ein
    # Rest unter dem richtigen Namen nicht.
    models = comfyui / "models"
    for folder, name in (
        ("diffusion_models", "flux-2-klein-4b.safetensors"),
        ("text_encoders", "qwen_3_4b.safetensors"),
        ("vae", "flux2-vae.safetensors"),
    ):
        (models / folder).mkdir(parents=True, exist_ok=True)
        (models / folder / name).write_bytes(b"x")
    assert not comfy_setup.image_model_present(comfyui), "der Rest unter dem Namen zählt nicht"
    (models / "vae" / "flux2-vae.safetensors").unlink()
    (models / "vae" / "flux2_vae_bf16.safetensors").write_bytes(b"x")
    assert comfy_setup.image_model_present(comfyui)
    commands.clear()
    comfy_setup.fetch_image_model(comfyui, Path("python"))
    assert commands == [], "ein vorhandenes Bildmodell wird nicht noch einmal geladen"


def test_a_file_of_ours_counts_only_in_full_size(tmp_path: Path) -> None:
    """Ein abgebrochener Austausch darf nie wie ein fertiges Modell aussehen."""
    import dataclasses

    from app.core.backends import comfy_setup

    entry = dataclasses.replace(comfy_setup.SHAPE_FILES[0], size=8)
    target = entry.target(tmp_path)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"halb")
    assert not comfy_setup.file_present(tmp_path, entry)
    target.write_bytes(b"komplett")
    assert comfy_setup.file_present(tmp_path, entry)


def test_the_image_model_checks_both_disks_before_it_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dieselbe Platzprüfung wie bei den Gewichten — Zwischenordner und Ziel."""
    from app.core.backends import comfy_setup

    monkeypatch.setattr(comfy_setup, "scratch_dir", lambda name: tmp_path / name)
    monkeypatch.setattr(comfy_setup, "_run_repeatedly", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(comfy_setup, "free_gigabytes", lambda _where: 1.0)

    with pytest.raises(comfy_setup.SetupFailed, match="models/diffusion_models"):
        comfy_setup.fetch_image_model(tmp_path / "ComfyUI", Path("python"))


def test_the_setup_fetches_the_image_model_only_when_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acht Gigabyte für einen Weg, den ein Foto umgeht — nur auf Wunsch.

    Und erst nach den Gewichten: Wer abbricht, hat den Bildweg vollständig.
    """
    from app.core.backends import comfy_setup

    comfyui = _comfyui_folder(tmp_path)
    monkeypatch.setattr(comfy_setup, "find_python", lambda _folder: Path("python"))
    steps: list[str] = []
    monkeypatch.setattr(
        comfy_setup, "fetch_background", lambda *_a, **_k: steps.append("background")
    )
    monkeypatch.setattr(comfy_setup, "fetch_weights", lambda *_a, **_k: steps.append("weights"))
    monkeypatch.setattr(
        comfy_setup, "fetch_image_model", lambda *_a, **_k: steps.append("image_model")
    )
    monkeypatch.setattr(comfy_setup, "weights_present", lambda _c: True)
    there = {"image": False}
    monkeypatch.setattr(comfy_setup, "image_model_present", lambda _c: there["image"])

    result = comfy_setup.setup(comfyui, weights=True)
    assert "image_model" not in steps, "ohne Wunsch bleibt das Bildmodell liegen"
    assert result.done and not result.image_model

    steps.clear()
    there["image"] = True
    result = comfy_setup.setup(comfyui, weights=True, image_model=True)
    assert steps == ["background", "weights", "image_model"], "zuletzt, nach den Gewichten"
    assert result.done and result.image_model

    steps.clear()
    result = comfy_setup.setup(comfyui, weights=False, image_model=True)
    assert steps == ["image_model"], (
        "liegen die Gewichte schon, holt der Wunsch das Bildmodell trotzdem (RM-343)"
    )
    assert result.done and result.image_model

    steps.clear()
    result = comfy_setup.setup(comfyui, weights=False, image_model=False)
    assert steps == [], "ohne Wunsch wird nichts geladen"
    assert result.done


@pytest.mark.parametrize("path", ["/prompt", "/history/", "/upload/image"])
def test_a_service_that_answers_with_a_json_list_is_a_sentence_not_a_crash(path: str) -> None:
    """Unter der Adresse steht ein anderer Dienst — gültiges JSON, nur kein Objekt.

    ``.get`` auf einer Liste war ein ``AttributeError`` und damit „Im Programm
    ist ein unerwarteter Fehler aufgetreten" für eine falsch eingetragene
    Adresse (Regel 17).
    """
    server = Comfy()

    def answer(url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        if path in url:
            server.requests.append(url)
            return b'["kein", "Objekt"]'
        return server(url, body, headers)

    comfy = ComfyBackend(url="http://127.0.0.1:8188", transport=answer, poll_seconds=0.0)
    with pytest.raises(GenerationFailed) as raised:
        if path == "/upload/image":
            comfy.image_to_mesh(b"PNG", seed=1)
        else:
            comfy.text_to_mesh("ein Halter")

    assert raised.value.suggestions


def test_an_output_entry_of_the_wrong_shape_is_skipped_not_fatal() -> None:
    """Eine Ausgabe, die kein Objekt ist, gehört nicht uns — weitersuchen."""
    server = Comfy()

    def answer(url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        if "/history/" in url:
            return json.dumps(
                {
                    "job-1": {
                        "outputs": {
                            "1": ["kein", "Knoten"],
                            "2": {"meshes": "kein Eintrag"},
                            "4": {"meshes": [{"filename": "out.stl"}]},
                        }
                    }
                }
            ).encode("utf-8")
        return server(url, body, headers)

    comfy = ComfyBackend(url="http://127.0.0.1:8188", transport=answer, poll_seconds=0.0)

    assert comfy.text_to_mesh("ein Halter").mesh.triangle_count > 0
