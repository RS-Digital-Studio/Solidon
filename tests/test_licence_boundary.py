"""Die Grenze im Datenpfad (Konzept §2 C, §2 I, V4).

Fünf Stellen im Kern prüfen den Freischaltzustand selbst: jede
Dokumentänderung (``History.apply``), das Löschen von Schritten
(``History.remove_operations``), jeder Export (``write_plan``,
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
from app.core.errors import ExternalToolError, InstallationDamaged, LicenceRequired
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
from tools.make_licence_keys import make_key, public_key, sign

MESHES = Path(__file__).parent / "data" / "meshes"

#: Der erste Testvektor aus RFC 8032 — nur für die Signaturen dieser Datei.
TEST_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")


def _lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stellt den Zustand dieses Prozesses auf „Testlauf abgelaufen"."""
    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))


def _certificate() -> activation.ActivationCertificate:
    """Ein bereits geprüftes Gerätezertifikat für reine Grenztests."""
    return activation.ActivationCertificate(
        licence_digest="test-licence",
        device_public=b"\x01" * 32,
        device_name="Prüfrechner",
        activation_id="test-activation",
        issued_on=date(2026, 8, 28),
    )


def _license(monkeypatch: pytest.MonkeyPatch) -> None:
    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-1234",
        holder="kaeufer@beispiel.de",
    )
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(licence=licence, certificate=_certificate()),
    )


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


def test_an_expired_trial_blocks_removing_a_step(monkeypatch: pytest.MonkeyPatch) -> None:
    """``remove_operations`` schreibt ins Dokument, ohne durch ``apply`` zu
    gehen — die Regel in ``kern.md`` verlangt für so eine Stelle den eigenen
    ``require``-Aufruf und diesen Fall hier, in beide Richtungen: Die
    Vorschau ``removal_closure`` ist Lesen und bleibt frei, das Löschen
    selbst lehnt ab und lässt das Dokument unberührt."""
    project = _project()
    history = History(project.document)
    op_id = project.document.ops[0].id
    before_ops = list(project.document.ops)
    before_transactions = list(project.document.transactions)
    _lock(monkeypatch)

    assert history.removal_closure([op_id]) == (op_id,), "die Vorschau ist Lesen und bleibt frei"

    with pytest.raises(LicenceRequired) as raised:
        history.remove_operations([op_id])
    assert raised.value.action == activation.CHANGE
    assert raised.value.suggestions, "Regel 17: auch diese Ausnahme trägt Handlungen"
    assert list(project.document.ops) == before_ops, "abgelehnt heißt: nichts geschrieben"
    assert list(project.document.transactions) == before_transactions


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


def test_answers_to_questions_of_the_evaluation_stay_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Entscheidung, festgenagelt — sonst geht sie beim nächsten Audit
    wieder als Lücke auf (dort stand sie schon einmal, 26.08.2026).

    ``record_answers`` und ``record_matches`` schreiben in den Stapel, aber
    nur, was die **Auswertung selbst erfragt** hat: die Einheit einer Datei,
    die Zuordnung eines Merkmals. Ein ``require`` dort sperrte das Öffnen
    einer Datei mit offener Rückfrage — der Betrachter wäre nicht mehr
    vollständig (§2 C). Die Grenze verläuft am Fragesteller: Was der Kunde
    anstößt, geht durch ``apply`` und dessen ``require``; was die Auswertung
    fragt, ist Teil des Lesens.
    """
    project = _project()
    history = History(project.document)
    _lock(monkeypatch)

    with pytest.raises(LicenceRequired):
        activation.require(activation.CHANGE)

    assert history.record_answers({1: {"unit": "in"}}), (
        "die Antwort auf eine Frage der Auswertung bleibt frei"
    )
    assert history.record_matches({1: {"at_feature": "hole_1"}}), "die Zuordnungsantwort ebenso"


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
    """H4 in einem Satz: ein Patch an einer der vier Dateien fällt auf.

    **Die Zusicherung hat sich am 26.08.2026 geändert, und zwar in dem Teil,
    der dem Kunden gilt.** Hier stand ``state().expired`` und
    ``raises(LicenceRequired)`` — gemessen wurde damit, dass eine beschädigte
    Installation sich als *abgelaufener Testzeitraum* meldet und *Solidon
    kaufen* vorschlägt. Das traf auch den, der längst bezahlt hatte: Sein
    Schlüssel wurde bei gebrochenem Manifest gar nicht erst gelesen.

    Gesperrt bleibt sie trotzdem — das ist der unveränderte Teil und wird hier
    weiter gemessen (``not unlocked``). Neu ist nur, wie sie heißt und welchen
    Weg sie anbietet: ein eigener Zustand mit Neuinstallation und Support.
    """
    files = integrity.boundary_hashes()
    files["core/scene/history.py"] = "0" * 64
    target = fresh_state / "licence.manifest"
    _write_manifest(target, files)
    _expect_manifest(monkeypatch, target)
    state = activation.state()
    assert state.damaged
    assert not state.unlocked, "H4 unverändert: die schreibende Seite bleibt zu"
    assert not state.expired, "abgelaufen ist es nicht — es ist beschädigt"
    with pytest.raises(InstallationDamaged):
        activation.require(activation.CHANGE)


def test_a_missing_manifest_locks_when_one_is_expected(
    fresh_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Manifest zu löschen darf die Prüfung nicht abschalten — sonst wäre
    sie ein Aufkleber."""
    _expect_manifest(monkeypatch, fresh_state / "licence.manifest")
    state = activation.state()
    assert state.damaged
    assert not state.unlocked


