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
from app.core.agent.analysis import ANALYSIS_KINDS, analysis_text
from app.core.agent.context import build_messages
from app.core.agent.prompt import PROMPT_VERSION
from app.core.agent.proposal import Proposal, Question
from app.core.agent.tools import (
    ADD_FIT,
    ADD_PARAMETER,
    ASK_USER,
    FIND_PART,
    OBJECTS_FIELD,
    READ_ANALYSIS,
    READ_DIGEST,
    READ_REPORT,
    READ_STANDARD,
    SET_PARAMETER,
    SET_PRINT_TARGET,
    STANDARD_KINDS,
    UNDO_TRANSACTION,
    tool_schemas,
)
from app.core.backends.llm import LLMBackend, Message, ToolCall
from app.core.errors import AppError, UserError
from app.core.knowledge import rules
from app.core.log import get_logger
from app.core.perceive.digest import digest, new_feature_lines
from app.core.registry import GATHERED_KINDS, REGISTRY, Registry, validate
from app.core.scene.evaluate import EvaluationResult, evaluate
from app.core.scene.history import History, OperationDraft
from app.core.types import (
    FIT_KINDS,
    CancelToken,
    Document,
    FeatureRef,
    Finding,
    Fit,
    FitKind,
    ObjectId,
    Origin,
    Parameter,
    Profile,
    Scene,
    SourceAccess,
)
from app.i18n import _, tr

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


#: Unter so vielen Rest-Token geht keine Anfrage mehr hinaus: die Antwort
#: würde mitten in einem Werkzeugaufruf abgeschnitten, und ein halber
#: JSON-Block ist ein eigener Fehlerfall statt eines sauberen Halts.
MIN_ANSWER_TOKENS = 512


def _refuse(question: str, options: list[str]) -> str:
    """Ohne jemanden zum Fragen lässt sich eine mehrdeutige Anfrage nicht
    beantworten.

    Der Satz kommt über ``_`` und nicht über ``tr``: Er wird zu einem
    Fehlertext, und den zeigt die Oberfläche unter Umständen erst später und
    in einer Sprache, die beim Werfen noch nicht feststand (§33.1). ``tr``
    übersetzt sofort und friert die Sprache dieses Augenblicks ein.
    """
    raise AppError(_("Für diese Rückfrage ist niemand da."), detail=question)


def _gathered_refusal(kind: str) -> str:
    """Warum ein gesammelter Parameter abgelehnt wird — je Art ein eigener Satz.

    Ein gemeinsamer Satz taugt hier nicht: Wohin der Nutzer geschickt wird, ist
    bei jeder der drei Arten eine andere Stelle — Grundformen, Pinsel,
    Skeletteditor. Eine Ablehnung ohne diesen Zusatz erzeugt einen zweiten
    Versuch, keinen besseren.

    **Beim Skelett sind es beide Felder**, `armature` *und* `pose`. Der
    naheliegende Satz „die Winkel kannst du danach angeben" stand hier schon
    und war falsch: Die Stellung trägt dieselbe Art und ist damit genauso
    gesperrt. Sie ist auch kein Zahlenfeld, sondern drei Winkel je Knochen in
    einem Text — geraten von einem Modell, das das Skelett nicht sieht, ergäbe
    er eine Haltung zu Knochen, die es nicht gibt.
    """
    if kind == "strokes":
        return tr("Pinselstriche setzt der Nutzer selbst — beschreibe ihm, wo er ansetzen soll.")
    if kind == "armature":
        return tr("Skelett und Stellung setzt der Nutzer selbst — im Skeletteditor und im Dialog.")
    return tr("Skizzen zeichnet der Nutzer selbst — benutze die Grundformen und Maße.")


def _truncation_finding(had_calls: bool) -> Finding:
    """Die Antwort brach mitten ab (:data:`~app.core.backends.llm.TRUNCATED_STOPS`).

    Ausgeführt wird von diesem Schritt nichts mehr: Was abgeschnitten ist, ist
    auch der letzte Werkzeugaufruf, und ein halb übertragener Aufruf mit halben
    Zahlen ist schlimmer als keiner. Der Vorschlag zeigt den Stand bis hierhin
    — dieselbe Zusage wie bei der Schritt- und der Tokengrenze (§26.5).
    """
    return Finding(
        code="agent.answer_truncated",
        severity="warning",
        message=_(
            "Die Antwort des Modells brach mitten ab — sie war länger als das, "
            "was das Modell je Schritt ausgeben darf. Der Vorschlag zeigt den "
            "Stand bis hierhin; eine kürzere Anweisung oder ein kleinerer "
            "Schritt kommt durch."
        ),
        values={"dropped_call": "yes" if had_calls else "no"},
    )


