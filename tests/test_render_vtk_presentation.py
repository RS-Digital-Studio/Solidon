"""Sichtbare Präsentation und lesbare, zum Text ausgerichtete VTK-Beschriftungen."""

from types import SimpleNamespace

import numpy as np
import pytest

from app.ui.render.api import CameraPose, LabelStyle, SurfaceStyle, rgb
from app.ui.render.vtk_renderer import VtkRenderer


def test_swap_control_waits_for_visible_context_and_is_configured_once():
    """Versteckter Aufbau bleibt möglich; sichtbare Bilder konfigurieren nur einmal."""
    calls = []
    shown = [False]
    renderer = VtkRenderer.__new__(VtkRenderer)
    renderer._presentation_configured = False
    renderer.widget = SimpleNamespace(isVisible=lambda: shown[0])
    renderer.window = SimpleNamespace(
        Render=lambda: calls.append("render"),
        MakeCurrent=lambda: calls.append("current"),
        SetSwapControl=lambda value: calls.append(("swap", value)),
    )
    renderer.render()
    assert calls == ["render"]
    shown[0] = True
    renderer.render()
    renderer.render()
    assert calls == ["render", "render", "current", ("swap", 0), "render"]


def test_window_without_swap_control_keeps_rendering():
    """Ein abweichender VTK-Fenstertyp bleibt ohne Plattformfunktion benutzbar."""
    calls = []
    renderer = VtkRenderer.__new__(VtkRenderer)
    renderer._presentation_configured = False
    renderer.widget = SimpleNamespace(isVisible=lambda: True)
    renderer.window = SimpleNamespace(Render=lambda: calls.append("render"))
    renderer.render()
    renderer.render()
    assert calls == ["render", "render"]


def test_offscreen_and_other_platforms_keep_their_presentation():
    """Der schon abgeschlossene Plattformpfad greift nicht in den Kontext ein."""
    calls = []
    renderer = VtkRenderer.__new__(VtkRenderer)
    renderer._presentation_configured = True
    renderer.widget = None
    renderer.window = SimpleNamespace(Render=lambda: calls.append("render"))
    renderer.render()
    assert calls == ["render"]


