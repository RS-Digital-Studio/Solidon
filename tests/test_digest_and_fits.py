"""The scene digest and the fit check (Bauplan §23, §14)."""

from __future__ import annotations

from pathlib import Path

from app.core.geom.mesh import read_mesh
from app.core.geom.transform import place_on_bed
from app.core.ingest.loader import normalise
from app.core.knowledge import profiles
from app.core.perceive.digest import digest
from app.core.perceive.features import detect
from app.core.scene import fits as fit_check
from app.core.types import (
    Document,
    Feature,
    FeatureRef,
    Finding,
    Fit,
    Origin,
    Parameter,
    Profile,
    Report,
    Scene,
    SceneObject,
    Transaction,
)

MESHES = Path(__file__).parent / "data" / "meshes"


def plate_scene(profile: Profile) -> Scene:
    mesh = place_on_bed(
        normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh
    )
    entry = SceneObject(id="obj_1", name="Halterung", mesh=mesh, features=detect(mesh))
    return Scene(objects={"obj_1": entry}, profile=profile)


# --- digest ---------------------------------------------------------------------


def test_the_digest_names_the_scene_and_the_printer(profile: Profile) -> None:
    text = digest(plate_scene(profile))

    assert "centauri-carbon-2" in text
    assert "petg" in text
    assert "Startwert" in text, "an uncalibrated material says so (§28.3)"


def test_the_digest_describes_every_object(profile: Profile) -> None:
    text = digest(plate_scene(profile))

    assert 'obj_1  "Halterung"' in text
    assert "80.0 × 50.0 × 8.0 mm" in text
    assert "cm³" in text
    assert "geschlossen" in text
    assert "auf Bett" in text


def test_the_digest_lists_features_by_name(profile: Profile) -> None:
    """Leitprinzip 5: the agent refers to these names, never to coordinates."""
    text = digest(plate_scene(profile))

    assert "hole_1" in text
    # A bore made of 48 segments measures a hair under its nominal diameter.
    assert "Ø 5.1" in text or "Ø 5.2" in text
    assert "Achse +Z" in text
    assert "Durchgang" in text
    assert "face_1" in text


def test_the_digest_shows_parameters_and_selection(profile: Profile) -> None:
    scene = plate_scene(profile)
    scene.parameters["breite"] = Parameter(name="breite", value=84.0, unit="mm")

    text = digest(scene, selection=("obj_1", "hole_3"))

    assert "breite=84 mm" in text
    assert "Auswahl: obj_1 · hole_3" in text


def test_the_digest_carries_warnings_but_not_noise(profile: Profile) -> None:
    """§26.1: the agent has to know what it is standing on."""
    scene = plate_scene(profile)
    scene.report = Report(
        (
            Finding(code="a", severity="warning", message="Dünnstelle bei 0.9 mm"),
            Finding(code="b", severity="info", message="Punkte verschweißt"),
        )
    )
    text = digest(scene)

    assert "Dünnstelle" in text
    assert "verschweißt" not in text, "notes are not what the agent needs to worry about"


def test_the_digest_summarises_the_stack(profile: Profile) -> None:
    document = Document(format_version=1, app_version="0.0.1")
    document.transactions.append(
        Transaction(id="t1", title="Import und Reparatur", ops=(1, 2), origin=Origin(by="user"))
    )
    document.transactions.append(
        Transaction(id="t2", title="Teilen", ops=(3,), origin=Origin(by="agent"))
    )

    text = digest(plate_scene(profile), document)

    assert 't1 "Import und Reparatur"' in text
    assert "Nutzer" in text and "Agent" in text


# --- fits -----------------------------------------------------------------------


def pin_and_hole(hole_diameter: float, pin_diameter: float, profile: Profile) -> Scene:
    hole = Feature(
        id="hole_1", kind="hole", provenance="detected", params={"diameter": hole_diameter}
    )
    pin = Feature(id="pin_1", kind="pin", provenance="generated", params={"diameter": pin_diameter})
    first = SceneObject(id="obj_1", name="Buchse", mesh=_dummy(), features={"hole_1": hole})
    second = SceneObject(id="obj_2", name="Stift", mesh=_dummy(), features={"pin_1": pin})
    return Scene(objects={"obj_1": first, "obj_2": second}, profile=profile)


