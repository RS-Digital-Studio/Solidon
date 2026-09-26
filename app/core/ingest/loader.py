"""Die Eingangsstufe (Bauplan §17.1).

Jede geladene Datei geht dieselben sechs Schritte, in dieser Reihenfolge:

1. Einheit bestimmen — STL trägt keine, also entscheidet eine Heuristik und
   **fragt, wenn sie sich nicht sicher ist**, statt anzunehmen;
2. Eckpunkte verschweißen, mit einer Toleranz, die mit der Modellgröße
   skaliert;
3. entartete Dreiecke entfernen (Nullfläche, Nadeln, Duplikate);
4. Normalen vereinheitlichen und die Ausrichtung prüfen;
5. Komponenten zählen und Kleinstteile **melden** statt still zu löschen;
6. den Schwerpunkt finden, das Aufsetzen aufs Bett und das Zentrieren
   darauf **anbieten**.

Alles, was die Stufe getan hat, landet in ``IngestInfo`` und in Befunden — der
Prüfbericht (§17.3) und der Steckbrief können also sagen, was auf dem Weg
hinein geändert wurde.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import math
import mimetypes
import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import unquote, urlsplit

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import (
    CANCEL,
    CHOOSE_ANOTHER_FILE,
    RESOLVE_INTERSECTIONS,
    SPLIT_BODIES,
    UserError,
    ValidationError,
)
from app.core.geom.mesh import (
    TRIMESH_SUFFIXES,
    MeshData,
    concatenated,
    edge_table,
    face_components,
    read_mesh,
)
from app.core.geom.repair import (
    is_closed,
    open_edge_count,
    parts_can_be_merged,
    parts_that_cross,
    small_components,
)
from app.core.geom.repair import weld as weld_points
from app.core.log import get_logger
from app.core.perceive.maps import MAP_LIMIT_TRIANGLES
from app.core.types import BoundingBox, CancelToken, Finding, IngestInfo, ProgressFn, Vec3
from app.core.units import (
    EPS_GEOM,
    LengthUnit,
    to_mm,
    weld_digits,
    weld_tolerance,
)
from app.i18n import _

if TYPE_CHECKING:
    import zipfile

_log = get_logger(__name__)

#: Endungen, die die Eingangsstufe öffnen kann (§25, „Import"): alles, was
#: trimesh zu einem Körper liest, und 3MF als Baugruppe. Dateidialog,
#: Ablagefeld, Kommandozeile und Netzimport lesen dieselbe Liste — eine
#: eigene Aufzählung in der Oberfläche wäre ein Versprechen, das vom Leser
#: wegdriften kann.
READABLE_SUFFIXES: Final[tuple[str, ...]] = (".stl", ".3mf", *TRIMESH_SUFFIXES[1:])

#: Importgrenzen (§32). Eine klare Meldung schlägt einen Speicherüberlauf.
MAX_TRIANGLES: Final = 20_000_000
MAX_FILE_BYTES: Final = 512 * 1024 * 1024

#: Ein 3MF-Archiv darf weder sein Zentralverzeichnis noch den Entpacker als
#: zweite, von der Dateigröße unabhängige Ressource missbrauchen. Kleine XML-
#: Dateien dürfen sich stark packen; erst ab einem MiB ist das Verhältnis
#: aussagekräftig.
MAX_ARCHIVE_ENTRIES: Final = 4096
MIN_RATIO_ENTRY_BYTES: Final = 1024 * 1024
MAX_COMPRESSION_RATIO: Final = 250.0
_ZIP_END_SIGNATURE: Final = b"PK\x05\x06"
_ZIP_CENTRAL_SIGNATURE: Final = b"PK\x01\x02"
_ZIP64_END_SIGNATURE: Final = b"PK\x06\x06"
_ZIP64_LOCATOR_SIGNATURE: Final = b"PK\x06\x07"
_ZIP_END_RECORD: Final = struct.Struct("<4s4H2LH")
_ZIP64_END_RECORD: Final = struct.Struct("<4sQ2H2L4Q")
_ZIP64_LOCATOR: Final = struct.Struct("<4sLQL")
_ZIP_CENTRAL_HEADER_BYTES: Final = 46
_MAX_ZIP_COMMENT_BYTES: Final = 65_535
_ARCHIVE_COMPARE_BYTES: Final = 64 * 1024

#: Darüber sagt die Eingangsstufe etwas. Keine Grenze — die darüber liegt eine
#: Größenordnung höher —, sondern die Größe, ab der die Analyse aufhört helfen
#: zu können. Ein Community-Modell mit zwei Millionen Dreiecken ist etwas, das
#: einem normalerweise gereicht wird, und es sollte sagen, was es ist, statt
#: nur langsam zu sein.
#:
#: **Keine eigene Zahl.** Hier stand 500 000, und damit gab es drei Schwellen
#: für dieselbe Frage: Die Karten verweigern ab 120 000, die Merkmalserkennung
#: ab 200 000 (§31) — die Meldung versprach also, was längst geschehen war,
#: und zwischen 200 000 und 500 000 schwieg sie ganz. Sie ist die Grenze der
#: Analysekarten: Ob die Merkmalserkennung ausgelassen wird, entscheidet seit
#: dem 24.09.2026 die Frage beim Laden (§21.1), und das meldet der Körper.
HEAVY_TRIANGLES: Final = MAP_LIMIT_TRIANGLES

#: Was ein druckbares Teil üblicherweise misst, in Millimetern — die
#: Untergrenze fest, die Obergrenze als Vorgabe ohne Drucker. Mit Drucker
#: gilt :func:`plausible_reach`: das Doppelte seiner Bauraumdiagonale, wenn
#: das größer ist. Ein Teil, das ein 256er Bett füllt, hat 440 mm Diagonale
#: und lief bis zum 02.09.2026 in die Einheitenfrage, obwohl es in
#: Millimetern die einzige sinnvolle Lesart hatte; wer ein Teil zum Teilen
#: einliest, darf auch doppelt so groß sein wie sein Drucker.
PLAUSIBLE_MIN_MM: Final = 10.0
PLAUSIBLE_MAX_MM: Final = 300.0
PLAUSIBLE_REACH_FACTOR: Final = 2.0


def plausible_reach(build_volume: tuple[float, float, float] | None) -> float:
    """Bis zu welcher Hüllquader-Diagonale (mm) eine Lesart plausibel ist.

    Ohne Bauraum die feste Vorgabe; mit Bauraum das Doppelte seiner Diagonale,
    wenn das mehr ist. Nie weniger als die Vorgabe — ein kleiner Drucker macht
    kein normales Teil unglaubwürdig.
    """
    if build_volume is None:
        return PLAUSIBLE_MAX_MM
    diagonal = math.sqrt(sum(float(side) ** 2 for side in build_volume))
    return max(PLAUSIBLE_MAX_MM, PLAUSIBLE_REACH_FACTOR * diagonal)


#: Einheiten, in denen eine Datei geschrieben sein könnte — die
#: wahrscheinlichste zuerst.
CANDIDATE_UNITS: Final[tuple[LengthUnit, ...]] = ("mm", "cm", "in", "m")

#: Die Datei so zu nehmen, wie sie dasteht. Der Kern rechnet in Millimetern
#: (§11.1), eine Zahl ohne Umrechnung ist also eine Zahl in Millimetern — und
#: das ist keine Vermutung über die Datei, sondern die einzige Lesart, die
#: nichts hinzudichtet.
MEASURED_UNIT: Final[LengthUnit] = "mm"


def read_model(payload: bytes, suffix: str) -> MeshData:
    """Eine Modelldatei aus dem Speicher als **ein** Körper — auch eine 3MF.

    Für alles, was trimesh liest, ist das :func:`app.core.geom.mesh.read_mesh`.
    Eine 3MF ist eine Baugruppe; wer ihre Körper getrennt will, fragt
    :func:`app.core.ingest.threemf.read_objects`. Hier werden sie verschweißt,
    denn das ist, was ein einzelner Rückgabewert sein kann. Die Slots reisen
    nur aus einer Datei mit einem Körper mit: jedes Teil nummeriert seine
    Slots ab null, und diese Nummerierungen ohne gemeinsame Palette zu
    mischen setzte das falsche Filament auf die Hälfte der Dreiecke (§20).

    Bis zum 02.09.2026 tat das ``geom.mesh.read_mesh`` selbst und holte sich
    den Leser dafür aus ``export`` — die unterste Schicht kannte ein
    Ausgabemodul. Jetzt entscheidet die Eingangsstufe, was eine Datei ist.
    """
    if suffix.lower() == ".3mf":
        from app.core.ingest import threemf

        parts = threemf.read_objects(payload)
        if len(parts) == 1:
            return parts[0].mesh
        if parts:
            return MeshData.of(concatenated([part.mesh.raw for part in parts]))
        # Eine 3MF ohne lesbares Objekt geht denselben Weg wie vorher: trimesh
        # sagt dann, was mit der Datei nicht stimmt.
        return read_mesh(payload, suffix)
    return read_mesh(payload, suffix)


def read_bounded_payload(path: Path) -> bytes:
    """Liest eine lokale Datei innerhalb der gemeinsamen Importgrenze.

    Die Grenze steht vor dem Lesen. ``Path.read_bytes`` hob vorher auch eine
    20-GiB-Datei erst vollständig in den Speicher und erklärte danach, dass
    sie zu groß war. Der begrenzte Lesezug fängt zusätzlich eine Datei ab,
    die zwischen Größenabfrage und Lesen wächst.

    **Ein ``OSError`` ist eine Lage, kein Programmfehler** (RM-224): eine
    verschobene Datei, ein getrenntes Laufwerk, fehlende Rechte. Seit das
    Einlesen im Arbeiter liest, käme er dort als Absturzbericht an; hier wird
    er zum Hinweis mit Weg, mit den Sätzen, die der Lesearbeiter der
    Quellenwahl bis dahin selbst formulierte. Der Grund des Systems reist als
    Wert mit.
    """
    try:
        check_limits(path.stat().st_size, 0)
        with path.open("rb") as stream:
            payload = stream.read(MAX_FILE_BYTES + 1)
    except OSError as problem:
        raise unreadable_file(path, problem) from problem
    check_limits(len(payload), 0)
    return payload


def unreadable_file(path: Path, problem: OSError) -> UserError:
    """Der Hinweis für eine Datei, die das System nicht herausgibt.

    Ein Satz für jeden Leseweg — das Einlesen und die Quellenwahl im Dialog
    fragen beide hier, statt ihn je selbst zu formulieren.
    """
    return UserError(
        title=_("Diese Datei ließ sich nicht lesen."),
        detail=_(
            "Sie ist vielleicht verschoben worden, oder das Laufwerk ist "
            "gerade nicht erreichbar. Wählen Sie die Datei noch einmal aus."
        ),
        values={"path": path.name, "reason": problem.strerror or str(problem)},
        suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
    )


def read_local_payload(path: Path) -> bytes:
    """Liest eine lokale Modelldatei als eigenständige Projektquelle.

    GLTF darf Puffer und Bilder in Begleitdateien führen. Eine Projektquelle
    ist dagegen genau eine Datei und muss auch auf einem anderen Rechner noch
    rechnen (§16.1). Darum werden lokale Begleitdateien als Datenadressen in
    das JSON eingebettet; die Geometrie selbst wird dabei weder geladen noch
    verändert.

    Verweise außerhalb des Ordners werden nicht verfolgt. Sonst könnte eine
    fremde GLTF beim Einlesen beliebige Dateien des Rechners in das Projekt
    ziehen — ein ausgewähltes Modell ist keine Erlaubnis, die Platte zu lesen
    (§32).
    """
    payload = read_bounded_payload(path)
    if path.suffix.lower() != ".gltf":
        return payload
    folder = path.parent.resolve()
    packed = embed_gltf_dependencies(
        path.name, payload, lambda entry, uri: _gltf_reference(folder, entry, uri)
    )
    check_limits(len(packed), 0)
    return packed


GltfLocator = Callable[[dict[str, Any], str], "GltfReference"]
"""``(eintrag, uri) -> Referenz``: wo eine Begleitdatei liegt und wie sie gelesen
wird. Ein Ordner auf der Platte ist ein Ort dafür, ein ZIP-Archiv ein zweiter
(:mod:`app.core.ingest.archive`) — die Grenzen des Einbettens gelten für beide."""


def embed_gltf_dependencies(file_name: str, payload: bytes, locate: GltfLocator) -> bytes:
    """Macht die externen Puffer und Bilder einer GLTF selbstständig."""
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as problem:
        raise ValidationError(
            field="file",
            detail=_("Die GLTF-Datei enthält kein lesbares JSON."),
            constraint="unreadable",
            values={"file": file_name},
        ) from problem
    if not isinstance(document, dict):
        raise ValidationError(
            field="file",
            detail=_("Die GLTF-Datei enthält kein gültiges Modelldokument."),
            constraint="unreadable",
            values={"file": file_name},
        )

    references: list[GltfReference] = []
    for section in ("buffers", "images"):
        entries = document.get(section, [])
        if not isinstance(entries, list):
            raise ValidationError(
                field="file",
                detail=_("Die GLTF-Datei enthält kein gültiges Modelldokument."),
                constraint="unreadable",
                values={"file": file_name, "section": section},
            )
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValidationError(
                    field="file",
                    detail=_("Die GLTF-Datei enthält kein gültiges Modelldokument."),
                    constraint="unreadable",
                    values={"file": file_name, "section": section},
                )
            uri = entry.get("uri")
            if not isinstance(uri, str) or not uri or uri.lower().startswith("data:"):
                continue
            references.append(locate(entry, uri))

    # Vor dem ersten Lesen und erst recht vor Base64 steht die Größe des
    # fertigen JSON fest. Base64 macht drei Bytes zu vier; zwei einzeln
    # erlaubte Begleitdateien können darum gemeinsam weit über der Grenze
    # liegen. Die Prüfung danach kam für den Speicherüberlauf zu spät.
    compact = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    projected_size = len(compact)
    for reference in references:
        previous_size = len(json.dumps(reference.uri, ensure_ascii=False).encode("utf-8"))
        projected_size += _embedded_uri_size(reference) + 2 - previous_size
    check_limits(projected_size, 0)

    cached: dict[str, str] = {}
    for reference in references:
        reference.entry["uri"] = _embedded_gltf_uri(reference, cached)
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class GltfReference:
    """Eine bereits geprüfte Referenz samt ihrer späteren Größe.

    ``key`` erkennt dieselbe Begleitdatei unter zwei Verweisen wieder, ``read``
    liest höchstens so viele Bytes, wie es bekommt — ein Ordner und ein
    Archiv lesen verschieden, begrenzt werden beide gleich.
    """

    entry: dict[str, Any]
    uri: str
    key: str
    media_type: str
    size: int
    read: Callable[[int], bytes]


def _gltf_reference(folder: Path, entry: dict[str, Any], uri: str) -> GltfReference:
    """Prüft Pfad und Größe, ohne den Inhalt der Begleitdatei zu lesen."""
    parts = urlsplit(uri)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise ValidationError(
            field="file",
            detail=_(
                "Die GLTF-Datei verweist nach außen. Speichern Sie Modell und Begleitdateien "
                "in demselben Ordner oder exportieren Sie als GLB."
            ),
            constraint="scheme",
            values={"dependency": uri},
        )

    dependency = (folder / Path(unquote(parts.path))).resolve()
    try:
        dependency.relative_to(folder)
    except ValueError as problem:
        raise ValidationError(
            field="file",
            detail=_(
                "Die GLTF-Datei verweist aus ihrem Ordner heraus. Legen Sie die Begleitdatei "
                "neben das Modell oder exportieren Sie als GLB."
            ),
            constraint="absolute_path",
            values={"dependency": uri},
        ) from problem
    if not dependency.is_file():
        raise ValidationError(
            field="file",
            detail=_(
                "Zur GLTF-Datei fehlt eine Begleitdatei. Legen Sie sie neben das Modell oder "
                "exportieren Sie als GLB."
            ),
            constraint="missing_file",
            values={"dependency": uri},
        )

    try:
        size = dependency.stat().st_size
    except OSError as problem:
        raise ValidationError(
            field="file",
            detail=_(
                "Die Begleitdatei der GLTF ließ sich nicht lesen. Prüfen Sie ihre Zugriffsrechte "
                "oder exportieren Sie als GLB."
            ),
            constraint="unreadable",
            values={"dependency": uri},
        ) from problem
    media_type = mimetypes.guess_type(dependency.name)[0] or "application/octet-stream"

    def read(limit: int) -> bytes:
        with dependency.open("rb") as stream:
            return stream.read(limit)

    return GltfReference(entry, uri, str(dependency), media_type, size, read)


def _embedded_uri_size(reference: GltfReference) -> int:
    """Länge der späteren Datenadresse, ohne sie schon anzulegen."""
    prefix = f"data:{reference.media_type};base64,"
    encoded = 4 * ((reference.size + 2) // 3)
    return len(prefix.encode("ascii")) + encoded


def _embedded_gltf_uri(reference: GltfReference, cached: dict[str, str]) -> str:
    """Liest genau eine vorgeprüfte Begleitdatei innerhalb des Modellordners."""
    if reference.key in cached:
        return cached[reference.key]

    try:
        # Hat ein anderes Programm die Datei nach der Vorprüfung ersetzt,
        # wird höchstens ein Byte über die angekündigte Größe hinaus
        # gelesen. Ein Größenrennen darf die frühe Grenze nicht umgehen —
        # und ein Archiveintrag, der mehr entpackt, als er ankündigt, auch
        # nicht.
        data = reference.read(reference.size + 1)
    except OSError as problem:
        raise ValidationError(
            field="file",
            detail=_(
                "Die Begleitdatei der GLTF ließ sich nicht lesen. Prüfen Sie ihre Zugriffsrechte "
                "oder exportieren Sie als GLB."
            ),
            constraint="unreadable",
            values={"dependency": reference.uri},
        ) from problem
    if len(data) > reference.size:
        raise ValidationError(
            field="file",
            detail=_(
                "Die Begleitdatei der GLTF ließ sich nicht lesen. Prüfen Sie ihre Zugriffsrechte "
                "oder exportieren Sie als GLB."
            ),
            constraint="unreadable",
            values={"dependency": reference.uri},
        )
    check_limits(len(data), 0)
    embedded = f"data:{reference.media_type};base64,{base64.b64encode(data).decode('ascii')}"
    cached[reference.key] = embedded
    return embedded


@dataclass(frozen=True, slots=True)
class UnitGuess:
    """Was die Heuristik gefunden hat. ``unit`` ist None, wenn sie sich nicht
    sicher ist (§17.1).
    """

    unit: LengthUnit | None
    candidates: tuple[LengthUnit, ...]
    diagonal: float

    @property
    def certain(self) -> bool:
        return self.unit is not None


def detect_unit(diagonal: float, largest_mm: float = PLAUSIBLE_MAX_MM) -> UnitGuess:
    """Rät die Einheit einer Datei aus der Größe ihres Hüllquaders.

    Genau eine plausible Lesart gewinnt. Mehrere plausible Lesarten heißen,
    dass die Frage an den Nutzer geht — das ist Leitprinzip 6, keine
    Höflichkeit. ``largest_mm`` ist die Obergrenze des Plausiblen; die
    Operation gibt sie aus dem Drucker (:func:`plausible_reach`).
    """
    if diagonal <= EPS_GEOM:
        return UnitGuess(unit=None, candidates=CANDIDATE_UNITS, diagonal=diagonal)
    plausible = tuple(
        unit
        for unit in CANDIDATE_UNITS
        if PLAUSIBLE_MIN_MM <= to_mm(diagonal, unit) <= PLAUSIBLE_MAX_MM
    )
    if not plausible and PLAUSIBLE_MIN_MM <= diagonal <= largest_mm:
        # **Nur die Millimeter-Lesart darf über die feste Grenze hinaus.** Die
        # 300 mm trennen Millimeter von Zentimetern: Ein 30-mm-Teil wäre als
        # 30 cm noch glaubwürdig, ein 40-mm-Teil nicht mehr. Hebt man die
        # Grenze für alle Lesarten, wird jedes Teil bis 80 mm wieder zur
        # Frage. Also bleibt sie stehen — und nur, wenn gar nichts plausibel
        # ist, darf ein großes Teil in Millimetern durch, solange es den
        # Drucker nicht um mehr als das Doppelte überragt.
        return UnitGuess(unit="mm", candidates=("mm",), diagonal=diagonal)
    if len(plausible) == 1:
        return UnitGuess(unit=plausible[0], candidates=plausible, diagonal=diagonal)
    if not plausible:
        return UnitGuess(unit=None, candidates=CANDIDATE_UNITS, diagonal=diagonal)
    # **Die gemessene Einheit steht immer zur Wahl.** Plausibel heißt hier
    # „zwischen zehn und dreihundert Millimetern", und darunter fiel „mm" aus
    # der Antwortliste: Eine M3-Unterlegscheibe misst über alles sieben
    # Millimeter, und wer sie korrekt in Millimetern gespeichert hatte, konnte
    # nur zwischen „cm" und „in" wählen — beide falsch — oder abbrechen.
    #
    # Als *einzige* Lesart bleibt sie unplausibel; genau deshalb wird
    # überhaupt gefragt. Als *Antwort* gehört sie dazu, und zwar zuerst: Eine
    # Frage, deren richtige Antwort fehlt, ist schlimmer als keine Frage
    # (§17.1, Leitprinzip 6).
    candidates = tuple(
        unit for unit in CANDIDATE_UNITS if unit in plausible or unit == MEASURED_UNIT
    )
    return UnitGuess(unit=None, candidates=candidates, diagonal=diagonal)


def check_limits(payload_size: int, triangle_count: int) -> None:
    """Lehnt übergroße Eingaben mit klarer Meldung ab, statt dass der Speicher
    ausgeht.
    """
    if payload_size > MAX_FILE_BYTES:
        raise ValidationError(
            field="file",
            detail=_("Die Datei ist größer, als diese Anwendung verarbeitet."),
            constraint="file_too_large",
            values={"size": payload_size, "limit": MAX_FILE_BYTES},
        )
    if triangle_count > MAX_TRIANGLES:
        raise ValidationError(
            field="file",
            detail=_("Das Modell hat mehr Dreiecke, als diese Anwendung verarbeitet."),
            constraint="too_many_triangles",
            values={"triangles": triangle_count, "limit": MAX_TRIANGLES},
        )


#: Der Kopf einer binären STL: 80 Byte Bezeichnung, dann die Dreieckszahl.
STL_HEADER_BYTES: Final = 84
#: Ein Dreieck darin: Normale, drei Ecken, ein Attributfeld.
STL_TRIANGLE_BYTES: Final = 50


def check_readable(payload: bytes, suffix: str) -> None:
    """Lehnt eine Datei ab, aus der kein Modell werden kann — **vor** der Op.

    Gemessen am 03.09.2026 gingen fünf unbrauchbare Dateien klaglos durch:
    null Bytes, ein abgebrochener Download, eine umbenannte Textdatei, die
    404-Seite eines Servers und eine STL mit null Dreiecken. Jede wurde zur
    Operation im Stapel und zur eingebetteten Quelle im Dokument, und jede
    wanderte beim nächsten Speichern in die Projektdatei. Gemeldet wurde es
    erst bei der Auswertung, als Befund über einem leeren Viewport.

    Geprüft wird nur, was **ohne einen Parser** entschieden werden kann: die
    leere Datei für jedes Format, die Struktur bei ``.stl``, die Archivkennung
    bei ``.3mf``. Wo diese Funktion schweigt, heißt das nicht „gültig" — es
    heißt „hier entscheidet der Leser".

    **Die Reihenfolge bei STL ist wichtig und nicht umkehrbar.** Erst die
    Längenrechnung, dann der ASCII-Weg. Ein Kopf, der mit ``solid`` beginnt,
    steht auch in manchen binären Dateien; umgekehrt trägt eine echte binäre
    STL beliebigen Text im Kopf. Aus einem Durchlauf über sechzehn
    Kundendateien (3d-druck-c7, 03.09.2026) stammt der Beleg: In
    ``broomholdervcd_d35mm.stl`` stehen dort die Bytes ``ST`` — die Datei ist
    binär, gültig, und eine Prüfung „fängt mit solid an, sonst raus" hätte sie
    abgewiesen.
    """
    if not payload:
        raise ValidationError(
            suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
            field="file",
            detail=_(
                "Die Datei ist leer. Meistens ist ein Download abgebrochen — "
                "laden Sie sie erneut herunter und öffnen Sie sie noch einmal."
            ),
            constraint="file_empty",
            values={"size": 0},
        )

    kind = suffix.lower()
    if kind == ".3mf":
        # Eine 3MF ist ein Zip-Archiv, und ein Zip beginnt mit „PK". Das ist
        # keine Formatprüfung, sondern die Frage, ob überhaupt ein Archiv
        # vorliegt: Was ein Server als Fehlerseite schickt, ist keines.
        if not payload.startswith(b"PK"):
            raise ValidationError(
                suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
                field="file",
                detail=_(
                    "Diese Datei ist kein 3MF-Archiv, auch wenn sie so heißt. "
                    "Prüfen Sie, ob der Download vollständig war, und laden Sie sie sonst "
                    "erneut herunter."
                ),
                constraint="not_an_archive",
                values={"size": len(payload)},
            )
        return

    if kind != ".stl":
        # OBJ, PLY, GLB, STEP: keine Kennung, die sich ohne Parser prüfen
        # ließe. Die leere Datei oben ist alles, was hier ehrlich zu haben ist
        # — insbesondere darf hier nichts fallen, sonst schnitte diese Prüfung
        # den STEP-Weg ab, der in ``import_plan`` gleich danach beginnt.
        return

    announced = -1
    if len(payload) >= STL_HEADER_BYTES:
        announced = int(struct.unpack("<I", payload[80:STL_HEADER_BYTES])[0])
    expected = STL_HEADER_BYTES + STL_TRIANGLE_BYTES * announced
    binary_fits = announced > 0 and len(payload) == expected

    if binary_fits:
        return

    # **Erst hier der ASCII-Weg, und dann ohne die Zahlen von oben.** Bei einer
    # Textdatei sind die Bytes 80 bis 84 irgendein Wort, und die daraus
    # gerechnete Dreieckszahl ist Zufall: Eine gültige ASCII-STL mit einem
    # Kommentarblock vor der ersten Facette wurde damit als „unvollständig"
    # abgewiesen. Wer hier ``solid`` liest, verlässt den binären Zweig ganz.
    if payload[:512].lstrip()[:5].lower() == b"solid":
        if b"facet" in payload.lower():
            return
        raise ValidationError(
            suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
            field="file",
            detail=_(
                "Die Datei enthält kein Modell: Sie ist gültig aufgebaut, führt "
                "aber null Dreiecke. Prüfen Sie im Ursprungsprogramm, ob beim "
                "Exportieren etwas ausgewählt war."
            ),
            constraint="no_triangles",
            values={"triangles": 0},
        )

    if announced == 0 and len(payload) == STL_HEADER_BYTES:
        raise ValidationError(
            suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
            field="file",
            detail=_(
                "Die Datei enthält kein Modell: Sie ist gültig aufgebaut, führt "
                "aber null Dreiecke. Prüfen Sie im Ursprungsprogramm, ob beim "
                "Exportieren etwas ausgewählt war."
            ),
            constraint="no_triangles",
            values={"triangles": 0},
        )

    if announced > 0 and len(payload) < expected:
        raise ValidationError(
            suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
            field="file",
            detail=_(
                "Die Datei ist unvollständig: Ihr Kopf nennt mehr Dreiecke, als "
                "enthalten sind. Meistens ist ein Download abgebrochen — laden Sie "
                "sie erneut herunter."
            ),
            constraint="file_truncated",
            values={"announced": announced, "size": len(payload), "expected": expected},
        )

    raise ValidationError(
        suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
        field="file",
        detail=_(
            "Diese Datei ist keine STL-Datei, auch wenn sie so heißt. Häufig "
            "steckt dahinter die Fehlerseite eines Servers, die beim "
            "Herunterladen anstelle des Modells kam."
        ),
        constraint="not_a_mesh",
        values={"size": len(payload)},
    )


def _zip64_directory(payload: bytes, end_offset: int) -> tuple[int, int, int] | None:
    """Liest Zähler, Größe und tatsächliches Ende eines ZIP64-Verzeichnisses."""
    locator_offset = end_offset - _ZIP64_LOCATOR.size
    if locator_offset < 0:
        return None
    locator = _ZIP64_LOCATOR.unpack_from(payload, locator_offset)
    if locator[0] != _ZIP64_LOCATOR_SIGNATURE or locator[1] != 0 or locator[3] > 1:
        return None

    relative_offset = locator[2]
    fixed_offset = locator_offset - _ZIP64_END_RECORD.size
    if fixed_offset < 0 or relative_offset > fixed_offset:
        return None
    record_offset = relative_offset
    if payload[record_offset : record_offset + 4] != _ZIP64_END_SIGNATURE:
        # Bei vorangestellten Daten ist der Locator-Offset relativ zum
        # eigentlichen Archiv. Der feste Ort direkt vor dem Locator bleibt
        # dagegen absolut und ist auch der Rückfall des Standardlesers.
        record_offset = fixed_offset
    if payload[record_offset : record_offset + 4] != _ZIP64_END_SIGNATURE:
        return None
    record = _ZIP64_END_RECORD.unpack_from(payload, record_offset)
    extra_bytes = fixed_offset - relative_offset if record_offset == relative_offset else 0
    if record[9] + record[8] != relative_offset:
        return None
    if record[1] + 12 != _ZIP64_END_RECORD.size + extra_bytes:
        return None
    return max(int(record[6]), int(record[7])), int(record[8]), record_offset


def _archive_entry_count(payload: bytes) -> int | None:
    """Zählt das Zentralverzeichnis ohne ``ZipInfo``-Objekte anzulegen.

    Die Anzahl im Endsatz ist fremd und kann kleiner als das Verzeichnis sein.
    Deshalb werden dessen feste Köpfe durchlaufen. Ein ungültiger Aufbau ergibt
    ``None``; der eigentliche ZIP-Leser liefert dafür anschließend seine genauere
    Fehlermeldung, ohne zuvor mehr als die bereits gezählten Einträge anzulegen.
    """
    search_start = max(0, len(payload) - _ZIP_END_RECORD.size - _MAX_ZIP_COMMENT_BYTES)
    end_offset = payload.rfind(_ZIP_END_SIGNATURE, search_start)
    if end_offset < search_start or end_offset + _ZIP_END_RECORD.size > len(payload):
        return None
    # Wie ``ZipFile`` gilt die letzte Signatur im erlaubten Kommentarbereich.
    # Dessen Längenfeld wird nicht geglaubt: Auch nachlaufende Bytes akzeptiert
    # der Leser, also dürfen sie diese Vorprüfung nicht umgehen.
    end_record = _ZIP_END_RECORD.unpack_from(payload, end_offset)

    announced = max(int(end_record[3]), int(end_record[4]))
    directory_bytes = int(end_record[5])
    directory_end = end_offset
    zip64 = _zip64_directory(payload, end_offset)
    if zip64 is not None:
        announced, directory_bytes, directory_end = zip64
    if announced > MAX_ARCHIVE_ENTRIES:
        return announced
    cursor = directory_end - directory_bytes
    if cursor < 0:
        return None

    counted = 0
    while cursor < directory_end:
        header_end = cursor + _ZIP_CENTRAL_HEADER_BYTES
        if header_end > directory_end or payload[cursor : cursor + 4] != _ZIP_CENTRAL_SIGNATURE:
            return None
        name_bytes, extra_bytes, comment_bytes = struct.unpack_from("<HHH", payload, cursor + 28)
        cursor = header_end + name_bytes + extra_bytes + comment_bytes
        if cursor > directory_end:
            return None
        counted += 1
        if counted > MAX_ARCHIVE_ENTRIES:
            return counted
    return max(announced, counted)


def _too_many_archive_entries(entries: int, *, model_archive: bool = False) -> ValidationError:
    """Baut die gemeinsame Absage für ein zu großes Zentralverzeichnis."""
    return ValidationError(
        suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
        field="file",
        detail=(
            _("Das ZIP-Archiv enthält mehr Einträge, als diese Anwendung verarbeitet.")
            if model_archive
            else _("Das 3MF-Archiv enthält mehr Einträge, als diese Anwendung verarbeitet.")
        ),
        constraint="file_too_large",
        values={"entries": entries, "limit": MAX_ARCHIVE_ENTRIES},
    )


def check_unpacked(payload: bytes, *, model_archive: bool = False) -> None:
    """Prüft Verzeichnis, Eindeutigkeit und Entpackgröße eines 3MF (§32).

    ``model_archive`` nennt in den Absagen ein ZIP-Archiv statt eines 3MF —
    dieselben Grenzen gelten für ein heruntergeladenes Archiv mit Modellen
    darin (:mod:`app.core.ingest.archive`), und ein Kunde, der ein ZIP
    abgelegt hat, soll nicht von einem 3MF lesen.

    Geprüft war nur die gepackte Größe: 2,6 MB wurden beim Lesen zu 1,08 GB —
    Verhältnis 412, und über ``ingest/fetch`` ist so eine Datei aus dem Netz
    erreichbar. Zunächst gelten alle Grenzen aus dem zentralen Verzeichnis,
    einschließlich mehrfacher Einträge. Erst danach werden gleich benannte
    Einträge blockweise verglichen: Bytegleiche Beilagen sind eindeutig,
    verschiedene Inhalte unter demselben Namen sind es nicht.
    """
    import zipfile
    import zlib
    from io import BytesIO

    announced_entries = _archive_entry_count(payload)
    if announced_entries is not None and announced_entries > MAX_ARCHIVE_ENTRIES:
        raise _too_many_archive_entries(announced_entries, model_archive=model_archive)

    try:
        with zipfile.ZipFile(BytesIO(payload)) as container:
            infos = container.infolist()
    except zipfile.BadZipFile:
        # Keine gültige Zip — das meldet der eigentliche Leser mit seinem
        # eigenen, besseren Satz.
        return

    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise _too_many_archive_entries(len(infos), model_archive=model_archive)

    seen: dict[str, zipfile.ZipInfo] = {}
    duplicates: list[tuple[zipfile.ZipInfo, zipfile.ZipInfo]] = []
    unpacked = 0
    compressed = 0
    for info in infos:
        if info.filename in seen:
            duplicates.append((seen[info.filename], info))
        else:
            seen[info.filename] = info
        unpacked += info.file_size
        compressed += info.compress_size
        if unpacked > MAX_FILE_BYTES:
            raise ValidationError(
                suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
                field="file",
                detail=_("Die Datei entpackt sich größer, als diese Anwendung verarbeitet."),
                constraint="file_too_large",
                values={"unpacked": unpacked, "limit": MAX_FILE_BYTES},
            )
        if info.file_size >= MIN_RATIO_ENTRY_BYTES and (
            info.file_size / max(info.compress_size, 1) > MAX_COMPRESSION_RATIO
        ):
            raise ValidationError(
                suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
                field="file",
                detail=_("Die Datei entpackt sich größer, als diese Anwendung verarbeitet."),
                constraint="file_too_large",
                values={"entry": info.filename, "limit": MAX_COMPRESSION_RATIO},
            )
    if unpacked >= MIN_RATIO_ENTRY_BYTES and (
        unpacked / max(compressed, 1) > MAX_COMPRESSION_RATIO
    ):
        raise ValidationError(
            suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
            field="file",
            detail=_("Die Datei entpackt sich größer, als diese Anwendung verarbeitet."),
            constraint="file_too_large",
            values={"unpacked": unpacked, "limit": MAX_COMPRESSION_RATIO},
        )

    if duplicates:
        with zipfile.ZipFile(BytesIO(payload)) as container:
            for first, second in duplicates:
                try:
                    identical = _matching_archive_entries(container, first, second)
                except (
                    OSError,
                    EOFError,
                    zipfile.BadZipFile,
                    zlib.error,
                    NotImplementedError,
                    RuntimeError,
                ):
                    # Eine unlesbare Dublette ist kein Beweis für Gleichheit.
                    identical = False
                if not identical:
                    raise ValidationError(
                        suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
                        field="file",
                        detail=(
                            _("Das ZIP-Archiv enthält denselben Eintrag mehrfach.")
                            if model_archive
                            else _("Das 3MF-Archiv enthält denselben Eintrag mehrfach.")
                        ),
                        constraint="invalid_archive",
                        values={"entry": second.filename},
                    )


def _matching_archive_entries(
    container: zipfile.ZipFile, first: zipfile.ZipInfo, second: zipfile.ZipInfo
) -> bool:
    """Vergleicht Inhalte ohne volle Entpackkopien oder Vertrauen in eine CRC.

    Die Gesamtgröße wurde vorher begrenzt. Der erste Inhalt wird höchstens
    einmal je Dublette gelesen; auch bei vielen Wiederholungen bleibt die
    gelesene Menge damit unter dem Doppelten dieser Gesamtgröße.
    """
    if first.file_size != second.file_size or first.CRC != second.CRC:
        return False
    with container.open(first) as left, container.open(second) as right:
        while True:
            a, b = left.read(_ARCHIVE_COMPARE_BYTES), right.read(_ARCHIVE_COMPARE_BYTES)
            if a != b:
                return False
            if not a:
                return True


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Das normalisierte Netz plus was mit ihm passiert ist."""

    mesh: MeshData
    info: IngestInfo
    findings: tuple[Finding, ...] = ()


