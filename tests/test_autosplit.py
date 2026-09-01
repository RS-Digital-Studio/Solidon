"""Auto Split mit Verstiftung (Bauplan §25, §22.3, §14; §40 für P10).

Das Abnahmekriterium sind drei Sätze: jedes Teil für sich wasserdicht,
Passungspaare angelegt und geprüft, und ``oversized.stl`` in etwas Druckbares
geteilt, ohne dass jemand einen Parameter anfasst. Alle drei stehen hier.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import BooleanFailedError, OperationCancelled, ValidationError
from app.core.geom import autosplit, pins
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.prepare import split_at_plane
from app.core.geom.section import Axis, SectionPlane
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cancel import CancelSignal, NeverCancelled
from app.core.scene.project import Project, ProjectSources, load, new_project, save
from app.core.slice.orientation import best_face_candidate
from app.core.split import apply_line_split, apply_planned, apply_split, plan_split
from app.core.types import OpContext, Profile, Scene, SceneObject, Source

MESHES = Path(__file__).parent / "data" / "meshes"


def body(name: str = "oversized.stl") -> MeshData:
    """So, wie die Eingangsstufe ihn liefert — verschweißt und damit
    geschlossen.
    """
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def bar(length: float = 400.0) -> MeshData:
    return MeshData.of(trimesh.creation.box(extents=(length, 60.0, 40.0)))


def crossed_overhangs() -> MeshData:
    """Zwei rechtwinklige Überhänge dicht rechts von der Körpermitte.

    Der lange Balken macht den Körper zu groß für das Bett. Ein Schnitt in
    seiner Mitte sieht für die billige Nahtbewertung vollkommen aus: eine
    Kontur, prismatisch, ausgewogen. Dann bleiben aber beide Überhänge am
    rechten Teil und verlangen widersprüchliche Grundflächen. Bei x = 3,25 mm
    werden sie getrennt und können unabhängig liegen.

    Alle Maße sind Quadermaße. Das Stützvolumen ist damit kein Urteil über
    einen Modellnamen, sondern die Säule unter zwei analytischen Decken.
    """
    pieces = []
    beam = trimesh.creation.box(extents=(400.0, 12.0, 12.0))
    beam.apply_translation((0.0, 0.0, 6.0))
    pieces.append(beam)

    upright_stem = trimesh.creation.box(extents=(2.0, 14.0, 35.0))
    upright_stem.apply_translation((1.5, 0.0, 17.5))
    upright_roof = trimesh.creation.box(extents=(2.0, 45.0, 6.0))
    upright_roof.apply_translation((1.5, 0.0, 38.0))
    pieces.extend((upright_stem, upright_roof))

    sideways_stem = trimesh.creation.box(extents=(2.0, 35.0, 14.0))
    sideways_stem.apply_translation((6.0, 17.5, 6.0))
    sideways_roof = trimesh.creation.box(extents=(2.0, 6.0, 45.0))
    sideways_roof.apply_translation((6.0, 38.0, 6.0))
    pieces.extend((sideways_stem, sideways_roof))
    return MeshData.of(trimesh.boolean.union(pieces))


def dumbbell(neck: float = 30.0, flank: float = 60.0) -> MeshData:
    """Dicke Enden, ein Hals, der sich **stetig** auf ``neck`` verjüngt.

    Der Radius fällt über ``flank`` Millimeter von 40 auf ``neck`` und steigt
    wieder — eine **sanfte** Mulde, und das ist der Punkt.

    Drei Entwürfe davor trafen den Fall nicht, und jeder verfehlte ihn anders:

    * Zwei Kegel Spitze an Spitze berühren sich in einem Punkt mit Querschnitt
      **null**. Dort lässt sich gar nicht schneiden.
    * Ein Hals, der von −8 bis +8 gleich stark bleibt, ist im Suchfenster
      überall gleich dick — bei einem 400 mm langen Körper auf einem 220er
      Bett reicht das Fenster nur ±16 mm um die Mitte, weiter außen passt eine
      Hälfte nicht mehr. Es gab keine Kerbe zu erkennen, nur eine flache
      Strecke.
    * Eine **steile** Verjüngung über ±30 mm fängt schon der vorhandene
      ``PRISM_WEIGHT``-Term: Dort ändert sich der Querschnitt kräftig, und die
      Naht wandert von selbst weg. Der Test war grün, ohne den neuen Term zu
      brauchen.

    Die Lücke liegt dazwischen: eine Verjüngung, die flach genug ist, dass
    ``change`` sie über seine halbe Millimeter nicht sieht, und tief genug,
    dass die Naht dort nicht hingehört. Gemessen wählt die Suche ohne den
    Einschnürungsterm genau die Mitte, mit einer Punktzahl von 0,003.
    """
    profile_line = np.array(
        [
            [0.0, -200.0],
            [40.0, -200.0],
            [40.0, -flank],
            [neck, 0.0],
            [40.0, flank],
            [40.0, 200.0],
            [0.0, 200.0],
        ]
    )
    body_mesh = trimesh.creation.revolve(profile_line, sections=64)
    body_mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    return MeshData.of(body_mesh)


# --- die Suche ------------------------------------------------------------------


def test_a_part_that_fits_is_left_alone(profile: Profile) -> None:
    small = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))

    assert autosplit.fits(small, profile)
    assert autosplit.find_plane(small, profile) is None
    assert not autosplit.split_to_fit(small, profile).divided


def test_the_oversize_is_measured_per_axis(profile: Profile) -> None:
    over = autosplit.oversize(body(), profile)

    assert over[0] == pytest.approx(400.0 - 252.0), "252 mm usable of a 256 mm plate"
    assert over[1] == 0.0 and over[2] == 0.0


def test_the_plane_lands_in_the_slim_middle(profile: Profile) -> None:
    """§22.3: der Querschnitt entscheidet, und die schmale prismatische Mitte
    gewinnt.
    """
    candidate = autosplit.find_plane(body(), profile)

    assert candidate is not None
    assert candidate.axis == "x", "cut across the direction that is too long"
    assert -85.0 < candidate.position < 85.0, "inside the middle bar"
    assert candidate.contours == 1, "one seam, not several thin bridges"
    assert candidate.area == pytest.approx(40.0 * 30.0), "the section of the middle"


def test_real_support_moves_the_seam_between_crossed_overhangs(profile: Profile) -> None:
    """T2, §22.3: echtes Stützvolumen schlägt die billige Mittenlage.

    Ohne die zweite Stufe gewinnt die gute Naht knapp links der Mitte. Dort
    bleiben die zwei rechtwinkligen Überhänge an derselben Hälfte. Schon der
    nächste gute Kandidat rechts davon trennt sie; beide Hälften dürfen dann
    ihre eigene Grundfläche wählen und brauchen zusammen wesentlich weniger
    Stützen.
    """
    mesh = crossed_overhangs()

    axis: Axis = "x"
    window = autosplit._window(mesh, profile, axis)
    positions = np.linspace(window[0], window[1], autosplit.SAMPLES)
    cheap = min(autosplit._judge(mesh, axis, positions), key=autosplit._candidate_order)

    candidate = autosplit.find_plane(mesh, profile)

    assert candidate is not None
    assert cheap.position < 0.0, "die erste Stufe bleibt absichtlich bei der Nahtheuristik"
    assert candidate.position > 2.0, (
        f"die Naht blieb bei {candidate.position:.2f} mm in der billigen Mitte, "
        "obwohl dort beide Überhänge an einem Teil bleiben"
    )
    cheap_support = autosplit._support_after_cut(
        mesh, cheap, profile, orientation_candidates=3, cancelled=None
    )
    chosen_support = autosplit._support_after_cut(
        mesh, candidate, profile, orientation_candidates=3, cancelled=None
    )
    assert chosen_support < cheap_support * 0.5, (
        f"die gewählte Naht braucht {chosen_support:.0f} statt {cheap_support:.0f} mm³ — "
        "der analytische Körper soll den Unterschied deutlich, nicht im Rauschen zeigen"
    )


def test_support_within_five_percent_keeps_the_better_seam(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Millimeter³ werden nicht in den dimensionslosen Naht-Score addiert.

    Die Vorauswahl hält die Nahtqualität fest. Erst mehr als die vorhandene
    Fünf-Prozent-Grenze der Orientierung darf sie umwerfen.
    """
    mesh = crossed_overhangs()
    better_seam = autosplit.Candidate("x", 0.0, 144.0, 1, 0.0)
    worse_seam = autosplit.Candidate("x", 3.25, 144.0, 1, 0.1)
    support = {better_seam.position: 100.0, worse_seam.position: 96.0}
    monkeypatch.setattr(
        autosplit,
        "_support_after_cut",
        lambda _mesh, candidate, _profile, **_kwargs: support[candidate.position],
    )

    chosen = autosplit._best_by_support(
        mesh,
        profile,
        (worse_seam, better_seam),
        plane_candidates=2,
        orientation_candidates=3,
        cancelled=None,
    )

    assert chosen is better_seam


