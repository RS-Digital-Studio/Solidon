"""Prototyp: Offenheit einer Stützsäule über Modell, aus den Schichtschnitten."""
import sys, time, math, numpy as np, trimesh, shapely, manifold3d as mf
from app.core.geom.mesh import MeshData
from app.core.slice.analysis import slice_body, _layer_shape, _above_material
def fib(n):
    i = np.arange(n) + 0.5; phi = np.arccos(1 - 2 * i / n); th = math.pi * (1 + 5 ** 0.5) * i
    return np.column_stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)])
def on_model_columns(result):
    layers = result.layers; out = []
    shapes = [_layer_shape(l) for l in layers]
    for index in range(len(layers) - 1, 0, -1):
        for contour in layers[index].overhangs or ():
            poly = shapely.Polygon(contour.outline, contour.holes); pending = [poly]
            for j in range(index - 1, -1, -1):
                below = shapes[j]
                if below.is_empty: continue
                before = sum(p.area for p in pending); pending = _above_material(pending, below)
                if before - sum(p.area for p in pending) > 1e-6:
                    out.append((index, j, poly)); break
                if not pending: break
    return out, shapes
def openness(result, shapes, point, rays=256, step=0.4):
    zs = np.array([l.z for l in result.layers]); lo = np.array([min(s.bounds[0] for s in shapes if not s.is_empty), min(s.bounds[1] for s in shapes if not s.is_empty)]); hi = np.array([max(s.bounds[2] for s in shapes if not s.is_empty), max(s.bounds[3] for s in shapes if not s.is_empty)])
    D = fib(rays); reach = float(np.hypot(*(hi - lo)) + zs[-1]) ; t = np.arange(step, reach, step)
    P = point[None, None, :] + D[:, None, :] * t[None, :, None]  # rays x steps x 3
    inside_box = (P[..., 0] >= lo[0]) & (P[..., 0] <= hi[0]) & (P[..., 1] >= lo[1]) & (P[..., 1] <= hi[1]) & (P[..., 2] >= zs[0]) & (P[..., 2] <= zs[-1])
    hit = np.zeros(P.shape[:2], bool)
    k = np.clip(np.searchsorted(zs, P[..., 2]), 0, len(zs) - 1)
    for layer in np.unique(k[inside_box]):
        sel = inside_box & (k == layer)
        if shapes[layer].is_empty: continue
        hit[sel] = shapely.contains_xy(shapes[layer], P[..., 0][sel], P[..., 1][sel])
    blocked = hit.any(axis=1)
    return 1.0 - blocked.mean()
def probe(name, mesh):
    t0 = time.perf_counter()
    result = slice_body(MeshData(mesh), 0.2, first_layer_height=0.25, support_volume=False)
    cols, shapes = on_model_columns(result)
    if not cols: print(f"{name}: keine Säule auf dem Modell"); return
    # nach Ort bündeln (5-mm-Raster), je Bündel größte Fläche
    groups = {}
    for i, j, poly in cols:
        c = poly.representative_point(); key = (round(c.x / 5), round(c.y / 5))
        groups.setdefault(key, []).append((i, j, poly))
    for key, items in sorted(groups.items(), key=lambda kv: -sum(p.area for _, _, p in kv[1]))[:6]:
        i, j, poly = max(items, key=lambda it: it[2].area)
        c = poly.representative_point(); z = (result.layers[i].z + result.layers[j].z) / 2
        o = openness(result, shapes, np.array([c.x, c.y, z]))
        print(f"{name}: Bündel bei ({c.x:.0f},{c.y:.0f}) z {result.layers[j].z:.1f}..{result.layers[i].z:.1f}, Fläche {sum(p.area for _,_,p in items):.0f} mm², Offenheit {o:.1%}")
    print(f"   ({time.perf_counter() - t0:.1f} s)")
def box(a, b):
    return trimesh.creation.box(extents=np.subtract(b, a), transform=trimesh.transformations.translation_matrix(np.add(a, b) / 2))
def union(*ms):
    r = None
    for m in ms:
        x = mf.Manifold(mf.Mesh(vert_properties=m.vertices.astype(np.float32), tri_verts=m.faces.astype(np.uint32)))
        r = x if r is None else r + x
    o = r.to_mesh(); return trimesh.Trimesh(np.asarray(o.vert_properties)[:, :3], np.asarray(o.tri_verts))
def minus(a, b):
    A = mf.Manifold(mf.Mesh(vert_properties=a.vertices.astype(np.float32), tri_verts=a.faces.astype(np.uint32)))
    B = mf.Manifold(mf.Mesh(vert_properties=b.vertices.astype(np.float32), tri_verts=b.faces.astype(np.uint32)))
    o = (A - B).to_mesh(); return trimesh.Trimesh(np.asarray(o.vert_properties)[:, :3], np.asarray(o.tri_verts))
