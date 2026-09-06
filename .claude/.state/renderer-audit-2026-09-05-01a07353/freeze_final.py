"""Kombiniert geprüfte Erkennung und eigene UI-Dateien in einer neuen festen Kopie."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

root = Path(__file__).resolve().parent
repository = root.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--core-source", type=Path, required=True)
parser.add_argument("--name", default="final-source-v3")
args = parser.parse_args()
core = args.core_source.resolve(strict=True)
destination = (root / args.name).resolve()
if destination.parent != root or destination.exists():
    raise ValueError("Der neue Quellstand braucht einen unbenutzten direkten Audit-Unterordner")

owned = (
    "app/ui/render/gfx_renderer.py", "app/ui/render/gfx_occlusion.py",
    "app/ui/render/gfx_lines.py", "app/ui/render/vtk_renderer.py",
    "app/ui/render/api.py",
    "app/ui/viewport.py", "app/ui/render/CLAUDE.md", "app/ui/CLAUDE.md",
    "tests/test_render_gfx_regressions.py", "tests/test_render_vtk_presentation.py",
    "tests/test_selection.py", "tests/test_viewport_decisions.py",
    "tests/test_feature_label_layout.py", "tests/test_viewport_pending_transform.py",
)

def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((folder / "app").rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}

before = hashes(core)
own_before = {name: hashlib.sha256((repository / name).read_bytes()).hexdigest() for name in owned}
destination.mkdir()
shutil.copytree(core / "app", destination / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
shutil.copytree(root / "baseline-source/tools", destination / "tools", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
for name in ("pyproject.toml", "constraints.txt"):
    shutil.copy2(root / "baseline-source" / name, destination / name)
for name in owned:
    target = destination / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repository / name, target)
after = hashes(core)
own_after = {name: hashlib.sha256((repository / name).read_bytes()).hexdigest() for name in owned}
if before != after or own_before != own_after:
    raise RuntimeError("Eine Quelle änderte sich beim Kopieren; diese Kopie ist nicht freigegeben")
manifest = {"core_source": str(core), "core_files_sha256": before,
            "own_files_sha256": own_before, "final_app_files_sha256": hashes(destination),
            "base": "782f98bb", "copy_verified": True}
(destination / "audit-source-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
print(destination)
