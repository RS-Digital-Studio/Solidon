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

import pytest
from packaging.requirements import Requirement

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
#: Kritzel-Version, die für ein Lichtbild das falsche Modell wäre. Beide
#: stehen mit Absicht vor der richtigen Antwort.
OFFERED: dict[str, list[str]] = {
    "CheckpointLoaderSimple.ckpt_name": [
        "hunyuan_3d_v2.1.safetensors",
        "Juggernaut-X-v10.safetensors",
        "animagine-xl-4.0-opt.safetensors",
    ],
    "TripoSGLoader.model": ["TripoSG-scribble", "TripoSG"],
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
        "nicht die Kritzel-Version, die davor in der Liste steht"
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


def test_triposg_source_uses_and_verifies_the_fixed_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Installationsstand darf nicht davon abhängen, wann jemand einrichtet.

    Ein flacher Klon von ``HEAD`` war zwar klein, holte aber bei jedem Lauf
    potenziell anderen Quelltext. Der feste Commit muss deshalb schon im Fetch
    stehen, ausgecheckt werden und als tatsächlicher ``HEAD`` geprüft werden.
    LICENSE und NOTICE reisen weiterhin neben den Knoten mit.
    """
    from app.core.backends import comfy_setup

    target = tmp_path / "ComfyUI" / "custom_nodes" / comfy_setup.NODE_NAME
    target.mkdir(parents=True)
    scratch = target / "_clone"
    commands: list[list[str]] = []

    monkeypatch.setattr(comfy_setup.discover, "find_program", lambda *_args: Path("git"))

    def run(
        command: list[str],
        _what: object,
        _progress: object,
        _cancelled: object = None,
    ) -> None:
        commands.append(command)
        if command[1] == "init":
            scratch.mkdir()
        if "checkout" in command:
            (scratch / "triposg").mkdir()
            (scratch / "LICENSE").write_text("MIT", encoding="utf-8")
            (scratch / "NOTICE").write_text("Hinweise", encoding="utf-8")

    monkeypatch.setattr(comfy_setup, "_run", run)

    comfy_setup.fetch_triposg(target)

    commit = comfy_setup.TRIPOSG_COMMIT
    assert [
        "git",
        "-C",
        str(scratch),
        "fetch",
        "--depth",
        "1",
        comfy_setup.TRIPOSG_REPO,
        commit,
    ] in commands
    assert ["git", "-C", str(scratch), "checkout", "--detach", commit] in commands
    assert [
        command[6:]
        for command in commands
        if command[3:6] == ["merge-base", "--is-ancestor", commit]
    ] == [["HEAD"]]
    assert [
        command[6:]
        for command in commands
        if command[3:6] == ["merge-base", "--is-ancestor", "HEAD"]
    ] == [[commit]]
    assert (target / "triposg").is_dir()
    assert (target / "LICENSE-TripoSG").read_text(encoding="utf-8") == "MIT"
    assert (target / "NOTICE-TripoSG").read_text(encoding="utf-8") == "Hinweise"


# --- läuft es, und kennt es die Knoten? (§27) -------------------------------------


def _object_info(known: bool, node: str = "TripoSGImageToMesh") -> bytes:
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


def test_our_own_nodes_alone_are_not_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    """**„Bereit" stand da, und der Auftrag scheiterte trotzdem.**

    Geprüft wurde nur der Knoten aus unserer eigenen Sammlung. Der lag nach der
    Einrichtung vor, also stand „Bereit" da — und abgeschickt scheiterte der
    Auftrag an einem *anderen* Knoten, den derselbe Ablauf anspricht. Gemessen
    an einem frischen ComfyUI Desktop: unsere vier Knoten geladen, `RMBG`
    fehlte, und die Anwendung behauptete Bereitschaft.

    Und der fehlende Name gehört in die Auskunft: „ein Knoten fehlt" schickt
    niemanden weiter (Regel 17).
    """
    from app.core.backends import mesh as mesh_module

    nodes = mesh_module.ComfyBackend()._graph_nodes()
    eigene = {kind for kind in nodes if kind.startswith(mesh_module.OWN_NODE_PREFIX)}
    fremde = set(nodes) - eigene
    assert eigene and fremde, "der Ablauf spricht eigene und fremde Knoten an"

    # ``with_models=False``: Dieser Test prüft die Knotenfrage. Ein Server, der
    # die Modelle mitbeantwortet, würde damit auch die Knoten bejahen, für die
    # er eine Auswahlliste führt.
    backend = ComfyBackend(transport=_answers_for(eigene, with_models=False))
    monkeypatch.setattr(mesh_module, "reachable", lambda url, seconds=0.25: True)

    assert backend.readiness() is mesh_module.Readiness.NO_NODES
    assert set(backend.missing_nodes()) == fremde


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

    nodes = ComfyBackend()._graph_nodes()

    assert nodes, "der Ablauf nennt seine Knoten selbst"
    assert any(kind.startswith(mesh_module.OWN_NODE_PREFIX) for kind in nodes)
    graph = json.loads((WORKFLOW_DIR / "image_to_mesh.json").read_text(encoding="utf-8"))
    assert set(nodes) == {str(entry.get("class_type")) for entry in graph.values()}


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
    abfragen = iter((False, True))

    with pytest.raises(comfy_setup.Cancelled):
        comfy_setup._run(
            ["git", "clone"],
            "TripoSG holen",
            lambda step: gesehen.append(str(step)),
            cancelled=lambda: next(abfragen, True),
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


def test_the_package_list_carries_what_a_fresh_comfyui_lacks() -> None:
    """**Sie nannte drei Pakete, und es fehlten sechs.**

    Gemessen war sie an einer Installation, in der andere Knoten das übrige
    längst mitgebracht hatten. Auf einem frischen ComfyUI Desktop fehlten
    ``trimesh``, ``diffusers``, ``scikit-image``, ``lazy_loader``, ``omegaconf``
    und die Laufzeit von ``antlr4`` — und die Einrichtung meldete „fertig".

    Die Version an ``antlr4`` ist keine Übervorsicht: ``omegaconf`` liest damit
    einen vorkompilierten Automaten, und die 4.13 serialisiert ihn anders.
    """
    from app.core.backends import comfy_setup

    assert comfy_setup.PACKAGES == (
        "jaxtyping==0.3.7; python_version < '3.11'",
        "jaxtyping==0.3.11; python_version >= '3.11'",
        "typeguard==4.6.0",
        "fast-simplification==0.2.0",
        "trimesh==5.0.0",
        "diffusers==0.40.0",
        "scikit-image==0.25.2; python_version < '3.11'",
        "scikit-image==0.26.0; python_version >= '3.11'",
        "lazy_loader==0.5",
        "omegaconf==2.3.1",
        "antlr4-python3-runtime==4.9.3",
    )


@pytest.mark.parametrize(
    ("python_version", "jaxtyping", "scikit_image"),
    [
        ("3.10", "==0.3.7", "==0.25.2"),
        ("3.11", "==0.3.11", "==0.26.0"),
        ("3.14", "==0.3.11", "==0.26.0"),
    ],
)
def test_fixed_packages_cover_every_supported_comfy_python(
    python_version: str,
    jaxtyping: str,
    scikit_image: str,
) -> None:
    """ComfyUI unterstützt 3.10; neuere Wheels dürfen diesen Weg nicht sperren."""
    from app.core.backends import comfy_setup

    selected: dict[str, list[str]] = {}
    for raw in comfy_setup.BINARY_PACKAGES:
        requirement = Requirement(raw)
        if requirement.marker is None or requirement.marker.evaluate(
            {"python_version": python_version}
        ):
            selected.setdefault(requirement.name, []).append(str(requirement.specifier))

    assert selected["jaxtyping"] == [jaxtyping]
    assert selected["scikit-image"] == [scikit_image]


def test_package_installation_allows_only_fixed_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wheels sind Pflicht; das einzige Quellpaket trägt eine Prüfsumme."""
    from app.core.backends import comfy_setup

    commands: list[list[str]] = []

    def remember(command, _what, _progress, _cancelled=None) -> None:
        commands.append(command)

    monkeypatch.setattr(comfy_setup, "_run", remember)

    comfy_setup.install_packages(Path("python"))

    assert len(commands) == 2
    assert "--no-deps" in commands[0]
    assert "--only-binary=:all:" in commands[0]
    assert commands[0][-len(comfy_setup.BINARY_PACKAGES) :] == list(comfy_setup.BINARY_PACKAGES)
    assert "--no-deps" in commands[1]
    assert "--only-binary=:all:" not in commands[1]
    assert "--require-hashes" in commands[1]
    assert "--no-build-isolation" in commands[1]
    assert commands[1][-1] == (
        "antlr4-python3-runtime @ "
        "https://files.pythonhosted.org/packages/3e/38/"
        "7859ff46355f76f8d19459005ca000b6e7012f2f1ca597746cbcd1fbfe5e/"
        "antlr4-python3-runtime-4.9.3.tar.gz"
        "#sha256=f224469b4168294902bb1efa80a8bf7855f24c99aef99cbefc1bcd3cce77881b"
    )


def test_setting_up_looks_whether_the_nodes_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**„Fertig" war eine Behauptung, und sie war auf frischen Rechnern falsch.**

    Die Einrichtung kopierte, klonte, flickte und installierte — ob am Ende
    etwas lief, erfuhr der Kunde erst beim Erzeugen. Der Schritt kostet zwei
    Sekunden und steht **vor** den Gewichten: Ein fehlendes Paket nach zwei
    Sekunden zu melden ist mehr wert als nach einer halben Stunde Download.
    """
    from app.core.backends import comfy_setup

    comfyui = tmp_path / "ComfyUI"
    (comfyui / "custom_nodes").mkdir(parents=True)
    reihenfolge: list[str] = []
    monkeypatch.setattr(comfy_setup, "find_python", lambda _folder: Path("python"))
    monkeypatch.setattr(comfy_setup, "fetch_triposg", lambda *a, **k: None)
    monkeypatch.setattr(comfy_setup, "patch_sources", lambda *a, **k: None)
    monkeypatch.setattr(
        comfy_setup, "install_packages", lambda *a, **k: reihenfolge.append("pakete")
    )
    monkeypatch.setattr(comfy_setup, "nodes_load", lambda *a, **k: reihenfolge.append("nachsehen"))
    monkeypatch.setattr(
        comfy_setup, "fetch_background", lambda *a, **k: reihenfolge.append("freistellen")
    )
    monkeypatch.setattr(
        comfy_setup, "fetch_weights", lambda *a, **k: reihenfolge.append("gewichte")
    )

    comfy_setup.setup(comfyui)

    # Das Kleine vor dem Großen: 445 MB vor 7,5 GB. Wer abbricht, hat dann
    # wenigstens den Teil, der schnell ging.
    assert reihenfolge == ["pakete", "nachsehen", "freistellen", "gewichte"]


def test_nodes_that_do_not_load_say_what_helps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 17: Der Satz nennt die Ursache und den nächsten Schritt.

    Was der Ladefehler selbst sagt („No module named 'trimesh'"), sagt genauer,
    was fehlt, als jeder Satz, den wir vorher erraten könnten — also reist er
    mit.
    """
    from app.core.backends import comfy_setup

    def scheitert(*_args: object, **_kwargs: object) -> None:
        raise comfy_setup.SetupFailed("No module named 'trimesh'")

    monkeypatch.setattr(comfy_setup, "_run", scheitert)

    with pytest.raises(comfy_setup.SetupFailed) as raised:
        comfy_setup.nodes_load(tmp_path, Path("python"), tmp_path / "nodes")

    gesagt = str(raised.value)
    assert "No module named 'trimesh'" in gesagt, "die Ursache reist mit"
    assert "zweiter Lauf" in gesagt, "und der nächste Schritt steht dabei"


def test_the_weights_are_downloaded_through_a_short_folder() -> None:
    """**MAX_PATH ist 260, und der Pfad war 261 Zeichen lang.**

    ``huggingface_hub`` legt seine halbfertigen Dateien unter dem Ziel ab, und
    ihre Namen sind rund 163 Zeichen lang. Zusammen mit dem Installationspfad
    von ComfyUI Desktop (98) waren das gemessene 261 — ein Zeichen über der
    Grenze, und der Kunde bekam mitten im 7,5-GB-Download einen
    ``FileNotFoundError`` mit einem Pfad, den kein Mensch liest.

    Geprüft wird der Programmtext und nicht ein Lauf: Der Lauf lädt 7,5 GB.

    **Eine dritte Zusicherung stand hier und ist am 22.08.2026 gefallen.** Sie
    rechnete ``len(tempfile.gettempdir()) + len("/solidon-triposg") + 163 <
    260`` — also die Pfadlänge **dieser** Maschine. Das ist keine Aussage über
    den Code und keine über den Kunden: Wer ``TEMP`` umbiegt, macht sie rot,
    ohne dass sich an der Anwendung etwas geändert hätte, und genau das ist an
    jenem Tag zweimal passiert, als eine Sitzung ihre Protokolle in einen
    eigenen Ordner schrieb. Ein Test, der die Umgebung seines Läufers misst
    statt sein Thema, kostet jede Sitzung Zeit und schützt niemanden.

    **Was sie prüfen wollte, ist trotzdem richtig und gehört woanders hin:**
    Windows bricht bei 260 Zeichen ab, und ein Kunde mit einem tiefen
    ``TEMP``-Pfad bekäme mitten im 7,5-GB-Ladevorgang einen
    ``FileNotFoundError``. Das ist eine Aussage über den **Kunden** und muss
    deshalb im Programm stehen, nicht im Test: ``comfy_setup`` gehört dazu
    gebracht, die Länge vor dem Laden zu prüfen und mit einem
    Handlungsvorschlag anzuhalten (§2.7, §33.1) — „Ihr Zwischenordner ist zu
    tief; setzen Sie TEMP auf einen kürzeren Pfad." Ein Test darauf prüft dann
    das Verhalten und nicht den Rechner, auf dem er läuft.

    **Und seit dem 25.08.2026 kommt der Ordner nicht mehr aus ``tempfile``.**
    Ein fester Name im gemeinsamen Temp ist unter Linux von jedem anderen Konto
    vorbelegbar; er liegt jetzt im Nutzer-Cache und wird als Argument
    hereingereicht — das Programm läuft in ComfyUIs Python und kennt unseren
    Kern nicht.
    """
    from app.core.backends import comfy_setup
    from app.core.paths import user_cache_dir

    programm = comfy_setup._FETCH_WEIGHTS
    assert "tempfile" not in programm, "der Zwischenordner kommt nicht mehr aus dem Temp"
    assert "sys.argv[3]" in programm, "sondern von außen, aus app.core.paths"
    assert "shutil.move" in programm, "und danach an seinen Platz gebracht"

    ordner = comfy_setup.scratch_dir("dl-triposg")
    assert user_cache_dir() in ordner.parents, "er liegt im Nutzer-Cache"
    assert ordner.is_dir(), "und er ist angelegt, bevor jemand hineinlädt"


def test_triposg_weights_use_and_verify_the_fixed_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch die 7,5 GB müssen bei jedem Einrichten denselben Stand ergeben."""
    from app.core.backends import comfy_setup

    monkeypatch.setattr(comfy_setup, "scratch_dir", lambda name: tmp_path / name)
    monkeypatch.setattr(comfy_setup, "free_gigabytes", lambda _where: 500.0)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        comfy_setup,
        "_run_repeatedly",
        lambda command, *_args, **_kwargs: commands.append(command),
    )

    comfy_setup.fetch_weights(tmp_path / "ComfyUI", Path("python"))

    assert len(commands) == 1
    command = commands[0]
    assert command[-1] == comfy_setup.WEIGHTS_REVISION
    program = comfy_setup._FETCH_WEIGHTS

    calls: list[tuple[str, str, str]] = []

    def download(repo: str, *, revision: str, local_dir: str, max_workers: int) -> str:
        assert max_workers == 8
        calls.append(("laden", repo, revision))
        (Path(local_dir) / "model_index.json").write_text("{}", encoding="utf-8")
        return local_dir

    class Api:
        def model_info(self, repo: str, *, revision: str) -> SimpleNamespace:
            calls.append(("prüfen", repo, revision))
            return SimpleNamespace(sha=revision)

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(HfApi=Api, snapshot_download=download),
    )
    monkeypatch.setattr(sys, "argv", ["-c", *command[4:]])

    exec(program, {})

    expected = (comfy_setup.WEIGHTS_REPO, comfy_setup.WEIGHTS_REVISION)
    assert calls == [("laden", *expected), ("prüfen", *expected)]
    assert (tmp_path / "ComfyUI" / "models" / "triposg" / "TripoSG").is_dir()


def test_triposg_weights_reject_a_different_resolved_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Revisionsparameter allein genügt nicht; sein Ergebnis wird geprüft."""
    from app.core.backends import comfy_setup

    target = tmp_path / "target"
    scratch = tmp_path / "scratch"

    def download(_repo: str, **kwargs: object) -> str:
        local_dir = Path(str(kwargs["local_dir"]))
        (local_dir / "model_index.json").write_text("{}", encoding="utf-8")
        return str(local_dir)

    class Api:
        def model_info(self, _repo: str, *, revision: str) -> SimpleNamespace:
            assert revision == comfy_setup.WEIGHTS_REVISION
            return SimpleNamespace(sha="0" * 40)

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(HfApi=Api, snapshot_download=download),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "-c",
            str(target),
            comfy_setup.WEIGHTS_REPO,
            str(scratch),
            comfy_setup.WEIGHTS_REVISION,
        ],
    )

    with pytest.raises(RuntimeError, match="Modellstand"):
        exec(comfy_setup._FETCH_WEIGHTS, {})

    assert scratch.is_dir(), "der falsche Stand wird nicht an den Zielort verschoben"
    assert not target.exists()


