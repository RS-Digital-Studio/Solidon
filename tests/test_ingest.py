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
from app.core.ingest.plan import import_plan, is_only_imported
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
    # Stehen gelassen ist keine Zeile im Bericht (Bedienweg A4): Geschehen
    # ist nichts, und der Kunde kann nichts tun. ``info.welded`` sagt es.
    assert "ingest.weld_skipped" not in codes
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
    assert "ingest.degenerate_kept" not in codes, "stehen gelassen ist keine Zeile (A4)"
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


def test_reading_an_stl_is_not_a_finding() -> None:
    """„Doppelte Punkte wurden verschweißt." stand bei jedem sauberen STL-Import
    als erste Zeile des Prüfberichts — sechs von sechs Modellen, ohne Handlung
    (Bedienweg-Durchsicht 14.09.2026). Eine STL speichert jedes Dreieck mit
    eigenen Ecken; sie zu verschweißen ist Lesen, keine Reparatur. Bei einem
    Format mit Punktliste bleibt der Befund: Dort sind doppelte Punkte eine
    Eigenschaft der Datei.
    """
    read = normalise(mesh_of("cube_clean.stl"), "mm", weld_is_reading=True)
    assert read.info.welded and read.mesh.vertex_count == 8, "verschweißt wird weiter"
    assert "ingest.welded" not in {finding.code for finding in read.findings}

    listed = normalise(mesh_of("cube_clean.stl"), "mm")
    assert "ingest.welded" in {finding.code for finding in listed.findings}


def test_an_open_model_is_repaired_on_import() -> None:
    """**Der Import schließt, was zu schließen ist** (Entscheidung Robert,
    22.09.2026: „am besten beim Import", „alles bei der Reparatur beheben").

    Bis dahin stand hier „nicht geschlossen, ‚Reparieren' schließt die offenen
    Stellen" — ein Hinweis auf einen Knopf, den der Kunde erst finden musste,
    und ein Modell, das bis dahin nicht druckbar war. Gemessen am Korpus
    ``F:\\3D Dateien`` (171 Dateien, 484 Körper): 118 Körper kamen offen herein
    und gehen geschlossen heraus, keiner bleibt offen.

    ``broken_open.stl`` fehlen drei Flächen — eine fehlende Wand. Auch sie
    wird geschlossen, und weil dort eine Fläche entsteht, die im Modell nicht
    war, steht eine Warnung daneben.
    """
    result = normalise(mesh_of("broken_open.stl"), "mm")

    assert result.mesh.is_watertight, "der Körper kommt geschlossen aus dem Import"
    codes = {finding.code for finding in result.findings}
    assert "ingest.not_watertight" not in codes
    assert "repair.holes_filled" in codes, "und der Bericht sagt, was geschlossen wurde"
    wide = next(f for f in result.findings if f.code == "repair.wide_hole_filled")
    assert wide.severity == "warning"


def test_an_open_model_turned_inside_out_comes_in_facing_outward() -> None:
    """Erst am geschlossenen Netz lässt sich fragen, wo außen ist.

    Das Angleichen der Außenseiten sieht ein offenes Netz; ist es durchweg
    gleich herum gewickelt, nur eben innen-außen verkehrt, gibt es nichts zu
    richten, und das Vorzeichen des Volumens trägt an einem offenen Körper
    keine Aussage. Danach schloss das Lochfüllen das Netz in der Wicklung
    seiner Nachbarn — und der Würfel kam geschlossen und umgestülpt aus dem
    Import, Volumen −8 000 mm³ (Durchsicht 24.09.2026). Das Schließen fragt
    seither selbst nach außen.
    """
    import numpy as np

    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).subdivide()
    body.invert()
    keep = np.ones(len(body.faces), dtype=bool)
    keep[0] = False
    body.update_faces(keep)
    body.remove_unreferenced_vertices()
    assert body.is_winding_consistent and not body.is_watertight

    result = normalise(MeshData.of(body), "mm")

    assert result.mesh.is_watertight
    assert result.mesh.raw.volume == pytest.approx(8000.0, rel=1e-9)
    codes = [finding.code for finding in result.findings]
    assert codes.count("repair.normals_flipped") + codes.count("ingest.normals_flipped") == 1, (
        "eine Zeile für die Außenseiten, auch wenn beide Stufen richten"
    )


def test_closing_on_import_leaves_the_outsides_alone_when_asked_to() -> None:
    """*Außenseiten angleichen: aus* gilt auch für das Schließen in Schritt 4b (Review R8)."""
    import numpy as np

    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).subdivide()
    body.invert()
    keep = np.ones(len(body.faces), dtype=bool)
    keep[0] = False
    body.update_faces(keep)
    body.remove_unreferenced_vertices()

    result = normalise(MeshData.of(body), "mm", unify_normals=False)

    codes = {finding.code for finding in result.findings}
    assert "repair.normals_flipped" not in codes and "ingest.normals_flipped" not in codes
    assert result.mesh.raw.volume < 0.0, "verkehrt, wie angefordert"


def test_the_place_of_a_finding_moves_with_an_assembly_set_on_the_bed() -> None:
    """Eine Baugruppe geht gemeinsam aufs Bett — und der Ort ihrer Befunde mit ihr.

    Das Nachführen stand nur im Weg eines einzelnen Körpers; an einer 3MF mit
    großer Öffnung zeigte der Klick danach ins Leere (Review R7, 24.09.2026).
    """
    from app.core.ingest.ops import _group_on_bed
    from app.core.types import SceneObject

    first = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    first.apply_translation((100.0, 100.0, 50.0))
    second = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    second.apply_translation((120.0, 100.0, 50.0))
    outputs = [
        SceneObject(id="", name="eins", mesh=MeshData.of(first)),
        SceneObject(id="", name="zwei", mesh=MeshData.of(second)),
    ]
    findings = [
        Finding(
            code="repair.wide_hole_filled",
            severity="warning",
            message="",
            location=(100.0, 100.0, 55.0),
            outline=(((95.0, 95.0, 55.0), (105.0, 95.0, 55.0)),),
        )
    ]

    moved = _group_on_bed(outputs, findings, place_on_bed=True, centre=False)

    low = moved[0].mesh.bounds.minimum
    assert low[2] == pytest.approx(0.0)
    # Die Oberseite des ersten Würfels, wo die Öffnung war, liegt jetzt bei 10.
    assert findings[0].location == pytest.approx((100.0, 100.0, 10.0))
    # Und ihr Rand mit ihr — *Stelle zeigen* umrandet die neue Fläche dort, wo sie liegt.
    ((first_end, second_end),) = findings[0].outline
    assert first_end == pytest.approx((95.0, 95.0, 10.0))
    assert second_end == pytest.approx((105.0, 95.0, 10.0))


