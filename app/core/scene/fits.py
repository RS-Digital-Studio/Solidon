"""Passungen zwischen Merkmalen (Bauplan §14).

Objekte sind sonst unabhängig, und ein Fehler zeigt sich erst beim
Zusammenbau — wenn der Stift nicht ins Loch geht und der Druck schon gemacht
ist. Eine Passung bindet zwei Merkmale aneinander und wird bei jeder
Auswertung geprüft.

Die Toleranz ist ein Verweis ins Materialprofil, nie eine Zahl in der
Datei (§12, AGENTS.md Regel 7). Genau das lässt die Kalibrierung (§28.3)
Projekte erreichen, die vor ihr gebaut wurden.
"""

from __future__ import annotations

import math

from app.core.errors import AppError
from app.core.expressions import resolve as resolve_parameters
from app.core.expressions import resolve_value
from app.core.knowledge.profiles import for_object, resolve_tolerance
from app.core.log import get_logger
from app.core.types import (
    AUTO_TOLERANCE_PREFIX,
    Document,
    Feature,
    FeatureRef,
    Finding,
    Fit,
    FitKind,
    Profile,
    Scene,
    vec3_or_none,
)
from app.core.units import EPS_DISPLAY, EPS_GEOM, format_length
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Wie weit das tatsächliche Spiel vom Profilwert abweichen darf, bevor es ein
#: Befund wird.
#:
#: §14 sagt „im Rahmen von ``EPS_GEOM``", und das stimmt für den Fall, den er
#: meinte: zwei **konstruierte** Maße unterscheiden sich exakt bis aufs
#: Fließkommarauschen. Gemessen wird hier aber an erkannten Merkmalen, und
#: deren Maße kommen bei B-Rep-Körpern aus der Tessellation — die trägt
#: konstant etwa 0,025 mm (die halbe ``DEFLECTION``; gemessen in der
#: Live-Durchsicht vom 05.08.2026, bei Ø 6 wie bei Ø 120). Mit ``EPS_GEOM``
#: wäre jede Passung auf einem exakten Körper „verletzt". Fünffaches
#: ``EPS_DISPLAY`` liegt sicher über dem Rauschen und weit unter jedem
#: Spiel, über das eine Passung etwas aussagt. §14 ist entsprechend
#: nachzuziehen — Bauplanänderung mit Ansage, siehe ROADMAP.
FIT_TOLERANCE = EPS_DISPLAY * 5


def resolve(scene: Scene, reference: FeatureRef) -> Feature | None:
    """Das Merkmal, auf das eine Passung zeigt — oder None, wenn es fort ist."""
    entry = scene.objects.get(reference.object_id)
    if entry is None:
        return None
    return entry.features.get(reference.feature_id)


def diameter_of(feature: Feature) -> float | None:
    return _positive(feature, "diameter")


def _positive(feature: Feature, name: str) -> float | None:
    """Ein wirklich gemessenes positives Maß; bool und nichtendliche Werte zählen nicht."""
    value = feature.params.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value > EPS_GEOM else None


def _role(feature: Feature) -> str | None:
    """Die belegte Innen-/Außenrolle, nie aus der größeren Zahl geraten."""
    if feature.kind in {"hole", "pin"}:
        return "inner" if feature.kind == "hole" else "outer"
    if feature.kind == "thread" and isinstance(feature.params.get("internal"), bool):
        return "inner" if feature.params["internal"] else "outer"
    role = feature.params.get("fit_role")
    if feature.kind == "face" and isinstance(role, str) and role in {"inner", "outer"}:
        return role
    return None


def pair_problem(kind: FitKind, first: Feature, second: Feature) -> TranslatableText | None:
    """Gemeinsame Eignungsprüfung für gespeicherte Beziehungen und ihre Anlegeoberfläche."""
    problem = _pair_problem(kind, first, second)
    return problem[1] if problem is not None else None


