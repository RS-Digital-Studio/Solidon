"""STEP hinein und hinaus (Bauplan §30, §25, §29, §17.1).

STEP ist das Format, das eine Konstruktion trägt statt einer Haut: Flächen,
Kanten und ihre Kurven überstehen es — und genau darum lohnt ein zweiter Kern
überhaupt. Eine runde Reise muss als derselbe Körper zurückkommen, nicht als
dasselbe Bild, und der Test sagt das, indem er Volumen misst und Flächen
zählt.

Einheiten: STEP-Dateien tragen ihre eigenen, und OpenCASCADE rechnet beim
Hereinkommen auf Millimeter um. Das ist die eine Umrechnung, die die
Eingangsstufe nicht raten muss (§11.1), und der Grund, warum ein STEP nie die
Einheitenfrage stellt.

**Eine STEP-Datei ist eine Baugruppe** (P7.4). :func:`read_assembly` liest
sie über XCAF (``STEPCAFControl_Reader``) und löst jede Komponenteninstanz in
einen eigenen Körper mit Weltlage, Namen und Flächenfarben auf — eine flache
Liste, wie die 3MF-Baugruppe sie liefert (``ingest.threemf``). Lebende
Instanzbeziehungen entstehen dabei nicht: Zwei Bolzen desselben Teils sind
danach zwei unabhängige Körper. :func:`read` bleibt der bisherige Weg — ein
Körper aus ``OneShape`` — für Schritte, die vor P7.4 gespeichert wurden.

Welcher Name und welche Farbe gilt, steht bei :func:`read_assembly`; beides
ist Vertrag und in ``app/core/brep/CLAUDE.md`` festgehalten.
"""

from __future__ import annotations

import io
import re
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from app.core.brep.kernel import Solid, box_limits, copy_shape, require
from app.core.errors import CANCEL, CHOOSE_ANOTHER_FILE, ValidationError
from app.core.log import get_logger
from app.core.types import CancelToken
from app.core.units import ASSEMBLY_BODIES, ASSEMBLY_DEPTH, EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Wie eine STEP-Datei heißt. Beide Schreibweisen kommen vor.
SUFFIXES: tuple[str, ...] = (".step", ".stp")

#: Mehr Körper trägt kein Projekt — dieselbe Grenze wie bei der 3MF
#: (``units.ASSEMBLY_BODIES``). Ein Name im Modul, damit ein Test sie senken kann.
MAX_BODIES: Final = ASSEMBLY_BODIES

#: Wie tief Baugruppen ineinander stecken dürfen. XCAF kennt keine Zyklen,
#: aber eine Datei, die dieselbe Unterbaugruppe über viele Ebenen verdoppelt,
#: vervielfacht sich je Ebene; die Körpergrenze fängt das, diese Zahl fängt
#: die Tiefe davor (``units.ASSEMBLY_DEPTH``, wie bei der 3MF).
MAX_DEPTH: Final = ASSEMBLY_DEPTH

#: Wie oft die Traversierung eine Komponente betreten darf, bevor sie anhält.
#: Eine Baugruppe aus lauter leeren Unterbaugruppen trägt keinen Körper, der
#: die Körpergrenze auslöste — betreten wird sie trotzdem.
_MAX_VISITS: Final = MAX_BODIES * (MAX_DEPTH + 1)

#: Namen, die kein Mensch vergeben hat. OpenCASCADE schreibt seinen eigenen
#: Übersetzernamen ins PRODUCT, wenn niemand einen setzt („Open CASCADE STEP
#: translator 8.0 1", gemessen), eine Instanz ohne Namen heißt nach ihrer
#: laufenden Nummer („1", „2" — die ID des NAUO), und XCAFs automatische
#: Benennung vergibt Typwörter und Label-Pfade („SOLID", „=>[0:1:1:2]").
_GENERATED_NAME: Final = re.compile(
    r"(?:open cascade step translator.*"
    r"|\d+"
    r"|nauo\d*"
    r"|=>\[[\d:]+\]"
    r"|(?:solid|compound|compsolid|shell|face|shape|assembly|part)\s*\d*"
    r"|unnamed.*|noname.*|none|default)",
    re.IGNORECASE,
)


def usable_name(text: str | None) -> bool:
    """Ob ein Name aus der Datei einen Körper benennt oder nur ein Platzhalter ist."""
    if text is None:
        return False
    stripped = text.strip()
    return bool(stripped) and _GENERATED_NAME.fullmatch(stripped) is None


