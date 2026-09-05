"""Die Eingangsstufe: sechs Schritte, eine Einheitenfrage, und harte
Importgrenzen (§17.1, §32).
"""

from __future__ import annotations

import struct
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshCodec, MeshData, read_mesh
from app.core.geom.transform import apply, translation
from app.core.ingest.loader import (
    MAX_FILE_BYTES,
    MAX_TRIANGLES,
    check_limits,
    detect_unit,
    normalise,
)
from app.core.ingest.ops import unit_question
from app.core.ingest.plan import import_plan
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import CachedResult, DiskCache
from app.core.scene.project import Project, ProjectSources, checksum, new_project
from app.core.types import Finding, Profile, Source
from app.core.units import UNIT_NAMES
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
        # Der Klarname („Zoll (in)") statt des Kürzels — der Kunde liest die
        # Frage, der Kern bekommt weiter das Kürzel (Review 02.09.2026).
        label = str(UNIT_NAMES.get(unit, unit))
        assert any(line.startswith(f"{label}:") for line in lines[1:]), unit
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


def test_removing_degenerate_faces_that_would_tear_the_mesh_open_is_taken_back() -> None:
    """Der Zwilling zum Verschweißen: Auch das Entfernen ist eine Reparatur.

    In einem geschlossenen Netz ist jedes Dreieck an zwei Kanten der einzige
    Nachbar — wer eines herausnimmt, reißt genau dort ein Loch, auch wenn es
    keine Fläche hat.

    Gefunden an einer TripoSG-Ausgabe: 221 138 Dreiecke, geschlossen; zwölf
    entartete entfernt, und danach standen zwanzig Kanten allein da. Der
    Prüfbericht meldete „Das Modell ist nicht geschlossen" über eine Datei,
    die es war; die Reparatur schloss vierzehn der zwanzig und meldete Erfolg;
    ihr Vorschlag „Kanten verfeinern" endete in „Erst reparieren, dann noch
    einmal". Vier Meldungen aus einer Ursache.

    Hier derselbe Fall in klein: ein Quader, dessen vierte Bodenecke auf der
    Diagonale zwischen ihren beiden Nachbarn liegt. Das eine Bodendreieck hat
    damit keine Fläche mehr, und die Topologie bleibt unberührt.
    """
    import numpy as np
    import trimesh

    corners = np.array(
        [
            [0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
            [10.0, 10.0, 0.0],
            [5.0, 5.0, 0.0],
            [0.0, 0.0, 10.0],
            [10.0, 0.0, 10.0],
            [10.0, 10.0, 10.0],
            [0.0, 10.0, 10.0],
        ]
    )
    faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 4, 5],
            [0, 5, 1],
            [1, 5, 6],
            [1, 6, 2],
            [2, 6, 7],
            [2, 7, 3],
            [3, 7, 4],
            [3, 4, 0],
        ]
    )
    body = trimesh.Trimesh(vertices=corners, faces=faces, process=False)
    assert body.is_watertight, "geschlossen, trotz des flachen Dreiecks"
    assert int(body.nondegenerate_faces(height=1e-9).sum()) == 11, "eines hat keine Fläche"

    result = normalise(MeshData.of(body), "mm")

    assert result.mesh.is_watertight, "und bleibt es"
    assert result.mesh.triangle_count == 12, "das flache Dreieck steht noch"
    assert result.info.removed_triangles == 0
    codes = {finding.code for finding in result.findings}
    assert "ingest.degenerate_kept" in codes
    assert "ingest.degenerate_removed" not in codes
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


def offset_cube(x: float, y: float, z: float) -> MeshData:
    """Der Korpuswürfel, aus der Mitte geschoben — so kommt ein Modell aus
    einem CAD-Programm herein, dessen Nullpunkt in einer Ecke liegt."""
    return apply(mesh_of("cube_clean.stl"), translation((x, y, z)))


def test_centring_puts_the_model_in_the_middle_of_the_bed() -> None:
    """Das Bett liegt um den Ursprung, also ist seine Mitte x = y = 0."""
    off = offset_cube(120.0, -35.0, 40.0)
    assert off.bounds.centre[0] == pytest.approx(120.0)

    centred = normalise(off, "mm", centre=True)
    assert centred.mesh.bounds.centre[0] == pytest.approx(0.0)
    assert centred.mesh.bounds.centre[1] == pytest.approx(0.0)


def test_centring_leaves_the_height_alone() -> None:
    """Mittig heißt seitlich mittig. Wer nicht aufsetzen lässt, bleibt in
    seiner Höhe — sonst tut ein Haken zwei Dinge."""
    centred = normalise(offset_cube(120.0, -35.0, 40.0), "mm", centre=True)
    assert centred.mesh.bounds.minimum[2] == pytest.approx(30.0)


def test_centring_and_placing_work_together() -> None:
    both = normalise(offset_cube(120.0, -35.0, 40.0), "mm", place_on_bed=True, centre=True)
    assert both.mesh.bounds.centre[0] == pytest.approx(0.0)
    assert both.mesh.bounds.centre[1] == pytest.approx(0.0)
    assert both.mesh.bounds.minimum[2] == pytest.approx(0.0)


