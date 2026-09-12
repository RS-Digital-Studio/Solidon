"""Mehrere Druckplatten in einer Szene (Bauplan §25, §29).

Mehr Teile, als auf eine Platte passen, ist der Normalfall, sobald jemand einen
Satz von etwas druckt. Was nicht passieren darf, ist, dass das Anordnen sie
still übereinanderstapelt oder der Export Dateien schreibt, die niemand
auseinanderhalten kann.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
import trimesh
from PySide6.QtWidgets import QApplication

from app.core.export.writer import plan_export
from app.core.geom.mesh import MeshData
from app.core.geom.prepare import MAX_PLATES, arrange_on_bed, check_build_volume, check_collisions
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, PlaneFrame, Profile, Scene, SceneObject
from app.ui.header import ALL_PLATES, HeaderBar


def slab(size: float = 120.0) -> MeshData:
    """Eine Platte auf dem Bett — alles unter Z = 0 ist außerhalb des Raums."""
    body = trimesh.creation.box(extents=(size, size, 10.0))
    body.apply_translation((0.0, 0.0, 5.0))
    return MeshData.of(body)


def many(count: int, size: float = 120.0) -> list[MeshData]:
    return [slab(size) for _ in range(count)]


# --- arranging ------------------------------------------------------------------


def test_what_fits_stays_on_one_plate(profile: Profile) -> None:
    """Vier Platten passen auf die uneingeschränkte rechteckige Nennfläche."""
    profile = dataclasses.replace(
        profile, printer=dataclasses.replace(profile.printer, bed_exclusions=())
    )
    result = arrange_on_bed(many(4), profile, spacing=5.0, plates=4)

    assert result.plates == [0, 0, 0, 0]
    assert result.plate_count == 1
    assert not result.findings


def test_centauri_carbon_2_arrangement_keeps_its_actual_exclusion_clear(profile: Profile) -> None:
    """Auf dem CC2 bleibt die gesperrte Ecke frei; das vierte Teil wechselt die Platte."""
    from shapely.geometry import Polygon, box

    assert profile.printer.id == "centauri-carbon-2"
    assert profile.printer.bed_exclusions, "the real printer must retain its exclusion"
    forbidden = [Polygon(points) for points in profile.printer.bed_exclusions]

    result = arrange_on_bed(many(4), profile, spacing=5.0, plates=4)

    assert len(result.meshes) == 4
    assert result.plate_count == 2
    assert not result.findings
    for mesh in result.meshes:
        bounds = mesh.bounds
        rectangle = box(bounds.minimum[0], bounds.minimum[1], bounds.maximum[0], bounds.maximum[1])
        assert all(rectangle.disjoint(area) for area in forbidden)
    for plate in range(result.plate_count):
        on_plate = [
            mesh for mesh, entry in zip(result.meshes, result.plates, strict=True) if entry == plate
        ]
        assert not check_collisions(on_plate), f"plate {plate}"


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


#: Zweiundfünfzig Teile in gemischten Größen, deterministisch aus einer festen
#: Folge — kein Zufall, also auch kein Startwert (Regel 9). Die Mischung bildet
#: nach, was der Durchgang durch neun heruntergeladene Modelle am 21.08.2026
#: fand: viele kleine Teile, ein paar große dazwischen.
MIXED_EDGES = (18.0, 25.0, 40.0, 12.0, 95.0, 30.0, 22.0, 60.0, 15.0, 110.0, 35.0, 28.0, 50.0)


def mixed_batch(count: int = 52) -> list[MeshData]:
    """Ein Satz gemischter Teile — die Vorlage für die Messung aus §29."""
    parts = []
    for index in range(count):
        width = MIXED_EDGES[index % len(MIXED_EDGES)]
        depth = MIXED_EDGES[(index * 7 + 3) % len(MIXED_EDGES)]
        body = trimesh.creation.box(extents=(width, depth, 10.0))
        body.apply_translation((0.0, 0.0, 5.0))
        parts.append(MeshData.of(body))
    return parts


def test_fifty_two_parts_need_fewer_plates_than_rows_did(profile: Profile) -> None:
    """Die Abnahme aus Bauplan §29 ist eine Messung und keine Meinung.

    Zeilenweise gepackt brauchte dieser Satz **fünf** Platten (12/13/13/13/1):
    Über jedem flachen Teil blieb ein Streifen von der Tiefe des tiefsten Teils
    derselben Zeile ungenutzt. Ohne Zeilen — jeder Körper an die hinterste,
    dann linkeste freie Stelle — sind es drei (22/16/14). Wird es das nicht
    mehr, ist die Regel ihren Preis nicht wert und die Zeilen kommen zurück.
    """
    result = arrange_on_bed(mixed_batch(), profile, spacing=5.0, plates=8)

    assert result.plate_count < 5, f"rows needed 5, this needs {result.plate_count}"
    assert len(result.meshes) == 52, "nothing is quietly dropped"
    for plate in range(result.plate_count):
        on_plate = [
            mesh for mesh, entry in zip(result.meshes, result.plates, strict=True) if entry == plate
        ]
        assert not check_collisions(on_plate), f"plate {plate}"
        assert not check_build_volume(on_plate, profile), f"plate {plate}"


def test_the_place_is_the_rearmost_then_leftmost_one(profile: Profile) -> None:
    """Die Regel in einem Satz: hinterste freie Stelle, dann linkeste.

    Drei gleiche Teile nebeneinander, dann ein viertes: Es gehört neben das
    dritte und nicht hinter das erste, solange in derselben Tiefe noch Platz
    ist. Zeilenweise wäre das dasselbe — der Unterschied zeigt sich erst, wenn
    ein tiefes Teil dazwischenliegt, und dafür steht der Test darunter.
    """
    result = arrange_on_bed(many(4, size=50.0), profile, spacing=5.0, plates=1)

    corners = [(mesh.bounds.minimum[0], mesh.bounds.minimum[1]) for mesh in result.meshes]
    assert len({round(y, 6) for _x, y in corners}) == 1, "all four sit in the same depth"
    assert corners == sorted(corners), "and left to right in the order they came"


def test_a_deep_part_does_not_waste_the_strip_beside_it(profile: Profile) -> None:
    """Der Streifen, um den es geht: neben einem tiefen Teil bleibt Platz.

    Ein Teil von 180 x 200 mm, dann fünf flache von 40 x 40. Zeilenweise passen
    zwei davon neben das tiefe, und das dritte reißt die Zeile: Es beginnt erst
    **hinter** dem tiefen Teil, obwohl über den beiden flachen noch 160 mm frei
    sind. Genau dieser Streifen ist der Grund, aus dem 52 Teile sieben Platten
    brauchten. Ohne Zeilen wandert nichts dahinter.
    """
    deep = trimesh.creation.box(extents=(180.0, 200.0, 10.0))
    deep.apply_translation((0.0, 0.0, 5.0))
    parts = [MeshData.of(deep), *many(5, size=40.0)]

    result = arrange_on_bed(parts, profile, spacing=5.0, plates=1)

    assert not check_collisions(result.meshes)
    behind = result.meshes[0].bounds.maximum[1]
    assert all(mesh.bounds.maximum[1] <= behind + 1e-6 for mesh in result.meshes[1:]), (
        "the flat ones fill the strip beside the deep part instead of starting behind it"
    )


def test_what_is_packed_ends_up_in_the_middle_of_the_bed(profile: Profile) -> None:
    """Gepackt wird in der Ecke, gelegt wird in der Mitte (Robert, 09.09.2026).

    Jeder Slicer, den Robert danebenstehen hat — ElegooSlicer, Orca, Bambu
    Studio, PrusaSlicer —, legt seine Teile mittig aufs Bett. Solidon packte
    sie nach hinten links, weil die Packregel dort ihre Ecke hat; auf einem
    256er Bett standen zwei Türme damit bei x −123 und y 123, also in der
    Ecke, während drei Viertel der Fläche leer blieben.

    Das Packverfahren selbst bleibt, wie es ist — es ist an denselben
    Referenzteilen abgenommen (§29) und liefert dieselbe Plattenzahl. Nur die
    fertige Packung wandert als Ganzes in die Mitte, und deshalb ändert sich
    weder die Reihenfolge noch der Abstand noch die Kollisionsfreiheit.
    """
    profile = dataclasses.replace(
        profile, printer=dataclasses.replace(profile.printer, bed_exclusions=())
    )

    result = arrange_on_bed(many(2, size=40.0), profile, spacing=5.0, plates=1)

    left = min(mesh.bounds.minimum[0] for mesh in result.meshes)
    right = max(mesh.bounds.maximum[0] for mesh in result.meshes)
    front = min(mesh.bounds.minimum[1] for mesh in result.meshes)
    back = max(mesh.bounds.maximum[1] for mesh in result.meshes)
    assert abs(left + right) < 1e-6, f"x is off centre: {left} .. {right}"
    assert abs(front + back) < 1e-6, f"y is off centre: {front} .. {back}"
    assert not check_collisions(result.meshes), "and still nothing touches"


def test_every_plate_finds_its_own_middle(profile: Profile) -> None:
    """Zentriert wird je Platte, nicht über den ganzen Auftrag.

    Zwei Platten sind zwei Drucke; eine gemeinsame Mitte über beide wäre die
    Mitte von nichts. Die zweite Platte trägt hier ein einziges Teil, und das
    steht auf ihr genauso mittig wie die volle erste.
    """
    profile = dataclasses.replace(
        profile, printer=dataclasses.replace(profile.printer, bed_exclusions=())
    )

    result = arrange_on_bed(many(5), profile, spacing=5.0, plates=4)

    assert result.plate_count >= 2, "der Fall braucht mehr als eine Platte"
    for plate in range(result.plate_count):
        on_plate = [
            mesh for mesh, at in zip(result.meshes, result.plates, strict=True) if at == plate
        ]
        left = min(mesh.bounds.minimum[0] for mesh in on_plate)
        right = max(mesh.bounds.maximum[0] for mesh in on_plate)
        assert abs(left + right) < 1e-6, f"plate {plate} is off centre: {left} .. {right}"


def test_a_blocked_middle_keeps_the_packing_where_it_fits(profile: Profile) -> None:
    """Wo die Mitte gesperrt ist, bleibt die Packung in der Ecke.

    Die Verschiebung umgeht die Prüfung, mit der ``place`` jede einzelne Lage
    gegen die freigegebene Fläche hält — ein Drucker mit Sperrzone bekäme sonst
    Teile mitten hinein geschoben. Hier liegt die Sperrzone genau dort, wo die
    Packung landen würde; sie bleibt deshalb, wo sie gepackt wurde.
    """
    middle = (((-60.0, -60.0), (60.0, -60.0), (60.0, 60.0), (-60.0, 60.0)),)
    profile = dataclasses.replace(
        profile, printer=dataclasses.replace(profile.printer, bed_exclusions=middle)
    )

    result = arrange_on_bed(many(2, size=40.0), profile, spacing=5.0, plates=1)

    assert not check_build_volume(result.meshes, profile), "nichts liegt in der Sperrzone"
    assert not check_collisions(result.meshes)


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


def _arrange(objects: list[SceneObject], profile: Profile, **params: object) -> object:
    """Die Operation fahren, wie das Menü sie fährt."""
    spec = REGISTRY.get("arrange_bed")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry for entry in objects}),
            inputs=objects,
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_arranging_twice_says_that_nothing_moved(profile: Profile) -> None:
    """Eine Operation, die nichts bewirkt hat, sagt das — hier für die Lage.

    Robert am 24.08.2026, nachdem er *Auf dem Bett anordnen* zum zweiten Mal
    geklickt hatte: „das an druckbett ausrichten funktioniert nicht mehr."
    Es lag schon alles, wo es liegen sollte — der Dialog ging auf, OK rechnete
    dasselbe Ergebnis, im Verlauf stand ein Schritt, und das Bild blieb, wie es
    war. Ohne ein Wort dazu ist das von einer kaputten Anwendung nicht zu
    unterscheiden.

    Dieselbe Zusage wie ``boolean.without_effect`` für das Volumen, nur für die
    Position — und ein eigener Code, weil es **nicht** dasselbe Problem meldet:
    Dort liegt ein Werkzeug neben dem Körper und der Nutzer wollte etwas
    anderes; hier ist das Ergebnis richtig.
    """
    objects = [
        SceneObject(id=f"obj_{index}", name=f"Teil {index}", mesh=slab(60.0)) for index in range(2)
    ]

    erst = _arrange(objects, profile, spacing=5.0, plates=1)
    codes = {finding.code for finding in erst.findings}
    assert "arrange.already_arranged" not in codes, (
        f"beim ersten Mal wird verschoben, da ist nichts zu melden: {codes}"
    )

    # Was herauskam, noch einmal anordnen — wie ein zweiter Klick.
    again = [
        dataclasses.replace(entry, mesh=output.mesh, plate=output.plate)
        for entry, output in zip(objects, erst.outputs, strict=True)
    ]
    zweit = _arrange(again, profile, spacing=5.0, plates=1)

    assert "arrange.already_arranged" in {finding.code for finding in zweit.findings}, (
        "der zweite Klick bewegt nichts und muss es sagen"
    )
    said = next(f for f in zweit.findings if f.code == "arrange.already_arranged")
    assert said.severity == "info", "gelungen, nur ohne Wirkung — kein Fehler"
    assert [tuple(output.mesh.bounds.minimum) for output in zweit.outputs] == [
        tuple(output.mesh.bounds.minimum) for output in erst.outputs
    ], "und die Lage bleibt, wie sie war"


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

    # Die Platte weit draußen **passt** auf ein Bett, sie liegt nur woanders —
    # das ist die Kennung für die Lage und nicht die für die Größe
    # (``_fits_at_all``). Die Plattennummer ist hier die Aussage, nicht die
    # Kennung.
    outside = [entry for entry in plan.findings if entry.code == "arrange.off_the_plate"]
    assert [entry.values["plate"] for entry in outside] == [2]


# --- der Wähler -----------------------------------------------------------------


def test_the_selector_appears_from_two_plates_on(qt_app: QApplication) -> None:
    """``isVisibleTo`` und nicht ``isVisible``: Die Kopfzeile steht immer, aber
    der Wähler darin nur, wenn es etwas zu wählen gibt.
    """
    bar = HeaderBar()

    bar.show_plates(1)
    assert not bar.plates.isVisibleTo(bar)

    bar.show_plates(3)
    assert bar.plates.isVisibleTo(bar)
    assert bar.plates.count() == 4, "all plus three"


def test_the_selector_starts_on_everything(qt_app: QApplication) -> None:
    bar = HeaderBar()
    bar.show_plates(3)

    assert bar.plate == ALL_PLATES


def test_choosing_a_plate_reports_it(qt_app: QApplication) -> None:
    bar = HeaderBar()
    bar.show_plates(3)
    seen: list[int] = []
    bar.plateChanged.connect(seen.append)

    bar.plates.setCurrentIndex(2)

    assert seen == [1], "the second plate counts as 1"
    assert bar.plate == 1


def test_the_selector_lives_in_the_header_and_not_in_the_explosion(
    qt_app: QApplication,
) -> None:
    """**Er wohnte im Explodieren, und dort gehörte er nie hin.**

    Der Wähler stand in der Leiste, die Teile auseinanderzieht, und erschien nur,
    wenn dort auch der Schieber etwas zu tun hatte — bei genau einer Platte war
    er also unsichtbar, bei einem einzelnen Körper die ganze Leiste. Wer eine
    Platte ansehen wollte, suchte ihn unter einem Werkzeug für etwas anderes.
    """
    from app.ui.explode_bar import ExplodeBar

    strip = ExplodeBar()

    assert not hasattr(strip, "plates"), "der Wähler ist fort"
    assert not hasattr(strip, "plateChanged"), "und sein Signal auch"
    assert hasattr(HeaderBar(), "plates"), "und steht in der Kopfzeile"


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


def test_a_single_body_on_two_plates_still_gets_the_selector(qt_app: QApplication) -> None:
    """**Der Mangel, um den es ging.** In der Explodier-Leiste hing der Wähler
    an ihrer Sichtbarkeit, und die begann bei zwei Körpern: Ein einzelner Körper
    auf Platte 2 von 3 — nach einem Auto-Split, der Deckel und Rumpf verteilt,
    oder bei einer Auswahl — ließ ihn verschwinden. In der Kopfzeile hängt er nur
    noch an der Zahl der Platten, und das ist die Frage, die er beantwortet.
    """
    bar = HeaderBar()

    bar.show_plates(3)

    assert bar.plates.isVisibleTo(bar), "drei Platten, ein Wähler"
    assert bar.plates.count() == 4


def test_a_plate_that_disappears_takes_the_view_with_it(qt_app: QApplication) -> None:
    """Fällt die betrachtete Platte weg, erfährt es die Ansicht — immer.

    **Der Fall, der diese Prüfung veranlasst hat** (gemessen 3d-druck-85 am
    03.09.2026): Wer Platte 3 betrachtet und dann auf zwei Platten fällt,
    stand vor einem leeren Bauraum ohne Rückweg. ``clear()`` stellt den Wähler
    auf „Alle Platten", die Wiederherstellung darüber greift nicht mehr
    (``previous < plates`` ist bei 2 < 2 falsch) — und weil noch **mehr als
    eine** Platte übrig war, meldete die Kopfzeile das nicht: Die alte Regel
    sprach nur den Sonderfall „nur noch eine Platte" an.

    Die Ansicht filterte deshalb weiter auf Platte 3, auf der nichts mehr
    liegt. Und der Weg zurück fehlte: Der Wähler zeigte „Alle Platten", ein
    Klick auf denselben Eintrag ändert den Index nicht und sendet nichts.
    Auch ein neues Projekt heilte es nicht.
    """
    bar = HeaderBar()
    bar.show_plates(3)
    bar.plates.setCurrentIndex(3)
    assert bar.plate == 2, "die dritte Platte zählt als 2"

    seen: list[int] = []
    bar.plateChanged.connect(seen.append)
    bar.show_plates(2)

    assert bar.plate == ALL_PLATES, "die dritte Platte gibt es nicht mehr"
    assert seen == [ALL_PLATES], "die Ansicht muss erfahren, dass der Filter fällt"


def test_a_plate_that_survives_is_kept_without_a_word(qt_app: QApplication) -> None:
    """Die Gegenprobe: Was bleibt, wird behalten und **nicht** gemeldet.

    Ohne sie wäre eine Kopfzeile, die bei jedem Neuaufbau meldet, genauso
    grün — und die Ansicht spränge bei jeder Änderung der Plattenzahl zurück
    auf „alle", obwohl die betrachtete Platte noch da ist.
    """
    bar = HeaderBar()
    bar.show_plates(3)
    bar.plates.setCurrentIndex(2)

    seen: list[int] = []
    bar.plateChanged.connect(seen.append)
    bar.show_plates(5)

    assert bar.plate == 1, "die zweite Platte ist noch da"
    assert seen == [], "wo sich nichts ändert, wird nichts gemeldet"


# --- die Kulisse wird nur gebaut, wenn sie sich ändert (RM-124) -------------------


def _with_recorder(profile: Profile) -> tuple[Any, Any]:
    """Ein Viewport mit Aufzeichnung und einem stehenden Bett."""
    from app.ui.viewport import Viewport
    from tests.render_fakes import RecordingRenderer

    viewport = Viewport()
    viewport.renderer = RecordingRenderer(size=(900, 600))
    viewport.show_build_volume(profile)
    return viewport, viewport.renderer


def _bed_actors(renderer: Any) -> int:
    """Wie viele Aktoren der Kulisse bisher entstanden sind."""
    return sum(
        1 for _kind, entry in renderer.drawn if entry["name"].startswith(("bed_", "build_volume_"))
    )


def _rebuilds(viewport: Any, renderer: Any, work: Any) -> int:
    """Wie viele Aktoren der Kulisse ein Aufruf neu anlegt.

    Nur die der Kulisse: ``set_theme`` zeichnet die Szene gleich mit, und
    deren Aktoren beantworten eine andere Frage.
    """
    before = _bed_actors(renderer)
    work()
    return _bed_actors(renderer) - before


def test_an_unchanged_build_volume_is_not_built_again(
    profile: Profile, qt_app: QApplication
) -> None:
    """Das Fenster ruft die Kulisse bei **jeder** Auswertung (RM-124).

    Sie warf dabei vier Aktoren je Platte weg, um dieselben vier wieder
    anzulegen. Gemessen am 12.09.2026 am eigenen Renderer ohne Fenster:
    19,2 ms für ein Bett, 71,3 ms für vier — im Qt-Hauptthread, für ein Bild,
    das sich nicht unterscheidet. Danach sind es 2,1 und 2,5 ms, und die sind
    das Anfordern des Bildes und nicht der Aufbau.
    """
    viewport, renderer = _with_recorder(profile)

    assert _rebuilds(viewport, renderer, lambda: viewport.show_build_volume(profile)) == 0
    assert not renderer.removed, "und weggeworfen wird auch nichts"


def test_every_reason_to_build_the_bed_again_still_builds_it(
    profile: Profile, qt_app: QApplication
) -> None:
    """Vier Gründe, und jeder muss durchkommen (RM-124).

    Ein anderer Bauraum, eine Platte mehr, andere Farben aus dem Thema, ein
    anderer Renderer. Ein Wächter, der einen davon verschluckt, lässt eine
    Kulisse stehen, die etwas anderes zeigt als die Szene.
    """
    from tests.render_fakes import RecordingRenderer

    viewport, renderer = _with_recorder(profile)

    larger = dataclasses.replace(
        profile,
        printer=dataclasses.replace(profile.printer, build_volume=(300.0, 300.0, 400.0)),
    )
    assert _rebuilds(viewport, renderer, lambda: viewport.show_build_volume(larger)) == 4, (
        "ein anderer Bauraum"
    )

    viewport._plate_count = lambda: 3  # type: ignore[method-assign]
    assert _rebuilds(viewport, renderer, lambda: viewport.show_build_volume(larger)) == 12, (
        "drei Platten, drei Betten"
    )

    # Der Themenwechsel baut die Kulisse selbst neu — er ruft
    # ``show_build_volume``, und genau das muss durchkommen, sonst stünde ein
    # fast schwarzes Bett auf hellem Grund.
    assert _rebuilds(viewport, renderer, lambda: viewport.set_theme("light")) == 12, "andere Farben"

    zweiter = RecordingRenderer(size=(900, 600))
    viewport.renderer = zweiter
    assert _rebuilds(viewport, zweiter, lambda: viewport.show_build_volume(larger)) == 12, (
        "ein anderer Renderer braucht seine eigenen Aktoren"
    )


def test_the_bed_keeps_what_was_hidden_and_gets_it_back(
    profile: Profile, qt_app: QApplication
) -> None:
    """Sichtbarkeit und Zeichenebene über einen Aufruf hinweg (RM-124).

    Vorher galt die Reihenfolge: frisch gebaut, dann ausblenden. Seit die
    Aktoren stehen bleiben, gilt die Regel in **beide** Richtungen
    (``_apply_bed_visibility``, eine Stelle statt zweier).

    **Dieser Test ist ein Wächter um den Wächter und kein Nachweis dafür.**
    Gegengeprüft am 12.09.2026: Mit der alten, nur ausblendenden Fassung
    bleibt er grün, weil ``set_bed_visible`` und das Ende des Zeichenmodus die
    Sichtbarkeit selbst wiederherstellen — ein Ablauf, in dem die alte Regel
    falsch liegt, ließ sich nicht konstruieren. Was er sichert, ist das, was
    zählt: Der neue Wächter darf keinen dieser Zustände verschlucken.
    """
    viewport, _renderer = _with_recorder(profile)

    viewport.set_bed_visible(False)
    viewport.show_build_volume(profile)
    assert not any(actor.visible() for actor in viewport._frame_actors), "ausgeblendet bleibt aus"

    viewport.set_bed_visible(True)
    viewport.show_build_volume(profile)
    assert all(actor.visible() for actor in viewport._frame_actors), "und kommt wieder"

    viewport.set_sketching(
        PlaneFrame(
            origin=(0.0, 0.0, 0.0),
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(0.0, 1.0, 0.0),
            normal=(0.0, 0.0, 1.0),
        )
    )
    viewport.show_build_volume(profile)
    assert not any(actor.visible() for actor in viewport._ground_actors), (
        "der Boden tritt beim Zeichnen ab"
    )
    assert any(
        actor.visible() for actor in viewport._frame_actors if actor not in viewport._ground_actors
    ), "die Bauraumkanten bleiben"

    viewport.set_sketching(None)
    viewport.show_build_volume(profile)
    assert all(actor.visible() for actor in viewport._frame_actors), "und danach steht alles wieder"
