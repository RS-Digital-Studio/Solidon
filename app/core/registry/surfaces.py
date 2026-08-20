"""Alles, was aus dem Register erzeugt wird (Bauplan §10).

| Ausgabe                    | Abgeleitet aus                        |
|----------------------------|---------------------------------------|
| Menüeintrag und Dialog     | title, category, Parameterschema      |
| Kontextmenü                | applies_to                            |
| Palette und Kürzel         | title, doc, shortcut                  |
| Kommandozeile              | name, Parameterschema                 |
| Agenten-Werkzeugschema     | name, doc, JSON-Schema                |
| Dokumentationsabschnitt    | alles davon                           |

Nichts hier weiß von Qt: das sind Datenstrukturen, die eine Oberfläche
darstellt.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.registry.params import json_schema
from app.core.registry.registry import (
    CATEGORIES,
    FEATURE_TITLES,
    MENU_GROUPS,
    MENU_TWINS,
    REGISTRY,
    TWIN_TOGGLES,
    MenuSection,
    OperationSpec,
    Registry,
    group_title,
)
from app.core.types import ParamSpec
from app.i18n import TranslatableText, _, format_decimal, sort_key


def menu_tree(registry: Registry | None = None) -> tuple[MenuSection, ...]:
    """Das Menü, in der Reihenfolge des Katalogs (§25)."""
    source = registry or REGISTRY
    return tuple(
        MenuSection(category=category, title=CATEGORIES[category], entries=entries)
        for category, entries in source.by_category().items()
    )


def menu_path(spec: OperationSpec, registry: Registry | None = None) -> str:
    """Der vollständige Menüweg eines Eintrags — mit denselben Ebenen, die
    die Menüleiste einzieht (§2.6).

    Drei Staffelungen, alle aus Kern-Daten: die Gruppe aus ``MENU_GROUPS``,
    ein Kategorie-Untermenü, wenn die Gruppe mehr als eine besetzte Kategorie
    hat, und die Bausteingruppe aus dem Katalog. Die Werkzeugbeschreibungen
    des Agenten nannten nur Gruppe und Titel — der Chat schickte den Nutzer
    nach „Ändern → Bohrung setzen", während der Eintrag unter
    „Ändern → Bohrungen → Bohrung setzen" steht; das traf 72 von 77 Ops.
    Ein Test hält Leiste und Pfad aneinander fest.
    """
    source = registry or REGISTRY
    if spec.name in MENU_TWINS:
        # Ein zusammengelegter Zwilling hat keinen eigenen Eintrag
        # (MENU_TWINS): sein Ort ist der Eintrag des Partners — alles andere
        # schickte Nutzer und Agent an eine Stelle, die es nicht gibt.
        #
        # Wie er dort erreicht wird, hängt am Paar: mit einem Umschalter
        # (TWIN_TOGGLES), oder über einen Wert im Dialog. Der Zusatz nannte
        # früher immer den Umschalter „Exakt" — für ein Paar ohne ihn wäre
        # das eine Wegbeschreibung zu einem Haken, den es nicht gibt.
        twin = source.get(MENU_TWINS[spec.name])
        where = menu_path(twin, source)
        if spec.name in TWIN_TOGGLES:
            return f"{where} ({_('Umschalter „Exakt“')})"
        return f"{where} ({_('im selben Dialog')})"
    steps = [group_title(spec.category)]

    populated = {entry.category for entry in source.all()}
    in_group = next(
        (categories for _title, categories in MENU_GROUPS if spec.category in categories),
        (),
    )
    if sum(1 for category in in_group if category in populated) > 1:
        steps.append(str(CATEGORIES.get(spec.category, spec.category)))

    # Die Bausteingruppe ist dieselbe, nach welcher der Katalog seine Kacheln
    # ordnet — lazy importiert, weil die Bausteine ihrerseits das Register
    # laden.
    from app.core.knowledge.parts import GROUPS, PARTS
    from app.core.knowledge.parts.ops import op_name

    part_group = next(
        (part.group for part in PARTS.all() if op_name(part.name) == spec.name),
        None,
    )
    if part_group is not None and part_group in GROUPS:
        steps.append(str(GROUPS[part_group]))

    steps.append(str(spec.title))
    return " → ".join(steps)


def context_menu(feature_kind: str, registry: Registry | None = None) -> tuple[OperationSpec, ...]:
    """Was ein Klick auf ein Merkmal anbietet — der kürzeste Weg vom Sehen
    zum Tun (§2.6).
    """
    return (registry or REGISTRY).for_feature(feature_kind)


@dataclass(frozen=True, slots=True)
class PaletteEntry:
    """Eine Zeile der Befehlspalette. Das Kürzel steht daneben, so lernt man
    es nebenbei.
    """

    name: str
    title: TranslatableText | str
    category: str
    doc: TranslatableText | str
    shortcut: str | None = None
    available: bool = True
    """Ob der Eintrag jetzt ausführbar ist — die Palette zeigt ihn trotzdem:
    sie ist eine Reihenfolge, keine Auswahl."""
    reason: TranslatableText | str = ""
    """Warum nicht, wenn nicht — dieselbe Auskunft, die das Menü im
    Hinweistext trägt (Regel 18: der Grund ist die zweite Kodierung neben
    dem Ausgrauen)."""


def palette_entries(
    registry: Registry | None = None, *, for_feature: str | None = None
) -> tuple[PaletteEntry, ...]:
    """Alle Operationen als Palettenzeilen.

    Ist ein Merkmal ausgewählt, stehen die Operationen vorn, die dafür
    deklariert sind (``applies_to``, §10). Wer eine Bohrung angeklickt hat,
    sucht Senken und Verschließen — und nicht das, was zufällig vorn im
    Alphabet steht.

    Es ist eine **Reihenfolge, keine Auswahl**: alles bleibt erreichbar. Eine
    Palette, die aussortiert, wäre eine Betriebsart mit anderem Namen, und die
    stehen auf der Nicht-bauen-Liste.
    """
    specs = list((registry or REGISTRY).all())
    # **Nach dem Titel, nicht nach dem Namen.** ``Registry.all()`` sortiert nach
    # dem internen englischen Bezeichner, und die Palette gab das ungefiltert
    # weiter: „An Merkmal ausrichten", „Textur aufbringen", „Auf dem Bett
    # anordnen", „Slot zuweisen" — für einen deutschen Leser eine Zufallsfolge,
    # während die Menüleiste daneben nach Titel sortiert (``by_category``, mit
    # genau dieser Begründung im Docstring).
    #
    # Zuerst nach Titel, dann stabil nach ``applies_to``: Python sortiert
    # stabil, also steht die passende Gruppe vorn und innerhalb jeder Gruppe
    # alphabetisch.
    #
    # Über ``sort_key``, denselben Schlüssel wie ``by_category`` in der
    # Menüleiste — nicht bloß ``str``: 23 der 85 Titel tragen einen Umlaut, und
    # nach Codepunkt verglichen landet „Überhangfächer" hinter allem anderen,
    # weil „Ü" hinter „z" steht. Nicht zu verwechseln mit der Suchfaltung der
    # Palette (``command_palette.fold``, „ä" → „ae"): hier zählt „ä" wie „a"
    # nach DIN 5007-1, dort wie es auf einer Tastatur ohne Umlaute geschrieben
    # wird.
    specs.sort(key=lambda spec: sort_key(spec.title))
    if for_feature:
        specs.sort(key=lambda spec: for_feature not in spec.applies_to)
    return tuple(
        PaletteEntry(
            name=spec.name,
            title=spec.title,
            category=spec.category,
            doc=spec.doc,
            shortcut=spec.shortcut,
        )
        for spec in specs
    )


@dataclass(frozen=True, slots=True)
class CliArgument:
    """Eine Kommandozeilen-Option, abgeleitet aus einem Parameter."""

    flag: str
    name: str
    kind: str
    required: bool
    help: str
    choices: tuple[str, ...] = ()
    default: Any = None


@dataclass(frozen=True, slots=True)
class CliCommand:
    """Ein Kommandozeilen-Befehl, abgeleitet aus einer Operation."""

    name: str
    help: str
    arguments: tuple[CliArgument, ...]


def _help_text(spec: ParamSpec) -> str:
    text = str(spec.doc) if spec.doc is not None else str(spec.title)
    return f"{text} [{spec.unit}]" if spec.unit else text


def cli_commands(registry: Registry | None = None) -> tuple[CliCommand, ...]:
    """Befehle aus dem Register (ROADMAP P0: die Kommandozeile liest
    dieselbe Quelle).
    """
    commands: list[CliCommand] = []
    for spec in (registry or REGISTRY).all():
        arguments = tuple(
            CliArgument(
                flag=f"--{entry.name.replace('_', '-')}",
                name=entry.name,
                kind=entry.kind,
                required=entry.required,
                help=_help_text(entry),
                choices=entry.choices,
                default=entry.default,
            )
            for entry in spec.params.spec()
        )
        commands.append(CliCommand(name=spec.name, help=str(spec.doc), arguments=arguments))
    return tuple(commands)


def caveat_line(spec: OperationSpec, markup: bool = False) -> str:
    """Wann diese Operation die falsche Wahl ist — als fertige Zeile, oder leer.

    **Die Angabe gab es, und sie kam nur im Handbuch an.** Zwölf Operationen
    tragen einen ``caveat`` („Nicht ohne Entlüftung, wenn im Slicer Stützen
    entstehen"), und gelesen hat ihn allein :func:`documentation`. Der
    Menüeintrag setzte ``doc`` als Tooltip, der Dialog zeigte ``doc`` als
    Beschreibung, und der Agent bekam ``doc`` als Werkzeugbeschreibung — an
    keiner dieser drei Stellen stand die Grenze, also an keiner, an der jemand
    die Operation gerade wählt. Der Docstring des Feldes rechnet selbst mit der
    Oberfläche: „dann steht neben jedem Menüeintrag eine Warnung".

    Das Wort davor steht hier und nicht dreimal daneben — ``caveat`` ohne
    Vorwort liest sich wie eine Fortsetzung des ``doc``-Satzes, und genau davor
    warnt die Deklaration des Feldes.

    ``markup`` setzt die Sternchen für das Handbuch. Ein Tooltip und ein
    Systemprompt wollen keine, und ein Handbuch ohne wäre ein Absatz, den man
    überliest.
    """
    if not spec.caveat:
        return ""
    label = str(_("Wann nicht"))
    if markup:
        return f"**{label}:** {spec.caveat}"
    return f"{label}: {spec.caveat}"


def tool_schemas(registry: Registry | None = None) -> tuple[dict[str, Any], ...]:
    """Werkzeugbeschreibungen für den Agenten (§26.2). Dasselbe Schema wie
    Dialog und Kommandozeile.
    """
    return tuple(
        {
            "name": spec.name,
            # Die Grenze gehört dazu: Der Agent wählt aus derselben Auskunft,
            # aus der ein Mensch wählt (§10, Leitprinzip 3). Ohne sie schlug er
            # *Gitter füllen* für ein Teil vor, das dicht sein muss, und nichts
            # in seiner Werkzeugliste sagte, dass das die falsche Wahl ist.
            "description": _with_caveat(str(spec.doc) or str(spec.title), spec),
            "input_schema": json_schema(spec.params),
        }
        for spec in (registry or REGISTRY).all()
    )


def _with_caveat(text: str, spec: OperationSpec) -> str:
    """Beschreibung und Grenze in einem Absatz, getrennt durch eine Leerzeile."""
    line = caveat_line(spec)
    return f"{text}\n\n{line}" if line else text


#: Welche Abbildung eine Kategorieseite eröffnet.
#:
#: Nicht je Operation — dreiundsiebzig Vorher-Nachher-Bilder wären
#: dreiundsiebzig Aufbauten mit je eigenem Ausgangskörper, eigenen Werten und
#: eigener Auswahl, und jedes davon veraltet für sich. Eine je Kategorie zeigt,
#: worum es in dem Kapitel geht, und stammt aus demselben Katalog, den die
#: geschriebenen Seiten benutzen. Wo keine passt, steht keine: ein Bild, das
#: nur ungefähr dazugehört, kostet mehr Vertrauen, als es Verständnis bringt.
CATEGORY_FIGURES: dict[str, str] = {
    "holes": "drill",
    "prepare": "split",
    "surface": "texture",
    "parts": "part-nut-trap",
}


def documentation(registry: Registry | None = None, category: str = "") -> str:
    """Der Referenzteil der Dokumentation — erzeugt, nie von Hand geschrieben.

    Mit ``category`` nur ein Bereich. Das Handbuchfenster zeigt eine Kategorie
    je Seite und liest denselben Text, den die Kommandozeile ausgibt: eine
    zweite Quelle wäre eine, die veraltet.
    """
    lines: list[str] = []
    for name, entries in (registry or REGISTRY).by_category().items():
        if category and name != category:
            continue
        lines.append(f"## {CATEGORIES[name]}")
        lines.append("")
        opening = CATEGORY_FIGURES.get(name)
        if opening:
            lines.append(f"![](figure:{opening})")
            lines.append("")
        for spec in entries:
            lines.append(f"### {spec.title} (`{spec.name}`)")
            lines.append("")
            if spec.doc:
                lines.append(str(spec.doc))
                lines.append("")
            if spec.caveat:
                # Eigener Absatz mit eigenem Wort davor: In den doc-Satz
                # gehängt liest sich eine Grenze wie ein Nachtrag. Das Wort
                # kommt aus ``caveat_line`` — Dialog, Menü und Agent zeigen
                # dasselbe, und ein zweites Vorwort daneben wäre eines zu viel.
                lines.append(caveat_line(spec, markup=True))
                lines.append("")
            facts = [
                f"{_('Objekte')}: {spec.consumes} → {spec.produces}",
                str(_("umkehrbar") if spec.reversible else _("nicht umkehrbar")),
                str(_("deterministisch") if spec.deterministic else _("mit Startwert")),
            ]
            if spec.shortcut:
                facts.append(f"{_('Kürzel')} `{spec.shortcut}`")
            if spec.applies_to:
                # Die Merkmalsarten mit ihren Namen, nicht mit ihren
                # Schlüsseln: „Features: face, hole" ist eine Zeile aus dem
                # Register, keine aus einem Handbuch.
                named = ", ".join(str(FEATURE_TITLES.get(kind, kind)) for kind in spec.applies_to)
                facts.append(f"{_('Gilt für')}: {named}")
            lines.append(" · ".join(facts))
            lines.append("")
            parameters = spec.params.spec()
            if parameters:
                lines.extend(parameter_table(parameters))
    return "\n".join(lines).rstrip() + "\n"


def _span_of(entry: ParamSpec) -> str:
    """Der zulässige Bereich als Text, oder nichts."""
    if entry.choices:
        return ", ".join(entry.choices)
    if entry.minimum is None and entry.maximum is None:
        return ""
    low = "" if entry.minimum is None else format_decimal(entry.minimum)
    high = "" if entry.maximum is None else format_decimal(entry.maximum)
    return f"{low} … {high}"


def _default_of(entry: ParamSpec) -> str:
    """Die Vorgabe, wie ein Mensch sie liest.

    ``True`` und ``False`` standen so in der Tabelle — Pythons Schreibweise in
    einem deutschen Handbuch, und für jeden, der nicht programmiert, zwei
    Wörter ohne Bedeutung. Ein Schalter ist an oder aus.

    Für Zahlen galt dasselbe und blieb übersehen: ``f"{0.2}"`` schreibt einen
    Punkt, und der stand 252-mal im deutschen Handbuch neben einer Anwendung,
    die ``2,40 mm`` anzeigt. :func:`format_decimal` entscheidet das jetzt nach
    der aktiven Sprache — und kürzt dabei ``5.0`` auf ``5``, weil eine
    Nachkommastelle ohne Aussage nur Platz kostet.
    """
    if entry.required:
        return str(_("erforderlich"))
    if isinstance(entry.default, bool):
        return str(_("an") if entry.default else _("aus"))
    if entry.default is None:
        return ""
    if isinstance(entry.default, (int, float)):
        return format_decimal(entry.default)
    return f"{entry.default}"


def parameter_table(parameters: tuple[ParamSpec, ...]) -> list[str]:
    """Die Parametertabelle einer Operation, als Markdown-Zeilen.

    **Der Titel steht vorn, der Schlüssel dahinter.** Vorher war es umgekehrt:
    die Spalte „Parameter" trug ``fill_holes``, ``small_components``,
    ``self_intersections`` — die internen englischen Namen, in Monospace, in
    einem deutschen Handbuch —, und was sie bedeuten, stand ganz rechts. Der
    Schlüssel bleibt stehen: Kommandozeile und Agent brauchen ihn, nur ist er
    nicht das Erste, was man liest.

    **Leere Spalten fallen weg.** Bei der Reparatur waren „Einheit" und
    „Bereich" über die ganze Tabelle leer; eine Spalte, die nichts trägt, ist
    kein Platzhalter für später, sondern eine Frage, die der Leser sich selbst
    stellt.
    """
    columns: tuple[tuple[str, Callable[[ParamSpec], str]], ...] = (
        (str(_("Parameter")), lambda entry: f"{entry.title} `{entry.name}`"),
        (str(_("Einheit")), lambda entry: entry.unit or ""),
        (str(_("Vorgabe")), _default_of),
        (str(_("Bereich")), _span_of),
        (str(_("Bedeutung")), lambda entry: str(entry.doc or "")),
    )
    shown = [
        (title, value)
        for index, (title, value) in enumerate(columns)
        if index == 0 or any(value(entry) for entry in parameters)
    ]

    lines = ["| " + " | ".join(title for title, _value in shown) + " |"]
    lines.append("|" + "---|" * len(shown))
    for entry in parameters:
        lines.append("| " + " | ".join(value(entry) for _title, value in shown) + " |")
    lines.append("")
    return lines
