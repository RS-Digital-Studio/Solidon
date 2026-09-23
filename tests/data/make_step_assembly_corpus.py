"""Baut die STEP-Baugruppen des Korpus (P7.4) — über XCAF geschrieben, aus Konstruktionsmaßen.

Die Sollwerte der Tests kommen aus **diesen Maßen und Lagen**, nie aus dem
Prüfling: ``tests/test_step_assembly.py`` liest die Konstanten hier
(``PLATE``, ``BOLT``, ``BRACKET_VOLUME`` …) und vergleicht, was
``brep.step.read_assembly`` daraus macht. Geschrieben wird mit OCCTs eigenem
XCAF-Schreiber, nicht mit ``step.write_bodies`` — sonst prüfte der Leser nur,
was der eigene Schreiber für richtig hält.

    .venv\\Scripts\\python.exe tests/data/make_step_assembly_corpus.py          # alle
    .venv\\Scripts\\python.exe tests/data/make_step_assembly_corpus.py nested   # eine
    .venv\\Scripts\\python.exe tests/data/make_step_assembly_corpus.py --check  # vergleichen

Die Dateien liegen als Ergebnis unter ``tests/data/step/``, damit der Test
eine echte Datei liest — mit Kopf, Kodierung und Einheit, wie sie ein fremdes
Programm schreibt. Der Kopf trägt feste Angaben statt der Uhrzeit.
**Byteweise wiederholbar ist die Ausgabe trotzdem nicht**: OCCTs Schreiber
ordnet die Farbangaben über eine Tabelle, deren Schlüssel Speicheradressen
sind — derselbe Erzeuger schrieb im Testprozess die Stile in anderer
Reihenfolge als von der Kommandozeile (gemessen). ``--check`` vergleicht
deshalb, was die Datei **sagt**: den XCAF-Baum mit Namen, Lagen, Farben und
Maßen, gelesen direkt über OCCT und nicht über ``brep.step`` — der Prüfling
soll seinen eigenen Sollwert nicht mitbestimmen.

Was jede Datei prüft:

- ``instances.step``: drei Instanzen eines Bolzens mit Namen und Lage (eine
  gedreht), eine davon mit eigener Farbe; eine Platte mit Teil- und
  Flächenfarbe.
- ``nested.step``: eine Unterbaugruppe zweimal eingesetzt, eine Farbe nur für
  ein tieferes Vorkommen (SHUO), eine gespiegelte Instanz.
- ``multibody.step``: ein Teil mit drei Körpern, zwei benannt und gefärbt,
  einer ohne beides.
- ``unnamed.step``: eine Baugruppe ohne einen einzigen Namen und ohne Farbe.
- ``inch.step``: ein Teil in Zoll.
- ``surfaces.step``: eine geschlossene Schale ohne Körper, eine offene Schale
  und ein Teil nur aus einer Kante.
"""

from __future__ import annotations

import io
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STEPS = HERE / "step"

# --- Maße und Farben: die Sollwerte ---------------------------------------------

#: Die Grundplatte, Ecke im Ursprung (Breite, Tiefe, Höhe in mm).
PLATE = (80.0, 40.0, 5.0)
#: Der Bolzen: Radius und Höhe, Achse +Z, Fuß im Ursprung.
BOLT = (5.0, 30.0)
#: Wo die drei Bolzen stehen: Name, Verschiebung, Drehachse, Winkel in Grad.
BOLT_INSTANCES: tuple[
    tuple[str, tuple[float, float, float], tuple[float, float, float] | None, float], ...
] = (
    ("Bolzen links", (10.0, 20.0, 5.0), None, 0.0),
    ("Bolzen liegend", (40.0, 5.0, 10.0), (1.0, 0.0, 0.0), 90.0),
    ("Bolzen rechts", (70.0, 20.0, 5.0), None, 0.0),
)
#: Der Winkel als L-Profil in der XZ-Ebene, 10 mm in +Y gezogen.
BRACKET_OUTLINE = ((0.0, 0.0), (20.0, 0.0), (20.0, 4.0), (4.0, 4.0), (4.0, 20.0), (0.0, 20.0))
BRACKET_DEPTH = 10.0
BRACKET_VOLUME = (20.0 * 4.0 + 4.0 * 16.0) * BRACKET_DEPTH
#: Der Halter steht in der Achse um diesen Betrag in +X versetzt.
HOLDER_OFFSET = 10.0
#: Die hintere Achse steht um diesen Betrag in +Y.
AXLE_OFFSET = 50.0
#: Die gespiegelte Instanz: an der YZ-Ebene gespiegelt, dann um diesen Betrag in X.
MIRRORED_SHIFT = -30.0

