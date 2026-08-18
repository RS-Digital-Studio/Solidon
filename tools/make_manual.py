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
* ``Releases/Solidon-Handbuch-<sprache>.pdf`` — über Qt gesetzt, damit dafür
  keine Abhängigkeit dazukommt, deren Lizenz erst geprüft werden müsste (§36).

Das PDF braucht Qt und damit die echte Plattform; zu den Schriften unter
``offscreen`` steht alles in ``tools/make_figures.py``.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.branding import APP_NAME, APP_VENDOR, APP_VERSION, COPYRIGHT, WEBSITE_URL
from app.core import figures, manual
from app.core.bootstrap import load_operations
from app.i18n import install_catalog, set_language, tr
from app.i18n.catalog import available_languages, read_catalog

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"
RELEASES = ROOT / "Releases"

#: Wie die Handbuchseite je Sprache heißt und wo sie liegt. Deutsch ist die
#: Wurzel der Website, jede andere Sprache wohnt in ihrem eigenen Unterordner
#: — also auch ihr Handbuch.
PAGES = {
    "de": ("handbuch.html", "handbuch/de"),
    "en": ("en/manual.html", "../handbuch/en"),
    "es": ("es/manual.html", "../handbuch/es"),
    "fr": ("fr/manual.html", "../handbuch/fr"),
    "it": ("it/manual.html", "../handbuch/it"),
    "pt": ("pt/manual.html", "../handbuch/pt"),
}


def page_for(language: str) -> tuple[str, str]:
    """Zielseite und Bildpfad einer Sprache.

    Eine Sprache, die noch keinen Eintrag hat, bekommt den Ort, den sie nach
    demselben Muster hätte — sonst stünde die Sprachauswahl in der Anwendung
    schon offen, während der Handbuchbauer beim ersten neuen Kürzel mit einem
    ``KeyError`` abbricht.
    """
    if language in PAGES:
        return PAGES[language]
    return f"{language}/manual.html", f"../handbuch/{language}"