def test_support_above_five_percent_can_move_the_seam(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    better_seam = autosplit.Candidate("x", 0.0, 144.0, 1, 0.0)
    worse_seam = autosplit.Candidate("x", 3.25, 144.0, 1, 0.1)
    support = {better_seam.position: 100.0, worse_seam.position: 94.0}
    monkeypatch.setattr(
        autosplit,
        "_support_after_cut",
        lambda _mesh, candidate, _profile, **_kwargs: support[candidate.position],
    )

    chosen = autosplit._best_by_support(
        crossed_overhangs(),
        profile,
        (better_seam, worse_seam),
        plane_candidates=2,
        orientation_candidates=3,
        cancelled=None,
    )

    assert chosen is worse_seam


def test_a_failed_probe_cut_does_not_hide_a_usable_candidate(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    mesh = crossed_overhangs()
    failed = autosplit.Candidate("x", 0.0, 144.0, 1, 0.0)
    usable = autosplit.Candidate("x", 3.25, 144.0, 1, 0.1)
    support = {failed.position: float("inf"), usable.position: 100.0}
    monkeypatch.setattr(
        autosplit,
        "_support_after_cut",
        lambda _mesh, candidate, _profile, **_kwargs: support[candidate.position],
    )

    chosen = autosplit._best_by_support(
        mesh,
        profile,
        (failed, usable),
        plane_candidates=2,
        orientation_candidates=3,
        cancelled=None,
    )

    assert chosen is usable


def test_only_the_fixed_shortlist_is_sliced(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die 33 billigen Ebenen werden nicht zu 33 Schichtanalysen."""
    seen: list[float] = []

    def record(
        _mesh: MeshData, candidate: autosplit.Candidate, _profile: Profile, **_kwargs: object
    ) -> float:
        seen.append(candidate.position)
        return abs(candidate.position)

    monkeypatch.setattr(autosplit, "_support_after_cut", record)

    autosplit.find_plane(crossed_overhangs(), profile, support_planes=3)

    assert len(seen) == 3


def test_support_refinement_is_reproducible(profile: Profile) -> None:
    mesh = crossed_overhangs()

    first = autosplit.find_plane(mesh, profile)
    second = autosplit.find_plane(mesh, profile)

    assert first == second


def test_support_refinement_stops_before_the_probe_cut(profile: Profile) -> None:
    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        autosplit._support_after_cut(
            crossed_overhangs(),
            autosplit.Candidate("x", 0.0, 144.0, 1, 0.0),
            profile,
            orientation_candidates=3,
            cancelled=signal,
        )


def test_support_refinement_stops_after_the_probe_cut(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    signal = CancelSignal()
    mesh = crossed_overhangs()

    def cut_and_cancel(
        _mesh: MeshData, _candidate: autosplit.Candidate
    ) -> tuple[MeshData, MeshData]:
        signal.cancel()
        return mesh, mesh

    monkeypatch.setattr(autosplit, "_cut_in_two", cut_and_cancel)

    with pytest.raises(OperationCancelled):
        autosplit._support_after_cut(
            mesh,
            autosplit.Candidate("x", 0.0, 144.0, 1, 0.0),
            profile,
            orientation_candidates=3,
            cancelled=signal,
        )


def test_support_refinement_stops_after_the_connector_plan(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    signal = CancelSignal()
    original = pins.plan_pins

    def plan_and_cancel(*args: object, **kwargs: object):
        plan = original(*args, **kwargs)
        signal.cancel()
        return plan

    monkeypatch.setattr(pins, "plan_pins", plan_and_cancel)
    monkeypatch.setattr(
        pins,
        "add_pins",
        lambda *_args, **_kwargs: pytest.fail("nach dem Abbruch wurden Verbinder gebaut"),
    )

    with pytest.raises(OperationCancelled):
        autosplit._support_after_cut(
            crossed_overhangs(),
            autosplit.Candidate("x", 0.0, 144.0, 1, 0.0),
            profile,
            orientation_candidates=3,
            cancelled=signal,
            connector_count=pins.PIN_COUNT,
        )


def test_support_refinement_stops_after_adding_connectors(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.knowledge.parts import PARTS

    PARTS.all()
    signal = CancelSignal()
    original = pins.add_pins

    def add_and_cancel(*args: object, **kwargs: object):
        pair = original(*args, **kwargs)
        signal.cancel()
        return pair

    monkeypatch.setattr(pins, "add_pins", add_and_cancel)

    with pytest.raises(OperationCancelled):
        autosplit._support_after_cut(
            crossed_overhangs(),
            autosplit.Candidate("x", 0.0, 144.0, 1, 0.0),
            profile,
            orientation_candidates=3,
            cancelled=signal,
            connector_count=pins.PIN_COUNT,
        )


def test_the_decomposition_path_checks_cancellation_before_vhacd(profile: Profile) -> None:
    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        autosplit._from_decomposition(crossed_overhangs(), "x", (-10.0, 10.0), cancelled=signal)


def test_the_decomposition_path_checks_cancellation_after_vhacd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signal = CancelSignal()
    mesh = crossed_overhangs()

    def decompose_and_cancel(_mesh: MeshData) -> list[MeshData]:
        signal.cancel()
        return [mesh, mesh]

    monkeypatch.setattr(autosplit, "convex_parts", decompose_and_cancel)

    with pytest.raises(OperationCancelled):
        autosplit._from_decomposition(mesh, "x", (-10.0, 10.0), cancelled=signal)


def test_support_aware_split_reports_monotonic_progress(profile: Profile) -> None:
    seen: list[tuple[float, str]] = []

    outcome = autosplit.split_to_fit(
        crossed_overhangs(),
        profile,
        pins=0,
        progress=lambda fraction, text: seen.append((fraction, text)),
    )

    assert outcome.divided
    fractions = [fraction for fraction, _text in seen]
    assert fractions == sorted(fractions)
    assert fractions[-1] == pytest.approx(1.0)
    assert any(text for _fraction, text in seen[:-1]), "der Balken nennt die laufende Arbeit"


def test_cancellation_during_plane_search_starts_no_final_cut(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    signal = CancelSignal()

    def find_and_cancel(*_args: object, **_kwargs: object) -> autosplit.Candidate:
        signal.cancel()
        return autosplit.Candidate("x", 0.0, 2400.0, 1, 0.0)

    monkeypatch.setattr(autosplit, "find_plane", find_and_cancel)
    monkeypatch.setattr(
        autosplit,
        "_cut_in_two",
        lambda *_args: pytest.fail("nach dem Abbruch begann noch der endgültige Schnitt"),
    )

    with pytest.raises(OperationCancelled):
        autosplit.split_to_fit(bar(), profile, cancelled=signal)


def test_cancellation_after_the_final_cut_starts_no_pin_plan(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    signal = CancelSignal()
    half = MeshData.of(trimesh.creation.box(extents=(200.0, 60.0, 40.0)))

    def cut_and_cancel(*_args: object) -> tuple[MeshData, MeshData]:
        signal.cancel()
        return half, half

    monkeypatch.setattr(
        autosplit,
        "find_plane",
        lambda *_args, **_kwargs: autosplit.Candidate("x", 0.0, 2400.0, 1, 0.0),
    )
    monkeypatch.setattr(autosplit, "_cut_in_two", cut_and_cancel)
    monkeypatch.setattr(autosplit, "_pin_allowance", lambda *_args, **_kwargs: 0.0)
    monkeypatch.setattr(
        pins,
        "plan_pins",
        lambda *_args, **_kwargs: pytest.fail("nach dem Abbruch begann noch die Stiftplanung"),
    )

    with pytest.raises(OperationCancelled):
        autosplit.split_to_fit(bar(), profile, cancelled=signal)


def test_cancelled_pin_allowance_starts_no_pin_plan(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    signal = CancelSignal()
    signal.cancel()
    monkeypatch.setattr(
        pins,
        "plan_pins",
        lambda *_args, **_kwargs: pytest.fail("nach dem Abbruch begann noch die Stiftplanung"),
    )

    with pytest.raises(OperationCancelled):
        autosplit._pin_allowance(bar(), "x", profile, pins.PIN_COUNT, cancelled=signal)


def test_pin_allowance_stops_after_pin_planning(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    signal = CancelSignal()
    original = pins.plan_pins

    def plan_and_cancel(*args: object, **kwargs: object):
        plan = original(*args, **kwargs)
        signal.cancel()
        return plan

    monkeypatch.setattr(pins, "plan_pins", plan_and_cancel)

    with pytest.raises(OperationCancelled):
        autosplit._pin_allowance(bar(), "x", profile, pins.PIN_COUNT, cancelled=signal)


def test_split_stops_after_final_connector_planning(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    signal = CancelSignal()
    original = pins.plan_pins
    calls = 0

    def plan_and_cancel_final(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        plan = original(*args, **kwargs)
        if calls == 2:
            signal.cancel()
        return plan

    monkeypatch.setattr(pins, "plan_pins", plan_and_cancel_final)
    monkeypatch.setattr(
        autosplit,
        "find_plane",
        lambda *_args, **_kwargs: autosplit.Candidate("x", 0.0, 2400.0, 1, 0.0),
    )

    with pytest.raises(OperationCancelled):
        autosplit.split_to_fit(bar(), profile, max_parts=2, cancelled=signal)
    assert calls == 2


def test_plan_split_stops_after_counting_fitting_pins(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import split as split_core

    signal = CancelSignal()
    outcome = autosplit.split_to_fit(bar(), profile)
    original = split_core.plan_pins

    def plan_and_cancel(*args: object, **kwargs: object):
        plan = original(*args, **kwargs)
        signal.cancel()
        return plan

    monkeypatch.setattr(split_core, "split_to_fit", lambda *_args, **_kwargs: outcome)
    monkeypatch.setattr(split_core, "plan_pins", plan_and_cancel)

    with pytest.raises(OperationCancelled):
        plan_split(bar(), "obj_1", profile, cancelled=signal)


def test_final_progress_cancellation_applies_no_split(profile: Profile) -> None:
    """Auch ein Abbruch am 100-Prozent-Signal lässt das Dokument unangetastet."""
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 400.0, "depth": 60.0, "height": 40.0})],
    )
    mesh = bar()
    signal = CancelSignal()
    before_ops = tuple(project.document.ops)
    before_fits = tuple(project.document.fits)
    before_transactions = tuple(project.document.transactions)

    def cancel_at_the_end(fraction: float, _text: str) -> None:
        if fraction >= 1.0:
            signal.cancel()

    with pytest.raises(OperationCancelled):
        apply_split(
            project.document,
            mesh,
            "obj_1",
            profile,
            pins=0,
            cancelled=signal,
            progress=cancel_at_the_end,
        )

    assert tuple(project.document.ops) == before_ops
    assert tuple(project.document.fits) == before_fits
    assert tuple(project.document.transactions) == before_transactions


def test_auto_dovetails_take_part_in_the_support_choice(profile: Profile) -> None:
    """Die Nahtsuche bewertet die Verbinder, die Auto Split wirklich baut.

    Der analytische Körper erweitert den Balken aus ``crossed_overhangs`` auf
    einen 22 × 22-mm-Querschnitt. Damit wählt T4 an allen guten Nähten echte
    Schwalbenschwänze. Ohne sie gewinnt die rechte Naht sehr deutlich; mit der
    heute gerundeten Verbindergeometrie bleibt sie vorn, aber mit den
    tatsächlich höheren Stützvolumen beider Nähte. Der direkte Vergleich hält
    fest, dass T2 die finale Geometrie und nicht bloß nackte Hälften beurteilt.
    """
    from app.core.knowledge.parts import PARTS

    PARTS.all()
    wide_beam = trimesh.creation.box(extents=(400.0, 22.0, 22.0))
    wide_beam.apply_translation((0.0, 0.0, 11.0))
    mesh = MeshData.of(trimesh.boolean.union([crossed_overhangs().raw, wide_beam]))
    left = autosplit.Candidate("x", -3.25, 484.0, 1, 0.0)
    right = autosplit.Candidate("x", 3.25, 484.0, 1, 0.0)

    def final_support(candidate: autosplit.Candidate) -> float:
        first, second = autosplit._cut_in_two(mesh, candidate)
        assert first is not None and second is not None
        plan = pins.plan_pins(mesh, candidate.plane, count=pins.PIN_COUNT, shape=pins.AUTO)
        assert plan.shape == "dovetail"
        pair = pins.add_pins(first, second, plan, profile, quality="draft")
        return sum(
            best_face_candidate(part, count=3, profile=profile).support_volume
            for part in (pair.first, pair.second)
        )

    bare_left = autosplit._support_after_cut(
        mesh, left, profile, orientation_candidates=3, cancelled=None
    )
    bare_right = autosplit._support_after_cut(
        mesh, right, profile, orientation_candidates=3, cancelled=None
    )
    left_final = final_support(left)
    right_final = final_support(right)
    evaluated_left = autosplit._support_after_cut(
        mesh,
        left,
        profile,
        orientation_candidates=3,
        cancelled=None,
        connector_count=pins.PIN_COUNT,
    )
    evaluated_right = autosplit._support_after_cut(
        mesh,
        right,
        profile,
        orientation_candidates=3,
        cancelled=None,
        connector_count=pins.PIN_COUNT,
    )

    assert bare_right < bare_left * 0.5
    assert right_final < left_final * (1.0 - autosplit.SUPPORT_TIE)
    assert evaluated_left == pytest.approx(left_final)
    assert evaluated_right == pytest.approx(right_final)

    chosen = autosplit.find_plane(mesh, profile)

    assert chosen is not None
    assert chosen.position == pytest.approx(right.position)


def test_a_seam_with_several_bridges_loses(profile: Profile) -> None:
    """Zwei Arme nebeneinander: quer durch beide zu schneiden ist schlechter,
    als die Verbindung zu schneiden.
    """
    left = trimesh.creation.box(extents=(300.0, 20.0, 20.0))
    left.apply_translation((0.0, -40.0, 10.0))
    right = trimesh.creation.box(extents=(300.0, 20.0, 20.0))
    right.apply_translation((0.0, 40.0, 10.0))
    joint = trimesh.creation.box(extents=(40.0, 100.0, 20.0))
    joint.apply_translation((0.0, 0.0, 10.0))
    fork = MeshData.of(trimesh.boolean.union([left, right, joint]))

    candidate = autosplit.find_plane(fork, profile)

    assert candidate is not None
    assert candidate.contours == 1
    assert abs(candidate.position) <= 20.0, "through the joint, not through both arms"


def test_the_seam_avoids_the_narrowest_place(profile: Profile) -> None:
    """§22.3, Festigkeit: durch die dünnste Stelle wird nicht getrennt.

    Eine Hantel — dicke Enden, eine Einschnürung in der Mitte. Bis hierher
    gewann genau diese Stelle: Sie hat **eine** Kontur, der Querschnitt ist
    dort am kleinsten, und sie liegt in der Mitte, also trugen alle drei
    bisherigen Terme sie. Gedruckt bricht das Teil dann an der Naht, denn
    quer zur Schicht ist die Verbindung ohnehin am schwächsten, und sie sitzt
    am dünnsten Querschnitt.

    Der Unterschied zu ``test_the_plane_lands_in_the_slim_middle`` ist die
    **Form** der dünnen Stelle, nicht ihre Dicke: Dort ist die Taille
    prismatisch, verläuft also über eine Strecke gleich — hier ist sie ein
    Minimum an einem Punkt. Die prismatische Taille bleibt die richtige Naht;
    verboten ist nur die Kerbe.
    """
    candidate = autosplit.find_plane(dumbbell(), profile)

    assert candidate is not None
    assert candidate.axis == "x", "quer zur langen Richtung"
    # Gemessen liegt das Minimum bei x = 0 mit 201 mm², die Flanken steigen
    # binnen fünfzehn Millimetern auf das Doppelte. Alles innerhalb von zehn
    # Millimetern um die Mitte ist die Kerbe.
    assert abs(candidate.position) > 10.0, (
        f"die Naht liegt bei {candidate.position:.1f} und damit in der Einschnürung — "
        "dort bricht das gedruckte Teil"
    )
    assert candidate.area > 400.0, (
        f"der Querschnitt der Naht ist {candidate.area:.0f} mm² und damit nahe am Minimum von 201"
    )


def test_a_prismatic_waist_is_still_the_right_seam(profile: Profile) -> None:
    """Die Gegenprobe zur Regel darüber, und sie ist die wichtigere Hälfte.

    Eine Einschnürung zu meiden ist nur dann richtig, wenn eine **prismatische**
    Taille weiterhin gewinnt — sonst hat die neue Regel die alte umgeworfen,
    statt sie zu ergänzen. ``oversized.stl`` hat genau so eine Taille, und die
    Naht gehört hinein.

    Steht dieser Test rot, ist der Einschnürungsterm zu grob: Er bestraft dann
    jede dünne Stelle statt nur die spitze.
    """
    candidate = autosplit.find_plane(body(), profile)

    assert candidate is not None
    assert candidate.area == pytest.approx(40.0 * 30.0), "weiterhin der Querschnitt der Mitte"


def shield(low: float, high: float, y: float = 30.0, z: float = 20.0) -> np.ndarray:
    """Die Eckpunkte einer geschützten Fläche auf der Oberseite eines Balkens.

    Sie steht für das, was in der Anwendung aus ``Feature.face_indices`` kommt:
    die Punkte der angeklickten Fläche. Koordinaten und keine Indizes, denn ein
    Teilstück ist ein neues Netz mit neuer Nummerierung — eine Sperre über
    Indizes wäre nach dem ersten Schnitt verloren, und genau die Fälle mit
    mehreren Schnitten sind die, für die es sie gibt.
    """
    return np.array(
        [[x, side, z] for x in (low, high) for side in (-y, y)],
        dtype=float,
    )


def test_a_protected_face_pushes_the_seam_aside(profile: Profile) -> None:
    """T8, §22.3: „Diese Fläche soll schön bleiben."

    Die Naht darf durch eine gesperrte Fläche nicht hindurch. Gemessen wird
    gegen den ungesperrten Lauf desselben Körpers und nicht gegen eine
    abgelesene Zahl: Wo die Naht ohne Sperre liegt, entscheidet die Bewertung,
    und die ändert sich mit jedem neuen Term.
    """
    whole = bar()
    free = autosplit.find_plane(whole, profile)
    assert free is not None and free.axis == "x"

    guard = shield(free.position - 6.0, free.position + 6.0)
    guarded = autosplit.find_plane(whole, profile, protect=[guard])

    assert guarded is not None, "neben der Sperre bleibt Platz, also gibt es eine Naht"
    assert not (guard[:, 0].min() < guarded.position < guard[:, 0].max()), (
        f"die Naht liegt bei {guarded.position:.1f} und damit in der geschützten Fläche "
        f"({guard[:, 0].min():.1f} bis {guard[:, 0].max():.1f})"
    )


def test_a_face_across_the_whole_window_leaves_no_seam(profile: Profile) -> None:
    """Deckt die Sperre jede mögliche Naht, gibt es keine — und das wird gesagt.

    ``find_plane`` antwortet mit ``None``, wie bei einem Körper, den Schneiden
    nicht rettet. Was die Oberfläche daraus macht, ist die Wahl mit ihrem Preis
    (Sperre aufheben, trotzdem trennen, von Hand trennen) — hier steht nur, dass
    der Kern nicht heimlich doch hindurchschneidet.
    """
    whole = bar()

    assert autosplit.find_plane(whole, profile, protect=[shield(-200.0, 200.0)]) is None


def test_the_plan_carries_the_guard_into_its_drafts(profile: Profile) -> None:
    """Die Sperre muss bis in die Operationen des Plans durchschlagen.

    ``plan_split`` ist die Brücke zwischen der Suche und dem Verlauf: Es sucht
    die Schnitte und macht ``split_pinned``-Schritte daraus. Ohne diesen Test
    wäre das Durchreichen von ``protect`` ungeprüft — und eine Zeile, deren
    Entfernen nichts rot macht, prüft nichts.

    **Warum die Sperre nicht in der Operation steht:** Was der Verlauf
    festhält, ist die gefundene Ebene mit Achse und Position, und daraus
    entsteht dasselbe Ergebnis, gleich wie sie gefunden wurde. Ein
    ``protect``-Parameter an ``split_pinned`` wäre einer, den niemand
    auswertet — die Suche hat da längst stattgefunden.
    """
    whole = bar()
    free = plan_split(whole, "obj_1", profile)
    assert free.drafts, "ungesperrt wird geteilt"
    seam = float(free.drafts[0].params["position"])

    guard = shield(seam - 6.0, seam + 6.0)
    guarded = plan_split(whole, "obj_1", profile, protect=[guard])

    assert guarded.drafts, "neben der Sperre bleibt Platz"
    for draft in guarded.drafts:
        position = float(draft.params["position"])
        assert not (guard[:, 0].min() < position < guard[:, 0].max()), (
            f"ein Schritt des Plans schneidet bei {position:.1f} durch die Sperre"
        )


def test_the_second_opinion_obeys_the_guard(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch die konvexe Zerlegung darf nicht durch eine gesperrte Fläche.

    ``find_plane`` hat zwei Wege zu einer Naht: die abgetasteten Ebenen und,
    wenn die alle mittelmäßig sind, die konvexe Zerlegung als zweite Meinung.
    Eine Sperre, die nur den ersten Weg kennt, hätte im **schwierigen** Fall
    keine Wirkung — also genau dort, wo es darauf ankommt.

    **Warum die Schwelle hier gesetzt wird.** Gemessen an den Körpern dieses
    Korpus wird die zweite Meinung nie gefragt: Die beste abgetastete Ebene
    kommt auf 0,000 bis 0,070 und bleibt damit weit unter ``HINT_THRESHOLD``
    von 0,3. Ohne die gesetzte Schwelle prüft dieser Test also nichts — die
    Mutation „Sperre im Zerlegungsweg entfernen" blieb grün, und das ist der
    Grund, aus dem er überhaupt geschrieben wurde.

    Gemessen an dieser Gabel schlägt die Zerlegung x = −13,0 vor. Die Sperre
    reicht von −14 bis +14, also liegt der Vorschlag mitten darin, und seine
    Punktzahl ist besser als die der erlaubten Ebenen — ohne die Prüfung
    gewänne er.
    """
    monkeypatch.setattr(autosplit, "HINT_THRESHOLD", 0.0)
    left = trimesh.creation.box(extents=(300.0, 20.0, 20.0))
    left.apply_translation((0.0, -40.0, 10.0))
    right = trimesh.creation.box(extents=(300.0, 20.0, 20.0))
    right.apply_translation((0.0, 40.0, 10.0))
    joint = trimesh.creation.box(extents=(40.0, 100.0, 20.0))
    joint.apply_translation((0.0, 0.0, 10.0))
    fork = MeshData.of(trimesh.boolean.union([left, right, joint]))
    guard = np.array([[x, s, 20.0] for x in (-14.0, 14.0) for s in (-50.0, 50.0)], dtype=float)

    candidate = autosplit.find_plane(fork, profile, protect=[guard])

    assert candidate is not None
    assert not (-14.0 < candidate.position < 14.0), (
        f"die Naht liegt bei {candidate.position:.1f} und damit in der Sperre — "
        "die zweite Meinung hat sie umgangen"
    )


def test_the_guard_survives_the_second_cut(profile: Profile) -> None:
    """Ein Körper, der zweimal geteilt wird, hält die Sperre auch beim zweiten Mal.

    **Das ist der Test, an dem eine Sperre über Dreiecksindizes gescheitert
    wäre**: Nach dem ersten Schnitt sind die Stücke neue Netze, ihre Dreiecke
    tragen neue Nummern, und der Verweis zeigte ins Leere. Über Koordinaten
    trägt sie durch jeden Schnitt — deshalb steht die Entscheidung hier als
    Test und nicht nur als Satz in einer Karte.
    """
    whole = bar(600.0)
    free = autosplit.split_to_fit(whole, profile)
    assert len(free.cuts) >= 2, "sechshundert Millimeter brauchen zwei Schnitte"

    second = free.cuts[1].plane.position
    guard = shield(second - 6.0, second + 6.0)
    guarded = autosplit.split_to_fit(whole, profile, protect=[guard])

    assert guarded.divided, "geteilt wird trotzdem"
    for step in guarded.cuts:
        assert not (guard[:, 0].min() < step.plane.position < guard[:, 0].max()), (
            f"ein Schnitt liegt bei {step.plane.position:.1f} und damit in der Sperre"
        )


def test_a_body_twice_too_long_takes_two_cuts(profile: Profile) -> None:
    outcome = autosplit.split_to_fit(bar(600.0), profile)

    assert len(outcome.parts) == 3
    assert all(autosplit.fits(part, profile) for part in outcome.parts)


def test_every_piece_is_closed_and_nothing_is_lost(profile: Profile) -> None:
    """Das P10-Kriterium: jedes Teil wasserdicht, und das Volumen geht auf."""
    whole = body()
    outcome = autosplit.split_to_fit(whole, profile)

    assert outcome.divided
    assert all(part.is_watertight for part in outcome.parts)
    assert sum(part.volume for part in outcome.parts) == pytest.approx(whole.volume, rel=1e-6)
    assert all(autosplit.fits(part, profile) for part in outcome.parts)


def test_the_steps_say_which_piece_was_cut(profile: Profile) -> None:
    """Ohne das lässt sich der Stapel nicht bauen — der nächste Schnitt
    braucht ein Objekt.
    """
    outcome = autosplit.split_to_fit(bar(600.0), profile)

    assert [step.part_index for step in outcome.cuts] == [0, 1]


def test_the_search_stops_instead_of_cutting_forever(profile: Profile) -> None:
    outcome = autosplit.split_to_fit(bar(4000.0), profile, max_parts=4)

    assert len(outcome.parts) == 4
    assert "split.too_many_parts" in {finding.code for finding in outcome.findings}


def test_the_pin_overhang_counts_towards_the_bed(profile: Profile) -> None:
    """§25: Ein Passstift steht über die Schnittfläche, also ragt die
    verstiftete Hälfte weiter als ihr nacktes Netz.

    ``oversize`` mit Zugabe rechnet ihn mit; ohne Zugabe misst es das blanke
    Netz wie zuvor. Der Quader passt nackt genau aufs Bett.
    """
    limit = profile.printer.build_volume[0] - 2.0 * autosplit.MARGIN
    box = MeshData.of(trimesh.creation.box(extents=(limit, 40.0, 40.0)))

    assert autosplit.oversize(box, profile)[0] == pytest.approx(0.0), "nackt passt es genau"
    assert autosplit.oversize(box, profile, allowance=(7.0, 0.0, 0.0))[0] == pytest.approx(7.0)


def test_a_half_with_its_pin_stays_on_the_bed(profile: Profile) -> None:
    """§25: Auto Split rechnet den Stiftüberstand ein und teilt feiner.

    Der Quader ist zwei Bettlängen weniger sechs Millimeter lang: eine einzige
    Naht ließe beide Hälften nackt aufs Bett passen — knapp. Mit Stift stünde
    jede darüber (gemessen 259,8 mm auf einem 252er Bett, bevor die Prüfung den
    Überstand kannte). Also entsteht ein dritter Schnitt, und keine Hälfte ragt
    mitsamt Stift über das Bett.
    """
    limit = profile.printer.build_volume[0] - 2.0 * autosplit.MARGIN
    box = MeshData.of(trimesh.creation.box(extents=(2.0 * limit - 6.0, 60.0, 60.0)))

    outcome = autosplit.split_to_fit(box, profile)

    assert len(outcome.parts) >= 3, "eine Naht reichte nackt, mit Stift nicht"
    for part in outcome.parts:
        seam = SectionPlane(autosplit.AXIS_NORMALS["x"], float(part.bounds.centre[0]))
        overhang = pins.plan_pins(part, seam).length / 2.0
        assert part.bounds.size[0] + overhang <= limit + autosplit.EPS_GEOM, (
            "Hälfte samt Stift bleibt auf dem Bett"
        )


def test_without_pins_the_bed_check_is_the_bare_extent(profile: Profile) -> None:
    """Die Gegenprobe: Wer ohne Stifte teilt, bekommt keine Zugabe.

    Derselbe Quader wie oben, aber ``pins=0``. Ohne Stift steht nichts über, die
    alte Rechnung bleibt, und eine einzige Naht genügt.
    """
    limit = profile.printer.build_volume[0] - 2.0 * autosplit.MARGIN
    box = MeshData.of(trimesh.creation.box(extents=(2.0 * limit - 6.0, 60.0, 60.0)))

    outcome = autosplit.split_to_fit(box, profile, pins=0)

    assert len(outcome.parts) == 2, "nackt reicht eine Naht"


def test_convex_parts_take_an_l_apart(profile: Profile) -> None:
    """§22.3: die Zerlegung findet, wo ein L von selbst auseinanderfällt.

    Dieser Test übersprang sich früher, wenn die Antwort leer war, und die
    Antwort war immer leer: der Aufruf übergab ein ``randomizeSeed``, das dieses
    V-HACD nicht hat, der TypeError wurde als „Modul fehlt" gelesen, und der
    ganze Hinweispfad der Ebenensuche war hinter einer grünen Suite tot. Also:
    kein Skip. Ist V-HACD installiert, muss es liefern, und die Ecke des L ist
    das, was es finden muss.
    """
    shape = trimesh.boolean.union(
        [
            trimesh.creation.box(extents=(60.0, 20.0, 20.0)),
            trimesh.creation.box(extents=(20.0, 20.0, 60.0)).apply_translation([20.0, 0.0, 40.0]),
        ]
    )
    parts = autosplit.convex_parts(MeshData.of(shape))

    assert len(parts) >= 2, "an L is not convex"
    assert sum(abs(part.volume) for part in parts) == pytest.approx(abs(shape.volume), rel=0.05)
    assert [abs(part.volume) for part in parts] == sorted(
        (abs(part.volume) for part in parts), reverse=True
    ), "largest first, as documented"


def test_convex_parts_are_reproducible(profile: Profile) -> None:
    """§11.3: derselbe Körper gibt dieselben Stücke, ohne einen Startwert zu
    speichern.
    """
    shape = trimesh.boolean.union(
        [
            trimesh.creation.box(extents=(60.0, 20.0, 20.0)),
            trimesh.creation.box(extents=(20.0, 20.0, 60.0)).apply_translation([20.0, 0.0, 40.0]),
        ]
    )
    first = autosplit.convex_parts(MeshData.of(shape))
    second = autosplit.convex_parts(MeshData.of(shape))

    assert len(first) == len(second)
    assert [round(part.volume, 3) for part in first] == [round(part.volume, 3) for part in second]


# --- die Passstifte -------------------------------------------------------------


def connector_body(depth: float, face: float) -> MeshData:
    """Ein Nahtkörper mit getrennt messbarer Tiefe und Fügefläche.

    Getrennt wird bei x = 0. ``depth`` liegt damit hinter der Naht, ``face``
    spannt die quadratische Schnittfläche auf. So kann jede Grenze gegen
    denselben Körper variiert werden, statt Form und Messwert zugleich zu
    ändern.
    """
    return MeshData.of(trimesh.creation.box(extents=(depth, face, face)))


CONNECTOR_PLANE = SectionPlane(normal=(1.0, 0.0, 0.0), position=0.0)


@pytest.mark.parametrize("shape", ["round", "dovetail", "snap"])
def test_batched_connectors_equal_the_sequential_product_geometry(
    shape: str, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei Produktboolesche ergeben dieselben Körper wie bisher vier.

    Rundstift, Schwalbenschwanz und Schnapper durchlaufen denselben echten
    Baustein- und Booleschen Weg. Verglichen werden nicht nur Volumen, sondern
    ihr vollständiges gemeinsames Volumen, Wasserdichtheit, Merkmale, Befunde
    und Rückfallstufe. Die Dreiecksaufteilung der ebenen Naht darf abweichen.
    """
    from app.core.geom.boolean import shared_volume
    from app.core.knowledge.parts import PARTS

    PARTS.all()
    whole = connector_body(40.0, 40.0)
    candidate = autosplit.Candidate("x", 0.0, 1600.0, 1, 0.0)
    first, second = autosplit._cut_in_two(whole, candidate)
    assert first is not None and second is not None
    plan = pins.plan_pins(whole, CONNECTOR_PLANE, count=2, shape=shape)
    assert plan.count == 2

    sequential = pins.add_pins(first, second, plan, profile, quality="draft")
    calls: list[str] = []
    original = pins.boolean

    def record(kind: str, meshes: list[MeshData], **kwargs: object):
        calls.append(kind)
        return original(kind, meshes, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(pins, "boolean", record)
    batched = pins.add_pins(first, second, plan, profile, quality="draft", batch=True)

    assert calls == ["union", "difference"]
    assert batched.solver == sequential.solver
    assert batched.findings == sequential.findings
    assert batched.pin_features == sequential.pin_features
    assert batched.bore_features == sequential.bore_features
    for result, reference in (
        (batched.first, sequential.first),
        (batched.second, sequential.second),
    ):
        assert result.is_watertight == reference.is_watertight is True
        assert result.volume == pytest.approx(reference.volume, rel=1e-12)
        assert shared_volume(result.raw, reference.raw) == pytest.approx(
            abs(reference.volume), rel=1e-12
        )


def test_failed_connector_batch_uses_the_sequential_fallback(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der schnelle Versuch darf die bewährte Rückfallkette nie ersetzen."""
    from app.core.geom.boolean import shared_volume
    from app.core.knowledge.parts import PARTS

    PARTS.all()
    whole = connector_body(40.0, 40.0)
    candidate = autosplit.Candidate("x", 0.0, 1600.0, 1, 0.0)
    first, second = autosplit._cut_in_two(whole, candidate)
    assert first is not None and second is not None
    plan = pins.plan_pins(whole, CONNECTOR_PLANE, count=2, shape="round")
    reference = pins.add_pins(first, second, plan, profile, quality="draft")
    original = pins.boolean
    calls: list[tuple[str, object]] = []

    def fail_the_batch_once(kind: str, meshes: list[MeshData], **kwargs: object):
        calls.append((kind, kwargs.get("stages")))
        if len(calls) == 1:
            raise BooleanFailedError(detail="erzwungene Batch-Gegenprobe", attempted=("direct",))
        return original(kind, meshes, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(pins, "boolean", fail_the_batch_once)
    result = pins.add_pins(first, second, plan, profile, quality="draft", batch=True)

    assert calls == [
        ("union", ("direct",)),
        ("union", None),
        ("difference", None),
        ("union", None),
        ("difference", None),
    ]
    assert result.solver == reference.solver
    assert shared_volume(result.first.raw, reference.first.raw) == pytest.approx(
        abs(reference.first.volume), rel=1e-12
    )
    assert shared_volume(result.second.raw, reference.second.raw) == pytest.approx(
        abs(reference.second.volume), rel=1e-12
    )


def test_auto_connector_uses_a_dovetail_on_a_roomy_joining_face() -> None:
    """Zwei getrennte Verbinderplätze machen die Fläche geeignet.

    Die Wahl beruht nicht auf einem Modellnamen: Gemessen werden die
    zusammenhängende Fügefläche und der Abstand der bereits geplanten Sitze
    gegen deren Hülle aus Durchmesser plus verbleibender Wand.
    """
    plan = pins.plan_pins(connector_body(40.0, 40.0), CONNECTOR_PLANE, shape="auto")

    assert plan.shape == "dovetail"
    assert plan.choice is not None
    assert plan.choice.face_area >= plan.choice.required_face_area
    assert plan.choice.seat_spacing >= plan.choice.required_seat_spacing
    assert plan.choice.requires_glue is False


def test_auto_connector_uses_a_snap_when_only_the_depth_is_roomy() -> None:
    """Eine schmale Fläche trägt keinen Schwalbenschwanz, aber einen Arm.

    Die Gegenprobe trennt die zwei Richtungen: Quer zur Naht liegen die Sitze
    zu dicht für zwei Schwalbenschwänze, hinter ihr stehen mehr als acht
    Millimeter für den Federarm.
    """
    plan = pins.plan_pins(connector_body(40.0, 12.0), CONNECTOR_PLANE, shape="auto")

    assert plan.shape == "snap"
    assert plan.choice is not None
    assert plan.choice.seat_spacing < plan.choice.required_seat_spacing
    assert plan.choice.material_depth >= plan.choice.required_material_depth
    assert plan.length / 2.0 >= pins.SNAP_MIN_REACH
    assert plan.choice.requires_glue is False


def test_auto_connector_uses_round_pins_and_says_glue_when_both_are_tight() -> None:
    """Ohne breite Fläche und Federweg bleibt die gutmütige Klebenaht.

    Rund ist hier kein stiller Standard: Der Plan weist die beiden
    unterschrittenen Messgrößen aus und gibt den vorhandenen Kleberhinweis
    als Befund zurück.
    """
    plan = pins.plan_pins(connector_body(12.0, 12.0), CONNECTOR_PLANE, shape="auto")

    assert plan.shape == "round"
    assert plan.choice is not None
    assert plan.choice.seat_spacing < plan.choice.required_seat_spacing
    assert plan.choice.material_depth < plan.choice.required_material_depth
    assert plan.choice.requires_glue is True
    assert [finding.code for finding in plan.findings] == ["split.connector_glue"]
    assert "Kleber" in str(plan.findings[0].message)


def test_an_explicit_round_choice_is_not_overwritten_by_the_automatic_rule() -> None:
    """T4 gilt nur für Auto Split; eine ausdrückliche Form bleibt bestehen."""
    plan = pins.plan_pins(connector_body(40.0, 40.0), CONNECTOR_PLANE, shape="round")

    assert plan.shape == "round"
    assert plan.choice is None
    assert not plan.findings


def test_the_connector_suggestion_is_deterministic() -> None:
    """§11.3: gleiche Nahtmessung, gleiche Form und dieselben Messwerte."""
    body = connector_body(40.0, 12.0)

    first = pins.plan_pins(body, CONNECTOR_PLANE, shape="auto")
    second = pins.plan_pins(body, CONNECTOR_PLANE, shape="auto")

    assert first.shape == second.shape
    assert first.choice == second.choice
    assert first.findings == second.findings


def test_a_perforated_corpus_plate_does_not_get_a_false_connector() -> None:
    """Der reale Lochplattenkörper widerlegt die Entscheidung nach Fläche allein.

    ``plate_holes.stl`` hat 796 Dreiecke, vier Durchgangsbohrungen und bei
    z = 4 eine große, gelochte Fügefläche. Hinter ihr stehen aber nur vier
    Millimeter Material je Hälfte. Das trägt nicht einmal den kleinsten
    sinnvollen Stift samt Restwand; ein Schwalbenschwanz oder Federarm wäre
    deshalb eine falsche Zusage. Derselbe zweite Lauf ist die
    Determinismus-Gegenprobe am Korpuskörper.
    """
    perforated = body("plate_holes.stl")
    plane = SectionPlane(normal=(0.0, 0.0, 1.0), position=float(perforated.bounds.centre[2]))

    first = pins.plan_pins(perforated, plane, shape="auto")
    second = pins.plan_pins(perforated, plane, shape="auto")

    assert perforated.triangle_count == 796, "der Test benutzt den komplexen Korpuskörper"
    assert first == second
    assert first.shape == "round"
    assert first.count == 0 and first.choice is None
    assert [finding.code for finding in first.findings] == ["split.seam_too_thin"]
    values = first.findings[0].values
    assert values["depth_mm"] < values["needed_mm"], values


def test_the_round_fallback_still_builds_two_watertight_halves(profile: Profile) -> None:
    """Der Hinweis ersetzt die Geometrie nicht: Rundstift und Bohrung entstehen."""
    whole = connector_body(12.0, 12.0)
    first, second, findings = split_at_plane(whole, CONNECTOR_PLANE)
    assert not findings
    plan = pins.plan_pins(whole, CONNECTOR_PLANE, shape="auto")

    pair = pins.add_pins(first, second, plan, profile)

    assert plan.shape == "round"
    assert pair.first.is_watertight and pair.second.is_watertight
    assert len(pair.pin_features) == len(pair.bore_features) == plan.count
    assert [finding.code for finding in pair.findings] == ["split.connector_glue"]


def test_pins_sit_inside_the_cut_face(profile: Profile) -> None:
    whole = body()
    candidate = autosplit.find_plane(whole, profile)
    assert candidate is not None

    plan = pins.plan_pins(whole, candidate.plane)

    assert plan.count == 2, "one pin is a hinge"
    assert pins.PIN_MIN <= plan.diameter <= pins.PIN_MAX
    for position in plan.positions:
        assert position[0] == pytest.approx(candidate.position), "on the parting plane"
        assert abs(position[1]) < 20.0 and 5.0 < position[2] < 35.0, "inside the middle bar"


def test_a_face_too_small_gets_no_pins_and_says_so(profile: Profile) -> None:
    """Eine Naht ohne Stifte klebt immer noch; ein Stift durch die Wand nicht."""
    thin = MeshData.of(trimesh.creation.box(extents=(400.0, 3.0, 3.0)))
    candidate = autosplit.find_plane(thin, profile)
    assert candidate is not None

    plan = pins.plan_pins(thin, candidate.plane)

    assert plan.count == 0
    assert [finding.code for finding in plan.findings] == ["split.face_too_small"]


def wall(thickness: float) -> MeshData:
    """Eine Trennwand: große Fläche, wenig Material dahinter.

    Der Fall, den die Schnittfläche allein nicht erkennt. Der Schnitt bei
    y = 0 liefert 100 mal 100 Millimeter — reichlich Platz für zwei Stifte samt
    Wand —, und in Richtung der Stiftachse steht die halbe Wandstärke. So sieht
    jede Trennwand eines Kastens aus.
    """
    return MeshData.of(trimesh.creation.box(extents=(100.0, thickness, 100.0)))


#: Die Ebene quer durch eine solche Wand. Ihre Normale ist die Stiftachse.
WALL_PLANE = SectionPlane(normal=(0.0, 1.0, 0.0), position=0.0)


def usable_in(thickness: float) -> float:
    """Die Einbindung, die eine Wand dieser Dicke hergibt.

    Die halbe Wand, abzüglich des Freistichs, um den die Bohrung tiefer reicht
    als der Stift, und einer Wandstärke, die hinter ihr stehen bleiben muss.
    """
    return thickness / 2.0 - pins.BORE_RELIEF - pins.PIN_WALL


def test_a_seam_with_nothing_behind_it_gets_no_pins_and_says_so(profile: Profile) -> None:
    """Eine 3-mm-Wand trägt keinen Stift, so groß ihre Schnittfläche auch ist.

    Gemessen am Besteckkorb gefunden: zehn geplante Stifte, je 12 mm tief, und
    an jeder Stelle 1,5 mm Material. Die Stifte standen im Fach, die Bohrungen
    gingen durch die Wand, und gemeldet wurde nichts — die Fläche war ja groß
    genug. Sie ist die falsche Größe: quer ist nicht tief.
    """
    plan = pins.plan_pins(wall(3.0), WALL_PLANE)

    assert plan.count == 0
    assert [finding.code for finding in plan.findings] == ["split.seam_too_thin"]
    values = plan.findings[0].values
    assert values["depth_mm"] == pytest.approx(1.5), "die halbe Wandstärke steht zur Verfügung"
    assert values["needed_mm"] > values["depth_mm"], "und sie reicht nicht"


def test_a_thick_enough_seam_keeps_the_full_pin(profile: Profile) -> None:
    """Wo Material steht, ändert die Messung nichts.

    Die Gegenprobe zum Fall darüber: derselbe Körper, nur 40 mm dick. Der Stift
    bekommt seine volle Länge — anderthalb Durchmesser je Hälfte —, und kein
    Befund entsteht.
    """
    plan = pins.plan_pins(wall(40.0), WALL_PLANE)

    assert plan.count == 2
    assert plan.diameter == pytest.approx(pins.PIN_MAX), "die Fläche gibt den dicksten her"
    assert plan.length == pytest.approx(plan.diameter * pins.PIN_DEPTH_FACTOR * 2.0)
    assert not plan.findings


def test_a_tight_seam_shortens_the_pin_instead_of_dropping_it(profile: Profile) -> None:
    """Dazwischen wird gekürzt, nicht verworfen.

    24 mm Wand heißt 12 mm je Seite und damit 10 mm Einbindung — weniger als
    die 12 mm, die ein Stift von 8 mm gern hätte, und mehr als die 6 mm, unter
    denen er nichts mehr führt. Der Durchmesser bleibt, die Länge gibt nach.
    """
    plan = pins.plan_pins(wall(24.0), WALL_PLANE)

    assert plan.count == 2
    assert plan.diameter == pytest.approx(pins.PIN_MAX), "quer ist Platz genug"
    reach = plan.length / 2.0
    assert reach == pytest.approx(usable_in(24.0))
    assert reach < plan.diameter * pins.PIN_DEPTH_FACTOR, "gekürzt gegenüber dem Wunsch"


def test_a_tighter_seam_thins_the_pin_before_giving_up(profile: Profile) -> None:
    """Und darunter wird er dünner, nicht keiner.

    12 mm Wand geben 4 mm Einbindung. Für einen Stift von 8 mm ist das zu
    wenig — er bräuchte 6 —, aber Einbindung und Durchmesser hängen aneinander:
    ein dünnerer kommt mit weniger aus. Gewählt wird der dickste, der noch
    sitzt, und das ist die Rechnung rückwärts.
    """
    plan = pins.plan_pins(wall(12.0), WALL_PLANE)

    assert plan.count == 2
    assert pins.PIN_MIN <= plan.diameter < pins.PIN_MAX, "dünner, aber nicht zu dünn"
    reach = plan.length / 2.0
    assert reach == pytest.approx(usable_in(12.0))
    assert reach == pytest.approx(plan.diameter * pins.PIN_MIN_ENGAGEMENT), "gerade noch führend"


def test_the_pin_goes_into_one_half_and_the_bore_into_the_other(profile: Profile) -> None:
    whole = body()
    candidate = autosplit.find_plane(whole, profile)
    assert candidate is not None
    first, second, _findings = split_at_plane(whole, candidate.plane)
    plan = pins.plan_pins(whole, candidate.plane)

    pair = pins.add_pins(first, second, plan, profile)

    assert pair.first.is_watertight and pair.second.is_watertight
    assert pair.first.volume > first.volume, "the pins add material"
    assert pair.second.volume < second.volume, "the bores take it away"
    assert sorted(pair.pin_features) == ["pin_1", "pin_2"]
    assert sorted(pair.bore_features) == ["bore_1", "bore_2"]


def test_the_play_comes_from_the_material_profile(profile: Profile) -> None:
    """Regel 7: die Bohrung ist der Stift plus das kalibrierte Spiel, nie ein
    Literal.
    """
    whole = body()
    candidate = autosplit.find_plane(whole, profile)
    assert candidate is not None
    first, second, _findings = split_at_plane(whole, candidate.plane)
    plan = pins.plan_pins(whole, candidate.plane)

    pair = pins.add_pins(first, second, plan, profile)

    pin = pair.pin_features["pin_1"].params["diameter"]
    bore = pair.bore_features["bore_1"].params["diameter"]
    assert bore - pin == pytest.approx(profile.material.clearance)


# --- Als Operation ---------------------------------------------------------------


def run(op: str, entry: SceneObject, profile: Profile, **params: object):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_split_pinned_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Balken", mesh=body())

    result = run("split_pinned", entry, profile, axis="x", position=0.0, pins=2)

    assert [str(output.name) for output in result.outputs] == [
        "Balken A · Stifte",
        "Balken B · Löcher",
    ], "beim Export ist der Name die einzige Auskunft darüber, welches Teil welches ist"
    assert all(output.mesh.is_watertight for output in result.outputs)
    assert "pin_1" in result.outputs[0].features
    assert "bore_1" in result.outputs[1].features


def test_split_pinned_can_also_just_cut(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Balken", mesh=body())

    result = run("split_pinned", entry, profile, axis="x", position=0.0, pins=0)

    assert not any("pin_1" in output.features for output in result.outputs)
    assert all(output.mesh.is_watertight for output in result.outputs)


def test_a_plane_that_misses_the_body_is_a_user_error(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Balken", mesh=body())

    with pytest.raises(ValidationError) as problem:
        run("split_pinned", entry, profile, axis="x", position=9999.0, pins=2)

    assert problem.value.field == "position"


# --- der ganze Weg --------------------------------------------------------------


@pytest.fixture
def loaded(profile: Profile) -> tuple[Project, MeshData]:
    project = new_project("centauri-carbon-2", "petg")
    payload = (MESHES / "oversized.stl").read_bytes()
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/oversized.stl", sha256=""
    )
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    return project, result.scene.objects["obj_1"].mesh


def test_the_plan_is_one_operation_per_cut(loaded, profile: Profile) -> None:
    _project, mesh = loaded

    plan = plan_split(mesh, "obj_1", profile)

    assert plan.cuts == 1
    assert all(draft.op == "split_pinned" for draft in plan.drafts)
    assert plan.drafts[0].params["axis"] == "x"


def test_auto_split_stores_its_connector_suggestion_in_every_step(profile: Profile) -> None:
    """Die Messung wird ein Parameter und nicht bloß eine flüchtige Meinung.

    Nur so rechnet dieselbe Projektdatei beim nächsten Öffnen dieselbe Form.
    Der breite Balken bietet je Naht zwei getrennte Sitze und bekommt deshalb
    Schwalbenschwänze.
    """
    plan = plan_split(bar(600.0), "obj_1", profile)

    assert plan.drafts
    assert [draft.params["shape"] for draft in plan.drafts] == [
        step.connector_shape for step in plan.outcome.cuts
    ]
    assert all(draft.params["shape"] == "dovetail" for draft in plan.drafts)


def test_auto_split_stores_snap_for_a_deep_narrow_seam(profile: Profile) -> None:
    """Die zweite Form erreicht ebenfalls den wirklichen Operationsstapel."""
    narrow = MeshData.of(trimesh.creation.box(extents=(400.0, 12.0, 12.0)))

    first = plan_split(narrow, "obj_1", profile)
    second = plan_split(narrow, "obj_1", profile)

    assert first.drafts
    assert all(draft.params["shape"] == "snap" for draft in first.drafts)
    assert [draft.params for draft in first.drafts] == [draft.params for draft in second.drafts]


def test_auto_split_builds_the_suggested_snaps(profile: Profile) -> None:
    """Der schmale Fall endet nicht beim Parameter, sondern in echter Geometrie."""
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [
            OperationDraft(
                op="create_box",
                params={"width": 400.0, "depth": 12.0, "height": 12.0},
            )
        ],
    )
    narrow = MeshData.of(trimesh.creation.box(extents=(400.0, 12.0, 12.0)))

    applied = apply_split(project.document, narrow, "obj_1", profile)
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    split_ops = [entry for entry in project.document.ops if entry.op == "split_pinned"]
    assert split_ops and all(entry.params["shape"] == "snap" for entry in split_ops)
    assert result.complete
    assert all(
        result.scene.objects[object_id].mesh.is_watertight for object_id in applied.object_ids
    )
    assert applied.fits, "jeder erzeugte Schnapper bekommt sein Passungspaar"


def test_the_automatic_round_fallback_keeps_its_glue_hint(profile: Profile, tmp_path: Path) -> None:
    """Der notwendige Handgriff überlebt Projektdatei und Neuauswertung.

    Die konkrete Form allein reicht dafür nicht: ``round`` kann auch eine
    ausdrückliche Nutzerwahl sein. Auto Split hält deshalb zusätzlich fest,
    dass diese runden Stifte der Rückfall aus zu kleiner Fügefläche und zu
    kurzem Federweg waren. ``auto`` selbst reist nie in der Datei mit.
    """
    tight_profile = replace(
        profile,
        printer=replace(profile.printer, build_volume=(14.0, 256.0, 256.0)),
    )
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [
            OperationDraft(
                op="create_box",
                params={"width": 12.0, "depth": 12.0, "height": 12.0},
            )
        ],
    )
    tight = connector_body(12.0, 12.0)

    applied = apply_split(project.document, tight, "obj_1", tight_profile)
    split_ops = [entry for entry in project.document.ops if entry.op == "split_pinned"]

    assert [entry.params["shape"] for entry in split_ops] == ["round"]
    assert all(entry.params["shape"] != "auto" for entry in split_ops)
    assert [entry.params["glue_hint"] for entry in split_ops] == [True]
    assert [finding.code for finding in applied.findings] == ["split.connector_glue"]

    path = tmp_path / "rund-mit-kleberhinweis.p3d"
    save(project, path)
    reopened = load(path)
    result = evaluate(
        reopened.document,
        tight_profile,
        sources=ProjectSources(reopened, base_dir=path.parent),
    )

    reopened_split = [entry for entry in reopened.document.ops if entry.op == "split_pinned"]
    assert [entry.params["glue_hint"] for entry in reopened_split] == [True]
    assert result.complete
    assert [
        finding.code
        for finding in result.scene.report.findings
        if finding.code == "split.connector_glue"
    ] == ["split.connector_glue"]


def test_an_explicit_round_operation_does_not_claim_an_automatic_fallback(
    profile: Profile,
) -> None:
    """Die neue Herkunftsangabe ändert die manuelle Rundwahl nicht."""
    entry = SceneObject(id="obj_1", name="Balken", mesh=body())

    result = run(
        "split_pinned",
        entry,
        profile,
        axis="x",
        position=0.0,
        pins=2,
        shape="round",
    )

    assert "split.connector_glue" not in {finding.code for finding in result.findings}


def test_oversized_is_divided_without_anybody_touching_a_parameter(
    loaded, profile: Profile
) -> None:
    """Das P10-Abnahmekriterium, Ende zu Ende (§40)."""
    project, mesh = loaded

    applied = apply_split(project.document, mesh, "obj_1", profile)
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    split_ops = [entry for entry in project.document.ops if entry.op == "split_pinned"]
    assert split_ops and all(entry.params["shape"] == "dovetail" for entry in split_ops)
    assert len(applied.object_ids) == 2
    for object_id in applied.object_ids:
        part = result.scene.objects[object_id]
        assert part.mesh.is_watertight, object_id
        assert autosplit.fits(part.mesh, profile), object_id


def test_splitting_a_piece_again_keeps_its_existing_fits(profile: Profile) -> None:
    """Zweimal trennen erhält die erste Naht auf dem richtigen Kindstück.

    So gefunden: Sechs Fachmodule über fünf gezeichnete Schnitte, und danach
    nur vier statt zehn Verbindungsgruppen. Ein Teil in mehr als zwei Stücke zu
    schneiden heißt, ein schon geschnittenes noch einmal zu schneiden. Seine
    Passungen müssen deshalb mitwandern, während die neue Naht eigene,
    unverwechselbare Merkmalskennungen bekommt.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(80.0, 60.0, 40.0)))

    first = apply_line_split(
        project.document, "obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), profile, mesh=block
    )
    assert len(first.fits) == 2, "die erste Naht bekommt ihre Paare"
    assert project.document.fits == first.fits

    halved = evaluate(project.document, profile, sources=ProjectSources(project))
    target = first.object_ids[0]
    second = apply_line_split(
        project.document,
        target,
        SectionPlane((0.0, 1.0, 0.0), 0.0),
        profile,
        mesh=halved.scene.objects[target].mesh,
        features=halved.scene.objects[target].features,
    )

    assert not [finding for finding in second.findings if finding.code == "split.fit_dropped"]
    assert {fit.name for fit in first.fits} <= {fit.name for fit in project.document.fits}, (
        "die erste Naht bleibt unter ihrer Kennung erhalten"
    )
    assert len(project.document.fits) == 4, "beide Nähte tragen je zwei Passungen"
    assert [fit.a.feature_id for fit in second.fits] == ["pin_3", "pin_4"]
    assert [fit.b.feature_id for fit in second.fits] == ["bore_3", "bore_4"]

    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    codes = [finding.code for finding in result.scene.report.findings]
    assert "fit.missing_feature" not in codes, codes


def test_a_cut_through_an_existing_connector_drops_only_that_fit(profile: Profile) -> None:
    """Eine gestreifte Verbindung darf nicht als voll tragfähig weiterleben.

    Der Mittelpunkt allein reicht dafür nicht: Eine Ebene kann den Rand eines
    Stifts schneiden, obwohl sein Mittelpunkt eindeutig auf einer Seite liegt.
    Dann entfällt genau dieses Paar; die andere alte Verbindung bleibt erhalten.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(80.0, 60.0, 40.0)))
    first = apply_line_split(
        project.document, "obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), profile, mesh=block
    )
    halved = evaluate(project.document, profile, sources=ProjectSources(project))
    target = first.object_ids[0]
    entry = halved.scene.objects[target]
    pin = entry.features["pin_1"]
    centre = pin.params["centre"]
    diameter = float(pin.params["diameter"])
    plane = SectionPlane((0.0, 1.0, 0.0), float(centre[1]) + diameter / 4.0)

    second = apply_line_split(
        project.document,
        target,
        plane,
        profile,
        mesh=entry.mesh,
        features=entry.features,
    )

    assert [finding.code for finding in second.findings].count("split.fit_dropped") == 1
    assert first.fits[0] not in project.document.fits, "der angeschnittene Stift trägt nicht mehr"
    assert first.fits[1].name in {fit.name for fit in project.document.fits}
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert "fit.missing_feature" not in [finding.code for finding in result.scene.report.findings]


def test_undo_brings_the_dropped_fits_back(profile: Profile) -> None:
    """Und ein Undo holt sie zurück — sie reisen in der Transaktion.

    Die Passungen wurden bisher **nach** dem Aufruf ins Dokument geschrieben,
    also an der Transaktion vorbei: Ein Undo nahm die Teilung zurück und ließ
    die Paare stehen. Jetzt bildet ``History.apply`` sie aus den geplanten
    Operationen, und beides ist ein Schritt.
    """
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(80.0, 60.0, 40.0)))

    applied = apply_line_split(
        project.document, "obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), profile, mesh=block
    )
    assert project.document.fits == applied.fits

    History(project.document).undo()

    assert project.document.fits == [], "was die Teilung anlegte, nimmt das Undo mit"


