"""Auto Split mit Verstiftung (Bauplan §25, §22.3, §14; §40 für P10).

Das Abnahmekriterium sind drei Sätze: jedes Teil für sich wasserdicht,
Passungspaare angelegt und geprüft, und ``oversized.stl`` in etwas Druckbares
geteilt, ohne dass jemand einen Parameter anfasst. Alle drei stehen hier.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import BooleanFailedError, OperationCancelled, ValidationError
from app.core.geom import autosplit, pins
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.prepare import split_at_plane
from app.core.geom.section import Axis, SectionPlane
from app.core.ingest.loader import normalise
from app.core.knowledge import profiles
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import ResultCache
from app.core.scene.cancel import CancelSignal, NeverCancelled
from app.core.scene.project import Project, ProjectSources, load, new_project, save
from app.core.slice.orientation import SUPPORT_TIE, best_face_candidate
from app.core.split import apply_line_split, apply_planned, apply_split, plan_split
from app.core.types import Finding, OpContext, Profile, Scene, SceneObject, Source
from app.i18n import source_text
from tests.helpers import at_the_start_rule

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
    # Deutlich heißt: jenseits der Toleranz, unter der zwei Nähte als gleich
    # teuer gelten und die Nahtgüte entscheidet (``SUPPORT_TIE``). Hier stand
    # die Hälfte; solange die Mittenlage nur eine Lage auf einer Kante oder
    # am fernen Ende fand, lag ihr Preis um Größenordnungen darüber.
    assert chosen_support < cheap_support * (1.0 - SUPPORT_TIE), (
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


def test_a_seam_without_room_for_a_connector_is_judged_once(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Passt kein Verbinder auf die Naht, gibt es keine zweite Stiftseite (RM-266).

    ``add_pins`` gibt die Hälften dann unverändert zurück; „Stifte an B"
    wären dieselben zwei Hälften in anderer Folge, dieselbe Summe — und B
    gewinnt nur mit weniger. Die Suche beurteilte sie trotzdem zweimal: an der
    Waschschüssel und am Besteckeinsatz aus dem Korpus jede zweite
    Beurteilung. Ein Stab mit 4 mm Querschnitt hat für keinen Stift Platz.
    """
    stick = MeshData.of(trimesh.creation.box(extents=(300.0, 4.0, 4.0)))
    seam = autosplit.Candidate("x", 0.0, 16.0, 1, 0.0)
    assert not autosplit._connector_plan(stick, seam, pins.PIN_COUNT).count, (
        "der Stab trägt einen Verbinder — dann prüft der Test nichts"
    )
    both = [
        autosplit._support_after_cut(
            stick,
            seam,
            profile,
            orientation_candidates=3,
            cancelled=None,
            connector_count=pins.PIN_COUNT,
            pins_on_b=pins_on_b,
        )
        for pins_on_b in (False, True)
    ]
    assert both[0] == both[1], "ohne Verbinder sind beide Zuordnungen dieselbe Summe"

    judged: list[tuple[float, bool]] = []
    support_after_cut = autosplit._support_after_cut

    def record(*args: Any, **kwargs: Any) -> float:
        judged.append((args[1].position, bool(kwargs.get("pins_on_b", False))))
        return support_after_cut(*args, **kwargs)

    monkeypatch.setattr(autosplit, "_support_after_cut", record)
    chosen = autosplit.find_plane(stick, profile)

    assert chosen is not None and not chosen.pins_on_b
    assert judged, "die Suche beurteilte keine Naht"
    assert not any(pins_on_b for _, pins_on_b in judged)
    assert len({position for position, _ in judged}) == len(judged), "je Naht einmal"


