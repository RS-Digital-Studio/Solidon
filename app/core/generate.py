"""Way 3: text or image to a body in the scene (Bauplan §2.2, §27).

    Text oder Bild → Mesh → Reparaturkette läuft automatisch → Prüfbericht

Two things about how that is built are worth stating, because both were
decisions and not the obvious route.

**The generated file becomes a source, not an operation.** A generator is not a
function: the same prompt with the same seed gives something else after a model
update. An operation that called it would make every project unreproducible
(§11.3). So the bytes are embedded in the project like a dragged-in file, and
the stack that follows is the ordinary one.

**The repair chain is on the stack, not baked into the body.** Way 3 says it
runs automatically, and it does — but as its own step, so the report can say
what it changed, and so it can be taken back when it took away something that
was meant to be there (§11.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.backends.mesh import GeneratedMesh, MeshBackend
from app.core.log import get_logger
from app.core.scene.history import History, OperationDraft
from app.core.scene.project import Project, embedded_source_path
from app.core.types import ObjectId, Origin, ProgressFn, Source, SourceId, SourceOrigin
from app.i18n import _, tr

_log = get_logger(__name__)

#: The repair chain for a generated body (§25). Everything is on, including the
#: two steps the import stage leaves off: a generated mesh brings stray
#: fragments and self-intersections as standard, and unlike a part somebody
#: modelled there is no intent in them worth preserving.
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
    """What way 3 produced: the source, the object, and how it got there."""

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
    """Generate a body from a description and put it into the project."""
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
    """Generate a body from a picture and put it into the project."""
    result = backend.image_to_mesh(image, seed=seed, progress=progress)
    return into_project(project, result, name or str(_("Aus Bild")))


def into_project(project: Project, result: GeneratedMesh, name: str = "") -> Generation:
    """Embed the file, load it, repair it — two steps in the history, both undoable.

    Separate from the two calls above so a surface that already has a result —
    because it ran the generator on its own thread — takes the same way in.
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
    # The user pressed generate, so the transaction is theirs (§26.4). Which
    # generator it was belongs to the source, where it stays readable.
    origin = Origin(by="user")
    loading = history.apply(
        tr("Modell erzeugen"),
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
        tr("Reparaturkette"),
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
    """A prompt is a sentence; an object name is not. First few words, no more."""
    words = name.strip().split()
    return " ".join(words[:5]) if words else str(_("Erzeugt"))
