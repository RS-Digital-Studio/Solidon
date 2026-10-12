"""Die Urteile des Funktionsdurchgangs je Prüfpunkt und Kriterium (RM-737, Paket D0-U).

Liest das Messprotokoll eines Falls (``cases/<nr>/function.json``, Bauplan D0
§2.7) und gibt je Prüfpunkt und je geltendem Kriterium ein
:class:`~tools.function_checks.Outcome` nach §2.8 (:func:`judge_case`).
Schema, Schwellen und Datenmodell stehen in ``tools/function_checks.py``, die
Gegenproben in ``tools/function_samples.py``.

**Fund vor Urteil vor erfüllt.** Findet Stufe A etwas, ist es ein Fund mit
vorgeschlagener Schwere (``Issue``); besteht Stufe A und verlangt der Punkt
ein Urteil, ist er ``stufe_b``; fehlt die Messung, ``nicht_gelaufen`` — nie
„gut“. Eine Urteilsfunktion für ein Kriterium gibt ``None`` zurück, wo es an
der Zeile nicht gilt (Z3 ohne Auswahlbezug, I5 außerhalb der Zeile
Vorher/Nachher).

Szenenabdrücke werden mit ``!=`` verglichen: Rückgängig soll den Stand
**genau** herstellen (Konzept §4, Prüfpunkt 5), Abdrücke sind Hashes und
Parameter aus derselben Quelle. Messwerte dagegen nur über :func:`_close`.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from itertools import pairwise
from typing import Any, Final

from app.ui.motion import ACCENT_MS, MEDIUM_MS
from app.ui.op_dialog import MAX_FRONT_FIELDS, MAX_LEAD_WORDS, MAX_LEAD_WORDS_TRANSLATED
from app.ui.session import COARSE_PREVIEW_ABOVE
from app.ui.style import LEVELS, SPACE
from app.ui.theme import contrast_ratio
from tools.function_checks import (
    BAR_AFTER_S,
    CHECKPOINTS,
    CRITERIA,
    DESIGN_PARTS,
    EXPIRED_RUNS,
    FEEDBACK_AFTER_S,
    LAPTOP_SIZE,
    LICENCE_RUNS,
    MAIN_GAP_MS,
    MANUAL_WINDOW,
    MAX_ACCENTS,
    MAX_CLICKS,
    MAX_CLICKS_AT_FEATURE,
    MAX_DECISIONS,
    MAX_DRAG_MS,
    MAX_GLANCES,
    MAX_INPUTS,
    MAX_PRIMARY,
    MAX_RANK,
    MAX_TITLE_OVERLAP,
    MIN_CONTRAST,
    MIN_CONTRAST_LARGE,
    NOT_APPLICABLE,
    RAW_CLASSES,
    SELECTION_STAGES,
    START_SIZE,
    CaseOutcome,
    Context,
    Issue,
    Outcome,
    validate_protocol,
    words,
)

# --- Hilfen über dem Protokoll --------------------------------------------


def _word_set(text: str) -> set[str]:
    return {word.lower() for word in re.findall(r"\w+", text) if any(c.isalpha() for c in word)}


def _row(protocol: Mapping[str, Any]) -> Mapping[str, Any]:
    """Die Zeile nach §2.3; eine bloße Kennung wird zur Zeile mit ``id``."""
    row = protocol.get("row")
    if isinstance(row, Mapping):
        return row
    return {"id": str(row or ""), "kind": protocol.get("kind", "")}


def _spec(protocol: Mapping[str, Any]) -> Mapping[str, Any]:
    spec = protocol.get("spec")
    return spec if isinstance(spec, Mapping) else {}


def _list(protocol: Mapping[str, Any], key: str) -> list[Any] | None:
    value = protocol.get(key)
    return list(value) if isinstance(value, list) else None


def _map(protocol: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = protocol.get(key)
    return value if isinstance(value, Mapping) else None


def _close(first: Any, second: Any) -> bool:
    """Zwei Zahlen oder Zahlenreihen gleich bis auf Rundung (Regel 6: nie ``==``)."""
    if isinstance(first, (list, tuple)) and isinstance(second, (list, tuple)):
        return len(first) == len(second) and all(
            _close(a, b) for a, b in zip(first, second, strict=True)
        )
    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        return math.isclose(float(first), float(second), rel_tol=1e-6, abs_tol=1e-6)
    return False


def _clicks(steps: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [step for step in steps if step.get("button")]


def _is_selection(step: Mapping[str, Any]) -> bool:
    target = str(step.get("target") or "")
    return target.startswith(("tree.row:", "view:"))


def _after_selection(steps: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Die Schritte nach der letzten Auswahl — der Startzustand ist die Auswahl (§4)."""
    last = max((index for index, step in enumerate(steps) if _is_selection(step)), default=-1)
    return list(steps[last + 1 :])


def _selected_feature(steps: Sequence[Mapping[str, Any]], row: Mapping[str, Any]) -> bool:
    """Gilt die Zeile einem Merkmal oder einer Kante (E1: höchstens zwei Klicks danach)?"""
    requirement = str(row.get("requirement") or "")
    if requirement.startswith(("merkmal", "kante")):
        return True
    chosen = [str(step.get("target")) for step in steps if _is_selection(step)]
    return bool(chosen) and "." in chosen[-1].split(":", 1)[1]


def _has_selection_relation(row: Mapping[str, Any]) -> bool:
    """Z3 gilt an Zeilen mit Merkmals- oder Körperbezug (aus der Anforderung, §2.5)."""
    requirement = str(row.get("requirement") or "")
    return requirement.startswith(("merkmal", "kante", "koerper"))


