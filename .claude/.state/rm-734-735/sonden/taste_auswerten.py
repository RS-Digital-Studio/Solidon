"""Fasst Tastendruckmessungen zusammen. Aufruf: <ordner> <name>=<datei>,<datei> ..."""

import json
import statistics
import sys
from pathlib import Path

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
    print(f"  Öffnen       Median {statistics.median(opens) * 1000:7.1f} ms  max {max(opens) * 1000:7.1f} ms")
    print(f"  1. Zeichen   Median {statistics.median(firsts) * 1000:7.1f} ms  max {max(firsts) * 1000:7.1f} ms")
    print(f"  übrige       Median {statistics.median(rest) * 1000:7.1f} ms  max {max(rest) * 1000:7.1f} ms  (n={len(rest)})")
    print(f"               Summe  {sum(rest) * 1000:7.1f} ms")
    for word, times in per_word.items():
        print(f"    {word:10} Median {statistics.median(times) * 1000:7.1f} ms  max {max(times) * 1000:7.1f} ms")
