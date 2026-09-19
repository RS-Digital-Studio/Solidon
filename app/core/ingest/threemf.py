"""3MF lesen — als Baugruppe, mit Farbgruppen und der erklärten Einheit (§17.1, §20).

trimesh parst die Geometrie einer 3MF, gibt sie aber einheitlich grau zurück
und löst eine Komponente, die in eine externe Objektdatei zeigt, zur *ganzen
Datei* auf statt zu dem einen Objekt, das sie benennt: eine Datei mit
siebzehn Teilen in einer Objektdatei kam siebzehnmal heraus, jeder Körper auf
einer Kopie seiner selbst gestapelt. Am Modellkorpus gemessen: eine Düse aus
zwei Körpern und 290 120 Dreiecken kam als vier Körper und 580 240 an, mit
doppeltem Volumen — und damit doppelter Materialschätzung und doppelter
Druckzeit. Das ist kein Tempoproblem, also wird es nicht mit einem
schnelleren Parser behoben, sondern mit dem richtigen.

Der Leser stand bis zum 02.09.2026 neben dem Schreiber in
``export/threemf.py``, und ``geom/mesh.py`` holte ihn von dort — die unterste
Schicht des Kerns kannte damit ein Ausgabemodul. Jetzt liest ``ingest``,
``export`` schreibt, und ``geom`` kennt kein Dateiformat; die Konstanten des
Containers stehen hier, der Schreiber holt sie sich.

Von Hand geschrieben statt mit einer Bibliothek, weil es keine gibt, die nur
das tut.
"""

from __future__ import annotations

import dataclasses
import json
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from typing import Final
from xml.etree import ElementTree as ET
from xml.parsers import expat

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import (
    CANCEL,
    CHOOSE_ANOTHER_FILE,
    PROGRAMMING_ERRORS,
    Action,
    AppError,
    ValidationError,
)
from app.core.geom import transform
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import MAX_FILAMENT_COLOURS, Finding, MaterialSlot, ProgressFn, SolverInfo
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

CORE_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PRUSA_NAMESPACE = "http://schemas.slic3r.org/3mf/2017/06"

#: Belegter erweiterter Ganzflächenbereich in Orcas nativer Filamenttabelle.
NATIVE_TOOL_LIMIT: Final = 32
PRODUCTION_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"

MODEL_PATH = "3D/3dmodel.model"

#: Wo ein Slicer die Namen der Teile hinschreibt. Nicht Teil des Formats —
#: der Standard hat ein ``name``-Attribut, und diese Dateien lassen es leer —
#: aber es ist der einzige Ort, an dem „Wasserfall_4_TPU-Liner" notiert steht,
#: und eine Szene aus Körpern namens „object 7" ist eine Szene, in der niemand
#: arbeiten kann. Gelesen, wenn da; achselzuckend übergangen, wenn nicht.
SETTINGS_PATH = "Metadata/model_settings.config"

#: Endungen, die ein Slicer in einem Teilnamen stehen lässt, weil das Teil aus
#: einer Datei kam.
NAME_SUFFIXES = (".stl", ".3mf", ".obj", ".step", ".stp")

#: Farbe, die ein Slot ohne eigene bekommt. Grau, damit niemand sie für eine
#: Wahl hält.
DEFAULT_COLOUR = (0.72, 0.72, 0.72)


@dataclass(slots=True)
class _NativeMaterials:
    """Werkzeuge der Slicer; Part-IDs gelten jeweils nur in ihrem Objekt.

    ``troubles`` nennt je Objekt, was sich an seinen Werkzeugangaben nicht
    lesen ließ — das Objekt kommt dann einfarbig, die anderen behalten ihre
    Farben.
    """

    palette: tuple[MaterialSlot, ...] = ()
    objects: dict[str, int] = field(default_factory=dict)
    parts: dict[tuple[str, str], int] = field(default_factory=dict)
    volumes: dict[str, list[tuple[int, int, int]]] = field(default_factory=dict)
    troubles: dict[str, _MaterialError] = field(default_factory=dict)


class _MaterialError(Exception):
    """Werkzeug- oder Flächenfarben, die sich nicht eindeutig lesen lassen.

    Bis zum 14.09.2026 war das ein ``ValidationError`` mit dem Rat, die Datei
    im Slicer nach Filamenten aufzuteilen — und er hielt den **ganzen Import**
    an, über einem Netz, das vollständig war. So bekam ein Kunde ein Modell
    von MakerWorld nicht auf (Support-Vorgang S-20260914-e4b6d7). Seither ist
    es eine Auskunft: Der Körper wird geladen, einfarbig wenn es sein muss,
    und der Grund steht mit demselben Rat als Befund im Prüfbericht
    (Entscheidung Robert, 14.09.2026: „zur Not soll das Filament halt
    einfarbig bleiben").
    """

    def __init__(self, reason: TranslatableText | str) -> None:
        super().__init__(str(reason))
        self.reason = reason


class _ForeignVolumeError(_MaterialError):
    """Ein Dreiecksbereich von PrusaSlicer, der kein Modellteil ist.

    Ein anderer Satz als „Farben nicht gelesen": Der Bereich — ein
    Modifikator, eine Aussparung — liegt im selben Netz wie der Körper und
    kommt als dessen Material an. Das soll der Kunde erfahren, nicht nur,
    dass die Farben fehlen (Regel 21).
    """

    def __init__(self, kind: str) -> None:
        super().__init__(
            _(
                "Der Bereich „{kind}“ ist kein druckbares Modellteil und liegt im selben Netz",
                kind=kind,
            )
        )
        self.kind = kind


def _unsupported_materials(reason: TranslatableText | str) -> _MaterialError:
    """Keine Werkzeug- oder Flächenangabe still verlieren — der Grund reist mit."""
    return _MaterialError(reason)


#: Was ein Slicer außer druckbaren Teilen in ein Objekt legt. Die Namen sind
#: die aus ``model_settings.config`` (Bambu Studio, Orca, Elegoo).
NEGATIVE_KIND: Final = "negative_part"
HELPER_TITLES: Final = {
    "modifier_part": _("Modifikator"),
    "support_blocker": _("Stützblocker"),
    "support_enforcer": _("Stützverstärker"),
}
#: Aus derselben Tabelle wie die Namen, damit eine vierte Art nicht in der
#: einen Liste steht und in der anderen fehlt — das wäre ein ``KeyError`` an
#: einer Kundendatei.
HELPER_KINDS: Final[frozenset[str]] = frozenset(HELPER_TITLES)


def _is_body(kind: str) -> bool:
    """Was der Leser zu einem Körper macht — und der Zählweg mitzählt (§11).

    Eine Art, die keiner der beiden kennt, ist ein Körper: Sie wird geladen
    **und** gezählt, und der Leser sagt, dass er sie nicht kennt. Zwei
    Stellen mit je eigener Liste liefen hier auseinander — der Zählweg
    zählte nur ``normal_part``, der Leser übersprang nur, was er kannte, und
    eine neue Slicer-Art hätte die Auswertung mit ``evaluate.object_count``
    angehalten (Review, 14.09.2026).
    """
    return kind != NEGATIVE_KIND and kind not in HELPER_KINDS


#: Tiefer teilt kein Slicer: Der längste Code eines Korpus von 744 429 hat
#: 253 Ziffern, rund neun Ebenen. Ohne Grenze reißt ein Code mit tausend
#: Ebenen den Import als ``RecursionError`` — ein Dateiproblem im Gewand
#: eines Programmfehlers (§32: eine Grenze sagt etwas, sie hängt nicht).
MAX_PAINT_DEPTH: Final = 64


def _slicer_config(payload: bytes) -> ET.Element:
    """Eine Slicer-Konfiguration (``model_settings.config``,
    ``Slic3r_PE_model.config``) als Baum — **ohne Namensräume**.

    Bambu Studio und der Elegoo-Slicer schreiben ein SVG-Relief als
    ``<slic3rpe:shape …/>`` in diese Datei und deklarieren den Präfix
    nirgends; sie lesen sie selbst mit einem Parser, der von Namensräumen
    nichts weiß. ``ET.fromstring`` weiß davon und wirft „unbound prefix" —
    und daran hing der ganze Import, an einer Zeile Metadaten über einem
    vollständigen Netz (drei von sechzehn Dateien eines Downloads-Ordners,
    Support-Vorgang vom 14.09.2026).

    Expat ohne Trennzeichen für Namensräume liest die Datei so, wie der
    Slicer sie liest: Ein Präfix bleibt Teil des Namens. Die Tags, die hier
    gesucht werden — ``object``, ``part``, ``volume``, ``metadata`` — tragen
    ohnehin keinen.
    """
    builder = ET.TreeBuilder()
    parser = expat.ParserCreate()
    parser.StartElementHandler = builder.start
    parser.EndElementHandler = builder.end
    parser.CharacterDataHandler = builder.data
    try:
        parser.Parse(payload, True)
    except expat.ExpatError as problem:
        raise ET.ParseError(str(problem)) from problem
    return builder.close()


def _native_materials(container: zipfile.ZipFile, model: ET.Element) -> _NativeMaterials:
    """Native Paletten und Werkzeugnummern als Daten, ohne Slicer-Ausdrücke."""
    result = _NativeMaterials()
    names = set(container.namelist())
    values: dict[str, object] = {}
    if "Metadata/project_settings.config" in names:
        try:
            parsed = json.loads(container.read("Metadata/project_settings.config"))
            if isinstance(parsed, dict):
                values = parsed
        except (ValueError, UnicodeError) as problem:
            _log.warning("3MF project settings are not readable: %s", problem)
            raise _unsupported_materials(
                _("Die Projekteinstellungen der Datei sind nicht lesbar")
            ) from problem
    elif "Metadata/Slic3r_PE.config" in names:
        for line in container.read("Metadata/Slic3r_PE.config").decode("utf-8-sig").splitlines():
            key, separator, value = line.lstrip("; ").partition(" = ")
            if separator and key in {"filament_colour", "filament_type", "filament_settings_id"}:
                values[key] = value.split(";")
    standard = next(iter(_materials_in(model).values()), [])
    colours = values.get("filament_colour", [])
    kinds = values.get("filament_type", [])
    titles = values.get("filament_settings_id", [])
    if not isinstance(colours, list) or not all(isinstance(c, str) for c in colours):
        raise _unsupported_materials(_("Ungültige Filamentfarbliste"))
    # Ein mehrfarbiges Filament der Orca-Familie: alle Farben in einer
    # Zeichenkette, durch Leerzeichen getrennt, die erste steht zugleich in
    # ``filament_colour``. Die weiteren wandern in den Slot, damit eine
    # Bambu-Datei ihr zweifarbiges Seidenfilament auf dem Rückweg behält.
    multi = values.get("filament_multi_colour", [])
    if not isinstance(multi, list):
        multi = []
    result.palette = tuple(
        MaterialSlot(
            index=index,
            name=standard[index][0]
            if index < len(standard)
            else (
                str(titles[index]).strip('"')
                if isinstance(titles, list) and index < len(titles)
                else str(_("Slot {number}", number=index))
            ),
            colour=_rgb(colours[index]) if index < len(colours) else standard[index][1],
            material_type=str(kinds[index]).strip('"')
            if isinstance(kinds, list) and index < len(kinds)
            else None,
            extra_colours=_extra_colours(multi[index]) if index < len(multi) else (),
        )
        for index in range(max(len(colours), len(standard)))
    )
    for path in (SETTINGS_PATH, "Metadata/Slic3r_PE_model.config"):
        if path not in names:
            continue
        try:
            config = _slicer_config(container.read(path))
        except ET.ParseError as problem:
            _log.warning("3MF slicer configuration %s is not readable: %s", path, problem)
            raise _unsupported_materials(
                _("Die Slicer-Konfiguration der Datei ist nicht lesbar")
            ) from problem
        for obj in config.findall("object"):
            identifier = obj.get("id", "")
            try:
                _object_tools(obj, identifier, result)
            except _MaterialError as problem:
                result.troubles[identifier] = problem
    return result


