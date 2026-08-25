"""Die Grenze im Datenpfad (Konzept §2 C, §2 I, V4).

Vier Stellen im Kern prüfen den Freischaltzustand selbst: jede
Dokumentänderung (``History.apply``), jeder Export (``write_plan``,
``write_assembly``), die Slicer-Übergabe (``slice_model``) und der Chat
(``AgentSession.propose``). Hier steht beides fest — dass sie mit abgelaufenem
Testlauf ablehnen, und dass alles Lesende weiterläuft. Die zweite Hälfte ist
die eigentliche Zusicherung: eine Testversion, die gespeicherte Arbeit
einschließt, erzeugt einen verärgerten Nicht-Käufer statt eines späteren.

Messen und Bemaßen liegen in der Ansicht, nicht im Dokument (§2 C) — es gibt
keinen Kernpfad, der sie sperren könnte; genau das ist ihre Freiheit. Der
Prüfbericht ist das Zusammensetzen der Befunde aus der Auswertung, die hier
als frei belegt wird.

Dazu das Manifest aus §2 I H4: eine veränderte Grenzdatei nimmt der
Freischaltung die Grundlage, und zwar beim Zustandsabruf — nicht über einen
Absturz.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from app.core import activation
from app.core.activation import integrity, key, store
from app.core.agent.session import AgentSession
from app.core.backends.llm import Reply
from app.core.backends.scripted import ScriptedBackend
from app.core.errors import ExternalToolError, LicenceRequired
from app.core.export.handover import SlicerSetup, slice_model
from app.core.export.writer import plan_export, write_assembly, write_plan
from app.core.geom.mesh import as_mesh_data, read_mesh
from app.core.geom.transform import place_on_bed
from app.core.ingest.loader import normalise
from app.core.perceive.maps import overhang_map
from app.core.scene import History, OperationDraft
from app.core.scene.evaluate import evaluate
from app.core.scene.project import Project, ProjectSources, load, new_project, save
from app.core.slice.analysis import cross_section
from app.core.types import PrintSettings, Profile, SceneObject, Source
from tools.make_licence_keys import public_key, sign

MESHES = Path(__file__).parent / "data" / "meshes"

#: Der erste Testvektor aus RFC 8032 — nur für die Signaturen dieser Datei.
TEST_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")


def _lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stellt den Zustand dieses Prozesses auf „Testlauf abgelaufen"."""
    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))


def _license(monkeypatch: pytest.MonkeyPatch) -> None:
    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-1234",
        holder="kaeufer@beispiel.de",
    )
    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence))


