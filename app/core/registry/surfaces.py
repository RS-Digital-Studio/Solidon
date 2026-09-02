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

from collections.abc import Callable, Collection, Container
from dataclasses import dataclass
from typing import Any, Final

from app.core.registry.params import condition_text, json_schema
from app.core.registry.registry import (
    CATEGORIES,
    FEATURE_TITLES,
    MENU_GROUPS,
    MENU_TWINS,
    REGISTRY,
    TWIN_TOGGLES,
    VARIANT_GROUPS,
    MenuSection,
    OperationSpec,
    Registry,
    group_title,
    variant_members,
)
from app.core.types import ParamSpec
from app.i18n import TranslatableText, _, format_decimal, sort_key


def menu_tree(
    registry: Registry | None = None, skip: Container[str] = frozenset()
) -> tuple[MenuSection, ...]:
    """Das Menü, in der Reihenfolge des Katalogs (§25).

    ``skip`` lässt Operationen aus der Menüleiste heraus, ohne sie aus dem
    Register zu nehmen — sie bleiben über Katalog, Befehlspalette und
    Kontextmenü erreichbar.

    **Die Entscheidung, *wen* das trifft, gehört nicht hierher.** Der Kern
    bekommt Namen und nicht den Grund: Die Oberfläche reicht die eigenen
    Bausteine des Nutzers herein (§24.5), weil jeder davon eine Operation wird
    und zwanzig eigene Teile aus einem Menü eine Liste zum Absuchen machen.
    Welche Regel dahintersteht, weiß der Aufrufer.
    """
    source = registry or REGISTRY
    sections = []
    for category, entries in source.by_category().items():
        kept = tuple(entry for entry in entries if entry.name not in skip)
        if kept:
            sections.append(
                MenuSection(category=category, title=CATEGORIES[category], entries=kept)
            )
    return tuple(sections)


#: Wie viele Zeilen ein Menü zeigen darf, bevor es eine Liste zum Absuchen
#: wird. Dieselbe Zahl hält ``tests/test_interface_limits.py`` ein zweites Mal
#: — **absichtlich als eigene Kopie und nicht als Import**: Ein Wächter, der
#: seine Grenze von dem holt, den er bewacht, ist an dem Tag blind, an dem
#: jemand die Grenze erhöht.
MAX_MENU_ROWS: Final = 12