def _object_tools(obj: ET.Element, identifier: str, result: _NativeMaterials) -> None:
    """Die Werkzeugangaben eines Objekts: das Objekt selbst, seine Teile, bei
    PrusaSlicer seine Dreiecksbereiche.

    Ein Teil, das kein druckbares Modellteil ist, hat hier kein Werkzeug —
    was es ist, liest :func:`_settings`, und :func:`read_objects` entscheidet,
    ob es übersprungen oder abgezogen wird. Ein Dreiecksbereich, der keines
    ist, bleibt dagegen ein Problem dieses Objekts: Seine Dreiecke liegen im
    selben Netz, und ohne sie herauszunehmen wäre jede Farbe daran geraten.
    """
    tool = _native_tool(obj)
    if tool is not None:
        if identifier in result.objects and result.objects[identifier] != tool:
            raise _unsupported_materials(
                _("Widersprüchliche Werkzeugzuordnungen für dasselbe Objekt")
            )
        result.objects[identifier] = tool
    for part in obj.findall("part"):
        if part.get("subtype", "normal_part") != "normal_part":
            continue
        part_tool = _native_tool(part)
        if part_tool is not None:
            result.parts[identifier, part.get("id", "")] = part_tool
    for volume in obj.findall("volume"):
        kind = volume.find("metadata[@key='volume_type']")
        if kind is not None and kind.get("value") != "ModelPart":
            raise _ForeignVolumeError(kind.get("value") or "")
        volume_tool = _native_tool(volume)
        if volume_tool is not None:
            try:
                first = int(volume.get("firstid", ""))
                last = int(volume.get("lastid", ""))
            except ValueError as problem:
                raise _unsupported_materials(_("Ungültiger Dreiecksbereich")) from problem
            result.volumes.setdefault(identifier, []).append((first, last, volume_tool))


def _native_tool(node: ET.Element) -> int | None:
    """Null erbt; positive native Nummern zählen ab eins."""
    entries = node.findall("metadata[@key='extruder']")
    found: set[int] = set()
    for entry in entries:
        try:
            value = int(entry.get("value", ""))
        except ValueError as problem:
            raise _unsupported_materials(_("Ungültige Werkzeugnummer")) from problem
        if value < 0:
            raise _unsupported_materials(_("Negative Werkzeugnummer"))
        if value:
            found.add(value - 1)
    if len(found) > 1:
        raise _unsupported_materials(_("Widersprüchliche Werkzeugnummern"))
    return next(iter(found), None)


@dataclass(frozen=True, slots=True)
class _PaintLeaf:
    """Ein Dreieck — oder Teildreieck —, das ganz einem Zustand gehört.

    Zustand 0 erbt das Werkzeug des Körpers, Zustand *n* ab 1 ist Filament *n*.
    """

    state: int


@dataclass(frozen=True, slots=True)
class _PaintSplit:
    """Ein Dreieck, das der Slicer beim Bemalen geteilt hat.

    ``sides`` zählt die halbierten Seiten (1 bis 3), ``special`` die Ecke, ab
    der der Slicer die Ecken abzählt — bei einer Seite liegt die geteilte
    gegenüber, bei zweien die **behaltene**. ``children`` stehen in der
    Reihenfolge, in der der Slicer sie anlegt; die Geometrie dazu baut
    :func:`_refine`.
    """

    sides: int
    special: int
    children: tuple[_PaintNode, ...]


_PaintNode = _PaintLeaf | _PaintSplit


def _decode_paint(code: str) -> _PaintNode:
    """Der Bemalungscode eines Dreiecks als Baum.

    Das Format ist der Bitstrom von ``TriangleSelector::serialize`` aus
    PrusaSlicer, Bambu Studio und Orca — nachgelesen, nicht erraten, und an
    744 429 Codes einer Datei von MakerWorld gemessen: jeder ging exakt auf.
    Vier Bit je Knoten, als eine Hexziffer; **die Zeichenkette steht
    rückwärts**, das letzte Zeichen ist der erste Knoten. In den unteren
    zwei Bit die Zahl der geteilten Seiten. Null heißt Blatt: dann tragen die
    oberen zwei Bit den Zustand, und ``11`` kündigt eine erweiterte Nummer an
    — die nächste Ziffer plus 3, jede ``F`` davor zählt 15 dazu (so kommen
    Bambus Filamente 17 bis 32 heraus). Sonst nennen die oberen zwei Bit die
    besondere Ecke, und es folgen ``sides + 1`` Kinder, **in umgekehrter
    Reihenfolge**.

    Ein Code, der vor dem letzten Knoten endet oder Ziffern übrig lässt, ist
    keiner: Er wird zurückgewiesen statt zur Hälfte gelesen.
    """
    try:
        nibbles = [int(char, 16) for char in reversed(code)]
    except ValueError as problem:
        raise _unsupported_materials(_("Ungültige Flächenbemalung")) from problem
    position = 0

    def next_nibble() -> int:
        nonlocal position
        if position >= len(nibbles):
            raise _unsupported_materials(_("Unvollständige oder überzählige Flächenbemalung"))
        value = nibbles[position]
        position += 1
        return value

    def node(depth: int = 0) -> _PaintNode:
        if depth > MAX_PAINT_DEPTH:
            raise _unsupported_materials(_("Flächenbemalung zu tief verschachtelt"))
        head = next_nibble()
        sides = head & 0b11
        if sides == 0:
            if head & 0b1100 != 0b1100:
                return _PaintLeaf(head >> 2)
            state = 3
            while (extra := next_nibble()) == 0b1111:
                state += 15
            return _PaintLeaf(state + extra)
        children: list[_PaintNode | None] = [None] * (sides + 1)
        for index in range(sides, -1, -1):
            children[index] = node(depth + 1)
        return _PaintSplit(
            sides, head >> 2, tuple(child for child in children if child is not None)
        )

    tree = node()
    if position != len(nibbles):
        raise _unsupported_materials(_("Unvollständige oder überzählige Flächenbemalung"))
    return tree


def _leaf_tool(leaf: _PaintLeaf) -> int | None:
    """Das Werkzeug eines Blatts, ab null gezählt — ``None`` erbt."""
    if leaf.state > NATIVE_TOOL_LIMIT:
        raise _unsupported_materials(_("Nicht unterstützte Filamentnummer"))
    return leaf.state - 1 if leaf.state else None


#: Wie tief eine Komponente andere Komponenten referenzieren darf. Das Format
#: erlaubt einen Baum, und eine Datei, die so tief verschachtelt, ist kaputt
#: statt raffiniert.
#:
#: Eine Tiefengrenze allein reicht gegen einen Zyklus nicht, und das war eine
#: Messung wert: zwei Objekte, die sich gegenseitig mit je zwei Komponenten
#: referenzieren, haben 2^32 Pfade hindurch, alle 32 tief und keiner
#: wiederholt — die Grenze hält also, und der Import kehrt nie zurück.
#: Fünfhundert Byte Datei. Was es wirklich stoppt, ist die Weigerung, ein
#: Objekt zu betreten, das schon auf dem Weg dorthin liegt (§32: eine Grenze
#: sagt etwas, sie hängt nicht).
MAX_DEPTH = 32

#: Mehr Körper trägt kein Projekt (``project.MAX_PROJECT_OBJECTS``): Jedes
#: Blatt des Builds wird ein Objekt im Stapel, und eine Datei, die mehr davon
#: erzeugt, ließe sich nie speichern.
MAX_BODIES: Final = 10_000


@dataclass(slots=True)
class _Budget:
    """Was das Auflösen des Builds bisher gekostet hat — Körper und
    **instanzierte** Dreiecke.

    Der Scan zählt gespeicherte Dreiecke, und die Zyklensperre hält nur eine
    Komponente auf, die sich selbst nennt. Eine Unterbaugruppe, die zweimal
    dieselbe nächsttiefere nennt, verdoppelt je Ebene: 432 Byte mit zehn
    Ebenen wurden 1024 Körper, 469 Byte mit vierzehn Ebenen 16 384 — aus einem
    einzigen gespeicherten Dreieck, und die Größenprüfung stand erst hinter
    dem fertigen Blattwald (Gesamtreview 05.09.2026, B-04). Gezählt wird
    deshalb beim Auflösen selbst, und die Grenze hält an, **bevor** das
    nächste Blatt entsteht.
    """

    bodies: int = 0
    triangles: int = 0
    components: int = 0

    def visit(self) -> None:
        """Begrenzt auch wiederholte Zweige, die gar kein Netz beitragen."""
        self.components += 1
        limit = MAX_BODIES * (MAX_DEPTH + 1)
        if self.components > limit:
            raise ValidationError(
                field="file",
                detail=_(
                    "Die Baugruppe enthält zu viele verschachtelte oder wiederholte Komponenten."
                ),
                constraint="too_many_components",
                values={"components": self.components, "limit": limit},
            )

    def take(self, mesh_node: ET.Element) -> None:
        """Ein Blatt mehr — oder der Abbruch, wenn es eines zu viel ist."""
        # Erst hier geholt: ``loader`` zieht die Auswertung nach, und die
        # Dreiecksgrenze soll eine Zahl bleiben, die an genau einer Stelle
        # steht — ein Test, der sie dort senkt, senkt sie auch hier.
        from app.core.ingest.loader import MAX_TRIANGLES

        self.bodies += 1
        self.triangles += _entries_in(mesh_node, _TRIANGLES_TAG)
        if self.bodies > MAX_BODIES:
            raise ValidationError(
                field="file",
                detail=_("Die Baugruppe hat mehr Körper, als diese Anwendung verarbeitet."),
                constraint="too_many_bodies",
                values={"bodies": self.bodies, "limit": MAX_BODIES},
            )
        if self.triangles > MAX_TRIANGLES:
            raise ValidationError(
                field="file",
                detail=_("Das Modell hat mehr Dreiecke, als diese Anwendung verarbeitet."),
                constraint="too_many_triangles",
                values={"triangles": self.triangles, "limit": MAX_TRIANGLES},
            )


@dataclass(frozen=True, slots=True)
class Groups:
    """Die Farbgruppen, die eine 3MF-Datei trägt (§20, Import)."""

    slots: tuple[int, ...]
    """Ein Slot-Index je Dreieck, in der Reihenfolge der Datei."""
    materials: tuple[MaterialSlot, ...]


