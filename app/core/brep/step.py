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

from app.core.brep.kernel import Solid, require
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
    """Ein Körper als STEP-Bytes, in Millimetern."""
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