def _pair_problem(
    kind: FitKind, first: Feature, second: Feature
) -> tuple[str, TranslatableText] | None:
    """Code und Vorschlag kommen aus derselben Prüfung, auch nach späteren Maßänderungen."""
    if kind == "flush":
        if first.kind != "face" or second.kind != "face":
            return "fit.not_measurable", _("Für eine bündige Passung zwei ebene Flächen wählen.")
        for feature in (first, second):
            centre = vec3_or_none(feature.params.get("centre"))
            normal = vec3_or_none(feature.params.get("normal"))
            if (
                centre is None
                or normal is None
                or not all(math.isfinite(v) for v in (*centre, *normal))
                or not math.isfinite(math.hypot(*normal))
                or math.hypot(*normal) <= EPS_GEOM
            ):
                return "fit.not_measurable", _(
                    "Diese Fläche hat keine gemessene Ebene. Eine andere ebene Fläche wählen."
                )
        return None
    if kind == "thread":
        if first.kind != "thread" or second.kind != "thread":
            return "fit.not_measurable", _(
                "Für eine Gewindepassung ein Innen- und ein Außengewinde wählen."
            )
        if _positive(first, "pitch") is None or _positive(second, "pitch") is None:
            return "fit.not_measurable", _(
                "Die Gewindesteigung fehlt. Zwei Gewinde mit gemessener Steigung wählen."
            )
    if {_role(first), _role(second)} != {"inner", "outer"}:
        return "fit.not_measurable", _(
            "Eine Öffnung und ihr Gegenstück wählen, etwa Bohrung und Zapfen."
        )
    if diameter_of(first) is None or diameter_of(second) is None:
        return "fit.not_measurable", _(
            "Ein Durchmesser fehlt. Zwei Merkmale mit gemessenem Durchmesser wählen."
        )
    if kind == "thread":
        first_pitch, second_pitch = _positive(first, "pitch"), _positive(second, "pitch")
        assert first_pitch is not None and second_pitch is not None
        if abs(first_pitch - second_pitch) > EPS_GEOM:
            return "fit.pitch_mismatch", _(
                "Die Gewindesteigungen unterscheiden sich. Beide Gewinde auf dieselbe "
                "Steigung ändern."
            )
    return None


def pair_kinds(first: Feature, second: Feature) -> tuple[FitKind, ...]:
    """Die sinnvollen neuen Prüfbeziehungen; historische radiale Gewindepaare bleiben lesbar."""
    candidates: tuple[FitKind, ...]
    if first.kind == "thread" or second.kind == "thread":
        candidates = ("thread",)
    elif _role(first) is not None or _role(second) is not None:
        candidates = ("clearance", "press")
    else:
        candidates = ("flush",)
    return tuple(kind for kind in candidates if pair_problem(kind, first, second) is None)


def target(scene: Scene, fit: Fit, profile: Profile) -> tuple[float, tuple[str, ...]]:
    """Sollmaß und tatsächlich verwendete Materialtitel für die sichtbare Anlegeauskunft."""
    if fit.kind == "flush":
        return 0.0, ()
    first, second = resolve(scene, fit.a), resolve(scene, fit.b)
    if first is None or second is None or pair_problem(fit.kind, first, second) is not None:
        raise ValueError("fit_not_measurable")
    hole, _pin = _sort_by_kind(first, second)
    hole_ref, pin_ref = (fit.a, fit.b) if hole is first else (fit.b, fit.a)
    wanted, _ = _wanted(scene, fit, hole_ref, pin_ref, profile)
    references = (hole_ref,) if fit.kind == "thread" else (hole_ref, pin_ref)
    names = tuple(
        dict.fromkeys(_profile_of(scene, ref, profile).material.title for ref in references)
    )
    return wanted, names


def _condition_value(fit: Fit, document: Document | None) -> float:
    """Die Bedingung liest die aktuelle Operation, nie einen kopierten Altwert."""
    if fit.when_positive is None:
        return 1.0
    if document is None:
        raise ValueError("document_missing")
    operation_id, parameter = fit.when_positive
    operation = next((entry for entry in document.ops if entry.id == operation_id), None)
    if operation is None:
        raise ValueError("operation_missing")
    from app.core.registry import REGISTRY

    fields = {entry.name: entry for entry in REGISTRY.get(operation.op).params.fields()}
    if parameter not in fields:
        raise ValueError("parameter_missing")
    value = operation.params.get(parameter, fields[parameter].default)
    value = resolve_value(value, resolve_parameters(document.parameters))
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("condition_not_numeric")
    return float(value)


