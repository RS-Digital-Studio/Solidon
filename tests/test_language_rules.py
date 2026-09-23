"""Bezeichner bleiben englisch (Bauplan §4.1, AGENTS.md).

Ohne diese Prüfung wächst eine Mischung wie ``bausteinRegistry`` oder
``wall_staerke`` von selbst herein. Angesehen werden nur Bezeichner —
Zeichenketten tragen die deutschen Oberflächentexte und sollen deutsch sein.
"""

from __future__ import annotations

import ast
import itertools
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import app

PACKAGE_DIR = Path(app.__file__).parent
TOOLS_DIR = PACKAGE_DIR.parent / "tools"

#: Deutsche Wörter, die nie ein Abschnitt eines Bezeichners sein dürfen.
#:
#: Die Liste ist kuratiert und nicht vollständig — sie kann es nicht sein, denn
#: ein deutsches Wörterbuch träfe zu viel: `object`, `radius`, `position` und
#: `parameter` stehen wörtlich in den deutschen Oberflächentexten und sind
#: trotzdem englische Bezeichner. Was hier steht, ist eindeutig.
#:
#: **Hier steht auch, was als Stamm zu kurz ist.** ``masse``, ``spanne`` und
#: ``passt`` standen bis zum 26.08.2026 unter `GERMAN_STEMS` und wurden dort
#: als Teilzeichenkette gesucht — sie trafen damit ``masses``, ``spanned`` und
#: ``passthrough``, drei englische Wörter, die jederzeit in einem Bezeichner
#: stehen dürfen. Ein Falschmelder auf Vorrat: Der erste, der eines davon
#: schreibt, sucht den Fehler in seinem englischen Code. Als ganzes Wort
#: gesucht fangen sie weiter, was sie fangen sollen — ``masse_pro_teil`` ist
#: nach wie vor ein Verstoß.
GERMAN_WORDS = frozenset(
    {
        # Zwei Bezeichner aus der Notlage der Platzsuche in ``overlay.py``
        # (``platz``, ``unten``, vom 09.09. bis 21.09.2026); als ganzes Wort, denn
        # „unten" steckt in „untenable" und „platz" in keinem, das man
        # ausschließen müsste — der Stamm wäre trotzdem ein Falschmelder
        # auf Vorrat.
        "platz",
        "unten",
        "erwartet",
        "fehlend",
        "gelesen",
        "grenze",
        "lage",
        "treffer",
        "vergeben",
        "zeichen",
        "marke",
        "eigene",
        "vom",
        "genannt",
        "ordnung",
        "abstand",
        # Beide als ganzes Wort und nicht als Stamm: Als
        # Teilzeichenkette träfe "anker" die englischen "banker",
        # "tanker" und "flanker", "neu" träfe "neural" — dieselbe
        # Falle wie bei masse/spanne/passt. Gemessen am 30.08.2026,
        # als in bundling.py drei deutsche Namen standen und diese
        # Prüfung dazu schwieg.
        "anker",
        # "taste" ist zugleich das englische Verb (to taste, tasted): als
        # Stamm gesucht wäre es ein Falschmelder auf Vorrat, als ganzes Wort
        # fängt es, was es fangen soll. Anlass: In der Flugsteuerung des
        # Viewports standen am 03.09.2026 "taste", "achse" und "wert"
        # nebeneinander, und nur "wert" wurde gemeldet.
        "taste",
        "knopf",
        "metrik",
        "neu",
        "rahmen",
        "toleranz",
        "ecken",
        "lebende",
        "titel",
        "versteckt",
        "nach",
        "vorhanden",
        "anlass",
        "anzahl",
        "arten",
        "bauteil",
        "baustein",
        "beschreibung",
        "beschriftung",
        "breite",
        "datei",
        "dicke",
        "direkt",
        "durchmesser",
        "ebene",
        "einheit",
        "ende",
        "farbe",
        "fehler",
        "feld",
        "gleich",
        "hinweis",
        "kante",
        "koerper",
        "loch",
        "masse",
        "menge",
        "meldung",
        "minuten",
        "mutter",
        "objekt",
        "ordner",
        "passt",
        "pfad",
        "punkt",
        "schicht",
        "schraube",
        "schritt",
        "seite",
        "spalte",
        "spanne",
        "stelle",
        "stift",
        "stunde",
        "szene",
        "teil",
        "tiefe",
        "vorlage",
        "wand",
        "wert",
        "wurzel",
        "zahl",
        "zeile",
    }
)

