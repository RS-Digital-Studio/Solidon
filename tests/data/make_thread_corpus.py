"""Baut die Gewinde-Referenzkörper des Korpus (P2.5) — aus Konstruktionsmaßen, als STEP.

Dieselbe Bauart wie ``konzepte/nachweise-cad-p2-5/reference.py``: Die
Sollwerte der Tests kommen aus **diesen Maßen**, nie aus dem Prüfling. Die
Körper liegen als STEP hier, weil der zweigängige Bolzen und die Naht ohne
Rille als Sweep mit Fuzzy-Vereinigung entstehen und Sekunden kosten; die
drei Bolzen aus ``profiles.threaded_rod`` baut der genähte Weg in unter
einer halben Sekunde (RM-195). Alles Abgeleitete (Spiegelung, Lage,
Zuschnitt, Beschädigung, geteilte Träger, NURBS) baut
``tests/test_thread_import.py`` aus ``m6_rechts`` selbst.

    .venv\\Scripts\\python.exe tests/data/make_thread_corpus.py            # alle neu bauen
    .venv\\Scripts\\python.exe tests/data/make_thread_corpus.py m6_rechts  # einen neu bauen
    .venv\\Scripts\\python.exe tests/data/make_thread_corpus.py --check    # Datei gegen Erzeuger

Nur neu bauen, wenn ein Maß oder der Erzeuger sich ändert; die Sollwerte
stehen in der Fallmatrix des Tests. ``--check`` baut jeden Körper und
vergleicht Flächenzahl, Volumen und Oberfläche (auf ``CHECK_RELATIVE``) mit
der abgelegten Datei — der Wächter dafür, dass Korpus und Erzeuger nicht
auseinanderlaufen: Am 20.09.2026 lagen sie an M10 um 0,09 mm³ auseinander.
``tests/test_thread_import.py`` fährt ihn je Lauf an den drei Bolzen
(``test_the_corpus_matches_its_generator``); die zwei Sweep-Körper prüft der
Aufruf von Hand vor einem Release.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.brep import edit, profiles, step  # noqa: E402
from app.core.brep.kernel import Solid, boolean_builder, copy_shape  # noqa: E402

THREADS = HERE / "threads"


def _helix_ridge(
    root_radius: float,
    crest_radius: float,
    pitch: float,
    lead: float,
    length: float,
    phase_deg: float,
) -> Solid:
    """Ein Gang als Helix-Sweep mit dem Vierpunktprofil des Netzwegs."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.BRepLib import BRepLib
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.Geom import Geom_CylindricalSurface
    from OCP.Geom2d import Geom2d_Line
    from OCP.gp import gp_Ax2d, gp_Ax3, gp_Dir2d, gp_Pnt, gp_Pnt2d
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    turns = length / lead + 2.0
    surface = Geom_CylindricalSurface(gp_Ax3(), root_radius)
    start = math.radians(phase_deg)
    line = Geom2d_Line(gp_Ax2d(gp_Pnt2d(start, -lead), gp_Dir2d(2.0 * math.pi, lead)))
    span = math.hypot(2.0 * math.pi, lead) * turns
    helix = BRepBuilderAPI_MakeEdge(line, surface, 0.0, span).Edge()
    BRepLib.BuildCurves3d_s(helix)
    spine = BRepBuilderAPI_MakeWire(helix).Wire()
    inward = root_radius - 0.1
    corners = (
        (inward, -lead),
        (root_radius, -lead),
        (crest_radius, -lead + pitch * 0.25),
        (crest_radius, -lead + pitch * 0.55),
        (root_radius, -lead + pitch * 0.8),
        (inward, -lead + pitch * 0.8),
    )
    cs, sn = math.cos(start), math.sin(start)
    outline = BRepBuilderAPI_MakeWire()
    for index in range(len(corners)):
        a, b = corners[index - 1], corners[index]
        outline.Add(
            BRepBuilderAPI_MakeEdge(
                gp_Pnt(a[0] * cs, a[0] * sn, a[1]), gp_Pnt(b[0] * cs, b[0] * sn, b[1])
            ).Edge()
        )
    pipe = BRepOffsetAPI_MakePipeShell(spine)
    pipe.SetMode(True)
    pipe.Add(outline.Wire())
    pipe.Build()
    if not pipe.IsDone():
        raise RuntimeError("Gang: MakePipeShell scheiterte")
    pipe.MakeSolid()
    ridge = Solid(pipe.Shape())
    slab = edit.cylinder(2.0 * crest_radius + 2.0, length)
    trimmed = edit.boolean("intersection", [ridge, slab])
    explorer = TopExp_Explorer(trimmed.shape, TopAbs_SOLID)
    return Solid(TopoDS.Solid(explorer.Current()))


