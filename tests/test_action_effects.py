"""Jede angebotene Handlung sagt, was sie außer ihrem Zweck verändert (RM-090, Produktkompass 4.3).

Gesucht wird im Quelltext des Kerns: Jede ``Action(...)`` mit einer festen
Kennung kann als Knopf an einem Befund stehen. Fehlt ihr Satz, stünde der Knopf
ohne Nebenfolge in der Befundkarte; ein Satz ohne Handlung ist toter Text.
"""

from __future__ import annotations

import ast
from pathlib import Path

import app.core
from app.core.action_effects import (
    NOTHING,
    SIDE_EFFECTS,
    WHEN_APPLIED,
    effect_worth_showing,
    side_effect,
)


def _core_action_ids() -> set[str]:
    root = Path(app.core.__file__).parent
    found: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Action"
            ):
                continue
            argument = node.args[0] if node.args else None
            for keyword in node.keywords:
                if keyword.arg == "id":
                    argument = keyword.value
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                found.add(argument.value)
    return found


def test_every_action_the_core_offers_names_its_side_effect() -> None:
    from app.ui.panels import FINDING_ACTIONS

    offered = _core_action_ids()
    assert len(offered) > 60, f"nur {len(offered)} Handlungen gefunden — dann prüft das nichts"
    offered |= {action.id for actions in FINDING_ACTIONS.values() for action in actions}
    missing = sorted(identifier for identifier in offered if side_effect(identifier) is None)
    assert not missing, f"Handlung ohne Nebenfolge (action_effects.SIDE_EFFECTS): {missing}"
    unused = sorted(set(SIDE_EFFECTS) - offered)
    assert not unused, f"Nebenfolge ohne Handlung — austragen: {unused}"


def test_the_actions_that_move_or_cut_say_so() -> None:
    """Stichproben, an denen ein „ändert nichts“ eine Lüge wäre."""
    for identifier in ("arrange_on_bed", "scale_to_fit", "split_bodies", "decimate_mesh"):
        assert SIDE_EFFECTS[identifier] is not NOTHING
        assert "nichts" not in str(SIDE_EFFECTS[identifier])
    assert "alle Körper" in str(SIDE_EFFECTS["arrange_on_bed"])
    assert SIDE_EFFECTS["show_locations"] is NOTHING


def test_only_an_effect_that_changes_something_stands_under_the_main_button() -> None:
    """Die Floskeln bleiben in Kurzhilfe und Beschreibung, nicht unter dem Knopf (RM-508).

    „Ändert nichts am Modell.“ stand unter der Mehrzahl aller Handlungen und
    verdrängte im Prüfbericht die nächste Zeile.
    """
    floskeln = {key for key, effect in SIDE_EFFECTS.items() if effect in (NOTHING, WHEN_APPLIED)}
    assert len(floskeln) > len(SIDE_EFFECTS) / 2, "sonst prüft die Gegenprobe nichts"
    assert not any(effect_worth_showing(key) for key in floskeln)
    assert all(effect_worth_showing(key) for key in set(SIDE_EFFECTS) - floskeln)
    assert effect_worth_showing("arrange_on_bed")
    assert not effect_worth_showing("show_location")
    assert not effect_worth_showing("correct_input")
    assert not effect_worth_showing("unbekannt")


#: Handlungen des Kerns, die das Hauptfenster nicht selbst einlöst — mit der
#: Stelle, die es tut. Der Name der Handlung steht dort im Quelltext.
WIRED_ELSEWHERE: dict[str, str] = {
    # Suchradius und Stelle kennt nur der Dialog der örtlichen Erkennung.
    "enlarge_radius": "local_recognition.py",
    "shrink_radius": "local_recognition.py",
    "pick_elsewhere": "local_recognition.py",
    "repair_mesh": "local_recognition.py",
    # Datei und Revision des Filamentlagers hat nur seine Ansicht.
    "reload": "filament_inventory.py",
    "restore_backup": "filament_inventory.py",
    "set_aside_file": "filament_inventory.py",
    # Am konkreten Bausteinfehler mit den gelesenen Bytes (Katalog).
    "choose": "main_window.py",
    "use_suggested_name": "main_window.py",
}

