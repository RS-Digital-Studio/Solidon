"""Die Gegenproben des Funktionsdurchgangs (RM-737, Paket D0-U, Bauplan D0 §3).

Je Prüfpunkt und Kriterium mindestens eine Gegenprobe: ein absichtlich
kaputtes Protokoll, Urteil oder Fund, das rot werden muss
(:data:`BROKEN_SAMPLES`). Grundlage ist ein vollständiges Protokoll, an dem
nichts zu finden ist (:func:`sample_protocol`); jede Gegenprobe verdirbt genau
eine Stelle davon. Ein Prüfpunkt oder Kriterium ohne Gegenprobe macht die
Suite rot (:func:`uncovered`) — ein neuer Punkt kommt nur mit seinem Rotfall.

Wer eine Gegenprobe abweist, sagt ``BrokenSample.kind``; gefahren werden sie
über ``function_report.is_red`` in ``tests/test_function_report.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from app.ui.motion import MEDIUM_MS
from app.ui.op_dialog import MAX_LEAD_WORDS
from app.ui.session import COARSE_PREVIEW_ABOVE
from tools.function_checks import (
    CHECKPOINTS,
    COARSE_NOTE,
    CRITERIA,
    LAPTOP_SIZE,
    MANUAL_WINDOW,
    START_SIZE,
    Context,
)

# --- Gegenproben -----------------------------------------------------------


def sample_context() -> Context:
    """Ein Kontext mit bekanntem Ausgang für die Gegenproben."""
    return Context(
        negative_words=(
            ("wasserdicht", "de", r"[Ww]asserdicht\w*"),
            ("Voxel", "de", r"[Vv]oxel\w*"),
            ("boolesch", "de", r"[Bb]oolesch\w*"),
            ("Normale", "de", r"Normale\b"),
            ("watertight", "en", r"[Ww]atertight"),
        ),
        frozen_texts=frozenset({"Ein eingefrorener, viel zu langer Satz über die Bohrung."}),
        coarse_note=lambda language: COARSE_NOTE,
        manual_place=lambda row: "ref-holes#operation-drill_hole",
        website_hits=lambda row: ("website/funktionen.html",),
        agent_place=lambda row: ("karte", "Handlungen rechts (bei gewähltem Körper) → Bohrung"),
    )


def _scene_print(
    ops: Sequence[str], body: str, selection: Sequence[str] = ("body1",)
) -> dict[str, Any]:
    return {
        "ops": list(ops),
        "params": {op: {} for op in ops},
        "project_params": {"wand": 2.0},
        "fits": [],
        "bodies": {"body1": body},
        "selection": list(selection),
        "camera": {"azimuth": 30.0, "elevation": 20.0},
    }


def sample_protocol() -> dict[str, Any]:
    """Ein vollständiges Protokoll, an dem kein Prüfpunkt und kein Kriterium etwas findet.

    Jede Gegenprobe in :data:`BROKEN_SAMPLES` verdirbt genau eine Stelle davon.
    """
    before = _scene_print(["create_brep_box"], "aaaa")
    applied = _scene_print(["create_brep_box", "drill_hole"], "bbbb")
    return {
        "row": {
            "id": "drill_hole",
            "kind": "operation",
            "source": "register",
            "package": "D4",
            "requirement": "koerper:1",
            "start_scene": "quader.exakt",
            "target": "operation:drill_hole",
            "menu_path": "Handlungen rechts (bei gewähltem Körper) → Bohrung",
            "shortcut": "",
        },
        "kind": "operation",
        "package": "D4",
        "spec": {
            "example_goal": "Bohrung Ø 5 mm",
            "inputs": {"feature.field:drill_hole.diameter": 5.0},
            "search_probes": [{"word": "bohren", "origin": "slicer"}],
            "questions": ["Loch machen"],
            "expectation": {
                "volume": {
                    "value": 23.8,
                    "tolerance": 0.05,
                    "origin": "Formel: Quader minus Zylinder",
                }
            },
            "fault_case": {
                "inputs": {"feature.field:drill_hole.depth": 500.0},
                "refusal": "grenzablehnung",
            },
        },
        "variant": {
            "language": "de",
            "theme": "light",
            "unit": "mm",
            "licence": "gekauft",
            "preconditions": {},
            "platform": "windows",
            "screen": "1",
            "scale": 1.0,
            "window_size": list(START_SIZE),
            "motion": True,
        },
        "version": {"commit": "a280ee8f5", "app": "0.6.1"},
        "scene": {"key": "quader.exakt", "triangles": 12, "build_s": 0.1, "eval_s": 0.2},
        "steps": [
            {
                "target": "tree.row:body1",
                "why": "ziel",
                "button": "left",
                "zone": "karte_links",
                "hit": True,
                "t": 0.1,
            },
            {
                "target": "operation:drill_hole",
                "why": "ziel",
                "button": "left",
                "zone": "karte_rechts",
                "hit": True,
                "t": 0.4,
            },
            {
                "target": "feature.field:drill_hole.diameter",
                "why": "ziel",
                "button": None,
                "typed": "5",
                "zone": "dialog",
                "hit": True,
                "t": 0.9,
            },
            {
                "target": "feature.apply",
                "why": "ziel",
                "button": "left",
                "zone": "dialog",
                "hit": True,
                "t": 1.2,
            },
        ],
        "spot": {"point": [640, 410], "covered_by": None},
        "states": {
            "before": before,
            "preview": before,
            "applied": applied,
            "undo": before,
            "redo": applied,
            "escape": before,
            "cancelled": before,
            "aborted": before,
            "after_switch": _scene_print([], "", selection=()),
        },
        "preview": {
            "bodies": {"body1": "bbbb"},
            "coarse": False,
            "banner_text": "Volumen minus 0,2 cm³",
            "volume": 23.8,
            "extent": [20.0, 20.0, 10.0],
        },
        "result": {"metrics": {"volume": 23.8, "extent": [20.0, 20.0, 10.0]}, "digest": "bbbb"},
        "cli": {"digest": "bbbb", "max_deviation_mm": 0.0, "print_equal": True},
        "timing": {
            "total_s": 0.5,
            "first_feedback_s": 0.05,
            "progress_shown_s": None,
            "cancel_shown_s": None,
            "main_gap_ms": 40.0,
            "budget_s": 1.0,
        },
        "frames": {"drag_ms": [12.0, 18.0], "reference_factor": 1.0},
        "modals": [],
        "raw_windows": [],
        "windows": [{"class": "OperationDialog", "title": "Bohrung"}],
        "messages": [
            {
                "text": "Die Bohrung reicht durch den Boden. Weniger tief bohren?",
                "actions": [
                    {
                        "label": "Tiefe anpassen",
                        "target": "finding.action:fit_depth",
                        "clicked": True,
                        "effect": True,
                    }
                ],
            }
        ],
        "texts": [
            {
                "text": "Bohrt ein rundes Loch in die gewählte Fläche.",
                "carrier": "QLabel",
                "need_px": 260,
                "width_px": 300,
                "cut": False,
                "lead": True,
            },
            {
                "text": "Übernehmen",
                "carrier": "QPushButton",
                "need_px": 80,
                "width_px": 96,
                "cut": False,
                "lead": False,
            },
        ],
        "fields": [
            {
                "label": "Durchmesser",
                "accessible_name": "Durchmesser",
                "description": "Wie weit das Loch quer gemessen wird.",
                "tooltip": "",
                "front": True,
            },
            {
                "label": "Tiefe",
                "accessible_name": "Tiefe",
                "description": "Wie weit es in den Körper reicht.",
                "tooltip": "",
                "front": True,
            },
        ],
        "tab_chain": [
            {"name": "Durchmesser", "rect": [12, 40, 120, 24]},
            {"name": "Tiefe", "rect": [12, 72, 120, 24]},
            {"name": "Übernehmen", "rect": [12, 120, 96, 28]},
        ],
        "names": ["Durchmesser", "Tiefe", "Übernehmen"],
        "focus_return": True,
        "matrix": {
            "ohne": {"state": "grau", "reason": "Erst einen Körper wählen.", "effective": None},
            "ein_koerper": {"state": "angeboten", "reason": "", "effective": True},
            "mehrere_koerper": {"state": "angeboten", "reason": "", "effective": True},
            "ein_merkmal": {"state": "fehlt", "reason": "", "effective": None},
            "mehrere_merkmale": {"state": "fehlt", "reason": "", "effective": None},
            "eine_kante": {"state": "fehlt", "reason": "", "effective": None},
        },
        "search": {
            "bohren": {
                "rank": 1,
                "hits": ["operation:drill_hole"],
                "origin": "slicer",
                "question": False,
            },
            "Loch machen": {
                "rank": 2,
                "hits": ["operation:drill_hole"],
                "origin": "fragebogen",
                "question": True,
            },
        },
        "place": {"where": "karte", "path": ["Auswahl", "Bohrung"], "error": None},
        "layout": [
            {"kind": "primary", "surface": "OperationDialog", "primary": 1, "accents": 1},
            {
                "kind": "spacing",
                "surface": "OperationDialog",
                "group": "felder",
                "spacing": 8,
                "margins": [12, 12, 12, 12],
            },
            {
                "kind": "form",
                "surface": "OperationDialog",
                "label_edges": [12, 12],
                "field_edges": [140, 140],
                "values": [{"alignment": "right", "unit": True}],
            },
        ],
        "fonts": [
            {"surface": "OperationDialog", "widget": "QLabel", "level": "body", "stylesheet": ""}
        ],
        "state_images": [
            {
                "surface": "OperationDialog",
                "widget": "Übernehmen",
                "states": {
                    "rest": "s1",
                    "hover": "s2",
                    "focus": "s3",
                    "pressed": "s4",
                    "disabled": "s5",
                },
            }
        ],
        "contrast": [
            {
                "surface": "OperationDialog",
                "widget": "QLabel",
                "theme": "light",
                "foreground": "#1a1a1a",
                "background": "#ffffff",
                "large": False,
            }
        ],
        "icons": [
            {
                "surface": "OperationDialog",
                "widget": "Hilfe",
                "text": "",
                "icon": "help",
                "own": True,
                "tooltip": "Hilfe (F1)",
                "shortcut": "F1",
                "style": "linie",
                "scale": 1.0,
                "pixmap_ratio": 1.0,
            }
        ],
        "animations": [
            {
                "surface": "OperationDialog",
                "widget": "Weitere Einstellungen",
                "duration_ms": float(MEDIUM_MS),
            }
        ],
        "scrollbars": [
            {
                "surface": "OperationDialog",
                "window_size": list(START_SIZE),
                "front": True,
                "vertical": False,
                "horizontal": False,
            },
            {
                "surface": "OperationDialog",
                "window_size": list(LAPTOP_SIZE),
                "front": True,
                "vertical": False,
                "horizontal": False,
            },
        ],
        "hover_labels": [{"kind": "hole", "label": "Bohrung Ø 5 mm"}],
        "empty_states": [
            {
                "surface": "Verlauf",
                "sentence": "Noch kein Schritt.",
                "button": "Würfel einfügen",
                "intended": False,
            }
        ],
        "licence_runs": {
            "demo_abgelaufen": {
                "writes": True,
                "enabled": False,
                "reason": "Die Demo ist abgelaufen.",
            },
            "testlauf_abgelaufen": {
                "writes": True,
                "enabled": False,
                "reason": "Der Testlauf ist abgelaufen.",
            },
            "gekauft": {"writes": True, "enabled": True, "reason": ""},
        },
        "halt": {
            "text": "Die Kette hält bei Schritt 3: Die Bohrung trifft keinen Körper.",
            "step": 3,
        },
        "insertion": {
            "outcome": "absage",
            "text": "Hier kann nichts eingefügt werden.",
            "actions": [{"label": "Einfügen beenden", "target": "menu:history.insert_end"}],
        },
        "switch": {"phases": ["vorschau", "entwurf", "rechnung"], "late_events": []},
        "revise": [
            {
                "way": "menue",
                "opened": True,
                "fields": {"diameter": 5.0},
                "params": {"diameter": 5.0},
                "history_before": 2,
                "history_after": 2,
            },
            {
                "way": "doppelklick",
                "opened": True,
                "fields": {"diameter": 5.0},
                "params": {"diameter": 5.0},
                "history_before": 2,
                "history_after": 2,
            },
        ],
        "abort": {"eval_s": 2.4, "cancel_shown_s": 2.0, "clicked": True},
        "images": ["cases/1/01-vorher.png"],
        "errors": [],
    }


@dataclass(frozen=True)
class BrokenSample:
    """Eine Gegenprobe: absichtlich kaputt, und sie muss rot werden.

    ``kind`` sagt, wer sie abweist: ``protocol`` das Urteil über
    :func:`sample_protocol` nach ``change`` (``expect`` ist das erwartete
    Ergebnis), ``verdict`` die Urteilsprüfung, ``finding`` die Prüfung der
    Funddatei, ``share`` ein Paketanteil, ``count`` die Zählung von I4.
    """

    subject: int | str
    title: str
    kind: str = "protocol"
    change: Callable[[dict[str, Any]], None] | None = None
    context: Mapping[str, Any] = field(default_factory=dict)
    expect: str = "fund"
    verdict: Mapping[str, Any] | None = None
    finding: str | None = None
    values: tuple[Any, ...] = ()


def _set(path: str, value: Any) -> Callable[[dict[str, Any]], None]:
    """Setzt einen Wert über einen Punktpfad; Zahlen greifen in Listen."""

    def change(protocol: dict[str, Any]) -> None:
        *head, last = path.split(".")
        target: Any = protocol
        for part in head:
            target = target[int(part)] if isinstance(target, list) else target[part]
        if isinstance(target, list):
            target[int(last)] = value
        else:
            target[last] = value

    return change


def _drop(key: str) -> Callable[[dict[str, Any]], None]:
    return lambda protocol: protocol.pop(key)


def _steps(*steps: Mapping[str, Any]) -> Callable[[dict[str, Any]], None]:
    return _set("steps", [dict(step) for step in steps])


def _all(*changes: Callable[[dict[str, Any]], None]) -> Callable[[dict[str, Any]], None]:
    def change(protocol: dict[str, Any]) -> None:
        for one in changes:
            one(protocol)

    return change


def _click(target: str, zone: str = "karte_rechts", why: str = "ziel") -> dict[str, Any]:
    return {"target": target, "why": why, "button": "left", "zone": zone, "hit": True}


_GOOD_VERDICT: Final[dict[str, Any]] = {
    "row": "drill_hole",
    "verdict": "gut",
    "reviewer": "stufe_b",
    "reason": "Bild und Text gelesen",
    "image": "cases/1/01-vorher.png",
    "place": "Merkmalfenster, Kopf der Bohrung",
}


def _verdict(**values: Any) -> dict[str, Any]:
    verdict = dict(_GOOD_VERDICT)
    for key, value in values.items():
        if value is None:
            verdict.pop(key, None)
        else:
            verdict[key] = value
    return verdict


_FINDING: Final = """### FD-1 Zwei Hauptknöpfe im Bohrdialog

