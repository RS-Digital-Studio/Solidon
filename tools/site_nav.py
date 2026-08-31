"""Das Kopfmenü der Website — an einer Stelle, für alle Erzeuger.

**Warum es dieses Modul gibt.** Am 31.08.2026 trugen sechs Seiten sechs
verschiedene Kopfmenüs: Die Startseite nannte Funktionen, Preis, Handbuch und
Neuerungen, die Funktionsseite Vier Wege, KI-Modelle und Handbuch, die
KI-Seite wieder andere drei. Robert: „die seitenverteilung ist auch bisschen
schwer über das menü." Wer auf einer Seite einen Weg sieht und ihn auf der
nächsten nicht wiederfindet, lernt ihn nicht.

Schlimmer war, was **keines** der sechs Menüs nannte: die Tauschbörse. Sie war
gebaut, geprüft und in sechs Sprachen übersetzt — und hatte **null** eingehende
Verweise. Eine Insel, erreichbar nur über die Adresszeile.

Beide Erzeuger bauten ihre Kopfzeile bis dahin selbst zusammen
(`make_manual._header`, `make_changelog._header`), und die statischen Seiten
trugen ihre eigene. Drei Orte für dieselbe Sache sind der Grund, warum sie
auseinanderlief. Hier steht sie einmal; dass die statischen Seiten dazu passen,
prüft `tests/test_website.py`.

**Die Börse trägt als einzige keine Ausblendeklasse.** Auf schmalem Schirm
verschwinden Funktionen, KI-Modelle, Preis und Neuerungen der Reihe nach;
Börse und Handbuch bleiben. Ein Weg, den nur der Desktop zeigt, ist für die
Hälfte der Besucher keiner.
"""

from __future__ import annotations

from typing import Final

#: Je Sprache die sechs Einträge: Ziel, Beschriftung, Ausblendeklasse.
#: Die Reihenfolge hier ist die Reihenfolge im Menü. Alle Beschriftungen
#: stammen aus dem Bestand — jede stand schon in einem der alten Menüs; neu
#: ist allein die Börse, deren Wort aus dem Titel ihrer Seite kommt.
ENTRIES: Final[dict[str, list[tuple[str, str, str]]]] = {
    "de": [
        ("/funktionen.html", "Funktionen", "hide-small"),
        ("/ki-modelle.html", "KI-Modelle", "hide-small"),
        ("/boerse.html", "Tauschbörse", ""),
        ("#preis", "Preis", "hide-tiny"),
        ("/changelog.html", "Neuerungen", "hide-small"),
        ("/handbuch.html", "Handbuch", ""),
    ],
    "en": [
        ("/en/features.html", "Features", "hide-small"),
        ("/en/ai-models.html", "AI models", "hide-small"),
        ("/en/exchange.html", "Exchange", ""),
        ("#pricing", "Price", "hide-tiny"),
        ("/en/changelog.html", "What’s new", "hide-small"),  # noqa: RUF001
        ("/en/manual.html", "Manual", ""),
    ],
    "es": [
        ("/es/features.html", "Funciones", "hide-small"),
        ("/es/ai-models.html", "Modelos de IA", "hide-small"),
        ("/es/exchange.html", "Intercambio", ""),
        ("#pricing", "Precio", "hide-tiny"),
        ("/es/changelog.html", "Novedades", "hide-small"),
        ("/es/manual.html", "Manual", ""),
    ],
    "fr": [
        ("/fr/features.html", "Fonctions", "hide-small"),
        ("/fr/ai-models.html", "Modèles IA", "hide-small"),
        ("/fr/exchange.html", "Échange", ""),
        ("#pricing", "Prix", "hide-tiny"),
        ("/fr/changelog.html", "Nouveautés", "hide-small"),
        ("/fr/manual.html", "Manuel", ""),
    ],
    "it": [
        ("/it/features.html", "Funzioni", "hide-small"),
        ("/it/ai-models.html", "Modelli IA", "hide-small"),
        ("/it/exchange.html", "Scambio", ""),
        ("#pricing", "Prezzo", "hide-tiny"),
        ("/it/changelog.html", "Novità", "hide-small"),
        ("/it/manual.html", "Manuale", ""),
    ],
    "pt": [
        ("/pt/features.html", "Funções", "hide-small"),
        ("/pt/ai-models.html", "Modelos de IA", "hide-small"),
        ("/pt/exchange.html", "Troca", ""),
        ("#pricing", "Preço", "hide-tiny"),
        ("/pt/changelog.html", "Novidades", "hide-small"),
        ("/pt/manual.html", "Manual", ""),
    ],
}