#: Deutsche Stämme, die eindeutig genug sind, um innerhalb von Bezeichnern
#: gesucht zu werden.
#:
#: **Das ist eine Stichprobe und kein vollständiger Test — und das ist keine
#: Nachlässigkeit, sondern gemessen.** Am 23.08.2026 sind vier deutsche
#: Bezeichner in einer einzigen Sitzung durchgerutscht (``schuldige``,
#: ``letzter``, ``grund``, ``frei``), weil keiner davon auf dieser Liste stand.
#:
#: Der naheliegende Ausweg wurde probiert und ist gescheitert: die Liste aus
#: den **deutschen Kommentaren des Projekts** zu gewinnen. Sie lieferte 1319
#: Kandidaten und meldete 2758 angebliche Verstöße — darunter ``index``,
#: ``material``, ``parameter``, ``value``, ``export``, ``message``, ``scene``
#: und ``profile``. **Deutsch und Englisch überlappen bei technischen Wörtern
#: zu stark**, um sie ohne echtes Wörterbuch zu trennen, und ein Wörterbuch
#: wäre eine neue Abhängigkeit für einen Test.
#:
#: Also bleibt es bei der kuratierten Liste, und daraus folgt die Pflegeregel:
#: **Wer ein deutsches Wort in einem Bezeichner findet, trägt seinen Stamm
#: hier ein.** Der Test fängt, was schon einmal jemand falsch gemacht hat —
#: mehr verspricht er nicht, und weniger auch nicht.
#:
#: Und die Gegenfrage dazu, bevor ein Stamm hier landet: **Steckt er in einem
#: englischen Wort?** Dann gehört er nach `GERMAN_WORDS` und wird als ganzes
#: Wort gesucht — drei Einträge sind aus genau diesem Grund umgezogen (siehe
#: dort).
GERMAN_STEMS = (
    "knoten",
    "allein",
    "aenderung",
    "befehl",
    "begriff",
    "beispiel",
    "achse",
    "aussen",
    "auswahl",
    "bereit",
    "bohrung",
    "breit",
    "laeng",
    "dezimier",
    "druck",
    "durchmesser",
    "einstellung",
    "ergebnis",
    "fertig",
    "flaeche",
    "folge",
    "frei",
    "gefunden",
    "gemerkt",
    "geworden",
    "geschlossen",
    "geschoben",
    "geschrieben",
    "gespeichert",
    "gesperrt",
    "groesse",
    "grund",
    "halb",
    "haupt",
    "offen",
    "satz",
    "sauber",
    "stufe",
    "tipp",
    "umbruch",
    "umgebung",
    "vorher",
    "hoehe",
    "laenge",
    "lasche",
    "leiste",
    "letzt",
    "liefer",
    "loesch",
    "merkmal",
    "namen",
    "pruef",
    "quell",
    "reihe",
    "schluss",
    "schmal",
    "schuld",
    "schwelle",
    "sicht",
    "skizze",
    "sprach",
    "staerke",
    "stelle",
    "stueck",
    "verschmolzen",
    "versetz",
    "volumen",
    "waehl",
    "werkzeug",
    "zeile",
    "ziel",
    "zweig",
)