def test_centring_is_offered_not_forced() -> None:
    """Die Gegenprobe: ohne Haken bleibt die Lage der Datei erhalten."""
    kept = normalise(offset_cube(120.0, -35.0, 40.0), "mm")
    assert kept.mesh.bounds.centre[0] == pytest.approx(120.0)
    assert kept.mesh.bounds.centre[1] == pytest.approx(-35.0)


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
    Dreiecken. Die Karten lehnten aber ab 120 000 ab und die Merkmalserkennung
    ab 200 000 (§31): Zwischen 200 000 und 500 000 war beides längst
    abgelehnt, und die Eingangsstufe schwieg dazu. Die Zahl hier ist deshalb
    keine eigene mehr, sondern die kleinere der beiden echten.

    **Und der Test darf nicht wissen, welche das ist.** Seine erste Fassung
    setzte die Kartengrenze als die kleinere ein und wurde am 04.09.2026 rot,
    als sie auf 900 000 stieg — über die Merkmalsgrenze. Rot war er zu Recht,
    aber aus dem falschen Grund: Nicht die Zusage hatte sich geändert, nur
    ihre Lage. Geprüft wird deshalb, was ``_too_fine`` selbst tut — die
    kleinere Grenze nennt ihre Ablehnung allein, die größere nennt beide —,
    und welche welche ist, leitet der Test ab.
    """
    from app.core.ingest import loader
    from app.core.perceive.maps import MAP_LIMIT_TRIANGLES
    from app.core.scene.evaluate import FEATURE_LIMIT_TRIANGLES

    kleiner = min(MAP_LIMIT_TRIANGLES, FEATURE_LIMIT_TRIANGLES)
    groesser = max(MAP_LIMIT_TRIANGLES, FEATURE_LIMIT_TRIANGLES)
    zuerst_die_karten = MAP_LIMIT_TRIANGLES < FEATURE_LIMIT_TRIANGLES

    assert kleiner == loader.HEAVY_TRIANGLES
    assert loader._too_fine(kleiner) is None, "an der Grenze ist noch alles möglich"

    dazwischen = loader._too_fine(kleiner + 1)
    assert dazwischen is not None and dazwischen.code == "ingest.very_large"
    laeuft_noch = "Merkmalserkennung" if zuerst_die_karten else "Analysekarten"
    assert laeuft_noch not in str(dazwischen.message), f"{laeuft_noch} läuft hier noch"
    assert "Dreiecke verringern" in str(dazwischen.message), "Regel 17: was jetzt hilft"

    darueber = loader._too_fine(groesser + 1)
    assert darueber is not None
    assert "Merkmalserkennung" in str(darueber.message), "und hier lehnt auch sie ab"
    assert "Analysekarten" in str(darueber.message), "und die Karten ebenso"
    assert darueber.values["triangles"] == groesser + 1


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
    from app.core.ingest import loader, plan, threemf

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


def test_a_3mf_with_too_many_archive_entries_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.ingest import loader

    monkeypatch.setattr(loader, "MAX_ARCHIVE_ENTRIES", 2, raising=False)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as container:
        for index in range(3):
            container.writestr(f"Metadata/{index}.txt", b"")
    payload = bytearray(buffer.getvalue())
    end_record = payload.rfind(b"PK\x05\x06")
    assert end_record >= 0
    # Die beiden angekündigten Anzahlen sind fremde Daten. Der Vorflug zählt
    # deshalb die tatsächlichen Verzeichniseinträge und glaubt nicht dieser 1.
    struct.pack_into("<HH", payload, end_record + 8, 1, 1)
    # ``ZipFile`` akzeptiert angehängte Bytes als Kommentar, auch wenn dessen
    # Längenfeld sie nicht nennt. Das darf den frühen Zähler nicht umgehen.
    payload.extend(b"nachlauf")

    def must_not_open(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("ZipFile materialisierte das übergroße Zentralverzeichnis")

    # PySide lädt beim Fixture-Abbau selbst ein ZIP. Deshalb muss die globale
    # Standardbibliothek noch innerhalb des Tests wiederhergestellt sein.
    with monkeypatch.context() as guarded:
        guarded.setattr(zipfile, "ZipFile", must_not_open)
        with pytest.raises(ValidationError) as refused:
            loader.check_unpacked(bytes(payload))

    assert refused.value.constraint == "file_too_large"
    assert refused.value.suggestions


def test_a_zip64_directory_cannot_hide_entries_from_the_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.ingest import loader

    monkeypatch.setattr(loader, "MAX_ARCHIVE_ENTRIES", 2, raising=False)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as container:
        for index in range(3):
            container.writestr(f"Metadata/{index}.txt", b"")
    payload = bytearray(buffer.getvalue())
    end_offset = payload.rfind(b"PK\x05\x06")
    assert end_offset >= 0
    end_record = struct.unpack_from("<4s4H2LH", payload, end_offset)
    directory_size = end_record[5]
    directory_offset = end_record[6]
    zip64_end = struct.pack(
        "<4sQ2H2L4Q",
        b"PK\x06\x06",
        44,
        45,
        45,
        0,
        0,
        3,
        3,
        directory_size,
        directory_offset,
    )
    zip64_locator = struct.pack("<4sLQL", b"PK\x06\x07", 0, end_offset, 1)
    payload[end_offset:end_offset] = zip64_end + zip64_locator
    classic_offset = end_offset + len(zip64_end) + len(zip64_locator)
    # Der Standardleser ersetzt diese absichtlich zu kleinen Werte durch die
    # drei Zähler aus ZIP64. Der Vorflug muss dasselbe tun.
    struct.pack_into("<HH", payload, classic_offset + 8, 1, 1)
    struct.pack_into("<L", payload, classic_offset + 12, 0xFFFFFFFF)
    with zipfile.ZipFile(BytesIO(payload)) as container:
        assert len(container.infolist()) == 3

    def must_not_open(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("ZipFile materialisierte das ZIP64-Zentralverzeichnis")

    with monkeypatch.context() as guarded:
        guarded.setattr(zipfile, "ZipFile", must_not_open)
        with pytest.raises(ValidationError) as refused:
            loader.check_unpacked(bytes(payload))

    assert refused.value.constraint == "file_too_large"
    assert refused.value.suggestions


def test_a_3mf_with_duplicate_archive_entries_is_refused() -> None:
    from app.core.ingest import loader

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as container:
        container.writestr("3D/3dmodel.model", b"first")
        with pytest.warns(UserWarning, match="Duplicate name"):
            container.writestr("3D/3dmodel.model", b"second")

    with pytest.raises(ValidationError) as refused:
        loader.check_unpacked(buffer.getvalue())

    assert refused.value.constraint == "invalid_archive"
    assert refused.value.suggestions


def test_a_3mf_with_an_extreme_compression_ratio_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.ingest import loader

    monkeypatch.setattr(loader, "MIN_RATIO_ENTRY_BYTES", 1, raising=False)
    monkeypatch.setattr(loader, "MAX_COMPRESSION_RATIO", 2.0, raising=False)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr("3D/3dmodel.model", bytes(10_000))

    with pytest.raises(ValidationError) as refused:
        loader.check_unpacked(buffer.getvalue())

    assert refused.value.constraint == "file_too_large"
    assert refused.value.suggestions


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


def test_the_first_model_of_a_project_lands_in_the_middle_of_the_bed() -> None:
    """§17.1, Schritt 6 — Entscheidung Robert, 03.09.2026.

    Ein frisches Projekt zeigt sein erstes Modell mittig auf der Platte statt
    dort, wo die Datei es hinlegt. Die Entscheidung steht in den Parametern der
    Operation und nicht in einem Zustand, den die nächste Auswertung anders
    vorfindet.
    """
    from app.core.ingest import plan

    first = plan.import_plan("src_1", "modell.stl", _stl(_cube()), first_model=True)
    assert first.draft.params["place_on_bed"] is True
    assert first.draft.params["centre"] is True


def test_a_further_model_keeps_its_place() -> None:
    """Die Gegenprobe, und der Grund für sie: Ein zweites Modell in die Mitte
    zu schieben legte es in das erste hinein. Dafür gibt es *Auf dem Bett
    anordnen* (§29)."""
    from app.core.ingest import plan

    later = plan.import_plan("src_1", "modell.stl", _stl(_cube()))
    assert "centre" not in later.draft.params
    assert "place_on_bed" not in later.draft.params


def test_only_a_mesh_is_placed_and_centred() -> None:
    """STEP und eine flache Zeichnung gehen andere Operationen; ihnen einen
    Parameter mitzugeben, den sie nicht kennen, wäre ein Planungsfehler."""
    from app.core.ingest import plan

    # Ein Kopf statt einer leeren Datei: Seit ``loader.check_readable``
    # ist eine Nutzlast ohne ein einziges Byte in jedem Format eine
    # Absage. Die Weiche entscheidet an der Endung und liest den Inhalt
    # nicht, die Aussage des Tests bleibt also dieselbe.
    for name, payload in (
        ("teil.step", b"ISO-10303-21;"),
        ("zeichnung.dxf", b"0 SECTION"),
        ("platte.svg", b"<svg/>"),
    ):
        draft = plan.import_plan("src_1", name, payload, first_model=True).draft
        assert draft.op != "load", name
        assert "centre" not in draft.params, name


def off_centre_stl() -> bytes:
    """Ein Quader, dessen Nullpunkt in einer Ecke liegt und der unter der
    Platte beginnt — die Lage, in der ein CAD-Export hereinkommt."""
    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    body.apply_translation((140.0, 60.0, -8.0))
    return bytes(body.export(file_type="stl"))


def test_the_window_actually_asks_for_the_first_model(qt_app: object) -> None:
    """Die Kette endet am letzten Glied: `import_plan` kann den Schalter
    kennen, und trotzdem setzt ihn niemand.

    Deshalb steht hier der Weg, den ein Kunde geht — Sitzung, Datei, Stapel —
    und nicht der Aufruf der Planfunktion. Geprüft werden die Parameter der
    Operation und nicht die Geometrie: Was der Schalter bewirkt, messen die
    Tests über `normalise` weiter oben.
    """
    from app.ui.session import Session

    session = Session()
    assert session.import_payload("ecke.stl", off_centre_stl(), unit="mm")

    first = session.history.operations[0]
    assert first.op == "load"
    assert first.params["place_on_bed"] is True
    assert first.params["centre"] is True


def test_a_second_model_is_not_dragged_into_the_first(qt_app: object) -> None:
    """Die Gegenprobe am selben Weg — und der Grund für sie steht in der
    Geometrie: Zentriert läge das zweite Modell im ersten."""
    from app.ui.session import Session

    session = Session()
    assert session.import_payload("ecke.stl", off_centre_stl(), unit="mm")
    assert session.import_payload("noch-eine.stl", off_centre_stl(), unit="mm")

    second = session.history.operations[-1]
    assert second.op == "load"
    assert second.params.get("centre") is not True
    assert second.params.get("place_on_bed") is not True


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


def test_an_assembly_is_centred_as_one_body(profile: Profile) -> None:
    """Und mittig gerückt wird sie ebenso **gemeinsam** (§17.1, Schritt 6).

    Derselbe Grund wie eine Zusicherung höher, andere Achse: Jeden Körper für
    sich zu zentrieren legte Gehäuse, Deckel und Tülle übereinander. Die Mitte
    ist die des gemeinsamen Hüllquaders, und was die Teile voneinander trennt,
    bleibt.
    """
    from app.core.export import threemf

    links = trimesh.creation.box((10.0, 10.0, 10.0))
    links.apply_translation((100.0, 50.0, 15.0))
    rechts = trimesh.creation.box((10.0, 10.0, 10.0))
    rechts.apply_translation((140.0, 50.0, 15.0))
    payload = threemf.write_assembly(
        [
            threemf.AssemblyPart(mesh=MeshData.of(links), name="Links"),
            threemf.AssemblyPart(mesh=MeshData.of(rechts), name="Rechts"),
        ]
    )
    project = _project_of(payload, "gruppe.3mf")
    history = History(project.document)
    history.apply(
        _("Laden"),
        [
            OperationDraft(
                op="load",
                params={"source": "src_1", "place_on_bed": True, "centre": True},
                produces=2,
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    erstes = result.scene.objects["obj_1"].mesh.bounds
    zweites = result.scene.objects["obj_2"].mesh.bounds
    # Die Gruppe reicht von x 95 bis 145, ihre Mitte liegt also bei 120.
    assert erstes.centre[0] == pytest.approx(-20.0), "gemeinsam gerückt, nicht jeder für sich"
    assert zweites.centre[0] == pytest.approx(20.0)
    assert erstes.centre[1] == pytest.approx(0.0), "auf der zweiten Achse ebenso"
    assert zweites.centre[1] == pytest.approx(0.0)
    assert zweites.centre[0] - erstes.centre[0] == pytest.approx(40.0), "der Abstand bleibt"
    assert erstes.minimum[2] == pytest.approx(0.0), "und die Gruppe steht auf der Platte"


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
    # Eine echte STL, keine leere Nutzlast: Seit der Eingangsprüfung
    # (``check_readable``) ist eine leere Datei eine Absage und kommt gar
    # nicht mehr bis zur Einheitenfrage. Die Aussage des Tests bleibt
    # dieselbe — ein STL nennt seine Einheit nie.
    assert import_plan("src_1", "teil.stl", _stl(_cube())).asks_unit, "ein STL sagt nie etwas"


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
        sha256=checksum((MESHES / "cube_clean.stl").read_bytes()),
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


def test_a_part_that_fills_the_bed_is_plausible_in_millimetres() -> None:
    """Die Obergrenze kennt den Bauraum (Durchsicht Einlesen/Export, 02.09.2026).

    Ein Teil, das ein 256er Bett füllt, hat 440 mm Diagonale — ohne Drucker
    fiel es in die Einheitenfrage, obwohl Millimeter die einzige sinnvolle
    Lesart sind. Mit Drucker reicht die Grenze bis zum Doppelten seiner
    Diagonale; ein kleiner Drucker senkt sie nie unter die Vorgabe.
    """
    from app.core.ingest.loader import PLAUSIBLE_MAX_MM, detect_unit, plausible_reach

    assert plausible_reach(None) == PLAUSIBLE_MAX_MM
    assert plausible_reach((80.0, 80.0, 80.0)) == PLAUSIBLE_MAX_MM, "nie unter die Vorgabe"
    reach = plausible_reach((256.0, 256.0, 256.0))
    assert reach == pytest.approx(2.0 * (3 * 256.0**2) ** 0.5)

    assert detect_unit(440.0).unit is None, "ohne Drucker bleibt die Frage"
    assert detect_unit(440.0, reach).unit == "mm"
    assert detect_unit(30.0, reach).unit is None, "30 mm oder 30 cm — die Frage bleibt"
    assert detect_unit(60.0, reach).unit == "mm", "60 cm wären zu groß, 60 mm nicht"
    assert detect_unit(2 * reach, reach).unit is None, "größer als der doppelte Drucker fragt"


# ---------------------------------------------------------------------
# Was ein Kunde wirklich auf der Platte hat: der abgebrochene Download,
# die umbenannte Datei, die Fehlerseite des Servers (03.09.2026).


# ---------------------------------------------------------------- Bausteine


def _stl(dreiecke: list) -> bytes:
    """Eine binäre STL, wie jedes Werkzeug sie schreibt."""
    teile = [b"\0" * 80, struct.pack("<I", len(dreiecke))]
    for ecken in dreiecke:
        teile.append(struct.pack("<3f", 0.0, 0.0, 1.0))
        for ecke in ecken:
            teile.append(struct.pack("<3f", *ecke))
        teile.append(struct.pack("<H", 0))
    return b"".join(teile)


def _cube(kante: float = 20.0) -> list:
    k = kante
    ecken = [
        (0, 0, 0),
        (k, 0, 0),
        (k, k, 0),
        (0, k, 0),
        (0, 0, k),
        (k, 0, k),
        (k, k, k),
        (0, k, k),
    ]
    flaechen = [
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    ]
    return [tuple(ecken[i] for i in f) for f in flaechen]


GOOD_STL = _stl(_cube())

#: Eine ASCII-STL — die zweite gültige Bauart, die nicht fallen darf.
ASCII_STL = (
    b"solid wuerfel\n"
    b"  facet normal 0 0 1\n    outer loop\n"
    b"      vertex 0 0 0\n      vertex 1 0 0\n      vertex 0 1 0\n"
    b"    endloop\n  endfacet\nendsolid wuerfel\n"
)


# ------------------------------------------------------------------- Absagen


@pytest.mark.parametrize(
    ("name", "payload", "constraint"),
    [
        # Der abgebrochene Download — die häufigste kaputte Datei überhaupt.
        ("leer.stl", b"", "file_empty"),
        # Halb geladen: Der Kopf nennt zwölf Dreiecke, es kam eines an.
        ("halb.stl", GOOD_STL[:84] + GOOD_STL[84:134], "file_truncated"),
        # Jemand hat eine Textdatei umbenannt.
        ("text.stl", b"Hallo, das ist keine STL.\n", "not_a_mesh"),
        # Der Server lieferte seine Fehlerseite statt des Modells.
        ("seite.stl", b"<!DOCTYPE html><html><body>404</body></html>\n", "not_a_mesh"),
        # Gültig aufgebaut, aber ohne Inhalt: Export ohne Auswahl.
        ("leer_gueltig.stl", _stl([]), "no_triangles"),
        # Eine 3MF ist ein Zip; was nicht mit PK beginnt, ist keines.
        ("kein_archiv.3mf", b"Das ist kein ZIP-Archiv.", "not_an_archive"),
    ],
)
def test_an_unusable_file_is_refused_before_it_reaches_the_stack(
    name: str, payload: bytes, constraint: str
) -> None:
    """Unbrauchbares wird abgewiesen, **bevor** es Operation und Quelle wird.

    Bis zum 03.09.2026 ging jede dieser sechs Dateien durch: Die Operation lag
    im Stapel, die Datei als eingebettete Quelle im Dokument, und gemeldet
    wurde es als Befund ohne einen einzigen Ausweg. ``_drop_source`` räumt nur
    auf, wenn eine ``AppError`` fliegt — hier flog keine.
    """
    with pytest.raises(ValidationError) as gefangen:
        import_plan("src_1", name, payload)
    assert gefangen.value.values.get("constraint", constraint) is not None
    # Regel 17: Der Satz sagt, was zu tun ist — nicht nur, was nicht geht.
    assert str(gefangen.value.detail)


# ------------------------------------------------------------------ Durchlass


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("cube.stl", GOOD_STL),
        # ASCII-STL: die zweite Bauart. Sie hat keine Längenrechnung.
        ("ascii.stl", ASCII_STL),
        # In Zoll gezeichnet — gültig, nur klein. Die Einheitenfrage kommt
        # später und ist nicht Sache dieser Prüfung.
        ("zoll.stl", _stl(_cube(0.7874))),
        # Zu groß für jede Platte — auch das ist eine gültige Datei.
        ("riesig.stl", _stl(_cube(4000.0))),
    ],
)
def test_a_valid_file_still_passes(name: str, payload: bytes) -> None:
    """Was gültig ist, bleibt gültig — auch die ungewöhnliche Bauart."""
    plan = import_plan("src_1", name, payload)
    assert plan.draft.op == "load"


def test_a_format_without_a_signature_is_not_judged() -> None:
    """STEP, OBJ und PLY haben keine Kennung, die ohne Parser prüfbar wäre.

    Sie dürfen deshalb nicht an dieser Prüfung scheitern — sonst schnitte sie
    den STEP-Weg ab, der drei Zeilen weiter unten in ``import_plan`` beginnt.
    Gemeldet von 3d-druck-c7 beim Durchfahren echter Kundendateien.
    """
    plan = import_plan("src_1", "teil.step", b"ISO-10303-21;\nHEADER;\n")
    assert plan.draft.op == "load_step"


def test_an_empty_file_is_refused_whatever_its_format() -> None:
    """Null Bytes sind in **jedem** Format nichts — auch in STEP."""
    for name in ("teil.step", "teil.obj", "teil.ply", "teil.3mf", "teil.stl"):
        with pytest.raises(ValidationError):
            import_plan("src_1", name, b"")


def test_no_file_of_the_corpus_is_refused() -> None:
    """**Der wichtigste Test dieser Datei.**

    Eine Eingangsprüfung, die ein gültiges Modell abweist, macht aus einem
    stillen Fehler einen lauten — und der ist schlimmer. Gemessen am
    03.09.2026 über 23 Dateien des Korpus, keine fiel; dazu sechzehn echte
    Kundendateien aus einem Durchlauf von 3d-druck-c7, darunter eine binäre
    STL, deren 80-Byte-Kopf mit ``ST`` beginnt und die eine Prüfung „fängt mit
    solid an" abgewiesen hätte.
    """
    korpus = Path(__file__).parent / "data"
    gefallen = []
    for pfad in sorted(korpus.rglob("*")):
        if not pfad.is_file() or pfad.suffix.lower() not in (".stl", ".3mf", ".obj", ".ply"):
            continue
        try:
            import_plan("src_1", pfad.name, pfad.read_bytes())
        except ValidationError as fehler:
            gefallen.append(f"{pfad.name}: {fehler}")
    assert not gefallen, f"gültige Dateien abgewiesen: {gefallen}"


def test_a_real_ascii_stl_from_a_foreign_tool_passes() -> None:
    """Die einzige ASCII-STL im Bestand, und sie kommt nicht von uns.

    **Warum eine gebaute hier nicht genügt.** Eine selbst erzeugte Datei
    enthält, was man hineinlegt — und genau daran ist die erste Fassung von
    ``check_readable`` vorbeigelaufen: Sie las die binäre Dreieckszahl aus den
    Bytes 80 bis 84, bevor feststand, ob die Datei überhaupt binär ist. Bei
    Text steht dort irgendein Wort.

    An dieser Datei ist das eine Zahl mit elf Stellen:

        n an Byte 80..84 = 221 523 232
        84 + 50n         = 11 076 161 684
        Datei            =         22 972

    Die erste Fassung hätte sie als „unvollständig" abgewiesen, weil
    ``len(payload) < expected`` überwältigend zutrifft. Der ASCII-Zweig
    verlässt den binären deshalb ganz.

    Erzeugt hat sie OpenSCAD 2021.01 (3d-druck-c7, 03.09.2026), nachdem
    gemessen war, dass PrusaSlicer 2.9.6 gar keine ASCII-STL schreiben kann —
    es kennt nur ``--export-stl`` (binär) und ``--export-obj``. Sie bringt
    deshalb eine fremde Zahlenschreibweise mit: ganze Zahlen ohne Dezimalpunkt
    und eine negative Null in der zweiten Normalen (``facet normal -1 -0 0``).
    """
    payload = (Path(__file__).parent / "data" / "meshes" / "openscad_ascii.stl").read_bytes()

    assert payload[:6] == b"solid ", "sonst prüft dieser Test die falsche Bauart"
    announced = struct.unpack("<I", payload[80:84])[0]
    assert 84 + 50 * announced > 1000 * len(payload), (
        "die binäre Rechnung muss hier grob danebenliegen — sonst belegt die "
        "Datei nicht, worum es geht"
    )

    plan = import_plan("src_1", "openscad_ascii.stl", payload)
    assert plan.draft.op == "load"


def test_a_finding_of_an_assembly_knows_which_body_it_belongs_to(profile: Profile) -> None:
    """Ein Befund einer Baugruppe trägt die Kennung seines Körpers.

    **Vorher trug er nur dessen Namen.** Die Auswertung setzt die Kennung
    nach, aber nur bei genau einer Ausgabe — bei mehreren wäre jede Zuordnung
    geraten (Regel 21). Eine 3MF mit acht Körpern bekam deshalb acht Befunde
    ohne Ziel, und *Dreiecke verringern* landete auf der zufällig gewählten
    Auswahl statt auf dem gemeinten Körper (gemessen von 3d-druck-7f am
    03.09.2026 an ``Wizard+Tower+Staunton+Elegoo.3mf``).

    Geraten wird trotzdem nichts: ``ingest.ops._named`` schreibt den Namen des
    Teils in ``values["object"]``, und die Auswertung kennt die Namen ihrer
    Ausgaben. Wo er genau eine trifft, ist die Zuordnung belegt.
    """
    from app.core.export import threemf

    unten = trimesh.creation.box((10.0, 10.0, 10.0))
    # Der zweite Körper ist offen — sonst meldet die Eingangsstufe über diese
    # Baugruppe gar nichts, und der Test prüfte eine leere Liste.
    oben = trimesh.creation.box((10.0, 10.0, 10.0))
    oben.apply_translation((0.0, 0.0, 20.0))
    oben.update_faces([index for index in range(len(oben.faces)) if index != 0])
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
        [OperationDraft(op="load", params={"source": "src_1"}, produces=2)],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    benannt = [
        entry
        for entry in result.scene.report.findings
        if entry.values.get("object") in ("Unten", "Oben")
    ]
    assert benannt, "ohne einen benannten Befund prüft dieser Test nichts"
    for entry in benannt:
        erwartet = "obj_1" if entry.values["object"] == "Unten" else "obj_2"
        assert entry.object_id == erwartet, (
            f"{entry.code} nennt {entry.values['object']}, zeigt aber auf {entry.object_id}"
        )


def test_two_bodies_of_the_same_name_stay_unassigned() -> None:
    """Wo der Name nicht eindeutig ist, wird nicht zugeordnet (Regel 21).

    **Über eine 3MF ist dieser Fall nicht herstellbar**, und das ist eine
    eigene Auskunft: Das Format macht gleichnamige Körper selbst eindeutig —
    aus zweimal „Gleich" werden beim Schreiben „Gleich 1" und „Gleich 2".
    Gemessen am 03.09.2026; der Versuch über ``write_assembly`` lieferte genau
    diese beiden Namen und damit zwei saubere Zuordnungen.

    Die Klausel gehört trotzdem zur Funktion und nicht zum Format: Ein anderer
    Weg in die Szene — ein Baustein, eine Operation, ein späteres Format —
    kann zwei Ausgaben desselben Namens erzeugen. Dann sind zwei Körper keine
    Zuordnung, sondern eine Wahl, und die trifft die Auswertung nicht.
    """
    from app.core.scene.evaluate import _by_name

    fund = Finding(
        code="ingest.not_watertight", severity="warning", message="x", values={"object": "Gleich"}
    )

    assert _by_name(fund, {"Gleich": "obj_1"}) == "obj_1", "eindeutig wird zugeordnet"
    assert _by_name(fund, {"Gleich": None}) is None, "mehrdeutig bleibt ohne Kennung"
    assert _by_name(fund, {"Anderer": "obj_1"}) is None, "ein fremder Name trifft nichts"

    ohne_namen = Finding(code="load.assembly", severity="info", message="x")
    assert _by_name(ohne_namen, {"Gleich": "obj_1"}) is None, "kein Name, keine Kennung"


def _await_signal(session: Any, *, seconds: int = 20) -> tuple[dict[str, Any], Any]:
    """Fährt den asynchronen Einleseweg zu Ende und sammelt, was er meldet.

    Ohne eine laufende Ereignisschleife stellt Qt die Signale des Arbeiters nie
    zu — der Test liefe ins Zeitlimit und sähe nichts. Das Zeitlimit hier ist
    die Notbremse, nicht der Normalfall.
    """
    from PySide6.QtCore import QEventLoop, QTimer

    gesehen: dict[str, Any] = {"fortschritt": []}
    loop = QEventLoop()
    session.importFinished.connect(lambda ok: gesehen.update(accepted=ok))
    session.importFailed.connect(lambda error: gesehen.update(error=error))
    session.progressChanged.connect(
        lambda anteil, text: gesehen["fortschritt"].append((anteil, text))
    )
    session.importFinished.connect(lambda _ok: loop.quit())
    session.importFailed.connect(lambda _error: loop.quit())
    QTimer.singleShot(seconds * 1000, loop.quit)

    def settle() -> None:
        """Wartet nur, wenn es etwas zu warten gibt.

        Unterhalb von ``PLAN_IN_WORKER_ABOVE`` läuft der Weg gerade durch, und
        das Signal kommt **vor** dieser Zeile. Eine Schleife, die dann noch
        startet, wartet auf etwas Vergangenes — und läuft ins Zeitlimit.
        """
        if "accepted" not in gesehen and "error" not in gesehen:
            loop.exec()

    return gesehen, settle


def test_a_model_is_read_without_blocking_the_window(
    qt_app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Einleseweg des Fensters läuft im Arbeiter, nicht im Hauptthread.

    **Warum es diesen zweiten Weg gibt.** ``import_plan`` klingt billig und ist
    es bei einer STL auch. Bei einer 3MF zählt es Körper und Dreiecke der
    ganzen Baugruppe, bevor eine Operation entsteht — der Stapel vergibt seine
    Objekt-IDs vorher (§11), und die Größengrenze greift vor dem Parsen (§32).
    Gemessen am 03.09.2026 an einer Datei von 63 MB mit 32 Körpern und
    5 476 596 Dreiecken: **0,09 s Lesen, 14,1 s Zählen.**

    Vierzehn Sekunden im Hauptthread sind kein Wartezeiger, sondern ein
    eingefrorenes Fenster; Windows schreibt ab etwa fünf Sekunden „Keine
    Rückmeldung" in die Titelleiste.
    """
    from app.ui import session as session_module
    from app.ui.session import Session

    modell = tmp_path / "wuerfel.stl"
    modell.write_bytes(_stl(_cube()))

    session = Session()
    # Die Grenze außer Kraft: Eine Testdatei von 684 Bytes bliebe sonst unter
    # ``PLAN_IN_WORKER_ABOVE`` und liefe gerade durch — geprüft würde dann der
    # andere Weg. Acht Megabyte in einem Test zu erzeugen wäre die Alternative
    # und kostete mehr, als sie belegt.
    monkeypatch.setattr(session_module, "PLAN_IN_WORKER_ABOVE", 0)
    gesehen, settle = _await_signal(session)
    session.import_model_async(modell)

    # **Die Zusicherung, die den Test scharf macht.** Ohne sie wäre er auch
    # grün, wenn alles wieder synchron liefe — er prüft ja nur das Ergebnis.
    # Der Aufruf kehrt zurück, bevor der Stapel steht: Der Plan entsteht im
    # Arbeiter, und ``_on_plan_ready`` läuft erst, wenn die Ereignisschleife
    # ihn zustellt.
    assert not session.project.document.ops, "der Aufruf darf nicht blockieren"

    settle()

    assert gesehen.get("error") is None, gesehen.get("error")
    assert gesehen.get("accepted") is True, "der Weg muss bis zum Ende laufen"
    assert [entry.op for entry in session.project.document.ops] == ["load"]


