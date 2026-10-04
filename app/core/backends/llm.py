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

import base64
import http.client
import json
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from typing import Any, ClassVar, Final, Literal, Protocol

from app.core.backends import keys
from app.core.backends.resources import keep_warm, local_ai_slot
from app.core.discover import PROBE_SECONDS, UNUSABLE_ADDRESS, is_local_address, opener_for
from app.core.errors import (
    CANCEL,
    OPEN_SETTINGS,
    RETRY,
    AppError,
    ExternalToolError,
    OperationCancelled,
)
from app.core.http import (
    HttpBoundaryError,
    ResponseDeadlineError,
    ResponseTooLargeError,
    apply_header_deadline,
    deadline_after,
    iter_limited,
    read_limited,
    redirect_left_origin,
    validate_http_url,
)
from app.core.json_boundary import loads as load_json
from app.core.log import get_logger, redact_external, redact_url
from app.core.types import CancelToken
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

Role = Literal["system", "user", "assistant", "tool"]

#: Wie lange eine einzelne Anfrage an ein **gehostetes** Modell dauern darf.
#:
#: Dort misst die Zahl die Erreichbarkeit: Wer in zwei Minuten nicht antwortet,
#: antwortet nicht mehr.
TIMEOUT_SECONDS = 120.0

#: Und wie lange bei einem **lokalen** Modell.
#:
#: **Dieselbe Zahl für beide misst zwei verschiedene Dinge.** Bei einem
#: gehosteten Modell die Erreichbarkeit, bei einem lokalen die Rechenleistung
#: des Kunden — und die kennen wir nicht. Der erste Kunde mit 0.1.3 riss nach
#: 122 Sekunden auf einem ``qwen3:8b``, bei einem Limit von 120; Solidon selbst
#: schreibt im Chat, ein Werkzeugaufruf könne zwei Minuten kosten. Das Limit
#: lag also genau auf dem Wert, vor dem die eigene Oberfläche warnt.
#:
#: Zehn Minuten bleiben die technische Grenze des noch synchronen Transports.
#: Die gemessenen 7,8 Token je Sekunde waren kein Grafiklauf, sondern Ollamas
#: Rückfall auf den Prozessor. Für den vollständigen Solidon-Auftrag begann die
#: Antwort dort erst nach rund 42 Minuten; dieser Weg ist damit nicht nur
#: langsam, sondern im aktuellen Transport unbrauchbar. Die Probe sagt deshalb
#: ausdrücklich, auf eine geeignete Grafikkarte oder einen gehosteten Zugang zu
#: wechseln. Eine Stunde blockierbares Warten wäre kein ehrlicher Ersatz für
#: einen wirklich abbrechbaren Transport.
LOCAL_TIMEOUT_SECONDS = 600.0

#: Selbst die größte erlaubte Modellausgabe ist wesentlich kleiner. Der
#: Spielraum trägt Anbieter-Metadaten, ohne einem Fehlerproxy den Arbeitsspeicher
#: zu überlassen.
MAX_RESPONSE_BYTES: Final = 8 * 1024 * 1024
MAX_ERROR_BYTES: Final = 64 * 1024


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
    images: tuple[tuple[str, bytes], ...] = ()
    """Beschriftete PNG-Ansichten (§23): „das Loch vorne links" ist im Text
    mehrdeutig, im Bild nicht. Nur ein Backend mit ``supports_images`` bekommt
    sie — der Textpfad bleibt für jedes Modell vollständig (Leitprinzip 8)."""


#: Ein ``stop_reason``, bei dem die Antwort **unvollständig** ist.
#:
#: Anthropic nennt ``max_tokens``, wenn die Ausgabegrenze zuschlug, Ollama
#: ``length``. Beides heißt: Der Satz bricht mitten ab, und ein angefangener
#: Werkzeugaufruf fehlt ganz. Gespeichert wurde das bis zum 25.08.2026 und nie
#: gelesen — die Sitzung nahm eine abgeschnittene Antwort für eine fertige.
TRUNCATED_STOPS: Final = frozenset({"max_tokens", "length"})

#: Und der Fall, in dem das Modell die Arbeit ablehnt.
#:
#: Er sieht wie eine leere Antwort aus: kein Text, kein Werkzeugaufruf, keine
#: Fehlermeldung. Wer ihn nicht ausweist, lässt den Nutzer auf einen Knopf
#: starren, der nichts getan hat.
REFUSAL_STOPS: Final = frozenset({"refusal", "content_filter"})

#: Was eine **gelesene** Zwischenspeicherzeile im Zugbudget wiegt.
#:
#: Ein Zehntel eines regulären Eingabe-Tokens — so rechnet die Gegenseite sie
#: ab (Preisstand 08/2026, Anthropic: reguläre Eingabe einfach, eine Lesung ein
#: Zehntel, eine Schreibung das 1,25-fache bei fünf Minuten Haltezeit).
#:
#: Warum das Budget überhaupt wiegt, statt zu zählen: Die markierte
#: Werkzeugliste wiegt rund 25 000 Token, und **jeder** Schritt meldet sie
#: erneut als ``cache_read``. Ungewichtet war das Budget aus §26.5 damit nach
#: vier von acht Schritten erschöpft, obwohl die Gegenseite dafür ein Zehntel
#: verlangt hatte.
CACHE_READ_WEIGHT: Final = 0.1

#: Und was das **Schreiben** in den Zwischenspeicher wiegt: das 1,25-fache
#: (derselbe Preisstand). Es passiert einmal je Zug — beim ersten Schritt, der
#: die Markierung anlegt —, und es ist tatsächlich teurer als reguläre
#: Eingabe. Deshalb wird es aufgewertet und nicht einfach mitgezählt.
CACHE_WRITE_WEIGHT: Final = 1.25


@dataclass(frozen=True, slots=True)
class Reply:
    """Was zurückkam: Worte, Aufrufe, und was es gekostet hat."""

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    model: str = ""
    stop_reason: str = ""
    input_tokens: int = 0
    """Alle Eingabe-Token dieses Schrittes — **einschließlich der
    zwischengespeicherten**, und **ungewichtet**.

    Anthropic zählt bei ``cache_control`` getrennt: ``input_tokens`` sind nur
    die *neuen*, ``cache_creation_input_tokens`` und
    ``cache_read_input_tokens`` stehen daneben. Dieser Weg setzt die Markierung
    auf Systemblock und Werkzeugliste (:meth:`AnthropicBackend.complete`), und
    das ist der weitaus größte Teil des Prompts: Gezählt wurde also der
    kleinste. Zugbudget und Kostenanzeige maßen damit an einem Zug von 25 000
    Token ein paar hundert.

    Das ist die **ehrliche** Zahl: so viele Token sind wirklich geflossen, und
    genau sie zeigt die Kostenzeile des Chats. Was der Zug vom Budget nimmt,
    steht daneben in :attr:`budget_input_tokens` — zwei Fragen, zwei
    Auskünfte."""
    cache_read_tokens: int = 0
    """Der Teil von :attr:`input_tokens`, der aus dem Zwischenspeicher der
    Gegenseite kam (``cache_read_input_tokens``)."""
    cache_write_tokens: int = 0
    """Der Teil von :attr:`input_tokens`, der in den Zwischenspeicher
    geschrieben wurde (``cache_creation_input_tokens``)."""
    output_tokens: int = 0

    @property
    def budget_input_tokens(self) -> int:
        """Was dieser Schritt vom Zugbudget nimmt (§26.5) — gewichtet.

        Die Rohsumme taugt als Deckel nicht, und der Grund ist die
        Wiederholung: Die markierte Werkzeugliste geht in jedem Schritt erneut
        als Cache-Lesung durch die Zählung, kostet dort aber ein Zehntel. Bei
        120 000 Token Budget war die Grenze nach vier Schritten erreicht, bei
        acht erlaubten — der Vorschlag blieb halbfertig stehen und meldete
        ``stopped="tokens"``.

        Gewichtet wird nach dem Preis der Gegenseite
        (:data:`CACHE_READ_WEIGHT`, :data:`CACHE_WRITE_WEIGHT`), denn das
        Budget ist ein Kostendeckel und keine Zeichenzählung. Die **Ausgabe**
        bleibt draußen: Sie wird nicht zwischengespeichert, hat also nichts zu
        gewichten, und die Sitzung addiert sie selbst dazu.
        """
        # Was weder gelesen noch geschrieben wurde, ist frisch verrechnete
        # Eingabe und zählt voll. Ein lokales Modell meldet keine der beiden
        # Zahlen — dort ist die gewichtete Summe die Rohsumme.
        fresh = max(0, self.input_tokens - self.cache_read_tokens - self.cache_write_tokens)
        weighted = (
            fresh
            + CACHE_WRITE_WEIGHT * self.cache_write_tokens
            + CACHE_READ_WEIGHT * self.cache_read_tokens
        )
        return round(weighted)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)

    @property
    def truncated(self) -> bool:
        """Ob die Antwort mitten im Satz endete (:data:`TRUNCATED_STOPS`)."""
        return self.stop_reason in TRUNCATED_STOPS

    @property
    def refused(self) -> bool:
        """Ob das Modell die Antwort verweigert hat (:data:`REFUSAL_STOPS`)."""
        return self.stop_reason in REFUSAL_STOPS


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
    def supports_images(self) -> bool:
        """Ob ``Message.images`` dieses Modell erreichen (§23). ``False``
        heißt: die Bilder entfallen, der Text trägt allein — Bilder sind
        Zugabe, nie Voraussetzung (Leitprinzip 8)."""
        ...

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


