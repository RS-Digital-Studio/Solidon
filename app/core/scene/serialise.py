"""Dokument zu Daten und zurück (Bauplan §12).

Die Schlüssel, die hier geschrieben werden, sind das Dateiformat. Sie sind
englisch, sie sind stabil, und sie entsprechen dem Beispiel in §12 —
einschließlich ``in``/``out``, die als Python-Schlüsselwörter im Code
``inputs``/``outputs`` heißen.

Zwei Indirektionen überstehen die runde Reise unangetastet, denn genau das
ist ihr Zweck: ``auto:<material>`` für Toleranzen und ``=@name`` für
Parameter (§13).
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Final

from app.core.errors import ValidationError
from app.core.types import (
    FIT_KINDS,
    Action,
    AdhesionSettings,
    ChatEntry,
    CoolingSettings,
    Document,
    DocumentChange,
    DocumentState,
    FeatureRef,
    FilamentSettings,
    Finding,
    Fit,
    InfillSettings,
    IngestInfo,
    LayerSettings,
    Operation,
    Origin,
    Parameter,
    PrintSettings,
    Report,
    RetractionSettings,
    ShellSettings,
    SlotOverride,
    SolverInfo,
    Source,
    SourceOrigin,
    SpeedSettings,
    SupportSettings,
    TemperatureSettings,
    Transaction,
)
from app.i18n import TranslatableText, _


def _without_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


# --- Parameter -----------------------------------------------------------------


def parameter_to_data(parameter: Parameter) -> dict[str, Any]:
    """Ein Titel aus dem Code reist als Message-ID, ein getippter als Text.

    Dasselbe Muster wie :func:`transaction_to_data`: ``str(title)`` fror die
    Übersetzung der Sprache ein, die beim **Speichern** aktiv war — das
    mitgelieferte Beispiel ``dose-mit-deckel.p3d`` zeigte einem englischen
    Kunden „Breite/Tiefe/Höhe/Wandstärke", obwohl die Übersetzungen
    existieren (Fund des Gesamtreviews vom 25.08.2026).
    """
    title = parameter.title
    return _without_none(
        {
            "value": parameter.value,
            "unit": parameter.unit,
            "min": parameter.minimum,
            "max": parameter.maximum,
            "title": (
                None
                if title is None
                else (title.msgid if isinstance(title, TranslatableText) else str(title))
            ),
            "title_translatable": True if isinstance(title, TranslatableText) else None,
            "title_context": title.context if isinstance(title, TranslatableText) else None,
            "expression": parameter.expression,
        }
    )


def parameter_from_data(name: str, data: dict[str, Any]) -> Parameter:
    title: TranslatableText | str | None = data.get("title")
    if title is not None and data.get("title_translatable"):
        title = TranslatableText(str(title), data.get("title_context"))
    return Parameter(
        name=name,
        value=float(data.get("value", 0.0)),
        unit=data.get("unit", "mm"),
        title=title,
        minimum=data.get("min"),
        maximum=data.get("max"),
        expression=data.get("expression"),
    )


# --- Passungen ------------------------------------------------------------------


def fit_to_data(fit: Fit) -> dict[str, Any]:
    return {
        "name": fit.name,
        "a": str(fit.a),
        "b": str(fit.b),
        "type": fit.kind,
        "tolerance": fit.tolerance,
    }


def fit_from_data(data: dict[str, Any]) -> Fit:
    kind = data.get("type", "clearance")
    if kind not in FIT_KINDS:
        # Vor der Auswertung, nicht mitten in ihr: ``check_fits`` steht
        # außerhalb jedes ``try``, und eine unbekannte Passungsart aus der
        # Datei riss die Auswertung mit einer rohen ``KeyError`` ab (Fund
        # des Gesamtreviews vom 25.08.2026).
        raise ValidationError(
            field="fits",
            detail=_(
                "Eine Passung in der Datei trägt eine unbekannte Art. "
                "Entfernen Sie die Passung, oder öffnen Sie die Datei mit "
                "einer neueren Version."
            ),
            constraint="unknown_format",
            values={"fit": str(data.get("name", "?")), "kind": str(kind)},
        )
    return Fit(
        name=data["name"],
        a=FeatureRef.parse(data["a"]),
        b=FeatureRef.parse(data["b"]),
        kind=kind,
        tolerance=data.get("tolerance", "auto:"),
    )


# --- Quellen --------------------------------------------------------------------


def source_to_data(source: Source) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": source.kind,
        "path": source.path,
        "sha256": source.sha256,
        "embedded": source.embedded,
        "ingest": {
            "unit": source.ingest.unit,
            "scale": source.ingest.scale,
            "welded": source.ingest.welded,
            "removed_triangles": source.ingest.removed_triangles,
            "components": source.ingest.components,
        },
    }
    if source.origin is not None:
        data["origin"] = _without_none(
            {
                "url": source.origin.url,
                "title": source.origin.title,
                "author": source.origin.author,
                "license": source.origin.licence,
                "retrieved": source.origin.retrieved,
                "prompt": source.origin.prompt,
                "seed": source.origin.seed,
            }
        )
    return data


def source_from_data(source_id: str, data: dict[str, Any]) -> Source:
    ingest = data.get("ingest", {})
    origin = data.get("origin")
    return Source(
        id=source_id,
        kind=data.get("type", "import"),
        path=data["path"],
        sha256=data.get("sha256", ""),
        embedded=bool(data.get("embedded", True)),
        ingest=IngestInfo(
            unit=ingest.get("unit", "mm"),
            scale=float(ingest.get("scale", 1.0)),
            welded=bool(ingest.get("welded", False)),
            removed_triangles=int(ingest.get("removed_triangles", 0)),
            components=int(ingest.get("components", 1)),
        ),
        origin=(
            SourceOrigin(
                url=origin.get("url"),
                title=origin.get("title"),
                author=origin.get("author"),
                licence=origin.get("license"),
                retrieved=origin.get("retrieved"),
                prompt=origin.get("prompt"),
                seed=(None if origin.get("seed") is None else int(origin["seed"])),
            )
            if origin
            else None
        ),
    )


# --- Stapel ---------------------------------------------------------------------


def origin_to_data(origin: Origin) -> dict[str, Any]:
    return _without_none(
        {
            "by": origin.by,
            "model": origin.model,
            "prompt_version": origin.prompt_version,
            "rules_version": origin.rules_version,
            "temperature": origin.temperature,
        }
    )


def origin_from_data(data: dict[str, Any] | None) -> Origin:
    if not data:
        return Origin(by="user")
    return Origin(
        by=data.get("by", "user"),
        model=data.get("model"),
        prompt_version=data.get("prompt_version"),
        rules_version=data.get("rules_version"),
        temperature=data.get("temperature"),
    )


def state_to_data(state: DocumentState) -> dict[str, Any]:
    """Eine Seite einer Dokumentänderung (§15.5).

    Ein Feld, das nicht beteiligt war, fehlt hier ganz — das unterscheidet es
    von einem, das beteiligt und leer war. Bei den Parametern bleibt ein
    ``null`` dagegen stehen: es heißt „gab es damals nicht" und macht aus dem
    Undo eines neuen Parameters ein Löschen.
    """
    return _without_none(
        {
            "parameters": (
                None
                if state.parameters is None
                else {
                    name: None if parameter is None else parameter_to_data(parameter)
                    for name, parameter in state.parameters.items()
                }
            ),
            "fits": None if state.fits is None else [fit_to_data(entry) for entry in state.fits],
            "printer": state.printer,
            "material": state.material,
            # Seit v12: die Fassung eines nachträglich geänderten Schritts —
            # beide Seiten reisen mit, sonst ist der alte Stand nach dem
            # Speichern unwiederbringlich (§15.4, §15.5).
            "edited_ops": (
                None
                if state.edited_ops is None
                else {
                    str(op_id): None if version is None else operation_to_data(version)
                    for op_id, version in state.edited_ops.items()
                }
            ),
        }
    )


def state_from_data(data: dict[str, Any]) -> DocumentState:
    parameters = data.get("parameters")
    fits = data.get("fits")
    edited = data.get("edited_ops")
    return DocumentState(
        edited_ops=(
            None
            if edited is None
            else {
                int(op_id): None if version is None else operation_from_data(version)
                for op_id, version in edited.items()
            }
        ),
        parameters=(
            None
            if parameters is None
            else {
                name: None if entry is None else parameter_from_data(name, entry)
                for name, entry in parameters.items()
            }
        ),
        fits=None if fits is None else tuple(fit_from_data(entry) for entry in fits),
        printer=data.get("printer"),
        material=data.get("material"),
    )


def change_to_data(change: DocumentChange) -> dict[str, Any]:
    return {"before": state_to_data(change.before), "after": state_to_data(change.after)}


def change_from_data(data: dict[str, Any]) -> DocumentChange:
    return DocumentChange(
        before=state_from_data(data.get("before", {})),
        after=state_from_data(data.get("after", {})),
    )


def transaction_to_data(transaction: Transaction) -> dict[str, Any]:
    """Ein Titel aus dem Code reist als Message-ID, ein getippter als Text.

    ``title_translatable`` unterscheidet die beiden: steht es, ist ``title``
    die Message-ID (der deutsche Quelltext, §4.1), und die Anzeige löst sie in
    der aktiven Sprache auf — die mitgelieferten Beispiele zeigen ihren
    Verlauf so auch englisch. Fehlt es, ist ``title`` wörtlich gemeint und
    bleibt es auch: was ein Nutzer selbst benannt hat, wird nicht übersetzt.
    """
    title = transaction.title
    return _without_none(
        {
            "id": transaction.id,
            "title": title.msgid if isinstance(title, TranslatableText) else str(title),
            "title_translatable": True if isinstance(title, TranslatableText) else None,
            "title_context": title.context if isinstance(title, TranslatableText) else None,
            "origin": origin_to_data(transaction.origin),
            "ops": list(transaction.ops),
            "changes": (
                None if transaction.changes is None else change_to_data(transaction.changes)
            ),
        }
    )


def transaction_from_data(data: dict[str, Any]) -> Transaction:
    changes = data.get("changes")
    title: TranslatableText | str = data.get("title", "")
    if data.get("title_translatable"):
        title = TranslatableText(str(title), data.get("title_context"))
    return Transaction(
        id=data["id"],
        title=title,
        ops=tuple(int(entry) for entry in data.get("ops", ())),
        origin=origin_from_data(data.get("origin")),
        changes=None if changes is None else change_from_data(changes),
    )


def chat_to_data(entry: ChatEntry) -> dict[str, Any]:
    """§26.3: der Beitrag und die Transaktion, die er erzeugt hat, gehören
    zusammen."""
    return _without_none(
        {
            "id": entry.id,
            "role": entry.role,
            "text": entry.text,
            "transaction": entry.transaction_id,
            "origin": origin_to_data(entry.origin) if entry.origin is not None else None,
        }
    )


def chat_from_data(data: dict[str, Any]) -> ChatEntry:
    return ChatEntry(
        id=str(data["id"]),
        role=data.get("role", "user"),
        text=str(data.get("text", "")),
        transaction_id=data.get("transaction"),
        origin=origin_from_data(data["origin"]) if data.get("origin") else None,
    )


def solver_to_data(solver: SolverInfo) -> dict[str, Any]:
    return _without_none(
        {
            "strategy": solver.strategy,
            "attempted": list(solver.attempted) or None,
            "seed": solver.seed,
            "note": str(solver.note) if solver.note is not None else None,
        }
    )


def solver_from_data(data: dict[str, Any] | None) -> SolverInfo | None:
    if not data:
        return None
    return SolverInfo(
        strategy=data["strategy"],
        attempted=tuple(data.get("attempted", ())),
        seed=data.get("seed"),
        note=data.get("note"),
    )


def operation_to_data(operation: Operation) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": operation.id,
        "op": operation.op,
        "in": list(operation.inputs),
        "out": list(operation.outputs),
        "params": dict(operation.params),
    }
    if operation.solver is not None:
        data["solver"] = solver_to_data(operation.solver)
    if operation.seed is not None:
        data["seed"] = operation.seed
    # Nur schreiben, wenn etwas drinsteht: Ein leeres Feld in jeder Operation
    # bläht die Datei und sagt nichts. Die meisten Zuordnungen sind eindeutig
    # und stellen nie eine Frage.
    if operation.matches:
        data["matches"] = {name: dict(entry) for name, entry in operation.matches.items()}
    # Nur schreiben, wo etwas steht: Der Normalfall ist ein Name, den jemand
    # selbst getippt hat, und der ist wörtlich gemeint.
    if operation.translatable:
        data["translatable"] = list(operation.translatable)
    return data


def operation_from_data(data: dict[str, Any]) -> Operation:
    return Operation(
        id=int(data["id"]),
        op=data["op"],
        inputs=tuple(data.get("in", ())),
        outputs=tuple(data.get("out", ())),
        params=dict(data.get("params", {})),
        solver=solver_from_data(data.get("solver")),
        seed=data.get("seed"),
        matches={name: dict(entry) for name, entry in data.get("matches", {}).items()},
        translatable=tuple(data.get("translatable", ())),
    )


# --- Prüfbericht ----------------------------------------------------------------


def finding_to_data(finding: Finding) -> dict[str, Any]:
    """Ein Befund als Daten — **mit der Message-ID, nicht mit ihrer Übersetzung.**

    Hier stand ``str(finding.message)``, und das löst sofort auf: in der
    Sprache, die beim **Erzeugen** aktiv war. :func:`finding_from_data` las die
    Zeichenkette danach als rohen ``str`` zurück, und ab da war sie eingefroren.

    **Gemeldet von Robert am 23.08.2026, an zwei Sätzen aus dem Prüfbericht:**
    ``Ausgehöhlt. Die Wandstärke stimmt im Rahmen des Rasters.`` und
    ``Deckel erzeugt — das Spiel kommt aus dem Materialprofil.`` Beide sind in
    allen fünf Sprachen übersetzt; der Kunde las sie trotzdem deutsch.

    **Warum ausgerechnet diese zwei:** Aushöhlen und Deckelerzeugen sind teuer,
    ihre Ergebnisse liegen im Plattencache. Die mitgelieferten Beispiele sind
    auf Deutsch erzeugt worden — also trug der Cache deutschen Text, und jede
    Sprache bekam ihn.

    Dasselbe Muster wie :func:`transaction_to_data` über dem Titel und
    ``_name_to_data`` in ``scene/cache.py`` über dem Objektnamen. Diese eine
    Stelle war durchgerutscht, und der Kommentar an ``_name_to_data`` beschreibt
    sie wortwörtlich: **ein Fehler, den nur ein warmer Cache zeigt** — in der
    Suite läuft jeder Test kalt.

    Was ein Aufrufer als schlichte Zeichenkette übergibt, bleibt eine.
    """
    message = finding.message
    return _without_none(
        {
            "code": finding.code,
            "severity": finding.severity,
            "message": message.msgid if isinstance(message, TranslatableText) else str(message),
            "message_translatable": True if isinstance(message, TranslatableText) else None,
            "message_context": message.context if isinstance(message, TranslatableText) else None,
            "object_id": finding.object_id,
            "op_id": finding.op_id,
            "feature_ids": list(finding.feature_ids) or None,
            "values": dict(finding.values) or None,
            "location": list(finding.location) if finding.location else None,
            "source": finding.source,
            "suggestions": [
                _without_none(
                    {
                        "id": action.id,
                        "label": (
                            action.label.msgid
                            if isinstance(action.label, TranslatableText)
                            else str(action.label)
                        ),
                        "label_translatable": (
                            True if isinstance(action.label, TranslatableText) else None
                        ),
                        "label_context": (
                            action.label.context
                            if isinstance(action.label, TranslatableText)
                            else None
                        ),
                        "primary": True if action.primary else None,
                    }
                )
                for action in finding.suggestions
            ]
            or None,
        }
    )


def finding_from_data(data: dict[str, Any]) -> Finding:
    location = data.get("location")
    message: TranslatableText | str = data.get("message", "")
    if data.get("message_translatable"):
        message = TranslatableText(str(message), data.get("message_context"))
    suggestions: list[Action] = []
    for entry in data.get("suggestions", ()):
        label: TranslatableText | str = entry.get("label", "")
        if entry.get("label_translatable"):
            label = TranslatableText(str(label), entry.get("label_context"))
        suggestions.append(
            Action(
                id=str(entry.get("id", "")),
                label=label,
                primary=bool(entry.get("primary", False)),
            )
        )
    return Finding(
        code=data["code"],
        severity=data.get("severity", "info"),
        message=message,
        object_id=data.get("object_id"),
        op_id=data.get("op_id"),
        feature_ids=tuple(data.get("feature_ids", ())),
        values=data.get("values", {}),
        location=(location[0], location[1], location[2]) if location else None,
        source=data.get("source", "internal"),
        suggestions=tuple(suggestions),
    )


def report_to_data(report: Report) -> dict[str, Any]:
    return {"findings": [finding_to_data(entry) for entry in report.findings]}


def report_from_data(data: dict[str, Any]) -> Report:
    return Report(tuple(finding_from_data(entry) for entry in data.get("findings", ())))


# --- Dokument -------------------------------------------------------------------


#: Die Gruppen von :class:`PrintSettings` und ihre Klassen. Gelesen wird über
#: die Felder der Dataclass, nicht über eine zweite Liste von Namen: eine neue
#: Einstellung soll gespeichert werden, ohne dass jemand hier daran denkt.
_SETTING_GROUPS: Final[dict[str, type]] = {
    "layers": LayerSettings,
    "shell": ShellSettings,
    "infill": InfillSettings,
    "temperature": TemperatureSettings,
    "cooling": CoolingSettings,
    "speed": SpeedSettings,
    "support": SupportSettings,
    "adhesion": AdhesionSettings,
    "retraction": RetractionSettings,
    "filament": FilamentSettings,
}


#: Die Gruppen, die ein Slot übersteuern darf — was an der Spule hängt.
#: Geometrie steht nicht dabei: Wandstärke und Schichthöhe sind Eigenschaften
#: des Teils, nicht des Materials (§20).
_OVERRIDE_GROUPS = {
    "temperature": TemperatureSettings,
    "cooling": CoolingSettings,
    "retraction": RetractionSettings,
    "filament": FilamentSettings,
}


def _override_to_data(override: SlotOverride | None) -> dict[str, Any] | None:
    """Ein Slot-Übersteuerer als Schlüssel und Werte, oder ``None``."""
    if override is None or override.empty:
        return None
    # Verzögert, weil ``cache.py`` seinerseits von hier importiert: Ein
    # Modulimport oben schlösse den Kreis, und ``core`` liesse sich nicht mehr
    # laden. Dieselben zwei Funktionen halten den Slotnamen im Cache.
    from app.core.scene.cache import _name_to_data

    # Die Identität zuerst: Ohne sie fände der Übersteuerer sein Filament
    # beim nächsten Öffnen nicht wieder, und die Werte lägen auf der
    # Spule, die zufällig an derselben Stelle steht.
    data: dict[str, Any] = {
        "name": _name_to_data(override.name),
        "colour": list(override.colour) if override.colour is not None else None,
    }
    for group in _OVERRIDE_GROUPS:
        section = getattr(override, group)
        if section is not None:
            data[group] = {entry.name: getattr(section, entry.name) for entry in fields(section)}
    return data


def _override_from_data(data: Any) -> SlotOverride | None:
    """Zurück aus der Projektdatei — unbekannte Schlüssel fallen weg.

    Dieselbe Nachsicht wie bei den Einstellungen selbst: Eine Datei aus einer
    späteren Fassung kann ein Feld tragen, das es hier noch nicht gibt, und
    das Projekt öffnet trotzdem.
    """
    if not isinstance(data, dict):
        return None
    groups: dict[str, Any] = {}
    for group, klass in _OVERRIDE_GROUPS.items():
        stored = data.get(group)
        if not isinstance(stored, dict):
            continue
        known = {entry.name for entry in fields(klass)}
        groups[group] = klass(**{key: value for key, value in stored.items() if key in known})
    if not groups:
        return None
    from app.core.scene.cache import _name_from_data

    colour = data.get("colour")
    return SlotOverride(
        name=_name_from_data(data.get("name", "")),
        colour=tuple(float(one) for one in colour)  # type: ignore[arg-type]
        if isinstance(colour, (list, tuple)) and len(colour) == 3
        else None,
        **groups,
    )


def print_settings_to_data(settings: PrintSettings) -> dict[str, Any]:
    """Die Druckeinstellungen als Schlüssel und Werte (§29)."""
    data: dict[str, Any] = {
        "id": settings.id,
        "title": settings.title,
        "quality": settings.quality,
        # Die Übergabeart (§29): „je Projekt gemerkt" heißt, sie reist hier
        # mit. Ein älterer Leser übergeht den Schlüssel, ein älterer
        # Schreiber lässt ihn weg — beides landet auf „slice", dem
        # bisherigen einzigen Weg.
        "handover": settings.handover,
        # Die Zuordnung Slot zu Filament (§20). Als Liste, weil JSON kein
        # Tupel kennt — beim Lesen wird wieder eines daraus.
        "slot_profiles": list(settings.slot_profiles),
        # Was je Slot anders gilt (§20). Geschrieben werden nur die
        # gesetzten Gruppen: Ein Slot ohne eigene Werte steht als
        # ``null`` da und nicht als vier leere Objekte, die vortäuschen,
        # dass jemand etwas eingestellt hätte.
        "slot_overrides": [_override_to_data(one) for one in settings.slot_overrides],
    }
    for group in _SETTING_GROUPS:
        section = getattr(settings, group)
        data[group] = {entry.name: getattr(section, entry.name) for entry in fields(section)}
    return data


def print_settings_from_data(data: dict[str, Any]) -> PrintSettings:
    """Zurück aus der Projektdatei.

    Was in der Datei fehlt, bleibt auf der Vorgabe der Dataclass — eine ältere
    Datei kennt eine später hinzugekommene Einstellung nicht, und das ist kein
    Fehler, sondern der Normalfall beim Öffnen.
    """
    groups: dict[str, Any] = {}
    for group, klass in _SETTING_GROUPS.items():
        stored = data.get(group, {})
        known = {entry.name for entry in fields(klass)}
        groups[group] = klass(**{key: value for key, value in stored.items() if key in known})
    return PrintSettings(
        id=str(data.get("id", "standard")),
        title=str(data.get("title", "")),
        quality=data.get("quality", "standard"),
        # Nur die zwei bekannten Arten: Was eine fremde oder künftige Datei
        # sonst hineinschreibt, fällt auf „slice" zurück, statt als
        # unbekannter Wert bis in die Knopfleiste zu reisen.
        handover="open" if data.get("handover") == "open" else "slice",
        slot_profiles=tuple(str(one) for one in data.get("slot_profiles", ())),
        slot_overrides=tuple(_override_from_data(one) for one in data.get("slot_overrides", ())),
        **groups,
    )


def document_to_data(document: Document) -> dict[str, Any]:
    return {
        "format_version": document.format_version,
        "app_version": document.app_version,
        "libs": dict(document.libs),
        "parts_version": document.parts_version,
        "scene": {"printer": document.printer, "material": document.material},
        "parameters": {
            name: parameter_to_data(parameter) for name, parameter in document.parameters.items()
        },
        "sources": {
            source_id: source_to_data(source) for source_id, source in document.sources.items()
        },
        "fits": [fit_to_data(entry) for entry in document.fits],
        "transactions": [transaction_to_data(entry) for entry in document.transactions],
        "ops": [operation_to_data(entry) for entry in document.ops],
        "chat": [chat_to_data(entry) for entry in document.chat],
        # Die Wasserlinie der Nummernvergabe (§15.4). Additiv und optional:
        # Fehlt sie, zählt der Verlauf aus dem Bestand — die Begründung, warum
        # das ohne Schritt in der Formatkette geht, steht bei
        # ``Document.highest_transaction``.
        "numbering": {
            "transaction": document.highest_transaction,
            "op": document.highest_op,
            "object": document.highest_object,
        },
        "print_settings": (
            None
            if document.print_settings is None
            else print_settings_to_data(document.print_settings)
        ),
    }


def document_from_data(data: dict[str, Any]) -> Document:
    scene = data.get("scene", {})
    numbering = data.get("numbering", {})
    return Document(
        format_version=int(data["format_version"]),
        app_version=data.get("app_version", ""),
        libs=dict(data.get("libs", {})),
        parts_version=str(data.get("parts_version", "0")),
        printer=scene.get("printer", ""),
        material=scene.get("material", ""),
        parameters={
            name: parameter_from_data(name, entry)
            for name, entry in data.get("parameters", {}).items()
        },
        sources={
            source_id: source_from_data(source_id, entry)
            for source_id, entry in data.get("sources", {}).items()
        },
        fits=[fit_from_data(entry) for entry in data.get("fits", ())],
        transactions=[transaction_from_data(entry) for entry in data.get("transactions", ())],
        ops=[operation_from_data(entry) for entry in data.get("ops", ())],
        chat=[chat_from_data(entry) for entry in data.get("chat", ())],
        # Fehlt der Eintrag, bleibt die Wasserlinie auf null: eine Datei ohne
        # dieses Feld zählt aus ihrem Bestand, und der trägt jede Nummer, auf
        # die noch etwas zeigt.
        highest_transaction=int(numbering.get("transaction", 0)),
        highest_op=int(numbering.get("op", 0)),
        highest_object=int(numbering.get("object", 0)),
        print_settings=(
            print_settings_from_data(stored)
            if isinstance(stored := data.get("print_settings"), dict)
            else None
        ),
    )
