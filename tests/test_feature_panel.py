"""Das Merkmal-Panel: was man mit dem gewählten Merkmal tun kann, als Felder.

Robert am 03.09.2026: „evtl noch ein eigenes Panel, damit man nicht für alles
Rechtsklick machen muss — übersichtlich, verständlich, innovativ und intuitiv."

Geprüft wird, dass das Panel die Auskunft des Kerns rendert und **keine
zweite Tabelle führt**: Was gilt, welche Felder es hat und was ihr heutiger
Wert ist, sagt ``app.core.perceive.actions.actions_for``.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
)

from app.core.geom.mesh import MeshData, read_mesh
from app.core.perceive import features
from app.core.perceive.actions import actions_for
from app.core.types import Feature
from app.ui.labels import LengthSpin
from app.ui.panels import FeaturePanel

MESHES = Path(__file__).parent / "data" / "meshes"


def plate() -> MeshData:
    return read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")


def a_hole() -> tuple[str, Feature]:
    found = features.detect(plate())
    return next((key, value) for key, value in found.items() if value.kind == "hole")


def buttons(panel: FeaturePanel) -> list[str]:
    return [knopf.text() for row in panel._built for knopf in row.findChildren(QPushButton)]


def fields(row: QWidget) -> list[QWidget]:
    return [
        widget
        for widget in row.findChildren(QWidget)
        if isinstance(widget, (LengthSpin, QComboBox, QCheckBox))
    ]


def test_without_a_selection_the_panel_says_what_brings_you_here(qt_app: QApplication) -> None:
    """Ein leeres Feld erklärt nichts; ein Satz schon (§2.7)."""
    panel = FeaturePanel()
    assert panel._empty.isVisibleTo(panel)
    assert panel._empty.text().strip(), "der leere Zustand trägt einen Satz"
    assert not panel._built, "und keine Zeilen"


def test_the_panel_offers_what_the_core_says_and_nothing_else(qt_app: QApplication) -> None:
    """Die Zeilen kommen aus ``actions_for`` — eine Stelle, nicht zwei.

    Verglichen wird gegen die Auskunft selbst und nicht gegen eine Liste im
    Test: Sobald der Kern eine Handlung dazubekommt, wächst das Panel mit, und
    dieser Test bleibt richtig.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    expected = [str(action.title) for action in actions_for(feature) if action.op is not None]
    assert expected, "ohne Handlungen prüft dieser Test nichts"
    assert buttons(panel) == expected


def test_every_number_starts_on_what_was_measured(qt_app: QApplication) -> None:
    """Roberts „sinnvolle Einstellungen": Die Vorgabe jedes Feldes ist der
    heutige Wert, damit der Kunde die eine Zahl ändert, die er meint."""
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    centre = feature.params["centre"]
    move = next(
        row
        for row in panel._built
        if any(k.text() == "Merkmal verschieben" for k in row.findChildren(QPushButton))
    )
    spins = [widget for widget in fields(move) if isinstance(widget, LengthSpin)]
    assert len(spins) == 3, "Ort heißt drei Achsen"
    for spin, measured in zip(spins, centre, strict=True):
        assert spin.value_mm() == pytest.approx(float(measured))


def test_pressing_an_action_names_the_operation_and_its_feature(qt_app: QApplication) -> None:
    """Das Panel rechnet nichts — es nennt Operation und Werte, wie der
    Operationsdialog auch. ``at_feature`` steht dabei nicht als Feld: Welches
    Merkmal gemeint ist, sagt die Auswahl."""
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    seen: list[tuple[str, dict[str, object]]] = []
    panel.operationRequested.connect(lambda op, params: seen.append((op, params)))

    move = next(
        knopf
        for row in panel._built
        for knopf in row.findChildren(QPushButton)
        if knopf.text() == "Merkmal verschieben"
    )
    move.click()

    assert len(seen) == 1
    op, params = seen[0]
    assert op == "move_feature"
    assert params["at_feature"] == identifier
    assert set(params) >= {"at_feature", "x", "y", "z"}