GREY = "#808080"
YELLOW = "#ffd700"
BLUE = "#1e4bd2"
RED = "#e61919"
GREEN = "#28b43c"

#: Die drei Körper des mehrteiligen Teils: Name (oder keiner), Ecke, Maße, Farbe.
HOUSING: tuple[
    tuple[str | None, tuple[float, float, float], tuple[float, float, float], str | None], ...
] = (
    ("Unterteil", (0.0, 0.0, 0.0), (60.0, 40.0, 20.0), RED),
    ("Deckel", (0.0, 0.0, 25.0), (60.0, 40.0, 3.0), GREEN),
    (None, (70.0, 0.0, 0.0), (10.0, 10.0, 10.0), None),
)
#: Der Klotz in Zoll, als Millimeter gebaut und in Zoll geschrieben.
INCH_BLOCK = (25.4, 50.8, 76.2)


# --- XCAF ------------------------------------------------------------------------


def _colour(hex_colour: str) -> Any:
    from OCP.Quantity import Quantity_Color, Quantity_TypeOfColor

    value = hex_colour.lstrip("#")
    red, green, blue = (int(value[index : index + 2], 16) / 255.0 for index in (0, 2, 4))
    return Quantity_Color(red, green, blue, Quantity_TypeOfColor.Quantity_TOC_sRGB)


def _document() -> tuple[Any, Any, Any]:
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool

    document = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    XCAFApp_Application.GetApplication_s().InitDocument(document)
    XCAFDoc_ShapeTool.SetAutoNaming_s(False)
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    colours = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
    return document, shapes, colours


def _name(label: Any, text: str) -> None:
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name

    TDataStd_Name.Set_s(label, TCollection_ExtendedString(text, True))


def _paint(colours: Any, label: Any, hex_colour: str) -> None:
    from OCP.XCAFDoc import XCAFDoc_ColorType

    colours.SetColor(label, _colour(hex_colour), XCAFDoc_ColorType.XCAFDoc_ColorSurf)


def placement(
    shift: tuple[float, float, float],
    axis: tuple[float, float, float] | None = None,
    degrees: float = 0.0,
    *,
    mirror_x: bool = False,
) -> Any:
    """Erst spiegeln, dann drehen, dann verschieben — als ``TopLoc_Location``."""
    from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCP.TopLoc import TopLoc_Location

    transform = gp_Trsf()
    if mirror_x:
        transform.SetMirror(gp_Ax2(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(1.0, 0.0, 0.0)))
    if axis is not None:
        turn = gp_Trsf()
        turn.SetRotation(gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(*axis)), math.radians(degrees))
        transform = turn.Multiplied(transform)
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(*shift))
    return TopLoc_Location(move.Multiplied(transform))


def bolt() -> Any:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    return BRepPrimAPI_MakeCylinder(BOLT[0], BOLT[1]).Shape()


def plate() -> Any:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    return BRepPrimAPI_MakeBox(*PLATE).Shape()


def bracket() -> Any:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec

    outline = BRepBuilderAPI_MakePolygon()
    for x, z in BRACKET_OUTLINE:
        outline.Add(gp_Pnt(x, 0.0, z))
    outline.Close()
    face = BRepBuilderAPI_MakeFace(outline.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0.0, BRACKET_DEPTH, 0.0)).Shape()


