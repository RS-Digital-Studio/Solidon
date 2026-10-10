"""RM-317: gemessene Objektfähigkeiten und vollständige Werte je Teil.

Die Sollwerte kommen aus der Zwei-Körper-Matrix vom 03.10.2026: sieben echte
Slicer, native Projektbeilagen und getrennt gelesene Bahnen. Hier bleibt der
Anschluss portabel; kein installiertes Programm wird aufgerufen.
"""

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import trimesh

from app.core.export import handover, manufacturer, writer
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.types import SceneObject, SettingAdvice


def _advice(path, value, settings):
    return SettingAdvice(path, value, print_settings.read_path(settings, path), "Grund des Teils")


@pytest.mark.parametrize(
    "executable,flavour,missing",
    [
        (
            "PrusaSlicer.exe",
            "prusa",
            {
                "speed.acceleration",
                "speed.outer_wall_acceleration",
            },
        ),
        ("SuperSlicer.exe", "prusa", {"speed.acceleration", "speed.outer_wall_acceleration"}),
        ("bambu-studio.exe", "orca", {"speed.acceleration", "speed.outer_wall_acceleration"}),
        ("orca-slicer.exe", "orca", set()),
        ("elegoo-slicer.exe", "orca", set()),
        ("CrealityPrint.exe", "orca", set()),
        # Wie Orca je Objekt (``PrintObjectConfig``), nicht nur je Platte wie Bambu.
        ("AnycubicSlicerNext.exe", "orca", set()),
        ("CuraEngine.exe", "cura", set()),
    ],
)
def test_part_limits_follow_the_measured_program(executable, flavour, missing):
    profile = profiles.make_profile("generic-220", "pla")
    base = print_settings.resolve(profile)
    wanted = {
        "speed.outer_wall": 10.0,
        "speed.inner_wall": 12.0,
        "speed.acceleration": 123.0,
        "speed.outer_wall_acceleration": 99.0,
    }
    selected = base
    for path, value in wanted.items():
        selected = print_settings.with_accepted(selected, path, value)
    split = handover.split_for_parts(
        selected, profile, handover.SlicerSetup(Path(executable), flavour), flavour
    )
    assert split.unavailable == missing
    assert split.per_part == wanted.keys() - missing
    assert selected.accepted == wanted.keys(), "gespeicherte Wahl bleibt bestehen"


@pytest.mark.parametrize("program", ["prusaslicer", "superslicer"])
def test_part_width_reaches_native_prusa_roles(program):
    base = print_settings.resolve(profiles.make_profile())
    written = handover.object_keys(
        base, [_advice("layers.line_width", 0.48, base)], "prusa", program=program
    )
    for key in (
        "external_perimeter_extrusion_width",
        "perimeter_extrusion_width",
        "infill_extrusion_width",
        "solid_infill_extrusion_width",
        "top_infill_extrusion_width",
        "support_material_extrusion_width",
    ):
        assert written[key] == "0.48"
    assert "first_layer_extrusion_width" not in written


def test_cura_part_rollback_recalculates_dependent_values():
    profile = profiles.make_profile("sovol-sv06", "pla")
    base = print_settings.resolve(profile)
    for path, value in {
        "layers.line_width": 0.42,
        "infill.density": 0.15,
        "infill.pattern": "grid",
        "shell.wall_count": 3,
        "shell.outer_wall_first": False,
        "speed.inner_wall": 40.0,
        "speed.acceleration": 500.0,
    }.items():
        base = print_settings.with_choice(base, path, value)
    wanted = {
        "layers.line_width": 0.48,
        "infill.density": 0.37,
        "shell.wall_count": 4,
        "shell.outer_wall_first": True,
        "speed.inner_wall": 29.0,
        "speed.acceleration": 321.0,
    }
    plate = base
    for path, value in wanted.items():
        plate = print_settings.with_accepted(plate, path, value)
    split = handover.PartSplit(plate, base, frozenset(wanted), revert=True, accepted=plate)
    values = writer._values_for(split, [], [], "cura", profile=profile)
    expected = {
        "infill_line_distance": 5.6,
        "wall_line_width_0": 0.42,
        "wall_line_width_x": 0.42,
        "top_skin_preshrink": 1.26,
        "speed_wall_x": 40.0,
        "acceleration_wall_x": 500.0,
    }
    for key, value in expected.items():
        assert float(values.keys[key]) == pytest.approx(value)
    assert values.keys["initial_layer_inset_direction"] == "inside_out"
    assert "support_type" not in values.keys


