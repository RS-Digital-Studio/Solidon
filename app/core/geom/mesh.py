"""Die Mesh-Hülle um den Geometriekern (Bauplan §9, §7).

Der Rest des Kerns spricht mit dem ``Mesh``-Protokoll, nie direkt mit
``trimesh`` oder ``manifold3d``. Das hält den Kern austauschbar und macht den
B-Rep-Kern (§30) zu einer Ergänzung statt einem Umbau.

Eine ``MeshData`` gilt als unveränderlich: jede Operation gibt eine neue
zurück — das ist non-destruktives Bearbeiten, eine Ebene tiefer.
"""

from __future__ import annotations

import hashlib
import io
import itertools
import json
import math
import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Final, cast

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import CANCEL, CHOOSE, PROGRAMMING_ERRORS, GeometryError, ValidationError
from app.core.log import get_logger
from app.core.types import BoundingBox, CancelToken, Mesh
from app.core.units import EPS_GEOM, weld_digits, weld_tolerance
from app.i18n import _

_log = get_logger(__name__)

#: Endungen, die trimesh hier zu **einem** Körper liest. 3MF steht nicht
#: darin: Eine 3MF ist eine Baugruppe, und die liest die Eingangsstufe
#: (:mod:`app.core.ingest.threemf`) — was sie insgesamt öffnen kann, sagt
#: ``ingest.loader.READABLE_SUFFIXES``.
TRIMESH_SUFFIXES: tuple[str, ...] = (".stl", ".obj", ".ply", ".off", ".glb", ".gltf")