def test_background_weights_use_a_fixed_revision_and_verify_the_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.backends import comfy_setup

    monkeypatch.setattr(comfy_setup, "scratch_dir", lambda name: tmp_path / name)
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
        ["-c", str(target), "repo", "weights.bin", str(scratch), "revision", expected],
    )

    exec(comfy_setup._FETCH_FILE, {})

    assert calls == [("repo", "weights.bin", "revision")]
    assert (target / "weights.bin").read_bytes() == payload


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
    Gemessen an drei Abbrüchen hintereinander auf einer wackeligen Leitung
    (``WinError 10054``, dann 2 GB weit, dann ``WinError 10038``); bei 7,5 GB
    ist das der Normalfall und nicht das Pech.

    Geprüft wird der Programmtext: Ein Lauf lädt 7,5 GB.

    Der feste Name steht seit dem 25.08.2026 nicht mehr im Programmtext,
    sondern in :func:`comfy_setup.scratch_dir` — dieselbe Zusage, eine Stelle
    weiter oben: Zweimal gefragt, zweimal derselbe Ordner.
    """
    from app.core.backends import comfy_setup

    programm = comfy_setup._FETCH_WEIGHTS
    assert comfy_setup.scratch_dir("dl-triposg") == comfy_setup.scratch_dir("dl-triposg"), (
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

    for programm in (comfy_setup._FETCH_WEIGHTS, comfy_setup._FETCH_FILE):
        assert "range(" not in programm, "die Wiederholung gehört nicht ins Kind"

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


def test_the_device_fixes_never_comment_out_the_rest_of_a_line() -> None:
    """**Der Flicken hat die Datei zerbrochen, und das war lehrreich.**

    Der erste Versuch hängte „# von Solidon" an die Zeile mit ``torch.zeros``,
    und die ging weiter: ``dtype`` und ``requires_grad`` standen dahinter und
    waren damit wegkommentiert, die Klammer blieb offen. ComfyUI meldete „'('
    was never closed", und die ganze Knotensammlung fiel aus.

    Gefangen hat es `nodes_load` — der Beleg dafür, dass dieser Schritt
    hingehört. Und hier steht die Regel, die daraus folgt: Ein Kommentar am
    Zeilenende ist nur dort erlaubt, wo die Zeile auch endet.
    """
    from app.core.backends import comfy_setup

    for wanted, fixed in comfy_setup._DEVICE_FIXES:
        if "#" not in fixed:
            continue
        vorher, _, _rest = fixed.partition("#")
        assert vorher.rstrip().endswith((")", ":", "None")), (
            f"„{fixed[:60]}…“ trägt einen Kommentar mitten in einer Zeile, die weitergeht"
        )
        assert not wanted.rstrip().endswith(","), (
            f"„{wanted[:60]}…“ endet mit einem Komma — die Zeile geht weiter, "
            "ein Kommentar dahinter verschluckt den Rest"
        )


def test_the_device_fixes_are_applied_and_stay_applied(tmp_path: Path) -> None:
    """Zweimal geflickt ist einmal geflickt, und die Prüfung sucht die Wirkung.

    Wer den Marker sucht, den er selbst geschrieben hat, flickt eine von Hand
    geänderte Datei ein zweites Mal und macht aus ihr Bruch.
    """
    from app.core.backends import comfy_setup

    quelle = tmp_path / "inference_utils.py"
    quelle.write_text(
        "import torch\n"
        "def f(edge_coords, grid_size):\n"
        "    expanded_tensor = torch.zeros(grid_size, grid_size, grid_size, "
        "device='cuda', dtype=torch.float16, requires_grad=False)\n"
        "    torch.cuda.empty_cache()\n"
        "    return expanded_tensor\n",
        encoding="utf-8",
    )

    assert comfy_setup._fix_devices(quelle) is True
    danach = quelle.read_text(encoding="utf-8")
    assert "device='cuda'" not in danach
    assert "is_available()" in danach
    # Und die Datei ist danach noch Python.
    import ast

    ast.parse(danach)

    assert comfy_setup._fix_devices(quelle) is False, "beim zweiten Mal bleibt sie, wie sie ist"


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

    Klassisch steht die Auswahlliste als erstes Element (``[["TripoSG"], {…}]``)
    — ein Typname wie ``"INT"`` steht an derselben Stelle und ist keine. Die
    neuen eingebauten Knoten schreiben statt der Liste ``"COMBO"`` und legen
    die Namen daneben.

    Gemessen an einem ComfyUI 0.33: ``TripoSGLoader`` klassisch,
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

    Er spricht andere Knoten an und braucht ein Modell mehr: TripoSG kennt
    keinen Texteingang, Text wird erst zu einem Bild, und dafür steht ein
    SDXL-Modell im Ablauf. Geprüft wurde immer ``image_to_mesh`` — wer kein
    Bildmodell hatte, las „Bereit" und erfuhr es beim Abschicken.
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
    """**Ein fehlendes Modell ist keine fehlende Knotensammlung.**

    Beides führte zu „Erzeugen" und dann zu einem Fehler, aber die Handlungen
    sind verschieden: Knoten legt Solidon selbst hinein, ein SDXL-Modell ist
    ComfyUIs eigene Sache. Vier Lagen statt drei, und jede zieht einen anderen
    Satz nach sich.
    """
    from app.core.backends import mesh as mesh_module

    nodes = set(ComfyBackend()._graph_nodes("text_to_mesh"))
    # Alle Knoten da, aber keine Auswahllisten — also kein Modell.
    backend = ComfyBackend(transport=_answers_for(nodes, with_models=False))
    monkeypatch.setattr(mesh_module, "reachable", lambda url, seconds=0.25: True)

    assert backend.readiness("text_to_mesh") is mesh_module.Readiness.NO_MODEL
    assert "image" in backend.missing_models("text_to_mesh")


def test_a_ready_comfy_says_nothing_about_missing_models() -> None:
    """Wo alles da ist, fehlt nichts — auch keine Rolle."""
    nodes = set(ComfyBackend()._graph_nodes("image_to_mesh"))
    backend = ComfyBackend(transport=_answers_for(nodes))

    assert backend.missing_models("image_to_mesh") == ()


# --- Platz vor dem Download -------------------------------------------------------


def test_the_weights_are_not_fetched_onto_a_full_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein 7,5-GB-Download stirbt an einer vollen Platte, und die Meldung lügt.

    Am 23.08.2026 lief er dreimal an und starb dreimal nach Minuten, weil ``C:``
    voll war. Was huggingface dabei meldet, nennt den Grund mit keinem Wort:

        RuntimeError: File reconstruction error: Internal Writer Error:
        Background writer channel closed

    Wer das liest, sucht am Netz. Gefunden wurde es nur, weil der Abbruch
    **dreimal an derselben Stelle** kam.

    Geprüft wird deshalb **vorher**: Ein Problem nach zwei Sekunden zu melden ist
    mehr wert als nach zwanzig Minuten — dieselbe Begründung, aus der
    ``nodes_load`` vor dem Download steht und nicht danach.
    """
    from app.core.backends import comfy_setup

    monkeypatch.setattr(comfy_setup, "free_gigabytes", lambda _where: 2.5)

    with pytest.raises(comfy_setup.SetupFailed) as fehler:
        comfy_setup.fetch_weights(tmp_path, Path("python"))

    gesagt = str(fehler.value)
    assert "2.5" in gesagt or "2,5" in gesagt, f"nennt den freien Platz nicht: {gesagt}"
    assert "9" in gesagt, f"nennt nicht, wie viel gebraucht wird: {gesagt}"


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

    assert gerufen == ["los"], "die Prüfung hat den Download aufgehalten, obwohl Platz war"


