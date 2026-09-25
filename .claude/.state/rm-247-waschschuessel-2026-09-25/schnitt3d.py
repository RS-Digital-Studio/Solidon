"""Halbschnitte der ausgerichteten Schüssel rendern (Kappe rot)."""
import sys, numpy as np, trimesh, pygfx as gfx
from rendercanvas.offscreen import RenderCanvas
from PIL import Image
S = r"C:\Users\rober\AppData\Local\Temp\claude\F--3D-Druck\5a618bfd-281d-49da-a2e6-53d607465f68\scratchpad"
m = trimesh.load(S + r"\out\bowl_washing_bowl_v1.stl")
def render(mesh_list, eye, target, size=(900, 700)):
    canvas = RenderCanvas(size=size, pixel_ratio=1)
    renderer = gfx.WgpuRenderer(canvas)
    scene = gfx.Scene(); scene.add(gfx.Background.from_color("#f4f4f4"))
    for mm, col in mesh_list:
        geo = gfx.Geometry(positions=mm.vertices.astype(np.float32), indices=mm.faces.astype(np.uint32), normals=mm.vertex_normals.astype(np.float32))
        scene.add(gfx.Mesh(geo, gfx.MeshPhongMaterial(color=col, side="both")))
    cam = gfx.PerspectiveCamera(35, size[0]/size[1])
    cam.local.position = eye; cam.world.reference_up = (0, 0, 1); cam.look_at(target)
    scene.add(gfx.AmbientLight(intensity=0.6))
    l = gfx.DirectionalLight(intensity=2.2); l.local.position = eye; scene.add(l)
    canvas.request_draw(lambda: renderer.render(scene, cam))
    return Image.fromarray(np.asarray(canvas.draw())[..., :3])
c = m.bounds.mean(axis=0)
views = []
# Schnitt durch die Mitte, Normale +Y (vordere Hälfte weg)
for normal, eye in [((0, 1, 0), c + np.array([0, -420, 120])), ((1, 0, 0), c + np.array([-420, 0, 120]))]:
    import manifold3d as mf
    body = mf.Manifold(mf.Mesh(vert_properties=m.vertices.astype(np.float32), tri_verts=m.faces.astype(np.uint32)))
    half_m = body.trim_by_plane(tuple(float(v) for v in normal), float(np.dot(normal, c)))
    out = half_m.to_mesh()
    half = trimesh.Trimesh(np.asarray(out.vert_properties)[:, :3], np.asarray(out.tri_verts), process=False)
    views.append(render([(half, "#5b8fd9")], eye, c))
# Unteransicht und Draufsicht
views.append(render([(m, "#5b8fd9")], c + np.array([1, -60, -420]), c))
views.append(render([(m, "#5b8fd9")], c + np.array([1, -60, 420]), c))
sheet = Image.new("RGB", (1800, 1400), "white")
for i, v in enumerate(views): sheet.paste(v, ((i % 2) * 900, (i // 2) * 700))
sheet.save(S + r"\schnitt3d.png")