def _silent(fraction: float, text: str) -> None:
    return None


def bed_offset(bounds: BoundingBox, *, place_on_bed: bool = False, centre: bool = False) -> Vec3:
    """Der Versatz, der einen Körper auf das Bett und in dessen Mitte legt
    (§17.1, Schritt 6).

    **Die Mitte des Bettes ist der Ursprung.** Der Kern rechnet um ihn herum:
    ``arrange_on_bed`` misst seine Ränder als ``±width/2``, und der Viewport
    zeichnet die Platte um denselben Punkt. Zentrieren heißt deshalb: den
    Mittelpunkt des Hüllquaders auf x = y = 0 schieben.

    Als eigene Funktion, weil zwei Stellen denselben Versatz brauchen — ein
    einzelner Körper und eine Baugruppe, die als Ganzes bewegt wird — und weil
    eine Verschiebung, die nur im Ablauf steht, sich nicht einzeln prüfen lässt.

    Der Hüllquader kommt von außen, weil eine Baugruppe ihren gemeinsamen
    braucht und nicht den eines einzelnen Körpers.
    """
    return (
        -bounds.centre[0] if centre else 0.0,
        -bounds.centre[1] if centre else 0.0,
        -bounds.minimum[2] if place_on_bed else 0.0,
    )


def moved_findings(findings: Sequence[Finding], offset: Sequence[float]) -> list[Finding]:
    """Die Befunde mit ihrem Ort um denselben Versatz wie ihr Körper verschoben.

    Eine Stelle für beide Wege aufs Bett (Review R7, 24.09.2026): den eines
    einzelnen Körpers in :func:`normalise` und den einer Baugruppe in
    ``ingest.ops._group_on_bed``. Dort fehlte das Nachführen, und der Klick
    auf die große Öffnung einer 3MF flog ins Leere.
    """
    return [
        dataclasses.replace(
            entry,
            location=(
                entry.location[0] + float(offset[0]),
                entry.location[1] + float(offset[1]),
                entry.location[2] + float(offset[2]),
            ),
        )
        if entry.location is not None
        else entry
        for entry in findings
    ]


