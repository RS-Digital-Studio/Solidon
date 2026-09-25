"""Einmalig: ein körpernahes, elementweises Volumen für alle Entscheidungen (B16/B17)."""

from __future__ import annotations

from pathlib import Path


def edit(name: str, pairs: list[tuple[str, str]]) -> None:
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        assert text.count(old) == 1, (name, text.count(old), old[:90])
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")


edit(
    "app/core/geom/mesh.py",
    [
        (
            '''def enclosed_volume(body: trimesh.Trimesh) -> float:
    """Das Volumenintegral über die Oberfläche, bezogen auf den Ursprung.

    Dieselbe Formel wie ``trimesh.triangles.mass_properties``, ohne Schwerpunkt
    und Trägheit, summiert mit ``math.fsum`` — an 203 776 Dreiecken 0,07 statt
    0,29 s. Für ein geschlossenes Netz das Volumen, für ein offenes eine Zahl,
    die an der Lage hängt; so war sie es vorher auch.
    """
    triangles = np.asarray(body.triangles, dtype=np.float64)
    if not len(triangles):
        return 0.0
    products = np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2]))
    return math.fsum(products) / 6.0
''',
            '''def triple_products(triangles: np.ndarray) -> np.ndarray:
    """Das Spatprodukt ``a · (b × c)`` je Dreieck ``(n, 3, 3)``.

    Elementweise und nicht über ``np.einsum`` (RM-187): Das nutzt auf ARM FMA,
    und am Vorzeichen der Summe hängt, ob ein Körper, eine Schale oder ein
    Ergebnis gilt.
    """
    first, crossed = triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])
    return np.asarray(
        first[:, 0] * crossed[:, 0] + first[:, 1] * crossed[:, 1] + first[:, 2] * crossed[:, 2]
    )


def enclosed_volume(body: trimesh.Trimesh) -> float:
    """Das Volumenintegral über die Oberfläche, bezogen auf den Ursprung.

    Dieselbe Formel wie ``trimesh.triangles.mass_properties``, ohne Schwerpunkt
    und Trägheit, summiert mit ``math.fsum`` — an 203 776 Dreiecken 0,07 statt
    0,29 s. Für ein geschlossenes Netz das Volumen, für ein offenes eine Zahl,
    die an der Lage hängt; so war sie es vorher auch. **Für eine Entscheidung
    gilt** :func:`signed_volume`: Weit vom Ursprung verliert diese Summe das
    Volumen eines kleinen Körpers in der Rundung.
    """
    triangles = np.asarray(body.triangles, dtype=np.float64)
    if not len(triangles):
        return 0.0
    return math.fsum(triple_products(triangles).tolist()) / 6.0


def signed_volume(body: trimesh.Trimesh) -> float:
    """Das Volumenintegral nahe am Körper — die Zahl, an der Entscheidungen hängen.

    Bezogen auf die erste Ecke statt auf den Ursprung. Für ein geschlossenes
    Netz derselbe Wert wie :func:`enclosed_volume`, nur ohne dessen Verlust
    weit draußen: Ein Würfel von 1 mm bei 10⁸ mm hatte dort ein Volumen, das
    allein aus Rundung bestand, und die Reparatur stülpte ihn um (Befund B16
    der Durchsicht 24.09.2026). Ob ein Netz ein positiver Körper ist, ob ein
    Boolesches Ergebnis gilt und ob eine Füllung Dicke hat, fragen dieselbe
    Rechnung.
    """
    triangles = np.asarray(body.triangles, dtype=np.float64)
    if not len(triangles):
        return 0.0
    return math.fsum(triple_products(triangles - triangles[0, 0]).tolist()) / 6.0
''',
        ),
    ],
)

edit(
    "app/core/geom/boolean.py",
    [
        (
            "from app.core.geom.mesh import MeshData, enclosed_volume\n",
            "from app.core.geom.mesh import MeshData, enclosed_volume, signed_volume\n",
        ),
        (
            "        body.is_watertight and body.is_winding_consistent and _signed_volume(body) > 0.0\n",
            "        body.is_watertight and body.is_winding_consistent and signed_volume(body) > 0.0\n",
        ),
        ("    return _signed_volume(shared.raw)\n", "    return signed_volume(shared.raw)\n"),
        (
            '''def _signed_volume(body: trimesh.Trimesh) -> float:
    """Volumenintegral ohne Schwerpunktdivision, nahe am Körper ausgewertet."""
    triangles = np.asarray(body.triangles, dtype=np.float64)
    if not len(triangles):
        return 0.0
    local = triangles - triangles[0, 0]
    # Das Spatprodukt elementweise, nicht über ``np.einsum`` — das nutzt auf
    # ARM FMA, und am Vorzeichen dieser Summe hängt, ob ein Ergebnis gilt.
    first, crossed = local[:, 0], np.cross(local[:, 1], local[:, 2])
    products = (
        first[:, 0] * crossed[:, 0] + first[:, 1] * crossed[:, 1] + first[:, 2] * crossed[:, 2]
    )
    return math.fsum(products.tolist()) / 6.0


''',
            "",
        ),
        (
            "    return bool(mesh.raw.is_watertight) and _signed_volume(mesh.raw) > 0.0\n",
            "    return bool(mesh.raw.is_watertight) and signed_volume(mesh.raw) > 0.0\n",
        ),
    ],
)

