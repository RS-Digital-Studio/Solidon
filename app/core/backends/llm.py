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
from typing import Any, Final, Literal, Protocol

from app.core.backends import keys
from app.core.errors import AppError
from app.core.log import get_logger
from app.i18n import TranslatableText, _

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
    """Bei einer ``tool``-Nachricht gesetzt: auf welchen Aufruf sie antwortet."""


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
        """Kurzname, den die Einstellungen und die Transaktionsherkunft
        festhalten (§26.4).
        """
        ...

    @property
    def model(self) -> str: ...

    @property
    def available(self) -> bool:
        """False, wenn es keinen Schlüssel und keinen lokalen Server gibt — der
        Chat graut dann aus."""
        ...

    def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]] = (),
        *,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ) -> Reply:
        """``max_output_tokens`` ist eine Obergrenze für diese eine Antwort,
        keine Zusage: die Sitzung reicht ihr verbleibendes Zugbudget herein
        (§26.5), und ein Backend, für das die Grenze nichts bedeutet — lokal
        kostet eine Antwort kein Geld — darf sie ignorieren.
        """
        ...


Transport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]
"""``url, headers, payload -> answer``. Austauschbar — genau das macht den
Agenten ohne Netz prüfbar."""


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
    max_tokens: int = 8192
    """Obergrenze je Antwort. Ein Parameter, keine Konstante: 4096 fest
    verdrahtet neben einem Zugbudget von 120 000 war unbegründet knapp —
    ein abgeschnittener Antworttext ist ein eigener Fehlerfall, den niemand
    braucht. Das Zugbudget deckelt zusätzlich über ``max_output_tokens``."""

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
        max_output_tokens: int | None = None,
    ) -> Reply:
        key = keys.read(self.id)
        if key is None:
            raise BackendUnavailable(detail="no key stored")

        limit = self.max_tokens
        if max_output_tokens is not None:
            limit = max(1, min(limit, max_output_tokens))

        system = " ".join(entry.content for entry in messages if entry.role == "system")
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": limit,
            "temperature": temperature,
            "messages": [_as_anthropic(entry) for entry in messages if entry.role != "system"],
        }
        if system:
            # Der Systemblock ist über alle Schritte eines Zuges identisch —
            # die Markierung lässt ihn im Zwischenspeicher der Gegenseite
            # liegen, statt ihn je Schritt neu zu verrechnen.
            payload["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        if tools:
            payload["tools"] = [_as_anthropic_tool(entry) for entry in tools]
            # Die Werkzeugschemata sind das teuerste stabile Stück des Prompts
            # (~99 KB je Schritt, bis zu acht Schritte je Zug). Die Markierung
            # auf dem letzten Schema spannt den Zwischenspeicher über die
            # ganze Liste — Schritt zwei bis acht zahlen sie nicht noch einmal.
            payload["tools"][-1]["cache_control"] = {"type": "ephemeral"}

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


# --- Lokal, über Ollama -----------------------------------------------------------


#: Das lokale Vorgabemodell. Gewählt nach dem einzigen Kriterium, das hier
#: zählt: Kommt ein strukturierter Werkzeugaufruf zurück oder Prosa?
#:
#: Gemessen wird das mit **allen** Werkzeugen, die der Agent anbietet — das
#: sind die dreiundachtzig aus dem geladenen Register, rund 96 KB Schema, und
#: nicht die sieben Zusatzwerkzeuge allein. Der Unterschied entscheidet die
#: Wahl und hat sie einmal falsch entschieden: mit sieben Schemata trifft
#: ``llama3.1:8b`` fünf von fünf, mit dem vollen Register zwei. Es kennt die
#: richtige Antwort auch dann — es schreibt sie als Fließtext hin, statt sie
#: aufzurufen, und Ollama kann sie nicht auslesen.
#:
#: Mit dem vollen Register: ``qwen3:14b`` vier von fünf, ``llama3.1:8b`` zwei,
#: ``qwen2.5-coder:14b`` keine. :func:`ollama_tool_check` und
#: ``tools/check_local_model.py`` fahren die Messung nach.
DEFAULT_OLLAMA_MODEL = "qwen3:14b"
OLLAMA_URL = "http://localhost:11434/api/chat"

#: Wie groß das Kontextfenster sein muss, das Ollama für einen Aufruf öffnet.
#:
#: **Ohne diese Angabe schneidet Ollama den Prompt ab**, und zwar stillschweigend:
#: sein Vorgabefenster ist 4096 Token, das Register bringt allein 84
#: Werkzeugschemata mit rund 99 000 Zeichen — gemessen 21 162 Token. Was nicht
#: hineinpasst, fällt weg, und mit ihm der Systemprompt samt der vier
#: Vorrangregeln. Genau das war der Befund „der Agent greift nicht zu den
#: Bausteinen (0/13)": nicht die Regel, nicht das Modell, sondern ein Fenster,
#: in das die Regel nie gelangte.
#:
#: Gemessen mit ``qwen3:14b`` an drei Anfragen, für die ein Baustein die
#: richtige Antwort ist:
#:
#: ====== ============= =========== =========
#: Fenster verarbeitet   je Frage    Baustein
#: ====== ============= =========== =========
#: 4096    2050 (Rest weg)  30,1 s   0 von 3
#: 8192    4098 (Rest weg)  34,1 s   0 von 3
#: 16384   8194 (Rest weg)  36,1 s   0 von 3
#: 32768  21162 (ganz)      21,2 s   3 von 3
#: ====== ============= =========== =========
#:
#: Das volle Fenster ist dabei nicht nur richtiger, sondern **schneller** — ein
#: Modell, das den Auftrag kennt, rät nicht herum. Es kostet Speicher: mit
#: 32768 belegt ``qwen3:14b`` 14 GB und bleibt damit vollständig auf einer
#: 16-GB-Karte. Wer ein größeres Modell fährt, zahlt hier zuerst.
OLLAMA_CONTEXT_TOKENS = 32768


#: Unter welchem Namen der gewählte Modellname gemerkt wird. Neben der Adresse
#: des Dienstes, weil es dieselbe Art Angabe ist: etwas, das von diesem Rechner
#: abhängt und nie in ein Projekt gehört (§38).
OLLAMA_MODEL_SETTING = "ollama_model"


def _configured_ollama_url() -> str:
    """Die eingetragene Ollama-Adresse, sonst die auf dieser Maschine.

    Der Import steht im Aufruf: :mod:`app.core.discover` liest die
    Nutzerkonfiguration, und eine Testumgebung lenkt die noch um.
    """
    from app.core import discover

    return discover.service_url("ollama", OLLAMA_URL)


def configured_ollama_model() -> str:
    """Das eingetragene Modell, sonst die Vorgabe.

    Öffentlich, anders als die Adresse nebenan: der Einstellungsdialog zeigt
    diesen Wert an und schreibt ihn zurück, und beides über dieselbe Stelle,
    damit die Vorgabe genau einmal im Programm steht.
    """
    from app.core import discover

    return discover.remembered(OLLAMA_MODEL_SETTING) or DEFAULT_OLLAMA_MODEL


def remember_ollama_model(model: str) -> None:
    """Ein Modell merken. Leer heißt „wieder die Vorgabe", nicht „keines"."""
    from app.core import discover

    discover.remember(OLLAMA_MODEL_SETTING, model.strip())


@dataclass(slots=True)
class OllamaBackend:
    """Ein lokales Modell. §27: Werkzeugaufrufe brauchen ein hinreichend
    großes Modell — kleine scheitern daran, und der Fehler sagt das.
    """

    model: str = field(default_factory=lambda: configured_ollama_model())
    # Wie bei ComfyUI: die Adresse darf woanders hinzeigen, wenn das Modell auf
    # einem zweiten Rechner läuft (§38).
    url: str = field(default_factory=lambda: _configured_ollama_url())
    transport: Transport = post_json

    @property
    def id(self) -> str:
        return "ollama"

    @property
    def available(self) -> bool:
        """Lauscht ein Server?

        Mit einem Socket gefragt statt mit einer Anfrage: die Antwort wird
        gebraucht, während ein Fenster gebaut wird, und ein HTTP-Aufruf an einen
        geschlossenen Port kostet auf manchen Maschinen Sekunden — lang genug,
        um bei jedem Start spürbar zu sein.
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
        max_output_tokens: int | None = None,
    ) -> Reply:
        # ``max_output_tokens`` wird hier bewusst nicht angewandt: lokal
        # kostet eine Antwort kein Geld, und ``num_predict`` schnitte sie
        # mitten im Satz ab, statt etwas zu sparen.
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            # ``num_ctx`` ist keine Feineinstellung, sondern die Bedingung
            # dafür, dass der Auftrag überhaupt ankommt — siehe
            # :data:`OLLAMA_CONTEXT_TOKENS`.
            "options": {"temperature": temperature, "num_ctx": OLLAMA_CONTEXT_TOKENS},
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


#: Unterhalb dieser Modellgröße (Milliarden Parameter) scheitern
#: Werkzeugaufrufe erfahrungsgemäß reproduzierbar (§27). Die Grenze steht im
#: README und im Warnsatz — wer sie ändert, zieht beide nach.
OLLAMA_MIN_PARAMETERS: Final = 7.0

#: Wie lange die Frage nach den installierten Modellen dauern darf. Sie läuft
#: in einem Arbeiter, nie im Oberflächen-Thread — das Limit begrenzt nur, wie
#: lange der Arbeiter lebt.
TAGS_TIMEOUT_SECONDS = 3.0

Fetch = Callable[[str], dict[str, Any]]
"""``url -> answer``. Austauschbar, damit die Prüfung ohne Netz testbar ist."""


def _get_json(url: str) -> dict[str, Any]:
    """Ein GET, JSON heraus — das Gegenstück zu :func:`post_json` für die
    Modell-Liste von Ollama."""
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=TAGS_TIMEOUT_SECONDS) as answer:
        return dict(json.loads(answer.read().decode("utf-8")))


def parse_parameter_count(text: str) -> float | None:
    """„14.8B" → 14,8 Milliarden, „780M" → 0,78. ``None``, wenn das Format
    fremd ist — dann wird nichts behauptet."""
    cleaned = text.strip().upper()
    if len(cleaned) < 2:
        return None
    scale = {"B": 1.0, "M": 1e-3, "K": 1e-6}.get(cleaned[-1])
    if scale is None:
        return None
    try:
        return float(cleaned[:-1]) * scale
    except ValueError:
        return None


def ollama_size_warning(
    model: str, url: str | None = None, fetch: Fetch = _get_json
) -> TranslatableText | None:
    """Der Satz aus §27, an der Stelle gesagt, an der er hilft.

    Ein Neuling installiert Ollama mit einem kleinen Modell und erlebt das
    dokumentierte Scheitern der Werkzeugaufrufe, ohne zu wissen warum. Diese
    Prüfung fragt die installierten Modelle ab und antwortet dreifach:
    ``None``, wenn nichts zu sagen ist (Server weg — dann meldet sich der Chat
    ohnehin ab — oder Modell groß genug); ein Satz, wenn das eingestellte
    Modell fehlt; ein Satz, wenn es unter der Erfahrungsgrenze liegt.
    """
    address = (url or _configured_ollama_url()).replace("/api/chat", "/api/tags")
    try:
        answer = fetch(address)
    except (OSError, ValueError):
        return None

    wanted = {model, f"{model}:latest"}
    entry = next(
        (
            candidate
            for candidate in answer.get("models", ())
            if str(candidate.get("name", "")) in wanted
        ),
        None,
    )
    if entry is None:
        return _(
            "Das eingestellte Modell ist bei Ollama nicht installiert — der "
            "erste Chat-Zug würde scheitern. „ollama pull“ mit dem Modellnamen "
            "holt es."
        )
    size = parse_parameter_count(str(entry.get("details", {}).get("parameter_size", "")))
    if size is None or size >= OLLAMA_MIN_PARAMETERS:
        return None
    return _(
        "Das lokale Modell hat weniger als 7 Milliarden Parameter — "
        "Werkzeugaufrufe scheitern damit erfahrungsgemäß. Bewährt hat sich "
        "qwen3:14b; das braucht eine Grafikkarte mit 16 GB Speicher."
    )


#: Ein Werkzeug, das es nur für die Probe gibt: klein, eindeutig, und mit einem
#: Pflichtfeld, damit die Antwort nicht bloß ein leeres Objekt sein kann.
PROBE_TOOL: Final = {
    "name": "set_length",
    "description": "Setzt eine Länge in Millimetern.",
    "input_schema": {
        "type": "object",
        "properties": {"value": {"type": "number"}},
        "required": ["value"],
    },
}

PROBE_REQUEST: Final = "Setze die Länge auf 20 Millimeter."


def ollama_tool_check(
    model: str, url: str | None = None, transport: Transport = post_json
) -> bool | None:
    """Ruft dieses Modell wirklich Werkzeuge auf, oder redet es nur darüber?

    Die Größenprüfung nebenan beantwortet das **nicht**, und der Unterschied
    hat hier einmal Zeit gekostet: ``qwen2.5-coder:14b`` liegt mit 14,8
    Milliarden Parametern weit über der Grenze, meldet ``tools`` als Fähigkeit
    — und gibt den Aufruf trotzdem als JSON im Fließtext aus, ohne die
    Markierung, die sein eigenes Vorlagenformat verlangt. Ollama kann ihn
    darum nicht auslesen, und die Agentenschicht sieht Prosa, wo sie eine
    Operation erwartet. Groß genug heißt nicht werkzeugfähig, und angekündigt
    heißt es auch nicht.

    Das kostet einen echten Zug samt Laden des Modells — Sekunden bis Minuten.
    Diese Prüfung gehört deshalb dorthin, wo jemand sie anstößt, nicht in den
    Start.

    ``True`` heißt brauchbar, ``False`` heißt Prosa statt Aufruf, ``None``
    heißt „keine Antwort" — dann wird nichts behauptet, denn ein Server, der
    schweigt, meldet sich ohnehin schon über :attr:`OllamaBackend.available` ab.
    """
    backend = OllamaBackend(model=model, transport=transport)
    if url is not None:
        backend.url = url
    try:
        reply = backend.complete([Message(role="user", content=PROBE_REQUEST)], tools=[PROBE_TOOL])
    except (AppError, OSError, ValueError):
        return None
    return reply.wants_tools


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