def test_cura_channel_geometry_belongs_to_each_part():
    profile = profiles.make_profile("sovol-sv06", "pla")
    base = print_settings.resolve(profile)
    accepted = print_settings.with_accepted(base, "support.block_channels", True)
    split = handover.split_for_parts(accepted, profile, None, "cura")
    assert "support.block_channels" in split.per_part
    reference = writer._values_for(split, [], [], "cura")
    assert reference.effective.support.block_channels is False


@pytest.mark.parametrize("for_window", [False, True])
def test_cura_width_keeps_the_global_first_layer_width(tmp_path, monkeypatch, for_window):
    profile = profiles.make_profile("sovol-sv06", "pla")
    base = print_settings.resolve(profile)
    base = print_settings.with_choice(base, "layers.line_width", 0.42)
    base = print_settings.with_choice(base, "layers.first_layer_line_width", 0.42)
    selected = print_settings.with_accepted(base, "layers.line_width", 0.48)
    split = handover.split_for_parts(selected, profile, None, "cura")
    reference = writer._values_for(split, [], [], "cura", profile=profile)
    written = handover.values_for(split.plate, profile, "cura") | reference.keys
    # Cura liest den Faktor nur am Extruder. Ein Netzfaktor kann eine
    # zurückgenommene Rollenbreite deshalb nicht wieder ausgleichen.
    first_width = (
        float(written["wall_line_width_0"])
        * float(written["initial_layer_line_width_factor"])
        / 100.0
    )
    assert first_width == pytest.approx(0.42)
    assert "layers.line_width" in split.unavailable
    assert "wall_line_width_0" not in reference.keys
    objects = [
        SceneObject(
            id=f"part-{index}",
            name=f"Part {index}",
            mesh=MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 6.0))),
        )
        for index in range(2)
    ]
    monkeypatch.setattr(
        writer,
        "part_advice",
        lambda entry, _mesh, settings, *_args, **_kwargs: (
            [_advice("layers.line_width", 0.48, settings)] if entry.id == "part-0" else []
        ),
    )
    _path, findings = writer.write_assembly(
        objects,
        tmp_path,
        project_name="Width",
        profile=profile,
        settings=selected,
        flavour="cura",
        for_window=for_window,
    )
    assert not [entry for entry in findings if entry.code == "export.part_setting"]
    reported = [entry for entry in findings if entry.code == "export.part_setting_unavailable"]
    assert [(entry.object_id, entry.values["setting"]) for entry in reported] == [
        ("part-1", "layers.line_width")
    ]


def test_cura_unfulfilled_support_style_keeps_the_requested_value():
    base = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "support.style", "none"
    )
    plate = print_settings.with_accepted(base, "support.style", "tree")
    split = handover.PartSplit(
        plate, base, frozenset({"support.style"}), revert=True, accepted=plate
    )
    wanted = _advice("support.style", "grid", base)
    values = writer._values_for(split, [wanted], [], "cura")
    assert values.keys["support_enable"] == "true"
    assert [entry.value for entry in values.unavailable] == ["grid"]
    assert not values.applied, "der unerfüllte Gitterrat darf nicht als übernommen erscheinen"
    assert values.effective.support.style == "tree"
    disabled = writer._values_for(split, [_advice("support.style", "none", base)], [], "cura")
    assert disabled.keys["support_enable"] == "false"
    assert disabled.effective.support.style == "none"
    assert not disabled.unavailable


