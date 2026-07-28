"""STEP in and out (Bauplan §30, §25, §29).

STEP is the format that carries a construction rather than a skin: faces,
edges and their curves survive it, which is why it is worth having a second
kernel for at all. A round trip has to come back as the same body — not as the
same picture — and the test says so by measuring volume and counting faces.

Units: STEP files carry their own, and OpenCASCADE converts to millimetres on
the way in. That is the one conversion the input stage does not have to guess
at (§11.1), and the reason a STEP never asks the unit question.
"""

from __future__ import annotations

from pathlib import Path

from app.core.brep.kernel import Solid, require
from app.core.errors import ValidationError
from app.core.log import get_logger
from app.i18n import _

_log = get_logger(__name__)

#: What a STEP file is called. Both spellings are in the wild.
SUFFIXES: tuple[str, ...] = (".step", ".stp")


def read(payload: bytes) -> Solid:
    """One body from STEP bytes. Several shapes arrive as one compound."""
    require()
    import tempfile

    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    with tempfile.TemporaryDirectory(prefix="formwerk-step-") as folder:
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
    body = Solid(shape)
    _log.info("read a STEP body with %d face(s)", body.face_count)
    return body


def write(solid: Solid) -> bytes:
    """A body as STEP bytes, in millimetres."""
    require()
    import tempfile

    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

    with tempfile.TemporaryDirectory(prefix="formwerk-step-") as folder:
        path = Path(folder) / "output.step"
        writer = STEPControl_Writer()
        Interface_Static.SetCVal_s("write.step.unit", "MM")
        writer.Transfer(solid.shape, STEPControl_AsIs)
        if writer.Write(str(path)) != IFSelect_RetDone:
            raise ValidationError(
                field="file",
                detail=_("Die STEP-Datei ließ sich nicht schreiben."),
                constraint="unwritable",
            )
        return path.read_bytes()


def is_step(suffix: str) -> bool:
    return suffix.lower() in SUFFIXES