@dataclass(frozen=True, slots=True)
class MeshData:
    """Ein Körper: Eckpunkte, Dreiecke und ein Materialslot je Dreieck (§20)."""

    raw: trimesh.Trimesh
    slots: tuple[int, ...] = field(default_factory=tuple)
    cavity: MeshData | None = None
    #: Ob die belegte Innengeometrie über eine Öffnung frei liegt — *Oben öffnen*,
    #: eine gewählte Fläche — und nicht nur über Entlüftungen. Sagt nur das
    #: Aushöhlen, das sie geschnitten hat; eine Dose hat zwei Seiten an jeder
    #: Wand, ein entlüfteter Hohlraum eine (``label_ops.opposite_side``).
    cavity_open: bool = False

    def __post_init__(self) -> None:
        """Die belegte Innengeometrie trägt selbst keine weitere Innengeometrie,
        und offen sein kann nur eine, die es gibt."""
        if self.cavity is not None and self.cavity.cavity is not None:
            raise ValueError("nested_cavity")
        if self.cavity_open and self.cavity is None:
            raise ValueError("open_without_cavity")

    # --- Protokoll --------------------------------------------------------------

    @property
    def vertex_count(self) -> int:
        return len(self.raw.vertices)

    @property
    def triangle_count(self) -> int:
        return len(self.raw.faces)

    @property
    def bounds(self) -> BoundingBox:
        if self.triangle_count == 0:
            return BoundingBox((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        low, high = self.raw.bounds
        return BoundingBox(
            (float(low[0]), float(low[1]), float(low[2])),
            (float(high[0]), float(high[1]), float(high[2])),
        )

    @property
    def volume(self) -> float:
        # **Ein leeres Netz hat Volumen null und wirft nicht.** ``bounds``
        # darüber fängt den Fall seit je ab, ``volume`` und ``area`` taten es
        # nicht — dieselbe Klasse, zwei Haltungen. trimesh rechnet dort nicht
        # null, sondern wirft ``ValueError: Triangles must be (n, 3, 3)!``,
        # und das kam beim Vergleich zweier gleicher Zustände heraus, sobald
        # die Boolesche Kette ein leeres Ergebnis durchlassen durfte.
        if self.triangle_count == 0:
            return 0.0
        # **Ohne Trägheitsmomente und einmal je Netz** (RM-208, 23.09.2026):
        # ``trimesh.volume`` rechnet über ``mass_properties`` Schwerpunkt und
        # Trägheit mit — an der Lochplatte mit 203 776 Dreiecken 0,29 s, von
        # denen das Volumen 0,07 braucht. Gefragt wird es nach jedem Bohren
        # (``without_effect``). Dasselbe Integral, auf den Ursprung bezogen wie
        # bei trimesh, damit auch ein offenes Netz dieselbe Zahl behält.
        cache = getattr(self.raw, "_cache", None)
        if cache is not None:
            cache.verify()
            if "solidon_volume" in cache:
                return float(cache["solidon_volume"])
        volume = enclosed_volume(self.raw)
        if cache is not None:
            cache["solidon_volume"] = volume
        return volume

    @property
    def area(self) -> float:
        if self.triangle_count == 0:
            return 0.0
        return float(self.raw.area)

    @property
    def is_watertight(self) -> bool:
        return bool(self.raw.is_watertight)

    @property
    def component_count(self) -> int:
        """Die Zahl der zusammenhängenden Teile — einmal gezählt je Netz.

        Der Zusammenhangslauf kostet einen Gang über alle Dreiecke, und die
        Auswertung fragt ihn je merkmalsberührendem Schritt zweimal
        (``evaluate._split_findings``). Abgelegt wird die Zahl im Cache des
        Netzes selbst, der mit dessen Geometrie verfällt — ein eigenes Feld
        gibt es an dieser eingefrorenen Klasse nicht.
        """
        cache = getattr(self.raw, "_cache", None)
        if cache is not None:
            cache.verify()
            if "solidon_component_count" in cache:
                return int(cache["solidon_component_count"])
        count = len(face_components(self.raw))
        if cache is not None:
            cache["solidon_component_count"] = count
        return count

    @property
    def slot_indices(self) -> tuple[int, ...]:
        return self.slots

    def held_bytes(self, seen: set[int] | None = None, freeable: list[int] | None = None) -> int:
        """Was dieses Netz im Arbeitsspeicher hält, in Bytes (RM-567).

        Ecken und Dreiecke, dazu alles, was ``trimesh``, die Erkennung und
        der Prüfbericht in seinem Cache gemerkt haben — Kantentabellen,
        Nachbarschaften, eine Schichtanalyse — und die belegte
        Innengeometrie. Am Laptop-Riser 36 Byte je Dreieck für die
        Grunddaten und 608 für den Cache nach dem Laden (08.10.2026). Gelesen
        wird am rohen Speicher von ``trimesh``, ohne dessen Prüfsumme: Die
        Frage darf nichts rechnen. ``seen`` zählt geteilte Felder einmal.

        ``freeable`` bekommt in seinem ersten Element dazugezählt, was
        :meth:`lean` losließe: die Ableitungen aus :data:`RELEASABLE`, soweit
        nicht schon gezählt. Erst wird gezählt, was bliebe, dann das Lösbare —
        ein Feld, das beide tragen, bleibt.
        """
        from app.core.memory import held_bytes

        known = set() if seen is None else seen
        raw = self.raw
        total = held_bytes(self.slots, known)
        loose: list[object] = []
        for holder in (raw, getattr(raw, "visual", None)):
            store = getattr(getattr(holder, "_data", None), "data", None)
            cache = getattr(getattr(holder, "_cache", None), "cache", None)
            total += held_bytes(store, known)
            if not isinstance(cache, dict):
                continue
            snapshot = dict(cache)
            total += held_bytes(
                {key: value for key, value in snapshot.items() if not _releasable(key)}, known
            )
            loose.extend(value for key, value in snapshot.items() if _releasable(key))
        if self.cavity is not None:
            total += self.cavity.held_bytes(known, freeable)
        released = sum(held_bytes(value, known) for value in loose)
        if freeable is not None:
            freeable[0] += released
        return total + released

    def lean(self) -> MeshData:
        """Dieselben Ecken und Dreiecke ohne das, was sich aus ihnen neu rechnen lässt (RM-567).

        Für ältere Einträge des Ergebniscaches: Eine Auswertung liest von ihnen
        das Ergebnis, nicht Kantentabellen oder Nachbarschaften — die hielten
        am Spiderman zwei Drittel des Eintrags. Die Schichtanalyse des
        Prüfberichts bleibt (:data:`RELEASABLE`).

        **Ein neues Netz, kein geleertes.** Dasselbe Netz kann in diesem
        Augenblick ein anderer Faden lesen — Vorschau, Karte, Prüfbericht —,
        und ``trimesh`` wie die Erkennung fragen erst, ob ein Wert im Cache
        steht, und lesen ihn danach; dazwischen entfernt, käme ``None``. Die
        Felder teilt das neue Netz mit dem alten, den Speicher des Abgeleiteten
        gibt erst frei, wer das alte zuletzt loslässt. Was nicht aus der
        Geometrie folgt — der Ursprung je Dreieck, der Beleg einer starren
        Bewegung —, reist mit, ebenso Normalen, die eine Datei mitgebracht
        haben kann, und die Farben. Ein Netz mit Textur bleibt, wie es ist.
        """
        raw = self.raw
        visual = getattr(raw, "visual", None)
        kind = getattr(visual, "kind", None)
        if kind not in (None, "face", "vertex") or not hasattr(raw, "_cache"):
            return self
        # Eine Kopie des Caches in einem Zug: Ein anderer Faden kann gerade
        # etwas hinzufügen, und über das Wörterbuch selbst zu laufen, bräche
        # dann mit „dictionary changed size during iteration“ ab.
        known = dict(raw._cache.cache)
        if not any(_releasable(key) for key in known) and (
            self.cavity is None or self.cavity.lean() is self.cavity
        ):
            return self
        fresh = trimesh.Trimesh(
            vertices=raw.vertices, faces=raw.faces, process=False, validate=False
        )
        if kind is not None and visual is not None:
            fresh.visual = visual.copy()
        carried = {key: value for key, value in known.items() if not _releasable(key)}
        fresh._cache.verify()
        fresh._cache.update(carried)
        cavity = self.cavity.lean() if self.cavity is not None else None
        return MeshData(raw=fresh, slots=self.slots, cavity=cavity, cavity_open=self.cavity_open)

    # --- Aufbau -----------------------------------------------------------------

    @classmethod
    def of(cls, mesh: trimesh.Trimesh, slots: tuple[int, ...] = ()) -> MeshData:
        return cls(raw=mesh, slots=slots)

    def replacing(self, mesh: trimesh.Trimesh) -> MeshData:
        """Eine neue Hülle um einen geänderten Körper; die Slots bleiben, wo
        sie passen.

        Der Ursprung je Dreieck (:func:`refined_units`) bleibt nur, wo die
        Dreiecke dieselben sind und ihre Gestalt behalten
        (:func:`carry_refined_units`) — eine gleiche Zahl allein belegt das
        nicht."""
        slots = self.slots if len(self.slots) == len(mesh.faces) else ()
        carry_refined_units(self.raw, mesh)
        return MeshData(raw=mesh, slots=slots)

    # --- Serialisierung ---------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Verlustfreie Form für den Platten-Cache.

        STL würde Slots und die Darstellungsfarben importierter OBJ-, PLY-
        oder GLTF-Dateien verlieren. Eine Textur wird dabei auf eine Farbe je
        Dreieck abgetastet: Das reicht für die Ansicht, ohne Bilddateien oder
        Druckmaterial vorzutäuschen.
        """
        from app.core.geom.texture import face_colours

        colours = face_colours(self.raw)
        stored_colours = (
            np.clip(np.rint(colours * 255.0), 0.0, 255.0).astype(np.uint8)
            if colours is not None
            else np.empty((0, 3), dtype=np.uint8)
        )
        # **Der Ursprung je Dreieck reist mit, wo es einen gibt** (R1): Ohne
        # ihn erkennt ein von der Platte gelesenes Netz nach *Kanten
        # verfeinern* anders als in der Sitzung. Ein Netz ohne Teilung legt das
        # Feld gar nicht erst an — seine Datei bleibt, wie sie war.
        units = refined_units(self.raw)
        extra: dict[str, Any] = {} if units is None else {"refined_units": units}
        buffer = io.BytesIO()
        np.savez_compressed(
            buffer,
            vertices=np.asarray(self.raw.vertices, dtype=np.float64),
            faces=np.asarray(self.raw.faces, dtype=np.int64),
            slots=np.asarray(self.slots, dtype=np.int32),
            face_colours=stored_colours,
            cavity_vertices=(
                np.asarray(self.cavity.raw.vertices, dtype=np.float64)
                if self.cavity is not None
                else np.empty((0, 3), dtype=np.float64)
            ),
            cavity_faces=(
                np.asarray(self.cavity.raw.faces, dtype=np.int64)
                if self.cavity is not None
                else np.empty((0, 3), dtype=np.int64)
            ),
            cavity_open=np.asarray([self.cavity_open], dtype=np.bool_),
            **extra,
        )
        return buffer.getvalue()

    @classmethod
    def from_bytes(cls, payload: bytes, *, maximum_bytes: int | None = None) -> MeshData:
        if maximum_bytes is not None:
            _check_array_storage(payload, maximum_bytes)
        with np.load(io.BytesIO(payload)) as data:
            mesh = trimesh.Trimesh(vertices=data["vertices"], faces=data["faces"], process=False)
            slots = tuple(int(entry) for entry in data["slots"])
            colours = data["face_colours"] if "face_colours" in data.files else ()
            if len(colours) == len(mesh.faces):
                alpha = np.full((len(colours), 1), 255, dtype=np.uint8)
                mesh.visual = trimesh.visual.ColorVisuals(
                    mesh=mesh,
                    face_colors=np.column_stack((colours, alpha)),
                )
            cavity = None
            if "cavity_faces" in data.files and len(data["cavity_faces"]):
                cavity = cls.of(
                    trimesh.Trimesh(
                        vertices=data["cavity_vertices"],
                        faces=data["cavity_faces"],
                        process=False,
                    )
                )
            # Ein Eintrag von vor dem Feld zählt als entlüftet; das Aushöhlen
            # trägt dafür eine neue ``cache_version`` und rechnet neu.
            opened = bool(
                cavity is not None
                and "cavity_open" in data.files
                and data["cavity_open"].shape == (1,)
                and data["cavity_open"][0]
            )
            # Ein Ursprung, der nicht zu den Dreiecken passt, wird nicht
            # angelegt: Das Netz erkennt dann wie ein ungeteiltes.
            if "refined_units" in data.files:
                units = data["refined_units"]
                if units.dtype.kind in "iu" and units.shape == (len(mesh.faces),):
                    remember_refined_units(mesh, units)
        return cls(raw=mesh, slots=slots, cavity=cavity, cavity_open=opened)

    def to_stl(self) -> bytes:
        """Binäres STL, für den Export und die Übergabe an einen Slicer (§29).

        Byte für Byte, was ``trimesh.exchange.stl.export_stl`` schreibt — Kopf,
        Normalen und Ecken als float32 —, aber blockweise in einen Puffer
        (RM-567): trimesh baute das gepackte Feld und kopierte es danach
        zweimal; hier wird es einmal in den Puffer geschrieben.
        """
        from trimesh.exchange import stl

        faces = np.asarray(self.raw.faces)
        vertices = np.asarray(self.raw.vertices)
        header = np.zeros(1, dtype=stl._stl_dtype_header)
        header["face_count"] = len(faces)
        size = header.nbytes + len(faces) * stl._stl_dtype.itemsize
        buffer = bytearray(size)
        buffer[: header.nbytes] = header.tobytes()
        packed = np.frombuffer(buffer, dtype=stl._stl_dtype, offset=header.nbytes)
        if len(faces):
            packed["normals"] = self.raw.face_normals
            for begin in range(0, len(faces), _STL_BLOCK):
                end = begin + _STL_BLOCK
                packed["vertices"][begin:end] = vertices[faces[begin:end]]
        return bytes(buffer)


#: Wie viele Dreiecke :meth:`MeshData.to_stl` je Block in den Puffer schreibt.
_STL_BLOCK: Final = 262_144

_STORAGE_SUGGESTIONS = (CANCEL,)
"""Ein eingebetteter Netzstand, dem nicht zu trauen ist, hat genau einen Weg:
abbrechen — die Daten kommen aus einer geöffneten Projektdatei, und
``evaluate`` reichte den früheren Codestring als ``InternalError`` bis zum
Kunden durch. Jetzt ein Satz je Fall, die Kennung als ``constraint`` (sie
steht in der Gegenliste von ``test_errors``)."""


def _check_array_storage(payload: bytes, maximum_bytes: int) -> None:
    """Prüft Dateigröße und Arrayform vor einer Allokation aus einem Projekt."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = archive.infolist()
        if sum(entry.file_size for entry in entries) > maximum_bytes:
            raise ValidationError(
                "baked",
                _("Der eingebettete Netzstand ist größer, als eine Projektdatei tragen darf."),
                constraint="mesh_storage_too_large",
                suggestions=_STORAGE_SUGGESTIONS,
            )
        if len({entry.filename for entry in entries}) != len(entries):
            raise ValidationError(
                "baked",
                _("Der eingebettete Netzstand enthält denselben Eintrag zweimal."),
                constraint="duplicate_mesh_array",
                suggestions=_STORAGE_SUGGESTIONS,
            )
        for entry in entries:
            with archive.open(entry) as stream:
                version = np.lib.format.read_magic(stream)
                if version == (1, 0):
                    shape, _order, dtype = np.lib.format.read_array_header_1_0(stream)
                elif version == (2, 0):
                    shape, _order, dtype = np.lib.format.read_array_header_2_0(stream)
                else:
                    raise ValidationError(
                        "baked",
                        _("Der eingebettete Netzstand hat ein unbekanntes Arrayformat."),
                        constraint="unsupported_mesh_array",
                        suggestions=_STORAGE_SUGGESTIONS,
                    )
                if (
                    dtype.hasobject
                    or math.prod(shape) * dtype.itemsize != entry.file_size - stream.tell()
                ):
                    raise ValidationError(
                        "baked",
                        _("Der eingebettete Netzstand passt nicht zu seiner Größenangabe."),
                        constraint="invalid_mesh_array_size",
                        suggestions=_STORAGE_SUGGESTIONS,
                    )


def as_mesh_data(mesh: Mesh) -> MeshData:
    """Das konkrete Netz hinter dem Protokoll.

    Operationen deklarieren ``Mesh``, denn das ist der Vertrag (§9) — aber die
    Dreiecksarbeit braucht den Kern. Hier wird ein Körper der falschen Sorte
    mit klarer Meldung abgewiesen (§30).
    """
    if isinstance(mesh, MeshData):
        return mesh
    # §30: der Weg von B-Rep zu Mesh steht jederzeit offen — eine Mesh-Op auf
    # einem exakten Körper funktioniert also: auf seiner Tessellation, und das
    # Objekt kommt danach als Mesh markiert heraus, denn das ist es jetzt.
    converted = getattr(mesh, "to_mesh", None)
    if callable(converted):
        result = converted()
        if isinstance(result, MeshData):
            return result
    raise GeometryError(
        _("Diese Operation arbeitet nur auf Netzen."),
        detail=_("Das Objekt liegt in einer anderen Darstellung vor."),
        # Auch hier nicht die Vorgabe: Netzreparatur macht aus einem exakten
        # Körper kein Netz, und Stellen nennt dieser Fehler keine. Was hilft,
        # ist eine andere Auswahl — der Körper, an dem die Operation arbeiten
        # kann.
        suggestions=(CHOOSE, CANCEL),
    )


#: Unter diesem Schlüssel trägt ein Netz im Cache von ``trimesh`` je Dreieck
#: seinen Ursprung vor *Kanten verfeinern* samt dessen Abdruck
#: (:func:`refined_units`). Er lebt und stirbt mit der Geometrie wie
#: ``face_adjacency``.
_REFINED_UNITS_KEY: Final = "solidon_refined_units"


def refined_units(body: trimesh.Trimesh) -> np.ndarray | None:
    """Je Dreieck sein Ursprung vor *Kanten verfeinern* — ``None`` an einem ungeteilten Netz.

    **Die Erkennung zählt Dreiecke, und die Teilung vervielfacht sie**
    (Durchsicht 0.5.1, R1). *Kanten verfeinern* ändert die Form nicht, aber
    jede Regel, die an einer Dreieckszahl hängt, liest das feinere Netz
    anders: Nach 1 mm und einer Bohrung zerfiel die gerundete Seite des
    Screen-Covers in 50 Verrundungen. Der Schritt selbst trägt seine Merkmale
    über den Herkunftsvermerk weiter (``perceive.features.note_refinement``);
    der nächste Schritt baut ein neues Netz, und dort erkennt die Erkennung
    frisch. Deshalb reist der Ursprung als Eigenschaft des Netzes mit — durch
    die Boolesche Kette über die Dreiecke, die sie nicht berührt hat
    (``geom.attributes.carry_refined_units``), und durch jede starre Bewegung
    (:meth:`MeshData.replacing`) —, und die Erkennung zählt die Stücke eines
    Ursprungs als eines (``perceive.features.face_count``).

    Gleiche Nummern heißen: Stücke **eines** Dreiecks vor der Teilung. ``-1``
    trägt ein Dreieck, das keine Teilung hervorgebracht hat — eine
    Schnittfläche, die Wand einer Bohrung —; es zählt für sich.
    """
    cache = getattr(body, "_cache", None)
    if cache is None or _REFINED_UNITS_KEY not in cache.cache:
        return None
    cache.verify()
    held = cache.cache.get(_REFINED_UNITS_KEY)
    if held is None or len(held[0]) != len(body.faces):
        return None
    return cast(np.ndarray, held[0])


def refined_units_key(body: trimesh.Trimesh) -> bytes | None:
    """Der Abdruck des Ursprungs je Dreieck (:func:`refined_units`) — für den Abdruck
    des Netzes, an dem die Erkennung ihre Antwort merkt."""
    if refined_units(body) is None:
        return None
    return cast(bytes, body._cache.cache[_REFINED_UNITS_KEY][1])


def remember_refined_units(body: trimesh.Trimesh, units: np.ndarray | None) -> None:
    """Legt den Ursprung je Dreieck an ein **frisch gebautes** Netz (:func:`refined_units`).

    Frisch heißt: Noch hat niemand dieses Netz nach etwas gefragt, das am
    Ursprung hängt — der Merker der Erkennung hält seine Antworten je Körper,
    und eine Antwort von davor zählte die Stücke einzeln. Die Aufrufer bauen
    das Netz unmittelbar davor: *Kanten verfeinern*, die Boolesche Kette,
    :meth:`MeshData.replacing`, das Verschweißen und der Plattencache.

    Ohne ein Dreieck mit Ursprung wird nichts abgelegt: Ein Netz, in dem nichts
    geteilt ist, zählt ohnehin jedes Dreieck für sich.
    """
    cache = getattr(body, "_cache", None)
    if units is None or cache is None:
        return
    held = np.array(units, dtype=np.int64, copy=True)
    if held.shape != (len(body.faces),) or not bool((held >= 0).any()):
        return
    held.flags.writeable = False
    digest = hashlib.blake2b(held.tobytes(), digest_size=16).digest()
    cache.verify()
    cache[_REFINED_UNITS_KEY] = (held, digest)


def carry_refined_units(source: trimesh.Trimesh, target: trimesh.Trimesh) -> None:
    """Gibt den Ursprung je Dreieck weiter, wenn ``target`` dieselben Dreiecke in
    derselben Gestalt trägt.

    Dieselben Dreiecke: dieselben Eckennummern je Dreieck. Dieselbe Gestalt:
    jede Seite so lang wie vorher, bis auf einen gemeinsamen Maßstab — eine
    starre Bewegung, ein gleichmäßiges Skalieren, der Weg einer Bohrung in
    ihren Rahmen und zurück (``prepare.drill``). Dann liegen die Stücke eines
    Ursprungs weiter in seiner Ebene, und die Erkennung darf sie als eines
    lesen.

    **Ein Netz, dessen Ecken sich gegeneinander bewegt haben, trägt keinen
    Ursprung weiter** — Glätten, Biegen, Formen, Verschieben einzelner Ecken:
    Die Stücke eines Ursprungs liegen danach nicht mehr in einer Ebene, und
    wer sie als eines läse, verschmierte die Krümmung über den ganzen
    Ursprung. Gleiche Dreieckszahl allein ist kein Beleg (dieselbe Lehre wie
    bei den Slots, ``boolean._keep_slots``).
    """
    cache = getattr(source, "_cache", None)
    if cache is None or _REFINED_UNITS_KEY not in cache.cache or target is source:
        return
    units = refined_units(source)
    if units is None or refined_units(target) is not None:
        return
    faces = np.asarray(source.faces)
    if faces.shape != np.asarray(target.faces).shape or not np.array_equal(faces, target.faces):
        return
    before = _side_lengths(np.asarray(source.vertices, dtype=np.float64)[faces])
    after = _side_lengths(np.asarray(target.vertices, dtype=np.float64)[faces])
    total = float(before.sum())
    if total <= 0.0:
        return
    scale = float(after.sum()) / total
    # Eine Rechengrenze, keine Geometrietoleranz: Eine starre Bewegung
    # verschiebt die letzten Stellen, jede Verformung Mikrometer und mehr.
    if float(np.abs(after - before * scale).max()) > EPS_GEOM * max(1.0, scale):
        return
    remember_refined_units(target, units)


def _side_lengths(triangles: np.ndarray) -> np.ndarray:
    """Die drei Seitenlängen je Dreieck, mit Grundrechenarten und ``sqrt``."""
    sides = np.empty(triangles.shape[:2], dtype=np.float64)
    for column, (first, second) in enumerate(((0, 1), (1, 2), (2, 0))):
        step = triangles[:, second] - triangles[:, first]
        sides[:, column] = np.sqrt((step * step).sum(axis=1))
    return sides


def fully_stitched(mesh: trimesh.Trimesh) -> bool:
    """Hat schon jede Kante ihren Partner? Dann ist am Ort nichts mehr zu holen.

    Drei Kanten je Dreieck, jede von zwei Dreiecken geteilt — ein geschlossenes,
    zusammengeführtes Netz hat also ``3F/2`` Nachbarschaften. Wer die erreicht,
    kann durch Zusammenlegen keine Verbindung dazugewinnen.

    Die Frage kostet nichts: ``face_adjacency`` braucht ohnehin jeder, der hier
    vorbeikommt, und ``trimesh`` legt sie am Körper ab. Das ist der Unterschied
    zu einer Abkürzung, die selbst rechnet, was sie abkürzen soll.

    **Wozu sie da ist**, steht in einer Zahl: Das Zusammenlegen der Ecken einer
    Kugel mit 327 680 Dreiecken kostet kalt rund 160 ms und findet nichts. Ohne
    diese Zeile lag die Merkmalserkennung dort bei 733 ms gegen 571 vorher —
    achtundzwanzig Prozent für eine Antwort, die schon dastand.
    """
    return len(mesh.faces) > 0 and 2 * len(mesh.face_adjacency) >= 3 * len(mesh.faces)


def unique_edges(
    edges: np.ndarray, *, return_counts: bool = False, return_inverse: bool = False
) -> tuple[np.ndarray, ...]:
    """Die verschiedenen Kanten einer Kantenliste — über eine Zahl je Kante.

    ``np.unique(edges, axis=0)`` sortiert Zeilen als Strukturen und ist an
    180 000 Kanten viermal langsamer als dieselbe Frage an einer Kantennummer
    ``a·n + b`` (gemessen am 22.09.2026: 70 gegen 16 ms). Die Randringe der
    Merkmalsketten stellten sie je Facette, und an der unterteilten Lochplatte
    kostete jeder Szenenaufbau im Objektbaum 0,4 s allein damit.

    Die Kanten werden je Zeile aufsteigend sortiert, die Nummer ist eindeutig,
    solange ``n²`` in ``int64`` passt — bei drei Milliarden Ecken. Zurück
    kommen die Kanten selbst, in derselben Reihenfolge, die ``np.unique`` über
    die Achse liefern würde, dann auf Wunsch Zähler und Rückabbildung.
    """
    ordered = np.sort(np.asarray(edges, dtype=np.int64).reshape(-1, 2), axis=1)
    if not len(ordered):
        results: list[np.ndarray] = [ordered]
        if return_inverse:
            results.append(np.zeros(0, dtype=np.int64))
        if return_counts:
            results.append(np.zeros(0, dtype=np.int64))
        return tuple(results)
    width = int(ordered.max()) + 1
    codes = ordered[:, 0] * width + ordered[:, 1]
    _codes, first, inverse, counts = np.unique(
        codes, return_index=True, return_inverse=True, return_counts=True
    )
    results = [ordered[first]]
    if return_inverse:
        results.append(np.asarray(inverse).reshape(-1))
    if return_counts:
        results.append(counts)
    return tuple(results)


def stable_normals(mesh: trimesh.Trimesh) -> tuple[np.ndarray, np.ndarray]:
    """Einheitsnormale und Fläche je Dreieck — auf jeder Maschine dieselben Bits.

    **Nicht ``face_normals`` und ``area_faces`` von ``trimesh``.** Beide
    normieren über ``np.dot(v * v, [1, 1, 1])``, und das geht durch BLAS: Die
    letzte Stelle hängt an der CPU (RM-187). Wo aus Normalen und Flächen eine
    **Entscheidung** wird — welche Lage die beste ist, welche Fläche aufliegt
    —, reicht das, um auf zwei Maschinen zwei verschiedene Teile zu drucken.
    Hier entstehen beide aus Kreuzprodukt, Quadratsumme und Wurzel, jede als
    eigene NumPy-Operation und damit nach IEEE-754 gerundet.

    Ein Dreieck ohne Fläche bekommt die Normale ``(0, 0, 0)``, wie bei
    ``trimesh``. Das Ergebnis liegt im Cache des Netzes und verfällt mit
    dessen Geometrie.
    """
    cache = getattr(mesh, "_cache", None)
    if cache is not None:
        cache.verify()
        if "solidon_stable_normals" in cache:
            return cast(tuple[np.ndarray, np.ndarray], cache["solidon_stable_normals"])
    found = _normals_and_areas(np.asarray(mesh.triangles, dtype=np.float64))
    if cache is not None:
        cache["solidon_stable_normals"] = found
    return found


def stable_areas(mesh: trimesh.Trimesh, faces: np.ndarray) -> np.ndarray:
    """Die Flächen der Dreiecke ``faces`` — dieselben Bits wie :func:`stable_normals`.

    Wer nur wenige Dreiecke fragt, bekommt sie ohne das ganze Netz zu rechnen
    (RM-224: Das Auflösen verzweigter Kanten wog am Piratenschiff vier
    Dreiecke und rechnete dafür 1,2 Millionen Normalen). Jede Zahl entsteht
    elementweise, eine Fläche hängt also nicht daran, welche Dreiecke sonst
    gefragt werden. Steht die Antwort für alle schon im Cache, kommt sie von
    dort.
    """
    cache = getattr(mesh, "_cache", None)
    if cache is not None:
        cache.verify()
        if "solidon_stable_normals" in cache:
            normals_and_areas = cast(tuple[np.ndarray, np.ndarray], cache["solidon_stable_normals"])
            return np.asarray(normals_and_areas[1][faces])
    corners = np.asarray(mesh.vertices, dtype=np.float64)[
        np.asarray(mesh.faces, dtype=np.int64)[np.asarray(faces, dtype=np.int64)]
    ]
    return _normals_and_areas(corners.reshape(-1, 3, 3))[1]


def _normals_and_areas(corners: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Einheitsnormale und Fläche je Dreieck ``(n, 3, 3)``, elementweise (RM-187)."""
    if not len(corners):
        return np.zeros((0, 3)), np.zeros(0)
    cross = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    doubled = np.sqrt(
        cross[:, 0] * cross[:, 0] + cross[:, 1] * cross[:, 1] + cross[:, 2] * cross[:, 2]
    )
    usable = doubled > 0.0
    normals = np.zeros_like(cross)
    normals[usable] = cross[usable] / doubled[usable, None]
    return normals, doubled / 2.0


_SQRT3: Final = 1.7320508075688772
_TAN_PI_12: Final = 0.2679491924311227
_PI_6: Final = 0.5235987755982988
_PI_2: Final = 1.5707963267948966
#: ``(-1)ⁿ/(2n+1)`` bis ``n = 14`` — für ``|t| ≤ tan(π/12)`` liegt der erste
#: weggelassene Term unter 10⁻¹⁸.
_ATAN_TERMS: Final = tuple(
    (1.0 if order % 2 == 0 else -1.0) / (2 * order + 1) for order in range(15)
)


def _stable_arctan(values: np.ndarray) -> np.ndarray:
    """``arctan(t)`` für ``t ≥ 0`` aus Grundrechenarten — auf jeder Maschine
    dieselben Bits (RM-187).

    Zweimal exakt reduziert — ``t > 1`` über ``π/2 - arctan(1/t)``, ``t >
    tan(π/12)`` über ``π/6 + arctan((t√3 - 1)/(t + √3))`` —, dann die Reihe im
    Horner-Schema. Jede Operation ist eine eigene NumPy-Operation und damit
    nach IEEE-754 gerundet; ``np.arctan`` dagegen wählt seine Umsetzung nach
    der CPU. Die Abweichung zur wahren Funktion liegt bei wenigen Einheiten
    der letzten Stelle.
    """
    t = np.asarray(values, dtype=np.float64)
    inverse = t > 1.0
    with np.errstate(divide="ignore"):
        s = np.where(inverse, 1.0 / np.where(inverse, t, 1.0), t)
    shifted = s > _TAN_PI_12
    s = np.where(shifted, (s * _SQRT3 - 1.0) / (s + _SQRT3), s)
    square = s * s
    total = np.full_like(s, _ATAN_TERMS[-1])
    for coefficient in reversed(_ATAN_TERMS[:-1]):
        total = total * square + coefficient
    result = s * total
    result = np.where(shifted, _PI_6 + result, result)
    return np.asarray(np.where(inverse, _PI_2 - result, result))


#: Bis zu welchem Betrag :func:`stable_sin_cos` einen Winkel annimmt. Die Reihe
#: hält dort die volle Stellenzahl; mehr als eine halbe Drehung je Seite
#: braucht keine ihrer Aufrufer.
STABLE_ANGLE_LIMIT: Final = 4.0


def stable_sin_cos(angles: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
    """Sinus und Kosinus vieler Winkel (Bogenmaß) — auf jeder Maschine dieselben Bits.

    Die Taylorreihen nach Horner, fünfzehn Glieder, elementweise in
    Grundrechenarten: ``np.sin`` und ``math.sin`` runden je nach CPU anders
    (RM-187), und :func:`app.core.units.exact_sin` rechnet je Punkt in
    ``decimal`` — für die zehntausend Ecken einer gebogenen Schrift zu teuer.
    Bis :data:`STABLE_ANGLE_LIMIT` ist der Restfehler kleiner als eine Stelle
    (``4^31 / 31!`` < ``1e-15``); darüber ist es eine Absage, keine Näherung.
    """
    t = np.asarray(angles, dtype=np.float64)
    if t.size and float(np.max(np.abs(t))) > STABLE_ANGLE_LIMIT:
        raise ValueError("stable_sin_cos takes angles up to four radians")
    square = t * t
    sine = np.ones_like(t)
    cosine = np.ones_like(t)
    for k in range(15, 0, -1):
        sine = 1.0 - square / float((2 * k) * (2 * k + 1)) * sine
        cosine = 1.0 - square / float((2 * k - 1) * (2 * k)) * cosine
    return t * sine, cosine


def row_dots(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Das Skalarprodukt je Zeile zweier ``(n, 3)``-Felder — ``einsum("ij,ij->i")`` ohne FMA.

    Drei Produkte und zwei Summen je Zeile, jede als eigene NumPy-Operation:
    ``np.einsum`` zieht auf ARM Produkt und Summe zu einer FMA zusammen, auf
    x86 nicht (RM-187).
    """
    a = np.asarray(first, dtype=np.float64)
    b = np.asarray(second, dtype=np.float64)
    return np.asarray(a[..., 0] * b[..., 0] + a[..., 1] * b[..., 1] + a[..., 2] * b[..., 2])


#: Was ``trimesh`` bei einer reinen Verschiebung behält (``Trimesh.apply_transform``
#: ohne Drehung): Normalen und Topologie hängen nicht an der Lage.
_KEPT_BY_A_SHIFT: Final = (
    "face_normals",
    "vertex_normals",
    "face_adjacency",
    "face_adjacency_edges",
    "face_adjacency_unshared",
    "edges",
    "edges_face",
    "edges_sorted",
    "edges_unique",
    "edges_unique_idx",
    "edges_unique_inverse",
    "edges_sparse",
    "body_count",
    "faces_unique_edges",
    "euler_number",
)


def shift_body(body: object, offset: Sequence[float] | np.ndarray) -> None:
    """Ein Netz an Ort und Stelle verschieben — der Ersatz für ``apply_translation``.

    ``trimesh`` verschiebt über ein Matrixprodukt mit einer Einheitsdrehung.
    Das ist rechnerisch exakt, geht aber durch BLAS, und der Rauschtest kann es
    von einem echten Produkt nicht unterscheiden (RM-187); elementweise bleibt
    der Weg prüfbar. Gemerkt bleibt, was ``trimesh`` bei einer Verschiebung
    behält (:data:`_KEPT_BY_A_SHIFT`): Neu gerechnete Normalen trügen die
    letzte Stelle der neuen Lage, und Kopieren und Versetzen gesenkter
    Bohrungen entschieden danach anders.
    """
    raw = cast("trimesh.Trimesh", body)
    cache = getattr(raw, "_cache", None)
    kept: dict[str, Any] = {}
    if cache is not None:
        cache.verify()
        kept = {name: cache.cache[name] for name in _KEPT_BY_A_SHIFT if name in cache.cache}
    raw.vertices = np.asarray(raw.vertices, dtype=np.float64) + np.asarray(offset, dtype=np.float64)
    if kept and cache is not None:
        cache.verify()
        cache.cache.update(kept)
        cache.id_set()


def periodic_sin_cos(
    angles: np.ndarray | Sequence[float] | float,
) -> tuple[np.ndarray, np.ndarray]:
    """:func:`stable_sin_cos` für Winkel jeder Größe — erst um ganze Umläufe gefaltet.

    Der Winkel abzüglich der nächsten ganzen Zahl von Umläufen landet in
    ``[-π, π]``; das Abziehen ist eine Grundrechenart und damit auf jeder
    Maschine gleich gerundet. Für Lagen, die über die Naht eines Zylinders
    reichen, ohne dort eine Absage zu verdienen (RM-187).
    """
    t = np.asarray(angles, dtype=np.float64)
    turns = np.round(t / (2.0 * math.pi))
    return stable_sin_cos(t - turns * (2.0 * math.pi))


def stable_arctan2(y: np.ndarray | float, x: np.ndarray | float) -> np.ndarray:
    """``arctan2`` aus :func:`_stable_arctan` — auf jeder Maschine dieselben Bits (RM-187).

    Der Winkel in ``(-π, π]`` über den Arkustangens des Verhältnisses der
    kleineren zur größeren Koordinate, die Quadranten über Vorzeichen und
    ``π/2``-Ergänzung. Der Ursprung bekommt null wie bei ``np.arctan2``
    (dort mit Vorzeichen der Null; hier ohne, denn keine Lage hängt daran).
    """
    yy = np.asarray(y, dtype=np.float64)
    xx = np.asarray(x, dtype=np.float64)
    ay, ax = np.abs(yy), np.abs(xx)
    steep = ay > ax
    big = np.where(steep, ay, ax)
    small = np.where(steep, ax, ay)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(big > 0.0, small / np.where(big > 0.0, big, 1.0), 0.0)
    angle = _stable_arctan(ratio)
    angle = np.where(steep, _PI_2 - angle, angle)
    angle = np.where(xx < 0.0, math.pi - angle, angle)
    return np.asarray(np.where(yy < 0.0, -angle, angle))


def stable_arccos(values: np.ndarray | float) -> np.ndarray:
    """``arccos`` aus Grundrechenarten und :func:`_stable_arctan` — auf jeder
    Maschine dieselben Bits (RM-166).

    ``arccos(x) = arctan(√(1 - x²) / x)`` für ``x > 0`` und ``π`` minus
    dasselbe für ``x < 0``; die Wurzel über ``(1 - x)(1 + x)``, damit sie an
    den Rändern nicht auslöscht. Eingaben außerhalb von ``[-1, 1]`` werden auf
    den Rand gelegt, wie ``np.clip`` vor ``np.arccos`` es tat. ``np.arccos``
    und ``math.acos`` wählen ihre Umsetzung nach der CPU bzw. der
    Mathematikbibliothek der Plattform.
    """
    x = np.clip(np.asarray(values, dtype=np.float64), -1.0, 1.0)
    rest = np.sqrt((1.0 - x) * (1.0 + x))
    size = np.abs(x)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(size > 0.0, rest / np.where(size > 0.0, size, 1.0), 0.0)
    angle = _stable_arctan(ratio)
    return np.asarray(np.where(x > 0.0, angle, np.where(x < 0.0, math.pi - angle, _PI_2)))


def stable_vertex_normals(mesh: trimesh.Trimesh) -> np.ndarray:
    """Die Eckennormalen, gewichtet mit den Winkeln der Dreiecke an der Ecke —
    wie ``vertex_normals`` von ``trimesh``, aber auf jeder Maschine dieselben Bits.

    ``trimesh`` misst die Winkel mit ``np.arccos`` und normiert über BLAS;
    beides rundet je nach CPU anders (RM-187). Wo eine Eckennormale zu
    Geometrie wird — *Offene Fläche schließen* versetzt jede Ecke entlang
    ihrer Normalen —, trug damit jede Ecke der Innenhaut die letzte Stelle der
    Maschine. Hier: Normalen aus :func:`stable_normals`, Winkel als
    ``2·arctan(|a - b| / |a + b|)`` der Kanteneinheitsvektoren über
    :func:`_stable_arctan`, die Summe je Ecke in fester Reihenfolge. Ein
    Dreieck mit einem Winkel unter 10⁻⁸ zählt nicht — dieselbe Regel wie bei
    ``trimesh``.
    """
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    summed = np.zeros((len(vertices), 3), dtype=np.float64)
    if not len(faces):
        return summed
    normals, _areas = stable_normals(mesh)
    return _angle_weighted(vertices, faces, normals, summed)


def stable_vertex_normals_at(mesh: trimesh.Trimesh, wanted: np.ndarray) -> np.ndarray:
    """:func:`stable_vertex_normals` für einige Ecken — dieselben Bits, ohne den
    Rest des Netzes.

    Gerechnet wird nur an den Dreiecken, die eine gewünschte Ecke tragen, in
    ihrer Reihenfolge im Netz: Die Summe je Ecke läuft dann genau so wie über
    alle. Die Wandprobe eines Formschritts fragt 256 Ecken eines Netzes mit
    Hunderttausenden (RM-419).
    """
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    wanted = np.asarray(wanted, dtype=np.int64)
    summed = np.zeros((len(vertices), 3), dtype=np.float64)
    if not len(faces) or not len(wanted):
        return np.asarray(summed[wanted])
    marked = np.zeros(len(vertices), dtype=bool)
    marked[wanted] = True
    carrying = np.flatnonzero(marked[faces].any(axis=1))
    normals, _areas = _normals_and_areas(vertices[faces[carrying]])
    return np.asarray(_angle_weighted(vertices, faces[carrying], normals, summed)[wanted])


def _angle_weighted(
    vertices: np.ndarray, faces: np.ndarray, normals: np.ndarray, summed: np.ndarray
) -> np.ndarray:
    """Die Normalen ``normals`` der Dreiecke ``faces``, mit ihren Winkeln je Ecke
    in ``summed`` aufsummiert und normiert (:func:`stable_vertex_normals`)."""
    corners = vertices[faces]
    angles = np.zeros((len(faces), 3), dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        for corner in range(2):
            first = corners[:, (corner + 1) % 3] - corners[:, corner]
            second = corners[:, (corner + 2) % 3] - corners[:, corner]
            first_length = np.sqrt((first * first).sum(axis=1))[:, None]
            second_length = np.sqrt((second * second).sum(axis=1))[:, None]
            a = np.where(first_length > 0.0, first / first_length, 0.0)
            b = np.where(second_length > 0.0, second / second_length, 0.0)
            apart = a - b
            together = a + b
            across = np.sqrt((apart * apart).sum(axis=1))
            along = np.sqrt((together * together).sum(axis=1))
            ratio = np.where(along > 0.0, across / np.where(along > 0.0, along, 1.0), np.inf)
            angles[:, corner] = 2.0 * _stable_arctan(ratio)
    angles[:, 2] = np.pi - angles[:, 0] - angles[:, 1]
    angles[(angles < 1e-8).any(axis=1) | ~np.isfinite(angles).all(axis=1)] = 0.0
    for corner in range(3):
        np.add.at(summed, faces[:, corner], normals * angles[:, corner, None])
    lengths = np.sqrt((summed * summed).sum(axis=1))
    usable = lengths > 0.0
    summed[usable] /= lengths[usable, None]
    return summed


@dataclass(frozen=True)
class IntegerGrid:
    """Nichtnegative Werte auf einem gemeinsamen Raster als ganze Zahlen —
    damit jede Teilsumme exakt und von der Reihenfolge unabhängig ist.

    Eine Gleitkommasumme hängt an der Reihenfolge ihrer Summanden, und zwei
    spiegelgleiche Lagen eines symmetrischen Teils tragen dieselben Flächen in
    anderer Reihenfolge: Ihre Summen unterschieden sich in der letzten Stelle,
    und welche Lage gewann, entschied das Rauschen und nicht die Richtung, die
    als Gleichstandsregel dahinter steht. Hier wird jeder Wert **einmal** auf
    ein Raster gelegt, dessen Schritt ``2⁻⁶⁰`` der größtmöglichen Summe ist;
    eine Summe ganzer Zahlen ist exakt — gleich in welcher Reihenfolge, gleich
    auf welcher Maschine —, und der Rasterfehler liegt achtzehn Stellen unter
    der Summe.
    """

    steps: np.ndarray
    exponent: int

    @classmethod
    def of(cls, values: np.ndarray, *, count: int | None = None) -> IntegerGrid:
        """``count`` zählt auch ausgelassene Nullen; Raster und Summe bleiben gleich."""
        raw = np.abs(np.asarray(values, dtype=np.float64))
        if count is not None and count < len(raw):
            raise ValueError("count must include every stored value")
        largest = float(raw.max()) if len(raw) else 0.0
        if not largest or not math.isfinite(largest):
            return cls(np.zeros(len(raw), dtype=np.int64), 0)
        exponent = 60 - math.frexp(float(len(raw) if count is None else count) * largest)[1]
        return cls(np.rint(np.ldexp(raw, exponent)).astype(np.int64), exponent)

    def sums(self, masks: np.ndarray) -> np.ndarray:
        """Je Zeile von ``masks`` die Summe der gewählten Werte."""
        chosen = np.where(np.asarray(masks, dtype=bool), self.steps, 0).sum(axis=-1)
        return np.ldexp(np.asarray(chosen, dtype=np.float64), -self.exponent)

    def total(self) -> float:
        """Die Summe aller Werte."""
        return float(np.ldexp(float(int(self.steps.sum())), -self.exponent))


@dataclass(frozen=True)
class EdgeTable:
    """Die Kanten eines Netzes, einmal gezählt: ``inverse`` ordnet jede Zeile
    von ``edges_sorted`` (drei je Dreieck, in Dreiecksreihenfolge) ihrer
    Kante zu, ``counts`` sagt je Kante, wie viele Dreiecke sie tragen."""

    unique: np.ndarray
    inverse: np.ndarray
    counts: np.ndarray

    def rows(self, count: int) -> np.ndarray:
        """Die Zeilen der Kanten mit genau ``count`` Dreiecken, aufsteigend."""
        return np.flatnonzero(self.counts[self.inverse] == count)

    def face_pairs(self) -> np.ndarray:
        """Je Kante mit genau zwei Dreiecken das Paar, kleinere Nummer zuerst.

        Dieselbe Menge wie trimeshs ``face_adjacency`` (ohne ein Dreieck, das
        mit sich selbst eine Kante teilt), ohne dafür alle Kanten ein zweites
        Mal zu gruppieren. Die Reihenfolge der Paare ist eine andere; wer
        daraus Zusammenhänge zählt, bekommt dieselben Teile.
        """
        rows = self.rows(2)
        if not len(rows):
            return np.zeros((0, 2), dtype=np.int64)
        paired = rows[np.argsort(self.inverse[rows], kind="stable")] // 3
        pairs = np.sort(paired.reshape(-1, 2), axis=1)
        return np.asarray(pairs[pairs[:, 0] != pairs[:, 1]])


#: Wo :func:`edge_table` die Zählung im Cache des Netzes ablegt.
_EDGE_TABLE_KEY: Final = "solidon_edge_table"

#: Was :meth:`MeshData.lean` nicht mitnimmt: was
#: ``trimesh`` aus Ecken und Dreiecken ableitet und groß ist, und Solidons
#: eigene Ableitungen — Kantentabelle, Nachbarindex, Eckenfächer und -rang,
#: Normalen, Fleckennachbarschaft. Nicht darin: ``face_normals`` und
#: ``vertex_normals``, die eine Datei mitbringen kann, und alles, was ein Netz
#: über seine Herkunft trägt. Ebenfalls nicht darin, obwohl ableitbar, was der
#: Bericht nach dem Zurücknehmen am gezeigten Stand fragt: die Teile
#: (:func:`face_components`) und ``area_faces``, je 8 Byte je Dreieck — ohne
#: sie rechnete er am Spiderman 0,4 s je Schritt neu (Review L, G9) —, und die
#: Schichtanalyse des Prüfberichts (``slice.findings``): Ohne sie schnitt er
#: nach dem Zurücknehmen neu, am Spiderman 52 s; als Felder hält sie seit
#: RM-595 nur 17 bis 31 MB (Nachprüfung L, M-2).
RELEASABLE: Final = frozenset(
    {
        "triangles",
        "triangles_cross",
        "triangles_center",
        "face_angles",
        "edges",
        "edges_face",
        "edges_sorted",
        "edges_unique",
        "edges_unique_idx",
        "edges_unique_inverse",
        "edges_unique_length",
        "face_adjacency",
        "face_adjacency_edges",
        "face_adjacency_unshared",
        "face_adjacency_angles",
        "face_adjacency_projections",
        "face_adjacency_span",
        "face_adjacency_radius",
        "face_adjacency_convex",
        "facets",
        "facets_area",
        "facets_normal",
        "facets_origin",
        "facets_boundary",
        "vertex_faces",
        "vertex_neighbors",
        "vertex_degree",
        _EDGE_TABLE_KEY,
        "solidon_neighbour_index",
        "solidon_vertex_rank",
        "solidon_vertex_faces",
        "solidon_stable_normals",
        "solidon_patch_adjacency",
    }
)


def _releasable(key: object) -> bool:
    return isinstance(key, str) and key in RELEASABLE


def edge_table(body: trimesh.Trimesh) -> EdgeTable:
    """Die Kantenzählung eines Netzes — einmal je Netz, im Cache des Netzes.

    Gezählt wird über eine Kantennummer (:func:`unique_edges`); der Cache
    verfällt mit der Geometrie. Offene Ränder, Verzweigungen, Randringe und
    Sanduhren der Reparatur lesen sie, die Teilezerlegung
    (:func:`face_components`) liest daraus die Nachbarschaft.

    **Und dieselbe Zählung beantwortet ``is_watertight``** (RM-224). trimesh
    gruppiert dafür alle Kanten ein zweites Mal — am Piratenschiff eine halbe
    Sekunde je Netz. Die Antwort und der Umlaufsinn, den trimesh daneben
    ablegt, kommen deshalb von hier in dessen Cache, mit trimeshs Definition
    (:func:`trimesh.graph.is_watertight`): dicht, wenn jede Kante genau zwei
    Dreiecke trägt; einheitlich gewickelt, wenn jede solche Kante in ihren
    zwei Dreiecken gegenläufig steht — gezählt über die Richtung je Zeile,
    ohne die Paare zu sortieren. Gegen trimesh geprüft an allen 485 Körpern
    aus ``F:\\3D Dateien``, roh und verschweißt.
    """
    cache = getattr(body, "_cache", None)
    if cache is not None and _EDGE_TABLE_KEY in cache:
        return cast(EdgeTable, cache[_EDGE_TABLE_KEY])
    unique, inverse, counts = unique_edges(
        np.asarray(body.edges_sorted, dtype=np.int64), return_inverse=True, return_counts=True
    )
    table = EdgeTable(unique=unique, inverse=inverse, counts=counts)
    _remember_edges(body, table)
    return table


def _remember_edges(body: trimesh.Trimesh, table: EdgeTable) -> None:
    """Legt die Kantenzählung in den Cache des Netzes, samt Dichtheit und Umlaufsinn.

    Eine Stelle für beide Wege — gezählt (:func:`edge_table`) und abgeleitet
    (:func:`without_faces`, :func:`carry_appended_edges`) —, damit trimeshs
    Antwort nie aus zwei Rechnungen kommt.
    """
    cache = getattr(body, "_cache", None)
    if cache is None:
        return
    cache[_EDGE_TABLE_KEY] = table
    counts, inverse = table.counts, table.inverse
    if len(counts) and "is_watertight" not in cache:
        directed = np.asarray(body.edges, dtype=np.int64)
        up = np.bincount(inverse, weights=directed[:, 0] < directed[:, 1], minlength=len(counts))
        down = np.bincount(inverse, weights=directed[:, 0] > directed[:, 1], minlength=len(counts))
        pairs = counts == 2
        cache["is_watertight"] = bool(np.all(pairs))
        cache["is_winding_consistent"] = bool(np.array_equal(up[pairs], down[pairs]))


def remember_edge_table(body: trimesh.Trimesh, table: EdgeTable) -> None:
    """Eine schon gezählte Kantenzählung am Netz ablegen — sie muss zu seinen Dreiecken passen.

    Für den, der die Zählung ohnehin braucht, bevor das Netz entsteht: Das
    Verschweißen fragt an den verschweißten Dreiecken, ob es etwas aufreißt
    (``repair.weld``), und dieselbe Zählung beantwortet danach Dichtheit,
    Ränder und Teile, ohne alle Kanten ein zweites Mal zu sortieren.
    """
    _remember_edges(body, table)


def without_faces(body: trimesh.Trimesh, keep: np.ndarray) -> trimesh.Trimesh:
    """Eine Kopie mit den Dreiecken aus ``keep`` und ohne unbenutzte Ecken.

    Dasselbe wie ``copy``, ``update_faces(keep)`` und
    ``remove_unreferenced_vertices`` — **aber die Kantenzählung wird
    abgeleitet, nicht neu sortiert** (RM-224). Die Reparatur nimmt einem Netz
    Verzweigungen, Splitter und Kleinstteile, und jedes Mal zählte sie danach
    alle Kanten neu: am Piratenschiff 0,4 s für ein Netz, das vier Dreiecke
    weniger hatte. Wer Dreiecke streicht, zieht ihre Zeilen von den Zählern ab;
    Kanten ohne Dreieck fallen weg. Die Ecken behalten beim Aufräumen ihre
    Reihenfolge (trimesh legt die benutzten dicht zusammen), also bleiben die
    Kanten sortiert, und jede Zeile gehört weiter zu ihrem Dreieck.

    Hatte ``body`` noch keine Zählung, zählt die Kopie bei Bedarf selbst.
    ``keep`` ist eine Maske über die Dreiecke.
    """
    keep = np.asarray(keep, dtype=bool)
    trimmed = body.copy()
    trimmed.update_faces(keep)
    trimmed.remove_unreferenced_vertices()
    _carry_face_measures(body, trimmed, keep=keep)
    cache = getattr(body, "_cache", None)
    if cache is None or _EDGE_TABLE_KEY not in cache:
        return trimmed
    table = cast(EdgeTable, cache[_EDGE_TABLE_KEY])
    rows = (np.flatnonzero(keep)[:, None] * 3 + np.arange(3, dtype=np.int64)).reshape(-1)
    before = table.inverse[rows]
    counts = np.bincount(before, minlength=len(table.counts))
    alive = counts > 0
    compact = np.cumsum(alive, dtype=np.int64) - 1
    used = np.zeros(len(body.vertices), dtype=bool)
    used[np.asarray(body.faces, dtype=np.int64)[keep].reshape(-1)] = True
    renumbered = np.cumsum(used, dtype=np.int64) - 1
    _remember_edges(
        trimmed,
        EdgeTable(
            unique=renumbered[table.unique[alive]],
            inverse=compact[before],
            counts=counts[alive].astype(np.int64),
        ),
    )
    return trimmed


def carry_appended_edges(body: trimesh.Trimesh, extended: trimesh.Trimesh) -> None:
    """Die Kantenzählung eines Netzes, an das nur Dreiecke und Ecken angehängt wurden.

    ``extended`` trägt die Ecken von ``body`` in derselben Reihenfolge, danach
    neue, und die Dreiecke von ``body``, danach neue — so baut die Lochfüllung
    das geflickte Netz (RM-224). Statt alle Kanten neu zu sortieren, werden
    nur die der neuen Dreiecke in die sortierte Liste eingefügt: Die alten
    Kanten behalten ihre Reihenfolge und rücken um die Zahl der neuen davor.
    Ohne Zählung an ``body`` geschieht nichts; ``extended`` zählt dann selbst.
    Die Kreuzprodukte und Flächen je Dreieck reisen ebenso mit
    (:func:`_carry_face_measures`).
    """
    _carry_face_measures(body, extended)
    cache = getattr(body, "_cache", None)
    if cache is None or _EDGE_TABLE_KEY not in cache:
        return
    table = cast(EdgeTable, cache[_EDGE_TABLE_KEY])
    old_count = len(body.faces)
    added = np.asarray(extended.faces, dtype=np.int64)[old_count:]
    if not len(added):
        _remember_edges(extended, table)
        return
    width = len(extended.vertices)
    fresh_rows = np.sort(added[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    old_codes = table.unique[:, 0] * width + table.unique[:, 1]
    new_codes = fresh_rows[:, 0] * width + fresh_rows[:, 1]
    candidates = np.unique(new_codes)
    known = np.zeros(len(candidates), dtype=bool)
    if len(old_codes):
        at = np.minimum(np.searchsorted(old_codes, candidates), len(old_codes) - 1)
        known = old_codes[at] == candidates
    unseen = candidates[~known]
    merged = np.insert(old_codes, np.searchsorted(old_codes, unseen), unseen)
    moved = np.arange(len(old_codes), dtype=np.int64) + np.searchsorted(unseen, old_codes)
    inverse = np.concatenate([moved[table.inverse], np.searchsorted(merged, new_codes)])
    counts = np.zeros(len(merged), dtype=np.int64)
    counts[moved] = table.counts
    counts += np.bincount(inverse[len(table.inverse) :], minlength=len(merged))
    _remember_edges(
        extended,
        EdgeTable(
            unique=np.column_stack((merged // width, merged % width)),
            inverse=inverse,
            counts=counts,
        ),
    )


#: Was je Dreieck nur an seinen drei Ecken hängt und trimesh im Cache des Netzes
#: ablegt — :func:`_carry_face_measures` trägt es in ein abgeleitetes Netz.
_FACE_MEASURES: Final = ("triangles_cross", "area_faces")


def _carry_face_measures(
    source: trimesh.Trimesh, target: trimesh.Trimesh, *, keep: np.ndarray | None = None
) -> None:
    """Kreuzprodukt und Fläche je Dreieck in ein abgeleitetes Netz tragen, statt sie neu zu rechnen.

    Beide hängen nur an den drei Ecken ihres Dreiecks, und trimesh rechnet sie
    Zeile für Zeile: Ein Dreieck, das bleibt, hat danach dieselben Bits, ein
    angehängtes wird allein gerechnet. **Am Piratenschiff rechnete das
    Einlesen beide dreimal über 1,2 Millionen Dreiecke** — für die leeren
    Dreiecke, für die Fläche vor der Lochfüllung und für die Füllungen ohne
    Dicke, je 0,12 s —, obwohl sich dazwischen acht Dreiecke geändert hatten
    (Durchsicht 0.5.1). ``keep`` ist die Maske eines Streichens
    (:func:`without_faces`); ohne sie trägt ``target`` die Dreiecke von
    ``source`` vorn und neue dahinter (:func:`carry_appended_edges`).
    """
    known = getattr(source, "_cache", None)
    into = getattr(target, "_cache", None)
    if known is None or into is None:
        return
    count = len(source.faces)
    crosses: np.ndarray | None = None
    for name in _FACE_MEASURES:
        # ``in`` prüft, ob der Eintrag noch zur Geometrie von ``source`` gehört.
        if name not in known:
            continue
        values = np.asarray(known[name])
        if len(values) != count:
            continue
        if keep is not None:
            into[name] = values[keep]
            continue
        added = np.asarray(target.faces, dtype=np.int64)[count:]
        if len(added):
            if crosses is None:
                corners = np.asarray(target.vertices, dtype=np.float64)[added]
                crosses = np.asarray(trimesh.triangles.cross(corners))
            fresh = (
                crosses if name == "triangles_cross" else trimesh.triangles.area(crosses=crosses)
            )
            values = np.concatenate([values, np.asarray(fresh, dtype=values.dtype)])
        into[name] = values


def face_components(
    mesh: trimesh.Trimesh, *, cancelled: CancelToken | None = None
) -> list[np.ndarray]:
    """Zusammenhängende Komponenten als Dreiecksindizes.

    Mit Absicht über die Flächen-Nachbarschaft statt ``Trimesh.split``: das
    Splitten baut Teilnetze und versucht, sie zu reparieren — das ist
    langsamer und zugleich eine Entscheidung, die die Eingangsstufe noch gar
    nicht getroffen hat (§17.1 Schritt 5).

    **Gefragt wird nach dem Teil, nicht nach der Speicherform.** Eine STL kennt
    keine gemeinsamen Ecken; ungeschweißt geladen hat ein solches Netz gar
    keine Flächen-Nachbarschaft, und dann ist jedes Dreieck seine eigene
    Komponente. Gemessen: 796 statt 1 an ``plate_holes.stl``, 12 statt 1 am
    Würfel. Der Prüfbericht schrieb daraufhin „Das Modell besteht aus mehreren
    Teilen" mit 796 daneben, an einem Teil, das aus einem Stück ist.

    Gezählt wird deshalb über die **Vereinigung** beider Lesarten: benachbart
    ist, was eine Kante teilt — nach den gespeicherten Eckennummern *oder* nach
    dem Ort. Das ist der Teil, der nicht selbstverständlich ist, und er hat
    einen gemessenen Anlass: Über den Ort **allein** zerfiel ein
    verrundeter Blend-Körper mit Radius 12 in fünf Stücke. Dort liegen zwei
    Ecken 88 Nanometer auseinander; sie auf denselben Ort zu legen macht aus
    einem Dreieck ein entartetes, das keine Kante mehr teilt — und wenn es eine
    Brücke war, reißt der Graph an einer Stelle, an der nichts fehlt.

    Zusammenführen darf Verbindungen **hinzufügen** und nie welche wegnehmen.
    Die Vereinigung sichert genau das zu, und die Gegenprobe steht daneben:
    Zwei Würfel mit fünf Millimetern Abstand bleiben zwei.

    Das Netz des Aufrufers wird dabei nicht angefasst — umnummeriert wird eine
    Kopie der Flächentabelle, die Dreiecke behalten ihren Platz, und die
    Rückgabe zeigt auf dieselben Dreiecke wie vorher. Die Toleranz ist dieselbe
    wie bei ``repair.merge_vertices`` und ``perceive.features``:
    ``trimesh.scale`` ist die Diagonale des Hüllquaders, also derselbe Wert wie
    ``MeshData.bounds.diagonal`` (nachgemessen, auf die letzte Stelle gleich).

    **Einmal je Netz** (RM-224): Das Einlesen fragte dasselbe Netz bis zu
    dreimal — Teilezahl, Schalen, Durchdringung —, am Piratenschiff mit
    1,2 Millionen Dreiecken 0,4 s je Frage. Die Teile liegen im Cache des
    Netzes und verfallen mit seiner Geometrie; sie sind schreibgeschützt,
    die Liste darum ist je Aufruf neu.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    count = len(mesh.faces)
    if count == 0:
        return []
    cache = getattr(mesh, "_cache", None)
    if cache is not None and _COMPONENTS_KEY in cache:
        return list(cast("tuple[np.ndarray, ...]", cache[_COMPONENTS_KEY]))
    # Wie ``trimesh.graph.connected_components(…, engine="scipy")``: jede
    # Nachbarschaft liegt zwischen zwei der ``count`` Dreiecke, also ist die
    # Knotenmenge alles und die Gruppen sind die der Nummern. Die Nummern
    # rechnet ``kernel_jobs.component_labels`` — an großen Netzen im
    # Hilfsprozess, denn ``csgraph`` hält den GIL (RM-212).
    from app.core.geom import kernel_process

    edges = np.asarray(_adjacency_by_place(mesh), dtype=np.int64).reshape(-1, 2)
    labels = kernel_process.run(
        "component_labels", {"edges": edges}, {"count": count}, weight=count, cancelled=cancelled
    )[0]["labels"]
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    pieces = tuple(
        np.asarray(piece, dtype=np.int64) for piece in trimesh.grouping.group(labels, min_len=1)
    )
    for piece in pieces:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        piece.flags.writeable = False
    if cache is not None:
        cache[_COMPONENTS_KEY] = pieces
    return list(pieces)


#: Wo :func:`face_components` seine Teile im Cache des Netzes ablegt.
_COMPONENTS_KEY: Final = "solidon_face_components"


def _adjacency_by_place(mesh: trimesh.Trimesh) -> np.ndarray:
    """Nachbarschaften nach gespeicherten Nummern **und** nach Ort.

    Die zweite Hälfte ist die, die eine ungeschweißte Datei überhaupt erst
    zusammenhängen lässt; die erste die, ohne die ein zusammengelegter Ort eine
    bestehende Verbindung kosten könnte. Beide zusammen sind die Frage, die
    gemeint ist — der Grund steht bei :func:`face_components`.
    """
    stored = edge_table(mesh).face_pairs()
    # Dieselbe Frage wie :func:`fully_stitched`, an denselben Paaren — über
    # ``face_adjacency`` gestellt, gruppierte trimesh die Kanten doch noch.
    if len(mesh.faces) and 2 * len(stored) >= 3 * len(mesh.faces):
        return stored
    digits = weld_digits(weld_tolerance(float(mesh.scale)))
    _, place = trimesh.grouping.unique_rows(np.asarray(mesh.vertices, dtype=float), digits=digits)
    faces = np.asarray(place, dtype=np.int64)[np.asarray(mesh.faces, dtype=np.int64)]
    welded = np.asarray(trimesh.graph.face_adjacency(faces=faces), dtype=np.int64).reshape(-1, 2)
    return np.vstack([stored, welded])


def triple_products(triangles: np.ndarray) -> np.ndarray:
    """Das Spatprodukt ``a · cross(b, c)`` je Dreieck ``(n, 3, 3)``.

    Elementweise und nicht über ``np.einsum`` (RM-187): Das nutzt auf ARM FMA,
    und am Vorzeichen der Summe hängt, ob ein Körper, eine Schale oder ein
    Ergebnis gilt.
    """
    first, crossed = triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])
    return np.asarray(
        first[:, 0] * crossed[:, 0] + first[:, 1] * crossed[:, 1] + first[:, 2] * crossed[:, 2]
    )


#: Wie viele Werte eines Felds auf einmal zu Python-Zahlen werden
#: (:func:`python_values`).
PYTHON_VALUES_CHUNK: Final = 262_144


def python_values(values: np.ndarray) -> Iterator[Any]:
    """Die Werte eines eindimensionalen Felds als Python-Zahlen, Stück für Stück.

    Dieselbe Folge wie ``values.tolist()``; ``math.fsum`` oder ``tuple``
    darüber ergeben dieselbe Zahl, dasselbe Tupel. Nur ist ein ``tolist`` über
    Millionen Werte ein einziger C-Aufruf, ``fsum`` oder ``tuple`` darüber ein
    zweiter, und keiner gibt den GIL her: Am Spielwürfel nach *Kanten
    verfeinern* (5,8 Mio. Dreiecke) hielt allein das Volumen den Hauptfaden
    bis zu 300 ms an, obwohl ein Arbeiter rechnete (RM-212). Zwischen zwei
    Stücken läuft hier Python, und dort wechselt der Interpreter den Faden.
    """
    return itertools.chain.from_iterable(
        values[start : start + PYTHON_VALUES_CHUNK].tolist()
        for start in range(0, len(values), PYTHON_VALUES_CHUNK)
    )


def enclosed_volume(body: trimesh.Trimesh) -> float:
    """Das Volumenintegral über die Oberfläche, bezogen auf den Ursprung.

    Dieselbe Formel wie ``trimesh.triangles.mass_properties``, ohne Schwerpunkt
    und Trägheit, summiert mit ``math.fsum`` — an 203 776 Dreiecken 0,07 statt
    0,29 s. Für ein geschlossenes Netz das Volumen, für ein offenes eine Zahl,
    die an der Lage hängt; so war sie es vorher auch. **Für eine Entscheidung
    gilt** :func:`signed_volume`: Weit vom Ursprung verliert diese Summe das
    Volumen eines kleinen Körpers in der Rundung. Summiert wird in Stücken
    (:func:`python_values`) — ``fsum`` rundet genau einmal, die Zahl ist
    dieselbe.
    """
    triangles = np.asarray(body.triangles, dtype=np.float64)
    if not len(triangles):
        return 0.0
    return math.fsum(python_values(triple_products(triangles))) / 6.0


def signed_volume(body: trimesh.Trimesh) -> float:
    """Das Volumenintegral nahe am Körper — die Zahl, an der Entscheidungen hängen.

    Bezogen auf die erste Ecke statt auf den Ursprung. Für ein geschlossenes
    Netz derselbe Wert wie :func:`enclosed_volume`, nur ohne dessen Verlust
    weit draußen: Ein Würfel von 1 mm bei 10⁸ mm hatte dort ein Volumen, das
    allein aus Rundung bestand, und die Reparatur stülpte ihn um (Befund B16
    der Durchsicht 24.09.2026). Ob ein Netz ein positiver Körper ist, ob ein
    Boolesches Ergebnis gilt und ob eine Füllung Dicke hat, fragen dieselbe
    Rechnung.
    """
    triangles = np.asarray(body.triangles, dtype=np.float64)
    if not len(triangles):
        return 0.0
    return math.fsum(triple_products(triangles - triangles[0, 0]).tolist()) / 6.0


def on_surface(
    body: trimesh.Trimesh, points: np.ndarray, *, index: _SurfaceIndex | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Für jeden Punkt der nächste Ort auf der Oberfläche, sein Abstand und
    sein Dreieck.

    **Ohne ``rtree``, seit dem 24.08.2026 — und das ist der ganze Zweck dieser
    Funktion.** Der Weg über ``trimesh.proximity`` führte durch dessen Index,
    und ``rtree`` greift auf dieser Maschine in fremde Seiten: Ein Kunde, der
    im Beispiel von Weg 2 die Breite auf 90 stellte, verlor die Anwendung —
    ohne eine Zeile im Protokoll, denn ein nativer Abriss schreibt keine.
    Die Milderungen davor (ein Wiederholversuch an einer Kopie, zwei
    Größenordnungen weniger Anfragen über den Vorfilter in
    ``geom.attributes``) machten den Fehlgriff selten, nicht unmöglich; und
    ein geladenes ``rtree`` beschädigte sogar Unbeteiligtes — das Zahlenlesen
    in ``export/threemf.py`` scheiterte sechsmal öfter, solange es im Prozess
    war.

    Der Ersatz fragt ``cKDTree``-Bäume über den **Dreiecksschwerpunkten**
    (scipy, längst Abhängigkeit) und rechnet exakt nach: Erst der nächste
    Schwerpunkt als Schranke ``u``, dann alle Dreiecke, deren Schwerpunkt
    näher als ``u`` plus ihre Schwerpunkt-Ecke-Spanne liegen kann — jedes
    andere kann die Schranke nicht mehr unterbieten. Auf den Kandidaten
    entscheidet die exakte Rechnung von ``trimesh.triangles``. Das ist
    **kein** Näherungsverfahren: gemessen gegen ``ProximityQuery`` sind die
    Abstände identisch.

    Die Spanne gilt **je Größenband**, nicht einmal als größter Wert des ganzen
    Netzes. Eine einzige große Fläche machte sonst aus dem Baum wieder die
    vollständige Suche: Im Dosenbeispiel wurden 32,36 Millionen Paare exakt
    nachgerechnet, obwohl 99 Prozent der Dreiecke klein sind. Zweierpotenzen
    teilen die Bänder ohne willkürliche Millimetergrenze; dieselbe Datei fragt
    damit noch 224 432 Paare und liefert dieselben Slotwerte.

    Der Baum entsteht je Aufruf und wird nicht am Netz zwischengespeichert —
    der von ``trimesh`` gecachte ``rtree``-Index war genau die Stelle, unter
    der der beschädigte Speicher lag. Wer dasselbe Netz in mehreren Portionen
    fragt, baut ihn einmal (:class:`_SurfaceIndex`); so misst
    :func:`max_distance_to_surface`. Wer ihn über mehrere Aufrufe hält, gibt
    ihn als ``index`` mit (:func:`surface_index`) — er muss zu ``body``
    gehören. Die Bäume der Größenbänder hält der Index mit
    (:attr:`_SurfaceIndex.bands`); ein zweiter Aufruf baut keinen Baum über
    dem Netz mehr.
    """
    built = index if index is not None and index.body is body else _SurfaceIndex.of(body)
    return _nearest_on(built, np.asarray(points, dtype=float).reshape(-1, 3))


def surface_index(body: trimesh.Trimesh) -> _SurfaceIndex:
    """Der Suchbaum für :func:`on_surface`, einmal gebaut für viele Fragen an dasselbe Netz.

    Nur Zahlen und ein ``cKDTree`` — kein ``rtree``, und nichts davon liegt
    im Cache des Netzes. Wer ihn hält, entscheidet, wie lange.
    """
    return _SurfaceIndex.of(body)


@dataclass(frozen=True)
class _SurfaceIndex:
    """Das Netz, wie :func:`on_surface` es befragt — einmal gebaut, beliebig oft gefragt.

    Dreiecke, Schwerpunkte, die Spanne je Dreieck (Schwerpunkt zur fernsten
    Ecke), die Quader um jedes Dreieck und der ``cKDTree`` über den
    Schwerpunkten; beim ersten Gebrauch dazu die Größenbänder mit ihren Bäumen
    (:attr:`bands`). Kein Zustand, der sich danach ändert; das Netz selbst
    wird nicht angefasst.
    """

    triangles: np.ndarray
    centroids: np.ndarray
    span: np.ndarray
    lows: np.ndarray
    highs: np.ndarray
    tree: object
    body: trimesh.Trimesh

    @classmethod
    def of(cls, body: trimesh.Trimesh) -> _SurfaceIndex:
        from scipy.spatial import cKDTree

        triangles = np.asarray(body.triangles, dtype=float)
        centroids = triangles.mean(axis=1)
        return cls(
            triangles=triangles,
            centroids=centroids,
            span=np.linalg.norm(triangles - centroids[:, None, :], axis=2).max(axis=1),
            lows=triangles.min(axis=1),
            highs=triangles.max(axis=1),
            tree=cKDTree(centroids),
            body=body,
        )

    @cached_property
    def bands(self) -> tuple[tuple[np.ndarray, Any, float], ...]:
        """Die Größenbänder der Dreiecke — je Band die Nummern, ihr Suchbaum und
        die größte Spanne darin.

        Ein Band sind die Dreiecke, deren Spanne in dieselbe Zweierpotenz fällt
        (die Gründe stehen in :func:`_nearest_on`). Die Bänder hängen nur am
        Netz, nicht an der Frage; bis zur Durchsicht 0.5.1 entstanden ihre
        Bäume trotzdem in jedem Aufruf neu — am Gartenschlauchhalter
        (392 532 Dreiecke) neunzehn Bäume und 66 ms je Frage, auch am
        gemerkten Index und auch für zwei Punkte (RM-260). Gebaut beim ersten
        Gebrauch: :meth:`bound` und eine Messung, die ohne exakte Frage
        auskommt (:func:`beyond_surface` an einem heilen Netz), brauchen sie
        nicht. Fragen zwei Fäden zugleich zum ersten Mal, bauen beide
        dieselben Bänder, und einer davon bleibt.
        """
        from scipy.spatial import cKDTree

        exponents = np.frexp(self.span)[1]
        bands = []
        for exponent in np.unique(exponents):
            indices = np.flatnonzero(exponents == exponent)
            band_tree = (
                self.tree
                if len(indices) == len(self.triangles)
                else cKDTree(self.centroids[indices])
            )
            bands.append((indices, band_tree, float(self.span[indices].max())))
        return tuple(bands)

    def bound(self, queries: np.ndarray, *, neighbours: int = 1) -> np.ndarray:
        """Je Punkt eine obere Schranke für seinen Abstand zur Oberfläche: der
        kleinste exakte Abstand zu den Dreiecken der ``neighbours`` nächsten
        Schwerpunkte.

        Einer genügt der Suche in :func:`_nearest_on`; mehrere machen die
        Schranke enger, wo der nächste Schwerpunkt nicht zum nächsten Dreieck
        gehört — an Nadeldreiecken die Regel, denn deren Schwerpunkt liegt
        weit von ihren Enden. Immer endlich — ein Dreieck ohne Fläche macht
        die exakte Rechnung zu NaN, und dann tritt Abstand zum Schwerpunkt
        plus Spanne an seine Stelle (die Gründe stehen in :func:`_nearest_on`).
        """
        from trimesh.triangles import closest_point as closest_on

        tree: Any = self.tree
        count = min(neighbours, len(self.triangles))
        _, ring = tree.query(queries, k=count)
        ring = np.asarray(ring, dtype=np.int64).reshape(len(queries), count)
        asked = np.repeat(queries, count, axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            spots = closest_on(self.triangles[ring.ravel()], asked)
        gaps = np.linalg.norm(asked - spots, axis=1)
        loose = (
            np.linalg.norm(asked - self.centroids[ring.ravel()], axis=1) + self.span[ring.ravel()]
        )
        gaps = np.where(np.isfinite(gaps), gaps, loose)
        return np.asarray(gaps.reshape(len(queries), count).min(axis=1), dtype=float)

    def bound_at_corners(self, queries: np.ndarray, *, neighbours: int = 4) -> np.ndarray:
        """Dieselbe Schranke über die Dreiecke an den ``neighbours`` nächsten
        Ecken des Netzes — die Ergänzung zu :meth:`bound` für **große**
        Dreiecke.

        Ein Punkt mitten auf einer großen ebenen Facette hat Abstand null zu
        ihr, aber ihr Schwerpunkt liegt weit weg, und acht nähere Schwerpunkte
        gehören zu kleinen Dreiecken daneben (:meth:`bound` bleibt dort über
        null). Die nächste **Ecke** des Netzes ist dagegen fast immer eine
        Ecke genau dieser Facette, und ihre Dreiecke enthalten sie.
        ``inf``, wo ein Punkt keine Ecke mit Dreieck findet.
        """
        from scipy.spatial import cKDTree
        from trimesh.triangles import closest_point as closest_on

        vertices = np.asarray(self.body.vertices, dtype=float)
        faces = np.asarray(self.body.faces, dtype=np.int64)
        if not len(vertices) or not len(faces):
            return np.full(len(queries), np.inf)
        # Je Ecke ihre Dreiecke, dicht abgelegt: ``vertex_faces`` von ``trimesh``
        # füllt jede Zeile auf den größten Grad auf, und die Nabe eines Fächers
        # mit zweihundert Dreiecken macht daraus zweihundert Spalten für jede
        # Ecke des Netzes.
        by_vertex = np.argsort(faces.ravel(), kind="stable") // 3
        degree = np.bincount(faces.ravel(), minlength=len(vertices))
        starts = np.concatenate(([0], np.cumsum(degree)))
        count = min(neighbours, len(vertices))
        _, near = cKDTree(vertices).query(queries, k=count)
        near = np.asarray(near, dtype=np.int64).reshape(len(queries), count)
        owners = np.repeat(np.arange(len(queries), dtype=np.int64), degree[near].sum(axis=1))
        corners = near.ravel()
        runs = degree[corners]
        offsets = np.arange(int(runs.sum()), dtype=np.int64) - np.repeat(
            np.cumsum(runs) - runs, runs
        )
        chosen = by_vertex[np.repeat(starts[corners], runs) + offsets]
        asked = queries[owners]
        with np.errstate(invalid="ignore", divide="ignore"):
            spots = closest_on(self.triangles[chosen], asked)
        gaps = np.linalg.norm(asked - spots, axis=1)
        loose = np.linalg.norm(asked - self.centroids[chosen], axis=1) + self.span[chosen]
        gaps = np.where(np.isfinite(gaps), gaps, loose)
        bound = np.full(len(queries), np.inf)
        np.minimum.at(bound, owners, gaps)
        return bound


def max_distance_to_surface(
    body: trimesh.Trimesh, points: np.ndarray, *, cancelled: CancelToken | None = None
) -> float:
    """Der größte Abstand, den einer der Punkte zur Oberfläche hat — exakt,
    aber nur dort ausgerechnet, wo er das Maximum noch heben kann.

    :func:`on_surface` beantwortet je Punkt drei Fragen; die Abweichungsmessung
    einer Dezimierung stellt nur eine, und die nur einmal: Wie weit liegt der
    fernste Punkt weg? Dafür genügt die Schranke aus :meth:`_SurfaceIndex.bound`
    für jeden Punkt, der sie nicht überbieten kann. Die Punkte werden nach
    ihrer Schranke absteigend in wachsenden Portionen exakt gemessen; sobald
    die größte verbleibende Schranke unter dem bisher gemessenen Maximum liegt,
    kann kein Punkt danach das Maximum noch heben, und die Messung endet.

    Das ist keine Näherung: Jeder Abstand ist höchstens seine Schranke, und
    gemessen wird, bis die Schranken kleiner sind als ein gemessener Abstand —
    oder als das Rundungsrauschen der Koordinaten, unter dem kein Maximum
    mehr eines ist.
    Was es spart, sind die Nadeldreiecke: An einem CAD-Export eines
    Besenhalters (59 740 Dreiecke, 97 Prozent Nadeln) misst die Dezimierung
    29 856 alte Ecken gegen 13 202 neue Dreiecke — vollständig 2,3 s, weil
    jede Ecke unter den Kugeln langer Dreiecke Hunderte Bewerber hat; hier
    tragen 78 Prozent der Ecken eine Schranke unter dem Maximum und werden nie
    exakt gemessen (22.09.2026).

    ``cancelled`` wird je Portion gefragt: Am Voronoi-Spiderman (885 570
    Dreiecke) misst die Abweichung nach dem Glätten 5,4 s (23.09.2026).
    """
    return farthest_from_surface(body, points, cancelled=cancelled)[0]


def farthest_from_surface(
    body: trimesh.Trimesh, points: np.ndarray, *, cancelled: CancelToken | None = None
) -> tuple[float, int | None]:
    """Dasselbe Maximum wie :func:`max_distance_to_surface` — und welcher Punkt es hat.

    Gebraucht, wo der Ort zählt: Die Umwandlung ins Exakte meldet die größte
    Abweichung mit der Stelle, an die die Ansicht fliegt. Den Ort danach über
    :func:`on_surface` zu suchen hieß, jeden Punkt exakt zu messen — genau das,
    was die Schranken hier sparen (an ``post_with_fillet.stl``: 4,0 s statt
    der Zehntelsekunde davor). ``None``, wo kein Punkt über dem Rundungsrauschen
    liegt.
    """
    queries = np.asarray(points, dtype=float).reshape(-1, 3)
    if not len(queries) or not len(body.faces):
        return 0.0, None
    index = _SurfaceIndex.of(body)
    bound = index.bound(queries)
    # Der Boden ist das Rundungsrauschen der Koordinaten: Ein Punkt, der
    # rechnerisch 1e-16 mm neben einer Facette liegt, auf der er sitzt, hebt
    # kein Maximum, das jemand liest — derselbe Maßstab wie in
    # :func:`app.core.geom.mesh_ops.deviation`.
    roundoff = (
        8
        * np.finfo(np.float64).eps
        * max(float(np.max(np.abs(index.triangles))), float(np.max(np.abs(queries))), 1.0)
    )
    highest = 0.0
    where: int | None = None
    portion = 256
    rounds = 0
    # Wer die Schranke des bisher Gemessenen nicht überbietet, kann das
    # Maximum nicht heben.
    alive = np.flatnonzero(bound > max(highest, roundoff))
    while len(alive):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if rounds == 1:
            # Nach dem ersten Maß lohnt die engere Schranke: Sie kostet acht
            # exakte Abstände je Punkt, aber nur für die, die noch im Rennen
            # sind — und lässt die meisten davon ausscheiden.
            asked = queries[alive]
            bound[alive] = np.minimum.reduce(
                [bound[alive], index.bound(asked, neighbours=8), index.bound_at_corners(asked)]
            )
            alive = alive[bound[alive] > max(highest, roundoff)]
            if not len(alive):
                break
        chosen = alive[np.argsort(-bound[alive], kind="stable")[:portion]]
        _spot, distance, _triangle = _nearest_on(index, queries[chosen])
        best = int(np.argmax(distance))
        if float(distance[best]) > highest:
            highest = float(distance[best])
            where = int(chosen[best])
        bound[chosen] = distance
        portion *= 2
        rounds += 1
        alive = np.flatnonzero(bound > max(highest, roundoff))
    return highest, where


def beyond_surface(
    body: trimesh.Trimesh, points: np.ndarray, floor: float | np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Die Punkte, die weiter als ``floor`` von der Oberfläche liegen — exakt gemessen.

    ``floor`` gilt für alle Punkte oder je Punkt.

    Dieselben Schranken wie :func:`max_distance_to_surface`: Wessen Schranke
    unter ``floor`` bleibt, liegt sicher darunter und wird nie gemessen. Die
    Umwandlung ins Exakte fragt so nach den Stellen, an denen das Netz weiter
    vom Körper abliegt als von seiner eigenen Fläche — eine Naht, die eine
    Vereinigung nicht verschmolzen hat, liegt im Inneren des Körpers, und in
    einem gewöhnlichen Netz gibt es keine; gemessen wird dann nichts.

    Zurück kommen die Nummern der Punkte, ihre Abstände, die nächsten Punkte
    auf der Oberfläche und deren Dreiecke — nur für die, die ``floor``
    überschreiten.
    """
    queries = np.asarray(points, dtype=float).reshape(-1, 3)
    floors = np.broadcast_to(np.asarray(floor, dtype=float), (len(queries),))
    empty = np.zeros(0, dtype=np.int64)
    if not len(queries) or not len(body.faces):
        return empty, np.zeros(0), np.zeros((0, 3)), empty
    index = _SurfaceIndex.of(body)
    alive = np.flatnonzero(index.bound(queries) > floors)
    if not len(alive):
        return empty, np.zeros(0), np.zeros((0, 3)), empty
    tighter = np.minimum(
        index.bound(queries[alive], neighbours=8), index.bound_at_corners(queries[alive])
    )
    alive = alive[tighter > floors[alive]]
    if not len(alive):
        return empty, np.zeros(0), np.zeros((0, 3)), empty
    spots, distances, triangles = _nearest_on(index, queries[alive])
    keep = distances > floors[alive]
    return alive[keep], distances[keep], spots[keep], triangles[keep]


def _nearest_on(
    index: _SurfaceIndex, queries: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Der Rumpf von :func:`on_surface` über einem gebauten Index."""
    from scipy.spatial import cKDTree
    from trimesh.triangles import closest_point as closest_on

    triangles = index.triangles
    centroids = index.centroids
    span = index.span
    tree: Any = index.tree

    # Die Schranke: exakter Abstand zum Dreieck mit dem nächsten Schwerpunkt.
    _, nearest = tree.query(queries)
    nearest = np.atleast_1d(nearest)
    # **Die Division durch null wird hier erwartet, nicht verhindert.** Ein
    # Dreieck ohne Fläche lässt ``closest_point`` baryzentrisch durch eine
    # Kantenlänge von null teilen; numpy warnt, und die Suite behandelt jede
    # Warnung als Fehler. Unterdrückt wird sie genau dort, wo das NaN danach
    # ausdrücklich abgefangen wird — beide Stellen prüfen unmittelbar auf
    # ``isfinite``. Ein Filter in der Testkonfiguration wäre die schlechtere
    # Antwort: Er gölte für den ganzen Lauf.
    with np.errstate(invalid="ignore", divide="ignore"):
        bound_spot = closest_on(triangles[nearest], queries)
    bound = np.linalg.norm(queries - bound_spot, axis=1)

    # **Ein entartetes Dreieck macht die Schranke zu NaN, und ein NaN-Radius
    # findet nichts.** ``closest_point`` rechnet baryzentrisch und teilt dabei
    # durch die Kantenlänge; bei einem Dreieck ohne Fläche ist das eine
    # Division durch null. Gemessen an einem Gyroid-Gitter mit 1 201 216
    # Dreiecken: **ein einziger** von 11 322 Abfragepunkten bekam so eine
    # NaN-Schranke, seine Kugel fand keinen Kandidaten, und die Zeile darunter
    # brach mit „need at least one array to concatenate" ab — der Kunde las
    # beim Verringern der Dreiecke „Im Programm ist ein unerwarteter Fehler
    # aufgetreten".
    #
    # Ersetzt wird die Schranke durch eine, die dasselbe Dreieck umschließt und
    # immer endlich ist: Abstand zu seinem Schwerpunkt plus seine Spanne. Sie
    # ist größer als die exakte, also bleibt die Kandidatenmenge eine
    # Obermenge — gesucht wird etwas weiter, gefunden dasselbe.
    unusable = ~np.isfinite(bound)
    if unusable.any():
        loose = np.linalg.norm(queries[unusable] - centroids[nearest[unusable]], axis=1)
        bound[unusable] = loose + span[nearest[unusable]]

    # Alle Dreiecke, die sie noch unterbieten könnten. Pro Größenband genügt
    # dessen größte Spanne als Radius; ein großes Dreieck weitet damit nur die
    # Suche unter anderen großen Dreiecken. ``frexp`` liefert Zweierpotenzen
    # ohne eine zweite, in Millimetern festgeschriebene Wahrheit. Die Bänder
    # und ihre Bäume hält der Index (:attr:`_SurfaceIndex.bands`, RM-260).
    #
    # **Kein Gang je Abfragepunkt, und keine Python-Liste je Punkt.**
    # ``query_ball_point`` gab je Punkt eine Liste zurück — an 51 000 Ecken
    # der Lochplatte mit 204 000 Dreiecken sechzehn Millionen Zahlen als
    # Objekte, vier Sekunden allein dafür, dann je Punkt ein ``sort``
    # (gemessen am 22.09.2026: 7,7 s für eine Abweichungsmessung). Die Paare
    # kommen jetzt als dünn besetzte Matrix aus dem Baum
    # (``sparse_distance_matrix``, C), in Portionen begrenzter Paarzahl, und
    # ein einziges ``lexsort`` stellt dieselbe stabile Reihenfolge her.
    #
    # **Und zwei Siebe, beide exakt.** Die Kugel eines Bands fragt mit der
    # größten Spanne seiner Mitglieder; je Dreieck gilt seine eigene — wer
    # weiter weg liegt als Schranke plus Spanne, unterbietet sie nicht. Und
    # der Abstand zum Quader um ein Dreieck ist nie größer als der zum
    # Dreieck: Liegt der Quader weiter weg als die Schranke, ist das Dreieck
    # kein Bewerber. An den Nadeldreiecken der Lochplatte — lang, dünn, große
    # Spanne — lässt der Quader von 8,7 Millionen Paaren einen Bruchteil übrig.
    owners_by_band: list[np.ndarray] = []
    candidates_by_band: list[np.ndarray] = []
    lows = index.lows
    highs = index.highs
    budget = 2_000_000
    for indices, band_tree, band_span in index.bands:
        radius = bound + band_span
        lengths = np.asarray(
            band_tree.query_ball_point(queries, radius, return_length=True), dtype=np.int64
        )
        if not lengths.any():
            continue
        # **Portionen mit gleichem Radius, bis auf die Spanne.** Die Matrix
        # fragt mit einem Radius je Portion; ein Punkt weit weg vom Netz neben
        # einem darauf zöge für beide den großen Radius — und ein ferner
        # Punkt sieht schon mit ein paar Millimetern mehr das ganze Netz statt
        # seines zugewandten Rands. Nach Radius sortiert, und eine Portion
        # reicht nur so weit, wie der Radius um höchstens eine Spanne wächst;
        # kleine Portionen (ferne, vereinzelte Punkte) gehen den alten
        # Listenweg, der dort schnell ist.
        by_radius = np.argsort(radius, kind="stable")
        sorted_radius = radius[by_radius]
        cumulative = np.cumsum(lengths[by_radius])
        first = 0
        while first < len(queries):
            before_first = int(cumulative[first - 1]) if first else 0
            last = int(np.searchsorted(cumulative, before_first + budget, side="right"))
            last = min(
                last,
                int(np.searchsorted(sorted_radius, sorted_radius[first] + band_span, side="right")),
            )
            last = max(last, first + 1)
            chosen = by_radius[first:last]
            if last - first < 64:
                found = band_tree.query_ball_point(queries[chosen], radius[chosen])
                rows = np.repeat(chosen, lengths[chosen])
                columns = indices[
                    np.concatenate([np.asarray(local, dtype=np.int64) for local in found])
                    if len(found)
                    else np.zeros(0, dtype=np.int64)
                ]
                reach = np.linalg.norm(centroids[columns] - queries[rows], axis=1)
            else:
                block = cKDTree(queries[chosen])
                pairs = block.sparse_distance_matrix(
                    band_tree, float(sorted_radius[last - 1]), output_type="coo_matrix"
                )
                rows = chosen[np.asarray(pairs.row, dtype=np.int64)]
                columns = indices[np.asarray(pairs.col, dtype=np.int64)]
                reach = np.asarray(pairs.data, dtype=float)
            possible = (reach <= radius[rows]) & (reach <= bound[rows] + span[columns])
            rows, columns = rows[possible], columns[possible]
            if len(rows):
                gap = np.maximum(
                    np.maximum(lows[columns] - queries[rows], queries[rows] - highs[columns]), 0.0
                )
                possible = np.linalg.norm(gap, axis=1) <= bound[rows]
                rows, columns = rows[possible], columns[possible]
            owners_by_band.append(rows)
            candidates_by_band.append(columns)
            first = last
    # Der nächste Schwerpunkt bleibt immer Kandidat: Er trägt die Schranke
    # selbst, und ein Nullabstand zu ihm stünde in der Matrix nicht.
    owners_by_band.append(np.arange(len(queries), dtype=np.int64))
    candidates_by_band.append(np.asarray(nearest, dtype=np.int64))
    all_owners = np.concatenate(owners_by_band)
    all_candidates = np.concatenate(candidates_by_band)

    # **Der Sieger je Punkt ohne Sortierung.** Der bisherige einzelne Baum
    # gab seine Kandidaten nach Dreiecksnummer geordnet zurück, und bei
    # gleichem Abstand — an einer exakt geteilten Kante — gewann der erste,
    # also die kleinste Nummer. Dieselbe Antwort gibt die Reduktion je Punkt:
    # kleinster Abstand, darunter kleinste Nummer (``np.minimum.at``), in
    # Portionen begrenzter Paarzahl, denn weit weg vom Netz deckt jede Kugel
    # fast alle Schwerpunkte, und tausend Punkte gegen ein dichtes Netz wären
    # Milliarden Paare auf einmal. Ein ``lexsort`` über neun Millionen Paare
    # kostete davor 1,5 der 4 Sekunden.
    closest = np.empty_like(queries)
    distance = np.full(len(queries), np.inf, dtype=float)
    unset = np.int64(len(triangles))
    triangle = np.full(len(queries), unset, dtype=np.int64)
    for lower in range(0, len(all_owners), budget):
        owners = all_owners[lower : lower + budget]
        candidates = all_candidates[lower : lower + budget]
        with np.errstate(invalid="ignore", divide="ignore"):
            spots = closest_on(triangles[candidates], queries[owners])
        # **Dasselbe entartete Dreieck, eine Stufe später.** Oben rettet der
        # Ersatz für die Schranke die Kandidatensuche; hier gäbe dieselbe
        # Division durch null einen NaN-Abstand. Solange ein gesunder Kandidat
        # danebensteht, verliert der NaN von selbst — ein NaN ist nie kleiner.
        # Ist er der **einzige**, käme ohne diese Zeilen ein NaN als Ergebnis
        # heraus, und der Kunde läse „Abweichung: nan mm".
        #
        # Ein flaches Dreieck ist geometrisch die Vereinigung seiner drei
        # Kanten. Auf die nächste davon zu projizieren bleibt deshalb auch bei
        # einer langen Restkante exakt; nur die nächste Ecke zu nehmen machte
        # den Fehler so groß wie die halbe Kante.
        broken = ~np.isfinite(spots).all(axis=1)
        if broken.any():
            corners = triangles[candidates[broken]]
            asked = queries[owners[broken]]
            starts = corners
            edges = np.roll(corners, -1, axis=1) - starts
            squared = np.einsum("nij,nij->ni", edges, edges)
            along = np.zeros_like(squared)
            np.divide(
                np.einsum("nij,nij->ni", asked[:, None, :] - starts, edges),
                squared,
                out=along,
                where=squared > 0.0,
            )
            along = np.clip(along, 0.0, 1.0)
            projections = starts + along[:, :, None] * edges
            nearest_edge = np.linalg.norm(projections - asked[:, None, :], axis=2).argmin(axis=1)
            spots[broken] = projections[np.arange(len(projections)), nearest_edge]
        gaps = np.linalg.norm(queries[owners] - spots, axis=1)
        before = distance.copy()
        np.minimum.at(distance, owners, gaps)
        # Wo diese Portion den Abstand verbessert hat, zählt die bisherige
        # Nummer nicht mehr; wo er gleich blieb, entscheidet weiter die kleinste.
        triangle[distance < before] = unset
        tied = gaps == distance[owners]
        np.minimum.at(triangle, owners[tied], candidates[tied])
        # Wer nach dieser Portion Bestwert und kleinste Nummer trägt, setzt
        # den Ort; ein späterer Block mit besserem Abstand überschreibt ihn.
        won = tied & (candidates == triangle[owners])
        closest[owners[won]] = spots[won]
    return closest, distance, triangle


#: Ab wann eine Möller-Trumbore-Determinante als „Strahl parallel zum
#: Dreieck" gilt. Keine Millimeter (dafür gäbe es ``EPS_GEOM``), sondern das
#: Spatprodukt aus Richtung und zwei Kanten — gemessen wird ein Dreieck mit
#: 1e-6 mm Kantenlänge damit noch getroffen.
RAY_PARALLEL_EPS: Final = 1e-12


def ray_hit_distances(
    triangles: np.ndarray, origin: np.ndarray, direction: np.ndarray
) -> np.ndarray:
    """Alle Strahlparameter, zu denen ein Strahl die gegebenen Dreiecke trifft.

    Möller-Trumbore, vektorisiert über die Dreiecke, exakt und ohne Index —
    die Alternative wäre ``body.ray.intersects_location``, und die baut sich
    ihren Suchbaum über ``rtree`` (warum das Paket den Prozess nicht mehr
    betreten darf, steht an :func:`on_surface`). Für die Anfragen dieses
    Hauses — ein paar Strahlen gegen einen Körper, wie bei der Materialtiefe
    der Stifte — ist die volle Rechnung billiger als jeder Baum, den man
    vorher bauen müsste.

    Zurück kommen die **positiven** Strahlparameter ``t``, unsortiert —
    gemessen von ``origin`` entlang ``direction``, **das normiert erwartet
    wird** (dieselbe Zusage wie bei :func:`ray_span_in_hull`): Mit einer
    Richtung der Länge zwei wäre jeder „Abstand" halb so groß wie der echte.
    Wer den ersten Austritt will, nimmt das Minimum.

    **Ein Treffer auf einer geteilten Kante oder Ecke zählt mehrfach** — je
    einmal pro angrenzendem Dreieck, gemessen: die Diagonale einer Deckfläche
    gibt zwei gleiche Werte, eine Ecke fünf. Für ein Minimum ist das egal;
    für Innen/Außen über die **Parität** der Durchdringungen taugt diese
    Funktion deshalb nicht.
    """
    return ray_hits(triangles, origin, direction)[0]


def ray_hits(
    triangles: np.ndarray,
    origin: np.ndarray,
    direction: np.ndarray,
    *,
    edge_margin: float = 1e-9,
    minimum_travel: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Positive Strahlparameter mit den zugehörigen ursprünglichen Dreiecksnummern.

    Teilmengen verwenden lokale Nummern; der Aufrufer führt seinen Blockbeginn
    hinzu. Kanten können mehrere Treffer tragen, wie bei ``ray_hit_distances``.

    ``edge_margin`` ist, wie weit ein Treffer baryzentrisch neben dem Dreieck
    noch zählt, ``minimum_travel`` der kleinste Strahlparameter, der ein
    Treffer ist. Die Wandstärke (``measure.ray_distances``) fragt mit
    ``EPS_GEOM`` und ``100·EPS_GEOM``: Sie schießt von der Oberfläche aus, und
    das Dreieck unter dem Startpunkt ist dort kein Gegenüber.

    **Elementweise und nicht über ``np.dot`` oder ``np.einsum``** (RM-187):
    Aus dem Treffer wird die Materialtiefe eines Stifts oder der Sitz eines
    gesetzten Bausteins, und beide sollen auf jeder Maschine dieselben sein.
    ``np.dot`` ging durch BLAS, ``np.einsum`` nutzt auf ARM FMA.
    """
    triangles = np.asarray(triangles, dtype=float)
    origin = np.asarray(origin, dtype=float).reshape(3)
    direction = np.asarray(direction, dtype=float).reshape(3)
    t, inside = _ray_triangle_parameters(
        triangles[:, 0],
        triangles[:, 1] - triangles[:, 0],
        triangles[:, 2] - triangles[:, 0],
        origin,
        direction,
        edge_margin,
        minimum_travel,
    )
    return np.asarray(t[inside], dtype=float), np.flatnonzero(inside)


def _ray_triangle_parameters(
    vertex: np.ndarray,
    edge_one: np.ndarray,
    edge_two: np.ndarray,
    origin: np.ndarray,
    direction: np.ndarray,
    edge_margin: float,
    minimum_travel: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Möller-Trumbore für :func:`ray_hits` und :func:`ray_hits_batch` — eine Stelle.

    Die Felder werden nur gesendet (NumPy-Broadcasting): ein Strahl gegen
    ``n`` Dreiecke oder ``m`` Strahlen gegen einen Block Dreiecke, dieselbe
    Rechnung in derselben Reihenfolge. Zurück kommen der Strahlparameter
    ``t`` und die Maske der gültigen Treffer.
    """
    across = np.cross(direction, edge_two)
    determinant = _rowwise_dot(edge_one, across)
    parallel = np.abs(determinant) < RAY_PARALLEL_EPS
    # Division erst nach dem Ausblenden der parallelen — sonst rechnet numpy
    # mit inf weiter und meldet Warnungen über Fälle, die keiner nimmt.
    safe = np.where(parallel, 1.0, determinant)
    to_origin = origin - vertex
    u = _rowwise_dot(to_origin, across) / safe
    q = np.cross(to_origin, edge_one)
    v = _rowwise_dot(q, direction) / safe
    t = _rowwise_dot(edge_two, q) / safe
    inside = (
        ~parallel
        & (u >= -edge_margin)
        & (v >= -edge_margin)
        & (u + v <= 1.0 + edge_margin)
        & (t > minimum_travel)
    )
    return t, inside


def _rowwise_dot(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Skalarprodukt über die letzte Achse zweier Felder, elementweise (RM-187).

    ``...`` statt eines festen ``:`` trägt auch ein drittes Achsenpaar mit,
    wie es :func:`ray_hits_batch` braucht — für die bisherigen zweiachsigen
    Aufrufer ist das dieselbe Rechnung.
    """
    return np.asarray(
        first[..., 0] * second[..., 0]
        + first[..., 1] * second[..., 1]
        + first[..., 2] * second[..., 2]
    )


#: Wie viele Strahl-Dreieck-Paare :func:`ray_hits_batch` höchstens auf einmal
#: als Feld hält — dieselbe Kostenüberlegung wie ``PAIR_BLOCK`` in
#: ``geom.intersections``, nur mit einer zweiten Strahlachse statt eines
#: zweiten Dreiecks.
RAY_BATCH_PAIRS: Final = 200_000

#: Ab wie vielen Strahl-Dreieck-Paaren :func:`ray_hits_batch` die Dreiecke je
#: Strahl über einen räumlichen Index vorauswählt. Darunter rechnet sie alle
#: Paare; der Aufbau des Index kostete dort mehr, als er spart.
RAY_CULL_PAIRS: Final = 4 * RAY_BATCH_PAIRS

#: Wie viele Dreiecke ein Blatt des Strahlindex höchstens trägt. Kleiner heißt
#: engere Quader und weniger gerechnete Paare, aber mehr Knoten je Strahl.
RAY_INDEX_LEAF: Final = 8

#: Wie viele Strahl-Knoten-Paare der Index höchstens auf einmal im Feld hält;
#: darüber teilt er die Strahlgruppe. Der Scheibentest hält je Paar rund
#: zwanzig Gleitkommazahlen zugleich — 500 000 Paare sind gut 100 MB. Die
#: Dreieckspaare der Blätter rechnet Möller-Trumbore danach in Blöcken von
#: ``RAY_BATCH_PAIRS``, wie der Vollvergleich.
RAY_INDEX_PAIRS: Final = 500_000

#: Mit wie vielen Strahlen eine Gruppe den Index hinabsteigt. Gemessen an einer
#: Vollkugel mit 51 200 Dreiecken (26.09.2026, unter Last): 512 bis 1024 am
#: schnellsten (2,4 s), 4096 langsamer (3,0 s) bei fast doppelter Spitze.
RAY_INDEX_RAYS: Final = 1024


def ray_hits_batch(
    triangles: np.ndarray,
    origins: np.ndarray,
    directions: np.ndarray,
    *,
    edge_margin: float = 1e-9,
    minimum_travel: float = 0.0,
    cancelled: CancelToken | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Für viele eigene Strahlen zugleich der **nächste** Treffer und dessen Dreieck.

    Dieselbe Möller-Trumbore-Rechnung wie :func:`ray_hits`
    (:func:`_ray_triangle_parameters`), aber über zwei Achsen zugleich:
    ``m`` Strahlen (je eigener Ursprung und Richtung) gegen dieselben ``n``
    Dreiecke, blockweise über die Dreiecksachse, damit der
    Speicher begrenzt bleibt. Das ist der Ersatz für VTKs
    ``vtkStaticCellLocator`` in der Bausteinbereichsprüfung (RM-050):
    ``knowledge/parts/range_check.local_wall_thickness`` schießt hier von
    jedem Dreiecksschwerpunkt einwärts und braucht außer dem Abstand auch,
    **welches** Dreieck getroffen wurde, um dessen Normale zu prüfen.

    **Elementweise und nicht über ``np.dot`` oder ``np.einsum``** (RM-187):
    dasselbe Ergebnis auf jeder Maschine.

    **Ab** ``RAY_CULL_PAIRS`` **Paaren über einen räumlichen Index**
    (:func:`_indexed_ray_hits`, RM-214). Die Wandstärke schießt von jedem
    Dreieck aus; ohne Index ist das quadratisch — an einer Dichtschnur mit
    45 000 Dreiecken zwei Milliarden Paare und über sechs Minuten. Jeder
    Strahl steigt einen Baum aus Hüllquadern hinab und rechnet nur gegen die
    Dreiecke der Blätter, deren Quader er durchquert. Der Index entscheidet
    nur, **welche** Paare gerechnet werden, nie den Wert eines Paars: Jedes
    gerechnete Paar trägt dieselben Bits wie im Vollvergleich, und gleiche
    Abstände entscheidet weiter die kleinste Dreiecksnummer. Die eine
    Ausnahme sind fast streifende Treffer an der Grenze von
    ``RAY_PARALLEL_EPS``, deren Lage auch der Vollvergleich nur gerundet
    kennt (Herleitung an :func:`_indexed_ray_hits`). Ein negatives
    ``minimum_travel`` — Treffer hinter dem Ursprung — rechnet immer voll.

    Zurück kommen je Strahl der kleinste positive Treffer (``np.inf`` ohne
    Treffer) und die zugehörige Dreiecksnummer (``-1`` ohne Treffer). Ein
    Abbruch mitten im Lauf liefert den bis dahin gefundenen Teilstand zurück;
    der Aufrufer erkennt ihn an ``cancelled.is_cancelled``.
    """
    triangles = np.asarray(triangles, dtype=float)
    origins = np.asarray(origins, dtype=float)
    directions = np.asarray(directions, dtype=float)
    count = len(origins)
    total = len(triangles)
    if not total or not count:
        return np.full(count, np.inf), np.full(count, -1, dtype=np.int64)
    if total * count <= RAY_CULL_PAIRS or minimum_travel < 0.0:
        return _nearest_ray_hits(
            triangles, origins, directions, edge_margin, minimum_travel, cancelled
        )
    return _indexed_ray_hits(triangles, origins, directions, edge_margin, minimum_travel, cancelled)


def _nearest_ray_hits(
    triangles: np.ndarray,
    origins: np.ndarray,
    directions: np.ndarray,
    edge_margin: float,
    minimum_travel: float,
    cancelled: CancelToken | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Der Vollvergleich: jeder Strahl gegen jedes Dreieck, blockweise.

    Die Blöcke laufen in aufsteigender Dreiecksnummer, und ein späterer Block
    ersetzt nur einen **echt** kleineren Abstand — gleiche Abstände behält
    damit die kleinste Nummer, so wie ``np.argmin`` innerhalb eines Blocks.
    """
    count = len(origins)
    total = len(triangles)
    best_travel = np.full(count, np.inf)
    best_face = np.full(count, -1, dtype=np.int64)
    block = max(1, min(total, RAY_BATCH_PAIRS // max(1, count)))
    for start in range(0, total, block):
        if cancelled is not None and cancelled.is_cancelled:
            break
        chunk = triangles[start : start + block]
        t, inside = _ray_triangle_parameters(
            chunk[None, :, 0, :],
            (chunk[:, 1] - chunk[:, 0])[None, :, :],
            (chunk[:, 2] - chunk[:, 0])[None, :, :],
            origins[:, None, :],
            directions[:, None, :],
            edge_margin,
            minimum_travel,
        )
        masked = np.where(inside, t, np.inf)
        local_best = np.argmin(masked, axis=1)
        local_travel = masked[np.arange(count), local_best]
        better = local_travel < best_travel
        best_travel = np.where(better, local_travel, best_travel)
        best_face = np.where(better, start + local_best, best_face)
    return best_travel, best_face


class _IndexCancelledError(Exception):
    """Der Abbruch mitten im Abstieg — der Aufrufer gibt den Teilstand zurück."""


@dataclass(frozen=True, slots=True)
class _RayIndex:
    """Ein Baum aus Hüllquadern über den Dreiecken, von den Blättern zur Wurzel.

    ``levels[0]`` sind die Blätter, ``levels[-1]`` die Wurzel; Knoten ``i``
    einer Ebene hat die Kinder ``2i`` und ``2i + 1`` der Ebene darunter, soweit
    es sie gibt. ``members`` nennt je Blatt seine Dreiecksnummern, ``-1``
    füllt das letzte auf.
    """

    levels: tuple[tuple[np.ndarray, np.ndarray], ...]
    members: np.ndarray


def _spread_bits(value: np.ndarray) -> np.ndarray:
    """Zehn Bits so auseinandergezogen, dass zwei Nullen zwischen je zweien stehen."""
    value = value & 0x3FF
    value = (value | (value << 16)) & 0x030000FF
    value = (value | (value << 8)) & 0x0300F00F
    value = (value | (value << 4)) & 0x030C30C3
    return (value | (value << 2)) & 0x09249249


def _ray_index(lower: np.ndarray, upper: np.ndarray) -> _RayIndex:
    """Blätter aus je ``RAY_INDEX_LEAF`` Dreiecken in Morton-Reihenfolge, Quader darüber.

    Die Reihenfolge ist nur eine Auswahl: Welche Dreiecke ein Blatt teilen,
    ändert, welche Paare gerechnet werden, nie deren Wert.
    """
    total = len(lower)
    centre = (lower + upper) * 0.5
    low = centre.min(axis=0)
    span = np.maximum(centre.max(axis=0) - low, 1e-300)
    cells = np.clip(np.floor((centre - low) / span * 1023.0), 0, 1023).astype(np.int64)
    code = _spread_bits(cells[:, 0]) | (_spread_bits(cells[:, 1]) << 1)
    code |= _spread_bits(cells[:, 2]) << 2
    order = np.lexsort((np.arange(total), code))
    leaves = -(-total // RAY_INDEX_LEAF)
    flat = np.full(leaves * RAY_INDEX_LEAF, -1, dtype=np.int64)
    flat[:total] = order
    members = flat.reshape(leaves, RAY_INDEX_LEAF)
    # Die Lücken des letzten Blatts erben den Quader seines ersten Dreiecks.
    filled = np.where(members >= 0, members, members[:, :1])
    levels = [(lower[filled].min(axis=1), upper[filled].max(axis=1))]
    while len(levels[-1][0]) > 1:
        below_low, below_high = levels[-1]
        if len(below_low) % 2:
            below_low = np.concatenate((below_low, below_low[-1:]))
            below_high = np.concatenate((below_high, below_high[-1:]))
        levels.append(
            (
                np.minimum(below_low[0::2], below_low[1::2]),
                np.maximum(below_high[0::2], below_high[1::2]),
            )
        )
    return _RayIndex(tuple(levels), members)


def _crossing(
    origins: np.ndarray, inverse: np.ndarray, low: np.ndarray, high: np.ndarray
) -> np.ndarray:
    """Ob der Strahl ``o + t·d`` mit ``t ≥ 0`` den Quader berührt (Scheibentest).

    ``inverse`` ist ``1 / d`` je Achse. Eine Achse ohne Richtungsanteil gibt
    ``0 · ∞`` genau dann, wenn der Ursprung auf der Quaderwand liegt — das
    zählt als berührt, die Auswahl bleibt damit auf der sicheren Seite.
    """
    with np.errstate(invalid="ignore", over="ignore"):
        first = (low - origins) * inverse
        second = (high - origins) * inverse
    # ``minimum`` und ``maximum`` reichen ein ``NaN`` weiter (``fmin`` nähme
    # die andere Grenze und verwürfe den Quader); es gibt die Achse frei.
    near = np.minimum(first, second)
    far = np.maximum(first, second)
    near = np.where(np.isnan(near), -np.inf, near)
    far = np.where(np.isnan(far), np.inf, far)
    entry = np.maximum(np.maximum(near[:, 0], near[:, 1]), near[:, 2])
    leave = np.minimum(np.minimum(far[:, 0], far[:, 1]), far[:, 2])
    return np.asarray((entry <= leave) & (leave >= 0.0))


def _indexed_ray_hits(
    triangles: np.ndarray,
    origins: np.ndarray,
    directions: np.ndarray,
    edge_margin: float,
    minimum_travel: float,
    cancelled: CancelToken | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Dieselbe Antwort wie :func:`_nearest_ray_hits`, gegen weniger Dreiecke je Strahl.

    **Warum die Auswahl nichts verliert.** Jedes Dreieck sitzt in genau einem
    Blatt, jeder Knotenquader umschließt die Quader darunter, und jeder
    Dreiecksquader ist um das baryzentrische ``edge_margin`` des Treffertests
    und ein Milliardstel der Szenendiagonale gewachsen. Ein Treffer liegt auf
    dem Strahl und im gewachsenen Quader seines Dreiecks; der Strahl berührt
    damit jeden Quader auf dem Weg von der Wurzel zu diesem Blatt, und der
    Scheibentest (:func:`_crossing`) verwirft keinen davon — er rechnet in
    den Koordinaten des Strahls, seine Rundung liegt weit unter der Zugabe.
    Jedes Dreieck erreicht ein Strahl höchstens einmal, und das Minimum mit
    der kleinsten Nummer bei Gleichstand ist dasselbe wie im Vollvergleich.

    Die Ausnahme: Möller-Trumbore rechnet ``t``, ``u`` und ``v`` eines fast
    streifenden Dreiecks mit einem relativen Fehler um ``ε / s``, ``s`` dem
    Sinus aus Determinante und Kanten. Unter ``s`` von etwa ``10⁻¹⁴`` — ganz am
    Rand dessen, was ``RAY_PARALLEL_EPS`` noch als Treffer zählt — kann der
    Vollvergleich einen Treffer melden, den die Geometrie nicht hat und dessen
    Quader der Strahl nicht berührt. Dort war auch der Vollvergleich keine
    geometrische Aussage mehr.

    Ein Strahl der Länge null trifft nie — die Determinante ist genau null —
    und bekommt ``inf`` ohne Rechnung. Nicht endliche Strahlen und Szenen mit
    nicht endlichen Koordinaten rechnet der Vollvergleich wie bisher.
    """
    count = len(origins)
    best_travel = np.full(count, np.inf)
    best_face = np.full(count, -1, dtype=np.int64)
    lower = triangles.min(axis=1)
    upper = triangles.max(axis=1)
    scene_low = np.minimum(lower.min(axis=0), origins.min(axis=0))
    scene_high = np.maximum(upper.max(axis=0), origins.max(axis=0))
    span = scene_high - scene_low
    diagonal = float(np.sqrt(span[0] * span[0] + span[1] * span[1] + span[2] * span[2]))
    if not math.isfinite(diagonal) or diagonal <= 0.0:
        # Eine Szene ohne Ausdehnung oder mit nicht endlichen Koordinaten hat
        # keine Quader; der Vollvergleich antwortet dort wie bisher.
        return _nearest_ray_hits(
            triangles, origins, directions, edge_margin, minimum_travel, cancelled
        )
    guard = diagonal * 1e-9 + 1e-12
    # Ein Treffer zählt baryzentrisch bis ``edge_margin`` neben dem Dreieck —
    # also höchstens um so viele Kantenlängen außerhalb seines Quaders.
    slack = (upper - lower).max(axis=1) * (3.0 * max(edge_margin, 0.0)) + guard
    index = _ray_index(lower - slack[:, None], upper + slack[:, None])

    length = np.sqrt(_rowwise_dot(directions, directions))
    finite = np.isfinite(length) & np.isfinite(origins).all(axis=1)
    usable = np.flatnonzero(finite & (length > 0.0))
    with np.errstate(divide="ignore"):
        inverse = 1.0 / directions
    pending = [
        usable[start : start + RAY_INDEX_RAYS] for start in range(0, len(usable), RAY_INDEX_RAYS)
    ]
    while pending:
        if cancelled is not None and cancelled.is_cancelled:
            return best_travel, best_face
        rays = pending.pop()
        try:
            candidates = _index_candidates(index, origins, inverse, rays, cancelled)
        except _IndexCancelledError:
            return best_travel, best_face
        if candidates is None:
            # Zu viele Paare auf einmal: dieselbe Gruppe in zwei Hälften.
            half = len(rays) // 2
            pending.extend((rays[:half], rays[half:]))
            continue
        pair_ray, pair_face = candidates
        if not len(pair_ray):
            continue
        masked = np.empty(len(pair_ray))
        for start in range(0, len(pair_ray), RAY_BATCH_PAIRS):
            part = slice(start, start + RAY_BATCH_PAIRS)
            chosen = triangles[pair_face[part]]
            t, inside = _ray_triangle_parameters(
                chosen[:, 0, :],
                chosen[:, 1] - chosen[:, 0],
                chosen[:, 2] - chosen[:, 0],
                origins[pair_ray[part]],
                directions[pair_ray[part]],
                edge_margin,
                minimum_travel,
            )
            masked[part] = np.where(inside, t, np.inf)
        # Je Strahl der kleinste Abstand, bei Gleichstand die kleinste Nummer.
        order = np.lexsort((pair_face, masked, pair_ray))
        first = np.ones(len(order), dtype=bool)
        first[1:] = pair_ray[order][1:] != pair_ray[order][:-1]
        winners = order[first]
        hit = np.isfinite(masked[winners])
        best_travel[pair_ray[winners[hit]]] = masked[winners[hit]]
        best_face[pair_ray[winners[hit]]] = pair_face[winners[hit]]

    # Länge null trifft nie und bleibt bei ``inf``; nicht endliche Strahlen
    # rechnet der Vollvergleich wie bisher.
    open_rays = np.flatnonzero(~finite)
    if len(open_rays):
        travel, face = _nearest_ray_hits(
            triangles,
            origins[open_rays],
            directions[open_rays],
            edge_margin,
            minimum_travel,
            cancelled,
        )
        best_travel[open_rays] = travel
        best_face[open_rays] = face
    return best_travel, best_face


def _index_candidates(
    index: _RayIndex,
    origins: np.ndarray,
    inverse: np.ndarray,
    rays: np.ndarray,
    cancelled: CancelToken | None,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Die Strahl-Dreieck-Paare, deren Blattquader der Strahl durchquert.

    ``None``, wenn eine Ebene mehr als ``RAY_INDEX_PAIRS`` Paare hielte und die
    Gruppe mehr als einen Strahl hat — der Aufrufer teilt sie dann. Gefragt,
    ob abgebrochen wurde, wird je Ebene; ein Abbruch wirft
    :class:`_IndexCancelledError`, damit der Aufrufer nicht ein zweites Mal fragt.
    """
    pair_ray = rays
    pair_node = np.zeros(len(rays), dtype=np.int64)
    for depth in range(len(index.levels) - 1, -1, -1):
        if cancelled is not None and cancelled.is_cancelled:
            raise _IndexCancelledError
        low, high = index.levels[depth]
        keep = _crossing(origins[pair_ray], inverse[pair_ray], low[pair_node], high[pair_node])
        pair_ray = pair_ray[keep]
        pair_node = pair_node[keep]
        if depth == 0:
            break
        width = len(index.levels[depth - 1][0])
        pair_ray = np.repeat(pair_ray, 2)
        pair_node = (pair_node[:, None] * 2 + np.array([0, 1])).reshape(-1)
        exists = pair_node < width
        pair_ray = pair_ray[exists]
        pair_node = pair_node[exists]
        if len(pair_ray) > RAY_INDEX_PAIRS and len(rays) > 1:
            return None
    faces = index.members[pair_node]
    pair_ray = np.repeat(pair_ray, faces.shape[1])
    pair_face = faces.reshape(-1)
    real = pair_face >= 0
    return pair_ray[real], pair_face[real]


def distance_to_triangles(triangles: np.ndarray, point: np.ndarray) -> float:
    """Der kürzeste Abstand von einem Punkt zu einer gegebenen Menge Dreiecke.

    Die Frage hinter „welches Merkmal liegt unter diesem Klick?" (§18.5): Die
    Dreiecke sind die eines erkannten Merkmals, der Punkt ist die Stelle, auf
    die gezeigt wurde. Gerechnet wird gegen den nächsten **Ort auf dem
    Dreieck** und nicht gegen den nächsten Eckpunkt — der Unterschied ist kein
    Feinschliff: Die Deckfläche der Platte aus dem Korpus besteht aus zwei
    großen Dreiecken, und ein Klick in ihre Mitte liegt vierzig Millimeter von
    jedem ihrer Eckpunkte entfernt.

    **Ohne den Näherungsindex**, anders als :func:`on_surface`: Hier steht die
    Dreiecksmenge schon fest, es ist also nichts zu suchen, sondern nur zu
    rechnen — reine Arithmetik über ein Array. Damit bleibt der Weg an
    ``rtree`` vorbei, und was dort oben über Zugriffsverletzungen steht, gilt
    hier nicht.

    Eine leere Menge hat keinen Abstand und bekommt unendlich — der Aufrufer
    vergleicht gegen eine Reichweite, und „unendlich" fällt dort heraus, ohne
    dass er einen Sonderfall braucht.
    """
    gaps = distances_to_triangles(triangles, point)
    return float(gaps.min()) if len(gaps) else float("inf")


def distances_to_triangles(triangles: np.ndarray, point: np.ndarray) -> np.ndarray:
    """Dasselbe je Dreieck statt als Minimum — ein Abstand für jedes.

    Der Pinsel braucht beides (:mod:`app.core.geom.paint`): das nächste Dreieck
    als Startpunkt seines Laufes und die einzelnen Abstände als Grenze seines
    Umfangs. Beides aus derselben Rechnung, und die steht **hier**, weil
    ``trimesh.triangles`` keine Signaturen trägt und diese Datei die typisierte
    Engführung dafür ist — dasselbe Muster wie :func:`concatenated`.
    """
    if not len(triangles):
        return np.empty(0, dtype=float)
    query = np.repeat(np.asarray(point, dtype=float).reshape(1, 3), len(triangles), axis=0)
    nearest = trimesh.triangles.closest_point(np.asarray(triangles, dtype=float), query)
    return np.asarray(np.linalg.norm(np.asarray(nearest, dtype=float) - query, axis=1), dtype=float)


#: Wie viele Eckpunkte höchstens in die konvexe Hülle eingehen
#: (:func:`hull_planes`). Dieselbe Zahl und derselbe Grund wie beim
#: Schattenumriss der Ansicht: Bei einer feinen Kugel liegt **jeder** Punkt auf
#: der Hülle, und die exakte Rechnung kostet dann mehr als sie wert ist.
#: Gemessen an ``dense_1m.stl`` (655 362 Eckpunkte): **5084 ms** exakt gegen
#: **20 ms** über die Stichprobe. An der Korpusplatte liefern beide dasselbe —
#: zwölf Flächen, Volumen 32 000 mm³.
HULL_SAMPLE_LIMIT = 4096


def planar_outline(points: np.ndarray) -> np.ndarray | None:
    """Der geordnete Rand einer ebenen Punktwolke, gegen den Uhrzeigersinn.

    Die konvexe Hülle in zwei Dimensionen, als ``(n, 2)``; ``None``, wo keine
    Fläche herauskommt — weniger als drei Punkte, oder alle auf einer Linie.

    **Über GEOS und nicht über Qhull**, und das ist keine Geschmacksfrage:
    SciPys ``ConvexHull`` führt Qhulls Ausgabe über ``tempfile.mkstemp`` und
    legt damit **je Aufruf eine Datei** an. Die Regel dazu steht seit dem
    12.09.2026 in ``.claude/rules/kern.md`` („gehört nicht in eine Schleife
    über Flecken") — die Schattenprojektion der Ansicht tat es trotzdem, eine
    Ebene höher: Gemessen an ``1-24+scale+polebarn.3mf`` (89 Körper) kostete
    **eine** Kamerageste 1843 ms, davon 1679 ms in dieser Hülle und 635 ms
    allein im Anlegen der Temporärdateien (16.09.2026, Robert: „nach jedem
    kameraverschieben hängt es erstmal").

    Sie liegt hier und nicht in der Ansicht, weil dort keine Geometrie
    gerechnet wird — dieselbe Grenze wie bei :func:`hull_planes`, das die
    Ansicht für ihre Klickstrahlen fragt.
    """
    from shapely.geometry import MultiPoint

    grid = np.asarray(points, dtype=float)[:, :2]
    if len(grid) < 3:
        return None
    hull = MultiPoint(grid).convex_hull
    if hull.geom_type != "Polygon":
        # Alle Punkte auf einer Linie: das ist kein Umriss, und ein Schatten
        # ohne Fläche ist keiner. GEOS gibt dort ein ``LineString`` zurück, wo
        # Qhull einen ``QhullError`` warf.
        return None
    # Der Ring schließt sich mit seinem ersten Punkt; der letzte fällt weg,
    # damit der Rand so herauskommt, wie ihn ein Streckenzug erwartet. GEOS
    # ordnet den äußeren Ring im Uhrzeigersinn, Qhull gab ihn dagegen — und
    # ``clip_polygon`` verlangt eine Richtung, also wird umgedreht.
    return np.asarray(hull.exterior.coords, dtype=float)[-2::-1]


def planar_outlines(clouds: Sequence[np.ndarray]) -> list[np.ndarray | None]:
    """:func:`planar_outline` für viele Punktwolken in einem Aufruf.

    Dieselbe Antwort je Wolke, aber **ein** Gang durch GEOS statt eines je
    Wolke: Der Schatten der Ansicht rechnet am Ende jeder Kamerageste einen
    Umriss je Körperstück, und je Aufruf kostete das Anlegen des
    ``MultiPoint`` und das Auslesen des Rings mehr als die Hülle selbst —
    gemessen am 22.09.2026 an einem Piratenschiff aus 17 Körpern und 58
    Stücken: 22 ms je Geste, davon zwei Drittel Aufrufaufwand.
    """
    import shapely

    grids = [np.asarray(cloud, dtype=float).reshape(-1, 3)[:, :2] for cloud in clouds]
    wanted = [index for index, grid in enumerate(grids) if len(grid) >= 3]
    answers: list[np.ndarray | None] = [None] * len(grids)
    if not wanted:
        return answers
    coordinates = np.vstack([grids[index] for index in wanted])
    owners = np.repeat(np.arange(len(wanted)), [len(grids[index]) for index in wanted])
    hulls = shapely.convex_hull(shapely.multipoints(coordinates, indices=owners))
    polygons = shapely.get_type_id(hulls) == 3
    rings = shapely.get_exterior_ring(hulls[polygons])
    points, belongs = shapely.get_coordinates(rings, return_index=True)
    places = np.flatnonzero(polygons)
    starts = np.searchsorted(belongs, np.arange(len(rings)))
    ends = np.append(starts[1:], len(points))
    for ring, (start, end) in enumerate(zip(starts, ends, strict=True)):
        # Wie :func:`planar_outline`: der schließende Punkt fällt weg, und die
        # Richtung wird gegen den Uhrzeigersinn gedreht.
        answers[wanted[int(places[ring])]] = np.asarray(points[start:end], dtype=float)[-2::-1]
    return answers


def hull_planes(mesh: Mesh) -> np.ndarray | None:
    """Die konvexe Hülle eines Netzes als Halbräume, ``n·x + d <= 0`` innen.

    Nicht als Netz, sondern als Ebenengleichungen: Die Frage dahinter ist „läuft
    dieser Sichtstrahl **durch** den Körper hindurch?" (:func:`ray_span_in_hull`),
    und die beantwortet ein Halbraumschnitt in einer Handvoll Rechenschritten,
    während ein Strahl gegen ein Hüllnetz wieder jedes Dreieck anfassen müsste.

    **Die Stichprobe ist der Kostendeckel**, und sie unterschätzt die Hülle
    leicht: Jeder ``n``-te Eckpunkt, dazu die äußersten in allen sechs
    Achsenrichtungen, damit ein gescannter Halter seine Ecken behält. Für die
    Frage, ob ein Klick durch eine Öffnung geht, ist das genau genug — die
    Öffnung ist millimeterweit, die Abweichung liegt im Bereich der Punktdichte.

    ``None`` heißt „keine räumliche Hülle": ein ebener oder entarteter Körper —
    oder einer ohne Eckpunkte, denn das ``Mesh``-Protokoll (§9) sagt nichts über
    ein ``raw`` zu; ein B-Rep-Körper hat keines. Der Aufrufer hat dann keinen
    Innenraum zu prüfen und braucht dafür keinen Sonderfall.
    """
    from scipy.spatial import ConvexHull, QhullError

    raw = getattr(mesh, "raw", None)
    if raw is None:
        return None
    points = np.asarray(raw.vertices, dtype=float)
    if len(points) < 4:
        return None
    if len(points) > HULL_SAMPLE_LIMIT:
        step = len(points) // HULL_SAMPLE_LIMIT + 1
        extremes = np.concatenate(
            [points[points[:, axis].argmin()][None] for axis in range(3)]
            + [points[points[:, axis].argmax()][None] for axis in range(3)]
        )
        points = np.concatenate([points[::step], extremes])
    try:
        return np.asarray(ConvexHull(points).equations, dtype=float)
    except QhullError as problem:
        # Flach, entartet oder alle Punkte auf einer Linie — kein Innenraum.
        _log.info("convex hull unavailable: %s", problem)
        return None


def ray_span_in_hull(
    planes: np.ndarray, origin: np.ndarray, direction: np.ndarray
) -> tuple[float, float] | None:
    """Von wo bis wo ein Strahl innerhalb dieser Halbräume läuft.

    Der Schnitt eines Strahls mit einem konvexen Körper, gerechnet wie das
    Kappen an Schichten: Jede Ebene schiebt entweder den Eintritt nach hinten
    oder den Austritt nach vorn, und bleibt am Ende ein Stück übrig, geht der
    Strahl hindurch. Zurück kommen die beiden Strahlparameter in Millimetern,
    gemessen von ``origin`` entlang ``direction`` (das normiert erwartet wird),
    oder nichts.

    Der Eintritt kann ``-inf`` sein — dann liegt der Ursprung selbst innen. Wer
    nur nach vorn sehen will, klemmt auf null; hier bleibt es stehen, weil die
    Aussage „von hier bis dort" nichts über die Blickrichtung des Aufrufers
    voraussetzen soll.
    """
    # Nur auf leer, nicht auf ``None``: Der Typ sagt ``np.ndarray``, und der
    # einzige Aufrufer fängt das fehlende Hüllwerk von ``hull_planes`` schon
    # eine Zeile vorher ab.
    if not len(planes):
        return None
    normals = np.asarray(planes, dtype=float)[:, :3]
    offsets = np.asarray(planes, dtype=float)[:, 3]
    along = normals @ np.asarray(direction, dtype=float)
    gap = normals @ np.asarray(origin, dtype=float) + offsets

    # Parallel zu einer Ebene und außerhalb von ihr: der Strahl kommt nie hinein.
    parallel = np.abs(along) <= EPS_GEOM
    if bool(np.any(parallel & (gap > EPS_GEOM))):
        return None

    crossing = ~parallel
    if not bool(np.any(crossing)):
        return None
    steps = -gap[crossing] / along[crossing]
    leaving = along[crossing] > 0.0
    enter = float(steps[~leaving].max()) if bool(np.any(~leaving)) else -math.inf
    leave = float(steps[leaving].min()) if bool(np.any(leaving)) else math.inf
    return (enter, leave) if enter < leave else None


def read_mesh(payload: bytes, suffix: str) -> MeshData:
    """Parst eine Datei, die schon im Speicher liegt. Noch keine
    Aufbereitung — die ist §17.1.

    GLB und GLTF bleiben hier in ihren Quellachsen und Quelleinheiten.
    Knotenmatrizen löst der Parser auf; die Umrechnung von Y-oben/Metern nach
    Z-oben/Millimetern übernimmt die registrierte ``load``-Operation anhand
    ihrer gespeicherten Parameter ``coordinates`` und ``unit``. Neue Importe
    wählen die glTF-Konvention, migrierte Projekte behalten ``legacy_raw``.
    Rohe Generatorquellen verwenden ebenfalls diesen ausdrücklichen Altweg,
    weil der Generator selbst keine glTF-Achsenkonvention zusichert.
    """
    normalised = suffix.lower()
    if normalised not in TRIMESH_SUFFIXES:
        raise ValidationError(
            field="file",
            detail=_("Dieses Dateiformat kann nicht gelesen werden."),
            constraint="unsupported_format",
            values={"suffix": suffix, "known": list(TRIMESH_SUFFIXES)},
        )
    if normalised == ".gltf":
        _check_embedded_gltf(payload)

    try:
        # ``load_mesh`` statt ``load(force="mesh")``: trimesh 5 führt ``load``
        # nur noch als Rückwärtskompatibilität und nennt es im Docstring
        # veraltet. Der Nachfolger sagt schon im Rückgabetyp, dass ein
        # ``Trimesh`` herauskommt — mehrere Körper in einer Datei verschweißt
        # er wie zuvor ``force="mesh"``, gemessen an einer GLB mit zwei
        # Quadern: beide Wege 24 Dreiecke.
        loaded = _stl_body(payload) if normalised == ".stl" else None
        if loaded is None:
            loaded = trimesh.load_mesh(
                io.BytesIO(payload), file_type=normalised.lstrip("."), process=False
            )
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # trimesh wirft eine breite Palette an Parserfehlern
        raise ValidationError(
            field="file",
            detail=_("Die Datei ließ sich nicht lesen; sie ist vermutlich beschädigt."),
            constraint="unreadable",
            values={"suffix": suffix},
        ) from problem

    # Eine Datei, an der der Parser scheitert, ohne zu werfen, kommt als leerer
    # Körper heraus — das ist der Fall, den die Zeile abfängt.
    if not len(loaded.faces):
        raise ValidationError(
            field="file",
            detail=_("Die Datei enthält keine Dreiecksgeometrie."),
            constraint="no_geometry",
            values={"suffix": suffix},
        )
    return MeshData.of(loaded)


def _stl_body(payload: bytes) -> trimesh.Trimesh | None:
    """Eine STL direkt aus ihrem Leser, ohne den Umweg über eine Szene (RM-567).

    ``trimesh.load_mesh`` baut eine Szene, zieht ihr Netz heraus und kopiert
    es; Szene und Original bleiben als Ring liegen, den erst die
    Speicherbereinigung abräumt — am Spiderman 254 MB, am Murmelbrett 650 MB,
    und im Fenster räumt sie nur der Hauptfaden nach seinen Schwellen ab
    (``ui.leash.collect_in_main_thread``). Dieselben Ecken, Dreiecke und
    Dreiecksattribute, ohne die Normalen aus der Datei — die Kopie dort
    verwarf sie ebenfalls; geprüft an 65 STL aus Korpus und ``F:\\3D Dateien``.
    Eine ASCII-STL mit mehreren Körpern ist eine Szene; für sie ``None``.
    """
    loaded = trimesh.exchange.stl.load_stl(io.BytesIO(payload))
    if not isinstance(loaded, dict) or "geometry" in loaded:
        return None
    return trimesh.Trimesh(
        vertices=loaded["vertices"],
        faces=loaded["faces"],
        face_attributes=loaded.get("face_attributes"),
        metadata=loaded.get("metadata"),
        process=False,
    )


def _check_embedded_gltf(payload: bytes) -> None:
    """Lehnt eine allein nicht lesbare GLTF mit einem Ausweg ab.

    Der Speicherleser hat keinen Ordner, aus dem er ``.bin``- oder Bilddateien
    holen könnte. Lokale Dateien macht :func:`read_local_payload` vorher
    eigenständig; ein Download muss bereits eigenständig sein oder als GLB
    vorliegen. Ohne diese Prüfung endet trimesh an einer gewöhnlichen GLTF mit
    einem rohen ``TypeError`` statt einer Meldung für den Nutzer.
    """
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as problem:
        raise ValidationError(
            field="file",
            detail=_("Die GLTF-Datei enthält kein lesbares JSON."),
            constraint="unreadable",
        ) from problem
    if not isinstance(document, dict):
        raise ValidationError(
            field="file",
            detail=_("Die GLTF-Datei enthält kein gültiges Modelldokument."),
            constraint="unreadable",
        )
    for section in ("buffers", "images"):
        entries = document.get(section, [])
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            raise ValidationError(
                field="file",
                detail=_("Die GLTF-Datei enthält kein gültiges Modelldokument."),
                constraint="unreadable",
                values={"section": section},
            )
        external = [
            entry["uri"]
            for entry in entries
            if isinstance(entry.get("uri"), str)
            and entry["uri"]
            and not entry["uri"].lower().startswith("data:")
        ]
        if external:
            raise ValidationError(
                field="file",
                detail=_(
                    "Diese GLTF braucht Begleitdateien. Öffnen Sie sie lokal zusammen "
                    "mit diesen Dateien, oder exportieren Sie das Modell als GLB."
                ),
                constraint="missing_file",
                values={"dependencies": external},
            )


def lifted_caps(raw: trimesh.Trimesh, caps: Sequence[tuple[Any, Any, float]]) -> trimesh.Trimesh:
    """Hebt ebene Deckel eines geschlossenen Netzes an und ergänzt die Wand darunter.

    Je Deckel ``(Dreiecke, Richtung, Strecke)``: Seine Punkte werden um die
    Strecke entlang der Richtung kopiert, der Deckel wandert auf die Kopie, und
    zwischen altem und neuem Rand entsteht die Wand. Die Richtung ist ein
    Vektor für alle Punkte oder einer je Punkt, in der Folge von ``np.unique``
    seiner Dreiecke — so setzt ``prepare_ops._continued_walls`` die Wand selbst
    fort. Die alten Randpunkte bleiben bei den Flächen darunter; das Netz
    bleibt geschlossen, und was davor war, behält seine Punkte und Dreiecke in
    derselben Reihenfolge.

    Der Netz-Zwilling von ``brep.edit.collared`` (ein Prisma über einer ebenen
    Fläche) und die eine Stelle, an der das am Netz geschieht: für die
    Mündungen eines Hohlraums (``prepare_ops._past_the_mouths``) und für die
    Öffnung eines abtragenden Bausteins, der schräg zu seiner Fläche steht
    (``knowledge.parts.ops._opened_to_the_face``). Die Dreiecke eines Deckels
    werden vor dem ersten Anheben gelesen — zwei Deckel mit gemeinsamem Rand
    sehen einander so, wie sie waren.
    """
    points = np.asarray(raw.vertices, dtype=np.float64)
    faces = np.asarray(raw.faces, dtype=np.int64).copy()
    chosen = [(np.asarray(indices, dtype=np.int64), faces[indices]) for indices, _n, _d in caps]
    added: list[Any] = [points]
    collars: list[Any] = []
    next_index = len(points)
    for (indices, cap), (_indices, normal, reach) in zip(chosen, caps, strict=True):
        members = np.unique(cap)
        directed = np.vstack([cap[:, [0, 1]], cap[:, [1, 2]], cap[:, [2, 0]]])
        _, inverse, counts = np.unique(
            np.sort(directed, axis=1), axis=0, return_inverse=True, return_counts=True
        )
        rim = directed[counts[inverse.ravel()] == 1]
        lifted = np.full(int(members.max()) + 1, -1, dtype=np.int64)
        lifted[members] = np.arange(next_index, next_index + len(members))
        added.append(points[members] + np.asarray(normal, dtype=np.float64) * reach)
        next_index += len(members)
        faces[indices] = lifted[cap]
        first, second = rim[:, 0], rim[:, 1]
        collars.append(np.column_stack([first, second, lifted[second]]))
        collars.append(np.column_stack([first, lifted[second], lifted[first]]))
    return trimesh.Trimesh(
        vertices=np.vstack(added), faces=np.vstack([faces, *collars]), process=False
    )


def concatenated(parts: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Verschweißt mehrere Netze zu einem.

    trimesh annotiert ``concatenate`` mit dem gemeinsamen Obertyp ``Geometry``,
    weil auch Punktwolken hineinpassen; aus lauter ``Trimesh`` entsteht aber
    immer ein ``Trimesh``. Die eine Engführung lebt hier, nicht an jeder
    Aufrufstelle.
    """
    merged = trimesh.util.concatenate(parts)
    assert isinstance(merged, trimesh.Trimesh)
    return merged


class MeshCodec:
    """Codec für den Platten-Cache (§38). Registriert, sobald der Kern da ist."""

    suffix = ".npz"

    def stores(self, mesh: Mesh) -> bool:
        """Nur Netze. Ein exakter Körper (§30) wird neu gerechnet statt gelegt.

        Die Frage gibt es, damit der Aufrufer den Normalfall nicht am
        geworfenen ``TypeError`` erkennen muss — der bedeutet dort auch einen
        Programmfehler, und beide sahen gleich aus.
        """
        return isinstance(mesh, MeshData)

    def dumps(self, mesh: Mesh) -> bytes:
        # Bleibt: Wer ohne zu fragen ablegt, hat einen Programmfehler, und der
        # soll auffallen. ``stores`` ist die Frage, das hier die Zusicherung.
        if not isinstance(mesh, MeshData):
            raise TypeError("the disk cache can only store MeshData")
        return mesh.to_bytes()

    def loads(self, data: bytes) -> Mesh:
        return MeshData.from_bytes(data)