def test_a_linked_countersink_is_named_before_the_bore_moves(qt_app: QApplication) -> None:
    """Das Panel sagt vor dem Klick, dass beide Teile des Hohlraums mitgehen."""
    bore = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 6.0,
            "depth": 10.0,
        },
    )
    sink = Feature(
        id="cone_1",
        kind="cone",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 5.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 12.0,
            "recess": True,
        },
    )
    linked = {bore.id: bore, sink.id: sink}
    panel = FeaturePanel()

    panel.show_feature(bore.id, bore, features=linked)

    move = next(
        row
        for row in panel._built
        if any(button.text() == "Merkmal verschieben" for button in row.findChildren(QPushButton))
    )
    text = " ".join(label.text() for label in move.findChildren(QLabel))
    assert "Bohrung und Senkung" in text
    assert "gemeinsam verschoben" in text


def test_a_handling_that_does_not_apply_brings_its_reason(qt_app: QApplication) -> None:
    """Was nicht geht, steht als Satz und nicht als graues Feld.

    Eine Kantenschleife ist ein Netzfehler und kein Körper; für sie gilt keine
    der Handlungen. Das Panel zeigt sie trotzdem — mit dem Grund, sonst rät
    der Kunde, ob sie fehlt oder vergessen wurde.
    """
    loop = Feature(
        id="edge_loop_1",
        kind="edge_loop",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "open_edges": 4},
    )
    ungültig = [action for action in actions_for(loop) if action.op is None]
    assert ungültig, "ohne abgelehnte Handlungen prüft dieser Test nichts"
    assert all(str(action.reason).strip() for action in ungültig), "jede nennt ihren Grund"

    panel = FeaturePanel()
    panel.show_feature("edge_loop_1", loop)

    assert not buttons(panel), "keine Handlung ist anklickbar"
    texte = " ".join(
        label.text()
        for row in panel._built
        for label in row.findChildren(QWidget)
        if hasattr(label, "text")
    )
    for action in ungültig:
        assert str(action.reason) in texte, f"der Grund von {action.title} fehlt"


def test_a_changed_number_is_reported_before_it_is_done(qt_app: QApplication) -> None:
    """Robert am 03.09.2026: „eine live vorschau wäre noch gut."

    Das Panel meldet jede Änderung über ein **eigenes** Signal — getrennt vom
    Ausführen, damit ein Empfänger ohne Nachdenken weiß, ob er rechnen oder
    ändern soll. Ein Empfänger, der beim falschen Signal ausführt, schriebe
    einen Schritt, den niemand ausgelöst hat.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    gemeldet: list[tuple[str, dict[str, object]]] = []
    getan: list[tuple[str, dict[str, object]]] = []
    panel.valuesChanged.connect(lambda op, params: gemeldet.append((op, params)))
    panel.operationRequested.connect(lambda op, params: getan.append((op, params)))

    spin = next(
        widget for row in panel._built for widget in fields(row) if isinstance(widget, LengthSpin)
    )
    spin.set_value_mm(spin.value_mm() + 2.0)

    assert gemeldet, "die Änderung wurde nicht gemeldet"
    assert gemeldet[-1][1]["at_feature"] == identifier, "das Merkmal steht dabei"
    assert not getan, "gemeldet heißt nicht getan"


def test_a_length_is_reported_in_millimetres(qt_app: QApplication) -> None:
    """Qts ``valueChanged`` trägt den Anzeigewert; gemeldet wird der des Kerns.

    Wer das verwechselt, schickt bei Zoll 0,1969 statt 5 — derselbe Fehler,
    für den ``LengthSpin`` sein eigenes Signal hat.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    gemeldet: list[dict[str, object]] = []
    panel.valuesChanged.connect(lambda _op, params: gemeldet.append(params))

    spin = next(
        widget for row in panel._built for widget in fields(row) if isinstance(widget, LengthSpin)
    )
    spin.set_value_mm(12.5)

    assert gemeldet, "nichts gemeldet"
    werte = [wert for name, wert in gemeldet[-1].items() if name != "at_feature"]
    assert any(abs(float(wert) - 12.5) < 1e-6 for wert in werte if isinstance(wert, (int, float)))


