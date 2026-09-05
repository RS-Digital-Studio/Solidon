"""Registerkonsistenz über die Operationen, die die Anwendung wirklich
ausliefert (§35).

Jede Operation erscheint in jeder Oberfläche, trägt ein Schema, übersetzte Texte
und einen Test; Kürzel sind eindeutig; nicht-deterministische Operationen
benutzen einen Startwert.

Solange der Katalog noch gefüllt wird, laufen diese Prüfungen über wenige
Operationen — sie beißen in dem Moment, in dem eine unvollständig hinzukommt.
"""

from __future__ import annotations

import ast
import inspect
import re
import textwrap
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final

import pytest

from app.core.bootstrap import load_operations
from app.core.registry import (
    CATEGORIES,
    FEATURE_KINDS,
    REGISTRY,
    OperationSpec,
    cli_commands,
    documentation,
    menu_tree,
    palette_entries,
    tool_schemas,
)

TESTS_DIR = Path(__file__).parent


def registered() -> list[OperationSpec]:
    return list(REGISTRY.all())


def ids(spec: OperationSpec) -> str:
    return spec.name


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_operation_is_completely_declared(spec: OperationSpec) -> None:
    assert str(spec.title).strip(), f"{spec.name} has no title"
    assert str(spec.doc).strip(), f"{spec.name} has no documentation text"
    assert spec.category in CATEGORIES
    assert all(kind in FEATURE_KINDS for kind in spec.applies_to)
    assert spec.params.spec() is not None


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_every_parameter_says_what_it_does(spec: OperationSpec) -> None:
    """Ein Titel ist eine Beschriftung, keine Erklärung (§2.4).

    „Spiel [mm]" über einem Zahlenfeld sagt nicht, wovon dieses Spiel abgezogen
    wird und was passiert, wenn es null ist. Der Satz dahinter wird zum Tooltip
    im Dialog und zur Spalte *Bedeutung* im Handbuch — beide leer zu lassen ist
    die stille Art, eine Operation unbenutzbar zu machen.
    """
    for entry in spec.params.spec():
        text = str(entry.doc or "")
        assert text.strip(), f"{spec.name}.{entry.name} has no help text"
        assert text.strip() != str(entry.title).strip(), (
            f"{spec.name}.{entry.name} only repeats its title"
        )


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_no_user_text_carries_a_paragraph_number(spec: OperationSpec) -> None:
    """Der Nutzer hat den Bauplan nicht.

    „(§39)", „(§30)", „(§32)" standen in Dialogtexten und Befunden — für den
    Leser Ballast, für den Suchenden ein Verweis auf ein Dokument, das er nicht
    hat. Im Quelltext sind die Verweise richtig und bleiben; was durch ``_()``
    geht, ist Oberfläche.
    """
    texts = [str(spec.title), str(spec.doc)]
    texts.extend(str(entry.doc or "") for entry in spec.params.spec())
    texts.extend(str(entry.title) for entry in spec.params.spec())
    for text in texts:
        assert "§" not in text, f"{spec.name}: §-Verweis im Nutzertext — {text[:60]}"


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_no_user_text_addresses_the_agent(spec: OperationSpec) -> None:
    """Was die Operation dem Sprachmodell sagt, ist nicht, was sie dem Nutzer
    sagt.

    Im ``doc`` von *Quader anlegen* stand „Erst in der Bausteinbibliothek
    suchen" — eine Regel aus ``rules.toml``, gelandet in dem Feld, das der
    Nutzer im Dialog liest. Wer auf „Quader anlegen" klickt, hat sich
    entschieden.

    Geprüft wird gegen die Regelsammlung selbst: taucht ein ganzer Regelsatz in
    einem Dialogtext auf, ist er dort falsch.
    """
    from app.core.knowledge.rules import load

    doc = " ".join(str(spec.doc).split())
    for rule in load().rules:
        for sentence in rule.text.split("."):
            trimmed = " ".join(sentence.split())
            if len(trimmed) < 25:
                continue
            assert trimmed not in doc, f"{spec.name}: Agentenregel im Nutzertext — {trimmed[:60]}"


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_non_deterministic_operations_use_a_seed(spec: OperationSpec) -> None:
    if spec.deterministic:
        return
    source = inspect.getsource(spec.fn)
    assert "seed" in source, f"{spec.name} is marked non-deterministic but never reads ctx.seed"


#: Wo die Bausteine gesammelt geprüft werden, und woran man erkennt, dass es
#: **alle** sind: an der Ableitung aus dem Register statt aus einer Namensliste.
#:
#: **Der Träger hat am 03.09.2026 gewechselt.** Bis dahin stand hier
#: ``test_a_part_holds_over_its_whole_range``, der jeden Baustein über sein
#: ganzes Parameterprodukt rechnete — rund eine Minute je Baustein, eine halbe
#: Stunde je Torlauf, und deshalb gefallen (Entscheidung Robert). Was diese
#: Stelle braucht, ist aber gar nicht der teure Lauf, sondern ein Test, der
#: **jeden** Baustein aus dem Register anfasst; das leistet der Merkmalstest
#: genauso und in Sekunden.
PARTS_TEST: Final = "test_parts.py"
PARTS_SWEEP: Final = "test_a_part_names_the_features_it_promised"