def test_the_seam_search_cuts_without_filaments(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Probeschnitte tragen keine Filamente weiter (RM-266).

    Jeder Schnitt gab seinen Hälften die Slots der Oberfläche mit, je Dreieck
    über den nächsten Ort auf dem alten Netz — am farbigen Besteckeinsatz aus
    dem Korpus 4,7 von 4,8 s je Probeschnitt. Die Suche liest davon nichts:
    Dieselbe Form, einmal farbig, einmal nicht, bekommt dieselbe Teilung.
    """
    from app.core.geom import attributes

    plain = bar()
    coloured = MeshData(
        raw=plain.raw.copy(), slots=tuple(index % 2 for index in range(plain.triangle_count))
    )
    carried: list[int] = []
    transfer = attributes.transfer

    def counting(result: MeshData, sources: list[MeshData], **kwargs: Any) -> MeshData:
        if any(source.slots for source in sources):
            carried.append(result.triangle_count)
        return transfer(result, sources, **kwargs)

    monkeypatch.setattr(attributes, "transfer", counting)
    with_colour = plan_split(coloured, "obj_1", profile)

    assert not carried, "die Suche übertrug Filamente auf Stücke, die niemand bekommt"
    without = plan_split(plain, "obj_1", profile)
    assert with_colour.drafts and [draft.params for draft in with_colour.drafts] == [
        draft.params for draft in without.drafts
    ]
    assert [plan.positions if plan else None for plan in with_colour.connectors] == [
        plan.positions if plan else None for plan in without.connectors
    ]


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

    # Je Naht zwei Rechnungen, seit beide Stiftseiten gewertet werden (RM-005):
    # dieselben drei Ebenen, nicht mehr.
    assert len(set(seen)) == 3
    assert len(seen) == 6


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
    ) -> tuple[MeshData, MeshData, list[Finding]]:
        signal.cancel()
        return mesh, mesh, []

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

    def find_and_cancel(*_args: object, **_kwargs: object) -> autosplit.PlaneSearch:
        signal.cancel()
        return autosplit.PlaneSearch(autosplit.Candidate("x", 0.0, 2400.0, 1, 0.0))

    monkeypatch.setattr(autosplit, "search_plane", find_and_cancel)
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

    def cut_and_cancel(*_args: object) -> tuple[MeshData, MeshData, list[Finding]]:
        signal.cancel()
        return half, half, []

    monkeypatch.setattr(
        autosplit,
        "search_plane",
        lambda *_args, **_kwargs: autosplit.PlaneSearch(
            autosplit.Candidate("x", 0.0, 2400.0, 1, 0.0)
        ),
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


def test_cancelled_pin_allowance_starts_no_pin_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    signal = CancelSignal()
    signal.cancel()
    monkeypatch.setattr(
        pins,
        "plan_pins",
        lambda *_args, **_kwargs: pytest.fail("nach dem Abbruch begann noch die Stiftplanung"),
    )

    with pytest.raises(OperationCancelled):
        autosplit._pin_allowance(bar(), "x", pins.PIN_COUNT, cancelled=signal)


def test_pin_allowance_stops_after_pin_planning(monkeypatch: pytest.MonkeyPatch) -> None:
    signal = CancelSignal()
    original = pins.plan_pins

    def plan_and_cancel(*args: object, **kwargs: object):
        plan = original(*args, **kwargs)
        signal.cancel()
        return plan

    monkeypatch.setattr(pins, "plan_pins", plan_and_cancel)

    with pytest.raises(OperationCancelled):
        autosplit._pin_allowance(bar(), "x", pins.PIN_COUNT, cancelled=signal)


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
        "search_plane",
        lambda *_args, **_kwargs: autosplit.PlaneSearch(
            autosplit.Candidate("x", 0.0, 2400.0, 1, 0.0)
        ),
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


def test_auto_dovetails_take_part_in_the_support_choice(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Nahtsuche bewertet die Verbinder, die Auto Split wirklich baut.

    Der analytische Körper erweitert den Balken aus ``crossed_overhangs`` auf
    einen 22 × 22-mm-Querschnitt. Damit wählt T4 an allen guten Nähten echte
    Schwalbenschwänze.

    Der stehende Überhang sitzt bei x 0,5…2,5, der liegende bei x 5…7. Eine
    Naht bei −3,25 liegt vor beiden und lässt sie zusammen auf der rechten
    Hälfte. Bei +3,25 werden sie getrennt und jede Hälfte darf sich selbst
    legen. Gemessen am 06.09.2026, Stützvolumen in mm³ je Naht, nackt →
    fertig: links 7004,8 → 7132,9, rechts 2137,5 → 3473,6.

    Die frühere Behauptung dieses Tests, die Schwalbenschwänze kehrten diese
    Rangfolge um, trifft auf die tatsächlich gebauten Halbschalen nicht zu.
    Rechts steht die erste fertige Hälfte auf 4471,5 mm² Bodenfläche und
    braucht 1981,3 mm³ Stützraum; die zweite steht auf 455,7 mm² Nahtfläche
    und braucht 1492,4 mm³. Alle vier geprüften Halbschalen sind wasserdichte
    Einzelkörper mit konsistenten Normalen. Die Schwalbenschwänze verteuern
    rechts stärker, aber nicht um die belegten 3659,3 mm³ Vorsprung.

    Was der Test festhält: T2 misst die fertige Geometrie. ``evaluated_*``
    trifft ``final_*`` auf die Stelle und unterscheidet sich von ``bare_*``.
    Ohne ``connector_count`` stünde dort die nackte Zahl. Die Suche folgt
    anschließend der günstigeren fertigen Naht rechts.

    Die beiden Kandidaten sind nicht frei gewählt: Bei diesem Drucker legt
    ``_window`` das Fenster auf [−52, 52] und ``SAMPLES`` 33 Stellen hinein,
    also Schritte von 3,25 mm. ±3,25 sind damit genau die zwei besten Stellen
    des Rasters (billige Punktzahl 0,004063, gleichauf), und die Suche
    entscheidet zwischen ihnen allein über das Stützvolumen.
    """
    from app.core.knowledge.parts import PARTS

    PARTS.all()
    wide_beam = trimesh.creation.box(extents=(400.0, 22.0, 22.0))
    wide_beam.apply_translation((0.0, 0.0, 11.0))
    mesh = MeshData.of(trimesh.boolean.union([crossed_overhangs().raw, wide_beam]))
    left = autosplit.Candidate("x", -3.25, 484.0, 1, 0.0)
    right = autosplit.Candidate("x", 3.25, 484.0, 1, 0.0)

    def final_support(candidate: autosplit.Candidate) -> float:
        first, second, _cut_findings = autosplit._cut_in_two(mesh, candidate)
        assert first is not None and second is not None
        plan = pins.plan_pins(mesh, candidate.plane, count=pins.PIN_COUNT, shape=pins.AUTO)
        assert plan.shape == "dovetail"
        pair = pins.add_pins(first, second, plan, profile, quality="draft")
        assert all(part.is_watertight for part in (pair.first, pair.second))
        assert all(part.component_count == 1 for part in (pair.first, pair.second))
        assert all(part.raw.is_winding_consistent for part in (pair.first, pair.second))
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
    assert right_final < left_final * (1.0 - autosplit.SUPPORT_TIE), (
        f"fertig links {left_final:.1f}, rechts {right_final:.1f}"
    )
    assert left_final > bare_left
    assert right_final > bare_right
    assert evaluated_left == pytest.approx(left_final)
    assert evaluated_right == pytest.approx(right_final)

    measured_counts = []
    original_support = autosplit._support_after_cut

    def record_support(*args, **kwargs):
        measured_counts.append(kwargs.get("connector_count", 0))
        return original_support(*args, **kwargs)

    monkeypatch.setattr(autosplit, "_support_after_cut", record_support)
    chosen = autosplit.find_plane(mesh, profile)

    assert measured_counts and set(measured_counts) == {pins.PIN_COUNT}, (
        "Die Suche muss die Verbinderzahl bis zur echten Stützrechnung weiterreichen."
    )

    assert chosen is not None
    # Beide liegen auf dem Raster und haben dieselbe billige Punktzahl. Die
    # fertige Stützrechnung löst den Gleichstand zugunsten der rechten Naht.
    assert chosen.position == pytest.approx(right.position), (
        f"die Naht liegt bei {chosen.position} statt bei {right.position}"
    )


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


def test_the_profile_curve_measures_at_its_own_stations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Einschnürungskurve misst dort, wo sie hinsieht (§22.3).

    ``_sections_in_blocks`` liefert zu jeder Position drei Schnitte — einen
    halben Millimeter darunter, auf der Position, einen halben darüber. Wer
    davon das erste Drittel nimmt, hat die Kurve um ``PRISM_STEP`` nach unten
    verschoben und nebenher neununddreißig Schnitte gerechnet statt dreizehn.

    Ein Kegel zeigt beides: Sein Querschnitt fällt stetig, also gehört zu jeder
    Verschiebung ein anderer Wert, und die Tiefe an einer Station muss zu dem
    Querschnitt passen, der an dieser Station steht.
    """
    cone = MeshData.of(trimesh.creation.cone(radius=20.0, height=60.0, sections=64))
    # Gefragt wird über ``sections_across`` — seit dem Normalenfächer (T3)
    # nimmt die Kurve eine Richtung, keine Achse.
    measure = autosplit.sections_across
    asked: list[np.ndarray] = []

    def recording(mesh: MeshData, normal: Any, heights: np.ndarray) -> list[Any]:
        asked.append(np.asarray(heights, dtype=float))
        return measure(mesh, normal, heights)

    monkeypatch.setattr(autosplit, "sections_across", recording)
    depth_at = autosplit._notch_depth(cone, "z")

    low = float(cone.bounds.minimum[2]) + autosplit.PRISM_STEP
    high = float(cone.bounds.maximum[2]) - autosplit.PRISM_STEP
    stations = np.linspace(low, high, autosplit.PROFILE_SAMPLES)
    heights = np.concatenate(asked)

    assert len(heights) == autosplit.PROFILE_SAMPLES, (
        f"die Profilkurve nimmt {len(heights)} Schnitte statt {autosplit.PROFILE_SAMPLES}"
    )
    assert np.allclose(np.sort(heights), stations), (
        f"die Schnitte liegen nicht auf den Stationen: {np.sort(heights)}"
    )

    areas = [float(entry.area) for entry in measure(cone, (0.0, 0.0, 1.0), stations)]
    middle = autosplit.PROFILE_SAMPLES // 2
    expected = (max(areas) - areas[middle]) / max(areas)
    assert depth_at(float(stations[middle])) == pytest.approx(expected, rel=1e-9), (
        "die Tiefe gehört zu einem anderen Querschnitt als dem an dieser Stelle"
    )


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


def test_the_search_counts_what_the_guard_cost(profile: Profile) -> None:
    """Die Suche sagt, wie viele Ebenen die Sperre gefressen hat (RM-080).

    Zwei Antworten sehen sonst gleich aus: „nichts gefunden" und „nichts
    gefunden, weil alles gesperrt war". Nur die zweite hat den Ausweg
    *Sperren aufheben*, also muss die Suche sie unterscheiden können.
    """
    whole = bar()

    free = autosplit.search_plane(whole, profile)
    assert free.candidate is not None and free.blocked == 0, "ohne Sperre kostet nichts"

    everything = autosplit.search_plane(whole, profile, protect=[shield(-200.0, 200.0)])
    assert everything.candidate is None
    assert everything.blocked > 0, "jede Ebene mit Fläche ist an der Sperre gescheitert"

    seam = free.candidate.position
    narrow = autosplit.search_plane(whole, profile, protect=[shield(seam - 6.0, seam + 6.0)])
    assert narrow.candidate is not None
    assert 0 < narrow.blocked < everything.blocked, "eine schmale Sperre kostet weniger als alles"


def test_a_guard_over_everything_is_named_as_the_reason(profile: Profile) -> None:
    """Bleibt neben der Sperre nichts, heißt der Befund nicht „keine Ebene".

    ``split.no_plane`` rät zur gezeichneten Linie; wer aber selbst alles
    gesperrt hat, braucht zuerst den anderen Weg — die Sperre aufheben. Der
    eigene Befund trägt die Zahl der gesperrten Ebenen und bekommt im
    Prüfbericht *Sperren aufheben und erneut teilen* als ersten Knopf.
    """
    from app.ui.panels import FINDING_ACTIONS

    outcome = autosplit.split_to_fit(bar(), profile, pins=0, protect=[shield(-200.0, 200.0)])

    codes = [finding.code for finding in outcome.findings]
    assert "split.blocked_by_protection" in codes, codes
    assert "split.no_plane" not in codes, "die Sperre ist der Grund, nicht das Teil"
    blocked = next(f for f in outcome.findings if f.code == "split.blocked_by_protection")
    assert int(blocked.values["blocked_planes"]) > 0
    assert not outcome.divided
    handlungen = FINDING_ACTIONS.get("split.blocked_by_protection")
    assert handlungen, "der Befund führt im Prüfbericht zu keiner Handlung"
    assert handlungen[0].id == "release_protection", [a.id for a in handlungen]


def test_the_plan_names_the_body_on_every_search_finding(profile: Profile) -> None:
    """Berichtshandlungen lesen ihren Körper aus dem Befund, nie aus der Auswahl.

    Die Suche rechnet auf einem Netz und kennt keine Kennungen; ``plan_split``
    kennt sie. Ohne die Kennung hätte *Sperren aufheben* kein Ziel.
    """
    plan = plan_split(bar(), "obj_9", profile, pins=0, protect=[shield(-200.0, 200.0)])

    assert plan.outcome.findings, "ohne Befund prüft dieser Test nichts"
    assert all(finding.object_id == "obj_9" for finding in plan.outcome.findings), [
        (finding.code, finding.object_id) for finding in plan.outcome.findings
    ]


def test_protected_patches_come_from_the_feature_triangles() -> None:
    """Aus den Kennungen des Dokuments werden die Punktwolken der Suche.

    Zwei Zusicherungen: Die Wolke besteht aus genau den Ecken der Dreiecke des
    Merkmals, und eine Kennung, die der Körper nicht trägt, ergibt keine Wolke
    und keinen Fehler — was nicht da ist, kann keine Naht zerteilen.
    """
    from app.core.split import protected_patches
    from app.core.types import Feature, SceneObject

    mesh = bar()
    top = [index for index, normal in enumerate(mesh.raw.face_normals) if normal[2] > 0.9]
    assert top, "der Balken hat eine Oberseite"
    entry = SceneObject(
        id="obj_1",
        name="Balken",
        mesh=mesh,
        features={
            "face_top": Feature(
                id="face_top",
                kind="face",
                provenance="detected",
                params={},
                face_indices=tuple(top),
            ),
            "edge_1": Feature(id="edge_1", kind="edge_loop", provenance="detected", params={}),
        },
    )

    patches = protected_patches(entry, ("face_top", "edge_1", "hole_99"))

    assert len(patches) == 1, "nur das Merkmal mit Dreiecken ergibt eine Wolke"
    assert len(patches[0]) == 3 * len(top)
    assert np.allclose(patches[0][:, 2], mesh.raw.vertices[:, 2].max()), (
        "die Wolke der Oberseite liegt ganz oben"
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
    # Gemessen an den gebauten Stücken samt ihren wirklichen Stiften — seit die
    # Zugabe nur noch an der Hälfte mit Stiften hängt, trägt nicht jedes Stück
    # einen, und die Probe mit einem gedachten Stift an jedem wäre zu streng.
    for built in built_pieces(box, profile):
        assert autosplit.fits(built, profile), "Stück samt Stift bleibt auf dem Bett"


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
    first, second, _cut_findings = autosplit._cut_in_two(whole, candidate)
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
    first, second, _cut_findings = autosplit._cut_in_two(whole, candidate)
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


@pytest.mark.parametrize("refusal", ["chain", "crossing_shell"])
def test_a_seam_whose_connectors_fail_does_not_end_the_search(
    monkeypatch: pytest.MonkeyPatch, profile: Profile, refusal: str
) -> None:
    """Scheitert an einer Naht der Bau der Stifte, ist sie nicht zu beurteilen — mehr nicht.

    Die Suche baut an jeder Naht der engeren Wahl die Stifte probeweise, um
    ihr Stützvolumen zu messen. Warf die Boolesche Kette dabei, brach die ganze
    Teilung ab: Am Laptopständer (``parametric-laptop-riser.stl``) stand nach
    6,7 s ein Fehlerdialog über „die schnelle Vorschau", dessen Knöpfe an der
    Teilung nichts ändern konnten (KUNDE-10). Eine Naht ohne messbare Stifte
    kostet unbekannt viel — wie eine Hälfte ohne Lage —, und die übrigen Nähte
    werden weiter beurteilt. Hält der Schritt danach selbst an, sagt es der
    Bericht an ihm.

    **Jede Absage der Geometrie, nicht nur die der Rückfallkette** (RM-409):
    Eine Stiftbohrung durch eine Schale, die sich selbst kreuzt, hält vor dem
    Kern mit ``GeometryError`` an — der Oberklasse von ``BooleanFailedError``.
    Am Laptopständer brach damit wieder die ganze Suche ab.
    """
    from app.core.errors import CANCEL, CORRECT_INPUT, GeometryError
    from app.core.geom import pins as connectors
    from app.core.geom.boolean import CROSSING_SHELL_IN_THE_WAY

    def failing(*_args: object, **_kwargs: object) -> None:
        if refusal == "chain":
            raise BooleanFailedError(detail="Stifte", attempted=("direct", "welded"))
        raise GeometryError(detail=CROSSING_SHELL_IN_THE_WAY, suggestions=(CORRECT_INPUT, CANCEL))

    monkeypatch.setattr(connectors, "add_pins", failing)

    plan = plan_split(bar(), "obj_1", profile)

    assert plan.drafts, "the search ends with a seam, not with the kernel's exception"
    assert all(draft.op == "split_pinned" for draft in plan.drafts)


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
    # Der Würfel ist spiegelgleich, die Naht liegt in der Mitte (T6) — und das
    # sagt der zweite Befund.
    assert [finding.code for finding in applied.findings] == [
        "split.connector_glue",
        "split.symmetric",
    ]

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
        project.document, "obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), mesh=block
    )
    assert len(first.fits) == 2, "die erste Naht bekommt ihre Paare"
    assert project.document.fits == first.fits

    halved = evaluate(project.document, profile, sources=ProjectSources(project))
    target = first.object_ids[0]
    second = apply_line_split(
        project.document,
        target,
        SectionPlane((0.0, 1.0, 0.0), 0.0),
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
        project.document, "obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), mesh=block
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
        project.document, "obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), mesh=block
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
    # **Und die erste Naht behält ihre Passungen** (RM-080, T7): Bis zum
    # 23.09.2026 entfielen die zwei Paare des ersten Schnitts, weil der zweite
    # ein verstiftetes Stück noch einmal teilte. Jetzt wandern sie auf die
    # Hälfte, die den Stift trägt.
    assert [finding.code for finding in applied.findings].count("split.fit_dropped") == 0
    assert len(applied.fits) == 4, "beide Nähte tragen je zwei Passungen"

    result = evaluate(project.document, profile, sources=ProjectSources(project))
    codes = [finding.code for finding in result.scene.report.findings]
    assert "fit.missing_feature" not in codes, codes

    live = set(applied.object_ids)
    for fit in project.document.fits:
        assert fit.a.object_id in live and fit.b.object_id in live, fit.name


@pytest.mark.parametrize(("length", "count"), [(600.0, 3), (900.0, 4)])
def test_auto_split_numbers_three_or_more_pieces_and_names_what_each_carries(
    profile: Profile, length: float, count: int
) -> None:
    """„Leiste 2 von 3 · Stifte und Löcher“ statt „Leiste B A · Stifte“ (RM-229).

    Der Plan trägt jedem Schnitt die Nummern seiner Stücke ein, gezählt in der
    Reihenfolge der fertigen Stücke; ein Stück, das derselbe Lauf gleich weiter
    teilt, bekommt keine. Der Zusatz folgt den Verbindern, die das Stück trägt
    — welche Hälfte die Stifte bekommt, entscheidet der Plan je Naht.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [
            OperationDraft(
                op="create_box",
                params={"width": length, "depth": 60.0, "height": 40.0, "name": "Leiste"},
            )
        ],
    )
    block = MeshData.of(trimesh.creation.box(extents=(length, 60.0, 40.0)))

    applied = apply_split(project.document, block, "obj_1", profile)
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert len(applied.object_ids) == count
    notes = {(True, False): "Stifte", (False, True): "Löcher", (True, True): "Stifte und Löcher"}
    names = []
    for number, object_id in enumerate(applied.object_ids, start=1):
        entry = result.scene.objects[object_id]
        features = entry.features.items()
        carries = (
            any(key.startswith("pin_") and f.provenance == "generated" for key, f in features),
            any(key.startswith("bore_") and f.provenance == "generated" for key, f in features),
        )
        names.append(source_text(entry.name))
        assert source_text(entry.name) == f"Leiste {number} von {count} · {notes[carries]}"
    assert all(" A" not in name and " B" not in name for name in names), names


