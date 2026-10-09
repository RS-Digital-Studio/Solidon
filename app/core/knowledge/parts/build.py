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

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from app.core.errors import InternalError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.parts.shapes import Form, ThreadProfile
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
    diameter: float,
    pitch: float,
    length: float,
    *,
    internal: bool = False,
    bottom: float = 0.0,
    profile: ThreadProfile = "flat",
    starts: int = 1,
    left: bool = False,
    taper: float = 0.0,
    reference: float | None = None,
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

    **Der Gang beginnt einen Umlauf unter dem unteren Ende**, wie beim exakten
    Zwilling, und wird erst vom Schnittzylinder auf die Länge gebracht. Bis zum
    22.09.2026 begann er am Netz genau bei ``bottom``: Oben lief er über die
    Länge hinaus und wurde abgeschnitten, unten setzte er erst mit seinem
    Anfang ein. An einem Innengewinde — Mutter, Gewindeloch — stand damit an der
    unteren Stirnfläche ein Umlauf Material im Gang, und eine gedruckte
    Schraube kam nicht hindurch: bei M8 und 0,2 mm Spiel überdeckten sich
    Schraube und Mutter um 2,3 mm³, gleich wie man sie gegeneinander drehte.
    Mit dem Vorlauf ist der Gang an beiden Stirnflächen offen, und die Phase
    bleibt dieselbe: Sie hängt an ``bottom`` modulo Steigung.

    **Gewindeform, Gangzahl, Drehsinn und Kegel** (RM-544): ``profile`` wählt das
    Gangprofil (``shapes.ThreadProfile``), ``starts`` Gänge teilen sich den
    Vorschub ``starts · pitch``, ``left`` baut linksgängig, und ``taper`` ist der
    Zuwachs des Halbmessers je Millimeter Höhe — negativ, wo der Kegel nach oben
    enger wird. ``diameter`` gilt dann auf der Höhe ``reference`` (Vorgabe
    ``bottom``), in derselben Lage wie ``bottom``. Die Phase bleibt an
    ``bottom``: Bei Winkel null beginnt dort ein Gang, wie bisher, auch gespiegelt.
    """
    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.knowledge.parts import shapes

    level = bottom if reference is None else reference
    if shapes.building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.threaded(
            diameter,
            pitch,
            length,
            internal=internal,
            bottom=bottom,
            profile=profile,
            starts=starts,
            left=left,
            taper=taper,
            reference=level,
        )
    if taper and _exact_available():
        # **Ein Kegel entsteht genäht und wird vernetzt** (RM-544). Am Netz gebaut
        # — Kegelkern und kegelig gelegter Gang vereinigt — ließ die Boolesche
        # Kette an R 1/4 über 200 mm eine Falte von drei Dreiecken stehen, und ein
        # nachträglich verzogener Zylinder faltete seine Stirnflächen
        # (Bereichsnachweis). ``helical_thread`` legt den Kegel in die Flächen
        # selbst; vernetzt ist der Körper dicht und ohne Selbstdurchdringung.
        with shapes.building("brep"):
            solid = threaded(
                diameter,
                pitch,
                length,
                internal=internal,
                bottom=bottom,
                profile=profile,
                starts=starts,
                left=left,
                taper=taper,
                reference=level,
            )
        return as_mesh_data(solid)
    depth = shapes.ridge_depth(pitch, profile)
    lead = starts * pitch
    # Ohne exakten Kern ist ein Kegel ein verzogener Zylinder: Gebaut wird das
    # zylindrische Gewinde mit dem Maß der Bezugsebene, danach rückt jede Ecke
    # radial um ``taper`` je Millimeter Abstand von ihr (:func:`_tapered`). Höhe
    # und Winkel bleiben, die Phase also auch. Sehnen und Kernecken richten sich
    # nach der weitesten Stelle, denn dort wächst die Sehnentiefe mit.
    spread = 2.0 * abs(taper) * max(abs(bottom - level), abs(bottom + length - level))
    widest = diameter + spread
    core_diameter = diameter if internal else diameter - 2.0 * depth
    # Kern und Gang auf denselben Winkeln, so fein, wie der Kamm es verlangt.
    segments = shapes.turn_segments(widest / 2.0 + depth if internal else widest / 2.0)
    core = shapes.cylinder(
        core_diameter + 2.0 * BOOLEAN_OVERLAP,
        length,
        segments=_core_segments((core_diameter + spread) / 2.0, segments),
    )
    # **Der Gang läuft über ganze Umläufe** und wird erst vom Schnittzylinder
    # gekürzt — wie beim Drehdeckel (``lid._thread_tool_height``) und beim
    # exakten Zwilling. ``thread_body`` verteilt ``round(Umläufe) · segments``
    # Schritte über seine Höhe; bei einer krummen Umlaufzahl lagen die
    # Stationen nicht mehr auf den Kernecken, und je Umlauf blieben weniger
    # Sehnen, als ``turn_segments`` verlangt (Ø 46 auf 2 mm: 33 statt 48,
    # Review RM-532 R1).
    turns = math.ceil((length + lead) / lead - 1e-9)
    ridge = shapes.moved(
        shapes.thread_body(
            diameter,
            pitch,
            turns * lead,
            segments=segments,
            internal=internal,
            profile=profile,
            starts=starts,
            left=left,
        ),
        (0.0, 0.0, -lead),
    )
    body = union(core, ridge)
    limit = shapes.cylinder(diameter * 2.0 + 4.0, length)
    body = intersect(body, limit)
    if taper:
        body = _tapered(shapes.mesh_only(body), taper, level - bottom)
    return shapes.moved(body, (0.0, 0.0, bottom)) if bottom else body


def _exact_available() -> bool:
    """Ob der exakte Kern da ist: im Paket immer, in einem Quellklon ohne Extra nicht."""
    from app.core.brep import kernel

    return bool(kernel.available())


def _tapered(body: MeshData, taper: float, reference: float) -> MeshData:
    """Ein zylindrisches Netz radial zum Kegel verzogen: ``r + taper · (z - reference)``.

    Jede Ecke behält Höhe und Winkel. Die Verschiebung ist an jeder Höhe für alle
    Ecken gleich groß und ändert sich über die Länge um ein Zweiunddreißigstel je
    Millimeter — weit zu wenig, als dass eine Fläche über eine andere klappte; die
    Überdeckung zwischen Kern und Gang bleibt dieselbe.
    """
    import numpy as np

    raw = body.raw.copy()
    points = np.asarray(raw.vertices, dtype=np.float64)
    radius = np.hypot(points[:, 0], points[:, 1])
    grown = radius + taper * (points[:, 2] - reference)
    scale = np.divide(grown, radius, out=np.ones_like(radius), where=radius > 0.0)
    points[:, 0] *= scale
    points[:, 1] *= scale
    raw.vertices = points
    return body.replacing(raw)


def _core_segments(root: float, segments: int) -> int:
    """Ecken des Netzkerns: so viele, dass er den Gang auch in der Sehnenmitte überdeckt.

    Der Kern reicht ``BOOLEAN_OVERLAP`` über den Fuß des Gangs hinaus, damit
    beide sich nicht nur auf derselben Zylinderfläche berühren. Am Netz liegt
    seine Sehne aber um ``r · (1 - cos(π / n))`` innen, und wo das mehr ist als
    die Überdeckung, endet der Kern in der Sehnenmitte unter dem Fuß des Gangs:
    Dort blieb ein Splitter stehen — am Bolzen eine Kerbe, in der Mutter ein
    Grat im Gang. Gemessen am 06.10.2026 an gedruckter Schraube und Mutter: ab
    M12 mit 48 Sehnen (0,011 mm Sehnentiefe) überdeckten sich beide, bei M20
    um 0,27 mm³, bei M42 um 10 mm³, gleich an welcher Stelle der Schraube
    (Review RM-532, R1).

    **Feiner statt weiter**: Ein Vielfaches der Gangsehnen, damit jede Station
    des Gangs auf einer Kernecke liegt, und der Eckenradius bleibt der Fuß plus
    Überdeckung — der Gewindegrund behält sein Maß. Bis M8 bleiben es die
    Sehnen des Gangs; die Sehnenzahl dieser Tabellengewinde ändert sich nicht.
    """
    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.units import exact_cos

    reach = root + BOOLEAN_OVERLAP
    count = segments
    while reach * exact_cos(math.pi / count) < root:
        count += segments
    return count


def compound(*parts: Form) -> Form:
    """Mehrere Körper in einem Objekt, ohne sie zu verschweißen — je Kern.

    Ein Baustein, der erklärt aus mehreren Körpern besteht (``PartSpec.bodies``,
    das Bolzenscharnier), sagt es hier statt über eine Vereinigung, die nichts
    vereinigt: Am Netz ist das dieselbe Boolesche Vereinigung — Körper, die
    sich nicht berühren, bleiben darin getrennte Komponenten —, exakt ein
    Verbund (``exact.compound``), der die Teile als Körper nebeneinander trägt.
    """
    bodies = [part for part in parts if part is not None]
    if len(bodies) == 1:
        return bodies[0]
    plain = _meshes(bodies)
    if plain is None:
        from app.core.knowledge.parts import exact as twins

        return twins.compound(*_solids(bodies))
    return boolean("union", plain, quality="fine").mesh


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
    left: bool = False,
    starts: int = 1,
    taper: float = 0.0,
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

    **Drehsinn, Gangzahl und Kegel** (RM-544) im Vertrag des exakten Lesers
    (``brep.thread.thread_features``): ``handedness``, ``starts`` und ``lead``
    nur, wo es mehr als einen Gang gibt, ``taper`` als halber Kegelwinkel in Grad,
    positiv, wo der Durchmesser entlang ``axis`` wächst — nur am kegeligen
    Gewinde; ``diameter`` gilt dann in der Mitte (``centre``). ``taper`` hier ist
    der Zuwachs des Halbmessers je Millimeter, wie ``build.threaded`` ihn nimmt.
    """
    params: dict[str, Any] = {
        "diameter": diameter,
        "pitch": pitch,
        # thread_body lässt Winkel und Höhe gemeinsam wachsen; Innenwerkzeug,
        # Schraube und Mutter behalten den Drehsinn ihres Bausteins.
        "handedness": "left" if left else "right",
        "centre": centre,
        "axis": axis,
        "internal": internal,
        "length": length,
    }
    if starts > 1:
        params["starts"] = starts
        params["lead"] = starts * pitch
    if taper:
        params["taper"] = math.degrees(math.atan(taper))
    return identifier, Feature(
        id=identifier,
        kind="thread",
        provenance="generated",
        params=params,
        # Auch die Händigkeit ist ein Parameter des Bausteins, keine Messung —
        # ohne Quelle las der Steckbrief „rechtsgängig" wie ein gemessenes Maß.
        measure_sources=dict.fromkeys(
            (
                "diameter",
                "pitch",
                "handedness",
                "centre",
                "axis",
                "length",
                *(name for name in ("starts", "lead", "taper") if name in params),
            ),
            "parameter",
        ),
    )


def result(mesh: Form, *features: tuple[FeatureId, Feature]) -> PartResult:
    """Die Antwort eines Bausteins: die Geometrie und alles, wie er sich
    nennen lässt.
    """
    return PartResult(mesh=mesh, features=dict(features))
