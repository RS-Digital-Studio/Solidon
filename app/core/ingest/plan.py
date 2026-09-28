"""Welche Operation eine Datei einliest — für Fenster und Kommandozeile.

Die Entscheidung ist klein und stand zweimal im Code: STEP nimmt den exakten
Kern, eine flache Zeichnung wird extrudiert, alles andere ist ein Netz, und bei
einer 3MF-Baugruppe steht die Körperzahl in der Datei. Das Fenster traf sie
vollständig (``Session.import_payload``); die Kommandozeile legte immer ``load``
auf den Stapel.

Was dabei herauskam, ist die schlechteste Sorte Fehler — einer, der eine
Unwahrheit sagt: ``solidon3d import projekt.p3d teil.step`` antwortete „Dieses
Dateiformat kann nicht gelesen werden.", für ein Format, das dieselbe Anwendung
im Fenster einliest. Dasselbe für SVG und DXF.

Deshalb steht sie jetzt hier: eine Stelle, zwei Aufrufer, kein Weg
auseinanderzulaufen. Der Titel gehört dazu — er steht im Verlauf, und „STEP
laden" gegen „Modell laden" ist Teil derselben Entscheidung.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.core.brep import step as brep_step
from app.core.errors import AppError
from app.core.ingest import threemf
from app.core.ingest.loader import (
    READABLE_SUFFIXES,
    check_limits,
    check_readable,
    check_unpacked,
)
from app.core.ingest.outline import OUTLINE_SUFFIXES, is_outline
from app.core.log import get_logger
from app.core.registry import REGISTRY
from app.core.registry.params import WHOLE_FILE, reads_scene
from app.core.scene.history import OperationDraft
from app.core.types import Document, ObjectId, ProgressFn, SceneObject
from app.core.units import EPS_DISPLAY
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Der Titel der Transaktion je Weg. Im Verlauf steht er, nicht der Op-Name.
_TITLES: Final[dict[str, TranslatableText]] = {
    "load_step": _("STEP laden"),
    "load_outline": _("Zeichnung hochziehen"),
    "load": _("Modell laden"),
}

#: Jede Endung, die der Plan einer Import-Operation zuordnen kann. Dateidialog,
#: Ablagefeld und Netzimport lesen dieselbe Liste; eine eigene Aufzählung in der
#: Oberfläche wäre ein Versprechen, das vom Decoder wegdriften kann.
MODEL_SUFFIXES: Final = tuple(
    dict.fromkeys((*READABLE_SUFFIXES, *brep_step.SUFFIXES, *OUTLINE_SUFFIXES))
)


@dataclass(frozen=True, slots=True)
class BodyChoice:
    """Ein Körper einer STEP-Baugruppe, wie ihn die Importauswahl zeigt (P7.4).

    Nur Auskunft, keine Geometrie: Name, Farben, Maße, welches Teil er
    einsetzt — damit Fenster und Kommandozeile ohne OpenCASCADE zeigen
    können, was gewählt wird. Die Kennung ist die aus
    ``brep.step.StepBody.key``, dieselbe, die in ``bodies`` gespeichert wird.
    """

    key: str
    name: str
    colours: tuple[str, ...]
    """``#rrggbb`` je Farbe des Körpers, in der Reihenfolge ihres Auftretens."""
    size: tuple[float, float, float]
    """Ausdehnung in X, Y und Z, in Millimetern."""
    low: tuple[float, float, float]
    """Die untere Ecke der Weltgrenzen — mit ``size`` die Lage in der Baugruppe."""
    part: str
    """Gleiche Angabe heißt: dasselbe Teil, nur anders gelegt oder gefärbt."""
    mirrored: bool = False
    solid: bool = True


