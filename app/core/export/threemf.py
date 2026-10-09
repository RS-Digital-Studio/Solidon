"""3MF mit Farbgruppen (Bauplan §20, §29).

trimesh schreibt 3MF, aber nicht die Materialgruppen je Dreieck, die ein
mehrfarbiger Druck braucht. Also wird der Container hier geschrieben: das
Format ist ein ZIP mit einem XML darin, und der Teil, auf den es ankommt, sind
fünfzehn Zeilen davon.

Die Zuordnung ist die aus §20: ein Materialslot des Objekts wird ein Eintrag
in einer ``basematerials``-Gruppe, und jedes Dreieck trägt den Index seines
Slots. Die Slicerfamilien benötigen zusätzlich native Objektwerkzeuge und
Flächenfarben: Standardfarben allein wählen dort kein Filament.

Das Zurücklesen stand bis zum 02.09.2026 ebenfalls hier und liegt jetzt in
:mod:`app.core.ingest.threemf` — ``ingest`` liest, ``export`` schreibt, und
``geom`` kennt kein Dateiformat mehr. Die Konstanten des Containers, die beide
brauchen, stehen beim Leser; dieses Modul holt sie sich von dort.

Von Hand geschrieben statt mit einer Bibliothek, weil es keine gibt, die nur
das tut — und ein 3MF-Schreiber, der alles andere auch kann, wäre eine
Abhängigkeit für fünfzehn Zeilen.
"""

from __future__ import annotations

import dataclasses
import json
import secrets
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from io import BytesIO
from typing import Final
from xml.etree import ElementTree as ET

import numpy as np

from app.branding import APP_NAME, APP_VERSION
from app.core.errors import CANCEL, SPLIT_FILAMENT_FILES, InternalError, ValidationError
from app.core.export import slicer_keys
from app.core.geom.mesh import MeshData
from app.core.ingest.threemf import (
    CORE_NAMESPACE,
    DEFAULT_COLOUR,
    MODEL_PATH,
    NATIVE_TOOL_LIMIT,
    PRUSA_NAMESPACE,
    SETTINGS_PATH,
    plate_origin,
)

# Der Plattenraster wohnt beim Leser, der ihn seit RM-252 auch braucht, und
# ebenso der Ort der Projekteinstellungen, aus dem er die Druckfläche liest;
# beide bleiben unter diesem Modul erreichbar, wo Übergabe, Tests und Karte
# sie nennen.
from app.core.ingest.threemf import (
    PROJECT_SETTINGS_PATH as PROJECT_SETTINGS_PATH,
)
from app.core.ingest.threemf import (
    SLICER_PLATE_GAP as SLICER_PLATE_GAP,
)
from app.core.knowledge import profiles
from app.core.log import get_logger
from app.core.types import MaterialSlot, SceneObject
from app.core.units import is_zero
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
MODEL_RELATIONSHIP = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"

#: Wo PrusaSlicer führt, was die Orca-Familie in ``PROJECT_SETTINGS_PATH``
#: ablegt (die Konstanten des Containers stehen beim Leser,
#: ``ingest/threemf.py``) — dieselbe Sache, ein anderes Format: eine
#: Zeile ``; schlüssel = wert`` je Einstellung statt einer JSON-Abbildung.
#:
#: Er schreibt sie beim Konsolenexport selbst nicht mit, **liest** sie aber:
#: eine 3MF mit dieser Beilage, ohne ``--load`` geslict, ergab Solidons Werte
#: bis in die Wandzahl und die Fülldichte hinein. Ohne sie war eine
#: exportierte Datei für PrusaSlicer bloß Geometrie.
PRUSA_CONFIG_PATH = "Metadata/Slic3r_PE.config"

#: Prusas eigene Objektwerte; die Orca-Beilage wird dort nicht gelesen.
PRUSA_MODEL_CONFIG_PATH = "Metadata/Slic3r_PE_model.config"

#: Die erste Zeile jener Beilage. PrusaSlicer überspringt sie — bei ihm steht
#: dort seine eigene Kennung —, und was ohne sie an erster Stelle stünde, wäre
#: verloren, ohne dass es jemand merkt.
PRUSA_CONFIG_HEADER = "; von Solidon geschrieben"

#: Curas Namensraum für Werte je Objekt (``ThreeMFWriter`` in Cura 5.13). Das
#: Fenster liest sie aus ``<metadatagroup>`` am Objekt, als ``cura:<schlüssel>``;
#: libSavitar streift das Präfix ab (``SceneNode::fillByXMLNode``).
CURA_NAMESPACE = "http://software.ultimaker.com/xml/cura/3mf/2015/10"


def write(mesh: MeshData, slots: list[MaterialSlot] | None = None, name: str = "") -> bytes:
    """Ein Körper als 3MF-Container, mit einem Material je Slot."""
    entries = _slots_for(mesh, slots)
    model = _model_xml(mesh, entries, name)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr("[Content_Types].xml", _content_types())
        container.writestr("_rels/.rels", _relationships())
        container.writestr(MODEL_PATH, model)
        if slots and len(entries) == 1:
            # Dieselbe Extruderzuordnung wie :func:`write_assembly`: Erst sie
            # macht eine einzige Farbe zur Wahl. Ohne sie las der Import den
            # einfarbigen Einzelexport als Vorgabe und verlor das Filament,
            # das die Baugruppe desselben Körpers behielt. Mehrere Materialien
            # sind schon über die Dreiecke eine Wahl; eine Objektangabe
            # überstimmte dort die Bemalung.
            part = AssemblyPart(mesh=mesh, name=name, slots=tuple(slots or ()))
            materials = merge_slots([part])
            container.writestr(SETTINGS_PATH, _settings_xml([part], materials, False))
            container.writestr(
                PRUSA_MODEL_CONFIG_PATH, _prusa_settings_xml([part], materials, False)
            )
    _log.info("wrote 3MF with %d material(s)", len(entries))
    return buffer.getvalue()


