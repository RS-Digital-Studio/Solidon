"""Friert bündige Körperproben und Formabweichung mit getrennten Umfängen ein."""

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


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


catalogs = [f"app/i18n/locales/{lang}.json" for lang in ("en", "es", "fr", "it", "pt")]
shared = ["app/core/scene/CLAUDE.md", *catalogs]
scopes = {
    "flush": ["app/core/scene/fits.py", "tests/test_fit_geometry.py",
              "tests/test_digest_and_fits.py", *shared],
    "deviation": """
3d-agent-bauplan.md
app/core/CLAUDE.md
app/core/brep/CLAUDE.md
app/core/brep/features.py
app/core/geom/CLAUDE.md
app/core/geom/deviation.py
app/core/geom/prepare_ops.py
app/core/geom/seal_ops.py
app/core/geom/transform.py
app/core/knowledge/parts/CLAUDE.md
app/core/knowledge/parts/profile_clamps.py
app/core/knowledge/parts/seals.py
app/core/organizer/CLAUDE.md
app/core/organizer/build.py
app/core/perceive/CLAUDE.md
app/core/perceive/features.py
app/core/perceive/local.py
app/core/perceive/maps.py
app/core/perceive/matching.py
app/core/perceive/slots.py
app/core/perceive/surfaces.py
app/core/scene/cache.py
app/core/scene/evaluate.py
app/core/types.py
app/core/units.py
app/ui/CLAUDE.md
app/ui/analysis_bar.py
app/ui/labels.py
app/ui/main_window.py
tests/test_analysis_ui.py
tests/test_brep_surfaces.py
tests/test_brep_voids.py
tests/test_cache.py
tests/test_core_package_direction.py
tests/test_evaluation.py
tests/test_maps.py
tests/test_organizer_build.py
tests/test_profile_clamps.py
tests/test_seal_ops.py
tests/test_seal_parts.py
tests/test_surface_deviation.py
tests/test_surface_patches.py
tests/test_units.py
""".split() + shared,
    "docs": ["ROADMAP.md"],
}

assert not git("diff", "--cached", "--name-only").strip()
declared = set().union(*(paths for scope, paths in scopes.items() if scope != "docs"))
changed = set(git("diff", "--name-only", "HEAD").decode().splitlines())
untracked = set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
owned = {path for path in changed | untracked
         if not path.startswith(("website/", ".claude/.state/", "konzepte/nachweise-cad-p2-7/"))}
assert owned == declared, (sorted(owned - declared), sorted(declared - owned))
folder = Path(tempfile.gettempdir()) / f"solidon-cad-deviation-final-{uuid.uuid4().hex}"
folder.mkdir()
previous = Path((STATE / "current-development-gate.txt").read_text(encoding="utf-8-sig").strip())
for scope, paths in scopes.items():
    assert len(paths) == len(set(paths))
    (folder / f"{scope}-paths.json").write_text(json.dumps(sorted(paths), indent=2), encoding="utf-8")
(folder / "commit-order.json").write_text(json.dumps(["flush", "deviation", "docs"]), encoding="utf-8")
relevant = set(git("ls-files", "app", "tests", "tools", ".claude/rules", "AGENTS.md", "CLAUDE.md",
                  "pyproject.toml", "constraints.txt", "3d-agent-bauplan.md").decode().splitlines())
relevant |= declared | {"ROADMAP.md"}
snapshot = {"head": git("rev-parse", "HEAD").decode().strip(),
            "files": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                      for path in sorted(relevant)}}
for name in ("snapshot.json", "docs-snapshot.json"):
    (folder / name).write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "initial-status.txt").write_bytes(git("status", "--short"))
(folder / "full.diff").write_bytes(git("diff", "HEAD", "--", *sorted(declared)))
for name in ("run.ps1", "commit_scope.py"):
    shutil.copyfile(previous / name, folder / name)
shutil.copyfile(STATE / "prepare_deviation_scope.py", folder / "prepare_scope.py")
shutil.copyfile(STATE / "p13-flush-texts.json", folder / "flush-texts.json")
messages = {
    "flush": (
        "Bündige Passungen prüfen zusätzlich die vollständigen Körper\n\n"
        "Die unabhängige Körperprobe ergänzt die Ebenenregel für Netz und\n"
        "exakten Kern. Gleichgerichtete und getrennte koplanare Flächen\n"
        "bleiben zulässig; Körperbefunde behaupten keinen Flächenkontakt.\n"
        "Unklare Einbaulagen und gemischte Näherungen bleiben ausgewiesen.\n"
    ),
    "deviation": (
        "Formabweichung ganzer Originaldreiecke nachvollziehbar eingrenzen\n\n"
        "Belegte Teilflächen reisen durch Erkennung, Transformation und Cache.\n"
        "Die Analysekarte begrenzt ganze Dreiecke gegen ihre gespeicherten\n"
        "Ebenen, Zylinder, Kugeln, gerichteten Kegel und Ringtori. Numerische\n"
        "Breite, unbekannte Bereiche, Herkunft und ein wirklicher Zeuge\n"
        "bleiben bis zur übersetzten Anzeige und Ortsmarke erhalten.\n"
        "Berechnung und Veröffentlichung reichen Abbruch unverändert weiter.\n"
    ),
}
for scope, message in messages.items():
    (folder / f"{scope}-message.txt").write_text(
        message + "\nFenster- und Leistungsabnahme bleiben beim Release.\n"
        "\nCo-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8")
(STATE / "next-development-gate.txt").write_text(str(folder), encoding="utf-8")
print(json.dumps({"folder": str(folder), "head": snapshot["head"], "files": len(relevant)}))
