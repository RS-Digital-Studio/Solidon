# Sondierung: .claude/konzept-veroeffentlichung-1.0.md

**Titel:** Konzept: Erste Veröffentlichung (Solidon 1.0)
**Stand laut Dokument:** Stand 06.08.2026. — mit Nachträgen „Nachgetragen am 08.08.2026", „Berichtigt am 06.08.2026", „Nachgezogen am 08.08.2026", „Stand nach V4c (08.08.2026)"
**Zweck:** Fachliche SSOT der ersten Veröffentlichung: Ist-Zustand, Design-Entscheidungen zu Bezahlmodell, Aktivierung und Härtung, Umsetzungsplan V0–V10, Risiken, offene Einkaufsentscheidungen und Fortschrittstabelle.

**Alterung:** 5/5 — Das Dokument ist ein laufender Veröffentlichungsplan mit Fortschrittstabelle: Testzahlen, Commit-Stände, „offen/fertig"-Marken und git-Zustand veralten mit jedem Arbeitstag — die Nachträge vom 08.08.2026 haben binnen zwei Tagen fünf Ist-Aussagen überholt. Dazu kommen viele externe Zahlen (MoR-Gebühren, Azure-Preis, Zertifikatslage, Hoster-Limits), die eigenständig altern und Entscheidungen tragen.

## Gliederung

- §1 Ist-Zustand
- §2 Design-Entscheidungen
- §3 Nicht-Ziele dieser Veröffentlichung
- §4 Umsetzungsplan
- §5 Reihenfolge
- §6 Risiken
- §7 Entscheidungen und was offen bleibt
- §8 Der private Schlüssel
- §9 Fortschritt

## Extern prüfbare Behauptungen (20)

- **[hoch/preis] Paddle / Lemon Squeezy / Stripe** — Merchant of Record kostet rund 5 % plus Transaktionsgebühr, Stripe direkt etwa 1,5 %; bei 49 € rund 1,70 € Unterschied je Verkauf  
  _Ort:_ §2 D
- **[hoch/marktlage] Lemon Squeezy / Stripe** — Lemon Squeezy ist heute Teil von Stripe und wird weiter als Merchant of Record betrieben  
  _Ort:_ §2 D
- **[hoch/funktionsumfang] Paddle, Lemon Squeezy** — Paddle und Lemon Squeezy können vorab erzeugte Schlüsselvorräte ausliefern (License-Key-Delivery), also ohne eigenen Server  
  _Ort:_ §2 D
- **[hoch/recht] Merchant of Record (EU-Umsatzsteuer, OSS)** — Ein MoR wird rechtlich selbst der Verkäufer, schuldet die Umsatzsteuer im Land des Käufers, meldet sie und stellt die Rechnung  
  _Ort:_ §2 D
- **[mittel/recht] EU One-Stop-Shop / § 19 UStG** — Bei EU-B2C-Direktverkauf digitaler Güter liegen OSS-Registrierung und Kleinunternehmerregelung beim Verkäufer  
  _Ort:_ §2 D
- **[hoch/recht] Digitale-Dienste-Gesetz (DDG) § 5** — Eine Anschrift im Impressum ist nach § 5 DDG Pflicht  
  _Ort:_ §1.3
- **[hoch/recht] CA/Browser Forum, Code-Signing-Baseline-Requirements** — Seit Juni 2023 geben Zertifizierungsstellen keine Code-Signing-Schlüssel mehr als exportierbare Datei (PFX) heraus; sie liegen auf Token oder Cloud-HSM  
  _Ort:_ §2 E
- **[hoch/preis] Microsoft Azure Trusted Signing** — Azure Trusted Signing kostet ~10 $/Monat, signiert ohne Hardware in der CI, verlangt Nachweise zum Unternehmen  
  _Ort:_ §2 E, §7 Punkt 2
- **[hoch/preis] OV-Code-Signing-Zertifikat (Sectigo/DigiCert u. a.)** — OV-Code-Signing-Zertifikat auf Token/HSM kostet ~250–400 €/Jahr  
  _Ort:_ §2 E