def _unpackable(problem: Exception) -> ValidationError:
    """Ein Archiv, dessen Packverfahren wir nicht auspacken (§32).

    Deflate64 und AES stehen im Verzeichnis wie jedes andere Verfahren: Die
    Namensliste kommt, und erst beim Lesen wirft ``zipfile`` ein rohes
    ``NotImplementedError``. Verschlüsselt kommt ein ``RuntimeError`` dazu.
    Beide flogen durch jeden Leser hindurch — in der Oberfläche tat Ablegen
    dann sichtbar nichts, und die Quelle blieb als Waise im Dokument.

    **Die Datei ist nicht kaputt, sie ist anders gepackt.** Das ist ein
    anderer Satz und ein anderer Ausweg als „vermutlich beschädigt", und der
    Ausweg ist praktisch: Jeder Slicer schreibt beim Speichern ein Archiv in
    gewöhnlichem Deflate.
    """
    return ValidationError(
        field="file",
        detail=_("Diese Datei ist in einem Packverfahren geschrieben, das Solidon nicht öffnet."),
        constraint="unsupported_compression",
        values={"reason": str(problem)},
        suggestions=(
            Action(
                id="repack_file",
                label=_("Die Datei im Slicer öffnen und neu speichern."),
                primary=True,
            ),
            CANCEL,
        ),
    )


def read(payload: bytes, faces: int) -> Groups | None:
    """Liest die Materialgruppen aus einer 3MF zurück — oder ``None``, wenn
    sie keine hat.

    Gelesen wird nur eine Datei mit einem einzigen Mesh-Objekt: bei mehreren
    werden die Dreiecke auf dem Weg hinein aneinandergehängt, und die
    Reihenfolge zu raten, in der sie gelandet sind, wäre schlechter, als nichts
    zu sagen. ``faces`` ist das, was der geladene Körper wirklich hat — eine
    Abweichung heißt genau dieser Fall.

    Die Slotnummern kommen als 0..n-1 heraus. 3MF kennt Positionen in einer
    Gruppe, nicht unsere Nummerierung — ein Körper, dessen einzige Farbe Slot 3
    war, kommt also als Slot 0 zurück, mit Namen und Farbe unversehrt.
    """
    leaves = _leaves(payload, [])
    if len(leaves) == 1:
        try:
            native = _native_tools_of(leaves[0])
            if native is not None:
                if native.splits:
                    # Der Körper kam über den allgemeinen Leser und trägt die
                    # Dreiecke der Datei; die Teilung der Bemalung kennt er
                    # nicht.
                    _log.info("3MF paint splits triangles — no groups for a body read as one")
                    return None
                assigned = _groups_from(native.tools, native.palette)
                return assigned if len(assigned.slots) == faces else None
        except _MaterialError as problem:
            _log.info("3MF native colours not read: %s", problem)
            return None
    try:
        with zipfile.ZipFile(BytesIO(payload)) as container:
            model = ET.fromstring(container.read(MODEL_PATH))
    except KeyError, zipfile.BadZipFile, ET.ParseError:
        return None
    except (NotImplementedError, RuntimeError) as problem:
        raise _unpackable(problem) from problem

    materials = _materials_in(model)
    if not materials:
        return None

    objects = model.findall(f".//{{{CORE_NAMESPACE}}}object")
    meshes = [entry for entry in objects if entry.find(f"{{{CORE_NAMESPACE}}}mesh") is not None]
    if len(meshes) != 1:
        return None

    # Dieselbe Zuordnung wie beim Baugruppenleser, und aus demselben Grund an
    # einer Stelle: Sie stand hier zweimal, und die beiden Fassungen sind
    # auseinandergelaufen — die eine kannte die Vorgabe des Objekts
    # (``pindex``), die andere nicht.
    groups = _groups_of(
        meshes[0],
        materials,
        meshes[0].get("pid") or "",
        _position(meshes[0].get("pindex"), 0),
    )
    if groups is None:
        return None
    if len(groups.slots) != faces:
        _log.info(
            "3MF has %d triangles, the loaded body %d — no groups read", len(groups.slots), faces
        )
        return None
    return groups


@dataclass(frozen=True, slots=True)
class Part:
    """Ein Körper eines 3MF-Builds, mit dem Ort, an den die Datei ihn setzt."""

    name: str
    mesh: MeshData
    slots: tuple[MaterialSlot, ...] = field(default_factory=tuple)
    solver: SolverInfo | None = None
    """Wie eine Aussparung abgezogen wurde (§17.2) — ``None``, wenn keine da
    war. Die ``load``-Operation meldet die tiefste Stufe aller Körper."""


def read_objects(payload: bytes, findings: list[Finding] | None = None) -> list[Part]:
    """Jeder Körper, den der Build platziert, jeder dort, wohin die Datei ihn
    setzt.

    ``findings`` nimmt auf, was der Leser nicht übernehmen konnte oder
    stillschweigend entschieden hätte: Farben, die einfarbig wurden, ein
    Hilfsteil des Slicers, das keine Geometrie ist, eine Aussparung, die
    abgezogen wurde. Wer die Liste nicht mitgibt, bekommt die Körper trotzdem
    — die Auskunft steht dann nur im Protokoll.

    Eine leere Liste heißt: das ist keine 3MF, die sich hier lesen lässt — der
    Aufrufer fällt auf den allgemeinen Loader zurück, statt für eine Datei eine
    Ausnahme zu bekommen, die ein anderer Leser durchaus schaffen mag.

    Ein Körper je Blatt-Mesh, nicht einer je Build-Element. Ein Slicer packt
    eine Baugruppe als ein Element aus Komponenten, und diese Komponenten
    *sind* die einzelnen Teile: Gehäuse, Deckel, Tülle, Liner. Sie als einen
    verschweißten Körper zu übergeben würfe genau die Teilung weg, die sie
    einzeln druckbar macht — und es ist die Teilung, die das Projekt ohnehin
    braucht, für sein eigenes Material je Körper (§12) und seine eigene
    Platte (§25).
    """
    # Träge, aus demselben Grund wie in ``_carved``: Ohne Aussparung braucht
    # der Leser den Rechenkern nicht.
    from app.core.geom.boolean import deepest

    noted = findings if findings is not None else []
    leaves = _leaves(payload, noted)

    # Aussparungen zuerst, je Objekt gesammelt: Sie gehören zu jedem
    # druckbaren Teil desselben Objekts, und die Reihenfolge der Blätter
    # sagt nicht, welches zuerst kommt.
    cutters: dict[str, list[tuple[str, trimesh.Trimesh]]] = {}
    for leaf in leaves:
        if leaf.kind != NEGATIVE_KIND:
            continue
        body = _mesh_from(leaf.node)
        if body is None:
            continue
        moved = body.raw.copy()
        transform.moved(moved, leaf.transform)
        cutters.setdefault(leaf.owner, []).append((leaf.name, moved))
    carved: set[str] = set()

    parts: list[Part] = []
    skipped = 0
    effective: set[tuple[str, str]] = set()
    for leaf in leaves:
        if leaf.kind == NEGATIVE_KIND:
            continue
        if not _is_body(leaf.kind):
            skipped += 1
            _log.info("3MF part %r is a slicer %s — not a body", leaf.name, leaf.kind)
            noted.append(
                Finding(
                    code="ingest.helper_skipped",
                    severity="info",
                    message=_(
                        "„{name}“ ist ein Hilfsteil des Slicers ({kind}) und keine Geometrie "
                        "des Drucks — es wurde nicht geladen.",
                        name=leaf.name,
                        kind=HELPER_TITLES[leaf.kind],
                    ),
                    values={"name": leaf.name, "kind": HELPER_TITLES[leaf.kind]},
                )
            )
            continue
        if leaf.kind != "normal_part":
            _log.info(
                "3MF part %r has the unknown kind %s — loaded as a body", leaf.name, leaf.kind
            )
            noted.append(
                Finding(
                    code="ingest.unknown_part_kind",
                    severity="info",
                    message=_(
                        "„{name}“ ist ein Teil der Art „{kind}“, die Solidon nicht kennt — es "
                        "wurde als Körper geladen.",
                        name=leaf.name,
                        kind=leaf.kind,
                    ),
                    values={"name": leaf.name, "kind": leaf.kind},
                )
            )
        body = _mesh_from(leaf.node)
        if body is None:
            continue
        raw = body.raw
        groups: Groups | None = None
        try:
            native = _native_tools_of(leaf)
            if native is not None:
                tools = native.tools
                if native.splits:
                    # Erst teilen, dann bewegen: Die Mittelpunkte sind in
                    # jeder Lage dieselben, und die Kopie unten nimmt das
                    # Netz, das die Bemalung tragen kann.
                    raw, tools = _refine(raw, tools, native.splits, leaf.name)
                groups = _groups_from(tools, native.palette)
        except _ForeignVolumeError as problem:
            _log.warning("3MF body %r carries a %s volume: %s", leaf.name, problem.kind, problem)
            raw = body.raw
            noted.append(
                Finding(
                    code="ingest.foreign_volume",
                    severity="warning",
                    message=_(
                        "„{name}“ trägt einen Bereich, den der Slicer als „{kind}“ führt — er "
                        "ist als Material des Körpers geladen, und die Farben wurden nicht "
                        "übernommen.",
                        name=leaf.name,
                        kind=problem.kind,
                    ),
                    values={"name": leaf.name, "kind": problem.kind},
                )
            )
        except _MaterialError as problem:
            _log.warning("3MF body %r keeps one colour: %s", leaf.name, problem)
            raw = body.raw
            noted.append(_colours_dropped(leaf.name, problem.reason))
        if groups is None:
            groups = _groups_of(leaf.node, leaf.palette, leaf.pid, leaf.pindex)
        moved = raw.copy()
        transform.moved(moved, leaf.transform)
        mesh = (
            MeshData(raw=moved, slots=groups.slots) if groups is not None else body.replacing(moved)
        )
        solver: SolverInfo | None = None
        for cutter_name, cutter in cutters.get(leaf.owner, ()):
            mesh, cut, touched = _carved(mesh, leaf.name, cutter_name, cutter, noted)
            carved.add(leaf.owner)
            if touched:
                effective.add((leaf.owner, cutter_name))
            if cut is not None:
                solver = deepest((solver, cut))
        parts.append(
            Part(
                name=leaf.name,
                mesh=mesh,
                slots=tuple(groups.materials) if groups else (),
                solver=solver,
            )
        )

    for owner, tools_of in cutters.items():
        for cutter_name, _cutter in tools_of:
            if owner in carved and (owner, cutter_name) not in effective:
                # Ein Objekt hat druckbare Teile, und die Aussparung trifft
                # keines: Im Slicer schneidet sie dort ebenso wenig. Gesagt
                # wird es trotzdem — es ist die eine Stelle, an der der
                # Leser sonst schweigend entschiede (Regel 21).
                noted.append(
                    Finding(
                        code="ingest.negative_without_effect",
                        severity="info",
                        message=_(
                            "Die Aussparung „{cutter}“ trifft keinen Körper — sie hat keine "
                            "Wirkung.",
                            cutter=cutter_name,
                        ),
                        values={"cutter": cutter_name},
                    )
                )
            if owner in carved:
                continue
            noted.append(
                Finding(
                    code="ingest.negative_orphaned",
                    severity="warning",
                    message=_(
                        "Die Aussparung „{name}“ gehört zu keinem druckbaren Körper und wurde "
                        "nicht geladen.",
                        name=cutter_name,
                    ),
                    values={"name": cutter_name},
                )
            )

    if not parts and (cutters or skipped):
        # **Nicht leer zurückgeben.** Eine leere Liste heißt für den Aufrufer
        # „keine 3MF, die sich hier lesen lässt", und er fällt auf den
        # allgemeinen Leser zurück — der kennt keine Teilarten und lüde die
        # Aussparung als Körper, neben dem Befund, sie sei nicht geladen.
        raise ValidationError(
            field="file",
            detail=_(
                "Die Datei enthält nur Hilfsteile oder Aussparungen des Slicers und keinen "
                "druckbaren Körper."
            ),
            constraint="no_printable_part",
            values={"skipped": skipped + sum(len(entries) for entries in cutters.values())},
            suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
        )
    _log.info("read %d part(s) from a 3MF build", len(parts))
    return _numbered(parts)