@dataclass(frozen=True, slots=True)
class StepBody:
    """Ein Körper einer STEP-Baugruppe — eine aufgelöste Instanz, in Weltlage."""

    key: str
    """Stabile Kennung innerhalb der Datei: der Pfad der Instanzen („1.3.2"),
    bei einem Teil mit mehreren Körpern dazu dessen Nummer („1.3#2"). Die
    Importauswahl speichert diese Kennungen (``load_step.bodies``)."""
    name: str
    """Der Name nach Vorrang und Unterscheidung (siehe :func:`read_assembly`)."""
    shape: Any
    """``TopoDS_Shape`` in Weltlage und Millimetern — die Instanzlagen sind
    angewandt, eine Spiegelung ist eingerechnet statt als Lage getragen."""
    face_colours: tuple[str | None, ...]
    """Farbe je Fläche als ``#rrggbb`` (sRGB), in der Reihenfolge von
    ``TopExp.MapShapes(shape, FACE)`` — derselben, in der ``Solid.face_slots``
    zählt. ``None`` heißt: Die Datei sagt für diese Fläche nichts."""
    part: str
    """Welches Teil diese Instanz einsetzt. Gleiche Kennung heißt: dieselbe
    Geometrie, nur anders gelegt oder gefärbt."""
    mirrored: bool = False
    """Ob die Instanz gespiegelt eingesetzt ist (negative Determinante)."""
    named: bool = True
    """Ob die Datei den Körper benennt; ``False`` heißt: Ersatzname."""
    solid: bool = True
    """Ob die Form ein Volumenkörper ist. Offene Flächen eines Teils kommen
    gesammelt als ein Körper, der ``False`` trägt."""
    placement: Any = None
    """Die Weltlage der Instanz als ``gp_Trsf`` — ``None`` für die Identität.
    Zwei Instanzen derselben Geometrie unterscheiden sich genau darin."""
    geometry: str = ""
    """Welche Geometrie die Instanz trägt: das Teil und, bei einem Teil mit
    mehreren Körpern, dessen Nummer. Gleiche Angabe, gleiche Form."""
    size: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Die Maße des Teils selbst, unabhängig von seiner Lage — was der Kunde
    als Größe des Körpers liest."""
    box: tuple[float, float, float, float, float, float] | None = None
    """Ein Quader um die Weltlage, der die Form sicher enthält: die Grenzen des
    Teils, an ihren acht Ecken in die Lage gebracht. Bei einer reinen
    Verschiebung sind das die genauen Grenzen (``box_exact``)."""
    box_exact: bool = False

    @property
    def colours(self) -> tuple[str, ...]:
        """Die Farben dieses Körpers, in der Reihenfolge ihres ersten Auftretens."""
        return tuple(dict.fromkeys(colour for colour in self.face_colours if colour))

    def bounds(self) -> tuple[float, float, float, float, float, float]:
        """Die genauen Weltgrenzen der Form, ohne Toleranzzuschlag.

        Aus dem Quader, wo er genau ist, sonst gemessen: ``AddOptimal`` kostet
        an einem gerundeten Teil rund 8 ms, an tausend Instanzen also Sekunden
        für eine Antwort, die bei einer Verschiebung schon feststeht.
        """
        if self.box is not None and self.box_exact:
            return self.box
        return shape_bounds(self.shape)


@dataclass(frozen=True, slots=True)
class StepAssembly:
    """Was eine STEP-Datei an Körpern trägt, flach aufgelöst."""

    bodies: tuple[StepBody, ...]
    unit: str = "millimetre"
    """Die Längeneinheit, die die Datei nennt — umgerechnet ist schon."""
    skipped: int = 0
    """Teile ohne eine einzige Fläche (nur Kanten oder Punkte)."""

    @property
    def colours(self) -> tuple[str, ...]:
        """Jede Farbe der Datei einmal, in der Reihenfolge ihres ersten Auftretens."""
        return tuple(dict.fromkeys(colour for body in self.bodies for colour in body.colours))

    @property
    def millimetres(self) -> bool:
        """Ob die Datei in Millimetern geschrieben ist."""
        return self.unit.lower() in ("millimetre", "millimeter", "mm")


def shape_bounds(shape: Any) -> tuple[float, float, float, float, float, float]:
    """Die Grenzen einer Form ohne Toleranzzuschlag (wie ``Solid.bounds``)."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    return box_limits(box)


# --- Lesen ---------------------------------------------------------------------


_translator_ready = False

#: Ein XCAF-Dokument zur Zeit. Das Dokument hängt an der einen
#: ``XCAFApp_Application`` des Prozesses, und die Übersetzerparameter sind
#: global (``Interface_Static``); der Einleseplan im Arbeiter und die
#: Auswertung eines zweiten Imports dürfen sich dort nicht begegnen. Gelesen
#: wird eine Baugruppe in Sekunden — so lange wartet der zweite.
_XCAF = threading.Lock()


def _prepare_translator() -> None:
    """Die Übersetzerparameter einmal je Prozess setzen.

    ``Interface_Static`` ist ein globaler Zustand, und er kennt die Schlüssel
    erst, wenn der Controller sie angemeldet hat: Vor
    ``STEPCAFControl_Controller.Init`` gibt ``SetIVal`` still ``False`` zurück
    (gemessen). ``subshapes.name`` holt die Körpernamen eines Teils mit
    mehreren Körpern — Fusion schreibt sie als Namen der
    ``MANIFOLD_SOLID_BREP`` („internal_tray1" an ``build_tray_v3.step``);
    ohne den Schalter kamen sie als leere Namen an. Dieselbe Angabe beim
    Schreiben, damit die Rundreise sie behält.
    """
    global _translator_ready
    if _translator_ready:
        return
    from OCP.Interface import Interface_Static
    from OCP.STEPCAFControl import STEPCAFControl_Controller

    STEPCAFControl_Controller.Init_s()
    Interface_Static.SetIVal_s("read.stepcaf.subshapes.name", 1)
    Interface_Static.SetIVal_s("write.stepcaf.subshapes.name", 1)
    _translator_ready = True


def _unreadable() -> ValidationError:
    return ValidationError(
        suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
        field="file",
        detail=_("Diese STEP-Datei ließ sich nicht lesen."),
        constraint="unreadable",
    )


def _no_geometry() -> ValidationError:
    return ValidationError(
        suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
        field="file",
        detail=_("Die STEP-Datei enthält keine Geometrie."),
        constraint="no_geometry",
    )


def read(payload: bytes) -> Solid:
    """Ein Körper aus STEP-Bytes. Mehrere Formen kommen als ein Compound an.

    Der Weg vor P7.4, und er bleibt: Ein Ladeschritt, der vor der
    Baugruppenlesung gespeichert wurde, rechnet mit ihm weiter, damit dasselbe
    Projekt dasselbe Teil ergibt (§15.1) — und er ist der Rückfall, wenn XCAF
    eine Datei nicht auflösen kann; ``load_step`` meldet dann, dass Namen und
    Farben fehlen.
    """
    require()
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    reader = STEPControl_Reader()
    if reader.ReadStream("input.step", io.BytesIO(payload)) != IFSelect_RetDone:
        raise _unreadable()
    reader.TransferRoots()
    shape = reader.OneShape()

    if shape is None or shape.IsNull():
        raise _no_geometry()
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
        body = _closed_solid(shell)
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


def _silent(fraction: float, text: str) -> None:
    """Kein Fortschritt gewünscht — eine Funktion statt ``None`` wie in ``ingest``."""


