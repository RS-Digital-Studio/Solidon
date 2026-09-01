"""Die MCP-Schnittstelle (Bauplan §26, Konzept P15 §7 Etappe 9, D19).

Vier Auflagen stehen im Konzept, und drei davon lassen sich hier prüfen: kein
Zugriff von außerhalb, kein Pfadparameter, kein Quelltext. Die vierte — jeder
Fernaufruf eine Transaktion — prüft `tests/test_ui.py` am laufenden Fenster,
denn sie ist eine Aussage über das Dokument, nicht über das Protokoll.

Geprüft wird die Abweisung **vor** der Rechnung. Ein Aufruf, der erst rechnet
und danach merkt, dass er nicht durfte, hat schon getan, was er nicht sollte.
"""

from __future__ import annotations

import json

import pytest

from app.core.agent import remote
from app.core.errors import ValidationError
from app.core.scene import foreign


class _Bridge:
    """Nimmt Aufrufe entgegen und merkt sich, was ankam."""

    def __init__(self, answer: str = "fertig") -> None:
        self.answer = answer
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call(self, name: str, arguments: dict[str, object]) -> str:
        self.calls.append((name, arguments))
        return self.answer


def request(method: str, params: dict[str, object] | None = None, ident: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}}


# --- Protokoll ------------------------------------------------------------------


def test_initialize_names_the_application_and_its_protocol() -> None:
    """Ohne diese Antwort verbindet sich kein Gegenüber.

    Der Name steht nicht doppelt im Code — er kommt aus ``app.branding``, so
    wie Fenstertitel und Dateiendung auch.
    """
    answer = remote.handle(request("initialize"), _Bridge())
    result = answer["result"]
    assert result["protocolVersion"] == remote.PROTOCOL_VERSION
    assert result["serverInfo"]["name"]
    assert result["capabilities"]["tools"] == {}


def test_the_tool_list_comes_from_the_registry() -> None:
    """Keine zweite Liste (E9, Leitprinzip 3).

    Eine Operation, die heute deklariert wird, ist morgen über MCP erreichbar,
    ohne dass jemand diese Schicht anfasst. Eine von Hand gepflegte Liste wäre
    am Tag nach der nächsten Operation falsch, und niemand würde es merken.
    """
    answer = remote.handle(request("tools/list"), _Bridge())
    listed = {entry["name"] for entry in answer["result"]["tools"]}
    assert "sketch_extrude" in listed
    assert "read_report" in listed, "auch die Werkzeuge neben den Operationen"
    assert len(listed) > 40


def test_an_unknown_method_answers_with_an_error_not_a_crash() -> None:
    """JSON-RPC verlangt eine Antwort, auch auf Unsinn."""
    answer = remote.handle(request("does/not/exist"), _Bridge())
    assert answer["error"]["code"] == remote.METHOD_NOT_FOUND
    assert "result" not in answer


def test_broken_json_gets_an_answer_too() -> None:
    """Ein abgeschnittener Datenstrom ist der Normalfall, nicht die Ausnahme."""
    answer = remote.answer_bytes(b"{not json", _Bridge())
    assert json.loads(answer)["error"]["code"] == remote.PARSE_ERROR


@pytest.mark.parametrize(
    "raw",
    [
        b'{"jsonrpc":"2.0","method":"initialize","id":NaN}',
        (b"[" * 65) + b"0" + (b"]" * 65),
    ],
)
def test_unsafe_json_gets_a_protocol_parse_error(raw: bytes) -> None:
    answer = json.loads(remote.answer_bytes(raw, _Bridge()))

    assert answer["error"]["code"] == remote.PARSE_ERROR


# --- Die Auflagen ---------------------------------------------------------------


