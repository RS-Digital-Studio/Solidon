"""Erzeugt, was Suchmaschinen von der Website zuerst holen.

Drei Dateien und ein Auszeichnungsblock, alle aus dem Bestand abgeleitet und
keiner von Hand gepflegt:

* ``website/robots.txt`` — verweist auf die Sitemap, sonst nichts Verbotenes.
* ``website/sitemap.xml`` — jede Seite einmal, mit ihren Sprachversionen
  daneben (``xhtml:link``). Die Zuordnung kommt aus den ``hreflang``-Angaben
  der Seiten selbst; eine zweite Liste hier würde beim nächsten Zusatz
  auseinanderlaufen.
* ``website/llms.txt`` — dasselbe für Sprachmodelle, die eine Übersicht
  suchen statt eines Crawls.
* ``FAQPage``-Auszeichnung in den Startseiten, gelesen aus dem
  ``<div class="faq">``, das dort ohnehin steht.

Kein ``lastmod``, kein ``priority``, kein ``changefreq``: Google wertet die
beiden letzten nicht aus, und ein ``lastmod``, das aus der Dateizeit stammt,
ist nach einem frischen Klon für jede Seite derselbe falsche Tag.

Läuft **nach** ``make_manual.py`` und ``make_legal.py`` — es liest deren
Ergebnis mit.

Aufruf::

    .venv\\Scripts\\python.exe tools/make_seo.py
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"
SITE = "https://solidon3d.de/"

#: Die Startseite heißt in der Adresse nicht ``index.html``, sondern nichts.
#: Beim Verweis auf sie zählt der Ordner, sonst steht dieselbe Seite unter
#: zwei Adressen — und die Auswahl, welche gewinnt, trifft dann Google.
_INDEX = re.compile(r"(^|/)index\.html$")

_NOINDEX = re.compile(r'<meta name="robots" content="[^"]*noindex')

#: Der Nachweis für die Google Search Console. Es ist eine Datei mit einer
#: Zeile, kein Dokument: sie muss unter ihrem Namen erreichbar sein und sonst
#: nichts. In der Sitemap wäre sie eine angebotene Seite ohne Inhalt — und
#: genau darüber meldet die Search Console dann einen Fehler.
_VERIFICATION = re.compile(r"^google[0-9a-f]+\.html$")
_ALTERNATE = re.compile(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">')
_TITLE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
_DESCRIPTION = re.compile(r'<meta name="description" content="([^"]*)"')
_FAQ_BLOCK = re.compile(r'<div class="faq">(.*?)</div>\s*</section>', re.DOTALL)

#: Die Sprungmarke des Abschnitts, in dem die Fragen stehen. Sie heißt in jeder
#: Sprache anders (`fragen`, `questions`) und wird deshalb abgelesen, nicht
#: angenommen. Gesucht wird **rückwärts** ab dem Fragenblock: vorwärts fände
#: `search` die erste Section des Dokuments und nicht die, um die es geht —
#: beide bestehen die Sprungmarkenprüfung, nur zeigt die eine auf die falsche
#: Stelle.
_SECTION = re.compile(r'<section id="([^"]+)"')
_ENTRY = re.compile(r"<details>\s*<summary>(.*?)</summary>(.*?)</details>", re.DOTALL)
_LD_FAQ = re.compile(
    r'\n<script type="application/ld\+json">\n\{\n  "@context": "https://schema\.org",\n'
    r'  "@type": "FAQPage".*?\n</script>',
    re.DOTALL,
)


def page_url(path: Path) -> str:
    """Die Adresse, unter der eine Datei erreichbar ist."""
    relative = path.relative_to(WEBSITE).as_posix()
    return SITE + _INDEX.sub(r"\1", relative)


def pages() -> list[Path]:
    """Alle ausgelieferten Seiten, oberste Ebene und Sprachordner.

    Ohne den Nachweis der Search Console: der liegt zwar als ``.html`` dort,
    ist aber eine Zeile Text und keine Seite.
    """
    found = [*WEBSITE.glob("*.html"), *WEBSITE.glob("*/*.html")]
    return sorted(p for p in found if not _VERIFICATION.match(p.name))


def listed_pages() -> list[Path]:
    """Die Seiten, die in eine Suchmaschine gehören.

    Die fünf Rechtstexte tragen ``noindex`` — das ist eine Entscheidung, keine
    Lücke: sie sollen erreichbar sein, aber nicht in der Suche mit der
    Startseite konkurrieren. Eine Sitemap, die sie trotzdem anbietet, sagt das
    Gegenteil dessen, was auf der Seite steht; die Search Console meldet
    genau diesen Widerspruch, und welches Signal gewinnt, entscheidet dann
    Google.
    """
    return [p for p in pages() if _NOINDEX.search(p.read_text(encoding="utf-8")) is None]


def language_groups() -> dict[str, list[tuple[str, str]]]:
    """Ordnet jeder Seite ihre Sprachversionen zu.

    Die Quelle sind die ``hreflang``-Angaben in den Seiten. Wo keine stehen,
    bleibt die Liste leer.
    """
    groups: dict[str, list[tuple[str, str]]] = {}
    for page in listed_pages():
        groups[page_url(page)] = _ALTERNATE.findall(page.read_text(encoding="utf-8"))
    return groups


def sitemap() -> str:
    """Die Sitemap als XML, eine Seite je ``<url>``."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for address, alternates in language_groups().items():
        lines.append("  <url>")
        lines.append(f"    <loc>{address}</loc>")
        for language, target in alternates:
            lines.append(f'    <xhtml:link rel="alternate" hreflang="{language}" href="{target}"/>')
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def robots() -> str:
    """``robots.txt`` — alle Seiten erlaubt, die Maschinerie darunter nicht.

    ``/api/`` steht auf der Sperrliste, seit dort mehr liegt als die
    Rückmeldung: der Zählpunkt und die Auswertung dazu. Beide sind keine
    Seiten, und die Auswertung ist ohnehin hinter einer Anmeldung — in einem
    Suchindex haben sie nichts verloren.
    """
    return (
        "# Solidon3D — solidon3d.de\n"
        "# Die Seite hat nichts zu verbergen: kein Konto, keine Ansicht, die\n"
        "# nur für angemeldete Besucher gilt. Gezählt wird auf dem eigenen\n"
        "# Server und ohne Cookie; was dabei entsteht, steht in der\n"
        "# Datenschutzerklärung.\n"
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "\n"
        f"Sitemap: {SITE}sitemap.xml\n"
    )


