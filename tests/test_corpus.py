"""Die drei Korpusdateien, die fehlten (Bauplan §34).

Jede von ihnen existiert, um ein Versprechen prüfbar zu machen, das vorher nur
hingeschrieben war: dass die Rückfallkette mit einer Selbstdurchdringung noch
zurechtkommt, dass eine hier geschriebene 3MF hier mit ihren Farben gelesen
wird, und dass ein Passungspaar bemerkt, wenn sich der Boden unter ihm bewegt.
"""

from __future__ import annotations

import fnmatch
import math
import re
import subprocess
from pathlib import Path, PurePosixPath

import pytest

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest import threemf
from app.core.ingest.loader import normalise, read_model
from app.core.knowledge import profiles
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene import fits as fit_check
from app.core.scene.project import ProjectSources, load
from app.core.types import Profile
from app.core.units import EPS_GEOM

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


def assembled_project():
    """Die alte Korpusdatei unverändert laden und ihre Einbaulage herstellen.

    Die Grundkörper liegen in der Quelldatei beide auf z=0 und durchdringen
    sich. Erst auf der Schulter bei z=6 sitzt die Platte um den freien Stift.
    Die Korrektur ist ein regulärer Schritt, kein Umschreiben des Altformats.
    """
    opened = project()
    History(opened.document).apply(
        "Platte auf die Stiftschulter setzen",
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dz": 6.0})],
    )
    return opened


@pytest.mark.parametrize("material,diameter", [("petg", 6.2), ("pla", 6.15)])
def test_the_legacy_assembly_reports_its_intersecting_shoulders(
    material: str, diameter: float
) -> None:
    """Passende Kreismaße heben die echte Kollision der alten Grundkörper nicht auf."""
    opened = project()
    result = evaluate(
        opened.document,
        profiles.make_profile("centauri-carbon-2", material),
        sources=ProjectSources(opened),
    )

    assert result.complete
    findings = {
        finding.code: finding
        for finding in result.scene.report.findings
        if finding.code.startswith("fit.")
    }
    assert set(findings) == (
        {"fit.collision"} if material == "petg" else {"fit.collision", "fit.mesh_uncertain"}
    )
    collision = findings["fit.collision"]
    # Grundkörper 20 mal 20 mal 6 mm abzüglich der durchgehenden 48-eckigen Bohrung.
    bore_area = 48 / 2 * (diameter / 2) ** 2 * math.sin(math.tau / 48)
    assert collision.values["overlap_mm3"] == pytest.approx((20 * 20 - bore_area) * 6)
    assert collision.values["intersects"] is True
    assert collision.severity == "warning"


def test_the_assembly_holds_with_the_material_it_was_built_for(profile: Profile) -> None:
    """6 mm nominal werden eine 6,2-mm-Bohrung, der Stift ist 5,95 — das sind
    0,25 Spiel.
    """
    opened = assembled_project()

    result = evaluate(opened.document, profile, sources=ProjectSources(opened))

    assert result.complete
    codes = {finding.code for finding in result.scene.report.findings}
    assert not {code for code in codes if code.startswith("fit.")}, (
        "PETG is what both the circle dimensions and the mesh clearance were chosen for — "
        "a fit that holds is no finding"
    )
    proof = fit_check.overlap(result.scene, result.scene.fits[0])
    assert proof is not None, "the assembled pose is proven, so the probe has a number"
    assert proof.source == "mesh"
    assert proof.overlap_mm3 == pytest.approx(0.0)
    assert proof.intersects is False
    assert "bore.compensated" in codes, "and the bore says it was widened"


