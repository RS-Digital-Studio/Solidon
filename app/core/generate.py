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
from app.core.errors import AppError
from app.core.geom.mesh import MeshData, edge_table
from app.core.geom.repair import branching_edge_count, separate_touching_sheets
from app.core.log import get_logger
from app.core.scene.history import History, OperationDraft
from app.core.scene.project import Project, checksum, embedded_source_path, next_source_id
from app.core.types import Mesh, ObjectId, Origin, ProgressFn, Source, SourceId, SourceOrigin
from app.core.units import EPS_GEOM
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
    # Ein Bildmodell meint innen nichts. TRELLIS.2 liefert über ComfyUIs
    # ``RemeshMesh`` (Modus ``udf``) um jede Fläche eine zweite, nach innen
    # gewendete Hülle. Der Ablauf lässt sie stehen, weil sie an einer dünnen
    # Wand die zweite Seite der Wand ist (RM-550); bei einem vollen Körper
    # liegt sie innen und fällt hier — sonst druckte der Slicer einen hohlen
    # Körper mit Wänden von Zehntelmillimetern.
    "inner_shells": True,
}

#: Auf welche längste Kante ein erzeugter Körper gebracht wird.
#:
#: Ein Bildmodell liefert seine Ausgabe auf einem Einheitswürfel — als
#: Millimeter gelesen ein Krümel von ein bis zwei Millimetern. Hundert ist
#: keine Vorhersage, wie groß das Teil werden soll, sondern der Punkt, von dem
#: aus jede Richtung gleich weit ist: ein Möbel im Puppenhausmaßstab liegt
#: darunter, ein Gehäuse darüber, und beides ist ein Schritt.
WORKING_SIZE_MM = 100.0

#: Die Titel, unter denen eine Erzeugung bis RM-372 ihre Schritte als eigene
#: Transaktionen anlegte. Neue Projekte tragen sie nicht mehr; gespeicherte
#: schon (der Titel reist als ``msgid``), und ihr Verlauf soll in jeder
#: Sprache lesbar bleiben — deshalb stehen sie hier für die Kataloge.
EARLIER_TITLES: Final = (
    _("Auf Arbeitsgröße bringen"),
    _("Reparaturkette"),
    _("Auf Arbeitsauflösung bringen"),
)


def working_volume(body: Mesh) -> float:
    """Das Volumen, mit dem ein erzeugter Körper ins Projekt kommt, in mm³.

    Der Generator liefert auf dem Einheitswürfel, und dessen Volumen — ein,
    zwei Kubikmillimeter — hielte der Kunde für einen Krümel, der zwei
    Schritte später hundert Millimeter misst. Gerechnet wird wie in
    ``fit_to_size``: dieselbe Konstante, dasselbe Maß, die längste Kante des
    achsparallelen Hüllquaders. Das Drehen der glTF-Achsen beim Laden
    vertauscht nur Achsen und ändert diese Kante nicht; die Reparaturkette
    danach kann das Volumen noch um ihre Korrekturen verschieben.
    ``tests/test_way_three.py`` hält beide Rechnungen an derselben Antwort.

    Ohne Ausdehnung gibt es keinen Faktor (``fit_to_size`` sagt dann ab); der
    Körper behält sein Volumen, wie es ist.
    """
    longest = max(body.bounds.size)
    if longest <= EPS_GEOM:
        return body.volume
    factor = WORKING_SIZE_MM / longest
    return body.volume * factor * factor * factor


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

#: Ab welchem Anteil von Kanten, an denen nach dem Trennen berührender Stücke
#: noch mehr als zwei Flächen hängen, ein erzeugtes Rohnetz als zerfallen gilt
#: (RM-550).
#:
#: Ein heiles Netz von TRELLIS.2 über ComfyUIs ``RemeshMesh`` (``udf``) hat
#: höchstens ein paar Dutzend solcher Kanten, dort, wo sich zwei Stücke an
#: einer Linie berühren — gemessen 0 bis 0,036 % —, und die Reparatur trennt
#: sie alle (``repair.separate_touching_sheets``). Manche Startwerte zerfallen
#: dagegen schon im Generator: 0,63 bis 3,4 % der Kanten, oft Hunderte Teile,
#: keine davon trennbar, und kein Lauf endete geschlossen. Die Grenze liegt mit
#: Abstand zwischen beiden. Ein Anteil und keine Zahl, weil ein feineres Netz
#: mehr Kanten hat; gezählt wird erst nach dem Trennen, weil ein kleines Netz
#: mit einer einzigen Berührkante sonst schon über dem Anteil läge.
TANGLED_EDGE_SHARE: Final = 0.002