def read_assembly(
    payload: bytes,
    stem: str = "",
    *,
    cancelled: CancelToken | None = None,
    progress: Callable[[float, str], None] = _silent,
) -> StepAssembly:
    """Jede Komponenteninstanz einer STEP-Datei als eigener Körper in Weltlage.

    ``stem`` ist der Dateiname ohne Endung: Ein einzelner Körper ohne
    brauchbaren Namen heißt nach seiner Datei, wie bei einer STL.

    **Der Name** eines Körpers — die erste brauchbare Angabe
    (:func:`usable_name`) in dieser Reihenfolge:

    1. *Instanz*: der Name des Vorkommens, das das Teil einsetzt
       („Bolzen links").
    2. *Referenz*: der Name des eingesetzten Teils („Bolzen").
    3. *Form*: der Name des Körpers selbst in der Datei.

    Trägt ein Teil **mehrere** Körper, nennen Instanz und Referenz die Gruppe
    und nicht den Körper — dort geht der Körpername vor, und ohne ihn heißt der
    Körper wie das Teil mit seiner Nummer. Heißen danach mehrere Körper gleich,
    bekommt jeder den Namen des nächsten unterscheidenden Vorkommens darüber in
    Klammern („Welle (Achse vorn)"), und was dann noch gleich heißt, eine
    Nummer („Bolzen 1", „Bolzen 2").

    **Die Farbe** einer Fläche — die erste Angabe in dieser Reihenfolge:

    1. *Instanz*: eine Farbe am Vorkommen, von der äußersten Baugruppe nach
       innen; auf jeder Ebene zuerst eine Angabe genau für das tiefere
       Vorkommen (XCAF-SHUO), dann die Farbe des Vorkommens selbst. Wer in der
       Baugruppe einen Bolzen rot färbt, meint den ganzen Bolzen.
    2. *Referenz*: im eingesetzten Teil die Farbe der Fläche, dann die ihrer
       Schale, dann die ihres Körpers, dann die des Teils — das Genaueste
       gewinnt.
    3. *Form*: eine Farbe, die nur an der Form selbst hängt
       (``XCAFDoc_ColorTool.GetColor`` über die Form statt über das Label).

    Oberflächenfarbe vor allgemeiner Farbe, Kantenfarben zählen nicht. **Der
    Farbraum ist sRGB**: STEP-Programme schreiben die Werte, die sie zeigen,
    und OpenCASCADE hält Farben intern linear — ``0,627`` aus der Datei kam
    als ``0,3515`` an (gemessen an ``build_tray_v3.step``). Zurückgerechnet
    wird mit ``Quantity_TOC_sRGB`` und auf acht Bit je Kanal gerundet, die
    Genauigkeit von ``#rrggbb`` im Rest der Anwendung.

    Abbruch wird vor dem Lesen, zwischen Lesen und Übertragen und je
    Komponente geprüft. Das Übertragen selbst ist ein nativer Aufruf ohne
    Unterbrechungspunkt: ``Message_ProgressIndicator`` lässt sich in OCP
    8.0.1 nicht in Python ableiten („No constructor defined", gemessen).
    """
    with _XCAF:
        return _read_assembly(payload, stem, cancelled=cancelled, progress=progress)


def _read_assembly(
    payload: bytes,
    stem: str,
    *,
    cancelled: CancelToken | None,
    progress: Callable[[float, str], None],
) -> StepAssembly:
    """:func:`read_assembly` unter der Sperre ``_XCAF``."""
    require()
    _prepare_translator()
    from OCP.collections import Sequence_TCollection_AsciiString, Sequence_TDF_Label
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    progress(0.0, str(_("STEP-Datei lesen")))
    document = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    XCAFApp_Application.GetApplication_s().InitDocument(document)
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetSHUOMode(True)
    reader.SetLayerMode(False)
    reader.SetPropsMode(False)
    reader.SetGDTMode(False)
    reader.SetMatMode(False)
    reader.SetViewMode(False)
    if reader.ReadStream("input.step", io.BytesIO(payload)) != IFSelect_RetDone:
        raise _unreadable()
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    progress(0.3, str(_("STEP-Datei lesen")))
    if not reader.Transfer(document):
        raise _unreadable()
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    progress(0.6, str(_("STEP-Datei lesen")))

    lengths = Sequence_TCollection_AsciiString()
    reader.Reader().FileUnits(
        lengths, Sequence_TCollection_AsciiString(), Sequence_TCollection_AsciiString()
    )
    unit = lengths.Value(1).ToCString() if lengths.Length() else "millimetre"

    shapes = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    roots = Sequence_TDF_Label()
    shapes.GetFreeShapes(roots)
    walk = _Walk(shapes, XCAFDoc_DocumentTool.ColorTool_s(document.Main()), cancelled)
    for number in range(1, roots.Length() + 1):
        walk.visit(roots.Value(number), (str(number),), (), None, 1)
        progress(0.6 + 0.4 * number / roots.Length(), str(_("STEP-Datei lesen")))
    if not walk.found:
        raise _no_geometry()
    bodies = _named(walk.found, stem)
    _log.info(
        "read a STEP assembly: %d bodies from %d parts, %d colour(s), unit %s",
        len(bodies),
        len({body.part for body in bodies}),
        len({colour for body in bodies for colour in body.colours}),
        unit,
    )
    return StepAssembly(bodies=tuple(bodies), unit=unit, skipped=walk.skipped)


def hex_colour(red: float, green: float, blue: float) -> str:
    """``#rrggbb`` aus sRGB-Werten zwischen null und eins."""

    def channel(value: float) -> int:
        return max(0, min(255, int(value * 255.0 + 0.5)))

    return f"#{channel(red):02x}{channel(green):02x}{channel(blue):02x}"


def _name_of(label: Any) -> str | None:
    """Der Name an einem Label.

    **Nicht über ``FindAttribute``.** Die übliche Form
    ``label.FindAttribute(TDataStd_Name.GetID_s(), TDataStd_Name())`` — so steht
    sie auch in CadQuery — stürzt in OCP 8.0.1 nativ ab: Der Rückgabewert ist
    ein Handle-Ausgabeparameter, und das in Python erzeugte Attribut wird
    dabei freigegeben, während Python es noch hält (Zugriffsverletzung nach
    wenigen Aufrufen, reproduzierbar an den Körperlabels von
    ``build_tray_v3.step``). Der Iterator gibt einen Zeiger auf das
    vorhandene Attribut zurück, und der Handle-Zähler hält es.
    """
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDF import TDF_AttributeIterator

    attributes = TDF_AttributeIterator(label)
    while attributes.More():
        attribute = attributes.Value()
        if isinstance(attribute, TDataStd_Name):
            return str(attribute.Get().ToExtString())
        attributes.Next()
    return None


def _label_colour(label: Any) -> str | None:
    """Die Farbe an einem Label: Oberflächenfarbe vor allgemeiner Farbe."""
    from OCP.Quantity import Quantity_Color
    from OCP.XCAFDoc import XCAFDoc_ColorTool, XCAFDoc_ColorType

    colour = Quantity_Color()
    for kind in (XCAFDoc_ColorType.XCAFDoc_ColorSurf, XCAFDoc_ColorType.XCAFDoc_ColorGen):
        if XCAFDoc_ColorTool.GetColor_s(label, kind, colour):
            return _srgb(colour)
    return None