@dataclass(frozen=True, slots=True)
class ImportPlan:
    """Was aus einer Datei wird: eine Transaktion mit genau einem Entwurf."""

    title: TranslatableText
    draft: OperationDraft
    asks_unit: bool
    """Ob die Einheitenfrage überhaupt gestellt werden muss.

    Nur ein Netz hat sie, und auch das nicht immer. STEP trägt seine Einheit
    selbst, und eine flache Zeichnung hat keine dritte Dimension, bis jemand
    sagt, wie dick sie sein soll (§25, §30, §11.1) — dort wäre die Frage eine
    Zumutung ohne Zweck. Eine 3MF sagt ihre Einheit ebenfalls selbst, sofern
    sie das ``unit``-Attribut führt.
    """
    choices: tuple[BodyChoice, ...] = ()
    """Die Körper einer STEP-Baugruppe, aus denen der Kunde wählt (P7.4).

    Leer bei jedem anderen Format und bei einer STEP-Datei mit einem Körper —
    dort gibt es nichts zu wählen. Die Auswahl selbst steht im Entwurf
    (``load_step.bodies``); die Liste ist, was die Importauswahl zeigt.
    """


#: Die Operationen, deren ``name``-Parameter im Objektbaum landet.
_NAMING_OPS: Final[frozenset[str]] = frozenset({"load", "load_step", "load_outline"})


def names_in_use(document: Document) -> tuple[str, ...]:
    """Die Objektnamen, die die Schritte dieses Stapels schon vergeben haben.

    **Gefragt wird der Stapel und nicht die ausgewertete Szene** — dieselbe
    Entscheidung wie bei ``first_model`` unten: Er steht fest, bevor gerechnet
    wird, und was daraus folgt, landet in den Parametern der Operation statt
    in einem Zustand, den die nächste Auswertung anders vorfindet (§15.1).

    Genommen wird, was je vergeben wurde, auch ein weggetauschter Name: Wer
    umbenennt, gibt seinen alten Namen nicht wieder frei. Das ist die sichere
    Richtung — eine Nummer zu viel ist ein ungewöhnlicher Name, eine zu wenig
    sind zwei Körper, die im Baum gleich heißen.

    Eine 3MF-Baugruppe bringt ihre Namen aus der Datei mit; die stehen in
    keinem Parameter und deshalb auch nicht hier.
    """
    used: list[str] = []
    for operation in document.ops:
        chosen = str(operation.params.get("name", "") or "")
        if operation.op == "rename_object":
            if chosen:
                used.append(chosen)
            continue
        if operation.op not in _NAMING_OPS:
            continue
        if chosen:
            used.append(chosen)
            continue
        source = document.sources.get(str(operation.params.get("source", "")))
        if source is not None:
            stem = Path(source.path).stem
            copy = operation.params.get("copy")
            # Eine nummerierte Kopie belegt ihre Nummer, sonst bekäme die
            # dritte dieselbe wie die zweite.
            if isinstance(copy, int) and not isinstance(copy, bool) and copy >= 2:
                used.append(copy_name(stem, copy))
            else:
                used.append(stem)
    return tuple(used)


def copy_name(name: str, number: int) -> str:
    """„plate_holes (2)" — wie eine zweite Kopie derselben Datei heißt."""
    return f"{name} ({number})"


def _copy_number(file_name: str, taken: Sequence[str]) -> int:
    """Null, wenn der Dateiname frei ist — sonst die erste freie Nummer ab zwei.

    Auch die ältere Schreibweise „plate_holes 2" belegt ihre Nummer: Projekte
    vor 0.5.0 tragen sie als Namen im Schritt.
    """
    stem = Path(file_name).stem
    if stem not in taken:
        return 0
    number = 2
    while copy_name(stem, number) in taken or f"{stem} {number}" in taken:
        number += 1
    return number


def _own_name(file_name: str, taken: Sequence[str], *, loads: bool) -> dict[str, object]:
    """Die Nummer für diesen Import, wenn der Dateiname schon steht.

    Dieselbe Datei zweimal einzulesen ist der gewöhnliche Weg zu zwei gleichen
    Teilen, und der Objektbaum trug danach zweimal „plate_holes": im Baum nicht
    auseinanderzuhalten, im Prüfbericht zweimal derselbe Satz.

    **Die Ladeoperation bekommt eine Nummer, keinen Namen** (Durchsicht
    0.5.0): ``copy`` hängt „(2)" an jeden Körper, den sie einliest. Ein Name
    passte nur auf einen Körper — eine Baugruppe bringt ihre Namen aus der
    Datei mit, und die zweite Kopie trug sie alle ein zweites Mal; eine
    3MF mit einem benannten Körper hieß beim ersten Mal nach dem Körper und
    beim zweiten nach der Datei. Die Klammer, weil Teilnamen selbst oft auf
    eine Zahl enden („Sieb 1 (2)" statt „Sieb 1 2"). Die anderen
    Einleseoperationen machen genau einen Körper und bekommen den Namen
    selbst, in derselben Schreibweise.

    Ist der Name frei, steht **kein** Parameter im Entwurf: Ein leerer Name
    heißt „nimm den Dateinamen", und ihn hineinzuschreiben hieße, dieselbe
    Auskunft zweimal zu führen.
    """
    number = _copy_number(file_name, taken)
    if not number:
        return {}
    if loads:
        return {"copy": number}
    return {"name": copy_name(Path(file_name).stem, number)}


