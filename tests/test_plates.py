"""Mehrere Druckplatten in einer Szene (Bauplan §25, §29).

Mehr Teile, als auf eine Platte passen, ist der Normalfall, sobald jemand einen
Satz von etwas druckt. Was nicht passieren darf, ist, dass das Anordnen sie
still übereinanderstapelt oder der Export Dateien schreibt, die niemand
auseinanderhalten kann.
"""

from __future__ import annotations

import pytest
import trimesh
from PySide6.QtWidgets import QApplication

from app.core.export.writer import plan_export
from app.core.geom.mesh import MeshData
from app.core.geom.prepare import MAX_PLATES, arrange_on_bed, check_build_volume, check_collisions
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject
from app.ui.explode_bar import ALL_PLATES, ExplodeBar


def slab(size: float = 120.0) -> MeshData:
    """Eine Platte auf dem Bett — alles unter Z = 0 ist außerhalb des Raums."""
    body = trimesh.creation.box(extents=(size, size, 10.0))
    body.apply_translation((0.0, 0.0, 5.0))
    return MeshData.of(body)


def many(count: int, size: float = 120.0) -> list[MeshData]:
    return [slab(size) for _ in range(count)]


# --- arranging ------------------------------------------------------------------


def test_what_fits_stays_on_one_plate(profile: Profile) -> None:
    result = arrange_on_bed(many(4), profile, spacing=5.0, plates=4)

    assert result.plates == [0, 0, 0, 0]
    assert result.plate_count == 1
    assert not result.findings


def test_what_does_not_fit_goes_on_the_next_plate(profile: Profile) -> None:
    """Vier 120-mm-Platten passen auf eine 256er; neun nicht."""
    result = arrange_on_bed(many(9), profile, spacing=5.0, plates=4)

    assert result.plate_count > 1
    assert sorted(set(result.plates)) == list(range(result.plate_count))
    assert not result.findings, "spread over enough plates, nothing sticks out"


def test_each_plate_is_checked_on_its_own(profile: Profile) -> None:
    result = arrange_on_bed(many(9), profile, spacing=5.0, plates=4)

    for plate in range(result.plate_count):
        on_plate = [
            mesh for mesh, entry in zip(result.meshes, result.plates, strict=True) if entry == plate
        ]
        assert not check_build_volume(on_plate, profile), f"plate {plate}"
        assert not check_collisions(on_plate), f"plate {plate}"


def test_two_parts_at_the_same_spot_on_different_plates_are_fine(profile: Profile) -> None:
    """Ohne Platten wäre das die Kollision, die es nie gibt."""
    result = arrange_on_bed(many(9), profile, spacing=5.0, plates=4)

    first = [mesh for mesh, plate in zip(result.meshes, result.plates, strict=True) if plate == 0]
    second = [mesh for mesh, plate in zip(result.meshes, result.plates, strict=True) if plate == 1]

    assert first and second
    assert check_collisions([first[0], second[0]]), "they do overlap in space"
    assert not check_collisions(first) and not check_collisions(second), "but not on a plate"


def test_one_plate_too_few_is_said_rather_than_hidden(profile: Profile) -> None:
    """Nichts fällt weg — die letzte Platte nimmt den Rest, und der Bericht
    sagt es.
    """
    result = arrange_on_bed(many(9), profile, spacing=5.0, plates=1)

    assert len(result.meshes) == 9, "every part is placed"
    assert "arrange.needs_more_plates" in {finding.code for finding in result.findings}


def test_the_upper_limit_is_a_number_somebody_chose() -> None:
    assert MAX_PLATES == 12


def deep_slab(depth: float) -> MeshData:
    """Ein Teil, das tiefer ist, als das Bett hergibt."""
    body = trimesh.creation.box(extents=(160.0, depth, 14.0))
    body.apply_translation((0.0, 0.0, 7.0))
    return MeshData.of(body)


def test_the_first_plate_is_never_left_empty(profile: Profile) -> None:
    """Ein zu tiefes Teil darf nicht auf die nächste Platte weiterwandern,
    solange die aktuelle noch leer ist.

    So gefunden: zwei Sockel von 231 mm Tiefe, zwei Platten — beide landeten
    auf Platte 2, aufeinandergestapelt, während Platte 1 leer blieb.
    """
    parts = [deep_slab(profile.printer.build_volume[1] + 12.0) for _ in range(2)]

    result = arrange_on_bed(parts, profile, spacing=6.0, plates=2)

    assert result.plates == [0, 1], "one per plate, starting at the first"
    assert min(result.plates) == 0