def _srgb(colour: Any) -> str:
    """Eine OCCT-Farbe (intern linear) als ``#rrggbb`` im sRGB der Datei."""
    from OCP.Quantity import Quantity_TypeOfColor

    red, green, blue = colour.Values(Quantity_TypeOfColor.Quantity_TOC_sRGB)
    return hex_colour(red, green, blue)


def _shape_colour(tool: Any, shape: Any) -> str | None:
    """Die Farbe, die an der Form selbst hängt, nicht an einem Label im Pfad."""
    from OCP.Quantity import Quantity_Color
    from OCP.XCAFDoc import XCAFDoc_ColorType

    colour = Quantity_Color()
    for kind in (XCAFDoc_ColorType.XCAFDoc_ColorSurf, XCAFDoc_ColorType.XCAFDoc_ColorGen):
        if tool.GetColor(shape, kind, colour):
            return _srgb(colour)
    return None


@dataclass(slots=True)
class _Piece:
    """Ein Körper eines Teils, noch ohne Lage: Form, Name und Flächenfarben."""

    shape: Any
    name: str | None
    colours: list[str | None]
    solid: bool
    bounds: tuple[float, float, float, float, float, float] = (0.0,) * 6
    """Die genauen Grenzen der ungelegten Form — einmal je Teil gemessen."""


@dataclass(slots=True)
class _Part:
    """Was ein eingesetztes Teil einmal beiträgt, gleich wie oft es vorkommt."""

    key: str
    name: str | None
    pieces: list[_Piece]


@dataclass(slots=True)
class _Found:
    """Ein aufgelöster Körper vor der Namensgebung."""

    key: str
    shape: Any
    colours: tuple[str | None, ...]
    part: str
    mirrored: bool
    solid: bool
    candidates: tuple[str | None, ...]
    """Brauchbare Namen vom Körper aus nach oben: zuerst der Name nach
    Vorrang, danach die Vorkommen darüber — die Unterscheider."""
    number: int
    """Die Nummer des Körpers in seinem Teil, null bei einem Teil mit einem."""
    placement: Any
    """Die Weltlage der Instanz (``gp_Trsf``) oder ``None``."""
    size: tuple[float, float, float]
    box: tuple[float, float, float, float, float, float]
    box_exact: bool
    fallback: str | None
    """Der Name des Teils, nach dem ein namenloser Körper eines mehrteiligen
    Teils heißt."""


