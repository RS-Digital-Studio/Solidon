"""Der Skeletteditor im Fenster (Konzept P16 §7.5).

Dieselbe Bauart wie die Formsitzung: ein Werkzeugmodus, eine Leiste neben der
Werkzeugzeile, ein Zustand im Fenster, eine Operation am Ende. Was ihn
unterscheidet, ist die Arbeitsteilung dahinter — **hier werden Gesten
gesammelt, die Stellung selbst ist eine Zahl.**

Zwei Klicks machen einen Knochen: erst das Gelenk, dann das Ende. Die Winkel
setzt niemand mit der Maus; sie stehen im Dialog der Operation, wo auch ein
Projektparameter erlaubt ist. Das ist der Punkt, an dem Posing hierher gehört
und nicht zu einem Animationsprogramm.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.geom.pose import armature_from_text
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    return MainWindow(Session(), UiSettings())


def with_a_body(window: MainWindow) -> str:
    """Die saubere Figur aus dem Korpus — ein Körper, der ein Skelett verdient."""
    window.open_path(MESHES / "clean_figure.stl")
    window.session.wait_for_idle()
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    object_id = window.object_tree.selected()
    assert object_id
    return str(object_id)


def bone(
    window: MainWindow, head: tuple[float, float, float], tail: tuple[float, float, float]
) -> None:
    """Ein Knochen sind zwei Klicks."""
    window._on_bone_point(head)
    window._on_bone_point(tail)


# --- hinein und heraus ----------------------------------------------------------


def test_the_session_needs_something_to_hang_bones_in(window: MainWindow) -> None:
    window.start_armature()

    assert not window.setting_armature()
    assert not window.pose_bar.isVisible()


def test_starting_shows_the_bar_and_hides_the_view_tools(window: MainWindow) -> None:
    object_id = with_a_body(window)

    window.start_armature(object_id)

    assert window.setting_armature()
    assert window.pose_bar.isVisibleTo(window)
    assert not window.tools.isVisibleTo(window)


def test_two_sessions_do_not_open_at_once(window: MainWindow) -> None:
    """Wer formt, setzt kein Skelett — und umgekehrt.

    Ein Modus, der beides gleichzeitig kann, kann keines von beidem
    verlässlich: Derselbe Klick müsste zwei Dinge bedeuten.
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)

    window.start_armature(object_id)

    assert not window.setting_armature()
    assert window.sculpting()


# --- Knochen setzen -------------------------------------------------------------


def test_two_clicks_make_one_bone(window: MainWindow) -> None:
    """Erst das Gelenk, dann das Ende."""
    object_id = with_a_body(window)
    window.start_armature(object_id)

    window._on_bone_point((0.0, 0.0, 0.0))
    assert not window._armature_bones, "nach einem Klick steht noch kein Knochen"

    window._on_bone_point((0.0, 0.0, 20.0))
    assert len(window._armature_bones) == 1
    assert window._armature_bones[0].head == (0.0, 0.0, 0.0)
    assert window._armature_bones[0].tail == (0.0, 0.0, 20.0)


def test_the_next_bone_hangs_on_the_one_before(window: MainWindow) -> None:
    """Ein Skelett ist meistens eine Kette.

    Wer für jeden Knochen sein Elternteil wählen muss, klickt dreimal so oft
    wie nötig.
    """
    object_id = with_a_body(window)
    window.start_armature(object_id)

    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    bone(window, (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))

    assert window._armature_bones[0].parent == ""
    assert window._armature_bones[1].parent == window._armature_bones[0].name


def test_a_new_chain_hangs_on_nothing(window: MainWindow) -> None:
    """Für den zweiten Arm — sonst wächst alles an einer Kette weiter."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))

    window.break_armature_chain()
    bone(window, (10.0, 0.0, 0.0), (20.0, 0.0, 0.0))

    assert window._armature_bones[1].parent == ""


def test_a_name_is_used_once_and_then_forgotten(window: MainWindow) -> None:
    """Ein stehen gebliebener Name wäre der Name des nächsten Knochens.

    Zwei Knochen mit demselben Namen sind ein Skelett, dessen Stellung niemand
    mehr zuordnet — die Winkel stehen je Name.
    """
    object_id = with_a_body(window)
    window.start_armature(object_id)

    window.pose_bar.name.setText("oberarm")
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    bone(window, (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))

    assert window._armature_bones[0].name == "oberarm"
    assert window._armature_bones[1].name != "oberarm"
    assert not window.pose_bar.name.text()


def test_a_repeated_name_is_made_unique(window: MainWindow) -> None:
    """Auch wenn jemand denselben Namen zweimal tippt."""
    object_id = with_a_body(window)
    window.start_armature(object_id)

    window.pose_bar.name.setText("arm")
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    window.pose_bar.name.setText("arm")
    bone(window, (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))

    names = [entry.name for entry in window._armature_bones]
    assert len(set(names)) == 2, f"zwei Knochen, zwei Namen: {names}"


# --- zurücknehmen ---------------------------------------------------------------


def test_undo_takes_back_the_half_set_bone_first(window: MainWindow) -> None:
    """Sonst nähme das erste Strg+Z einen fertigen Knochen und ließe den
    angefangenen stehen."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    window._on_bone_point((0.0, 0.0, 20.0))

    window.action_undo()

    assert window._armature_head is None
    assert len(window._armature_bones) == 1, "der fertige Knochen steht noch"


