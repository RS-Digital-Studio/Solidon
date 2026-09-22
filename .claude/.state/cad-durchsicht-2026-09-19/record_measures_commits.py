"""Trägt ausschließlich abgeschlossene Commits und das grüne Entwicklungstor nach."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent
folder = Path((STATE / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())
statuses = json.loads((folder / "exits.json").read_text(encoding="utf-8-sig"))
assert set(statuses) == {"ruff", "format", "mypy", "suite"} and set(statuses.values()) == {0}
assert (folder / "parent-exit.txt").read_text(encoding="utf-8-sig").strip() == "0"
snapshot = json.loads((folder / "snapshot.json").read_text(encoding="utf-8"))
for path, expected in snapshot["files"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path

commits = {}
for scope in ("runner", "void", "bore", "measures"):
    entry = json.loads((folder / f"{scope}-commit.json").read_text(encoding="utf-8"))
    commit = entry["commit"]
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, check=True)
    commits[scope] = commit[:8]

suite_bytes = (folder / "suite.txt").read_bytes()
suite_text = suite_bytes.decode("utf-16" if suite_bytes.startswith(b"\xff\xfe") else "utf-8-sig")
match = re.search(r"(?m)^(\d+) passed, (\d+) skipped in ([^\r\n]+)", suite_text)
assert match
passed, skipped = (f"{int(value):,}".replace(",", ".") for value in match.group(1, 2))
path = ROOT / "ROADMAP.md"
text = path.read_text(encoding="utf-8")
anchor = "  **Die Pakete in dieser Folge**"
assert text.count(anchor) == 1 and "**Maß- und Innenraumstand 20.09.:**" not in text
paragraph = f"""  **Maß- und Innenraumstand 20.09.:** `{commits['runner']}` schützt die
  Release-Grenze ganzer Fensterdateien auch vor Namens- und Markerfiltern.
  `{commits['void']}` erkennt vollständige Innenräume in beiden Kernen;
  `{commits['bore']}` belegt ursprüngliche Bohrungsschritte und ihren
  gemeinsamen Flächensitz. `{commits['measures']}` verbindet Fachfelder,
  Platzierungsgriffe und dargestellte Vorschau im ersten gemeinsamen
  Maßeditor. Entwicklungstor: **{passed} bestanden, {skipped} übersprungen**,
  Suite und übergeordneter Prozess mit Exit 0; Ruff, Format und mypy jeweils 0.
  Der erste Gesamtversuch meldete einen Fehler bei 11.874 bestandenen
  Kerntests: Sein als Sacklangloch bezeichneter Testkörper enthielt tatsächlich
  einen geschlossenen Innenraum. Native Schalen, Materialpunkte und unabhängiges
  Luftvolumen belegten den falschen Testaufbau. Die korrigierte offene Mündung
  und der eingeschlossene Gegenfall sind jetzt für beide Kerne geprüft;
  die Produkterkennung wurde dafür nicht abgeschwächt. Der rote Lauf bleibt
  erhalten. Fenster- und Leistungsabnahme bleiben ausdrücklich beim Release.

"""
text = text.replace(anchor, paragraph + anchor)
old = "Der nächste uncommittete Anschluss erkennt geschlossene Innenräume"
assert text.count(old) == 1
text = text.replace(old, f"`{commits['void']}` erkennt geschlossene Innenräume")
old = "Uncommitteter Anschluss; Kernnachweise vorhanden, Fensterfälle werden ausschließlich beim Release ausgeführt."
assert text.count(old) == 1
text = text.replace(old, f"`{commits['bore']}` / `{commits['measures']}`: Kernnachweise und Entwicklungstor grün; Fensterfälle werden ausschließlich beim Release ausgeführt. Historische Hilfen gehören zur Prefixanzeige, werden über der Gesamtvorschau ausgeblendet und nach Tiefenänderung neu geprüft.")
path.write_text(text, encoding="utf-8")
snapshot["head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
snapshot["files"]["ROADMAP.md"] = hashlib.sha256(path.read_bytes()).hexdigest()
(folder / "docs-snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "docs-message.txt").write_text(
    "Maßeditor und Innenräume tragen ihre überprüften Entwicklungsnachweise\n\n"
    "Die Arbeitsliste verknüpft die vier getrennten Umsetzungen mit dem neuen\n"
    "grünen Entwicklungstor und erhält den vorherigen roten Lauf samt Ursache.\n"
    "P0.3, P2.3 und der CAD-Gesamtausbau bleiben mit ihren Resten offen;\n"
    "Fenster und Leistung gehören weiterhin ausschließlich zur Release-Abnahme.\n\n"
    "Co-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8"
)
(STATE / "current-development-gate.txt").write_text(str(folder), encoding="utf-8")
print(json.dumps({"commits": commits, "passed": passed, "skipped": skipped, "folder": str(folder)}))