def _silent_plan(fraction: float, text: str) -> None:
    """Der Vorgabewert: Wer keinen Fortschritt will, bekommt keinen.

    Dieselbe Form wie ``loader._silent`` und ``threemf._silent_scan`` — eine
    Funktion statt ``None``, damit die Zählschleife nicht bei jedem Schritt
    fragen muss, ob sie melden darf.
    """


def import_plan(
    source_id: str,
    name: str,
    payload: bytes,
    unit: str = "auto",
    *,
    first_model: bool | None = None,
    taken: Sequence[str] = (),
    progress: ProgressFn = _silent_plan,
) -> ImportPlan:
    """Der Einleseweg für eine Datei, entschieden an ihrer Endung.

    ``first_model`` sagt, ob die Szene noch leer ist. **Das erste Modell**
    eines Projekts (``True``) kommt **auf** die Platte und **in ihre Mitte**
    (§17.1, Schritt 6), statt dort zu liegen, wo seine Datei es hinlegt: Ein
    heruntergeladenes Modell sitzt meist um den Ursprung und steckt zur Hälfte
    unter dem Bett, eines aus einem CAD-Programm hat seinen Nullpunkt in einer
    Ecke und liegt weit daneben. Beides ist für den ersten Blick auf ein
    frisches Projekt die falsche Lage (Entscheidung Robert, 03.09.2026).

    **Jedes weitere** (``False``) kommt aufgesetzt an die erste freie Stelle,
    Platte für Platte wie *Auf dem Bett anordnen* (§29): In die Mitte
    geschoben läge es im ersten, an seinen Dateikoordinaten meist außerhalb,
    obwohl auf den Platten Platz war (Robert, 28.09.2026). ``None`` heißt, der
    Aufrufer entscheidet nichts — die Datei behält ihre Lage.

    Die Entscheidung fällt hier und wird in die Parameter der Operation
    geschrieben (``place_on_bed``, ``centre``, ``free_spot``), nicht als Regel
    beim Auswerten nachgeschlagen: Sonst hinge das Ergebnis daran, was sonst
    noch in der Szene steht. Die freie Stelle sucht die Operation einmal und
    hält sie als Antwort im Schritt fest (§15.7, ``spot_*``) — danach bleibt
    das Modell liegen, auch wenn sich davor etwas ändert.

    ``taken`` sind die Namen, die in diesem Stapel schon vergeben sind
    (:func:`names_in_use`). Trägt einer davon den Dateinamen, bekommt dieser
    Körper eine Nummer dahinter — sonst stünden nach zweimal derselben Datei
    zwei gleichnamige Körper im Baum und zweimal derselbe Satz im Prüfbericht.

    ``payload`` wird nur für die 3MF-Baugruppe gebraucht: Wie viele Körper eine
    Datei hält, entscheidet sich **vor** der Operation, weil der Stapel die
    Objekt-IDs vergibt, bevor irgendetwas läuft (§11). Gezählt wird ohne eine
    einzige Koordinate zu lesen.
    """
    suffix = Path(name).suffix
    # Die Größengrenze steht vor jeder Operation, für **jedes** Format — nicht
    # nur für 3MF. Eine zu große STL ging sonst als Quelle ins Dokument, die
    # Operation landete im Stapel und scheiterte erst bei der Auswertung, und
    # die übergroße Quelle wanderte beim nächsten Speichern in die Projektdatei.
    # (Die entpackte Größe bleibt 3MF-eigen — nur ein Archiv hat eine.)
    check_limits(len(payload), 0)
    # Und ob überhaupt ein Modell darin sein kann. Beides gehört vor die
    # Operation: Was hier durchgeht, wird zur eingebetteten Quelle im
    # Dokument und wandert beim Speichern in die Projektdatei — auch wenn
    # der Leser danach nichts damit anfangen kann.
    check_readable(payload, suffix)
    own_name = _own_name(name, taken, loads=False)
    if brep_step.is_step(suffix):
        return _step_plan(
            source_id, name, payload, first_model=first_model, taken=taken, progress=progress
        )
    if is_outline(suffix):
        return ImportPlan(
            title=_TITLES["load_outline"],
            draft=OperationDraft(op="load_outline", params={"source": source_id, **own_name}),
            asks_unit=False,
        )
    parts = 1
    asks = True
    gltf = suffix.lower() in (".glb", ".gltf")
    if gltf:
        # Der neue Import speichert den Formatvertrag. Alte Ladeschritte
        # behalten über Schema und Migration ausdrücklich ihre Rohachsen.
        asks = False
    if suffix.lower() == ".3mf":
        # **Die entpackte Grenze steht vor dem Parsen.** Zählen heißt bei einer
        # 3MF, das ganze XML zu lesen, und das geschieht hier — im Hauptthread,
        # bevor irgendeine Operation läuft. Eine Datei von 1,9 MB wird dabei zu
        # 660 MB im Speicher. ``check_unpacked`` gibt es für genau diesen Fall
        # (§32); es lief nur an der falschen Stelle, nämlich erst in der
        # Operation. Die Zahlen dafür stehen im zentralen Verzeichnis des
        # Archivs; erst nach den Grenzen werden gleich benannte Einträge
        # auf bytegleichen Inhalt geprüft.
        check_unpacked(payload)
        # Körper und Dreiecke in einem streamenden Lauf. Die entpackte Grenze
        # allein hält den Speicher nicht auf: read_objects hebt beim Vollparse
        # rund das Zwölffache der entpackten XML in ET.Element-Objekte, und die
        # Dreiecksgrenze griff bisher erst *nach* diesem Parsen. Sie greift
        # jetzt hier, vor jeder Operation — gezählt wurde ohne eine Koordinate.
        parts, triangles = threemf.scan_assembly(payload, progress)
        check_limits(len(payload), triangles)
        # Eine 3MF trägt ihre Einheit im ``unit``-Attribut. Wo sie dasteht,
        # stellt die Operation die Frage nicht — und dann darf der Aufrufer
        # sie auch nicht vorweg stellen: Die Kommandozeile tat es, und ihre
        # Antwort hätte die Angabe der Datei überschrieben.
        asks = threemf.declared_unit(payload) is None
    return ImportPlan(
        title=_TITLES["load"],
        draft=OperationDraft(
            op="load",
            params={
                "source": source_id,
                "unit": unit,
                **({"coordinates": "gltf"} if gltf else {}),
                # Eine Datei mit mehreren Platten kommt auf ihre Platten (RM-252).
                **({"plates": True} if suffix.lower() == ".3mf" else {}),
                # Eine Nummer statt eines Namens (``_own_name``): Sie gilt
                # jedem Körper, den die Datei bringt, auch einer Baugruppe.
                **_own_name(name, taken, loads=True),
                **_placement(first_model),
            },
            produces=max(parts, 1),
        ),
        asks_unit=asks,
    )