def test_more_plates_are_only_offered_when_they_would_help(profile: Profile) -> None:
    """Ein einzelnes Teil, das auf kein Bett passt, bekommt keinen Rat, der
    nichts löst (Regel 17).
    """
    too_deep = profile.printer.build_volume[1] + 12.0
    parts = [deep_slab(too_deep) for _ in range(2)]

    result = arrange_on_bed(parts, profile, spacing=6.0, plates=2)

    codes = {finding.code for finding in result.findings}
    assert "arrange.needs_more_plates" not in codes, "another plate changes nothing here"
    assert "arrange.out_of_build_volume" in codes, "but the size is still said"


def test_a_part_in_exactly_bed_size_does_not_ask_for_a_plate_either(profile: Profile) -> None:
    """„Passt allein" heißt „würde allein passend gelegt".

    Ein Teil in genau Bettgröße passt roh und ragt nach dem Anordnen dennoch
    über den Rand — der Abstand steht auf beiden Seiten. Ohne ihn in der
    Rechnung wäre der Rat wieder einer, der nichts löst.
    """
    width, depth, _height = profile.printer.build_volume
    exact = trimesh.creation.box(extents=(width, depth, 10.0))
    exact.apply_translation((0.0, 0.0, 5.0))
    parts = [MeshData.of(exact), MeshData.of(exact.copy())]

    result = arrange_on_bed(parts, profile, spacing=5.0, plates=2)

    codes = {finding.code for finding in result.findings}
    assert "arrange.needs_more_plates" not in codes
    assert "arrange.out_of_build_volume" in codes, "der Abstand ragt hinaus, und das steht da"


def test_crowding_still_asks_for_another_plate(profile: Profile) -> None:
    """Der Rat bleibt, wo er stimmt: viele Teile, die einzeln passen."""
    result = arrange_on_bed(many(9), profile, spacing=5.0, plates=1)

    assert "arrange.needs_more_plates" in {finding.code for finding in result.findings}


# --- Als Operation ---------------------------------------------------------------


def test_arranging_writes_the_plate_onto_the_objects(profile: Profile) -> None:
    objects = [
        SceneObject(id=f"obj_{index}", name=f"Teil {index}", mesh=slab()) for index in range(9)
    ]
    spec = REGISTRY.get("arrange_bed")

    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry for entry in objects}),
            inputs=objects,
            params=spec.params(spacing=5.0, plates=4),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )

    plates = {output.plate for output in result.outputs}
    assert len(plates) > 1
    assert all(output.plate >= 0 for output in result.outputs)


# --- export ---------------------------------------------------------------------


def test_the_plate_lands_in_the_file_name(profile: Profile) -> None:
    objects = [
        SceneObject(id="obj_1", name="Deckel", mesh=slab(), plate=0),
        SceneObject(id="obj_2", name="Boden", mesh=slab(), plate=1),
    ]

    plan = plan_export(objects, project_name="Kiste", profile=profile)

    assert [entry.filename for entry in plan.entries] == [
        "Kiste_platte1_Deckel_1von2.stl",
        "Kiste_platte2_Boden_2von2.stl",
    ]


def test_one_plate_keeps_the_plain_name(profile: Profile) -> None:
    objects = [SceneObject(id="obj_1", name="Deckel", mesh=slab(), plate=0)]

    plan = plan_export(objects, project_name="Kiste", profile=profile)

    assert plan.entries[0].filename == "Kiste_Deckel.stl"


def test_the_export_check_knows_which_plate_complains(profile: Profile) -> None:
    from app.core.geom.transform import apply, translation

    far = MeshData.of(slab().raw.copy())
    far = apply(far, translation((400.0, 0.0, 0.0)))
    objects = [
        SceneObject(id="obj_1", name="Gut", mesh=slab(), plate=0),
        SceneObject(id="obj_2", name="Weit", mesh=far, plate=1),
    ]

    plan = plan_export(objects, project_name="Kiste", profile=profile)

    outside = [entry for entry in plan.findings if entry.code == "arrange.out_of_build_volume"]
    assert [entry.values["plate"] for entry in outside] == [2]


# --- der Wähler -----------------------------------------------------------------


def test_the_selector_appears_from_two_plates_on(qt_app: QApplication) -> None:
    """``isVisibleTo`` und nicht ``isVisible``: die Leiste selbst zeigt sich
    nicht mehr — das tut die Werkzeugzeile, wenn jemand ihren Knopf drückt.
    Gefragt ist hier, ob der Wähler *innerhalb* der Leiste dazugehört.
    """
    bar = ExplodeBar()

    bar.show_for(3, plates=1)
    assert not bar.plates.isVisibleTo(bar)

    bar.show_for(3, plates=3)
    assert bar.plates.isVisibleTo(bar)
    assert bar.plates.count() == 4, "all plus three"


