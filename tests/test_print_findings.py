"""Die Schichtanalyse im Prüfbericht (§17.3, §22.2, §22.3).

Geprüft gegen Körper, deren Zahlen sich ausrechnen lassen: ein schwebender
Würfel (eine Insel, 10 × 10 mm, 20 mm über dem Bett — 2 cm³ Raum darunter),
ein Pilz (ein Hut, der frei überhängt), ein Steg über einer Lücke, ein Kinn
mit schräger Unterseite aus vielen kleinen Streifen, ein Winkel, der liegend
keine Stütze braucht. Jede Zeile trägt ihren Ort, eine Handlung
und die Herkunft ``internal`` (Regel 14).
"""

from __future__ import annotations

from dataclasses import replace

import pytest
import trimesh

from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.perceive import maps
from app.core.slice import advise, findings
from app.core.slice.findings import print_findings
from app.core.types import Scene, SceneObject
from tests.helpers import brick, chin, chin_over_chest, on_bed


def _box(size: tuple[float, float, float], at: tuple[float, float, float]) -> trimesh.Trimesh:
    body = trimesh.creation.box(extents=size)
    body.apply_translation(at)
    return body


def _scene(*meshes: MeshData) -> Scene:
    return Scene(
        objects={
            f"obj_{number}": SceneObject(id=f"obj_{number}", name=f"Teil {number}", mesh=mesh)
            for number, mesh in enumerate(meshes, start=1)
        },
        parameters={},
    )


def _floating_cube(size: float = 10.0) -> MeshData:
    """Ein Sockel 20 × 20 × 10 und daneben ein Würfel der Kante ``size``,
    10 mm hoch, dessen Unterseite 20 mm über dem Bett schwebt."""
    return MeshData.of(
        trimesh.util.concatenate(
            [_box((20.0, 20.0, 10.0), (0.0, 0.0, 5.0)), _box((size, size, 10.0), (30.0, 0.0, 25.0))]
        )
    )


@pytest.fixture
def petg() -> tuple[object, object]:
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    return profile, print_settings.resolve(profile)


def _codes(found: list[object]) -> list[str]:
    return [finding.code for finding in found]  # type: ignore[attr-defined]


def test_a_floating_cube_is_one_island_with_its_place_and_its_column(petg) -> None:
    profile, settings = petg

    found = print_findings(_scene(_floating_cube()), profile, settings)

    islands = [entry for entry in found if entry.code == "slice.island_needs_support"]
    assert len(islands) == 1
    island = islands[0]
    assert island.object_id == "obj_1"
    assert island.source == "internal", "Regel 14: geschätzt, nicht aus G-Code"
    assert island.values["area_mm2"] == pytest.approx(100.0, rel=0.01)
    # 10 mal 10 mm über 20 mm Luft: 2 000 mm³, auf die Schnittmitten gerechnet.
    assert island.values["support_cm3"] == pytest.approx(2.0, rel=0.03)
    assert island.values["count"] == 1
    assert island.location is not None
    x, y, z = island.location
    assert 25.0 < x < 35.0 and -5.0 < y < 5.0, "der Klick fliegt zum Würfel, nicht zum Sockel"
    assert z == pytest.approx(20.0, abs=0.3)
    assert [action.id for action in island.suggestions] == ["orient_for_print", "show_support_need"]
    assert maps.map_for(island) == "support", "der Klick öffnet die Stützkarte"


def test_a_solid_block_reports_no_geometry(petg) -> None:
    profile, settings = petg
    block = MeshData.of(_box((30.0, 20.0, 10.0), (0.0, 0.0, 5.0)))

    found = print_findings(_scene(block), profile, settings)

    assert not [code for code in _codes(found) if code.startswith(("slice.", "orient."))], (
        "ein Klotz auf dem Bett hat nichts zu berichten"
    )


