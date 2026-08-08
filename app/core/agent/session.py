"""Ein Zug des Agenten, von der Anfrage zum Vorschlag (Bauplan §26.5).

Die Schleife ist mit Absicht kurz: das Modell fragen, ausführen, worum es
gebeten hat, zurückgeben, was passiert ist, wiederholen, bis es aufhört zu
fragen. Vertrauenswürdig macht sie, was drumherum passiert.

* Operationen werden **gesammelt**, nicht auf das Dokument des Nutzers
  angewandt. Sie laufen auf einer Arbeitskopie, damit die Prüfung nach jeder
  Operation (§26.5) etwas zu prüfen hat — und das Projekt des Nutzers bleibt
  unberührt, bis er annimmt.
* Jede Operation ist **schemagültig, bevor gerechnet wird**. Ein ungültiger
  Aufruf kommt als Meldung zurück, die das Modell korrigieren kann, nicht als
  Ausnahme.
* Mehrdeutigkeit **fragt** (§26.2). Die Frage reist über denselben Rückruf
  hinaus, den auch die Operationen benutzen (§9) — die Kommandozeile fragt
  also auf der Kommandozeile, das Fenster in einem Dialog.
* Schritt- und Token-Grenzen sind **hart** (§26.5). Ein Modell, das sich im
  Kreis dreht, hält nach einer festen Zahl von Zügen an und sagt es.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, cast

from app.core import activation
from app.core.agent import checks
from app.core.agent.context import build_messages
from app.core.agent.prompt import PROMPT_VERSION
from app.core.agent.proposal import Proposal, Question
from app.core.agent.tools import (
    ADD_FIT,
    ADD_PARAMETER,
    ASK_USER,
    FIND_PART,
    OBJECTS_FIELD,
    READ_DIGEST,
    READ_REPORT,
    READ_STANDARD,
    SET_PARAMETER,
    STANDARD_KINDS,
    UNDO_TRANSACTION,
    tool_schemas,
)
from app.core.backends.llm import LLMBackend, Message, ToolCall
from app.core.errors import AppError
from app.core.knowledge import rules
from app.core.log import get_logger
from app.core.perceive.digest import digest, new_feature_lines
from app.core.registry import REGISTRY, Registry, validate
from app.core.scene.evaluate import EvaluationResult, evaluate
from app.core.scene.history import History, OperationDraft
from app.core.types import (
    FIT_KINDS,
    CancelToken,
    Document,
    FeatureRef,
    Fit,
    FitKind,
    ObjectId,
    Origin,
    Parameter,
    Profile,
    Scene,
    SourceAccess,
)
from app.i18n import tr

_log = get_logger(__name__)

#: Harte Grenzen aus §26.5. Ein Lauf, der an eine stößt, sagt an welche.
MAX_STEPS = 8
MAX_TOKENS = 120_000

AskFn = Callable[[str, list[str]], str]

ProgressFn = Callable[[int, str], None]
"""``(schritt, beschriftung)`` — was der Zug gerade tut, für die Statuszeile.

