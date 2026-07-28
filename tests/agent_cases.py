"""The reference requests for pillar C (Bauplan §35, §40 for P4).

Fifteen requests to way 1 — adapting a foreign model — of which three are
deliberately ambiguous. They are data, not test functions, because two runners
use them: the suite in ``test_agent_suite.py``, which checks what the harness
guarantees without a model, and ``tools/run_agent_suite.py``, which puts them to
a real model and reports the quota.

What is measured is named in §35: is an existing part used instead of own
geometry, do main dimensions become parameters, and is a question asked when the
request is ambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Case:
    """One reference request and what a good answer looks like."""

    id: str
    request: str
    ambiguous: bool = False
    """Deliberately unclear — a good answer asks instead of guessing (§26.2)."""
    expects_ops: tuple[str, ...] = ()
    """Operations a good answer uses. Empty means: none is needed."""
    expects_parameter: bool = False
    expects_answer_only: bool = False
    """A question about the model, not a change to it."""
    selection: tuple[str, str] | None = None
    note: str = ""
    forbids_ops: tuple[str, ...] = field(default_factory=tuple)


#: Way 1 of §2.2, on the plate with four bores from the corpus.
CASES: tuple[Case, ...] = (
    Case(
        id="move",
        request="Verschieb die Platte 10 mm nach rechts.",
        expects_ops=("translate_object",),
    ),
    Case(
        id="rotate",
        request="Dreh das Teil um 90 Grad um die Z-Achse.",
        expects_ops=("rotate_object",),
    ),
    Case(
        id="on_bed",
        request="Setz das Teil auf das Druckbett.",
        expects_ops=("place_on_bed",),
    ),
    Case(
        id="scale",
        request="Skalier das Teil auf 120 Prozent.",
        expects_ops=("scale_object",),
    ),
    Case(
        id="repair",
        request="Repariere das Modell, es hat offene Stellen.",
        expects_ops=("repair",),
    ),
    Case(
        id="orient",
        request="Richte das Teil so aus, dass es möglichst wenig Stützen braucht.",
        expects_ops=("orient_for_print",),
    ),
    Case(
        id="split",
        request="Teile das Teil auf halber Höhe.",
        expects_ops=("split_plane",),
    ),
    Case(
        id="drill",
        request="Bohr ein Loch mit 5 mm Durchmesser in die Oberseite, mittig.",
        expects_ops=("drill_hole",),
        selection=("obj_1", "face_1"),
    ),
    Case(
        id="drill_on_feature",
        request="Setz noch eine Bohrung wie hole_1 daneben.",
        expects_ops=("drill_hole",),
        selection=("obj_1", "hole_1"),
    ),
    Case(
        id="duplicate",
        request="Leg eine Kopie des Teils daneben.",
        expects_ops=("duplicate_object",),
    ),
    Case(
        id="parameter",
        request="Mach die Plattenbreite zu einem Projektparameter.",
        expects_parameter=True,
        note="§39: main dimensions are parameters, not scattered numbers.",
    ),
    Case(
        id="question",
        request="Wie dick ist die Platte?",
        expects_answer_only=True,
        note="A question about the model changes nothing.",
    ),
    # --- the three ambiguous ones ---------------------------------------------
    Case(
        id="which_hole",
        request="Mach das Loch größer.",
        ambiguous=True,
        note="Four bores, no selection: which one?",
    ),
    Case(
        id="how_much_thinner",
        request="Mach das Teil dünner.",
        ambiguous=True,
        note="Thinner by how much, and in which direction?",
    ),
    Case(
        id="join_what",
        request="Verbinde die beiden Teile.",
        ambiguous=True,
        note="There is only one object in the scene.",
    ),
)

AMBIGUOUS = tuple(case for case in CASES if case.ambiguous)


def by_id(identifier: str) -> Case:
    for case in CASES:
        if case.id == identifier:
            return case
    raise KeyError(identifier)
