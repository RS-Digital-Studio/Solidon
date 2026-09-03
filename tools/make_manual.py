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
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.branding import APP_NAME, APP_VENDOR, APP_VERSION, COPYRIGHT, WEBSITE_URL
from app.core import figures, manual
from app.core.bootstrap import load_operations
from app.i18n import SOURCE_LANGUAGE, install_catalog, language_name, set_language
from app.i18n.catalog import available_languages, read_catalog
from tools.site_nav import entries_for, nav_menu, site_text

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"
RELEASES = ROOT / "Releases"

#: Beschriftung des Tastatur-Sprungs für die aktuell installierten Sprachen.
#: Die Website-Prüfung liest dieselbe Zuordnung wie der Generator. Eine später
#: hinzugefügte Sprache fällt beim Erzeugen trotzdem auf ihren Katalog zurück;
#: sie braucht keine Änderung an diesem Modul.
SKIP = {language: site_text("Zum Inhalt springen", language) for language in available_languages()}


def page_for(language: str) -> tuple[str, str]:
    """Zielseite und Bildpfad einer Sprache.

    Eine Sprache, die noch keinen Eintrag hat, bekommt den Ort, den sie nach
    demselben Muster hätte — sonst stünde die Sprachauswahl in der Anwendung
    schon offen, während der Handbuchbauer beim ersten neuen Kürzel mit einem
    ``KeyError`` abbricht.
    """
    if language == SOURCE_LANGUAGE:
        return "handbuch.html", "handbuch/de"
    return f"{language}/manual.html", f"../handbuch/{language}"


