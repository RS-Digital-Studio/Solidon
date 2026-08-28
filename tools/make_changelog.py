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
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"
SITE = "https://solidon3d.de"

sys.path.insert(0, str(ROOT))

from app.branding import APP_NAME, APP_VERSION  # noqa: E402
from app.core import changes  # noqa: E402
from app.i18n import SOURCE_LANGUAGE, TranslatableText, _, language_name  # noqa: E402
from app.i18n.catalog import available_languages, read_catalog  # noqa: E402
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
    empty: str
    change_one: str
    change_many: str
    topic_one: str
    topic_many: str


COPY_MESSAGES: Final[dict[str, TranslatableText]] = {
    "title": _("Neuerungen — {app}"),
    "description": _("Alle Neuerungen nach Version: klar erklärt, ohne CAD-Fachwissen."),
    "skip": _("Zum Inhalt springen"),
    "features": _("Funktionen"),
    "manual": _("Handbuch"),
    "news": _("Neuerungen"),
    "demo": _("Demo"),
    "language": _("Sprache wählen"),
    "kicker": _("Neuerungen"),
    "heading": _("Was ist neu in {app}?"),
    "lead": _(
        "Neue Werkzeuge, einfachere Abläufe und behobene Stolpersteine — "
        "verständlich erklärt und nach Version geordnet."
    ),
    "select": _("Version"),
    "current": _("diese Version"),
    "version": _("Version"),
    "app_note": _(
        "Dieselben Neuerungen finden Sie auch direkt in Solidon3D unter Hilfe → Neuerungen."
    ),
    "no_script": _("Ohne JavaScript stehen alle Versionen vollständig untereinander."),
    "home": _("Startseite"),
    "legal": _("Impressum"),
    "privacy": _("Datenschutz"),
    "preview_alt": _("Das Hauptfenster von Solidon3D mit Modell, Verlauf und Prüfbericht"),
    "empty": _("Für diese Version liegt kein Verlauf bei."),
    "change_one": _("Neuerung", "Changelog-Zähler"),
    "change_many": _("Neuerungen", "Changelog-Zähler"),
    "topic_one": _("Thema", "Changelog-Zähler"),
    "topic_many": _("Themen", "Changelog-Zähler"),
}


def copy_for(language: str) -> Copy:
    """Die Rahmentexte einer Sprache aus ihrem einzigen Katalog lesen."""
    catalog = read_catalog(language)
    translated: dict[str, str] = {}
    for field_name, message in COPY_MESSAGES.items():
        key = f"{message.context}\x04{message.msgid}" if message.context else message.msgid
        translated[field_name] = (
            message.msgid if language == SOURCE_LANGUAGE else catalog.get(key, message.msgid)
        )
    return Copy(**translated)


def page_path(language: str) -> str:
    """Der Webpfad einer Sprache, ohne eine feste Sprachliste."""
    return "changelog.html" if language == SOURCE_LANGUAGE else f"{language}/changelog.html"


BRAND_MARK = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
    'aria-hidden="true">'
    '<path d="M12 2.6 21 7.5v9L12 21.4 3 16.5v-9z" stroke-linejoin="round"/>'
    '<path d="M3 7.5 12 12.4l9-4.9M12 12.4v9" stroke-linejoin="round"/>'
    "</svg>"
)


def path_for(language: str) -> Path:
    """Der Ausgabeort einer Sprache."""
    return WEBSITE / page_path(language)


def address_for(language: str) -> str:
    """Die öffentliche Adresse einer Sprache."""
    return f"{SITE}/{page_path(language)}"


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
            f'<li><a href="/{page_path(other)}" hreflang="{other}" lang="{other}"{current}>'
            f"{html.escape(language_name(other))}</a></li>"
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
        f'<a href="/{page_path(language)}" aria-current="page">{html.escape(copy.news)}</a>'
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


def _summary(entry: changes.Entry, copy: Copy) -> str:
    """Eine kurze, auch ohne Fachsprache verständliche Größenordnung."""
    changes_count = len(entry.points)
    topics_count = len(entry.groups)
    changes_word = copy.change_one if changes_count == 1 else copy.change_many
    topics_word = copy.topic_one if topics_count == 1 else copy.topic_many
    return f"{changes_count} {changes_word} · {topics_count} {topics_word}"


def _entry(entry: changes.Entry, selected: str, copy: Copy) -> str:
    """Eine Version mit ihren kundennahen Gruppen und Punkten."""
    groups = []
    for index, group in enumerate(entry.groups, start=1):
        title = (
            '<div class="release-group-head">'
            f'<span class="release-group-index" aria-hidden="true">{index:02d}</span>'
            f"<h3>{html.escape(group.title)}</h3></div>"
            if group.title
            else ""
        )
        points = "".join(f"<li>{html.escape(point)}</li>" for point in group.points)
        groups.append(f'<div class="release-group">{title}<ul>{points}</ul></div>')
    summary = _summary(entry, copy)
    badge = (
        f'<span class="release-badge">{html.escape(copy.current)}</span>'
        if entry.version == APP_VERSION
        else ""
    )
    hidden = "" if entry.version == selected else " hidden"
    return (
        f'<article class="release-card" id="{version_id(entry.version)}" '
        f'data-changelog-entry data-version="{html.escape(entry.version)}" '
        f'data-announcement="{html.escape(f"{entry.version}: {summary}", quote=True)}"{hidden}>'
        '<header class="release-heading">'
        f'<div><p class="release-version-label">{html.escape(copy.version)}</p>'
        f"<h2>{html.escape(entry.version)}</h2>"
        f'<p class="release-summary">{html.escape(summary)}</p></div>{badge}'
        f'</header><div class="release-groups">{"".join(groups)}</div></article>'
    )


def render_page(language: str) -> str:
    """Eine vollständige Sprachfassung als statisches HTML."""
    copy = copy_for(language)
    entries = changes.history(language)
    selected = (
        APP_VERSION
        if any(entry.version == APP_VERSION for entry in entries)
        else entries[0].version
        if entries
        else ""
    )
    cards = (
        "".join(_entry(entry, selected, copy) for entry in entries)
        if entries
        else f'<p class="release-empty">{html.escape(copy.empty)}</p>'
    )
    picker = _picker(entries, selected, copy) if entries else ""
    no_script = (
        "<noscript>"
        f'<p class="release-noscript">{html.escape(copy.no_script)}</p>'
        "<style>.release-card[hidden]{display:block!important}</style>"
        "</noscript>"
        if entries
        else ""
    )
    canonical = address_for(language)
    title = copy.title.format(app=APP_NAME)
    heading = copy.heading.format(app=APP_NAME)
    icon_stamp = stamp_of(WEBSITE / "icon.svg")
    style_stamp = stamp_of(WEBSITE / "style.css")
    script_stamp = stamp_of(WEBSITE / "site.js")
    return f"""<!doctype html>
<html lang="{language}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(copy.description, quote=True)}">
<link rel="canonical" href="{canonical}">
{_alternates()}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Solidon3D">
<meta property="og:url" content="{canonical}">
<meta property="og:title" content="{html.escape(title, quote=True)}">
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
      <h1>{html.escape(heading)}</h1>
      <p class="lead">{html.escape(copy.lead)}</p>
      {picker}
      <p class="release-app-note">{html.escape(copy.app_note)}</p>
    </div>
  </section>
  <section class="changelog-content">
    <div class="wrap" id="release-list" data-changelog-list>
      {no_script}
      <p class="visually-hidden" data-changelog-status aria-live="polite"></p>
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
