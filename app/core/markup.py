"""Markdown zu HTML — nur die Teilmenge, die das Handbuch benutzt.

Ein vollständiger Markdown-Übersetzer wäre hier eine Abhängigkeit für ein
Problem, das es nicht gibt: das Markdown, das umgewandelt wird, ist selbst
erzeugt (:mod:`app.core.manual`, :func:`app.core.registry.documentation`).
Damit ist die Menge dessen, was vorkommen kann, bekannt und geschlossen —
Überschriften, Absätze, Aufzählungen, Tabellen, Fettdruck, Kursives, Code und
Bildverweise.

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
_BULLET: Final = re.compile(r"^[*-]\s+(.*)$")
"""Beide Markdown-Schreibweisen: Die geschriebenen Kapitel nutzen ``* ``,
die erzeugten Referenzlisten ``- `` — wer nur eine kennt, klebt die andere
zu einem Fließtextabsatz zusammen, und aus zwanzig Operationen wird ein
Klumpen."""
_FIGURE: Final = re.compile(r"^!\[\]\(figure:([a-z0-9-]+)\)$")
_ROW: Final = re.compile(r"^\|(.+)\|$")
_SEPARATOR: Final = re.compile(r"^\|[\s:|-]+\|$")


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


def inline(text: str) -> str:
    """Fettdruck, Kursives und Code einer Zeile — der Rest wird maskiert."""
    pieces: list[str] = []

    def keep_code(match: re.Match[str]) -> str:
        pieces.append(f"<code>{escape(match.group(1))}</code>")
        return f"\x00{len(pieces) - 1}\x00"

    stashed = _CODE.sub(keep_code, text)
    result = escape(stashed)
    result = _STRONG.sub(r"<strong>\1</strong>", result)
    result = _EMPHASIS.sub(r"<em>\1</em>", result)
    for index, piece in enumerate(pieces):
        result = result.replace(f"\x00{index}\x00", piece)
    return result


def to_html(markdown: str, figure: FigureResolver | None = None) -> str:
    """Ein Markdown-Text als HTML-Rumpf, ohne Kopf und ohne Gerüst.

    ``figure`` beantwortet einen Bildschlüssel mit Quelle, Alt-Text und
    Unterschrift. Ohne die Funktion — oder wenn sie nichts weiß — bleibt der
    Alt-Text als Absatz stehen, damit die Aussage nicht verschwindet.
    """
    out: list[str] = []
    table: list[list[str]] = []
    bullets: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            items = "".join(f"<li>{inline(entry)}</li>" for entry in bullets)
            out.append(f"<ul>{items}</ul>")
            bullets.clear()

    def flush_table() -> None:
        if not table:
            return
        head, *body = table
        header = "".join(f"<th>{inline(cell)}</th>" for cell in head)
        rows = "".join(
            "<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in row) + "</tr>" for row in body
        )
        out.append(f"<table><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table>")
        table.clear()

    def flush_all() -> None:
        flush_paragraph()
        flush_bullets()
        flush_table()

    for raw in markdown.splitlines():
        line = raw.rstrip()

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
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            continue

        bullet = _BULLET.match(line)
        if bullet:
            flush_paragraph()
            bullets.append(bullet.group(1))
            continue
        flush_bullets()

        paragraph.append(line.strip())

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
    image = f'<img src="{escape(source, quote=True)}" alt="{escape(alt, quote=True)}">'
    if dark:
        # ``<picture>`` und nicht zwei Bilder mit CSS: der Browser lädt genau
        # eine Datei, und beim Drucken greift die helle — Papier ist hell.
        image = (
            f'<picture><source srcset="{escape(dark, quote=True)}" '
            f'media="(prefers-color-scheme: dark)">{image}</picture>'
        )
    return f"<figure>{image}{text}</figure>"
