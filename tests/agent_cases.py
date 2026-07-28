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
    pillar: str = "C"
    """C — adapting a foreign model. A — building something new (§2.2)."""
    empty_scene: bool = False
    """Pillar A starts on an empty project, pillar C on the plate."""
    expects_part: bool = False
    """§35: is an existing part used instead of own geometry?"""


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

#: Way 2 of §2.2 — building something new, on an empty project. What is measured
#: here is what §35 asks about pillar A: is a part used instead of own geometry,
#: and do the main dimensions become parameters.
CASES_A: tuple[Case, ...] = (
    Case(
        id="bracket",
        request="Bau einen Halter, 60 mm breit, 40 mm tief, 6 mm stark, mit zwei M4-Löchern.",
        pillar="A",
        empty_scene=True,
        expects_ops=("create_box", "insert_screw_hole", "insert_screw_hole"),
        expects_parameter=True,
        expects_part=True,
    ),
    Case(
        id="magnet_lid",
        request="Ein Deckel mit vier Magnettaschen für 8x3-Magnete.",
        pillar="A",
        empty_scene=True,
        expects_ops=("create_box", "insert_magnet_pocket"),
        expects_part=True,
    ),
    Case(
        id="wall_holder",
        request="Ein Wandhalter für einen Router, 30 mm breit.",
        pillar="A",
        empty_scene=True,
        expects_ops=("insert_wall_mount",),
        expects_part=True,
        note="The part exists — building the plate by hand would be the wrong answer.",
    ),
    Case(
        id="cable_exit",
        request="Eine Kabeldurchführung mit Zugentlastung in eine 3 mm starke Wand.",
        pillar="A",
        empty_scene=True,
        expects_ops=("create_box", "insert_cable_gland"),
        expects_part=True,
    ),
    Case(
        id="threaded_stud",
        request="Ein M6-Gewindezapfen, 12 mm lang.",
        pillar="A",
        empty_scene=True,
        expects_ops=("insert_printed_thread",),
        expects_part=True,
    ),
    Case(
        id="nut_plate",
        request="Eine Platte mit einer Mutternfalle für M4 von der Seite.",
        pillar="A",
        empty_scene=True,
        expects_ops=("create_box", "insert_nut_trap"),
        expects_part=True,
    ),
    Case(
        id="spacer",
        request="Eine Distanzhülse, 12 mm hoch, für eine M3-Schraube.",
        pillar="A",
        empty_scene=True,
        expects_ops=("create_cylinder", "insert_screw_hole"),
        expects_part=True,
    ),
    Case(
        id="hinge",
        request="Ein Filmscharnier für einen Deckel, 30 mm breit.",
        pillar="A",
        empty_scene=True,
        expects_ops=("insert_living_hinge",),
        expects_part=True,
    ),
    Case(
        id="snap_box",
        request="Ein Schnappverschluss für eine Box.",
        pillar="A",
        empty_scene=True,
        expects_ops=("insert_snap_fit",),
        expects_part=True,
    ),
    Case(
        id="keyhole_back",
        request="Eine Schlüsselloch-Aufhängung auf der Rückseite.",
        pillar="A",
        empty_scene=True,
        expects_ops=("create_box", "insert_keyhole"),
        expects_part=True,
    ),
    Case(
        id="stiffen",
        request="Versteife die Wand mit einer Rippe.",
        pillar="A",
        empty_scene=True,
        expects_ops=("create_box", "insert_rib"),
        expects_part=True,
    ),
    Case(
        id="dowels",
        request="Setz Passstifte, damit die beiden Hälften zueinander finden.",
        pillar="A",
        empty_scene=True,
        expects_ops=("create_box", "insert_dowel"),
        expects_part=True,
    ),
    Case(
        id="inserts",
        request="Vier Einpressbuchsen M3 in die Ecken.",
        pillar="A",
        empty_scene=True,
        expects_ops=("create_box", "insert_heatset_m4"),
        expects_part=True,
    ),
    Case(
        id="parameterise",
        request="Mach die Breite und die Höhe zu Projektparametern.",
        pillar="A",
        empty_scene=True,
        expects_parameter=True,
        note="§39: main dimensions are parameters, not scattered numbers.",
    ),
    Case(
        id="free_shape",
        request="Ein Trichter mit 40 mm oben und 10 mm unten.",
        pillar="A",
        empty_scene=True,
        expects_ops=("create_from_scad",),
        note="No part fits — this is what the fallback level is for (§24.1).",
    ),
)

ALL_CASES: tuple[Case, ...] = (*CASES, *CASES_A)

AMBIGUOUS = tuple(case for case in ALL_CASES if case.ambiguous)


def by_id(identifier: str) -> Case:
    for case in ALL_CASES:
        if case.id == identifier:
            return case
    raise KeyError(identifier)