def a_face() -> tuple[str, Feature]:
    found = features.detect(plate())
    return next((key, value) for key, value in found.items() if value.kind == "face")


def test_a_face_gets_the_catalogue_instead_of_a_dead_end(qt_app: QApplication) -> None:
    """An einer Fläche gilt keine der vier Handlungen — dort setzen dafür
    fünfundzwanzig Bausteine an.

    Vier graue Zeilen mit Begründung sind eine Sackgasse mit Erklärung; eine
    Sackgasse bleibt es trotzdem. Der Katalog lag hinter Rechtsklick und
    Untermenü.
    """
    identifier, feature = a_face()
    assert all(action.op is None for action in actions_for(feature)), "sonst prüft das nichts"

    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    gerufen: list[bool] = []
    panel.catalogRequested.connect(lambda: gerufen.append(True))

    knopf = next(widget for widget in panel._built if isinstance(widget, QPushButton))
    knopf.click()

    assert gerufen == [True], "der Knopf öffnet den Katalog"


def test_the_all_alike_box_appears_only_with_siblings(qt_app: QApplication) -> None:
    """„Auf alle 1 anwenden" wäre eine Frage ohne Unterschied."""
    identifier, feature = a_hole()
    allein = FeaturePanel()
    allein.show_feature(identifier, feature)
    assert not [
        widget
        for row in allein._built
        for widget in row.findChildren(QCheckBox)
        if "alle" in widget.text()
    ], "ohne Geschwister kein Haken"

    mit = FeaturePanel()
    mit.show_feature(identifier, feature, ["hole_2", "hole_3"])
    haken = [
        widget
        for row in mit._built
        for widget in row.findChildren(QCheckBox)
        if "alle" in widget.text()
    ]
    assert haken, "mit Geschwistern schon"
    assert "3" in haken[0].text(), "und er nennt die Zahl: das eigene plus zwei"


def test_the_all_alike_box_names_every_sibling(qt_app: QApplication) -> None:
    """Gesetzt gilt die Handlung allen — und das Panel nennt sie einzeln,
    damit das Fenster eine Transaktion daraus machen kann (Regel 16)."""
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature, ["hole_2", "hole_3"])
    fuer_alle: list[tuple[str, dict[str, object], list[str]]] = []
    einzeln: list[tuple[str, dict[str, object]]] = []
    panel.operationRequestedForEach.connect(
        lambda op, params, ids: fuer_alle.append((op, params, ids))
    )
    panel.operationRequested.connect(lambda op, params: einzeln.append((op, params)))

    row = next(
        row for row in panel._built if row.findChildren(QCheckBox) and row.findChildren(QPushButton)
    )
    next(box for box in row.findChildren(QCheckBox) if "alle" in box.text()).setChecked(True)
    row.findChildren(QPushButton)[0].click()

    assert not einzeln, "gesetzt heißt: nicht nur dieses eine"
    assert fuer_alle, "die Sammelhandlung wurde nicht gemeldet"
    _op, _params, ids = fuer_alle[-1]
    assert ids == [identifier, "hole_2", "hole_3"], "alle drei, das eigene zuerst"


