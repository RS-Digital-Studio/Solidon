"""Fail-closed Verträge der rechtlichen und organisatorischen Produktakten.

Die Tests entscheiden keine Rechtsfrage. Sie verhindern, dass eine
Freigabesperre, ein notwendiger Ablauf oder die Übergabe an die sichtbare
Oberfläche bei einer Textänderung unbemerkt verschwindet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

RECORDS: dict[str, tuple[str, ...]] = {
    "PRODUCT-SAFETY.md": (
        "Freigabestatus: GESPERRT",
        "allgemeines Werkzeug",
        "medizinische oder dentale Zweckbestimmung",
        "Safety Business Gateway",
        "mindestens zehn Jahre",
        "Rücknahme oder Rückruf",
    ),
    "EXPORT-COMPLIANCE.md": (
        "Freigabestatus: GESPERRT",
        "Art. 5n",
        "Anhang XXXIX",
        "Eigentum und Kontrolle",
        "Offlineaktivierung ist keine Ausnahme",
        "Dual-Use-Klassifizierung",
        "BAFA",
    ),
    "PRIVACY-COMPLIANCE.md": (
        "Freigabestatus: GESPERRT",
        "Verzeichnis der Verarbeitungstätigkeiten",
        "Interessenabwägungen",
        "Anthropic mit eigenem API-Schlüssel",
        "Backups",
        "DSFA-Schwellenentscheidung",
        "netcup/Serveradministration",
        "nachweisbare Löschung spätestens",
        "PayPal/Steuerberatung",
        "Pseudonymisierung, keine Anonymisierung",
        "Ratelimit-Scheduler",
        "monatlichen Reichweitenzeilen",
    ),
    "AI-COMPLIANCE.md": (
        "Freigabestatus: GESPERRT",
        "Sie interagieren mit einem KI-System",
        "Interaktion mit einem KI-System",
        "vor der ersten Modellkommunikation",
        "Anthropic",
        "Ollama",
        "Art. 50 Abs. 2",
        "KI-Kompetenz nach Art. 4",
    ),
    "CONSUMER-WITHDRAWAL.md": (
        "Freigabestatus: GESPERRT",
        "§ 356a BGB",
        "Vertrag widerrufen",
        "Widerruf bestätigen",
        "ständig verfügbare, hervorgehoben platzierte und leicht zugängliche Funktion",
        "POST",
        "dauerhaften Datenträger",
        "idempotent",
        "/api/withdrawal.php?do=preview",
        "/api/withdrawal.php?do=submit",
        "8 KiB",
    ),
}


@pytest.mark.parametrize("name", sorted(RECORDS))
def test_compliance_record_is_substantial_and_keeps_its_release_gate(name: str) -> None:
    text = (ROOT / name).read_text(encoding="utf-8")

    assert len(text) >= 3000, f"{name} ist keine belastbare Prozessakte"
    missing = [sentence for sentence in RECORDS[name] if sentence not in text]
    assert not missing, f"{name} verliert Pflichtinhalt: {missing}"


def test_the_product_scope_does_not_turn_industry_interest_into_a_reference() -> None:
    text = (ROOT / "PRODUCT-SAFETY.md").read_text(encoding="utf-8")

    assert "Amsler" not in text
    assert "Ivoclar" not in text
    assert "Kundenreferenz" not in text


def test_printability_is_not_a_safety_or_conformity_claim() -> None:
    text = (ROOT / "PRODUCT-SAFETY.md").read_text(encoding="utf-8")
    words = " ".join(text.split())

    for required in (
        "geometrische und drucktechnische Eignung",
        "Tragfähigkeit",
        "Lebensmittelechtheit",
        "Schutzvorrichtungen einschließlich persönlicher Schutzausrüstung",
        "Gas-/Druckanwendungen",
        "elektrische Sicherheit",
        "tragende Konstruktionen",
        "Nutzerinhalt, Agentenausgabe oder mitgelieferter",
        "keine CE-Kennzeichnung",
        "CRA-Klassifizierung",
        "nicht automatisch zum Hersteller",
        "mitgelieferte digitale Konstruktionsunterlagen",
        "kein besonderes Zertifizierungs- oder Konformitätsbewertungsverfahren",
        "keine unbelegte Zertifizierungsbehauptung",
    ):
        assert required in words


def test_recipe_exchange_stays_local_and_creates_no_hosted_processing() -> None:
    text = (ROOT / "PRIVACY-COMPLIANCE.md").read_text(encoding="utf-8")
    assert "ausschließlich ein lokaler Offline-Dateiweg" in text
    assert "RS Digital nimmt keine Rezepte oder Kontaktdaten entgegen" in text
    assert "keinen VVT-Eintrag" in text
    assert "spätere gehostete Austauschfunktion" in text

    privacy = (ROOT / "DATENSCHUTZ.md").read_text(encoding="utf-8")
    assert "ausschließlich als Datei lokal exportieren und" in privacy
    assert "keinen RS-Dienst" in privacy
    assert "Tauschbörse" not in privacy
    assert "Veröffentlichungsnachweis" not in privacy
    assert "Art. 16 der Verordnung (EU) 2022/2065" not in privacy
    assert "Sechs klar begrenzte Netzwege" not in privacy


def test_the_public_website_has_no_feedback_form() -> None:
    privacy = (ROOT / "DATENSCHUTZ.md").read_text(encoding="utf-8")
    words = " ".join(privacy.split())

    assert "Informationsseiten dieser Website sind statisch" in words
    assert "keinen Fragebogen und kein Rückmeldungsformular" in words
    assert "Rückmeldungsbogen auf der Startseite" not in words


def test_privacy_notice_does_not_claim_an_unproven_processor_contract() -> None:
    """Der reale Art.-28-Nachweis kommt aus dem Vertragskonto, nicht aus Git."""

    privacy = (ROOT / "DATENSCHUTZ.md").read_text(encoding="utf-8")
    assert "Mit dem Anbieter besteht ein Vertrag über Auftragsverarbeitung" not in privacy
    assert "netcup GmbH" in privacy


def test_withdrawal_api_never_mutates_on_a_link_preview() -> None:
    text = (ROOT / "CONSUMER-WITHDRAWAL.md").read_text(encoding="utf-8")

    assert "GET, Link-Vorschau, Crawler oder Reload dürfen" in text
    assert "Erst dieser\nPOST" in text


def test_ai_disclosure_keeps_local_and_cloud_paths_in_the_same_gate() -> None:
    text = (ROOT / "AI-COMPLIANCE.md").read_text(encoding="utf-8")

    assert "ersten Anthropic- und Ollama-Aufruf" in text
    assert "sendet nichts" in text
    for required in (
        "bis zu zwölf frühere Chatbeiträge",
        "Steckbrief der gesamten aktuellen Szene",
        "Prüfbericht",
        "Werkzeugschemata",
        "automatisch gerenderte",
        "Netzgeometrie selbst",
        "Lokales Ollama-Ziel (Loopback)",
        "Entferntes Ollama-Ziel",
        "festen technischen Prüfauftrag",
        "Wechsel von lokal zu",
    ):
        assert required in text

    privacy = (ROOT / "DATENSCHUTZ.md").read_text(encoding="utf-8")
    assert "bis zu zwölf frühere Chatbeiträge" in privacy
    assert "automatisch gerenderte Ansichten" in privacy
    assert "Die Projektdatei und die Netzgeometrie selbst" in privacy
    assert "bei einer vom Nutzer eingetragenen entfernten Adresse" in privacy
    assert "festen technischen Prüfauftrag" in privacy


def test_the_single_incident_intake_covers_all_three_legal_clocks() -> None:
    text = (ROOT / "SECURITY-INCIDENT.md").read_text(encoding="utf-8")

    for required in (
        "Gemeinsamer Eingang für CRA, DSGVO und Produktsicherheit",
        "DSGVO-Uhr",
        "Produktsicherheits-Uhr",
        "72 Stunden",
        "Safety Business Gateway",
        "derselben Vorgangskennung",
    ):
        assert required in text, required

    assert "`INC-JJJJ-NNN`" in text
    assert "`SEC-JJJJ-NNN`" not in text


def test_public_security_text_does_not_claim_an_unproven_reporting_operation() -> None:
    """Die Kundenseite verspricht keinen ENISA-Betrieb vor seiner Abnahme."""

    files = [ROOT / "SECURITY.md", *(ROOT / "website").glob("**/security.html")]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "ENISA Single Reporting Platform" not in text, path
        assert "plataforma única de ENISA" not in text, path
        assert "plateforme unique de l’ENISA" not in text, path
        assert "piattaforma unica ENISA" not in text, path
        assert "plataforma única da ENISA" not in text, path


def test_product_liability_cutoff_uses_the_corrected_directive_date() -> None:
    """Die Berichtigung 2026 verschiebt den sachlichen Beginn nicht um einen Tag."""

    files = [
        ROOT / "PRODUCT-SAFETY.md",
        ROOT / "AUDIT-RECHT-LIZENZEN-SICHERHEIT-2026-08-31.md",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "nach dem 8. Dezember 2026" in text, path
        assert "nach dem 9. Dezember 2026" not in text, path