def parts_under_range_check() -> set[str]:
    """Welche Bausteine der Bereichstest aus `test_parts.py` wirklich fährt.

    **Gefragt wird die Sammlung, nicht der Dateitext.** Der Freibrief unten
    hing bis zum 26.08.2026 an ``"PARTS.all()" in test_parts.py`` — eine
    Zeichenkette, die ein Kommentar am Leben hält und die auch dann noch
    dasteht, wenn die Liste vor der Parametrisierung gefiltert wird. Gelesen
    wird deshalb die Parameterliste des Sweeps selbst: Was dort nicht
    drinsteht, wird nicht gefahren, gleich was in der Datei geschrieben steht.
    """
    from tests import test_parts

    sweep = getattr(test_parts, PARTS_SWEEP, None)
    assert sweep is not None, (
        f"{PARTS_TEST} hat kein {PARTS_SWEEP} mehr — der Nachweis, dass jede "
        "Baustein-Operation von einem Test angefasst wird, hängt daran"
    )
    marks = [
        mark
        for mark in getattr(sweep, "pytestmark", [])
        if mark.name == "parametrize" and mark.args and mark.args[0] == "spec"
    ]
    assert marks, f"{PARTS_SWEEP} läuft nicht mehr über eine Bausteinliste"
    geprueft = {entry.name for mark in marks for entry in mark.args[1]}
    assert geprueft, f"{PARTS_SWEEP} sammelt keinen einzigen Baustein ein"
    return geprueft


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_every_operation_has_a_test(spec: OperationSpec) -> None:
    """Eine neue Operation ohne Test ist nicht fertig (AGENTS.md, Checkliste).

    Gesucht wird der **Name** im Text einer Testdatei, und das ist eine
    Näherung — sie war immer eine. Für Bausteine ist sie am 25.08.2026
    zerbrochen: `test_parts.py` führte zwei handgepflegte Namenslisten, in
    denen die zwei neuesten Bausteine fehlten, und als sie durch eine
    Ableitung aus dem Register ersetzt wurden, verschwanden mit den Listen
    auch die Erwähnungen. Drei Bausteine wurden rot, die seither **besser**
    geprüft sind als vorher.

    Für eine Baustein-Operation gilt deshalb ein zweiter Weg: Steht der
    Baustein in der Parameterliste des Bereichstests, ist er gefahren —
    namentlich genannt wird keiner mehr, und das ist der Fortschritt und nicht
    die Lücke. Das ist kein Freibrief: Fehlt er dort, greift wieder die
    Namenssuche, und ein Baustein ohne beides ist so ungeprüft wie jede andere
    Operation ohne Test.
    """
    mentions = [
        path.name
        for path in TESTS_DIR.rglob("test_*.py")
        if path.name != Path(__file__).name and spec.name in path.read_text(encoding="utf-8")
    ]
    if mentions:
        return

    from app.core.knowledge.parts.ops import part_of

    part = part_of(spec.name)
    if part is not None and part.name in parts_under_range_check():
        return

    raise AssertionError(f"no test mentions {spec.name}")


def test_shortcuts_are_unique() -> None:
    shortcuts = [spec.shortcut.casefold() for spec in registered() if spec.shortcut]
    assert len(shortcuts) == len(set(shortcuts))


def test_every_operation_reaches_every_surface() -> None:
    names = {spec.name for spec in registered()}
    assert {spec.name for section in menu_tree() for spec in section.entries} == names
    assert {entry.name for entry in palette_entries()} == names
    assert {command.name for command in cli_commands()} == names
    assert {schema["name"] for schema in tool_schemas()} == names
    text = documentation()
    assert all(f"`{name}`" in text for name in names)


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_a_parameter_set_can_always_be_taken_apart(spec: OperationSpec) -> None:
    """``fields()`` warf bei einer parameterlosen Operation.

    *Objekt löschen* braucht keine Parameter, und ihr Parametersatz ist deshalb
    ``BaseParams`` selbst — keine Dataclass. ``dataclasses.fields`` wirft dort
    ein nacktes ``TypeError``, das weder ein ``AppError`` ist noch einen
    Handlungsvorschlag trägt (Regel 17); zu beheben gibt es dabei nichts, denn
    „kein Parameter" ist eine gültige Antwort. Wer über das Register läuft — die
    Baustein-Operationen tun es (§24.1) — traf damit auf einen Abbruch statt auf
    eine leere Liste.

    Und die Felder gehören zum Schema: Was das eine kennt, kennt das andere.
    """
    entries = spec.params.fields()
    assert {entry.name for entry in entries} >= {entry.name for entry in spec.params.spec()}, (
        f"{spec.name}: das Schema nennt Parameter, die als Feld fehlen"
    )


def test_one_spelling_for_the_angle() -> None:
    """Sechsundzwanzig Winkel trugen „grad", vier trugen „°".

    Im Dialog las sich das als „Winkel [grad]" in *Senken* und „Winkel [°]" in
    *Formschräge anstellen* — zwei Schreibweisen derselben Einheit im selben
    Produkt. „grad" ist obendrein ein roher deutscher Schlüssel: Er steht in
    keinem Katalog, also stand er auch in der englischen Oberfläche so da.

    Geprüft wird über das ganze Register, denn eine Vereinbarung hält nur bis
    zum nächsten Winkelparameter. Erlaubt sind Millimeter und
    :data:`DEGREE_UNIT`; wer eine dritte Einheit braucht, trägt sie hier ein und
    entscheidet damit bewusst.
    """
    from app.core.units import DEGREE_UNIT

    allowed = {"mm", DEGREE_UNIT}
    found: dict[str, list[str]] = {}
    for spec in registered():
        for entry in spec.params.spec():
            if entry.unit and entry.unit not in allowed:
                found.setdefault(entry.unit, []).append(f"{spec.name}.{entry.name}")
    assert not found, f"unbekannte Einheiten im Register: {found}"

    angles = [
        f"{spec.name}.{entry.name}"
        for spec in registered()
        for entry in spec.params.spec()
        if entry.unit == DEGREE_UNIT
    ]
    assert len(angles) > 20, f"nur {len(angles)} Winkelparameter — prüft dieser Test noch etwas?"


def test_the_shared_placement_names_match_the_parts_library() -> None:
    """Das Register erklärt die geteilten Ortsangaben der Bausteine einmal am
    Kategoriekopf und filtert sie aus den Einzeltabellen — über eine eigene
    Namensliste, weil es die Bausteinbibliothek nicht importieren darf.
    Driftet eine der beiden Seiten, verschwinden Parameter aus dem Handbuch
    oder stehen wieder doppelt.
    """
    from app.core.knowledge.parts.ops import _PLACEMENT
    from app.core.registry.surfaces import PART_PLACEMENT_PARAMS

    assert tuple(name for name, _kind, _spec in _PLACEMENT) == PART_PLACEMENT_PARAMS