def test_a_broken_file_reports_instead_of_raising(qt_app: Any, tmp_path: Path) -> None:
    """Was der synchrone Weg wirft, meldet der asynchrone.

    Wer im Arbeiter plant, kann nicht in einen Aufrufer werfen, der längst
    zurückgekehrt ist — der ``try``/``except`` um ``import_model`` in
    ``open_path`` fängt hier nichts mehr. Der Fehler kommt über
    ``importFailed`` und wird dort gezeigt, wo er vorher auch stand.

    **Und die Quelle wird zurückgenommen.** Sonst bliebe sie als Waise im
    Dokument und wanderte mit dem nächsten Speichern in die Projektdatei; bei
    einer abgewiesenen Datei von 63 MB ist das nicht theoretisch.
    """
    from app.ui.session import Session

    kaputt = tmp_path / "halb.stl"
    ganz = _stl(_cube())
    kaputt.write_bytes(ganz[:84] + ganz[84:134])

    session = Session()
    gesehen, settle = _await_signal(session)
    session.import_model_async(kaputt)
    settle()

    assert gesehen.get("accepted") is None, "eine kaputte Datei darf nicht ankommen"
    assert gesehen.get("error") is not None, "und sie muss sich melden"
    assert not session.project.document.sources, "die Quelle wird zurückgenommen"
    assert not session.project.document.ops, "und keine Operation bleibt stehen"