STYLE = """
    /* Der Text bleibt schmal, weil sich lange Zeilen schlecht lesen. Die
       Abbildungen dürfen darüber hinausragen: ein Bildschirmfoto auf halbe
       Spaltenbreite gestaucht zeigt Beschriftungen, die niemand mehr liest. */
    main { max-width: 74rem; margin: 0 auto; padding: 2rem 1.25rem 5rem;
           counter-reset: chapter; }
    main > :not(figure) { max-width: 52rem; margin-left: auto; margin-right: auto; }
    /* Der Einstieg: derselbe Ton wie der Aufmacher der Startseite, eine
       Nummer kleiner — das Handbuch verkauft nicht, es empfängt. */
    main > h1 { font-size: clamp(2rem, 4vw, 2.6rem); letter-spacing: -0.015em;
                margin: 1.6rem auto 0.4rem; }
    p.lede { color: var(--muted); font-size: 1.12rem; margin-bottom: 2rem; }
    /* Die Kapitelüberschrift trägt die Akzentfarbe — dieselbe, die in der
       Anwendung den Hauptknopf und die aktive Karte kennzeichnet. Sie ist
       das, woran man beim Blättern die Gliederung erkennt. Die Nummer davor
       ist dieselbe wie im Verzeichnis: was dort eine Stelle hat, hat sie
       auch im Text.

       Erkannt wird ein Kapitel an seinem Anker, nicht an der Ebene:
       ``core.markup`` rückt Überschriften eine Stufe nach unten, die Kapitel
       stehen als ``<h3>`` da — ein Stil, der auf ``h2`` festgenagelt wäre,
       griffe ins Leere, und genau das tat der alte (siehe ``anchored``). */
    main > h2[id], main > h3[id] {
      margin-top: 3.2rem; color: var(--accent); font-size: 1.45rem;
      border-bottom: 1px solid var(--line); padding-bottom: .4rem;
      counter-increment: chapter;
    }
    main > h2[id]::before, main > h3[id]::before {
      content: counter(chapter, decimal-leading-zero);
      font-size: .68em; font-weight: 600; color: var(--muted);
      margin-right: .8rem; font-variant-numeric: tabular-nums;
    }
    h3 { margin-top: 2rem; }
    figure { margin: 2rem auto; text-align: center; max-width: 72rem; }
    figure img { max-width: 100%; height: auto; border-radius: 6px; }
    figcaption { color: var(--muted); font-size: .9rem; margin-top: .5rem; }
    /* Die Bildschirmfotos liegen auf derselben dunklen Bühne wie auf der
       Startseite — ``.stage`` samt Streiflicht kommt aus ``style.css``, hier
       steht nur, was im Handbuch anders ist: ``figure`` zentriert schon,
       also braucht die Bühne keinen eigenen Abstand nach oben. */
    figure.screenshot .stage { margin: 0; }

    /* Die Abbildungen steigen beim Lesen ein Stück auf — dieselbe Geste wie
       auf der Startseite, hinter demselben ``@supports``: wo der Browser die
       Zeitachse nicht kennt, steht alles vollständig da. */
    @supports (animation-timeline: view()) {
      @media (prefers-reduced-motion: no-preference) {
        main figure { animation: rise linear both; animation-timeline: view();
                      animation-range: entry 5% cover 18%; }
      }
    }
    .figure-text { color: var(--muted); font-style: italic; }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .92rem; }
    /* Eine Tabelle mit sieben Spalten passt auf kein Telefon, und sie soll es
       auch nicht: die Materialtabelle ist eine Tabelle, kein Fließtext. Sie
       bekommt deshalb ihren eigenen Rollbereich, statt die Seite zu sprengen
       — gemessen ließ sich das Handbuch bei 375 px Bildbreite um 270 Pixel
       nach rechts schieben, weil die breiteste Tabelle 645 px maß.
       ``display: block`` ist der Preis dafür, dass hier kein Wrapper um jede
       Tabelle steht; die Spalten bleiben lesbar, weil ``white-space: nowrap``
       nur die Kopfzeile trifft. */
    table { display: block; overflow-x: auto; max-width: 100%; }
    thead th { white-space: nowrap; }
    th, td { border: 1px solid var(--line); padding: .4rem .6rem; text-align: left; }
    th { background: var(--card); }
    code { background: var(--card); padding: .1rem .3rem; border-radius: 3px; }
    /* Das Verzeichnis: gezählt, zweispaltig, ohne Aufzählungspunkte. Die
       Nummer trägt die Akzentfarbe und steht auf fester Breite, damit die
       Titel eine gemeinsame Kante haben — daran liest man eine Liste
       entlang, nicht an achtundzwanzig einzelnen Zeilen. */
    nav.toc { background: var(--card); border: 1px solid var(--line);
              border-radius: 10px; padding: 1.4rem 1.8rem 1.6rem; margin: 2.5rem 0; }
    nav.toc .toc-title { margin: 0 0 1rem; border: none; padding: 0;
                         font-size: 1.1rem; letter-spacing: .02em; }
    /* ``style.css`` nummeriert das Verzeichnis der Funktionsseite über
       einen Zähler und legt es als Raster an. Hier trägt jeder Eintrag
       seine Kapitelnummer schon im Markup, und die Spalten füllen sich
       der Reihe nach — beides ausdrücklich abschalten, sonst stehen zwei
       Nummern nebeneinander. */
    nav.toc ol { columns: 2; column-gap: 2.5rem; margin: 0; padding: 0;
                 list-style: none; counter-reset: none; display: block; }
    nav.toc a::before { content: none; }
    nav.toc li { break-inside: avoid; margin: 0; }
    nav.toc a { display: flex; gap: .7rem; align-items: baseline;
                padding: .28rem 0; border-bottom: 1px solid var(--line);
                text-decoration: none; color: var(--fg); font-size: .95rem; }
    nav.toc li:last-child a { border-bottom: none; }
    /* Die Fuge zwischen den geschriebenen Kapiteln und der Referenz —
       gedämpft, weil sie ordnet und nicht ruft. */
    nav.toc .toc-divider { margin: 1.6rem 0 .8rem; border: none; padding: 0;
                           font-size: .92rem; color: var(--muted);
                           font-weight: 600; letter-spacing: .02em; }
    nav.toc a:hover { color: var(--accent); }
    nav.toc .num { color: var(--accent); font-size: .82rem; font-weight: 600;
                   min-width: 1.6rem; font-variant-numeric: tabular-nums; }
    @media (max-width: 40rem) { nav.toc ol { columns: 1; } }

    /* Das Deckblatt gehört dem Papier. Auf der Website steht der Titel schon
       in der Kopfzeile, ein zweiter wäre eine Dopplung. */
    .cover { display: none; }

    /* --- Papier ---------------------------------------------------------
       Dieselbe Seite, gedruckt. Chromium setzt sie über diese Regeln; was
       hier steht, ist der Unterschied zwischen Bildschirm und Blatt und
       nicht eine zweite Gestaltung. */
    @page { size: A4; margin: 18mm 16mm; }

    @media print {
      /* Gedruckt wird auf Weiß, auch wenn der Leser dunkel eingestellt hat. */
      :root { --bg: #ffffff; --fg: #1c1b1a; --muted: #5f5b55;
              --accent: #a4551e; --card: #f7f6f3; --line: #e0ddd7; }
      body { background: #fff; color: var(--fg); font-size: 10.5pt; line-height: 1.45; }
      main { max-width: none; padding: 0; }
      main > :not(figure) { max-width: none; }
      .no-print { display: none !important; }

      /* Die dunkle Bühne bleibt am Bildschirm: gedruckt wäre sie eine
         Tonerfläche um jedes Bildschirmfoto. */
      figure.screenshot .stage { background: none; border: none; padding: 0;
                                 box-shadow: none; border-radius: 0; }
      /* Die Kapitelnummer bleibt ebenfalls am Bildschirm: der Kolumnentitel
         des PDF erkennt ein Kapitel an seiner Titelzeile, und eine Nummer
         davor macht aus „Die vier Wege" eine Zeile, die niemand erwartet
         (siehe ``_chapter_of_each_page``). */
      main > h2[id]::before, main > h3[id]::before { content: none; }

      .cover { display: flex; flex-direction: column; justify-content: center;
               min-height: 84vh; break-after: page; }
      .cover h1 { font-size: 40pt; margin: 0 0 .2em; border: none; }
      .cover .subtitle { font-size: 20pt; color: var(--accent); margin: 0 0 1.2rem; }
      .cover hr { border: none; border-top: 2px solid var(--line); margin: 0 0 1.2rem; }
      .cover .claim { font-size: 11pt; color: var(--muted); margin: 0; }
      .cover .imprint { margin-top: auto; font-size: 9.5pt; color: var(--muted); }

      nav.toc { break-after: page; background: none; border: none;
                border-radius: 0; padding: 0; margin: 0; }
      nav.toc .toc-title { font-size: 18pt; margin-bottom: 1.2rem; }
      nav.toc ol { columns: 2; column-gap: 2rem; }
      nav.toc a { color: var(--fg); font-size: 9.5pt; padding: .22rem 0; }

      /* Eine Überschrift steht nie allein am Fuß, und ein Bild wird nie
         zwischen zwei Blättern zerschnitten — das war der auffälligste
         Fehler des alten Satzes. */
      /* Nur der Referenzteil beginnt je Kapitel auf einem neuen Blatt: dort
         schlägt jemand nach, und ein Kapitel, das mitten auf der Seite
         anfängt, findet er nicht. Die Einführung liest man am Stück —
         achtundzwanzig erzwungene Umbrüche wären achtundzwanzig halb leere
         Seiten für nichts. */
      h2 { break-after: avoid; margin-top: 2.2rem; color: var(--accent); }
      /* Beide Ebenen, aus demselben Grund wie am Bildschirm: die Kapitel
         stehen als ``<h3>`` da, und ein ``h2.chapter`` allein griffe nie. */
      h2.chapter, h3.chapter { break-before: page; margin-top: 0; }
      h3 { break-after: avoid; }
      figure { break-inside: avoid; margin: 1.2rem auto; }
      /* Höher als das hier passt ein Bildschirmfoto kaum je noch neben Text
         auf ein Blatt — es rutscht dann allein auf die nächste Seite und
         lässt die vorige halb leer. */
      /* Neun Zentimeter für ein Bildschirmfoto: hoch genug, dass die Leiste
         und der Prüfbericht lesbar bleiben, und niedrig genug, dass Text
         darüber und darunter auf dasselbe Blatt passt. Bei elf blieb unter
         zwei Absätzen kein Platz mehr für das nächste Bild, und die halbe
         Seite blieb leer. */
      figure img { max-width: 100%; max-height: 9cm; width: auto; }
      figcaption { break-before: avoid; }

      /* Die gezeichneten Abbildungen stehen im Text statt über ihm: der
         Absatz füllt, was das Bild übrig lässt, und es entsteht keine halbe
         Leerseite. Genau dafür gibt es den Satzspiegel. Achtundvierzig
         Prozent, nicht vierzig — bei vierzig war die Bemaßung mancher
         Zeichnung nicht mehr zu entziffern. */
      figure.drawing { float: right; width: 48%; margin: .2rem 0 .8rem 1.6rem;
                       text-align: center; }
      figure.drawing img { max-height: 8.5cm; }
      figure.drawing + p { margin-top: 0; }
      /* Eine Überschrift beginnt wieder an der vollen Breite — sonst
         schmiegt sich das nächste Kapitel an eine Zeichnung des vorigen. */
      h2, h3 { clear: both; }
      table, pre, li { break-inside: avoid; }
      p { orphans: 3; widows: 3; }
      a { color: var(--fg); text-decoration: none; }
    }
"""