@dataclass(frozen=True, slots=True)
class AssemblyPart:
    """Ein Teil einer Baugruppe, für :func:`write_assembly` (§20, §29)."""

    mesh: MeshData
    name: str = ""
    slots: tuple[MaterialSlot, ...] = ()
    settings: Mapping[str, str] = field(default_factory=dict)
    """Was nur für dieses Teil gilt, in der Schreibweise des Slicers.

    Eine Platte hat einen Satz Einstellungen, aber nicht jedes Teil darauf
    braucht dasselbe: eine Streuscheibe steht auf drei 1,1-mm-Federarmen und
    will einen Brim, die zwölf Behälter daneben stehen auf Ø 40 und wollen
    keinen. Leer heißt: es gilt, was für die Platte gilt.
    """
    plate: int = 0
    """Auf welche Druckplatte dieses Teil gehört, von null an gezählt."""
    support_blocker: MeshData | None = None
    """Wo der Slicer an diesem Teil keine Stützen anlegen darf, in seinen
    Koordinaten — die Kanäle, deren Decken sich selbst schließen (§22.2).

    Er reist als zweiter Volumenbereich desselben Objekts, ``SupportBlocker``
    in der Prusa-Beilage — so schreiben PrusaSlicer und die Orca-Familie ihn
    selbst. Gemessen am ElegooSlicer mit der Waschschüssel (26.09.2026):
    „Stützen überall" legte ohne ihn 22,9 m Stütze in den Wasserkanal, mit
    ihm 0,3 m.
    """


SlotKey = tuple[TranslatableText | str, tuple[float, float, float] | None, str | None, str | None]
"""Woran zwei Slots als **dasselbe Filament** erkannt werden: Name, Farbe,
Herstellerprofil und Materialart."""


def slot_identity(slot: MaterialSlot) -> SlotKey:
    """Die Identität eines Slots für das Zusammenlegen (§20).

    Name und Farbe allein reichten nicht: Zwei Teile mit je einem Slot
    „Schwarz" in Schwarz, eines PLA und eines PETG, wurden **eine** Düse —
    die Baugruppe trug einen Materialeintrag, jedes Dreieck ``p1="0"``, und
    das PETG-Profil war aus der Liste verschwunden, je nachdem, welches Teil
    zuerst kam (Gesamtreview 05.09.2026, CORE-21). Gleicher Name und gleiche
    Farbe dürfen zusammenfallen, wenn auch Profil und Materialart gleich sind.
    """
    return (slot.name, slot.colour, slot.material, slot.material_type)


def slots_for_object(entry: SceneObject) -> tuple[MaterialSlot, ...]:
    """Erhält Spulenidentitäten und nimmt ausdrückliche alte Körpermaterialien mit.

    Vor den Materialslots stand die Wahl nur am Körper. Eine vollständig
    fehlende Slotliste darf diese belegte Materialart beim Export nicht zur
    Projektvorgabe machen. Deklarierte Plätze bleiben unverändert; fehlende
    Plätze eines bemalten Körpers ergänzt erst :func:`assembly_slots` neutral.
    Das Objekt selbst wird weder geändert noch mit einer Spule versehen.
    """
    if entry.material_slots or not entry.material:
        return tuple(entry.material_slots)
    return (
        MaterialSlot(
            index=0,
            name=profiles.material(entry.material).title,
            material_type=slicer_keys.filament_type(entry.material),
        ),
    )


def assembly_slots(part: AssemblyPart) -> tuple[MaterialSlot, ...]:
    """Erhält deklarierte Plätze und ergänzt verwendete fehlende Slots neutral.

    Eine alte Slotliste kann Einträge ohne Flächen oder Flächen ohne Eintrag
    tragen. Die ersten bleiben für die Bindung alter Profilwahlen erhalten,
    die zweiten bekommen dieselben neutralen Platzhalter wie beim Export
    eines einzelnen Körpers. Die Ausgabe filtert danach in :func:`merge_slots`.
    """
    declared = part.slots or (MaterialSlot(index=0, name=""),)
    known = {slot.index for slot in declared}
    missing = (slot for slot in _slots_for(part.mesh, declared) if slot.index not in known)
    return (*declared, *missing)


def merge_slots(
    parts: Sequence[AssemblyPart],
    across: Sequence[AssemblyPart] | None = None,
    *,
    include_unused: bool = False,
) -> list[MaterialSlot]:
    """Eine Materialliste über alle Teile — das ist die Extruderzuordnung
    (§20).

    Ein Slot ist ein Filament, kein Objektmerkmal: zwei Teile in derselben
    Farbe sollen aus derselben Düse kommen und nicht aus zweien. Zusammengelegt
    wird deshalb über :func:`slot_identity` — Name, Farbe, Profil **und**
    Materialart (CORE-21: gleichfarbiges PLA und PETG sind zwei Spulen) —, und
    die Reihenfolge des Ergebnisses ist die Reihenfolge der Extruder.

    Ohne diese Zusammenlegung bekäme eine Baugruppe aus drei einfarbigen Teilen
    drei Materialien — und der Slicer fragte nach drei Filamenten für einen
    einfarbigen Druck.

    **``across`` ist der Auftrag, ``parts`` die Platte** (Fund von 3d-druck-de,
    26.08.2026). Nummeriert wird nach dem ersten Auftreten — und weil der
    Export je Platte aufruft, lag dieselbe Farbe in einem Auftrag an
    verschiedenen Düsen: Platte 1 nur Rot (Extruder 0), Platte 2 Weiß und Rot
    (Rot dann Extruder 1). Wer den Auftrag am Stück druckt, müsste mittendrin
    umstecken. Wer alle Platten kennt, gibt sie hier mit; die Nummern kommen
    dann für alle aus derselben Zählung. Ohne Angabe bleibt es bei ``parts``,
    denn eine einzeln exportierte Platte *ist* der Auftrag.

    Unbemalte alte Deklarationen gehören nicht zum Druckauftrag. Nur die
    einmalige Bindung alter Profilplätze fragt mit ``include_unused`` die
    vollständige frühere Reihenfolge ab, bevor Werkzeuge neu nummeriert werden.
    """
    from app.core.geom.attributes import used_slots

    def present(part: AssemblyPart) -> tuple[MaterialSlot, ...]:
        declared = assembly_slots(part)
        if include_unused:
            return declared
        used = set(used_slots(part.mesh))
        return tuple(slot for slot in declared if slot.index in used)

    order: list[MaterialSlot] = []
    # Der Name darf ein ``TranslatableText`` sein (:attr:`MaterialSlot.name`).
    # Zusammengelegt wird trotzdem richtig: Ein solcher Text vergleicht und
    # hasht wie seine Message-ID, auch gegen eine schlichte Zeichenkette.
    seen: dict[SlotKey, int] = {}
    for part in across if across is not None else parts:
        for slot in present(part):
            key = slot_identity(slot)
            if key in seen:
                continue
            seen[key] = len(order)
            order.append(dataclasses.replace(slot, index=len(order)))
    if across is None:
        return order
    # Die Belegung des Auftrags, beschränkt auf das, was diese Platte braucht —
    # mit den Nummern des Auftrags. Ein Slicer, der eine Platte allein bekommt,
    # soll nicht nach Filamenten fragen, die auf ihr nicht vorkommen.
    here = {slot_identity(slot) for part in parts for slot in present(part)}
    return [slot for slot in order if slot_identity(slot) in here]