def _colours_dropped(name: str, reason: TranslatableText | str) -> Finding:
    """Der Befund, der aus dem früheren Abbruch wurde: derselbe Grund,
    derselbe Rat — nur dass der Körper jetzt da ist.

    **Der Rat steht im Satz, nicht in ``suggestions``.** Der Prüfbericht
    zeigt nur Handlungen, für die das Fenster einen Handler hat
    (``panels.actions_for_document`` … ``if action.id in handlers``), und
    für „im Slicer nach Filamenten aufteilen" gibt es keinen — den Text
    zum Lesen kennt nur der Fehlerdialog (``dialogs.unhandled_advice``). Als
    Vorschlag angehängt kam der Rat also nie an (Review, 14.09.2026).
    """
    return Finding(
        code="ingest.colours_dropped",
        severity="warning",
        message=_(
            "Die Farben von „{name}“ wurden nicht übernommen: {reason}. Der Körper ist "
            "einfarbig geladen — im Slicer nach Filamenten in einzelne Körper aufgeteilt und "
            "neu exportiert kommen die Farben mit.",
            name=name,
            reason=reason,
        ),
        values={"name": name, "reason": reason},
    )


def _carved(
    mesh: MeshData, name: str, cutter_name: str, cutter: trimesh.Trimesh, noted: list[Finding]
) -> tuple[MeshData, SolverInfo | None, bool]:
    """Zieht eine Aussparung des Slicers vom Körper ab — wie der Slicer es
    beim Slicen täte, und wie die Datei den Körper zeigt. Zurück kommt das
    Netz, die Stufe, die es gerechnet hat (``None``, wenn nichts geschnitten
    wurde), und ob die Aussparung diesen Körper überhaupt berührt hat — ein
    gescheiterter Schnitt hat ihn berührt, ein wirkungsloser nicht.

    Ein ``negative_part`` ist keine eigene Geometrie des Drucks, sondern eine
    Anweisung an das Objekt daneben: Bambu Studio und Orca rechnen die
    Differenz beim Slicen. Als eigener Körper geladen stünde er als Klotz im
    Modell, weggelassen fehlte das Loch. Gerechnet wird über die Rückfallkette
    des Kerns; scheitert sie, bleibt der Körper, wie er war, und der Befund
    sagt es — die Körperzahl steht nämlich fest, bevor irgendetwas gerechnet
    ist (:func:`_scan`), und ein Werkzeug, das als Ersatz auftauchte, brächte
    sie durcheinander.
    """
    # Erst hier geholt: ``boolean`` zieht ``manifold3d`` nach, und der
    # Leser soll ohne Rechenkern importierbar bleiben, solange keine Datei
    # eine Aussparung trägt.
    from app.core.geom.boolean import boolean, without_effect

    try:
        outcome = boolean("difference", [mesh, MeshData.of(cutter)], allow_empty=True)
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # Kerne scheitern auf kerneigene Arten
        _log.warning(
            "3MF negative part %r could not be cut from %r: %s", cutter_name, name, problem
        )
        # Der Ausweg des Rechenkerns reist mit: ``BooleanFailedError`` sagt,
        # ob Maße oder Netz das Problem sind, und der Prüfbericht zeigt seine
        # Handlungen (Regel 17).
        noted.append(
            Finding(
                code="ingest.negative_kept_out",
                severity="warning",
                message=_(
                    "Die Aussparung „{cutter}“ ließ sich nicht von „{name}“ abziehen — der "
                    "Körper ist ohne sie geladen.",
                    cutter=cutter_name,
                    name=name,
                ),
                values={"cutter": cutter_name, "name": name, "detail": str(problem)},
                suggestions=tuple(problem.suggestions) if isinstance(problem, AppError) else (),
            )
        )
        return mesh, None, True
    if outcome.mesh.triangle_count == 0:
        _log.warning("3MF negative part %r covers all of %r — not cut", cutter_name, name)
        noted.append(
            Finding(
                code="ingest.negative_kept_out",
                severity="warning",
                message=_(
                    "Die Aussparung „{cutter}“ deckt „{name}“ ganz — sie wurde nicht abgezogen.",
                    cutter=cutter_name,
                    name=name,
                ),
                values={"cutter": cutter_name, "name": name},
            )
        )
        return mesh, None, True
    if without_effect(mesh, outcome.mesh, "difference") is not None:
        # Ein Objekt aus mehreren Teilen: Die Aussparung gilt allen, trifft
        # aber nur eines. Die anderen behalten ihr Netz, wie es ankam — und
        # bekommen keinen Befund über einen Schnitt, der keiner war.
        _log.info("3MF negative part %r does not touch %r", cutter_name, name)
        return mesh, None, False
    # Die Befunde der Kette kommen mit — „verschweißt", „verwackelt", „auf
    # dem Raster" — und die Stufe steht am Befund: Stufe 4 vernetzt den
    # ganzen Körper neu, und das läuft nie stillschweigend (§17.2).
    noted.extend(outcome.findings)
    noted.append(
        Finding(
            code="ingest.negative_carved",
            severity="info",
            message=_(
                "Die Aussparung „{cutter}“ wurde von „{name}“ abgezogen.",
                cutter=cutter_name,
                name=name,
            ),
            values={"cutter": cutter_name, "name": name, "solver": outcome.solver.strategy},
        )
    )
    return outcome.mesh, outcome.solver, True


#: Wie der 3MF-Kern seine Einheiten nennt. Sechs Namen, und zwei davon kann
#: der Kern nicht als Einheit führen (§11.1) — sie sind trotzdem gültig, und
#: eine Datei in Mikrometern gibt es.
#:
#: Vorgabe des Formats ist Millimeter; steht kein Attribut da, gilt sie. Wir
#: nehmen sie trotzdem nicht an, sondern melden „nichts angegeben": Die
#: Vorgabe stimmt für eine Datei, die den Standard kennt, und wer sein
#: ``unit`` weglässt, hat ihn meist nicht gelesen. Dann ist die Frage besser
#: als die Annahme (Regel 21).
THREEMF_UNITS: Final[tuple[str, ...]] = (
    "micron",
    "millimeter",
    "centimeter",
    "inch",
    "foot",
    "meter",
)


def declared_unit(payload: bytes) -> str | None:
    """Die Einheit, die eine 3MF selbst nennt — oder ``None``.

    STL kennt keine Einheit, 3MF schon: Sie steht im ``unit``-Attribut des
    ``model``-Elements, und damit ist die Frage aus §17.1 für dieses Format
    beantwortet, bevor sie gestellt wird.

    Gelesen wird nur der Wurzelknoten. Der Rest der Datei kann dreihundert
    Megabyte Koordinaten sein, und für ein Attribut am Anfang lohnt es nicht,
    sie anzufassen — ``iterparse`` liest häppchenweise, und beim ersten
    Element ist Schluss.

    ``None`` heißt: kein Attribut, ein unbekannter Name oder eine Datei, die
    sich nicht öffnen lässt. In allen drei Fällen wird gefragt statt geraten.
    """
    try:
        with zipfile.ZipFile(BytesIO(payload)) as container, container.open(MODEL_PATH) as stream:
            for _event, element in ET.iterparse(stream, events=("start",)):
                stated = (element.get("unit") or "").strip().lower()
                return stated if stated in THREEMF_UNITS else None
    except KeyError, OSError, zipfile.BadZipFile, ET.ParseError, NotImplementedError:
        return None
    return None


#: Die zwei Teilbäume, die eine Modelldatei schwer machen: je ein Kind pro Ecke
#: und pro Dreieck. Die Struktur darüber — Objekt, Mesh-Hülle, Komponenten,
#: Build — ist klein.
_VERTICES_TAG: Final = f"{{{CORE_NAMESPACE}}}vertices"
_TRIANGLES_TAG: Final = f"{{{CORE_NAMESPACE}}}triangles"
#: Die Kinder der beiden Sammelknoten — sie werden gezählt, nicht gebaut.
_VERTEX_TAG: Final = f"{{{CORE_NAMESPACE}}}vertex"
_TRIANGLE_TAG: Final = f"{{{CORE_NAMESPACE}}}triangle"

#: Wie viele Kinder ein geleerter Teilbaum hatte. Kein Attribut des Formats: Es
#: steht nur in dem Baum, den :func:`_model_without_geometry` baut, und lebt
#: nicht länger als er. Geschrieben wird es, weil der Scan sonst nicht
#: unterscheiden kann, ob ein ``mesh`` leer war oder nur ausgeräumt wurde.
_SCANNED_COUNT: Final = "solidon-scanned-count"


def _model_without_geometry(container: zipfile.ZipFile, entry: str) -> tuple[ET.Element, int]:
    """Eine Modelldatei als Baum ohne ihre Koordinaten, dazu die Zahl ihrer
    Dreiecke.

    ``ET.iterparse`` liest häppchenweise, und jeder ``vertices``/``triangles``-
    Teilbaum wird geleert, sobald er geschlossen ist: Die Objekt- und
    Build-Struktur bleibt vollständig — :func:`_objects_in` und :func:`_parts_of`
    sehen ohnehin nie hinein —, die Millionen Ecken und Dreiecke fallen weg. So
    bleibt der Spitzenspeicher bei einem einzelnen Block statt bei der ganzen
    Datei; ``ET.fromstring`` dagegen hob das gesamte XML in ET.Element-Objekte,
    rund das Zwölffache der entpackten Größe.

    Was das Leeren mitnähme, bleibt als Zahl stehen (:data:`_SCANNED_COUNT`) —
    :func:`_carries_geometry` fragt danach.
    """
    builder = _StructureOnly()
    parser = ET.XMLParser(target=builder)
    with container.open(entry) as stream:
        while chunk := stream.read(1 << 20):
            parser.feed(chunk)
    root = parser.close()
    if root is None:
        raise ET.ParseError("model file without a root element")
    return root, builder.triangles


