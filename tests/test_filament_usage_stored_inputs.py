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
PINNED_BOOKING = "3aa49b71e62d0e6815f5ab5c7182f4dd"
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


def test_a_recipe_names_the_versions_of_the_parts_it_sets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review RM-706, L3: Ein Rezept setzt Bibliotheksbausteine. Ändert einer davon
    seine Maße (``PartChange``), ändert sich der Druck, auch wenn das Rezept selbst
    — und mit ihm seine Fassung — gleich bleibt."""
    from app.core.knowledge.parts import recipe

    inner = Operation(id=1, op="insert_screw_hole", inputs=("obj_1",), outputs=("obj_1",))
    monkeypatch.setitem(
        PARTS._parts,
        "rm706_rezept",
        SimpleNamespace(
            name="rm706_rezept", version="rezept-1", recipe_data={"rezept": 1}, standalone=False
        ),
    )
    monkeypatch.setattr(
        recipe,
        "from_data",
        lambda data: SimpleNamespace(document=SimpleNamespace(ops=[inner])),
    )
    outer = Operation(id=2, op="insert_rm706_rezept", inputs=("obj_1",), outputs=("obj_1",))
    reference = usage._part_versions(outer)
    spec = PARTS.get("screw_hole")
    monkeypatch.setitem(PARTS._parts, "screw_hole", replace(spec, version=spec.version + "0"))
    assert usage._part_versions(outer) != reference


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


def test_every_reading_of_the_cache_key_reaches_the_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review RM-706, L2: ``_read_beside`` ist der Zwilling von
    ``evaluate._with_nested_context`` (``zwillinge.md``, gewollt).

    Für jede registrierte Operation und jede Lesart, die der Cache-Schlüssel
    neben den Eingängen nimmt, liest der Abdruck dasselbe: eine Quelle als
    Quelle, ein Projektmaß als Projektmaß, ein Merkmal, eine Skizzenebene und die
    Szene als alle lebenden Körper. Eine neue Lesart der Auswertung ohne
    Gegenstück hier macht ihn rot — sonst trügen zwei Drucke einen Abdruck.
    """
    from importlib import import_module

    from app.core.registry import REGISTRY
    from app.core.scene import orphans
    from app.core.types import FeatureRef

    # Das Modul, nicht die gleichnamige Funktion, die das Paket ausgibt.
    evaluation = import_module("app.core.scene.evaluate")
    project = build()
    profile = profiles.make_profile(project.document.printer, project.document.material)
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    objects = dict(result.scene.objects)
    hashes = dict(result.object_hashes)
    feature = min(objects["obj_1"].features)
    plate = plate_project()
    sources = ProjectSources(plate)
    stored = usage.StoredInputs(plate.document, sources)
    kinds = tuple(evaluation.nested_references())

    def reads(text: str) -> frozenset[str]:
        # Kein @ im Text: Das Projektmaß liest nur der Sammler der Art, nicht
        # die Suche nach Ausdrücken in den Werten.
        return frozenset({"probe"}) if text == "probe-text" else frozenset()

    monkeypatch.setattr(
        evaluation, "nested_references", lambda *, strict=False: dict.fromkeys(kinds, reads)
    )
    plane = FeatureRef("obj_1", feature)

    def standing(text: str) -> FeatureRef | None:
        return plane if text == "plane" else None

    monkeypatch.setattr(evaluation, "feature_ref_of_sketch", standing)
    monkeypatch.setattr(orphans, "feature_ref_of_sketch", standing)

    def probes(entry: Any) -> list[object]:
        if entry.kind in evaluation.SOURCE_KINDS:
            return ["src_1"]
        if entry.kind == "features":
            return [[feature]]
        if entry.kind == "feature" or entry.targets_feature:
            return [feature]
        if entry.kind == "sketch":
            return ["plane", "probe-text"]
        if entry.kind in kinds:
            return ["probe-text"]
        if entry.reads_scene:
            return [True]
        return []

    missed: list[str] = []
    readings = 0
    for spec in REGISTRY.all():
        entries = {entry.name: entry for entry in spec.params.spec()}
        cases: list[dict[str, Any]] = [{}]
        cases += [{name: value} for name, entry in entries.items() for value in probes(entry)]
        for resolved in cases:
            theirs = evaluation._with_nested_context(
                spec.params,
                resolved,
                {"probe": 1.0},
                sources,
                objects,
                hashes,
                reads_other_bodies=spec.reads_other_bodies,
            )
            mine = usage._read_beside(
                spec, Operation(id=1, op=spec.name, params=resolved), {"obj_1": "x"}, stored
            )
            for key in sorted(set(theirs) - set(resolved)):
                readings += 1
                if key.endswith(".solver"):
                    # Die Fassung des Lösers ist eine Umsetzung, kein Druck.
                    continue
                if key == "#scene":
                    found = "#scene" in mine
                elif key.startswith("@"):
                    found = key[1:] in mine.get("@", {})
                else:
                    name = key[1:].split(":")[0].split(".")[0]
                    entry = entries.get(name)
                    if entry is None:
                        found = False
                    elif entry.kind in evaluation.SOURCE_KINDS:
                        found = f"#{name}" in mine
                    else:
                        found = "#scene" in mine
                if not found:
                    missed.append(f"{spec.name}: {key} bei {resolved}")
    assert readings > 20, f"nur {readings} Lesarten gefunden — dann prüft der Wächter nichts"
    assert not missed, "Lesarten des Cache-Schlüssels ohne Gegenstück im Abdruck:\n" + "\n".join(
        missed[:10]
    )


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