@pytest.mark.parametrize("suppress", [False, True], ids=["delete", "suppress"])
def test_auto_split_names_follow_active_pieces_after_last_cut_change(
    profile: Profile, suppress: bool
) -> None:
    """Der Rest eines Auto-Split-Bündels zählt nach Löschen und Ausschalten neu.

    Derselbe Cache bleibt absichtlich über alle Auswertungen erhalten: Ein
    Drei-Stücke-Ergebnis darf die neue Zwei-Stücke-Zählung nicht überdecken.
    """
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Anlegen",
        [
            OperationDraft(
                op="create_box",
                params={"width": 600.0, "depth": 60.0, "height": 40.0, "name": "Leiste"},
            )
        ],
    )
    block = MeshData.of(trimesh.creation.box(extents=(600.0, 60.0, 40.0)))
    applied = apply_split(project.document, block, "obj_1", profile)
    split_ops = [entry for entry in project.document.ops if entry.op == "split_pinned"]
    assert len(split_ops) == 2
    last = split_ops[-1]
    saved_params = {entry.id: dict(entry.params) for entry in project.document.ops}
    saved_format_version = project.document.format_version
    cache = ResultCache()

    def evaluated_bases() -> set[str]:
        result = evaluate(project.document, profile, sources=ProjectSources(project), cache=cache)
        assert result.complete
        return {
            source_text(entry.name).split(" · ", maxsplit=1)[0]
            for entry in result.scene.objects.values()
        }

    assert len(applied.object_ids) == 3
    assert evaluated_bases() == {"Leiste 1 von 3", "Leiste 2 von 3", "Leiste 3 von 3"}

    if suppress:
        history.commit(history.plan_suppress([last.id]))
    else:
        history.remove_operations([last.id])

    assert evaluated_bases() == {"Leiste A", "Leiste B"}
    assert project.document.format_version == saved_format_version
    assert all(dict(entry.params) == saved_params[entry.id] for entry in project.document.ops)

    if not suppress:
        history.apply(
            "Anordnen",
            [OperationDraft(op="arrange_bed", inputs=split_ops[0].outputs)],
        )
        assert evaluated_bases() == {"Leiste A", "Leiste B"}
        history.undo()

    history.undo()
    assert evaluated_bases() == {"Leiste 1 von 3", "Leiste 2 von 3", "Leiste 3 von 3"}

    history.redo()
    assert evaluated_bases() == {"Leiste A", "Leiste B"}
    assert all(dict(entry.params) == saved_params[entry.id] for entry in project.document.ops)

    if suppress:
        history.commit(history.plan_reactivate([last.id]))
        assert evaluated_bases() == {"Leiste 1 von 3", "Leiste 2 von 3", "Leiste 3 von 3"}
    assert project.document.format_version == saved_format_version


@pytest.mark.parametrize("revision", ["move", "retry"], ids=["Verschieben", "Neu-fassen"])
def test_auto_split_names_follow_the_bundle_after_history_clones(
    profile: Profile, revision: str
) -> None:
    """Verschobene und beim Reparieren neu gefasste Schnitte bleiben im Bündel."""
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Anlegen",
        [
            OperationDraft(
                op="create_box",
                params={"width": 600.0, "depth": 60.0, "height": 40.0, "name": "Leiste"},
            )
        ],
    )
    block = MeshData.of(trimesh.creation.box(extents=(600.0, 60.0, 40.0)))
    applied = apply_split(project.document, block, "obj_1", profile)
    split_ops = [entry for entry in project.document.ops if entry.op == "split_pinned"]
    assert len(split_ops) == 2

    history.apply(
        "Unabhängig umbenennen",
        [
            OperationDraft(
                op="rename_object",
                inputs=(applied.object_ids[0],),
                params={"name": "Randstück"},
            )
        ],
    )
    if revision == "move":
        history.commit(history.plan_move([split_ops[-1].id], before=None))
    else:
        history.repair_and_retry(split_ops[0].id)

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    names = {
        source_text(entry.name).split(" · ", maxsplit=1)[0]
        for object_id, entry in result.scene.objects.items()
        if object_id in applied.object_ids
    }
    assert names == {"Randstück", "Leiste 2 von 3", "Leiste 3 von 3"}


def test_auto_split_suffix_clones_do_not_form_a_new_smaller_run(profile: Profile) -> None:
    """Zwei verschobene Schnitte bleiben Teil des Vier-Stücke-Laufs."""
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Anlegen",
        [
            OperationDraft(
                op="create_box",
                params={"width": 900.0, "depth": 60.0, "height": 40.0, "name": "Leiste"},
            ),
            OperationDraft(
                op="create_box",
                params={
                    "width": 20.0,
                    "depth": 20.0,
                    "height": 20.0,
                    "y": 80.0,
                    "name": "Nebenmodell",
                },
            ),
        ],
    )
    block = MeshData.of(trimesh.creation.box(extents=(900.0, 60.0, 40.0)))
    applied = apply_split(project.document, block, "obj_1", profile)
    split_ops = [entry for entry in project.document.ops if entry.op == "split_pinned"]
    assert len(applied.object_ids) == 4
    assert len(split_ops) == 3

    history.apply(
        "Unabhängig umbenennen",
        [
            OperationDraft(
                op="rename_object",
                inputs=("obj_2",),
                params={"name": "Randstück"},
            )
        ],
    )
    history.commit(history.plan_move([entry.id for entry in split_ops[-2:]], before=None))

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    assert source_text(result.scene.objects["obj_2"].name) == "Randstück"
    names = {
        source_text(entry.name).split(" · ", maxsplit=1)[0]
        for object_id, entry in result.scene.objects.items()
        if object_id in applied.object_ids
    }
    assert names == {
        "Leiste 1 von 4",
        "Leiste 2 von 4",
        "Leiste 3 von 4",
        "Leiste 4 von 4",
    }


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

    # Ohne Kennung: Die Passung folgt dem Material, in dem die Hälften
    # gedruckt werden (Durchsicht 0.5.0; siehe ``test_a_seam_follows_…``).
    assert [fit.tolerance for fit in applied.fits] == ["auto:", "auto:"]
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

    applied = apply_planned(project.document, plan, "obj_1")

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


def test_sections_across_matches_upright_and_turned_axes(profile: Profile) -> None:
    """Die Drehung muss exakt sein — die Stiftpositionen werden durch sie
    gerechnet.
    """
    plate = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))

    along_z = autosplit.sections_across(plate, autosplit.AXIS_NORMALS["z"], np.array([0.0]))[0]
    along_x = autosplit.sections_across(plate, autosplit.AXIS_NORMALS["x"], np.array([0.0]))[0]

    assert along_z is not None and along_x is not None
    assert along_z.area == pytest.approx(60.0 * 40.0)
    assert along_x.area == pytest.approx(40.0 * 20.0)