def tools_in_use(
    parts: Sequence[AssemblyPart], across: Sequence[AssemblyPart] | None = None
) -> tuple[int, ...]:
    """Welche Werkzeuge die **Flächen** dieser Teile wirklich benutzen (§20).

    Die Gegenprobe nach dem Slicen braucht diese Zahl, und die Slotliste
    beantwortet sie nicht: Ein Körper darf einen Slot deklarieren, den keines
    seiner Dreiecke trägt — eine alte Spulenwahl, eine gelöschte Bemalung —,
    und eine Prüfung gegen die Deklaration schlüge dann bei einem Druck an,
    dem nichts fehlt (``handover.spools_left_out``).

    Gezählt wird in derselben Nummerierung wie in der geschriebenen Datei:
    über :func:`slot_identity` in die Reihenfolge aus :func:`merge_slots`.
    ``across`` bedeutet dasselbe wie dort — der Auftrag gibt die Nummern vor,
    ``parts`` ist die Platte.
    """
    # Örtlich wie in :func:`_slots_for`: ``geom.attributes`` wird von hier aus
    # nur für diese eine Frage gebraucht, und der Import bleibt dort, wo er
    # gilt.
    from app.core.geom.attributes import used_slots

    positions = {slot_identity(entry): entry.index for entry in merge_slots(parts, across=across)}
    tools: set[int] = set()
    for part in parts:
        active = set(used_slots(part.mesh))
        for slot in assembly_slots(part):
            if slot.index in active and slot_identity(slot) in positions:
                tools.add(positions[slot_identity(slot)])
    return tuple(sorted(tools))


def by_extruder(slots: Sequence[MaterialSlot]) -> list[MaterialSlot | None]:
    """Dieselben Slots an ihrem Extruderplatz, mit ``None`` in den Lücken (§20).

    :func:`merge_slots` rechnet die Nummer des **Auftrags** aus und gibt für
    eine einzelne Platte nur die Filamente zurück, die dort vorkommen. Wer
    diese Liste danach durchnummeriert, wirft die Rechnung weg: Lässt Platte 2
    die Farbe von Platte 1 aus, rutscht die verbliebene auf Extruder 0, und
    derselbe Auftrag bräuchte mittendrin ein Umstecken.

    Der freie Platz bleibt deshalb frei. Was ein Aufrufer daraus macht — ein
    Platzhalter in der Materialliste, ein Filamentprofil mit den Projektwerten
    — hängt an seiner Datei; die Reihenfolge ist an allen Stellen dieselbe.
    """
    if not slots:
        return []
    placed: list[MaterialSlot | None] = [None] * (max(entry.index for entry in slots) + 1)
    for entry in slots:
        placed[entry.index] = entry
    return placed


def write_assembly(
    parts: Sequence[AssemblyPart],
    name: str = "",
    bed_centre: tuple[float, float] | None = None,
    project_settings: Mapping[str, object] | None = None,
    layout: tuple[float, float] | None = None,
    prusa_config: Mapping[str, str] | None = None,
    across: Sequence[AssemblyPart] | None = None,
    blocker_as_part: bool = True,
    cura: bool = False,
) -> bytes:
    """Mehrere Körper als eine 3MF-Baugruppe (§20, §29).

    Das ist der Unterschied zwischen „eine Datei je Teil" und „ein
    Druckauftrag": ein Slicer, der eine Baugruppe bekommt, ordnet sie als
    Ganzes an und schreibt eine Druckdatei. Bekommt er einzelne Dateien,
    entscheidet er über die Zusammengehörigkeit selbst — und was Solidon über
    die Platte weiß, ist verloren.

    Die Materialien sind über alle Teile zusammengelegt (:func:`merge_slots`),
    denn genau diese Liste liest der Slicer als seine Extruderbelegung.

    ``bed_centre`` ist Solidons Bettmitte in den Koordinaten des Slicers
    (``build_area.machine_shift``). Mit dieser Angabe bekommt jedes Teil eine
    Platzierung auf der Platte — Solidon rechnet um die Bettmitte, ein Slicer
    um den Nullpunkt seiner Maschine, meist die Ecke, an einem Delta oder am
    Dremel 3D45 nicht (RM-424). Ohne die Umrechnung liegt die ganze Szene
    neben dem Bett, und der Slicer ordnet notgedrungen selbst an: was
    `arrange_bed` errechnet hat, ist dann weg, samt Haftungsrand und
    Plattenzuordnung.

    Verschoben wird über die Platzierungsmatrix des Standards, nicht über die
    Punkte. Die Geometrie bleibt damit die, die im Dokument steht — dieselbe
    Datei taugt weiter als Modell und nicht nur als Druckauftrag.

    ``layout`` ist Breite und Tiefe des Betts für die zweite Verschiebung:
    Liegen die Teile auf mehreren Platten, rückt jede Platte an ihren Platz im
    Raster der Orca-Familie (:func:`plate_origin`) — auch ohne ``bed_centre``,
    denn sonst stünde die zweite Platte auf der ersten.

    ``project_settings`` sind die Druckeinstellungen der Platte, wie die
    Orca-Familie sie in einer Projektdatei führt (:data:`PROJECT_SETTINGS_PATH`).
    Ohne sie öffnet der Slicer die Datei mit dem Profil, das gerade eingestellt
    ist — die Geometrie stimmt dann, und alles andere ist Zufall. Gebaut wird
    die Abbildung nicht hier, sondern in ``handover``: sie zu kennen heißt, den
    Slicer zu kennen, und dieses Modul kennt nur das Format.

    ``prusa_config`` ist dieselbe Sache für PrusaSlicer, der sie als
    Textzeilen führt (:data:`PRUSA_CONFIG_PATH`). Zwei Parameter für einen
    Zweck, weil es zwei Formate sind — und Formate sind das, was dieses Modul
    kennt.

    ``cura`` ist Curas Schreibweise für sein Fenster: die Werte je Teil als
    ``cura:``-Metadaten am Objekt (:data:`CURA_NAMESPACE`), die Stützsperre als
    Komponente neben dem Körper mit ``anti_overhang_mesh``, und keine Beilage
    der anderen Familien. Die Komponente und nicht ein eigenes Objekt: Cura
    setzt ein freistehendes Objekt aufs Bett und ordnet es für sich an, ein
    Kind einer Gruppe wandert mit ihr.
    """
    if not parts:
        raise ValueError("an assembly needs at least one part")

    materials = merge_slots(parts, across=across)
    model = _assembly_xml(parts, materials, name, bed_centre, layout, blocker_as_part or cura, cura)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr("[Content_Types].xml", _content_types())
        container.writestr("_rels/.rels", _relationships())
        container.writestr(MODEL_PATH, model)
        if not cura:
            container.writestr(SETTINGS_PATH, _settings_xml(parts, materials, blocker_as_part))
            container.writestr(
                PRUSA_MODEL_CONFIG_PATH, _prusa_settings_xml(parts, materials, blocker_as_part)
            )
        if project_settings:
            container.writestr(
                PROJECT_SETTINGS_PATH,
                json.dumps(dict(project_settings), indent=4, ensure_ascii=False),
            )
        if prusa_config:
            # Die Kopfzeile ist kein Schmuck: PrusaSlicer überspringt die
            # erste Zeile dieser Beilage — dort steht bei ihm selbst „generated
            # by PrusaSlicer". Ohne sie fiel der alphabetisch erste Schlüssel
            # heraus, und zwar lautlos: gemessen war es
            # ``avoid_crossing_perimeters``, das als 1 in der Datei stand und
            # als 0 im G-Code ankam.
            lines = [PRUSA_CONFIG_HEADER]
            lines += [f"; {key} = {value}" for key, value in sorted(prusa_config.items())]
            container.writestr(PRUSA_CONFIG_PATH, "\n".join(lines) + "\n")
    _log.info(
        "wrote 3MF assembly: %d part(s), %d material(s), settings: %s",
        len(parts),
        len(materials),
        "yes" if project_settings or prusa_config else "no",
    )
    return buffer.getvalue()


