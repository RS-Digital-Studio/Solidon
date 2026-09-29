"""(ii): die zwei Tests auf das neue Verhalten (einmaliges Umbauskript)."""

import io
import sys

TREE = sys.argv[1]


def patch(relative: str, old: str, new: str) -> None:
    path = f"{TREE}/{relative}"
    text = io.open(path, encoding="utf-8", newline="").read()
    assert text.count(old) == 1, (relative, old[:70], text.count(old))
    io.open(path, "w", encoding="utf-8", newline="").write(text.replace(old, new))


patch(
    "tests/test_mesh_edges.py",
    '''def test_both_kernels_refuse_what_does_not_fit_on_a_thin_wall(
    op: str, field: str, fits: float, too_large: float, kernel: str
) -> None:
    """Die oberen Kanten einer 3-mm-Wand, verrundet oder gefast: dieselbe Antwort
    an beiden Kernen (Übertrag der Durchsicht v0.4.1, Punkt 3).

    Auf der 3 mm breiten Stirnfläche treffen sich die Berührlinien beider
    Kanten, sobald das Maß die halbe Breite erreicht. Der exakte Kern lehnte
    ab 1,5 mm ab („Der Radius ist für diese Kanten zu groß."), das Netz rechnete
    weiter und machte die Wand still niedriger — gemessen am 22.09.2026: Fase
    2,9 mm ergab 18,6 statt 20 mm Höhe, Verrundung 2,0 mm 19,93 mm. Jetzt
    sagen beide dasselbe, mit dem größten Maß, das passt.
    """''',
    '''def test_both_kernels_leave_out_what_does_not_fit_on_a_thin_wall(
    op: str, field: str, fits: float, too_large: float, kernel: str
) -> None:
    """Die oberen Kanten einer 3-mm-Wand, verrundet oder gefast: dieselbe Antwort
    an beiden Kernen (Übertrag der Durchsicht v0.4.1, Punkt 3).

    Auf der 3 mm breiten Stirnfläche treffen sich die Berührlinien beider
    langen Kanten, sobald das Maß die halbe Breite erreicht. Der exakte Kern
    lehnte ab 1,5 mm ab, das Netz rechnete weiter und machte die Wand still
    niedriger — gemessen am 22.09.2026: Fase 2,9 mm ergab 18,6 statt 20 mm
    Höhe, Verrundung 2,0 mm 19,93 mm. Vom 23.09. an sagten beide für die
    ganze Gruppe ab, mit dem größten Maß, das passt.

    **Seit dem 28.09.2026 lässt die Gruppe die zwei langen Kanten aus und
    bearbeitet die zwei kurzen**, an beiden Kernen gleich (RM-279 (ii),
    Entscheidung der Release-Sitzung 0.5.1 nach Kundensicht, Robert gemeldet):
    An Kundenteilen mit einer einzigen schmalen Fläche war „senkrecht“ sonst
    bei jedem Radius unbenutzbar (pegboard-goot ab 0,37 mm). Die Wand bleibt
    20 mm hoch, und der Befund ``edges.too_narrow`` nennt die ausgelassenen
    mit dem größten Maß, das dort passt, und *Stelle zeigen*. Wer die lange
    Kante **einzeln** wählt, bekommt weiter die Absage.
    """''',
)
patch(
    "tests/test_mesh_edges.py",
    '''    fitted = run(op, entry, **{field: fits, "edges": "top"}).outputs[0]
    assert fitted.mesh.bounds.size[2] == pytest.approx(height, abs=1e-6)

    with pytest.raises(GeometryError) as refused:
        run(op, entry, **{field: too_large, "edges": "top"})
    assert refused.value.values["largest_mm"] == pytest.approx(1.5, abs=1e-6)
    assert "1.50 mm" in str(refused.value.detail) or "1,50 mm" in str(refused.value.detail)
''',
    '''    fitted = run(op, entry, **{field: fits, "edges": "top"})
    assert fitted.outputs[0].mesh.bounds.size[2] == pytest.approx(height, abs=1e-6)
    assert "edges.too_narrow" not in {finding.code for finding in fitted.findings}

    partly = run(op, entry, **{field: too_large, "edges": "top"})
    result = partly.outputs[0].mesh
    assert result.bounds.size[2] == pytest.approx(height, abs=1e-6), "keine still niedrigere Wand"
    assert result.volume < body.volume - 0.5, "die kurzen Kanten sind bearbeitet"
    narrow = next(finding for finding in partly.findings if finding.code == "edges.too_narrow")
    assert (narrow.values["skipped"], narrow.values["worked"]) == (2, 2)
    assert narrow.values["largest_mm"] == pytest.approx(1.5, abs=1e-3)
    assert "1.50 mm" in str(narrow.message) or "1,50 mm" in str(narrow.message)
    assert narrow.location is not None and abs(narrow.location[1]) == pytest.approx(1.5, abs=1e-3)
    assert [action.id for action in narrow.suggestions][:1] == ["show_location"]

    if kernel == "brep":
        from app.core.brep import edit as exact

        long_edge = next(
            e for e in exact.edges_of(body) if e.length > 30.0 and e.middle[2] > 19.0
        )
        key = exact.edge_key(long_edge)
    else:
        key = next(
            edge_key(e) for e in edges_of(body) if e.length > 30.0 and e.middle[2] > 9.0
        )
    with pytest.raises(GeometryError) as refused:
        run(op, entry, **{field: too_large, "edges": "named", "edge_keys": key})
    assert refused.value.values["largest_mm"] == pytest.approx(1.5, abs=1e-6)
''',
)
patch(
    "tests/test_brep.py",
    '''def test_the_same_radius_gets_the_same_answer_on_both_kernels() -> None:
    """Derselbe Radius, dieselbe Antwort — am Netz wie am exakten Körper.

    Gemessen am 14.09.2026 an einem Hohlkasten 40 x 30 x 20 mit 3 mm Wand
    (offen nach oben): Über **alle** Kanten nahm das Netz einen Radius von
    2 mm an, der exakte Kern sagte ihn ab, und ein Vorbehalt im Register
    erklärte den Unterschied. Am 22.09.2026 gemessen, *wie* das Netz ihn
    annahm: Zwei Bänder zu je 2 mm auf einer 3 mm breiten Stirnfläche
    überlappen, und die Wand kam still niedriger heraus. Seither stellen beide
    Kerne dieselbe Frage (``edges.contact_band_limit``) und sagen denselben
    Radius mit demselben größten Wert ab; der Vorbehalt über zwei Antworten
    ist gefallen.
    """''',
    '''def test_both_kernels_ask_the_same_question_of_a_thin_walled_box(profile: Profile) -> None:
    """Derselbe Radius, dieselbe Frage — am Netz wie am exakten Körper.

    Gemessen am 14.09.2026 an einem Hohlkasten 40 x 30 x 20 mit 3 mm Wand
    (offen nach oben): Über **alle** Kanten nahm das Netz einen Radius von
    2 mm an, der exakte Kern sagte ihn ab, und ein Vorbehalt im Register
    erklärte den Unterschied. Am 22.09.2026 gemessen, *wie* das Netz ihn
    annahm: Zwei Bänder zu je 2 mm auf einer 3 mm breiten Stirnfläche
    überlappen, und die Wand kam still niedriger heraus. Vom 23.09.2026 an
    stellten beide Kerne dieselbe Frage (``edges.contact_band_limit``) und
    sagten denselben Radius mit demselben größten Wert ab.

    **Seit dem 28.09.2026 lässt eine Gruppe die Kanten aus, die das Maß nicht
    tragen** (RM-279 (ii), Entscheidung der Release-Sitzung 0.5.1 nach
    Kundensicht, Robert gemeldet): Die Frage ist an beiden Kernen dieselbe
    (``edges.contact_band_limits``). Das Netz rundet hier 17 Kanten und nennt
    die vier ausgelassenen mit 1,5 mm; die Wand bleibt 20 mm hoch. Der exakte
    Kern fragt dasselbe, aber OpenCASCADE baut die verbleibenden 17 Kanten an
    diesem Kasten nicht — dort bleibt es bei der Absage mit demselben größten
    Wert. Gemessen am 28.09.2026 (``sonden\\\\kanten\\\\wand.py``).
    """''',
)
patch(
    "tests/test_brep.py",
    '''    netz = MeshData.of(tessellate(kasten.shape, 0.05).raw)
    with pytest.raises(GeometryError) as abgesagt:
        round_edges(netz, 2.0, "all", quality="draft")
    assert abgesagt.value.values["largest_mm"] == pytest.approx(1.5, abs=0.01)
    assert abgesagt.value.suggestions, "die Absage nennt einen Ausweg"
''',
    '''    exakt = SceneObject(id="obj_1", name="Kasten", mesh=kasten, kind="brep")
    with pytest.raises(GeometryError) as abgesagt:
        run("fillet_edges", exakt, profile, radius=2.0, edges="all")
    assert abgesagt.value.values["largest_mm"] == pytest.approx(1.5, abs=0.01)

    netz = MeshData.of(tessellate(kasten.shape, 0.05).raw)
    teils = round_edges(netz, 2.0, "all", quality="draft")
    ausgelassen = next(f for f in teils.findings if f.code == "edges.too_narrow")
    assert ausgelassen.values["largest_mm"] == pytest.approx(1.5, abs=0.01)
    assert (ausgelassen.values["skipped"], ausgelassen.values["worked"]) == (4, 17)
    assert ausgelassen.suggestions, "der Befund nennt einen Ausweg"
    assert teils.mesh.is_watertight
    assert teils.mesh.bounds.size[2] == pytest.approx(20.0, abs=1e-6)
''',
)
print("ok")