#: Deutsche Beugungen der Wörter oben. ``wert`` stand in der Liste und
#: ``werte`` kam trotzdem durch: geprüft wurde auf Gleichheit, und ein
#: deutscher Plural ist kein anderes Wort. Nur ``-e``, ``-en`` und ``-n`` —
#: ``-er`` und ``-s`` erzeugen aus ``wand`` und ``loch`` die englischen
#: ``wander`` und ``lochs``.
GERMAN_ENDINGS = ("e", "en", "n")
INFLECTED = frozenset(
    word + ending
    for word in GERMAN_WORDS
    for ending in GERMAN_ENDINGS
    if word + ending not in GERMAN_WORDS
)

UMLAUTS = "äöüÄÖÜß"


def source_files() -> list[Path]:
    """Die Dateien, gegen die die Sprachprüfung läuft.

    **Die Zusicherung steht hier und nicht in den Tests.** Vier Tests werden
    über diese Liste parametrisiert, und eine leere Parameterliste macht sie
    nicht rot — pytest sammelt dann schlicht **null Tests**, meldet
    ``no tests ran`` und gibt Exit 5. Ein Lauf, der nichts geprüft hat, sieht
    damit aus wie einer, der nichts gefunden hat.

    Eine Zusicherung *in* den Tests fängt das nicht: Sie liefe nie. Und eine je
    Datei wäre falsch — eine leere ``__init__.py`` hat legitim keine Bezeichner,
    was elf Fehlschläge gab, als es einmal so versucht wurde.
    """
    gefunden = sorted({*PACKAGE_DIR.rglob("*.py"), *TOOLS_DIR.glob("*.py")})
    assert len(gefunden) > 50, (
        f"nur {len(gefunden)} Quelldateien gefunden — stimmen {PACKAGE_DIR} "
        f"und {TOOLS_DIR} noch? Die Sprachprüfung hätte sonst nichts zu prüfen."
    )
    return gefunden


def identifiers_of(tree: ast.AST) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found.append((node.name, node.lineno))
        elif isinstance(node, ast.arg):
            found.append((node.arg, node.lineno))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            found.append((node.id, node.lineno))
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            found.append((node.attr, node.lineno))
        elif isinstance(node, ast.alias) and node.asname:
            found.append((node.asname, node.lineno))
    return found


def offences_in(name: str) -> list[str]:
    lowered = name.lower()
    hits = [word for word in lowered.split("_") if word in GERMAN_WORDS | INFLECTED]
    hits += [stem for stem in GERMAN_STEMS if stem in lowered]
    return hits


@pytest.mark.parametrize("path", source_files(), ids=lambda path: path.name)
def test_identifiers_are_english(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        f"{path.name}:{line} {name} -> {', '.join(hits)}"
        for name, line in identifiers_of(tree)
        if (hits := offences_in(name))
    ]
    assert not offenders, "\n".join(offenders)


@pytest.mark.parametrize("path", source_files(), ids=lambda path: path.name)
def test_identifiers_have_no_umlauts(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        f"{path.name}:{line} {name}"
        for name, line in identifiers_of(tree)
        if any(character in UMLAUTS for character in name)
    ]
    assert not offenders, "\n".join(offenders)


def test_module_names_are_english() -> None:
    offenders = [
        f"{path.name} -> {', '.join(hits)}"
        for path in source_files()
        if (hits := offences_in(path.stem))
    ]
    assert not offenders, "\n".join(offenders)