def _fuzzy_union(body: Solid, ridge: Solid, pitch: float, at_least: float) -> Solid:
    """Kern und Gang vereinigen — mit der Stufenleiter und einer Volumenuntergrenze.

    Ohne Toleranz verschluckt die Vereinigung den Gang still (P2.5 B3, P2.7
    B1); jede Stufe läuft auf privaten Kopien, sonst reißt die dritte nativ.
    """
    for ratio in (1e-4, 1e-3, 1e-2):
        left, _faces, _edges = copy_shape(body.shape)
        right, _faces, _edges = copy_shape(ridge.shape)
        operation = boolean_builder("union", left, right, tolerance=ratio * pitch)
        operation.Build()
        if not operation.IsDone():
            continue
        candidate = Solid(operation.Shape())
        if candidate.solid_count == 1 and candidate.is_closed and candidate.volume > at_least:
            return candidate
    raise RuntimeError("Gang ließ sich nicht mit dem Kern vereinigen")


def multi_start(major: float, pitch: float, starts: int, length: float) -> Solid:
    """Mehrgängiger Bolzen: ``starts`` Gänge, Vorschub ``starts * pitch``."""
    depth = pitch * 0.55
    root_radius = major / 2.0 - depth
    lead = starts * pitch
    body = edit.cylinder(2.0 * root_radius + 0.02, length)
    for start in range(starts):
        ridge = _helix_ridge(root_radius, major / 2.0, pitch, lead, length, 360.0 * start / starts)
        body = _fuzzy_union(body, ridge, pitch, body.volume * 1.02)
    return body


def internal_block(
    major: float, pitch: float, depth: float, play: float, size: float = 20.0
) -> Solid:
    """Gewindebohrung: Block minus Bolzen mit Spiel, unter der Mündung (z <= 0)."""
    tool = edit.moved(profiles.threaded_rod(major + play, pitch, depth), (0.0, 0.0, -depth))
    block = edit.moved(edit.box(size, size, depth), (0.0, 0.0, -depth))
    return edit.boolean("difference", [block, tool])


def seam_helix(diameter: float, height: float, pitch: float, depth: float) -> Solid:
    """Eine Wendel ohne Rille: ein hauchdünner Gang (``depth``) auf dem Zylinder."""
    root_radius = diameter / 2.0
    core = edit.cylinder(diameter + 0.02, height)
    ridge = _helix_ridge(root_radius, root_radius + depth, pitch, pitch, height, 0.0)
    return _fuzzy_union(core, ridge, pitch, core.volume * 1.0001)


#: Der halbe Kegelwinkel eines Rohrgewindes: 1:16 auf den Durchmesser.
PIPE_TAPER = math.atan(1.0 / 32.0)


def sewn_rod(
    major: float, pitch: float, length: float, *, starts: int = 1, taper: float = 0.0
) -> Solid:
    """Ein genähter Bolzen mit ``starts`` Gängen, auf ``length`` geschnitten (P2.5-Rest).

    Dasselbe ISO-nahe Profil wie ``profiles.threaded_rod``; ``major`` ist der
    Kamm-Ø auf der Höhe null, ein kegeliges Gewinde wird von dort mit
    ``tan(taper)`` je Millimeter weiter. Genäht statt vereinigt: Der
    mehrgängige Sweep-Körper oben braucht die Fuzzy-Leiter und Sekunden.
    """
    ridge = profiles.thread_ridge(major, pitch)
    lead = starts * pitch
    turns = math.ceil(length / lead) + 2
    # Die Radien des Profils gelten auf der Höhe ``start``; auf null soll der
    # Kamm ``major`` sein, darunter ist der Kegel um ``lead · tan`` schmaler.
    start = -lead
    shifted = [(radial + start * math.tan(taper), axial) for radial, axial in ridge]
    whole = profiles.helical_thread(
        shifted[0][0], pitch, turns, shifted, start=start, starts=starts, taper=taper
    )
    reach = major + 2.0 + 2.0 * length * math.tan(taper)
    return edit.boolean("intersection", [whole, edit.box(reach, reach, length)])


