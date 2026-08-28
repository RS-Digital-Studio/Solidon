"""Den kundenlesbaren Versionsverlauf für die Website erzeugen.

Die Inhalte stehen bereits je Sprache unter ``changelog/`` und reisen von dort
auch in die Anwendung. Dieses Werkzeug baut nur den Webrahmen darum: Auswahl,
Navigation und Gestaltung. So gibt es weiterhin genau eine gepflegte Aussage
darüber, was eine Version gebracht hat.

Aufruf::

    .venv/Scripts/python.exe tools/make_changelog.py
"""

from __future__ import annotations

import html
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"
SITE = "https://solidon3d.de"

sys.path.insert(0, str(ROOT))

from app.branding import APP_VERSION  # noqa: E402
from app.core import changes  # noqa: E402
from app.i18n.catalog import available_languages  # noqa: E402
from tools.stamp_assets import stamp_of  # noqa: E402


@dataclass(frozen=True, slots=True)
class Copy:
    """Die wenigen Rahmentexte einer Sprachfassung."""

    title: str
    description: str
    skip: str
    features: str
    manual: str
    news: str
    demo: str
    language: str
    kicker: str
    heading: str
    lead: str
    select: str
    current: str
    version: str
    app_note: str
    no_script: str
    home: str
    legal: str
    privacy: str
    preview_alt: str


