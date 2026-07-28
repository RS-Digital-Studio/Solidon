"""Against models somebody actually printed (Bauplan §34, §35).

The reference corpus is built to hit one thing each and stays small. What it
cannot bring is the shape nobody thinks to construct: a community model with a
million triangles in forty-one pieces, a 3MF exported by a slicer, a scan.

The folder is not part of the repository, so these tests skip themselves when
it is not there. That is deliberate — a suite that fails on a machine without
somebody's private model folder would be a suite people stop running.

    python tools/run_model_suite.py "F:/3D Druck/3D Drucker"

is the same walk with a report instead of assertions; this file keeps the
handful of findings that came out of it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import HEAVY_TRIANGLES, normalise
from app.core.perceive.features import detect
from app.core.slice.analysis import slice_body

MODELS = Path("F:/3D Druck/3D Drucker")

pytestmark = pytest.mark.skipif(not MODELS.is_dir(), reason="the model folder is not here")

#: Small, closed, and nothing special — the shape most prints actually are.
PLAIN = "Getraenkehalter_Pool_ThreeSixty.stl"

#: A million triangles in forty-one pieces, as it came off a community site.
HEAVY = "Cat_Toys_V2.3mf"


def find(name: str) -> Path:
    found = [entry for entry in MODELS.rglob(name)]
    if not found:
        pytest.skip(f"{name} is not in the folder")
    return found[0]


def load(name: str):
    path = find(name)
    return normalise(read_mesh(path.read_bytes(), path.suffix), "mm")


def test_a_plain_printed_part_goes_through_without_a_complaint() -> None:
    result = load(PLAIN)

    assert result.mesh.is_watertight
    assert result.mesh.triangle_count > 0
    severe = [entry for entry in result.findings if entry.severity == "error"]
    assert not severe, [entry.code for entry in severe]


def test_a_very_fine_model_is_told_it_is_one() -> None:
    """The finding this corpus produced: a million triangles used to be silent.

    Not refused — the limit for that is twenty million (§17.1). But every map
    and the feature detection turn a model this size away, so being handed one
    and saying nothing left people waiting for something that was never coming.
    """
    result = load(HEAVY)

    assert result.mesh.triangle_count > HEAVY_TRIANGLES
    codes = {entry.code for entry in result.findings}
    assert "ingest.very_large" in codes
    assert "ingest.multiple_components" in codes, "forty-one pieces, and it says so"


def test_a_model_in_many_pieces_keeps_all_of_them() -> None:
    """§17.1: small components are reported, never dropped."""
    result = load(HEAVY)

    assert result.info.components > 1
    assert result.mesh.triangle_count > 0


def test_the_layer_analysis_holds_on_a_real_part() -> None:
    mesh = load(PLAIN).mesh

    sliced = slice_body(mesh, 0.2)

    assert sliced.layers, "a body with height has layers"
    assert sliced.support_volume >= 0.0
    assert sliced.layers[0].area > 0.0


def test_feature_detection_survives_a_real_part() -> None:
    """It may find nothing — what it must not do is fall over."""
    mesh = load(PLAIN).mesh

    found = detect(mesh)

    assert isinstance(found, dict)