def test_a_manifest_signed_by_someone_else_locks(
    fresh_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein selbst geschriebenes Manifest hilft nicht: die Signatur läuft
    gegen den eingebauten öffentlichen Schlüssel."""
    other = bytes.fromhex("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7")
    target = fresh_state / "licence.manifest"
    _write_manifest(target, integrity.boundary_hashes(), seed=other)
    _expect_manifest(monkeypatch, target)
    state = activation.state()
    assert state.damaged
    assert not state.unlocked


def test_a_valid_key_does_not_open_a_damaged_installation(
    fresh_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Schlüssel wird gelesen — freischalten darf er hier nichts.

    Das ist die Kehrseite der freundlicheren Meldung und die gefährlichere
    Hälfte: Wäre ``damaged`` nur ein anderer Text und der Schlüssel zählte
    weiter, hätte H4 eine Hintertür bekommen — Grenzdatei patchen, gültigen
    Schlüssel danebenlegen, fertig.

    Beide Richtungen in einem Test, weil erst der Vergleich etwas aussagt:
    mit intaktem Manifest schaltet derselbe Schlüssel dieselbe Handlung frei.
    """
    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-1234",
        holder="kaeufer@beispiel.de",
    )
    monkeypatch.setattr(key, "PUBLIC_KEY", public_key(TEST_SEED))
    store.write_key(make_key(TEST_SEED, licence))
    monkeypatch.setattr(activation.certificates, "load_for", lambda _licence: _certificate())
    target = fresh_state / "licence.manifest"

    # Richtung eins: unversehrt — Schlüssel und Gerätezertifikat wirken.
    _write_manifest(target, integrity.boundary_hashes())
    _expect_manifest(monkeypatch, target)
    activation.forget_cache()
    assert activation.state().unlocked
    activation.require(activation.CHANGE)

    # Richtung zwei: dieselbe Ablage, eine geänderte Grenzdatei.
    files = integrity.boundary_hashes()
    files["core/export/writer.py"] = "0" * 64
    _write_manifest(target, files)
    activation.forget_cache()
    state = activation.state()

    assert state.licence is not None, "der zahlende Kunde wird erkannt"
    assert not state.unlocked, "erkannt heißt nicht freigeschaltet (H4)"
    with pytest.raises(InstallationDamaged):
        activation.require(activation.EXPORT)


