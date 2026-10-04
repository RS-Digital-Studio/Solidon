"""Jede angebotene Handlung sagt, was sie außer ihrem Zweck verändert (RM-090, Produktkompass 4.3).

Gesucht wird im Quelltext des Kerns: Jede ``Action(...)`` mit einer festen
Kennung kann als Knopf an einem Befund stehen. Fehlt ihr Satz, stünde der Knopf
ohne Nebenfolge in der Befundkarte; ein Satz ohne Handlung ist toter Text.
"""

from __future__ import annotations

import ast
from pathlib import Path

import app.core
from app.core.action_effects import NOTHING, SIDE_EFFECTS, side_effect


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