def _plain(markup: str) -> str:
    """Auszeichnung raus, Text übrig — für die Antwort im FAQ-Schema.

    Ein Tag wird zu einem Leerzeichen und nicht zu nichts, sonst klebte das
    Ende eines Absatzes am Anfang des nächsten. Steht hinter dem Tag aber ein
    Satzzeichen, entsteht daraus eine Lücke davor: aus ``<b>…1.0</b>, die
    Verkaufsversion`` wird ``…1.0 , die Verkaufsversion``. Das stand am
    28.08.2026 an sechs Stellen in der ausgelieferten Auszeichnung.

    **Nur Komma und Punkt werden angezogen.** Vor ``; : ! ?`` setzt die
    französische Typografie bewusst ein Leerzeichen, und die Seite tut das
    auch — ein Fix über alle Satzzeichen würde sie brechen.
    """
    stripped = re.sub(r"<[^>]+>", " ", markup)
    text = re.sub(r"\s+", " ", html.unescape(stripped)).strip()
    return re.sub(r" +([,.])", r"\1", text)


def faq_entries(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Liest Sprungmarke, Frage und Antwort aus dem FAQ-Abschnitt einer Seite."""
    block = _FAQ_BLOCK.search(text)
    if block is None:
        return "", []
    before = _SECTION.findall(text[: block.start()])
    entries = [(_plain(q), _plain(a)) for q, a in _ENTRY.findall(block.group(1))]
    return (before[-1] if before else ""), entries


def faq_markup(text: str, address: str) -> str:
    """Die ``FAQPage``-Auszeichnung zu den Fragen einer Seite."""
    mark, entries = faq_entries(text)
    if not entries:
        return ""
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "@id": f"{address}#{mark}",
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
            for question, answer in entries
        ],
    }
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    return f'\n<script type="application/ld+json">\n{raw}\n</script>'


def write_faq() -> int:
    """Setzt die Auszeichnung in jede Seite, die häufige Fragen führt."""
    written = 0
    for page in pages():
        text = page.read_text(encoding="utf-8")
        updated = _LD_FAQ.sub("", text)
        markup = faq_markup(updated, page_url(page))
        if not markup:
            if updated != text:
                page.write_text(updated, encoding="utf-8")
            continue
        updated = updated.replace("\n</head>", f"{markup}\n</head>", 1)
        if updated != text:
            page.write_text(updated, encoding="utf-8")
            written += 1
    return written


def llms() -> str:
    """``llms.txt`` — die Seite in Kurzform, für Modelle statt für Crawler."""
    lines = [
        "# Solidon3D",
        "",
        "> Desktop-Anwendung für den 3D-Druck: heruntergeladene Modelle anpassen,",
        "> eigene konstruieren, Druckbarkeit vor dem Slicen prüfen. Läuft lokal auf",
        "> Windows, macOS und Linux — ohne Konto, ohne Abo, ohne Telemetrie.",
        "",
        "Solidon3D ist kein Slicer und kein Modellkatalog. Es sitzt dazwischen:",
        "zwischen der heruntergeladenen STL, die nicht passt, und dem Slicer, der",
        "sie ohne Rückfrage druckt. Geometrie rechnet Code, nicht das Sprachmodell;",
        "der eingebaute Agent bedient dieselben Operationen wie die Menüs und ist",
        "abschaltbar.",
        "",
        "## Seiten",
        "",
    ]
    for page in listed_pages():
        text = page.read_text(encoding="utf-8")
        title = _TITLE.search(text)
        description = _DESCRIPTION.search(text)
        if title is None:
            continue
        name = html.unescape(title.group(1).strip())
        sentence = f": {html.unescape(description.group(1))}" if description else ""
        lines.append(f"- [{name}]({page_url(page)}){sentence}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    (WEBSITE / "robots.txt").write_text(robots(), encoding="utf-8")
    (WEBSITE / "sitemap.xml").write_text(sitemap(), encoding="utf-8")
    (WEBSITE / "llms.txt").write_text(llms(), encoding="utf-8")
    count = write_faq()
    listed = len(listed_pages())
    print(f"robots.txt, sitemap.xml ({listed} Seiten) und llms.txt geschrieben.")
    print(f"FAQ-Auszeichnung in {count} Seiten gesetzt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