def normalise(
    mesh: MeshData,
    unit: LengthUnit,
    *,
    weld: bool = True,
    weld_is_reading: bool = False,
    remove_degenerate: bool = True,
    unify_normals: bool = True,
    mend: bool = True,
    wide_holes: bool = True,
    place_on_bed: bool = False,
    centre: bool = False,
    progress: ProgressFn = _silent,
    cancelled: CancelToken | None = None,
) -> IngestResult:
    """Führt die sechs Schritte aus und meldet, was sie getan haben.

    ``mend`` schließt offene Stellen (Schritt 4b). Abschalten lässt es sich für
    Prüfungen, die ein offenes Netz **brauchen** — die Fehlerkarte, der Schnitt
    ohne Deckel, die Warnung des Aushöhlens: Sie messen, was ein Defekt
    auslöst, und ein Import, der ihn vorher behebt, nimmt ihnen den Gegenstand.
    ``wide_holes=False`` lässt dabei nur die großen Öffnungen offen (*Offen
    lassen*, RM-241).

    ``weld_is_reading`` sagt, dass das Verschweißen zum **Lesen** des Formats
    gehört und kein Befund ist: Eine STL speichert jedes Dreieck mit eigenen
    Ecken, also wird bei jeder STL verschweißt — „Doppelte Punkte wurden
    verschweißt." stand damit als erste Zeile jedes sauberen Imports im
    Prüfbericht, ohne Handlung und ohne Folge (sechs von sechs Modellen,
    Bedienweg-Durchsicht 14.09.2026). Verschweißt wird weiter, und
    ``info.welded`` sagt es; bei einem Format mit Punktliste (OBJ, PLY, 3MF)
    bleibt der Befund, denn dort sind doppelte Punkte eine Eigenschaft der
    Datei.

    ``cancelled`` reicht der Ladeschritt herein (§15.6): Das Schließen in
    Schritt 4b fährt die ganze Füllkette der Reparatur, und an einem Netz mit
    vielen Löchern ist das der längste Weg des Imports (Review R10,
    24.09.2026).
    """
    findings: list[Finding] = []
    body: trimesh.Trimesh = mesh.raw.copy()
    # Die Filamentzuweisung je Dreieck reist mit — entlang derselben Masken,
    # mit denen Dreiecke fallen. ``replacing`` konnte das nicht: Sobald die
    # Dreieckszahl abwich, ließ es die Slots fallen, und ein rot-blauer Würfel
    # mit einem doppelten Dreieck kam einfarbig an (Gesamtreview 05.09.2026,
    # B-05). Dasselbe Nachziehen wie in der Reparatur (§20).
    slots = (
        np.asarray(mesh.slots, dtype=int)
        if mesh.slots and len(mesh.slots) == len(body.faces)
        else None
    )
    scale = to_mm(1.0, unit)

    # 1 — Einheit. Die einzige Stelle außer der Anzeige, an der umgerechnet
    # wird (§11.1).
    progress(0.0, str(_("Einheit anwenden")))
    if abs(scale - 1.0) > EPS_GEOM:
        body.apply_scale(scale)
        findings.append(
            Finding(
                code="ingest.scaled",
                severity="info",
                message=_("Die Datei wurde in Millimeter umgerechnet."),
                values={"unit": unit, "scale": scale},
            )
        )

    # Die Diagonale direkt aus den Ecken: ``body.extents`` läuft über
    # ``bounds`` und die über die referenzierten Ecken — am 1,3-M-Netz 135 ms
    # für ein Minimum und ein Maximum (Review, 21.09.2026).
    vertices = np.asarray(body.vertices, dtype=np.float64)
    diagonal = (
        float(np.linalg.norm(vertices.max(axis=0) - vertices.min(axis=0)))
        if len(body.faces)
        else 0.0
    )

    # 2 — Eckpunkte verschweißen, mit einer Toleranz, die der Modellgröße folgt.
    welded = False
    # Ob das Netz vor einem Schritt dicht war, wird je Netz einmal gefragt
    # und danach weitergereicht: ``is_watertight`` kostet am 1,3-M-Netz
    # 330 ms, und ein Verschweißen, das nichts zusammenlegt, ändert die
    # Antwort nicht. Eine Dreieckssuppe — jede Ecke genau einmal gebraucht,
    # wie jede STL sie speichert — ist nie dicht, ohne dass jemand zählt.
    closed: bool | None = None
    if len(body.faces) and len(body.vertices) == 3 * len(body.faces):
        closed = False
    if weld and len(body.faces):
        from app.core.geom.repair import used_vertex_count

        progress(0.2, str(_("Doppelte Punkte zusammenführen")))
        digits = weld_digits(weld_tolerance(diagonal))
        # **Dieselbe Funktion wie die Reparatur** (RM-239): Sie legt nur
        # zusammen, was an offenen Rändern liegt, trennt jede Punktgruppe nach
        # dem Flächenblatt, zu dem ihre Kopien gehören, und nimmt nichts, was
        # das Netz schlechter macht. Ein dichter Eingang hat keinen offenen
        # Rand; ihn reißt das Verschweißen nicht mehr auf, und die Kopie für
        # den Rückweg, die hier jedes Mal entstand, ist entfallen. Gemessen an
        # einer 3MF, die diese Anwendung selbst geschrieben hatte: 17186 Ecken,
        # wasserdicht; trimeshs Verschweißen bei 0,28 µm ließ 17184 übrig, und
        # der Prüfbericht sagte „Das Modell ist nicht geschlossen" über eine
        # Datei, die es war.
        merged = weld_points(body, digits)
        welded = merged > 0
        if welded:
            closed = is_closed(body)
        elif remove_degenerate and closed is not False:
            # Die Antwort gilt auch für Schritt 3: Gefragt wird einmal.
            closed = is_closed(body)
            single = _without_doubled_shell(body, digits) if closed else None
            if single is not None:
                # **Dieselbe Schale zweimal, jede mit eigenen Ecken** (Durchsicht
                # 0.5.0, gefunden vom Paket „netzkern"): Jede Schale ist für sich
                # dicht, und keine Ecke liegt an einem offenen Rand — das
                # Verschweißen lässt sie beide stehen. Die Kugel kam sonst als zwei
                # Teile mit doppeltem Volumen an, gegenläufig geschrieben mit dem
                # Volumen null.
                body, kept_faces = single
                if slots is not None:
                    slots = slots[kept_faces]
                closed = True
                findings.append(
                    Finding(
                        code="ingest.doubled_shell_removed",
                        severity="info",
                        message=_(
                            "Die Datei trug den Körper zweimal deckungsgleich. Die Kopie wurde "
                            "entfernt."
                        ),
                        values={"removed": int((~kept_faces).sum())},
                    )
                )
        if not welded and used_vertex_count(body) < len(body.vertices):
            # Unbenutzte Ecken räumte das Verschweißen bisher immer mit weg;
            # was danach kommt, rechnet mit einem Netz ohne sie.
            body.remove_unreferenced_vertices()
        if welded and not weld_is_reading:
            findings.append(
                Finding(
                    code="ingest.welded",
                    severity="info",
                    message=_("Doppelte Punkte wurden zusammengeführt."),
                    values={"removed": merged},
                )
            )

    # 3 — entartete Dreiecke: null Fläche, Nadeln, Duplikate.
    removed = 0
    if remove_degenerate and len(body.faces):
        progress(0.4, str(_("Leere Dreiecke entfernen")))
        before = len(body.faces)
        was_closed = is_closed(body) if closed is None else closed
        closed = was_closed
        intact = body.copy() if was_closed else None
        intact_slots = slots
        keep = body.nondegenerate_faces(height=EPS_GEOM)
        body.update_faces(keep)
        if slots is not None:
            slots = slots[np.asarray(keep, dtype=bool)]
        unique = body.unique_faces()
        body.update_faces(unique)
        if slots is not None:
            slots = slots[np.asarray(unique, dtype=bool)]
        body.remove_unreferenced_vertices()
        removed = before - len(body.faces)
        if removed:
            closed = None
        # **Dasselbe Zurücknehmen wie beim Verschweißen, aus demselben Grund.**
        #
        # In einem geschlossenen Netz ist jedes Dreieck an zwei Kanten der
        # einzige Nachbar. Wer eines entfernt, reißt genau dort ein Loch — auch
        # dann, wenn es keine Fläche hat. Gemessen an einer TripoSG-Ausgabe:
        # 221 138 Dreiecke, geschlossen; zwölf entartete entfernt, und danach
        # standen zwanzig Kanten allein da. Der Prüfbericht meldete „Das Modell
        # ist nicht geschlossen" über eine Datei, die es war, die Reparatur
        # schloss vierzehn der zwanzig und meldete Erfolg, und ihr Vorschlag
        # „Kanten verfeinern" endete in „Erst reparieren, dann noch einmal".
        # Vier Meldungen aus einer Ursache.
        #
        # Ein Duplikat ist der Fall, für den die Prüfung offen bleibt: Es
        # kommt in einem geschlossenen Netz nicht vor — es gibt der Kante
        # einen dritten Nachbarn —, und ``was_closed`` ist dann von vornherein
        # falsch.
        if removed and intact is not None and not body.is_watertight:
            kept = removed
            body = intact
            slots = intact_slots
            removed = 0
            closed = True
            # **Was stehen bleibt, ist keine Zeile im Bericht** (Bedienweg A4,
            # 25.09.2026): Geschehen ist nichts, und der Kunde kann nichts tun —
            # am Korpus ``F:\3D Dateien`` stand der Satz an 41 beziehungsweise 23
            # von 485 Körpern. Das Protokoll behält ihn für den Support.
            _log.info("degenerate kept on import: removing %d would tear the mesh", kept)
        elif removed:
            findings.append(
                Finding(
                    code="ingest.degenerate_removed",
                    # **Hinweis, nicht Warnung — die Sache ist erledigt.** Eine
                    # Warnung fragt nach einer Handlung, und hier gibt es
                    # keine: Die entarteten Dreiecke sind weg, drei Zeilen
                    # weiter oben. Ihre zwei Geschwister sagen dasselbe seit je
                    # als Hinweis — ``ingest.welded`` zwanzig Zeilen darüber
                    # und ``repair.degenerate_removed`` mit **demselben Satz**
                    # (``geom/repair.py:349``). Gemessen am Korpus stand die
                    # Warnung bei fünf von zwanzig Modellen und ließ den
                    # Prüfbericht bei jedem zweiten Import gelb aufgehen, ohne
                    # dass jemand etwas tun konnte.
                    severity="info",
                    message=_("Leere Dreiecke wurden entfernt."),
                    values={"removed": removed},
                )
            )

    # 4 — Normalen und Orientierung. Ob etwas korrigiert wurde, sagen die
    # Dreiecke selbst — ein Vergleich vorher/nachher —, nicht zwei Volumina:
    # ``body.volume`` rechnet den ganzen Trägheitstensor, 490 ms am 1,3-M-Netz,
    # für eine Frage nach dem Vorzeichen.
    if closed is None and len(body.faces):
        closed = is_closed(body)
    # **Außen ist je Schale, nicht je Körper** — dieselbe Regel wie die
    # Reparatur (:func:`app.core.geom.repair.turn_shells_outward`), nicht mehr
    # ``trimesh.repair.fix_inversion``, das nur das Gesamtvolumen fragt. Zwei
    # Stellen für dieselbe Frage hatten zwei Antworten: Die Reparatur richtete
    # einen umgestülpten Würfel neben einem richtigen, der Import nicht.
    from app.core.geom.repair import turn_shells_outward, wind_consistently

    flipped = False
    if unify_normals and len(body.faces):
        progress(0.6, str(_("Außenseiten angleichen")))
        faces_before = np.array(body.faces, copy=True)
        wind_consistently(body)
        if closed:
            turn_shells_outward(body)
        flipped = not np.array_equal(np.asarray(body.faces), faces_before)
        if flipped:
            findings.append(
                Finding(
                    code="ingest.normals_flipped",
                    severity="info",
                    message=_("Die Außenseiten wurden angeglichen."),
                )
            )

    # 4b — **Offene Stellen schließen, statt nur davon zu berichten**
    # (Entscheidung Robert, 22.09.2026: „am besten beim Import", „alles bei der
    # Reparatur beheben"). Bis dahin stand im Prüfbericht „Das Modell ist nicht
    # geschlossen. Reparieren schließt die offenen Stellen." — ein Hinweis auf
    # einen Knopf, den der Kunde erst finden musste, und ein Modell, das bis
    # dahin nicht druckbar war.
    #
    # Gelaufen wird der Weg der Operation (:func:`app.core.geom.repair.repair`)
    # mit denselben Schritten, die hier ohnehin anstehen — verzweigte Kanten
    # auflösen, Ränder vernähen, Ringe schließen —, und nur, wenn es etwas zu
    # tun gibt: Ein geschlossener Körper geht ohne eine einzige Messung durch.
    # Die Befunde der Reparatur reisen in denselben Bericht; was sie schließt,
    # steht dort mit Zahl, und eine große Öffnung mit einer Warnung.
    #
    # **Nur an einem verschweißten Netz.** Eine Dreieckssuppe — jede Ecke genau
    # einmal gebraucht, wie jede STL sie speichert — hat keine offenen Ränder,
    # sondern nur offene Ränder: Jede ihrer Kanten gehört zu einem Dreieck.
    # Dort etwas zu schließen hieße, das Netz zu erfinden, und wer ``weld=False``
    # sagt, will genau das nicht.
    mended_here = False
    if mend and weld and len(body.faces) and (closed is False or not body.is_watertight):
        from app.core.geom.repair import repair as repair_mesh

        progress(0.7, str(_("Offene Stellen schließen")))
        mended = repair_mesh(
            MeshData(raw=body, slots=tuple(int(slot) for slot in slots))
            if slots is not None and len(slots) == len(body.faces)
            else mesh.replacing(body),
            # Was hier schon gelaufen ist, läuft nicht zweimal — die
            # Außenseiten aber doch: **Erst am geschlossenen Netz lässt sich
            # fragen, wo außen ist** (Durchsicht 24.09.2026). Schritt 4 sah das
            # Netz offen und konnte es nur einheitlich machen; stand es
            # einheitlich verkehrt, kam der Körper geschlossen und umgestülpt
            # an — Volumen minus 8 000 an einem Würfel, und der Bericht sagte
            # „korrigiert". Wer *Außenseiten angleichen* am Ladeschritt
            # abschaltet, bekommt es auch hier nicht (Review R8).
            weld=False,
            degenerate=False,
            normals=unify_normals,
            wide_holes=wide_holes,
            cancelled=cancelled,
        )
        mended_here = True
        if flipped:
            # Eine Zeile für die Außenseiten, auch wenn beide Stufen richten.
            mended.findings = [
                entry for entry in mended.findings if entry.code != "repair.normals_flipped"
            ]
        if mended.changed:
            body = mended.mesh.raw
            slots = (
                np.asarray(mended.mesh.slots, dtype=int)
                if mended.mesh.slots and len(mended.mesh.slots) == len(body.faces)
                else None
            )
            # **Und die Antwort auf „ist es dicht" gilt neu.** Sie steht weiter
            # unten im Cache des Netzes, das der Hauptthread abliest; ein
            # ``None`` an dieser Stelle wurde dort zu ``False``, und ein
            # geschlossener Körper meldete sich als offen.
            closed = is_closed(body)
        findings.extend(mended.findings)

    # 5 — Komponenten. Kleine werden gemeldet, nie still verworfen.
    progress(0.8, str(_("Komponenten zählen")))
    components = _count_components(
        body, findings, closed=bool(closed) and unify_normals, cancelled=cancelled
    )
    # Ein Teil im Teil sagt der Bericht, statt es zu raten — dieselbe Frage
    # und derselbe Befund wie beim Reparieren, das in Schritt 4b schon selbst
    # gefragt hat (:func:`app.core.geom.repair.parts_inside_parts`).
    if unify_normals and closed and not mended_here and components > 1:
        from app.core.geom.repair import part_inside_finding, parts_inside_parts

        places = parts_inside_parts(body)
        if places:
            findings.append(part_inside_finding(places, components))
    # trimesh berechnet Dichtheit und Umlaufsinn gemeinsam. Die reine
    # Verschiebung verwirft beide Cachewerte; zurückgelegt werden sie als Paar.
    winding = bool(body.is_winding_consistent) if len(body.faces) else False

    # 6 — Lage. Aufsetzen und Zentrieren werden angeboten, nicht erzwungen.
    if (place_on_bed or centre) and len(body.faces):
        progress(0.9, str(_("Auf das Bett setzen")))
        low, high = body.bounds
        box = BoundingBox(
            (float(low[0]), float(low[1]), float(low[2])),
            (float(high[0]), float(high[1]), float(high[2])),
        )
        offset = bed_offset(box, place_on_bed=place_on_bed, centre=centre)
        body.apply_translation(offset)
        # Ein Befund mit Ort — die große Öffnung der Reparatur — zeigt auf die
        # Stelle am Körper, und der steht jetzt woanders.
        findings = moved_findings(findings, offset)

    too_fine = _too_fine(len(body.faces))
    if too_fine is not None:
        findings.append(too_fine)

    if len(body.faces):
        # Die Kennzahlen, die das Fenster gleich liest — Volumen, Fläche,
        # Dichtheit, Teilezahl — sind hier im Arbeiter gerechnet und liegen im
        # Cache des Netzes; der Hauptthread liest sie nur noch ab.
        cache = getattr(body, "_cache", None)
        if cache is not None:
            cache.verify()
            cache["is_watertight"] = bool(closed)
            cache["is_winding_consistent"] = winding
            cache["solidon_component_count"] = components
        # Das Volumen über ``MeshData`` — dasselbe Integral wie trimesh, ohne
        # dessen Trägheitsmomente, und unter dem Schlüssel, den ``volume``
        # später liest (RM-208).
        for figure in ("volume", "area"):
            getattr(MeshData.of(body), figure)
    if not closed and len(body.faces) and not mended_here:
        # Der Satz steht nur noch, wo die Reparatur oben nicht lief — etwa mit
        # „Offene Stellen schließen" aus. Lief sie und blieb etwas offen, sagt
        # sie es selbst, mit der Zahl der Stellen (``repair.still_open``,
        # ``repair.no_thickness``); zwei Zeilen über dieselben Ränder waren
        # eine zu viel, und „Reparieren" hätte dieselben Mittel noch einmal
        # versucht (Durchsicht 24.09.2026).
        findings.append(
            Finding(
                code="ingest.not_watertight",
                severity="warning",
                # **Was jetzt hilft, steht im Knopf** (§2.7, Regel 17): Seit das
                # Einlesen selbst schließt, kommt der Satz nur noch, wo jemand
                # „Offene Stellen schließen" abgeschaltet hat oder nicht
                # verschweißt wird — dann schließt *Reparieren* wirklich etwas.
                # Der Rat im Satz nannte einen anderen Namen als der Knopf
                # daneben (Bedienweg D4, 24.09.2026).
                message=_("Das Modell ist nicht geschlossen."),
                values={"open_edges": open_edge_count(MeshData.of(body))},
            )
        )

    progress(1.0, "")
    _log.info(
        "ingested mesh: %d triangles, unit %s, %d components", len(body.faces), unit, components
    )
    return IngestResult(
        mesh=MeshData(raw=body, slots=tuple(int(slot) for slot in slots))
        if slots is not None and len(slots) == len(body.faces)
        else mesh.replacing(body),
        info=IngestInfo(
            unit=unit,
            scale=scale,
            welded=welded,
            removed_triangles=removed,
            components=components,
        ),
        findings=tuple(findings),
    )