def test_a_file_with_broken_coordinates_is_refused_instead_of_asked_about(
    profile: Profile,
) -> None:
    """Eine Datei ohne gültige Maße wird abgewiesen, nicht zur Frage gemacht.

    **Der Dialog zeigte „nan".** Eine STL mit einer NaN-Ecke ergibt eine
    Ausdehnung, die keine ist; die Einheitenerkennung findet dann nichts
    Plausibles und fragt — und die Frage listet zu jeder Antwort das Ergebnis
    auf, in diesem Fall mit „nan" in der ersten Spalte. Gemessen am
    03.09.2026 über den Weg des Fensters.

    ``_unit_for`` nennt die Regel in seinem eigenen Docstring: „Anhalten und
    fragen bleibt richtig — eine Frage, die niemand beantworten kann, ist aber
    nur die halbe Regel." Hier ist die Antwort keine Einheit, sondern eine
    kaputte Datei, und das gehört gesagt statt gefragt.
    """
    from app.core.scene import History, OperationDraft, evaluate

    # Ein Dreieck mit einer NaN-Ecke, dazu ein sauberer Würfel: Die Prüfung
    # geht über alle Teile, nicht über den größten — ``max`` über eine Folge
    # mit NaN wählt unvorhersehbar, weil jeder Vergleich mit NaN falsch ist.
    kaputt = [((0.0, 0.0, 0.0), (float("nan"), 0.0, 0.0), (0.0, 10.0, 0.0))]
    payload = _stl(kaputt + _cube())

    project = _project_of(payload, "kaputt.stl")
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert not result.complete, "eine Datei ohne gültige Maße darf nicht durchgehen"
    codes = {entry.code for entry in result.scene.report.findings}
    assert any("ValidationError" in code for code in codes), codes


