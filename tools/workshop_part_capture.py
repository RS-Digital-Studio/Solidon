"""Einen Bibliotheksbaustein über echte Katalog-, Werte- und Vorschaugesten einsetzen."""

from __future__ import annotations

from time import monotonic
from typing import Any


def capture_step(tutorial: Any, step: dict[str, Any], body: str) -> list[dict[str, Any]]:
    """Suche, Auswahl, Einfügen und jedes Feld als getrennte reale Handlungen aufnehmen."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.core.knowledge.parts import PARTS
    from app.i18n import get_language
    from app.ui import guide_targets
    from app.ui.catalog import PartCatalog
    from tools.make_workshop_videos import write_json
    from tools.workshop_inventory_capture import _click, _frame, _type

    window = tutorial.window
    language = get_language()
    scenes: list[dict[str, Any]] = []
    entry_end: int | None = None

    def record(key: str, dialog: Any = None, action: Any = None, target: Any = None) -> None:
        stage = step["stages"][key]
        scenes.append(
            tutorial.control_scene(
                f"{step['key']}-{key}",
                tuple(stage["de"][name] for name in ("title", "voice_before", "voice_after")),
                tuple(stage["en"][name] for name in ("title", "voice_before", "voice_after")),
                dialog=dialog,
                action=action,
                target=target,
                minimum_seconds=stage.get("minimum_seconds", 0),
                short=bool(stage.get("short", False)),
            )
        )

    def catalog(opened: Any) -> None:
        nonlocal entry_end
        if not isinstance(opened, PartCatalog):
            raise RuntimeError("Der Bausteinkatalog fehlt; den sichtbaren Einstieg prüfen.")
        deadline = monotonic() + 120
        while not all(spec.name in opened._previews for spec in PARTS.all()):
            if monotonic() > deadline:
                raise RuntimeError("Katalogbilder fehlen; die Aufnahme vor der Auswahl anhalten.")
            tutorial.settle(3)
        _frame(tutorial, dialog=opened, seconds=1.5)
        entry_end = len(tutorial.recorder.slides)
        record("catalog", opened)
        record(
            "search",
            opened,
            lambda: _type(tutorial, opened.search, step["search_" + language], dialog=opened),
            opened.search,
        )
        item = opened._item_named(step["part"])
        if item is None:
            raise RuntimeError("Der benannte Baustein fehlt; Suche und Bibliothek prüfen.")
        opened.list.scrollToItem(item)
        tutorial.settle(8)

        def choose() -> None:
            point = opened.list.visualItemRect(item).center()
            QTest.mouseMove(opened.list.viewport(), point, 100)
            tutorial.recorder.click(
                "", "", dialog=opened, target=opened.list.viewport().mapToGlobal(point)
            )
            QTest.mouseClick(
                opened.list.viewport(), Qt.MouseButton.LeftButton, pos=point, delay=100
            )
            tutorial.settle(10)
            _frame(tutorial, dialog=opened, seconds=1.5)

        record("choice", opened, choose, opened.list)
        if (
            opened.list.currentItem() is not item
            or opened._insert is None
            or not opened._insert.isEnabled()
        ):
            raise RuntimeError("Einfügen ist gesperrt; gewählten Körper und Zielfläche prüfen.")
        record(
            "insert",
            opened,
            lambda: _click(tutorial, opened._insert, dialog=opened),
            opened._insert,
        )

    if window.object_tree.selected_features() != ((body, step["feature"]),):
        raise RuntimeError("Die geplante Zielfläche ist nicht gewählt; Aufnahme davor korrigieren.")
    button = guide_targets.widget_for(window, "selection.parts")
    if not button.isVisible() or not button.isEnabled():
        raise RuntimeError("Der echte Bausteinknopf ist nicht erreichbar; Auswahl prüfen.")
    first = len(tutorial.recorder.slides)
    tutorial.recorder.add("", "", 2.0, target=button)
    action_first = len(tutorial.recorder.slides)
    tutorial.modal(lambda: _click(tutorial, button), catalog)
    if entry_end is None:
        raise RuntimeError("Der geöffnete Katalog wurde nicht aufgenommen.")
    entry = step["stages"]["entry"]
    scenes.insert(
        0,
        {
            "key": f"{step['key']}-entry",
            **entry[language],
            "first_slide": first,
            "last_slide": entry_end,
            "action_first_slide": action_first,
            "action_last_slide": entry_end - 1,
            "model_crop": [0, 0, *tutorial.recorder.frame_size],
            "short": bool(entry.get("short", False)),
        },
    )
    tutorial.settle(20)
    dialog = window._op_dialog
    if dialog is None or not dialog.isVisible() or dialog.spec.name != step["op"]:
        raise RuntimeError("Der Baustein hat seinen Wertedialog nicht geöffnet; Kundenweg prüfen.")
    scenes.extend(tutorial.operation_dialog_scenes(step, dialog))
    actual = tutorial.session.project.document.ops[-1]
    if actual.op != step["op"]:
        raise RuntimeError("Im Verlauf steht eine andere Operation; Aufnahme anhalten.")
    write_json(
        tutorial.folder / f"part-{step['key']}.json",
        {
            "part": step["part"],
            "operation": actual.op,
            "stored_values": dict(actual.params),
        },
    )
    return scenes