def test_the_check_would_catch_a_violation() -> None:
    """Ein Wächter, der laut scheitert, falls die Wortlisten je geleert werden."""
    assert offences_in("marke")
    assert offences_in("eigene")
    assert offences_in("vom_material")
    assert offences_in("genannt")
    assert offences_in("ordnung")
    assert offences_in("wall_staerke")
    assert offences_in("baustein_registry")
    assert offences_in("hoehe")
    assert offences_in("_knoten")
    assert not offences_in("detail_view")
    assert not offences_in("part_registry")
    # Der Nachtrag vom 25.08.2026: Ein Werkzeug unter ``tools/`` sprach
    # durchgehend deutsch, und keiner dieser Stämme stand auf der Liste.
    assert offences_in("zweig")
    assert offences_in("sauber")
    assert offences_in("liefere")
    assert offences_in("umgebung")
    assert offences_in("befehl")
    assert offences_in("fertig")
    assert offences_in("verschmolzen")
    assert offences_in("geschoben")
    assert offences_in("schluss")
    assert offences_in("haupt")
    # Und die Gegenprobe zu genau diesen: Was englisch ist, bleibt es.
    assert not offences_in("branch_name")
    assert not offences_in("clean_tree")
    assert not offences_in("command_line")
    assert not offences_in("main_branch")
    # Die drei Umzügler vom 26.08.2026 fangen als ganzes Wort weiter — und
    # gefragt wird nach ihnen selbst: In ``masse_pro_teil`` hätte auch ``teil``
    # gereicht, und die Zeile prüfte dann den Nachbarn statt den Umzügler.
    assert "masse" in offences_in("masse_der_platte")
    assert "spanne" in offences_in("spanne_der_platte")
    assert "passt" in offences_in("passt_das")


def test_the_check_sees_through_a_german_plural() -> None:
    """``wert`` stand in der Liste, ``werte`` kam durch — ein Jahr lang.

    Gesucht wurde auf Gleichheit, und der Plural ist damit ein anderes Wort.
    Die vier hier standen so im Bestand oder hätten es jederzeit gekonnt.
    """
    assert offences_in("werte")
    assert offences_in("schritte")
    assert offences_in("kanten")
    assert offences_in("objekte")


def test_the_check_leaves_english_words_alone() -> None:
    """Die Gegenprobe zur Beugung, und der Grund für die Wahl der Endungen.

    ``wand`` und ``loch`` stehen in der Liste; mit ``-er`` und ``-s`` daran
    entstünden ``wander`` und ``lochs``, und beide sind englisch. Deshalb
    kennt `GERMAN_ENDINGS` nur ``-e``, ``-en`` und ``-n``.

    Und dieselbe Frage eine Ebene höher: ``masse``, ``spanne`` und ``passt``
    stecken in ``masses``, ``spanned`` und ``passthrough``. Als Stamm gesucht
    meldeten sie diese drei englischen Wörter — deshalb stehen sie seit dem
    26.08.2026 unter `GERMAN_WORDS` und werden als ganzes Wort verglichen.
    """
    assert not offences_in("wander")
    assert not offences_in("wanders")
    assert not offences_in("lochs")
    assert not offences_in("ends")
    assert not offences_in("masses")
    assert not offences_in("spanned")
    assert not offences_in("passthrough")
    assert not offences_in("marker")
    assert not offences_in("marked")


#: Wörter, an denen eine Sprache zu erkennen ist, ohne den Satz zu verstehen.
#:
#: Funktionswörter und keine Fachbegriffe: „solid", „dots" oder „Encoding"
#: stehen in beiden Sprachen gleich da, „the" und „der" nicht.
GERMAN_MARKERS = frozenset(
    (
        "der",
        "die",
        "das",
        "und",
        "nicht",
        "ein",
        "eine",
        "ist",
        "dem",
        "den",
        "mit",
        "von",
        "auf",
        "für",
        "wird",
        "was",
        "wer",
        "sich",
        "nur",
        "nach",
        "aus",
        "als",
        "auch",
        "dann",
        "über",
        "kein",
        "keine",
        "sie",
        "es",
        "im",
        "zu",
        "bei",
        "noch",
        "wie",
        "damit",
        "ohne",
        "steht",
        "bleibt",
    )
)
ENGLISH_MARKERS = frozenset(
    (
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "from",
        "which",
        "when",
        "what",
        "are",
        "not",
        "but",
        "only",
        "any",
        "can",
        "cannot",
        "its",
        "their",
        "them",
        "would",
        "also",
        "shown",
        "print",
        "stays",
        "either",
    )
)