def group_is_flat(category: str, registry: Registry | None = None) -> bool:
    """Ob die Menügruppe dieser Kategorie ohne Zwischenebene auskommt (§2.6).

    **Zwei Maße maßen dieselbe Sache, und sie waren sich uneinig.** Der Aufbau
    zog eine Zwischenebene ein, sobald eine Gruppe *mehr als eine Kategorie*
    hatte; die Hausgrenze zählt aber *Zeilen* (zwölf je Menü). Damit bekam
    „Vorbereiten" ein Untermenü, weil es zwei Kategorien hat — nicht, weil es
    zu lang wäre. Gerechnet wird deshalb hier, statt an zwei Stellen gewusst.

    Gezählt werden die sichtbaren Einträge aller besetzten Kategorien der
    Gruppe. Zusammengelegte Zwillinge (``MENU_TWINS``) haben keinen eigenen
    Eintrag und zählen nicht mit. Trennstriche zählen ebenfalls nicht: Sie
    sind der Ersatz für die Namen der Untermenüs, die wegfallen, und wer sie
    mitzählte, bestrafte das Flachziehen für seine eigene Wirkung.

    **Und Variantengruppen zählen als eine Zeile, nicht als ihre Mitglieder.**
    Das war der Fehler, und er kostete genau ein Menü: *Erzeugen* zeigt **11**
    Einträge, gezählt wurden **14**, und die Grenze liegt bei zwölf — die
    Zwischenebene entstand also für drei Operationen, die das Menü gar nicht
    zeigt (``sketch_revolve``, ``sketch_sweep``, ``sketch_loft`` stehen unter
    dem Sammeleintrag). Damit kostete jede Erzeugungs-Operation einen dritten
    Klick, und zwar in dem Menü, das Weg 2 trägt.

    Gemessen am 27.08.2026 beim Vergleich mit Fusion, wo dieselbe Handlung
    einen Klick kostet. Die Regel selbst stand schon da — „gefaltet wird, weil
    es sein muss, nicht weil es ordentlich aussieht" (``folded_groups``); was
    fehlte, war eine Zählung, die zählt, was zu sehen ist. Derselbe Fehler wie
    ein Sollwert, der aus dem Prüfling kommt: Die Zahl war plausibel und
    beschrieb etwas anderes als die Frage.

    **Eine Gruppe mit einer einzigen besetzten Kategorie ist immer flach**,
    gleich wie lang sie ist — ihre Zwischenebene hieße genauso wie das Menü
    darüber („Bausteine → Bausteine → Deckel erzeugen"). Das ist keine
    Ausnahme von der Zeilenregel, sondern eine zweite Frage, die dieselbe
    Antwort braucht: Eine Kategorie-Ebene ist dort nie das, was die Länge
    lösen würde. Die Bausteine lösen ihre zwanzig Zeilen über die
    Bausteingruppen, und die zählt diese Funktion zu Recht nicht.

    Die Bedingung steht hier und nicht in den Aufrufern, weil sonst jeder
    weitere sie neu lernen müsste — genau der Grund, aus dem die Funktion in
    den Kern gehört.

    **Seit dem 27.08.2026 ist das nur noch die halbe Frage**, und die Antwort
    kommt von :func:`folded_categories`: „ganz flach" heißt „keine einzige
    Kategorie muss falten". Vorher war es die *ganze* Frage — entweder passte
    eine Gruppe vollständig, oder **jede** ihrer Kategorien bekam eine
    Zwischenebene. Im Menü *Ändern* lagen damit alle sieben eine Ebene tiefer,
    auch *Reparatur* mit einem Eintrag.

    Die Funktion bleibt, weil ihre Frage weiter vorkommt (ein Menü ohne jedes
    Untermenü zeigt alle seine Kategorienamen). Sie **rechnet** aber nicht mehr
    selbst: Zwei Rechnungen über dieselbe Sache waren genau der Grund, aus dem
    die Leiste und das Kontextmenü auseinandergelaufen sind.
    """
    return not folded_categories(category, registry)


def menu_rows_of(categories: Collection[str], registry: Registry | None = None) -> int:
    """Wie viele Zeilen diese Kategorien flach in einem Menü belegen.

    Die eine Zählung für die Frage „passt das ohne Zwischenebene", und sie
    zählt, **was zu sehen ist**: Zwillinge aus ``MENU_TWINS`` haben keinen
    Eintrag, und die Mitglieder einer Variantengruppe teilen einen — vier
    Skizzen-Operationen sind eine Zeile.

    Als eigene Funktion, damit sie prüfbar ist, ohne ein Fenster zu bauen: Ein
    Test über ``group_is_flat`` sieht nur ja oder nein und könnte die Zahl
    dahinter nicht gegen die des gebauten Menüs halten.
    """
    source = registry or REGISTRY
    inside = [spec for spec in source.all() if spec.category in categories]
    names = {spec.name for spec in inside if spec.name not in MENU_TWINS}
    members = variant_members()
    rows = len(names - members)
    # Je Variantengruppe, die hier überhaupt vertreten ist, genau eine Zeile
    # für den Sammeleintrag.
    rows += sum(1 for group in VARIANT_GROUPS if any(name in names for name in group.members))
    return rows


def menu_rank(title: str) -> int:
    """Wo diese Gruppe in der Reihenfolge der Menüleiste steht.

    Kennt ``MENU_GROUPS`` den Titel nicht, steht er hinten — dieselbe Antwort,
    die ``group_title`` einer unbekannten Kategorie gibt, und aus demselben
    Grund: Eine neue Kategorie soll auftauchen und nicht verschwinden.
    """
    for position, (menu_title, _categories) in enumerate(MENU_GROUPS):
        if str(menu_title) == title:
            return position
    return len(MENU_GROUPS)


