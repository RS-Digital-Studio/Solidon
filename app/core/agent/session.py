"""One turn of the agent, from request to proposal (Bauplan §26.5).

The loop is short on purpose: ask the model, run what it asked for, hand back
what happened, repeat until it stops asking. What makes it trustworthy is what
happens around it.

* Operations are **collected**, not applied to the user's document. They run on
  a scratch copy so the check after every operation (§26.5) has something to
  check, and the user's project stays untouched until they accept.
* Every operation is **schema-valid before it is computed**. An invalid call
  comes back as a message the model can fix, not as an exception.
* Ambiguity **asks** (§26.2). The question travels out through the same callback
  the operations use (§9), so the command line asks on the command line and the
  window asks in a dialog.
* Step and token limits are **hard** (§26.5). A model that keeps going in
  circles stops after a fixed number of turns and says so.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

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
    READ_REPORT,
    SET_PARAMETER,
    UNDO_TRANSACTION,
    tool_schemas,
)
from app.core.backends.llm import LLMBackend, Message, ToolCall
from app.core.errors import AppError
from app.core.knowledge import rules
from app.core.log import get_logger
from app.core.registry import REGISTRY, Registry, validate
from app.core.scene.evaluate import EvaluationResult, evaluate
from app.core.scene.history import History, OperationDraft
from app.core.types import (
    Document,
    FeatureRef,
    Fit,
    ObjectId,
    Origin,
    Parameter,
    Profile,
    Scene,
    SourceAccess,
)
from app.i18n import tr

_log = get_logger(__name__)

#: Hard limits from §26.5. A run that hits one of them says which.
MAX_STEPS = 8
MAX_TOKENS = 120_000

AskFn = Callable[[str, list[str]], str]


def _refuse(question: str, options: list[str]) -> str:
    """Without anyone to ask, an ambiguous request cannot be answered."""
    raise AppError(tr("Für diese Rückfrage ist niemand da."), detail=question)


@dataclass(slots=True)
class AgentSession:
    """One conversation against one document."""

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

    def propose(self, request: str) -> Proposal:
        """Answer a request with a proposal. Nothing is applied to the document."""
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
            reply = self.backend.complete(messages, tools, temperature=self.temperature)
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
        """Run one tool call and say what happened, in words the model reads."""
        name = call.name
        arguments = dict(call.arguments)

        if name == ASK_USER:
            return self._ask_user(arguments, proposal), scene
        if name == UNDO_TRANSACTION:
            return self._undo(arguments, proposal, working), scene
        if name in (ADD_PARAMETER, SET_PARAMETER):
            return self._parameter(name, arguments, proposal, working), scene
        if name == ADD_FIT:
            return self._fit(arguments, proposal, working), scene
        if name == READ_REPORT:
            return _report_text(scene, arguments.get("severity")), scene
        if name == FIND_PART:
            return _find_part(arguments.get("description", "")), scene
        return self._operation(call, proposal, working, history, scene)

    def _ask_user(self, arguments: dict[str, Any], proposal: Proposal) -> str:
        """§26.2: asking is a duty. The answer goes into the proposal as well, so
        the surface can show what was decided and on what basis."""
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
            return f"{tr('Diese Transaktion gibt es nicht')}: {wanted}"
        proposal.undo_of = wanted
        return f"{tr('Zum Zurücknehmen vorgemerkt')}: {wanted}"

    def _parameter(
        self, name: str, arguments: dict[str, Any], proposal: Proposal, working: Document
    ) -> str:
        key = str(arguments.get("name", "")).strip()
        if not key:
            return tr("Ein Parameter braucht einen Namen.")
        existing = working.parameters.get(key)
        if name == SET_PARAMETER and existing is None:
            return f"{tr('Diesen Parameter gibt es nicht')}: {key}"

        parameter = Parameter(
            name=key,
            value=float(arguments.get("value", 0.0)),
            unit=str(arguments.get("unit", existing.unit if existing else "mm")),
            title=str(arguments.get("title", existing.title if existing else "")),
        )
        proposal.previous_parameters.setdefault(key, existing)
        proposal.parameters[key] = parameter
        working.parameters[key] = parameter
        return f"{tr('Parameter gesetzt')}: {key} = {parameter.value:g} {parameter.unit}"

    def _fit(self, arguments: dict[str, Any], proposal: Proposal, working: Document) -> str:
        try:
            first = FeatureRef.parse(str(arguments.get("a", "")))
            second = FeatureRef.parse(str(arguments.get("b", "")))
        except ValueError:
            return tr("Ein Passungspaar braucht zwei Merkmale als obj_1:hole_2.")

        fit = Fit(
            name=str(arguments.get("name", "")) or f"fit_{len(working.fits) + 1}",
            a=first,
            b=second,
            kind=arguments.get("kind", "clearance"),
            tolerance=f"auto:{self.profile.material.id}",
        )
        if proposal.previous_fits is None:
            proposal.previous_fits = list(working.fits)
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
        """An operation from the registry: validate, apply to the copy, check."""
        try:
            spec = self.registry.get(call.name)
        except AppError:
            return f"{tr('Dieses Werkzeug gibt es nicht')}: {call.name}", scene

        arguments = dict(call.arguments)
        inputs = tuple(str(entry) for entry in arguments.pop(OBJECTS_FIELD, ()) or ())
        try:
            # P4 acceptance: schema-valid before anything is computed.
            validate(spec.params, arguments)
        except AppError as error:
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
            # §15.2: the chain stopped, so this operation is not part of the
            # proposal. The scratch copy goes back to where it was.
            history.undo()
            return f"{tr('Die Kette hält an')}: {checks.as_lines(findings)}", before

        proposal.drafts.append(draft)

        return (
            f"{tr('Ausgeführt')}: {spec.name}. {checks.as_lines(findings)}\n"
            f"{_objects_text(result.scene)}",
            result.scene,
        )

    # --- helpers ----------------------------------------------------------------

    def _evaluate(self, document: Document) -> EvaluationResult:
        """§26.5: the agent works in draft quality and switches only at the end."""
        return evaluate(
            document,
            self.profile,
            quality="draft",
            registry=self.registry,
            sources=self.sources,
            ask=lambda question, options: self.ask(question, list(options)),
        )

    def _origin(self, active: rules.RuleSet) -> Origin:
        """§26.4: under which conditions this proposal came about."""
        return Origin(
            by="agent",
            model=f"{self.backend.id}:{self.backend.model}",
            prompt_version=PROMPT_VERSION,
            rules_version=active.version,
            temperature=self.temperature,
        )


def _objects_text(scene: Scene) -> str:
    """The scene in one line — enough for the model to see what it did."""
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


def _find_part(description: str) -> str:
    """§26.2: look in the library before building geometry by hand.

    The answer names the operation, not just the part: what the model does with
    a find is call it, and a name it has to guess at is a name it gets wrong.
    """
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts.ops import op_name

    found = PARTS.search(description)
    if not found:
        return tr("Dazu gibt es keinen Baustein.")
    return "\n".join(f"{op_name(spec.name)}: {spec.title} — {spec.doc}" for spec in found[:6])