Dasselbe Muster wie ``ask``: ein Rückruf statt Qt, damit der Kern nichts vom
Fenster weiß (§7). Ohne ihn sieht der Nutzer bis zu acht Schritte lang nur
einen endlosen Balken (Konzept Agent-Vertiefung 4.1)."""


def _refuse(question: str, options: list[str]) -> str:
    """Ohne jemanden zum Fragen lässt sich eine mehrdeutige Anfrage nicht
    beantworten.
    """
    raise AppError(tr("Für diese Rückfrage ist niemand da."), detail=question)


@dataclass(slots=True)
class AgentSession:
    """Ein Gespräch gegen ein Dokument."""

    backend: LLMBackend
    document: Document
    profile: Profile
    sources: SourceAccess | None = None
    ask: AskFn = _refuse
    registry: Registry = field(default_factory=lambda: REGISTRY)
    rule_set: rules.RuleSet | None = None
    temperature: float = 0.0
    max_steps: int = MAX_STEPS
    max_tokens: int = MAX_TOKENS
    selection: tuple[ObjectId, str] | None = None
    cancelled: CancelToken | None = None
    """§15.6: ein Zug dauert zehn bis sechzig Sekunden, und so lange muss er
    sich abbrechen lassen. Geprüft wird zwischen den Schritten — mitten in
    einer Antwort des Modells gibt es keine Stelle dafür."""
    progress: ProgressFn | None = None
    """Meldet je Schritt, was gerade läuft — siehe :data:`ProgressFn`."""

    def propose(self, request: str) -> Proposal:
        """Beantwortet eine Anfrage mit einem Vorschlag. Am Dokument wird nichts
        angewandt.
        """
        # §2 C: der Chat braucht die Freischaltung — schon der Vorschlag, nicht
        # erst das Übernehmen, denn er kostet Modellaufrufe und liefert Arbeit.
        activation.require(activation.CHAT)
        active = self.rule_set or rules.load()
        proposal = Proposal(request=request, origin=self._origin(active))

        working = copy.deepcopy(self.document)
        history = History(working, self.registry)
        scene = self._evaluate(working).scene

        messages = build_messages(
            request, working, scene, selection=self.selection, rule_set=active
        )
        tools = list(tool_schemas(self.registry))

        while True:
            if self.cancelled is not None:
                self.cancelled.raise_if_cancelled()
            self._progress(proposal.steps + 1, tr("Das Modell antwortet …"))
            # §26.5: das Zugbudget deckelt auch die einzelne Antwort — was vom
            # Budget übrig ist, ist das Meiste, das dieser Schritt noch
            # ausgeben darf.
            remaining = self.max_tokens - (proposal.input_tokens + proposal.output_tokens)
            reply = self.backend.complete(
                messages, tools, temperature=self.temperature, max_output_tokens=remaining
            )
            proposal.steps += 1
            proposal.input_tokens += reply.input_tokens
            proposal.output_tokens += reply.output_tokens
            if reply.text:
                proposal.answer = reply.text

            if not reply.tool_calls:
                break

            messages.append(
                Message(role="assistant", content=reply.text, tool_calls=reply.tool_calls)
            )
            for call in reply.tool_calls:
                proposal.tool_calls += 1
                self._progress(proposal.steps, self._label_for(call.name))
                answer, scene = self._run(call, proposal, working, history, scene)
                messages.append(Message(role="tool", tool_call_id=call.id, content=answer))

            if proposal.steps >= self.max_steps:
                proposal.stopped = "steps"
                break
            if proposal.input_tokens + proposal.output_tokens >= self.max_tokens:
                proposal.stopped = "tokens"
                break

        _log.info(
            "proposal with %d operations after %d steps", len(proposal.drafts), proposal.steps
        )
        return proposal

    # --- tools ------------------------------------------------------------------

    def _run(
        self,
        call: ToolCall,
        proposal: Proposal,
        working: Document,
        history: History,
        scene: Scene,
    ) -> tuple[str, Scene]:
        """Führt einen Werkzeugaufruf aus und sagt, was passiert ist — in Worten,
        die das Modell liest.
        """
        name = call.name
        arguments = dict(call.arguments)

        if name == ASK_USER:
            return self._ask_user(arguments, proposal), scene
        if name == READ_REPORT:
            return _report_text(scene, arguments.get("severity")), scene
        if name == FIND_PART:
            return find_part_text(arguments.get("description", "")), scene
        if name == READ_DIGEST:
            # Der Steckbrief der Arbeitskopie — mit allem, was die bisherigen
            # Schritte dieses Zuges erzeugt haben (Konzept Agent-Vertiefung 3.1).
            wanted = tuple(str(entry) for entry in arguments.get(OBJECTS_FIELD, ()) or ())
            return digest(scene, working, self.selection, only=wanted or None), scene
        if name == READ_STANDARD:
            return self._standard(arguments, proposal), scene
        if name == UNDO_TRANSACTION:
            return self._undo(arguments, proposal, working), scene
        if proposal.undo_of is not None:
            # Die Annahme lehnt die Mischung ohnehin ab (§15.4, Regel 16);
            # hier erfährt es das Modell früh genug, um sie gar nicht erst zu
            # bauen — und in Worten, aus denen der nächste Zug folgt.
            return (
                tr(
                    "Dieser Vorschlag nimmt bereits eine Transaktion zurück. "
                    "Zurücknehmen und Anlegen gehören in zwei Vorschläge — "
                    "erst diesen abschließen, dann den nächsten."
                ),
                scene,
            )
        if name in (ADD_PARAMETER, SET_PARAMETER):
            return self._parameter(name, arguments, proposal, working), scene
        if name == ADD_FIT:
            return self._fit(arguments, proposal, working), scene
        return self._operation(call, proposal, working, history, scene)

    def _ask_user(self, arguments: dict[str, Any], proposal: Proposal) -> str:
        """§26.2: Fragen ist Pflicht. Die Antwort geht auch in den Vorschlag,
        damit die Oberfläche zeigen kann, was auf welcher Grundlage entschieden
        wurde.
        """
        text = str(arguments.get("question", "")).strip()
        options = [str(entry) for entry in arguments.get("options", ())]
        question = Question(text=text, options=tuple(options))
        proposal.questions.append(question)
        answer = self.ask(text, options)
        question.answer = answer
        return f"{tr('Antwort')}: {answer}"

    def _undo(self, arguments: dict[str, Any], proposal: Proposal, working: Document) -> str:
        wanted = str(arguments.get("transaction", ""))
        known = {entry.id for entry in working.transactions}
        if wanted not in known:
            proposal.invalid_calls += 1
            return f"{tr('Diese Transaktion gibt es nicht')}: {wanted}"
        if proposal.drafts or proposal.parameters or proposal.fits:
            # Andere Richtung derselben Schranke aus ``_run`` (§15.4, Regel 16):
            # was schon angelegt ist, ließe sich nach einem Undo nicht mehr
            # vollständig zurücknehmen.
            return tr(
                "Dieser Vorschlag legt bereits etwas an. Zurücknehmen gehört in "
                "einen eigenen Vorschlag — erst diesen abschließen, dann zurücknehmen."
            )
        proposal.undo_of = wanted
        return f"{tr('Zum Zurücknehmen vorgemerkt')}: {wanted}"

    def _parameter(
        self, name: str, arguments: dict[str, Any], proposal: Proposal, working: Document
    ) -> str:
        key = str(arguments.get("name", "")).strip()
        if not key:
            proposal.invalid_calls += 1
            return tr("Ein Parameter braucht einen Namen.")
        existing = working.parameters.get(key)
        if name == SET_PARAMETER and existing is None:
            proposal.invalid_calls += 1
            return f"{tr('Diesen Parameter gibt es nicht')}: {key}"

        # Diese Werkzeuge sind keine Register-Ops, ``validate`` sieht sie also
        # nie: was hier ungeprüft durchginge, wäre entweder ein ValueError im
        # Arbeiter — der ist kein AppError und ließe den Thread ohne Meldung
        # sterben — oder ein NaN, das bis in die Geometrieauswertung reist.
        try:
            value = float(arguments.get("value", 0.0))
        except (TypeError, ValueError):
            proposal.invalid_calls += 1
            return f"{tr('Dieser Wert ist keine Zahl')}: {arguments.get('value')!r}"
        if not isfinite(value):
            proposal.invalid_calls += 1
            return f"{tr('Dieser Wert ist keine endliche Zahl')}: {value}"

        parameter = Parameter(
            name=key,
            value=value,
            unit=str(arguments.get("unit", existing.unit if existing else "mm")),
            title=str(arguments.get("title", existing.title if existing else "")),
        )
        proposal.parameters[key] = parameter
        working.parameters[key] = parameter
        return f"{tr('Parameter gesetzt')}: {key} = {parameter.value:g} {parameter.unit}"

    def _standard(self, arguments: dict[str, Any], proposal: Proposal) -> str:
        """§24.2 als Werkzeug: nachschlagen statt raten.

        Eine unbekannte Tabelle ist ein Schemaverstoß gegen das Enum und
        zählt als ungültig; eine unbekannte Größe ist eine Fachauskunft —
        die Antwort nennt, was es gibt, wie ``find_part`` bei einem leeren
        Fund.
        """
        kind = str(arguments.get("kind", ""))
        if kind not in STANDARD_KINDS:
            proposal.invalid_calls += 1
            return f"{tr('Diese Tabelle gibt es nicht')}: {kind} ({', '.join(STANDARD_KINDS)})"
        return standard_text(kind, str(arguments.get("size", "")).strip())

    def _fit(self, arguments: dict[str, Any], proposal: Proposal, working: Document) -> str:
        try:
            first = FeatureRef.parse(str(arguments.get("a", "")))
            second = FeatureRef.parse(str(arguments.get("b", "")))
        except ValueError:
            proposal.invalid_calls += 1
            return tr("Ein Passungspaar braucht zwei Merkmale als obj_1:hole_2.")

        # Der Enum steht im Werkzeugschema, aber ein Schema ist eine Bitte,
        # keine Zusage: eine unbekannte Art landete sonst in der Projektdatei
        # und erst bei der nächsten Auswertung als KeyError in ``_FIT_FIELD``.
        kind = str(arguments.get("kind", "clearance"))
        if kind not in FIT_KINDS:
            proposal.invalid_calls += 1
            known = ", ".join(FIT_KINDS)
            return f"{tr('Diese Passungsart gibt es nicht')}: {kind} ({known})"

        fit = Fit(
            name=str(arguments.get("name", "")) or f"fit_{len(working.fits) + 1}",
            a=first,
            b=second,
            kind=cast(FitKind, kind),
            tolerance=f"auto:{self.profile.material.id}",
        )
        proposal.fits.append(fit)
        working.fits.append(fit)
        return f"{tr('Passung angelegt')}: {fit.name} ({fit.kind}, {fit.tolerance})"

    def _operation(
        self,
        call: ToolCall,
        proposal: Proposal,
        working: Document,
        history: History,
        scene: Scene,
    ) -> tuple[str, Scene]:
        """Eine Operation aus dem Register: validieren, auf die Kopie anwenden,
        prüfen.
        """
        try:
            spec = self.registry.get(call.name)
        except AppError:
            proposal.invalid_calls += 1
            return f"{tr('Dieses Werkzeug gibt es nicht')}: {call.name}", scene

        arguments = dict(call.arguments)
        inputs = tuple(str(entry) for entry in arguments.pop(OBJECTS_FIELD, ()) or ())
        if spec.takes_whole_scene and not inputs:
            # Anordnen wirkt auf alles (§25). Das Modell jedes Objekt aufzählen
            # zu lassen wäre eine Gelegenheit, eines zu vergessen — und die
            # Szene kennt sie.
            inputs = tuple(scene.objects)
        if any(
            entry.kind == "sketch" and arguments.get(entry.name) for entry in spec.params.spec()
        ):
            # §26, Leitprinzip 5: Skizzen entstehen beim Nutzer, nie als rohe
            # Punktliste aus dem Modell. Das Schema bietet den Parameter nicht
            # an — und hier wird er auch abgelehnt, wenn das Modell ihn rät.
            proposal.invalid_calls += 1
            return (
                tr("Skizzen zeichnet der Nutzer selbst — benutze die Grundformen und Maße."),
                scene,
            )
        try:
            # P4 acceptance: schema-valid before anything is computed.
            validate(spec.params, arguments)
        except AppError as error:
            proposal.invalid_calls += 1
            return f"{tr('Ungültige Werte')}: {error.title} {error.detail or ''}".strip(), scene

        before = scene
        draft = OperationDraft(op=spec.name, inputs=inputs, params=arguments)
        try:
            history.apply(spec.title, [draft])
        except AppError as error:
            return f"{tr('Nicht anwendbar')}: {error.title} {error.detail or ''}".strip(), scene

        result = self._evaluate(working)
        findings = checks.check(result, before)
        proposal.findings.extend(findings)

        if result.stopped_at is not None:
            # §15.2: die Kette hat angehalten, diese Operation ist also nicht
            # Teil des Vorschlags. Die Arbeitskopie geht dorthin zurück, wo sie
            # war.
            history.undo()
            return f"{tr('Die Kette hält an')}: {checks.as_lines(findings)}", before

        proposal.drafts.append(draft)

        # Konzept Agent-Vertiefung 3.1: die IDs der neuen Merkmale gehören in
        # die Antwort — sonst kennt das Modell die Bohrung nicht, die es
        # gerade gesetzt hat, und der nächste Schritt zeigt ins Leere.
        created = new_feature_lines(before, result.scene)
        return (
            f"{tr('Ausgeführt')}: {spec.name}. {checks.as_lines(findings)}\n"
            + ("\n".join(created) + "\n" if created else "")
            + f"{_objects_text(result.scene)}",
            result.scene,
        )

    # --- helpers ----------------------------------------------------------------

    def _progress(self, step: int, label: str) -> None:
        if self.progress is not None:
            self.progress(step, label)

    def _label_for(self, name: str) -> str:
        """Was in der Statuszeile steht, während dieses Werkzeug läuft."""
        extras = {
            ASK_USER: tr("Rückfrage an dich"),
            UNDO_TRANSACTION: tr("Merkt eine Rücknahme vor"),
            ADD_PARAMETER: tr("Legt einen Parameter an"),
            SET_PARAMETER: tr("Ändert einen Parameter"),
            ADD_FIT: tr("Legt eine Passung an"),
            READ_REPORT: tr("Liest den Prüfbericht"),
            FIND_PART: tr("Sucht in der Bausteinbibliothek"),
            READ_DIGEST: tr("Liest den Steckbrief"),
            READ_STANDARD: tr("Schlägt in der Normteiltabelle nach"),
        }
        if name in extras:
            return extras[name]
        try:
            return str(self.registry.get(name).title)
        except AppError:
            return name

    def _evaluate(self, document: Document) -> EvaluationResult:
        """§26.5: der Agent arbeitet in Entwurfsqualität und schaltet erst am
        Ende um.
        """
        return evaluate(
            document,
            self.profile,
            quality="draft",
            registry=self.registry,
            sources=self.sources,
            ask=lambda question, options: self.ask(question, list(options)),
        )

    def _origin(self, active: rules.RuleSet) -> Origin:
        """§26.4: unter welchen Bedingungen dieser Vorschlag zustande kam."""
        return Origin(
            by="agent",
            model=f"{self.backend.id}:{self.backend.model}",
            prompt_version=PROMPT_VERSION,
            rules_version=active.version,
            temperature=self.temperature,
        )


def _objects_text(scene: Scene) -> str:
    """Die Szene in einer Zeile — genug, damit das Modell sieht, was es getan
    hat.
    """
    if not scene.objects:
        return tr("Keine Objekte.")
    parts = []
    for object_id, entry in scene.objects.items():
        size = entry.mesh.bounds.size
        parts.append(
            f"{object_id} {size[0]:.1f}x{size[1]:.1f}x{size[2]:.1f} mm, "
            f"{entry.mesh.volume / 1000.0:.1f} cm3"
        )
    return " · ".join(parts)


def _report_text(scene: Scene, severity: str | None) -> str:
    wanted = {"info", "warning", "error"} if not severity else _from(severity)
    findings = [entry for entry in scene.report.findings if entry.severity in wanted]
    if not findings:
        return tr("Keine Befunde.")
    return "\n".join(f"{entry.severity}: {entry.code}: {entry.message}" for entry in findings)


def _from(severity: str) -> set[str]:
    order = ["info", "warning", "error"]
    if severity not in order:
        return set(order)
    return set(order[order.index(severity) :])


#: Welches Feld der Normteiltabellen zu welcher Werkzeug-Art gehört.
_STANDARD_TABLES = {
    "screw": "screws",
    "nut": "nuts",
    "washer": "washers",
    "insert": "inserts",
    "magnet": "magnets",
    "bearing": "bearings",
    "profile": "profiles",
    "tube": "tubes",
}


def standard_text(kind: str, size: str) -> str:
    """Ein Normteil in einer Zeile (§24.2) — für Sitzung und Fernsteuerung.

    Nichts hier interpretiert, wie im Modul selbst: die Antwort nennt die
    Maße mit ihren Feldnamen, was ein Baustein daraus macht, bleibt beim
    Baustein. Eine unbekannte Größe nennt die bekannten, statt zu scheitern —
    für das Modell ist die Liste die nützlichere Antwort.
    """
    from dataclasses import asdict

    from app.core.knowledge import standards

    table: dict[str, Any] = getattr(standards.load(), _STANDARD_TABLES[kind])
    entry = table.get(size) or table.get(size.upper())
    if entry is None:
        known = ", ".join(sorted(table))
        return f"{tr('Diese Größe steht nicht in der Normteiltabelle')}: {size}. {known}"
    facts = ", ".join(
        f"{key}={value:g} mm" if isinstance(value, float) else f"{key}={value}"
        for key, value in asdict(entry).items()
        if key != "size" and value
    )
    return f"{kind} {entry.size}: {facts}"


def find_part_text(description: str) -> str:
    """§26.2: in der Bibliothek nachsehen, bevor Geometrie von Hand entsteht.

    Die Antwort nennt die Operation, nicht nur den Baustein: was das Modell mit
    einem Fund tut, ist ihn aufzurufen, und einen Namen, den es raten muss,
    rät es falsch.
    """
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts.ops import op_name

    found = PARTS.search(description)
    if not found:
        return tr("Dazu gibt es keinen Baustein.")
    return "\n".join(f"{op_name(spec.name)}: {spec.title} — {spec.doc}" for spec in found[:6])