def test_the_scan_counts_what_the_reader_would_return() -> None:
    """Der Scan zählt, was der Leser zurückgäbe — sein eigenes Versprechen.

    ``_scan`` sagt es im Docstring: „Die Körper werden über dieselben
    ``_objects_in``/``_parts_of`` gezählt wie beim Lesen, damit die Zahl
    garantiert die ist, die ``read_objects`` zurückgäbe." Geprüft hat das
    nichts — und die Zahl ist keine Nebensache: Der Stapel vergibt daraus seine
    Objekt-IDs, **bevor** irgendetwas gerechnet ist (§11). Eine zu große Zahl
    hält die Auswertung mit ``evaluate.object_count`` an, und aus einer Datei
    mit einem lesbaren Körper wird ein Import, der gar nichts einliest.

    **Gefunden über eine Mutation, die grün blieb** (03.09.2026): Nimmt man
    dem Zähllauf das Attribut, mit dem er die Größe der geleerten Sammelknoten
    festhält, liefert ``scan_assembly`` für ``colored.3mf`` **(0, 20)** statt
    (1, 20) — null Körper. Fünfundachtzig Tests liefen weiter grün, weil keiner
    die Körperzahl des Scans je gegen den Leser gehalten hat.
    """
    from app.core.ingest import threemf

    payload = (MESHES / "colored.3mf").read_bytes()

    bodies, triangles = threemf.scan_assembly(payload)
    parts = threemf.read_objects(payload)

    assert bodies == len(parts), (
        f"der Scan zählt {bodies} Körper, der Leser gibt {len(parts)} zurück"
    )
    assert triangles == sum(part.mesh.triangle_count for part in parts), (
        "und dieselbe Zusage gilt für die Dreiecke — an ihnen hängt die Größengrenze"
    )
    assert bodies > 0, "ohne einen Körper prüft dieser Test nichts"