def internal_multi_start(
    major: float, pitch: float, starts: int, depth: float, play: float, size: float = 24.0
) -> Solid:
    """Mehrgängige Gewindebohrung: Block minus genähter Bolzen mit Spiel, unter der Mündung."""
    tool = edit.moved(
        sewn_rod(major + play, pitch, depth + 2.0 * starts * pitch, starts=starts),
        (0.0, 0.0, -depth - starts * pitch),
    )
    block = edit.moved(edit.box(size, size, depth), (0.0, 0.0, -depth))
    return edit.boolean("difference", [block, tool])


BODIES = {
    # Name: (Erzeuger, Konstruktionsmaße) — die Sollwerte des Tests folgen daraus.
    "m6_rechts": lambda: profiles.threaded_rod(6.0, 1.0, 12.0),
    "m10_rechts": lambda: profiles.threaded_rod(10.0, 1.5, 20.0),
    "m8_innen": lambda: internal_block(8.0, 1.25, 10.0, 0.2),
    "zweigaengig": lambda: multi_start(8.0, 1.0, 2, 12.0),
    "gegen_naht": lambda: seam_helix(6.0, 12.0, 1.0, 0.02),
    "dreigaengig": lambda: sewn_rod(10.0, 1.0, 12.0, starts=3),
    "innen_zweigaengig": lambda: internal_multi_start(10.0, 1.25, 2, 12.0, 0.2),
    "konisch": lambda: sewn_rod(10.0, 1.5, 12.0, taper=PIPE_TAPER),
}


#: Wie weit das Volumen der Datei vom Erzeuger abweichen darf — die
#: STEP-Rundreise liegt bei 10⁻⁸, ein anderer Erzeuger bei 10⁻⁶ und mehr.
CHECK_RELATIVE = 1e-6


def compare(name: str) -> tuple[bool, str]:
    """Baut ``name`` neu und vergleicht mit der Datei: Flächen, Volumen, Oberfläche.

    Kanten zählen nicht mit: Der STEP-Umlauf legt am genähten Bolzen eine
    doppelt genähte Rampenkante zusammen (81 Kanten hinein, 80 heraus, Volumen
    und Oberfläche auf 10⁻¹⁴ gleich). Gibt zurück, ob beides dasselbe ist, und
    die Zeile dazu.
    """
    body = BODIES[name]()
    stored = step.read((THREADS / f"{name}.step").read_bytes())
    same = (
        body.face_count == stored.face_count
        and abs(body.volume - stored.volume) <= CHECK_RELATIVE * abs(stored.volume)
        and abs(body.area - stored.area) <= CHECK_RELATIVE * abs(stored.area)
    )
    line = (
        f"{name}: Erzeuger {body.face_count} Flächen, Volumen {body.volume:.6f}, "
        f"Oberfläche {body.area:.6f} | Datei {stored.face_count} Flächen, "
        f"Volumen {stored.volume:.6f}, Oberfläche {stored.area:.6f} | "
        f"{'gleich' if same else 'VERSCHIEDEN'}"
    )
    return same, line


def main(arguments: list[str]) -> int:
    """Baut die genannten Körper, ohne Namen alle; mit ``--check`` nur vergleichen."""
    check = "--check" in arguments
    names = [name for name in arguments if name != "--check"]
    unknown = [name for name in names if name not in BODIES]
    if unknown:
        print(f"unbekannt: {', '.join(unknown)} — bekannt sind {', '.join(BODIES)}")
        return 2
    THREADS.mkdir(parents=True, exist_ok=True)
    failed = False
    for name, build in BODIES.items():
        if names and name not in names:
            continue
        if check:
            same, line = compare(name)
            failed = failed or not same
            print(line)
            continue
        body = build()
        payload = step.write(body)
        (THREADS / f"{name}.step").write_bytes(payload)
        print(
            f"{name}: {body.face_count} Flächen, {body.edge_count} Kanten, "
            f"Volumen {body.volume:.6f}, {len(payload)} Byte"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