def _too_fine(triangles: int) -> Finding | None:
    """Sagt, welche Stufe der Analyse bei dieser Dreieckszahl ablehnt (§31).

    Nicht abgelehnt wird deswegen nichts — die Importgrenze liegt eine
    Größenordnung höher (§17.1). Ausgesprochen wird es trotzdem, mit dem
    Ausweg dazu: Ein Modell dieser Größe macht jeden späteren Schritt langsam,
    und ein Teil der Analyse antwortet gar nicht mehr.

    **Der Satz spricht über die Karten, die Erkennung meldet sich selbst.**
    Der eine Satz für beide log zwischen 120 000 und 200 000: Dort lehnten
    die Karten ab, die Merkmalserkennung lief weiter. Seit die Vollerkennung
    großer Importe nach einer Frage läuft (§21.1), weiß der Loader nicht
    einmal mehr, ob sie ablehnt — ein Satz über sie wäre nach einem Ja wie
    nach einem Nein falsch, und am selben Körper stand ``perceive.too_large``
    mit denselben Knöpfen darunter. Was die Erkennung auslässt, sagt deshalb
    allein dieser Befund der Auswertung, am Körper und mit seinen Wegen.

    Genannt wird die **Operation**, nicht der Menüweg: Hier stand „Netz →
    Dezimieren", und beides war falsch — das Menü heißt *Ändern*, die
    Operation *Dreiecke verringern*. Ein Weg im Text driftet, sobald jemand
    eine Kategorie verschiebt; ein Operationstitel ist derselbe String, den
    Menü, Palette und Kontextmenü zeigen, und die Palette findet ihn.
    """
    if triangles <= HEAVY_TRIANGLES:
        return None
    return Finding(
        code="ingest.very_large",
        severity="warning",
        message=_(
            "Für die Analysekarten ist dieses Modell zu fein vernetzt. „Dreiecke verringern“ hilft."
        ),
        values={"triangles": triangles, "comfortable": HEAVY_TRIANGLES},
    )


