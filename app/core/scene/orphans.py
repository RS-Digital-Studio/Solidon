"""Merkmalsverweise, die ihr Merkmal verloren haben (Bauplan §21.3).

Bezeichner sind stabil, solange eine Sitzung läuft (§21.2) — aber eine
Projektdatei überlebt die Sitzung, in der sie entstand: das Netz wurde
ersetzt, die Operation davor bearbeitet, die Bausteinbibliothek geändert. Dann
zeigt eine Passung auf ``hole_3``, und ein ``hole_3`` gibt es nicht mehr.

Die Regel ist dieselbe, der die ganze Anwendung folgt: **nicht raten**. Jeder
Verweis einer geöffneten Datei wird einmal geprüft, und was sich nicht
auflösen lässt, wird dem Nutzer vorgelegt, die Kandidaten gleich dabei. Seine
Antwort wird ins Dokument zurückgeschrieben — die Frage kommt einmal, nicht
bei jeder Auswertung.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.log import get_logger
from app.core.registry import REGISTRY, Registry
from app.core.types import (
    Document,
    Feature,
    FeatureId,
    FeatureRef,
    Finding,
    ObjectId,
    Scene,
)
from app.i18n import _, tr

_log = get_logger(__name__)

#: Die Antwort, die die Passung streicht, statt sie woandershin zu zeigen.
REMOVE_CHOICE = "-"


@dataclass(slots=True)
class Reference:
    """Eine Stelle im Dokument, die ein Merkmal benennt."""

    where: str
    """``fit:stift_1:a`` oder ``op:7:at_feature`` — genug, um die Antwort
    zurückzuschreiben."""
    ref: FeatureRef
    index: int | None = None
    """Bei einer Merkmalliste die Position, die eine Antwort gezielt ersetzt."""
    removable: bool = True
    """Eine leere Flächenauswahl darf niemals versehentlich den ganzen Körper betreffen."""

    @property
    def kind(self) -> str:
        return self.where.split(":")[0]

    @property
    def fit_name(self) -> str:
        return self.where.split(":")[1]

    @property
    def side(self) -> str:
        return self.where.split(":")[2]

    @property
    def op_id(self) -> int:
        return int(self.where.split(":")[1])

    @property
    def field(self) -> str:
        return self.where.split(":")[2]

    @property
    def title(self) -> str:
        """Wie dieser Verweis in einer Frage oder einem Befund heißt."""
        return self.fit_name if self.kind == "fit" else f"{tr('Operation')} {self.op_id}"


@dataclass(slots=True)
class CheckResult:
    """Was die Prüfung gefunden und was sie geändert hat."""

    findings: list[Finding] = field(default_factory=list)
    rewritten: int = 0
    removed: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.rewritten or self.removed)


def references(document: Document, registry: Registry | None = None) -> list[Reference]:
    """Jeder Merkmalsverweis, den das Dokument hält.

    Die Passungen (§14), und die Operationen, die ein Merkmal benennen. Diese
    Funktion sagte früher: „Operationen tragen Koordinaten, keine Merkmal-IDs;
    sobald eine von ihnen ein Merkmal referenziert, wird sie hier
    mitaufgezählt" — und das war falsch, seit es die Bausteinbibliothek gibt:
    jeder eingefügte Baustein trägt ``at_feature``, achtzehn Operationen
    deklarieren eines, und keine davon wurde je geprüft. Eine Datei, deren
    ``hole_1`` fort war, bekam nicht die Frage aus §21.3; sie hielt an dieser
    Operation mit einem Fehler an — eine Phase nach der Phase, die das
    Gegenteil versprochen hatte.

    Welche Parameter zählen, ist deklariert, nicht am Namen geraten:
    ``kind="feature"`` stand von Anfang an im Parametervertrag und hatte
    keinen Nutzer.
    """
    found: list[Reference] = []
    for fit in document.fits:
        found.append(Reference(f"fit:{fit.name}:a", fit.a))
        found.append(Reference(f"fit:{fit.name}:b", fit.b))

    source = registry or REGISTRY
    for operation in document.ops:
        for field_name in _feature_fields(source, operation.op):
            named = str(operation.params.get(field_name) or "")
            if not named or not operation.inputs:
                continue
            # Das Merkmal gehört zu dem Objekt, auf dem die Operation arbeitet.
            found.append(
                Reference(
                    f"op:{operation.id}:{field_name}",
                    FeatureRef(operation.inputs[0], named),
                    removable=operation.op != "clear_filament",
                )
            )
        for field_name in _feature_fields(source, operation.op, multiple=True):
            names = operation.params.get(field_name, ())
            if not isinstance(names, list | tuple) or not operation.inputs:
                continue
            for index, named in enumerate(names):
                if isinstance(named, str) and named:
                    found.append(
                        Reference(
                            f"op:{operation.id}:{field_name}:{index}",
                            FeatureRef(operation.inputs[0], named),
                            index=index,
                            removable=False,
                        )
                    )
        for field_name in _sketch_fields(source, operation.op):
            plane_reference = feature_ref_of_sketch(str(operation.params.get(field_name) or ""))
            if plane_reference is None:
                continue
            # Eine Skizze auf einer Fläche benennt ein Merkmal — im
            # Skizzentext statt in einem feature-Parameter, und genau deshalb
            # sah dieser Filter sie nie: Die Datei bekam bei „Skizze auf
            # Fläche" keine §21.3-Frage. Nur alte Projekte tragen hier einen
            # leeren Objektnamen; neue Ebenen benennen ihren Körper eindeutig.
            found.append(Reference(f"plane:{operation.id}:{field_name}", plane_reference))
    return found


def lineage(document: Document) -> dict[ObjectId, frozenset[ObjectId]]:
    """Woraus jeder Körper hervorgegangen ist — die Kennungen durch den Stapel.

    Ein Verweis nennt den Körper, an dem das Merkmal **damals** hing. Teilt
    eine spätere Operation ihn, trägt nur das erste Stück seine Kennung weiter;
    der Rest bekommt frische (``History._outputs_for``). Ein Verweis auf
    ``obj_1:hole_2`` zeigte danach ins Leere, obwohl das Loch als
    ``obj_3:hole_1`` in der Szene steht — und statt der Frage aus §21.3 kam
    eine Sackgasse: „Die Schritte ab dort zurücknehmen und vor der Passung
    ausführen." Gemessen am 12.09.2026 an zwei Klötzen mit je einer Bohrung,
    nach *In Einzelteile zerlegen* (RM-023).

    Gefragt wird der **Stapel** und nicht die Szene: ``Operation.inputs`` und
    ``outputs`` bilden den DAG (§12), und daraus folgt, welcher Körper für
    welchen einstehen kann. Die Richtung ist „Nachfahre → Vorfahren", denn so
    wird gefragt: Zu einem Verweis auf ``obj_1`` gehören alle Körper, in deren
    Herkunft ``obj_1`` steht.

    **Auch die Gegenrichtung fällt darunter**, und das ist kein Versehen: Nach
    einer Vereinigung führt der Ausgang die Herkunft beider Eingänge, ein
    Verweis auf den aufgesogenen Körper findet also den, der ihn aufgenommen
    hat.
    """
    family: dict[ObjectId, frozenset[ObjectId]] = {}
    for operation in sorted(document.ops, key=lambda entry: entry.id):
        sources: set[ObjectId] = set()
        for entry in operation.inputs:
            sources |= family.get(entry, frozenset({entry}))
        for entry in operation.outputs:
            family[entry] = family.get(entry, frozenset()) | sources | {entry}
    return family


def _heirs(
    scene: Scene, object_id: ObjectId, family: Mapping[ObjectId, frozenset[ObjectId]]
) -> list[ObjectId]:
    """Die Körper der Szene, die für diesen einstehen können.

    Ohne Stammbaum ist das der Körper selbst — ein Aufrufer, der kein Dokument
    hat, bekommt das bisherige Verhalten und keine geratene Verwandtschaft.
    """
    found = [
        current
        for current in scene.objects
        if object_id in family.get(current, frozenset({current}))
    ]
    return found or ([object_id] if object_id in scene.objects else [])


def pending_references(document: Document, stopped_at: int | None) -> list[Reference]:
    """Prüft Verweise gegen den Stand, an dem sie tatsächlich gebraucht werden.

    Vor dem angehaltenen Schritt sind seine Eingänge noch vorhanden. Frühere
    Schritte wurden bereits erfolgreich aufgelöst; ihre später verbrauchten
    Körper sind keine verwaisten Verweise. Zukünftige Schritte müssen warten,
    bis ihre Eingänge erzeugt wurden. Passungen gelten erst im Endstand.
    """
    from app.core.scene.fits import active_fits

    found = references(document)
    if stopped_at is not None:
        return [entry for entry in found if entry.kind != "fit" and entry.op_id == stopped_at]
    active = {fit.name for fit in active_fits(document)}
    return [entry for entry in found if entry.kind == "fit" and entry.fit_name in active]


def _sketch_fields(registry: Registry, op_name: str) -> tuple[str, ...]:
    """Parameter dieser Operation, die eine Skizze tragen — aus der
    Deklaration, wie bei :func:`_feature_fields`."""
    if not registry.has(op_name):
        return ()
    return tuple(
        entry.name for entry in registry.get(op_name).params.spec() if entry.kind == "sketch"
    )


def face_of_sketch(text: str) -> str | None:
    """Die Fläche, auf der diese Skizze liegt — oder nichts.

    Ein unlesbarer Skizzentext ist der Fehler der Operation, nicht dieser
    Prüfung: Sie zählt Verweise auf und übergeht, was sie nicht lesen kann.
    Öffentlich, weil der Cache-Schlüssel dieselbe Frage stellt
    (``evaluate._with_nested_context``): Wer die Ebene liest, hängt vom
    Träger ab, und zwei Fassungen derselben Auskunft liefen auseinander.
    """
    reference = feature_ref_of_sketch(text)
    return reference.feature_id if reference is not None else None


def feature_ref_of_sketch(text: str) -> FeatureRef | None:
    """Die eindeutige Flächenreferenz einer Skizze lesen — oder nichts.

    Für die alte Schreibweise bleibt ``object_id`` leer. Aufrufer, die nur
    die Merkmalskennung brauchen, verwenden :func:`face_of_sketch`.
    """
    if not text:
        return None
    from app.core.sketch.planes import feature_plane_parts, is_feature_plane
    from app.core.sketch.serialize import sketch_from_text

    try:
        plane = sketch_from_text(text).plane
    except Exception:
        return None
    if not is_feature_plane(plane):
        return None
    object_id, feature_id = feature_plane_parts(plane)
    return FeatureRef(object_id, feature_id)


def _feature_fields(registry: Registry, op_name: str, *, multiple: bool = False) -> tuple[str, ...]:
    """Parameter dieser Operation, die ein Merkmal benennen — aus der
    Deklaration.

    Gefragt statt gefangen: eine Operation, die dieser Stand nicht kennt —
    eine Datei aus einer neueren Version, ein nicht geladenes Plugin — hat
    Verweise, die hier niemand auflösen kann, und die zu melden ist nicht
    Sache dieser Prüfung.
    """
    if not registry.has(op_name):
        return ()
    return tuple(
        entry.name
        for entry in registry.get(op_name).params.spec()
        if entry.kind == ("features" if multiple else "feature")
    )


def check(
    document: Document,
    scene: Scene,
    ask: Any,
    registry: Registry | None = None,
    announce: Callable[[tuple[tuple[str, str], ...]], None] | None = None,
    *,
    pending: Sequence[Reference] | None = None,
) -> CheckResult:
    """Löst jeden Verweis einmal auf und fragt, wo die Antwort nicht
    offensichtlich ist (§21.3).

    ``announce`` sagt vor jeder Frage, welche Merkmale gleich zur Wahl stehen —
    je Kandidat ein Paar aus Körper und Kennung —, und nach der Antwort mit
    einer leeren Folge, dass nichts mehr aussteht. **Der Grund steht im
    Bauplan:** §21.3
    verlangt, die Kandidaten *hervorgehoben* zu zeigen. Ohne das steht der
    Kunde vor drei Kennungen — ``hole_1``, ``hole_2``, ``hole_3`` — und soll
    zwischen Bohrungen entscheiden, die er nicht sieht.

    Ein Rückruf und kein Rückgabewert, weil die Hervorhebung **während** der
    Frage gilt: Der Arbeiter blockiert in ``ask``, und was danach zurückkäme,
    käme zu spät. Ohne ``announce`` ändert sich nichts — der Kern kennt keine
    Ansicht (Regel 1), er sagt nur Bescheid, wenn jemand zuhört.

    **Paare und keine bloßen Kennungen**, und das ist keine Bequemlichkeit:
    Merkmalskennungen sind je Körper vergeben. Zwei Körper tragen beide ein
    ``hole_1``, und wer nur die Kennung hervorhebt, leuchtet an zwei Stellen,
    während die Frage eine meint. Beim leeren Objektnamen — der Skizzenebene,
    die auf jeder planaren Fläche der Szene zu Hause sein darf — ist das der
    Regelfall und nicht der Sonderfall.
    """
    result = CheckResult()
    family = lineage(document)
    for reference in references(document, registry) if pending is None else pending:
        if _resolves(scene, reference.ref):
            continue
        candidates = _candidates(scene, reference, family)
        if not candidates:
            result.findings.append(_lost(reference, None))
            continue

        choices = [_choice(pair, qualified=_spans_bodies(candidates)) for pair in candidates]
        question, offered = question_for(reference, tuple(choices))
        if announce is not None:
            announce(tuple(candidates))
        try:
            answer = ask(question, offered)
        finally:
            # Auch bei Abbruch: Was hervorgehoben ist, gehört zur offenen
            # Frage — bleibt es danach stehen, leuchtet die Ansicht ohne
            # Anlass weiter.
            if announce is not None:
                announce(())
        if answer in choices:
            chosen = candidates[choices.index(answer)]
            _rewrite(document, reference, chosen)
            result.rewritten += 1
            result.findings.append(_rewritten_finding(reference, chosen))
        elif reference.kind == "plane" or not reference.removable:
            # Keine Antwort streicht keine Ebene oder bewusste Merkmalsauswahl:
            # Eine geleerte Flächenmenge könnte den ganzen Körper betreffen.
            # Der erhaltene Verweis hält die Operation gezielt an (§15.2).
            result.findings.append(_lost(reference, None))
        else:
            _remove(document, reference)
            result.removed += 1
            result.findings.append(_lost(reference, reference.title))
    if result.changed:
        _log.info("orphan check rewrote %d and removed %d", result.rewritten, result.removed)
    return result


def _resolves(scene: Scene, reference: FeatureRef) -> bool:
    if reference.object_id == "":
        # Der leere Objektname heißt „irgendwo in der Szene" — eine
        # Skizzenebene kennt ihren Körper nicht, ``frame_for`` sucht genauso.
        return any(reference.feature_id in entry.features for entry in scene.objects.values())
    entry = scene.objects.get(reference.object_id)
    return entry is not None and reference.feature_id in entry.features


def _candidates(
    scene: Scene, reference: Reference, family: Mapping[ObjectId, frozenset[ObjectId]]
) -> list[tuple[ObjectId, FeatureId]]:
    """Merkmale gleicher Art — die plausiblen Nachfolger, als Paar aus Körper
    und Kennung.

    Beim leeren Objektnamen über **alle** Körper: Eine Skizzenebene darf auf
    jeder planaren Fläche der Szene neu zu Hause sein, so wie ``frame_for``
    sie dort auch suchen würde.

    **Sonst über den Stammbaum** (:func:`lineage`, RM-023): Nach *In
    Einzelteile zerlegen* trägt nur das erste Stück die alte Kennung, und ein
    Verweis auf ``obj_1:hole_2`` fand sein Loch nicht mehr, obwohl es als
    ``obj_3:hole_1`` dasteht. Über alle Körper zu suchen wäre die falsche
    Abhilfe: Zwei Platten tragen beide ein ``hole_1``, und eine Frage nach
    einem fremden Loch ist schlechter als keine.

    **Ein Operationsverweis bleibt bei seinem Körper**, und das ist keine
    Vorsicht, sondern die Darstellung: Ein ``kind="feature"``-Parameter trägt
    nur die Merkmalskennung und wird gegen ``inputs[0]`` aufgelöst
    (``.claude/rules/operationen.md``). Eine Antwort, die auf einen anderen
    Körper zeigt, ließe sich dort gar nicht hinschreiben — angeboten wird
    deshalb nur, was auch ankommt.
    """
    if reference.ref.object_id == "":
        return _plausible(scene, reference.ref, list(scene.objects))
    bodies = (
        [reference.ref.object_id]
        if reference.kind == "op"
        else _heirs(scene, reference.ref.object_id, family)
    )
    return _plausible(scene, reference.ref, bodies)


def _plausible(
    scene: Scene, reference: FeatureRef, bodies: Sequence[ObjectId]
) -> list[tuple[ObjectId, FeatureId]]:
    """Die Merkmale gleicher Art an den genannten Körpern, in fester Ordnung."""
    wanted = _kind_of(reference.feature_id)
    return sorted(
        (object_id, feature_id)
        for object_id in bodies
        if object_id in scene.objects
        for feature_id, feature in scene.objects[object_id].features.items()
        if wanted is None or feature.kind == wanted
    )


def _spans_bodies(candidates: Sequence[tuple[ObjectId, FeatureId]]) -> bool:
    """Ob die Kandidaten an mehr als einem Körper hängen."""
    return len({object_id for object_id, _feature_id in candidates}) > 1


def _choice(pair: tuple[ObjectId, FeatureId], *, qualified: bool) -> str:
    """Wie ein Kandidat in der Frage heißt.

    **Der Körper steht dabei, sobald es mehr als einen gibt** — und nur dann.
    Zwei Zeilen „hole_1" sind keine Wahl, und ein ``obj_1:`` vor jeder Antwort
    wäre im Normalfall Lärm: Dort hängen alle Kandidaten ohnehin am selben
    Körper, und der steht in der Frage.
    """
    object_id, feature_id = pair
    return f"{object_id}:{feature_id}" if qualified else feature_id


def _kind_of(feature_id: str) -> str | None:
    """``hole_3`` benennt ein Loch. Das Präfix ist die Namensregel aus §21.1.

    Die Liste kommt aus ``FeatureKind`` statt von Hand: Die handgepflegte
    kannte ``cone``, ``sphere``, ``torus`` und ``fillet`` nicht und führte
    das tote ``slot`` — für einen verschwundenen Kegel wurden Flächen und
    Bohrungen als „plausible Nachfolger" angeboten (Fund des Gesamtreviews
    vom 25.08.2026). Der längste Treffer zuerst, damit ``edge_loop_1`` nie
    an einem kürzeren Präfix hängen bleibt.
    """
    from typing import get_args

    from app.core.types import FeatureKind

    for kind in sorted(get_args(FeatureKind), key=len, reverse=True):
        if feature_id.startswith(f"{kind}_"):
            return str(kind)
    return None


def question_for(reference: Reference, candidates: Sequence[str]) -> tuple[str, list[str]]:
    """Die Frage und ihre Antworten; die Passung zu streichen ist der letzte
    Ausweg.

    Eine Skizzenebene und eine fest gewählte Merkmalsmenge bieten kein
    Streichen an: Eine leere Auswahl kann den Wirkungsbereich erweitern.
    Wer nicht antwortet, verliert nichts; der Verweis hält die Operation an.
    """
    question = (
        f"{tr('Dieser Verweis zeigt ins Leere:')} {reference.ref}. "
        f"{tr('Welches Merkmal ist gemeint?')}"
    )
    if reference.kind == "plane" or not reference.removable:
        return question, [*candidates]
    return question, [*candidates, REMOVE_CHOICE]


def _rewrite(document: Document, reference: Reference, chosen: tuple[ObjectId, FeatureId]) -> None:
    """Zeigt den Verweis auf das gewählte Merkmal — einmal beantwortet, nicht
    täglich.

    **Der Körper gehört zur Antwort** (RM-023). Nach einer Zerlegung steht das
    Merkmal an einer anderen Kennung, und ein Verweis, der nur die
    Merkmalskennung umschreibt, zeigte weiter auf den falschen Körper. Wo die
    Darstellung keinen Körper trägt — ein ``kind="feature"``-Parameter wird
    gegen ``inputs[0]`` aufgelöst —, kommt gar kein fremder Körper als
    Kandidat an (:func:`_candidates`).
    """
    object_id, feature_id = chosen
    if reference.kind == "plane":
        # Die Antwort gehört in den Skizzentext, nicht in einen eigenen
        # Parameter: Dort steht die Ebene, dort liest die Auswertung sie.
        from app.core.sketch.planes import feature_plane
        from app.core.sketch.serialize import sketch_from_text, sketch_to_text

        for index, operation in enumerate(document.ops):
            if operation.id != reference.op_id:
                continue
            drawn = sketch_from_text(str(operation.params.get(reference.field) or ""))
            params = dict(operation.params)
            plane = (
                feature_plane(object_id, feature_id)
                if reference.ref.object_id
                else f"feature:{feature_id}"
            )
            params[reference.field] = sketch_to_text(dataclasses.replace(drawn, plane=plane))
            document.ops[index] = dataclasses.replace(operation, params=params)
            return
        return
    if reference.kind == "op":
        _set_param(document, reference, feature_id)
        return
    for index, fit in enumerate(document.fits):
        if fit.name != reference.fit_name:
            continue
        replacement = FeatureRef(object_id, feature_id)
        document.fits[index] = (
            dataclasses.replace(fit, a=replacement)
            if reference.side == "a"
            else dataclasses.replace(fit, b=replacement)
        )
        return


def _remove(document: Document, reference: Reference) -> None:
    """Streicht, was sich nicht auflösen lässt — eine Passung geht, eine
    Operation verliert nur den Namen.

    Eine Operation ist ein Schritt, den jemand getan hat — sie zu löschen,
    weil einer ihrer Parameter sein Ziel verlor, nähme die Geometrie mit.
    Geleert fällt die Operation auf ihre eigenen Zahlen zurück — bei einem
    Baustein der Ursprung, bei einem Deckel die Oberkante — und der Befund
    sagt es, damit niemanden ein Schritt überrascht, der still umgezogen ist.
    """
    if reference.kind == "op":
        _set_param(document, reference, "")
        return
    document.fits[:] = [fit for fit in document.fits if fit.name != reference.fit_name]


def _set_param(document: Document, reference: Reference, value: str) -> None:
    for index, operation in enumerate(document.ops):
        if operation.id == reference.op_id:
            params = dict(operation.params)
            if reference.index is None:
                params[reference.field] = value
            else:
                names = list(params[reference.field])
                names[reference.index] = value
                params[reference.field] = tuple(names)
            document.ops[index] = dataclasses.replace(operation, params=params)
            return


def _rewritten_finding(reference: Reference, chosen: tuple[ObjectId, FeatureId]) -> Finding:
    """Der Befund nennt das Ziel so, wie die Frage es genannt hat.

    Steht das Merkmal an einem anderen Körper, gehört dessen Kennung in den
    Satz: „hole_2 → hole_1" wäre über eine Zerlegung hinweg keine Auskunft,
    sondern ein Rätsel (RM-023).
    """
    object_id, feature_id = chosen
    moved = object_id != reference.ref.object_id
    return Finding(
        code="feature.rewritten",
        severity="info",
        message=_("Ein Verweis wurde auf ein anderes Merkmal umgeschrieben."),
        object_id=object_id,
        feature_ids=(feature_id,),
        values={
            "from": reference.ref.feature_id,
            "to": f"{object_id}:{feature_id}" if moved else feature_id,
            "where": reference.title,
        },
    )


def _lost(reference: Reference, removed_fit: str | None) -> Finding:
    return Finding(
        code="feature.orphaned",
        severity="warning" if removed_fit else "error",
        message=_("Ein Verweis zeigt auf ein Merkmal, das es nicht mehr gibt."),
        object_id=reference.ref.object_id,
        feature_ids=(reference.ref.feature_id,),
        values={"reference": str(reference.ref), "where": reference.title},
    )


def candidates_of(scene: Scene, reference: FeatureRef) -> dict[str, Feature]:
    """Die Kandidaten-Merkmale selbst — die Oberfläche hebt sie hervor (§21.3).

    Nach Kennungen und nicht nach Paaren, denn sie beantwortet eine Frage an
    **einen** Körper: „welche Merkmale dieses Körpers kämen in Frage". Wo eine
    Zerlegung die Kandidaten über mehrere Körper verteilt (RM-023), reicht
    ``check`` sie als Paare über ``announce`` heraus — dort steht der Körper
    dabei, und nur dort wird er gebraucht.
    """
    bodies = list(scene.objects) if reference.object_id == "" else [reference.object_id]
    return {
        feature_id: scene.objects[object_id].features[feature_id]
        for object_id, feature_id in _plausible(scene, reference, bodies)
    }