def folded_groups(
    sizes: dict[str, int],
    limit: int = MAX_MENU_ROWS,
    fixed: int = 0,
    keep: Collection[str] = (),
    rank: Callable[[str], int] | None = None,
) -> list[str]:
    """Welche Gruppen ein Untermenü bekommen, damit das Menü in die Grenze passt.

    Reine Rechnung über Namen und Anzahlen — **kein Qt**, und deshalb ohne ein
    einziges Fenster prüfbar. Das ist hier keine Stilfrage: Am 24.08.2026 wurde
    gemessen, dass jeder Test, der über die ``window``-Fixture ein
    ``MainWindow`` baut, die Abrissquote der **ganzen Testdatei** hebt (2 von 9
    auf 2 von 3). Eine Frage, die eine Funktion beantworten kann, bekommt kein
    Fenster.

    Gefaltet wird nur so weit, bis der Rest in die Grenze passt. Eine Gruppe
    mit einem einzigen Eintrag wird **nie** gefaltet: Ihr Untermenü spart keine
    Zeile und kostet einen Klick. Bleibt das Menü danach zu lang, bleibt es zu
    lang — ein Aufklappen, das nichts bündelt, macht es nicht kürzer, sondern
    nur tiefer.

    **Welche Gruppe es trifft, entscheidet die Reihenfolge der Menüleiste.**
    Genügt eine Gruppe allein, um unter die Grenze zu kommen, fällt die
    **hinterste** aus ``MENU_GROUPS`` — die Leiste ordnet von häufig nach
    vorbereitend, und wer falten muss, faltet hinten. Genügt keine allein,
    fällt die größte, sonst käme die Rechnung nicht voran.

    Vorher entschied allein die Größe, und das war am Flächenklick die falsche
    Frage: Nach „Bausteine" fehlt genau **eine** Zeile, und die größte der
    übrigen ist „Ändern" — mit der Bohrung darin, also genau dem Eintrag,
    dessen zweiter Klick den Umbau vom 24.08.2026 ausgelöst hat. Eine Gruppe,
    die ``MENU_GROUPS`` nicht kennt, steht hinten — dieselbe Antwort, die
    ``group_title`` einer unbekannten Kategorie gibt.

    **Die Zahlen dazu, gemessen am 27.08.2026** (und sie wandern: hier stand
    „19 Operationen, davon 10 Bausteine", was einmal stimmte und mit jedem
    neuen Baustein weiter danebenlag — wer sie als Grundlage nimmt, rechnet
    dann mit zwölf Bausteinen zu wenig):

    ===================  ====
    Bausteine              22
    Ändern                  5
    Erzeugen                2
    Vorbereiten             2
    ===================  ====

    Einunddreißig Operationen, drei feste Zeilen darüber. „Bausteine" spart
    einundzwanzig und genügt trotzdem nicht — danach fehlt eine Zeile, und die
    zweite Faltung entscheidet, welcher Eintrag einen Klick tiefer liegt. Wer
    diese Rechnung anfasst, misst sie neu, statt die Tabelle zu glauben.

    ``fixed`` sind Zeilen, die mitzählen, aber nie gefaltet werden können —
    im Bausteine-Untermenü die Einträge, die zu keinem Baustein der Bibliothek
    gehören und deshalb keine Gruppe haben.

    ``keep`` sind Gruppen, die **zuletzt** gefaltet werden, weil sie eine
    Geste tragen, für die man überhaupt auf das Merkmal zeigt. Der Rang aus
    ``MENU_GROUPS`` ordnet von häufig nach vorbereitend und war deshalb bis
    zum 27.08.2026 die ganze Antwort — bis das Färben in „Vorbereiten"
    landete, also ganz hinten. Am Flächenklick fehlt nach den Bausteinen
    genau **eine** Zeile, und die Rechnung nahm sie sich dort: Gemessen am
    gebauten Fenster stand „Fläche färben" danach im Untermenü, unter einem
    Wort, unter dem niemand Farbe sucht. Entscheidung Robert: Die häufige
    Geste bleibt oben, das Seltenere wandert. Wer die Gruppen bestimmt, ist
    :func:`groups_to_keep` — über die **Kategorie** und nicht über den
    Titel, denn der ist übersetzt.

    **Und die einzige Gruppe wird nie gefaltet**, gleich wie lang sie ist.
    Bliebe sonst ein Menü, das aus einem einzigen Untermenü besteht: ein Klick
    für alles, und die Zwischenebene hieße, wonach man ohnehin schon geklickt
    hat. Das ist dieselbe Ausnahme, die ``registry.surfaces.group_is_flat`` für
    die Menüleiste macht — dort wörtlich als „Bausteine → Bausteine → Deckel
    erzeugen" beschrieben. Sie stand hier zuerst nicht, obwohl der Text auf die
    Regel verwies: Eine zitierte Regel ist keine befolgte.

    ``rank`` ordnet, wen es zuerst trifft. Ohne Angabe ist es die Reihenfolge
    der Menüleiste (:func:`menu_rank`) — die Antwort für das **Kontextmenü**,
    wo die Schlüssel Gruppentitel sind. Die **Leiste selbst** fragt dieselbe
    Rechnung mit den Kategorien *einer* Gruppe als Schlüsseln, und dort ordnet
    ihre Stellung in ``MENU_GROUPS``; siehe :func:`folded_categories`.

    **Zwei Ordnungen, eine Rechnung.** Eine zweite Umsetzung wäre die zweite
    Wahrheit, und an genau dieser Stelle ist die Leiste schon einmal
    auseinandergelaufen: Sie hatte ein gröberes Modell (alles flach oder jede
    Kategorie gefaltet), weil diese Funktion in der Oberfläche lag und der Kern
    sie nicht fragen konnte. Deshalb steht sie seit dem 27.08.2026 hier.
    """
    ordnung = rank or menu_rank
    if len(sizes) < 2 and not fixed:
        return []
    rows = sum(sizes.values()) + fixed
    # Nur Gruppen ab zwei Einträgen: eine von eins spart keine Zeile.
    foldable = {title: count for title, count in sizes.items() if count > 1}
    folded: list[str] = []
    while rows > limit and foldable:
        missing = rows - limit
        enough = [title for title, count in foldable.items() if count - 1 >= missing]
        if enough:
            # Erst die Ungeschützten, dann die hinterste, die allein genügt;
            # bei gleichem Platz die größere, und ganz zuletzt der Name, damit
            # die Antwort eindeutig bleibt.
            title = min(
                enough,
                key=lambda name: (name in keep, -ordnung(name), -foldable[name], name),
            )
        else:
            # **Bei gleicher Größe entscheidet die Reihenfolge, nicht das
            # Alphabet.** Der Zweig darüber fragte den Rang, dieser nicht — und
            # damit stand die Zusage „wer falten muss, faltet hinten" nur für
            # die halbe Rechnung. Gemessen am Menü *Ändern* (27.08.2026): Bei
            # gleich großen Gruppen fiel „Verbinden und Abziehen" statt
            # „Formgebung", weil „boolean" alphabetisch vor „shaping" steht —
            # die häufigere Gruppe wanderte eine Ebene tiefer als die seltenere.
            title = min(
                foldable,
                key=lambda name: (name in keep, -foldable[name], -ordnung(name), name),
            )
        folded.append(title)
        rows -= foldable.pop(title) - 1
    return folded


