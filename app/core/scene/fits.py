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

from app.core.knowledge.profiles import for_object, resolve_tolerance
from app.core.log import get_logger
from app.core.types import (
    AUTO_TOLERANCE_PREFIX,
    Feature,
    FeatureRef,
    Finding,
    Fit,
    FitKind,
    Profile,
    Scene,
)
from app.core.units import EPS_DISPLAY, format_length
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

#: Wie parallel zwei Flächen stehen müssen, damit sich eine bündige Passung
#: überhaupt messen lässt. 0.99 sind etwa acht Grad — darüber sind es nicht
#: dieselbe Ebene, sondern zwei Ebenen, die sich an einer Ecke treffen.
FLUSH_PARALLEL = 0.99


def resolve(scene: Scene, reference: FeatureRef) -> Feature | None:
    """Das Merkmal, auf das eine Passung zeigt — oder None, wenn es fort ist."""
    entry = scene.objects.get(reference.object_id)
    if entry is None:
        return None
    return entry.features.get(reference.feature_id)


def diameter_of(feature: Feature) -> float | None:
    value = feature.params.get("diameter")
    return float(value) if value is not None else None


def check(scene: Scene, profile: Profile) -> list[Finding]:
    """Prüft jede Passung der Szene. Verletzungen sind nie still (§14)."""
    findings: list[Finding] = []
    for fit in scene.fits:
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
            )
        ]

    normal = _vector(first.params.get("normal"))
    other = _vector(second.params.get("normal"))
    centre = _vector(first.params.get("centre"))
    against = _vector(second.params.get("centre"))
    if normal is None or other is None or centre is None or against is None:
        return [
            Finding(
                code="fit.not_measurable",
                severity="warning",
                message=_("Diese Passung lässt sich nicht messen — es fehlt eine Fläche."),
                values={"fit": fit.name},
            )
        ]

    alignment = abs(sum(a * b for a, b in zip(normal, other, strict=True)))
    if alignment < FLUSH_PARALLEL:
        return [
            Finding(
                code="fit.violated",
                severity="warning",
                message=_("Die beiden Flächen stehen nicht parallel — bündig können sie nicht."),
                values={"fit": fit.name, "alignment": round(alignment, 3)},
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
        )
    ]


def _vector(value: object) -> tuple[float, float, float] | None:
    """Ein dreikomponentiger Parameter, oder None, wenn er keiner ist."""
    if not isinstance(value, list | tuple) or len(value) != 3:
        return None
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        return None


def _sort_by_kind(first: Feature, second: Feature) -> tuple[Feature, Feature]:
    """Das Loch zuerst, der Stift danach — egal, wie herum sie geschrieben
    wurden."""
    if first.kind == "hole":
        return first, second
    if second.kind == "hole":
        return second, first
    # Keines ist ein Loch: der größere Durchmesser übernimmt die Rolle.
    return (
        (first, second)
        if (diameter_of(first) or 0.0) >= (diameter_of(second) or 0.0)
        else (second, first)
    )


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