def test_every_detected_feature_kind_offers_an_operation() -> None:
    """Ein angeklicktes Merkmal führt zu einer Handlung — oder es steht im
    Ausnahmeverzeichnis unten (§2.6, §18.5).

    **Warum das eine eigene Prüfung braucht.** ``applies_to`` sagt, welche
    Merkmale eine Operation annimmt; die Gegenrichtung sagt niemand. Sie fiel
    beim Nachfahren von Weg 1 auf: ``edge_loop`` ist das Merkmal für eine
    offene Stelle im Netz — genau das, was der Prüfbericht als „Das Modell ist
    an drei Stellen offen" meldet — und das Kontextmenü daran bot nichts an.
    Dabei gibt es ``repair`` („Schließt Löcher"), es hatte sich nur für kein
    Merkmal angemeldet. §2.6 nennt das Kontextmenü „den kürzesten Weg vom
    Sehen zum Tun"; für den häufigsten Defekt führte er ins Leere.

    Geprüft werden nur Arten, die auch **entstehen**: ``FEATURE_KINDS`` kommt
    aus dem Typ und führt Vorrat, der noch keinen Erzeuger hat. Ein Merkmal,
    das niemand anklicken kann, braucht kein Menü. Woher die Menge stammt,
    steht unten — sie wird abgeleitet und nicht gepflegt, und der Grund dafür
    ist ein Fall von heute.
    """
    from app.core.perceive.features import DETECTABLE_KINDS
    from app.core.registry import REGISTRY

    #: Erzeugt, aber ohne Operation — je Art mit dem Grund, warum das offen
    #: ist. Beim Lösen hier streichen, nicht die Prüfung aufweichen.
    known_gaps = {
        # Der Gewinde-Baustein gibt dieses Merkmal zurück
        # (knowledge/parts/build.py), und über ``applies_to`` bleibt es leer —
        # aber nicht mehr, weil die Frage offen wäre. §21.2 hat sie am
        # 22.08.2026 anders beantwortet, als sie gestellt war: Ein erzeugtes
        # Merkmal bietet **seinen Erzeugerschritt** an („Diesen Schritt
        # ändern", über ``Feature.created_by`` und ``ObjectTree``), nicht eine
        # Operation je Merkmalsart. Der Klick führt also irgendwohin; er nimmt
        # nur den anderen der beiden Wege, und diese Prüfung kennt bisher den
        # einen.
        "thread",
        # Kugel und Torus sind aus einem anderen Grund offen als ``thread``:
        # Dort ist ``applies_to`` der falsche Weg (§21.2 entscheidet es über
        # die Provenienz), hier gibt es die Handlung noch gar nicht. §41 führt
        # beide als Ausbaustufe, und der Umfang war ausdrücklich auf die
        # Wahrnehmung geschnitten. Eine Operation zu erfinden, damit diese
        # Prüfung grün wird, hieße die Reihenfolge umzudrehen.
        "sphere",
        "torus",
        # Verrundung: Der Klick führt über **keinen** der beiden Wege irgendwohin,
        # und beide Gründe gehören hier hin — sonst hält der Nächste den ersten
        # für gelöst, so wie ich es getan habe.
        #
        # Über ``applies_to``: ``fillet_edges`` („Verrunden") wirkt auf **Kanten**.
        # Eine Verrundung ist keine Kante, sondern ihr Ergebnis; wer sie anklickt,
        # will den Radius ändern und nicht die Rundung runden. Und an eingelesener
        # Geometrie gibt es die Operation ohnehin nicht (B-Rep-Kern, §30) — ein
        # Menüeintrag, der bei jedem Netz anhält, ist schlechter als keiner.
        #
        # Über die Provenienz (§21.2, „Diesen Schritt ändern") ebenfalls nicht:
        # ``_with_features`` setzt ``created_by`` nur bei
        # ``provenance == "generated"``, und eine selbst gesetzte Verrundung ist
        # ``detected``. Der Fall „Solidon hat sie erzeugt" fällt damit genauso aus
        # wie der eingelesene, nur aus einem anderen Grund.
        #
        # Registerpunkt: 4b925ee. Gefunden von 3d-druck-3a, die Provenienz-Hälfte
        # berichtigt von 3d-druck-64.
        "fillet",
    }
    #: Abgeleitet und nicht aufgezählt — der Unterschied hat am 22.08.2026
    #: genau eine Runde gehalten.
    #:
    #: Hier stand eine Liste von Hand, und als ``sphere`` und ``torus``
    #: dazukamen, passierte das Schlimmste, was einer Prüfung passieren kann:
    #: **nichts.** Kein roter Lauf, keine Meldung — die zwei neuen Arten
    #: standen einfach nicht darin und wurden nie gefragt, ob ein Klick auf
    #: sie irgendwohin führt. Gefunden hat es keine Prüfung, sondern eine
    #: Absprache zwischen zwei Sitzungen, die zufällig gleichzeitig liefen.
    #: Wer in vier Wochen eine Merkmalsart ergänzt, hat diese Absprache nicht.
    #:
    #: ``DETECTABLE_KINDS`` ist die Menge, die ``detect()`` wirklich erzeugt —
    #: nicht ``FEATURE_KINDS``, denn der Typ führt auch Vorrat ohne Erzeuger,
    #: und ein Merkmal, das niemand anklicken kann, braucht kein Menü.
    #: ``thread`` kommt nicht aus der Erkennung, sondern aus dem
    #: Gewinde-Baustein, und wird deshalb einzeln dazugelegt.
    produced = set(DETECTABLE_KINDS) | {"thread"}

    empty = {kind for kind in produced if not REGISTRY.for_feature(kind)}
    assert empty <= known_gaps, (
        f"Merkmale ohne jede Operation im Kontextmenü: {sorted(empty - known_gaps)} — "
        "ein Klick darauf endet in einem Menü aus Ausblenden (§2.6)"
    )
    assert produced >= known_gaps, (
        f"Ausnahme für ein Merkmal, das nicht entsteht: {sorted(known_gaps - produced)}"
    )


