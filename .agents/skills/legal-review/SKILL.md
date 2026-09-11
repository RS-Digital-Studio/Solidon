---
name: legal-review
description: >
  Erstellt eine quellenbelegte rechtliche und lizenzbezogene Vorprüfung für
  Solidon, Website und Auslieferung. Benutzen bei Fragen zu Nutzungsrechten,
  Datenschutz, Verkauf, Rechtstexten oder gesetzlichen Produktpflichten.
  Prüft zuerst Anwendbarkeit und Rechtsstand; erteilt keine juristische Freigabe.
---

# Rechte und rechtliche Vorprüfung

Prüfe die konkrete Nutzung oder Veröffentlichung. Eine Lizenzliste, ein grüner
Test und ein früherer Audit sind Belege für Teilfragen, keine Rechtsfreigabe.
Halte gesicherte Tatsachen, rechtliche Bewertung und fehlende Angaben auseinander.

## Auftrag und Anwendbarkeit

Ermittle aus Anfrage und Projektunterlagen: handelnde Person oder Firma,
Zielmärkte, Verbraucher oder Unternehmen, kostenloses oder entgeltliches
Angebot, tatsächlichen Vertriebsweg, betroffene Version und Prüfdatum. Eine
deutsche Website allein legt weder alle Zielmärkte noch alle Pflichten fest.
Frage nach fehlenden Angaben, wenn sie die Bewertung ändern; prüfe davon
unabhängige Punkte weiter. Keine stillen Annahmen über Unternehmensgröße,
Rechteinhaberschaft, Einwilligungen oder bereits erfolgte Veröffentlichungen.

Wähle nur die betroffenen Themen: Rechte an Code und Medien, Datenverarbeitung,
Verträge und Verbraucherinformationen, Barrierefreiheit oder Produktsicherheit.
Ein Lizenzcheck für eine Schrift wird nicht automatisch zum gesamten Rechtsaudit.

## Quellen und Bestandsaufnahme

Lies den einschlägigen Bauplan über `.agents/skills/bauplan/SKILL.md`, die Lizenzregeln in `AGENTS.md`
und vorhandene Unterlagen. Je Thema sind dies insbesondere:

| Thema | Belege im Repository |
|---|---|
| Abhängigkeiten und Paket | `pyproject.toml`, `constraints.txt`, `app/core/knowledge/data/third_party_licenses/`, `tests/test_licences.py`, `tests/test_sbom.py`; bei einer Auslieferung zusätzlich der tatsächliche Paketinhalt. |
| Bilder, Schriften, Modelle | `ASSET-RIGHTS.toml`, `tests/data/LICENSE`, Originalquellen und Lizenztexte der konkret verwendeten Fassungen. |
| Vertrag und Website | `EULA.md`, `AGB.md`, `WIDERRUF.md`, `DATENSCHUTZ.md`, `website/CLAUDE.md`, erzeugte Seiten und tatsächlich bedienbarer Vertriebsweg. |
| Daten und Sicherheitszusagen | Betroffene Aufrufer und Endpunkte unter `app/` und `website/api/`, `app/branding.py`, Aufbewahrung, Empfänger und öffentliche Aussagen. |

Suche bestehende Audits, etwa `AUDIT-RECHT-LIZENZEN-SICHERHEIT-2026-08-31.md`,
und offene Einträge in `ROADMAP.md`. Überprüfe ihre Aussagen am heutigen Stand.
Lies keine geheimen Schlüssel, vollständigen Kundendaten oder Zugangskonfigurationen,
wenn Dateinamen, Schema oder Aufrufer zur Prüfung ausreichen.

Rechtsfragen erfordern aktuelle Originalquellen. Öffne die konkrete Vorschrift
und prüfe Fassung, Geltungsgebiet, Übergangsregel und Anwendungsdatum getrennt:

- Deutsche Gesetze: [Gesetze im Internet](https://www.gesetze-im-internet.de/),
  insbesondere BGB, EGBGB, DDG, TDDDG, UrhG und je Anwendungsfall BFSG/BFSGV.
- EU-Recht: [DSGVO](https://eur-lex.europa.eu/eli/reg/2016/679/oj) und
  [Cyber Resilience Act](https://eur-lex.europa.eu/eli/reg/2024/2847/oj),
  jeweils mit aktueller Fassung und gegebenenfalls amtlichen Berichtigungen.
- Nutzungsrechte: Original-Lizenztext und Bedingungen des Rechteinhabers für
  genau die verwendete Version; Produktbeschreibung und SPDX-Kürzel reichen
  bei unklarer Reichweite nicht. Behördenhinweise als Auslegung kennzeichnen.

Diese Liste ist ein Einstieg, keine Behauptung, dass alle Vorschriften gelten.
Ein Suchtreffer ersetzt das Lesen nicht. Ist eine Quelle nicht abrufbar,
kennzeichne die offene Verifikation; erfinde keine Fundstelle oder aktuelle Frist.
Context7 dient Bibliotheksdokumentation, nicht als Rechtsquelle.

## Prüfung und Ergebnis

Verfolge bei Rechten die Kette von Quelle und Fassung über Bearbeitung bis zur
beabsichtigten Nutzung: kommerziell, Weitergabe, Einbettung, Namensnennung,
Lizenzhinweise und weitere Bedingungen. Quellcode, Modellgewichte und erzeugte
Ausgaben können unterschiedlichen Bedingungen unterliegen. Fehlende Nachweise
bedeuten ungeklärte Rechte, nicht automatisch eine bewiesene Rechtsverletzung.

Gleiche Rechtstexte mit dem Verhalten ab: Was wird wirklich gesendet, gespeichert,
verkauft und zugesagt? Ein umformulierter Satz behebt keine abweichende Umsetzung.
BFSG-Anwendbarkeit und technische Zugänglichkeit getrennt beurteilen;
ein bestandener WCAG-Test beantwortet nicht die gesamte Rechtsfrage.

Führe passende bestehende Tests nur für die untersuchten technischen Aussagen
aus, beispielsweise `test_asset_rights.py`, `test_legal.py` oder
`test_licence_notices.py`; Ablauf und Ergebnisnachweis über `.agents/skills/pruefen/SKILL.md`.

Je Befund: betroffener Stand und Datei, tatsächliche Nutzung, Vorschrift oder
Lizenzabschnitt mit Link und Abrufdatum, Begründung der Anwendbarkeit,
Auswirkung, konkreter Vorschlag und verbleibende Unsicherheit. Juristisch
klärungsbedürftige Punkte als präzise Fragen formulieren. Keine pauschalen
Aussagen wie „rechtssicher“ oder „vollständig DSGVO-konform“.

Bei beauftragten Änderungen die zuständige Quelle bearbeiten und generierte
Seiten über `.agents/skills/erzeugen/SKILL.md` aktualisieren. Ungeklärte Tatsachen nicht in Vertragstext
verwandeln. Veröffentlichung, Kontaktaufnahme und verbindliche Erklärungen
erfordern einen entsprechenden Auftrag; eine Vorprüfung erteilt ihn nicht.