def open_body(name: str = "oversized.stl") -> MeshData:
    """Derselbe zu große Körper, aber mit einem Loch — so, wie er aus einem
    fremden STL kommt.

    Ein einzelnes Dreieck fehlt. Das genügt: ``is_watertight`` ist damit falsch,
    und genau daran entscheidet der Schnitt, ob er deckeln kann
    (``section._apply`` reicht es als ``cap`` an trimesh weiter). Die
    Eingangsstufe verschweißt normalerweise — hier wird sie bewusst umgangen,
    denn ein Loch verschwindet dabei nicht.
    """
    raw = body(name).raw
    faces = np.asarray(raw.faces)
    keep = np.ones(len(faces), dtype=bool)
    keep[0] = False
    return MeshData.of(trimesh.Trimesh(vertices=raw.vertices, faces=faces[keep], process=False))


def test_auto_split_says_when_it_could_not_close_the_cut(profile: Profile) -> None:
    """Ein offener Körper wird geschnitten — und das wird gesagt.

    Der Handschnitt meldet es seit jeher: ``split_at_plane`` gibt
    ``split.uncapped`` zurück, wenn eine der beiden Hälften ungedeckelt bleibt.
    Auto Split rief dieselbe Funktion, packte die Befunde in ``_findings`` aus
    und warf sie weg. Der Kunde bekam zwei offene Hälften und keinen Hinweis —
    beim einzigen Weg, auf dem er die Teilung *nicht* selbst gewählt hat.

    Warum das trägt: Ein ungedeckeltes Netz ist kein Körper. Der Slicer füllt es
    nach eigenem Gutdünken oder gar nicht, und der Fehler zeigt sich erst am
    Druck. Das ist genau der Fall, für den Auto Split gedacht ist — Weg 1, ein
    fremdes STL, das aufs Bett soll.
    """
    open_mesh = open_body()
    assert not open_mesh.raw.is_watertight, "die Vorbedingung des Tests"

    outcome = autosplit.split_to_fit(open_mesh, profile, pins=0)

    assert outcome.divided, "geschnitten wird trotzdem — gemeldet wird es jetzt auch"
    assert "split.uncapped" in [finding.code for finding in outcome.findings]


def test_the_open_cut_is_reported_once_and_not_per_cut(profile: Profile) -> None:
    """Einmal, nicht je Schnitt.

    ``capped`` ist genau ``is_watertight`` der Eingabe, und eine Hälfte eines
    offenen Körpers ist wieder offen — der Befund fiele sonst bei jedem Schnitt
    erneut an und stünde vierfach im Prüfbericht. Er sagt aber viermal dasselbe:
    dass die Quelle ein Loch hat.
    """
    outcome = autosplit.split_to_fit(open_body(), profile, pins=0, max_parts=4)

    codes = [finding.code for finding in outcome.findings]
    assert codes.count("split.uncapped") == 1, f"einmal, nicht {codes.count('split.uncapped')}-mal"


def test_a_closed_body_is_split_without_that_warning(profile: Profile) -> None:
    """Die Gegenprobe: Der geschlossene Regelfall bleibt still."""
    outcome = autosplit.split_to_fit(body(), profile, pins=0)

    assert outcome.divided
    assert "split.uncapped" not in [finding.code for finding in outcome.findings]


def test_the_open_cut_says_why_and_what_to_do(profile: Profile) -> None:
    """Der Befund nennt die Ursache und den Rückweg, nicht nur das Ergebnis.

    „Die Schnittflächen konnten nicht geschlossen werden" stand bis zum
    10.09.2026 allein da, und ein Kunde konnte daraus nichts machen: Der Satz
    klang nach einem Fehler des Schnitts, also suchte man am Schnitt. Der
    Schnitt kann aber nichts dafür — ``SectionResult.capped`` ist genau
    ``is_watertight`` der **Eingabe** (``section._apply``), das Modell war
    also schon vorher offen.

    Geprüft wird die Aussage und nicht der Wortlaut: dass der Zustand **vor**
    dem Schnitt benannt wird und dass ein Weg nach vorn dasteht (Regel 17).

    **Und der Satz sagt „nicht geschlossen", nicht „Loch".** ``is_watertight``
    heißt in trimesh „jede Kante hat genau zwei Flächen" — ein Würfel mit einer
    doppelt geführten Fläche ist nicht wasserdicht und hat trotzdem kein Loch
    (gemessen 10.09.2026). Bei fremden STL-Dateien ist das Alltag; der Kunde
    suchte dann ein Loch, das es nicht gibt. Aufgefallen im Review, nicht beim
    Schreiben.
    """
    outcome = autosplit.split_to_fit(open_body(), profile, pins=0)

    offen = [finding for finding in outcome.findings if finding.code == "split.uncapped"]
    assert offen, "der Befund fehlt ganz"
    satz = source_text(offen[0].message)
    assert "vor dem" in satz and "nicht geschlossen" in satz, f"die Ursache fehlt: {satz}"
    assert "Reparieren" in satz, f"der Rückweg fehlt: {satz}"


def test_new_fit_pairs_never_take_a_name_that_is_already_in_use(loaded, profile: Profile) -> None:
    """Gesamtreview 05.09.2026, CORE-31: Die Stiftpaare wurden durchgezählt
    — ``stift_{Anzahl + 1}`` —, und neben einer einzigen vorhandenen Passung
    namens ``stift_2`` bekam der nächste Schnitt eine Namensschwester. Beim
    Beheben verlorener Verweise traf die gewählte Zuordnung danach die erste,
    unbeteiligte Passung."""
    from app.core.scene.history import change_for
    from app.core.types import FeatureRef, Fit

    project, mesh = loaded
    History(project.document).apply(
        "Zwei Klötze",
        [
            OperationDraft(op="create_box", params={"width": 10.0, "depth": 10.0, "height": 5.0}),
            OperationDraft(op="create_box", params={"width": 10.0, "depth": 10.0, "height": 5.0}),
        ],
    )
    by_hand = Fit(
        name="stift_2",
        a=FeatureRef("obj_2", "face_top"),
        b=FeatureRef("obj_3", "face_top"),
        kind="clearance",
        tolerance="auto:petg",
    )
    History(project.document).apply(
        "Passung von Hand", changes=change_for(project.document, fits=[by_hand])
    )

    apply_split(project.document, mesh, "obj_1", profile)

    names = [fit.name for fit in project.document.fits]
    assert names[0] == "stift_2", "die eigene bleibt, sie hängt an unbeteiligten Körpern"
    assert len(names) > 1, "ohne neue Paare prüft dieser Test nichts"
    assert len(names) == len(set(names)), f"doppelte Namen: {names}"


def test_the_open_cut_carries_its_body_and_a_button(profile: Profile) -> None:
    """Der Satz stand da, der Knopf fehlte (RM-039).

    `split.uncapped` stand nicht in `FINDING_ACTIONS`, während seine
    Geschwister `split.no_plane` und `split.cut_failed` dort welche haben —
    der Befund war damit im Prüfbericht ein Satz ohne Weg nach vorn, und
    Regel 17 gilt im Bericht so gut wie im Dialog.

    **Und der Knopf braucht seinen Körper.** Eine Berichtshandlung liest ihr
    Ziel aus dem Befund und nicht aus der Auswahl; die Geometriefunktion
    rechnet auf einem Netz und kennt keine Kennungen, also verortet sie die
    Operation — dieselbe Aufteilung wie beim Aushöhlen.
    """
    from app.ui.panels import FINDING_ACTIONS

    outcome = autosplit.split_to_fit(open_body(), profile, pins=0)

    offen = [finding for finding in outcome.findings if finding.code == "split.uncapped"]
    assert offen, "der Befund fehlt ganz"
    handlungen = FINDING_ACTIONS.get("split.uncapped")
    assert handlungen, "der Befund führt im Prüfbericht zu keiner Handlung"
    assert any(action.id == "repair_and_retry" for action in handlungen), (
        f"der Rückweg, den der Satz nennt, fehlt als Knopf: {[a.id for a in handlungen]}"
    )


def test_the_open_cut_names_the_body_it_belongs_to(profile: Profile) -> None:
    """Der Knopf braucht ein Ziel, und das steht im Befund (RM-039).

    „Berichtshandlungen lesen ihren Zielkörper aus Befund oder Dokument. Eine
    aktuelle Auswahl ist kein Ersatz" — ohne die Kennung wäre *Reparieren und
    erneut versuchen* ein Knopf über einem Körper, den niemand benannt hat.
    """
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene, SceneObject

    entry = SceneObject(id="obj_7", name="Offenes Teil", mesh=open_body())
    spec = REGISTRY.get("split_pinned")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(axis="z", position=5.0, pins=0),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )

    offen = [finding for finding in result.findings if finding.code == "split.uncapped"]
    assert offen, "der Befund fehlt"
    assert offen[0].object_id == "obj_7", f"der Befund nennt keinen Körper: {offen[0].object_id!r}"


def test_splitting_from_the_dialog_pairs_its_pins_in_one_step(profile: Profile) -> None:
    """*Teilen* aus dem Dialog legt seine Passungen an wie *Automatisch teilen*.

    Bis zum 22.09.2026 legte der Dialog nur den Schritt ``split_pinned`` an:
    Stifte und Bohrungen entstanden, eine Passung dazwischen nicht, und im
    Slicer fehlten die Werte, die über das Zusammenstecken entscheiden. Das
    Trennen-Werkzeug und *Automatisch teilen* taten es längst, und die Website
    zählt es zu *Teilen*. Jetzt geht auch der Dialog über den Ablauf, in einer
    Transaktion mit dem Schnitt — ein Undo nimmt beides.
    """
    from app.core.split import SplitTarget, apply_pinned_split

    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    History(document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(80.0, 60.0, 40.0)))
    transactions = len(document.transactions)

    applied = apply_pinned_split(
        document,
        [SplitTarget("obj_1", block, {})],
        {"axis": "x", "position": 0.0, "pins": 2, "shape": "round"},
        title="Teilen",
    )

    assert len(document.transactions) == transactions + 1, "ein Schritt"
    assert document.ops[-1].op == "split_pinned"
    assert len(applied.fits) == 2
    assert document.fits == applied.fits
    assert [fit.a.feature_id for fit in applied.fits] == ["pin_1", "pin_2"]
    result = evaluate(document, profile, sources=ProjectSources(project))
    assert result.complete
    assert "fit.missing_feature" not in [f.code for f in result.scene.report.findings]

    History(document).undo()
    assert document.fits == [], "das Undo nimmt die Passungen mit"