def _top_face(shape: Any, height: float) -> Any:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        properties = GProp_GProps()
        BRepGProp.SurfaceProperties_s(explorer.Current(), properties)
        if abs(properties.CentreOfMass().Z() - height) < 1e-9:
            return explorer.Current()
        explorer.Next()
    raise RuntimeError("the plate has no top face")


def instances_document() -> Any:
    """Platte (grau, Oberseite gelb) und drei Instanzen eines blauen Bolzens."""
    document, shapes, colours = _document()
    root = shapes.NewShape()
    _name(root, "Baugruppe")
    board = plate()
    board_label = shapes.AddShape(board, False)
    _name(board_label, "Platte")
    _paint(colours, board_label, GREY)
    top = shapes.AddSubShape(board_label, _top_face(board, PLATE[2]))
    _paint(colours, top, YELLOW)
    bolt_label = shapes.AddShape(bolt(), False)
    _name(bolt_label, "Bolzen")
    _paint(colours, bolt_label, BLUE)
    component = shapes.AddComponent(root, board_label, placement((0.0, 0.0, 0.0)))
    _name(component, "Grundplatte")
    for name, shift, axis, degrees in BOLT_INSTANCES:
        component = shapes.AddComponent(root, bolt_label, placement(shift, axis, degrees))
        _name(component, name)
        if name == "Bolzen rechts":
            # Die Instanzfarbe: Rot für genau dieses Vorkommen, das Teil bleibt blau.
            _paint(colours, component, RED)
    shapes.UpdateAssemblies()
    return document


def nested_document() -> Any:
    """Zwei Achsen aus Welle und Halter; die hintere Welle rot (SHUO); ein Halter gespiegelt."""
    from OCP.collections import Sequence_TDF_Label
    from OCP.XCAFDoc import XCAFDoc_ColorType

    document, shapes, colours = _document()
    root = shapes.NewShape()
    _name(root, "Gestell")
    axle = shapes.NewShape()
    _name(axle, "Achse")
    bolt_label = shapes.AddShape(bolt(), False)
    _name(bolt_label, "Bolzen")
    _paint(colours, bolt_label, BLUE)
    bracket_label = shapes.AddShape(bracket(), False)
    _name(bracket_label, "Winkel")
    _paint(colours, bracket_label, GREEN)
    _name(shapes.AddComponent(axle, bolt_label, placement((0.0, 0.0, 0.0))), "Welle")
    _name(shapes.AddComponent(axle, bracket_label, placement((HOLDER_OFFSET, 0.0, 0.0))), "Halter")
    front = shapes.AddComponent(root, axle, placement((0.0, 0.0, 0.0)))
    _name(front, "Achse vorn")
    back = shapes.AddComponent(root, axle, placement((0.0, AXLE_OFFSET, 0.0)))
    _name(back, "Achse hinten")
    mirrored = shapes.AddComponent(
        root, bracket_label, placement((MIRRORED_SHIFT, 0.0, 0.0), mirror_x=True)
    )
    _name(mirrored, "Halter gespiegelt")
    shapes.UpdateAssemblies()
    # Die Farbe gilt dem Vorkommen „Welle“ in „Achse hinten“ und nur ihm —
    # die vordere Welle bleibt blau. XCAF legt dafür eine SHUO an.
    parts = Sequence_TDF_Label()
    shapes.GetComponents_s(axle, parts, False)
    shaft = parts.Value(1)
    located = shapes.GetShape_s(shaft).Moved(shapes.GetLocation_s(back))
    if not colours.SetInstanceColor(located, XCAFDoc_ColorType.XCAFDoc_ColorSurf, _colour(RED)):
        raise RuntimeError("the instance colour found no occurrence")
    return document