def spread(panel: FeaturePanel, scroller: QScrollArea, height: int) -> int:
    """Der Abstand zwischen dem obersten und dem untersten Knopf, in Punkten.

    Gemessen wird über den **Rollbereich**, weil die Anwendung es so baut: Er
    trägt ``setWidgetResizable(True)`` und zieht das Panel auf seine Höhe. Wer
    das Panel stattdessen selbst vergrößert, misst eine Lage, die kein Fenster
    herstellt — nachgemessen am 03.09.2026: Dort antwortet die Messung auf jede
    Höhe gleich, und der Fehler bliebe unsichtbar.
    """
    scroller.resize(320, height)
    QApplication.processEvents()
    layout = panel.layout()
    assert layout is not None
    layout.activate()
    lagen = [
        knopf.mapTo(panel, knopf.rect().topLeft()).y()
        for row in panel._built
        for knopf in row.findChildren(QPushButton)
    ]
    assert len(lagen) >= 2, "mehrere Handlungen, sonst misst der Test nichts"
    return max(lagen) - min(lagen)


def test_a_tall_window_does_not_pull_the_handlings_apart(qt_app: QApplication) -> None:
    """Der Restplatz gehört nach unten, nicht zwischen die Handlungen.

    Das Panel steckt in einem Rollbereich mit ``setWidgetResizable`` und wird
    damit auf dessen Höhe gezogen. Ohne eine Dehnung am Ende verteilt Qt den
    Überschuss auf die Zeilen: In einem 1255 Punkte hohen Fenster wollte der
    Inhalt 581 und stand am Ende 179 Punkte je Handlung auseinander. Vier
    Knöpfe mit so viel Luft dazwischen gehören sichtbar nicht mehr zu den
    Feldern über ihnen.

    Die Höhe ist der **Eingang** der Messung: Eine Antwort, die sich mit ihr
    ändert, ist der Fehler. Gegengeprüft, dass der Test ihn auch fängt — ohne
    die Dehnung wuchs die Spanne von 319 auf 725 Punkte.
    """
    key, feature = a_hole()
    panel = FeaturePanel()
    scroller = QScrollArea()
    scroller.setWidget(panel)
    scroller.setWidgetResizable(True)
    scroller.show()
    panel.show_feature(key, feature)
    QApplication.processEvents()
    wanted = panel.sizeHint().height()

    tight = spread(panel, scroller, wanted)
    roomy = spread(panel, scroller, wanted * 3)

    assert tight > 0, "die Knöpfe stehen überhaupt untereinander"
    assert roomy == tight, (
        f"die Handlungen wandern mit der Fensterhöhe auseinander: {tight} -> {roomy} Punkte"
    )


def two_holes() -> tuple[tuple[str, Feature], tuple[str, Feature]]:
    found = features.detect(plate())
    holes = [(key, value) for key, value in found.items() if value.kind == "hole"]
    assert len(holes) >= 2, "die Platte hat mehrere Bohrungen"
    return holes[0], holes[1]


def test_two_features_show_how_far_apart_they_stand(qt_app: QApplication) -> None:
    """Robert am 03.09.2026 zum Ausbau: der Abstand zweier Bohrungen ist das,
    was man vor jedem Druck wissen will.

    Bis dahin ging das nur über das Messwerkzeug und zwei Klicks ins Bild. Zwei
    Zeilen im Baum anzuklicken ist der kürzere Weg — markiert hat man sie
    ohnehin schon.
    """
    (first_id, first), (second_id, second) = two_holes()
    panel = FeaturePanel()
    panel.show_pair(first_id, first, second_id, second)

    texte = " ".join(
        label.text()
        for row in panel._built
        for label in row.findChildren(QLabel)
        if hasattr(label, "text")
    ) + " ".join(row.text() for row in panel._built if isinstance(row, QLabel))
    # Der Kundenname und nicht die rohe Kennung: „Bohrung 1", nicht „hole_1".
    from app.ui.labels import feature_name

    assert feature_name(first_id, first) in texte, "das erste steht dabei"
    assert feature_name(second_id, second) in texte, "und das zweite"

    here = first.params["centre"]
    there = second.params["centre"]
    erwartet = math.sqrt(sum((float(b) - float(a)) ** 2 for a, b in zip(here, there, strict=True)))
    # Die Zahl steht als Text mit Einheit; geprüft wird, dass sie vorkommt.
    assert (
        f"{erwartet:.2f}".replace(".", ",") in texte or f"{erwartet:.1f}".replace(".", ",") in texte
    ), texte


