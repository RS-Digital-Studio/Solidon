"""Bausteine als OpenSCAD-Quelltext (Bauplan §24.1).

``to_scad()`` bleibt ein *Ausgabeformat*: wer einen OpenSCAD-Arbeitsablauf hat,
kann einen Baustein ohne Formwerk mitnehmen. Was es nicht ist, ist eine zweite
Umsetzung — die Geometrie kommt aus derselben Funktion, die die Anwendung
benutzt, und wird als ``polyhedron`` geschrieben.

Darüber klar zu sein zählt. Eine handgeschriebene SCAD-Fassung jedes Bausteins
wäre eine zweite Quelle der Wahrheit, die abdriftet, und den ersten Unterschied
zwischen beiden fände ein Nutzer, in einem Druck. Also werden die Parameter als
lesbare Variablen in die Datei geschrieben, und der Körper darunter ist genau
das Netz.
"""

from __future__ import annotations

from app.core.geom.mesh import as_mesh_data
from app.core.knowledge.parts.registry import PartSpec
from app.core.types import BaseParams

#: Written into every file, so nobody mistakes it for a parametric model.
HEADER = """// {title} ({name}, Version {version})
// Erzeugt von Formwerk. Die Werte unten sind zum Nachlesen da: das Modell
// darunter ist ein festes Netz, kein parametrischer Nachbau.
"""


def to_scad(spec: PartSpec, params: BaseParams | None = None) -> str:
    """Ein Baustein als OpenSCAD-Modul."""
    values = params or spec.params()
    mesh = as_mesh_data(spec.fn(values).mesh)

    lines = [
        HEADER.format(title=spec.title, name=spec.name, version=spec.version),
        "",
    ]
    for entry in values.spec():
        lines.append(f"{entry.name} = {_literal(getattr(values, entry.name))};")
    lines.append("")
    lines.append(f"module {spec.name}() {{")
    lines.append("  polyhedron(")
    lines.append("    points = [")
    for point in mesh.raw.vertices:
        lines.append(f"      [{point[0]:.4f}, {point[1]:.4f}, {point[2]:.4f}],")
    lines.append("    ],")
    lines.append("    faces = [")
    for triangle in mesh.raw.faces:
        lines.append(f"      [{triangle[0]}, {triangle[1]}, {triangle[2]}],")
    lines.append("    ],")
    lines.append("    convexity = 8")
    lines.append("  );")
    lines.append("}")
    lines.append("")
    lines.append(f"{spec.name}();")
    return "\n".join(lines)


def _literal(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    return f"{value}"