COPY = {
    "de": Copy(
        title="Changelog: Neuerungen und Verbesserungen — Solidon3D",
        description=(
            "Alle Neuerungen von Solidon3D nach Version: neue Werkzeuge, "
            "Verbesserungen und behobene Stolpersteine für den 3D-Druck."
        ),
        skip="Zum Inhalt springen",
        features="Funktionen",
        manual="Handbuch",
        news="Neuerungen",
        demo="Demo",
        language="Sprache wählen",
        kicker="Produktfortschritt",
        heading="Was sich in Solidon3D geändert hat.",
        lead=(
            "Neue Werkzeuge, spürbare Verbesserungen und behobene Stolpersteine — "
            "nach Version geordnet und so beschrieben, wie sie beim Arbeiten auffallen."
        ),
        select="Version auswählen",
        current="Diese Version",
        version="Version",
        app_note="Dieselben Neuerungen finden Sie direkt in Solidon3D unter Hilfe → Neuerungen.",
        no_script="Ohne JavaScript stehen alle Versionen vollständig untereinander.",
        home="Startseite",
        legal="Impressum",
        privacy="Datenschutz",
        preview_alt="Das Hauptfenster von Solidon3D mit Modell, Verlauf und Prüfbericht",
    ),
    "en": Copy(
        title="Changelog: what\u2019s new and improved — Solidon3D",
        description=(
            "Every Solidon3D release note by version: new tools, improvements "
            "and fixed pain points for 3D printing."
        ),
        skip="Skip to content",
        features="Features",
        manual="Manual",
        news="What\u2019s new",
        demo="Demo",
        language="Choose language",
        kicker="Product progress",
        heading="What changed in Solidon3D.",
        lead=(
            "New tools, meaningful improvements and fixed pain points — organised "
            "by version and described as you experience them while working."
        ),
        select="Choose a version",
        current="This version",
        version="Version",
        app_note=(
            "You can find the same release notes inside Solidon3D under Help → What\u2019s new."
        ),
        no_script="Without JavaScript, every version is shown in full below.",
        home="Home",
        legal="Legal notice",
        privacy="Privacy",
        preview_alt="The Solidon3D main window with model, history and inspection report",
    ),
    "es": Copy(
        title="Historial de cambios: novedades y mejoras — Solidon3D",
        description=(
            "Todas las novedades de Solidon3D por versión: herramientas nuevas, "
            "mejoras y obstáculos resueltos para la impresión 3D."
        ),
        skip="Saltar al contenido",
        features="Funciones",
        manual="Manual",
        news="Novedades",
        demo="Demo",
        language="Elegir idioma",
        kicker="Evolución del producto",
        heading="Qué ha cambiado en Solidon3D.",
        lead=(
            "Herramientas nuevas, mejoras perceptibles y obstáculos resueltos, "
            "ordenados por versión y descritos tal como se notan al trabajar."
        ),
        select="Elegir una versión",
        current="Esta versión",
        version="Versión",
        app_note="Encontrará las mismas novedades en Solidon3D, en Ayuda → Novedades.",
        no_script="Sin JavaScript, todas las versiones aparecen completas una tras otra.",
        home="Inicio",
        legal="Aviso legal",
        privacy="Privacidad",
        preview_alt=(
            "La ventana principal de Solidon3D con modelo, historial e informe de inspección"
        ),
    ),
    "fr": Copy(
        title="Journal des modifications : nouveautés et améliorations — Solidon3D",
        description=(
            "Toutes les nouveautés de Solidon3D par version : nouveaux outils, "
            "améliorations et obstacles supprimés pour l'impression 3D."
        ),
        skip="Aller au contenu",
        features="Fonctions",
        manual="Manuel",
        news="Nouveautés",
        demo="Démo",
        language="Choisir la langue",
        kicker="Évolution du produit",
        heading="Ce qui a changé dans Solidon3D.",
        lead=(
            "De nouveaux outils, des améliorations sensibles et des obstacles "
            "supprimés — classés par version et décrits tels qu'ils se présentent au travail."
        ),
        select="Choisir une version",
        current="Cette version",
        version="Version",
        app_note="Vous trouverez les mêmes nouveautés dans Solidon3D sous Aide → Nouveautés.",
        no_script="Sans JavaScript, toutes les versions sont affichées intégralement à la suite.",
        home="Accueil",
        legal="Mentions légales",
        privacy="Confidentialité",
        preview_alt=(
            "La fenêtre principale de Solidon3D avec le modèle, l'historique et le rapport"
        ),
    ),
    "it": Copy(
        title="Cronologia delle modifiche: novità e miglioramenti — Solidon3D",
        description=(
            "Tutte le novità di Solidon3D per versione: nuovi strumenti, "
            "miglioramenti e ostacoli risolti per la stampa 3D."
        ),
        skip="Vai al contenuto",
        features="Funzioni",
        manual="Manuale",
        news="Novità",
        demo="Demo",
        language="Scegli la lingua",
        kicker="Evoluzione del prodotto",
        heading="Che cosa è cambiato in Solidon3D.",
        lead=(
            "Nuovi strumenti, miglioramenti concreti e ostacoli risolti, ordinati "
            "per versione e descritti così come si notano durante il lavoro."
        ),
        select="Scegli una versione",
        current="Questa versione",
        version="Versione",
        app_note="Trovi le stesse novità in Solidon3D alla voce Aiuto → Novità.",
        no_script=(
            "Senza JavaScript, tutte le versioni sono mostrate per intero una dopo l'altra."
        ),
        home="Pagina iniziale",
        legal="Note legali",
        privacy="Privacy",
        preview_alt=(
            "La finestra principale di Solidon3D con modello, cronologia e rapporto di controllo"
        ),
    ),
    "pt": Copy(
        title="Registo de alterações: novidades e melhorias — Solidon3D",
        description=(
            "Todas as novidades do Solidon3D por versão: novas ferramentas, "
            "melhorias e obstáculos resolvidos para impressão 3D."
        ),
        skip="Ir para o conteúdo",
        features="Funções",
        manual="Manual",
        news="Novidades",
        demo="Demo",
        language="Escolher idioma",
        kicker="Evolução do produto",
        heading="O que mudou no Solidon3D.",
        lead=(
            "Novas ferramentas, melhorias visíveis e obstáculos resolvidos, "
            "organizados por versão e descritos tal como se sentem durante o trabalho."
        ),
        select="Escolher uma versão",
        current="Esta versão",
        version="Versão",
        app_note="Encontra as mesmas novidades no Solidon3D em Ajuda → Novidades.",
        no_script="Sem JavaScript, todas as versões aparecem completas umas após as outras.",
        home="Início",
        legal="Aviso legal",
        privacy="Privacidade",
        preview_alt=(
            "A janela principal do Solidon3D com modelo, histórico e relatório de verificação"
        ),
    ),
}

LANGUAGE_NAMES = {
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "pt": "Português",
}

PAGE_PATHS = {
    "de": "changelog.html",
    "en": "en/changelog.html",
    "es": "es/changelog.html",
    "fr": "fr/changelog.html",
    "it": "it/changelog.html",
    "pt": "pt/changelog.html",
}