def field_docstrings(tree: ast.AST) -> list[tuple[int, str]]:
    """Die Docstrings, die hinter einem Feld stehen — mit Zeile.

    ``ast.get_docstring`` sieht sie nicht: Es kennt Modul, Klasse und Funktion,
    und ein Feld-Docstring ist syntaktisch nur ein Ausdruck, der auf eine
    Zuweisung folgt. Genau deshalb braucht es diese Funktion.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for before, after in itertools.pairwise(body):
            if not isinstance(before, ast.AnnAssign | ast.Assign):
                continue
            if not isinstance(after, ast.Expr):
                continue
            value = after.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                found.append((after.lineno, value.value))
    return found


def reads_as_english(text: str) -> bool:
    """Ob dieser Text eher englisch als deutsch ist.

    Gezählt, nicht geparst: zwei Sätze Funktionswörter, und die Mehrheit
    entscheidet. Zwei Treffer sind die Untergrenze, damit ein deutscher Satz
    mit einem zitierten ``for`` nicht umkippt. Gemessen am Bestand hat diese
    Schwelle 454 von 457 Feld-Docstrings richtig durchgelassen und die drei
    englischen gefunden.
    """
    words = {word.strip(".,;:()`*\"'").lower() for word in text.split()}
    english = len(words & ENGLISH_MARKERS)
    return english >= 2 and english > len(words & GERMAN_MARKERS)


@pytest.mark.parametrize("path", source_files(), ids=lambda path: path.name)
def test_field_docstrings_are_german(path: Path) -> None:
    """Auch der Satz hinter einem Feld ist Doku, und Doku ist deutsch.

    **Warum das eine eigene Prüfung braucht.** Die Sprachregelung trennt
    Bezeichner (englisch) von Docstrings (deutsch), und geprüft wurden bisher
    nur die Bezeichner. Für die Docstrings stand in `CLAUDE.md`, der Bestand
    sei „vollständig nachgezogen" — und für Modul, Klasse und Funktion stimmt
    das auch, nachgezählt am 21.08.2026: null englische unter allen.

    Drei sind trotzdem übrig geblieben, alle in derselben Nische: der Satz
    hinter einem Dataclass-Feld. ``ast.get_docstring`` sieht ihn nicht, also
    sah ihn keine Prüfung — zwei in ``palette.py`` (``pattern``, ``symbol``)
    und einer in ``settings.py`` (``display_unit``). Gefunden beim Durchgang
    durch den Viewport, beim Nachlesen, ob die Differenzansicht eine zweite
    Kodierung neben der Farbe führt (§19.1 — sie führt drei).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        f"{path.name}:{line} {text.splitlines()[0][:60]}"
        for line, text in field_docstrings(tree)
        if len(text) >= 25 and reads_as_english(text)
    ]
    assert not offenders, "englische Feld-Docstrings:" + chr(10) + chr(10).join(offenders)