def write_figures(target: Path, language: str) -> tuple[dict[str, str], dict[str, str]]:
    """Jede Abbildung als Datei ablegen. Liefert die Adressen je Schlüssel.

    Zurück kommen zwei Zuordnungen: die gewöhnlichen Quellen und die für ein
    dunkles Farbschema. Gezeichnet wird beides, weil ``core.drawing`` beide
    Paletten kennt — die dunkle Fassung blieb bis dahin ungenutzt, und im
    Dunkelmodus standen zwanzig weiße Kästen in einer dunklen Seite.
    """
    target.mkdir(parents=True, exist_ok=True)
    sources: dict[str, str] = {}
    dark_sources: dict[str, str] = {}
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

        dark = figures.svg(figure.key, "dark")
        if dark is not None:
            (target / f"{figure.key}-dark.svg").write_text(dark, encoding="utf-8")
            dark_sources[figure.key] = f"{figure.key}-dark.svg"
    return sources, dark_sources


#: Die Überschrift des Inhaltsverzeichnisses. Nicht über ``tr()``: der
#: Textsammler liest nur ``app/``, und ein Wort, das nur auf der Website
#: vorkommt, gehört nicht in den Katalog der Anwendung — es stünde dort für
#: immer als unübersetzbar herum.
CONTENTS = {
    "de": "Inhalt",
    "en": "Contents",
    "es": "Índice",
    "fr": "Sommaire",
    "it": "Indice",
    "pt": "Índice",
}

#: Die Zwischenüberschrift im Verzeichnis, dort wo die geschriebenen Kapitel
#: enden und die aus dem Register erzeugten beginnen.
#:
#: Ohne sie war das Verzeichnis eine flache Liste von vierzig Einträgen, in
#: der „Meldungen im Wortlaut" und „Szene, Reparatur, Transformation" ohne
#: Fuge aufeinander folgten — erzählte Seiten und Nachschlagewerk sahen gleich
#: aus. Nicht über ``tr()``, aus demselben Grund wie :data:`CONTENTS`.
REFERENCE_HEADING = {
    "de": "Referenz — jede Operation mit ihren Werten",
    "en": "Reference — every operation with its values",
    "es": "Referencia — cada operación con sus valores",
    "fr": "Référence — chaque opération avec ses valeurs",
    "it": "Riferimento — ogni operazione con i suoi valori",
    "pt": "Referência — cada operação com os seus valores",
}

#: Die Adresse, unter der die Seiten liegen — für canonical, hreflang und die
#: Vorschau beim Teilen. Aus ``branding.WEBSITE_URL``, damit sie an einer
#: Stelle steht.
SITE = WEBSITE_URL

#: Was eine Suchmaschine und eine geteilte Vorschau vom Handbuch zeigen. Nicht
#: über ``tr()``, aus demselben Grund wie ``CONTENTS``.
DESCRIPTION = {
    "de": "Das Handbuch zu Solidon3D: {pages} Kapitel von den ersten fünfzehn Minuten "
    "bis zu jeder Operation mit ihren Werten und Bereichen. Die Referenzhälfte "
    "kommt aus demselben Register wie die Menüs.",
    "en": "The Solidon3D manual: {pages} chapters, from the first fifteen minutes to "
    "every operation with its values and ranges. The reference half comes from "
    "the same registry as the menus.",
    "es": "El manual de Solidon3D: {pages} capítulos, desde los primeros quince "
    "minutos hasta cada operación con sus valores y rangos. La mitad de "
    "referencia sale del mismo registro que los menús.",
    "fr": "Le manuel de Solidon3D : {pages} chapitres, des quinze premières minutes "
    "à chaque opération avec ses valeurs et ses plages. La moitié de référence "
    "vient du même registre que les menus.",
    "it": "Il manuale di Solidon3D: {pages} capitoli, dai primi quindici minuti a "
    "ogni operazione con i suoi valori e intervalli. La metà di riferimento "
    "viene dallo stesso registro dei menu.",
    "pt": "O manual do Solidon3D: {pages} capítulos, dos primeiros quinze minutos "
    "a cada operação com os seus valores e intervalos. A metade de referência "
    "vem do mesmo registo que os menus.",
}

