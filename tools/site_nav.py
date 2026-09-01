"""Das Kopfmenü der Website — an einer Stelle, für alle Erzeuger.

**Warum es dieses Modul gibt.** Am 31.08.2026 trugen sechs Seiten sechs
verschiedene Kopfmenüs: Die Startseite nannte Funktionen, Preis, Handbuch und
Neuerungen, die Funktionsseite Vier Wege, KI-Modelle und Handbuch, die
KI-Seite wieder andere drei. Robert: „die seitenverteilung ist auch bisschen
schwer über das menü." Wer auf einer Seite einen Weg sieht und ihn auf der
nächsten nicht wiederfindet, lernt ihn nicht.

Beide Erzeuger bauten ihre Kopfzeile bis dahin selbst zusammen
(`make_manual._header`, `make_changelog._header`), und die statischen Seiten
trugen ihre eigene. Drei Orte für dieselbe Sache sind der Grund, warum sie
auseinanderlief. Hier steht sie einmal; dass die statischen Seiten dazu passen,
prüft `tests/test_website.py`.

Auf schmalem Schirm bleibt jeder Eintrag über den Aufklapper erreichbar. Ein
Weg, den nur der Desktop zeigt, ist für die Hälfte der Besucher keiner.
"""

from __future__ import annotations

from typing import Final

from app.i18n import SOURCE_LANGUAGE, _, source_text
from app.i18n.catalog import available_languages, read_catalog

#: Die fünf Wege als Quellpfad, Unterordnerpfad und deutscher Textschlüssel.
#: Sprache sieben braucht damit nur ihren Katalog; sie bekommt weder deutsche
#: Beschriftungen noch Verweise auf die deutsche Seite.
ENTRY_SPECS: Final = (
    ("funktionen.html", "features.html", _("Funktionen")),
    ("ki-modelle.html", "ai-models.html", _("KI-Modelle")),
    ("#preis", "#pricing", _("Preis")),
    ("changelog.html", "changelog.html", _("Neuerungen")),
    ("handbuch.html", "manual.html", _("Handbuch")),
)


def site_text(source: str, language: str) -> str:
    """Ein Rahmentext aus dem Katalog, Deutsch als Quellsprache."""
    if language == SOURCE_LANGUAGE:
        return source
    return read_catalog(language).get(source, source)


def entries_for(language: str) -> list[tuple[str, str, str]]:
    """Die fünf Menüwege einer Sprache aus Pfadschema und Katalog."""
    entries = []
    for german_path, translated_path, label in ENTRY_SPECS:
        if language == SOURCE_LANGUAGE:
            target = german_path
        elif translated_path.startswith("#"):
            target = translated_path
        else:
            target = f"{language}/{translated_path}"
        address = target if target.startswith("#") else f"/{target}"
        entries.append((address, site_text(source_text(label), language), ""))
    return entries


#: Rückwärtskompatible Momentaufnahme für Erzeuger, die ausschließlich die
#: bereits vorhandenen Sprachen brauchen. Neue Wege rufen :func:`entries_for`.
ENTRIES: Final = {language: entries_for(language) for language in available_languages()}


def nav_links(language: str, *, current: str = "", on_home: bool = False) -> str:
    """Die fünf Verweise als HTML, ohne das umgebende ``<nav>``.

    ``current`` ist der Pfad der Seite, die das Menü trägt (etwa
    ``/en/manual.html``); der passende Eintrag bekommt ``aria-current``.
    ``on_home`` sagt, ob die Seite selbst die Startseite ist — nur dort
    bleiben Anker kurz.
    """
    entries = entries_for(language)
    parts: list[str] = []
    for target, label, hide in entries:
        address = target
        if target.startswith("#") and not on_home:
            home = "/" if language == SOURCE_LANGUAGE else f"/{language}/"
            address = home + target
        marker = ' aria-current="page"' if current and target == current else ""
        attribute = f' class="{hide}"' if hide else ""
        parts.append(f'<a{attribute} href="{address}"{marker}>{label}</a>')
    return "".join(parts)


#: Drei Striche als Symbol. **Kein Zeichen aus einer Schrift und kein Emoji**
#: (Hausregel): Ein Glyph hängt davon ab, was der Rechner installiert hat,
#: eine Zeichnung nicht.
MENU_MARK: Final[str] = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round"/></svg>'
)


def nav_menu(language: str, *, current: str = "", on_home: bool = False, extra: str = "") -> str:
    """Die fünf Verweise in einem Aufklapper, der am Rechner keiner ist.

    **Warum ein ``details`` und kein Skript.** Auf einem Handy passten nur
    zwei Einträge in die Zeile; die übrigen wurden per CSS ausgeblendet, und
    damit kannte die Hälfte der Besucher mehrere Wege nicht.
    Robert am 31.08.2026: „mach doch ein aufklappmenü für mobil."

    Am Rechner soll dieselbe Leiste aber eine Leiste bleiben — ein Aufklapper,
    wo Platz ist, verlangt einen Klick für nichts. Beides aus **einem** Markup
    geht, weil das Verstecken nicht geschieht: Das Browser-Stylesheet blendet
    die Kinder eines geschlossenen ``details`` mit ``display`` aus, und eine
    eigene ``display``-Regel gewinnt dagegen. Am Rechner steht deshalb der
    Inhalt offen und das Symbol verschwindet; erst unterhalb der Umbruchbreite
    dreht sich beides um.

    ``extra`` nimmt einen Weg auf, den nur **diese** Seite hat — im Handbuch
    den Sprung ins Inhaltsverzeichnis. Er gehört **in** das Panel und nicht
    daneben: Außerhalb verschwände er auf einem Telefon ganz, während die
    fünf gemeinsamen Wege im Aufklapper erreichbar bleiben — und ein
    Handbuch ohne Sprung ins Inhaltsverzeichnis ist dort schwer zu benutzen.

    Dieselbe Bauart trägt der Sprachwechsel daneben seit jeher — und sie
    braucht keine Zeile JavaScript, funktioniert also auch, wenn nichts lädt.
    """
    return (
        f'<details class="menu">'
        f'<summary aria-label="{site_text("Menü", language)}">'
        f"{MENU_MARK}</summary></details>"
        f'<div class="menu-panel">'
        f"{nav_links(language, current=current, on_home=on_home)}"
        f"{extra}"
        f"</div>"
    )
