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

    for name in ("trimesh", "diffusers", "scikit-image", "lazy_loader", "omegaconf"):
        assert name in comfy_setup.PACKAGES, name
    antlr = [p for p in comfy_setup.PACKAGES if p.startswith("antlr4")]
    assert antlr == ["antlr4-python3-runtime==4.9.3"], "die Version gehört dazu"


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
    """
    from app.core.backends import comfy_setup

    programm = comfy_setup._FETCH_WEIGHTS
    assert "tempfile.gettempdir" in programm, "geladen wird in einen kurzen Ordner"
    assert "shutil.move" in programm, "und danach an seinen Platz gebracht"


def test_a_broken_download_is_resumed_and_not_thrown_away() -> None:
    """**Der Docstring versprach Fortsetzen, und der Code löschte.**

    Der Ordner hieß ``mkdtemp``, also jedes Mal anders, und ein ``finally``
    räumte ihn auf — zusammen war „setzt beim nächsten Lauf fort" eine Lüge.
    Gemessen an drei Abbrüchen hintereinander auf einer wackeligen Leitung
    (``WinError 10054``, dann 2 GB weit, dann ``WinError 10038``); bei 7,5 GB
    ist das der Normalfall und nicht das Pech.

    Geprüft wird der Programmtext: Ein Lauf lädt 7,5 GB.
    """
    from app.core.backends import comfy_setup

    programm = comfy_setup._FETCH_WEIGHTS
    assert "solidon-triposg" in programm, "der Ordner trägt einen festen Namen"
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