def multibody_document() -> Any:
    """Ein Teil „Gehäuse“ mit drei Körpern, wie Fusion ein Bauteil mit Körpern schreibt."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    from OCP.TopoDS import TopoDS_Compound

    document, shapes, colours = _document()
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    boxes = [
        BRepPrimAPI_MakeBox(gp_Pnt(*corner), *size).Shape() for _name_, corner, size, _c in HOUSING
    ]
    for box in boxes:
        builder.Add(compound, box)
    part = shapes.AddShape(compound, False)
    _name(part, "Gehäuse")
    for box, (name, _corner, _size, colour) in zip(boxes, HOUSING, strict=True):
        if name is None and colour is None:
            continue
        sub = shapes.AddSubShape(part, box)
        if name is not None:
            _name(sub, name)
        if colour is not None:
            _paint(colours, sub, colour)
    return document


def unnamed_document() -> Any:
    """Zwei Teile, drei Instanzen, kein einziger Name und keine Farbe."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    document, shapes, _colours = _document()
    root = shapes.NewShape()
    cube = shapes.AddShape(BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape(), False)
    bar = shapes.AddShape(BRepPrimAPI_MakeBox(20.0, 5.0, 5.0).Shape(), False)
    shapes.AddComponent(root, cube, placement((0.0, 0.0, 0.0)))
    shapes.AddComponent(root, bar, placement((30.0, 0.0, 0.0)))
    shapes.AddComponent(root, bar, placement((30.0, 20.0, 0.0)))
    shapes.UpdateAssemblies()
    return document


def inch_document() -> Any:
    """Ein Klotz, der in der Datei 1 × 2 × 3 Zoll misst."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    document, shapes, _colours = _document()
    part = shapes.AddShape(BRepPrimAPI_MakeBox(*INCH_BLOCK).Shape(), False)
    _name(part, "Zollklotz")
    return document


def surfaces_document() -> Any:
    """Eine geschlossene Schale ohne Körper, eine offene Schale, ein Teil nur aus einer Kante."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS_Shell

    document, shapes, _colours = _document()
    root = shapes.NewShape()
    _name(root, "Flächenmodell")
    closed = TopExp_Explorer(BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape(), TopAbs_SHELL).Current()
    builder = BRep_Builder()
    open_shell = TopoDS_Shell()
    builder.MakeShell(open_shell)
    faces = TopExp_Explorer(
        BRepPrimAPI_MakeBox(gp_Pnt(20.0, 0.0, 0.0), 10.0, 10.0, 10.0).Shape(), TopAbs_FACE
    )
    count = 0
    while faces.More():
        if count < 5:
            builder.Add(open_shell, faces.Current())
        count += 1
        faces.Next()
    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(0.0, 30.0, 0.0), gp_Pnt(10.0, 30.0, 0.0)).Edge()
    for name, shape, shift in (
        ("Hülle", closed, (0.0, 0.0, 0.0)),
        ("Wanne", open_shell, (0.0, 0.0, 0.0)),
        ("Skizze", edge, (0.0, 0.0, 0.0)),
    ):
        label = shapes.AddShape(shape, False)
        _name(label, name)
        _name(shapes.AddComponent(root, label, placement(shift)), name)
    shapes.UpdateAssemblies()
    return document


BUILDERS = {
    "instances": (instances_document, "MM"),
    "nested": (nested_document, "MM"),
    "multibody": (multibody_document, "MM"),
    "unnamed": (unnamed_document, "MM"),
    "inch": (inch_document, "INCH"),
    "surfaces": (surfaces_document, "MM"),
}