def test_closing_holes_on_import_stops_when_asked_to() -> None:
    """Das Schließen beim Einlesen fragt den Abbruch (§15.6, Review R10, 24.09.2026).

    Schritt 4b fährt die ganze Füllkette der Reparatur; vorher kannte
    ``normalise`` kein Abbruchsignal, und *Abbrechen* griff erst danach.
    """
    import numpy as np

    from app.core.errors import OperationCancelled

    class Signal:
        """Meldet den Abbruch ab der zweiten Frage — mitten im Schließen."""

        asked = 0

        def raise_if_cancelled(self) -> None:
            self.asked += 1
            if self.asked > 1:
                raise OperationCancelled()

    sphere = trimesh.creation.icosphere(subdivisions=4, radius=20.0)
    keep = np.ones(len(sphere.faces), dtype=bool)
    keep[::40] = False
    sphere.update_faces(keep)
    signal = Signal()

    with pytest.raises(OperationCancelled):
        normalise(MeshData.of(sphere), "mm", cancelled=signal)  # type: ignore[arg-type]
    assert signal.asked >= 2


def test_a_part_inside_a_part_is_named_on_import_where_it_now_is() -> None:
    """Der Import sagt es wie die Reparatur — und der Ort folgt dem Aufsetzen."""
    inner = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    inner.apply_translation((2.0, 1.0, 0.5))
    both = trimesh.util.concatenate([trimesh.creation.box(extents=(20.0, 20.0, 20.0)), inner])

    result = normalise(MeshData.of(both), "mm", place_on_bed=True)

    inside = [entry for entry in result.findings if entry.code == "repair.part_inside"]
    assert len(inside) == 1
    # Aufgesetzt steht die Außenschale mit ihrer Unterseite auf null, die
    # Mitte der Innenschale also 10 mm höher als in der Datei.
    assert float(result.mesh.raw.bounds[0][2]) == pytest.approx(0.0)
    assert inside[0].location == pytest.approx((2.0, 1.0, 10.5))


def test_the_place_of_a_wide_opening_moves_with_the_body() -> None:
    """Der Klick auf „große Öffnung" fliegt dorthin, wo die Öffnung jetzt ist.

    Das Schließen misst den Ort am Körper, wie er aus der Datei kam; das
    Aufsetzen auf das Bett schiebt ihn danach. Ohne Nachführen zeigte die
    Marke um die Höhe des Aufsetzens neben die Stelle.
    """
    kept = normalise(mesh_of("broken_open.stl"), "mm")
    placed = normalise(mesh_of("broken_open.stl"), "mm", place_on_bed=True)

    def wide_at(result: Any) -> tuple[float, float, float]:
        finding = next(f for f in result.findings if f.code == "repair.wide_hole_filled")
        assert finding.location is not None
        return finding.location

    shift = placed.mesh.bounds.minimum[2] - kept.mesh.bounds.minimum[2]
    assert shift == pytest.approx(10.0), "sonst prüft der Test nichts"
    assert wide_at(placed)[2] - wide_at(kept)[2] == pytest.approx(shift)
    assert wide_at(placed)[:2] == pytest.approx(wide_at(kept)[:2])