def fell_apart(mesh: Mesh) -> bool:
    """Ob ein erzeugtes Rohnetz schon im Generator zerfallen ist.

    Gefragt wird vor dem Übernehmen, denn der Ausweg ist ein neuer Versuch und
    keine Reparatur. Gezählt wird am Netz, wie es aus dem Generator kommt; ein
    heiles Netz liegt schon vor dem Trennen unter der Grenze und kostet eine
    Kantenzählung, die sich das Netz merkt. Der Dialog fragt im Arbeiter. Ein
    Netz ohne Dreiecke zum Zählen — eine Attrappe mit Kennzahlen — gilt als
    heil.
    """
    if not isinstance(mesh, MeshData):
        return False
    edges = len(edge_table(mesh.raw).counts)
    limit = TANGLED_EDGE_SHARE * edges
    if not edges or branching_edge_count(mesh) < limit:
        return False
    separated, _count = separate_touching_sheets(mesh)
    return branching_edge_count(separated) >= limit


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
    """Kopfloser Prüfweg: Bildbytes zu einem Körper im Projekt.

    Der produktive Dialog lässt ``image_to_mesh`` in seinem Arbeiter laufen und
    übernimmt das Ergebnis über ``Session.add_generated``. Dieser synchrone
    Adapter prüft denselben Kernweg ohne Fenster; ``cancelled`` gilt wie bei
    :func:`from_text`.
    """
    result = backend.image_to_mesh(image, seed=seed, progress=progress, cancelled=cancelled)
    return into_project(project, result, name or str(_("Aus Bild")))


