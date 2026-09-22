"""Liest beide Materialfälle des unveränderten alten Passungskorpus."""

import json
import os
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
private = tempfile.mkdtemp(prefix="solidon-corpus-fit-")
for key in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[key] = private

from app.core.bootstrap import load_operations
from app.core.knowledge import profiles
from app.core.scene import evaluate
from app.core.scene.fits import resolve, target
from app.core.scene.project import ProjectSources, load

load_operations()
for material in ("petg", "pla"):
    opened = load(root / "tests/data/projects/assembly_fit.p3d")
    profile = profiles.make_profile("centauri-carbon-2", material)
    result = evaluate(opened.document, profile, sources=ProjectSources(opened))
    fit = result.scene.fits[0]
    print(json.dumps({
        "material": material, "fit": str(fit), "target": target(result.scene, fit, profile),
        "a": dict(resolve(result.scene, fit.a).params),
        "b": dict(resolve(result.scene, fit.b).params),
        "findings": [{"code": f.code, "values": dict(f.values)} for f in result.scene.report.findings if f.code.startswith("fit.")],
    }, default=str), flush=True)
