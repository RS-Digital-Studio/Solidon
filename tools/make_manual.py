"""Das Handbuch als Website-Seite und als PDF ausgeben (Bauplan §37.2).

    .venv\\Scripts\\python.exe tools/make_manual.py

Dreimal derselbe Text: im Fenster, auf der Website, im PDF. Es gibt genau eine
Quelle dafür (:mod:`app.core.manual`), und das ist der Punkt — ein Handbuch,
das an drei Stellen gepflegt wird, sagt nach dem zweiten Monat dreierlei.

Was entsteht:

* ``website/handbuch.html`` und ``website/en/manual.html`` — je eine Seite,
  passend zum vorhandenen ``style.css``, ohne JavaScript und ohne fremde
  Ressourcen, wie der Rest der Seite auch.
* ``website/handbuch/`` mit den Abbildungen. Gezeichnetes und Gerendertes als
  SVG, weil es dann in jeder Größe scharf bleibt; die Bildschirmfotos als PNG,
  weil sie nun einmal Pixel sind.
* ``Releases/Formwerk-Handbuch-<sprache>.pdf`` — über Qt gesetzt, damit dafür
  keine Abhängigkeit dazukommt, deren Lizenz erst geprüft werden müsste (§36).

Das PDF braucht Qt und damit die echte Plattform; zu den Schriften unter
``offscreen`` steht alles in ``tools/make_figures.py``.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.branding import APP_NAME
from app.core import figures, manual
from app.core.bootstrap import load_operations
from app.i18n import SUPPORTED_LANGUAGES, install_catalog, set_language, tr
from app.i18n.catalog import read_catalog

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"
RELEASES = ROOT / "Releases"

#: Wie die Handbuchseite je Sprache heißt und wo sie liegt. Der englische Teil
#: der Website wohnt in einem Unterordner, also auch sein Handbuch.
PAGES = {
    "de": ("handbuch.html", "handbuch/de"),
    "en": ("en/manual.html", "../handbuch/en"),
}

STYLE = """
    /* Der Text bleibt schmal, weil sich lange Zeilen schlecht lesen. Die
       Abbildungen dürfen darüber hinausragen: ein Bildschirmfoto auf halbe
       Spaltenbreite gestaucht zeigt Beschriftungen, die niemand mehr liest. */
    main { max-width: 74rem; margin: 0 auto; padding: 2rem 1.25rem 5rem; }
    main > :not(figure) { max-width: 52rem; margin-left: auto; margin-right: auto; }
    h2 { margin-top: 3rem; border-bottom: 1px solid var(--line); padding-bottom: .4rem; }
    h3 { margin-top: 2rem; }
    figure { margin: 2rem auto; text-align: center; max-width: 72rem; }
    figure img { max-width: 100%; height: auto; border-radius: 6px; }
    figcaption { color: var(--muted); font-size: .9rem; margin-top: .5rem; }
    .figure-text { color: var(--muted); font-style: italic; }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .92rem; }
    th, td { border: 1px solid var(--line); padding: .4rem .6rem; text-align: left; }
    th { background: var(--card); }
    code { background: var(--card); padding: .1rem .3rem; border-radius: 3px; }
    nav.toc { background: var(--card); border: 1px solid var(--line);
              border-radius: 8px; padding: 1rem 1.5rem; margin: 2rem 0; }
    nav.toc ul { columns: 2; margin: 0; padding-left: 1.2rem; }
    @media (max-width: 40rem) { nav.toc ul { columns: 1; } }
