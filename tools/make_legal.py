"""Aus den Rechtstexten die Seiten der Website machen — und die Fassung für den
Installer.

Quelle sind ``EULA.md``, ``AGB.md`` und ``WIDERRUF.md`` im Wurzelverzeichnis.
Sie stehen dort, weil sie zum Repository gehören wie die Lizenz: lesbar, ohne
Werkzeug, in der Fassung, die gilt. Was hier entsteht, wird nie von Hand
geändert — eine zweite Fassung eines Rechtstexts ist schlimmer als keine.

**Warum nicht** ``app.core.markup``. Der Übersetzer dort deckt genau die
Teilmenge ab, die das Handbuch erzeugt: keine Verweise, keine gezählten
Listen, keine Zitatblöcke. Rechtstexte brauchen alle drei. Ihn dafür zu
erweitern hieße, einen Baustein der Anwendung für ein Bauwerkzeug zu ändern —
der Übersetzer hier ist klein genug, um daneben zu stehen.

Aufruf:

    .venv\\Scripts\\python.exe tools/make_legal.py
"""

from __future__ import annotations

import re
import sys
from html import escape
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.branding import APP_NAME, APP_VENDOR  # noqa: E402

WEBSITE = ROOT / "website"

#: Quelle, Zieldatei, Titel der Seite und die Beschriftung im Fußbereich.
DOCUMENTS: tuple[tuple[str, str, str], ...] = (
    ("EULA.md", "eula.html", "Lizenzvertrag"),
    ("AGB.md", "agb.html", "AGB"),
    ("WIDERRUF.md", "widerruf.html", "Widerruf"),
)

# --- Der Übersetzer ---------------------------------------------------------------

_CODE = re.compile(r"`([^`]+)`")
_STRONG = re.compile(r"\*\*([^*]+)\*\*")
_EMPHASIS = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_AUTOLINK = re.compile(r"&lt;(https?://[^&\s]+|mailto:[^&\s]+|[^&\s@]+@[^&\s]+)&gt;")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^\*\s+(.*)$")
_NUMBERED = re.compile(r"^(\d+)\.\s+(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
_RULE = re.compile(r"^-{3,}$")


#: Zwei Leerzeichen am Zeilenende sind in Markdown ein harter Umbruch. Eine
#: Anschrift braucht ihn — ohne ihn steht sie als eine Zeile da, und das ist
#: bei einer Widerrufsadresse keine Schönheitsfrage.
BREAK = "\x01"


def inline(text: str) -> str:
    """Auszeichnung einer Zeile. Code zuerst, damit darin nichts umgedeutet wird."""
    kept: list[str] = []

    def keep_code(match: re.Match[str]) -> str:
        kept.append(f"<code>{escape(match.group(1))}</code>")
        return f"\x00{len(kept) - 1}\x00"

    result = escape(_CODE.sub(keep_code, text))
    result = _LINK.sub(r'<a href="\2">\1</a>', result)
    result = _AUTOLINK.sub(_autolink, result)
    result = _STRONG.sub(r"<strong>\1</strong>", result)
    result = _EMPHASIS.sub(r"<em>\1</em>", result)
    result = result.replace(r"\*", "*").replace(BREAK, "<br>")
    for index, piece in enumerate(kept):
        result = result.replace(f"\x00{index}\x00", piece)
    return result


def _autolink(match: re.Match[str]) -> str:
    target = match.group(1)
    href = target if target.startswith(("http", "mailto:")) else f"mailto:{target}"
    return f'<a href="{href}">{target}</a>'


def to_html(markdown: str) -> str:
    """Der Rumpf einer Rechtstextseite."""
    out: list[str] = []
    paragraph: list[str] = []
    bullets: list[str] = []
    numbers: list[str] = []
    quote: list[str] = []

    def flush() -> None:
        if paragraph:
            out.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()
        if bullets:
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in bullets) + "</ul>")
            bullets.clear()
        if numbers:
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in numbers) + "</ol>")
            numbers.clear()
        if quote:
            out.append(f"<blockquote><p>{inline(' '.join(quote))}</p></blockquote>")
            quote.clear()

    for raw in markdown.splitlines():
        # Zwei Leerzeichen am Ende: harter Umbruch, der die Verkettung übersteht.
        line = raw.rstrip() + (BREAK if raw.endswith("  ") and raw.strip() else "")

        if not line.strip() or line.strip() == "&nbsp;":
            flush()
            if line.strip() == "&nbsp;":
                out.append('<p class="blank">&nbsp;</p>')
            continue

        if _RULE.match(line):
            flush()
            out.append("<hr>")
            continue

        heading = _HEADING.match(line)
        if heading:
            flush()
            level = min(len(heading.group(1)), 6)
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            continue

        marker = _QUOTE.match(line)
        if marker:
            if paragraph or bullets or numbers:
                flush()
            quote.append(marker.group(1))
            continue

        bullet = _BULLET.match(line)
        if bullet:
            if paragraph or numbers or quote:
                flush()
            bullets.append(bullet.group(1))
            continue

        numbered = _NUMBERED.match(line)
        if numbered:
            if paragraph or bullets or quote:
                flush()
            numbers.append(numbered.group(2))
            continue

        # Fortsetzungszeile einer Aufzählung oder eines Zitats
        if bullets and line.startswith("  "):
            bullets[-1] += " " + line.strip()
            continue
        if numbers and line.startswith("   "):
            numbers[-1] += " " + line.strip()
            continue
        if quote:
            quote.append(line.strip())
            continue

        paragraph.append(line.strip())

    flush()
    return "\n".join(out)


