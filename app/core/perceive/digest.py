"""Der Steckbrief der Szene für den Agenten (Bauplan §23).

Was der Agent zu sehen bekommt, in Worten: Objekte mit ihren Maßen, Merkmale
mit ihren Namen, die Parameter, die aktuelle Auswahl, der Stapel in Kurzform.
Der Agent bezieht sich auf diese Namen und nie auf Koordinaten (Leitprinzip
5) — dieser Text ist also das Vokabular, auf dem das ganze Gespräch läuft.

Er ist zum Lesen geschrieben. Eine Wand aus JSON trüge dieselben Fakten und
wäre schwerer zu durchdenken — für das Modell so gut wie für den Menschen, der
nachsieht, was dem Modell gesagt wurde.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from pathlib import PurePosixPath

from app.core.perceive.relations import sleeve_at
from app.core.types import Document, Feature, FeatureId, ObjectId, Operation, Scene, SceneObject
from app.core.units import format_length, round_display
from app.i18n import TranslatableText, tr

#: Wie viele Zeichen ein Name aus einer fremden Datei im Steckbrief belegen
#: darf.
#:
#: Sechzig reichen für jeden Namen, den jemand vergibt („Deckel hinten links,
#: 3 mm Wand"), und decken den Fall, der hier zählt: Objekt- und Dateinamen
#: stehen in der Projektdatei, Projektdateien wandern zwischen Leuten, und der
#: Steckbrief reist ungefiltert in den Prompt. Ein „Name" von zweitausend
#: Zeichen ist kein Name, sondern ein Text, den jemand anderes dem Modell
#: unterschieben will — und er verdrängt dabei das, was wirklich in der Szene
#: steht.
NAME_LIMIT = 60


def as_value(text: object) -> str:
    """Ein Wert aus fremder Hand, auf eine Zeile gebracht und gekürzt (§32).

    **Der Umbruch ist der Punkt, nicht die Länge.** Der Steckbrief ist ein
    zeilenweiser Text, und eine Zeile darin ist eine Aussage über ein Objekt.
    Ein Wert mit ``\n`` darin schreibt in diesen Text hinein — beliebig viele
    eigene Zeilen, in derselben Form, in der die echten stehen. Das ist die
    ganze Mechanik von Prompt-Injektion über Daten, und sie kostet eine Zeile
    Code, sie zuzuhalten.

    Ohne Anführungszeichen, weil nicht jede Stelle einen Rahmen verträgt: Eine
    Einheit hinter einer Zahl, eine Passungskennung, der Name einer Operation
    und ihre Argumente werden vom Modell **wörtlich weiterverwendet** — ein
    Rahmen darum sähe aus, als gehörten die Zeichen zum Wert. Wo ein Rahmen
    passt, steht :func:`as_name` darüber.
    """
    flat = " ".join(str(text).split())
    if len(flat) > NAME_LIMIT:
        flat = flat[: NAME_LIMIT - 1] + "…"
    return flat


def as_name(text: TranslatableText | str) -> str:
    """Ein Name aus fremder Hand, so wie er in den Steckbrief darf (§32).

    Drei Dinge: Zeilenumbrüche und Steuerzeichen fallen weg (:func:`as_value`),
    alles wird auf :data:`NAME_LIMIT` gekürzt, und das Ergebnis steht in
    Anführungszeichen.

    **Das Anführungszeichen selbst muss dabei aus dem Wert heraus.** Sonst
    schließt der Name den Rahmen, den er bekommen hat: ``Deckel" ANWEISUNG:
    …`` kam als ``"Deckel" ANWEISUNG: …"`` an, und was hinter dem zweiten
    Zeichen steht, liest sich wie Text der Anwendung. Es wird durch das
    einfache ersetzt und nicht gelöscht — ein Name mit Zoll-Angabe behält so
    seine Bedeutung.

    Die Rahmung dazu steht im Kontext
    (:data:`app.core.agent.context.FOREIGN_NAMES_NOTICE`): Kürzen sagt, wie
    viel Platz ein Name bekommt, der Rahmen sagt, was ein Name ist.
    """
    plain = str(text).replace('"', "'")
    return f'"{as_value(plain)}"'


def digest(
    scene: Scene,
    document: Document | None = None,
    selection: tuple[ObjectId, str] | None = None,
    only: Collection[ObjectId] | None = None,
) -> str:
    """Die ganze Szene in der Form, die §23 beschreibt.

    ``only`` schränkt die Objektzeilen ein — für das Werkzeug ``read_digest``,
    das mitten im Zug nach einem einzelnen Objekt fragen kann. Alles andere
    (Parameter, Passungen, Quellen, Verlauf) bleibt vollständig: es gehört
    zur Szene, nicht zu einem Objekt.
    """
    plates = _plate_count(scene)
    lines: list[str] = [_scene_line(scene)]

    if scene.parameters:
        # Name und Einheit stehen so in der Projektdatei, wie jemand sie
        # geschrieben hat — beide durch :func:`as_value`, damit aus „mm" keine
        # zweite Zeile wird (§32).
        values = " · ".join(
            f"{as_value(name)}={round_display(parameter.value):g} {as_value(parameter.unit)}"
            for name, parameter in scene.parameters.items()
        )
        lines.append(f"{tr('Parameter')}: {values}")

    if selection is not None:
        object_id, feature_id = selection
        lines.append(f"{tr('Auswahl')}: {object_id}" + (f" · {feature_id}" if feature_id else ""))

    if document is not None:
        lines.extend(_fit_lines(document, scene))
        lines.extend(_print_settings_line(document))
        lines.extend(_source_lines(document))

    for object_id, entry in scene.objects.items():
        if only is not None and object_id not in only:
            continue
        lines.extend(_object_lines(object_id, entry, plates))

    lines.extend(_finding_lines(scene))
    if document is not None:
        lines.extend(_stack_lines(document))
    return "\n".join(lines)


def _fit_lines(document: Document, scene: Scene) -> list[str]:
    """Die Passungen des Projekts, mit ihrem Zustand (§14, §26.1).

    Der Agent konnte Passungen anlegen, aber nie nachsehen, welche es gibt —
    er sah nur die Verletzungen, die es bis in den Prüfbericht schafften.
    Verletzt oder nicht steht dabei: die Angabe kommt aus denselben Befunden,
    ausgewiesen am Namen der Passung.
    """
    if not document.fits:
        return []
    violated = {
        str(finding.values.get("fit", ""))
        for finding in scene.report.findings
        if finding.code == "fit.violated"
    }
    parts = []
    for fit in document.fits:
        state = f" — {tr('verletzt')}" if fit.name in violated else ""
        # Alle fünf Felder kommen aus der Projektdatei (§32). Ohne Rahmen:
        # Der Name einer Passung ist die Kennung, mit der der Agent sie
        # anspricht — in Anführungszeichen sähe er aus, als gehörten sie dazu.
        parts.append(
            f"{as_value(fit.name)} {as_value(fit.a)} ↔ {as_value(fit.b)} "
            f"({as_value(fit.kind)}, {as_value(fit.tolerance)}){state}"
        )
    return [f"{tr('Passungen')}: " + " · ".join(parts)]


def _print_settings_line(document: Document) -> list[str]:
    """Was eingestellt ist, in einer Zeile (§29, §26.1).

    Nur wenn das Projekt eigene Einstellungen trägt — ``None`` heißt, die
    Auflösung aus Stufe, Material und Drucker gilt, und Drucker wie Material
    stehen schon in der Szenenzeile. Nicht das ganze Profil: die Zeile sagt,
    was gilt; was einzustellen wäre, ist Sache der Analyse.
    """
    settings = document.print_settings
    if settings is None:
        return []
    walls = settings.shell.wall_count
    width = settings.layers.line_width
    # Titel und Stufe stehen im Projekt, also gerahmt beziehungsweise
    # abgeflacht (§32) — der Titel ist ein Name, die Stufe ein Schlüssel.
    return [
        f"{tr('Druckeinstellungen')}: {as_name(settings.title)} ({as_value(settings.quality)}), "
        f"{walls} {tr('Wände')} × {width:g} mm = {settings.wall_thickness:g} mm {tr('Wand')}"
    ]


def _source_lines(document: Document) -> list[str]:
    """Woher die Netze kommen (§16.3, §26.1).

    „Mach es wie beim importierten Deckel" scheitert sonst daran, dass der
    Agent nie erfährt, was importiert wurde. Nur der Dateiname — der Pfad ist
    relativ zur Projektdatei und sagt dem Modell nichts. Und nur so viel davon,
    wie ein Name lang sein darf (:func:`as_name`): Er kommt aus einer fremden
    Datei und reist ungefiltert in den Prompt.
    """
    if not document.sources:
        return []
    parts = [
        f"{source_id} {as_name(PurePosixPath(source.path).name)} ({as_value(source.kind)})"
        for source_id, source in document.sources.items()
    ]
    return [f"{tr('Quellen')}: " + " · ".join(parts)]


def _scene_line(scene: Scene) -> str:
    profile = scene.profile
    printer = profile.printer.id if profile else "-"
    material = profile.material.id if profile else "-"
    state = ""
    if profile is not None:
        state = f" ({tr('kalibriert') if profile.material.calibrated else tr('Startwert')})"
    plates = _plate_count(scene)
    spread = f", {plates} {tr('Platten')}" if plates > 1 else ""
    return (
        f"{tr('Szene')}: {len(scene.objects)} {tr('Objekte')}{spread}, "
        f"{tr('Drucker')} {printer}, {tr('Material')} {material}{state}"
    )


def _plate_count(scene: Scene) -> int:
    """Wie viele Druckplatten die Szene belegt.

    **Warum das überhaupt im Steckbrief steht.** Der Agent darf *Auf dem Bett
    anordnen* aufrufen, und diese Operation verteilt die Objekte auf Platten
    (``arrange_bed``, ``by_material``). Bis zum 03.09.2026 stand die Platte in
    der Szene (``SceneObject.plate``), wurde vom 3MF-Export gelesen — und kam
    im Steckbrief nicht vor. Der Agent handelte also auf Platten und war
    blind für das Ergebnis: Er konnte weder prüfen, was sein eigener Aufruf
    bewirkt hat, noch eine Frage wie „was liegt auf Platte 2" beantworten.

    Gezählt statt aufgezählt: Eine Szene auf einer Platte ist der Regelfall,
    und „1 Platte" an jeder Zeile wäre Rauschen (§26.1) — dieselbe
    Begründung, aus der das Material nur bei Abweichung dasteht.
    """
    return len({entry.plate for entry in scene.objects.values()})


def _object_lines(object_id: ObjectId, entry: SceneObject, plates: int = 1) -> list[str]:
    size = entry.mesh.bounds.size
    closed = tr("geschlossen") if entry.mesh.is_watertight else tr("offen")
    on_bed = tr("auf Bett") if abs(entry.mesh.bounds.minimum[2]) < 0.05 else ""
    facts = [
        f"{size[0]:.1f} × {size[1]:.1f} × {size[2]:.1f} mm",
        f"{entry.mesh.volume / 1000.0:.1f} cm³",
        closed,
    ]
    solidity = _solidity(entry)
    if solidity is not None:
        # Wie massiv das Teil ist, gemessen am Quader, den es einnimmt. Ein
        # Vollkörper liegt bei hundert Prozent, ein ausgehöhlter bei zwanzig,
        # ein gefüllter dazwischen — die eine Zahl, die sagt, wie viel Material
        # der Druck kostet, und sie steht schon in den beiden davor.
        facts.append(f"{solidity:.0%} {tr('massiv')}")
    if on_bed:
        facts.append(on_bed)
    if entry.material:
        # Nur, wenn es vom Projektmaterial abweicht — die Szenenzeile nennt
        # jenes bereits, und es an jedem Körper zu wiederholen wäre Rauschen (§26.1).
        facts.append(entry.material)
    if plates > 1:
        # Dieselbe Zurückhaltung wie beim Material: Wo alles auf einer Platte
        # liegt, sagt die Nummer nichts. Gezählt wird ab eins, wie überall, wo
        # ein Mensch sie liest (``export.writer`` schreibt ``plate + 1``).
        facts.append(f"{tr('Platte')} {entry.plate + 1}")

    lines = [f"{object_id}  {as_name(entry.name)}  " + ", ".join(facts)]
    lines.append("  " + _extent_line(entry))
    for feature_id, feature in entry.features.items():
        lines.append(
            "  " + _feature_line(feature_id, feature) + _wall_note(feature, entry.features)
        )
    return lines


def _wall_note(feature: Feature, features: Mapping[FeatureId, Feature]) -> str:
    """Die Wand, die dieses Merkmal mit seinem Nachbarn teilt — oder nichts.

    **Sie steht in keinem der beiden Merkmale.** Eine Bohrung nennt ihren
    Durchmesser, ein Zapfen den seinen, und dass zwischen beiden 3,40 mm
    Material liegen, ergibt sich erst aus ihrem Verhältnis
    (:func:`relations.sleeve_at`). Der Agent hat genau diesen Text und sonst
    nichts (§26.1): Ohne die Zeile liest er zwei unabhängige Zahlen und
    vergrößert die Bohrung eines Rohrs, bis von der Wand nichts übrig ist.

    An **beiden** Merkmalen und nicht nur an der Bohrung. Der Satz ist die
    Warnung vor einer Änderung, und geändert werden kann jedes von beiden —
    eine Auskunft nur an einem wäre an der anderen Hälfte der Fälle stumm.
    """
    sleeve = sleeve_at(feature, features)
    if sleeve is None:
        return ""
    partner = sleeve.wall if feature.id == sleeve.bore else sleeve.bore
    # **Ein Schlüssel, ein Satz.** „Wand" und „zu" einzeln zu übersetzen hieße,
    # zwei Wörter in den Katalog zu legen, die dort jeder andere Satz auch
    # brauchen kann — und die in keiner Sprache in dieser Reihenfolge stehen
    # müssen.
    note = tr("Wand {size} zu {feature}").format(
        size=format_length(sleeve.thickness), feature=partner
    )
    return f", {note}"


def _extent_line(entry: SceneObject) -> str:
    """Wo der Körper liegt, Achse für Achse.

    Die Maße sagen, wie groß er ist, nicht wo er steht — und Solidon legt
    einen Quader **um** den Ursprung. Das Modell nahm eine Ecke dort an und
    bohrte auf „mittig durch" in die Kante: ein Viertel abgetragen, und die
    Antwort lautete trotzdem „durchgehend und mittig". Herleiten ließ sich die
    Lage schon vorher aus den Flächenmitten — aber genau solche Rechnungen
    macht ein Sprachmodell falsch, und eine Zeile kostet nichts.
    """
    lower, upper = entry.mesh.bounds.minimum, entry.mesh.bounds.maximum
    spans = " · ".join(
        f"{name} {lower[index]:.1f} … {upper[index]:.1f}"
        for index, name in enumerate(("x", "y", "z"))
    )
    return f"{tr('liegt')}: {spans} mm"


def _solidity(entry: SceneObject) -> float | None:
    """Der Anteil des Hüllquaders, den der Körper wirklich ausfüllt.

    Nur, wo er etwas aussagt: ein offener Körper hat kein verlässliches
    Volumen, und ein Quader, der in einer Achse null misst, keinen Nenner.
    """
    size = entry.mesh.bounds.size
    box = size[0] * size[1] * size[2]
    if not entry.mesh.is_watertight or box <= 0.0:
        return None
    return float(entry.mesh.volume / box)


def _feature_line(feature_id: str, feature: Feature) -> str:
    """Ein Merkmal, mit dem Ort, an dem es sitzt.

    Die Position fehlte hier, und das machte den Steckbrief zu einer
    Beschreibung, auf die der Agent nicht handeln konnte: er las Durchmesser
    und Achse einer Bohrung und hatte nichts, was sagte, *wo* sie ist. Für
    „setz einen Baustein an hole_1" reicht der Name, für „bohr daneben"
    nicht. Die Oberfläche kennt die Position, seit sie anklickbar ist (§18.5)
    — der Agent sieht nur diesen Text (§26.1).
    """
    params = feature.params
    at = _place(params.get("centre"))
    if feature.kind == "hole":
        axis = _axis_name(params.get("axis", (0.0, 0.0, 1.0)))
        through = tr("Durchgang") if params.get("through") else tr("Sackloch")
        return (
            f"{feature_id}  Ø {format_length(float(params.get('diameter', 0.0)))}, "
            f"{tr('Achse')} {axis}, {through}{at}"
        )
    if feature.kind == "face":
        normal = _axis_name(params.get("normal", (0.0, 0.0, 1.0)))
        return (
            f"{feature_id}  {tr('planar')} {float(params.get('area', 0.0)):.0f} mm², "
            f"{tr('Normale')} {normal}{at}"
        )
    if feature.kind == "cone":
        # Der Öffnungswinkel steht vorn, weil er die Sache benennt: „90 Grad"
        # ist eine Senkung für eine Senkkopfschraube, „118 Grad" der Boden
        # einer gebohrten Sackbohrung. Und ob er eine Mulde ist oder ein
        # aufgesetzter Kegel, entscheidet, was man mit ihm tun kann.
        shape = tr("Senkung") if params.get("recess") else tr("Verjüngung")
        axis = _axis_name(params.get("axis", (0.0, 0.0, 1.0)))
        return (
            f"{feature_id}  {shape} {float(params.get('angle', 0.0)):.0f}°, "
            f"Ø {format_length(float(params.get('diameter', 0.0)))}, "
            f"{tr('Achse')} {axis}{at}"
        )
    if feature.kind == "pin":
        # Der Gegenpart zu ``hole``, und genauso aufgebaut: erst die Zahl, die
        # der Kunde nennt, dann Richtung und Länge. Ohne diesen Zweig las der
        # Agent „pin_1  pin" und wusste von einem Zapfen nur, dass es ihn gibt.
        axis = _axis_name(params.get("axis", (0.0, 0.0, 1.0)))
        return (
            f"{feature_id}  {tr('Zapfen')} Ø {format_length(float(params.get('diameter', 0.0)))}, "
            f"{tr('Achse')} {axis}, {tr('Höhe')} "
            f"{format_length(float(params.get('depth', 0.0)))}{at}"
        )
    if feature.kind == "thread":
        # Steigung dazu, denn sie macht das Gewinde: Ø6 mit 1,0 ist M6, Ø6 mit
        # 0,75 ist M6 fein, und in das eine passt die Schraube des anderen nicht.
        shape = tr("Innengewinde") if params.get("internal") else tr("Außengewinde")
        axis = _axis_name(params.get("axis", (0.0, 0.0, 1.0)))
        return (
            f"{feature_id}  {shape} Ø {format_length(float(params.get('diameter', 0.0)))}, "
            f"{tr('Steigung')} {format_length(float(params.get('pitch', 0.0)))}, "
            f"{tr('Achse')} {axis}{at}"
        )
    if feature.kind == "sphere":
        # Dieselbe Unterscheidung wie beim Kegel und aus demselben Grund: Eine
        # eingelassene Kalotte ist eine Pfanne (Kugellager, Magnettasche), eine
        # aufgesetzte eine Kuppel. Was man mit ihr tun kann, hängt daran.
        shape = tr("Pfanne") if params.get("recess") else tr("Kuppel")
        return f"{feature_id}  {shape} Ø {format_length(float(params.get('diameter', 0.0)))}{at}"
    if feature.kind == "torus":
        # Zwei Zahlen ohne Wort dazwischen, wie beim Kegel: Ringdurchmesser,
        # dann Rohrstärke. Ein Wort dazwischen wäre eine weitere Stelle, an der
        # eine Sprache fehlen kann — die Oberfläche hält es genauso.
        shape = tr("Kehle") if params.get("recess") else tr("Wulst")
        return (
            f"{feature_id}  {shape} Ø {format_length(float(params.get('diameter', 0.0)))} / "
            f"Ø {format_length(float(params.get('tube_diameter', 0.0)))}{at}"
        )
    if feature.kind == "fillet":
        # **R und nicht Ø.** Eine Verrundung wird über ihren Radius benannt:
        # so sagt es der Kunde, so steht es in Fusion, so heißt sie im Slicer.
        shape = tr("Hohlkehle") if params.get("recess") else tr("Verrundung")
        # **Die Achse nur, wenn es eine gibt.** Eine Verrundung an einer Kante
        # läuft entlang einer Achse; die Ecke, an der drei zusammentreffen, ist
        # ein Kugelstück und hat keine. Mit einem Vorgabewert stand dort „Achse
        # +Z" an jeder der acht Ecken eines rundum verrundeten Quaders — eine
        # Zahl, die der Agent für eine Auskunft hält. Dritter Fund derselben
        # Bauart an einem Tag, diesmal in frisch geschriebenem Code.
        direction = params.get("axis")
        along = f", {tr('Achse')} {_axis_name(direction)}" if direction is not None else ""
        size = format_length(float(params.get("radius", 0.0)))
        return f"{feature_id}  {shape} R{size}{along}{at}"
    if feature.kind == "edge_loop":
        # ``loops`` trägt nur die Sammelzeile, die ``detect_edge_loops`` ab
        # ihrer Obergrenze anhängt. Ohne diesen Zweig stünde dort eine einzelne
        # Schleife mit zehntausend offenen Kanten — eine falsche Auskunft statt
        # einer verkürzten.
        more = int(params.get("loops", 0))
        if more:
            return f"{feature_id}  {more} {tr('weitere offene Stellen')}"
        return f"{feature_id}  {params.get('open_edges', 0)} {tr('offene Kanten')}"
    # **Der Fallback nennt den englischen Schlüssel.** Er sieht aus wie ein Name
    # — genau daran sind pin, thread, sphere, torus und fillet vorbeigelaufen,
    # ohne dass ein Test etwas sagte.
    #
    # ``mypy`` hält diese Zeile inzwischen für unerreichbar, und für alles, was
    # ``FeatureKind`` zulässt, hat es recht: Die neun Arten sind oben
    # vollständig behandelt, und `tests/test_digest_and_fits.py` hält das fest.
    # Stehen bleibt sie trotzdem, weil der Typ nichts garantiert, was aus einer
    # **Projektdatei** kommt: `_feature_from_data` liest `kind` aus JSON, und
    # eine Datei aus einer neueren Fassung kann eine Art tragen, die es hier
    # noch nicht gibt. Dann ist eine englische Zeile besser als ein Absturz
    # mitten im Steckbrief.
    return f"{feature_id}  {feature.kind}{at}"  # type: ignore[unreachable]


def _place(centre: object) -> str:
    """``, bei (25, -15, 8)`` — oder nichts, bei einem Merkmal ohne Ort."""
    if not isinstance(centre, list | tuple) or len(centre) != 3:
        return ""
    try:
        numbers = ", ".join(_rounded(float(value)) for value in centre)
    except TypeError, ValueError:
        return ""
    return f", {tr('bei')} ({numbers})"


def _rounded(value: float) -> str:
    """Eine Null bleibt eine Null.

    Die Mittelpunkte kommen aus einer Rechnung, und ein zentrierter Quader
    landet dabei nicht auf 0, sondern auf -1.11022e-16. Für den Steckbrief ist
    das schädlich: der Agent liest ihn als Text und nimmt eine
    Zehn-hoch-minus-sechzehn für einen Wert, der etwas bedeutet — er ist
    darauf angewiesen, dass dasteht, was gemeint ist. Ein Zehntausendstel
    Millimeter unterschreitet jede Fertigungstoleranz, die dieses Gerät
    einhalten kann; darunter ist es Rechenrauschen.
    """
    return f"{0.0 if abs(value) < 1e-4 else value:g}"


def _axis_name(vector: tuple[float, float, float]) -> str:
    """Macht aus einer Richtung etwas Lesbares: +Z statt (0, 0, 1)."""
    names = ("X", "Y", "Z")
    largest = max(range(3), key=lambda index: abs(vector[index]))
    sign = "+" if vector[largest] >= 0 else "-"
    return f"{sign}{names[largest]}"


def _finding_lines(scene: Scene) -> list[str]:
    """Warnungen und Hinweise gehören in den Steckbrief — der Agent muss
    wissen, worauf er steht (§17.3, §26.1).
    """
    lines: list[str] = []
    for finding in scene.report.findings:
        if finding.severity == "info":
            continue
        marker = tr("Warnung") if finding.severity == "warning" else tr("Fehler")
        lines.append(f"  {marker.lower()} {finding.message}")
    return lines


#: Wie viele Parameter eine Op in der Verlaufszeile höchstens nennt. Der
#: Verlauf ist eine Zeile je Projekt, keine zweite Projektdatei.
_STACK_PARAM_LIMIT = 3


def _stack_lines(document: Document) -> list[str]:
    """Der Stapel in Kurzform — mit den gesetzten Hauptwerten (§26.1).

    Nur Titel und Op-Nummern trugen nichts: der Agent konnte aus dem Verlauf
    weder lernen, mit welchem Durchmesser gebohrt wurde, noch, was „t3"
    eigentlich getan hat. Jetzt steht die Op mit ihren wichtigsten Werten da;
    Objektlisten und Skizzen bleiben draußen, die stehen im Steckbrief selbst.
    """
    if not document.transactions:
        return []
    operations = {operation.id: operation for operation in document.ops}
    parts = []
    for transaction in document.transactions:
        calls = ", ".join(
            _op_call(operations[entry]) if entry in operations else str(entry)
            for entry in transaction.ops
        )
        by = tr("Agent") if transaction.origin.by == "agent" else tr("Nutzer")
        # Der Titel einer Transaktion ist ein Name aus der Projektdatei wie
        # jeder andere — und einer, den der Agent selbst vorgeschlagen haben
        # kann (§32).
        parts.append(f"{transaction.id} {as_name(transaction.title)} ({calls}, {by})")
    return [f"{tr('Verlauf')}: " + " · ".join(parts)]


def _op_call(operation: Operation) -> str:
    """``drill_hole(diameter=6, z=8)`` — die Op als lesbarer Aufruf.

    **Die Werte kommen aus der Projektdatei, und einer davon kann sehr lang
    sein.** Gefunden wurde es an ``create_from_scad``, das sein ganzes
    OpenSCAD-Programm im Parameter ``source`` trug — mehrzeilig, beliebig lang,
    und bis dahin lief es ungefiltert in den Verlaufssatz: Ein Schritt schrieb
    so viele Zeilen in den Steckbrief, wie sein Quelltext lang war, in
    derselben Form wie die echten.

    Die Operation ist seit dem 26.08.2026 fort, der Fall nicht. Ein
    **Sammelparameter** (``kind`` in ``sketch``, ``strokes``, ``armature``)
    trägt genauso einen beliebig langen Text — eine Skizze als JSON, eine
    Strichliste, ein Skelett. :func:`as_value` macht daraus eine Zeile mit
    :data:`NAME_LIMIT` Zeichen; wer den vollen Wert sehen will, liest ihn im
    Dokument.
    """
    shown: list[str] = []
    for key, value in operation.params.items():
        if len(shown) >= _STACK_PARAM_LIMIT:
            shown.append("…")
            break
        if isinstance(value, bool):
            shown.append(f"{key}={tr('ja') if value else tr('nein')}")
        elif isinstance(value, int | float):
            shown.append(f"{key}={round_display(float(value)):g}")
        elif isinstance(value, str) and value:
            shown.append(f"{as_value(key)}={as_value(value)}")
    return f"{as_value(operation.op)}({', '.join(shown)})"


def new_feature_lines(before: Scene, after: Scene) -> list[str]:
    """Was eine Operation an Merkmalen erzeugt hat — mit den IDs, auf die der
    nächste Schritt zeigen kann (Konzept Agent-Vertiefung 3.1).

    Ohne diese Zeilen arbeitete der Agent halbblind: nach ``drill_hole``
    kannte er die ID der neuen Bohrung nicht und musste raten, worauf ein
    Baustein oder eine Passung zeigen soll.
    """
    lines: list[str] = []
    for object_id, entry in after.objects.items():
        # Je Objekt verglichen, nicht über einen gemeinsamen Topf: die IDs
        # werden je Körper vergeben, und ein frisches hole_1 auf obj_2
        # verschwand sonst hinter dem gleichnamigen Bestand von obj_1.
        seen = before.objects[object_id].features if object_id in before.objects else {}
        fresh = {
            feature_id: feature
            for feature_id, feature in entry.features.items()
            if feature_id not in seen
        }
        if object_id not in before.objects:
            # Derselbe Rahmen wie in ``_object_lines``: Der Name kommt aus der
            # Projektdatei oder aus einem Werkzeugaufruf des Modells (§32).
            lines.append(f"{tr('Neues Objekt')}: {object_id} {as_name(entry.name)}")
        for feature_id, feature in fresh.items():
            lines.append(
                f"{tr('Neues Merkmal')}: {_feature_line(feature_id, feature)} "
                f"({tr('auf')} {object_id})"
            )
    return lines