def _project() -> Project:
    """Ein Projekt mit einer geladenen Platte — gebaut, solange offen ist."""
    made = new_project("centauri-carbon-2", "petg")
    made.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    made.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    History(made.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    return made


def _body():
    return place_on_bed(
        normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh
    )


def _scene_object() -> SceneObject:
    return SceneObject(id="obj_1", name="Halterung", mesh=_body())


# --- Abgelaufen: die vier Grenzstellen lehnen ab ----------------------------------


def test_an_expired_trial_blocks_every_document_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regel-16-Gegenstück: nichts schreibt am Dokument vorbei, also reicht
    diese eine Stelle für jede Änderung — Op, Parameter, Passung, Material."""
    project = _project()
    before = list(project.document.transactions)
    _lock(monkeypatch)
    with pytest.raises(LicenceRequired) as raised:
        History(project.document).apply(
            "Duplizieren",
            [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"name": "Kopie"})],
        )
    assert raised.value.action == activation.CHANGE
    assert raised.value.suggestions, "Regel 17: auch diese Ausnahme trägt Handlungen"
    assert project.document.transactions == before, "abgelehnt heißt: nichts geschrieben"


def test_an_expired_trial_blocks_reparametrising_a_step(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Fund der Durchsicht: das nachträgliche Ändern schrieb an der Grenze
    vorbei. ``change_params``, ``change_inputs`` und ``change_kernel`` schreiben
    ins Dokument, riefen ``require`` aber nicht — nach Ablauf blieb jeder Schritt
    umparametrierbar und speicherbar, das Projekt an einer geschlossenen Grenze
    vorbei vollständig umkonstruierbar. Jede der drei holt jetzt selbst und wirft
    selbst (kern.md)."""
    project = _project()
    history = History(project.document)
    op_id = project.document.ops[0].id
    before = list(project.document.ops)
    _lock(monkeypatch)

    changes = (
        lambda: history.change_params(op_id, {"unit": "cm"}),
        lambda: history.change_inputs(op_id, ["obj_1"]),
        lambda: history.change_kernel(op_id, "load", {}),
    )
    for change in changes:
        with pytest.raises(LicenceRequired) as raised:
            change()
        assert raised.value.action == activation.CHANGE

    assert list(project.document.ops) == before, "abgelehnt heißt: nichts geschrieben"


def test_an_expired_trial_blocks_the_export(
    profile: Profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Planen und Prüfen sind Lesen und bleiben frei — die Datei nicht."""
    plan = plan_export([_scene_object()], project_name="P", profile=profile)
    _lock(monkeypatch)
    with pytest.raises(LicenceRequired) as raised:
        write_plan(plan, tmp_path)
    assert raised.value.action == activation.EXPORT
    assert list(tmp_path.iterdir()) == [], "abgelehnt heißt: keine Datei entstanden"


def test_an_expired_trial_blocks_the_assembly_export(
    profile: Profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _lock(monkeypatch)
    with pytest.raises(LicenceRequired) as raised:
        write_assembly([_scene_object()], tmp_path, project_name="P", profile=profile)
    assert raised.value.action == activation.EXPORT
    assert list(tmp_path.iterdir()) == []


def test_an_expired_trial_blocks_the_slicer(
    profile: Profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Grenze steht vor allem anderen — auch vor der Prüfung, ob der
    Slicer überhaupt eingerichtet ist."""
    _lock(monkeypatch)
    setup = SlicerSetup(executable=tmp_path / "slicer.exe", flavour="orca")
    with pytest.raises(LicenceRequired) as raised:
        slice_model(tmp_path / "teil.stl", PrintSettings(), profile, setup)
    assert raised.value.action == activation.SLICER


def test_an_expired_trial_blocks_the_chat(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Schon der Vorschlag, nicht erst das Übernehmen: ein Zug kostet
    Modellaufrufe. Das leere Skript belegt, dass das Backend nie gefragt wird."""
    project = _project()
    _lock(monkeypatch)
    agent = AgentSession(
        backend=ScriptedBackend(answers=[]), document=project.document, profile=profile
    )
    with pytest.raises(LicenceRequired) as raised:
        agent.propose("Mach das Loch größer")
    assert raised.value.action == activation.CHAT


# --- Abgelaufen: was liest, läuft weiter ------------------------------------------


def test_opening_evaluating_saving_and_undo_stay_free(
    profile: Profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2 C, Fall für Fall: öffnen, auswerten, speichern, zurücknehmen,
    wiederherstellen — der Betrachter bleibt vollständig."""
    project = _project()
    history = History(project.document)
    _lock(monkeypatch)

    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.scene.objects, "auswerten läuft nach Ablauf weiter"

    path = save(project, tmp_path / "projekt.p3d")
    reopened = load(path)
    assert reopened.document.ops == project.document.ops, "speichern und öffnen bleiben frei"

    taken_back = history.undo()
    assert taken_back is not None, "undo bleibt frei"
    assert history.redo() is taken_back, "redo bleibt frei"


def test_a_licence_lets_a_step_be_reparametrised(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Gegenrichtung: mit Schlüssel geht das Nachbearbeiten wie heute — die
    Grenze sperrt nur den abgelaufenen Testlauf, nie den Käufer."""
    project = _project()
    history = History(project.document)
    history.apply(
        "Duplizieren",
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"name": "Kopie"})],
    )
    op_id = project.document.ops[-1].id
    _license(monkeypatch)

    changed = history.change_params(op_id, {"name": "Andere"})
    assert changed.params["name"] == "Andere"


def test_the_slice_analysis_and_the_maps_stay_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """Schichtanalyse und Analysekarten sind Lesen — sie rechnen über dem
    Netz, nicht am Dokument."""
    _lock(monkeypatch)
    mesh = as_mesh_data(_body())
    section = cross_section(mesh, float(mesh.bounds.minimum[2]) + 0.2)
    assert section is not None and not section.is_empty
    assert overhang_map(mesh).kind == "overhang"


# --- Freigeschaltet: alles wie vorher ---------------------------------------------


def test_a_licence_opens_all_four_boundaries(
    profile: Profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mit Schlüssel verhält sich alles wie heute — der Slicer-Weg kommt an
    der Grenze vorbei und scheitert erst am fehlenden Werkzeug, was genau die
    Aussage ist."""
    project = _project()
    _license(monkeypatch)

    History(project.document).apply(
        "Duplizieren",
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"name": "Kopie"})],
    )

    plan = plan_export([_scene_object()], project_name="P", profile=profile)
    written = write_plan(plan, tmp_path)
    assert written and written[0].is_file()

    setup = SlicerSetup(executable=tmp_path / "fehlt.exe", flavour="orca")
    with pytest.raises(ExternalToolError):
        slice_model(tmp_path / "fehlt.stl", PrintSettings(), profile, setup)

    agent = AgentSession(
        backend=ScriptedBackend(answers=[Reply(text="Fertig.")]),
        document=project.document,
        profile=profile,
    )
    assert agent.propose("Sag Fertig").answer == "Fertig."


# --- Das Manifest (H4) ------------------------------------------------------------


@pytest.fixture
def fresh_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Eigener Einstellungsordner und leerer Zustands-Cache, vorher wie
    nachher — ein Manifest-Test darf den übrigen Lauf nicht sperren."""
    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    activation.forget_cache()
    yield tmp_path
    activation.forget_cache()


def _write_manifest(path: Path, files: dict[str, str], seed: bytes = TEST_SEED) -> None:
    manifest = {"files": files, "signature": sign(seed, integrity.manifest_payload(files)).hex()}
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _expect_manifest(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(integrity, "MANIFEST_PUBLIC_KEY", public_key(TEST_SEED))
    monkeypatch.setattr(integrity, "manifest_path", lambda: path)


def test_without_a_manifest_key_nothing_is_checked(tmp_path: Path) -> None:
    """Der Repository-Zustand: kein erwartetes Manifest, keine Prüfung —
    sonst sperrte jeder Arbeitsstand die eigene Suite."""
    assert integrity.MANIFEST_PUBLIC_KEY is None
    assert integrity.intact()


def test_an_intact_manifest_changes_nothing(
    fresh_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = fresh_state / "licence.manifest"
    _write_manifest(target, integrity.boundary_hashes())
    _expect_manifest(monkeypatch, target)
    assert activation.state().in_trial


def test_a_changed_boundary_file_locks_the_writing_side(
    fresh_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H4 in einem Satz: ein Patch an einer der vier Dateien fällt auf."""
    files = integrity.boundary_hashes()
    files["core/scene/history.py"] = "0" * 64
    target = fresh_state / "licence.manifest"
    _write_manifest(target, files)
    _expect_manifest(monkeypatch, target)
    assert activation.state().expired
    with pytest.raises(LicenceRequired):
        activation.require(activation.CHANGE)


def test_a_missing_manifest_locks_when_one_is_expected(
    fresh_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Manifest zu löschen darf die Prüfung nicht abschalten — sonst wäre
    sie ein Aufkleber."""
    _expect_manifest(monkeypatch, fresh_state / "licence.manifest")
    assert activation.state().expired


def test_a_manifest_signed_by_someone_else_locks(
    fresh_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein selbst geschriebenes Manifest hilft nicht: die Signatur läuft
    gegen den eingebauten öffentlichen Schlüssel."""
    other = bytes.fromhex("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7")
    target = fresh_state / "licence.manifest"
    _write_manifest(target, integrity.boundary_hashes(), seed=other)
    _expect_manifest(monkeypatch, target)
    assert activation.state().expired
