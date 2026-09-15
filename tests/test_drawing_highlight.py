"""Auswahlmarkierungen bleiben auf sichtbaren Körperflächen und ändern keine Kameralage."""

import numpy as np

from app.core import drawing
from app.core.knowledge.parts.shapes import box


def test_default_and_invalid_selection_keep_existing_svg_identical():
    raw = box(30, 20, 10).raw
    plain = drawing.project(raw, edges=True)
    assert drawing.project(raw, edges=True, highlight_faces=()) == plain
    assert drawing.project(raw, edges=True, highlight_faces=(-1, len(raw.faces), 100000)) == plain


def test_selected_front_face_gets_contour_and_escaped_label_without_moving_camera():
    raw = box(30, 20, 10).raw
    normals = raw.face_normals @ drawing.camera(-35, 25).T
    visible = int(np.flatnonzero(normals[:, 2] > 0)[0])
    plain = drawing.project(raw, edges=True)
    marked = drawing.project(
        raw, edges=True, highlight_faces=(visible,), highlight_label="Wand <1>"
    )
    assert "Wand &lt;1&gt;" in marked
    assert 'data-highlight="true"' in marked
    assert 'data-selection-contour="true"' in marked
    assert plain.split('points="')[1].split('"')[0] == marked.split('points="')[1].split('"')[0]


def test_hidden_back_faces_do_not_shine_through_the_body():
    raw = box(30, 20, 10).raw
    normals = raw.face_normals @ drawing.camera(-35, 25).T
    hidden = tuple(map(int, np.flatnonzero(normals[:, 2] < 0)))
    assert drawing.project(raw, edges=True, highlight_faces=hidden) == drawing.project(
        raw, edges=True
    )