def test_superslicer_missing_generator_uses_its_classic_default(monkeypatch):
    profile = profiles.make_profile("prusa-mini", "pla")
    chain = manufacturer.PrusaChain("Prusa MINI", "Native", "PLA", {})
    monkeypatch.setattr(manufacturer, "prusa_chain", lambda *_args: chain)
    for executable, expected in (("SuperSlicer.exe", "classic"), ("PrusaSlicer.exe", "arachne")):
        setup = handover.SlicerSetup(Path(executable), "prusa", base_process="Native")
        foundation = manufacturer.base_settings(profile, "standard", setup)
        assert foundation.settings.shell.wall_generator == expected


def test_part_acceleration_limits_native_roles_without_raising_slower_ones():
    base = print_settings.resolve(profiles.make_profile())
    native = {
        "default_acceleration": "5000",
        "inner_wall_acceleration": "5000",
        "outer_wall_acceleration": "100",
        "initial_layer_acceleration": "1000",
        "travel_acceleration": "10000",
        "bridge_acceleration": "50%",
    }
    written = handover.object_keys(
        base,
        [_advice("speed.acceleration", 321.0, base)],
        "orca",
        program="crealityprint",
        native=native,
    )
    assert written["inner_wall_acceleration"] == "321"
    assert "outer_wall_acceleration" not in written
    assert "initial_layer_acceleration" not in written
    assert "travel_acceleration" not in written
    assert "bridge_acceleration" not in written


@pytest.mark.parametrize(
    "wanted,native_role,expected",
    [
        ({"speed.outer_wall": 17.0, "speed.inner_wall": 29.0}, "140", "17"),
        ({"speed.inner_wall": 29.0}, "140", "29"),
        ({"speed.outer_wall": 17.0}, "50%", "17"),
        ({"speed.outer_wall": 17.0, "speed.inner_wall": 29.0}, "50%", None),
        ({"speed.outer_wall": 17.0}, "10", None),
    ],
)
def test_part_speed_limits_native_small_perimeters(wanted, native_role, expected):
    base = print_settings.resolve(profiles.make_profile())
    native = {
        "small_perimeter_speed": native_role,
        "external_perimeter_speed": "140",
        "perimeter_speed": "140",
        "first_layer_speed": "25",
        "travel_speed": "180",
    }
    written = handover.object_keys(
        base,
        [_advice(path, value, base) for path, value in wanted.items()],
        "prusa",
        program="prusaslicer",
        native=native,
    )
    assert written.get("small_perimeter_speed") == expected
    assert "first_layer_speed" not in written
    assert "travel_speed" not in written


def test_part_speed_loads_native_roles_without_an_acceleration_choice(monkeypatch):
    profile = profiles.make_profile("prusa-mini", "pla")
    chain = manufacturer.PrusaChain(
        "MINI",
        "Native",
        "PLA",
        {
            "external_perimeter_speed": "140",
            "perimeter_speed": "140",
            "small_perimeter_speed": "140",
        },
    )
    monkeypatch.setattr(manufacturer, "prusa_chain", lambda *_args: chain)
    setup = handover.SlicerSetup(Path("PrusaSlicer.exe"), "prusa", base_process="Native")
    base = manufacturer.base_settings(profile, "standard", setup).settings
    base = print_settings.with_choice(base, "filament.max_flow", 100.0)
    selected = print_settings.with_accepted(base, "speed.outer_wall", 17.0)
    split = handover.split_for_parts(selected, profile, setup, "prusa")
    assert split.per_part == {"speed.outer_wall"}
    target = writer._values_for(
        split,
        [_advice("speed.outer_wall", 17.0, base)],
        [],
        "prusa",
        program="prusaslicer",
        profile=profile,
    )
    assert target.keys["small_perimeter_speed"] == "17"
    assert not writer._values_for(split, [], [], "prusa", profile=profile).keys