class _Walk:
    """Die Traversierung der XCAF-Struktur: Instanzen in Weltlage auflösen."""

    def __init__(self, shapes: Any, colour_tool: Any, cancelled: CancelToken | None) -> None:
        from OCP.collections import Sequence_TDF_Label

        self.shapes = shapes
        self.colour_tool = colour_tool
        self.cancelled = cancelled
        table = Sequence_TDF_Label()
        colour_tool.GetColors(table)
        # Eine Datei ohne eine einzige Farbe fragt keine Fläche nach ihrer:
        # Die Suche über die Form (``GetColor`` an der Form) durchläuft je
        # Fläche den Formbaum, und das kostete an 1000 Instanzen ohne Farbe
        # 0,7 s für lauter leere Antworten.
        self.coloured = table.Length() > 0
        self.found: list[_Found] = []
        self.skipped = 0
        self.visits = 0
        self._parts: dict[str, _Part] = {}
        self._shuos: dict[str, list[tuple[tuple[str, ...], str]]] = {}

    def visit(
        self,
        label: Any,
        path: tuple[str, ...],
        instances: tuple[Any, ...],
        placement: Any,
        depth: int,
    ) -> None:
        """Ein Label: Baugruppe → ihre Komponenten, sonst ein Teil mit Körpern."""
        from OCP.collections import Sequence_TDF_Label
        from OCP.TDF import TDF_Label

        self.visits += 1
        if self.visits > _MAX_VISITS:
            raise ValidationError(
                suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
                field="file",
                detail=_(
                    "Die Baugruppe enthält zu viele verschachtelte oder wiederholte Komponenten."
                ),
                constraint="too_many_components",
                values={"components": self.visits, "limit": _MAX_VISITS},
            )
        if self.cancelled is not None:
            self.cancelled.raise_if_cancelled()
        if depth > MAX_DEPTH:
            _log.warning("STEP assembly nested deeper than %d — stopped", MAX_DEPTH)
            return
        if self.shapes.IsAssembly_s(label):
            components = Sequence_TDF_Label()
            self.shapes.GetComponents_s(label, components, False)
            for number in range(1, components.Length() + 1):
                component = components.Value(number)
                referred = TDF_Label()
                if not self.shapes.GetReferredShape_s(component, referred):
                    continue
                local = self.shapes.GetLocation_s(component).Transformation()
                world = local if placement is None else placement.Multiplied(local)
                self.visit(
                    referred, (*path, str(number)), (*instances, component), world, depth + 1
                )
            return
        self._take(label, path, instances, placement)

    def _take(
        self, label: Any, path: tuple[str, ...], instances: tuple[Any, ...], placement: Any
    ) -> None:
        part = self._part(label)
        if not part.pieces:
            self.skipped += 1
            return
        overriding = self._instance_colour(instances)
        # Der innerste Instanzname nennt dieses Vorkommen; die brauchbaren
        # Namen der Vorkommen darüber, von innen nach außen, unterscheiden
        # gleichnamige Körper.
        inner = _name_of(instances[-1]) if instances else None
        above = tuple(
            name
            for name in (_name_of(entry) for entry in reversed(instances[:-1]))
            if usable_name(name)
        )
        several = len(part.pieces) > 1
        for number, piece in enumerate(part.pieces, 1):
            if self.cancelled is not None:
                self.cancelled.raise_if_cancelled()
            shape, mirrored, moved_faces = _placed(piece.shape, placement)
            colours = (
                (overriding,) * len(piece.colours)
                if overriding is not None
                else tuple(piece.colours[index] for index in moved_faces)
            )
            fallback: str | None = None
            if several:
                own = piece.name if usable_name(piece.name) else None
                candidates: tuple[str | None, ...] = (
                    own,
                    *((inner,) if usable_name(inner) else ()),
                    *above,
                )
                fallback = next((name for name in (inner, part.name) if usable_name(name)), None)
            else:
                first = next(
                    (name for name in (inner, part.name, piece.name) if usable_name(name)), None
                )
                candidates = (first, *above)
            key = ".".join(path) + (f"#{number}" if several else "")
            box, exact = _placed_box(piece.bounds, placement)
            low_x, low_y, low_z, high_x, high_y, high_z = piece.bounds
            self.found.append(
                _Found(
                    key=key,
                    shape=shape,
                    colours=colours,
                    part=part.key,
                    mirrored=mirrored,
                    solid=piece.solid,
                    candidates=candidates,
                    number=number if several else 0,
                    placement=placement,
                    size=(high_x - low_x, high_y - low_y, high_z - low_z),
                    box=box,
                    box_exact=exact,
                    fallback=fallback,
                )
            )
            if len(self.found) > MAX_BODIES:
                raise ValidationError(
                    suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
                    field="file",
                    detail=_("Die Baugruppe hat mehr Körper, als diese Anwendung verarbeitet."),
                    constraint="too_many_bodies",
                    values={"bodies": len(self.found), "limit": MAX_BODIES},
                )

    def _part(self, label: Any) -> _Part:
        """Körper, Namen und Flächenfarben eines Teils — einmal je Teil."""
        from OCP.TCollection import TCollection_AsciiString
        from OCP.TDF import TDF_Tool

        entry = TCollection_AsciiString()
        TDF_Tool.Entry_s(label, entry)
        key = entry.ToCString()
        known = self._parts.get(key)
        if known is None:
            known = _Part(key=key, name=_name_of(label), pieces=self._pieces(label))
            self._parts[key] = known
        return known

    def _pieces(self, label: Any) -> list[_Piece]:
        from OCP.BRep import BRep_Builder
        from OCP.collections import (
            IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as Ancestry,
        )
        from OCP.collections import (
            IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap,
        )
        from OCP.collections import Sequence_TDF_Label
        from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
        from OCP.TopExp import TopExp
        from OCP.TopoDS import TopoDS, TopoDS_Compound

        shape = self.shapes.GetShape_s(label)
        if shape is None or shape.IsNull():
            return []
        solids, shells, faces = ShapeMap(), ShapeMap(), ShapeMap()
        TopExp.MapShapes_s(shape, TopAbs_SOLID, solids)
        TopExp.MapShapes_s(shape, TopAbs_SHELL, shells)
        TopExp.MapShapes_s(shape, TopAbs_FACE, faces)
        # Welche Unterform einen eigenen Namen oder eine eigene Farbe trägt.
        own: dict[tuple[int, int], Any] = {}
        subs = Sequence_TDF_Label()
        self.shapes.GetSubShapes_s(label, subs)
        for number in range(1, subs.Length() + 1):
            sub = subs.Value(number)
            form = self.shapes.GetShape_s(sub)
            for kind, known in (
                (TopAbs_SOLID, solids),
                (TopAbs_SHELL, shells),
                (TopAbs_FACE, faces),
            ):
                if form.ShapeType() == kind:
                    index = int(known.FindIndex(form))
                    if index:
                        own[int(kind), index] = sub
        part_colour = _label_colour(label)

        def colour_of(face: Any, shell: Any | None, solid: Any | None) -> str | None:
            if not self.coloured:
                return None
            candidates = [own.get((int(TopAbs_FACE), int(faces.FindIndex(face))))]
            if shell is not None:
                candidates.append(own.get((int(TopAbs_SHELL), int(shells.FindIndex(shell)))))
            if solid is not None:
                candidates.append(own.get((int(TopAbs_SOLID), int(solids.FindIndex(solid)))))
            for sub_label in candidates:
                if sub_label is not None:
                    found = _label_colour(sub_label)
                    if found is not None:
                        return found
            if part_colour is not None:
                return part_colour
            return _shape_colour(self.colour_tool, face) or (
                _shape_colour(self.colour_tool, solid) if solid is not None else None
            )

        def piece_faces(container: Any, solid: Any | None) -> list[str | None]:
            owners = Ancestry()
            TopExp.MapShapesAndAncestors_s(container, TopAbs_FACE, TopAbs_SHELL, owners)
            local = ShapeMap()
            TopExp.MapShapes_s(container, TopAbs_FACE, local)
            result: list[str | None] = []
            for index in range(1, local.Extent() + 1):
                face = local.FindKey(index)
                shell = None
                position = int(owners.FindIndex(face))
                if position:
                    listed = owners.FindFromIndex(position)
                    if listed.Size():
                        shell = listed.First()
                result.append(colour_of(face, shell, solid))
            return result

        pieces: list[_Piece] = []
        for index in range(1, solids.Extent() + 1):
            solid = solids.FindKey(index)
            sub = own.get((int(TopAbs_SOLID), index))
            pieces.append(
                _Piece(
                    shape=solid,
                    name=_name_of(sub) if sub is not None else None,
                    colours=piece_faces(solid, solid),
                    solid=True,
                )
            )
        # Was nicht in einem Körper steckt: geschlossene Schalen werden Körper
        # (manche Programme schreiben Volumen als Flächenmodell), offene
        # Schalen und lose Flächen kommen gesammelt als ein offener Körper —
        # still weglassen hieße, Geometrie der Datei zu verlieren.
        in_solids = Ancestry()
        TopExp.MapShapesAndAncestors_s(shape, TopAbs_SHELL, TopAbs_SOLID, in_solids)
        in_shells = Ancestry()
        TopExp.MapShapesAndAncestors_s(shape, TopAbs_FACE, TopAbs_SHELL, in_shells)
        builder = BRep_Builder()
        loose = TopoDS_Compound()
        builder.MakeCompound(loose)
        has_loose = False
        for index in range(1, shells.Extent() + 1):
            shell = shells.FindKey(index)
            position = int(in_solids.FindIndex(shell))
            if position and in_solids.FindFromIndex(position).Size():
                continue
            closed = _closed_solid(TopoDS.Shell(shell))
            sub = own.get((int(TopAbs_SHELL), index))
            if closed is not None:
                pieces.append(
                    _Piece(
                        shape=closed,
                        name=_name_of(sub) if sub is not None else None,
                        colours=piece_faces(shell, None),
                        solid=True,
                    )
                )
            else:
                builder.Add(loose, shell)
                has_loose = True
        for index in range(1, faces.Extent() + 1):
            face = faces.FindKey(index)
            position = int(in_shells.FindIndex(face))
            if position and in_shells.FindFromIndex(position).Size():
                continue
            builder.Add(loose, face)
            has_loose = True
        if has_loose:
            pieces.append(
                _Piece(shape=loose, name=None, colours=piece_faces(loose, None), solid=False)
            )
        for piece in pieces:
            piece.bounds = shape_bounds(piece.shape)
        return pieces

    def _instance_colour(self, instances: tuple[Any, ...]) -> str | None:
        """Die Farbe, die ein Vorkommen im Pfad setzt — von außen nach innen."""
        if not instances or not self.coloured:
            return None
        from OCP.TCollection import TCollection_AsciiString
        from OCP.TDF import TDF_Tool

        entries: list[str] = []
        for component in instances:
            text = TCollection_AsciiString()
            TDF_Tool.Entry_s(component, text)
            entries.append(text.ToCString())
        for position, component in enumerate(instances):
            # Eine Angabe genau für ein tieferes Vorkommen (SHUO) ist
            # genauer als die Farbe des ganzen Vorkommens auf derselben Ebene.
            for chain, shuo in sorted(
                self._shuo_chains(component, entries[position]), key=lambda item: -len(item[0])
            ):
                if tuple(entries[position : position + len(chain)]) == chain:
                    return shuo
            own = _label_colour(component)
            if own is not None:
                return own
        return None

    def _shuo_chains(self, component: Any, entry: str) -> list[tuple[tuple[str, ...], str]]:
        """Die SHUO-Ketten, die an diesem Vorkommen beginnen, mit ihrer Farbe."""
        known = self._shuos.get(entry)
        if known is not None:
            return known
        from OCP.collections import Sequence_TDF_Attribute, Sequence_TDF_Label
        from OCP.TCollection import TCollection_AsciiString
        from OCP.TDF import TDF_Tool
        from OCP.XCAFDoc import XCAFDoc_ShapeTool

        def entry_of(label: Any) -> str:
            text = TCollection_AsciiString()
            TDF_Tool.Entry_s(label, text)
            return str(text.ToCString())

        chains: list[tuple[tuple[str, ...], str]] = []
        attributes = Sequence_TDF_Attribute()
        if XCAFDoc_ShapeTool.GetAllComponentSHUO_s(component, attributes):
            for number in range(1, attributes.Length() + 1):
                upper = attributes.Value(number).Label()
                colour = _label_colour(upper)
                if colour is None:
                    continue
                chain = [entry_of(upper.Father())]
                current = upper
                for _level in range(MAX_DEPTH):
                    following = Sequence_TDF_Label()
                    XCAFDoc_ShapeTool.GetSHUONextUsage_s(current, following)
                    if following.Length() != 1:
                        break
                    current = following.Value(1)
                    chain.append(entry_of(current.Father()))
                if len(chain) > 1:
                    chains.append((tuple(chain), colour))
        self._shuos[entry] = chains
        return chains


