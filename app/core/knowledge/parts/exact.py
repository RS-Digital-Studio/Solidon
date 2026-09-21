"""Die exakten Zwillinge der Grundformen — dieselbe Beschreibung, der zweite Auswerter (P2.7).

Ein Baustein beschreibt seine Form als Folge von Aufrufen an ``shapes`` und
``build``: ein Zylinder hier, ein Sechskant dort, vereinigt, abgezogen,
verschoben. Bis zum 20.09.2026 rechnete jeder dieser Aufrufe ein Netz, und ein
Baustein an einem exakten Träger vernetzte den Träger mit. Seither wählt der
Aufrufer den Kern (``shapes.building``), und dieselbe Beschreibung ergibt hier
einen ``Solid``: derselbe Rahmen (auf Z = 0 stehend, in X und Y zentriert),
dieselben Maße, dieselben Ecken — nur der Kreis ist ein Kreis und kein 48-Eck,
und der Gewindegang ist ein Sweep statt einer von Hand vernähten Ringfolge.

**Eine Formbeschreibung, zwei Auswerter** — keine zweite Funktion je Baustein
(Konzept §13.8, `zwillinge.md`): Was hier steht, ist je Grundform ein Zwilling,
und der Zweig endet ohne ihn, denn ein Netz hat keine Kanten, die eine Fase
nehmen könnten, und ein exakter Körper keine Dreiecke, die ``manifold3d``
vereinigen könnte. Die fachlichen Entscheidungen — Gangprofil, Rahmen,
Überlappung — stehen einmal in ``shapes`` und werden von hier gelesen.

Alles hier holt den exakten Kern **träge**: ``knowledge`` importiert ``brep``
nicht eifrig (``tests/test_core_package_direction.py``), und ohne OpenCASCADE
gibt es keinen exakten Träger, an dem ein Baustein diesen Weg ginge.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Final

from app.core.errors import CANCEL, CORRECT_INPUT, GeometryError
from app.core.types import Finding, Point2, Vec3
from app.i18n import _

if TYPE_CHECKING:
    from app.core.brep.kernel import Solid
    from app.core.sketch.profile import Profile

#: Die Stufenleiter der Vereinigung, in Millimetern: Ohne Toleranz lässt
#: OpenCASCADE zwei Teile, die sich nur um Rundungsstellen durchdringen, als
#: zwei Körper stehen; zu fein lässt die Naht offen, zu grob bringt die
#: Boolesche Operation zum Aufgeben, deshalb mehrere Werte. Dieselben drei
#: Zehnerpotenzen wie ``profiles.ROD_FUZZ_RATIOS`` — dort als Anteil der
#: Steigung, weil ein Gewinde ein Maß hat, an dem sich die Naht orientiert;
#: ein Baustein hat keines, also stehen die Werte hier absolut. Bei Steigungen
#: um einen Millimeter fallen beide zusammen; ``tests/test_exact_parts.py``
#: hält die Zahlen gleich, damit sie nicht still auseinanderlaufen.
UNION_FUZZ_MM: Final = (1e-4, 1e-3, 1e-2)


def _edit() -> Any:
    from app.core.brep import edit

    return edit


def _profiles() -> Any:
    from app.core.brep import profiles

    return profiles


def _polygon(points: Sequence[Point2]) -> Profile:
    """Ein geschlossener Umriss aus Strecken — derselbe, den das Netz extrudiert."""
    from app.core.sketch.profile import Profile, ProfileSegment

    corners = [(float(x), float(y)) for x, y in points]
    segments = tuple(
        ProfileSegment("line", corners[index - 1], corners[index]) for index in range(len(corners))
    )
    return Profile(segments=segments)


# --- Grundformen ---------------------------------------------------------------------


def cylinder(diameter: float, height: float) -> Solid:
    """Auf Z = 0 stehend, nach oben wachsend — wie ``shapes.cylinder``."""
    return _edit().cylinder(diameter, height)  # type: ignore[no-any-return]


def box(width: float, depth: float, height: float) -> Solid:
    """In X und Y zentriert, auf Z = 0 stehend — wie ``shapes.box``."""
    return _edit().box(width, depth, height)  # type: ignore[no-any-return]


def hexagon(width: float, height: float) -> Solid:
    """Sechskantprisma über die Schlüsselweite, dieselben Ecken wie am Netz."""
    radius = width / math.sqrt(3.0)
    corners = [
        (radius * math.cos(angle), radius * math.sin(angle))
        for angle in (math.pi / 6.0 + step * math.pi / 3.0 for step in range(6))
    ]
    return _profiles().extrude(_polygon(corners), height)  # type: ignore[no-any-return]


def dovetail(width: float, height: float, *, taper: float = 0.55) -> Solid:
    """Das Schwalbenschwanz-Prisma aus ``shapes.dovetail``, exakt."""
    broad = width / 2.0
    narrow = broad * taper
    depth = width / 2.0
    corners = [(-narrow, -depth), (narrow, -depth), (broad, depth), (-broad, depth)]
    return _profiles().extrude(_polygon(corners), height)  # type: ignore[no-any-return]


def cone(bottom: float, top: float, height: float) -> Solid:
    """Ein Kegelstumpf auf Z = 0 — der Grundkörper des Kerns, kein Drehkörper."""
    from app.core.brep.kernel import Solid, require

    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone

    return Solid(BRepPrimAPI_MakeCone(bottom / 2.0, top / 2.0, height).Shape())


def _slot_profile(width: float, length: float) -> Profile:
    """Langloch-Umriss: zwei Strecken, zwei **echte** Halbkreisbögen, Länge in X."""
    from app.core.sketch.profile import Profile, ProfileSegment

    radius = width / 2.0
    offset = (length - width) / 2.0
    return Profile(
        segments=(
            ProfileSegment("line", (-offset, -radius), (offset, -radius)),
            ProfileSegment("arc", (offset, -radius), (offset, radius), via=(offset + radius, 0.0)),
            ProfileSegment("line", (offset, radius), (-offset, radius)),
            ProfileSegment(
                "arc", (-offset, radius), (-offset, -radius), via=(-offset - radius, 0.0)
            ),
        )
    )


def slot(width: float, length: float, height: float) -> Solid:
    """Ein Langloch: zwei Halbkreise mit einem Rechteck dazwischen — exakte Bögen."""
    if length <= width:
        return cylinder(width, height)
    return _profiles().extrude(_slot_profile(width, length), height)  # type: ignore[no-any-return]


def tapered_bar(width: float, narrow: float, length: float, height: float, taper: float) -> Solid:
    """Der Nutenstein aus ``shapes.tapered_bar`` — derselbe Umriss, dieselben Grenzfälle."""
    if taper <= 0.0 or narrow >= width:
        return box(width, length, height)
    half_wide, half_narrow = width / 2.0, narrow / 2.0
    end, shoulder = length / 2.0, length / 2.0 - taper
    if shoulder <= 0.0:
        outline: list[Point2] = [
            (-half_narrow, -end),
            (half_narrow, -end),
            (half_wide, 0.0),
            (half_narrow, end),
            (-half_narrow, end),
            (-half_wide, 0.0),
        ]
    else:
        outline = [
            (-half_narrow, -end),
            (half_narrow, -end),
            (half_wide, -shoulder),
            (half_wide, shoulder),
            (half_narrow, end),
            (-half_narrow, end),
            (-half_wide, shoulder),
            (-half_wide, -shoulder),
        ]
    return _profiles().extrude(_polygon(outline), height)  # type: ignore[no-any-return]


def prism_across(outline: Sequence[Point2], width: float) -> Solid:
    """Der Seitenriss aus ``shapes.prism_across``: in YZ gezeichnet, quer über X aufgezogen."""
    # In YZ gezeichnet (x → Y, y → Z) und entlang +X aufgezogen, dann zentriert —
    # dieselbe Lage, die das Netz über seine Umlegematrix erreicht.
    body = _profiles().extrude(_polygon(outline), width, "plane:yz")
    return _edit().moved(body, (-width / 2.0, 0.0, 0.0))  # type: ignore[no-any-return]


def revolved(outline: Sequence[Point2]) -> Solid:
    """Der Drehkörper aus ``shapes.revolved`` — derselbe Umriss, exakt um Z gedreht."""
    return _profiles().revolve(_polygon(outline), 360.0)  # type: ignore[no-any-return]


def rounded_dovetail(diameter: float, length: float) -> Solid:
    """Der gerundete Schwalbenschwanz aus ``shapes.rounded_dovetail`` mit echtem Bogen."""
    from app.core.knowledge.parts.shapes import DOVETAIL_ARC, DOVETAIL_START
    from app.core.sketch.profile import Profile, ProfileSegment

    radius = diameter / 2.0

    def on_circle(angle: float) -> Point2:
        return (radius * math.cos(angle), radius * math.sin(angle))

    start = on_circle(DOVETAIL_START)
    end = on_circle(DOVETAIL_START + DOVETAIL_ARC)
    via = on_circle(DOVETAIL_START + DOVETAIL_ARC / 2.0)
    profile = Profile(
        segments=(
            ProfileSegment("arc", start, end, via=via),
            ProfileSegment("line", end, start),
        )
    )
    return _profiles().extrude(profile, length)  # type: ignore[no-any-return]


def threaded(
    diameter: float, pitch: float, length: float, *, internal: bool = False, bottom: float = 0.0
) -> Solid:
    """Kern und Gang des Bausteingewindes, auf Länge geschnitten — als genähter Körper.

    Dasselbe Gangprofil wie der Netzweg (``shapes.ridge_profile``), aber nicht
    als Sweep, der mit dem Kern vereinigt würde: ``profiles.helical_thread``
    näht Kern und Gang aus Flächen zusammen, die sich ihre Helixkanten teilen.
    Das Bausteingewinde behält damit sein Maß (``profiles.threaded_rod`` trägt
    ein anderes Profil und bleibt der Erzeuger *Gewindebolzen*, Bericht P2.7,
    Abschnitt 5.1). Ein Umlauf Vorlauf unter dem Fuß und einer über der Länge
    halten die Rampen der Enden aus dem Schnitt heraus.

    ``bottom`` ist die Höhe des unteren Endes: Der Körper entsteht gleich dort,
    denn jede Bewegung eines fertigen Körpers kostet den exakten Kern zwei
    Volumenintegrale über BSpline-Flächen (``edit.transformed``), an einem
    Gewinde fünf Sekunden — der Schnittzylinder zieht stattdessen mit.

    **Ein Unterschied zum Netz, benannt:** Dort ragt der Kern um
    ``BOOLEAN_OVERLAP`` über den Fußradius hinaus, damit ``manifold3d`` die
    Naht zum Gang findet. Hier gibt es keine Naht, und der Fuß liegt genau auf
    dem Fußradius.
    """
    from app.core.brep import profiles
    from app.core.knowledge.parts.shapes import ridge_profile

    ridge = ridge_profile(diameter, pitch, internal=internal)
    crest_radius = max(radial for radial, _axial in ridge)
    turns = math.ceil(length / pitch) + 2
    whole = profiles.helical_thread(ridge[0][0], pitch, turns, ridge, start=bottom - pitch)
    limit = cylinder(2.0 * crest_radius + 2.0, length)
    if bottom:
        limit = moved(limit, (0.0, 0.0, bottom))
    return intersect(whole, limit)


# --- Bewegen -------------------------------------------------------------------------


def moved(solid: Solid, offset: Vec3) -> Solid:
    return _edit().moved(solid, offset)  # type: ignore[no-any-return]


def turned(solid: Solid, degrees: float, axis: Vec3 = (0.0, 0.0, 1.0)) -> Solid:
    """Drehung um eine Achse durch den Ursprung — dieselbe Matrix wie ``shapes.turned``."""
    from app.core.geom.ops import as_transform
    from app.core.geom.transform import rotation_about

    matrix = as_transform(rotation_about(axis, (0.0, 0.0, 0.0), degrees))
    return _edit().transformed(solid, matrix)  # type: ignore[no-any-return]


# --- Boolesche Operationen -------------------------------------------------------------


def _fused(joined: Solid) -> bool:
    """Ob die Vereinigung aus allen Teilen einen geschlossenen Körper gemacht hat.

    Gefragt wird die Topologie, nicht das Volumen: Körperzahl und
    Geschlossenheit antworten in Mikrosekunden, ein konvergiertes
    Volumenintegral über BSpline-Flächen in Sekunden — und den stillen
    Verlust eines Gangs im Kern (B1) fände auch das Volumen nicht, denn der
    Kern allein ist größer als jedes Teil. Dafür entstehen Kern und Gang in
    :func:`threaded` ohne Vereinigung.
    """
    return joined.solid_count == 1 and joined.is_closed


def _fuzzy_union(left: Solid, right: Solid) -> tuple[Solid, float] | None:
    """Zwei Körper mit der Stufenleiter vereinigen — jede Stufe auf privaten Kopien.

    Dieselben Eingaben mehrfach durch Fuzzy-Booleans zu schicken riss den
    Prozess (P2.7, Befund B2a: Exit 139, dreimal von dreimal); Kopien je Stufe
    nicht. Zurück kommt der Körper mit der Stufe, die ihn gebraucht hat.
    """
    from app.core.brep.kernel import Solid, boolean_builder, copy_shape

    for tolerance in UNION_FUZZ_MM:
        one, _faces, _edges = copy_shape(left.shape)
        other, _faces, _edges = copy_shape(right.shape)
        operation = boolean_builder("union", one, other, tolerance=tolerance)
        operation.Build()
        if not operation.IsDone():
            continue
        candidate = Solid(operation.Shape())
        if _fused(candidate):
            return candidate, tolerance
    return None


def union(*parts: Solid) -> Solid:
    """Vereint Formen — und sieht nach, ob daraus ein Körper geworden ist.

    Erst die exakte Vereinigung aller Teile; bleiben Stücke stehen, folgt
    paarweise die Stufenleiter, und die gebrauchte Stufe geht als Befund an
    den Bau (``shapes.note``), nicht ins Protokoll. Was auch dann nicht
    verschmilzt, ist eine Absage mit Vorschlag: Ein Baustein ist ein Körper,
    und ein Baustein aus mehreren Körpern sagt das über ``compound``, nicht
    über eine Vereinigung, die nichts vereinigt hat.
    """
    from app.core.knowledge.parts.shapes import note

    bodies = [part for part in parts if part is not None]
    if len(bodies) == 1:
        return bodies[0]
    edit = _edit()
    joined = edit.boolean("union", bodies)
    if _fused(joined):
        return joined  # type: ignore[no-any-return]
    result = bodies[0]
    for other in bodies[1:]:
        plain = edit.boolean("union", [result, other])
        if _fused(plain):
            result = plain
            continue
        mended = _fuzzy_union(result, other)
        if mended is None:
            raise GeometryError(
                detail=(
                    _(
                        "Zwei Teile dieses Bausteins ließen sich nicht zu einem Körper "
                        "vereinigen — das Ergebnis wäre nicht geschlossen."
                    )
                    if not plain.is_closed
                    else _(
                        "Zwei Teile dieses Bausteins blieben getrennte Körper, statt zu "
                        "einem zu verschmelzen."
                    )
                ),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        result, tolerance = mended
        note(
            Finding(
                code="parts.fuzzy_union",
                severity="info",
                message=_(
                    "Zwei Teile dieses Bausteins ließen sich erst mit einer Nahttoleranz "
                    "zu einem Körper verbinden."
                ),
                values={"tolerance_mm": str(tolerance)},
            )
        )
    return result


def subtract(base: Solid, *cutters: Solid) -> Solid:
    return _edit().boolean("difference", [base, *cutters])  # type: ignore[no-any-return]


def intersect(first: Solid, second: Solid) -> Solid:
    return _edit().boolean("intersection", [first, second])  # type: ignore[no-any-return]


def compound(*parts: Solid) -> Solid:
    """Mehrere Körper in einem Szenenobjekt, ohne sie zu verschweißen (P2.7, B9).

    Schraube und Mutter liegen im selben Projekt und dürfen nicht zu einem
    unlösbaren Körper werden; ein Senkkopf und sein Gewinde berühren sich nur
    tangential, und die Fuzzy-Vereinigung, die daraus einen Körper machte,
    kam aus STEP ungültig zurück (B2). Ein Verbund trägt beide, gültig und
    STEP-fähig — **und er trägt, was die Teile tragen:** die Filamentzuweisung
    je Fläche, hintereinander in der Reihenfolge der Teile und mit Slot null
    aufgefüllt, wo ein Teil keine hat (so wie ``ops._concatenated_with_slots``
    am Netz), und die feinste Vernetzungsfeinheit der Teile. Ohne beides
    verlöre ein zweifarbiger Träger seine Farben in dem Moment, in dem eine
    Schraube dazukommt (§20).
    """
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    from app.core.brep.kernel import Solid

    builder = BRep_Builder()
    assembled = TopoDS_Compound()
    builder.MakeCompound(assembled)
    for part in parts:
        builder.Add(assembled, part.shape)
    slots: tuple[int, ...] = ()
    if any(part.face_slots for part in parts):
        slots = tuple(
            slot for part in parts for slot in (part.face_slots or (0,) * part.face_count)
        )
    return Solid(assembled, deflection=min(part.deflection for part in parts), face_slots=slots)
