"""Regel 17 im Prüfbericht: Jeder Fehler und jede Warnung hat einen Weg.

Ein Befund, der sagt, was nicht stimmt, und dann aufhört, ist „fehlgeschlagen"
mit mehr Worten. ``test_errors.py`` hält das für Ausnahmen fest; dieser Test
hält es für Befunde des Kerns (RM-215). Gezählt in der Durchsicht 0.5.1: 311
Befundstellen ohne Handlung, darunter acht Fehler und 101 Warnungen.

Einen Weg hat eine Befundstelle, wenn sie ``suggestions=`` trägt, ihre Kennung
in ``panels.FINDING_ACTIONS`` steht oder sie aus einer gescheiterten Operation
kommt (``op.…``: *Eingabe korrigieren*, ``panels.actions_for``). Wo es keinen
Knopf geben kann, steht die Kennung unten **mit Grund** — ein Grund heißt: Ein
Knopf wäre wirkungslos, oder die Handlung gibt es nicht und der Satz nennt sie.

Gelesen wird der Quelltext (``ast``), nicht ein Lauf: Die meisten dieser
Befunde entstehen nur an Geometrie, die niemand in der Suite baut.
"""

from __future__ import annotations

import ast
from pathlib import Path

import app.core

#: Kennung → warum sie ohne Knopf bleibt. Eine Kennung mit Platzhalter
#: (``{op}.…``) steht so, wie der Quelltext sie baut.
OHNE_KNOPF: dict[str, str] = {
    # Der Chat zeigt Vorschlagsbefunde als Zeilen am Vorschlag, dessen Knöpfe
    # Annehmen und Verwerfen sind (``chat._proposal_lines``); die Befunde der
    # Prüfung gehen außerdem an das Sprachmodell zurück.
    "agent.stopped": "Kopfzeile für das Sprachmodell; der Grund steht als eigener Befund daneben.",
    "agent.volume_jumped": "Am Vorschlag im Chat; der Weg ist Verwerfen.",
    "agent.components_grew": "Am Vorschlag im Chat; der Weg ist Verwerfen.",
    "agent.answer_truncated": "Im Chat; der Satz nennt die kürzere Anweisung.",
    "agent.halted_by_document_change": "Im Chat; die Änderung ist schon zurückgenommen.",
    "agent.answer_refused": "Im Chat; der Satz nennt andere Anweisung oder anderes Modell.",
    "agent.call_written_out": "Im Chat; der Satz nennt *Werkzeuge prüfen*.",
    "variants.stopped": (
        "Der Variantendialog bleibt offen, nennt die Werte ohne Ergebnis und setzt den "
        "Cursor in „Erster Wert“ (``variants_dialog._finished``)."
    ),
    # Der Weg liegt außerhalb: Speicherplatz freigeben — der Satz nennt es, und
    # Solidon nimmt den Hilfsprozess nach der Frist von selbst wieder (RM-436).
    "kernel.disk_full": "Der Satz nennt den Weg: Speicherplatz freigeben.",
    # Auskünfte über den Rechenweg: Es ist nichts falsch, und es gibt nichts zu tun.
    "boolean.jittered": "Auskunft über die Rückfallstufe (§17.2), das Ergebnis ist gültig.",
    "brep.from_mesh.freeform": "Auskunft beim Umwandeln; der Rest bleibt, wie er im Netz war.",
    "brep.from_mesh.deviation": "Auskunft beim Umwandeln; die Karte zeigt die Abweichung im Satz.",
    "hollow.exact_fallback": "Auskunft: Die Wand entstand am Netz, der Satz sagt, warum.",
    "evaluate.creator_inputs_dropped": "Auskunft; die übergangenen Objekte bleiben erhalten.",
    "seal.counterface": "Auskunft über die gemessene Gegenfläche.",
    "gcode.deviation": "Auskunft mit Herkunft (§22.5); Schätzung und G-Code stehen nebeneinander.",
    "export.part_setting": "Auskunft: Die Geometrie verlangt die Einstellung, sie ist gesetzt.",
    "export.part_setting_unavailable": "Auskunft über den Slicer; eine andere gibt es dort nicht.",
    "slicer.unknown_key": "Auskunft über die Slicer-Version; die Namen stehen in den Werten.",
    "slicer.arranged_itself": "Auskunft: Der Slicer hat selbst angeordnet, die Datei ist druckbar.",
    "split.no_cut_face": "Auskunft beim Teilen: Getrennt ist, nur ohne Stifte.",
    "split.seam_too_thin": "Auskunft beim Teilen: Getrennt ist, geklebt hält die Naht.",
    "split.face_too_small": "Auskunft beim Teilen: Getrennt ist, der Satz sagt „geklebt hält sie“.",
    # Der Weg ist ein Schritt vor diesem — den gibt es nicht als Knopf, der Satz nennt ihn.
    "displace.too_coarse": "Der Weg ist Vernetzen vor dem Relief; der Satz nennt es.",
    "sculpt.too_coarse": "Der Weg ist Vernetzen vor dem Formen; der Satz nennt es.",
    "pose.pinched": "Der Weg ist ein feineres Netz vor der Stellung; der Satz nennt es.",
    # Das Formen: *Eingabe korrigieren* öffnet nur den Rohtext der Striche,
    # nicht den Formeditor — ein Knopf dorthin wäre wirkungslos.
    "sculpt.no_effect": "Formeditor nicht aus dem Bericht erreichbar; der Satz nennt die Ursachen.",
    "sculpt.subtle": "Formeditor nicht aus dem Bericht erreichbar; der Satz nennt die Ursachen.",
    "sculpt.strokes_missed": "Formeditor aus dem Bericht nicht erreichbar; Satz nennt den Grund.",
    "sculpt.inverted": "Formeditor nicht aus dem Bericht erreichbar; der Satz nennt die Stärke.",
    "pose.no_armature": "Der Satz nennt den Skeletteditor; aus dem Bericht öffnet er sich nicht.",
    # Einlesen: der Weg liegt außerhalb von Solidon (Slicer, CAD-Programm, Datei).
    "ingest.foreign_volume": "Der Bereich gehört dem Slicer; der Satz sagt, wie er geladen ist.",
    "ingest.negative_orphaned": "Auskunft: Die Aussparung hat keinen Körper, dem sie gälte.",
    "ingest.negative_kept_out": "Auskunft: Die Aussparung hätte den ganzen Körper genommen.",
    "ingest.colours_dropped": "Der Satz nennt den Slicer als Weg zu den Farben.",
    "ingest.palette_dropped": "Der Satz nennt den Slicer als Weg zu den Farben.",
    "step.metadata_lost": "Der Satz nennt das CAD-Programm als Weg.",
    "step.colours_merged": "Der Satz nennt die Filamentzuweisung als Weg.",
    # Projekt und Bausteine: Herkunft und Dateien, die beim Kunden liegen.
    "project.scripted_source": "Sicherheitsauskunft (§32); zu tun ist nichts.",
    "project.carried_chat": "Sicherheitsauskunft (§32); zu tun ist nichts.",
    "project.external_source": "Auskunft; die Dateien liegen beim Kunden.",
    "parts.scripted_recipe": "Sicherheitsauskunft (§32); zu tun ist nichts.",
    "parts.travelling": "Der Satz nennt die Dateien, die der Empfänger braucht.",
    "parts.recipe_failed": "Die Datei liegt beim Kunden; die Werte nennen sie.",
    "parts.user_failed": "Die Datei liegt beim Kunden; die Werte nennen sie.",
    "parts.counterpart_unpaired": "Der Verlauf hat sich geändert; Satz nennt, was zu prüfen ist.",
    "slicer.overrides_unassigned": "Der Satz nennt die Spule; einen Knopf zur Spule gibt es nicht.",
    "parameter.out_of_range": "Der Satz nennt den Ausdruck; ein Knopf zur Parameterliste fehlt.",
    # Merkmale, deren Bezug nach einem Schritt fehlt: Die Geometrie stimmt,
    # der Satz nennt Strg+Z; eine Rücknahme gibt es nicht als Knopf.
    "{…}.feature_lost": "Die Geometrie stimmt; der Satz nennt Strg+Z.",
    "slot_hole.feature_lost": "Die Geometrie stimmt; der Satz nennt Strg+Z.",
    "resize_hole.feature_lost": "Die Geometrie stimmt; der Satz nennt Strg+Z.",
    "feature.body_split": "Der Körper ist zerfallen; der Satz nennt Strg+Z.",
}