#: Was eine Kalibrierung misst (Bauplan §28.3) und jede Geometrie mit einem
#: ``auto:<material>``-Maß liest — Deckel, Passungen, Bausteine, Lochfelder.
CALIBRATED = ("clearance", "press", "hole_compensation", "elephant_foot", "shrinkage")


def _calibrated(material: Any, name: str) -> Any:
    return replace(material, **{name: getattr(material, name) + 0.02})


@pytest.mark.parametrize("name", CALIBRATED)
def test_a_calibration_is_another_print(name: str) -> None:
    """Review RM-706, S1: Der Deckel klemmt, kalibrieren, neu drucken — das sind zwei Drucke.

    Gezählt wird grob wie im Cache-Schlüssel: jeder feste Wert des Materials, auch
    am schlichten Quader. Lieber kippt der Abdruck einmal zu oft, als dass der
    zweite Druck die Buchung des ersten bekommt. Ein Slicer-Update kippt ihn
    weiter nicht (``test_the_settings_count_by_what_the_project_owns``).
    """
    objects, settings, profile, inputs = job(build())
    reference = request_for(objects, settings, profile, inputs).fingerprint
    calibrated = replace(profile, material=_calibrated(profile.material, name))
    assert request_for(objects, settings, calibrated, inputs).fingerprint != reference