@pytest.mark.parametrize("program", ["PrusaSlicer.exe", "SuperSlicer.exe"])
@pytest.mark.parametrize("foundation", ["none", "absent", "missing", "unreadable", "malformed"])
@pytest.mark.parametrize("accepted", [False, True])
def test_prusa_fallback_writes_small_roles_for_own_and_part_speed(
    tmp_path, monkeypatch, program, foundation, accepted
):
    """Auch ohne Kette muss 5 mm/s unter der eingebauten kleinen Rolle gelten.

    Gemessen mit leerem Datadir: Prusa 2.9.6 nimmt 15 mm/s, SuperSlicer
    2.5.59.13 50 % des Innenwandtempos. Beide liegen hier über 5 mm/s.
    """
    profile = profiles.make_profile("generic-220", "pla")
    setup = None if foundation == "none" else handover.SlicerSetup(Path(program), "prusa")
    if foundation in {"missing", "unreadable", "malformed"}:
        setup = handover.SlicerSetup(
            Path(program), "prusa", machine_profile="Machine", base_process="Process"
        )
        broken = tmp_path / "printer" / "Broken.ini"
        broken.parent.mkdir()
        if foundation == "malformed":
            broken.write_bytes(b"\xff\xfe\xff")
        else:
            broken.write_text("inherits = Missing parent\n", encoding="utf-8")
        monkeypatch.setattr(handover, "machine_for", lambda *_args: "Machine")
        monkeypatch.setattr(handover, "_profile_roots", lambda *_args: ())
        monkeypatch.setattr(
            handover,
            "profile_source",
            lambda *_args: None if foundation == "missing" else broken,
        )
    base = print_settings.resolve(profile)
    base = print_settings.with_choice(base, "filament.max_flow", 100.0)
    base = print_settings.with_choice(base, "speed.inner_wall", 60.0)
    choose = print_settings.with_accepted if accepted else print_settings.with_choice
    selected = choose(base, "speed.outer_wall", 5.0)
    objects = [
        SceneObject(
            id=f"part-{index}",
            name=f"Part {index}",
            mesh=MeshData.of(trimesh.creation.cylinder(radius=6.0, height=6.0)),
        )
        for index in range(2)
    ]

    def requested(entry, _mesh, settings, *_args, **_kwargs):
        return (
            [_advice("speed.outer_wall", 5.0, settings)]
            if accepted and entry.id == "part-0"
            else []
        )

    monkeypatch.setattr(writer, "part_advice", requested)
    path, _findings = writer.write_assembly(
        objects,
        tmp_path,
        project_name="Fallback",
        profile=profile,
        settings=selected,
        flavour="prusa",
        setup=setup,
    )
    if foundation in {"missing", "unreadable"}:
        assert any(item.code == "slicer.process_unreadable" for item in _findings)
    with zipfile.ZipFile(path) as archive:
        plate = archive.read("Metadata/Slic3r_PE.config").decode("utf-8")
        root = ET.fromstring(archive.read("Metadata/Slic3r_PE_model.config"))
    if accepted:
        object_values = [
            {item.get("key"): item.get("value") for item in obj.findall("metadata")}
            for obj in root.findall("object")
        ]
        assert len(object_values) == 2
        assert object_values[0]["external_perimeter_speed"] == "5"
        assert object_values[0]["small_perimeter_speed"] == "5"
        assert "small_perimeter_speed" not in object_values[1]
        assert "external_perimeter_speed" not in object_values[1]
        assert "small_perimeter_speed = 5\n" not in plate
    else:
        written, expected = handover.prusa_values(selected, profile, setup, console=True)
        assert written["small_perimeter_speed"] == "5"
        assert expected["small_perimeter_speed"] == "5"
        assert "small_perimeter_speed = 5\n" in plate


@pytest.mark.parametrize(
    "program,outer,expected",
    [
        ("PrusaSlicer.exe", 20.0, None),
        ("SuperSlicer.exe", 40.0, None),
        ("SuperSlicer.exe", 20.0, "20"),
    ],
)
def test_prusa_fallback_preserves_slower_native_small_roles(program, outer, expected):
    """Die absolute Prusa- und relative SuperSlicer-Vorgabe werden nie erhöht."""
    profile = profiles.make_profile("generic-220", "pla")
    base = print_settings.resolve(profile)
    base = print_settings.with_choice(base, "filament.max_flow", 100.0)
    base = print_settings.with_choice(base, "speed.inner_wall", 60.0)
    base = print_settings.with_choice(base, "speed.outer_wall", outer)
    setup = handover.SlicerSetup(Path(program), "prusa")
    written, _expected = handover.prusa_values(base, profile, setup, console=False)
    assert written.get("small_perimeter_speed") == expected


