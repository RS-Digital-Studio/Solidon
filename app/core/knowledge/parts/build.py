"""Gemeinsamer Boden für jeden Baustein (Bauplan §24.1).

Drei Dinge, die jeder Baustein braucht und keines davon selbst erfinden soll:
einen Weg, Formen zu vereinen, einen Weg, ein Provenienz-Merkmal zu benennen,
und die Regel, dass eine abgezogene Form ein Haar über die Fläche hinausreicht,
die sie schneidet (§39).

Die Merkmale sind der Grund, warum es Bausteine überhaupt gibt. Eine Bohrung,
die aus der Bibliothek kommt, heißt von Anfang an ``bore_1`` und muss danach
nicht neu erkannt werden (§21.1) — Passung, Steckbrief und Agent sprechen alle
unter diesem Namen von ihr.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from app.core.errors import InternalError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.parts.shapes import Form
from app.core.types import BRepBody, Feature, FeatureId, MeasureSource, PartResult, Vec3

if TYPE_CHECKING:
    from app.core.brep.kernel import Solid


def _meshes(forms: list[Form]) -> list[MeshData] | None:
    """Alle als Netz — oder ``None``, sobald eine Form ein exakter Körper ist."""
    meshes = [form for form in forms if isinstance(form, MeshData)]
    return meshes if len(meshes) == len(forms) else None


def _solids(forms: list[Form]) -> list[Solid]:
    """Alle als exakter Körper — ein Netz darunter ist ein Kernwechsel mitten im Baustein.

    Der Kern wird einmal je Bau gewählt (``shapes.building``); eine Beschreibung,
    die beides mischt, hat ein Netz an einer Stelle erzeugt, die ``mesh_only``
    nicht kennt. Das ist ein Programmfehler, kein Bedienfehler.
    """
    solids = [form for form in forms if isinstance(form, BRepBody)]
    if len(solids) != len(forms):
        raise InternalError(detail="a part mixed mesh and exact forms in one build")
    return solids


def union(*meshes: Form) -> Form:
    """Vereint Formen. Ein Körper hinein, ein Körper heraus — je Kern (P2.7)."""
    bodies = [mesh for mesh in meshes if mesh is not None]
    if len(bodies) == 1:
        return bodies[0]
    plain = _meshes(bodies)
    if plain is None:
        from app.core.knowledge.parts import exact as twins

        return twins.union(*_solids(bodies))
    return boolean("union", plain, quality="fine").mesh


def subtract(base: Form, *cutters: Form) -> Form:
    plain = _meshes([base, *cutters])
    if plain is None:
        from app.core.knowledge.parts import exact as twins

        return twins.subtract(*_solids([base, *cutters]))
    return boolean("difference", plain, quality="fine").mesh


def intersect(first: Form, second: Form) -> Form:
    """Der gemeinsame Teil zweier Formen — je Kern; das Netz kannte ihn nur örtlich."""
    plain = _meshes([first, second])
    if plain is None:
        from app.core.knowledge.parts import exact as twins

        return twins.intersect(*_solids([first, second]))
    return boolean("intersection", plain, quality="fine").mesh


def threaded(
    diameter: float, pitch: float, length: float, *, internal: bool = False, bottom: float = 0.0
) -> Form:
    """Kern und Gang eines Bausteingewindes, auf Länge geschnitten — je Kern (P2.7).

    Am Netz: der Kern ein Hundertstel über den Fußradius hinaus, damit
    ``manifold3d`` die Naht zum Gang findet, dazu der Gang aus
    ``shapes.thread_body``, vereinigt und mit einem Zylinder auf die Länge
    beschnitten, weil die Helix ein Stück über sie hinausläuft. Exakt: ein
    genähter Körper ohne Naht (``exact.threaded``). Außen liegt der Fuß
    ``RIDGE_SHARE`` Steigungen unter dem Durchmesser, innen ist der
    Durchmesser die Bohrung und der Gang wächst nach außen. ``bottom`` ist die
    Höhe des unteren Endes — der exakte Kern baut gleich dort, statt einen
    fertigen Körper zu bewegen.
    """
    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.knowledge.parts import shapes

    if shapes.building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.threaded(diameter, pitch, length, internal=internal, bottom=bottom)
    depth = pitch * shapes.RIDGE_SHARE
    core_diameter = diameter if internal else diameter - 2.0 * depth
    core = shapes.cylinder(core_diameter + 2.0 * BOOLEAN_OVERLAP, length)
    ridge = shapes.thread_body(diameter, pitch, length, internal=internal)
    body = union(core, ridge)
    limit = shapes.cylinder(diameter * 2.0 + 4.0, length)
    body = intersect(body, limit)
    return shapes.moved(body, (0.0, 0.0, bottom)) if bottom else body


def compound(*parts: Form) -> Form:
    """Mehrere Körper in einem Objekt, ohne sie zu verschweißen — nur am exakten Kern.

    Das Netz hat dafür ``ops._concatenated_with_slots``; ein Baustein ruft
    diese Funktion nur unter ``shapes.building_exact()``.
    """
    from app.core.knowledge.parts import exact as twins

    return twins.compound(*_solids(list(parts)))


def form_of(produced: PartResult) -> Form:
    """Die Form eines gebauten Teils zurück in die Beschreibung — Netz oder exakter Körper.

    Ein Baustein, der einen anderen als Teil verwendet (die Schraube ihren
    Bolzen, die Mutter ihr Werkzeug), bekommt ihn im Kern, in dem gerade
    gebaut wird — ohne ihn zu vernetzen.
    """
    mesh = produced.mesh
    if isinstance(mesh, MeshData):
        return mesh
    if isinstance(mesh, BRepBody):
        return cast("Solid", mesh)
    return as_mesh_data(mesh)


def bore(
    identifier: FeatureId,
    diameter: float,
    centre: Vec3,
    *,
    depth: float = 0.0,
    axis: Vec3 = (0.0, 0.0, 1.0),
    through: bool = False,
) -> tuple[FeatureId, Feature]:
    """Eine benannte Bohrung, so wie der Baustein sie verspricht (§24.1)."""
    return identifier, Feature(
        id=identifier,
        kind="hole",
        provenance="generated",
        params={
            "diameter": diameter,
            "centre": centre,
            "axis": axis,
            "depth": depth,
            "through": through,
        },
        measure_sources=dict.fromkeys(("diameter", "centre", "axis", "depth"), "parameter"),
    )


def pin(
    identifier: FeatureId,
    diameter: float,
    centre: Vec3,
    *,
    length: float = 0.0,
    axis: Vec3 = (0.0, 0.0, 1.0),
) -> tuple[FeatureId, Feature]:
    """Das Gegenstück einer Bohrung — das, womit eine Passung sie paart (§14)."""
    return identifier, Feature(
        id=identifier,
        kind="pin",
        provenance="generated",
        params={
            "diameter": diameter,
            "centre": centre,
            "axis": axis,
            "depth": length,
        },
        measure_sources=dict.fromkeys(("diameter", "centre", "axis", "depth"), "parameter"),
    )


def face(
    identifier: FeatureId,
    area: float,
    centre: Vec3,
    normal: Vec3 = (0.0, 0.0, 1.0),
    *,
    measure_sources: Mapping[str, MeasureSource] | None = None,
) -> tuple[FeatureId, Feature]:
    return identifier, Feature(
        id=identifier,
        kind="face",
        provenance="generated",
        params={"area": area, "centre": centre, "normal": normal},
        measure_sources={
            **dict.fromkeys(("area", "centre", "normal"), "parameter"),
            **(measure_sources or {}),
        },
    )


def thread(
    identifier: FeatureId,
    diameter: float,
    pitch: float,
    centre: Vec3,
    *,
    axis: Vec3 = (0.0, 0.0, 1.0),
    internal: bool = False,
    length: float = 0.0,
) -> tuple[FeatureId, Feature]:
    """Ein benanntes Gewinde, wie ein Baustein es beim Bauen erklärt (§24.1).

    ``length`` ist die **bewendelte Strecke**, und ``centre`` liegt in ihrer
    Mitte — beides zusammen sagt, wo das Gewinde anfängt und aufhört.

    **Wozu die Länge da ist.** Die Erkennung sieht eine Wendel nicht als
    Gewinde, sondern als das, was sie geometrisch ist: eine Folge von
    Zylinder-, Kegel- und Kugelflecken. An einem gedruckten M6 werden daraus
    Phantommerkmale im Objektbaum — ein „Zapfen Ø 5,79" an einem Bolzen, den
    niemand gesetzt hat (gemeldet von einem Kunden, gemessen von 3d-druck-4d
    über sechs Größen: kein Fall ohne Phantom). Was innerhalb der Hülle des
    benannten Gewindes liegt, ist ein Artefakt der Wendel und gehört nicht in
    die Szene — Provenienz schlägt Erkennung (§21.2).

    Radial genügt der Durchmesser dafür nicht: Ohne die Strecke längs der
    Achse verschluckt dieselbe Unterdrückung eine echte Bohrung, die koaxial
    unter einem Gewindebolzen sitzt. Genau deshalb steht die Länge hier und
    nicht als Näherung bei dem, der sie braucht.

    Die Vorgabe ist null, damit ein Baustein, der sie nicht kennt, sich nicht
    ändert: Wer keine Strecke nennt, bekommt keine Unterdrückung, und ein
    altes Projekt behält seine Funde, statt dass jemand radial rät.
    """
    return identifier, Feature(
        id=identifier,
        kind="thread",
        provenance="generated",
        params={
            "diameter": diameter,
            "pitch": pitch,
            # thread_body lässt Winkel und Höhe gemeinsam wachsen; auch
            # Innenwerkzeuge, Schraube und Mutter behalten diesen rechten Gang.
            "handedness": "right",
            "centre": centre,
            "axis": axis,
            "internal": internal,
            "length": length,
        },
        measure_sources=dict.fromkeys(
            ("diameter", "pitch", "centre", "axis", "length"), "parameter"
        ),
    )


def result(mesh: Form, *features: tuple[FeatureId, Feature]) -> PartResult:
    """Die Antwort eines Bausteins: die Geometrie und alles, wie er sich
    nennen lässt.
    """
    return PartResult(mesh=mesh, features=dict(features))