def active_fits(document: Document) -> list[Fit]:
    """Nur eine gültige nichtpositive Bedingung deaktiviert eine Passung."""
    active: list[Fit] = []
    for fit in document.fits:
        try:
            if _condition_value(fit, document) <= 0.0:
                continue
        except AppError, ValueError, TypeError, KeyError:
            # Ungültig bleibt sichtbar; check liefert den zugehörigen Befund.
            pass
        active.append(fit)
    return active


def check(scene: Scene, profile: Profile, *, document: Document | None = None) -> list[Finding]:
    """Prüft jede Passung der Szene. Verletzungen sind nie still (§14)."""
    findings: list[Finding] = []
    for fit in scene.fits:
        try:
            if _condition_value(fit, document) <= 0.0:
                continue
        except (AppError, ValueError, TypeError, KeyError) as problem:
            findings.append(
                Finding(
                    code="fit.invalid_condition",
                    severity="error",
                    message=_(
                        "Die Bedingung dieser Passung lässt sich nicht auswerten. Den "
                        "zugehörigen Schritt und seinen Parameter prüfen."
                    ),
                    object_id=fit.a.object_id,
                    values={"fit": fit.name, "reason": str(problem)},
                )
            )
            continue
        findings.extend(_check_one(scene, fit, profile))
    return findings


def _check_one(scene: Scene, fit: Fit, profile: Profile) -> list[Finding]:
    first = resolve(scene, fit.a)
    second = resolve(scene, fit.b)
    if first is None or second is None:
        # **Der Satz nennt den Grund und einen Weg.** Er nannte keinen von
        # beiden, und der häufigste Fall ist einer, in den ein Kunde ohne
        # Warnung hineinläuft: Er öffnet „Dose mit Deckel", schreibt seinen
        # Namen darauf — und der Prüfbericht meldet einen Fehler. Eine
        # Boolesche Operation baut den Körper neu, die Merkmale werden neu
        # erkannt, und die vom Deckel *benannten* (`lid_cavity`) sind dabei
        # nicht mehr. Wer das nicht weiß, sucht den Fehler in seiner
        # Beschriftung.
        return [
            Finding(
                code="fit.missing_feature",
                severity="error",
                message=_(
                    "Eine Passung verweist auf ein Merkmal, das es nicht mehr gibt: eine "
                    "Operation danach hat den Körper neu gebaut, und benannte Merkmale "
                    "überstehen das nicht. Die Schritte ab dort zurücknehmen und vor der "
                    "Passung ausführen."
                ),
                values={"fit": fit.name, "a": str(fit.a), "b": str(fit.b)},
                # Ein Merkmal, das es nicht mehr gibt, lässt sich nicht
                # ansteuern — der Körper aber schon. Das ist die zweite Stufe
                # der Zusage aus §18.4, und ohne diese Zeile war es keine.
                object_id=fit.a.object_id,
            )
        ]

    problem = _pair_problem(fit.kind, first, second)
    if problem is not None:
        code, message = problem
        values = {"fit": fit.name, "a": str(fit.a), "b": str(fit.b)}
        if code == "fit.pitch_mismatch":
            values.update(
                first_pitch=format_length(float(first.params["pitch"])),
                second_pitch=format_length(float(second.params["pitch"])),
            )
        return [
            Finding(
                code=code,
                severity="warning",
                message=message,
                values=values,
                object_id=fit.a.object_id,
                feature_ids=(fit.a.feature_id,),
            )
        ]

    if fit.kind == "flush":
        return _check_flush(fit, first, second)

    hole, pin = _sort_by_kind(first, second)
    hole_diameter = diameter_of(hole)
    pin_diameter = diameter_of(pin)
    if hole_diameter is None or pin_diameter is None:
        return [
            Finding(
                code="fit.not_measurable",
                severity="warning",
                message=_("Diese Passung lässt sich nicht messen — es fehlt ein Durchmesser."),
                values={"fit": fit.name},
                object_id=fit.a.object_id,
                feature_ids=(fit.a.feature_id,),
            )
        ]

    # Aus welchem der zwei Verweise das Loch kam: _sort_by_kind kann sie
    # getauscht haben, und „hole_1" ist nur im eigenen Objekt eindeutig.
    hole_ref, pin_ref = (fit.a, fit.b) if hole is first else (fit.b, fit.a)
    wanted, materials = _wanted(scene, fit, hole_ref, pin_ref, profile)
    actual = hole_diameter - pin_diameter
    if abs(actual - wanted) <= FIT_TOLERANCE:
        return []

    return [
        Finding(
            code="fit.violated",
            severity="warning",
            message=_message_for(fit.kind, actual, wanted),
            values={
                "fit": fit.name,
                "actual": format_length(actual),
                "expected": format_length(wanted),
                **({"materials": materials} if materials else {}),
            },
            # **Wohin der Klick führt.** Genannt wird das Loch und nicht der
            # Zapfen: Bei einer Schiebepassung ist die Öffnung die Stelle, an
            # der man nachsieht. Aus dem Merkmal rechnet `maps.location_of`
            # den Punkt, zu dem die Kamera fliegt.
            object_id=hole_ref.object_id,
            feature_ids=(hole_ref.feature_id,),
        )
    ]


