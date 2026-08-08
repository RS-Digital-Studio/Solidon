"""Der Steckbrief der Szene und die Passungsprüfung (Bauplan §23, §14)."""

from __future__ import annotations

from pathlib import Path

from app.core.geom.mesh import read_mesh
from app.core.geom.transform import place_on_bed
from app.core.ingest.loader import normalise
from app.core.knowledge import profiles
from app.core.perceive.digest import digest, new_feature_lines
from app.core.perceive.features import detect
from app.core.scene import fits as fit_check
from app.core.types import (
    Document,
    Feature,
    FeatureRef,
    Finding,
    Fit,
    Operation,
    Origin,
    Parameter,
    PrintSettings,
    Profile,
    Report,
    Scene,
    SceneObject,
    Source,
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
    """Leitprinzip 5: der Agent bezieht sich auf diese Namen, nie auf
    Koordinaten.
    """
    text = digest(plate_scene(profile))

    assert "hole_1" in text
    # Eine Bohrung aus 48 Segmenten misst ein Haar unter ihrem Nenndurchmesser.
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
    """§26.1: der Agent muss wissen, worauf er steht."""
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


def test_the_stack_carries_the_values_of_its_ops(profile: Profile) -> None:
    """Konzept Agent-Vertiefung 3.2: nur Titel und Op-Nummern trugen nichts —
    der Agent konnte aus dem Verlauf nicht lernen, mit welchem Durchmesser
    gebohrt wurde. Gedeckelt, damit der Verlauf eine Zeile bleibt.
    """
    document = Document(format_version=1, app_version="0.0.1")
    document.ops.append(
        Operation(
            id=1,
            op="drill_hole",
            params={"diameter": 6.0, "x": 25.0, "y": -15.0, "z": 8.0, "axis": "z"},
        )
    )
    document.transactions.append(
        Transaction(id="t1", title="Bohren", ops=(1,), origin=Origin(by="agent"))
    )

    text = digest(plate_scene(profile), document)

    assert "drill_hole(diameter=6, x=25, y=-15, …)" in text


def test_the_digest_lists_fits_with_their_state(profile: Profile) -> None:
    """Konzept Agent-Vertiefung 3.2: der Agent konnte Passungen anlegen, aber
    nie nachsehen, welche es gibt. Verletzt oder nicht steht dabei — aus den
    Befunden, am Namen der Passung ausgewiesen.
    """
    document = Document(format_version=1, app_version="0.0.1")
    document.fits.append(clearance_fit())
    document.fits.append(
        Fit(
            name="deckel_1",
            a=FeatureRef("obj_1", "hole_2"),
            b=FeatureRef("obj_2", "pin_2"),
            kind="press",
            tolerance="auto:petg",
        )
    )
    scene = plate_scene(profile)
    scene.report = Report(
        (
            Finding(
                code="fit.violated",
                severity="warning",
                message="zu eng",
                values={"fit": "deckel_1"},
            ),
        )
    )

    text = digest(scene, document)

    assert "Passungen: stift_1 obj_1:hole_1 ↔ obj_2:pin_1 (clearance, auto:)" in text
    assert "deckel_1 obj_1:hole_2 ↔ obj_2:pin_2 (press, auto:petg) — verletzt" in text


def test_the_digest_names_print_settings_when_the_project_has_them(profile: Profile) -> None:
    """Konzept Agent-Vertiefung 3.2: die Zeile sagt, was eingestellt ist.
    ``None`` heißt Auflösung aus Stufe, Material und Drucker — dann sagt sie
    nichts, denn Drucker und Material stehen schon in der Szenenzeile.
    """
    document = Document(format_version=1, app_version="0.0.1")
    assert "Druckeinstellungen" not in digest(plate_scene(profile), document)

    document.print_settings = PrintSettings()
    text = digest(plate_scene(profile), document)

    assert 'Druckeinstellungen: "Standard" (standard)' in text
    assert "mm Wand" in text


def test_the_digest_names_the_sources(profile: Profile) -> None:
    """Konzept Agent-Vertiefung 3.2: „mach es wie beim importierten Deckel"
    scheitert sonst daran, dass der Agent nie erfährt, was importiert wurde.
    """
    document = Document(format_version=1, app_version="0.0.1")
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )

    text = digest(plate_scene(profile), document)

    assert "Quellen: src_1 plate_holes.stl (import)" in text


def test_the_digest_can_narrow_to_named_objects(profile: Profile) -> None:
    """Für ``read_digest`` mitten im Zug: nur die gefragten Objektzeilen,
    alles Szenenweite bleibt.
    """
    text = digest(plate_scene(profile), only=("obj_99",))

    assert "Szene: 1 Objekte" in text
    assert 'obj_1  "Halterung"' not in text


