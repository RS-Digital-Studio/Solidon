import inspect, sys, textwrap
sys.path.insert(0, r"F:\3D Druck")
import pytest
from app.core.geom import mesh as m
import tests.test_geometry_review as t
cases = [lambda p: t.test_the_spatial_preselection_of_ray_hits_batch_changes_no_bit(p), lambda p: t.test_each_safeguard_of_the_ray_preselection_decides_a_constructed_case()]
source = textwrap.dedent(inspect.getsource(m._culled_ray_hits))
mutations = {
    "jeder Treffer der Auswahl gilt": ("taken = (distance <= reach[rays] * RAY_CULL_TAKEN) | final", "taken = np.isfinite(distance) | final"),
    "ohne Randzugabe am Quader": ("slack = (upper - lower).max(axis=1) * (3.0 * max(edge_margin, 0.0)) + guard", "slack = np.zeros(len(triangles)) - guard * 0"),
    "Stück nur halb so lang": ("ends = origins[rays] + directions[rays] * (reach[rays] / length[rays])[:, None]", "ends = origins[rays] + directions[rays] * (0.5 * reach[rays] / length[rays])[:, None]"),
}
original = m._culled_ray_hits
for name, (old, new) in mutations.items():
    assert old in source, name
    namespace = dict(vars(m))
    exec(compile(source.replace(old, new), "mutant", "exec"), namespace)
    m._culled_ray_hits = namespace["_culled_ray_hits"]
    patch = pytest.MonkeyPatch()
    try:
        [case(patch) for case in cases]
        print(f"GRÜN (schlecht): {name}")
    except AssertionError as error:
        print(f"rot (gut): {name}: {(str(error) or "assert").splitlines()[0][:100]}")
    finally:
        patch.undo()
        m._culled_ray_hits = original
