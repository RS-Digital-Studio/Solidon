"""Ein geändertes Merkmal behält seinen Platz (FD-161).

Nach *Bohrung ändern* stand die Bohrung im Objektbaum am Ende der Liste: Die
Auswertung hängte die Merkmale, die der Schritt selbst ausgibt (``declared``),
hinter die neu zugeordneten (``scene.evaluate._with_features``), und der Baum
zeigt die Merkmale in der Folge des Ergebnisses. Wer eine Bohrung ändert,
sucht sie danach neu — an der Platte mit vier Bohrungen nach jeder Änderung.
"""

from __future__ import annotations

from app.core.scene import OperationDraft, evaluate
from app.core.scene.project import ProjectSources
from app.core.types import Document, Profile
from app.i18n import _
from tests.test_prepare import loaded


def test_a_resized_hole_keeps_its_place_among_the_features(
    document: Document, profile: Profile
) -> None:
    project, history = loaded(document, "plate_holes.stl")
    first = evaluate(document, profile, sources=ProjectSources(project))
    before = list(first.scene.objects["obj_1"].features)
    assert before[0] == "hole_1" and len(before) > 2, before

    history.apply(
        _("Bohrung ändern"),
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                outputs=("obj_1",),
                params={"at_feature": "hole_1", "diameter": 7.0},
            )
        ],
    )
    second = evaluate(document, profile, sources=ProjectSources(project))

    after = list(second.scene.objects["obj_1"].features)
    assert after == before, f"vorher {before}, nachher {after}"


def test_a_new_feature_stands_with_its_kind(document: Document, profile: Profile) -> None:
    """Gegenprobe: Eine neue Bohrung hat keinen alten Platz und steht, wo die Erkennung sie
    findet — bei den Bohrungen, nicht hinter den Flächen. Die bekannten behalten ihre Folge."""
    project, history = loaded(document, "plate_holes.stl")
    first = evaluate(document, profile, sources=ProjectSources(project))
    before = list(first.scene.objects["obj_1"].features)
    history.apply(
        _("Bohren"),
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                outputs=("obj_1",),
                params={"diameter": 3.0, "axis": "z"},
            )
        ],
    )
    second = evaluate(document, profile, sources=ProjectSources(project))

    after = list(second.scene.objects["obj_1"].features)
    known = [name for name in after if name in before]
    assert known == [name for name in before if name in after]
    new = [name for name in after if name not in before]
    assert new == ["hole_5"], after
    assert after.index("hole_5") < after.index("face_1"), after