class _StructureOnly:
    """Ein Parserziel, das die Struktur baut und die Geometrie nur zählt.

    **Warum nicht mehr ``iterparse``.** Der baute für jedes Element ein
    ``ET.Element`` — auch für jedes der Millionen Dreiecke und Ecken, die eine
    Zeile später wieder geleert wurden. Gemessen am 03.09.2026 an einer 3MF mit
    5 476 596 Dreiecken in 28 Modelldateien (463 MB entpackt):

        iterparse            21,3 s
        dieses Ziel           7,1 s

    Der Unterschied ist nicht das Parsen, sondern der Objektbau: Was gar nicht
    erst entsteht, muss auch nicht geleert werden.

    Gebaut wird alles außer ``triangle`` und ``vertex``; die zählt es. Die
    beiden Sammelknoten bekommen ihre Zahl als Attribut, genau wie vorher —
    :func:`_carries_geometry` fragt danach, und ohne sie hielte es jedes Mesh
    für leer.
    """

    __slots__ = ("_depth", "_inner", "_seen", "triangles")

    def __init__(self) -> None:
        self._inner = ET.TreeBuilder()
        self._depth = 0
        """Wie tief wir in einem übersprungenen Teilbaum stehen."""
        self._seen = 0
        """Die Kinder des offenen Sammelknotens."""
        self.triangles = 0

    def start(self, tag: str, attrs: dict[str, str]) -> None:
        if tag in (_TRIANGLES_TAG, _VERTICES_TAG):
            self._seen = 0
        elif tag in (_TRIANGLE_TAG, _VERTEX_TAG):
            self._seen += 1
            if tag == _TRIANGLE_TAG:
                self.triangles += 1
            self._depth += 1
            return
        if self._depth:
            self._depth += 1
            return
        self._inner.start(tag, attrs)

    def end(self, tag: str) -> None:
        if self._depth:
            self._depth -= 1
            return
        element = self._inner.end(tag)
        if tag in (_TRIANGLES_TAG, _VERTICES_TAG):
            element.set(_SCANNED_COUNT, str(self._seen))

    def data(self, text: str) -> None:
        # Text innerhalb der Geometrie gibt es nicht, und was es gäbe, wollen
        # wir nicht: Millionen leere Zeichenketten sind derselbe Aufwand, den
        # dieses Ziel gerade spart.
        if not self._depth:
            self._inner.data(text)

    def close(self) -> ET.Element:
        return self._inner.close()


def _carries_geometry(mesh_node: ET.Element) -> bool:
    """Ob ein ``mesh``-Knoten Ecken **und** Dreiecke hat.

    Die Vorprüfung von :func:`_mesh_from`, aber ohne eine einzige Koordinate zu
    lesen — der Scan muss dieselbe Antwort geben wie der Leser, sonst verspricht
    er dem Stapel einen Körper, den es nicht gibt (§11).

    Sie deckt, was ohne die Zahlen entscheidbar ist: fehlender oder leerer
    Teilbaum. Was erst an den Werten auffällt — ein Index außerhalb der
    Eckenliste, unlesbare Koordinaten — bleibt dem Leser; solche Dateien sind
    kaputt und nicht bloß leer.
    """
    return _entries_in(mesh_node, _VERTICES_TAG) > 0 and _entries_in(mesh_node, _TRIANGLES_TAG) > 0


def _entries_in(mesh_node: ET.Element, tag: str) -> int:
    """Wie viele Kinder ein Teilbaum hat — auch wenn der Scan ihn geleert hat."""
    found = mesh_node.find(tag)
    if found is None:
        return 0
    return len(found) or int(found.get(_SCANNED_COUNT) or 0)


def _silent_scan(fraction: float, text: str) -> None:
    """Der Vorgabewert: Wer keinen Fortschritt will, bekommt keinen.

    Dieselbe Form wie ``loader._silent`` — eine Funktion statt ``None``, damit
    die Zählschleife nicht bei jedem Schritt fragen muss, ob sie melden darf.
    """


def _scan(payload: bytes, progress: ProgressFn = _silent_scan) -> tuple[int, int]:
    """Zählt Körper und Dreiecke einer Baugruppe, ohne eine Koordinate in den
    Speicher zu heben.

    Zwei Fragen stehen vor der Geometrie: Wie viele Objekt-IDs vergibt der
    Stapel (§11), und passt die Datei überhaupt in den Speicher (§32)? Beide
    beantwortet ein streamender Lauf. Die Körper werden über dieselben
    :func:`_objects_in`/:func:`_parts_of` gezählt wie beim Lesen, damit die Zahl
    garantiert die ist, die :func:`read_objects` zurückgäbe. Die Dreiecke fallen
    beim Streamen ab und decken **alle** Modelldateien ab, auch die vom Build
    nicht erreichten — der Vollparse in :func:`read_objects` liest sie ebenso,
    und der Speicher, der ihn sprengt, hängt an ihrer Gesamtzahl.
    """
    try:
        with zipfile.ZipFile(BytesIO(payload)) as container:
            names = set(container.namelist())
            if MODEL_PATH not in names:
                return 0, 0
            triangles = 0
            models: dict[str, ET.Element] = {}
            # **Erst die Liste, dann der Lauf** — und zwar wegen des
            # Fortschritts: Wer eine Schleife mit ``continue`` filtert, kennt
            # ihre Länge nicht und kann keinen Bruchteil melden. Eine große
            # Baugruppe bringt es hier auf 28 Dateien, und das Zählen dauert
            # bei 5,5 Millionen Dreiecken vierzehn Sekunden (§2.8).
            geometry = [
                entry
                for entry in sorted(names)
                if entry != MODEL_PATH
                and entry.startswith("3D/Objects/")
                and entry.endswith(".model")
            ]
            for index, entry in enumerate([MODEL_PATH, *geometry]):
                progress(index / (len(geometry) + 1), str(_("Modell wird gelesen")))
                models[entry], found = _model_without_geometry(container, entry)
                triangles += found
            settings = (
                _settings(container.read(SETTINGS_PATH)) if SETTINGS_PATH in names else _Settings()
            )
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as problem:
        _log.info("3MF could not be scanned as an assembly: %s", problem)
        return 0, 0
    except (NotImplementedError, RuntimeError) as problem:
        # Wie :func:`_leaves`: anders gepackt (Deflate64, AES) ist kein kaputtes
        # Archiv, sondern eine eigene Auskunft mit eigenem Ausweg — kein stummes
        # (0, 0), das die Datei als leer ausgäbe (§32, Regel 17).
        raise _unpackable(problem) from problem

    catalog = {path: _objects_in(model) for path, model in models.items()}
    # Für das Zählen zählt die Palette nicht — _parts_of legt sie nur ab.
    without_palette: dict[str, dict[str, list[tuple[str, tuple[float, float, float]]]]] = {
        path: {} for path in models
    }
    bodies = 0
    budget = _Budget()
    for item in models[MODEL_PATH].findall(f"{{{CORE_NAMESPACE}}}build/{{{CORE_NAMESPACE}}}item"):
        identifier = item.get("objectid")
        if identifier is None:
            continue
        for leaf in _parts_of(
            identifier,
            _inside(item.get(f"{{{PRODUCTION_NAMESPACE}}}path")),
            _matrix(item.get("transform")),
            catalog,
            without_palette,
            settings,
            item.get("name") or settings.titles.get(identifier, ""),
            0,
            budget,
        ):
            # Ein Mesh ohne Dreiecke ist kein Körper. Gezählt wurde es
            # trotzdem, und der Leser überging es — der Stapel bekam damit eine
            # Objekt-ID zu viel, die Auswertung hielt mit
            # ``evaluate.object_count`` an, und aus einer Datei mit einem
            # lesbaren Körper wurde ein Import, der gar nichts einlas.
            #
            # Dasselbe für die Teile, aus denen der Leser keinen Körper macht:
            # Ein Hilfsteil wird übersprungen, eine Aussparung abgezogen.
            if not _is_body(leaf.kind):
                _log.info("3MF part %r is a slicer %s — not counted", leaf.name, leaf.kind)
            elif _carries_geometry(leaf.node):
                bodies += 1
            else:
                _log.warning("3MF body %r has no geometry — not counted", leaf.name)
    # Gespeichert **oder** instanziert, was größer ist: Das Parsen kostet die
    # gespeicherten Dreiecke, die Körper danach die instanzierten — und ein
    # Blatt, das der Build zehnmal erreicht, liegt zehnmal im Speicher.
    return bodies, max(triangles, budget.triangles)


def scan_assembly(payload: bytes, progress: ProgressFn = _silent_scan) -> tuple[int, int]:
    """(Zahl der Körper, Zahl der Dreiecke) einer 3MF — streamend, ohne
    Koordinaten im Speicher.

    Die Körperzahl braucht der Stapel für die Objekt-IDs (§11), die Dreieckzahl
    die Größengrenze: Sie geht an ``check_limits``, **bevor** ``read_objects``
    das ganze XML in den Speicher hebt. Beides in einem Lauf, damit die Datei
    nur einmal durchläuft.
    """
    return _scan(payload, progress)


def count_objects(payload: bytes) -> int:
    """Wie viele Körper :func:`read_objects` zurückgäbe.

    Der Stapel vergibt Objekt-IDs, bevor irgendetwas gerechnet ist (§11) — die
    Anzahl muss also bekannt sein, bevor es die Geometrie ist, und ohne ein
    einziges Dreieck in den Speicher zu heben (:func:`_scan`).
    """
    return _scan(payload)[0]


@dataclass(frozen=True, slots=True)
class _Leaf:
    """Ein Mesh, das der Build erreicht, und alles, was unterwegs über es
    bekannt wurde.
    """

    name: str
    node: ET.Element
    transform: np.ndarray
    palette: dict[str, list[tuple[str, tuple[float, float, float]]]]
    pid: str = ""
    """Die Materialgruppe, die das **Objekt** nennt. Ein Dreieck ohne eigene
    Angabe gehört ihr — ohne sie las jeder Körper aus der ersten Gruppe der
    Datei, auch wenn er auf eine andere zeigte."""
    pindex: int = 0
    """Und die Stelle darin. Bei einem einfarbigen Körper steht die Farbe
    genau hier und an keinem einzigen Dreieck."""
    native: _NativeMaterials | None = None
    tool: int | None = None
    volumes: tuple[tuple[int, int, int], ...] = ()
    owner: str = ""
    """Das Objekt des Builds, zu dem dieses Blatt gehört — die Klammer, in
    der eine Aussparung ihre Körper findet."""
    identifier: str = ""
    """Die eigene Objekt-ID des Blatts. PrusaSlicer notiert seine
    Werkzeuge unter ihr, nicht unter dem Build-Objekt darüber."""
    kind: str = "normal_part"
    """Was der Slicer aus dem Teil macht: ein druckbares Teil, eine
    Aussparung (:data:`NEGATIVE_KIND`) oder ein Hilfsteil
    (:data:`HELPER_KINDS`)."""


@dataclass(frozen=True, slots=True)
class _NativeAssignment:
    """Was die Slicer-Metadaten einem Körper zuweisen: ein Werkzeug je
    Dreieck der Datei, dazu die Dreiecke, die der Slicer beim Bemalen
    geteilt hat — für die steht in ``tools`` das Werkzeug, das ihre erbenden
    Teile bekommen, und in ``splits`` der Baum, den :func:`_refine` in
    Geometrie übersetzt.
    """

    tools: list[int]
    splits: dict[int, _PaintSplit]
    palette: tuple[MaterialSlot, ...]


