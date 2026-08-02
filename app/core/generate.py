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

from app.core.backends.mesh import GeneratedMesh, MeshBackend
from app.core.log import get_logger
from app.core.scene.history import History, OperationDraft
from app.core.scene.project import Project, embedded_source_path
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


def _silent(fraction: float, text: str) -> None:
    del fraction, text


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
) -> Generation:
    """Erzeugt einen Körper aus einer Beschreibung und legt ihn ins Projekt."""
    result = backend.text_to_mesh(prompt, seed=seed, progress=progress)
    return into_project(project, result, name or prompt)


def from_image(
    project: Project,
    backend: MeshBackend,
    image: bytes,
    *,
    seed: int = 0,
    name: str = "",
    progress: ProgressFn = _silent,
) -> Generation:
    """Erzeugt einen Körper aus einem Bild und legt ihn ins Projekt."""
    result = backend.image_to_mesh(image, seed=seed, progress=progress)
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
    source_id = f"src_{len(document.sources) + 1}"
    short = _short(name)

    document.sources[source_id] = Source(
        id=source_id,
        kind="generated",
        path=embedded_source_path(f"{short}{result.suffix}"),
        sha256="",
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
                params={"source": source_id, "unit": "mm", "name": short},
            )
        ],
        origin,
    )
    object_id = document.ops[-1].outputs[0]

    repairing = history.apply(
        _("Reparaturkette"),
        [OperationDraft(op="repair", inputs=(object_id,), params=dict(GENERATED_REPAIR))],
        origin,
    )
    _log.info("generated %s into %s via %s", object_id, source_id, result.backend)
    return Generation(
        source_id=source_id,
        object_id=object_id,
        result=result,
        transactions=(loading.id, repairing.id),
    )


def _short(name: str) -> str:
    """Ein Prompt ist ein Satz; ein Objektname nicht. Die ersten paar Wörter,
    mehr nicht."""
    words = name.strip().split()
    return " ".join(words[:5]) if words else str(_("Erzeugt"))
