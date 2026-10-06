"""Sonde: Welche Merkmale trägt der Stift ohne und mit Erkennung, und woher?"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def main() -> None:
    tree, project_path, out_path = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    out = open(out_path, "w", encoding="utf-8", buffering=1)
    home = Path(tempfile.mkdtemp(prefix="sonde_merkmale_"))
    os.environ["APPDATA"] = str(home / "roaming")
    os.environ["LOCALAPPDATA"] = str(home / "local")
    sys.path.insert(0, tree)
    from app.core.bootstrap import load_operations
    from app.core.scene import project as project_module
    from app.core.scene.evaluate import evaluate
    from app.core.knowledge import profiles

    load_operations()
    project = project_module.load(project_path)
    out.write(f"Projekt geladen: {project is not None}\n")
    document = project.document
    from app.cli.main import profile_of
    profile = profile_of(project)
    out.write(f"Profil: {profile is not None}\n")
    sources = project_module.ProjectSources(project)
    for detect in (False, True):
        result = evaluate(document, profile, sources=sources, detect_features=detect, quality="draft")
        entry = result.scene.objects.get("obj_3")
        out.write(f"\nErkennung={detect}: angehalten={result.stopped_at}\n")
        if entry is None:
            continue
        for fid, feature in entry.features.items():
            out.write(
                f"  {fid}: {feature.kind} prov={getattr(feature, 'provenance', None)} "
                f"by={feature.created_by} params={ {k: v for k, v in feature.params.items() if k in ('diameter', 'depth', 'through', 'span')} }\n"
            )
    out.close()
    os._exit(0)


if __name__ == "__main__":
    main()