def _code(node: ast.expr) -> list[str]:
    """Die Kennungen, die ein ``code=`` bilden kann — ein ``… if … else …`` sind zwei."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [
            "".join(part.value if isinstance(part, ast.Constant) else "{…}" for part in node.values)
        ]
    if isinstance(node, ast.IfExp):
        return _code(node.body) + _code(node.orelse)
    return [ast.unparse(node)]


def _severities(node: ast.expr) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.IfExp):
        return _severities(node.body) | _severities(node.orelse)
    return set()


def _sites() -> list[tuple[str, int, list[str], set[str], bool]]:
    """Jede ``Finding(...)``-Stelle im Kern: Ort, Kennungen, Stufen, trägt sie Vorschläge?"""
    root = Path(app.core.__file__).parent
    found = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Finding"
            ):
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            if "code" not in keywords or "severity" not in keywords:
                continue  # eine andere Klasse gleichen Namens (``parts/shared.py``)
            suggested = None in keywords or (
                "suggestions" in keywords
                and not (
                    isinstance(keywords["suggestions"], ast.Tuple)
                    and not keywords["suggestions"].elts
                )
            )
            found.append(
                (
                    path.relative_to(root).as_posix(),
                    node.lineno,
                    _code(keywords["code"]),
                    _severities(keywords["severity"]),
                    suggested,
                )
            )
    return found


def test_every_error_and_warning_has_a_way() -> None:
    from app.ui.panels import FINDING_ACTIONS

    sites = _sites()
    assert len(sites) > 300, f"nur {len(sites)} Befundstellen gefunden — dann prüft das nichts"

    without: list[str] = []
    used: set[str] = set()
    for name, line, codes, severities, suggested in sites:
        if not severities & {"warning", "error"} or suggested:
            continue
        for code in codes:
            if code in FINDING_ACTIONS or code.startswith("op."):
                continue
            if code in OHNE_KNOPF:
                used.add(code)
                continue
            without.append(f"app/core/{name}:{line} {code} ({'/'.join(sorted(severities))})")
    assert not without, (
        "Warnung oder Fehler ohne Weg (Regel 17) — Handlung setzen oder mit Grund in "
        "OHNE_KNOPF eintragen:\n" + "\n".join(without)
    )
    unused = sorted(set(OHNE_KNOPF) - used)
    assert not unused, f"Ausnahmen ohne Befund — austragen: {unused}"


#: Befunde, die sagen, was ein Schritt mit einem änderbaren Wert getan hat
#: (RM-374, Vorgabe Robert 02.10.2026). Sie tragen den Knopf, der genau diesen
#: Schritt zum Ändern öffnet (``errors.CHANGE_*``, Kennung ``change_step``).
#: Wer einen solchen Befund baut, trägt ihn hier ein — mit dem Feld, in das
#: der Cursor gehört, oder ``None`` für den Schritt als Ganzes. Meint derselbe
#: Befund an verschiedenen Merkmalsarten verschiedene Werte, steht das Feld je
#: Stelle da, nach der Funktion, in der der Befund entsteht — eine Menge ließe
#: „``pitch`` am Gewinde“ durch (Review RM-441).
MEINT_DEN_SCHRITT: dict[str, str | dict[str, str] | None] = {
    "transform.fitted": "largest",
    "transform.without_effect": None,
    "lattice.filled": "cell",
    "displace.applied": "strength",
    "hollow.done": "wall",
    "thread.thin_wall": "diameter",
    "parts.bore_too_wide": "size",
    # RM-441: die „hat nichts getan“-Befunde aus dem Review vom 02.10.2026.
    "mesh.already_below_target": "triangles",
    "move_feature.unchanged": "x",
    "duplicate_feature.unchanged": "x",
    # RM-546: Um die eigene Achse gedreht meint der Befund die Achse, nach einer
    # vollen Umdrehung den Winkel.
    "rotate_feature.unchanged": {
        "rotate_feature": "angle",
        "_rotate_torus": "axis",
        "_turned_onto_itself": frozenset({"axis", "angle"}),
    },
    "resize_feature.unchanged": {
        "resize_feature": "diameter",
        "_resize_torus": "diameter",
        "_resize_pattern": "pitch",
        "_resize_thread": "diameter",
        "_reshape_the_fillet": "diameter",
    },
    "bore.resize_unchanged": "diameter",
    "bore.already_through": "depth",
    "pin_for_bore.thread_touches": "clearance",
    # Review RM-532 Runde 2, N2: Restwand und Aufbohren am Gewinde öffnen das Feld,
    # das das Maß trägt — bei „Eigenes Maß“ den Nenndurchmesser, sonst die Größe.
    "parts.thread_thin_wall": frozenset({"diameter", "size"}),
    "parts.bore_widened": frozenset({"diameter", "size"}),
    "parts.countersink_derived": "countersink",
    # RM-633: die Wand ist dicker, als der Baustein eingetragen hat.
    "parts.wall_thicker": "wall",
}

#: Die Operationen, deren Dialog der Knopf öffnet — das Feld muss es an jeder
#: geben, sonst fände ``edit_operation`` es nicht und öffnete still ohne
#: Cursor. Nicht hier: Befunde ohne Feld (``transform.without_effect``) und
#: solche der Bausteine statt einer Operation (``parts.bore_too_wide``).
OPERATION_OF: dict[str, tuple[str, ...]] = {
    "transform.fitted": ("fit_to_size",),
    "lattice.filled": ("lattice_fill",),
    "displace.applied": ("displace_image",),
    "hollow.done": ("hollow_object", "shell_exact"),
    "thread.thin_wall": ("resize_feature",),
    "mesh.already_below_target": ("decimate_mesh",),
    "move_feature.unchanged": ("move_feature",),
    "duplicate_feature.unchanged": ("duplicate_feature",),
    "rotate_feature.unchanged": ("rotate_feature",),
    "resize_feature.unchanged": ("resize_feature",),
    "bore.resize_unchanged": ("resize_hole",),
    "bore.already_through": ("resize_hole",),
    "pin_for_bore.thread_touches": ("pin_for_bore",),
}

#: Befunde mit Feld, die keine Operation öffnen: Der Baustein hat seinen eigenen
#: Dialog. Jedes andere Kennwort mit Feld steht in ``OPERATION_OF`` — sonst
#: liefe es ungeprüft gegen das Register.
OHNE_OPERATION: frozenset[str] = frozenset(
    {
        "parts.bore_too_wide",
        "parts.thread_thin_wall",
        "parts.bore_widened",
        "parts.countersink_derived",
        "parts.wall_thicker",
    }
)

#: Helfer, die einen solchen Befund bauen; das Feld ist ihr zweites Argument
#: oder ``field=``.
BEFUND_HELFER: dict[str, str] = {"_already_this_size": "resize_feature.unchanged"}


def _suggestion_names(node: ast.expr) -> set[str]:
    """Die Namen der Handlungen in ``suggestions=(…)``."""
    if isinstance(node, ast.Tuple | ast.List):
        return {element.id for element in node.elts if isinstance(element, ast.Name)}
    return set()


def _fields(node: ast.expr) -> tuple[object, ...]:
    """Die Felder eines ``"field":``-Werts: ausgeschrieben oder ``a if … else b``."""
    if isinstance(node, ast.Constant):
        return (node.value,)
    if isinstance(node, ast.IfExp):
        return _fields(node.body) + _fields(node.orelse)
    return ("?",)


def _codes(node: ast.expr | None) -> tuple[str, ...]:
    """Die Kennwörter eines ``code=``: ausgeschrieben oder ``a if … else b``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    if isinstance(node, ast.IfExp):
        return _codes(node.body) + _codes(node.orelse)
    return ()