def test_no_operation_calls_its_core_function_with_an_argument_it_refuses() -> None:
    """Eine Operation ruft nur, was ihre Kernfunktion annimmt.

    **Der Fund, der diese Prüfung veranlasst hat.** ``plug_hole`` übergab
    ``profile=ctx.profile`` an ``plug()``, und ``plug()`` hatte diesen
    Parameter nicht. Die Operation „Loch verschließen" konnte damit mit keinem
    Wert durchlaufen: Der ``TypeError`` wurde zum ``InternalError``, und der
    Nutzer bekam „Im Programm ist ein unerwarteter Fehler aufgetreten" samt
    Knopf für den Fehlerbericht — auf einen Klick, an dem nichts falsch war.

    **Warum die Suite geschwiegen hat.** ``tests/test_missing_ops.py`` prüft
    ``plug()`` — die Funktion, direkt, mit den richtigen Argumenten. Sie ist in
    Ordnung. Geprüft hat niemand die Zeile *zwischen* Register und Funktion.
    Genau diesen Blindfleck beschreibt ``errors.py`` bei
    ``PROGRAMMING_ERRORS``: „ihr Test übersprang sich aus demselben Grund, und
    der Hinweispfad war zwei Phasen lang tot — hinter einer grünen Suite."

    Geprüft wird statisch und nicht durch Fahren: Ein Lauf über 86 Operationen
    braucht Eingangskörper, die zu jeder passen, und eine Operation, die aus
    einem anderen Grund anhält, verdeckt diesen hier. Der Syntaxbaum kennt die
    Aufrufe, ``inspect`` die Signaturen — das genügt und kostet nichts.

    **Die Bausteine gehen mit.** Sie rufen dieselben Kernfunktionen und stehen
    in einem eigenen Register; der Fehler von ``plug_hole`` wäre dort genauso
    möglich und genauso unsichtbar. Gemessen sind sie heute sauber — geprüft
    waren sie nicht.
    """
    from app.core.knowledge.parts.registry import PARTS

    # **Die Module, nicht nur die eintragenden Funktionen.** Erst prüfte diese
    # Stelle ``spec.fn`` allein, und eine Gegenprobe zeigte, was das wert ist:
    # ein erfundenes Schlüsselwort in einer Hilfsfunktion von ``fasteners.py``
    # blieb unentdeckt. ``plug_hole`` fiel nur auf, weil der falsche Aufruf
    # zufällig in der Operation selbst stand. Geprüft wird deshalb jedes Modul,
    # das eine Operation oder einen Baustein hält — mit allem, was darin steht.
    both: list[Any] = [*registered(), *PARTS.all()]
    # **Sagt selbst, dass die Menge nicht leer ist.** Beides sind
    # Verbotstests: grün, sobald both leer wäre. Und das ist kein
    # erfundener Fall — ohne load_operations() hat das Register **null**
    # Operationen statt 86, und beide Prüfungen liefen still ins Nichts.
    assert both, "weder Operationen noch Bausteine — sonst prüft dieser Test nichts"
    modules = {module for spec in both if (module := inspect.getmodule(spec.fn)) is not None}
    offenders: list[str] = []
    for module in sorted(modules, key=lambda entry: entry.__name__):
        namespace = vars(module)
        try:
            source = textwrap.dedent(inspect.getsource(module))
            tree = ast.parse(source)
        except (OSError, SyntaxError, TypeError):  # pragma: no cover - Vorsicht
            continue
        where = module.__name__

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            target = namespace.get(node.func.id)
            # Nur echte Funktionen dieses Projekts: Klassen nehmen über
            # ``__init__`` an, C-Funktionen haben keine lesbare Signatur, und
            # ein Name, den das Modul nicht kennt, ist ein lokaler.
            if not inspect.isfunction(target):
                continue
            try:
                parameters = inspect.signature(target).parameters
            except (TypeError, ValueError):  # pragma: no cover - Vorsicht
                continue
            if any(p.kind is p.VAR_KEYWORD for p in parameters.values()):
                continue
            for keyword in node.keywords:
                if keyword.arg and keyword.arg not in parameters:
                    offenders.append(
                        f"{where}:{node.lineno} → {node.func.id}(…, {keyword.arg}=…) "
                        f"— {node.func.id} nimmt {sorted(parameters)}"
                    )

    assert not offenders, "Operationen rufen ihre Kernfunktion falsch auf:\n" + "\n".join(offenders)


def test_every_expression_example_in_the_register_actually_evaluates() -> None:
    """**Ein Beispiel, das der eigene Auswerter ablehnt, ist schlechter als
    keines.**

    Der Hilfetext von ``create_box --width`` nannte ``=breite*2``. Genau so
    getippt antwortet der Auswerter „Unbekannter Name im Ausdruck. Parameter
    werden mit @ geschrieben." — der Kunde wird aufgefangen, aber er wurde
    vorher falsch losgeschickt. Gefunden beim Lesen der
    Kommandozeilenhilfe.

    Geprüft wird jeder Text des Registers, der wie ein Ausdrucksbeispiel
    aussieht: Er muss sich gegen einen Parameter dieses Namens wirklich
    ausrechnen lassen.
    """
    import re

    from app.core import expressions
    from app.core.types import Parameter

    #: Was in einem Dokumentationstext ein Ausdrucksbeispiel ist: ein
    #: Gleichheitszeichen, dahinter etwas ohne Leerzeichen. Der Satzpunkt
    #: gehört nicht dazu.
    muster = re.compile(r"=[^\s,;.]+")

    texte: list[tuple[str, str]] = []
    for spec in REGISTRY.all():
        texte.append((spec.name, str(spec.doc or "")))
        for entry in spec.params.spec():
            texte.append((f"{spec.name}.{entry.name}", str(entry.doc or "")))
            texte.append((f"{spec.name}.{entry.name} (Titel)", str(entry.title or "")))

    geprueft = 0
    for wo, text in texte:
        for treffer in muster.findall(text):
            # Namen der Parameter im Beispiel einsammeln und mit Werten
            # belegen — der Test prüft die Form, nicht die Zahl.
            namen = re.findall(r"@([A-Za-z_][A-Za-z_0-9]*)", treffer)
            werte = {name: Parameter(name=name, value=2.0, unit="mm") for name in namen}
            werte["_probe"] = Parameter(name="_probe", value=0.0, unit="mm", expression=treffer)
            try:
                expressions.resolve(werte)
            except Exception as problem:
                raise AssertionError(
                    f"{wo}: das Beispiel „{treffer}“ lässt sich nicht ausrechnen — "
                    f"{type(problem).__name__}: {problem}"
                ) from problem
            geprueft += 1

    assert geprueft, "es gibt Ausdrucksbeispiele im Register, und sie werden geprüft"