#: Die Texte des Deckblatts, aus demselben Grund nicht über ``tr()``.
COVER = {
    "de": ("Handbuch", "Konstruieren, Erzeugen und Bearbeiten für den 3D-Druck", "Version"),
    "en": ("Manual", "Design, generate and prepare for 3D printing", "Version"),
    "es": ("Manual", "Construir, generar y preparar para la impresión 3D", "Versión"),
    "fr": ("Manuel", "Concevoir, générer et préparer pour l'impression 3D", "Version"),
    "it": ("Manuale", "Costruire, generare e preparare per la stampa 3D", "Versione"),
    "pt": ("Manual", "Construir, gerar e preparar para a impressão 3D", "Versão"),
}

#: Die Kopfzeile der Seite — dieselbe wie auf der Startseite, damit das
#: Handbuch als Teil des Auftritts gelesen wird und nicht als Anhang. Je
#: Sprache: Verzeichnis-Link, Sprachwechsel (Text und Ziel) und der Knopf
#: zur Startseite mit ihrer Preis-Sprungmarke. Nicht über ``tr()``, aus
#: demselben Grund wie ``CONTENTS``.
HEADER_NAV = {
    "de": ("Inhalt", "Testen", "index.html#preis"),
    "en": ("Contents", "Try it", "index.html#pricing"),
    "es": ("Índice", "Probar", "index.html#pricing"),
    "fr": ("Sommaire", "Essayer", "index.html#pricing"),
    "it": ("Indice", "Prova", "index.html#pricing"),
    "pt": ("Índice", "Experimentar", "index.html#pricing"),
}

#: Der Satz unter dem Titel. Er sagt in einer Zeile, was die Seite ist und
#: woher sie kommt — nicht über ``tr()``, wie alles hier.
LEDE = {
    "de": "{pages} Kapitel — von den ersten fünfzehn Minuten bis zur Referenz "
    "jeder Operation, erzeugt aus derselben Quelle wie das Handbuch in der "
    "Anwendung.",
    "en": "{pages} chapters — from the first fifteen minutes to the reference "
    "of every operation, generated from the same source as the manual inside "
    "the application.",
    "es": "{pages} capítulos — desde los primeros quince minutos hasta la "
    "referencia de cada operación, generados de la misma fuente que el manual "
    "dentro de la aplicación.",
    "fr": "{pages} chapitres — des quinze premières minutes à la référence de "
    "chaque opération, générés depuis la même source que le manuel dans "
    "l'application.",
    "it": "{pages} capitoli — dai primi quindici minuti al riferimento di ogni "
    "operazione, generati dalla stessa fonte del manuale nell'applicazione.",
    "pt": "{pages} capítulos — dos primeiros quinze minutos à referência de "
    "cada operação, gerados da mesma fonte que o manual dentro da aplicação.",
}

#: Das Markenzeichen der Kopfzeile, identisch mit der Startseite.
BRAND_MARK = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
    'aria-hidden="true">'
    '<path d="M12 2.6 21 7.5v9L12 21.4 3 16.5v-9z" stroke-linejoin="round"/>'
    '<path d="M3 7.5 12 12.4l9-4.9M12 12.4v9" stroke-linejoin="round"/>'
    "</svg>"
)


def _switch_target(current: str, other: str) -> str:
    """Wo das Handbuch der anderen Sprache liegt, von der aktuellen aus.

    Deutsch wohnt in der Wurzel, jede andere Sprache in ihrem Ordner — die
    Pfade sind also relativ verschieden, je nachdem, wo man steht.
    """
    if current == "de":
        return "handbuch.html" if other == "de" else f"{other}/manual.html"
    return "../handbuch.html" if other == "de" else f"../{other}/manual.html"


#: Sprachnamen und Menü-Beschriftung des Sprachwechsels, je in der eigenen
#: Sprache — wer Deutsch nicht liest, findet seinen Eintrag trotzdem.
LANGUAGE_NAMES = {
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "pt": "Português",
}
SWITCHER_LABELS = {
    "de": "Sprache wählen",
    "en": "Choose language",
    "es": "Elegir idioma",
    "fr": "Choisir la langue",
    "it": "Scegli la lingua",
    "pt": "Escolher idioma",
}


def _switcher(language: str) -> str:
    """Der Sprachwechsel als Aufklappmenü — zu sehen ist das eigene Kürzel,
    offen stehen alle sechs Sprachen ausgeschrieben.

    ``details`` braucht kein Skript; dasselbe Markup tragen die statischen
    Seiten, die Stile wohnen in ``style.css`` unter ``details.langs``.
    """
    rows = "".join(
        f'<li><a href="{_switch_target(language, other)}" hreflang="{other}" lang="{other}"'
        + (' aria-current="page"' if other == language else "")
        + f">{LANGUAGE_NAMES[other]}</a></li>"
        for other in sorted(PAGES)
    )
    return (
        '<details class="langs">'
        f'<summary aria-label="{SWITCHER_LABELS[language]}">{language.upper()}</summary>'
        f"<ul>{rows}</ul></details>"
    )


