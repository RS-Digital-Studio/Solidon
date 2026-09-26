"""Gespeicherte Suiteläufe mit der Bewertung vom 26.09.2026 nachrechnen.

Zwei Korrekturen, beide nur lockernd und aus der gespeicherten Antwort
ableitbar: die Wo-Fälle zählen „Handlungen" statt „Menü", und ein Zwilling
zählt als dieselbe Handlung (P2.8). Ein Fall kippt nur dann auf gut, wenn
außer der Operationsliste nichts gegen ihn stand (kein Fehler, nicht
mehrdeutig, Parameter vorhanden, wo verlangt).

    python rescore.py <lauf.json> ...
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"F:\3D Druck")
from app.core.bootstrap import load_operations  # noqa: E402
from app.core.registry import menu_twins  # noqa: E402
from tests.agent_cases import by_id  # noqa: E402

load_operations()
TWINS = menu_twins()


def acts(names):
    return Counter(TWINS.get(name, name) for name in names)


for name in sys.argv[1:]:
    data = json.loads(Path(name).read_text(encoding="utf-8"))
    results = data["results"]
    good = 0
    flipped = []
    for entry in results:
        case = by_id(entry["id"])
        ok = entry["good"]
        if not ok and not entry["error"] and not case.ambiguous:
            if entry["id"] in ("where_menu", "where_hollow"):
                ok = not entry["ops"] and "Handlungen" in entry["answer"]
            elif case.expects_ops and not case.expects_answer_only:
                params_ok = not case.expects_parameter or entry["parameters"] > 0
                ok = params_ok and acts(case.expects_ops) <= acts(entry["ops"])
            if ok:
                flipped.append(entry["id"])
        good += ok
    print(f"{data['model']:14} {Path(data['root']).name:7} Fenster {data.get('window', 32768):6}  "
          f"gut {sum(e['good'] for e in results):2} → {good:2}  gekippt: {', '.join(flipped) or '—'}")