def _refusal_finding() -> Finding:
    """Das Modell hat die Antwort verweigert
    (:data:`~app.core.backends.llm.REFUSAL_STOPS`).

    Ohne diesen Befund war das von „nichts zu tun gefunden" nicht zu
    unterscheiden: kein Text, kein Aufruf, keine Meldung — und ein Nutzer, der
    denselben Satz noch einmal schickt.
    """
    return Finding(
        code="agent.answer_refused",
        severity="warning",
        message=_(
            "Das Modell hat diese Anfrage abgelehnt und nicht geantwortet. Eine "
            "andere Formulierung oder ein anderes Modell führt weiter — an der "
            "Anwendung liegt es nicht."
        ),
    )


def _unknown_objects(wanted: tuple[str, ...], scene: Scene) -> str:
    """Eine Meldung, wenn genannte Objekt-IDs nicht existieren — sonst leer.

    Ohne sie war „obj_9" nicht von „Objekt ist weg" zu unterscheiden: der
    Steckbrief kam schlicht ohne Objektzeilen zurück, und das Modell erfuhr
    nie, dass seine ID falsch war.
    """
    missing = [entry for entry in wanted if entry not in scene.objects]
    if not missing:
        return ""
    known = ", ".join(scene.objects) or tr("keine")
    return f"{tr('Diese Objekte gibt es nicht')}: {', '.join(missing)}. {tr('Vorhanden')}: {known}"


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
    views: tuple[tuple[str, bytes], ...] = ()
    """Gerenderte Ansichten der Szene (§23), beschriftete PNG-Bilder. Sie
    erreichen nur ein Backend mit ``supports_images`` — der Textpfad bleibt
    vollständig, Bilder sind Zugabe (Leitprinzip 8)."""

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
            request,
            working,
            scene,
            selection=self.selection,
            rule_set=active,
            views=self.views if self.backend.supports_images else (),
        )
        # Ein lokales Modell bekommt dieselben Werkzeuge, nur knapper
        # beschrieben. Gemessen: qwen3:14b traf drei von fünf und brauchte für
        # einen einzigen Aufruf bis zu zwei Minuten — damals bei 88 Werkzeugen
        # mit 104 KB Schema. Inzwischen sind es 96 mit 110 KB, kompakt 87: die
        # Enge ist gewachsen, nicht geschrumpft. Was fehlt, ist nicht Können,
        # sondern Platz.
        tools = list(tool_schemas(self.registry, compact=self.backend.id == "ollama"))

        while True:
            if self.cancelled is not None:
                self.cancelled.raise_if_cancelled()
            self._progress(proposal.steps + 1, tr("Das Modell antwortet …"))
            # §26.5: das Zugbudget deckelt auch die einzelne Antwort — was vom
            # Budget übrig ist, ist das Meiste, das dieser Schritt noch
            # ausgeben darf.
            remaining = self.max_tokens - (proposal.input_tokens + proposal.output_tokens)
            if remaining < MIN_ANSWER_TOKENS:
                proposal.stopped = "tokens"
                break
            reply = self.backend.complete(
                messages, tools, temperature=self.temperature, max_output_tokens=remaining
            )
            proposal.steps += 1
            # Beide Zahlen kommen aus der Antwort und nicht aus einer eigenen
            # Schätzung; ``Reply.input_tokens`` zählt seit dem 25.08.2026 auch
            # die zwischengespeicherten Eingabe-Token (§26.5) — sonst maß der
            # Deckel den kleinsten Teil eines Zuges.
            proposal.input_tokens += reply.input_tokens
            proposal.output_tokens += reply.output_tokens
            if reply.text:
                proposal.answer = reply.text

            # **``stop_reason`` wurde gespeichert und nie gelesen.** Zwei
            # Gründe verschwanden damit lautlos: eine abgeschnittene Antwort
            # galt als vollständige — samt halbem Werkzeugaufruf, den
            # auszuführen niemand verantworten kann —, und eine Verweigerung
            # des Modells sah aus wie ein Zug, der nichts zu tun fand. Beide
            # sagen es jetzt, und beide sagen, was hilft (Regel 17).
            if reply.refused:
                proposal.stopped = "refused"
                proposal.findings.append(_refusal_finding())
                break
            if reply.truncated:
                proposal.stopped = "truncated"
                proposal.findings.append(_truncation_finding(bool(reply.tool_calls)))
                break

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

        # §40: die Suite misst über ``readings``, ob eine Frage nachgesehen
        # oder geraten wurde. Eingetragen wird erst NACH der Prüfung des
        # jeweiligen Zweigs — ein abgelehnter Aufruf hat nichts gelesen.
        if name == ASK_USER:
            return self._ask_user(arguments, proposal), scene
        if name == READ_REPORT:
            proposal.readings.append(name)
            return report_text(scene, arguments.get("severity")), scene
        if name == FIND_PART:
            proposal.readings.append(name)
            return find_part_text(arguments.get("description", "")), scene
        if name == READ_DIGEST:
            # Der Steckbrief der Arbeitskopie — mit allem, was die bisherigen
            # Schritte dieses Zuges erzeugt haben (Konzept Agent-Vertiefung 3.1).
            wanted = tuple(str(entry) for entry in arguments.get(OBJECTS_FIELD, ()) or ())
            unknown = _unknown_objects(wanted, scene)
            if unknown:
                proposal.invalid_calls += 1
                return unknown, scene
            proposal.readings.append(name)
            return digest(scene, working, self.selection, only=wanted or None), scene
        if name == READ_STANDARD:
            return self._standard(arguments, proposal), scene
        if name == READ_ANALYSIS:
            return self._analysis(arguments, proposal, working, scene), scene
        if name == UNDO_TRANSACTION:
            return self._undo(arguments, proposal, working), scene
        if proposal.undo_of is not None:
            # Die Annahme lehnt die Mischung ohnehin ab (§15.4, Regel 16);
            # hier erfährt es das Modell früh genug, um sie gar nicht erst zu
            # bauen — und in Worten, aus denen der nächste Zug folgt. Der
            # Aufruf zählt als ungültig: die Mechanik lehnt ihn ab, bevor
            # gerechnet wird.
            proposal.invalid_calls += 1
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
        if name == SET_PRINT_TARGET:
            return self._print_target(arguments, proposal, working), scene
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
        """Eine Transaktion zum Zurücknehmen vormerken — mit dem, was mitgeht.

        Drei Schranken, und jede hat ihren eigenen Grund:

        * **Eine unbekannte Kennung** ist ein Fehlgriff des Modells.
        * **Ein zweiter Aufruf** überschrieb den ersten wortlos: Der Vorschlag
          trägt genau ein ``undo_of``, und das Modell erfuhr nie, dass seine
          erste Rücknahme verschwunden war. Was zwei Transaktionen zurücknehmen
          soll, sind zwei Vorschläge (Regel 16).
        * **Zurücknehmen und Anlegen** gehören nicht in denselben Zug (§15.4).

        Und die Antwort sagt, was wirklich geschieht: Undo ist ein Stapel, eine
        Transaktion aus der Mitte nimmt jede jüngere mit
        (:func:`~app.core.agent.apply.sweep_for`). Das Modell soll das in
        seinem Antwortsatz nennen können, statt es dem Nutzer zu verschweigen.
        """
        from app.core.agent.apply import sweep_for, undo_finding

        wanted = str(arguments.get("transaction", ""))
        sweep = sweep_for(working, wanted)
        if not sweep:
            proposal.invalid_calls += 1
            return f"{tr('Diese Transaktion gibt es nicht')}: {wanted}"
        if proposal.undo_of is not None:
            proposal.invalid_calls += 1
            return (
                f"{tr('Dieser Vorschlag nimmt schon eine Transaktion zurück')}: "
                f"{proposal.undo_of}. "
                + tr(
                    "Ein Vorschlag nimmt genau eine zurück — für eine weitere "
                    "gehört ein eigener Zug her."
                )
            )
        if proposal.creates_something:
            # Andere Richtung derselben Schranke aus ``_run`` (§15.4, Regel 16):
            # was schon angelegt ist, ließe sich nach einem Undo nicht mehr
            # vollständig zurücknehmen.
            proposal.invalid_calls += 1
            return tr(
                "Dieser Vorschlag legt bereits etwas an. Zurücknehmen gehört in "
                "einen eigenen Vorschlag — erst diesen abschließen, dann zurücknehmen."
            )
        proposal.undo_of = wanted
        proposal.undo_sweeps = sweep
        proposal.findings.append(undo_finding(sweep))
        if len(sweep) > 1:
            return (
                f"{tr('Zum Zurücknehmen vorgemerkt')}: {wanted}. "
                + tr(
                    "Sie liegt nicht zuoberst — der Verlauf kennt keine "
                    "Verzweigungen, also gehen alle jüngeren mit zurück"
                )
                + f": {', '.join(sweep)}. "
                + tr("Sage das in deiner Antwort, bevor der Nutzer entscheidet.")
            )
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
            value = parse_number(arguments.get("value", 0.0))
        except ValueError as error:
            proposal.invalid_calls += 1
            return str(error)

        parameter = Parameter(
            name=key,
            value=value,
            unit=str(arguments.get("unit", existing.unit if existing else "mm")),
            title=str(arguments.get("title", existing.title if existing else "")),
        )
        proposal.parameters[key] = parameter
        working.parameters[key] = parameter
        # Der Steckbrief liest die ausgewertete Szene, und die entsteht erst
        # mit der nächsten Operation — ohne den Zusatz meldete genau die
        # Prüfschleife „setzen, nachsehen" einen Misserfolg.
        return f"{tr('Parameter gesetzt')}: {key} = {parameter.value:g} {parameter.unit} — " + tr(
            "im Steckbrief sichtbar ab der nächsten Operation."
        )

    def _analysis(
        self, arguments: dict[str, Any], proposal: Proposal, working: Document, scene: Scene
    ) -> str:
        """§26.2: Analysen lesbar machen — auf der Arbeitskopie, nur lesend."""
        kind = str(arguments.get("kind", ""))
        if kind not in ANALYSIS_KINDS:
            proposal.invalid_calls += 1
            return f"{tr('Diese Analyse gibt es nicht')}: {kind} ({', '.join(ANALYSIS_KINDS)})"
        wanted = tuple(str(entry) for entry in arguments.get(OBJECTS_FIELD, ()) or ())
        unknown = _unknown_objects(wanted, scene)
        if unknown:
            proposal.invalid_calls += 1
            return unknown
        proposal.readings.append(READ_ANALYSIS)
        return analysis_text(
            kind, scene, working, self.profile, objects=wanted, cancelled=self.cancelled
        )

    def _print_target(
        self, arguments: dict[str, Any], proposal: Proposal, working: Document
    ) -> str:
        """Drucker oder Material des Projekts wechseln (§12, §15.5).

        Beides reist als ``DocumentChange`` in der Transaktion des Vorschlags
        — ein Undo nimmt es mit zurück (Regel 16). Das Profil der Sitzung
        zieht sofort mit: sonst widersprechen sich zwei Antworten desselben
        Zuges — der Steckbrief nennte weiter das alte Material, und
        ``read_analysis`` rechnete mit der alten Düse. Die Verweis-Toleranzen
        (`auto:<material>`) lösen sich damit schon im Zug richtig um
        (Regel 7).
        """
        from app.core.knowledge import profiles

        wanted_printer = str(arguments.get("printer", "")).strip() or working.printer
        wanted_material = str(arguments.get("material", "")).strip() or working.material
        try:
            profiles.printer(wanted_printer)
            profiles.material(wanted_material)
        except AppError as error:
            proposal.invalid_calls += 1
            return f"{error.title} {error.detail or ''}".strip()
        if (wanted_printer, wanted_material) == (working.printer, working.material):
            return tr("Drucker und Material sind schon so eingestellt.")
        working.printer = wanted_printer
        working.material = wanted_material
        self.profile = profiles.make_profile(wanted_printer, wanted_material)
        proposal.print_target = (wanted_printer, wanted_material)
        return f"{tr('Druckziel geändert')}: {wanted_printer} / {wanted_material} — " + tr(
            "gilt mit der Übernahme des Vorschlags."
        )

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
        proposal.readings.append(READ_STANDARD)
        return standard_text(kind, str(arguments.get("size", "")).strip())

    def _fit(self, arguments: dict[str, Any], proposal: Proposal, working: Document) -> str:
        try:
            fit = build_fit(arguments, self.profile.material.id, len(working.fits))
        except ValueError as error:
            proposal.invalid_calls += 1
            return str(error)
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
        gathered = next(
            (
                entry
                for entry in spec.params.spec()
                if entry.kind in GATHERED_KINDS and arguments.get(entry.name)
            ),
            None,
        )
        if gathered is not None:
            # §26, Leitprinzip 5: Was aus Gesten entsteht, entsteht beim
            # Nutzer — nie als rohe Koordinatenliste aus dem Modell. Das
            # Schema bietet diese Parameter nicht an, und hier werden sie auch
            # abgelehnt, wenn ein Modell sie rät. Die Ablehnung nennt den Weg,
            # der offen bleibt: sonst versucht es dieselbe Operation noch
            # dreimal mit anderen Zahlen.
            proposal.invalid_calls += 1
            return _gathered_refusal(gathered.kind), scene
        try:
            # Abnahme P4: schemagültig, bevor überhaupt gerechnet wird.
            validate(spec.params, arguments)
        except AppError as error:
            proposal.invalid_calls += 1
            return f"{tr('Ungültige Werte')}: {_error_text(error)}", scene

        before = scene
        draft = OperationDraft(op=spec.name, inputs=inputs, params=arguments)
        try:
            history.apply(spec.title, [draft])
        except AppError as error:
            # Ein Bedienfehler ist ein Aufruf, den das Modell hätte vermeiden
            # können — er zählt wie ein ungültiger. Ein `GeometryError` nicht:
            # dass eine Boolesche Operation an der Geometrie scheitert, ist ein
            # Ergebnis der Rechnung und kein Fehlgriff des Aufrufers.
            #
            # Ohne diese Zeile unterschlug die Messung genau die häufigste
            # Klasse: `sketch_pocket` ohne das Pflichtfeld ``objects`` lief hier
            # hindurch, und der Läufer meldete „0 ungültig" zu einem Zug, in dem
            # nichts angewandt wurde.
            if isinstance(error, UserError):
                proposal.invalid_calls += 1
            return f"{tr('Nicht anwendbar')}: {_error_text(error)}", scene

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
            READ_ANALYSIS: tr("Rechnet eine Analyse"),
            SET_PRINT_TARGET: tr("Wechselt Drucker oder Material"),
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