#: Die Startseite je Sprache. Ein Anker wirkt nur auf der Seite, die ihn
#: trägt — von einer Unterseite aus muss er die Startseite mitnennen, sonst
#: springt er ins Nichts der eigenen Seite.
HOME: Final[dict[str, str]] = {
    "de": "/",
    "en": "/en/",
    "es": "/es/",
    "fr": "/fr/",
    "it": "/it/",
    "pt": "/pt/",
}


def nav_links(language: str, *, current: str = "", on_home: bool = False) -> str:
    """Die sechs Verweise als HTML, ohne das umgebende ``<nav>``.

    ``current`` ist der Pfad der Seite, die das Menü trägt (etwa
    ``/en/manual.html``); der passende Eintrag bekommt ``aria-current``.
    ``on_home`` sagt, ob die Seite selbst die Startseite ist — nur dort
    bleiben Anker kurz.
    """
    entries = ENTRIES.get(language, ENTRIES["de"])
    parts: list[str] = []
    for target, label, hide in entries:
        address = target
        if target.startswith("#") and not on_home:
            address = HOME.get(language, "/") + target
        marker = ' aria-current="page"' if current and target == current else ""
        attribute = f' class="{hide}"' if hide else ""
        parts.append(f'<a{attribute} href="{address}"{marker}>{label}</a>')
    return "".join(parts)


#: Die Beschriftung des Aufklappmenüs je Sprache. Sie steht nur für
#: Vorlesegeräte da — sichtbar ist das Symbol.
MENU_LABELS: Final[dict[str, str]] = {
    "de": "Menü",
    "en": "Menu",
    "es": "Menú",
    "fr": "Menu",
    "it": "Menu",
    "pt": "Menu",
}

#: Drei Striche als Symbol. **Kein Zeichen aus einer Schrift und kein Emoji**
#: (Hausregel): Ein Glyph hängt davon ab, was der Rechner installiert hat,
#: eine Zeichnung nicht.
MENU_MARK: Final[str] = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round"/></svg>'
)


def nav_menu(language: str, *, current: str = "", on_home: bool = False) -> str:
    """Die sechs Verweise in einem Aufklapper, der am Rechner keiner ist.

    **Warum ein ``details`` und kein Skript.** Auf einem Handy passten von
    sechs Einträgen nur zwei in die Zeile; die übrigen vier wurden per CSS
    ausgeblendet, und damit kannte die Hälfte der Besucher vier Wege nicht.
    Robert am 31.08.2026: „mach doch ein aufklappmenü für mobil."

    Am Rechner soll dieselbe Leiste aber eine Leiste bleiben — ein Aufklapper,
    wo Platz ist, verlangt einen Klick für nichts. Beides aus **einem** Markup
    geht, weil das Verstecken nicht geschieht: Das Browser-Stylesheet blendet
    die Kinder eines geschlossenen ``details`` mit ``display`` aus, und eine
    eigene ``display``-Regel gewinnt dagegen. Am Rechner steht deshalb der
    Inhalt offen und das Symbol verschwindet; erst unterhalb der Umbruchbreite
    dreht sich beides um.

    Dieselbe Bauart trägt der Sprachwechsel daneben seit jeher — und sie
    braucht keine Zeile JavaScript, funktioniert also auch, wenn nichts lädt.
    """
    return (
        f'<details class="menu">'
        f'<summary aria-label="{MENU_LABELS.get(language, MENU_LABELS["de"])}">'
        f"{MENU_MARK}</summary></details>"
        f'<div class="menu-panel">'
        f"{nav_links(language, current=current, on_home=on_home)}"
        f"</div>"
    )
