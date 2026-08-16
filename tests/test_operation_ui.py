"""Eine Fläche wählen, und eine Operation nachträglich korrigieren (§18.5,
§15.4).

Offscreen, und ohne einen einzigen Dialog zu öffnen: ein Test, der ``exec()``
aufruft, wartet auf einen Menschen, der nicht da ist. Geprüft wird, was *in*
den Dialog hineingeht und was aus der Änderung wieder herauskommt — der Dialog
selbst entsteht aus dem Schema und wird in ``tests/test_ui.py`` geprüft.

Dieselbe Falle hat eine zweite Tür, und die hat hier einen Nachmittag
gekostet: ein lebendes ``MainWindow`` beantwortet ``session.failed`` mit einer
modalen Meldung. Alles, was scheitern *soll*, läuft darum auf einer nackten
``Session``, die dasselbe Signal trägt und nichts zeigt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.errors import ValidationError
from app.core.registry import REGISTRY
from app.core.scene import OperationDraft
from app.ui.main_window import MainWindow
from app.ui.op_dialog import OperationDialog
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    """Die Platte mit vier Bohrungen — jede Merkmalsart, die das hier braucht,
    ist darauf.
    """
    window = MainWindow(Session(), UiSettings())
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    return window


def select(window: MainWindow, feature_id: str | None = None) -> str:
    """Das Objekt wählen und, wenn verlangt, eines seiner Merkmale — wie ein
    Klick es täte.
    """
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    object_id = window.object_tree.selected()
    assert object_id is not None

    if feature_id is not None:
        for index in range(item.childCount()):
            child = item.child(index)
            assert child is not None
            if window.object_tree.tree.itemWidget(child, 0) is None and feature_id in (
                child.data(1, 0x0100),
                child.data(1, 32),
            ):
                child.setSelected(True)
                item.setSelected(False)
                break
    return object_id


# --- Die Auswahl erreicht den Dialog ----------------------------------------------


def test_without_a_feature_the_body_offers_its_top(window: MainWindow) -> None:
    """Kein Merkmal gewählt heißt nicht „keine Ahnung, wohin".

    Vorher stand hier, dass nichts eingetragen wird — der Dialog öffnete dann
    auf X/Y/Z = 0,00. Ob der Ursprung im Material liegt, ist Zufall: bei
    dieser Platte um den Nullpunkt ging es gut, bei einem Körper, der auf dem
    Bett angeordnet ist, lag er fünfundsechzig Millimeter daneben, und die
    Bohrung trug nichts ab.
    """
    object_id = select(window)

    values = window._from_selection(REGISTRY.get("drill_hole"), object_id)

    assert set(values) >= {"x", "y", "z"}
    assert values["z"] == pytest.approx(4.0), "die Oberseite der Platte"
    assert "at_feature" not in values, "geraten ist nicht gezeigt"


def test_a_selected_bore_fills_in_where_it_is(window: MainWindow) -> None:
    """Die Verbindung, die §25 verlangt: die Operation beginnt dort, wo das
    Merkmal ist.

    plate_holes hat seine Bohrungen bei ±25/±15, die eingetragene Position
    lässt sich also gegen die Datei prüfen statt gegen sich selbst.
    """
    object_id = select(window)
    window._on_feature_picked("hole_1")

    values = window._from_selection(REGISTRY.get("drill_hole"), object_id)

    assert set(values) >= {"x", "y", "z", "axis"}
    assert (abs(values["x"]), abs(values["y"])) == (pytest.approx(25.0), pytest.approx(15.0))
    assert values["axis"] == "z"


def test_a_part_is_told_the_name_of_the_feature(window: MainWindow) -> None:
    object_id = select(window)
    window._on_feature_picked("hole_1")

    values = window._from_selection(REGISTRY.get("insert_heatset_m4"), object_id)

    assert values == {"at_feature": "hole_1"}


def test_a_feature_that_is_gone_falls_back_to_the_body(window: MainWindow) -> None:
    """Kein Fehler: Baum und Szene dürfen einen Moment auseinander sein.

    Was danach zählt, ist der Körper — dieselbe Antwort wie für eine Auswahl,
    in der nie ein Merkmal stand. Eine verschwundene Kennung darf nicht
    schlechter dastehen als gar keine.
    """
    object_id = select(window)
    spec = REGISTRY.get("drill_hole")
    without_any = window._from_selection(spec, object_id)

    window._on_feature_picked("hole_99")
    after_a_ghost = window._from_selection(spec, object_id)

    assert after_a_ghost == without_any
    assert after_a_ghost["z"] == pytest.approx(4.0), "die Oberseite, nicht der Ursprung"


# --- Der Dialog öffnet auf Werten statt auf Vorgaben ------------------------------


def test_the_dialog_starts_on_what_it_was_given(qt_app: QApplication) -> None:
    spec = REGISTRY.get("drill_hole")

    dialog = OperationDialog(spec, [], None, values={"diameter": 8.5, "x": -12.0, "axis": "y"})

    assert dialog.values()["diameter"] == pytest.approx(8.5)
    assert dialog.values()["x"] == pytest.approx(-12.0)
    assert dialog.values()["axis"] == "y"


def test_what_it_was_not_given_keeps_the_default(qt_app: QApplication) -> None:
    spec = REGISTRY.get("drill_hole")

    dialog = OperationDialog(spec, [], None, values={"x": 3.0})

    assert dialog.values()["diameter"] == pytest.approx(5.0), "the schema's default"


def test_the_confirm_button_names_the_operation(qt_app: QApplication) -> None:
    """Der Knopf sagt, was gleich passiert: „Bohrung setzen" statt „OK".

    Der Fenstertitel trägt den Namen zwar auch, steht aber beim Klicken nicht
    im Blick — und ein Dialog, dessen Knöpfe „OK/Abbrechen" heißen, liest sich
    bei jeder Operation gleich.
    """
    from PySide6.QtWidgets import QDialogButtonBox

    spec = REGISTRY.get("drill_hole")

    dialog = OperationDialog(spec, [], None)

    ok = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
    assert ok is not None
    assert ok.text().replace("&", "") == str(spec.title)


def test_a_filled_in_value_is_not_hidden_behind_the_advanced_box(qt_app: QApplication) -> None:
    """Ein gerade entschiedener Wert gehört dorthin, wo er zu sehen ist."""
    spec = REGISTRY.get("drill_hole")
    depth = next(entry for entry in spec.params.spec() if entry.name == "depth")
    assert depth.placement == "advanced", "otherwise this test proves nothing"

    dialog = OperationDialog(spec, [], None, values={"depth": 4.0})

    assert dialog.values()["depth"] == pytest.approx(4.0)


# --- Ein Maß, das an einem Projektparameter hängt (§13) ---------------------------


def test_a_bound_operation_opens_at_all(qt_app: QApplication) -> None:
    """Ein Ausdruck im Schema-Feld darf den Dialog nicht mitreißen.

    Er tat es: ``float("=@breite")`` warf eine ``ValueError`` mitten im Aufbau,
    und weil der Aufbau in einem Slot lief, sah der Nutzer davon nichts — kein
    Dialog, keine Meldung, ein Doppelklick, der nichts tut. Betroffen war jede
    Operation des Weg-2-Beispiels, also genau die, auf die dessen Tour zeigt.
    """
    spec = REGISTRY.get("create_box")

    dialog = OperationDialog(spec, [], None, values={"width": "=@breite"})

    assert dialog.values()["width"] == "=@breite"


def test_the_binding_survives_the_dialog(qt_app: QApplication) -> None:
    """Wer eine gebundene Operation öffnet und bestätigt, behält die Bindung.

    Den Ausdruck beim Öffnen aufzulösen wäre die stillste Art, ihn zu
    verlieren: im Feld stünde eine plausible Zahl, und beim nächsten Drehen am
    Parameter bliebe das Modell stehen.
    """
    spec = REGISTRY.get("create_box")

    dialog = OperationDialog(
        spec,
        [],
        None,
        values={"width": "=@breite", "depth": 30.0},
        parameter_values={"breite": 60.0},
    )

    assert dialog.values()["width"] == "=@breite", "der Ausdruck, nicht die 60"
    assert dialog.values()["depth"] == pytest.approx(30.0)


def test_a_number_can_be_bound_in_the_dialog(qt_app: QApplication) -> None:
    """Weg 2 endete im Fenster auf halber Strecke: Parameter ließen sich
    anlegen, aber an kein Maß hängen.
    """
    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, [], None, parameter_values={"breite": 60.0})
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)

    field.toggle.setChecked(True)
    field.text.setText("=@breite / 2")

    assert dialog.values()["width"] == "=@breite / 2"
    assert "30" in field.hint.text(), f"der Hinweis rechnet mit: {field.hint.text()!r}"


def test_an_emptied_expression_falls_back_to_the_number(qt_app: QApplication) -> None:
    """Ein leeres Ausdrucksfeld darf keinen unlesbaren Parameter erzeugen."""
    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, [], None, values={"width": 42.0})
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)

    field.toggle.setChecked(True)
    field.text.clear()

    assert dialog.values()["width"] == pytest.approx(42.0)


def test_a_wrong_expression_says_so_before_it_is_confirmed(qt_app: QApplication) -> None:
    """§2.7: der billigste Vorschlag ist der, der kommt, bevor etwas
    schiefgeht."""
    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, [], None, parameter_values={"breite": 60.0})
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)

    field.toggle.setChecked(True)
    field.text.setText("=@gibtsnicht * 2")

    assert field.hint.text(), "der Hinweis bleibt stumm"
    assert not field.hint.text().startswith("="), (
        f"ein Ergebnis, wo eine Erklärung stehen müsste: {field.hint.text()!r}"
    )


def test_every_operation_of_the_weg2_example_can_be_opened(qt_app: QApplication) -> None:
    """Der Fund aus der Durchsicht, am Original: im Weg-2-Beispiel ließ sich
    keine der vier Operationen im Verlauf öffnen.

    Ein eigenes Fenster, nicht das Fixture: dessen Projekt ist geändert, und
    ``open_path`` fragt dann modal nach dem Speichern — in einem Testlauf ist
    das ein Fenster, auf das niemand klickt.
    """
    from app.core import examples

    window = MainWindow(Session(), UiSettings())
    window.open_path(examples.directory() / "weg2-halter-konstruieren.p3d")
    window.session.wait_for_idle()
    QApplication.processEvents()

    bound = [
        operation
        for operation in window.session.project.document.ops
        if any(str(value).startswith("=") for value in operation.params.values())
    ]
    assert bound, "das Beispiel bindet nichts mehr — dann prüft dieser Test nichts"

    for operation in bound:
        window.edit_operation(operation.id)
        QApplication.processEvents()
        assert window._op_dialog is not None, f"Op {operation.id} ({operation.op}) öffnet nicht"
        window._op_dialog.reject()
        QApplication.processEvents()


# --- correcting an operation ----------------------------------------------------


def test_an_operation_can_be_given_other_numbers(window: MainWindow) -> None:
    select(window)
    window.session.apply(
        "Bohren",
        [
            OperationDraft(
                op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "x": 0.0, "y": 0.0}
            )
        ],
    )
    window.session.wait_for_idle()
    op_id = window.session.project.document.ops[-1].id

    window.session.change_params(op_id, {"x": 10.0})
    window.session.wait_for_idle()

    assert window.session.history.operation(op_id).params["x"] == pytest.approx(10.0)
    assert window.session.history.operation(op_id).params["diameter"] == pytest.approx(5.0)
    assert window.session.last_result is not None
    assert window.session.last_result.complete


def test_a_refused_change_reaches_the_surface_as_a_suggestion(qt_app: QApplication) -> None:
    """§2.7: was nicht geht, wird gesagt, nicht verschluckt.

    Auf der Sitzung allein, ohne Fenster: ein lebendes ``MainWindow``
    beantwortet ``failed`` mit einer modalen Meldung, und ein Test, der eine
    aufgehen lässt, wartet darauf, dass jemand sie wegklickt. Geprüft wird
    hier, dass das Signal den Fehler trägt — wer ihn zeigt, ist Sache des
    Fensters.
    """
    session = Session()
    problems: list[object] = []
    session.failed.connect(problems.append)

    session.change_params(999, {"x": 1.0})

    assert problems and isinstance(problems[0], ValidationError)


def test_every_operation_of_the_history_can_be_opened(window: MainWindow) -> None:
    """Eine Transaktion aus mehreren Operationen bekommt eine Zeile je
    Operation (§15.4).
    """
    select(window)
    window.session.apply(
        "Zwei Schritte",
        [
            OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Platte"}),
            OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 4.0}),
        ],
    )
    window.session.wait_for_idle()
    QApplication.processEvents()

    rows = window.history_panel.list
    reachable = {
        rows.item(index).data(0x0100)
        for index in range(rows.count())
        if rows.item(index) is not None and rows.item(index).data(0x0100) is not None
    }

    assert {entry.id for entry in window.session.project.document.ops} <= reachable


# --- Was zur Bauart der Auswahl passt ---------------------------------------------


BREP_ONLY = ("fillet_edges", "chamfer_edges", "draft_faces", "shell_exact", "brep_to_mesh")


def test_the_exact_operations_are_greyed_out_on_a_mesh(window: MainWindow) -> None:
    """Sie waren anklickbar, und der Satz „Der gewählte Körper ist ein Netz"
    kam erst nach dem ausgefüllten Dialog.

    Das Menü fragte allein, wie viele Objekte gewählt sind — die Bauart stand
    die ganze Zeit daneben in ``SceneObject.kind``. Regel 19 verlangt keine
    Sackgassen, und eine Operation, die hier nie gehen kann, ist eine.
    """
    select(window)
    window._update_actions()

    for name in BREP_ONLY:
        action = window._op_actions[name]
        assert not action.isEnabled(), name


def test_the_greyed_out_entry_says_why(window: MainWindow) -> None:
    """Ausgrauen allein ist die halbe Antwort — der Nutzer sucht den Grund
    sonst bei sich."""
    select(window)
    window._update_actions()

    hint = window._op_actions["fillet_edges"].toolTip()
    assert "B-Rep" in hint or "exakt" in hint.casefold()


def test_the_same_operations_are_available_on_an_exact_body(window: MainWindow) -> None:
    """Die Gegenprobe: ausgegraut wird nach der Bauart, nicht immer."""
    window.session.start_new("centauri-carbon-2", "petg")
    window.session.history.apply(
        "Exakter Quader", [OperationDraft(op="create_brep_box", params={})]
    )
    window.session.evaluate_now()
    select(window)
    window._update_actions()

    for name in BREP_ONLY:
        assert window._op_actions[name].isEnabled(), name


def test_the_register_says_which_operations_need_an_exact_body() -> None:
    """Die Auskunft steht im Register, nicht in einer Liste in der Oberfläche
    — sonst fehlt die nächste Operation des exakten Kerns darin."""
    for name in (*BREP_ONLY, "push_face", "sketch_pocket"):
        assert REGISTRY.get(name).requires_kind == "brep", name
    for name in ("drill_hole", "hollow_object", "repair"):
        assert not REGISTRY.get(name).requires_kind, name


# --- Texturmuster (§2.6, B2) ----------------------------------------------------


def test_the_patterns_are_shown_and_named(qt_app: object) -> None:
    """Acht Muster standen als „knurl_diamond" in einer Liste ohne Bild.

    Beides zusammen war der Befund: unlesbar **und** unsichtbar. Geprüft wird
    an der fertigen Auswahl, nicht an der Namensliste — die Verdrahtung ist
    hier der Punkt.
    """
    from PySide6.QtWidgets import QComboBox

    from app.core.geom.texture_ops import PATTERNS
    from app.core.registry import REGISTRY
    from app.ui.op_dialog import OperationDialog

    dialog = OperationDialog(REGISTRY.get("apply_texture"), [])
    combo = dialog._editors["pattern"]
    assert isinstance(combo, QComboBox)
    assert combo.count() == len(PATTERNS)

    for index in range(combo.count()):
        label = combo.itemText(index)
        assert label not in PATTERNS, f"{label} ist ein Schlüssel, kein Name"
        assert not combo.itemIcon(index).isNull(), f"{label} hat kein Bild"
    dialog.deleteLater()


def test_a_pattern_tile_comes_from_the_geometry() -> None:
    """§25: Was im Bild steht, ist das, was gerechnet wird — kein gemaltes
    Vorschaubild, das irgendwann von der Geometrie abweicht."""
    from app.core import figures
    from app.core.geom.texture_ops import PATTERNS

    for pattern in PATTERNS:
        tile = figures.texture_tile(pattern, "light")
        assert tile.startswith("<svg")
        assert "<polygon" in tile, f"{pattern} zeichnet keine Umrisse"


def test_the_description_is_as_tall_as_its_text(qt_app: QApplication) -> None:
    """Der Satz über den Feldern stand vertikal zentriert in 189 Pixeln.

    Im Bild sah das aus wie ein Gestaltungsfehler — ein Beschreibungstext, der
    ohne Grund in der Mitte schwebt. Es war eine fehlende Größenrichtlinie: Das
    senkrechte Layout verteilte die freie Höhe auf alle Einträge, und der erste
    war dieser Satz. Der Platz gehört zwischen Felder und Knöpfe, nicht darüber.
    """
    from app.ui.op_dialog import OperationDialog

    dialog = OperationDialog(REGISTRY.get("drill_hole"), [])
    try:
        dialog.resize(520, 460)
        dialog.show()
        description = dialog.layout().itemAt(0)

        assert description.widget() is dialog._description
        # Zwei Zeilen Text in einem Dialog dieser Höhe — großzügig gedeckelt,
        # damit der Test eine andere Schrift überlebt und trotzdem anschlägt,
        # wenn das Label wieder wächst.
        assert description.geometry().height() < 120
    finally:
        dialog.deleteLater()


# --- Bilder als Quelle (§25, P16.7) ----------------------------------------------


def test_the_image_field_lists_only_images(window: MainWindow) -> None:
    """Das Feld „Bild" bot jede Quelle des Projekts an — also STLs in einem
    Feld dieses Namens, und einen Weg zu einem Bild gab es nicht. Der Befund
    schlug „Ein Bild wählen." vor, eine Handlung, die es nicht gab."""
    from app.ui.op_dialog import ImageSourceField

    spec = REGISTRY.get("displace_image")
    dialog = OperationDialog(
        spec,
        {},
        window,
        sources={"src_1": "halterung.stl"},
        images={},
        pick_image=None,
    )

    editor = dialog._editors["source"]
    assert isinstance(editor, ImageSourceField)
    assert editor.combo.count() == 0, "eine STL ist kein Bild"


def test_the_pick_button_imports_and_selects(window: MainWindow, tmp_path: Path) -> None:
    """Der Knopf ist der fehlende Weg: Bild von der Platte holen, als Quelle
    einbetten, im Feld auswählen — ohne load-Operation, denn ein Bild wird
    kein Körper."""
    from app.ui.op_dialog import ImageSourceField

    picture = tmp_path / "relief.png"
    # Ein minimales, echtes PNG — imageio braucht es hier nicht, nur der Weg.
    picture.write_bytes(b"\x89PNG\r\n\x1a\nbild")
    before = len(window.session.project.document.ops)

    def pick() -> tuple[str, str]:
        source_id = window.session.import_image(picture)
        return source_id, picture.name

    spec = REGISTRY.get("displace_image")
    dialog = OperationDialog(spec, {}, window, images={}, pick_image=pick)
    editor = dialog._editors["source"]
    assert isinstance(editor, ImageSourceField)

    editor.button.click()

    chosen = dialog.values()["source"]
    assert chosen, "das geholte Bild ist ausgewählt"
    source = window.session.project.document.sources[chosen]
    assert source.kind == "image"
    assert len(window.session.project.document.ops) == before, (
        "ein Bild bekommt keine load-Operation"
    )