def _header(language: str) -> str:
    """Die Kopfzeile — am Bildschirm klebt sie oben, im Druck fehlt sie."""
    toc_label, cta_label, cta_target = HEADER_NAV.get(language, HEADER_NAV["de"])
    return (
        '<header class="site no-print"><div class="wrap">'
        f'<a class="brand" href="index.html">{BRAND_MARK}Solidon<span>3D</span></a>'
        '<nav class="lang">'
        f'<a href="#toc">{toc_label}</a>'
        f"{_switcher(language)}"
        f'<a class="cta" href="{cta_target}">{cta_label}</a>'
        "</nav></div></header>"
    )


#: Seitenränder des Drucks in Millimetern. Sie stehen hier und nicht im CSS:
#: ``printToPdf`` mit einem Layout schlägt jedes ``@page`` im Stylesheet.
PDF_MARGIN_SIDE = 18.0
PDF_MARGIN_TOP = 16.0

#: Wie die Fußzeile die Seite zählt.
PAGE_OF = {
    "de": "Seite {page} von {total}",
    "en": "Page {page} of {total}",
    "es": "Página {page} de {total}",
    "fr": "Page {page} sur {total}",
    "it": "Pagina {page} di {total}",
    "pt": "Página {page} de {total}",
}

#: Die Farben des hellen Themas (``website/style.css``). Gedruckt wird auf
#: Papier, also gilt hell — und es sind dieselben Werte, mit denen die
#: Anwendung arbeitet, kein zweiter Satz daneben.
PDF_MUTED = "#5f5b55"
PDF_ACCENT = "#a4551e"
PDF_LINE = "#d8d4cd"


def _anchor(page: manual.Page) -> str:
    """Der Anker einer Seite — für erzeugte Kapitel mit Vorsatz.

    Der Seitenschlüssel allein reicht nicht: die geschriebene Seite „Die
    Bausteine" und das erzeugte Kapitel „Bausteine" heißen beide ``parts``,
    und zwei gleiche ``id`` in einer Seite sind ungültiges HTML. Der Browser
    springt dann bei beiden Verzeichniseinträgen an dieselbe Stelle — auf
    die erste, und das ist die falsche.

    Der Vorsatz sitzt am Anker und nicht am Schlüssel: ``manual.find`` führt
    von einer Operation in ihr Kapitel und erwartet den Kategorienamen.
    """
    return f"ref-{page.key}" if page.generated else page.key


def contents(language: str) -> str:
    """Ein Inhaltsverzeichnis — bei dreiunddreißig Kapiteln kein Luxus.

    Mit gezählten Kapiteln und zweispaltig: eine Punktliste über
    dreiunddreißig Zeilen ist eine Aufzählung, kein Verzeichnis — man findet
    darin nichts wieder, weil nichts eine Stelle hat. Die Nummer gibt jedem
    Kapitel eine.

    Die Anker dazu setzt `anchored`; hier steht nur die Liste.
    """

    def entry(number: int, page: manual.Page) -> str:
        return (
            f'<li><a href="#{_anchor(page)}">'
            f'<span class="num">{number:02d}</span>{page.title}</a></li>'
        )

    pages = list(manual.pages())
    written = [(number, page) for number, page in enumerate(pages, start=1) if not page.generated]
    generated = [(number, page) for number, page in enumerate(pages, start=1) if page.generated]

    heading = CONTENTS.get(language, CONTENTS["de"])
    blocks = [f'<h2 class="toc-title">{heading}</h2>']
    blocks.append("<ol>" + "".join(entry(number, page) for number, page in written) + "</ol>")
    if generated:
        # Die Fuge, an der aus Lesen Nachschlagen wird. Die Nummern laufen
        # durch: sie stehen so auch über den Kapiteln selbst.
        divider = REFERENCE_HEADING.get(language, REFERENCE_HEADING["de"])
        blocks.append(f'<h3 class="toc-divider">{divider}</h3>')
        blocks.append(
            f'<ol start="{generated[0][0]}">'
            + "".join(entry(number, page) for number, page in generated)
            + "</ol>"
        )
    return f'<nav class="toc" id="toc">{"".join(blocks)}</nav>'


def anchored(html: str) -> str:
    """Jeder Kapitelüberschrift ihren Anker geben, damit das Verzeichnis trägt.

    Die Ebene steht nicht fest: ``core.markup`` rückt Überschriften um eine
    Stufe nach unten, weil die Seite selbst das ``<h1>`` trägt. Ein Anker, der
    auf ``<h2>`` festgenagelt ist, greift dann ins Leere — und das
    Inhaltsverzeichnis führt nirgendwohin, ohne dass es jemand sieht.
    """
    for page in manual.pages():
        # Erzeugte Kapitel bekommen zusätzlich eine Klasse: im Druck fängt
        # der Referenzteil je Kapitel auf einem neuen Blatt an, die
        # Einführung liest man am Stück (siehe ``@media print``).
        css = ' class="chapter"' if page.generated else ""
        anchor = _anchor(page)
        pattern = re.compile(rf"<h([1-6])>{re.escape(str(page.title))}</h\1>")
        html = pattern.sub(
            lambda match, key=anchor, css=css: (  # type: ignore[misc]
                f'<h{match.group(1)} id="{key}"{css}>{match.group(0)[4:-5]}</h{match.group(1)}>'
            ),
            html,
            count=1,
        )
    return html