#: Handlungen ohne Knopf, mit Grund. Sie bleiben Rat zum Lesen
#: (``dialogs.unhandled_advice``) oder sind das Schließen selbst.
NOT_A_BUTTON: dict[str, str] = {
    "cancel": "das Schließen, kein Vorschlag",
    # Der Rückmeldedialog trägt die drei Wege als eigene Knöpfe
    # (``SupportDialog.send``, ``save_folder``, ``by_mail``).
    "retry_send": "Knopf im Rückmeldedialog",
    "save_report": "Knopf im Rückmeldedialog",
    "send_by_mail": "Knopf im Rückmeldedialog",
    # Ein Schritt im Slicer, den Solidon nicht ausführen kann.
    "split_filament_files": "Schritt im Slicer",
    # Eine Eingabe des Nutzers am Schritt, in der Auswahl oder im Bild; der
    # Satz sagt, welche. Ein Knopf müsste raten, welcher Wert gemeint ist.
    "check_input": "Rat zum Lesen",
    "coarser_pitch": "Rat zum Lesen",
    "fewer_iterations": "Rat zum Lesen",
    "fix_parent": "Rat zum Lesen",
    "open_sketch": "Rat zum Lesen",
    "pick_face": "Rat zum Lesen",
    "pick_feature": "Rat zum Lesen",
    "pick_image": "Rat zum Lesen",
    "pick_in_tree": "Rat zum Lesen",
    "repack_file": "Rat zum Lesen",
    "smaller_bodies": "Rat zum Lesen",
    "smaller_diameter": "Rat zum Lesen",
    "texture.pick_cylinder": "Rat zum Lesen",
    "texture.wrap_flat": "Rat zum Lesen",
    "use_parts": "Rat zum Lesen",
    "use_planar": "Rat zum Lesen",
    "use_texture": "Rat zum Lesen",
    "write_target": "Rat zum Lesen",
    "sketch.check_position": "Rat zum Lesen",
    "sketch.clear_axis_feature": "Rat zum Lesen",
    "sketch.clear_up_to": "Rat zum Lesen",
    "sketch.enter_height": "Rat zum Lesen",
    "sketch.flip_plane": "Rat zum Lesen",
    "sketch.pick_face": "Rat zum Lesen",
    "sketch.pick_round_feature": "Rat zum Lesen",
    "sketch.use_all_regions": "Rat zum Lesen",
    "sketch.use_global_plane": "Rat zum Lesen",
}


def test_every_action_of_the_core_is_wired_in_the_window_or_named() -> None:
    """Jede Handlung des Kerns hat im Fenster einen Handler oder einen Grund (RM-771).

    Ohne einlösbaren Vorschlag fiel der Fehlerdialog auf *Fehlerbericht
    erstellen* zurück, und ein Kunde schickte einen Bedienfehler als
    Absturzbericht (S-20261010-e5014c). Diesen Rückfall hat jetzt nur noch der
    ``InternalError``; dafür muss jede andere Handlung ankommen. Gelesen wird
    ``MainWindow.error_handlers`` selbst, ohne Fenster: ein Platzhalter steht
    für das Fenster, die Handler werden nur aufgezählt.
    """
    from unittest.mock import MagicMock

    from app.ui import main_window

    window = MagicMock()
    window._write_failure = None
    known = set(main_window.MainWindow.error_handlers(window))
    # Die zwei Wege eines gescheiterten Schreibens stehen nur, solange es eines gibt.
    window._write_failure = object()
    known |= set(main_window.MainWindow.error_handlers(window))
    assert len(known) > 60, f"nur {len(known)} Handler gefunden — dann prüft das nichts"

    unknown = sorted(
        identifier
        for identifier in SIDE_EFFECTS
        if identifier not in known
        and identifier not in WIRED_ELSEWHERE
        and identifier not in NOT_A_BUTTON
    )
    assert not unknown, (
        "Handlung ohne Handler im Fenster und ohne Grund — verdrahten oder in "
        f"NOT_A_BUTTON/WIRED_ELSEWHERE begründen: {unknown}"
    )
    stale = sorted((set(WIRED_ELSEWHERE) | set(NOT_A_BUTTON)) & known)
    assert not stale, f"Hat inzwischen einen Handler im Fenster — Ausnahme austragen: {stale}"
    gone = sorted((set(WIRED_ELSEWHERE) | set(NOT_A_BUTTON)) - set(SIDE_EFFECTS))
    assert not gone, f"Bietet der Kern nicht mehr an — Ausnahme austragen: {gone}"

    ui = Path(main_window.__file__).parent
    for identifier, file in WIRED_ELSEWHERE.items():
        source = (ui / file).read_text(encoding="utf-8")
        assert f'"{identifier}"' in source, f"{identifier} ist in {file} nicht verdrahtet"
