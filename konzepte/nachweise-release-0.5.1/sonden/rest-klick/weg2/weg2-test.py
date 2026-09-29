

@pytest.mark.parametrize("rotation", [False, True])
def test_a_retargeted_gizmo_is_the_gizmo_a_rebuild_would_draw(rotation: bool) -> None:
    """Versetzt statt neu gebaut: dieselben Elemente, dasselbe Bild, derselbe Zug (RM-232).

    Die Platzierung hängt den Griff bei jedem Klick auf ein anderes Merkmal
    an einen neuen Werkzeugkörper. Der versetzte Griff muss danach Punkt für
    Punkt der sein, den ein frischer Renderer mit einem frisch gebauten
    Griff zeigt — auch wenn am alten eine Hervorhebung stand — und sein Zug
    muss gegen das neue Ziel rechnen.
    """
    views = [make_renderer(SIZE), make_renderer(SIZE)]
    try:
        bodies = []
        for view in views:
            view.set_background("#101418")
            view.set_camera_pose(
                CameraPose((90.0, -110.0, 80.0), (10.0, 10.0, 10.0), (0.0, 0.0, 1.0))
            )
            view.reset_camera((-30.0, 50.0, -30.0, 50.0, -30.0, 50.0))
            vertices, faces = cube(10.0, origin=(15.0, 5.0, 0.0))
            bodies.append(view.add_surface(vertices, faces, name="tool", style=SurfaceStyle()))
        moved, reference = views
        first = moved.add_surface(*cube(20.0), name="old-tool", style=SurfaceStyle())
        gizmo = Gizmo(moved, first, scale=0.4, rotation=rotation)
        before = list(gizmo.items)
        x, y = arrow_tip_pixel(moved, gizmo, 2)
        gizmo.handle(hover(x, y))
        assert gizmo.items[2].colour() == HIGHLIGHT
        moved.remove(first)
        gizmo.retarget(bodies[0], scale=0.4)
        assert list(gizmo.items) == before, "dieselben Elemente, keine neuen"
        assert gizmo.fits(bodies[0], rotation=rotation, scale=0.4)
        assert [item.colour() for item in gizmo.items[:3]] == list(AXIS_COLOURS)
        fresh = Gizmo(reference, bodies[1], scale=0.4, rotation=rotation)
        assert gizmo.origin == pytest.approx(fresh.origin)
        assert gizmo.reach == pytest.approx(fresh.reach)
        assert np.array_equal(moved.screenshot(), reference.screenshot())
        # Derselbe Zug an beiden Griffen gibt dieselbe Matrix, und am
        # versetzten bewegt er das neue Ziel.
        results = []
        for view, grip, target in ((moved, gizmo, bodies[0]), (reference, fresh, bodies[1])):
            releases: list[np.ndarray] = []
            grip._release = releases.append
            x, y = arrow_tip_pixel(view, grip, 2)
            grip.handle(hover(x, y))
            assert grip.handle(press(x, y)), "der Griff nimmt die Geste"
            far = np.asarray(grip.origin) + grip.axes[2] * grip._arrow_length * 1.5
            fx, fy, _depth = view.world_to_display((float(far[0]), float(far[1]), float(far[2])))
            assert grip.handle(move(fx, fy))
            assert grip.handle(release(fx, fy))
            assert np.allclose(target.matrix(), releases[-1])
            results.append((grip._selected, releases[-1]))
        assert results[0][0] == results[1][0]
        assert np.allclose(results[0][1], results[1][1])
        assert not np.allclose(results[0][1], np.eye(4)), "der Zug hat etwas bewegt"
        assert np.allclose(first.matrix(), np.eye(4)), "das alte Ziel bleibt, wo es war"
        fresh.remove()
        gizmo.remove()
    finally:
        for view in views:
            view.close()