def test_a_calibrated_own_material_of_a_body_is_another_print(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Körper mit eigenem Material rechnet mit dessen Spiel (``profiles.for_object``),
    nicht mit dem des Projekts; dessen Kalibrierung ist ein anderer Druck."""
    from app.core.knowledge import profiles as known

    objects, settings, profile, inputs = job(build())
    own = [replace(body, material="petg") for body in objects]
    reference = request_for(own, settings, profile, inputs).fingerprint
    original = known.material
    monkeypatch.setattr(
        known,
        "material",
        lambda name: _calibrated(original(name), "clearance") if name == "petg" else original(name),
    )
    assert request_for(own, settings, profile, inputs).fingerprint != reference


def test_a_calibrated_material_named_by_a_step_is_another_print(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Schritt mit Materialfeld (Dichtung, Klemme) rechnet mit dem Spiel dieses Materials."""
    from app.core.knowledge import profiles as known

    project = build()
    project.document.ops.append(
        Operation(
            id=50,
            op="create_seal",
            outputs=("obj_9",),
            params={"body_material": "petg", "gasket_material": "tpu-95a"},
        )
    )
    objects, settings, profile, _inputs = job(build())
    inputs = usage.StoredInputs(project.document)
    reference = request_for(objects, settings, profile, inputs).fingerprint
    original = known.material
    monkeypatch.setattr(
        known,
        "material",
        lambda name: (
            _calibrated(original(name), "clearance") if name == "tpu-95a" else original(name)
        ),
    )
    assert request_for(objects, settings, profile, inputs).fingerprint != reference


def test_an_own_process_in_the_slicer_is_another_print() -> None:
    """Review RM-706, M2: Ein eigener Prozess im Slicer (0,15 statt 0,28 mm Schicht)
    lässt die Stufe stehen und ändert die Grundlage — ein anderer Druck.

    Gezählt wird die *Wahl* der Grundlage (Slicerart, Maschine, Prozess), nicht ihr
    Inhalt: Ein Slicer-Update mit denselben Profilnamen kippt den Abdruck nicht,
    und wo der Slicer liegt, ändert nichts am Druck.
    """
    objects, settings, profile, inputs = job(build())

    def named(base: handover.SlicerSetup | None) -> str:
        return usage.prepare(objects, settings, profile, "Probe", inputs=inputs, base=base)[
            0
        ].fingerprint

    draft = handover.SlicerSetup(
        Path("prusa-slicer"), "prusa", "Original Prusa MK4S", "0.28mm DRAFT"
    )
    own = replace(draft, base_process="0.15mm SPEED")
    assert named(draft) != named(own)
    assert named(draft) != named(replace(draft, machine_profile="Original Prusa MK4"))
    assert named(draft) != named(replace(draft, flavour="orca"))
    assert named(draft) != named(None)
    # Derselbe Slicer an anderem Ort und mit neuen Werten unter denselben Namen.
    assert named(draft) == named(replace(draft, executable=Path("anderswo/prusa-slicer")))
    updated = print_settings.with_path(settings, "layers.layer_height", 0.3)
    assert usage.prepare(objects, updated, profile, "Probe", inputs=inputs, base=draft)[
        0
    ].fingerprint == named(draft)


@pytest.mark.parametrize("version", ["7.3", "8.0"])
def test_the_chosen_base_counts_by_name_not_by_path(version: str) -> None:
    """Nachprüfung RM-706, N1: Die Orca-Familie kennt ein Profil am Pfad seiner Datei,
    und Creality Print legt Installation und Nutzerdaten in Ordnern mit Fassungsnummer
    ab. Dieselbe Wahl nach einem Update ist derselbe Druck; ein anderer Name nicht."""
    objects, settings, profile, inputs = job(build())

    def setup(root: str, process: str = "0.20mm Standard @Creality K1 (0.4 nozzle)") -> Any:
        profiles_dir = f"C:\\Program Files\\Creality\\Creality Print {root}\\resources\\profiles"
        return handover.SlicerSetup(
            Path(f"C:/Program Files/Creality/Creality Print {root}/CrealityPrint.exe"),
            "orca",
            f"{profiles_dir}\\Creality\\machine\\Creality K1 (0.4 nozzle).json",
            f"C:\\Users\\kunde\\AppData\\Roaming\\Creality\\Creality Print\\{root}\\user\\42"
            f"\\process\\{process}.json",
        )

    def named(base: Any) -> str:
        return usage.prepare(objects, settings, profile, "Probe", inputs=inputs, base=base)[
            0
        ].fingerprint

    before = named(setup("7.2"))
    assert named(setup(version)) == before
    linux = handover.SlicerSetup(
        Path("/opt/creality/CrealityPrint"),
        "orca",
        "/home/kunde/.config/Creality/machine/Creality K1 (0.4 nozzle).json",
        "/home/kunde/.config/Creality/user/42/process/"
        "0.20mm Standard @Creality K1 (0.4 nozzle).json",
    )
    assert named(linux) == before
    assert named(setup(version, "0.12mm Fine @Creality K1 (0.4 nozzle)")) != before


def test_another_edge_answer_is_another_print() -> None:
    """Review RM-706, M1: Dieselben Werte, die Antwort einmal rechte, einmal linke Kante.

    Die Antwort steht in ``Operation.matches`` und wählt die Geometrie des
    Verbrauchers (``scene.edge_binding``) — zwei Netze, also zwei Drucke.
    """
    from app.core.scene import History, evaluate
    from tests import test_edge_binding as edge

    def answered(pick: Any) -> tuple[Any, Any]:
        body, kind = edge._body("mesh")
        registry = edge._registry(body, kind)
        document = edge._document(edge.COLLIDING_KEY)
        chooser = edge._EdgeChooser(pick)
        first = evaluate(
            document,
            edge._profile(),
            registry=registry,
            ask=chooser,
            question_context=chooser.context,
        )
        assert first.complete, first.scene.report.findings
        History(document).record_matches(first.matches)
        return document, evaluate(document, edge._profile(), registry=registry)

    right_document, right = answered(edge._right_box)
    left_document, left = answered(edge._left_box)
    assert right_document.ops[1].params == left_document.ops[1].params
    profile = edge._profile()
    settings = replace(print_settings.resolve(profile), inventory_project_id="rm706-kanten")
    fingerprints = [
        usage.prepare(
            list(result.scene.objects.values()),
            settings,
            profile,
            "Paar",
            inputs=usage.StoredInputs(document, None, result.stopped_at),
        )[0].fingerprint
        for document, result in ((right_document, right), (left_document, left))
    ]
    assert fingerprints[0] != fingerprints[1]


def _edge_answer(candidates: list[dict[str, Any]], chosen: int, scope: str) -> dict[str, Any]:
    from app.core.perceive.match_records import edge_answer_key

    key = "e:0.00,10.00,5.00:0.000,0.000,1.000"
    return {
        edge_answer_key("obj_1", "edge_keys", [key]): {
            "object_id": "obj_1",
            "field": "edge_keys",
            "keys": [key],
            "scope": scope,
            "candidates": {key: candidates},
            "decisions": {key: {"candidate": chosen}},
        }
    }


def _edge(x: float) -> dict[str, Any]:
    return {"middle": [x, 10.0, 5.0], "direction": [0.0, 0.0, 1.0], "extent": 0.0, "length": 10.0}


def _with_answer(matches: dict[str, Any]) -> dict[str, str]:
    project = build(
        extra=(
            OperationDraft(
                op="fillet_edges",
                params={"radius": 2.0, "edges": "named", "edge_keys": "e"},
                inputs=("obj_1",),
            ),
        )
    )
    last = project.document.ops[-1]
    project.document.ops[-1] = replace(last, matches=matches)
    return usage.StoredInputs(project.document).bodies()


def test_a_saved_answer_counts_as_its_decision_not_as_its_record() -> None:
    """M1: Eine nach einer neuen Fassung (``scope``) wieder gestellte und gleich
    beantwortete Frage behält den Abdruck — auch wenn die Kandidaten in anderer
    Folge und um weniger als die Druckgrenze verschoben gespeichert sind. Eine
    andere Wahl ändert ihn."""
    shift = PRINT_LIMIT / 4
    right = _with_answer(_edge_answer([_edge(-0.002), _edge(0.002)], 1, "fassung-1"))
    again = _with_answer(
        _edge_answer([_edge(0.002 + shift), _edge(-0.002 - shift)], 0, "fassung-2")
    )
    left = _with_answer(_edge_answer([_edge(-0.002), _edge(0.002)], 0, "fassung-1"))
    unanswered = _with_answer({})
    assert right == again
    assert right != left
    assert right != unanswered


def test_a_feature_mapping_counts_with_its_decision() -> None:
    """M1: Eine Merkmalszuordnung (§21.3) entscheidet, welches Merkmal ein späterer
    Schritt greift; eine andere Zuordnung und ``not_carried`` sind andere Drucke."""
    from app.core.perceive.match_records import group_key

    def mapping(decision: dict[str, Any]) -> dict[str, Any]:
        fingerprint = {
            "kind": "hole",
            "relative": [0.25, 0.5, 0.5],
            "axis": [0.0, 0.0, 1.0],
            "diameter": 5.0,
            "directional": False,
        }
        other = {**fingerprint, "relative": [0.75, 0.5, 0.5]}
        return {
            group_key("obj_1", ["hole_1"]): {
                "object_id": "obj_1",
                "old_ids": ["hole_1"],
                "candidates": [
                    {"fingerprint": fingerprint, "claims": ["hole_1"]},
                    {"fingerprint": other, "claims": ["hole_1"]},
                ],
                "decisions": {"hole_1": decision},
            }
        }

    first = _with_answer(mapping({"candidate": 0}))
    second = _with_answer(mapping({"candidate": 1}))
    dropped = _with_answer(mapping({"not_carried": True}))
    assert len({first["obj_1"], second["obj_1"], dropped["obj_1"]}) == 3


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


def test_a_creator_with_stray_inputs_keeps_them_like_the_evaluation() -> None:
    """Review RM-706, L1: Ein Erzeuger mit Eingängen (Dateien vor dem 07.09.2026)
    verbraucht sie nicht — die Auswertung lässt den genannten Körper stehen
    (``evaluate._without_stray_inputs``), also auch der Abdruck. Sonst fiel er auf
    seine Netzbits zurück und kippte mit jeder druckgleichen Änderung."""
    from app.core.types import Document

    document = Document(
        format_version=51,
        app_version="0.5.3",
        ops=[
            Operation(id=1, op="create_box", outputs=("obj_1",), params={"width": 20.0}),
            Operation(
                id=2, op="create_box", inputs=("obj_1",), outputs=("obj_2",), params={"width": 30.0}
            ),
        ],
    )
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    result = evaluate(document, profile)
    inputs = usage.StoredInputs(document, None, result.stopped_at)
    assert set(inputs.bodies()) == set(result.scene.objects) == {"obj_1", "obj_2"}
    settings = replace(print_settings.resolve(profile), inventory_project_id="rm706-streu")
    objects = list(result.scene.objects.values())
    before = request_for(objects, settings, profile, inputs)
    after = request_for(_changed(objects, _shifted), settings, profile, inputs)
    assert after.fingerprint == before.fingerprint


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