STYLE = """
    /* Der Text bleibt schmal, weil sich lange Zeilen schlecht lesen. Die
       Abbildungen dürfen darüber hinausragen: ein Bildschirmfoto auf halbe
       Spaltenbreite gestaucht zeigt Beschriftungen, die niemand mehr liest. */
    main { max-width: 74rem; margin: 0 auto; padding: 2rem 1.25rem 5rem;
           counter-reset: chapter; }
    /* **Zwei Breiten, weil hier zweierlei steht.** 52rem galt bis zum
       31.08.2026 für alles, und der Satz darüber stimmte nur der Absicht nach:
       Gemessen an 344 mehrzeiligen Absätzen des deutschen Handbuchs standen
       darauf 90 Zeichen je Zeile im Mittel und 119 im schlimmsten Fall — gut
       lesbar sind 60 bis 75. Bei 38rem sind es gemessene 70.

       Die 52rem bleiben trotzdem stehen, denn sie tragen auch die 97 Tabellen
       der Referenz. Eine Tabelle auf Fließtextbreite bricht ihre Spalten um,
       und dann liest sich gar nichts mehr. Beide bleiben mittig, die breiteren
       Elemente ragen also symmetrisch heraus. */
    main > :not(figure) { max-width: 52rem; margin-left: auto; margin-right: auto; }
    main > p, main > ul, main > ol, main > h3, main > h4 { max-width: 38rem; }
    /* Der Einstieg: derselbe Ton wie der Aufmacher der Startseite, eine
       Nummer kleiner — das Handbuch verkauft nicht, es empfängt. */
    main > h1 { font-size: clamp(2rem, 4vw, 2.6rem); letter-spacing: -0.015em;
                margin: 1.6rem auto 0.4rem; }
    p.lede { color: var(--muted); font-size: var(--t-base); margin-bottom: 2rem; }
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
      margin-top: 3.2rem; color: var(--accent); font-size: var(--t-xl);
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
    figcaption { color: var(--muted); font-size: var(--t-sm); margin-top: .5rem; }
    /* Die Bildschirmfotos liegen auf derselben dunklen Bühne wie auf der
       Startseite — ``.stage`` samt Streiflicht kommt aus ``style.css``, hier
       steht nur, was im Handbuch anders ist: ``figure`` zentriert schon,
       also braucht die Bühne keinen eigenen Abstand nach oben. */
    figure.screenshot .stage { margin: 0; }

    /* Der Verweis um ein Bildschirmfoto ist ein Weg, keine Verzierung: keine
       Unterstreichung, keine Linkfarbe, kein Rahmen. Er traegt den Alt-Text
       des Bildes als Beschriftung, ein Bildschirmleser sagt also, wohin er
       fuehrt. */
    figure.screenshot .stage a { display: block; text-decoration: none;
                                 color: inherit; }

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
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: var(--t-md); }
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
    /* ``margin: auto`` wie bei den übrigen Kindern von ``main`` — die
       Kartenregel der Funktionsseite in style.css setzt sonst 0 und schiebt
       das Verzeichnis als einziges Element an den linken Rand. */
    nav.toc { background: var(--card); border: 1px solid var(--line);
              border-radius: 10px; padding: 1.4rem 1.8rem 1.6rem; margin: 2.5rem auto; }
    nav.toc .toc-title { margin: 0 0 1rem; border: none; padding: 0;
                         font-size: var(--t-base); letter-spacing: .02em; }
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
                text-decoration: none; color: var(--fg); font-size: var(--t-md); }
    nav.toc li:last-child a { border-bottom: none; }
    /* Die Fuge zwischen den geschriebenen Kapiteln und der Referenz —
       gedämpft, weil sie ordnet und nicht ruft. */
    nav.toc .toc-divider { margin: 1.6rem 0 .8rem; border: none; padding: 0;
                           font-size: var(--t-md); color: var(--muted);
                           font-weight: 600; letter-spacing: .02em; }
    nav.toc a:hover { color: var(--accent); }
    nav.toc .num { color: var(--accent); font-size: var(--t-xs); font-weight: 600;
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

      /* **Ohne diese Zeile trägt das PDF kein einziges Bild.** Die
         Abbildungen steigen am Bildschirm beim Lesen auf, und diese
         Animation hängt an der Scroll-Position (``animation-timeline:
         view()`` weiter oben). Gedruckt wird nicht gescrollt: Der
         Fortschritt bleibt null, die Animation steht auf ihrem Anfangswert,
         und der ist unsichtbar. Die Bilder laden dabei alle — 39 von 39 mit
         ``naturalWidth > 0`` —, sie werden nur nicht gezeichnet.

         Gemessen am 27.08.2026 durch Halbierung des Stylesheets: mit dieser
         einen Regel null Rasterbilder im PDF, ohne sie vierunddreißig. Sechs
         andere Vermutungen (Pfade, Ladezustand, ``display: none``,
         Ruhezeit, fehlender Viewport, ``decode()``) waren zuvor gemessen
         ausgeschlossen worden, und die Regel stand die ganze Zeit daneben —
         sie versteckt nichts, sie animiert nur. */
      main figure { animation: none !important; }

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


def _write_stubbornly(path: Path, payload: str | bytes) -> None:
    """Eine Datei schreiben und eine flüchtige Kollision aussitzen.

    **Warum es sie gibt.** Derselbe Lauf riss an drei verschiedenen Stellen
    mit ``OSError 22`` beim Öffnen zum Schreiben — beim englischen PDF, beim
    spanischen, bei einer SVG-Datei. Jedes Mal war die Datei unmittelbar
    danach wieder frei und ihr Ordner beschreibbar. Auf dieser Maschine
    arbeiten mehrere Sitzungen im selben Baum, und der Lauf legt über
    zweihundert Dateien in schneller Folge an; wer dabei einmal auf einen
    fremden Handle oder einen Scanner trifft, verliert sonst zwanzig Minuten
    Arbeit für einen Zustand, der eine halbe Sekunde später nicht mehr
    besteht.

    Der letzte Versuch scheitert laut — eine Datei, die nach drei Anläufen
    nicht zu schreiben ist, hat einen anderen Grund als Eile.
    """
    import time

    for wait in (0.0, 0.4, 1.5):
        if wait:
            time.sleep(wait)
        try:
            if isinstance(payload, bytes):
                path.write_bytes(payload)
            else:
                path.write_text(payload, encoding="utf-8")
        except OSError as error:
            last = error
            continue
        if wait:
            print(f"  {path.name}: erst im zweiten Anlauf geschrieben")
        return
    raise last


def write_figures(target: Path, language: str) -> tuple[dict[str, str], dict[str, str]]:
    """Jede Abbildung als Datei ablegen. Liefert die Adressen je Schlüssel.

    Zurück kommen zwei Zuordnungen: die gewöhnlichen Quellen und die für ein
    dunkles Farbschema. Gezeichnet wird beides, weil ``core.drawing`` beide
    Paletten kennt — die dunkle Version blieb bis dahin ungenutzt, und im
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
            _write_stubbornly(target / f"{figure.key}.png", source.read_bytes())
            sources[figure.key] = f"{figure.key}.png"
            continue
        svg = figures.svg(figure.key, "light")
        if svg is None:
            print(f"  fehlt: {figure.key} (lässt sich hier nicht zeichnen)")
            continue
        _write_stubbornly(target / f"{figure.key}.svg", svg)
        sources[figure.key] = f"{figure.key}.svg"

        dark = figures.svg(figure.key, "dark")
        if dark is not None:
            _write_stubbornly(target / f"{figure.key}-dark.svg", dark)
            dark_sources[figure.key] = f"{figure.key}-dark.svg"
    return sources, dark_sources


