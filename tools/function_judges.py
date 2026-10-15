"""Die Urteile des Funktionsdurchgangs je Kriterium und ihre Hilfen (RM-737, Paket D0-U).

Liest das Messprotokoll eines Falls (``cases/<nr>/function.json``, Schema in
:data:`~tools.function_checks.PROTOCOL_SCHEMA`) und gibt je geltendem
Kriterium E1 bis I6 ein :class:`~tools.function_checks.Outcome` (Konzept §4,
:data:`CRITERION_JUDGES`). Die Prüfpunkte und das Urteil über einen ganzen
Fall (``judge_case``) stehen in ``tools/function_points.py``, das die Hilfen
über dem Protokoll von hier nimmt. Schema, Schwellen und Datenmodell stehen
in ``tools/function_checks.py``, die Gegenproben in
``tools/function_samples.py``.

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

import functools
import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from itertools import dropwhile, pairwise
from typing import Any, Final

from app.ui.motion import ACCENT_MS, MEDIUM_MS
from app.ui.op_dialog import MAX_FRONT_FIELDS, MAX_LEAD_WORDS, MAX_LEAD_WORDS_TRANSLATED
from app.ui.style import LEVELS, SPACE
from app.ui.theme import contrast_ratio
from tools.function_checks import (
    MAIN_PHASES,
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
    NOT_FOUND,
    RAW_CLASSES,
    REFERENCE_FACTOR_AT,
    SMALLEST_WINDOW,
    Context,
    Issue,
    Outcome,
    words,
)
from tools.function_list import BODY_SELECTIONS, FEATURE_REQUIREMENT, FEATURE_SELECTIONS

# --- Hilfen über dem Protokoll --------------------------------------------


def _word_set(text: str) -> set[str]:
    return {word.lower() for word in re.findall(r"\w+", text) if any(c.isalpha() for c in word)}


def _row(protocol: Mapping[str, Any]) -> Mapping[str, Any]:
    """Die Zeile nach Konzept §3; eine bloße Kennung wird zur Zeile mit ``id``."""
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


def _path(protocol: Mapping[str, Any]) -> list[Mapping[str, Any]] | None:
    """Die Schritte des Hauptwegs (:data:`MAIN_PHASES`), ``None`` ohne sie.

    Nur sie zählen für Prüfpunkt 2 und E1 bis E4: Suche, Escape, Matrix und die
    übrigen Phasen des Prüfstands klicken auch, aber nicht auf dem Weg des
    Kunden zum Beispielziel. Trägt das Protokoll keinen Schritt des Hauptwegs,
    ist der Weg nicht gemessen — nie „gut“.
    """
    steps = _list(protocol, "steps")
    if steps is None:
        return None
    path = [
        step for step in steps if isinstance(step, Mapping) and step.get("phase") in MAIN_PHASES
    ]
    return path or None


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
    return target.startswith(("tree.row:", "view:", "view.edge:"))


def _route_targets(row: Mapping[str, Any]) -> list[str]:
    """Die Ziele des Auswahlwegs der Zeile (``Row.route`` aus ``function_list``)."""
    return [
        str(click.get("target"))
        for click in row.get("route") or ()
        if isinstance(click, Mapping) and click.get("target")
    ]


def _leading_selection(steps: Sequence[Mapping[str, Any]], row: Mapping[str, Any]) -> int:
    """Wie viele Schritte am Anfang die Startauswahl herstellen (Konzept §4).

    Trägt die Zeile ihren Auswahlweg (``route``), endet die Startauswahl mit dem
    Klick, der dessen letztes Ziel **trifft** (``why`` ``ziel``): Die Wegklicks
    davor — Reiter, Klappe, Rollen — tragen dasselbe Ziel, und mit dem ersten
    von ihnen zu enden zählte den Rest der Auswahl als Klicks danach (Probelauf,
    F-17: drei Klicks nach der Auswahl an einer Befundhandlung). Ohne Treffer
    endet sie am letzten Schritt mit diesem Ziel. Sonst sind es die führenden
    Auswahlklicks. Ein Klick ins Bild mitten im Weg (*Im Bild einstellen*, eine
    platzierende Operation) oder ein zweiter Eingang ist ein Schritt des Kunden
    und zählt mit.
    """
    route = _route_targets(row)
    if route:
        last = route[-1]
        aimed = [index for index, step in enumerate(steps) if step.get("target") == last]
        hit = [index for index in aimed if steps[index].get("why") == "ziel"]
        if hit:
            return hit[0] + 1
        return aimed[-1] + 1 if aimed else 0
    count = 0
    for step in steps:
        if not _is_selection(step):
            break
        count += 1
    return count


def _after_selection(
    steps: Sequence[Mapping[str, Any]], row: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """Die Schritte nach der Startauswahl."""
    return list(steps[_leading_selection(steps, row) :])


def _selected_feature(steps: Sequence[Mapping[str, Any]], row: Mapping[str, Any]) -> bool:
    """Gilt die Zeile einem Merkmal oder einer Kante (E1: höchstens zwei Klicks danach)?

    Aus der Anforderung der Zeile (``function_list``: ``merkmal:<art>``, die
    Merkmalsauswahlen, ``kante``) oder, wo sie fehlt, aus der Startauswahl: ein
    Merkmal ist eine Baumzeile oder Stelle im Bild mit Merkmal
    (``tree.row:obj_1.hole_1``), eine Kante ihre Stelle im Bild
    (``view.edge:obj_1``). Ein Befund ist keines, auch wenn sein Code
    einen Punkt trägt (``finding:arrange.below_bed``, Probelauf F-17).
    """
    requirement = str(row.get("requirement") or "")
    if requirement.startswith(FEATURE_REQUIREMENT) or requirement in FEATURE_SELECTIONS:
        return True
    if requirement == "kante":
        return True
    chosen = [str(step.get("target")) for step in steps[: _leading_selection(steps, row)]]
    if not chosen:
        return False
    kind, _separator, rest = chosen[-1].partition(":")
    return kind == "view.edge" or (kind in ("tree.row", "view") and "." in rest)


def _has_selection_relation(row: Mapping[str, Any]) -> bool:
    """Z3 und die Stelle von E4 gelten an Zeilen mit Merkmals- oder Körperbezug.

    Abgelesen am Auswahlweg der Zeile (eine Baumzeile darin) oder an ihrer
    Anforderung nach ``function_list``: Körper, Merkmal, Kante, Körperzustand.
    """
    if any(target.startswith("tree.row:") for target in _route_targets(row)):
        return True
    requirement = str(row.get("requirement") or "")
    return (
        requirement.startswith((FEATURE_REQUIREMENT, "koerper:"))
        or requirement in FEATURE_SELECTIONS
        or requirement in BODY_SELECTIONS
    )


def _number(value: Any) -> float | None:
    """Ein Messwert als Zahl; ``None``, wo der Prüfstand nichts gemessen hat.

    ``null`` im Protokoll heißt nicht gemessen (``validate_protocol``) — nie
    Null und nie ein Absturz.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _settled(
    subject: int | str,
    issues: Sequence[Issue],
    absent: Sequence[str],
    summary: str,
    measurement: Mapping[str, Any],
    *,
    judged: bool = False,
    notes: Sequence[str] = (),
) -> Outcome:
    """Fund bleibt Fund, auch wenn eine zweite Messung fehlt; sonst fehlt sie.

    Ein gemessener Verstoß geht nicht verloren, weil daneben etwas nicht
    gemessen wurde — das Fehlende steht als Vermerk dabei. Ohne Verstoß heißt
    ein fehlender Teil „nicht gelaufen“, nie „erfüllt“.
    """
    if issues:
        extra = [f"fehlt: {', '.join(absent)}"] if absent else []
        return _result(subject, issues, summary, measurement, notes=(*notes, *extra))
    if absent:
        return _missing(subject, *absent)
    return _result(subject, issues, summary, measurement, judged=judged, notes=notes)