@pytest.mark.parametrize("program", [None, "unknown.exe", "prusa"])
@pytest.mark.parametrize("inner", [20.0, 60.0])
@pytest.mark.parametrize("outer", [5.0, 12.0, 15.0, 20.0, 30.0])
@pytest.mark.parametrize("accepted", [False, True])
def test_unknown_prusa_program_keeps_both_measured_small_role_limits(
    tmp_path, monkeypatch, program, inner, outer, accepted
):
    """Ein Familienexport darf weder 15 mm/s noch 50 % der Innenwand erhöhen."""
    profile = profiles.make_profile("generic-220", "pla")
    setup = handover.SlicerSetup(Path(program), "prusa") if program else None
    base = print_settings.with_choice(print_settings.resolve(profile), "filament.max_flow", 100.0)
    base = print_settings.with_choice(base, "speed.inner_wall", inner)
    choose = print_settings.with_accepted if accepted else print_settings.with_choice
    selected = choose(base, "speed.outer_wall", outer)
    objects = [
        SceneObject(
            id=f"part-{index}",
            name=f"Part {index}",
            mesh=MeshData.of(trimesh.creation.cylinder(radius=1.0, height=6.0)),
        )
        for index in range(2)
    ]

    def requested(entry, _mesh, settings, *_args, **_kwargs):
        return (
            [_advice("speed.outer_wall", outer, settings)]
            if accepted and entry.id == "part-0"
            else []
        )

    monkeypatch.setattr(writer, "part_advice", requested)
    path, _findings = writer.write_assembly(
        objects,
        tmp_path,
        project_name="Family",
        profile=profile,
        settings=selected,
        flavour="prusa",
        setup=setup,
    )
    # Bei einer eigenen Plattenwahl gilt auch die explizite Innenwand als
    # Obergrenze; am einzelnen Außenwandrat bleibt die Innenwand unangetastet.
    limit = outer if accepted else min(inner, outer)
    native = (15.0, 0.5 * inner)
    expected = f"{min(limit, *native):g}" if max(native) > limit else None
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("Metadata/Slic3r_PE_model.config"))
        plate = archive.read("Metadata/Slic3r_PE.config").decode("utf-8")
    if accepted:
        values = [
            {entry.get("key"): entry.get("value") for entry in obj.findall("metadata")}
            for obj in root.findall("object")
        ]
        assert len(values) == 2
        assert values[0].get("small_perimeter_speed") == expected
        assert "small_perimeter_speed" not in values[1]
        assert "external_perimeter_speed" not in values[1]
        assert "small_perimeter_speed =" not in plate
    else:
        written, expected_values = handover.prusa_values(selected, profile, setup, console=True)
        assert written.get("small_perimeter_speed") == expected
        assert expected_values.get("small_perimeter_speed") == expected
        assert (
            (f"small_perimeter_speed = {expected}\n" in plate)
            if expected
            else "small_perimeter_speed =" not in plate
        )