def test_auto_split_leaves_no_dead_fit_after_two_cuts(profile: Profile) -> None:
    """Zwei Schnitte in **einem** Auto-Split-Lauf hinterlassen keine tote Passung.

    Auto Split legt je Schnitt ein Passungspaar an. Teilte ein späterer Schnitt
    desselben Laufs ein schon verstiftetes Stück noch einmal, blieben dessen
    Paare stehen und zeigten ins Leere: zwei ``fit.missing_feature`` im
    Prüfbericht, obwohl niemand einen Parameter angefasst hatte. Der Balken ist
    doppelt zu lang und braucht darum zwei Schnitte.

    Das Gegenstück zu ``test_splitting_a_piece_again_lets_its_fits_go``: dort
    zwei gezeichnete Schnitte in zwei Läufen, hier zwei aus einem Lauf — die
    entfielen bisher nur im Dokument, nicht im Lauf-Akkumulator, und der schrieb
    sie über ``change_for`` erneut hinein.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 600.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(600.0, 60.0, 40.0)))

    applied = apply_split(project.document, block, "obj_1", profile)

    assert len(applied.object_ids) == 3, "doppelt zu lang: zwei Schnitte, drei Stücke"
    assert [finding.code for finding in applied.findings].count("split.fit_dropped") == 2

    result = evaluate(project.document, profile, sources=ProjectSources(project))
    codes = [finding.code for finding in result.scene.report.findings]
    assert "fit.missing_feature" not in codes, codes

    live = set(applied.object_ids)
    for fit in project.document.fits:
        assert fit.a.object_id in live and fit.b.object_id in live, fit.name


def test_one_undo_restores_a_complete_multi_cut_auto_split(profile: Profile) -> None:
    """Mehrere Auto-Split-Nähte sind genau eine History-Transaktion."""
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 600.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(600.0, 60.0, 40.0)))
    before_ops = tuple(project.document.ops)
    before_fits = tuple(project.document.fits)
    before_transactions = tuple(project.document.transactions)

    original = evaluate(project.document, profile, sources=ProjectSources(project))
    assert set(original.scene.objects) == {"obj_1"}
    assert not autosplit.fits(original.scene.objects["obj_1"].mesh, profile)

    applied = apply_split(project.document, block, "obj_1", profile)

    assert len(applied.object_ids) == 3
    assert len(project.document.transactions) == len(before_transactions) + 1
    assert len(project.document.transactions[-1].ops) == 2
    assert project.document.fits

    History(project.document).undo()
    restored = evaluate(project.document, profile, sources=ProjectSources(project))

    assert tuple(project.document.ops) == before_ops
    assert tuple(project.document.fits) == before_fits
    assert tuple(project.document.transactions) == before_transactions
    assert set(restored.scene.objects) == {"obj_1"}
    restored_mesh = restored.scene.objects["obj_1"].mesh
    assert restored_mesh.volume == pytest.approx(block.volume)
    assert restored_mesh.bounds.size == pytest.approx(block.bounds.size)
    assert not autosplit.fits(restored_mesh, profile)


def test_the_seams_become_fit_pairs(loaded, profile: Profile) -> None:
    """§14: Auto Split legt die Paare an, denn dort entstehen sie."""
    project, mesh = loaded

    applied = apply_split(project.document, mesh, "obj_1", profile)

    assert [fit.tolerance for fit in applied.fits] == ["auto:petg", "auto:petg"]
    assert project.document.fits == applied.fits
    assert applied.fits[0].a.feature_id == "pin_1"
    assert applied.fits[0].b.feature_id == "bore_1"


def test_a_seam_without_pins_gets_no_fit_pair(profile: Profile) -> None:
    """Ein Paar, dessen beide Seiten es nicht gibt, ist schlimmer als keines.

    Ist die Schnittfläche für Stifte zu schmal, setzt ``plan_pins`` keinen und
    sagt das als Befund. Die Passung entstand hier trotzdem — und die
    Passungsprüfung meldete danach eine Verletzung an einem Teil, das in
    Ordnung ist.

    Der Balken ist genau dafür gebaut: vierhundert Millimeter lang, drei mal
    drei im Querschnitt. Er muss geteilt werden, und auf neun Quadratmillimeter
    passt kein Stift samt Wand.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 400.0, "depth": 3.0, "height": 3.0})],
    )
    thin = MeshData.of(trimesh.creation.box(extents=(400.0, 3.0, 3.0)))

    plan = plan_split(thin, "obj_1", profile)

    assert plan.cuts, "der Balken passt nicht auf das Bett und wird geteilt"
    assert all(count == 0 for count in plan.seated), "auf 3 × 3 mm sitzt kein Stift"

    applied = apply_planned(project.document, plan, "obj_1", profile)

    assert applied.fits == [], "keine Passung ohne Stift, auf den sie zeigt"
    assert project.document.fits == []