def _way_clicks(
    steps: Sequence[Mapping[str, Any]], row: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """Wegklicks nach der Startauswahl: alles, was nicht die Handlung selbst ist."""
    return [
        step
        for step in _clicks(_after_selection(steps, row))
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


def _input_clicks(steps: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Klicks in ein Feld, in das danach getippt wird — Eingaben, die E2 zählt.

    E1 zählt Klicks „mit den Vorgaben“ (Konzept §4); wer eine Zahl tippt,
    weicht von der Vorgabe ab, und den Klick ins Feld zählte E1 sonst doppelt
    mit der Eingabe (Probelauf F-18: *Parameter anlegen* mit vier Klicks).
    """
    typed = {str(step.get("target")) for step in steps if step.get("typed")}
    return [
        step
        for step in _clicks(steps)
        if step.get("why") == "ziel" and str(step.get("target")) in typed
    ]


def _short_of_goal(protocol: Mapping[str, Any], steps: Sequence[Mapping[str, Any]]) -> str | None:
    """Warum der Weg das Beispielziel nicht erreicht hat — ``None``, wenn er es tat (FD-146).

    E1 bis E3 zählen bis zum Beispielziel der Zeilenspezifikation (Konzept §4).
    Ohne Beispielziel oder ohne gelungenen Schritt *Übernehmen* endete der Weg
    vorher: an der Fläche eines Sprachdurchgangs, an einem grauen Hauptknopf,
    an einem Unterdialog. Was danach käme, ist nicht gemessen — aus dem Bild
    geschätzte Restschritte sind keine Messung, also nie „gut“.
    """
    if not str(_spec(protocol).get("example_goal") or "").strip():
        return "spec.example_goal (Zeile ohne Beispielziel)"
    applied = [
        step
        for step in steps
        if step.get("phase") == MAIN_PHASES[-1] and step.get("hit") and not step.get("finding")
    ]
    return None if applied else "Übernehmen (der Weg endet vor dem Beispielziel)"


def _e1(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    steps = _path(protocol)
    if steps is None:
        return _missing("E1", "steps")
    if (short := _short_of_goal(protocol, steps)) is not None:
        return _missing("E1", short)
    row = _row(protocol)
    at_feature = _selected_feature(steps, row)
    limit = MAX_CLICKS_AT_FEATURE if at_feature else MAX_CLICKS
    after = _after_selection(steps, row)
    inputs = {id(step) for step in _input_clicks(after)}
    counted = len([step for step in _clicks(after) if id(step) not in inputs])
    issues = []
    if counted > limit:
        where = "nach der Auswahl am Merkmal" if at_feature else "bis zum Ergebnis"
        issues.append(Issue(f"{counted} Klicks {where}, erlaubt {limit}", "mittel", "E1"))
    return _result(
        "E1", issues, f"{counted} Klicks", {"clicks": counted, "limit": limit}, judged=True
    )


def _e2(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    steps = _path(protocol)
    if steps is None:
        return _missing("E2", "steps")
    if (short := _short_of_goal(protocol, steps)) is not None:
        return _missing("E2", short)
    typed = sum(1 for step in steps if step.get("typed"))
    # Mehr als eine Eingabe an einer Zeile ist noch kein Fund: Die Schwelle
    # gilt für 90 % des Pakets (``function_report.package_values``). Ob eine
    # Vorgabe die zweite Eingabe erspart, urteilt Stufe B.
    return _result("E2", [], f"{typed} Eingaben", {"inputs": typed}, judged=typed > MAX_INPUTS)


def _e3(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    steps = _path(protocol)
    if steps is None:
        return _missing("E3", "steps")
    if (short := _short_of_goal(protocol, steps)) is not None:
        return _missing("E3", short)
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
    steps = _path(protocol)
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
    # „Kein Dialog verdeckt die Stelle“ ist nur gemessen, wo es eine Stelle gibt:
    # an Zeilen mit Auswahl muss der Prüfstand sie nachsehen.
    absent = ["spot"] if spot is None and _has_selection_relation(_row(protocol)) else []
    return _settled(
        "E4",
        issues,
        absent,
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
    # Drei Arten Sackgasse, drei Messungen: Fehlt eine, ist E7 nicht gemessen.
    absent = [
        name
        for name, value in (("matrix", matrix), ("empty_states", empty), ("messages", messages))
        if value is None
    ]
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
        if entry.get("kind") in ("sperrgrund", "grenzablehnung") and entry.get("way_out") is True:
            # Derselbe Vertrag wie V5: Der gemessene Ausweg am gesperrten
            # Bedienelement ist eine Handlungsmöglichkeit, kein Meldungsknopf.
            continue
        if not entry.get("actions"):
            issues.append(
                Issue(f"Meldung ohne Handlung: „{entry.get('text', '')}“", "schwer", "E7")
            )
    return _settled("E7", issues, absent, f"{len(issues)} Sackgassen", {"dead_ends": len(issues)})


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
    # Was die Szene selbst benennt — Projekt und Körper nach ihren Dateien —, hat
    # der Kunde geschrieben, nicht die Anwendung (Probelauf F-10: ``cube_clean``
    # traf das Muster für Bezeichner).
    names = sorted(
        (str(name) for name in (_map(protocol, "scene") or {}).get("names") or () if name),
        key=len,
        reverse=True,
    )
    issues: list[Issue] = []
    for entry in texts:
        text = str(entry.get("text") or "")
        for name in names:
            text = text.replace(name, " ")
        hits = _negative_hits(text, patterns)
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
    lacking = set()
    # Konzept §4: „Kurzhilfe und zugängliche Beschreibung“ — beide Sätze, und
    # jeder sagt mehr als der Titel.
    for entry in fields_:
        label = str(entry.get("label") or "")
        for key, title in (("tooltip", "Kurzhilfe"), ("description", "Beschreibung")):
            sentence = str(entry.get(key) or "").strip()
            if not sentence:
                issues.append(Issue(f"Feld „{label}“ ohne {title}", "leicht", "V3"))
                lacking.add(label)
                continue
            said = _word_set(sentence)
            shared = len(said & _word_set(label)) / len(said) if said else 1.0
            if shared > MAX_TITLE_OVERLAP:
                issues.append(
                    Issue(
                        f"Feld „{label}“: {title} wiederholt den Titel („{sentence}“)",
                        "leicht",
                        "V3",
                    )
                )
                lacking.add(label)
    with_sentence = len(fields_) - len(lacking)
    return _result(
        "V3",
        issues,
        f"{with_sentence} von {len(fields_)} Feldern mit eigenen Sätzen",
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
        kind = entry.get("kind")
        if kind in ("sperrgrund", "grenzablehnung"):
            # Ein Sperrgrund am grauen Bedienelement ist keine Meldung und braucht
            # keinen Knopf, er nennt aber den Ausweg (Entscheidung Koordinator);
            # die Grenzablehnung nennt die Grenze.
            if entry.get("way_out") is False:
                issues.append(
                    Issue(f"Sperrgrund ohne Ausweg: „{entry.get('text', '')}“", "mittel", "V5")
                )
            continue
        if kind == "befund":
            # Ein Befund trägt seine Handlungen im Prüfbericht; die prüfen die
            # Zeilen der Befundhandlungen (D8), nicht dieser Fehlfall.
            continue
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
    if not entries:
        return _missing("G1", "layout (primary)")
    issues = []
    absent = []
    for entry in entries:
        primary, accents = _number(entry.get("primary")), _number(entry.get("accents"))
        if primary is None or accents is None:
            absent.append(f"layout.primary an {entry.get('surface')}")
            continue
        if primary > MAX_PRIMARY:
            issues.append(
                Issue(f"{primary:g} Hauptknöpfe in {entry.get('surface')}", "leicht", "G1")
            )
        if accents > MAX_ACCENTS:
            issues.append(Issue(f"{accents:g} Akzente in {entry.get('surface')}", "leicht", "G1"))
    return _settled("G1", issues, absent, f"{len(entries)} Flächen", {"surfaces": len(entries)})


def _g2(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    entries = _layout(protocol, "spacing")
    if not entries:
        return _missing("G2", "layout (spacing)")
    issues = []
    absent = []
    groups: dict[tuple[str, str], set[float]] = {}
    for entry in entries:
        spacing = _number(entry.get("spacing"))
        margins = [_number(value) for value in entry.get("margins") or ()]
        items = _number(entry.get("items"))
        # Ein Abstand liegt erst zwischen zwei sichtbaren Elementen (Probelauf
        # F-6): Ein Layout mit einem zeigt nur seine Ränder.
        between = items is None or items >= 2
        if (between and spacing is None) or any(value is None for value in margins):
            absent.append(f"layout.spacing an {entry.get('surface')}")
            continue
        # Raster und Formular haben zwei Abstände, senkrecht und waagerecht
        # (Probelauf F-7: Qts ``spacing()`` sagte dort -1).
        horizontal = _number(entry.get("horizontal"))
        gaps = [value for value in (spacing, horizontal) if between and value is not None]
        values = [*gaps, *(value for value in margins if value is not None)]
        off = sorted({value for value in values if value % SPACE})
        if off:
            issues.append(
                Issue(
                    f"Abstand {off} in {entry.get('surface')} kein Vielfaches von {SPACE}",
                    "leicht",
                    "G2",
                )
            )
        if entry.get("group") and between and spacing is not None:
            key = (str(entry.get("surface")), str(entry.get("group")))
            groups.setdefault(key, set()).add(spacing)
    for (surface, group), found in sorted(groups.items()):
        if len(found) > 1:
            issues.append(
                Issue(f"Gruppe {group} in {surface} mit Abständen {sorted(found)}", "leicht", "G2")
            )
    return _settled("G2", issues, absent, f"{len(entries)} Layouts", {"layouts": len(entries)})


def _g3(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    entries = _layout(protocol, "form")
    if entries is None:
        return _missing("G3", "layout")
    issues = []
    absent = []
    for entry in entries:
        for name, edges in (
            ("Beschriftungen", entry.get("label_edges")),
            ("Felder", entry.get("field_edges")),
        ):
            read = [_number(edge) for edge in edges or ()]
            numbers = [number for number in read if number is not None]
            if len(numbers) != len(read):
                absent.append(f"layout.form an {entry.get('surface')}")
                continue
            if len(set(numbers)) > 1:
                issues.append(
                    Issue(
                        f"{name} in {entry.get('surface')} nicht bündig: {sorted(set(numbers))}",
                        "leicht",
                        "G3",
                    )
                )
        for value in entry.get("values") or ():
            if not isinstance(value, Mapping):
                absent.append(f"layout.form.values an {entry.get('surface')}")
            elif value.get("alignment") != "right" or not value.get("unit"):
                issues.append(
                    Issue(
                        f"Wert in {entry.get('surface')} nicht rechtsbündig mit Einheit",
                        "leicht",
                        "G3",
                    )
                )
    notes = [] if entries else ["kein Formular am Fall"]
    return _settled(
        "G3", issues, absent, f"{len(entries)} Formulare", {"forms": len(entries)}, notes=notes
    )


_STYLE_SIZE: Final = re.compile(r"font(?:-size)?\s*:", re.IGNORECASE)
#: Eine Schriftfarbe im Stylesheet: ``color:`` (nicht ``background-color:``) und ihr Wert.
_STYLE_TEXT_COLOUR: Final = re.compile(r"(?<![\w-])color\s*:\s*([^;}]+)", re.IGNORECASE)


@functools.cache
def design_text_colours() -> frozenset[str]:
    """Die Schriftfarben der Gestaltungswerte: beide Themen, die Rollen und die Feldschrift.

    Was ein Stylesheet aus ``THEMES``, ``palette.ROLES*`` oder ``readable_on``
    setzt, ist eine Gestaltungsfarbe, keine fest gesetzte (Probelauf F-5: die
    Warnmarken, die Legende der Analyse, die Auswahlquittung).
    """
    from app.ui import palette
    from app.ui.theme import THEMES

    found: set[str] = set()
    for colours in THEMES.values():
        found.update(str(value) for value in colours.values() if str(value).startswith("#"))
    for table in (palette.ROLES, palette.ROLES_ON_LIGHT, palette.ROLES_ON_DARK):
        found.update(table.values())
    found.update((palette.ON_LIGHT_FIELD, palette.ON_DARK_FIELD))
    return frozenset(colour.lower() for colour in found)


def _foreign_text_colours(sheet: str) -> list[str]:
    """Schriftfarben eines Stylesheets, die keine Gestaltungsfarbe sind."""
    found = []
    for match in _STYLE_TEXT_COLOUR.finditer(sheet):
        value = match.group(1).strip().lower()
        if value.startswith("#") and value in design_text_colours():
            continue
        if value.startswith(("#", "rgb")):
            found.append(value)
    return found


def _effective_level(entry: Mapping[str, Any]) -> str | None:
    """Die Stufe, die die wirksame Schrift trägt, aus Punkten und Gewicht.

    ``type_scale`` der Grundgröße (``style.apply_style``) nennt je Stufe Größe
    und Gewicht; eine Schrift ohne gesetzte Eigenschaft ist die Grundschrift
    und damit ``body`` (Probelauf F-4). ``None``, wenn sie keiner Stufe
    entspricht; ``""`` ohne Messung der Schrift. Die belegte Primärrolle darf
    die Grundschrift halbfett betonen, aber weder Größe noch Familie ändern.
    """
    from PySide6.QtGui import QFont

    from app.ui.style import type_scale

    points, weight, base = (_number(entry.get(key)) for key in ("points", "weight", "base_points"))
    if points is None or weight is None or base is None or points <= 0 or base <= 0:
        return ""
    family, base_family = entry.get("family"), entry.get("base_family")
    if family is not None or base_family is not None:
        if (
            not isinstance(family, str)
            or not family
            or not isinstance(base_family, str)
            or not base_family
        ):
            return ""
        if family != base_family:
            return None
    sizes = type_scale(int(base))
    for level, (size, bold) in sizes.items():
        if abs(points - size) < 0.05 and int(weight) == bold:
            return level
    if entry.get("primary") is True:
        if not family or not base_family:
            return ""
        if abs(points - sizes["body"][0]) < 0.05 and int(weight) == QFont.Weight.DemiBold.value:
            return "body"
    return None


def _g4(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    fonts = _list(protocol, "fonts")
    if not fonts:
        # Eine Fläche ohne aufgenommene Schrift heißt: nichts gemessen
        # (wie ``contrast: []`` bei G6).
        return _missing("G4", "fonts" if fonts is None else "fonts (keine Schriften)")
    issues = []
    absent = []
    for entry in fonts:
        widget = entry.get("widget")
        if "points" in entry:
            level = _effective_level(entry)
            if level == "":
                absent.append(f"fonts.points/Familie an {widget}")
            elif level is None:
                issues.append(
                    Issue(
                        f"Schrift {entry.get('points')} pt, Gewicht {entry.get('weight')} an "
                        f"{widget} ist keine Stufe aus {list(LEVELS)}",
                        "leicht",
                        "G4",
                    )
                )
        elif entry.get("level") not in LEVELS:
            # Ein Protokoll ohne wirksame Schrift: nur die gesetzte Stufe.
            issues.append(Issue(f"Schrift ohne Stufe an {widget}", "leicht", "G4"))
        sheet = str(entry.get("stylesheet") or "")
        foreign = _foreign_text_colours(sheet)
        if _STYLE_SIZE.search(sheet) or foreign:
            issues.append(
                Issue(
                    f"Größe oder Farbe im Stylesheet an {widget}: {sheet}",
                    "leicht",
                    "G4",
                )
            )
    return _settled("G4", issues, absent, f"{len(fonts)} Schriften", {"fonts": len(fonts)})


#: Die Zustände, die der Prüfstand an jedem Widget aufnimmt
#: (``function_capture.state_images``); die übrigen nur, wo es sie gibt.
_TAKEN_STATES: Final = ("rest", "hover", "focus", "pressed")


def _g5(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    images = _list(protocol, "state_images")
    if images is None:
        return _missing("G5", "state_images")
    issues = []
    absent = []
    for entry in images:
        states = dict(entry.get("states") or {})
        unseen = sorted(state for state, digest in states.items() if not digest)
        if unseen:
            absent.append(f"state_images {entry.get('widget')}: {', '.join(unseen)}")
        seen: dict[str, str] = {}
        for state, digest in sorted(states.items()):
            if not digest:
                continue
            if digest in seen:
                issues.append(
                    Issue(
                        f"{entry.get('widget')}: {seen[digest]} und {state} sehen gleich aus",
                        "leicht",
                        "G5",
                    )
                )
            seen.setdefault(digest, state)
        missing = [state for state in _TAKEN_STATES if state not in states]
        if missing:
            # Nicht aufgenommen ist nicht gemessen, kein Fund.
            absent.append(f"state_images {entry.get('widget')}: {', '.join(missing)}")
    return _settled(
        "G5", issues, absent, f"{len(images)} Widgets", {"widgets": len(images)}, judged=True
    )


_COLOUR: Final = re.compile(r"#[0-9a-fA-F]{6}")


def _g6(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    pairs = _list(protocol, "contrast")
    if pairs is None:
        return _missing("G6", "contrast")
    issues = []
    absent = []
    lowest = math.inf
    for entry in pairs:
        colours = (entry.get("foreground"), entry.get("background"))
        if not all(isinstance(c, str) and _COLOUR.fullmatch(c) for c in colours):
            absent.append(f"contrast an {entry.get('widget')}")
            continue
        ratio = contrast_ratio(str(colours[0]), str(colours[1]))
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
    if not pairs:
        absent.append("contrast (keine Paare)")
    summary = "keine Paare" if math.isinf(lowest) else f"kleinster Kontrast {lowest:.2f}"
    return _settled(
        "G6",
        issues,
        absent,
        summary,
        {"pairs": len(pairs), "lowest": None if math.isinf(lowest) else round(lowest, 3)},
    )


def _g7(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    icons = _list(protocol, "icons")
    if icons is None:
        return _missing("G7", "icons")
    issues = []
    notes = []
    for entry in icons:
        if entry.get("text"):
            continue
        name = entry.get("widget")
        # ``own`` ``None`` heißt: Die Herkunft ließ sich am Bild nicht belegen —
        # ein Vermerk für Stufe B, kein Fund (Probelauf F-12). Ein Fund ist ein
        # Knopf ohne Symbol oder mit einem fremden.
        if not entry.get("icon") or entry.get("own") is False:
            issues.append(
                Issue(f"Symbolknopf {name} ohne Symbol aus dem eigenen Satz", "leicht", "G7")
            )
        elif entry.get("own") is None:
            notes.append(f"Herkunft des Symbols an {name} nicht belegt")
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
    return _result("G7", issues, f"{len(icons)} Symbole", {"icons": len(icons)}, notes=notes)


def _g8(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    animations = _list(protocol, "animations")
    if animations is None:
        return _missing("G8", "animations")
    variant = _map(protocol, "variant") or {}
    # Abgeschaltet ist die Bewegung nur bei ``False``; ``null`` heißt nicht
    # gemessen, und dann gilt der gewöhnliche Lauf mit Bewegung.
    motion_off = variant.get("motion") is False
    issues = []
    absent = []
    for entry in animations:
        duration = _number(entry.get("duration_ms"))
        if duration is None:
            absent.append(f"animations an {entry.get('widget')}")
            continue
        if motion_off and duration > 0:
            issues.append(
                Issue(
                    f"Bewegung trotz abgeschalteter Bewegung an {entry.get('widget')}",
                    "leicht",
                    "G8",
                )
            )
        elif not motion_off and not ACCENT_MS <= duration <= MEDIUM_MS:
            issues.append(
                Issue(
                    f"Übergang {duration:g} ms an {entry.get('widget')}, "
                    f"erlaubt {ACCENT_MS} bis {MEDIUM_MS}",
                    "leicht",
                    "G8",
                )
            )
    return _settled(
        "G8", issues, absent, f"{len(animations)} Übergänge", {"animations": len(animations)}
    )


def _g9(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    return Outcome("G9", "B", "stufe_b", "Gestaltungsurteil")


def _reference_factor(protocol: Mapping[str, Any]) -> float | None:
    """Der Referenzfaktor des Laufs (:data:`REFERENCE_FACTOR_AT`), ``None`` ohne Messung."""
    block, key = REFERENCE_FACTOR_AT
    return _number((_map(protocol, block) or {}).get(key))


def _z1(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    frames = _map(protocol, "frames")
    # Ohne Zug an der Zeile gilt Z1 nicht — ``frames`` kann dann allein den
    # Referenzfaktor tragen. Nennt die Spezifikation Z1, fehlt die Messung.
    if frames is None or "raw_drag_ms" not in frames:
        return (
            None
            if "Z1" not in (_spec(protocol).get("criteria") or ())
            else _missing("Z1", "frames.raw_drag_ms")
        )
    measured = [_number(value) for value in frames.get("raw_drag_ms") or ()]
    delays = [value for value in measured if value is not None]
    factor = _reference_factor(protocol)
    # Bleibt nach einem Ziehereignis das Bild aus, ist das der längste Verzug —
    # außer am Ende der Aufnahme, wo danach nichts mehr gemalt werden musste.
    trailing = len(measured) - len(list(dropwhile(lambda v: v is None, reversed(measured))))
    stalled = [
        index + 1
        for index, value in enumerate(measured[: len(measured) - trailing])
        if value is None
    ]
    issues = [Issue(f"Ziehereignis {index} ohne Bild danach", "mittel", "Z1") for index in stalled]
    absent = [".".join(REFERENCE_FACTOR_AT)] if factor is None else []
    if not delays and not stalled:
        absent.insert(0, "frames.raw_drag_ms")
    notes = [f"{trailing} Ereignisse am Ende der Aufnahme ohne Bild danach"] if trailing else []
    # Roh gemessen, einmal auf die Referenz umgerechnet.
    worst = max(delays) * factor if delays and factor is not None else None
    if worst is not None and worst > MAX_DRAG_MS:
        issues.append(
            Issue(
                f"{worst:.0f} ms bis zum nächsten Bild beim Ziehen, erlaubt {MAX_DRAG_MS}",
                "mittel",
                "Z1",
            )
        )
    return _settled(
        "Z1",
        issues,
        absent,
        "ohne Umrechnung" if worst is None else f"{worst:.0f} ms",
        {"worst_ms": None if worst is None else round(worst, 1), "factor": factor},
        notes=notes,
    )


def _z2(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    # ``allowed`` setzt die Wache: die Ausnahmen aus Konzept Z2, die eigene
    # Fläche der Zeile und die Fehlermeldung mit Handlungsvorschlag nach Regel 17
    # (``function_capture.error_proposal``, Durchsicht welle4 D-M2).
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
    steps = _path(protocol)
    if steps is None:
        return _missing("Z3", "steps")
    way = _way_clicks(steps, row)
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


def _size_of(value: Any) -> tuple[int, int] | None:
    """Eine Fenstergröße ``[b, h]`` aus dem Protokoll, ``None`` ohne Messung."""
    numbers = [_number(item) for item in value] if isinstance(value, list) else []
    if len(numbers) != 2 or numbers[0] is None or numbers[1] is None:
        return None
    return int(numbers[0]), int(numbers[1])


def judge_sizes(protocols: Iterable[Mapping[str, Any]], *, complete: bool) -> Outcome | None:
    """Z6 über die Rollleisten und Symbole eines Falls oder aller Fälle einer Zeile.

    Der Prüfstand fährt je Fenstergröße einen Fall. Eine Größe gilt als
    gemessen, wenn ein Fall in ihr lief (``variant.window_size``) und seine
    Rollleisten aufnahm — auch als leere Liste — oder ein Eintrag sie nennt.
    Verlangt ist die kleinste Fensterfläche (``SMALLEST_WINDOW``); größere
    Flächen zählen mit, eine kleinere ist kein Fall, und eine Rollleiste dort
    kein Fund (Festlegung Robert: 1920 x 1080 logisch, drunter nie). So urteilt
    ``function_report.merge_cases`` einmal je Zeile (``complete``); ein
    einzelner Fall muss in ihr gelaufen sein. ``None``, wenn kein Fall etwas
    aufnahm.
    """
    sizes = {SMALLEST_WINDOW}
    issues = []
    run: set[tuple[int, int]] = set()
    surfaces = 0
    taken = False
    for protocol in protocols:
        bars, icons = _list(protocol, "scrollbars"), _list(protocol, "icons")
        own = _size_of((_map(protocol, "variant") or {}).get("window_size"))
        if bars is not None:
            taken = True
            surfaces += len(bars)
            if own is not None:
                run.add(own)
        for entry in bars or []:
            size = _size_of(entry.get("window_size")) or own
            if size is None:
                continue
            run.add(size)
            if (
                size[0] >= SMALLEST_WINDOW[0]
                and size[1] >= SMALLEST_WINDOW[1]
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
        if icons is not None:
            taken = True
        for entry in icons or []:
            scale, ratio = _number(entry.get("scale")), _number(entry.get("pixmap_ratio"))
            # Unscharf ist nur ein Bild mit weniger Punkten als der Schirm: Die
            # Symbole rastern absichtlich doppelt (``icons.OVERSAMPLING``), und
            # ein Bild mit mehr Punkten ist schärfer (Probelauf F-11).
            if (
                scale is not None
                and ratio is not None
                and ratio < scale
                and not _close(scale, ratio)
            ):
                issues.append(
                    Issue(
                        f"Symbol {entry.get('widget')} bei {scale * 100:.0f} % "
                        f"mit Pixmap {ratio:g}",
                        "leicht",
                        "Z6",
                    )
                )
    if not taken:
        return None
    missing = sorted(sizes - run)
    if complete:
        absent = [f"scrollbars bei {width} x {height}" for width, height in missing]
    else:
        absent = (
            []
            if run & sizes
            else [" oder ".join(f"scrollbars bei {w} x {h}" for w, h in sorted(sizes))]
        )
    return _settled("Z6", issues, absent, f"{surfaces} Flächen", {"surfaces": surfaces})


def _z6(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    return judge_sizes([protocol], complete=False) or _missing("Z6", "scrollbars", "icons")


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
    # Eine Art ohne zugewandte Stelle oder ein gescheitertes Überfahren ist nicht
    # gemessen, kein Fund (Probelauf F-28) — der Vermerk sagt, welche.
    missed = (_map(protocol, "unmeasured") or {}).get("hover_labels")
    notes = [f"nicht gemessen: {missed}"] if missed else []
    return _result(
        "I1", issues, f"{len(labels)} Arten", {"kinds": len(labels)}, judged=True, notes=notes
    )


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
    row = _row(protocol)
    # I3 ist ein Anteil an einer vorab festgelegten Liste der häufigsten
    # Kundenziele (Konzept §4): gemessen nur an deren Zeilen, und auch dort
    # kein Fund je Zeile — die Schwelle gilt dem Paket (``package_values``).
    if str(row.get("target") or "") not in context.common_goal_targets:
        return None
    steps = _path(protocol)
    if steps is None:
        return _missing("I3", "steps")
    way = _way_clicks(steps, row)
    notes = [f"Ziel erst nach {len(way)} Wegklicks da — zählt im Paketanteil"] if way else []
    return _result(
        "I3",
        [],
        f"{len(way)} Wegklicks",
        {"way_clicks": len(way)},
        judged=bool(way),
        notes=notes,
    )


def _i4(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    # Zählt je Paket ohne Fenster (``function_report.solution_count``).
    return None


def _i5(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    if "I5" not in (_spec(protocol).get("criteria") or ()):
        return None
    steps = _path(protocol)
    if steps is None:
        return _missing("I5", "steps")
    issues = []
    clicks = len(_clicks(steps))
    # Kein Weg zum Ziel steht am Schritt, an dem der Prüfstand aufgab.
    if any(step.get("finding") == NOT_FOUND for step in steps):
        issues.append(Issue("Vorher und nachher nicht erreichbar", "mittel", "I5"))
    elif clicks > 1:
        issues.append(Issue(f"Vorher und nachher erst nach {clicks} Klicks", "mittel", "I5"))
    return _result("I5", issues, f"{clicks} Klicks", {"clicks": clicks}, judged=True)


def _bench_findings(protocol: Mapping[str, Any], kind: str) -> list[Mapping[str, Any]]:
    """Was der Prüfstand unterwegs fand (``findings``), von einer Art."""
    return [
        found
        for found in _list(protocol, "findings") or ()
        if isinstance(found, Mapping) and found.get("kind") == kind
    ]


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
        # ``rank = null`` heißt: Die Probe fand das Ziel unter keinem Treffer.
        rank = _number(entry.get("rank"))
        if rank is None or rank > MAX_RANK:
            shown = "nicht gefunden" if rank is None else f"Rang {rank:g}"
            issues.append(Issue(f"Suche „{word}“: {shown}", severity, criterion))
    return issues


def _i6(protocol: Mapping[str, Any], context: Context) -> Outcome | None:
    probes = _probes(protocol, question=True)
    if not probes:
        return None
    issues = _rank_issues(probes, "Vorschlag", "I6")
    return _result("I6", issues, f"{len(probes)} Fragen", {"questions": len(probes)})


JudgeCriterion = Callable[[Mapping[str, Any], Context], Outcome | None]


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

#: Die 19 Prüfpunkte (Konzept §4).


def compare_themes(light: Mapping[str, Any], dark: Mapping[str, Any]) -> list[Issue]:
    """Z6: hell und dunkel zeigen dieselben Flächen mit derselben Zahl Akzente."""

    def accents(protocol: Mapping[str, Any]) -> dict[str, float | None]:
        return {
            str(entry.get("surface")): _number(entry.get("accents"))
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
