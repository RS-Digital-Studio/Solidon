"""Bei welchem Baustein landen erkannte Flächen heute beim Körper?

Je Baustein: Quader bauen, Baustein einsetzen, auswerten. Gezählt wird, welche
erkannten Flächen der Bausteinschritt über ``created_by`` bekommt (der heutige
Weg) und welche zusätzlich über ``shaped_by`` (der Umbau).
"""

from __future__ import annotations

from app.core.bootstrap import load_operations
from app.core.knowledge.parts import PARTS
from app.core.knowledge.profiles import make_profile
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft
from app.core.scene.evaluate import evaluate
from app.core.scene.project import ProjectSources, new_project

load_operations()
profil = make_profile("centauri-carbon-2", "petg")


def messen(name: str) -> tuple[int, int, int] | str:
    op_name = f"insert_{name}"
    if op_name not in {spec.name for spec in REGISTRY.all()}:
        return "keine insert-Operation"
    projekt = new_project("centauri-carbon-2", "petg")
    try:
        History(projekt.document).apply(
            "Aufbau",
            [
                OperationDraft(
                    op="create_box", params={"width": 60.0, "depth": 60.0, "height": 12.0}
                ),
                OperationDraft(op=op_name, inputs=("obj_1",), params={"z": 12.0}),
            ],
        )
        ergebnis = evaluate(projekt.document, profil, sources=ProjectSources(projekt))
    except Exception as fehler:  # noqa: BLE001 — Sonde
        return f"{type(fehler).__name__}: {str(fehler)[:60]}"
    eintrag = ergebnis.scene.objects.get("obj_1")
    if eintrag is None:
        return "kein Ergebnisobjekt"
    schritt = 2
    erkannt = [f for f in eintrag.features.values() if f.provenance == "detected"]
    ueber_created = [f for f in erkannt if f.created_by == schritt]
    nur_shaped = [f for f in erkannt if f.created_by is None and f.shaped_by == schritt]
    return (len(erkannt), len(ueber_created), len(nur_shaped))


treffer = []
for name in sorted(PARTS.versions()):
    ergebnis = messen(name)
    if isinstance(ergebnis, str):
        print(f"{name:22s} — {ergebnis}")
        continue
    erkannt, ueber_created, nur_shaped = ergebnis
    marke = "   <<< der Umbau greift" if nur_shaped else ""
    if nur_shaped:
        treffer.append((name, nur_shaped))
    print(
        f"{name:22s} erkannt {erkannt:3d}  am Baustein {ueber_created:3d}  "
        f"nur über shaped_by {nur_shaped:3d}{marke}"
    )

print()
print(f"{len(treffer)} Bausteine, bei denen der Umbau Flächen umhängt:")
for name, anzahl in treffer:
    print(f"   {name}: {anzahl}")
