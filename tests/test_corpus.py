"""Die drei Korpusdateien, die fehlten (Bauplan §34).

Jede von ihnen existiert, um ein Versprechen prüfbar zu machen, das vorher nur
hingeschrieben war: dass die Rückfallkette mit einer Selbstdurchdringung noch
zurechtkommt, dass eine hier geschriebene 3MF hier mit ihren Farben gelesen
wird, und dass ein Passungspaar bemerkt, wenn sich der Boden unter ihm bewegt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest import threemf
from app.core.ingest.loader import normalise, read_model
from app.core.knowledge import profiles
from app.core.scene import evaluate
from app.core.scene.project import ProjectSources, load
from app.core.types import Profile

DATA = Path(__file__).parent / "data"
MESHES = DATA / "meshes"


def body(name: str) -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


# --- die Selbstdurchdringung ----------------------------------------------------


def test_a_self_intersecting_body_still_goes_through_a_boolean() -> None:
    """§17.2: für genau diese Form gibt es die Kette.

    Dass der Kern sie derzeit auf der ersten Stufe löst, ist der Befund, kein
    Problem — und es lohnt, ihn festzuhalten: der Tag, an dem er damit
    aufhört, ist der Tag, an dem die Stufen drei und vier sich verdienen.
    """
    import trimesh

    mesh = body("broken_selfint.stl")
    tool = MeshData.of(trimesh.creation.cylinder(radius=3.0, height=60.0))

    outcome = boolean("difference", [mesh, tool])

    assert outcome.mesh.triangle_count > 0
    assert outcome.mesh.volume > 0.0
    assert outcome.solver.strategy in ("direct", "welded", "jittered", "voxel")


def test_the_two_blocks_really_do_pass_through_each_other() -> None:
    """Sonst wäre die Datei eine gewöhnliche Vereinigung und bewiese nichts."""
    mesh = body("broken_selfint.stl")

    assert mesh.triangle_count == 24, "two boxes, untouched by a boolean"
    assert mesh.bounds.size[0] == pytest.approx(28.0)


# --- die Farben -----------------------------------------------------------------


def test_the_coloured_file_comes_back_with_its_groups() -> None:
    payload = (MESHES / "colored.3mf").read_bytes()
    mesh = read_model(payload, ".3mf")

    groups = threemf.read(payload, mesh.triangle_count)

    assert groups is not None
    assert [entry.name for entry in groups.materials] == ["Rot", "Schwarz"]
    assert len(groups.slots) == mesh.triangle_count
    assert set(groups.slots) == {0, 1}


def test_both_colours_carry_real_area() -> None:
    """Eine Gruppe über drei Dreiecken bestünde die Prüfung darüber und hieße
    nichts.
    """
    payload = (MESHES / "colored.3mf").read_bytes()
    mesh = read_model(payload, ".3mf")
    groups = threemf.read(payload, mesh.triangle_count)
    assert groups is not None

    counted = {slot: groups.slots.count(slot) for slot in set(groups.slots)}
    assert min(counted.values()) >= 8, counted


# --- die Passung ----------------------------------------------------------------


def project():
    return load(DATA / "projects" / "assembly_fit.p3d")


def test_the_assembly_holds_with_the_material_it_was_built_for(profile: Profile) -> None:
    """6 mm nominal werden eine 6,2-mm-Bohrung, der Stift ist 5,95 — das sind
    0,25 Spiel.
    """
    opened = project()

    result = evaluate(opened.document, profile, sources=ProjectSources(opened))

    assert result.complete
    codes = {finding.code for finding in result.scene.report.findings}
    assert "fit.violated" not in codes, "PETG is what the numbers were chosen for"
    assert "bore.compensated" in codes, "and the bore says it was widened"


def test_the_fit_notices_when_the_ground_moves() -> None:
    """§14: die Prüfung läuft bei jeder Auswertung, nicht einmal beim
    Hinschreiben.

    In einem anderen Material gedruckt kommt die Bohrung anders heraus — die
    Toleranz bleibt, was das Paar sagt, und der Unterschied wird gemeldet statt
    still hingenommen.
    """
    opened = project()
    other = profiles.make_profile("centauri-carbon-2", "pla")

    result = evaluate(opened.document, other, sources=ProjectSources(opened))

    violations = [
        finding for finding in result.scene.report.findings if finding.code == "fit.violated"
    ]
    assert violations, "a fit written for PETG does not hold in PLA by itself"
    assert violations[0].values["fit"] == "stift_1"


def test_the_pair_points_at_features_that_exist(profile: Profile) -> None:
    opened = project()

    result = evaluate(opened.document, profile, sources=ProjectSources(opened))

    for fit in opened.document.fits:
        for reference in (fit.a, fit.b):
            entry = result.scene.objects[reference.object_id]
            assert reference.feature_id in entry.features, str(reference)
