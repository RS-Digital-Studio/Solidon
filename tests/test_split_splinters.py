"""*In Einzelteile aufteilen* an einem Körper, dessen übrige Teile Splitter sind (FD-113).

Am Würfel mit Bruchstück (``two_components.stl``, die Prüfszene
``mehrteilig.netz``) meldet der Prüfbericht zwei Teile, und die Absage sagte
„Der Körper besteht aus einem Stück“: Ohne *Splitter behalten* zählt
``split_bodies`` das Bruchstück nicht mit, und die Vorschläge waren nur
*Eingabe korrigieren* und *Abbrechen*. Die Absage nennt jetzt den Splitter und
bietet den einen Schalter an, der weiterhilft.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from app.core.errors import CANCEL, CORRECT_INPUT, KEEP_SPLINTERS, ValidationError
from app.core.geom.mesh import MeshData, as_mesh_data, read_mesh
from app.core.geom.prepare_ops import ONE_PIECE
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject

MESHES = Path(__file__).parent / "data" / "meshes"


def _split(entry: SceneObject, profile: Profile, **params: object):
    spec = REGISTRY.get("split_bodies")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda *_: None,
            ask=lambda _question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def _cube_with_a_crumb() -> SceneObject:
    """Der Korpus der Prüfszene, geladen wie dort."""
    mesh = normalise(read_mesh((MESHES / "two_components.stl").read_bytes(), ".stl"), "mm").mesh
    assert mesh.component_count == 2, "Vorbedingung: Würfel und Bruchstück"
    return SceneObject(id="obj_1", name="Würfel", mesh=mesh)


def test_a_body_with_splinters_names_them_and_offers_to_keep_them(profile: Profile) -> None:
    entry = _cube_with_a_crumb()

    with pytest.raises(ValidationError) as refusal:
        _split(entry, profile, count=2)

    error = refusal.value
    assert error.detail is not ONE_PIECE, "kein „aus einem Stück“, der Bericht sagt zwei Teile"
    assert "Splitter" in str(error.detail)
    assert error.suggestions == (KEEP_SPLINTERS, CANCEL)
    assert error.values["field"] == "keep_tiny", "der Schritt öffnet am Schalter"
    assert str(KEEP_SPLINTERS.label) == "Splitter behalten"

    kept = _split(entry, profile, count=2, keep_tiny=True)
    volumes = sorted(abs(float(as_mesh_data(part.mesh).volume)) for part in kept.outputs)
    assert len(volumes) == 2
    assert volumes[0] < profile.smallest_printable_volume < volumes[1]


def test_a_body_of_one_piece_still_says_so(profile: Profile) -> None:
    entry = SceneObject(
        id="obj_1", name="Quader", mesh=MeshData.of(trimesh.creation.box((10.0, 10.0, 10.0)))
    )

    with pytest.raises(ValidationError) as refusal:
        _split(entry, profile, count=2)

    assert refusal.value.detail is ONE_PIECE
    assert refusal.value.suggestions == (CORRECT_INPUT, CANCEL)