#: Was eine Auswertung von außen holen könnte, ohne dass es im Stack, in den
#: Quellen, den Parametern, den Profilen oder dem Startwert steht — und wie es
#: in der Meldung heißen soll. ``os.path`` heißt je nach System ``ntpath`` oder
#: ``posixpath``; beide Namen stehen hier, damit die Prüfung unter Linux findet,
#: was sie unter Windows findet.
_OUTSIDE_WORLD: Final[dict[str, str]] = {
    "time.time": "die Uhr",
    "time.time_ns": "die Uhr",
    "time.monotonic": "die Uhr",
    "time.monotonic_ns": "die Uhr",
    "time.perf_counter": "die Uhr",
    "time.perf_counter_ns": "die Uhr",
    "time.process_time": "die Uhr",
    "time.localtime": "die Uhr",
    "time.gmtime": "die Uhr",
    "datetime.datetime.now": "die Uhr",
    "datetime.datetime.today": "die Uhr",
    "datetime.datetime.utcnow": "die Uhr",
    "datetime.date.today": "die Uhr",
    "os.environ": "die Umgebung",
    "os.environb": "die Umgebung",
    "os.getenv": "die Umgebung",
    "os.getenvb": "die Umgebung",
    "os.getcwd": "das Arbeitsverzeichnis",
    "os.getcwdb": "das Arbeitsverzeichnis",
    "pathlib.Path.cwd": "das Arbeitsverzeichnis",
    "pathlib.Path.home": "das Nutzerverzeichnis",
    "os.path.expanduser": "das Nutzerverzeichnis",
    "ntpath.expanduser": "das Nutzerverzeichnis",
    "posixpath.expanduser": "das Nutzerverzeichnis",
    "app.core.paths.user_data_dir": "den Nutzerordner",
    "app.core.paths.user_config_dir": "den Nutzerordner",
    "app.core.paths.user_cache_dir": "den Nutzerordner",
    "socket.gethostname": "den Rechnernamen",
    "platform.node": "den Rechnernamen",
    "getpass.getuser": "den angemeldeten Nutzer",
}

#: Die Module, in denen gerechnet wird. Durch sie wird der Aufrufgraph verfolgt,
#: durch die übrigen nicht — die Begründung steht im Test.
_COMPUTING: Final[tuple[str, ...]] = (
    "app.core.geom",
    "app.core.sketch",
    "app.core.brep",
    "app.core.scene",
    "app.core.slice",
    "app.core.perceive",
    "app.core.ingest",
    "app.core.knowledge",
)


def _dotted_name(node: ast.expr) -> list[str]:
    """Zerlegt ``a.b.c`` in seine Glieder; alles andere ergibt eine leere Liste."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return []
    parts.append(node.id)
    parts.reverse()
    return parts


def _import_aliases(tree: ast.AST) -> dict[str, str]:
    """Welcher Name in diesem Baum wofür steht — ``import``-Anweisungen, auch die
    innerhalb einer Funktion.

    Ohne sie liest die Prüfung nur die Hälfte: Ein ``import datetime`` mitten in
    der Funktion legt nichts im Namensraum des Moduls ab, und genau diese Form
    ist im Bestand üblich. Die erste Fassung dieser Prüfung übersah sie —
    gemeldet hat es die Gegenprobe unten, nicht das Nachdenken darüber.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # ``import os.path`` bindet ``os``, ``import os.path as p`` bindet p.
                aliases[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _public_module(name: str) -> str:
    """Streicht die privaten Zwischenmodule aus einem Herkunftsnamen.

    ``pathlib.Path`` sagt seit Python 3.13 von sich, es komme aus
    ``pathlib._local`` — geschrieben wird trotzdem ``pathlib.Path``. Die zweite
    Gegenprobe unten fiel genau darüber; ohne diese Zeile stünde in der Liste
    oben ein Name, den niemand tippt, und die Prüfung liefe ins Leere.
    """
    return ".".join(part for part in name.split(".") if not part.startswith("_"))


def _qualify(namespace: dict[str, Any], aliases: dict[str, str], parts: list[str]) -> str | None:
    """Macht aus den Gliedern den vollen Namen.

    ``datetime.now()`` nach ``import datetime`` und ``datetime.now()`` nach
    ``from datetime import datetime`` ergeben beide ``datetime.datetime.now``:
    Erst greift die Zuordnung aus den ``import``-Anweisungen, danach das, was
    wirklich im Namensraum des Moduls liegt. Über den Namen allein ginge es
    nicht — ``monotonic()`` sagt nicht, aus welchem Modul es kommt.
    """
    if parts[0] in aliases:
        return ".".join([aliases[parts[0]], *parts[1:]])
    head = namespace.get(parts[0])
    if head is None:
        return None
    if inspect.ismodule(head):
        base = _public_module(head.__name__)
    else:
        module = getattr(head, "__module__", None)
        qualname = getattr(head, "__qualname__", None)
        if not module or not qualname:
            return None
        base = f"{_public_module(module)}.{qualname}"
    return ".".join([base, *parts[1:]])


def _reads_from_outside(seeds: Iterable[Any], inside: tuple[str, ...]) -> list[str]:
    """Verfolgt den Aufrufgraph von ``seeds`` aus durch die Module in ``inside``
    und meldet jede Stelle, die etwas aus ``_OUTSIDE_WORLD`` liest.

    Verfolgt werden Aufrufe, die sich statisch auflösen lassen: freie Namen und
    Modulattribute. Ein Aufruf über ein Objekt (``self.helper()``) bleibt außen
    vor — dafür bräuchte es Typinferenz, und die Stelle, an der eine Operation
    die Uhr läse, ist eine Funktion und keine Methode.
    """
    found: list[str] = []
    queue: list[Any] = list(seeds)
    visited: set[str] = set()
    while queue:
        function = queue.pop()
        module = inspect.getmodule(function)
        if module is None or not module.__name__.startswith(inside):
            continue
        where = f"{module.__name__}.{getattr(function, '__qualname__', '?')}"
        if where in visited:
            continue
        visited.add(where)
        try:
            tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
        except (OSError, SyntaxError, TypeError):  # pragma: no cover - Vorsicht
            continue
        namespace = vars(module)
        aliases = _import_aliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute | ast.Name):
                parts = _dotted_name(node)
                name = _qualify(namespace, aliases, parts) if parts else None
                if name in _OUTSIDE_WORLD:
                    found.append(
                        f"{where} (Zeile {node.lineno}) liest {_OUTSIDE_WORLD[name]} — {name}"
                    )
            if isinstance(node, ast.Call):
                parts = _dotted_name(node.func)
                target: Any = None
                if parts:
                    target = namespace.get(parts[0])
                    for step in parts[1:]:
                        target = getattr(target, step, None)
                if inspect.isfunction(target):
                    queue.append(target)
    return sorted(set(found))


