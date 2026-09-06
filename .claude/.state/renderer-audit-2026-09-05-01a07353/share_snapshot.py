"""Stellt ausschließlich eigene geprüfte Dateien aus einem festen Quellstand bereit."""

from pathlib import Path
import argparse
import hashlib
import json
import shutil

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--name", required=True)
args = parser.parse_args()
source = (root / args.source).resolve(strict=True)
target = (root / args.name).resolve()
if source.parent != root or target.parent != root or target.exists():
    raise ValueError("Quelle und neues Paket müssen direkte Audit-Unterordner sein")
manifest = json.loads((source / "audit-source-manifest.json").read_text(encoding="utf8"))
files = manifest["own_files_sha256"]
target.mkdir()
for name, expected in files.items():
    origin = source / name
    if hashlib.sha256(origin.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"Die feste Quelle änderte sich: {name}")
    destination = target / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origin, destination)
    if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"Die Kopie weicht ab: {name}")
result = {"base": manifest["base"], "files_sha256": files, "source": str(source),
          "copy_verified": True,
          "validation": "Gezielte Regressionen grün; vollständige native Modellmatrix und Tor noch offen. Runtimewechsel braucht eigene Prüfung."}
(target / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
print(target)