def folded_categories(category: str, registry: Registry | None = None) -> frozenset[str]:
    """Welche Kategorien **dieser Gruppe** ein Untermenü bekommen (§2.6).

    Die Antwort für die Menüleiste, und sie ersetzt die gröbere von
    :func:`group_is_flat`: Dort war es alles oder nichts — entweder war die
    ganze Gruppe flach, oder **jede** Kategorie bekam eine Zwischenebene. Das
    Kontextmenü kann das seit dem 24.08.2026 besser (:func:`folded_groups`
    faltet nur so weit, bis der Rest passt); die Leiste konnte es nicht, weil
    die Rechnung in der Oberfläche lag und der Kern sie von dort nicht fragen
    darf (§8).

    Gemessen am 27.08.2026, Menü *Ändern* bei einer Grenze von zwölf: Die
    Kategorien tragen 9, 9, 4, 4, 3, 3 und 1 Zeilen, zusammen 33. Gefaltet
    werden müssen **vier**, dann sind es elf — *Bohrungen*, *Oberfläche* und
    *Reparatur* bleiben direkte Zeilen. Vorher lagen alle sieben eine Ebene
    tiefer, und damit auch die Bohrung: genau der Eintrag, dessen zweiter Klick
    den Umbau des Kontextmenüs ausgelöst hat.

    **Die Ordnung ist die der Kategorien in ihrer Gruppe.** ``MENU_GROUPS``
    zählt sie von häufig nach selten auf, und wer falten muss, faltet hinten —
    dieselbe Regel, die :func:`folded_groups` für die Gruppen der Leiste
    anwendet, eine Ebene tiefer.

    Eine Gruppe mit einer einzigen besetzten Kategorie faltet nie, aus dem
    Grund, der bei :func:`group_is_flat` steht.
    """
    source = registry or REGISTRY
    in_group = next(
        (categories for _title, categories in MENU_GROUPS if category in categories),
        (),
    )
    # Gezählt wird, was im Menü **eine Zeile hat** — nicht, was irgendeine
    # Operation trägt. Eine Kategorie, deren Operationen alle Zwillinge aus
    # ``MENU_TWINS`` sind, ist besetzt und im Menü unsichtbar; sie zählte
    # trotzdem als eine der Kategorien, unter denen gefaltet wird, und stand
    # mit null Zeilen in ``sizes``. Heute trifft das keine (gemessen am
    # 02.09.2026), und genau deshalb steht es hier: Die nächste Zwillingsgruppe
    # bräuchte sonst niemanden, der daran denkt.
    present = [name for name in in_group if menu_rows_of([name], source)]
    if len(present) <= 1:
        return frozenset()
    sizes = {name: menu_rows_of([name], source) for name in present}
    order = {name: position for position, name in enumerate(present)}
    return frozenset(
        folded_groups(
            sizes,
            keep={"holes"},
            rank=lambda name: order.get(name, len(order)),
        )
    )