def test_no_operation_reads_the_clock_the_environment_or_the_machine() -> None:
    """Die Auswertung ist eine reine Funktion — für den Zufall durchgesetzt, für
    alles andere bisher eine Absichtserklärung (§15.1).

    Aus Stack, Quellen, Parametern, Profilen und Startwerten muss dasselbe
    Ergebnis folgen, heute und auf einem anderen Rechner. Für den **Zufall** hält
    das jemand: ``operation_hash`` nimmt ``operation.seed``, Regel 9 verlangt den
    gespeicherten Startwert, und ``test_non_deterministic_operations_use_a_seed``
    weiter oben prüft ihn. Für die Uhr, die Umgebung und das Nutzerverzeichnis
    hielt das niemand — eine künftige Operation mit ``datetime.now()`` darin wäre
    keine reine Funktion, und kein Test hätte es gemerkt. Aufgefallen ist es beim
    Plattencache, wo eine unreine Operation den Cache still vergiftet hätte; die
    Regel gilt aber ohne jede Cache-Ebene.

    **Wie weit die Prüfung reicht, ist gemessen und nicht gewählt.** Nur die
    Module, die Operationen halten, sehen zu wenig — sie fänden nichts, was eine
    Hilfsfunktion zwei Ebenen tiefer tut. Der ganze Aufrufgraph durch ``app.``
    dagegen meldet fünfzehn Stellen, und alle fünfzehn sind in Ordnung:
    ``perf_counter`` in einem Backend misst die Laufzeit eines
    Unterprozesses, ``os.environ`` und ``Path.home`` in ``discover`` und
    ``paths`` suchen das fremde Werkzeug und den Nutzerordner. Eine Prüfung mit
    fünfzehn Ausnahmen prüft nichts mehr. Verfolgt wird deshalb der Aufrufgraph
    durch die **rechnenden** Module: Wo gerechnet wird, gibt es keinen Grund, die
    Uhr zu lesen; wo ein fremdes Werkzeug gesucht und gestartet wird, gibt es ihn.

    Nicht in der Liste stehen ``random`` und ``uuid4``: Der Zufall ist über
    Regel 9 und den Determinismustest gedeckt, und eine zweite Stelle, die
    dasselbe prüft, driftet von der ersten weg.
    """
    from app.core.knowledge.parts.registry import PARTS

    both: list[Any] = [*registered(), *PARTS.all()]
    # **Sagt selbst, dass die Menge nicht leer ist.** Beides sind
    # Verbotstests: grün, sobald both leer wäre. Und das ist kein
    # erfundener Fall — ohne load_operations() hat das Register **null**
    # Operationen statt 86, und beide Prüfungen liefen still ins Nichts.
    assert both, "weder Operationen noch Bausteine — sonst prüft dieser Test nichts"
    offenders = _reads_from_outside([spec.fn for spec in both], _COMPUTING)
    assert not offenders, (
        "Die Auswertung holt sich etwas von außen — das gehört in einen Parameter, "
        "ein Profil oder den Startwert (§15.1):\n" + "\n".join(offenders)
    )


def _probe_reads_the_clock() -> float:
    """Gegenprobe: liest die Uhr über einen Import innerhalb der Funktion."""
    import datetime

    return datetime.datetime.now().timestamp()


def _probe_reads_a_renamed_clock() -> float:
    """Gegenprobe: liest die Uhr über einen umbenannten Einzelimport."""
    from time import monotonic as tick

    return tick()


def _probe_reads_the_home_directory() -> Path:
    """Gegenprobe: liest das Nutzerverzeichnis über den Namensraum des Moduls."""
    return Path.home()


def _probe_calls_something_impure() -> float:
    """Gegenprobe: tut selbst nichts, ruft aber etwas Unreines."""
    return _probe_reads_the_clock()


def _probe_is_clean() -> Path:
    """Gegenprobe in die andere Richtung: rechnet und liest nichts von außen."""
    return Path("werkstueck") / "deckel.stl"


def test_the_purity_check_would_notice() -> None:
    """Eine Prüfung, die nichts findet, ist erst dann eine gute Nachricht, wenn
    sie zeigen kann, dass sie etwas fände.

    Die erste Fassung fand die vier Fälle unten **nicht** — sie sah nur in den
    Namensraum des Moduls, und ein ``import`` innerhalb der Funktion legt dort
    nichts ab. Der Bestand war trotzdem grün, und ohne diese Gegenprobe wäre er
    es aus dem falschen Grund geblieben. Sie bleibt deshalb stehen: Sie prüft
    nicht den Code der Anwendung, sondern das Werkzeug darüber.

    Die letzte Probe geht in die andere Richtung — eine Prüfung, die alles
    meldet, ist so wertlos wie eine, die nichts meldet.
    """
    here = (__name__,)
    for probe in (
        _probe_reads_the_clock,
        _probe_reads_a_renamed_clock,
        _probe_reads_the_home_directory,
        _probe_calls_something_impure,
    ):
        assert _reads_from_outside([probe], here), (
            f"die Prüfung übersieht {probe.__name__} — sie ist eine Attrappe"
        )
    assert not _reads_from_outside([_probe_is_clean], here), (
        "die Prüfung meldet eine saubere Funktion — so wird sie abgeschaltet"
    )


# --- Jede Parameterart wird geprüft, und zwar als das, was sie ist ----------------


