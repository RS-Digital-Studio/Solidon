"""Vermerkt tatsächlich eingecheckte CAD-Pakete und getrennt belegte Prüfungen."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent
folder = Path((STATE / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())
validation = json.loads((folder / "commit-validation.json").read_text(encoding="utf-8"))
assert all(code == 0 for code in validation["statuses"].values())
commits = {scope: json.loads((folder / f"{scope}-commit.json").read_text(encoding="utf-8"))["commit"]
           for scope in ("flush", "deviation")}
snapshot = json.loads((folder / "snapshot.json").read_text(encoding="utf-8"))
for path, expected in snapshot["files"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path


def once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


flush, deviation = (commits[scope][:8] for scope in ("flush", "deviation"))
passed = f"{validation['passed']:,}".replace(",", ".")
path = ROOT / "ROADMAP.md"
text = path.read_text(encoding="utf-8")
anchor = "  **Die Pakete in dieser Folge**"
addition = (
    f"  **Bündige Passung und Formabweichung 20.09.:** `{flush}` ergänzt die\n"
    "  unabhängige vollständige Körperprobe für bündige Ebenenpaare. Die\n"
    "  bestehende Ebenenregel verlangt weiterhin keinen Flächenkontakt.\n"
    f"  `{deviation}` führt belegte analytische Teilträger über Originaldreiecke,\n"
    "  Transformation, warmen/kalten Cache und Historie bis zur neuen\n"
    "  Analysekarte. Ganze Dreiecke werden mit numerischer Klammer begrenzt;\n"
    "  unbekannte Bereiche, Herkunft und wirkliche Zeugen bleiben ausgewiesen.\n"
    "  Berichtsklick, Fortschritt, Abbruch, Ortsmarke und gerichtete\n"
    "  Anzeigerundung teilen denselben Kartenweg in allen Sprachen.\n"
    f"  Vollständige Kernsammlung: **{passed} bestanden, {validation['skipped']} übersprungen**,\n"
    "  Exit 0. mypy ist grün; Ruff und Format sind ohne den ausdrücklich\n"
    "  getrennten parallelen P2.7-Nachweisordner ebenfalls grün. Der erste\n"
    "  unbeschränkte Torprozess bleibt wegen vier Ruff-Befunden und eines\n"
    "  Formatbefunds in dessen fremder Sonde korrekt Exit 1. Eigene\n"
    "  Commitprüfung und Originalergebnis sind getrennt festgehalten unter\n"
    f"  `{folder.as_posix()}`.\n"
    "  Die unabhängige Gegenprüfung sichert Quellenverlust, Abbruchübergaben,\n"
    "  numerischen Überlauf und native Kegelnappen einschließlich echter\n"
    "  Spitzentopologie ab. Zusätzliche Modellsonden treffen analytische\n"
    "  Facettierungsabstände, erhalten ein polygonales Loch und weisen den\n"
    "  nach einem Ausreißer verworfenen Rundfit als unbekannten Mantel aus.\n"
    "  Produktcommits sind nach origin/main gepusht. Fensterdateien und\n"
    "  Leistungsabnahme bleiben ausdrücklich beim Release.\n\n"
)
text = once(text, anchor, addition + anchor)
text = once(text, "  * **läuft** P1.3 —", "  * **implementiert, Release-Abnahme offen** P1.3 —")
text = once(
    text,
    "Offen bleibt die unabhängige Körperprobe der bündigen Ebenenpassung, deren bestehende Ebenenregel keinen Flächenkontakt verlangt.",
    f"`{flush}` ergänzt die unabhängige Körperprobe der bündigen Ebenenpassung; deren bestehende Ebenenregel verlangt weiterhin keinen Flächenkontakt. Verschiedene Platten und zwei Merkmale desselben Körpers bleiben ungeklärte Einbaulagen, kein gemessenes Nullvolumen.",
)
text = once(
    text,
    "  * **offen** P1.6 — Analysekarte „Formabweichung“ aus den Fits",
    f"  * **implementiert, Release-Abnahme offen** P1.6 — `{deviation}`: Analysekarte „Formabweichung“ aus den bereits belegten Ebenen-, Zylinder-, Kugel-, Kegel- und Torusträgern. Originaldreiecke, Teilflächen, tatsächliche Fitwerte und Quellen reisen durch lokale Auswahl, Zusammenfassung, Transformation und Cache. Ganze ausgefüllte Dreiecke erhalten numerische Unter-/Obergrenzen und einen wirklichen baryzentrischen Zeugen; mehrdeutige oder nicht endlich begrenzbare Bereiche bleiben unbekannt. Keine erneute Einpassung. Bericht, asynchroner Fortschritt, Abbruch, bekannte Abdeckung, numerische Breite, Millimeter/Zoll und Ortsmarke sind angeschlossen. Gerichtete native Kegelnappen folgen der wirklichen Trimmung; beide Nappen werden nicht zu einer falschen vereint. Kern- und getrennte Commitprüfung siehe oben; Fenster und Leistung bleiben beim Release.",
)
path.write_text(text, encoding="utf-8")
snapshot["files"]["ROADMAP.md"] = hashlib.sha256(path.read_bytes()).hexdigest()
(folder / "docs-snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "docs-message.txt").write_text(
    "Bündige Körperproben und Formabweichung mit ihren Nachweisen vermerken\n\n"
    "Die tatsächlich gepushten Produktpakete, vollständige Kernsammlung und\n"
    "getrennte Statikprüfung im gemeinsamen Baum sind nachvollziehbar benannt.\n"
    "Fenster- und Leistungsabnahme bleiben offen bis zum Release.\n\n"
    "Co-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8")
print(json.dumps({"commits": commits, "passed": validation["passed"], "skipped": validation["skipped"]}))