def to_text(markdown: str) -> str:
    """Reiner Text für die Lizenzseite des Installers.

    Inno Setup zeigt die Datei roh an; Sternchen und Rautezeichen stünden dort
    als Zeichen herum. Die Gliederung bleibt über Leerzeilen erhalten.

    Fettdruck wird **vor** dem Zerlegen in Zeilen entfernt: er reicht über
    Zeilenumbrüche hinweg, und ein zeilenweiser Ausdruck findet dann nur die
    Hälfte — im Text stand danach ``**vierzehn Tage`` mit offenem Sternchen.
    """
    markdown = re.sub(r"\*\*(.+?)\*\*", r"\1", markdown, flags=re.S)
    lines: list[str] = []
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if _RULE.match(line):
            lines.append("")
            continue
        heading = _HEADING.match(line)
        if heading:
            title = heading.group(2)
            lines.extend(["", _plain(title), "-" * len(_plain(title))])
            continue
        lines.append(_plain(line))
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def _plain(text: str) -> str:
    """Auszeichnung entfernen, Inhalt behalten."""
    text = _LINK.sub(r"\1 (\2)", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = text.replace("\\*", "*")
    text = _CODE.sub(r"\1", text)
    text = re.sub(r"^>\s?", "", text)
    text = re.sub(r"^\*\s+", "  - ", text)
    text = text.replace("<", "").replace(">", "")
    return text.replace("&nbsp;", "").replace(BREAK, "").rstrip()


# --- Die Seite --------------------------------------------------------------------


#: Ein Platzhalter: Großbuchstaben in eckigen Klammern.
PLACEHOLDER = re.compile(r"\[[A-ZÄÖÜ][A-ZÄÖÜ .\-,]{3,}\]")

DRAFT_NOTE = (
    '<p class="draft">Entwurf — dieser Text nennt noch Platzhalter statt '
    "Angaben und ist vor der Veröffentlichung fachlich zu prüfen.</p>"
)

#: Ob die Texte fachlich geprüft sind. Auf ``False`` stellen, sobald sie es
#: sind — dann fällt der Vorbehalt, und nur dann.
REVIEW_PENDING = True

REVIEW_NOTE = (
    '<p class="draft">Sorgfältiger Entwurf, aber keine Rechtsberatung — vor '
    "der Veröffentlichung fachlich zu prüfen.</p>"
)

#: Die englische Startseite verlinkt hierher, und wer von dort kommt, steht
#: unangekündigt vor einem deutschen Vertrag. Die AGB sagen in § 3, dass die
#: Vertragssprache Deutsch ist — nur liest das niemand, der auf „Licence
#: agreement" geklickt hat. Der Hinweis steht deshalb oben und in der Sprache,
#: in der die Frage entsteht.
LANGUAGE_NOTE = (
    '<p class="lang-note" lang="en"><b>This document is in German.</b> '
    "German is the contract language for every purchase from this site; a "
    "translation would be a courtesy, not the agreement. If anything here "
    "matters to your decision, write to "
    '<a href="mailto:support@solidon3d.de">support@solidon3d.de</a> and we '
    "will explain it in English before you buy.</p>"
)


def draft_banner(markdown: str) -> str:
    """Der Entwurfshinweis — aus zwei Gründen, die nicht zusammenfallen.

    Der erste ist der Platzhalter. Er wird nicht von Hand gesetzt und nicht von
    Hand entfernt: sobald die Anschrift eingetragen ist, verschwindet er beim
    nächsten Lauf von selbst. Ein Hinweis, den jemand wegnehmen muss, bleibt
    sonst stehen, wenn er nicht mehr stimmt — oder er steht noch da, wenn er
    längst falsch ist.

    Der zweite ist die fachliche Prüfung, und sie hängt an keinem Platzhalter.
    Beides an einen Satz zu hängen war zu wenig: mit dem Namen des
    Zahlungsdienstleisters fiel der letzte Platzhalter, und ein ungeprüfter
    Vertrag hätte ohne jeden Vorbehalt dagestanden. Diese Zeile fällt erst,
    wenn jemand :data:`REVIEW_PENDING` umstellt — also wenn die Prüfung
    wirklich stattgefunden hat.
    """
    if PLACEHOLDER.search(markdown):
        return DRAFT_NOTE
    return REVIEW_NOTE if REVIEW_PENDING else ""


def body_html(markdown: str) -> str:
    """Der Rumpf einer Seite: Überschrift, Hinweise, Text.

    Die Hinweise stehen unter der Überschrift und nicht darüber — sonst liest
    man zuerst eine Warnung und danach erst, wozu sie gehört.
    """
    notes = "\n".join(filter(None, (draft_banner(markdown), LANGUAGE_NOTE)))
    heading, _, rest = to_html(markdown).partition("\n")
    return f"{heading}\n{notes}\n{rest}"


def page(title: str, body: str, siblings: str) -> str:
    return (
        f'<!DOCTYPE html>\n<html lang="de">\n<head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)} — {APP_NAME}</title>\n"
        f'<meta name="robots" content="noindex">\n'
        f'<link rel="icon" href="/icon.svg" type="image/svg+xml">\n'
        f'<link rel="stylesheet" href="style.css">\n'
        f"</head>\n<body>\n\n"
        f'<header class="site">\n  <div class="wrap">\n'
        f'    <a class="brand" href="/">Solidon<span>3D</span></a>\n'
        f"  </div>\n</header>\n\n"
        f'<main class="legal">\n  <div class="wrap">\n{body}\n  </div>\n</main>\n\n'
        f'<footer class="site">\n  <div class="wrap">\n'
        f"    © 2026 {APP_VENDOR} ·\n"
        f'    <a href="/">Startseite</a>{siblings}\n'
        f"  </div>\n</footer>\n\n</body>\n</html>\n"
    )


def main() -> int:
    links = {
        "eula.html": "Lizenzvertrag",
        "agb.html": "AGB",
        "widerruf.html": "Widerruf",
        "impressum.html": "Impressum",
        "datenschutz.html": "Datenschutz",
    }

    for source_name, target_name, title in DOCUMENTS:
        source = ROOT / source_name
        markdown = source.read_text(encoding="utf-8")

        others = "".join(
            f' ·\n    <a href="/{name}">{label}</a>'
            for name, label in links.items()
            if name != target_name
        )
        target = WEBSITE / target_name
        target.write_text(page(title, body_html(markdown), others), encoding="utf-8")
        marker = "  (Entwurf)" if draft_banner(markdown) else ""
        print(f"  {source_name} → website/{target_name}{marker}")

    # Der Installer zeigt den Lizenzvertrag, nicht die Urheberrechtsnotiz.
    licence_text = ROOT / "packaging" / "eula.txt"
    licence_text.write_text(
        to_text((ROOT / "EULA.md").read_text(encoding="utf-8")), encoding="utf-8"
    )
    print(f"  EULA.md → packaging/{licence_text.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