def test_every_parameter_kind_is_sorted_into_a_check() -> None:
    """Ein ``kind``, den ``_coerce`` nicht kennt, machte jedes Feld still zum
    Textfeld — samt Verlust seiner Grenzen.

    Gefunden hat es Robert am 27.08.2026 an der Oberfläche: „Bei Auswahl eines
    Filaments kommt die Meldung Text wird erwartet." Die Ursache lag zwei
    Ebenen tiefer. ``_coerce`` verzweigte über ``bool``, dann ``float``/``int``
    — und alles Übrige fiel in den Textzweig. ``slot`` ist ein ganzzahliges
    Feld mit Grenzen 0 bis 7; sobald es ``kind="filament"`` trug (richtig, die
    Oberfläche soll dort den Wähler zeigen), lehnte die Prüfung die Zahl ab.

    **Und die stille Hälfte war die schlimmere:** ``{"slot": "Rot"}`` wurde
    *angenommen*. Ein Feld im Textzweig hat keine Ober- und Untergrenze mehr,
    also wäre auch Slot 99 durchgegangen — ohne Meldung, bis der Slicer nach
    hundert Filamenten fragt.

    Deshalb wird hier nicht ein ``kind`` nachgetragen, sondern die Lücke
    geschlossen: Jede Art steht in genau einer der beiden Mengen, und wer eine
    neue einführt, ordnet sie ein — oder dieser Lauf ist rot und sagt, welche
    fehlt. Dieselbe Bauart wie ``_RANGE_CONSTRAINTS``/``_NOT_A_RANGE`` bei den
    Beschränkungen.
    """
    from typing import get_args

    from app.core.registry import params as params_module
    from app.core.types import ParamKind

    known = set(get_args(ParamKind))
    assert len(known) > 10, "zu wenige Arten gefunden — die Aufzählung ist nicht die gemeinte"

    sorted_out = params_module.NUMBER_KINDS | params_module.TEXT_KINDS | {"bool"}
    missing = known - sorted_out
    assert not missing, (
        "Diese Parameterarten kennt keine der beiden Mengen — trag sie in "
        "``params.NUMBER_KINDS`` ein, wenn der Kern eine Zahl bekommt, sonst in "
        f"``params.TEXT_KINDS``: {sorted(missing)}"
    )

    invented = sorted_out - known - {"bool"}
    assert not invented, f"Diese Arten gibt es in ``ParamKind`` nicht: {sorted(invented)}"

    both = params_module.NUMBER_KINDS & params_module.TEXT_KINDS
    assert not both, f"Zahl und Text zugleich geht nicht: {sorted(both)}"


def test_a_filament_parameter_takes_a_number_and_keeps_its_bounds() -> None:
    """Der Fall, an dem es aufgefallen ist — als Zusage.

    Die Nummer eines Materialslots ist im Kern eine Zahl wie zuvor; der
    Filamentwähler ist eine Sache der Oberfläche. Beide Richtungen gehören
    geprüft: Die Zahl kommt an, und der Text nicht — denn genau dieser
    Textzweig hatte die Grenzen des Feldes verschluckt.
    """
    from app.core.errors import ValidationError
    from app.core.registry.params import validate

    spec = REGISTRY.get("paint_slot")

    taken = validate(spec.params, {"slot": 1, "at_feature": "face_1"})
    assert taken.slot == 1

    with pytest.raises(ValidationError):
        validate(spec.params, {"slot": "Rot", "at_feature": "face_1"})

    with pytest.raises(ValidationError):
        validate(spec.params, {"slot": 99, "at_feature": "face_1"})


def test_the_slot_limit_is_one_number_not_three() -> None:
    """``MAX_SLOTS`` stand dreimal im Code, mit derselben Zahl und dem
    Kommentar „wie bei den Farb-Operationen" daneben — ein Verweis auf die
    Kopie statt geteilter Sache.

    Das ist die Bauart, aus der Zwillinge entstehen (Robert, 27.08.2026):
    Wer die Grenze eines Tages ändert, ändert sie an einer Stelle, und zwei
    Operationen erlauben danach etwas anderes als die dritte. Der Kunde sieht
    davon nichts, bis eine Farbe im Slicer fehlt.

    Geprüft wird nicht der Quelltext, sondern die **Wirkung**: Jedes Feld, das
    ein Filament benennt, hat dieselbe Obergrenze.
    """
    limits = {
        (op.name, entry.name): entry.maximum
        for op in REGISTRY.all()
        for entry in op.params.spec()
        if entry.kind == "filament"
    }
    assert len(limits) >= 3, f"zu wenige Filamentfelder gefunden ({len(limits)}) — prüft das etwas?"
    assert len(set(limits.values())) == 1, f"verschiedene Obergrenzen für dasselbe: {limits}"


#: Zahlwörter, wie die Regeldateien sie schreiben — Ziffern stehen dort nicht.
_ZAHLWORT: Final[dict[str, int]] = {
    "elf": 11,
    "zwölf": 12,
    "zwanzig": 20,
    "sechsundzwanzig": 26,
    "siebenundzwanzig": 27,
    "achtundzwanzig": 28,
    "neunundzwanzig": 29,
    "dreißig": 30,
    "fünfundneunzig": 95,
    "neunundneunzig": 99,
    "hundert": 100,
    "sechsundneunzig": 96,
    "siebenundneunzig": 97,
}


