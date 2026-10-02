"""Markdown zu HTML — nur die Teilmenge, die das Handbuch benutzt.

Ein vollständiger Markdown-Übersetzer wäre hier eine Abhängigkeit für ein
Problem, das es nicht gibt: das Markdown, das umgewandelt wird, ist selbst
erzeugt (:mod:`app.core.manual`, :func:`app.core.registry.documentation`).
Damit ist die Menge dessen, was vorkommen kann, bekannt und geschlossen —
Überschriften, Absätze, Aufzählungen, Tabellen, Fettdruck, Kursives, Code,
Bildverweise und Verweise auf andere Seiten des Handbuchs.

Der Grund, es überhaupt selbst zu tun: Qt kann Markdown, aber Qt gehört nicht
in den Kern. So lässt sich das Handbuch auch dort als Seite ausgeben, wo kein
Fenster existiert — auf einem Bauserver, in der Kommandozeile, in einem Test.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from html import escape
from typing import Final, NamedTuple

#: Was in einer Zeile ausgezeichnet werden kann. Reihenfolge zählt: Code
#: zuerst, damit ein Sternchen in einem Codeschnipsel keins bleibt.
_CODE: Final = re.compile(r"`([^`]+)`")
_STRONG: Final = re.compile(r"\*\*([^*]+)\*\*")
_EMPHASIS: Final = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_HEADING: Final = re.compile(r"^(#{1,6})\s+(.*)$")
_SETEXT: Final = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_FENCE: Final = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_BULLET: Final = re.compile(r"^[*-]\s+(.*)$")
"""Beide Markdown-Schreibweisen: Die geschriebenen Kapitel nutzen ``* ``,
die erzeugten Referenzlisten ``- `` — wer nur eine kennt, klebt die andere
zu einem Fließtextabsatz zusammen, und aus zwanzig Operationen wird ein
Klumpen."""
_NUMBERED: Final = re.compile(r"^(\d+)\.\s+(.*)$")
"""Eine nummerierte Liste. Das Handbuchfenster kannte sie immer, denn es liest
Qts Markdown; hier fehlte sie, und die drei Schritte der Seite über zusätzliche
Programme klebten auf der Website zu einem Absatz zusammen. Die Legenden der
Bildanleitungen brauchen sie: Ihre Nummern sind die Nummern im Bild."""
_FIGURE: Final = re.compile(r"^!\[\]\(figure:([a-z0-9-]+)\)$")
_ROW: Final = re.compile(r"^\|(.+)\|$")
_SEPARATOR: Final = re.compile(r"^\|[\s:|-]+\|$")

MANUAL_LINK: Final = re.compile(r"\[([^\]\n]+)\]\(manual:([a-z0-9-]+)\)")
"""Ein Verweis auf eine andere Seite: ``[Ein Loch bohren](manual:drill-a-hole)``.