def test_a_pair_writes_no_step(qt_app: QApplication) -> None:
    """Eine Auskunft und keine Handlung (Regel 2): kein Knopf, kein Signal."""
    (first_id, first), (second_id, second) = two_holes()
    panel = FeaturePanel()
    getan: list[object] = []
    panel.operationRequested.connect(lambda *_a: getan.append(True))
    panel.operationRequestedForEach.connect(lambda *_a: getan.append(True))
    panel.show_pair(first_id, first, second_id, second)

    assert not [knopf for row in panel._built for knopf in row.findChildren(QPushButton)], (
        "kein Knopf unter einer Auskunft"
    )
    assert not getan


def test_a_pair_without_a_measured_centre_says_so(qt_app: QApplication) -> None:
    """Ein erfundener Abstand wäre schlimmer als keiner."""
    (first_id, first), _zweites = two_holes()
    ohne = Feature(
        id="edge_loop_1",
        kind="edge_loop",
        provenance="detected",
        params={"open_edges": 4},
    )
    panel = FeaturePanel()
    panel.show_pair(first_id, first, "edge_loop_1", ohne)

    texte = " ".join(row.text() for row in panel._built if isinstance(row, QLabel))
    assert "kein Abstand" in texte, texte


def test_a_hole_says_which_screw_fits(qt_app: QApplication) -> None:
    """Die Anwendung kennt die Antwort und sagte sie nur im Bohrdialog.

    „Ist das eine M5?" ist die Frage vor jedem Druck. Der Durchmesser steht im
    Panel ohnehin; ihn zu zeigen und die Normgröße zu verschweigen wäre die
    halbe Auskunft.
    """
    from app.core.scene.placement import bore_advice

    identifier, feature = a_hole()
    erwartet, _choices = bore_advice(float(feature.params["diameter"]))

    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    texte = " ".join(row.text() for row in panel._built if isinstance(row, QLabel))
    assert erwartet in texte, texte


def test_only_a_hole_gets_the_screw_line(qt_app: QApplication) -> None:
    """Die Gegenprobe: Eine Fläche hat keinen Durchmesser und keine Schraube.

    Ein Satz über Normgrößen an einer Fläche wäre eine Auskunft über etwas,
    das dort nicht gemessen wurde.
    """
    identifier, feature = a_face()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    texte = " ".join(row.text() for row in panel._built if isinstance(row, QLabel))
    assert "Bohrung misst" not in texte, texte


def test_the_same_refusal_is_said_once(qt_app: QApplication) -> None:
    """Fünf graue Zeilen mit demselben Satz sind eine Sackgasse mit Echo.

    **Gemessen am 04.09.2026 an Roberts Besenhalter.** Er trägt zehn Flächen
    und neun Verrundungen; wer eine Fläche anklickt, bekommt fünf Zeilen, und
    alle fünf sagen wörtlich „Eine Fläche gehört zur Oberfläche des Körpers …".
    Bei der Verrundung sind es vier von fünf. Jede Zeile für sich ist richtig —
    `actions_for` begründet zu Recht, warum eine Handlung fehlt, statt sie
    still wegzulassen —, und zusammen liest es sich als fünf Absagen auf
    dieselbe Frage.

    Gefaltet wird nur, was **denselben** Grund trägt, und weggelassen wird
    nichts: Die Zeile nennt weiter jede Handlung beim Namen. An der Verrundung
    bleiben deshalb drei Zeilen und nicht eine — ihre drei Gründe sind
    verschieden, und einer davon ist die Ankündigung, dass der Radius kommt.

    Was gilt, wird nie gefaltet: An einer Bohrung stehen alle fünf Handlungen
    einzeln, mit ihren Feldern und ihrem Knopf.
    """
    from app.core.perceive.actions import FeatureAction
    from app.ui.panels import _folded

    gleich = "Eine Fläche gehört zur Oberfläche des Körpers."
    anders = "Den Radius zu ändern ist noch nicht gebaut."
    actions = [
        FeatureAction(title="Merkmal verschieben", op=None, reason=gleich),
        FeatureAction(title="Merkmal ändern", op=None, reason=anders),
        FeatureAction(title="Merkmal drehen", op=None, reason=gleich),
        FeatureAction(title="Merkmal verdoppeln", op=None, reason=gleich),
    ]

    gefaltet = _folded(actions)

    assert len(gefaltet) == 2, [str(entry.title) for entry in gefaltet]
    assert str(gefaltet[0].title) == "Merkmal verschieben, drehen und verdoppeln", (
        "die drei mit demselben Grund stehen zusammen, ohne das Wort dreimal"
    )
    assert str(gefaltet[0].reason) == gleich
    # Die Reihenfolge des Kerns bleibt: Die zusammengelegte Zeile steht dort,
    # wo die erste ihrer Handlungen stand.
    assert str(gefaltet[1].title) == "Merkmal ändern"
    assert str(gefaltet[1].reason) == anders