def _without_doubled_shell(
    body: trimesh.Trimesh, digits: int
) -> tuple[trimesh.Trimesh, np.ndarray] | None:
    """Das dichte Netz ohne eine deckungsgleiche Kopie seiner Schale — wenn es eine trägt.

    Gefragt wird nur, wo es mehr als ein Teil gibt. Eine Kopie des Netzes wird
    über alles verschweißt, wie trimesh es tut, und von jeder Gruppe
    deckungsgleicher Dreiecke (dieselben Ecken, gleich in welchem Umlauf)
    bleibt das erste. Ist das Netz danach dicht, war die Doppelung eine Kopie
    derselben Schale. Berühren sich dagegen zwei Körper an einer Fläche, bleibt
    dort eine Kante mit drei Flächen zurück, und die Antwort ist ``None``: Dann
    bleibt der Eingang, wie er ist. Zurück kommt das Netz und die Maske der
    behaltenen Dreiecke — die Filamentzuweisung je Dreieck folgt ihr.
    """
    if not len(body.faces) or _index_parts(body) < 2:
        return None
    joined = body.copy()
    joined.merge_vertices(digits_vertex=digits)
    faces = np.asarray(joined.faces)
    _groups, first = np.unique(np.sort(faces, axis=1), axis=0, return_index=True)
    if len(first) == len(faces):
        return None
    keep = np.zeros(len(faces), dtype=bool)
    keep[first] = True
    single = joined
    single.update_faces(keep)
    single.remove_unreferenced_vertices()
    if not single.is_watertight:
        return None
    return single, keep


