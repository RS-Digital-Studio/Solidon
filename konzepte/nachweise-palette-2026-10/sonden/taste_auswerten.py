"""Fasst die Messungen von ``sonde_tastendruck.py`` zusammen.

Aufruf: python taste_auswerten.py <ordner> <name>=<datei>,<datei> ...

Je Name: Öffnen, erster Tastendruck (baut die Zeilen), die übrigen und jedes
Wort für sich, als Median und Höchstwert in Millisekunden.
"""

import json
import statistics
import sys
from pathlib import Path


def summary(label: str, times: list[float]) -> str:
    """Eine Zeile: Median und Höchstwert in Millisekunden."""
    median = statistics.median(times) * 1000
    return f"  {label:12} Median {median:7.1f} ms  max {max(times) * 1000:7.1f} ms"


folder = Path(sys.argv[1])
for spec in sys.argv[2:]:
    label, files = spec.split("=")
    opens: list[float] = []
    firsts: list[float] = []
    rest: list[float] = []
    per_word: dict[str, list[float]] = {}
    for name in files.split(","):
        data = json.loads((folder / name).read_text(encoding="utf-8"))
        for measured in data["rounds"]:
            opens.append(measured["open"])
            first_word = True
            for word, times in measured.items():
                if word == "open":
                    continue
                if first_word:
                    firsts.append(times[0])
                    rest.extend(times[1:])
                    first_word = False
                else:
                    rest.extend(times)
                per_word.setdefault(word, []).extend(times)
    print(f"== {label}")
    print(summary("Öffnen", opens))
    print(summary("1. Zeichen", firsts))
    print(summary("übrige", rest) + f"  (n={len(rest)}, Summe {sum(rest) * 1000:.1f} ms)")
    for word, times in per_word.items():
        print("  " + summary(word, times))