def _classify(html: str) -> str:
    """Jeder Abbildung ansehen, wie breit sie gesetzt werden will.

    Die Unterscheidung steht schon im Katalog, sie muss nur benutzt werden.
    Ein **gerendertes** Bild zeigt einen Körper — eine Mutternfalle, ein
    Filmscharnier, eine Bohrung vorher und nachher. Das ist kompakt und
    verträgt die halbe Spalte; der Absatz fließt daneben, und es entsteht
    keine halbe Leerseite.

    Eine **Zeichnung** ist ein Schema mit Beschriftung — die drei Zonen des
    Fensters, die drei Wege, der Stapel. Halbiert wird ihre Schrift zu klein,
    und ein Schema, dessen Beschriftung man nicht liest, erklärt nichts.
    Ebenso die Bildschirmfotos. Beide bleiben über die volle Textbreite.
    """
    compact = {entry.key for entry in figures.FIGURES if entry.kind == "rendered"}

    def widen(match: re.Match[str]) -> str:
        opening, name = match.group(1), match.group(2)
        key = name.rsplit("/", 1)[-1].rsplit(".", 1)[0].removesuffix("-dark")
        css = ' class="drawing"' if key in compact else ""
        return f"<figure{css}>{opening}"

    # Eine themenfähige Abbildung steht als ``<figure><picture><source …>``
    # da; der Schlüssel ist dann in der ersten Quelle zu finden, nicht im
    # ``<img>``. Beide Formen werden erkannt.
    return re.sub(r'<figure>(<(?:picture><source srcset|img src)="([^"]+)")', widen, html)


def page_html(language: str, prefix: str) -> str:
    body = _classify(
        manual.as_html(
            figure_source=lambda key: f"{prefix}/{key}.{_suffix(key)}",
            dark_source=lambda key: "" if _suffix(key) == "png" else f"{prefix}/{key}-dark.svg",
        )
    )
    # Die Bildschirmfotos bekommen die Bühne der Startseite. Erkannt werden
    # sie an ihrer Endung: nur Aufnahmen sind PNG, alles Gezeichnete und
    # Gerenderte reist als SVG und bleibt ohne Bühne — ein Schema auf
    # dunklem Grund hat seinen Grund schon selbst.
    body = re.sub(
        r'<figure><img (src="[^"]+\.png"[^>]*)>',
        r'<figure class="screenshot"><div class="stage"><img \1></div>',
        body,
    )
    title = f"{tr('Handbuch')} — {APP_NAME}"
    pages = len(manual.pages())
    description = DESCRIPTION[language].format(pages=pages)
    lede = LEDE.get(language, LEDE["de"]).format(pages=pages)
    canonical = f"{SITE}{page_for(language)[0]}"
    # Jede Sprache nennt jede — sechs Zeilen aus derselben Tabelle, die auch
    # die Seiten baut, statt zweier von Hand gepflegter.
    alternates = "".join(
        f'<link rel="alternate" hreflang="{code}" href="{SITE}{page_for(code)[0]}">\n'
        for code in sorted(PAGES)
    )
    return (
        f'<!doctype html>\n<html lang="{language}">\n<head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        # Das Handbuch ist die zweitwichtigste Seite und war die einzige ohne
        # Auszeichnung: geteilt wurde sie als nackter Link, und eine Suche fand
        # sie über nichts als ihren Titel.
        f'<meta name="description" content="{description}">\n'
        f'<link rel="canonical" href="{canonical}">\n'
        f"{alternates}"
        f'<link rel="alternate" hreflang="x-default" href="{SITE}handbuch.html">\n'
        f'<meta property="og:type" content="article">\n'
        f'<meta property="og:site_name" content="{APP_NAME}">\n'
        f'<meta property="og:url" content="{canonical}">\n'
        f'<meta property="og:title" content="{title}">\n'
        f'<meta property="og:description" content="{description}">\n'
        f'<meta property="og:image" content="{SITE}handbuch/{language}/main-window.png">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f'<link rel="icon" href="{"icon.svg" if language == "de" else "../icon.svg"}" '
        f'type="image/svg+xml">\n'
        f'<link rel="stylesheet" href="{"style.css" if language == "de" else "../style.css"}">\n'
        f"<style>{STYLE}</style>\n</head>\n<body>\n"
        f"{_header(language)}\n<main>\n"
        f"{_cover_block(language)}\n"
        f'<h1 class="no-print">{tr("Handbuch")}</h1>\n'
        f'<p class="lede no-print">{lede}</p>\n'
        f"{contents(language)}\n"
        f"{anchored(body)}\n"
        f"</main>\n</body>\n</html>\n"
    )


def _cover_block(language: str) -> str:
    """Das Deckblatt — im Druck die erste Seite, am Bildschirm ausgeblendet.

    Es steht im HTML und nicht in einem eigenen Setzlauf, weil es sonst eine
    zweite Quelle wäre: ein Titel, der sich ändert, müsste an zwei Stellen
    nachgezogen werden, und die zweite vergisst man.
    """
    title, subtitle, version_word = COVER.get(language, COVER["de"])
    return (
        f'<section class="cover">'
        f"<h1>{APP_NAME}</h1>"
        f'<p class="subtitle">{title}</p>'
        f"<hr>"
        f'<p class="claim">{subtitle}</p>'
        f'<p class="imprint">{version_word} {APP_VERSION}<br>{COPYRIGHT}</p>'
        f"</section>"
    )


def _suffix(key: str) -> str:
    figure = figures.find(key)
    return "png" if figure is not None and figure.kind == "shot" else "svg"