def test_an_operation_that_runs_foreign_source_never_travels_over_the_wire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regel 11 und die dritte Auflage aus §7 Etappe 9.

    Eine Operation, die ausführbaren Quelltext entgegennimmt, wäre über eine
    offene Schnittstelle die Ausführung fremden Codes auf diesem Rechner —
    unabhängig davon, wie gut die Quelltextprüfung ist. Sie bliebe im Menü und
    wäre nur nicht fernbedienbar.

    **Die Attrappe ist seit dem 26.08.2026 nötig.** Hier stand
    ``create_from_scad``, die einzige Operation dieser Art; mit dem
    OpenSCAD-Ausbau ist sie entfallen, und ein Test mit ihrem Namen hätte
    danach nur noch geprüft, dass eine Operation, die es nicht gibt, nicht
    gelistet wird. Geprüft wird die **Sperre**, also bekommt eine echte
    Operation die erfundene Eigenschaft.
    """
    monkeypatch.setattr(foreign, "SCRIPTED_OPS", frozenset({"create_box"}))

    answer = remote.handle(request("tools/list"), _Bridge())
    listed = {entry["name"] for entry in answer["result"]["tools"]}
    assert listed, "ohne Werkzeugliste prüft der Vergleich darunter nichts"
    assert "create_box" not in listed

    bridge = _Bridge()
    answer = remote.handle(
        request("tools/call", {"name": "create_box", "arguments": {"width": 10.0}}),
        bridge,
    )
    assert answer["result"]["isError"] is True
    assert not bridge.calls, "abgewiesen, bevor gerechnet wurde"


@pytest.mark.parametrize(
    "value",
    [
        "C:\\Windows\\System32\\config",
        "/etc/passwd",
        "..\\..\\geheim.p3d",
        "../../../etc/shadow",
        "\\\\server\\freigabe\\datei",
        # Ein Pfad in URL-Form ist ein Pfad. Er stand nicht in dieser Liste
        # und kam durch: `file:` trifft keines der vier Merkmale von
        # `looks_like_path` — kein fuehrender Trenner, kein
        # Laufwerksbuchstabe an zweiter Stelle, kein Netzpfad, kein
        # Schritt nach oben.
        "file:///C:/Windows/System32/config",
        "file:///etc/passwd",
        # Relative Angaben sind ebenfalls Pfade. Sie gegen das aktuelle
        # Arbeitsverzeichnis aufzulösen würde nur einen scheinbar sicheren
        # Workspace-Bezug erzeugen: Der Server darf keinen Dateipfad annehmen,
        # auch keinen, dessen Basis erst der Prozess liefert.
        "./model.stl",
        ".\\model.stl",
        "models/part.stl",
        "models\\part.stl",
        "part.stl",
        "mein modell.stl",
        "payload.diesisteineungewoehnlichlangeendung",
        "payload.dies-ist-eine-ungewöhnlich-lange-endung",
        "part.stl:stream",
        "README:stream",
        "README:stream:$DATA",
        "README::$DATA",
        ".",
    ],
)
def test_a_value_that_looks_like_a_path_is_refused(value: str) -> None:
    """Die zweite Auflage, geprüft am Wert statt am Namen.

    Ein Parameter muss nicht ``path`` heißen, um einen Pfad zu tragen. Der
    Name eines Objekts ist Text, und Text nimmt alles auf — geprüft wird
    deshalb, was ankommt.
    """
    bridge = _Bridge()
    answer = remote.handle(
        request("tools/call", {"name": "translate_object", "arguments": {"name": value}}), bridge
    )
    assert answer["result"]["isError"] is True
    assert not bridge.calls


def test_an_ordinary_name_still_gets_through() -> None:
    """Und die Prüfung darf nicht alles verschlucken.

    „Deckel 2" ist ein Name, keine Pfadangabe. Eine Sperre, die zu breit
    greift, macht die Schnittstelle unbrauchbar und sieht dabei sicher aus.
    """
    bridge = _Bridge()
    answer = remote.handle(
        request("tools/call", {"name": "translate_object", "arguments": {"name": "Deckel 2"}}),
        bridge,
    )
    assert answer["result"]["isError"] is False
    assert bridge.calls == [("translate_object", {"name": "Deckel 2"})]


def test_only_the_loopback_address_may_talk() -> None:
    """Die dritte Auflage: nur dieser Rechner.

    Dreimal geprüft — der Server bindet an 127.0.0.1, jede Anfrage nennt ihre
    Herkunft, und ihr ``Origin`` wird gelesen. Eine Bindung allein reicht
    nicht: sie kann durch eine Weiterleitung umgangen werden, und dann steht
    die Schnittstelle im Netz.
    """
    assert remote.HOST == "127.0.0.1"
    assert remote.allowed("127.0.0.1")
    assert remote.allowed("::1")
    assert not remote.allowed("192.168.1.40")
    assert not remote.allowed("10.0.0.1")
    assert not remote.allowed("")


def test_a_web_page_cannot_drive_the_interface() -> None:
    """Die Adressprüfung allein hält keinen Browser auf.

    Er läuft auf diesem Rechner und kommt damit von 127.0.0.1 — welche Seite
    ihn geschickt hat, steht allein im ``Origin``. Eine beliebige aufgerufene
    Seite kann per ``fetch`` einen einfachen POST hierher absetzen; die Antwort
    verbirgt CORS vor ihr, **ausgeführt** wäre der Aufruf trotzdem. Bei einer
    Schnittstelle, die Operationen am offenen Dokument auslöst, ist das der
    Unterschied zwischen Mitlesen und Mitschreiben.
    """
    assert remote.origin_allowed(None), "ein MCP-Client ist kein Browser und schickt keinen"
    assert remote.origin_allowed("http://127.0.0.1:8787")
    assert remote.origin_allowed("http://localhost:3000")
    assert remote.origin_allowed("https://localhost")
    assert remote.origin_allowed("http://[::1]:8787")

    assert not remote.origin_allowed("https://beispiel.de")
    assert not remote.origin_allowed("http://127.0.0.1.angreifer.de"), "der Name endet woanders"
    assert not remote.origin_allowed("null"), "file:// und abgeschottete Rahmen"
    assert not remote.origin_allowed(""), "kein Schema, kein Rechnername"
    assert not remote.origin_allowed("chrome-extension://abcdef")


def test_calling_an_operation_that_does_not_exist_says_so() -> None:
    """Regel 17 gilt auch über die Leitung."""
    bridge = _Bridge()
    answer = remote.handle(
        request("tools/call", {"name": "verbiege_alles", "arguments": {}}), bridge
    )
    assert answer["result"]["isError"] is True
    assert not bridge.calls


def test_the_bridge_may_refuse_and_the_answer_stays_an_answer() -> None:
    """Was der Kern ablehnt, wird zur Fehlerantwort, nicht zum Abbruch.

    Ein Ferngast bekommt denselben Handlungsvorschlag zu lesen, den ein
    Nutzer im Fenster sähe — ein Fehler endet auch hier nicht mit
    „fehlgeschlagen" (Regel 17).
    """

    class _Refusing(_Bridge):
        def call(self, name: str, arguments: dict[str, object]) -> str:
            raise ValidationError("width", "Dieses Maß muss größer als null sein.", value=0)

    answer = remote.handle(
        request("tools/call", {"name": "translate_object", "arguments": {"dx": 1.0}}), _Refusing()
    )
    assert answer["result"]["isError"] is True
    assert "null" in answer["result"]["content"][0]["text"]


def test_asking_a_question_over_the_wire_goes_nowhere_and_is_blocked() -> None:
    """Hier ist niemand zu fragen.

    Im Chat hält der Agent mit ``ask_user`` an und wartet auf eine Antwort aus
    dem Fenster (Leitprinzip 6). Über die Leitung säße die Frage in einem
    Programm fest, das seinen eigenen Nutzer hat — und der Aufruf lief bis
    hierhin durch bis in einen Programmfehler, weil ``ask_user`` keine
    Operation ist und das Register sie nicht kennt.
    """
    answer = remote.handle(request("tools/list"), _Bridge())
    assert "ask_user" not in {entry["name"] for entry in answer["result"]["tools"]}

    bridge = _Bridge()
    answer = remote.handle(
        request("tools/call", {"name": "ask_user", "arguments": {"question": "Welche?"}}), bridge
    )
    assert answer["result"]["isError"] is True
    assert not bridge.calls


def test_the_other_six_extra_tools_stay_reachable() -> None:
    """Und die übrigen bleiben — eine Sperre, die aufräumt, nimmt zu viel mit."""
    listed = {
        entry["name"]
        for entry in remote.handle(request("tools/list"), _Bridge())["result"]["tools"]
    }
    for name in ("undo_transaction", "add_parameter", "set_parameter", "add_fit", "read_report"):
        assert name in listed, name


def test_a_path_inside_a_list_is_refused() -> None:
    """Die Zusage lautet „am Wert erkannt" (§32).

    Flach zu prüfen genügte nicht: jedes Operationswerkzeug trägt seine Objekte
    als Liste, und derselbe Text, der als Zeichenkette abgewiesen wird, kam
    darin durch.
    """
    with pytest.raises(remote.RemoteRefusedError):
        remote.check_call("translate_object", {"objects": ["C:/Windows/system.ini"], "dx": 1.0})


def test_a_path_inside_a_nested_object_is_refused() -> None:
    with pytest.raises(remote.RemoteRefusedError):
        remote.check_call("translate_object", {"objects": ["obj_1"], "meta": {"file": "../../x"}})


def test_an_ordinary_call_still_passes() -> None:
    """Eine Sperre, die „Deckel 2" verschluckt, macht die Schnittstelle
    unbrauchbar und sieht dabei sicher aus."""
    remote.check_call("translate_object", {"objects": ["obj_1"], "dx": 1.0})


# --- Was eine Operation tut, nicht wie sie heißt (Review 25.08.2026) ---------------


@pytest.fixture
def scripted_recipe_part(monkeypatch: pytest.MonkeyPatch):
    """Ein Rezept-Baustein, dessen Schritte eine quelltextführende Op enthalten.

    Welche Operation das ist, sagt :data:`foreign.SCRIPTED_OPS` — und die ist
    seit dem OpenSCAD-Ausbau leer. Die Fixture setzt sie deshalb auf eine echte
    Operation: Geprüft wird, dass die Sperre **durch ein Rezept hindurch**
    sieht, und das hat mit dem Namen der Operation nichts zu tun.

    Global registriert, weil beide Sperren den Baustein über den
    Operationsnamen suchen — der Weg, den ein Fernaufruf auch nimmt. Der
    Eintrag geht danach wieder weg; die Prüfung schaut auf **einen** Namen,
    nicht auf die Größe des Katalogs.
    """
    from app.core.knowledge.parts import ops as part_ops
    from app.core.knowledge.parts.registry import PARTS, PartSpec
    from app.core.registry import REGISTRY, Registry, op_params, param
    from app.core.types import BaseParams, PartResult

    @op_params
    class Params(BaseParams):
        size: float = param(title="Größe", default=10.0, minimum=1.0, maximum=100.0)

    def build(values: BaseParams) -> PartResult:  # pragma: no cover - nie gerechnet
        raise AssertionError("dieser Baustein wird nicht gebaut")

    spec = PartSpec(
        name="scad_probe",
        title="Probe aus Quelltext",
        group="fasteners",
        params=Params,
        fn=build,
        features=("body",),
        doc="Ein Rezept, dessen Schritte ein fremdes Programm anwerfen.",
        source="recipe",
        recipe_data={"document": {"ops": [{"op": "create_box", "params": {"width": 10.0}}]}},
    )
    monkeypatch.setattr(foreign, "SCRIPTED_OPS", frozenset({"create_box"}))
    registry = Registry()
    PARTS.register(spec)
    part_ops.register_one(spec, registry)
    try:
        yield part_ops.op_name(spec.name), registry
    finally:
        PARTS.remove(spec.name)
        REGISTRY._ops.pop(part_ops.op_name(spec.name), None)


def test_a_recipe_that_runs_openscad_is_locked_like_the_operation_itself(
    scripted_recipe_part,
) -> None:
    """**Beide Sperren verglichen den Namen.**

    Ein Rezept darf seit dem 24.08.2026 einen ``create_from_scad``-Schritt
    tragen (Regel 13) — und es heißt dann ``insert_<name>``. Damit war es über
    die Leitung erreichbar: angeboten, nicht abgewiesen, und der Aufruf hätte
    OpenSCAD auf diesem Rechner gestartet. Gefragt wird jetzt, was die
    Operation **tut**.
    """
    name, registry = scripted_recipe_part

    assert name not in {entry["name"] for entry in remote.remote_tools(registry)}

    with pytest.raises(remote.RemoteRefusedError):
        remote.check_call(name, {"size": 10.0}, registry)


def test_such_a_recipe_is_not_accepted_without_asking(scripted_recipe_part) -> None:
    """Dieselbe Frage an der zweiten Stelle (§26.5): Ein Vorschlag mit diesem
    Schritt galt als eindeutig umkehrbar und lief ohne Rückfrage durch.
    """
    from app.core.agent.apply import auto_acceptable
    from app.core.agent.proposal import Proposal
    from app.core.scene.history import OperationDraft

    name, registry = scripted_recipe_part
    proposal = Proposal(request="Setz die Probe ein")
    proposal.drafts.append(OperationDraft(op=name, inputs=("obj_1",), params={"size": 10.0}))

    assert not auto_acceptable(proposal, registry)


@pytest.fixture
def nested_recipe_part(scripted_recipe_part):
    """Ein Rezept, das ein Rezept mit Quelltext einsetzt — Ebene zwei.

    ``recipe.capture`` nimmt beliebige registrierte Operationen auf, also auch
    ein ``insert_<name>``. Die Schrittliste des äußeren Rezepts nennt dann nur
    diesen Namen, und der Quelltext steht eine Etage tiefer.
    """
    from app.core.knowledge.parts import ops as part_ops
    from app.core.knowledge.parts.registry import PARTS, PartSpec
    from app.core.registry import REGISTRY, op_params, param
    from app.core.types import BaseParams, PartResult

    inner, registry = scripted_recipe_part

    @op_params
    class Params(BaseParams):
        size: float = param(title="Größe", default=10.0, minimum=1.0, maximum=100.0)

    def build(values: BaseParams) -> PartResult:  # pragma: no cover - nie gerechnet
        raise AssertionError("dieser Baustein wird nicht gebaut")

    spec = PartSpec(
        name="scad_huelle",
        title="Hülle um die Probe",
        group="fasteners",
        params=Params,
        fn=build,
        features=("body",),
        doc="Ein Rezept, das ein Rezept mit Quelltext einsetzt.",
        source="recipe",
        recipe_data={"document": {"ops": [{"op": inner, "params": {}}]}},
    )
    PARTS.register(spec)
    part_ops.register_one(spec, registry)
    try:
        yield part_ops.op_name(spec.name), registry
    finally:
        PARTS.remove(spec.name)
        REGISTRY._ops.pop(part_ops.op_name(spec.name), None)


def test_a_recipe_inside_a_recipe_is_locked_just_the_same(nested_recipe_part) -> None:
    """Die Sperre sah genau eine Ebene tief.

    Wer Rezept A über ``insert_A`` in Rezept B aufnimmt, bekam ein
    ``insert_B``, dessen Schrittliste nur ``insert_A`` nennt: über die Leitung
    angeboten und aufrufbar, obwohl der Aufruf OpenSCAD auf diesem Rechner
    startet. Gefragt wird jetzt beliebig tief.
    """
    name, registry = nested_recipe_part

    assert name not in {entry["name"] for entry in remote.remote_tools(registry)}

    with pytest.raises(remote.RemoteRefusedError):
        remote.check_call(name, {"size": 10.0}, registry)


def test_an_ordinary_part_stays_reachable() -> None:
    """Eine Sperre, die alle Bausteine mitnimmt, macht die Schnittstelle
    unbrauchbar und sieht dabei sicher aus."""
    listed = {entry["name"] for entry in remote.remote_tools()}

    assert "insert_screw_hole" in listed


def test_the_refusal_for_a_question_names_the_right_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """„Sie führt fremden Quelltext aus" stand für beide Sperrgründe und war
    für ``ask_user`` schlicht falsch (Regel 17).
    """
    grund = str(remote.refusal_for("ask_user"))

    assert "Quelltext" not in grund

    monkeypatch.setattr(foreign, "SCRIPTED_OPS", frozenset({"create_box"}))
    assert "Quelltext" in str(remote.refusal_for("create_box"))


# --- Gesten kommen vom Nutzer, nicht über die Leitung ------------------------------


def test_a_gathered_parameter_is_refused_over_the_wire() -> None:
    """**Die Chat-Sitzung lehnt sie ab, die Leitung tat es nicht.**

    Skizzenpunkte, Pinselstriche und Skelett entstehen aus Gesten (§26,
    Leitprinzip 5). Das Werkzeugschema bietet sie nicht an — ein Wert unter dem
    richtigen Namen ging hier trotzdem ungeprüft an die Anwendung, wo ihn kein
    Schema mehr erwartete.
    """
    from app.core.registry import GATHERED_KINDS, REGISTRY

    fundstelle = next(
        (
            (spec.name, entry.name)
            for spec in REGISTRY.all()
            for entry in spec.params.spec()
            if entry.kind in GATHERED_KINDS
        ),
        None,
    )
    assert fundstelle is not None, "ohne gesammelte Parameter prüft dieser Test nichts"
    name, feld = fundstelle

    with pytest.raises(remote.RemoteRefusedError):
        remote.check_call(name, {"objects": ["obj_1"], feld: "geraten"})
