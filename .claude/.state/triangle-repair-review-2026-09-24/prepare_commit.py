"""Stellt nur die eigenen Änderungen in einem privaten Index bereit."""

import ast
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path.cwd()
AUDIT = ROOT / ".claude/.state/triangle-repair-review-2026-09-24"
ENV = dict(os.environ, GIT_INDEX_FILE=str(AUDIT / "review.index"))


def git(*arguments, data=None, private=False):
    result = subprocess.run(
        ["git", *arguments],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        env=ENV if private else None,
    )
    return result.stdout


def base(path):
    return git("show", f"HEAD:{path}").decode("utf-8")


def stage_text(path, text):
    identifier = git("hash-object", "-w", "--stdin", data=text.encode("utf-8")).decode().strip()
    git("update-index", "--add", "--cacheinfo", "100644", identifier, path, private=True)


def selected_hunks(path, markers):
    patch = git("diff", "HEAD", "--", path).decode("utf-8")
    pieces = re.split(r"(?=^@@ )", patch, flags=re.MULTILINE)
    selected = [piece for piece in pieces[1:] if any(marker in piece for marker in markers)]
    if not selected:
        raise RuntimeError(f"Eigene Änderung fehlt: {path}")
    git("apply", "--cached", "-", data=(pieces[0] + "".join(selected)).encode(), private=True)


def function_text(text, name):
    node = next(entry for entry in ast.parse(text).body if isinstance(entry, ast.FunctionDef) and entry.name == name)
    first = min([node.lineno, *(entry.lineno for entry in node.decorator_list)])
    return "\n".join(text.splitlines()[first - 1 : node.end_lineno])


def stage_test_functions(path, added, before, replaced=()):
    original = base(path)
    current = (ROOT / path).read_text(encoding="utf-8")
    following = function_text(original, before)
    block = "\n\n\n".join(function_text(current, name) for name in added)
    staged = original.replace(following, block + "\n\n\n" + following, 1)
    for name in replaced:
        staged = staged.replace(function_text(original, name), function_text(current, name), 1)
    stage_text(path, staged)


git("read-tree", "HEAD", private=True)
full = [
    "app/core/geom/repair.py", "app/core/geom/ops.py", "app/core/perceive/maps.py",
    "app/ui/panels.py", "app/ui/local_recognition.py", "tests/test_maps.py",
    "tests/test_repair.py", "tests/test_repair_features.py", "tests/data/repair_features.json",
    "tests/data/README.md",
    "app/core/ingest/ops.py", "tests/test_errors.py",
]
git("add", "--", *full, private=True)
selected_hunks("app/core/perceive/local.py", ['constraint="local_boundary"'])
selected_hunks("app/core/errors.py", ['+RECOGNIZE_LOCAL ='])
selected_hunks("app/core/perceive/CLAUDE.md", ["+`local_error`", "+Die Netzfehlerkarte übernimmt"])
selected_hunks("app/core/geom/CLAUDE.md", ["+Normalenkorrekturen vergleichen"])
selected_hunks("app/ui/CLAUDE.md", ["+Die Fehlerursache `local_<reason>`"])
flow_path = "app/ui/local_recognition_flow.py"
flow = (ROOT / flow_path).read_text(encoding="utf-8")
for foreign in (
    "        if not self.view._quiet_command_allowed():\n            return\n",
    "        if self.view._quiet_host is not None:\n            self.view.end_quiet_placement()\n",
):
    assert foreign not in base(flow_path)
    flow = flow.replace(foreign, "")
stage_text(flow_path, flow)
selected_hunks("app/ui/main_window.py", ['+            "recognize_local":'])
selected_hunks("app/ui/viewport.py", [
    "+        self._surface_picker:", "+    def set_surface_picker(",
    "+        self._place_surface_picker()", "+        if self._surface_picker_key(event):",
])
selected_hunks(".claude/rules/oberflaeche.md", ["+ **Lokale Formenerkennung", "+- **Lokale Formenerkennung"])
selected_hunks("tests/test_local_detection.py", ["+def test_local_errors_identify"])
selected_hunks("tests/test_ui.py", ["+def test_intersection_repair_advice"])
selected_hunks("ROADMAP.md", ["+| [RM-238", '+<a id="rm-238"'])
stage_test_functions(
    "tests/test_local_recognition_ui.py",
    [
        entry.name
        for entry in ast.parse((ROOT / "tests/test_local_recognition_ui.py").read_text(encoding="utf-8")).body
        if isinstance(entry, ast.FunctionDef) and (
            entry.name.startswith("test_local_report_")
            or entry.name in {
                "test_local_error_correction_follows_the_structured_cause",
                "test_local_worker_preserves_the_error_cause_for_the_dialog",
                "_local_report_flow_stub",
            }
        )
    ],
    "make_dialog",
    ["test_ray_with_no_original_hit_never_uses_the_lod_placeholder"],
)
stage_test_functions(
    "tests/test_local_recognition_flow.py",
    ["test_bad_surface_can_be_picked_again_without_a_document_change",
     "test_surface_picker_keys_use_device_pixels_and_keep_unrelated_keys",
     "test_surface_picker_position_is_clamped_and_drawn_in_logical_pixels",
     "test_keyboard_surface_choice_opens_local_recognition_and_cancel_hides_the_crosshair"],
    "test_failed_preview_stays_visible_and_cannot_be_accepted",
)

tree = ast.parse((AUDIT / "update_translations.py").read_text(encoding="utf-8"))
tables = {entry.targets[0].id: ast.literal_eval(entry.value) for entry in tree.body if isinstance(entry, ast.Assign) and isinstance(entry.targets[0], ast.Name) and entry.targets[0].id in {"TEXTS", "REMOVED"}}
for language in ("en", "es", "fr", "it", "pt"):
    path = f"app/i18n/locales/{language}.json"
    catalog = json.loads(base(path))
    current = json.loads((ROOT / path).read_text(encoding="utf-8"))
    for key in tables["TEXTS"]:
        catalog[key] = current[key]
    for key in tables["REMOVED"]:
        if key not in current:
            catalog.pop(key, None)
    stage_text(path, json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

git("diff", "--cached", "--check", private=True)
(AUDIT / "staged.patch").write_bytes(git("diff", "--cached", "HEAD", private=True))
(AUDIT / "staged-head.txt").write_bytes(git("rev-parse", "HEAD"))
print(git("diff", "--cached", "--stat", private=True).decode())