def write_pdf(language: str, page_file: Path) -> Path:
    """Das Handbuch als PDF — gedruckt aus derselben Seite, die im Web steht.

    **Warum nicht mit** ``QTextDocument``. Das war der Weg bis hierher, und er
    hat drei Dinge nicht hinbekommen, die ein Handbuch braucht. ``<figure>``
    ist HTML5, Qt kennt es nicht und hängt das Bild an den Textfluss daneben —
    im PDF stand mitten in einem Satz eine Zeichnung. Ein Bild, das nicht mehr
    auf die Seite passt, wird nicht umbrochen, sondern überschritt den Rand.
    Und beim seitenweisen Zeichnen landete das Inhaltsverzeichnis zwar im
    Text des PDF, aber außerhalb des gezeichneten Ausschnitts: lesbar für die
    Textsuche, unsichtbar auf dem Blatt.

    Chromium kann all das, und es kann es mit **demselben** Stylesheet, das
    die Website benutzt. Damit ist das PDF keine zweite Gestaltung mehr, die
    hinter der ersten herhinkt, sondern dieselbe Seite auf Papier.

    Was dabei verloren geht, sind **Seitenzahlen**: die gehören in CSS Paged
    Media, und das setzt Chromium nicht um. Dafür trägt jede Seite ihre
    Ordnung im Inhaltsverzeichnis und in den Kapitelüberschriften — und der
    Leser sieht die Zahl in seinem Betrachter.
    """
    from PySide6.QtCore import QEventLoop, QMarginsF, QTimer, QUrl
    from PySide6.QtGui import QPageLayout, QPageSize
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    RELEASES.mkdir(parents=True, exist_ok=True)
    target = RELEASES / f"{APP_NAME}-Handbuch-{language}.pdf"

    # Die Ränder stehen hier und nicht im ``@page`` des Stylesheets: bekommt
    # ``printToPdf`` ein Layout, gewinnt dessen Rand, und das CSS daneben ist
    # wirkungslos. Der erste Druck stand deshalb am Blattrand.
    layout = QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4),
        QPageLayout.Orientation.Portrait,
        QMarginsF(PDF_MARGIN_SIDE, PDF_MARGIN_TOP, PDF_MARGIN_SIDE, PDF_MARGIN_TOP),
        QPageLayout.Unit.Millimeter,
    )

    def attempt(settle: int) -> bool:
        """Ein Druckversuch. ``settle`` ist die Ruhezeit vor dem Druck."""
        page = QWebEnginePage()
        loop = QEventLoop()
        done: list[bool] = []

        def printed(data: bytes) -> None:
            if data:
                target.write_bytes(bytes(data))
            done.append(bool(data))
            loop.quit()

        def loaded(ok: bool) -> None:
            if not ok:
                done.append(False)
                loop.quit()
                return
            # Ein Lidschlag, damit die Bilder wirklich im Layout stehen:
            # gedruckt wird, was in dem Moment gesetzt ist, und ein Bild ohne
            # Maße reißt sonst eine Lücke, wo es hingehört.
            QTimer.singleShot(settle, lambda: page.printToPdf(printed, layout))

        page.loadFinished.connect(loaded)
        page.load(QUrl.fromLocalFile(str(page_file.resolve())))
        QTimer.singleShot(120_000, loop.quit)
        loop.exec()
        page.deleteLater()
        return bool(done) and done[0]

    # Zwei Anläufe, der zweite mit mehr Ruhe. Chromium bringt seinen eigenen
    # Prozess mit, und der ist unter Last gelegentlich noch nicht bereit,
    # wenn ``loadFinished`` schon kam — ein Handbuch deswegen gar nicht zu
    # drucken wäre die schlechtere Antwort.
    if not attempt(400) and not attempt(2500):
        raise RuntimeError(f"das Handbuch {language} ließ sich nicht drucken")

    _stamp(target, language)
    return target


#: Wo Kopf- und Fußzeile sitzen, in Punkt vom oberen bzw. unteren Blattrand.
#: Sie liegen im Seitenrand, den ``printToPdf`` freigelassen hat — deshalb
#: rückt der Text darüber und darunter nicht zusammen.
HEADER_BASELINE = 30.0
FOOTER_BASELINE = 32.0

#: Seitenrand links und rechts in Punkt, passend zu :data:`PDF_MARGIN_SIDE`.
STAMP_INSET = PDF_MARGIN_SIDE * 72.0 / 25.4


def _chapter_of_each_page(pdf: Path) -> list[str]:
    """Welches Kapitel auf welcher Seite läuft.

    Aus dem gesetzten PDF gelesen und nicht aus dem Quelltext gerechnet: erst
    der Satz weiß, wo ein Kapitel anfängt. Weil jedes auf einer neuen Seite
    beginnt (``break-before: page``), genügt der erste Titel, der auf einer
    Seite auftaucht; die Seiten danach führen ihn weiter.
    """
    from PySide6.QtPdf import QPdfDocument

    document = QPdfDocument()
    document.load(str(pdf))
    titles = [str(entry.title) for entry in manual.pages()]

    running = ""
    ahead = 0
    found: list[str] = []
    for number in range(document.pageCount()):
        lines = {line.strip() for line in document.getAllText(number).text().splitlines()}
        # Gesucht wird der **nächste erwartete** Titel, und er muss eine
        # eigene Zeile sein. Beides zusammen trifft: irgendwo im Fließtext zu
        # suchen setzte „Netz" über die Anleitung zum ersten Loch, weil ein
        # Satz darunter von einem offenen Netz sprach. Nur die erste Zeile zu
        # nehmen ging am anderen Ende daneben — ein Kapitel, das nicht oben
        # auf dem Blatt beginnt, wurde nie erkannt, und der Kolumnentitel
        # blieb Seiten später beim vorigen stehen.
        while ahead < len(titles) and titles[ahead] in lines:
            running = titles[ahead]
            ahead += 1
        found.append(running)
    return found


