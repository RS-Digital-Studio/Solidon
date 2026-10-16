"""Der Sprachhinweis der deutschen Startseite im Quelltext der Website.

Herausgelöst aus ``test_website.py`` (Regel 6: keine neue Definition in einer
Datei über 2 000 Zeilen). Wie der Hinweis im Browser wirkt, prüft
``test_website_browser.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent.parent / "website"


#: Die alternativen Sprachfassungen, wie die deutsche Startseite sie selbst
#: im Kopf erklärt — dieselbe Quelle, die Suchmaschinen lesen.
HREFLANG = re.compile(
    r'<link rel="alternate" hreflang="([a-z]{2})" href="https://solidon3d\.de/\1/">'
)


def _language_hint() -> tuple[str, str]:
    """Die deutsche Startseite und ihre Vorlage des Sprachhinweises."""
    page = (WEBSITE / "index.html").read_text(encoding="utf-8")
    templates = re.findall(r"<template data-language-hint>(.*?)</template>", page, re.DOTALL)
    assert len(templates) == 1, "genau eine Vorlage des Sprachhinweises"
    return page, templates[0]


def test_the_german_start_page_offers_every_other_language_in_its_hint() -> None:
    """Der Sprachhinweis führt jede Fassung, die die Seite per ``hreflang``
    anbietet — eine neue Sprache fällt sonst still aus dem Hinweis.

    Jede Fassung trägt ihre Sprache am Element (Vorleser, Silbentrennung),
    ``data-nosnippet`` (ein Crawler mit englischer Browsersprache sähe sonst
    einen englischen Satz oben auf der deutschen Seite als Suchausschnitt),
    einen Verweis auf ihre Startseite und ein Kreuz mit Namen in ihrer Sprache.
    """
    page, template = _language_hint()
    offered = HREFLANG.findall(page.split("</head>", 1)[0])
    assert len(offered) >= 5, f"zu wenige Sprachfassungen im Kopf gefunden: {offered}"

    sections = re.findall(r"<section ([^>]*)>(.*?)</section>", template, re.DOTALL)
    hinted = []
    for attributes, body in sections:
        code = re.search(r'\blang="([a-z]{2})"', attributes)
        assert code, f"Fassung ohne Sprache: {attributes}"
        code = code[1]
        hinted.append(code)
        assert 'class="language-hint"' in attributes, code
        assert "data-nosnippet" in attributes, code
        assert re.search(r'aria-label="[^"]+"', attributes), code
        assert re.search(r"<p>(?:<svg\b.*?</svg>)?[^<]{8,}</p>", body, re.DOTALL), code
        assert re.search(
            rf'<a class="btn" href="/{code}/" hreflang="{code}">Solidon3D [^<]+</a>', body
        ), code
        assert re.search(
            r'<button type="button" class="language-hint-close" aria-label="[^"]+">', body
        ), code
    assert sorted(hinted) == sorted(offered), "jede angebotene Fassung genau einmal"

    skip, template_at, header = (
        page.index('class="skip"'),
        page.index("<template data-language-hint>"),
        page.index("<header"),
    )
    assert skip < template_at < header, "der Sprung an den Inhalt bleibt das erste Ziel"


def test_only_the_german_start_page_carries_the_language_hint() -> None:
    """Nur die deutsche Startseite ist ``x-default`` und Ziel der fremden Presse;
    jede andere Seite ist bereits gewählt worden und bekommt keinen Hinweis."""
    pages = sorted(WEBSITE.rglob("*.html"))
    assert len(pages) > 20, "ohne Seiten prüft dieser Test nichts"
    carriers = [
        page.relative_to(WEBSITE).as_posix()
        for page in pages
        if "language-hint" in page.read_text(encoding="utf-8")
    ]
    assert carriers == ["index.html"]


def test_the_language_hint_never_redirects_and_reports_nothing() -> None:
    """Der Hinweis bietet an, er leitet nicht um: Suchmaschinen, ``hreflang``
    und die Wahl des Lesers brauchen die deutsche Seite unter ihrer Adresse.

    Er meldet auch nichts — gezählt werden nur die Seitenaufrufe, die es
    ohnehin gibt (``stats.php``, Wechsel von der deutschen Startseite). Die
    einzige Ablage ist die Wahl für Deutsch — Schließen oder Wechsel aus einer
    anderen Fassung —, und jeder Zugriff darauf steht in einem ``try``:
    Gesperrter Speicher darf den Hinweis nicht mitnehmen.
    """
    script = (WEBSITE / "site.js").read_text(encoding="utf-8")
    marker = "Der Sprachhinweis der deutschen Startseite."
    assert script.count(marker) == 1
    block = script.split(marker, 1)[1].split("\n})();", 1)[0]

    assert "navigator.languages" in block
    for redirect in ("location.href =", "location.assign", "location.replace", "location ="):
        assert redirect not in block, redirect
    for report in ("sendBeacon", "fetch(", "XMLHttpRequest"):
        assert report not in block, report
    accesses = block.count("localStorage.")
    guarded = len(re.findall(r"try \{\s*(?:if \()?localStorage\.", block))
    assert accesses == guarded == 2, "Lesen und Schreiben, beide in einem try"


def test_the_language_hint_shifts_nothing_and_stays_under_the_header_menus() -> None:
    """Fest gestellt verschiebt die Karte nichts, auch wenn ``site.js`` sie bei
    langsamem Netz erst nach dem ersten Bild einsetzt; unter der Kopfzeile
    gehen deren Menüs über ihr auf, und auf Papier fehlt sie. Im Fluss steht
    sie nur bei wenig Höhe (``test_website_browser.py``)."""
    css = (WEBSITE / "style.css").read_text(encoding="utf-8")
    hint = re.search(r"\n\.language-hint \{([^}]*)\}", css)
    header = re.search(r"\nheader\.site \{([^}]*)\}", css)
    assert hint and header
    assert "position: fixed;" in hint[1]
    z_index = re.compile(r"z-index: (\d+);")
    hint_layer, header_layer = z_index.search(hint[1]), z_index.search(header[1])
    assert hint_layer and header_layer
    assert int(hint_layer[1]) < int(header_layer[1])
    assert re.search(r"@media print \{\s*\.language-hint \{ display: none; \}", css)
