"""Die Prüfpunkte des Funktionsdurchgangs und das Urteil über einen Fall (RM-737, D0-U).

Liest das Messprotokoll eines Falls (``cases/<nr>/function.json``, Schema in
:data:`~tools.function_checks.PROTOCOL_SCHEMA`) und gibt je Prüfpunkt und je
geltendem Kriterium ein :class:`~tools.function_checks.Outcome` (Konzept §4,
:func:`judge_case`). Die Kriterien urteilt ``tools/function_judges.py``; ein
Prüfpunkt fasst seine Kriterien mit :func:`_combine` zusammen und misst, was
ihm selbst gehört. :func:`judge_licence` und :func:`judge_design` urteilen
auch einmal je Zeile über alle Fälle (``function_report.merge_cases``).

Eigenes Modul, damit keine Datei des Pakets die Größengrenze der Codestruktur
(2 000 Zeilen, W1) reißt.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from itertools import pairwise
from typing import Any, Final

from tools.function_checks import (
    BAR_AFTER_S,
    CHECKPOINTS,
    COVERED,
    CRITERIA,
    DESIGN_PARTS,
    FAULT_PHASE,
    FEEDBACK_AFTER_S,
    LICENCE_UNLOCKED,
    MAIN_GAP_MS,
    MAIN_PHASES,
    MATRIX_UNREACHABLE,
    NO_DRAFT,
    NO_RESPONSE,
    NOT_FOUND,
    REVISE_WAYS,
    SELECTION_STAGES,
    STEP_WITHOUT_VALUES,
    SWITCH_ABSENT,
    SWITCH_PHASES,
    WITHOUT_DIALOG,
    CaseOutcome,
    Context,
    Issue,
    Outcome,
    validate_protocol,
)
from tools.function_judges import (
    _MM_VALUE,
    CRITERION_JUDGES,
    _bench_findings,
    _clicks,
    _close,
    _list,
    _map,
    _missing,
    _number,
    _path,
    _print_without_view,
    _probes,
    _rank_issues,
    _reference_factor,
    _result,
    _row,
    _settled,
    _spec,
)
from tools.function_list import LICENCE_STATES, NOT_APPLICABLE_REASONS, licence_states

#: Wie das Ziel in einem Lizenzlauf dastand (``function_bench.phase_licence``):
#: offen, grau oder gar nicht — dieselben Wörter wie in der Matrix.
LICENCE_RUN_STATES: Final = ("angeboten", "grau", "fehlt")
LICENCE_MISSING: Final = LICENCE_RUN_STATES[2]

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
    """Ein Prüfpunkt aus seinen Kriterien: Fund vor nicht prüfbar vor nicht gelaufen vor Urteil.

    Ein Kriterium, das an der Zeile nicht gilt, kommt als ``None`` und zählt
    nicht. Ein geltendes, aber nicht gemessenes lässt den Prüfpunkt höchstens
    „nicht gelaufen“ werden — nie „Stufe B“, die ein Urteil „gut“ schließen
    könnte. Was an einer Zeile nicht gilt, steht als *entfällt* mit Grund in der
    Spezifikation.
    """
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
    unmeasured = [part for part in present if part.verdict == "nicht_gelaufen"]
    if unmeasured or (not measured and not present):
        reasons = "; ".join(f"{part.subject} {part.reason}" for part in unmeasured)
        return Outcome(
            subject,
            "A",
            "nicht_gelaufen",
            "nicht gemessen",
            data,
            reason=reasons or "keine Messung",
        )
    if judged or any(part.verdict == "stufe_b" for part in present):
        return Outcome(subject, "B", "stufe_b", summary, data)
    return Outcome(subject, "A", "erfuellt", summary, data)


def _point_1(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    place = _map(protocol, "place")
    issues = []
    for found in _bench_findings(protocol, NOT_FOUND):
        if found.get("phase") in MAIN_PHASES:
            # Auf dem Hauptweg heißt „kein Weg“: Der Kunde findet die Funktion nicht.
            issues.append(
                Issue(f"nicht auffindbar: {found.get('target')} ({found.get('detail')})", "schwer")
            )
    if place is None:
        # Ein Fall, der nur bis zur Fläche geht (Zoll, Skalierung, Thema), misst
        # keinen Ort — sein „nicht auffindbar“ auf dem Weg dorthin bleibt ein
        # Fund (Probelauf F-37), nur der Ort fehlt.
        if issues:
            return _settled(1, issues, ["place"], "nicht auffindbar", {"where": None})
        return _missing(1, "place")
    if place.get("error"):
        issues.insert(0, Issue(f"nicht auffindbar ({place.get('error')})", "schwer"))
    probes = _probes(protocol, question=False)
    issues.extend(_rank_issues(probes, "mittel", None))
    # Suchproben sind Pflicht für Prüfpunkt 1 (Zeilenspezifikation): ohne sie
    # ist die Hälfte von „auffindbar“ nicht gemessen.
    absent = [] if probes else ["search (Suchproben)"]
    where = place.get("where", "?")
    return _settled(
        1,
        issues,
        absent,
        f"{where}, {len(probes)} Suchproben",
        {
            "where": where,
            "path": place.get("path"),
            "probes": {w: e.get("rank") for w, e in probes.items()},
        },
        judged=True,
    )


def _point_2(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    steps = _path(protocol)
    if steps is None:
        return _missing(2, "steps")
    parts = [criteria.get(key) for key in ("E1", "E3", "E4", "E5", "E6", "E7")]
    clicks = _clicks(steps)
    # „Verdeckt“ ist ein Fund in jeder Phase: An der Stelle, die der Kunde
    # anklicken soll, liegt etwas anderes (Konzept §5). Ein Ziel ohne Weg
    # außerhalb des Hauptwegs gehört dem Prüfpunkt seiner Phase und steht hier
    # als Vermerk.
    own = [
        Issue(f"verdeckt in Phase {found.get('phase')}: {found.get('detail')}", "mittel")
        for found in _bench_findings(protocol, COVERED)
    ]
    elsewhere = [
        f"kein Weg zu {found.get('target')} in Phase {found.get('phase')}"
        for found in _bench_findings(protocol, NOT_FOUND)
        if found.get("phase") not in MAIN_PHASES
    ]
    outcome = _combine(
        2,
        parts,
        own=own,
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
    return replace(outcome, notes=(*outcome.notes, *elsewhere))


def _point_3(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    preview = _map(protocol, "preview")
    if preview is None:
        return _missing(3, "preview")
    variant = _map(protocol, "variant") or {}
    # Grob entscheidet die Anwendung je Körper (``Session``); der Prüfstand sieht
    # es am Fall. Die Dreieckssumme der Szene wäre eine zweite, falsche Regel.
    coarse = preview.get("coarse")
    if not isinstance(coarse, bool):
        return _missing(3, "preview.coarse")
    if coarse:
        banner = preview.get("banner_text")
        if banner is None:
            return _missing(3, "preview.banner_text")
        note = context.coarse_note(str(variant.get("language") or "de"))
        issues = (
            []
            if note in str(banner)
            else [Issue("grobe Vorschau ohne ihren Satz im Band", "mittel")]
        )
        return _result(3, issues, "grobe Vorschau", {"coarse": True})
    states = _map(protocol, "states") or {}
    applied, before = states.get("applied"), states.get("before")
    result = _map(protocol, "result")
    if not isinstance(applied, Mapping) or not isinstance(before, Mapping) or result is None:
        return _missing(3, "states.applied", "states.before", "result")
    issues = []
    absent = []
    kept = dict(applied.get("bodies") or {})
    changed = {
        key: digest
        for key, digest in kept.items()
        if (before.get("bodies") or {}).get(key) != digest
    }
    shown = preview.get("bodies")
    if not isinstance(shown, Mapping):
        absent.append("preview.bodies")
    else:
        differ = sorted(key for key, digest in shown.items() if kept.get(key) != digest)
        if differ:
            issues.append(Issue(f"Vorschau zeigt andere Körper als übernommen: {differ}", "schwer"))
        unshown = sorted(set(changed) - set(shown))
        if unshown:
            issues.append(Issue(f"Vorschau zeigt geänderte Körper nicht: {unshown}", "schwer"))
    metrics = dict(result.get("metrics") or {})
    for key, title in (("volume", "Volumen"), ("extent", "Außenmaß")):
        if preview.get(key) is None or metrics.get(key) is None:
            absent.append(f"{key} in Vorschau und Ergebnis")
        elif not _close(preview[key], metrics[key]):
            issues.append(
                Issue(f"{title} der Vorschau {preview[key]} ≠ Ergebnis {metrics[key]}", "schwer")
            )
    return _settled(
        3,
        issues,
        absent,
        f"{len(changed)} geänderte Körper verglichen",
        {"bodies": len(changed), "coarse": False},
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
    # Eine Erwartung ohne Herkunft oder ohne Wert ist ein Fehler der
    # Spezifikation: nicht prüfbar, bis sie berichtigt ist.
    unusable = sorted(
        key
        for key, entry in expectation.items()
        if not isinstance(entry, Mapping)
        or not str(entry.get("origin") or "").strip()
        or _number(entry.get("value")) is None
    )
    if unusable:
        return Outcome(
            4,
            "A",
            "nicht_pruefbar",
            "Erwartung ohne Herkunft oder Wert",
            reason=f"ohne Herkunft oder Wert: {unusable}",
        )
    metrics = dict(result.get("metrics") or {})
    issues = []
    absent = []
    for key, entry in sorted(expectation.items()):
        measured = _number(metrics.get(key))
        if measured is None:
            absent.append(f"result.metrics.{key}")
            continue
        value = float(entry["value"])
        tolerance = _number(entry.get("tolerance")) or 0.0
        if abs(measured - value) > tolerance:
            issues.append(Issue(f"{key} {measured:g} statt {value:g} ± {tolerance:g}", "schwer"))
    cli = _map(protocol, "cli")
    equal = cli.get("print_equal") if cli is not None else None
    if not isinstance(equal, bool):
        # Fehlt der Vergleich mit der Kommandozeile, bleibt ein Fund an den
        # Kennzahlen trotzdem ein Fund (Vermerk statt Verlust).
        absent.append("cli.print_equal")
    elif not equal:
        issues.append(
            Issue(
                "Kommandozeile nicht druckgleich "
                f"(größte Abweichung {(cli or {}).get('max_deviation_mm')} mm)",
                "schwer",
            )
        )
    said = "nicht verglichen" if equal is None else "druckgleich" if equal else "abweichend"
    return _settled(
        4,
        issues,
        absent,
        f"{len(expectation)} Kennzahlen, Kommandozeile {said}",
        {"metrics": metrics, "cli_deviation_mm": (cli or {}).get("max_deviation_mm")},
    )


def _point_5(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    states = _map(protocol, "states")
    # Escape verwirft den Entwurf (Konzept §4, Prüfpunkt 5); ohne ihn ist der
    # Rückweg nur zur Hälfte gemessen. Hat die Zeile weder Entwurf noch Dialog —
    # eine Befundhandlung wie *Auf das Bett setzen* —, gibt es nichts zu
    # verwerfen, und der Rückweg ist Rückgängig und Wiederholen (FD-128).
    unmeasured = _map(protocol, "unmeasured") or {}
    nothing_to_discard = (
        unmeasured.get("states.escape") == NO_DRAFT
        and unmeasured.get("focus_return") == WITHOUT_DIALOG
    )
    required = ("before", "applied", "undo", "redo") + (() if nothing_to_discard else ("escape",))
    if states is None or not all(isinstance(states.get(key), Mapping) for key in required):
        return _missing(5, *(f"states.{key}" for key in required))
    before, applied = states["before"], states["applied"]
    if _print_without_view(before) == _print_without_view(applied):
        # Hat das Übernehmen nichts geändert, gibt es nichts zurückzunehmen:
        # Rückgängig, Wiederholen und Escape stünden alle „gleich“, und der
        # Rückweg hieße erfüllt, ohne gelaufen zu sein (Probelauf F-36).
        return Outcome(
            5,
            "A",
            "nicht_gelaufen",
            "nicht gemessen",
            reason="Übernehmen änderte den Stand nicht — kein Rückweg zu messen",
        )
    issues = []
    notes = []
    checks = [("undo", before, "Rückgängig"), ("redo", applied, "Wiederholen")]
    if nothing_to_discard:
        notes.append(f"Escape und Abbrechen entfallen: {NO_DRAFT}, {WITHOUT_DIALOG}")
    else:
        checks.append(("escape", before, "Escape"))
        if isinstance(states.get("cancelled"), Mapping):
            checks.append(("cancelled", before, "Abbrechen"))
        else:
            notes.append("Abbrechen im Dialog nicht gemessen (Zeile ohne Dialog?)")
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


#: Wie spät eine Rückmeldung nach ihrer Schwelle kommen darf: eine Lücke im
#: Hauptfaden. Ein Zeitgeber, der bei 0,2 s feuern soll, kommt höchstens so spät,
#: wie der Hauptfaden blockiert sein darf (Prüfpunkt 6).
_LATE_S: Final = MAIN_GAP_MS / 1000


def _point_6(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    timing = _map(protocol, "timing")
    # Eine Wartefrist ohne fertiges Ergebnis ist ein Fund, auch wenn die Zeiten
    # dann fehlen (Entscheidung Koordinator, 12.10.: „keine Rückmeldung“).
    silent = [
        Issue(
            f"keine Rückmeldung in Phase {found.get('phase')}: {found.get('target')} "
            f"({found.get('detail')})",
            "schwer",
        )
        for found in _bench_findings(protocol, NO_RESPONSE)
    ]
    if timing is None:
        if silent:
            return _settled(6, silent, ["timing"], "keine Rückmeldung", {})
        return _missing(6, "timing")
    issues = list(silent)
    notes = []
    gap, total = _number(timing.get("main_gap_ms")), _number(timing.get("total_s"))
    absent = [
        f"timing.{key}"
        for key, value in (("main_gap_ms", gap), ("total_s", total))
        if value is None
    ]
    if gap is not None and gap > MAIN_GAP_MS:
        issues.append(
            Issue(f"Hauptfaden {gap:.0f} ms ohne Ereignis, erlaubt {MAIN_GAP_MS}", "mittel")
        )
    # Ab 0,2 s Zeiger, ab 2 s Balken und *Abbrechen* — und zwar dann, nicht
    # irgendwann (Konzept §4, Prüfpunkt 6; Schwellen aus ``app.ui.loading``).
    due: list[tuple[str, str, float]] = []
    if total is not None and total >= FEEDBACK_AFTER_S:
        due.append(("first_feedback_s", "Zeiger oder Statuszeile", FEEDBACK_AFTER_S))
    if total is not None and total >= BAR_AFTER_S:
        due.append(("progress_shown_s", "Fortschrittsbalken", BAR_AFTER_S))
        due.append(("cancel_shown_s", "sichtbares Abbrechen", BAR_AFTER_S))
    for key, title, after in due:
        shown = _number(timing.get(key))
        if shown is None:
            issues.append(Issue(f"{total:.1f} s ohne {title}", "mittel"))
        elif shown > after + _LATE_S:
            issues.append(
                Issue(f"{title} erst nach {shown:.2f} s, fällig ab {after:g} s", "mittel")
            )
    budget = _number(timing.get("budget_s"))
    factor = _reference_factor(protocol)
    # Das Budget gilt auf der Referenzmaschine (§31): die rohe Dauer einmal
    # umgerechnet, wie bei Z1. Ohne Faktor roh, und der Vermerk sagt es.
    reference = None if total is None or factor is None else total * factor
    if budget is None:
        notes.append("kein Budget")
    elif reference is not None and reference > budget:
        # Eine Überschreitung ist ein Verdacht, den ``window_bench.py`` oder
        # die Leistungstests bestätigen (Konzept §4, Prüfpunkt 6).
        notes.append(
            f"Verdacht: {reference:.2f} s auf der Referenz über dem Budget von {budget:.2f} s"
        )
    elif reference is None and total is not None and total > budget:
        notes.append(
            f"Verdacht: {total:.2f} s über dem Budget von {budget:.2f} s, roh verglichen "
            "(kein Referenzfaktor)"
        )
    return _settled(
        6,
        issues,
        absent,
        f"{total or 0:.2f} s, Lücke {gap or 0:.0f} ms",
        {
            "total_s": total,
            "main_gap_ms": gap,
            "budget_s": budget,
            "reference_factor": factor,
            "reference_s": None if reference is None else round(reference, 3),
        },
        notes=notes,
    )


def _point_7(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    fault = _spec(protocol).get("fault_case")
    if not fault:
        return _missing(7, "spec.fault_case")
    # Kam der Prüfstand nicht bis zum Fehlfall — ein Fund oder Fehler in seiner
    # Phase —, ist der Fehlerweg nicht gemessen; „keine Meldung“ hieße sonst,
    # die Anwendung schwiege (Probelauf F-24, F-34).
    stopped = [
        f"{found.get('kind')}: {found.get('target')}"
        for found in _list(protocol, "findings") or ()
        if isinstance(found, Mapping) and found.get("phase") == FAULT_PHASE
    ]
    stopped += [
        str(error).partition("\n")[0]
        for error in _list(protocol, "errors") or ()
        if str(error).startswith(f"{FAULT_PHASE}:")
    ]
    if stopped:
        return Outcome(
            7,
            "A",
            "nicht_gelaufen",
            "Fehlfall nicht hergestellt",
            reason="der Fehlfall kam nicht zustande: " + "; ".join(stopped),
        )
    messages = _list(protocol, "messages")
    if messages is None:
        return _missing(7, "messages")
    # Gezählt wird, was der Fehlfall meldete — die Meldungen der Fläche davor
    # tragen keine Phase (``FunctionFlow.phase_fault``).
    entries = [m for m in messages if isinstance(m, Mapping)]
    if any("phase" in m for m in entries):
        entries = [m for m in entries if m.get("phase") == FAULT_PHASE]
    own: list[Issue] = []
    notes: list[str] = []
    expected = str(fault.get("expected") or "")
    kinds = sorted({str(m["kind"]) for m in entries if m.get("kind")})
    if not entries:
        own.append(Issue("der Fehlfall ergab keine Meldung", "mittel"))
    elif expected and kinds and expected not in kinds:
        # Die Absage ist eine andere als die, die die Spezifikation erwartet
        # (Entscheidung Koordinator): ein Sperrgrund statt einer Grenzablehnung
        # ist ein anderer Weg für den Kunden.
        own.append(Issue(f"erwartet {expected}, gemessen {', '.join(kinds)}", "mittel"))
    elif expected and not kinds:
        notes.append(f"Art der Absage nicht gemessen, erwartet {expected}")
    outcome = _combine(
        7,
        [criteria.get("V5")],
        own=own,
        measured=True,
        judged=True,
        summary=f"{len(entries)} Meldungen",
    )
    return replace(outcome, notes=(*outcome.notes, *notes)) if notes else outcome


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
            # Eine umbrochene Listenzeile misst ihre Höhe (FD-110).
            axis = " Höhe" if entry.get("axis") == "hoehe" else ""
            issues.append(
                Issue(f"„{entry.get('text')}“ braucht {need} px{axis}, hat {width} px", "leicht")
            )
        if variant.get("unit") not in {None, "mm"} and _MM_VALUE.search(
            str(entry.get("text") or "")
        ):
            issues.append(Issue(f"mm im Zolllauf: „{entry.get('text')}“", "mittel"))
    return _result(
        9,
        issues,
        f"{len(texts)} Texte in {variant.get('language', '?')}",
        {"texts": len(texts), "language": variant.get("language")},
        judged=True,
    )


def _rect(entry: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    """Ein Rechteck ``[x, y, b, h]`` aus dem Protokoll, ``None`` ohne Messung."""
    values = entry.get("rect")
    if not isinstance(values, list) or len(values) != 4:
        return None
    numbers = [_number(value) for value in values]
    if any(number is None for number in numbers):
        return None
    x, y, width, height = (float(number or 0.0) for number in numbers)
    return x, y, width, height


def _reading_order_jumps(chain: Sequence[tuple[str, tuple[float, ...]]]) -> list[str]:
    """Rücksprünge der Tab-Kette gegen die Lesefolge.

    Ein Rücksprung ist ein Schritt in eine Zeile darüber oder nach links in
    derselben Zeile. Die Kette endet vor ihrem Umlauf zum ersten Element.
    """
    jumps = []
    for (before_name, before), (after_name, after) in pairwise(chain):
        bx, by, _bw, bh = before
        ax, ay, _aw, ah = after
        above = ay + ah <= by
        same_row = ay < by + bh and by < ay + ah
        if above or (same_row and ax < bx):
            jumps.append(f"{before_name} → {after_name}")
    return jumps


def _within_chain(chain: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Die Kette ohne ihr Schlussglied, wenn es sie schließt oder hinausführt.

    Der Prüfstand drückt Tab, bis ein Widget wiederkommt oder der Fokus den
    Dialog verlässt, und schreibt dieses Glied mit; ein Sprung dorthin ist
    das Ende der Kette, kein Rücksprung gegen die Lesefolge.
    """
    if not chain:
        return []
    last, before = chain[-1], chain[:-1]
    closes = any(_same_link(last, entry) for entry in before)
    return list(before) if closes or last.get("inside") is False else list(chain)


