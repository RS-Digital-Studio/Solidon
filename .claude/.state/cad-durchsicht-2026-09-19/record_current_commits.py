"""Vermerkt die tatsächlich eingecheckten Pakete und ihren gemeinsamen Torlauf."""

from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
folder = Path((Path(__file__).parent / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())
exits = json.loads((folder / "exits.json").read_text(encoding="utf-8-sig"))
assert set(exits) == {"ruff", "format", "mypy", "suite"} and not any(exits.values())
commits = {
    name: json.loads((folder / f"{name}-commit.json").read_text(encoding="utf-8"))["commit"][:8]
    for name in ("policy", "nurbs", "group", "crash", "notice")
}
counts = set(re.findall(r"(\d+) passed, (\d+) skipped", (folder / "suite.txt").read_text(encoding="utf-8-sig")))
assert len(counts) == 1, counts
passed, skipped = next(iter(counts))
passed = f"{int(passed):,}".replace(",", ".")


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


path = ROOT / "ROADMAP.md"
text = path.read_text(encoding="utf-8")
text = replace_once(text, "  **Entwicklungsstand 20.09.:**", "  **Erster Entwicklungsstand 20.09.:**")
anchor = "  **Die Pakete in dieser Folge**"
addition = (
    f"  **Weiterer Entwicklungsstand 20.09.:** `{commits['nurbs']}` schließt\n"
    "  kanonische NURBS-Träger an den durchgehenden Bearbeitungsweg an.\n"
    f"  `{commits['group']}` ergänzt gemeinsames Aufsetzen von Importgruppen,\n"
    f"  `{commits['crash']}` den lokalen Absturzschutz und `{commits['notice']}`\n"
    "  die Rückmeldung am Handlungsort. Gemeinsames Entwicklungstor:\n"
    f"  **{passed} bestanden, {skipped} übersprungen**, Prozessausgang 0; Ruff,\n"
    "  Format und mypy jeweils 0. Der erste Lauf dieses Blocks meldete vier\n"
    "  Kernfehler und einen Formatbefund; nach ihren Korrekturen bestanden\n"
    "  11.745 Kerntests. Der zusätzliche Hook-Abgleich erforderte fünf neue\n"
    "  Gegenproben und den hier genannten abschließenden Gesamtlauf.\n"
    f"  `{commits['policy']}` ergänzt die Release-Regel aus `69f956e76` im\n"
    "  Commit-Hook und in den verbleibenden Agentenanleitungen: neue Texte\n"
    "  werden statisch geprüft; sämtliche Fensterdateien und Leistungsprüfungen\n"
    "  bleiben beim Release. Die Agenten-Werkzeugliste umfasst 144 Einträge;\n"
    "  der funktionale Zählaufruf von qwen3:14b belegt dafür 36.826 Prompt-Token\n"
    "  bei `num_ctx=40960`, ohne eine Leistungsprüfung auszuführen.\n\n"
)
text = replace_once(text, anchor, addition + anchor)
text = replace_once(text, "P2.3 — erster Anschluss", f"P2.3 — `{commits['nurbs']}`: erster Anschluss")
text = replace_once(
    text,
    "Die unabhängige Gegenprüfung ergänzt periodische Nahttrimmungen und unveränderte Originalflächen bei Defeaturing.",
    "Die unabhängige Gegenprüfung ergänzt periodische Nahttrimmungen und unveränderte Originalflächen bei Defeaturing. Acht weitere Maßfälle sichern wiederholte Radialänderungen sowie schräge Originalränder über enge NURBS-Knoten in beiden Richtungen, auch unter Offset- und Trimmhüllen.",
)
text = replace_once(text, "P0.7 — früher", f"P0.7 — `{commits['group']}` / `{commits['crash']}` / `{commits['notice']}`: früher")
path.write_text(text, encoding="utf-8")

path = ROOT / "konzepte/durchsicht-cad-konzepte-2026-09.md"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "STEP-Platte, ändert ihre Bohrung, speichert, öffnet und nimmt zurück. Die\nübrigen Merkmalsarten",
    "STEP-Platte, ändert ihre Bohrung, speichert, öffnet und nimmt zurück.\nMaßintegrale berücksichtigen die ursprünglichen NURBS-Knoten auch unter\nOffset- und Trimmhüllen; schräge Originalränder werden in beiden\nKnotenrichtungen unterteilt. Wiederholte Radialänderungen und enge Spannen\nhaben unabhängige Sollwerte. Die übrigen Merkmalsarten",
)
path.write_text(text, encoding="utf-8")
print(json.dumps({"commits": commits, "passed": passed, "skipped": skipped}, ensure_ascii=False))