def test_mending_on_import_can_be_left_out() -> None:
    """„Offene Stellen schließen" aus: Das Modell kommt, wie es ist, und der
    Bericht sagt, dass es offen ist (Entscheidung Robert, 24.09.2026 — der
    Rückweg zu „Offen lassen")."""
    result = normalise(mesh_of("broken_open.stl"), "mm", mend=False)

    assert not result.mesh.is_watertight
    codes = {finding.code for finding in result.findings}
    assert "ingest.not_watertight" in codes
    assert "repair.holes_filled" not in codes
    assert "repair.wide_hole_filled" not in codes


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
    ihre Lage. Geprüft wird deshalb, was ``_too_fine`` selbst tut, und welche
    Grenze die kleinere ist, leitet der Test ab.

    **Über die Erkennung sagt der Satz nichts mehr** (24.09.2026). Bis zur
    bestätigbaren Grenze entscheidet die Frage beim Laden, darüber meldet
    ``perceive.too_large`` am Körper, was ausgelassen wurde; ein zweiter Satz
    darüber stand mit denselben Knöpfen darunter.
    """
    from app.core.ingest import loader
    from app.core.perceive.local import CONFIRMED_FEATURE_LIMIT_TRIANGLES
    from app.core.perceive.maps import MAP_LIMIT_TRIANGLES
    from app.core.scene.evaluate import FEATURE_LIMIT_TRIANGLES

    kleiner = min(MAP_LIMIT_TRIANGLES, FEATURE_LIMIT_TRIANGLES)
    zuerst_die_karten = MAP_LIMIT_TRIANGLES < FEATURE_LIMIT_TRIANGLES

    assert kleiner == loader.HEAVY_TRIANGLES
    assert loader._too_fine(kleiner) is None, "an der Grenze ist noch alles möglich"

    dazwischen = loader._too_fine(kleiner + 1)
    assert dazwischen is not None and dazwischen.code == "ingest.very_large"
    laeuft_noch = "Merkmalserkennung" if zuerst_die_karten else "Analysekarten"
    assert laeuft_noch not in str(dazwischen.message), f"{laeuft_noch} läuft hier noch"
    assert "Dreiecke verringern" in str(dazwischen.message), "Regel 17: was jetzt hilft"

    for triangles in (FEATURE_LIMIT_TRIANGLES + 1, CONFIRMED_FEATURE_LIMIT_TRIANGLES + 1):
        darueber = loader._too_fine(triangles)
        assert darueber is not None
        assert darueber.message == dazwischen.message, "ein Satz für die Karten, keiner mehr"
        assert darueber.values["triangles"] == triangles


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


def _duplicate_archive(first: bytes, second: bytes) -> bytes:
    """Zwei gleich benannte ZIP-Einträge, beide tatsächlich im Archiv."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as container:
        container.writestr("3D/relief.svg", first)
        with pytest.warns(UserWarning, match="Duplicate name"):
            container.writestr("3D/relief.svg", second, compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def test_identical_3mf_entries_load_without_changing_the_source() -> None:
    """Elegoo schreibt dasselbe SVG-Relief mehrfach in ein gültiges Modell."""
    from app.core.export.threemf import write
    from app.core.ingest.threemf import read_objects

    source = BytesIO(write(mesh_of("cube_clean.stl"), name="Würfel"))
    with zipfile.ZipFile(source, "a") as container:
        container.writestr("3D/relief.svg", b'<svg width="10"/>')
        with pytest.warns(UserWarning, match="Duplicate name"):
            container.writestr("3D/relief.svg", b'<svg width="10"/>')
    payload = source.getvalue()
    before = checksum(payload)
    plan = import_plan("src_1", "relief.3mf", payload)
    bodies = read_objects(payload)
    assert plan.draft.produces == 1
    assert len(bodies) == 1
    assert bodies[0].mesh.bounds.size == pytest.approx(mesh_of("cube_clean.stl").bounds.size)
    assert bodies[0].mesh.volume == pytest.approx(mesh_of("cube_clean.stl").volume)
    assert checksum(payload) == before


def test_identical_entries_may_use_different_compression() -> None:
    from app.core.ingest.loader import check_unpacked

    check_unpacked(_duplicate_archive(b"same content", b"same content"))


def test_equal_crc_and_size_do_not_prove_identical_entries() -> None:
    """Diese beiden verschiedenen Wörter haben dieselbe ZIP-Prüfsumme."""
    from app.core.ingest.loader import check_unpacked

    payload = _duplicate_archive(b"plumless", b"buckeroo")
    with zipfile.ZipFile(BytesIO(payload)) as container:
        first, second = container.infolist()
        assert first.CRC == second.CRC and first.file_size == second.file_size
    with pytest.raises(ValidationError) as refused:
        check_unpacked(payload)
    assert refused.value.constraint == "invalid_archive"
    assert refused.value.suggestions


@pytest.mark.parametrize("limit", ["MAX_FILE_BYTES", "MAX_ARCHIVE_ENTRIES"])
def test_duplicate_entries_count_towards_limits_before_comparing_content(
    limit: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.ingest import loader

    payload = _duplicate_archive(b"12345678", b"12345678")
    monkeypatch.setattr(loader, limit, 15 if limit == "MAX_FILE_BYTES" else 1)

    def must_not_read(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("archive limits must precede content comparison")

    with monkeypatch.context() as guarded:
        guarded.setattr(zipfile.ZipFile, "open", must_not_read)
        with pytest.raises(ValidationError) as refused:
            loader.check_unpacked(payload)
    assert refused.value.constraint == "file_too_large"


@pytest.mark.parametrize("compressed", [False, True])
def test_a_damaged_duplicate_is_not_treated_as_identical(compressed: bool) -> None:
    from app.core.ingest.loader import check_unpacked

    payload = bytearray(_duplicate_archive(b"same content", b"same content"))
    with zipfile.ZipFile(BytesIO(payload)) as container:
        info = container.infolist()[int(compressed)]
    offset = info.header_offset + 30 + len(info.filename.encode())
    # Typ 3 ist im Deflate-Blockkopf ungültig; beim gespeicherten Inhalt
    # greift stattdessen der CRC-Vergleich des ZIP-Lesers.
    payload[offset] = (payload[offset] & ~7) | 7
    with pytest.raises(ValidationError) as refused:
        check_unpacked(bytes(payload))
    assert refused.value.constraint == "invalid_archive"


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


def test_a_further_model_is_planned_for_a_free_place() -> None:
    """Die Gegenprobe zum ersten Modell (§17.1, Schritt 6; Robert, 28.09.2026).

    In die Mitte geschoben läge ein zweites Modell im ersten; an seinen
    Dateikoordinaten lag es meist außerhalb, obwohl auf den Platten Platz war.
    Es kommt aufgesetzt an die erste freie Stelle — und auch das steht als
    Parameter in der Operation.
    """
    from app.core.ingest import plan

    later = plan.import_plan("src_1", "modell.stl", _stl(_cube()), first_model=False)
    assert "centre" not in later.draft.params
    assert later.draft.params["place_on_bed"] is True
    assert later.draft.params["free_spot"] is True
    first = plan.import_plan("src_1", "modell.stl", _stl(_cube()), first_model=True)
    assert "free_spot" not in first.draft.params, "das erste bleibt mittig"
    undecided = plan.import_plan("src_1", "modell.stl", _stl(_cube()))
    assert not {"place_on_bed", "centre", "free_spot"} & set(undecided.draft.params), (
        "ohne Angabe des Aufrufers bleibt die Lage der Datei"
    )


def test_only_a_mesh_is_placed_and_centred() -> None:
    """Eine flache Zeichnung geht eine andere Operation; ihr einen Parameter
    mitzugeben, den sie nicht kennt, wäre ein Planungsfehler.

    STEP stand hier bis P7.4 mit dabei. Seit dem Baugruppenimport trägt
    ``load_step`` dieselben zwei Haken wie ``load`` — §17.1 Schritt 6 gilt für
    jedes erste Modell —, und der Plan liest die Datei, um ihre Körper zu
    zählen; das prüft ``tests/test_step_assembly.py``.
    """
    from app.core.ingest import plan

    # Ein Kopf statt einer leeren Datei: Seit ``loader.check_readable``
    # ist eine Nutzlast ohne ein einziges Byte in jedem Format eine
    # Absage. Die Weiche entscheidet an der Endung und liest den Inhalt
    # nicht, die Aussage des Tests bleibt also dieselbe.
    for name, payload in (
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
    Geometrie: Zentriert läge das zweite Modell im ersten. Es geht an eine
    freie Stelle (Robert, 28.09.2026)."""
    from app.ui.session import Session

    session = Session()
    assert session.import_payload("ecke.stl", off_centre_stl(), unit="mm")
    assert session.import_payload("noch-eine.stl", off_centre_stl(), unit="mm")

    second = session.history.operations[-1]
    assert second.op == "load"
    assert second.params.get("centre") is not True
    assert second.params.get("place_on_bed") is True
    assert second.params.get("free_spot") is True


# --- weitere Modelle an eine freie Stelle (Robert, 28.09.2026) --------------------


def _box_stl(width: float, depth: float, height: float) -> bytes:
    """Ein Quader um den Ursprung, wie eine heruntergeladene Datei ihn bringt."""
    body = trimesh.creation.box(extents=(width, depth, height))
    return bytes(body.export(file_type="stl"))


def _imported_in_turn(profile: Profile, *files: tuple[str, bytes]) -> Any:
    """Die Dateien nacheinander über den Einlesplan — wie Fenster und Kommandozeile."""
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    for number, (name, payload) in enumerate(files, start=1):
        key = f"src_{number}"
        project.document.sources[key] = Source(
            id=key, kind="import", path=f"sources/{name}", sha256=""
        )
        project.sources[key] = payload
        chosen = import_plan(key, name, payload, "mm", first_model=not project.document.ops)
        history.apply(chosen.title, [chosen.draft])
    return project, history


def _scene(project: Project, profile: Profile, **options: Any) -> Any:
    result = evaluate(project.document, profile, sources=ProjectSources(project), **options)
    assert result.complete, [entry.values for entry in result.scene.report.findings]
    return result


def _apart(one: Any, other: Any, spacing: float) -> bool:
    """Halten zwei Körper in der Aufsicht den Abstand — in irgendeiner Richtung?"""
    a, b = one.mesh.bounds, other.mesh.bounds
    return bool(
        a.maximum[0] + spacing <= b.minimum[0] + 1e-6
        or b.maximum[0] + spacing <= a.minimum[0] + 1e-6
        or a.maximum[1] + spacing <= b.minimum[1] + 1e-6
        or b.maximum[1] + spacing <= a.minimum[1] + 1e-6
    )


def test_a_further_model_lands_in_a_free_place_on_the_first_plate(profile: Profile) -> None:
    """Zwei Würfel aus ``cube_clean.stl``: Der erste liegt mittig, der zweite
    kommt auf dieselbe Platte an die erste freie Stelle — hinten links, wie
    *Auf dem Bett anordnen* (§29) —, ganz auf der Druckfläche, im Abstand der
    Anordnung und aufgesetzt. Der erste bleibt, wo er war.
    """
    from app.core.build_area import fits_on_bed
    from app.core.geom.prepare import ARRANGE_SPACING

    cube = (MESHES / "cube_clean.stl").read_bytes()
    project, _history = _imported_in_turn(profile, ("erster.stl", cube), ("zweiter.stl", cube))

    result = _scene(project, profile)
    first, second = result.scene.objects["obj_1"], result.scene.objects["obj_2"]
    assert first.mesh.bounds.centre[:2] == pytest.approx((0.0, 0.0)), "der erste bleibt"
    assert (first.plate, second.plate) == (0, 0), "Platz war auf der ersten Platte"
    assert fits_on_bed(second.mesh, profile.printer), "ganz auf der Druckfläche"
    assert second.mesh.bounds.minimum[2] == pytest.approx(0.0), "aufgesetzt"
    assert _apart(first, second, ARRANGE_SPACING), "und mit dem Abstand der Anordnung"
    # Die hinterste, dann linkeste Stelle der Fläche mit Rand (-123 … 123).
    assert second.mesh.bounds.minimum[0] == pytest.approx(-123.0)
    assert second.mesh.bounds.maximum[1] == pytest.approx(123.0)
    codes = {entry.code for entry in result.scene.report.findings}
    assert "arrange.free_spot" in codes, "und der Bericht sagt, wo es hinkam"


def test_a_further_model_goes_to_the_next_plate_when_the_first_is_full(
    profile: Profile,
) -> None:
    """Eine Platte von 230 mm auf dem 256er Bett lässt keinen Platz: Der Würfel
    kommt auf die nächste, dort mittig, weil sie leer ist; der dritte legt sich
    auf dieser zweiten Platte neben ihn, nicht in ihn."""
    from app.core.build_area import fits_on_bed
    from app.core.geom.prepare import ARRANGE_SPACING

    cube = (MESHES / "cube_clean.stl").read_bytes()
    project, _history = _imported_in_turn(
        profile,
        ("platte.stl", _box_stl(230.0, 230.0, 4.0)),
        ("erster.stl", cube),
        ("zweiter.stl", cube),
    )

    result = _scene(project, profile)
    plate, first, second = (result.scene.objects[key] for key in ("obj_1", "obj_2", "obj_3"))
    assert [entry.plate for entry in (plate, first, second)] == [0, 1, 1]
    assert fits_on_bed(first.mesh, profile.printer)
    assert fits_on_bed(second.mesh, profile.printer)
    assert first.mesh.bounds.centre[:2] == pytest.approx((0.0, 0.0)), "eine leere Platte: mittig"
    assert _apart(first, second, ARRANGE_SPACING), "der dritte nicht im zweiten"
    assert plate.mesh.bounds.centre[:2] == pytest.approx((0.0, 0.0)), "die Platte bleibt liegen"


def test_an_assembly_as_further_model_moves_as_one(profile: Profile) -> None:
    """Eine 3MF-Baugruppe als weiteres Modell: alle Körper auf einmal, an eine
    freie Stelle, die Teile behalten ihre Lage zueinander (§17.1, Schritt 6)."""
    from app.core.build_area import fits_on_bed
    from app.core.export import threemf
    from app.core.geom.prepare import ARRANGE_SPACING

    links = trimesh.creation.box((10.0, 10.0, 10.0))
    links.apply_translation((100.0, 50.0, 15.0))
    rechts = trimesh.creation.box((10.0, 10.0, 10.0))
    rechts.apply_translation((140.0, 50.0, 15.0))
    group = threemf.write_assembly(
        [
            threemf.AssemblyPart(mesh=MeshData.of(links), name="Links"),
            threemf.AssemblyPart(mesh=MeshData.of(rechts), name="Rechts"),
        ]
    )
    cube = (MESHES / "cube_clean.stl").read_bytes()
    project, _history = _imported_in_turn(profile, ("wuerfel.stl", cube), ("gruppe.3mf", group))

    result = _scene(project, profile)
    first, left, right = (result.scene.objects[key] for key in ("obj_1", "obj_2", "obj_3"))
    assert [entry.plate for entry in (first, left, right)] == [0, 0, 0]
    for body in (left, right):
        assert fits_on_bed(body.mesh, profile.printer), body.name
        assert _apart(first, body, ARRANGE_SPACING), body.name
        assert body.mesh.bounds.minimum[2] == pytest.approx(0.0), body.name
    shift = [b - a for a, b in zip(left.mesh.bounds.centre, right.mesh.bounds.centre, strict=True)]
    assert shift == pytest.approx([40.0, 0.0, 0.0]), "die Teile behalten ihre Lage zueinander"


def test_an_older_further_load_keeps_the_place_of_its_file(profile: Profile) -> None:
    """Ein Ladeschritt ohne den Schalter — gespeichert vor dem 28.09.2026 —
    rechnet wie gespeichert: Das zweite Modell bleibt an seinen Dateikoordinaten."""
    cube = (MESHES / "cube_clean.stl").read_bytes()
    project = new_project("centauri-carbon-2", "petg")
    for key in ("src_1", "src_2"):
        project.document.sources[key] = Source(
            id=key, kind="import", path=f"sources/{key}.stl", sha256=""
        )
        project.sources[key] = cube
    history = History(project.document)
    history.apply(
        _("Modell laden"),
        [
            OperationDraft(
                op="load",
                params={"source": "src_1", "unit": "mm", "place_on_bed": True, "centre": True},
            )
        ],
    )
    history.apply(
        _("Modell laden"),
        [OperationDraft(op="load", params={"source": "src_2", "unit": "mm"})],
    )

    result = _scene(project, profile)
    second = result.scene.objects["obj_2"]
    assert second.plate == 0
    assert tuple(second.mesh.bounds.minimum) == pytest.approx((-10.0, -10.0, -10.0))
    assert "arrange.free_spot" not in {entry.code for entry in result.scene.report.findings}


def test_the_free_place_is_found_once_and_then_kept(profile: Profile) -> None:
    """Die freie Stelle wird einmal gerechnet und im Schritt festgehalten
    (Entscheidung Robert, §15.7): wie die beantwortete Einheitenfrage.

    Solange sie nicht im Schritt steht, hängt sie an dem, was davor liegt —
    wird der erste Würfel in Zentimetern gelesen (200 mm), ist auf der ersten
    Platte kein Platz, und mit Cache darf nicht das alte Ergebnis kommen. Steht
    sie im Schritt, bleibt der zweite liegen, wie in jedem Slicer.
    """
    from app.core.scene.cache import ResultCache

    cube = (MESHES / "cube_clean.stl").read_bytes()
    project, history = _imported_in_turn(profile, ("erster.stl", cube), ("zweiter.stl", cube))
    cache = ResultCache()
    first = _scene(project, profile, cache=cache)
    second_step = project.document.ops[1]
    placed = first.scene.objects["obj_2"].mesh.bounds
    assert first.answers[second_step.id] == {
        "spot_x": pytest.approx(placed.centre[0]),
        "spot_y": pytest.approx(placed.centre[1]),
        "spot_plate": 1,
    }, "die Stelle kommt als Antwort zurück"

    # Noch nicht festgehalten: Die Stelle folgt dem, was davor liegt.
    history.change_params(project.document.ops[0].id, {"unit": "cm"})
    moved = _scene(project, profile, cache=cache).scene.objects["obj_2"]
    assert moved.plate == 1, "kein Platz mehr neben 200 mm — die nächste Platte"
    history.change_params(project.document.ops[0].id, {"unit": "mm"})

    # Festgehalten — wie die Sitzung es nach dem ersten Ergebnis tut: Der
    # zweite bleibt, wo er zuerst hinkam.
    assert history.record_answers(first.answers)
    history.change_params(project.document.ops[0].id, {"unit": "cm"})
    kept = _scene(project, profile, cache=cache).scene.objects["obj_2"]
    assert kept.plate == 0
    assert tuple(kept.mesh.bounds.minimum) == pytest.approx(tuple(placed.minimum))


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


def test_the_same_file_twice_gives_two_names_that_can_be_told_apart(
    profile: Profile,
) -> None:
    """Zweimal dieselbe STL ergibt zwei Körper — und zwei Namen.

    Der gewöhnliche Weg zu zwei gleichen Teilen ist, dieselbe Datei zweimal
    einzulesen. Im Objektbaum standen danach zwei Zeilen „plate_holes", und im
    Prüfbericht zweimal derselbe Satz mit demselben Namen dahinter: kein Weg,
    beim Lesen zu erkennen, welcher Körper gemeint ist. Der zweite heißt
    deshalb „plate_holes (2)" — seit der Durchsicht 0.5.0 mit Klammer und für
    jede Datei gleich: Eine Baugruppe nummeriert jeden Teil so, und Teilnamen
    enden selbst oft auf eine Zahl („Sieb 1 (2)" statt „Sieb 1 2").

    Der Bericht bündelt gleiche Meldungen seit 0.4.1, hier aber **nicht**, und
    das ist richtig: In seinen Gruppenschlüssel geht der Schritt ein, und zwei
    Importe sind zwei Schritte (``panels._bundled``). Zwei Zeilen zu zwei
    Schritten sind die Wahrheit — sie müssen nur sagen, zu welchem Körper sie
    gehören, und genau das tut der Name.
    """
    from app.core.ingest.plan import names_in_use

    project = new_project("centauri-carbon-2", "petg")
    payload = (MESHES / "plate_holes.stl").read_bytes()
    for nummer in (1, 2):
        source_id = f"src_{nummer}"
        project.document.sources[source_id] = Source(
            id=source_id, kind="import", path="sources/plate_holes.stl", sha256=""
        )
        project.sources[source_id] = payload
        plan = import_plan(
            source_id,
            "plate_holes.stl",
            payload,
            "mm",
            taken=names_in_use(project.document),
        )
        History(project.document).apply(plan.title, [plan.draft])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, f"gestoppt bei op {result.stopped_at}"
    namen = [entry.name for entry in result.scene.objects.values()]
    assert namen == ["plate_holes", "plate_holes (2)"], namen

    # **Und der Bericht nennt beide unterscheidbar.** Die Zeile des Fensters
    # setzt den Namen des Körpers hinter den Satz (``panels._line_for``); was
    # sie dafür liest, ist genau diese Zuordnung.
    zu_namen = result.object_names
    beteiligt = {
        zu_namen.get(str(finding.object_id))
        for finding in result.scene.report.findings
        if finding.object_id is not None
    }
    assert {"plate_holes", "plate_holes (2)"} <= beteiligt, beteiligt


def _imported_twice(file_name: str, payload: bytes, times: int, profile: Profile) -> list[str]:
    """Dieselbe Datei so oft eingelesen, wie das Fenster es täte — die Namen danach."""
    from app.core.ingest.plan import names_in_use

    project = new_project("centauri-carbon-2", "petg")
    for number in range(1, times + 1):
        source_id = f"src_{number}"
        project.document.sources[source_id] = Source(
            id=source_id, kind="import", path=f"sources/{file_name}", sha256=""
        )
        project.sources[source_id] = payload
        plan = import_plan(
            source_id, file_name, payload, "mm", taken=names_in_use(project.document)
        )
        History(project.document).apply(plan.title, [plan.draft])
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, f"gestoppt bei op {result.stopped_at}"
    return [str(entry.name) for entry in result.scene.objects.values()]


def test_the_same_assembly_twice_keeps_every_name_apart(profile: Profile) -> None:
    """Eine Baugruppe zweimal eingelesen: jeder Teil mit seiner Kopiennummer.

    Der Einleseplan nummerierte nur einen einzelnen Körper; eine Baugruppe
    bringt ihre Namen aus der Datei mit, und die zweite Kopie trug sie alle
    ein zweites Mal. Gemessen am ``Siebhalter+X1C.3mf`` eines Kunden: sieben
    gleiche Zeilen im Baum und im Prüfbericht (Durchsicht 0.5.0). Die dritte
    Kopie bekommt die nächste Nummer, nicht noch einmal die zweite.
    """
    from tests.test_threemf_assembly import cube, production_container

    payload = production_container(
        {"1": cube(10.0), "2": cube(12.0, at=(30.0, 0.0, 0.0))},
        names={"1": "Halter", "2": "Deckel"},
    )

    names = _imported_twice("baugruppe.3mf", payload, 3, profile)

    assert names == [
        "Halter",
        "Deckel",
        "Halter (2)",
        "Deckel (2)",
        "Halter (3)",
        "Deckel (3)",
    ], names


def test_an_unnamed_body_in_a_3mf_is_named_after_its_file(profile: Profile) -> None:
    """Ein unbenannter Körper heißt wie seine Datei — wie bei einer STL.

    Hier stand der Ersatz „Körper 1", und beim zweiten Einlesen hieß derselbe
    Körper nach der Datei: „Körper 1" und „drill-holder 2" im selben Baum,
    gemessen an ``drill-holder.3mf`` (Durchsicht 0.5.0).
    """
    from tests.test_threemf_assembly import cube, production_container

    payload = production_container({"1": cube(10.0)})

    assert _imported_twice("halter.3mf", payload, 2, profile) == ["halter", "halter (2)"]


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
    assert gefangen.value.constraint == constraint
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
    # Seit P7.4 liest der Plan eine STEP-Datei, um ihre Körper zu zählen; die
    # Kennungsprüfung davor bleibt stumm, und was der Leser nicht versteht,
    # ist seine Absage mit Vorschlag, nicht die der Prüfung.
    step = (Path(__file__).parent / "data" / "step" / "inch.step").read_bytes()
    plan = import_plan("src_1", "teil.step", step)
    assert plan.draft.op == "load_step"
    with pytest.raises(ValidationError) as caught:
        import_plan("src_1", "teil.step", b"ISO-10303-21;\nHEADER;\n")
    assert caught.value.constraint == "unreadable", "der Leser sagt ab, nicht die Kennung"
    assert caught.value.suggestions


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
    dateien = [
        pfad
        for pfad in sorted(korpus.rglob("*"))
        if pfad.is_file() and pfad.suffix.lower() in (".stl", ".3mf", ".obj", ".ply")
    ]
    assert korpus / "meshes" / "cube_clean.stl" in dateien, "Der Modellkorpus fehlt."
    gefallen = []
    for pfad in dateien:
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


@pytest.mark.parametrize("suffix", [".obj", ".ply", ".3mf"])
@pytest.mark.parametrize("inverted", [False, True], ids=["same", "inverted"])
def test_a_shell_written_twice_with_its_own_corners_arrives_once(
    profile: Profile, suffix: str, inverted: bool
) -> None:
    """Eine Datei, die ihre Schale zweimal mit eigenen Ecken trägt, liefert sie einmal.

    Gefunden vom Paket „netzkern" der Durchsicht 0.5.0, nachgemessen hier: Eine
    Kugel (1280 Dreiecke, 33 221,9 mm³) zweimal in einer OBJ, PLY oder 3MF kam
    als zwei deckungsgleiche Teile mit **doppeltem** Volumen an, und der
    Bericht sagte nur „Doppelte Punkte blieben stehen" und „besteht aus
    mehreren Teilen". Das Verschweißen hätte die Kopie zu doppelten Dreiecken
    gemacht und wurde zurückgenommen, weil das Netz dann offen war. Eine STL
    kam richtig an — sie ist eine Dreieckssuppe, dort räumt ``unique_faces``
    die Doppelung ab.

    Jetzt bleibt von deckungsgleichen Dreiecken das erste, wenn das Netz
    danach geschlossen ist, und der Bericht sagt es. Gleich wie die Kopie
    umläuft: Die Außenseiten richtet der nächste Schritt aus.
    """
    ball = trimesh.creation.icosphere(subdivisions=3, radius=20.0)
    copy = ball.copy()
    if inverted:
        copy.invert()
    twice = trimesh.util.concatenate([ball, copy])
    assert len(twice.vertices) == 2 * len(ball.vertices), "jede Schale mit eigenen Ecken"
    exported = twice.export(file_type=suffix.lstrip("."))
    payload = exported if isinstance(exported, bytes) else exported.encode("utf-8")

    project = _project_of(payload, f"kugel{suffix}")
    History(project.document).apply(
        _("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    (body,) = result.scene.objects.values()
    assert body.mesh.triangle_count == len(ball.faces)
    assert body.mesh.component_count == 1
    assert body.mesh.is_watertight
    # PLY speichert Ecken in einfacher Genauigkeit: daher die Toleranz.
    assert float(body.mesh.volume) == pytest.approx(float(ball.volume), rel=1e-6)
    codes = {entry.code for entry in result.scene.report.findings}
    assert "ingest.doubled_shell_removed" in codes, codes
    assert not codes & {"ingest.weld_skipped", "ingest.multiple_components"}, codes


def test_two_closed_bodies_that_only_touch_keep_both(profile: Profile) -> None:
    """Die Gegenprobe: Zwei Würfel, die sich an einer Fläche berühren, sind keine Kopie.

    Ihr Verschweißen macht die gemeinsame Fläche zu einem deckungsgleichen
    Paar; das erste zu behalten ließe eine Kante mit drei Flächen zurück. Dann
    bleibt es beim Zurücknehmen des Verschweißens — zwei Teile, beide ganz.
    """
    left = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right.apply_translation((10.0, 0.0, 0.0))
    exported = trimesh.util.concatenate([left, right]).export(file_type="obj")
    payload = exported if isinstance(exported, bytes) else exported.encode("utf-8")

    project = _project_of(payload, "wuerfel.obj")
    History(project.document).apply(
        _("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    (body,) = result.scene.objects.values()
    assert body.mesh.component_count == 2
    assert float(body.mesh.volume) == pytest.approx(2000.0, rel=1e-9)
    codes = {entry.code for entry in result.scene.report.findings}
    assert "ingest.doubled_shell_removed" not in codes


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
    # Über die Nutzlast: Sie wird sofort eingebettet und im Arbeiter geplant —
    # genau die Lage dieses Befunds. Eine Datei vom Pfad liest seit RM-224
    # zuerst ein eigener Arbeiter; die verspätete Lesung prüft der Test darunter.
    session.import_payload_async(kaputt.name, kaputt.read_bytes())
    assert list(session.project.document.sources) == ["src_1"], "der alte Import trägt src_1"

    # Bevor der Arbeiter antwortet: ein neues Projekt mit einer eigenen src_1.
    session.start_new("centauri-carbon-2", "petg")
    own = session._embed_source("import", "eigenes.stl", ganz)
    assert own == "src_1", "das neue Projekt vergibt dieselbe Kennung"

    settle()

    assert "src_1" in session.project.document.sources, "die Quelle des neuen Projekts bleibt"
    assert session.project.sources["src_1"] == ganz, "samt Nutzdaten"
    assert gesehen.get("error") is None, "der alte Fehler gilt dem neuen Projekt nicht"


def test_a_model_file_is_read_in_the_worker(qt_app: Any, tmp_path: Path) -> None:
    """RM-224: ``open_path`` liest keine Datei mehr im Hauptthread.

    Eine Datei auf einem Laufwerk, das nicht antwortet, hielt das Fenster bis
    zum Zeitlimit des Systems an (gemessen 21 s). Der Aufruf kehrt jetzt
    zurück, bevor die Datei gelesen ist — sichtbar daran, dass noch keine
    Quelle eingebettet ist; ohne Grenze gilt das für jede Größe.
    """
    from app.ui.session import Session

    modell = tmp_path / "wuerfel.stl"
    modell.write_bytes(_stl(_cube()))
    session = Session()
    gesehen, settle = _await_signal(session)

    session.import_model_async(modell)

    assert not session.project.document.sources, "gelesen wird im Arbeiter, nicht im Aufruf"
    assert session.busy, "und die Sitzung sagt, dass sie arbeitet"
    settle()
    assert gesehen.get("error") is None, gesehen.get("error")
    assert gesehen.get("accepted") is True, "der Weg muss bis zum Ende laufen"
    assert [entry.op for entry in session.project.document.ops] == ["load"]


def test_a_file_that_cannot_be_read_says_so_with_a_way(qt_app: Any, tmp_path: Path) -> None:
    """Eine fehlende Datei ist eine Lage des Kunden, kein Programmfehler.

    Im Arbeiter käme ein nacktes ``OSError`` als Absturzbericht an. Es kommt
    als Hinweis mit *Andere Datei wählen* — derselbe Satz wie in der
    Quellenwahl eines Dialogs (``loader.unreadable_file``).
    """
    from app.core.errors import InternalError, UserError
    from app.ui.session import Session

    session = Session()
    gesehen, settle = _await_signal(session)

    session.import_model_async(tmp_path / "verschoben.stl")
    settle()

    error = gesehen.get("error")
    assert isinstance(error, UserError) and not isinstance(error, InternalError), error
    assert str(error.title) == "Diese Datei ließ sich nicht lesen."
    assert [action.id for action in error.suggestions] == ["choose_another_file", "cancel"]
    assert not session.project.document.sources and not session.project.document.ops


def test_a_read_that_arrives_after_the_project_changed_is_dropped(
    qt_app: Any, tmp_path: Path
) -> None:
    """Die Lesung trägt den Stempel ihres Dokuments, wie der Plan (UI-01).

    Zwischen Aufruf und Antwort des Lesearbeiters kann ein neues Projekt offen
    sein; die gelesene Datei gehört dann in keines der beiden.
    """
    from app.ui.session import Session

    modell = tmp_path / "wuerfel.stl"
    modell.write_bytes(_stl(_cube()))
    session = Session()

    session.import_model_async(modell)
    session.start_new("centauri-carbon-2", "petg")
    assert session.wait_for_idle(20_000)

    assert not session.project.document.sources, "die alte Lesung bettet nichts ein"
    assert not session.project.document.ops, "und legt keinen Schritt an"


def test_reading_a_file_the_system_refuses_is_a_hint(tmp_path: Path) -> None:
    """``read_bounded_payload`` übersetzt den ``OSError`` des Systems (RM-224).

    Der Grund des Systems reist als Wert mit; der Dateiname auch, der Pfad
    nicht — er gehört in keinen Bericht.
    """
    from app.core.errors import UserError
    from app.core.ingest.loader import read_bounded_payload

    with pytest.raises(UserError) as raised:
        read_bounded_payload(tmp_path / "weg.stl")

    assert [action.id for action in raised.value.suggestions] == ["choose_another_file", "cancel"]
    assert raised.value.values["path"] == "weg.stl"
    assert raised.value.values["reason"]
    assert isinstance(raised.value.__cause__, OSError)


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


# --- was nur eingelesen wurde (RM-130) --------------------------------------------


def _after_an_import(name: str = "cube_clean.stl") -> Any:
    """Eine Sitzung, in der genau eine Datei eingelesen wurde."""
    from app.ui.session import Session

    session = Session()
    assert session.import_model(MESHES / name), "der Import selbst muss durchgehen"
    return session


def test_a_document_that_only_read_files_says_so() -> None:
    """Der Normalfall des Kunden: ansehen, nichts tun (RM-130).

    Zwei Dateien nacheinander sind immer noch nichts, was jemand getan hat —
    beide liegen auf der Platte, beide kommen beim nächsten Mal genauso
    wieder herein.
    """
    session = _after_an_import()

    assert is_only_imported(session.project.document)
    assert session.only_imported

    assert session.import_model(MESHES / "plate_holes.stl")
    assert is_only_imported(session.project.document)


def test_an_empty_document_is_not_only_imported() -> None:
    """Ohne Stapel gibt es nichts zu verlieren, und die Frage stellt sich nicht."""
    from app.ui.session import Session

    assert not is_only_imported(Session().project.document)


def test_anything_beyond_reading_a_file_counts_as_work() -> None:
    """Jede Entscheidung, die jemand noch einmal treffen müsste, zählt (RM-130).

    Sieben Wege, aus einem eingelesenen Modell ein Dokument zu machen — und
    jeder einzelne muss die Frage beim Schließen zurückholen. Der Reihe nach:
    eine Operation, die keine Ladeoperation ist; ein benannter Parameter; eine
    Passung; ein Gesprächsbeitrag; gewählte Druckeinstellungen; eine
    **erzeugte** Quelle (sie trägt Anfrage und Startwert und ist ohne die
    Projektdatei weg); und ein Drucker- oder Materialwechsel, der nicht im
    Stapel steht, sondern in den Änderungen der Transaktion (§15.5).
    """
    from dataclasses import replace

    from app.core.types import (
        ChatEntry,
        DocumentChange,
        DocumentState,
        FeatureRef,
        Fit,
        Operation,
        Parameter,
        PrintSettings,
    )

    def mit_operation(document: Any) -> None:
        document.ops.append(Operation(id=99, op="create_box", inputs=(), outputs=("obj_9",)))

    def mit_parameter(document: Any) -> None:
        document.parameters["hoehe"] = Parameter(name="hoehe", value=10.0)

    def mit_passung(document: Any) -> None:
        document.fits.append(
            Fit(name="stift_1", a=FeatureRef("obj_1", "hole_1"), b=FeatureRef("obj_1", "pin_1"))
        )

    def mit_beitrag(document: Any) -> None:
        document.chat.append(ChatEntry(id="chat_1", role="user", text="Mach es hohl"))

    def mit_druckeinstellungen(document: Any) -> None:
        document.print_settings = PrintSettings()

    def mit_erzeugter_quelle(document: Any) -> None:
        key = next(iter(document.sources))
        document.sources[key] = replace(document.sources[key], kind="generated")

    def mit_druckerwechsel(document: Any) -> None:
        document.transactions[0] = replace(
            document.transactions[0],
            changes=DocumentChange(
                before=DocumentState(printer="generic-220"),
                after=DocumentState(printer="centauri-carbon"),
            ),
        )

    for name, aendern in (
        ("eine Operation", mit_operation),
        ("ein Parameter", mit_parameter),
        ("eine Passung", mit_passung),
        ("ein Gesprächsbeitrag", mit_beitrag),
        ("Druckeinstellungen", mit_druckeinstellungen),
        ("eine erzeugte Quelle", mit_erzeugter_quelle),
        ("ein Druckerwechsel", mit_druckerwechsel),
    ):
        session = _after_an_import()
        assert is_only_imported(session.project.document), name
        aendern(session.project.document)
        assert not is_only_imported(session.project.document), (
            f"{name} macht aus dem Einlesen ein Dokument"
        )


def test_a_saved_project_is_never_only_imported(tmp_path: Path) -> None:
    """Sobald es eine Datei gibt, geht es um Änderungen an ihr (RM-130).

    Eine gespeicherte Projektdatei ist das, was der Kunde pflegt; was daran
    ungesichert ist, wird gefragt — auch wenn der Stapel nur einen Import
    trägt.
    """
    session = _after_an_import()
    session.save_project(tmp_path / "projekt.p3d")

    assert is_only_imported(session.project.document), "am Dokument ändert das Speichern nichts"
    assert not session.only_imported, "die Sitzung hat jetzt eine Datei"


def test_leaving_wide_openings_open_on_import_names_what_stays_open() -> None:
    """*Offen lassen* am Ladeschritt: die große Öffnung bleibt, mit Ort und Weg (RM-241)."""
    result = normalise(mesh_of("broken_open.stl"), "mm", wide_holes=False)

    assert not result.mesh.is_watertight
    codes = {finding.code for finding in result.findings}
    assert "repair.wide_hole_filled" not in codes
    assert "ingest.not_watertight" not in codes, "ein Satz über dieselben Ränder genügt"
    kept = next(finding for finding in result.findings if finding.code == "repair.wide_hole_kept")
    assert str(kept.message) == "Eine große Öffnung bleibt offen."
    assert kept.location is not None


def _two_boxes(offset: float) -> MeshData:
    """Zwei Würfel mit 20 mm Kante, der zweite um ``offset`` entlang X verschoben."""
    first = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second.apply_translation((offset, 0.0, 0.0))
    return MeshData.of(trimesh.util.concatenate([first, second]))


def test_parts_that_stick_into_each_other_are_named_on_import() -> None:
    """Zwei ineinandergeschobene Würfel: der Satz sagt es, und der erste Knopf löst es auf.

    Befund A5 der Bedienweg-Durchsicht (24.09.2026): Vorher stand nur „Das
    Modell besteht aus mehreren Teilen" mit *In Einzelteile zerlegen* — zerlegt
    wären es zwei Teile am selben Ort.
    """
    result = normalise(_two_boxes(10.0), "mm")

    finding = next(f for f in result.findings if f.code == "ingest.multiple_components")
    assert str(finding.message) == "Das Modell besteht aus zwei Teilen, die ineinanderstecken."
    assert [action.id for action in finding.suggestions] == [
        "resolve_intersections",
        "split_bodies",
    ]
    assert finding.location is not None
    assert -10.0 <= finding.location[0] <= 20.0


def test_parts_apart_or_with_play_keep_the_plain_sentence() -> None:
    """Die Gegenprobe: getrennte Teile und ein Ring mit Spiel um einen Stift.

    Der Ring hat einen Hüllquader, der den Stift umschließt, und keine einzige
    gemeinsame Stelle — ein Kettenglied, ein Druck-im-Stück-Gelenk. Dort
    steckt nichts ineinander, und *Überschneidungen auflösen* hätte nichts zu tun.
    """
    apart = normalise(_two_boxes(30.0), "mm")
    finding = next(f for f in apart.findings if f.code == "ingest.multiple_components")
    assert str(finding.message) == "Das Modell besteht aus mehreren Teilen."
    assert not finding.suggestions

    pin = trimesh.creation.cylinder(radius=4.0, height=20.0, sections=48)
    ring = trimesh.creation.annulus(r_min=6.0, r_max=8.0, height=5.0, sections=48)
    loose = normalise(MeshData.of(trimesh.util.concatenate([pin, ring])), "mm")
    finding = next(f for f in loose.findings if f.code == "ingest.multiple_components")
    assert str(finding.message) == "Das Modell besteht aus mehreren Teilen."