def _wanted(
    scene: Scene, fit: Fit, hole: FeatureRef, pin: FeatureRef, profile: Profile
) -> tuple[float, str]:
    """Das Spiel, das diese Passung haben soll, in den Materialien, aus denen
    sie besteht (§12).

    Ein benannter Verweis (``auto:petg``) bleibt, was er sagt — dieses
    Material hat jemand mit Absicht hingeschrieben. Das nackte ``auto:``
    heißt „worin das eben gedruckt wird", und das ist nicht unbedingt eines:
    eine TPU-Dichtung im PETG-Gehäuse hat zwei Antworten.

    Wo sie sich unterscheiden, gewinnt der größere Wert — eine Regel für beide
    Arten statt zwei. Ein Spiel ist positiv, der größere Wert also der
    weitere Spalt: es geht zusammen. Ein Pressmaß ist negativ, der größere
    Wert also das *kleinere* Übermaß: es sprengt das Teil nicht, in das
    gepresst wird. Beide Male fällt die Wahl auf die Seite, deren Scheitern
    ein brauchbares Teil übrig lässt — eine Verbindung, die locker sitzt,
    kann man kleben; ein Gehäuse, das beim Zusammenbau gerissen ist, ist
    Ausschuss.

    Ein Gewinde ist eine Eigenschaft des Lochs und liest nur dessen Material.
    """
    if not isinstance(fit.tolerance, str) or fit.tolerance != AUTO_TOLERANCE_PREFIX:
        return resolve_tolerance(fit.tolerance, fit.kind, profile), ""

    both = [_profile_of(scene, hole, profile), _profile_of(scene, pin, profile)]
    if fit.kind == "thread":
        both = both[:1]
    chosen = max(resolve_tolerance(fit.tolerance, fit.kind, entry) for entry in both)

    names = {entry.material.id for entry in both}
    return chosen, ", ".join(sorted(names)) if len(names) > 1 else ""


def _profile_of(scene: Scene, reference: FeatureRef, profile: Profile) -> Profile:
    """Das Profil des Körpers, auf den ein Passungsverweis zeigt."""
    return for_object(profile, scene.objects.get(reference.object_id))


