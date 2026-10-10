"""Der Abdruck einer Buchung hängt an dem, was das Projekt gespeichert hat (RM-706).

Bis RM-706 ging die Geometrie als Prüfsumme der **ausgewerteten** Netze in den
Abdruck. Druckgleich (Bauplan §11.2) erlaubt aber, dass eine Beschleunigung
Punkte innerhalb der Druckgrenze verschiebt, die Dreiecke umsortiert oder ein
Netz in float32 hält (RM-698) — jeder solche Schritt hätte jeden gebuchten
Druck zu einem neuen gemacht. Seither benennen die gespeicherten Eingänge den
Körper: Quellen mit ihrer Inhaltsprüfsumme, die Schritte mit ihren Werten,
die Fassung der Bausteine, die gelesenen Projektmaße. Die Einstellungen gehen
über das ein, was dem Projekt gehört (eigene Wahl, Vorschläge, Stufe, Spulen),
nicht über die Grundlage des Herstellers (Review RM-705, N3).

Der Abdruck von davor bleibt als **Vorabdruck** (``former_fingerprints``): Er
belegt dieselbe Gleichheit wie bisher, damit Buchungen aus 0.5.2 bis 0.6.0
wiedererkannt werden, solange ihre Netzbits gleich sind.
"""

from __future__ import annotations

import dataclasses
import shutil
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core import filament_usage as usage
from app.core.export import handover, manufacturer
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge import filaments, print_settings, profiles
from app.core.knowledge.parts import PARTS
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, load, new_project, save
from app.core.types import (
    MaterialSlot,
    Operation,
    Parameter,
    PrintSettings,
    Profile,
    SceneObject,
    SlotOverride,
)
from app.core.units import PRINT_LIMIT
from app.ui import filament_usage as ui
from tests.helpers import plate_project

DATA = Path(__file__).parent / "data"

#: Der Abdruck des Würfels aus ``usage_booking_v46.p3d`` nach RM-706, auf dem
#: Weg der Anwendung (Herstellergrundlage ohne Slicer). **Kein Sollwert von
#: außen** — es gibt keinen älteren Stand, der so rechnete. Die Zahl hält die
#: Bildung fest: Ändert sie sich, findet Solidon keine Buchung mehr, die nach
#: diesem Stand gebucht wurde. Wer sie ändern muss, führt den alten Abdruck als
#: Vorabdruck mit (``verbrauch.md``).
PINNED_BOOKING = "9759ad3f42418e8d5bd48bb8bfa854cd"
#: Die Buchung im Lager von 0.5.3 (``test_filament_usage_fingerprint_history``).
BOOKED_053 = "aa373e5e86b4471cf557a31589dc8383"


def build(
    *,
    width: float = 20.0,
    parameter: float | None = None,
    extra: tuple[OperationDraft, ...] = (),
) -> Any:
    """Ein gespeichertes Projekt mit einem Quader, ausgewertet wie in der Anwendung."""
    project = new_project("centauri-carbon-2", "pla")
    params: dict[str, Any] = {"width": width, "depth": 20.0, "height": 20.0}
    if parameter is not None:
        project.document.parameters["breite"] = Parameter("breite", parameter)
        params["width"] = "=@breite"
    History(project.document).apply(
        "Quader", [OperationDraft(op="create_box", params=params), *extra]
    )
    return project


def job(project: Any) -> tuple[list[SceneObject], PrintSettings, Profile, usage.StoredInputs]:
    profile = profiles.make_profile(project.document.printer, project.document.material)
    settings = replace(print_settings.resolve(profile), inventory_project_id="rm706-probe")
    sources = ProjectSources(project)
    result = evaluate(project.document, profile, sources=sources)
    assert result.stopped_at is None, result.scene.report.findings
    inputs = usage.StoredInputs(project.document, sources, result.stopped_at)
    return list(result.scene.objects.values()), settings, profile, inputs


def request_for(
    objects: list[SceneObject],
    settings: PrintSettings,
    profile: Profile,
    inputs: usage.StoredInputs,
) -> usage.UsageRequest:
    return usage.prepare(objects, settings, profile, "Probe", inputs=inputs)[0]