def _native_tools_of(leaf: _Leaf) -> _NativeAssignment | None:
    """Werkzeug je Dreieck aus Objekt, Teil, Prusa-Bereich und Bemalung —
    oder ``None``, wenn die Datei zu diesem Körper nichts davon sagt.
    """
    if leaf.native is None:
        return None
    # Unter beiden Kennungen, wie ``volumes`` und ``parts`` daneben: Bambu
    # und Orca führen das Build-Objekt, PrusaSlicer das Mesh-Objekt selbst
    # — und in einer Datei, die beides trennt, lag das Problem unter der
    # einen und wurde unter der anderen gesucht (Review, 14.09.2026).
    for key in (leaf.owner, leaf.identifier):
        if key in leaf.native.troubles:
            raise leaf.native.troubles[key]
    triangles = leaf.node.findall(f".//{{{CORE_NAMESPACE}}}triangle")
    stated: list[tuple[str, ...]] = [
        tuple(
            code
            for code in (
                face.get("paint_color"),
                face.get(f"{{{PRUSA_NAMESPACE}}}mmu_segmentation"),
            )
            if code
        )
        for face in triangles
    ]
    if not any(stated) and leaf.tool is None and not leaf.volumes:
        return None
    base: list[int | None] = [leaf.tool] * len(triangles)
    covered: set[int] = set()
    for first, last, range_tool in leaf.volumes:
        if first < 0 or last < first or last >= len(triangles):
            raise _unsupported_materials(_("Dreiecksbereich liegt außerhalb des Netzes"))
        for index in range(first, last + 1):
            if index in covered:
                raise _unsupported_materials(_("Überlappende Dreiecksbereiche"))
            covered.add(index)
            base[index] = range_tool
    # Ein Code je Dreieck, aber nur wenige verschiedene: 744 429 bemalte
    # Dreiecke einer Datei trugen 3 126 verschiedene Codes, und 739 168 davon
    # denselben. Dekodiert wird deshalb je Code, nicht je Dreieck.
    trees: dict[str, _PaintNode] = {}
    tools: list[int] = []
    splits: dict[int, _PaintSplit] = {}
    for index, codes in enumerate(stated):
        tool: int | None = base[index]
        nodes: list[_PaintNode] = []
        for code in codes:
            if code not in trees:
                trees[code] = _decode_paint(code)
            nodes.append(trees[code])
        if len(set(nodes)) > 1:
            raise _unsupported_materials(_("Widersprüchliche Farbzuordnungen auf derselben Fläche"))
        if nodes:
            node = nodes[0]
            if isinstance(node, _PaintSplit):
                splits[index] = node
            else:
                painted = _leaf_tool(node)
                if painted is not None:
                    tool = painted
        # Native Slicer geben einem nicht zugewiesenen Objekt Werkzeug 1.
        tools.append(0 if tool is None else tool)
    return _NativeAssignment(tools, splits, leaf.native.palette)


def _groups_from(tools: list[int], palette: tuple[MaterialSlot, ...]) -> Groups:
    """Lokale Slots aus Werkzeugnummern: benutzt wird numeriert ab null, die
    Palette liefert Namen und Farben.
    """
    if any(tool < 0 or tool >= len(palette) for tool in tools):
        raise _unsupported_materials(_("Werkzeugnummer außerhalb der Filamentpalette"))
    used = sorted(set(tools))
    order = {tool: index for index, tool in enumerate(used)}
    return Groups(
        slots=tuple(order[tool] for tool in tools),
        materials=tuple(
            dataclasses.replace(palette[tool], index=index) for index, tool in enumerate(used)
        ),
    )


def _refine(
    mesh: trimesh.Trimesh, tools: list[int], splits: dict[int, _PaintSplit], name: str
) -> tuple[trimesh.Trimesh, list[int]]:
    """Teilt die bemalten Dreiecke so, wie der Slicer sie geteilt hat, und
    gibt jedem Teil sein Werkzeug.

    Der Slicer halbiert Seiten an ihrer Mitte und hängt an jedes Kind
    dieselbe Regel — die Geometrie ändert sich dabei nicht, nur ihre
    Zerlegung. Die Eckenmuster der drei Fälle stehen in
    ``TriangleSelector::perform_split``, und sie stehen hier genauso:

    * eine Seite: die gegenüber der besonderen Ecke, zwei Kinder
    * zwei Seiten: die **behaltene** liegt gegenüber, drei Kinder
    * drei Seiten: vier Kinder, das vierte in der Mitte

    **Ein Mittelpunkt gehört beiden Seiten einer Kante.** Er wird über die
    beiden Endpunkte gefunden, nicht neu gesetzt — sonst läge er zweimal im
    Netz, und ``manifold3d`` sähe eine offene Kante. Und wo nur eine Seite
    geteilt wurde, kennt die andere den Punkt nicht: Ein T-Stoß, den der
    Slicer beim Slicen selbst schließt (``get_facets_strict``). Hier schließt
    ihn der zweite Durchgang: Jedes Dreieck, auf dessen Kante ein bekannter
    Mittelpunkt liegt, wird dort geteilt, bis keiner mehr übrig ist. Beide
    Hälften tragen das Werkzeug des Ganzen; der Körper bleibt so dicht, wie
    er ankam.
    """
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    points: list[np.ndarray] = []
    midpoints: dict[tuple[int, int], int] = {}

    def point(index: int) -> np.ndarray:
        if index < len(vertices):
            return np.asarray(vertices[index])
        return points[index - len(vertices)]

    def midpoint(first: int, second: int) -> int:
        key = (first, second) if first < second else (second, first)
        found = midpoints.get(key)
        if found is None:
            found = len(vertices) + len(points)
            points.append((point(first) + point(second)) / 2.0)
            midpoints[key] = found
        return found

    split_faces: list[tuple[int, int, int]] = []
    split_tools: list[int] = []

    def expand(corners: tuple[int, int, int], node: _PaintNode, inherited: int) -> None:
        if isinstance(node, _PaintLeaf):
            split_faces.append(corners)
            painted = _leaf_tool(node)
            split_tools.append(inherited if painted is None else painted)
            return
        if node.special > 2:
            raise _unsupported_materials(_("Ungültige Flächenbemalung"))
        a, b, c = (corners[(node.special + offset) % 3] for offset in range(3))
        pieces: tuple[tuple[int, int, int], ...]
        if node.sides == 1:
            middle = midpoint(c, b)
            pieces = ((a, b, middle), (middle, c, a))
        elif node.sides == 2:
            ab, ca = midpoint(b, a), midpoint(a, c)
            pieces = ((a, ab, ca), (ab, b, ca), (b, c, ca))
        else:
            ab, bc, ca = midpoint(b, a), midpoint(c, b), midpoint(a, c)
            pieces = ((a, ab, ca), (ab, b, bc), (bc, c, ca), (ab, bc, ca))
        for piece, child in zip(pieces, node.children, strict=True):
            expand(piece, child, inherited)

    for index, tree in splits.items():
        a, b, c = (int(corner) for corner in faces[index])
        expand((a, b, c), tree, tools[index])

    kept = np.ones(len(faces), dtype=bool)
    kept[list(splits)] = False
    all_faces = np.vstack([faces[kept], np.array(split_faces, dtype=np.int64).reshape(-1, 3)])
    all_tools = np.concatenate([np.asarray(tools, dtype=np.int64)[kept], split_tools])

    # Der zweite Durchgang: Kanten mit einem bekannten Mittelpunkt. Erst
    # die Kandidaten — Dreiecke, die eine Ecke einer geteilten Kante tragen,
    # über ein Bool-Feld je Ecke —, dann die Schlüssel nur für sie: Ein
    # Schlüsselfeld über alle Dreiecke kostete an der Importgrenze ein
    # halbes Gigabyte je Zwischenfeld, für ein paar Tausend Treffer.
    total = len(vertices) + len(points)
    edge_keys = np.array(list(midpoints), dtype=np.int64).reshape(-1, 2)
    at_split_edge = np.zeros(total, dtype=bool)
    at_split_edge[edge_keys.ravel()] = True
    candidates = np.flatnonzero(at_split_edge[all_faces].any(axis=1))
    known = edge_keys[:, 0] * total + edge_keys[:, 1]
    corners = all_faces[candidates]
    ends = np.roll(corners, -1, axis=1)
    keys = np.minimum(corners, ends) * total + np.maximum(corners, ends)
    touched = np.zeros(len(all_faces), dtype=bool)
    touched[candidates[np.isin(keys, known).any(axis=1)]] = True

    closed_faces: list[tuple[int, int, int]] = []
    closed_tools: list[int] = []
    for face, tool in zip(all_faces[touched], all_tools[touched], strict=True):
        stack = [(int(face[0]), int(face[1]), int(face[2]))]
        while stack:
            a, b, c = stack.pop()
            for first, second, third in ((a, b, c), (b, c, a), (c, a, b)):
                middle = midpoints.get((first, second) if first < second else (second, first))
                if middle is not None:
                    stack.append((first, middle, third))
                    stack.append((middle, second, third))
                    break
            else:
                closed_faces.append((a, b, c))
                closed_tools.append(int(tool))

    # ``reshape``, weil eine leere Liste sonst die Form ``(0,)`` hätte und
    # ``vstack`` daran reißt — und leer ist sie, sobald der Slicer jede
    # Kante von beiden Seiten geteilt hat (gemessen: alle zwölf Dreiecke
    # einer Box dreifach, kein T-Stoß übrig).
    final_faces = np.vstack(
        [all_faces[~touched], np.array(closed_faces, dtype=np.int64).reshape(-1, 3)]
    )
    final_tools = [int(tool) for tool in all_tools[~touched]] + closed_tools
    _log.info(
        "3MF body %r: %d painted triangle(s) split into %d, %d T-joint(s) closed, %d triangles",
        name,
        len(splits),
        len(split_faces),
        len(closed_faces) - int(touched.sum()),
        len(final_faces),
    )
    return trimesh.Trimesh(
        vertices=np.vstack([vertices, np.array(points, dtype=np.float64)]),
        faces=final_faces,
        process=False,
    ), final_tools