**Art:** Gestaltung
**Schwere:** {severity}
**Funktion:** drill_hole
**Prüfpunkt:** {subject}
**Beleg:** cases/1/03-dialog.png
**Ursache:** Der Dialog setzt make_primary zweimal.
**Vorschlag:** Nur Übernehmen ist die Hauptaktion.
**Wirkung beim Kunden:** Der Kunde sieht zwei gleich laute Knöpfe.
**Stand:** offen RM-800
"""


#: Je Prüfpunkt und Kriterium mindestens eine Gegenprobe (Bauplan D0 §3).
BROKEN_SAMPLES: Final[tuple[BrokenSample, ...]] = (
    BrokenSample(1, "Suchprobe auf Rang 4", change=_set("search.bohren.rank", 4)),
    BrokenSample(
        1,
        "Weg mit MissingTargetError ist nicht auffindbar",
        change=_set("place.error", "MissingTargetError"),
    ),
    BrokenSample(
        2,
        "4 Klicks an einer Körperhandlung",
        change=_steps(
            _click("tree.row:body1", "karte_links"),
            _click("operation:drill_hole"),
            _click("feature.in_view"),
            _click("feature.every"),
            _click("feature.apply"),
        ),
    ),
    BrokenSample(
        2,
        "fehlende Schritte ergeben nicht gemessen",
        change=_drop("steps"),
        expect="nicht_gelaufen",
    ),
    BrokenSample(3, "ungleiche Abdrücke", change=_set("preview.bodies.body1", "cccc")),
    BrokenSample(
        3, "grobe Szene ohne Bandsatz", change=_set("scene.triangles", COARSE_PREVIEW_ABOVE + 1)
    ),
    BrokenSample(4, "Volumen außerhalb der Toleranz", change=_set("result.metrics.volume", 24.5)),
    BrokenSample(
        4,
        "Kommandozeilennetz mit verschobener Ecke",
        change=_all(_set("cli.print_equal", False), _set("cli.max_deviation_mm", 0.4)),
    ),
    BrokenSample(
        4,
        "Erwartung ohne Herkunft",
        change=_set("spec.expectation.volume.origin", ""),
        expect="nicht_pruefbar",
    ),
    BrokenSample(
        5,
        "Rückgängig ungleich vorher",
        change=_set("states.undo", _scene_print(["create_brep_box", "drill_hole"], "bbbb")),
    ),
    BrokenSample(
        5,
        "Escape mit gewachsenem Verlauf",
        change=_set("states.escape", _scene_print(["create_brep_box", "drill_hole"], "aaaa")),
    ),
    BrokenSample(6, "Lücke im Hauptfaden 150 ms", change=_set("timing.main_gap_ms", 150.0)),
    BrokenSample(
        6,
        "Lauf von 3 s ohne sichtbares Abbrechen",
        change=_all(_set("timing.total_s", 3.0), _set("timing.progress_shown_s", 2.0)),
    ),
    BrokenSample(7, "Meldung ohne Handlung", change=_set("messages.0.actions", [])),
    BrokenSample(7, "Handlung ohne Wirkung", change=_set("messages.0.actions.0.effect", False)),
    BrokenSample(
        8,
        "Negativwort im sichtbaren Text",
        change=_set("texts.0.text", "Macht den Körper wasserdicht."),
    ),
    BrokenSample(8, "Feld ohne eigenen Satz", change=_set("fields.1.description", "")),
    BrokenSample(
        8,
        "B „gut“ trotz V1-Treffer",
        kind="verdict",
        change=_set("texts.0.text", "Rechnet mit Voxeln."),
        verdict=_verdict(point=8),
    ),
    BrokenSample(9, "Bedarf über Platz", change=_set("texts.1.need_px", 120)),
    BrokenSample(
        9,
        "mm an einem Längenwert im Zolllauf",
        change=_all(_set("variant.unit", "inch"), _set("texts.0.text", "Bohrt 5 mm tief.")),
    ),
    BrokenSample(
        10, "Rücksprung in der Tab-Kette", change=_set("tab_chain.2.rect", [12, 8, 96, 28])
    ),
    BrokenSample(10, "doppelter Name", change=_set("names.1", "Durchmesser")),
    BrokenSample(10, "Fokus kommt nicht zurück", change=_set("focus_return", False)),
    BrokenSample(11, "Operation ohne Handbuchstelle", context={"manual_place": lambda row: None}),
    BrokenSample(
        11, "B-Urteil ohne Bild oder Stelle", kind="verdict", verdict=_verdict(point=11, image=None)
    ),
    BrokenSample(12, "Verlauf gewachsen", change=_set("revise.0.history_after", 3)),
    BrokenSample(
        12, "Feldwert ungleich Parameter", change=_set("revise.1.fields", {"diameter": 6.0})
    ),
    BrokenSample(13, "grau mit leerem Grund", change=_set("matrix.ohne.reason", "")),
    BrokenSample(13, "angeboten ohne Wirkung", change=_set("matrix.ein_koerper.effective", False)),
    BrokenSample(
        14,
        "Abdruck nach Abbruch ungleich vorher",
        change=_set("states.aborted", _scene_print(["create_brep_box", "drill_hole"], "bbbb")),
    ),
    BrokenSample(
        14,
        "Szene unter 2 s ist nicht prüfbar",
        change=_set("abort.eval_s", 0.8),
        expect="nicht_pruefbar",
    ),
    BrokenSample(
        15,
        "Haltegrund ohne Schrittnummer",
        change=_set("halt.text", "Die Kette hält: Die Bohrung trifft keinen Körper."),
    ),
    BrokenSample(15, "Absage ohne Handlung", change=_set("insertion.actions", [])),
    BrokenSample(
        16,
        "später Befund nach dem Wechsel",
        change=_set(
            "switch.late_events", [{"kind": "befund", "text": "Wand zu dünn", "phase": "rechnung"}]
        ),
    ),
    BrokenSample(
        17,
        "Menüpfad im Menü bei Ort Karte",
        context={"agent_place": lambda row: ("menue", "Datei → Bohrung")},
    ),
    BrokenSample(
        18,
        "schreibendes Ziel frei trotz Ablauf",
        change=_set("licence_runs.demo_abgelaufen.enabled", True),
    ),
    BrokenSample(18, "grau ohne Grund", change=_set("licence_runs.testlauf_abgelaufen.reason", "")),
    BrokenSample(19, "zwei Hauptknöpfe", change=_set("layout.0.primary", 2)),
    BrokenSample(
        "E1",
        "4 Klicks an einer Körperhandlung",
        change=_steps(
            _click("tree.row:body1", "karte_links"),
            _click("operation:drill_hole"),
            _click("feature.in_view"),
            _click("feature.every"),
            _click("feature.apply"),
        ),
    ),
    BrokenSample(
        "E1",
        "3 Klicks nach der Auswahl an einer Merkmalszeile",
        change=_all(
            _set("row.requirement", "merkmal:hole"),
            _steps(
                _click("tree.row:body1.hole1", "karte_links"),
                _click("feature:resize_hole"),
                _click("feature.in_view"),
                _click("feature.apply"),
            ),
        ),
    ),
    BrokenSample(
        "E2",
        "2 von 10 Zeilen mit 2 Eingaben ergeben 80 %",
        kind="share",
        values=(1, 1, 1, 0, 1, 1, 1, 1, 2, 2),
    ),
    BrokenSample(
        "E3",
        "zwei Entscheidungen ohne B-Urteil bleiben offen",
        change=_all(_set("steps.1.decision", True), _set("steps.2.decision", True)),
        expect="stufe_b",
    ),
    BrokenSample(
        "E4",
        "3 Blickwechsel",
        change=_steps(
            _click("tree.row:body1", "karte_links"),
            _click("operation:drill_hole", "karte_rechts"),
            _click("feature.in_view", "ansicht"),
            _click("feature.apply", "dialog"),
        ),
    ),
    BrokenSample(
        "E4",
        "Dialog über der bearbeiteten Stelle",
        change=_set("spot.covered_by", "OperationDialog"),
    ),
    BrokenSample(
        "E5",
        "5 Felder vorn",
        change=_set(
            "fields",
            [
                {
                    "label": f"Feld {n}",
                    "description": f"Satz Nummer {n} erklärt etwas.",
                    "front": True,
                }
                for n in range(5)
            ],
        ),
    ),
    BrokenSample(
        "E5",
        "26 deutsche Wörter über dem ersten Feld",
        change=_set("texts.0.text", " ".join(["Wort"] * (MAX_LEAD_WORDS + 1))),
    ),
    BrokenSample(
        "E6",
        "QMessageBox nach Übernehmen",
        change=_set(
            "modals",
            [{"class": "QMessageBox", "title": "Wirklich?", "allowed": False, "question": True}],
        ),
    ),
    BrokenSample(
        "E7", "gesperrter Knopf mit leerem Tooltip", change=_set("matrix.ohne.reason", " ")
    ),
    BrokenSample(
        "V1", "„wasserdicht“", change=_set("texts.0.text", "Macht den Körper wasserdicht.")
    ),
    BrokenSample(
        "V2",
        "Text aus dem eingefrorenen Bestand",
        change=_set("texts.0.text", "Ein eingefrorener, viel zu langer Satz über die Bohrung."),
    ),
    BrokenSample("V3", "Satz gleich Titel", change=_set("fields.0.description", "Durchmesser")),
    BrokenSample(
        "V4", "V4-Urteil ohne Vorhersage", kind="verdict", verdict=_verdict(criterion="V4")
    ),
    BrokenSample("V5", "Meldung ohne Handlung", change=_set("messages.0.actions", [])),
    BrokenSample(
        "V6",
        "Handbuchfenster im Protokoll",
        change=_set("windows", [{"class": MANUAL_WINDOW, "title": "Handbuch"}]),
    ),
    BrokenSample("G1", "zwei Hauptknöpfe", change=_set("layout.0.primary", 2)),
    BrokenSample("G2", "Abstand 6", change=_set("layout.1.spacing", 6)),
    BrokenSample(
        "G2",
        "zwei Abstände in einer Gruppe",
        change=lambda p: p["layout"].append(
            {
                "kind": "spacing",
                "surface": "OperationDialog",
                "group": "felder",
                "spacing": 12,
                "margins": [12, 12, 12, 12],
            }
        ),
    ),
    BrokenSample("G3", "Feldkanten 3 px versetzt", change=_set("layout.2.field_edges", [140, 143])),
    BrokenSample(
        "G4", "Stylesheet font-size: 13px", change=_set("fonts.0.stylesheet", "font-size: 13px")
    ),
    BrokenSample(
        "G5",
        "Ruhe und Fokus mit gleichem Abdruck",
        change=_set("state_images.0.states.focus", "s1"),
    ),
    BrokenSample(
        "G6", "Kontrast 3,9 bei normaler Schrift", change=_set("contrast.0.foreground", "#818181")
    ),
    BrokenSample("G7", "Symbolknopf ohne Tooltip", change=_set("icons.0.tooltip", "")),
    BrokenSample("G8", "Animation 300 ms", change=_set("animations.0.duration_ms", 300.0)),
    BrokenSample(
        "G9",
        "G9 als „mittel“",
        kind="finding",
        finding=_FINDING.format(severity="mittel", subject="G9"),
    ),
    BrokenSample(
        "Z1",
        "50 ms umgerechnet",
        change=_set("frames", {"drag_ms": [25.0], "reference_factor": 2.0}),
    ),
    BrokenSample(
        "Z2",
        "Erfolg als Meldungsfenster",
        change=_set(
            "modals",
            [{"class": "QMessageBox", "title": "Fertig", "allowed": False, "question": False}],
        ),
    ),
    BrokenSample(
        "Z3",
        "Klappenklick, B sagt ja",
        kind="verdict",
        change=lambda p: p["steps"].insert(2, _click("feature.more", "dialog", "klappe")),
        verdict=_verdict(criterion="Z3", design_judgement=True),
    ),
    BrokenSample(
        "Z4",
        "ohne Knopf, B sagt ja",
        kind="verdict",
        change=_set("empty_states.0.button", None),
        verdict=_verdict(criterion="Z4", design_judgement=True),
    ),
    BrokenSample(
        "Z5",
        "QInputDialog",
        change=_set("raw_windows", [{"class": "QInputDialog", "title": "Name", "allowed": False}]),
    ),
    BrokenSample("Z6", "Rollleiste bei 1366 x 728", change=_set("scrollbars.1.vertical", True)),
    BrokenSample("Z6", "Pixmap 1,0 bei 200 %", change=_set("icons.0.scale", 2.0)),
    BrokenSample(
        "Z7",
        "Protokoll ohne Fehlklickzahl",
        kind="verdict",
        verdict=_verdict(criterion="Z7", reviewer="stufe_c", steps=14),
    ),
    BrokenSample(
        "I1",
        "Art ohne Beschriftung, Urteil gut",
        kind="verdict",
        change=_set("hover_labels.0.label", ""),
        verdict=_verdict(criterion="I1", design_judgement=True),
    ),
    BrokenSample(
        "I2",
        "gerechnete Vorschau ohne Bandaufnahme",
        change=_set("preview.banner_text", None),
        expect="nicht_gelaufen",
    ),
    BrokenSample(
        "I3",
        "Anteil 70 %",
        kind="share",
        values=(True, True, True, True, True, True, True, False, False, False),
    ),
    BrokenSample(
        "I4", "{mit, ohne} ergibt 1 von 2", kind="count", values=(("mit", True), ("ohne", False))
    ),
    BrokenSample(
        "I5",
        "fehlt, Urteil gut",
        kind="verdict",
        change=_all(_set("spec.criteria", ["I5"]), _set("place.error", "MissingTargetError")),
        verdict=_verdict(criterion="I5", design_judgement=True),
    ),
    BrokenSample("I6", "Rang 5", change=_set("search.Loch machen.rank", 5)),
)


def uncovered(samples: Iterable[BrokenSample] = BROKEN_SAMPLES) -> set[int | str]:
    """Prüfpunkte und Kriterien ohne Gegenprobe — leer, sonst ist die Suite rot."""
    covered = {sample.subject for sample in samples}
    return (set(CHECKPOINTS) | set(CRITERIA)) - covered