def test_undo_then_takes_back_a_whole_bone(window: MainWindow) -> None:
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    bone(window, (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))
    before = len(window.session.project.document.ops)

    window.action_undo()

    assert len(window._armature_bones) == 1
    assert len(window.session.project.document.ops) == before, "der Verlauf bleibt unberührt"


# --- was dabei herauskommt ------------------------------------------------------


def test_finishing_opens_the_dialog_with_the_skeleton(window: MainWindow) -> None:
    """„Fertig" gibt an den Operationsdialog ab, wie es die Skizze vormacht.

    Vorher legte es eine Operation mit leerer Stellung an: nichts geschah,
    ohne Ansage, und weiter ging es nur über Verlauf → Doppelklick → JSON.
    Der Dialog öffnet mit gesetztem Skelett — die Winkel sind der nächste
    Handgriff, dort darf auch ein Projektparameter stehen.
    """
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    bone(window, (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))
    before = len(window.session.project.document.ops)

    window.finish_armature()

    assert len(window.session.project.document.ops) == before, (
        "eine Operation mit leerer Stellung täte nichts — erst der Dialog"
    )
    dialog = window._op_dialog
    assert dialog is not None
    bones = armature_from_text(str(dialog.values()["armature"]))
    assert len(bones) == 2
    assert bones[1].parent == bones[0].name


def test_accepting_the_dialog_writes_one_operation(window: MainWindow) -> None:
    """Regel 16: Der ganze Vorgang ist eine Transaktion."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    before = len(window.session.project.document.ops)

    window.finish_armature()
    dialog = window._op_dialog
    assert dialog is not None
    dialog.accept()

    ops = window.session.project.document.ops
    assert len(ops) == before + 1
    assert ops[-1].op == "pose_armature"
    assert armature_from_text(str(ops[-1].params["armature"]))


def test_an_empty_session_leaves_no_step_behind(window: MainWindow) -> None:
    object_id = with_a_body(window)
    before = len(window.session.project.document.ops)

    window.start_armature(object_id)
    window.finish_armature()

    assert len(window.session.project.document.ops) == before


def test_escape_ends_the_session_without_throwing_it_away(window: MainWindow) -> None:
    """Wie beim Formen: Escape beendet und verwirft nicht — die gesetzten
    Knochen stehen im Dialog, der sich daraufhin öffnet."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))

    window._escape()

    assert not window.setting_armature()
    dialog = window._op_dialog
    assert dialog is not None
    assert armature_from_text(str(dialog.values()["armature"]))


