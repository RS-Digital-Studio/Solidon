"""Der mitgelieferte Startbestand ist vollständig und benutzbar (Bauplan
§38, §28.3).
"""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.core.knowledge import profiles
from app.core.types import MaterialSlot, Profile, SceneObject


def test_starting_set_is_present() -> None:
    printers = profiles.printer_profiles()
    assert profiles.DEFAULT_PRINTER in printers
    assert "centauri-carbon-2" in printers
    assert len(printers) >= 10, "nobody should have to type build volumes on first start"


def test_every_printer_has_a_plausible_build_volume() -> None:
    for identifier, printer in profiles.printer_profiles().items():
        width, depth, height = printer.build_volume
        assert min(width, depth, height) > 50.0, identifier
        assert max(width, depth, height) < 1000.0, identifier
        assert printer.nozzle_diameter > 0.0, identifier
        assert printer.extrusion_width >= printer.nozzle_diameter, identifier


def test_every_material_is_marked_uncalibrated() -> None:
    materials = profiles.material_profiles()
    assert profiles.DEFAULT_MATERIAL in materials
    for identifier, material in materials.items():
        assert not material.calibrated, f"{identifier} ships as a starting point, not a measurement"
        assert material.clearance > 0.0, identifier
        assert material.hole_compensation > 0.0, identifier


@pytest.mark.parametrize(
    ("material_type", "identifier"),
    (("PLA", "pla"), ("petg", "petg"), ("TPU", "tpu-95a"), ("PCTG", ""), ("", "")),
)
def test_a_slicer_material_type_has_one_unambiguous_profile(
    material_type: str, identifier: str
) -> None:
    """Bekannte Schreibweisen werden aufgelöst; unbekannte nie geraten."""
    assert profiles.material_id_for_type(material_type) == identifier


def test_minimum_wall_thickness_follows_the_rule_set() -> None:
    profile = profiles.make_profile()
    assert profile.minimum_wall_thickness == pytest.approx(2 * profile.printer.extrusion_width)


def test_tolerance_reference_resolves_against_the_material() -> None:
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    petg = profiles.material("petg")
    assert profiles.resolve_tolerance("auto:", "clearance", profile) == pytest.approx(
        petg.clearance
    )
    assert profiles.resolve_tolerance("auto:petg", "clearance", profile) == pytest.approx(
        petg.clearance
    )
    assert profiles.resolve_tolerance("auto:tpu-95a", "clearance", profile) == pytest.approx(
        profiles.material("tpu-95a").clearance
    )
    assert profiles.resolve_tolerance(0.3, "clearance", profile) == pytest.approx(0.3)
    assert profiles.resolve_tolerance("auto:", "flush", profile) == pytest.approx(0.0)


def test_unknown_profile_is_a_user_error_with_a_suggestion() -> None:
    with pytest.raises(ValidationError) as caught:
        profiles.printer("does-not-exist")
    assert caught.value.suggestions

    with pytest.raises(ValidationError):
        profiles.material("does-not-exist")


def test_plain_string_is_not_a_tolerance() -> None:
    with pytest.raises(ValidationError):
        profiles.resolve_tolerance("0.2mm", "clearance", profiles.make_profile())


def test_make_profile_pairs_printer_and_material() -> None:
    profile = profiles.make_profile("bambu-p1s", "asa")
    assert isinstance(profile, Profile)
    assert profile.printer.enclosed, "ASA wants a closed chamber; the profile has to say so"


# --- Das Material kommt aus der Spule (D14b) ----------------------------------------


def _body(**kwargs: object) -> SceneObject:
    """Ein Körper, wie ihn die Auswertung baut.

    Das Netz ist der Platzhalter aus ``conftest``: Welches Material gilt,
    entscheidet sich an den Spulen und am Feld daneben, nie an der Geometrie —
    ein echtes Netz kostete hier nur Ladezeit.
    """
    from tests.conftest import FakeMesh

    return SceneObject(id="obj_1", name="Teil", mesh=FakeMesh(), **kwargs)  # type: ignore[arg-type]