def test_a_mushroom_hat_is_one_located_overhang_and_not_an_island(petg) -> None:
    profile, settings = petg
    mushroom = MeshData.of(
        trimesh.boolean.union(
            [_box((10.0, 10.0, 20.0), (0.0, 0.0, 10.0)), _box((40.0, 40.0, 4.0), (0.0, 0.0, 22.0))]
        )
    )

    found = print_findings(_scene(mushroom), profile, settings)

    assert "slice.island_needs_support" not in _codes(found), "der Hut hängt am Stiel"
    overhangs = [entry for entry in found if entry.code == "slice.large_overhang"]
    assert len(overhangs) == 1
    hat = overhangs[0]
    # Der Hut ragt 40² minus (10 + Zugabe)² hinaus; die Zugabe ist die 45-Grad-Reichweite
    # einer Schicht rund um den Stiel.
    assert 1400.0 < hat.values["area_mm2"] < 1500.0
    assert hat.location is not None and hat.location[2] == pytest.approx(20.0, abs=0.3)
    assert maps.map_for(hat) == "overhang"


def test_a_long_bridge_points_at_the_gap(petg) -> None:
    profile, settings = petg
    bridge = MeshData.of(
        trimesh.boolean.union(
            [
                _box((5.0, 10.0, 10.0), (-17.5, 0.0, 5.0)),
                _box((5.0, 10.0, 10.0), (17.5, 0.0, 5.0)),
                _box((40.0, 10.0, 2.0), (0.0, 0.0, 11.0)),
            ]
        )
    )

    found = print_findings(_scene(bridge), profile, settings)

    spans = [entry for entry in found if entry.code == "slice.long_bridge"]
    assert len(spans) == 1
    assert spans[0].values["span_mm"] == pytest.approx(30.0, abs=0.5)
    assert spans[0].location is not None
    assert abs(spans[0].location[0]) < 10.0, "über der Lücke, nicht am Ursprung eines Pfeilers"
    assert spans[0].object_id == "obj_1"


def _slice_codes(found: list[object]) -> list[str]:
    return [code for code in _codes(found) if code.startswith("slice.")]


def test_many_small_overhangs_point_at_the_underside_of_the_chin(petg) -> None:
    """RM-572: Ein Kinn mit 18° flacher Unterseite zerfällt im Schnitt in
    Streifen unter 10 mm²; kein Stück erreicht die Meldeschwelle, der Rat
    verlangt trotzdem Stützen. Der Bericht nennt die Stelle — auf der
    Unterseite, an der Höhe ihrer Schicht. Die Unterseite steigt von 44 mm an
    der Rückwand (y = 15) bis 50 mm an der Spitze (y = −3); ein Streifen auf
    der Höhe z liegt also bei y = −3 + 3·(50 − z)."""
    profile, settings = petg

    found = print_findings(_scene(chin_over_chest()), profile, settings)

    assert "slice.large_overhang" not in _codes(found), "kein Stück über der Meldeschwelle"
    small = [entry for entry in found if entry.code == "slice.small_overhangs"]
    assert len(small) == 1
    finding = small[0]
    assert finding.object_id == "obj_1"
    assert finding.source == "internal", "Regel 14: geschätzt, nicht aus G-Code"
    assert finding.values["area_mm2"] > findings.OVERHANG_REPORTED_FROM
    assert finding.location is not None
    x, y, z = finding.location
    assert -8.0 < x < 8.0 and -3.0 < y < 15.0, "im Grundriss des Kinns"
    assert 44.0 < z < 50.2
    # Ein Streifen ist eine Schicht hoch, in y also 3 · 0,2 mm breit.
    assert y == pytest.approx(-3.0 + 3.0 * (50.0 - z), abs=1.1), "auf der Unterseite"
    assert finding.values["z_mm"] == pytest.approx(z, abs=0.01)
    assert [action.id for action in finding.suggestions] == [
        "orient_for_print",
        "show_support_need",
    ]
    assert maps.map_for(finding) == "overhang", "der Klick öffnet die Überhangkarte"


