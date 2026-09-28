"""Der mitgelieferte Startbestand ist vollständig und benutzbar (Bauplan
§38, §28.3).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.core.errors import FileWriteError, ValidationError
from app.core.knowledge import profiles
from app.core.types import MaterialSlot, Profile, SceneObject


def test_saving_a_custom_printer_preserves_existing_profiles_and_exact_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eigene Profile bleiben nach dem Schreiben und einem erneuten Laden vollständig."""
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    template = profiles.printer(profiles.DEFAULT_PRINTER)
    first = replace(
        template, id="user-first", title='Drucker "groß"', build_volume=(300.125, 270, 410)
    )
    second = replace(template, id="user-second", title="Werkstatt")
    profiles.save_printer(first)
    profiles.save_printer(second)
    profiles.reload()
    assert profiles.printer(first.id) == first
    assert profiles.printer(second.id) == second
    assert profiles.printer(profiles.DEFAULT_PRINTER) == template
    assert set(profiles.user_printer_profiles()) == {first.id, second.id}


@pytest.mark.parametrize("value", (0, -1, float("nan"), float("inf")))
def test_custom_printer_rejects_invalid_dimensions_without_writing(
    value: float, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein ungültiger Bauraum verändert auch eine vorhandene Profildatei nicht."""
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    entry = replace(profiles.printer(profiles.DEFAULT_PRINTER), id="user-own", title="Eigen")
    profiles.save_printer(entry)
    before = (tmp_path / "printers.toml").read_bytes()
    with pytest.raises(ValidationError):
        profiles.save_printer(replace(entry, build_volume=(value, 200, 300)))
    assert (tmp_path / "printers.toml").read_bytes() == before


def test_a_failed_printer_save_preserves_the_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die fertige temporäre Datei ersetzt den Bestand erst nach erfolgreichem Schreiben."""
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    entry = replace(profiles.printer(profiles.DEFAULT_PRINTER), id="user-own", title="Eigen")
    profiles.save_printer(entry)
    before = (tmp_path / "printers.toml").read_bytes()

    def denied(_path: Path, _target: Path) -> None:
        raise PermissionError("occupied")

    monkeypatch.setattr(Path, "replace", denied)
    with pytest.raises(FileWriteError):
        profiles.save_printer(replace(entry, title="Geändert"))
    assert (tmp_path / "printers.toml").read_bytes() == before
    assert not tuple(tmp_path.glob("*.tmp"))


def test_starting_set_is_present() -> None:
    printers = profiles.printer_profiles()
    assert profiles.DEFAULT_PRINTER in printers
    assert "centauri-carbon-2" in printers
    assert len(printers) >= 10, "nobody should have to type build volumes on first start"


def test_every_printer_has_a_plausible_build_volume() -> None:
    """Jeder Drucker trägt einen Bauraum und die Maße seines Verfahrens.

    FDM: Düse und Bahn. Resin: Pixel und Mindestwand, und Düse wie Bahn auf
    null — dieses Verfahren hat keine (RM-071).
    """
    for identifier, printer in profiles.printer_profiles().items():
        width, depth, height = printer.build_volume
        assert min(width, depth, height) > 50.0, identifier
        assert max(width, depth, height) < 1000.0, identifier
        if printer.is_resin:
            assert printer.nozzle_diameter == 0.0, identifier
            assert printer.extrusion_width == 0.0, identifier
            assert 0.0 < printer.pixel_size <= 0.1, identifier
            assert 0.0 < printer.minimum_wall <= 1.0, identifier
            assert 0.0 < printer.layer_height <= 0.1, identifier
            continue
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
    from tests.helpers import FakeMesh

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


# --- Eigene Drucker reisen mit dem Projekt (Durchsicht 0.5.0) ------------------


@pytest.fixture
def two_computers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Zwei Rechner: je ein eigener Profilordner, dazwischen eine Projektdatei.

    Ein Rechnerwechsel ist hier ein anderer Profilordner und ein frisch
    geladener Bestand — genau das, was ein zweiter Rechner beim Öffnen hat.
    """
    folders = {"erster": tmp_path / "erster", "zweiter": tmp_path / "zweiter"}

    def switch(name: str) -> Path:
        monkeypatch.setattr(profiles, "user_profiles_dir", lambda: folders[name])
        profiles.carry(None)
        profiles.reload()
        return folders[name]

    yield switch
    profiles.carry(None)
    profiles.reload()


def _own_printer() -> object:
    template = profiles.printer(profiles.DEFAULT_PRINTER)
    return replace(
        template,
        id="werkstatt-xl",
        title="Werkstatt XL",
        build_volume=(420.0, 380.0, 500.0),
        nozzle_diameter=0.6,
        layer_height=0.3,
    )


def _project_on(printer_id: str, path: Path) -> Path:
    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft
    from app.core.scene.project import new_project, save

    load_operations()
    project = new_project(printer_id, "petg")
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 30.0, "depth": 20.0, "height": 8.0})],
    )
    return save(project, path)


def test_an_own_printer_travels_with_the_project_to_another_computer(
    tmp_path: Path, two_computers
) -> None:
    """Auf dem zweiten Rechner hieß es nur „Dieses Druckerprofil ist nicht bekannt."

    Keine Szene, keine Druckeinstellungen (Fund aus dem Paket „dialoge",
    Durchsicht 0.5.0). Jetzt trägt die Projektdatei die Beschreibung des
    eigenen Druckers — Name, Bauraum, Düse, Verfahren, Schichthöhe, kein Pfad
    und kein Code —, der zweite Rechner rechnet damit, der Prüfbericht bietet
    an, ihn zu übernehmen, und ein Speichern dort verliert ihn nicht.
    """
    from app.core.errors import ADOPT_PRINTER, CHOOSE_PRINTER
    from app.core.knowledge import print_settings
    from app.core.scene import evaluate
    from app.core.scene.project import ProjectSources, load, project_data, save

    two_computers("erster")
    own = _own_printer()
    profiles.save_printer(own)
    path = _project_on(own.id, tmp_path / "werkstatt.p3d")
    carried = project_data(path)["carried_profiles"]["printers"]
    assert set(carried) == {own.id}
    assert "id" not in carried[own.id], "die Kennung steht einmal, als Schlüssel"

    two_computers("zweiter")
    with pytest.raises(ValidationError):
        profiles.printer(own.id)
    project = load(path)
    assert profiles.carry(project.document.carried_profiles) == (own.id,)

    profile = profiles.scene_profile(project.document.printer, project.document.material)
    assert profile.printer == own, "gerechnet wird mit der mitgebrachten Beschreibung"
    assert print_settings.resolve(profile).layers.layer_height == pytest.approx(0.3)
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    (said,) = profiles.carried_findings(project.document.printer, project.document.material)
    assert said.code == "profile.carried_printer"
    assert said.suggestions == (ADOPT_PRINTER, CHOOSE_PRINTER)

    again = save(project, tmp_path / "weitergegeben.p3d")
    assert set(project_data(again)["carried_profiles"]["printers"]) == {own.id}, (
        "ein Speichern auf dem zweiten Rechner verlor die Beschreibung"
    )

    assert profiles.adopt_carried() == (own.id,)
    profiles.reload()
    assert profiles.user_printer_profiles()[own.id] == own
    assert profiles.only_carried() == ()
    assert profiles.carried_findings(own.id, "petg") == ()


def test_a_project_whose_printer_is_nowhere_still_opens(two_computers) -> None:
    """Ohne Beschreibung rechnet das Projekt mit dem Standarddrucker — und sagt es."""
    from app.core.errors import CHOOSE_PRINTER

    two_computers("zweiter")

    profile = profiles.scene_profile("gibt-es-nicht", "petg")

    assert profile.printer.id == profiles.DEFAULT_PRINTER
    assert profile.material.id == "petg"
    (said,) = profiles.carried_findings("gibt-es-nicht", "petg")
    assert said.code == "profile.printer_missing" and said.severity == "warning"
    assert said.suggestions == (CHOOSE_PRINTER,)
    assert "{" not in str(said.message), "ein Befundsatz trägt keinen Platzhalter"


def test_a_carried_printer_is_read_like_an_own_file(two_computers) -> None:
    """Eine fremde Beschreibung geht durch denselben Prüfer — Unlesbares bleibt weg."""
    two_computers("zweiter")

    adoptable = profiles.carry(
        {
            "printers": {
                "kaputt": {"title": "Kaputt", "build_volume": ["breit", 1, 2]},
                "ohne-mass": {"title": "Ohne Maß"},
                "gut": {"title": "Gut", "build_volume": [200, 200, 200]},
            }
        }
    )

    assert adoptable == ("gut",)
    assert profiles.scene_profile("kaputt", "pla").printer.id == profiles.DEFAULT_PRINTER


def test_a_carried_printer_never_replaces_one_this_computer_has(two_computers) -> None:
    """Kennt der Rechner die Kennung selbst, gilt seine Beschreibung."""
    two_computers("zweiter")
    local = _own_printer()
    profiles.save_printer(local)

    adoptable = profiles.carry(
        {"printers": {local.id: {"title": "Fremd", "build_volume": [100, 100, 100]}}}
    )

    assert adoptable == ()
    assert profiles.printer(local.id) == local


def test_a_shipped_printer_is_never_carried(tmp_path: Path, two_computers) -> None:
    """Mitgelieferte Profile gibt es überall — die Datei bleibt, wie sie war."""
    from app.core.scene.project import project_data

    two_computers("erster")
    path = _project_on("centauri-carbon-2", tmp_path / "centauri.p3d")

    assert "carried_profiles" not in project_data(path)