def menu_path(spec: OperationSpec, registry: Registry | None = None) -> str:
    """Der vollständige Menüweg eines Eintrags — mit denselben Ebenen, die
    die Menüleiste einzieht (§2.6).

    Drei Staffelungen, alle aus Kern-Daten: die Gruppe aus ``MENU_GROUPS``,
    ein Kategorie-Untermenü für die Kategorien, die falten müssen
    (:func:`folded_categories`), und die Bausteingruppe aus dem Katalog.
    Die Werkzeugbeschreibungen des Agenten nannten nur Gruppe und Titel — der
    Chat schickte den Nutzer nach „Ändern → Fase anbringen", während der
    Eintrag unter „Ändern → Formgebung → Fase anbringen" steht; das traf 72
    von 77 Ops. Ein Test hält Leiste und Pfad aneinander fest.

    **Das Beispiel hier stand einmal auf der Bohrung**, und es ist mit dem
    27.08.2026 unbrauchbar geworden: *Bohrungen* faltet seither nicht mehr,
    also ist „Ändern → Bohrung setzen" der **richtige** Weg — der Docstring
    führte den heutigen Sollzustand als Fehlerbild vor. Ein Beispiel altert mit
    dem, was es zeigt; wer die Menütiefe ändert, sucht die Wege, die in
    Docstrings, Katalogen und Tests als Zeichenketten stehen (gefunden wurden
    fünf, vier davon in ``tests/test_agent_suite.py``).
    """
    source = registry or REGISTRY
    if spec.name in MENU_TWINS:
        # Ein zusammengelegter Zwilling hat keinen eigenen Eintrag
        # (MENU_TWINS): sein Ort ist der Eintrag des Partners — alles andere
        # schickte Nutzer und Agent an eine Stelle, die es nicht gibt.
        #
        # Wie er dort erreicht wird, hängt am Paar: mit einer Option
        # (TWIN_TOGGLES), oder über einen Wert im Dialog. Der Zusatz nannte
        # früher immer den Umschalter „Exakt" — für ein Paar ohne ihn wäre
        # das eine Wegbeschreibung zu einem Haken, den es nicht gibt.
        twin = source.get(MENU_TWINS[spec.name])
        where = menu_path(twin, source)
        if spec.name in TWIN_TOGGLES:
            return f"{where} ({_('Option „Flächen und Kanten später bearbeiten“')})"
        return f"{where} ({_('im selben Dialog')})"
    if spec.name in catalogue_operations():
        # **Ein Baustein nennt den Ort, den er wirklich hat.**
        # Die Bausteine der Bibliothek stehen seit dem 29.08.2026 nur noch im
        # Katalog; ein Weg „Bausteine → Mechanik → Filmscharnier" schickte
        # Kunde, Agent und Handbuch zu einem Menü, das es nicht mehr gibt.
        # Gefragt wird nach der Kachel und nicht nach der Kategorie — warum,
        # steht in :func:`catalogue_operations`.
        #
        # **Und der Ersatz darf nicht dieselbe Kette weiterschreiben.** Hier
        # stand zuerst „Datei → Bausteinkatalog → Mechanik → Bolzenscharnier",
        # also vier Glieder in einer Pfeilkette — von denen die letzten beiden
        # keine Menüeinträge sind, sondern Gruppe und Kachel *im Katalogfenster*.
        # Siebenundzwanzig Werkzeugbeschreibungen nannten das unter dem Vorwort
        # „Menü:", und wer danach im Datei-Menü ein Untermenü *Mechanik* sucht,
        # findet keines. Ein Pfeil zwischen zwei Menüs bedeutet „dann dort
        # weiter"; zwischen Menü und Dialog bedeutet er nichts.
        #
        # Der Bruch wird deshalb ausgeschrieben: bis zum Katalog ein Menüweg,
        # danach ein Satz. Er ist auch die Antwort auf die Zusage von
        # ``tests/test_agent_suite.py``, dass kein Menüweg tiefer als drei
        # Ebenen wird — die Leiste faltet höchstens eine Ebene, tiefer *kann*
        # keiner sein.
        return _catalogue_path(spec)
    steps = [group_title(spec.category)]

    # **Je Kategorie gefragt, nicht je Gruppe.** ``group_is_flat`` beantwortet
    # dieselbe Frage gröber — alles flach oder jede Kategorie eine Ebene
    # tiefer —, und die Leiste faltet seit dem 27.08.2026 nur so weit, wie sie
    # muss. Ein Pfad, der die alte Frage stellt, schickt den Nutzer und den
    # Agenten zu einer Zwischenebene, die es nicht mehr gibt.
    if spec.category in folded_categories(spec.category, source):
        steps.append(str(CATEGORIES.get(spec.category, spec.category)))

    steps.append(str(spec.title))
    return " → ".join(steps)


