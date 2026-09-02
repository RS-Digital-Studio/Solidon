"""Aus den Rechtstexten die Seiten der Website machen — und die Version für den
Installer.

Quelle sind die Rechtstexte im Wurzelverzeichnis.
Sie stehen dort, weil sie zum Repository gehören wie die Lizenz: lesbar, ohne
Werkzeug, in der Version, die gilt. Was hier entsteht, wird nie von Hand
geändert — eine zweite Version eines Rechtstexts ist schlimmer als keine.

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
from tools.site_nav import ENTRIES  # noqa: E402

WEBSITE = ROOT / "website"

#: Quelle, Zieldatei, Titel der Seite — und ob sie ein **Vertragstext** ist.
#:
#: Das vierte Feld entscheidet über den englischen Sprachhinweis
#: (:data:`LANGUAGE_NOTE`). Er sagt „German is the contract language for every
#: purchase from this site" und gehört damit zu Lizenzvertrag, AGB und
#: Widerruf. In der **Datenschutzerklärung** wäre er schlicht falsch: Sie ist
#: kein Vertrag, sie gilt auch für jemanden, der nie etwas kauft, und ein
#: Hinweis auf die Vertragssprache beantwortet dort eine Frage, die niemand
#: gestellt hat. Genau deshalb trug die von Hand gepflegte Seite ihn nie.
DOCUMENTS: tuple[tuple[str, str, str, bool], ...] = (
    ("EULA.md", "eula.html", "Lizenzvertrag", True),
    ("AGB.md", "agb.html", "AGB", True),
    ("WIDERRUF.md", "widerruf.html", "Widerruf", True),
    ("DATENSCHUTZ.md", "datenschutz.html", "Datenschutz", False),
)

# --- Der Übersetzer ---------------------------------------------------------------

_CODE = re.compile(r"`([^`]+)`")
_STRONG = re.compile(r"\*\*([^*]+)\*\*")
_EMPHASIS = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_AUTOLINK = re.compile(r"&lt;(https?://[^&\s]+|mailto:[^&\s]+|[^&\s@]+@[^&\s]+)&gt;")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")

#: Eine Sprungmarke am Ende einer Überschrift: ``## Rückmeldung {#rueckmeldung}``.
#: Kleinbuchstaben, Ziffern und Bindestrich — mehr braucht ein Anker nicht, und
#: mehr zuzulassen hieße, jede Eingabe für ein ``id``-Attribut zu maskieren.
_ANCHOR = re.compile(r"^(.*?)\s*\{#([a-z][a-z0-9-]*)\}$")


def _split_anchor(title: str) -> tuple[str, str]:
    """Trennt eine Überschrift von ihrer Sprungmarke.

    **Ohne sie kann ein Rechtstext nicht auf sich selbst verweisen.** Die
    Datenschutzerklärung braucht genau das: Ein Absatz verweist auf einen
    weiter unten erklärten Eingabeweg. Ein Verweis ohne Ziel ist schlechter als keiner —
    ``tests/test_website.py`` prüft jede Sprungmarke gegen ihr Ziel.

    Steht keine Marke da, bleibt die Überschrift, wie sie war; die drei
    bestehenden Dokumente ändern sich dadurch um kein Byte (gemessen).
    """
    match = _ANCHOR.match(title)
    return (match.group(1), match.group(2)) if match else (title, "")


_BULLET = re.compile(r"^\*\s+(.*)$")
_NUMBERED = re.compile(r"^(\d+)\.\s+(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
_RULE = re.compile(r"^-{3,}$")


#: Zwei Leerzeichen am Zeilenende sind in Markdown ein harter Umbruch. Eine
#: Anschrift braucht ihn — ohne ihn steht sie als eine Zeile da, und das ist
#: bei einer Widerrufsadresse keine Schönheitsfrage.
BREAK = "\x01"

#: Ein mit Gegenschrägstrich geschütztes Sternchen. Es muss aus dem Text
#: verschwinden, **bevor** die Auszeichnungsregeln laufen — sonst liest
#: `_EMPHASIS` zwei geschützte Sternchen einer Zeile als Paar und macht ein
#: `<em>` daraus. Genau das ist dem Muster-Widerrufsformular passiert, wo
#: `(\*)` zweimal je Zeile steht: Im fertigen HTML stand dort `(\<em>)`
#: mitten im gesetzlich vorgegebenen Text.
STAR = "\x02"


def inline(text: str) -> str:
    """Auszeichnung einer Zeile. Code zuerst, damit darin nichts umgedeutet wird."""
    kept: list[str] = []

    def keep_code(match: re.Match[str]) -> str:
        kept.append(f"<code>{escape(match.group(1))}</code>")
        return f"\x00{len(kept) - 1}\x00"

    result = escape(_CODE.sub(keep_code, text))
    result = result.replace(r"\*", STAR)
    result = _LINK.sub(r'<a href="\2">\1</a>', result)
    result = _AUTOLINK.sub(_autolink, result)
    result = _STRONG.sub(r"<strong>\1</strong>", result)
    result = _EMPHASIS.sub(r"<em>\1</em>", result)
    result = result.replace(STAR, "*").replace(BREAK, "<br>")
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
            title, anchor = _split_anchor(heading.group(2))
            marker = f' id="{anchor}"' if anchor else ""
            out.append(f"<h{level}{marker}>{inline(title)}</h{level}>")
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
        # Eine Zahl mit Punkt am Zeilenanfang ist nur dann eine Aufzählung,
        # wenn eine läuft, sie mit 1 beginnt oder kein Absatz offen ist —
        # sonst ist es ein Datum am Umbruch: Der Vertrag zeigte „1. Oktober
        # 2026", weil „30. Oktober 2026." hinter „nennt den" auf einer
        # neuen Zeile stand.
        if numbered and (numbers or numbered.group(1) == "1" or not paragraph):
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
    markdown = re.sub(r"\*\*(.+?)\*\*", r"\1", markdown, flags=re.DOTALL)
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
    '<p class="draft">Entwurf — Pflichtangaben fehlen noch; die Veröffentlichung '
    "bleibt bis zu ihrer Ergänzung gesperrt.</p>"
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
    """Ein sichtbarer Hinweis nur dann, wenn echte Platzhalter übrig sind.

    Eine allgemeine Bewertung der Texte gehört in die interne Auditakte und
    nicht auf jede öffentliche Rechtsseite. Der Erzeuger verhindert weiterhin,
    dass eine Seite einen Platzhalter wie eine fertige Angabe zeigt.
    """
    return DRAFT_NOTE if PLACEHOLDER.search(markdown) else ""


def body_html(markdown: str, contract: bool = True) -> str:
    """Der Rumpf einer Seite: Überschrift, Hinweise, Text.

    Die Hinweise stehen unter der Überschrift und nicht darüber — sonst liest
    man zuerst eine Warnung und danach erst, wozu sie gehört.

    ``contract`` entscheidet über den englischen Sprachhinweis. Er spricht von
    der **Vertragssprache beim Kauf** und gehört damit zu Lizenzvertrag, AGB
    und Widerruf; in der Datenschutzerklärung beantwortet er eine Frage, die
    dort niemand stellt, und behauptet nebenbei einen Kauf, den es für ihre
    Geltung nicht braucht. Die von Hand gepflegte Seite trug ihn nie — das
    war kein Versehen, sondern die richtige Entscheidung, und sie bleibt.
    """
    notes = "\n".join(filter(None, (draft_banner(markdown), LANGUAGE_NOTE if contract else "")))
    heading, _, rest = to_html(markdown).partition("\n")
    return f"{heading}\n{notes}\n{rest}"


def page(title: str, body: str, siblings: str) -> str:
    """Der Rumpf einer Rechtsseite.

    Der Sprung an den Inhalt steht hier und nicht von Hand in der erzeugten
    Datei. Dort stand er: „Neunundzwanzig Seiten, und auf keiner kam die
    Tastatur an der Kopfzeile vorbei" zählte die drei Rechtstexte zu den von
    Hand gepflegten und trug ihn im Quelltext nach — nur werden sie erzeugt.
    Der nächste Lauf nahm ihn wieder heraus, und ``tests/test_website.py``
    wurde rot, ohne dass sich eine Zeile Inhalt geändert hatte (WCAG 2.4.1).
    """
    return (
        f'<!DOCTYPE html>\n<html lang="de">\n<head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)} — {APP_NAME}</title>\n"
        f'<meta name="robots" content="noindex">\n'
        f'<meta property="og:image" '
        f'content="https://solidon3d.de/handbuch/de/main-window.png">\n'
        f'<meta property="og:image:alt" '
        f'content="Das Hauptfenster von Solidon3D mit Modell, Verlauf und Prüfbericht">\n'
        f'<link rel="icon" href="/icon.svg" type="image/svg+xml">\n'
        f'<link rel="stylesheet" href="style.css">\n'
        f"</head>\n<body>\n\n"
        f'<a class="skip" href="#content">Zum Inhalt springen</a>\n\n'
        f'<header class="site">\n  <div class="wrap">\n'
        f'    <a class="brand" href="/">Solidon<span>3D</span></a>\n'
        f"  </div>\n</header>\n\n"
        f'<main id="content" class="legal">\n  <div class="wrap">\n{body}\n  </div>\n</main>\n\n'
        f'<footer class="site">\n  <div class="wrap">\n'
        f"    © 2026 {APP_VENDOR} ·\n"
        # Die Rechtstexte tragen kein Kopfmenü — hier ist die Fußzeile
        # der einzige Weg zurück zu den Produktfunktionen.
        f'    <a href="/">Startseite</a> ·\n'
        f'    <a href="{ENTRIES["de"][0][0]}">{ENTRIES["de"][0][1]}</a>{siblings}\n'
        # Auch die Rechtstexte: Wer wissen will, ob jemand das Widerrufs-
        # recht liest, braucht die Zeile. Was gezählt wird, steht in der
        # Datenschutzerklärung selbst — der Pfad und sonst nichts.
        f'  </div>\n</footer>\n\n<script src="/site.js" defer></script>\n</body>\n</html>\n'
    )


def main() -> int:
    links = {
        "eula.html": "Lizenzvertrag",
        "agb.html": "AGB",
        "widerruf.html": "Widerruf",
        "impressum.html": "Impressum",
        "datenschutz.html": "Datenschutz",
    }

    for source_name, target_name, title, contract in DOCUMENTS:
        source = ROOT / source_name
        markdown = source.read_text(encoding="utf-8")

        others = "".join(
            f' ·\n    <a href="/{name}">{label}</a>'
            for name, label in links.items()
            if name != target_name
        )
        target = WEBSITE / target_name
        target.write_text(page(title, body_html(markdown, contract), others), encoding="utf-8")
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