def test_a_half_finished_download_is_not_blocked_by_the_space_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was schon liegt, zählt mit — sonst verweigert die Prüfung die Wiederaufnahme.

    ``_run_repeatedly`` setzt einen abgebrochenen Download dort fort, wo er
    stand: Nur was fehlt, wird noch geholt. Eine Platzprüfung, die den bereits
    belegten Platz ignoriert, blockiert **ausgerechnet den zweiten Anlauf** —
    bei 5 von 7,5 GB geladen fehlen 2,5, verlangt würden 9.

    Der Fall ist im Review vom 23.08.2026 aufgefallen, nachdem die Prüfung
    schon eingebaut war.

    **Und die Bruchstücke liegen im Zwischenordner**, nicht am Ziel: Seit dem
    ``scratch_dir``-Umbau lädt ``huggingface_hub`` dorthin, und erst der
    gelungene Lauf verschiebt. Bis zum 26.08.2026 legte dieser Test sie unter
    ``models/triposg`` ab — geprüft wurde damit eine Wiederaufnahme an einem
    Ort, an dem keine stattfindet.
    """
    from app.core.backends import comfy_setup

    needed = comfy_setup.NEEDED_GIGABYTES
    scratch = comfy_setup.scratch_dir("dl-triposg")

    # 6 MB statt der echten 5 GB: Der Test soll die **Rechnung** pruefen, nicht
    # die Platte fuellen. Die freie Menge liegt darum knapp unter der Schwelle,
    # sodass erst der Zuschlag sie ueberschreitet.
    (scratch / "halb.safetensors").write_bytes(b"x" * 6_000_000)

    monkeypatch.setattr(
        comfy_setup,
        "free_gigabytes",
        lambda where: needed - 0.003 if where == scratch else 500.0,
    )
    gerufen: list[str] = []
    monkeypatch.setattr(comfy_setup, "_run_repeatedly", lambda *a, **k: gerufen.append("los"))

    comfy_setup.fetch_weights(tmp_path, Path("python"))

    assert gerufen == ["los"], "die Prüfung hat den zweiten Anlauf blockiert"


def test_the_space_is_measured_where_the_download_lands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gemessen wurde der falsche Datenträger — und zwar seit dem Umbau.

    Geprüft wurde am ComfyUI-Ordner, geladen wird seit dem ``scratch_dir``-Umbau
    in den Nutzer-Cache (unter Windows ``%LOCALAPPDATA%``). Roberts Aufbau ist
    genau der Fall, den das trifft: ComfyUI liegt auf ``D:`` mit viel Platz, ``C:``
    ist knapp — die Prüfung meldete grün, und der Download starb zwanzig Minuten
    später an der vollen Platte. Der Fehlertext, der dabei herauskam, nennt den
    Grund mit keinem Wort; genau dagegen war die Prüfung gebaut.

    Und die Absage nennt den Ort (Regel 17): „auf dem Datenträger ist zu wenig
    Platz" schickt niemanden weiter, der zwei Datenträger hat.
    """
    from app.core.backends import comfy_setup

    scratch = comfy_setup.scratch_dir("dl-triposg")
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

    scratch = comfy_setup.scratch_dir("dl-triposg")
    ziel = tmp_path / "models" / "triposg" / "TripoSG"
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