def post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float = TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Der Vorgabe-Transport: ein POST, JSON hinein, JSON heraus."""
    try:
        address = validate_http_url(url, allow_http=True)
    except ValueError as error:
        raise BackendUnavailable() from error
    # **Über blankes HTTP reist kein Zugangswert** — ein Schlüssel im Kopf
    # wäre auf der Leitung lesbar. Der Inhaltstyp ist keiner: Die eigene
    # Geschwindigkeitsmessung schickt ihn an das lokale Ollama, und die Sperre
    # ließ sie vor dem Öffnen der Verbindung mit „keine Messung" enden — genau
    # der Kunde ohne Grafikkarte bekam damit keine Langsam-Warnung
    # (Gesamtreview 05.09.2026, CORE-05).
    if urllib.parse.urlsplit(address).scheme == "http" and any(
        key.lower() != "content-type" for key in headers
    ):
        raise BackendUnavailable()
    deadline = deadline_after(timeout)
    body = json.dumps(payload).encode("utf-8")
    # Die Adresse kommt aus dem Backend, nie aus etwas, das das Modell gesagt hat.
    request = urllib.request.Request(
        address, data=body, headers={"Content-Type": "application/json", **headers}
    )
    opener = opener_for(address)
    apply_header_deadline(opener, deadline)
    try:
        with opener.open(request, timeout=timeout) as answer:
            if redirect_left_origin(answer, address, allow_http=True):
                raise BackendUnavailable()
            raw = read_limited(answer, limit=MAX_RESPONSE_BYTES, deadline=deadline)
            return _as_object(raw, address)
    except urllib.error.HTTPError as error:
        try:
            raw = read_limited(error, limit=MAX_ERROR_BYTES, deadline=deadline)
            detail = redact_external(raw.decode("utf-8", errors="replace"))
        except ResponseDeadlineError, ResponseTooLargeError, ValueError:
            detail = ""
        finally:
            error.close()
        raise BackendUnavailable(status=error.code, detail=detail) from error
    except urllib.error.URLError as error:
        raise BackendUnavailable(detail=redact_external(error.reason)) from error
    except TimeoutError as error:
        # **Und zwar getrennt von ``URLError``, denn urllib wickelt nur die
        # Hälfte ein.** Beim Verbindungsaufbau wird ein Zeitlimit zu einem
        # ``URLError``; beim **Lesen der Antwort** kommt der nackte
        # ``TimeoutError`` durch — ``http/client.py`` reicht ihn von
        # ``socket.readinto`` unverändert weiter. Genau dort stand er im
        # Protokoll des ersten Kunden mit 0.1.3, und dort wird das Warten auf
        # ein rechnendes Modell auch verbracht.
        #
        # Ohne diese Zeile wurde daraus ein ``InternalError``: „Im Programm ist
        # ein unerwarteter Fehler aufgetreten" plus die Bitte um einen
        # Fehlerbericht — für ein Modell, das schlicht länger rechnet.
        raise BackendTooSlow(seconds=timeout) from error
    except ConnectionError as error:
        # **Der Zwilling der Zeile darüber**, und aus demselben Grund:
        # Beim Verbindungsaufbau wickelt urllib einen Abbruch in
        # ``URLError``, beim Lesen der Antwort nicht. Ollama macht die
        # Verbindung genau dort zu, wenn ihm ein Modell zu groß wird
        # oder der Dienst neu startet.
        #
        # Gemeldet von einem Kunden mit 0.1.5 (S-20260826-1db075): „Try
        # to use Ollama, after many attempts, the program crashed" —
        # und im Bericht „An unexpected error occurred in the
        # application. ConnectionResetError: [WinError 10054]".
        #
        # ``ConnectionError`` und nicht die eine Klasse: Abbruch,
        # verweigerte Annahme und geschlossene Gegenstelle sind für den
        # Kunden dieselbe Lage und verdienen denselben Satz.
        raise BackendUnavailable(detail=redact_external(error)) from error
    except ResponseTooLargeError as error:
        raise BackendUnavailable() from error
    except HttpBoundaryError as error:
        raise BackendUnavailable() from error


def _as_object(raw: bytes, url: str) -> dict[str, Any]:
    """Die Antwort als JSON-Objekt — oder eine Meldung, die weiterführt.

    **Was hier ankommt, muss kein JSON sein.** Gemessen an drei echten Lagen:
    Ein Firmenproxy schiebt eine HTML-Anmeldeseite dazwischen, eine
    OpenAI-kompatible Gegenstelle antwortet mit einer JSON-**Liste**, und wer
    die Adresse eines ganz anderen Dienstes einträgt, bekommt dessen Antwort.
    In allen dreien warf ``json.loads`` beziehungsweise ``dict()`` einen
    ``ValueError``, den niemand fing — daraus wurde ein ``InternalError``: „Im
    Programm ist ein unerwarteter Fehler aufgetreten", mit der Bitte um einen
    Fehlerbericht. Der Fehler lag aber nicht im Programm, sondern in der
    Adresse, und der Nutzer konnte ihn beheben.

    Der Anfang der Antwort reist mit. Er ist die eigentliche Auskunft: „<!DOCTYPE
    html" beantwortet die Frage „was steht da denn?" in einem Blick.
    """
    text = raw.decode("utf-8", errors="replace")
    try:
        loaded = load_json(text, max_bytes=MAX_RESPONSE_BYTES)
    except ValueError as error:
        raise BackendAnswerUnreadable(url=url, excerpt=text) from error
    if not isinstance(loaded, dict):
        raise BackendAnswerUnreadable(url=url, excerpt=text)
    return dict(loaded)


def post_json_local(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    """Derselbe Transport, mit der Frist eines lokalen Modells.

    Als eigene Funktion und nicht als Vorgabewert am Backend: Der
    ``Transport``-Vertrag hat drei Argumente, und daran hängen die Attrappen
    der Tests. Was sich unterscheidet, ist die Frist — also unterscheidet sich
    der Transport, nicht seine Signatur.
    """
    return post_json(url, headers, payload, timeout=LOCAL_TIMEOUT_SECONDS)


def post_json_local_cancelable(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    cancelled: CancelToken,
) -> dict[str, Any]:
    """Lokales JSON-POST, dessen Verbindung ein Nutzerabbruch wirklich schließt."""
    cancelled.raise_if_cancelled()
    parts = urllib.parse.urlsplit(url)
    if not is_local_address(url) or parts.scheme not in {"http", "https"}:
        answer = post_json_local(url, headers, payload)
        cancelled.raise_if_cancelled()
        return answer
    if not parts.hostname:
        raise BackendUnavailable(detail=_("Die Adresse enthält keinen Rechnernamen."))

    connection_type = (
        http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    )
    connection = connection_type(
        parts.hostname,
        parts.port,
        timeout=LOCAL_TIMEOUT_SECONDS,
    )
    finished = threading.Event()
    body = json.dumps(payload).encode("utf-8")
    target = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
    answers: list[dict[str, Any]] = []
    errors: list[BaseException] = []
    active_socket: socket.socket | None = None
    # Dieselbe Grenze wie im nicht abbrechbaren Weg: Ein Ollama, das antwortet,
    # ist noch kein Ollama — hinter der Adresse kann ein beliebiger Dienst
    # liegen, und ein endloser Strom füllte sonst den Arbeitsspeicher.
    deadline = deadline_after(LOCAL_TIMEOUT_SECONDS)

    def request() -> None:
        nonlocal active_socket
        try:
            connection.connect()
            # HTTP/1.0 und Connection: close übertragen den Socket beim Lesen
            # der Header an die Antwort. connection.sock ist danach None;
            # der Abbruch muss denselben Netzsocket weiterhin erreichen.
            active_socket = connection.sock
            cancelled.raise_if_cancelled()
            connection.request(
                "POST",
                target,
                body=body,
                headers={"Content-Type": "application/json", **headers},
            )
            with connection.getresponse() as response:
                raw = read_limited(response, limit=MAX_RESPONSE_BYTES, deadline=deadline)
                if response.status >= 400:
                    raise BackendUnavailable(
                        status=response.status,
                        # Fremder Text, also redigiert und gedeckelt — er steht
                        # gleich in einer Meldung und im Protokoll (§33.2).
                        detail=redact_external(raw.decode("utf-8", errors="replace"), limit=500),
                    )
                answers.append(_as_object(raw, url))
        except TimeoutError as error:
            errors.append(BackendTooSlow(seconds=LOCAL_TIMEOUT_SECONDS))
            errors[-1].__cause__ = error
        except (OSError, http.client.HTTPException) as error:
            errors.append(BackendUnavailable(detail=str(error)))
            errors[-1].__cause__ = error
        except HttpBoundaryError as error:
            # Zu große oder nicht begrenzbare Antwort: dieselbe Lage wie in
            # :func:`post_json`, und dieselbe Antwort — ein Fehler mit
            # Handlungsvorschlägen statt einer nackten Grenzverletzung.
            errors.append(BackendUnavailable())
            errors[-1].__cause__ = error
        except BaseException as error:
            errors.append(error)
        finally:
            connection.close()
            finished.set()

    worker = threading.Thread(target=request, name="ollama-request", daemon=True)
    worker.start()
    while not finished.wait(0.05):
        if not cancelled.is_cancelled:
            continue
        sock = active_socket or connection.sock
        if sock is not None:
            with suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)
            # makefile() hält den Descriptor trotz socket.close() offen.
            # Windows weckt den wartenden Leser erst beim tatsächlichen
            # Schließen. detach() verhindert dabei ein späteres doppeltes
            # Schließen durch Antwort oder Verbindung.
            with suppress(OSError):
                descriptor = sock.detach()
                if descriptor >= 0:
                    socket.close(descriptor)
            # Der Request-Thread schließt Antwort und Verbindung selbst.
            # Vorzeitiges close() könnte während request() den Socket leeren
            # und damit eine automatische zweite Verbindung auslösen.
            worker.join()
        raise OperationCancelled

    cancelled.raise_if_cancelled()
    if errors:
        raise errors[0]
    return answers[0]


class BackendUnavailable(ExternalToolError):
    """Das Modell war nicht erreichbar oder hat abgelehnt.

    Ein ``ExternalToolError``, kein nackter ``AppError`` (§33.1): Der
    häufigste Auslöser ist ein nicht laufendes Ollama oder ein abgelaufener
    Schlüssel — dort helfen „Einstellungen öffnen" und „Erneut versuchen",
    nicht das geerbte „Abbrechen" allein.
    """

    default_title = _("Das Sprachmodell hat nicht geantwortet.")

    def __init__(
        self,
        status: int | None = None,
        detail: TranslatableText | str = "",
        provider: str = "",
    ) -> None:
        # **Der Anbieter gehört in die Meldung, und zwar aus einem gemessenen
        # Grund.** Ein Kunde richtete am 24.08.2026 sein lokales Ollama ein und
        # las über einem Anthropic-Schlüsselfehler „Das Sprachmodell hat nicht
        # geantwortet". Geantwortet *hatte* eines — nur ein anderes als das
        # gerade eingerichtete. Der Satz stimmte und führte drei Stunden in die
        # Irre; was fehlte, war der Name dessen, der gefragt wurde.
        #
        # Er steht in ``values`` und nicht im Satz: Einen Fehlertext aus dem
        # Kern formatiert niemand nach, ein ``{platzhalter}`` erschiene dem
        # Kunden mit Klammern (``tests/test_errors.py`` sucht danach).
        self.status = status
        self.provider = provider
        values: dict[str, Any] = {}
        if status is not None:
            values["status"] = str(status)
        if provider:
            values["provider"] = provider
        super().__init__(detail=detail or None, values=values)


class BackendAnswerUnreadable(ExternalToolError):
    """Es kam etwas zurück, aber nichts, was ein Sprachmodell geschickt hätte.

    **Getrennt von :class:`BackendUnavailable`, weil etwas geantwortet hat.**
    „Nicht erreichbar" schickt den Nutzer zum Starten; hier läuft etwas und
    spricht eine andere Sprache — ein Proxy, ein falscher Port, eine Adresse,
    hinter der ein anderer Dienst sitzt, oder ein Modell, das dieses Protokoll
    nicht bedient.

    Ein ``ExternalToolError`` und ausdrücklich **kein** Programmfehler: Wer für
    eine falsch eingetragene Adresse einen Fehlerbericht schicken soll, sucht
    den Fehler bei sich und findet keinen (Regel 17, §33.1).
    """

    default_title = _("Die Antwort des Sprachmodells war nicht zu lesen.")

    #: Wie viel von der Antwort mitgeht. Genug für „<!DOCTYPE html" und eine
    #: Fehlerzeile, zu wenig, um ein Protokoll zu fluten.
    EXCERPT_CHARS: ClassVar[int] = 200

    def __init__(self, url: str = "", excerpt: str = "", provider: str = "") -> None:
        # Adresse und Auszug stehen in ``values`` und nicht im Satz: Einen
        # Fehlertext aus dem Kern formatiert niemand nach, ein
        # ``{platzhalter}`` erschiene dem Kunden mit Klammern
        # (``tests/test_errors.py`` sucht danach).
        self.provider = provider
        values: dict[str, Any] = {}
        if url:
            values["url"] = redact_url(url)
        if excerpt:
            values["answer"] = redact_external(excerpt, limit=self.EXCERPT_CHARS)
        if provider:
            values["provider"] = provider
        super().__init__(
            detail=_(
                "Unter dieser Adresse hat etwas geantwortet, aber nicht in der "
                "Sprache, die ein Sprachmodell spricht — meist steckt ein Proxy "
                "oder ein anderer Dienst dahinter. Der Anfang der Antwort steht "
                "daneben. Prüfen Sie die Adresse in den Einstellungen, oder "
                "wählen Sie ein anderes Modell."
            ),
            values=values,
            suggestions=(OPEN_SETTINGS, RETRY, CANCEL),
        )


class BackendPromptTruncated(ExternalToolError):
    """Der Auftrag passte nicht in das Fenster des lokalen Modells — und Ollama
    hat ihn still gekürzt.

    **Gemessen am 14.09.2026:** Ein Prompt von 4 098 Token gegen ein Fenster
    von 2 048 kam mit ``prompt_eval_count`` 1 026 zurück — keine Meldung,
    kein ``done_reason``, nur die halbe Zahl. Ollama behält den Anfang bis
    ``n_keep`` und die zweite Hälfte des Rests; was in der Mitte steht, ist
    weg. Bei Solidon steht dort der Auftrag mit seinen Werkzeugen, und eine
    Antwort auf einen halben Auftrag sieht aus wie eine ganze — die
    Bausteinquote fiel am 03.09. aus genau diesem Grund von 3/3 auf 0/3, und
    niemand sah warum.

    Erkannt wird es an der Zahl, die Ollama meldet, gegen die Länge des
    gesendeten Texts (:func:`prompt_was_cut`): Weniger Token, als dieser Text
    mindestens hat, kann kein Modell gezählt haben. Bis zum 25.09.2026 stand
    hier die Werkzeugzahl als Maß — seit ein lokaler Zug nicht mehr jedes
    Werkzeug ausführlich schickt (``agent/offer.py``), sagt sie über die Länge
    nichts mehr. Ein ``ExternalToolError`` und kein Programmfehler: Die Abhilfe
    ist ein Modell mit größerem Fenster oder ein gehostetes — kein
    Fehlerbericht.
    """

    default_title = _("Der Auftrag war zu lang für das Sprachmodell.")

    def __init__(
        self, counted: int = 0, expected: int = 0, window: int = 0, provider: str = ""
    ) -> None:
        # Die Zahlen stehen in ``values`` und nicht im Satz — einen
        # Fehlertext aus dem Kern formatiert niemand nach. Ohne Zahlen (die
        # nackte Ausnahme aus ``test_errors``) bleiben sie weg.
        self.provider = provider
        values: dict[str, Any] = {}
        if counted:
            values["counted"] = counted
        if expected:
            values["expected"] = expected
        if window:
            values["window"] = window
        if provider:
            values["provider"] = provider
        super().__init__(
            detail=_(
                "Das lokale Modell hat den Auftrag nicht ganz bekommen: Was über "
                "die Länge hinausgeht, die es fasst, schneidet Ollama still ab, und "
                "die Antwort beruht dann auf einem halben Auftrag. Ein kürzerer "
                "Chatverlauf hilft, sonst ein Modell, das längere Aufträge fasst, "
                "oder ein gehostetes."
            ),
            values=values,
            suggestions=(OPEN_SETTINGS, CANCEL),
        )


class BackendContextShifted(ExternalToolError):
    """Auftrag und Antwort zusammen waren länger als das Fenster — und Ollama
    hat während der Antwort die Mitte des Auftrags verworfen.

    Die zweite Gestalt derselben Kürzung, gefunden am 14.09.2026 im Protokoll
    des laufenden Suitelaufs: Der erste Schritt eines Zugs endete bei 32 680
    von 32 768 Token, der zweite begann mit 32 300 und erzeugte 847 —
    ``stop processing: n_tokens = 16765, truncated = 1``. llama.cpp schiebt
    dann den Kontext: Es behält ``n_keep`` Token vorn, verwirft die Hälfte des
    Rests und rechnet weiter, und die Antwort steht auf einem Auftrag, den es
    so nicht mehr gab. Die Antwort trägt kein Zeichen davon — ``done_reason``
    sagt ``stop``, ``prompt_eval_count`` zählt den ganzen Prompt.

    Erkannt wird es an der Summe: Was Ollama an Eingabe und Ausgabe zählt,
    passt zusammen in das Fenster, oder es ist geschoben worden. Dieselbe
    Abhilfe wie bei :class:`BackendPromptTruncated`: mehr Fenster, oder ein
    gehostetes Modell — kein Fehlerbericht.
    """

    default_title = _("Auftrag und Antwort wurden zu lang für das Sprachmodell.")

    def __init__(self, counted: int = 0, window: int = 0, provider: str = "") -> None:
        self.provider = provider
        values: dict[str, Any] = {}
        if counted:
            values["counted"] = counted
        if window:
            values["window"] = window
        if provider:
            values["provider"] = provider
        super().__init__(
            detail=_(
                "Auftrag und Antwort zusammen waren länger, als das lokale Modell "
                "fasst. Ollama verwirft dann während der Antwort die Mitte des "
                "Auftrags und rechnet mit dem Rest weiter — die Antwort beruht auf "
                "einem Auftrag, den es so nicht mehr gab. Wählen Sie in den "
                "Einstellungen ein Modell, das längere Aufträge fasst, oder ein "
                "gehostetes."
            ),
            values=values,
            suggestions=(OPEN_SETTINGS, CANCEL),
        )


class BackendTooSlow(ExternalToolError):
    """Das Modell hat gerechnet und war nicht rechtzeitig fertig.

    **Getrennt von :class:`BackendUnavailable`, weil der Nutzer etwas anderes
    tun muss.** „Nicht erreichbar" heißt: Ollama starten, Schlüssel prüfen.
    „Zu langsam" heißt: kleineres Modell, kürzere Anweisung, oder ein
    gehostetes nehmen — die Sache läuft, sie dauert nur.

    Ein ``ExternalToolError`` und ausdrücklich **kein** Programmfehler: Wer für
    eine lange Rechnung einen Fehlerbericht schicken soll, sucht den Fehler bei
    sich und findet keinen.
    """

    default_title = _("Das Sprachmodell hat zu lange gebraucht.")

    def __init__(self, seconds: float = 0.0) -> None:
        # **Der Vorgabewert ist kein Zierat.** ``tests/test_errors.py`` erzeugt
        # jede Ausnahmeklasse ohne Argumente, und das ist keine Förmlichkeit:
        # Eine Ausnahme, die das nicht kann, überlebt die Serialisierung nicht
        # — und die braucht der Fehlerbericht, um sie überhaupt zu übertragen.
        # **Die Zahl steht in ``values``, nicht im Satz.** Einen Fehlertext aus
        # dem Kern formatiert niemand nach — der Dialog zeigt ``detail``, wie es
        # ist, und hängt die ``values`` als eigene Zeilen darunter. Ein
        # ``{platzhalter}`` erschiene dem Kunden mit geschweiften Klammern.
        # In der Oberfläche wäre derselbe Platzhalter richtig; das ist die
        # Falle, und ``tests/test_errors.py`` sucht im ganzen Kern danach.
        super().__init__(
            detail=_(
                "Das Modell hat gerechnet, war aber innerhalb der Wartezeit nicht "
                "fertig. Lokale Modelle brauchen je nach Rechner Minuten für einen "
                "Schritt — ein kleineres Modell, eine kürzere Anweisung oder ein "
                "gehostetes Modell mit eigenem Schlüssel sind schneller."
            ),
            values={"waited_minutes": f"{seconds / 60:.0f}"},
        )


# --- Gehostet, mit dem eigenen Schlüssel des Nutzers -------------------------------


DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
"""Das Modell, gegen das gefahren wird, wenn der Nutzer keines einträgt.