def _dummy():
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


def clearance_fit() -> Fit:
    return Fit(
        name="stift_1",
        a=FeatureRef("obj_1", "hole_1"),
        b=FeatureRef("obj_2", "pin_1"),
        kind="clearance",
        tolerance="auto:",
    )


def test_a_fit_that_matches_the_profile_says_nothing(profile: Profile) -> None:
    gap = profiles.material("petg").clearance
    scene = pin_and_hole(5.0 + gap, 5.0, profile)
    scene.fits.append(clearance_fit())

    assert fit_check.check(scene, profile) == []


def test_a_tight_fit_is_reported(profile: Profile) -> None:
    """§14: violations appear in the report, never silently."""
    scene = pin_and_hole(5.02, 5.0, profile)
    scene.fits.append(clearance_fit())

    findings = fit_check.check(scene, profile)

    assert findings and findings[0].code == "fit.violated"
    assert "enger" in str(findings[0].message)


def test_a_loose_fit_is_reported(profile: Profile) -> None:
    scene = pin_and_hole(6.0, 5.0, profile)
    scene.fits.append(clearance_fit())

    findings = fit_check.check(scene, profile)
    assert findings and "loser" in str(findings[0].message)


def test_the_tolerance_follows_the_material(profile: Profile) -> None:
    """AGENTS.md rule 7: the number lives in the profile, not in the file."""
    tpu = profiles.make_profile("centauri-carbon-2", "tpu-95a")
    scene = pin_and_hole(5.0 + profiles.material("petg").clearance, 5.0, profile)
    scene.fits.append(clearance_fit())

    assert fit_check.check(scene, profile) == []
    scene.profile = tpu
    assert fit_check.check(scene, tpu), "the same geometry is wrong for a softer material"


def two_faces(offset: float, normal_b: tuple[float, float, float], profile: Profile) -> Scene:
    """Two faces that are meant to sit in one plane, and one that is offset."""
    lower = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"area": 100.0, "centre": (0.0, 0.0, 10.0), "normal": (0.0, 0.0, 1.0)},
    )
    upper = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"area": 100.0, "centre": (0.0, 0.0, 10.0 + offset), "normal": normal_b},
    )
    return Scene(
        objects={
            "obj_1": SceneObject(
                id="obj_1", name="Kiste", mesh=_dummy(), features={"face_1": lower}
            ),
            "obj_2": SceneObject(
                id="obj_2", name="Deckel", mesh=_dummy(), features={"face_1": upper}
            ),
        },
        profile=profile,
    )


def flush_fit() -> Fit:
    return Fit(
        name="deckel",
        a=FeatureRef("obj_1", "face_1"),
        b=FeatureRef("obj_2", "face_1"),
        kind="flush",
        tolerance="auto:",
    )


def test_two_faces_in_one_plane_say_nothing(profile: Profile) -> None:
    """§14: ``flush`` was accepted and never checked — a fit kind as a stage prop."""
    scene = two_faces(0.0, (0.0, 0.0, -1.0), profile)
    scene.fits.append(flush_fit())

    assert fit_check.check(scene, profile) == []


def test_a_lid_that_sits_proud_is_reported(profile: Profile) -> None:
    scene = two_faces(0.3, (0.0, 0.0, -1.0), profile)
    scene.fits.append(flush_fit())

    findings = fit_check.check(scene, profile)

    assert findings and findings[0].code == "fit.violated"
    assert findings[0].values["actual"].startswith("0.3")


def test_faces_at_an_angle_are_a_different_mistake(profile: Profile) -> None:
    """Two planes meeting at a corner have no distance worth reporting."""
    scene = two_faces(0.0, (1.0, 0.0, 0.0), profile)
    scene.fits.append(flush_fit())

    findings = fit_check.check(scene, profile)

    assert findings and "parallel" in str(findings[0].message)