def _placement(first_model: bool | None) -> dict[str, bool]:
    """Die Lage eines Ladeschritts als seine Parameter (§17.1, Schritt 6).

    Das erste Modell aufgesetzt und mittig, jedes weitere aufgesetzt an die
    erste freie Stelle; ohne Angabe nichts — dann gilt die Lage der Datei.
    """
    if first_model is None:
        return {}
    if first_model:
        return {"place_on_bed": True, "centre": True}
    return {"place_on_bed": True, "free_spot": True}


def _step_plan(
    source_id: str,
    name: str,
    payload: bytes,
    *,
    first_model: bool | None,
    taken: Sequence[str],
    progress: ProgressFn,
) -> ImportPlan:
    """Der Einleseweg einer STEP-Datei: jede Komponenteninstanz ein Körper (P7.4).

    Wie viele Körper die Datei trägt, steht vor der Operation fest — wie bei
    der 3MF-Baugruppe, weil der Stapel die Objekt-IDs vergibt, bevor gerechnet
    wird (§11). Gewählt sind zunächst alle; die Importauswahl im Fenster darf
    die Liste kürzen (``choices``).

    **Lässt sich die Baugruppe nicht auflösen**, liest der Schritt die Datei
    über den bisherigen Leser als einen Körper (``*``) und sagt im
    Prüfbericht, dass Namen und Farben dabei fehlen (Konzept §13.9: der
    Rückfall mit Metadatenverlust wird angezeigt, nicht verschwiegen). Was
    der Kunde korrigieren kann — eine unlesbare Datei, zu viele Körper —,
    bleibt eine Absage mit Vorschlag.
    """
    stem = Path(name).stem
    choices: tuple[BodyChoice, ...] = ()
    try:
        assembly = brep_step.read_assembly(payload, stem, progress=progress)
    except AppError:
        raise
    except Exception as problem:
        # Ein nativer Fehler der Baugruppenlesung ist kein Grund, die Datei
        # abzuweisen, solange der bisherige Leser sie kennt: ``load_step``
        # liest ``*`` über ihn und meldet den Verlust.
        _log.warning("the STEP assembly could not be resolved, one body instead: %s", problem)
        keys: list[str] = [WHOLE_FILE]
    else:
        keys = [body.key for body in assembly.bodies]
        if len(assembly.bodies) > 1:
            choices = tuple(choice_of(body) for body in assembly.bodies)
    return ImportPlan(
        title=_TITLES["load_step"],
        draft=OperationDraft(
            op="load_step",
            params={
                "source": source_id,
                "bodies": selection(keys),
                # Eine Nummer statt eines Namens, wie beim Netz: Sie gilt
                # jedem Körper, den die Datei bringt (``_own_name``).
                **_own_name(name, taken, loads=True),
                **_placement(first_model),
            },
            produces=len(keys),
        ),
        asks_unit=False,
        choices=choices,
    )