Bis zum 19.08.2026 stand hier ``claude-sonnet-4-5`` — ein Alias auf den
Schnappschuss vom 29.09.2025, mit vorläufigem Rückzugsdatum („not sooner than
September 29, 2026"). Der Nachfolger kostet weniger (2 statt 3 USD Eingabe je
Mio. Token) und trägt das fünffache Kontextfenster: eine Million Token statt
zweihunderttausend. Bei einem Prompt, dessen Werkzeugschemata allein 110 KB
wiegen, ist das der Unterschied, der zählt.

**Gegen dieses Modell ist die Agenten-Suite nicht gefahren** — entschieden von
Robert am 19.08.2026, in Kenntnis dessen. §35 verlangt die Messung vorher und
nachher; sie steht als offener Punkt in der ROADMAP und kostet zwei Läufe über
den Schlüssel des Nutzers. Was hier steht, ist deshalb die begründete Vorgabe
und nicht die gemessene.

Zwei Eigenheiten der Thinking-Modelle, die niemandem auffallen, bevor er sie
sucht: Die ``thinking``-Blöcke der Antwort reisen bei einem mehrschrittigen Zug
**nicht** zurück — :func:`_from_anthropic` liest nur ``text`` und ``tool_use``,
und der nächste Schritt baut seine Nachrichten neu auf. Das kostet Kontext,
aber es bricht nichts. Und ``stop_reason`` kann ``"refusal"`` heißen — der Wert
wird seit dem 25.08.2026 auch behandelt: :data:`REFUSAL_STOPS` erkennt ihn,
:attr:`Reply.refused` sagt es, und die Sitzung hält damit an und legt einen
Befund dazu (``agent/session.py``). Bis dahin wurde er durchgereicht und
nirgends gelesen, und eine Ablehnung sah aus wie ein Zug ohne Fund.
"""

#: Modelle, die ``temperature`` noch annehmen.
#:
#: Eine **Positivliste**, und das ist der Punkt: Ab Claude Opus 4.7 ist der
#: Parameter entfernt, und ein Nicht-Standardwert liefert einen 400er — der
#: Aufruf scheitert also vollständig, nicht bloß anders. Wer hier eine
#: Negativliste führte, müsste sie zu jedem neuen Modell nachziehen und bekäme
#: bis dahin einen harten Fehler. So fällt ein unbekanntes Modell in „nicht
#: senden", und das ist immer zulässig: Ohne Angabe nimmt die Gegenseite ihren
#: eigenen Vorgabewert.
ANTHROPIC_MODELS_TAKING_TEMPERATURE: Final = (
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "claude-opus-4-5",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def takes_temperature(model: str) -> bool:
    """Nimmt dieses Modell den ``temperature``-Parameter noch an?

    Verglichen wird über den Namensanfang, weil dieselbe Version sowohl unter
    dem Alias (``claude-sonnet-4-5``) als auch unter ihrem Schnappschuss
    (``claude-sonnet-4-5-20250929``) angesprochen werden kann.
    """
    return model.startswith(ANTHROPIC_MODELS_TAKING_TEMPERATURE)


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
        """Ein Schlüssel liegt vor — und die Gegenseite hat ihn nicht schon
        abgelehnt (:data:`_rejected`)."""
        return self.id not in _rejected and keys.read(self.id) is not None

    @property
    def supports_images(self) -> bool:
        return True

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
            raise BackendUnavailable(detail="no key stored", provider=self.id)
        # **Auch ein schon gespeicherter Schlüssel wird geprüft.** Seit dem
        # 24.08.2026 lehnt :func:`keys.store` ab, was keiner sein kann — im
        # Schlüsselbund derer, die vorher gespeichert haben, liegt es trotzdem.
        # Ungeprüft flöge es als ``ValueError`` aus ``http.client.putheader``,
        # also als Programmfehler mit der Bitte um einen Fehlerbericht.
        problem = keys.unusable(key)
        if problem is not None:
            reject(self.id)
            raise BackendUnavailable(detail=str(problem), provider=self.id)

        limit = self.max_tokens
        if max_output_tokens is not None:
            limit = max(1, min(limit, max_output_tokens))

        system = " ".join(entry.content for entry in messages if entry.role == "system")
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": limit,
            "messages": [_as_anthropic(entry) for entry in messages if entry.role != "system"],
        }
        if takes_temperature(self.model):
            payload["temperature"] = temperature
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

        try:
            answer = self.transport(
                ANTHROPIC_URL,
                {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION},
                payload,
            )
        except BackendUnavailable as error:
            error.provider = error.provider or self.id
            error.values.setdefault("provider", self.id)
            if error.status in AUTH_REFUSED:
                # Ab hier gilt dieser Zugang als nicht verfügbar, und der Chat
                # nimmt den nächsten — statt bei jedem Zug denselben abgelehnten
                # Schlüssel erneut zu schicken.
                reject(self.id)
            raise
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
    for label, image in message.images:
        # §23: die Ansichten reisen neben dem Steckbrief, jede mit ihrer
        # Beschriftung — ein Bild ohne Namen lässt sich nicht ansprechen.
        if label:
            blocks.append({"type": "text", "text": label})
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(image).decode("ascii"),
                },
            }
        )
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
    """Die Antwort in eine :class:`Reply` — auch wenn sie nicht so aussieht,
    wie sie soll.

    **``content`` muss keine Liste von Blöcken sein.** Kommt dort eine
    Zeichenkette an — eine OpenAI-kompatible Gegenstelle unter der
    Anthropic-Adresse tut genau das —, lief die Schleife über ihre *Zeichen*,
    und ``block.get`` warf einen ``AttributeError``: ein Programmfehler samt
    Bitte um Fehlerbericht für eine falsch eingetragene Adresse. Dasselbe für
    ``usage``, dessen Zahlen keine sein müssen.
    """
    blocks = answer.get("content", ())
    if isinstance(blocks, str) or not isinstance(blocks, list | tuple):
        raise BackendAnswerUnreadable(excerpt=str(answer)[:400], provider="anthropic")
    text: list[str] = []
    calls: list[ToolCall] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text.append(str(block.get("text", "")))
        elif block.get("type") == "tool_use":
            calls.append(
                ToolCall(
                    id=str(block.get("id", "")),
                    name=str(block.get("name", "")),
                    arguments=_arguments(block.get("input")),
                )
            )
    found = answer.get("usage")
    usage: dict[str, Any] = dict(found) if isinstance(found, dict) else {}
    return Reply(
        text="".join(text),
        tool_calls=tuple(calls),
        model=str(answer.get("model", "")),
        stop_reason=str(answer.get("stop_reason") or ""),
        input_tokens=_input_tokens(usage),
        cache_read_tokens=_count(usage, CACHE_READ_FIELD),
        cache_write_tokens=_count(usage, CACHE_WRITE_FIELD),
        output_tokens=_count(usage, "output_tokens"),
    )


def _count(usage: dict[str, Any], key: str) -> int:
    """Eine Token-Zahl aus der Nutzungsangabe. Was keine Zahl ist, zählt null.

    ``int("viele")`` warf einen ``ValueError`` und machte aus einer schrägen
    Angabe einen Programmfehler. Eine fehlende Zählung ist kein Grund, einen
    fertigen Zug wegzuwerfen — sie ist ein Grund, null zu zählen.

    **Und eine Zahl kann zu groß sein, statt keine zu sein.** JSON kennt kein
    Unendlich, sein Zahlenformat schreibt es trotzdem hin: Aus einem Feld mit
    ``1e400`` macht ``json.loads`` ein ``inf``, und daraus wird kein ``int`` —
    das ist ein ``OverflowError`` und kein ``ValueError``, also ein zweiter
    Weg zum selben Programmfehler. Beide zählen null.
    """
    value = usage.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return 0
    try:
        return int(float(value))
    except ValueError, OverflowError:
        return 0


#: Wie Anthropic die zwischengespeicherten Eingabe-Token benennt.
CACHE_WRITE_FIELD: Final = "cache_creation_input_tokens"
CACHE_READ_FIELD: Final = "cache_read_input_tokens"

#: Wie Anthropic die Eingabe zählt, wenn ein Zwischenspeicher im Spiel ist.
#:
#: Drei Felder, und ``input_tokens`` ist bei gesetztem ``cache_control`` das
#: kleinste davon: Es zählt nur, was **neu** verrechnet wurde. Wer nur dieses
#: liest, deckelt ein Budget von 120 000 an einem Zug, der in Wahrheit 25 000
#: verbraucht hat — und zeigt dieselbe falsche Zahl als Kosten an.
CACHE_TOKEN_FIELDS: Final = (
    "input_tokens",
    CACHE_WRITE_FIELD,
    CACHE_READ_FIELD,
)


def _input_tokens(usage: dict[str, Any]) -> int:
    """Alle Eingabe-Token, auch die aus dem Zwischenspeicher
    (:data:`CACHE_TOKEN_FIELDS`) — **ungewichtet**.

    Das ist die Zahl für die Kostenzeile: so viel ist geflossen. Was davon das
    Zugbudget belastet, rechnet :attr:`Reply.budget_input_tokens`.
    """
    return sum(_count(usage, field_name) for field_name in CACHE_TOKEN_FIELDS)


class UnreadableArguments(dict[str, Any]):
    """Die Argumente eines Werkzeugaufrufs, die sich nicht lesen ließen.

    Ein ``dict``, damit nichts bricht, was Argumente einfach benutzt — und ein
    eigener Typ, damit die Sitzung den Aufruf ablehnen kann, statt ihn mit
    lauter Vorgabewerten auszuführen (:data:`UNREADABLE_ARGUMENTS`).
    """


#: Was ``_arguments`` zurückgibt, wenn nichts zu lesen war.
#:
#: **Ein leeres Objekt war hier die falsche Antwort**, und die Begründung
#: daneben trug nicht: Die Schemaprüfung der Sitzung mache daraus eine Meldung,
#: die das Modell korrigieren kann (§26.5). Das gilt nur, solange die Operation
#: etwas verlangt. Bei ``consumes=0`` — ``create_box`` und seine Geschwister —
#: füllt ``validate`` jeden nicht verlangten Parameter mit seiner Vorgabe, der
#: Aufruf ist damit vollständig gültig, und heraus kommt ein Vorgabekörper samt
#: der Antwort „Ausgeführt". Ein Modell, dessen Maße unterwegs verlorengingen,
#: erfährt davon nichts und hat keinen Grund, den Aufruf zu wiederholen — genau
#: das stillschweigende Raten, das Regel 21 verbietet.
UNREADABLE_ARGUMENTS: Final[UnreadableArguments] = UnreadableArguments()


def _arguments(value: Any) -> dict[str, Any]:
    """Die Argumente eines Werkzeugaufrufs — als Objekt, auch wenn Text kam.

    **Der Fall ist bei OpenAI-kompatiblen Servern der Normalfall**, nicht die
    Ausnahme: Dort ist ``arguments`` eine Zeichenkette mit JSON darin, und
    manche Ollama-Gegenstellen reichen das unverändert durch. ``dict("{…}")``
    warf einen ``ValueError`` — der ganze Zug endete als Programmfehler, obwohl
    der Aufruf lesbar dastand. Also wird gelesen statt abgelehnt.

    Was sich auch dann nicht lesen lässt, kommt als
    :data:`UNREADABLE_ARGUMENTS` zurück — nicht als Ausnahme, die den Zug
    beendet, und nicht als leeres Objekt, das wie eine gültige Angabe aussieht.
    Die Sitzung lehnt den Aufruf damit ab und sagt dem Modell, was zu tun ist.

    Ein wirklich leeres ``{}`` bleibt unmarkiert: ``read_report`` und
    ``read_digest`` werden ohne Argumente gerufen, und die dürfen nicht in
    dieselbe Ablehnung laufen.
    """
    if isinstance(value, str):
        try:
            value = load_json(value, max_bytes=MAX_RESPONSE_BYTES)
        except ValueError:
            _log.warning("tool arguments were neither object nor JSON text")
            return UNREADABLE_ARGUMENTS
    if isinstance(value, dict):
        return dict(value)
    if value is None:
        # Kein Feld ``arguments`` heißt „ohne Argumente" und nicht „unlesbar" —
        # so ruft ein Modell jedes Werkzeug, das keine braucht.
        return {}
    _log.warning("tool arguments arrived as %s", type(value).__name__)
    return UNREADABLE_ARGUMENTS


# --- Lokal, über Ollama -----------------------------------------------------------


#: Das lokale Vorgabemodell. Gewählt nach dem einzigen Kriterium, das hier
#: zählt: Kommt ein strukturierter Werkzeugaufruf zurück oder Prosa?
#:
#: Gemessen wird das mit **allen** Werkzeugen, die der Agent anbietet — in der
#: aktuellen Messung 106 aus dem geladenen Register, rund 156 KB Schema,
#: und nicht die elf Zusatzwerkzeuge allein. Der Unterschied entscheidet die
#: Wahl und hat sie einmal falsch entschieden: mit den damals sieben
#: Zusatzschemata traf ``llama3.1:8b`` fünf von fünf, mit dem vollen Register
#: (dreiundachtzig zu der Zeit) zwei. Es kennt die
#: richtige Antwort auch dann — es schreibt sie als Fließtext hin, statt sie
#: aufzurufen, und Ollama kann sie nicht auslesen.
#:
#: Mit dem vollen Register: ``qwen3:14b`` fünf von fünf, ``llama3.1:8b`` zwei,
#: ``qwen2.5-coder:14b`` keine. :func:`ollama_tool_check` und
#: ``tools/check_local_model.py`` fahren die Messung nach.
DEFAULT_OLLAMA_MODEL = "qwen3:14b"
OLLAMA_URL = "http://localhost:11434/api/chat"

#: Wie lange Ollama das Modell nach einer Anfrage hält — zwischen zwei
#: Schritten desselben Vorschlags und nach dem Zug.
#:
#: Ein Werkzeugaufruf und die abschließende Antwort gehören zu einem Zug und
#: sollen nicht zweimal kalt starten; und die nächste Frage kommt meist binnen
#: einer Minute. **Bis zum 25.09.2026 entlud Solidon nach jedem Zug**, und
#: jeder Zug zahlte den Modellstart neu: 3 bis 4,5 s auf einer ruhigen Karte,
#: 56 bis 314 s, sobald der Treiber am Rand des Grafikspeichers umlagerte
#: (RM-081). Seither bleibt es drei Minuten geladen, und
#: :func:`~app.core.backends.resources.keep_warm` sorgt dafür, dass ein
#: anderer Lauf — ComfyUI, ein anderes Modell — die Karte trotzdem frei
#: bekommt (Entscheidung nach Roberts Vorgabe vom 25.09.2026). Danach entlädt
#: Ollama von selbst.
OLLAMA_KEEP_ALIVE = "3m"

#: Wie lange warmgehalten wird, wenn das Modell auf dem Prozessor rechnet.
#:
#: **Dort kostet Warmhalten mehr, als es bringt.** Gemessen am 31.08.2026 auf
#: derselben Maschine, einmal vor und einmal nach einem Neustart, der Ollamas
#: GPU-Erkennung reparierte: auf der Karte 19 641 Token in **9,7 Sekunden**,
#: auf dem Prozessor dieselben 19 641 in **701**. Zwischen Werkzeugaufruf und
#: Abschluss liegen trotzdem nur Sekunden; dafür reicht der kürzere Rückfall.
#:
#: Dreißig Sekunden reichen zwischen zwei unmittelbar aufeinanderfolgenden
#: Schritten. Nach dem Zug wird auf dem Prozessor ausdrücklich entladen: Dort
#: belegt das Modell den Arbeitsspeicher, den die Anwendung selbst braucht.
OLLAMA_KEEP_ALIVE_ON_CPU = "30s"

#: Wie viele Token eine einzelne lokale Antwort höchstens erzeugt — Denkblock
#: eingeschlossen.
#:
#: **Gegen eine Schleife, nicht gegen eine lange Antwort.** Am 25.09.2026 lief
#: gemma4:12b bei der Werkzeugprobe in eine Antwort, die nicht endete: 14 400
#: Token mit 57 je Sekunde, bis die Wartezeit von zehn Minuten riss — so lange
#: war die Karte für alles andere belegt. Ein Zug von qwen3:14b erzeugte je
#: Schritt 480 bis 850 Token, Denkblock eingeschlossen. Achttausend lassen
#: davon ein Zehnfaches und enden auf einer 16-GB-Karte nach rund drei Minuten;
#: was darüber hinausläuft, kommt als abgeschnittene Antwort zurück
#: (``done_reason`` ``length``), und der Vorschlag sagt es mit Befund.
OLLAMA_ANSWER_TOKENS: Final = 8192

#: Entladen ist eine Verwaltungsanfrage, keine Modellrechnung. Bleibt sie
#: länger offen, darf der fertige Vorschlag trotzdem zur Oberfläche zurück.
OLLAMA_RELEASE_SECONDS = 10.0

#: Wie groß das Kontextfenster sein muss, das Ollama für einen Aufruf öffnet.
#:
#: **Ohne diese Angabe schneidet Ollama den Prompt ab**, und zwar stillschweigend:
#: sein Vorgabefenster ist 4096 Token, das Register bringt allein 85
#: Werkzeugschemata mit rund 109 000 Zeichen — gemessen 24 474 Token. Was nicht
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
#: Modell, das den Auftrag kennt, rät nicht herum. Es kostet mehr Speicher als
#: ein kleineres Fenster; im aktuellen RTX-4080-Lauf blieb ``qwen3:14b``
#: vollständig auf der Grafikkarte. Wer ein größeres Modell fährt, zahlt hier
#: zuerst.
#:
#: Die Reihe fuhr 84 Schemata. Am 08.09.2026 sind es mit 119 Werkzeugen
#: **28 281 Token** für den kompakten Satz, den dieser Weg fährt
#: (:func:`~app.core.agent.tools.tool_schemas` mit ``compact``) — **86,3 %** des
#: Fensters. Am 03.09. waren es 22 856 bei 111, am 31.08. 19 641 bei 106, und
#: davor am selben Tag 24 161; die Differenz zwischen den letzten beiden sind
#: die zwei Schritte, die wortgleiche Wiederholung aus dem Schema in den
#: Systemprompt geholt haben (``objects`` und die sechs Platzierungsangaben
#: eines Bausteins). Der Test gegen :data:`PROMPT_TOOL_COUNT` macht jede
#: weitere Operation zum Anlass für eine neue Messung — am 08.09. hat er dabei
#: eine Fortschreibung widerlegt, die um mehr als das Vierfache zu optimistisch
#: war (siehe dort).
#:
#: **Die Zeit daneben misst etwas anderes als die Zahl.** Beide Läufe brauchten
#: über zehn Minuten, weil ``api/ps`` während der Messung ``0.0 GB im VRAM``
#: meldete — das Modell rechnete vollständig auf der CPU. ``prompt_eval_count``
#: zählt trotzdem die Nutzlast: Die Dauer gehört der Maschine, die Token
#: gehören dem Schema.
#:
#: **Seit dem 16.09.2026 sind es 40 960** (Entscheidung Robert). Mit 143
#: Werkzeugen kostet der kompakte Satz 36 731 Token und passte in 32 768 nicht
#: mehr — Ollama kürzte still auf die Hälfte (:data:`PROMPT_TOKENS`). Der
#: Preis ist gemessen, auf einer RTX 4080 mit 16 GB: qwen3:14b liegt bei
#: 40 960 zu 89 % im VRAM (14,7 von 16,4 GB), elf Prozent rechnen auf dem
#: Prozessor, und die Antwort fällt von 41 auf 11 Token je Sekunde — ein
#: warmer Zug mit 160 Token Antwort dauert 18 s statt 6,3. Robert: „18 s sind
#: in Ordnung, bis 30 alles ok." Auf einer 24-GB-Karte bleibt alles im VRAM.
#: Der Platz im Schema bleibt der eigentliche Hebel (RM-185): Wer das Schema
#: unter 28 000 Token bringt, stellt hier 32 768 zurück und bekommt die
#: Geschwindigkeit wieder.
#:
#: **Seit dem 22.09.2026 wieder 32 768** (RM-185): Die Kurzfassung der
#: Werkzeuge kostet 27 293 Token statt 37 836 — ohne Einheiten am Feld, ohne
#: die zehn Ortsfelder der Bausteine und ohne den Text der Rückseitenfelder,
#: alle drei als Satz im Prompt (``agent/prompt.py``, Version 7). Damit
#: bleiben 5 475 Token für Steckbrief, Verlauf und Antwort, und qwen3:14b
#: liegt auf einer 16-GB-Karte wieder ganz im VRAM.
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
    transport: Transport = post_json_local

    #: Ob der letzte Zug auf einer Grafikkarte lief — ``None``, solange keiner
    #: gelaufen ist.
    #:
    #: **Gemessen wird aus der Antwort, nicht durch eine eigene Anfrage.**
    #: Jede Ollama-Antwort bringt ``prompt_eval_count`` und
    #: ``prompt_eval_duration`` mit; daraus fällt die Rate ohne einen einzigen
    #: zusätzlichen Aufruf ab. Ein ``api/ps`` je Zug wäre eine Messlast im
    #: Kundenzug, und die trägt kein Chat.
    on_gpu: bool | None = None

    @property
    def id(self) -> str:
        return "ollama"

    @property
    def supports_images(self) -> bool:
        """Fest ``False``: das Vorgabemodell (``qwen3:14b``) ist kein
        Vision-Modell, und ein installiertes, gemessenes gibt es nicht.
        Zieht eines ein, gehört hier eine Prüfung wie ``ollama_tool_check``
        hin — angekündigte Fähigkeit heißt auch bei Bildern nichts."""
        return False

    @property
    def available(self) -> bool:
        """Lauscht ein Server?

        Mit einem Socket gefragt statt mit einer Anfrage: die Antwort wird
        gebraucht, während ein Fenster gebaut wird, und ein HTTP-Aufruf an einen
        geschlossenen Port kostet auf manchen Maschinen Sekunden — lang genug,
        um bei jedem Start spürbar zu sein.
        """
        import socket

        try:
            address = urllib.parse.urlsplit(ollama_endpoint(self.url))
            if not address.hostname:
                # Ohne Rechnernamen wird nicht gefragt. Der Rückfall stand hier
                # auf ``localhost`` — und damit fragte eine Adresse, die keine
                # ist, den eigenen Rechner. Dieselbe Stelle gab es dreimal
                # (hier, ``discover.reachable``, ``mesh.reachable``); gefunden
                # hat sie die CI an einer, nachdem eine davon behoben war.
                return False
            with socket.create_connection(
                (address.hostname, address.port or 11434),
                timeout=PROBE_SECONDS,
            ):
                return True
        except UNUSABLE_ADDRESS:
            # Eine unbrauchbare Adresse heißt „nicht erreichbar", nicht
            # „Absturz" — wer hier einen Windows-Pfad einträgt, bekommt ein
            # ausgegrautes Modell und keinen Fehlerbericht (Regel 17). Was
            # eine solche Adresse alles werfen kann, steht bei
            # :data:`UNUSABLE_ADDRESS`; es sind drei Familien, und keine erbt
            # von einer anderen.
            return False

    @property
    def holder(self) -> str:
        """Unter welcher Kennung dieses Modell die Karte hält (Adresse und Name)."""
        return f"ollama:{ollama_endpoint(self.url)}:{self.model}"

    @contextmanager
    def resource_session(
        self, cancelled: CancelToken | None, progress: Callable[[str], None] | None = None
    ) -> Iterator[None]:
        """Hält einen vollständigen Agentenzug exklusiv — und das Modell danach warm.

        Auf der Karte bleibt es geladen (:data:`OLLAMA_KEEP_ALIVE`), bis ein
        anderer Lauf die Spur betritt; auf dem Prozessor wird es sofort
        entladen, dort belegt es den Arbeitsspeicher der Anwendung.
        """
        address = ollama_endpoint(self.url)
        with local_ai_slot(address, cancelled, progress, holder=self.holder):
            try:
                yield
            finally:
                if self.on_gpu is False or not is_local_address(address):
                    self.release()
                else:
                    keep_warm(self.holder, self.release)

    def release(self) -> None:
        """Entlädt ausschließlich ein Ollama auf diesem Rechner."""
        address = ollama_endpoint(self.url)
        if not is_local_address(address):
            return
        payload = {
            "model": self.model,
            "messages": [],
            "stream": False,
            "keep_alive": 0,
        }
        try:
            if self.transport is post_json_local:
                post_json(address, {}, payload, timeout=OLLAMA_RELEASE_SECONDS)
            else:
                self.transport(address, {}, payload)
        except AppError, OSError, ValueError:
            # Freigabe ist Aufräumen. Ein fertiger Vorschlag bleibt gültig,
            # selbst wenn ein gerade beendetes Ollama dabei nicht mehr antwortet.
            _log.warning("Ollama-Modell %s konnte nicht entladen werden", self.model)

    def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]] = (),
        *,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ) -> Reply:
        return self._complete(
            messages,
            tools,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            cancelled=None,
        )

    def complete_cancelable(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]] = (),
        *,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
        cancelled: CancelToken,
    ) -> Reply:
        """Wie :meth:`complete`, mit echtem Abbruch für das lokale Ollama."""
        return self._complete(
            messages,
            tools,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            cancelled=cancelled,
        )

    def _complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]],
        *,
        temperature: float,
        max_output_tokens: int | None,
        cancelled: CancelToken | None,
    ) -> Reply:
        # ``max_output_tokens`` gilt hier nicht: Es ist das Zugbudget eines
        # gehosteten Modells und kostet dort Geld. Lokal begrenzt
        # :data:`OLLAMA_ANSWER_TOKENS` die einzelne Antwort — gegen eine
        # Schleife, nicht gegen eine lange Antwort.
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            # ``num_ctx`` ist keine Feineinstellung, sondern die Bedingung
            # dafür, dass der Auftrag überhaupt ankommt — siehe
            # :data:`OLLAMA_CONTEXT_TOKENS`.
            "options": {
                "temperature": temperature,
                "num_ctx": OLLAMA_CONTEXT_TOKENS,
                "num_predict": OLLAMA_ANSWER_TOKENS,
            },
            # Zwischen zwei Schritten desselben Vorschlags geladen bleiben
            # (:data:`OLLAMA_KEEP_ALIVE`). Danach entlädt ``resource_session``.
            #
            # **Auf dem Prozessor kürzer** (:data:`OLLAMA_KEEP_ALIVE_ON_CPU`):
            # Dort dauert eine Antwort Minuten; die Lage steht in
            # :attr:`on_gpu` und kommt aus der vorigen Antwort. Der erste
            # Schritt nimmt den minutenlangen Rückfall nicht mehr mit.
            "keep_alive": (OLLAMA_KEEP_ALIVE_ON_CPU if self.on_gpu is False else OLLAMA_KEEP_ALIVE),
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

        try:
            address = ollama_endpoint(self.url)
            if cancelled is not None and self.transport is post_json_local:
                answer = post_json_local_cancelable(address, {}, payload, cancelled)
            else:
                if cancelled is not None:
                    cancelled.raise_if_cancelled()
                answer = self.transport(address, {}, payload)
                if cancelled is not None:
                    cancelled.raise_if_cancelled()
        except BackendUnavailable as error:
            # Kein ``reject``: Ollama hat keinen Schlüssel, den man falsch
            # eintragen könnte. Der Name gehört trotzdem in die Meldung — er
            # ist die Antwort auf „welches Modell denn?".
            error.provider = error.provider or self.id
            error.values.setdefault("provider", self.id)
            raise
        self.on_gpu = _ran_on_gpu(answer)
        reply = _from_ollama(answer, self.model)
        length = request_length(payload)
        if prompt_was_cut(reply.input_tokens, length, OLLAMA_CONTEXT_TOKENS):
            raise BackendPromptTruncated(
                counted=reply.input_tokens,
                expected=least_tokens(length),
                window=OLLAMA_CONTEXT_TOKENS,
                provider=self.id,
            )
        # **Und das Fenster kann auch während der Antwort reißen.** Passen
        # Eingabe und Ausgabe zusammen nicht hinein, hat llama.cpp den Kontext
        # geschoben und die Mitte des Auftrags verworfen — ohne ein Zeichen in
        # der Antwort (:class:`BackendContextShifted`). llama.cpp schiebt,
        # sobald der nächste Token das Fenster **erreichte** — die Summe darf
        # also nur darunter liegen. Nur bei gezählter Eingabe: Eine Antwort
        # ohne Zählung ist ungemessen, nicht geschoben.
        total = reply.input_tokens + reply.output_tokens
        if reply.input_tokens and total >= OLLAMA_CONTEXT_TOKENS:
            raise BackendContextShifted(
                counted=total, window=OLLAMA_CONTEXT_TOKENS, provider=self.id
            )
        return reply


#: Wie viele Zeichen des gesendeten JSON ein Token höchstens umfasst — die
#: Obergrenze, mit der die Länge einer Anfrage ihre **Mindestzahl** an Token
#: ergibt (:func:`least_tokens`).
#:
#: Gemessen am 25.09.2026 an der Grundlast des lokalen Zugs (JSON der
#: Nachrichten und Werkzeuge ohne Maskierung der Umlaute): qwen3:14b 4,4
#: Zeichen je Token, qwen3.5:9b 3,5, gemma4:12b 4,9, granite4.1:8b 4,2 —
#: und **gpt-oss:20b 7,5**. Dessen Vorlage schreibt die Werkzeuge nicht als
#: JSON, sondern als knappe Typdeklaration; das JSON, das Solidon zählt, ist
#: dort viel länger als der Text, den das Modell liest. Die Grenze liegt
#: deshalb bei zehn und nicht knapp über dem Größten, das es heute gibt.
MOST_CHARS_PER_TOKEN: Final = 10.0

#: Wie wenige Zeichen ein Token mindestens umfasst — die Untergrenze, mit der
#: die Länge einer Anfrage ihre **Höchstzahl** an Token ergibt. Deutsche Prosa
#: liegt bei 3,5 bis 4 Zeichen je Token, JSON darüber. Eine Anfrage, die auch
#: so gezählt kleiner ist als das Fenster, kann Ollama nicht gekürzt haben.
LEAST_CHARS_PER_TOKEN: Final = 2.5

#: Wie weit Ollamas Zählung einer gekürzten Anfrage über der Hälfte des
#: Fensters liegt: Es behält ``n_keep`` Token vorn und die Hälfte des Rests —
#: gemessen 16 386 bei 32 768 und 1 026 bei 2 048. Die Marke lässt Luft für
#: eine andere Vorgabe von ``n_keep``.
TRUNCATION_KEEPS: Final = 64


def request_length(payload: dict[str, Any]) -> int:
    """Wie viele Zeichen Nachrichten und Werkzeuge einer Anfrage umfassen.

    Ohne die ``\\u``-Maskierung: Ein „ä" ist ein Zeichen und kein
    sechsstelliges, sonst wüchse die Untergrenze aus :func:`least_tokens` mit
    jedem Umlaut über die Wirklichkeit hinaus.
    """
    return len(json.dumps(payload.get("messages", []), ensure_ascii=False)) + len(
        json.dumps(payload.get("tools", []), ensure_ascii=False)
    )


def least_tokens(length: int) -> int:
    """So viele Token hat ein Text dieser Länge mindestens
    (:data:`MOST_CHARS_PER_TOKEN`)."""
    return int(length / MOST_CHARS_PER_TOKEN)


def most_tokens(length: int) -> int:
    """So viele Token hat ein Text dieser Länge höchstens
    (:data:`LEAST_CHARS_PER_TOKEN`)."""
    return int(length / LEAST_CHARS_PER_TOKEN)


def prompt_was_cut(counted: int, length: int, window: int) -> bool:
    """Ob Ollama eine Anfrage dieser Länge gekürzt hat, als es ``counted``
    Token zählte.

    Zwei Zeichen, und jedes genügt: **weniger Token, als der Text mindestens
    hat** — das kann kein Tokenizer gezählt haben —, oder **genau die Zahl,
    die Ollama nach dem Kürzen meldet** (die Hälfte des Fensters und
    :data:`TRUNCATION_KEEPS`), bei einer Anfrage, die größer sein **kann** als
    das Fenster. Das zweite fängt die Kürzung knapp über dem Fenster, wo das
    erste noch schweigt; und eine Anfrage, die auch reichlich gezählt ins
    Fenster passt, ist nie gekürzt. Ohne Zählung ist nichts zu sagen.

    Öffentlich, weil ``tools/measure_local_model.py`` dieselbe Frage stellt:
    Was die Anwendung als gekürzt zurückweist, weist auch die Messung zurück —
    aus einer Rechnung, nicht aus einer Kopie.
    """
    if counted <= 0:
        return False
    if counted < least_tokens(length) * PROMPT_TRUNCATION_FLOOR:
        return True
    if most_tokens(length) < window:
        return False
    half = window // 2
    return half <= counted <= half + TRUNCATION_KEEPS


def _ran_on_gpu(answer: dict[str, Any]) -> bool | None:
    """Ob dieser Zug auf einer Grafikkarte lief — ``None``, wenn ungemessen.

    **Aus der Antwort, ohne eine zweite Frage.** Ollama legt
    ``prompt_eval_count`` und ``prompt_eval_duration`` jeder Antwort bei; ihr
    Verhältnis ist die Einleserate, und die trennt Karte von Prozessor um
    Größenordnungen. Gemessen am 31.08.2026 auf derselben Maschine mit
    denselben 19 641 Token: kalt **1 504 Token je Sekunde** auf einer RTX 4080,
    **28** auf dem Prozessor, als Ollamas GPU-Erkennung in einen Watchdog
    lief. Die Marke von :data:`GPU_PROMPT_TOKENS_PER_SECOND` liegt mit 100
    dazwischen und muss nicht genau treffen — zwischen 28 und 1 504 ist viel
    Platz.

    ``None`` heißt „nicht zu sagen" und nicht „Prozessor": Eine Antwort ohne
    Zähler oder mit Dauer null darf die Einstellung nicht umstellen.
    """
    count = answer.get("prompt_eval_count")
    duration = answer.get("prompt_eval_duration")
    if not isinstance(count, int) or not isinstance(duration, int | float) or duration <= 0:
        return None
    return count / (float(duration) / 1e9) >= GPU_PROMPT_TOKENS_PER_SECOND


def _as_ollama(message: Message) -> dict[str, Any]:
    entry: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        entry["tool_calls"] = [
            {"function": {"name": call.name, "arguments": call.arguments}}
            for call in message.tool_calls
        ]
    return entry


def _from_ollama(answer: dict[str, Any], model: str) -> Reply:
    """Dasselbe für den lokalen Weg — und mit denselben drei Fallen.

    ``message`` muss ein Objekt sein, ``content`` muss keine Zeichenkette sein
    (manche Gegenstellen schicken eine Liste von Textblöcken), und
    ``arguments`` ist bei OpenAI-kompatiblen Servern JSON **als Text**. Alle
    drei endeten hier in einem Programmfehler mit der Bitte um einen
    Fehlerbericht; die ersten beiden werden jetzt gemeldet, der dritte
    gelesen (:func:`_arguments`).
    """
    message = answer.get("message")
    if not isinstance(message, dict):
        raise BackendAnswerUnreadable(excerpt=str(answer)[:400], provider="ollama")
    raw_calls = message.get("tool_calls") or ()
    if isinstance(raw_calls, str) or not isinstance(raw_calls, list | tuple):
        raise BackendAnswerUnreadable(excerpt=str(answer)[:400], provider="ollama")
    calls = tuple(
        ToolCall(
            id=f"call_{index}",
            name=str(_function(entry).get("name", "")),
            arguments=_arguments(_function(entry).get("arguments")),
        )
        for index, entry in enumerate(raw_calls, start=1)
        if isinstance(entry, dict)
    )
    return Reply(
        text=_text_of(message.get("content")),
        tool_calls=calls,
        model=str(answer.get("model", model)),
        stop_reason=str(answer.get("done_reason") or ""),
        input_tokens=_count(answer, "prompt_eval_count"),
        output_tokens=_count(answer, "eval_count"),
    )


def _function(entry: dict[str, Any]) -> dict[str, Any]:
    """Der ``function``-Teil eines Werkzeugaufrufs, notfalls leer."""
    found = entry.get("function")
    return found if isinstance(found, dict) else {}


def _text_of(value: Any) -> str:
    """Der Text einer Antwort, auch wenn er in Blöcken ankommt."""
    if isinstance(value, str):
        return value
    if isinstance(value, list | tuple):
        return "".join(
            str(block.get("text", "")) if isinstance(block, dict) else str(block) for block in value
        )
    return "" if value is None else str(value)


#: Unterhalb dieser Modellgröße (Milliarden Parameter) scheitern
#: Werkzeugaufrufe erfahrungsgemäß reproduzierbar (§27). Die Grenze steht im
#: README und im Warnsatz — wer sie ändert, zieht beide nach.
OLLAMA_MIN_PARAMETERS: Final = 7.0

#: Wie lange die Frage nach den installierten Modellen dauern darf. Sie läuft
#: in einem Arbeiter, nie im Oberflächen-Thread — das Limit begrenzt nur, wie
#: lange der Arbeiter lebt.
TAGS_TIMEOUT_SECONDS = 3.0
MAX_TAGS_RESPONSE_BYTES: Final = 1024 * 1024

Fetch = Callable[[str], dict[str, Any]]
"""``url -> answer``. Austauschbar, damit die Prüfung ohne Netz testbar ist."""


def _get_json(url: str) -> dict[str, Any]:
    """Ein GET, JSON heraus — das Gegenstück zu :func:`post_json` für die
    Modell-Liste von Ollama."""
    address = validate_http_url(url, allow_http=True)
    deadline = deadline_after(TAGS_TIMEOUT_SECONDS)
    request = urllib.request.Request(address)
    opener = opener_for(address)
    apply_header_deadline(opener, deadline)
    with opener.open(request, timeout=TAGS_TIMEOUT_SECONDS) as answer:
        if redirect_left_origin(answer, address, allow_http=True):
            raise ValueError("redirected model list")
        raw = read_limited(answer, limit=MAX_TAGS_RESPONSE_BYTES, deadline=deadline)
    return dict(load_json(raw, max_bytes=MAX_TAGS_RESPONSE_BYTES))


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


#: Modelle, die sich hier bewährt haben — Name, Größe des Downloads, und was
#: die Messung ergeben hat. Die Namen stehen als Konstanten hier und kommen
#: nie aus einer Antwort: an ihnen hängt ein Download.
#:
#: **Warum diese Liste überhaupt existiert.** Wer Ollama über den Knopf in der
#: Liste der zusätzlichen Programme installiert hatte, stand danach vor einem
#: Chat, der weiterhin nicht ging — Ollama bringt kein Modell mit, und der
#: einzige Hinweis darauf war ein Satz mit „ollama pull" darin. Ein Modellname
#: allein hilft dabei nicht: Zwischen 7 und 19 GB Download liegt eine
#: Entscheidung, und ob es Werkzeuge aufruft, ist die eigentliche Frage.
#:
#: **Empfohlen wird jedes Modell, mit dem es klappt** (Robert, 25.09.2026) —
#: und „klappt" heißt gemessen: in ``tools/check_local_model.py`` mindestens
#: sieben von acht Aufrufen richtig, und bei der absichtlich unklaren Anfrage
#: gefragt statt geraten (Fragen vor Raten, §26.1). Der Grafikspeicher im Satz
#: ist die Belegung auf der Karte mit ``num_ctx`` 32 768, gemessen als
#: Unterschied in ``nvidia-smi`` vor und nach dem Laden — mehr als Ollama in
#: ``ps`` meldet, weil der Treiber seinen Anteil dazulegt. Er ist die
#: Systemanforderung: Passt das Modell nicht ganz auf die Karte, rechnet der
#: Prozessor mit, und jede Antwort dauert ein Vielfaches.
#:
#: Gemessen am 25.09.2026 auf einer RTX 4080 (16 GB), Ollama 0.34.3, mit dem
#: Werkzeugangebot aus ``agent/offer.py`` und dem kompakten Prompt. Die Suite
#: (39 Aufträge, ``tools/run_agent_suite.py``) am 26.09.2026 auf freier Karte
#: zeigt, was die Probe nicht zeigt: qwen3:14b trifft in ihr 22, qwen3.5:9b
#: 21, gpt-oss:20b nur 10 — es fordert nie eine Kurzform an und setzt keinen
#: Baustein. qwen3:30b-a3b ist dort nicht gemessen. Gezählt mit der Bewertung
#: vom 26.09.2026 (ein Zwilling ist dieselbe Handlung, ``run_agent_suite``).
#:
#: **Mehrteilig** heißt: ein Fall mit mindestens zwei erwarteten Operationen,
#: zehn der 39 (Grundkörper plus Baustein). Davon trafen qwen3:14b und
#: qwen3.5:9b je zwei, gpt-oss:20b keinen — nachgezählt an denselben Läufen in
#: der Durchsicht 0.5.1; der Changelog verspricht genau diese Auskunft. Die
#: Sätze sagen „Einzelne Anweisungen" und „Testaufträge" statt „Probe" und
#: „Suite": Der Kunde kennt keines der beiden Werkzeuge.
#:
#: **7,4 GB heißt nicht „passt auf 8 GB".** Wie viel auf die Karte geht,
#: entscheidet llama-server beim Laden selbst: qwen3.5:9b plant 6 031 MiB und
#: verlangt dazu 1 919 MiB Rest, also rund 7 950 MiB frei. Auf einer 8-GB-Karte
#: bliebe das nur mit weniger als 250 MiB für Desktop und Fenster; auf der
#: Messmaschine belegten sie ohne Modell 1,3 GB. Nachgestellt in der
#: Durchsicht 0.5.1 über ``LLAMA_ARG_FIT_TARGET`` an einem zweiten Ollama
#: (eine fremde Belegung der Karte hilft unter WDDM nicht, llama-server sah
#: weiter 15 022 MiB frei): mit 1,35 GB Desktop 26 von 34 Schichten auf der
#: Karte und 21 bis 26 statt 80 Token je Sekunde, mit 0,7 GB 30 Schichten und
#: 31 bis 34. Ab 10 GB passt es ganz.
OLLAMA_SUGGESTIONS: Final = (
    (
        "qwen3.5:9b",
        6.6,
        _(
            "Belegt 7,4 GB Grafikspeicher und passt ab 10 GB ganz auf die Karte; auf einer "
            "8-GB-Karte rechnet ein Teil auf dem Prozessor, jede Anfrage dauert dann zwei- "
            "bis dreimal so lange. Einzelne Anweisungen: sieben von acht richtig. "
            "Von 39 Testaufträgen 21, von zehn mehrteiligen zwei; fragt bei Unklarem "
            "seltener nach. Rund 6 Sekunden je Anfrage."
        ),
    ),
    (
        "qwen3:14b",
        9.3,
        _(
            "Belegt 13,6 GB Grafikspeicher. Einzelne Anweisungen: acht von acht richtig. "
            "Von 39 Testaufträgen 22, von zehn mehrteiligen zwei; denkt vor jeder Antwort "
            "nach, rund 18 Sekunden je Anfrage."
        ),
    ),
    (
        "gpt-oss:20b",
        13.8,
        _(
            "Belegt 12,9 GB Grafikspeicher. Einzelne Anweisungen: sieben von acht richtig. "
            "Von 39 Testaufträgen nur 10, von zehn mehrteiligen keinen — gut für einzelne "
            "Anweisungen; rund 7 Sekunden je Anfrage."
        ),
    ),
    (
        "qwen3:30b-a3b",
        18.6,
        _(
            "Braucht mehr als 16 GB Grafikspeicher; auf einer 16-GB-Karte rechnet ein "
            "Drittel auf dem Prozessor, und es bleibt bei rund 17 Sekunden je Anfrage. "
            "Einzelne Anweisungen: acht von acht richtig; mit den Testaufträgen nicht "
            "gemessen."
        ),
    ),
)

#: Gemessen und **nicht** empfohlen — angeboten wird keines davon. Der Satz
#: steht trotzdem da, wenn eines installiert ist: Ein Kunde, der es schon hat,
#: soll lesen, warum der Chat damit nichts tut oder rät, statt drei nackte
#: Namen zu sehen (:func:`known_model_note`). Dieselbe Messung wie oben.
OLLAMA_UNSUITABLE: Final = (
    (
        "qwen3.5:9b-q8_0",
        10.7,
        _(
            "Belegt 10,6 GB und traf mit sechs von acht seltener als qwen3.5:9b — "
            "die kleinere Version ist die bessere Wahl."
        ),
    ),
    (
        "gemma4:12b",
        7.6,
        _("Lief bei zwei von acht Anfragen in eine Antwort ohne Ende. Für Solidon ungeeignet."),
    ),
    (
        "granite4.1:8b",
        5.3,
        _("Rät bei einer unklaren Anfrage, statt nachzufragen. Für Solidon ungeeignet."),
    ),
    (
        "llama3.1:8b",
        4.9,
        _("Rät bei einer unklaren Anfrage, statt nachzufragen. Für Solidon ungeeignet."),
    ),
    (
        "mistral-nemo:latest",
        7.1,
        _(
            "Schreibt bei vier von acht Anfragen über das Werkzeug, statt es "
            "aufzurufen. Für Solidon ungeeignet."
        ),
    ),
    (
        "qwen2.5-coder:14b",
        9.0,
        _(
            "Schreibt jeden Aufruf als Text hin, statt ihn auszuführen — trotz "
            "vierzehn Milliarden Parametern. Für Solidon ungeeignet."
        ),
    ),
    (
        "llama3:latest",
        4.7,
        _("Ollama lehnt Werkzeuge für dieses Modell ab. Für Solidon ungeeignet."),
    ),
)


def normalised_model_name(name: str) -> str:
    """Der Vergleichsname einer Ollama-Modellfamilie.

    ``:latest`` ist Ollamas Kennzeichnung für denselben unmarkierten Namen,
    kein zweites installiertes Modell. Andere Kennzeichnungen bleiben
    erhalten: ``qwen3:8b`` und ``qwen3:14b`` sind tatsächlich verschieden.
    """
    return name.strip().removesuffix(":latest")


def known_model_suggestion(name: str) -> tuple[float, TranslatableText] | None:
    """Größe und Satz zu einem Modellnamen, sonst ``None``.

    Verglichen wird ohne Kennzeichnung: Ollama führt dasselbe Modell als
    ``mistral-nemo`` und als ``mistral-nemo:latest``, und der Kunde hat es
    einmal installiert, nicht zweimal. Gesucht wird in beiden Listen — die
    empfohlenen und die gemessen ungeeigneten.
    """

    wanted = normalised_model_name(name)
    for entry, gigabytes, note in (*OLLAMA_SUGGESTIONS, *OLLAMA_UNSUITABLE):
        if normalised_model_name(entry) == wanted:
            return gigabytes, note
    return None


def known_model_note(name: str) -> TranslatableText | None:
    """Der Satz zu einem Modellnamen, oder ``None`` für ein unbekanntes.

    Was zu einem installierten Modell danebensteht, wenn es in
    :data:`OLLAMA_SUGGESTIONS` oder :data:`OLLAMA_UNSUITABLE` bekannt ist.

    **Die Zahl entscheidet die Wahl, und sie stand nur bei den empfohlenen.**
    Ein Kunde mit drei installierten Modellen sah drei nackte Namen; dass
    ``mistral-nemo`` in dieser Messung null von fünf Aufrufen schaffte, war
    nirgends zu lesen. Ein Modell, das die Aufrufe als Fließtext ausgibt, sieht
    im Chat aus, als arbeite es — genau deshalb gibt es
    ``tools/check_local_model.py``, und genau deshalb gehört sein Ergebnis in
    die Auswahl und nicht nur in einen Docstring.
    """
    suggestion = known_model_suggestion(name)
    return suggestion[1] if suggestion is not None else None


#: Ein Download von mehreren Gigabyte. Die Grenze ist großzügig, weil eine
#: langsame Leitung sonst mitten im Modell aufgibt.
PULL_TIMEOUT_SECONDS = 7200.0
MAX_PULL_RESPONSE_BYTES: Final = 16 * 1024 * 1024
MAX_PULL_LINE_BYTES: Final = 64 * 1024

PullProgress = Callable[[str, float], None]
"""``schritt, anteil -> None``. Der Anteil ist 0…1, oder -1 für „unbekannt"."""


