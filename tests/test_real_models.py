"""Gegen Modelle, die jemand wirklich gedruckt hat (Bauplan §34, §35).

Der Referenzkorpus ist gebaut, um je eine Sache zu treffen, und bleibt klein.
Was er nicht mitbringen kann, ist die Form, auf die niemand kommt, wenn er
konstruiert: ein Community-Modell mit einer Million Dreiecken in einundvierzig
Stücken, eine von einem Slicer exportierte 3MF, ein Scan.

Der Ordner ist nicht Teil des Repositorys, diese Tests überspringen sich also,
wenn es ihn nicht gibt. Das ist Absicht — eine Suite, die auf einer Maschine
ohne jemandes privaten Modellordner scheitert, wäre eine Suite, die Leute
aufhören zu benutzen.

    python tools/run_model_suite.py "F:/3D Druck/3D Drucker"

ist derselbe Durchlauf mit einem Bericht statt Zusicherungen; diese Datei hält
die Handvoll Funde fest, die dabei herauskamen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.export import threemf
from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import HEAVY_TRIANGLES, normalise
from app.core.perceive.features import detect
from app.core.slice.analysis import slice_body

MODELS = Path("F:/3D Druck/3D Drucker")

pytestmark = pytest.mark.skipif(not MODELS.is_dir(), reason="the model folder is not here")

#: Klein, geschlossen und nichts Besonderes — die Form, die die meisten
#: Drucke wirklich haben.
PLAIN = "Getraenkehalter_Pool_ThreeSixty.stl"

#: Eine Million Dreiecke in einundvierzig Stücken, wie sie von einer
#: Community-Seite kam.
HEAVY = "Cat_Toys_V2.3mf"


def find(name: str) -> Path:
    found = list(MODELS.rglob(name))
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
    """Der Fund, den dieser Korpus erbrachte: eine Million Dreiecke war früher
    still.

    Nicht abgelehnt — die Grenze dafür sind zwanzig Millionen (§17.1). Aber
    jede Karte und die Merkmalserkennung weisen ein Modell dieser Größe ab —
    eines gereicht zu bekommen und nichts zu sagen ließ Leute also auf etwas
    warten, das nie kam.
    """
    result = load(HEAVY)

    assert result.mesh.triangle_count > HEAVY_TRIANGLES
    codes = {entry.code for entry in result.findings}
    assert "ingest.very_large" in codes
    assert "ingest.multiple_components" in codes, "forty-one pieces, and it says so"


def test_a_model_in_many_pieces_keeps_all_of_them() -> None:
    """§17.1: kleine Komponenten werden gemeldet, nie verworfen."""
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
    """Sie darf nichts finden — was sie nicht darf, ist umfallen."""
    mesh = load(PLAIN).mesh

    found = detect(mesh)

    assert isinstance(found, dict)


# --- Eine Slicer-3MF ist eine Baugruppe, und sie wurde vielfach gelesen ---------


def test_the_pool_waterfall_arrives_as_its_four_parts() -> None:
    """Das Projekt, aus dem dieses Feature kam: Gehäuse, Deckel, Tülle,
    TPU-Liner.

    Zu einem Körper verschweißt kann der Liner sein eigenes Material nicht
    bekommen (§12), und kein Teil kann auf seine eigene Platte (§25) — die
    Teilung ist der Sinn der Datei.
    """
    parts = threemf.read_objects(find("Wasserfall_.3mf").read_bytes())

    assert [part.name for part in parts] == [
        "Wasserfall_1_Koerper",
        "Wasserfall_2_Deckel",
        "Wasserfall_3_Tuelle",
        "Wasserfall_4_TPU-Liner",
    ]
    assert all(part.mesh.is_watertight for part in parts)


def test_a_nozzle_of_two_bodies_is_not_read_as_four() -> None:
    """Die gemessene Regression: jeder Körper kam einmal je Komponente an."""
    parts = threemf.read_objects(find("Pool-Fountain_Nozzle_horizontal.3mf").read_bytes())

    assert len(parts) == 2
    assert sum(part.mesh.triangle_count for part in parts) == 290_120
    assert sum(abs(part.mesh.volume) for part in parts) / 1000.0 == pytest.approx(52.05, abs=0.05)


def test_seventeen_parts_in_one_object_file_stay_seventeen() -> None:
    """Der schlimmste Fall des Korpus: 787 836 Dreiecke als 13 393 212
    gelesen.

    Siebzehn Komponenten, alle in eine externe Modelldatei zeigend, jede von
    ihnen zur ganzen Datei aufgelöst — siebzehnmal alles.
    """
    parts = threemf.read_objects(find("Cat_Phone_Stand_Kawaii_material.3mf").read_bytes())

    assert len(parts) == 17
    assert sum(part.mesh.triangle_count for part in parts) == 787_836


def test_the_count_is_right_before_the_geometry_is_read() -> None:
    """§11: der Stapel vergibt zuerst die IDs, die Anzahl darf also keine
    Vermutung sein.
    """
    for name in ("Wasserfall_.3mf", "Gewürz.3mf", "Taschentuchbox_material.3mf"):
        payload = find(name).read_bytes()
        assert threemf.count_objects(payload) == len(threemf.read_objects(payload)), name