BRAND_MARK = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
    'aria-hidden="true">'
    '<path d="M12 2.6 21 7.5v9L12 21.4 3 16.5v-9z" stroke-linejoin="round"/>'
    '<path d="M3 7.5 12 12.4l9-4.9M12 12.4v9" stroke-linejoin="round"/>'
    "</svg>"
)


def path_for(language: str) -> Path:
    """Der Ausgabeort einer Sprache."""
    return WEBSITE / PAGE_PATHS[language]


def address_for(language: str) -> str:
    """Die öffentliche Adresse einer Sprache."""
    return f"{SITE}/{PAGE_PATHS[language]}"


def home_for(language: str) -> str:
    """Die Startseite derselben Sprache."""
    return "/" if language == "de" else f"/{language}/"


def feature_for(language: str) -> str:
    """Die Funktionsseite derselben Sprache."""
    return "/funktionen.html" if language == "de" else f"/{language}/features.html"


def manual_for(language: str) -> str:
    """Das Handbuch derselben Sprache."""
    return "/handbuch.html" if language == "de" else f"/{language}/manual.html"


def price_for(language: str) -> str:
    """Der Preisabschnitt derselben Sprache."""
    mark = "preis" if language == "de" else "pricing"
    return f"{home_for(language)}#{mark}"


def version_id(version: str) -> str:
    """Eine stabile Sprungmarke aus einer Versionsnummer."""
    return "version-" + "-".join(part for part in version.split(".") if part)


def _alternates() -> str:
    """Die Sprachzuordnung für Suchmaschinen."""
    rows = [
        f'<link rel="alternate" hreflang="{language}" href="{address_for(language)}">'
        for language in available_languages()
    ]
    rows.append(f'<link rel="alternate" hreflang="x-default" href="{address_for("de")}">')
    return "\n".join(rows)


def _switcher(language: str, copy: Copy) -> str:
    """Der Sprachwechsel führt immer zur gleichen Seitenart."""
    rows = []
    for other in available_languages():
        current = ' aria-current="page"' if other == language else ""
        rows.append(
            f'<li><a href="/{PAGE_PATHS[other]}" hreflang="{other}" lang="{other}"{current}>'
            f"{html.escape(LANGUAGE_NAMES[other])}</a></li>"
        )
    return (
        '<details class="langs">'
        f'<summary aria-label="{html.escape(copy.language)}">{language.upper()}</summary>'
        f"<ul>{''.join(rows)}</ul></details>"
    )


def _header(language: str, copy: Copy) -> str:
    """Die vertraute Kopfzeile der übrigen Website-Seiten."""
    return (
        '<header class="site"><div class="wrap">'
        f'<a class="brand" href="{home_for(language)}">{BRAND_MARK}Solidon<span>3D</span></a>'
        '<nav class="lang">'
        f'<a class="hide-small" href="{feature_for(language)}">{html.escape(copy.features)}</a>'
        f'<a href="/{PAGE_PATHS[language]}" aria-current="page">{html.escape(copy.news)}</a>'
        f'<a class="hide-tiny" href="{manual_for(language)}">{html.escape(copy.manual)}</a>'
        f"{_switcher(language, copy)}"
        f'<a class="cta" href="{price_for(language)}">{html.escape(copy.demo)}</a>'
        "</nav></div></header>"
    )


def _picker(entries: tuple[changes.Entry, ...], selected: str, copy: Copy) -> str:
    """Die Auswahl aller Fassungen, neueste zuerst."""
    options = []
    for entry in entries:
        label = entry.version
        if entry.version == APP_VERSION:
            label += f" — {copy.current}"
        active = " selected" if entry.version == selected else ""
        options.append(
            f'<option value="{html.escape(entry.version)}"{active}>{html.escape(label)}</option>'
        )
    return (
        '<div class="release-picker">'
        f'<label for="release-version">{html.escape(copy.select)}</label>'
        '<select id="release-version" data-changelog-select aria-controls="release-list">'
        f"{''.join(options)}</select></div>"
    )