edit(
    "app/core/geom/difference.py",
    [
        (
            "from app.core.geom.boolean import _signed_volume, boolean\n"
            "from app.core.geom.mesh import MeshData, as_mesh_data, face_components\n",
            "from app.core.geom.boolean import boolean\n"
            "from app.core.geom.mesh import MeshData, as_mesh_data, face_components, signed_volume\n",
        ),
        (
            "        if abs(_signed_volume(part)) > roundoff:\n",
            "        if abs(signed_volume(part)) > roundoff:\n",
        ),
    ],
)

edit(
    "app/core/geom/repair.py",
    [
        (
            '''def _shell_volumes(body: trimesh.Trimesh, labels: np.ndarray, count: int) -> np.ndarray:
    """Das eingeschlossene Volumen je Schale — über ``np.cross`` und
    Grundrechenarten, weil das Vorzeichen eine Entscheidung trägt (RM-187)."""
    triangles = np.asarray(body.triangles, dtype=np.float64)
    crossed = np.cross(triangles[:, 1], triangles[:, 2])
    products = (
        triangles[:, 0, 0] * crossed[:, 0]
        + triangles[:, 0, 1] * crossed[:, 1]
        + triangles[:, 0, 2] * crossed[:, 2]
    )
    return np.bincount(labels, weights=products, minlength=count) / 6.0
''',
            '''def _shell_volumes(body: trimesh.Trimesh, labels: np.ndarray, count: int) -> np.ndarray:
    """Das eingeschlossene Volumen je Schale, nahe an der Schale gerechnet.

    Jede Schale bezieht sich auf ihre eigene erste Ecke, nicht auf den
    Ursprung (Befund B16, 24.09.2026): Weit draußen bestand das Volumen eines
    kleinen Teils sonst aus Rundung, und sein Vorzeichen entschied, ob es
    umgestülpt wird. Das Spatprodukt rechnet :func:`mesh.triple_products`
    elementweise (RM-187).
    """
    triangles = np.asarray(body.triangles, dtype=np.float64)
    if not len(triangles):
        return np.zeros(count)
    _shells, first = np.unique(labels, return_index=True)
    anchors = np.zeros((count, 3))
    anchors[labels[first]] = triangles[first, 0]
    products = triple_products(triangles - anchors[labels][:, None, :])
    return np.bincount(labels, weights=products, minlength=count) / 6.0
''',
        ),
        (
            '''    unter
    ``EPS_GEOM`` bleibt der Ring offen. Die Summen laufen über ``np.cross``
    und Grundrechenarten (RM-187).
    """
    body = patched.raw
    components = face_components(body)
    labels = np.empty(len(body.faces), dtype=np.int64)
    for index, faces in enumerate(components):
        labels[faces] = index
    triangles = np.asarray(body.triangles, dtype=np.float64)
    crossed = np.cross(triangles[:, 1], triangles[:, 2])
    products = (
        triangles[:, 0, 0] * crossed[:, 0]
        + triangles[:, 0, 1] * crossed[:, 1]
        + triangles[:, 0, 2] * crossed[:, 2]
    )
    volume = np.bincount(labels, weights=products, minlength=len(components)) / 6.0
''',
            '''    unter
    ``EPS_GEOM`` bleibt der Ring offen. Das Volumen je Teil kommt aus
    :func:`_shell_volumes`, nahe am Teil und elementweise (RM-187).
    """
    body = patched.raw
    components = face_components(body)
    labels = np.empty(len(body.faces), dtype=np.int64)
    for index, faces in enumerate(components):
        labels[faces] = index
    volume = _shell_volumes(body, labels, len(components))
''',
        ),
        (
            "    if not mesh.volume > 0.0:\n        return \"flat\"\n",
            "    if not signed_volume(mesh.raw) > 0.0:\n        return \"flat\"\n",
        ),
        (
            '''    """Dichtheit, Wicklung und positives Volumen ohne Schwerpunktdivision prüfen."""
    return mesh.is_watertight and mesh.raw.is_winding_consistent and mesh.volume > 0.0
''',
            '''    """Dichtheit, Wicklung und positives Volumen — nahe am Körper gerechnet (B16)."""
    return (
        mesh.is_watertight and mesh.raw.is_winding_consistent and signed_volume(mesh.raw) > 0.0
    )
''',
        ),
    ],
)
print("ok")