def test_the_fit_notices_when_the_ground_moves() -> None:
    """§14: die Prüfung läuft bei jeder Auswertung, nicht einmal beim
    Hinschreiben.

    In einem anderen Material gedruckt kommt die Bohrung anders heraus — die
    Toleranz bleibt, was das Paar sagt. Die Kreisdurchmesser ergeben in PLA
    0,20 mm Spiel und liegen damit gerade noch im Prüfbereich um 0,25 mm.
    Der tatsächliche 48-eckige Mantel unterschreitet dessen Untergrenze:
    Eine unsichere Netzpassung muss sichtbar bleiben, obwohl die vollständigen
    Körper in der hergestellten Einbaulage nachweislich nicht kollidieren.
    """
    opened = assembled_project()
    other = profiles.make_profile("centauri-carbon-2", "pla")

    result = evaluate(opened.document, other, sources=ProjectSources(opened))

    assert result.complete
    findings = {
        finding.code: finding
        for finding in result.scene.report.findings
        if finding.code.startswith("fit.")
    }
    assert set(findings) == {"fit.mesh_uncertain"}
    uncertainty = findings["fit.mesh_uncertain"]
    assert uncertainty.severity == "warning"
    assert uncertainty.values["fit"] == "stift_1"
    assert uncertainty.values["clearance_min_mm"] == pytest.approx(
        6.15 * math.cos(math.pi / 48) - 5.95, abs=EPS_GEOM
    )
    assert uncertainty.values["clearance_max_mm"] == pytest.approx(0.20, abs=EPS_GEOM)
    assert uncertainty.values["expected"] == "0.25 mm"
    proof = fit_check.overlap(result.scene, result.scene.fits[0])
    assert proof is not None
    assert proof.overlap_mm3 == pytest.approx(0.0)
    assert proof.intersects is False


def test_the_pair_points_at_features_that_exist(profile: Profile) -> None:
    opened = project()

    result = evaluate(opened.document, profile, sources=ProjectSources(opened))

    for fit in opened.document.fits:
        for reference in (fit.a, fit.b):
            entry = result.scene.objects[reference.object_id]
            assert reference.feature_id in entry.features, str(reference)


# --- jede Datei hat ihre Zeile ---------------------------------------------------


def _unlisted(names: list[str], readme: str) -> list[str]:
    """Die Dateien, die ``README.md`` weder mit Pfad noch Namen noch Stamm nennt.

    Genannt heißt: der Pfad relativ zu ``tests/data`` irgendwo im Text, der
    Dateiname oder der Stamm in Backticks, oder eine Familie in Backticks
    (``projects/example_v*.p3d``, auch ``<N>`` statt ``*``).
    """
    quoted = set(re.findall(r"`([^`\n]+)`", readme))
    families = [token.replace("<N>", "*") for token in quoted if "*" in token or "<N>" in token]
    return [
        name
        for name in names
        if name not in readme
        and PurePosixPath(name).name not in quoted
        and PurePosixPath(name).stem not in quoted
        and not any(fnmatch.fnmatchcase(name, family) for family in families)
    ]


def test_the_search_for_unlisted_files_finds_what_is_missing() -> None:
    """Der Fall mit bekanntem Ausgang: Pfad, Name, Stamm und Familie gelten, sonst nichts."""
    readme = "| `meshes/a.stl` | … `b.ply` … `c_v3` … `projects/example_v<N>.p3d` |"
    names = ["meshes/a.stl", "meshes/b.ply", "projects/c_v3.p3d", "projects/example_v7.p3d"]

    assert _unlisted([*names, "meshes/d.stl", "projects/example.p3d"], readme) == [
        "meshes/d.stl",
        "projects/example.p3d",
    ]


def test_every_corpus_file_has_its_line_in_the_readme() -> None:
    """``tests/data/CLAUDE.md`` verspricht je Datei eine Zeile in ``README.md`` (Inhalt,
    Kennzahl, Test). Gelesen wird die versionierte Menge aus Git, nicht der Ordner — ein
    örtliches Erzeugnis wie ``dense_1m.stl`` zählt nicht.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "."],
        cwd=DATA,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.split("\0")
    names = [name for name in listed if name and name not in {"README.md", "CLAUDE.md"}]
    assert len(names) > 100, f"nur {len(names)} Korpusdateien aus Git — dann prüft das nichts"

    missing = _unlisted(names, (DATA / "README.md").read_text(encoding="utf-8"))

    assert not missing, "ohne Zeile in tests/data/README.md:\n" + "\n".join(missing)