def test_typing_a_key_does_not_repair_a_damaged_installation(
    fresh_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Test darüber prüft den **abgelegten** Schlüssel — dieser den frisch
    **eingetippten**, und das war die offene Tür.

    ``remember`` setzt den Zustand aus der eben geprüften Lizenz, statt ihn
    über ``state()`` neu zu ermitteln; das ist richtig und begründet — es läse
    die Datei ein zweites Mal und rechnete dieselbe Signaturprüfung noch
    einmal. Dabei fiel aber ``damaged`` heraus: Wer eine Grenzdatei veränderte
    und danach seinen gültigen Schlüssel eintippte, hob die Sperre für die
    ganze Sitzung auf. Dieselbe Hintertür, die der Test darüber schließt, nur
    durch die andere Tür — und die Oberfläche war die einzige Hürde davor
    (der Prüfknopf ist bei ``damaged`` grau), was ``kern.md`` ausdrücklich
    nicht gelten lässt: Die Oberfläche graut nur vorher aus, sie ist nie die
    Hürde.
    """
    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-1234",
        holder="kaeufer@beispiel.de",
    )
    monkeypatch.setattr(key, "PUBLIC_KEY", public_key(TEST_SEED))
    text = make_key(TEST_SEED, licence)

    target = fresh_state / "licence.manifest"
    files = integrity.boundary_hashes()
    files["core/scene/history.py"] = "0" * 64
    _write_manifest(target, files)
    _expect_manifest(monkeypatch, target)
    activation.forget_cache()

    state = activation.remember(text)

    assert state.licence is not None, "der Schlüssel ist gültig und wird gelesen"
    assert not state.unlocked, "ein eingetippter Schlüssel hebt die Sperre nicht auf"
    with pytest.raises(InstallationDamaged):
        activation.require(activation.CHANGE)
    with pytest.raises(InstallationDamaged):
        activation.require(activation.EXPORT)


def test_a_refused_import_leaves_nothing_behind(
    monkeypatch: pytest.MonkeyPatch, qt_app: object, tmp_path: Path
) -> None:
    """Abgelehnt heißt: nichts geschrieben — auch keine Quelle.

    **Die Grenze hielt, und trotzdem blieb etwas liegen.** `import_model`
    bettet die Quelle ein und lässt danach `apply` rechnen; `History.apply`
    fragt als Erstes die Lizenzgrenze. Der Rücknahmepfad galt aber nur dem
    Einleseplan, nicht dem Anwenden — also entstand keine Geometrie (die
    Grenze hielt), und die Quelle blieb im Dokument. Bei einem großen STL sind
    das hunderte Megabyte, die mit dem nächsten Speichern in die Projektdatei
    wandern.

    Der schwerere Teil ist nicht die Größe: `_embed_source` setzt kein
    `_dirty`, der Kunde schließt also **ohne Nachfrage**, und seine Datei
    trägt danach etwas, das er nie hineingetan hat. Dasselbe Argument, mit dem
    §32 die Ansage fremder Inhalte begründet.

    **Und der Aufrufer merkt davon nichts**, was den Fall erst vollständig
    macht: ``Session.apply`` fängt jeden ``AppError`` und schickt ihn über
    ``failed`` an die Oberfläche, wirft also nicht. Ein ``try`` um den Aufruf
    griffe nie. Gefragt wird deshalb nach dem Ergebnis — ist ein Schritt
    entstanden? —, und das trägt die Lizenzgrenze genauso wie jeden anderen
    Ablehnungsgrund, der einmal dazukommt.

    Gefunden von 3d-druck-46 im Lizenz-Audit.
    """
    from app.ui.session import Session

    session = Session()
    stl = (Path(__file__).parent / "data" / "meshes" / "plate_holes.stl").read_bytes()
    gemeldet: list[object] = []
    session.failed.connect(gemeldet.append)
    _lock(monkeypatch)

    session.import_payload("plate_holes.stl", stl, unit="mm")

    assert gemeldet, "abgelehnt wird nicht stumm — die Oberfläche bekommt den Grund"
    assert not session.project.document.sources, "die Quelle ist wieder draußen"
    assert not session.project.sources, "und ihr Inhalt auch"
    assert not session.project.document.ops, "Geometrie ist ohnehin keine entstanden"
    assert not session._dirty, "und nichts zu speichern, worüber niemand gefragt hätte"


def test_an_image_needs_the_same_permission_as_everything_else(
    monkeypatch: pytest.MonkeyPatch, qt_app: object, tmp_path: Path
) -> None:
    """Auch ohne Operation ist ein eingebettetes Bild eine Änderung (§2 C).

    ``import_image`` legt eine Quelle ins Dokument und fragte niemanden.
    Erreichbar war der Weg praktisch nur aus einem Operationsdialog, und die
    sind gesperrt — aber das ist ein Zufall der Oberfläche und keine Grenze.
    Wer sich darauf verlässt, hat eine Zusage, die beim nächsten Aufrufer still
    verschwindet; `kern.md` verlangt deshalb, dass jede schreibende Stelle den
    Zustand selbst holt und selbst wirft.
    """
    from app.core.errors import LicenceRequired
    from app.ui.session import Session

    bild = tmp_path / "relief.png"
    bild.write_bytes(bytes([137]) + b"PNG" + b"0" * 64)
    session = Session()
    _lock(monkeypatch)

    with pytest.raises(LicenceRequired):
        session.import_image(bild)

    assert not session.project.document.sources, "abgelehnt heißt: nichts geschrieben"