def _hidden_code(node: ast.expr | None) -> bool:
    """Ein zusammengesetztes Kennwort, das auf einen Eintrag oben endet.

    ``code=f"{operation}.unchanged"`` stand so bis RM-441 da: Für diesen
    Wächter war die Stelle unsichtbar, und sie trug keinen Knopf.
    """
    if not isinstance(node, ast.JoinedStr) or not node.values:
        return False
    tail = node.values[-1]
    if not (isinstance(tail, ast.Constant) and isinstance(tail.value, str)):
        return False
    return any(code.endswith(tail.value) for code in MEINT_DEN_SCHRITT if "." in tail.value)


def test_a_finding_about_a_step_value_opens_that_step() -> None:
    """RM-374: „Auf Maß gebracht.“ meldete die Arbeitsgröße ohne Weg zum
    gemeinten Maß. Jeder Befund, der einen änderbaren Schritt meint, bringt
    jetzt den Knopf mit, der diesen Schritt öffnet — gelesen am Quelltext,
    jede Stelle, an der der Befund entsteht."""
    from app.core import errors

    changes = {
        name
        for name, value in vars(errors).items()
        if isinstance(value, errors.Action) and value.id == "change_step"
    }
    assert len(changes) >= 3, changes
    root = Path(app.core.__file__).parent
    found: dict[str, int] = {}
    without: list[str] = []
    seen: list[tuple[str, str | None, str]] = []  # Kennwort, Feld, Ort

    def expected(code: str, function: str) -> str | None:
        field = MEINT_DEN_SCHRITT[code]
        if isinstance(field, dict):
            return field.get(function, f"<keine Angabe für {function}>")
        return field

    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

        def function_of(node: ast.AST, parents: dict[ast.AST, ast.AST] = parents) -> str:
            while node in parents:
                node = parents[node]
                if isinstance(node, ast.FunctionDef):
                    return node.name
            return "<Modul>"

        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            place = f"app/core/{path.relative_to(root).as_posix()}:{node.lineno}"
            if node.func.id in BEFUND_HELFER:
                code = BEFUND_HELFER[node.func.id]
                found[code] = found.get(code, 0) + 1
                given = {keyword.arg: keyword.value for keyword in node.keywords}
                argument = node.args[1] if len(node.args) > 1 else given.get("field")
                named = argument.value if isinstance(argument, ast.Constant) else "?"
                field = expected(code, function_of(node))
                allowed = field if isinstance(field, frozenset) else {field}
                if named not in allowed:
                    without.append(f"{place} {code}: Feld {named!r} statt {field!r}")
                seen.append((code, named, place))
                continue
            if node.func.id != "Finding":
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            if _hidden_code(keywords.get("code")):
                without.append(f"{place}: Kennwort zusammengesetzt — ausschreiben")
            for code in _codes(keywords.get("code")):
                if code not in MEINT_DEN_SCHRITT:
                    continue
                where = f"{place} {code}"
                if not _suggestion_names(keywords.get("suggestions", ast.Tuple(elts=[]))) & changes:
                    without.append(f"{where}: ohne Knopf zum Ändern des Schritts")
                values = keywords.get("values")
                named: tuple[object, ...] = (None,)
                if isinstance(values, ast.Dict):
                    for key, value in zip(values.keys, values.values, strict=True):
                        if isinstance(key, ast.Constant) and key.value == "field":
                            named = _fields(value)
                if function_of(node) in BEFUND_HELFER:
                    continue  # der Helfer selbst; seine Aufrufe zählen oben
                found[code] = found.get(code, 0) + 1
                field = expected(code, function_of(node))
                allowed = field if isinstance(field, frozenset) else {field}
                for name in named:
                    if name not in allowed:
                        without.append(f"{where}: Feld {name!r} statt {sorted(map(str, allowed))}")
                    seen.append((code, name, place))
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY

    load_operations()
    with_field = {code for code, field in MEINT_DEN_SCHRITT.items() if field is not None}
    assert with_field >= OHNE_OPERATION and not OHNE_OPERATION & set(OPERATION_OF), OHNE_OPERATION
    unlisted = with_field - OHNE_OPERATION - set(OPERATION_OF)
    assert not unlisted, f"ohne Operation in OPERATION_OF, ungeprüft gegen das Register: {unlisted}"
    for code, named, place in seen:
        if named is None or code in OHNE_OPERATION:
            continue
        for operation in OPERATION_OF[code]:
            fields = {entry.name for entry in REGISTRY.get(operation).params.spec()}
            if named not in fields:
                without.append(f"{place} {code}: {operation} hat kein Feld {named!r}")
    assert set(found) == set(MEINT_DEN_SCHRITT), f"Befund nicht gefunden: {found}"
    assert not without, "\n".join(without)