#: Die Adresse, unter der die Seiten liegen — für canonical, hreflang und die
#: Vorschau beim Teilen. Aus ``branding.WEBSITE_URL``, damit sie an einer
#: Stelle steht.
SITE = WEBSITE_URL

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


def _switcher(language: str) -> str:
    """Der Sprachwechsel als Aufklappmenü — zu sehen ist das eigene Kürzel,
    offen stehen alle sechs Sprachen ausgeschrieben.

    ``details`` braucht kein Skript; dasselbe Markup tragen die statischen
    Seiten, die Stile wohnen in ``style.css`` unter ``details.langs``.
    """
    rows = "".join(
        f'<li><a href="{_switch_target(language, other)}" hreflang="{other}" lang="{other}"'
        + (' aria-current="page"' if other == language else "")
        + f">{language_name(other)}</a></li>"
        for other in sorted(available_languages())
    )
    return (
        '<details class="langs">'
        f'<summary aria-label="{site_text("Sprache wählen", language)}">'
        f"{language.upper()}</summary>"
        f"<ul>{rows}</ul></details>"
    )


def _header(language: str) -> str:
    """Die Kopfzeile — am Bildschirm klebt sie oben, im Druck fehlt sie."""
    toc_label = site_text("Inhalt", language)
    cta_label = site_text("Testen", language)
    cta_target = "./#preis" if language == SOURCE_LANGUAGE else "./#pricing"
    entries = entries_for(language)
    toc_link = f'<a href="#toc">{toc_label}</a>'
    return (
        '<header class="site no-print"><div class="wrap">'
        f'<a class="brand" href="./">{BRAND_MARK}Solidon<span>3D</span></a>'
        '<nav class="lang">'
        # **Das gemeinsame Menü zuerst, der Inhaltsverweis danach.** Das
        # Handbuch trägt dieselben sechs Wege wie jede andere Seite — sonst
        # ist es eine Sackgasse, aus der nur der Zurück-Knopf führt. Sein
        # eigenes Inhaltsverzeichnis kommt dazu, nicht an ihrer Stelle.
        # Der Sprung ins Inhaltsverzeichnis gehört **in** das Menü, nicht
        # daneben: außerhalb verschwände er auf einem Telefon ganz, während
        # die sechs gemeinsamen Wege im Aufklapper erreichbar bleiben.
        f"{nav_menu(language, current=entries[-1][0], extra=toc_link)}"
        f"{_switcher(language)}"
        f'<a class="cta" href="{cta_target}">{cta_label}</a>'
        "</nav></div></header>"
    )