def test_the_sizes_in_the_progress_text_match_the_constants() -> None:
    """Was der Fortschritt nennt, muss die Konstante sagen — sonst driftet es.

    ``BACKGROUND_MEGABYTES`` (445) und ``WEIGHT_GIGABYTES`` (7,5) tragen die
    Größen der beiden Downloads, und ihre Kommentare sagen, sie stünden im
    Fortschrittstext. Sie standen dort auch — nur **von Hand getippt**, nicht aus
    der Konstante. Bis zum 24.08.2026 las die beiden Konstanten niemand.

    Der Beleg, dass das driftet, stand daneben: Der Kommentar über
    ``BACKGROUND_MEGABYTES`` sprach von „444 MB", die Konstante von 445 und der
    Text von 445. Ein Megabyte ist harmlos; die Bauform ist es nicht — wer die
    Modellgröße nachzieht, ändert eine der beiden Stellen.

    **Der Text bleibt, wie er ist, und die Konstante wird zur Zusicherung.**
    Die Zahl in die Message-ID hineinzuformatieren wäre der andere Weg —
    ``NEEDED_GIGABYTES`` macht es zwei Dutzend Zeilen weiter genau so
    (``.format(needed=…)``) und ist damit das Vorbild. Hier kostet er fünf
    Übersetzungen für zwei Sätze, und die kann diese Sitzung nicht liefern; ein
    Test kostet nichts und fängt dasselbe.
    """
    import re

    from app.core.backends import comfy_setup

    quelle = Path(comfy_setup.__file__).read_text(encoding="utf-8")

    # Die deutsche Quelle schreibt Dezimalkommas: „7,5 GB".
    erwartet_gb = f"{comfy_setup.WEIGHT_GIGABYTES:g}".replace(".", ",")
    erwartet_mb = f"{comfy_setup.BACKGROUND_MEGABYTES:g}"

    gb_texte = re.findall(r'_\("([^"]*\bGB\b[^"]*)"\)', quelle)
    mb_texte = re.findall(r'_\("([^"]*\bMB\b[^"]*)"\)', quelle)

    assert gb_texte, "kein Fortschrittstext mit GB gefunden — der Test prüfte nichts"
    assert mb_texte, "kein Fortschrittstext mit MB gefunden — der Test prüfte nichts"

    for text in gb_texte:
        zahlen = re.findall(r"\d+(?:,\d+)?(?=\s*GB)", text)
        assert erwartet_gb in zahlen, (
            f"{text!r} nennt {zahlen}, WEIGHT_GIGABYTES sagt {erwartet_gb}"
        )
    for text in mb_texte:
        zahlen = re.findall(r"\d+(?:,\d+)?(?=\s*MB)", text)
        assert erwartet_mb in zahlen, (
            f"{text!r} nennt {zahlen}, BACKGROUND_MEGABYTES sagt {erwartet_mb}"
        )


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
        (url.rsplit("/", 1)[-1], json.loads((body or b"{}").decode("utf-8")))
        for url, body in server.posts
    ]