def _closed_solid(shell: Any) -> Any | None:
    """Ein Körper aus einer geschlossenen Schale — oder ``None``, wenn sie offen ist.

    Die eine Stelle für :func:`read` (``_closed_shells_as_solids``) und die
    Baugruppe (``_Walk._pieces``): dicht, richtig herum orientiert
    (``OrientClosedSolid``) und gültig (``BRepCheck_Analyzer``) — sonst bleibt
    die Schale, was sie ist.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepLib import BRepLib
    from OCP.ShapeAnalysis import ShapeAnalysis_Shell

    checker = ShapeAnalysis_Shell()
    checker.LoadShells(shell)
    # Freie Kanten zählt die Prüfung nur mit ``alsofree`` (``Solid.is_closed``).
    checker.CheckOrientedShells(shell, True)
    if checker.HasFreeEdges():
        return None
    maker = BRepBuilderAPI_MakeSolid(shell)
    if not maker.IsDone():
        return None
    solid = maker.Solid()
    if not BRepLib.OrientClosedSolid_s(solid) or not BRepCheck_Analyzer(solid).IsValid():
        return None
    return solid


def _placed(shape: Any, placement: Any) -> tuple[Any, bool, tuple[int, ...]]:
    """Die Form in Weltlage, ob gespiegelt, und welche Quellfläche jede Fläche ist.

    **Eine starre Lage bleibt eine Lage** (``TopLoc_Location``): Die Form
    teilt ihre Geometrie mit dem Teil, und die Flächen stehen in derselben
    Reihenfolge. **Eine Spiegelung oder ein Maßstab wird eingerechnet**
    (``BRepBuilderAPI_Transform``): Eine Lage mit negativer Determinante
    kehrt Normalen um, und Vernetzung wie Volumen verlassen sich auf die
    Orientierung der Flächen — dort baut der Transformationsbuilder die
    Flächen neu und richtet sie aus. Die Flächenzuordnung kommt dann aus
    seinem ``ModifiedShape``, nie aus einer angenommenen Reihenfolge.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopLoc import TopLoc_Location

    source = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, source)
    identity = tuple(range(source.Extent()))
    if placement is None:
        return shape, False, identity
    mirrored = bool(placement.IsNegative())
    scaled = abs(abs(placement.ScaleFactor()) - 1.0) > EPS_GEOM
    if not mirrored and not scaled:
        return shape.Moved(TopLoc_Location(placement)), False, identity
    builder = BRepBuilderAPI_Transform(shape, placement, True)
    moved = builder.Shape()
    target = ShapeMap()
    TopExp.MapShapes_s(moved, TopAbs_FACE, target)
    order = [0] * target.Extent()
    for index in range(1, source.Extent() + 1):
        position = int(target.FindIndex(builder.ModifiedShape(source.FindKey(index))))
        if position:
            order[position - 1] = index - 1
    return moved, mirrored, tuple(order)


