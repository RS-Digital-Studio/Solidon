"""Misst, wie lange ein lokales Modell für Solidons Auftrag braucht.

Der Läufer nebenan (``check_local_model.py``) fragt, **ob** ein Modell
Werkzeugaufrufe zurückgibt. Dieser fragt, **wie lange** es dafür braucht —
und beantwortet die drei Fragen, an denen einzelne Messungen bisher
gescheitert sind:

**Rechnet es auf der Karte oder auf dem Prozessor?** Der Unterschied ist keine
Nuance, sondern eine Größenordnung: Am 31.08.2026 brauchte dieselbe Anfrage
mit 106 Werkzeugen **701 Sekunden** auf dem Prozessor und **9,7** auf einer
RTX 4080 — Faktor 72. Die Lage steht in jeder Zeile, gelesen aus ``api/ps``.

**Ist das Modell warm oder kalt?** Ein Kaltstart kostete in derselben Messung
**219 Sekunden** gegen **6,9** warm. Wer beides in einen Mittelwert wirft,
bekommt eine Zahl, die keinen der beiden Fälle beschreibt.

**Und wie sehr streut es?** Eine Zahl aus einem Einzellauf ist nicht die Zahl
aus einer Reihe. Gemessen an anderer Stelle im Projekt: dasselbe Vorhaben
brauchte 9,4 bis 18,5 Sekunden einzeln und 61,8 als siebtes in Folge — Spanne
fast Faktor zwei. Dieser Läufer fährt deshalb mehrere Züge und weist Median
**und** Spanne aus, nie einen Mittelwert allein.

**Er räumt hinter sich auf.** Warmhalten ist der Sinn der Sache, aber 15 GB,
die nach dem Messen liegen bleiben, machen den Rechner zäh — am 31.08.2026
war genau das ein Teil eines Nachmittags, an dem nichts mehr voranging. Am
Ende steht deshalb ein ``keep_alive: 0``, auch wenn der Lauf scheitert.

Er ist **kein** Teil der Suite: Er braucht ein laufendes Ollama, lädt Modelle
in den Speicher und dauert Minuten.

``--count-tokens`` zählt stattdessen genau einen vollständigen Auftrag ohne
Zeit-, Karten- oder Warmmessung. Die JSON-Auskunft nennt Modell, Kontext,
Werkzeugzahl und den SHA-256 der tatsächlich gesendeten Anfrage. Eine
erkennbare Kürzung oder eine unvollständige Antwort liefert keinen Zählwert.

**Gezählt wird die Grundlast, wie die Anwendung sie schickt** — der kompakte
Systemprompt und das Werkzeugangebot eines lokalen Zugs
(``agent/offer.py``) zu einer Frage, die keine Operation meint: jede
Operation angekündigt, keine ausführlich. Was ein wirklicher Zug dazulegt,
sind die gemeinten Werkzeuge (höchstens ``DETAILED_LIMIT``), der Steckbrief
und der Verlauf.

``--context`` öffnet ein anderes Fenster als die Vorgabe — für ein Modell,
dessen Grafikspeicher mehr trägt.

    python tools/measure_local_model.py
    python tools/measure_local_model.py --model qwen3:14b --runs 5
    python tools/measure_local_model.py --tools 0 --runs 3
    python tools/measure_local_model.py --count-tokens
    python tools/measure_local_model.py --count-tokens --model qwen3.5:9b --context 65536
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.agent.offer import ToolOffer
from app.core.agent.prompt import system_prompt
from app.core.backends.llm import (
    DEFAULT_OLLAMA_MODEL,
    GPU_PROMPT_TOKENS_PER_SECOND,
    OLLAMA_CONTEXT_TOKENS,
    ollama_endpoint,
    prompt_was_cut,
    request_length,
)
from app.core.bootstrap import load_operations
from app.core.discover import opener_for
from app.core.http import apply_header_deadline, deadline_after, read_limited
from app.core.json_boundary import StrictJsonError
from app.core.json_boundary import loads as load_json

#: Wie lange eine einzelne Anfrage höchstens dauern darf.
#:
#: Großzügig, weil der Prozessorfall echte elf Minuten braucht und ein zu
#: knappes Limit genau die Messung abschnitte, für die dieser Läufer da ist.
REQUEST_TIMEOUT_SECONDS = 1800

#: Wie lange zwischen den Zügen warmgehalten wird.
#:
#: Nur so lange, wie der Lauf dauert — länger als das Sicherheitsnetz des
#: Produkts. Ein Messwerkzeug, das warmhält, gibt den Speicher am Ende zurück.
MEASURE_KEEP_ALIVE = "10m"
MAX_STATE_RESPONSE_BYTES = 1024 * 1024
MAX_CHAT_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_UNLOAD_RESPONSE_BYTES = 64 * 1024

#: Die Frage des Zählwegs. Sie meint keine Operation — gezählt wird damit die
#: Grundlast, nicht ein zufällig gemeintes Werkzeug.
QUESTION = "Hallo."


def base_tools() -> list[dict[str, object]]:
    """Das Werkzeugangebot eines lokalen Zugs zu :data:`QUESTION`.

    Dieselbe Rechnung wie in der Sitzung (``AgentSession._offer_for``), nicht
    eine Kopie: Was die Anwendung schickt, zählt die Messung.
    """
    from app.core.registry import REGISTRY

    return list(ToolOffer.for_turn(REGISTRY, [QUESTION]).schemas())


@dataclass(frozen=True, slots=True)
class Turn:
    """Ein einzelner Zug: was hineinging, was zurückkam, wie lange es dauerte."""

    seconds: float
    prompt_tokens: int
    on_gpu: bool | None
    vram_share: int | None

    @property
    def tokens_per_second(self) -> float:
        return self.prompt_tokens / self.seconds if self.seconds else 0.0


def _answer_json(answer: object, *, limit: int, timeout: float) -> dict[str, object]:
    """Liest eine Ollama-Antwort mit Gesamt-, Byte- und Strukturgrenze."""
    raw = read_limited(
        answer,  # type: ignore[arg-type]
        limit=limit,
        deadline=deadline_after(timeout),
    )
    value = load_json(raw, max_bytes=limit)
    if not isinstance(value, dict):
        raise StrictJsonError("Ollama-Antwort ist kein Objekt")
    return dict(value)


def model_state() -> tuple[bool | None, int | None]:
    """Wo das Modell gerade liegt — ``(ganz im VRAM?, Anteil in Prozent)``.

    ``(None, None)``, wenn ``api/ps`` nicht antwortet oder nichts geladen ist.
    Das ist keine Aussage über die Lage, sondern das Eingeständnis, keine zu
    haben — und es steht als solches in der Ausgabe.
    """
    try:
        # Über denselben Weg wie die Anwendung: ohne Proxy für einen lokalen
        # Dienst, und mit der Frist auch über Statuszeile und Kopfzeilen.
        opener = opener_for("http://localhost:11434/api/ps")
        apply_header_deadline(opener, deadline_after(15))
        with opener.open("http://localhost:11434/api/ps", timeout=15) as answer:
            raw_models = _answer_json(
                answer,
                limit=MAX_STATE_RESPONSE_BYTES,
                timeout=15,
            ).get("models")
    except urllib.error.URLError, OSError, ValueError, TimeoutError:
        return None, None
    if not isinstance(raw_models, list) or not raw_models or not isinstance(raw_models[0], dict):
        return None, None
    entry = raw_models[0]
    raw_size = entry.get("size")
    raw_vram = entry.get("size_vram")
    if (
        not isinstance(raw_size, int)
        or isinstance(raw_size, bool)
        or not isinstance(raw_vram, int)
        or isinstance(raw_vram, bool)
    ):
        return None, None
    size = raw_size
    vram = raw_vram
    if not size:
        return None, None
    share = 100 * vram // size
    return share >= 99, share


def _payload(
    model: str,
    tools: list[dict[str, object]],
    *,
    keep_alive: str | int,
    window: int = OLLAMA_CONTEXT_TOKENS,
) -> bytes:
    """Dieselbe vollständige Anfrage für Tokenzählung und Zeitmessung."""
    return json.dumps(
        {
            "model": model,
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"temperature": 0.0, "num_ctx": window, "num_predict": 1},
            "messages": [
                {"role": "system", "content": system_prompt(compact=True)},
                {"role": "user", "content": QUESTION},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": entry["name"],
                        "description": entry.get("description", ""),
                        "parameters": entry.get("input_schema", {"type": "object"}),
                    },
                }
                for entry in tools
            ],
        }
    ).encode("utf-8")


def _chat(payload: bytes) -> dict[str, object]:
    """Sendet eine Anfrage mit denselben Fristen und Antwortgrenzen wie der Messweg."""
    request = urllib.request.Request(
        ollama_endpoint(None),
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    opener = opener_for(ollama_endpoint(None))
    apply_header_deadline(opener, deadline_after(REQUEST_TIMEOUT_SECONDS))
    with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as answer:
        return _answer_json(
            answer,
            limit=MAX_CHAT_RESPONSE_BYTES,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )


def _count_tokens(
    model: str, tools: list[dict[str, object]], window: int = OLLAMA_CONTEXT_TOKENS
) -> dict[str, object]:
    """Zählt einen Auftrag; fehlende oder gekürzte Auskunft ist keine neue Referenz."""
    payload = _payload(model, tools, keep_alive=0, window=window)
    data = _chat(payload)
    counted, produced = data.get("prompt_eval_count"), data.get("eval_count")
    if (
        data.get("done") is not True
        or data.get("model") != model
        or "error" in data
        or not isinstance(counted, int)
        or isinstance(counted, bool)
        or counted <= 0
        or not isinstance(produced, int)
        or isinstance(produced, bool)
        or not 0 <= produced <= 1
    ):
        raise ValueError("Ollama liefert keine vollständige Tokenauskunft. Erneut zählen.")
    if prompt_was_cut(counted, request_length(json.loads(payload)), window):
        raise ValueError(
            "Ollama hat den Auftrag offenbar gekürzt. Kontext und Modell prüfen, dann neu zählen."
        )
    if counted + produced >= window:
        raise ValueError(
            "Ollamas Kontextfenster ist voll. Kontext und Modell prüfen, dann neu zählen."
        )
    return {
        "model": model,
        "num_ctx": window,
        "tool_count": len(tools),
        "prompt_eval_count": counted,
        "eval_count": produced,
        "request_sha256": hashlib.sha256(payload).hexdigest(),
    }


def _ask(
    model: str, tools: list[dict[str, object]], window: int = OLLAMA_CONTEXT_TOKENS
) -> Turn | None:
    """Ein Zug. ``None``, wenn die Gegenseite nicht antwortet."""
    payload = _payload(model, tools, keep_alive=MEASURE_KEEP_ALIVE, window=window)
    started = time.monotonic()
    try:
        data = _chat(payload)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as error:
        print(f"    Abbruch nach {time.monotonic() - started:.0f} s — {type(error).__name__}")
        return None
    seconds = time.monotonic() - started
    on_gpu, share = model_state()
    raw_tokens = data.get("prompt_eval_count")
    prompt_tokens = (
        raw_tokens if isinstance(raw_tokens, int) and not isinstance(raw_tokens, bool) else 0
    )
    return Turn(
        seconds=seconds,
        prompt_tokens=prompt_tokens,
        on_gpu=on_gpu,
        vram_share=share,
    )


def unload(model: str) -> None:
    """Den Speicher zurückgeben — auch wenn der Lauf gescheitert ist."""
    request = urllib.request.Request(
        ollama_endpoint(None),
        data=json.dumps({"model": model, "keep_alive": 0, "messages": []}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    opener = opener_for(ollama_endpoint(None))
    apply_header_deadline(opener, deadline_after(120))
    try:
        with opener.open(request, timeout=120) as answer:
            reason = _answer_json(
                answer,
                limit=MAX_UNLOAD_RESPONSE_BYTES,
                timeout=120,
            ).get("done_reason")
        print(f"  entladen ({reason})")
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as error:
        print(f"  ENTLADEN GESCHEITERT ({type(error).__name__}) — von Hand nachholen:")
        print('    curl http://localhost:11434/api/chat -d \'{"model":"…","keep_alive":0}\'')


def _report(label: str, turns: list[Turn]) -> None:
    """Median und Spanne — nie ein Mittelwert allein.

    **Die Rate eines warmen Zuges ist keine Rechenleistung.** Ollama hält den
    verarbeiteten Auftrag im Zwischenspeicher, und weil Systemprompt und
    Werkzeugschemata von Zug zu Zug gleich bleiben, wird beim zweiten Mal
    nichts davon neu eingelesen — ``prompt_eval_count`` meldet die Token
    trotzdem. Gemessen am 31.08.2026: 12,5 Sekunden kalt gegen 2,2 warm, und
    daraus gerechnet 1 567 gegen 8 864 Token je Sekunde. Die zweite Zahl
    beschreibt einen Zwischenspeicher, nicht eine Karte.

    Das ist **kein Messfehler, sondern der Kundenfall**: Auch im Chat bleibt
    der Auftrag gleich und nur die Frage ändert sich. Die Zahl steht deshalb
    da — mit dem Wort, das sie einordnet.
    """
    if not turns:
        print(f"  {label:12} —")
        return
    seconds = sorted(entry.seconds for entry in turns)
    rate = statistics.median(entry.tokens_per_second for entry in turns)
    last = turns[-1]
    where = (
        "ungemessen"
        if last.on_gpu is None
        else f"{'Karte' if last.on_gpu else 'Prozessor'} ({last.vram_share} % im VRAM)"
    )
    spread = (
        f"{seconds[0]:.1f} bis {seconds[-1]:.1f} s" if len(seconds) > 1 else f"{seconds[0]:.1f} s"
    )
    # „einlesend" gegen „aus dem Zwischenspeicher": Beim kalten Zug wird der
    # Auftrag wirklich verarbeitet, beim warmen liegt er schon da.
    kind = "einlesend" if label.startswith("kalt") else "gepuffert"
    print(
        f"  {label:12} Median {statistics.median(seconds):7.1f} s | Spanne {spread:>16} | "
        f"{rate:7.1f} Token/s {kind} | {turns[0].prompt_tokens} Token | {where}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_OLLAMA_MODEL)
    parser.add_argument(
        "--count-tokens",
        action="store_true",
        help="Einen vollständigen Auftrag zählen, ohne Zeit- oder Geschwindigkeitsmessung",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Wie viele warme Züge nach dem Kaltstart (Vorgabe 3)",
    )
    parser.add_argument(
        "--tools",
        type=int,
        default=-1,
        help="Wie viele Werkzeuge; -1 heißt alle, 0 heißt keine (Nullpunkt)",
    )
    parser.add_argument(
        "--context",
        type=int,
        default=OLLAMA_CONTEXT_TOKENS,
        help=f"Kontextfenster in Token (Vorgabe {OLLAMA_CONTEXT_TOKENS})",
    )
    arguments = parser.parse_args()
    if arguments.count_tokens and arguments.tools != -1:
        parser.error("--count-tokens verlangt alle Werkzeuge; --tools weglassen.")

    # Ohne das ist das Register leer und das Angebot enthält nur die
    # Zusatzwerkzeuge — eine Messung gegen eine Nutzlast, die es nicht gibt.
    load_operations()
    schemas = base_tools()
    if arguments.tools >= 0:
        schemas = schemas[: arguments.tools]

    if arguments.count_tokens:
        try:
            counted = _count_tokens(arguments.model, schemas, arguments.context)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as error:
            print(f"Tokenzählung nicht abgeschlossen: {error}", file=sys.stderr)
            print("Ollama und das installierte Modell prüfen, dann erneut zählen.", file=sys.stderr)
            return 1
        print(json.dumps(counted, ensure_ascii=False, sort_keys=True))
        return 0

    print(f"{arguments.model} — {len(schemas)} Werkzeuge, num_ctx {arguments.context}")
    # Kein Anführungszeichen im f-String: Das deutsche Schlusszeichen beendet
    # ihn, und die Fehlermeldung zeigt auf eine ganz andere Stelle.
    print(f"  Ab {GPU_PROMPT_TOKENS_PER_SECOND:.0f} Token/s gilt es als Karte\n")

    try:
        # **Kalt zuerst, und kalt heißt wirklich kalt.** Ein Kaltstart nach
        # einem warmen Lauf misst nichts — deshalb wird vorher entladen.
        unload(arguments.model)
        print("  Kaltstart …")
        cold = _ask(arguments.model, schemas, arguments.context)
        warm = []
        for number in range(arguments.runs):
            print(f"  warmer Zug {number + 1}/{arguments.runs} …")
            turn = _ask(arguments.model, schemas, arguments.context)
            if turn is not None:
                warm.append(turn)
    finally:
        unload(arguments.model)

    print()
    _report("kalt", [cold] if cold else [])
    _report("warm", warm)
    if cold and warm:
        gain = cold.seconds - statistics.median(entry.seconds for entry in warm)
        print(f"\n  Das Warmhalten spart {gain:.0f} Sekunden je Zug nach einer Pause.")
        print("  Der warme Wert ist gepuffert: Auftrag und Werkzeuge bleiben gleich,")
        print("  nur die Frage ändert sich — im Chat ist das genauso.")
    return 0 if warm else 1


if __name__ == "__main__":
    raise SystemExit(main())
