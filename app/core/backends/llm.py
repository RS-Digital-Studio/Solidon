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
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar, Final, Literal, Protocol

from app.core.backends import keys
from app.core.discover import PROBE_SECONDS, UNUSABLE_ADDRESS, opener_for
from app.core.errors import CANCEL, OPEN_SETTINGS, RETRY, AppError, ExternalToolError
from app.core.log import get_logger
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
#: Zehn Minuten, und die Begründung ist dieselbe wie bei ComfyUI: **Ein
#: Zeitlimit gilt dem Hängen, nicht der Langsamkeit.** Auf Intel- und
#: AMD-Grafik sind 7,8 Token je Sekunde gemessen worden; wer dort rechnet,
#: soll ein Ergebnis bekommen und keine Absage.
LOCAL_TIMEOUT_SECONDS = 600.0


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
    body = json.dumps(payload).encode("utf-8")
    # Die Adresse kommt aus dem Backend, nie aus etwas, das das Modell gesagt hat.
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json", **headers}
    )
    try:
        with opener_for(url).open(request, timeout=timeout) as answer:
            return _as_object(answer.read(), url)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise BackendUnavailable(status=error.code, detail=detail) from error
    except urllib.error.URLError as error:
        raise BackendUnavailable(detail=str(error.reason)) from error
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
        raise BackendUnavailable(detail=str(error)) from error


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
        loaded = json.loads(text)
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


class BackendUnavailable(ExternalToolError):
    """Das Modell war nicht erreichbar oder hat abgelehnt.

    Ein ``ExternalToolError``, kein nackter ``AppError`` (§33.1): Der
    häufigste Auslöser ist ein nicht laufendes Ollama oder ein abgelaufener
    Schlüssel — dort helfen „Einstellungen öffnen" und „Erneut versuchen",
    nicht das geerbte „Abbrechen" allein.
    """

    default_title = _("Das Sprachmodell hat nicht geantwortet.")

    def __init__(self, status: int | None = None, detail: str = "", provider: str = "") -> None:
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
            values["url"] = url
        if excerpt:
            values["answer"] = " ".join(excerpt.split())[: self.EXCERPT_CHARS]
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
    except (ValueError, OverflowError):
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
            value = json.loads(value)
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
#: Gemessen wird das mit **allen** Werkzeugen, die der Agent anbietet — das
#: sind die sechsundneunzig aus dem geladenen Register, rund 110 KB Schema,
#: und nicht die elf Zusatzwerkzeuge allein. Der Unterschied entscheidet die
#: Wahl und hat sie einmal falsch entschieden: mit den damals sieben
#: Zusatzschemata traf ``llama3.1:8b`` fünf von fünf, mit dem vollen Register
#: (dreiundachtzig zu der Zeit) zwei. Es kennt die
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
#: Modell, das den Auftrag kennt, rät nicht herum. Es kostet Speicher: mit
#: 32768 belegt ``qwen3:14b`` 14 GB und bleibt damit vollständig auf einer
#: 16-GB-Karte. Wer ein größeres Modell fährt, zahlt hier zuerst.
#:
#: Die Reihe fuhr 84 Schemata. Bei 85 nachgemessen sind es 26 601 Token für
#: Systemprompt und alle Werkzeuge, 19 249 für den kompakten Satz, den dieser
#: Weg fährt (:func:`~app.core.agent.tools.tool_schemas` mit ``compact``) —
#: beide kamen ganz an. Das Fenster trägt also weiter; wachsen kann es kaum,
#: ohne die Karte zu verlassen. Was wächst, ist die Werkzeugliste: wer sie
#: ändert, misst ``prompt_eval_count`` nach.
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

        try:
            answer = self.transport(ollama_endpoint(self.url), {}, payload)
        except BackendUnavailable as error:
            # Kein ``reject``: Ollama hat keinen Schlüssel, den man falsch
            # eintragen könnte. Der Name gehört trotzdem in die Meldung — er
            # ist die Antwort auf „welches Modell denn?".
            error.provider = error.provider or self.id
            error.values.setdefault("provider", self.id)
            raise
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

Fetch = Callable[[str], dict[str, Any]]
"""``url -> answer``. Austauschbar, damit die Prüfung ohne Netz testbar ist."""


def _get_json(url: str) -> dict[str, Any]:
    """Ein GET, JSON heraus — das Gegenstück zu :func:`post_json` für die
    Modell-Liste von Ollama."""
    request = urllib.request.Request(url)
    with opener_for(url).open(request, timeout=TAGS_TIMEOUT_SECONDS) as answer:
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


