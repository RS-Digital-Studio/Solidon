"""Schreibt nach echtem grünem Abschluss die überprüfbaren Fakten in die dauerhafte Übergabe."""

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent
folder = Path((STATE / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout.decode().strip()


def log(path):
    raw = path.read_bytes()
    return raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")


exits = json.loads((folder / "exits.json").read_text(encoding="utf-8-sig"))
assert set(exits) == {"ruff", "format", "mypy", "suite"} and all(v == 0 for v in exits.values())
assert (folder / "parent-exit.txt").read_text(encoding="utf-8-sig").strip() == "0"
results = set(re.findall(r"(\d+) passed, (\d+) skipped in ([\d.]+)s", log(folder / "suite.txt")))
assert len(results) == 1, results
passed, skipped, seconds = next(iter(results))
commit = json.loads((folder / "spatial-commit.json").read_text())["commit"]
assert not git("diff", "HEAD", "--", "ROADMAP.md", "konzepte/README.md", "konzepte/uebergabe-cad-2026-09-20.md")
snapshot = json.loads((folder / "snapshot.json").read_text())
for path, expected in snapshot["files"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path

evidence = f"""Ausgangscommit: `{snapshot['head']}`.
Produktcommit: **`{commit}`**. Genau 15 eigene Produkt-/Test-/Katalogpfade;
die Übergabe samt ROADMAP- und Indexverweis folgt als getrennter Dokucommit.

Gemeinsames Entwicklungstor am eingefrorenen Stand von **981 relevanten
Dateien**: **{int(passed):,} bestanden, {skipped} übersprungen, {seconds} s**;
Suite und übergeordneter Prozess Exit **0**, Ruff/Format/mypy jeweils **0**.
Ruff prüfte den ganzen Baum; Format meldete 1138 Dateien, mypy 303 Quelldateien.
Protokolle, vier Ausgänge, Snapshot, vollständiger eigener Diff und private
Commitpfade: `{folder.as_posix()}/`.

Gezielte Nachweise: 41 neue Kernelfälle und 13 neue Verbraucherfälle grün;
447 Verbraucherregressionen sowie sieben bestehende Rundungsfälle jeweils
Exit 0. Der zusätzliche 639er-Kernlauf war ebenfalls grün, importierte aber
vor dem letzten Endkopie-Abbruchfix. Dessen Endstand belegen der anschließende
41er-Lauf und das obige vollständige Entwicklungstor. Kernelprotokolle:
`C:/Users/rober/AppData/Local/Temp/solidon-p14c-face-kernel-green-1789905229636/`;
Verbraucherprotokolle:
`C:/Users/rober/AppData/Local/Temp/solidon-p14c-consumer-green-684fa2a707524b2bb2fc42a92a054a77/`.

Eine zusätzliche Gegenprobe war vor dem Endkopie-Fix 1 rot/3 grün; sie bleibt
als `result-copy-red.txt` erhalten. Im Verbraucher-Testentwurf wurde nur die
erwartete Fehlerklasse für leere Auswahl von GeometryError zu der gemeinsamen
ValidationError präzisiert; Ablehnung, Handlungsvorschläge und unveränderte
Originalbytes bleiben geprüft. Ein zwischenzeitlicher mypy-Typbefund und eine
zu lange Testdocstring wurden vor dem finalen Tor korrigiert.

**Nicht ausgeführt:** Fensterdateien, Leistungsprüfungen, installierte Pakete,
neuer Releasebau und Veröffentlichung. `test_calibration.py` wurde vom
betroffenen Runner vollständig als Fensterdatei zurückgestellt. Der reine
Katalogeinsammler meldete 5917 Quellen, in allen fünf Sprachen null offene
Übersetzungen. Der unabhängige lesende Review fand keinen konkreten Blocker.
""".replace(f"{int(passed):,}", f"{int(passed):,}".replace(",", "."))

p25 = ROOT / "konzepte/nachweise-cad-p2-5"
p25_commit = git("log", "-1", "--format=%h %s", "--", "konzepte/nachweise-cad-p2-5")
p25_status = git("status", "--short", "--", "konzepte/nachweise-cad-p2-5")
readme = (p25 / "README.md").read_text(encoding="utf-8-sig") if (p25 / "README.md").exists() else ""
pending = bool(re.search(r"\{\{[^}]+\}\}", readme))
p25_state = (
    "\nLetzter gelesener Übergabesnapshot: Der externe README-Bericht liegt "
    + ("noch mit einem Platzhalter vor. " if pending else "ohne sichtbaren Vorlagenplatzhalter vor. ")
    + (f"Letzter Git-Eintrag nur dieses Ordners: `{p25_commit}`. " if p25_commit else "Für diesen Ordner ist noch kein Git-Commit vorhanden. ")
    + ("Der Ordner enthält weiterhin lokale Änderungen bzw. untracked Dateien. " if p25_status else "Der Ordner hat im Snapshot keinen lokalen Diff. ")
    + "Das ist eine Bestandsaufnahme, keine technische Abnahme seiner Prototypen.\n\n"
    + "Die Inventur seines laufenden Berichts nennt zusätzlich stillen Gangverlust "
    "bei halbzahligen Längen (Überschneidung mit P2.7), falsche tessellationsabhängige "
    "Gangtiefe am Netz, Steigungsquellen/Passung und den Merkmals-/Nenndurchmesservertrag. "
    "Innen-Nenn-Ø und beide gemessenen Radien getrennt halten. Gemeinsame Fehler "
    "gemeinsam beheben; Gegenstück und Normgrößenvorschlag bleiben P2.6. Zum gelesenen "
    "Zwischenstand waren fremdes Hersteller-STEP, mindestens drei Gänge, links/mehrgängig "
    "innen sowie konische und kantenlos tangential modellierte Gewinde noch offen. "
    "Diese Grenzen am finalen Bericht erneut prüfen.\n"
)
draft = (STATE / "handoff-draft.md").read_text(encoding="utf-8")
assert draft.count("{{FINAL_EVIDENCE}}") == draft.count("{{P25_STATE}}") == 1
handoff = draft.replace("{{FINAL_EVIDENCE}}", evidence).replace("{{P25_STATE}}", p25_state)
assert "{{" not in handoff
(ROOT / "konzepte/uebergabe-cad-2026-09-20.md").write_text(handoff, encoding="utf-8")

roadmap = ROOT / "ROADMAP.md"
lines = roadmap.read_text(encoding="utf-8").splitlines()
indices = [i for i, line in enumerate(lines) if line.startswith("  * **läuft** P1.4 —")]
assert len(indices) == 1
lines[indices[0]] += (
    f" **P1.4c.1 (`{commit[:9]}`) ist im Entwicklungsumfang abgeschlossen:** "
    "Fläche versetzen und Rundung entfernen übernehmen aktuelle vollständige Originalflächen "
    "durch die private Kopierabbildung; ungültige Auswahl wechselt nicht zur Mittelpunkt-Suche. "
    "Auch Abbruch nach der letzten Ergebniskopie ist geprüft. "
    f"Endtor: {int(passed):,} bestanden, {skipped} übersprungen, Suite/Ruff/Format/mypy je 0. "
    "Native historische Fortführung, Gruppen-/Kantenneuwahl und Radiuswechsel bleiben offen. "
    "Die [vollständige Übergabe](konzepte/uebergabe-cad-2026-09-20.md) hält "
    "Anschlussverträge, Belege und die getrennte P2.5-/P2.7-Arbeit fest."
).replace(f"{int(passed):,}", f"{int(passed):,}".replace(",", "."))
roadmap.write_text("\n".join(lines) + "\n", encoding="utf-8")

index = ROOT / "konzepte/README.md"
content = index.read_text(encoding="utf-8")
anchor = "| Dokument | Stand | Thema | Wie es dasteht |\n|---|---|---|---|\n"
assert content.count(anchor) == 1
entry = (
    "| [uebergabe-cad-2026-09-20.md](uebergabe-cad-2026-09-20.md) | **20.09., nach P1.4c.1** | "
    "Übergabe der laufenden CAD-Umsetzung an die nächste Session | "
    "**Entwicklungsabschluss des direkten Flächenanschlusses, Gesamtauftrag offen.** "
    "Paketstand, konkrete Folgegrenzen, Cache-/Formatverträge, Prüfbelege, "
    "P2.5-/P2.7-Zuständigkeit und Starttext; Arbeitsregister bleibt RM-188. |\n"
)
index.write_text(content.replace(anchor, anchor + entry), encoding="utf-8")
summary = {"product_commit": commit, "gate": str(folder), "core": {"passed": int(passed),
           "skipped": int(skipped), "seconds": float(seconds), "exit": 0},
           "exits": exits, "p25_commit": p25_commit, "p25_status": p25_status,
           "handoff": "konzepte/uebergabe-cad-2026-09-20.md"}
(STATE / "p14c1-completed.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