def written(document: Any, unit: str = "MM") -> bytes:
    """Ein XCAF-Dokument als STEP-Bytes, mit festem Kopf statt Uhrzeit."""
    from OCP.APIHeaderSection import APIHeaderSection_MakeHeader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.Message import Message, Message_PrinterOStream
    from OCP.STEPCAFControl import STEPCAFControl_Controller, STEPCAFControl_Writer
    from OCP.TCollection import TCollection_HAsciiString

    Message.DefaultMessenger_s().RemovePrinters(Message_PrinterOStream.get_type_descriptor_s())
    STEPCAFControl_Controller.Init_s()
    Interface_Static.SetIVal_s("write.stepcaf.subshapes.name", 1)
    Interface_Static.SetCVal_s("write.step.unit", unit)
    try:
        writer = STEPCAFControl_Writer()
        writer.SetColorMode(True)
        writer.SetNameMode(True)
        if not writer.Transfer(document):
            raise RuntimeError("the XCAF document did not transfer")
        header = APIHeaderSection_MakeHeader(writer.ChangeWriter().Model())
        header.SetName(TCollection_HAsciiString("Solidon test corpus"))
        header.SetTimeStamp(TCollection_HAsciiString("2026-09-23T00:00:00"))
        header.SetAuthorValue(1, TCollection_HAsciiString(""))
        header.SetOrganizationValue(1, TCollection_HAsciiString(""))
        header.SetPreprocessorVersion(TCollection_HAsciiString("Open CASCADE"))
        header.SetOriginatingSystem(
            TCollection_HAsciiString("tests/data/make_step_assembly_corpus.py")
        )
        header.SetAuthorisation(TCollection_HAsciiString(""))
        stream = io.BytesIO()
        if writer.WriteStream(stream) != IFSelect_RetDone:
            raise RuntimeError("the STEP writer failed")
        return stream.getvalue()
    finally:
        Interface_Static.SetCVal_s("write.step.unit", "MM")


def build(name: str) -> bytes:
    """Die Bytes einer Korpusdatei, frisch gebaut."""
    maker, unit = BUILDERS[name]
    return written(maker(), unit)