def catalogue_operations() -> frozenset[str]:
    """Die Operationen, die im Bausteinkatalog eine Kachel haben.

    **Die Trennlinie für den Menüort, und sie liegt an der Bibliothek — nicht
    an der Kategorie.** Hier stand zuerst eine Menge von Kategorien
    (``WITHOUT_MENU = {"parts"}``), und das war eine Näherung: Von den
    neunundzwanzig Operationen der Kategorie ``parts`` haben
    siebenundzwanzig eine Kachel, zwei nicht — ``create_lid`` und
    ``screw_lid`` sind Operationen, die einen Deckel *bauen*, und der Katalog
    zeigt ``PARTS.all()``.

    Die Näherung hat beide aus der Menüleiste genommen, ohne sie irgendwo
    hinzustellen: gemessen am gebauten Fenster **114 Menüeinträge, kein
    „Deckel erzeugen" darunter**, im Katalog nicht vorhanden, und
    :func:`menu_path` schickte jeden Fragenden dorthin. Auch das Kontextmenü
    einer Fläche verlor sie — also genau der Ort, den §18.5 für sie vorsieht,
    und den die Tour *dose-mit-deckel* dem Kunden nennt.

    Gefragt wird deshalb nach der Sache: Wer eine Kachel hat, steht im
    Katalog; wer keine hat, steht im Menü. Lazy importiert, weil die
    Bausteine ihrerseits das Register laden.
    """
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts.ops import op_name

    return frozenset(op_name(part.name) for part in PARTS.all())