def _check_flush(fit: Fit, first: Feature, second: Feature) -> list[Finding]:
    """Zwei Flächen, die in einer Ebene sitzen sollen (§14).

    Gemessen als Abstand des Mittelpunkts der zweiten Fläche von der Ebene der
    ersten. Das ist die Zahl, für die jemand ein Haarlineal über den
    Zusammenbau legen würde, und sie entscheidet, ob ein Deckel übersteht.

    Ein Flächenpaar, das nicht parallel steht, ist ein anderer Fehler und
    bekommt das gesagt: zwei Ebenen im Winkel haben keinen Abstand, der sich
    zu melden lohnt.
    """
    if first.kind != "face" or second.kind != "face":
        return [
            Finding(
                code="fit.not_measurable",
                severity="warning",
                message=_("Eine bündige Passung braucht zwei Flächen."),
                values={"fit": fit.name, "a": first.kind, "b": second.kind},
                object_id=fit.a.object_id,
                feature_ids=(fit.a.feature_id,),
            )
        ]

    normal = vec3_or_none(first.params.get("normal"))
    other = vec3_or_none(second.params.get("normal"))
    centre = vec3_or_none(first.params.get("centre"))
    against = vec3_or_none(second.params.get("centre"))
    if normal is None or other is None or centre is None or against is None:
        return [
            Finding(
                code="fit.not_measurable",
                severity="warning",
                message=_("Diese Passung lässt sich nicht messen — es fehlt eine Fläche."),
                values={"fit": fit.name},
                object_id=fit.a.object_id,
                feature_ids=(fit.a.feature_id,),
            )
        ]

    normal_size, other_size = math.hypot(*normal), math.hypot(*other)
    normal = (normal[0] / normal_size, normal[1] / normal_size, normal[2] / normal_size)
    other = (other[0] / other_size, other[1] / other_size, other[2] / other_size)
    signed = sum(a * b for a, b in zip(normal, other, strict=True))
    direction = 1.0 if signed >= 0.0 else -1.0
    # Bündig verlangt dieselbe Ebene, keinen acht Grad breiten Winkelbereich.
    # Die normierten Richtungen vergleichen wir mit der vorhandenen numerischen
    # Geometriegenauigkeit; das Materialspiel ist keine Winkeltoleranz.
    if math.dist(normal, tuple(direction * value for value in other)) > EPS_GEOM:
        return [
            Finding(
                code="fit.violated",
                severity="warning",
                message=_("Die beiden Flächen stehen nicht parallel — bündig können sie nicht."),
                values={"fit": fit.name, "alignment": abs(signed)},
                object_id=fit.a.object_id,
                feature_ids=(fit.a.feature_id,),
            )
        ]

    offset = abs(sum((b - a) * n for a, b, n in zip(centre, against, normal, strict=True)))
    if offset <= FIT_TOLERANCE:
        return []
    return [
        Finding(
            code="fit.violated",
            severity="warning",
            message=_("Die beiden Flächen sitzen nicht bündig."),
            values={"fit": fit.name, "actual": format_length(offset), "expected": "0 mm"},
            # Die erste Fläche ist die Bezugsebene, gegen die gemessen
            # wird — und damit die Stelle, an der man nachsieht.
            object_id=fit.a.object_id,
            feature_ids=(fit.a.feature_id,),
        )
    ]


def _sort_by_kind(first: Feature, second: Feature) -> tuple[Feature, Feature]:
    """Das Loch zuerst, der Stift danach — egal, wie herum sie geschrieben
    wurden."""
    if _role(first) == "inner":
        return first, second
    if _role(second) == "inner":
        return second, first
    raise ValueError("fit_inner_role_missing")


def _message_for(kind: FitKind, actual: float, wanted: float) -> TranslatableText:
    """Die Meldung zu einer Passung, die nicht sitzt wie gewollt.

    Der Marker steht hier an den Zeichenketten und **nicht** um den Aufruf
    herum. Das ist kein Geschmack: Der Sammler nimmt nur Konstanten, die
    unmittelbar in ``_()`` stehen (``app/i18n/extract.py``). Als
    ``_(_message_for(...))`` geschrieben, sah der Aufruf übersetzt aus, war
    es aber nie — beide Sätze standen in keinem Katalog, und im spanischen
    Handbuchbild stand ein deutscher Befund zwischen sieben spanischen.
    """
    if actual < wanted:
        return _("Die Passung sitzt enger als vorgesehen.")
    return _("Die Passung sitzt loser als vorgesehen.")


def add(scene_fits: list[Fit], fit: Fit) -> list[Fit]:
    """Fügt ein Paar an; ein gleichnamiges wird ersetzt (§25, Agentenwerkzeug
    ``add_fit``)."""
    kept = [entry for entry in scene_fits if entry.name != fit.name]
    kept.append(fit)
    _log.info("fit %s: %s to %s", fit.name, fit.a, fit.b)
    return kept


def remove(scene_fits: list[Fit], name: str) -> list[Fit]:
    return [entry for entry in scene_fits if entry.name != name]