def summary(data: bytes) -> list[str]:
    """Was eine STEP-Datei sagt, als Zeilen: Baum, Namen, Lagen, Farben, Maße.

    Unabhängig vom Prüfling — gelesen mit ``STEPCAFControl_Reader`` direkt.
    Namen über den Attributiterator, nicht über ``FindAttribute``: Das stürzt
    in OCP 8.0.1 nativ ab (siehe ``brep.step._name_of``).
    """
    from OCP.BRepGProp import BRepGProp
    from OCP.collections import (
        Sequence_TCollection_AsciiString,
        Sequence_TDF_Attribute,
        Sequence_TDF_Label,
    )
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.Quantity import Quantity_Color, Quantity_TypeOfColor
    from OCP.STEPCAFControl import STEPCAFControl_Controller, STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDF import TDF_AttributeIterator, TDF_Label
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_ColorTool, XCAFDoc_ColorType, XCAFDoc_DocumentTool

    STEPCAFControl_Controller.Init_s()
    Interface_Static.SetIVal_s("read.stepcaf.subshapes.name", 1)
    document = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    XCAFApp_Application.GetApplication_s().InitDocument(document)
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetSHUOMode(True)
    if reader.ReadStream("corpus.step", io.BytesIO(data)) != IFSelect_RetDone:
        return ["unlesbar"]
    reader.Transfer(document)
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    units = Sequence_TCollection_AsciiString()
    reader.Reader().FileUnits(
        units, Sequence_TCollection_AsciiString(), Sequence_TCollection_AsciiString()
    )
    lines = [f"unit {units.Value(1).ToCString() if units.Length() else '?'}"]

    def name(label: Any) -> str:
        attributes = TDF_AttributeIterator(label)
        while attributes.More():
            attribute = attributes.Value()
            if isinstance(attribute, TDataStd_Name):
                text = str(attribute.Get().ToExtString())
                # Den Übersetzernamen zählt OCCT je Prozess hoch („8.0 4",
                # „8.0 6"); er sagt nichts über die Datei.
                if text.startswith("Open CASCADE STEP translator"):
                    return "(Übersetzer)"
                # Eine Instanz ohne Namen heißt nach der laufenden Nummer ihres
                # NAUO, und auch die zählt je Prozess weiter.
                return "(Nummer)" if text.isdigit() else text
            attributes.Next()
        return "-"

    def colour(label: Any) -> str:
        found = Quantity_Color()
        for kind in (XCAFDoc_ColorType.XCAFDoc_ColorSurf, XCAFDoc_ColorType.XCAFDoc_ColorGen):
            if XCAFDoc_ColorTool.GetColor_s(label, kind, found):
                red, green, blue = found.Values(Quantity_TypeOfColor.Quantity_TOC_sRGB)
                return "#" + "".join(f"{round(value * 255):02x}" for value in (red, green, blue))
        return "-"

    def walk(label: Any, depth: int) -> None:
        indent = "  " * depth
        if shapes.IsComponent_s(label):
            transform = shapes.GetLocation_s(label).Transformation()
            cells = " ".join(
                f"{transform.Value(row, column):.6f}"
                for row in (1, 2, 3)
                for column in (1, 2, 3, 4)
            )
            chains = Sequence_TDF_Attribute()
            shuos = ""
            if shapes.GetAllComponentSHUO_s(label, chains):
                shuos = " shuo " + ",".join(
                    colour(chains.Value(number).Label()) for number in range(1, chains.Length() + 1)
                )
            lines.append(f"{indent}instance {name(label)} {colour(label)} [{cells}]{shuos}")
            referred = TDF_Label()
            shapes.GetReferredShape_s(label, referred)
            walk(referred, depth + 1)
            return
        shape = shapes.GetShape_s(label)
        properties = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, properties)
        lines.append(
            f"{indent}{'assembly' if shapes.IsAssembly_s(label) else 'part'} {name(label)} "
            f"{colour(label)} {shape.ShapeType().name} volume {properties.Mass():.4f}"
        )
        subs = Sequence_TDF_Label()
        shapes.GetSubShapes_s(label, subs)
        lines.extend(
            sorted(
                f"{indent}  sub {name(subs.Value(n))} {colour(subs.Value(n))} "
                f"{shapes.GetShape_s(subs.Value(n)).ShapeType().name}"
                for n in range(1, subs.Length() + 1)
            )
        )
        if shapes.IsAssembly_s(label):
            components = Sequence_TDF_Label()
            shapes.GetComponents_s(label, components, False)
            for number in range(1, components.Length() + 1):
                walk(components.Value(number), depth + 1)

    roots = Sequence_TDF_Label()
    shapes.GetFreeShapes(roots)
    for number in range(1, roots.Length() + 1):
        walk(roots.Value(number), 0)
    return lines


def compare(name: str) -> tuple[bool, str]:
    """Ob die abgelegte Datei dasselbe sagt wie der Erzeuger (``summary``)."""
    path = STEPS / f"{name}.step"
    if not path.is_file():
        return False, f"{path.name}: fehlt"
    stored, fresh = summary(path.read_bytes()), summary(build(name))
    if stored == fresh:
        return True, f"{path.name}: gleich"
    first = next(
        (index for index, (a, b) in enumerate(zip(stored, fresh, strict=False)) if a != b),
        min(len(stored), len(fresh)),
    )
    shown = stored[first] if first < len(stored) else "-"
    built = fresh[first] if first < len(fresh) else "-"
    return False, f"{path.name}: anders als der Erzeuger — Datei {shown!r}, Erzeuger {built!r}"


def main(arguments: list[str]) -> int:
    """Baut die genannten Dateien, ohne Namen alle; mit ``--check`` nur vergleichen."""
    check = "--check" in arguments
    names = [name for name in arguments if name != "--check"] or list(BUILDERS)
    failed = False
    for name in names:
        if check:
            same, text = compare(name)
            failed = failed or not same
            print(text)
            continue
        STEPS.mkdir(parents=True, exist_ok=True)
        (STEPS / f"{name}.step").write_bytes(build(name))
        print(f"{name}.step geschrieben")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