@pytest.mark.parametrize("antialias", [False, True])
def test_occlusion_preserves_the_gradient_through_resize_and_disable(antialias):
    """Eine wirkliche deckende Fläche aktiviert SSAO, ohne den Hintergrund zu ersetzen."""
    from tests.test_render_vtk import cube

    renderer = VtkRenderer(offscreen=True, size=(400, 300))
    try:
        renderer.add_surface(*cube(), name="body", style=SurfaceStyle())
        renderer.set_camera_pose(CameraPose((10, 10, 100), (10, 10, 0), (0, 1, 0)))
        renderer.set_background("#203040", top="#e0f0ff")
        renderer.set_anti_aliasing(antialias)
        for size in ((400, 300), (360, 240)):
            renderer.window.SetSize(*size)
            renderer.set_ambient_occlusion(False, radius=5, bias=0.01)
            plain = renderer.screenshot()
            renderer.set_ambient_occlusion(True, radius=5, bias=0.01)
            shaded = renderer.screenshot()
            samples = ((12, 12), (size[1] // 2, 12), (size[1] - 13, 12))
            for y, x in samples:
                assert shaded[y, x] == pytest.approx(plain[y, x], abs=2)
            assert shaded[12, 12].sum() > shaded[-13, 12].sum() + 300
            renderer.set_ambient_occlusion(False, radius=5, bias=0.01)
            assert np.array_equal(renderer.screenshot(), plain)
    finally:
        renderer.close()


def test_occlusion_keeps_distant_planes_clean_and_contact_shading_visible():
    """Die begrenzte Pufferpräzision einer fernen Kamera darf keine Platte abdunkeln."""
    from tests.test_render_vtk import cube

    renderer = VtkRenderer(offscreen=True, size=(500, 400))
    try:
        plane = renderer.add_surface(
            np.asarray([[-80, -80, 0], [80, -80, 0], [80, 80, 0], [-80, 80, 0]]),
            np.asarray([[0, 1, 2], [0, 2, 3]]),
            name="plane",
            style=SurfaceStyle(colour="#808080", ambient=1, diffuse=0, specular=0),
        )
        renderer.add_surface(*cube(), name="body", style=SurfaceStyle())
        renderer.set_camera_pose(CameraPose((300, -300, 220), (0, 0, 0), (0, 0, 1)))
        renderer.reset_clipping_range()

        def sample(image, point):
            x, y, _depth = renderer.world_to_display(point)
            return image[round(y), round(x), :3].astype(float)

        far_points = [(x, -40.0, 0.0) for x in (-40.0, -20.0, 0.0, 20.0, 40.0)]
        contact_points = [(x, -2.0, 0.0) for x in (5.0, 10.0, 15.0)]
        plain = renderer.screenshot()
        x, y, _depth = renderer.world_to_display(far_points[2])
        before_pick = renderer.pick_surface(x, y)
        assert before_pick is not None and before_pick.item is plane
        renderer.set_ambient_occlusion(True, radius=5.0, bias=0.01)
        shaded = renderer.screenshot()
        for point in far_points:
            assert sample(shaded, point) == pytest.approx(sample(plain, point), abs=2)
        contact_darkening = [
            float(np.mean(sample(plain, point) - sample(shaded, point))) for point in contact_points
        ]
        assert max(contact_darkening) > 5, "AO must still darken the plane beside the body"
        after_pick = renderer.pick_surface(x, y)
        assert after_pick is not None and after_pick.item is plane
        assert after_pick.cell == before_pick.cell
        assert after_pick.point == pytest.approx(before_pick.point)
    finally:
        renderer.close()


def test_occlusion_switches_antialiasing_and_preserves_translucency_and_labels():
    """Der eigene Pass erhält OIT, Textüberlagerungen und die echte FXAA-Umschaltung."""
    renderer = VtkRenderer(offscreen=True, size=(320, 240))
    try:
        vertices = np.asarray([[-12, -9, 0], [12, -5, 0], [8, 9, 0], [-10, 7, 0]])
        faces = np.asarray([[0, 1, 2], [0, 2, 3]])
        for name, colour, height, opacity in (
            ("back", "#00ff00", -2, 0.5),
            ("body", "#0000ff", 0, 1),
            ("front", "#ff0000", 2, 0.5),
        ):
            renderer.add_surface(
                vertices + np.asarray((0, 0, height)),
                faces,
                name=name,
                style=SurfaceStyle(
                    colour=colour, opacity=opacity, ambient=1, diffuse=0, specular=0
                ),
            )
        renderer.add_labels(
            np.asarray([[7, 5, 3]]),
            ["HH  HH"],
            name="label",
            style=LabelStyle(
                font_size=16,
                text_colour="#00ff00",
                background="#ffffff",
                background_opacity=1,
                margin=5,
            ),
        )
        renderer.set_background("#555555")
        renderer.set_camera_pose(CameraPose((0, 0, 50), (0, 0, 0), (0, 1, 0)))
        renderer.set_parallel_projection(True)
        renderer.set_parallel_scale(15)
        renderer.set_anti_aliasing(False)
        plain = renderer.screenshot()
        renderer.set_ambient_occlusion(True, radius=1, bias=0.01)
        aliased = renderer.screenshot()
        assert aliased[120, 160, :3] == pytest.approx((128, 0, 128), abs=2)
        ink = np.all(plain[:, :, :3] == (0, 255, 0), axis=2)
        # Bei 16 Punkt sind nur die Querbalken der vier H rein grün; die
        # Stämme sind kantengeglättet. Gemessen: 28 Bildpunkte in einer Zeile.
        assert np.count_nonzero(ink) > 16
        assert np.array_equal(ink, np.all(aliased[:, :, :3] == (0, 255, 0), axis=2))
        renderer.set_anti_aliasing(True)
        smoothed = renderer.screenshot()
        assert not np.array_equal(smoothed, aliased)
        assert np.array_equal(ink, np.all(smoothed[:, :, :3] == (0, 255, 0), axis=2))
        renderer.set_anti_aliasing(False)
        assert np.array_equal(renderer.screenshot(), aliased)
        # Schließen nach ausgeschaltetem AO muss auch die abgehängten
        # AO-Texturen und den zuletzt unbenutzten FXAA-Pass freigeben.
        renderer.set_ambient_occlusion(False, radius=1, bias=0.01)
        assert np.array_equal(renderer.screenshot(), plain)
    finally:
        renderer.close()


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("margin", [2, 6])
@pytest.mark.parametrize("line_first", [True, False])
def test_label_field_is_centred_padded_and_covers_its_leader(theme, margin, line_first, tmp_path):
    """Echte Pixel halten Text, Feld, Verbindung und Auswahl in beiden Themen zusammen."""
    from PIL import Image

    foreground, background = ("#202833", "#ffffff") if theme == "light" else ("#f2f5fa", "#20262f")
    renderer = VtkRenderer(offscreen=True, size=(440, 320))
    try:
        body = renderer.add_surface(
            np.asarray([[-22, -16, -1], [22, -16, -1], [22, 16, -1], [-22, 16, -1]]),
            np.asarray([[0, 1, 2], [0, 2, 3]]),
            name="body",
            style=SurfaceStyle(colour="#777777", lighting=False),
        )

        def line():
            """Das innere Stück reicht bewusst bis zur Textmitte."""
            return renderer.add_lines(
                np.asarray([[-18.0, 0, 0], [6.0, 0, 0]]),
                name="leader",
                colour="#ff0000",
                width=3,
                keep_in_front=True,
                pickable=False,
            )

        leader = line() if line_first else None
        label = renderer.add_labels(
            np.asarray([[6.0, 0, 0]]),
            ["Verrundung · R2,86 mm"],
            name="label",
            style=LabelStyle(
                font_size=14,
                text_colour=foreground,
                background=background,
                background_opacity=1.0,
                margin=margin,
                show_points=False,
                always_visible=True,
                pickable=False,
            ),
        )
        if leader is None:
            leader = line()
        renderer.set_camera_pose(CameraPose((0, 0, 50), (0, 0, 0), (0, 1, 0)))
        renderer.set_parallel_projection(True)
        renderer.set_parallel_scale(16)
        for index, anchor in enumerate(((6.0, 0, 0), (-2.0, 3.0, 0))):
            if index:
                label.update_labels(np.asarray([anchor]), ["Bohrung · Ø12,34 mm"])
                leader.update_points(np.asarray([[-18.0, 3.0, 0], anchor]))
            image = renderer.screenshot()[:, :, :3]
            Image.fromarray(image).save(tmp_path / f"{theme}-{margin}-{index}.png")
            field = (
                np.max(np.abs(image.astype(float) - np.asarray(rgb(background)) * 255), axis=2) < 8
            )
            # FreeType glättet die dünnen Glyphen mit dem Feld; der mittlere
            # Grauton des Körpers liegt deutlich außerhalb dieser Farbnähe.
            text = (
                np.max(np.abs(image.astype(float) - np.asarray(rgb(foreground)) * 255), axis=2) < 45
            )
            red = (image[:, :, 0] > 200) & (image[:, :, 1:].max(axis=2) < 40)
            fy, fx = np.where(field)
            ty, tx = np.where(text)
            assert len(fx) > 100 and len(tx) > 50
            x, y, _depth = renderer.world_to_display(anchor)
            assert (fx.min() + fx.max()) / 2 == pytest.approx(x, abs=2)
            assert (fy.min() + fy.max()) / 2 == pytest.approx(y, abs=2)
            assert fx.min() + margin - 1 <= tx.min() <= tx.max() <= fx.max() - margin + 1
            assert fy.min() + margin - 1 <= ty.min() <= ty.max() <= fy.max() - margin + 1
            assert not np.any(red[fy.min() : fy.max() + 1, fx.min() : fx.max() + 1])
            assert np.count_nonzero(red) > 50
            assert np.array_equal(image, renderer.screenshot()[:, :, :3])
            hit = renderer.pick_surface(x, y)
            assert hit is not None and hit.item is body
    finally:
        renderer.close()


@pytest.mark.parametrize("opacity", [0.0, 0.25, 0.5, 1.0])
@pytest.mark.parametrize("always_visible", [True, False])
@pytest.mark.parametrize("label_count", [1, 2])
def test_translucent_label_field_stays_translucent_without_hiding_text(
    opacity, always_visible, label_count
):
    """Jeder gewollte Eintrag mischt genau einmal, der Kollisionspfad blendet Doppelungen aus."""
    renderer = VtkRenderer(offscreen=True, size=(240, 160))
    try:
        renderer.set_background("#777777")
        label = renderer.add_labels(
            np.zeros((label_count, 3)),
            ["HH      HH"] * label_count,
            name="label",
            style=LabelStyle(
                font_size=20,
                text_colour="#00ff00",
                background="#0000ff",
                background_opacity=opacity,
                margin=6,
                always_visible=always_visible,
                show_points=False,
            ),
        )
        renderer.set_camera_pose(CameraPose((0, 0, 50), (0, 0, 0), (0, 1, 0)))
        image = renderer.screenshot()
        x, y, _depth = renderer.world_to_display((0, 0, 0))
        centre = image[round(y), round(x), :3]
        visible_count = label_count if always_visible else 1
        effective_alpha = 1 - (1 - opacity) ** visible_count
        expected = (
            np.asarray([119, 119, 119]) * (1 - effective_alpha)
            + np.asarray([0, 0, 255]) * effective_alpha
        )
        assert np.allclose(centre, expected, atol=2), (centre, expected)
        if opacity > 0:
            from vtkmodules.util.numpy_support import vtk_to_numpy

            rectangle = vtk_to_numpy(label._field_data.GetPoints().GetData())[:4]
            left, bottom = rectangle[0, :2]
            right, top = rectangle[2, :2]
            for px, py in (
                (left + 2, (bottom + top) / 2),
                (right - 2, (bottom + top) / 2),
                ((left + right) / 2, bottom + 2),
                ((left + right) / 2, top - 2),
            ):
                pixel = image[image.shape[0] - 1 - round(py), round(px), :3]
                assert np.allclose(pixel, expected, atol=2), (pixel, expected)
        assert np.array_equal(image, renderer.screenshot())
        green = (image[:, :, 1] > 200) & (image[:, :, 0] < 40) & (image[:, :, 2] < 40)
        assert np.count_nonzero(green) > 50
        if opacity == 0:
            blue = (image[:, :, 2] > 200) & (image[:, :, :2].max(axis=2) < 40)
            assert not np.any(blue)
        label.set_visible(False)
        renderer.add_labels(
            np.zeros((label_count, 3)),
            ["HH      HH"] * label_count,
            name="plain-reference",
            style=LabelStyle(
                font_size=20,
                text_colour="#00ff00",
                margin=6,
                always_visible=always_visible,
            ),
        )
        reference = renderer.screenshot()
        ink = np.all(image[:, :, :3] == (0, 255, 0), axis=2)
        assert np.array_equal(ink, np.all(reference[:, :, :3] == (0, 255, 0), axis=2))
    finally:
        renderer.close()


@pytest.mark.parametrize("always_visible", [True, False])
def test_label_updates_keep_text_style_anchors_visibility_and_pick_contract(always_visible):
    """Beide Beschriftungswege bearbeiten denselben Stil und lassen die Körperauswahl durch."""
    renderer = VtkRenderer(offscreen=True, size=(240, 160))
    try:
        body = renderer.add_surface(
            np.asarray([[-20, -12, -1], [20, -12, -1], [20, 12, -1], [-20, 12, -1]]),
            np.asarray([[0, 1, 2], [0, 2, 3]]),
            name="body",
            style=SurfaceStyle(colour="#777777", lighting=False),
        )
        label = renderer.add_labels(
            np.asarray([[-5.0, 0, 0]]),
            ["HH      HH"],
            name="label",
            style=LabelStyle(
                font_size=20,
                text_colour="#00ff00",
                always_visible=always_visible,
                show_points=True,
                pickable=False,
            ),
        )
        renderer.set_camera_pose(CameraPose((0, 0, 50), (0, 0, 0), (0, 1, 0)))
        renderer.set_parallel_projection(True)
        renderer.set_parallel_scale(12)
        before = renderer.screenshot()
        anchor = (5.0, 3.0, 0.0)
        label.update_labels(np.asarray([anchor]), ["HH    HH"])
        label.set_colour("#ff0000")
        label.set_opacity(0.5)
        assert label.colour() == "#ff0000"
        assert label.opacity() == pytest.approx(0.5)
        after = renderer.screenshot()
        assert not np.array_equal(before, after)
        x, y, _depth = renderer.world_to_display(anchor)
        hit = renderer.pick_surface(x, y)
        assert hit is not None and hit.item is body
        label.set_visible(False)
        hidden = renderer.screenshot()
        assert not np.array_equal(after, hidden)
        renderer.remove(label)
        assert np.array_equal(hidden, renderer.screenshot())
    finally:
        renderer.close()


@pytest.mark.parametrize("always_visible", [True, False])
def test_label_fields_share_collision_multiline_updates_buffers_and_lifetime(always_visible):
    """Duplikate, mehrzeilige Texte und leere Sätze behalten gemeinsame Feld-/Schriftgrenzen."""
    from vtkmodules.util.numpy_support import vtk_to_numpy

    renderer = VtkRenderer(offscreen=True, size=(320, 200))
    try:
        renderer.set_background("#777777")
        points = np.asarray([[0.0, 0, 0], [0, 0, 0], [30, 0, 0]])
        texts = ["Alpha\nBeta", "Alpha\nBeta", "Gamma"]
        label = renderer.add_labels(
            points,
            texts,
            name="labels",
            style=LabelStyle(
                background="#0000ff",
                background_opacity=0.5,
                margin=6,
                show_points=True,
                always_visible=always_visible,
            ),
        )
        renderer.set_camera_pose(CameraPose((0, 0, 50), (0, 0, 0), (0, 1, 0)))
        renderer.set_parallel_projection(True)
        renderer.set_parallel_scale(30)
        renderer.screenshot()
        count = 3 if always_visible else 2
        assert label.mapper.GetInput().GetNumberOfPoints() == count
        assert label._field_data.GetNumberOfCells() == count
        positions = label._field_data.GetPoints().GetData()
        before = vtk_to_numpy(positions).copy()
        renderer.set_camera_pose(CameraPose((2, 1, 50), (2, 1, 0), (0, 1, 0)))
        renderer.screenshot()
        assert label._field_data.GetPoints().GetData() is positions
        assert not np.array_equal(before, vtk_to_numpy(positions))
        reordered = ["Gamma", "Alpha\nBeta", "Alpha\nBeta"]
        label.update_labels(points[[2, 0, 1]], reordered)
        renderer.screenshot()
        visible = label.mapper.GetInput().GetPointData().GetAbstractArray("labels")
        expected = reordered if always_visible else reordered[:2]
        assert [visible.GetValue(i) for i in range(visible.GetNumberOfValues())] == expected
        label.set_position((1, 2, 0))
        renderer.screenshot()
        assert np.allclose(
            vtk_to_numpy(label.data.GetPoints().GetData()), points[[2, 0, 1]] + (1, 2, 0)
        )
        label.update_labels(np.empty((0, 3)), [])
        renderer.screenshot()
        assert label.mapper.GetInput().GetNumberOfPoints() == 0
        assert label._field_data.GetNumberOfCells() == 0
        label.update_labels(points[:1], texts[:1])
        renderer.screenshot()
        assert label._field_data.GetNumberOfCells() == 1
        props = label.props()
        assert all(renderer.renderer.HasViewProp(prop) for prop in props)
        renderer.remove(label)
        assert label not in renderer._label_items
        assert all(not renderer.renderer.HasViewProp(prop) for prop in props)
        assert label not in renderer._items.values()
        assert np.all(renderer.screenshot() == 119)
    finally:
        renderer.close()
