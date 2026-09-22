"""Staget ausschließlich benannte Pfade, gemeinsame Dateien je geprüftem Teilumfang."""

from __future__ import annotations

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


assert not git("diff", "--cached", "--name-only").strip()
head = git("rev-parse", "HEAD").decode().strip()
main_index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
main_hash = hashlib.sha256(main_index.read_bytes()).hexdigest()
index = folder / f"{scope}.index"
private = dict(environment, GIT_INDEX_FILE=str(index))
git("read-tree", head, env=private)
git("add", "--", *paths, env=private)

overrides: dict[str, str] = {}
if scope == "void":
    path = "app/core/perceive/CLAUDE.md"
    text = (ROOT / path).read_text(encoding="utf-8")
    start = text.index("`bore_action` bietet nach bestätigter Zuordnung")
    end = text.index("Zwei Entscheidungen darin sind Absicht", start)
    overrides[path] = text[:start] + text[end:]

    path = "app/core/scene/cache.py"
    text = (ROOT / path).read_text(encoding="utf-8")
    native = ("#: Native Merkmale erhalten außerdem dieselbe eindeutige Erzeugerzuordnung\n"
              "#: wie Netzmerkmale; alte Auskünfte ohne diesen Bezug werden neu ausgewertet.\n")
    assert text.count(native) == 1 and text.count("CACHE_FORMAT_VERSION: Final = 14") == 1
    overrides[path] = text.replace(native, "").replace("CACHE_FORMAT_VERSION: Final = 14", "CACHE_FORMAT_VERSION: Final = 13")

    path = "tests/test_cache.py"
    text = (ROOT / path).read_text(encoding="utf-8")
    assert text.count("12, 13]") == 2
    overrides[path] = text.replace("12, 13]", "12]")

catalog_keys = {
    "void": {
        "Die geschlossenen Innenflächen lassen sich nicht zuverlässig zuordnen. Prüfen Sie den Körper oder reparieren Sie eine Arbeitskopie.",
    },
    "bore": {
        "Bohrung im ursprünglichen Schritt ändern",
        "Zeigt die ursprünglichen Schrittwerte vor späteren Größen- und Lageänderungen. Tiefe 0 bohrt durch das ganze Teil.",
    },
}
if scope in catalog_keys:
    keys = catalog_keys[scope]
    for path in paths:
        if path.startswith("app/i18n/locales/"):
            original = json.loads(git("show", f"{head}:{path}"))
            current = json.loads((ROOT / path).read_text(encoding="utf-8"))
            assert keys.isdisjoint(original) and keys <= current.keys()
            original.update({key: current[key] for key in keys})
            overrides[path] = json.dumps(dict(sorted(original.items())), ensure_ascii=False, indent=2) + "\n"

for path, content in overrides.items():
    blob = content.encode("utf-8")
    saved = folder / f"{scope}-blobs" / path
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(blob)
    oid = git("hash-object", "-w", "--stdin", data=blob).decode().strip()
    git("update-index", "--cacheinfo", f"100644,{oid},{path}", env=private)

staged = git("diff", "--cached", "--name-only", env=private).decode().splitlines()
assert staged == paths, (staged, paths)
git("diff", "--cached", "--check", env=private)
for flag, label in (("--name-only", "names"), ("--numstat", "numstat")):
    (folder / f"{scope}-stage-{label}.txt").write_bytes(git("diff", "--cached", flag, env=private))
(folder / f"{scope}-stage.diff").write_bytes(git("diff", "--cached", env=private))
assert head == git("rev-parse", "HEAD").decode().strip()
assert main_hash == hashlib.sha256(main_index.read_bytes()).hexdigest()
report = {"head": head, "index": str(index), "main_index_sha256": main_hash, "paths": paths}
(folder / f"{scope}-stage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"scope": scope, "paths": len(paths), "head": head}))
