"""Die Körpervorschau zeigt steigende Modellhöhen nach oben im Bild."""

from xml.etree import ElementTree as ET

import numpy as np
import pytest
import trimesh

from app.core import drawing


@pytest.mark.parametrize("around", [-35.0, 0.0, 55.0])
@pytest.mark.parametrize("down", [8.0, 25.0, 55.0, 85.0])
def test_a_higher_triangle_appears_above_its_lower_copy(around, down):
    """Zwei gleiche Flächen unterscheiden sich allein in ihrer Modellhöhe."""
    base = np.array([(0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (0.0, 2.0, 0.0)])
    raw = trimesh.Trimesh(
        vertices=np.vstack((base, base + np.array([0.0, 0.0, 20.0]))),
        faces=[(0, 1, 2), (3, 4, 5)],
        process=False,
    )
    root = ET.fromstring(drawing.project(raw, around=around, down=down))
    triangles = root.findall("{http://www.w3.org/2000/svg}polygon")
    assert len(triangles) == 2
    lower, upper = (
        np.array([tuple(map(float, point.split(","))) for point in entry.attrib["points"].split()])
        for entry in triangles
    )
    assert np.allclose(upper[:, 0], lower[:, 0])
    assert np.all(upper[:, 1] < lower[:, 1])


def test_a_side_view_keeps_world_z_up_and_world_x_right():
    """Die Vorschau spiegelt weder links/rechts noch die Körperhöhe."""
    matrix = drawing.camera(0.0, 90.0)
    assert np.allclose(matrix @ (1.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    assert np.allclose(matrix @ (0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
    assert np.linalg.det(matrix) == pytest.approx(1.0)
