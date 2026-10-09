"""Bausteine als OpenSCAD-Quelltext (Bauplan §24.1).

``to_scad()`` bleibt ein *Ausgabeformat*: wer einen OpenSCAD-Arbeitsablauf hat,
kann einen Baustein ohne Solidon mitnehmen. Was es nicht ist, ist eine zweite
Umsetzung — die Geometrie kommt aus derselben Funktion, die die Anwendung
benutzt, und wird als ``polyhedron`` geschrieben.

Darüber klar zu sein zählt. Eine handgeschriebene SCAD-Version jedes Bausteins
wäre eine zweite Quelle der Wahrheit, die abdriftet, und den ersten Unterschied
zwischen beiden fände ein Nutzer, in einem Druck. Also werden die Parameter als
lesbare Variablen in die Datei geschrieben, und der Körper darunter ist genau
das Netz.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.parts.registry import PartSpec
from app.core.types import BaseParams

if TYPE_CHECKING:
    from app.core.knowledge.parts.through import ShownBore

#: In jede Datei geschrieben, damit niemand sie für ein parametrisches
#: Modell hält.
HEADER = """// {title} ({name}, Version {version})
// Erzeugt von Solidon. Die Werte unten sind zum Nachlesen da: das Modell
// darunter ist ein festes Netz, kein parametrischer Nachbau.
"""


def to_scad(spec: PartSpec, params: BaseParams | None = None) -> str:
    """Ein Baustein als OpenSCAD-Modul."""
    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.knowledge.parts.through import shown_bores
    from app.core.units import EPS_GEOM

    values = params or spec.params()
    produced = spec.fn(values)
    mesh = as_mesh_data(produced.mesh)

    lines = [
        HEADER.format(title=spec.title, name=spec.name, version=spec.version),
        "",
    ]
    for entry in values.spec():
        lines.append(f"{entry.name} = {_literal(getattr(values, entry.name))};")
    lines.append("")
    lines.extend(_module(spec.name, mesh))
    for suffix, build, advice in (
        ("host_add", spec.host_add, "Vor dem Bausteinschnitt mit dem Träger vereinigen."),
        ("host_cut", spec.host_cut, "Vor dem Anfügen des Bausteins vom Träger abziehen."),
    ):
        extra = build(values) if build is not None else None
        if extra is not None:
            lines.extend(
                ["", f"// {advice}", *_module(f"{spec.name}_{suffix}", as_mesh_data(extra.mesh))]
            )
    upward = float(mesh.bounds.maximum[2]) > BOOLEAN_OVERLAP + EPS_GEOM
    shown = shown_bores(spec, produced, upward=upward)
    lines.extend(_shown_module(spec.name, shown))
    lines.extend(["", f"{spec.name}();"])
    if shown:
        lines.append(f"{spec.name}_through();")
    return "\n".join(lines)


def _shown_module(name: str, shown: list[ShownBore]) -> list[str]:
    """Die Bohrungen durch den Träger als Zylinder mit lesbarer Länge (RM-632).

    Im Netz des Bausteins liegt eine solche Bohrung ganz in ihm; wie weit sie
    reicht, misst in Solidon erst der Schritt am Träger. Hier steht sie mit
    der Anzeigelänge da, als Variable, die man an den eigenen Träger anpasst.
    """
    from app.core.knowledge.parts.shapes import SEGMENTS
    from app.core.knowledge.parts.through import SHOWN_REACH, turn_onto

    if not shown:
        return []
    lines = [
        "",
        "// Bohrung durch den Träger: In Solidon reicht sie, so weit der Träger Material hat.",
        f"// Hier {SHOWN_REACH:g} Durchmesser lang; through_length an den eigenen Träger anpassen.",
        f"through_length = {shown[0].length:.4f};",
        f"module {name}_through() {{",
    ]
    for entry in shown:
        turn = turn_onto(entry.direction)
        rotate = (
            ""
            if turn is None
            else f"rotate(a = {turn[0]:.4f}, v = [{turn[1][0]:.4f}, {turn[1][1]:.4f}, "
            f"{turn[1][2]:.4f}]) "
        )
        lines.append(
            f"  translate([{entry.start[0]:.4f}, {entry.start[1]:.4f}, {entry.start[2]:.4f}]) "
            f"{rotate}cylinder(d = {entry.diameter:.4f}, h = through_length, $fn = {SEGMENTS});"
        )
    lines.append("}")
    return lines


def _module(name: str, mesh: MeshData) -> list[str]:
    """Ein Netzmodul, gemeinsam für Baustein, Trägeraufbau und vorbereitenden Schnitt."""
    lines = [f"module {name}() {{", "  polyhedron(", "    points = ["]
    for point in mesh.raw.vertices:
        lines.append(f"      [{point[0]:.4f}, {point[1]:.4f}, {point[2]:.4f}],")
    lines.extend(["    ],", "    faces = ["])
    for triangle in mesh.raw.faces:
        lines.append(f"      [{triangle[0]}, {triangle[1]}, {triangle[2]}],")
    lines.extend(["    ],", "    convexity = 8", "  );", "}"])
    return lines


def _literal(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        # Maskiert wie JSON — OpenSCAD-Strings kennen dieselben
        # Fluchtzeichen. Heute führt kein Baustein ein Freitextfeld; der
        # erste, der eines bekommt, bräche hier sonst am ersten
        # Anführungszeichen im Wert.
        return json.dumps(value, ensure_ascii=False)
    return f"{value}"
