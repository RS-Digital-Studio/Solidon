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
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.agent.tools import tool_schemas
from app.core.backends.llm import (
    DEFAULT_OLLAMA_MODEL,
    Message,
    OllamaBackend,
)
from app.core.bootstrap import load_operations

SYSTEM = (
    "Du steuerst ein CAD-Programm über Werkzeuge. Benutze für jede Anfrage ein "
    "Werkzeug. Ist die Anfrage mehrdeutig, frage über ask_user nach, statt zu raten."
)

#: Anfrage und das Werkzeug, das sie verlangt. Die letzte ist mit Absicht
#: mehrdeutig — „Fragen vor Raten" ist eine der vier Vorrangregeln, und ein
#: Modell, das hier rät, ist für den Agenten unbrauchbar.
CASES: tuple[tuple[str, str], ...] = (
    ("Lege einen Projektparameter laenge mit dem Wert 20 mm an.", "add_parameter"),
    ("Zeig mir den Prüfbericht.", "read_report"),
    ("Suche einen Baustein für eine M3-Schraube.", "find_part"),
    ("Nimm die letzte Änderung zurück.", "undo_transaction"),
    ("Mach das Ding etwas größer.", "ask_user"),
)


def check(model: str) -> bool:
    """Ein Modell durch alle Fälle. ``True``, wenn jeder Aufruf saß."""
    backend = OllamaBackend(model=model)
    schemas = tool_schemas()
    structured = 0
    hits = 0
    lines: list[str] = []

    for question, wanted in CASES:
        messages = [
            Message(role="system", content=SYSTEM),
            Message(role="user", content=question),
        ]
        started = time.perf_counter()
        try:
            reply = backend.complete(messages, tools=schemas)
        except Exception as problem:  # eine Messung, kein Produktionsweg
            lines.append(f"    {wanted:18} Fehler  {type(problem).__name__}: {problem}")
            continue
        seconds = time.perf_counter() - started

        if not reply.wants_tools:
            lines.append(f"    {wanted:18} Prosa  {seconds:5.1f}s  {reply.text[:58]!r}")
            continue
        structured += 1
        names = [call.name for call in reply.tool_calls]
        if wanted in names:
            hits += 1
            lines.append(f"    {wanted:18} ok     {seconds:5.1f}s  {names}")
        else:
            lines.append(f"    {wanted:18} falsch {seconds:5.1f}s  {names}")

    total = len(CASES)
    print(f"  {model}")
    print(f"    strukturiert {structured}/{total} · richtig {hits}/{total}")
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
    schemas = tool_schemas()
    print(f"Werkzeuge: {len(schemas)} ({len(json.dumps(schemas)) // 1024} KB Schema)\n")
    good = [model for model in chosen if check(model)]

    print(f"Brauchbar: {', '.join(good) if good else 'keines'}")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