def test_global_prusa_acceleration_limits_roles_and_keeps_the_own_outer_choice(monkeypatch):
    profile = profiles.make_profile("prusa-mini", "pla")
    chain = manufacturer.PrusaChain(
        "MINI",
        "Native",
        "PLA",
        {
            "default_acceleration": "5000",
            "perimeter_acceleration": "2500",
            "infill_acceleration": "4000",
            "external_perimeter_acceleration": "1500",
            "bridge_acceleration": "200",
            "first_layer_acceleration": "800",
            "travel_acceleration": "4000",
        },
    )
    monkeypatch.setattr(manufacturer, "prusa_chain", lambda *_args: chain)
    setup = handover.SlicerSetup(Path("PrusaSlicer.exe"), "prusa", base_process="Native")
    base = manufacturer.base_settings(profile, "standard", setup).settings
    selected = print_settings.with_choice(base, "speed.acceleration", 321.0)
    selected = print_settings.with_choice(selected, "speed.outer_wall_acceleration", 777.0)
    written, _expected = handover.prusa_values(selected, profile, setup, console=False)
    assert written["perimeter_acceleration"] == "321"
    assert written["infill_acceleration"] == "321"
    assert written["external_perimeter_acceleration"] == "777"
    assert written["bridge_acceleration"] == "200"
    assert written["first_layer_acceleration"] == "800"
    assert written["travel_acceleration"] == "4000"


def test_cura_unfulfilled_style_is_not_reapplied_to_every_part():
    base = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "support.style", "none"
    )
    plate = print_settings.with_accepted(base, "support.style", "tree")
    split = handover.PartSplit(
        plate, base, frozenset({"support.style"}), revert=True, accepted=plate
    )
    wanted = _advice("support.style", "grid", base)
    values = writer._values_for(split, [wanted], [], "cura")
    assert writer._unserved(split, plate, [values]) == []
    again = writer._values_for(split, values.applied, values.unavailable, "cura")
    assert again.keys["support_enable"] == "true"
    assert [entry.value for entry in again.unavailable] == ["grid"]
    assert not again.applied


def test_cura_plate_without_support_still_allows_a_part_to_enable_grid():
    base = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "support.style", "none"
    )
    split = handover.PartSplit(base, base, frozenset({"support.style"}), revert=True)
    values = writer._values_for(split, [_advice("support.style", "grid", base)], [], "cura")
    assert values.keys["support_enable"] == "true"
    assert values.effective.support.style == "grid"
    assert [entry.value for entry in values.applied] == ["grid"]
    assert not values.unavailable


@pytest.mark.parametrize("style", ["none", "tree", "grid"])
def test_cura_automatic_support_uses_the_plate_style_without_false_warning(style):
    plate = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "support.style", style
    )
    split = handover.PartSplit(plate, plate, frozenset({"support.style"}), revert=True)
    values = writer._values_for(split, [_advice("support.style", "auto", plate)], [], "cura")
    assert values.keys["support_enable"] == "true"
    assert values.effective.support.style == ("tree" if style == "tree" else "grid")
    assert not values.unavailable
    assert len(values.applied) == 1


@pytest.mark.parametrize("executable", [None, "unknown.exe", "prusa"])
@pytest.mark.parametrize("flavour", ["prusa", "orca"])
def test_file_export_without_program_only_promises_shared_object_capabilities(
    tmp_path, monkeypatch, flavour, executable
):
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    paths = {"speed.acceleration": 321.0, "speed.outer_wall_acceleration": 123.0}
    for path, value in paths.items():
        settings = print_settings.with_accepted(settings, path, value)
    objects = [
        SceneObject(
            id=f"part-{index}",
            name=f"Part {index}",
            mesh=MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 6.0))),
        )
        for index in range(2)
    ]

    def requested(entry, _mesh, base, *_args, **_kwargs):
        return (
            [_advice(path, value, base) for path, value in paths.items()]
            if entry.id == "part-0"
            else []
        )

    monkeypatch.setattr(writer, "part_advice", requested)
    path, findings = writer.write_assembly(
        objects,
        tmp_path,
        project_name="Shared",
        profile=profile,
        settings=settings,
        flavour=flavour,
        setup=handover.SlicerSetup(Path(executable), flavour) if executable else None,
    )
    assert not [entry for entry in findings if entry.code == "export.part_setting"]
    reported = {
        (entry.object_id, entry.values["setting"])
        for entry in findings
        if entry.code == "export.part_setting_unavailable"
    }
    assert reported == {("part-1", key) for key in paths}
    with zipfile.ZipFile(path) as archive:
        name = (
            "Metadata/Slic3r_PE_model.config"
            if flavour == "prusa"
            else "Metadata/model_settings.config"
        )
        root = ET.fromstring(archive.read(name))
    assert not any(
        entry.get("key")
        in {
            "default_acceleration",
            "outer_wall_acceleration",
            "external_perimeter_acceleration",
            "perimeter_speed",
            "external_perimeter_speed",
        }
        for entry in root.iter("metadata")
    )