def _prusa_settings_xml(
    parts: Sequence[AssemblyPart], materials: Sequence[MaterialSlot], blocker_as_part: bool = True
) -> bytes:
    """Objektwerte mit Prusas Typkennung und Zuordnung der Dreiecke (§29).

    Die Stützsperre steht hier nur, wenn sie als Bereich im Netz hängt
    (``blocker_as_part`` falsch, die Schreibweise von PrusaSlicer); als
    eigenes Teil nennt sie die Orca-Beilage (:func:`_settings_xml`).
    """
    config = ET.Element("config")
    for number, part in enumerate(parts, start=2):
        node = ET.SubElement(config, "object", {"id": str(number), "instances_count": "1"})
        values = {"name": part.name, **part.settings}
        if part.slots or part.mesh.slots:
            values["extruder"] = str(_part_extruder(part, materials) + 1)
        for key, value in values.items():
            ET.SubElement(node, "metadata", {"type": "object", "key": key, "value": value})
        if part.mesh.triangle_count:
            volume = ET.SubElement(
                node, "volume", {"firstid": "0", "lastid": str(part.mesh.triangle_count - 1)}
            )
            ET.SubElement(
                volume, "metadata", {"type": "volume", "key": "volume_type", "value": "ModelPart"}
            )
        if (
            not blocker_as_part
            and part.support_blocker is not None
            and part.support_blocker.triangle_count
        ):
            first = part.mesh.triangle_count
            blocker = ET.SubElement(
                node,
                "volume",
                {
                    "firstid": str(first),
                    "lastid": str(first + part.support_blocker.triangle_count - 1),
                },
            )
            ET.SubElement(
                blocker,
                "metadata",
                {
                    "type": "volume",
                    "key": "volume_type",
                    "value": slicer_keys.PRUSA_SUPPORT_BLOCKER,
                },
            )
            ET.SubElement(
                blocker,
                "metadata",
                {"type": "volume", "key": "name", "value": str(_("Stützsperre"))},
            )
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + bytes(
        ET.tostring(config, encoding="utf-8")
    )


