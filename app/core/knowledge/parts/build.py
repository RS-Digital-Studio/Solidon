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

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.types import Feature, FeatureId, PartResult, Vec3


def union(*meshes: MeshData) -> MeshData:
    """Vereint Formen. Ein Körper hinein, ein Körper heraus."""
    bodies = [mesh for mesh in meshes if mesh is not None]
    if len(bodies) == 1:
        return bodies[0]
    return boolean("union", bodies, quality="fine").mesh


def subtract(base: MeshData, *cutters: MeshData) -> MeshData:
    return boolean("difference", [base, *cutters], quality="fine").mesh


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
            "diameter": round(diameter, 4),
            "centre": centre,
            "axis": axis,
            "depth": round(depth, 4),
            "through": through,
        },
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
            "diameter": round(diameter, 4),
            "centre": centre,
            "axis": axis,
            "depth": round(length, 4),
        },
    )


def face(
    identifier: FeatureId,
    area: float,
    centre: Vec3,
    normal: Vec3 = (0.0, 0.0, 1.0),
) -> tuple[FeatureId, Feature]:
    return identifier, Feature(
        id=identifier,
        kind="face",
        provenance="generated",
        params={"area": round(area, 4), "centre": centre, "normal": normal},
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
            "diameter": round(diameter, 4),
            "pitch": round(pitch, 4),
            "centre": centre,
            "axis": axis,
            "internal": internal,
            "length": round(length, 4),
        },
    )


def result(mesh: MeshData, *features: tuple[FeatureId, Feature]) -> PartResult:
    """Die Antwort eines Bausteins: die Geometrie und alles, wie er sich
    nennen lässt.
    """
    return PartResult(mesh=mesh, features=dict(features))