def test_new_features_are_named_with_their_ids(profile: Profile) -> None:
    """Konzept Agent-Vertiefung 3.1: nach ``drill_hole`` muss der Agent die ID
    der neuen Bohrung kennen — sonst zeigt der nächste Schritt ins Leere.
    """
    before = plate_scene(profile)
    after = plate_scene(profile)
    grown = dict(after.objects["obj_1"].features)
    grown["hole_99"] = Feature(
        id="hole_99",
        kind="hole",
        provenance="detected",
        params={"diameter": 6.0, "axis": (0.0, 0.0, 1.0), "through": True},
    )
    after.objects["obj_1"] = SceneObject(
        id="obj_1", name="Halterung", mesh=after.objects["obj_1"].mesh, features=grown
    )

    lines = new_feature_lines(before, after)

    assert len(lines) == 1
    assert "Neues Merkmal" in lines[0]
    assert "hole_99" in lines[0] and "Ø 6" in lines[0] and "auf obj_1" in lines[0]
    assert new_feature_lines(before, before) == []


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
    """§14: Verletzungen erscheinen im Prüfbericht, nie still."""
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
    """AGENTS.md Regel 7: die Zahl lebt im Profil, nicht in der Datei."""
    tpu = profiles.make_profile("centauri-carbon-2", "tpu-95a")
    scene = pin_and_hole(5.0 + profiles.material("petg").clearance, 5.0, profile)
    scene.fits.append(clearance_fit())

    assert fit_check.check(scene, profile) == []
    scene.profile = tpu
    assert fit_check.check(scene, tpu), "the same geometry is wrong for a softer material"


def two_faces(offset: float, normal_b: tuple[float, float, float], profile: Profile) -> Scene:
    """Zwei Flächen, die in einer Ebene sitzen sollen, und eine versetzte."""
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
    """§14: ``flush`` wurde angenommen und nie geprüft — eine Passungsart als
    Bühnenrequisite.
    """
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
    """Zwei Ebenen, die sich an einer Ecke treffen, haben keinen Abstand, der
    sich zu melden lohnt.
    """
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


# --- Eine Szene ist nicht ein Material (§12) ------------------------------------


def test_a_softer_body_gets_its_own_clearance(profile: Profile) -> None:
    """Der Fall, den der Modellordner zeigte: eine TPU-Dichtung im
    PETG-Gehäuse.

    Mit dem Projektmaterial gerechnet ist der Spalt 0,25 — die Zahl für PETG.
    Die Dichtung ist TPU und will 0,35, und der Unterschied ist nicht
    akademisch: bei 0,25 ist der Zusammenbau eine Presspassung, nach der
    niemand gefragt hat.
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
    """Rauschen in einem Bericht ist das, was den Bericht ungelesen lässt."""
    scene = pin_and_hole(5.0, 5.0, profile)
    scene.fits.append(clearance_fit())

    findings = fit_check.check(scene, profile)

    assert findings and "materials" not in findings[0].values


def test_a_named_material_stays_what_it_says(profile: Profile) -> None:
    """``auto:petg`` wurde mit Absicht hingeschrieben, und kein Körper
    überstimmt es (§12).
    """
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
    """Negative Werte: der größere ist das kleinere Übermaß.

    PETG presst mit -0,05 und TPU mit -0,10. Einen TPU-Stift mit der TPU-Zahl
    in ein PETG-Loch zu pressen heißt 0,1 mm Übermaß in einem Körper, der nicht
    nachgibt — das Gehäuse reißt. -0,05 hält und übersteht es.
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


def test_the_digest_says_where_a_feature_is(profile: Profile) -> None:
    """§26.1: der Agent sieht nur diesen Text.

    Durchmesser und Achse ohne Position sind eine Beschreibung, auf die niemand
    handeln kann: „setz einen Baustein an hole_1" geht über den Namen, „bohr
    daneben" nicht. Die Oberfläche kennt die Position, seit ein Merkmal
    anklickbar ist (§18.5).
    """
    text = digest(plate_scene(profile))

    assert "bei (" in text
    assert "-25, -15" in text or "-25, 15" in text, "the bores of plate_holes sit at ±25/±15"


def test_a_zero_in_the_digest_reads_as_zero() -> None:
    """Ein zentrierter Körper landet rechnerisch auf -1.11022e-16, nicht auf 0.

    Der Agent liest den Steckbrief als Text. Steht dort eine Zehn-hoch-minus-
    sechzehn, nimmt er sie für einen Wert, der etwas bedeutet — er hat keine
    andere Quelle als diesen Satz.
    """
    from app.core.perceive.digest import _place

    assert _place((-1.11022e-16, 4.14329e-17, 10.0)) == ", bei (0, 0, 10)"
    # Was oberhalb des Rauschens liegt, bleibt unangetastet.
    assert _place((0.5, -15.0, 10.0)) == ", bei (0.5, -15, 10)"