def report_text(scene: Scene, severity: str | None) -> str:
    """Der Prüfbericht als Text — für Sitzung und Fernsteuerung dieselbe
    Funktion (Konzept Agent-Vertiefung 2.4).

    ``severity`` heißt „ab dieser Schwere", nicht „genau diese": so steht es
    im Werkzeugschema. Die Fernsteuerung filterte exakt und lieferte auf
    ``warning`` keine Fehler — dieselbe Frage, zwei Antworten, je nachdem,
    woher sie kam.
    """
    wanted = {"info", "warning", "error"} if not severity else _from(severity)
    findings = [entry for entry in scene.report.findings if entry.severity in wanted]
    if not findings:
        return tr("Keine Befunde.")
    return "\n".join(f"{entry.severity}: {entry.code}: {entry.message}" for entry in findings)


def parse_number(value: Any) -> float:
    """Eine Zahl aus einem Werkzeugargument — oder ein ``ValueError``, dessen
    Text direkt als Antwort taugt.

    Für Sitzung und Fernsteuerung dieselbe Prüfung (Konzept 2.4): die
    Fernsteuerung rief ``float()`` ungeprüft, und ein „abc" als Wert war dort
    ein Programmfehler statt einer Meldung.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{tr('Dieser Wert ist keine Zahl')}: {value!r}") from None
    if not isfinite(number):
        raise ValueError(f"{tr('Dieser Wert ist keine endliche Zahl')}: {number}")
    return number


def build_fit(arguments: dict[str, Any], material_id: str, taken: int) -> Fit:
    """Ein Passungspaar aus Werkzeugargumenten — geprüft, mit Verweis-Toleranz.

    Der Enum steht im Werkzeugschema, aber ein Schema ist eine Bitte, keine
    Zusage: eine unbekannte Art landete sonst in der Projektdatei und erst
    bei der nächsten Auswertung als KeyError. Sitzung und Fernsteuerung
    bauten diesen Fit je einmal — jetzt einmal hier (Konzept 2.4).
    """
    try:
        first = FeatureRef.parse(str(arguments.get("a", "")))
        second = FeatureRef.parse(str(arguments.get("b", "")))
    except ValueError:
        raise ValueError(tr("Ein Passungspaar braucht zwei Merkmale als obj_1:hole_2.")) from None
    kind = str(arguments.get("kind", "clearance"))
    if kind not in FIT_KINDS:
        known = ", ".join(FIT_KINDS)
        raise ValueError(f"{tr('Diese Passungsart gibt es nicht')}: {kind} ({known})")
    return Fit(
        name=str(arguments.get("name", "")) or f"fit_{taken + 1}",
        a=first,
        b=second,
        kind=cast(FitKind, kind),
        tolerance=f"auto:{material_id}",
    )


def _from(severity: str) -> set[str]:
    order = ["info", "warning", "error"]
    if severity not in order:
        return set(order)
    return set(order[order.index(severity) :])


def standard_text(kind: str, size: str) -> str:
    """Ein Normteil in einer Zeile (§24.2) — für Sitzung und Fernsteuerung.

    Nichts hier interpretiert, wie im Modul selbst: die Antwort nennt die
    Maße mit ihren Feldnamen, was ein Baustein daraus macht, bleibt beim
    Baustein. Eine unbekannte Größe nennt die bekannten, statt zu scheitern —
    für das Modell ist die Liste die nützlichere Antwort.

    Welche Arten es gibt, sagt ``standards.TABLES`` und nicht diese Datei. Die
    Zuordnung stand hier, mit einem ``getattr`` daneben — also lag das Wissen
    über die Tabellen in der Agentenschicht, und eine neunte Tabelle hätte
    zwei Dateien gebraucht.
    """
    from dataclasses import asdict

    from app.core.knowledge import standards

    table = standards.table(kind)
    if table is None:
        # Die Funktion ist öffentlich, und beide heutigen Aufrufer prüfen
        # vorher — der dritte wird es vergessen, und ein KeyError trägt
        # keinen Vorschlag (Regel 17).
        return f"{tr('Diese Tabelle gibt es nicht')}: {kind} ({', '.join(standards.TABLES)})"
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


#: Was aus einem Fehler nicht in die Antwort ans Modell gehört: der Name der
#: Operation steht schon im Aufruf, und ``constraint`` ist die Kennung der
#: Regel, nicht ihr Inhalt.
#:
#: ``field`` stand hier zuerst mit dabei — als „Schemaangabe für die
#: Oberfläche". Das war falsch, und die Messung sagte es sofort: das Modell
#: schickte `corners=0` und las „Der Wert liegt unter dem zulässigen
#: Mindestwert (minimum=3)", ohne zu erfahren, **welcher** Wert gemeint war.
#: Es korrigierte daraufhin dreimal die Tiefe. Ohne den Feldnamen ist eine
#: Grenze kein Hinweis, sondern ein Rätsel.
_SILENT_VALUES = frozenset({"op", "constraint"})


def _error_text(error: AppError) -> str:
    """Ein Fehler, wie das Modell ihn braucht — mit den Zahlen darin.

    Die Fehlertexte des Kerns tragen **keine Platzhalter**: „Die Operation
    erwartet eine andere Anzahl an Objekten" ist der ganze Satz, und was er
    meint, steht daneben in ``values`` (``expected: 1, given: 0``). Die
    Oberfläche setzt beides zusammen; die Antwort ans Modell tat es nicht und
    schickte nur Titel und Detail.

    Damit war der häufigste Fehlgriff unkorrigierbar: `sketch_pocket` ohne das
    Pflichtfeld ``objects`` bekam „erwartet eine andere Anzahl" zurück — ohne
    die Auskunft, dass eines erwartet wurde und keines kam. Das Modell rief
    danach dieselbe Operation genauso wieder auf.
    """
    parts = [str(error.title)]
    if error.detail:
        parts.append(str(error.detail))
    facts = ", ".join(
        f"{key}={value}" for key, value in error.values.items() if key not in _SILENT_VALUES
    )
    if facts:
        parts.append(f"({facts})")
    return " ".join(parts).strip()


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