def test_a_late_import_failure_leaves_the_next_project_alone(
    qt_app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesamtreview 05.09.2026, UI-01: Der Planarbeiter meldete Erfolg oder
    Fehler ohne Bindung an das Projekt, für das er lief. Ein neues Projekt
    trägt wieder eine eigene ``src_1`` — und der verspätete Fehler des alten
    Imports räumte genau diese Quelle aus dem **neuen** Dokument, samt
    Nutzdaten. Jede Meldung trägt seither den Stempel ihres Dokuments."""
    from app.ui import session as session_module
    from app.ui.session import Session

    kaputt = tmp_path / "halb.stl"
    ganz = _stl(_cube())
    kaputt.write_bytes(ganz[:84] + ganz[84:134])

    session = Session()
    monkeypatch.setattr(session_module, "PLAN_IN_WORKER_ABOVE", 0)
    gesehen, settle = _await_signal(session)
    session.import_model_async(kaputt)
    assert list(session.project.document.sources) == ["src_1"], "der alte Import trägt src_1"

    # Bevor der Arbeiter antwortet: ein neues Projekt mit einer eigenen src_1.
    session.start_new("centauri-carbon-2", "petg")
    own = session._embed_source("import", "eigenes.stl", ganz)
    assert own == "src_1", "das neue Projekt vergibt dieselbe Kennung"

    settle()

    assert "src_1" in session.project.document.sources, "die Quelle des neuen Projekts bleibt"
    assert session.project.sources["src_1"] == ganz, "samt Nutzdaten"
    assert gesehen.get("error") is None, "der alte Fehler gilt dem neuen Projekt nicht"


def test_the_cleanup_keeps_the_filament_slots_of_the_remaining_triangles() -> None:
    """B-05 aus dem Gesamtreview vom 05.09.2026: Beim Entfernen entarteter
    und doppelter Dreiecke wurden die Slots nicht mitgeführt; ``replacing``
    ließ sie bei abweichender Dreieckszahl ganz fallen, und ein rot-blauer
    Würfel mit einem doppelten Dreieck kam einfarbig an."""
    import numpy as np
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.ingest.loader import normalise

    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    faces = np.vstack([box.faces, box.faces[:1]])  # das erste Dreieck noch einmal
    doubled = trimesh.Trimesh(vertices=box.vertices, faces=faces, process=False)
    slots = (*(0 if index < 6 else 1 for index in range(12)), 0)
    mesh = MeshData(raw=doubled, slots=slots)

    result = normalise(mesh, "mm")

    assert result.mesh.triangle_count == 12, "das Duplikat ist weg"
    assert len(result.mesh.slots) == 12, "die Slots reisen mit"
    assert sorted(set(result.mesh.slots)) == [0, 1], "beide Farben bleiben"
    assert result.info.removed_triangles == 1


def test_cancelling_during_the_import_plan_keeps_the_file_out(
    qt_app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesamtreview 05.09.2026, UI-08: Der Abbrechen-Knopf setzte das Signal,
    der fertige Plan wurde trotzdem angewandt, und die Auswertung danach
    setzte das Signal still zurück — das Objekt stand, das Dokument war
    geändert. Ein abgebrochener Plan verwirft seine Quelle."""
    from app.ui import session as session_module
    from app.ui.session import Session

    modell = tmp_path / "wuerfel.stl"
    modell.write_bytes(_stl(_cube()))
    session = Session()
    monkeypatch.setattr(session_module, "PLAN_IN_WORKER_ABOVE", 0)
    gesehen, settle = _await_signal(session)

    session.import_model_async(modell)
    session.cancel_evaluation()
    settle()

    assert gesehen.get("error") is None, gesehen.get("error")
    assert gesehen.get("accepted") is False, "abgebrochen heißt nicht übernommen"
    assert not session.project.document.ops, "kein Ladeschritt"
    assert not session.project.sources, "und die Quelle ist wieder draußen"
    assert not session.cancel_signal.is_cancelled, "das Signal ist verbraucht"


def test_an_unsaveable_document_says_so_instead_of_raising(tmp_path: Path) -> None:
    """Gesamtreview 05.09.2026, UI-26: Ein nicht endlicher Wert im Dokument
    ließ ``save`` einen nackten ValueError werfen, und der Speichern-Slot
    fängt nur AppError — keine Datei, keine Meldung."""
    from app.core.errors import AppError
    from app.core.types import Parameter
    from app.ui.session import Session

    session = Session()
    session.project.document.parameters["hoehe"] = Parameter(name="hoehe", value=float("inf"))

    with pytest.raises(AppError) as raised:
        session.save_project(tmp_path / "projekt.p3d")

    assert raised.value.suggestions, "Regel 17: ein Fehler endet nie ohne Vorschlag"
    assert not (tmp_path / "projekt.p3d").exists()
