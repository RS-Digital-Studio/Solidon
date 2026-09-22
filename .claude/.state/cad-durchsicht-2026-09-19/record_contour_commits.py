"""Verknüpft die vier geprüften Fachcommits mit ihren tatsächlich offenen CAD-Paketen."""

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
parent = (folder / "parent-exit.txt").read_bytes()
assert parent.decode("utf-16" if parent.startswith(b"\xff\xfe") else "utf-8-sig").strip() == "0"
snapshot = json.loads((folder / "snapshot.json").read_text(encoding="utf-8"))
for path, expected in snapshot["files"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
commits = {}
for scope in ("contours", "surfaces", "filaments", "references"):
    entry = json.loads((folder / f"{scope}-commit.json").read_text(encoding="utf-8"))
    commit = entry["commit"]
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, check=True)
    commits[scope] = commit[:8]
suite_bytes = (folder / "suite.txt").read_bytes()
suite = suite_bytes.decode("utf-16" if suite_bytes.startswith(b"\xff\xfe") else "utf-8-sig")
match = re.search(r"(?m)^(\d+) passed, (\d+) skipped in ([^\r\n]+)", suite)
assert match
passed, skipped = (f"{int(value):,}".replace(",", ".") for value in match.group(1, 2))
path = ROOT / "ROADMAP.md"
text = path.read_text(encoding="utf-8")
anchor = "  **Die Pakete in dieser Folge**"
assert text.count(anchor) == 1 and "**Konturmaße und native Filamente 20.09.:**" not in text
paragraph = f"""  **Konturmaße und native Filamente 20.09.:** `{commits['contours']}`
  misst Zylinder und Langlöcher an belegten Konturen, führt Fehler und echte
  Netzgrenzen durch Transformationen und reicht Passungsbefunde an Oberfläche,
  Steckbrief und Agent weiter. `{commits['surfaces']}` ergänzt native und
  vollständig geprüfte rationale Ringträger sowie gerundete Restflächen.
  `{commits['filaments']}` bindet Filamente an native Flächen und erhält sie
  beim Vernetzen, Kopieren, Weiterbearbeiten, Wiederöffnen und Undo/Redo.
  `{commits['references']}` verbindet Maßfelder mit den belegten Kanten,
  Mitten und Langlochachsen der gewählten Oberfläche.
  Entwicklungstor: **{passed} bestanden, {skipped} übersprungen**, Suite und
  übergeordneter Prozess Exit 0; Ruff, Format und mypy jeweils 0. Der
  eingefrorene Stand und die Protokolle liegen unter `{folder.as_posix()}`.
  Rote Vorläufe bleiben als Nachweis erhalten: Der doppelte Langloch-Kreisfit
  und ein um gerade Flanken vergrößerter Mantelfit wurden behoben, ohne
  Konturtoleranzen zu lockern. Neue Fensterfälle sind vorbereitet und bleiben
  wie Leistung und installierte Plattformen der Release-Abnahme vorbehalten.

"""
text = text.replace(anchor, paragraph + anchor)
old = "`torus`, `curved_face` und die vollständige Semantik-/Teilflächenparität bleiben offen."
assert text.count(old) == 1
text = text.replace(old, f"`{commits['surfaces']}` ergänzt native Ringe, rationale Ringträger mit vollständigem Koeffizientennachweis und gerundete Restflächen. Angrenzende gleiche Ringstücke werden vereint, getrennte bleiben getrennt; vollständige native Flächen behalten exakte Integrale und Originalauswahl. Die vollständige Semantik-/Teilflächenparität und weiteren Trägerfamilien bleiben offen.")
replacements = {
    "  * **offen** P1.1 — Zylindermaßvertrag: Kontur statt Schwerpunkt, Achse, Teilabdeckung, Unterteilung, bewusst polygonale Gegenformen":
        f"  * **implementiert, Release-Abnahme offen** P1.1 — `{commits['contours']}`: belegte Konturecken statt Schwerpunkte, zentrierte Achsrechnung, wirkliche axiale Grenzen und radiale Dreiecksabstände. Unterteilung, schiefe Schnitte, Teilbögen, große Koordinaten, Spiegelung, bewusste Gegenformen und Abbruch sind geprüft. Offene und geschlossene Langlöcher erhalten die volle Maßgenauigkeit; der zweite offene Kreisfit entfällt. Fitfehler und Netzband bleiben getrennt von Fertigungsspiel. Entwicklungstor grün; Fenster und Leistung bleiben beim Release.",
    "  * **offen** P0.4 — Referenzauswahl: echte Kanten, Mitten, Achsen; Bezugswechsel; keine Facetten und keine flüchtigen IDs als Bezug":
        f"  * **läuft** P0.4 — `{commits['references']}`: Bezugswechsel über Auswahlfeld und Modellklick, echte Außen-/Innenkanten, belegte Mitten und Langlochachsen. Zug, Mittenversatz und erneute historische Vorschau erhalten gültige Bezüge. Fast parallele Referenzen und falsche Originalflächen werden abgewiesen; die Bediengrenze ist von geometrischer Toleranz getrennt. Gespeichert werden Operationswerte, keine flüchtigen Kantenbindungen. Vollständige Achsen-/Symmetrieparität folgt mit P1.5, dauerhafte Bezüge mit P3.2; Fensterabnahme bleibt beim Release.",
    "  * **offen** P1.3 — `fits.check` mit Kollisionsprobe; grobe und unsichere Maße gekennzeichnet":
        f"  * **läuft** P1.3 — `{commits['contours']}`: passende Kreismaße reichen bei groben Netzen nicht mehr als Spielbeleg; tatsächliche radiale Grenzen und fehlende Messdaten erzeugen sichtbare Befunde. Steckbrief und Agent erhalten die vollständige Passungsdiagnose. Echte Kollisionsprobe in belegter Einbaulage und einheitliche Kennzeichnung geschätzter Maße bleiben offen.",
    "  * **offen** P2.2 — `assign_slot`, `paint_slot` erhalten B-Rep und Filamentzuweisung über Tessellierung und Speicherung":
        f"  * **implementiert, Release-Abnahme offen** P2.2 — `{commits['filaments']}`: `assign_slot`, `paint_slot` und `clear_filament` erhalten B-Rep. Native Flächen tragen unveränderliche Slots, jede Tessellation folgt ihrer belegten Flächenkarte; reine Attribute erhalten aktuelle Merkmalsdreiecke. Builder-Herkunft führt Farben durch Folgeschritte, verschiedenfarbige Teilungsgrenzen bleiben erhalten. Warmer Cache, bewusster Mesh-Diskcache, Quellen plus Operationsverlauf, Wiederöffnung und Undo/Redo sind geprüft. Fensterfall auf B-Rep-Erhalt umgestellt, ausschließlich zum Release auszuführen.",
}
for old, new in replacements.items():
    assert text.count(old) == 1, old
    text = text.replace(old, new)
path.write_text(text, encoding="utf-8")
snapshot["head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
snapshot["files"]["ROADMAP.md"] = hashlib.sha256(path.read_bytes()).hexdigest()
(folder / "docs-snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "docs-message.txt").write_text(
    "Konturmaße, Flächenfilamente und Bezüge tragen ihre geprüften CAD-Nachweise\n\n"
    "Die Arbeitsliste verknüpft vier getrennte Fachcommits mit dem grünen\n"
    "Entwicklungstor. Restumfang und Release-Abnahme bleiben ausdrücklich offen.\n\n"
    "Co-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8"
)
(STATE / "current-development-gate.txt").write_text(str(folder), encoding="utf-8")
print(json.dumps({"commits": commits, "passed": passed, "skipped": skipped, "folder": str(folder)}))