def ollama_endpoint(url: str | None, path: str = "/api/chat") -> str:
    """Die Adresse eines Ollama-Endpunkts aus dem, was jemand eingetragen hat.

    **Der Kunde trägt ein, was das Werkzeug über sich selbst sagt.** Ollamas
    eigene Ausgabe nennt ``http://127.0.0.1:11434`` — die Basisadresse ohne
    Endpunkt ist damit die *wahrscheinlichste* Eingabe und nicht die
    unwahrscheinlichste.

    Bis zum 24.08.2026 entstand die Adresse hier aus
    ``url.replace("/api/chat", "/api/pull")``. Enthielt die Eingabe kein
    ``/api/chat``, blieb sie unverändert, und jede Anfrage ging an die Wurzel;
    Ollama antwortet darauf mit **405 method not allowed**. Ein Kunde hat drei
    Stunden dafür gebraucht, und im Protokoll standen vierzehn dieser 405.

    Angenommen werden deshalb alle Schreibweisen — mit und ohne Schema, mit und
    ohne Endpunkt, mit und ohne Schrägstrich am Ende. **Ein eigener Pfad davor
    bleibt erhalten:** Hinter einem Reverse-Proxy liegt Ollama unter
    ``/ollama/api/chat``, und wer das einträgt, meint es so.
    """
    address = (url or "").strip() or OLLAMA_URL
    if "://" not in address:
        # „127.0.0.1:11434" ohne Schema ist keine Nachlässigkeit, sondern die
        # Schreibweise, in der Adressen üblicherweise weitergegeben werden.
        address = f"http://{address}"
    parts = urllib.parse.urlsplit(address)
    prefix = parts.path.rstrip("/")
    # Ein bekannter Endpunkt wird durch den gefragten ersetzt, alles davor
    # bleibt stehen. Zwei Fälle, und beide brauchen ihre eigene Prüfung:
    # ``…/api/chat`` endet auf einem Endpunkt, ``…/api`` **ist** einer. Ein
    # bloßes ``rfind("/api")`` deckte beide ab und schnitt dabei auch
    # ``/apiary`` und ``/api-gateway`` ab — Pfadanfänge, die zufällig so
    # beginnen und einem Reverse-Proxy gehören.
    if prefix.endswith("/api"):
        prefix = prefix[: -len("/api")]
    else:
        endpoint = prefix.rfind("/api/")
        if endpoint != -1:
            prefix = prefix[:endpoint]
    # Abfrage und Fragment bleiben stehen. Sie gehören zwar zum Endpunkt und
    # nicht zur Basis — aber wer einen Zugangstoken in der Adresse führt, weil
    # sein Reverse-Proxy ihn verlangt, verlöre ihn hier stillschweigend.
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, prefix + path, parts.query, parts.fragment)
    )


