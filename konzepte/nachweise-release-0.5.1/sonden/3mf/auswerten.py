"""Fasst die Läufe von ``p01_nativ.py`` einer Reihe zusammen (RM-258).

Je Lauf: längste Lücke des Qt-Takts insgesamt, längste Lücke **vor** der
Rückfrage zur Vollerkennung (der Import selbst; danach baut der Hauptfaden den
Dialog, und der Arbeiter wartet auf die Antwort), Zahl der Lücken über 200 ms.

    python auswerten.py <reihenname>
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
name = sys.argv[1]
rows = []
for path in sorted(OUT.glob(f"p01_{name}_*.txt")):
    if path.name.endswith(".stderr.txt"):
        continue
    text = path.read_text("utf-8")
    gaps_line = re.search(r"Lücken Qt-Takt über 100 ms \(Beginn, Dauer\): (\[.*\])", text)
    ask = re.search(r"Wachhund sieht AskDialog bei ([0-9.]+)", text)
    done = re.search(r"fertig nach ([0-9.]+)", text)
    if gaps_line is None:
        rows.append((path.stem, "ohne Ergebnis"))
        continue
    gaps = ast.literal_eval(gaps_line.group(1))
    asked = float(ask.group(1)) if ask else None
    # Der Wachhund sieht den Dialog bis zu 150 ms nach seinem Erscheinen; was
    # in der Sekunde davor endet, gehört zum Bild vor der Frage und zum Dialog.
    before = [length for start, length in gaps if asked is None or start + length < asked - 1.0]
    at_ask = [length for start, length in gaps if asked is not None and asked - 1.0 <= start + length <= asked + 0.2]
    rows.append(
        (
            path.stem.removeprefix(f"p01_{name}_"),
            f"längste {max((g for _s, g in gaps), default=0):.2f} s,"
            f" Import {max(before, default=0):.2f} s,"
            f" Bild und Rückfrage {max(at_ask, default=0):.2f} s,"
            f" über 200 ms {sum(1 for _s, g in gaps if g > 0.2)},"
            f" fertig nach {done.group(1) if done else '?'} s",
        )
    )
for label, summary in rows:
    print(f"{label:10s} {summary}")