- **[mittel/funktionsumfang] Microsoft Defender SmartScreen** — Unsignierte Setup-Dateien lösen bei Windows SmartScreen „Unbekannter Herausgeber" aus; Reputation baut sich über Zeit und Downloadzahl auf  
  _Ort:_ §2 E, §7 Punkt 2
- **[mittel/preis] Apple Developer Program** — macOS-Auslieferung bräuchte Beglaubigung und ein Apple-Programm für 99 $/Jahr  
  _Ort:_ §3
- **[hoch/funktionsumfang] Cloudflare Pages, Netlify** — Cloudflare Pages deckelt bei 25 MB je Datei, Netlify ähnlich — 255 MB je Fassung schließen die üblichen Statik-Dienste aus  
  _Ort:_ §7 Punkt 3
- **[hoch/funktionsumfang] Google Workspace, Google Sites** — Google Workspace liefert keine Dateien aus (kein Webspace, kein FTP); Google Sites nimmt kein fertiges HTML entgegen und kann version.json nicht als rohes JSON unter fester Adresse ausliefern  
  _Ort:_ §2 H
- **[hoch/funktionsumfang] Google Cloud DNS, Squarespace Domains** — Die Zone von rs-digital.org liegt in Google Cloud DNS, Registrierung bei Squarespace; keines der beiden Häuser bietet eine Oberfläche für einen freien A-Record  
  _Ort:_ §2 H
- **[mittel/api] RFC 8032 (EdDSA)** — Ed25519-Verifikation nach RFC 8032 in reinem Python in etwa 90 Zeilen; Testvektoren aus RFC 8032 verfügbar  
  _Ort:_ §2 B, §6
- **[niedrig/fassung] PyPI: cryptography, pynacl** — Weder `cryptography` noch `pynacl` liegen im Baum; als Rückfall käme `cryptography` in Frage  
  _Ort:_ §2 B, §6
- **[mittel/funktionsumfang] Cython, PyInstaller** — Cython als reine Bauabhängigkeit kann `licence`/`activation` nach C übersetzen, so dass kein .pyc im Paket liegt  
  _Ort:_ §2 I H5, V4c
- **[niedrig/funktionsumfang] GitHub Actions, GitHub CLI** — GitHub Actions hebt Artefakte sieben Tage auf; `gh` per `winget install GitHub.cli` installierbar  
  _Ort:_ §2 H, V1
- **[mittel/marktlage] Domain solidon3d.de** — Die Domain solidon3d.de wird beim Webspace-Anbieter registriert und verwaltet; Support-Adresse support@solidon3d.de  
  _Ort:_ §2 H, V2
- **[mittel/preis] Webspace-/Objektspeicher-Anbieter** — Gebraucht wird gewöhnlicher Webspace mit SFTP, HTTPS und Platz für rund 255 MB je Fassung; sonst Objektspeicher  
  _Ort:_ §7 Punkt 3

## Intern prüfbare Behauptungen (15)

- **[hoch]** Das Tor war am 06.08.2026 grün mit 2872 Tests, 10 übersprungen, 11 abgewählt; später „2913 Tests" bzw. „2913 Tests decken nicht ab"  
  _Prüfen:_ .venv\Scripts\python.exe -m pytest -q — Testzahl vergleichen  
  _Ort:_ §1.1, §9 (V3), §7
- **[hoch]** Acht Beispielprojekte, das achte (dose-mit-deckel) zunächst uncommittet; README nannte sieben  
  _Prüfen:_ app/core/examples.py zählen, README.md:41 lesen, git status  
  _Ort:_ §1.1, §1.2, V0
- **[mittel]** Handbuch achtzehn Seiten (§1.1), laut Nachtrag jetzt dreiunddreißig Seiten und achtundzwanzig Abbildungen  
  _Prüfen:_ app/core/manual.py Seitenliste zählen bzw. tools/make_manual.py laufen lassen  
  _Ort:_ §1.1 und Nachtrag-Tabelle
