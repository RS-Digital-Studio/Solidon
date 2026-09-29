"""(ii): Bandprüfung je Kante, eine Gruppe lässt zu enge Kanten mit Befund aus (einmalig)."""

import io
import sys

TREE = sys.argv[1]
path = TREE + "/app/core/geom/edges.py"
text = io.open(path, encoding="utf-8", newline="").read()


def swap(old: str, new: str, count: int = 1) -> None:
    global text
    found = text.count(old)
    assert found == count, (old[:70], found)
    text = text.replace(old, new)


start = text.index("def contact_band_limit(\n")
end = text.index("def _with_station_rays(")
body = text[start:end]
doc_start = body.index('    """Das Maß, unter dem die Berührlinien')
doc_end = body.index('    """\n', doc_start + 10) + len('    """\n')
docstring = body[doc_start:doc_end]
signature = body[:doc_start]
core = body[doc_end:]

core_signature = signature.replace("def contact_band_limit(", "def _band_rows(").replace(
    ") -> float | None:\n",
    ") -> tuple[list[MeshEdge], np.ndarray, np.ndarray, np.ndarray] | None:\n",
)
core_doc = '''    """Die Rechnung hinter :func:`contact_band_limit` — je verletzendem Strahl.

    Zurück kommen die Züge, je Strahl der Zug, dem er gehört, das größte Maß,
    das an ihm passt, und ob dieses Maß mit der Eingabe wächst (sonst passt
    dort keines). ``None``, wenn das eingetragene überall passt.
    """
'''
old_tail = """    width, needed, scaling = width[~skipped], needed[~skipped], scaling[~skipped]
"""
assert core.count(old_tail) == 1
core = core.replace(
    old_tail,
    """    width, needed, scaling = width[~skipped], needed[~skipped], scaling[~skipped]
    mine_chain = mine_chain[~skipped]
""",
)
old_end = """    usable = scaling > EPS_GEOM
    return float(((width[usable] - steady[usable]) / scaling[usable]).min())
"""
assert core.count(old_end) == 1
core = core.replace(
    old_end,
    """    usable = scaling > EPS_GEOM
    limit = np.where(usable, (width - steady) / np.where(usable, scaling, 1.0), 0.0)
    return chains, mine_chain, limit, usable
""",
)
public = (
    signature
    + docstring
    + '''    rows = _band_rows(
        entries,
        chosen,
        size,
        rounded=rounded,
        tolerance=tolerance,
        narrowest=narrowest,
        shape=shape,
        law=law,
    )
    if rows is None:
        return None
    _chains, _owners, limit, usable = rows
    return float(limit[usable].min())


def contact_band_limits(
    entries: Sequence[MeshEdge],
    chosen: Sequence[MeshEdge],
    size: float,
    *,
    rounded: bool,
    tolerance: float,
    narrowest: float = MAX_FACET_SAG,
    shape: ChamferShape | None = None,
    law: RadiusLaw | None = None,
) -> dict[int, float]:
    """Je gewählter Kante, die das Maß nicht trägt, das größte Maß, das an ihr passt.

    Der Schlüssel ist ``id`` der Kante aus ``chosen``; wer das Maß trägt,
    fehlt. Dieselbe Rechnung wie :func:`contact_band_limit` — die Gruppe
    einer Operation lässt die Kanten aus, die hier stehen (:func:`too_narrow_finding`),
    und rundet den Rest. Stoßen zwei gewählte Kanten auf derselben schmalen
    Fläche aneinander, stehen beide hier: Welche von beiden bleiben soll, wäre
    geraten.
    """
    rows = _band_rows(
        entries,
        chosen,
        size,
        rounded=rounded,
        tolerance=tolerance,
        narrowest=narrowest,
        shape=shape,
        law=law,
    )
    if rows is None:
        return {}
    chains, owners, limit, usable = rows
    found: dict[int, float] = {}
    for chain, value, grows in zip(owners.tolist(), limit.tolist(), usable.tolist(), strict=True):
        key = id(chains[int(chain)])
        found[key] = min(found.get(key, math.inf), float(value) if grows else 0.0)
    return found


'''
)
text = text[:start] + public + core_signature + core_doc + core + text[end:]

