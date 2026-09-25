"""Druckempfehlung am Bowl wie im Druckdialog, dazu die Überhänge über Modellmaterial."""
import sys, time, numpy as np, trimesh, shapely
from app.core.geom.mesh import MeshData
from app.core.knowledge import profiles, print_settings
from app.core.slice import advise
from app.core.slice.analysis import slice_body, _layer_shape, _above_material, _areas_of, _supported_span, OVERHANG_MARGIN
from app.core.types import Profile
S = r"C:\Users\rober\AppData\Local\Temp\claude\F--3D-Druck\5a618bfd-281d-49da-a2e6-53d607465f68\scratchpad"
path = sys.argv[1] if len(sys.argv) > 1 else S + r"\out\bowl_washing_bowl_v1.stl"
m = trimesh.load(path); m.apply_translation([128, 128, -m.bounds[0][2]])
mesh = MeshData(m)
profile = profiles.make_profile("centauri-carbon-2", "pla")
settings = print_settings.resolve(profile)
t = time.perf_counter()
result = slice_body(mesh, settings.layers.layer_height, first_layer_height=settings.layers.first_layer_height,
                    overhang_angle=45.0, bridge_from=profile.minimum_wall_thickness, support_volume=False)
print(f"Schnitt {time.perf_counter() - t:.1f} s, {len(result.layers)} Schichten, erste Schicht {result.first_layer_area:.0f} mm²")
for entry in advise.advise(settings, profile, result, bounds=mesh.bounds):
    if entry.path.split(".")[0] in ("support", "adhesion", "speed"):
        print("  Vorschlag", entry.path, entry.was, "->", entry.value, "|", str(entry.reason)[:110])
# Überhänge, deren Säule auf Modell endet: von oben nach unten, je Stück mit Herkunftsschicht
layers = result.layers
pieces = []  # (start_index, polygon)
for index in range(len(layers) - 1, 0, -1):
    layer = layers[index]
    if not layer.overhangs: continue
    below = _layer_shape(layers[index - 1])
    for contour in layer.overhangs:
        poly = shapely.Polygon(contour.outline, contour.holes)
        pending = [poly]
        for j in range(index - 1, 0, -1):
            nxt = _layer_shape(layers[j - 1]) if j else None
            if nxt is None or nxt.is_empty: continue
            before = sum(p.area for p in pending)
            pending = _above_material(pending, nxt)
            if before - sum(p.area for p in pending) > 1e-6:
                landed = before - sum(p.area for p in pending)
                supported = below.buffer(OVERHANG_MARGIN)
                span = _supported_span(poly, supported) if poly.geom_type == "Polygon" else float("nan")
                anchored = supported.buffer(1e-6).covers(poly.exterior)
                pieces.append((layers[index].z, layers[j - 1].z, poly.area, landed, span, anchored, poly.centroid.x, poly.centroid.y))
                break
            if not pending: break
print(f"{len(pieces)} Überhangstücke landen auf dem Modell")
pieces.sort(key=lambda p: -p[2])
for z, zl, area, landed, span, anch, x, y in pieces[:25]:
    print(f"  z {z:6.2f} -> landet bei {zl:6.2f}  Fläche {area:7.1f}  gelandet {landed:7.1f}  Spannweite {span:6.1f}  ringsum verankert {anch}  bei ({x:.0f}, {y:.0f})")
print("Brückenweiten > 5 mm:")
for layer in layers:
    if layer.bridge_width > 5: print(f"  z {layer.z:6.2f} Brücke {layer.bridge_width:6.1f} Überhang {layer.overhang_area:7.1f}")
import collections
g = collections.Counter()
for z, zl, area, landed, span, anch, x, y in pieces:
    g[("Kanal" if x > 150 and y > 170 else "Turm" if abs(x - 128) < 35 and abs(y - 128) < 35 else f"sonst ({x:.0f},{y:.0f})")] += area
print("Überhang über Modell nach Ort (mm², Summe über Schichten):", dict(g))