def test_a_bound_angle_bends_the_body_and_follows_the_parameter(qt_app: QApplication) -> None:
    """Der Punkt, an dem Posing hierher gehoert und nicht zu Blender.

    Vier Stellen sagten zu, dass ein Gelenkwinkel ein Projektparameter sein
    darf — Registereintrag, ``Pose``-Docstring, der ``fx``-Umschalter am
    Winkelfeld und der Kopf von ``tests/test_pose.py``. Der Kern antwortete
    darauf mit ``Diese Stellung laesst sich nicht lesen``.

    Geprueft wird Ende zu Ende, und der zweite Teil ist der wichtigere: Wird
    der Parameter geaendert, muss sich der Koerper **mitbewegen**. Der
    Cache-Schluessel deckt alles, wovon das Ergebnis abhaengt (§15) — und ein
    Ausdruck im JSON-Text der Operation ist fuer ``resolve_params``
    unsichtbar. Ohne ``NESTED_REFERENCES`` bliebe der Arm gebeugt, waehrend
    die Zahl daneben schon die neue ist.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene import OperationDraft
    from app.core.types import Parameter

    session = Session()
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    session.add_parameter(Parameter(name="neigung", value=10.0, unit="°"))
    session.apply(
        "Stellung geben",
        [
            OperationDraft(
                op="pose_armature",
                inputs=("obj_1",),
                params={
                    "armature": '[{"n":"b1","h":[0,0,0],"t":[0,0,10]}]',
                    "pose": '{"b1":["=@neigung",0,0]}',
                },
            )
        ],
    )
    session.wait_for_idle()

    result = session.last_result
    assert result is not None
    zehn_grad = as_mesh_data(result.scene.objects["obj_1"].mesh).bounds.size

    # Derselbe Stapel, ein anderer Parameterwert: Der Koerper muss folgen.
    session.change_parameter("neigung", 45.0)
    session.wait_for_idle()

    result = session.last_result
    assert result is not None
    fuenfundvierzig = as_mesh_data(result.scene.objects["obj_1"].mesh).bounds.size

    assert zehn_grad != fuenfundvierzig, (
        "der gebeugte Koerper haengt am Parameter — sonst steht ein altes Ergebnis im Cache"
    )


def test_the_context_menu_opens_the_editor_and_not_a_raw_dialog(window: MainWindow) -> None:
    """Das Kontextmenü führte drei Gesten-Operationen in einen Rohdialog.

    Genau dieser Fehler ist für Menü und Palette schon behoben worden — der
    Docstring von ``launch_operation`` beschreibt ihn: „„Formen" über
    Strg+Umschalt+P endete in einem Rohdialog: die Operation lief, veränderte
    nichts und hinterließ einen leeren Schritt im Verlauf." Das Kontextmenü blieb
    an ``run_operation`` hängen, und drei Operationen mit Gestenfeld stehen dort
    am Körper: „Formen", „Stellung geben" und „Tasche schneiden".

    Der Rechtsklick auf den Körper ist der Weg, den §2.6 „den kürzesten Weg vom
    Sehen zum Tun" nennt. Geprüft wird das Signal, nicht die Methode: die
    Verbindung ist die Aussage.
    """
    from app.core.registry import REGISTRY

    with_a_body(window)
    gesture = {"sketch", "strokes", "armature"}
    offered = [
        spec
        for spec in REGISTRY.all()
        if spec.consumes == 1 and {entry.kind for entry in spec.params.spec()} & gesture
    ]
    assert len(offered) >= 3, f"nur {len(offered)} Gesten-Operationen im Kontextmenü?"

    for spec in offered:
        window.object_tree.operationRequested.emit(spec)
        QApplication.processEvents()
        opened = window._sketch_panel is not None or window.sculpting() or window.setting_armature()
        assert opened, f"{spec.title} landete nicht in ihrem Editor"
        # Zurück auf Anfang, sonst prüft der zweite Durchgang die Sitzung des
        # ersten.
        window._escape()
        QApplication.processEvents()


# --- Was die Leiste über sich selbst sagt -------------------------------------


def test_every_button_in_the_bar_says_what_it_does(qt_app: QApplication) -> None:
    """Jeder Knopf der Skelettleiste trägt einen Tooltip.

    **Weil die Beschriftung allein zwei von dreien nicht trug.** „Letzten
    zurück" nannte nicht, *was* zurückgeht — ein Knochen, eine Kette oder die
    Sitzung; „Fertig" nannte nicht, dass danach ein Verlaufsschritt steht und
    das Skelett nicht mehr im Bild zu suchen ist. Für jemanden ohne
    CAD-Erfahrung sind das genau die Fragen, die vor dem Klick entstehen.

    Der Test zählt nicht, er fragt jeden Knopf einzeln — eine Zahl wäre beim
    vierten Knopf still wieder falsch.
    """
    from PySide6.QtWidgets import QPushButton

    from app.ui.pose_bar import PoseBar

    leiste = PoseBar()
    knoepfe = leiste.findChildren(QPushButton)
    assert len(knoepfe) >= 3, f"nur {len(knoepfe)} Knöpfe gefunden — sucht das noch richtig?"

    stumm = [knopf.text() for knopf in knoepfe if not knopf.toolTip().strip()]
    assert not stumm, "Knöpfe ohne Tooltip: " + ", ".join(stumm)


def test_the_name_field_belongs_to_the_bone_not_to_the_pose(qt_app: QApplication) -> None:
    """Was ein Screenreader vorliest, muss dasselbe sein wie das, was daneben steht.

    **Hier stand „Name der Pose", und das Feld benennt den Knochen.** Der
    Platzhalter sagte es richtig, der barrierefreie Name etwas anderes, und
    ``next_name`` tut das Dritte — wer die Leiste nicht sieht, bekam die
    falsche Auskunft (Regel 18 dem Geist nach: die zweite Kodierung muss
    dasselbe sagen wie die erste). Eine Pose hat in dieser Anwendung überhaupt
    keinen Namen.
    """
    from app.ui.pose_bar import PoseBar

    leiste = PoseBar()
    gesprochen = leiste.name.accessibleName()
    gelesen = leiste.name.placeholderText()

    assert "Pose" not in gesprochen, f"das Feld benennt den Knochen, nicht die Pose: {gesprochen!r}"
    assert "Knochen" in gesprochen, (
        f"der barrierefreie Name muss den Knochen nennen: {gesprochen!r}"
    )
    assert gesprochen == gelesen, (
        f"gesprochen {gesprochen!r} gegen gelesen {gelesen!r} — beide beschreiben "
        "dasselbe Feld und dürfen nicht auseinanderlaufen"
    )


# --- Ein zweites Mal an dasselbe Skelett --------------------------------------


def test_reopening_the_editor_brings_the_bones_back(window: MainWindow) -> None:
    """Wer den Editor erneut öffnet, sieht sein Skelett — kein leeres Blatt.

    **Weil ein Kunde, der ein Skelett gesetzt hat, es ändern will und nicht
    ersetzen.** Vorher fing der Editor jedes Mal bei null an; der einzige Weg
    zu einem verschobenen Gelenk war, alles neu zu setzen — und beim „Fertig"
    entstand eine **zweite** Operation, die den Körper ein zweites Mal beugt.

    Gelesen wird aus dem Dokument und nicht aus der Szene: Dort steht die
    Eingabe, die Szene trägt nur das Ergebnis, und aus einem gebeugten Körper
    lassen sich die Knochen nicht zurückrechnen.
    """
    from app.core.geom.pose import Bone, armature_to_text
    from app.core.scene.history import OperationDraft

    # **Mit armature_to_text gebaut und nicht von Hand getippt.** Das Format
    # ist JSON; ein erfundener Text wäre eine Zusage über die Schreibweise
    # statt über das Laden — genau die Sorte Test, die am Prüfling vorbeimisst.
    # Der erste Anlauf tat es und fiel an einer ValidationError, die mit dem
    # Gemessenen nichts zu tun hatte.
    gesetzt = [
        Bone(name="arm", head=(0.0, 0.0, 0.0), tail=(0.0, 0.0, 10.0), parent=""),
        Bone(name="hand", head=(0.0, 0.0, 10.0), tail=(0.0, 0.0, 20.0), parent="arm"),
    ]
    koerper = with_a_body(window)
    window.session.apply(
        "Skelett",
        [
            OperationDraft(
                op="pose_armature",
                inputs=(koerper,),
                params={"armature": armature_to_text(gesetzt), "pose": ""},
            )
        ],
    )
    window.session.wait_for_idle()

    window.start_armature(koerper)

    assert len(window._armature_bones) == 2, (
        f"das gesetzte Skelett muss im Editor stehen, dort stehen "
        f"{len(window._armature_bones)} Knochen"
    )
    assert window._armature_step is not None, (
        "der Editor muss wissen, welchen Schritt er ändert — sonst legt „Fertig“ "
        "einen zweiten an, und der Körper wird zweimal gebeugt"
    )
    assert "arm" in armature_to_text(window._armature_bones), (
        "die Namen der Knochen müssen mitkommen, sonst heißt die Stellung anders als vorher"
    )


def test_a_body_without_an_armature_starts_empty(window: MainWindow) -> None:
    """Ohne gesetztes Skelett bleibt der Editor ein leeres Blatt.

    Die Gegenprobe zum Laden: Wer zum ersten Mal ein Skelett setzt, darf keine
    Knochen vorfinden, und „Fertig" legt einen neuen Schritt an statt einen
    fremden zu ändern.
    """
    window.start_armature(with_a_body(window))

    assert window._armature_bones == [], "ohne Skelett fängt der Editor leer an"
    assert window._armature_step is None, (
        "ohne vorhandenen Schritt darf keiner zum Ändern vorgemerkt sein"
    )


def test_an_unreadable_armature_does_not_block_the_editor(window: MainWindow) -> None:
    """Ein unlesbares Skelett lässt den Editor leer anfangen, statt ihn zu verweigern.

    Der Schritt bleibt unberührt im Verlauf stehen — eine kaputte Eingabe ist
    kein Grund, dem Kunden das Werkzeug zu nehmen (§2.1).
    """
    from app.core.scene.history import OperationDraft

    koerper = with_a_body(window)
    window.session.apply(
        "Skelett",
        [
            OperationDraft(
                op="pose_armature",
                inputs=(koerper,),
                params={"armature": "das ist kein Skelett", "pose": ""},
            )
        ],
    )
    window.session.wait_for_idle()

    window.start_armature(koerper)

    assert window.setting_armature(), "der Editor muss trotzdem aufgehen"
    assert window._armature_bones == []
    assert window._armature_step is None, (
        "ein unlesbarer Schritt darf nicht zum Ändern vorgemerkt werden — sonst "
        "überschriebe „Fertig“ ihn mit einem halben Skelett"
    )