def _catalogue_path(spec: OperationSpec) -> str:
    """Wo ein Baustein liegt — Menüweg bis zum Katalog, danach ein Satz.

    Getrennt von :func:`menu_path`, weil es zwei verschiedene Auskünfte sind:
    Ein Menüweg ist eine Kette gleichartiger Schritte, hier wechselt nach dem
    zweiten das Fenster. Die Bausteingruppe ist dieselbe, nach der der Katalog
    seine Kacheln ordnet — lazy importiert, weil die Bausteine ihrerseits das
    Register laden.

    Kennt der Katalog die Gruppe nicht, bleibt der kurze Satz: Eine erfundene
    Gruppe wäre schlechter als keine (Regel 21).
    """
    from app.core.knowledge.parts import GROUPS, PARTS
    from app.core.knowledge.parts.ops import op_name

    where = f"{_('Datei')} → {_('Bausteinkatalog …')}"
    part_group = next(
        (part.group for part in PARTS.all() if op_name(part.name) == spec.name),
        None,
    )
    if part_group is not None and part_group in GROUPS:
        return str(_("{path}, dort unter {group}: {title}")).format(
            path=where, group=GROUPS[part_group], title=spec.title
        )
    return str(_("{path}, dort: {title}")).format(path=where, title=spec.title)


def context_menu(feature_kind: str, registry: Registry | None = None) -> tuple[OperationSpec, ...]:
    """Was ein Klick auf ein Merkmal anbietet — der kürzeste Weg vom Sehen
    zum Tun (§2.6).

    **Die Rohmenge, nicht die Zeilen des Menüs.** Der Name legt das andere
    nahe, und `tests/test_acceptance_p0.py` nagelt ausdrücklich diese Lesart
    fest: alles, dessen ``applies_to`` die Art nennt. Was die Oberfläche daraus
    macht, entscheidet sie — sie legt zusammengelegte Zwillinge zusammen
    (``MENU_TWINS``), faltet nach Zeilen und vertritt die Bausteine mit Kachel
    durch den Katalog.

    Der Satz steht hier, weil die Verwechslung Geld gekostet hat: An jeder
    Fläche stand *Bohrung setzen* zweimal, weil ``operations_for_feature`` in
    `app/ui/panels.py` diese Menge ungefiltert weitergab und die
    Zusammenlegung nicht kannte, die die Menüleiste seit je macht.
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


#: Die Ortsangaben, die jede Baustein-Operation zusätzlich trägt — die Namen
#: aus ``knowledge/parts/ops.py`` (``_PLACEMENT``), hier als Konstante, weil
#: das Register die Bausteinbibliothek nicht importieren darf. Ein Test hält
#: beide Listen deckungsgleich. Das Handbuch erklärt sie einmal am Kopf der
#: Kategorie, statt sechs identische Zeilen in jede Bausteintabelle zu setzen.
PART_PLACEMENT_PARAMS: Final = ("x", "y", "z", "axis", "angle", "at_feature")


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
        if name == "parts" and entries:
            shared = tuple(
                entry for entry in entries[0].params.spec() if entry.name in PART_PLACEMENT_PARAMS
            )
            if shared:
                lines.append(
                    str(
                        _(
                            "Alle Bausteine teilen dieselben Ortsangaben. Sie stehen "
                            "hier einmal und fehlen deshalb in den Tabellen darunter:"
                        )
                    )
                )
                lines.append("")
                lines.extend(parameter_table(shared))
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
            if name == "parts":
                # Die geteilten Ortsangaben stehen einmal am Kategoriekopf.
                parameters = tuple(
                    entry for entry in parameters if entry.name not in PART_PLACEMENT_PARAMS
                )
            if parameters:
                lines.extend(parameter_table(parameters))
    return "\n".join(lines).rstrip() + "\n"


def _meaning_of(entry: ParamSpec, schema: tuple[ParamSpec, ...]) -> str:
    """Was ein Parameter tut — und wann er es tut.

    Die Bedingung als **eigener Satz** hinter der Bedeutung und nicht in sie
    hineingeschoben: „Von Mitte zu Mitte, bei der linearen Art" sagt es
    beiläufig, „Gilt bei Art = linear." sagt es nachprüfbar. Eine siebte Spalte
    wäre die Alternative gewesen, und eine Tabelle mit sieben Spalten liest
    niemand.
    """
    condition = condition_text(entry, schema)
    meaning = str(entry.doc or "")
    if not condition:
        return meaning
    return f"{meaning} {condition}".strip()


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
        (str(_("Bedeutung")), lambda entry: _meaning_of(entry, parameters)),
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
