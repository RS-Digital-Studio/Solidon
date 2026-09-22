"""Hält den gemeinsamen Entwicklungsstand und getrennte Commitumfänge fest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
folder = Path((Path(__file__).parent / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


nurbs = [
    "app/core/brep/CLAUDE.md", "app/core/brep/canonical.py", "app/core/brep/edit.py",
    "app/core/brep/features.py", "app/core/brep/kernel.py", "app/core/brep/ops.py",
    "app/core/brep/profiles.py", "app/core/brep/properties.py",
    "app/core/geom/CLAUDE.md", "app/core/geom/edge_ops.py", "app/core/geom/face_ops.py",
    "app/core/geom/ops.py", "app/core/geom/prepare_ops.py", "app/core/scene/CLAUDE.md",
    "app/core/scene/cache.py", "app/core/sketch/CLAUDE.md", "app/core/sketch/ops.py",
    "tests/test_brep_canonical_surfaces.py", "tests/test_brep_import_workflow.py",
    "tests/test_brep_trimmed_cylinder_centres.py", "tests/test_cache.py", "tests/test_solid_ownership.py",
    "tests/test_brep.py", "tests/test_sketch_ops.py",
]
ux = [
    ".claude/rules/agentenschicht.md", ".claude/rules/fenster.md", ".claude/rules/grenzen.md",
    ".claude/rules/oberflaeche.md", "3d-agent-bauplan.md", "app/cli/CLAUDE.md",
    "app/cli/__init__.py", "app/cli/main.py", "app/core/CLAUDE.md", "app/core/geom/CLAUDE.md",
    "app/core/geom/ops.py", "app/core/ingest/CLAUDE.md", "app/core/ingest/plan.py",
    "app/core/log.py", "app/core/paths.py", "app/core/report.py", "app/core/scene/CLAUDE.md",
    "app/core/scene/project.py", "app/ui/CLAUDE.md", "app/ui/app.py", "app/ui/main_window.py",
    "app/ui/panels.py", "app/ui/support_dialog.py", "pyproject.toml", "tests/test_cli.py",
    "tests/test_exact_body_parity.py", "tests/test_first_run.py", "tests/test_import_placement.py",
    "tests/test_registry_consistency.py",
    "app/core/backends/llm.py", "app/core/backends/CLAUDE.md",
    "tools/measure_local_model.py", "tools/CLAUDE.md", "tests/test_measure_local_model_security.py",
    "tests/test_support.py", "tests/test_ui.py", "tests/test_viewport_decisions.py", "tests/test_window_bench.py",
    *[f"app/i18n/locales/{language}.json" for language in ("en", "es", "fr", "it", "pt")],
]
docs = [
    "ROADMAP.md", "konzepte/README.md", "konzepte/konzept-bedienung.md",
    "konzepte/konzept-vollwertiges-cad-2026-09.md", "konzepte/durchsicht-cad-konzepte-2026-09.md",
]
policy = [
    ".githooks/pre-commit", "CLAUDE.md", "tests/test_delivery_tools.py", "tools/check_new_texts.py",
    ".claude/agents/oberflaechentexte.md", ".claude/agents/solidon3d-sprache.md",
    ".codex/agents/oberflaechentexte.toml", ".codex/agents/solidon3d-sprache.toml",
]

group = [
    ".claude/rules/agentenschicht.md", ".claude/rules/grenzen.md", ".claude/rules/oberflaeche.md",
    "3d-agent-bauplan.md", "app/core/geom/CLAUDE.md", "app/core/geom/ops.py",
    "app/core/ingest/CLAUDE.md", "app/core/ingest/plan.py", "app/ui/CLAUDE.md",
    "app/ui/main_window.py", "app/ui/panels.py", "tests/test_exact_body_parity.py",
    "tests/test_import_placement.py", "tests/test_registry_consistency.py", "tests/test_ui.py",
    "app/core/backends/llm.py", "app/core/backends/CLAUDE.md",
    "tools/measure_local_model.py", "tools/CLAUDE.md", "tests/test_measure_local_model_security.py",
    *[f"app/i18n/locales/{language}.json" for language in ("en", "es", "fr", "it", "pt")],
]
notice = [
    ".claude/rules/fenster.md", "app/ui/CLAUDE.md", "app/ui/main_window.py", "tests/test_ui.py",
    "tests/test_viewport_decisions.py", "tests/test_window_bench.py",
]
crash = sorted((set(ux) - set(group) - set(notice)) | {"app/ui/CLAUDE.md"} | {
    f"app/i18n/locales/{language}.json" for language in ("en", "es", "fr", "it", "pt")
})

assert not git("diff", "--cached", "--name-only").strip()
declared = set(nurbs + ux + docs + policy)
changed = set(git("diff", "--name-only", "HEAD").decode().splitlines())
untracked = set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
untracked = {path for path in untracked if not path.startswith(".claude/.state/")}
assert changed | untracked <= declared, sorted((changed | untracked) - declared)

for scope, paths in (("policy", policy), ("nurbs", nurbs), ("group", group), ("crash", crash), ("notice", notice), ("docs", docs)):
    (folder / f"{scope}-paths.json").write_text(json.dumps(sorted(paths), indent=2), encoding="utf-8")

relevant = set(git("ls-files", "app", "tests", "tools", ".claude/rules", "AGENTS.md", "CLAUDE.md", "pyproject.toml", "constraints.txt", "3d-agent-bauplan.md").decode().splitlines())
relevant |= declared | untracked
snapshot = {
    "head": git("rev-parse", "HEAD").decode().strip(),
    "files": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sorted(relevant)},
}
(folder / "snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "docs-snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "initial-status.txt").write_bytes(git("status", "--short"))
print(json.dumps({"folder": str(folder), "head": snapshot["head"], "files": len(snapshot["files"])}))
