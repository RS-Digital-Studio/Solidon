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


# --- Die Auflagen ---------------------------------------------------------------


def test_openscad_source_never_travels_over_the_wire() -> None:
    """Regel 11 und die dritte Auflage aus §7 Etappe 9.

    ``create_from_scad`` nimmt ausführbaren Quelltext. Über eine offene
    Schnittstelle wäre das die Ausführung fremden Codes auf diesem Rechner —
    unabhängig davon, wie gut die Quelltextprüfung ist. Die Operation gibt es
    weiter; sie ist nur nicht fernbedienbar.
    """
    answer = remote.handle(request("tools/list"), _Bridge())
    listed = {entry["name"] for entry in answer["result"]["tools"]}
    assert "create_from_scad" not in listed

    bridge = _Bridge()
    answer = remote.handle(
        request("tools/call", {"name": "create_from_scad", "arguments": {"source": "cube(10);"}}),
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

    Zweimal geprüft — der Server bindet an 127.0.0.1, und jede Anfrage nennt
    ihre Herkunft. Eine Bindung allein reicht nicht: sie kann durch eine
    Weiterleitung umgangen werden, und dann steht die Schnittstelle im Netz.
    """
    assert remote.HOST == "127.0.0.1"
    assert remote.allowed("127.0.0.1")
    assert remote.allowed("::1")
    assert not remote.allowed("192.168.1.40")
    assert not remote.allowed("10.0.0.1")
    assert not remote.allowed("")


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
