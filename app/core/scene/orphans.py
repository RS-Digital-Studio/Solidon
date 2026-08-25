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
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.log import get_logger
from app.core.registry import REGISTRY, Registry
from app.core.types import Document, Feature, FeatureRef, Finding, Scene
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
                Reference(f"op:{operation.id}:{field_name}", FeatureRef(operation.inputs[0], named))
            )
        for field_name in _sketch_fields(source, operation.op):
            plane_feature = _face_of_sketch(str(operation.params.get(field_name) or ""))
            if plane_feature is None:
                continue
            # Eine Skizze auf einer Fläche benennt ein Merkmal — im
            # Skizzentext statt in einem feature-Parameter, und genau deshalb
            # sah dieser Filter sie nie: Die Datei bekam bei „Skizze auf
            # Fläche" keine §21.3-Frage. Der **leere Objektname** ist Absicht:
            # Wem die Fläche gehört, weiß erst die Auswertung — ``frame_for``
            # sucht über alle Körper, weil ``sketch_extrude`` nichts
            # verbraucht.
            found.append(
                Reference(f"plane:{operation.id}:{field_name}", FeatureRef("", plane_feature))
            )
    return found


def _sketch_fields(registry: Registry, op_name: str) -> tuple[str, ...]:
    """Parameter dieser Operation, die eine Skizze tragen — aus der
    Deklaration, wie bei :func:`_feature_fields`."""
    if not registry.has(op_name):
        return ()
    return tuple(
        entry.name for entry in registry.get(op_name).params.spec() if entry.kind == "sketch"
    )


def _face_of_sketch(text: str) -> str | None:
    """Die Fläche, auf der diese Skizze liegt — oder nichts.

    Ein unlesbarer Skizzentext ist der Fehler der Operation, nicht dieser
    Prüfung: Sie zählt Verweise auf und übergeht, was sie nicht lesen kann.
    """
    if not text:
        return None
    from app.core.sketch.planes import is_feature_plane
    from app.core.sketch.serialize import sketch_from_text

    try:
        plane = sketch_from_text(text).plane
    except Exception:
        return None
    if not is_feature_plane(plane):
        return None
    return plane.partition(":")[2]


def _feature_fields(registry: Registry, op_name: str) -> tuple[str, ...]:
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
        entry.name for entry in registry.get(op_name).params.spec() if entry.kind == "feature"
    )


def check(
    document: Document, scene: Scene, ask: Any, registry: Registry | None = None
) -> CheckResult:
    """Löst jeden Verweis einmal auf und fragt, wo die Antwort nicht
    offensichtlich ist (§21.3)."""
    result = CheckResult()
    for reference in references(document, registry):
        if _resolves(scene, reference.ref):
            continue
        candidates = _candidates(scene, reference.ref)
        if not candidates:
            result.findings.append(_lost(reference, None))
            continue

        question, choices = question_for(reference, candidates)
        answer = ask(question, choices)
        if answer in candidates:
            _rewrite(document, reference, answer)
            result.rewritten += 1
            result.findings.append(_rewritten_finding(reference, answer))
        elif reference.kind == "plane":
            # Keine Antwort streicht keine Ebene: Das Dokument bleibt, wie es
            # ist, und die Auswertung hält an der Operation mit ``frame_fors``
            # eigenem Satz an (§15.2). Der Befund sagt trotzdem, wo es hakt.
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


def _candidates(scene: Scene, reference: FeatureRef) -> list[str]:
    """Merkmale gleicher Art am selben Objekt — die plausiblen Nachfolger.

    Beim leeren Objektnamen über **alle** Körper: Eine Skizzenebene darf auf
    jeder planaren Fläche der Szene neu zu Hause sein, so wie ``frame_for``
    sie dort auch suchen würde.
    """
    wanted = _kind_of(reference.feature_id)
    if reference.object_id == "":
        return sorted(
            {
                feature_id
                for entry in scene.objects.values()
                for feature_id, feature in entry.features.items()
                if wanted is None or feature.kind == wanted
            }
        )
    entry = scene.objects.get(reference.object_id)
    if entry is None:
        return []
    return sorted(
        feature_id
        for feature_id, feature in entry.features.items()
        if wanted is None or feature.kind == wanted
    )


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

    **Eine Skizzenebene bietet kein Streichen an**: Ohne Ebene gibt es die
    Skizze nicht — wer nicht antwortet, verliert nichts, die Operation hält
    später mit dem eigenen Satz von ``frame_for`` an (§15.2).
    """
    question = (
        f"{tr('Dieser Verweis zeigt ins Leere:')} {reference.ref}. "
        f"{tr('Welches Merkmal ist gemeint?')}"
    )
    if reference.kind == "plane":
        return question, [*candidates]
    return question, [*candidates, REMOVE_CHOICE]


def _rewrite(document: Document, reference: Reference, feature_id: str) -> None:
    """Zeigt den Verweis auf das gewählte Merkmal — einmal beantwortet, nicht
    täglich."""
    if reference.kind == "plane":
        # Die Antwort gehört in den Skizzentext, nicht in einen eigenen
        # Parameter: Dort steht die Ebene, dort liest die Auswertung sie.
        from app.core.sketch.serialize import sketch_from_text, sketch_to_text

        for index, operation in enumerate(document.ops):
            if operation.id != reference.op_id:
                continue
            drawn = sketch_from_text(str(operation.params.get(reference.field) or ""))
            params = dict(operation.params)
            params[reference.field] = sketch_to_text(
                dataclasses.replace(drawn, plane=f"feature:{feature_id}")
            )
            document.ops[index] = dataclasses.replace(operation, params=params)
            return
        return
    if reference.kind == "op":
        _set_param(document, reference, feature_id)
        return
    for index, fit in enumerate(document.fits):
        if fit.name != reference.fit_name:
            continue
        replacement = FeatureRef(reference.ref.object_id, feature_id)
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
            params[reference.field] = value
            document.ops[index] = dataclasses.replace(operation, params=params)
            return


def _rewritten_finding(reference: Reference, feature_id: str) -> Finding:
    return Finding(
        code="feature.rewritten",
        severity="info",
        message=_("Ein Verweis wurde auf ein anderes Merkmal umgeschrieben."),
        object_id=reference.ref.object_id,
        feature_ids=(feature_id,),
        values={"from": reference.ref.feature_id, "to": feature_id, "where": reference.title},
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
    """Die Kandidaten-Merkmale selbst — die Oberfläche hebt sie hervor (§21.3)."""
    if reference.object_id == "":
        gathered: dict[str, Feature] = {}
        for anybody in scene.objects.values():
            gathered.update(anybody.features)
        return {name: gathered[name] for name in _candidates(scene, reference) if name in gathered}
    entry = scene.objects.get(reference.object_id)
    if entry is None:
        return {}
    return {name: entry.features[name] for name in _candidates(scene, reference)}