def _leaves(payload: bytes, noted: list[Finding]) -> list[_Leaf]:
    """Läuft den Build ab und sammelt jedes Mesh, das er erreicht, der Reihe
    nach.

    ``noted`` bekommt den Befund, wenn die Filamentpalette der Datei nicht
    lesbar ist — dann kommen alle Körper ohne native Farben, aber sie kommen.
    """
    try:
        with zipfile.ZipFile(BytesIO(payload)) as container:
            names = set(container.namelist())
            if MODEL_PATH not in names:
                return []
            models = {MODEL_PATH: ET.fromstring(container.read(MODEL_PATH))}
            for entry in sorted(names):
                if entry.startswith("3D/Objects/") and entry.endswith(".model"):
                    models[entry] = ET.fromstring(container.read(entry))
            settings = (
                _settings(container.read(SETTINGS_PATH)) if SETTINGS_PATH in names else _Settings()
            )
            native: _NativeMaterials | None
            try:
                native = _native_materials(container, models[MODEL_PATH])
            except _MaterialError as problem:
                _log.warning("3MF filament palette not read, bodies keep one colour: %s", problem)
                native = None
                noted.append(
                    Finding(
                        code="ingest.palette_dropped",
                        severity="warning",
                        # Der Rat im Satz, aus demselben Grund wie bei
                        # ``_colours_dropped``.
                        message=_(
                            "Die Filamentpalette dieser 3MF ließ sich nicht lesen: {reason}. "
                            "Die Körper sind einfarbig geladen — im Slicer nach Filamenten in "
                            "einzelne Körper aufgeteilt und neu exportiert kommen die Farben mit.",
                            reason=problem.reason,
                        ),
                        values={"reason": problem.reason},
                    )
                )
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as problem:
        _log.info("3MF could not be read as an assembly: %s", problem)
        return []
    except (NotImplementedError, RuntimeError) as problem:
        # Kein Rückfall auf den allgemeinen Leser: Der scheitert am selben
        # Archiv und nennt es „vermutlich beschädigt" — ein Satz, der auf eine
        # heile Datei zeigt und in die falsche Richtung schickt.
        raise _unpackable(problem) from problem

    catalog = {path: _objects_in(model) for path, model in models.items()}
    materials = {path: _materials_in(model) for path, model in models.items()}

    found: list[_Leaf] = []
    budget = _Budget()
    for item in models[MODEL_PATH].findall(f"{{{CORE_NAMESPACE}}}build/{{{CORE_NAMESPACE}}}item"):
        identifier = item.get("objectid")
        if identifier is None:
            continue
        found.extend(
            _parts_of(
                identifier,
                _inside(item.get(f"{{{PRODUCTION_NAMESPACE}}}path")),
                _matrix(item.get("transform")),
                catalog,
                materials,
                settings,
                item.get("name") or settings.titles.get(identifier, ""),
                0,
                budget,
                native=native,
            )
        )
    return found


def _numbered(parts: list[Part]) -> list[Part]:
    """Hält Körper auseinander, die mit demselben Namen herauskamen.

    Siebzehn Teile einer Objektdatei teilen sich, wie auch immer das Objekt
    hieß, und ein Objektbaum mit siebzehn identischen Einträgen ist eine Liste,
    kein Baum.
    """
    seen: dict[str, int] = {}
    result: list[Part] = []
    counts = {part.name: 0 for part in parts}
    for part in parts:
        counts[part.name] += 1
    for part in parts:
        if counts[part.name] == 1:
            result.append(part)
            continue
        seen[part.name] = seen.get(part.name, 0) + 1
        result.append(dataclasses.replace(part, name=f"{part.name} {seen[part.name]}"))
    return result


@dataclass(frozen=True, slots=True)
class _Settings:
    """Was ``model_settings.config`` über die Teile sagt: ihre Namen und
    ihre Art.
    """

    titles: dict[str, str] = field(default_factory=dict)
    """Nach Objekt- und nach Part-ID."""
    kinds: dict[tuple[str, str], str] = field(default_factory=dict)
    """``(Objekt, Part) → subtype`` — nur, wo der Slicer einen nennt."""


def _settings(payload: bytes) -> _Settings:
    """Namen und Arten, die der Slicer notiert hat.

    Eine Part-ID ist das, was eine Komponente benennt — das Blatt bekommt also
    den Namen der Datei, die es einmal war, und das ist der Name, den jemand
    gewählt hat. Die Art (``subtype``) sagt, ob es überhaupt ein druckbares
    Teil ist; sie gilt je Objekt, denn dieselbe Part-ID kann in zwei
    Objekten zweierlei sein.
    """
    try:
        config = _slicer_config(payload)
    except ET.ParseError:
        return _Settings()

    found = _Settings()
    for node in [*config.findall(".//object"), *config.findall(".//part")]:
        identifier = node.get("id")
        if identifier is None:
            continue
        for entry in node.findall("metadata"):
            if entry.get("key") == "name" and entry.get("value"):
                found.titles[identifier] = _without_suffix(str(entry.get("value")))
                break
    for obj in config.findall("object"):
        for part in obj.findall("part"):
            kind = part.get("subtype")
            if kind and kind != "normal_part":
                found.kinds[obj.get("id", ""), part.get("id", "")] = kind
    return found


def _without_suffix(name: str) -> str:
    """``Wasserfall_4_TPU-Liner.stl`` ist ein Teil namens
    Wasserfall_4_TPU-Liner.
    """
    lowered = name.lower()
    for suffix in NAME_SUFFIXES:
        if lowered.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _parts_of(
    identifier: str,
    path: str,
    transform: np.ndarray,
    catalog: dict[str, dict[str, ET.Element]],
    materials: dict[str, dict[str, list[tuple[str, tuple[float, float, float]]]]],
    settings: _Settings,
    inherited: str,
    depth: int,
    budget: _Budget,
    seen: frozenset[tuple[str, str]] = frozenset(),
    native: _NativeMaterials | None = None,
    owner: str = "",
    tool: int | None = None,
) -> list[_Leaf]:
    """Die Meshes, die ein Objekt beiträgt, mit den Transformationen darüber
    angewandt.

    ``budget`` zählt jedes Blatt mit und hält an, sobald der Build mehr
    Körper oder Dreiecke instanziert, als die Anwendung trägt (:class:`_Budget`).
    """
    budget.visit()
    if depth > MAX_DEPTH:
        _log.warning("3MF component nesting deeper than %d — stopped", MAX_DEPTH)
        return []
    if (path, identifier) in seen:
        _log.warning("3MF object %s in %s refers back to itself — stopped", identifier, path)
        return []

    entry = catalog.get(path, {}).get(identifier)
    if entry is None:
        # Eine Komponente, die ein Objekt benennt, das niemand notiert hat. Die
        # ganze Datei darüber still fallenzulassen wäre schlimmer, als den
        # einen Körper fallenzulassen.
        _log.info("3MF references object %s in %s, which is not there", identifier, path)
        return []

    name = (
        entry.get("name")
        or settings.titles.get(identifier)
        or inherited
        or str(_("Körper {number}", number=identifier))
    )
    # Der Eigentümer ist das Objekt, das der Build nennt — die Klammer, in
    # der Part-IDs, Werkzeuge und Aussparungen gelten.
    if not owner:
        owner = identifier
        if native is not None:
            tool = native.objects.get(identifier, tool)
    if native is not None:
        tool = native.parts.get((owner, identifier), tool)
    mesh_node = entry.find(f"{{{CORE_NAMESPACE}}}mesh")
    if mesh_node is not None:
        budget.take(mesh_node)
        return [
            _Leaf(
                name=name,
                node=mesh_node,
                transform=transform,
                palette=materials.get(path, {}),
                pid=entry.get("pid") or "",
                pindex=_position(entry.get("pindex"), 0),
                native=native,
                tool=tool,
                volumes=tuple(native.volumes.get(identifier, ())) if native else (),
                owner=owner,
                identifier=identifier,
                kind=settings.kinds.get((owner, identifier), "normal_part"),
            )
        ]

    found: list[_Leaf] = []
    for component in entry.findall(f"{{{CORE_NAMESPACE}}}components/{{{CORE_NAMESPACE}}}component"):
        child = component.get("objectid")
        if child is None:
            continue
        # Der Pfad einer Komponente ist der Ort, an dem *ihr* Objekt lebt. Ohne
        # diese Zeile löst jede Komponente einer externen Datei zur ganzen Datei
        # auf — und das ist die Vervielfachung, für die es diesen Leser gibt.
        stated = component.get(f"{{{PRODUCTION_NAMESPACE}}}path")
        child_path = _inside(stated) if stated else path
        found.extend(
            _parts_of(
                child,
                child_path,
                transform @ _matrix(component.get("transform")),
                catalog,
                materials,
                settings,
                name,
                depth + 1,
                budget,
                seen | {(path, identifier)},
                native,
                owner,
                tool,
            )
        )
    return found


def _inside(path: str | None) -> str:
    """Ein Teilpfad, wie der Container ihn schreibt.

    Das Format schreibt sie absolut — ``/3D/Objects/lid.model`` — und ein ZIP
    hat keine Wurzel: der führende Schrägstrich muss also weg, sonst geht jede
    Suche daneben.
    """
    return (path or MODEL_PATH).lstrip("/")


def _objects_in(model: ET.Element) -> dict[str, ET.Element]:
    """Jedes Objekt einer Modelldatei, nach ID."""
    found: dict[str, ET.Element] = {}
    for entry in model.findall(f".//{{{CORE_NAMESPACE}}}object"):
        identifier = entry.get("id")
        if identifier is not None:
            found[identifier] = entry
    return found


def _mesh_from(node: ET.Element) -> MeshData | None:
    """Die Dreiecke eines ``mesh``-Knotens."""
    vertices = node.find(f"{{{CORE_NAMESPACE}}}vertices")
    triangles = node.find(f"{{{CORE_NAMESPACE}}}triangles")
    if vertices is None or triangles is None or not len(triangles):
        return None
    try:
        points, faces = _numbers_from(vertices, triangles)
    except (TypeError, ValueError) as problem:
        _log.info("3MF mesh has unreadable coordinates: %s", problem)
        return None
    # Ein Körper, der hier ausfällt, verschwindet aus der Baugruppe — und das
    # ist genau die Sorte Verlust, die niemandem auffällt: siebzehn Teile
    # kommen als sechzehn zurück, und keine Zeile sagt warum. Er wird deshalb
    # nicht bloß übersprungen, sondern benannt.
    if not len(points) or not len(faces):
        _log.warning("3MF mesh is empty: %d point(s), %d triangle(s)", len(points), len(faces))
        return None
    # Beide Grenzen, nicht nur die obere: Ein negativer Index bestand die
    # Prüfung auf die Eckenzahl und lief durch ``Trimesh(process=False)``, wo
    # numpy ihn nach hinten umschlägt — der Körper kam offen und mit falschem
    # Vorzeichen des Volumens zurück, benannt wurde die wahre Lage nie.
    if int(faces.min()) < 0 or int(faces.max()) >= len(points):
        _log.warning(
            "3MF mesh points outside its own vertices: index range %d..%d of %d point(s)",
            int(faces.min()),
            int(faces.max()),
            len(points),
        )
        return None
    return MeshData.of(trimesh.Trimesh(vertices=points, faces=faces, process=False))


def _numbers_from(vertices: ET.Element, triangles: ET.Element) -> tuple[np.ndarray, np.ndarray]:
    """Punkte und Dreiecke als Zahlenfelder — und einmal wiederholt, wenn nicht.

    Dieselbe Wunde wie bei :func:`app.core.geom.mesh.on_surface`, an der
    zweiten Stelle: Wer diese Datei dreißigmal im selben Prozess liest, bekommt
    sporadisch ``OverflowError``, ``SystemError`` oder — am hässlichsten — ein
    ``ValueError`` über eine Zeichenkette, die eine völlig gültige Zahl ist.
    Gemessen und eingegrenzt: es liegt weder am XML-Leser (``lxml`` verhält
    sich gleich) noch an der Art der Umwandlung, sondern am geladenen
    ``rtree`` — ohne es fällt die Rate von sechs auf eins von dreißig, mit
    seiner Version 1.4 stirbt der Prozess ganz.

    Ein zweiter Anlauf trägt fast immer. Er ist kein Verschlucken: was zweimal
    scheitert, fliegt weiter, und der Aufrufer verwirft den Körper dann mit
    einer Zeile im Protokoll statt schweigend.

    Seit dem 24.08.2026 ruft die Anwendung ``rtree`` nicht mehr auf
    (:func:`app.core.geom.mesh.on_surface` fragt einen eigenen Baum,
    ``ingest.outline`` verschachtelt über shapely) — die Rate sollte damit auf
    das Eins-von-Dreißig ohne ``rtree`` fallen. Der zweite Anlauf bleibt
    trotzdem: Er kostet nichts, solange nichts scheitert, und die Messung,
    dass ohne ``rtree`` *gar* nichts scheitert, gibt es nicht.
    """
    try:
        return _read_numbers(vertices, triangles)
    except (OverflowError, SystemError, ValueError) as stumble:
        _log.warning("3MF numbers came back damaged, reading them again: %s", stumble)
        return _read_numbers(vertices, triangles)


