"""Weg 1 aus Bauplan §2.2, an der Kundenanfrage entlang, die ihn ausgelöst hat.

Ein Kunde lädt ein Modell herunter — einen Halter, einen Behälter, was auch
immer — und will es an eine Lochwand hängen, ohne es nachzukonstruieren. Das
Konzept ``konzepte/konzept-befestigungssysteme-2026-08.md`` beschreibt den Weg
in sieben Schritten; hier steht, was davon der Kern prüfen kann.

**Was hier nicht geprüft wird und warum.** Die Schritte 2 und 3 sind Klicks —
eine Fläche wählen, den Eintrag im Kontextmenü finden. Beides hängt an einem
Fenster, und ein Test, der eines baut, hebt die Abrissquote der ganzen
Testdatei (gemessen am 24.08.2026: von 2 von 9 auf 2 von 3). Dass der
Lochwand-Einhänger im Kontextmenü einer Fläche **steht**, prüft
``test_parts.py`` über ``at_face``; dass das Menü ihn erreichbar zeigt, wurde
am echten Fenster nachgesehen. Was hier bleibt, ist die Kette dazwischen: aus
einer fremden Datei wird ein Körper mit benannten Flächen, und an eine davon
setzt sich der Einhänger.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge import profiles, standards
from app.core.knowledge.parts import PARTS
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Profile, Source

load_operations()

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def profile() -> Profile:
    return profiles.make_profile("centauri-carbon-2", "petg")


def _downloaded(name: str = "bracket_inch.stl", unit: str = "in") -> tuple[object, str]:
    """Ein Projekt mit einem eingelesenen Netz — der Kunde hat es gerade geladen.

    **Die Einheit steht hier, weil ``auto`` sie nicht raten darf.** Der Halter
    ist in Zoll gezeichnet; auf ``auto`` hält die Auswertung an und meldet
    ``AmbiguityError`` — genau das, was Regel 21 verlangt, und für den Kunden
    eine Rückfrage. Was hier als Parameter steht, ist seine Antwort.

    Und es ist mehr als eine Formalie: als Millimeter gelesen misst dasselbe
    Modell **4 × 2 × 0,2 mm** und trägt zwei Flächen. Ein Einhänger von 55 mm
    Breite daran wäre ein grüner Test über einen unsinnigen Fall. In Zoll sind
    es 101,6 × 50,8 × 6,3 mm und sechs Flächen — ein Halter, wie ihn jemand
    herunterlädt.
    """
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    project.sources["src_1"] = (MESHES / name).read_bytes()
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": unit})]
    )
    return project, "obj_1"


def test_a_model_without_a_unit_asks_instead_of_guessing(profile: Profile) -> None:
    """Schritt 1, und der Fall, in dem er nicht durchläuft (Regel 21).

    Der Halter ist in Zoll gezeichnet, und die Datei sagt es nicht — STL kennt
    keine Einheit. Auf ``auto`` **hält die Auswertung an**, statt eine zu
    wählen: Sie meldet eine Mehrdeutigkeit, und der Kunde entscheidet.

    Der Test steht hier und nicht bei den Ladeoperationen, weil er zu diesem
    Weg gehört: Wer ein fremdes Modell an eine Wand hängen will, trifft diese
    Frage als Erstes, und eine falsch geratene Antwort macht aus einem Halter
    ein Teil von vier Millimetern.
    """
    project, _obj = _downloaded(unit="auto")
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert not result.complete, "an ambiguous unit must stop the evaluation"
    assert not result.scene.objects, "nothing should be built on a guess"
    assert result.scene.report.findings, "stopping without a finding leaves the user blind"


def test_a_downloaded_model_gets_hooks_in_one_step(profile: Profile) -> None:
    """Schritt 1 bis 5: geladen, eine Fläche gewählt, Einhänger gesetzt.

    Der Kern der Zusage steckt in einer Zahl: **ein** Schritt im Stapel. Der
    Kunde hat nicht zwei Haken einzeln gesetzt und danach vereinigt, sondern
    einmal geklickt — und ein Undo nimmt es vollständig zurück (Regel 16).
    """
    project, obj = _downloaded()
    first = evaluate(project.document, profile, sources=ProjectSources(project))
    before = first.scene.objects[obj].mesh.volume
    faces = [fid for fid, f in first.scene.objects[obj].features.items() if f.kind == "face"]
    assert faces, "the downloaded model has no named faces to hang it by"

    History(project.document).apply(
        "Einhänger",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=(obj,),
                params={"at_feature": faces[0], "count": 2},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    body = result.scene.objects[obj].mesh
    assert body.volume > before, "the hooks did not add anything"
    assert body.is_watertight, "the model with hooks is not printable"
    assert body.component_count == 1, "the hooks did not grow together with the model"
    assert len(project.document.ops) == 2, "loading and hanging should be two steps, not more"


def test_the_hooks_keep_the_grid_of_the_board(profile: Profile) -> None:
    """Was der Kunde nicht nachmessen soll: den Rasterabstand.

    Gemessen wird an den **benannten Merkmalen** und nicht am Hüllquader. Die
    erste Fassung dieses Tests rechnete ``bounds.size[0] - 3 * slot_width`` —
    dieselbe Formel, die der Baustein benutzt, nur rückwärts. Ein Test, der die
    Formel des Prüflings nachrechnet, prüft, ob sie sich geändert hat, nicht ob
    sie stimmt (``.claude/memory/sollwert-aus-dem-pruefling.md``). Der
    Rasterabstand kommt aus der Tabelle; die Zapfen stehen dort, wo die
    Merkmale es sagen.
    """
    board = standards.board("skadis")
    spec = PARTS.get("pegboard_hook")

    for count in (1, 2, 3):
        built = spec.fn(spec.params(count=count))
        hooks = sorted(
            (
                f.params["centre"][0]
                for name, f in built.features.items()
                if name.startswith("hook_")
            ),
        )
        assert len(hooks) == count, f"{count} hooks asked for, {len(hooks)} named"
        for left, right in itertools.pairwise(hooks):
            assert right - left == pytest.approx(board.pitch, abs=0.01), (
                f"neighbouring hooks sit {right - left:.2f} mm apart, the grid says {board.pitch}"
            )


def test_the_shank_fits_the_rounded_slot_and_not_just_its_bounding_box(
    profile: Profile,
) -> None:
    """Der Schlitz hat runde Enden, und daran ist die erste Fassung gescheitert.

    **Ein Hüllquader ist keine Passung.** Ein Rechteck von 4,75 mal 14,75 mm
    liegt vollständig im Hüllquader einer 5-mal-15-Öffnung und trotzdem
    außerhalb der Öffnung: Weil deren Enden Halbkreise mit 2,5 mm Radius sind,
    steht jede Ecke des Rechtecks 0,86 mm über die Rundung hinaus. Erst beim
    größten zulässigen Spiel von 1,5 mm ginge es hinein — und dann sitzt ein
    3,5-mm-Zapfen in einem 5-mm-Schlitz und wackelt.

    Gemessen wird deshalb ein echter **Querschnitt** in der Mitte der Lochwand,
    Punkt für Punkt gegen die Stadionform. Vertices allein genügen nicht: Ein
    extrudierter Zapfen hat auf halber Höhe keine.

    **Und die Öffnung steht nicht auf y = 0.** Seit der Rastzunge sitzt neben
    dem Zapfen noch etwas im Schlitz, und zwar oberhalb von ihm; wer den
    Querschnitt gegen ein Langloch um den Ursprung misst, misst dann die Lage
    des Hakens im Schlitz mit. Die Frage ist aber, ob er **bei irgendeiner
    Höhe** hineingeht — geprüft wird deshalb über den Versatz, und zwar mit
    demselben Verfahren, das ``test_parts.py`` für die Verriegelung benutzt.
    """
    board = standards.board("skadis")
    spec = PARTS.get("pegboard_hook")
    straight = (board.slot_height - board.slot_width) / 2.0

    for play, latch in itertools.product((0.0, 0.25, 0.5), (False, True)):
        built = spec.fn(spec.params(count=1, play=play, plate=2.0, latch=latch))
        cut = built.mesh.raw.section(
            plane_origin=[0.0, 0.0, board.thickness / 2.0],
            plane_normal=[0.0, 0.0, 1.0],
        )
        assert cut is not None, f"play={play}: nothing crosses the board at all"
        points = np.asarray(cut.vertices, dtype=float)
        # Abstand zur Mittellinie des Langlochs: im geraden Teil senkrecht,
        # an den Enden radial um den Rundungsmittelpunkt — für jede Höhe, in
        # der das Loch stehen kann, und es genügt eine, die trägt.
        passt = False
        for shift in np.arange(-board.slot_height, board.slot_height, 0.05):
            y = points[:, 1] + shift
            centre = np.clip(y, -straight, straight)
            reach = float(np.hypot(points[:, 0], y - centre).max())
            passt = passt or reach <= board.slot_width / 2.0 + 1e-6
        assert passt, (
            f"play={play} latch={latch}: the shank reaches past the "
            f"{board.slot_width / 2.0} mm the slot allows, at every height"
        )


def test_the_hook_has_room_to_sink_and_the_nose_catches(profile: Profile) -> None:
    """Eingehängt wird in zwei Zügen, und der zweite braucht Platz.

    Zapfen und Nase gehen gemeinsam durch den Schlitz; danach sinkt der Haken,
    bis die Nase hinter dem Steg unter der Öffnung liegt. Was er dabei sinken
    kann, ist genau das, was der Schlitz höher ist als beide zusammen.

    **Die erste Fassung ließ dafür 0,25 mm.** Zapfen und Nase standen auf der
    vollen nutzbaren Schlitzhöhe, und die Nase griff danach um ein Viertel
    Millimeter hinter die Platte — geometrisch vorhanden, praktisch nutzlos.
    Der Fehler war im gebauten Körper nicht zu sehen: Er war wasserdicht,
    einteilig und maß in jeder Richtung, was er sollte.

    **Gemessen ohne Rastzunge, und das ist hier die Sache selbst.** Der Weg zum
    Absinken ist der Weg, auf dem sich der Haken auch wieder löst; die Zunge
    sperrt ihn, sie verkürzt ihn nicht. Was sie ändert, ist die Rechnung
    darunter: Mit ihr steht über dem Zapfen noch etwas im Schlitz, und der Hub
    folgt nicht mehr aus „Schlitzhöhe minus alles zusammen", sondern aus dem
    Abstand zwischen Zapfenunterkante und Nasenunterkante. Beides prüft
    ``test_parts.py`` an der Zunge; hier bleibt die Aufteilung, aus der beides
    hervorgeht.
    """
    board = standards.board("skadis")
    spec = PARTS.get("pegboard_hook")
    built = spec.fn(spec.params(count=1, play=0.0, plate=2.0, latch=False))

    def span(height: float) -> tuple[float, float]:
        cut = built.mesh.raw.section(plane_origin=[0.0, 0.0, height], plane_normal=[0.0, 0.0, 1.0])
        assert cut is not None, f"nothing to measure at z={height}"
        y = np.asarray(cut.vertices, dtype=float)[:, 1]
        return float(y.min()), float(y.max())

    shank = span(board.thickness / 2.0)
    nose = span(board.thickness + 0.5)

    inserted = max(shank[1], nose[1]) - min(shank[0], nose[0])
    travel = board.slot_height - inserted
    assert travel > 2.0, (
        f"shank and nose together are {inserted:.2f} mm tall in a "
        f"{board.slot_height} mm slot — only {travel:.2f} mm left to sink"
    )
    # Und derselbe Hub, anders gefragt: Wie weit die Nase unter dem Zapfen
    # steht, ist das, was der Haken sinken kann, bis sie hinter dem Steg liegt.
    # Diese Form gilt auch mit Zunge — sie ist der Grund, dass die Zunge den
    # Hub nicht kostet.
    mit_zunge = spec.fn(spec.params(count=1, play=0.0, plate=2.0))
    tief = mit_zunge.mesh.raw.section(
        plane_origin=[0.0, 0.0, board.thickness + 0.5], plane_normal=[0.0, 0.0, 1.0]
    )
    unten = float(np.asarray(tief.vertices, dtype=float)[:, 1].max())
    assert unten - shank[1] == pytest.approx(travel, abs=0.1), (
        f"with the latch the nose reaches {unten - shank[1]:.2f} mm past the shank, "
        f"without it the hook sinks {travel:.2f} mm — the latch took the sink away"
    )

    # **Im eigenen System des Bausteins ist oben -Y** und unten +Y — die
    # Konvention von ``axis="y"``, der auch ``PartSpec.keeps_up`` folgt. Die
    # Nase ragt also nach **+Y** über den Zapfen hinaus, und am -Y-Ende enden
    # beide bündig. Diese Prüfung stand einen Nachmittag lang andersherum, weil
    # der Baustein selbst es andersherum baute; gefangen hat den Wechsel nicht
    # sie, sondern das Schlüsselloch, das an derselben Regel hing.
    assert nose[1] > shank[1] + 1.0, "the nose does not reach past the shank, so it catches nothing"
    assert nose[1] - shank[1] == pytest.approx(travel, abs=0.1), (
        f"the nose reaches {nose[1] - shank[1]:.2f} mm past the shank but the "
        f"hook can only sink {travel:.2f} mm — one of the two is wasted"
    )
    assert nose[0] == pytest.approx(shank[0], abs=0.3), (
        f"nose and shank start at {nose[0]:.2f} and {shank[0]:.2f} at the top — "
        "they should finish flush, or the nose sits on the wrong end"
    )


# --- Sitzt der Haken sinnvoll? --------------------------------------------------


BOX_FACES = [
    # Alle sechs, auch die Unterseite: Ein Einhänger dort ist unsinnig, und
    # genau deshalb steht sie hier — die Richtung muss auch dann stimmen, wenn
    # die Wahl es nicht tut. Gemessen wächst sie um -10,56 in Z und um null
    # nach oben, wie jede andere.
    ("face_1", (0.0, 0.0, -1.0)),
    ("face_3", (0.0, -1.0, 0.0)),
    ("face_4", (0.0, 1.0, 0.0)),
    ("face_5", (-1.0, 0.0, 0.0)),
    ("face_6", (1.0, 0.0, 0.0)),
    ("face_top", (0.0, 0.0, 1.0)),
]


@pytest.mark.parametrize(("face", "normal"), BOX_FACES, ids=[f[0] for f in BOX_FACES])
def test_the_hook_grows_outward_and_never_inward(
    face: str, normal: tuple[float, float, float], profile: Profile
) -> None:
    """Ein Baustein, der nach innen wächst, steckt im Teil statt daran.

    **Das ist die Frage, die „das Volumen ist gewachsen" nicht beantwortet.**
    Ein Einhänger, der in den Körper hineinragt, erzeugt genauso mehr Volumen
    wie einer, der nach außen steht — er hält nur nichts. Geprüft wird deshalb
    die **Richtung**: Der Hüllquader darf sich nur auf der Seite ausdehnen, in
    die die angeklickte Fläche schaut, und auf der Gegenseite um keinen
    Millimeter.

    Gemessen an einem Quader, weil dessen Flächen ihre Normalen kennen: 40 × 30
    × 10 mm, sechs benannte Flächen, jede in eine Achsrichtung. Was hier gilt,
    gilt an einem heruntergeladenen Netz genauso — dort heißen die Flächen nur
    nicht so ordentlich.
    """
    # **Ein Träger, der breiter ist als der Baustein.** Die Vorgabe von
    # ``create_box`` misst 40 auf 30 auf 10, zwei Haken im Raster sind 51 mm breit —
    # der Baustein ragte also über jede Kante hinaus und schnitt beim Setzen
    # durch die Nachbarflächen. Die Zuordnung fand dann zwei gleich gute
    # Kandidaten und hielt an („Die Angabe ist nicht eindeutig"). Das ist ein
    # eigener Fall und gehört in einen eigenen Test; hier geht es um die
    # Richtung, und dafür braucht es einen Träger, der den Haken trägt.
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 120.0, "depth": 90.0, "height": 40.0})],
    )
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    box = before.scene.objects["obj_1"].mesh.bounds

    History(project.document).apply(
        "Einhänger",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=("obj_1",),
                params={"at_feature": face, "count": 2},
            )
        ],
    )
    after = evaluate(project.document, profile, sources=ProjectSources(project))
    assert after.complete, [f.message for f in after.scene.report.findings]
    grown = after.scene.objects["obj_1"].mesh.bounds

    for axis in range(3):
        below = box.minimum[axis] - grown.minimum[axis]
        above = grown.maximum[axis] - box.maximum[axis]

        if normal[axis] > 0.0:
            assert above > 1.0, f"{face}: nothing grew along the face normal on axis {axis}"
            assert below == pytest.approx(0.0, abs=0.01), (
                f"{face}: the hook reaches into the body on axis {axis}"
            )
        elif normal[axis] < 0.0:
            assert below > 1.0, f"{face}: nothing grew along the face normal on axis {axis}"
            assert above == pytest.approx(0.0, abs=0.01), (
                f"{face}: the hook reaches into the body on axis {axis}"
            )
        else:
            # **Quer zur Normalen muss es symmetrisch sein**, und diese Zeile
            # ist die schärfste des Tests. Ohne sie blieb er grün, als eine
            # Probe die Flächennormale verwarf: Der Einhänger stand dann in der
            # Vorgabeachse Z statt in der Fläche — er wuchs *trotzdem* nach
            # außen, weil er am Flächenmittelpunkt sitzt, nur eben schief. In
            # Zahlen war der Unterschied 0,0/+5,6 gegen -7,4/+7,4.
            assert below == pytest.approx(above, abs=0.05), (
                f"{face}: the hook sits lopsided on axis {axis} — {below:.1f} below "
                f"against {above:.1f} above; it is not aligned with the face"
            )


def test_the_hook_stands_off_the_face_by_the_board_alone(profile: Profile) -> None:
    """Wie weit er absteht, ist keine freie Zahl — und die Rückplatte zählt nicht mit.

    Ein Einhänger, der zu kurz absteht, greift nicht hinter die Lochwand; einer,
    der zu weit absteht, hält das Teil auf Abstand von der Wand. Beides merkt
    der Kunde erst am gedruckten Teil.

    **Die Rückplatte stand einmal dazwischen**, und seit dem 25.08.2026 tut sie
    das nicht mehr: Sie ist die Ausnahme statt die Vorgabe, und wer eine
    bestellt, bekommt sie im Träger liegend. Der Abstand kommt damit allein aus
    der Tabelle — Plattendicke plus Nase — und ändert sich nicht mehr, wenn
    jemand an der Rückplatte dreht. Genau das prüft der zweite Teil.

    **Mit Rastzunge kommt eine Armlänge dazu, und die ist keine freie Zahl
    mehr, sondern eine gerechnete.** Ein Federarm trägt zehnmal so lang wie
    dick (``SNAP_RATIO``), sonst bricht er statt zu federn; die Zunge läuft
    neben dem Zapfen nach hinten und endet dort, wo diese Länge erreicht ist.
    Gemessen sind das anderthalb Millimeter mehr, und sie liegen **hinter** der
    Lochwand, wo Luft ist — vom Teil zur Wand ändert sich nichts. Geprüft wird
    hier deshalb beides: die Zusage von vorher, wenn die Zunge aus ist, und die
    Grenze mit ihr.
    """
    board = standards.board("skadis")
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    box = before.scene.objects["obj_1"].mesh.bounds

    History(project.document).apply(
        "Einhänger",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "count": 1, "latch": False},
            )
        ],
    )
    after = evaluate(project.document, profile, sources=ProjectSources(project))
    assert after.complete, [str(f.message) for f in after.scene.report.findings]
    stand = after.scene.objects["obj_1"].mesh.bounds.maximum[2] - box.maximum[2]

    # Plattendicke aus der Tabelle plus Nase (zwei Drittel davon).
    expected = board.thickness + board.thickness * (2.0 / 3.0)
    assert stand == pytest.approx(expected, abs=0.4), (
        f"the hook stands off {stand:.1f} mm, expected about {expected:.1f} "
        f"(board {board.thickness} + lip)"
    )

    # Mit Zunge kommt der Federarm dazu, und nicht mehr: Zehn Armstärken plus
    # Wurzel und Anlaufschräge sind das, was ein Federarm braucht — wer hier
    # mehr misst, hat einen Zapfen gebaut, der das Teil auf Abstand hält.
    mit_zunge = new_project("centauri-carbon-2", "petg")
    History(mit_zunge.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    History(mit_zunge.document).apply(
        "Einhänger",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "count": 1},
            )
        ],
    )
    verriegelt = evaluate(mit_zunge.document, profile, sources=ProjectSources(mit_zunge))
    assert verriegelt.complete, [str(f.message) for f in verriegelt.scene.report.findings]
    tief = verriegelt.scene.objects["obj_1"].mesh.bounds.maximum[2] - box.maximum[2]
    assert expected <= tief <= expected + 2.0, (
        f"with the latch the hook reaches {tief:.1f} mm instead of {expected:.1f} — "
        "that is more than a spring arm costs"
    )

    # Und eine bestellte Rückplatte ändert daran nichts: Sie liegt im Träger.
    with_plate = new_project("centauri-carbon-2", "petg")
    History(with_plate.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    History(with_plate.document).apply(
        "Einhänger",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "count": 1, "plate": 3.0, "latch": False},
            )
        ],
    )
    thick = evaluate(with_plate.document, profile, sources=ProjectSources(with_plate))
    assert thick.complete, [str(f.message) for f in thick.scene.report.findings]
    raised = thick.scene.objects["obj_1"].mesh.bounds.maximum[2] - box.maximum[2]
    assert raised == pytest.approx(stand, abs=0.05), (
        f"a 3 mm back plate raised the hook from {stand:.2f} to {raised:.2f} mm — "
        "it is supposed to sit inside the part, not under the hooks"
    )

    # Mit Zunge gilt dieselbe Zusage in der Richtung, auf die es ankommt: Die
    # Platte hebt den Haken nicht an. Gleich lang wird er dabei nicht — der
    # Federarm wird an der Plattenoberseite frei statt an seiner eigenen
    # Wurzel und endet dadurch um eine Armstärke früher.
    History(mit_zunge.document).apply(
        "Einhänger mit Platte",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "count": 1, "plate": 3.0},
            )
        ],
    )
    beides = evaluate(mit_zunge.document, profile, sources=ProjectSources(mit_zunge))
    assert beides.complete, [str(f.message) for f in beides.scene.report.findings]
    hoch = beides.scene.objects["obj_1"].mesh.bounds.maximum[2] - box.maximum[2]
    assert hoch <= tief + 0.05, (
        f"a 3 mm back plate raised the latched hook from {tief:.2f} to {hoch:.2f} mm"
    )


def test_the_hook_reaches_the_customer_through_the_catalogue() -> None:
    """Der Weg, den der Kunde nimmt: Katalog aufschlagen, Baustein finden.

    Ein Baustein, den man nur kennt, wenn man seinen Namen kennt, ist für den
    Kunden nicht da — §24.3 sagt es so: „Eine Bibliothek, die man nicht sieht,
    existiert für den Nutzer nicht." Geprüft wird deshalb, was der Katalog über
    ihn weiß: Gruppe, Titel, Beschreibung, und ein Bild, das aus ihm selbst
    gerendert wird und nicht von Hand gepflegt ist.
    """
    from app.core.knowledge.parts import PARTS, preview
    from app.core.knowledge.parts.registry import GROUPS

    spec = PARTS.get("pegboard_hook")

    assert spec.group in GROUPS, "the hook sits in a group the catalogue does not show"
    assert str(spec.title) != spec.name, "the catalogue would show the key, not a name"
    assert str(spec.doc), "no description means a tile the customer cannot judge"
    assert str(spec.caveat), "a part without a caveat never says where it is the wrong choice"

    picture = preview.render(spec)
    assert picture.triangles > 0, "the preview is empty"
    assert picture.svg.startswith("<svg"), "the preview is not an image"