def test_the_pins_go_to_the_half_that_needs_less_support(profile: Profile) -> None:
    """RM-005: Welche Hälfte die Stifte trägt, entscheidet das fertige Stützvolumen.

    Die Stifte stehen über die Naht, und die Hälfte mit ihnen kann nicht mehr
    auf der Naht liegen. Bis zum 22.09.2026 trug immer A die Stifte. An der
    Naht, die Auto Split am Balken mit zwei gekreuzten Überhängen wählt
    (x = 3,25), kosten die Stifte an A 3 754 mm³ Stützen, an B 3 298 — zwölf
    Prozent, mehr als die fünf, mit denen eine Naht die andere schlägt.
    Beide Zuordnungen werden jetzt fertig gebaut, und die bessere steht im
    Schritt.

    Die Zahlen gelten der Startregel. Mit den 60 Grad des Centauri trägt dieselbe
    Naht die Stifte besser an A (3 620 gegen 4 255 mm³) — die Wahl dreht sich mit
    dem Winkel, und genau deshalb werden beide gebaut.
    """
    from app.core.slice.orientation import SUPPORT_TIE

    profile = at_the_start_rule(profile)
    mesh = crossed_overhangs()
    seam = autosplit.Candidate("x", 3.25, 144.0, 1, 0.0)
    on_a = autosplit._support_after_cut(
        mesh, seam, profile, orientation_candidates=3, cancelled=None, connector_count=2
    )
    on_b = autosplit._support_after_cut(
        mesh,
        seam,
        profile,
        orientation_candidates=3,
        cancelled=None,
        connector_count=2,
        pins_on_b=True,
    )
    assert on_b < on_a * (1.0 - SUPPORT_TIE), (on_a, on_b)

    chosen = autosplit._best_by_support(
        mesh,
        profile,
        (seam,),
        plane_candidates=1,
        orientation_candidates=3,
        cancelled=None,
        connector_count=2,
    )
    assert chosen.pins_on_b, "die Hälfte ohne Stifte liegt günstiger"
    assert (chosen.axis, chosen.position) == (seam.axis, seam.position)
    found = autosplit.find_plane(mesh, profile)
    assert found is not None
    assert (found.axis, found.position, found.pins_on_b) == ("x", 3.25, True), (
        "und Auto Split nimmt genau diese Wahl"
    )


def stretched_ring() -> MeshData:
    """``torus_ring.stl``, gestreckt wie der Körper des Leistungstests: die
    lange Achse 1,6 Bauräume des Centauri Carbon 2, die übrigen 0,75 — zu groß
    fürs Bett, mittig um den Ursprung."""
    ring = read_mesh((MESHES / "torus_ring.stl").read_bytes(), ".stl").raw.copy()
    ring.merge_vertices()
    extents = ring.extents
    room = 256.0
    ring.apply_scale((1.6 * room / extents[0], 0.75 * room / extents[1], 0.75 * room / extents[1]))
    ring.apply_translation(-ring.bounds.mean(axis=0))
    return MeshData.of(ring)


def _half_of_a_stretched_ring() -> MeshData:
    first, _second, _findings = split_at_plane(stretched_ring(), SectionPlane.along("x", 0.0))
    return first


@pytest.mark.parametrize("pins_on_b", [False, True])
def test_a_flat_ring_gets_a_price_at_every_seam(profile: Profile, pins_on_b: bool) -> None:
    """Die Hälften stehen flach auf gut 600 mm², aber kaum ein Dreieck ihrer
    Rundung zeigt genau nach unten. Eine Vorprüfung an der geschätzten
    Auflage verwarf die Lage, und jede Naht des Rings kostete „unbekannt“."""
    price = autosplit._support_after_cut(
        stretched_ring(),
        autosplit.Candidate("x", 0.0, 1.0, 2, 0.0),
        profile,
        orientation_candidates=3,
        cancelled=None,
        connector_count=2,
        pins_on_b=pins_on_b,
    )

    assert math.isfinite(price)


def test_the_free_place_asks_the_same_question_as_the_judgement(profile: Profile) -> None:
    """Der freie Platz fragt, ob eine Lage steht, ohne den Körper zu schneiden
    (``standing_check``). Beide Antworten müssen für jede Lage gleich ausfallen,
    sonst verdrängt der Platz eine Lage, die steht, oder bleibt leer."""
    from app.core.geom.orient import ranked_orientations
    from app.core.slice.orientation import judge, standing_check, stands

    half = _half_of_a_stretched_ring()
    footing = profile.printer.layer_height / 2.0
    ask = standing_check(half, profile)
    ranked = ranked_orientations(
        half, printer=profile.printer, overhang_limit=profile.overhang_limit_degrees
    )
    answers = {
        entry.direction: (
            ask(entry),
            stands(
                judge(
                    half,
                    entry.direction,
                    1.0,
                    footing,
                    overhang_angle=profile.overhang_limit_degrees,
                    line_width=profile.printer.extrusion_width,
                ),
                profile.smallest_first_layer,
            ),
        )
        for entry in ranked
    }

    assert any(judged for _asked, judged in answers.values()), "Voraussetzung: eine Lage steht"
    assert {direction for direction, (asked, judged) in answers.items() if asked != judged} == set()


