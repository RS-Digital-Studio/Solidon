"""Staget Maß- und Passungspaket ohne Eingriff in den gemeinsamen Arbeitsbaum."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path("F:/3D Druck")
folder = Path(__file__).parent
scope = sys.argv[1]
paths = sorted(json.loads((folder / f"{scope}-paths.json").read_text(encoding="utf-8")))
assert paths and len(paths) == len(set(paths))
assert all(not path.startswith("website/") for path in paths)
environment = dict(os.environ, SOLIDON_KEIN_PUSH="1", PYTHONUTF8="1")
environment.pop("GIT_INDEX_FILE", None)


def git(*args: str, env=environment, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, env=env, input=data,
                          capture_output=True, check=True).stdout


def old(path: str) -> str:
    return git("show", f"{head}:{path}").decode("utf-8")


def current(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def without(text: str, first: str, next_: str | None) -> str:
    assert text.count(first) == 1
    start = text.index(first)
    if next_ is None:
        return text[:start]
    assert text.count(next_) == 1
    end = text.index(next_)
    assert end > start
    return text[:start] + text[end:]


def function_range(text: str, name: str) -> tuple[int, int]:
    nodes = [node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(nodes) == 1, name
    node = nodes[0]
    first = min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
    lines = text.splitlines(keepends=True)
    return sum(map(len, lines[:first - 1])), sum(map(len, lines[:node.end_lineno]))


def messages(text: str) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(text)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in {"_", "tr", "site_text"} and node.args
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            found.add(node.args[0].value)
    return found


assert not git("diff", "--cached", "--name-only").strip()
head = git("rev-parse", "HEAD").decode().strip()
main_index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
main_hash = hashlib.sha256(main_index.read_bytes()).hexdigest()
index = folder / f"{scope}.index"
private = dict(environment, GIT_INDEX_FILE=str(index))
git("read-tree", head, env=private)
git("add", "--", *paths, env=private)
overrides: dict[str, str] = {}
if scope == "measures":
    path = "tests/test_digest_and_fits.py"
    text, original = current(path), old(path)
    names = [
        "test_a_coarse_circle_measure_does_not_prove_actual_mesh_clearance",
        "test_fine_contours_keep_the_existing_measurable_fit_contract",
        "test_incomplete_mesh_band_does_not_fall_back_to_a_successful_circle_measure",
        "test_thread_fit_accepts_either_matching_handedness",
        "test_threads_need_opposite_roles_and_the_same_pitch",
        "test_a_fit_that_matches_the_profile_says_nothing",
        "test_a_conditional_fit_requires_its_document_without_blaming_the_step",
        "test_the_tolerance_follows_the_material", "test_a_softer_body_gets_its_own_clearance",
        "test_a_named_material_stays_what_it_says", "test_a_press_fit_takes_the_gentler_number",
    ]
    for name in names:
        new_name = ("test_matching_profile_dimensions_leave_the_installation_pose_open"
                    if name == "test_a_fit_that_matches_the_profile_says_nothing" else name)
        a, b = function_range(text, new_name)
        first, last = function_range(original, name)
        text = text[:a] + original[first:last] + text[b:]
    overrides[path] = text
    sections = {
        "app/core/scene/CLAUDE.md": ("Zusätzlich prüft `fits.check(..., cancelled=...)`", "`fits.active_fits(document)`"),
        "app/core/geom/CLAUDE.md": ("`measure.body_overlap` misst", None),
        "app/core/perceive/CLAUDE.md": ("Die Passungskarte übernimmt ausschließlich", "`slots.open_slots_instead_of_fillets`"),
        "app/ui/CLAUDE.md": ("Die Exportvorprüfung nutzt", "`PlacementFlow` bietet"),
    }
    for path, (first, next_) in sections.items():
        overrides[path] = without(current(path), first, next_)
    second_keys: set[str] = set()
    for path in ("app/core/scene/fits.py", "app/core/perceive/maps.py", "app/ui/main_window.py", "app/core/tour.py"):
        second_keys |= messages(current(path)) - messages(old(path))
    assert len(second_keys) >= 10, second_keys
    old_tour_keys = messages(old("app/core/tour.py")) - messages(current("app/core/tour.py"))
    for path in paths:
        if path.startswith("app/i18n/locales/"):
            complete, original = json.loads(current(path)), json.loads(old(path))
            assert second_keys.isdisjoint(original) and second_keys <= complete.keys()
            for key in second_keys:
                del complete[key]
            for key in old_tour_keys:
                assert key in original
                complete[key] = original[key]
            overrides[path] = json.dumps(dict(sorted(complete.items())), ensure_ascii=False, indent=2) + "\n"
    (folder / "fits-message-keys.json").write_text(json.dumps(sorted(second_keys), ensure_ascii=False, indent=2), encoding="utf-8")

for path, content in overrides.items():
    blob = content.encode("utf-8")
    if path.endswith(".py"):
        blob = subprocess.run(
            [str(ROOT / ".venv/Scripts/python.exe"), "-m", "ruff", "format", "--stdin-filename", path],
            cwd=ROOT, input=blob, capture_output=True, check=True,
        ).stdout
        subprocess.run(
            [str(ROOT / ".venv/Scripts/python.exe"), "-m", "ruff", "check", "--stdin-filename", path],
            cwd=ROOT, input=blob, capture_output=True, check=True,
        )
        ast.parse(blob, filename=path)
    saved = folder / f"{scope}-blobs" / path
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(blob)
    oid = git("hash-object", "-w", "--stdin", data=blob).decode().strip()
    git("update-index", "--cacheinfo", f"100644,{oid},{path}", env=private)
staged = git("diff", "--cached", "--name-only", env=private).decode().splitlines()
assert staged == paths, (staged, paths)
git("diff", "--cached", "--check", env=private)
(folder / f"{scope}-stage.diff").write_bytes(git("diff", "--cached", env=private))
assert head == git("rev-parse", "HEAD").decode().strip()
assert main_hash == hashlib.sha256(main_index.read_bytes()).hexdigest()
report = {"head": head, "index": str(index), "main_index_sha256": main_hash, "paths": paths}
(folder / f"{scope}-stage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"scope": scope, "paths": len(paths), "head": head}))