def _imports_of(tree: ast.Module) -> list[tuple[int, str]]:
    """Die Importe auf Modulebene in Dateireihenfolge: (Zeile, Modulname)."""
    found: list[tuple[int, str]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            found.append((node.lineno, node.module))
    return found


def test_the_interface_loads_qt_types_before_the_first_window() -> None:
    """PySide legt seine Typen erst beim ersten Zugriff an — und das riss den
    Prozess, deterministisch, ``0xc0000374`` im ``gc.collect`` nach dem Abbau
    eines Fensters (``tests/test_filament_picker.py``).

    Zweimal bisektiert bis auf einen Import: am 14.09.2026 ein ungenutztes
    ``QMouseEvent`` in ``labels.py``, am 15.09.2026 ``QSpinBox`` in
    ``panels.py`` — derselbe Name über ``QtWidgets.QSpinBox`` gelesen war
    grün. Die Ursache ist nicht der Name, sondern **wann** PySide 6.11.2 den
    Typ anlegt; mit ``PYSIDE6_OPTION_LAZY=0`` laufen beide Stände durch. Die
    Variable wirkt nur, bevor ``PySide6`` zum ersten Mal geladen wird. Das
    Paket ``app.ui`` setzt sie beim Betreten; gehalten wird hier, dass es das
    tut, bevor PySide da ist, und dass ``app.py`` — als Skript gestartet, so
    ruft es das gebaute Paket — das Paket vor dem ersten PySide-Import lädt.
    Hier und nicht in einer Fensterdatei, weil der Wächter kein Fenster
    braucht und diese Datei vor jedem Commit an ``app/`` läuft
    (``.githooks/pre-commit``).
    """
    probe = (
        "import sys; before = 'PySide6' in sys.modules; import app.ui; import os; "
        "import PySide6.QtWidgets as widgets; "
        "print(before, os.environ.get('PYSIDE6_OPTION_LAZY'), "
        "all(name in vars(widgets) for name in ('QMdiArea', 'QWizard', 'QLCDNumber')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=PACKAGE_DIR.parent,
        env={key: value for key, value in os.environ.items() if key != "PYSIDE6_OPTION_LAZY"},
    )
    assert result.stdout.split() == ["False", "0", "True"], result.stdout

    source = PACKAGE_DIR / "ui" / "app.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    imports = _imports_of(tree)
    package = next((line for line, name in imports if name == "app.ui"), None)
    qt = next((line for line, name in imports if name.startswith("PySide6")), None)
    assert package is not None, "app.py lädt app.ui nicht auf Modulebene"
    assert qt is not None and package < qt, (
        f"app.ui (Zeile {package}) muss vor PySide6 (Zeile {qt}) stehen"
    )


#: Sätze, die mit Absicht duzen: Beschreibungen der Werkzeuge an das
#: Sprachmodell und Beispiele, die der Kunde selbst an den Agenten schreibt.
#: Beides spricht nicht den Kunden an. Wer hier etwas einträgt, hat einen
#: Satz, der ans Modell geht — alles andere siezt (AGENTS.md, Oberflächentexte).
_DU_ON_PURPOSE: frozenset[str] = frozenset(
    {
        "Lege ein Hauptmaß als Projektparameter an, statt es als Zahl zu setzen.",
        "Lege ein Passungspaar an. Die Toleranz kommt aus dem Materialprofil.",
        "Lies den Steckbrief der Szene neu — mit den Merkmalen und IDs, die deine "
        "bisherigen Schritte erzeugt haben.",
        "Lies den Prüfbericht, wahlweise nur ab einer Schwere.",
        "Lies eine Analyse: Druckbarkeit (Überhang, Inseln, Brücken), Zeit- und "
        "Materialschätzung, Einstellungsrat oder Orientierungssuche. Nur lesend, "
        "Herkunft wird ausgewiesen.",
        "Mach die Wandstärke 3 mm",
        "Nimm eine Transaktion aus dem Verlauf zurück.",
        "Sage das in deiner Antwort, bevor der Nutzer entscheidet.",
        "Skizzen zeichnet der Nutzer selbst — benutze die Grundformen und Maße.",
        "Suche einen passenden Baustein, bevor du Geometrie selbst zusammensetzt.",
        "Teile das Teil, damit es auf das Bett passt",
        "Ändere den Wert eines bestehenden Projektparameters.",
    }
)

#: Imperative der zweiten Person, wie sie in einem Oberflächensatz stehen
#: würden. ``Teile``, ``Stelle`` und ``Lege`` sind auch Nomen oder Konjunktive
#: — gesucht wird deshalb am Satzanfang und nach einem Gedankenstrich.
#: ``Suche`` fehlt mit Absicht: „Suche abgebrochen" ist ein Nomen, und ein
#: duzendes „suche" fängt die Prüfung auf ``du`` daneben.
_DU_VERBS = (
    "Ordne|Erzeuge|Wähle|Prüfe|Öffne|Lade|Setze|Entferne|Nimm|Gib|Versuche|Speichere|"
    "Ändere|Repariere|Verschiebe|Lege|Teile|Schließe|Starte|Installiere|Trage|Richte|"
    "Klicke|Ziehe|Drücke|Tippe|Sieh|Schau|Warte|Lass|Nutze|Benutze|Verwende|Füge|Stelle|"
    "Mach|Halte|Exportiere|Importiere|Wiederhole|Aktiviere|Deaktiviere|Lies|Sage"
)


def _noun_title(text: str) -> bool:
    """Ein Knopftitel wie „Stelle im Bild wählen" ist ein Nomen mit Infinitiv.

    „Stelle" und „Teile" sind Nomen und Befehlsform zugleich. Ein Titel ohne
    Satzzeichen, der mit dem Infinitiv endet, duzt niemanden; „Stelle den
    Schritt um." endet mit Punkt und bleibt ein Befund.
    """
    words = text.split()
    return (
        words[0] in {"Stelle", "Teile"}
        and not re.search(r"[.!?:;]", text)
        and re.fullmatch(r"\w+en", words[-1]) is not None
    )


def test_customer_texts_say_sie() -> None:
    """Die Oberfläche siezt — auch in einem Befund, der tief im Kern entsteht.

    Gefunden in der Durchsicht 0.5.0 an fünf Sätzen, die den Kunden duzten:
    „Ordne sie in den betroffenen Folgeschritten neu zu", „erzeuge sie im
    Ursprungsprogramm neu", „Öffne sie lokal …", „Stelle den Schritt …" und
    „Rückfrage an dich". Geprüft wird die deutsche Quelle jedes Katalogs,
    also jeder Satz, den der Kunde lesen kann.
    """
    import json
    import re

    catalog = json.loads((PACKAGE_DIR / "i18n" / "locales" / "en.json").read_text("utf-8"))
    assert len(catalog) > 1000, "der Katalog wurde nicht gelesen — die Prüfung sähe nichts"
    opening = re.compile(rf"(^|[.!?:;]\s+|\(\s*)({_DU_VERBS})\s+(?!Sie\b)\S")
    dashed = re.compile(rf"[—–]\s+({_DU_VERBS.lower()})\s+(sie|es|ihn|den|die|das)\b")
    pronoun = re.compile(r"\b(du|dich|dir|dein|deine|deinen|deinem|deiner)\b", re.IGNORECASE)
    offending = sorted(
        text
        for text in catalog
        if text not in _DU_ON_PURPOSE
        and (opening.search(text) or dashed.search(text) or pronoun.search(text))
        # ``Teile``, ``Stelle`` allein sind Nomen: Knopf- und Spaltentitel.
        and len(text.split()) > 2
        and not _noun_title(text)
    )
    assert not offending, f"Diese Sätze duzen den Kunden: {offending}"


def test_customer_texts_quote_no_internal_keys() -> None:
    """Ein Satz verweist nie auf einen Schlüssel, den der Kunde nicht sieht.

    „Wie weit, steht in „needed_mm"; was die Maschine kann, in „volume_mm""
    stand im Befund zu einem Muster, das über den Bauraum reicht (Durchsicht
    0.5.0), und fünf weitere Sätze bei Gitter, Zellmuster und Prägung
    verwiesen ebenso auf „nozzle_mm", „layer_mm" und „minimum_mm". Die
    Einzelheiten zeigen diese Werte als „Nötig", „Düse", „Schicht" — die
    Schlüssel selbst liest dort niemand.
    """
    import json
    import re

    catalog = json.loads((PACKAGE_DIR / "i18n" / "locales" / "en.json").read_text("utf-8"))
    # Wertschlüssel tragen ihre Einheit als Endung (``labels._VALUE_UNITS``).
    # Echte Datei- und Ordnernamen — „custom_nodes" bei ComfyUI — sind keine
    # und bleiben erlaubt: Die sucht der Kunde selbst.
    quoted_key = re.compile(
        r"[„“\"«]([a-z0-9]+(?:_[a-z0-9]+)*_(?:mm|mm2|mm3|cm3|deg|percent))[“”\"»]"
    )
    offending = sorted(text for text in catalog if quoted_key.search(text))
    assert not offending, f"Diese Sätze nennen interne Schlüssel: {offending}"