def test_a_half_that_cannot_stand_has_no_cheap_support(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Lage, die nicht steht, ist kein Preis für eine Naht.

    ``best_face_candidate`` gibt eine Lage, die nicht steht, nur zurück, wenn
    keine der vorgewählten steht — und ihr Stützvolumen ist dann eine Zahl
    über eine Kante. Am Balken bei x = −2 stand die Hälfte B mit den Stiften
    auf 1,4 mm² erster Schicht und „kostete" 2 988 mm³, weniger als jede
    Naht, die die Überhänge trennt; Auto Split hätte sie gewählt (gemessen am
    22.09.2026). Unbekannt heißt: niemals billig.

    Seit die Vorauswahl einen Platz für eine Lage hält, die steht, steht B
    dort aufrecht auf ihrem Ende, mit den Stiften 210 mm hoch, beide Decken
    (je 45 x 6 mm, nichts darunter) über 190 mm hoch — ein ehrlicher Preis,
    und teurer als die Naht, die die Überhänge trennt.
    Die Sperre selbst gilt weiter für jede Hälfte, deren Vorauswahl nicht steht.
    """
    mesh = crossed_overhangs()

    def price(position: float, *, pins_on_b: bool) -> float:
        return autosplit._support_after_cut(
            mesh,
            autosplit.Candidate("x", position, 144.0, 1, 0.0),
            profile,
            orientation_candidates=3,
            cancelled=None,
            connector_count=2,
            pins_on_b=pins_on_b,
        )

    upright = price(-2.0, pins_on_b=True)
    assert math.isfinite(upright)
    assert upright > 2 * (45.0 * 6.0) * 190.0, "zwei freie Decken, als Säulen gerechnet"
    assert upright > price(3.25, pins_on_b=False), "die Naht zwischen den Überhängen"

    from app.core.slice.orientation import Candidate as Pose

    monkeypatch.setattr(
        autosplit,
        "best_face_candidate",
        lambda *_args, **_kwargs: Pose((0.0, 0.0, -1.0), 2988.0, 1.4, 12.0),
    )
    assert price(-2.0, pins_on_b=True) == float("inf")


def test_the_free_place_goes_to_the_cheapest_pose_that_stands(profile: Profile) -> None:
    """Am Balken bei x = −2 mit den Stiften an A hat B nur Löcher und steht auf
    der Schnittfläche. Die Heuristik reihte das ferne Ende knapp davor (Löcher
    kosten Auflage), und der freie Platz ging dorthin: 238 325 mm³ statt rund
    5 000. Auf der Schnittfläche hängen Pfosten und Decke aufrecht (616 mm²)
    2,5 mm über dem Bett, seitlich (688 mm²) 7 mm — als Säulen gerechnet die
    Obergrenze unten, die Lochdecken nicht mitgezählt.
    """
    price = autosplit._support_after_cut(
        crossed_overhangs(),
        autosplit.Candidate("x", -2.0, 144.0, 1, 0.0),
        profile,
        orientation_candidates=3,
        cancelled=None,
        connector_count=2,
        pins_on_b=False,
    )

    assert price < 616.0 * 2.5 + 688.0 * 7.0


def test_a_seam_with_pins_on_b_keeps_its_pairs_the_right_way_round(profile: Profile) -> None:
    """Trägt B die Stifte, zeigt jede Passung von B nach A — und die Namen sagen es.

    Der Schritt ``split_pinned`` mit ``pins_on_b`` setzt die Stifte an die
    zweite Hälfte, die Bohrungen in die erste. Die Passungen des Ablaufs
    müssen dem folgen, sonst zeigte ``pin_1`` auf ein Teil, das nur Löcher
    hat, und die Prüfung meldete ein fehlendes Merkmal.
    """
    from app.core.split import SplitTarget, apply_pinned_split

    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    History(document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(80.0, 60.0, 40.0)))
    applied = apply_pinned_split(
        document,
        [SplitTarget("obj_1", block, {})],
        {"axis": "x", "position": 0.0, "pins": 2, "shape": "round", "pins_on_b": True},
        title="Teilen",
    )
    first, second = applied.object_ids
    assert all(fit.a.object_id == second and fit.b.object_id == first for fit in applied.fits)

    result = evaluate(document, profile, sources=ProjectSources(project))
    assert result.complete
    a, b = result.scene.objects[first], result.scene.objects[second]
    assert "pin_1" in b.features and "bore_1" in a.features
    assert "Löcher" in str(a.name) and "Stifte" in str(b.name)
    assert b.mesh.bounds.minimum[0] < -1.0, "die Stifte von B ragen über die Naht nach A"
    assert a.mesh.bounds.maximum[0] == pytest.approx(0.0, abs=1e-6), "A trägt keine"
    assert "fit.missing_feature" not in [f.code for f in result.scene.report.findings]


@pytest.mark.parametrize("material", ["tpu-95a", "pla"])
def test_a_seam_follows_the_material_it_is_printed_in(material: str) -> None:
    """Geteilt in PETG, gerechnet in einem anderen Material: die Passung zieht mit.

    Die Stifte rechnen ihr Spiel aus dem Material, in dem gerechnet wird. Die
    Passung schrieb bis zur Durchsicht 0.5.0 das Material des Augenblicks
    fest (``auto:petg``), und nach dem Wechsel auf TPU meldete der Prüfbericht
    beide Stifte als verletzt — für eine Naht, die genau richtig war. Die
    Presse verspricht „wechselt man auf PLA, ändert sich das Spiel mit".
    """
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(80.0, 60.0, 40.0)))
    applied = apply_line_split(
        project.document, "obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), mesh=block
    )
    assert applied.fits

    other = profiles.make_profile("centauri-carbon-2", material)
    result = evaluate(project.document, other, sources=ProjectSources(project))

    assert result.complete, result.scene.report.findings
    codes = [finding.code for finding in result.scene.report.findings]
    assert "fit.violated" not in codes, codes
    assert all(fit.tolerance == "auto:" for fit in project.document.fits)


def z_shape(longer: float = 0.0) -> MeshData:
    """Zwei lange Stäbe, versetzt, verbunden durch eine schräge Strebe.

    400 mm lang, also zu lang für jedes Bett bis 256. Jede achsparallele Ebene,
    die beide Hälften aufs Bett bringt (x zwischen etwa −45 und 45), schneidet
    mindestens zwei Stäbe, meist dazu die Strebe — zwei oder drei Konturen, so
    viele Brücken. Eine schräge Ebene quer zur Strebe schneidet nur die Strebe.

    ``longer`` verlängert den ersten Stab nach außen: Dann braucht das Teil
    einen Schnitt mehr, und die schräge Naht wird der zweite eines Laufs.
    """
    import manifold3d as m

    first = m.Manifold.cube((240.0 + longer, 20.0, 20.0)).translate((-200.0 - longer, -10.0, 0.0))
    second = m.Manifold.cube((240.0, 20.0, 20.0)).translate((-40.0, 140.0, 0.0))
    strut = (
        m.Manifold.cube((math.hypot(160.0, 150.0), 20.0, 20.0), center=True)
        .rotate((0.0, 0.0, math.degrees(math.atan2(150.0, 160.0))))
        .translate((0.0, 75.0, 10.0))
    )
    built = (first + second + strut).to_mesh64()
    return MeshData.of(
        trimesh.Trimesh(
            vertices=np.array(built.vert_properties[:, :3]),
            faces=np.array(built.tri_verts),
            process=False,
        )
    )


def test_a_tilted_plane_is_tried_when_every_upright_one_cuts_three_bars(profile: Profile) -> None:
    """RM-080, T3: schräge Ebenen in der automatischen Suche.

    Bis zum 23.09.2026 blieb die Suche achsparallel. Am Z aus zwei Stäben und
    einer Strebe gewann damit eine Naht durch zwei oder drei Konturen — so
    viele dünne Brücken, so viele Stellen zum Kleben. Liegt die beste achsparallele Ebene über
    der Schwelle, fragt die Suche jetzt einen Fächer gekippter Richtungen
    (15, 30 und 45 Grad zur Schnittachse, aus ganzzahligen Ecken und damit auf
    jeder Maschine dieselben) und nimmt die, die eine Kontur schneidet und
    beide Hälften aufs Bett bringt.
    """
    mesh = z_shape()
    axis_only = [
        entry
        for entry in autosplit._judge(
            mesh, "x", np.linspace(*autosplit._window(mesh, profile, "x"), autosplit.SAMPLES)
        )
        if entry.area > 0.0
    ]
    assert min(entry.contours for entry in axis_only) >= 2, "der Prüfkörper trifft den Fall"

    candidate = autosplit.find_plane(mesh, profile)

    assert candidate is not None
    assert candidate.normal is not None, "die Naht ist schräg"
    assert abs(candidate.normal[2]) < 1e-9
    assert candidate.contours == 1
    assert autosplit.find_plane(mesh, profile) == candidate, "und jedes Mal dieselbe"

    outcome = autosplit.split_to_fit(mesh, profile)
    assert len(outcome.parts) == 2
    for part in outcome.parts:
        assert part.is_watertight
        assert autosplit.fits(part, profile)

    plan = plan_split(mesh, "obj_1", profile)
    assert [draft.op for draft in plan.drafts] == ["split_line"]
    params = plan.drafts[0].params
    assert math.isclose(math.hypot(params["normal_x"], params["normal_y"]), 1.0, abs_tol=1e-9)

    # Und der Weg in den Verlauf: ein Schritt, Passungen je Stift, die Hälften passen.
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/1_z.stl", sha256=""
    )
    project.sources["src_1"] = mesh.raw.export(file_type="stl")
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    applied = apply_planned(project.document, plan, "obj_1")
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    assert len(applied.fits) == plan.pins_at(0, 2)
    codes = [finding.code for finding in result.scene.report.findings]
    assert "fit.missing_feature" not in codes, codes
    for object_id in applied.object_ids:
        assert autosplit.fits(result.scene.objects[object_id].mesh, profile), object_id


def test_a_run_with_a_tilted_seam_numbers_its_pieces_too(profile: Profile) -> None:
    """Ab drei Stücken zählt ein Lauf auch dann, wenn eine Naht schräg liegt (RM-229, RM-080 T3).

    Eine schräge Naht geht als *An gezeichneter Linie trennen* in den Verlauf.
    Die Zählung schrieb ihre drei Felder in jeden Schritt des Laufs, und
    ``SplitLineParams`` kannte sie nicht: Die ganze Teilung scheiterte mit
    „Diesen Parameter gibt es bei dieser Operation nicht.“ (Durchsicht 0.5.1).
    Sollwert: drei Stücke aus dem Plan, gezählt in ihrer Reihenfolge.
    """
    mesh = z_shape(longer=250.0)
    plan = plan_split(mesh, "obj_1", profile)
    assert [draft.op for draft in plan.drafts] == ["split_pinned", "split_line"], (
        "der Prüfkörper trifft den Fall: zweiter Schnitt schräg"
    )
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/1_z.stl", sha256=""
    )
    project.sources["src_1"] = mesh.raw.export(file_type="stl")
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )

    applied = apply_planned(project.document, plan, "obj_1")
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    names = [source_text(result.scene.objects[entry].name) for entry in applied.object_ids]
    assert [name.split(" · ")[0] for name in names] == [
        f"1_z {number} von 3" for number in (1, 2, 3)
    ], names


def test_an_upright_seam_that_is_good_enough_stays_upright(profile: Profile) -> None:
    """Die Gegenprobe: Wo achsparallel eine gute Naht liegt, wird nichts gekippt."""
    candidate = autosplit.find_plane(bar(), profile)
    assert candidate is not None and candidate.normal is None


def test_the_tilted_fan_listens_to_cancel(profile: Profile) -> None:
    """Der Fächer fragt vor jeder Richtung nach dem Abbruch (§15.6)."""
    token = CancelSignal()
    token.cancel()
    with pytest.raises(OperationCancelled):
        autosplit._tilted(z_shape(), profile, "x", 0.0, cancelled=token)


def test_the_tilted_fan_is_the_same_on_every_machine() -> None:
    """Zwölf Richtungen aus ganzzahligen Ecken — kein ``np.cos``, keine Plattformfrage."""
    fan = autosplit.tilted_normals("x")
    assert len(fan) == 12 and len(set(fan)) == 12
    for normal in fan:
        assert math.isclose(math.hypot(*normal), 1.0, abs_tol=1e-15)
        assert normal[0] > 0.0


# --- die Folge als Ganzes, Symmetrie, Lücken (RM-080, T6/T7) -------------------


def built_split(mesh: MeshData, profile: Profile, *, pins: int = 2):
    """Auto Split den Weg des Kunden: planen, anwenden, auswerten.

    Zurück kommen der Plan, was angewandt wurde, und das Ergebnis der
    Auswertung — gemessen wird an den gebauten Stücken mit ihren wirklichen
    Verbindern, nicht an den nackten Hälften der Suche.
    """
    project = new_project(profile.printer.id, profile.material.id)
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/1_teil.stl", sha256=""
    )
    project.sources["src_1"] = mesh.raw.export(file_type="stl")
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    plan = plan_split(mesh, "obj_1", profile, pins=pins)
    applied = apply_planned(project.document, plan, "obj_1", pins=pins)
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    return plan, applied, result


def built_pieces(mesh: MeshData, profile: Profile, *, pins: int = 2) -> list[MeshData]:
    """Die gebauten Stücke einer Auto-Split-Teilung, samt Stiften und Bohrungen."""
    _plan, applied, result = built_split(mesh, profile, pins=pins)
    return [result.scene.objects[object_id].mesh for object_id in applied.object_ids]


def manifold_body(shape: Any) -> MeshData:
    """Ein Körper aus ``manifold3d``, wie ihn die Tests hier bauen."""
    built = shape.to_mesh64()
    return MeshData.of(
        trimesh.Trimesh(
            vertices=np.array(built.vert_properties[:, :3]),
            faces=np.array(built.tri_verts),
            process=False,
        )
    )


def block(size: tuple[float, float, float], at: tuple[float, float, float] = (0.0, 0.0, 0.0)):
    import manifold3d as m

    return m.Manifold.cube(size, center=True).translate(at)


def slotted_bar(length: float = 730.0) -> MeshData:
    """Ein Balken mit einem Durchbruch genau dort, wo drei Stücke ihre erste Naht brauchen.

    Auf einem 252er Bett (256 weniger Rand) braucht ein 730 mm langer Balken
    drei Stücke — die untere Schranke, 730/252 aufgerundet. Dafür muss die
    erste Naht zwischen x = -139 (sonst ist der Rest länger als zwei Betten)
    und x = -113 (sonst passt das erste Stück nicht) liegen. Genau dort, von
    -150 bis -100, geht ein Durchbruch durch den Balken: Jede Naht hat dort
    zwei Konturen. Die Suche für sich nimmt eine Naht mit einer Kontur weiter
    links — und braucht danach vier Stücke.
    """
    return manifold_body(
        block((length, 60.0, 40.0), (0.0, 0.0, 20.0))
        - block((50.0, 20.0, 60.0), (-125.0, 0.0, 20.0))
    )


def fork() -> MeshData:
    """Ein Sockel von 400 mm und zwei 600 mm hohe Zinken an seinen Enden.

    Nach dem ersten Schnitt quer zur Höhe besteht das obere Stück aus zwei
    losen Zinken, 370 mm auseinander — zusammen breiter als das Bett, einzeln
    schmal. Keine Ebene mit Schnittfläche macht sie kleiner; die Lücke
    zwischen ihnen tut es ohne Naht.
    """
    return manifold_body(
        block((400.0, 30.0, 40.0), (0.0, 0.0, 20.0))
        + block((30.0, 30.0, 600.0), (-185.0, 0.0, 300.0))
        + block((30.0, 30.0, 600.0), (185.0, 0.0, 300.0))
    )


def test_the_sequence_is_planned_as_a_whole(profile: Profile) -> None:
    """RM-080, T7: Braucht ein Teil mehrere Schnitte, zählt die ganze Folge.

    Die Suche allein nahm am Balken mit Durchbruch die schönste erste Naht —
    eine Kontur, links vom Durchbruch — und brauchte danach vier Stücke. Die
    Planung teilt je Nahtlage den Rest zu Ende und nimmt die mit den wenigsten
    Stücken: drei, die untere Schranke, und eine Naht mit zwei Brücken im
    Durchbruch. Klebestellen sind es gleich viele: 2 + 1 gegen 1 + 1 + 1.
    """
    mesh = slotted_bar()
    assert autosplit.fewest_parts(mesh, profile) == 3

    outcome = autosplit.split_to_fit(mesh, profile, pins=0)

    assert len(outcome.parts) == 3
    assert sum(step.plane.contours for step in outcome.cuts) == 3
    assert "split.fewest_parts" in {finding.code for finding in outcome.findings}
    for part in outcome.parts:
        assert part.is_watertight
        assert autosplit.fits(part, profile)


def test_the_planned_sequence_holds_with_pins_and_is_reproducible(profile: Profile) -> None:
    """Dieselbe Folge mit Stiften — und jedes Mal dieselbe (§11.3).

    Die gebauten Stücke passen samt ihren wirklichen Stiften aufs Bett, und die
    Passungen zeigen auf Merkmale, die es gibt.
    """
    mesh = slotted_bar()
    first = autosplit.split_to_fit(mesh, profile)
    second = autosplit.split_to_fit(mesh, profile)

    assert len(first.parts) == 3
    assert [step.plane for step in first.cuts] == [step.plane for step in second.cuts]
    plan, applied, result = built_split(mesh, profile)
    assert len(applied.object_ids) == 3
    for object_id in applied.object_ids:
        assert autosplit.fits(result.scene.objects[object_id].mesh, profile), object_id
    codes = [finding.code for finding in result.scene.report.findings]
    assert "fit.missing_feature" not in codes, codes
    assert len(applied.fits) == sum(plan.pins_at(index, 2) for index in range(plan.cuts)), (
        "jede Naht behält ihre Passungen, auch die eines später noch einmal geteilten Stücks"
    )


def test_only_the_half_with_the_pins_grows(profile: Profile) -> None:
    """Die Stiftzugabe gehört der Hälfte, die die Stifte trägt.

    Bis zum 23.09.2026 bekamen beide Hälften sie. Ein 760 mm langer Balken
    passt in vier Stücke (760/252 aufgerundet); mit der doppelten Zugabe
    wurden es fünf, weil das mittlere Stück an beiden Enden je einen Stift
    zu tragen schien, den es gar nicht hatte.
    """
    mesh = bar(760.0)

    outcome = autosplit.split_to_fit(mesh, profile)

    assert len(outcome.parts) == autosplit.fewest_parts(mesh, profile) == 4
    for built in built_pieces(mesh, profile):
        assert autosplit.fits(built, profile)


def test_the_child_reserve_follows_the_pins() -> None:
    """Die Zugabe hängt an der Hälfte mit Stiften — an A, oder an B, wenn die Suche es sagt."""
    seam = autosplit.Candidate("x", 0.0, 100.0, 1, 0.0)
    on_a, bare = autosplit._child_reserves((1.0, 0.0, 0.0), seam, 5.0)
    assert on_a == (6.0, 0.0, 0.0) and bare == (1.0, 0.0, 0.0)
    bare, on_b = autosplit._child_reserves((1.0, 0.0, 0.0), replace(seam, pins_on_b=True), 5.0)
    assert on_b == (6.0, 0.0, 0.0) and bare == (1.0, 0.0, 0.0)


def test_loose_arms_are_parted_at_the_gap(profile: Profile) -> None:
    """Ein Stück aus zwei losen Teilen wird an der Lücke getrennt, ohne Naht.

    Bis zum 23.09.2026 endete die Gabel nach zwei Schnitten mit „keine
    brauchbare Trennebene" — gemessen genauso am Pflock aus dem Korpus,
    anderthalbfach. Jetzt passt jedes Stück; wo die Folge an einer Lücke
    trennt, hat der Schritt keine Kontur und keine Stifte.
    """
    mesh = fork()

    outcome = autosplit.split_to_fit(mesh, profile)

    codes = {finding.code for finding in outcome.findings}
    assert "split.no_plane" not in codes and "split.too_many_parts" not in codes
    assert all(autosplit.fits(part, profile) for part in outcome.parts)
    plan, applied, result = built_split(mesh, profile)
    for step, draft in zip(plan.outcome.cuts, plan.drafts, strict=True):
        if step.plane.gap:
            assert draft.params["pins"] == 0
    for object_id in applied.object_ids:
        assert autosplit.fits(result.scene.objects[object_id].mesh, profile), object_id
    assert "fit.missing_feature" not in [f.code for f in result.scene.report.findings]


def test_a_recognised_pin_without_a_twin_does_not_shift_a_later_seam(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-267: Ein erkannter Stift ohne Zwilling verschiebt die Stifte späterer Nähte nicht.

    Auto Split plant die Passungen jeder Naht mit den Namen ihrer Stifte, bevor
    die Schritte rechnen. Der Schritt zählte seine Nummern nach jedem Namen
    ``pin_…`` und ``bore_…`` am Stück — auch nach einem erkannten Stift, den
    die Zuordnung keinem erklärten zuwies (ERKENNUNG-16, die Gabel): Er hieß
    ``pin_3``, die Verbinder der nächsten Naht rückten eine Nummer weiter, zwei
    Passungen zeigten ins Leere und eine auf den fremden Stift. Nachgestellt
    wird die Empfindlichkeit selbst: Die Zuordnung lässt jeden erkannten
    Stift umkämpft, wie vor ERKENNUNG-16. Jetzt trägt jeder Schritt die
    Nummer, die der Plan ihm gab, und der fremde Stift weicht aus.
    """
    import dataclasses
    import importlib

    evaluation = importlib.import_module("app.core.scene.evaluate")
    original = evaluation.declared_partners

    def contested(declared: Any, detected: Any, centre: Any, diagonal: Any, **kwargs: Any) -> Any:
        seen = original(declared, detected, centre, diagonal, **kwargs)
        pinned = sorted(name for name in seen.mapping if declared[name].kind == "pin")
        return dataclasses.replace(
            seen,
            mapping={name: found for name, found in seen.mapping.items() if name not in pinned},
            ambiguous={**seen.ambiguous, **{name: (seen.mapping[name],) for name in pinned}},
            fresh=(*seen.fresh, *(seen.mapping[name] for name in pinned)),
        )

    monkeypatch.setattr(evaluation, "declared_partners", contested)
    _plan, applied, result = built_split(fork(), profile)

    stray = [
        (object_id, name)
        for object_id in applied.object_ids
        for name, feature in result.scene.objects[object_id].features.items()
        if feature.kind == "pin" and feature.provenance == "detected"
    ]
    assert stray, "the recognition must have left a pin without its twin"
    codes = [finding.code for finding in result.scene.report.findings]
    assert "fit.missing_feature" not in codes
    assert len(applied.fits) == 10
    for fit in applied.fits:
        pin = result.scene.objects[fit.a.object_id].features[fit.a.feature_id]
        bore = result.scene.objects[fit.b.object_id].features[fit.b.feature_id]
        assert (pin.kind, pin.provenance, bore.kind, bore.provenance) == (
            "pin",
            "generated",
            "hole",
            "generated",
        ), fit.name
        assert pin.params["centre"] == pytest.approx(bore.params["centre"]), fit.name


def test_a_gap_is_found_where_no_edge_crosses() -> None:
    """Eine Lücke ist, wo keine Kante die Ebene kreuzt und beiderseits Material liegt."""
    two = manifold_body(
        block((10.0, 10.0, 10.0), (-20.0, 0.0, 0.0)) + block((10.0, 10.0, 10.0), (20.0, 0.0, 0.0))
    )
    found = autosplit._gaps(two, "x", np.array([-20.0, 0.0, 14.0, 16.0, 30.0]))
    assert [entry.position for entry in found] == [0.0, 14.0]
    assert all(entry.gap and entry.area == 0.0 for entry in found)


def test_the_mirror_plane_is_measured_not_guessed() -> None:
    """T6: Symmetrie wird gemessen — an der Oberfläche, gegen die Vergleichstoleranz."""
    from app.core import units
    from app.core.geom.symmetry import mirror_plane

    box = MeshData.of(trimesh.creation.box(extents=(40.0, 20.0, 10.0)))
    found = mirror_plane(box, (1.0, 0.0, 0.0))
    assert found is not None and found.position == pytest.approx(0.0) and found.deviation < 1e-9

    ell = manifold_body(
        block((40.0, 10.0, 10.0), (0.0, 0.0, 0.0)) + block((10.0, 30.0, 10.0), (15.0, 15.0, 0.0))
    )
    assert mirror_plane(ell, (1.0, 0.0, 0.0)) is None, "ein L ist quer zu x nicht spiegelgleich"
    assert mirror_plane(ell, (0.0, 0.0, 1.0)) is not None, "flach liegend aber schon"

    # Ein Zylinder, um 7 Grad gedreht: Seine Sehnen liegen beiderseits der
    # Ebene verschieden, und trotzdem ist er spiegelgleich — bis auf die
    # Sehnenhöhe, weit unter der Toleranz.
    turned = trimesh.creation.cylinder(radius=20.0, height=30.0, sections=48)
    turned.apply_transform(trimesh.transformations.rotation_matrix(np.radians(7.0), [0, 0, 1]))
    found = mirror_plane(MeshData.of(turned), (1.0, 0.0, 0.0))
    assert found is not None and 0.0 < found.deviation < found.tolerance

    # Ein Höcker über der Toleranz macht es zu einer Form, nicht zu Rauschen.
    bump = manifold_body(block((40.0, 20.0, 10.0)) + block((4.0, 4.0, 4.0), (12.0, 0.0, 6.0)))
    assert units.match_tolerance(float(np.linalg.norm(bump.bounds.size))) < 4.0
    assert mirror_plane(bump, (1.0, 0.0, 0.0)) is None


def centre_rib(thickness: float = 0.6) -> MeshData:
    """Ein spiegelgleicher Balken mit einem dünnen Steg genau in der Mitte.

    Der Steg ist dünner als ``2 · PRISM_STEP``: Die Querschnitte einen halben
    Millimeter daneben haben ihn nicht, und die Nahtbewertung sieht in der
    Mitte eine sprunghafte Änderung. Die Suche für sich nimmt deshalb eine Naht
    daneben — zwei ungleiche Hälften, eine mit dem ganzen Steg.
    """
    return manifold_body(
        block((400.0, 60.0, 40.0), (0.0, 0.0, 20.0))
        + block((thickness, 70.0, 50.0), (0.0, 0.0, 20.0))
    )


def test_a_symmetric_part_is_cut_in_its_mirror_plane(profile: Profile) -> None:
    """T6: In der Symmetrieebene sind beide Schnittflächen gleich — der Steg stört dort nicht.

    Die Querschnittsänderung misst, ob die zwei Schnittflächen verschieden
    ausfallen. An der Spiegelebene sind sie es nie. Die Naht liegt deshalb in
    der Mitte, beide Hälften sind gleich, und der Prüfbericht sagt es.
    """
    mesh = centre_rib()
    window = autosplit._window(mesh, profile, "x")
    sampled = [
        entry
        for entry in autosplit._judge(mesh, "x", np.linspace(window[0], window[1], 33))
        if entry.area > 0.0
    ]
    assert abs(min(sampled, key=autosplit._candidate_order).position) > 0.01, (
        "der Prüfkörper trifft den Fall: ohne Symmetrie gewinnt eine Naht daneben"
    )

    outcome = autosplit.split_to_fit(mesh, profile, pins=0)

    assert len(outcome.cuts) == 1
    assert outcome.cuts[0].plane.symmetric
    assert outcome.cuts[0].plane.position == pytest.approx(0.0, abs=1e-9)
    first, second = outcome.parts
    assert first.volume == pytest.approx(second.volume, rel=1e-9)
    assert "split.symmetric" in {finding.code for finding in outcome.findings}


def test_the_mirror_plane_does_not_win_at_a_waist(profile: Profile) -> None:
    """Die Hantel ist spiegelgleich, und ihre Mitte ist die dünnste Stelle (T1) — dort nicht."""
    mesh = dumbbell()
    mirror = autosplit._mirror_candidate(
        mesh, "x", autosplit._window(mesh, profile, "x"), protect=(), cancelled=None
    )
    assert mirror is not None and mirror.notch > 0.0, "die Hantel ist spiegelgleich, mit Taille"

    candidate = autosplit.find_plane(mesh, profile)

    assert candidate is not None and not candidate.symmetric
    assert abs(candidate.position) > 1.0


def test_a_long_symmetric_bar_comes_apart_in_equal_pieces() -> None:
    """T6 in der Folge: erst die Mitte, dann jede Hälfte gespiegelt.

    Ein 900 mm langer Balken braucht vier Stücke. Die Säge vom Rand nahm
    252, 252, 198 und 198; geplant sind es viermal 225 — und die zwei
    Hälften sind gespiegelt geschnitten, nicht je für sich gesucht.
    """
    from app.core.knowledge import profiles

    flat = profiles.make_profile("bambu-a1", "petg")
    outcome = autosplit.split_to_fit(bar(900.0), flat, pins=0)

    lengths = sorted(float(part.bounds.size[0]) for part in outcome.parts)
    assert lengths == pytest.approx([225.0] * 4)
    positions = sorted(step.plane.position for step in outcome.cuts)
    assert positions == pytest.approx([-225.0, 0.0, 225.0])
    codes = [finding.code for finding in outcome.findings]
    assert "split.symmetric" in codes and "split.fewest_parts" in codes


def test_a_reflected_cut_lands_on_the_mirrored_place() -> None:
    """Die Spiegelung eines Schnitts: dieselbe Achse gespiegelt, eine andere Achse unverändert."""
    mirror = SectionPlane((1.0, 0.0, 0.0), 10.0)
    same_axis, flipped = autosplit._reflected(autosplit.Candidate("x", 30.0, 1.0, 1, 0.0), mirror)
    assert flipped and same_axis.position == pytest.approx(-10.0) and same_axis.normal is None
    other_axis, flipped = autosplit._reflected(autosplit.Candidate("y", 5.0, 1.0, 1, 0.0), mirror)
    assert not flipped and other_axis.position == pytest.approx(5.0)
    tilted = autosplit.tilted_normals("y")[0]
    turned, _flipped = autosplit._reflected(
        autosplit.Candidate("y", 7.0, 1.0, 1, 0.0, normal=tilted), mirror
    )
    assert turned.normal is not None and turned.normal[1] > 0.0
    assert math.isclose(math.hypot(*turned.normal), 1.0, abs_tol=1e-12)


def test_the_planning_listens_to_cancel(profile: Profile, monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Planung fragt zwischen ihren Probeschnitten nach dem Abbruch (§15.6)."""
    signal = CancelSignal()
    cuts_after_cancel: list[int] = []
    original = autosplit._cut_in_two

    def watched(*args: Any) -> Any:
        if signal.cancelled:
            cuts_after_cancel.append(1)
        return original(*args)

    def cancel_while_planning(_fraction: float, text: str) -> None:
        if "Schnittfolge" in text:
            signal.cancel()

    monkeypatch.setattr(autosplit, "_cut_in_two", watched)
    with pytest.raises(OperationCancelled):
        autosplit.split_to_fit(
            slotted_bar(), profile, pins=0, cancelled=signal, progress=cancel_while_planning
        )
    assert not cuts_after_cancel, "nach dem Abbruch lief kein Probeschnitt mehr"


def test_the_planning_reports_its_progress(profile: Profile) -> None:
    """Die Planung sagt, woran sie ist, und der Balken läuft nie rückwärts."""
    seen: list[tuple[float, str]] = []
    autosplit.split_to_fit(
        slotted_bar(),
        profile,
        pins=0,
        progress=lambda fraction, text: seen.append((fraction, text)),
    )
    fractions = [fraction for fraction, _text in seen]
    assert fractions == sorted(fractions)
    assert any("Schnittfolge" in text for _fraction, text in seen)


def test_a_spent_budget_falls_back_to_the_plain_search(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Budget begrenzt die Probeschnitte als Zahl, nicht als Zeit (§11.3).

    Ohne Budget entscheidet die Naht selbst — die Teilung wird trotzdem fertig,
    nur wieder mit vier Stücken.
    """
    monkeypatch.setattr(autosplit, "PLAN_BUDGET", 0)
    outcome = autosplit.split_to_fit(slotted_bar(), profile, pins=0)
    assert len(outcome.parts) == 4
    assert all(autosplit.fits(part, profile) for part in outcome.parts)


def test_the_window_knows_the_corner_the_bed_does_not_have(profile: Profile) -> None:
    """Die Sperrzone des Centauri Carbon 2 nimmt einem breiten Stück Länge.

    Das Bett ist 252 mm breit (256 weniger zwei Rand), die Sperrzone mit Rand
    reicht von x = 116 bis 126 und bis y = -106. Ein Stück, 245 mm tief, muss
    in y über ihr liegen, also bleibt in x von -126 bis 116: 242 mm. Ein
    schmales Stück legt sich daneben und hat die vollen 252.
    """
    wide = MeshData.of(trimesh.creation.box(extents=(300.0, 245.0, 10.0)))
    narrow = MeshData.of(trimesh.creation.box(extents=(300.0, 60.0, 10.0)))
    assert autosplit._room(wide, profile, "x") == pytest.approx(242.0, abs=0.01)
    assert autosplit._room(narrow, profile, "x") == pytest.approx(252.0)


def test_two_loose_blocks_come_apart_at_the_gap(profile: Profile) -> None:
    """Zwei lose Blöcke, zusammen 500 mm breit: getrennt an der Lücke, ohne Naht.

    Bis zum 23.09.2026 lag das ganze Suchfenster in der Lücke — jede
    abgetastete Ebene ohne Schnittfläche —, und der Kunde bekam „keine
    brauchbare Trennebene" für ein Teil, das nur auseinanderzulegen war.
    """
    left = trimesh.creation.box(extents=(200.0, 60.0, 40.0))
    left.apply_translation((-150.0, 0.0, 0.0))
    right = trimesh.creation.box(extents=(200.0, 60.0, 40.0))
    right.apply_translation((150.0, 0.0, 0.0))
    mesh = MeshData.of(trimesh.util.concatenate([left, right]))

    outcome = autosplit.split_to_fit(mesh, profile)

    assert len(outcome.parts) == 2
    assert [step.plane.contours for step in outcome.cuts] == [0]
    assert "split.no_plane" not in {finding.code for finding in outcome.findings}
    plan = plan_split(mesh, "obj_1", profile)
    assert plan.drafts[0].params["pins"] == 0, "an einer Lücke sitzt kein Stift"
    assert plan.seated == (0,)


def waisted_bar() -> MeshData:
    """900 mm, spiegelgleich, und in der Mitte jeder Hälfte eine sanfte Mulde.

    Jede Hälfte hat damit zwei gleich gute Nähte links und rechts ihrer Mulde
    (T1 meidet die Mulde selbst). Sucht jede Hälfte für sich, entscheidet der
    Gleichstand beide Male für die tiefere Lage — und die Stücke beiderseits
    der Mitte sind keine Spiegelbilder mehr.
    """
    line = [[0.0, -450.0], [40.0, -450.0]]
    for centre in (-225.0, 225.0):
        line += [[40.0, centre - 60.0], [32.0, centre], [40.0, centre + 60.0]]
    line += [[40.0, 450.0], [0.0, 450.0]]
    body = trimesh.creation.revolve(np.array(line), sections=64)
    body.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    return MeshData.of(body)


def test_the_pieces_beside_a_mirror_seam_are_cut_as_mirror_images() -> None:
    """T6: Die Stücke beiderseits der Symmetrieebene werden gespiegelt geschnitten.

    Gemessen am Balken mit zwei Mulden: Je für sich gesucht lagen die Nähte bei
    -198, 54 und 282 — die rechte Hälfte nahm die andere Seite ihrer Mulde als
    die linke. Gespiegelt liegen sie bei -198, 0 und 198, und die äußeren und
    inneren Stücke sind je gleich lang.
    """
    from app.core.knowledge import profiles

    flat = profiles.make_profile("bambu-a1", "petg")
    outcome = autosplit.split_to_fit(waisted_bar(), flat, pins=0)

    positions = sorted(step.plane.position for step in outcome.cuts)
    assert positions == pytest.approx([-positions[2], 0.0, positions[2]], abs=1e-9)
    lengths = sorted(float(part.bounds.size[0]) for part in outcome.parts)
    assert lengths[0] == pytest.approx(lengths[1]) and lengths[2] == pytest.approx(lengths[3])
