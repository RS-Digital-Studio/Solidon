"""Friert Konturmaße, native Flächenattribute und Platzierungsbezüge für das Kerntor ein."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent
folder = Path(tempfile.gettempdir()) / f"solidon-cad-contours-final-{uuid.uuid4().hex}"
folder.mkdir()
previous = Path((STATE / "current-development-gate.txt").read_text(encoding="utf-8-sig").strip())


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


catalogs = [f"app/i18n/locales/{language}.json" for language in ("en", "es", "fr", "it", "pt")]
scopes = {
    "contours": [
        "app/core/agent/CLAUDE.md", "app/core/agent/checks.py",
        "app/core/brep/features.py",
        "app/core/geom/prepare_ops.py", "app/core/geom/CLAUDE.md", "tests/test_prepare.py",
        "app/core/perceive/CLAUDE.md", "app/core/perceive/features.py",
        "app/core/perceive/local.py", "app/core/perceive/slots.py",
        "app/core/perceive/digest.py", "app/core/perceive/matching.py",
        "app/core/perceive/relations.py", "app/core/scene/fits.py",
        "app/core/scene/cache.py", "app/core/scene/CLAUDE.md", "app/ui/labels.py",
        "tests/test_cache.py", "tests/test_features.py", "tests/test_cylinder_measurements.py",
        "tests/test_cylinder_facets.py", "tests/test_corpus.py",
        "tests/test_digest_and_fits.py", "tests/test_matching.py", "tests/test_feature_groups.py",
        *catalogs,
    ],
    "surfaces": [
        "app/core/brep/canonical.py", "app/core/brep/features.py", "app/core/brep/CLAUDE.md",
        "app/core/perceive/features.py", "app/core/scene/cache.py", "tests/test_cache.py",
        "tests/test_brep_surfaces.py", "tests/test_brep_canonical_surfaces.py",
    ],
    "filaments": [
        "app/core/brep/CLAUDE.md", "app/core/brep/kernel.py", "app/core/brep/edit.py",
        "app/core/brep/ops.py", "app/core/brep/profiles.py", "app/core/geom/CLAUDE.md",
        "app/core/geom/attributes.py", "app/core/geom/colour_ops.py", "app/core/geom/paint.py",
        "app/core/scene/cache.py", "tests/test_cache.py", "tests/test_brep.py",
        "tests/test_paint.py", "tests/test_exact_body_parity.py", "tests/test_filament_workflow.py",
        *catalogs,
    ],
    "references": [
        "app/core/scene/placement.py", "app/core/scene/CLAUDE.md", "app/ui/CLAUDE.md",
        "app/ui/placement_flow.py", "tests/test_surface_placement.py",
        "tests/test_surface_placement_ui.py", *catalogs,
    ],
    "docs": ["ROADMAP.md"],
}
assert not git("diff", "--cached", "--name-only").strip()
declared = set().union(*(paths for scope, paths in scopes.items() if scope != "docs"))
changed = set(git("diff", "--name-only", "HEAD").decode().splitlines())
untracked = set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
owned = {path for path in changed | untracked
         if not path.startswith(("website/", ".claude/.state/"))}
assert owned == declared, (sorted(owned - declared), sorted(declared - owned))
for scope, paths in scopes.items():
    (folder / f"{scope}-paths.json").write_text(json.dumps(sorted(paths), indent=2), encoding="utf-8")
(folder / "commit-order.json").write_text(
    json.dumps(["surfaces", "contours", "filaments", "references", "docs"]), encoding="utf-8"
)
relevant = set(git("ls-files", "app", "tests", "tools", ".claude/rules", "AGENTS.md", "CLAUDE.md",
                         "pyproject.toml", "constraints.txt", "3d-agent-bauplan.md").decode().splitlines())
relevant |= declared | {"ROADMAP.md"}
snapshot = {
    "head": git("rev-parse", "HEAD").decode().strip(),
    "files": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sorted(relevant)},
}
(folder / "snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "docs-snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "initial-status.txt").write_bytes(git("status", "--short"))
(folder / "full.diff").write_bytes(git("diff", "HEAD", "--", *sorted(declared)))
shutil.copyfile(previous / "run.ps1", folder / "run.ps1")
shutil.copyfile(previous / "commit_scope.py", folder / "commit_scope.py")
shutil.copyfile(STATE / "prepare_contour_scope.py", folder / "prepare_scope.py")
messages = {
    "contours": (
        "Konturmaße bleiben beim Erkennen, Wiederaufbauen und Prüfen maßhaltig\n\n"
        "Zylinder und Langlöcher verwenden belegte Konturecken, tatsächliche\n"
        "Netzgrenzen und einen gemeinsamen Kreisfit. Relative Fehler bleiben\n"
        "dimensionslos, Wiederherstellungen erhalten das Maß ohne frühere\n"
        "Vieleckkorrektur. Passungsunsicherheit erreicht alle Verbraucher.\n"
    ),
    "surfaces": (
        "Native Ringträger und gerundete Restflächen behalten ihre Originalauswahl\n\n"
        "Rationale Ringe teilen den Kandidatenweg mit Netzen und benötigen\n"
        "zusätzlich einen vollständigen Koeffizientennachweis. Angrenzende\n"
        "gleiche Ringflächen bilden eine Auswahl; getrennte bleiben getrennt.\n"
        "Freie Rundflächen teilen die bestehende Erkennung beider Kerne.\n"
    ),
    "filaments": (
        "Filamentzuweisungen erhalten exakte Körper und native Flächengrenzen\n\n"
        "Slots gehören zur nativen Fläche und folgen jeder neuen Tessellation.\n"
        "Kopien und Builder-Herkunft erhalten belegte Attribute durch Folgeschritte;\n"
        "verschiedenfarbige Teilungsgrenzen werden bewahrt. Cache, Wiederöffnung\n"
        "und Undo sind geprüft. Fensterabnahme bleibt ausschließlich beim Release.\n"
    ),
    "references": (
        "Platzierungsmaße lassen ihre belegten Kanten, Mitten und Achsen wählen\n\n"
        "Maßfeld und Modellklick teilen die Referenzauskunft der Originalfläche.\n"
        "Bezüge bleiben beim Ziehen und Neuaufbau gültig; mehrdeutige und fast\n"
        "parallele Auswahl wird erklärt. Gespeichert werden Operationswerte.\n"
        "Die ergänzten Fensterfälle bleiben bis zum Release unausgeführt.\n"
    ),
}
for scope, message in messages.items():
    (folder / f"{scope}-message.txt").write_text(
        message + "\nCo-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8"
    )
(STATE / "next-development-gate.txt").write_text(str(folder), encoding="utf-8")
print(json.dumps({"folder": str(folder), "head": snapshot["head"], "files": len(relevant)}))
