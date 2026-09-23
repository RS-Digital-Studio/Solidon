"""STEP hinein und hinaus (Bauplan §30, §25, §29).

STEP ist das Format, das eine Konstruktion trägt statt einer Haut: Flächen,
Kanten und ihre Kurven überstehen es — und genau darum lohnt ein zweiter Kern
überhaupt. Eine runde Reise muss als derselbe Körper zurückkommen, nicht als
dasselbe Bild, und der Test sagt das, indem er Volumen misst und Flächen
zählt.

Einheiten: STEP-Dateien tragen ihre eigenen, und OpenCASCADE rechnet beim
Hereinkommen auf Millimeter um. Das ist die eine Umrechnung, die die
Eingangsstufe nicht raten muss (§11.1), und der Grund, warum ein STEP nie die
Einheitenfrage stellt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.brep.kernel import Solid, copy_shape, require
from app.core.errors import ValidationError
from app.core.log import get_logger
from app.i18n import _

_log = get_logger(__name__)

#: Wie eine STEP-Datei heißt. Beide Schreibweisen kommen vor.
SUFFIXES: tuple[str, ...] = (".step", ".stp")


def read(payload: bytes) -> Solid:
    """Ein Körper aus STEP-Bytes. Mehrere Formen kommen als ein Compound an."""
    require()
    import tempfile

    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    with tempfile.TemporaryDirectory(prefix="solidon-step-") as folder:
        path = Path(folder) / "input.step"
        path.write_bytes(payload)
        reader = STEPControl_Reader()
        if reader.ReadFile(str(path)) != IFSelect_RetDone:
            raise ValidationError(
                field="file",
                detail=_("Diese STEP-Datei ließ sich nicht lesen."),
                constraint="unreadable",
            )
        reader.TransferRoots()
        shape = reader.OneShape()

    if shape is None or shape.IsNull():
        raise ValidationError(
            field="file",
            detail=_("Die STEP-Datei enthält keine Geometrie."),
            constraint="no_geometry",
        )
    body = Solid(_closed_shells_as_solids(shape))
    _log.info("read a STEP body with %d face(s)", body.face_count)
    return body


def _closed_shells_as_solids(shape: Any) -> Any:
    """Geschlossene Schalen ohne Körper werden Körper; alles andere bleibt, wie es kam.

    Manche Programme schreiben ein Teil nicht als Volumenkörper, sondern als
    Flächenmodell (``SHELL_BASED_SURFACE_MODEL``): Die Schale ist dicht, aber
    ohne das umschließende ``Solid``. OpenCASCADE liest sie genau so, und der
    Körper hatte dann null Volumenkörper — die Vereinigung mit einem
    Baustein, die Prüfung auf „ein Stück" nach Verrunden, Fase und Bewegen
    und das Gewinde einsetzen sagten ab, obwohl nichts fehlte. Eine Schale
    ohne freie Kante wird hier zum Körper, richtig herum orientiert
    (``OrientClosedSolid``) und gültig geprüft; eine offene bleibt offen, und
    ``load_step`` sagt es. Eine Form ohne lose Schale kommt unverändert
    zurück — dasselbe Objekt, keine Kopie.
    """
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepLib import BRepLib
    from OCP.ShapeAnalysis import ShapeAnalysis_Shell
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID, TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS, TopoDS_Compound

    loose = TopExp_Explorer(shape, TopAbs_SHELL, TopAbs_SOLID)
    if not loose.More():
        return shape
    builder = BRep_Builder()
    assembled = TopoDS_Compound()
    builder.MakeCompound(assembled)
    solids = TopExp_Explorer(shape, TopAbs_SOLID)
    while solids.More():
        builder.Add(assembled, solids.Current())
        solids.Next()
    changed = False
    while loose.More():
        shell = TopoDS.Shell(loose.Current())
        loose.Next()
        checker = ShapeAnalysis_Shell()
        checker.LoadShells(shell)
        checker.CheckOrientedShells(shell, True)
        body = None
        if not checker.HasFreeEdges():
            maker = BRepBuilderAPI_MakeSolid(shell)
            if maker.IsDone():
                candidate = maker.Solid()
                if (
                    BRepLib.OrientClosedSolid_s(candidate)
                    and BRepCheck_Analyzer(candidate).IsValid()
                ):
                    body = candidate
        if body is not None:
            builder.Add(assembled, body)
            changed = True
        else:
            builder.Add(assembled, shell)
    # Was außerhalb jeder Schale steht, reist mit: lose Flächen, Drähte und
    # Kanten — die Datei soll nichts verlieren, nur ihre dichten Schalen
    # werden zu dem, was sie sind.
    for kind, outside in ((TopAbs_FACE, TopAbs_SHELL), (TopAbs_WIRE, TopAbs_FACE)):
        rest = TopExp_Explorer(shape, kind, outside)
        while rest.More():
            builder.Add(assembled, rest.Current())
            rest.Next()
    edges = TopExp_Explorer(shape, TopAbs_EDGE, TopAbs_WIRE)
    while edges.More():
        builder.Add(assembled, edges.Current())
        edges.Next()
    return assembled if changed else shape


def open_edge_count(solid: Solid) -> int:
    """Wie viele Kanten des Körpers nur an einer Fläche hängen — die offenen Stellen."""
    require()
    from OCP.ShapeAnalysis import ShapeAnalysis_Shell
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    checker = ShapeAnalysis_Shell()
    checker.LoadShells(solid.shape)
    if checker.NbLoaded() == 0:
        return 0
    checker.CheckOrientedShells(solid.shape, True)
    count = 0
    free = TopExp_Explorer(checker.FreeEdges(), TopAbs_EDGE)
    while free.More():
        count += 1
        free.Next()
    return count


def write(solid: Solid, name: str = "") -> bytes:
    """Ein Körper als STEP-Bytes, in Millimetern.

    ``name`` ist der Name des Teils in der Datei. Ohne ihn steht dort, was der
    Übersetzer von sich aus schreibt — „Open CASCADE STEP translator 7.9 1" —,
    und in Fusion heißt das Teil danach „Körper1". Der Objektname ist im
    Dokument vorhanden; er ging nur auf dem Weg verloren. Beim 3MF war das
    schon einmal ein Fund, dort hieß eine Baugruppe „Object 1, Object 2".
    """
    require()
    import tempfile

    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

    with tempfile.TemporaryDirectory(prefix="solidon-step-") as folder:
        path = Path(folder) / "output.step"
        writer = STEPControl_Writer()
        Interface_Static.SetCVal_s("write.step.unit", "MM")
        # Der Name gehört gesetzt, *bevor* übertragen wird: er wandert beim
        # Transfer in das PRODUCT der Datei, nachher ist er wirkungslos.
        Interface_Static.SetCVal_s("write.step.product.name", name or "Solidon")
        # Der Transfer verändert auch bei gültigen Rundflächen interne
        # Kennzeichen. Szene und Cache behalten ausschließlich ihre eigene Form.
        working, _faces, _edges = copy_shape(solid.shape)
        writer.Transfer(working, STEPControl_AsIs)
        if writer.Write(str(path)) != IFSelect_RetDone:
            raise ValidationError(
                field="file",
                detail=_("Die STEP-Datei ließ sich nicht schreiben."),
                constraint="unwritable",
            )
        return path.read_bytes()


def is_step(suffix: str) -> bool:
    return suffix.lower() in SUFFIXES