# Die unabhängigen Messungen aus RM-317 und RM-318 umfassen 17 dieser Pfade;
# ``support.spare_ledges`` belegt der Eiffelturm (RM-582: ElegooSlicer 869 → 216 m
# Stütze, dieselbe Stützsperre wie die Kanäle). Den Stützkontakt (RM-583) belegt
# eine Platte mit zwei gestützten Stufenkörpern, einer mit Objektwerten, in allen
# acht Programmen (``.claude/.state/drache-2026-10-08/kontakt_je_teil.py``):
# geschrieben 0,4 gegen 0,2 mm und so weiter, gemessen je Programm in
# ``konzepte/begruendungen/regel-druckrat.md``; Cura nimmt die Lücke nicht je Netz.
# Feine Schichten und Deckschichtdicke (RM-586) belegt eine Kuppe neben einem
# Klotz (``scratchpad/rm586/slicer_fein.py``, Archiv RM-586): die Kuppe oben mit
# 0,1 mm, der Klotz gleichmäßig, in allen sieben Programmen, die die Kurve lesen;
# die Mindestdicke 0,8 bzw. 1,2 mm je Teil hebt die dünne Füllung um 0,1 bis 0,2 mm,
# außer in SuperSlicer, der sie in Lagen der normalen Schicht zählt. Die
# Menge wird absichtlich nicht aus PART_PATHS oder den Schlüsseltabellen
# gebaut: ein neuer Pfad braucht einen eigenen Wirkungsnachweis.
MEASURED_PART_PATHS = frozenset(
    {
        "adhesion.kind",
        "adhesion.brim_gap",
        "infill.density",
        "layers.fine_layer_height",
        "layers.line_width",
        "shell.ironing",
        "shell.outer_wall_first",
        "shell.precise_outer_wall",
        "shell.scarf_seam",
        "shell.top_thickness",
        "shell.wall_count",
        "shell.wall_generator",
        "speed.acceleration",
        "speed.inner_wall",
        "speed.outer_wall",
        "speed.outer_wall_acceleration",
        "support.block_channels",
        "support.bottom_interface_layers",
        "support.interface_layers",
        "support.interface_spacing",
        "support.placement",
        "support.spare_ledges",
        "support.style",
        "support.z_gap",
    }
)


@pytest.mark.parametrize(
    "program,flavour,absent",
    [
        ("orcaslicer", "orca", set()),
        ("elegooslicer", "orca", set()),
        ("crealityprint", "orca", set()),
        ("anycubicslicernext", "orca", set()),
        ("bambustudio", "orca", {"speed.acceleration", "speed.outer_wall_acceleration"}),
        (
            "prusaslicer",
            "prusa",
            {
                "shell.precise_outer_wall",
                "speed.acceleration",
                "speed.outer_wall_acceleration",
            },
        ),
        (
            "superslicer",
            "prusa",
            {
                "shell.precise_outer_wall",
                "shell.scarf_seam",
                "shell.top_thickness",
                "speed.acceleration",
                "speed.outer_wall_acceleration",
            },
        ),
        (
            "cura",
            "cura",
            {
                "adhesion.kind",
                "adhesion.brim_gap",
                "layers.fine_layer_height",
                "layers.line_width",
                "support.interface_spacing",
                "support.placement",
                "shell.precise_outer_wall",
                "shell.top_thickness",
                "shell.wall_generator",
            },
        ),
    ],
)
def test_every_measured_part_path_matches_the_program_capability(program, flavour, absent):
    from app.core.slice import advise

    assert advise.PART_PATHS == MEASURED_PART_PATHS
    assert handover._part_paths(flavour, program) == MEASURED_PART_PATHS - absent