def _read_numbers(vertices: ET.Element, triangles: ET.Element) -> tuple[np.ndarray, np.ndarray]:
    points = np.array(
        [(entry.get("x"), entry.get("y"), entry.get("z")) for entry in vertices],
        dtype=np.float64,
    )
    faces = np.array(
        [(entry.get("v1"), entry.get("v2"), entry.get("v3")) for entry in triangles],
        dtype=np.int64,
    )
    return points, faces


#: Ein Dreieck zeigt mit ``pid`` auf eine Materialgruppe und mit ``p1`` auf
#: einen Eintrag darin. Beides zusammen ist der Schlüssel — nicht ``p1``
#: allein, denn Position 0 zweier Gruppen sind zwei verschiedene Filamente.
_Key = tuple[str, int]


def _groups_of(
    node: ET.Element,
    materials: dict[str, list[tuple[str, tuple[float, float, float]]]],
    pid: str = "",
    pindex: int = 0,
) -> Groups | None:
    """Die Farbgruppen eines Körpers — seine eigenen, nicht die der
    Datei (§20).

    ``pid`` und ``pindex`` sind, was das **Objekt** über sich sagt: seine
    Materialgruppe und seine Stelle darin. Ein Dreieck darf beides
    überschreiben; sagt es nichts, gilt das des Objekts.

    Drei Dinge gingen hier verloren, und alle drei an der eigenen Datei:

    * **Gezählt wird die Datei, nicht der einzelne Körper.** „Weniger als zwei
      benutzte Slots" galt als „keine Farbe". Eine zweifarbige Baugruppe
      besteht aber aus einfarbigen Teilen: Jedes Teil benutzt genau einen
      Slot, und die zwei Farben stehen *zwischen* den Teilen. Die eigene
      Ausgabe kam damit vollständig grau zurück. Führt die Datei nur ein
      einziges Material, bleibt es dabei — dann ist es die Vorgabe und keine
      Wahl.
    * **Eine fremde Gruppe ist eine eigene Gruppe.** Gelesen wurde nur die
      erste ``basematerials``-Gruppe der Datei; was auf eine andere zeigte,
      fiel still auf deren ersten Eintrag. Zwei Gruppen kamen einfarbig an.
    * **Jeder vergebene Slot hat einen Eintrag.** Was über die Materialliste
      hinauszeigte, wurde aus der Liste gestrichen — das Netz behielt seine
      Slotnummer, und die zeigte ins Leere.

    Was niemand benennt, bleibt dabei unbenannt: Ein Objekt ohne ``pid``,
    dessen Dreiecke ebenfalls schweigen, bekommt kein Material — auch nicht
    das erste der Datei.

    Bleibt der Fall, den auch diese Fassung nicht auflösen kann: ein ``pid``,
    das keine ``basematerials``-Gruppe benennt (eine Farbgruppe oder eine
    Textur aus einer Erweiterung). Solche Dreiecke bekommen das Material ihres
    Objekts — aber nicht mehr stillschweigend: Es steht im Protokoll, mit den
    Kennungen, um die es geht.
    """
    if not materials:
        return None
    triangles = _triangles_of(node)
    if not triangles:
        return None

    # Die Gruppe, die gilt, wenn ein Dreieck keine nennt.
    own = pid if pid in materials else next(iter(materials))
    # Ob überhaupt jemand ein Material benennt — das Objekt oder eines seiner
    # Dreiecke. Sagt keiner etwas, gehört der Körper zu keinem, auch wenn die
    # Datei daneben Materialien führt: Ihm das erste zuzuschreiben wäre
    # geraten (Regel 21).
    stated = pid in materials
    foreign: set[str] = set()
    assignment: list[_Key] = []
    for entry in triangles:
        group = entry.get("pid") or own
        stated = stated or bool(entry.get("pid") or entry.get("p1"))
        if group not in materials:
            foreign.add(group)
            assignment.append((own, pindex))
            continue
        assignment.append((group, _position(entry.get("p1"), pindex if group == own else 0)))
    if not stated:
        return None
    if foreign:
        _log.info(
            "3MF triangles point at %s, which is no material group — they take the "
            "material of their object",
            ", ".join(sorted(foreign)),
        )

    used = sorted(set(assignment))
    if len(used) < 2 and sum(len(entries) for entries in materials.values()) < 2:
        # **Eine Farbe, die die Datei nur einmal kennt, ist keine Zuordnung.**
        # Sie ist die Vorgabe — und aus ihr einen Materialslot zu machen hieße,
        # jedem einfarbigen Import einen Slot namens „Slot 0" anzuhängen, den
        # niemand gewählt hat.
        #
        # Führt die Datei dagegen **mehrere** Materialien, ist die Wahl eines
        # davon eine Aussage, auch wenn dieser Körper nur bei einem bleibt.
        # Genau das ging verloren: Eine zweifarbige Baugruppe besteht aus
        # einfarbigen Teilen, und die Bedingung sah nur den einzelnen Körper.
        return None
    order = {key: index for index, key in enumerate(used)}
    return Groups(
        slots=tuple(order[key] for key in assignment),
        materials=tuple(
            MaterialSlot(index=index, name=name, colour=colour)
            for index, (name, colour) in enumerate(_material_at(materials, key) for key in used)
        ),
    )


def _triangles_of(node: ET.Element) -> list[ET.Element]:
    """Die Dreiecke eines ``mesh``- oder ``object``-Knotens.

    Beide Leser kommen hier durch, und sie halten verschiedene Knoten in der
    Hand: :func:`read_objects` das Mesh, :func:`read` das Objekt darüber. Ohne
    diese Zeile bräuchte jede Seite ihre eigene Zuordnung — und die eine
    driftete von der anderen weg, was sie zweimal getan hat.
    """
    mesh = node.find(f"{{{CORE_NAMESPACE}}}mesh")
    inside = mesh if mesh is not None else node
    return inside.findall(f"{{{CORE_NAMESPACE}}}triangles/{{{CORE_NAMESPACE}}}triangle")


def _position(text: str | None, fallback: int) -> int:
    """Die Stelle in einer Materialgruppe. Was keine Zahl ist, ist keine
    Angabe.
    """
    try:
        return int(text) if text else fallback
    except ValueError:
        return fallback


def _material_at(
    materials: dict[str, list[tuple[str, tuple[float, float, float]]]], key: _Key
) -> tuple[str, tuple[float, float, float]]:
    """Name und Farbe zu einer Stelle — und ein Platzhalter, wo die Datei
    daneben zeigt.

    Ein Eintrag, den es nicht gibt, ist keine Farbe; er ist aber auch kein
    Grund, dem Netz seine Slotnummer zu lassen und die Liste dazu wegzuwerfen.
    """
    group, position = key
    names = materials.get(group, [])
    if 0 <= position < len(names):
        return names[position]
    _log.info("3MF names no material at position %d of group %s", position, group)
    # Übersetzt, denn der Name landet in der Pinselleiste (Regel 20). Die
    # zwei Schreibstellen weiter unten bleiben roh: Dateiinhalt für fremde
    # Slicer ist keine Oberfläche.
    return (str(_("Slot {number}", number=position)), DEFAULT_COLOUR)


def _matrix(text: str | None) -> np.ndarray:
    """Eine 3MF-Transformation — zwölf Zahlen, spaltenweise 4x3 — als
    4x4-Matrix.

    Kein Attribut heißt „steht, wo es steht": die Einheitsmatrix, und dazu gibt
    es nichts zu sagen. Ein Attribut, das dasteht und sich nicht lesen lässt,
    ist etwas anderes — das Teil landet dann an einer Stelle, die die Datei
    nicht meint, und ohne diese Zeile suchte man den Grund in der Geometrie.
    Gemeldet wie in :func:`_mesh_from`, mit dem Rohtext: Er sagt beim nächsten
    Fall, welcher Schreiber ihn erzeugt hat.
    """
    if not text:
        return np.eye(4)
    parts = text.replace(",", " ").split()
    if len(parts) != 12:
        _log.warning("3MF placement has %d value(s) instead of 12: %r", len(parts), text)
        return np.eye(4)
    try:
        values = [float(entry) for entry in parts]
    except ValueError:
        _log.warning("3MF placement is not readable as numbers: %r", text)
        return np.eye(4)
    matrix = np.eye(4)
    matrix[:3, :3] = np.array(values[:9], dtype=float).reshape(3, 3).T
    matrix[:3, 3] = values[9:]
    return matrix


def _materials_in(model: ET.Element) -> dict[str, list[tuple[str, tuple[float, float, float]]]]:
    """Jede ``basematerials``-Gruppe, nach ID, in Dokumentreihenfolge."""
    found: dict[str, list[tuple[str, tuple[float, float, float]]]] = {}
    for group in model.findall(f".//{{{CORE_NAMESPACE}}}basematerials"):
        identifier = group.get("id")
        if identifier is None:
            continue
        found[identifier] = [
            (entry.get("name") or "", _rgb(entry.get("displaycolor")))
            for entry in group.findall(f"{{{CORE_NAMESPACE}}}base")
        ]
    return {key: value for key, value in found.items() if value}


def _extra_colours(text: object) -> tuple[tuple[float, float, float], ...]:
    """Die zweite bis vierte Farbe aus ``filament_multi_colour`` — ohne die erste.

    Höchstens :data:`app.core.types.MAX_FILAMENT_COLOURS` insgesamt; eine
    Datei, die mehr nennt, ist kein Grund anzuhalten, nur einer, den Rest
    stehen zu lassen. Was keine Farbe ist, fällt weg statt auf die Vorgabe zu
    fallen — sonst trüge ein Filament eine zweite Farbe, die nie dastand.
    """
    if not isinstance(text, str):
        return ()
    valid: list[str] = []
    for part in text.split():
        digits = part.lstrip("#")
        if len(digits) not in (6, 8):
            continue
        try:
            int(digits[:6], 16)
        except ValueError:
            continue
        valid.append(part)
    return tuple(_rgb(part) for part in valid[1:MAX_FILAMENT_COLOURS])


def _rgb(text: str | None) -> tuple[float, float, float]:
    """``#RRGGBB`` oder ``#RRGGBBAA`` als drei Zahlen; Alpha druckt nicht."""
    digits = (text or "").lstrip("#")
    if len(digits) not in (6, 8):
        return DEFAULT_COLOUR
    try:
        values = [int(digits[start : start + 2], 16) / 255.0 for start in (0, 2, 4)]
    except ValueError:
        return DEFAULT_COLOUR
    return (values[0], values[1], values[2])
