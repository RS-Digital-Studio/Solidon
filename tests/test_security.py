"""Öffentlicher Sicherheitsweg und interner CRA-Ablauf."""

from pathlib import Path

from app.branding import SECURITY_SUPPORT_UNTIL

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"

PAGES = {
    "de": WEBSITE / "security.html",
    "en": WEBSITE / "en" / "security.html",
    "es": WEBSITE / "es" / "security.html",
    "fr": WEBSITE / "fr" / "security.html",
    "it": WEBSITE / "it" / "security.html",
    "pt": WEBSITE / "pt" / "security.html",
}

INDEXES = {
    "de": WEBSITE / "index.html",
    "en": WEBSITE / "en" / "index.html",
    "es": WEBSITE / "es" / "index.html",
    "fr": WEBSITE / "fr" / "index.html",
    "it": WEBSITE / "it" / "index.html",
    "pt": WEBSITE / "pt" / "index.html",
}

ADDRESSES = {
    "de": "/security.html",
    "en": "/en/security.html",
    "es": "/es/security.html",
    "fr": "/fr/security.html",
    "it": "/it/security.html",
    "pt": "/pt/security.html",
}

PAID_WORDING = {
    "de": "kostenpflichtige Kauflizenz",
    "en": "paid perpetual-use licence",
    "es": "licencia de pago y compra única",
    "fr": "licence payante achetée une fois",
    "it": "licenza a pagamento acquistata una volta",
    "pt": "licença paga de compra única",
}

FREE_VERSION_ONE = {
    "de": ("kostenlose version 1", "kostenlose 1.x-aktualisierungen"),
    "en": ("free version 1", "free 1.x updates"),
    "es": ("versión 1 gratuita", "actualizaciones 1.x gratuitas"),
    "fr": ("version 1 gratuite", "mises à jour 1.x gratuites"),
    "it": ("versione 1 gratuita", "aggiornamenti 1.x gratuiti"),
    "pt": ("versão 1 gratuita", "atualizações 1.x gratuitas"),
}

LONG_DATE = {
    "de": "{day}. Oktober {year}",
    "en": "{day} October {year}",
    "es": "{day} de octubre de {year}",
    "fr": "{day} octobre {year}",
    "it": "{day} ottobre {year}",
    "pt": "{day} de outubro de {year}",
}


def _long_date(language: str) -> str:
    """Sprachform der einen Produktkonstante, wie sie die Website verwendet."""
    assert SECURITY_SUPPORT_UNTIL.month == 10
    return LONG_DATE[language].format(
        day=SECURITY_SUPPORT_UNTIL.day,
        year=SECURITY_SUPPORT_UNTIL.year,
    )


def _short_date(language: str) -> str:
    separator = "." if language == "de" else "/"
    return separator.join(
        (
            f"{SECURITY_SUPPORT_UNTIL.day:02d}",
            f"{SECURITY_SUPPORT_UNTIL.month:02d}",
            str(SECURITY_SUPPORT_UNTIL.year),
        )
    )


def test_every_language_has_the_same_public_security_route() -> None:
    """Eine Sprache mehr ist kein Link auf die deutsche Erklärung."""
    expected_alternates = {
        f'hreflang="{language}" href="https://solidon3d.de{address}"'
        for language, address in ADDRESSES.items()
    }

    for language, page in PAGES.items():
        text = page.read_text(encoding="utf-8")
        assert f'<html lang="{language}">' in text
        assert text.count("<h1>") == 1
        assert '<main id="content" class="legal">' in text
        assert "support@solidon3d.de" in text
        assert _long_date(language) in text
        assert "0.x" in text
        assert PAID_WORDING[language] in text
        for alternate in expected_alternates:
            assert alternate in text


def test_the_purchase_page_names_support_before_the_footer() -> None:
    """Unterstützungsdauer ist eine Kaufinformation, kein Kleingedrucktes."""
    for language, page in INDEXES.items():
        text = page.read_text(encoding="utf-8")
        section_id = "preis" if language == "de" else "pricing"
        anchor = text.index(f'id="{section_id}"')
        start = text.rfind("<section", 0, anchor)
        assert start >= 0, f"{language}: Preisanker steht außerhalb eines Abschnitts"
        end = text.index("</section>", anchor)
        price = text[start:end]
        address = ADDRESSES[language]

        assert f'href="{address}"' in price
        expected = _long_date(language) if language == "en" else _short_date(language)
        assert expected in price
        assert text.count(f'href="{address}"') >= 2


def test_version_one_is_never_called_the_free_version() -> None:
    """Kostenlos ist die befristete Demo 0.x, nicht das Bezahlmodell 1."""
    for language in PAGES:
        catalogue = (
            (ROOT / "app" / "i18n" / "locales" / f"{language}.json").read_text(encoding="utf-8")
            if language != "de"
            else ""
        )
        public = "\n".join(
            (
                PAGES[language].read_text(encoding="utf-8"),
                INDEXES[language].read_text(encoding="utf-8"),
                catalogue,
            )
        ).lower()
        for forbidden in FREE_VERSION_ONE[language]:
            assert forbidden not in public
        for forbidden in FREE_VERSION_ONE["de"]:
            assert forbidden not in catalogue.lower()
        assert PAID_WORDING[language].lower() in public

    policy = "\n".join(
        (
            (ROOT / "SECURITY.md").read_text(encoding="utf-8"),
            (ROOT / "app" / "ui" / "dialogs.py").read_text(encoding="utf-8"),
        )
    ).lower()
    for forbidden in FREE_VERSION_ONE["de"]:
        assert forbidden not in policy
    assert "solidon 1 ist eine kostenpflichtige kauflizenz" in policy


def test_the_internal_incident_clock_keeps_both_final_reports_apart() -> None:
    """Vierzehn Tage und ein Monat gehören zu zwei verschiedenen Fällen."""
    text = (ROOT / "SECURITY-INCIDENT.md").read_text(encoding="utf-8")

    assert text.count("Binnen 24 Stunden") == 2
    assert text.count("Binnen 72 Stunden") == 2
    assert "Spätestens 14 Tage nachdem eine Korrektur" in text
    assert "Binnen eines Monats nach der 72-Stunden-Meldung" in text
    assert _long_date("de") in text
    assert "Solidon3D.cdx.json" in text
    assert "single-reporting-platform-srp" in text


def test_the_twenty_four_hour_route_stays_a_release_blocker_until_it_is_real() -> None:
    """Ein Postfach und eine Anleitung ersetzen weder Alarm noch Vertretung."""
    text = (ROOT / "SECURITY-INCIDENT.md").read_text(encoding="utf-8")
    collapsed = " ".join(text.split())

    assert "Der Meldeweg ist **noch nicht betriebsbereit**" in text
    assert "darf keine Verkaufs- oder Sicherheitsfassung freigegeben werden" in collapsed
    assert "EU-Login" in text
    assert "Primary" in text and "Secondary" in text
    assert "zuständige **CSIRT**" in text
    assert "24 Stunden an sieben Tagen" in text
    assert "höchstens 15 Minuten" in text
    assert "Probelauf außerhalb der Arbeitszeit" in text
    assert "bloße werktägliche Postfachprüfung genügt nicht" in collapsed


def test_the_repository_security_policy_matches_the_public_promise() -> None:
    """Meldeweg, Produktgrenze und Zeitraum kommen aus einer Zusage."""
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    assert "support@solidon3d.de" in text
    assert "kostenpflichtige Kauflizenz" in text
    assert _long_date("de") in text
    assert "zwei Arbeitstagen" in text
    assert "keinen Lizenzschlüssel" in text