def _reordered(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Dieselben Dreiecke in anderer Folge, die Punkte neu nummeriert."""
    vertex_order = np.arange(len(mesh.vertices))[::-1]
    renumber = np.empty_like(vertex_order)
    renumber[vertex_order] = np.arange(len(vertex_order))
    faces = renumber[np.asarray(mesh.faces)][::-1]
    # Jedes Dreieck beginnt an einer anderen Ecke, die Umlaufrichtung bleibt.
    faces = np.roll(faces, 1, axis=1)
    return trimesh.Trimesh(np.asarray(mesh.vertices)[vertex_order], faces, process=False)


def _shifted(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Jeder Punkt um weniger als die Druckgrenze verschoben, fest und ohne Zufall."""
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    pattern = np.sin(np.arange(vertices.size, dtype=np.float64)).reshape(vertices.shape)
    return trimesh.Trimesh(vertices + pattern * PRINT_LIMIT / 4, mesh.faces, process=False)


def _rounded_to_float32(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Die Punkte so, wie RM-698 ein Netz hält: float32, für die Rechnung zurück."""
    vertices = np.asarray(mesh.vertices, dtype=np.float64) + 1e-7
    held = vertices.astype(np.float32).astype(np.float64)
    return trimesh.Trimesh(held, mesh.faces, process=False)


def _everything(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    return _rounded_to_float32(_shifted(_reordered(mesh)))


PRINT_EQUAL = {
    "reordered": _reordered,
    "shifted": _shifted,
    "float32": _rounded_to_float32,
    "everything": _everything,
}


def _changed(objects: list[SceneObject], change: Any) -> list[SceneObject]:
    return [
        dataclasses.replace(body, mesh=MeshData.of(change(as_mesh_data(body.mesh).raw)))
        for body in objects
    ]


@pytest.mark.parametrize("name", sorted(PRINT_EQUAL))
def test_a_print_equal_result_keeps_the_fingerprint(name: str) -> None:
    """Der Wächter: Eine druckgleiche Änderung am Ergebnis läuft am Abdruck vorbei.

    Die Gegenprobe steckt mit drin: Der Vorabdruck über die Netzbits ändert
    sich — die Änderung ist also wirklich bei den Netzen angekommen.
    """
    objects, settings, profile, inputs = job(build())
    before = request_for(objects, settings, profile, inputs)
    changed = _changed(objects, PRINT_EQUAL[name])
    after = request_for(changed, settings, profile, inputs)
    assert after.fingerprint == before.fingerprint
    assert after.former_fingerprints != before.former_fingerprints


def test_a_print_equal_result_of_a_loaded_mesh_keeps_the_fingerprint() -> None:
    """Dasselbe an einer eingelesenen Quelle, wie Weg 1 sie anlegt."""
    objects, settings, profile, inputs = job(plate_project())
    before = request_for(objects, settings, profile, inputs)
    after = request_for(_changed(objects, _everything), settings, profile, inputs)
    assert after.fingerprint == before.fingerprint


@pytest.mark.parametrize(
    "variant",
    ["width", "parameter", "another_step", "seed_free_twin_step"],
)
def test_a_changed_input_changes_the_fingerprint(variant: str) -> None:
    """Gegenprobe: Was der Kunde am Projekt ändert, macht einen anderen Druck."""
    objects, settings, profile, inputs = job(build(parameter=20.0))
    reference = request_for(objects, settings, profile, inputs).fingerprint
    if variant == "width":
        project = build(width=21.0)
    elif variant == "parameter":
        project = build(parameter=21.0)
    elif variant == "another_step":
        project = build(
            parameter=20.0,
            extra=(OperationDraft(op="translate_object", params={"dz": 1.0}, inputs=("obj_1",)),),
        )
    else:
        # Dieselbe Geometrie auf anderem Weg ist ein anderer Satz Eingänge.
        project = build(width=20.0)
    changed = request_for(*job(project))
    assert changed.fingerprint != reference


def test_another_source_mesh_changes_the_fingerprint() -> None:
    first = plate_project()
    objects, settings, profile, inputs = job(first)
    reference = request_for(objects, settings, profile, inputs).fingerprint
    second = plate_project()
    box = trimesh.creation.box(extents=(30.0, 20.0, 4.0))
    second.sources["src_1"] = box.export(file_type="stl")
    assert request_for(*job(second)).fingerprint != reference


def test_the_fingerprint_is_the_same_before_and_after_saving(tmp_path: Path) -> None:
    """Ein ungespeichertes Projekt trägt noch keine Prüfsumme der Quelle; der
    Abdruck rechnet sie aus dem Inhalt — gespeichert und geöffnet ist er gleich."""
    project = plate_project()
    assert not project.document.sources["src_1"].sha256
    objects, settings, profile, inputs = job(project)
    before = request_for(objects, settings, profile, inputs).fingerprint
    target = tmp_path / "platte.p3d"
    save(project, target)
    opened = load(target)
    assert opened.document.sources["src_1"].sha256
    objects, _settings, profile, inputs = job(opened)
    assert request_for(objects, settings, profile, inputs).fingerprint == before


def test_a_part_with_a_new_version_changes_the_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine Maßänderung eines Bausteins (``PartChange``) ist ein anderer Druck;
    eine neue Fassung nur des Cache-Schlüssels nicht."""
    project = build(
        extra=(OperationDraft(op="insert_screw_hole", params={}, inputs=("obj_1",)),),
    )
    stored = usage.StoredInputs(project.document)
    reference = stored.bodies()
    assert set(reference) == {"obj_1"}
    spec = PARTS.get("screw_hole")
    monkeypatch.setitem(PARTS._parts, "screw_hole", replace(spec, version=spec.version + "0"))
    assert stored.bodies() != reference


def test_a_new_implementation_keeps_the_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine neue Fassung der Umsetzung (``cache_version``) ist kein anderer Druck —
    sie steigt genau bei einer druckgleichen Beschleunigung."""
    from app.core.registry import REGISTRY

    stored = usage.StoredInputs(build().document)
    reference = stored.bodies()
    spec = REGISTRY.get("create_box")
    monkeypatch.setitem(REGISTRY._ops, "create_box", replace(spec, cache_version="neu"))
    assert stored.bodies() == reference


def test_a_step_that_reads_another_body_follows_it() -> None:
    """Liest ein Schritt neben seinen Eingängen (``reads_other_bodies``), ändert ein
    anderer Körper davor seinen Abdruck; ohne solche Lesart bleibt er."""

    def two_boxes(first_width: float, *, moved: bool) -> dict[str, str]:
        project = new_project("centauri-carbon-2", "pla")
        steps = [
            OperationDraft(op="create_box", params={"width": first_width}),
            OperationDraft(op="create_box", params={"width": 30.0}),
        ]
        if moved:
            steps.append(
                OperationDraft(op="translate_object", params={"dx": 5.0}, inputs=("obj_2",))
            )
        History(project.document).apply("Zwei", steps)
        return usage.StoredInputs(project.document).bodies()

    assert two_boxes(20.0, moved=True)["obj_2"] != two_boxes(21.0, moved=True)["obj_2"]
    assert two_boxes(20.0, moved=False)["obj_2"] == two_boxes(21.0, moved=False)["obj_2"]


def test_a_step_that_only_names_or_checks_keeps_the_body() -> None:
    plain = usage.StoredInputs(build().document).bodies()
    renamed = build(
        extra=(OperationDraft(op="rename_object", params={"name": "Anders"}, inputs=("obj_1",)),)
    )
    assert usage.StoredInputs(renamed.document).bodies() == plain


def test_a_step_that_passes_its_input_through_keeps_the_body() -> None:
    """*Duplizieren* reicht das Original unverändert durch (``leaves_inputs_unchanged``):
    Es bleibt derselbe Körper, nur die Kopie ist neu."""
    plain = usage.StoredInputs(build().document).bodies()
    duplicated = usage.StoredInputs(
        build(
            extra=(OperationDraft(op="duplicate_object", params={"count": 2}, inputs=("obj_1",)),),
        ).document
    ).bodies()
    assert len(duplicated) == 2
    assert duplicated["obj_1"] == plain["obj_1"]
    (copy,) = set(duplicated) - {"obj_1"}
    assert duplicated[copy] != plain["obj_1"]


def test_a_suppressed_step_and_a_halt_count_like_the_evaluation() -> None:
    """Ein ausgeschalteter Schritt rechnet nicht, nach dem Halt rechnet nichts."""
    project = build(
        extra=(OperationDraft(op="translate_object", params={"dz": 1.0}, inputs=("obj_1",)),),
    )
    moved = usage.StoredInputs(project.document).bodies()
    plain = usage.StoredInputs(build().document).bodies()
    assert moved != plain
    last = project.document.ops[-1]
    stopped = usage.StoredInputs(project.document, stopped_at=last.id).bodies()
    assert stopped == plain
    from app.core.types import Suppression

    project.document.ops[-1] = replace(last, suppressed=Suppression())
    assert usage.StoredInputs(project.document).bodies() == plain


def test_the_settings_count_by_what_the_project_owns() -> None:
    """N3: Eine andere Grundlage ändert nichts, eine eigene Wahl und eine Spule schon."""
    objects, settings, profile, inputs = job(build())
    reference = request_for(objects, settings, profile, inputs).fingerprint
    # Eine neue Grundlage: Slicer-Update oder Solidons eigene (Cura, RM-583).
    for path in ("support.z_gap", "speed.outer_wall", "cooling.minimum_speed"):
        value = print_settings.read_path(settings, path)
        other = print_settings.with_path(settings, path, value * 2 + 1)
        assert request_for(objects, other, profile, inputs).fingerprint == reference, path
    chosen = print_settings.with_choice(settings, "infill.density", 0.42)
    accepted = print_settings.with_accepted(settings, "infill.density", 0.42)
    assert request_for(objects, chosen, profile, inputs).fingerprint != reference
    # Woher ein Wert kommt, ändert den Druck nicht (H10).
    assert (
        request_for(objects, chosen, profile, inputs).fingerprint
        == request_for(objects, accepted, profile, inputs).fingerprint
    )
    quality = replace(settings, quality="fine")
    assert request_for(objects, quality, profile, inputs).fingerprint != reference
    slot = request_for(objects, settings, profile, inputs).lines[0].slot
    spool = SlotOverride(
        name=slot.name,
        colour=slot.colour,
        material=slot.material,
        material_type=slot.material_type,
        temperature=replace(settings.temperature, nozzle=215),
    )
    spooled = handover.with_slot_override(settings, slot, spool)
    assert request_for(objects, spooled, profile, inputs).fingerprint != reference
    # Eine Spulenbindung ist kein anderer Druck.
    bound = usage.with_spool(settings, slot, "spule-1")
    assert request_for(objects, bound, profile, inputs).fingerprint == reference


def test_the_former_fingerprint_is_the_one_of_rm705() -> None:
    """Ohne Eingänge rechnet ``prepare`` wie bisher; mit ihnen ist das der Vorabdruck."""
    objects, settings, profile, inputs = job(build())
    plain = usage.prepare(objects, settings, profile, "Probe")[0]
    request = request_for(objects, settings, profile, inputs)
    assert request.former_fingerprints == (plain.fingerprint,)
    assert request.legacy_fingerprints == plain.legacy_fingerprints
    assert request.fingerprint != plain.fingerprint


def _booking_053(tmp_path: Path) -> tuple[Any, usage.UsageRequest]:
    target = filaments.catalogue_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DATA / "usage_booking_v46_inventory.json", target)
    project_file = tmp_path / "wuerfel.p3d"
    shutil.copyfile(DATA / "projects/usage_booking_v46.p3d", project_file)
    project = load(project_file)
    profile = profiles.make_profile(project.document.printer, project.document.material)
    stored = project.document.print_settings
    assert stored is not None
    # Der Weg der Anwendung (``MainWindow.effective_print_settings``), ohne Slicer.
    settings = manufacturer.effective(
        stored, manufacturer.base_settings(profile, stored.quality, None)
    )
    sources = ProjectSources(project)
    result = evaluate(project.document, profile, sources=sources)
    request = usage.prepare(
        list(result.scene.objects.values()),
        settings,
        profile,
        "Würfel",
        inputs=usage.StoredInputs(project.document, sources, result.stopped_at),
    )[0]
    return project, request


def test_a_booking_written_by_053_is_found_with_the_stored_inputs(tmp_path: Path) -> None:
    """Der Kundenweg: Die Buchung aus 0.5.3 ist derselbe Druck, nicht nur ein Kandidat."""
    _project, request = _booking_053(tmp_path)
    assert request.fingerprint == PINNED_BOOKING
    assert BOOKED_053 in request.former_fingerprints
    snapshot = filaments.read_snapshot()
    assert [one.operation_id for one in ui._previous(request, snapshot)] == ["rm705-druck"]
    assert ui._legacy_bookings(request, snapshot) == ()


def test_an_old_booking_is_kept_under_its_own_fingerprint(tmp_path: Path) -> None:
    """Ein Nachbuchen am Vorgang aus 0.5.3 schreibt mit dessen Abdruck, ohne Konflikt."""
    _project, request = _booking_053(tmp_path)
    previous = ui._previous(request, filaments.read_snapshot())[0]
    again = filaments.book(
        previous.operation_id,
        ui._booking_fingerprint(request, previous),
        previous.positions,
        project_name=request.project_name,
    )
    assert again == previous


def test_the_stored_inputs_read_no_mesh() -> None:
    """Die Eingänge kommen aus dem Dokument; ein Schritt, den es hier nicht gibt,
    hält wie die Auswertung an."""
    project = build()
    project.document.ops.append(
        Operation(id=99, op="does_not_exist", inputs=("obj_1",), outputs=("obj_1",))
    )
    assert (
        usage.StoredInputs(project.document).bodies()
        == usage.StoredInputs(build().document).bodies()
    )


@pytest.fixture
def stock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    entry = filaments.save(
        filaments.CatalogueFilament("PLA", "#ffffff", "PLA", remaining_grams=500)
    )
    slot = MaterialSlot(0, "PLA", (1.0, 1.0, 1.0), material_type="PLA")
    line = usage.UsageLine(slot, 42.0, entry.identifier)
    request = usage.UsageRequest("new", "Part", 0, (line,), former_fingerprints=("former",))
    position = filaments.BookingPosition(
        entry.identifier, 42.0, "internal", ui._note(line), filament_key=ui._line_key(line)
    )
    return entry, request, position


def test_automatic_booking_keeps_a_booking_under_the_former_fingerprint(stock: Any) -> None:
    """*Ohne Rückfrage buchen*: Der Vorgang aus 0.6.0 ist derselbe Druck — kein
    zweiter Abzug, eine Korrektur aus dem G-Code bleibt an ihm, ohne Konflikt."""
    entry, request, position = stock
    old = filaments.book("booked-in-060", "former", [position])
    assert ui._auto_book(request) == old
    assert filaments.get(entry.identifier).remaining_grams == 458
    corrected = replace(request, lines=(replace(request.lines[0], grams=47.0, source="gcode"),))
    result = ui._auto_book(corrected)
    assert (result.operation_id, result.fingerprint) == ("booked-in-060", "former")
    assert filaments.get(entry.identifier).remaining_grams == 453
    # Nach der Rücknahme ist ein weiterer Druck ein neuer Vorgang mit neuem Abdruck.
    filaments.reverse_booking(old.operation_id)
    again = ui._auto_book(request)
    assert again.fingerprint == "new"
    assert again.operation_id != old.operation_id


def test_the_notice_marks_the_offer_booked_under_its_own_name(stock: Any) -> None:
    _entry, _request, position = stock
    old = filaments.book("booked-in-060", "former", [position])
    host = SimpleNamespace(
        _active="new",
        _booked=set(),
        _declined=set(),
        changed=SimpleNamespace(emit=lambda: None),
        _sync_review=lambda: None,
        _start_pending=lambda: None,
    )
    ui.UsageNotice._completed(host, old)
    assert host._booked == {"new"}


def test_a_source_path_reads_the_same_on_every_platform() -> None:
    """Ein Pfad mit Rückstrich (alte Windows-Datei) nennt dieselbe Quelle wie mit
    Schrägstrich — der Abdruck hängt an keiner Plattform."""
    forward = plate_project()
    backward = plate_project()
    source = backward.document.sources["src_1"]
    backward.document.sources["src_1"] = replace(source, path=source.path.replace("/", "\\"))
    assert usage.StoredInputs(backward.document, ProjectSources(backward)).bodies() == (
        usage.StoredInputs(forward.document, ProjectSources(forward)).bodies()
    )
