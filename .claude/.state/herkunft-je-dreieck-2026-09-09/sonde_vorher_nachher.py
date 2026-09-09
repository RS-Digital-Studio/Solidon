"""Was ändert der Umbau für das Projekt aus dem Bild — vorher gegen nachher?"""

from __future__ import annotations

from pathlib import Path

from app.core.bootstrap import load_operations
from app.core.knowledge.profiles import make_profile
from importlib import import_module
from app.core.scene.evaluate import evaluate

evaluate_modul = import_module("app.core.scene.evaluate")
from app.core.scene.project import ProjectSources
from app.core.scene.project import load as load_project

load_operations()


def lauf(mit_umbau: bool) -> dict[str, int | None]:
    if not mit_umbau:
        evaluate_modul._from_the_mesh = lambda features, mesh: features
    projekt = load_project(Path("app/examples/weg2-halter-konstruieren.p3d"))
    ergebnis = evaluate(
        projekt.document, make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(projekt),
    )
    eintrag = ergebnis.scene.objects["obj_1"]
    return {
        kennung: (merkmal.created_by or getattr(merkmal, "shaped_by", None))
        for kennung, merkmal in eintrag.features.items()
    }


echt = evaluate_modul._from_the_mesh
nachher = lauf(True)
vorher = lauf(False)
evaluate_modul._from_the_mesh = echt

print(f"{'Merkmal':24s} {'vorher':>8s} {'nachher':>8s}")
geaendert = 0
for kennung in sorted(set(vorher) | set(nachher)):
    a, b = vorher.get(kennung), nachher.get(kennung)
    marke = "   <<<" if a != b else ""
    if a != b:
        geaendert += 1
    print(f"{kennung:24s} {str(a):>8s} {str(b):>8s}{marke}")
print(f"\n{geaendert} Merkmale hängen jetzt woanders")