def into_project(project: Project, result: GeneratedMesh, name: str = "") -> Generation:
    """Datei einbetten, laden, auf Maß bringen, reparieren, aufsetzen — als
    **eine** Transaktion, deren Schritte einzeln im Verlauf stehen (§15.5).

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
    # Die Frage vorzuziehen deckt den gemeldeten Fall vollständig: Zwischen
    # hier und dem `apply` ändert sich der Freischaltzustand nicht. Lehnt
    # `apply` aus einem anderen Grund ab, nimmt der Rücknahmepfad unten die
    # Quelle wieder heraus — seit die Erzeugung eine Transaktion ist, ist das
    # eine Zeile. Gefunden von 3d-druck-46 im Lizenz-Audit.
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
    # **Eine Erzeugung ist ein Rückgängig-Schritt** (RM-372, §15.5). Hier
    # standen drei bis vier Transaktionen: Nach dem ersten Strg+Z änderte sich
    # bei einem dichten Netz nichts Sichtbares, nach dem zweiten lag ein
    # Krümel von zwei Millimetern da, erst der dritte nahm das Modell weg. Die
    # Schritte bleiben einzeln im Verlauf und änderbar — nur die Rücknahme
    # nimmt sie zusammen. Der Körper bekommt seine Kennung vorab, damit die
    # Schritte nach dem Laden ihn in derselben Transaktion nennen können.
    object_id = history.next_object_id()
    loading = OperationDraft(
        op="load",
        outputs=(object_id,),
        params={
            "source": source_id,
            "unit": "mm",
            # **Eine erzeugte GLB steht auf glTF-Achsen** (RM-086). Hier stand
            # „Rohachsen", und gemessen war das nie: TripoSG schrieb Y-oben
            # wie jede glTF-Datei — der Drache aus ``image_00001_.glb`` und die
            # vier Puppenhausmöbel tragen ihre Höhe auf Y. TRELLIS.2 rechnet
            # Z-oben, ComfyUIs ``VaeDecodeShapeTrellis`` dreht vor dem
            # Speichern auf Y-oben, also gilt dasselbe. Roh gelesen lag
            # jeder erzeugte Körper auf dem Rücken. Gedreht wird wie beim
            # Import; die Meter der Spezifikation gelten dagegen nicht: Die
            # Einheit bleibt ``mm``, die Größe setzt der eigene Schritt
            # ``fit_to_size`` darunter. Ältere Projekte behalten
            # ``legacy_raw`` über die Migration (24 → 25).
            "coordinates": ("gltf" if result.suffix.lower() in (".glb", ".gltf") else "legacy_raw"),
            "name": short,
            # Beim Laden nichts bereinigen, solange das Modell winzig ist. Die
            # Reparaturkette unten holt jeden dieser Schritte nach — dann aber
            # auf hundert Millimetern, wo dieselben Toleranzen das Richtige
            # treffen.
            #
            # Beide Stufen messen absolut: das Verschweißen sucht Punkte, deren
            # Abstand unter der Toleranz liegt, das Entarten sucht Dreiecke,
            # deren Fläche darunter liegt. Bei zwei Millimetern Modellgröße ist
            # das nicht der Doppelpunkt und nicht die Nadel, sondern die halbe
            # Lehne und achtundachtzig Dreiecke, die die Hülle schließen. Vier
            # von vier erzeugten Netzen gingen hier auf, ohne dass jemand eine
            # Absicht hatte — und danach half nichts mehr: Löcher füllen
            # schließt eine Naht, aber keine, die quer durch das Modell läuft.
            "weld": False,
            "remove_degenerate": False,
            "unify_normals": False,
        },
    )

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
    # kommt — der Befund des Schritts trägt dafür *Größe ändern* (RM-374).
    sizing = OperationDraft(
        op="fit_to_size",
        inputs=(object_id,),
        outputs=(object_id,),
        # **Und erst am fertigen Maß wird gelegt** (Robert, 28.09.2026): Ein
        # erzeugtes Modell ist aus Kundensicht ein weiteres Modell — aufgesetzt
        # an die freie Stelle nächst der Plattenmitte, wie beim Einfügen
        # (§17.1, Schritt 6). In einem leeren Projekt heißt das: mittig auf
        # Platte 1.
        params={"largest": WORKING_SIZE_MM, "free_spot": True},
    )
    repairing = OperationDraft(op="repair", inputs=(object_id,), params=dict(GENERATED_REPAIR))
    # Und ein eigener Schritt, wenn das Netz zu fein ist, um damit zu arbeiten.
    #
    # Ein Generator liefert typisch anderthalb Millionen Dreiecke. Damit hat
    # niemand ein Problem, außer der Merkmalserkennung — sie steigt oberhalb
    # von :data:`GENERATED_TRIANGLE_LIMIT` aus, und ohne Merkmale gibt es
    # nichts, worauf ein Klick oder der Agent zeigen könnte: keine Bohrung,
    # keinen Baustein, keine Passung. Der Ausweg stand bisher als Nebensatz im
    # Prüfbericht („Netz → Dezimieren"), und niemand ging ihn. Als Schritt und
    # nicht als stiller Teil der Reparatur: Der Verlauf zeigt ihn, und wer die
    # volle Auflösung braucht, schaltet ihn aus.
    thinning: tuple[OperationDraft, ...] = ()
    if result.mesh.triangle_count > GENERATED_TRIANGLE_LIMIT:
        thinning = (
            OperationDraft(
                op="decimate_mesh",
                inputs=(object_id,),
                outputs=(object_id,),
                params={"triangles": GENERATED_TRIANGLE_TARGET},
            ),
        )
    # **Und zuletzt wieder aufs Bett.** Die Stelle steht seit ``fit_to_size``
    # fest, die Höhe nicht: Die Reparaturkette nimmt lose Krümel weg, und lag
    # einer unter dem Körper, schwebte er danach — gemessen 5,21 mm über dem
    # Bett (Review F8). Aufgesetzt wird deshalb nach der ganzen Kette.
    seating = OperationDraft(op="place_on_bed", inputs=(object_id,), outputs=(object_id,))
    try:
        made = history.apply(
            _("Modell erzeugen"), [loading, sizing, repairing, *thinning, seating], origin
        )
    except AppError:
        # Abgelehnt heißt: nichts geschrieben — auch die Quelle nicht, die
        # sonst als Waise mit der Anfrage des Kunden ins Projekt reiste.
        del document.sources[source_id]
        project.sources.pop(source_id, None)
        raise

    _log.info("generated %s into %s via %s", object_id, source_id, result.backend)
    return Generation(
        source_id=source_id,
        object_id=object_id,
        result=result,
        transactions=(made.id,),
    )


#: Zeichen, die in keinem Dateinamen stehen dürfen — unter Windows nicht und
#: im Container nicht, wo ``/`` einen Ordner anfängt. Schräg- und Rückstrich
#: werden zum Bruchstrich U+2044.
_FRACTION_SLASH: Final = "\u2044"
_NOT_IN_A_FILENAME: Final = str.maketrans(
    dict.fromkeys('<>:"|?*', " ") | {"/": _FRACTION_SLASH, "\\": _FRACTION_SLASH}
)


def _short(name: str) -> str:
    """Ein Prompt ist ein Satz; ein Objektname nicht. Die ersten paar Wörter,
    mehr nicht.

    Aus dem Ergebnis wird der Dateiname der Quelle, und aus dessen Stamm der
    Objektname. Ein Schrägstrich machte daraus einen Ordner, ein Name nur aus
    Punkten verschluckte die Endung — `load` hielt dann mit „Dieses
    Dateiformat kann nicht gelesen werden.“ (RM-362). Schrägstriche werden
    zum Bruchstrich, damit „1/2 Zoll“ lesbar bleibt.
    """
    cleaned = "".join(
        letter for letter in name.translate(_NOT_IN_A_FILENAME) if letter.isprintable()
    )
    words = cleaned.split()
    short = " ".join(words[:5]).rstrip(". ")
    return short if short.strip(".") else str(_("Erzeugt"))
