"""Das Sprachmodell hinter dem Agenten (Bauplan §27).

Eine Schnittstelle, drei Wege sie zu erfüllen: der eigene Schlüssel des
Nutzers gegen ein gehostetes Modell, ein lokales Modell über Ollama, und ein
geskriptetes für die Suite. Die Agentenschicht darüber erfährt nie, welches
geantwortet hat.

Zwei Dinge sind Absicht. Erstens kein Hersteller-SDK: die Anfrage ist eine
Handvoll JSON-Felder, und die Antwort ist JSON zurück — eine Abhängigkeit, die
lizenzgeprüft und aktualisiert werden muss, ist dafür ein schlechter Tausch
(§36). Zweitens ist der Transport eine Funktion, die sich austauschen lässt —
die Suite fährt den ganzen Agenten, ohne ein Netz anzufassen.

Ohne Schlüssel sind die Agentenfunktionen abgeschaltet, und alles andere läuft
weiter (§27). Das ist kein Rückfall, das ist der Normalzustand auf einem
frischen Rechner.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.core.backends import keys
from app.core.errors import AppError
from app.core.log import get_logger
from app.i18n import _

_log = get_logger(__name__)

Role = Literal["system", "user", "assistant", "tool"]

#: Wie lange eine einzelne Anfrage dauern darf, bevor sie aufgegeben wird.
TIMEOUT_SECONDS = 120.0

#: Wie lange die Prüfung „läuft ein lokales Modell" dauern darf. Sie passiert,
#: während das Fenster gebaut wird, muss also vorbei sein, bevor es jemand
#: bemerkt.
PROBE_SECONDS = 0.25


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Eine Operation, die das Modell ausführen will, mit ihren Argumenten."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Message:
    """Ein Gesprächsbeitrag, wie das Backend ihn sieht."""

    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    """Set on a ``tool`` message: which call this is the answer to."""


@dataclass(frozen=True, slots=True)
class Reply:
    """Was zurückkam: Worte, Aufrufe, und was es gekostet hat."""

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    model: str = ""
    stop_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLMBackend(Protocol):
    """Was der Agent von einem Modell braucht, und nicht mehr."""

    @property
    def id(self) -> str:
        """Short name the settings and the transaction origin record (§26.4)."""
        ...

    @property
    def model(self) -> str: ...

    @property
    def available(self) -> bool:
        """False when there is no key or no local server — the chat greys out."""
        ...

    def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]] = (),
        *,
        temperature: float = 0.0,
    ) -> Reply: ...


Transport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]
"""``url, headers, payload -> answer``. Replaceable, which is what makes the
agent testable without a network."""


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    """Der Vorgabe-Transport: ein POST, JSON hinein, JSON heraus."""
    body = json.dumps(payload).encode("utf-8")
    # Die Adresse kommt aus dem Backend, nie aus etwas, das das Modell gesagt hat.
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json", **headers}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:
            return dict(json.loads(answer.read().decode("utf-8")))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise BackendUnavailable(status=error.code, detail=detail) from error
    except urllib.error.URLError as error:
        raise BackendUnavailable(detail=str(error.reason)) from error


class BackendUnavailable(AppError):
    """Das Modell war nicht erreichbar oder hat abgelehnt."""

    default_title = _("Das Sprachmodell hat nicht geantwortet.")

    def __init__(self, status: int | None = None, detail: str = "") -> None:
        super().__init__(
            detail=detail or None,
            values={"status": str(status)} if status is not None else {},
        )


# --- Gehostet, mit dem eigenen Schlüssel des Nutzers -------------------------------


DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


@dataclass(slots=True)
class AnthropicBackend:
    """Ein gehostetes Modell, erreicht mit dem Schlüssel aus dem
    Schlüsselbund (§27).
    """

    model: str = DEFAULT_ANTHROPIC_MODEL
    transport: Transport = post_json
    max_tokens: int = 4096

    @property
    def id(self) -> str:
        return "anthropic"

    @property
    def available(self) -> bool:
        return keys.read(self.id) is not None

    def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]] = (),
        *,
        temperature: float = 0.0,
    ) -> Reply:
        key = keys.read(self.id)
        if key is None:
            raise BackendUnavailable(detail="no key stored")

        system = " ".join(entry.content for entry in messages if entry.role == "system")
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "messages": [_as_anthropic(entry) for entry in messages if entry.role != "system"],
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [_as_anthropic_tool(entry) for entry in tools]

        answer = self.transport(
            ANTHROPIC_URL,
            {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION},
            payload,
        )
        return _from_anthropic(answer)


def _as_anthropic(message: Message) -> dict[str, Any]:
    if message.role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content,
                }
            ],
        }
    blocks: list[dict[str, Any]] = []
    if message.content:
        blocks.append({"type": "text", "text": message.content})
    for call in message.tool_calls:
        blocks.append(
            {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
        )
    return {"role": message.role, "content": blocks or [{"type": "text", "text": ""}]}


def _as_anthropic_tool(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": schema["name"],
        "description": schema.get("description", ""),
        "input_schema": schema.get("input_schema", {"type": "object", "properties": {}}),
    }


def _from_anthropic(answer: dict[str, Any]) -> Reply:
    text: list[str] = []
    calls: list[ToolCall] = []
    for block in answer.get("content", ()):
        if block.get("type") == "text":
            text.append(str(block.get("text", "")))
        elif block.get("type") == "tool_use":
            calls.append(
                ToolCall(
                    id=str(block.get("id", "")),
                    name=str(block.get("name", "")),
                    arguments=dict(block.get("input", {})),
                )
            )
    usage = answer.get("usage", {})
    return Reply(
        text="".join(text),
        tool_calls=tuple(calls),
        model=str(answer.get("model", "")),
        stop_reason=str(answer.get("stop_reason", "")),
        input_tokens=int(usage.get("input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
    )


# --- local, over Ollama -----------------------------------------------------------


DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:14b"
OLLAMA_URL = "http://localhost:11434/api/chat"


def _configured_ollama_url() -> str:
    """Die eingetragene Ollama-Adresse, sonst die auf dieser Maschine.

    Der Import steht im Aufruf: :mod:`app.core.discover` liest die
    Nutzerkonfiguration, und eine Testumgebung lenkt die noch um.
    """
    from app.core import discover

    return discover.service_url("ollama", OLLAMA_URL)


@dataclass(slots=True)
class OllamaBackend:
    """Ein lokales Modell. §27: Werkzeugaufrufe brauchen ein hinreichend
    großes Modell — kleine scheitern daran, und der Fehler sagt das.
    """

    model: str = DEFAULT_OLLAMA_MODEL
    # Wie bei ComfyUI: die Adresse darf woanders hinzeigen, wenn das Modell auf
    # einem zweiten Rechner läuft (§38).
    url: str = field(default_factory=lambda: _configured_ollama_url())
    transport: Transport = post_json

    @property
    def id(self) -> str:
        return "ollama"

    @property
    def available(self) -> bool:
        """Is a server listening?

        Asked with a socket rather than with a request: the answer is needed
        while a window is being built, and an HTTP call to a closed port costs
        seconds on some machines — long enough to be felt on every start.
        """
        import socket
        from urllib.parse import urlparse

        address = urlparse(self.url)
        try:
            with socket.create_connection(
                (address.hostname or "localhost", address.port or 11434),
                timeout=PROBE_SECONDS,
            ):
                return True
        except OSError:
            return False

    def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]] = (),
        *,
        temperature: float = 0.0,
    ) -> Reply:
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": temperature},
            "messages": [_as_ollama(entry) for entry in messages],
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": entry["name"],
                        "description": entry.get("description", ""),
                        "parameters": entry.get("input_schema", {"type": "object"}),
                    },
                }
                for entry in tools
            ]

        answer = self.transport(self.url, {}, payload)
        return _from_ollama(answer, self.model)


def _as_ollama(message: Message) -> dict[str, Any]:
    entry: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        entry["tool_calls"] = [
            {"function": {"name": call.name, "arguments": call.arguments}}
            for call in message.tool_calls
        ]
    return entry


def _from_ollama(answer: dict[str, Any], model: str) -> Reply:
    message = answer.get("message", {})
    calls = tuple(
        ToolCall(
            id=f"call_{index}",
            name=str(entry.get("function", {}).get("name", "")),
            arguments=dict(entry.get("function", {}).get("arguments", {})),
        )
        for index, entry in enumerate(message.get("tool_calls", ()), start=1)
    )
    return Reply(
        text=str(message.get("content", "")),
        tool_calls=calls,
        model=str(answer.get("model", model)),
        stop_reason=str(answer.get("done_reason", "")),
        input_tokens=int(answer.get("prompt_eval_count", 0)),
        output_tokens=int(answer.get("eval_count", 0)),
    )


# --- choosing one -----------------------------------------------------------------


def backends() -> tuple[LLMBackend, ...]:
    """Alles, was antworten könnte, in der Reihenfolge, in der die
    Einstellungen es anbieten."""
    return (AnthropicBackend(), OllamaBackend())


def first_available() -> LLMBackend | None:
    """Das Backend, das der Chat ungefragt benutzt. None heißt: kein
    Chat (§27)."""
    for backend in backends():
        if backend.available:
            return backend
    return None
