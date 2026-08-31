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


def test_withdrawal_api_never_mutates_on_a_link_preview() -> None:
    text = (ROOT / "CONSUMER-WITHDRAWAL.md").read_text(encoding="utf-8")

    assert "GET, Link-Vorschau, Crawler oder Reload dürfen" in text
    assert "Erst dieser\nPOST" in text


def test_ai_disclosure_keeps_local_and_cloud_paths_in_the_same_gate() -> None:
    text = (ROOT / "AI-COMPLIANCE.md").read_text(encoding="utf-8")

    assert "ersten Anthropic- und Ollama-Aufruf" in text
    assert "sendet nichts" in text


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
