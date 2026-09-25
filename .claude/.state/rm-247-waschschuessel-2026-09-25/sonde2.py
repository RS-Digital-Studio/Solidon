import sys, time, trimesh
from app.core.geom.mesh import MeshData
from app.core.knowledge import profiles, print_settings
from app.core.slice import advise
from app.core.slice.analysis import slice_body, model_support
path = sys.argv[1]
m = trimesh.load(path, force="mesh"); m.apply_translation([128 - m.bounds.mean(0)[0], 128 - m.bounds.mean(0)[1], -m.bounds[0][2]])
mesh = MeshData(m)
profile = profiles.make_profile("centauri-carbon-2", "pla")
settings = print_settings.resolve(profile)
t = time.perf_counter()
result = slice_body(mesh, settings.layers.layer_height, first_layer_height=settings.layers.first_layer_height,
                    overhang_angle=45.0, bridge_from=profile.minimum_wall_thickness, support_volume=False)
t1 = time.perf_counter()
ms = model_support(result)
t2 = time.perf_counter()
print(f"{path.split(chr(92))[-1]}: {len(m.faces)} Dreiecke, Schnitt {t1-t:.2f} s, model_support {1000*(t2-t1):.0f} ms")
print(f"  außen auf Modell {ms.open_patch:.1f} mm², Kanäle {len(ms.channels)} Stücke / {ms.channel_area:.0f} mm² bei {ms.channel_at}")
for e in advise.advise(settings, profile, result, bounds=mesh.bounds):
    if e.path.split(".")[0] in ("support", "adhesion"):
        print("  Vorschlag", e.path, e.was, "->", e.value, "|", str(e.reason)[:100])
for f in advise.located_warnings(result, profile):
    print("  Befund", f.code, f.values)