#: Seitenränder des Drucks in Millimetern. Sie stehen hier und nicht im CSS:
#: ``printToPdf`` mit einem Layout schlägt jedes ``@page`` im Stylesheet.
PDF_MARGIN_SIDE = 18.0
PDF_MARGIN_TOP = 16.0

#: Notbremse für einen Druckversuch. Sie greift nur, wenn Chromium gar nicht
#: antwortet — seit auf ``decode()`` gewartet wird, druckt der Rückruf sonst
#: sofort. Großzügig, weil ein Handbuch mit vierzig Bildern auf einer
#: ausgelasteten Maschine länger braucht als auf einer leeren.
PDF_PRINT_LIMIT_MS = 150_000

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

    heading = site_text("Inhalt", language)
    blocks = [f'<h2 class="toc-title">{heading}</h2>']
    blocks.append("<ol>" + "".join(entry(number, page) for number, page in written) + "</ol>")
    if generated:
        # Die Fuge, an der aus Lesen Nachschlagen wird. Die Nummern laufen
        # durch: sie stehen so auch über den Kapiteln selbst.
        divider = site_text("Referenz — jede Operation mit ihren Werten", language)
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
    Inhaltsverzeichnis führt nirgendwohin, ohne dass es jemand sieht. Sie wird
    darum gelernt und nicht gesetzt: Die erste gefundene Kapitelüberschrift
    sagt, auf welcher Ebene die Kapitel stehen, und dabei bleibt es.

    Zwei Dinge, die eine Suche nach dem Wortlaut allein falsch macht:

    **Der Titel steht maskiert im HTML.** ``markup.inline`` schreibt aus einem
    Apostroph ``&#x27;``; gegen den rohen Titel gehalten fand die Suche
    „Ce qu'est Solidon" nie. Im französischen Handbuch verloren drei Kapitel
    ihren Anker, im italienischen eines — beide ohne eine rote Zeile.

    **Derselbe Wortlaut kommt zweimal vor.** Das Kapitel *Die Werkzeuge der
    Fernsteuerung* gliedert seine Werkzeuge nach denselben fünfzehn Kategorien,
    die weiter unten die Referenzkapitel sind. Die alte Version nahm den ersten
    Treffer im ganzen Text: Alle fünfzehn Referenzanker saßen auf einem
    Unterabschnitt der Fernsteuerung, und das Verzeichnis sprang ab Kapitel 26
    mitten in Kapitel 24. Gesucht wird deshalb nur vorwärts — die Kapitel stehen
    im Text in derselben Reihenfolge wie in ``manual.pages()`` — und nur auf der
    Ebene der Kapitel.
    """
    from app.core.markup import inline

    pieces: list[str] = []
    cursor = 0
    level = ""
    for page in manual.pages():
        title = inline(str(page.title))
        pattern = re.compile(rf"<h([1-6])>{re.escape(title)}</h\1>")
        at = cursor
        while True:
            found = pattern.search(html, at)
            if found is None:
                break
            if level and found.group(1) != level:
                # Gleicher Wortlaut, tiefere Ebene: ein Unterabschnitt, nicht
                # das Kapitel.
                at = found.end()
                continue
            level = found.group(1)
            # Erzeugte Kapitel bekommen zusätzlich eine Klasse: im Druck fängt
            # der Referenzteil je Kapitel auf einem neuen Blatt an, die
            # Einführung liest man am Stück (siehe ``@media print``).
            css = ' class="chapter"' if page.generated else ""
            pieces.append(html[cursor : found.start()])
            pieces.append(f'<h{level} id="{_anchor(page)}"{css}>{title}</h{level}>')
            cursor = found.end()
            break
    pieces.append(html[cursor:])
    return "".join(pieces)


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


def _picture_size(source: str) -> tuple[int, int] | None:
    """Die Maße einer Abbildung, aus der Datei gelesen statt geschätzt.

    Bei PNG stehen sie im IHDR-Block gleich hinter der Signatur, bei SVG im
    ``viewBox``. Was sich nicht lesen lässt, bekommt keine Angabe — eine
    falsche wäre schlimmer als keine, weil der Browser dann Platz in der
    falschen Größe reserviert.
    """
    path = WEBSITE / source.removeprefix("../")
    if not path.exists():
        return None
    if path.suffix == ".png":
        width, height = struct.unpack(">II", path.read_bytes()[16:24])
        return int(width), int(height)
    box = re.search(
        r'viewBox="[\d.-]+ [\d.-]+ ([\d.]+) ([\d.]+)"',
        path.read_text(encoding="utf-8")[:2000],
    )
    if box is None:
        return None
    return round(float(box.group(1))), round(float(box.group(2)))


def _defer_offscreen_pictures(html: str) -> str:
    """Gibt jeder Abbildung ihre Maße und lädt die unteren erst bei Bedarf.

    Zwei Dinge, ein Durchgang, weil beide dasselbe ``<img>`` betreffen:

    * ``width`` und ``height`` reservieren den Platz, bevor das Bild da ist.
      Ohne sie rutscht beim Laden alles darunter — auf einer Seite mit über
      zweihundert Abbildungen ist das kein Zucken, sondern ein Springen.
    * ``loading="lazy"`` holt nur, was in Sichtweite kommt. **Außer der
      ersten**: die steht oben, wird also sofort gebraucht, und ein
      verzögertes erstes Bild verschlechtert genau die Messung, die dieser
      Zusatz verbessern soll.
    """
    seen = 0

    def extend(match: re.Match[str]) -> str:
        nonlocal seen
        seen += 1
        tag, source = match.group(0), match.group(1)
        extra = "" if seen == 1 else ' loading="lazy" decoding="async"'
        size = _picture_size(source)
        if size is not None and "width=" not in tag:
            extra += f' width="{size[0]}" height="{size[1]}"'
        return tag[:-1] + extra + ">"

    return re.sub(r'<img src="([^"]+)"[^>]*>', extend, html)


def _staged(match: re.Match[str]) -> str:
    """Ein Bildschirmfoto auf die Bühne stellen — höchstens so breit, wie es ist.

    ``.stage img`` zieht jedes Bild auf die volle Breite der Bühne, und auf
    einer Startseite ist das richtig: Dort steht ein Fenster in einer schmalen
    Spalte. Im Handbuch ist die Spalte 1124 Bildpunkte breit, und derselbe Satz
    blies den Prüfbericht auf **181 Prozent** auf, den Operationsdialog auf
    **216** — hochgerechnete Bildschirmfotos mit weicher Schrift, und zwar
    ausgerechnet die beiden, bei denen es auf die Beschriftung ankommt.

    Begrenzt wird die ``figure`` und nicht das Bild: Sie zentriert bereits
    (``margin: 2rem auto``), also rückt die Bühne mit. Dazu kommen das Polster
    der Bühne (zweimal 0,55 rem) und ihr Rahmen. Wo sich die Größe nicht lesen
    lässt, bleibt es beim alten Verhalten — eine falsche Schranke wäre
    schlimmer als keine.
    """
    attributes = match.group(1)
    source = re.search(r'src="([^"]+)"', attributes)
    size = _picture_size(source.group(1)) if source else None
    limit = f' style="max-width: calc({size[0]}px + 1.1rem + 2px)"' if size else ""
    # **Antippen oeffnet das Bild.** Auf einem 375er Schirm steht ein
    # Bildschirmfoto von 2560 px Breite 300 px breit, und darauf ist nichts
    # mehr zu lesen — gemessen am Startbildschirm, dessen Alt-Text drei Dinge
    # nennt, die man nicht sieht. Ein Verweis auf die Datei selbst braucht
    # kein JavaScript und keine eigene Bedienung: Der Browser zeigt das Bild
    # in voller Groesse und zoomt von selbst.
    #
    # Nur wo die Quelle lesbar ist — ein Verweis ins Leere waere schlimmer als
    # keiner.
    if source:
        bild = f'<a href="{source.group(1)}"><img {attributes}></a>'
    else:
        bild = f"<img {attributes}>"
    return f'<figure class="screenshot"{limit}><div class="stage">{bild}</div>'


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
    body = re.sub(r'<figure><img (src="[^"]+\.png"[^>]*)>', _staged, body)
    body = _defer_offscreen_pictures(body)
    title = f"{site_text('Handbuch: 3D-Modelle für den Druck vorbereiten', language)} — {APP_NAME}"
    pages = len(manual.pages())
    description = site_text(
        "Das Handbuch zu Solidon3D: {pages} Kapitel von den ersten fünfzehn Minuten "
        "bis zu jeder Operation mit ihren Werten und Bereichen. Die Referenzhälfte "
        "kommt aus demselben Register wie die Menüs.",
        language,
    ).format(pages=pages)
    lede = site_text(
        "{pages} Kapitel — von den ersten fünfzehn Minuten bis zur Referenz "
        "jeder Operation, erzeugt aus derselben Quelle wie das Handbuch in der "
        "Anwendung.",
        language,
    ).format(pages=pages)
    canonical = f"{SITE}{page_for(language)[0]}"
    # Jede Sprache nennt jede — sechs Zeilen aus derselben Tabelle, die auch
    # die Seiten baut, statt zweier von Hand gepflegter.
    alternates = "".join(
        f'<link rel="alternate" hreflang="{code}" href="{SITE}{page_for(code)[0]}">\n'
        for code in sorted(available_languages())
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
        f'<a class="skip" href="#content">'
        f"{SKIP.get(language, site_text('Zum Inhalt springen', language))}</a>\n"
        f'{_header(language)}\n<main id="content">\n'
        f"{_cover_block(language)}\n"
        f'<h1 class="no-print">{site_text("Handbuch", language)}</h1>\n'
        f'<p class="lede no-print">{lede}</p>\n'
        f"{contents(language)}\n"
        f"{anchored(body)}\n"
        # Der Zähler, wie auf jeder anderen Seite. Ohne ihn stand das
        # Handbuch in sechs Sprachen in keiner Statistik.
        f'</main>\n<script src="/site.js" defer></script>\n</body>\n</html>\n'
    )


def _cover_block(language: str) -> str:
    """Das Deckblatt — im Druck die erste Seite, am Bildschirm ausgeblendet.

    Es steht im HTML und nicht in einem eigenen Setzlauf, weil es sonst eine
    zweite Quelle wäre: ein Titel, der sich ändert, müsste an zwei Stellen
    nachgezogen werden, und die zweite vergisst man.
    """
    title = site_text("Handbuch", language)
    subtitle = site_text("Konstruieren, Erzeugen und Bearbeiten für den 3D-Druck", language)
    version_word = site_text("Version", language)
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
        """Ein Druckversuch. ``settle`` ist die Ruhezeit nach dem Dekodieren."""
        page = QWebEnginePage()
        loop = QEventLoop()
        done: list[bool] = []
        seen_images: list[int] = []

        def printed(data: bytes) -> None:
            if data:
                target.write_bytes(bytes(data))
            done.append(bool(data))
            loop.quit()

        def count_then_print(found: object) -> None:
            """Die Bildzahl der Seite festhalten, dann drucken."""
            seen_images.append(int(found) if isinstance(found, int | float) else -1)
            QTimer.singleShot(settle, lambda: page.printToPdf(printed, layout))

        def loaded(ok: bool) -> None:
            if not ok:
                done.append(False)
                loop.quit()
                return
            # Ein Lidschlag, damit die Bilder wirklich im Layout stehen.
            #
            # **Er reicht nicht, und das ist ein offener Punkt** (ROADMAP,
            # 26.08.2026): Die erzeugten PDFs tragen null eingebettete Bilder,
            # an jeder Abbildung steht eine Lücke in exakt ihrer Größe. Zwei
            # Wege sind gemessen und untauglich — ``decode()`` abzuwarten löst
            # sein Promise nie auf (und ``runJavaScript`` wartet ohnehin nicht
            # auf Promises, es gibt den synchronen Wert zurück), und eine
            # ``QWebEngineView`` mit echtem Viewport druckt genauso ohne Bilder.
            # Die Zahl daneben ist deshalb keine Zierde: Sie sagt, wie viele
            # Bilder die Seite kennt, und trennt „Seite ohne Abbildungen" von
            # „Abbildungen, die nicht mitgedruckt werden".
            page.runJavaScript("document.images.length", count_then_print)

        page.loadFinished.connect(loaded)
        page.load(QUrl.fromLocalFile(str(page_file.resolve())))
        QTimer.singleShot(PDF_PRINT_LIMIT_MS, loop.quit)
        loop.exec()
        page.deleteLater()
        if seen_images and seen_images[0] == 0:
            # Ein Handbuch ohne ein einziges Bild ist kein Erfolg, sondern eine
            # Seite, die ihre Abbildungen nicht gefunden hat.
            print(f"  {language}: die Seite trug kein einziges Bild", file=sys.stderr)
        return bool(done) and done[0]

    # Zwei Anläufe, der zweite mit mehr Ruhe. Chromium bringt seinen eigenen
    # Prozess mit, und der ist unter Last gelegentlich noch nicht bereit, wenn
    # ``loadFinished`` schon kam — ein Handbuch deswegen gar nicht zu drucken
    # wäre die schlechtere Antwort.
    #
    # **Der zweite Anlauf läuft nie**, und das gehört zum offenen Punkt oben:
    # ``attempt`` gilt als gelungen, sobald ``printToPdf`` Bytes liefert, und
    # ein PDF ohne Bilder ist auch Bytes. Eine Erfolgsbedingung, die die Bilder
    # prüft, braucht eine verlässliche Zählung im fertigen PDF — ein Grep auf
    # ``/Subtype /Image`` taugt dafür nicht, weil Chromium Objektströme
    # komprimiert und der Grep dann auch über einem guten PDF null liefert.
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
    # **Ausdrücklich schließen, nicht dem Einsammler überlassen.** Qt hält die
    # Datei offen, solange das Dokument lebt, und ``_stamp`` schreibt gleich
    # darauf in dieselbe Datei. Ohne diese Zeile hing es davon ab, wann
    # CPython das lokale Objekt einsammelt: Am 03.09.2026 riss der Lauf
    # zweimal mit ``OSError 22`` beim Öffnen zum Schreiben — einmal bei
    # Englisch, einmal bei Französisch, und dazwischen gingen dieselben
    # Sprachen durch. Ein Fehler, der die Reihenfolge wechselt, ist kein
    # Fehler der Datei.
    document.close()
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
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter

    chapters = _chapter_of_each_page(pdf)
    # **Aus dem Speicher und nicht über den Pfad.** ``PdfReader`` liest
    # verzögert und hält die Datei offen, solange er lebt — und unten wird
    # dieselbe Datei zum Schreiben geöffnet. Das war der zweite Halter neben
    # dem ``QPdfDocument`` darüber: Am 03.09.2026 riss der Lauf mit
    # ``OSError 22`` beim englischen Handbuch, nachdem das deutsche
    # durchgegangen war. Wer nur einen von beiden schließt, verschiebt den
    # Fehler auf eine andere Sprache, statt ihn abzustellen.
    reader = PdfReader(BytesIO(pdf.read_bytes()))
    total = len(reader.pages)
    overlay = _overlay(pdf.with_suffix(".stamp.pdf"), chapters, total, language)

    writer = PdfWriter()
    # Dieselbe Vorsicht: ``overlay`` wird am Ende gelöscht.
    marks = PdfReader(BytesIO(overlay.read_bytes()))
    for number, page in enumerate(reader.pages):
        if number >= SKIP_STAMP:
            page.merge_page(marks.pages[number])
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": f"{site_text('Handbuch', language)} — {APP_NAME}",
            "/Author": APP_VENDOR,
            "/Creator": f"{APP_NAME} {APP_VERSION}",
        }
    )
    _replace_with(pdf, writer)
    overlay.unlink(missing_ok=True)


def _replace_with(pdf: Path, writer: object) -> None:
    """Die gestempelte Fassung daneben schreiben und an die Stelle rücken.

    **Warum nicht in die Datei selbst.** Ein ``pdf.open("wb")`` auf die eben
    gedruckte PDF riss dreimal mit ``OSError 22`` — bei Englisch, dann bei
    Spanisch, jedes Mal nach einer Sprache, die durchgelaufen war. Ein Fehler,
    der die Stelle wechselt, ist keine Aussage über die Datei, sondern über
    Zeitpunkte: Irgendetwas hält sie noch, wenn geschrieben werden soll.

    **Zwei Halter sind gefunden und behoben** — das ``QPdfDocument`` in
    :func:`_chapter_of_each_page` und der ``PdfReader``, der über den Pfad
    statt über den Speicher las. Ein dritter blieb, und eine Sonde über alle
    drei Schritte meldete die Datei nach jedem einzelnen als frei: Er sitzt
    nicht hier, sondern im Drucken davor, wo QtWebEngine seinen Rückruf nicht
    zwingend abgearbeitet hat, bevor die Ereignisschleife verlassen wird.

    Deshalb wird hier nicht der vierte Verdacht repariert, sondern die Stelle
    unempfindlich gemacht: danebenschreiben, dann ersetzen. Zwischen den
    Anläufen läuft die Ereignisschlange einmal leer — das ist die Gelegenheit
    für einen hängenden Rückruf, fertig zu werden, und sie kostet nichts, wenn
    keiner aussteht.
    """
    import time

    from PySide6.QtCore import QCoreApplication

    beside = pdf.with_suffix(".stamped.pdf")
    with beside.open("wb") as stream:
        writer.write(stream)  # type: ignore[attr-defined]

    for wait in (0.0, 0.5, 2.0):
        if wait:
            application = QCoreApplication.instance()
            if application is not None:
                application.processEvents()
            time.sleep(wait)
        try:
            beside.replace(pdf)
        except OSError:
            continue
        return

    # Angekommen heißt: Die Datei ist auch nach drei Anläufen gehalten. Dann
    # sagt die Meldung, wer — eine Zahl ist mehr wert als ein zweiter Versuch.
    try:
        with pdf.open("r+b"):
            holder = "niemand mehr, das Ersetzen scheiterte aus einem anderen Grund"
    except OSError as error:
        holder = f"jemand hält sie: {error.errno} ({error.strerror})"
    beside.unlink(missing_ok=True)
    raise RuntimeError(f"{pdf.name} ließ sich nicht ersetzen — {holder}")


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
    label = site_text("Seite {page} von {total}", language)

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
                f"{site_text('Handbuch', language)} · {APP_NAME} {APP_VERSION}",
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
    # Der Katalog ist die Anmeldung einer Sprache (§4.1). ``page_for`` und die
    # sichtbaren Rahmentexte stammen für jedes Kürzel aus demselben Katalog;
    # ein unvollständiger Katalog macht die Übersetzungsprüfung rot. Eine
    # zweite Sprachliste würde den Erzeugerlauf wieder still unvollständig machen.
    for language in available_languages():
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
        _write_stubbornly(target, page_html(language, prefix))
        print(f"  Seite → {target.relative_to(ROOT)}")

        pdf = write_pdf(language, target)
        if pdf is not None:
            size = pdf.stat().st_size / 1024
            print(f"  PDF → {pdf.relative_to(ROOT)} ({size:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
