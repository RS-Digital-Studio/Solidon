"""Die Eingangsstufe (Bauplan §17.1).

Jede geladene Datei geht dieselben sechs Schritte, in dieser Reihenfolge:

1. Einheit bestimmen — STL trägt keine, also entscheidet eine Heuristik und
   **fragt, wenn sie sich nicht sicher ist**, statt anzunehmen;
2. Eckpunkte verschweißen, mit einer Toleranz, die mit der Modellgröße
   skaliert;
3. entartete Dreiecke entfernen (Nullfläche, Nadeln, Duplikate);
4. Normalen vereinheitlichen und die Ausrichtung prüfen;
5. Komponenten zählen und Kleinstteile **melden** statt still zu löschen;
6. den Schwerpunkt finden und das Aufsetzen aufs Bett **anbieten**.

Alles, was die Stufe getan hat, landet in ``IngestInfo`` und in Befunden — der
Prüfbericht (§17.3) und der Steckbrief können also sagen, was auf dem Weg
hinein geändert wurde.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.parse import unquote, urlsplit

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData, face_components
from app.core.geom.repair import SMALL_COMPONENT_SHARE
from app.core.log import get_logger
from app.core.perceive.maps import MAP_LIMIT_TRIANGLES
from app.core.scene.evaluate import FEATURE_LIMIT_TRIANGLES
from app.core.types import Finding, IngestInfo, ProgressFn
from app.core.units import EPS_GEOM, LengthUnit, format_length, to_mm, weld_tolerance
from app.i18n import _

_log = get_logger(__name__)

#: Importgrenzen (§32). Eine klare Meldung schlägt einen Speicherüberlauf.
MAX_TRIANGLES: Final = 20_000_000
MAX_FILE_BYTES: Final = 512 * 1024 * 1024

#: Darüber sagt die Eingangsstufe etwas. Keine Grenze — die darüber liegt eine
#: Größenordnung höher —, sondern die Größe, ab der die Analyse aufhört helfen
#: zu können. Ein Community-Modell mit zwei Millionen Dreiecken ist etwas, das
#: einem normalerweise gereicht wird, und es sollte sagen, was es ist, statt
#: nur langsam zu sein.
#:
#: **Keine eigene Zahl.** Hier stand 500 000, und damit gab es drei Schwellen
#: für dieselbe Frage: Die Karten verweigern ab 120 000, die Merkmalserkennung
#: ab 200 000 (§31) — die Meldung versprach also, was längst geschehen war,
#: und zwischen 200 000 und 500 000 schwieg sie ganz. Sie ist jetzt die
#: kleinere der beiden echten Grenzen, und wer eine davon verschiebt,
#: verschiebt diese mit.
HEAVY_TRIANGLES: Final = min(MAP_LIMIT_TRIANGLES, FEATURE_LIMIT_TRIANGLES)

#: Was ein druckbares Teil üblicherweise misst, in Millimetern.
PLAUSIBLE_MIN_MM: Final = 10.0
PLAUSIBLE_MAX_MM: Final = 300.0

#: Einheiten, in denen eine Datei geschrieben sein könnte — die
#: wahrscheinlichste zuerst.
CANDIDATE_UNITS: Final[tuple[LengthUnit, ...]] = ("mm", "cm", "in", "m")

#: Die Datei so zu nehmen, wie sie dasteht. Der Kern rechnet in Millimetern
#: (§11.1), eine Zahl ohne Umrechnung ist also eine Zahl in Millimetern — und
#: das ist keine Vermutung über die Datei, sondern die einzige Lesart, die
#: nichts hinzudichtet.
MEASURED_UNIT: Final[LengthUnit] = "mm"


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
    # Die Grenze steht vor dem Lesen. ``Path.read_bytes`` hob vorher auch eine
    # 20-GiB-Datei erst vollständig in den Speicher und erklärte danach, dass
    # sie zu groß war. Der begrenzte Lesezug fängt zusätzlich eine Datei ab,
    # die zwischen Größenabfrage und Lesen wächst.
    check_limits(path.stat().st_size, 0)
    with path.open("rb") as stream:
        payload = stream.read(MAX_FILE_BYTES + 1)
    check_limits(len(payload), 0)
    if path.suffix.lower() != ".gltf":
        return payload
    packed = _embed_gltf_dependencies(path, payload)
    check_limits(len(packed), 0)
    return packed


def _embed_gltf_dependencies(path: Path, payload: bytes) -> bytes:
    """Macht die externen Puffer und Bilder einer GLTF selbstständig."""
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as problem:
        raise ValidationError(
            field="file",
            detail=_("Die GLTF-Datei enthält kein lesbares JSON."),
            constraint="unreadable",
            values={"file": path.name},
        ) from problem
    if not isinstance(document, dict):
        raise ValidationError(
            field="file",
            detail=_("Die GLTF-Datei enthält kein gültiges Modelldokument."),
            constraint="unreadable",
            values={"file": path.name},
        )

    folder = path.parent.resolve()
    references: list[_GltfReference] = []
    for section in ("buffers", "images"):
        entries = document.get(section, [])
        if not isinstance(entries, list):
            raise ValidationError(
                field="file",
                detail=_("Die GLTF-Datei enthält kein gültiges Modelldokument."),
                constraint="unreadable",
                values={"file": path.name, "section": section},
            )
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValidationError(
                    field="file",
                    detail=_("Die GLTF-Datei enthält kein gültiges Modelldokument."),
                    constraint="unreadable",
                    values={"file": path.name, "section": section},
                )
            uri = entry.get("uri")
            if not isinstance(uri, str) or not uri or uri.lower().startswith("data:"):
                continue
            references.append(_gltf_reference(folder, entry, uri))

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

    cached: dict[Path, str] = {}
    for reference in references:
        reference.entry["uri"] = _embedded_gltf_uri(reference, cached)
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class _GltfReference:
    """Eine bereits geprüfte lokale Referenz samt ihrer späteren Größe."""

    entry: dict[str, Any]
    uri: str
    dependency: Path
    media_type: str
    size: int


def _gltf_reference(folder: Path, entry: dict[str, Any], uri: str) -> _GltfReference:
    """Prüft Pfad und Größe, ohne den Inhalt der Begleitdatei zu lesen."""
    parts = urlsplit(uri)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise ValidationError(
            field="file",
            detail=_(
                "Die GLTF-Datei verweist nach außen. Speichere Modell und Begleitdateien "
                "in demselben Ordner oder exportiere als GLB."
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
                "Die GLTF-Datei verweist aus ihrem Ordner heraus. Lege die Begleitdatei "
                "neben das Modell oder exportiere als GLB."
            ),
            constraint="absolute_path",
            values={"dependency": uri},
        ) from problem
    if not dependency.is_file():
        raise ValidationError(
            field="file",
            detail=_(
                "Zur GLTF-Datei fehlt eine Begleitdatei. Lege sie neben das Modell oder "
                "exportiere als GLB."
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
                "Die Begleitdatei der GLTF ließ sich nicht lesen. Prüfe ihre Zugriffsrechte "
                "oder exportiere als GLB."
            ),
            constraint="unreadable",
            values={"dependency": uri},
        ) from problem
    media_type = mimetypes.guess_type(dependency.name)[0] or "application/octet-stream"
    return _GltfReference(entry, uri, dependency, media_type, size)


def _embedded_uri_size(reference: _GltfReference) -> int:
    """Länge der späteren Datenadresse, ohne sie schon anzulegen."""
    prefix = f"data:{reference.media_type};base64,"
    encoded = 4 * ((reference.size + 2) // 3)
    return len(prefix.encode("ascii")) + encoded


def _embedded_gltf_uri(reference: _GltfReference, cached: dict[Path, str]) -> str:
    """Liest genau eine vorgeprüfte Begleitdatei innerhalb des Modellordners."""
    if reference.dependency in cached:
        return cached[reference.dependency]

    try:
        with reference.dependency.open("rb") as stream:
            # Hat ein anderes Programm die Datei nach der Vorprüfung ersetzt,
            # wird höchstens ein Byte über die angekündigte Größe hinaus
            # gelesen. Ein Größenrennen darf die frühe Grenze nicht umgehen.
            data = stream.read(reference.size + 1)
    except OSError as problem:
        raise ValidationError(
            field="file",
            detail=_(
                "Die Begleitdatei der GLTF ließ sich nicht lesen. Prüfe ihre Zugriffsrechte "
                "oder exportiere als GLB."
            ),
            constraint="unreadable",
            values={"dependency": reference.uri},
        ) from problem
    if len(data) > reference.size:
        raise ValidationError(
            field="file",
            detail=_(
                "Die Begleitdatei der GLTF ließ sich nicht lesen. Prüfe ihre Zugriffsrechte "
                "oder exportiere als GLB."
            ),
            constraint="unreadable",
            values={"dependency": reference.uri},
        )
    check_limits(len(data), 0)
    embedded = f"data:{reference.media_type};base64,{base64.b64encode(data).decode('ascii')}"
    cached[reference.dependency] = embedded
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


def detect_unit(diagonal: float) -> UnitGuess:
    """Rät die Einheit einer Datei aus der Größe ihres Hüllquaders.

    Genau eine plausible Lesart gewinnt. Mehrere plausible Lesarten heißen,
    dass die Frage an den Nutzer geht — das ist Leitprinzip 6, keine
    Höflichkeit.
    """
    if diagonal <= EPS_GEOM:
        return UnitGuess(unit=None, candidates=CANDIDATE_UNITS, diagonal=diagonal)
    plausible = tuple(
        unit
        for unit in CANDIDATE_UNITS
        if PLAUSIBLE_MIN_MM <= to_mm(diagonal, unit) <= PLAUSIBLE_MAX_MM
    )
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


def check_unpacked(payload: bytes) -> None:
    """Die entpackte Summe eines Containers gegen dieselbe Grenze (§32).

    Geprüft war nur die gepackte Größe: 2,6 MB wurden beim Lesen zu 1,08 GB —
    Verhältnis 412, und über ``ingest/fetch`` ist so eine Datei aus dem Netz
    erreichbar. Die Zahlen stehen im zentralen Verzeichnis des Archivs; die
    Prüfung liest kein einziges Byte des Inhalts.
    """
    import zipfile
    from io import BytesIO

    try:
        with zipfile.ZipFile(BytesIO(payload)) as container:
            unpacked = sum(info.file_size for info in container.infolist())
    except zipfile.BadZipFile:
        # Keine gültige Zip — das meldet der eigentliche Leser mit seinem
        # eigenen, besseren Satz.
        return
    if unpacked > MAX_FILE_BYTES:
        raise ValidationError(
            field="file",
            detail=_("Die Datei entpackt sich größer, als diese Anwendung verarbeitet."),
            constraint="file_too_large",
            values={"unpacked": unpacked, "limit": MAX_FILE_BYTES},
        )


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Das normalisierte Netz plus was mit ihm passiert ist."""

    mesh: MeshData
    info: IngestInfo
    findings: tuple[Finding, ...] = ()


