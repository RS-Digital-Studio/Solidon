"""Nur den geprüften Viewport-Nachtrag zu V8 weiterreichen, ohne neuen AO-Code."""

from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parent
repository = root.parents[2]
base = root / "shared-fixes-v8"
output = root / "viewport-fixes-v9"
output.mkdir(exist_ok=False)
files = ("app/ui/viewport.py", "app/ui/CLAUDE.md",
         "tests/test_viewport_decisions.py", "tests/test_feature_label_layout.py")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


before = {name: digest(repository / name) for name in files}
for name in files:
    target = output / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repository / name, target)
assert before == {name: digest(repository / name) for name in files}
assert before == {name: digest(output / name) for name in files}
record = {"base_shared_source": str(base),
          "base_files_sha256": {name: digest(base / name) for name in files},
          "files_sha256": before, "copy_verified": True,
          "scope": "Cache der Bettentscheidung für tatsächlich gezeichnete Szene; echte Flächenanker in Schnittresten",
          "checks": {"old_v8": "8 failed, 1 passed; erwarteter Exit 1",
                     "current": "226 passed, tatsächlicher Exit 0",
                     "ruff_format_mypy": "grün; danach ausschließlich zwei Formatumbrüche in Tests",
                     "resource_overlap": "Ein fremder nativer VTK-Prozess überschnitt den frühen Lauf; keine Zeit-/FPS-Abnahme",
                     "native_followup": "noch ausstehend"}}
(output / "manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
print(output)