def test_a_running_generation_can_be_cancelled() -> None:
    """**Bis zu einer Stunde war eine laufende Erzeugung nicht abbrechbar.**

    Der Dialog wartet beim Schließen fünfzig Millisekunden auf seinen Arbeiter
    und lässt dann los; der Arbeiter rechnete weiter und meldete sein Ergebnis
    an ein Fenster, das es nicht mehr gab. Gefragt wird jetzt in der
    Warteschleife — dort wird die Zeit verbracht.

    Unterbrochen wird, weil dieser Auftrag in ``queue_running`` steht: Der
    Test daneben zeigt den wartenden Fall, in dem ``/interrupt`` ausbleibt.
    """

    class Running(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
            # Nur die Frage nach der Schlange wird beantwortet; das Löschen ist
            # ein POST auf dieselbe Adresse und gehört in die Liste der Sendungen.
            if url.endswith("/queue") and body is None:
                return json.dumps(
                    {"queue_running": [[0, "job-1", {}]], "queue_pending": []}
                ).encode()
            return super().__call__(url, body, headers)

    posts = _cancel_and_collect(Running(ready_after=99))

    assert ("queue", {"delete": ["job-1"]}) in posts
    assert ("interrupt", {"prompt_id": "job-1"}) in posts
    assert ("free", {"unload_models": True, "free_memory": True}) in posts


def test_cancelling_a_waiting_job_leaves_a_foreign_job_alone() -> None:
    """**``/interrupt`` wählt nicht aus — es beendet, was gerade rechnet.**

    Das ``prompt_id`` im Rumpf sieht wie eine Auswahl aus und ist keine.
    Unbedingt geschickt, traf der Abbruch auf einem geteilten ComfyUI den
    fremden Auftrag, der gerade lief, während der eigene unversehrt in der
    Schlange stand. Wartet der eigene Auftrag nur, genügt darum ``delete``.
    """

    class Queued(Comfy):
        def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
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


def test_the_node_check_can_be_cancelled_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der einzige ``_run``-Aufruf ohne Abbruchmerker — und er lädt Torch."""
    from app.core.backends import comfy_setup

    gesehen: list[object] = []

    def merken(command, what, progress, cancelled=None) -> None:
        gesehen.append(cancelled)

    monkeypatch.setattr(comfy_setup, "_run", merken)
    merker = lambda: False  # noqa: E731 - eine Marke, keine Funktion mit Namen

    comfy_setup.nodes_load(Path("comfy"), Path("python"), Path("nodes"), cancelled=merker)

    assert gesehen == [merker]


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

    ``prefer`` trifft das Übliche: Wer ein Juggernaut liegen hat, will es vor
    dem Basismodell. Aber wer drei Feintunings nebeneinander hat, hat sie aus
    einem Grund, und keiner davon steht in einem Muster — das eine zeichnet
    Produktfotos, das andere Comicfiguren. Genau wie beim Sprachmodell gehört
    die Wahl dem Kunden.
    """
    from app.core.backends import mesh as mesh_module

    gemerkt: dict[str, str] = {}
    monkeypatch.setattr(
        mesh_module, "configured_model", lambda role: gemerkt.get(role, mesh_module.AUTOMATIC)
    )

    backend = mesh_module.ComfyBackend()
    angeboten = {
        "CheckpointLoaderSimple.ckpt_name": [
            "sd_xl_base_1.0.safetensors",
            "juggernautXL_v9.safetensors",
            "comicDiffusionXL.safetensors",
        ]
    }

    # Ohne Wahl gewinnt das Muster: ``juggernaut`` steht in ``prefer`` vorn.
    ohne = backend._pick("image", "CheckpointLoaderSimple", "ckpt_name", dict(angeboten))
    assert ohne == "juggernautXL_v9.safetensors"

    # Mit Wahl gewinnt der Kunde — auch gegen die eigene Rangfolge.
    gemerkt["image"] = "comicDiffusionXL.safetensors"
    mit = backend._pick("image", "CheckpointLoaderSimple", "ckpt_name", dict(angeboten))
    assert mit == "comicDiffusionXL.safetensors"


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
    angeboten = {"CheckpointLoaderSimple.ckpt_name": ["sd_xl_base_1.0.safetensors"]}

    assert (
        backend._pick("image", "CheckpointLoaderSimple", "ckpt_name", angeboten)
        == "sd_xl_base_1.0.safetensors"
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
    monkeypatch.setattr(
        mesh_module.ComfyBackend,
        "_offered",
        lambda self, kind, field: (
            ["eins.safetensors", "zwei.safetensors"]
            if kind == "CheckpointLoaderSimple"
            else ["nur_eins.safetensors"]
        ),
    )

    choices = backend.model_choices("text_to_mesh")

    assert "image" in choices, "der Textweg nennt die Bildrolle"
    assert choices["image"] == ("eins.safetensors", "zwei.safetensors")
    # Rollen mit nur einer Datei kommen mit — „nur eine" ist nicht „keine".
    assert all(files for files in choices.values())
    assert set(choices) >= {"image", "shape", "background"}


def test_every_role_that_can_be_chosen_has_a_name() -> None:
    """Ein Auswahlfeld ohne Namen fragt nach einem Schlüssel (Regel 20).

    ``shape_vae`` trägt bewusst keinen: Die Rolle gehört zu einem Ablauf, den
    Solidon nicht mitliefert, und ein Feld dafür wäre eine Frage nach etwas,
    das niemand hat.
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

    for role in benutzt:
        spec = mesh_module.MODEL_ROLES[role]
        assert str(spec.title), f"die Rolle {role} steht in einem Ablauf und braucht einen Namen"


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


def test_the_weights_are_staged_beside_the_target_and_swapped_in_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesamtreview 05.09.2026, CORE-24: Über die Grenze eines Datenträgers
    kopiert ``shutil.move`` Datei für Datei — direkt ins Ziel lag
    ``model_index.json`` da, bevor die Gewichte ankamen, und ein Abbruch
    dazwischen sah beim nächsten Einrichten wie ein vollständiges Modell
    aus. Kopiert wird daneben, eingewechselt in einem Schritt."""
    import shutil

    from app.core.backends import comfy_setup

    target = tmp_path / "models" / "TripoSG"
    scratch = tmp_path / "scratch"

    def download(_repo: str, **kwargs: object) -> str:
        local_dir = Path(str(kwargs["local_dir"]))
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / "model_index.json").write_text("{}", encoding="utf-8")
        return str(local_dir)

    class Api:
        def model_info(self, _repo: str, *, revision: str) -> SimpleNamespace:
            return SimpleNamespace(sha=revision)

    moves: list[Path] = []
    real_move = shutil.move

    def watched_move(source: str, destination: str) -> str:
        moves.append(Path(destination))
        return real_move(source, destination)

    monkeypatch.setattr(shutil, "move", watched_move)
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(HfApi=Api, snapshot_download=download),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["-c", str(target), comfy_setup.WEIGHTS_REPO, str(scratch), comfy_setup.WEIGHTS_REVISION],
    )

    exec(comfy_setup._FETCH_WEIGHTS, {})

    assert moves, "ohne Verschieben prüft dieser Test nichts"
    assert target not in moves, "nie Datei für Datei ins Ziel"
    assert all(path.parent == target.parent and path != target for path in moves)
    assert (target / "model_index.json").is_file()
    assert not list(target.parent.glob("*.part")), "die Zwischenstufe ist eingewechselt"
