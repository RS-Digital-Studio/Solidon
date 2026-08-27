"""Von einer Textur zu druckbaren Slots (Bauplan §20).

Ein erzeugter Körper kommt mit einer Textur aus tausenden Farben an; ein
Drucker hat vier, oder fünf, oder eine. Der Weg vom einen zum anderen ist der,
den §20 benennt: auf die Dreiecke zurückprojizieren, auf die Zahl der
geladenen Filamente quantisieren, gegen Einzeldreieck-Sprenkel glätten, als
Slots ablegen.

Die Quantisierung ist k-Means, **mit gespeichertem Startwert**. Genau darum
steht sie hier ausgeschrieben statt aus einer Bibliothek mit globalem
Zufallszustand geholt: dasselbe Modell mit demselben Startwert muss gleich
herauskommen, sonst beschreibt die Datei das Teil nicht mehr (§11.3).

Und sie ist nie so fein wie die Darstellung. Zwei Farben, die ein Bildschirm
auseinanderhält, landen im selben Filament — und die Operation sagt das,
statt so zu tun als nicht.
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

#: Wie oft die Zentren bewegt werden, bevor das Ergebnis als eingependelt
#: gilt. Der Farbraum ist klein und k winzig; das konvergiert lange vor dem
#: Ende.
ROUNDS = 20

#: Wie oft der Sprenkelfilter läuft. Zweimal erwischt ein Paar verirrter
#: Dreiecke nebeneinander; mehr fängt an, echtes Detail zu fressen.
SMOOTH_ROUNDS = 2

#: Unter diesem Anteil der Oberfläche ist eine Farbe keinen Filamentwechsel
#: wert.
MIN_SHARE = 0.002


@dataclass(frozen=True, slots=True)
class Quantisation:
    """Die Zuordnung und die Farben, auf die sie sich eingependelt hat."""

    labels: np.ndarray
    centres: np.ndarray

    @property
    def count(self) -> int:
        return len(self.centres)


def face_colours(mesh: trimesh.Trimesh) -> np.ndarray | None:
    """Eine Farbe je Dreieck, in 0..1 — oder ``None``, wenn der Körper keine
    hat.

    Abgetastet in der Mitte des Dreiecks statt aus seinen Ecken gemittelt: an
    der Grenze zwischen zwei Farben erfindet der Eckmittelwert eine dritte,
    die es weder in der Textur noch in der Filamentschublade gibt.
    """
    visual: Any = mesh.visual
    kind = getattr(visual, "kind", None)
    if kind is None:
        return None

    if kind == "texture":
        sampled = _sample_texture(mesh)
        if sampled is not None:
            return sampled
        # Eine Textur ohne verbliebenes Bild: trimesh kann aus den UVs immer
        # noch Farben je Eckpunkt machen, und das ist besser als gar keine.
        visual = visual.to_color()

    colours = np.asarray(getattr(visual, "face_colors", ()), dtype=float)
    if len(colours) != len(mesh.faces):
        return None
    return colours[:, :3] / 255.0


def _sample_texture(mesh: trimesh.Trimesh) -> np.ndarray | None:
    """Liest das Bild an der UV-Mitte jedes Dreiecks."""
    material = getattr(mesh.visual, "material", None)
    image = getattr(material, "image", None)
    uv = getattr(mesh.visual, "uv", None)
    if image is None or uv is None or len(uv) != len(mesh.vertices):
        return None

    picture = np.asarray(image.convert("RGB"), dtype=float) / 255.0
    height, width = picture.shape[:2]

    middle = np.asarray(uv, dtype=float)[mesh.faces].mean(axis=1)
    # UV läuft von unten links, Bildzeilen von oben links.
    columns = np.clip((middle[:, 0] % 1.0) * width, 0, width - 1).astype(int)
    rows = np.clip((1.0 - middle[:, 1] % 1.0) * height, 0, height - 1).astype(int)
    return np.asarray(picture[rows, columns], dtype=float)


def quantise(colours: np.ndarray, count: int, seed: int) -> Quantisation:
    """k-Means über die Dreiecksfarben, reproduzierbar für ein gegebenes
    ``seed``.

    Weniger verschiedene Farben als Filamente ist kein Fehlschlag — es ist ein
    Körper, der drei Filamente braucht, und dann sind drei die Antwort.
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
    """k-Means++-Start, gezogen aus einem gesetzten Generator und sonst
    nichts.

    Die ersten Zentren auseinanderzuziehen zählt hier mehr als irgendwo
    sonst: mit zufälligem Start landen zwei Filamente im selben Grauton, und
    das Modell kommt mit einer Farbe weniger heraus, als der Drucker geladen
    hat.
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
    """Nimmt die Farben weg, denen kein Nachbar zustimmt.

    Ein einzelnes Dreieck in eigener Farbe ist kein Detail, das ein Drucker
    halten kann — es ist ein Filamentwechsel für eine Fläche kleiner als die
    Düse. Angefasst werden nur Dreiecke, die *allen* ihren Nachbarn
    widersprechen; eine echte Grenze hat auf einer Seite Dreiecke ihrer
    eigenen Farbe und überlebt.
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
    """Der ganze Weg aus §20: Textur hinein, Slots und Filamentfarben
    heraus.

    Gibt den Körper unverändert zurück, wenn er gar keine Farbe trägt — ein
    graues STL bleibt ein graues STL, statt Farben zu bekommen, die es nie
    hatte.
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
    """Wirft die Slots weg, die einen Filamentwechsel für nichts kosteten.

    Gemessen an der Fläche, nicht an der Dreieckszahl: ein feines Netz legt
    tausend Dreiecke in einen Fleck von Fingernagelgröße, ein grobes ein
    Dreieck über das halbe Teil.
    """
    areas = np.asarray(mesh.area_faces, dtype=float)
    total = float(areas.sum()) or 1.0
    share = np.array([areas[labels == index].sum() / total for index in range(len(centres))])
    keep = np.flatnonzero(share >= MIN_SHARE)
    if len(keep) == len(centres) or not len(keep):
        return labels, centres
    return _assign(colours, centres[keep]), centres[keep]