def test_the_small_overhangs_are_not_shown_on_a_self_supporting_collar(petg) -> None:
    """Ein Kragen ragt 2 mm um die Rückwand, auf der Höhe der Kinnstreifen. Er
    trägt sich selbst (``ledges``), bringt seiner Schicht aber die meiste
    Überhangfläche; der Ort gehört trotzdem unter das Kinn (Review RM-572)."""
    profile, settings = petg
    body = on_bed(
        brick(80.0, 60.0, 4.0, (0.0, 0.0, 2.0)),
        brick(40.0, 10.0, 60.0, (0.0, 20.0, 34.0)),
        brick(60.0, 30.0, 20.0, (0.0, 0.0, 14.0)),
        chin(44.0),
        brick(44.0, 14.0, 2.0, (0.0, 20.0, 47.0)),
    )

    found = print_findings(_scene(body), profile, settings)

    small = [entry for entry in found if entry.code == "slice.small_overhangs"]
    assert len(small) == 1
    assert small[0].location is not None
    x, y, z = small[0].location
    assert -8.0 < x < 8.0 and -3.0 < y < 15.0, "unter dem Kinn, nicht am Kragen"
    assert y == pytest.approx(-3.0 + 3.0 * (50.0 - z), abs=1.1)


@pytest.mark.parametrize("size", [12.0, 20.0])
def test_a_larger_floating_cube_is_only_an_island(petg, size: float) -> None:
    """Ein schwebender Würfel ist ein Überhangstück über 100 mm², und der
    Überhangweg des Rats ist wahr. Er ist aber eine Insel und hat seine Zeile;
    „viele kleine Überhänge“ stand daneben an derselben Stelle (Review RM-572)."""
    profile, settings = petg

    found = print_findings(_scene(_floating_cube(size)), profile, settings)

    assert _slice_codes(found) == ["slice.island_needs_support"]


def test_two_long_narrow_bridges_are_only_long_bridges(petg) -> None:
    """Zwei Stege von 3 mm Breite über 20 mm Lücke, je 58 mm² Überhang: Der Rat
    verlangt Stützen wegen der Brücke; zusammen 115,8 mm² trägt keiner der
    beiden Flächenwege. Dafür gibt es ``slice.long_bridge`` — keinen zweiten
    Befund über kleine Überhänge (Review RM-572)."""
    profile, settings = petg
    parts = [_box((40.0, 30.0, 2.0), (0.0, 0.0, 1.0))]
    for y in (-8.0, 8.0):
        parts += [
            _box((3.0, 3.0, 10.0), (-11.5, y, 7.0)),
            _box((3.0, 3.0, 10.0), (11.5, y, 7.0)),
            _box((26.0, 3.0, 2.0), (0.0, y, 13.0)),
        ]
    bridges = MeshData.of(trimesh.boolean.union(parts))

    found = print_findings(_scene(bridges), profile, settings)

    assert _slice_codes(found) == ["slice.long_bridge"]


