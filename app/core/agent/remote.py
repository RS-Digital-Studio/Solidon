"""Die Schnittstelle nach außen: MCP über JSON-RPC (Bauplan §26, D19).

Ein zweites Programm — Claude Code, ein Editor, ein Skript — soll dieselben
Operationen aufrufen können wie das Menü. Der Weg dorthin ist derselbe wie beim
Chat: das Register liefert die Werkzeuge (§10), die Sitzung macht daraus eine
Transaktion, und ein Strg+Z im Fenster nimmt sie zurück. Es gibt keine zweite
Liste und keinen zweiten Weg ins Dokument.

**Vier Auflagen, und keine davon ist optional.**

* Standardmäßig aus. Eine offene Schnittstelle, die niemand eingeschaltet hat,
  ist eine offene Tür.
* Nur ``127.0.0.1``. Dreimal geprüft — die Bindung, die Absenderadresse jeder
  Anfrage und ihr ``Origin``. Eine Bindung allein lässt sich durch eine
  Weiterleitung umgehen, und die Adresse allein sagt beim Browser nichts: der
  läuft auf diesem Rechner, ganz gleich, welche Seite ihn geschickt hat.
* Kein ausführbarer Quelltext, kein Dateipfad. Beides wird abgewiesen, **bevor**
  gerechnet wird; ein Aufruf, der erst rechnet und danach merkt, dass er nicht
  durfte, hat schon getan, was er nicht sollte.
* Jeder Aufruf eine Transaktion mit Herkunftsvermerk. Wer hinterher wissen
  will, was von außen kam, sieht es im Verlauf.

Ohne Netzbibliothek und ohne SDK: JSON-RPC ist ein Umschlag um einen Namen und
ein Wörterbuch, und die Standardbibliothek trägt ihn. Eine Abhängigkeit dafür
wäre eine Lizenzzeile für dreißig Zeilen Code (Regel 22).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Final, Protocol
from urllib.parse import urlsplit

from app.branding import APP_NAME, APP_VERSION
from app.core.agent.tools import ASK_USER, runs_foreign_source, tool_schemas
from app.core.errors import AppError
from app.core.registry import Registry
from app.i18n import TranslatableText, _

#: Die Version des Protokolls, auf die sich beide Seiten einigen.
PROTOCOL_VERSION: Final = "2024-11-05"

#: Woran gebunden wird. Keine Einstellung — wer von außen erreichbar sein will,
#: baut sich einen Tunnel und weiß dann, was er tut.
HOST: Final = "127.0.0.1"

#: Voreingestellter Port. Über 1024, damit kein erhöhtes Recht nötig ist.
DEFAULT_PORT: Final = 8787

#: JSON-RPC-Fehlercodes, so wie die Spezifikation sie vergibt.
PARSE_ERROR: Final = -32700
INVALID_REQUEST: Final = -32600
METHOD_NOT_FOUND: Final = -32601
INTERNAL_ERROR: Final = -32603

#: Werkzeuge, die nie fernbedienbar sind.
#:
#: ``create_from_scad`` nimmt ausführbaren Quelltext entgegen. Über eine offene
#: Schnittstelle wäre das die Ausführung fremden Codes auf diesem Rechner —
#: unabhängig davon, wie gründlich die Quelltextprüfung aus §32 ist, denn sie
#: prüft, was der Nutzer selbst eingegeben hat. Die Operation bleibt im Menü;
#: sie ist nur nicht fernsteuerbar.
#:
#: ``ask_user`` ist gesperrt, weil hier niemand zu fragen ist. Im Chat hält der
#: Agent damit an und wartet auf eine Antwort aus dem Fenster (Leitprinzip 6);
#: über die Leitung säße die Frage in einem Programm fest, das seinen eigenen
#: Nutzer hat. Wer fern steuert, fragt ihn selbst — und tut es an der Stelle,
#: an der er sitzt.
#:
#: **Diese Liste allein reicht nicht**, und das ist der Grund, warum
#: :func:`refusal_for` daneben steht: Ein Rezept darf einen
#: ``create_from_scad``-Schritt tragen (Regel 13) und heißt dann
#: ``insert_<name>``. Ein Name in einer Liste erwischt das nicht — gefragt wird
#: zusätzlich, was eine Operation **tut**.
DENIED: Final[frozenset[str]] = frozenset({"create_from_scad", ASK_USER})

#: Adressen, die als „dieser Rechner" gelten.
_LOOPBACK: Final[frozenset[str]] = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})

#: Rechnernamen, die in einem ``Origin`` als „dieser Rechner" gelten.
_LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"127.0.0.1", "localhost", "::1"})


class Bridge(Protocol):
    """Was die Anwendung beisteuert: einen Aufruf ausführen.

    Absichtlich schmal. Diese Schicht kennt kein Dokument, keine Sitzung und
    kein Fenster — sie packt aus, prüft und reicht weiter. Alles Weitere
    entscheidet die Seite, die das Dokument hält.
    """

    def call(self, name: str, arguments: dict[str, Any]) -> str: ...


def allowed(address: str) -> bool:
    """Ob diese Gegenstelle sprechen darf.

    Nur der eigene Rechner. Die Prüfung steht zusätzlich zur Bindung, weil
    eine Bindung sich weiterleiten lässt: ein Proxy davor, und die
    Schnittstelle steht im Netz, ohne dass hier eine Zeile anders liefe.
    """
    return address in _LOOPBACK


def origin_allowed(origin: str | None) -> bool:
    """Ob eine Anfrage mit diesem ``Origin`` sprechen darf.

    Die dritte Prüfung zur zweiten Auflage — und die einzige, die den Browser
    erfasst. Er läuft auf demselben Rechner, kommt also von ``127.0.0.1`` und
    besteht :func:`allowed` mühelos. Eine beliebige aufgerufene Webseite kann
    ihn per ``fetch`` zu einem POST hierher bewegen: die **Antwort** bekommt
    sie durch CORS nie zu sehen, der Aufruf wäre trotzdem **ausgeführt**. Bei
    einer Schnittstelle, die Operationen am offenen Dokument auslöst, ist das
    der Unterschied zwischen Mitlesen und Mitschreiben.

    Ohne Kopfzeile: erlaubt. Ein MCP-Client ist kein Browser und schickt
    keine — und gerade darin liegt der Wert dieser Prüfung: ``Origin`` hängt
    der Browser von sich aus an, und Seiten-Code kann ihn nicht fälschen.

    ``Origin: null`` (aus einer ``file://``-Seite oder einem abgeschotteten
    Rahmen) hat keinen Rechnernamen und fällt damit durch.
    """
    if origin is None:
        return True
    parts = urlsplit(origin)
    if parts.scheme not in ("http", "https"):
        return False
    return (parts.hostname or "") in _LOOPBACK_HOSTS


def remote_tools(registry: Registry | None = None) -> tuple[dict[str, Any], ...]:
    """Die Werkzeuge, die über die Leitung erreichbar sind.

    Dieselben wie im Chat, abzüglich der gesperrten. Aus dem Register, nicht
    aus einer Liste — siehe ``tools.py``.

    Gesperrt heißt hier auch: nicht angeboten. Eine Operation, die
    :func:`check_call` abweisen wird, in der Liste zu führen, hieße, der
    Gegenstelle einen Weg zu zeigen, den es nicht gibt."""
    return tuple(
        entry
        for entry in tool_schemas(registry)
        if entry["name"] not in DENIED and not runs_foreign_source(str(entry["name"]))
    )


def looks_like_path(value: str) -> bool:
    """Ob dieser Text ein Dateipfad sein könnte.

    Am **Wert** geprüft und nicht am Namen des Parameters: ein Feld muss nicht
    ``path`` heißen, um einen Pfad zu tragen — der Name eines Objekts ist Text,
    und Text nimmt alles auf.

    Absichtlich eng gefasst. „Deckel 2" ist ein Name, und eine Sperre, die zu
    breit greift, macht die Schnittstelle unbrauchbar und sieht dabei sicher
    aus. Erkannt wird, was ohne Zweifel ein Pfad ist: ein Laufwerksbuchstabe,
    ein führender Trenner, ein Netzpfad, ein Schritt nach oben — oder ein
    Pfad in URL-Form.

    **``file:`` kam durch**, und zwar weil es keines der anderen vier Merkmale
    trifft: kein führender Trenner, der Doppelpunkt steht an fünfter Stelle
    statt an zweiter, kein Netzpfad, kein Schritt nach oben. Heute nimmt keine
    Operation eine URL an, der Weg war also zu — aber die Auflage aus §26.6
    sagt „kein Dateipfad", und ein Pfad mit Schema davor bleibt einer. Eine
    Sperre, die erst greift, wenn irgendwo ein Feld für eine Adresse entsteht,
    greift zu spät.
    """
    text = value.strip()
    if not text:
        return False
    if text.lower().startswith("file:"):
        return True
    if text.startswith(("/", "\\", "~")):
        return True
    if len(text) > 1 and text[1] == ":" and text[0].isalpha():
        return True
    return ".." in text.replace("\\", "/").split("/")


def _holds_path(value: Any) -> bool:
    """Ob irgendwo in diesem Wert ein Pfad steckt.

    Flach zu prüfen genügte nicht: jedes Operationswerkzeug trägt seine Objekte
    als Liste, und derselbe Text, der als Zeichenkette abgewiesen wird, käme in
    einer Liste durch. Die Zusage lautet „am Wert erkannt" — dann muss auch
    hineingesehen werden, wo Werte ineinander liegen.
    """
    if isinstance(value, str):
        return looks_like_path(value)
    if isinstance(value, Mapping):
        return any(_holds_path(entry) for entry in value.values())
    if isinstance(value, (list, tuple)):
        return any(_holds_path(entry) for entry in value)
    return False


def refusal_for(name: str) -> TranslatableText | None:
    """Warum diese Operation gesperrt ist — ``None``, wenn sie es nicht ist.

    Zwei Gründe, zwei Sätze. Bis hierhin stand einer für beide, und für
    ``ask_user`` war er schlicht falsch: „sie führt fremden Quelltext aus"
    schickt jemanden auf die Suche nach einem Quelltext, den es nicht gibt
    (Regel 17).

    Und die Frage nach dem Quelltext geht an die Wirkung, nicht an den Namen:
    Ein Rezept mit einem ``create_from_scad``-Schritt heißt ``insert_<name>``
    (Regel 13) und stand in keiner Liste — über die Leitung erreichbar und
    ohne Rückfrage annehmbar.
    """
    if name == ASK_USER:
        return _(
            "Über diese Schnittstelle ist niemand zu fragen — die Rückfrage "
            "gehört dorthin, wo Ihr eigener Nutzer sitzt."
        )
    if name in DENIED or runs_foreign_source(name):
        return _(
            "Diese Operation ist über die Schnittstelle gesperrt: sie führt fremden Quelltext aus."
        )
    return None


def check_call(name: str, arguments: dict[str, Any], registry: Registry | None = None) -> None:
    """Wirft, wenn dieser Aufruf nicht über die Leitung kommen darf.

    Vor der Rechnung, nicht danach. Die Reihenfolge ist die eigentliche
    Zusage: gesperrte Operation, unbekannte Operation, gesammelter Parameter,
    verdächtiger Wert — und erst wenn alle vier durch sind, sieht die Anwendung
    den Aufruf überhaupt.
    """
    refusal = refusal_for(name)
    if refusal is not None:
        raise RemoteRefusedError(refusal)
    known = {entry["name"] for entry in remote_tools(registry)}
    if name not in known:
        raise RemoteRefusedError(_("Diese Operation gibt es nicht."))
    _refuse_gathered(name, arguments, registry)
    for key, value in arguments.items():
        if _holds_path(value):
            refused = _(
                "Ein Wert sieht aus wie ein Dateipfad — über diese Schnittstelle geht das nicht."
            )
            raise RemoteRefusedError(f"{refused} ({key})")


def _refuse_gathered(name: str, arguments: dict[str, Any], registry: Registry | None) -> None:
    """Gesammelte Parameter kommen vom Nutzer, nicht über die Leitung
    (§26, Leitprinzip 5).

    Skizzenpunkte, Pinselstriche, Skelett und Stellung entstehen aus Gesten.
    Das Werkzeugschema bietet sie deshalb nicht an — die Chat-Sitzung lehnt
    sie trotzdem ab, falls ein Modell sie rät, und nennt dabei den Weg, der
    offen bleibt. Hier fehlte beides: Ein Wert unter dem richtigen Namen ging
    ungeprüft an die Anwendung, wo ihn kein Schema mehr erwartete.

    Ein unbekanntes Werkzeug ist hier kein Fehler mehr — die Zeile darüber hat
    das schon abgelehnt; was hier ankommt, steht im Register.
    """
    from app.core.registry import GATHERED_KINDS, REGISTRY

    source = registry or REGISTRY
    if not source.has(name):
        return
    for entry in source.get(name).params.spec():
        if entry.kind in GATHERED_KINDS and arguments.get(entry.name):
            refused = _(
                "Dieser Parameter entsteht aus Gesten des Nutzers und wird nicht "
                "ferngesteuert — Skizze, Pinsel und Skelett gehören ins Fenster."
            )
            raise RemoteRefusedError(f"{refused} ({entry.name})")


class RemoteRefusedError(Exception):
    """Ein Aufruf, der die Auflagen verletzt. Bleibt hier und wird zur
    Fehlerantwort — der Kern sieht ihn nie."""


def handle(payload: dict[str, Any], bridge: Bridge) -> dict[str, Any]:
    """Eine JSON-RPC-Anfrage beantworten.

    Rein rechnend: kein Netz, kein Zustand, keine Nebenwirkung außer der, die
    die Brücke auslöst. Deshalb ist die ganze Protokollschicht ohne Server
    prüfbar.
    """
    ident = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if method == "initialize":
        return _result(
            ident,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": APP_NAME, "version": APP_VERSION},
            },
        )
    if method in ("notifications/initialized", "ping"):
        return _result(ident, {})
    if method == "tools/list":
        return _result(ident, {"tools": [dict(entry) for entry in remote_tools()]})
    if method == "tools/call":
        return _result(ident, _called(params, bridge))
    return _error(ident, METHOD_NOT_FOUND, _("Diese Methode gibt es nicht."))


def _called(params: dict[str, Any], bridge: Bridge) -> dict[str, Any]:
    """Ein Werkzeugaufruf, mit allen Auflagen davor.

    Auch ein Fehler ist ein Ergebnis: MCP unterscheidet zwischen einem
    Protokollfehler (die Anfrage war unverständlich) und einem Werkzeugfehler
    (das Werkzeug hat nicht gekonnt). Ein abgewiesener Aufruf ist das Zweite,
    und deshalb liest die Gegenstelle den Handlungsvorschlag wie ein Nutzer im
    Fenster (Regel 17).
    """
    name = str(params.get("name", ""))
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return _tool_error(str(_("Die Argumente sind ein Objekt.")))
    try:
        check_call(name, arguments)
        answer = bridge.call(name, arguments)
    except RemoteRefusedError as refused:
        return _tool_error(str(refused))
    except AppError as problem:
        return _tool_error(_readable(problem))
    return {"content": [{"type": "text", "text": answer}], "isError": False}


def _readable(problem: AppError) -> str:
    """Ein Fehler als Text, mit seinen Handlungsvorschlägen.

    Dieselben drei Teile wie im Fenster: was nicht ging, warum, was jetzt
    möglich ist (§2.7). Ein Ferngast hat keinen Knopf zum Anklicken, also
    stehen die Vorschläge als Aufzählung darunter — weglassen hieße, ihm
    genau das vorzuenthalten, was Regel 17 zusichert.
    """
    lines = [str(problem.title)]
    if problem.detail is not None:
        lines.append(str(problem.detail))
    lines.extend(f"- {action.label}" for action in problem.suggestions)
    return "\n".join(lines)


def _tool_error(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": True}


def _result(ident: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def _error(ident: Any, code: int, message: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": str(message)}}


def answer_bytes(raw: bytes, bridge: Bridge) -> bytes:
    """Von rohen Zeichen zur rohen Antwort — die Form, die ein Server braucht.

    Ein abgeschnittener Datenstrom ist der Normalfall und keine Ausnahme; er
    bekommt eine Antwort wie alles andere, statt den Server zu beenden.
    """
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _dumped(_error(None, PARSE_ERROR, _("Das war kein gültiges JSON.")))
    if not isinstance(payload, dict):
        return _dumped(_error(None, INVALID_REQUEST, _("Eine Anfrage ist ein Objekt.")))
    try:
        return _dumped(handle(payload, bridge))
    except Exception:
        # Ein Server, der bei einer kaputten Anfrage abbricht, ist keiner.
        return _dumped(_error(payload.get("id"), INTERNAL_ERROR, _("Unerwarteter Fehler.")))


def _dumped(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")