def _index_parts(body: trimesh.Trimesh) -> int:
    """Wie viele Teile das Netz nach seinen Eckennummern hat.

    Nicht :func:`~app.core.geom.mesh.face_components`: Das verbindet auch, was
    nur am selben Ort liegt, und zwei deckungsgleiche Schalen sind dort ein
    Teil. Gelesen wird die Kantenzählung, die das Verschweißen schon angelegt hat.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    count = len(body.faces)
    pairs = edge_table(body).face_pairs()
    graph = coo_matrix(
        (np.ones(len(pairs), dtype=np.int8), (pairs[:, 0], pairs[:, 1])), shape=(count, count)
    )
    parts, _labels = connected_components(graph, directed=False)
    return int(parts)


def _count_components(
    body: trimesh.Trimesh,
    findings: list[Finding],
    *,
    closed: bool = False,
    cancelled: CancelToken | None = None,
) -> int:
    """Die Teile zählen und sagen, was aus ihrer Zahl folgt.

    **Stecken die Teile ineinander, sagt der Satz es** (Befund A5 der
    Bedienweg-Durchsicht, 24.09.2026): Dann ist *Überschneidungen auflösen*
    der erste Knopf und *In Einzelteile zerlegen* der zweite — zerlegt wären es
    zwei Teile am selben Ort. Gefragt wird nur am geschlossenen, einheitlich
    ausgerichteten Netz (``closed``), denn nur dort trägt das Auflösen
    (:func:`~app.core.geom.repair.parts_can_be_merged`).
    """
    pieces = face_components(body)
    if len(pieces) <= 1:
        return len(pieces)
    small = small_components(body)
    crossing = parts_that_cross(body, pieces, cancelled) if closed else None
    if crossing is not None:
        findings.append(
            Finding(
                code="ingest.multiple_components",
                severity="info",
                # Gefunden ist ein Paar, nicht alle: Bei 69 Teilen des
                # Bohrhalters stecken nicht alle 69 ineinander.
                message=_("Das Modell besteht aus zwei Teilen, die ineinanderstecken.")
                if len(pieces) == 2
                else _(
                    "Das Modell besteht aus {components} Teilen, von denen manche "
                    "ineinanderstecken.",
                    components=len(pieces),
                ),
                values={"components": len(pieces)},
                location=crossing,
                suggestions=(RESOLVE_INTERSECTIONS, SPLIT_BODIES)
                if parts_can_be_merged(MeshData.of(body))
                else (SPLIT_BODIES,),
            )
        )
    else:
        findings.append(
            Finding(
                code="ingest.multiple_components",
                severity="info",
                message=_("Das Modell besteht aus mehreren Teilen."),
                values={"components": len(pieces)},
            )
        )
    if small:
        findings.append(
            Finding(
                code="ingest.small_components",
                severity="warning",
                message=_("Es gibt sehr kleine Einzelteile. Gelöscht wurde nichts."),
                values={"count": len(small)},
            )
        )
    return len(pieces)
