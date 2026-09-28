"""Weg 3: Text oder Bild zu einem Körper in der Szene (Bauplan §2.2, §27).

    Text oder Bild → Mesh → Reparaturkette läuft automatisch → Prüfbericht

Zwei Dinge am Aufbau sind es wert, festgehalten zu werden, denn beide waren
Entscheidungen und nicht der naheliegende Weg.

**Die erzeugte Datei wird eine Quelle, keine Operation.** Ein Generator ist
keine Funktion: derselbe Prompt mit demselben Startwert liefert nach einem
Modell-Update etwas anderes. Eine Operation, die ihn aufriefe, machte jedes
Projekt unreproduzierbar (§11.3). Also werden die Bytes wie eine
hineingezogene Datei ins Projekt eingebettet, und der Stapel danach ist der
gewöhnliche.

**Die Reparaturkette liegt auf dem Stapel, nicht im Körper eingebacken.**
Weg 3 sagt, sie läuft automatisch, und das tut sie — aber als eigener Schritt,
damit der Bericht sagen kann, was sie geändert hat, und damit sie zurückgeht,
wenn sie etwas weggenommen hat, das gemeint war (§11.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final

from app.core import activation
from app.core.backends.mesh import CancelledFn, GeneratedMesh, MeshBackend
from app.core.log import get_logger
from app.core.scene.history import History, OperationDraft
from app.core.scene.project import Project, checksum, embedded_source_path, next_source_id
from app.core.types import ObjectId, Origin, ProgressFn, Source, SourceId, SourceOrigin
from app.i18n import _

_log = get_logger(__name__)

#: Die Reparaturkette für einen erzeugten Körper (§25). Alles ist an, auch die
#: zwei Schritte, die die Importstufe weglässt: ein erzeugtes Netz bringt lose
#: Fragmente und Selbstdurchdringungen serienmäßig mit, und anders als bei
#: einem Teil, das jemand modelliert hat, steckt darin keine Absicht, die es
#: zu bewahren lohnte.
GENERATED_REPAIR: dict[str, bool] = {
    "weld": True,
    "degenerate": True,
    "normals": True,
    "fill_holes": True,
    "small_components": True,
    "self_intersections": True,
}

#: Auf welche längste Kante ein erzeugter Körper gebracht wird.
#:
#: Ein Bildmodell liefert seine Ausgabe auf einem Einheitswürfel — als
#: Millimeter gelesen ein Krümel von ein bis zwei Millimetern. Hundert ist
#: keine Vorhersage, wie groß das Teil werden soll, sondern der Punkt, von dem
#: aus jede Richtung gleich weit ist: ein Möbel im Puppenhausmaßstab liegt
#: darunter, ein Gehäuse darüber, und beides ist ein Schritt.
WORKING_SIZE_MM = 100.0


def _silent(fraction: float, text: str) -> None:
    del fraction, text


#: Ab wie vielen Dreiecken ein erzeugtes Netz dezimiert wird — **nie über der
#: automatischen Merkmalserkennung** (``perceive.local.FEATURE_LIMIT_TRIANGLES``).
#:
#: Hier stand einmal 500 000, begründet mit der Grenze des Steckbriefs, während
#: die Erkennung bei 200 000 ausstieg: Was dazwischen lag, behielt seine
#: Auflösung und verlor die Merkmale — kein Klick auf eine Bohrung, keine
#: Passung, nichts für den Agenten, und bei TripoSG war das der Normalfall.
#: Die Zwickmühle daneben (``decimate`` zerriss ein unverschweißtes Netz) ist
#: seit ``geom.mesh_ops._welded_for_simplify`` aufgelöst.
#:
#: **Eine eigene Zahl seit dem 24.09.2026.** Die Anhebung der Erkennung auf
#: 1,5 Millionen hebt sie nicht mit: Ein erzeugtes Netz braucht keine feinere
#: Auflösung, und jede Million mehr kostet jeden Folgeschritt Zeit. Die Zusage
#: bleibt die Richtung — darunter, nie darüber.
GENERATED_TRIANGLE_LIMIT: Final = 1_000_000

#: Worauf dezimiert wird: drei Viertel der Grenze, damit eine spätere Boolesche
#: Operation nicht sofort wieder darüber landet — und immer noch fein genug,
#: dass eine erzeugte Figur ihre Falten behält. Als Anteil und nicht als eigene
#: Zahl: Wer die Grenze verschiebt, verschiebt den Abstand mit.
GENERATED_TRIANGLE_TARGET: Final = GENERATED_TRIANGLE_LIMIT * 3 // 4


@dataclass(frozen=True, slots=True)
class Generation:
    """Was Weg 3 erzeugt hat: die Quelle, das Objekt, und wie es dahin kam."""

    source_id: SourceId
    object_id: ObjectId
    result: GeneratedMesh
    transactions: tuple[str, ...] = field(default_factory=tuple)


def from_text(
    project: Project,
    backend: MeshBackend,
    prompt: str,
    *,
    seed: int = 0,
    name: str = "",
    progress: ProgressFn = _silent,
    cancelled: CancelledFn | None = None,
) -> Generation:
    """Erzeugt einen Körper aus einer Beschreibung und legt ihn ins Projekt.

    ``cancelled`` reicht bis in die Warteschleife des Generators durch (§15.6,
    :meth:`app.core.backends.mesh.MeshBackend.text_to_mesh`) — eine Erzeugung
    dauert Minuten, und so lange muss sie sich abbrechen lassen. Der Abbruch
    kommt als ``OperationCancelled`` heraus und ist kein Fehler: Ins Projekt
    ist dann nichts geschrieben, denn geschrieben wird erst danach.
    """
    result = backend.text_to_mesh(prompt, seed=seed, progress=progress, cancelled=cancelled)
    return into_project(project, result, name or prompt)


def from_image(
    project: Project,
    backend: MeshBackend,
    image: bytes,
    *,
    seed: int = 0,
    name: str = "",
    progress: ProgressFn = _silent,
    cancelled: CancelledFn | None = None,
) -> Generation:
    """Erzeugt einen Körper aus einem Bild und legt ihn ins Projekt.

    ``cancelled`` wie bei :func:`from_text` — derselbe Weg, dieselbe Zusage.
    """
    result = backend.image_to_mesh(image, seed=seed, progress=progress, cancelled=cancelled)
    return into_project(project, result, name or str(_("Aus Bild")))


def into_project(project: Project, result: GeneratedMesh, name: str = "") -> Generation:
    """Datei einbetten, laden, reparieren — zwei Schritte im Verlauf, beide
    rücknehmbar.

    Getrennt von den zwei Aufrufen darüber, damit eine Oberfläche, die schon
    ein Ergebnis hat — weil sie den Generator auf ihrem eigenen Thread laufen
    ließ — denselben Weg hinein nimmt.
    """
    name = name or result.prompt or str(_("Aus Bild"))
    document = project.document

    # **Gefragt wird, bevor geschrieben wird.** Die Quelle unten geht sofort
    # ins Dokument, und `History.apply` weiter unten fragt als Erstes die
    # Lizenzgrenze — schlägt sie dort zu, bleibt das Dokument unberührt bis
    # auf genau diese Quelle. Sie bliebe als Waise zurück und wanderte mit dem
    # nächsten Speichern in die Projektdatei, und weil das Einbetten kein
    # `_dirty` setzt, schlösse der Kunde ohne Nachfrage. Bei einem erzeugten
    # Modell ist das kein kleiner Rest: Die Quelle trägt Prompt und Startwert
    # im `SourceOrigin`, also die Anfrage des Kunden.
    #
    # Ein Rücknahmepfad wie in `Session.import_model` ginge hier nicht mit
    # einer Zeile — es folgen mehrere Transaktionen. Die Frage vorzuziehen ist
    # billiger und deckt den gemeldeten Fall vollständig: Zwischen hier und
    # dem ersten `apply` ändert sich der Freischaltzustand nicht.
    # Gefunden von 3d-druck-46 im Lizenz-Audit.
    activation.require(activation.CHANGE)

    source_id = next_source_id(document.sources)
    short = _short(name)

    document.sources[source_id] = Source(
        id=source_id,
        kind="generated",
        path=embedded_source_path(f"{short}{result.suffix}", source_id),
        # Jede Quelle kennt ihren Inhalt von Anfang an — siehe
        # ``Session._embed_source``. Der Cache-Schlüssel fragt danach (§15).
        sha256=checksum(result.payload),
        origin=SourceOrigin(
            title=short,
            author=result.backend,
            prompt=result.prompt,
            seed=result.seed,
            retrieved=datetime.now(UTC).date().isoformat(),
        ),
    )
    project.sources[source_id] = result.payload

    history = History(document)
    # Der Nutzer hat Erzeugen gedrückt, also gehört die Transaktion ihm
    # (§26.4). Welcher Generator es war, gehört zur Quelle — dort bleibt es
    # lesbar.
    origin = Origin(by="user")
    loading = history.apply(
        _("Modell erzeugen"),
        [
            OperationDraft(
                op="load",
                params={
                    "source": source_id,
                    "unit": "mm",
                    # **Eine erzeugte GLB steht auf glTF-Achsen** (RM-086).
                    # Hier stand „Rohachsen", und gemessen war das nie:
                    # TripoSG schreibt Y-oben wie jede glTF-Datei — der
                    # Drache aus ``image_00001_.glb`` und die vier
                    # Puppenhausmöbel tragen ihre Höhe auf Y. Roh gelesen lag
                    # jeder erzeugte Körper auf dem Rücken. Gedreht wird wie
                    # beim Import; die Meter der Spezifikation gelten dagegen
                    # nicht: Die Einheit bleibt ``mm``, die Größe setzt der
                    # eigene Schritt ``fit_to_size`` darunter. Ältere Projekte
                    # behalten ``legacy_raw`` über die Migration (24 → 25).
                    "coordinates": (
                        "gltf" if result.suffix.lower() in (".glb", ".gltf") else "legacy_raw"
                    ),
                    "name": short,
                    # Beim Laden nichts bereinigen, solange das Modell winzig
                    # ist. Die Reparaturkette unten holt jeden dieser Schritte
                    # nach — dann aber auf hundert Millimetern, wo dieselben
                    # Toleranzen das Richtige treffen.
                    #
                    # Beide Stufen messen absolut: das Verschweißen sucht
                    # Punkte, deren Abstand unter der Toleranz liegt, das
                    # Entarten sucht Dreiecke, deren Fläche darunter liegt. Bei
                    # zwei Millimetern Modellgröße ist das nicht der
                    # Doppelpunkt und nicht die Nadel, sondern die halbe Lehne
                    # und achtundachtzig Dreiecke, die die Hülle schließen.
                    # Vier von vier erzeugten Netzen gingen hier auf, ohne dass
                    # jemand eine Absicht hatte — und danach half nichts mehr:
                    # Löcher füllen schließt eine Naht, aber keine, die quer
                    # durch das Modell läuft.
                    "weld": False,
                    "remove_degenerate": False,
                    "unify_normals": False,
                },
            )
        ],
        origin,
    )
    object_id = document.ops[-1].outputs[0]

    # Erst die Größe, dann die Reparatur — und diese Reihenfolge ist das
    # Gegenteil einer Geschmacksfrage.
    #
    # Ein Bildmodell normiert seine Ausgabe auf einen Einheitswürfel: was
    # ankommt, misst ein bis zwei Millimeter. Die vier Möbel fürs Puppenhaus
    # kamen dabei **geschlossen** an — und wurden es erst hier nicht mehr. Das
    # Verschweißen sucht Punkte, die zusammenfallen, und seine Toleranz hängt
    # an der Diagonale; bei zwei Millimetern liegt darunter nicht der
    # Doppelpunkt, sondern die halbe Lehne. Vier von vier Netzen gingen auf,
    # ohne dass sich ein Dreieck geändert hätte, und danach half nichts mehr:
    # Löcher füllen kann eine Naht schließen, aber keine, die quer durchs
    # Modell läuft.
    #
    # In dieser Reihenfolge bleiben alle vier dicht und behalten 99,9 % ihrer
    # Dreiecke. Kanten verfeinern — der andere Weg, ein Netz zu schließen — hätte
    # sie gekostet.
    #
    # Geraten wird beim Maß nichts (Regel 21): dass ein Stuhl 75 mm hoch
    # werden soll und ein Schrank 250, weiß nur der Nutzer. Was hier entsteht,
    # ist eine Ausgangsgröße, von der aus er in einem Schritt auf sein Maß
    # kommt — und weil es eine eigene Transaktion ist, nimmt ein Undo sie
    # zurück.
    sizing = history.apply(
        _("Auf Arbeitsgröße bringen"),
        [
            OperationDraft(
                op="fit_to_size",
                inputs=(object_id,),
                outputs=(object_id,),
                # **Und erst am fertigen Maß wird gelegt** (Robert,
                # 28.09.2026): Ein erzeugtes Modell ist aus Kundensicht ein
                # weiteres Modell — aufgesetzt an die erste freie Stelle,
                # nach derselben Regel wie beim Einfügen (§17.1, Schritt 6).
                # In einem leeren Projekt heißt das: mittig auf Platte 1.
                params={"largest": WORKING_SIZE_MM, "free_spot": True},
            )
        ],
        origin,
    )

    repairing = history.apply(
        _("Reparaturkette"),
        [OperationDraft(op="repair", inputs=(object_id,), params=dict(GENERATED_REPAIR))],
        origin,
    )
    # Und ein vierter Schritt, wenn das Netz zu fein ist, um damit zu arbeiten.
    #
    # Ein Generator liefert typisch anderthalb Millionen Dreiecke. Damit hat
    # niemand ein Problem, außer der Merkmalserkennung — sie steigt oberhalb
    # von :data:`GENERATED_TRIANGLE_LIMIT` aus, und ohne Merkmale gibt es
    # nichts, worauf ein Klick oder der Agent zeigen könnte: keine Bohrung,
    # keinen Baustein, keine Passung. Der Ausweg stand bisher als Nebensatz im
    # Prüfbericht („Netz → Dezimieren"), und niemand ging ihn.
    #
    # Als eigene Transaktion und nicht als stiller Teil der Reparatur: ein
    # Undo nimmt sie zurück, der Stapel zeigt sie, und wer die volle Auflösung
    # braucht, hat sie einen Klick entfernt.
    # **Vollständig, und das war es nicht.** fit_to_size fehlte hier, und
    # damit rollte der erste Rückroller — wer immer die Liste abarbeitet — die
    # Erzeugung nur zu drei Vierteln zurück: Der Körper blieb als Transaktion
    # stehen, auf 100 mm gebracht, ohne die Quelle, aus der er kam. Was in
    # einem Zug entstanden ist, gehört vollständig in die Liste.
    steps = [loading.id, sizing.id, repairing.id]
    if result.mesh.triangle_count > GENERATED_TRIANGLE_LIMIT:
        decimating = history.apply(
            _("Auf Arbeitsauflösung bringen"),
            [
                OperationDraft(
                    op="decimate_mesh",
                    inputs=(object_id,),
                    outputs=(object_id,),
                    params={"triangles": GENERATED_TRIANGLE_TARGET},
                )
            ],
            origin,
        )
        steps.append(decimating.id)

    # **Und zuletzt wieder aufs Bett.** Die Stelle steht seit ``fit_to_size``
    # fest, die Höhe nicht: Die Reparaturkette nimmt lose Krümel weg, und lag
    # einer unter dem Körper, schwebte er danach — gemessen 5,21 mm über dem
    # Bett (Review F8). Aufgesetzt wird deshalb nach der ganzen Kette.
    seating = history.apply(
        _("Auf das Bett setzen"),
        [OperationDraft(op="place_on_bed", inputs=(object_id,), outputs=(object_id,))],
        origin,
    )
    steps.append(seating.id)

    _log.info("generated %s into %s via %s", object_id, source_id, result.backend)
    return Generation(
        source_id=source_id,
        object_id=object_id,
        result=result,
        transactions=tuple(steps),
    )


def _short(name: str) -> str:
    """Ein Prompt ist ein Satz; ein Objektname nicht. Die ersten paar Wörter,
    mehr nicht."""
    words = name.strip().split()
    return " ".join(words[:5]) if words else str(_("Erzeugt"))