def _stamp(pdf: Path, language: str) -> None:
    """Kopf- und Fußzeile auf jede Seite legen.

    Chromium druckt keine — CSS Paged Media kennt Randboxen mit Seitenzähler,
    Chromium setzt sie nicht um. Also wird eine zweite, durchsichtige Lage
    gezeichnet und darübergelegt: oben das laufende Kapitel und der Name,
    unten Version und Seitenzahl.

    Deckblatt und Inhaltsverzeichnis bleiben frei — ein Titelblatt mit
    Kolumnentitel sieht aus wie eine Seite, die verrutscht ist.
    """
    from pypdf import PdfReader, PdfWriter

    chapters = _chapter_of_each_page(pdf)
    reader = PdfReader(str(pdf))
    total = len(reader.pages)
    overlay = _overlay(pdf.with_suffix(".stamp.pdf"), chapters, total, language)

    writer = PdfWriter()
    marks = PdfReader(str(overlay))
    for number, page in enumerate(reader.pages):
        if number >= SKIP_STAMP:
            page.merge_page(marks.pages[number])
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": f"{tr('Handbuch')} — {APP_NAME}",
            "/Author": APP_VENDOR,
            "/Creator": f"{APP_NAME} {APP_VERSION}",
        }
    )
    with pdf.open("wb") as stream:
        writer.write(stream)
    overlay.unlink(missing_ok=True)


#: Wie viele Seiten am Anfang ohne Kolumnentitel bleiben: Deckblatt und
#: Inhaltsverzeichnis.
SKIP_STAMP = 2


def _overlay(target: Path, chapters: list[str], total: int, language: str) -> Path:
    """Die Lage mit Kopf- und Fußzeilen, eine Seite je Seite des Handbuchs."""
    from PySide6.QtCore import QMarginsF, QRectF, Qt
    from PySide6.QtGui import (
        QColor,
        QFont,
        QPageLayout,
        QPageSize,
        QPainter,
        QPdfWriter,
        QPen,
    )

    writer = QPdfWriter(str(target))
    # Zweiundsiebzig dpi und keine Ränder: dann ist eine Einheit ein Punkt,
    # und die Lage deckt sich mit dem, worüber sie liegt.
    writer.setResolution(72)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)

    width = writer.width()
    height = writer.height()
    label = PAGE_OF.get(language, PAGE_OF["de"])

    painter = QPainter(writer)
    try:
        font = QFont(painter.font())
        font.setPointSizeF(8.0)
        painter.setFont(font)
        for number in range(total):
            if number:
                writer.newPage()
            if number < SKIP_STAMP:
                continue

            box = QRectF(STAMP_INSET, 0, width - 2 * STAMP_INSET, HEADER_BASELINE)
            painter.setPen(QPen(QColor(PDF_MUTED)))
            painter.drawText(
                box, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom), APP_NAME
            )
            painter.setPen(QPen(QColor(PDF_ACCENT)))
            painter.drawText(
                box,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom),
                chapters[number],
            )
            painter.setPen(QPen(QColor(PDF_LINE), 0.6))
            painter.drawLine(
                int(STAMP_INSET),
                int(HEADER_BASELINE + 5),
                int(width - STAMP_INSET),
                int(HEADER_BASELINE + 5),
            )

            foot = QRectF(
                STAMP_INSET, height - FOOTER_BASELINE, width - 2 * STAMP_INSET, FOOTER_BASELINE
            )
            painter.setPen(QPen(QColor(PDF_LINE), 0.6))
            painter.drawLine(
                int(STAMP_INSET),
                int(height - FOOTER_BASELINE),
                int(width - STAMP_INSET),
                int(height - FOOTER_BASELINE),
            )
            painter.setPen(QPen(QColor(PDF_MUTED)))
            painter.drawText(
                foot,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                f"{tr('Handbuch')} · {APP_NAME} {APP_VERSION}",
            )
            painter.drawText(
                foot,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
                label.format(page=number + 1, total=total),
            )
    finally:
        painter.end()
    return target


def main() -> int:
    # Zurückgesetzt hier und nicht beim Import: Das Modul stand als Falle für
    # jeden, der es importiert, statt es zu starten. `tests/test_translations.py`
    # führt es aus, um `page_for()` zu prüfen — danach galt für den ganzen
    # Testlauf keine Offscreen-Plattform mehr, `viewport._available()` sagte ja,
    # und jedes später gebaute Fenster bekam einen echten VTK-Interactor ohne
    # OpenGL-Kontext. Das nahm den Prozess mit. Wer dieses Werkzeug startet, hat
    # die Variable ohnehin nicht gesetzt; der Pop bleibt für den Fall, dass doch.
    os.environ.pop("QT_QPA_PLATFORM", None)

    load_operations()
    # Nur die Sprachen, für die es eine Seite auf der Website gibt. Seit die
    # Kataloge für ES, FR, IT und PT dazugekommen sind, liefert
    # ``available_languages()`` mehr, als hier gebaut werden kann: Jede Sprache
    # braucht ihren Ordner, ihre Navigation und einen Sprachwechsler, der fünf
    # Ziele kennt. Das ist ein eigenes Stück Arbeit, und bis es getan ist, ist
    # eine Meldung ehrlicher als ein Abbruch mit KeyError.
    known = [language for language in available_languages() if language in PAGES]
    missing = [language for language in available_languages() if language not in PAGES]
    if missing:
        print(f"ohne Handbuchseite, übersprungen: {', '.join(sorted(missing))}")
    for language in known:
        install_catalog(language, read_catalog(language))
        set_language(language)
        figures.forget()
        print(f"{language}:")

        name, prefix = page_for(language)
        # Je Sprache ein eigener Ordner: die Beschriftungen stecken in den
        # Zeichnungen, also ist ein deutsches Bild kein englisches.
        folder = WEBSITE / "handbuch" / language
        sources, dark_sources = write_figures(folder, language)
        print(
            f"  {len(sources)} Abbildungen ({len(dark_sources)} auch dunkel) "
            f"→ {folder.relative_to(ROOT)}"
        )

        target = WEBSITE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page_html(language, prefix), encoding="utf-8")
        print(f"  Seite → {target.relative_to(ROOT)}")

        pdf = write_pdf(language, target)
        if pdf is not None:
            size = pdf.stat().st_size / 1024
            print(f"  PDF → {pdf.relative_to(ROOT)} ({size:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