def _entry(entry: changes.Entry, selected: str, copy: Copy) -> str:
    """Eine Version mit ihren kundennahen Gruppen und Punkten."""
    groups = []
    for group in entry.groups:
        title = f"<h3>{html.escape(group.title)}</h3>" if group.title else ""
        points = "".join(f"<li>{html.escape(point)}</li>" for point in group.points)
        groups.append(f'<div class="release-group">{title}<ul>{points}</ul></div>')
    badge = (
        f'<span class="release-badge">{html.escape(copy.current)}</span>'
        if entry.version == APP_VERSION
        else ""
    )
    hidden = "" if entry.version == selected else " hidden"
    return (
        f'<article class="release-card" id="{version_id(entry.version)}" '
        f'data-changelog-entry data-version="{html.escape(entry.version)}"{hidden}>'
        '<header class="release-heading">'
        f"<div><p>{html.escape(copy.version)}</p><h2>{html.escape(entry.version)}</h2></div>{badge}"
        f'</header><div class="release-groups">{"".join(groups)}</div></article>'
    )


def render_page(language: str) -> str:
    """Eine vollständige Sprachfassung als statisches HTML."""
    copy = COPY[language]
    entries = changes.history(language)
    selected = (
        APP_VERSION
        if any(entry.version == APP_VERSION for entry in entries)
        else entries[0].version
    )
    cards = "".join(_entry(entry, selected, copy) for entry in entries)
    canonical = address_for(language)
    icon_stamp = stamp_of(WEBSITE / "icon.svg")
    style_stamp = stamp_of(WEBSITE / "style.css")
    script_stamp = stamp_of(WEBSITE / "site.js")
    return f"""<!doctype html>
<html lang="{language}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(copy.title)}</title>
<meta name="description" content="{html.escape(copy.description, quote=True)}">
<link rel="canonical" href="{canonical}">
{_alternates()}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Solidon3D">
<meta property="og:url" content="{canonical}">
<meta property="og:title" content="{html.escape(copy.title, quote=True)}">
<meta property="og:description" content="{html.escape(copy.description, quote=True)}">
<meta property="og:image" content="{SITE}/handbuch/{language}/main-window.png">
<meta property="og:image:alt" content="{html.escape(copy.preview_alt, quote=True)}">
<meta name="theme-color" content="#f7f6f3" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#171614" media="(prefers-color-scheme: dark)">
<link rel="icon" href="/icon.svg?v={icon_stamp}">
<link rel="stylesheet" href="/style.css?v={style_stamp}">
</head>
<body>
<a class="skip" href="#content">{html.escape(copy.skip)}</a>
{_header(language, copy)}
<main id="content" class="changelog-page">
  <section class="changelog-hero">
    <div class="wrap changelog-intro">
      <p class="hero-kicker">{html.escape(copy.kicker)}</p>
      <h1>{html.escape(copy.heading)}</h1>
      <p class="lead">{html.escape(copy.lead)}</p>
      {_picker(entries, selected, copy)}
      <p class="release-app-note">{html.escape(copy.app_note)}</p>
    </div>
  </section>
  <section class="changelog-content">
    <div class="wrap" id="release-list" data-changelog-list>
      <noscript>
        <p class="release-noscript">{html.escape(copy.no_script)}</p>
        <style>.release-card[hidden]{{display:block!important}}</style>
      </noscript>
      {cards}
    </div>
  </section>
</main>
<footer class="site"><div class="wrap">
  © 2026 RS Digital ·
  <a href="{home_for(language)}">{html.escape(copy.home)}</a> ·
  <a href="{manual_for(language)}">{html.escape(copy.manual)}</a> ·
  <a href="mailto:support@solidon3d.de">support@solidon3d.de</a> ·
  <a href="/impressum.html">{html.escape(copy.legal)}</a> ·
  <a href="/datenschutz.html">{html.escape(copy.privacy)}</a>
</div></footer>
<script src="/site.js?v={script_stamp}" defer></script>
</body>
</html>
"""


def write_pages() -> tuple[Path, ...]:
    """Alle vorhandenen Sprachen schreiben und ihre Ziele zurückgeben."""
    written = []
    for language in available_languages():
        target = path_for(language)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_page(language), encoding="utf-8")
        written.append(target)
    return tuple(written)


def main() -> int:
    """Alle vorhandenen Sprachen in einem Lauf schreiben."""
    written = write_pages()
    names = ", ".join(target.relative_to(WEBSITE).as_posix() for target in written)
    print(f"{len(written)} Changelog-Seiten geschrieben: {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