def test_the_selector_starts_on_everything(qt_app: QApplication) -> None:
    bar = ExplodeBar()
    bar.show_for(3, plates=3)

    assert bar.plate == ALL_PLATES


def test_choosing_a_plate_reports_it(qt_app: QApplication) -> None:
    bar = ExplodeBar()
    bar.show_for(3, plates=3)
    seen: list[int] = []
    bar.plateChanged.connect(seen.append)

    bar.plates.setCurrentIndex(2)

    assert seen == [1], "the second plate counts as 1"
    assert bar.plate == 1


def test_the_viewport_shows_one_plate_without_touching_the_scene(qt_app: QApplication) -> None:
    from app.core.scene import EvaluationResult
    from app.ui.viewport import Viewport

    result = EvaluationResult(
        scene=Scene(
            objects={
                "obj_1": SceneObject(id="obj_1", name="A", mesh=slab(), plate=0),
                "obj_2": SceneObject(id="obj_2", name="B", mesh=slab(), plate=1),
            }
        )
    )
    viewport = Viewport()
    viewport.show_scene(result)

    viewport.set_plate(1)

    assert list(result.scene.objects) == ["obj_1", "obj_2"], "the scene is untouched"
    assert viewport._plate == 1


def two_plates() -> object:
    from app.core.scene import EvaluationResult

    return EvaluationResult(
        scene=Scene(
            objects={
                "obj_1": SceneObject(id="obj_1", name="A", mesh=slab(), plate=0),
                "obj_2": SceneObject(id="obj_2", name="B", mesh=slab(), plate=1),
            }
        )
    )


def test_the_beds_stand_beside_each_other(profile: Profile, qt_app: QApplication) -> None:
    """Zwei Platten, zwei Betten — sonst stehen die Teile ineinander.

    Gemeldet als „bei Projekten mit mehreren Platten sehe ich trotzdem nur
    eine": jede Platte hat ihren eigenen Nullpunkt, die Anordnung setzt Platte 2
    an denselben Ort wie Platte 1, und ein Bett für alle zeigt genau das.
    """
    from app.ui.viewport import PLATE_GAP, Viewport, plate_shift

    viewport = Viewport()
    viewport.show_build_volume(profile)
    viewport.show_scene(two_plates())

    width = profile.printer.build_volume[0]
    assert viewport._beds_drawn == 2, "one bed per plate"
    assert plate_shift(0, width) == (0.0, 0.0, 0.0), "the first stays where it was"
    assert plate_shift(1, width)[0] == pytest.approx(width + PLATE_GAP)


def test_one_bed_again_as_soon_as_a_single_plate_is_chosen(
    profile: Profile, qt_app: QApplication
) -> None:
    """Wer eine Platte wählt, sieht ein Bett — und die Teile an ihrem Ort."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.show_build_volume(profile)
    viewport.show_scene(two_plates())

    viewport.set_plate(1)

    assert viewport._beds_drawn == 1
    entry = SceneObject(id="obj_2", name="B", mesh=slab(), plate=1)
    assert list(viewport._plate_offset(entry)) == [0.0, 0.0, 0.0]


def test_a_click_on_the_second_bed_lands_on_the_second_plate(
    profile: Profile, qt_app: QApplication
) -> None:
    """Die Umkehrung, ohne die ein Klick eine Bettbreite daneben bohrt."""
    from app.ui.viewport import PLATE_GAP, Viewport, plate_at

    viewport = Viewport()
    viewport.show_build_volume(profile)
    viewport.show_scene(two_plates())

    width = profile.printer.build_volume[0]
    pitch = width + PLATE_GAP
    assert plate_at(0.0, 2, width) == 0
    assert plate_at(pitch + 12.0, 2, width) == 1
    assert plate_at(pitch * 9, 2, width) == 1, "never past the last plate"

    back = viewport._from_view((pitch + 12.0, 4.0, 3.0))
    assert back == pytest.approx((12.0, 4.0, 3.0))


def test_a_single_plate_draws_exactly_what_it_always_did(
    profile: Profile, qt_app: QApplication
) -> None:
    """Die Gegenprobe: eine Platte, ein Bett, kein Versatz — Bild für Bild wie
    vorher.
    """
    from app.core.scene import EvaluationResult
    from app.ui.viewport import Viewport

    result = EvaluationResult(
        scene=Scene(objects={"obj_1": SceneObject(id="obj_1", name="A", mesh=slab(), plate=0)})
    )
    viewport = Viewport()
    viewport.show_build_volume(profile)
    viewport.show_scene(result)

    assert viewport._beds_drawn == 1
    entry = result.scene.objects["obj_1"]
    assert list(viewport._plate_offset(entry)) == [0.0, 0.0, 0.0]
    assert viewport._from_view((5.0, 6.0, 7.0)) == (5.0, 6.0, 7.0)
