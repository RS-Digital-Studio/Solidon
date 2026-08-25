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
    """
    board = standards.board("skadis")
    spec = PARTS.get("pegboard_hook")
    straight = (board.slot_height - board.slot_width) / 2.0

    for play in (0.0, 0.25, 0.5):
        built = spec.fn(spec.params(count=1, play=play, plate=2.0))
        cut = built.mesh.raw.section(
            plane_origin=[0.0, 0.0, 2.0 + board.thickness / 2.0],
            plane_normal=[0.0, 0.0, 1.0],
        )
        assert cut is not None, f"play={play}: nothing crosses the board at all"
        points = np.asarray(cut.vertices, dtype=float)
        # Abstand zur Mittellinie des Langlochs: im geraden Teil senkrecht,
        # an den Enden radial um den Rundungsmittelpunkt.
        centre = np.clip(points[:, 1], -straight, straight)
        reach = np.hypot(points[:, 0], points[:, 1] - centre).max()
        assert reach <= board.slot_width / 2.0 + 1e-6, (
            f"play={play}: the shank reaches {reach:.3f} mm from the centre line, "
            f"the slot allows {board.slot_width / 2.0}"
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
    """
    board = standards.board("skadis")
    spec = PARTS.get("pegboard_hook")
    built = spec.fn(spec.params(count=1, play=0.0, plate=2.0))

    def span(height: float) -> tuple[float, float]:
        cut = built.mesh.raw.section(plane_origin=[0.0, 0.0, height], plane_normal=[0.0, 0.0, 1.0])
        assert cut is not None, f"nothing to measure at z={height}"
        y = np.asarray(cut.vertices, dtype=float)[:, 1]
        return float(y.min()), float(y.max())

    shank = span(2.0 + board.thickness / 2.0)
    nose = span(2.0 + board.thickness + 0.5)

    inserted = max(shank[1], nose[1]) - min(shank[0], nose[0])
    travel = board.slot_height - inserted
    assert travel > 2.0, (
        f"shank and nose together are {inserted:.2f} mm tall in a "
        f"{board.slot_height} mm slot — only {travel:.2f} mm left to sink"
    )
    assert nose[0] < shank[0] - 1.0, (
        "the nose does not reach below the shank, so it catches nothing"
    )
    assert shank[0] - nose[0] == pytest.approx(travel, abs=0.1), (
        f"the nose reaches {shank[0] - nose[0]:.2f} mm below the shank but the "
        f"hook can only sink {travel:.2f} mm — one of the two is wasted"
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


def test_the_hook_stands_off_the_face_by_plate_and_board(profile: Profile) -> None:
    """Wie weit er absteht, ist keine freie Zahl: Rückplatte plus Plattendicke
    plus Nase — und die letzten beiden kommen aus der Tabelle.

    Ein Einhänger, der zu kurz absteht, greift nicht hinter die Lochwand; einer,
    der zu weit absteht, hält das Teil auf Abstand von der Wand. Beides merkt
    der Kunde erst am gedruckten Teil, und deshalb steht die Zahl hier.
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
                params={"at_feature": "face_top", "count": 1, "plate": 2.0},
            )
        ],
    )
    after = evaluate(project.document, profile, sources=ProjectSources(project))
    stand = after.scene.objects["obj_1"].mesh.bounds.maximum[2] - box.maximum[2]

    # Rückplatte 2 + Plattendicke aus der Tabelle + Nase (zwei Drittel davon).
    expected = 2.0 + board.thickness + board.thickness * (2.0 / 3.0)
    assert stand == pytest.approx(expected, abs=0.4), (
        f"the hook stands off {stand:.1f} mm, expected about {expected:.1f} "
        f"(plate 2 + board {board.thickness} + lip)"
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