def choice_of(body: brep_step.StepBody) -> BodyChoice:
    """Was die Importauswahl über einen Körper zeigt — ohne seine Form.

    Die Maße sind die des Teils selbst, gleich wie es liegt; die Lage kommt
    aus dem Quader um die Instanz (``StepBody.box``). Gemessen wird dafür
    nichts je Instanz: ``AddOptimal`` an tausend gerundeten Teilen kostete im
    Plan 8,3 s.
    """
    low = body.box[:3] if body.box is not None else body.bounds()[:3]
    return BodyChoice(
        key=body.key,
        name=body.name,
        colours=body.colours,
        size=body.size,
        low=(low[0], low[1], low[2]),
        part=body.geometry,
        mirrored=body.mirrored,
        solid=body.solid,
    )


def selection(keys: Sequence[str]) -> str:
    """Die gespeicherte Form einer Körperauswahl (``load_step.bodies``)."""
    return json.dumps(list(keys), ensure_ascii=False, separators=(",", ":"))


def with_selection(plan: ImportPlan, keys: Sequence[str]) -> ImportPlan:
    """Derselbe Plan mit einer gekürzten Körperauswahl.

    Die Zahl der Ausgänge folgt der Auswahl — der Stapel liest sie aus
    ``bodies`` (``produces_from``), der Entwurf trägt sie mit.
    """
    import dataclasses

    known = {choice.key for choice in plan.choices}
    wanted = [key for key in keys if key in known]
    return dataclasses.replace(
        plan,
        draft=dataclasses.replace(
            plan.draft,
            params={**plan.draft.params, "bodies": selection(wanted)},
            produces=len(wanted),
        ),
    )


#: Die Operationen, die eine Datei **nur hereinnehmen**.
#:
#: ``load_outline`` steht ausdrücklich nicht dabei: Eine flache Zeichnung wird
#: dort auf eine Höhe gezogen, die niemand aus der Datei lesen kann — das ist
#: eine Konstruktionsentscheidung und kein Einlesen.
PLAIN_IMPORT_OPS: Final[frozenset[str]] = frozenset({"load", "load_step"})