def test_a_body_is_printed_in_the_material_of_its_spool() -> None:
    """„das material kommt ja auch aus dem filament" (Robert, 30.08.2026).

    Ein Körper, dessen Spule PLA trägt, wird in PLA gerechnet — auch wenn das
    Projekt auf PETG steht. Die Zahl dahinter ist das Spiel: 0,20 mm gegen
    0,25 mm, gemessen. Wer die Spule wechselt und weiter mit dem alten Spiel
    bohrt, bekommt eine Passung, die nicht passt.
    """
    project = profiles.make_profile("generic-220", "petg")
    spool = MaterialSlot(index=0, name="Gehäuse", material_type="PLA")

    chosen = profiles.for_object(project, _body(material_slots=[spool]))

    assert chosen.material.id == "pla", "die Spule bestimmt, nicht das Projekt"
    assert chosen.printer is project.printer, "der Drucker bleibt der des Projekts"


def test_the_first_spool_decides_and_not_the_decoration() -> None:
    """Slot 0 ist der Körper selbst, jeder weitere ist Bemalung (§20).

    Ein Gehäuse in PETG mit einem Schriftzug in PLA bohrt ins Gehäuse. Die
    Fläche des Schriftzugs zu messen wäre teurer und im Randfall falsch: Ein
    zu 60 % bemaltes Teil hat seine Passung trotzdem im Grundmaterial.
    """
    project = profiles.make_profile("generic-220", "asa")
    body = _body(
        material_slots=[
            MaterialSlot(index=0, name="Gehäuse", material_type="PETG"),
            MaterialSlot(index=1, name="Schrift", material_type="PLA"),
        ]
    )

    assert profiles.for_object(project, body).material.id == "petg"


def test_slot_zero_decides_wherever_it_stands_in_the_list() -> None:
    """Gesucht ist die **Nummer**, nicht der erste Eintrag der Liste.

    Die Reihenfolge in ``material_slots`` ist keine Zusage — Slots kommen beim
    Bemalen dazu, und eine Operation darf sie umsortieren. Wer den ersten
    Eintrag nimmt, hat in der üblichen Reihenfolge zufällig recht und in der
    umgekehrten still unrecht; die Zusage lautet „Slot 0 ist der Körper" (§20).
    """
    project = profiles.make_profile("generic-220", "asa")
    body = _body(
        material_slots=[
            MaterialSlot(index=1, name="Schrift", material_type="PLA"),
            MaterialSlot(index=0, name="Gehäuse", material_type="PETG"),
        ]
    )

    assert profiles.for_object(project, body).material.id == "petg"


def test_an_own_material_still_beats_the_spool() -> None:
    """Was ausdrücklich am Körper steht, ist eine Entscheidung — die Spule ist
    eine Herleitung, und eine Herleitung überstimmt keine Entscheidung."""
    project = profiles.make_profile("generic-220", "petg")
    body = _body(
        material="tpu-95a",
        material_slots=[MaterialSlot(index=0, name="Gehäuse", material_type="PLA")],
    )

    assert profiles.for_object(project, body).material.id == "tpu-95a"


def test_a_spool_without_a_known_type_keeps_the_project_material() -> None:
    """Regel 21: nicht raten. Eine Spule „Holzoptik" nennt kein Material, das
    Solidon kennt — dann gilt weiter, was das Projekt sagt, und nicht das
    nächstbeste Profil.

    Denselben Weg geht der häufigste Fall überhaupt: Eine frisch eingelesene
    STL hat **null** Spulen (gemessen). Der Rückfall ist hier nicht der
    Sonderfall, sondern der Normalweg.
    """
    project = profiles.make_profile("generic-220", "petg")

    unknown = _body(material_slots=[MaterialSlot(index=0, name="Holzoptik", material_type="Wood")])
    empty = _body(material_slots=[MaterialSlot(index=0, name="Grau")])
    none_at_all = _body()

    for body in (unknown, empty, none_at_all):
        assert profiles.for_object(project, body).material.id == "petg"
