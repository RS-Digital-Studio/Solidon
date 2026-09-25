"""Modell halbdurchsichtig mit den Stützbahnen als Linien rendern."""
import pickle, sys, numpy as np, trimesh, pygfx as gfx
from rendercanvas.offscreen import RenderCanvas
from PIL import Image
S = r"C:\Users\rober\AppData\Local\Temp\claude\F--3D-Druck\5a618bfd-281d-49da-a2e6-53d607465f68\scratchpad"
run = sys.argv[1]
layers = pickle.load(open(S + "\\" + run + "\layers.pkl", "rb"))
m = trimesh.load(S + r"\out\bowl_washing_bowl_v1.stl"); m.apply_translation([128, 128, 0])
segs = []
for i, L in enumerate(layers):
    for k in ("Support", "Support interface", "Support transition"):
        v = L["seg"].get(k)
        if v is None or not len(v): continue
        v = v[:: 1 if i % 3 == 0 else 1000000]  # jede dritte Schicht
        a = np.column_stack([v[:, 0], v[:, 1], np.full(len(v), L["z"])]); b = np.column_stack([v[:, 2], v[:, 3], np.full(len(v), L["z"])])
        segs.append(np.stack([a, b], 1).reshape(-1, 3))
P = np.vstack(segs).astype(np.float32)
def render(eye, clip=None):
    canvas = RenderCanvas(size=(1000, 760), pixel_ratio=1); r = gfx.WgpuRenderer(canvas)
    scene = gfx.Scene(); scene.add(gfx.Background.from_color("#ffffff"))
    mesh = m
    if clip is not None:
        import manifold3d as mf
        body = mf.Manifold(mf.Mesh(vert_properties=m.vertices.astype(np.float32), tri_verts=m.faces.astype(np.uint32)))
        o = body.trim_by_plane(clip[0], clip[1]).to_mesh(); mesh = trimesh.Trimesh(np.asarray(o.vert_properties)[:, :3], np.asarray(o.tri_verts), process=False)
        n = np.array(clip[0]); keep = (P @ n >= clip[1] - 0.3).reshape(-1, 2).all(1).repeat(2)
        pts = P[keep]
    else:
        pts = P
    geo = gfx.Geometry(positions=mesh.vertices.astype(np.float32), indices=mesh.faces.astype(np.uint32), normals=mesh.vertex_normals.astype(np.float32))
    scene.add(gfx.Mesh(geo, gfx.MeshPhongMaterial(color=(0.36, 0.56, 0.85, 0.45 if clip is None else 1.0), side="both")))
    scene.add(gfx.Line(gfx.Geometry(positions=pts), gfx.LineSegmentMaterial(color="#e8590c", thickness=1.0)))
    cam = gfx.PerspectiveCamera(35, 1000 / 760); c = np.array([128, 128, 50.0])
    cam.local.position = c + np.array(eye); cam.world.reference_up = (0, 0, 1); cam.look_at(c)
    scene.add(gfx.AmbientLight(intensity=0.7)); l = gfx.DirectionalLight(intensity=2); l.local.position = cam.local.position; scene.add(l)
    canvas.request_draw(lambda: r.render(scene, cam)); return Image.fromarray(np.asarray(canvas.draw())[..., :3])
views = [render([200, -330, 170]), render([-60, -380, 60], clip=((0, 1, 0), 128.0)), render([330, 60, 90], clip=((-1, 0, 0), -205.0)), render([0, -10, -420])]
sheet = Image.new("RGB", (2000, 1520), "white")
for i, v in enumerate(views): sheet.paste(v, ((i % 2) * 1000, (i // 2) * 760))
sheet.save(S + "\\" + run + "\stuetz3d.png")