def imported_group_for_bed(
    document: Document, object_id: ObjectId, objects: Mapping[ObjectId, SceneObject]
) -> tuple[ObjectId, ...]:
    """Nur ein wirksames gemeinsames Aufsetzen darf die Einzelhandlung ersetzen."""
    targets = imported_group(document, object_id, objects)
    if (
        not targets
        or abs(min(objects[key].mesh.bounds.minimum[2] for key in targets)) <= EPS_DISPLAY
    ):
        return ()
    return targets


def imported_group(
    document: Document, object_id: ObjectId, live_objects: Collection[ObjectId]
) -> tuple[ObjectId, ...]:
    """Die vollständigen, noch unbenutzten Ausgaben genau dieses mehrteiligen Imports.

    Ein späterer Zugriff auf ein Mitglied beendet das gemeinsame Angebot,
    auch wenn die Operation dessen Kennung erhält. Andere Imports und die
    aktuelle Auswahl ändern den Umfang nicht. Die Auswertung liefert die
    lebenden Kennungen; unvollständige Ergebnisse erhalten kein Gruppenangebot.
    """
    for index, operation in enumerate(document.ops):
        if operation.op not in PLAIN_IMPORT_OPS or object_id not in operation.outputs:
            continue
        targets = operation.outputs
        members = set(targets)
        if len(targets) < 2 or not members.issubset(live_objects):
            return ()
        for later in document.ops[index + 1 :]:
            if members.intersection((*later.inputs, *later.outputs)):
                return ()
            if REGISTRY.has(later.op):
                spec = REGISTRY.get(later.op)
                # Eine spätere Gegenflächenwahl kann ihren Träger auch über
                # einen Ausdruck bestimmen. Ohne Auswertung keinen fremden
                # Bezug als unbenutzt erklären: Das Angebot endet konservativ.
                if (
                    spec.reads_other_bodies
                    or reads_scene(spec.params, later.params)
                    or any(
                        field.targets_feature and later.params.get(field.name, field.default)
                        for field in spec.params.spec()
                    )
                ):
                    return ()
        return targets
    return ()


def is_only_imported(document: Document) -> bool:
    """Ob dieses Dokument nichts enthält, was nicht in seinen Dateien steht
    (RM-130).

    **Wozu die Frage gestellt wird.** Wer eine STL öffnet, ansieht und das
    Fenster schließt, bekam „Ungesicherte Änderungen — Speichern / Verwerfen /
    Abbrechen". Technisch stimmte das (der Import ist eine Operation im
    Stapel, und die Sitzung gilt danach als geändert), für den Kunden war es
    eine Frage nach etwas, das er nicht getan hat (Robert, 04.09.2026;
    gemessen an allen neunzehn Kundendateien). Regel 19 verlangt die Nachfrage
    dort, wo etwas unwiederbringlich weg wäre — und ein eingelesenes Modell
    ist das nicht: Die Datei liegt weiter auf der Platte.

    **Wonach gefragt wird, ist die Reproduzierbarkeit und nicht der Aufwand.**
    Ein 63-MB-Container kostet vierzehn Sekunden, aber er kostet sie ein
    zweites Mal genauso; was er nicht kostet, ist eine Entscheidung, die
    jemand noch einmal treffen müsste. Deshalb zählt hier alles mit, was eine
    solche Entscheidung festhält:

    * jede Operation, die keine reine Ladeoperation ist
      (:data:`PLAIN_IMPORT_OPS`) — auch ein Verschieben auf dem Bett,
    * jede Quelle, die nicht aus einem Import stammt; ein **erzeugtes** Modell
      trägt Anfrage und Startwert in seiner Herkunft und ist ohne die
      Projektdatei weg,
    * Parameter, Passungen und Gesprächsbeiträge,
    * Druckeinstellungen — Stufe, Düse und Material sind eine Wahl,
    * und jede Transaktion mit ``changes``: Drucker- und Materialwechsel
      stehen nicht im Stapel, sondern dort (§15.5).

    Ein leerer Stapel ist **nicht** „nur importiert": Dort gibt es nichts zu
    verlieren, und die Frage stellt sich gar nicht erst.
    """
    if not document.ops:
        return False
    if document.parameters or document.fits or document.chat:
        return False
    if document.print_settings is not None:
        return False
    if any(operation.op not in PLAIN_IMPORT_OPS for operation in document.ops):
        return False
    if any(source.kind != "import" for source in document.sources.values()):
        return False
    return all(entry.changes is None for entry in document.transactions)
