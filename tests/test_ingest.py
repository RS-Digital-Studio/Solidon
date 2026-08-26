"""Die Eingangsstufe: sechs Schritte, eine Einheitenfrage, und harte
Importgrenzen (§17.1, §32).
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshCodec, MeshData, read_mesh
from app.core.ingest.loader import (
    MAX_FILE_BYTES,
    MAX_TRIANGLES,
    check_limits,
    detect_unit,
    normalise,
)
from app.core.ingest.ops import unit_question
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import CachedResult, DiskCache
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def mesh_of(name: str) -> MeshData:
    return read_mesh((MESHES / name).read_bytes(), ".stl")


# --- unit heuristic -------------------------------------------------------------


def test_a_single_plausible_reading_needs_no_question() -> None:
    guess = detect_unit(mesh_of("cube_clean.stl").bounds.diagonal)
    assert guess.certain
    assert guess.unit == "mm"


def test_an_ambiguous_size_asks_instead_of_assuming() -> None:
    for name in ("bracket_inch.stl", "plate_cm.stl"):
        guess = detect_unit(mesh_of(name).bounds.diagonal)
        assert not guess.certain, name
        assert set(guess.candidates) >= {"cm", "in"}, name


def test_an_empty_model_offers_every_unit() -> None:
    guess = detect_unit(0.0)
    assert not guess.certain
    assert guess.candidates == ("mm", "cm", "in", "m")


def test_a_small_part_can_still_be_read_in_millimetres() -> None:
    """Die gemessene Einheit steht immer zur Wahl (§17.1).

    Eine M3-Unterlegscheibe misst über alles rund sieben Millimeter, und damit
    fiel „mm" aus der Antwortliste: Die Heuristik hält alles unter zehn
    Millimetern für unplausibel, und was unplausibel ist, stand nicht zur
    Auswahl. Wer eine korrekte Datei in Millimetern importierte, konnte also
    nur zwischen „cm" und „in" wählen — beide falsch — oder abbrechen.

    Als *einzige* Lesart bleibt „mm" hier unplausibel; das ist der Grund, dass
    überhaupt gefragt wird. Als *Antwort* muss sie dastehen.
    """
    guess = detect_unit(5.0)

    assert not guess.certain, "fünf Millimeter oder fünf Zentimeter — das ist eine Frage"
    assert "mm" in guess.candidates, "die Datei so zu nehmen, wie sie dasteht"
    assert guess.candidates[0] == "mm", "und zuerst, denn es ist der häufigste Fall"
    assert set(guess.candidates) >= {"cm", "in"}, "die plausiblen Lesarten bleiben"


def test_the_question_says_how_big_each_answer_would_be() -> None:
    """Eine Frage, die niemand beantworten kann, ist die halbe Regel (§17.1).

    Zur Wahl standen „cm" und „in" — zwei Wörter. In keinem STL steht die
    Einheit; wer eine fremde Datei herunterlädt, kann sie nicht wissen. Was er
    weiß, ist, wie groß das Teil sein soll, und genau das steht jetzt neben
    jeder Antwort.
    """
    bounds = mesh_of("bracket_inch.stl").bounds
    guess = detect_unit(bounds.diagonal)
    question = unit_question(bounds.size, guess.candidates)

    lines = question.splitlines()
    assert lines[0] == str(_("In welcher Einheit ist diese Datei gespeichert?"))
    assert len(lines) == 1 + len(guess.candidates), "je Antwort eine Zeile"
    for unit in guess.candidates:
        assert any(line.startswith(f"{unit}:") for line in lines[1:]), unit
    # Vier Zoll sind 101,6 mm — die Zahl, an der man die Antwort erkennt.
    assert "101.60" in question
    assert "40.00" in question, "und in Zentimetern wären es vierzig"


# --- reading --------------------------------------------------------------------


def test_a_clean_cube_reads_as_twelve_triangles() -> None:
    """Lesen ist nur Lesen: STL wiederholt jeden Eckpunkt, das rohe Netz ist
    also noch nicht wasserdicht — und genau dafür gibt es Schritt 2 der
    Eingangsstufe.
    """
    mesh = mesh_of("cube_clean.stl")
    assert mesh.triangle_count == 12
    assert mesh.vertex_count == 36
    assert not mesh.is_watertight
    assert mesh.volume == pytest.approx(8000.0)
    assert mesh.bounds.size == pytest.approx((20.0, 20.0, 20.0))


def test_an_unknown_format_is_refused_with_a_suggestion() -> None:
    with pytest.raises(ValidationError) as caught:
        read_mesh(b"whatever", ".xyz")
    assert caught.value.constraint == "unsupported_format"
    assert caught.value.suggestions


def test_a_damaged_file_is_reported_not_raised_raw() -> None:
    with pytest.raises(ValidationError) as caught:
        read_mesh(b"not an stl at all", ".stl")
    assert caught.value.constraint in ("unreadable", "no_geometry")


# --- die sechs Schritte ---------------------------------------------------------


def test_welding_turns_a_raw_stl_into_a_solid() -> None:
    result = normalise(mesh_of("cube_clean.stl"), "mm")
    assert result.mesh.triangle_count == 12
    assert result.mesh.vertex_count == 8, "the 36 repeated STL vertices were welded"
    assert result.mesh.is_watertight
    assert result.info.welded
    assert result.info.scale == pytest.approx(1.0)
    assert result.info.components == 1
    assert result.info.removed_triangles == 0
    assert result.mesh.volume == pytest.approx(8000.0)


def test_welding_that_would_tear_the_mesh_open_is_taken_back() -> None:
    """Verschweißen ist eine Reparatur, und eine Reparatur, die etwas kaputt
    macht, wird nicht angewendet.

    Gefunden an einer 3MF, die diese Anwendung selbst geschrieben hatte: 17186
    Ecken, wasserdicht; verschweißt bei 0,28 µm blieben 17184, und der
    Prüfbericht sagte „Das Modell ist nicht geschlossen" über eine Datei, die es
    war. Hier derselbe Fall in klein — zwei geschlossene Quader, die eine Fläche
    teilen: zusammengelegt bekommt jede Kante dieser Fläche vier Nachbarn statt
    zwei.
    """
    import trimesh

    lower = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    lower.apply_translation((0.0, 0.0, 5.0))
    upper = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    upper.apply_translation((0.0, 0.0, 15.0))
    stacked = trimesh.util.concatenate([lower, upper])
    assert stacked.is_watertight, "beide Quader sind für sich geschlossen"

    result = normalise(MeshData.of(stacked), "mm")

    assert result.mesh.is_watertight, "und bleiben es"
    assert result.mesh.vertex_count == 16, "die geteilten Ecken stehen noch"
    assert not result.info.welded
    codes = {finding.code for finding in result.findings}
    assert "ingest.weld_skipped" in codes
    assert "ingest.not_watertight" not in codes


def test_welding_can_be_switched_off() -> None:
    result = normalise(mesh_of("cube_clean.stl"), "mm", weld=False)
    assert not result.info.welded
    assert result.mesh.vertex_count == 36


def test_the_unit_is_converted_exactly_once() -> None:
    result = normalise(mesh_of("bracket_inch.stl"), "in")
    assert result.info.scale == pytest.approx(25.4)
    assert result.mesh.bounds.size == pytest.approx((101.6, 50.8, 6.35))
    assert "ingest.scaled" in {finding.code for finding in result.findings}


def test_degenerate_triangles_are_removed_and_reported() -> None:
    before = mesh_of("degenerate.stl")
    result = normalise(before, "mm")
    assert result.mesh.triangle_count < before.triangle_count
    assert result.info.removed_triangles > 0
    assert "ingest.degenerate_removed" in {finding.code for finding in result.findings}


def test_an_open_model_is_reported_not_repaired() -> None:
    result = normalise(mesh_of("broken_open.stl"), "mm")
    assert not result.mesh.is_watertight
    finding = next(f for f in result.findings if f.code == "ingest.not_watertight")
    assert finding.severity == "warning"


def test_small_components_are_reported_and_kept() -> None:
    before = mesh_of("two_components.stl")
    result = normalise(before, "mm")
    codes = {finding.code for finding in result.findings}
    assert "ingest.multiple_components" in codes
    assert "ingest.small_components" in codes
    assert result.info.components == 2
    assert result.mesh.triangle_count == before.triangle_count, "nothing is deleted silently"


def test_placing_on_the_bed_is_offered_not_forced() -> None:
    lying = normalise(mesh_of("cube_clean.stl"), "mm")
    assert lying.mesh.bounds.minimum[2] == pytest.approx(-10.0)

    placed = normalise(mesh_of("cube_clean.stl"), "mm", place_on_bed=True)
    assert placed.mesh.bounds.minimum[2] == pytest.approx(0.0)


def test_progress_is_reported_while_running() -> None:
    seen: list[float] = []
    normalise(
        mesh_of("cube_clean.stl"), "mm", progress=lambda fraction, text: seen.append(fraction)
    )
    assert seen and seen[-1] == pytest.approx(1.0)


# --- limits (§32) ---------------------------------------------------------------


def test_the_warning_about_a_fine_mesh_holds_at_the_limit_it_names() -> None:
    """Drei Schwellen für eine Frage, und die Warnung stimmte in keiner.

    Gesagt wurde „Analysekarten und Merkmalserkennung lehnen ab" — ab 500 000
    Dreiecken. Die Karten lehnen aber ab 120 000 ab und die Merkmalserkennung
    ab 200 000 (§31): Zwischen 200 000 und 500 000 war beides längst
    abgelehnt, und die Eingangsstufe schwieg dazu. Die Zahl hier ist deshalb
    keine eigene mehr, sondern die kleinere der beiden echten.
    """
    from app.core.ingest import loader
    from app.core.perceive.maps import MAP_LIMIT_TRIANGLES
    from app.core.scene.evaluate import FEATURE_LIMIT_TRIANGLES

    assert min(MAP_LIMIT_TRIANGLES, FEATURE_LIMIT_TRIANGLES) == loader.HEAVY_TRIANGLES
    assert loader._too_fine(MAP_LIMIT_TRIANGLES) is None, "an der Grenze ist noch alles möglich"

    dazwischen = loader._too_fine(MAP_LIMIT_TRIANGLES + 1)
    assert dazwischen is not None and dazwischen.code == "ingest.very_large"
    assert "Merkmalserkennung" not in str(dazwischen.message), "die läuft hier noch"
    assert "Dreiecke verringern" in str(dazwischen.message), "Regel 17: was jetzt hilft"

    darueber = loader._too_fine(FEATURE_LIMIT_TRIANGLES + 1)
    assert darueber is not None
    assert "Merkmalserkennung" in str(darueber.message), "und hier lehnt auch sie ab"
    assert darueber.values["triangles"] == FEATURE_LIMIT_TRIANGLES + 1


def test_import_limits_are_stated_clearly() -> None:
    check_limits(1000, 1000)

    with pytest.raises(ValidationError) as big_file:
        check_limits(MAX_FILE_BYTES + 1, 10)
    assert big_file.value.constraint == "file_too_large"
    assert big_file.value.suggestions

    with pytest.raises(ValidationError) as many_triangles:
        check_limits(10, MAX_TRIANGLES + 1)
    assert many_triangles.value.constraint == "too_many_triangles"


def test_a_zip_bomb_is_refused_before_anything_parses_it(monkeypatch) -> None:
    """§32: Die Grenze steht **vor** dem Parsen, nicht daneben.

    ``import_plan`` zählt die Körper einer 3MF, weil der Stapel die Objekt-IDs
    vergeben muss, bevor gerechnet wird (§11) — und zählen heißt, das ganze
    XML zu lesen. Eine Datei von 1,9 MB wird dabei zu 660 MB im Speicher des
    Hauptfensters, und geprüft wurde die entpackte Größe erst in der
    Operation, also lange danach. ``check_unpacked`` gab es genau für diesen
    Fall; es lief nur an der falschen Stelle.

    Die Grenze steht hier klein, damit der Test keine 600 MB anlegen muss —
    geprüft wird die Reihenfolge, nicht die Zahl.
    """
    from app.core.export import threemf
    from app.core.ingest import loader, plan

    monkeypatch.setattr(loader, "MAX_FILE_BYTES", 1_000_000)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr("3D/3dmodel.model", bytes(4_000_000))
    payload = buffer.getvalue()
    assert len(payload) < 100_000, "gepackt harmlos, entpackt nicht"

    def niemals(_payload: bytes) -> tuple[int, int]:
        raise AssertionError("gescannt wurde, bevor die Grenze griff")

    monkeypatch.setattr(threemf, "scan_assembly", niemals)

    with pytest.raises(ValidationError) as abgewiesen:
        plan.import_plan("src_1", "bombe.3mf", payload)

    assert abgewiesen.value.constraint == "file_too_large"
    assert abgewiesen.value.suggestions, "Regel 17"


def test_a_too_large_file_is_refused_for_every_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """M7: die Größengrenze stand nur im 3MF-Zweig.

    Eine zu große STL ging als Quelle ins Dokument, die Operation landete im
    Stapel und scheiterte erst bei der Auswertung — und die übergroße Quelle
    wanderte beim nächsten Speichern in die Projektdatei. Die Grenze steht jetzt
    vor der Operation, für jedes Format.
    """
    from app.core.ingest import loader, plan

    monkeypatch.setattr(loader, "MAX_FILE_BYTES", 1000)
    payload = bytes(5000)

    for name in ("teil.stl", "teil.obj", "teil.ply", "teil.step", "teil.svg"):
        with pytest.raises(ValidationError) as refused:
            plan.import_plan("src_1", name, payload)
        assert refused.value.constraint == "file_too_large", name
        assert refused.value.suggestions, "Regel 17"


# --- die Lade-Operation ---------------------------------------------------------


def project_with(name: str) -> Project:
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    project.sources["src_1"] = (MESHES / name).read_bytes()
    return project


def test_load_puts_a_named_object_into_the_scene(profile: Profile) -> None:
    project = project_with("cube_clean.stl")
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    body = result.scene.objects["obj_1"]
    assert body.name == "cube_clean"
    assert body.mesh.volume == pytest.approx(8000.0)
    assert body.created_by == 1


def test_load_asks_when_the_unit_is_ambiguous(profile: Profile) -> None:
    project = project_with("bracket_inch.stl")
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])
    asked: list[tuple[str, list[str]]] = []

    def ask(question: str, choices: list[str]) -> str:
        asked.append((question, choices))
        return "in"

    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=ask)

    assert asked, "an ambiguous unit is a question, not a guess"
    assert "in" in asked[0][1]
    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((101.6, 50.8, 6.35))


def _three_mf(name: str, unit: str, size: float = 4.0) -> bytes:
    """Ein Würfel als 3MF, mit einer selbst gewählten Einheitenangabe.

    ``threemf.write`` schreibt immer Millimeter — die Angabe wird danach
    ausgetauscht, damit im Test die Datei steht und nicht ein zweiter
    Schreiber daneben. Leer heißt: **kein** Attribut, also eine Datei, die
    nichts über ihre Einheit sagt.
    """
    from app.core.export import threemf

    cube = trimesh.creation.box((size, size, size))
    payload = threemf.write(MeshData.of(cube), name=name)
    buffer = BytesIO()
    with (
        zipfile.ZipFile(BytesIO(payload)) as quelle,
        zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as ziel,
    ):
        for info in quelle.infolist():
            data = quelle.read(info.filename)
            if info.filename == threemf.MODEL_PATH:
                ersatz = f'unit="{unit}"'.encode() if unit else b""
                data = data.replace(b'unit="millimeter"', ersatz)
                assert ersatz in data
            ziel.writestr(info.filename, data)
    return buffer.getvalue()


def _project_of(payload: bytes, name: str = "wuerfel.3mf") -> Project:
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    project.sources["src_1"] = payload
    return project


def _asks_never(question: str, choices: list[str]) -> str:
    raise AssertionError(f"gefragt, obwohl die Datei es sagt: {question}")


@pytest.mark.parametrize(
    ("declared", "factor"),
    [("millimeter", 1.0), ("centimeter", 10.0), ("inch", 25.4), ("meter", 1000.0)],
)
def test_a_3mf_states_its_unit_and_is_not_asked_about_it(
    profile: Profile, declared: str, factor: float
) -> None:
    """§17.1: Gefragt wird, wo die Datei schweigt — nicht, wo sie es sagt.

    STL kennt keine Einheit, 3MF schon: sie steht im ``unit``-Attribut des
    Modells. Solidon las sie nicht und stellte die Frage trotzdem — bei einem
    4-mm-Würfel mit „cm" und „in" zur Auswahl, und die Datei sagte die ganze
    Zeit, was richtig ist.
    """
    project = _project_of(_three_mf("Wuerfel", declared))
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=_asks_never)

    assert result.complete
    size = result.scene.objects["obj_1"].mesh.bounds.size
    assert size == pytest.approx((4.0 * factor,) * 3)


@pytest.mark.parametrize(("declared", "factor"), [("micron", 0.001), ("foot", 304.8)])
def test_a_unit_that_none_of_the_four_answers_names_still_arrives(
    profile: Profile, declared: str, factor: float
) -> None:
    """Der Grund, dass die Frage hier nicht reicht: Das Format kennt Mikrometer
    und Fuß, der Kern kennt sie nicht (§11.1).

    Keine der vier Antworten wäre richtig gewesen — die Datei hätte sich nur
    falsch importieren lassen. Umgerechnet wird auf eine Einheit, die Solidon
    führt; der Rest ist ein Faktor davor.
    """
    project = _project_of(_three_mf("Wuerfel", declared))
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=_asks_never)

    assert result.complete
    size = result.scene.objects["obj_1"].mesh.bounds.size
    assert size == pytest.approx((4.0 * factor,) * 3)
    codes = {entry.code for entry in result.scene.report.findings}
    assert "ingest.declared_unit" in codes, "und es steht dabei, woher die Zahl kommt"


def test_placing_an_assembly_on_the_bed_moves_it_as_one(profile: Profile) -> None:
    """„Auf das Bett setzen" tat bei einer Baugruppe nichts — und sagte es
    nicht (§17.1, Schritt 6).

    Der Grund war richtig: Jeden Körper für sich abzusetzen nähme einem
    Gehäuse den Deckel ab und stapelte die Teile aufeinander. Die Antwort
    darauf ist aber nicht, den Haken wirkungslos zu machen, sondern die Gruppe
    **gemeinsam** abzusetzen: Der unterste Punkt kommt auf null, und die Teile
    behalten ihre Lage zueinander.
    """
    from app.core.export import threemf

    unten = trimesh.creation.box((10.0, 10.0, 10.0))
    unten.apply_translation((0.0, 0.0, 15.0))
    oben = trimesh.creation.box((10.0, 10.0, 10.0))
    oben.apply_translation((0.0, 0.0, 35.0))
    payload = threemf.write_assembly(
        [
            threemf.AssemblyPart(mesh=MeshData.of(unten), name="Unten"),
            threemf.AssemblyPart(mesh=MeshData.of(oben), name="Oben"),
        ]
    )
    project = _project_of(payload, "gruppe.3mf")
    history = History(project.document)
    history.apply(
        _("Laden"),
        [
            OperationDraft(
                op="load",
                params={"source": "src_1", "place_on_bed": True},
                produces=2,
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    erstes = result.scene.objects["obj_1"].mesh.bounds
    zweites = result.scene.objects["obj_2"].mesh.bounds
    assert erstes.minimum[2] == pytest.approx(0.0), "die Gruppe steht auf der Platte"
    assert zweites.minimum[2] == pytest.approx(20.0), "und der Abstand der Teile bleibt"
    codes = {entry.code for entry in result.scene.report.findings}
    assert "load.assembly_on_bed" in codes, "und es steht dabei, dass etwas verschoben wurde"


def test_an_assembly_already_on_the_bed_is_left_alone(profile: Profile) -> None:
    """Die Gegenprobe: Wer schon unten steht, wird nicht verschoben — und
    bekommt auch keinen Befund darüber."""
    from app.core.export import threemf

    unten = trimesh.creation.box((10.0, 10.0, 10.0))
    unten.apply_translation((0.0, 0.0, 5.0))
    oben = trimesh.creation.box((10.0, 10.0, 10.0))
    oben.apply_translation((0.0, 0.0, 25.0))
    payload = threemf.write_assembly(
        [
            threemf.AssemblyPart(mesh=MeshData.of(unten), name="Unten"),
            threemf.AssemblyPart(mesh=MeshData.of(oben), name="Oben"),
        ]
    )
    project = _project_of(payload, "gruppe.3mf")
    history = History(project.document)
    history.apply(
        _("Laden"),
        [
            OperationDraft(
                op="load",
                params={"source": "src_1", "place_on_bed": True},
                produces=2,
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.scene.objects["obj_2"].mesh.bounds.minimum[2] == pytest.approx(20.0)
    codes = {entry.code for entry in result.scene.report.findings}
    assert "load.assembly_on_bed" not in codes


def test_the_import_plan_does_not_ask_what_the_file_answers() -> None:
    """Und die Stelle davor: Die Kommandozeile fragt nach dem Plan, nicht
    nach der Operation.

    Stand ``asks_unit`` auf wahr, fragte sie — und schrieb die Antwort in die
    Parameter. Damit hätte eine getippte Einheit die Angabe der Datei
    überschrieben, ohne dass jemand von ihr wusste.
    """
    from app.core.ingest.plan import import_plan

    mit = import_plan("src_1", "wuerfel.3mf", _three_mf("Wuerfel", "inch"))
    ohne = import_plan("src_1", "wuerfel.3mf", _three_mf("Wuerfel", ""))

    assert not mit.asks_unit, "die Datei sagt es"
    assert ohne.asks_unit, "und wo sie schweigt, wird gefragt"
    assert import_plan("src_1", "teil.stl", b"").asks_unit, "ein STL sagt nie etwas"


def test_a_3mf_without_a_unit_is_still_asked_about(profile: Profile) -> None:
    """Die Gegenprobe: Ohne Angabe bleibt es bei der Frage (Regel 21)."""
    project = _project_of(_three_mf("Wuerfel", ""))
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])
    asked: list[list[str]] = []

    def ask(question: str, choices: list[str]) -> str:
        asked.append(choices)
        return "mm"

    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=ask)

    assert result.complete
    assert asked, "vier Millimeter sind mehrdeutig, und die Datei sagt nichts"
    assert "mm" in asked[0]


def test_the_unit_chosen_by_hand_beats_the_one_in_the_file(profile: Profile) -> None:
    """Wer die Einheit im Stapel setzt, korrigiert die Datei — auch eine, die
    sich irrt."""
    project = _project_of(_three_mf("Wuerfel", "inch"))
    history = History(project.document)
    history.apply(
        _("Laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=_asks_never)

    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((4.0, 4.0, 4.0))


def test_the_answer_can_be_stored_in_the_operation(profile: Profile) -> None:
    """Die Einheit zu speichern macht aus der Frage eine einmalige (§17.1)."""
    project = project_with("plate_cm.stl")
    history = History(project.document)
    history.apply(
        _("Laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "cm"})],
    )

    def refuse(question: str, choices: list[str]) -> str:
        raise AssertionError("a stored unit must not be asked for again")

    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=refuse)
    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((80.0, 50.0, 5.0))


def test_without_anyone_to_ask_the_chain_stops(profile: Profile) -> None:
    project = project_with("bracket_inch.stl")
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.stopped_at == 1, "guessing would be worse than stopping"
    assert any("AmbiguityError" in finding.code for finding in result.scene.report.findings)


def test_findings_of_the_input_stage_reach_the_report(profile: Profile) -> None:
    project = project_with("two_components.stl")
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    codes = {finding.code for finding in result.scene.report.findings}
    assert "ingest.small_components" in codes
    # Was aus einer Operation kommt, trägt ihre Nummer. Nicht jeder Befund tut
    # das: die Prüfungen der Szene — Passungen (§14) und die Lage zum Bauraum —
    # gehören keiner Operation, sondern dem Stand danach.
    from_operations = [
        finding for finding in result.scene.report.findings if finding.code.startswith("ingest.")
    ]
    assert from_operations
    assert all(finding.op_id == 1 for finding in from_operations)


def test_an_unknown_source_is_a_user_error(profile: Profile) -> None:
    project = project_with("cube_clean.stl")
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_9"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.stopped_at == 1


def test_a_linked_source_is_read_relative_to_the_project(profile: Profile, tmp_path: Path) -> None:
    (tmp_path / "meshes").mkdir()
    (tmp_path / "meshes" / "cube_clean.stl").write_bytes((MESHES / "cube_clean.stl").read_bytes())
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path="meshes/cube_clean.stl",
        sha256="",
        embedded=False,
    )
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project, base_dir=tmp_path))
    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(8000.0)


# --- mesh hull ------------------------------------------------------------------


def test_a_mesh_survives_the_disk_cache_losslessly(tmp_path: Path) -> None:
    mesh = mesh_of("cube_clean.stl")
    disk = DiskCache(codec=MeshCodec(), directory=tmp_path)
    from app.core.types import SceneObject

    disk.put("key", CachedResult(objects=(SceneObject(id="obj_1", name="Würfel", mesh=mesh),)))

    restored = disk.get("key")
    assert restored is not None
    assert restored.objects[0].mesh.triangle_count == 12
    assert restored.objects[0].mesh.volume == pytest.approx(8000.0)


def test_the_hull_exports_binary_stl() -> None:
    payload = mesh_of("cube_clean.stl").to_stl()
    assert read_mesh(payload, ".stl").triangle_count == 12


def test_the_most_common_finding_says_what_helps() -> None:
    """„Das Modell ist nicht geschlossen." — und dann?

    Es ist der häufigste Befund beim Einlesen eines heruntergeladenen Modells,
    und er sagte nur, was nicht stimmt. Regel 17 verlangt die Handlung dazu, und
    der Nachbar eine Zeile darüber im Quelltext nennt sie seit je („… hilft").

    Genannt wird die **Operation**, nicht der Menüweg: Dort stand „Netz →
    Dezimieren", und beides war falsch — das Menü heißt *Ändern*, die Operation
    *Dreiecke verringern*. Ein Weg im Text driftet, sobald jemand eine Kategorie
    verschiebt; ein Operationstitel ist derselbe String, den Menü, Palette und
    Kontextmenü zeigen. Deshalb prüft dieser Test gegen das Register: Wer eine
    Operation umbenennt, sieht hier, welcher Satz mitgeht.
    """
    from app.core.bootstrap import load_operations
    from app.core.ingest import loader
    from app.core.registry import REGISTRY

    load_operations()
    source = Path(loader.__file__).read_text(encoding="utf-8")

    for name in ("repair", "decimate_mesh"):
        title = str(REGISTRY.get(name).title)
        assert title in source, (
            f"kein Befund nennt {title!r} — heisst die Operation noch so, "
            "und steht der Satz noch dort?"
        )
    # Nur die Zeilen, die der Nutzer liest: Der Kommentar über dem Befund zitiert
    # den alten, falschen Weg absichtlich — er ist die Begründung.
    spoken = [line for line in source.splitlines() if not line.lstrip().startswith("#")]
    assert not any("Netz → Dezimieren" in line for line in spoken), (
        "der Menüweg im Text war falsch und driftet"
    )