- **[hoch]** constraints.txt liegt nicht im Repository — der eigentliche Blocker (später als erledigt markiert)  
  _Prüfen:_ git ls-files constraints.txt  
  _Ort:_ §1.2, Nachtrag, V0
- **[hoch]** Es gibt keine Zeile Code zu Bezahlung, Testlauf, Aktivierung (später erledigt: app/core/activation/, b5b5096, TRIAL_DAYS = 14)  
  _Prüfen:_ ls app/core/activation/, grep TRIAL_DAYS, git show b5b5096  
  _Ort:_ §1.3, Nachtrag
- **[hoch]** Kein EULA, keine AGB, keine Widerrufsbelehrung (später erledigt: EULA.md, AGB.md, WIDERRUF.md, 6456a95)  
  _Prüfen:_ Dateien im Wurzelverzeichnis prüfen, git show 6456a95  
  _Ort:_ §1.3, Nachtrag
- **[hoch]** Anschrift, Hoster und Zahlungsdienstleister fehlen weiterhin; drei Platzhalter mit Entwurfshinweis, den ein Test erzwingt  
  _Prüfen:_ grep -r "\[" website/impressum.html website/datenschutz.html; den erzwingenden Test in tests/ suchen  
  _Ort:_ Nachtrag, §1.3, V2
- **[hoch]** 13 lokale Commits nicht gepusht, origin/main steht auf 4700309; unklar ob die CI je grün lief, gh nicht installiert  
  _Prüfen:_ git log origin/main..main, gh run list  
  _Ort:_ §1.1, V1
- **[mittel]** 35 geänderte Dateien, drei unversionierte im Baum  
  _Prüfen:_ git status  
  _Ort:_ §1.2
- **[mittel]** ROADMAP.md:526 („es gibt kein Remote") ist veraltet; ROADMAP.md:2033 gehört auf [x] (aa48f10 legt Fit über fits an OpResult an)  
  _Prüfen:_ ROADMAP.md an den genannten Zeilen lesen, git show aa48f10  
  _Ort:_ §1.1, §1.4
- **[hoch]** P0–P12 abgeschlossen, drei Hauptwege als Ende-zu-Ende-Tests (AGENTS.md nennt vier Wege aus Bauplan §2.2)  
  _Prüfen:_ ROADMAP.md Phasenstand, tests/ nach Hauptwege-Tests durchsehen  
  _Ort:_ §1.1, V6
- **[mittel]** Schichtanalyse braucht 1,05 s statt der 300 ms aus §31 — wird dokumentierte Grenze  
  _Prüfen:_ .venv\Scripts\python.exe -m pytest -q -m performance  
  _Ort:_ §1.4, §3, V10
- **[hoch]** APP_VERSION steht auf 0.0.1 (app/branding.py:35) und pyproject.toml:7 ebenso; soll auf 1.0.0  
  _Prüfen:_ beide Stellen lesen  
  _Ort:_ §2 G, V6
- **[hoch]** integrity.py (H4) fehlt und require() hat keinen Aufrufer — die Grenze greift nicht (später: V4/V4b/V4c fertig, c6b5eea, 7fe8cb9, 19fe09b, PUBLIC_KEY gesetzt)  
  _Prüfen:_ grep -r "require(" app/core/, ls app/core/activation/integrity.py, tests/test_licence_boundary.py laufen lassen, git show c6b5eea 7fe8cb9 19fe09b  
  _Ort:_ V3-Kasten, §9
- **[hoch]** Fortschrittstabelle §9: V0, V3, V4, V4b, V4c fertig; V1, V2, V5, V6, V7, V8, V9 offen — Aufwand zwölf bis sechzehn Arbeitstage, drei bis fünf Wochen  
  _Prüfen:_ §9 gegen ROADMAP.md und git log seit 08.08.2026 abgleichen  
  _Ort:_ §9, §5