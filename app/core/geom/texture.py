"""From a texture to printable slots (Bauplan §20).

A generated body arrives with a texture of thousands of colours; a printer has
four, or five, or one. The way from the one to the other is the one §20 names:
back-project onto the triangles, quantise onto the number of filaments loaded,
smooth against single-triangle speckle, store as slots.

The quantisation is k-Means, **with a stored starting value**. That is the whole
reason it is written out here rather than pulled from a library with a global
random state: the same model with the same seed has to come out the same way,
or the file does not describe the part any more (§11.3).

And it is never as fine as the render. Two colours that a screen keeps apart end
up in the same filament, and the operation says so rather than pretending.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import MaterialSlot
from app.i18n import tr

_log = get_logger(__name__)

#: How often the centres are moved before the result is called settled. Colour
#: space is small and k is tiny; this converges long before it runs out.
ROUNDS = 20

#: How often the speckle filter runs. Twice catches a pair of stray triangles
#: sitting next to each other; more than that starts eating real detail.
SMOOTH_ROUNDS = 2

#: Below this share of the surface a colour is not worth a filament change.
MIN_SHARE = 0.002


@dataclass(frozen=True, slots=True)
class Quantisation:
    """The assignment and the colours it settled on."""

    labels: np.ndarray
    centres: np.ndarray

    @property
    def count(self) -> int:
        return len(self.centres)


def face_colours(mesh: trimesh.Trimesh) -> np.ndarray | None:
    """One colour per triangle, in 0..1 — or ``None`` when the body has none.

    Sampled at the centre of the triangle rather than averaged from its
    corners: on the boundary between two colours the corner average invents a
    third one that is in neither the texture nor the filament drawer.
    """
    visual: Any = mesh.visual
    kind = getattr(visual, "kind", None)
    if kind is None:
        return None

    if kind == "texture":
        sampled = _sample_texture(mesh)
        if sampled is not None:
            return sampled
        # A texture without an image left: trimesh can still turn the UVs into
        # per-vertex colours, and that is better than no colour at all.
        visual = visual.to_color()

    colours = np.asarray(getattr(visual, "face_colors", ()), dtype=float)
    if len(colours) != len(mesh.faces):
        return None
    return colours[:, :3] / 255.0


def _sample_texture(mesh: trimesh.Trimesh) -> np.ndarray | None:
    """Read the image at the UV centre of every triangle."""
    material = getattr(mesh.visual, "material", None)
    image = getattr(material, "image", None)
    uv = getattr(mesh.visual, "uv", None)
    if image is None or uv is None or len(uv) != len(mesh.vertices):
        return None

    picture = np.asarray(image.convert("RGB"), dtype=float) / 255.0
    height, width = picture.shape[:2]

    middle = np.asarray(uv, dtype=float)[mesh.faces].mean(axis=1)
    # UV runs from the bottom left, image rows from the top left.
    columns = np.clip((middle[:, 0] % 1.0) * width, 0, width - 1).astype(int)
    rows = np.clip((1.0 - middle[:, 1] % 1.0) * height, 0, height - 1).astype(int)
    return np.asarray(picture[rows, columns], dtype=float)


def quantise(colours: np.ndarray, count: int, seed: int) -> Quantisation:
    """k-Means over the triangle colours, reproducible for a given ``seed``.

    Fewer distinct colours than filaments is not a failure — it is a body that
    needs three filaments, and then three is the answer.
    """
    if count < 1:
        raise ValueError("a quantisation needs at least one colour")

    distinct = np.unique(colours, axis=0)
    if len(distinct) <= count:
        return Quantisation(labels=_assign(colours, distinct), centres=distinct)

    centres = _starting_centres(colours, count, seed)
    labels = _assign(colours, centres)
    for _round in range(ROUNDS):
        moved = np.stack(
            [
                colours[labels == index].mean(axis=0) if np.any(labels == index) else centre
                for index, centre in enumerate(centres)
            ]
        )
        if np.allclose(moved, centres):
            break
        centres = moved
        labels = _assign(colours, centres)
    return Quantisation(labels=labels, centres=centres)


def _starting_centres(colours: np.ndarray, count: int, seed: int) -> np.ndarray:
    """k-Means++ start, drawn from one seeded generator and nothing else.

    Spreading the first centres apart matters more here than anywhere: with a
    random start two filaments can land in the same shade of grey and the model
    comes out with one colour fewer than the printer has loaded.
    """
    generator = np.random.default_rng(seed)
    chosen = [colours[int(generator.integers(len(colours)))]]
    while len(chosen) < count:
        gap = np.min(
            ((colours[:, None, :] - np.asarray(chosen)[None, :, :]) ** 2).sum(axis=2), axis=1
        )
        total = float(gap.sum())
        if total <= 0.0:
            break
        chosen.append(colours[int(generator.choice(len(colours), p=gap / total))])
    return np.asarray(chosen)


def _assign(colours: np.ndarray, centres: np.ndarray) -> np.ndarray:
    distance = ((colours[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
    return np.asarray(distance.argmin(axis=1), dtype=np.int32)


def smooth(mesh: trimesh.Trimesh, labels: np.ndarray, rounds: int = SMOOTH_ROUNDS) -> np.ndarray:
    """Take away the colours no neighbour agrees with.

    A single triangle in its own colour is not a detail a printer can hold — it
    is a filament change for a surface smaller than the nozzle. Only triangles
    that disagree with *all* their neighbours are touched; a real boundary has
    triangles of its own colour on one side and survives.
    """
    adjacency = np.asarray(mesh.face_adjacency)
    if not len(adjacency) or not len(labels):
        return labels

    pairs = np.vstack([adjacency, adjacency[:, ::-1]])
    result = labels.copy()
    width = int(result.max()) + 1
    for _round in range(rounds):
        neighbours = np.zeros((len(result), width), dtype=np.int32)
        np.add.at(neighbours, (pairs[:, 0], result[pairs[:, 1]]), 1)
        alone = neighbours[np.arange(len(result)), result] == 0
        if not alone.any():
            break
        result[alone] = neighbours.argmax(axis=1)[alone]
    return result


def to_slots(mesh: MeshData, count: int, seed: int) -> tuple[MeshData, list[MaterialSlot]]:
    """The whole way of §20: texture in, slots and filament colours out.

    Returns the body unchanged when it carries no colour at all — a grey STL
    stays a grey STL rather than being given colours it never had.
    """
    colours = face_colours(mesh.raw)
    if colours is None:
        return mesh, []

    quantised = quantise(colours, count, seed)
    labels = smooth(mesh.raw, quantised.labels)
    labels, centres = _drop_the_negligible(mesh.raw, labels, quantised.centres, colours)

    slots = [
        MaterialSlot(
            index=index,
            name=f"{tr('Farbe')} {index + 1}",
            colour=(float(centre[0]), float(centre[1]), float(centre[2])),
        )
        for index, centre in enumerate(centres)
    ]
    _log.info("quantised %d faces onto %d slot(s)", len(labels), len(slots))
    return MeshData(raw=mesh.raw, slots=tuple(int(entry) for entry in labels)), slots


def _drop_the_negligible(
    mesh: trimesh.Trimesh, labels: np.ndarray, centres: np.ndarray, colours: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Throw away the slots that would cost a filament change for nothing.

    Measured by area, not by triangle count: a fine mesh can put a thousand
    triangles into a patch the size of a fingernail, and a coarse one one
    triangle across half the part.
    """
    areas = np.asarray(mesh.area_faces, dtype=float)
    total = float(areas.sum()) or 1.0
    share = np.array([areas[labels == index].sum() / total for index in range(len(centres))])
    keep = np.flatnonzero(share >= MIN_SHARE)
    if len(keep) == len(centres) or not len(keep):
        return labels, centres
    return _assign(colours, centres[keep]), centres[keep]
