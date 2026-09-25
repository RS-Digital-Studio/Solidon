from pathlib import Path

path = Path("app/core/geom/repair.py")
text = path.read_text(encoding="utf-8")
old = text[text.index("    faces = np.asarray(body.faces, dtype=np.int64)\n    if not len(faces):\n        return False\n    components = face_components(body)"):text.index("#: Wie weit ein Punkt neben einer Kante sitzen darf")]
new = '''    if not len(body.faces):
        return False
    components = face_components(body)
    labels = np.empty(len(body.faces), dtype=np.int64)
    for index, members in enumerate(components):
        labels[members] = index
    volumes = _shell_volumes(body, labels, len(components))
    inverted = math.fsum(volumes.tolist()) < 0.0
    if inverted:
        # Der ganze Körper steht verkehrt — auch ein Hohlkörper, dessen
        # Außenschale negativ und dessen Hohlraum positiv ist.
        body.invert()
        volumes = -volumes
    negative = [index for index, volume in enumerate(volumes.tolist()) if volume < 0.0]
    if not negative or len(components) < 2:
        return inverted
    from app.core.perceive.features import _point_inside_shell, _triangle_bounds

    faces = np.asarray(body.faces, dtype=np.int64).copy()
    triangles = np.asarray(body.triangles, dtype=np.float64)
    boxes = [
        (
            triangles[members].reshape(-1, 3).min(axis=0),
            triangles[members].reshape(-1, 3).max(axis=0),
        )
        for members in components
    ]
    turned = False
    for index in negative:
        low, high = boxes[index]
        point = triangles[components[index][0], 0]
        enclosed = False
        for other, volume in enumerate(volumes.tolist()):
            if other == index or volume <= 0.0:
                continue
            outer_low, outer_high = boxes[other]
            if np.any(low < outer_low) or np.any(high > outer_high):
                continue
            shell = triangles[components[other]]
            answer = _point_inside_shell(point, shell, _triangle_bounds(shell))
            if answer is None or answer:
                enclosed = True
                break
        if not enclosed:
            members = components[index]
            faces[members] = faces[members][:, ::-1]
            turned = True
    if turned:
        body.faces = faces
    return inverted or turned


'''
text = text.replace(old, new, 1)
text = text.replace("    MeshData,\n    enclosed_volume,\n    face_components,", "    MeshData,\n    face_components,", 1)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
