"""Trägt nur den nachgewiesenen P1.4b-Stand nach dem Produktcommit ein."""

import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent
folder = Path((STATE / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())
exits = json.loads((folder / "exits.json").read_text(encoding="utf-8-sig"))
assert set(exits) == {"ruff", "format", "mypy", "suite"}
assert all(value == 0 for value in exits.values()), exits
committed = json.loads((folder / "spatial-commit.json").read_text(encoding="utf-8"))
commit = committed["commit"]
result = subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT)
assert result.returncode == 0
data = (folder / "suite.txt").read_bytes()
suite = data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
counts = sorted(set(re.findall(r"(\d+) passed, (\d+) skipped", suite)))
assert len(counts) == 1, counts
passed, skipped = (int(value) for value in counts[0])
passed_de = f"{passed:,}".replace(",", ".")
path = ROOT / "ROADMAP.md"
before = path.read_bytes()
text = before.decode("utf-8")
lines = text.splitlines(keepends=True)
found = [index for index, line in enumerate(lines) if line.startswith("  * **läuft** P1.4 —")]
assert len(found) == 1, found
index = found[0]
assert "P1.4b" in lines[index] and "d483e1477" in lines[index]
newline = "\r\n" if lines[index].endswith("\r\n") else "\n"
lines[index] = (
    "  * **läuft** P1.4 — `d483e1477` trägt die räumliche Vorauswahl und durchgehenden Abbruch; "
    f"`{commit[:9]}` schließt **P1.4b** im Entwicklungsumfang an: "
    "konkurrierende Ansprüche und gleichwertige globale Zuordnungen bleiben gemeinsam offen; "
    "vollständige körperbezogene Entscheidungen übernehmen jeden Nachfolger höchstens einmal "
    "und speichern auch die ausdrückliche Nichtfortführung. Antworten werden über alle Ausgaben "
    "einer Operation atomar veröffentlicht. Format 27 erhält alte Antworten und die jeweilige "
    "Maßfassung bei Undo/Redo; tatsächlich gebundene Merkmale entwerten den Folgecache. "
    "Die Rückfrage zeigt echte Ausgabegeometrie und wartet auf die aufgebaute Ansicht; "
    "dieser Fensteranschluss ist statisch geprüft, seine Ausführung bleibt Release-Abnahme. "
    "Echte STL-/STEP-Projekte mit 1056 Flächen prüfen Identität, Maßquellen, Originalträger, "
    "Änderung, Cache, Wiederöffnung und Undo/Redo. "
    f"Entwicklungstor: {passed_de} bestanden, {skipped} übersprungen; Ruff, Format und mypy jeweils 0. "
    "Fachlich offen bleibt **P1.4c**: native Flächen- und Kantenbezüge ausdrücklich neu wählen "
    "und die gewählte aktuelle Topologie bis zur Operation erhalten. Referenzierte native "
    "Konkurrenz hält bereits an; Netzantworten geben sie nicht frei. Die Produktionsgrenze "
    "bleibt bei 1000; ihre Anhebung sowie Fenster- und Leistungsabnahme folgen erst mit dem "
    "Release-Nachweis." + newline
)
assert path.read_bytes() == before
path.write_bytes("".join(lines).encode("utf-8"))
note = (
    "\n## Gemeinsamer Entwicklungsnachweis P1.4b\n\n"
    f"Gate `{folder}`: {passed} bestanden, {skipped} übersprungen. "
    "Kernsammlung, Ruff, Format und mypy jeweils direkter Exit 0. "
    f"Produktcommit `{commit}` umfasst nur die {len(committed['paths'])} ausdrücklichen eigenen Pfade. "
    "Fenster-/Leistungsprüfungen wurden nicht ausgeführt. Der native Neuwahlanschluss "
    "bleibt P1.4c. Der Push wird separat mit dem Remote-Commit nachgewiesen.\n"
)
with (STATE / "p14b-root-integration.md").open("a", encoding="utf-8") as stream:
    stream.write(note)
print(json.dumps({"commit": commit, "passed": passed, "skipped": skipped, "roadmap_line": index + 1}))