def _settings_xml(
    parts: Sequence[AssemblyPart], materials: Sequence[MaterialSlot], blocker_as_part: bool = True
) -> bytes:
    """Die Beilage, in der die Orca-Familie Namen und Objektwerte führt.

    Zwei Dinge stehen hier, die sonst verloren gingen. Zum einen die **Namen**:
    der Standard hat ein ``name``-Attribut am Objekt, und Solidon schreibt es
    auch — aber diese Slicer schreiben es selbst nie und lesen die Namen von
    hier. Eine Baugruppe kam deshalb als „Object 1, Object 2" an, obwohl die
    Namen in der Datei standen.

    Zum anderen die **Einstellungen je Teil**. Eine Platte hat einen Satz
    Werte, aber nicht jedes Teil darauf braucht dasselbe — und ohne diesen Ort
    gäbe es nur die Wahl zwischen „alle bekommen es" und „keiner".

    Für PrusaSlicer und CuraEngine hat die Datei keine Bedeutung; sie stört
    dort auch nicht, denn was ein Programm nicht kennt, liest es nicht.
    """
    config = ET.Element("config")
    helpers = _helper_ids(parts) if blocker_as_part else {}
    for number, part in enumerate(parts, start=2):
        node = ET.SubElement(config, "object", {"id": str(number)})
        if part.name:
            ET.SubElement(node, "metadata", {"key": "name", "value": part.name})
        # **Jedes Objekt nennt sein Werkzeug, auch ohne Spule** — dann das des
        # neutralen Platzes, den ``tools_in_use`` für die Gegenprobe zählt.
        # Creality Print 7.2 lässt ein Objekt ohne ``extruder`` auf der Konsole
        # ohne Werkzeug: Die Werkzeugfolge bleibt leer, und jede solche 3MF
        # endete mit „The print is empty" (RM-164, 29.09.2026).
        ET.SubElement(
            node,
            "metadata",
            {
                "key": "extruder",
                "value": str(_part_extruder(part, materials) + 1),
            },
        )
        for key, value in part.settings.items():
            ET.SubElement(node, "metadata", {"key": key, "value": value})
        if number in helpers:
            # Die Teile des Objekts, wie ``_assembly_xml`` sie als Komponenten
            # anlegt; die Matrix ist die Einheit, gelegt wird über den Build.
            for child, kind, title in (
                (helpers[number][0], "normal_part", part.name),
                (helpers[number][1], slicer_keys.ORCA_SUPPORT_BLOCKER, str(_("Stützsperre"))),
            ):
                piece = ET.SubElement(node, "part", {"id": str(child), "subtype": kind})
                if title:
                    ET.SubElement(piece, "metadata", {"key": "name", "value": title})
                ET.SubElement(piece, "metadata", {"key": "matrix", "value": _IDENTITY_MATRIX})

    # Und die Platten. Ohne sie ist eine Datei mit mehreren Platten für den
    # Slicer eine einzige, auf der alles nebeneinander steht — die Teile
    # lägen weit außerhalb des Betts, und er ordnete notgedrungen neu an.
    #
    # Aufbau aus einer echten Slicer-Datei gelesen: je Platte ein
    # ``plate``-Block mit ``plater_id`` von eins an und je Teil ein
    # ``model_instance``, das auf die Objektnummer zeigt. Die Vorschaubilder,
    # die der Slicer daneben führt, entstehen bei ihm — was hier fehlt,
    # rechnet er beim Öffnen nach.
    #
    # **Gezählt wird durch, nicht nach Solidons Nummer.** Der Slicer legt seine
    # Platten in der Reihenfolge der Blöcke ins Raster (:func:`plate_origin`),
    # und die Matrix der Teile rechnet mit demselben Rang — eine Lücke in den
    # Nummern (Platte 1 und 3 gewählt) darf die beiden nicht auseinanderbringen.
    for rank, plate in enumerate(sorted({part.plate for part in parts})):
        block = ET.SubElement(config, "plate")
        ET.SubElement(block, "metadata", {"key": "plater_id", "value": str(rank + 1)})
        ET.SubElement(block, "metadata", {"key": "plater_name", "value": ""})
        ET.SubElement(block, "metadata", {"key": "locked", "value": "false"})
        for number, part in enumerate(parts, start=2):
            if part.plate != plate:
                continue
            instance = ET.SubElement(block, "model_instance")
            ET.SubElement(instance, "metadata", {"key": "object_id", "value": str(number)})
            ET.SubElement(instance, "metadata", {"key": "instance_id", "value": "0"})

    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + bytes(
        ET.tostring(config, encoding="utf-8")
    )


#: Die Einheitsmatrix in der Schreibweise der Orca-Beilage, sechzehn Werte zeilenweise.
_IDENTITY_MATRIX: Final = "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"


def _part_extruder(part: AssemblyPart, materials: Sequence[MaterialSlot]) -> int:
    """Das Grundwerkzeug, in derselben globalen Reihenfolge wie die Flächenfarben."""
    positions = {slot_identity(slot): slot.index for slot in materials}
    used = set(part.mesh.slots or (0,))
    return min(
        positions[slot_identity(slot)] for slot in assembly_slots(part) if slot.index in used
    )


def _paint_code(extruder: int) -> str:
    """Native Ganzflächenwerte bis zur belegten Grenze, einschließlich FC-Erweiterung."""
    if not 0 <= extruder < NATIVE_TOOL_LIMIT:
        raise ValidationError(
            field="slots",
            detail=_(
                "Diese 3MF-Ausgabe kann höchstens 32 Filamente zuordnen. "
                "Teilen Sie den Auftrag nach Filamenten auf."
            ),
            constraint="native_filament_limit",
            suggestions=(SPLIT_FILAMENT_FILES, CANCEL),
        )
    state = extruder + 1
    if state < 3:
        return f"{state << 2:X}"
    return f"{state - 3:X}C" if state < 18 else f"{state - 18:X}FC"


def _slots_for(mesh: MeshData, slots: Sequence[MaterialSlot] | None) -> list[MaterialSlot]:
    """Jeder Slot, den das Mesh wirklich benutzt, mit Namen und Farbe."""
    from app.core.geom.attributes import used_slots

    known = {entry.index: entry for entry in (slots or [])}
    return [
        known.get(index, MaterialSlot(index=index, name=_("Slot {number}", number=index)))
        for index in used_slots(mesh)
    ]


#: Der Platz, an dem die Geometrie eines Körpers ins fertige XML kommt.
#: Ein Zähler dahinter, weil eine Baugruppe mehrere trägt; die Zeichen sind
#: bewusst harmlos, damit ``ElementTree`` sie unverändert durchreicht.
#:
#: **Die Klammern am Ende sind nicht Zierat.** Ohne sie hieß die Marke
#: ``SOLIDON-MESH-2``, und das ist der Anfang von ``SOLIDON-MESH-20`` bis
#: ``-26``: Bei einer Baugruppe mit 25 Teilen fand sich die erste Marke
#: achtmal im Dokument, und die Prüfung in :func:`_fill_in` hielt an. Sie hat
#: den Fehler gefangen, weil sie zählt statt zu ersetzen — eine Ersetzung ohne
#: Zählung hätte die Geometrie des ersten Teils mitten in die Marke des
#: zwanzigsten geschrieben.
#:
#: Die Kennung je Körper ist zufällig: Ein Objektname reist unverändert ins
#: XML, und ein Körper namens ``[SOLIDON-MESH-2]`` ließ die Zählung mit
#: einer nackten Ausnahme abbrechen. Auf das Ergebnis hat der Zufall keinen
#: Einfluss — die Marke wird ersetzt und steht in keiner Datei.
#: Wie viele Ecken oder Dreiecke :func:`_write_geometry` je Block als Text baut.
_TEXT_BLOCK: Final = 65_536

_GEOMETRY_MARK: Final = "[SOLIDON-MESH-{run}-{number}]"


