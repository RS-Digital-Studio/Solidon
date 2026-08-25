"""Ein eigener Baustein als Rezept — Daten statt Programm (§24.5, Konzept
Befestigungssysteme §16 bis §19, Pakete E2 und E5).

Ein Rezept ist ein **Ausschnitt aus dem Op-Stapel plus die Beschreibung
seiner Parameter**: eine Liste registrierter Operationen mit Werten, die
Parameter, die der Kunde nach außen geben will, und die Merkmale, die der
fertige Baustein verspricht. Kein Python, keine Funktion, nichts, was
ausgeführt wird — seine Sicherheitslage ist die einer Projektdatei, nicht die
einer fremden ``.py`` (Regel 13, Entscheidung vom 24.08.2026). Trägt ein
Rezept einen ``create_from_scad``-Schritt, greift die Quelltextprüfung aus
§32 bei der Auswertung wie überall sonst — hier wird nichts daran vorbei
gebaut, weil hier derselbe Auswerter läuft wie für jede Projektdatei.

**Der Dokument-Ausschnitt reist als Dokument.** Serialisiert wird er über
``scene.serialise`` — dieselben Funktionen, die die Projektdatei schreiben.
Damit erbt ein Rezept den Migrationsweg des Dokumentformats, statt einen
zweiten zu brauchen: Öffnet eine spätere Version ein altes Rezept, laufen
dieselben Migrationen wie für eine alte Projektdatei. Die Hülle darum trägt
ihre eigene ``FORMAT_VERSION`` für das, was nur das Rezept kennt.

**Die Version ist der Hash** (§24.4, Konzept §18f): :func:`fingerprint`
rechnet über die kanonischen Daten, und ein geändertes Rezept ist damit per
Bauart ein anderes — niemand muss einen Änderungsverlauf pflegen, den es bei
eigenen Bausteinen erfahrungsgemäß nie gibt.

**Ausgewertet wird mit dem Auswerter der Szene** (:func:`build`): Parameter
hinein, ein Körper mit benannten Merkmalen heraus — der ``PartFn``-Ersatz aus
Paket E5. Ein Rezept, dessen Ausschnitt nicht auf genau einen Körper
hinausläuft, wird beim Anlegen abgewiesen und nicht später halb gebaut
(Konzept §18a).

``to_scad()`` gibt es für Rezepte nicht, und das ist benannt statt umgangen
(Konzept §18e): Für beliebige Operationen lässt sich kein OpenSCAD-Modul
bilden.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.errors import CANCEL, CORRECT_INPUT, GeometryError, ValidationError
from app.core.knowledge.parts.registry import PartRegistry, PartSpec
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_parts_dir
from app.core.registry import Registry, op_params, param
from app.core.scene.migrations import migrate
from app.core.scene.serialise import document_from_data, document_to_data
from app.core.types import (
    BaseParams,
    Document,
    Feature,
    Finding,
    PartResult,
    Profile,
    Quality,
)
from app.i18n import _

_log = get_logger(__name__)

#: Version der Rezept-Hülle. Der Dokument-Ausschnitt darin trägt seine eigene
#: (``document.format_version``) und reist über deren Migrationen.
FORMAT_VERSION = 1

#: Wo eigene Rezepte liegen: neben den ``.py``-Bausteinen, als eigener
#: Unterordner — eine Datei je Rezept, der Dateiname ist der Name.
RECIPES_DIRNAME = "recipes"

#: Kennzeichnung im Katalog (§24.5): ein Rezept ist weder ``shipped`` noch
#: eine ``user``-``.py``. Der Unterschied trägt: ``travelling_parts`` warnt
#: vor ``.py``-Bausteinen, die nie mitreisen — ein Rezept reist als Daten und
#: gehört darum ausdrücklich **nicht** in diese Warnung.
RECIPE_SOURCE = "recipe"

#: Herkunft eines Rezepts, das mit einer Projektdatei angekommen ist.
#: „Lokal schlägt mitgereist, immer" (Konzept §17.1): Es wird registriert und
#: im Katalog gekennzeichnet, aber nie in den Nutzerordner geschrieben — es
#: gehört der Datei, mit der es kam, nicht dieser Maschine.
TRAVELLED_SOURCE = "travelled"

#: Wo Rezepte in einer Projektdatei liegen (Konzept §17.1).
CONTAINER_PREFIX = "recipes/"


def container_entry(name: str) -> str:
    """Der Pfad eines Rezepts im Projektcontainer."""
    return f"{CONTAINER_PREFIX}{name}.json"


@dataclass(frozen=True, slots=True)
class ExposedParam:
    """Ein Parameter, den das Rezept nach außen gibt.

    Genau die Angaben, die ``param()`` für einen eingebauten Baustein
    verlangt (Konzept §16, Schritt 4): Titel, Einheit, Grenzen, Vorgabe,
    vorn oder hinten im Dialog, ein Satz Beschreibung. ``name`` muss ein
    Projektparameter des Ausschnitts sein — er ist die Stelle, an der der
    Wert in die Operationen fließt (``@name`` in Ausdrücken, §13).
    """

    name: str
    title: str
    default: float
    unit: str = "mm"
    minimum: float | None = None
    maximum: float | None = None
    placement: str = "front"
    """``front`` oder ``advanced`` — vorn im Dialog oder unter „Weitere Einstellungen“."""
    doc: str = ""


@dataclass(frozen=True, slots=True)
class Recipe:
    """Ein eigener Baustein als Daten (Konzept §16)."""

    name: str
    title: str
    group: str
    document: Document
    """Der Ausschnitt: Ops, Parameter und Quellen-Metadaten, als gewöhnliches
    Dokument — die Auswertung ist dieselbe wie für ein Projekt."""
    payloads: dict[str, bytes] = field(default_factory=dict)
    """Inhalte eingebetteter Quellen des Ausschnitts. Ein Rezept aus einem
    eingelesenen Modell trägt sein Netz mit — Daten, kein Code."""
    exposed: tuple[ExposedParam, ...] = ()
    features: dict[str, str] = field(default_factory=dict)
    """Öffentlicher Merkmalsname → Merkmals-ID im ausgewerteten Körper
    (Konzept §18d): Der Dialog benennt, was nach außen sichtbar ist, sonst
    wäre die Provenienzkette an der Naht unterbrochen."""
    doc: str = ""
    format_version: int = FORMAT_VERSION
    range_report: Any = None
    """Der letzte Bereichstest (:mod:`range_check`), oder ``None``.

    Am Rezept, **nicht im Hash**: Der Hash ist die Version (§24.4), und das
    Prüfen darf aus dem Rezept kein anderes machen. ``to_data`` lässt den
    Bericht deshalb aus, ``save`` schreibt ihn als eigenes Feld daneben."""


def to_data(recipe: Recipe) -> dict[str, Any]:
    """Das Rezept als reine Daten, bereit für JSON."""
    return {
        "format_version": recipe.format_version,
        "name": recipe.name,
        "title": recipe.title,
        "group": recipe.group,
        "doc": recipe.doc,
        "document": document_to_data(recipe.document),
        "payloads": {
            key: base64.b64encode(value).decode("ascii")
            for key, value in sorted(recipe.payloads.items())
        },
        "exposed": [dataclasses.asdict(entry) for entry in recipe.exposed],
        "features": dict(sorted(recipe.features.items())),
    }


def from_data(data: dict[str, Any]) -> Recipe:
    """Ein Rezept aus seinen Daten. Der Dokument-Teil läuft durch die
    Migrationen des Dokumentformats — ein altes Rezept öffnet wie eine alte
    Projektdatei."""
    return Recipe(
        name=str(data["name"]),
        title=str(data.get("title") or data["name"]),
        group=str(data.get("group", "structure")),
        doc=str(data.get("doc", "")),
        # Durch die Migrationen, wie eine Projektdatei: Der Dokumentteil
        # eines Rezepts altert mit dem Dokumentformat, und eine Datei aus
        # der Zukunft wird abgewiesen statt falsch gelesen (``too_new``).
        document=document_from_data(migrate(dict(data["document"]))),
        payloads={
            key: base64.b64decode(value) for key, value in dict(data.get("payloads", {})).items()
        },
        exposed=tuple(ExposedParam(**entry) for entry in data.get("exposed", ())),
        features=dict(data.get("features", {})),
        format_version=int(data.get("format_version", 1)),
        range_report=_report_from(data.get("range_report")),
    )


def _report_from(data: Any) -> Any:
    """Der gespeicherte Bericht, oder ``None`` — er ist Zugabe, kein Muss."""
    if not data:
        return None
    from app.core.knowledge.parts.range_check import RangeFailure, RangeReport

    return RangeReport(
        checked=int(data.get("checked", 0)),
        failures=tuple(
            RangeFailure(values=dict(entry["values"]), reason=str(entry["reason"]))
            for entry in data.get("failures", ())
        ),
    )


def fingerprint(recipe: Recipe) -> str:
    """Der Hash über die kanonischen Daten — er **ist** die Version (§24.4).

    Kanonisch heißt: sortierte Schlüssel, keine Zeitstempel, nichts
    Maschinenabhängiges. Zwei gleiche Rezepte geben denselben Wert, jede
    Änderung einen anderen — und der Vergleich beim Öffnen eines Projekts ist
    damit derselbe wie für jeden anderen Baustein.
    """
    canon = json.dumps(to_data(recipe), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# --- Auswertung (E5): der PartFn-Ersatz ------------------------------------------


def build(
    recipe: Recipe,
    values: dict[str, float] | None = None,
    *,
    profile: Profile,
    quality: Quality = "fine",
    registry: Registry | None = None,
) -> PartResult:
    """Parameter hinein, ein Körper mit benannten Merkmalen heraus.

    Der Ausschnitt wird mit dem **Auswerter der Szene** gerechnet — derselbe
    Weg, denselben Regeln: Rückfallkette, ``auto:``-Toleranzen aus dem
    Profil, Quelltextprüfung für OpenSCAD-Schritte. Ein zweiter Auswerter nur
    für Rezepte wäre eine zweite Wahrheit.

    Läuft der Ausschnitt nicht auf **genau einen** Körper hinaus, hält das
    hier an (Konzept §18a): Ein Baustein ist eine Funktion, ein Stapel ein
    Ablauf, und aufnehmbar ist nur, was sich wie eine Funktion verhält.
    """
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import Project, ProjectSources

    document = _with_values(recipe.document, recipe, values or {})
    project = Project(document=document, sources=dict(recipe.payloads))
    result = evaluate(
        document,
        profile,
        quality=quality,
        registry=registry,
        sources=ProjectSources(project),
    )
    if result.stopped_at is not None:
        # ``evaluate`` wirft bei einem gescheiterten Schritt nicht — es setzt
        # ``stopped_at`` und behält, was bis dahin entstand. Für ein Projekt
        # ist das richtig (der Verlauf zeigt den Riss); für einen Baustein
        # wäre es ein halber Körper, der wie ein ganzer aussieht: Ein Rezept
        # aus Quader und Bohrung gäbe bei gescheiterter Differenz den Klotz
        # ohne Loch zurück, und der Bereichstest hielte ihn für bestanden.
        cause = next((str(entry.message) for entry in result.scene.report.findings), "")
        raise GeometryError(
            title=_("Das Rezept ließ sich nicht bis zum Ende rechnen."),
            detail=cause or _("Ein Schritt des Rezepts scheiterte an dieser Parameterkombination."),
            values={"recipe": recipe.name, "stopped_at": result.stopped_at},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    bodies = list(result.scene.objects.values())
    if len(bodies) != 1:
        raise ValidationError(
            field="recipe",
            # Ohne Platzhalter: ``show_details`` zeigt den Satz wörtlich und
            # hängt die ``values`` als eigene Zeilen darunter — ein ``{count}``
            # bliebe als geschweifte Klammer stehen (tests/test_errors.py).
            detail=_(
                "Dieses Rezept ergibt nicht genau einen Körper. Ein Baustein "
                "ist genau ein Teil — teilen Sie den Ausschnitt oder vereinen "
                "Sie die Körper, bevor Sie speichern."
            ),
            values={"count": len(bodies), "recipe": recipe.name},
            constraint="one_body",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    body = bodies[0]
    features: dict[str, Feature] = {}
    for public, internal in recipe.features.items():
        found = body.features.get(internal)
        if found is None:
            raise ValidationError(
                field="features",
                detail=_(
                    "Ein benanntes Merkmal gibt es im Ergebnis nicht mehr. "
                    "Benennen Sie die Merkmale des Rezepts neu, oder entfernen "
                    "Sie den Eintrag."
                ),
                values={"name": public, "missing": internal, "recipe": recipe.name},
                constraint="unknown_feature",
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        # **Mit dem Namen wechselt die Provenienz.** Das Rezept hat diesem
        # Merkmal einen Namen gegeben — ab jetzt ist es ein *erzeugtes*, wie
        # bei jedem eingebauten Baustein: Eine Passung darf darauf zeigen, der
        # Agent darf darauf verweisen (§21.3, Leitprinzip 5). Als ``detected``
        # weitergereicht verwaiste es still bei der nächsten Wiedererkennung —
        # gemessen am E6-Durchlauf: Der Deckel eines Rezepts aus einem
        # eingelesenen Netz verschwand nach dem Einsetzen als
        # ``perceive.orphaned``, während derselbe Deckel aus ``create_box``
        # (dort von Haus aus erzeugt) blieb. Genau das ist die Naht, von der
        # Konzept §18d spricht.
        features[public] = dataclasses.replace(found, id=public, provenance="generated")
    return PartResult(
        mesh=body.mesh, features=features, findings=list(result.scene.report.findings)
    )


def _with_values(document: Document, recipe: Recipe, values: dict[str, float]) -> Document:
    """Der Ausschnitt mit den eingesetzten Parameterwerten — als Kopie.

    Nur freigegebene Parameter sind setzbar; alles andere wäre ein Weg, am
    Dialog vorbei in ein fremdes Rezept zu greifen. Der Wert ersetzt Wert
    **und** Ausdruck des Projektparameters: Ein Ausdruck bliebe sonst die
    stärkere Quelle, und der Dialogwert täte nichts.
    """
    exposed = {entry.name for entry in recipe.exposed}
    unknown = sorted(set(values) - exposed)
    if unknown:
        raise ValidationError(
            field="values",
            detail=_("Diesen Parameter gibt das Rezept nicht nach außen."),
            values={"unknown": ", ".join(unknown), "recipe": recipe.name},
            constraint="unknown",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    parameters = dict(document.parameters)
    for name, value in values.items():
        current = parameters.get(name)
        if current is None:
            raise ValidationError(
                field="exposed",
                detail=_(
                    "Ein freigegebener Parameter steht nicht im "
                    "Ausschnitt. Legen Sie ihn im Projekt an, bevor Sie ihn "
                    "freigeben."
                ),
                values={"name": name, "recipe": recipe.name},
                constraint="unknown_parameter",
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        parameters[name] = dataclasses.replace(current, value=float(value), expression="")
    return dataclasses.replace(document, parameters=parameters)


# --- Anschluss an Katalog und Register (E1/E5) -----------------------------------


def _params_class(recipe: Recipe) -> type[BaseParams]:
    """Die Parameterklasse des Rezepts — aus Daten, denselben Weg entlang.

    Eine **rohe** Klasse, kein fertiges Dataclass: ``op_params`` friert
    selbst ein und leitet das Schema ab — wie bei jeder deklarierten
    Parameterklasse, nur dass Annotationen und ``param()``-Felder hier aus
    Daten entstehen. Registrierung und Bereichstest teilen sich diese eine
    Fassung; zwei drifteten auseinander.
    """
    namespace: dict[str, Any] = {
        "__annotations__": {entry.name: float for entry in recipe.exposed},
        "__module__": __name__,
    }
    for entry in recipe.exposed:
        namespace[entry.name] = param(
            title=entry.title,
            default=float(entry.default),
            unit=entry.unit,
            minimum=entry.minimum,
            maximum=entry.maximum,
            placement="front" if entry.placement == "front" else "advanced",
            doc=entry.doc or entry.title,
        )
    return op_params(type(f"Recipe_{recipe.name}_Params", (BaseParams,), namespace))


def range_check(
    recipe: Recipe,
    profile: Profile,
    *,
    progress: Any = None,
    cancelled: Any = None,
) -> Recipe:
    """Der Bereichstest über die freigegebenen Grenzen (§24.5, Konzept E3).

    Fährt die Ecken mit der **echten Auswertung** und gibt das Rezept mit
    Bericht zurück — der Hash bleibt derselbe, denn der Bericht steht
    außerhalb (siehe ``Recipe.range_report``). Der Aufrufer entscheidet, ob
    ein gebrochener Bericht das Speichern verhindert; §24.5 verlangt den
    Warnhinweis im Katalog, kein Verbot.
    """
    from app.core.knowledge.parts.range_check import check

    params_cls = _params_class(recipe)

    def built(values: BaseParams) -> PartResult:
        raw = {entry.name: float(getattr(values, entry.name)) for entry in recipe.exposed}
        return build(recipe, raw, profile=profile)

    report = check(params_cls, built, profile, progress=progress, cancelled=cancelled)
    return dataclasses.replace(recipe, range_report=report)


def register(
    recipe: Recipe,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
    *,
    source: str = RECIPE_SOURCE,
) -> None:
    """Macht aus dem Rezept einen Baustein wie jeden anderen.

    Das Parameterschema entsteht aus den freigegebenen Parametern — dieselbe
    Deklaration, die ein eingebauter Baustein über ``param()`` trägt, nur aus
    Daten gebaut. Registriert wird über denselben Weg wie jede ``.py``
    (``ops.register_all``-Mechanik), damit Katalog, Palette, Dialog und
    Provenienz nichts Neues lernen müssen.

    ``fn`` wertet mit dem **Standardprofil** aus — das trifft Vorschaubild
    und Bereichstest. Beim echten Einsetzen läuft stattdessen
    ``build_with_profile`` mit dem Profil des Dokuments (``ops.insert``
    bevorzugt es): Eine ``auto:``-Toleranz im Rezept rechnet dann mit dem
    Material des Kunden, nicht mit unserem.
    """
    from app.core.knowledge.parts import ops as part_ops
    from app.core.knowledge.parts.registry import PARTS

    params_cls = _params_class(recipe)

    def build_with_profile(params: BaseParams, profile: Profile | None) -> PartResult:
        chosen = profile or _default_profile()
        values = {entry.name: float(getattr(params, entry.name)) for entry in recipe.exposed}
        return build(recipe, values, profile=chosen)

    def fn(params: BaseParams) -> PartResult:
        return build_with_profile(params, None)

    spec = PartSpec(
        name=recipe.name,
        title=recipe.title,
        group=recipe.group,
        params=params_cls,
        fn=fn,
        build_with_profile=build_with_profile,
        version=fingerprint(recipe),
        features=tuple(recipe.features),
        doc=recipe.doc or recipe.title,
        source=source,
        range_passed=(recipe.range_report.passed if recipe.range_report is not None else None),
        # Für die Reise: Das Speichern eines Projekts, das diesen Baustein
        # benutzt, bettet genau diese Daten in den Container ein — ohne die
        # Datei im Nutzerordner erneut zu lesen, die ein mitgereistes Rezept
        # gar nicht hat.
        recipe_data=file_data(recipe),
    )
    target = parts or PARTS
    target.register(spec)
    try:
        part_ops.register_one(spec, registry)
    except Exception:
        # Halb registriert ist schlimmer als gar nicht: Ein Katalogeintrag
        # ohne Operation ist ein Knopf, dessen Klick in einem
        # ``InternalError`` endet. Der Eintrag geht zurück, der Fehler weiter.
        target.remove(spec.name)
        raise


def _default_profile() -> Profile:
    """Das Profil für Vorschau und Bereichstest, wo keines mitkommt."""
    from app.core.knowledge import profiles

    printers = profiles.printer_profiles()
    materials = profiles.material_profiles()
    return profiles.make_profile(next(iter(printers)), next(iter(materials)))


# --- Ablage im Nutzerordner -------------------------------------------------------


def recipes_dir(base: Path | None = None) -> Path:
    """Wo die Rezepte liegen: ein Unterordner des Bausteinordners."""
    return (base or user_parts_dir()) / RECIPES_DIRNAME


def save(recipe: Recipe, directory: Path | None = None, *, overwrite: bool = False) -> Path:
    """Schreibt das Rezept als eine Datei; der Dateiname ist der Name.

    Eine vorhandene Datei ist Kundenarbeit: Ersetzt wird nur mit
    ``overwrite=True`` — „Ändern heißt neu speichern" ist der gewollte Fall,
    und den sagt der Aufrufer ausdrücklich. Ohne diese Absicht hält die
    Funktion an, statt still zu tauschen. Der Dialog lief am 25.08.2026 in
    genau diese Falle: ``register()`` lehnte den doppelten Namen ab, nachdem
    ``save()`` die alte Datei bereits überschrieben hatte — die Meldung sprach
    von einem Fehlschlag, die Platte trug längst den Verlust.
    """
    folder = ensure_dir(recipes_dir() if directory is None else directory)
    target = folder / f"{recipe.name}.json"
    if target.exists() and not overwrite:
        raise ValidationError(
            field="title",
            detail=_(
                "Unter diesem Namen liegt schon ein eigener Baustein. Wählen "
                "Sie einen anderen Namen — oder ersetzen Sie den vorhandenen "
                "ausdrücklich."
            ),
            values={"recipe": recipe.name, "file": target.name},
            constraint="exists",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    target.write_text(
        json.dumps(file_data(recipe), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def file_data(recipe: Recipe) -> dict[str, Any]:
    """Die Daten samt Bereichstest-Bericht — was eine Rezeptdatei trägt.

    Dieselbe Gestalt für die Datei im Nutzerordner und für die Reise in einer
    Projektdatei: Der Bericht hängt **neben** den Daten, nicht darin (siehe
    ``Recipe.range_report``) — Prüfen macht aus dem Rezept kein anderes, aber
    der Empfänger soll die Warnung aus §24.5 sehen, ohne selbst zu prüfen.
    """
    data = to_data(recipe)
    if recipe.range_report is not None:
        data["range_report"] = {
            "checked": recipe.range_report.checked,
            "failures": [
                {"values": entry.values, "reason": entry.reason}
                for entry in recipe.range_report.failures
            ],
        }
    return data


@dataclass(slots=True)
class LoadResult:
    """Was aus dem Rezeptordner herausgekommen ist — wie bei den ``.py``s."""

    loaded: tuple[str, ...] = ()
    findings: list[Finding] = field(default_factory=list)


def load_all(
    directory: Path | None = None,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
) -> LoadResult:
    """Liest jedes Rezept des Ordners und registriert es.

    Eine kaputte Datei hält den Start nicht an, sondern wird ein Befund —
    dieselbe Haltung wie bei den ``.py``-Bausteinen (Regel 17): Der Rest des
    Katalogs bleibt benutzbar, und der Befund nennt Datei und Grund.
    """
    folder = recipes_dir() if directory is None else directory
    if not folder.is_dir():
        return LoadResult()
    loaded: list[str] = []
    findings: list[Any] = []
    for path in sorted(folder.glob("*.json")):
        try:
            recipe = from_data(json.loads(path.read_text(encoding="utf-8")))
            register(recipe, parts, registry)
            loaded.append(recipe.name)
            # Regel 13 hält nur mit Regel 11 zusammen: Ein Rezept darf
            # Quelltext tragen (``create_from_scad``), und dann muss der
            # Nutzer es erfahren, **bevor** er den Baustein rechnen lässt —
            # dieselbe Auskunft, die ``foreign.findings_for`` einer geöffneten
            # Projektdatei gibt. Eine Datei im eigenen Ordner ist keine
            # Entwarnung: Rezepte werden weitergegeben.
            from app.core.scene.foreign import findings_for

            for warning in findings_for(recipe.document):
                findings.append(
                    dataclasses.replace(
                        warning, values={**dict(warning.values), "recipe": recipe.name}
                    )
                )
        except Exception as problem:  # Regel 17: Befund statt Abbruch
            _log.warning("recipe %s failed to load: %s", path.name, problem)
            findings.append(
                Finding(
                    code="parts.recipe_failed",
                    severity="warning",
                    message=_("Ein eigenes Rezept ließ sich nicht laden."),
                    values={"file": path.name, "reason": str(problem)[:200]},
                )
            )
    return LoadResult(loaded=tuple(loaded), findings=findings)


# --- Der Ausschnitt (die Naht zu E4) ---------------------------------------------


def capture(
    document: Document,
    payloads: dict[str, bytes],
    *,
    name: str,
    title: str,
    group: str,
    op_ids: tuple[int, ...],
    exposed: tuple[ExposedParam, ...],
    features: dict[str, str],
    doc: str = "",
    profile: Profile,
) -> Recipe:
    """Aus einem echten Dokument den Ausschnitt herausschneiden.

    Die Naht zu Paket E4: Der Dialog sammelt Name, Titel, Gruppe, die
    gewählten Schritte, die freigegebenen Parameter samt ihren Angaben und die
    benannten Merkmale — hier entsteht daraus das Rezept, und die **Probe
    läuft sofort**: einmal auswerten, genau ein Körper, jedes benannte
    Merkmal vorhanden (Konzept §18a und §18d). Was hier durchgeht, steht
    danach im Katalog; was nicht, sagt beim Speichern warum, nicht später
    beim Benutzen.

    Mitgenommen werden alle Projektparameter des Dokuments — sie sind kleine
    Daten, und welche der Ausschnitt wirklich liest, entscheiden seine
    Ausdrücke — und nur die Quellen, auf die der Ausschnitt sich bezieht.
    """
    if not features:
        # §24.1 verlangt es ohnehin beim Registrieren — aber dort hieße der
        # Fehler „beim Laden", und der Kunde stünde vor einem gespeicherten
        # Rezept, das nie auftaucht. Die Regel gehört an die Stelle, an der
        # sie behebbar ist: hier, beim Speichern (Konzept §18d).
        raise ValidationError(
            field="features",
            detail=_(
                "Ein Baustein verspricht benannte Merkmale — geben Sie "
                "mindestens einem Merkmal des Ergebnisses einen Namen."
            ),
            constraint="empty",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    wanted = set(op_ids)
    ops = [entry for entry in document.ops if entry.id in wanted]
    if not ops:
        raise ValidationError(
            field="op_ids",
            detail=_("Der Ausschnitt ist leer — wählen Sie mindestens einen Schritt."),
            constraint="empty",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    used_sources = {key: source for key, source in document.sources.items() if _mentions(ops, key)}
    slice_document = dataclasses.replace(
        document,
        ops=ops,
        sources=used_sources,
        transactions=[],
        chat=[],
        fits=[],
    )
    recipe = Recipe(
        name=name,
        title=title,
        group=group,
        document=slice_document,
        payloads={key: payloads[key] for key in used_sources if key in payloads},
        exposed=exposed,
        features=dict(features),
        doc=doc,
    )
    build(recipe, profile=profile)  # die Probe — wirft mit Handlungsvorschlag
    return recipe


def _mentions(ops: list[Any], source_id: str) -> bool:
    """Ob ein Schritt des Ausschnitts diese Quelle nennt — irgendwo in seinen
    Werten, denn der Parametername dafür gehört der jeweiligen Operation."""
    for entry in ops:
        for value in entry.params.values():
            if value == source_id:
                return True
    return False


# --- Die Reise in der Projektdatei (Konzept §17.1) --------------------------------


def for_container(document: Document, parts: PartRegistry | None = None) -> dict[str, str]:
    """Was mit diesem Projekt reisen muss: je benutztem Rezept sein JSON-Text.

    Entscheidung Robert, 24.08.2026: Ein Rezept darf mitreisen — es nennt
    Namen registrierter Operationen und Zahlen, seine Sicherheitslage ist die
    einer ``project.json``. Mitgereiste reisen weiter: Wer eine Datei
    bekommt und weitergibt, gibt den Baustein mit, sonst endet die Kette beim
    zweiten Empfänger mit ``parts.missing``.
    """
    from app.core.knowledge.parts.registry import PARTS, used_parts

    source = parts or PARTS
    travelling: dict[str, str] = {}
    for name in sorted(set(used_parts(document.ops))):
        if not source.has(name):
            continue
        spec = source.get(name)
        if spec.recipe_data is None:
            continue
        travelling[name] = json.dumps(
            dict(spec.recipe_data), ensure_ascii=False, indent=2, sort_keys=True
        )
    return travelling


def adopt(
    data: dict[str, Any],
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
) -> list[Finding]:
    """Nimmt ein mitgereistes Rezept auf — „lokal schlägt mitgereist, immer".

    Drei Lagen (Konzept §17.1):

    * Der Name ist frei: registrieren, als ``travelled`` gekennzeichnet.
      In den Nutzerordner geschrieben wird nichts — das Rezept gehört der
      Datei, mit der es kam, und reist mit ihr weiter.
    * Es gibt lokal denselben Stand (gleicher Abdruck): nichts zu tun.
    * Es gibt lokal einen **anderen** Stand: Der lokale gewinnt — alles
      andere wäre eine Datei, die von außen den Werkzeugkasten des Kunden
      umschreibt. Der mitgereiste bekommt einen abgeleiteten Namen und steht
      daneben im Katalog; dass das Projekt mit dem lokalen anders rechnet,
      meldet der §24.4-Abdruckvergleich beim Öffnen ohnehin.

    Eine kaputte Datei ist ein Befund, kein Abbruch (Regel 17) — der Rest
    des Projekts öffnet.
    """
    from app.core.knowledge.parts.registry import PARTS

    source = parts or PARTS
    try:
        arrived = from_data(data)
        mark = fingerprint(arrived)
        name = arrived.name
        if source.has(name):
            local = source.get(name)
            if local.version == mark:
                return []
            name = f"{arrived.name}_travelled"
            if source.has(name):
                # Noch einmal geöffnet in derselben Sitzung — oder zwei
                # Projekte mit demselben fremden Rezept: derselbe Abdruck
                # heißt dasselbe Rezept, ein anderer bleibt ein Befund statt
                # einer endlosen Namensreihe.
                if source.get(name).version == mark:
                    return []
                raise ValidationError(
                    field="recipe",
                    detail=_(
                        "Zwei verschiedene mitgereiste Fassungen desselben "
                        "Bausteins in einer Sitzung — die zweite wird nicht "
                        "aufgenommen. Schließen Sie das andere Projekt und "
                        "öffnen Sie diese Datei erneut."
                    ),
                    values={"recipe": arrived.name},
                    constraint="exists",
                    suggestions=(CANCEL,),
                )
            arrived = dataclasses.replace(arrived, name=name)
        register(arrived, source, registry, source=TRAVELLED_SOURCE)
        return []
    except Exception as problem:  # Regel 17: Befund statt Abbruch
        _log.warning("travelled recipe failed to adopt: %s", problem)
        return [
            Finding(
                code="parts.recipe_failed",
                severity="warning",
                message=_("Ein mitgereistes Rezept ließ sich nicht aufnehmen."),
                values={"reason": str(problem)[:200]},
            )
        ]


def replace(
    recipe: Recipe,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
    directory: Path | None = None,
) -> Path:
    """Legt ein Rezept an **oder** ersetzt seinen vorhandenen Stand — Datei,
    Katalogeintrag und Operation zusammen.

    Ein Weg für beide Fälle (Absprache mit der Dialogseite, 26.08.2026):
    Ist der Name frei, wirkt es wie ``save`` plus ``register``; ist er
    vergeben, werden alle drei Seiten getauscht. „Ersetzen oder anlegen"
    bleibt damit eine Frage der Knopfbeschriftung, nicht des Ablaufs.

    **Die Operation wird wirklich neu gebunden.** ``register_one`` hält den
    ``PartSpec`` als Vorgabewert seiner ``run``-Funktion fest — ein neuer
    Katalogeintrag allein ändert die Rechnung nicht (b0s Messung vom
    26.08.2026). Deshalb erst abmelden, dann neu registrieren.

    Scheitert ein Schritt, wird zurückgestellt, was schon getauscht war:
    Halb ersetzt wäre die schlimmste aller Lagen — Katalog neu, Rechnung
    alt, Platte irgendwo dazwischen.
    """
    from app.core.knowledge.parts import ops as part_ops
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    source = parts or PARTS
    operations = registry or REGISTRY
    op = part_ops.op_name(recipe.name)
    previous = source.get(recipe.name) if source.has(recipe.name) else None

    if previous is not None:
        source.remove(recipe.name)
        operations.remove(op)
    try:
        register(recipe, source, operations)
    except Exception:
        if previous is not None:
            source.register(previous)
            part_ops.register_one(previous, operations)
        raise
    try:
        return save(recipe, directory, overwrite=True)
    except Exception:
        # Die Platte hat den alten Stand behalten — dann behalten ihn auch
        # Katalog und Register, sonst rechnete die Sitzung mit einem Stand,
        # den der nächste Start nicht mehr kennt.
        source.remove(recipe.name)
        operations.remove(op)
        if previous is not None:
            source.register(previous)
            part_ops.register_one(previous, operations)
        raise