def _silent(fraction: float, text: str) -> None:
    return None


def normalise(
    mesh: MeshData,
    unit: LengthUnit,
    *,
    weld: bool = True,
    remove_degenerate: bool = True,
    unify_normals: bool = True,
    place_on_bed: bool = False,
    progress: ProgressFn = _silent,
) -> IngestResult:
    """Führt die sechs Schritte aus und meldet, was sie getan haben."""
    findings: list[Finding] = []
    body: trimesh.Trimesh = mesh.raw.copy()
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

    diagonal = float(np.linalg.norm(body.extents)) if len(body.faces) else 0.0

    # 2 — Eckpunkte verschweißen, mit einer Toleranz, die der Modellgröße folgt.
    welded = False
    if weld and len(body.faces):
        progress(0.2, str(_("Punkte verschweißen")))
        before = len(body.vertices)
        was_closed = bool(body.is_watertight)
        tolerance = weld_tolerance(diagonal)
        unwelded = body.copy() if was_closed else None
        body.merge_vertices(digits_vertex=_digits_for(tolerance))
        welded = len(body.vertices) < before
        # **Ein Verschweißen, das das Netz aufreißt, wird zurückgenommen.**
        #
        # Zwei Punkte, die dichter beieinanderliegen als die Toleranz, gehören
        # meist zusammen — manchmal aber zu zwei Blättern derselben Fläche, und
        # dann schnürt das Zusammenlegen sie zu einer Kante mit drei Nachbarn
        # ab. Gemessen an einer 3MF, die diese Anwendung selbst geschrieben
        # hatte: 17186 Ecken, wasserdicht; verschweißt bei 0,28 µm blieben
        # 17184, und der Prüfbericht sagte „Das Modell ist nicht geschlossen"
        # über eine Datei, die es war. Verschweißen ist eine Reparatur, und
        # eine Reparatur, die etwas kaputt macht, wird nicht angewendet.
        if welded and unwelded is not None and not body.is_watertight:
            body = unwelded
            welded = False
            findings.append(
                Finding(
                    code="ingest.weld_skipped",
                    severity="info",
                    message=_(
                        "Doppelte Punkte blieben stehen — sie zu verschweißen hätte das "
                        "geschlossene Netz aufgerissen."
                    ),
                    values={"tolerance": format_length(tolerance)},
                )
            )
        elif welded:
            findings.append(
                Finding(
                    code="ingest.welded",
                    severity="info",
                    message=_("Doppelte Punkte wurden verschweißt."),
                    values={"removed": before - len(body.vertices)},
                )
            )

    # 3 — entartete Dreiecke: null Fläche, Nadeln, Duplikate.
    removed = 0
    if remove_degenerate and len(body.faces):
        progress(0.4, str(_("Entartete Dreiecke entfernen")))
        before = len(body.faces)
        was_closed = bool(body.is_watertight)
        intact = body.copy() if was_closed else None
        body.update_faces(body.nondegenerate_faces(height=EPS_GEOM))
        body.update_faces(body.unique_faces())
        body.remove_unreferenced_vertices()
        removed = before - len(body.faces)
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
            removed = 0
            findings.append(
                Finding(
                    code="ingest.degenerate_kept",
                    severity="info",
                    message=_(
                        "Entartete Dreiecke blieben stehen — sie zu entfernen hätte das "
                        "geschlossene Netz aufgerissen."
                    ),
                    values={"kept": kept},
                )
            )
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
                    message=_("Entartete Dreiecke wurden entfernt."),
                    values={"removed": removed},
                )
            )

    # 4 — Normalen und Orientierung.
    if unify_normals and len(body.faces):
        progress(0.6, str(_("Normalen vereinheitlichen")))
        was_volume = float(body.volume)
        trimesh.repair.fix_winding(body)
        if body.is_watertight:
            trimesh.repair.fix_inversion(body)
        if was_volume < 0.0 <= float(body.volume):
            findings.append(
                Finding(
                    code="ingest.normals_flipped",
                    severity="info",
                    message=_("Die Ausrichtung der Flächen wurde korrigiert."),
                )
            )

    # 5 — Komponenten. Kleine werden gemeldet, nie still verworfen.
    progress(0.8, str(_("Komponenten zählen")))
    components = _count_components(body, findings)

    # 6 — Lage. Das Aufsetzen aufs Bett wird angeboten, nicht erzwungen.
    if place_on_bed and len(body.faces):
        progress(0.9, str(_("Auf das Bett setzen")))
        body.apply_translation((0.0, 0.0, -float(body.bounds[0][2])))

    too_fine = _too_fine(len(body.faces))
    if too_fine is not None:
        findings.append(too_fine)

    if not body.is_watertight and len(body.faces):
        findings.append(
            Finding(
                code="ingest.not_watertight",
                severity="warning",
                # **Und was jetzt hilft** (§2.7, Regel 17). Das war der
                # häufigste Befund beim Einlesen eines heruntergeladenen
                # Modells, und er sagte nur, was nicht stimmt — der Nachbar
                # eine Zeile darüber nennt seine Handlung seit je.
                message=_(
                    "Das Modell ist nicht geschlossen. „Reparieren“ schließt die offenen Stellen."
                ),
                values={"open_edges": _open_edge_count(body)},
            )
        )

    progress(1.0, "")
    _log.info(
        "ingested mesh: %d triangles, unit %s, %d components", len(body.faces), unit, components
    )
    return IngestResult(
        mesh=mesh.replacing(body),
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

    **Zwei Sätze, weil es zwei Grenzen sind.** Der eine Satz für beide log
    zwischen 120 000 und 200 000: Dort lehnen die Karten ab, die
    Merkmalserkennung läuft weiter. Ein Befund, der mehr behauptet, als
    stimmt, kostet den nächsten seinen Kredit.

    Genannt wird die **Operation**, nicht der Menüweg: Hier stand „Netz →
    Dezimieren", und beides war falsch — das Menü heißt *Ändern*, die
    Operation *Dreiecke verringern*. Ein Weg im Text driftet, sobald jemand
    eine Kategorie verschiebt; ein Operationstitel ist derselbe String, den
    Menü, Palette und Kontextmenü zeigen, und die Palette findet ihn.
    """
    if triangles <= HEAVY_TRIANGLES:
        return None
    if triangles > max(MAP_LIMIT_TRIANGLES, FEATURE_LIMIT_TRIANGLES):
        message = _(
            "Dieses Modell ist sehr fein vernetzt. Analysekarten und "
            "Merkmalserkennung lehnen ab; „Dreiecke verringern“ hilft."
        )
    elif MAP_LIMIT_TRIANGLES < FEATURE_LIMIT_TRIANGLES:
        message = _(
            "Dieses Modell ist fein vernetzt. Die Analysekarten lehnen ab; "
            "„Dreiecke verringern“ hilft."
        )
    else:
        message = _(
            "Dieses Modell ist fein vernetzt. Die Merkmalserkennung lehnt ab; "
            "„Dreiecke verringern“ hilft."
        )
    return Finding(
        code="ingest.very_large",
        severity="warning",
        message=message,
        values={"triangles": triangles, "comfortable": HEAVY_TRIANGLES},
    )


def _open_edge_count(body: trimesh.Trimesh) -> int:
    """Kanten, die zu genau einem Dreieck gehören. Direkt gezählt, ohne
    Graphenbibliothek.
    """
    single = trimesh.grouping.group_rows(body.edges_sorted, require_count=1)
    return len(single)


def _digits_for(tolerance: float) -> int:
    """Die Verschweißtoleranz so ausgedrückt, wie trimesh sie will:
    als Nachkommastellen.
    """
    if tolerance <= 0.0:
        return 8
    return max(0, min(12, round(float(-np.log10(tolerance)))))


def _count_components(body: trimesh.Trimesh, findings: list[Finding]) -> int:
    pieces = face_components(body)
    if len(pieces) <= 1:
        return len(pieces)
    sizes = [float(body.area_faces[piece].sum()) for piece in pieces]
    largest = max(sizes)
    small = [size for size in sizes if size < largest * SMALL_COMPONENT_SHARE]
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