"""


def write_figures(target: Path, language: str) -> dict[str, str]:
    """Jede Abbildung als Datei ablegen. Liefert die Adressen je Schlüssel."""
    target.mkdir(parents=True, exist_ok=True)
    sources: dict[str, str] = {}
    for figure in figures.FIGURES:
        if figure.kind == "shot":
            source = figure.path(language)
            if not source.is_file():
                print(f"  fehlt: {figure.key} ({source.name}) — tools/make_figures.py läuft nicht?")
                continue
            (target / f"{figure.key}.png").write_bytes(source.read_bytes())
            sources[figure.key] = f"{figure.key}.png"
            continue
        svg = figures.svg(figure.key, "light")
        if svg is None:
            print(f"  fehlt: {figure.key} (lässt sich hier nicht zeichnen)")
            continue
        (target / f"{figure.key}.svg").write_text(svg, encoding="utf-8")
        sources[figure.key] = f"{figure.key}.svg"
    return sources


#: Die Überschrift des Inhaltsverzeichnisses. Nicht über ``tr()``: der
#: Textsammler liest nur ``app/``, und ein Wort, das nur auf der Website
#: vorkommt, gehört nicht in den Katalog der Anwendung — es stünde dort für
#: immer als unübersetzbar herum.
CONTENTS = {"de": "Inhalt", "en": "Contents"}


def contents(language: str) -> str:
    """Ein Inhaltsverzeichnis — bei fünfundzwanzig Kapiteln kein Luxus.

    Die Anker dazu setzt `anchored`; hier steht nur die Liste.
    """
    items = "".join(f'<li><a href="#{page.key}">{page.title}</a></li>' for page in manual.pages())
    heading = CONTENTS.get(language, CONTENTS["de"])
    return f'<nav class="toc"><strong>{heading}</strong><ul>{items}</ul></nav>'


def anchored(html: str) -> str:
    """Jeder Kapitelüberschrift ihren Anker geben, damit das Verzeichnis trägt.

    Die Ebene steht nicht fest: ``core.markup`` rückt Überschriften um eine
    Stufe nach unten, weil die Seite selbst das ``<h1>`` trägt. Ein Anker, der
    auf ``<h2>`` festgenagelt ist, greift dann ins Leere — und das
    Inhaltsverzeichnis führt nirgendwohin, ohne dass es jemand sieht.
    """
    for page in manual.pages():
        pattern = re.compile(rf"<h([1-6])>{re.escape(str(page.title))}</h\1>")
        html = pattern.sub(
            lambda match, key=page.key: (  # type: ignore[misc]
                f'<h{match.group(1)} id="{key}">{match.group(0)[4:-5]}</h{match.group(1)}>'
            ),
            html,
            count=1,
        )
    return html


def page_html(language: str, prefix: str) -> str:
    body = manual.as_html(figure_source=lambda key: f"{prefix}/{key}.{_suffix(key)}")
    title = f"{tr('Handbuch')} — {APP_NAME}"
    # Die Startseite liegt in beiden Sprachen neben ihrem Handbuch.
    home = "index.html"
    return (
        f'<!doctype html>\n<html lang="{language}">\n<head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        f'<link rel="icon" href="{"icon.svg" if language == "de" else "../icon.svg"}" '
        f'type="image/svg+xml">\n'
        f'<link rel="stylesheet" href="{"style.css" if language == "de" else "../style.css"}">\n'
        f"<style>{STYLE}</style>\n</head>\n<body>\n<main>\n"
        f'<p><a href="{home}">← {APP_NAME}</a></p>\n'
        f"<h1>{title}</h1>\n"
        f"{contents(language)}\n"
        f"{anchored(body)}\n"
        f"</main>\n</body>\n</html>\n"
    )


def _suffix(key: str) -> str:
    figure = figures.find(key)
    return "png" if figure is not None and figure.kind == "shot" else "svg"


#: Auflösung, in der das PDF gesetzt wird. Nicht die höchstmögliche, sondern
#: die, in der eine Schriftgröße dasselbe bedeutet wie auf dem Bildschirm:
#: ``QTextDocument`` rechnet in Pixeln, und bei 1200 dpi ist eine
#: Zwölf-Pixel-Schrift auf einer A4-Seite ein Staubkorn. Der erste Versuch
#: brachte das ganze Handbuch auf zwei Seiten unter, lesbar unter der Lupe.
PDF_RESOLUTION = 96

#: Seitenrand in Millimetern.
PDF_MARGIN = 18.0


def write_pdf(language: str, folder: Path) -> Path:
    """Das Handbuch setzen und als PDF ablegen."""
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    RELEASES.mkdir(parents=True, exist_ok=True)
    target = RELEASES / f"{APP_NAME}-Handbuch-{language}.pdf"

    writer = QPdfWriter(str(target))
    writer.setResolution(PDF_RESOLUTION)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(
        QMarginsF(PDF_MARGIN, PDF_MARGIN, PDF_MARGIN, PDF_MARGIN),
        QPageLayout.Unit.Millimeter,
    )
    writer.setTitle(f"{tr('Handbuch')} — {APP_NAME}")

    document = QTextDocument()
    # Damit die Bilder gefunden werden: die Verweise im HTML sind relativ.
    document.setBaseUrl(folder.as_uri() + "/")
    document.setPageSize(QSizeF(writer.width(), writer.height()))
    body = manual.as_html(figure_source=lambda key: f"{key}.{_suffix(key)}")
    document.setHtml(
        f"<h1>{tr('Handbuch')} — {APP_NAME}</h1>" + _sized(body, folder, writer.width())
    )
    document.print_(writer)
    return target


def _sized(html: str, folder: Path, page_width: int) -> str:
    """Jedem Bild eine Breite geben, die auf die Seite passt.

    ``QTextDocument`` versteht kein ``max-width``: ohne Angabe zeichnet es
    jedes Bild in seiner natürlichen Größe, und ein Bildschirmfoto von 1180
    Pixeln steht dann zur Hälfte außerhalb der Seite. Kleinere Bilder werden
    nicht aufgeblasen — eine gestreckte Vorschau wäre schlechter als eine
    kleine.
    """
    from PySide6.QtGui import QImageReader

    def add_width(match: re.Match[str]) -> str:
        name = match.group(1)
        natural = QImageReader(str(folder / name)).size().width()
        width = min(natural, page_width) if natural > 0 else page_width
        return f'<img width="{width}" src="{name}"'

    return re.sub(r'<img src="([^"]+)"', add_width, html)


def main() -> int:
    load_operations()
    for language in SUPPORTED_LANGUAGES:
        install_catalog(language, read_catalog(language))
        set_language(language)
        figures.forget()
        print(f"{language}:")

        name, prefix = PAGES[language]
        # Je Sprache ein eigener Ordner: die Beschriftungen stecken in den
        # Zeichnungen, also ist ein deutsches Bild kein englisches.
        folder = WEBSITE / "handbuch" / language
        sources = write_figures(folder, language)
        print(f"  {len(sources)} Abbildungen → {folder.relative_to(ROOT)}")

        target = WEBSITE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page_html(language, prefix), encoding="utf-8")
        print(f"  Seite → {target.relative_to(ROOT)}")

        pdf = write_pdf(language, folder)
        if pdf is not None:
            size = pdf.stat().st_size / 1024
            print(f"  PDF → {pdf.relative_to(ROOT)} ({size:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
