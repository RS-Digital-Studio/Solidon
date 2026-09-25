"""Offscreen-Ansichten eines Netzes mit pygfx: python ansicht.py <stl> <ausgabe.png> [az el ...]."""
import sys, numpy as np, trimesh, pygfx as gfx
from rendercanvas.offscreen import RenderCanvas
from PIL import Image
m = trimesh.load(sys.argv[1])
out = sys.argv[2]
views = [float(v) for v in sys.argv[3:]] or [30, 25, 210, 25, 30, -35, 90, 0]
tiles = []
for az, el in zip(views[0::2], views[1::2]):
    canvas = RenderCanvas(size=(700, 560), pixel_ratio=1)
    renderer = gfx.WgpuRenderer(canvas)
    scene = gfx.Scene()
    scene.add(gfx.Background.from_color("#f4f4f4"))
    geo = gfx.Geometry(positions=m.vertices.astype(np.float32), indices=m.faces.astype(np.uint32), normals=m.vertex_normals.astype(np.float32))
    mesh = gfx.Mesh(geo, gfx.MeshPhongMaterial(color="#5b8fd9", side="both"))
    scene.add(mesh)
    cam = gfx.PerspectiveCamera(35, 700/560)
    c = m.bounds.mean(axis=0); r = np.linalg.norm(m.extents) * 1.25
    a, e = np.radians(az), np.radians(el)
    cam.local.position = c + r * np.array([np.cos(e)*np.cos(a), np.cos(e)*np.sin(a), np.sin(e)])
    cam.world.reference_up = (0, 0, 1)
    cam.look_at(c)
    scene.add(gfx.AmbientLight(intensity=0.5))
    light = gfx.DirectionalLight(intensity=2.5); light.local.position = cam.local.position; scene.add(light)
    canvas.request_draw(lambda: renderer.render(scene, cam))
    img = np.asarray(canvas.draw())
    tiles.append(Image.fromarray(img[..., :3]))
w = 2
rows = (len(tiles)+w-1)//w
sheet = Image.new("RGB", (700*w, 560*rows), "white")
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % w)*700, (i//w)*560))
sheet.save(out)