def installed_models(url: str | None = None, fetch: Fetch = _get_json) -> tuple[str, ...]:
    """Welche Modelle bei Ollama liegen. Leer, wenn es nicht antwortet.

    Für die Auswahl im Einrichtungsdialog: Ein Feld, in das man den Namen
    tippt, setzt voraus, dass man ihn kennt.
    """
    address = ollama_endpoint(url or _configured_ollama_url(), "/api/tags")
    try:
        answer = fetch(address)
    except UNUSABLE_ADDRESS:
        return ()
    return tuple(
        str(entry.get("name", "")) for entry in answer.get("models", ()) if entry.get("name")
    )


def pull_model(
    model: str,
    url: str | None = None,
    progress: PullProgress | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> TranslatableText | None:
    """Ein Modell holen. ``None`` heißt: es liegt jetzt da.

    Ollama antwortet auf ``/api/pull`` mit einer Zeile JSON je Zustand, und
    beim Herunterladen tragen die Zeilen ``total`` und ``completed`` — daraus
    entsteht ein echter Prozentwert und nicht der unbestimmte Balken, mit dem
    ein Vorgang von neun Gigabyte aussieht wie ein Hänger.

    **Der Modellname wird nicht geprüft, sondern eingesetzt.** Er kommt aus
    :data:`OLLAMA_SUGGESTIONS` oder von dem, der ihn tippt — nie aus einer
    Modellantwort. Was Ollama daraus macht, ist seine Sache; ein unbekannter
    Name kommt als Fehlermeldung zurück und nicht als Download.
    """
    address = ollama_endpoint(url or _configured_ollama_url(), "/api/pull")
    body = json.dumps({"model": model, "stream": True}).encode("utf-8")
    _log.info("pulling ollama model %s", model)
    deadline = deadline_after(PULL_TIMEOUT_SECONDS)
    try:
        # **Der Bau der Anfrage steht mit im ``try``.** ``Request()`` selbst
        # wirft einen ``ValueError``, sobald die Adresse kein Schema trägt, das
        # es kennt — gemessen an ``://kaputt``. Davor lag er eine Zeile
        # oberhalb, und dort fing ihn nichts.
        address = validate_http_url(address, allow_http=True)
        request = urllib.request.Request(
            address, data=body, headers={"Content-Type": "application/json"}
        )
        opener = opener_for(address)
        apply_header_deadline(opener, deadline)
        with opener.open(request, timeout=PULL_TIMEOUT_SECONDS) as answer:
            if redirect_left_origin(answer, address, allow_http=True):
                raise ValueError("redirected model pull")
            for raw in _pull_lines(answer, deadline):
                if cancelled is not None and cancelled():
                    # Ollama räumt einen abgebrochenen Zug selbst auf und
                    # behält, was schon geladen ist — ein zweiter Versuch
                    # setzt fort, statt neu anzufangen.
                    _log.info("pull of %s cancelled", model)
                    return _("Abgebrochen. Ein neuer Versuch setzt fort, wo dieser aufgehört hat.")
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    entry = dict(load_json(line, max_bytes=MAX_PULL_LINE_BYTES))
                except ValueError:
                    continue
                if entry.get("error"):
                    return _("Ollama hat den Namen nicht angenommen.")
                if progress is not None:
                    progress(str(entry.get("status", "")), _share(entry))
    except urllib.error.HTTPError as error:
        try:
            raw = read_limited(error, limit=MAX_ERROR_BYTES, deadline=deadline)
            detail = redact_external(raw.decode("utf-8", errors="replace"), limit=200)
        except ResponseDeadlineError, ResponseTooLargeError, ValueError:
            detail = ""
        finally:
            error.close()
        _log.warning("pull of %s refused: %s", model, detail)
        return _("Ollama hat den Namen nicht angenommen.")
    except UNUSABLE_ADDRESS:
        return _("Ollama hat nicht geantwortet — läuft es noch?")
    return None


def _pull_lines(answer: Any, deadline: float) -> Iterator[bytes]:
    """Zerlegt Ollamas begrenzten Antwortstrom in ebenfalls begrenzte Zeilen."""
    pending = b""
    for chunk in iter_limited(
        answer,
        limit=MAX_PULL_RESPONSE_BYTES,
        deadline=deadline,
    ):
        pending += chunk
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            if len(line) > MAX_PULL_LINE_BYTES:
                raise ResponseTooLargeError(len(line), MAX_PULL_LINE_BYTES)
            yield line
        if len(pending) > MAX_PULL_LINE_BYTES:
            raise ResponseTooLargeError(len(pending), MAX_PULL_LINE_BYTES)
    if pending:
        yield pending


def _share(entry: dict[str, Any]) -> float:
    """Der Anteil aus einer Fortschrittszeile, oder -1, wenn sie keinen trägt."""
    total = entry.get("total")
    done = entry.get("completed")
    if not isinstance(total, int | float) or not total:
        return -1.0
    if not isinstance(done, int | float):
        return -1.0
    return max(0.0, min(1.0, float(done) / float(total)))


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
    address = ollama_endpoint(url or _configured_ollama_url(), "/api/tags")
    try:
        answer = fetch(address)
    except UNUSABLE_ADDRESS:
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
    # Kein Modellname im Satz: Welche sich bewährt haben, sagt die Liste im
    # Dialog (:data:`OLLAMA_SUGGESTIONS`), und ein zweiter Name hier wäre ein
    # Zwilling, der beim nächsten Wechsel der Vorgabe stehen bliebe.
    return _(
        "Das lokale Modell hat weniger als 7 Milliarden Parameter — "
        "Werkzeugaufrufe scheitern damit erfahrungsgemäß. Bewährt haben sich "
        "die Modelle, die „Bearbeiten → Chat einrichten“ vorschlägt. Ohne "
        "passende Grafikkarte fällt Ollama auf den Prozessor zurück und wird "
        "erheblich langsamer."
    )


def local_model_expectation(model: str | None = None) -> TranslatableText:
    """Was das eingestellte lokale Modell hier leistet — gemessen, nicht geschätzt.

    Der Satz gehört an die Stelle, an der jemand Ollama einträgt. Ohne ihn
    erlebt er das Ergebnis als Fehler der Anwendung: Ein Rückfall auf den
    Prozessor beginnt erst nach vielen Minuten zu antworten, während derselbe
    Werkzeugweg auf einer geeigneten Grafikkarte in Sekunden fertig ist.

    **Die Messung ist die des eingestellten Modells**, aus derselben Liste,
    die der Dialog zeigt (:func:`known_model_note`). Bis zum 25.09.2026 stand
    hier fest die Messung von qwen3:14b — auch unter einem anderen Modell, und
    dann über ein fremdes. Ein unbekanntes Modell bekommt den Weg zur Probe.
    """
    name = model or configured_ollama_model()
    note = known_model_note(name)
    measured = (
        _("Für {model} liegt keine Messung vor.", model=name)
        if note is None
        else _("{model}, gemessen auf einer RTX 4080: {note}", model=name, note=note)
    )
    return _(
        "{measured} Passt das Modell nicht ganz in den Grafikspeicher, rechnet der "
        "Prozessor mit — gemessen wurden dort 7,8 Token je Sekunde beim Einlesen, und "
        "eine Antwort beginnt erst nach vielen Minuten; nach zehn Minuten bricht "
        "Solidon ab. Welcher Weg hier rechnet, sagt „Werkzeuge prüfen“ unter "
        "„Bearbeiten → Chat einrichten“. Für zügige Antworten braucht es eine "
        "geeignete Grafikkarte oder einen Schlüssel für ein gehostetes Modell.",
        measured=measured,
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
    except AppError, OSError, ValueError:
        return None
    _stays_warm(backend)
    return reply.wants_tools


def _stays_warm(backend: OllamaBackend) -> None:
    """Ein Modell, das eine Probe geladen hat, bleibt für den ersten Zug warm —
    und gibt die Karte frei, sobald ein anderer Lauf sie braucht
    (:func:`~app.core.backends.resources.keep_warm`). Ohne den Eintrag hielte
    es sie drei Minuten gegen einen ComfyUI-Lauf, der davon nichts weiß."""
    if is_local_address(ollama_endpoint(backend.url)):
        keep_warm(backend.holder, backend.release)


#: Wie viele Token je Sekunde eine Grafikkarte beim Einlesen mindestens
#: schafft. Der Wert trennt nicht scharf zwischen Karten, sondern zwischen
#: *Karte* und *Prozessor*: Gemessen liegt eine 16-GB-Karte bei einigen
#: hundert bis über tausend, und ein Prozessor bei 8 bis 30. Alles unter dieser
#: Marke ist Prozessorbetrieb, gleich welche Karte im Rechner steckt.
GPU_PROMPT_TOKENS_PER_SECOND: Final = 100.0

#: Wie groß der Systemprompt dieser Anwendung ist — einschließlich des
#: kompakten Werkzeugsatzes, den der Ollama-Pfad fährt. Am 03.09.2026 mit
#: ``qwen3:14b`` über den echten ``/api/chat``-Auftrag gemessen, nicht aus der
#: JSON-Länge geschätzt (siehe :data:`OLLAMA_CONTEXT_TOKENS`).
#:
#: **Diese Zahl rechnet dem Kunden seine Wartezeit vor** — sie steht in
#: :func:`speed_warning` als Platzhalter und wird dort mit
#: :attr:`Speed.prompt_minutes` zu Minuten. Wer die Grundlast ändert, ändert
#: sie mit: Vor dem 31.08.2026 stand hier 23 891 aus einer Messung vom 28.,
#: und nach zwei Schritten an den Werkzeugschemata waren es 19 641 — der
#: Kunde bekam eine um 22 Prozent zu hohe Schätzung, bei 7,8 Token je Sekunde
#: einundfünfzig statt zweiundvierzig Minuten.
#:
#: **Und sie wächst mit dem Register, nicht nur mit einer Optimierung.** Die
#: vier Merkmalsoperationen vom 03.09.2026 haben sie auf **22 691** gehoben —
#: dieselbe Messung, dieselbe Karte, 110 statt 106 Werkzeuge. Das sind bei
#: 7,8 Token je Sekunde achtundvierzig Minuten statt zweiundvierzig, und
#: genau deshalb steht die Zahl nicht als Schätzung im Code: Wer eine
#: Operation dazulegt, verlängert dem Kunden die Wartezeit, und er soll es
#: hier sehen.
#:
#: *Merkmal verdoppeln* hat am selben Tag **165 Token** dazugelegt — von
#: 22 691 auf 22 856, eine einzige Operation. Das ist die Größenordnung, in
#: der eine neue Operation den Chat kostet: knapp zwei Zehntel Prozent des
#: Fensters und eine halbe Minute Wartezeit auf dem Prozessorweg.
#:
#: **Am 08.09.2026 nachgemessen: 25 670 Token bei 115 Werkzeugen** (*Fügeweg
#: prüfen*), qwen3:14b auf der RTX 4080, vollständig im VRAM — 52,2 s kalt,
#: 11,6 s warm. Damit sind es **78,3 %** des Fensters von 32 768 statt der
#: 69,8 %, die hier standen.
#:
#: **Die Fortschreibung hat den Zuwachs unterschätzt, und zwar erheblich.**
#: Hier stand, nach der Rate von 165 Token je Operation wären es rund 23 355;
#: gemessen sind es 25 670. Zwischen der letzten echten Messung (22 856 bei
#: 111 Werkzeugen am 03.09.) und heute liegen vier Operationen und **2814
#: Token** — 703 je Operation statt 165. Die Rate stammte von *Merkmal
#: verdoppeln*, einer Operation mit wenigen Parametern; wer eine mit vollem
#: Schema und einem ``caveat`` dazulegt, zahlt ein Vielfaches.
#:
#: Der Satz, der hier stand — „der Abstand zwischen gemessener und wirklicher
#: Zahl wächst still" —, hat sich damit selbst belegt. Er stimmte, und er war
#: um mehr als das Vierfache zu optimistisch.
#:
#: Die nachfolgende Operations-/Bausteineinheit mit Parameterbindungen,
#: Featurelisten und drei direkt erzeugbaren Kalibrierkörpern wurde mit
#: 119 Werkzeugen erneut gemessen: **28 281 Token**, 18,9 s kalt und 2,3 s
#: warm (je ein Lauf, qwen3:14b, vollständig im VRAM). Der warme Wert nutzt
#: den Promptcache und ist keine ungepufferte Einleserate.
#:
#: **Was daraus folgt, ist keine Zahl, sondern eine Grenze:** Bei 86,3 % des
#: Fensters allein für Auftrag und Werkzeuge bleibt für Szenensteckbrief,
#: Prüfbericht und Chatverlauf weniger als ein Viertel. Die nächsten
#: Operationen kosten den Chat nicht mehr Wartezeit, sondern Platz.
#:
#: **Am 14.09.2026 mit 121 Werkzeugen gemessen: 31 465 Token** (RM-054;
#: ``tools/measure_local_model.py``, qwen3:14b, RTX 4080, vollständig im
#: VRAM — 22,9 s kalt, warm 2,3 bis 2,4 s in drei Zügen). Das sind **96,0 %**
#: des Fensters; für Steckbrief, Prüfbericht, Verlauf und die Frage selbst
#: bleiben 1 303 Token. Und das Fenster lässt sich auf dieser Karte nicht
#: heben: Mit ``num_ctx`` 40 960 meldet ``ollama ps`` 16 GB und
#: ``10 %/90 % CPU/GPU`` — das Modell läuft über, und der Prozessorweg ist
#: laut derselben Messreihe 72-mal langsamer. Der Platz muss aus dem Schema
#: kommen (RM-173). Die zwei Zahlen davor — 121 Werkzeuge, 28 281 Token von
#: 119 — standen fünf Tage auseinander; der Wächter hatte zweimal nur die
#: Werkzeugzahl nachziehen lassen, weil eine hochgerechnete Messung keine ist.
#:
#: **Mit der Kürzung des kompakten Schemas (RM-173) am 15.09.2026 neu gemessen:
#: 28 616 Token** — dieselben 121 Werkzeuge, dasselbe Werkzeug, dieselbe Karte,
#: drei warme Züge mit 2,3 bis 7,1 s. `play` und die vier Geschwisterachsen
#: ohne Feldtext, Zahlenfelder als Zahl, Konventionen und Bindung einmal im
#: Prompt: 87,3 % des Fensters statt 96,0 %, 4 152 Token Rest statt 1 303. Der
#: Kaltstart derselben Messung — 188 s — ist keine Eigenschaft des Prompts:
#: Der Modellstart kriecht seit den Torläufen dreier Sitzungen am Abend beim
#: Anlegen des KV-Caches (RM-081); die 22,9 s vom Nachmittag bleiben der
#: Bezugswert.
#:
#: **Am 16.09.2026 mit 142 Werkzeugen gemessen: 36 546 Token** — und damit
#: **111,5 % des Fensters.** Die erste Messung mit ``num_ctx`` 32 768 meldete
#: 16 386: die Hälfte des Fensters plus zwei, also die stille Kürzung aus
#: :class:`BackendPromptTruncated`, keine Ersparnis. Ungekürzt gezählt mit
#: ``num_ctx`` 65 536 (29 s kalt, ``num_predict`` 1); bei 40 960 liegt
#: qwen3:14b noch zu 89 % im VRAM (14,7 von 16,4 GB), warm 4,3 bis 4,5 s statt
#: 2,4 — aber Steckbrief, Prüfbericht und Verlauf kommen obendrauf, und auch
#: dieses Fenster wäre voll. Die 21 Werkzeuge seit dem 15.09.2026 (Organizer,
#: Felder, Lochbilder, Profilklemme, Dichtnut) haben das Schema über das
#: Fenster geschoben: Wer mit dem Vorgabemodell chattet, bekommt die
#: Kürzungsmeldung mit ihren Handlungen. Der Platz muss aus dem Schema kommen
#: (RM-173, Fortsetzung als RM-185). Mit *Abschneiden* als 143. Werkzeug am
#: selben Tag erneut gezählt: 36 731.
#:
#: Am 20.09.2026 mit *Baugruppe auf die Platte* funktional neu gezählt:
#: **36 826 Token bei 144 Werkzeugen**, qwen3:14b (bdbd181c33f2), Ollama 0.34.2.
#: ``tools/measure_local_model.py --count-tokens --model qwen3:14b`` sendete
#: genau einen vollständigen kompakten Auftrag mit ``num_ctx`` 40 960,
#: ``num_predict`` 1 und ``keep_alive`` 0; die Antwort zählte einen Ausgabetoken.
#: Keine Zeit- oder Geschwindigkeitsmessung. SHA-256 der gesendeten Anfrage:
#: ``52a8e8a613cfd8f9c21eb7569f1959ef456484bd6019d4352aadaabaa5b550b1``.
#:
#: Am 21.09.2026 mit den drei exakten Grundkörpern Kegel, Kugel und Ring
#: (P2.8) erneut gezählt: **37 661 Token bei 147 Werkzeugen**, 91,9 Prozent des
#: Fensters — qwen3:14b (bdbd181c33f2), Ollama 0.34.2, derselbe Aufruf mit
#: ``num_ctx`` 40 960, ``num_predict`` 1, ``keep_alive`` 0, ein Ausgabetoken.
#: SHA-256 der gesendeten Anfrage:
#: ``9028a67c2d6d7aabfb11c287dfffc0fcaacc2a32526f6c0eb805ecc04d692143``.
#:
#: Am 22.09.2026 zählte derselbe Aufruf vor jeder Änderung **37 836** — der
#: Satz war seit dem 21. um 175 Token gewachsen, ohne neue Operation. Mit der
#: Kurzfassung aus RM-185 (Prompt-Version 7) dann **27 293 Token bei 147
#: Werkzeugen**, gezählt mit ``num_ctx`` 32 768 und ebenso mit 40 960 —
#: dieselbe Zahl, also ungekürzt; 83,3 % des Fensters. qwen3:14b
#: (bdbd181c33f2), Ollama 0.34.2, ``num_predict`` 1, ``keep_alive`` 0, ein
#: Ausgabetoken. SHA-256 der Anfrage mit 32 768:
#: ``728c421340d676cb926088faaf77bf5c1aca43b97b3a0e347cf6c9e92a297329``.
#:
#: **Am 25.09.2026 mit dem Werkzeugangebot (``agent/offer.py``, Prompt-Version
#: 8) gezählt: 7 276 Token bei 153 Werkzeugen** — 22,2 % des Fensters. Gezählt
#: ist seither die Grundlast eines lokalen Zugs: jede Operation in Kurzform,
#: keine ausführlich, denn „Hallo." meint keine. Eine Anfrage, die Operationen
#: meint, legt je ausführlichem Werkzeug rund 100 bis 300 Token dazu (in der
#: Suite bis 14 215 mit Steckbrief und Verlauf). Dieselben 153 Werkzeuge in
#: der Kurzfassung von vorher kosteten 30 461. qwen3:14b (bdbd181c33f2),
#: Ollama 0.34.3, ``num_ctx`` 32 768, ``num_predict`` 1, ``keep_alive`` 0, ein
#: Ausgabetoken. SHA-256 der Anfrage:
#: ``a66f67dae56492664bc4b762938c2b534e5777c084bd0bdd840b962f37cbd9ce``.
#:
#: Am 02.10.2026 mit *Rohr anlegen* in beiden Kernen (RM-398) gezählt:
#: **7 342 Token bei 155 Werkzeugen**, 22,4 % des Fensters — qwen3:14b,
#: Ollama 0.35.0, ``num_ctx`` 32 768, ``num_predict`` 1, ``keep_alive`` 0, ein
#: Ausgabetoken. SHA-256 der Anfrage:
#: ``46cf91e87d1a0b8290b0e1de2455371be110f4d732d9f57252b0ddd84925156c``.
#: Mit der *Lasche mit Loch* (RM-398) derselbe Aufruf: **7 372 Token bei 156
#: Werkzeugen**; SHA-256
#: ``0c050279ab0443f9cd1987c7a4634d20b6765c808d6db1fadff2335caf4cd820``.
#: Mit der *Rohrschelle* (Einsetzen und Anlegen) und der Rohrreihe als
#: Tabellenart: **7 436 Token bei 158 Werkzeugen**; SHA-256
#: ``6319d645968f0b9fdcb2c847a41c2349e03e654518204fcaa98ed61c2363ddfe``.
#: Am 02.10.2026 mit den vier Haltern (RM-399, je Einsetzen und Erzeugen)
#: derselbe Aufruf: **7 522 Token bei 161 Werkzeugen**, 23,0 % des Fensters —
#: acht Werkzeuge in Kurzform kosten 246 Token. qwen3:14b (bdbd181c33f2),
#: Ollama 0.35.0, ``num_ctx`` 32 768, ``num_predict`` 1, ``keep_alive`` 0, ein
#: Ausgabetoken. SHA-256 der Anfrage:
#: ``112446278d944634a2caeb85861a6fc6edf2aa4b728826c0bc31ab50df8105e5``.
#: Mit Rohr, Lasche und Rohrschelle (RM-398) und den vier Haltern (RM-399)
#: zusammen derselbe Aufruf: **7 729 Token bei 166 Werkzeugen**, 23,6 % des
#: Fensters. qwen3:14b, Ollama 0.35.0, ``num_ctx`` 32 768, ``num_predict`` 1,
#: ``keep_alive`` 0, ein Ausgabetoken. SHA-256 der Anfrage:
#: ``f119d89ad564b8679fca5d510a53f3cc1e346ec16ffa6ba500a719bad92703e6``.
#: Am 03.10.2026 mit dem Behälter-Assistenten (RM-397: *Behälter mit Deckel*
#: und *Behältereinsatz erzeugen*) derselbe Aufruf: **7 794 Token bei 168
#: Werkzeugen**, 23,8 % des Fensters — qwen3:14b, Ollama 0.35.1, ``num_ctx``
#: 32 768, ``num_predict`` 1, ``keep_alive`` 0, ein Ausgabetoken. SHA-256 der
#: Anfrage: ``76eab8f55813d0f21ca9a999f78a702cb278603126d9a7376f86ddc7116e3920``.
#: Am 04.10.2026 mit *Als Muster zusammenfassen* (RM-504) derselbe Aufruf:
#: **7 825 Token bei 169 Werkzeugen**, 23,9 % des Fensters — qwen3:14b
#: (bdbd181c33f2), Ollama 0.35.1, ``num_ctx`` 32 768, ``num_predict`` 1,
#: ``keep_alive`` 0, ein Ausgabetoken. SHA-256 der Anfrage:
#: ``e2d8a22a52e426158688f0f32a7542254873d5cf53e3dd00a33046cb15a2081f``.
#: Am 04.10.2026 mit den acht Bausteinen aus dem Dateiaudit (RM-184, je Einsetzen
#: und, außer der Schlauchtülle, Erzeugen) derselbe Aufruf, zusammen mit RM-504:
#: **8 300 Token bei 184 Werkzeugen**, 25,3 % des Fensters — qwen3:14b, Ollama
#: 0.35.1, ``num_ctx`` 32 768, ``num_predict`` 1, ``keep_alive`` 0, ein
#: Ausgabetoken. SHA-256 der Anfrage:
#: ``0ba0af27ea66ae4dd8e5258ff4c7738c09e8a1f022e0e08351ef3aff97c98c06``.
#: Am 04.10.2026 mit *Schrift einlegen* und den Abläufen aus dem Dateiaudit
#: (RM-184: drehender Fügeweg, Prüfausschnitt einer Passung, Schrift auf Bogen
#: und Rundung) derselbe Aufruf: **8 330 Token bei 185 Werkzeugen**, 25,4 %
#: des Fensters — qwen3:14b, Ollama 0.35.1, ``num_ctx`` 32 768,
#: ``num_predict`` 1, ``keep_alive`` 0, ein Ausgabetoken. SHA-256 der Anfrage:
#: ``fde40c864e0c61de6949d749a3de15523ea8e4b0efa9020c863df44f81f8a0cf``.
#: Mit *Gegenform einlassen* (RM-184) derselbe Aufruf: **8 361 Token bei 186
#: Werkzeugen**, 25,5 % des Fensters; SHA-256
#: ``0414aa80760535459915458d4f30f50233b0c4ad520e6eebe8782ec55685e97a``.
#: Mit *Stift für Bohrung* und dem Scharnier an *Deckel erzeugen* (RM-184):
#: **8 394 Token bei 187 Werkzeugen**, 25,6 % des Fensters; SHA-256
#: ``8c6e6097e5aee4c30cd3189d0d9f583fd70b04911ae4d99d17f97d96a78456eb``.
PROMPT_TOKENS: Final = 8394

#: Wie viele Token der **erste Schritt eines üblichen Zugs** einliest — die
#: Zahl, mit der die Wartezeit auf dem Prozessor geschätzt wird
#: (:meth:`Speed.prompt_minutes`).
#:
#: Nicht :data:`PROMPT_TOKENS`: Das ist die Grundlast zu „Hallo.", ohne ein
#: einziges ausführliches Werkzeug, ohne Steckbrief. Ein wirklicher Zug legt
#: die gemeinten Werkzeuge und die Szene dazu. Gemessen am 26.09.2026 in der
#: Suite (qwen3:14b, Endstand ``2c34c2a7``, 39 Fälle): Median des ersten
#: Schritts 9 061, höchstens 10 886 (Durchsicht 0.5.1). Mit der Grundlast
#: geschätzt, sagte der Prozessorhinweis rund ein Viertel zu wenig Minuten.
TURN_TOKENS: Final = 9061

#: Werkzeugzahl derselben Messung. Der Test macht eine neue Operation zum
#: bewussten Anlass für eine neue Messung, statt die Zeitangabe still altern zu
#: lassen — am 08.09.2026 hat er genau das geleistet und dabei eine
#: Fortschreibung widerlegt, die vier Tage lang plausibel aussah.
#:
#: **Und genau das ist am 10.09.2026 wieder eingetreten.** Die Zahl stand auf
#: 119, das Register hatte 120 — eine Operation war ohne neue Messung
#: dazugekommen. Mit *Wulst anlegen* sind es jetzt 121. Die **Tokenzahl
#: darüber ist damit die von 119 Werkzeugen**: Sie wird hier nicht
#: fortgeschrieben, denn eine hochgerechnete Messung ist keine. Was sie wert
#: ist, sagt der nächste echte Lauf gegen qwen3:14b; bis dahin ist sie eine
#: Untergrenze und als solche benannt.
#:
#: Die funktionale Zählung vom 04.10.2026 enthält genau diese 186 Werkzeuge;
#: Modell, Kontext und Anfragebeleg stehen bei :data:`PROMPT_TOKENS`.
PROMPT_TOOL_COUNT: Final = 187

#: Unter diesem Anteil der Mindestzahl aus :func:`least_tokens` gilt eine
#: Antwort als gekürzt (:func:`prompt_was_cut`). Die Mindestzahl ist schon
#: eine untere Grenze; die zehn Prozent darunter fangen Rundung und eine
#: Vorlage, die weniger Token legt, als sie Zeichen spart.
PROMPT_TRUNCATION_FLOOR: Final = 0.9


@dataclass(frozen=True, slots=True)
class Speed:
    """Was dieser Rechner mit diesem Modell wirklich leistet.

    ``None`` bei :attr:`tokens_per_second` heißt „nicht gemessen" und wird
    nirgends als Aussage verwendet — ein Server, der schweigt, meldet sich
    schon über :attr:`OllamaBackend.available` ab.
    """

    tokens_per_second: float | None = None

    @property
    def on_gpu(self) -> bool | None:
        """Rechnet es auf einer Grafikkarte? ``None`` heißt: nicht gemessen."""
        if self.tokens_per_second is None:
            return None
        return self.tokens_per_second >= GPU_PROMPT_TOKENS_PER_SECOND

    @property
    def prompt_minutes(self) -> float | None:
        """Geschätzte Einlesedauer für den ersten Schritt eines üblichen Zugs
        (:data:`TURN_TOKENS`)."""
        if not self.tokens_per_second:
            return None
        return TURN_TOKENS / self.tokens_per_second / 60.0


def ollama_speed(model: str, url: str | None = None, transport: Transport = post_json) -> Speed:
    """Messen, was der Rechner kann — statt zu erwarten, was Modelle können.

    **Die Erwartung nebenan gilt für einen Rechner mit Grafikkarte.** Ohne eine
    ist es keine andere Geschwindigkeit, sondern eine andere Größenordnung:
    Gemessen auf einer Maschine mit Intel-Arc-Grafik, die Ollama nicht
    anspricht, 7,8 Token je Sekunde beim Einlesen — für den Systemprompt dieser
    Anwendung zweiundvierzig Minuten, **bevor** das erste Wort der Antwort
    beginnt. Der Kunde sieht ein Fenster, das nichts tut, und hält es für einen
    Fehler; es ist eine Eigenschaft seiner Maschine, und die kann ihm niemand
    sagen außer uns.

    Ollama nennt die Zahlen in jeder Antwort mit, also kostet die Messung genau
    einen kurzen Zug und keine Zeitnahme von außen. Gerechnet wird mit dem
    Einlesetempo und nicht mit dem Schreibtempo: Der Prompt ist das, was hier
    groß ist — die Antwort sind ein paar Dutzend Token, der Prompt sind knapp
    zwanzigtausend.
    """
    backend = OllamaBackend(model=model, transport=transport)
    if url is not None:
        backend.url = url
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROBE_REQUEST}],
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"num_ctx": OLLAMA_CONTEXT_TOKENS, "num_predict": 8},
    }
    try:
        # **Über ``ollama_endpoint`` und nicht über die rohe Adresse.** Wer
        # „127.0.0.1:11434" einträgt — die Schreibweise, die Ollama selbst
        # ausgibt —, bekam hier keine Messung und damit ausgerechnet keine
        # Langsam-Warnung: also genau der Kunde nicht, dessen Adresse schon
        # einmal krumm war. Jeder andere Aufruf dieses Moduls geht längst
        # durch dieselbe Normalisierung.
        answer = transport(
            ollama_endpoint(backend.url), {"Content-Type": "application/json"}, payload
        )
    except AppError, OSError, ValueError:
        return Speed()
    _stays_warm(backend)
    count = answer.get("prompt_eval_count")
    duration = answer.get("prompt_eval_duration")
    if not isinstance(count, int) or not isinstance(duration, int | float) or duration <= 0:
        return Speed()
    return Speed(tokens_per_second=count / (float(duration) / 1e9))