S = r"C:\Users\rober\AppData\Local\Temp\claude\F--3D-Druck\5a618bfd-281d-49da-a2e6-53d607465f68\scratchpad"
if "bowl" in sys.argv:
    m = trimesh.load(S + r"\out\bowl_washing_bowl_v1.stl"); m.apply_translation([128, 128, 0]); probe("Schüssel", m)
# Tisch: Bodenplatte 40x40x4, Säule 10x10, Platte 40x40x4 auf 30 mm
probe("Tisch", union(box((0, 0, 0), (40, 40, 4)), box((15, 15, 4), (25, 25, 30)), box((0, 0, 30), (40, 40, 34))))
# offener Kasten 80x80x60, Wand 3, Innenregal an einer Wand auf 35 mm, 25 tief
probe("Kasten mit Regal", union(minus(box((0, 0, 0), (80, 80, 60)), box((3, 3, 3), (77, 77, 61))), box((3, 3, 35), (28, 77, 38))))
# Block 60x40x40 mit Tunnel 20x20 quer (offen an beiden Enden)
probe("Tunnel", minus(box((0, 0, 0), (60, 40, 40)), box((20, -1, 8), (40, 41, 28))))
# geschlossener Hohlkörper 60x60x40, Wand 3 (verschlossene Kammer)
probe("verschlossen", minus(box((0, 0, 0), (60, 60, 40)), box((3, 3, 3), (57, 57, 37))))
# Rohrbogen: Block mit Kanal 20x20, der unten quer läuft und senkrecht nach oben austritt
probe("Kanal mit Bogen", minus(box((0, 0, 0), (80, 40, 50)), union(box((10, 10, 8), (70, 30, 28)), box((50, 10, 8), (70, 30, 51)))))

def passage(shapes, layer, point, window=80.0):
    """Größter leerer Kreis im freien Raum der Schicht, der den Punkt enthält (Durchmesser)."""
    shape = shapes[layer]; p = shapely.Point(point[0], point[1])
    area = p.buffer(window, quad_segs=16)
    free = area.difference(shape)
    if free.is_empty or not free.covers(p): return 0.0
    # nur der Teil des freien Raums, der den Punkt enthält
    parts = [g for g in getattr(free, "geoms", [free]) if g.covers(p)]
    free = parts[0]
    lo, hi = 0.0, window
    for _ in range(14):
        r = (lo + hi) / 2
        core = free.buffer(-r)
        # der Fensterrand ist kein Material: ein Kreis, der ihn berührt, ist „weit"
        if not core.is_empty and core.distance(p) <= r + 1e-9: lo = r
        else: hi = r
    return 2 * lo
def probe2(name, mesh):
    result = slice_body(MeshData(mesh), 0.2, first_layer_height=0.25, support_volume=False)
    cols, shapes = on_model_columns(result)
    if not cols: print(f"{name}: keine Säule auf dem Modell"); return
    widths = []
    for i, j, poly in cols:
        c = poly.representative_point(); mid = (i + j) // 2
        ws = [passage(shapes, k, (c.x, c.y)) for k in (j + 1, mid, i - 1)]
        widths.append((min(ws), poly.area, c.x, c.y, result.layers[i].z))
    widths.sort()
    area_narrow = sum(a for w, a, *_ in widths if w <= 30)
    print(f"{name}: {len(widths)} Säulen, Weite min {widths[0][0]:.1f}, median {widths[len(widths)//2][0]:.1f}, max {widths[-1][0]:.1f}; Fläche <=30 mm: {area_narrow:.0f} von {sum(a for _, a, *_ in widths):.0f} mm²")
if "bowl" in sys.argv:
    m = trimesh.load(S + r"\out\bowl_washing_bowl_v1.stl"); m.apply_translation([128, 128, 0]); probe2("Schüssel", m)
probe2("Tisch", union(box((0, 0, 0), (40, 40, 4)), box((15, 15, 4), (25, 25, 30)), box((0, 0, 30), (40, 40, 34))))
probe2("Kasten mit Regal", union(minus(box((0, 0, 0), (80, 80, 60)), box((3, 3, 3), (77, 77, 61))), box((3, 3, 35), (28, 77, 38))))
probe2("Tunnel", minus(box((0, 0, 0), (60, 40, 40)), box((20, -1, 8), (40, 41, 28))))
probe2("verschlossen", minus(box((0, 0, 0), (60, 60, 40)), box((3, 3, 3), (57, 57, 37))))
probe2("Kanal mit Bogen", minus(box((0, 0, 0), (80, 40, 50)), union(box((10, 10, 8), (70, 30, 28)), box((50, 10, 8), (70, 30, 51)))))
probe2("breiter Tunnel", minus(box((0, 0, 0), (80, 40, 40)), box((10, -1, 8), (70, 41, 28))))
