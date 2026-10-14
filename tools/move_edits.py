"""Die Umschreibtabelle des Verschiebewerkzeugs und ihr Schreiber.

Ein Schnitt (``tools/move_names.py``) erzeugt je Datei eine Tabelle aus :class:`Edit`-Zeilen —
jede nennt die Stelle, den neuen Text und die Regel des Zuschnitts, aus der sie folgt. Der
Schreiber (:func:`apply_text`) setzt sie Zeichen für Zeichen in den Quelltext; alles außerhalb der
Stellen bleibt Byte für Byte, auch Kommentare und Zeilenenden. Ob das Ergebnis stimmt, entscheidet
nicht die Tabelle, sondern der Beweis (``tools/move_proof.py``) am geschriebenen Baum.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass

from tools.move_source import Source

#: ``expr``: einen Ausdruck ersetzen; ``stmt``: eine Anweisung samt ihrer Zeilen durch Anweisungen
#: ersetzen (leerer Text: entfernen); ``after``: Anweisungen hinter eine Anweisung setzen.
KINDS = ("expr", "stmt", "after")


@dataclass(frozen=True)
class Edit:
    """Eine Zeile der Umschreibtabelle. Die Lage ist die des alten Knotens wie ``ast`` sie nennt
    (Spalten in UTF-8-Bytes); ``text`` ist der neue Ausdruck oder die neuen Anweisungen ohne
    Einrückung, ``rule`` die Regel des Zuschnitts, ``detail`` das Wie fürs Protokoll."""

    path: str
    kind: str
    rule: str
    detail: str
    text: str
    line: int
    col: int
    end_line: int
    end_col: int

    @staticmethod
    def at(path: str, kind: str, node: ast.AST, text: str, rule: str, detail: str) -> Edit:
        line = getattr(node, "lineno", 0)
        col = getattr(node, "col_offset", 0)
        end_line = getattr(node, "end_lineno", None) or line
        end_col = getattr(node, "end_col_offset", None) or col
        return Edit(path, kind, rule, detail, text, line, col, end_line, end_col)


class EditError(Exception):
    """Die Tabelle lässt sich so nicht anwenden — ein Fehler des Werkzeugs; die Meldung nennt Datei
    und Zeile."""


def _indent_block(text: str, indent: str, newline: str) -> str:
    return newline.join((indent + line) if line else line for line in text.split("\n"))


def apply_text(source: Source, edits: Iterable[Edit]) -> str:
    """Die Tabelle in den Quelltext geschrieben."""
    ops: list[tuple[int, int, int, str, Edit]] = []
    for order, edit in enumerate(edits):
        if edit.kind == "expr":
            start = source.offset(edit.line, edit.col)
            end = source.offset(edit.end_line, edit.end_col)
            ops.append((start, end, order, edit.text, edit))
        elif edit.kind == "stmt":
            _whole_lines(source, edit)
            start = source.line_start(edit.line)
            end = source.line_end(edit.end_line)
            if edit.text:
                indent = source.indent_of(edit.line)
                body = _indent_block(edit.text, indent, source.newline) + source.newline
            else:
                body = ""
            ops.append((start, end, order, body, edit))
        elif edit.kind == "after":
            indent = source.indent_of(edit.line)
            at = source.line_end(edit.end_line)
            body = _indent_block(edit.text, indent, source.newline) + source.newline
            if at == len(source.text) and not source.text.endswith("\n"):
                body = source.newline + body
            ops.append((at, at, order, body, edit))
        else:
            raise EditError(f"{edit.path}: unbekannte Art {edit.kind!r}")
    ops.sort(key=lambda op: (op[0], op[1], op[2]))
    out: list[str] = []
    cursor = 0
    for start, end, _order, text, edit in ops:
        if start < cursor:
            raise EditError(
                f"{edit.path}:{edit.line}: zwei Zeilen der Tabelle überlappen ({edit.rule})"
            )
        out.append(source.text[cursor:start])
        out.append(text)
        cursor = end
    out.append(source.text[cursor:])
    result = "".join(out)
    return ("﻿" + result) if source.bom else result


def _whole_lines(source: Source, edit: Edit) -> None:
    """Eine ersetzte Anweisung steht allein auf ihren Zeilen (Kommentar dahinter erlaubt; er
    gehört dann in ``text``)."""
    before = source.lines[edit.line - 1][: source.char_col(edit.line, edit.col)]
    after = source.lines[edit.end_line - 1][source.char_col(edit.end_line, edit.end_col) :]
    if before.strip() or (after.strip() and not after.strip().startswith("#")):
        raise EditError(f"{edit.path}:{edit.line}: die Anweisung teilt ihre Zeile mit anderem Code")


def trailing_comment(source: Source, node: ast.AST) -> str:
    """Der Kommentar hinter der letzten Zeile einer Anweisung (``# noqa: E402``), sonst leer."""
    end_line = getattr(node, "end_lineno", None)
    end_col = getattr(node, "end_col_offset", None)
    if end_line is None or end_col is None:
        return ""
    rest = source.lines[end_line - 1][source.char_col(end_line, end_col) :].strip()
    return rest if rest.startswith("#") else ""