def _same_link(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    return first.get("name") == second.get("name") and first.get("rect") == second.get("rect")


def _point_10(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    chain = _list(protocol, "tab_chain")
    names = _list(protocol, "names")
    focus = protocol.get("focus_return")
    # Ohne Dialog gibt es nichts, wohin der Fokus zurückkehren müsste (Probelauf
    # F-29: an einer Befundhandlung gemessen); das sagt der Prüfstand selbst.
    without_dialog = (_map(protocol, "unmeasured") or {}).get("focus_return") == WITHOUT_DIALOG
    if chain is None or names is None or not (isinstance(focus, bool) or without_dialog):
        return _missing(10, "tab_chain", "names", "focus_return")
    issues = []
    absent = []
    placed = [(str(entry.get("name")), _rect(entry)) for entry in _within_chain(chain)]
    if any(rect is None for _name, rect in placed):
        absent.append("tab_chain.rect")
    else:
        issues += [
            Issue(f"Rücksprung in der Tab-Kette: {jump}", "mittel")
            for jump in _reading_order_jumps([(name, rect) for name, rect in placed if rect])
        ]
    shown = [str(name) for name in names]
    if any(not name.strip() for name in shown):
        issues.append(Issue("Bedienelement ohne zugänglichen Namen", "mittel"))
    doubled = sorted({name for name in shown if name.strip() and shown.count(name) > 1})
    if doubled:
        issues.append(Issue(f"doppelte Namen: {doubled}", "mittel"))
    notes = ["Bildschirmleser: ungeprüft"]
    if without_dialog and not isinstance(focus, bool):
        notes.append(f"Fokusrückkehr entfällt: {WITHOUT_DIALOG}")
    elif not focus:
        issues.append(Issue("der Fokus kehrt nach dem Dialog nicht zurück", "mittel"))
    return _settled(
        10,
        issues,
        absent,
        f"{len(chain)} Tab-Schritte",
        {"chain": len(chain), "names": len(shown)},
        notes=notes,
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
    if not ways and (_map(protocol, "unmeasured") or {}).get("revise") == STEP_WITHOUT_VALUES:
        # Ein Schritt ohne Wert (*Auf das Bett setzen*) hat keinen Dialog, der
        # aufginge — der Prüfstand sagt es, statt „öffnet nicht“ zu messen
        # (Probelauf F-23).
        return Outcome(
            12, "A", "entfaellt", NOT_APPLICABLE_REASONS["ohne_dialog"], reason="ohne_dialog"
        )
    if ways is None:
        return _missing(12, "revise")
    issues = []
    absent = []
    # Beide Wege gehören gemessen: *Diesen Schritt ändern* und der Doppelklick
    # im Verlauf (Konzept §4, Prüfpunkt 12).
    taken = {str(way.get("way")) for way in ways if isinstance(way, Mapping)}
    absent += [f"revise ({way})" for way in REVISE_WAYS if way not in taken]
    for way in ways:
        title = way.get("way", "?")
        if not way.get("opened"):
            issues.append(Issue(f"Schritt ändern über {title} öffnet nicht", "schwer"))
            continue
        after, before = _number(way.get("history_after")), _number(way.get("history_before"))
        if after is None or before is None:
            absent.append(f"revise ({title}): Verlaufslänge")
        elif after != before:
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
        typed = way.get("typed_values")
        after_params = way.get("params_after")
        if not isinstance(typed, Mapping) or not typed:
            absent.append(f"revise ({title}): keine getippte Änderung gemessen")
        elif not isinstance(after_params, Mapping):
            absent.append(f"revise ({title}): geänderte Parameter nicht übernommen")
        else:
            for name, value in typed.items():
                if name not in fields_ or name not in params:
                    issues.append(Issue(f"Fremdes Feld geändert über {title}: {name}", "schwer"))
                elif _close(value, params[name]) or value == params[name]:
                    absent.append(f"revise ({title}): Wert blieb unverändert ({name})")
                elif name not in after_params or not (
                    value == after_params[name] or _close(value, after_params[name])
                ):
                    issues.append(
                        Issue(f"Änderung nicht übernommen über {title}: {name}", "schwer")
                    )
    return _settled(12, issues, absent, f"{len(ways)} Wege", {"ways": [w.get("way") for w in ways]})


def _point_13(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    matrix = _map(protocol, "matrix")
    if matrix is None:
        return _missing(13, "matrix")
    issues = []
    notes = []
    absent = []
    for stage in SELECTION_STAGES:
        entry = matrix.get(stage)
        if not isinstance(entry, Mapping):
            absent.append(f"matrix.{stage}")
            continue
        state = entry.get("state")
        if state == MATRIX_UNREACHABLE:
            # Der Prüfstand konnte die Auswahl in der Startszene nicht
            # herstellen: gemessen ist nichts, und das bleibt sichtbar.
            notes.append(f"Auswahlstufe {stage} nicht herstellbar")
        elif state == "grau" and not str(entry.get("reason") or "").strip():
            issues.append(Issue(f"grau ohne Grund bei {stage}", "schwer"))
        elif state == "angeboten" and entry.get("effective") is False:
            issues.append(Issue(f"angeboten ohne Wirkung bei {stage}", "schwer"))
    return _settled(
        13,
        issues,
        absent,
        "sechs Auswahlstufen",
        {stage: (matrix.get(stage) or {}).get("state") for stage in SELECTION_STAGES},
        judged=True,
        notes=notes,
    )


def _point_14(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    abort = _map(protocol, "abort")
    states = _map(protocol, "states") or {}
    if abort is None:
        return _missing(14, "abort")
    seconds = _number(abort.get("eval_s"))
    if seconds is None:
        return _missing(14, "abort.eval_s")
    if seconds < BAR_AFTER_S:
        return Outcome(
            14,
            "A",
            "nicht_pruefbar",
            f"Szene rechnet {seconds:.2f} s",
            reason=f"Szene unter {BAR_AFTER_S:g} s",
        )
    issues = []
    absent = []
    if _number(abort.get("cancel_shown_s")) is None:
        issues.append(Issue("kein Abbrechen sichtbar", "schwer"))
    elif not abort.get("clicked"):
        issues.append(Issue("Abbrechen nicht geklickt", "mittel"))
    after, before = states.get("aborted"), states.get("before")
    if not isinstance(after, Mapping) or not isinstance(before, Mapping):
        # Der Stand danach fehlt — ein schon gemessener Fund bleibt (Vermerk).
        absent.append("states.aborted")
    elif _print_without_view(after) != _print_without_view(before):
        issues.append(Issue("Stand nach dem Abbruch ≠ vorher", "schwer"))
    return _settled(14, issues, absent, f"Abbruch nach {seconds:.1f} s", {"eval_s": seconds})


def _point_15(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    halt = _map(protocol, "halt")
    insertion = _map(protocol, "insertion")
    if halt is None or insertion is None:
        return _missing(15, "halt", "insertion")
    issues = []
    absent = []
    step = _number(halt.get("step"))
    if step is None:
        # Ohne die Schrittnummer, an der die Kette hält, lässt sich nicht prüfen,
        # ob der Grund sie nennt.
        absent.append("halt.step")
    elif not re.search(rf"(?<!\d){int(step)}(?!\d)", str(halt.get("text") or "")):
        issues.append(Issue(f"Haltegrund ohne Schrittnummer: „{halt.get('text')}“", "mittel"))
    if insertion.get("outcome") == "absage" and not insertion.get("actions"):
        issues.append(Issue("Absage an der Einfügemarke ohne Handlung", "mittel"))
    elif insertion.get("outcome") not in {"absage", "ergebnis"}:
        absent.append("insertion.outcome")
    return _settled(
        15,
        issues,
        absent,
        f"Halt bei Schritt {step:g}" if step is not None else "Halt ohne Schrittnummer",
        {"step": step, "insertion": insertion.get("outcome")},
    )


def _point_16(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    # Gewechselt wird während Vorschau, Entwurf und Rechnung (Konzept §4,
    # Prüfpunkt 16) — in den Lagen, die die Zeile hat (FD-128). Ohne Eingaben
    # gibt es weder Entwurf noch Vorschau, und eine Rechnung, die vorbei ist,
    # bevor der Kunde wechseln kann, ist keine Lage, in die er wechselt.
    without = {
        phase: reason
        for phase, reason in _switch_notes(protocol).items()
        if reason.startswith(SWITCH_ABSENT)
    }
    wanted = [phase for phase in SWITCH_PHASES if phase not in without]
    notes = [f"{phase} entfällt: {reason}" for phase, reason in sorted(without.items())]
    switch = _map(protocol, "switch")
    if switch is None:
        if not wanted:
            return Outcome(
                16,
                "A",
                "entfaellt",
                NOT_APPLICABLE_REASONS["ohne_rechnung"],
                reason="ohne_rechnung",
                notes=tuple(notes),
            )
        return _missing(16, *(f"switch ({phase})" for phase in wanted))
    late = [event for event in switch.get("late_events") or () if isinstance(event, Mapping)]
    issues = [
        Issue(f"nach dem Wechsel: {event.get('kind')} „{event.get('text', '')}“", "schwer")
        for event in late
    ]
    phases = sorted(set(switch.get("phases") or ()))
    absent = [f"switch ({phase})" for phase in wanted if phase not in phases]
    return _settled(
        16,
        issues,
        absent,
        f"{len(phases)} Wechsel",
        {"phases": phases, "late": len(late)},
        notes=notes,
    )


def _switch_notes(protocol: Mapping[str, Any]) -> dict[str, str]:
    """Warum eine Lage des Projektwechsels nicht lief, je Lage (``unmeasured.switch``).

    ``function_switch`` schreibt ``<lage>: <grund>`` und trennt mit „; “; ein
    Grund ohne Lage (eine fehlende Szene) gilt allen Lagen.
    """
    text = str((_map(protocol, "unmeasured") or {}).get("switch") or "")
    found: dict[str, str] = {}
    for part in (piece.strip() for piece in text.split("; ") if piece.strip()):
        phase, separator, reason = part.partition(": ")
        if separator and phase in SWITCH_PHASES:
            found[phase] = reason
        else:
            found.update({phase: part for phase in SWITCH_PHASES if phase not in found})
    return found


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


def judge_licence(runs: Mapping[str, Any], *, complete: bool) -> Outcome:
    """Prüfpunkt 18 über die Lizenzläufe einer Zeile.

    Gesperrt (``LOCKED_STATES``) heißt: Schreibendes grau mit Grund, Lesendes
    frei; freigeschaltet heißt: alles frei. ``complete`` verlangt jeden Lauf aus
    ``function_list.licence_states`` — so urteilt ``function_report.merge_cases`` einmal je
    Zeile über die Läufe aller ihrer Fälle; ein fehlender Lauf ist dann nicht
    gemessen. Ein einzelner Fall trägt nur seinen Lauf und wird nur an ihm
    gemessen.

    Jeder Lauf trägt, wie das Ziel dastand (``state``: :data:`LICENCE_RUN_STATES`),
    und den Grund aus dem grauen Ziel. **„fehlt“ ist kein Grund** (Durchsicht
    welle4 C-S1): Fehlt das Ziel im gesperrten Lauf und steht es freigeschaltet
    da, versteckt die Oberfläche es, statt es auszugrauen — ein Fund. Sonst hat
    der Prüfstand das Ziel nicht erreicht, und der Lauf ist nicht gemessen.
    """
    issues = []
    absent = [f"unbekannter Lizenzzustand {state}" for state in runs if state not in LICENCE_STATES]
    if not runs:
        absent.append("licence_runs")
    if complete:
        absent += [f"Lizenzlauf {state}" for state in licence_states() if state not in runs]
    measured = {
        state: entry
        for state, entry in runs.items()
        if state in LICENCE_STATES
        and isinstance(entry, Mapping)
        and isinstance(entry.get("writes"), bool)
        and entry.get("state") in LICENCE_RUN_STATES
        and isinstance(entry.get("reason"), str)
    }
    # Ob eine Funktion schreibt, ist ihre Eigenschaft, nicht die eines Laufs: Was
    # freigeschaltet das Dokument ändert, schreibt auch im gesperrten Lauf, wo
    # nichts geändert werden konnte (Probelauf F-35).
    writing = any(entry["writes"] for entry in measured.values())
    offered_unlocked = any(
        LICENCE_UNLOCKED[state] and entry.get("state") == LICENCE_RUN_STATES[0]
        for state, entry in measured.items()
    )
    for state in LICENCE_STATES:
        if state not in runs:
            continue
        if state not in measured:
            absent.append(f"licence_runs.{state}")
            continue
        entry = measured[state]
        writes = writing or entry["writes"]
        shown, reason = entry["state"], entry["reason"]
        should = LICENCE_UNLOCKED[state] or not writes
        if shown == LICENCE_MISSING:
            if LICENCE_UNLOCKED[state] or not offered_unlocked:
                absent.append(f"licence_runs.{state} (Ziel nicht erreicht)")
            elif writes:
                issues.append(
                    Issue(f"schreibendes Ziel fehlt bei {state}, statt grau mit Grund", "mittel")
                )
            else:
                issues.append(
                    Issue(f"lesendes Ziel fehlt bei {state}, obwohl es offen bleibt", "schwer")
                )
            continue
        enabled = shown == LICENCE_RUN_STATES[0]
        if not enabled and not reason.strip():
            issues.append(Issue(f"grau ohne Grund bei {state}", "schwer"))
        if enabled and not should:
            # Regelverstoß und Umweg (Konzept §4, *mittel*): Der Kern lehnt an der
            # Lizenzgrenze ab, die Oberfläche hätte grau sein sollen (D-L3).
            issues.append(Issue(f"schreibendes Ziel frei trotz {state}", "mittel"))
        if not enabled and should:
            # Gekauft schaltet frei, und Lesendes bleibt in jedem Zustand offen
            # (``Activation.unlocked``, Lizenzgrenze in ``kern.md``).
            issues.append(Issue(f"gesperrt, obwohl {state} es offen lässt", "schwer"))
    return _settled(
        18,
        issues,
        absent,
        f"{len(runs)} Lizenzläufe",
        {
            state: entry.get("state") if isinstance(entry, Mapping) else None
            for state, entry in runs.items()
        },
    )


def _point_18(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    runs = _map(protocol, "licence_runs")
    if not runs:
        return _missing(18, "licence_runs")
    return judge_licence(runs, complete=False)


def judge_design(criteria: Mapping[str, Outcome]) -> Outcome:
    """Prüfpunkt 19 aus seinen Kriterien — je Fall und einmal je Zeile (``merge_cases``)."""
    parts = [criteria.get(key) for key in DESIGN_PARTS if key != "Z7"]
    # Der Gesamteindruck — hochwertig, aufgeräumt, nichts Überflüssiges —
    # urteilt immer Stufe B (Konzept §4).
    return _combine(19, parts, judged=True, summary="Gestaltung")


def _point_19(
    protocol: Mapping[str, Any], context: Context, criteria: Mapping[str, Outcome]
) -> Outcome:
    return judge_design(criteria)


JudgePoint = Callable[[Mapping[str, Any], Context, Mapping[str, Outcome]], Outcome]


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
    if reason not in NOT_APPLICABLE_REASONS:
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
        outcome.subject,
        outcome.stage,
        "entfaellt",
        NOT_APPLICABLE_REASONS[reason],
        reason=reason,
    )


def judge_case(
    protocol: Mapping[str, Any], context: Context, source: str = "function.json"
) -> CaseOutcome:
    """Alle Prüfpunkte und die geltenden Kriterien eines Falls.

    ``source`` ist die Datei des Protokolls, relativ zu ``<out>/cases``
    (``1/function.json``, ``2/surfaces/drill_hole.json``) — auf sie zeigen die
    Belege.
    """
    problems = tuple(validate_protocol(protocol))
    reasons = _not_applicable(_spec(protocol))
    images = tuple(str(image) for image in _list(protocol, "images") or ())

    def evidence(outcome: Outcome, fields: Iterable[str]) -> Outcome:
        # Beleg (Konzept §5, „mit Bild und Stelle“): die Bilder des Falls und
        # die Stellen im Protokoll, die das Urteil gelesen hat.
        read = tuple(f"{source}#{name}" for name in fields if name in protocol)
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