def _placed_box(
    bounds: tuple[float, float, float, float, float, float], placement: Any
) -> tuple[tuple[float, float, float, float, float, float], bool]:
    """Ein Quader um die gelegte Form: die acht Ecken der Teilgrenzen in der Lage.

    Er enthält die Form immer; genau ist er, wenn die Lage nur verschiebt
    (``gp_Identity``, ``gp_Translation``). Gedreht oder gespiegelt ist er
    höchstens größer — gut für eine Vorschau und als Schranke, nicht als Maß.
    """
    from OCP.gp import gp_Pnt, gp_TrsfForm

    if placement is None:
        return bounds, True
    low_x, low_y, low_z, high_x, high_y, high_z = bounds
    corners = [
        gp_Pnt(x, y, z).Transformed(placement)
        for x in (low_x, high_x)
        for y in (low_y, high_y)
        for z in (low_z, high_z)
    ]
    box = (
        min(corner.X() for corner in corners),
        min(corner.Y() for corner in corners),
        min(corner.Z() for corner in corners),
        max(corner.X() for corner in corners),
        max(corner.Y() for corner in corners),
        max(corner.Z() for corner in corners),
    )
    return box, _moves_only(placement, gp_TrsfForm)


def _moves_only(placement: Any, forms: Any) -> bool:
    """Ob eine Lage nur verschiebt — nach ihrer Form oder, zusammengesetzt, nach ihrer Matrix.

    Eine aus XCAF-Lagen verkettete Verschiebung trägt die Form
    ``gp_CompoundTrsf``, auch wenn ihr linearer Teil die Einheitsmatrix ist.
    Verglichen wird dann bitgenau: Nur eine wirkliche Einheitsmatrix macht den
    Quader zur genauen Grenze, sonst wird gemessen.
    """
    if placement.Form() in (forms.gp_Identity, forms.gp_Translation):
        return True
    if placement.ScaleFactor() != 1.0:
        return False
    return all(
        placement.Value(row, column) == (1.0 if row == column else 0.0)
        for row in (1, 2, 3)
        for column in (1, 2, 3)
    )


def _named(found: Sequence[_Found], stem: str) -> list[StepBody]:
    """Gibt jedem Körper seinen Namen — Vorrang, Unterscheidung, Ersatz."""
    base: list[str | None] = []
    for entry in found:
        first = entry.candidates[0] if entry.candidates else None
        if first is None and entry.fallback is not None:
            first = f"{entry.fallback} {entry.number}" if entry.number else entry.fallback
        base.append(first)
    names = list(base)
    groups: dict[str, list[int]] = {}
    for index, name in enumerate(names):
        if name is not None:
            groups.setdefault(name, []).append(index)
    for name, members in groups.items():
        if len(members) < 2:
            continue
        # Das nächste Vorkommen darüber, das die Gleichnamigen auseinanderhält.
        for level in range(1, max(len(found[index].candidates) for index in members)):
            qualified = {
                index: found[index].candidates[level]
                for index in members
                if level < len(found[index].candidates) and found[index].candidates[level]
            }
            if len(qualified) == len(members) and len(set(qualified.values())) == len(members):
                for index, qualifier in qualified.items():
                    names[index] = f"{name} ({qualifier})"
                break
        else:
            for number, index in enumerate(members, 1):
                names[index] = f"{name} {number}"
    unnamed = [index for index, name in enumerate(names) if name is None]
    for number, index in enumerate(unnamed, 1):
        if len(found) == 1 and stem:
            names[index] = stem
        else:
            names[index] = str(_("Körper {number}", number=number))
    return [
        StepBody(
            key=entry.key,
            name=str(names[index]),
            shape=entry.shape,
            face_colours=entry.colours,
            part=entry.part,
            mirrored=entry.mirrored,
            named=base[index] is not None,
            solid=entry.solid,
            placement=entry.placement,
            geometry=f"{entry.part}#{entry.number}",
            size=entry.size,
            box=entry.box,
            box_exact=entry.box_exact,
        )
        for index, entry in enumerate(found)
    ]


# --- Schreiben -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StepExport:
    """Ein Körper für eine STEP-Datei: Form, Name, Farbe je Fläche."""

    solid: Solid
    name: str = ""
    face_colours: tuple[str | None, ...] = ()
    """``#rrggbb`` je Fläche in der Reihenfolge von ``solid.faces()``; leer
    heißt: ohne Farbe."""


def write(solid: Solid, name: str = "", face_colours: Sequence[str | None] = ()) -> bytes:
    """Ein Körper als STEP-Bytes, in Millimetern.

    ``name`` ist der Name des Teils in der Datei. Ohne ihn steht dort, was der
    Übersetzer von sich aus schreibt — „Open CASCADE STEP translator 7.9 1" —,
    und in Fusion heißt das Teil danach „Körper1". Der Objektname ist im
    Dokument vorhanden; er ging nur auf dem Weg verloren. Beim 3MF war das
    schon einmal ein Fund, dort hieß eine Baugruppe „Object 1, Object 2".
    """
    return write_bodies([StepExport(solid, name, tuple(face_colours))])


def write_bodies(bodies: Sequence[StepExport], assembly: str = "") -> bytes:
    """Körper mit Namen und Farben als STEP-Bytes (XCAF, Millimeter).

    Ein Körper wird ein Teil; mehrere werden Teile einer Baugruppe, jedes an
    seiner Weltlage (die Instanzen stehen an der Identität — die Lage steckt
    in der Form). So liest :func:`read_assembly` die Datei zurück, wie sie
    geschrieben wurde: dieselben Körper, dieselben Namen, dieselben Farben.

    **Der Name steht wörtlich im PRODUCT.** Der frühere Weg über
    ``write.step.product.name`` hängte eine laufende Nummer an: Aus
    „Lagerbock" wurde „Lagerbock 1" (gemessen). **Und Umlaute stehen
    kodiert in der Datei** (``\\X2\\00E4\\X0\\``, ISO 10303-21): Der Schreiber
    legte die UTF-8-Bytes roh ab, ein Leser nach der Norm liest daraus
    „GehÃ¤use".
    """
    with _XCAF:
        return _write_bodies(bodies, assembly)