def test_the_pairs_hold_when_the_scene_is_checked(loaded, profile: Profile) -> None:
    project, mesh = loaded
    apply_split(project.document, mesh, "obj_1", profile)

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    codes = {finding.code for finding in result.scene.report.findings}
    assert "fit.violated" not in codes
    assert "fit.missing_feature" not in codes


def test_one_undo_takes_a_cut_back(loaded, profile: Profile) -> None:
    project, mesh = loaded
    apply_split(project.document, mesh, "obj_1", profile)

    History(project.document).undo()
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    assert list(result.scene.objects) == ["obj_1"], "the whole part is back"


def test_a_part_that_already_fits_is_not_cut(profile: Profile) -> None:
    project = new_project("centauri-carbon-2", "petg")
    small = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))

    applied = apply_split(project.document, small, "obj_1", profile)

    assert applied.object_ids == ["obj_1"]
    assert applied.fits == []
    assert project.document.ops == []


def test_the_sections_of_a_turned_axis_match_the_upright_ones(profile: Profile) -> None:
    """Die Drehung muss exakt sein — die Stiftpositionen werden durch sie
    gerechnet.
    """
    plate = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))

    along_z = autosplit.sections_along(plate, "z", np.array([0.0]))[0]
    along_x = autosplit.sections_along(plate, "x", np.array([0.0]))[0]

    assert along_z is not None and along_x is not None
    assert along_z.area == pytest.approx(60.0 * 40.0)
    assert along_x.area == pytest.approx(40.0 * 20.0)
