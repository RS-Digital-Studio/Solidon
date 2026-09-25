"""Prüft, ob ein lokales Modell Solidons Werkzeuge wirklich aufruft.

Die Agenten-Suite nebenan misst die Güte der Antworten. Dieser Läufer misst die
Stufe davor, ohne die keine Antwort etwas nützt: **kommt ein strukturierter
Werkzeugaufruf zurück, oder Prosa?** Ein Modell, das die Aufrufe als Fließtext
ausgibt, sieht im Chat aus, als arbeite es — und führt nichts aus.

Weder Größe noch die von Ollama gemeldete Fähigkeit beantworten das:
``qwen2.5-coder:14b`` hat 14,8 Milliarden Parameter, meldet ``tools``, und traf
in dieser Messung null von fünf. Deshalb gibt es diesen Läufer.

Er ist **kein** Teil der Suite: er braucht ein laufendes Ollama, lädt Modelle in
den Speicher und dauert Minuten.

    python tools/check_local_model.py
    python tools/check_local_model.py llama3.1:8b qwen3:14b
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.agent.offer import ToolOffer
from app.core.agent.prompt import system_prompt
from app.core.backends.llm import (
    DEFAULT_OLLAMA_MODEL,
    Message,
    OllamaBackend,
)
from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from tools.measure_local_model import model_state, unload

#: Was das Modell in jedem Fall über die Szene erfährt — ein Körper mit
#: Kennung, damit eine Operation überhaupt ein Ziel hat, und ein Verlauf mit
#: Transaktionen, damit es etwas zurückzunehmen gibt. Ohne ihn antwortet ein
#: gutes Modell auf „Nimm die letzte Änderung zurück" mit Recht, es gebe
#: keine (gemessen am 25.09.2026 an qwen3.5:9b). Der volle Steckbrief gehört
#: der Agenten-Suite; hier geht es um den Aufruf, nicht um die Szene.
SCENE = (
    "Szene: obj_1, Platte 80 x 60 x 6 mm, liegt auf dem Druckbett.\n"
    'Verlauf: t1 "Laden" (load, Nutzer), t2 "Verschieben" (translate_object(x=10), Nutzer)'
)

#: Anfrage und die Werkzeuge, von denen eines sie erfüllt. Die fünfte ist mit
#: Absicht mehrdeutig — „Fragen vor Raten" ist eine der drei Vorrangregeln,
#: und ein Modell, das hier rät, ist für den Agenten unbrauchbar. Die letzten
#: drei verlangen eine **Operation**: Die fünf davor sind Zusatzwerkzeuge, die
#: immer mit allen Feldern dastehen, und prüften das Werkzeugangebot
#: (``agent/offer.py``) nicht.
CASES: tuple[tuple[str, frozenset[str]], ...] = (
    ("Lege einen Projektparameter laenge mit dem Wert 20 mm an.", frozenset({"add_parameter"})),
    ("Zeig mir den Prüfbericht.", frozenset({"read_report"})),
    ("Suche einen Baustein für eine M3-Schraube.", frozenset({"find_part"})),
    ("Nimm die letzte Änderung zurück.", frozenset({"undo_transaction"})),
    ("Mach das Ding etwas größer.", frozenset({"ask_user"})),
    ("Verschieb obj_1 um 10 mm nach rechts.", frozenset({"translate_object"})),
    ("Dreh obj_1 um 90 Grad um die Z-Achse.", frozenset({"rotate_object"})),
    (
        "Bohr in die Mitte der Oberseite von obj_1 ein Loch mit 5 mm Durchmesser.",
        frozenset({"drill_hole", "drill_brep_hole"}),
    ),
)


def check(model: str) -> bool:
    """Ein Modell durch alle Fälle. ``True``, wenn jeder Aufruf saß."""
    backend = OllamaBackend(model=model)
    # **Wie die Anwendung es Ollama schickt** (``session.py``): der kompakte
    # Systemprompt und das Werkzeugangebot zu genau dieser Frage. Mit dem
    # vollen Schema (258 KB) passte der Prompt nie in das Fenster von 32 768
    # Token, Ollama kürzte ihn still, und dieses Werkzeug maß über Wochen ein
    # halbes Schema — aufgefallen am 14.09.2026, als ``BackendPromptTruncated``
    # zum ersten Mal anschlug (RM-173).
    system = system_prompt(compact=True)
    structured = 0
    hits = 0
    times: list[float] = []
    lines: list[str] = []

    for question, wanted in CASES:
        label = "/".join(sorted(wanted))
        messages = [
            Message(role="system", content=system),
            Message(role="user", content=SCENE),
            Message(role="user", content=question),
        ]
        schemas = ToolOffer.for_turn(REGISTRY, [question]).schemas()
        started = time.perf_counter()
        try:
            reply = backend.complete(messages, tools=schemas)
        except Exception as problem:  # eine Messung, kein Produktionsweg
            lines.append(f"    {label:18} Fehler  {type(problem).__name__}: {problem}")
            continue
        seconds = time.perf_counter() - started
        times.append(seconds)

        if not reply.wants_tools:
            lines.append(f"    {label:18} Prosa  {seconds:5.1f}s  {reply.text[:58]!r}")
            continue
        structured += 1
        names = [call.name for call in reply.tool_calls]
        right = bool(wanted & set(names))
        hits += 1 if right else 0
        verdict = "ok    " if right else "falsch"
        lines.append(
            f"    {label:18} {verdict} {seconds:5.1f}s  {reply.input_tokens:6} Token  {names}"
        )

    total = len(CASES)
    # **Quote und Zeit aus demselben Lauf.** Zwei Tabellen über zwei Zustände
    # der Maschine wären nicht vergleichbar: Ein Modell mit guter Quote in
    # 700 Sekunden ist für den Kunden schlechter als eines mit knapper Quote
    # in zehn, und diese Abwägung darf nicht aus getrennten Läufen entstehen.
    on_gpu, share = model_state()
    where = (
        "ungemessen"
        if on_gpu is None
        else f"{'Karte' if on_gpu else 'Prozessor'} ({share} % im VRAM)"
    )
    # **Erst messen, dann entladen.** Die erste Fassung räumte vor der
    # Abfrage auf und meldete deshalb bei jedem Modell „ungemessen" — das
    # Aufräumen ist richtig, es stand nur an der falschen Stelle.
    unload(model)
    middle = statistics.median(times) if times else 0.0
    print(f"  {model}")
    print(
        f"    strukturiert {structured}/{total} · richtig {hits}/{total}"
        f" · Median {middle:.1f} s je Anfrage · {where}"
    )
    for line in lines:
        print(line)
    print()
    return hits == total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "models",
        nargs="*",
        default=[DEFAULT_OLLAMA_MODEL],
        help=f"Modelle, die geprüft werden. Vorgabe: {DEFAULT_OLLAMA_MODEL}",
    )
    chosen = parser.parse_args().models

    if not OllamaBackend().available:
        print("Ollama antwortet nicht — „ollama serve“ starten, dann noch einmal.")
        return 2

    # Ohne das stünden hier elf Werkzeuge statt sechsundneunzig, und die
    # Messung sagte etwas über eine Lage aus, in der der Agent nie ist. Genau
    # daran hat diese Prüfung beim ersten Anlauf vorbeigemessen: dasselbe
    # Modell traf mit den damals sieben Zusatzschemata fünf von fünf und fiel
    # mit dem vollständigen Register in Fließtext.
    load_operations()
    schemas = ToolOffer.for_turn(REGISTRY, ["Hallo."]).schemas()
    print(f"Werkzeuge: {len(schemas)} ({len(json.dumps(schemas)) // 1024} KB Grundlast)\n")
    good = [model for model in chosen if check(model)]

    print(f"Brauchbar: {', '.join(good) if good else 'keines'}")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
