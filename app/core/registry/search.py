"""Operationen nach Wörtern finden — für die Befehlspalette und den Agenten.

Zwei Leser stellen dieselbe Frage: Welche Operation meint jemand, der diese
Wörter schreibt? Die Befehlspalette (``app/ui/command_palette.py``) sortiert
danach ihre Zeilen, der lokale Agent (``agent/offer.py``) entscheidet damit,
welche Werkzeuge er mit allen Feldern sieht. Die Faltung, der Wortstamm und
die Kundenwörter stehen deshalb hier und nicht in der Oberfläche: Zwei
Tabellen über dieselben Wörter liefen auseinander, sobald jemand an einer
nachbessert (``.claude/rules/zwillinge.md``).

Kein Qt, keine Anzeige — was hier steht, rechnet nur.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Final

from app.core.registry.registry import Registry
from app.i18n import TranslatableText

#: Wie ein Umlaut auf einer Tastatur ohne Umlaute geschrieben wird.
#:
#: Beide Richtungen zählen, und deshalb wird auf **beiden** Seiten gefaltet:
#: Wer „aushoehlen" tippt, meint „Aushöhlen"; wer „Größe" tippt, soll auch das
#: finden, was im Register „groesse" heißt. Gefaltet wird nur der Vergleich —
#: angezeigt bleibt, was dasteht.
#:
#: **Nicht dasselbe wie ``i18n.sort_key``**, und das ist Absicht: Sortiert wird
#: nach DIN 5007-1, wo „ä" wie „a" zählt, damit „Ändern" zwischen „Analyse" und
#: „Anordnen" steht. Gesucht wird nach der Ersatzschreibweise der Tastatur, wo
#: „ä" zu „ae" wird. Eine Tabelle für beides täte einer von beiden Aufgaben
#: unrecht.
_FOLDED: Final[dict[str, str]] = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ß": "ss",
    "á": "a",
    "à": "a",
    "â": "a",
    "é": "e",
    "è": "e",
    "ê": "e",
    "í": "i",
    "ì": "i",
    "î": "i",
    "ó": "o",
    "ò": "o",
    "ô": "o",
    "ú": "u",
    "ù": "u",
    "û": "u",
    "ç": "c",
    "ñ": "n",
}


def fold(text: str) -> str:
    """Kleinschreibung, Umlaute ausgeschrieben, Akzente weg."""
    lowered = text.casefold()
    return "".join(_FOLDED.get(letter, letter) for letter in lowered)


#: Ab wie vielen Zeichen ein Wortstamm als Suchbegriff durchgeht.
#:
#: Vier, weil darunter jedes zweite Wort passt: „ver" fände Verrunden,
#: Vereinigen, Versetzen und Verstiften zugleich.
STEM_LENGTH: Final = 4

#: Wie viele Zeichen eine Beugung höchstens abschneiden darf.
#:
#: Die Untergrenze allein genügt nicht — sie war der Fehler. „gibtsnicht"
#: fand acht Einträge, weil die ersten vier Zeichen „gibt" in acht
#: Beschreibungen stehen; die Zeile „Kein Befehl passt zu …" kam nie zum
#: Vorschein. Ein Stamm ist ein *gekürztes* Wort, kein beliebiger Anfang:
#: „bohren" → „bohr" wirft zwei Zeichen weg, „skalieren" → „skalier" drei.
#: Darüber ist es ein anderes Wort.
STEM_CUT: Final = 3


def stem_of(word: str) -> str:
    """Der Suchstamm eines Wortes — kurz genug für die Beugung, lang genug
    für die Bedeutung.
    """
    return word[: max(STEM_LENGTH, len(word) - STEM_CUT)]


#: Wörter, die ein Kunde tippt, und die Operationen, die er damit meint.
#:
#: **Gemessen, nicht geraten.** Am 23.08.2026 wurden 42 Wörter durchprobiert,
#: wie sie jemand tippt, der noch nie in unserem Register gelesen hat —
#: Alltagswörter, Slicer-Wörter, und die aus anderen CAD-Programmen. Zehn
#: davon fanden **nichts**: nicht das Falsche, sondern gar nichts, und die
#: Palette antwortete „Kein Befehl passt".
#:
#: Eine Synonymtabelle deckt so etwas nie vollständig ab. Das ist kein Grund,
#: sie wegzulassen: Die Faltung und der Wortstamm tragen weit — „aushoehlen"
#: findet das Aushöhlen, „bohren" die Bohrung —, aber sie tragen nicht über die
#: Wortgrenze. „Fase anbringen" und „Kante brechen" haben keinen gemeinsamen
#: Buchstabenanfang, und keine Rechnung der Welt findet das eine über das
#: andere.
#:
#: **Nur wo das gemeinte Wort im Titel nicht vorkommt.** „Spiegeln" steht
#: nicht hier, weil die Operation so heißt; „bohren" auch nicht, weil der
#: Stamm es findet. Was hier steht, ist der Rest.
#:
#: Dieselbe Tabelle liest der lokale Agent (:func:`rank_operations`): Ein Kunde
#: schreibt im Chat dieselben Wörter, die er in die Palette tippt.
#: ``tests/test_theme_and_palette.py`` prüft, dass jedes Wort seine Operation
#: findet und dass jedes Ziel im Register existiert — ein Synonym, dessen
#: Operation umbenannt wurde, zeigt sonst stumm ins Leere.
SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    "fillet_edges": ("abrunden", "rundung", "radius"),
    "chamfer_edges": ("kante brechen", "abschraegen", "45 grad"),
    "pattern": ("array", "vervielfaeltigen", "wiederholen"),
    "split_pinned": ("zerschneiden", "halbieren", "durchschneiden"),
    "union_objects": ("zusammenfuegen", "verschmelzen", "verbinden"),
    "subtract_objects": ("ausschneiden", "aussparen", "wegnehmen"),
    "label_text": ("gravieren", "beschriften", "praegen"),
    "decimate_mesh": ("vereinfachen", "reduzieren", "leichter machen"),
    "hollow_object": ("aushoehlen", "leer machen", "exakt", "brep", "echte kanten"),
    # Versteckter Zwilling (``MENU_TWINS``): kein Menüeintrag, also ist die
    # Palette neben dem Verlauf sein einziger direkter Weg.
    "shell_exact": ("exakt aushoehlen", "brep aushoehlen"),
    # **„exakt" gehört an beide Hälften eines Paares**, seit die Grundliste den
    # Zwilling nicht mehr auflistet (``command_palette.matches``). Wer das Wort
    # tippt, will zwei Wege sehen: die Direktwahl des exakten Kerns **und** den
    # Eintrag, dessen Dialog den Haken trägt — und der ist meist der bessere,
    # weil er alle Felder zeigt. Ohne diese Zeilen fände er nur den ersten.
    #
    # „echte kanten" steht daneben, weil es das Wort ist, mit dem die
    # ``doc``-Sätze den Unterschied erklären, ohne „exakt" zu benutzen: „Legt
    # einen Quader mit echten Kanten an."
    # **Nur diese drei Wörter, keine Zugaben.** Der erste Anlauf hängte
    # „loch bohren" an ``drill_hole`` — und machte damit die Suche nach
    # „bohren" zu einem *genauen* Treffer. Daran hing ein fremder Test: Der
    # Wortstamm-Rückfall greift laut ``_refilter`` erst, wenn die genaue Suche
    # leer ausgeht, und „bohren" gegen „Bohrung setzen" war sein Prüffall. Ein
    # Synonym, das der Stamm ohnehin schon findet, bringt nichts und nimmt
    # einer Zusicherung ihren Fall.
    "create_box": ("exakt", "brep", "echte kanten"),
    "create_brep_box": ("exakt", "brep", "echte kanten"),
    "create_cylinder": ("exakt", "brep", "echte kanten"),
    "create_brep_cylinder": ("exakt", "brep", "echte kanten"),
    "create_cone": ("exakt", "brep", "echte kanten"),
    "create_brep_cone": ("exakt", "brep", "echte kanten"),
    "create_sphere": ("exakt", "brep", "echte kanten"),
    "create_brep_sphere": ("exakt", "brep", "echte kanten"),
    "create_torus": ("exakt", "brep", "echte kanten"),
    "create_brep_torus": ("exakt", "brep", "echte kanten"),
    "drill_hole": ("exakt", "brep", "echte kanten"),
    "drill_brep_hole": ("exakt", "brep", "echte kanten"),
    "repair_mesh": ("loecher schliessen", "reparieren", "flicken"),
    # **Die gewöhnlichsten Wörter fehlten**, und das fiel niemandem auf, weil
    # niemand sie sucht, der das Register kennt: „kopieren" und „loeschen"
    # führten ins Leere, obwohl es beides gibt. Gemessen an vierzig Wörtern,
    # mit denen ein Kunde suchen würde — sechs fanden nichts, und keines davon
    # war ein Fachbegriff.
    "duplicate_object": ("kopieren", "klonen", "zweites teil"),
    "delete_object": ("loeschen", "wegwerfen", "rauswerfen"),
    "load": ("oeffnen", "importieren", "stl", "datei"),
    # Beide heißen seit dem Filament-Umbau „färben" und stehen im Menü
    # nebeneinander; die Suchwörter trennen sie nach dem, was der Kunde
    # meint — das ganze Teil oder die eine Fläche. „Pinseln" und „anmalen"
    # sind geblieben: Wer sie tippt, sucht das, was der Pinsel einmal tat,
    # und findet jetzt die Füllung.
    "assign_slot": ("faerben", "einfaerben", "farbe zuweisen", "ganzes teil"),
    # **Ohne jedes „faerben", auch nicht in einem längeren Wort.** Seit der
    # Umbenennung tragen beide Titel das Wort („Filament zuweisen", „Filament auf eine
    # färben"), also entscheidet es nichts mehr — und als Synonym stand es
    # zusätzlich an beiden. Wer „färben" tippte, bekam die Fläche, weil bei
    # Gleichstand die Reihenfolge im Register zählt.
    #
    # Gestrichen wurde deshalb auch „flaeche einfaerben": Gesucht wird per
    # Teilzeichenkette, und darin **steckt** „faerben". Ein Synonym, das das
    # gesuchte Wort enthält, ohne es zu meinen, wirkt wie eines, das es meint.
    # Das Wort allein gehört dem Teil; die Fläche findet, wer „flaeche" tippt.
    "paint_slot": ("anmalen", "pinseln", "flaeche"),
    # Ein Logo ist ein Bild, und ein Bild wird hier zu einer Höhe. Beide Wörter
    # stehen im Kopf dessen, der es aufbringen will, und keines im Titel.
    "displace_image": ("logo", "foto", "bild aufbringen"),
}


def synonyms_for(name: str) -> str:
    """Die Kundenwörter dieser Operation, als ein Stück Suchtext.

    Gefaltet gespeichert und gefaltet gesucht — die Tabelle oben schreibt
    „aushoehlen" und nicht „aushöhlen", damit beide Schreibweisen denselben
    Weg nehmen.
    """
    return " ".join(SYNONYMS.get(name, ()))


# --- Rangfolge für eine Anfrage in Sätzen ------------------------------------------

#: Wie viel ein Treffer in welchem Teil einer Operation wiegt.
#:
#: Der Titel ist das, was der Kunde im Fenster liest, die Kundenwörter sind
#: eine bewusste Zuordnung — beide wiegen am schwersten. Der Name trägt die
#: englische Fassung („drill_hole"), der ``doc``-Satz alles, was die Operation
#: nebenbei erwähnt; er findet viel und entscheidet deshalb wenig.
_FIELD_WEIGHTS: Final = (("title", 3.0), ("name", 2.0), ("doc", 1.0))

#: Was ein Kundenwort aus :data:`SYNONYMS` wiegt, wenn die Anfrage es ganz
#: enthält. **Als Wendung, nicht Wort für Wort:** „leichter machen" meint das
#: Verringern der Dreiecke nur, wenn beide Wörter dastehen — Wort für Wort
#: gezählt machte jedes „mach" aus einer Anfrage einen Treffer dort.
_SYNONYM_SCORE: Final = 6.0

#: Ein Treffer über den Wortstamm statt über das ganze Wort zählt weniger —
#: „bohren" gegen „Bohrung" ist dieselbe Sache, „mitte" gegen „Mitteln" nicht.
_STEM_SHARE: Final = 0.6

#: Kürzere Wörter tragen keine Bedeutung, die ein Titel verrät: „M4", „in", „zu".
_SHORTEST_TERM: Final = 3

_WORDS: Final = re.compile(r"[^\W\d_]+")


def request_terms(text: str) -> tuple[str, ...]:
    """Die Wörter einer Anfrage, gefaltet und ohne Zahlen, jedes einmal."""
    seen: dict[str, None] = {}
    for word in _WORDS.findall(fold(text)):
        if len(word) >= _SHORTEST_TERM:
            seen.setdefault(word, None)
    return tuple(seen)


def _texts_of(value: object) -> str:
    """Anzeige **und** Quelle eines übersetzbaren Texts.

    Wer auf Englisch arbeitet und auf Deutsch schreibt, meint dieselbe
    Operation; die deutsche Quelle steht deshalb neben der Übersetzung.
    """
    shown = str(value)
    if isinstance(value, TranslatableText) and value.msgid != shown:
        return f"{shown} {value.msgid}"
    return shown


def _fields_of(registry: Registry) -> dict[str, dict[str, str]]:
    """Je Operation die gefalteten Suchtexte, nach Feld getrennt."""
    return {
        spec.name: {
            "title": fold(_texts_of(spec.title)),
            "name": fold(spec.name.replace("_", " ")),
            # Der erste Satz sagt, was die Operation tut; der Rest erklärt
            # Randfälle und nennt dabei fast jedes Wort des Fachs.
            "doc": fold(str(spec.doc).split(". ")[0]),
            # Gezählt wird die Seltenheit am ganzen Text: In einem ersten Satz
            # ist „das" selten, im ganzen ``doc`` steht es fast überall — und
            # genau daran erkennt die Rechnung ein Füllwort.
            "all": fold(f"{_texts_of(spec.title)} {spec.name.replace('_', ' ')} {spec.doc}"),
        }
        for spec in registry.all()
    }


#: Ab welcher Länge ein Wort auch **mitten** in einem Wort des Registers
#: zählt — und wie viel. Deutsche Titel sind Zusammensetzungen: „Magnettasche",
#: „Schraubenloch". Wer „tasche" schreibt, meint sie mit; wer „teil" schreibt,
#: meint nicht „Einzelteile" und nicht „verteilt". Fünf Buchstaben trennen das
#: gemessen an den Referenzanfragen der Suite: Vier ließen „teil", „mach" und
#: „loch" in jeden zweiten ``doc``-Satz fallen.
_INNER_LENGTH: Final = 5
_INNER_SHARE: Final = 0.3


def _starts_a_word(part: str, text: str) -> bool:
    """Ob ``part`` in ``text`` am Anfang eines Worts steht."""
    start = text.find(part)
    while start != -1:
        if start == 0 or not text[start - 1].isalpha():
            return True
        start = text.find(part, start + 1)
    return False


def _strength(term: str, text: str) -> float:
    """Wie gut ein Wort der Anfrage einen Suchtext trifft, zwischen 0 und 1.

    Am Wortanfang zählt das ganze Wort voll und sein Stamm zu
    :data:`_STEM_SHARE`; mitten im Wort nur ein langes Wort, und nur zu
    :data:`_INNER_SHARE`.
    """
    if len(term) < STEM_LENGTH:
        # Drei Buchstaben sind ein Wort oder nichts: „pla" meint das Material,
        # nicht „place", und „box" nicht „boxed".
        return 1.0 if term in text.split() else 0.0
    stem = stem_of(term)
    if _starts_a_word(term, text):
        return 1.0
    if stem != term and _starts_a_word(stem, text):
        return _STEM_SHARE
    if len(term) >= _INNER_LENGTH and stem in text:
        return _INNER_SHARE
    return 0.0


def _says(phrase: str, terms: list[str]) -> bool:
    """Ob die Anfrage jedes Wort dieser Wendung enthält, ganz oder am Stamm."""
    return all(
        any(_strength(term, word) >= _STEM_SHARE for term in terms) for word in phrase.split()
    )


def rank_operations(
    texts: Iterable[str], registry: Registry, *, favoured: Iterable[str] = ()
) -> tuple[tuple[str, float], ...]:
    """Welche Operationen diese Sätze meinen — die beste zuerst.

    Anders als die Palette sucht hier niemand nach einem Namen, sondern
    beschreibt, was er will: „Bohr ein Loch mit 5 mm Durchmesser in die
    Oberseite". Jedes Wort zählt deshalb nach seiner **Seltenheit** im
    Register: „bohr" trifft zwei Titel und entscheidet, „mit" und „die" stehen
    in fast jedem ``doc``-Satz und wiegen nichts. Eine Liste von Füllwörtern
    je Sprache braucht es damit nicht — wer in sechs Sprachen schreibt,
    bekommt dieselbe Rechnung.

    ``favoured`` hebt Operationen, die zur Auswahl passen (``applies_to``), um
    einen festen Betrag: Wer eine Bohrung gewählt hat und „größer" schreibt,
    meint die Handlungen an der Bohrung. Zurück kommt jede Operation mit
    Wertung über null, bei Gleichstand in der Reihenfolge des Registers.
    """
    terms: list[str] = []
    for text in texts:
        for term in request_terms(text):
            if term not in terms:
                terms.append(term)
    fields = _fields_of(registry)
    total = len(fields)
    wanted = set(favoured)
    if not total:
        return ()
    scores = dict.fromkeys(fields, 0.0)
    for term in terms:
        hits: dict[str, float] = {}
        for name, texts_of_op in fields.items():
            best = max(
                weight * _strength(term, texts_of_op[field]) for field, weight in _FIELD_WEIGHTS
            )
            if best:
                hits[name] = best
        spread = sum(1 for texts_of_op in fields.values() if _strength(term, texts_of_op["all"]))
        # **Ein Wort, das in jeder sechsten Operation steht, entscheidet
        # nichts** — „das", „die", „mit", „auf". Gezählt statt aufgelistet:
        # eine Liste von Füllwörtern bräuchte es je Sprache, die Zählung nicht.
        if not hits or spread > total * COMMON_SHARE:
            continue
        # Die Seltenheit wie in der Textsuche üblich, geglättet: ein Wort in
        # einer Operation wiegt rund 4,5, eines in allen fast nichts.
        rarity = math.log((total + 1) / (spread + 0.5))
        for name, weight in hits.items():
            scores[name] += rarity * weight
    for name in scores:
        if any(_says(phrase, terms) for phrase in SYNONYMS.get(name, ())):
            scores[name] += _SYNONYM_SCORE
    for name in wanted:
        if name in scores:
            scores[name] += FAVOURED_BONUS
    order = {name: index for index, name in enumerate(fields)}
    ranked = sorted(
        ((name, score) for name, score in scores.items() if score > 0.0),
        key=lambda entry: (-entry[1], order[entry[0]]),
    )
    return tuple(ranked)


#: Ab welchem Anteil der Operationen ein Wort als Füllwort gilt und nicht
#: zählt. Gemessen an den Referenzanfragen der Suite: „das" trifft 40 der 153
#: Titel und ersten Sätze, „loch" 11, „bohr" 9.
COMMON_SHARE: Final = 1 / 6

#: Was eine Operation gewinnt, die zur gewählten Stelle passt. So groß wie
#: ein Titeltreffer eines mittelseltenen Worts: Die Auswahl entscheidet
#: zwischen gleich guten Treffern, sie überstimmt keinen klaren.
FAVOURED_BONUS: Final = 3.0
