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
#: unter den Checkpoints liegt neben den Bildmodellen auch ein Formkern aus
#: einer früheren Installation, und neben dem gemeinten TripoSG steht die
#: Kritzel-Fassung, die für ein Lichtbild das falsche Modell wäre. Beide
#: stehen mit Absicht vor der richtigen Antwort.
OFFERED: dict[str, list[str]] = {
    "CheckpointLoaderSimple.ckpt_name": [
        "hunyuan_3d_v2.1.safetensors",
        "Juggernaut-X-v10.safetensors",
        "animagine-xl-4.0-opt.safetensors",
    ],
    "TripoSGLoader.model": ["TripoSG-scribble", "TripoSG"],
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
    sich gegen den laufenden Server.
    """
    server = Comfy()

    backend(server).text_to_mesh("ein Halter")

    graph = server.graphs[0]
    chosen = {
        node["class_type"]: node["inputs"]
        for node in graph.values()
        if node["class_type"] in ("CheckpointLoaderSimple", "TripoSGLoader")
    }
    assert chosen["TripoSGLoader"]["model"] == "TripoSG", (
        "nicht die Kritzel-Fassung, die davor in der Liste steht"
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


def test_the_nodes_travel_with_the_application() -> None:
    """Sie lagen unter ``tools/`` — und dorthin kommt ein Kunde nicht.

    Die Anwendung wies auf „«python tools/setup_comfyui.py»" hin; im gebauten
    Paket gibt es weder das Skript noch die Knoten daneben, denn ``tools/``
    reist nicht mit. Jetzt liegen sie bei den Workflows, die sie ansprechen —
    und der Eintrag der Spec für ``app/core/backends/data`` deckt beide.
    """
    from app.core.backends import comfy_setup

    assert comfy_setup.NODE_SOURCE.is_dir(), "die Knoten fehlen in dieser Installation"
    for name in ("nodes.py", "__init__.py"):
        assert (comfy_setup.NODE_SOURCE / name).is_file(), name
    # Neben den Workflows, nicht irgendwo: Was der Ablauf anspricht und was ihn
    # ausführt, gehört in denselben Datenordner.
    from app.core.backends import mesh as mesh_module

    assert comfy_setup.NODE_SOURCE.is_relative_to(mesh_module.WORKFLOW_DIR)


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


def test_setting_up_copies_the_nodes_and_says_each_step(tmp_path: Path) -> None:
    """Vier Schritte, und jeder meldet sich — „das dauert" ist keine Auskunft."""
    from app.core.backends import comfy_setup

    comfyui = tmp_path / "ComfyUI"
    (comfyui / "custom_nodes").mkdir(parents=True)
    seen: list[str] = []

    target = comfy_setup.copy_nodes(comfyui, progress=lambda step: seen.append(str(step)))

    assert (target / "nodes.py").is_file()
    assert target.name == comfy_setup.NODE_NAME
    assert seen, "der Schritt meldet sich"


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
    """Ein halb kopierter Knotenordner wäre schlimmer als ein langer Lauf.

    Abgebrochen wird zwischen den Schritten, und der Satz dazu sagt, dass ein
    neuer Lauf fortsetzt — sonst fängt jemand von vorn an.
    """
    from app.core.backends import comfy_setup

    comfyui = tmp_path / "ComfyUI"
    (comfyui / "custom_nodes").mkdir(parents=True)
    monkeypatch.setattr(comfy_setup, "find_python", lambda _folder: Path("python"))

    result = comfy_setup.setup(comfyui, cancelled=lambda: True)

    assert not result.done
    assert "setzt fort" in str(result.reason)
    assert (result.nodes / "nodes.py").is_file(), "der getane Schritt bleibt getan"


# --- läuft es, und kennt es die Knoten? (§27) -------------------------------------


def _object_info(known: bool, node: str = "TripoSGImageToMesh") -> bytes:
    """Was ComfyUI auf ``/object_info/<knoten>`` antwortet.

    Ein ComfyUI ohne diesen Knoten antwortet mit einem **leeren Objekt** und
    nicht mit einem Fehler — genau daran hängt die Unterscheidung.
    """
    return json.dumps({node: {"input": {}}} if known else {}).encode("utf-8")


def test_a_comfy_that_knows_our_node_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.backends import mesh as mesh_module

    node = mesh_module.ComfyBackend()._own_node()
    assert node, "der mitgelieferte Ablauf nennt einen eigenen Knoten"

    backend = ComfyBackend(transport=lambda url, data, headers: _object_info(True, node))
    monkeypatch.setattr(mesh_module, "reachable", lambda url, seconds=0.25: True)

    assert backend.readiness() is mesh_module.Readiness.READY


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
    from app.core.backends import mesh as mesh_module

    node = ComfyBackend()._own_node()

    assert node is not None
    assert node.startswith(mesh_module.OWN_NODE_PREFIX)
    graph = json.loads((WORKFLOW_DIR / "image_to_mesh.json").read_text(encoding="utf-8"))
    assert any(entry.get("class_type") == node for entry in graph.values())


def test_a_step_can_be_cancelled_while_it_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Abbrechen wirkte beim längsten Schritt nicht.**

    ``subprocess.run`` blockiert bis zum Ende, und die Abbruchprüfung lag
    *zwischen* den Schritten — einer davon lädt 7,5 GB. Wer abbrach, wartete
    eine halbe Stunde auf einen Download, den er nicht mehr wollte.
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

    with pytest.raises(comfy_setup.Cancelled):
        comfy_setup._run(
            ["git", "clone"],
            "TripoSG holen",
            lambda step: gesehen.append(str(step)),
            cancelled=lambda: True,
        )

    assert getoetet == [True], "der Kindprozess wird beendet, nicht abgewartet"


def test_a_cancelled_setup_says_that_a_new_run_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Und der Satz dazu ist keine Höflichkeit: Es stimmt.

    ``huggingface_hub`` lässt teilweise geladene Dateien liegen und setzt beim
    nächsten Lauf fort; die Knoten sind idempotent kopiert.
    """
    from app.core.backends import comfy_setup

    comfyui = tmp_path / "ComfyUI"
    (comfyui / "custom_nodes").mkdir(parents=True)
    monkeypatch.setattr(comfy_setup, "find_python", lambda _folder: Path("python"))

    def bricht_ab(*_args: object, **_kwargs: object) -> None:
        raise comfy_setup.Cancelled("Gewichte laden")

    monkeypatch.setattr(comfy_setup, "fetch_triposg", bricht_ab)

    result = comfy_setup.setup(comfyui, cancelled=lambda: False)

    assert not result.done
    assert "setzt fort" in str(result.reason)
    assert (result.nodes / "nodes.py").is_file(), "der getane Schritt bleibt getan"