def test_a_flush_fit_needs_two_faces(profile: Profile) -> None:
    scene = pin_and_hole(5.25, 5.0, profile)
    scene.fits.append(
        Fit(
            name="falsch",
            a=FeatureRef("obj_1", "hole_1"),
            b=FeatureRef("obj_2", "pin_1"),
            kind="flush",
            tolerance="auto:",
        )
    )

    findings = fit_check.check(scene, profile)

    assert findings and findings[0].code == "fit.not_measurable"


def test_a_fit_pointing_at_nothing_is_an_error(profile: Profile) -> None:
    scene = pin_and_hole(5.25, 5.0, profile)
    scene.fits.append(
        Fit(name="weg", a=FeatureRef("obj_1", "hole_9"), b=FeatureRef("obj_2", "pin_1"))
    )

    findings = fit_check.check(scene, profile)
    assert findings and findings[0].code == "fit.missing_feature"
    assert findings[0].severity == "error"


def test_fits_can_be_added_and_removed() -> None:
    entries: list[Fit] = []
    entries = fit_check.add(entries, clearance_fit())
    assert len(entries) == 1

    entries = fit_check.add(entries, clearance_fit())
    assert len(entries) == 1, "the same name replaces, it does not pile up"

    entries = fit_check.remove(entries, "stift_1")
    assert entries == []


# --- a scene is not one material (§12) ------------------------------------------


def test_a_softer_body_gets_its_own_clearance(profile: Profile) -> None:
    """The case the model folder showed: a TPU seal in a PETG housing.

    Computed with the project material the gap is 0,25 — the number for PETG.
    The seal is TPU and wants 0,35, and the difference is not academic: at
    0,25 the assembly is a press fit nobody asked for.
    """
    scene = pin_and_hole(5.0 + profiles.material("tpu-95a").clearance, 5.0, profile)
    scene.fits.append(clearance_fit())
    assert fit_check.check(scene, profile), "with one material this gap is too loose"

    scene.objects["obj_2"].material = "tpu-95a"

    assert fit_check.check(scene, profile) == []


def test_the_finding_names_both_materials(profile: Profile) -> None:
    scene = pin_and_hole(5.0, 5.0, profile)
    scene.objects["obj_2"].material = "tpu-95a"
    scene.fits.append(clearance_fit())

    findings = fit_check.check(scene, profile)

    assert findings and findings[0].values["materials"] == "petg, tpu-95a"


def test_one_material_is_not_worth_mentioning(profile: Profile) -> None:
    """Noise in a report is what makes the report unread."""
    scene = pin_and_hole(5.0, 5.0, profile)
    scene.fits.append(clearance_fit())

    findings = fit_check.check(scene, profile)

    assert findings and "materials" not in findings[0].values


def test_a_named_material_stays_what_it_says(profile: Profile) -> None:
    """`auto:petg` was written down on purpose and no body overrules it (§12)."""
    scene = pin_and_hole(5.0 + profiles.material("petg").clearance, 5.0, profile)
    scene.objects["obj_2"].material = "tpu-95a"
    scene.fits.append(
        Fit(
            name="stift_1",
            a=FeatureRef("obj_1", "hole_1"),
            b=FeatureRef("obj_2", "pin_1"),
            kind="clearance",
            tolerance="auto:petg",
        )
    )

    assert fit_check.check(scene, profile) == []


def test_a_press_fit_takes_the_gentler_number(profile: Profile) -> None:
    """Negative values: the larger one is the smaller interference.

    PETG presses with -0,05 and TPU with -0,10. Pressing a TPU pin into a PETG
    hole with the TPU figure means 0,1 mm of oversize in a body that does not
    give — the housing splits. -0,05 holds and survives.
    """
    scene = pin_and_hole(5.0, 5.05, profile)
    scene.objects["obj_2"].material = "tpu-95a"
    scene.fits.append(
        Fit(
            name="press_1",
            a=FeatureRef("obj_1", "hole_1"),
            b=FeatureRef("obj_2", "pin_1"),
            kind="press",
            tolerance="auto:",
        )
    )

    assert fit_check.check(scene, profile) == []


def test_the_digest_names_a_body_that_is_not_in_the_project_material(profile: Profile) -> None:
    scene = plate_scene(profile)
    next(iter(scene.objects.values())).material = "tpu-95a"

    assert "tpu-95a" in digest(scene)
