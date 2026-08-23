"""Die Referenzanfragen für Säule C (Bauplan §35, §40 für P4).

Fünfzehn Anfragen an Weg 1 — ein fremdes Modell anpassen —, von denen drei mit
Absicht mehrdeutig sind. Sie sind Daten, keine Testfunktionen, denn zwei
Läufer benutzen sie: die Suite in ``test_agent_suite.py``, die ohne Modell
prüft, was die Mechanik garantiert, und ``tools/run_agent_suite.py``, das sie
einem echten Modell vorlegt und die Quote meldet.

Gemessen wird, was §35 benennt: wird ein vorhandener Baustein statt eigener
Geometrie benutzt, werden Hauptmaße zu Parametern, und wird gefragt, wenn die
Anfrage mehrdeutig ist.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Case:
    """Eine Referenzanfrage und wie eine gute Antwort darauf aussieht."""

    id: str
    request: str
    ambiguous: bool = False
    """Deliberately unclear — a good answer asks instead of guessing (§26.2)."""
    expects_ops: tuple[str, ...] = ()
    """Operationen, die eine gute Antwort benutzt. Leer heißt: es braucht keine."""
    expects_parameter: bool = False
    expects_answer_only: bool = False
    """Eine Frage zum Modell, keine Änderung daran."""
    selection: tuple[str, str] | None = None
    note: str = ""
    forbids_ops: tuple[str, ...] = field(default_factory=tuple)
    pillar: str = "C"
    """C — adapting a foreign model. A — building something new (§2.2)."""
    empty_scene: bool = False
    """Pillar A starts on an empty project, pillar C on the plate."""
    expects_part: bool = False
    """§35: is an existing part used instead of own geometry?"""
    expects_reading: tuple[str, ...] = ()
    """Lesende Werkzeuge, die eine gute Antwort benutzt — nachsehen statt
    raten (§26.2, Konzept Agent-Vertiefung 3.3/3.4)."""
    expects_target: bool = False
    """Eine gute Antwort wechselt Drucker oder Material (``set_print_target``)."""
    expects_mention: tuple[str, ...] = ()
    """Wörter, die in der Antwort stehen müssen — §2.6: der Chat ist auch ein
    Suchfeld, und eine Wie-Frage bekommt den Menüort genannt."""


#: Weg 1 aus §2.2, auf der Platte mit vier Bohrungen aus dem Korpus.
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
        expects_ops=("split_pinned",),
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
    # --- nachsehen statt raten (Konzept Agent-Vertiefung, Schritt 3) ----------
    Case(
        id="printable",
        request="Lässt sich das Teil so gut drucken?",
        expects_answer_only=True,
        expects_reading=("read_analysis",),
        note="Überhang, Inseln, Brücken — die Schichtanalyse weiß es, das Modell nicht.",
    ),
    Case(
        id="how_long",
        request="Wie lange dauert der Druck ungefähr?",
        expects_answer_only=True,
        expects_reading=("read_analysis",),
        note="Zeit und Material kommen aus der Schätzung, nie aus dem Bauchgefühl des Modells.",
    ),
    Case(
        id="core_hole",
        request="Welches Kernloch braucht ein M4-Gewinde?",
        expects_answer_only=True,
        expects_reading=("read_standard",),
        note="Eine Frage an die Tabelle (§24.2), nicht ans Gedächtnis des Modells.",
    ),
    Case(
        id="switch_material",
        request="Stell das Projekt auf PLA um.",
        expects_target=True,
        expects_answer_only=True,
        note="Drucker und Material reisen als DocumentChange — ein Undo nimmt beide zurück.",
    ),
    Case(
        id="where_menu",
        request="Wie kann ich eine Bohrung größer machen, ohne den Chat zu benutzen?",
        expects_answer_only=True,
        expects_mention=("Menü",),
        note="§2.6: der Chat ist auch ein Suchfeld — die Antwort nennt den Menüort.",
    ),
    Case(
        id="where_hollow",
        request="Wo finde ich das Aushöhlen im Programm?",
        expects_answer_only=True,
        expects_mention=("Menü",),
        note="Eine reine Wo-Frage: keine Operation, nur der Ort im Fenster.",
    ),
    # --- die drei mehrdeutigen ------------------------------------------------
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

#: Weg 2 aus §2.2 — etwas Neues bauen, auf einem leeren Projekt. Gemessen wird
#: hier, wonach §35 bei Säule A fragt: wird ein Baustein statt eigener Geometrie
#: benutzt, und werden die Hauptmaße zu Parametern.
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
        expects_ops=("sketch_loft",),
        forbids_ops=("create_from_scad",),
        note=(
            "Bis P13 war das der Fall für den OpenSCAD-Rückfall — jetzt kann "
            "sketch_loft ihn im Haus, und der Rückfall wäre die falsche Wahl (§30.1)."
        ),
    ),
    Case(
        id="hex_base",
        request="Ein sechseckiger Sockel, 30 mm über die Ecken, 8 mm hoch.",
        pillar="A",
        empty_scene=True,
        expects_ops=("sketch_extrude",),
        note="§30.1: Grundform über die Skizze, nie über rohe Punktlisten.",
    ),
    Case(
        id="pocket_plate",
        request="Ein Deckel 60 x 60 x 4 mm mit einer rechteckigen Tasche 40 x 40, 2 mm tief.",
        pillar="A",
        empty_scene=True,
        expects_ops=("sketch_extrude", "sketch_pocket"),
        note="Aufziehen und Tasche schneiden — der Weg für flache Frästeile (§30.1).",
    ),
    Case(
        id="handrail_bend",
        request="Ein runder Handlauf-Bogen: 12 mm dick, Bogenradius 60, 90 Grad.",
        pillar="A",
        empty_scene=True,
        expects_ops=("sketch_sweep",),
        note="Entlang eines Bogens führen — vor P13 ging das nur außerhalb (§30.1).",
    ),
)

ALL_CASES: tuple[Case, ...] = (*CASES, *CASES_A)

AMBIGUOUS = tuple(case for case in ALL_CASES if case.ambiguous)


def by_id(identifier: str) -> Case:
    for case in ALL_CASES:
        if case.id == identifier:
            return case
    raise KeyError(identifier)