def speed_warning(speed: Speed) -> TranslatableText | None:
    """Der Satz zur Messung — oder keiner, wenn es nichts zu sagen gibt.

    Gesagt wird nur, was der Kunde nicht selbst sehen kann, und mit der Zahl
    dabei: „langsam" ist keine Auskunft, „zweiundvierzig Minuten, bis die
    Antwort beginnt" ist eine. Und der Vorschlag gehört dazu (Regel 17) — auf
    einem Rechner ohne nutzbare Karte hilft kein kleineres Modell über die
    Runden, sondern ein Schlüssel.

    Die drei Platzhalter ``rate``, ``tokens`` und ``minutes`` bleiben stehen;
    eingesetzt werden sie von der Oberfläche aus
    :meth:`Speed.tokens_per_second`, :data:`TURN_TOKENS` und
    :meth:`Speed.prompt_minutes`. **``tokens`` ist ein Platzhalter und keine
    Zahl im Satz, weil er sonst altert:** Hier stand „rund 24 000", während
    die Konstante daneben schon gepflegt wurde. Dasselbe Muster wie bei ``AppError.values``
    (§33.1): Der Kern kennt den Satz und die Zahlen, das Zusammensetzen gehört
    dorthin, wo auch die Sprache feststeht.
    """
    if speed.on_gpu is not False or speed.prompt_minutes is None:
        return None
    # **Die Grenze wird gerechnet, nicht behauptet.** Bis zum 25.09.2026
    # sagte der Satz unbedingt, der Auftrag werde nicht fertig — bei 27 293
    # Token stimmte das für jeden Prozessor unter 45 Token je Sekunde. Seit
    # dem Werkzeugangebot ist der Auftrag ein Drittel so lang, und ein
    # schneller Prozessor beginnt binnen Minuten. Er bekommt die Wartezeit
    # ohne Absage.
    if speed.prompt_minutes * 60.0 < LOCAL_TIMEOUT_SECONDS:
        return _(
            "Dieses Modell rechnet auf dem Prozessor, nicht auf der Grafikkarte — "
            "gemessene {rate} Token je Sekunde beim Einlesen. Der zuletzt gemessene "
            "Auftrag dieser Anwendung umfasst rund {tokens} Token; bei diesem Umfang "
            "dauert es hier etwa {minutes} Minuten, bis eine Antwort beginnt. Für "
            "zügige Antworten braucht es eine geeignete Grafikkarte oder einen "
            "Schlüssel für ein gehostetes Modell."
        )
    return _(
        "Dieses Modell rechnet auf dem Prozessor, nicht auf der Grafikkarte — "
        "gemessene {rate} Token je Sekunde beim Einlesen. Der zuletzt gemessene Auftrag "
        "dieser Anwendung umfasst rund {tokens} Token; bei diesem Umfang dauert es "
        "hier etwa {minutes} Minuten, bis eine Antwort überhaupt beginnt. Seitdem "
        "ergänzte Werkzeuge können die Wartezeit verlängern. Das "
        "überschreitet Solidons Zehn-Minuten-Grenze; dieser vollständige "
        "Auftrag kann so nicht abgeschlossen werden. Für zügige Antworten braucht es eine "
        "geeignete "
        "Grafikkarte oder einen Schlüssel für ein gehostetes Modell — alles "
        "außer dem Chat bleibt ohne beides benutzbar."
    )


