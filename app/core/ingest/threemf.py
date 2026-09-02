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
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from typing import Final
from xml.etree import ElementTree as ET

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import CANCEL, Action, ValidationError
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import MaterialSlot
from app.i18n import _

_log = get_logger(__name__)

CORE_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
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
    try:
        with zipfile.ZipFile(BytesIO(payload)) as container:
            model = ET.fromstring(container.read(MODEL_PATH))
    except (KeyError, zipfile.BadZipFile, ET.ParseError):
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


def read_objects(payload: bytes) -> list[Part]:
    """Jeder Körper, den der Build platziert, jeder dort, wohin die Datei ihn
    setzt.

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
    parts: list[Part] = []
    for leaf in _leaves(payload):
        body = _mesh_from(leaf.node)
        if body is None:
            continue
        moved = body.raw.copy()
        moved.apply_transform(leaf.transform)

        groups = _groups_of(leaf.node, leaf.palette, leaf.pid, leaf.pindex)
        mesh = (
            MeshData(raw=moved, slots=groups.slots) if groups is not None else body.replacing(moved)
        )
        parts.append(
            Part(name=leaf.name, mesh=mesh, slots=tuple(groups.materials) if groups else ())
        )

    _log.info("read %d part(s) from a 3MF build", len(parts))
    return _numbered(parts)


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
    except (KeyError, OSError, zipfile.BadZipFile, ET.ParseError, NotImplementedError):
        return None
    return None


#: Die zwei Teilbäume, die eine Modelldatei schwer machen: je ein Kind pro Ecke
#: und pro Dreieck. Die Struktur darüber — Objekt, Mesh-Hülle, Komponenten,
#: Build — ist klein.
_VERTICES_TAG: Final = f"{{{CORE_NAMESPACE}}}vertices"
_TRIANGLES_TAG: Final = f"{{{CORE_NAMESPACE}}}triangles"

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
    triangles = 0
    root: ET.Element | None = None
    with container.open(entry) as stream:
        for event, element in ET.iterparse(stream, events=("start", "end")):
            if root is None:
                # Das erste Startelement ist die Wurzel; ohne diesen Griff wäre
                # sie nach dem Leeren der Kinder nicht mehr zu greifen.
                root = element
            if event != "end":
                continue
            if element.tag in (_TRIANGLES_TAG, _VERTICES_TAG):
                found = len(element)
                if element.tag == _TRIANGLES_TAG:
                    triangles += found
                # ``clear`` nimmt die Attribute mit — die Zahl kommt danach.
                element.clear()
                element.set(_SCANNED_COUNT, str(found))
    if root is None:
        raise ET.ParseError("model file without a root element")
    return root, triangles


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


def _scan(payload: bytes) -> tuple[int, int]:
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
            for entry in [MODEL_PATH, *sorted(names)]:
                if entry in models:
                    continue
                if entry != MODEL_PATH and not (
                    entry.startswith("3D/Objects/") and entry.endswith(".model")
                ):
                    continue
                models[entry], found = _model_without_geometry(container, entry)
                triangles += found
            titles = _titles(container.read(SETTINGS_PATH)) if SETTINGS_PATH in names else {}
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
            titles,
            item.get("name") or titles.get(identifier, ""),
            0,
        ):
            # Ein Mesh ohne Dreiecke ist kein Körper. Gezählt wurde es
            # trotzdem, und der Leser überging es — der Stapel bekam damit eine
            # Objekt-ID zu viel, die Auswertung hielt mit
            # ``evaluate.object_count`` an, und aus einer Datei mit einem
            # lesbaren Körper wurde ein Import, der gar nichts einlas.
            if _carries_geometry(leaf.node):
                bodies += 1
            else:
                _log.warning("3MF body %r has no geometry — not counted", leaf.name)
    return bodies, triangles


def scan_assembly(payload: bytes) -> tuple[int, int]:
    """(Zahl der Körper, Zahl der Dreiecke) einer 3MF — streamend, ohne
    Koordinaten im Speicher.

    Die Körperzahl braucht der Stapel für die Objekt-IDs (§11), die Dreieckzahl
    die Größengrenze: Sie geht an ``check_limits``, **bevor** ``read_objects``
    das ganze XML in den Speicher hebt. Beides in einem Lauf, damit die Datei
    nur einmal durchläuft.
    """
    return _scan(payload)


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


def _leaves(payload: bytes) -> list[_Leaf]:
    """Läuft den Build ab und sammelt jedes Mesh, das er erreicht, der Reihe
    nach.
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
            titles = _titles(container.read(SETTINGS_PATH)) if SETTINGS_PATH in names else {}
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
                titles,
                item.get("name") or titles.get(identifier, ""),
                0,
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


def _titles(payload: bytes) -> dict[str, str]:
    """Namen, die der Slicer notiert hat, nach Objekt und nach Part-ID.

    Eine Part-ID ist das, was eine Komponente benennt — das Blatt bekommt also
    den Namen der Datei, die es einmal war, und das ist der Name, den jemand
    gewählt hat.
    """
    try:
        config = ET.fromstring(payload)
    except ET.ParseError:
        return {}

    found: dict[str, str] = {}
    for node in [*config.findall(".//object"), *config.findall(".//part")]:
        identifier = node.get("id")
        if identifier is None:
            continue
        for entry in node.findall("metadata"):
            if entry.get("key") == "name" and entry.get("value"):
                found[identifier] = _without_suffix(str(entry.get("value")))
                break
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
    titles: dict[str, str],
    inherited: str,
    depth: int,
    seen: frozenset[tuple[str, str]] = frozenset(),
) -> list[_Leaf]:
    """Die Meshes, die ein Objekt beiträgt, mit den Transformationen darüber
    angewandt.
    """
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
        or titles.get(identifier)
        or inherited
        or str(_("Körper {number}", number=identifier))
    )
    mesh_node = entry.find(f"{{{CORE_NAMESPACE}}}mesh")
    if mesh_node is not None:
        return [
            _Leaf(
                name=name,
                node=mesh_node,
                transform=transform,
                palette=materials.get(path, {}),
                pid=entry.get("pid") or "",
                pindex=_position(entry.get("pindex"), 0),
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
                titles,
                name,
                depth + 1,
                seen | {(path, identifier)},
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
