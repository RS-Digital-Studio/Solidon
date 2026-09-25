"""Einmalig: loader.normalise Schritt 2–4b an die Reparatur angleichen."""

from pathlib import Path

path = Path("app/core/ingest/loader.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str) -> None:
    global text
    assert text.count(old) == 1, old[:80]
    text = text.replace(old, new, 1)


# Dieselben Sätze wie die Reparatur — ein Satz je Sache, eine Katalogzeile.
swap(
    '''                    message=_(
                        "Doppelte Punkte blieben stehen — sie zu verschweißen hätte das "
                        "geschlossene Netz aufgerissen."
                    ),
                    values={"tolerance": format_length(tolerance)},''',
    '''                    message=_(
                        "Doppelte Punkte blieben stehen, weil das Verschweißen das Modell "
                        "aufgerissen hätte."
                    ),
                    values={"tolerance": tolerance},''',
)
swap(
    '''        progress(0.4, str(_("Entartete Dreiecke entfernen")))''',
    '''        progress(0.4, str(_("Leere Dreiecke entfernen")))''',
)
swap(
    '''                    message=_(
                        "Entartete Dreiecke blieben stehen — sie zu entfernen hätte das "
                        "geschlossene Netz aufgerissen."
                    ),
                    values={"kept": kept},''',
    '''                    message=_(
                        "Leere Dreiecke blieben stehen, weil ihr Entfernen das Modell "
                        "aufgerissen hätte."
                    ),
                    values={"kept": kept},''',
)
swap(
    '''                    message=_("Entartete Dreiecke wurden entfernt."),''',
    '''                    message=_("Leere Dreiecke wurden entfernt."),''',
)

# Schritt 4: dieselbe Außenregel wie die Reparatur.
swap(
    '''    if unify_normals and len(body.faces):
        progress(0.6, str(_("Außenseiten angleichen")))
        faces_before = np.array(body.faces, copy=True)
        trimesh.repair.fix_winding(body)
        if closed:
            trimesh.repair.fix_inversion(body)
        if not np.array_equal(np.asarray(body.faces), faces_before):
            findings.append(
                Finding(
                    code="ingest.normals_flipped",
                    severity="info",
                    message=_("Die Ausrichtung der Flächen wurde korrigiert."),
                )
            )
''',
    '''    # **Außen ist je Schale, nicht je Körper** — dieselbe Regel wie die
    # Reparatur (:func:`app.core.geom.repair.turn_shells_outward`), nicht mehr
    # ``trimesh.repair.fix_inversion``, das nur das Gesamtvolumen fragt. Zwei
    # Stellen für dieselbe Frage hatten zwei Antworten: Die Reparatur richtete
    # einen umgestülpten Würfel neben einem richtigen, der Import nicht.
    from app.core.geom.repair import turn_shells_outward

    flipped = False
    if unify_normals and len(body.faces):
        progress(0.6, str(_("Außenseiten angleichen")))
        faces_before = np.array(body.faces, copy=True)
        trimesh.repair.fix_winding(body)
        if closed:
            turn_shells_outward(body)
        flipped = not np.array_equal(np.asarray(body.faces), faces_before)
        if flipped:
            findings.append(
                Finding(
                    code="ingest.normals_flipped",
                    severity="info",
                    message=_("Die Außenseiten wurden angeglichen."),
                )
            )
''',
)

# Schritt 4b: nach dem Schließen die Außenfrage stellen; Befunde nicht doppeln.
swap(
    '''    if mend and weld and len(body.faces) and (closed is False or not body.is_watertight):
        from app.core.geom.repair import repair as repair_mesh

        progress(0.7, str(_("Offene Stellen schließen")))
        mended = repair_mesh(
            MeshData(raw=body, slots=tuple(int(slot) for slot in slots))
            if slots is not None and len(slots) == len(body.faces)
            else mesh.replacing(body),
            # Was hier schon gelaufen ist, läuft nicht zweimal.
            weld=False,
            degenerate=False,
            normals=False,
        )
        if mended.changed:''',
    '''    mended_here = False
    if mend and weld and len(body.faces) and (closed is False or not body.is_watertight):
        from app.core.geom.repair import repair as repair_mesh

        progress(0.7, str(_("Offene Stellen schließen")))
        mended = repair_mesh(
            MeshData(raw=body, slots=tuple(int(slot) for slot in slots))
            if slots is not None and len(slots) == len(body.faces)
            else mesh.replacing(body),
            # Was hier schon gelaufen ist, läuft nicht zweimal — die
            # Außenseiten aber doch: **Erst am geschlossenen Netz lässt sich
            # fragen, wo außen ist** (Durchsicht 24.09.2026). Schritt 4 sah das
            # Netz offen, ``fix_winding`` richtete es nach seinem Bezugsdreieck,
            # und lag das falsch, kam der Körper geschlossen und umgestülpt an
            # — Volumen −8 000 an einem Würfel, und der Bericht sagte
            # „korrigiert".
            weld=False,
            degenerate=False,
            normals=True,
        )
        mended_here = True
        if flipped:
            # Eine Zeile für die Außenseiten, auch wenn beide Stufen richten.
            mended = dataclasses.replace(
                mended,
                findings=[
                    entry for entry in mended.findings if entry.code != "repair.normals_flipped"
                ],
            )
        if mended.changed:''',
)
swap(
    '''            closed = bool(body.is_watertight)
            findings.extend(mended.findings)
''',
    '''            closed = bool(body.is_watertight)
        findings.extend(mended.findings)
''',
)

# Schritt 6: Orte der Befunde wandern mit dem Körper.
swap(
    '''        body.apply_translation(bed_offset(box, place_on_bed=place_on_bed, centre=centre))
''',
    '''        offset = bed_offset(box, place_on_bed=place_on_bed, centre=centre)
        body.apply_translation(offset)
        # Ein Befund mit Ort — die große Öffnung der Reparatur — zeigt auf die
        # Stelle am Körper, und der steht jetzt woanders.
        findings = [
            dataclasses.replace(
                entry,
                location=(
                    entry.location[0] + float(offset[0]),
                    entry.location[1] + float(offset[1]),
                    entry.location[2] + float(offset[2]),
                ),
            )
            if entry.location is not None
            else entry
            for entry in findings
        ]
''',
)

# „Nicht geschlossen" nur, wo die Reparatur nicht gelaufen ist.
swap(
    '''    if not closed and len(body.faces):
        # Der Satz steht nur noch, wo die Reparatur oben nicht durchkam — sie
        # läuft vorher und schließt, was zu schließen ist.
        findings.append(''',
    '''    if not closed and len(body.faces) and not mended_here:
        # Der Satz steht nur noch, wo die Reparatur oben nicht lief — etwa mit
        # „Offene Stellen schließen" aus. Lief sie und blieb etwas offen, sagt
        # sie es selbst, mit der Zahl der Stellen (``repair.still_open``,
        # ``repair.no_thickness``); zwei Zeilen über dieselben Ränder waren
        # eine zu viel, und „Reparieren" hätte dieselben Mittel noch einmal
        # versucht (Durchsicht 24.09.2026).
        findings.append(''',
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