def _write_geometry(
    parent: ET.Element,
    mesh: MeshData,
    group_id: str,
    order: dict[int, int],
    native: bool = False,
    *,
    number: int = 0,
    blocker: MeshData | None = None,
) -> tuple[str, bytes]:
    """Ecken und Dreiecke eines Körpers, mit ihrer Materialzuordnung.

    Eine Stelle für beide Wege: eine Baugruppe schreibt dieselben Dreiecke wie
    ein einzelner Körper, nur mehrfach. Zwei Versionen davon wären zwei Orte,
    an denen sich eine Materialzuordnung verlieren kann.

    **Koordinaten bleiben in doppelter Genauigkeit erhalten.** Auch eine
    Rundung unter EPS_GEOM kann die Rechnung im Slicer verändern: Beim
    zweifarbigen Besteckeinsatz stürzte Elegoo mit Gitterstützen nach Rundung
    auf sechs Nachkommastellen ab. Siebzehn signifikante Stellen erhalten
    jeden endlichen float64-Wert, auch bei Stützsperren (§11.2, RM-252).

    **Die Geometrie entsteht als Text und nicht als Baum**, und das ist der
    Grund für die Rückgabe: Zurück kommen die Marke, die im Baum steht, und
    die Bytes, die an ihre Stelle gehören. Ein ``ET.SubElement`` je Ecke und je
    Dreieck legte für eine Kundenbaugruppe von 500 000 Dreiecken rund 750 000
    Objekte an, jedes mit eigenem Attributverzeichnis — und ``ET.tostring``
    läuft am Ende noch einmal über alle. Gemessen am 10.09.2026 an 25 Teilen
    mit zusammen gut 500 000 Dreiecken: **vier von fünf Läufen brachen ab**,
    einer davon mit Speicherzugriffsfehler, die übrigen mit
    ``SystemError: error return without exception set`` aus CPythons
    ElementTree. Der Fehler ist älter als diese Fassung — am Stand 0.3.5
    gemessen drei von fünf.

    Der Baum trägt jetzt je Körper **ein** Element mit der Marke als Text; die
    Zeichenkette daneben wächst linear und ohne Objektaufwand. Nach dem Umbau
    waren es zwei rote Läufe von vierundzwanzig statt vier von fünf; was übrig
    bleibt, ist dieselbe native Speicherfamilie, die dieses Projekt an
    mehreren Stellen hat.

    **Der damalige Umbau zum Text erhielt die Ausgabe bytegenau.** Gemessen
    am 10.09.2026 gegen drei vor diesem Umbau geschriebene Dateien — ein Körper,
    ein bemalter Körper, eine Baugruppe, mit ``&`` und ``<`` in den Namen —,
    alle drei byte-identisch. Im Tor steht dafür
    ``test_every_part_keeps_its_own_geometry_in_a_long_assembly``: Es zählt je
    Objekt Dreiecke und Ecken und verlangt, dass keine Marke im ausgelieferten
    Dokument stehen bleibt.
    """
    mark = _GEOMETRY_MARK.format(run=secrets.token_hex(6), number=number)
    geometry = ET.SubElement(parent, "mesh")
    geometry.text = mark

    # **Über Python-Listen, nicht über NumPy-Zeilen** (RM-568): Je Ecke drei
    # NumPy-Skalare zu lesen kostete am Meshy-Murmelbrett (1,95 Mio. Dreiecke)
    # den größten Teil der 7,3 s des 3MF-Exports. Dieselben Zahlen, dieselbe
    # Schreibweise: ``tolist`` gibt jeden float64 und jede Eckennummer
    # unverändert als Python-Zahl. **Und blockweise** (RM-567): Als eine
    # Liste aus Millionen Zeilen hielt der Text am Murmelbrett 850 MB über
    # dem Ergebnis; je Block entsteht er, wird kodiert und losgelassen.
    parts: list[bytes] = [b"<vertices>"]

    def vertex_rows(points: np.ndarray) -> None:
        for begin in range(0, len(points), _TEXT_BLOCK):
            parts.append(
                "".join(
                    f'<vertex x="{x:.17g}" y="{y:.17g}" z="{z:.17g}" />'
                    for x, y, z in points[begin : begin + _TEXT_BLOCK].tolist()
                ).encode("utf-8")
            )

    vertex_rows(np.asarray(mesh.raw.vertices))
    # Die Stützsperre als Bereich (PrusaSlicer): Ihre Dreiecke kommen nach
    # allen des Körpers, und die Prusa-Beilage nennt den Bereich.
    if blocker is not None:
        vertex_rows(np.asarray(blocker.raw.vertices))
    parts.append(b"</vertices><triangles>")

    # Der Schwanz eines Dreiecks hängt nur an seinem Slot: einmal je Slot
    # gebaut statt je Dreieck.
    tails: dict[int, str] = {}

    def tail(slot: int) -> str:
        known = tails.get(slot)
        if known is None:
            painted = (
                f' paint_color="{_paint_code(order[slot])}"'
                f' slic3rpe:mmu_segmentation="{_paint_code(order[slot])}"'
                if native
                else ""
            )
            known = tails[slot] = f' pid="{group_id}" p1="{order.get(slot, 0)}"{painted} />'
        return known

    faces = np.asarray(mesh.raw.faces)
    assignment = mesh.slots or ((0,) * len(faces))
    for begin in range(0, len(faces), _TEXT_BLOCK):
        parts.append(
            "".join(
                f'<triangle v1="{a}" v2="{b}" v3="{c}"{tail(int(slot))}'
                for (a, b, c), slot in zip(
                    faces[begin : begin + _TEXT_BLOCK].tolist(),
                    assignment[begin : begin + _TEXT_BLOCK],
                    strict=True,
                )
            ).encode("utf-8")
        )
    if blocker is not None:
        start = len(mesh.raw.vertices)
        parts.append(
            "".join(
                f'<triangle v1="{a + start}" v2="{b + start}" v3="{c + start}"'
                f' pid="{group_id}" p1="0" />'
                for a, b, c in np.asarray(blocker.raw.faces).tolist()
            ).encode("utf-8")
        )
    parts.append(b"</triangles>")
    return mark, b"".join(parts)


def _fill_in(document: bytes, blocks: Sequence[tuple[str, bytes]]) -> bytes:
    """Setzt jede Geometrie an die Stelle ihrer Marke.

    Gezählt und ersetzt wird das vollständige ``<mesh>``-Platzhalterelement.
    Namen dürfen denselben Text enthalten; XML-Sonderzeichen sind darin
    maskiert und können deshalb nicht mit dem Element selbst kollidieren.
    Fehlte eine Marke, bliebe sie in der Datei stehen; deshalb wird gezählt.
    """
    for mark, geometry in blocks:
        marker = f"<mesh>{mark}</mesh>".encode("ascii")
        found = document.count(marker)
        if found != 1:
            # Ein Programmfehler, kein Bedienfehler — und einer, der den
            # Export-Arbeiter nicht abreißen darf (§33.1, Regel 17).
            #
            # **Die Marke selbst geht ins Protokoll, nicht in den Befund**
            # (§33.2). Sie ist eine zufällige interne Kennung, für die es in
            # `ui.labels._VALUE_NAMES` keine Beschriftung gibt und geben soll —
            # ohne eine stünde der rohe Bezeichner im Tooltip des Kunden
            # (Regel 20), und `tests/test_value_labels.py` hat genau das
            # gefangen. Die Zahl, die etwas erklärt, ist die Trefferzahl.
            _log.error("geometry placeholder %s appears %d time(s) in the document", mark, found)
            raise InternalError(values={"count": found})
        document = document.replace(marker, b"<mesh>" + geometry + b"</mesh>", 1)
    return document