def test_the_rule_file_counts_the_caveats_it_claims() -> None:
    """Eine Zahl in einer Regeldatei altert genauso still wie eine in einer Mail.

    `.claude/rules/oberflaeche.md` nannte „Zwölf Operationen tragen einen
    ``caveat``". Gemessen am 29.08.2026 waren es **sechsundzwanzig** von
    fünfundneunzig — mehr als das Doppelte, und niemand hat es bemerkt, weil
    eine Doku-Zahl niemandem auffällt, solange sie plausibel klingt. Gefunden
    hat sie eine Nachbarsitzung beim Bauen einer ganz anderen Prüfung.

    Der Fehler war dabei nicht die falsche Zahl, sondern dass sie **ungeprüft**
    dastand. Dieselbe Klammer, die `test_changelog.py` seit demselben Abend um
    die Presseentwürfe legt, gehört deshalb auch hierher: Wer eine Operation
    mit ``caveat`` hinzufügt, zieht den Satz nach oder bekommt einen roten Lauf.

    Geprüft werden **beide** Zahlen des Satzes — die mit ``caveat`` und die
    Gesamtzahl. Eine davon allein wäre die Hälfte der Aussage.
    """
    regel = Path(__file__).resolve().parent.parent / ".claude" / "rules" / "oberflaeche.md"
    assert regel.exists(), f"die Regeldatei fehlt: {regel}"
    text = regel.read_text(encoding="utf-8")

    satz = re.search(r"([A-Za-zäöüß]+) von ([A-Za-zäöüß]+)\s*\n?\s*Operationen tragen einen", text)
    assert satz, (
        "der Satz über die caveat-Zahl steht nicht mehr in oberflaeche.md — "
        "wurde er umformuliert, gehört diese Prüfung mit ihm umgeschrieben"
    )
    genannt_mit = _ZAHLWORT.get(satz.group(1).lower())
    genannt_alle = _ZAHLWORT.get(satz.group(2).lower())
    assert genannt_mit is not None and genannt_alle is not None, (
        f"unbekanntes Zahlwort in oberflaeche.md: {satz.group(1)!r} von {satz.group(2)!r} — "
        f"in _ZAHLWORT eintragen"
    )

    load_operations()
    alle = REGISTRY.all()
    mit_caveat = [spec.name for spec in alle if spec.caveat]
    assert alle, "leeres Register — dann prüft dieser Test nichts"

    assert genannt_alle == len(alle), (
        f"oberflaeche.md nennt {genannt_alle} Operationen, das Register hat {len(alle)}"
    )
    assert genannt_mit == len(mit_caveat), (
        f"oberflaeche.md nennt {genannt_mit} mit caveat, gezählt sind {len(mit_caveat)} — "
        "den Satz im Abschnitt „Eine Grenze steht dort, wo gewählt wird“ nachziehen"
    )


def test_the_rule_files_count_the_operations_parameters_and_tools_they_claim() -> None:
    """Dieselbe Klammer wie darüber, um drei weitere Zahlen.

    Gemessen am 02.09.2026: `oberflaeche.md` nannte „457 Parameter der 86
    Operationen", `agentenschicht.md` „90 Operationen und elf
    Zusatzwerkzeuge" und „90 Operationen, 101 Werkzeuge". Das Register hatte
    95 Operationen mit 581 Parametern, der Agent 106 Werkzeuge — drei Sätze,
    zwei Dateien, alle plausibel und alle falsch. Wer eine Operation oder ein
    Werkzeug hinzufügt, zieht die Sätze nach oder bekommt einen roten Lauf.
    """
    from app.core.agent.tools import EXTRA_TOOLS
    from app.core.agent.tools import tool_schemas as agent_tool_schemas

    rules = Path(__file__).resolve().parent.parent / ".claude" / "rules"
    oberflaeche = (rules / "oberflaeche.md").read_text(encoding="utf-8")
    agentenschicht = (rules / "agentenschicht.md").read_text(encoding="utf-8")

    parameter = re.search(r"(\d+) Parameter der (\d+)\s+Operationen", oberflaeche)
    heute = re.search(
        r"heute sind es (\d+)\s+Operationen und\s+([a-zäöüß]+)\s+Zusatzwerkzeuge", agentenschicht
    )
    stand = re.search(
        r"Stand \d\d\.\d\d\.\d{4}: (\d+) Operationen, (\d+) Werkzeuge", agentenschicht
    )
    assert parameter, "der Satz „… Parameter der … Operationen“ steht nicht mehr in oberflaeche.md"
    assert heute, "der Satz „heute sind es … Operationen und … Zusatzwerkzeuge“ fehlt"
    assert stand, "die Zeile „Stand …: … Operationen, … Werkzeuge“ fehlt in agentenschicht.md"
    genannt_zusatz = _ZAHLWORT.get(heute.group(2).lower())
    assert genannt_zusatz is not None, (
        f"unbekanntes Zahlwort in agentenschicht.md: {heute.group(2)!r} — in _ZAHLWORT eintragen"
    )

    load_operations()
    alle = REGISTRY.all()
    assert alle, "leeres Register — dann prüft dieser Test nichts"
    parameter_gesamt = sum(len(spec.params.spec()) for spec in alle)
    werkzeuge = len(agent_tool_schemas())

    assert int(parameter.group(2)) == len(alle), (
        f"oberflaeche.md nennt {parameter.group(2)} Operationen, das Register hat {len(alle)}"
    )
    assert int(parameter.group(1)) == parameter_gesamt, (
        f"oberflaeche.md nennt {parameter.group(1)} Parameter, gezählt sind {parameter_gesamt}"
    )
    assert int(heute.group(1)) == len(alle), (
        f"agentenschicht.md nennt heute {heute.group(1)} Operationen, das Register hat {len(alle)}"
    )
    assert genannt_zusatz == len(EXTRA_TOOLS), (
        f"agentenschicht.md nennt {genannt_zusatz} Zusatzwerkzeuge, EXTRA_TOOLS hat "
        f"{len(EXTRA_TOOLS)}"
    )
    assert int(stand.group(1)) == len(alle), (
        f"der Stand in agentenschicht.md nennt {stand.group(1)} Operationen, es sind {len(alle)}"
    )
    assert int(stand.group(2)) == werkzeuge, (
        f"der Stand in agentenschicht.md nennt {stand.group(2)} Werkzeuge, tool_schemas() hat "
        f"{werkzeuge}"
    )


def test_a_variant_member_is_reached_through_its_group_not_through_an_entry_of_its_own() -> None:
    """Gesamtreview 05.09.2026, CORE-22: ``menu_path`` nannte für die
    Mitglieder einer Variantengruppe „Erzeugen → Grundform hochziehen" — einen
    Menüeintrag, den es nicht gibt. Die Leiste zeigt je Gruppe einen Eintrag,
    die Art wählt der Dialog; Handbuch und Werkzeugbeschreibungen schickten
    trotzdem an den Eintrag ohne Ort."""
    from app.core.registry import REGISTRY, VARIANT_GROUPS, menu_path

    load_operations()
    assert VARIANT_GROUPS, "ohne Gruppe prüft dieser Test nichts"
    for group in VARIANT_GROUPS:
        for member in group.members:
            spec = REGISTRY.get(member)
            path = menu_path(spec)
            assert f"→ {group.title}" in path, f"{member}: {path}"
            assert path.endswith(f"({group.choice}: {spec.title})"), f"{member}: {path}"
            assert f"→ {spec.title}" not in path, (
                f"{member}: der Weg nennt den Mitgliedstitel als Eintrag — den gibt es nicht"
            )