def _way_clicks(steps: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Wegklicks nach der Auswahl: alles, was nicht die Handlung selbst ist."""
    return [
        step
        for step in _clicks(_after_selection(steps))
        if step.get("why") != "ziel"
        or str(step.get("target") or "") in {"search", "toolbar.search"}
    ]


def _print_without_view(state: Mapping[str, Any]) -> dict[str, Any]:
    """Ein Szenenabdruck ohne Auswahl und Kamera — die notiert Prüfpunkt 5 getrennt."""
    return {key: value for key, value in state.items() if key not in {"selection", "camera"}}


_MM_VALUE: Final = re.compile(r"\d(?:[\d.,]*\d)?\s*mm\b")


# --- Kriterien ------------------------------------------------------------


def _result(
    subject: int | str,
    issues: Sequence[Issue],
    summary: str,
    measurement: Mapping[str, Any],
    *,
    judged: bool = False,
    notes: Sequence[str] = (),
) -> Outcome:
    """Fund, wenn Stufe A etwas fand; sonst Stufe B, wenn ein Urteil aussteht."""
    if issues:
        return Outcome(
            subject, "A", "fund", summary, measurement, tuple(issues), notes=tuple(notes)
        )
    if judged:
        return Outcome(subject, "B", "stufe_b", summary, measurement, notes=tuple(notes))
    return Outcome(subject, "A", "erfuellt", summary, measurement, notes=tuple(notes))


def _missing(subject: int | str, *fields: str, stage: str = "A") -> Outcome:
    """Nicht gemessen — nie „gut“."""
    return Outcome(
        subject, stage, "nicht_gelaufen", "nicht gemessen", reason="fehlt: " + ", ".join(fields)
    )


def _e1(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    steps = _list(protocol, "steps")
    if steps is None:
        return _missing("E1", "steps")
    row = _row(protocol)
    at_feature = _selected_feature(steps, row)
    limit = MAX_CLICKS_AT_FEATURE if at_feature else MAX_CLICKS
    counted = len(_clicks(_after_selection(steps)))
    issues = []
    if counted > limit:
        where = "nach der Auswahl am Merkmal" if at_feature else "bis zum Ergebnis"
        issues.append(Issue(f"{counted} Klicks {where}, erlaubt {limit}", "mittel", "E1"))
    return _result(
        "E1", issues, f"{counted} Klicks", {"clicks": counted, "limit": limit}, judged=True
    )


def _e2(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    steps = _list(protocol, "steps")
    if steps is None:
        return _missing("E2", "steps")
    typed = sum(1 for step in steps if step.get("typed"))
    # Mehr als eine Eingabe an einer Zeile ist noch kein Fund: Die Schwelle
    # gilt für 90 % des Pakets (``function_report.package_values``). Ob eine
    # Vorgabe die zweite Eingabe erspart, urteilt Stufe B.
    return _result("E2", [], f"{typed} Eingaben", {"inputs": typed}, judged=typed > MAX_INPUTS)


def _e3(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    steps = _list(protocol, "steps")
    if steps is None:
        return _missing("E3", "steps")
    decisions = sum(1 for step in steps if step.get("decision"))
    # Mehr als eine Entscheidung: Ob sie Vorwissen verlangen, sagt nur Stufe B
    # — bis dahin bleibt der Punkt offen und nie „gut“.
    return _result(
        "E3",
        [],
        f"{decisions} Entscheidungen",
        {"decisions": decisions},
        judged=decisions > MAX_DECISIONS,
    )


def _e4(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    steps = _list(protocol, "steps")
    if steps is None:
        return _missing("E4", "steps")
    zones = [str(step.get("zone")) for step in steps if step.get("zone")]
    glances = sum(1 for before, after in pairwise(zones) if before != after)
    issues = []
    if glances > MAX_GLANCES:
        issues.append(Issue(f"{glances} Blickwechsel ({' → '.join(zones)})", "mittel", "E4"))
    spot = _map(protocol, "spot")
    covered = spot.get("covered_by") if spot else None
    if covered:
        issues.append(Issue(f"{covered} verdeckt die bearbeitete Stelle", "mittel", "E4"))
    return _result(
        "E4",
        issues,
        f"{glances} Blickwechsel",
        {"glances": glances, "zones": zones, "covered_by": covered},
    )


def _e5(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    fields_ = _list(protocol, "fields")
    texts = _list(protocol, "texts")
    if fields_ is None or texts is None:
        return _missing("E5", "fields", "texts")
    front = sum(1 for entry in fields_ if entry.get("front"))
    language = str((_map(protocol, "variant") or {}).get("language") or "de")
    limit = MAX_LEAD_WORDS if language == "de" else MAX_LEAD_WORDS_TRANSLATED
    lead = sum(words(str(entry.get("text") or "")) for entry in texts if entry.get("lead"))
    issues = []
    if front > MAX_FRONT_FIELDS:
        issues.append(Issue(f"{front} Felder vorn, erlaubt {MAX_FRONT_FIELDS}", "mittel", "E5"))
    if lead > limit:
        issues.append(Issue(f"{lead} Wörter über dem ersten Feld, erlaubt {limit}", "leicht", "E5"))
    notes = (
        [f"{front} Felder vorn: die Ausnahme, Regel sind drei"] if front == MAX_FRONT_FIELDS else []
    )
    return _result(
        "E5",
        issues,
        f"{front} Felder, {lead} Wörter",
        {"front": front, "lead_words": lead, "word_limit": limit},
        notes=notes,
    )


def _e6(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    modals = _list(protocol, "modals")
    if modals is None:
        return _missing("E6", "modals")
    asked = [m for m in modals if m.get("question") and not m.get("allowed")]
    issues = [
        Issue(
            f"Nachfrage {m.get('class')} „{m.get('title', '')}“ außerhalb Regel 19", "mittel", "E6"
        )
        for m in asked
    ]
    return _result("E6", issues, f"{len(asked)} Nachfragen", {"questions": len(asked)})


def _e7(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    matrix = _map(protocol, "matrix")
    empty = _list(protocol, "empty_states")
    messages = _list(protocol, "messages")
    if matrix is None and empty is None and messages is None:
        return _missing("E7", "matrix", "empty_states", "messages")
    issues = []
    for stage, entry in sorted((matrix or {}).items()):
        if (
            isinstance(entry, Mapping)
            and entry.get("state") == "grau"
            and not str(entry.get("reason") or "").strip()
        ):
            issues.append(Issue(f"gesperrt ohne Grund bei Auswahl „{stage}“", "schwer", "E7"))
    for entry in empty or []:
        if not entry.get("intended") and not str(entry.get("sentence") or "").strip():
            issues.append(Issue(f"leere Fläche ohne Satz: {entry.get('surface')}", "schwer", "E7"))
    for entry in messages or []:
        if not entry.get("actions"):
            issues.append(
                Issue(f"Meldung ohne Handlung: „{entry.get('text', '')}“", "schwer", "E7")
            )
    return _result("E7", issues, f"{len(issues)} Sackgassen", {"dead_ends": len(issues)})


def _negative_hits(text: str, patterns: Iterable[tuple[str, str]]) -> list[str]:
    """Wörter der Negativliste im Text, je über ihr Suchmuster aus der Wortliste."""
    return [word for word, pattern in patterns if re.search(pattern, text)]


def _v1(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    texts = _list(protocol, "texts")
    if texts is None:
        return _missing("V1", "texts")
    if not context.negative_words:
        return Outcome(
            "V1", "A", "nicht_pruefbar", "keine Negativliste", reason="Negativliste leer"
        )
    language = str((_map(protocol, "variant") or {}).get("language") or "de")
    patterns = [
        (word, pattern) for word, said_in, pattern in context.negative_words if said_in == language
    ]
    if not patterns:
        # Die Liste führt für diese Sprache keine Wörter: V1 gilt hier nicht,
        # die Quellsprache trägt die Prüfung.
        return None
    issues = []
    for entry in texts:
        hits = _negative_hits(str(entry.get("text") or ""), patterns)
        issues.extend(Issue(f"„{hit}“ in „{entry.get('text')}“", "leicht", "V1") for hit in hits)
    return _result("V1", issues, f"{len(issues)} Treffer", {"hits": len(issues)})


def _v2(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    texts = _list(protocol, "texts")
    if texts is None:
        return _missing("V2", "texts")
    long = [
        str(entry.get("text")) for entry in texts if str(entry.get("text")) in context.frozen_texts
    ]
    issues = [Issue(f"zu lang (eingefrorener Bestand): „{text}“", "leicht", "V2") for text in long]
    return _result("V2", issues, f"{len(long)} zu lange Texte", {"too_long": len(long)})


def _v3(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    fields_ = _list(protocol, "fields")
    if fields_ is None:
        return _missing("V3", "fields")
    issues = []
    for entry in fields_:
        label = str(entry.get("label") or "")
        sentence = str(entry.get("description") or entry.get("tooltip") or "").strip()
        if not sentence:
            issues.append(Issue(f"Feld „{label}“ ohne eigenen Satz", "leicht", "V3"))
            continue
        said = _word_set(sentence)
        shared = len(said & _word_set(label)) / len(said) if said else 1.0
        if shared > MAX_TITLE_OVERLAP:
            issues.append(
                Issue(
                    f"Feld „{label}“: der Satz wiederholt den Titel („{sentence}“)", "leicht", "V3"
                )
            )
    with_sentence = len(fields_) - len(issues)
    return _result(
        "V3",
        issues,
        f"{with_sentence} von {len(fields_)} Feldern mit eigenem Satz",
        {"fields": len(fields_), "own_sentence": with_sentence},
    )


def _v4(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    # Nur Stufe B: Die Vorhersage steht im Urteil (``prediction``).
    return Outcome("V4", "B", "stufe_b", "Vorhersage im Urteil")


def _v5(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    messages = _list(protocol, "messages")
    if messages is None:
        return _missing("V5", "messages")
    issues = []
    for entry in messages:
        actions = entry.get("actions") or []
        if not actions:
            issues.append(
                Issue(f"Meldung ohne Handlung: „{entry.get('text', '')}“", "mittel", "V5")
            )
        for action in actions:
            if not action.get("clicked"):
                issues.append(
                    Issue(f"Handlung „{action.get('label')}“ nie geklickt", "mittel", "V5")
                )
            elif not action.get("effect"):
                issues.append(
                    Issue(f"Handlung „{action.get('label')}“ ohne Wirkung", "mittel", "V5")
                )
    return _result(
        "V5",
        issues,
        f"{len(messages)} Meldungen",
        {"messages": len(messages)},
        judged=bool(messages),
    )


def _v6(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    windows = _list(protocol, "windows")
    if windows is None:
        return _missing("V6", "windows")
    manual = [w for w in windows if w.get("class") == MANUAL_WINDOW]
    issues = [Issue("das Handbuch musste aufgehen", "mittel", "V6")] if manual else []
    return _result(
        "V6",
        issues,
        "Handbuch offen" if manual else "ohne Handbuch",
        {"manual": bool(manual)},
        judged=True,
    )


def _layout(protocol: Mapping[str, Any], kind: str) -> list[Mapping[str, Any]] | None:
    layout = _list(protocol, "layout")
    if layout is None:
        return None
    return [entry for entry in layout if entry.get("kind") == kind]


def _g1(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    entries = _layout(protocol, "primary")
    if entries is None:
        return _missing("G1", "layout")
    issues = []
    for entry in entries:
        if int(entry.get("primary", 0)) > MAX_PRIMARY:
            issues.append(
                Issue(
                    f"{entry.get('primary')} Hauptknöpfe in {entry.get('surface')}", "leicht", "G1"
                )
            )
        if int(entry.get("accents", 0)) > MAX_ACCENTS:
            issues.append(
                Issue(f"{entry.get('accents')} Akzente in {entry.get('surface')}", "leicht", "G1")
            )
    return _result("G1", issues, f"{len(entries)} Flächen", {"surfaces": len(entries)})


def _g2(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    entries = _layout(protocol, "spacing")
    if entries is None:
        return _missing("G2", "layout")
    issues = []
    groups: dict[tuple[str, str], set[int]] = {}
    for entry in entries:
        values = [int(entry.get("spacing", 0)), *(int(v) for v in entry.get("margins") or ())]
        off = sorted({value for value in values if value % SPACE})
        if off:
            issues.append(
                Issue(
                    f"Abstand {off} in {entry.get('surface')} kein Vielfaches von {SPACE}",
                    "leicht",
                    "G2",
                )
            )
        if entry.get("group"):
            key = (str(entry.get("surface")), str(entry.get("group")))
            groups.setdefault(key, set()).add(int(entry.get("spacing", 0)))
    for (surface, group), spacings in sorted(groups.items()):
        if len(spacings) > 1:
            issues.append(
                Issue(
                    f"Gruppe {group} in {surface} mit Abständen {sorted(spacings)}", "leicht", "G2"
                )
            )
    return _result("G2", issues, f"{len(entries)} Layouts", {"layouts": len(entries)})


def _g3(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    entries = _layout(protocol, "form")
    if entries is None:
        return _missing("G3", "layout")
    issues = []
    for entry in entries:
        for name, edges in (
            ("Beschriftungen", entry.get("label_edges")),
            ("Felder", entry.get("field_edges")),
        ):
            if edges and len(set(edges)) > 1:
                issues.append(
                    Issue(
                        f"{name} in {entry.get('surface')} nicht bündig: {sorted(set(edges))}",
                        "leicht",
                        "G3",
                    )
                )
        for value in entry.get("values") or ():
            if value.get("alignment") != "right" or not value.get("unit"):
                issues.append(
                    Issue(
                        f"Wert in {entry.get('surface')} nicht rechtsbündig mit Einheit",
                        "leicht",
                        "G3",
                    )
                )
    return _result("G3", issues, f"{len(entries)} Formulare", {"forms": len(entries)})


_STYLE_SIZE: Final = re.compile(r"font(?:-size)?\s*:", re.IGNORECASE)
_STYLE_COLOUR: Final = re.compile(r"#[0-9a-f]{3,8}\b|rgba?\s*\(", re.IGNORECASE)


def _g4(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    fonts = _list(protocol, "fonts")
    if fonts is None:
        return _missing("G4", "fonts")
    issues = []
    for entry in fonts:
        if entry.get("level") not in LEVELS:
            issues.append(Issue(f"Schrift ohne Stufe an {entry.get('widget')}", "leicht", "G4"))
        sheet = str(entry.get("stylesheet") or "")
        if _STYLE_SIZE.search(sheet) or _STYLE_COLOUR.search(sheet):
            issues.append(
                Issue(
                    f"Größe oder Farbe im Stylesheet an {entry.get('widget')}: {sheet}",
                    "leicht",
                    "G4",
                )
            )
    return _result("G4", issues, f"{len(fonts)} Schriften", {"fonts": len(fonts)})


def _g5(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    images = _list(protocol, "state_images")
    if images is None:
        return _missing("G5", "state_images")
    issues = []
    for entry in images:
        states = dict(entry.get("states") or {})
        seen: dict[str, str] = {}
        for state, digest in sorted(states.items()):
            if digest in seen:
                issues.append(
                    Issue(
                        f"{entry.get('widget')}: {seen[digest]} und {state} sehen gleich aus",
                        "leicht",
                        "G5",
                    )
                )
            seen.setdefault(digest, state)
        if "rest" in states and "focus" not in states:
            issues.append(Issue(f"{entry.get('widget')}: Fokus nicht aufgenommen", "leicht", "G5"))
    return _result("G5", issues, f"{len(images)} Widgets", {"widgets": len(images)}, judged=True)


def _g6(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    pairs = _list(protocol, "contrast")
    if pairs is None:
        return _missing("G6", "contrast")
    issues = []
    lowest = math.inf
    for entry in pairs:
        ratio = contrast_ratio(str(entry["foreground"]), str(entry["background"]))
        lowest = min(lowest, ratio)
        limit = MIN_CONTRAST_LARGE if entry.get("large") or entry.get("symbol") else MIN_CONTRAST
        if ratio < limit:
            issues.append(
                Issue(
                    f"Kontrast {ratio:.2f} an {entry.get('widget')} "
                    f"({entry.get('theme')}), verlangt {limit}",
                    "leicht",
                    "G6",
                )
            )
    summary = f"kleinster Kontrast {lowest:.2f}" if pairs else "keine Paare"
    return _result(
        "G6",
        issues,
        summary,
        {"pairs": len(pairs), "lowest": None if not pairs else round(lowest, 3)},
    )


def _g7(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    icons = _list(protocol, "icons")
    if icons is None:
        return _missing("G7", "icons")
    issues = []
    for entry in icons:
        if entry.get("text"):
            continue
        name = entry.get("widget")
        if not entry.get("icon") or not entry.get("own"):
            issues.append(
                Issue(f"Symbolknopf {name} ohne Symbol aus dem eigenen Satz", "leicht", "G7")
            )
        tooltip = str(entry.get("tooltip") or "")
        if not tooltip.strip():
            issues.append(Issue(f"Symbolknopf {name} ohne Tooltip", "leicht", "G7"))
        elif entry.get("shortcut") and str(entry["shortcut"]) not in tooltip:
            issues.append(
                Issue(
                    f"Symbolknopf {name}: Tooltip ohne Kürzel {entry['shortcut']}", "leicht", "G7"
                )
            )
    styles = {str(entry.get("style")) for entry in icons if entry.get("own") and entry.get("style")}
    if len(styles) > 1:
        issues.append(Issue(f"Symbole in mehreren Stilen: {sorted(styles)}", "leicht", "G7"))
    return _result("G7", issues, f"{len(icons)} Symbole", {"icons": len(icons)})


def _g8(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    animations = _list(protocol, "animations")
    if animations is None:
        return _missing("G8", "animations")
    variant = _map(protocol, "variant") or {}
    motion = variant.get("motion", True)
    issues = []
    for entry in animations:
        duration = float(entry.get("duration_ms", 0))
        if not motion and duration > 0:
            issues.append(
                Issue(
                    f"Bewegung trotz abgeschalteter Bewegung an {entry.get('widget')}",
                    "leicht",
                    "G8",
                )
            )
        elif motion and not ACCENT_MS <= duration <= MEDIUM_MS:
            issues.append(
                Issue(
                    f"Übergang {duration:g} ms an {entry.get('widget')}, "
                    f"erlaubt {ACCENT_MS} bis {MEDIUM_MS}",
                    "leicht",
                    "G8",
                )
            )
    return _result("G8", issues, f"{len(animations)} Übergänge", {"animations": len(animations)})


def _g9(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    return Outcome("G9", "B", "stufe_b", "Gestaltungsurteil")


def _z1(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    frames = _map(protocol, "frames")
    if frames is None:
        return (
            None
            if "Z1" not in (_spec(protocol).get("criteria") or ())
            else _missing("Z1", "frames")
        )
    delays = [float(value) for value in frames.get("drag_ms") or ()]
    if not delays:
        return _missing("Z1", "frames")
    factor = float(frames.get("reference_factor", 1.0))
    worst = max(delays) * factor
    issues = (
        [
            Issue(
                f"{worst:.0f} ms bis zum nächsten Bild beim Ziehen, erlaubt {MAX_DRAG_MS}",
                "mittel",
                "Z1",
            )
        ]
        if worst > MAX_DRAG_MS
        else []
    )
    return _result("Z1", issues, f"{worst:.0f} ms", {"worst_ms": round(worst, 1), "factor": factor})


def _z2(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    modals = _list(protocol, "modals")
    if modals is None:
        return _missing("Z2", "modals")
    blocking = [m for m in modals if not m.get("allowed")]
    issues = [
        Issue(f"modales Fenster {m.get('class')} „{m.get('title', '')}“", "mittel", "Z2")
        for m in blocking
    ]
    return _result("Z2", issues, f"{len(blocking)} modale Fenster", {"modals": len(blocking)})


def _z3(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    row = _row(protocol)
    if not _has_selection_relation(row):
        return None
    steps = _list(protocol, "steps")
    if steps is None:
        return _missing("Z3", "steps")
    way = _way_clicks(steps)
    issues = [
        Issue(
            f"Wegklick nach der Auswahl: {step.get('why')} auf {step.get('target')}", "leicht", "Z3"
        )
        for step in way
    ]
    return _result("Z3", issues, f"{len(way)} Wegklicks", {"way_clicks": len(way)}, judged=True)


def _z4(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    empty = _list(protocol, "empty_states")
    if empty is None:
        return _missing("Z4", "empty_states")
    if not empty:
        return Outcome("Z4", "A", "erfuellt", "kein leerer Zustand")
    issues = [
        Issue(f"leerer Zustand ohne Knopf: {entry.get('surface')}", "leicht", "Z4")
        for entry in empty
        if not entry.get("intended") and not entry.get("button")
    ]
    return _result("Z4", issues, f"{len(empty)} leere Zustände", {"empty": len(empty)}, judged=True)


def _z5(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    raw = _list(protocol, "raw_windows")
    if raw is None:
        return _missing("Z5", "raw_windows")
    shown = [w for w in raw if w.get("class") in RAW_CLASSES and not w.get("allowed")]
    issues = [
        Issue(f"rohes Qt-Fenster {w.get('class')} „{w.get('title', '')}“", "mittel", "Z5")
        for w in shown
    ]
    return _result("Z5", issues, f"{len(shown)} rohe Fenster", {"raw": len(shown)})


def _z6(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    bars = _list(protocol, "scrollbars")
    icons = _list(protocol, "icons")
    if bars is None and icons is None:
        return _missing("Z6", "scrollbars", "icons")
    sizes = {START_SIZE, LAPTOP_SIZE}
    issues = []
    for entry in bars or []:
        size = tuple(int(v) for v in entry.get("window_size") or ())
        if (
            size in sizes
            and entry.get("front")
            and (entry.get("vertical") or entry.get("horizontal"))
        ):
            issues.append(
                Issue(
                    f"Rollleiste vorn in {entry.get('surface')} bei {size[0]} x {size[1]}",
                    "leicht",
                    "Z6",
                )
            )
    for entry in icons or []:
        scale = entry.get("scale")
        ratio = entry.get("pixmap_ratio")
        if scale is not None and ratio is not None and not _close(scale, ratio):
            issues.append(
                Issue(
                    f"Symbol {entry.get('widget')} bei {float(scale) * 100:.0f} % "
                    f"mit Pixmap {float(ratio):g}",
                    "leicht",
                    "Z6",
                )
            )
    return _result("Z6", issues, f"{len(bars or [])} Flächen", {"surfaces": len(bars or [])})


def _z7(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    # Die ersten fünf Minuten: nur Stufe C, das Protokoll steht im Urteil.
    return Outcome("Z7", "C", "nicht_gelaufen", "Stufe C", reason="nur Stufe C")


def _i1(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    labels = _list(protocol, "hover_labels")
    if labels is None:
        return (
            None
            if "I1" not in (_spec(protocol).get("criteria") or ())
            else _missing("I1", "hover_labels")
        )
    issues = [
        Issue(f"Art {entry.get('kind')} ohne Name und Maß beim Überfahren", "mittel", "I1")
        for entry in labels
        if not str(entry.get("label") or "").strip()
        or not re.search(r"\d", str(entry.get("label")))
    ]
    return _result("I1", issues, f"{len(labels)} Arten", {"kinds": len(labels)}, judged=True)


def _i2(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    preview = _map(protocol, "preview")
    if preview is None:
        return None
    if preview.get("banner_text") is None:
        return _missing("I2", "preview.banner_text")
    return Outcome(
        "I2", "B", "stufe_b", "Bandtext aufgenommen", {"banner": preview.get("banner_text")}
    )


def _i3(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    steps = _list(protocol, "steps")
    if steps is None:
        return _missing("I3", "steps")
    way = _way_clicks(steps)
    # Ein einzelnes verfehltes Ziel ist ein Vorschlag; die Schwelle gilt dem
    # Paket (``function_report.package_values``).
    issues = [Issue(f"Ziel erst nach {len(way)} Wegklicks da", "Vorschlag", "I3")] if way else []
    return _result("I3", issues, f"{len(way)} Wegklicks", {"way_clicks": len(way)})


def _i4(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    # Zählt je Paket ohne Fenster (``function_report.solution_count``).
    return None


def _i5(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    if "I5" not in (_spec(protocol).get("criteria") or ()):
        return None
    place = _map(protocol, "place")
    steps = _list(protocol, "steps")
    if place is None or steps is None:
        return _missing("I5", "place", "steps")
    issues = []
    if place.get("error"):
        issues.append(Issue("Vorher und nachher nicht erreichbar", "mittel", "I5"))
    elif len(_clicks(steps)) > 1:
        issues.append(
            Issue(f"Vorher und nachher erst nach {len(_clicks(steps))} Klicks", "mittel", "I5")
        )
    return _result(
        "I5", issues, place.get("where", "?"), {"clicks": len(_clicks(steps))}, judged=True
    )


def _probes(protocol: Mapping[str, Any], question: bool) -> dict[str, Mapping[str, Any]]:
    search = _map(protocol, "search") or {}
    return {
        word: entry
        for word, entry in search.items()
        if isinstance(entry, Mapping) and bool(entry.get("question")) is question
    }


def _rank_issues(
    probes: Mapping[str, Mapping[str, Any]], severity: str, criterion: str | None
) -> list[Issue]:
    issues = []
    for word, entry in sorted(probes.items()):
        rank = entry.get("rank")
        if rank is None or int(rank) > MAX_RANK:
            shown = "nicht gefunden" if rank is None else f"Rang {rank}"
            issues.append(Issue(f"Suche „{word}“: {shown}", severity, criterion))
    return issues


def _i6(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    probes = _probes(protocol, question=True)
    if not probes:
        return None
    issues = _rank_issues(probes, "Vorschlag", "I6")
    return _result("I6", issues, f"{len(probes)} Fragen", {"questions": len(probes)})


# --- Prüfpunkte -----------------------------------------------------------


def _combine(
    subject: int,
    parts: Iterable[Outcome | None],
    *,
    own: Sequence[Issue] = (),
    measured: bool = False,
    judged: bool = False,
    summary: str = "",
    measurement: Mapping[str, Any] | None = None,
) -> Outcome:
    """Ein Prüfpunkt aus seinen Kriterien: Fund vor Urteil vor erfüllt."""
    present = [part for part in parts if part is not None]
    issues = [*own]
    for part in present:
        if part.verdict == "fund":
            issues.extend(part.issues)
    notes = [
        f"{part.subject}: nicht prüfbar ({part.reason})"
        for part in present
        if part.verdict == "nicht_pruefbar"
    ]
    data = dict(measurement or {})
    data.update({str(part.subject): part.summary for part in present})
    if issues:
        return Outcome(subject, "A", "fund", summary, data, tuple(issues), notes=tuple(notes))
    if notes:
        # Ein Teil, der sich nicht beurteilen ließ, lässt den Prüfpunkt nicht
        # „gut“ werden — auch nicht über ein späteres Urteil der Stufe B.
        return Outcome(
            subject, "A", "nicht_pruefbar", summary, data, notes=tuple(notes), reason=notes[0]
        )
    ran = [part for part in present if part.verdict != "nicht_gelaufen"]
    if not measured and not ran:
        reasons = ", ".join(part.reason for part in present if part.reason) or "keine Messung"
        return Outcome(subject, "A", "nicht_gelaufen", "nicht gemessen", data, reason=reasons)
    if judged or any(part.verdict == "stufe_b" for part in present):
        return Outcome(subject, "B", "stufe_b", summary, data, notes=tuple(notes))
    return Outcome(subject, "A", "erfuellt", summary, data, notes=tuple(notes))


def _point_1(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    place = _map(protocol, "place")
    if place is None:
        return _missing(1, "place")
    issues = []
    if place.get("error"):
        issues.append(Issue(f"nicht auffindbar ({place.get('error')})", "schwer"))
    probes = _probes(protocol, question=False)
    issues.extend(_rank_issues(probes, "mittel", None))
    notes = [] if probes else ["keine Suchproben gemessen"]
    where = place.get("where", "?")
    return _result(
        1,
        issues,
        f"{where}, {len(probes)} Suchproben",
        {
            "where": where,
            "path": place.get("path"),
            "probes": {w: e.get("rank") for w, e in probes.items()},
        },
        judged=True,
        notes=notes,
    )


def _point_2(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    steps = _list(protocol, "steps")
    if steps is None:
        return _missing(2, "steps")
    parts = [criteria.get(key) for key in ("E1", "E3", "E4", "E5", "E6", "E7")]
    clicks = _clicks(steps)
    return _combine(
        2,
        parts,
        measured=True,
        judged=True,
        summary=f"{len(clicks)} Klicks, {sum(1 for s in steps if s.get('typed'))} Eingaben",
        measurement={
            "clicks": len(clicks),
            "way_clicks": sum(1 for s in clicks if s.get("why") != "ziel"),
            "keys": sum(1 for s in steps if s.get("key")),
            "typed": sum(1 for s in steps if s.get("typed")),
            "decisions": sum(1 for s in steps if s.get("decision")),
            "zones": [s.get("zone") for s in steps if s.get("zone")],
        },
    )


def _point_3(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    preview = _map(protocol, "preview")
    if preview is None:
        return _missing(3, "preview")
    scene = _map(protocol, "scene") or {}
    variant = _map(protocol, "variant") or {}
    coarse = int(scene.get("triangles", 0)) > COARSE_PREVIEW_ABOVE or bool(preview.get("coarse"))
    issues = []
    if coarse:
        note = context.coarse_note(str(variant.get("language") or "de"))
        if note not in str(preview.get("banner_text") or ""):
            issues.append(Issue("grobe Vorschau ohne ihren Satz im Vorschauband", "mittel"))
        return _result(3, issues, "grobe Vorschau", {"coarse": True})
    states = _map(protocol, "states") or {}
    applied = states.get("applied")
    result = _map(protocol, "result")
    if not isinstance(applied, Mapping) or result is None:
        return _missing(3, "states.applied", "result")
    shown = dict(preview.get("bodies") or {})
    kept = dict(applied.get("bodies") or {})
    differ = sorted(key for key, digest in shown.items() if kept.get(key) != digest)
    if differ:
        issues.append(Issue(f"Vorschau zeigt andere Körper als übernommen: {differ}", "schwer"))
    metrics = dict(result.get("metrics") or {})
    for key, title in (("volume", "Volumen"), ("extent", "Außenmaß")):
        if key in preview and key in metrics and not _close(preview[key], metrics[key]):
            issues.append(
                Issue(f"{title} der Vorschau {preview[key]} ≠ Ergebnis {metrics[key]}", "schwer")
            )
    return _result(
        3, issues, f"{len(shown)} Körper verglichen", {"bodies": len(shown), "coarse": False}
    )


def _point_4(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    result = _map(protocol, "result")
    if result is None:
        return _missing(4, "result")
    expectation = _spec(protocol).get("expectation")
    if not isinstance(expectation, Mapping) or not expectation:
        return _missing(4, "spec.expectation")
    without = sorted(
        key
        for key, entry in expectation.items()
        if not isinstance(entry, Mapping) or not str(entry.get("origin") or "").strip()
    )
    if without:
        return Outcome(
            4, "A", "nicht_pruefbar", "Erwartung ohne Herkunft", reason=f"ohne Herkunft: {without}"
        )
    metrics = dict(result.get("metrics") or {})
    issues = []
    for key, entry in sorted(expectation.items()):
        if key not in metrics:
            issues.append(Issue(f"{key} nicht gemessen", "schwer"))
            continue
        value, tolerance = float(entry["value"]), float(entry.get("tolerance", 0.0))
        if abs(float(metrics[key]) - value) > tolerance:
            issues.append(Issue(f"{key} {metrics[key]} statt {value} ± {tolerance}", "schwer"))
    cli = _map(protocol, "cli")
    if cli is None:
        return _missing(4, "cli")
    if not cli.get("print_equal"):
        issues.append(
            Issue(
                "Kommandozeile nicht druckgleich "
                f"(größte Abweichung {cli.get('max_deviation_mm')} mm)",
                "schwer",
            )
        )
    said = "druckgleich" if cli.get("print_equal") else "abweichend"
    return _result(
        4,
        issues,
        f"{len(expectation)} Kennzahlen, Kommandozeile {said}",
        {"metrics": metrics, "cli_deviation_mm": cli.get("max_deviation_mm")},
    )


def _point_5(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    states = _map(protocol, "states")
    if states is None or not all(
        isinstance(states.get(key), Mapping) for key in ("before", "applied", "undo", "redo")
    ):
        return _missing(5, "states.before", "states.applied", "states.undo", "states.redo")
    before, applied = states["before"], states["applied"]
    issues = []
    notes = []
    checks = [("undo", before, "Rückgängig"), ("redo", applied, "Wiederholen")]
    checks += [
        (key, before, title)
        for key, title in (("escape", "Escape"), ("cancelled", "Abbrechen"))
        if isinstance(states.get(key), Mapping)
    ]
    for key, expected, title in checks:
        got = states[key]
        if _print_without_view(got) != _print_without_view(expected):
            grown = len(got.get("ops") or ()) > len(expected.get("ops") or ())
            what = "mit gewachsenem Verlauf" if grown else "ungleich"
            issues.append(Issue(f"{title}: Stand {what}", "schwer"))
        elif got.get("selection") != expected.get("selection"):
            notes.append(f"{title}: nur die Auswahl verschieden")
    return _result(
        5,
        issues,
        f"{len(checks)} Rückwege",
        {"compared": [key for key, _, _ in checks]},
        notes=notes,
    )


def _point_6(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    timing = _map(protocol, "timing")
    if timing is None:
        return _missing(6, "timing")
    issues = []
    notes = []
    gap = float(timing.get("main_gap_ms", 0.0))
    total = float(timing.get("total_s", 0.0))
    if gap > MAIN_GAP_MS:
        issues.append(
            Issue(f"Hauptfaden {gap:.0f} ms ohne Ereignis, erlaubt {MAIN_GAP_MS}", "mittel")
        )
    if total >= FEEDBACK_AFTER_S and timing.get("first_feedback_s") is None:
        issues.append(Issue(f"{total:.1f} s ohne Zeiger oder Statuszeile", "mittel"))
    if total >= BAR_AFTER_S:
        if timing.get("progress_shown_s") is None:
            issues.append(Issue(f"{total:.1f} s ohne Fortschrittsbalken", "mittel"))
        if timing.get("cancel_shown_s") is None:
            issues.append(Issue(f"{total:.1f} s ohne sichtbares Abbrechen", "mittel"))
    budget = timing.get("budget_s")
    if budget is None:
        notes.append("kein Budget")
    elif total > float(budget):
        # Eine Überschreitung ist ein Verdacht, den ``window_bench.py`` oder
        # die Leistungstests bestätigen (Konzept §4, Prüfpunkt 6).
        notes.append(f"Verdacht: {total:.2f} s über dem Budget von {float(budget):.2f} s")
    return _result(
        6,
        issues,
        f"{total:.2f} s, Lücke {gap:.0f} ms",
        {"total_s": total, "main_gap_ms": gap, "budget_s": budget},
        notes=notes,
    )


def _point_7(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    fault = _spec(protocol).get("fault_case")
    if not fault:
        return _missing(7, "spec.fault_case")
    messages = _list(protocol, "messages")
    if messages is None:
        return _missing(7, "messages")
    own = [] if messages else [Issue("der Fehlfall ergab keine Meldung", "mittel")]
    return _combine(
        7,
        [criteria.get("V5")],
        own=own,
        measured=True,
        judged=True,
        summary=f"{len(messages)} Meldungen",
    )


def _point_8(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    parts = [criteria.get(key) for key in ("V1", "V2", "V3", "V6")]
    return _combine(8, parts, judged=True, summary="Texte und Felder")


def _point_9(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    texts = _list(protocol, "texts")
    if texts is None:
        return _missing(9, "texts")
    variant = _map(protocol, "variant") or {}
    issues = []
    for entry in texts:
        need, width = entry.get("need_px"), entry.get("width_px")
        if entry.get("cut") or (
            need is not None and width is not None and float(need) > float(width)
        ):
            issues.append(
                Issue(f"„{entry.get('text')}“ braucht {need} px, hat {width} px", "leicht")
            )
        if variant.get("unit") == "inch" and _MM_VALUE.search(str(entry.get("text") or "")):
            issues.append(Issue(f"mm im Zolllauf: „{entry.get('text')}“", "mittel"))
    return _result(
        9,
        issues,
        f"{len(texts)} Texte in {variant.get('language', '?')}",
        {"texts": len(texts), "language": variant.get("language")},
        judged=True,
    )


def _reading_order_jumps(chain: Sequence[Mapping[str, Any]]) -> list[str]:
    """Rücksprünge der Tab-Kette gegen die Lesefolge.

    Ein Rücksprung ist ein Schritt in eine Zeile darüber oder nach links in
    derselben Zeile. Die Kette endet vor ihrem Umlauf zum ersten Element.
    """
    jumps = []
    for before, after in pairwise(chain):
        bx, by, _bw, bh = (int(v) for v in before["rect"])
        ax, ay, _aw, ah = (int(v) for v in after["rect"])
        above = ay + ah <= by
        same_row = ay < by + bh and by < ay + ah
        if above or (same_row and ax < bx):
            jumps.append(f"{before.get('name')} → {after.get('name')}")
    return jumps


def _point_10(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    chain = _list(protocol, "tab_chain")
    names = _list(protocol, "names")
    if chain is None or names is None or "focus_return" not in protocol:
        return _missing(10, "tab_chain", "names", "focus_return")
    issues = [
        Issue(f"Rücksprung in der Tab-Kette: {jump}", "mittel")
        for jump in _reading_order_jumps(chain)
    ]
    shown = [str(name) for name in names]
    if any(not name.strip() for name in shown):
        issues.append(Issue("Bedienelement ohne zugänglichen Namen", "mittel"))
    doubled = sorted({name for name in shown if name.strip() and shown.count(name) > 1})
    if doubled:
        issues.append(Issue(f"doppelte Namen: {doubled}", "mittel"))
    if not protocol.get("focus_return"):
        issues.append(Issue("der Fokus kehrt nach dem Dialog nicht zurück", "mittel"))
    return _result(
        10,
        issues,
        f"{len(chain)} Tab-Schritte",
        {"chain": len(chain), "names": len(shown)},
        notes=["Bildschirmleser: ungeprüft"],
    )


def _point_11(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    row = _row(protocol)
    if row.get("kind", protocol.get("kind")) != "operation":
        return Outcome(11, "B", "stufe_b", "Fundstellen urteilt Stufe B", {"kind": row.get("kind")})
    place = context.manual_place(row)
    hits = context.website_hits(row)
    issues = [] if place else [Issue("Operation ohne Handbuchstelle", "mittel")]
    return _result(
        11,
        issues,
        place or "ohne Handbuchstelle",
        {"manual": place, "website": list(hits)},
        judged=True,
    )


def _point_12(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    ways = _list(protocol, "revise")
    if ways is None:
        return _missing(12, "revise")
    issues = []
    for way in ways:
        title = way.get("way", "?")
        if not way.get("opened"):
            issues.append(Issue(f"Schritt ändern über {title} öffnet nicht", "schwer"))
            continue
        if int(way.get("history_after", 0)) != int(way.get("history_before", 0)):
            issues.append(Issue(f"Verlauf gewachsen beim Ändern über {title}", "schwer"))
        fields_ = dict(way.get("fields") or {})
        params = dict(way.get("params") or {})
        wrong = sorted(
            key
            for key, value in fields_.items()
            if key in params and value != params[key] and not _close(value, params[key])
        )
        if wrong:
            issues.append(Issue(f"Feld ≠ Parameter über {title}: {wrong}", "schwer"))
    return _result(12, issues, f"{len(ways)} Wege", {"ways": [w.get("way") for w in ways]})


def _point_13(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    matrix = _map(protocol, "matrix")
    if matrix is None:
        return _missing(13, "matrix")
    issues = []
    for stage in SELECTION_STAGES:
        entry = matrix.get(stage)
        if not isinstance(entry, Mapping):
            issues.append(Issue(f"Auswahlstufe {stage} nicht gemessen", "mittel"))
            continue
        state = entry.get("state")
        if state == "grau" and not str(entry.get("reason") or "").strip():
            issues.append(Issue(f"grau ohne Grund bei {stage}", "schwer"))
        elif state == "angeboten" and entry.get("effective") is False:
            issues.append(Issue(f"angeboten ohne Wirkung bei {stage}", "schwer"))
    return _result(
        13,
        issues,
        "sechs Auswahlstufen",
        {stage: (matrix.get(stage) or {}).get("state") for stage in SELECTION_STAGES},
        judged=True,
    )


def _point_14(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    abort = _map(protocol, "abort")
    states = _map(protocol, "states") or {}
    if abort is None:
        return _missing(14, "abort")
    seconds = float(abort.get("eval_s", 0.0))
    if seconds < BAR_AFTER_S:
        return Outcome(
            14,
            "A",
            "nicht_pruefbar",
            f"Szene rechnet {seconds:.2f} s",
            reason=f"Szene unter {BAR_AFTER_S:g} s",
        )
    issues = []
    if abort.get("cancel_shown_s") is None:
        issues.append(Issue("kein Abbrechen sichtbar", "schwer"))
    elif not abort.get("clicked"):
        issues.append(Issue("Abbrechen nicht geklickt", "mittel"))
    after, before = states.get("aborted"), states.get("before")
    if not isinstance(after, Mapping) or not isinstance(before, Mapping):
        return _missing(14, "states.aborted", "states.before")
    if _print_without_view(after) != _print_without_view(before):
        issues.append(Issue("Stand nach dem Abbruch ≠ vorher", "schwer"))
    return _result(14, issues, f"Abbruch nach {seconds:.1f} s", {"eval_s": seconds})


def _point_15(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    halt = _map(protocol, "halt")
    insertion = _map(protocol, "insertion")
    if halt is None or insertion is None:
        return _missing(15, "halt", "insertion")
    issues = []
    step = halt.get("step")
    if step is None or not re.search(rf"(?<!\d){int(step)}(?!\d)", str(halt.get("text") or "")):
        issues.append(Issue(f"Haltegrund ohne Schrittnummer: „{halt.get('text')}“", "mittel"))
    if insertion.get("outcome") == "absage" and not insertion.get("actions"):
        issues.append(Issue("Absage an der Einfügemarke ohne Handlung", "mittel"))
    elif insertion.get("outcome") not in {"absage", "ergebnis"}:
        issues.append(
            Issue(f"Einfügemarke ohne Ergebnis oder Absage ({insertion.get('outcome')})", "mittel")
        )
    return _result(
        15,
        issues,
        f"Halt bei Schritt {step}",
        {"step": step, "insertion": insertion.get("outcome")},
    )


def _point_16(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    switch = _map(protocol, "switch")
    if switch is None:
        return _missing(16, "switch")
    late = list(switch.get("late_events") or ())
    issues = [
        Issue(f"nach dem Wechsel: {event.get('kind')} „{event.get('text', '')}“", "schwer")
        for event in late
    ]
    phases = sorted(set(switch.get("phases") or ()))
    missing = sorted({"vorschau", "entwurf", "rechnung"} - set(phases))
    notes = [f"Wechsel nicht geprüft während: {missing}"] if missing else []
    return _result(
        16, issues, f"{len(phases)} Wechsel", {"phases": phases, "late": len(late)}, notes=notes
    )


def _point_17(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    row = _row(protocol)
    agent = (
        context.agent_place(row) if row.get("kind", protocol.get("kind")) == "operation" else None
    )
    if agent is None:
        return Outcome(17, "A", "entfaellt", "ohne Agentenwerkzeug", reason="ohne_agentenwerkzeug")
    place = _map(protocol, "place")
    if place is None:
        return _missing(17, "place")
    said, path = agent
    where = str(place.get("where") or "")
    seen = {"menue": "menue", "karte": "karte"}.get(where)
    if seen is None:
        return Outcome(
            17, "A", "nicht_pruefbar", where, reason=f"Ort {where} ohne Gegenstück im Agentenweg"
        )
    told = "menue" if said == "katalog" else said
    issues = [] if told == seen else [Issue(f"Agent nennt „{path}“, gefunden {where}", "mittel")]
    return _result(17, issues, path, {"agent": path, "found": where})


def _point_18(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    runs = _map(protocol, "licence_runs")
    if runs is None:
        return _missing(18, "licence_runs")
    issues = []
    for state in LICENCE_RUNS:
        entry = runs.get(state)
        if not isinstance(entry, Mapping):
            issues.append(Issue(f"Lizenzlauf {state} fehlt", "mittel"))
            continue
        if not entry.get("enabled") and not str(entry.get("reason") or "").strip():
            issues.append(Issue(f"grau ohne Grund bei {state}", "schwer"))
        if state in EXPIRED_RUNS and entry.get("writes") and entry.get("enabled"):
            issues.append(Issue(f"schreibendes Ziel frei trotz {state}", "schwer"))
    return _result(
        18,
        issues,
        f"{len(runs)} Lizenzläufe",
        {state: (runs.get(state) or {}).get("enabled") for state in LICENCE_RUNS},
    )


def _point_19(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    parts = [criteria.get(key) for key in DESIGN_PARTS if key != "Z7"]
    # Der Gesamteindruck — hochwertig, aufgeräumt, nichts Überflüssiges —
    # urteilt immer Stufe B (Konzept §4).
    return _combine(19, parts, judged=True, summary="Gestaltung")


JudgeCriterion = Callable[[Mapping[str, Any], Context], Outcome | None]
JudgePoint = Callable[[Mapping[str, Any], Context, Mapping[str, Outcome]], Outcome]


CRITERION_JUDGES: Final[dict[str, JudgeCriterion]] = {
    "E1": _e1,
    "E2": _e2,
    "E3": _e3,
    "E4": _e4,
    "E5": _e5,
    "E6": _e6,
    "E7": _e7,
    "V1": _v1,
    "V2": _v2,
    "V3": _v3,
    "V4": _v4,
    "V5": _v5,
    "V6": _v6,
    "G1": _g1,
    "G2": _g2,
    "G3": _g3,
    "G4": _g4,
    "G5": _g5,
    "G6": _g6,
    "G7": _g7,
    "G8": _g8,
    "G9": _g9,
    "Z1": _z1,
    "Z2": _z2,
    "Z3": _z3,
    "Z4": _z4,
    "Z5": _z5,
    "Z6": _z6,
    "Z7": _z7,
    "I1": _i1,
    "I2": _i2,
    "I3": _i3,
    "I4": _i4,
    "I5": _i5,
    "I6": _i6,
}

#: Die 19 Prüfpunkte (Konzept §4, Bauplan D0 §3.1).

POINT_JUDGES: Final[dict[int, JudgePoint]] = {
    1: _point_1,
    2: _point_2,
    3: _point_3,
    4: _point_4,
    5: _point_5,
    6: _point_6,
    7: _point_7,
    8: _point_8,
    9: _point_9,
    10: _point_10,
    11: _point_11,
    12: _point_12,
    13: _point_13,
    14: _point_14,
    15: _point_15,
    16: _point_16,
    17: _point_17,
    18: _point_18,
    19: _point_19,
}


# --- Ein Fall --------------------------------------------------------------


def _not_applicable(spec: Mapping[str, Any]) -> dict[str, str]:
    """``not_applicable`` aus der Spezifikation, Schlüssel als Text (TOML kennt nur Texte)."""
    given = spec.get("not_applicable")
    return (
        {str(key): str(value) for key, value in given.items()} if isinstance(given, Mapping) else {}
    )


def _apply_not_applicable(outcome: Outcome, reasons: Mapping[str, str]) -> Outcome:
    """*entfällt* aus der Spezifikation — nur mit einem Grund aus der Liste, nie über einen Fund."""
    reason = reasons.get(str(outcome.subject))
    if reason is None:
        return outcome
    if reason not in NOT_APPLICABLE:
        return Outcome(
            outcome.subject,
            outcome.stage,
            "nicht_pruefbar",
            "fremder Grund",
            reason=f"fremder entfällt-Grund: {reason}",
        )
    if outcome.verdict == "fund":
        return replace(
            outcome,
            notes=(
                *outcome.notes,
                f"Spezifikation sagt entfällt ({reason}), gemessen ist ein Fund",
            ),
        )
    return Outcome(
        outcome.subject, outcome.stage, "entfaellt", NOT_APPLICABLE[reason], reason=reason
    )


def judge_case(protocol: Mapping[str, Any], context: Context) -> CaseOutcome:
    """Alle Prüfpunkte und die geltenden Kriterien eines Falls."""
    problems = tuple(validate_protocol(protocol))
    reasons = _not_applicable(_spec(protocol))
    images = tuple(str(image) for image in _list(protocol, "images") or ())

    def evidence(outcome: Outcome, fields: Iterable[str]) -> Outcome:
        # Beleg nach §2.8: die Bilder des Falls und die Stellen im Protokoll,
        # die das Urteil gelesen hat.
        read = tuple(f"function.json#{name}" for name in fields if name in protocol)
        return replace(outcome, evidence=(*images, *read))

    criteria: dict[str, Outcome] = {}
    for key, judge in CRITERION_JUDGES.items():
        outcome = judge(protocol, context)
        if outcome is not None:
            criteria[key] = evidence(_apply_not_applicable(outcome, reasons), CRITERIA[key].fields)
    points: dict[int, Outcome] = {}
    for number, judge_point in POINT_JUDGES.items():
        outcome = _apply_not_applicable(judge_point(protocol, context, criteria), reasons)
        points[number] = evidence(outcome, CHECKPOINTS[number].fields)
    variant = _map(protocol, "variant") or {}
    return CaseOutcome(_row(protocol), variant, points, criteria, problems)


def compare_themes(light: Mapping[str, Any], dark: Mapping[str, Any]) -> list[Issue]:
    """Z6: hell und dunkel zeigen dieselben Flächen mit derselben Zahl Akzente."""

    def accents(protocol: Mapping[str, Any]) -> dict[str, int]:
        return {
            str(entry.get("surface")): int(entry.get("accents", 0))
            for entry in _layout(protocol, "primary") or []
        }

    shown, other = accents(light), accents(dark)
    issues = []
    if set(shown) != set(other):
        issues.append(
            Issue(f"Flächen hell {sorted(shown)} ≠ dunkel {sorted(other)}", "leicht", "Z6")
        )
    for surface in sorted(set(shown) & set(other)):
        if shown[surface] != other[surface]:
            issues.append(
                Issue(
                    f"Akzente in {surface}: hell {shown[surface]}, dunkel {other[surface]}",
                    "leicht",
                    "Z6",
                )
            )
    return issues