def _assembly_xml(
    parts: Sequence[AssemblyPart],
    materials: list[MaterialSlot],
    name: str,
    bed_centre: tuple[float, float] | None = None,
    layout: tuple[float, float] | None = None,
    blocker_as_part: bool = True,
    cura: bool = False,
) -> bytes:
    """Das Modell-XML einer Baugruppe: ein ``object`` je Teil, ein ``item`` je
    Teil im Build. Eine Stützsperre wird ein eigenes Teil desselben Objekts
    oder ein Bereich hinter den Dreiecken des Körpers — je nachdem, welche
    Schreibweise der Slicer liest (``slicer_keys.helpers_as_parts``). Mit
    ``cura`` tragen Körper und Sperre ihre Werte als ``cura:``-Metadaten.
    """
    plates = sorted({part.plate for part in parts})
    root = ET.Element(
        "model",
        {
            "unit": "millimeter",
            "xml:lang": "de-DE",
            "xmlns": CORE_NAMESPACE,
            "xmlns:slic3rpe": PRUSA_NAMESPACE,
            **({"xmlns:cura": CURA_NAMESPACE} if cura else {}),
        },
    )
    ET.SubElement(root, "metadata", {"name": "Application"}).text = f"{APP_NAME} {APP_VERSION}"
    ET.SubElement(root, "metadata", {"name": "slic3rpe:MmPaintingVersion"}).text = "1"
    if not blocker_as_part:
        # **PrusaSlicer liest seine Beilage erst mit dieser Angabe.** Ohne sie
        # übersprang er die Bereichsarten: An der Waschschüssel stand die
        # Stütze im Sperrkörper mit und ohne Sperre bei 91,0 m, mit ihr bei
        # 6,5 m (26.09.2026). Nur hier, in der Prusa-Schreibweise — der
        # Orca-Familie bleibt ihre eigene Beilage.
        ET.SubElement(root, "metadata", {"name": "slic3rpe:Version3mf"}).text = "1"
    if name:
        ET.SubElement(root, "metadata", {"name": "Title"}).text = name

    resources = ET.SubElement(root, "resources")
    group_id = "1"
    group = ET.SubElement(resources, "basematerials", {"id": group_id})
    # **Ein Eintrag je Extruder, auch für die freien Plätze.** Die Nummer eines
    # Slots gehört dem Auftrag (:func:`merge_slots`), und ein Dreieck zeigt mit
    # ``p1`` auf die *Stelle* in dieser Gruppe — beides passt nur zusammen,
    # wenn die Lücken der Platte hier stehen bleiben (:func:`by_extruder`).
    for position, found in enumerate(by_extruder(materials)):
        # Ein freier Platz bekommt einen namenlosen Slot: Der Name daraus ist
        # „Slot N", die Farbe die graue Vorgabe — sichtbar als Platzhalter und
        # nicht als Wahl.
        entry = found if found is not None else MaterialSlot(index=position, name="")
        ET.SubElement(
            group,
            "base",
            # ``str`` ist hier keine Höflichkeit, sondern Pflicht: Ein Slotname
            # darf ein ``TranslatableText`` sein, und ``ElementTree`` schreibt
            # nur Zeichenketten — roh übergeben brach der ganze Export mit
            # ``cannot serialize`` (gemessen am Beispiel „Schild zweifarbig",
            # 26.08.2026). In die Datei gehört ohnehin die Übersetzung: Sie
            # wird von einem Slicer gelesen, nicht von Solidon.
            {
                "name": str(entry.name) or str(_("Slot {number}", number=position)),
                "displaycolor": _colour(entry),
            },
        )

    # Wohin ein objekteigener Slot in der gemeinsamen Liste zeigt. Ohne diese
    # Übersetzung trüge Teil zwei die Farben von Teil eins.
    positions = {slot_identity(entry): entry.index for entry in materials}

    build = ET.SubElement(root, "build")
    blocks: list[tuple[str, bytes]] = []
    helpers = _helper_ids(parts) if blocker_as_part else {}
    for number, part in enumerate(parts, start=2):
        order = {slot.index: positions.get(slot_identity(slot), 0) for slot in assembly_slots(part)}
        named = {"name": part.name} if part.name else {}
        own = helpers.get(number)
        body = ET.SubElement(
            resources,
            "object",
            {
                "id": str(number if own is None else own[0]),
                "type": "model",
                "pid": group_id,
                "pindex": "0",
                **named,
            },
        )
        if cura and part.settings:
            _cura_values(body, part.settings)
        blocks.append(
            _write_geometry(
                body,
                part.mesh,
                group_id,
                order,
                bool(part.slots or part.mesh.slots),
                number=number if own is None else own[0],
                blocker=None if blocker_as_part else part.support_blocker,
            )
        )
        if own is not None and part.support_blocker is not None:
            # **Die Stützsperre ist ein eigenes Teil desselben Objekts**, so
            # wie die Orca-Familie selbst sie schreibt: ein Objekt mit zwei
            # Komponenten, und ``model_settings.config`` nennt die zweite
            # ``support_blocker`` (:func:`_settings_xml`). Bis zum 26.09.2026
            # hingen ihre Dreiecke hinter denen des Körpers, und nur die
            # Prusa-Beilage nannte den Bereich — der ElegooSlicer liest dann
            # die Orca-Beilage, übergeht die Bereichsart und druckte die Sperre
            # als Kunststoff in den Wasserkanal der Waschschüssel (161,8 statt
            # 49,5 m Modellbahn im Kanal, 22,8 g mehr).
            shield = ET.SubElement(
                resources,
                "object",
                {
                    "id": str(own[1]),
                    "type": "model",
                    "pid": group_id,
                    "pindex": "0",
                    "name": str(_("Stützsperre")),
                },
            )
            if cura:
                # Curas Stützsperre ist ein Netz mit diesem Wert — so legt
                # sein eigenes Werkzeug „Stützblocker“ sie an.
                _cura_values(shield, {slicer_keys.CURA_SUPPORT_BLOCKER: "True"})
            blocks.append(
                _write_geometry(shield, part.support_blocker, group_id, {}, number=own[1])
            )
            holder = ET.SubElement(
                resources, "object", {"id": str(number), "type": "model", **named}
            )
            components = ET.SubElement(holder, "components")
            for child in own:
                ET.SubElement(components, "component", {"objectid": str(child)})
        item = {"objectid": str(number)}
        placement = _placement(
            bed_centre,
            plate_origin(plates.index(part.plate), len(plates), layout)
            if layout is not None and len(plates) > 1
            else (0.0, 0.0),
        )
        if placement is not None:
            item["transform"] = placement
        ET.SubElement(build, "item", item)

    document = b'<?xml version="1.0" encoding="UTF-8"?>\n' + bytes(
        ET.tostring(root, encoding="utf-8")
    )
    return _fill_in(document, blocks)