# --- choosing one -----------------------------------------------------------------


#: Status, mit denen eine Gegenseite sagt: *dieser Schlüssel nicht*.
#:
#: 401 ist die Antwort auf einen falschen Schlüssel, 403 die auf einen
#: gültigen ohne Recht auf dieses Modell. Beide ändern sich nicht dadurch,
#: dass man es noch einmal versucht — anders als 429 oder 5xx, die genau
#: dafür da sind.
AUTH_REFUSED: Final = (401, 403)

#: Backends, deren Zugang die Gegenseite in dieser Sitzung abgelehnt hat.
#:
#: **Warum es das gibt.** ``AnthropicBackend.available`` fragt, ob ein
#: Schlüssel *da* ist — nicht, ob er *gilt*. Ein einziger Tippversuch im
#: Schlüsselfeld genügte deshalb, um ein vollständig eingerichtetes lokales
#: Ollama dauerhaft auszusperren: Anthropic steht in :func:`backends` vorn,
#: gilt mit jedem beliebigen Text als verfügbar und scheitert dann bei jedem
#: Zug. Ein Kunde hat am 24.08.2026 drei Stunden dagegen gearbeitet.
#:
#: Der Merker lebt nur in dieser Sitzung und wird nicht gespeichert: Ein
#: abgelehnter Schlüssel kann beim Anbieter wieder gültig werden, und ein
#: neuer hebt ihn ohnehin auf (:func:`keys.store` ruft :func:`accept_again`).
_rejected: set[str] = set()


def reject(backend_id: str) -> None:
    """Merken, dass dieser Zugang abgelehnt wurde."""
    _rejected.add(backend_id)


def accept_again(backend_id: str = "") -> None:
    """Die Ablehnung zurücknehmen — ohne Namen für alle."""
    if backend_id:
        _rejected.discard(backend_id)
    else:
        _rejected.clear()


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