#: Modelle, die sich hier bewährt haben — Name, Größe des Downloads, und was
#: die Messung ergeben hat. Die Namen stehen als Konstanten hier und kommen
#: nie aus einer Antwort: an ihnen hängt ein Download.
#:
#: **Warum diese Liste überhaupt existiert.** Wer Ollama über den Knopf in der
#: Liste der zusätzlichen Programme installiert hatte, stand danach vor einem
#: Chat, der weiterhin nicht ging — Ollama bringt kein Modell mit, und der
#: einzige Hinweis darauf war ein Satz mit „ollama pull" darin. Ein Modellname
#: allein hilft dabei nicht: Zwischen 5 und 9 GB Download liegt eine
#: Entscheidung, und ob es Werkzeuge aufruft, ist die eigentliche Frage.
OLLAMA_SUGGESTIONS: Final = (
    (
        "qwen3:14b",
        9.3,
        _(
            "Bewährt: vier von fünf Werkzeugaufrufen, rund 15 Sekunden je Schritt. "
            "Belegt 14 GB Grafikspeicher."
        ),
    ),
    (
        "gpt-oss:20b",
        13.8,
        _("Am schnellsten: rund 6 Sekunden je Schritt, trifft drei von fünf."),
    ),
    ("qwen3:8b", 5.2, _("Kleiner und schneller, trifft seltener. Für kurze Anweisungen.")),
    (
        "qwen3:30b-a3b",
        18.6,
        _("Trifft wie das 14B, braucht aber die doppelte Zeit und den doppelten Platz."),
    ),
    (
        "llama3.1:8b",
        4.9,
        _("Zwei von fünf Werkzeugaufrufen — nur, wenn die anderen nicht laufen."),
    ),
    (
        "qwen2.5-coder:14b",
        9.0,
        _(
            "Ruft in dieser Messung kein einziges Werkzeug auf — trotz vierzehn "
            "Milliarden Parametern."
        ),
    ),
    (
        "mistral-nemo:latest",
        7.1,
        _("Ruft keine Werkzeuge auf, sondern schreibt darüber. Für Solidon unbrauchbar."),
    ),
)


#: Was zu einem installierten Modell danebensteht, wenn es in
#: :data:`OLLAMA_SUGGESTIONS` bekannt ist.
#:
#: **Die Zahl entscheidet die Wahl, und sie stand nur bei den empfohlenen.**
#: Ein Kunde mit drei installierten Modellen sah drei nackte Namen; dass
#: ``mistral-nemo`` in dieser Messung null von fünf Aufrufen schaffte, war
#: nirgends zu lesen. Ein Modell, das die Aufrufe als Fließtext ausgibt, sieht
#: im Chat aus, als arbeite es — genau deshalb gibt es
#: ``tools/check_local_model.py``, und genau deshalb gehört sein Ergebnis in
#: die Auswahl und nicht nur in einen Docstring.
def known_model_note(name: str) -> TranslatableText | None:
    """Der Satz zu einem Modellnamen, oder ``None`` für ein unbekanntes.

    Verglichen wird ohne Kennzeichnung: Ollama führt dasselbe Modell als
    ``mistral-nemo`` und als ``mistral-nemo:latest``, und der Kunde hat es
    einmal installiert, nicht zweimal.
    """

    def bare(entry: str) -> str:
        return entry.removesuffix(":latest")

    wanted = bare(name)
    for entry, _gigabytes, note in OLLAMA_SUGGESTIONS:
        if bare(entry) == wanted:
            return note
    return None


#: Ein Download von mehreren Gigabyte. Die Grenze ist großzügig, weil eine
#: langsame Leitung sonst mitten im Modell aufgibt.
PULL_TIMEOUT_SECONDS = 7200.0

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
    try:
        # **Der Bau der Anfrage steht mit im ``try``.** ``Request()`` selbst
        # wirft einen ``ValueError``, sobald die Adresse kein Schema trägt, das
        # es kennt — gemessen an ``://kaputt``. Davor lag er eine Zeile
        # oberhalb, und dort fing ihn nichts.
        request = urllib.request.Request(
            address, data=body, headers={"Content-Type": "application/json"}
        )
        with opener_for(address).open(request, timeout=PULL_TIMEOUT_SECONDS) as answer:
            for raw in answer:
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
                    entry = dict(json.loads(line))
                except ValueError:
                    continue
                if entry.get("error"):
                    return _("Ollama hat den Namen nicht angenommen.")
                if progress is not None:
                    progress(str(entry.get("status", "")), _share(entry))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:200]
        _log.warning("pull of %s refused: %s", model, detail)
        return _("Ollama hat den Namen nicht angenommen.")
    except UNUSABLE_ADDRESS:
        return _("Ollama hat nicht geantwortet — läuft es noch?")
    return None


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
    return _(
        "Das lokale Modell hat weniger als 7 Milliarden Parameter — "
        "Werkzeugaufrufe scheitern damit erfahrungsgemäß. Bewährt hat sich "
        "qwen3:14b; das braucht eine Grafikkarte mit 16 GB Speicher."
    )