def _write_bodies(bodies: Sequence[StepExport], assembly: str) -> bytes:
    """:func:`write_bodies` unter der Sperre ``_XCAF``."""
    require()
    _prepare_translator()
    if not bodies:
        raise ValidationError(
            field="objects",
            detail=_("Es ist nichts zum Exportieren ausgewählt."),
            constraint="empty",
        )
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool

    document = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    XCAFApp_Application.GetApplication_s().InitDocument(document)
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    colours = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
    # Ohne automatische Benennung: Ein Teil ohne Namen soll keinen erfundenen
    # bekommen — „SOLID" ist kein Name, den jemand vergeben hat.
    naming = XCAFDoc_ShapeTool.AutoNaming_s()
    XCAFDoc_ShapeTool.SetAutoNaming_s(False)
    try:
        root = None
        if len(bodies) > 1:
            root = shapes.NewShape()
            _set_name(root, assembly or "Solidon")
        for body in bodies:
            # Der Transfer verändert auch bei gültigen Rundflächen interne
            # Kennzeichen. Szene und Cache behalten ausschließlich ihre eigene
            # Form; die Kopie führt die Flächenzuordnung mit.
            working, faces, _edges = copy_shape(body.solid.shape)
            working, faces = _without_root_location(working, faces)
            label = shapes.AddShape(working, False)
            _set_name(label, body.name or "Solidon")
            _paint(shapes, colours, label, working, faces, body.face_colours)
            if root is not None:
                component = shapes.AddComponent(root, label, TopLoc_Location())
                _set_name(component, body.name or "Solidon")
        shapes.UpdateAssemblies()
        Interface_Static.SetCVal_s("write.step.unit", "MM")
        writer = STEPCAFControl_Writer()
        writer.SetColorMode(True)
        writer.SetNameMode(True)
        writer.SetLayerMode(False)
        writer.SetPropsMode(False)
        writer.SetDimTolMode(False)
        writer.SetMaterialMode(False)
        stream = io.BytesIO()
        if not writer.Transfer(document) or writer.WriteStream(stream) != IFSelect_RetDone:
            raise ValidationError(
                field="file",
                detail=_("Die STEP-Datei ließ sich nicht schreiben."),
                constraint="unwritable",
            )
    finally:
        XCAFDoc_ShapeTool.SetAutoNaming_s(naming)
    return escaped(stream.getvalue())


def _without_root_location(shape: Any, faces: tuple[int, ...]) -> tuple[Any, tuple[int, ...]]:
    """Die Form ohne Lage an der Wurzel — die Lage steckt danach in der Geometrie.

    Ein Körper aus einer Baugruppe trägt seine Instanzlage als
    ``TopLoc_Location`` an der Wurzel, auch wenn sie die Identität ist. XCAF
    findet die Flächen eines so gelegten Teils nicht wieder: ``AddSubShape``
    gab für jede Fläche ein leeres Label zurück, und die Flächenfarben fehlten
    in der Datei (gemessen an der Grundplatte aus ``instances.step``). Die Lage
    wird deshalb eingerechnet (starr, die Flächen bleiben analytisch), und die
    Flächenzuordnung folgt über ``ModifiedShape``.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopLoc import TopLoc_Location

    location = shape.Location()
    if location.IsIdentity():
        return shape, faces
    bare = shape.Located(TopLoc_Location())
    builder = BRepBuilderAPI_Transform(bare, location.Transformation(), True)
    moved = builder.Shape()
    source, target = ShapeMap(), ShapeMap()
    TopExp.MapShapes_s(bare, TopAbs_FACE, source)
    TopExp.MapShapes_s(moved, TopAbs_FACE, target)
    renumbered = tuple(
        int(target.FindIndex(builder.ModifiedShape(source.FindKey(index + 1)))) - 1
        for index in range(source.Extent())
    )
    return moved, tuple(renumbered[index] for index in faces)


def _set_name(label: Any, text: str) -> None:
    """Ein Name an ein Label — als Unicode, nicht Byte für Byte.

    ``TCollection_ExtendedString(text)`` nimmt die UTF-8-Bytes aus Python als
    einzelne Zeichen; aus „Gehäuse" wurde so „GehÃ¤use" (gemessen). Das
    zweite Argument sagt, dass die Bytes mehrbytig kodiert sind.
    """
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name

    TDataStd_Name.Set_s(label, TCollection_ExtendedString(text, True))


def _paint(
    shapes: Any,
    colours: Any,
    label: Any,
    shape: Any,
    faces: tuple[int, ...],
    face_colours: tuple[str | None, ...],
) -> None:
    """Farben an ein Teil: eine für alle Flächen am Teil, sonst je Fläche."""
    if not face_colours or not any(face_colours):
        return
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.XCAFDoc import XCAFDoc_ColorType

    surface = XCAFDoc_ColorType.XCAFDoc_ColorSurf
    distinct = set(face_colours)
    if len(distinct) == 1 and len(face_colours) == len(faces):
        colours.SetColor(label, _quantity(face_colours[0] or ""), surface)
        return
    target = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, target)
    for source, colour in enumerate(face_colours):
        if colour is None or source >= len(faces):
            continue
        face = target.FindKey(faces[source] + 1)
        sub = shapes.AddSubShape(label, face)
        if not sub.IsNull():
            colours.SetColor(sub, _quantity(colour), surface)


def _quantity(colour: str) -> Any:
    """``#rrggbb`` (sRGB) als OCCT-Farbe."""
    from OCP.Quantity import Quantity_Color, Quantity_TypeOfColor

    value = colour.lstrip("#")
    red, green, blue = (int(value[index : index + 2], 16) / 255.0 for index in (0, 2, 4))
    return Quantity_Color(red, green, blue, Quantity_TypeOfColor.Quantity_TOC_sRGB)


def escaped(payload: bytes) -> bytes:
    """Nicht-ASCII-Zeichen einer STEP-Datei nach ISO 10303-21 kodiert.

    ``\\X2\\hhhh…\\X0\\`` für die Basisebene, ``\\X4\\hhhhhhhh…\\X0\\``
    darüber. Außerhalb von Zeichenketten steht in einer gültigen Datei kein
    solches Zeichen, also genügt es, sie überall zu ersetzen. Eine Datei, die
    kein gültiges UTF-8 ist, bleibt, wie sie ist.
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    if text.isascii():
        return payload

    def run(match: re.Match[str]) -> str:
        chunk = match.group(0)
        if all(ord(character) <= 0xFFFF for character in chunk):
            return "\\X2\\" + "".join(f"{ord(character):04X}" for character in chunk) + "\\X0\\"
        return "\\X4\\" + "".join(f"{ord(character):08X}" for character in chunk) + "\\X0\\"

    return re.sub(r"[^\x00-\x7f]+", run, text).encode("ascii")


def is_step(suffix: str) -> bool:
    return suffix.lower() in SUFFIXES