def test_the_support_need_is_asked_only_where_a_turn_is_searched(
    petg, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Stützbedarf ist die teuerste Frage des Berichts. Ohne Lagensuche —
    mehr als acht Körper — stellt ihn auch der Befund über kleine Überhänge
    nicht (Review RM-572: ein Schachsatz zahlte je Figur Sekunden)."""
    profile, settings = petg
    entry = _scene(chin_over_chest()).objects["obj_1"]

    def refused(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("support_need ohne Lagensuche gefragt")

    monkeypatch.setattr(advise, "support_need", refused)
    found = findings.body_findings(entry, profile, settings, search=False)

    assert "slice.small_overhangs" not in _codes(found)


def test_a_rib_below_the_nozzle_is_located_at_the_rib(petg) -> None:
    profile, settings = petg
    plate = MeshData.of(
        trimesh.boolean.union(
            [_box((20.0, 20.0, 5.0), (0.0, 0.0, 2.5)), _box((0.25, 10.0, 5.0), (15.0, 0.0, 2.5))]
        )
    )

    found = print_findings(_scene(plate), profile, settings)

    thin = [entry for entry in found if entry.code == "settings.wall_below_nozzle"]
    assert len(thin) == 1
    assert thin[0].values["width_mm"] < 0.34
    assert thin[0].location is not None
    assert thin[0].location[0] > 10.0, "die dünnste Stelle ist die Rippe, nicht die Platte"
    assert maps.map_for(thin[0]) == "wall"


def test_a_lying_angle_is_offered_its_better_turn(petg) -> None:
    """Ein Winkel, stehend auf seinem Schenkel: Der andere Schenkel kragt 30 mm
    aus und braucht darunter Stützen. Liegend braucht er keine."""
    profile, settings = petg
    angle = MeshData.of(
        trimesh.boolean.union(
            [_box((5.0, 20.0, 40.0), (0.0, 0.0, 20.0)), _box((35.0, 20.0, 5.0), (15.0, 0.0, 37.5))]
        )
    )

    found = print_findings(_scene(angle), profile, settings)

    turns = [entry for entry in found if entry.code == "orient.saves_support"]
    assert len(turns) == 1
    assert turns[0].values["saved_percent"] >= 90
    assert turns[0].values["angle_deg"] == pytest.approx(90.0, abs=1.0)
    assert [action.id for action in turns[0].suggestions] == ["orient_for_print"]


def test_an_uncalibrated_material_offers_the_calibration(petg) -> None:
    profile, settings = petg
    uncalibrated = replace(profile, material=replace(profile.material, calibrated=False))

    found = advise.warnings_for(settings, uncalibrated)

    notes = [entry for entry in found if entry.code == "settings.uncalibrated_material"]
    assert len(notes) == 1
    assert [action.id for action in notes[0].suggestions] == ["calibrate_material"]


def test_the_calibration_note_needs_a_fit(petg) -> None:
    """Die Toleranzen eines Materials wirken nur an Passungen. Ohne sie stand
    der Hinweis an jedem Teil einer frischen Installation (Durchsicht 0.5.1,
    Inventar 1.3) — und ein Hinweis, der immer dasteht, wird überlesen."""
    profile, settings = petg
    uncalibrated = replace(profile, material=replace(profile.material, calibrated=False))
    scene = _scene(_floating_cube())

    def notes(fitted: bool | None = None) -> int:
        found = print_findings(scene, uncalibrated, settings, fitted=fitted)
        return sum(entry.code == "settings.uncalibrated_material" for entry in found)

    assert notes() == 0, "eine Szene ohne Passung"
    assert notes(fitted=True) == 1, "eine gebaute Passung, vom Dokument gemeldet"
    assert notes(fitted=False) == 0
    assert advise.warnings_for(settings, uncalibrated, fitted=False) == [
        entry
        for entry in advise.warnings_for(settings, uncalibrated)
        if entry.code != "settings.uncalibrated_material"
    ]


def test_the_analysis_is_kept_with_the_mesh(petg, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dasselbe Netz wird nicht zweimal geschnitten — eine Auswertung nach
    einem Klick in den Baum darf keine Sekunde Schichtanalyse kosten."""
    profile, settings = petg
    scene = _scene(_floating_cube())
    print_findings(scene, profile, settings)
    calls: list[int] = []
    original = findings.slice_body

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(findings, "slice_body", counting)
    again = print_findings(scene, profile, settings)

    assert not calls
    assert "slice.island_needs_support" in _codes(again)
    changed = replace(settings, layers=replace(settings.layers, layer_height=0.3))
    print_findings(scene, profile, changed)
    assert calls, "ein anderes Raster ist eine andere Analyse"


def test_a_resin_printer_hears_about_islands_only(petg) -> None:
    _profile, settings = petg
    resin = profiles.make_profile("generic-resin-130", "petg")
    assert resin.printer.is_resin

    found = print_findings(_scene(_floating_cube()), resin, settings)

    assert _codes(found) == ["slice.island_needs_support"]


def test_the_report_analysis_can_be_cancelled(petg) -> None:
    from app.core.scene.cancel import CancelSignal

    profile, settings = petg
    token = CancelSignal()
    token.cancel()

    with pytest.raises(OperationCancelled):
        print_findings(_scene(_floating_cube()), profile, settings, cancelled=token)