Die einzige Art Verweis, die das Handbuch kennt. Das Ziel ist der Schlüssel
einer Seite, und wohin er führt, entscheidet, wer ausgibt: Das Fenster schlägt
die Seite auf, Website und PDF springen zu ihrem Anker, die Textausgabe und die
Suche behalten nur den Text (:func:`unlinked`). Ein Schlüssel statt einer
Adresse, weil eine Seite in drei Ausgaben drei verschiedene Adressen hat."""

#: Wohin ein Seitenverweis führt: der Schlüssel hinein, eine Adresse heraus —
#: oder ``None``, dann bleibt der Text ohne Verweis stehen.
LinkResolver = Callable[[str], str | None]


class FigureSource(NamedTuple):
    """Was aus einem Bildverweis wird.

    ``dark`` ist die Quelle für ein dunkles Farbschema und darf leer bleiben.
    Gezeichnete Abbildungen entstehen in beiden Versionen — eine Zeichnung mit
    weißem Grund stand sonst als greller Block in einer dunklen Seite, während
    der Text um sie herum dem System folgte. Bildschirmfotos haben keine zweite
    Version: sie zeigen die Anwendung, wie sie eingestellt ist.
    """

    source: str
    alt: str
    caption: str
    dark: str = ""


#: Was aus einem Bildverweis wird: die Quelle, der Alt-Text, die Unterschrift —
#: als Tupel oder als :class:`FigureSource`, das zusätzlich die dunkle Version
#: kennt.
FigureResolver = Callable[[str], FigureSource | tuple[str, str, str] | None]


def inline(text: str, link: LinkResolver | None = None) -> str:
    """Fettdruck, Kursives, Code und Seitenverweise einer Zeile — der Rest wird maskiert.

    ``link`` sagt, wohin ein Seitenverweis führt. Ohne die Funktion, oder wenn
    sie für einen Schlüssel nichts weiß, bleibt sein Text stehen: Ein Verweis
    ins Leere wäre schlechter als keiner.
    """
    pieces: list[str] = []

    def stash(html: str) -> str:
        pieces.append(html)
        return f"\x00{len(pieces) - 1}\x00"

    def keep_link(match: re.Match[str]) -> str:
        label = _emphasised(escape(match.group(1)))
        target = link(match.group(2)) if link else None
        if not target:
            return stash(label)
        return stash(f'<a href="{escape(target, quote=True)}">{label}</a>')

    stashed = _CODE.sub(lambda match: stash(f"<code>{escape(match.group(1))}</code>"), text)
    stashed = MANUAL_LINK.sub(keep_link, stashed)
    result = _emphasised(escape(stashed))
    # Rückwärts, weil ein Verweis einen Codeschnipsel tragen kann: Sein Platzhalter
    # steht erst im Text, wenn der Verweis selbst eingesetzt ist.
    for index in reversed(range(len(pieces))):
        result = result.replace(f"\x00{index}\x00", pieces[index])
    return result


def _emphasised(html: str) -> str:
    """Fettdruck und Kursives in schon maskiertem Text."""
    html = _STRONG.sub(r"<strong>\1</strong>", html)
    return _EMPHASIS.sub(r"<em>\1</em>", html)


def unlinked(text: str) -> str:
    """Seitenverweise durch ihren Text ersetzen — für Textausgabe und Suche."""
    return MANUAL_LINK.sub(r"\1", text)


def plain(text: str) -> str:
    """Der Text ohne jede Auszeichnung — für den Alt-Text eines Bildes.

    Ein Schrittsatz hebt Namen hervor (``*Bohrung setzen*``) und verweist auf
    Seiten. Im ``alt`` eines Bildes wird nichts davon gesetzt; dort stünden
    Sternchen und Klammern, und ein Bildschirmleser läse sie vor.
    """
    text = _CODE.sub(r"\1", unlinked(text))
    return _EMPHASIS.sub(r"\1", _STRONG.sub(r"\1", text))


def _closes_fence(delimiter: re.Match[str] | None, fence: str) -> bool:
    """Ob derselbe Markdown-Codezaun ohne Zusatztext endet."""
    return bool(
        delimiter
        and delimiter[1][0] == fence[0]
        and len(delimiter[1]) >= len(fence)
        and not delimiter[2].strip()
    )


def below_heading(markdown: str, level: int) -> str:
    """Beschreibungsüberschriften unter ihre umgebende Überschrift einordnen.

    ATX nutzt dasselbe Muster wie der HTML-Export. Setext wird zuerst in
    ATX umgewandelt, damit Qt und Website dieselbe Hierarchie lesen. Die
    relativen Ebenen bleiben bis zur Markdown-Grenze H6 erhalten; eingezogene
    und eingezäunte Codebeispiele bleiben unverändert.
    """
    lines: list[str] = []
    headings: list[tuple[int, int, str]] = []
    paragraph: int | None = None
    fence = ""
    for line in markdown.split("\n"):
        delimiter = _FENCE.match(line)
        if fence:
            if _closes_fence(delimiter, fence):
                fence = ""
            lines.append(line)
            continue
        if delimiter:
            fence = delimiter[1]
            paragraph = None
            lines.append(line)
            continue
        candidate = line.lstrip(" ") if not line.startswith("    ") else line
        heading = _HEADING.match(candidate)
        underlined = _SETEXT.match(line)
        if heading:
            headings.append((len(lines), len(heading[1]), heading[2]))
            paragraph = None
        elif underlined and paragraph is not None:
            title = " ".join(part.strip() for part in lines[paragraph:])
            del lines[paragraph:]
            headings.append((len(lines), 1 if underlined[1][0] == "=" else 2, title))
            paragraph = None
        elif (
            not line.strip()
            or line.startswith(("    ", "\t"))
            or candidate.startswith(">")
            or _BULLET.match(candidate)
            or _NUMBERED.match(candidate)
            or _ROW.match(candidate)
        ):
            paragraph = None
        elif paragraph is None:
            paragraph = len(lines)
        lines.append(line)
    shift = max(
        0, level + 1 - min((depth for _index, depth, _title in headings), default=level + 1)
    )
    for index, depth, title in headings:
        lines[index] = f"{'#' * min(depth + shift, 6)} {title}"
    return "\n".join(lines)


def to_html(
    markdown: str, figure: FigureResolver | None = None, link: LinkResolver | None = None
) -> str:
    """Ein Markdown-Text als HTML-Rumpf, ohne Kopf und ohne Gerüst.

    ``figure`` beantwortet einen Bildschlüssel mit Quelle, Alt-Text und
    Unterschrift. Ohne die Funktion — oder wenn sie nichts weiß — bleibt der
    Alt-Text als Absatz stehen, damit die Aussage nicht verschwindet. ``link``
    beantwortet einen Seitenverweis mit seiner Adresse (:func:`inline`).
    """
    out: list[str] = []
    table: list[list[str]] = []
    bullets: list[str] = []
    numbered: list[str] = []
    first_number = [1]
    paragraph: list[str] = []
    fence = ""
    code: list[str] = []

    def flush_code() -> None:
        content = "\n".join(code)
        out.append(f"<pre><code>{escape(content)}</code></pre>")
        code.clear()

    def flush_paragraph() -> None:
        if paragraph:
            out.append(f"<p>{inline(' '.join(paragraph), link)}</p>")
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            items = "".join(f"<li>{inline(entry, link)}</li>" for entry in bullets)
            out.append(f"<ul>{items}</ul>")
            bullets.clear()
        if numbered:
            items = "".join(f"<li>{inline(entry, link)}</li>" for entry in numbered)
            start = f' start="{first_number[0]}"' if first_number[0] != 1 else ""
            out.append(f"<ol{start}>{items}</ol>")
            numbered.clear()

    def flush_table() -> None:
        if not table:
            return
        head, *body = table
        header = "".join(f"<th>{inline(cell, link)}</th>" for cell in head)
        rows = "".join(
            "<tr>" + "".join(f"<td>{inline(cell, link)}</td>" for cell in row) + "</tr>"
            for row in body
        )
        out.append(f"<table><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table>")
        table.clear()

    def flush_all() -> None:
        flush_paragraph()
        flush_bullets()
        flush_table()

    for raw in markdown.splitlines():
        line = raw.rstrip()

        # Ein Beispiel aus einer Rezeptbeschreibung ist keine Überschrift;
        # sonst könnte sein „### Titel“ einen fremden Operationsanker erben.
        delimiter = _FENCE.match(line)
        if fence:
            if _closes_fence(delimiter, fence):
                flush_code()
                fence = ""
            else:
                code.append(raw)
            continue
        if delimiter:
            flush_all()
            fence = delimiter[1]
            continue

        if not line.strip():
            flush_all()
            continue

        if _SEPARATOR.match(line):
            # Die Trennzeile einer Tabelle trägt keine Daten.
            continue

        cells = _ROW.match(line)
        if cells:
            flush_paragraph()
            flush_bullets()
            table.append([cell.strip() for cell in cells.group(1).split("|")])
            continue
        flush_table()

        picture = _FIGURE.match(line)
        if picture:
            flush_all()
            out.append(_figure_html(picture.group(1), figure))
            continue

        heading = _HEADING.match(line)
        if heading:
            flush_all()
            level = min(len(heading.group(1)) + 1, 6)
            out.append(f"<h{level}>{inline(heading.group(2), link)}</h{level}>")
            continue

        bullet = _BULLET.match(line)
        if bullet:
            flush_paragraph()
            if numbered:
                flush_bullets()
            bullets.append(bullet.group(1))
            continue
        number = _NUMBERED.match(line)
        if number:
            flush_paragraph()
            if bullets:
                flush_bullets()
            if not numbered:
                first_number[0] = int(number.group(1))
            numbered.append(number.group(2))
            continue
        flush_bullets()

        paragraph.append(line.strip())

    if fence:
        flush_code()
    flush_all()
    return "\n".join(out)


def _figure_html(key: str, resolve: FigureResolver | None) -> str:
    found = resolve(key) if resolve else None
    if found is None:
        return ""
    source, alt, caption, dark = found if isinstance(found, FigureSource) else (*found, "")
    if not source:
        # Kein Bild vorhanden: der Alt-Text tritt an seine Stelle, statt dass
        # die Aussage ersatzlos verschwindet (Regel 18).
        return f'<p class="figure-text">{inline(alt)}</p>'
    text = f"<figcaption>{inline(caption)}</figcaption>" if caption else ""
    image = f'<img src="{escape(source, quote=True)}" alt="{escape(plain(alt), quote=True)}">'
    if dark:
        # ``<picture>`` und nicht zwei Bilder mit CSS: der Browser lädt genau
        # eine Datei, und beim Drucken greift die helle — Papier ist hell.
        image = (
            f'<picture><source srcset="{escape(dark, quote=True)}" '
            f'media="(prefers-color-scheme: dark)">{image}</picture>'
        )
    return f"<figure>{image}{text}</figure>"