def _cura_values(parent: ET.Element, values: Mapping[str, str]) -> None:
    """Werte je Objekt, wie Curas Fenster sie liest: ``cura:<schlüssel>`` in
    der ``metadatagroup`` des Objekts, vor dessen Netz (3MF-Kern, Reihenfolge
    der Kinder von ``object``)."""
    group = ET.SubElement(parent, "metadatagroup")
    for key, value in sorted(values.items()):
        ET.SubElement(group, "metadata", {"name": f"cura:{key}", "type": "xs:string"}).text = value


def _helper_ids(parts: Sequence[AssemblyPart]) -> dict[int, tuple[int, int]]:
    """Je Teil mit Stützsperre die Objektnummern von Körper und Sperre.

    Das Teil selbst behält seine Nummer im Build — ab zwei, in der Folge der
    Teile —, denn unter ihr führen beide Beilagen und die Platten es. Körper
    und Sperre bekommen Nummern hinter allen Teilen. Eine Stelle für Modell
    und Beilage, damit die zwei nicht auseinanderzählen.
    """
    ids: dict[int, tuple[int, int]] = {}
    free = len(parts) + 2
    for number, part in enumerate(parts, start=2):
        if part.support_blocker is not None and part.support_blocker.triangle_count:
            ids[number] = (free, free + 1)
            free += 2
    return ids


def _placement(bed_centre: tuple[float, float] | None, origin: tuple[float, float]) -> str | None:
    """Die Platzierungsmatrix des Standards: neun Werte Drehung, drei
    Verschiebung. ``None``, wenn nichts zu verschieben ist.

    Gedreht wird nichts. Verschoben wird aus zwei voneinander unabhängigen
    Gründen, und beide landen in derselben Matrix:

    ``bed_centre`` verschiebt Solidons Bettmitte dorthin, wo sie in den
    Koordinaten der Maschine liegt — an einer Maschine mit Nullpunkt in der
    Ecke um das halbe Bett, an einem Bett um den Ursprung gar nicht
    (``build_area.machine_shift``, RM-424). Das gilt nur für die Übergabe an
    den Slicer. Dass diese Matrix dort wirklich gelesen wird, ist gemessen:
    mit ihr und ``--arrange 0`` stehen die Teile im G-Code auf ein Zehntel
    dort, wo das Dokument sie hat.

    ``origin`` verschiebt auf die eigene Druckplatte (:func:`plate_origin`).
    Die Orca-Familie legt ihre Platten in **einem** Koordinatenraum
    nebeneinander; welche Platte gemeint ist, steht in der Beilage, aber wo
    das Teil liegt, steht hier. Das gilt **immer**, wenn es mehr als eine
    Platte gibt — auch beim Export ohne Bettkoordinaten. Sonst stünde die
    zweite Platte auf der ersten.
    """
    across = (bed_centre[0] if bed_centre else 0.0) + origin[0]
    along = (bed_centre[1] if bed_centre else 0.0) + origin[1]
    if is_zero(across) and is_zero(along):
        return None
    return f"1 0 0 0 1 0 0 0 1 {across:g} {along:g} 0"


def _model_xml(mesh: MeshData, slots: list[MaterialSlot], name: str) -> bytes:
    root = ET.Element(
        "model",
        {
            "unit": "millimeter",
            "xml:lang": "de-DE",
            "xmlns": CORE_NAMESPACE,
        },
    )
    ET.SubElement(root, "metadata", {"name": "Application"}).text = f"{APP_NAME} {APP_VERSION}"
    if name:
        ET.SubElement(root, "metadata", {"name": "Title"}).text = name

    resources = ET.SubElement(root, "resources")

    group_id = "1"
    materials = ET.SubElement(resources, "basematerials", {"id": group_id})
    order = {entry.index: position for position, entry in enumerate(slots)}
    for entry in slots:
        ET.SubElement(
            materials,
            "base",
            # ``str`` aus demselben Grund wie in :func:`write_assembly` — ein
            # übersetzbarer Slotname brachte ``ElementTree`` zu Fall.
            {
                "name": str(entry.name) or str(_("Slot {number}", number=entry.index)),
                "displaycolor": _colour(entry),
            },
        )

    body = ET.SubElement(
        resources,
        "object",
        {"id": "2", "type": "model", "pid": group_id, "pindex": "0"},
    )
    block = _write_geometry(body, mesh, group_id, order, number=2)

    build = ET.SubElement(root, "build")
    ET.SubElement(build, "item", {"objectid": "2"})

    document = b'<?xml version="1.0" encoding="UTF-8"?>\n' + bytes(
        ET.tostring(root, encoding="utf-8")
    )
    return _fill_in(document, [block])


def _colour(slot: MaterialSlot) -> str:
    values = (round(max(0.0, min(1.0, part)) * 255) for part in slot.colour or DEFAULT_COLOUR)
    return "#" + "".join(f"{value:02X}" for value in values)


def _content_types() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml" />'
        '<Default Extension="model" '
        'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml" />'
        "</Types>"
    )


def _relationships() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Relationships xmlns="{RELATIONSHIP_NAMESPACE}">'
        f'<Relationship Target="/{MODEL_PATH}" Id="rel0" Type="{MODEL_RELATIONSHIP}" />'
        "</Relationships>"
    )