def test_what_works_is_never_folded_away(qt_app: QApplication) -> None:
    """Eine Handlung mit Feldern und Knopf teilt keine Zeile mit einer anderen."""
    from app.core.perceive.actions import FeatureAction
    from app.ui.panels import _folded

    actions = [
        FeatureAction(title="Bohrung ändern", op="resize_hole"),
        FeatureAction(title="Merkmal verschieben", op="move_feature"),
        FeatureAction(title="Merkmal drehen", op=None, reason="geht hier nicht"),
        FeatureAction(title="Merkmal verdoppeln", op=None, reason="geht hier nicht"),
    ]

    gefaltet = _folded(actions)

    assert [entry.op for entry in gefaltet] == ["resize_hole", "move_feature", None]


def test_every_field_group_says_what_it_belongs_to(qt_app: QApplication) -> None:
    """Zweimal X/Y/Z untereinander, und nur der Knopf darunter sagt, welche.

    **Der Fall.** An einer Bohrung stehen vier Gruppen untereinander: X/Y/Z für
    *Verschieben*, ein Durchmesser für *Ändern*, Achse und Winkel für *Drehen*,
    wieder X/Y/Z für *Verdoppeln*. Benannt wurden sie nur vom Knopf **unter**
    ihnen, und das trägt genau einmal — beim ersten Feldpaar liest man die
    Bedeutung noch von unten nach, beim zweiten nicht mehr (Alexanders
    Bildschirmfoto, gemessen von 3d-druck-4d am 04.09.2026).

    Geprüft wird an der Reihenfolge im Layout: Vor den Feldern muss eine
    Beschriftung mit dem Titel der Handlung stehen, und zwar **über** ihnen und
    nicht nur als Knopf darunter.
    """
    from app.core.perceive.actions import ActionField, FeatureAction
    from app.ui.panels import FeaturePanel

    panel = FeaturePanel()
    try:
        action = FeatureAction(
            title="Merkmal verschieben",
            op="move_feature",
            fields=(
                ActionField(name="x", label="X", unit="mm", value=1.0, kind="length"),
                ActionField(name="y", label="Y", unit="mm", value=2.0, kind="length"),
            ),
        )

        row = panel._build_action(action)
        beschriftungen = [
            kind.text() for kind in row.findChildren(QLabel) if kind.text() == "Merkmal verschieben"
        ]
        assert beschriftungen, (
            "über den Feldern steht kein Titel — dann sagt nur der Knopf darunter, wozu sie gehören"
        )

        # Und sie steht **vor** den Feldern, nicht irgendwo im Kasten.
        layout = row.layout()
        erstes = layout.itemAt(0).widget()
        assert isinstance(erstes, QLabel) and erstes.text() == "Merkmal verschieben", (
            f"zuerst steht {erstes!r} statt der Überschrift"
        )
    finally:
        panel.deleteLater()