# Die Gruppe lässt aus, was das Maß nicht trägt.
swap(
    """    largest = contact_band_limit(
        entries,
        chosen,
        size,
        rounded=rounded,
        tolerance=weld_tolerance(mesh.bounds.diagonal),
        narrowest=narrowest,
        shape=shape,
        law=law,
    )
    if largest is not None:
        raise too_large_for_the_faces(size, largest, rounded=rounded, varying=law is not None)
""",
    """    tolerance = weld_tolerance(mesh.bounds.diagonal)
    narrow: list[tuple[MeshEdge, float]] = []
    if selected_edges is None and not keys and choice != "named":
        # **Eine Gruppe nimmt auch hier, was das Maß trägt** (RM-279 (ii),
        # 28.09.2026). Bis dahin sagte die ganze Gruppe ab, sobald eine Kante
        # auf einer schmalen Fläche lag — an pegboard-goot war „senkrecht“ bei
        # jedem Radius über 0,37 mm unbenutzbar. Trägt keine Kante das Maß,
        # bleibt die Absage darunter.
        limits = contact_band_limits(
            entries,
            chosen,
            size,
            rounded=rounded,
            tolerance=tolerance,
            narrowest=narrowest,
            shape=shape,
            law=law,
        )
        narrow = [(entry, limits[id(entry)]) for entry in chosen if id(entry) in limits]
        if len(narrow) < len(chosen):
            chosen = [entry for entry in chosen if id(entry) not in limits]
        else:
            narrow = []
    largest = contact_band_limit(
        entries,
        chosen,
        size,
        rounded=rounded,
        tolerance=tolerance,
        narrowest=narrowest,
        shape=shape,
        law=law,
    )
    if largest is not None:
        raise too_large_for_the_faces(size, largest, rounded=rounded, varying=law is not None)
""",
)
swap(
    """    if skipped:
        outcome.findings.append(_skipped_finding(skipped, len(chosen)))
    return outcome
""",
    """    if skipped:
        outcome.findings.append(_skipped_finding(skipped, len(chosen)))
    if narrow:
        outcome.findings.append(
            too_narrow_finding(
                len(narrow),
                min(limit for _, limit in narrow),
                size,
                worked=len(chosen),
                rounded=rounded,
                varying=law is not None,
                place=narrow[0][0].points[0],
            )
        )
    return outcome
""",
)
swap(
    """def _skipped_finding(skipped: int, worked: int) -> Finding:""",
    '''def too_narrow_finding(
    skipped: int,
    largest: float,
    size: float,
    *,
    worked: int,
    rounded: bool,
    varying: bool = False,
    place: Sequence[float] | None = None,
) -> Finding:
    """Welche Kanten einer Gruppe das Maß nicht tragen — mit der Zahl, die dort passt.

    Derselbe Satz an beiden Kernen (RM-279 (ii)). *Stelle zeigen* fliegt zu
    einem Punkt auf der ersten ausgelassenen Kante (``place``; die Mitte
    eines Rings läge in der Luft), ``largest`` ist das kleinste der Maße, die
    an den ausgelassenen passen — darunter trägt jede von ihnen es.
    """
    from app.core.units import format_length

    shown = format_length(max(largest, 0.0))
    if varying:
        message = _(
            "Einige Kanten dieser Auswahl sind nicht verrundet: Neben ihnen ist die Fläche "
            "zu schmal für diese Radien. Dort passt nur ein größter Radius unter {largest}. "
            "Die übrigen Kanten sind verrundet. Soll die Rundung auch dort sitzen, "
            "verkleinern Sie die Radien.",
            largest=shown,
        )
    elif rounded:
        message = _(
            "Einige Kanten dieser Auswahl sind nicht verrundet: Neben ihnen ist die Fläche "
            "zu schmal für diesen Radius. Dort passt nur ein Radius unter {largest}. Die "
            "übrigen Kanten sind verrundet. Soll die Rundung auch dort sitzen, wählen Sie "
            "einen kleineren Radius.",
            largest=shown,
        )
    else:
        message = _(
            "Einige Kanten dieser Auswahl sind nicht gefast: Neben ihnen ist die Fläche zu "
            "schmal für diese Breite. Dort passt nur eine Breite unter {largest}. Die "
            "übrigen Kanten sind gefast. Soll die Fase auch dort sitzen, wählen Sie eine "
            "kleinere Breite.",
            largest=shown,
        )
    return Finding(
        code="edges.too_narrow",
        severity="warning",
        message=message,
        values={
            "skipped": skipped,
            "worked": worked,
            "size_mm": round(size, 3),
            "largest_mm": round(max(largest, 0.0), 3),
        },
        location=(
            (float(place[0]), float(place[1]), float(place[2])) if place is not None else None
        ),
        # Regel 17: der Ort, und das Maß steht im Schritt.
        suggestions=(SHOW_LOCATION, CORRECT_INPUT),
    )


def _skipped_finding(skipped: int, worked: int) -> Finding:''',
)
io.open(path, "w", encoding="utf-8", newline="").write(text)
print("ok")