def local_model_expectation() -> TranslatableText:
    """Was ein lokales Modell hier wirklich leistet — gemessen, nicht geschätzt.

    Der Satz gehört an die Stelle, an der jemand Ollama einträgt. Ohne ihn
    erlebt er das Ergebnis als Fehler der Anwendung: ein Zug, der zwei Minuten
    braucht und dann das falsche Werkzeug ruft, sieht nach einem Fehler aus und
    ist eine Eigenschaft des Modells.

    Die Zahlen stammen aus ``tools/check_local_model.py`` gegen die 88
    Werkzeuge dieser Anwendung, nicht aus einer Bestenliste.
    """
    return _(
        "Lokale Modelle sind langsamer und ungenauer als ein gehostetes: "
        "qwen3:14b hat in der Messung drei von fünf Werkzeugaufrufen richtig "
        "getroffen und für einen davon zwei Minuten gebraucht. Für kurze "
        "Anweisungen reicht das; für lange Züge lohnt ein Schlüssel."
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


#: Wie viele Token je Sekunde eine Grafikkarte beim Einlesen mindestens
#: schafft. Der Wert trennt nicht scharf zwischen Karten, sondern zwischen
#: *Karte* und *Prozessor*: Gemessen liegt eine 16-GB-Karte bei einigen
#: hundert bis über tausend, und ein Prozessor bei 8 bis 30. Alles unter dieser
#: Marke ist Prozessorbetrieb, gleich welche Karte im Rechner steckt.
GPU_PROMPT_TOKENS_PER_SECOND: Final = 100.0

#: Wie groß der Systemprompt dieser Anwendung ist — der kompakte Werkzeugsatz,
#: den der Ollama-Pfad fährt. Gemessen, nicht geschätzt (siehe
#: :data:`OLLAMA_CONTEXT_TOKENS`).
PROMPT_TOKENS: Final = 19249


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
        """Wie lange dieser Rechner braucht, bis die erste Antwort *beginnt*."""
        if not self.tokens_per_second:
            return None
        return PROMPT_TOKENS / self.tokens_per_second / 60.0


def ollama_speed(model: str, url: str | None = None, transport: Transport = post_json) -> Speed:
    """Messen, was der Rechner kann — statt zu erwarten, was Modelle können.

    **Die Erwartung nebenan gilt für einen Rechner mit Grafikkarte.** Ohne eine
    ist es keine andere Geschwindigkeit, sondern eine andere Größenordnung:
    Gemessen auf einer Maschine mit Intel-Arc-Grafik, die Ollama nicht
    anspricht, 8,4 Token je Sekunde beim Einlesen — für den Systemprompt dieser
    Anwendung achtunddreißig Minuten, **bevor** das erste Wort der Antwort
    beginnt. Der Kunde sieht ein Fenster, das nichts tut, und hält es für einen
    Fehler; es ist eine Eigenschaft seiner Maschine, und die kann ihm niemand
    sagen außer uns.

    Ollama nennt die Zahlen in jeder Antwort mit, also kostet die Messung genau
    einen kurzen Zug und keine Zeitnahme von außen. Gerechnet wird mit dem
    Einlesetempo und nicht mit dem Schreibtempo: Der Prompt ist das, was hier
    groß ist — die Antwort sind ein paar Dutzend Token, der Prompt sind
    neunzehntausend.
    """
    backend = OllamaBackend(model=model, transport=transport)
    if url is not None:
        backend.url = url
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROBE_REQUEST}],
        "stream": False,
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
    except (AppError, OSError, ValueError):
        return Speed()
    count = answer.get("prompt_eval_count")
    duration = answer.get("prompt_eval_duration")
    if not isinstance(count, int) or not isinstance(duration, int | float) or duration <= 0:
        return Speed()
    return Speed(tokens_per_second=count / (float(duration) / 1e9))


def speed_warning(speed: Speed) -> TranslatableText | None:
    """Der Satz zur Messung — oder keiner, wenn es nichts zu sagen gibt.

    Gesagt wird nur, was der Kunde nicht selbst sehen kann, und mit der Zahl
    dabei: „langsam" ist keine Auskunft, „einundvierzig Minuten, bis die
    Antwort beginnt" ist eine. Und der Vorschlag gehört dazu (Regel 17) — auf
    einem Rechner ohne nutzbare Karte hilft kein kleineres Modell über die
    Runden, sondern ein Schlüssel.

    Die zwei Platzhalter ``rate`` und ``minutes`` bleiben stehen; eingesetzt
    werden sie von der Oberfläche aus :meth:`Speed.tokens_per_second` und
    :meth:`Speed.prompt_minutes`. Dasselbe Muster wie bei ``AppError.values``
    (§33.1): Der Kern kennt den Satz und die Zahlen, das Zusammensetzen gehört
    dorthin, wo auch die Sprache feststeht.
    """
    if speed.on_gpu is not False or speed.prompt_minutes is None:
        return None
    return _(
        "Dieses Modell rechnet auf dem Prozessor, nicht auf der Grafikkarte — "
        "gemessene {rate} Token je Sekunde beim Einlesen. Der Auftrag dieser "
        "Anwendung ist rund 24 000 Token lang, es dauert hier also etwa "
        "{minutes} Minuten, bis eine Antwort überhaupt beginnt. Ein kleineres "
        "Modell ändert daran wenig; für zügige Antworten braucht es einen "
        "Schlüssel für ein gehostetes Modell — alles außer dem Chat bleibt "
        "ohne beides benutzbar."
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
