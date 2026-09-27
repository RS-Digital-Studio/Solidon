"""Die Suche im Handbuch (Konzept Handbuch §7).

Die Suche des Handbuchfensters fand Zeichenfolgen und ordnete nicht. Gemessen
an 38 Kundensuchen stand die richtige Seite bei der Hälfte nicht unter den
ersten drei, vier fanden gar nichts, weil das Handbuch ein anderes Wort
benutzt, und nach dem Treffer begann die Seite oben, auch wenn das Wort
fünftausend Wörter tiefer stand
(``konzepte/nachweise-handbuch-2026-09/findbarkeit.md``).

Jetzt zählt, **wo** ein Wort steht — im Titel mehr als in der Kurzfassung,
dort mehr als in einer Überschrift, dort mehr als im Fließtext — und **wie
genau** es passt. Jeder Treffer nennt die Stelle, an der die Seite aufschlägt.

**Was als Treffer zählt, entscheidet dieselbe Rechnung wie in der
Befehlspalette** (``app/core/registry/search.py``): dieselbe Faltung
(„aushoehlen" findet *Aushöhlen*), derselbe Wortstamm, dieselben
Kundenwörter. Wer in der Palette „abrunden" tippt, bekommt *Verrunden*; im
Handbuch führt dasselbe Wort auf die Seiten, die *Verrunden* erklären. Eine
zweite Tabelle für dieselben Wörter liefe auseinander, sobald jemand eine
davon nachbessert (``.claude/rules/zwillinge.md``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from app.core.manual import FIGURE_PATTERN, Page, Part, pages
from app.core.registry.registry import REGISTRY, Registry
from app.core.registry.search import customer_phrases, fold, request_terms, says, strength

#: Was ein Treffer an welcher Stelle wert ist, gerechnet für ein Wort, das
#: am Wortanfang passt (:func:`strength` gleich eins). Titel, Kurzfassung und
#: Stichwörter zählen einmal mit ihrem besten Treffer; der Text zählt jeden,
#: aber nur bis zu einer Grenze — sonst gewönne die längste Seite, und das
#: sind die Referenzseiten mit ihren tausenden Wörtern.
_TITLE_WEIGHT: Final = 60.0
_SUMMARY_WEIGHT: Final = 24.0
_MARKED_WEIGHT: Final = 18.0
_BODY_WEIGHT: Final = 4.0
_BODY_LIMIT: Final = 24.0

#: Das ganze Wort zählt die Hälfte mehr als ein Wort, das nur so anfängt. Die
#: Palette unterscheidet das nicht, sie ordnet Titel aus zwei, drei Wörtern;
#: auf einer Seite aus tausenden trennt es *hohl* von *Hohlkehle* und *Text*
#: von *Textur*. Gemessen an den Kundensuchen: mit einem Viertel landete
#: „hohl" bei der Hohlkehle, mit dem Ganzen fiel „Stütze" auf Rang drei.
_WHOLE_WORD: Final = 0.5

#: Stehen mehrere Suchwörter nebeneinander, zählt das extra, und die Seite
#: schlägt dort auf. Ein Stück mitten in einem Wort zählt dafür nicht.
_PHRASE_BONUS: Final = 20.0
_PHRASE_STRENGTH: Final = 0.5

#: Ein Vorsprung für die Teile, in denen ein Kunde zuerst nachsehen soll: Wer
#: „Loch" sucht, will zuerst die Anleitung sehen, dann die Referenz.
_PART_WEIGHT: Final[dict[Part, float]] = {
    "start": 20.0,
    "tasks": 20.0,
    "topics": 10.0,
    "help": 10.0,
    "reference": 0.0,
}

#: Die Seite für Programme, die Solidon fernsteuern. Sie wiederholt jede
#: Operationsbeschreibung und stand deshalb bei 30 von 38 Kundensuchen unter
#: den Treffern — gesucht hat dort keiner. Sie bleibt auffindbar, nur hinten.
_BACKGROUND_PAGES: Final = frozenset({"remote-tools"})
_BACKGROUND_SHARE: Final = 4.0

#: Wie viele Suchwörter sich ein Index mit ihren Treffern merkt. Beim Tippen
#: entsteht je Buchstabe ein neues; mehr als ein paar hundert braucht niemand.
_REMEMBERED: Final = 256

_TOKEN: Final = re.compile(r"\w+")
_MARKUP: Final = re.compile(r"[*`]")
_BREAK: Final = re.compile(r"\s*\n\s*")
_HEADING: Final = re.compile(r"^#+\s*(.+)$", re.MULTILINE)
_BOLD: Final = re.compile(r"\*\*(.+?)\*\*")


@dataclass(frozen=True, slots=True)
class Found:
    """Eine Seite, die zur Suche passt, und die Stelle, an der sie aufschlägt."""

    page: Page
    spot: str
    """Das Wort oder die Wortfolge, wie sie im Text steht — leer, wenn der
    Titel am besten passt und die Seite oben beginnen soll."""


@dataclass(frozen=True, slots=True)
class _Token:
    folded: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _Field:
    """Ein Stück Seite — Titel, Stichwörter, Kurzfassung oder Text — in Wörtern.

    ``first`` kennt jedes Wort mit seinem ersten Auftreten, ``counts`` weiß,
    wie oft es dasteht: Bewertet wird jedes Wort einmal, nicht jedes Vorkommen.
    """

    text: str
    tokens: tuple[_Token, ...]
    counts: dict[str, int]
    first: dict[str, _Token]


def _field(text: str) -> _Field:
    tokens = tuple(
        _Token(fold(match.group()), match.start(), match.end()) for match in _TOKEN.finditer(text)
    )
    counts: dict[str, int] = {}
    first: dict[str, _Token] = {}
    for token in tokens:
        counts[token.folded] = counts.get(token.folded, 0) + 1
        first.setdefault(token.folded, token)
    return _Field(text, tokens, counts, first)


def _marked(body: str, title: str) -> str:
    """Überschriften und fett gesetzte Stichwörter einer Seite.

    Daran erkennt man, dass eine Seite eine Sache erklärt und sie nicht nur
    nennt: Die Referenz setzt jede Operation als Überschrift, die
    geschriebenen Seiten beginnen ihre Absätze mit dem Stichwort in Fett. Wer
    „Spiegeln" sucht, meint den Abschnitt *Spiegeln* und nicht den Satz, in
    dem eine Skizze gespiegelt wird. Die Überschrift, die nur den Titel der
    Seite wiederholt, zählt hier nicht noch einmal.
    """
    headings = [heading for heading in _HEADING.findall(body) if heading.strip() != title]
    return "\n".join([*headings, *_BOLD.findall(body)])


def _words(text: str) -> tuple[str, ...]:
    """Die Wörter einer Suche, gefaltet wie die Seiten, jedes einmal.

    Anders als die Palette (``request_terms``) behält das Handbuch Zahlen und
    kurze Wörter: Wer „3MF" oder „M3" sucht, meint genau das, und auf einer
    Seite steht es so da.
    """
    return tuple(dict.fromkeys(match.group() for match in _TOKEN.finditer(fold(text))))


def _measure(values: dict[str, float], field: _Field) -> tuple[float, _Token | None, float]:
    """Der beste Treffer eines Suchworts in einem Feld — bei Gleichstand der
    erste — und alle Treffer zusammen."""
    best, found, total = 0.0, None, 0.0
    for folded, value in values.items():
        token = field.first.get(folded)
        if token is None:
            continue
        total += value * field.counts[folded]
        if value > best or (value == best and found is not None and token.start < found.start):
            best, found = value, token
    return best, found, total


@dataclass(frozen=True, slots=True)
class _Entry:
    page: Page
    order: int
    title: _Field
    marked: _Field
    summary: _Field
    body: _Field


class SearchIndex:
    """Die Seiten des Handbuchs, einmal in Wörter zerlegt.

    Das Fenster sucht bei jedem Tastendruck; zerlegt wird deshalb einmal und
    nicht bei jedem Buchstaben, und wie gut ein Suchwort jedes Wort des
    Handbuchs trifft, wird je Suchwort einmal gerechnet. Die Wörter entstehen
    in der Sprache, die beim Bau eingestellt ist, wie die Seiten selbst.
    """

    def __init__(
        self,
        source: tuple[Page, ...] | list[Page] | None = None,
        registry: Registry | None = None,
    ) -> None:
        self._registry = registry or REGISTRY
        entries = []
        vocabulary: set[str] = set()
        for order, page in enumerate(pages(registry) if source is None else source):
            title = str(page.title)
            body = FIGURE_PATTERN.sub(" ", str(page.body))
            entry = _Entry(
                page=page,
                order=order,
                title=_field(title),
                marked=_field(_marked(body, title)),
                summary=_field(str(page.summary)),
                body=_field(body),
            )
            for field in (entry.title, entry.summary, entry.body):
                vocabulary.update(field.counts)
            entries.append(entry)
        self._entries = tuple(entries)
        self._vocabulary = frozenset(vocabulary)
        self._values: dict[str, dict[str, float]] = {}

    def search(self, needle: str) -> list[Found]:
        """Die Seiten zu einer Suche, die passendste zuerst.

        Ohne Suchwort kommen alle Seiten in ihrer Reihenfolge und schlagen oben
        auf. Mehrere Wörter finden die Seiten, auf denen jedes vorkommt, und
        die, auf denen sie nebeneinander stehen, zuerst.
        """
        words = _words(needle)
        if not words:
            return [Found(entry.page, "") for entry in self._entries]
        # Was der Kunde getippt hat, und die Titel der Operationen, die er mit
        # einem Kundenwort meint. Eine Seite zählt mit der besseren Antwort.
        variants = [(words, False)]
        variants.extend((meant, True) for meant in self._meant(needle) if meant != words)
        ranked: list[tuple[float, int, Found]] = []
        for entry in self._entries:
            best: tuple[float, str] | None = None
            for variant, exact in variants:
                scored = self._score(variant, entry, exact=exact)
                if scored is None:
                    continue
                # Je Wort verglichen: Ein Titel aus zwei Wörtern sammelte sonst
                # doppelt und schlüge das eine Wort, das der Kunde getippt hat.
                value = scored[0] / len(variant)
                if best is None or value > best[0]:
                    best = (value, scored[1])
            if best is None:
                continue
            score = best[0] + _PART_WEIGHT[entry.page.part]
            if entry.page.key in _BACKGROUND_PAGES:
                score /= _BACKGROUND_SHARE
            ranked.append((-score, entry.order, Found(entry.page, best[1])))
        ranked.sort(key=lambda item: item[:2])
        return [item[2] for item in ranked]

    def _meant(self, needle: str) -> list[tuple[str, ...]]:
        """Die Titel der Operationen, die diese Suche über ein Kundenwort meint.

        Gezählt wird ein Kundenwort nur, wenn die Suche genau diese Wendung ist
        — kein Wort fehlt, keines kommt dazu. Wer „aumentar temperatura" sucht,
        meint die Temperatur und nicht *Skalieren*, obwohl „aumentar" allein
        dorthin führt; solche Suchen findet der Text selbst.
        """
        terms = list(request_terms(needle))
        if not terms:
            return []
        meant: list[tuple[str, ...]] = []
        for spec in self._registry.all():
            for phrase in customer_phrases(spec.name):
                if says(phrase, terms) and says(" ".join(terms), list(request_terms(phrase))):
                    title = _words(str(spec.title))
                    if title and title not in meant:
                        meant.append(title)
                    break
        return meant

    def _strengths(self, word: str, *, exact: bool = False) -> dict[str, float]:
        """Wie gut ein Suchwort die Wörter des Handbuchs trifft — nur die Treffer.

        Die Stärke rechnet die Palette (:func:`strength`); das ganze Wort
        bekommt :data:`_WHOLE_WORD` dazu. ``exact`` zählt nur das ganze Wort:
        So wird der Titel einer Operation gesucht, zu der ein Kundenwort
        führt. Das Handbuch schreibt ihn genau so, und *Text aufbringen* soll
        nicht *Textur aufbringen* finden.
        """
        if exact:
            return {word: 1.0 + _WHOLE_WORD} if word in self._vocabulary else {}
        known = self._values.get(word)
        if known is None:
            if len(self._values) >= _REMEMBERED:
                self._values.clear()
            known = {}
            for token in self._vocabulary:
                value = strength(word, token)
                if value:
                    known[token] = value + _WHOLE_WORD if token == word else value
            self._values[word] = known
        return known

    def _score(
        self, words: tuple[str, ...], entry: _Entry, *, exact: bool = False
    ) -> tuple[float, str] | None:
        """Wie gut eine Seite passt und wo sie aufschlägt; ``None``, wenn gar nicht.

        Jedes Wort muss irgendwo auf der Seite stehen. Stehen sie nebeneinander,
        zählt das extra, und die Seite schlägt an dieser Stelle auf.
        """
        score = 0.0
        in_title_best = 0.0
        spot_value = 0.0
        spot: tuple[_Field, int, int] | None = None
        for word in words:
            values = self._strengths(word, exact=exact)
            in_title = _measure(values, entry.title)[0]
            in_marked = _measure(values, entry.marked)[0]
            in_summary, summary_token, _summary_total = _measure(values, entry.summary)
            in_body, body_token, body_total = _measure(values, entry.body)
            if not (in_title or in_summary or in_body):
                return None
            in_title_best = max(in_title_best, in_title)
            score += in_title * _TITLE_WEIGHT + in_summary * _SUMMARY_WEIGHT
            score += in_marked * _MARKED_WEIGHT + min(body_total * _BODY_WEIGHT, _BODY_LIMIT)
            for value, token, field in (
                (in_summary, summary_token, entry.summary),
                (in_body, body_token, entry.body),
            ):
                if token is not None and value > spot_value:
                    spot_value, spot = value, (field, token.start, token.end)
        if len(words) > 1:
            for field in (entry.title, entry.summary, entry.body):
                span = self._phrase(words, field, exact=exact)
                if span is not None:
                    score += _PHRASE_BONUS
                    if field is not entry.title:
                        spot_value, spot = float("inf"), (field, *span)
                    break
            else:
                # Der Titel einer Operation ist ein Name: „Insert model" steht
                # als Folge da oder gar nicht, sonst träfe er jede Seite mit
                # „model" im Titel und „insert" irgendwo im Text.
                if exact:
                    return None
        if spot is None or in_title_best >= spot_value:
            return score, ""
        field, start, end = spot
        # So, wie das Fenster den Text zeigt: ohne Auszeichnung, und ein
        # Zeilenumbruch im Quelltext ist dort ein Leerzeichen.
        return score, _BREAK.sub(" ", _MARKUP.sub("", field.text[start:end]))

    def _phrase(
        self, words: tuple[str, ...], field: _Field, *, exact: bool = False
    ) -> tuple[int, int] | None:
        """Wo die Wörter der Suche nebeneinander stehen: Anfang und Ende im Text."""
        values = [self._strengths(word, exact=exact) for word in words]
        tokens = field.tokens
        size = len(words)
        for index in range(len(tokens) - size + 1):
            if all(
                values[offset].get(tokens[index + offset].folded, 0.0) >= _PHRASE_STRENGTH
                for offset in range(size)
            ):
                return tokens[index].start, tokens[index + size - 1].end
        return None


def search(
    needle: str,
    source: tuple[Page, ...] | list[Page] | None = None,
    registry: Registry | None = None,
) -> list[Found]:
    """Einmal suchen, ohne einen Index aufzuheben — für Tests und Werkzeuge."""
    return SearchIndex(source, registry).search(needle)
